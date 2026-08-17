# The Flip Was in the Instrument: Two Pre-Registered Cycles of Cross-Model Proposition Aggregation

Jeremiah Mannings, Andryo Marzuki

*Draft v3, 17 August 2026. All registered and post-hoc-diagnostic numbers are read from the run artifacts listed in Appendix B; the exploratory §7 figures derive from an unfrozen toolkit and are labelled accordingly, with their headline values recorded in `DECISIONS.md`. Analyses are labelled REGISTERED (frozen before the data they touch) or POST-HOC/EXPLORATORY throughout.*

---

## Abstract

Methods that pool several language models treat agreement as evidence, almost always at the level of the final answer. We tested the proposition-level version of that premise under pre-registration, twice. In the first cycle, an identical frozen protocol run on two independently selected three-model panels returned opposite verdicts on the registered primary, held-out Δ log-loss against a covariate baseline: **−0.159 nats [−0.249, −0.070], a decisive stop, on one panel and +0.122 [+0.037, +0.197], a decisive go, on the other**, with both intervals excluding zero. A paper reporting either panel alone would have been confident and wrong about the method. Post-hoc diagnosis located the disagreement not in the panels but in the instrument, twice over. First, the registered calibration map, a single fitted temperature, has no intercept, while the baseline it was measured against is a logistic regression fitted with one; giving both sides the same two parameters moved the failing panel from stop to go and turned all twelve panel × stratum × arm combinations positive, while every rank-based measurement was invariant by construction. Second, the corpus could barely contain a falsehood: 48% of propositions came from theories in which nothing can be false, only positive-polarity falsehoods ever survived alignment (0 of 607 negative-polarity propositions were scored), and the test splits held 14–16 negatives. Rather than reporting a post-hoc rescue, we froze a second registration (negation-family corpus with depth-5 enrichment, an intercept-bearing calibration map, three falsifiable predictions) and git-tagged it before any of its generation ran. The central prediction was **confirmed on two panel–corpus configurations sharing no model family with each other, one panel entirely new and one continuing from cycle 1, both on the enriched corpus: +0.220 [+0.160, +0.280] and +0.272 [+0.180, +0.353], both go, at 81 and 65 test negatives**. The other two registered predictions failed: consensus quality does not degrade monotonically with proof depth, and a deny-vote filter that helped one panel hurt the other. One finding is invariant across both cycles, both panels, and every stratum: counting distinct agents rather than claim instances is the difference between AUROC ≈ 0.5–0.6 and AUROC 0.89–1.00. Agreement measures who asserts a proposition, not how much text asserts it.

---

## 1 Introduction

A method that runs a prompt across several models and pools the results has to say what the pooling is doing. The usual answer is that independently trained models make different mistakes, so agreement concentrates on the correct answer while errors scatter. That premise is well supported at the level of the final answer: Liu (arXiv:2607.10139) studies cross-model consensus across seven benchmarks, identifies error decorrelation as the mechanism, and closes the entire gap to an oracle selector on competition mathematics.

What is not established is whether the premise survives being moved down a level, from the answer to the individual propositions inside a rationale. That move is what would make the idea useful where there is no extractable answer to vote on, and it is a harder measurement problem: propositions must be recovered from free text and aligned across models before anything can be counted, and a model that writes more sentences must not thereby acquire more votes.

We set out to test that, and this paper reports what it took to get an answer that survives its own instrument. The first pre-registered cycle produced a result that looked like a finding about models: the same frozen protocol, the same 150 items, the same extractor, embedding and NLI stack, and the same analysis code returned a decisive *stop* on one three-model panel and a decisive *go* on another. Had we run one panel we would have written one of two confident papers, and both would have been true statements about the run and misleading statements about the method.

The second cycle is what distinguishes this paper from a cautionary tale. Post-hoc analysis localised the flip to the one registered metric that is calibration-sensitive (every rank-based measurement agreed across panels) and identified two instrument defects: a calibration map structurally unable to match the base rate its opponent could match, and a corpus in which the propositions a method could be wrong about were nearly absent. Those diagnoses became three falsifiable predictions in a second registration, frozen and git-tagged **before any new generation ran**. One prediction, the central one, was confirmed on both panels under the new corpus, one panel entirely new and one continuing from cycle 1. Two failed. We report all three at the same prominence, because the failures bound what the confirmation means.

