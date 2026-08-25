# SPEC: wave-consensus

Status: DRAFT v0.9, 2026-08-25. Not locked. Lock happens at Phase 0 by writing
`prereg.yaml` and git-tagging it before any training or generation.

## 1. What this is

An independent, pre-registered experiment testing a sharpened form of cross-model
proposition-level consensus. The source study (Mannings & Marzuki 2026, *The Flip
Was in the Instrument*) showed that agreement across models on individual
propositions predicts proposition truth, under a frozen gate, on two cycles. Its
instrument, however, died at the free-text to proposition boundary: the NLI
alignment layer scored 0 of 607 negative-polarity propositions, the extractor had
no measured precision or recall, the M=3 Dawid-Skene fit sat at the
identifiability edge, and the error-decorrelation mechanism was never measured at
the proposition level.

wave-consensus moves the experiment to the other side of that boundary. Each
proposer is fine-tuned on the corpus to emit a strict set of structured atomic
propositions over the domain vocabulary. Voting becomes exact match, the alignment
layer disappears, and the aggregation machinery (which the source study validated
as robust) runs on clean input.

## 2. Why this form (link to the critique)

- Kills the alignment blind spot (C2): structured output makes polarity explicit,
  so no polarity class can be silently dropped.
- Upgrades the estimator (C7): a small shared label space is the classical
  Dawid-Skene regime; M=3 to 5 over it is comfortably identified.
- Removes unvalidated stages (C8): no NLI, no embedding retrieval; the pipeline's
  first stage is a parser against a frozen contract.
- Tests the mechanism the source study never did (C1): leave-one-proposer-out and
  proposition-level error correlation, so "consensus" is separated from "the
  oracle is in the panel".
- Matches the product configuration (C14): cheap fine-tuned proposers around an
  untouched expensive solver.

## 3. Research questions

- RQ1: Does consensus among corpus-fine-tuned structured proposers predict
  proposition truth beyond (a) the base rate, (b) the single best proposer, and
  (c) zero-shot models on the same corpus?
- RQ2: Is the signal present or absent when the strongest proposer is removed
  (consensus vs oracle)?
- RQ3: Is there error decorrelation at the proposition level across proposer
  families (E0, proposition level)?
- RQ4 (phase 2, optional): How does the consensus advantage vary as proposer
  competence rises through the 70, 80, 90 percent regimes?

## 4. Corpus and ground truth

- Corpus (phase 1): ProofWriter, `hitachi-nlp/proofwriter_processed_OWA`, the same
  dataset as the source study, for comparability. Pinned by SHA-255.
- Split: **theory-level**, not item-level. Whole theories are assigned to one
  role (train, calibration, test) so no near-duplicate propositions straddle a
  boundary. Frozen seed recorded in `prereg.yaml`.
- Ground truth: proposition truth values derived from the theory closure, the same
  construction as the source study. A 50-item human audit of truth labels runs at
  Phase 1 and is logged (closes the "unvalidated oracle" gap).
- Census: the corpus manifest records counts of y=0 propositions by polarity and
  by split role. Go/no-go: the held-out test set must hold at least 60 scorable
  false propositions. If it does not, the corpus selection is widened before the
  registration locks (the source study's lesson D2: a corpus that cannot contain
  falsehoods cannot measure a method that could be wrong).

## 5. Proposers

- Panel: 3 to 5 base models from **distinct families**, each in the 1B to 8B
  class (cheap by design), served locally on hydrogen where they fit and via
  OpenRouter otherwise. A sixth slot may hold the local 27B model as a
  "strong proposer" reference. Family list frozen at Phase 0.
- Fine-tuning: LoRA/QLoRA, each proposer on a **disjoint slice** of the training
  theories, with a different seed and, where possible, a different recipe, to keep
  error correlation low. Target competence: 75 to 92 percent proposition-level
  accuracy on the calibration split. Saturation (above 95 percent) is a failure
  of the design and triggers a re-tune (oracle re-emergence).
- Memorization check: train/calibration accuracy gap reported per proposer. A gap
  above 10 points is logged in DECISIONS.md and interpreted as memorization risk.
- Output contract (frozen at Phase 0, exact grammar in `prereg.yaml`):
  one proposition per line, canonical statement over the theory vocabulary,
  explicit polarity marker, e.g.
  `P: <canonical statement>` or `N: <canonical statement>`.
  Parse failures are logged as missing observations with a parse rate reported
  per proposer (target: 100 percent by construction).
