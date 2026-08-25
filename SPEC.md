# SPEC: wave-consensus

Status: DRAFT v0.11, 2026-08-25. Not locked. Lock happens at Phase 0 by writing
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

wave-consensus moves the experiment to the other side of that boundary, and adds
a second axis the source study never had: a strong solver that is never
fine-tuned, whose trace is verified by a jury of cheap fine-tuned proposers.

Scope: this track is a pilot, and it says so on purpose. It de-risks the locked
run on a real-world corpus; it does not replace the microworld. The source
study's ProofWriter microworld is kept as the controlled case study and re-run
with the same structured instrument as this track, so the two tracks compare
conditions, not pipelines.

Two design choices do the work:

- **Structured proposers.** Each jury member is LoRA fine-tuned to emit a strict
  voting block over a fixed proposition list. Voting becomes exact match on
  proposition IDs; the alignment layer disappears.
- **Cutoff-gap articles.** Each test item is a short news-style article about a
  real-world event that post-dates the training cutoff of every model in the
  panel. A cutoff is not a wall, so the design does not assume it: the cutoff
  gap buys the property that a confident claim has to come from the text, and
  that property is verified per item (section 4) by running each model on the
  questions without the article. Falsehoods are designed into the item, not
  left to chance: each article contains claims it supports, claims it
  contradicts, and, via in-passing mentions, claims it is silent on. The silent
  class is where real hallucinations live, and it is the kind of negative the
  microworld could not measure.

## 2. Why this form (link to the critique)

- Kills the alignment blind spot (C2): voting is by exact match on proposition
  IDs with explicit polarity, so no polarity class can be silently dropped.
- Upgrades the estimator (C7): a small shared label space is the classical
  Dawid-Skene regime; 5 proposers over it is comfortably identified.
- Removes unvalidated stages (C8): no NLI, no embedding retrieval; the pipeline's
  first stage is a parser against a frozen contract.
- Tests the mechanism the source study never did (C1): leave-one-proposer-out and
  proposition-level error correlation, so "consensus" is separated from "the
  oracle is in the panel".
- Matches the product configuration (C14): a cheap fine-tuned jury around an
  untouched expensive solver, measured on the actual configuration.
- Kills the parametric-recall confound: the cutoff gap forces text grounding, so
  a correct answer is evidence of extraction, not memory.
- Attacks demo land (W1): the domain is real-world news with real
  hallucination structure, not a synthetic microworld.

## 3. Research questions

- RQ1: Does consensus among corpus-fine-tuned structured proposers predict a
  proposition's truth relative to the article beyond (a) the base rate, (b) the
  single best proposer, and (c) zero-shot 4B models on the same articles?
- RQ2: Is the signal present or absent when the strongest proposer is removed
  (consensus vs oracle)?
- RQ3: Is there error decorrelation at the proposition level across proposer
  families (E0, proposition level)?
- RQ4: Does the jury's consensus flag the strong solver's false claims at a
  higher rate than its true claims, and does solver-plus-jury beat solver alone
  on claim accuracy? This is the product question.
- RQ5 (optional, phase 2): How does the consensus advantage vary as proposer
  competence rises through the 70, 80, 90 percent regimes?

## 4. Corpus and ground truth

- Corpus: 30 authored news-style articles (LLM-assisted drafting, human-checked),
  each centered on a real-world topic **post-dating the training cutoff of every
  panel model**. Each article contains at least one **in-passing mention** of a
  secondary fact, so that some seeded claims are true only in the sense of being
  mentioned, and some questions about them have no answer in the text. Topic
  list frozen at Phase 0. Worked example: an article about SynthID watermarking
  that mentions in passing "Claude recently implemented fingerprinting" without
  a date; the seeded question "when did Claude implement fingerprinting?" then
  has the correct answer "not stated in the article".
- The text is the oracle: a proposition's truth is defined by what the article
  states, not by what is actually true. A single wrong in-passing mention
  silently relabels a batch of claims, so every real-world fact in every
  article (named entities, features, dates) is fact-checked against the web
  before the corpus locks.
- Proposition pool: 40 propositions per article, seeded by 20 questions. Each
  question generates its true variant, false variants, and negative-polarity
  variants. Target mix per article: roughly 50 percent entailed (true), 25
  percent contradicted, 25 percent unstated; both polarities within each class.
  Difficulty is tuned on the zero-shot baseline (Phase 3) so that base 4B
  accuracy lands in the 80 to 90 percent band, not saturation.
- Ground truth semantics (the C12 fix, explicit): each proposition is labelled
  by the author with a frozen rubric as **ENTAIL** (the article supports it),
  **CONTRADICT** (the article states the opposite), or **UNSPECIFIED** (the
  article is silent). The gate's binary target is ENTAIL vs non-ENTAIL: a
  correct vote affirms exactly the ENTAIL propositions. UNSPECIFIED is the
  hallucination class: affirming an UNSPECIFIED proposition is a false claim of
  the kind a verification layer exists to catch.
