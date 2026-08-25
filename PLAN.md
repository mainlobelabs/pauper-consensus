# PLAN: wave-consensus

Living plan. Update at the end of each working session: current state, next step.

## Purpose

Independently conduct the wave-consensus experiment (see SPEC.md): author a
cutoff-gap news corpus with designed falsehoods, fine-tune five small 4B
proposers to vote on proposition lists, run an untouched 27B solver on the same
items, and determine whether the jury consensus predicts proposition truth and
flags the solver's false claims beyond a fitted covariate baseline, the single
best proposer, and zero-shot 4B models. The ProofWriter microworld is re-run
with the same structured instrument as the controlled comparison. This track is
a pilot, and it says so on purpose.

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

## Next step

ON HOLD per co-designer sign-off ("approve, then hang fire"). Task 1 collection
is done and the 30-topic selection is approved. When the go-ahead comes: (a)
task-4 fact-check pass on T08 (Lindell recount) and T12 (Operation Economic
Outcast, resolve the 21 Aug vs 24 Aug date conflict) plus the rest of the
keep-30; (b) pick the 4B families under the documented-cutoff filter (task 9)
and record their documented training windows; (c) freeze the corpus
(prereg.yaml + git tag, task 10); then task 2, the label rubric.

## Task list (in order)

### Corpus and registration (before any model runs)

1. [x] Pick the 30 topics (approved by the co-designer 2026-08-25,
       corpus/topics.md; 36 candidates, 6 dropped). Each post-dates the
       training cutoff of all six models. Cutoff dates recorded: 27B probed
       (cutoff-probe/probes.md); 4B families carry their documented training
       windows at selection (task 9 filter).
2. [ ] Write the label rubric first: what counts as ENTAIL, CONTRADICT,
      UNSPECIFIED, with worked examples of the CONTRADICT vs UNSPECIFIED
      boundary.
3. [ ] Draft the 30 articles, LLM-assisted, each with at least one in-passing
      mention of a secondary fact.
4. [ ] Fact-check every real-world fact in every article against the web. The
      text is the oracle; a wrong in-passing mention relabels a batch of
      claims.
5. [ ] Write 20 seed questions per article.
6. [ ] Expand the pool: 40 propositions per article, roughly 50 percent the
      article supports, 25 percent it contradicts, 25 percent it is silent on,
      both polarities.
7. [ ] Label all 1,200 propositions with the rubric.
8. [ ] Re-check 10 percent of the labels from scratch; log the agreement rate.
9. [ ] Pick the five 4B families (distinct from each other, none the 27B's
       family, documented training cutoff before 2026-08-14 - a family with an
       unclear or later cutoff is not selected, probe only if the
       documentation is unclear); record each family's documented cutoff in the
       manifest; write the frozen prompts: the 27B solver prompt and the jury
       vote contract, plus the covariate feature list.
10. [ ] Freeze: article-level split 10/10/10 with a fixed seed, hash the topics,
      articles, pools, and labels, write `prereg.yaml`, git-tag
      `prereg-waveconsensus-v1`. No fine-tuning before this tag.
- Verify: tag exists; every registered quantity in the spec has a line in
  `prereg.yaml`; decision-rule boundary clause present; census shows at least
  60 non-ENTAIL test propositions, else widen pools before the tag.

### Zero-shot checks (before training)

11. [ ] Serve the 27B and the five 4Bs locally on hydrogen; smoke test.
12. [ ] Contamination run: for every test article, each 4B answers the 20
      seed questions with the article and without. Flag anything answered
      above chance from memory; re-select or relabel it.
13. [ ] Difficulty check: zero-shot 4B accuracy on the test articles should sit
      around 80 to 90 percent. Higher means the task is too easy and the models
      will saturate into oracles; re-tune the pool.
- Verify: contamination table in the manifest, flags resolved or documented;
  difficulty band recorded per family.

### Training and generation

14. [ ] LoRA fine-tune each family on its own slice of the 10 training
      articles, in two variants (votes-only, think-then-vote), 10 adapters
      total, distinct seeds.
15. [ ] Competence check per adapter: 75 to 92 percent on the calibration
      articles, train/calibration gap no more than 10 points.
16. [ ] Run the 27B on the 10 test articles, frozen prompt, token
      probabilities captured.
17. [ ] Collect the jury votes: 10 adapters times 10 test articles, persisted
      call caps and attempt ledgers.
18. [ ] Re-run the microworld arm: the same structured instrument on the
      frozen ProofWriter split, for the conditions-not-pipelines comparison.
- Verify: every adapter in the competence band; gaps logged in DECISIONS.md;
  weights frozen and content-hashed; cache complete, ledgers within caps, parse
  rates reported.

### Analysis and report (tagged code, run unmodified)

19. [ ] Build the vote matrix by exact match on proposition IDs; silence as
      state. Run the arms: WCT-U, WCT-EM, claim-instance ablation, single best
      proposer, base rate, covariate baseline. Platt calibration on the
      calibration split only.
20. [ ] Primary and co-primary gates; within-article permutation null, 10,000
      draws.
21. [ ] Leave-one-voter-out, all six voters in turn, including the solver
      (P2).
22. [ ] E0: pairwise proposition-level residual error correlation across
      voters (RQ3).
23. [ ] Compare votes-only versus think-then-vote, reported not predicted.
24. [ ] Solver-value numbers (RQ4/P5): flag precision and recall on the 27B's
      false claims versus its true claims, against its token-probability
      confidence, 27B alone versus 27B plus panel.
25. [ ] Write the report: results tables, predictions confirmed/failed at
      equal prominence, invariants, the worked example (one in-passing
      mention, one hallucinated date, one panel flag), task difficulty stated,
      post-hoc diagnostics labelled, independent-recomputation note.
- Verify: all numbers in `out/*.summary.json`; independent re-run
  byte-identical; label-flip probe run; every number traceable to a committed
  artifact.

## Repo and record-keeping

1. [ ] Re-attribute all commits to Andryo (marzukia identity), rewrite history
   locally, set repo-local git identity.
2. [ ] Create the repo under marzukia on GitHub (private) with his new PAT,
   push, verify. The PAT lives at ~/.secrets/github-andryo.pat (chmod 600);
   the commit-as-Andryo workflow is the `commit-as-andryo` skill.

## Standing rules

- One phase's "verify" must pass before the next starts.
- Any change to a frozen quantity is a new registration, not an edit.
- Post-hoc analyses are labelled post-hoc, always.
- Commits in this repo are authored and committed as Andryo, not Frank.