- Weights frozen and content-hashed after training; hashes recorded in the
  registration artifact.

## 6. Measurement

- Vote matrix by **exact match** of canonical propositions. No NLI, no embeddings.
  Silence is an explicit cell state, not a missing value.
- Arms:
  - WCT-U: uniform signed support (count distinct affirm minus distinct deny).
  - WCT-EM: three-state Dawid-Skene, unsupervised (the registered primary arm).
  - Ablation, claim-instance counting (verbosity-weighted; expected to fail).
  - Ablation, single best proposer (calibrated), the oracle reference.
  - Base rate (trivial predictor), the floor.
- Baseline: logistic regression on depth, coverage, verbosity, length, fitted on
  the calibration split only, the same covariate set as the source study. The
  feature list is pinned in `prereg.yaml` and stated to be model-free.
- Calibration: Platt map, sigmoid(a*s + b), fitted on the calibration split by
  exact MLI. Temperature kept as an ablation. The calibration map and the
  baseline have the same degrees of freedom (the source study's lesson D1).
- Primary: held-out item-stratified delta log-loss, WCT-EM vs the covariate
  baseline, threshold delta = 0.02 nats, item-block bootstrap, 2000 resamples.
- Co-primary (rank, the robust part): within-item AUROC, WCT-EM vs a ranked
  covariate baseline.
- Null: within-item truth permutations, 10,000 permutations (the source study
  floored at 1,000 and reported the floor everywhere; we do not).
- Decision rule (the C11 fix, explicit): go requires the point estimate at or
  above delta **and** the bootstrap interval excluding zero. If the point clears
  delta but the bound does not, the verdict is INCONCLUSIVE. Degenerate intervals
  (zero width) are reported, never silently interpreted.

## 7. Registered predictions (frozen at lock, falsifiable)

- P1: WCT-EM primary returns GO on the fine-tuned panel.
- P2: the leave-one-proposer-out primary remains GO for every single member
  removed (consensus, not oracle).
- P3: claim-instance counting AUROC is below 0.65 on the test split (the
  one-vote-per-source invariant holds).
- P4: the delta log-loss advantage over the base rate on the fine-tuned panel is
  at least as large as the corresponding advantage of the zero-shot panel on the
  same items (fine-tuning does not destroy the signal).

Each prediction carries a power note: the tolerance is set from observed bin
noise where a bin is involved, not from aspiration (the source study's lesson C9).

## 8. Baselines, in order of stringency

1. Trivial base rate (floor).
2. Single best proposer, calibrated (the oracle reference).
3. Zero-shot panel on the same items, regenerated or from the source cache if
   obtainable (comparability).
4. Covariate logistic regression (the registered bar).
5. Optional: a small supervised verifier trained on the calibration labels
   (the strong-baseline the source study omitted).

## 9. Registration discipline

- `prereg.yaml` written, committed, and git-tagged (`prereg-waveconsensus-v1`)
  before any fine-tuning or generation it covers.
- Implementations-are-the-registration clause, plus the explicit decision-rule
  boundary clause from section 6.
- Generation cache content-hashed and immutable; analysis re-runs at zero
  inference cost.
- `DECISIONS.md` and `GOTCHAS.md` kept current; they are part of the record.
- Spend caps: hard cumulative per-proposer call caps, persisted across re-runs.

## 10. Deliverables

- A repository in which every reported number is reproducible from the committed
  cache by tagged analysis code.
- A v1 report: results tables, each prediction confirmed or failed at equal
  prominence, the invariants, the post-hoc diagnostics labelled as such.
- An independent-recomputation note: this implementation is a separate lineage
  from the source study; where we reuse its items or cache, we cross-check its
  published numbers (the fix for the single-implementation-lineage gap).
- A decision to preprint, made with the co-designers.

## 11. Risks and mitigations

- Memorization (proposers do lookup, not reasoning): theory-level split,
  train/calibration gap reported per proposer.
- Correlated errors from shared fine-tuning: disjoint slices, different seeds and
  recipes, E0 measured at the proposition level.
- Oracle re-emergence: competence target 75 to 92 percent, leave-one-out as a
  registered prediction (P2).
- Small panel: 3 to 5 distinct families, strong-proposer slot.
- Budget: proposers are 1B to 8B; fine-tuning fits on hydrogen's RTX 5000 Pro
  48GB. Call caps persist.