- Split: **article-level**, not proposition-level. Whole articles are assigned
  to one role (10 train, 10 calibration, 10 test) so no proposition from a seen
  article leaks into an unseen one. Frozen seed recorded in `prereg.yaml`.
- Contamination check (validates the cutoff assumption, per item): for every
  test article, each base 4B model is run on the seeded questions **without the
  article** (parametric only) and **with the article**. Any question where any
  model answers above chance without the article is flagged as parametric.
  Flagged items are re-selected or labelled, and the flags are logged before the
  fine-tuned test run is seen.
- Census and go/no-go: the manifest records label counts by class, polarity,
  and split role. The held-out test set must hold at least 60 non-ENTAIL
  propositions. If it does not, the pool is widened before the registration
  locks (the source study's lesson D2: a corpus that cannot contain falsehoods
  cannot measure a method that could be wrong).
- Label audit: the author is the single labeler (disclosed). A 10 percent sample
  of labels is re-checked against the rubric at Phase 1 and the agreement rate
  is logged (closes the "unvalidated oracle" gap in the form this design
  allows).

## 5. Panel: solver and proposers

- Solver: **qwen3.8-27B**, local on hydrogen, zero-shot, never fine-tuned. The
  solver reads each test article plus its 20 questions and returns a natural
  chain-of-thought trace with final answers. Its claims are what gets verified.
  This is the product frame: the customer's frontier model is never migrated or
  tuned.
- Jury: **5 base models in the 4B class from distinct families** (family list
  frozen at Phase 0), served locally on hydrogen, none of them sharing lineage
  with the solver's family, each LoRA fine-tuned on a **disjoint slice** of the
  training articles with a different seed and, where possible, a different
  recipe, to keep error correlation low. Target
  competence: 75 to 92 percent proposition-level accuracy on the calibration
  articles. Saturation (above 95 percent) is a design failure and triggers a
  re-tune (oracle re-emergence).
- Registered arm (cheap, always run): the solver also votes on the pool as a
  sixth, un-tuned proposer, so the oracle-vs-consensus decomposition includes
  the strong model.
- Memorization check: train/calibration accuracy gap reported per proposer. A
  gap above 10 points is logged in DECISIONS.md and read as memorization risk.
- Weights frozen and content-hashed after training; hashes recorded in the
  registration artifact.

## 6. Task and output contract (frozen at Phase 0, exact grammar in `prereg.yaml`)

- Jury task: article plus the full 40-proposition list in. Out: an optional
  THINK block, then one vote line per proposition, `P{id}: AFFIRM|DENY`. Strict
  on the vote block, unconstrained on the THINK block (free thinking is what
  keeps the five families from making identical mistakes).
- CoT ablation, registered: the jury is trained in **two variants** on the same
  data, votes-only and think-then-vote. Both are run on the test articles; the
  comparison is reported, not predicted. Ten adapters total (2 variants x 5
  families).
- Solver task: article plus its 20 questions in, free-form trace and answers
  out. No contract. Solver claims are matched to pool propositions by the
  author's seed mapping (each question's answer maps to its seeded
  propositions); unmatched claims are logged, not scored.
- Parse failures are logged as missing observations; parse rate reported per
  proposer (target: 100 percent by construction) and per solver question.

## 7. Measurement

- Vote matrix by **exact match** on proposition IDs, jury x pool. Silence is an
  explicit cell state, not a missing value.
- Arms:
  - WCT-U: uniform signed support (distinct affirm minus distinct deny).
  - WCT-EM: three-state Dawid-Skene, unsupervised (the registered primary arm).
  - Ablation, claim-instance counting (verbosity-weighted; expected to fail).
  - Ablation, single best proposer (calibrated), the oracle reference.
  - Base rate (trivial predictor), the floor.
- Baseline: logistic regression on article length, pool position, claim length,
  polarity, and question type, fitted on the calibration split only. The feature
  list is pinned in `prereg.yaml` and stated to be model-free. The registered
  bar is this covariate baseline; a signal that only beats the base rate does
  not pass.
- Task difficulty is a known difference from the source study and is stated in
  the report: the label mix is 50 percent ENTAIL, the source corpus was about
  95 percent true, so this task is intrinsically easier and a positive result
  is partly task difficulty, not transfer.
- E0: pairwise proposition-level residual error correlation across voters,
  reported as a number. "Independent enough" is a measurement, not an
  assumption.
