# Request: Slice 4 — cycle-3 registration

Workstream `20260828-181135-0d060fc4`, slice 4 of 4. Master: `MASTER_v3.md` §"Slice 4".
Prior: `e63f946` (corrected instrument), `87bfb7f` (paper corrections),
`32fead0` + `1bf61ba` (measured availability).

## Thoughts / context

> Finish slice 3 and move forward

Cycle 3 registers the contrast cycles 1 and 2 never tested. Slice 1 built the registered
arm nobody had implemented and found the panel beats its calibration-selected best single
source by only +0.0448 to +0.0887 nats on three of four panel-cycles, and inconclusively on
the fourth. Slice 2 corrected the paper to say so. The open question is whether that margin
GROWS with the number of independent sources — which is what error decorrelation predicts —
or does not, which would be evidence against the premise this literature rests on.

Slice 3 measured what can be registered: six reachable families, margin +1 over the five
required, so M=5 is registrable under the rule recorded 2026-08-30. It also established
three things this registration must absorb:

- **Neither cycle-2 panel survives.** Panel A is broken by `laguna`, panel B by `gptoss`
  and `gemma`. Cycle 3 cannot continue either; it pins fresh ids.
- **Three families are reachable only via ids the registration does not pin** (google,
  openai, poolside), because `:free` is a tier suffix and those tiers were withdrawn or
  rate-limited. Cycle 3 pins the working ids directly.
- **Only one endpoint has a registered expected echo.** For the rest an upstream
  substitution would pass unnoticed, so cycle 3 must pin one per panel member.

Human decision, 2026-08-30: cycle 3 pins ALL SIX families. The dose-response is drawn as
NESTED subsets of a fixed ordering (M=3 ⊂ M=4 ⊂ M=5) so a change in the margin is
attributable to ADDING a source rather than to swapping panels — the confound cycle 1
demonstrated when two same-size panels returned opposite verdicts. The sixth family is the
declared margin: pinned and smoke-tested, outside the primary M=5 panel, so one
disappearance is absorbed by documented promotion rather than an unregistered substitution.

## Constraints

- **No generation.** This slice registers; it does not run cycle 3. Smoke tests to confirm
  the pinned endpoints answer are permitted and are the only egress.
- **The tag precedes the data.** `prereg_v3.yaml` and the analysis driver are committed and
  git-tagged BEFORE any cycle-3 generation exists — the discipline cycle 1 lacked and
  cycle 2 established.
- **δ is set before results exist** and never moved afterwards, derived from slice 1's
  measured margins and recorded with that derivation.
- **The v2 tag stays byte-clean**: no edit or addition under `exp/`, `wct/`, `m0/`.
- `out/v3/`, `out/slice3/` and `out/e1*_summary*.json` stay byte-identical to their
  committed content.
- Free tiers are not pinned where a paid tier exists: slice 3 measured `:free` endpoints
  429ing repeatedly, and a 450-call panel cannot rely on them.

## Non-goals

- Running cycle 3, building its corpus artifacts, or spending on generation.
- Any change to `paper.md`. Slice 2's corrections stand.
- Re-measuring availability. `out/slice3/` is the evidence.
- Claim B, diffusion, or anything else in `EXPERIMENT.md` §5.

## Acceptance criteria

- B1: `prereg_v3.yaml` carrying every field `EXPERIMENT.md` §3.1(4) requires, with the
  registered primary stated as panel vs calibration-selected best single source.
- B2: δ derived from slice 1's measured margins, with the derivation recorded and the value
  frozen. A power calculation against slice 1's observed per-item variance reports the item
  count each of M=3, M=4 and M=5 needs; if the design is underpowered at feasible n, that is
  stated plainly rather than proceeded past.
- B3: Six families pinned with their WORKING ids and tiers, a fixed ordering, the nested
  M=3 ⊂ M=4 ⊂ M=5 subsets named explicitly, and the sixth family declared as margin with
  its promotion rule written in advance.
- B4: An expected echo pinned per panel member, so the exact-pinned-id rule has an explicit
  target rather than a default; the local endpoint additionally pinned by weights.
