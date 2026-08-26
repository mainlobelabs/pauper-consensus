# PLAN: wave-consensus

Living plan. Update at the end of each working session: current state, next step.

## Purpose

Independently conduct the wave-consensus experiment (see SPEC.md): author a
cutoff-gap news corpus with designed falsehoods, fine-tune five small models
(the jury, each below 4B with 1-2B preferred) to verdict on claims per call,
self-distilled so each LoRA learns only the output wrapper, run an untouched
27B solver (the defendant) on the same items, and determine whether the jury
consensus predicts proposition truth and flags the solver's false claims
beyond the 27B's own with-prompt self-review (the null control), a fitted
covariate baseline, the single best proposer, and the zero-shot jury. If the
below-4B jury passes, the hypothesis is proven at its strongest form; 4B is
the pre-registered fallback and a descriptive ceiling. The ProofWriter
microworld is re-run with the same structured instrument as the controlled
comparison. This track is a pilot, and it says so on purpose.

## Current state

- 2026-08-25: project bootstrapped (git, uv, ruff, pytest, passing sample tests).
  SPEC.md drafted at v0.9 (ProofWriter pilot).
- 2026-08-25: SPEC.md rewritten at v0.10 after design review with the
  co-designer: authored cutoff-gap news articles, qwen3.8-27B solver plus 5x 4B
  LoRA jury, three-valued labels (ENTAIL/CONTRADICT/UNSPECIFIED), in-passing
  mentions as the UNSPECIFIED generator, contamination check, CoT ablation, P5
  solver-value prediction.
- 2026-08-25: SPEC.md at v0.11 after the adversarial pass on the co-author
  brief: pilot framing stated, microworld re-run arm restored, text-is-the-
  oracle and fact-check rule, registered bar is the covariate baseline, task
  difficulty stated, E0 as a reported number, solver confidence = token
  probabilities, leave-one-out is each voter in turn, freeze-scope sentence.
  Nothing locked, nothing trained, no corpus built.
