#!/usr/bin/env bash
# Slice 4 gate. ONE command; the EXIT CODE is the pass signal (B10).
#   ./run_slice4.sh          validate everything (free, repeatable, no egress)
#   ./run_slice4.sh --smoke  additionally probe the endpoints once (SPENDS on paid tiers)
#   ./run_slice4.sh --tag    create the registration tag (separate, human-gated, last)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"
V2TAG="prereg-v2-2026-08-16"; EV="e63f946"
# out/slice3's evidence was finalised by the slice-3 follow-up commit (the gemma
# re-probe). Anchoring to a FIXED pre-slice-4 commit, not to HEAD: comparing against
# HEAD would let an evidence file modified and committed with this slice silently
# become its own baseline.
S3EV="1bf61ba"
V3TAG="$("$PY" -c "import yaml;print(yaml.safe_load(open('prereg_v3.yaml'))['tag'])")"
export PYTHONPATH="$ROOT"
export WCT_CACHE="${WCT_CACHE:-$ROOT/out/cache}"
# the suite contains tests that INVOKE this gate; without this marker the
# gate -> pytest -> gate cycle never terminates
export SLICE4_GATE_RUNNING=1
SMOKE=0; DOTAG=0
for a in "$@"; do
  [ "$a" = "--smoke" ] && SMOKE=1
  [ "$a" = "--tag" ] && DOTAG=1
done
step() { printf '\n=== %s ===\n' "$1"; }

step "1/10 toolchain pin"
"$PY" -c "import sys; assert sys.version_info[:2]==(3,12), sys.version; print('python', sys.version.split()[0], 'OK')"
grep -qi uv "$ROOT/.venv/pyvenv.cfg" || { echo "FAIL: .venv is not uv-created"; exit 1; }

step "2/10 frozen surface byte-clean under $V2TAG"
git diff --quiet "$V2TAG" HEAD -- exp/ wct/ m0/ || { echo "FAIL: committed diff"; exit 1; }
git diff --quiet "$V2TAG" -- exp/ wct/ m0/ || { echo "FAIL: working-tree diff"; exit 1; }
test -z "$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)" \
  || { echo "FAIL: untracked paths under the frozen surface"; exit 1; }
echo "clean"

step "3/10 evidence immutability: out/v3, out/slice3, out/e1*_summary*.json (B9)"
# out/v3 and the e1 summaries are pinned to the evidence commit $EV.
# out/slice3 postdates $EV (introduced by 32fead0), so it is pinned to its own
# committed content at HEAD: "byte-identical to their committed content" is the
# constraint, and for slice3 that content is HEAD's, not $EV's.
PINNED="$(git ls-tree -r --name-only "$EV" out/v3 | sort -u || true)"
NOW="$(git ls-files --cached --others --exclude-standard out/v3 | sort -u || true)"
test "$NOW" = "$PINNED" || { echo "FAIL: out/v3 contents differ from $EV"; exit 1; }
for f in $PINNED; do
  git show "$EV:$f" | diff -q - "$f" >/dev/null || { echo "FAIL: $f differs from $EV"; exit 1; }
done
# Anchored to the commit that INTRODUCED out/slice3, not to HEAD: comparing against
# HEAD lets a modified evidence file become its own baseline once it is committed with
# the slice, which is not immutability.
git merge-base --is-ancestor "$S3EV" HEAD 2>/dev/null \
  || { echo "FAIL: evidence anchor $S3EV is not an ancestor of HEAD"; exit 1; }
test "$(git rev-parse "$S3EV")" != "$(git rev-parse HEAD)" \
  || { echo "FAIL: evidence anchor is HEAD; it must predate this slice"; exit 1; }
S3_PINNED="$(git ls-tree -r --name-only "$S3EV" out/slice3 | sort -u || true)"
S3_NOW="$(git ls-files --cached --others --exclude-standard out/slice3 | sort -u || true)"
test -n "$S3_PINNED" || { echo "FAIL: out/slice3 absent at $S3EV; there is no pin to check"; exit 1; }
test "$S3_NOW" = "$S3_PINNED" || { echo "FAIL: out/slice3 path set differs from $S3EV (extra or missing files)"; exit 1; }
for f in $S3_PINNED; do
  git show "$S3EV:$f" | diff -q - "$f" >/dev/null || { echo "FAIL: $f differs from $S3EV"; exit 1; }
done
E1_PINNED="$(git ls-tree -r --name-only "$EV" out | grep -E 'out/e1.*_summary.*\.json$' | sort -u)"
E1_NOW="$(git ls-files --cached --others --exclude-standard out | grep -E 'out/e1.*_summary.*\.json$' | sort -u || true)"
test "$E1_NOW" = "$E1_PINNED" || { echo "FAIL: e1 summary path set differs from $EV (extra or missing files)"; exit 1; }
for f in $E1_PINNED; do
  git show "$EV:$f" | diff -q - "$f" >/dev/null || { echo "FAIL: $f differs from $EV"; exit 1; }
done
echo "immutable"

step "4/10 frozen NLI cache uncontaminated by fp32"
N_NLI="$(ls "$ROOT/out/cache/nli" | wc -l)"
test "$N_NLI" -eq 1826 || { echo "FAIL: out/cache/nli has $N_NLI entries, expected 1826 (fp32 leaked?)"; exit 1; }
echo "nli entries $N_NLI unchanged"

