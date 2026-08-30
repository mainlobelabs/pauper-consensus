# Plan: Slice 2 — paper corrections from slice 1's findings

Run `20260829-151714-c1159b09`, workstream `20260828-181135-0d060fc4` slice 2 of 4.

**Revision history** (non-normative; the live specification is `## Approach` and the
`## Tasks` fence, and nothing here overrides them). Rounds 1-3 closed B1/B3/B4/B5; B2
reopened twice on the same substance -- proving a figure was quoted does not prove it is
right -- and was resolved by removing the weak class rather than strengthening it. Spec
rounds then closed a factual overclaim in the correction itself, a contradiction about
source counting, three vacuous-pass bugs in the gate, and a premature claim that cycle 3
was already registered. This block is deliberately descriptive: earlier versions restated
rules and contradicted the spec once those rules changed.

## Approach

Three claims in `paper.md` rest on a measurement that did not measure them, and one
registered arm that would have tested the paper's central premise was never run. This slice
corrects the prose and adds a machine check so the corrected figures cannot drift from the
artifacts they come from. No analysis is re-run; no registered verdict moves.

**What actually has to change, and what must not.** The frozen `uncapped` arm scores
`n_claims`, which `align_anchored` has already collapsed to one observation per (agent,
pid), so it equals `n_emitting`: capped and unsigned. Every sentence built on it describes
a polarity contrast. But §§6.2-6.4, 7, and the whole cycle-1/cycle-2 narrative are
untouched by this: the permutation nulls, the rank-robustness result and the intercept
diagnosis do not depend on the uncapped arm. Rewriting them would be scope creep, and worse,
would blur which claims the correction actually reaches.

**The conclusion moves to the single-source finding** (human decision, OQ1). §9 currently
ends on the refuted sentence. It will end instead on this, stated precisely (B1): no
REGISTERED result in either cycle distinguishes cross-model agreement from one good model,
because the arm that would have — `single_best_calibration_selected` — was registered and
never implemented. The post-hoc contrasts this slice adds do bear on it and must be stated
in the same breath rather than elided: the panel beats its calibration-selected best single
source by +0.045 to +0.089 on three panel-cycles and inconclusively (+0.0329
[-0.0109,+0.0703]) on the fourth. So the honest close is that the margin is real but small,
unregistered, and absent on one panel — which is what cycle 3 exists to settle, not a claim
that nothing was found. An earlier draft of this plan said "no reported result", which
would have contradicted the very numbers the slice adds.

**A correction notice at the head of the paper** (human decision, OQ2), dated, naming each
changed claim and why, so a reader of draft v3 can see what moved. The project's precedent
is a superseding record that leaves the original visible, not a silent rewrite.

**Evidence is pinned to a commit, not to HEAD** (B3). `out/v3/` and the frozen
`out/e1*_summary*.json` are compared against **e63f946**, the commit that introduced them,
not against HEAD: a HEAD comparison would pass if an artifact had already been altered and
committed before the gate ran. The working tree is checked separately, so both a committed
alteration and an uncommitted one fail.

**What was wrong was the label, not the arithmetic.** Draft v3's quoted AUROC ranges are
correct readings of the frozen `uncapped` arm — its 0.502-0.554 is that arm's 0.50174 and
0.55439 across the cycle-1 strata. The paper did not miscompute anything; it described a
capped, unsigned coverage count as "claim-instance counting" and drew a conclusion about
per-source capping from it. The correction should say exactly that, because "the figures
were wrong" would be false and would invite a reader to distrust the rest of the numbers.
It also means every retained figure is artifact-assertable, which is what lets the checker
drop its weak quoted-figure class (B2).

**Figures are checked, not transcribed.** `exp3/check_paper.py` parses the numbers quoted in
the revised sections out of `paper.md` and asserts each against `out/v3/`. Hand-copying four
panels x four 2x2 cells plus four contrasts is exactly where a transcription error would
survive review, and the M6 numbers already moved once during slice 1 when a calibration map
was read for the wrong cycle.

## Risks

- **Overclaiming the correction.** The corrected result says capping costs nothing on THIS
  instrument and corpus, not that per-source capping is unnecessary in general; the
  one-vote-per-agent cap remains the design and M6 remains untested as a design question.
  The prose must say the narrower thing.
- **Understating it.** Equally, this is a refutation of a stated contribution, not a
  footnote. The notice names it as such.
- **Touching a registered verdict.** Mitigated structurally: the checker asserts the cycle-1
  and cycle-2 headline figures in the paper still match the FROZEN summaries, so an edit
  that altered a registered number fails the gate.
