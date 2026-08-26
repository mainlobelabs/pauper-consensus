# Covariate feature list (P1-9)

What gets recorded in the results files (Phase 5). Every downstream
analysis (RQ3 decorrelation, RQ6 jury-size sweep, pass criterion, cost
metrics, memorization check, perturbation analysis) reads only these
fields, so the analysis is reproducible from the results files alone.

## 1. Per article (n = 30)

- `article_id` (T01-T30)
- `split_role` (train | calibration | test; 10/10/10, fixed seed, Phase 2)
- `topic`, `event_dates`
- `source_type` (verbatim | drafted)
- `word_count`
- `sha256` (of the article file, Phase 2)
- `in_passing_mention_count` (from manifest)
- `disputed_count` (from manifest `disputed`)

## 2. Per claim (pool proposition, n = 1,200)

- `proposition_id` (T##-###)
- `article_id`, `position` (1-40)
- `gold_label` (ENTAIL | CONTRADICT | UNSPECIFIED)
- `gate_label` (1 = ENTAIL, 0 = not)
- `question_form_id` (row id in `corpus/pool/question_form/`)
- `fact_role` (direct_fact | passing_mention | silence) formalized from
  the P1-4/P1-5 seed notes: direct_fact = a main stated fact of the
  article (or a deliberate misstatement of one); passing_mention = a
  secondary fact mentioned in passing (stated, partial, or misstated);
  silence = the article is silent on the point (the UNSPECIFIED class)
- `trap_type` (none | unit_swap | figure_conflict | disputed_pin):
  unit_swap = asserted value is a unit or digit transposition of the
  article's (known: T02-024, T12-023, T19-032, T36-021); figure_conflict
  = the article states two different figures for the same quantity and
  the proposition pins a total (known: T25-031, T35-031); disputed_pin =
  the point is one of the manifest's disputed pins (articles T02, T13,
  T18, T24, T25, T30, T35, T36); none otherwise
- `polarity` (affirmative | negative claim; negative = the proposition is
  a negation of a point)
- `seeded_by` (list of seeded-question numbers whose target is this
  proposition; empty if none)
- `proposition_word_count`
- `number_entity_count` (figures in the proposition)
- `date_entity_count`
- `sha256` (of proposition + question form, Phase 2)

Note: `seed_type` and `trap_type` currently live only in NOTES.md. They
must be formalized into `corpus/pool/metadata.json` (one record per
proposition_id) before Phase 5 generation, so the covariates are machine-
readable, not reconstructed from prose.

## 3. Per juror x claim (n = 1,200 x proposers x variants)

- `proposer_id` (llama-3.2-1b, gemma-3-1b, phi-4-mini, olmoe-1b-0125,
  qwen3.5-4b, solver-27b)
- `proposer_role` (juror | solver_baseline | solver_with_prompt |
  solver_as_proposer)
- `family`, `org`, `params`
- `adapter_variant` (none for zero-shot and solver arms; reason_included |
  votes_only for the 10 LoRA adapters)
- `article_slice_for_this_family` (trained | calibration | test; every
  family is untrained on the 10 calibration articles)
- `answer` (PASS | FAIL | NOT_STATED | parse_failure)
- `reason_char_count`
- `correct` (exact match vs gold_label; null on parse_failure)
- `gate_correct` (PASS vs not-PASS vs gate_label; null on parse_failure)
- `prompt_tokens`, `completion_tokens`
- `ttft_seconds`, `total_seconds`

## 4. Per solver x question (n = 30 x 20 = 600)

- `article_id`, `question_id`
- `question_type` (direct_fact | passing_mention | silence_trap)
- `matched_proposition_ids` (seed mapping; empty if unmatched)
- `matched` (bool)
- `answer_text`, `answer_word_count`
- `prompt_tokens`, `completion_tokens`, `ttft_seconds`

## 5. Per family / adapter (n = 5 families, 10 adapters)

- `calibration_accuracy` overall and per class (75-92 percent band check;
  above 95 percent = saturation, design failure; below 75 percent =
  fallback trigger)
- `train_vs_test_accuracy_gap` (memorization check; above 10 points is
  logged in DECISIONS.md)
- `losslessness`: `exact_match_answer` (base vs fine-tuned on calibration
  articles), `exact_match_reason`, `ppl_ratio` (PPL of base native
  outputs under the fine-tuned model, divided by the base's self-PPL;
  1.0 = lossless)
- `perturbed_flag` (adapter flagged when fine-tuned outputs diverge from
  native on untrained articles; its consensus share is reported
  separately)
- `weight_sha256` (after training, registration artifact)
- `zero_shot_rank` (rank by calibration accuracy; drives the RQ6 arm
  selection)

## 6. RQ6 jury-size sweep (registered)

- `jury_size` (1 | 3 | 5)
- Arm membership is pre-specified, no post-hoc selection: size 1 = the
  single highest `zero_shot_rank` juror; size 3 = the three highest
  `zero_shot_rank` families; size 5 = all five.
- `gated_false_claim_rate` per arm, bootstrap interval (the C11 decision
  rule: go requires the point estimate at or above delta AND the interval
  excluding zero; otherwise INCONCLUSIVE).

## 7. Cost metrics per arm

- total input and output tokens, GPU-seconds (or Apple-Silicon
  equivalents on helium), USD cost, median TTFT, minimum hardware that
  serves the arm at target concurrency.
