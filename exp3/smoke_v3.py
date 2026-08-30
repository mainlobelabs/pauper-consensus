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
                          "Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf"},
    {"rank": 2, "agent": "glm", "family": "zhipu", "backend": "openrouter",
     "model": "zai-org/GLM-5.2", "tier": "free"},
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
        rec["identity"]["n_params"] = props.get("n_params")
        rec["identity"]["n_params_endpoint_verifiable"] = props.get(
            "n_params_endpoint_verifiable", False)
        if not props.get("n_params_endpoint_verifiable"):
            rec["identity"]["n_params_note"] = (
                "prereg_v2 pins n_params 27, but llama-server /props does not expose it; "
                "the verifiable half of the pin is model_path (+ model_ftype). Recorded "
                "as a known limit, not treated as a passed check.")
    return rec


def run(timeout: float = 120.0, include_fallback: bool = True,
        only: set[str] | None = None) -> dict:
    """Probe every panel member once and record its resolved serving identity."""
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