- Calibration: Platt map, sigmoid(a*s + b), fitted on the calibration split by
  exact MLE. Temperature kept as an ablation. The calibration map and the
  baseline have the same degrees of freedom (the source study's lesson D1).
- Primary: held-out article-block delta log-loss, WCT-EM vs the covariate
  baseline, threshold delta = 0.02 nats, article-block bootstrap, 2000 resamples.
- Co-primary (rank, the robust part): within-article AUROC, WCT-EM vs a ranked
  covariate baseline.
- Null: within-article truth permutations, 10,000 permutations (the source study
  floored at 1,000 and reported the floor everywhere; we do not).
- Solver-value metric (RQ4): over the solver's pool-matched claims on test
  articles, the jury consensus score separates the solver's ENTAIL claims from
  its non-ENTAIL claims. Reported: flag precision, flag recall, and the change
  in claim accuracy from solver alone to solver-plus-jury (low-consensus claims
  dropped). The solver's confidence is the mean token probability of the answer
  span, frozen in `prereg.yaml`, so the comparison is against a measured
  quantity, not a verbalized self-report.
- Decision rule (the C11 fix, explicit): go requires the point estimate at or
  above delta **and** the bootstrap interval excluding zero. If the point clears
  delta but the bound does not, the verdict is INCONCLUSIVE. Degenerate intervals
  (zero width) are reported, never silently interpreted.

## 8. Registered predictions (frozen at lock, falsifiable)

- P1: WCT-EM primary returns GO on the fine-tuned jury.
- P2: the leave-one-proposer-out primary remains GO with each voter removed in
  turn, not just the strongest (removing the winner first would be post-hoc
  winner selection), including the solver-as-proposer (consensus, not oracle).
- P3: claim-instance counting AUROC is below 0.65 on the test split (the
  one-vote-per-source invariant holds).
- P4: the delta log-loss advantage over the base rate on the fine-tuned jury is
  at least as large as the corresponding advantage of the zero-shot 4B jury on
  the same articles (fine-tuning does not destroy the signal).
- P5: the jury's consensus flags a strictly larger share of the solver's
  non-ENTAIL claims than of its ENTAIL claims on test articles (the verification
  layer catches the solver's hallucinations, not its facts).

Each prediction carries a power note: the tolerance is set from observed bin
noise where a bin is involved, not from aspiration (the source study's lesson
C9). P5's power note requires the test articles to yield at least 100
pool-matched solver claims of each class; if not, P5 is reported descriptive
only and the article count is raised before the next lock.

## 9. Baselines, in order of stringency

1. Trivial base rate (floor).
2. Single best proposer, calibrated (the oracle reference).
3. Zero-shot 4B jury on the same articles (comparability and the P4 arm).
4. Covariate logistic regression (the registered bar).
5. Optional: a small supervised verifier trained on the calibration labels
   (the strong-baseline the source study omitted).
6. Contamination runs (no-article, with-article) are validity checks, not
   baselines; they are logged in the manifest before the test run is seen.

## 10. Registration discipline

- `prereg.yaml` written, committed, and git-tagged (`prereg-waveconsensus-v1`)
  before any fine-tuning or generation it covers. The topic list, the 30
  articles, the proposition pools, and the labels are content-hashed into the
  registration artifact: the corpus is frozen before the jury is trained. A
  flipped result cannot be explained by post-hoc changes to the instrument;
  that is what the freeze buys. It does not fix a flawed instrument, and it
  freezes the single-labeler bias along with everything else.
- Implementations-are-the-registration clause, plus the explicit decision-rule
  boundary clause from section 7.
- Generation cache content-hashed and immutable; analysis re-runs at zero
  inference cost.
- `DECISIONS.md` and `GOTCHAS.md` kept current; they are part of the record.
- Spend caps: hard cumulative per-model call caps, persisted across re-runs.

## 11. Deliverables

- A repository in which every reported number is reproducible from the committed
  cache by tagged analysis code.
- A v1 report: results tables, each prediction confirmed or failed at equal
  prominence, the invariants, the post-hoc diagnostics labelled as such.
- A solver-verification section: the RQ4 numbers, the worked example (the
  in-passing mention, the solver's hallucinated date, the jury's flag).
- An independent-recomputation note: this implementation is a separate lineage
  from the source study; where artifacts overlap, we cross-check its published
  numbers (the fix for the single-implementation-lineage gap).
- A decision to preprint, made with the co-designers.

## 12. Risks and mitigations

- Cutoff leakage (the "post-cutoff" topic is actually in some model's training
  data): per-item contamination check with the no-article run, topic re-selection
  on flag, flags logged before the test run.
- Single-labeler bias: frozen rubric with worked examples for the CONTRADICT vs
  UNSPECIFIED boundary, 10 percent re-check, disclosure.
- Memorization (proposers do lookup, not reasoning): article-level split,
  train/calibration gap reported per proposer.
- Correlated errors from shared fine-tuning: disjoint slices, different seeds
  and recipes, E0 measured at the proposition level.
- Oracle re-emergence: competence target 75 to 92 percent, leave-one-out as a
  registered prediction (P2).
- Small corpus (30 articles): framed as the pilot that de-risks the locked run;
  census go/no-go at 60 non-ENTAIL test propositions; scale-up path documented.
- Easier task than the source study (50 percent ENTAIL, not 95 percent): stated
  in the report, not hidden.
- Budget: 4B-class LoRA adapters fit sequentially on hydrogen's RTX 5000 Pro
  48GB; the 27B runs zero-shot. Call caps persist.
