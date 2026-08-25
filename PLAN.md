# PLAN: wave-consensus

Living plan. Update at the end of each working session: current state, next step.

## Purpose

Independently conduct the wave-consensus experiment (see SPEC.md): author a
cutoff-gap news corpus with designed falsehoods, fine-tune five small 4B
proposers to vote on proposition lists, run an untouched 27B solver on the same
items, and determine whether the jury consensus predicts proposition truth and
flags the solver's false claims beyond base rate, the single best proposer, and
zero-shot 4B models.

## Current state

- 2026-08-25: project bootstrapped (git, uv, ruff, pytest, passing sample tests).
  SPEC.md drafted at v0.9 (ProofWriter pilot).
- 2026-08-25: SPEC.md rewritten at v0.10 after design review with the
  co-designer: authored cutoff-gap news articles replace ProofWriter as the
  primary corpus; qwen3.8-27B solver plus 5x 4B LoRA jury; three-valued labels
  (ENTAIL/CONTRADICT/UNSPECIFIED); in-passing mentions as the UNSPECIFIED
  generator; contamination check; CoT ablation; P5 solver-value prediction.
  Nothing locked, nothing trained, no corpus built.

## Next step

Phase 0: spec lock. Concretely: pick the 30 post-cutoff topics and write
`prereg.yaml` (contract grammar, rubric, family list, split seed, gate,
predictions P1 to P5, spend caps), commit and git-tag before any drafting of
test articles, training, or generation.

## Phases

### Phase 0: spec lock

- [ ] Review and lock SPEC.md v0.10 (output contract grammar, label rubric,
      topic criteria, family list, split and seed, gate, predictions P1 to P5,
      spend caps).
- [ ] Select the 30 post-cutoff topics (must post-date the cutoff of ALL panel
      families; criteria in `prereg.yaml`).
- [ ] Write `prereg.yaml`; commit and git-tag `prereg-waveconsensus-v1` BEFORE
      any article drafting, fine-tuning, or generation.
- Verify: tag exists; every registered quantity in the spec has a line in
  `prereg.yaml`; decision-rule boundary clause present.

### Phase 1: corpus construction and ground truth

- [ ] Draft 30 news-style articles (LLM-assisted, human-checked), each with at
      least one in-passing mention of a secondary fact.
- [ ] 20 seed questions per article; expand each to its true, false, and
      negative-polarity variants into a 40-proposition pool (target mix: 50
      percent ENTAIL, 25 percent CONTRADICT, 25 percent UNSPECIFIED, both
      polarities per class).
- [ ] Label every proposition with the frozen rubric (single labeler, disclosed).
- [ ] 10 percent label re-check; log agreement.
- [ ] Article-level split 10/10/10, frozen seed.
- [ ] Census: label counts by class, polarity, and split role.
- Go/no-go: held-out test holds at least 60 non-ENTAIL propositions. If not,
  widen pools and re-split before anything is trained.
- Verify: manifest assertions pass; audit logged; census in the manifest; corpus
  content-hashed into the registration artifact.

### Phase 2: panel setup and contamination check

- [ ] Select 5 distinct 4B-class base families; smoke-test local serving on
      hydrogen.
- [ ] Smoke-test qwen3.8-27B serving on hydrogen.
- [ ] Contamination check (validity, not baseline): for every TEST article, run
      each base 4B model on the 20 seed questions WITHOUT the article and WITH
      it. Flag any question answered above chance without the article.
- [ ] Log flags before any fine-tuned output exists; re-select or relabel
      flagged items.
- Verify: contamination table in the manifest; flags resolved or documented.

### Phase 3: proposer training

- [ ] LoRA fine-tune each of the 5 families on a DISJOINT slice of the 10
      training articles, distinct seeds, distinct recipes where possible.
- [ ] Two contract variants per family (votes-only, think-then-vote); 10
      adapters total.
- [ ] Competence report: calibration accuracy per adapter, train/calibration
      gap (memorization check).
- [ ] Freeze weights; content-hash; record hashes in the registration artifact.
- Verify: every adapter at 75 to 92 percent (not random, not saturated); gaps
  logged in DECISIONS.md.

### Phase 4: generation

- [ ] Solver run: qwen3.8-27B zero-shot on the 10 test articles, free-form
      traces and answers.
- [ ] Jury votes: 10 adapters x 10 test articles, persisted call caps and
      attempt ledgers.
- [ ] Parse against the frozen contract; log parse rate per adapter and per
      solver question; match solver claims to pool propositions via the seed
      mapping.
- [ ] Content-hash the cache; zero errors in the final cache.
- Verify: cache complete, ledgers within caps, parse rates reported.

### Phase 5: measurement and analysis (tagged code, run unmodified)

- [ ] Vote matrix by exact match on proposition IDs; silence as state.
- [ ] Arms: WCT-U, WCT-EM, claim-instance ablation, single best proposer, base
      rate, covariate baseline.
- [ ] Platt calibration per panel, calibration split only.
- [ ] Primary and co-primary gates; within-article permutation null, 10,000
      draws.
- [ ] Leave-one-proposer-out, every member including the solver-as-proposer
      (P2).
- [ ] E0: pairwise proposition-level residual error correlation (RQ3).
- [ ] Zero-shot 4B comparability run on the same articles (P4).
- [ ] CoT ablation: votes-only vs think-then-vote, same test articles,
      reported not predicted.
- [ ] Solver-value metric (RQ4/P5): flag precision, flag recall, solver alone
      vs solver-plus-jury claim accuracy.
- Verify: all numbers in `out/*.summary.json`; independent re-run byte-identical;
  label-flip probe run.

### Phase 6: report

- [ ] v1 report: results tables, predictions confirmed/failed at equal
      prominence, invariants, post-hoc diagnostics labelled.
- [ ] Solver-verification section with the worked example (in-passing mention,
      solver's hallucinated date, jury's flag).
- [ ] Independent-recomputation note vs the source study's published numbers.
- [ ] Review with co-designers; decide on preprint.
- Verify: every number traceable to a committed artifact.

## Standing rules

- One phase's "verify" must pass before the next phase starts.
- Any change to a frozen quantity is a new registration, not an edit.
- Post-hoc analyses are labelled post-hoc, always.
