# Request: Slice 2 — paper corrections from slice 1's findings

Workstream `20260828-181135-0d060fc4`, slice 2 of 4. Master: `MASTER_v3.md`.
Evidence: `out/v3/reanalysis_*.json` (committed in e63f946) and the `V3 SLICE 1 OUTCOME`
entry in `DECISIONS.md`.

## Thoughts / context

> Do all three

Rescoped from B10 and moved ahead of the registration by human decision, 2026-08-29: slice
1's D2 result REFUTES `paper.md` §6.1 rather than qualifying it, the correction costs
nothing (committed artifacts, zero inference), and a draft carrying two named authors
should not sit on a claim its own instrument contradicts while an expensive registration is
prepared.

The three passages at issue, verbatim:

- L32 (contribution 4): "A replication, across both cycles and all panels, of the
  one-vote-per-source result: claim-instance counting reaches AUROC 0.502-0.606 while
  unique-source support reaches 0.891-1.000."
- L164 (§6.1): "**One vote per source, or nothing.** Claim-instance counting: AUROC
  0.502-0.554 (cycle 1), 0.569-0.606 (cycle 2 ...). Unique-source support: 0.891-1.000 ...
  Whatever agreement measures, it is who asserts a proposition, not how much text asserts it."
- L200 (§9): "the one finding that needed no second cycle, because it never wavered:
  agreement carries information exactly when each source gets one vote. Count text instead
  of sources, and there is nothing there."

None of these measured what they claim. `align_anchored` collapses to one observation per
(agent, pid) BEFORE `exp/e1.py:76-78` counts, so the frozen `uncapped` arm scores
`n_claims`, which equals `n_emitting` identically: capped and UNSIGNED. The comparison
varies polarity, not capping. Measured separately (raw AUROC, `out/v3/`):

| panel | capped+signed | capped+unsigned | uncapped+signed | uncapped+unsigned |
|---|---|---|---|---|
| c1_local | 0.9001 | 0.5069 | 0.9664 | 0.4484 |
| c1_openrouter | 0.9911 | 0.5239 | 0.9875 | 0.4825 |
| c2_panelA | 0.9353 | 0.6063 | 0.9456 | 0.5884 |
| c2_panelB | 0.9323 | 0.5686 | 0.9530 | 0.5705 |

Uncapped matches or beats capped on 4 of 4 panels. The effect is polarity.

Two further corrections follow from slice 1: the registered arm
`single_best_calibration_selected` was never implemented in either cycle, so nothing in the
paper distinguishes cross-model agreement from one good model; and the panel's margin over
the source its own calibration split selects is +0.045 to +0.089, inconclusive on c2_panelB.

## Constraints

- **No registered verdict is restated or altered.** Cycles 1 and 2 stand as published. Every
  number added here is POST-HOC and labelled so, sourced to `out/v3/`.
- **No inference.** Corrections read committed artifacts only.
- **The v2 tag stays byte-clean**: no edit or addition under `exp/`, `wct/`, `m0/`.
- Every figure quoted must be machine-checked against `out/v3/`, not transcribed by hand.
- `paper.md` is the only prose file whose CONTENT this slice corrects. Also edited,
  and declared here rather than silently: `MASTER_v3.md` (restructured into slices
  2/3/4 under the human decision of 2026-08-29, before this run started),
  `REQUEST.md` and `PLAN.md` (this slice's own scoping), and `DECISIONS.md`
  (decision entries plus one slice-outcome entry).

## Non-goals

- Cycle-3 registration, corpus, panels, delta (slice 4); availability measurement (slice 3).
- Re-running any analysis; `out/v3/` is the evidence and is already committed.
- Rewriting sections the findings do not touch. §§6.2-6.4, 7, and the cycle-1/cycle-2
  narrative stand except where they cite a corrected figure.
- Any claim about cycle 3's outcome.

## Acceptance criteria

- C1: §6.1 and contribution 4 restated as the polarity result the corrected instrument
  measures, identifying the frozen `uncapped` arm as capped-and-unsigned with the mechanism
  (`align_anchored` collapses per (agent,pid) before `exp/e1.py:76-78` counts), and
  reporting the capping x polarity 2x2 in full at raw AUROC.
- C2: §8 discloses that `single_best_calibration_selected` (`prereg.yaml:166`,
  `plan.md:488`) was registered and never implemented in either cycle.
- C3: Slice 1's single-source contrast reported at the prominence the registered failures
  get, including that c2_panelB is inconclusive under the frozen decision rule.
- C4: Every new number labelled POST-HOC and sourced to `out/v3/`.
- C5: The D3 disclosure recorded: cycle 2's mapper could not be audited from cache because
  its own driver discarded the audit; the probe was computed under a recorded amendment and
  scores 0.9721 against cycle 1's 0.9724.
- C6: A correction notice at the head of the paper naming what changed from draft v3 and
  why, leaving the earlier draft's claims visible rather than silently replaced.
- C7: A script checks every figure quoted in the revised sections against `out/v3/` and
  exits non-zero on any mismatch; it runs in the slice gate.
- C8: The v2 tag remains byte-clean, asserted in the gate.

## Open questions

- OQ1: RESOLVED (human, 2026-08-29). §9 closes on the SINGLE-SOURCE finding, not the
  corrected polarity result. Rationale: it is the more consequential correction, because it
  bears on whether the paper's central premise was ever tested at all, and ending there
  makes the conclusion carry the paper's biggest open question rather than bury it.
- OQ2: RESOLVED (human, 2026-08-29). The correction notice is a dated block at the head of
  `paper.md`, not a separate file: unmissable, and it matches the project's own precedent of
  superseding records that leave the original visible (`DECISIONS.md`, 2026-08-15).
