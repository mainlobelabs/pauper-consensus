"""Measure which registered families actually answer, before anything is registered.

Slice 4 registers a dose-response across panel sizes. The five-family target has failed
TWICE on availability: cycle 1 found three local families, not five (GOTCHAS 2026-08-07),
and cycle 2 rebuilt panel A mid-programme when two of three models left the catalogue. This
module measures rather than assumes.

WHY A GENERATION AND NOT A CATALOGUE LOOKUP. prereg_v2.yaml records the trap exactly: the
:1234 catalogue LISTS qwen3.8-27b and 400s on completion. Any check that asks "is this model
listed" reports it available when it is not.

STATUS IS THREE-VALUED, and identity decides it:
  ok           answered with usable content AND the echoed id matches the registration's
               expected value. Only `ok` counts toward the pinned-family margin.
  substituted  answered, but under an id the registration did not expect. prereg_v2's
               resolution rule forbids substitution, so this is NOT availability of the
               registered model. Reported separately as a possible family for a NEW
               registration, which slice 4 adjudicates.
  fail         no usable content on ONE attempt at this timestamp. Deliberately not called
               "unavailable": one probe cannot distinguish a dead model from a flaky minute,
               and the request permits one attempt per endpoint.

ONE ATTEMPT PER ENDPOINT, no automatic retry: a retry would change the measured protocol and
multiply paid calls. A re-probe is a deliberate second invocation.

LOCAL PROBES RUN STRICTLY SEQUENTIALLY. GOTCHAS records that the local server holds ONE
model slot and that concurrent requests to different models returned 400 and 500 while only
one succeeded. Overlapping local calls would record a good model as failed purely from
contention -- the exact false negative this slice must not produce.

Usage:  PYTHONPATH=. .venv/bin/python -m exp3.availability --confirm
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

SCHEMA_VERSION = 1
REGISTRATION = "prereg_v2.yaml"
OUT = "out/slice3/availability.json"

# family attribution: model ids are not families, and two variants of one family are ONE
# source (the cycle-1 ornith error, GOTCHAS 2026-08-07)
FAMILY = {
    "qwen": "qwen", "laguna": "poolside", "glm": "zhipu",
    "nemotron": "nvidia", "gptoss": "openai", "gemma": "google",
}
PAID_BACKENDS = {"hoonify"}
# rates pinned in prereg_v2.yaml panelA.cost_note: USD per 1M tokens
PAID_RATES = {"hoonify": {"in": 1.40, "out": 4.40}}

# OpenRouter PAID variants of the pinned free ids. `:free` is a TIER SUFFIX, not part of the
# model: openai/gpt-oss-20b:free was withdrawn from the catalogue (404) while
# openai/gpt-oss-20b remains, and gemma's :free tier 429s on quota while the paid tier does
# not. The same OPENROUTER_API_KEY carries purchased credit (harness.toml
# [providers.deepseek_paid], kind = openrouter_paid). Rates read from the catalogue
# 2026-08-30, USD per 1M tokens.
PAID_OR_RATES = {
    "openai/gpt-oss-20b": {"in": 0.03, "out": 0.13},
    "google/gemma-4-26b-a4b-it": {"in": 0.07, "out": 0.34},
    "poolside/laguna-xs-2.1": {"in": 0.06, "out": 0.12},
    "nvidia/nemotron-3-super-120b-a12b": {"in": 0.08, "out": 0.40},
    "qwen/qwen3.8-27b": {"in": 0.42, "out": 2.55},
}


HARNESS_TOML = Path.home() / "dev/solon-harness/harness.toml"


def paid_binding() -> dict | None:
    """Resolve the harness's openrouter_paid provider binding.

    The amended request says to use the harness binding, and claiming equivalence from a
    matching endpoint and key NAME is not the same as resolving it: if the binding moves,
    an assertion of equivalence keeps passing while the probe talks to the old endpoint.
    """
    try:
        import tomllib
        cfg = tomllib.loads(HARNESS_TOML.read_text())
    except Exception:                              # noqa: BLE001
        return None
    for name, prov in (cfg.get("providers") or {}).items():
        if prov.get("kind") == "openrouter_paid" and prov.get("enabled"):
            url = str(prov.get("base_url", ""))
            return {"provider": name, "kind": prov["kind"],
                    "base": url.rsplit("/chat/completions", 1)[0],
                    "key_env": (prov.get("key_envs") or ["OPENROUTER_API_KEY"])[0],
                    "source": str(HARNESS_TOML)}
    return None


# Interim stand-ins for a pinned endpoint that is temporarily unreliable. Added
# 2026-08-30 on the owner's instruction: the local :8083 server is being worked on and
# flaps between answering and refusing, so the qwen FAMILY is probed via OpenRouter while
# that settles. A stand-in establishes the family is reachable; it is NOT the registered
# model and never counts toward the pinned total.
#
# NOTE the difference it does not erase: the registered local model is Qwen3.8-27B-Q4_K_M
# (4-bit quantised GGUF); the OpenRouter id serves the same family and nominal size at the
# provider's own precision. Same family, not the same weights.
INTERIM_STANDINS = {
    "qwen": {"model": "qwen/qwen3.8-27b", "backend": "openrouter",
             "reason": "local :8083 endpoint intermittent while being worked on "
                       "(owner, 2026-08-30)",
             "differs": "registered local weights are Q4_K_M quantised; the hosted id is "
                        "the provider's own build of the same family and nominal size"},
}
PAID_OR_RATES_EXTRA = {"qwen/qwen3.8-27b": {"in": 0.42, "out": 2.55}}


def interim_standins(cands: list[dict]) -> list[dict]:
    """Family stand-ins for pinned endpoints that are temporarily unreliable."""
    out = []
    for c in cands:
        s = INTERIM_STANDINS.get(c["agent"])
        if not s:
            continue
        b = paid_binding()
        out.append(dict(c, model=s["model"], backend=s["backend"], base=(b or {}).get("base"),
                        tier="interim", agent=f"{c['agent']}_or",
                        stands_in_for=c["model"], standin_reason=s["reason"],
                        standin_differs=s["differs"], expected_resolved=None,
                        identity_evidence=None, binding=b))
    return out


def paid_variants(cands: list[dict]) -> list[dict]:
    """Paid-tier twins of any pinned `:free` candidate.

    These are a DIFFERENT model id, so under prereg_v2's resolution rule they are not the
    registered model. They are probed to establish whether the FAMILY is reachable at all,
    which is what cycle 3 needs: cycle 3 pins its own panels and may pin the paid id
    directly. Recorded with tier="paid" so the two are never conflated.
    """
    out = []
    for c in cands:
        if c["backend"] != "openrouter" or not c["model"].endswith(":free"):
            continue
        paid = c["model"][: -len(":free")]
        if paid not in PAID_OR_RATES:
            continue
        b = paid_binding()
        if b is None:
            # silence here would let the probe quietly use the ordinary client while the
            # request says the harness binding is to be used
            print("WARNING: no enabled openrouter_paid provider in harness.toml; paid twins "
                  "will fall back to nodes.Client(openrouter) and the artifact will say so")
        out.append(dict(c, model=paid, tier="paid", agent=f"{c['agent']}_paid",
                        pinned_free_id=c["model"],
                        base=(b or {}).get("base") or c.get("base"),
                        binding=b))
    return out

_SECRET = re.compile(
    r"(?i)("
    r"(?:bearer|basic|token)\s+[A-Za-z0-9._\-+/=]{6,}"       # scheme + credential
    r"|authorization\s*[:=]\s*(?:\w+\s+)?\S+"                 # header, with optional scheme
    r"|x-[a-z-]*(?:api)?-?key\s*[:=]\s*\S+"                  # X-Api-Key: ...
    r"|sk-[A-Za-z0-9_\-]{8,}"
    r"|(?:api[-_]?key|token|secret|password)\"?\s*[\"':=]+\s*[\"']?[^\"',}\s]{4,}"
    r"|[?&](?:key|api_key|access_token|token)=[^&\s\"]+"
    r"|\"(?:user_id|account_id|org_id)\"\s*:\s*\"[^\"]*\""
    r"|\"id\"\s*:\s*\"gen-[^\"]*\""
    r")")
# provider request metadata is diagnostic noise that can carry account identifiers; the
# STATUS and the human-readable message are what a reader needs
_METADATA = re.compile(r'(?i),?\s*"metadata"\s*:\s*\{.*?\}\s*', re.S)


def sanitise(text: str, limit: int = 400) -> str:
    """Reduce a provider error to a status and a message. ALLOWLIST, not blocklist.

    Regex-stripping the `metadata` object was unsound: a non-greedy brace match stops at
    the FIRST nested closing brace, so `metadata:{raw:{...},billing_email:...}` left the
    billing address and account id in a tracked artifact. Enumerating what to remove loses
    to whatever the provider adds next, so this keeps only the two fields a reader needs
    and discards the rest of the structure.
    """
    if not text:
        return ""
    s = str(text)
    prefix = ""
    m = re.match(r"^(HTTP \d{3}: )(.*)$", s, re.S)
    if m:
        prefix, s = m.group(1), m.group(2)
    try:
        payload = json.loads(s)
    except Exception:                              # noqa: BLE001 — not JSON: redact and clip
        return _SECRET.sub("[REDACTED]", prefix + s)[:limit]
    err = payload.get("error") if isinstance(payload, dict) else payload
    if isinstance(err, str):
        # some providers put the whole message in `error` as a string; keep it as the
        # message so the reason survives, and let the redactor handle its contents
        return _SECRET.sub("[REDACTED]",
                           prefix + json.dumps({"message": err}, sort_keys=True))[:limit]
    if not isinstance(err, dict):
        err = payload if isinstance(payload, dict) else {}
    kept = {k: err.get(k) for k in ("code", "message", "type") if err.get(k) is not None}
    if not kept:
        kept = {"message": "provider error (no message field)"}
    return _SECRET.sub("[REDACTED]", prefix + json.dumps(kept, sort_keys=True))[:limit]


def candidates(root: Path) -> list[dict]:
    """Read the pinned six FROM the registration, so plan and registration cannot drift."""
    spec = yaml.safe_load((root / REGISTRATION).read_text())
    out = []
    for panel, pdef in (spec.get("panels") or {}).items():
        for agent, a in (pdef.get("cross_family") or {}).items():
            out.append({
                "panel": panel, "agent": agent,
                "family": FAMILY.get(agent, f"UNMAPPED:{agent}"),
                "backend": a["backend"], "model": a["model"],
                "base": a.get("base"), "expected_resolved": a.get("expected_resolved"),
                "identity_evidence": a.get("identity_evidence"),
            })
    return out


def registered_weights(c: dict) -> str | None:
    """The GGUF path prereg_v2 pins for this candidate, parsed from identity_evidence.

    The registration pins qwen by model_path AND n_params precisely because the server
    answers under a stale alias. Recording /props without comparing it left the alias echo
    as the only check -- which is what identity_evidence exists to backstop.
    """
    ev = c.get("identity_evidence") or ""
    m = re.search(r"model_path\s+(\S+\.gguf)", ev)
    return m.group(1) if m else None


def _local_weights(client) -> str | None:
    """The llama-server /props model_path, so a local swap is visible.

    prereg_v2 pins qwen's identity by GGUF path and parameter count precisely because the
    server answers under a stale launch alias; an echoed id alone cannot distinguish the
    registered weights from a different model loaded behind the same alias.
    """
    import httpx
    try:
        base = str(client.base).rsplit("/v1", 1)[0]
        r = httpx.get(f"{base}/props", timeout=10)
        if r.status_code != 200:
            return None
        j = r.json()
        return (j.get("model_path") or (j.get("default_generation_settings") or {})
                .get("model") or None)
    except Exception:                              # noqa: BLE001 — diagnostic only
        return None


def _identity(c: dict, echoed: str | None, weights: str | None = None) -> dict:
    """Expected identity DEFAULTS to the id we asked for.

    Treating a null `expected_resolved` as "nothing to check" made every remote `ok`
    unverifiable: an upstream route to different weights would have passed silently. The
    registration's `expected_resolved` is an ALIAS OVERRIDE for the one endpoint that
    legitimately answers under another name (qwen on :8083 as `ornith35`), not a licence to
    skip the comparison everywhere else.
    """
    expected = c.get("expected_resolved") or c["model"]
    rec = {"requested": c["model"], "echoed": echoed, "expected": expected,
           "expected_source": ("registered alias override" if c.get("expected_resolved")
                               else "requested id (default)"),
           "echo_present": echoed is not None,
           "checkable": True,
           "matches_expected": (echoed == expected) if echoed is not None else None}
    rec["loaded_weights"] = weights          # None means /props could not be read
    if c["backend"] == "local":
        want = registered_weights(c)
        rec["registered_weights"] = want
        if want and weights:
            rec["weights_match"] = (weights == want)
            if not rec["weights_match"]:
                rec["matches_expected"] = False
                rec["note"] = (f"loaded weights {weights!r} are not the registered "
                               f"{want!r}: the alias echo alone cannot detect this")
        # prereg_v2 pins qwen by GGUF path and parameter count precisely because the server
        # answers under a stale alias: an echo alone cannot tell the registered weights from
        # a different model loaded behind the same name. Unreadable weights => unverified.
        rec["weights_readable"] = weights is not None
        if weights is None:
            rec["matches_expected"] = False
            rec["note"] = ("local endpoint: /props could not be read, so the loaded weights "
                           "could not be checked against the registration")
    return rec


def _probe_one(c: dict, probe_item, timeout: float) -> dict:
    """ONE live HTTP call. No cache, no retry.

    `nodes.Client.generate` is unusable for an availability probe on two counts, both
    measured 2026-08-30:

      1. It consults the generation cache first, and the cache key covers (item, backend,
         model, role, prompt, seed, temperature, max_tokens) but NOT the agent. The frozen
         exp/smoke_v2 probe uses the same item and the same parameters, so a probe would be
         served from a cache entry written in August and report a model as available today
         without contacting anything. Two paid probes in this slice did exactly that
         (0.03s and 0.00s latencies).
      2. `Client._call` retries a model failure twice and waits out up to six 429s, which
         contradicts the one-attempt-per-endpoint limit the request sets and multiplies
         paid calls.

    So the probe issues the request itself, through the client only for base/key/header
    resolution. Availability is a property of the endpoint NOW, not of a cached artifact.
    """
    import httpx
    from wct import nodes
    rec = dict(c)
    t0 = time.time()
    try:
        client = nodes.Client(c["backend"], timeout=timeout, base_url=c.get("base"))
        prompt = nodes.build_prompt(probe_item, "neutral")
        body = {"model": c["model"], "temperature": 0.7, "seed": 1, "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]}
        import os as _os
        b = c.get("binding")
        key = _os.environ.get(b["key_env"]) if b else getattr(client, "key", None)
        base = (b or {}).get("base") or client.base
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        rec["binding_used"] = (b or {}).get("provider", f"nodes.Client({c['backend']})")
        with httpx.Client(timeout=timeout) as h:      # exactly one attempt
            r = h.post(f"{base}/chat/completions", json=body, headers=headers)
        rec["latency_s"] = round(time.time() - t0, 2)
        rec["http_status"] = r.status_code
        rec["live_call"] = True
        if r.status_code != 200:
            rec.update(status="fail", resolved=None, usage={}, content_chars=0,
                       error=sanitise(f"HTTP {r.status_code}: {r.text}"))
            rec["identity"] = _identity(
                c, None, _local_weights(client) if c["backend"] == "local" else None)
            return rec
        j = r.json()
        ch = (j.get("choices") or [{}])[0].get("message", {}) or {}
        content = (ch.get("content") or "") + (ch.get("reasoning") or "")
        rec["resolved"] = j.get("model")
        rec["usage"] = j.get("usage") or {}
        rec["content_chars"] = len(content)
        weights = _local_weights(client) if c["backend"] == "local" else None
        rec["identity"] = _identity(c, rec["resolved"], weights)
        if not content.strip():
            # identity is recorded BEFORE this return: an empty-200 is a valid recorded
            # failure, and the gate must be able to report it rather than reject the artifact
            rec.update(status="fail",
                       error="empty completion (no content, no reasoning)")
            return rec
        # status follows the identity comparison, which is ALWAYS made: expected defaults to
        # the requested id, with the registration's expected_resolved as an alias override.
        # An earlier version gated this on expected_resolved being set, so nine of ten
        # candidates could answer under any id and still be recorded `ok`.
        ident = rec["identity"]
        if ident["echoed"] is None:
            # answered, but echoed no model id: identity cannot be verified, so this must
            # not count toward a margin used to register an experiment
            rec.update(status="substituted", error="",
                       note=f"answered with content but echoed NO model id; expected "
                            f"{ident['expected']!r} ({ident['expected_source']}). Identity "
                            f"is unverifiable, so this is not counted as the registered "
                            f"model answering.")
        elif not ident["matches_expected"]:
            rec.update(status="substituted", error="",
                       note=f"answered as {ident['echoed']!r}, expected "
                            f"{ident['expected']!r} ({ident['expected_source']})")
        else:
            rec.update(status="ok", error="")
        rec["identity_verified"] = bool(ident["matches_expected"])
        return rec
    except Exception as e:                       # noqa: BLE001 — a probe reports, never raises
        rec["latency_s"] = round(time.time() - t0, 2)
        rec.update(status="fail", error=sanitise(f"{type(e).__name__}: {e}"),
                   content_chars=0, resolved=None, usage={}, live_call=True)
        # identity on EVERY return path: a transport failure still has a requested id and an
        # expected one, and "no echo observed" is the finding. An earlier edit stripped this,
        # leaving a connection-refused record with an empty identity that the gate rejects.
        rec["identity"] = _identity(c, None)
        return rec


def live_or_rates(models: set[str]) -> dict:
    """Fetch OpenRouter pricing now. A hard-coded rate from a dated catalogue reading can
    silently misstate spend once the provider changes it."""
    import os
    import httpx
    try:
        r = httpx.get("https://openrouter.ai/api/v1/models",
                      headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
                      timeout=30)
        r.raise_for_status()
        out = {}
        for m in r.json()["data"]:
            if m["id"] in models:
                p = m.get("pricing") or {}
                out[m["id"]] = {"in": float(p.get("prompt", 0)) * 1e6,
                                "out": float(p.get("completion", 0)) * 1e6}
        return out
    except Exception:                              # noqa: BLE001 — fall back, and say so
        return {}


def spend(records: list[dict], live_rates: dict | None = None) -> dict:
    """Calculated, not merely counted: tokens x pinned rates, with an upper bound where
    the provider reported no usage."""
    total, bounded = 0.0, False
    calls = 0
    for r in records:
        or_paid = r.get("tier") in ("paid", "interim") and r.get("model") in PAID_OR_RATES
        if r.get("backend") not in PAID_BACKENDS and not or_paid:
            continue
        calls += 1
        rates = {**PAID_OR_RATES, **(live_rates or {})}
        rate = rates[r["model"]] if or_paid else PAID_RATES[r["backend"]]
        u = r.get("usage") or {}
        # OpenRouter reports the actual charge; a rate calculation is a reconstruction and
        # can drift from what the account is billed
        if u.get("cost") is not None:
            total += float(u["cost"])
            continue
        pi, po = u.get("prompt_tokens"), u.get("completion_tokens")
        if pi is None or po is None:
            bounded = True
            pi, po = 1000, 2000          # conservative: prompt is tiny, max_tokens=2000
        total += pi / 1e6 * rate["in"] + po / 1e6 * rate["out"]
    per = [{"agent": r.get("agent"), "model": r.get("model"),
            "backend": r.get("backend"), "tier": r.get("tier", "pinned"),
            "usage": r.get("usage") or {}}
           for r in records
           if r.get("backend") in PAID_BACKENDS
           or (r.get("tier") == "paid" and r.get("model") in PAID_OR_RATES)]
    return {"paid_backends": sorted(PAID_BACKENDS), "paid_calls": calls,
            "usd": round(total, 6), "is_upper_bound": bounded,
            "per_call": per,                      # per-candidate, not just an aggregate
            "rates_usd_per_1m": {"hoonify": PAID_RATES["hoonify"], **PAID_OR_RATES},
            "rates_are_live": bool(live_rates),
            "cost_basis": ("provider-reported usage.cost where present, else tokens x rates"),
            "rates_provenance": {
                "hoonify": "prereg_v2.yaml panelA.cost_note",
                "openrouter_paid": "read LIVE from the openrouter /api/v1/models catalogue "
                                   "at probe time where available, else the fallback pinned "
                                   "in this module. NOT in prereg_v2.yaml, because cycle 2 "
                                   "registered only the :free ids. Slice 4 must pin them."},
            "binding": (paid_binding() or {"resolved": False,
                        "note": "harness.toml carries no enabled openrouter_paid provider; "
                                "paid twins fell back to the nodes.Client openrouter path"})}


def merge_reprobe(prior: dict, fresh: dict, only: set[str]) -> dict:
    """A re-probe SUPERSEDES without erasing.

    The plan makes a re-probe a deliberate second invocation, and the prior attempt is
    evidence: a 429 that later succeeds is a different fact from a model that always
    answered. Each superseded record is kept under `superseded_by_reprobe` with its own
    timestamp, so the history is auditable rather than overwritten.
    """
    out = dict(prior)
    by_agent = {c["agent"]: c for c in fresh["candidates"]}
    merged = []
    for c in prior["candidates"]:
        if c["agent"] in only and c["agent"] in by_agent:
            new = dict(by_agent[c["agent"]])
            hist = list(c.get("superseded_by_reprobe") or [])
            hist.append({k: c.get(k) for k in
                         ("status", "error", "latency_s", "measured_at", "usage")}
                        | {"measured_at": c.get("measured_at", prior["measured_at"])})
            new["superseded_by_reprobe"] = hist
            new["measured_at"] = fresh["measured_at"]
            merged.append(new)
        else:
            merged.append(c)
    # candidates the prior artifact does NOT contain must be APPENDED, not dropped. The
    # first version of this merge silently discarded them: two paid probes ran, their
    # results were thrown away, and the artifact still recorded the re-probe as having
    # happened -- a spend with no evidence and an internally inconsistent file.
    known = {c["agent"] for c in prior["candidates"]}
    for agent, rec in by_agent.items():
        if agent not in known:
            merged.append(rec)
    missing = only - {c["agent"] for c in merged}
    if missing:
        raise RuntimeError(
            f"re-probe targeted {sorted(only)} but {sorted(missing)} are absent from the "
            f"merged artifact; refusing to write a file that claims a probe it does not "
            f"contain")
    out["candidates"] = merged
    # superseded PAID attempts were really billed; recomputing spend from current records
    # alone under-reports what the account was charged
    superseded_paid = []
    for c in merged:
        for h in c.get("superseded_by_reprobe") or []:
            if h.get("usage") or h.get("was_paid"):
                superseded_paid.append({"agent": c["agent"], "model": c.get("model"),
                                        "backend": c.get("backend"), "tier": c.get("tier"),
                                        "usage": h.get("usage") or {}})
    out["reprobes"] = (prior.get("reprobes") or []) + [
        {"at": fresh["measured_at"], "agents": sorted(only),
         "reason": "deliberate second invocation (human decision)"}]
    out["measured_at"] = fresh["measured_at"]
    cur = spend(merged)
    prev = spend(superseded_paid) if superseded_paid else None
    if prev and prev["paid_calls"]:
        cur = dict(cur,
                   usd=round(cur["usd"] + prev["usd"], 6),
                   paid_calls=cur["paid_calls"] + prev["paid_calls"],
                   is_upper_bound=cur["is_upper_bound"] or prev["is_upper_bound"],
                   superseded_paid_attempts=prev)
    out["spend"] = cur
    return out


def run(root: Path, timeout: float = 180.0, only: set[str] | None = None,
        include_paid: bool = False) -> dict:
    from exp.envfile import load_harness_env
    from exp.smoke_v2 import _PROBE          # the frozen throwaway theory, imported
    allc = candidates(root)
    if include_paid:
        allc = allc + paid_variants(allc) + interim_standins(allc)
    cands = [c for c in allc if not only or c["agent"] in only]
    if not cands:
        raise SystemExit(f"no candidate matches {sorted(only or [])}")
    if any(c["backend"] != "local" for c in cands):
        load_harness_env()

    # local FIRST and strictly sequentially: the server holds one model slot
    ordered = [c for c in cands if c["backend"] == "local"] + \
              [c for c in cands if c["backend"] != "local"]
    records = []
    for c in ordered:
        records.append(_probe_one(c, _PROBE, timeout))

    reg = (root / REGISTRATION).read_bytes()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                                capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        commit = "unknown"
    try:
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                    capture_output=True, text=True,
                                    check=True).stdout.strip())
    except subprocess.CalledProcessError:
        dirty = True
    return {
        "schema_version": SCHEMA_VERSION,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": (f"UNCOMMITTED (parent {commit})" if dirty else commit),
        "source_commit_parent": commit,
        "source_tree_dirty": dirty,
        "probe_source_sha256": hashlib.sha256(
            Path(__file__).read_bytes()).hexdigest()[:16],
        "source_commit_note": (
            "the probe code was UNCOMMITTED when this ran, so this commit does not contain "
            "the implementation that produced the artifact" if dirty else
            "the working tree was clean; this commit contains the implementation"),
        "registration": REGISTRATION,
        "registration_sha256": hashlib.sha256(reg).hexdigest(),
        "probe": {"attempts_per_endpoint": 1, "retries": 0, "timeout_s": timeout,
                  "auxiliary_requests": [
                      {"what": "GET /api/v1/models", "why": "read paid rates live so a "
                       "stale hard-coded rate cannot misstate spend", "billable": False,
                       "count": 1},
                      {"what": "GET <local>/props", "why": "read the loaded GGUF path so it "
                       "can be compared with the weights prereg_v2 pins; the alias echo "
                       "alone cannot detect a different model behind the same name",
                       "billable": False, "scope": "local candidates only"}],
                  "item": "exp.smoke_v2._PROBE (throwaway theory; no corpus content)"},
        "candidates": records,
        "spend": spend(records, live_or_rates(
            {r["model"] for r in records if r.get("tier") == "paid"})),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true",
                    help="required: this SPENDS (a paid endpoint) and calls external services")
    ap.add_argument("--root", default=".")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--include-paid", action="store_true",
                    help="also probe paid-tier twins of the pinned :free ids")
    ap.add_argument("--only", default="",
                    help="comma-separated agent ids: probe ONLY these and merge the result "
                         "into the existing artifact, keeping the superseded attempt")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if not args.confirm:
        print(__doc__)
        print("refusing to run without --confirm (one paid call per paid endpoint)")
        return 2
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    res = run(root, timeout=args.timeout, only=only or None,
              include_paid=args.include_paid)
    out = root / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    if only and out.exists():
        res = merge_reprobe(json.loads(out.read_text()), res, only)
    out.write_text(json.dumps(res, indent=2, sort_keys=True))
    for r in res["candidates"]:
        print(f"  {r['status']:12s} {r['family']:9s} {r['agent']:9s} [{r['backend']}] "
              f"{r['model']}" + (f"  -> {r.get('note','')}" if r.get("note") else ""))
    s = res["spend"]
    print(f"paid calls: {s['paid_calls']}  USD {s['usd']}"
          f"{' (upper bound)' if s['is_upper_bound'] else ''}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
