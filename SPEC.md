# SPEC: wave-consensus

Status: DRAFT v0.14, 2026-08-25. Not locked. Lock happens at Phase 2 (the
registration freeze) by writing `prereg.yaml` and git-tagging it before any
training or generation. v0.14: primary jury below 4B (1-2B preferred) with a
pre-registered 4B fallback, phase numbers aligned with PLAN. v0.13: the null
control is with-prompt versus without-prompt (the blind mode was dropped), one
call per claim under the co-designer's claim-verification prompt, PASS|FAIL
verdict vocabulary, self-distilled training targets (the LoRA learns only the
wrapper), and the losslessness check on untrained articles.

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

Working vocabulary (the co-designer's courtroom frame, adopted 2026-08-25): the
harness/framework is the **prosecutor**; the qwen3.8-27B solver is the
**defendant**; the fine-tuned proposers are the **jurors**; the article is the
**evidence** (a stand-in for RAG); the solver's answers are the defendant's
**claims**; the prosecution presents each claim with the evidence and instructs
the jurors to base their yes or no solely on the evidence; the gate's output is
the **verdict**. The point of the exercise, in the co-designer's words: the jury
can be "way older models ... or even smaller models", and the point is to
"materially improve the hallucination of significantly better [models] with
cheap shitty models".

Scope: this track is a pilot, and it says so on purpose. It de-risks the locked
run on a real-world corpus; it does not replace the microworld. The source
study's ProofWriter microworld is kept as the controlled case study and re-run
with the same structured instrument as this track, so the two tracks compare
conditions, not pipelines.

Two design choices do the work:

- **Structured proposers.** Each jury member is LoRA fine-tuned to emit a strict
  verdict per claim: `{ answer: PASS|FAIL, reason }`. Voting becomes exact
  match on claim IDs; the alignment layer disappears.
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
- RQ6: How many jurors are required for a meaningful change in the gated
  frontier model? Report the gated false-claim rate at jury size 1 (the single
  best juror), 3, and 5. The 3-juror arm is pre-specified as the three
  families with the highest zero-shot calibration accuracy (deterministic, no
  post-hoc selection). Descriptive: where the marginal gain flattens is an
  operational rule for the minimum viable jury, not a prediction.
- RQ7 (optional, phase 2): Can three 1B models achieve the same? A 3x 1B
  jury, fine-tuned on disjoint slices under the same contract, compared
  against the full 5-juror jury and the frontier self-review control. With
  the primary jury now below 4B, this arm is the size-floor question (how
  small can the jury go). Reported if compute permits, does not gate the
  primary analysis.

## 4. Corpus and ground truth

- Corpus: 30 authored news-style articles, each centered on a real-world topic
  **post-dating the training cutoff of every panel model**. Where a complete
  real news article on the event exists, it is used **verbatim** (source URL
  recorded in the manifest, which makes the fact-check pass cheaper); otherwise
  it is LLM-assisted drafting from web-verified facts. Either way, human-checked
  and fact-checked per the rules below. Each article contains at least one **in-passing mention** of a
  secondary fact, so that some seeded claims are true only in the sense of being
  mentioned, and some questions about them have no answer in the text. Topic
  list frozen at Phase 2. Worked example: an article about SynthID watermarking
  that mentions in passing "Claude recently implemented fingerprinting" without
  a date; the seeded question "when did Claude implement fingerprinting?" then
  has the correct answer "not stated in the article".
- Cutoff verification policy: the 27B solver's cutoff was verified by direct
  probing (cutoff-probe/probes.md, 2026-08-25: blind to the 2026-08-14 to
  2026-08-25 window; self-report not trusted). The jury families' cutoffs are
  established by their documented training windows at model selection (hard
  filter: documented cutoff before 2026-08-14; a family with an unclear or
  later cutoff is not selected; probing only if the documentation is unclear).
  Reason: the jury task is text-conditional, so memory only matters on the
  silent (UNSPECIFIED) class, and a base model's documented training window is
  a reliable claim, unlike the 27B merge's unknown fine-tune data. The per-item
  contamination check below is the verification either way, and it also covers
  fine-tune-data leakage, which the pretraining cutoff cannot.
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
  correct verdict passes exactly the ENTAIL propositions. UNSPECIFIED is the
  hallucination class: passing an UNSPECIFIED proposition is a false claim of
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
- Jury: **5 base models from distinct families, each below 4B** (family list
  frozen at Phase 2), served locally on hydrogen, none of them sharing lineage
  with the solver's family, each LoRA fine-tuned on a **disjoint slice** of the
  training articles with a different seed and, where possible, a different
  recipe, to keep error correlation low. **The primary jury is below 4B, with
  1-2B preferred** (the co-designer's call, 2026-08-25): if the mechanism
  works on models that small, the hypothesis is proven at its strongest form,
  and the cost story is the best it can be. **Pre-registered fallback**: if a
  below-4B candidate family misses the competence band at Phase 4, the jury is
  filled from the 4B class for that family (declared at registration, applied
  family-by-family, the report labels which class ran). Older base models and
  smaller models are permitted and in fact preferred: the exercise is about
  cheap models doing the verification, and an older documented cutoff sits
  further from the topic window. If the below-4B jury passes the pass
  criterion, any 4B run is a descriptive ceiling check (phase 2), not part of
  the proof. Target competence: 75 to 92 percent proposition-level accuracy
  on the calibration articles. Saturation (above 95 percent) is a design
  failure and triggers a re-tune (oracle re-emergence); under-competence
  (below 75 percent) triggers the fallback for that family.
- **Null control (frontier self-review, the co-designer's sharpening,
  2026-08-25, clarified same day): the solver runs on the test articles in two
   modes, and the difference is the prompt. **WITH the prompt**: the frozen
  claim-verification prompt (article plus the claim in question form, the
  prosecution's instruction, PASS/FAIL plus reason), the same exercise as the
  jurors. WITHOUT the prompt (the baseline control)**: the ordinary defendant
  answers (article plus question, natural answer, no contract). The
  with-prompt run is the control for "a frontier model doing its own
  adversarial review": the extra expensive same-family compute call the
  product would otherwise make, and it doubles as the registered arm: the
  solver answering the claims as a sixth, un-tuned proposer, so the
   oracle-vs-consensus decomposition includes the strong model. The prompt is
   drafted from the co-designer's quoted wording (he dropped the link
   question; final text frozen in `prereg.yaml`).
- Memorization check: train/calibration accuracy gap reported per proposer. A
  gap above 10 points is logged in DECISIONS.md and read as memorization risk.
- Weights frozen and content-hashed after training; hashes recorded in the
  registration artifact.

## 6. Task and output contract (frozen at Phase 2, exact grammar in `prereg.yaml`)

- Jury task: one claim at a time. In: the article (evidence) plus one claim in
  question form. Out: `{ answer: PASS|FAIL, reason: <text> }`. The frozen
   prompt (drafted from the co-designer's quoted wording; final text in
   `prereg.yaml`): "Answer this question only
  based on the information available on this article. [question]", carrying
  the prosecution's instruction that the verdict rests solely on the article.
  One call per claim (40 per article per juror), so cost and TTFT are
  accounted per claim. The answer field is strict (PASS or FAIL; an explicit
  NOT_STATED maps to the silence cell and is kept so the three-state estimator
  survives); the reason field is free (the model's own grounding; free
  thinking is what keeps the five families from making identical mistakes).
- **Self-distilled training data (the co-designer's low-perturbation scheme,
  2026-08-25): before any fine-tuning, each base family is run zero-shot on
  its own training slice with the jury prompt, and its exact native output is
  captured. The fine-tuning target is not the gold label and not the verbatim
  output: it is `{ answer: <PASS|FAIL parsed from the native output>,
  reason: <the native output verbatim> }`. The LoRA therefore learns only the
  wrapper: the instruction style, the JSON contract, and the answer field; the
  reasoning content is the family's own native grounding. Perturbation is
  minimal, and each family's native competence and blind spots survive the
  fine-tune, which is what keeps the five voters decorrelated (RQ3). The
  zero-shot 1-4B jury baseline (P4) is this same native output scored on the
  same task, so fine-tuning versus native is a direct comparison.
- **Losslessness check (the co-designer's perturbation proof, 2026-08-25):
  for each adapter, base and fine-tuned are run on articles the family was NOT
  trained on (the 10 calibration articles, untrained for every family) with the
  same jury prompt. Two numbers, per family: (a) exact-match agreement between
  the base and fine-tuned outputs (answers, then reasons), and (b) the
  perplexity of the base model's native outputs under the fine-tuned model,
  reported as a PPL ratio against the base's self-PPL (1.0 is lossless). This
  is the direct measurement of how much the LoRA perturbed the family, and it
  is what makes RQ3's decorrelation claim an observed property instead of an
  assumption. Descriptive, per family; an adapter whose fine-tuned outputs
  diverge from native on untrained articles is flagged as perturbed, and its
  share of the consensus is reported separately.
- CoT ablation, registered: the jury is trained in **two variants** on the same
  data: the reason-included target (think-then-vote; the reason field carries
  the native grounding) and the votes-only target (`{ answer }` only, no
  reason). Both are run on the test articles; the comparison is reported, not
  predicted. Ten adapters total (2 variants x 5 families).
- Solver task: article plus its 20 questions in, free-form trace and answers
  out. No contract (this is the without-prompt baseline control). Solver
  claims are matched to pool propositions by the author's seed mapping (each
  question's answer maps to its seeded propositions); unmatched claims are
  logged, not scored.
- Parse failures are logged as missing observations; parse rate reported per
  proposer (target: 100 percent by construction) and per solver question.

## 7. Measurement

- Vote matrix by **exact match** on proposition IDs, jury x pool. Silence is an
  explicit cell state, not a missing value.
- Arms:
  - WCT-U: uniform signed support (distinct pass minus distinct fail).
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
- Frontier self-review control (the null control): the solver's with-prompt
  verdicts on the same claims are scored exactly like the jurors' verdicts,
  giving the "frontier model doing its own adversarial review" arm. The
  without-prompt run is the defendant's claims themselves (the baseline
  control, the source of what is verified); it is reported, not a separate arm.
- Pass criterion (null-control comparison, the co-designer's sharpening,
  2026-08-25): across the corpus of test articles and questions, the juror
  system (the defendant's claims gated by the jury consensus, below-4B primary
  with the registered 4B fallback where applied) passes if
  either (a) it outright outperforms the frontier self-review control on
  false-claim rate (the 95 percent bootstrap CI of the difference entirely
  below zero), or (b) it is comparable to the control within 10 percentage
  points of false-claim rate (point estimate, bootstrap CI reported) at a
  lower total compute cost. The 10 point band is the noise-scale margin per
  the co-designer: a tighter 2 point band falls under noise at the
  test-corpus sample size. The cost ratio (juror system versus control, USD at
  our amortized serving price) is reported as a headline number; the pass
  branch requires strictly lower cost, not a fixed ratio. Compute cost and
  hosting cost are first-class evaluation axes, not footnotes.
- Cost and serving metrics, reported per arm: total input and output tokens,
  GPU-seconds, USD cost, median TTFT, and the minimum hardware that serves the
  arm at target concurrency (this is the fan-out value: the jury runs on cheap
  hardware the solver cannot).
- Jury-size sweep (RQ6): the gated false-claim rate at jury size 1, 3, 5, with
  the 3-juror arm pre-specified as the three highest-calibration-accuracy
  families. Descriptive curve; the minimum viable jury is an operational
  decision, not a prediction.
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
- P6 (co-designer's prediction, pre-registered 2026-08-25, in his words:
  "a more capable near-frontier model is likely to confidently bullshit an
  answer, and having the jury double-check it will materially improve the
  accuracy of the model. Out of 30 questions, if it bullshits 25, the jury
  stops that at under 10, which I'm saying is a 50 percent increase in
  trustworthiness of reporting missing knowledge beyond what's available in
  the revisited text"): on test articles, over the solver's pool-matched
  claims on UNSPECIFIED propositions (questions the article does not answer),
  (a) the solver bullshits a confident answer on at least 50 percent of them,
  and (b) the jury-consensus gate (dropping low-consensus claims) removes at
  least half of those wrong answers, i.e. the false-answer rate on
  UNSPECIFIED questions drops from at least 50 percent to under 33 percent.

Each prediction carries a power note: the tolerance is set from observed bin
noise where a bin is involved, not from aspiration (the source study's lesson
C9). P5's power note requires the test articles to yield at least 100
pool-matched solver claims of each class; if not, P5 is reported descriptive
only and the article count is raised before the next lock. P6's power note
requires the test articles to yield at least 30 pool-matched solver claims on
  UNSPECIFIED propositions (the 30-question denominator of the prediction); if
  not, P6 is reported descriptive only.
- P7 (co-designer's prediction, pre-registered 2026-08-25, in his words:
  "I predict that a consensus will outperform a single model specially on the
  grounds of same family blind spots. Additionally, smaller models could be
  easily fanned out into cheap infrastructure this is a huge value add over
  another expensive compute call to same family. I predict the consensus will
  have >50% compute effort whilst marginally being better at bullshit
  detection"): (a) the 5-juror consensus outperforms the single best juror on
  false-claim rate on the test articles (mechanism: same-family blind spots);
   (b) the juror consensus's raw compute effort exceeds 50 percent of the 27B's
   while its false-claim rate is lower than the control's (marginally better at
   bullshit detection). Raw compute effort is aggregate parameter scale times
   tokens processed, confirmed by the co-designer's arithmetic: 4x 4B = 16B of
   parameters, roughly half the 27B, and the ensemble also processes more
   calls and tokens (one call per claim per family), so the >50 percent
   prediction holds in FLOPs even though each token is cheaper. The value is
   therefore not raw compute savings but infrastructure: the jury fans out
   onto cheap hardware the 27B cannot run on (minimum hardware, TTFT,
   fan-out), while the alternative stays a single expensive same-family call.
   Power note: P7(b) requires complete token and parameter accounting for
   every arm (defendant baseline, with-prompt control, 5-juror).

## 9. Baselines, in order of stringency

1. Trivial base rate (floor).
2. Single best proposer, calibrated (the oracle reference).
3. Zero-shot 1-4B jury on the same articles: the native outputs scored on the
   same task (comparability and the P4 arm).
4. Frontier self-review: the solver answering the same claims under the frozen
   claim-verification prompt (the null control; the pass criterion in section 7
   compares the gated system against this arm).
5. Covariate logistic regression (the registered bar).
6. Optional: a small supervised verifier trained on the calibration labels
   (the strong-baseline the source study omitted).
7. Contamination runs (no-article, with-article) are validity checks, not
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
