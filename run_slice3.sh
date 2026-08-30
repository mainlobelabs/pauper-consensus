#!/usr/bin/env bash
# Slice 3 gate. Default mode NEVER calls an endpoint; --probe performs the measurement once.
#   ./run_slice3.sh            validate the existing artifact (free, repeatable)
#   ./run_slice3.sh --probe    probe, then validate  (SPENDS on paid tiers)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; TAG="prereg-v2-2026-08-16"; EV="e63f946"
export PYTHONPATH="$ROOT"
# the suite contains tests that INVOKE this gate; without this marker the
# gate -> pytest -> gate cycle never terminates
export SLICE3_GATE_RUNNING=1
PROBE=0; [ "${1:-}" = "--probe" ] && PROBE=1
step() { printf '\n=== %s ===\n' "$1"; }

step "1/7 toolchain pin"
"$PY" -c "import sys; assert sys.version_info[:2]==(3,12), sys.version; print('python', sys.version.split()[0], 'OK')"
grep -qi uv "$ROOT/.venv/pyvenv.cfg" || { echo "FAIL: .venv is not uv-created"; exit 1; }

step "2/7 frozen surface byte-clean under $TAG"
git diff --quiet "$TAG" HEAD -- exp/ wct/ m0/ || { echo "FAIL: committed diff"; exit 1; }
git diff --quiet "$TAG" -- exp/ wct/ m0/ || { echo "FAIL: working-tree diff"; exit 1; }
test -z "$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)" \
  || { echo "FAIL: untracked paths under the frozen surface"; exit 1; }
echo "clean"

step "3/7 prior evidence immutable against $EV"
PINNED="$(git ls-tree -r --name-only "$EV" out/v3 | sort -u)"
NOW="$(git ls-files --cached --others --exclude-standard out/v3 | sort -u)"
test "$NOW" = "$PINNED" || { echo "FAIL: out/v3 contents differ from $EV"; exit 1; }
for f in $PINNED out/e1_summary.json out/e1_summary_openrouter.json \
         out/e1_v2_summary_panelA.json out/e1_v2_summary_panelB.json; do
  git show "$EV:$f" | diff -q - "$f" >/dev/null || { echo "FAIL: $f differs from $EV"; exit 1; }
done
echo "prior evidence identical to $EV"

step "4/7 measurement"
if [ "$PROBE" = "1" ]; then
  echo "probing (this SPENDS on paid tiers)"
  "$PY" -m exp3.availability --confirm --include-paid
else
  echo "validate-only: no endpoint is called (re-probe with --probe)"
fi
"$PY" -m exp3.slice3_verdict

step "5/7 artifact validation"
"$PY" - <<'EOF'
import hashlib, json, re, sys
from pathlib import Path
from exp3.availability import (REGISTRATION, SCHEMA_VERSION, candidates,
                               candidates as _c, paid_variants, interim_standins)
art = json.loads(Path("out/slice3/availability.json").read_text())
fails = []
if art.get("schema_version") != SCHEMA_VERSION:
    fails.append(f"schema_version {art.get('schema_version')} != {SCHEMA_VERSION}")
for k in ("measured_at", "source_commit", "registration_sha256", "probe", "spend"):
    if k not in art:
        fails.append(f"missing provenance field: {k}")
# freshness: the artifact must describe the CURRENT registration, not an older one
cur = hashlib.sha256(Path(REGISTRATION).read_bytes()).hexdigest()
if art.get("registration_sha256") != cur:
    fails.append(f"artifact measured against a DIFFERENT {REGISTRATION}")
pinned = {c["agent"] for c in candidates(Path("."))}
got = {c["agent"] for c in art["candidates"]}
if not pinned <= got:
    fails.append(f"pinned candidates missing from artifact: {sorted(pinned - got)}")
# the verdict counts paid twins, so an artifact without them would silently change the
# family margin while still passing a pinned-only coverage check
twins = {v["agent"] for v in paid_variants(_c(Path(".")))}
if not twins <= got:
    fails.append(f"paid twins missing from artifact: {sorted(twins - got)}; the verdict "
                 f"counts them, so their absence changes the margin")
# extras are allowed ONLY as declared paid twins of a pinned :free id, never arbitrary
allowed = (pinned | {v["agent"] for v in paid_variants(_c(Path(".")))}
           | {v["agent"] for v in interim_standins(_c(Path(".")))})
if got - allowed:
    fails.append(f"artifact carries undeclared candidates: {sorted(got - allowed)}")