**What we claim.** On a corpus capable of containing falsehoods, and under a calibration map with the same degrees of freedom as its baseline, cross-model proposition agreement clears its pre-registered gate on two panels sharing no model family (P1). We do not claim the accompanying depth story (P2, failed) or the deny-filter instrument fix (P3, failed in one direction), and we document one adjudication that is sensitive to how the frozen decision rule is read.

**Contributions.**

1. A two-cycle pre-registered design in which the second cycle tests the first cycle's post-hoc diagnosis as frozen, falsifiable predictions, including the confirmation of the central prediction on both cycle-2 configurations (one panel entirely new, one continuing; +0.220 and +0.272 nats, both go).
2. Identification and prospective repair of two instrument defects that jointly produced a verdict flip in cycle 1: a missing intercept in the registered calibration map (worth the entire flip; an intercept alone at the frozen slope captures 98.8% of the correction), and a corpus in which only 14–16 test negatives were scorable, including the measurement that *zero* of 607 negative-polarity propositions were ever scored by the alignment layer.
3. Two registered failures with verified mechanisms: consensus quality does not decline monotonically with proof depth (the violating bin is statistically indistinguishable from flat, which is itself the lesson about tolerance choice), and a self-contradiction filter on deny votes helps or harms depending on panel trace style (dropped-deny precision 0.373 vs 0.523).
4. A replication, across both cycles and all panels, of the one-vote-per-source result: claim-instance counting reaches AUROC 0.502–0.606 while unique-source support reaches 0.891–1.000.
5. A worked example of registration hygiene failing and being repaired: cycle 1's protocol was never tagged before inference (its own requirement), and the file-timestamp forensics of what can and cannot be established are part of the record; cycle 2's tag precedes every generation call.

---

## 2 Related work

**Cross-model consensus at the answer level.** Liu (arXiv:2607.10139) is the closest prior result: a panel of independently trained models treated as a jury, agreement structure as the verification signal, beating self-consistency and trained verifiers, at the level of final answers. Self-consistency resamples one model and inherits its correlated errors; Mixture-of-Agents adds a synthesis model that reads everything with no structural scoring; multi-agent debate lets agents see each other, which produces herding. Unsupervised process reward models (arXiv:2605.10158) score reasoning steps without labels but within a single model's distribution. Our question is whether agreement carries signal at the proposition level, across models, with each agent capped at one vote per proposition.

**Aggregation with latent truth.** Our primary estimator is a three-state Dawid–Skene model (Dawid & Skene, 1979): truth latent, per-agent sensitivity, false-positive rate and truth-dependent coverage estimated from the vote matrix alone. Silence is a state, not a missing value: under truth-dependent coverage, silence is informative, and the estimator uses it (M0 invariant I4, established on simulation before any inference, showed that both naive treatments of silence fail, in opposite regimes). Correlated sources bias such estimators in known ways (Li, Rubinstein & Cohn, 2019), which is one reason cycle 1 measured residual error correlation directly.

**Pre-registration.** The methodological literature on pre-registration mostly concerns human-subject sciences. The failure mode this paper documents (a frozen comparison that is *unfair in a way nobody anticipated*, so that freezing preserved the unfairness) and the remedy of a second registration testing the first's diagnosis, are, to our knowledge, rarely exhibited in ML evaluation.

---

## 3 Cycle 1: the same test, two verdicts

### 3.1 Design

