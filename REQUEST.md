# Request: Slice 1 — corrected instrument and zero-cost re-analysis

Workstream `20260828-181135-0d060fc4`, slice 1 of 2. Master: `MASTER_v3.md`.
Specification: `MASTER_v3.md` §"Slice 1"; the frozen instrument it corrects is
`exp/e1.py`, `exp/e1_v2.py` and `wct/cluster.py` under tag `prereg-v2-2026-08-16`.

## Thoughts / context

> fix all things on this list, and prepare a new experiment

Three defects, each verified against the frozen cache before being written down. Full
evidence in `MASTER_v3.md`; the short form:

- **D1** `single_best_calibration_selected` is a registered arm (`prereg.yaml:166`,
  `plan.md:488`, simulated at `m0/simulate.py:75`) that no analysis driver implements, and
  `prereg_v2.yaml` drops it silently. Computed post-hoc over the v2 cache it reproduces the
  committed WCT-U/WCT-EM points exactly and shows the cycle-2 panel B advantage over its own
  best single source is +0.0329 [-0.0109, +0.0703] — inconclusive under the frozen rule.
- **D2** the `uncapped` M6 ablation never sees a claim instance. `align_anchored` collapses
  to one observation per `(agent, pid)` before `exp/e1.py:76-78` counts them, so
  `n_claims == n_emitting` on 607/607 and 550/550 rows, max 3 = M. §6.1 compares signed
  support against unsigned coverage count: a polarity result, not a capping result.
- **D3** `exp/e1_v2.py:189` binds `audits` and discards it; neither cycle-2 summary carries
  an alignment audit. The claims -> observations funnel that found cycle 1's defect is absent
  from the run that produced the go.

This slice builds the corrected instrument beside the frozen one and re-runs every existing
panel through it at zero inference cost. Its numbers set slice 2's delta and power, so it
gates slice 2.

## Constraints

- **`prereg-v2-2026-08-16` stays byte-clean.** No edit to any file under `exp/`, `wct/` or
  `m0/` that the tag contains. Corrections are NEW modules importing the frozen ones.
  `git diff prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/` must be empty at slice exit; a
  non-empty diff fails the slice rather than being waived. Human decision, 2026-08-28.
- **No inference.** No OpenRouter, no `:1234` generation, no new embedding calls beyond what
  `out/cache/embed` and `out/cache/nli` already hold. PyPI installation is permitted.
 AMENDED 2026-08-28 (recorded in DECISIONS.md and resolved at the harness human gate): the aligner self-identification probe MAY be computed for the cycle-2 corpus by local in-process CPU NLI only (exp3/probe_backfill.py, --confirm required), because A6 and this constraint as originally written are unsatisfiable together — the probe's pairs are cached only for panels whose driver ran it, and exp/e1_v2.py never did, which IS defect D3. No API, no OpenRouter, no :1234 endpoint, no quota, no network egress. Everything else in this constraint stands.
- Python venv pinned to 3.12 via `uv`; 3.14 is the system default and lacks torch wheels.
- Every number this slice computes over cycle-1 or cycle-2 caches is POST-HOC and labelled
  so. It diagnoses those cycles; it never restates their registered verdicts.
- Fixed seeds, recorded in every result row. No wall-clock nondeterminism.
- Per `GOTCHAS.md`: no embedding or analysis call against `:1234` while generation is in
  flight. No generation runs in this slice, so this is a tripwire, not a schedule.
- New summaries are written to filenames distinct from the frozen `out/e1*_summary*.json`.

## Non-goals

- Cycle 3's registration, its corpus, its panels, its delta. That is slice 2.
- Any generation call whatsoever.
- Reopening cycle 1's or cycle 2's registered verdicts.
- `wct/diffuse.py`, `wct/derive.py`, E2 propagation, and the rest of `EXPERIMENT.md` §5.
- `paper.md` edits. The D1-D3 corrections land in slice 2 (B10).

## Acceptance criteria

- A1: New module carrying the corrected instrument, importing the frozen `exp/e1.py` and
  `wct/cluster.py` rather than editing them. `git diff prereg-v2-2026-08-16 HEAD -- exp/
  wct/ m0/` is empty at slice exit, asserted by the slice's own check.
- A2: A claim-instance-preserving alignment path retaining every claim that passes
  `T_ALIGN` with its `(agent, pid, obs, score)`, not only the per-agent argmax, so the true
  uncapped count is recoverable. The capped observation set it yields is bit-identical to
  `align_anchored`'s on the same inputs, asserted as a test.
- A3: A genuine `uncapped` arm scored on that count, plus a signed uncapped variant, so
  capping and polarity are separated instead of confounded. Reported beside the frozen arm,
  whose value is reproduced unchanged.
- A4: `single_best_calibration_selected` implemented as registered: source chosen on the
  calibration split alone, identical calibration map and bootstrap as every other arm, with
  the oracle-selected source reported beside it as the upper bound `m0/simulate.py:75`
  already distinguishes.
- A5: The covariate baseline refitted without the duplicated verbosity column and with a
  real verbosity feature, reported as a sensitivity row against the frozen baseline.
- A6: The cycle-1 alignment audit restored and emitted for every panel of both cycles:
  aligner self-identification, lexical-reference recall, same-agent conflicts, and the
  claims -> observations funnel.
- A7: All four panel-cycles (cycle 1 local, cycle 1 OpenRouter, cycle 2 panel A, cycle 2
  panel B) re-analysed under the corrected instrument, cache-only.
- A8: Every arm the frozen instrument reports is reproduced byte-identically by the new
  module wherever the correction does not touch it, so any movement is attributable.
- A9: One command runs the whole slice and exits non-zero on any failed assertion.
- A10: `DECISIONS.md` entry recording D1-D3, what moved, and what did not.

## Open questions

- OQ1: A2 must reproduce the frozen capped observation set exactly while retaining more.
  Confirm it is a parallel function in the new module rather than a widened return on
  `wct/cluster.align_anchored`, since the latter would touch a tagged file.
- OQ2: A7 re-runs cycle 1, whose panels used a different loader (`exp/common.load_dataset`
  and `load_generations` return per-cell dicts, not `run_generate_v2.load_cell_v2`'s shape).
  Confirm the corrected module handles both loaders rather than the v2 one only.
- OQ3: A8 asks for byte-identical reproduction of untouched arms. WCT-EM is fitted by EM
  and may not be bit-reproducible across numpy versions in the same venv. Confirm the
  assertion is exact equality on the frozen venv, or a stated tolerance.
- OQ4: If A7 shows no panel beats its calibration-selected best single source, slice 2
  registers a hypothesis already in trouble. Confirm slice 2 proceeds (the M=3 -> M=5
  dose-response is still the informative test) or parks for a human go/no-go at this exit.
