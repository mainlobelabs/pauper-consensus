# Decisions

## 2026-07-27T10:21:43Z - Slice 1 builds the real analysis-side modules wct/aggregate.py, wct/diffuse.py and wct/derive.py, rather than throwaway reference implementations in m0/.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: M0 invariants 1-3, 6 and 7 cannot be tested without them. These modules are inference-free, so they can be fully verified against simulated ground truth before any API call; a defect then surfaces against a known answer instead of being indistinguishable from a negative experimental result. Slices 4-6 shrink to the inference-dependent parts (nodes/extract/cluster/measure) plus experiment drivers.
- Alternatives: Stub reference implementations in m0/ and keep the master slice boundary (rejected: M0 would verify code that never ships, and the real modules would land untested against ground truth). Narrow to aggregate.py only, deferring invariants 6 and 7 (rejected: leaves the two operators unverified where ground truth is available).

## 2026-07-27T10:21:43Z - Slice 1 owns wct/schema.py, the shared cached-artifact schema, versioned via SCHEMA_VERSION which is included in the cache key.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: Protocol 3.0 requires the simulator to emit a schema matching the real cached artifacts, so a schema must exist in slice 1 regardless. Defining it once here avoids a second definition and a simulator/cache rework later. Resolves REQUEST.md OQ4.
- Alternatives: Define a minimal simulator-only schema now and design the production schema at slice 4 when real extraction output is visible (rejected: forces rework of simulator and cache, and leaves every later slice without a stable interface).

## 2026-07-27T10:21:43Z - m0.gate runs invariants only and stays under 90s; m0.sweep is a separate command. m0.gate --full additionally asserts sweep artifacts exist and their grid hash matches the current prereg.yaml.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: The sweep is minutes to the gate's seconds. Coupling them would discourage running the gate during development, which is when it has the most value. The --full staleness check keeps stale sweep artifacts from passing as current.
- Alternatives: One command always runs both (rejected: multi-minute gate gets run less often, which is the failure mode that matters).

## 2026-07-27T11:08:38Z - Dataset sourcing (OQ3): approved — stratified ladder for E1/E2.5. Stratum 1 generated formal (ProverGen/PrOntoQA), stratum 2 natural multi-hop (MuSiQue/2WikiMultiHopQA), stratum 3 hand-authored constrained-design. E3 gate items hand-authored with criterion rubrics.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: Generated formal items give per-proposition truth AND complete premise sets by construction, which is the only realistic source of E2.5's dependency ground truth, and being generated on demand they cannot be contaminated. Reporting the mechanism metric per stratum makes formal-to-open-ended transfer a measured slope instead of an untested assumption.
- Alternatives: Single-domain E1 on checkable math (rejected: no premise-set ground truth for E2.5, and contamination inflates agreement). GRACE as primary source (rejected: annotates context faithfulness not correctness, and explicitly does not annotate step dependencies).

## 2026-07-27T11:08:38Z - Delta values (OQ1): explored on M0 SIMULATION before any real inference, then frozen at R0. delta = max(smallest effect worth acting on, smallest effect detectable at feasible n). Never moved after real results are visible.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: Human asked to try thresholds and experiment. That is legitimate on simulated data with known ground truth and is exactly what the M0 failure surface and break-even boundary are for; it is analyst degrees of freedom (protocol 6.17) only if done after seeing E1/E3 results. The M0 sweep bounds what is achievable per regime, m0/ceiling.py bounds what is detectable at feasible n, and delta is set between those two before the freeze.
- Alternatives: Set delta by judgement with no simulation support (rejected: unfalsifiable and arbitrary). Tune delta after seeing results (rejected: destroys the pre-registration).

## 2026-07-27T11:08:38Z - Failed-gate policy (OQ2): a failed experimental gate PARKS the workstream for a human go/no-go. It never auto-abandons.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: Negative results are the expected and valuable output of this study; automatic abandonment would discard a boundary-condition result that protocol 7.3 identifies as potentially the most useful outcome. Parking preserves the artifacts and forces an explicit human decision against data.
- Alternatives: Auto-abandon on gate failure (rejected: throws away the scientifically useful negative result).