150 ProofWriter OWA items (`hitachi-nlp/proofwriter_processed_OWA`, depth-3/test, conjunctive rule required, target depth ≥ 2), split 50/100 calibration/test at the item level, seed 20260807. Every proposition carries a truth value derived from the theory's closure, so ground truth is by construction. Two panels of three model families each, sharing no family: panel A (local: thinkingcap-qwen3.6-27b, laguna-xs-2.1, ornith-1.0-35b) and panel B (OpenRouter: nemotron-3-super, gpt-oss-20b, gemma-4-26b). One fixed extractor turns each trace into claims; claims align to canonical propositions via local embedding retrieval (top-k = 8) and bidirectional CPU NLI (Laurer et al., 2024), thresholds frozen; each agent is capped at one observation per proposition. Arms: WCT-U (uniform signed support), WCT-EM (three-state Dawid–Skene, unsupervised), WCT-C (same observation model fitted on labelled calibration items), a covariate baseline (logistic regression on depth, coverage, verbosity, length; a feature list that diverges from prereg.yaml's registered wording; the implementation predates the first results, both cycles compare against it, and cycle 2's implementations-are-the-registration clause exists to close exactly this gap), and ablations. The registered primary: held-out item-stratified Δ log-loss, WCT-EM vs the covariate baseline, δ = 0.02 nats, item-block bootstrap. Calibration of every score arm: a single fitted temperature, sigmoid(s/t).

### 3.2 The registered primary flips with the panel

| | panel A (local) | panel B (OpenRouter) |
|---|---|---|
| primary, all items | **−0.159 [−0.249, −0.070] → stop** | **+0.122 [+0.037, +0.197] → go** |
| negation stratum (post-hoc, §3.3) | +0.001 [−0.104, +0.108] → inconclusive | +0.277 [+0.223, +0.343] → go |
| within-item AUROC | 0.905 [0.833, 1.000] → go | 1.000 [1.000, 1.000]† → go |
| permutation null | p = 0.001 | p = 0.001 |

†Degenerate interval, declined to interpret: 14 test negatives, perfect separation, every resample also perfectly separated.

Identical items, split, extractor, measurement stack, analysis code, and frozen δ. Both intervals exclude zero in opposite directions; this is not a disagreement more n resolves. The covariate baselines are near-identical across panels (0.2097 vs 0.2112 test log-loss) because they depend on items, not models: the whole movement is in the WCT arms.

Note the pattern that becomes the diagnosis: the two panels *agree* on every rank-based measurement (within-item AUROC passes on both, precision@k beats the baseline on both, the permutation null rejects at p = 0.001 on both) and disagree only on the calibration-sensitive metric.

### 3.3 The corpus could barely contain a falsehood

*(POST-HOC. The stratification in this section was defined after panel A's results were visible, as a validity restriction recorded in DECISIONS.md 2026-08-08; the frozen all-items primary of §3.2 is unchanged by it.)*

48% of the pre-registered proposition set (242 of 502 scored propositions on panel A; 234 of 484 on panel B) came from *Noneg* theories, in which nothing is stated with negation, so no positive proposition can ever be disproved. Measured prevalence on that stratum: exactly 1.0000, on both panels. Removing it moves panel A's primary from −0.159 to +0.001 (+0.160 nats) and panel B's from +0.122 to +0.277 (+0.155 nats): movements that flip panel A's verdict from stop to inconclusive without touching its ranking results at all.

A second, subtler restriction was found later (post-hoc): the alignment layer never scored a single negative-polarity proposition: 0 of 607 across both panels. Every scorable negative is a positive-polarity falsehood, of which the corpus held 46, of which roughly 62% scored. The test splits therefore held 14–16 negatives, and every claim about false propositions in cycle 1 rests on that many observations.

### 3.4 Cycle-1 secondary results

The registered E0 directional prediction (cross-family panels carry lower residual error correlation than same-family) failed in sign on panel A (ρ 0.080 vs −0.022) and was uncomputable on panel B, where two of three models answer every item correctly; the panels are at answer-level ceiling, and the test had negligible power. The claim-instance ablation destroyed the signal on every stratum of both panels (AUROC 0.502–0.554 against 0.891–1.000 for unique-source arms). Registration hygiene: cycle 1's own protocol required a git tag before any inference ran, and no tag existed; the retrospective record (tag `prereg-retrospective-2026-08-15`) documents what the file timestamps can and cannot establish: notably, that the frozen δ values predate the first results, but that panel B's *primary* designation cannot be shown to predate panel A's results.

---

## 4 Diagnosis (post-hoc, labelled as such)

### 4.1 The flip is a missing intercept

The registered calibration map sigmoid(s/t) is a positive scalar divisor: it can sharpen or flatten a score but cannot shift its mean. The covariate baseline is a logistic regression fitted *with* an intercept. Only one side of the registered comparison could match the base rate.

Re-analysing the frozen cache under three calibration maps, all fitted on calibration only: temperature and Platt are strictly monotone, so AUROC, precision@k and the selector's operating point are unchanged by construction (asserted, exact to machine precision), while isotonic is only weakly monotone (its plateaus create ties and shift AUROC by up to 0.034), so the invariance argument rests on the two strictly monotone maps alone. Only log-loss can move under them, and anything that moves is calibration:

| panel A, all items, WCT-EM | log-loss | mean pred − prevalence | Δ vs baseline | decision |
|---|---|---|---|---|
| temperature (registered) | 0.385 | −0.198 | −0.159 [−0.249, −0.070] | stop |
| Platt (adds intercept) | 0.146 | −0.018 | +0.069 [+0.029, +0.112] | go |
| isotonic | 0.143 | −0.010 | +0.071 [+0.028, +0.118] | go |

Under Platt, all 12 panel × stratum × arm combinations return go. The attribution was verified adversarially: an intercept alone at the frozen registered slope captures 98.8% of the full Platt improvement on the primary cell; the go survives an exact-ML refit of the baseline and a Platt-recalibrated baseline (weakest margin +0.056 [+0.023, +0.096]); item-blocked 5-fold cross-validation inside the calibration split preserves the advantage in all folds, and Platt's test log-loss beats its calibration log-loss, so this is not overfitting. A label-flip probe (all test labels inverted, every fit re-run) left every fitted parameter and prediction bitwise unchanged (run in the 2026-08-15 adversarial validation of this diagnostic and recorded in DECISIONS.md, then repeated independently in cycle 2's verification, §5.2): no path from test labels to any map.

