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
    """Hard cumulative per-panel CALL and DOLLAR caps, persisted across re-runs.

    The registration claims both counters persist and that the run aborts on breach of
    either. An earlier version tracked only calls, so the dollar authorisation was a
    number in a document rather than an enforced limit -- and the dollar cap is the one
    that actually protects the human's account, because a contingency (a promoted member,
    a qwen fallback onto a metered tier) can stay inside the call cap while multiplying
    spend.
    """

    limits: dict
    usd_limits: dict
    run_total_usd: float
    rates: dict
    tokens: dict
    used: dict = field(default_factory=dict)
    usd_used: dict = field(default_factory=dict)
    path: Path = CAPS_PATH

    @classmethod
    def load(cls, reg: dict, path: Path = CAPS_PATH) -> "Caps":
        cost = reg["cost"]
        cap = cost["hard_cap"]
        state = json.loads(path.read_text()) if path.exists() else {}
        rates = {}
        for panel in cost["panels"].values():
            for agent, rec in panel["per_member"].items():
                if "rate_in" in rec:
                    rates[agent] = {"in": rec["rate_in"], "out": rec["rate_out"]}
        for name, c in (cost.get("contingencies") or {}).items():
            if "rate_in" in c:
                rates[name] = {"in": c["rate_in"], "out": c["rate_out"]}
        return cls(limits=cap["per_panel_cumulative_calls"],
                   usd_limits=cap.get("per_panel_cumulative_usd", {}),
                   run_total_usd=float(cap.get("run_total_usd", 0.0)),
                   rates=rates, tokens=cost["token_projection"],
                   used=state.get("used", {}), usd_used=state.get("usd_used", {}),
                   path=path)

    def price(self, agent: str) -> float:
        """Projected USD for one call by this agent. Unmetered tiers cost 0."""
        r = self.rates.get(agent)
        if not r:
            return 0.0
        return (self.tokens["prompt_tokens_per_call"] * r["in"]
                + self.tokens["completion_tokens_per_call"] * r["out"]) / 1e6

    def remaining(self, panel: str) -> int:
        return self.limits[panel] - self.used.get(panel, 0)

    def remaining_usd(self, panel: str) -> float:
        return round(self.usd_limits.get(panel, self.run_total_usd)
                     - self.usd_used.get(panel, 0.0), 6)

    def remaining_run_usd(self) -> float:
        return round(self.run_total_usd - sum(self.usd_used.values()), 6)

    def charge(self, panel: str, n: int = 1, agent: str | None = None) -> None:
        """Charge calls AND dollars BEFORE the request, so a crash cannot re-run free."""
        if self.used.get(panel, 0) + n > self.limits[panel]:
            raise RegistrationError(
                f"panel {panel} cumulative CALL cap {self.limits[panel]} would be exceeded "
                f"(used {self.used.get(panel, 0)}, requesting {n}). Caps persist across "
                f"re-runs by design; raising one is a protocol amendment.")
        usd = self.price(agent) * n if agent else 0.0
        if usd:
            if self.usd_used.get(panel, 0.0) + usd > self.usd_limits.get(
                    panel, self.run_total_usd) + 1e-9:
                raise RegistrationError(
                    f"panel {panel} cumulative USD cap "
                    f"{self.usd_limits.get(panel, self.run_total_usd)} would be exceeded "
                    f"(used {self.usd_used.get(panel, 0.0):.4f}, requesting {usd:.4f})")
            if sum(self.usd_used.values()) + usd > self.run_total_usd + 1e-9:
                raise RegistrationError(
                    f"run-total USD authorisation {self.run_total_usd} would be exceeded "
                    f"(used {sum(self.usd_used.values()):.4f}, requesting {usd:.4f}). This "
                    f"is the human's authorised budget; raising it is not a code change.")
        self.used[panel] = self.used.get(panel, 0) + n
        if usd:
            self.usd_used[panel] = round(self.usd_used.get(panel, 0.0) + usd, 6)
        self.persist()

    def persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"used": self.used, "usd_used": self.usd_used, "limits": self.limits,
             "usd_limits": self.usd_limits, "run_total_usd": self.run_total_usd},
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
                    sched: Scheduler, member_index: int = 0,
                    max_attempts: int = 2) -> dict:
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
            # Latin square: the offset must include the MEMBER, or every model gets the
            # same role on the same item and role is perfectly confounded with item --
            # the opposite of what rotating roles is for.
            role = roles[(idx + member_index) % len(roles)]
            for attempt in range(1, max_attempts + 1):
                caps.charge(panel, 1, agent=member["agent"])   # calls AND dollars, before
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
    for mi, member in enumerate(members):       # strictly sequential, one slot at a time
        rep = generate_member(reg, member, items, caps, panel, sched, member_index=mi)
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
    res["_per_item_margin"] = per_item_margin(rows, agents, y, V, riids, is_calib)
    res["n_items_analysed"] = len(set(riids))
    res["agents"] = agents
    res["alignment_audit"] = audits[:0]          # audits are large; summarised not inlined
    return res