## 2026-07-27T11:08:38Z - Third-party egress (OQ2 original): APPROVED. Benchmark prompts and experimental items may be sent to OpenRouter.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: Items are public benchmark content with no secrets; egress_guard still scans payloads. Declining would require a local-only pool, which cannot currently supply five distinct model families on this host, and would therefore end Claim A rather than protect anything.
- Alternatives: Local-only pool (rejected: cannot supply five distinct families; local generation currently fails to load).

## 2026-07-27T11:08:38Z - Timeline (OQ1 original): day numbers in the schedule are ILLUSTRATIVE, not binding. Unattended overnight and weekend inference is permitted. Work proceeds continuously rather than to a day-boundary plan.

- Run: `20260727-201557-5e045099`
- Decided by: human
- Rationale: Human directive: 'just do it all at once, days are illustrative'. The gate ORDER remains binding; only the calendar mapping is relaxed.
- Alternatives: Hold to 13 elapsed days with attended-only execution (rejected by the human).

## 2026-08-07T19:40:00Z - M0 correction: the single-source baseline is split into an oracle bound and a calibration-selected achievable baseline, and the EM-vs-uniform gap is reported paired with a bootstrap interval.

- Run: paper build, local panel
- Decided by: assistant, recorded for human review
- Rationale: `m0/ceiling.py` reported `best_single = ps.max()`, the maximum TRUE accuracy, and D9 in EXPERIMENT.md described it as "the best single source". That is an oracle requiring truth labels to identify, so quoting it alone overstates the baseline. Adding a calibration-selected source (best on the first half of propositions, scored on the second) gives the achievable comparison. D9's conclusion survives the correction: uniform aggregation loses to the ACHIEVABLE single source too, 0.8548 against 0.9052. Separately, the "recovers 88% of the gap" figure was a ratio of column means whose across-panel sd is dominated by the shared random draw of reliabilities; it is now paired, at 87% with 95% CI [77%, 96%], and the paired accuracy difference is +0.0572 [+0.0432, +0.0724].
- Alternatives: Leave the oracle baseline and footnote it (rejected: the headline sentence would still assert something no unlabelled method can be asked to clear). Drop the single-source baseline entirely (rejected: it is the comparison that decides whether a panel is worth running at all).

## 2026-08-07T19:40:00Z - M0 invariant I4 restated: both naive treatments of silence fail, in OPPOSITE regimes.

- Run: paper build, local panel
- Decided by: assistant, recorded for human review
- Rationale: the protocol states I4 as "treating missing as denial is detectably biased when coverage is truth-dependent". The simulator falsified that as written: at cov(Y=1)=0.80 / cov(Y=0)=0.30, silence genuinely IS evidence of falsity, so forcing silence to denial GAINS 0.0118. The correct invariant is two-sided — ignoring silence is right only under truth-independent coverage and discards real information otherwise, while forcing silence to a denial is harmful under truth-independent coverage and only flatters itself when coverage happens to lean the right way. Three-state EM dominates both in every regime tested, which is the actual justification for carrying a coverage parameter (assumption M4).
- Alternatives: Weaken the assertion to a tolerance so it passes (rejected: it would encode a claim the simulation shows is false).

## 2026-08-07T20:15:00Z - R0 A7 SATISFIED: arXiv:2607.10139 verified to exist and to support what D8 attributes to it. D8's narrowing of the novelty claim stands.

- Run: paper build, local panel
- Decided by: assistant, verified against the arXiv record
- Rationale: EXPERIMENT.md flagged 2607.10139 as an unverified citation postdating the review's knowledge cutoff, and made R0 conditional on checking it. It is real: Ning Liu, "LLMs as a Jury: Cross-Model Consensus Can Outperform Process Reward Models for LLM Reasoning", submitted 2026-07-11, revised 2026-07-20. It studies cross-model consensus, identifies error decorrelation as the mechanism, and compares against process reward models — all three of which D8 attributes to it. Critically for WCT it operates at the level of the FINAL ANSWER (models agreeing on an answer), so the proposition-level aggregation and dependency-closed derivation question this study asks is not occupied by it. D8's narrowing is therefore correct and is retained rather than withdrawn.
- Alternatives: Withdraw D8's narrowing as unverifiable (rejected: the citation checks out). Treat answer-level consensus as still-open territory (rejected: it is not, and claiming otherwise in a paper would be a novelty overclaim).
- Also resolved: plan.md's "Unsupervised PRMs" prior-art row is arXiv:2605.10158, "Unsupervised Process Reward Models".