The mechanism, refined by cycle 2 (§6.4): the intercept corrects panel-specific *score miscentring*: how far the temperature-mapped scores sit from the base rate. On cycle 1's panel A that miscentring was 0.198 against the test split's prevalence of 0.951 (0.944 over all scored propositions); extreme prevalence amplified its cost. Prevalence is the amplifier, not the variable.

This diagnosis is post-hoc, and post-hoc it proves nothing about the method: turning a registered stop into a go by re-choosing the calibration map after seeing results is precisely the analyst degree of freedom this study documents. Its status is that of a hypothesis, which is why cycle 2 exists.

### 4.2 What a frozen registration cannot do

Cycle 1's registration froze a comparison that was unfair in a way nobody noticed: the baseline got an intercept, the treatment arms structurally could not have one. Freezing prevented tampering; it could not make the comparison fair, and the unfairness was invisible until two panels disagreed. That is the general lesson we take: pre-registration converts silent analyst freedom into visible specification defects, but only replication makes the defects findable.

---

## 5 Cycle 2: the diagnosis as frozen predictions

### 5.1 Registration

The v2 registration (`prereg_v2.yaml`, tag `prereg-v2-2026-08-16`) was committed and git-tagged before any v2 generation call, the discipline cycle 1 lacked. It freezes:

- **Corpus**: 150 negation-family items: 78 reused from cycle 1 (placed to preserve their role assignments and hence their cached generations) plus the 72 depth-5 items richest in positive-polarity falsehoods. 744 y=0 propositions, 202 of positive polarity; question depth extends to 5. Parquet snapshots pinned by SHA-256. Projected scored test negatives: 80–83 (Wilson band 68–95); a projection, explicitly not a gate.
- **Panels**: panel B unchanged from cycle 1 (nemotron/gpt-oss/gemma, its 234 cached generations reused exactly). Panel A rebuilt: cycle 1's local panel was abandoned when two of its three models left the local catalogue (recorded, not substituted); the new panel A is qwen3.8-27b (local), laguna-xs-2.1 (OpenRouter) and GLM-5.2 (Hoonify): three families, disjoint from panel B. Every endpoint smoke-tested before the tag; the local server's launch alias (`ornith35`) and the identity of its loaded weights (Qwen3.8-27B GGUF, 27.3B parameters) are pinned in the registration, with any other server echo defined as substitution.
- **Calibration**: Platt, sigmoid(a·s + b), a > 0, fitted on calibration by exact maximum likelihood; this is the intercept the cycle-1 map lacked. Temperature retained as an ablation.
- **Baseline sensitivity**: the primary verdict is stated against the cycle-1-style baseline fit, with an exact-ML refit reported alongside.
- **Registered instrument variants**: S1, a deny filter dropping any deny vote whose own trace affirms the proposition positively elsewhere (motivated by the post-hoc cycle-1 measurement that self-contradicted denies have precision 0.153 vs 0.798); S2, an extractor exemption admitting derivation sentences rejected solely for a "step " prefix.
- **Three predictions.** P1: with the intercept-bearing map and ~5× the test negatives, the primary returns go on both panels. (The registration itself notes that the strongest cycle-1 claim, that cycle-1's panel A would flip to go under an intercept, is not testable here, because that panel no longer exists; its evidence remains the post-hoc diagnostic of §4.) P2: proposition-level vote correctness is weakly decreasing across depth bins (tolerance 0.02) on both panels, and pooled unanimous-vote correctness at depth ≥ 4 falls below 0.90 on at least one panel. P3: S1 strictly improves the primary point estimate on both panels.
- **Spend**: hard cumulative per-panel call caps, persisted across re-runs.

Generation: 450/450 cached on each panel (panel B: 216 new calls plus 234 reused from cycle 1), zero errors in the final cache, zero retries needed. Analysis: the tagged code, unmodified (verified: the diff between tag and analysis is empty).

### 5.2 P1: confirmed on both panels

| REGISTERED, cycle 2 | panel A (new) | panel B (continuing) |
|---|---|---|
| primary (Platt) | **+0.220 [+0.160, +0.280] → go** | **+0.272 [+0.180, +0.353] → go** |
| primary vs exact-ML baseline | +0.224 [+0.158, +0.291] → go | +0.263 [+0.166, +0.353] → go |
| co-primary precision@k | +0.092 [+0.059, +0.119] → go | +0.077 [+0.042, +0.112] → go‡ |
| within-item AUROC | 0.924 [0.890, 0.960] → go | 0.932 [0.893, 0.976] → go |
| permutation null | p = 0.001 | p = 0.001 |
| test negatives | 81 | 65 |
| prevalence | 0.799 | 0.816 |

‡Reading-sensitive: go under the frozen decision rule (interval excludes zero and point ≥ δ); a stricter reading requiring the lower bound to exceed δ = 0.05 would return inconclusive, since the bound is +0.042. The registration's implementations-are-the-registration clause resolves this in favour of go; we disclose it rather than rely on it.

Every number above was reproduced byte-identically by an independent re-run of the tagged code against the immutable cache. The verdicts are robust to every reading of the frozen decision rule except the one flagged. The cycle-1 flip does not reappear: on a corpus with 65–81 test negatives and a calibration map with an intercept, proposition-level cross-model agreement clears its registered gate on two panels sharing no model family with each other. Panel A shares no serving stack and no provider mix with any panel previously measured, though it retains the qwen and laguna families, including the laguna-xs-2.1 model itself, now served via OpenRouter rather than locally, from cycle 1's abandoned local panel (the registration's panel history records this; it is why none of that panel's cycle-1 cache was reusable).

Consistent with the miscentring mechanism, the temperature ablation nearly matches Platt on panel B (0.1659 vs 0.1662 test log-loss) and remains worse on panel A (0.2577 vs 0.2324): the intercept pays where scores are miscentred, and panel A's are (−0.109 at calibration), panel B's are not (+0.001).

Disclosure: panel B's 65 scored test negatives fell below the registered projection's own uncertainty band (68–95). The projection was measured on depth-3 items and transferred imperfectly; it gated nothing, but we flag the miss.

### 5.3 P2: failed

Panel A's depth curve is not weakly decreasing: vote correctness runs 0.967 / 0.878 / 0.828 / 0.787 across depths 1–4 and then rises to 0.866 at depth 5, exceeding the frozen 0.02 tolerance by a factor of four. And pooled unanimous-vote correctness at depth ≥ 4 is 0.903 (panel A) and 0.905 (panel B): neither below the registered 0.90 line. The prediction fails on both conjuncts independently.

The honest gloss is not that depth is harmless: both panels lose roughly 0.10–0.18 of vote correctness between depth 1 and depth 4, and panel B's curve *is* weakly decreasing under the frozen tolerance (its only rises are +0.002 and +0.0002, far inside 0.02). The failure teaches two things. First, the depth-collapse story we extrapolated from cycle 1 was too clean. Second, the violating bin (56 propositions) carries an item-block bootstrap interval of [−0.033, +0.187] on its rise (a post-hoc check; the registered adjudication uses the frozen tolerance alone), statistically indistinguishable from flat, so the frozen tolerance of 0.02 asked a precision of the data that 56-proposition bins cannot supply. A registered prediction whose adjudication hinges on noise is a badly set prediction; we set it, and we report it as failed under its own terms.

### 5.4 P3: failed, one panel in each direction

The S1 deny filter raises the primary on panel A (+0.220 → +0.257) and lowers it on panel B (+0.272 → +0.245). The frozen wording required improvement on both.

The mechanism (a post-hoc verification analysis of the registered failure; only the S1 point estimates above are registered): on cycle 1's corpus, denies were mostly wrong, and the self-contradiction heuristic deleted mostly-wrong votes. Negative enrichment changed the base rates: overall deny precision is 0.667 (A) and 0.769 (B) in cycle 2 (measured in the verification pass over the cache, recorded in DECISIONS.md), against 0.153 for self-contradicted denies in the cycle-1 measurement. On panel A the filter still deletes mostly-wrong denies (precision of dropped denies 0.373; 96 wrong vs 57 correct removed). On panel B it deletes slightly-mostly-*correct* ones (0.523; 46 correct vs 42 wrong), and the harm concentrates in ten test propositions. The style dependence is specific: gpt-oss and nemotron restate the goal ("we need to determine whether X") in ways the heuristic reads as affirmation, and the frozen negation-token list lacks "don't" and "is false". An instrument fix validated on one corpus and one panel family does not transfer on its own, which is exactly the kind of claim only a registered failure can establish cleanly.

S2, the extractor exemption, was absorbed by the pipeline (post-hoc diagnosis of a registered secondary): it admitted ~160 additional derivation sentences per panel at the source, but the one-observation-per-agent cap and the alignment threshold left 12 (A) and 10 (B) new observation cells and a net change of one scored proposition (on panel A; panel B's count is unchanged). Its cycle-1 motivation (a trace style specific to a model family absent from cycle 2's panels) did not generalise at the level that matters.

---

## 6 What survives everything

Four results hold across both cycles, all panels, and all strata where they are defined.

**6.1 One vote per source, or nothing.** Claim-instance counting: AUROC 0.502–0.554 (cycle 1), 0.569–0.606 (cycle 2, primary instrument). Unique-source support: 0.891–1.000 (cycle 1), 0.931–0.939 (cycle 2, primary instrument). Whatever agreement measures, it is who asserts a proposition, not how much text asserts it.

**6.2 The signal is real everywhere it can be measured.** The within-item permutation null (does support predict truth beyond item difficulty?) rejects at p = 0.001 in every stratum of every panel in both cycles.

**6.3 Ranking is panel-robust; calibration is not.** Every verdict flip observed anywhere in this study lives in calibration-sensitive metrics; no rank-based measurement ever flipped. (Panel-dependent results that are not verdict flips, such as the depth-curve shapes of §5.3, the deny-precision divergence of §5.4 and E0's underpowered ρ contrast, live in vote-level descriptives, not in ranking.) Deployments that select (top-k, thresholds on ranks) inherit the robust part; deployments that consume the probabilities inherit the fragile part, and should fit an intercept-bearing map per panel.

**6.4 The intercept, understood.** Cycle 2 separates the variables cycle 1 confounded: at near-identical prevalence (0.799 vs 0.816 over the analysed propositions), the temperature-vs-Platt gap is +0.025 on panel A and −0.000 on panel B. What differs is score miscentring (−0.109 vs +0.001, recorded in DECISIONS.md). The intercept corrects miscentring; extreme prevalence amplifies the cost of not correcting it. Unarchived exploratory cycle-1 transfer analysis is consistent (scratch output, not in the committed artifact set): after unsupervised per-panel standardisation the fitted intercept transfers across panels, while the slope (which tracks discrimination) does not.

---

## 7 Exploratory analyses (not registered)

Three exploratory results from the cycle-1 cache informed cycle 2's design and are reported with that status. Their provenance is the 2026-08-15 exploratory battery, whose toolkit is deliberately not frozen in this repository (prereg_v2's planned-exploratory clause); the headline figures below are recorded in DECISIONS.md and are the only numbers in this paper not reproducible from the committed artifact set alone.

**Right answers rarely rest on wrong derivations here.** Matching cited rules in each trace against ground-truth proof DAGs (decodable for all 1,200 decidable propositions), genuine right-answer-wrong-derivation occurs in ~1 of 800 correct answers. The dominant failure is the inverse: agents that answer *wrong* cite the correct derivation ~82% of the time and fumble the verdict. Verdict extraction, not reasoning, is the weak link at this task scale.

**Path-weighted aggregation adds nothing at trace granularity.** Weighting votes by ground-truth derivation backing (a privileged upper bound) never beats plain vote counting, and a deployable cross-agent path-agreement weight is statistically indistinguishable from it. Rule citation is an item-level property of a trace: it cannot distinguish which agent to trust exactly where votes conflict. This is why cycle 2 registered no path-aware arm.

**A caveat on "EM recovers reliability."** Cycle 1's estimator orders agents by answer accuracy correctly, but on the local panel it *inverts* the labelled vote-accuracy ordering (the panel's most accurate voter is ranked last, with its false-positive rate more than doubled) and anti-correlates with derivation precision. With three agents, EM reliability is substantially agreement-with-consensus. n = 3 per panel; descriptive, not inferential.

