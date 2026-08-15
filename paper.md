# The Same Pre-Registered Test Passes on One Panel and Fails on Another: Panel and Corpus Dependence in Cross-Model Proposition Aggregation

Jeremiah Mannings, Andryo Marzuki

*Draft v2, 9 August 2026. All numbers are read from the run artifacts listed in Appendix B.*

---

## Abstract

Methods that pool several language models treat agreement between them as evidence, almost always at the level of the final answer. We test the proposition-level version of that premise under pre-registration: the design, the arms, the metrics and the smallest effect worth acting on were frozen before any inference ran. We then ran the identical protocol on two independently selected panels of three model families each, sharing no family between them, over the same 150 ProofWriter OWA items, with the same extractor, the same embedding and NLI stack, and the same analysis code. The registered primary, held-out delta log-loss against a covariate baseline, returns **−0.159 nats [−0.249, −0.070], a decisive stop, on one panel and +0.277 [+0.223, +0.343], a decisive go, on the other.** Nothing differs between those two runs except which three models produced the rationales. A second dependence acts on the same metric from a different direction: 48% of the pre-registered proposition set comes from theories stated without negation, in which no positive proposition can ever be disproved, and that stratum has a measured prevalence of exactly 1.0000 on both panels. Removing it moves the weaker panel's primary from −0.159 to +0.001 [−0.104, +0.108] and the stronger panel's from +0.122 to +0.277. The method is the smallest of the three terms: what a paper would report here is a joint property of the aggregation rule, the panel it was run on, and whether the corpus was capable of containing something for the panel to be wrong about. One finding is invariant across both panels and both strata, and it is the one we would act on: counting claim instances rather than distinct agents destroys the signal completely, at AUROC 0.502–0.554 against 0.897–1.000 for unique-source support. Agreement carries information about which agents assert a proposition and essentially none about how much text they produce. We also report that our registered directional prediction on error correlation failed on the first panel and was not even computable on the second, where two of three models answer every item correctly and the correlation is undefined rather than small.

---

## 1 Introduction

A method that runs a prompt across several models and pools the results has to say what the pooling is doing. The usual answer is that independently trained models make different mistakes, so agreement concentrates on the correct answer while errors scatter. That premise is well supported at the level of the final answer. Liu (arXiv:2607.10139) studies cross-model consensus across seven benchmarks, identifies error decorrelation as the mechanism, and closes the entire gap to an oracle selector on competition mathematics.

What is not established is whether the premise survives being moved down a level, from the answer to the individual propositions inside a rationale. That move is what would make the idea useful where there is no extractable answer to vote on, and it is a harder measurement problem: propositions must be recovered from free text and aligned across models before anything can be counted, and a model that writes more sentences must not thereby acquire more votes.

We set out to test that. What we found first was that the test is answerable only relative to a panel and a corpus, and that the size of those dependencies dwarfs the thing we were trying to measure.

The pre-registration is what makes this visible rather than merely suspected. Had we run one panel we would have written one of two confident papers, either a method that works or a method that does not, and both would have been true statements about the run and misleading statements about the method.

**What we claim.** Cross-model proposition agreement carries real signal about proposition truth on both panels, it survives a within-item permutation null that controls for item difficulty at p = 0.001 on both, and essentially all of it comes from capping each agent at one vote. We do not claim it passes its registered primary gate, because on one of the two panels it decisively does not.

**Contributions.**

1. A pre-registered proposition-level test run on two independently selected panels over identical items and identical instrumentation, in which the registered primary flips from a decisive stop to a decisive go with the panel alone.
2. Identification of a corpus property that moves the same metric by up to 0.28 nats: theories in which no proposition can be false, 48% of the pre-registered set, at a measured prevalence of exactly 1.0000 on both panels.
3. A direct measurement of the one-vote-per-source assumption that this literature normally asserts rather than tests, replicated on both panels: AUROC 0.502–0.554 for claim-instance counting against 0.897–1.000 for unique-source support.
4. Evidence that a three-state Dawid–Skene estimator recovers per-agent reliability from the unlabelled vote matrix, ordering each panel exactly as labelled answer accuracy does.
5. A full account of what failed, including a registered prediction that failed in sign on one panel and was undefined on the other, a degenerate confidence interval we decline to interpret, and an alignment audit whose yardstick proved too partial to support a precision figure.

---