# name membership is not enough: a record could claim a different family, backend or model
# and still pass, which would misattribute a family in the margin the registration rests on
expect = {c["agent"]: c for c in _c(Path("."))}
expect.update({v["agent"]: v for v in paid_variants(_c(Path(".")))})
expect.update({v["agent"]: v for v in interim_standins(_c(Path(".")))})
for c in art["candidates"]:
    e = expect.get(c["agent"])
    if not e:
        continue
    for field in ("panel", "family", "backend", "model"):
        if c.get(field) != e.get(field):
            fails.append(f"{c['agent']}: {field} is {c.get(field)!r}, registration/derivation "
                         f"gives {e.get(field)!r}")
    if e.get("tier") == "paid":
        if c.get("tier") != "paid":
            fails.append(f"{c['agent']}: paid twin not marked tier=paid")
        if c.get("pinned_free_id") != e.get("pinned_free_id"):
            fails.append(f"{c['agent']}: pinned_free_id mismatch")
    if e.get("tier") in ("paid", "interim") and not str(c.get("binding_used", "")).startswith("deepseek_paid"):
        fails.append(f"{c['agent']}: paid twin used {c.get('binding_used')!r}, not the "
                     f"harness openrouter_paid binding the request requires")
    ident = c.get("identity") or {}
    if ident.get("requested") != e.get("model"):
        fails.append(f"{c['agent']}: identity.requested {ident.get('requested')!r} != "
                     f"{e.get('model')!r}")
for c in art["candidates"]:
    if c.get("status") not in ("ok", "substituted", "fail"):
        fails.append(f"{c['agent']}: bad status {c.get('status')!r}")
    ident = c.get("identity")
    if not isinstance(ident, dict) or "requested" not in ident or "echoed" not in ident:
        fails.append(f"{c['agent']}: no identity record")
    elif c.get("status") == "ok" and ident.get("checkable") and not ident.get("matches_expected"):
        fails.append(f"{c['agent']}: ok but the echoed id does not match the expected one")
    if c.get("status") == "ok" and not c.get("content_chars"):
        fails.append(f"{c['agent']}: ok with no content — catalogue-shaped success")
# one attempt per endpoint per invocation, and every record must be a LIVE call:
# nodes.Client.generate consults the generation cache and its key omits the agent, so a
# probe could otherwise be served from an August smoke-test entry and report a model as
# available today (measured 2026-08-30: two probes returned at 0.03s and 0.00s).
if art["probe"].get("retries") != 0 or art["probe"].get("attempts_per_endpoint") != 1:
    fails.append("probe config records retries; the request permits one attempt")
for c in art["candidates"]:
    if not c.get("live_call"):
        fails.append(f"{c['agent']}: not recorded as a live call — possibly cache-served")
    if c.get("status") != "fail" and c.get("http_status") != 200:
        fails.append(f"{c['agent']}: status {c.get('status')} with HTTP {c.get('http_status')}")
# per-candidate paid accounting, not just the aggregate
# an interim stand-in is billed like any other paid OpenRouter call; counting only
# tier=="paid" made the coverage check disagree with the spend accounting
paid = [c for c in art["candidates"]
        if c.get("backend") == "hoonify" or c.get("tier") in ("paid", "interim")]
sup = (art["spend"].get("superseded_paid_attempts") or {}).get("paid_calls", 0)
if art["spend"]["paid_calls"] != len(paid) + sup:
    fails.append(f"spend records {art['spend']['paid_calls']} paid calls but "
                 f"{len(paid)} current paid candidates + {sup} superseded attempts")
# duplicates would satisfy the count while doubling the real spend
agents = [c["agent"] for c in art["candidates"]]
if len(agents) != len(set(agents)):
    dupes = sorted({a for a in agents if agents.count(a) > 1})
    fails.append(f"duplicate candidate records: {dupes}")
if any(art["spend"].get("per_call") is None for _ in [0]):
    fails.append("spend has no per-call breakdown; an aggregate alone cannot be audited")
# freshness must be REPORTED, not merely digested
from datetime import datetime, timezone
age_h = (datetime.now(timezone.utc)
         - datetime.strptime(art["measured_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
             tzinfo=timezone.utc)).total_seconds() / 3600
print(f"artifact age: {age_h:.1f}h (measured {art['measured_at']})")
if age_h > 24 * 14:
    fails.append(f"artifact is {age_h/24:.0f} days old; availability is a perishable fact")
# no corpus content, no credential-shaped strings
blob = json.dumps(art)
# reuse the sanitiser's own pattern: a gate that scans for fewer forms than the redactor
# recognises will pass an artifact the redactor was meant to have cleaned
from exp3.availability import _SECRET
if re.search(r"ProofWriter|proofwriter", blob):
    fails.append("artifact contains a corpus name")
hit = _SECRET.search(blob)
if hit:
    fails.append(f"artifact contains a credential-shaped string: {hit.group(0)[:24]!r}")
uncheckable = [c["agent"] for c in art["candidates"]
               if not (c.get("identity") or {}).get("checkable")]
if uncheckable:
    print(f"NOTE: substitution is UNDETECTABLE for {len(uncheckable)}/{len(art['candidates'])} "
          f"candidates ({', '.join(uncheckable)}): the registration pins no expected echo for "
          f"them, so an `ok` means 'something answered', not 'the registered model answered'.")
print("\n".join(f"FAIL: {f}" for f in fails) or
      f"artifact OK: {len(art['candidates'])} candidates, provenance and identity present, "
      f"spend USD {art['spend']['usd']}")
sys.exit(1 if fails else 0)
EOF

step "6/7 test suite"
"$PY" -m pytest -q tests/

step "7/7 DECISIONS.md entry"
"$PY" -m exp3.slice3_decide
"$PY" -m exp3.slice3_decide --check

printf '\n=== SLICE 3 GATE PASSED ===\n'
