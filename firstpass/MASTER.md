# Request: Build the WCT spike experiment

## Thoughts / context

> build it

Build the experiment specified in `EXPERIMENT.md` (the protocol) against `plan.md` (the
design of record). This is a science experiment, not production code: efficiency and
falsifiability over robustness.

The protocol is structured as a sequence of gates — M0, R0, E0, E1, E2, E2.5, E3 — each
with a pre-registered kill threshold. The slices below mirror those gates exactly, so a
slice's exit condition *is* the experiment's own decision point. Slices run sequentially,
which is what makes a negative result at slice N stop slices N+1 onward rather than
quietly continuing.

Two stage-zero facts already hold: version control is initialised with a pre-freeze
baseline commit, and M0 invariants I8–I14 are implemented and passing in `m0/ceiling.py`
and `m0/mechanics.py`.

## Constraints

- `EXPERIMENT.md` is the specification. Where this document and the protocol disagree, the
  protocol wins; record the discrepancy rather than silently resolving it.
- Python venv pinned to 3.12 (`uv`); 3.14 is the system default and lacks torch wheels.
- No GPU: NLI runs on CPU, batched, with prefilter top-k set by measured throughput.
- Embeddings via the local Nomic endpoint on `:1234`.
- **No experimental inference before R0 passes** and the protocol is tagged (protocol §3.1).
- Inference artifacts are immutable, content-hashed, write-once; all analysis re-runs over
  cache and costs no API calls.
- Authenticated request quota is the binding resource, not local compute.
- Push is human-only.

## Non-goals

- Claim B: cluster distribution, parallel fan-out, k-of-N gather, straggler handling,
  prefill benchmarking. Deferred past the E3 gate (protocol §3.7, §5).
- Everything else in protocol §5 "Deliberately not built".
- Production robustness: one recorded retry plus immutable caching is the whole
  error-handling budget.

## Slice 1: Scaffold and M0 mathematical gate

Repo scaffold and the simulation gate that must pass before any API call.

- A1: `uv` venv pinned to 3.12; dependencies installed per protocol §2.
- A2: `prereg.yaml` skeleton with every field protocol §3.1(4) requires, `delta` values
  left explicitly unset and marked as blocking R0.
- A3: Artifact cache layer implementing the protocol §2 layout and cache-key rule
  (item, resolved model/provider metadata, prompt template, decode params, requested seed),
  write-once, content-hashed.
- A4: `simulate.py` generating latent propositions, sources with configurable
  sensitivity/FPR/coverage, a shared-misconception component, duplication, alignment
  confusion, and AND/OR derivations with configurable defect rates.
- A5: Invariants 1–7 from protocol §3.0 implemented as tests and passing.
- A6: Existing invariants I8–I14 wired into the same test run and still passing.
- A7: Failure-surface output over reliability, dependence, coverage, alignment quality,
  plus the break-even boundary against single-source and voting baselines.
- A8: Simulator emits the same schema as the real cached artifacts, so E1–E2.5 analysis
  code is shared.

## Slice 2: R0 resource and freeze gate

No experimental generation happens until every item here is true.

- A1: Authenticated daily quota measured, not inferred from the public catalogue.
- A2: Five pinned model families (odd, per D11) complete the exact generation and
  structured-output prompts; at least one replacement per family identified; resolved
  model and provider metadata recorded.
- A3: 1,000-pair embedding + CPU NLI microbenchmark; exact HF NLI model id and revision
  pinned; top-k budget fixed from measured throughput.
- A4: Dataset manifests, role prompts, decode params, M0 grid, WCT-U/EM/C definitions,
  fixed-panel estimand, `delta` values, exclusion rules, analysis splits all committed.
- A5: Request cap for E0–E3 fits the remaining envelope with 20% retry allowance.
- A6: `REQUEST.md` OQ1–OQ3 resolved and recorded.
- A7: 2607.10139 confirmed to exist and to support what D8 attributes to it, or D8's
  narrowing is withdrawn.
- A8: `M_eff` ceiling table read against each gate's `delta`; unattainable gates rescoped
  or abandoned before any quota is spent.
- A9: Protocol tagged in git. Until the tag exists, no experimental inference may run.

## Slice 3: E0 model-family x role-prompt calibration

- A1: `nodes.py` — sequential pinned-model calls, one retry, immutable cache, no silent
  model substitution.
- A2: 2×2 factorial (model-family diversity × role-prompt diversity), Latin-square role
  rotation, four outputs per cell over 40 calibration items.