## 2026-08-08T09:40:00Z - E1 is reported over three strata. The frozen primary (all items) is retained; a negation-theory stratum is added as a VALIDITY restriction, not a difficulty filter.

- Run: paper build, local panel
- Decided by: assistant, recorded for human review
- Rationale: in a ProofWriter *Noneg* theory nothing is stated with negation, so no positive proposition can ever be disproved — it is True or Unknown, never False. Those items contribute only y=1 propositions. Measured: the noneg stratum has prevalence EXACTLY 1.0000 over 242 scored propositions, so truth discrimination is undefined there by construction, and it made up 48% of the pre-registered proposition set. Because "always predict true" is then nearly optimal on log-loss, the registered primary (delta log-loss vs a covariate baseline) was being decided by items incapable of informing it. All three strata are reported. The frozen all-items primary is NOT replaced, and its STOP verdict stands as the registered outcome.
- Alternatives: Silently restrict to negation theories (rejected: that is exactly the post-hoc corpus selection this study is about). Re-generate on a rebalanced pool (rejected as unnecessary: the stratification needs no new inference, and swapping the pool after seeing results would be a far worse analyst degree of freedom).

## 2026-08-08T09:40:00Z - E0's registered directional prediction FAILED, and the test is reported as underpowered rather than as a refutation.

