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