- 2026-08-25: cutoff probe run against the live 27B (cutoff-probe/probes.md).
  The 2026-08-14 to 2026-08-25 window is verified blind for the 27B (self-
  reported cutoff 2026-01, not trusted, window not widened). P6
  (co-designer's jury-gate prediction) pre-registered in SPEC section 8.
  Verbatim-article option added to the corpus rules.
- 2026-08-25: repo moved to the marzukia GitHub account; all commits
  re-attributed to Andryo; pushed and verified on GitHub's side.
- 2026-08-25: 36 topic candidates collected (corpus/topics.md): 12 existing +
  24 new from Wikipedia current events + 20 reserve. The 30-topic selection is
  APPROVED by the co-designer (drop T06, T07, T09, T11, T31, T33). Sign-off
  came with "hang fire": record and stop; freeze and label rubric wait for the
  go-ahead.
- 2026-08-25: 4B cutoff policy downgraded (co-designer sign-off): documented
  training window at family selection (hard filter, before 2026-08-14) replaces
  the per-family probe battery; the per-item contamination check stays as the
  verification and also covers fine-tune-data leakage. Recorded in SPEC (cutoff
  verification policy) and DECISIONS.
- 2026-08-25: design pass with the co-designer (SPEC v0.12). Courtroom
  vocabulary adopted (prosecutor/defendant/jury/evidence, vote solely on the
  evidence). Null control added: the 27B runs blind mode (questions, no
  article) and juror mode (pool + article, frozen contract); the pass
  criterion is beat the self-review control, or match it within 10 points at
  lower cost (ratio reported). Jury relaxed to 1-4B, older/smaller preferred.
  RQ6 jury-size sweep (1/3/5) and RQ7 1B arm (phase 2) added. P7
  pre-registered (his words). Cost/TTFT/minimum-hardware reporting added.
  Task list renumbered to 28. His follow-up reply: P7 compute basis confirmed
  (raw FLOPs, 4x 4B = 16B, roughly half the 27B), comparable margin widened
  to 10 points (2 was under noise), cost branch is strictly lower cost with
  the ratio reported.
- 2026-08-25: co-designer reply, SPEC v0.13. The "blind" flag is RESOLVED:
  the null control is with-prompt (the juror's exercise under the frozen
  claim-verification prompt) versus without-prompt (the ordinary defendant
  answers, the baseline control); no third run. The jury contract is
  restructured to one call per claim, out `{ answer: PASS|FAIL, reason }`.
  Training is self-distilled (capture each family's zero-shot native output;
  target = wrapper with the native output verbatim as reason, so the LoRA
  learns only the wrapper). Losslessness check per adapter on untrained
  articles: base-vs-fine-tuned output agreement plus PPL of the base native
  outputs under the fine-tuned model (1.0 = lossless).
- 2026-08-25: one-pager for the co-designer published to webdrop
  (ASD-STE100, the experiment in context of the v3 draft, the blind-spot
  goal). He dropped the prompt-link question ("don't worry about it"): no
  open items, the frozen prompt is drafted from his quoted wording.
- 2026-08-25: co-designer call (SPEC v0.14): the primary jury is BELOW 4B
  (1-2B preferred). If the mechanism works that small, the hypothesis is
  proven at its strongest form. 4B is the pre-registered fallback (applied
  family-by-family if a below-4B candidate misses the competence band) and a
  descriptive ceiling check. PLAN restructured into Phases 0-6 with concrete
  steps, deliverables, and gates per phase; SPEC jury section, RQ7, and
  phase numbers aligned.

## Next step

ON HOLD per co-designer sign-off ("approve, then hang fire"). Task 1 collection
is done and the 30-topic selection is approved. When the go-ahead comes: (a)
task-4 fact-check pass on T08 (Lindell recount) and T12 (Operation Economic
Outcast, resolve the 21 Aug vs 24 Aug date conflict) plus the rest of the
keep-30; (b) draft the frozen prompts from his quoted wording (task 9), then
pick the five below-4B jury families plus 2-3 4B fallback candidates under
the documented-cutoff filter (task 9); (c) Phase 2 freeze
(prereg.yaml + git tag, task 10); then task 2, the label rubric, and the
corpus proper.

## Phases and gates

Phase order is fixed. A phase starts only when the previous phase's verify
line passes. The Phase 2 tag is the point of no return for training: nothing
is fine-tuned before it, and any change to a frozen quantity after it is a
new registration.

### Phase 0 - Spec and design (DONE)

Concrete:

1. Adversarial pass on the v3 draft: 15 challenges (C1-C15), sharpest = the
   alignment blind spot (0/607 negative polarity) and the unmeasured
   error-decorrelation mechanism.
2. SPEC v0.14: courtroom frame, per-claim PASS|FAIL verdicts, self-distilled
   targets, losslessness check, null control (with/without prompt), pass
   criterion, below-4B primary jury + registered 4B fallback, P6/P7
   pre-registered in his words.
3. Cutoff probe on the live 27B (cutoff-probe/probes.md); window fixed at
   2026-08-14 to 2026-08-25.
4. 30-topic corpus approved by the co-designer (corpus/topics.md).

Deliverables: SPEC.md, PLAN.md, DECISIONS.md, corpus/topics.md.
Gate: co-designer sign-off. Status: met (the hang fire lifts it).

### Phase 1 - Corpus and jury (before any model run)

Concrete steps, in order:

1. Fact-check all 30 topics against the web (T08 Lindell recount and T12 Op
   Economic Outcast 21 vs 24 Aug date conflict first); log sources in
   topics.md (task 4).
2. Write the label rubric with worked CONTRADICT vs UNSPECIFIED boundary
   examples (task 2).
3. Draft the 30 articles: verbatim where a full article exists (source URL in
   the manifest), LLM-assisted otherwise, each with at least one in-passing
   mention of a secondary fact (task 3).
4. Write 20 seed questions per article: 600 total (task 5).
5. Expand to 40 propositions per article: 1,200 total, target mix 50 percent
   ENTAIL / 25 CONTRADICT / 25 UNSPECIFIED, both polarities within each class
   (task 6).
6. Label all 1,200 with the rubric (task 7).
7. Re-check 10 percent of the labels from scratch; log the agreement rate
   (task 8).
8. Pick the jury: five distinct families, each below 4B (1-2B preferred),
   none the 27B's family, documented training cutoff before 2026-08-14
   (probe only if documentation is unclear); plus 2-3 4B fallback candidates
   under the same filter. Record every documented cutoff in the manifest
   (task 9).
9. Draft the frozen prompts: the 27B solver prompt (no contract, ordinary
   answers, the without-prompt baseline control) and the claim-verification
   prompt (the jury contract, from the co-designer's quoted wording, one call
   per claim, out `{ answer: PASS|FAIL, reason }`), plus the covariate
   feature list (task 9).

Tasks: 1 (done), 2 (done), 3 (done), 4 (done), 5 (done), 6 (done),
7 (done), 8 (done), 9 (prompts + covariates drafted in prompts/; open:
1,200 question-form renderings in corpus/pool/question_form/ and
corpus/pool/metadata.json).
Deliverables: corpus/ (articles, questions, pools, labels), manifest.json,
prompts/.
- Verify: every fact web-checked with a source logged; rubric with worked
  examples committed; label agreement rate logged; jury families and fallback
  candidates listed with documented cutoffs; all frozen prompts drafted.

### Phase 2 - Registration (the freeze)

Concrete steps, in order:

1. Article-level split 10/10/10, fixed seed (task 10).
2. Hash topics, articles, pools, labels, prompts, manifest (sha256).
3. Write prereg.yaml: every registered quantity, the decision-rule boundary
   clause, the below-4B/4B fallback rule, the pass criterion.
4. Census go/no-go: at least 60 non-ENTAIL test propositions, else widen
   pools and re-hash.
5. Commit, tag `prereg-waveconsensus-v1`.

Task: 10.
- Verify: tag exists; every registered quantity in the spec has a line in
  prereg.yaml; decision-rule boundary clause present; census passes.
Gate: no fine-tuning before this tag.

### Phase 3 - Zero-shot checks (before training)

Concrete steps, in order:

1. Serve the 27B and the five jurors on hydrogen (vLLM, 1 concurrent request,
   temp 0, thinking off); smoke test (task 11).
2. Contamination run: each juror answers the 20 seed questions with and
   without each test article (parametric vs text-conditional); flag
   above-chance memory; re-select or relabel flagged items (task 12).
3. Run the 27B null control on the test articles: WITH the frozen
   claim-verification prompt (the juror's exercise, one call per claim) and
   WITHOUT it (the ordinary defendant answers, the baseline control); the
   with-prompt run doubles as the registered solver-as-proposer arm; capture
   token probabilities, tokens, GPU-seconds, TTFT (task 13).
4. Difficulty check: zero-shot jury accuracy on the test articles should sit
   around 80 to 90 percent; saturation means re-tune the pool (task 14).

Tasks: 11, 12, 13, 14.
- Verify: contamination table in the manifest, flags resolved or documented;
  difficulty band recorded per family; null control runs complete with full
  cost accounting.

### Phase 4 - Training

Concrete steps, in order:

1. Capture self-distilled targets: each base family zero-shot on the 10
   training articles under the jury prompt, one call per claim (400 per
   family); exact native outputs stored before any adapter exists (task 15).
2. Build targets: `{ answer: PASS|FAIL parsed from the native output,
   reason: the native output verbatim }`, plus the votes-only variant
   (task 15).
3. LoRA fine-tune: 5 families x 2 variants (votes-only, reason-included),
   distinct seeds, 10 adapters total (task 15).
4. Competence check per adapter: 75 to 92 percent on the calibration
   articles, train/calibration gap no more than 10 points (task 16).
5. Losslessness check per adapter: base vs fine-tuned on the calibration
   articles (untrained for every family), exact-match output agreement plus
   PPL ratio of the base native outputs under the fine-tuned model (1.0 =
   lossless) (task 16).
6. Go/no-go per family: out of band, re-tune once with a fresh seed; still
   out, apply the registered 4B fallback for that family; log every decision
   in DECISIONS.md (task 16).

Tasks: 15, 16.
- Verify: every adapter in the competence band or the fallback applied and
  logged; losslessness ratios recorded per family; weights frozen and
  content-hashed.

### Phase 5 - Generation

Concrete steps, in order:

1. 27B defendant run on the 10 test articles: frozen prompt, token
   probabilities captured, tokens and TTFT recorded (task 17).
2. Jury verdicts: one call per claim, 10 adapters x 10 test articles x 40
   claims = 4,000 calls, persisted call caps and attempt ledgers, tokens and
   TTFT per adapter and per claim (task 18).
3. Re-run the microworld arm: the same structured instrument on the frozen
   ProofWriter split, for the conditions-not-pipelines comparison (task 19).

Tasks: 17, 18, 19.
- Verify: every adapter in the competence band; cache complete; ledgers within
  caps; parse rates reported (target 100 percent by construction).

### Phase 6 - Analysis and report (tagged code, run unmodified)

Concrete steps, in order:

1. Build the vote matrix by exact match on proposition IDs, silence as state;
   run the arms: WCT-U, WCT-EM, claim-instance ablation, single best
   proposer, base rate, frontier self-review control, covariate baseline;
   Platt calibration on the calibration split only (task 20).
2. Primary and co-primary gates; within-article permutation null, 10,000
   draws (task 21).
3. Leave-one-voter-out, all six voters in turn, including the solver (P2)
   (task 22).
4. E0: pairwise proposition-level residual error correlation across voters
   (RQ3) (task 23).
5. Compare votes-only versus reason-included, reported not predicted
   (task 24).
6. Solver-value numbers (RQ4/P5): flag precision and recall on the 27B's
   false claims versus its true claims, against its token-probability
   confidence, 27B alone versus 27B plus panel (task 25).
7. Null control comparison (the pass criterion): defendant claims gated by
   the jury versus the with-prompt self-review control across the corpus, plus
   the cost table (tokens, GPU-seconds, USD, TTFT, minimum hardware per arm)
   and the P7 test (task 26).
8. Jury-size sweep (RQ6): gated false-claim rate at jury size 1 (single best
   juror), 3 (pre-specified top three by calibration accuracy), 5 (task 27).
9. Write the report: results tables, predictions confirmed and failed at
   equal prominence, invariants, the pass criterion verdict, the worked
   example (one in-passing mention, one hallucinated date, one panel flag),
   task difficulty stated, post-hoc diagnostics labelled, independent-
   recomputation note (task 28).

Tasks: 20, 21, 22, 23, 24, 25, 26, 27, 28.
- Verify: all numbers in `out/*.summary.json`; independent re-run
  byte-identical; label-flip probe run; every number traceable to a committed
  artifact.

## Repo and record-keeping

1. [x] Re-attribute all commits to Andryo (marzukia identity), rewrite history
   locally, set repo-local git identity.
2. [x] Create the repo under marzukia on GitHub (private) with his new PAT,
   push, verify. The PAT lives at ~/.secrets/github-andryo.pat (chmod 600);
   the commit-as-Andryo workflow is the `commit-as-andryo` skill.

## Standing rules

- One phase's "verify" must pass before the next starts.
- Any change to a frozen quantity is a new registration, not an edit.
- Post-hoc analyses are labelled post-hoc, always.
- Commits in this repo are authored and committed as Andryo, not Frank.
