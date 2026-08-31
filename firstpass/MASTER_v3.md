# Request: Corrected instrument, and a cycle-3 registration that tests the panel against its best single source

## Thoughts / context

> fix all things on this list, and prepare a new experiment

The list is three defects found by review on 2026-08-28, each verified against the frozen
cache before being written down. All three bear on how `paper.md` should be read.

**D1 — the registered single-source arm was never implemented.**
`prereg.yaml:166` registers `single_best_calibration_selected`. `plan.md:488` makes it
baseline #1. `m0/simulate.py:75` implements it in simulation. Neither `exp/e1.py` nor
`exp/e1_v2.py` has it, and `prereg_v2.yaml:591-599` drops it from the arm list without
comment; `paper.md` §8 discloses one unrun robustness check but not this arm.
Computed post-hoc over the frozen v2 cache (same Platt map, same split, same item-block
bootstrap, source selected on calibration only), it reproduces the committed WCT-U and
WCT-EM points exactly and gives:

| | best single source vs covariate baseline | panel (WCT-EM) over that source |
|---|---|---|
| panel A (`glm`) | +0.1436 [+0.0855, +0.2016] go | +0.0762 [+0.0465, +0.1068] go |
| panel B (`gptoss`) | +0.2394 [+0.1646, +0.3114] go | +0.0329 [-0.0109, +0.0703] **inconclusive** |

On panel B one model alone exceeds the point estimate the paper headlines for panel A, and
the three-model panel's advantage over it does not clear the frozen decision rule. The
registered primary therefore establishes that proposition-level vote scores beat
item-difficulty covariates; it does not establish that cross-model agreement is the
mechanism, which is what §1 asserts and what E0 failed to test.

**D2 — the `uncapped` M6 ablation does not measure claim instances.**
`cluster.align_anchored` collapses to at most one `Observation` per `(agent, pid)` (`best`
is keyed on that tuple, `wct/cluster.py:118-127`). `exp/e1.py:76-78` then counts those
already-collapsed observations and labels the result "claim-instance counts for the
uncapped ablation (assumption M6)". Verified: `n_claims == n_emitting` on 607/607 rows
(panel A) and 550/550 (panel B), maximum value 3 = M. So `paper.md` §6.1, contribution 4,
and the conclusion's "count text instead of sources, and there is nothing there" compare
*signed support* against *unsigned coverage count*, both capped — a result about polarity,
not about capping. True claim-instance counting was never measured; the pre-collapse
assignments are discarded inside `align_anchored`.
Consequence: `X` in `e1.to_arrays` carries `n_emitting` and `n_claims` as separate columns,
so the covariate baseline's registered "verbosity" feature is a duplicate of "coverage".
Checked and numerically harmless (primary 0.2198 -> 0.2196 deduplicated) — a reporting
defect, not an inflation.

**D3 — cycle 2 discarded the diagnostic that found cycle 1's defect.**
`exp/e1_v2.py:189` binds `audits` from `e1.build_observations` and never uses it; neither
cycle-2 summary contains an alignment audit. Cycle 1 reported aligner self-identification
0.9724 (n=1483, 41 wrong-proposition, 0 wrong-polarity), lexical recall 0.6899, 853
same-agent conflicts, and a 24,621-claims -> 1,197-observations funnel. That funnel and the
polarity restriction are how cycle 1's defect was found. The run that produced the go has
no measurement-quality evidence at all, which sits badly beside §4.2's own lesson.

The new experiment follows from D1. Cycle 3 registers, as its primary, the contrast cycle 2
left open: does an M-source panel beat the single source selected on calibration, and does
that margin grow with M? That is the dose-response error decorrelation predicts and the one
E0 was too underpowered to test. Panels at M=3 and M=5, the five-family target the original
protocol set and never met.

Human decisions taken at the harness gate, 2026-08-28:
- Fixes land as NEW modules. `exp/e1_v2.py`, `exp/e1.py` and `wct/cluster.py` stay
  byte-identical under `prereg-v2-2026-08-16`. Preserving `git diff prereg-v2-2026-08-16
  HEAD -- exp/ wct/ m0/` as empty is a hard constraint, not a preference: it is the paper's
  strongest independently verifiable claim.
- Cycle 3's registered primary is panel vs calibration-selected best single source, at
  M=3 and M=5.

## Constraints

- **The v2 tag stays byte-clean.** No edit to any file under `exp/`, `wct/` or `m0/` that
  `prereg-v2-2026-08-16` contains. Corrections go in new modules that import the frozen ones.
  A slice is failed, not waived, if `git diff prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/`
  is non-empty at its exit.