- Run: paper build, local panel
- Decided by: assistant, recorded for human review
- Rationale: the prediction was that cross-family panels carry lower residual error correlation than same-family ones. Measured in the diverse-role condition: cross-family rho = 0.080 against same-family rho = -0.022, so the reduction is -0.102 and the prediction fails in sign. But the panel is at ceiling — per-agent answer accuracy runs 0.858 to 0.992 and three of four cells reach consensus 0.98-1.00 — so the correlation estimates rest on a handful of errors. The same-family/same-role cell reports rho = 1.00 and M_eff = 1.00 from essentially one shared error, which is degenerate rather than informative. Reporting this as evidence against family diversity would overstate what a ceilinged design can support; it is recorded as a failed registered prediction whose test had negligible power, which is the honest reading and is itself a result about the item pool.
- Alternatives: Report the failure as a refutation of premise (a) of Claim A (rejected: unsupportable at this ceiling). Drop E0 (rejected: the ceiling finding is exactly what protocol 1.1's feasibility-before-power rule exists to surface).

## 2026-08-09T12:40:00Z - HEADLINE: the registered primary FLIPS between the two panels. The paper is rebuilt around panel and corpus dependence rather than around the method.

- Run: paper build, both panels
- Decided by: assistant, recorded for human review
- Rationale: identical items, split, extractor, embedding/NLI stack, analysis code and frozen delta. Panel A (qwen/laguna/ornith) returns delta log-loss -0.1588 [-0.2495,-0.0702], a decisive STOP. Panel B (nemotron/gpt-oss/gemma) returns +0.1225 [+0.0367,+0.1972], a decisive GO; on the negation stratum +0.2774 [+0.2229,+0.3428]. Both intervals exclude zero in opposite directions, so this is not a marginal disagreement resolvable with more n. The baselines are near-identical across panels (covariate 0.2097 vs 0.2112) because they depend on items not models, so the whole movement is in the WCT arms. Combined with the corpus effect (48% of the proposition set at prevalence exactly 1.0000, worth up to 0.28 nats), the defensible thesis is that the reported verdict is a joint property of the aggregation rule, the panel and the corpus, and the rule is the smallest term.
- Alternatives: Report panel B as the primary result and panel A as a failed replication (rejected: the pre-registration names B primary and A replication, but reporting only the flattering panel is precisely the failure mode this paper documents). Pool the panels (rejected: pooling would average away the single most informative feature of the data).

## 2026-08-09T12:40:00Z - Panel B's AUROC = 1.000 is reported as a point estimate with its bootstrap interval explicitly NOT interpreted.

- Run: paper build, panel B
- Decided by: assistant, recorded for human review
- Rationale: verified independently and label-free that separation is perfect on the 167 held-out propositions of the negation stratum — every proposition with WCT-U score <= -1 is false (14/14) and every one >= 0 is true (153/153). WCT-U consumes no truth labels so this cannot be outcome leakage. But it rests on 14 negatives, and the 95% item-block bootstrap returns [1.000, 1.000] because with perfect separation every resample is also perfectly separated. That interval is DEGENERATE, not precise. Quoting a zero-width interval would assert a certainty the data cannot support; a rule-of-three bound on 14 negatives allows an error rate up to roughly 1 in 5.
- Alternatives: Quote the [1.0,1.0] interval as evidence of precision (rejected: it is an artefact of the estimator, not a measurement). Suppress the result for being too clean (rejected: it is verified and real, and the small-negative caveat is reportable).

## 2026-08-15T00:00:00Z - Post-hoc calibration diagnostic: the panel flip on the registered primary is attributable to the calibration map's missing intercept. The registered verdicts are unchanged.

- Run: `exp/recalib.py` over the frozen cache; independently re-verified by adversarial workers (fair-baseline attack, intercept/slope decomposition, item-blocked CV)
- Decided by: assistant, recorded for human review
- Rationale: the registered calibration map sigmoid(s/t) is a positive scalar divisor with no intercept; the covariate baseline it is measured against is a logistic regression fitted WITH one. At test prevalence 0.95 only one side of the registered comparison could match the base rate. Measured on panel A all-items WCT-EM: temperature leaves the mean prediction 0.198 below prevalence at log-loss 0.385; Platt scaling (same map plus an intercept) closes the gap to 0.018 at log-loss 0.146, and the primary moves from -0.1588 STOP to +0.0694 [+0.0291,+0.1124] GO. Under Platt all 12 panel x stratum x arm combinations return GO. Attribution verified: an intercept alone at the frozen registered slope captures 98.8% of the full Platt improvement; the GO survives an exact-ML refit of the baseline and a Platt-recalibrated baseline (weakest margin +0.0556 [+0.0232,+0.0957]); item-blocked 5-fold CV inside the calibration split preserves the advantage in all 5 folds, and Platt's test log-loss beats its calibration log-loss, so this is not overfitting. All maps are monotone, so AUROC, precision@k and the selector's operating point are unchanged by construction, which is why the rank-based gates already agreed across panels while only the calibration-sensitive metric flipped. The registered primary remains the registered outcome; this entry records diagnosis, not replacement.
- Alternatives: Replace the registered primary with the Platt result (rejected: post-hoc; that substitution is precisely the analyst degree of freedom this study documents). Suppress the diagnostic (rejected: it explains the paper's central observation and is reproducible byte-identically from the cache).

## 2026-08-15T00:00:00Z - Corrections from adversarial validation; the 2026-08-09 HEADLINE entry's "worth up to 0.28 nats" figure is SUPERSEDED.

- Run: 8-worker adversarial validation over all session claims; every numeric claim traced to artifacts
- Decided by: assistant, recorded for human review
- Rationale: three defects surfaced and are fixed in paper.md. (1) "Worth up to 0.28 nats" overstated the corpus effect by ~75%: the measured movements from removing the noneg stratum are +0.160 nats (panel A, -0.1588 to +0.0011) and +0.155 (panel B, +0.1225 to +0.2774); 0.28 was the negation-stratum ENDPOINT, not a movement. Corrected to 0.16 in the abstract, 4.2 and the conclusion; the 2026-08-09 entry above is left as written per this log's append-only convention and is superseded on that figure by this entry. (2) The abstract and conclusion attributed +0.277 to "the registered primary"; panel B's frozen all-items primary is +0.1225, and +0.277 is the negation stratum. Relabelled. (3) Appendix A's blanket "2,000-resample bootstrap" was loose (the within-item AUROC gate used 1,000) and Appendix B overstated generation_index.json as covering "every generation" (it indexes only panel B's 720 entries; panel A's 850 carry provider=local in the cache). Also recorded for the path-level analysis now planned: every y=0 proposition's proof field derives the POSITIVE complement (verified 600/600), and 46/600 y=0 propositions are positive-polarity falsehoods, so path-fidelity for false propositions must be scored against the complement's derivation.
- Alternatives: Silently edit the historical log entry (rejected: rewriting an append-only decisions log destroys exactly the audit trail this study is about). Leave the paper figures uncorrected pending the larger rewrite (rejected: known-wrong numbers should not survive in the draft a rewrite would start from).