---

## 8 Limitations

- **Synthetic closed world.** ProofWriter's decidable, closed-vocabulary microworld is what makes proposition-level ground truth and proof DAGs available at all; nothing here establishes transfer to open-ended claims. The mechanism results (intercept, one-vote-per-source, rank robustness) are the most likely to travel; the effect sizes are not.
- **Three-model panels.** M = 3 was forced by endpoint availability in cycle 1 and retained for comparability; the five-family target of the original protocol was never met. EM reliability estimates at M = 3 are consensus-dominated (§7).
- **Answer parseability.** Under the frozen token budget, 53/150 GLM-5.2, 26/150 laguna and 20/150 qwen generations spent the entire budget reasoning and emitted no final content block. Traces remain non-empty (reasoning is retained) and no registered quantity conditions on answer parseability, but answer-level descriptives inherit missingness (parse rates 81–100% per agent, not depth-concentrated).
- **One adjudication is reading-sensitive** (panel B's co-primary, §5.2), and one projection missed its own uncertainty band (panel B's negative count). Both disclosed.
- **The two cycles share half a corpus and one panel.** Panel B and the 78 reused items appear in both cycles; cycle 2's panel A and its 72 depth-5 items are the genuinely fresh half. The P1 confirmation rests on both halves agreeing.
- **One registered robustness check was never run.** Cycle 1 registered a second embedding/NLI stack on a fixed 20% subsample; it was not run in either cycle, so the shared-measurement-stack confound (one extractor, one embedding model, one NLI model across all panels and both cycles) is disclosed but unquantified.
- **Cycle 1's registration was never tagged before inference**, its own requirement. The retrospective forensics (what file timestamps can and cannot establish) are in the record, and cycle 2 was run so that no such forensics are needed.

