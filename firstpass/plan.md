# Wave Convergence Thinking (WCT)

**Status:** pre-spike. Nothing built. This document is the design of record and the
decision gate.

**One line:** run a prompt across several different model families, decompose their
generated rationales into canonical propositions and dependency sets, aggregate each
proposition as noisy evidence from unique model sources, and assemble a dependency-closed
hybrid derivation whose steps may originate from different agents.

---

## 1. The claim

There are two claims, and they should be kept separate because they succeed or fail
independently.

**Claim A (reasoning quality).** Under explicit reliability, coverage, alignment, and
conditional-dependence assumptions, convergence between independently generated,
cross-model-family propositions is an unsupervised ranking signal for proposition quality.
The benefit over sampling N times from one model exists only where the heterogeneous panel
has enough additional effective information—lower shared-error correlation must compensate
for any capability loss.

“Unsupervised” here means that the inference-time ranking can operate without labels.
It does **not** mean that truth is identifiable from agreement with no assumptions. The
uncalibrated variant assumes exchangeable agents that are better than random; a calibrated
variant estimates model/domain reliability on held-out labelled data and is reported
separately.

**Claim B (deployment topology).** The node layer has zero inter-node communication
during generation. Each node holds one complete model and talks to nobody. This makes
WCT runnable on hardware where sharding a single large model performs badly: high
unified memory, weak interconnect, mixed consumer devices. A Mac cluster is the
canonical case.

Claim B is the more defensible of the two and should lead any external pitch. Claim A's
answer-level premise is now occupied by recent work; WCT's distinctive question is whether
proposition-level aggregation plus dependency-closed cross-agent synthesis adds value.

**Explicitly not claimed:** that this is FLOP-optimal. Under fungible datacenter compute,
scaling a single larger model is likely more efficient. The argument holds where compute
is *not* fungible, which is on-prem, air-gapped, sovereign, and edge.

**Experimental estimand:** the spike estimates performance for a **fixed panel of named
models and prompts** over a sampled item distribution. It does not estimate an average
causal effect of “architectures in general.” Generalisation across model families requires
replication with independently chosen panels.

---

## 2. Origin sketch

```
                         " . . . "
                              \
                               \____  inject specific
                                     expert instruction
                               |
                               v
   "wave pool"
   +------------------------------------------------------+
   |                                                      |
   |    ((( o )))                        ((( o )))        |
   |                    ((( o )))    X                    |
   |                            X  ((( o )))              |
   |                                                      |
   |                       X            X                 |
   |    ((( o )))     ((( o )))     ((( o )))             |
   |                          X                           |
   |                    X          X                      |
   |    ((( o )))         ((( o )))      ((( o )))        |
   |                                                      |
   +---------------------------+--------------------------+
                               |
                               v
                         construct CoT
```

`o` = an agent. `X` = an interaction point between waves from different agents.

The original notes framed this as a wave field. Of the wave concepts, exactly three
survive contact with implementation and all three are load-bearing:

| Concept | Survives | Implementation |
| --- | --- | --- |
| Amplitude | partly | proposition ranking score or derivation energy; a probability only when calibrated |
| Decay with distance | partly | explicit complexity prior on inference cost, balanced by answer coverage |
| Interference | partly | unique sources affirm or deny a canonical proposition |
| Wavelength, frequency | no | no analogue that is not support count relabelled |
| Velocity, dispersion | no | systems properties, not reasoning properties |
| Reflection, refraction | no | decoration |

Do not spend time mapping the rest. The metaphor is a communication device from here on,
not a design constraint.

---

## 3. Positioning against prior art

Read before building. Each of these occupies part of the space.

