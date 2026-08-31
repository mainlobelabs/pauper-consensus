"""Bounded endpoint smoke tests: pin an expected echo per panel member. (B4)

The slice constraints permit smoke tests as the ONLY egress, and B4 cannot be
satisfied without them: an expected echo has to be OBSERVED before it can be
pinned, or the exact-pinned-id rule has no target and defaults to whatever the
provider returns.

Three properties this must hold, each from something that already went wrong:

  * ONE call per endpoint. `nodes.Client.generate` consults the generation cache
    and retries twice, which is how two paid probes in slice 3 returned in 0.03s
    without contacting anything. The probe issues its own request.
  * Identity is checked, never assumed. Expected identity DEFAULTS to the id
    requested; `expected_resolved` is an alias override for the one endpoint that
    legitimately answers under another name, not a licence to skip the check.
  * The local endpoint is pinned by WEIGHTS, not by its echo, because it answers
    under a stale launch alias and an echo cannot tell the registered quantised
    weights from a different model behind the same name.

Output goes to out/slice4/smoke/ ONLY. Nothing here writes the generation cache,
so no smoke output can be mistaken for cycle-3 experimental data.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from exp3.availability import _identity, registered_weights, sanitise  # noqa: F401

def load_harness_env() -> bool:
    """Populate provider credentials the way every other harness surface does.

    solon-harness keeps its keys in ~/.config/solon/harness.env (override with
    SOLON_ENV_FILE) precisely so headless runs pick up OPENROUTER_API_KEY without
    sourcing a shell profile. Reading it through model_client.load_env_file means this
    probe authenticates through the SAME resolution path as the relay's own reviewers,
    rather than depending on whoever happened to export what into this shell -- which is
    why the first attempt reported five endpoints unreachable that were merely
    unauthenticated. Env vars already present always win, so an explicit export still
    overrides the file.
    """
    import sys

    for cand in (Path.home() / "dev/solon-harness/bin",):
        if cand.is_dir() and str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
    try:
        import model_client                                  # noqa: F401
        model_client.load_env_file()
        return True
    except Exception:                                        # noqa: BLE001
        return False


SMOKE_DIR = Path("out/slice4/smoke")
SMOKE_MAX_TOKENS = 64          # a smoke test proves reachability, not capability

# The registered ordering (PLAN.md). M=3 = ranks 1-3, M=4 adds 4, M=5 adds 5,
# rank 6 is the declared margin. Ordering is by identity assurance: the three
# whose PINNED ids still answered in slice 3, then the paid twins.
PANEL: tuple[dict, ...] = (
    {"rank": 1, "agent": "qwen", "family": "qwen", "backend": "local",
     "model": "qwen3.8-27b", "tier": "local", "base": "http://127.0.0.1:8083/v1",
     "expected_resolved": "ornith35",
     "identity_evidence": "model_path /home/jmannings/.lmstudio/models/unsloth/"
                          "Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf n_params 27"},
    # hoonify, NOT openrouter: OpenRouter has no such model id (HTTP 400 "not a valid
    # model ID"), and both prereg_v2 and slice 3's availability record pin this family to
    # the Hoonify endpoint. Registering the wrong backend would have failed every glm
    # generation in cycle 3.
    {"rank": 2, "agent": "glm", "family": "zhipu", "backend": "hoonify",
     "model": "zai-org/GLM-5.2", "tier": "paid"},
    {"rank": 3, "agent": "nemotron", "family": "nvidia", "backend": "openrouter",
     "model": "nvidia/nemotron-3-super-120b-a12b", "tier": "paid"},
    {"rank": 4, "agent": "gptoss", "family": "openai", "backend": "openrouter",
     "model": "openai/gpt-oss-20b", "tier": "paid"},
    {"rank": 5, "agent": "gemma", "family": "google", "backend": "openrouter",
     "model": "google/gemma-4-26b-a4b-it", "tier": "paid"},
    {"rank": 6, "agent": "laguna", "family": "poolside", "backend": "openrouter",
     "model": "poolside/laguna-xs-2.1", "tier": "paid", "role": "declared_margin"},
)

# Registered in advance so a switch is a documented promotion, not a substitution.
QWEN_FALLBACK = {"rank": 1, "agent": "qwen_or", "family": "qwen", "backend": "openrouter",
                 "model": "qwen/qwen3.8-27b", "tier": "paid",
                 "role": "declared_fallback_for_qwen"}

M_SUBSETS = {3: (1, 2, 3), 4: (1, 2, 3, 4), 5: (1, 2, 3, 4, 5)}


class SmokeError(RuntimeError):
    """An endpoint did not answer as the registration requires."""


def local_props(base: str, timeout: float) -> dict:
    """Everything /props exposes about the loaded weights.

    prereg_v2 pins qwen by model_path AND n_params. llama-server's /props does NOT
    expose n_params -- only model_path, model_alias and model_ftype -- so the n_params
    half of the pin is NOT endpoint-verifiable. That is recorded as a known limit rather
    than papered over: claiming a check that is not performed is worse than declaring
    which half of the identity the endpoint can actually confirm.
    """
    import httpx
    try:
        with httpx.Client(timeout=timeout) as h:
            r = h.get(base.rstrip("/").removesuffix("/v1") + "/props")
        if r.status_code != 200:
            return {}
        d = r.json() or {}
        return {"model_path": d.get("model_path"), "model_alias": d.get("model_alias"),
                "model_ftype": d.get("model_ftype"),
                "n_params": d.get("n_params"),
                "n_params_endpoint_verifiable": d.get("n_params") is not None}
    except Exception:                                    # noqa: BLE001
        return {}


def registered_n_params(c: dict) -> float | None:
    """The parameter count (in billions) that the registration pins for this candidate."""
    import re

    m = re.search(r"n_params\s+([\d.]+)", c.get("identity_evidence") or "")
    return float(m.group(1)) if m else None


def gguf_metadata(path: str) -> dict:
    """Read identity metadata from the GGUF file itself.

    llama-server's /props exposes model_path but NOT n_params, and prereg_v2 pins qwen by
    BOTH. The weights file carries its own size label, so the pin is verifiable after all:
    /props says WHICH file is loaded, and the file says what it contains. That chain is
    stronger than either half alone -- an echoed alias cannot detect a swapped file, and a
    file on disk says nothing about what is loaded.
    """
    import struct

    SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?",
           10: "<Q", 11: "<q", 12: "<d"}
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return {}
            _ver, _nt, nkv = struct.unpack("<IQQ", f.read(20))

            def rstr() -> str:
                n, = struct.unpack("<Q", f.read(8))
                return f.read(n).decode("utf-8", "replace")

            def skip(tp: int, count: int = 1) -> None:
                if tp == 8:
                    for _ in range(count):
                        n, = struct.unpack("<Q", f.read(8))
                        f.seek(n, 1)
                elif tp == 9:
                    for _ in range(count):
                        et, = struct.unpack("<I", f.read(4))
                        n, = struct.unpack("<Q", f.read(8))
                        skip(et, n)
                else:
                    f.seek(SZ[tp] * count, 1)

            out: dict = {}
            for _ in range(nkv):
                k = rstr()
                tp, = struct.unpack("<I", f.read(4))
                if tp in FMT:
                    v = struct.unpack(FMT[tp], f.read(SZ[tp]))[0]
                    if "param" in k or "size_label" in k or "block_count" in k:
                        out[k] = v
                elif tp == 8:
                    v = rstr()
                    if k in ("general.name", "general.size_label", "general.architecture",
                             "general.basename"):
                        out[k] = v
                else:
                    skip(tp)
            return out
    except Exception:                                    # noqa: BLE001
        return {}


def parse_n_params_billions(meta: dict) -> float | None:
    """Parameter count in billions, from an exact count or the size label."""
    import re

    exact = meta.get("general.parameter_count")
    if isinstance(exact, (int, float)) and exact > 0:
        return round(float(exact) / 1e9, 2)
    label = str(meta.get("general.size_label") or "")
    m = re.match(r"^\s*([\d.]+)\s*B\s*$", label, re.I)
    return float(m.group(1)) if m else None


def _local_props(base: str, timeout: float) -> str | None:
    """Back-compat shim: just the model_path, which is what _identity compares."""
    return local_props(base, timeout).get("model_path")


def probe_one(c: dict, timeout: float = 120.0) -> dict:
    """Exactly ONE live call. No cache, no retry."""
    import httpx
    from wct import nodes

    rec = {k: c[k] for k in ("rank", "agent", "family", "model", "tier") if k in c}
    rec["role"] = c.get("role", "panel_member")
    t0 = time.time()
    weights = None
    try:
        client = nodes.Client(c["backend"], timeout=timeout, base_url=c.get("base"))
        base = c.get("base") or client.base
        props = {}
        if c["backend"] == "local":
            props = local_props(base, timeout)
            weights = props.get("model_path")
            if weights:
                meta = gguf_metadata(weights)
                n_b = parse_n_params_billions(meta)
                props["n_params_billions"] = n_b
                props["n_params_source"] = "GGUF metadata of the loaded model_path"
                props["gguf_metadata"] = meta
                props["n_params_endpoint_verifiable"] = n_b is not None
            rec["local_props"] = props
        key = getattr(client, "key", None)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        body = {"model": c["model"], "temperature": 0.0, "max_tokens": SMOKE_MAX_TOKENS,
                "messages": [{"role": "user", "content": "Reply with the single word: ok"}]}
        with httpx.Client(timeout=timeout) as h:          # exactly one attempt
            r = h.post(f"{base}/chat/completions", json=body, headers=headers)
        rec["latency_s"] = round(time.time() - t0, 2)
        rec["http_status"] = r.status_code
        if r.status_code != 200:
            rec.update(status="fail", echoed=None,
                       error=sanitise(f"HTTP {r.status_code}: {r.text}"))
        else:
            payload = r.json()
            rec.update(status="ok", echoed=payload.get("model"),
                       usage=payload.get("usage") or {})
    except Exception as e:                                # noqa: BLE001
        rec.update(status="error", echoed=None, latency_s=round(time.time() - t0, 2),
                   error=sanitise(f"{type(e).__name__}: {e}"))
    rec["identity"] = _identity(c, rec.get("echoed"), weights)
    if c["backend"] == "local":
        rec["identity"]["model_ftype"] = props.get("model_ftype")
        rec["identity"]["n_params"] = props.get("n_params_billions")
        rec["identity"]["n_params_source"] = props.get("n_params_source")
        rec["identity"]["n_params_endpoint_verifiable"] = props.get(
            "n_params_endpoint_verifiable", False)
        want_n = registered_n_params(c)
        got_n = props.get("n_params_billions")
        rec["identity"]["registered_n_params"] = want_n
        if got_n is None:
            rec["identity"]["n_params_note"] = (
                "the loaded weights file carries no readable parameter count, so the "
                "n_params half of the pin could not be checked")
            rec["identity"]["matches_expected"] = False
        elif want_n is not None and abs(got_n - want_n) > 0.05:
            rec["identity"]["n_params_match"] = False
            rec["identity"]["matches_expected"] = False
            rec["identity"]["n_params_note"] = (
                f"loaded weights report {got_n}B parameters, registration pins {want_n}B")
        else:
            rec["identity"]["n_params_match"] = True
    return rec


def run(timeout: float = 120.0, include_fallback: bool = True,
        only: set[str] | None = None) -> dict:
    """Probe every panel member once and record its resolved serving identity."""
    load_harness_env()
    targets = [c for c in PANEL if not only or c["agent"] in only]
    if include_fallback and (not only or QWEN_FALLBACK["agent"] in only):
        targets = targets + [QWEN_FALLBACK]
    records = [probe_one(c, timeout) for c in targets]
    out = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "smoke_max_tokens": SMOKE_MAX_TOKENS,
        "attempts_per_endpoint": 1,
        "m_subsets": {str(k): list(v) for k, v in M_SUBSETS.items()},
        "records": records,
    }
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    (SMOKE_DIR / "smoke.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    return out


def expected_echoes(result: dict) -> dict[str, str]:
    """The observed serving identity per agent, for the registration to pin."""
    return {r["agent"]: r.get("echoed") for r in result["records"] if r.get("echoed")}


def verify(result: dict, require_all: bool = True) -> dict:
    """Fail on identity mismatch; report unreachable members as substitution candidates."""
    mismatched, unreachable = [], []
    for r in result["records"]:
        ident = r.get("identity") or {}
        if r.get("status") != "ok":
            unreachable.append(r["agent"])
        elif ident.get("matches_expected") is False:
            mismatched.append({"agent": r["agent"], "requested": ident.get("requested"),
                               "echoed": ident.get("echoed"),
                               "expected": ident.get("expected"),
                               "note": ident.get("note")})
    if mismatched:
        raise SmokeError(
            f"{len(mismatched)} endpoint(s) answered as a DIFFERENT model than registered; "
            f"under the exact-pinned-id rule these are substitutions, not panel members: "
            f"{mismatched}")
    if require_all and unreachable:
        raise SmokeError(f"unreachable at smoke time: {unreachable}")
    return {"mismatched": mismatched, "unreachable": unreachable,
            "expected_echoes": expected_echoes(result)}


def tag_ready(result: dict | None = None) -> tuple[bool, list[str]]:
    """Is the smoke evidence complete enough to FREEZE the registration? (B4)

    B4 requires an expected echo pinned PER PANEL MEMBER so the exact-pinned-id rule has
    an explicit target "rather than a default". A member whose echo was never observed
    falls back to its requested id, which is precisely the default B4 excludes -- so
    tagging on incomplete smoke evidence would freeze a registration that does not meet
    its own acceptance criterion.
    """
    if result is None:
        path = SMOKE_DIR / "smoke.json"
        if not path.exists():
            return False, ["no smoke artifact: out/slice4/smoke/smoke.json is absent"]
        result = json.loads(path.read_text())

    by_agent = {r["agent"]: r for r in result.get("records", [])}
    reasons = []
    for c in PANEL:
        r = by_agent.get(c["agent"])
        if r is None:
            reasons.append(f"{c['agent']}: never probed")
        elif r.get("status") != "ok":
            reasons.append(f"{c['agent']}: {r.get('status')} — no observed echo to pin")
        elif (r.get("identity") or {}).get("matches_expected") is not True:
            reasons.append(f"{c['agent']}: identity did not match the registered target")
        elif (c["backend"] == "local"
              and (r.get("identity") or {}).get("n_params_match") is not True):
            # prereg_v2 pins this endpoint by model_path AND n_params. /props exposes only
            # the former, but the loaded weights file carries its own size label, so both
            # halves are checkable and both must pass.
            reasons.append(f"{c['agent']}: n_params half of the identity pin did not "
                           f"verify against the loaded weights file")
    fb = by_agent.get(QWEN_FALLBACK["agent"])
    if fb is None or fb.get("status") != "ok":
        reasons.append(f"{QWEN_FALLBACK['agent']}: declared fallback unverified")
    return (not reasons), reasons


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-tag-ready", action="store_true")
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()
    if a.probe:
        res = run()
        rep = verify(res, require_all=False)
        print(f"echoes: {rep['expected_echoes']}")
        print(f"unreachable: {rep['unreachable']}")
    ok, reasons = tag_ready()
    if ok:
        print("smoke evidence COMPLETE: every panel member has an observed echo")
        return 0
    print("smoke evidence INCOMPLETE — tagging is blocked:")
    for r in reasons:
        print(f"  - {r}")
    return 1 if a.check_tag_ready else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
