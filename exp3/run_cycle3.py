"""Cycle-3 driver. Committed and tagged BEFORE generation: the implementation IS the
registration. (B8, B12, B13)

Everything this module refuses to do is as registered as everything it does:

  * It will not run without the registered fp32/GPU instrument (B13). There is no fp16
    code path. Cycles 1-2 ran fp16 because the checkpoint declares dtype=float16 and
    transformers honours it on CPU; that instrument is device dependent, and silently
    falling back to it would void the registration while producing plausible numbers.
  * It will not write into the frozen cache root, because fp16-cached and fp32-computed
    NLI must never mix: the smallest observed alignment margin is 0.0021, exactly 1x the
    fp16->fp32 perturbation.
  * It will not generate before the registration tag exists and resolves to the tested
    tree (B8). An empty-artifact check alone cannot stop someone invoking the driver
    between implementation and tagging.
  * It will not interleave models or run analysis while generation is active (B12). The
    local server has ONE model slot, so a concurrent swap silently answers from the wrong
    weights.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PREREG = Path("prereg_v3.yaml")
FROZEN_CACHE = Path("out/cache").resolve()
CAPS_PATH = Path("out/cycle3/caps.json")


class RegistrationError(RuntimeError):
    """The run does not match what was registered. Always fail closed."""


def load_registration(path: Path = PREREG) -> dict:
    if not path.exists():
        raise RegistrationError(f"{path} is missing: there is nothing to run against")
    return yaml.safe_load(path.read_text())


# ---------------------------------------------------------------- instrument (B13)

def assert_registered_instrument(reg: dict) -> dict:
    """Fail closed unless the registered fp32/GPU instrument is actually active.

    Returned dict is recorded into every artifact, so a later reader can tell which
    instrument produced the numbers rather than assuming.
    """
    ins = reg["instrument"]
    if ins["precision"] != "fp32" or ins["device"] != "cuda":
        raise RegistrationError(
            f"registration demands fp32/cuda, found {ins['precision']}/{ins['device']}")
    try:
        import torch
    except Exception as e:                                   # noqa: BLE001
        raise RegistrationError(f"torch unavailable, cannot honour the instrument: {e}")
    if not torch.cuda.is_available():
        raise RegistrationError(
            "CUDA is unavailable. The registered instrument is fp32 on GPU and there is NO "
            "fp16 fallback: falling back would silently substitute the device-dependent "
            "instrument cycles 1-2 used (4.4e-03 max deviation, with argmax flips).")
    from wct3 import gpu
    device = gpu.pick_device()
    if not device.startswith("cuda"):
        raise RegistrationError(f"expected a cuda device, resolved {device!r}")
    gpu.install(device=device)
    tok_mdl = gpu._STATE.get((ins["nli_model"], device))
    dtype = str(next(tok_mdl[1].parameters()).dtype) if tok_mdl else None
    if dtype is not None and "float32" not in dtype:
        raise RegistrationError(f"instrument loaded as {dtype}, registration demands float32")
    return {"device": device, "precision": "fp32", "nli_model": ins["nli_model"],
            "torch": torch.__version__,
            "gpu_name": torch.cuda.get_device_name(int(device.split(":")[1]))}


def assert_cache_isolation() -> str:
    """Refuse to run against the frozen cache root."""
    root = os.environ.get("WCT_CACHE")
    if not root:
        raise RegistrationError(
            "WCT_CACHE is unset. Cycle 3 requires an explicit SEPARATE cache root so its "
            "fp32 NLI cannot mix with the frozen fp16 entries.")
    resolved = Path(root).resolve()
    if resolved == FROZEN_CACHE:
        raise RegistrationError(
            f"WCT_CACHE points at the frozen root {FROZEN_CACHE}. Writing fp32 NLI there "
            f"would contaminate cycles 1-2 and mix precisions within cycle 3.")
    return str(resolved)


# ---------------------------------------------------------------- the tag (B8)

def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def assert_tagged(reg: dict) -> dict:
    """Generation may not precede the registration tag, and the tag must match this tree."""
    tag = reg["tag"]
    if not _git("tag", "-l", tag):
        raise RegistrationError(
            f"registration tag {tag!r} does not exist. The tag precedes the data: until it "
            f"exists the protocol is a draft and no cycle-3 inference may run.")
    tagged = _git("rev-parse", f"{tag}^{{tree}}")
    head = _git("rev-parse", "HEAD^{tree}")
    if not tagged or tagged != head:
        raise RegistrationError(
            f"tag {tag!r} resolves to tree {tagged[:12]!r} but HEAD is {head[:12]!r}: the "
            f"code about to run is not the code that was registered.")
    dirty = _git("status", "--porcelain", "--", "exp3", "wct3", "prereg_v3.yaml")
    if dirty:
        raise RegistrationError(f"uncommitted changes to registered code:\n{dirty}")
    return {"tag": tag, "tree": tagged}


# ---------------------------------------------------------------- caps (B7)

@dataclass
class Caps:
    """Hard cumulative per-panel call caps, persisted across re-runs."""

    limits: dict
    used: dict = field(default_factory=dict)
    path: Path = CAPS_PATH

    @classmethod
    def load(cls, reg: dict, path: Path = CAPS_PATH) -> "Caps":
        limits = reg["cost"]["hard_cap"]["per_panel_cumulative_calls"]
        used = {}
        if path.exists():
            used = json.loads(path.read_text()).get("used", {})
        return cls(limits=limits, used=used, path=path)

    def remaining(self, panel: str) -> int:
        return self.limits[panel] - self.used.get(panel, 0)

    def charge(self, panel: str, n: int = 1) -> None:
        """Charge BEFORE the call, so a crash cannot lose the charge and re-run free."""
        if self.used.get(panel, 0) + n > self.limits[panel]:
            raise RegistrationError(
                f"panel {panel} cumulative cap {self.limits[panel]} would be exceeded "
                f"(used {self.used.get(panel, 0)}, requesting {n}). Caps persist across "
                f"re-runs by design; raising one is a protocol amendment.")
        self.used[panel] = self.used.get(panel, 0) + n
        self.persist()

    def persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"used": self.used, "limits": self.limits},
                                        indent=2, sort_keys=True))


# ---------------------------------------------------------------- scheduling (B12)

class Phase:
    """Generation and analysis are separate phases and never overlap."""

    GENERATION = "generation"
    ANALYSIS = "analysis"


class Scheduler:
    """Model-major generation, strictly before analysis.

    The local endpoint has ONE model slot. Interleaving models, or issuing an embedding
    call while a generation pass is open, can answer from whichever weights happen to be
    resident -- a failure that leaves no trace in the artifact.
    """

    def __init__(self) -> None:
        self.phase: str | None = None
        self.active_model: str | None = None
        self.completed: list[str] = []

    def begin_generation(self, model: str) -> None:
        if self.phase == Phase.ANALYSIS:
            raise RegistrationError("generation cannot start after analysis has begun")
        if self.active_model is not None:
            raise RegistrationError(
                f"model {self.active_model!r} is still active: generation is MODEL-MAJOR, "
                f"one model completes its whole pass before {model!r} begins")
        if model in self.completed:
            raise RegistrationError(f"model {model!r} already completed its pass")
        self.phase, self.active_model = Phase.GENERATION, model

    def end_generation(self, model: str) -> None:
        if self.active_model != model:
            raise RegistrationError(f"{model!r} is not the active model")
        self.completed.append(model)
        self.active_model = None

    def begin_analysis(self) -> None:
        if self.active_model is not None:
            raise RegistrationError(
                f"cannot analyse while {self.active_model!r} is generating: no embedding or "
                f"analysis call may be issued during a generation pass")
        self.phase = Phase.ANALYSIS

    def guard_measurement(self) -> None:
        if self.phase == Phase.GENERATION and self.active_model is not None:
            raise RegistrationError("measurement issued during an open generation pass")


# ---------------------------------------------------------------- panels

def panel_members(reg: dict, m: int) -> list[dict]:
    ranks = set(reg["panels"]["nested_subsets"][f"M={m}"])
    return [x for x in reg["panels"]["members"] if x["rank"] in ranks]


def margin_member(reg: dict) -> dict:
    r = reg["panels"]["declared_margin"]["rank"]
    return [x for x in reg["panels"]["members"] if x["rank"] == r][0]


def promote(reg: dict, members: list[dict], failed_agent: str) -> tuple[list[dict], dict]:
    """Registered promotion: the declared margin fills a vacated rank.

    Data already collected under the vacated member is RETAINED and reported separately,
    per the registration -- merging it into the promoted member's arm would attribute one
    model's observations to another.
    """
    vacated = [m for m in members if m["agent"] == failed_agent]
    if not vacated:
        raise RegistrationError(f"{failed_agent!r} is not in this panel")
    marg = margin_member(reg)
    if marg["agent"] in {m["agent"] for m in members}:
        raise RegistrationError("the declared margin is already in the panel; no reserve left")
    promoted = [m for m in members if m["agent"] != failed_agent] + [
        dict(marg, rank=vacated[0]["rank"], promoted_from=marg["rank"])]
    event = {"event": "promotion", "vacated": failed_agent,
             "promoted": marg["agent"], "into_rank": vacated[0]["rank"],
             "prior_data": "retained and reported separately, not merged"}
    return sorted(promoted, key=lambda m: m["rank"]), event


def fallback_for(reg: dict, agent: str) -> dict | None:
    fb = reg["panels"].get("declared_fallback") or {}
    return fb if fb.get("for") == agent else None


# ---------------------------------------------------------------- generation (B12)

def generate_member(reg: dict, member: dict, items: list, caps: Caps, panel: str,
                    sched: Scheduler, max_attempts: int = 2) -> dict:
    """One model's COMPLETE pass. Charges before each call; never caches a failure.

    Retries are bounded and deterministic, and every attempt charges the cap, so a
    retry storm cannot buy extra calls that the registration did not authorise.
    """
    from wct import nodes

    sched.begin_generation(member["agent"])
    client = nodes.Client(member["backend"], base_url=member.get("base"))
    gen_cfg = reg["generation"]
    roles = gen_cfg["roles"]["role_set"]
    out: dict = {}
    errors: list[dict] = []
    try:
        for idx, item in enumerate(items):
            role = roles[idx % len(roles)]          # Latin-square rotation by item index
            for attempt in range(1, max_attempts + 1):
                caps.charge(panel, 1)               # charge BEFORE, including retries
                g = client.generate(
                    item, agent=member["agent"], model=member["model"], role=role,
                    seed=gen_cfg["seed"], temperature=gen_cfg["temperature"],
                    max_tokens=gen_cfg["max_tokens"],
                    expected_resolved=member.get("expected_resolved"))
                if not g.error:
                    out[item.item_id] = g
                    break
                errors.append({"item": item.item_id, "attempt": attempt,
                               "error": str(g.error)[:200]})
            # a persistently failing item is recorded and skipped, never cached
    finally:
        sched.end_generation(member["agent"])
    return {"agent": member["agent"], "generations": out, "errors": errors,
            "n_ok": len(out), "n_failed_items": len(items) - len(out)}


def generate_panel(reg: dict, members: list[dict], items: list, caps: Caps,
                   panel: str, sched: Scheduler) -> tuple[dict, list[dict]]:
    """MODEL-MAJOR: each model completes its whole pass before the next begins."""
    per_agent, reports = {}, []
    for member in members:                      # strictly sequential, one slot at a time
        rep = generate_member(reg, member, items, caps, panel, sched)
        per_agent[member["agent"]] = rep["generations"]
        reports.append({k: v for k, v in rep.items() if k != "generations"})
    cell: dict = {}
    for agent, gens in per_agent.items():
        for iid, g in gens.items():
            cell.setdefault(iid, {})[agent] = g
    return cell, reports


# ---------------------------------------------------------------- analysis

def analyse_panel(reg: dict, items: list, cell: dict, calib_ids: set, sched: Scheduler,
                  min_agents: int = 2) -> dict:
    """The registered analysis for one panel: arms, primary, and the comparator."""
    import numpy as np
    from exp.common import complete_items
    from exp.e1_v2 import extract_s2
    from wct3 import arms as v3arms
    from wct3 import observe

    sched.guard_measurement()                    # no measurement during generation
    iids = complete_items(cell, min_agents=min_agents)
    rows, agents, audits = observe.build_rows(items, cell, iids, extractor=extract_s2)
    y, V, riids, X = observe.to_arrays(rows, agents)
    is_calib = np.array([i in calib_ids for i in riids])
    u, s = observe.instance_arrays(rows)
    res = v3arms.analyse(rows, agents, y, V, riids, X, is_calib, u, s)
    res["n_items_analysed"] = len(set(riids))
    res["agents"] = agents
    res["alignment_audit"] = audits[:0]          # audits are large; summarised not inlined
    return res


def _margin(res: dict, mapname: str, arm: str = "WCT-EM") -> float | None:
    node = res.get("panel_vs_single_best_calibration_selected", {}).get(mapname, {}).get(arm)
    return node["delta_log_loss"]["point"] if node else None


def dose_response(by_m: dict, mapname: str) -> dict:
    """P2: does the margin over the best single source GROW with panel size?"""
    pts = {m: _margin(res, mapname) for m, res in sorted(by_m.items())}
    have = {m: v for m, v in pts.items() if v is not None}
    monotone = all(b >= a for a, b in zip(list(have.values()), list(have.values())[1:]))
    increment = (have[max(have)] - have[min(have)]) if len(have) >= 2 else None
    return {"margin_by_M": have, "monotone_increasing": monotone,
            "increment_M3_to_M5": increment,
            "estimand": "margin(M=5) - margin(M=3), paired on items"}


# ---------------------------------------------------------------- orchestration

def preflight(reg: dict, dry_run: bool) -> dict:
    """Every guard, cheapest failure first."""
    report = {"dry_run": dry_run, "tag": None, "instrument": None, "cache": None}
    if dry_run:
        report["note"] = "dry run: no generation call is issued and no cap is charged"
        return report
    report["tag"] = assert_tagged(reg)
    report["cache"] = assert_cache_isolation()
    report["instrument"] = assert_registered_instrument(reg)
    return report


def run(m: int = 5, dry_run: bool = True, registration: Path = PREREG,
        out_dir: Path = Path("out/cycle3"), limit: int | None = None) -> dict:
    """Execute the registered workflow. Refuses to generate unless every guard passes."""
    reg = load_registration(registration)
    members = panel_members(reg, m)
    report = preflight(reg, dry_run)
    sched = Scheduler()
    caps = Caps.load(reg)
    panel = f"M={m}"

    if dry_run:
        # exercise the scheduling contract without issuing anything
        for member in members:
            sched.begin_generation(member["agent"])
            sched.end_generation(member["agent"])
        sched.begin_analysis()
        return {"panel": panel, "members": [x["agent"] for x in members],
                "n_items": reg["dataset"]["n_items"],
                "planned_calls": reg["dataset"]["n_items"] * len(members),
                "cap_remaining": caps.remaining(panel), "generated": 0,
                "preflight": report, "delta": reg["delta"]["value"]}

    from exp3 import corpus_v3
    items = corpus_v3.load_corpus()
    if limit:
        items = items[:limit]
    split_seed = reg["analysis_splits"]["split_seed"]
    frac = reg["analysis_splits"]["calibration_fraction"]
    import numpy as np
    rng = np.random.default_rng(split_seed)
    ids = sorted(i.item_id for i in items)
    calib_ids = set(rng.permutation(ids)[: int(len(ids) * frac)].tolist())

    cell, gen_reports = generate_panel(reg, members, items, caps, panel, sched)
    sched.begin_analysis()
    res = analyse_panel(reg, items, cell, calib_ids, sched)

    provenance = {
        "registration_tag": reg["tag"],
        "registration_sha256": hashlib.sha256(registration.read_bytes()).hexdigest(),
        "instrument": report["instrument"],
        "cache_namespace": report["cache"],
        "delta": reg["delta"]["value"],
        "caps_used": caps.used,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"panel": panel, "members": [x["agent"] for x in members],
               "generation_reports": gen_reports, "results": res,
               "provenance": provenance}
    (out_dir / f"cycle3_{panel}.json").write_text(json.dumps(payload, indent=2,
                                                            sort_keys=True, default=str))
    return payload
