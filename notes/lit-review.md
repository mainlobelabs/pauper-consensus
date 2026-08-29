# Literature Review — wave-consensus v2 (novelty check + venue)

- Date: 2026-08-29
- Prepared by: Frank (automated lit review per `tasks/lit-review.md`)
- Method: Tavily + web search for discovery; **every arXiv ID below verified against
  `export.arxiv.org` (title + abstract + authors)** before citation. Items that could
  not be verified are flagged in §6, not silently dropped.
- Scope: novelty check and venue recommendation for an arXiv submission (primary goal),
  with a stretch target of a peer-reviewed journal.

---

## 1. Our study in one paragraph (framing for the review)

wave-consensus v2 is a **pre-registered measurement study** of claim verification.
From 200 real news articles (Jul–Aug 2026) we constructed 8,000 labeled claims
(40 per article, with a cutoff-gap design that manufactures plausible falsehoods).
A jury of **12 configurations of 3–4B local LLMs** — 4 families (Qwen3.5-4B,
Phi-4-mini, Gemma-3-4B, Llama-3.2-3B) × 3 prompt conditions (base, reason-included,
votes-only) — casts one PASS / FAIL / NOT_STATED vote per claim: **96,000 votes**,
run via llama.cpp on a Mac Studio M3 Ultra in 13.2 h. Votes are aggregated into
per-claim truth probabilities by a **Dawid-Skene-style EM calibration**
(per-config weights + per-class affine maps) **fitted once on the prior v1 corpus
and applied frozen**. Pre-registered result: **+0.20 nats log-loss vs the frozen
baseline (95% CI [0.187, 0.217]), all four test cells green** (v1's smaller jury:
+0.09). Cost is **measured, not estimated: ~A$11 per 96k votes on owned hardware**
(~A$5.5 estimated on 2× used 2018 2080 Ti). A head-to-head against a single
**Qwen 27B FP8** (RTX PRO 5000 Blackwell, 48 GB) is in progress: at 50%, 94.1% exact
label agreement, jury-FAIL precision vs 27B 96.9%, 27B adds ~3% extra catches on
jury-PASS cells. Protocol: frozen YAML + sha256 manifest + git tag, mechanical
decision gates, per-item spend caps.

---

## 2. Closest prior work (12 entries, verified)

### A. Label aggregation of LLM judges — the method cluster we must differentiate from

**1. Balasubramanian, Podkopaev & Kasiviswanathan (2026). "Dependence-Aware Label
Aggregation for LLM-as-a-Judge via Ising Models."**
arXiv:2601.22336 — https://arxiv.org/abs/2601.22336

Models binary LLM-judge votes with a class-dependent Ising model; shows that under
inter-vote correlation the conditional-independence assumption used by Dawid-Skene
and majority voting can be *strictly suboptimal*, even inverting the Bayes label;
beats classical baselines on three real-world LLM-evaluation datasets.
**Difference from us:** they propose a *new dependence model*; we use the
*simplest* member of this lineage (plain class-dependent EM) and show it, fitted
once and applied frozen across corpora, still clears a pre-registered bar on a
labeled news-claim task. No pre-registration, no cost accounting, no head-to-head
vs a single large model. Complementary: their theory motivates expecting our simple
EM to be suboptimal — our result is evidence that in this regime (heterogeneous
3–4B families × prompt diversity, 3-class verdicts) simple calibration is already
a large measurable win.

**2. Zhao et al. (2026). "CARE: Confounder-Aware Aggregation for Reliable LLM
Evaluation."** arXiv:2603.00039 — https://arxiv.org/abs/2603.00039

Confounder-aware aggregation: judge scores = latent quality + shared confounders
(verbosity, style, training artifacts), separated *without ground truth*, with
identifiability guarantees; up to 26.8% error reduction across 12 benchmarks
(continuous, binary, pairwise).
**Difference from us:** label-free method for continuous scores and preferences;
ours is label-based (EM consumes the 8,000 ground-truth labels), 3-class verdicts,
pre-registered news-verification domain, with measured cost and a 27B head-to-head.
They attack exactly the assumption our pipeline inherits (independent errors), so
the paper must cite CARE and acknowledge that part of our EM gain may be per-config
quality weighting rather than dependence modeling.

