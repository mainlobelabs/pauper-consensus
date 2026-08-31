# Fixture: planned revised passages (P1 unit tests only)

P1 runs before P2 writes the real text, so its tests parse this instead of paper.md.
It deliberately contains one figure of every class the completeness rule recognises.

## Correction notice (2026-08-29)

Draft v3's §6.1 reported AUROC 0.502-0.554 for cycle 1. That figure is correct; it is the
frozen `uncapped` arm (see exp/e1.py:76-78). The corrected value under the capping x
polarity separation is 0.5069 on c1_local.

## 6.1

Draft v3 reported: "Claim-instance counting: AUROC 0.502–0.554 (cycle 1), 0.569–0.606
(cycle 2, primary instrument). Unique-source support: 0.891–1.000 (cycle 1), 0.931–0.939
(cycle 2, primary instrument)." Those numbers are correct readings of the frozen arms.

| panel | capped+signed | capped+unsigned | uncapped+signed | uncapped+unsigned |
|---|---|---|---|---|
| c1_local | 0.9001 | 0.5069 | 0.9664 | 0.4484 |
| c1_openrouter | 0.9911 | 0.5239 | 0.9875 | 0.4825 |
| c2_panelA | 0.9353 | 0.6063 | 0.9456 | 0.5884 |
| c2_panelB | 0.9323 | 0.5686 | 0.9530 | 0.5705 |

## 8

`single_best_calibration_selected` (prereg.yaml:166, plan.md:488) was registered and never
implemented. The panel's margin over it is +0.0448 on c1_local (go) and +0.0329 on
c2_panelB (inconclusive).

| panel | map | selected source | panel (WCT-EM) over that source | decision |
|---|---|---|---|---|
| c1_local | temperature | qwen | +0.0448 [+0.0117, +0.0787] | **go** |
| c1_openrouter | temperature | nemotron | +0.0887 [+0.0455, +0.1421] | **go** |
| c2_panelA | platt | glm | +0.0762 [+0.0465, +0.1068] | **go** |
| c2_panelB | platt | gptoss | +0.0329 [-0.0109, +0.0703] | **inconclusive** |
