# WCT — Experiment Build Plan

**Companion to** `plan.md` (design of record). This document does not restate the design.
It specifies **how to test it**: what gets measured, in what order, against what threshold,
with what controls.

**Status:** draft protocol, pre-spike, no code.

This document is **not yet a frozen pre-registration**. The repo has no git history, the
dataset manifest is not fixed, and the API quota is not confirmed. Before the first
experimental inference call, initialise version control, freeze the item manifests and
prompts, and commit/tag this document. Any later deviation must be recorded against that
frozen version.

**Review decision:** proceed to a repaired pilot, not directly to the full build. The
experiment has a credible core, but the causal comparison, analysis unit, graph mechanics,
and inference budget need the corrections specified below.

**Mathematical review (second pass).** The aggregation and propagation mathematics has now
been checked numerically rather than asserted; the checks live in `m0/ceiling.py` and
`m0/mechanics.py` and currently pass. Three findings change the protocol rather than merely
annotating it: uniform weighting is provably the wrong estimator for a heterogeneous panel
and a fully unsupervised alternative exists (**D9**, new **WCT-EM** arm); the repaired
propagation update converges but still recirculates evidence, which a depth-restricted
operator eliminates by construction (**D10**); and an even-sized panel decides roughly a
quarter of binary propositions by coin flip (**D11**). Two bounds — effective panel size
and oracle-of-panel coverage — are now computed *before* the gates they constrain, so an
unwinnable gate is identified in advance instead of being misread as a refutation.

---

## 0. Assessment

### 0.1 What is in the repo

| File | What it is | Verdict |
| --- | --- | --- |
| `wave-convergence-thinking.md` | Original notes: wave-pool sketch, undecided loss curve, amplitude worked example | Superseded by `plan.md`; keep as provenance |
| `plan.md` | Revised design of record — probabilistic propositions, AND/OR derivations, topology | Mathematical assumptions are explicit; this document tests them |
| `EXPERIMENT.md` | This build and evaluation protocol | Draft until R0 freezes it |
| `REQUEST.md` | Scope, acceptance criteria, constraints, and open questions | Useful brief; unresolved quota question is now R0 |
| `m0/ceiling.py` | Pre-inference ceiling analysis: design effect, oracle bound, estimator comparison, power | Runs and passes; invariants I8–I11 |
| `m0/mechanics.py` | Operator mechanics: tie rates, diffusion self-echo, aggregate calibration | Runs and passes; invariants I12–I14 |

The two `m0/` scripts are the only code. They require no API access and settle by
algebra and simulation what would otherwise be discovered mid-run. No git repo yet;
R0 must initialise and tag one.

`plan.md` began with unusually good pre-spike discipline: separate claims, a
load-bearing naive-synthesis baseline, a kill criterion, and explicit weaknesses. It has
now been revised with the mathematical findings below. This section records why the
original evaluation was changed rather than pretending those choices never existed.

### 0.2 Defects in the original evaluation design

**D1 — Everything is built before anything is measured.**
The pre-review `plan.md` §7 built all six stages over two weeks, then ran one gate. The gate was
simultaneously the *last*, *most expensive*, and *noisiest* measurement in the plan. If it
fails, you have spent two weeks and learned only "it didn't work" — not *where* it broke.

Claim A is a chain of four premises:

```
(a) the chosen model-family panel contributes more effective information than resampling
        |
(b) unique-source proposition support predicts proposition correctness
        |
(c) optional relation propagation adds held-out signal without recycling evidence
        |
(d) dependency-closed AND/OR selection produces better final answers
```

Only (d) is currently tested. Each of (a)–(c) is **cheaper, less noisy, and has ground
truth available**. (a) is testable using only sequential cached generation, and (b) is the
first direct test of the proposed claim-quality signal. Build the reusable cache client
first, but do not spend Claim A time on cluster fan-out or straggler handling.

**D2 — The gate is confounded and its power is unknown.**
The pre-review `plan.md` §6 specified ~50 open-ended problems, judge-scored, WCT vs naive synthesis. Three
problems:

- *Pairing is unspecified.* Paired over items, n=50 detects d_z ≈ 0.4 at 80% power. Unpaired,
  n=50 total is badly underpowered for any effect this method plausibly produces. The design
  must state that it is paired — and it must be, since item difficulty variance dwarfs the
  treatment effect.
- *The variance of paired treatment differences is unknown, so n cannot be chosen.*
  Judge repeatability is a useful diagnostic, but the power calculation needs the
  item-level variance of actual WCT-minus-baseline differences from a complete paired
  pilot. A judge-only test–retest SD is not a substitute.
- *Verbosity/style confound.* WCT emits a verbalisation of a short structured path; naive
  synthesis emits free prose over all traces. These differ systematically in length and
  register, and LLM judges have documented length and position biases. As specified, the
  gate could return a significant result in either direction that is entirely an artifact
  of output format.

**D3 — There is no null model.**
In the original `plan.md`, every arm was an ablation of WCT against itself. None asked
*"would a field with no real structure do just as well?"* Without a null, a positive result cannot
distinguish "the graph algorithm works" from "asking a model to verbalise a short list of
claims happens to be a good prompt format." Given §4.6's explicit architectural commitment
that the intelligence lives in proposition aggregation and derivation selection, this is
precisely the thing that most needs a control.

**D4 — Architecture is confounded with role prompting.**
The original `plan.md` §4.1 gave nodes different expert instructions specifically to
engineer divergence. A same-architecture ablation alone therefore could not identify whether an
effect comes from model-family diversity, role-prompt diversity, or their interaction.
The corrected design is a 2×2 factorial:

| | Same role prompt | Diverse role prompts |
| --- | --- | --- |
| Same model family | sampling control | role-diversity effect |
| Cross-model families | family-diversity effect | proposed WCT treatment |

Use **model-family diversity** as the operational term. Hosted model APIs do not expose
enough training lineage to justify a literal claim of independent architectures.

**D5 — Claims are not independent observations.**
Claims are nested within traces, models, and items. Pooling all claims into one AUROC would
pseudoreplicate the data and can turn item difficulty into apparent proposition-level signal:
easy items produce both more agreement and more correct claims. All splits, bootstraps, and
permutations must therefore operate at the **item** level. The primary E1 analysis must
measure whether support predicts correctness *within item* and beyond model identity,
depth, and intrinsic confidence.

**D6 — The graph conflates agreement with derivation.**
An NLI edge can say that two claims agree, contradict, or entail one another. It does not
say that one is a valid next reasoning step after the other. Using NLI edges directly as
cross-trace succession edges can produce a high-scoring bag of compatible claims rather
than a derivation. The repaired structure has two layers:

1. a **proposition layer** for cross-agent equivalence, support, and contradiction; and
2. an **AND/OR derivation layer** whose inference nodes preserve complete premise sets.

Equivalent claims merge into one proposition; alternative inference nodes from different
agents may then use that proposition. A selected derivation must be dependency-closed.

**D7 — Depth and the proposed propagation rule are not well-defined across models.**
The original plan correctly noted that one model may emit four steps and another eleven,
but then used model-reported depth globally for decay and path ordering. This penalised
extraction granularity, not overthinking. The repaired plan recomputes depth centrally and
uses explicit inference cost or description length as a complexity prior.

The superseded nonlinear `sqrt` update was also not guaranteed to converge. For
example, two mutually contradictory claims with confidence `0.1`, decay `1`, and
`alpha=0.8` alternate between amplitudes `[0.1, 0.1]` and `[0, 0]`. E2 therefore starts
with direct unique-source proposition aggregation and treats row-normalised signed
diffusion as an ablation with an explicit convergence condition.

