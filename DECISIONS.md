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

## 2026-08-17T00:00:00Z - V2 OUTCOME: P1 PASS on both panels; P2 and P3 FAIL as registered. Verified by independent reproduction before entering the paper.

- Run: v2 generation (panelA 450/450, panelB 216 new + 234 reused, 0 errors either panel, caps unexhausted) and exp/e1_v2.py exactly as tagged prereg-v2-2026-08-16; three-worker adversarial verification
- Decided by: the frozen registration; recorded by assistant
- Rationale: P1 (the calibration thesis, pre-registered): WCT-EM vs covariate baseline under Platt returns +0.2198 [+0.1600,+0.2804] GO on panelA and +0.2723 [+0.1797,+0.3530] GO on panelB, robust to the exact-ML baseline sensitivity row and to every reading of the frozen decision rule. Co-primary and within-item AUROC GO everywhere; permutation nulls p=0.001. The corpus fix delivered 81/65 scored test negatives at prevalence 0.799/0.816 against v1's 14-16 at 0.944. P2 FAILS on both conjuncts: panelA's qdep-5 vote-correctness bin exceeds qdep-4 by +0.0787 (tolerance 0.02), and pooled qdep>=4 unanimous correctness is 0.9032/0.9048, neither below 0.90. P3 FAILS: the S1 deny filter raises the primary on panelA (+0.2198 -> +0.2566) but lowers it on panelB (+0.2723 -> +0.2451). Verification reproduced every published number byte-identically from the cache through the tagged code, confirmed zero post-tag drift in exp/ and wct/, and passed a full test-label-flip leakage probe.
- Disclosures that must accompany any report of these results: (1) panelB's co-primary +0.0769 [+0.0417,+0.1116] at delta 0.05 is GO under the frozen implementation (lo>0 and point>=delta) but would be inconclusive under a stricter lo>delta reading; the registration's implementations-are-the-registration clause resolves it, and the sensitivity is disclosed rather than hidden. (2) panelB's 65 scored negatives fell below the registered projection's own Wilson band (68-95); a projection miss, not a gate breach. (3) The panelA qdep-5 bounce that fails P2 carries an item-block bootstrap CI of [-0.033,+0.187] - statistically indistinguishable from flat; the registered adjudication stands, and the tolerance was evidently too tight for 56-prop bins.
- Mechanisms (verified): S1's flip is corpus-and-style-specific - dropped-deny precision is 0.373 on panelA (net win: 96 wrong vs 57 correct denials deleted) but 0.523 on panelB (net harm: 46 correct vs 42 wrong, concentrated in ten test propositions), driven by gptoss/nemotron goal-restatement phrasing plus negation tokens ("don't", "is false") missing from the frozen list. S2 admitted ~160 step-claims per panel but the M6 one-observation cap and the alignment gate absorbed all but 12/10, netting one scored proposition; the v1 measurement generalised at source level and died at the vote level. The v1 temperature-failure mechanism is REFINED: the intercept corrects panel-specific score MISCENTRING (temperature-mapped calib mean sits 0.109 below prevalence on panelA, +0.001 on panelB at near-identical prevalence); v1's extreme prevalence amplified the miscentring but is not itself the variable.
- Alternatives: Report P1 alone and soften the failed predictions (rejected: the failures are the registration working); re-adjudicate P2 given the bounce is statistically flat (rejected: the frozen tolerance decides, and the looseness of the prediction is itself the finding).

## 2026-08-17T12:00:00Z - Provenance record for numbers cited in paper draft v3 that predate this entry but were not previously in the committed record.

