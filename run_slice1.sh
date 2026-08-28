#!/usr/bin/env bash
# Slice 1 gate: one command, fails closed on the first error.
#
#   1. toolchain pin           2. tag-clean assertion (tracked AND untracked)
#   3. full pytest suite       4. cache manifest BEFORE
#   5. four-panel re-analysis  6. cache manifest AFTER (proves zero inference)
#   7. artifact validation     8. DECISIONS.md entry
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
TAG="prereg-v2-2026-08-16"
export PYTHONPATH="$ROOT"
export WCT_CACHE="${WCT_CACHE:-$ROOT/out/cache}"
# unroutable: a cache miss that slips past wct3.strict still cannot generate
export WCT_LOCAL_BASE="http://127.0.0.1:9"

step() { printf '\n=== %s ===\n' "$1"; }

step "1/8 toolchain pin"
"$PY" - <<'EOF'
import sys
assert sys.version_info[:2] == (3, 12), f"expected Python 3.12, got {sys.version}"
print("python", sys.version.split()[0], "OK")
EOF
test -f "$ROOT/.venv/pyvenv.cfg" || { echo "FAIL: no venv at .venv"; exit 1; }
# the uv pin is an assertion, not a note: a venv built by some other tool may
# resolve different wheels, and the frozen-value reproduction depends on them
grep -qi "uv" "$ROOT/.venv/pyvenv.cfg" \
  || { echo "FAIL: .venv is not uv-created (no uv marker in pyvenv.cfg)"; exit 1; }
echo "uv-created venv OK"

step "2/8 frozen surface is byte-clean under $TAG"
git diff --quiet "$TAG" HEAD -- exp/ wct/ m0/ \
  || { echo "FAIL: committed diff against $TAG under exp/ wct/ m0/"; exit 1; }
git diff --quiet "$TAG" -- exp/ wct/ m0/ \
  || { echo "FAIL: working-tree diff against $TAG under exp/ wct/ m0/"; exit 1; }
UNTRACKED="$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)"
test -z "$UNTRACKED" \
  || { echo "FAIL: untracked paths under the frozen surface:"; echo "$UNTRACKED"; exit 1; }
echo "clean: no tracked change, no untracked addition"

# The manifest is taken BEFORE the tests, not between them and the analysis: most
# real-cache tests do not install wct3.strict, so an NLI miss inside the suite
# could compute and write cache data that a later baseline would then treat as
# pre-existing. Snapshotting first makes the whole gate the measured window.
step "3/8 cache manifest BEFORE (covers tests AND analysis)"
# path + size + mtime + CONTENT hash: size alone cannot see an in-place rewrite
# of a same-length payload, and the cache is supposed to be immutable.
manifest() {
  find out/cache/embed out/cache/nli -type f -printf '%p %s %T@\n' 2>/dev/null | sort | sha256sum
  find out/cache/embed out/cache/nli -type f -print0 2>/dev/null | sort -z \
    | xargs -0 -r sha256sum | sha256sum
}
BEFORE="$(manifest)"
echo "$BEFORE"

step "4/8 full test suite (frozen tests/test_wct.py + every tests/test_wct3_*.py)"
"$PY" -m pytest -q tests/

step "5/8 four-panel re-analysis (cache-only)"
"$PY" -m exp3.reanalyse --panel all --out-dir out/v3

step "6/8 cache manifest AFTER — proves zero inference"
AFTER="$(manifest)"
echo "$AFTER"
test "$BEFORE" = "$AFTER" \
  || { echo "FAIL: the embed/NLI cache CHANGED — new inference ran"; exit 1; }
echo "unchanged: no embedding or NLI was computed"

step "7/8 artifact validation"
"$PY" -m exp3.validate --out-dir out/v3

step "8/8 DECISIONS.md entry"
"$PY" -m exp3.decide --out-dir out/v3
"$PY" -m exp3.decide --check

printf '\n=== SLICE 1 GATE PASSED ===\n'