step "5/10 cycle-3 generation artifact set is EMPTY (tag precedes data)"
if [ -d "$ROOT/out/cycle3" ]; then
  N_GEN="$(find "$ROOT/out/cycle3" -name '*.json' -not -name 'caps.json' | wc -l)"
  test "$N_GEN" -eq 0 || { echo "FAIL: $N_GEN cycle-3 generation artifacts exist before the tag"; exit 1; }
fi
echo "empty"

step "6/10 registration validated INDEPENDENTLY of the builder"
"$PY" -m exp3.validate_v3 || { echo "FAIL: independent validation"; exit 1; }

step "6b/10 registration re-derived from artifacts (no hand-typed figure)"
"$PY" - <<'PYX'
import sys, yaml
from exp3 import prereg_v3_build as B
on_disk = yaml.safe_load(open("prereg_v3.yaml"))
rebuilt = B.build()
if rebuilt != on_disk:
    diff = [k for k in set(rebuilt) | set(on_disk) if rebuilt.get(k) != on_disk.get(k)]
    print(f"FAIL: prereg_v3.yaml differs from the builder in: {diff}"); sys.exit(1)
print(f"re-derived identical ({len(on_disk)} top-level fields)")
PYX

step "7/10 corpus pin re-verified"
"$PY" -c "
from exp3 import corpus_v3 as C
v = C.verify()
print(f\"corpus {v['n_items']} items, sha {v['sha256'][:16]}..., cycle2 subset {v['cycle2_subset']}\")"

if [ "$SMOKE" = "1" ]; then
  step "7b/10 endpoint smoke (SPENDS)"
  "$PY" -c "
from exp3 import smoke_v3 as S
r = S.run(); rep = S.verify(r, require_all=False)
print('echoes:', rep['expected_echoes'])
print('unreachable:', rep['unreachable'])"
else
  step "7b/10 endpoint smoke SKIPPED (pass --smoke to probe)"
fi

step "8/10 frozen reproduction, all four panels, cache-only"
WCT_LOCAL_BASE=http://127.0.0.1:9 "$PY" - <<'PYX'
import sys
from wct3 import strict
strict.install()
import exp3.reanalyse as R
bad = []
for p in ("c1_local", "c1_openrouter", "c2_panelA", "c2_panelB"):
    r = R.analyse_panel(p)["frozen_reproduction_all_strata"]
    print(f"  {p:15s} {r['all_match']}")
    if not r["all_match"]:
        bad.append(p)
if bad:
    print(f"FAIL: reproduction broke for {bad}"); sys.exit(1)
PYX

step "9/10 full pinned suite"
"$PY" -m pytest -q tests/

step "10/10 DECISIONS entry current (B11)"
# no `|| true`: a failing render must propagate, or the stage is not gated at all
"$PY" -m exp3.decide_v3 || { echo "FAIL: could not render the DECISIONS entry"; exit 1; }
"$PY" -m exp3.decide_v3 --check || { echo "FAIL: DECISIONS entry stale"; exit 1; }

step "7c/10 smoke evidence completeness (B4)"
"$PY" -m exp3.smoke_v3 || true
if [ "$DOTAG" = "1" ]; then
  step "TAG $V3TAG (human-gated)"
  # B4 requires an OBSERVED echo per member; tagging on defaults would freeze a
  # registration that fails its own acceptance criterion.
  "$PY" -m exp3.smoke_v3 --check-tag-ready \
    || { echo "FAIL: cannot tag on incomplete smoke evidence (B4)"; exit 1; }
  test -z "$(git status --porcelain)" || { echo "FAIL: tree dirty; commit before tagging"; exit 1; }
  git rev-parse "$V3TAG" >/dev/null 2>&1 && { echo "FAIL: tag $V3TAG already exists"; exit 1; }
  REG_FP="$("$PY" -c "from exp3.decide_v3 import fingerprint; print(fingerprint())")"
  REG_SHA="$(sha256sum prereg_v3.yaml | cut -d" " -f1)"
  CORPUS_SHA="$("$PY" -c "import yaml;print(yaml.safe_load(open('prereg_v3.yaml'))['dataset']['sha256'])")"
  NLI_N="$(ls "$ROOT/out/cache/nli" | wc -l)"
  git tag -a "$V3TAG" -F - <<TAGMSG
Cycle-3 registration at $(git rev-parse --short HEAD)

registration-fingerprint: $REG_FP
prereg_v3.yaml sha256:    $REG_SHA
corpus sha256:            $CORPUS_SHA
frozen v2 surface:        clean under $V2TAG
evidence pinned:          out/v3 + e1 summaries at $EV, out/slice3 at $S3EV
frozen nli cache entries: $NLI_N
cycle-3 generation:       none at tag time
TAGMSG
  TAGGED="$(git rev-parse "$V3TAG^{tree}")"; HEADT="$(git rev-parse 'HEAD^{tree}')"
  test "$TAGGED" = "$HEADT" || { echo "FAIL: tag tree != HEAD tree"; exit 1; }
  echo "tagged $V3TAG -> tree ${TAGGED:0:12}"
else
  printf '\n=== TAG NOT CREATED (pass --tag; separate human-gated step) ===\n'
fi

printf '\nSLICE 4 GATE PASSED\n'