- B5: Corpus pinned by SHA-256, capable of containing falsehoods, with the projected count
  of scored positive-polarity negatives stated as a projection and explicitly not a gate.
- B6: Falsifiable predictions with adjudication rules, including the dose-response the
  decorrelation premise implies and what result would refute it.
- B7: Paid tiers priced for the registered call volume, from slice 3's measured rates, with
  a hard per-panel cap persisted across re-runs.
- B8: The analysis driver committed before generation, so the implementations are the
  registration.
- B9: A git tag created before any cycle-3 generation exists, with the byte-clean and
  evidence-immutability properties asserted at tag time.
- B10: One command runs the whole slice and exits non-zero on any failed assertion; its
  EXIT CODE is the pass signal.
- B11: `DECISIONS.md` entry derived from the emitted registration, fingerprinted so a stale
  entry is detected.

## Open questions

- OQ1: SUPERSEDED (human, 2026-08-30, later the same day). Cycle 3's corpus is 9,805
  ProofWriter items — depth-3 and depth-5, all three splits — pinned by SHA-256
  `63ca8131b43b5c81681deed8bc705c6c2f6f1c56fdac929d9b1efb7584e504a1`. The earlier
  resolution below was made when CPU NLI at 30 pairs/sec made anything larger infeasible;
  it explicitly deferred the question to "once a CUDA torch build is available". That
  build now exists and NLI runs at 2,500 pairs/sec fp32 on GPU, so the constraint that
  forced 150 items is gone and the human chose to scale. Comparability is PRESERVED, not
  traded away: cycle 2's 150 items are a verified COMPLETE SUBSET of the 9,805. The reuse
  disclosure below still applies to that subset. What scaling buys is power: the M=3→M=5
  dose-response increment — the thing cycle 3 exists to measure — is detectable to
  ~0.010 nats at n=9,805 versus ~0.08 nats at n=150. Consequences that must flow through
  the registration: call volume 58,830, cost ~$121, NLI ~6.3 h. NOTE: the ~0.010 figure
  here was a PRE-ARTIFACT estimate from a crude n*delta^2 basis. The registration derives
  the floor from slice 1's measured per-item SDs and reports 0.0071 nats; where the two
  differ the DERIVED value governs, and `exp3/validate_v3.py` recomputes it. NOTE the prior figure of
  "2,353 items" recorded in DECISIONS.md was a raw parquet ROW count; the filtered item
  count of that set was 2,277. Superseded text follows.
- OQ1 (superseded text): Cycle 3 REUSES cycle 2's corpus — the 150
  negation-family ProofWriter items with depth-5 enrichment, pinned by the same SHA-256.
  Comparability with the registered `+0.220` / `+0.272` results is worth more than
  independence from a cycle whose panels no longer exist, and the corpus itself was never
  the thing that failed. The reuse must be DISCLOSED in the registration, along with what
  it does and does not buy: the item set is shared, so cycle 3's dose-response is not
  independent evidence about this corpus, only about panel size on it.
- OQ2: RESOLVED (human, 2026-08-30). qwen is pinned as the LOCAL `qwen3.8-27b` — the
  registered weights (`Qwen3.8-27B-Q4_K_M`, pinned by model_path and n_params) — with
  `qwen/qwen3.8-27b` on OpenRouter as a DECLARED FALLBACK, registered in advance rather
  than substituted mid-run. The fallback's promotion rule, and the fact that it is the
  provider's own build rather than the registered quantised weights, are written into the
  registration so a switch is a documented event and not an unregistered substitution.
  This is the same discipline the sixth-family margin uses.

- OQ3: RESOLVED (human, 2026-08-30). The registration tag is `prereg-v3-2026-08-30`,
  following the v2 convention (`prereg-v2-2026-08-16`).
- OQ4: RESOLVED (human, 2026-08-30). The generation budget implied by the 9,805-item
  corpus — 58,830 calls, ~$121 at slice 3's measured paid-tier rates — is authorised as a
  registered CAP. The cap is registered in this slice; the spend happens in a later run.