## 9 Conclusion

We asked whether cross-model proposition agreement predicts proposition truth, and the first honest answer was: our instrument could not say. The same frozen test returned opposite verdicts on two panels, and the disagreement was traced, post hoc (§4), to the instrument: a calibration map denied the intercept its baseline had, on a corpus whose test splits held 14–16 falsehoods for a method to be wrong about. The second honest answer, from a second registration frozen before its data existed, is yes: +0.220 and +0.272 nats over a covariate baseline, both intervals well clear of the registered threshold, on two panel–corpus configurations sharing no model family, with the rank-based signal invariant everywhere and p = 0.001 against the within-item null throughout.

The registered failures bound the claim. Depth degrades consensus but not monotonically, and not past the unanimity threshold we predicted; an instrument fix that helped one panel's trace style hurt the other's. And the one finding that needed no second cycle, because it never wavered: agreement carries information exactly when each source gets one vote. Count text instead of sources, and there is nothing there.

---

## Author contributions and use of AI assistance

Study design, decisions, and all approvals: the human authors. Implementation, analysis, verification tooling and drafting were carried out with AI assistance (Claude, Anthropic); every number in this draft is read from committed artifacts, every registered analysis was frozen in a git tag before the data it touches existed, and the adversarial verification runs that checked reproduction, leakage and adjudication are described in `DECISIONS.md`.