## 2 Related work

**Cross-model consensus at the answer level.** Liu (arXiv:2607.10139) is the closest prior result. It treats a panel of independently trained models as a jury, uses the structure of agreement rather than any model's score of another as the verification signal, and beats both self-consistency and trained verifiers. It operates on final answers. Self-consistency resamples one model and inherits its correlated errors; Mixture-of-Agents adds a synthesis layer, but the synthesis is a single model reading everything with no structural scoring; Graph of Thoughts plans a reasoning graph rather than recovering one from independent traces; multi-agent debate lets agents see each other, which produces herding and destroys the independence that makes agreement informative.

**Step-level and process supervision.** Process reward models score intermediate steps but need supervision or a definable first-error position. Unsupervised process reward models (arXiv:2605.10158) remove the labelling requirement but operate within a single model family, where errors are correlated by construction.

**Aggregating noisy sources.** Our observation model is Dawid–Skene: latent truth, per-source sensitivity and specificity estimated from the agreement pattern alone. Its limits apply here. It corrects heterogeneity, not dependence, so it remains biased under correlated sources, and agreement alone admits a label-swapping symmetry broken only by an anchor, in our case initialisation at majority vote, encoding the assumption that the average source is better than random.

**What is new.** Not the aggregation model, and not the observation that models decorrelate. What we contribute is the proposition-level measurement run under pre-registration on two panels, and the finding that its verdict is a joint property of the panel and the corpus rather than of the aggregation rule.

---

## 3 Method

### 3.1 Two panels

Both panels are three distinct model families, panel size odd because an even panel decides a large fraction of binary propositions by tie: at M = 4 and p = 0.70 the exact-tie rate is 26.5%, and odd panels give zero.

| | panel A (local) | panel B (OpenRouter) |
| --- | --- | --- |
| families | `thinkingcap-qwen3.6-27b`, `laguna-xs-2.1`, `ornith-1.0-35b` | `nvidia/nemotron-3-super-120b-a12b`, `openai/gpt-oss-20b`, `google/gemma-4-26b-a4b-it` |
| role in pre-registration | replication | primary |
| generations | 850 unique, 0 errors | 660 unique, 0 errors |

The panels share **no model family**, which is what makes B a replication with an independently selected panel rather than extra sample size on the same one. `poolside/laguna-s-2.1` was available on OpenRouter and excluded for exactly this reason, since poolside also supplies panel A. Models excluded for other reasons are recorded in the pre-registration: `deepseek-v4-flash` fails to load, `ornith-1.0-35b-mtp-apex` is a variant of a model already in panel A, `inclusionai/ling-3.0-flash` is no longer served free.

Model-family diversity and role-prompt diversity are separate experimental factors, crossed in a 2×2, because giving nodes different expert roles to encourage divergence otherwise confounds the two. Roles rotate by Latin square so role is orthogonal to agent identity. The same-family cell is self-consistency: one model, three seeds, and we verified that sampling genuinely varies under seed before relying on it.

### 3.2 Items and ground truth

ProofWriter OWA (`hitachi-nlp/proofwriter_processed_OWA`, `depth-3`, `test`), which retains the proof trees most redistributions strip. Each item must carry at least one conjunctive rule, so two-premise inferences actually occur, and the target question must sit at proof depth ≥ 2 so it needs derivation rather than lookup. 150 items, split 50 calibration / 100 test at the item level. Both panels see the identical item set and the identical split.

Every candidate proposition already carries a truth value derived from the theory's closure, so proposition truth is available by construction and no adjudication is required. Propositions are canonicalised to positive polarity, because ProofWriter states each statement in both forms and treating them as two propositions would let one belief vote twice. Unknown propositions are excluded from the primary and reported separately.

### 3.3 Instrument

One common extractor processes every trace, so that a model which writes tidy bullet points does not score as a better reasoner for being a better formatter. It is deterministic, consumes no inference, and keeps sentences that both name an entity of the theory and predicate something of it. Both conditions are needed, since traces are full of sentences that mention entities while asserting nothing.