def _margin(res: dict, mapname: str, arm: str = "WCT-EM") -> float | None:
    node = res.get("panel_vs_single_best_calibration_selected", {}).get(mapname, {}).get(arm)
    return node["delta_log_loss"]["point"] if node else None


def per_item_margin(rows, agents, y, V, iids, is_calib, mapname: str = "platt"):
    """Per-item (single-best loss - panel loss) on TEST items.

    Positive means the panel beat the calibration-selected best single source on that
    item. Built from the same pieces wct3.arms uses -- same scores, same both-maps fit,
    same calibration-only selection -- so the dose-response is measured on the registered
    quantity rather than a lookalike.
    """
    import numpy as np
    from wct import aggregate as agg
    from wct3.arms import _both_maps

    te = ~is_calib
    panel_score = agg.em_logodds(V, agg.wct_em(V)[1])
    panel_p = _both_maps(panel_score, y, is_calib, allow_nonpositive=True)[mapname]
    singles = {a: _both_maps(agg.wct_u(V[:, [j]]), y, is_calib, allow_nonpositive=True)[mapname]
               for j, a in enumerate(agents)}
    # selection on CALIBRATION only, never test
    exact = {a: agg.log_loss(singles[a][is_calib], y[is_calib]) for a in agents}
    chosen = min(exact, key=exact.get)

    def loss(p):
        q = np.clip(p, 1e-12, 1 - 1e-12)
        return -(y * np.log(q) + (1 - y) * np.log(1 - q))

    margin = (loss(singles[chosen]) - loss(panel_p))[te]
    return {"margin": margin, "item_ids": [i for i, c in zip(iids, is_calib) if not c],
            "selected_single": chosen, "map": mapname}


def dose_response(by_m: dict, floor: float, mapname: str = "platt",
                  n_boot: int = 2000, seed: int = 20260807) -> dict:
    """P2 with the registered uncertainty method and MUTUALLY EXCLUSIVE verdicts.

    `by_m` maps panel size -> per_item_margin() output. The increment is
    margin(M=max) - margin(M=min), paired on the items both panels scored, with a
    percentile CI from the same item-block bootstrap the frozen contrasts use.

    The three verdicts partition the outcome space: lo > floor and hi < floor cannot both
    hold because lo <= hi. An earlier formulation could report SUPPORTS and REFUTES at
    once for a CI wholly inside (0, floor).
    """
    import numpy as np
    from wct import stats

    sizes = sorted(by_m)
    if len(sizes) < 2:
        return {"verdict": "not evaluable", "reason": "fewer than two panel sizes"}
    lo_m, hi_m = sizes[0], sizes[-1]
    a, b = by_m[lo_m], by_m[hi_m]
    shared = [i for i in a["item_ids"] if i in set(b["item_ids"])]
    ia = {i: k for k, i in enumerate(a["item_ids"])}
    ib = {i: k for k, i in enumerate(b["item_ids"])}
    da = np.array([a["margin"][ia[i]] for i in shared])
    db = np.array([b["margin"][ib[i]] for i in shared])
    paired = db - da                       # per-item increment from M=lo to M=hi

    ci = stats.item_bootstrap(shared, lambda rows: float(np.mean(paired[rows])),
                              n_boot=n_boot, seed=seed)
    points = {m: float(np.mean(by_m[m]["margin"])) for m in sizes}
    monotone = all(points[x] <= points[y] for x, y in zip(sizes, sizes[1:]))

    lo, hi = ci.get("lo"), ci.get("hi")
    if lo is None or hi is None:
        verdict = "inconclusive"
    elif lo > floor:
        verdict = "supports"               # increment significantly ABOVE the floor
    elif hi < floor:
        verdict = "refutes"                # increment significantly BELOW the floor
    else:
        verdict = "inconclusive"           # CI spans the floor
    return {
        "estimand": f"margin(M={hi_m}) - margin(M={lo_m}), paired on items",
        "margin_by_M": points,
        "monotone_increasing": monotone,
        "increment": ci.get("point"),
        "ci": {"lo": lo, "hi": hi, "n_boot": ci.get("n_boot"), "alpha": 0.05},
        "detectable_floor": floor,
        "verdict": verdict,
        "n_shared_items": len(shared),
        "adjudication": {
            "supports": "CI lower bound > detectable floor",
            "refutes": "CI upper bound < detectable floor",
            "inconclusive": "CI spans the detectable floor",
            "mutually_exclusive": True,
            "note": ("monotonicity is REPORTED but is not part of the verdict: it is not a "
                     "test and adding it as a conjunct would make the three outcomes "
                     "non-exhaustive"),
        },
    }


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