## Appendix A: reproduction

**Cycle 1** (tag `prereg-retrospective-2026-08-15`, retrospective): 150 items, depth-3/test, split 50/100 seed 20260807; panels and measurement as §3.1; 850 + 660 generations, 0 errors in the final cache; 2,000-resample item-block bootstrap for primaries and paired differences, 1,000 for the within-item AUROC gate, 1,000 within-item truth permutations. Analysis: `exp/e0.py`, `exp/e1.py`; post-hoc calibration diagnostic `exp/recalib.py` (byte-reproducible from cache in a no-network namespace).

**Cycle 2** (tag `prereg-v2-2026-08-16`, created before any v2 generation): corpus, panels, calibration, predictions and caps frozen in `prereg_v2.yaml`; corpus reconstruction and tripwires in `exp/v2_dataset.py` (parquet SHA-256 asserted); generation `exp/run_generate_v2.py` (preflight reuse contract: 234/234 cached hits on panel B, 0 on panel A; cumulative attempt ledgers 450/540 and 216/260); analysis `exp/e1_v2.py`, run unmodified from the tag; endpoint smoke evidence `out/smoke_v2_evidence.txt`. Verification: independent byte-identical reproduction of both summaries from cache; label-flip leakage probe; adjudication audit including alternative readings. All analysis re-runs over the immutable content-hashed cache at zero inference cost.

## Appendix B: artifact map

| artifact | contents |
| --- | --- |
| `prereg.yaml`, `prereg_v2.yaml` | the two registrations; v2 tagged before any v2 generation |
| `out/e1_summary.json`, `out/e1_summary_openrouter.json` | cycle 1, both panels: strata, arms, primaries, nulls, audits |
| `out/recalib_summary.json` | the post-hoc calibration diagnostic: three maps × three arms × both panels |
| `out/e1_v2_summary_panelA.json`, `_panelB.json` | cycle 2: primary, co-primary, S1, S2, depth descriptives |
| `out/e0_summary*.json` | cycle 1 E0 factorial: per-cell accuracy, ρ, M_eff, dose–response |
| `out/result_package.json` | cycle 1 gate decisions, panel comparison, negative-results list |
| `out/smoke_v2_evidence.txt` | v2 endpoint smoke evidence, both runs, including the serving-alias forensics |
| `out/generation_index*.json`, `out/attempts_v2_*.json` | per-call indexes; cumulative spend ledgers |
| `out/dataset_manifest.json` | cycle-1 item census |
| `out/cache/` | immutable content-hashed generation artifacts (embedding/NLI caches are regenerable and untracked) |
| `wct/`, `exp/`, `m0/` | instrument, experiment drivers, pre-inference invariant checks |
| `DECISIONS.md`, `GOTCHAS.md` | the decision log (including the two correction entries and the v2 outcome entry); measured environment constraints |

## References

- Liu, N. *LLMs as a Jury: Cross-Model Consensus Can Outperform Process Reward Models for LLM Reasoning.* arXiv:2607.10139.
- *Unsupervised Process Reward Models.* arXiv:2605.10158.
- Dawid, A.P., Skene, A.M. *Maximum Likelihood Estimation of Observer Error-Rates Using the EM Algorithm.* JRSS-C 28(1), 1979.
- Tafjord, O., Dalvi Mishra, B., Clark, P. *ProofWriter: Generating Implications, Proofs, and Abductive Statements over Natural Language.* Findings of ACL 2021.
- Laurer, M., van Atteveldt, W., Casas, A., Welbers, K. *Less Annotating, More Classifying.* Political Analysis, 2024.
- Li, Y., Rubinstein, B., Cohn, T. *Exploiting Worker Correlation for Label Aggregation in Crowdsourcing.* ICML 2019.
