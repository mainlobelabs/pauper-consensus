#!/usr/bin/env bash
# Slice 2 gate: one command, fails closed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
PY="$ROOT/.venv/bin/python"; TAG="prereg-v2-2026-08-16"; EV="e63f946"
export PYTHONPATH="$ROOT" WCT_CACHE="${WCT_CACHE:-$ROOT/out/cache}" WCT_LOCAL_BASE="http://127.0.0.1:9"
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

step "3/7 evidence immutable against $EV (not HEAD)"
# pinned to the introducing commit: a HEAD comparison would pass if an artifact had
# already been altered AND committed before this gate ran
for f in out/v3/reanalysis_c1_local.json out/v3/reanalysis_c1_openrouter.json \
         out/v3/reanalysis_c2_panelA.json out/v3/reanalysis_c2_panelB.json \
         out/e1_summary.json out/e1_summary_openrouter.json \
         out/e1_v2_summary_panelA.json out/e1_v2_summary_panelB.json; do
  git show "$EV:$f" | diff -q - "$f" >/dev/null || { echo "FAIL: $f differs from $EV"; exit 1; }
done
echo "8 evidence artifacts identical to $EV"
# the pinned evidence directory must not have GAINED files either: comparing only the
# eight known artifacts would miss a new one added alongside them
EV_FILES="$(git show "$EV" --stat --name-only --format= -- out/v3 | sort -u | grep . || true)"
NOW_FILES="$(git ls-files --cached --others --exclude-standard out/v3 | sort -u)"
PINNED="$(git ls-tree -r --name-only "$EV" out/v3 | sort -u)"
test "$NOW_FILES" = "$PINNED" \
  || { echo "FAIL: out/v3 contents differ from $EV:"; diff <(echo "$PINNED") <(echo "$NOW_FILES") || true; exit 1; }
echo "out/v3 contains exactly the files pinned at $EV"

step "4/7 unmarked prose unchanged against $EV"
"$PY" - <<'EOF'
import hashlib, re, subprocess, sys
# Two earlier versions of this check were unsound. Section-level scoping skipped any
# section containing a correction, so 6.2 (which shares `## 6` with the corrected 6.1) was
# unverified -- proven by tampering with it and watching the gate pass. Fragment membership
# then ignored ORDER and trusted the markers themselves, so protected prose could be
# exempted simply by wrapping it in a new marker pair. This version pins the marker count
# and walks the fragments in order.
EXPECTED_MARKERS = 9
cur = open("paper.md").read()
old = subprocess.run(["git", "show", "e63f946:paper.md"],
                     capture_output=True, text=True, check=True).stdout
if not old.strip():
    print("FAIL: could not read the pinned draft"); sys.exit(1)

# Pinning the COUNT does not pin WHICH text is exempt: a pair could be moved onto altered
# protected prose while a corrected passage was restored, keeping the count at seven. Each
# marked region must therefore open with its sanctioned anchor.
ANCHORS = ("## Correction notice", "One finding holds on all four panel-cycles",
           "4. A correction, across both cycles", "The arm draft v3 called",
           "**6.1 Polarity, not capping**",
           "The mechanism results (intercept, pola",
           "- **A registered arm was never implemented",
           "And the finding we reported as needing no second cycle",
           "| `out/v3/reanalysis_*.json` |")
marked = re.findall(r"<!-- slice2:begin -->(.*?)<!-- slice2:end -->", cur, flags=re.S)
# Start anchors alone are not enough: moving an END marker past 6.2-7 would exempt those
# sections while preserving both the count and every start anchor. Each region is pinned at
# BOTH ends, so its extent is fixed, not just its opening.
END_ANCHORS = (
    " and the pre-correction text remains available at `e63f946`.",
    "still counting sources \u2014 is what collapses them to chance.",
    "sts nothing, removing the sign destroys everything (\u00a76.1).",
    "the cost of discarding polarity (correction notice, \u00a76.1).",
    "only that this measurement never tested it.",
    "hether it is necessary remains untested.",
    "the cost of discarding the audit.",
    "ich twice already has not matched what a protocol assumed.",
    "e unchanged under tag `prereg-v2-2026-08-16` |",
)
for i, (region, anchor, tail) in enumerate(zip(marked, ANCHORS, END_ANCHORS)):
    body = region.strip()
    if not body.startswith(anchor):
        print(f"FAIL: marked region {i+1} does not OPEN with its sanctioned anchor "
              f"{anchor!r}; markers may not be reassigned to other text")
        sys.exit(1)
    if not body.endswith(tail):
        print(f"FAIL: marked region {i+1} does not CLOSE with its sanctioned anchor "
              f"{tail!r}; an end marker may not be moved to exempt further text")
        sys.exit(1)
