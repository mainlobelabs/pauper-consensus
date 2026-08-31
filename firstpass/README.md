# firstpass/

The original two-cycle pre-registered study — Mannings & Marzuki,
*The Flip Was in the Instrument* (this repo's §2, "Pass 1") — imported
from `mainlobelabs/waveconv1`, branch `e1-results-and-paper` @ 76d005d
(2026-08-31). Full commit history is preserved in this repo's git log;
the subtree merge commit is the junction.

## Layout (as upstream)

- `paper.md` — the Pass 1 paper, draft v3 (17 Aug 2026) with the
  2026-08-29 correction notice (one-vote-per-source retraction).
- `prereg.yaml` / `prereg_v2.yaml` / `prereg_v3.yaml` — cycle 1 / 2 / 3
  registrations. Cycle 3 (prereg-v3) is the frozen 9,805-item
  registration, tagged upstream as `prereg-v3-2026-08-30`.
- `data/` — proofwriter corpus (depth-3 and depth-5, train/dev/test).
- `out/` — all run artifacts from cycles 1-2, slices 2-4, and the
  reanalysis; `out/cache/generation/` is the committed generation cache
  (analysis re-runs at zero inference cost).
- `exp/` `exp3/` — experiment drivers (E0/E1, cycle 1-2, cycle 3).
- `wct/` `wct3/` — the WCT instrument (alignment, arms, GPU NLI).
- `m0/` — M0 simulator and invariant checks.
- `run_slice1.sh` … `run_slice4.sh` — slice gates.
- `tests/` — instrument and gate tests.
- `DECISIONS.md` `EXPERIMENT.md` `MASTER.md` `MASTER_v3.md` `PLAN.md`
  `plan.md` `REQUEST.md` `SESSION_HANDOFF.md`
  `wave-convergence-thinking.md` — working docs of the study.

Note: the root-level `DECISIONS.md`, `GOTCHAS.md`, `PLAN.md`,
`prereg.yaml` of this repo are the Pauper Consensus (Pass 2) documents —
do not confuse them with the same-named files here.