- **Drift between prose and artifacts.** The checker is the mitigation; it runs in the gate.
- **Scope creep into sections the findings do not reach.** The acceptance criteria enumerate
  the sections; the gate asserts the untouched ones are byte-identical to HEAD.

## Rollback

`git revert` the slice commit. The diff comprises: `paper.md` (nine marked passages);
five new files (`exp3/check_paper.py`, `exp3/slice2_decide.py`, `run_slice2.sh`,
`tests/test_check_paper.py`, `tests/fixtures/paper_revised_sections.md`); the
checker's report at `out/slice2/paper_check.json`, which the DECISIONS entry is
derived from and which is deliberately OUTSIDE the pinned `out/v3/` evidence set;
and edits to
`DECISIONS.md` (decision entries plus one slice-outcome entry), `REQUEST.md` and `PLAN.md`
(this slice's own scoping), and `MASTER_v3.md` (the human-approved restructuring into
slices 2/3/4, made before this run started and declared in `REQUEST.md`). No artifact,
cache, summary or tag is touched, and `git diff prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/`
is empty before and after.

## Tasks

```json
[
  {
    "id": "P1-checker",
    "title": "exp3/check_paper.py: assert every quoted figure against out/v3 and the frozen summaries",
    "depends_on": [],
    "files": [
      "exp3/check_paper.py",
      "tests/test_check_paper.py",
      "tests/fixtures/paper_revised_sections.md"
    ],
    "acceptance": [
      "ENVIRONMENT: run everything with /home/jmannings/dev/waveconv/.venv/bin/python (3.12). Bare `python` is system 3.14 without the project deps and will fail at `import httpx`. There is NO PyPI egress: never pip install, never create a venv. Run tests as PYTHONPATH=\"$PWD\" /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "COMPLETENESS RULE over TWO exhaustive classes; the weak 'quoted' class is GONE (B2). Every numeric literal in the revised passages and the correction notice is either: (a) ARTIFACT-ASSERTED -- equal to a value read from out/v3/ or the frozen out/e1*_summary*.json. This covers figures RETAINED from draft v3 as well as new ones, because draft v3's numbers were correct readings of the frozen uncapped arm (its quoted 0.502-0.554 is that arm's 0.50174 and 0.55439 across the cycle-1 strata); what was wrong was the LABEL, not the arithmetic. A figure presented as a quotation is additionally verified to appear verbatim in `git show e63f946:paper.md`, so the paper provably quotes its own earlier text -- but that check is on top of the artifact assertion, never instead of it. Or (b) STRUCTURAL -- matched by a DECLARED pattern: an ISO date, a source reference <path>.<py|yaml|md>:<line>[-<line>], a section number, or a draft version identifier, which P2 is required to add. A literal matching neither class fails the check",
      "asserts the capping x polarity 2x2 cells against out/v3/reanalysis_*.json m6_2x2.cells[*].raw_auroc",
      "asserts each single-source contrast against panel_vs_single_best_calibration_selected under that panel's registered map, including the decision string",
      "asserts the cycle-1 and cycle-2 headline figures still quoted in the paper against the FROZEN out/e1*_summary*.json, so a correction cannot silently move a registered number",
      "asserts the aligner probe figures against the artifacts",
      "exits non-zero naming any figure that does not match or is unclassified; tests prove it catches a planted wrong digit, an unclassified new figure, a literal that only superficially resembles a structural reference, AND a 'quoted' figure that does not appear in e63f946:paper.md, AND a retained draft-v3 figure that matches no artifact value",
      "UNIT TESTS USE A FIXTURE (B6): P1 runs before P2 writes the real passages, so its tests parse an in-repo fixture containing the planned revised text. The real-paper run is deferred to P2's and P3's checks, and the module takes the paper path as an argument so both work",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/ && test -z \"$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)\"",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_check_paper.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "P2-corrections",
    "title": "paper.md: correction notice, 6.1, contribution 4, 8 disclosure, 9 conclusion",
    "depends_on": [
      "P1-checker"
    ],
    "files": [
      "paper.md"
    ],
    "acceptance": [
      "a dated correction notice at the head naming each changed claim and why, leaving draft v3's original wording visible",
      "6.1 restated as the polarity result: the frozen `uncapped` arm identified as capped-and-unsigned, the mechanism given (align_anchored collapses per (agent,pid) before exp/e1.py:76-78 counts), and the full 2x2 reported at raw AUROC with all four panels",
      "contribution 4 restated to match 6.1, no longer claiming a one-vote-per-source replication",
      "8 discloses that single_best_calibration_selected (prereg.yaml:166, plan.md:488) was registered and never implemented in either cycle",
      "the single-source contrast reported at the prominence the registered failures get, including c2_panelB inconclusive under the frozen decision rule",
      "every new number labelled POST-HOC and sourced to out/v3/",
      "the D3 disclosure recorded: cycle 2's mapper was unauditable from cache because its own driver discarded the audit; probe computed under a recorded amendment, 0.9721 vs cycle 1's 0.9724",
      "no registered cycle-1 or cycle-2 verdict is restated or altered",
      "sections 6.2, 6.3, 6.4, 7 and the cycle-1/cycle-2 narrative are unchanged except where they cite a corrected figure",
      "9 closes on the single-source finding per the recorded human decision, stated as: no REGISTERED result in either cycle distinguishes cross-model agreement from one good model, because single_best_calibration_selected was never implemented. It must state IN THE SAME PASSAGE the post-hoc margins this slice adds (+0.045 to +0.089 on three panel-cycles, +0.0329 [-0.0109,+0.0703] inconclusive on c2_panelB), so the close is 'real but small, unregistered, and absent on one panel' and NOT 'nothing was found' (B1)"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" /home/jmannings/dev/waveconv/.venv/bin/python -m exp3.check_paper",
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "P3-gate",
    "title": "run_slice2.sh: one command, fail-closed",
    "depends_on": [
      "P2-corrections"
    ],
    "files": [
      "run_slice2.sh",
      "exp3/slice2_decide.py"
    ],
    "acceptance": [
      "ENVIRONMENT: run everything with /home/jmannings/dev/waveconv/.venv/bin/python (3.12). Bare `python` is system 3.14 without the project deps and will fail at `import httpx`. There is NO PyPI egress: never pip install, never create a venv. Run tests as PYTHONPATH=\"$PWD\" /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "asserts Python 3.12 and the uv pin, then the tag-clean check (committed, working-tree and untracked over exp/ wct/ m0/), then the full pytest suite, then exp3.check_paper against the real paper.md, exiting non-zero on the first failure",
      "ARTIFACT IMMUTABILITY PINNED TO A COMMIT (B3): asserts out/v3/*.json and out/e1*_summary*.json are byte-identical to their content at e63f946 via `git show e63f946:<path>`, NOT against HEAD, so an alteration committed before the gate ran still fails; the working tree is checked separately so an uncommitted edit fails too",
      "UNTOUCHED-PROSE GUARD (B4), by MARKER AND HASH rather than by heading extraction. The plan originally named an explicit heading list (6.2, 6.3, 6.4, 7, 3, 4, 5); that mechanism proved unsound in practice and is replaced by a stronger one, recorded here rather than left as a silent divergence. Heading-scoped checking skipped any section CONTAINING a correction, so 6.2 -- which shares `## 6` with the corrected 6.1 -- went unverified while the gate reported 24 sections checked (proven by tampering with it and watching the gate pass). The implemented guard instead: (a) pins the nine marked regions at BOTH ends to sanctioned anchors, so a marker cannot be added, moved, or extended to exempt further text; (b) pins the sha256 of ALL unmarked content, which no partial deletion, truncation, reordering or short-fragment skip survives; and (c) walks the fragments in order as a locating diagnostic, asserting it verified every non-trivial fragment rather than reporting success having verified none. This covers the whole paper outside the corrections, not an enumerated subset of it, and each property is verified by planting the failure it is meant to catch.",
      "appends the slice-outcome entry to DECISIONS.md (B5), derived from the checker's output rather than written by hand, and fails if it is absent afterwards; the OQ1/OQ2 decisions are already recorded and are NOT re-entered",
      "the 41 existing tests still pass unchanged",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && bash run_slice2.sh"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  }
]
```

## Open questions

- OQ1, OQ2 (REQUEST): both RESOLVED at the human gate 2026-08-29 and recorded in
  `DECISIONS.md`. §9 closes on the single-source finding; the correction notice is a dated
  block at the head of `paper.md`.
- OQ3 (new, non-blocking): the corrected §6.1 shows uncapped SIGNED counting slightly
  BEATING capped on three of four panels (e.g. c1_local 0.9664 vs 0.9001). That is a
  suggestive result about the cap costing information, not just being unnecessary, but it is
  post-hoc, unregistered, and on four panels. The plan states it as an observation and
  explicitly does not claim it. Flagging in case you want it registered in cycle 3 instead.