**D8 — The distinctive prior-art claim has narrowed.**
The July 2026 preprint
[LLMs as a Jury](https://arxiv.org/abs/2607.10139) directly studies cross-model consensus,
error decorrelation, and comparison with process reward models. It does not appear to test
proposition-level AND/OR derivation construction, but it means answer-level cross-model consensus and
its decorrelation premise are no longer open territory. The distinctive question for this
spike is now:

> Does unique-source proposition aggregation plus dependency-closed cross-agent derivation
> outperform answer-level consensus, graph-blind derivation selection, and ordinary synthesis?

**Unverified citation.** The 2607.10139 preprint postdates the assistant knowledge cutoff
used during this review and was not read directly. D8 narrows the novelty claim on the
strength of it, so R0 must confirm the reference exists and says what is attributed to it
before that narrowing is treated as settled.

**D9 — Uniform weighting is misspecified for the panel this study will use.**
Unweighted unique-source aggregation is the maximum-a-posteriori rule only when sources
have equal and symmetric error rates. `m0/ceiling.py` (I9/I10, 1200 propositions × 30 reps)
shows what happens when they do not:

| Panel | best single | WCT-U (uniform) | WCT-EM (latent-truth EM) | oracle weights |
| --- | --- | --- | --- | --- |
| homogeneous, p = .70 | 0.700 | **0.782** | 0.783 | 0.782 |
| heterogeneous, p ∈ [.52,.93] | 0.879 | **0.828** | **0.889** | 0.898 |

On a heterogeneous panel uniform aggregation *loses to the best single source by five
points*. The free pool spans a 550B Nemotron and a 20B gpt-oss, so this study's panel is in
the second row, not the first.

The consequence is a missing arm, not a dead method. **Dawid–Skene EM treats proposition
truth as latent and estimates per-source sensitivity and specificity from the unlabelled
vote matrix alone.** It consumes no truth labels, so it sits on the WCT-U side of the
supervision ledger, and it recovers 88% of the uniform-to-oracle gap while costing nothing
on a homogeneous panel. **WCT-EM is therefore added as the primary unsupervised arm, with
WCT-U retained as the uniform-weight reference.** Without it, a negative WCT-U result would
be misread as falsifying the unsupervised claim when it only falsified uniform weighting.

Register the limit too: DS-EM assumes the same conditional independence WCT-U does, so it
corrects heterogeneity, not dependence, and remains biased under correlated sources. Its
label-flip non-identifiability is resolved by initialising at majority vote.

The three-state form (affirm / deny / **silent**, with emission probability conditional on
truth) absorbs the absence-versus-denial problem into the same estimator, which is cleaner
than correcting for it downstream. Retain the partial-identification bounds — named
**Manski bounds** — as the sensitivity analysis rather than the primary treatment.

**D10 — Contraction is not the same as non-recirculation.**
The revised update is a genuine repair: absolute row normalisation gives `‖P‖∞ ≤ 1`, so the
map is a contraction for `alpha < 1` and the divergence of the superseded `sqrt` rule is
gone. But the fixed point `a* = (1-alpha)(I - alpha·P)^-1 a0 = (1-alpha)·Σ alpha^t P^t`
still sums over *walks*, and even-order walks return to their origin. `m0/mechanics.py`
(I13) shows `diag(P²) = 1` exactly for a reciprocal pair — **all** second-order walk mass
comes back — and NLI between near-equivalent propositions is frequently close to symmetric.
The self-echo share of accumulated amplitude is `alpha²/(1+alpha²)`: 20% at `alpha = 0.5`,
**39% at `alpha = 0.8`**.

The assumption register lists "diffusion adds new signal rather than recirculating edges"
with an edge-rewiring null as its check. The algebra says recirculation is *structural*, so
the null will detect it but cannot prevent it. **Restrict `W` to strictly depth-increasing
edges** — already required for succession in the original `plan.md` §4.5. Under a
topological order `P` is then strictly triangular and hence **nilpotent**: the Neumann
series terminates, propagation is exact in `D` steps, the tolerance and iteration-count
parameters disappear, and self-echo is identically zero. Where cycles are genuinely wanted,
the **non-backtracking (Hashimoto) operator** is the standard remedy.

**D11 — An even panel decides a quarter of all propositions by coin flip.**
Binary propositions with `M = 4` sources at `p = 0.70` produce an exact vote tie **26.5%**
of the time (34.6% at `p = 0.60`); `m0/mechanics.py` (I12). Odd panel sizes produce none.
R0 must pin an **odd** panel size — five families rather than four — or guarantee the score
is continuous enough that exact ties cannot arise.

Related but separate: decomposing an item into binary propositions converts a *plurality*
problem into a *majority* problem. Plurality is far more forgiving of correlated error,
because wrong answers spread across alternatives while wrong propositions concentrate on a
single complement. This is a real cost of the propositional reframing and is paid for by
finer-grained credit assignment; record it as a design trade rather than a free win.

### 0.3 What this environment can actually support

Measured, not assumed:

| Resource | Status | Consequence |
| --- | --- | --- |
| OpenRouter catalogue | 15 text-capable free model entries across 6 named vendor families were visible at review time | Candidate pool only; catalogue presence is not endpoint availability or independence |
| OpenRouter credentials | No `OPENROUTER_API_KEY` is exposed to the current shell; `.agent/model-availability.json` records only two remote models as checked | **Unresolved resource gate.** Provision and smoke-test at least four stable families before freezing the design |
| OpenRouter quota | Default free allowance is 50 requests/day; accounts with at least USD 10 of purchased credits receive 1,000 free-model requests/day | E0 as originally written costs 1,200 generations: 24 days at the default quota, before E1–E3 |
| Local LM server `:1234` | Up. `nomic-embed-text-v1.5` embeddings re-verified working during review | Free local prefilter |
| Local generation | `laguna-xs-2.1` **fails to load** (host at 38/60 GB RAM) | Do not depend on local generation; not needed |
| GPU | **Unusable** — NVML driver/library version mismatch | NLI must run on CPU. Fine: 64 cores, aggressive prefilter keeps pairs low |
| CPU / RAM / disk | 64 cores, ~21 GB available RAM, 79 GB free disk | Adequate; microbenchmark CPU NLI before fixing pair counts |
| Python | 3.14.4 default; `python3.12` + `uv` present | Pin the experiment venv to 3.12 to avoid dependency-compatibility risk |

**The binding constraint is authenticated request quota, not local compute.** The two-week
plan is feasible only if the account has the 1,000-request/day allowance (or an explicit
paid budget). At 50 requests/day, reduce the scientific scope or stop; do not quietly turn
two weeks into a month.

Order-of-magnitude envelope, to be replaced by R0's measured figures: ~800 generations for
E0, ~400 for E1, and ~2,400 for E3 — of which **judging dominates**, since six arms scored
absolutely by two judges with both presentation orders costs ~24 calls per item before any
generation. Roughly 3,600–4,000 requests plus retries. That is four days of pure quota
inside a thirteen-day schedule at the 1,000/day allowance, and out of reach by a factor of
about eight at 50/day. Because the judge term dominates, the single most effective budget
lever is §3.6's move to graded pairwise comparison on the two registered contrasts instead
of absolute scoring of all six arms.

Two consequences worth stating plainly:

- **Claim A needs model-family *diversity*, not *concurrency*.** Nodes can run strictly
  sequentially with results cached. All parallelism, straggler handling, and k-of-N gather
  is Claim B machinery and is deferred past the gate. This removes most of week 1's
  engineering.
- Do not use the random `openrouter/free` router. The experimental factor requires pinned
  model ids and recorded resolved provider metadata. Select **five** primary families (odd,
  per D11) and at least one replacement per family before the run.
- **A capability confound is now live.** The free pool spans a 550B Nemotron and a 20B
  gpt-oss. On this pool, capability and dependence are first-order confounds—“agreement”
  may simply track “the big model was right.” Matching is learned on the calibration split
  and applied unchanged to the test split. Note the double edge: per D9, reliability spread
  is also precisely the regime where a latent-truth-weighted estimator beats uniform
  weighting, so the same property that threatens attribution is what makes WCT-EM worth
  running. Report both matched and unmatched panels for every arm.

---

## 1. What is being tested

To be frozen at R0. Predictions, thresholds, and analysis choices are fixed **before** any
experimental run; results are recorded against them regardless of outcome.

| Exp | Question | Primary decision statistic | Decision | Cost |
| --- | --- | --- | --- | --- |
| **M0** | Under what reliability/dependence/coverage regimes should WCT work at all, and what do the operators do by algebra? | simulated failure surface, recovery checks, `M_eff` ceiling table, operator invariants | implementation must recover known synthetic regimes and pass every invariant before API use | ½ day, zero inference |
| **R0** | Can the environment support a valid run? | stable **odd-sized** family panel, authenticated daily quota, CPU-NLI pairs/s | any binding resource misses its pre-set minimum → **stop or rescope before inference** | ½ day |
| **E0** | How much effective information does the actual panel contain, what causes its diversity, and does gain scale with `M_eff`? | paired 2×2 contrasts, residual dependence, shared-error rate, `M_eff`, **gain-vs-`M_eff` dose–response**, marginal log-loss gain | calibration/screening result; a gain flat in `M_eff` falsifies the mechanism regardless of any single contrast | 1 day |
| **E1** | Does unique-source proposition support predict correctness beyond obvious covariates? | held-out item-stratified Δlog-loss and **precision@k at the selector's operating point**, for WCT-U, **WCT-EM**, and WCT-C | apply the three-region rule below to **WCT-EM** as the primary unsupervised arm | 2 days |
| **E2** | Do signed relation propagation or other scoring additions earn their complexity? | held-out Δmetric vs direct proposition aggregation and structure-preserving nulls | delete any component that does not add held-out signal | 1–2 days, ~0 inference |
| **E2.5** | Are selected AND/OR derivations dependency-complete and valid across agent switches? | blinded derivation-validity score vs matched graph-blind derivations | failure → **stop before verbalisation** | 1 day |
| **E3** | Does WCT beat matched synthesis controls end to end? | **measured oracle-selection headroom** as a pre-gate, then item-paired graded-preference difference with item-block bootstrap CI | headroom < `delta` → **gate is unwinnable, stop**; otherwise apply the three-region rule below | 3–4 days |
| **E4** | Claim B: cluster prefill economics | tokens/s at target context | — | **deferred past gate** |

M0, R0, E1, E2, E2.5, and E3 are sequential gates. **Do not build stage N+1 before stage
N clears.** E0 characterises the chosen pool but does not by itself prove or falsify the
proposition-level hypothesis.

### 1.1 Decision rule

For each scientific gate define the smallest effect worth continuing for, `delta`, on the
metric's natural scale **before running that gate**.

Use 95% item-block bootstrap confidence intervals unless `prereg.yaml` gives a justified
alternative.

- **Go:** the confidence interval excludes zero in the beneficial direction and the point
  estimate is at least `delta`.
- **Stop:** the upper confidence bound is below `delta`, or the effect is harmful.
- **Inconclusive:** neither condition holds. If the two-week constraint requires a binary
  operational decision, treat this as stop while reporting that the hypothesis was not
  falsified.

This replaces “CI includes zero means the method is false,” which confounds absence of
evidence with evidence of absence. Exact `delta` values cannot be fixed until the dataset
and rubric scales are frozen; they belong in the pre-registration manifest, not in
post-result analysis.

Only registered primary comparisons make continuation decisions. E3 requires both the
project and attribution gates to pass, an intersection rule. Secondary arms, domains,
metrics, and sensitivity analyses are descriptive unless their multiplicity treatment is
registered in advance.

Two notes on that intersection rule, because both are easy to get wrong in opposite
directions. It is an **intersection–union test**, which controls type I error at `alpha`
**without any multiplicity correction** — applying Bonferroni to it would forfeit power for
nothing. And it is deliberately conservative: requiring both gates means the study can
return "not demonstrated" while one component genuinely works, which is the intended
trade and must be reported as such rather than as a refutation.

**Feasibility precedes power.** Before each gate, check that the effect it is sized to
detect is even attainable. `m0/ceiling.py` gives the two relevant bounds: `M_eff` caps the
information a panel can contain, and oracle-of-panel selection caps what any selector can
extract. If the measured ceiling for a gate lies below its `delta`, the gate cannot be won
by any implementation and must be rescoped or abandoned before it is run, not after.

### 1.2 Assumption register and empirical checks

Every load-bearing assumption in `plan.md` §3.1 has an observable diagnostic. Record the
result even when the downstream gate passes.

| Assumption | Diagnostic | Stage | Failure interpretation |
| --- | --- | --- | --- |
| average source is better than random | per-model sensitivity/false-positive rate on labelled propositions | E1 | WCT-U is not identifiable for this pool |
| sources are close enough in reliability for uniform weights | spread of per-source sensitivity/specificity; WCT-U vs WCT-EM vs best-single | E1 | uniform weighting is misspecified (D9); WCT-EM is the correct unsupervised arm |
| conditional independence given truth | pairwise conditional odds ratios within each truth class on labelled calibration propositions | E1 | additive log-odds are misspecified; every aggregate is overconfident and needs the §3.3 temperature |
| relation graph carries no self-echo | `diag(P^t)` for even `t`; nilpotency check on the depth-restricted `W` | E2 | propagation is recirculating evidence rather than adding it (D10) |
| family diversity reduces useful dependence | residual error correlation, shared-wrong rate, `M_eff`, marginal log-loss gain | E0 | vendor diversity is cosmetic |
| coverage is adequate | true-proposition recall by agent and union of agents | E1 | ranking cannot repair generation omissions |
| absence differs from denial | emission and explicit-negation confusion audit | E1 | missing claims are being mis-scored |
| proposition alignment is reliable | cluster precision/recall, pairwise relation confusion, transitivity violations | E1 | the measurement stack dominates the result |
| evidence is counted once per source | capped-vs-uncapped sensitivity analysis | E2 | verbosity was manufacturing confidence |
| diffusion adds new signal rather than recirculating edges | held-out Δlog-loss and edge-rewiring null | E2 | delete diffusion |
| dependencies are complete and valid | premise-set precision/recall and manual audit of every selected handoff | E2.5 | hybrid synthesis is not a derivation |
| complexity helps after coverage is controlled | no-penalty and matched-coverage ablations | E2.5/E3 | delete or change the simplicity prior |
| conclusions generalise beyond one panel | repeat the frozen test with a second independently selected panel | post-spike | claim only fixed-panel validity |

The binary truth model applies to mechanism data. Open-ended E3 criteria may be ordinal,
set-valued, or explicitly uncertain; do not force them into proposition-level Boolean
labels.

#### Supervision ledger

The word *unsupervised* applies to proposition weighting and derivation selection, not to
the existence of pretrained measurement instruments. Freeze this ledger before inference
so Claim A cannot drift after results are visible.

| Component | WCT-U | **WCT-EM** | WCT-C |
| --- | --- | --- | --- |
| embedding and NLI models | generic pretrained models allowed; pin exact revisions | same | same |
| alignment/relation thresholds | generic or relation-labelled calibration allowed; no proposition-truth or answer-quality labels | same | target calibration allowed |
| source reliability and domain weights | uniform/exchangeable; no truth-labelled fitting | **estimated by EM with proposition truth latent; no truth labels consumed** | estimated on truth-labelled calibration items |
| complexity, inference-validity, and terminal-coverage weights | fixed from M0 before task labels are inspected | fixed from M0 before task labels are inspected | may be tuned on calibration outcomes |
| score-to-probability map | may be fitted for held-out log-loss reporting only; cannot change ranking or selection | one monotone temperature may be fitted on calibration; monotone, so ranking and selection are unchanged | operationally calibrated |
| test and final-gate labels | evaluation only, opened after all choices freeze | evaluation only, opened after all choices freeze | evaluation only, opened after all choices freeze |

**WCT-EM is an unsupervised arm.** Estimating per-source reliability from the unlabelled
vote matrix with truth latent consumes no proposition-truth labels, so it does not cross
the WCT-U boundary. What it *does* consume is the conditional-independence assumption,
which is registered above and checked in E1. Report WCT-U alongside it as the uniform-weight
reference: the pair separates "aggregation works" from "reliability weighting was needed."

If a component crosses the unsupervised boundary, relabel that arm WCT-C rather than
preserving the stronger name.

---

## 2. Architecture of the experiment harness

One design decision does most of the efficiency work:

> **Separate expensive immutable inference artifacts from free repeatable analysis.**

```
  prereg.yaml + item manifests + prompt files
        |
  [ INFERENCE — expensive, rate-limited, cached, content-hashed, write-once ]
        traces/<split>/<item>/<condition>/<model>/<sample>.json
        claims/<split>/<item>/<condition>/<model>/<sample>.json
        relations/<split>/<item>.npz
        |
  [ ANALYSIS — pure numpy/scipy, seconds, infinitely re-runnable, zero inference ]
        cluster propositions -> unique-source aggregate -> optional diffuse
        -> dependency-closed AND/OR derivation -> metrics
```

Everything in `plan.md` §6.4's scoring, complexity, dependency, and null ablations is an
**analysis re-run over cached artifacts** unless it changes extraction. None of those
analysis-only variants costs an API call.

Corollaries:
- Freeze `calibration`, `test`, `gate_pilot`, and `final_gate` item manifests before
  inference. Never move an item after observing model output.
- Cache key = hash of (item, resolved model/provider metadata, prompt template, decode
  params, requested seed). Never invalidate on analysis-side changes.
- Store NLI *probabilities*, never thresholded edges. Thresholds are analysis-side.
- Record requested seeds, but do not assume hosted endpoints honour them. Preserve response
  ids, timestamps, resolved model ids, provider metadata, token counts, and failures.
- Hash `prereg.yaml`, prompts, manifests, and exact package/model revisions into every
  result row.
- Ablations that change *extraction* (not scoring) do cost inference — budget them
  explicitly, there are few.
- Never silently substitute a model after a failed request. One documented retry is enough
  for the spike; replacement models change the treatment and require a recorded deviation.

**Modules** (small, in dependency order — each is one file):

| Module | Does | Needed by |
| --- | --- | --- |
| `m0/ceiling.py` | **written** — design effect, oracle bound, WCT-U/EM/oracle comparison, power | M0 |
| `m0/mechanics.py` | **written** — tie rates, diffusion self-echo, aggregate calibration | M0 |
| `simulate.py` | generate latent propositions, noisy/correlated sources, mapper errors, and derivations | M0 |
| `nodes.py` | sequential pinned-model calls, one retry, immutable cache | R0, E0 |
| `extract.py` | one common extractor: rationale → claims and complete premise sets | E1 |
| `cluster.py` | align paraphrases into propositions; cap each agent at one vote per proposition | E1 |
| `measure.py` | local embedding → top-k prefilter → bidirectional CPU NLI probabilities | E1 |
| `aggregate.py` | WCT-U unique-source score, **WCT-EM three-state Dawid–Skene**, WCT-C likelihood score, fitted temperature | E1 |
| `diffuse.py` | depth-restricted (nilpotent) signed propagation; row-normalised diffusion and loopy BP as ablations | E2 |
| `nulls.py` | item-local, structure-preserving permutation tests; within-item truth-label permutation | E1, E2 |
| `derive.py` | bipartite AND/OR DAG, dependency closure, **max-closure (min-cut) selector with AO\* over OR nodes** | E2.5 |
| `verbalise.py` | selected derivation → prose, with no unselected claims | E3 |
| `evalh.py` | paired, blinded, order-balanced, length-controlled evaluation | E3 |

Use one common extractor in Claim A experiments. Self-extraction by each generating node
mixes generator quality with model-specific decomposition and belongs to the later
deployment experiment. Derive depth from the extracted dependency DAG. Deduplicate
same-agent paraphrases before aggregation so verbose extraction cannot create extra votes.

Stack per `plan.md` §5, with embeddings via the **local Nomic endpoint**. Select and pin an
exact Hugging Face NLI model id and revision after a 1,000-pair CPU microbenchmark; the
generic label `DeBERTa-v3-base-mnli` is not a reproducible dependency. Fix top-k from the
calibration split rather than assuming 2–5k pairs per item is feasible.

Setup: `uv venv --python 3.12 && uv pip install numpy scipy networkx httpx transformers torch --torch-backend=cpu`.

---

## 3. The experiments

### 3.0 M0 — Mathematical simulation and invariant checks (½ day)

Run before external inference. The simulator makes every latent variable observable and
tests whether the implementation behaves correctly under its own assumptions.

Generate:

- binary proposition truth with configurable prevalence;
- `M` sources with sensitivity, false-positive rate, and truth-dependent coverage;
- conditionally independent errors plus a latent shared-misconception component controlling
  residual correlation and convergence on the same wrong proposition;
- claim duplication and variable decomposition granularity;
- an extraction/alignment confusion process with configurable precision and recall; and
- acyclic AND/OR derivations with configurable missing-premise and invalid-inference rates.

Sweep at least:

```text
mean reliability p
residual correlation rho
shared-wrong rate
union coverage
alignment precision / recall
dependency precision / recall
panel size M
```

Compare single-best source, uncapped claim counting, WCT-U, oracle-parameter WCT-C,
estimated WCT-C, diffusion, a linear-path diagnostic, and dependency-closed AND/OR
selection.

Required invariants:

1. With `p > 0.5`, adequate coverage, correct alignment, and `rho = 0`, unique-source
   aggregation improves as effective panel size grows.
2. As `rho -> 1`, panel gain collapses toward the shared-error floor.
3. Duplicating one source's wording changes uncapped counting but not WCT-U/WCT-C.
4. Treating missing as denial is detectably biased when coverage is truth-dependent.
5. Mapping errors degrade aggregation; the simulator exposes the precision/recall region
   where any WCT advantage disappears.
6. Row-normalised diffusion converges for `alpha < 1`; convergence alone does not improve
   truth recovery.
7. A linear path can accept an inference missing one conjunctive premise; the AND/OR
   selector cannot.

The following are settled by algebra rather than by data and are already implemented and
passing in `m0/ceiling.py` and `m0/mechanics.py`. They cost nothing and bound the study:

8. **Effective panel size** follows `M_eff = M / (1 + (M-1)*rho)` and is capped at `1/rho`
   however large the panel grows. At `M = 4`, `rho = 0.3` leaves 2.11 effective votes.
9. **Uniform weighting is not optimal** on a heterogeneous panel: it loses to the best
   single source once per-source reliability spreads (D9).
10. **Latent-truth EM matches uniform** on a homogeneous panel and beats it substantially
    on a heterogeneous one, consuming no truth labels.
11. **Oracle-of-panel selection bounds any selector.** Simulated at `M = 4`, `p = 0.70`,
    `rho = 0.25`: majority scores 0.740 against an oracle ceiling of 0.946. The measured
    version of this quantity is E3's pre-gate.
12. **Even panels tie.** `M = 4`, `p = 0.70` gives a 26.5% exact-tie rate; odd panels give
    zero (D11).
13. **Reciprocal relation edges recirculate.** `diag(P²) = 1` for a mutually supporting
    pair; self-echo share is `alpha²/(1+alpha²)`, reaching 39% at `alpha = 0.8`. A
    depth-restricted `W` is nilpotent and echo-free (D10).
14. **Additive log-odds over correlated sources are overconfident**, and the analytic
    design-effect divisor over-corrects at low `rho` (log-loss 0.317 → 0.363 at
    `rho = 0.195`) while helping at high `rho` (0.632 → 0.498 at `rho = 0.385`). A single
    temperature fitted on calibration dominates both and leaves ranking untouched.

Invariants 8–14 also fix the gain-versus-`M_eff` curve that E0's dose–response analysis is
compared against.

Outputs:

- unit tests for every invariant;
- a failure-surface plot over reliability, dependence, coverage, and alignment quality;
- the break-even boundary where each WCT variant beats the single-source and voting
  baselines; and
- a schema matching the real cached artifacts so analysis code is shared with E1–E2.5.

M0 is not evidence that real models satisfy the assumptions. It verifies the implementation
and identifies which empirical quantities must be measured. Do not spend API calls until
all invariants pass.

### 3.1 R0 — Resource and freeze gate (½ day)

No experimental generation occurs before all of these are true:

1. The authenticated account quota is measured, not inferred from the public catalogue.
2. **Five** pinned model families — odd, per D11 — complete the exact generation and
   structured-output prompts; at least one replacement per family is identified.
3. A 1,000-pair embedding + NLI microbenchmark establishes a top-k budget that fits the
   CPU schedule.
4. Dataset manifests, role prompts, decoding parameters, M0 simulation grid, WCT-U/WCT-C
   definitions, fixed-panel estimand, `delta` values, exclusion rules, and analysis splits
   are committed and tagged.
5. The maximum item count and request cap for E0–E3 fit the remaining envelope with a 20%
   allowance for documented retries and judge calls. The E3 pilot may choose a smaller n,
   never a larger cap.
6. `REQUEST.md` OQ1 is resolved: record whether “two weeks” means 14 elapsed days or 10
   working days and whether unattended overnight/weekend inference is allowed.
7. `REQUEST.md` OQ2–OQ3 are resolved: remote benchmark-prompt egress is approved or a
   local pool is substituted; and any external novelty claim triggers a broader
   literature search beyond the focused update in D8. The 2607.10139 reference is
   confirmed to exist and to support what D8 attributes to it.
8. `m0/ceiling.py` and `m0/mechanics.py` run clean, and the resulting `M_eff` table has
   been read against each gate's provisional `delta`, so the team knows which gates are
   attainable before any quota is spent.
9. Version control is initialised and this document, `prereg.yaml`, the manifests, and the
   prompts are committed and tagged. Until that tag exists the protocol is a draft and no
   experimental inference may run.

Failure is an infrastructure result, not evidence against WCT. Stop or rescope before
spending inference.

### 3.2 E0 — Model-family × role-prompt calibration (1 day)

E0 reproduces the answer-level decorrelation effect in the actual endpoint pool and
separates two sources of diversity. It is a calibration experiment, not the hard
falsification of Claim A.

- **Items:** 40 calibration-only, checkable-answer items spanning predeclared domains.
- **Factorial arms:** four outputs per cell of the 2×2 design in D4. Cross-family cells use
  four pinned families; same-family cells use four independent samples from one reference
  family. Rotate diverse expert roles across families with a Latin-square schedule so role
  is not tied to vendor.
- **Cost:** 40 items × 4 cells × 4 outputs = 640 generation requests.
- **Measures:** accuracy, disagreement, double-fault rate, residual error correlation after
  accounting for item difficulty and generator accuracy, convergence on the same wrong
  answer, `M_eff`, consensus-selection accuracy, and each model's marginal held-out
  log-loss reduction given the rest of the panel.
- **Inference:** use paired item-block bootstrap intervals for the model-family effect,
  role effect, and interaction. Do not treat pairwise model correlations as independent
  observations. Models and roles are fixed experimental levels; uncertainty generalises
  over the item distribution, not a population of architectures.
- **Capability control:** define an accuracy-matching rule on these calibration items and
  apply it unchanged to later test items. Report unmatched and matched panels.

- **Dose–response reanalysis (no additional inference).** The 2×2 answers a binary
  question; the same cached outputs answer a quantitative one for free. Construct panels
  spanning a range of measured `M_eff` — four samples from one family, two families × two
  samples, four families, four families with rotated roles — then regress ensemble gain on
  measured `M_eff` and compare the curve against the theoretical prediction from M0
  invariant 8 (`m0/ceiling.py`). A single contrast establishes *whether*; a dose–response
  relationship that tracks the predicted curve is far stronger mechanistic evidence, and a
  gain that is **flat in `M_eff` falsifies the mechanism** even if an individual contrast
  reaches significance. §7.3 already argues that a measured boundary condition is the most
  valuable outcome available; this is the cheapest way to obtain one.
- **Report both correlations, and say which is which.** Marginal error correlation governs
  the *performance ceiling*, because at inference time item difficulty is unknown and
  simultaneous failure on hard items is precisely the failure mode. Residual correlation
  after conditioning on difficulty governs *scientific attribution*. They answer different
  questions and must not be reported interchangeably. Note also that "difficulty-driven"
  and "shared-misconception" correlation are not separately identifiable from one panel
  without further structure; what **is** identifiable — and what the 2×2 delivers — is the
  contrast between cross-family and same-family intraclass correlation.

E0 selects and characterises the pool. A null family-diversity effect lowers the prior
probability that E1 will work, but only E1 directly tests proposition-level signal. Stop at E0
only for an operational reason such as no endpoint stability, no task headroom, or a pool
so capability-skewed that a meaningful comparison cannot be formed.

### 3.3 E1 — Does unique-source support predict proposition correctness? (2 days)

This is the first direct test of Claim A, before propagation, derivation selection, or
verbalisation.

- **Dataset:** pre-split multi-step items whose intermediate claims can be checked.
  Checkable math, logic, causal-rule microworlds, or constrained design cases are valid
  here even though they are inappropriate for the final open-ended gate. Mechanism probes
  need claim ground truth; E3 tests transfer to the target task class.
- **Extraction:** one fixed extractor processes every trace into claims and complete
  premise sets. Claims are deduplicated within agent and aligned into proposition
  clusters. Each agent contributes at most one affirm/deny/missing observation to a
  proposition.
- **Labels:** use executable checks where possible. Otherwise use two blinded annotators
  and adjudicate disagreements. Report agreement and maintain an `uncertain` label that is
  excluded under a predeclared rule.
- **Measurement audit:** label a fixed claim-pair and cluster subsample for equivalence,
  entailment, contradiction, and neutral. Report alignment precision/recall, relation
  confusion, cluster transitivity violations, and dependency precision/recall.
- **Reliability and coverage:** estimate each model's sensitivity, false-positive rate,
  affirm/deny confusion, emission rate conditional on truth, union coverage, residual
  dependence, and shared-wrong rate.
- **Primary comparison:** baseline covariates—model-reported confidence, raw/normalised
  depth, generator identity, role, and task stratum—versus **WCT-EM**, the three-state
  Dawid–Skene score with proposition truth latent. Per D9 this is the primary unsupervised
  arm; **WCT-U**, the capped unique-source signed score with uniform weights, is reported
  alongside it as the reference. The pair is diagnostic: WCT-EM > WCT-U means reliability
  weighting was load-bearing, and WCT-U ≈ best-single means uniform aggregation was
  misspecified for this panel rather than the signal being absent.
- **Independence check:** on labelled calibration propositions, test whether the source
  vote table factorises *within* each truth class — pairwise conditional odds ratios, or a
  likelihood-ratio test of conditional independence. This is the assumption underneath
  every additive-log-odds arm including WCT-EM. Failure does not invalidate the ranking but
  does mean the probabilities are overconfident, which the temperature below absorbs.
- **Calibration:** fit one monotone temperature on calibration items (M0 invariant 14). The
  analytic design-effect divisor `1 + (M-1)*rho` over-corrects at low `rho` and must not be
  applied blindly. Being monotone, the temperature leaves ranking and selection unchanged,
  so WCT-EM remains inside the unsupervised boundary.
- **Secondary comparison:** **WCT-C**, using source/domain likelihood weights estimated on
  truth-labelled calibration items. It is not reported as unsupervised.
- **Primary metric:** held-out item-stratified Δlog-loss, with an item-block bootstrap
  interval for WCT-EM. A monotone score-to-probability mapping may be fit on calibration
  items for log-loss evaluation, but the inference ranking itself remains label-free.
  **The covariate baseline must receive the identical calibration treatment**; comparing a
  calibrated score against an uncalibrated one manufactures a win out of nothing.
  Report WCT-U and WCT-C separately, plus macro within-item AUROC for items containing both
  labels, class balance, and PR-AUC as diagnostics.
- **Co-primary metric — `precision@k` at the selector's operating point.** The derivation
  selector only ever consults the top of the proposition ranking, so global AUROC spends
  most of its resolution on discrimination the system never uses. Register `k` from the
  derivation sizes observed in M0 and report `precision@k` alongside Δlog-loss. Where they
  disagree, `precision@k` is the decision-relevant one because it is what E2.5 consumes.
- **Exact null.** Permute proposition truth labels *within item* and re-run the complete
  fitted pipeline (≥1,000 permutations, `nulls.py`). This yields an exact rather than
  asymptotic reference distribution and absorbs every fitting choice made downstream of the
  permutation, including the temperature and the score-to-probability map.
- **Powered adequately at this scale.** With 40 items and a within-item AUROC standard
  deviation of 0.15 across items, the item-block standard error is 0.024 and the smallest
  detectable AUROC is 0.546 (`m0/ceiling.py`). D5's clustering warning is correct about the
  analysis unit but should not be read as a demand for more items.
- **Leakage guard:** tune clustering, top-k, NLI label mapping, and relation thresholds
  only against the separately identified relation-labelled calibration set. Do not use
  proposition-truth or answer-quality labels to weight sources, tune derivation choices,
  or alter WCT-U rankings. Evaluate the frozen pipeline once on test items.
- **Decision:** apply §1.1 to **WCT-EM's** incremental held-out signal. The three arms
  separate three different failures, and conflating them is how a live method gets killed:
  - **WCT-EM fails and WCT-U fails** → proposition-level agreement carries no usable signal
    for this panel and domain. This is the genuine negative result for the unsupervised
    claim.
  - **WCT-EM works and WCT-U fails** → the signal is real; uniform weighting was
    misspecified for a heterogeneous panel, exactly as D9 predicts. The unsupervised claim
    **survives**, because WCT-EM consumes no truth labels.
  - **WCT-EM fails and WCT-C works** → reliability estimation needs supervision. The
    unsupervised claim fails while a calibrated method remains viable.

  Low performance caused solely by extraction/alignment failure is a measurement failure;
  repair it once using calibration data, record the deviation, and repeat with the
  untouched test split.

Fold `plan.md` §7's qualitative inspection into E1 by sampling claims before labels are
revealed. For shared-judge robustness, re-score a fixed 20% item subsample with a second
embedding/NLI stack and report rank correlation plus any change in the primary conclusion.

### 3.4 E2 — Does signed relation diffusion earn its complexity? (1–2 days)

Everything here re-runs over E1's cached artifacts. Calibration items select
hyperparameters; test items are evaluated once.

**E2a — Direct proposition aggregation.** Freeze WCT-U and WCT-C from E1. Compare them
against confidence-only, uncapped claim counting, within-family support, cosine-only
clustering, and answer-level consensus. This establishes the non-propagated baselines.

**E2b — Propagation, in three variants of increasing licence.** The default is the
depth-restricted operator, because it is the only one that cannot recirculate evidence.

```text
P[i,j] = W[i,j] / max(sum_j(abs(W[i,j])), epsilon)
a0     = frozen WCT-EM (or WCT-U / WCT-C) proposition score
a*     = (1 - alpha) * (I - alpha * P)^-1 @ a0     # 0 <= alpha < 1
```

1. **Depth-restricted (default).** Admit into `W` only edges where derivation depth
   strictly increases — already required for succession by `plan.md` §4.5. Under a
   topological order `P` is strictly triangular and therefore **nilpotent**: the Neumann
   series terminates, `a*` is computed exactly in `D` steps, `alpha` is the only remaining
   parameter, and self-echo is identically zero. Assert nilpotency at run time.
2. **Unrestricted row-normalised diffusion (ablation).** Absolute row normalisation gives
   `||P||∞ <= 1`, so the map is a contraction for `alpha < 1` and converges. But
   convergence is not non-recirculation: for a reciprocal pair `diag(P²) = 1`, so **all**
   second-order walk mass returns to its origin, and the self-echo share of accumulated
   amplitude is `alpha²/(1+alpha²)` — 20% at `alpha = 0.5`, 39% at `alpha = 0.8` (D10,
   `m0/mechanics.py`). Run it to quantify what the restriction costs or saves, not as the
   default. Record tolerance, iteration count, and residual. Where cycles are genuinely
   wanted, the **non-backtracking (Hashimoto) operator** is the principled alternative.
3. **Loopy belief propagation (ablation).** A proposition graph with signed compatibilities
   over binary variables *is* a pairwise MRF, and BP is the principled version of what
   diffusion approximates — with a known literature and known failure modes on loopy graphs
   with strong couplings, rather than a bespoke update rule. Cheap to add once `W` exists.

`W` may connect **distinct canonical propositions** via directional support or
contradiction; claim-instance equivalence edges have already been collapsed and cannot be
circulated. Compare held-out proposition metrics against direct aggregation. If no variant
reaches the predeclared `delta`, delete propagation and keep the simpler score.

**E2c — Paired-corruption positive control.** Start only from human-verified or executable
true claims. Create paired corruptions by negating, swapping a numeric value, reversing a
causal direction, or substituting an entity. Verify that every corruption is false and
remains fluent. The outcome is the paired ranking of original above corruption.

This is a **positive control** for polarity, contradiction measurement, and signed
relation handling—not evidence that natural model errors have the same distribution. Do
not label arbitrary unseeded claims as true.

**E2d — Structure-preserving nulls.** Generate at least 1,000 item-local permutations for
each null:

| Null | Preserve | Destroy |
| --- | --- | --- |
| Relation rewiring | signed degree, magnitude distribution, depth bin | which distinct propositions support which |
| Agent-label permutation | claims per agent and trace depth profile | association between family and proposition |
| Within-cluster vote permutation | votes per source and proposition prevalence | which source supports which truth state |

Report the real statistic against each permutation distribution. “Indistinguishable” means
the real value does not exceed the predeclared null percentile and effect-size threshold.

**E2e — Ablations and sweeps.** Tune `alpha`, relation threshold, and any relation-edge
normalisation on calibration items only. Include no confidence, unsigned relation edges,
same-family artifacts from E0, and capped versus uncapped claims. Complexity `lambda` is
not tuned here; it belongs to derivation selection. Apply the selected configuration once
to the test split.

### 3.5 E2.5 — Can the hybrid derivation make valid handoffs? (1 day)

Do not let a verbaliser repair or conceal an invalid graph.

- Build the bipartite AND/OR DAG from canonical proposition nodes and inference nodes.
  Every inference node contains its complete premise set; every selected derivation is
  closed under those dependencies.
- **Selection is exact, not heuristic.** Maximum-weight dependency-closed subgraph selection
  in a DAG is the **maximum closure problem**, solvable exactly in polynomial time by
  min-cut (Picard, 1976) — not a dynamic program. OR nodes, which offer alternative premise
  sets for the same proposition, take it outside plain closure and into AND/OR graph search
  (NP-hard in general, solved by **AO\***). Two-stage relaxation: take the max over each
  proposition's alternative inference nodes first, then solve the residual problem as exact
  max-closure. Report the AO\* optimum against the relaxation gap on the calibration split
  so any suboptimality is measured rather than assumed away.
- **The complexity prior has a principled form.** Scoring a derivation as
  `log P(conclusion | D) - L(D)`, with `L(D)` the description length of the derivation, is
  **minimum description length**, which fixes `lambda = 1` in nats and removes a free
  hyperparameter instead of sweeping one. Register MDL as the default and any tuned
  `lambda` as the ablation, not the reverse.
- For WCT-U, freeze `lambda`, inference-validity transform, and terminal-coverage weight
  from M0 before proposition-truth or answer-quality labels are inspected. WCT-C may tune
  those values on calibration items. Report no-complexity and matched-coverage ablations
  for both.
- Select the highest-energy dependency-closed derivation and a graph-blind derivation
  matched on proposition count, inference count, depth span, terminal coverage, and number
  of cross-agent source changes.
- Run a **linear-path diagnostic** on the same artifacts. Its expected failure on
  multi-premise inferences quantifies why a path is inadequate; it is not an implementation
  fallback.
- Present raw derivation structures without model names or scores to blinded evaluators.
- Score proposition correctness, complete-premise recall, local inference validity,
  contradiction consistency, terminal coverage, and cross-agent handoff coherence.
- Inspect every selected multi-premise inference and every cross-agent source change in
  this small spike. An invalid dependency set is a direct failure of the thesis, not a
  verbalisation problem.

Apply §1.1 to the paired derivation-validity difference. If scored AND/OR derivations are
not better than matched graph-blind derivations, stop before building verbalisation.

### 3.6 E3 — End-to-end gate (3–4 days)

Run only if R0 and E1–E2.5 clear.

- **Dataset:** a frozen final-gate set of open-ended analysis, design critique,
  multi-constraint tradeoff, and causal-explanation items with criterion-level rubrics and
  reference facts or constraints. It must be disjoint from all calibration and mechanism
  items.
- **Design:** every arm receives the same item and the same cached candidate traces. Use
  the same final model, output word budget, and prose instructions wherever an arm requires
  generation.
- **Arms:**
  1. WCT-U dependency-closed derivation → verbaliser. The verbaliser sees the prompt and
     selected derivation only.
  2. WCT-C derivation → identical verbaliser, reported as a calibrated secondary arm.
  3. Graph-blind matched derivation → the identical verbaliser.
  4. Naive synthesis of all raw traces → the same final model.
  5. Best single answer selected on calibration data.
  6. Answer-level cross-model consensus where the task admits an operational answer.
  7. **Token-budget-matched single model with extended reasoning.** `plan.md` §1 explicitly
     disclaims FLOP-optimality, which makes this the baseline that tests whether the
     disclaimer is carrying too much weight. Arm 5 selects among existing short answers;
     this arm spends the panel's *entire* token budget on one strong model instead.
- **Ceiling pre-gate, run on the pilot before the full gate.** E3's attainable effect is
  bounded above by (oracle-of-panel selection − naive synthesis) on the same items: no
  selector, however good its scoring, can exceed what is present in the candidate pool.
  Measure that headroom on the 15 pilot items and compare it to the frozen `delta`.
  **If the headroom is below `delta`, the gate is unwinnable and must not be run** — that
  outcome is a coverage result about the panel, reported as such, and it saves roughly four
  days and ~2,400 requests. §1.2's union-coverage diagnostic is promoted here to a hard,
  numeric, pre-run comparison.
- **Pilot and power:** run complete paired arms on about 15 pilot items. Estimate the
  standard deviation of the actual item-level treatment differences—not judge test–retest
  variance—and solve for the sample size required for the frozen `delta`
  (`m0/ceiling.py`: n = 32 at `d_z` = 0.5, 50 at 0.4, 88 at 0.3, 197 at 0.2). If the
  required item or request count exceeds the budget, report that before running the gate.
- **Futility boundary.** Register an explicit early stop: if the pilot's one-sided 80%
  upper confidence bound on the primary difference lies below `delta`, stop without running
  the full gate. Quota is the binding constraint, so the early exit must be pre-declared
  rather than improvised once the pilot looks discouraging.
- **Evaluation — graded pairwise, not absolute scoring.** Judge the two registered
  contrasts (WCT vs naive synthesis, WCT vs graph-blind) on a five-point comparative scale
  (much better / slightly better / tie / slightly worse / much worse) rather than scoring
  all seven arms absolutely. This cuts the dominant budget term roughly threefold and
  improves inter-judge agreement. Do **not** collapse to binary win/loss: a 60/40 win rate
  needs 189 items under a sign test against 122 for the equivalent graded effect
  (`d_z` = 0.25), and the penalty converges to the sign test's asymptotic relative
  efficiency against the t-test on normal data, `pi/2` ≈ **1.57× the items**
  (`m0/ceiling.py`). Retain criterion-level absolute rubrics on a subsample for
  diagnostics — they explain *why* an arm wins, which the comparative scale cannot.
- Anonymise arms; balance both presentation orders; use two judges from families absent
  from generation and verbalisation; report criterion-level agreement and order
  inconsistency. Human-review a fixed subsample plus all cross-judge disagreements.
- **Analysis:** average the graded comparative scale within item (and predeclared rubric
  criteria on the diagnostic subsample), then item-block bootstrap the paired differences.
  Report intervals, raw distributions, wins/ties/losses, token counts, request counts,
  latency, and failure rates.
- **Decision:** **WCT-EM** versus naive synthesis is the project gate for Claim A.
  **WCT-EM** versus graph-blind matched derivations is the attribution gate showing whether
  proposition scoring and dependency selection, rather than compact prompting, caused the
  result. WCT-U is reported alongside as the uniform-weight reference; WCT-C is informative
  but cannot rescue a failed unsupervised claim. Apply §1.1 to both primary comparisons,
  as an intersection–union test with no multiplicity correction (§1.1).

### 3.7 E4 — Claim B

Deferred. Per `plan.md` §6.3, no cluster distribution or prefill benchmarking until E3
clears. Recorded here only so it is visibly *deferred* rather than forgotten.

---

## 4. Schedule

Against `plan.md` §10's two-week envelope: several cheap screening exits, one end-to-end
project gate, and one deliberate go/no-go decision. The table uses **13 elapsed days** and
assumes the 1,000-request/day allowance plus unattended cached inference. If the envelope
instead means ten working days with no background execution, this schedule does not fit;
R0 must rescope it before the protocol is frozen.

| Day | Work | Exit condition |
| --- | --- | --- |
| 1 | **M0** simulator + invariants 1–7 (8–14 already pass); **R0** quota, five-family endpoint and CPU-NLI checks; git init, freeze/tag protocol | mathematical + resource gates; `M_eff` ceiling read against every `delta` |
| 1–2 | cache layer, sequential `nodes.py`, **E0** factorial calibration + dose–response reanalysis | pinned panel characterised; gain-vs-`M_eff` curve |
| 2–3 | common `extract.py`, proposition clustering, blinded labels | claims auditable |
| 3–4 | `measure.py`, `aggregate.py` (WCT-U + **WCT-EM** + WCT-C), **E1**, independence check, hand inspection and judge-stack check | held-out signal; which weighting is load-bearing |
| 5 | `diffuse.py` (depth-restricted default), positive control and frozen calibration sweep | propagation variant selected or deleted |
| 5–6 | **E2** test evaluation and permutation nulls | component deletion decisions |
| 7 | `derive.py` (max-closure + AO\*), **E2.5** dependency and handoff evaluation | mechanism go/no-go written down |
| 8 | `verbalise.py`, matched arms and `evalh.py` | end-to-end pilot runs |
| 9 | complete paired pilot → **ceiling pre-gate and futility check**, then choose n from treatment-difference SD | gate declared winnable and sized, or abandoned here |
| 10–12 | **E3** final-gate generation and graded pairwise evaluation | attribution + project gates |
| 13 | Write up — including the negative results | — |

Day 7 is the important early decision point: it arrives before the expensive open-ended
gate and distinguishes “agreement has some signal” from “a dependency-complete hybrid
derivation can use it.” E3 remains the single project-level continuation gate.

---

## 5. Deliberately not built

Scope discipline, per `plan.md` §10. Each of these is a real temptation:

- Parallel/async cluster execution, k-of-N gather, straggler handling — **Claim B**, needs
  diversity-not-concurrency; sequential caching is sufficient through E3.
- Targeted re-querying of unsupported graph regions (`plan.md` §8, coverage gaps) —
  explicitly excluded
  by the design doc itself.
- Adaptive per-query routing or online reliability learning beyond frozen WCT-C
  calibration — different project.
- Any UI, dashboard, or service wrapper.
- Production retries, robustness, and error taxonomies. One recorded retry plus immutable
  caching is the entire error-handling budget.
- Fixing the GPU driver mismatch — CPU NLI is adequate at the prefiltered pair count.
- Node-local self-extraction — it confounds Claim A and belongs to the later topology test.
- Nonlinear wave dynamics — the metaphor does not justify an unstable propagation rule.

## 6. How this could still fool us

Stated up front, so they are checked rather than rediscovered:

1. **Free-tier model substitution.** Providers silently swap or quantise free endpoints.
   Record resolved model and provider metadata for every response. A mid-experiment change
   invalidates comparisons involving that endpoint; a fingerprint prompt is only a weak
   diagnostic.
2. **Capability spread as fake diversity.** Matching on E0 calibration data helps, but
   post-hoc matching on test results would manufacture the desired panel. Freeze the rule.
3. **Role prompts as fake model-family diversity.** The factorial design and Latin-square
   rotation are mandatory. Collapsing directly to the full WCT cell recreates the original
   confound.
4. **Shared judge stack.** One embedding model and one NLI model sit under the mechanism
   tests. E1's fixed robustness subsample prevents the whole study becoming a measurement
   of one NLI model's priors.
5. **Agreement is not self-authenticating.** If the average-better-than-random assumption
   fails, WCT-U cannot distinguish unanimously wrong from unanimously correct panels.
   WCT-C may diagnose the problem but changes the claim.
6. **Pairwise measurements as fake sample size.** `M` source outputs can create `O(M²)`
   NLI relations. Treating those relations as independent support dramatically understates
   uncertainty; only unique-source proposition observations count as votes.
7. **Extraction granularity as voting power.** Without proposition deduplication and a
   one-agent-one-vote cap, verbose models create more apparent consensus.
8. **Extraction quality masquerading as method failure.** The blinded inspection and
   label agreement separate a bad measurement instrument from a failed hypothesis. Only
   one calibration-only repair is allowed.
9. **Easy-item confounding.** Pooled claim metrics can look excellent when support merely
   identifies easy questions. Within-item metrics and item-block resampling are mandatory.
10. **Incomplete dependency sets.** A selected conclusion may look locally coherent while
    omitting a required co-premise. E2.5 audits raw AND/OR derivations and every selected
    multi-premise inference.
11. **Verbaliser repair.** A capable final model may repair a bad derivation or add outside
    facts. E2.5 evaluates raw structures, and the primary WCT verbaliser sees no unselected
    claims.
12. **Judge style bias.** Equal word budgets, criterion-level rubrics, balanced order, and
   human review reduce but do not eliminate preference for fluent or authoritative prose.
   Report order inconsistency and judge disagreement, not just average scores.
13. **Simulation overclaiming.** M0 verifies code and maps assumed regimes; it cannot show
    that real model errors follow the simulator.
14. **Synthetic-control overclaiming.** Detecting deliberately negated claims validates a
    component but does not establish performance on natural errors.
15. **Fixed-panel overclaiming.** Item-block inference generalises to the sampled item
    distribution for the named panel, not to unseen model families. A second panel is a
    separate replication.
16. **Rationales are not latent cognition.** API-visible explanations are elicited text,
    not direct observations of a model's hidden reasoning process. Conclusions must be
    phrased as aggregation of generated rationales and claims, not recovery of true CoT.
17. **Analyst degrees of freedom.** `delta`, grids, splits, exclusions, null percentiles,
    and primary outcomes are fixed in the tagged pre-registration. Later movement is
    permitted only as a labelled deviation; the original result remains reported.
18. **Killing the method when only the estimator was wrong.** Uniform weighting is
    provably suboptimal on a heterogeneous panel (D9), and this pool is heterogeneous. A
    negative WCT-U result read as a negative *unsupervised* result is the single most
    likely false conclusion in this study. WCT-EM exists to prevent it.
19. **Mistaking convergence for non-recirculation.** The propagation update converges for
    `alpha < 1`; that says nothing about whether a proposition's own evidence returns to
    it (D10). Convergence diagnostics are not evidence of independence of contributions.
20. **Running a gate that cannot be won.** Correlated sources cap information at `1/rho`
    effective votes, and panel coverage caps what any selector can extract. Both bounds
    are measurable before the expensive gate; failing to check them converts a coverage
    limitation into an apparent refutation of the scoring method.
21. **Unverified prior art.** D8 narrows the novelty claim on a preprint that was not read
    during review. Confirm it at R0 before it constrains the study's framing.

## 7. Experimental operating notes

### 7.1 Diagnose negative results at the stage that produced them

| Failure | What it means | What it does not mean |
| --- | --- | --- |
| M0 invariant fails | implementation or stated mathematics is inconsistent | real models refute WCT |
| R0 fails | the available environment cannot run the registered study | Claim A is false |
| E0 shows no effective family gain | this panel's vendor diversity adds little answer-level information | proposition aggregation is universally impossible |
| E1 alignment/coverage fails | the measurement or generation channel is inadequate | agreement itself has no signal |
| E1 WCT-EM **and** WCT-U both fail with adequate measurement | the unsupervised proposition signal is not practically useful for this panel/domain | WCT-C or Claim B is false |
| WCT-EM works but WCT-U fails | uniform weighting was misspecified for a heterogeneous panel (D9); reliability weighting is load-bearing | the method needs supervision — WCT-EM uses no truth labels |
| WCT-C works but WCT-EM fails | reliability estimation itself needs supervision | the method remains unsupervised |
| E2 diffusion fails | pairwise propagation adds no value or recycles evidence | direct proposition aggregation failed |
| E3 ceiling pre-gate fails | the panel does not contain enough correct candidate material for any selector to reach `delta` | proposition scoring or derivation selection is wrong |
| E2.5 dependency validity fails | extracted claims cannot support hybrid derivations | naive synthesis cannot work |
| E3 attribution gate fails | compact prompting, not structural scoring, explains the result | all ensemble methods fail |
| E3 project gate fails | WCT-U does not beat naive synthesis by the worthwhile effect | the mechanism metrics were measured incorrectly |

Only one calibration-only repair is permitted for extraction/alignment. A second repair
after test inspection creates a new experiment and requires a new untouched split.

### 7.2 Sensitivity analyses

These are secondary and must not replace the frozen primary result:

- leave one model family out, reporting both accuracy and `M_eff`;
- leave one task domain out;
- vary proposition alignment thresholds over the pre-registered calibration-supported
  range;
- treat all missing observations as ignored, then run explicit best/worst-case missingness
  bounds;
- compare capped and uncapped source contributions;
- compare WCT-U, WCT-EM, WCT-C, direct aggregation, and each propagation variant on
  identical propositions;
- vary panel size across the odd values the pool supports, reporting gain against `M_eff`
  rather than against raw `M`;
- vary the complexity prior while holding terminal coverage approximately matched;
- repeat the judge-stack robustness subset; and
- if resources permit after the gate, repeat with a second independently selected panel.

Sensitivity results explain fragility. They do not license choosing whichever
configuration happens to win on the test split.

### 7.3 Minimum result package

Publish or retain internally:

1. the tagged protocol, manifests, prompts, package lock, model/provider metadata, and all
   labelled deviations;
2. a flow table from items → traces → extracted claims → proposition clusters → labelled
   propositions → complete derivations;
3. M0 failure surfaces and invariant results, including the `M_eff` ceiling table and the
   operator invariants from `m0/ceiling.py` and `m0/mechanics.py`;
4. per-model reliability, coverage, marginal **and** residual dependence, shared-wrong
   rate, effective panel size, and the E0 gain-versus-`M_eff` dose–response curve against
   its theoretical prediction;
4b. the measured oracle-selection headroom on the E3 pilot, whether or not the gate ran;
5. alignment, polarity, and dependency confusion matrices;
6. item-level primary outcomes, intervals, effect sizes, and wins/ties/losses;
7. all registered treatment, baseline, null, and ablation results—including deletions;
8. token counts, requests, latency, failures, and judge disagreement; and
9. conclusions scoped to the named panel and sampled item distribution.

The most scientifically useful outcome may be a boundary condition: a measured region of
reliability, dependence, coverage, and mapper quality in which WCT works or fails. Report
that even if the end-to-end gate is negative.