- Run: paper v3 fact-check (four adversarial reviewers over every number in the draft)
- Decided by: assistant, recorded for human review
- Rationale: the fact-check found several verified quantities living only in session verification outputs; they are recorded here so every number in the paper traces to a committed artifact or to this log. (1) Cycle-1 diagnostic label-flip probe (2026-08-15 adversarial validation, cluster B1): flipping every test label and refitting left all fitted calibration maps, the WCT-C score and the covariate baseline bitwise unchanged on the cycle-1 recalibration path; independently repeated in the cycle-2 verification (entry above). (2) Cycle-2 overall deny precision, measured in the 2026-08-17 verification pass over the cache: P(y=0|deny) = 0.667 on panelA (214/321) and 0.769 on panelB (166/216); calibration-split prevalences 0.8029 (panelA) and 0.8135 (panelB). (3) Headline figures of the 2026-08-15 exploratory path battery (toolkit deliberately unfrozen, per prereg_v2's planned-exploratory clause; not reproducible from the repo alone): artifact-corrected right-answer-wrong-derivation 1/826 correct answers; wrong-answer-right-path 33/40 = 82.5%; ground-truth proof DAGs decoded semantically for 900/900 qdep>=1 propositions (1,200 decidable incl. 258 rule-free qdep-0); path-weighted aggregation never beat vote counting (privileged upper bound -0.030 [-0.039,-0.020] vs WCT-U on the local panel; deployable variant statistically indistinguishable everywhere); EM sensitivity inverted the labelled vote-accuracy ordering on the cycle-1 local panel and anti-correlated with path precision (Spearman -1.0 both panels, n=3 agents, descriptive).
- Alternatives: leave the numbers citable only to session transcripts (rejected: the paper's provenance rule would be false); freeze the battery toolkit into the repo retroactively (rejected: prereg_v2 explicitly declined to register it, and retroactive freezing would blur the registered/exploratory boundary the paper is about).
## 2026-08-28T08:32:16Z - Granted 1 additional plan-relay round (exceptional)

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: B6 (funnel monotonicity) was a real defect in the plan, found by round-2 review and fixed in PLAN.md revision 3; GPT has not seen revision 3. Granting one round to verify the fix rather than self-certify it: the task array drives 7 workers, so a wrong acceptance criterion would propagate into every prompt.
- Alternatives: revise the plan; human-approve the residual concerns

## 2026-08-28T08:33:49Z - OQ4 RESOLVED: slice 2 registers the M=3 -> M=5 dose-response regardless of what slice 1's re-analysis shows. It does not park for a go/no-go on the single-source contrast.

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: Deciding whether to register based on how promising slice 1's POST-HOC numbers look would condition the registration on the data, which is the analyst degree of freedom this paper documents and the reason cycle 2 exists. A flat M=3 -> M=5 curve is also the most informative result available here: direct evidence against the error-decorrelation premise the cross-model consensus literature rests on, which is worth more than another confirmation. Slice 1's numbers still set delta and the power calculation (B2, B3); they do not gate whether the experiment is registered.
- Alternatives: Park at slice 1's exit for a human go/no-go, per the project's existing failed-gate policy (DECISIONS.md 2026-07-27, OQ2). Rejected as the wrong analogy: that policy governs a FAILED GATE inside a running experiment, whereas this is whether to register at all. Parking would have been defensible as a resource decision about spending inference, but not as a scientific one.

## 2026-08-28T08:34:06Z - Gate 1f2b1545 resolved: Slice 2 registers the M=3 -> M=5 dose-response regardless of what slice 1's re-analysis shows. It does not park for a go/no-go on the single-source contrast.

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: Deciding whether to register based on how promising slice 1's POST-HOC numbers look would condition the registration on the data, which is the analyst degree of freedom this paper documents and the reason cycle 2 exists. A flat M=3 -> M=5 curve is also the most informative result available here: direct evidence against the error-decorrelation premise the cross-model consensus literature rests on, worth more than another confirmation. Slice 1's numbers still set delta and the power calculation (B2, B3); they do not gate whether the experiment is registered. Alternative considered and rejected: park at slice 1's exit per the project's failed-gate policy (DECISIONS.md 2026-07-27, OQ2) — that policy governs a failed gate inside a running experiment, not whether to register at all.

## 2026-08-28T08:34:42Z - Plan exit: human_approved_after_review (no GPT approval forged)

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: Plan verdict is APPROVED (round 3, B6 closed, zero open blockers). The only remaining exit issue is the model's question for the user, which the user answered: slice 2 registers the M=3 -> M=5 dose-response regardless of slice 1's result, rather than parking for a go/no-go. Recorded in DECISIONS.md and in resolved gate 1f2b1545. No blocker is being accepted or waived. | review proof: plan_round | accepted: (none) | recorded-but-unaccepted: (none)
- Alternatives: revise the plan; grant one more round


## 2026-08-28T10:46:39Z - AMENDMENT to slice 1's no-inference constraint: the aligner self-identification probe MAY be computed for the cycle-2 corpus, by local in-process CPU NLI only. Scope is exactly cluster.aligner_probe over the 150 v2 items. No API call, no OpenRouter, no :1234 endpoint, no network egress, no quota. Everything else in the constraint stands.

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: A6 requires the restored alignment audit for every panel of both cycles. The probe's NLI pairs are cached only for panels whose driver ran it, and exp/e1_v2.py never did -- that omission IS defect D3. So A6 and the as-written no-inference constraint are unsatisfiable together, which is why the GPT spec verdict routed it to the human gate rather than resolving it. Computing the probe restores the cycle-2 mapper diagnostic the paper's 'go' currently lacks; the cost is local CPU only. The probe is a function of the ITEM alone, so one pass over the v2 corpus serves both panels.
- Alternatives: Narrow A6 to panels whose probe pairs are cached and disclose the gap. Rejected by the human: it would leave cycle 2's mapper permanently unaudited, and the audit is the specific thing D3 is about. Recorded as considered.

## 2026-08-28T11:22:57Z - V3 SLICE 1 OUTCOME: D1/D2/D3 corrected; the panel does not clearly beat its best single source on 1 of 4 panel-cycles, and the one-vote-per-source result is a POLARITY result, not a capping result.

<!-- artifacts-fingerprint: 0bfe68c914d9276c -->

POST-HOC throughout. Nothing here restates a registered cycle-1 or cycle-2 verdict; every frozen quantity checked was reproduced EXACTLY, at the committed artifacts' own serialized precision, before any new number was read. Coverage: c1_local 82/82 across 2 strata (all_items, negation_theories), c1_openrouter 82/82 across 2 strata (all_items, negation_theories), c2_panelA 72/72 across 2 strata (all_items, all_items_S2), c2_panelB 72/72 across 2 strata (all_items, all_items_S2). SCOPE DISCLOSURE: cycle-1's `noneg_theories` stratum is excluded because its test split is single-class, so the frozen summary itself records an error there rather than results; there is nothing to reproduce. The v2 tag is untouched: the corrected instrument lives in wct3/ and exp3/.

**D1 - the registered single-source arm, built at last.** `single_best_calibration_selected` (prereg.yaml:166, plan.md:488, simulated at m0/simulate.py:75) was never implemented by any analysis driver. Source chosen on CALIBRATION log-loss alone; the panel-minus-source contrast under each cycle's own registered calibration map:

| panel | map | selected source | panel (WCT-EM) over that source | decision |
|---|---|---|---|---|
| c1_local | temperature | qwen | +0.0448 [+0.0117, +0.0787] | **go** |
| c1_openrouter | temperature | nemotron | +0.0887 [+0.0455, +0.1421] | **go** |
| c2_panelA | platt | glm | +0.0762 [+0.0465, +0.1068] | **go** |
| c2_panelB | platt | gptoss | +0.0329 [-0.0109, +0.0703] | **inconclusive** |

On 1 of 4 panel-cycles (c2_panelB) the multi-model panel is NOT shown to beat one model under the frozen decision rule. The registered primary compares against an item-covariate baseline, so it establishes that proposition-level vote scores carry signal; it does not establish that CROSS-MODEL agreement is the mechanism. This is what cycle 3 registers.

**D2 - the M6 ablation, corrected, refutes the claim it was cited for.** The frozen `uncapped` arm scores n_claims, which equals n_emitting identically because align_anchored collapses per (agent,pid) before exp/e1.py:76-78 counts. Varying capping and polarity separately (test AUROC):

Raw (unmapped) test AUROC — the quantity the signal question asks. A fitted calibration map can take a negative slope on a signal-free arm and flip mapped AUROC about 0.5, so the mapped values are recorded in the artifacts under each cycle's own registered map and are not used here.

| panel | capped+signed | capped+unsigned | uncapped+signed | uncapped+unsigned |
|---|---|---|---|---|
| c1_local | 0.9001 | 0.5069 | 0.9664 | 0.4484 |
| c1_openrouter | 0.9911 | 0.5239 | 0.9875 | 0.4825 |
| c2_panelA | 0.9353 | 0.6063 | 0.9456 | 0.5884 |
| c2_panelB | 0.9323 | 0.5686 | 0.9530 | 0.5705 |

Removing the cap costs nothing (signed: uncapped matches or beats capped, within 0.01, on 4 of 4 panels). Removing the SIGN destroys everything (no unsigned arm exceeds 0.6063 on any panel). paper.md 6.1 and contribution 4 — 'agreement carries information exactly when each source gets one vote; count text instead of sources and there is nothing there' — is therefore not supported by this instrument. The effect is polarity, not capping. This needs a paper correction (slice 2, B10), not a footnote.

**D3 - the discarded audit, restored.** exp/e1_v2.py:189 binds the alignment audit and never uses it. Restored for all four panel-cycles:

| panel | claims | instances | observations | same-agent conflicts | aligner probe |
|---|---|---|---|---|---|
| c1_local | 24621 | 4137 | 1197 | 853 | computed |
| c1_openrouter | 15599 | 2640 | 1121 | 195 | computed |
| c2_panelA | 29350 | 3824 | 1560 | 559 | computed |
| c2_panelB | 17914 | 2834 | 1241 | 225 | computed |

The funnel is NOT monotone: alignment scores each claim against up to top_k=8 targets, so one claim can pass against several. observations <= instances is the invariant.

The probe is computed on all four panel-cycles: self-identification 0.9721-0.9724, and 0 probe across 6766 was scored with the wrong polarity. The cycle-2 corpus is therefore NOT measurably worse mapped than cycle 1's, so the depth-5 enrichment did not degrade the instrument.

## 2026-08-28T11:54:34Z - Granted 1 additional spec review round(s)

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: All five findings from the previous verdict are fixed and verified present on disk (per-map source selection, full strata coverage 82/72 checks, named arm rows, fatal uv assertion, corrected DECISIONS coverage claim). The verdict on disk is bound to an earlier diff and QUESTIONS.md says so; the cap was reached before the current diff could be reviewed. Granting one round to verify the fixes rather than commit on an unreviewed diff.

## 2026-08-28T11:54:42Z - Gate 1dd102c7 resolved: Grant one additional spec review round to verify the fixes against the current diff.

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: The verdict on disk is bound to an earlier diff (QUESTIONS.md states this, and commit-ready blocks on staleness rather than on the findings). All five findings are fixed and verified present on disk: per-map source selection, full strata coverage at 82/72 checks per panel, named arm rows, a fatal uv assertion, and a corrected DECISIONS.md coverage claim. Committing on an unreviewed diff was the alternative and was declined.

## 2026-08-28T14:05:43Z - Granted 1 additional spec review round(s)

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 4's four findings are fixed and verified: validate.py now opens the committed summaries itself (>=40 fields per panel, proven to catch a planted mismatch), the cache manifest brackets the test suite as well as the analysis, probe_backfill enforces cache-only embeddings plus an unroutable endpoint and offline transformers, and panel identity is checked against the registered agent list rather than assumed. Round 4 found no incorrect values, only unenforced verification, so this round is to confirm the gate is now independent.

## 2026-08-28T14:24:06Z - Granted 1 additional spec review round(s)

- Run: `20260828-181147-a3e9edbc`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 5's two findings are fixed: cycle-2 reproduction now covers the registered S1_deny_filter block (imported from exp/e1_v2.py, not reimplemented), the exact-ML sensitivity primaries and the co-primary bootstrap difference, taking cycle-2 frozen checks from 72 to 136; and the independent validator's dead 'cc is c' agent guard is live again, with its own coverage extended to co-primary, within-item AUROC, permutation-null, S1 arms and S1 primaries under per-cycle floors. Findings have gone 5 -> 4 -> 2 with no incorrect value in the last two rounds; this round is to confirm convergence before commit.

## 2026-08-29T05:42:53Z - Slice 2: paper.md 9 closes on the single-source finding (not the corrected polarity result), and the correction notice is a dated block at the head of paper.md (not a separate CORRECTIONS.md).

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: The single-source finding is the more consequential correction: it bears on whether the paper's central premise -- that CROSS-MODEL agreement is the mechanism -- was ever tested, since the registered arm that would distinguish it from one good model was never implemented. Closing there makes the conclusion carry the open question instead of burying it. The in-paper notice is unmissable and follows the project's precedent of superseding records that leave the original visible.
- Alternatives: Close on the polarity result (keeps 9's existing shape, but ends on the smaller correction). Separate CORRECTIONS.md (keeps the paper's voice clean, at the risk of a reader missing it).

## 2026-08-29T05:53:29Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Rounds 3-6 never executed: the cap was reached after round 2, so those plan-verdict calls raised a gate and returned the CACHED verdict. Only two plan_rounds are on record, both hash-bound to plans predating revision 3. GPT has therefore never reviewed revisions 3-6, which include the three-class fix, the removal of the weak quoted-figure class, and the non-normative changelog. human-approve is refused without a hash-bound review of the current plan, and the automatic legacy_rebind does not fire because prior rounds exist. Granting one round to obtain a genuine review of the plan as it now stands, so the recorded human decision rests on real evidence rather than a cached finding.

## 2026-08-29T05:54:07Z - Gate 11a0569c resolved: Obtain one hash-bound GPT review of the current PLAN.md, then human-approve recording B2 as satisfied in substance.

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Rounds 3-6 never executed: after the cap was reached each plan-verdict call raised a gate and returned the cached verdict, so only two plan_rounds are on record and both predate revision 3. GPT has not seen the three-class fix, the removal of the weak quoted-figure class, or the non-normative changelog. The human decision to approve stands, but it must rest on a real review of the plan as it now is rather than on a cached finding.

## 2026-08-29T05:54:18Z - Granted 1 additional plan-relay round (exceptional)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Rounds 3-6 never executed: the cap was reached after round 2, so those plan-verdict calls raised a gate and returned the cached verdict. Both recorded plan_rounds predate revision 3, so GPT has never seen the three-class fix, the removal of the weak quoted-figure class, or the non-normative changelog. Granting the one exceptional plan round to obtain a hash-bound review of the current plan; human-approve is structurally refused without one.
- Alternatives: revise the plan; human-approve the residual concerns

## 2026-08-29T05:54:26Z - Gate d320c5b8 resolved: One additional plan round granted to obtain a hash-bound review of the current PLAN.md; then human-approve recording B2 as satisfied in substance if it persists.

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Only two plan_rounds are on record and both predate revision 3. Rounds 3-6 hit the cap and served a cached verdict, so the review has never seen the current plan.

## 2026-08-29T07:15:35Z - Gate b42abc84 resolved: Grant one more spec round to verify the fixes against the current diff.

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: The verdict on disk is timestamped before the prompt of the last call: spec_rounds_used is 4 against a granted budget of 1, so the cap was hit, gate b42abc84 was raised, and the cached verdict was returned. Its three findings describe code from before the fixes. The three are closed and verified by planting each failure: the unsigned maximum is now asserted against the computed maximum, section 9 carries c2_panelB's +0.0329 [-0.0109, +0.0703], and PLAN.md's duplicated block is repaired.

## 2026-08-29T07:15:35Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Spec cap reached at 4 used against 1 granted; the last call returned a cached verdict predating the fixes (verdict 17:05:28, prompt 17:07:44). All three findings are closed and each verified by planting the failure: the unsigned-maximum claim is asserted against the computed maximum (swapping it to 0.5884 now fails), section 9 carries c2_panelB's point and interval, and PLAN.md's self-inflicted duplicated Approach/Risks/Rollback block is repaired to five headings and one rollback section. Granting one round for a genuine review of the current diff.

## 2026-08-29T08:05:59Z - Gate 4869126b resolved: Commit slice 2 now, recording the three round-5 fixes as fixed-but-unreviewed.

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: The verdict on disk predates its own prompt (17:17:53 vs 17:19:53) and the round count did not advance, so the cap was hit and the cached verdict returned; its three findings describe the pre-fix state. Each fix is verified by planting its failure: a fabricated quotation range is caught, MASTER_v3.md C2 now reads REGISTERED, and the rollback lists all five new files. Five genuine spec rounds have run on this slice and every check now has a planted-failure test behind it, which is stronger evidence than a review pass.

## 2026-08-29T08:06:23Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Required to execute the human decision to commit. commit-ready structurally demands a genuine relay.py spec run bound to the CURRENT diff hash and recorded in the journal; there is no audited human exit for spec as there is for the plan, so a hand-written verdict cannot substitute. The three round-5 findings are already fixed and each verified by planting its failure. This round exists so the commit rests on a real review of the diff being committed.

## 2026-08-29T08:10:55Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 6's single blocker is fixed: unmarked content is now pinned by sha256 (deleting a clause from 6.2 is caught and located), and the ordered walk asserts it verified every non-trivial fragment rather than reporting success after verifying none. commit-ready requires a genuine spec run bound to the current diff, so this round is the mechanism for the human decision to commit.

## 2026-08-29T08:15:46Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 7's two blockers are closed. (1) Narrative figures are no longer membership-only: the three per-panel deltas, the shortfall, the single-source range and section 9's inline c2_panelB restatement are each asserted against derived artifact values. Verified by planting 0.0329 -- itself a genuine artifact value, so the old membership check would have accepted it -- and watching the new assertion reject it. (2) PLAN.md's P3 acceptance now describes the implemented marker-and-hash guard instead of the heading extraction it originally specified, with the reason: heading scoping skipped any section containing a correction, which left 6.2 unverified while the gate reported 24 sections checked. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-29T08:22:00Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 8's four findings are closed and each verified. (1) 'N of 4 panel-cycles' is no longer exempted as structural: it is asserted against the derived count and exempted only at that value, so 3 of 4 -> 4 of 4 now fails both the assertion and the completeness rule. (2) run_slice2.sh brackets the TEST SUITE with a content-hashed cache manifest, so an NLI miss during tests can no longer compute and write silently; it reports the cache unchanged. (3) exp3.check_paper emits out/v3/paper_check.json and slice2_decide refuses to write an entry without it, so the outcome rests on the gated check rather than an independent re-parse. (4) The notice no longer claims the original wording is quoted in every corrected passage; it distinguishes the two it quotes verbatim from those it characterises. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-29T08:26:35Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 9's two blockers are closed and each verified by planting the failure. (1) The source-reference regex partially consumed 'notaref.md:0.7714' as 'notaref.md:0', leaving '.7714' invisible to the numeric scanner; the pattern now refuses a partial line number and the scanner recognises bare decimals, so a figure hidden behind a fake reference is caught. (2) exp3.check_paper was writing paper_check.json INTO out/v3, the pinned evidence directory; it now writes to out/slice2/, and the gate additionally asserts out/v3 contains exactly the files pinned at e63f946 -- adding an intruder file now fails, which comparing only the eight known artifacts would have missed. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-29T08:31:58Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 10's two findings are documentation-only, with no implementation blockers remaining. Both closed: MASTER_v3.md now carries C8 (v2 tag byte-clean, asserted in the gate) and marks OQ2 and OQ4 RESOLVED with their recorded human decisions and, for OQ4, slice 1's actual answer; PLAN.md's rollback inventory now lists out/slice2/paper_check.json and notes it is deliberately outside the pinned out/v3 evidence set. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-29T08:36:19Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 11's single blocker is closed: tests/test_check_paper.py had no quotation-specific coverage — its retained-v3 test altered an UNQUOTED number, exercising only artifact classification. The fixture now carries a verbatim quotation from the pinned draft, and four new tests cover it: a verbatim quotation is accepted, a fabricated range inside a quotation (0.569-0.554, whose components each occur in the draft) is rejected, a wholly invented quotation is rejected, and an unreadable pinned draft fails rather than silently skipping the check. 54 tests pass. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-30T03:06:59Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 12's two findings are closed and unreviewed. The membership fallback is narrowed further: the abstract's approximate AUROC ranges are now asserted to BRACKET the real extremes, which caught an inaccuracy inherited from draft v3 (it said 0.5-0.6 where the actual unsigned range is 0.4484-0.6063) and the abstract now states the real figures. Appendix B lists the out/v3 artifacts, added as an eighth marked region with its own start and end anchors and an updated content hash. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-30T03:12:33Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 13's two findings are closed. The major one was a real survival of the refuted claim: paper.md 8's Limitations still listed one-vote-per-source among the mechanism results most likely to transfer, contradicting the corrected 6.1. That bullet sat OUTSIDE every marked region, which is why nine rounds of checking the corrections never reached it. It now reads polarity-carries-the-signal and explicitly withdraws the earlier item, as a ninth marked region with its own anchors and an updated content hash. PLAN.md's stale 'seven marked passages' is corrected to nine, and the notice no longer claims 3.4 is quoted verbatim when it retains draft v3's figures under corrected framing. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-30T03:16:56Z - V3 SLICE 2 OUTCOME: paper.md corrected in 9 marked passages; the refuted claim was a LABEL error, not an arithmetic one.

<!-- slice2-fingerprint: 140bffe077bbcd1d -->

Corrections derived from `out/v3/` at `e63f946` and machine-checked by `exp3/check_paper.py`, which requires every figure in a marked passage to equal an artifact value or match a declared structural pattern. The figures below are reported on the authority of that check (9 checks: positional 2x2, positional single-source, narrative deltas, panel counts, unsigned maximum, probe values, frozen headline occurrences, whole-span quotations, completeness (artifact-asserted or structural)), not an independent re-reading. No registered cycle-1 or cycle-2 verdict is restated or altered.

**What was wrong.** Draft v3's abstract, contribution 4, 3.4, 6.1 and 9 concluded that agreement carries information because each source gets one vote. Its quoted AUROC ranges are CORRECT readings of the frozen `uncapped` arm; the error is that the arm is capped and unsigned, because `cluster.align_anchored` collapses per (agent, proposition) before `exp/e1.py:76-78` counts. The contrast varied polarity, not capping. Separating them: uncapped signed BEATS capped on 3 of 4 panel-cycles and is 0.0036 lower on the remaining one, so the cap makes no measurable difference either way; no unsigned arm exceeds 0.6063 anywhere.

**What was disclosed.** `single_best_calibration_selected` (`prereg.yaml:166`, `plan.md:488`) was registered and never implemented in either cycle, so no registered result distinguished cross-model agreement from one good model. Post-hoc, the panel beats its calibration-selected best single source on 3 of 4 panel-cycles (+0.0448 to +0.0887 nats) and inconclusively on c2_panelB. 9 now closes there, per the recorded decision on OQ1.

**Scope.** 9 passages are delimited in `paper.md` by slice2 markers. Everything outside them is asserted byte-identical to `e63f946:paper.md` by the slice gate, so the correction cannot have altered a section it does not claim to touch.

## 2026-08-30T03:17:49Z - Granted 1 additional spec review round(s)

- Run: `20260829-151714-c1159b09`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 14's two blockers are closed, and the second uncovered a worse hole than reported. (1) slice2_decide refused to update an existing heading, so a stale fingerprint wedged the gate unpassably; it now supersedes a stale entry atomically and the gate reaches a current entry. (2) The unbounded structural exemptions were real, but bounding them exposed the actual defect: the numeric pattern required an integer not be followed by [\w.], which made EVERY integer at the end of a sentence invisible to the completeness scan -- depth-999, contribution 999, cycle-999 and slice 99 were all accepted for that reason, not because of the label patterns. The lookahead is now (?!\.?\d), all four are rejected, and a planted-failure test covers them. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-30T03:47:37Z - M=5 is registrable only WITH MARGIN (more than five families answering). If exactly five answer, slice 4 registers M=3/M=4 as primary with the fifth family as a declared stretch arm. Slice 3 reports the family count AND the margin.

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: The programme has twice lost models mid-flight: cycle 1 found three local families not five, and cycle 2 rebuilt panel A when two of three models left the catalogue. Registering M=5 on exactly five families means one disappearance forces an unregistered substitution or an abandoned arm -- precisely what prereg_v2's 'exact pinned id or the panel is DROPPED' rule prevents. A declared stretch arm degrades the design rather than breaking it, and the M=3 -> M=5 dose-response is still tested.
- Alternatives: Register M=5 on exactly five, accepting zero margin: rejected, it repeats the failure mode the project documents. Defer the decision until after measurement: rejected, deciding the rule before seeing the number is the point of registering anything.

## 2026-08-30T03:53:06Z - Granted 1 additional plan-relay round (exceptional)

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Plan rounds capped at 2; the last call returned a cached verdict predating its own prompt (13:52:25 vs 13:52:39) with the round count unchanged, so B1's fix is unreviewed. B1 was correctly held open -- the retry language survived in the Risks section after being removed from the Approach and acceptance criteria. It is now removed, and the residual risk is stated as ACCEPTED rather than mitigated: one probe cannot distinguish a dead model from a flaky minute, so a 'fail' means 'did not answer on one attempt at this timestamp' and the verdict must not overstate it as unavailable.
- Alternatives: revise the plan; human-approve the residual concerns

## 2026-08-30T03:53:14Z - Gate 6ada5db8 resolved: Grant one plan round so B1's fix is reviewed against the current plan.

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: The cap was reached after round 2; the next call returned a cached verdict predating its own prompt with the round count unchanged, so the fix has not been seen. B1 was a genuine internal contradiction: the retry language survived in the Risks section after removal elsewhere.

## 2026-08-30T07:53:09Z - The paid OpenRouter tier is authorised for slice 3, and the probe scope extends to paid-tier twins of the pinned :free ids. Twins are reported separately with tier=paid and never count toward the pinned total.

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Human instruction 2026-08-30: 'You have access to a paid open router endpoint, use that, use the bindings in the harness.' The binding is harness.toml [providers.deepseek_paid], kind = openrouter_paid, on OPENROUTER_API_KEY -- the account holding purchased credit. This was decisive: ':free' is a TIER SUFFIX, not part of the model id. openai/gpt-oss-20b:free returns 404 'This model is unavailable for free' while openai/gpt-oss-20b answers; gemma and laguna :free tiers rate-limit. Without the paid tier the honest verdict was three or four families and no viable dose-response; with it, six families are reachable and M=5 is registrable with margin.
- Alternatives: Probe only the pinned six: rejected by the instruction, and it would have reported families as unavailable when only their free tier was withdrawn. Silently substituting paid ids for pinned ones: rejected -- it would conflate 'cycle 2 is reproducible' with 'the family is reachable', which is why the verdict now carries both counts.

## 2026-08-30T07:59:15Z - Gate 36398fe0 resolved: Grant one spec round to verify the six fixes against the current diff.

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: The verdict on disk predates its own prompt (17:56:19 vs 17:58:43) with the round count unchanged, so it describes pre-fix code. Fixed and verified: sanitisation now runs before truncation (the metadata block and user_id are stripped), paid rates are fetched live with the hard-coded values as a labelled fallback, the artifact records source_tree_dirty because the probe code was uncommitted, the fingerprint covers every rendered field, the gate rejects duplicate candidate records and requires a per-call spend breakdown, and it surfaces that substitution is undetectable for 9 of 10 candidates.

## 2026-08-30T07:59:15Z - Granted 1 additional spec review round(s)

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Spec cap reached; the last call returned a cached verdict predating its own prompt. Six of the seven findings are fixed and each verified: sanitise-before-truncate (metadata and user_id now stripped), live rate fetch with labelled fallback, source_tree_dirty provenance, widened fingerprint, duplicate-record and per-call spend checks, and an explicit note that substitution is undetectable for 9/10 candidates. The seventh (paid twins using nodes.Client('openrouter')) is answered in the artifact's binding record: the paid tier is the same endpoint and key, and the ':free' suffix is what selects the free tier.

## 2026-08-30T10:13:54Z - Granted 1 additional spec review round(s)

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 4's five findings are closed. All three decide modules now write DECISIONS.md atomically (temp + os.replace) -- a direct write_text interrupted mid-way would truncate the project's durable record. Candidates carry identity_verified and the verdict reports identity-verified families separately from reachable ones, so 'ok' no longer implies the registered model answered. Spend prefers the provider's reported usage.cost over a rate reconstruction, with live catalogue rates. The auxiliary /api/v1/models request is declared in the artifact. The rollback inventory lists all five code files, two test files and two artifacts. commit-ready requires a genuine spec run bound to the current diff.

## 2026-08-30T11:30:25Z - Granted 1 additional spec review round(s)

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 5's four findings are closed and each verified. Per-panel reproducibility is DERIVED from the artifact (panelA reproducible, panelB broken by gptoss) rather than the hard-coded and false 'neither panel is reproducible'. Expected identity now defaults to the requested id with the registration's expected_resolved as an alias override, so all six families are identity-verified instead of one; an answer echoing no model id is classified substituted because identity is unverifiable. Identity is recorded on every return path including transport failures. The paid binding is resolved from harness.toml [providers.deepseek_paid] and the binding used is recorded per call. tests/test_slice3_gate.py exists with eleven negative tests, guarded against the gate->pytest->gate recursion that previously ran to timeout.

## 2026-08-30T11:38:15Z - Granted 1 additional spec review round(s)

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 6's five findings are closed, each verified. The sanitiser now redacts nine credential shapes including Authorization: Basic and X-Api-Key, which previously survived because the header pattern stopped at the first whitespace; a regression in the widened pattern (the JSON token": "value" form) was caught by its own test and restored. merge_reprobe carries superseded PAID usage forward so a re-probe no longer erases a call the account was billed for. The gate binds each record's panel, family, backend, model, tier and identity.requested against the registration rather than accepting any known agent name. The fingerprint covers the agent-to-family mapping, panel reproducibility and is_upper_bound. A missing or disabled harness binding now warns instead of silently falling back.

## 2026-08-30T11:46:11Z - Granted 1 additional spec review round(s)

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 7's five findings are closed and verified. sanitise() is now an ALLOWLIST -- it parses the error and keeps only code/message/type -- because regex-stripping the metadata object stopped at the first nested brace and left billing_email and account in the artifact; a string-valued error keeps its message rather than being replaced by a placeholder. A local /props failure now marks the candidate unverified instead of trusting its alias, since prereg_v2 pins qwen by GGUF path and parameter count. The gate requires the paid twins the verdict counts, binds each record's registered shape, and its imports are hoisted above first use. The plan's tasks describe the paid-twin scope and the single declared catalogue request.

## 2026-08-30T11:51:22Z - Granted 1 additional spec review round(s)

- Run: `20260830-134531-f0f0d997`
- Decided by: jerry.mannings@gmail.com
- Rationale: Round 8's five findings (no blockers) are closed and verified. REQUEST.md now authorises the single non-generation GET /api/v1/models, where scope belongs. A paid twin that falls back off the harness openrouter_paid binding now FAILS the gate rather than passing with a warning. The gate's paid-call accounting allows for superseded attempts, so a legitimate re-probe no longer makes the honest cumulative spend contradict the check. The artifact records source_commit as UNCOMMITTED (parent 87bfb7f) instead of quoting a commit that does not contain the probe code. The verdict's identity note no longer contradicts itself now that expected identity defaults to the requested id with one registered alias override.

## 2026-08-30T12:12:25Z - V3 SLICE 3 OUTCOME: only 3 of 6 PINNED ids still answer, but 6 families are reachable; M=5 registrable.

<!-- slice3-fingerprint: 40e91789d8108bc0 -->

Measured 2026-08-30T12:11:30Z at commit `UNCOMMITTED (parent 32fead0)`, one attempt per endpoint, no automatic retry. Registration digest `8e4950f2a98a`. Paid spend: USD 0.001378 across 6 call(s).

| agent | family | backend | status | detail |
|---|---|---|---|---|
| qwen | qwen | local | **ok** |  |
| laguna | poolside | openrouter | **fail** | HTTP 429: {"code": 429, "message": "Provider returned error" |
| glm | zhipu | hoonify | **ok** |  |
| nemotron | nvidia | openrouter | **ok** |  |
| gptoss | openai | openrouter | **fail** | HTTP 404: {"code": 404, "message": "This model is unavailabl |
| gemma | google | openrouter | **fail** | HTTP 429: {"code": 429, "message": "Provider returned error" |
| laguna_paid | poolside | openrouter | **ok** |  |
| nemotron_paid | nvidia | openrouter | **ok** |  |
| gptoss_paid | openai | openrouter | **ok** |  |
| gemma_paid | google | openrouter | **ok** |  |
| qwen_or | qwen | openrouter | **ok** |  |

**Which registered panels still run.** panelA: NOT reproducible, broken by laguna; panelB: NOT reproducible, broken by gptoss, gemma. prereg_v2's rule is 'exact pinned id or the panel is DROPPED', so a paid-tier twin does not restore a panel whose registered id has gone.

**Two counts, deliberately not merged.** Only 3 of six REGISTERED ids answered (nvidia, qwen, zhipu), so not every cycle-2 panel is reproducible as registered. But 6 distinct FAMILIES are reachable, google, openai, poolside only via a paid-tier twin of a withdrawn or rate-limited `:free` id. Cycle 3 pins its own panels and may pin those ids directly.

**Verdict, by the rule recorded 2026-08-30 BEFORE the measurement.** Margin +1 against the five required, on the reachable count. 6 families are reachable, 1 more than the five required, so one disappearance mid-run still leaves five.

**Cost consequence for slice 4.** Cycle 2 ran four of six models on free tiers; 3 of those families now require a paid tier. At 450 calls per panel that is a budget line for the registration, not a mid-run discovery.

**Consequence for slice 4.** The M=3 -> M=5 dose-response IS runnable: 6 families reachable with margin +1. Family-disjoint M=3 subsets available: 20. Slice 4 must pin the reachable ids (paid where the `:free` tier has been withdrawn or is rate limited), price the paid tiers, and record which registered panels survive (see above).

## 2026-08-30T12:23:11Z - Cycle 3 pins all SIX reachable families. The M=3 -> M=4 -> M=5 dose-response is drawn as NESTED subsets of a fixed ordering, and the sixth family is the declared margin: it is pinned and smoke-tested but not in the primary M=5 panel, so one disappearance mid-run is absorbed by promotion rather than by an unregistered substitution.

- Run: `20260830-221830-30689369`
- Decided by: jerry.mannings@gmail.com
- Rationale: Slice 3 measured six reachable families with margin +1. Nested subsets make the dose-response a within-panel comparison: M=3 is a subset of M=4 is a subset of M=5, so a change in the margin over the best single source is attributable to ADDING a source rather than to swapping panels. Independent panels at each size would confound panel composition with panel size, which is the confound cycle 1 already demonstrated when two panels of the same size returned opposite verdicts. Pinning the sixth as a declared margin follows the recorded rule of 2026-08-30: registering M=5 on a bare five would force an unregistered substitution or an abandoned arm on one disappearance, which is what prereg_v2's exact-pinned-id rule exists to prevent.
- Alternatives: Pin five and hold the sixth only as a replacement: rejected, it leaves the replacement unsmoke-tested and its promotion undocumented at registration time. Independent panels per size: rejected, it confounds composition with size.

## 2026-08-30T12:32:11Z - Cycle 3 reuses cycle 2's corpus (150 negation-family ProofWriter items, depth-5 enriched, same SHA-256) and pins qwen as the LOCAL qwen3.8-27b with qwen/qwen3.8-27b on OpenRouter as a declared fallback registered in advance.

- Run: `20260830-221830-30689369`
- Decided by: jerry.mannings@gmail.com
- Rationale: Corpus: comparability with the registered +0.220/+0.272 results is worth more than independence from a cycle whose panels are gone, and the corpus was never what failed. The reuse is disclosed, including that a shared item set makes cycle 3's dose-response evidence about panel SIZE on this corpus rather than independent evidence about the corpus. qwen: the local endpoint carries the registered weights, pinned by model_path and n_params, which is the only candidate whose identity can be verified beyond an echoed id; it is intermittent only because the owner is working on it. Declaring the OpenRouter build as a fallback in advance converts a mid-run switch from an unregistered substitution into a documented promotion -- the same discipline as the sixth-family margin.
- Alternatives: Fresh corpus draw: rejected, it forfeits comparability for independence from a cycle whose panels no longer exist. Pinning the OpenRouter qwen outright: rejected, it would abandon the only endpoint whose weights the registration can verify, and the owner reports the local one will be stable.

## 2026-08-30T12:42:17Z - Cycle 3's corpus is ALL 2,353 locally available ProofWriter items (1,405 depth-3/test + 948 depth-5/test), not cycle 2's 150-item subset and not a larger download. This supersedes the earlier 'reuse cycle 2's corpus' decision of 2026-08-30.

- Run: `20260830-221830-30689369`
- Decided by: jerry.mannings@gmail.com
- Rationale: Human instruction 2026-08-30: use what is already local, scale later. The power calculation from slice 1's measured margins (+0.033 to +0.089 nats, per-item SD 0.16-0.25) shows 150 items cannot power the dose-response: detecting a 0.03-nat increment needs ~1,103 items and a 0.02-nat increment ~2,481. 2,353 items powers roughly a 0.02-nat increment, which is the largest defensible design available without new downloads. Cost is ~$29 in API spend. The binding constraint is CPU NLI at a MEASURED 30 pairs/sec: 2,353 items x 6 agents is ~12.4M pairs, about 4.8 days of continuous CPU. Cycle 2's 150 items remain a subset, so comparability with the registered +0.220/+0.272 results is preserved on that stratum.
- Alternatives: 150 items (cycle 2's corpus): rejected, the dose-response would be badly underpowered and a null uninterpretable. 10,000 items: rejected for now, ~20 days of CPU NLI at the measured rate; revisit once a CUDA torch build is available, since two GPUs are present but this venv's torch is 2.13.0+cpu.

## 2026-08-30T13:19:59Z - The NLI instrument runs in fp16, not fp32: the MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli config declares dtype=float16 and transformers 5.14.1 honours that on CPU as well as GPU, so cycles 1-2 were measured in fp16. Cycle 3 switches the instrument to fp32 on GPU, and fp16-cached and fp32-computed NLI must NEVER be mixed inside one analysis.

- Run: `20260830-221830-30689369`
- Decided by: jerry.mannings@gmail.com
- Rationale: Discovered while porting NLI to CUDA: CPU-vs-GPU deviations landed on exact powers of two (2^-7, 2^-9), which is quantisation, not float drift. Measured on 800 corpus pairs: cpu/fp32 vs gpu/fp32 = 7.8e-06 with 0 argmax flips; cpu/fp16 vs gpu/fp16 = 4.4e-03 with 1 flip; cpu/fp16 vs cpu/fp32 = 3.8e-03. fp16 is therefore DEVICE DEPENDENT -- a naive GPU port would have made results a function of which card ran them, which is exactly the kind of silent instrument change pre-registration exists to prevent. fp32 is device independent to 7.8e-06, and on CPU is also 2.7x FASTER than fp16 (114.7 vs 43.2 pairs/sec) because CPUs emulate fp16 rather than implement it, so the frozen path chose the slowest, least accurate and least reproducible of the available options. End-to-end check on cycle 2 panel A (150 items, 29,509 claims): all 1,565 observations identical under fp32/GPU -- 0 label flips, none added, none dropped -- with max alignment-score movement 2.1e-03. But the smallest observed threshold margin is 0.0021, exactly 1x that perturbation, with 2 observations inside it; near-threshold cases scale with corpus size, so zero flips at 150 items is not a guarantee at 2,353. Hence the no-mixing rule, enforced by pointing WCT_CACHE at a separate root per precision. Frozen cache verified uncontaminated (embed=914, nli=1826, generation=2176 unchanged) and all four frozen panels still reproduce exactly.
- Alternatives: Port to GPU in fp16 to match the cached values bit-for-bit: rejected, fp16 does not reproduce across devices (4.4e-03, with flips), so it would bake the card into the measurement. Keep CPU fp16 for comparability: rejected, 79.7 h per cycle-3 pass versus 1.4 h, and it preserves a device-dependent instrument. Reuse the fp16 cache and compute only new pairs in fp32: rejected, that is precisely the mixing the margin analysis shows is unsafe.

