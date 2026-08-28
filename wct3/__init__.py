"""Corrected instrument (slice 1, workstream 20260828-181135-0d060fc4).

Parallel to `wct/`, which is FROZEN under tag `prereg-v2-2026-08-16`. Nothing
here edits or adds to `wct/`, `exp/` or `m0/`; the frozen modules are imported.

Three defects are corrected, none of which change a registered cycle-1 or
cycle-2 verdict:

  D1  `single_best_calibration_selected` — a registered arm (`prereg.yaml:166`,
      `plan.md:488`, simulated at `m0/simulate.py:75`) that no analysis driver
      ever implemented.
  D2  the `uncapped` M6 ablation never saw a claim instance: `align_anchored`
      collapses to one observation per (agent, pid) BEFORE `exp/e1.py:76-78`
      counts them, so `n_claims == n_emitting` identically. `wct3.align`
      retains the pre-collapse assignments so the real count exists.
  D3  `exp/e1_v2.py:189` binds the alignment audit and discards it.

Every number produced here over a cycle-1 or cycle-2 cache is POST-HOC. It
diagnoses those cycles; it never restates their registered verdicts.
"""