Alignment maps claims to canonical propositions using local embeddings for retrieval and a pinned CPU NLI model (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`), raw bidirectional probabilities stored unthresholded. Cosine decides only which pairs are worth an NLI call and never enters the evidence score. Both panels use the identical stack; when the embedding server went down mid-study we waited for it rather than substituting an in-process model, because running one panel through a different embedding runtime would have confounded the panel comparison with a change of measurement stack.

**Polarity is read from which surface form a claim matches, not from a contradiction against the positive form.** This is the most important implementation decision here and we got it wrong first. ProofWriter propositions are permutations over a small closed vocabulary, so two *different* propositions about the same entities are usually scored as a contradiction: "the mouse sees the bald eagle" against "the bald eagle sees the mouse" returns contradiction at 0.996. Reading that as a denial makes every agent deny nearly every proposition it never mentioned. Because ProofWriter supplies the negated surface form, each proposition contributes two alignment targets, which keeps NLI doing alignment only.

Each agent contributes at most one observation per proposition; where an agent's own claims conflict the highest-scoring alignment wins and the conflict is counted.

### 3.4 Arms and statistics

`WCT-U` is uniform signed unique-source support. `WCT-EM` is three-state Dawid–Skene with truth latent, estimating per-agent sensitivity, false-positive rate and truth-dependent coverage from the vote matrix alone; it consumes no truth labels. `WCT-C` fits the same model on labelled calibration items only. `uncapped` counts claim instances instead of sources. The covariate baseline is a logistic regression on depth, number of emitting agents, claim count and proposition length (everything except the signed cross-agent support), and receives identical calibration treatment including a fitted temperature.

Everything is item-blocked, because propositions are nested within items and a proposition-level bootstrap would let item difficulty masquerade as proposition-level signal. Intervals are 95% item-block bootstraps over 2,000 resamples; the null permutes truth *within* each item over 1,000 permutations, which asks whether support predicts truth beyond what item difficulty already explains.

---

## 4 Results

### 4.1 The registered primary flips with the panel

Same items, same split, same extractor, same embedding and NLI models, same analysis code, same frozen delta of 0.02 nats. The only difference is which three models wrote the rationales.

**Registered primary, held-out delta log-loss against the covariate baseline, WCT-EM:**

| stratum | panel A (local) | panel B (OpenRouter) | flips |
| --- | --- | --- | --- |
| all items (frozen primary) | **−0.1588** [−0.2495, −0.0702] → **stop** | **+0.1225** [+0.0367, +0.1972] → **go** | yes |
| negation theories | +0.0011 [−0.1041, +0.1080] → inconclusive | **+0.2774** [+0.2229, +0.3428] → **go** | yes |

Both intervals on panel A's frozen primary lie entirely below zero; both on panel B lie entirely above the registered delta. This is not a marginal disagreement that a larger sample would resolve: the two runs give confidently opposite answers to the registered question.

The arm tables show where the difference comes from:

| arm | A: log-loss | A: AUROC | B: log-loss | B: AUROC |
| --- | --- | --- | --- | --- |
| WCT-C | 0.1812 | 0.9004 | **0.0973** | 0.9920 |
| WCT-EM | 0.3847 | 0.8910 | **0.1069** | 0.9920 |
| WCT-U | 0.3386 | 0.9001 | **0.1234** | 0.9911 |
| covariate baseline | 0.2097 | 0.5979 | 0.2112 | 0.6562 |
| uncapped | 0.2234 | 0.5069 | 0.2243 | 0.5239 |
| prevalence only | 0.1984 | 0.500 | 0.1966 | 0.500 |

The baselines are nearly identical across panels (covariate 0.2097 against 0.2112, prevalence 0.1984 against 0.1966), which is what one expects, since they depend on the items rather than the models. Everything that moves is in the WCT arms. Panel B's models are simply more reliable at the proposition level, so their agreement is both better ordered and better calibrated, and the same fitted-temperature machinery that had to shrink panel A's scores by 2.78 needs only 1.67 for panel B.

On panel A the method ranks well and calibrates badly. On panel B it does both. The registered metric was sensitive to the difference; the descriptive one was not.

### 4.2 Half the corpus could not contain a false proposition

The primary is a log-loss comparison, so it is decided substantially by how hard the base rate is to beat. That base rate is a property of the corpus, and a structural one. ProofWriter theories come in *Noneg* and *Neg* families; in a Noneg theory nothing is stated with negation, so no positive proposition can be disproved: it is provable or it is Unknown.

| stratum | panel A props | A prevalence | panel B props | B prevalence |
| --- | --- | --- | --- | --- |
| all items | 502 | 0.9442 | 484 | 0.9401 |
| negation theories | 260 | 0.8923 | 250 | 0.8840 |
| non-negation theories | 242 | **1.0000** | 234 | **1.0000** |

Prevalence is exactly 1.0000 on both panels, over 242 and 234 propositions respectively. Truth discrimination is undefined there by construction, and the stratum accounted for 48% of the pre-registered proposition set.

Removing it moves panel A's primary from −0.159 to +0.001 and panel B's from +0.122 to +0.277. It does not touch panel A's ranking result at all: within-item AUROC stays at 0.9048 [0.8333, 1.0000] and the permutation p stays at 0.001, because AUROC is invariant to the base rate that log-loss is dominated by.

We report the frozen all-items primary as the registered outcome on both panels and its verdicts stand. But a paper reporting this method could move its headline number by 0.28 nats through corpus composition alone, without touching the method, and the direction of that move differs by panel.

### 4.3 The one finding that survives everything

| scoring rule | A, all | A, neg | B, all | B, neg |
| --- | --- | --- | --- | --- |
| unique-source signed support | 0.9001 | 0.8970 | 0.9911 | **1.0000** |
| claim instances, uncapped | 0.5069 | 0.5017 | 0.5239 | 0.5544 |

Counting how many times a proposition is asserted is worth nothing, on either panel, in either stratum, at 0.502 to 0.554 against a chance value of 0.5. Counting how many *distinct agents* assert it takes the identical extraction output to between 0.897 and 1.000. The one-vote-per-source rule is normally stated as a modelling assumption defended on the grounds that verbosity should not become voting power. It is not a refinement; it is the entire signal, and it is the only result here that is stable across both panels and both strata.

### 4.4 Perfect separation on panel B, and why we do not quote its interval

On panel B's negation stratum, WCT-U attains AUROC exactly 1.000. We checked it directly rather than trusting the pipeline. On the 167 held-out propositions:

| WCT-U score | n | true | false |
| --- | --- | --- | --- |
| −3 | 4 | 0 | 4 |
| −2 | 6 | 0 | 6 |
| −1 | 4 | 0 | 4 |
| 0 | 3 | 3 | 0 |
| +1 | 37 | 37 | 0 |
| +2 | 61 | 61 | 0 |
| +3 | 52 | 52 | 0 |

Every proposition with net support below zero is false and every one at or above zero is true. The separation is real and it is label-free: WCT-U consumes no truth labels, so nothing here can be leakage from the outcome.

It rests on **14 negatives**. The bootstrap returns a 95% interval of [1.000, 1.000], and that interval is degenerate rather than precise: with perfect separation every resample is also perfectly separated, so the procedure cannot express uncertainty. We report the point estimate and decline to interpret the interval. With 14 negatives all correctly ordered, a rule-of-three bound puts the plausible error rate on negatives at up to roughly one in five, which is a very different statement from an interval of zero width.

### 4.5 E0: the panels are at ceiling, and on panel B the dependence is not merely small but undefined

| panel, cell | per-agent accuracy | consensus | ρ | M_eff |
| --- | --- | --- | --- | --- |
| A, cross-family diverse role (n=120) | 0.858 / 0.958 / 0.992 | 0.9833 | 0.080 | 2.58 |
| A, same-family same role (n=50) | 0.987 mean | 0.9800 | 1.000 | 1.00 |
| B, cross-family same role (n=30) | 1.000 / 1.000 / 1.000 | 1.0000 | **undefined** | 3.00 |
| B, cross-family diverse role (n=149) | 0.926 / 1.000 / 1.000 | 1.0000 | **undefined** | 3.00 |

We registered the directional prediction that cross-family panels carry lower residual error correlation than same-family ones. On panel A it fails in sign: cross-family ρ = 0.080 against same-family ρ = −0.022, a reduction of −0.102. On panel B it cannot be evaluated at all, because two of the three models answer every item correctly and there is no error variance to correlate: ρ is undefined in every cell, not small.

We do not read either as evidence against family diversity. Panel A's ρ = 1.000 in the same-family cell comes from essentially one shared error. Same-wrong-answer convergence is 0.000 in every cell of both panels: the panels almost never agree on a wrong answer because they almost never produce one. Consensus fails to beat the best single agent in every cell of both panels.

The content of E0 is the ceiling itself, and panel B makes the point more sharply than panel A. At a single-model accuracy of 1.000 there is no headroom for any selector to recover, and this is what a pre-inference feasibility check exists to catch before quota is spent.

### 4.6 Measurement audit

The aligner is checked with a probe involving no model output: each proposition's own surface text and its negated form are fed back as pseudo-claims and required to align to themselves with the right polarity.

| panel | probes | self-identification | wrong proposition | wrong polarity |
| --- | --- | --- | --- | --- |
| A | 1,483 | 0.9724 | 41 | **0** |
| B | 1,483 | 0.9724 | 41 | **0** |

The probe depends only on the items, so it is identical across panels by construction and confirms that the two panels were measured through the same instrument. Zero polarity errors matters on a closed vocabulary where argument-order permutations score as confident contradictions.

The pipeline discards heavily, and less so on panel B: 24,621 claim instances become 1,197 observations on panel A with 853 same-agent conflicts, against 15,599 into 1,121 with 195 conflicts on panel B. Panel B's models write shorter, less repetitive traces (2,395 characters against 5,601) and contradict themselves within a trace far less often, which is a plausible part of why their agreement is cleaner.

We attempted a second audit against a lexical reference alignment and it did not work well enough to quote. A first, looser version silently matched *rule* restatements to propositions: "if something sees the mouse then it is cold" contains "the mouse is cold" without asserting it. The tightened version fires on too few observations to support a precision figure, so we report recall (0.690 on panel A) and deliberately report no precision, since an aligner output absent from a partial reference is unlabelled rather than wrong.

---

## 5 Limitations and confounds

**Two panels is two, not a sample.** We show the verdict differs between two independently selected panels. We cannot say how the effect is distributed over panels, which would need many more, and we cannot rule out that panel B is simply the better panel and panel A the anomaly. What the pair establishes is that a single-panel result does not determine the registered verdict, which is enough to change how such a study should be reported.

**Both panels are at ceiling on answers, and panel B severely.** Per-agent answer accuracy reaches 1.000 for two of three models on panel B. Everything in E0 is compressed against that, and E1's proposition set inherits it: agents mostly emit propositions they successfully derived.

**Panel B's headline rests on 14 negatives.** AUROC 1.000 with a zero-width bootstrap interval is a small-sample artefact of perfect separation, not a precise estimate, and we have flagged it as such rather than quoting the interval.

**The primary metric was a poor choice for this corpus.** At prevalence 0.94 a log-loss comparison is largely a test of who best predicts the base rate. We registered it in advance and are not free to swap it afterwards, and have not; but the registered primary and the registered question were less well aligned than they looked before data existed.

**The corpus stratification is post-hoc in timing, not in logic.** That a Noneg theory cannot disprove a positive proposition is a fact about ProofWriter establishable before running anything. We did not establish it in advance, so the frozen primary is reported first and the stratum second.

**Shared measurement stack.** Every rationale passes through one extractor, one embedding model and one NLI model. The generators are independent; the measurement is not. The pre-registered robustness check with a second embedding/NLI stack on a 20% subsample has not been run.

**Alignment is anchored to a known proposition set.** That set is derivable from the theory's facts and rules without any truth value and so consumes no labels, but it is easier than the general case where propositions must be discovered by clustering. These numbers measure aggregation given good alignment, plus a separate measurement of alignment quality.

**What we do not claim.** We do not claim the method passes its registered gate, since on panel A it does not. We do not claim dependency-closed derivation works, since E2, E2.5 and E3 were not run. We do not claim proposition-level aggregation beats answer-level consensus, which we did not measure.

---

## 6 Conclusion

We pre-registered a test of whether cross-model proposition agreement predicts proposition truth, and ran it twice over identical items with identical instrumentation on two panels sharing no model family. The registered primary returns −0.159 nats, a decisive stop, on one panel and +0.277, a decisive go, on the other. A corpus property acting on the same metric, whether the theory permits a proposition to be false at all, moves it by up to 0.28 nats, and 48% of our pre-registered proposition set was structurally incapable of containing a negative, at a measured prevalence of exactly 1.0000 on both panels.

The signal is real on both panels: the within-item permutation null is rejected at p = 0.001 in every stratum where it is defined. But the reported verdict is a joint property of the aggregation rule, the panel, and the corpus, and the aggregation rule is the smallest of the three. Anyone reporting that cross-model agreement does or does not work should say which panel and which corpus, because we have measured both dependencies and each is larger than the effect being reported.

One thing is invariant and worth acting on. Counting distinct agents rather than claim instances is the difference between AUROC 0.50 and AUROC 0.90–1.00, on both panels, in both strata. Whatever else agreement is measuring, it is measuring who asserts a proposition and not how much anyone writes.

---

## Author contributions and use of AI assistance

The measurement instrument, the pre-registration and the evaluation runs reported here were produced with an AI research assistant working under the authors' direction. The authors chose the questions, made the design calls, and are responsible for every claim. Because each number is traceable to the artifacts listed in Appendix B, a reader who would rather check the analysis than take it on trust is able to.

## Appendix A: reproduction

- Panel A: `thinkingcap-qwen3.6-27b`, `laguna-xs-2.1`, `ornith-1.0-35b`, served locally over an OpenAI-compatible endpoint that holds one model at a time, so generation is sequential and model-major.
- Panel B: `nvidia/nemotron-3-super-120b-a12b:free`, `openai/gpt-oss-20b:free`, `google/gemma-4-26b-a4b-it:free` via OpenRouter. Quota measured at the key, not read off the catalogue: 1,000 free requests/day, usage 0 at freeze. The E0 factorial was run on a 30-item calibration subset so the request cap fit that envelope with 20% retry allowance (660 unique calls, 792 with retries).
- Decode: temperature 0.7, max_tokens 3000, seeds 1–3.
- Items: `hitachi-nlp/proofwriter_processed_OWA`, config `depth-3`, split `test`; conjunctive rule required; target depth ≥ 2; 150 items; item-level split 50/100 at seed 20260807. Identical for both panels.
- Measurement: local `nomic-embed-text-v1.5` for retrieval (top-k = 8); `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` on CPU, raw probabilities stored unthresholded; alignment threshold 0.60 frozen at R0. Identical for both panels.
- Resampling: 2,000-resample item-block bootstrap; 1,000 within-item truth permutations; seed 20260807.
- Generation: 850 unique calls on panel A, 660 on panel B, 0 errors in the final cache for either.
- All analysis re-runs over the immutable content-hashed cache at zero inference cost.

## Appendix B: artifact map

| artifact | contents |
| --- | --- |
| `prereg.yaml` | the pre-registration frozen at R0: both panels, deltas, arms, exclusions, measured quota |
| `out/e1_summary.json` | panel A: all three strata, arms, primary/co-primary, nulls, EM parameters, alignment audit |
| `out/e1_summary_openrouter.json` | panel B, same structure |
| `out/e0_summary.json`, `out/e0_summary_openrouter.json` | §4.5: per-cell accuracy, ρ, M_eff, double-fault, dose–response, registered contrast |
| `out/result_package.json` | gate decisions per panel, the explicit panel comparison, and the negative-results list |
| `out/dataset_manifest.json` | item ids, depth and answer histograms, conjunctive-rule counts |
| `out/generation_index.json` | every generation: item, agent, model, role, seed, cell, trace length, error |
| `out/m0_ceiling.txt`, `out/m0_simulate.txt` | pre-inference invariants I1–I14 against known ground truth |
| `out/cache/` | immutable content-hashed generation, embedding and NLI artifacts |
| `wct/`, `exp/`, `m0/` | instrument, experiment drivers, pre-inference analysis |
| `DECISIONS.md`, `GOTCHAS.md` | design decisions with rationale; measured environment constraints |

## References

- Liu, N. *LLMs as a Jury: Cross-Model Consensus Can Outperform Process Reward Models for LLM Reasoning.* arXiv:2607.10139.
- *Unsupervised Process Reward Models.* arXiv:2605.10158.
- Dawid, A.P., Skene, A.M. *Maximum Likelihood Estimation of Observer Error-Rates Using the EM Algorithm.* JRSS-C 28(1), 1979.
- Tafjord, O., Dalvi Mishra, B., Clark, P. *ProofWriter: Generating Implications, Proofs, and Abductive Statements over Natural Language.* Findings of ACL 2021.
- Laurer, M., van Atteveldt, W., Casas, A., Welbers, K. *Less Annotating, More Classifying.* Political Analysis, 2024.
- Li, Y., Rubinstein, B., Cohn, T. *Exploiting Worker Correlation for Label Aggregation in Crowdsourcing.* ICML 2019.