def run(dry_run: bool = True, registration: Path = PREREG,
        out_dir: Path = Path("out/cycle3"), limit: int | None = None,
        sizes: tuple[int, ...] = (3, 4, 5)) -> dict:
    """The whole registered workflow: ONE generation pass, then every nested panel.

    Generating per-M would regenerate the shared members and, worse, place a later
    model's generation AFTER an earlier panel's analysis -- violating the registered
    "generation strictly before analysis" discipline (B12) while looking like three tidy
    runs. The union of the largest panel is generated once, in model-major order, and
    the nested subsets are then analysed from that single cell.
    """
    reg = load_registration(registration)
    union = panel_members(reg, max(sizes))
    report = preflight(reg, dry_run)
    sched = Scheduler()
    caps = Caps.load(reg)
    panel_label = f"M={max(sizes)}"

    if dry_run:
        for member in union:
            sched.begin_generation(member["agent"])
            sched.end_generation(member["agent"])
        sched.begin_analysis()
        return {"sizes": list(sizes), "union": [x["agent"] for x in union],
                "n_items": reg["dataset"]["n_items"],
                "planned_calls": reg["dataset"]["n_items"] * len(union),
                "cap_remaining": caps.remaining(panel_label),
                "cap_remaining_usd": caps.remaining_usd(panel_label),
                "generated": 0, "preflight": report, "delta": reg["delta"]["value"]}

    import numpy as np
    from exp3 import corpus_v3

    items = corpus_v3.load_corpus()
    if limit:
        items = items[:limit]
    split = reg["analysis_splits"]
    rng = np.random.default_rng(split["split_seed"])
    ids = sorted(i.item_id for i in items)
    calib_ids = set(rng.permutation(ids)[: int(len(ids) * split["calibration_fraction"])].tolist())

    # ---- ONE generation pass over the union, model-major, before any analysis
    events: list[dict] = []
    members = list(union)
    cell, gen_reports = generate_panel(reg, members, items, caps, panel_label, sched)

    # ---- registered contingencies, applied before analysis so the panel is fixed
    for rep in gen_reports:
        if rep["n_ok"] == 0:
            agent = rep["agent"]
            fb = fallback_for(reg, agent)
            if fb:
                events.append({"event": "fallback", "for": agent,
                               "to": fb["model"], "caveat": fb["caveat"]})
            else:
                members, ev = promote(reg, members, agent)
                events.append(ev)

    sched.begin_analysis()

    # ---- every nested subset from the SAME cell
    mapname = "platt"
    by_m, per_m_margin = {}, {}
    for m in sizes:
        want = {x["agent"] for x in panel_members(reg, m)}
        sub = {iid: {a: g for a, g in ags.items() if a in want}
               for iid, ags in cell.items()}
        sub = {iid: ags for iid, ags in sub.items() if len(ags) >= 2}
        res = analyse_panel(reg, items, sub, calib_ids, sched)
        by_m[m] = res
        pim = res.pop("_per_item_margin", None)
        if pim:
            per_m_margin[m] = pim

    floor = reg["power"]["dose_response_increment"]["detectable_at_registered_n"]
    dr = (dose_response(per_m_margin, floor=floor, mapname=mapname)
          if len(per_m_margin) >= 2 else {"verdict": "not evaluable"})

    provenance = {
        "registration_tag": reg["tag"],
        "registration_sha256": hashlib.sha256(registration.read_bytes()).hexdigest(),
        "instrument": report["instrument"],
        "cache_namespace": report["cache"],
        "delta": reg["delta"]["value"],
        "caps_used_calls": caps.used,
        "caps_used_usd": caps.usd_used,
        "events": events,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"sizes": list(sizes), "union": [x["agent"] for x in members],
               "generation_reports": gen_reports,
               "results_by_M": {str(k): v for k, v in by_m.items()},
               "dose_response": dr, "provenance": provenance}
    (out_dir / "cycle3_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str))
    return payload