**3. Kohli (2026). "Nine Judges, Two Effective Votes: Correlated Errors Undermine
LLM Evaluation Panels."** arXiv:2605.29800 — https://arxiv.org/abs/2605.29800

Nine frontier LLMs on three NLI datasets (100 human annotations each): Kish
effective sample size says a 9-judge panel ≈ **2 effective votes**; ~75% of nominal
independence is lost to co-failure; panel accuracy lands 8–22 points below the
independent-vote ideal; the best single judge beats the full panel; smarter
aggregation closes at most ~11% of the gap.
**Difference from us:** frontier (highly correlated) models, NLI, no ground-truth
calibration, no domain study, no cost. **This is the result most at odds with
ours — the skeptic's anchor.** Our counter-position: different regime
(heterogeneous small families × prompt conditions; news claims with a third
state; ground-truth-calibrated EM) and a measured +0.20 nats (CI excludes zero)
on a real corpus. The paper should report an effective-voter diagnostic
(our pre-registered E0 residual-correlation item is exactly this) and confront
the result directly rather than sidestepping it.

**4. Ai, Pan, Simchi-Levi, Tambe & Xu (2025). "Beyond Majority Voting: LLM
Aggregation by Leveraging Higher-Order Information."**
arXiv:2510.01499 — https://arxiv.org/abs/2510.01499

Training-free aggregation that uses first- and second-order information
(per-model accuracy + inter-model correlations) with a provable improvement over
majority voting; validated on UltraFeedback, MMLU, and a healthcare benchmark.
**Difference from us:** a better *decision rule* over vote distributions across
agents on reasoning/preference/health tasks; no domain pre-registration, no
consumer-hardware cost, no calibrated truth-probability output, no single-large
model head-to-head on the same claims.

### B. Calibration of ensembles and evaluators

**5. (EMNLP 2024) "Bayesian Calibration of Win Rate Estimation with LLM
Evaluators."** arXiv:2411.04424 — https://arxiv.org/abs/2411.04424 ·
Anthology: https://aclanthology.org/2024.emnlp-main.273/

LLM evaluators produce noisy pairwise preferences; models each evaluator's
reliability and calibrates the resulting win-rate estimates (Bradley–Terry style).
**Difference from us:** pairwise win rates, not 3-class truth verdicts; no news
domain, no cost, no pre-registration. **Closest on the calibration move:** model
annotator reliability, then correct the aggregate. Ours applies the same idea to
class-conditional error rates and outputs per-claim truth probabilities with a
frozen cross-corpus transfer none of these do.

**6. Camuffo et al. (2026). "Variance-Aware LLM Annotation for Strategy
Research."** arXiv:2601.02370 — https://arxiv.org/abs/2601.02370

A protocol paper for reliable LLM annotation in strategy research: identifies
five sources of variance, shows 12–85-point swings from prompt/model choice, and
specifies sampling budgets, aggregation rules, and reporting standards — framed
as auditable measurement infrastructure.
**Difference from us:** they diagnose *variance* and prescribe reporting; we
deliver the *aggregation result* (calibrated probabilities + pre-registered gate)
plus measured cost. Complementary; cite for the pre-registration/protocol framing.

### C. Ensembles, self-consistency, small vs large

**7. Wang et al. (2022). "Self-Consistency Improves Chain of Thought Reasoning in
Language Models."** arXiv:2203.11171 — https://arxiv.org/abs/2203.11171

Sample multiple reasoning paths from one model and majority-vote the answer;
large gains on reasoning benchmarks.
**Difference from us:** same model, task-agnostic, uncalibrated majority over
paths. Ours aggregates **across models and prompt conditions** with calibrated,
class-conditional weights, over 3-class verdicts. This is the canonical
"consensus voting is old" anchor — cite it as the single-model ancestor and
contrast.

**8. Zhang, Li, Wang et al. (2025). "The Avengers: A Simple Recipe for Uniting
Smaller Language Models to Challenge Proprietary Giants."**
arXiv:2505.19797 — https://arxiv.org/abs/2505.19797

