# DECISIONS

Decision log. One entry per significant decision, with the reason. Newest first.

## 2026-08-26

- Self-distillation target vocabulary: three-state (approved by Andryo
  Marzuki, action button, 2026-08-26 evening). The prereg training
  section reads "Target = {answer: PASS|FAIL parsed from the native
  output, reason: native output verbatim}". The frozen jury contract is
  three-state (PASS/FAIL/NOT_STATED), so the literal "PASS|FAIL"
  wording admits three readings: (a) shorthand for the contract
  vocabulary, (b) binary collapse with NOT_STATED mapped to FAIL, (c)
  exclusion of NOT_STATED natives. Chosen: (a). The target answer is
  whatever the model's own native output parsed to, including
  NOT_STATED. Reason: only under (a) does the fine-tuned jury answer
  under the frozen contract (the answer field can emit all three
  states); under (b) the losslessness exact-match check dips on every
  NOT_STATED cell for the wrong reason (base says NOT_STATED,
  fine-tuned says FAIL); under (c) the wrapper never learns the
  NOT_STATED answer, contradicting the "LoRA learns the wrapper
  (instruction style, JSON contract, answer field)" description.
  Unparsed native outputs are excluded under all readings: they carry
  no valid target. Implemented in tools/phase4/make_dataset.py (no
  change was needed; the builder already uses the parsed answer
  verbatim).
- Jury composition: the registered fallback rule is applied, and OLMoE
  is dropped; the panel runs four independent families (approved by
  Andryo Marzuki, action button, 2026-08-26 evening). Phase 3 zero-shot
  calibration results trigger the prereg fallback rule (primary below 75
  percent on the calibration set) for three families: llama-3.2-1b
  (56.8 percent), gemma-3-1b (0 of 1200 outputs parseable under the
  frozen contract), olmoe-0125 (69.6 percent). The rule replaces a
  failed primary with its same-family 4B sibling: llama-3.2-1b ->
  Llama-3.2-3B-Instruct, gemma-3-1b -> Gemma-3-4b-it, both already
  downloaded. For the third trigger, OLMoE has no 4B sibling, so the
  rule prescribes "a registered cross-family fill from the 4B-class
  candidates" - but the only two candidates (Llama-3.2-3B, Gemma-3-4b)
  are already consumed as sibling replacements, so the rule is
  incomplete in exactly this case and any resolution is a post-freeze
  decision. Two options: (a) double one model (5 seats, 4 sources), or
  (b) drop OLMoE (4 seats, 4 sources). Chosen: (b). Reason: a doubled
  model violates three registered properties at once - the
  one-vote-per-source invariant (prediction P3), the training section's
  requirement of distinct recipes to keep error correlation low (a
  doubled model is correlation 1.0 with itself), and the leave-one-out
  design of P2 (removing one of two identical seats changes nothing).
  Mechanically, under a 3-of-5 majority the doubled model plus any one
  vote is itself a majority, concentrating near-veto power in one
  family. Dropping keeps all invariants intact; the prereg already
  registers panel size as an analysis dimension (the 3-juror sweep arm
  is defined by family), and the cost accounting (P7b, aggregate params
  x tokens) is cheaper with four voters. Consequences, declared here:
  the panel is llama-3.2-3b-instruct, gemma-3-4b-it, phi-4-mini-
  instruct, qwen35-4b; the fine-tuned adapter count drops from the
  registered 10 (2 variants x 5 families) to 8 (2 variants x 4
  families); the headline "5-juror consensus" becomes 4-juror; the
  5-seat weighted variant (double = whichever of the two 4B candidates
  scores higher on calibration, tie alphabetical, deduped at
  aggregation) is reported as a sensitivity analysis so the letter of
  the fill-in rule is still testable. Phi-4-mini (calibration 90.5
  percent) and Qwen3.5-4B (93.3 percent) keep their primary seats. The
  prereg text is unchanged: this is an application of the registered
  rule, labelled per the rule's own instruction.