- A3: Accuracy, disagreement, double-fault rate, marginal and residual error correlation,
  same-wrong-answer convergence, `M_eff`, consensus accuracy, per-model marginal held-out
  log-loss — with paired item-block bootstrap intervals.
- A4: Dose–response reanalysis: gain regressed on measured `M_eff` across panels spanning
  one family to four-plus-roles, compared against the M0 theoretical curve.
- A5: Capability-matching rule defined on calibration items and frozen for later use;
  matched and unmatched panels both reported.

> **Amended after slice 1's step-4 gate** (see `DECISIONS.md`): `wct/aggregate.py`,
> `wct/diffuse.py` and `wct/derive.py` moved into slice 1, which builds and verifies them
> against simulated ground truth. Slices 4–6 below are reduced to the inference-dependent
> modules and their experiment drivers; the acceptance criteria naming those three modules
> are satisfied by slice 1 and are retained here only for traceability.

## Slice 4: E1 proposition-level signal

- A1: `extract.py` — one common extractor producing claims and complete premise sets;
  depth derived centrally from the extracted dependency DAG.
- A2: `cluster.py` — paraphrase alignment into propositions, same-agent dedup, one
  affirm/deny/missing observation per agent per proposition.
- A3: `measure.py` — local embedding, top-k prefilter, bidirectional CPU NLI probabilities
  stored unthresholded.
- A4: `aggregate.py` — WCT-U, WCT-EM (three-state Dawid–Skene, truth latent), WCT-C, and a
  single monotone temperature fitted on calibration.
- A5: Blinded proposition labels with adjudication and an `uncertain` class; measurement
  audit reporting alignment precision/recall, relation confusion, transitivity violations,
  dependency precision/recall.
- A6: Conditional-independence check on labelled calibration propositions.
- A7: Primary held-out item-stratified Δlog-loss for WCT-EM with item-block bootstrap;
  co-primary `precision@k` at the selector's operating point; identical calibration
  treatment for the covariate baseline.
- A8: Within-item truth-label permutation null, ≥1,000 permutations.
- A9: Shared-judge robustness on a fixed 20% subsample with a second embedding/NLI stack.
- A10: Protocol §3.3 three-way decision applied and recorded.

## Slice 5: E2 does propagation earn its complexity

- A1: `diffuse.py` — depth-restricted nilpotent operator as default with a run-time
  nilpotency assertion; row-normalised diffusion and loopy BP as registered ablations.
- A2: `nulls.py` — relation rewiring, agent-label permutation, within-cluster vote
  permutation; ≥1,000 item-local permutations each.
- A3: Paired-corruption positive control from verified-true claims only.
- A4: E2a non-propagated baselines; E2e sweeps tuned on calibration only, applied once to
  test.
- A5: Component deletion decisions recorded for anything failing to add held-out signal.

## Slice 6: E2.5 dependency-closed derivation

- A1: `derive.py` — bipartite AND/OR DAG; exact max-closure (min-cut) selection with AO*
  over OR nodes; relaxation gap reported on calibration.
- A2: MDL complexity prior as default; tuned `lambda` only as ablation.
- A3: Matched graph-blind derivations and the linear-path diagnostic.
- A4: Blinded scoring of raw structures; every selected multi-premise inference and every
  cross-agent handoff inspected.
- A5: Protocol §1.1 applied to the paired derivation-validity difference.

## Slice 7: E3 end-to-end gate

- A1: `verbalise.py` — sees the prompt and selected derivation only, no unselected claims.
- A2: `evalh.py` — paired, blinded, order-balanced, length-controlled, graded pairwise on
  the two registered contrasts.
- A3: Seven arms per protocol §3.6 including the token-budget-matched extended-reasoning
  single model.
- A4: Ceiling pre-gate measured on the 15-item pilot and compared to `delta` **before** the
  full gate runs; registered futility boundary applied.
- A5: n chosen from the pilot's treatment-difference SD, not judge test–retest variance.
- A6: Project gate and attribution gate both evaluated as an intersection–union test.
- A7: Minimum result package per protocol §7.3, including negative results.

## Open questions

- OQ1: R0 blocks on `delta` values, which cannot be set until the datasets and rubric
  scales are frozen. Who sets them, and does slice 2 stop for that decision?
- OQ2: Slices 3–7 are gated on empirical results, so their scope is conditional. Should a
  failed gate abandon the workstream outright, or park it for a human go/no-go?
- OQ3: Dataset sourcing is unspecified. E1 needs checkable multi-step items; E3 needs
  open-ended items with criterion rubrics. Existing benchmark, hand-authored, or both?