Embeds small-model outputs, clusters, scores, and votes to beat proprietary
flagship models on broad benchmarks.
**Difference from us:** generic benchmarks (no claim verification),
cluster/vote heuristics rather than ground-truth-calibrated aggregation, no
measured per-vote cost, no pre-registration, no head-to-head against one 27B
model on the same claims. Closest on "small ensemble vs big single model."

**9. (2026) "When Does Combining Language Models Help? A Co-Failure Ceiling on
Routing, Voting, and Mixture-of-Agents Across 67 Frontier Models."**
arXiv:2606.27288 — https://arxiv.org/abs/2606.27288

Theory + large-scale study: ensemble accuracy is bounded by 1 − β (the
all-wrong rate), and β is not identifiable from pairwise correlations; the
standard tetrachoric single-factor estimate underestimates β by ~2.5× on open
math models; low-ρ heterogeneous ensembles beat high-ρ Mixture-of-Agents.
**Difference from us:** frontier models on math/code/GPQA. **This ceiling is the
exact prior our 27B head-to-head measures:** how close does a small-model jury
get to a single large model on a *verifiable* task, and at what cost? Our
94.1% agreement / 96.9% FAIL precision / +3% PASS-cell numbers are an empirical
β-style quantification the theory paper predicts but does not deliver for the
news-verification domain.

### D. News fact verification pipelines

**10. Yoon, Jung, Yoon et al. (2024/2025). "HerO at AVeriTeC: The Herd of Open
Large Language Models for Verifying Real-World Claims"; follow-up "HerO 2"
(Team HUMANE at AVeriTeC 2025).** arXiv:2410.12377 —
https://arxiv.org/abs/2410.12377 · arXiv:2507.11004 —
https://arxiv.org/abs/2507.11004

Open-LLM-only fact-verification system for the AVeriTeC shared task (query
augmentation for retrieval, in-context prompting, fine-tuned veracity model);
2nd place in 2024, with a 2025 iteration.
**Difference from us:** a shared-task *pipeline* (retrieval + prompting +
fine-tuning) optimized for leaderboard score; no pre-registration, no
ground-truth-calibrated aggregation, no cost accounting, no single-large-model
head-to-head; benchmark claims, not a constructed labeled corpus from real
articles. Closest on **domain + open models**.

**11. Kryscinski et al. (2020). "Evaluating the Factual Consistency of Abstractive
Text Summarization" (FactCC).** EMNLP 2020 —
https://aclanthology.org/2020.emnlp-main.750/