- Jury-contract message amended at Phase 3, pre-generative (approved by
  Andryo Marzuki, action button, 2026-08-26 evening). The Phase 3 smoke
  test (task 11) showed all six models answering the frozen jury message
  in free prose: 0/6 parseable, including the 27B. Root cause: the
  registered user message in prereg.yaml carried the verification task
  and the article, but the JSON reply instruction and the PASS/FAIL/
  NOT_STATED definitions existed only in the Contract prose of
  prompts/jury_contract.md, not in the sent message. Fix: the Rules
  block (definitions, verbatim from the Contract section) and the
  "Reply with a single JSON object and nothing else" line were moved
  into the message intro. The co-designer's quoted sentences
  ("Answer this question only based on the information available on
  this article." + the question) are unchanged, as is the claim
  placement. Evidence before re-freezing (6 claims x 3 models): 27B and
  Qwen3.5-4B 100 percent parseable; Qwen3.5-4B correctly emits
  NOT_STATED on the "exactly 47" UNSPECIFIED cells where it previously
  said FAIL (the definitions change verdicts, measured); Llama-3.2-1B
  deterministically drops the closing brace on some cells at temp 0
  (genuine output, handled as missing observations per the registered
  contract). Consequence: re-frozen via tools/freeze_prereg.py; only the
  prompts/jury_contract.md hash and the prereg.yaml prompt block change;
  split, census, manifest sha256, and all other 156 corpus hashes are
  byte-identical. Tag prereg-waveconsensus-v1 moved to the amendment
  commit; pre-fix state at 5b35994. Pre-fix smoke output archived at
  cutoff-probe/runs/2026-08-26-phase3-smoke-prefix/. Spend at time of
  amendment: about 30 calls, all within the registered caps; no
  registered generation run had started, so nothing is re-run.
- Disputed-pin adjudication rules for the 30-article covariate pass
  (task 9, corpus/pool/metadata.json). Eight articles carry a manifest
  `disputed` field (cross-source split on one pin). Four cases decide the
  marking: (a) article SILENT on the disputed point, pin proposition in
  the UNSPECIFIED block -> disputed_pin on that pin (T02-031/032/034).
  (b) article pins a DISCRETE identity/name/age/date where reporting
  splits -> disputed_pin on the ENTAIL proposition carrying the article's
  pin (T18-005/006, T24-010, T36-006). (c) article states two conflicting
  figures and the proposition pins an EXACT/FINAL total the article never
  pins -> figure_conflict on the UNSPECIFIED pin, ENTAIL pins carrying the
  stated figures stay none (T13-031, T25-031, T35-031). (d) article silent
  on the RELATION between two stated disputed figures -> disputed_pin
  (T30-039). Reason: disputed_pin marks cells where the ground truth is
  itself contested across sources (the article's pin is defensible but not
  the world's truth), which the report must handle separately from
  figure_conflict, where the proposition merely fabricates precision the
  article never has. Both stay distinct covariates so the prereg can test
  whether the jury degrades differently on contested ground truth vs
  fabricated precision.
- Question-form conversion fixed to a POLAR form before any rendering was
  frozen (task 9, corpus pass). Every pool proposition renders as
  "Is it true that {proposition, verbatim, minus trailing period}?" with
  the asserted value kept. Reason: the jury contract's output is a verdict
  ON THE CLAIM ({ answer: PASS|FAIL|NOT_STATED, reason }), so the claim
  must be present in the prompt. The earlier draft interrogativized by
  DELETING the asserted value (wh-form: "What were Lala's sustained winds
  on August 16?"); with the value absent the jury could never answer FAIL
  for a wrong figure, so every wrong-number CONTRADICT would be
  indistinguishable from ENTAIL and the gate binary (PASS vs not-PASS)
  collapses. Polar form keeps the claim verbatim (auditable, trivial
  content hash), preserves negations as-is, and is one mechanical rule
  for all 1,200 propositions. Consequence: the seeded wh-questions in
  corpus/questions are the solver baseline task only; the jury contract
  uses the polar forms. Recorded before Phase 2 freeze, so no
  re-registration needed.

## 2026-08-25

- Primary jury below 4B, PLAN restructured into phases (co-designer's call,
  SPEC v0.14): the five jurors are each below 4B, 1-2B preferred. Reason:
  "if it works there already our hypothesis is proven" - if the jury
  mechanism works on models that small, the hypothesis (cheap small models
  materially improve the hallucination of a much better model) is proven at
  its strongest form, and the cost story is the best it can be. Pre-registered
  fallback: if a below-4B candidate family misses the competence band
  (75-92 percent) at Phase 4, the jury is filled from the 4B class for that
  family - declared at registration, applied family-by-family, labelled in
  the report. If the below-4B jury passes the pass criterion, 4B runs are a
  descriptive ceiling check (phase 2), not part of the proof. RQ7 (3x 1B)
  reframed as the size-floor question. PLAN now has Phases 0-6 with concrete
  steps, deliverables, and gates per phase; SPEC phase numbers aligned (lock =
  Phase 2, the registration freeze). One-pager published to webdrop for his
  review.
- Co-designer reply, SPEC v0.13 (2026-08-25):
  - The "blind" flag is RESOLVED: the two 27B runs differ in the prompt, not
    the article. WITH the frozen claim-verification prompt = the juror's
    exercise (the frontier self-review control); WITHOUT it = the ordinary
    defendant answers (the baseline control). There is no third run (no
     "no-article" mode). The prompt wording comes from the co-designer's own
     quote in the thread; he dropped the link question ("don't worry about
     it"), so the frozen prompt is drafted from that quote (task 9).
  - Jury contract restructured: one call per claim (article plus the claim in
    question form), out `{ answer: PASS|FAIL, reason }`. Vocabulary changed
    from AFFIRM|DENY to PASS|FAIL per his prompt. NOT_STATED maps to the
    silence cell and is kept so the three-state estimator survives. Reason:
    per-claim calls make cost and TTFT accountable per claim, which the pass
    criterion requires.
  - Training scheme: self-distillation (his low-perturbation idea). Before
    any fine-tuning, capture each base family's exact zero-shot native output
    on the training slice under the jury prompt ("Answer this question only
    based on the information available on this article. [question]"). Target =
    `{ answer: PASS|FAIL parsed from the native output, reason: the native
    output verbatim }`. The LoRA learns only the wrapper (instruction style,
    JSON contract, answer field); the reasoning content is the family's own
    native grounding. Reason: minimal perturbation preserves each family's
    native competence and blind spots, which is exactly what keeps the five
    voters decorrelated (RQ3). The P4 zero-shot baseline is the same native
    output scored on the same task, so fine-tuning versus native is a direct
    comparison.
  - Losslessness check (his perturbation proof): for each adapter, run base
    and fine-tuned on articles the family was NOT trained on (the calibration
    split, untrained for every family) and show the answers are lossless;
    report per family exact-match output agreement and the perplexity of the
    base's native outputs under the fine-tuned model (PPL ratio, 1.0 =
    lossless). This is the direct measurement of the level of PPL the LoRA
    introduces, and it turns RQ3's decorrelation from an assumption into an
    observed property.
  - Consequences: the with-prompt 27B run doubles as the registered
    solver-as-proposer arm (one run, two roles). The CoT ablation is
    redefined as reason-included target versus votes-only target (`{ answer }`
    only).
- Design pass with the co-designer, SPEC v0.12 (2026-08-25), several
  sign-offs in one message:
  - Courtroom vocabulary adopted: harness = prosecutor, 27B = defendant,
    fine-tuned proposers = jurors, article = evidence (stand-in for RAG),
    solver answers = claims, gate output = verdict. The prosecution instructs
    jurors to base their yes/no solely on the evidence. Reason: it makes the
    product frame legible and pins the jurors' task to the text.
  - Point of the exercise, in his words: the jury can be "way older models ...
    or even smaller models"; the point is to "materially improve the
    hallucination of significantly better [models] with cheap shitty models".
    Jury size class relaxed from 4B to 1-4B, older/smaller preferred.
  - Null control added: the 27B runs twice extra on the test articles, blind
    mode (20 seed questions, no article, parametric only) and juror mode
    (40-proposition pool plus article, frozen contract, vote block only,
    temp 0). The juror-mode 27B is the "frontier model doing its own
    adversarial review" control. Reason: without it, the jury's value could be
    "just make the frontier model review itself".
  - Pass criterion pre-registered: across the corpus, the juror-gated system
    passes if it outright outperforms the self-review control on false-claim
    rate (95 percent CI below zero), or is comparable within 10 percentage
    points at a strictly lower total compute cost (the cost ratio is reported
    as a headline number). The comparable band is 10 points, not the tighter
    proposal: per the co-designer, 2 points falls under noise at the
    test-corpus sample size. Cost is USD at our amortized serving price;
    compute cost and hosting are first-class evaluation axes. Reporting metrics fixed: tokens, GPU-seconds,
    USD, median TTFT, minimum hardware per arm.
  - RQ6 added: how many jurors for a meaningful change; gated false-claim
    rate at jury size 1/3/5, the 3-juror arm pre-specified as the top three
    calibration-accuracy families. Descriptive curve.
  - RQ7 added (optional, phase 2): can 3x 1B models achieve the same?
  - P7 pre-registered in his words: consensus outperforms a single model
    (same-family blind spots); small models fan out into cheap infrastructure,
    a huge value add over another expensive same-family compute call; he
    predicts the consensus will have >50 percent compute effort whilst
    marginally better at bullshit detection.
  Reason for the whole pass: it sharpens the experiment from "the jury helps"
  to "the jury beats the frontier model's own self-review at a fraction of the
  cost", which is the sellable claim.
  Flag status after the co-designer's reply (same day): (1) "blind" is still
  OPEN - he asked for the context of the word clarified before confirming
  whether it means "questions with no article" (a third 27B run) or "the
  ordinary defendant answers" (no new run); (2) P7's "compute effort" is
  CONFIRMED as raw compute (parameter scale times tokens), with his arithmetic
  4x 4B = 16B, roughly half the 27B - the value story is infrastructure
  fan-out, not raw compute savings; (3) the comparable margin is set at 10
  percentage points (the 2 point proposal was too tight, under noise) and the
  cost branch is strictly lower total cost with the ratio reported, not a
  fixed 10 percent ratio.
- 4B cutoff policy downgraded (co-designer sign-off): the jury families'
  cutoffs are established by their documented training windows at model
  selection (hard filter: documented cutoff before 2026-08-14; probe only if
  the documentation is unclear), not by a per-family probe battery. Reason:
  the jury task is text-conditional, so memory only matters on the silent
  (UNSPECIFIED) class where the text is silent; a base model's documented
  training window is a reliable claim, unlike the 27B community merge (unknown
  fine-tune data, self-report failed the P7 control). The per-item
  contamination check stays as written and is the real verification, since it
  also catches fine-tune-data leakage (cross-article fact overlap in the
  training slices), which the pretraining cutoff cannot.
- Corpus topics APPROVED (co-designer sign-off): the 30-topic selection in
  corpus/topics.md is locked in as the working set. Kept: T01-T05, T08, T10,
  T12, T13-T30, T32, T34, T35, T36. Dropped: T06, T07, T09, T11 (unverified or
  thin), T31, T33 (single-fact). Sign-off says "hang fire": record the decision
  and stop; the freeze (prereg.yaml + tag, task 10) and the label rubric (task 2)
  wait for the go-ahead. T08 and T12 still need the task-4 fact-check pass.
- Cutoff probe, qwen3.8-27b (orcarouter merge), 8 probes, 2026-08-25
  (cutoff-probe/probes.md): the model is verified blind to the 2026-08-14 to
  2026-08-25 band (Flores quake, Hurricane Lala, USS Abraham Lincoln, Hawk Fire
  all unknown; 2022 canary known). It self-reports a cutoff of 2026-01, but the
  October 2025 control (first $5T market cap) came back "Apple" instead of
  Nvidia, so the self-report is not trusted and the topic window is NOT
  widened: it stays 2026-08-14 to 2026-08-25, which is guaranteed
  post-cutoff for the whole panel by the release-date argument alone. Reason:
  a self-reported cutoff is an unverifiable claim about the merge's
  fine-tune data; the release date is a fact.
- Thesis-relevant bonus from the probe: the 27B makes confident factual errors
  on pre-cutoff knowledge (the P7 control miss). The jury therefore has
  something to catch even on items where the cutoff gap does not apply.
  Marked for the thesis: the verification layer's value does not depend on
  the cutoff gap being the only error source.
- Corpus decision: real news articles used **verbatim** where a complete
  article on the event exists (source URL in the manifest), drafted otherwise.
  Reason: verbatim articles are fact-dense, real, and cheaper to fact-check
  because the original is on record. As of today: 6 full single-topic
  articles collected (3 on the Flores quake, 2 on the Lincoln, 1 on Lala) plus
  ~10 headline digests to expand; target is 30, so drafting still dominates.
- P6 pre-registered: the co-designer's prediction (near-frontier models
  confidently bullshit; the jury gate cuts wrong answers on not-in-text
  questions by at least half, ~25/30 wrong down to under 10/30). Frozen in
  SPEC section 8 with a 30-claim power note; descriptive-only if the test
  articles yield fewer than 30 UNSPECIFIED solver claims.

## 2026-08-25 (earlier)

- Redesign v0.10 (co-designer, Andryo): the corpus is now 30 authored
  news-style articles about real-world topics that post-date every panel model's
  training cutoff, instead of ProofWriter. Falsehoods are designed in: each
  article carries claims it supports, claims it contradicts, and in-passing
  mentions that create claims the article is silent on. Three-valued labels
  (ENTAIL / CONTRADICT / UNSPECIFIED), single labeler, frozen rubric, 10 percent
  re-check. Reason: the cutoff gap forces text grounding (no parametric recall),
  the UNSPECIFIED class is exactly where hallucinations live, and the domain is
  real-world news, which attacks the demo-land objection.
- Redesign v0.10: panel is an un-fine-tuned qwen3.8-27B solver plus five 4B
  LoRA proposers from distinct families, each on a disjoint article slice, in
  two contract variants (votes-only and think-then-vote). The solver also votes
  as a sixth, un-tuned proposer (registered arm). Reason: the product
  configuration (cheap fine-tuned jury around an untouched expensive solver) is
  now the thing being measured, and the CoT ablation is reported on the same
  data.
- Redesign v0.10: new prediction P5 (the jury flags a larger share of the
  solver's non-ENTAIL claims than its ENTAIL claims) and a per-item
  contamination check (no-article zero-shot run before any fine-tuned output).
  Reason: RQ4 is the product question and deserves a falsifiable prediction;
  the cutoff assumption is only as good as the check that measures it.

## 2026-08-25 (bootstrap)

- Bootstrap: Python stack (uv, ruff, pytest), src layout, pre-commit hook on
  lint + format + tests. Reason: research/ML workload, house tooling.
- Bootstrap: vote primitive implements one-vote-per-source with silence as an
  explicit cell state. Reason: this is the load-bearing invariant from the
  source study; it is the first thing the pipeline must get right.
- Bootstrap: SPEC.md at v0.9 is NOT locked. Lock = `prereg.yaml` + git tag,
  before any training or generation (Phase 0).