- **No inference in this workstream.** No OpenRouter, no local generation endpoint, no new
  embedding calls beyond what the existing `out/cache/embed` and `out/cache/nli` already
  hold. "Prepare a new experiment" means register it, not run it. Package installation is
  permitted; PyPI is not inference.
- Python venv pinned to 3.12 via `uv` (system default 3.14 has no torch wheels).
- Every corrected-instrument number computed over cycle-1 or cycle-2 caches is POST-HOC and
  must be labelled so. It diagnoses those cycles; it never restates their registered verdicts.
- `Date.now()`-style nondeterminism banned; fixed seeds recorded in every result row.
- Per GOTCHAS: no embedding or analysis call against `:1234` while any generation is in
  flight; the single-model-slot contention kills the generation, not just the analysis.

## Non-goals

- Running cycle 3's generation. Registration and tag only; generation is a later run.
- Reopening cycle 1's or cycle 2's registered verdicts. They stand as published.
- `wct/diffuse.py`, `wct/derive.py`, E2 propagation, and everything else in EXPERIMENT.md §5
  "Deliberately not built". The wave-propagation idea stays unbuilt.
- Rewriting `paper.md` beyond the sections the three defects make false.
- Claim B work of any kind.

---

## Slice 1: Corrected instrument and zero-cost re-analysis

Build the corrected instrument alongside the frozen one and re-analyse every existing panel
with it. No inference: all four panel-cycles re-run over the immutable cache. This slice
produces the effect sizes that set cycle 3's delta and its power calculation, so it must
complete before slice 2 can register anything.

- A1: New module carrying the corrected instrument, importing the frozen `exp/e1.py` and
  `wct/cluster.py` rather than editing them. `git diff prereg-v2-2026-08-16 HEAD -- exp/
  wct/ m0/` is empty at slice exit, asserted in the slice's own check.
- A2: A claim-instance-preserving alignment path: every claim that passes `T_ALIGN` is
  retained with its `(agent, pid, obs, score)` rather than only the per-agent argmax, so
  the true uncapped count is recoverable. The capped observation set it yields is
  bit-identical to `align_anchored`'s on the same inputs, asserted as a test.
- A3: A genuine `uncapped` arm scored on that count, plus a signed uncapped variant, so
  capping and polarity are separated instead of confounded. Reported next to the frozen
  arm, with the frozen arm's value reproduced unchanged.
- A4: `single_best_calibration_selected` implemented as registered: source chosen on the
  calibration split alone, identical calibration map and bootstrap as every other arm, and
  the oracle-selected source reported beside it as the upper bound `m0/simulate.py:75`
  already distinguishes.
- A5: The covariate baseline refitted without the duplicated verbosity column, with a real
  verbosity feature, reported as a sensitivity row against the frozen baseline.
- A6: The cycle-1 alignment audit restored and emitted for every panel of both cycles:
  aligner self-identification, lexical-reference recall, same-agent conflicts, and the
  claims -> observations funnel.
- A7: All four panel-cycles (cycle 1 local, cycle 1 OpenRouter, cycle 2 panel A, cycle 2
  panel B) re-analysed under the corrected instrument, cache-only, into summaries kept
  separate from the frozen `out/e1*_summary*.json`.
- A8: Every arm the frozen instrument reports is reproduced byte-identically by the new
  module where the correction does not touch it, so any movement is attributable.
- A9: One command runs the whole slice and exits non-zero on any failed assertion.
- A10: `DECISIONS.md` entry recording D1-D3, what moved, and what did not.

## Slice 2: Paper corrections from slice 1's findings

RESCOPED 2026-08-29 (human decision). Originally B10 inside the registration slice.
Split out and moved first because slice 1's D2 result REFUTES paper.md 6.1 rather than
qualifying it, the correction costs nothing (it reads committed artifacts, no inference),
and a draft carrying two named authors should not sit on a claim its own instrument
contradicts while a registration that needs new generation is prepared.

- C1: 6.1 and contribution 4 restated as the polarity result the corrected instrument
  measures. The frozen `uncapped` arm is identified as capped-and-unsigned, with the
  reason (align_anchored collapses per (agent,pid) before exp/e1.py:76-78 counts), and
  the capping x polarity 2x2 reported in full at raw AUROC.
- C2: The unrun registered arm disclosed in 8: `single_best_calibration_selected`
  (prereg.yaml:166, plan.md:488) was never implemented in either cycle, so no REGISTERED
  result distinguishes cross-model agreement from one good model. The post-hoc contrasts
  this slice adds do bear on it and must be stated alongside, never elided: saying "no
  reported result" would contradict the very numbers the slice reports.
- C3: Slice 1's single-source contrast reported at the prominence the registered failures
  get, including that c2_panelB is inconclusive under the frozen decision rule.
