# DECISIONS

Decision log. One entry per significant decision, with the reason. Newest first.

## 2026-08-25

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
