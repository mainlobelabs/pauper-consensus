# DECISIONS

Decision log. One entry per significant decision, with the reason. Newest first.

## 2026-08-25

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