- C4: Every new number labelled POST-HOC and sourced to `out/v3/`; no registered cycle-1
  or cycle-2 verdict restated or altered.
- C5: The D3 disclosure recorded: cycle 2's mapper could not be audited from cache because
  its own driver discarded the audit, and the probe was computed under a recorded
  amendment (0.9721 vs cycle 1's 0.9724).
- C6: A correction notice at the head of the paper naming what changed from draft v3 and
  why, so a reader of the earlier draft can see it. The project's precedent is a
  superseding record that leaves the original visible.
- C7: Every figure quoted in the revised sections is checked against `out/v3/` artifacts by
  a script, not by hand, and that check runs in the slice gate.
- C8: The v2 tag remains byte-clean, asserted in the slice gate across committed,
  working-tree and untracked state.

## Slice 3: Five-family availability, measured before anything is registered

RESCOPED 2026-08-29 (human decision). Originally folded into the registration's B4. Made a
separate gate because the five-family target has now failed TWICE on availability: cycle 1
found three families locally, not five (GOTCHAS 2026-08-07), and cycle 2 had to rebuild
panel A mid-programme when two of its three models left the catalogue. Registering M=5
without measuring first risks freezing a design that cannot be run.

- E1: Every candidate endpoint smoke-tested for real: local `:1234`, OpenRouter, Hoonify.
  Generation attempted, not merely a model-list call, because a listed model that fails to
  load is the exact cycle-1 failure.
- E2: Resolved serving identity recorded per model (served alias AND loaded weights), since
  cycle 2 had to pin these to detect substitution.
- E3: Distinct FAMILIES counted, not model ids: two variants of one family are not two
  independent sources (GOTCHAS, ornith-35b vs ornith-35b-mtp-apex).
- E4: A written verdict on whether M=5 is registrable, with the M=3 subsets it supports.
- E5: If five families are not available, the finding is reported and slice 4 registers
  what IS available; the workstream does not stall and does not quietly register a
  design it cannot run.
- E6: Costs nothing beyond smoke-test tokens; no experimental generation.

## Slice 4: Cycle-3 registration

- B1: `prereg_v3.yaml` carrying every field `EXPERIMENT.md` 3.1(4) requires, with the
  registered primary stated as panel vs calibration-selected best single source.
- B2: Delta set from slice 1's measured margins (+0.033 to +0.089 over the best single
  source across four panel-cycles) and the M=3 spread, with the derivation recorded.
  Never moved after results are visible.
- B3: Power calculation against slice 1's observed per-item variance, reporting the item
  count each of M=3 and M=5 needs. If the design is underpowered at feasible n, that is
  stated plainly and registered as such rather than proceeded past.
- B4: Panels pinned from slice 3's MEASURED availability, every endpoint smoke-tested and
  its resolved serving identity recorded, with any other server echo defined in advance
  as substitution.
- B5: Corpus pinned by SHA-256, capable of containing falsehoods, with the projected count
  of scored positive-polarity negatives stated as a projection and explicitly not a gate.
- B6: Falsifiable predictions with their adjudication rules, including the dose-response
  the decorrelation premise implies (the margin over the best single source grows from
  M=3 to M=5) and what result would refute it.
- B7: The analysis driver committed before generation, so the implementations are the
  registration, as `prereg_v2.yaml` established.
- B8: Hard cumulative per-panel call caps, persisted across re-runs.
- B9: Git tag created before any cycle-3 generation call exists, with the empty-diff
  property asserted at tag time.

## Open questions

- OQ1: A2 changes what `align_anchored` retains. The claim-instance-preserving path must
  reproduce the frozen capped observation set exactly, but its extra output has no consumer
  in the frozen code. Confirm the new path is a parallel function rather than a widened
  return on the frozen one, since the latter would touch a tagged file.
- OQ2: RESOLVED (human, 2026-08-29). A dated correction notice at the head of `paper.md`,
  with draft v3's wording quoted verbatim where a passage turns on its exact claim (§6.1,
  §3.4) and characterised elsewhere; the pre-correction text remains at `e63f946`. B10 was
  split out of the registration slice and became slice 2.
- OQ3: M=5 requires five families that were never simultaneously available; cycle 1 found
  three locally and cycle 2 rebuilt panel A after two models left the catalogue. If five
  cannot be pinned at B4, does cycle 3 register at M=3 and M=4, or park for a human
  decision?
- OQ4: RESOLVED (human, 2026-08-28) and ANSWERED by slice 1. The panel does beat its
  calibration-selected best single source on three of four panel-cycles (+0.0448 to
  +0.0887) and inconclusively on c2_panelB, so the hypothesis is neither dead nor
  established. The dose-response is registered regardless, per the recorded decision;
  slice 4 sets delta and power from these margins.