| Work | Overlap | Difference |
| --- | --- | --- |
| Self-consistency | votes on final answers | discards the trace; undefined where there is no extractable answer |
| Mixture-of-Agents | multiple models, synthesis layer | synthesis is a single model reading everything, no structural scoring |
| Graph of Thoughts | reasoning as a graph | the graph is *planned*, not *emergent from independent traces* |
| Multi-agent debate | multiple agents | agents see each other, which produces herding |
| Process reward models | scores intermediate steps | needs supervision, or a definable first-error position |
| Unsupervised PRMs | verifier-free step scoring | single model family, correlated errors |
| iReasoner (intrinsic CoT agreement) | step-wise agreement across rollouts | conditions on a dominant answer group, so it needs an answer |
| [Dawid–Skene / noisy-annotator models](https://academic.oup.com/jrsssc/article/28/1/20/6953573) | infer latent truth and source reliability from agreement | assumes an identifiable observation model; no reasoning structure |
| [Correlated annotator aggregation](https://proceedings.mlr.press/v97/li19i.html) | models dependent sources rather than naive votes | no proposition extraction or hybrid derivation |
| [LLMs as a Jury](https://arxiv.org/abs/2607.10139) | cross-model consensus, error decorrelation, shared-error floor | answer-level selection; no claim graph or cross-trace derivation |

**Defensible combination:** model-family-diverse, proposition-level (not step-index-level),
unique-source evidence aggregation, and dependency-closed hybrid derivation without
inter-agent communication or required answer extraction. Each element individually is
taken. The combination appears open as of this writing, but this is not an exhaustive
novelty opinion. Re-check before any external claim.

### 3.1 Mathematical foundations

The wave metaphor does not supply a truth model. WCT needs an explicit observation model
before “amplitude” can be interpreted as evidence.

For item `q` and canonical proposition `z`, define:

| Symbol | Meaning |
| --- | --- |
| `Y[q,z] ∈ {0,1}` | latent proposition truth for the binary mechanism experiment |
| `X[m,q,z] ∈ {+,−,∅}` | model `m` affirms, denies, or does not emit proposition `z` |
| `s[m]` | `P(X=+ | Y=1, X≠∅)`, sensitivity conditional on emission |
| `f[m]` | `P(X=+ | Y=0, X≠∅)`, false-positive rate conditional on emission |
| `c[m,Y]` | probability that model `m` emits the proposition; coverage may depend on truth |
| `π[q,z]` | prior probability that the proposition is true |
| `J` | noisy extraction/alignment/NLI measurement process applied after generation |

Conditioned on truth and assuming independent model observations, the posterior log-odds
for an emitted proposition are:

```text
logit P(Y=1 | X)
  = logit π
  + Σ[m:X=+] log(c[m,1] * s[m] / (c[m,0] * f[m]))
  + Σ[m:X=−] log(c[m,1] * (1-s[m]) / (c[m,0] * (1-f[m])))
  + Σ[m:X=∅] log((1-c[m,1]) / (1-c[m,0]))
```

If coverage is truth-independent, its factors cancel and absence contributes zero; it may
then be treated as missing. Otherwise emission and non-emission are informative and the
coverage terms must remain. Absence is never silently converted into a negative vote.

This equation establishes the narrow conditions under which agreement is evidential:

1. at least some sources are better than random for the proposition class (`s[m] > f[m]`);
2. source errors are not perfectly conditionally dependent;
3. proposition alignment is accurate enough that votes refer to the same latent object;
4. every model contributes at most one observation to a proposition; and
5. coverage is sufficient—agreement can rank generated propositions but cannot recover
   a proposition that no model emitted.

Two variants must remain distinct:

- **WCT-U (uncalibrated):** no proposition-truth or answer-quality labels are used to
  weight sources or select derivations. Agents are treated as exchangeable and better than
  random, so the score is monotone in unique-agent signed support. Generic pretrained
  measurement models and separately disclosed relation-label calibration may still be
  used. It is an unsupervised **ranking score**, not a calibrated probability.
- **WCT-C (calibrated):** `s`, `f`, coverage, and optional domain effects are estimated on
  held-out labelled items. Its score may be interpreted probabilistically to the degree
  that the observation model is calibrated.

Unsupervised estimation of source error rates, for example via a Dawid–Skene-style latent
class model, is possible only under additional identifiability assumptions. Agreement
alone admits a label-swapping symmetry: unanimously wrong and unanimously correct panels
look the same without an anchor such as average-better-than-random reliability.

#### Conditional dependence and the shared-error floor

Model families share data, teachers, benchmarks, and post-training methods. Vendor names
are therefore not independence guarantees.

For `M` equally accurate sources with equicorrelated correctness indicators and pairwise
conditional correlation `ρ`, the variance of their mean has the same form as an
independent panel of approximate size:

```text
M_eff = M / (1 + (M - 1) * ρ)
```

`M_eff` is a dependence diagnostic, not an exact accuracy theorem. It shows why panel
benefit saturates: for positive `ρ`, adding models eventually hits a shared-error floor.
Cross-family diversity helps only when reduced dependence is worth more than any loss in
individual capability or coverage.

The useful quantity is therefore not “number of agents” but **marginal held-out information
given the existing panel**, measured as log-loss reduction or conditional mutual
information where estimable.

#### Measurement is not evidence

Embedding and NLI operate on pairs of claim texts, creating `O(M²)` pairwise measurements
from only `M` model outputs. Those pairwise edges are not independent evidence. Four
agreeing agents provide four sources, not twelve directed confirmations.

Use pairwise models to:

1. align claim instances into canonical propositions;
2. determine whether each source affirms or denies the proposition; and
3. estimate the uncertainty of that mapping.

Then collapse to one proposition node and aggregate unique-source observations. Any
algorithm that repeatedly circulates the same pairwise edges risks epistemic
double-counting even if it is numerically stable.

#### Assumption register

| ID | Assumption | Consequence if false |
| --- | --- | --- |
| M1 | proposition truth is operationally labelable for the mechanism dataset | E1 has no ground truth |
| M2 | the average source is better than random, or an external reliability anchor exists | unsupervised truth is not identifiable |
| M3 | residual source dependence is limited and measured | consensus confidence is overstated |
| M4 | non-emission is modelled separately from denial | quiet sources become false opposition |
| M5 | extraction and proposition alignment have adequate precision and recall | agreement measures the mapper, not reasoning |
| M6 | one source contributes at most one vote per proposition | verbosity becomes voting power |
| M7 | inference dependencies are explicit and valid | selected claims need not form a derivation |
| M8 | complexity decay is declared as a prior and balanced by coverage | short incomplete arguments win |
| M9 | API-visible rationales are treated as generated text, not latent cognition | claims overreach what is observed |
| M10 | models are treated as a fixed panel unless multiple panels are sampled | results do not generalise to architectures as a population |

---

## 4. Architecture

Six stages. Generation is independent across nodes. For the Claim A spike, one common
extractor is used centrally to avoid confounding generator quality with model-specific
self-extraction; node-local extraction is reintroduced only in the later Claim B topology
experiment. Stages 3–5 operate on compact structured claims. Stage 6 is one small model
call.

```
  prompt
    |
    +--> [node 1: Qwen]    --> trace --> claims  \
    +--> [node 2: Llama]   --> trace --> claims   \
    +--> [node 3: Gemma]   --> trace --> claims    >--> alignment + relation scoring
    +--> [node 4: Phi]     --> trace --> claims   /            |
    +--> [node 5: Mistral] --> trace --> claims  /             v
                                                  canonical propositions
         (no inter-node communication)                        |
                                                              v
                                              unique-source evidence aggregation
                                                              |
                                                              v
                                               dependency-closed AND/OR derivation
                                                              |
                                                              v
                                                     verbalisation --> answer
```

### 4.1 Node generation

Each node is a complete model on its own device. Nodes receive the prompt and may receive
an injected expert role that encourages a different framing, discipline, or solution
strategy.

Model-family diversity and role-prompt diversity are separate experimental factors. The
spike uses the 2×2 design in `EXPERIMENT.md`; it does not attribute role-induced
divergence to architecture. In a deployed WCT configuration, the combined diverse-family,
diverse-role cell is used only if both factors earn their place.

Nodes never see each other's output. This is deliberate and it is what distinguishes WCT
from debate methods: independence is the thing being measured, so contaminating it
destroys the measurement.

Client behaviour: async fan-out, per-node timeout, proceed on k-of-N returned. A dead or
slow node reduces the claim pool rather than failing the query. Tensor-parallel serving
has no equivalent property. This graceful degradation is a genuine differentiator for
mixed consumer hardware with real straggler variance, and it should be stated explicitly
in any pitch.

### 4.2 Claim and inference extraction

For the Claim A experiment, one fixed extractor processes every trace. This isolates the
generation hypothesis from model-specific self-extraction. For Claim B, the same
schema may later run on each producing node so raw traces remain local.

Each extracted claim carries:

- `text`, `agent`, and global `uid`;
- `polarity` where explicit negation is present;
- `depends_on`, the **complete set** of prerequisite claim ids for that inference;
- `confidence`, retained as an uncalibrated covariate rather than trusted probability;
- `source_span`, locating the claim in the emitted rationale; and
- optional `terminal_for`, identifying which proposed answer or conclusion it supports.

Dependency depth is recomputed centrally from the extracted DAG. Raw depth and normalised
depth may be reported, but neither is allowed to create extra votes.

One model may produce four steps, another eleven, and another a dense paragraph.
This is why rigid step-index alignment is invalid. Claim instances still require explicit
alignment into propositions before they are comparable; “claim-level” does not make that
measurement problem disappear.

### 4.3 Proposition alignment and relation measurement

Pairwise models are measurement instruments. They align text instances; they do not create
additional sources of evidence.

1. **Prefilter.** Embed claims and retain top-k semantically close candidates. Cosine is
   used only for retrieval, not multiplied into the final evidence score.
2. **Directional judge.** Store NLI probabilities for both directions of every shortlisted
   pair.
3. **Alignment.** Treat high bidirectional entailment as evidence that two claim instances
   express one canonical proposition. Use constrained clustering and audit transitivity
   errors.
4. **Polarity.** Map explicit denial or high contradiction to a negative observation of
   the proposition. Preserve `neutral`/unresolved rather than forcing every pair into
   agreement or contradiction.
5. **Deduplication.** Collapse same-agent paraphrases and cap the agent at one observation
   per proposition.

NLI probabilities are not assumed calibrated on the target domains. The experiment
measures alignment precision/recall and relation confusion on a labelled subsample, stores
raw probabilities, and freezes thresholds on calibration data.

After alignment, the central object is:

```text
Proposition {
    canonical_text,
    observations: {agent -> affirm | deny | missing},
    source_claims,
    alignment_uncertainty,
}
```

There is no `O(M²)` evidence bonus. Pairwise comparisons merely recover these `M`
source-level observations.

### 4.4 Proposition aggregation

The primary mathematical baseline is unique-source aggregation.

**WCT-U:**

```text
score_U[z] = Σ_m 1[X[m,z]=affirm] - Σ_m 1[X[m,z]=deny]
```

Missing observations contribute zero. A normalised version divides by the number of
emitting agents. This is an unsupervised rank score under the exchangeable,
average-better-than-random assumption; it is not a probability.

**WCT-C:** use the reliability-weighted posterior log-odds in §3.1, with parameters fitted
only on calibration items. Report uniform and calibrated variants separately so task
labels do not silently enter an “unsupervised” claim.

Model-reported confidence, raw/normalised dependency depth, model identity, and role are
covariates and ablations. They do not create evidence unless calibration shows held-out
value.

#### Diffusion is an ablation, not the truth model

If proposition-to-proposition support beyond direct co-reference is tested, use a stable,
row-normalised signed diffusion:

```text
P[i,j] = W[i,j] / max(Σ_j |W[i,j]|, epsilon)
a[0]   = proposition_score
a[t+1] = (1-alpha) * a[0] + alpha * P @ a[t]       # 0 <= alpha < 1
```

Absolute row normalisation gives `||P||∞ <= 1`, so the iteration is a contraction for
`alpha < 1`. This proves numerical convergence only. It does not prove that the fixed
point estimates truth, and loops may still reuse correlated evidence. Delete diffusion
unless it adds held-out signal over WCT-U and WCT-C.

### 4.5 Dependency-closed hybrid derivation

Reasoning dependencies are generally conjunctive. If `A` and `B` are both required for
`C`, two pairwise edges cannot represent the inference: it is the hyperedge
`{A,B} -> C`.

Represent the combined reasoning as an acyclic AND/OR structure:

- canonical propositions are OR nodes—different agents may supply alternative
  derivations of the same proposition;
- each extracted inference is an AND node or directed hyperedge whose complete premise
  set must be selected;
- prompt-grounded premises are leaves;
- terminal propositions are candidate answers or conclusions;
- a selected derivation is **dependency-closed**; and
- mutually contradictory propositions cannot coexist unless the output explicitly
  presents them as unresolved alternatives.

Cross-agent handoff now occurs naturally. Equivalent claims merge into one proposition,
and the selected derivation may use an inference supplied by a different agent after that
shared proposition. NLI agreement is not repurposed as a temporal transition.

For a tree-shaped acyclic derivation, a useful experimental energy is:

```text
V(z) = proposition_score(z)
       + max over e with head(e)=z [
             inference_score(e)
             + Σ_{u in premises(e)} V(u)
             - lambda * complexity(e)
         ]
       + terminal_coverage(z, prompt)
```

`complexity(e)` is an explicit prior such as inference-edge count or description length.
It is not model-reported depth. `terminal_coverage` prevents the method from selecting a
short but incomplete argument.

For WCT-U, `inference_score` and `terminal_coverage` are frozen label-free ranking scores
from the extraction/relevance instruments; they are not probabilities. WCT-C may calibrate
them on labelled derivations. The two variants must use the same candidate structures so
calibration is the only distinction.

This recurrence is exact only under the stated acyclic, additive, tree-shaped
approximation. With shared subproofs or dependent proposition scores it is an energy
function, not a calibrated proof probability. The spike must label it accordingly.

Implementation can use a bipartite DAG of proposition nodes and inference nodes rather
than a specialised hypergraph library. Dynamic programming over topological order selects
the best dependency-closed derivation. If extraction cannot reliably recover complete
premise sets, stop; a linear heaviest path is not an acceptable fallback for
multi-premise reasoning.

### 4.6 Verbalisation

The orchestrator receives the prompt and selected dependency-closed derivation only:
canonical propositions, inference links, source provenance, and explicitly unresolved
contradictions. It does not receive unselected top-k claims or raw traces. This prevents a
capable verbaliser from silently repairing the selector with outside context.

**Architectural commitment, made explicitly here because it is easy to drift:** the
intelligence lives in proposition aggregation and derivation selection, not in the
orchestrator model. If the
orchestrator becomes a large model reasoning over all raw traces, WCT is just a big model
with small-model scaffolding, which is a weaker and less interesting claim. Keep the
orchestrator starved of context.

This also matters for Claim B. Long-context prefill is compute-bound, which is precisely
where Apple Silicon is weakest. Feeding 40k tokens into the orchestrator would route the
slowest operation onto the least suitable hardware. Distributing claim extraction and
relation measurement keeps the orchestrator's input small and the cluster busy on work it
is actually good at.

---

## 5. Stack

| Layer | Choice | Note |
| --- | --- | --- |
| Nodes | llama.cpp or MLX servers | OpenAI-compatible endpoints so the client stays uniform |
| Client | `httpx` | sequential cached calls in Claim A; async k-of-N only for Claim B |
| Prefilter | local `nomic-embed-text-v1.5` endpoint | verified on the spike host; retrieval only |
| Relations | pinned NLI model after calibration | pairwise measurement, not independent evidence |
| Propositions | small custom clustering + numpy | one source, one observation, per proposition |
| Diffusion ablation | `scipy.sparse` + numpy | row-normalised contraction; delete unless useful |
| Derivation | bipartite AND/OR DAG + dynamic programming | dependency-closed selection, no linear-path fallback |

---

## 6. Evaluation

### 6.1 Dataset

Use different datasets for different inferential jobs:

- **Mechanism tests:** checkable math, logic, causal-rule microworlds, and constrained
  cases where proposition truth and dependencies can be labelled. These are allowed here
  because E1 needs ground truth.
- **Final gate:** open-ended analysis, design critique, multi-constraint tradeoff, and
  causal explanation where answer-level voting is structurally weak. Use a criterion-level
  rubric with reference facts or constraints.

Do not infer open-ended performance from a mechanism win on GSM8K/MATH-like items. Do not
infer that agreement lacks signal merely because it loses to answer voting on a dataset
where voting is near-optimal.

### 6.2 Baselines

1. Single best model selected on calibration data.
2. Answer-level cross-model consensus where an operational answer exists.
3. **Naive synthesis:** the same final model reads all N traces and writes an answer.
4. **Graph-blind matched derivation:** match WCT's number of propositions, dependency
   depth, and handoffs without using proposition scores; feed it to the identical
   verbaliser.

Naive synthesis is the project-level comparison. The graph-blind matched derivation is the
attribution comparison: it distinguishes structural selection from the prompt advantage
of giving a model a short claim set.

Report WCT-U and WCT-C separately. WCT-U is primary for the unsupervised claim; WCT-C
shows the value available when calibration labels are permitted.

### 6.3 Kill criterion

**If dependency-closed WCT-U does not beat naive synthesis and the graph-blind matched
control by the pre-registered smallest worthwhile effects, stop.**

Do not begin cluster distribution or prefill benchmarking until this clears. The topology
argument only matters if the method has signal.

### 6.4 Ablations

Run in the same pass. These tell you which parts to delete.

| Ablation | Question answered |
| --- | --- |
| WCT-U vs WCT-C | does model/domain calibration materially change the result? |
| One-hop unique-source score vs diffusion | does propagation add signal or recycle evidence? |
| One vote per source vs uncapped claim instances | was verbosity manufacturing consensus? |
| Same-family/same-role, same-family/diverse-role, cross-family/same-role, full WCT | which diversity factor is doing work? |
| No complexity prior | does simplicity help after coverage is controlled? |
| Linear path diagnostic | how much validity is lost by ignoring conjunctive dependencies? |
| Matched random AND/OR derivation | does score-guided dependency selection add value? |

The factorial diversity comparison is the most important for the family-diversity claim.
If same-family sampling performs equivalently on the untouched test split, WCT reduces to
a structured synthesis method plus the independent deployment story.

---

## 7. Build order

**Before inference — mathematical smoke test.**
Simulate proposition truth, source reliability, dependence, coverage, alignment error,
and inference-edge error. Verify that WCT-U, WCT-C, diffusion, and AND/OR selection behave
as expected in known regimes. Produce a failure-surface plot; do not debug basic
identifiability with paid model calls.

**Week 1 — measurement chain.**
Sequential cached generation, common extraction, proposition alignment, blinded labels,
and unique-source WCT-U/WCT-C scoring. Hand-inspect extraction, alignment, and dependency
sets before any structural selection. If propositions cannot be recovered reliably,
nothing downstream can work.

**Week 2 — derivation and final gate.**
Run the diffusion ablation, build the bipartite AND/OR DAG, directly test dependency
closure and cross-agent handoffs, then verbalise only paths that pass. Evaluate against
naive synthesis and the graph-blind matched control. `EXPERIMENT.md` owns the exact
schedule, thresholds, splits, and sequential stop decisions.

**Only if the gate clears — hardware.**
Measure prefill throughput at target context length on the actual cluster. That single
number determines whether the distributed-extraction design is necessary or merely nice.

---

## 8. Known weaknesses

Stated plainly so they are not rediscovered as surprises.

1. **Truth is not identifiable from agreement alone.** WCT-U depends on the
   average-better-than-random and limited-dependence assumptions. A unanimously wrong
   panel remains possible and produces a shared-error floor.

2. **Fixed-panel inference.** The spike estimates one named panel over an item
   distribution. It cannot support a population claim about architectures without
   replication across independently selected panels.

3. **Capability and dependence interact.** A weaker but decorrelated model may add
   information; a stronger correlated model may add almost none. Vendor diversity is not
   a sufficient statistic. WCT-C can model reliability but becomes a calibrated method,
   not the pure unsupervised variant.

4. **Shared measurement bias.** Every rationale is projected through one extractor,
   embedding model, and NLI model. Independent generators, dependent measurement stack.
   Robustness checks reduce but do not eliminate this surface.

5. **Coverage gaps and rare insights.** Anything nobody generates is unrecoverable. A
   correct but isolated insight may rank below commonplace consensus. Targeted re-querying
   is a plausible extension but is excluded from the spike.

6. **Dependency extraction is harder than claim extraction.** Missing one co-premise can
   make an apparently coherent derivation invalid. The direct E2.5 path audit is
   load-bearing.

7. **Open-ended truth is not always binary.** The binary `Y` model is a mechanism probe.
   Real design critiques contain value judgements, uncertainty, and partially compatible
   alternatives; E3 must use criterion-level utility rather than pretend every proposition
   has an objective Boolean truth.

8. **Operational load.** N model families means N tokenisers, quantisations, prompt
   formats, endpoints, and licences. On-prem, this can dominate the algorithmic work.

---

## 9. Salvage value

If Claim A fails, the orchestration layer still has standalone value: distributing
heterogeneous models across mixed local hardware with straggler tolerance, partial-result
assembly, and k-of-N gather is useful infrastructure regardless of whether convergence
scoring wins. **Build it as a separable component** so that it survives a negative result.

---

## 10. Discipline

Research timelines are unbounded by nature and this problem is seductive enough to
quietly absorb a quarter. Two weeks, one gate, one explicit go/no-go decision. Continuing
past the gate should be a deliberate choice made against data, not a drift.

---

## Appendix: worked example from the original notes

This table is retained as provenance, not as the executable algorithm. Its multiplicative
amplitude, uniform per-step loss, and linear path do not satisfy the assumptions in §3.1
or the dependency-closure requirement in §4.5.

Assume 0.25 loss per step, interaction doubles (note: the doubling is the naive form,
superseded by sublinear gain in section 4.4).

| | Wave 1 | Wave 2 | Wave 3 | Wave 4 |
| --- | --- | --- | --- | --- |
| CoT 1 | 0.25 | 1 | 0.5 | n/a |
| **CoT 2** | **1.5** | **2** | **1** | n/a |
| CoT 3 | 0.25 | 0.50 | 0.25 | **0.25** |

Original selected path: CoT2 w1 (1.5) -> CoT2 w2 (2) -> CoT2 w3 (1) -> CoT3 w4
(0.25).

The surviving idea is the source switch. In the current design it occurs by merging an
equivalent proposition and selecting a dependency-complete inference from another agent,
not by following the largest amplitude through pairwise NLI edges.
