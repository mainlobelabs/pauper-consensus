# PLAN: wave-consensus

Living plan. Update at the end of each working session: current state, next step.

## Purpose

Independently conduct the wave-consensus experiment (see SPEC.md): fine-tune
several small proposers on a corpus with a decidable vocabulary, aggregate one
vote per source under a frozen pre-registered gate, and determine whether
consensus predicts proposition truth beyond base rate, the single best proposer,
and zero-shot panels.

## Current state

- 2026-08-25: project bootstrapped (git, uv, ruff, pytest, passing sample tests).
  SPEC.md drafted at v0.9. PLAN.md created. Nothing locked, nothing trained.

## Next step

Phase 0: spec lock.

## Phases

### Phase 0: spec lock

- [ ] Review and lock SPEC.md (output contract grammar, theory-level split and
      seed, family list, gate, predictions, spend caps).
- [ ] Write `prereg.yaml`; commit and git-tag `prereg-waveconsensus-v1` BEFORE
      any fine-tuning or generation.
- [ ] Create `DECISIONS.md` and `GOTCHAS.md`.
- Verify: tag exists; every registered quantity in the spec has a line in
  `prereg.yaml`; decision-rule boundary clause present.

### Phase 1: corpus and ground truth

- [ ] Pull ProofWriter OWA dataset; pin by SHA-255 in the manifest.
- [ ] Theory-level train/calibration/test split, frozen seed, whole theories per
      role.
- [ ] Proposition table per item from the theory closure.
- [ ] 50-item human audit of truth labels; log agreement.
- [ ] Census: y=0 counts by polarity and split role.
- Go/no-go: held-out test holds at least 60 scorable false propositions. If not,
  widen corpus selection and re-split before Phase 0 artifacts are reused.
- Verify: manifest assertions pass; audit logged; census in the manifest.

### Phase 2: proposer training

- [ ] Select 3 to 5 distinct base families (1B to 8B), smoke-test endpoints.
- [ ] Fine-tune each on a disjoint training-theory slice, structured output
      contract, distinct seeds/recipes.
- [ ] Competence report: calibration accuracy per proposer, train/calibration
      gap (memorization check).
- [ ] Freeze weights; content-hash; record hashes in the registration artifact.
- Verify: every proposer at 75 to 92 percent (not random, not saturated); gaps
  logged in DECISIONS.md.

### Phase 3: generation

- [ ] Generate structured outputs on held-out test theories, all proposers, with
      persisted call caps and attempt ledgers.
- [ ] Parse against the frozen contract; log parse rate per proposer.
- [ ] Content-hash the cache; zero errors in the final cache.
- Verify: cache complete, ledgers within caps, parse rates reported.

### Phase 4: measurement and analysis (tagged code, run unmodified)

- [ ] Vote matrix by exact match; silence as state.
- [ ] Arms: WCT-U, WCT-EM, claim-instance ablation, single best proposer, base
      rate, covariate baseline.
- [ ] Platt calibration per panel, calibration split only.
- [ ] Primary and co-primary gates; within-item permutation null, 10,000 draws.
- [ ] Leave-one-proposer-out, every member (P2).
- [ ] E0: pairwise proposition-level residual error correlation (RQ3).
- [ ] Zero-shot comparability run on the same items (P4).
- Verify: all numbers in `out/*.summary.json`; independent re-run byte-identical;
  label-flip probe run.

### Phase 5: report

- [ ] v1 report: results tables, predictions confirmed/failed at equal
      prominence, invariants, post-hoc diagnostics labelled.
- [ ] Independent-recomputation note vs the source study's published numbers.
- [ ] Review with co-designers; decide on preprint.
- Verify: every number traceable to a committed artifact.

## Standing rules

- One phase's "verify" must pass before the next phase starts.
- Any change to a frozen quantity is a new registration, not an edit.
- Post-hoc analyses are labelled post-hoc, always.