Weakly supervised factual-consistency classifier: synthetic labels from
rule-based sentence transformations train a BERT classifier for
summary-vs-source consistency (with FactCCX span explanations).
**Difference from us:** a single-model classifier on synthetic labels; no LLM
jury, no aggregation, no pre-registration, no cost. It is the weak-supervision +
factual-consistency lineage anchor for our instrument failure in v1 (NLI
alignment 0/607). **Cite accurately:** it is a summarization
factual-consistency paper, *not* a news benchmark (the task file's "FactCC 2020,
news domain" shorthand is wrong on both counts).

**12. Thorne et al. (2018). "FEVER: a Large-scale Dataset for Fact Extraction and
VERification."** arXiv:1803.05355 — https://arxiv.org/abs/1803.05355 (NAACL 2018)

185k claims against Wikipedia with SUPPORT / REFUTE / NOT ENOUGH INFO labels; the
standard fact-verification task definition.
**Difference from us:** a dataset/task definition, not a method. Our 3-class
verdict scheme (PASS / FAIL / NOT_STATED) is a direct descendant of its label
scheme; our corpus is real news articles with manufactured cutoff-gap falsehoods
rather than claims against Wikipedia. Lineage anchor.

### Secondary related work (one line each, verified)

- FActScore (Min, Krishna et al., 2023) — arXiv:2305.14251, https://arxiv.org/abs/2305.14251 — atomic fact decomposition + verification of long-form generation; the instrument our atomic-claim design inherits.
- MiniCheck (Tang, Laban & Durrett, 2024) — arXiv:2404.10774, https://arxiv.org/abs/2404.10774 — efficient, answer-independent document-vs-claim fact checking; single-model baseline for the same task family.
- Multi-agent debate (Du, Li et al., 2023) — arXiv:2305.14325, https://arxiv.org/abs/2305.14325 — debate as an aggregation mechanism; adds multi-round interaction cost our one-vote-per-config design avoids.
- ChatEval (Chan et al., 2023) — arXiv:2308.07201, https://arxiv.org/abs/2308.07201 — multi-agent chatroom evaluation.
- "Debating Truth" (2025) — arXiv:2507.19090, https://arxiv.org/abs/2507.19090 — debate for factuality.
- Courtroom-style deliberation (Chowdhury et al., 2026) — arXiv:2603.28488, https://arxiv.org/abs/2603.28488 — role-based multi-agent judgment.
- Snorkel (Ratner et al., 2017) — arXiv:1711.10160, https://arxiv.org/abs/1711.10160 — programmatic labeling + DS-EM aggregation system; direct lineage anchor for our EM.
- WRENCH (Zhang, Yu, Li et al., 2021) — arXiv:2109.11377, https://arxiv.org/abs/2109.11377 — comprehensive weak-supervision benchmark.
- Dawid & Skene (1979) — JASA 74(366):89–93, https://doi.org/10.1080/01621459.1979.10482046 — the original EM model of observer reliability.
- Raykar et al. (2010), "Learning from Crowds" — JMLR 11:1225–1247, https://jmlr.org/papers/v11/raykar10a.html — gold-standard-free DS generalization.
- Niimi (2025), "A Simple Ensemble Strategy for LLM Inference" — arXiv:2504.18884, https://arxiv.org/abs/2504.18884 — simple ensemble for stable text classification.
- Sahnan, Corney, Larraz et al. (2026) — arXiv:2503.17684, https://arxiv.org/abs/2503.17684 — end-to-end automated fact-check article writing (TAACL 2026).
- On-premise LLM cost-benefit (2025) — arXiv:2509.18101, https://arxiv.org/abs/2509.18101 — org-level deployment economics.
- "The Price of Prompting" (2024) — arXiv:2407.16893, https://arxiv.org/abs/2407.16893 — prompt-compute tradeoffs.
- Energy considerations of LLM inference (2025) — arXiv:2504.17674, https://arxiv.org/abs/2504.17674 — energy side of the cost story.
- LLM Council (Liu et al., 2025) — arXiv:2505.08532, https://arxiv.org/abs/2505.08532 — multi-agent consultation framework; adjacent, not a direct competitor.

---

## 3. Verdict

**Is it novel? Yes — as a combination and a protocol, not as any single
component.** Every component has a predecessor:

| Component | Predecessor |
|---|---|
| EM aggregation of noisy votes | Dawid & Skene 1979; Snorkel 2017 |
| Majority/consensus over model outputs | Self-Consistency 2022 |
| Smaller-model ensemble vs flagships | Avengers 2025; co-failure ceiling 2026 |
| Calibrated aggregation of LLM judges | Ising 2026; CARE 2026; OW/ISP 2025; Bayesian win-rate 2024 |
| Claim verification on news/web claims | FEVER 2018; FActScore 2023; MiniCheck 2024; HerO/AVeriTeC 2024–25 |
| Pre-registered annotation protocol | Variance-Aware 2026 |

What is new, to our knowledge, is the **conjunction**:

1. **Frozen cross-corpus transfer of the calibration** — DS-EM fitted on one
   corpus, applied frozen to a second, larger corpus, and shown to beat the
   frozen baseline (+0.20 nats, CI [0.187, 0.217]). None of the 2026 aggregation
   papers refit per dataset and none test transfer; this is the core method claim.
2. **A pre-registered measurement protocol with mechanical gates** (frozen YAML +
   sha256 manifest + git tag) applied to an LLM jury, in the spirit of the
   variance-aware-annotation protocol literature but with hard go/no-go criteria.
3. **Measured per-vote cost on owned consumer hardware** (~A$11 / 96k votes;
   13.2 h on a Mac Studio; ~29 GB total VRAM barrier for 12 voters vs 48 GB for
   the 27B) — org-level cost papers exist, workload-level per-vote cost for an
   LLM jury does not.
4. **A quantified boundary against a single large model** — head-to-head on the
   same claims (94.1% agreement, 96.9% FAIL precision, +3% PASS-cell), which is
   the empirical answer the co-failure-ceiling theory predicts but never measures
   for this domain.
5. **Prompt condition as a voter design axis** — the same family votes under three
   prompt conditions, so prompt style is a first-class source of voter diversity
   that EM can weight, which no surveyed paper exploits.

**Defensible one-sentence novelty claim (use in the paper):**

> "To our knowledge, this is the first pre-registered, cross-corpus-validated
> evaluation of a heterogeneous small-model LLM jury for news-claim verification
> in which Dawid-Skene-style EM calibration is fitted once and applied frozen,
> per-vote cost is measured on owned consumer hardware, and the jury's boundary
> against a single 27B model is quantified head-to-head."

**Closest work a reviewer would cite first:**

- Method: **arXiv:2601.22336** (Ising label aggregation) — strongest methodological precedent.
- Skeptic: **arXiv:2605.29800** (Nine Judges, Two Effective Votes) — the result most likely to be used *against* us.
- Domain: **arXiv:2410.12377** (HerO at AVeriTeC) — nearest domain + open-model work.

**"We reinvented X" risks and positioning:**

1. **Dawid-Skene / Snorkel** — EM is 45 years old. Positioning: we do not claim a
   new estimator; we claim frozen cross-corpus transfer of a *simple* one to a
   3-class, prompt-conditioned LLM jury on real news claims, plus pre-registration
   and measured cost. The 2026 cluster (Ising, CARE, Nine Judges) shows the field
   has moved past naive conditional independence — cite all three and frame the
   result as evidence that simple calibration suffices for practitioners on
   consumer hardware.
2. **Self-Consistency** — consensus voting is old. We aggregate across models and
   prompt conditions with class-conditional calibrated weights; cite as the
   single-model ancestor and contrast.
3. **Avengers / co-failure** — small-vs-large ensembles are studied. Ours is a
   domain-specific, ground-truth-labeled, cost-quantified study; the co-failure
   ceiling is the prior that *motivates* the 27B head-to-head.
4. **Nine Judges** — "aggregation can't fix correlated judges." Most serious
   risk. Response: (i) different model regime (heterogeneous small families ×
   prompt conditions vs correlated frontier models); (ii) ground-truth-calibrated
   EM vs label-free aggregation; (iii) a measured +0.20 nats with CI excluding
   zero on a real corpus. Report an **effective-voter count**
   (Kish n_eff from the pre-registered E0 residual-correlation item) so the
   paper confronts the result directly.
5. **HerO / AVeriTeC** — they optimize leaderboard score with retrieval +
   fine-tuning; we measure a pre-registered bar with a fixed instrument and no
   task-specific training. Cite as the domain's shared-task lineage, not as the
   method competitor.

**Key tension to address head-on (not bury):** Nine Judges (2605.29800) and the
co-failure ceiling (2606.27288) jointly predict that a 12-voter panel of
correlated LLMs has a small effective sample size. Our data (12 configs across 4
families × 3 prompt conditions, all cells green, CI [0.187, 0.217]) is a
counterexample *in this regime* — but the paper must state the regime explicitly
and report the n_eff diagnostic, or a reviewer will cite Nine Judges and move on.

---

## 4. Venue fit

**arXiv category: `cs.CL` primary, `cs.AI` cross-list** (optional `cs.LG`).
Rationale: this is a measurement study of LLM behavior on an NLP verification
task; the cost/infrastructure angle is secondary. `cs.CY` is a weaker fit for
this content and only worth adding if the framing shifts toward community
fact-checking practice.

**Stretch journals (ranked):**

1. **JASIST** (first choice). Fit: strong. Publishes fact-checking, information
   quality, pre-registered empirical methods, and information-infrastructure
   studies. Our "calibrated jury as a measurement instrument + cost barrier"
   framing is squarely JASIST; the readership cares about the implications of
   verification methods, not estimator novelty, and pre-registration is
   welcomed there.
2. **PeerJ Computer Science** (safe fallback). Fit: good. Open,
   methods/empirical-friendly, fast review; a realistic landing spot if method
   novelty is judged incremental and the story is "rigorous pre-registered
   measurement."
3. **EMNLP Findings** (if we push the method angle). Fit: moderate. The 2026
   LLM-judge-aggregation cluster (Ising, CARE, Nine Judges, OW/ISP) shows an
   active reception venue. Required emphasis: frozen transfer of class-dependent
   calibration for 3-class LLM verdicts + the n_eff diagnostic. Risk: read as an
   application rather than a method.
4. **Journal of Computational Social Science**. Fit: moderate. Works if framed as
   computational measurement of the news-verification ecosystem (instrument
   design, replication culture); the cost/hardware angle lands less well.
5. **New Media & Society**. Fit: low–moderate. Only with a reframe toward
   "fact-checking infrastructure in the platform-media era"; methods reviewers
   will push on estimator detail.
6. **Digital Scholarship in the Humanities** — skipped: weakest fit of the
   candidates considered.

---

## 5. Suggested angle

**Recommended title:**

> **Twelve Small Judges: A Pre-Registered, Cost-Quantified Jury of 3–4B Language
> Models for News-Claim Verification, Head-to-Head with a Single 27B Model**

Alternative (shorter, cost-forward):

> **The Calibrated Jury at Eleven Dollars: Pre-Registered News-Claim
> Verification by 3–4B LLMs on Consumer Hardware**

**Three-sentence abstract:**

> We pre-register and run a jury of twelve 3–4B local language-model
> configurations — four families × three prompt conditions, each voting
> PASS, FAIL, or NOT_STATED per claim — to verify 8,000 labeled claims
> constructed from 200 real news articles, and aggregate the 96,000 votes into
> per-claim truth probabilities with a Dawid-Skene-style EM calibration fitted
> once on a prior corpus and applied frozen. The jury improves log-loss by
> 0.20 nats (95% CI [0.187, 0.217]) over the frozen baseline with all
> pre-registered test cells passing, at a measured cost of roughly A$11 on owned
> consumer hardware. In a direct head-to-head, a single 27B model agrees with
> the jury on 94.1% of claims, the jury's FAIL verdicts retain 96.9% precision
> against the 27B, and the 27B adds only ~3% extra catches on jury-PASS cells —
> quantifying where a calibrated small-model jury can stand in for a single
> large model on verifiable claims.

---

## 6. Open items and caveats

1. **v1 paper link missing.** Mannings & Marzuki, "The Flip Was in the
   Instrument: Two Pre-Registered Cycles of Cross-Model Proposition Aggregation"
   (2026) was not found on arXiv or via web search in this pass. Obtain the
   preprint link before submission; it is the replication target and part of the
   story.
2. **"GenIE" citation is ambiguous.** The task file's "Snorkel GenIE 2022"
   anchor (Hsieh et al., "GenIE: Generating In-Context Examples for Low-Resource
   Text Classification") has no stable arXiv/ACL Anthology link found in this
   pass, and the name collides with Josifoski et al. (2022), "GenIE: Generative
   Information Extraction" (NAACL 2022, https://aclanthology.org/2022.naacl-main.342/).
   Resolve before writing related work, or lean on Snorkel + WRENCH + Dawid-Skene
   for the weak-supervision lineage (which already covers it).
3. **27B head-to-head is 50% complete.** All head-to-head numbers in §1 and §5
   are provisional; update the review and the abstract at 100%.
4. **2080 Ti cost figure is an estimate** (kept labeled as such); the
   owned-Mac figure is the measured anchor.
5. **Add the n_eff / effective-voter diagnostic to the paper** (pre-registered
   E0 residual correlation is already in place). It is the direct answer to
   Nine Judges and the co-failure ceiling.
6. **Task-file "FactCC 2020" anchor corrected:** it is Kryscinski et al.'s
   summarization factual-consistency paper (EMNLP 2020), not a news benchmark —
   cite it accurately as the weak-supervision lineage anchor.