if len(marked) != len(ANCHORS):
    print(f"FAIL: {len(marked)} marked regions, expected {len(ANCHORS)}"); sys.exit(1)

n = len(re.findall(r"<!-- slice2:begin -->", cur))
m = len(re.findall(r"<!-- slice2:end -->", cur))
if n != m or n != EXPECTED_MARKERS:
    print(f"FAIL: {n} begin / {m} end markers, expected {EXPECTED_MARKERS} pairs. "
          f"Markers are what exempt text from this check, so their count is pinned: "
          f"adding one would silently exempt whatever it wraps.")
    sys.exit(1)

def trim(s):
    """Drop horizontal rules and blank lines at a fragment's edges.

    Inserting a new section legitimately adds a `---` rule, so an edge separator has no
    counterpart in the pinned draft. That is a consequence of the correction, not evidence
    of tampering; the PROSE either side of it is what must be verbatim.
    """
    lines = s.splitlines()
    while lines and (not lines[0].strip() or set(lines[0].strip()) <= {"-"}):
        lines.pop(0)
    while lines and (not lines[-1].strip() or set(lines[-1].strip()) <= {"-"}):
        lines.pop()
    return "\n".join(lines).strip()

# Substring containment is NOT sufficient: deleting a prefix or suffix from a fragment
# leaves a matching substring and passes, and a short fragment was skipped entirely. The
# concatenation of ALL unmarked text is therefore pinned by hash -- no partial deletion,
# truncation, reordering or skipped fragment survives it. The ordered walk is kept as a
# secondary diagnostic because a hash mismatch alone does not say WHERE.
UNMARKED_SHA = "9fed6e858cb9620cdb0a31ca070881ac44c3a55e6d07f669db3a86186e665ce6"
frags = re.split(r"<!-- slice2:begin -->.*?<!-- slice2:end -->", cur, flags=re.S)
joined = "\x00".join(f.strip() for f in frags)
got = hashlib.sha256(joined.encode()).hexdigest()
if got != UNMARKED_SHA:
    print(f"FAIL: unmarked content hash {got[:16]} != pinned {UNMARKED_SHA[:16]}. "
          f"Text outside the slice markers changed.")
    # locate it for the operator
    cursor = 0
    for i, f in enumerate(frags):
        f = trim(f)
        if not f:
            continue
        at = old.find(f, cursor)
        if at < 0:
            head = (f.splitlines() or [f])[0][:90]
            print(f"       first divergence in fragment {i+1}: {head!r}")
            break
        cursor = at + len(f)
    sys.exit(1)

# secondary, and it must actually run: an earlier version of this block reported
# "0 fragments verified" alongside a pass, which is the vacuous result this gate exists
# to prevent. The count is asserted against the number of non-trivial fragments.
cursor = checked = 0
nontrivial = sum(1 for f in frags if len(trim(f)) >= 40)
for f in frags:
    f = trim(f)
    if len(f) < 40:
        continue
    at = old.find(f, cursor)
    if at < 0:
        head = (f.splitlines() or [f])[0][:90]
        print(f"FAIL: unmarked text out of order or absent -> {head!r}")
        sys.exit(1)
    cursor = at + len(f)
    checked += 1
if checked != nontrivial or checked == 0:
    print(f"FAIL: ordered walk verified {checked} of {nontrivial} fragments; a check that "
          f"verifies nothing must not report success")
    sys.exit(1)
print(f"{checked} unmarked fragments verbatim and IN ORDER, all {len(frags)} hash-pinned; "
      f"{n} marker pairs as pinned")
EOF

step "5/7 full test suite (bracketed by a cache manifest)"
# Existing tests call the real cached embed/NLI paths without installing wct3.strict, so an
# NLI miss could compute locally and write the cache. Slice 1's gate proved zero inference
# with a manifest; this one must too, and it must bracket the TESTS, not just the analysis.
manifest() {
  find out/cache/embed out/cache/nli -type f -printf '%p %s %T@\n' 2>/dev/null | sort | sha256sum
  find out/cache/embed out/cache/nli -type f -print0 2>/dev/null | sort -z \
    | xargs -0 -r sha256sum | sha256sum
}
BEFORE="$(manifest)"
"$PY" -m pytest -q tests/
AFTER="$(manifest)"
test "$BEFORE" = "$AFTER" \
  || { echo "FAIL: the embed/NLI cache CHANGED during the suite — inference ran"; exit 1; }
echo "cache unchanged across the suite: no embedding or NLI was computed"

step "6/7 paper figure check"
"$PY" -m exp3.check_paper

step "7/7 DECISIONS.md entry"
"$PY" -m exp3.slice2_decide
"$PY" -m exp3.slice2_decide --check

printf '\n=== SLICE 2 GATE PASSED ===\n'
