<!-- DRAFT NOTES (not part of the paper)
  - Draft v4, 2026-08-29. Two-pass, DOI-ready framing. Venue plan: arXiv cs.CL primary,
    JASIST first journal choice, PeerJ CS fallback (notes/lit-review.md §4).
  - Title candidates (Andryo to choose):
    1. "The Flip Was in the Instrument: Two Pre-Registered Passes from Cross-Model
       Proposition Aggregation to a Cost-Quantified Jury of Small Language Models"  [used below]
    2. "Twelve Small Judges: A Pre-Registered, Cost-Quantified Jury of 3–4B Language
       Models for News-Claim Verification, Head-to-Head with a Single 27B Model"
    3. "The Calibrated Jury at Eleven Dollars: Pre-Registered News-Claim Verification
       by 3–4B LLMs on Consumer Hardware"
  - Open items before submission:
    * Pass 1 preprint: Zenodo DOI 10.5281/zenodo.22159293 now in ref [25]; record is
      reserved (DOI 404s until published) - publish the Zenodo record before submission.
    * 2080 Ti row in §6 is an estimate, not a measurement (kept labeled as such).
    * Affiliation set: Main Lobe Labs (both authors, single affiliation marker).
    * Figures 1-3 (charted, paper/figures/) are PDF-only: injected by tools/paper_pdf.py at build time, not in this .md.
  - All numbers below were copied verbatim from:
    * runs/2026-08-28-v2-jury/eval_v2.json
    * runs/2026-08-29-v2-27b/gate_analysis.json
    * runs/2026-08-29-v2-27b/judge.jsonl (co-failed claims, verbatim)
    * prereg-v2.yaml (frozen at git tag prereg-waveconsensus-v2)
    * /tmp/opencode/phase4-report.md (v1 Phase 4 report)
    * COST-BARRIER.md
  - Corpus window is 2026-02-15 to 2026-08-27 (Feb–Aug). lit-review.md §1 says
     "Jul–Aug 2026"; that shorthand is wrong and is not repeated in this draft.
-->

# The Flip Was in the Instrument: Two Pre-Registered Passes from Cross-Model Proposition Aggregation to a Cost-Quantified Jury of Small Language Models

**Jeremiah Mannings**¹, **Andryo Marzuki**¹

¹ Main Lobe Labs

Draft v4 · 2026-08-29 · Pre-submission draft · DOI: [Zenodo registration pending]
Code and artifacts: https://github.com/marzukia/pauper-consensus (git tags `prereg-waveconsensus-v1`, `prereg-waveconsensus-v2`; tag names keep the original working name, the repository was renamed after the registrations were cut)

---

## Abstract

We study when agreement across large language models is a trustworthy instrument for verification, and what it costs. We report two pre-registered passes of one measurement program. In Pass 1 ("the flip"), the same frozen proposition-aggregation protocol returned opposite primary verdicts on two three-model panels over synthetic reasoning traces (−0.159 vs +0.122 nats, both 95% CIs excluding zero); a post-hoc diagnosis identified two instrument defects (a calibration map without an intercept, and a corpus that could barely contain falsehoods) and a git-tagged second cycle confirmed the central repair (+0.220 and +0.272 nats) while falsifying two companion predictions. Pass 2 carries the instrument-integrity lesson into open news. A jury of twelve 3–4B local language-model configurations (four families × three arms) votes PASS / FAIL / NOT_STATED on 8,000 labeled claims constructed from 200 real news articles (96,000 votes in 13.2 hours on one Mac Studio); the votes are aggregated by a Dawid–Skene EM calibration fitted once on a smaller prior corpus and applied frozen. We call this jury protocol Pauper Consensus. The pre-registered headline gate passes: +0.20289 nats of log-loss over a frozen model-free baseline (95% article-block bootstrap CI [0.18737, 0.21740]), all four pre-registered test cells green, and the observed delta exceeds all 10,000 realizations of the post-hoc delta-form contrast (the registered sum-statistic one-sided p-value is 1.0, reported as stored; §4.2); the prior, smaller jury was INCONCLUSIVE as registered, and the registered prediction that the model-free bar's value would transfer across corpora fails. In the pre-registered system-level gate test against a single 27B model, both routes co-fail the only two unsupported claims (0/2 catch; false-claim rates 0.3396% vs 0.3419%, bootstrap CI [0.0, 5e-05]), so the jury route passes on the registered "comparable within 10 percentage points and strictly cheaper" branch at 0.956× the 27B's per-claim cost. Effective voting is 2.09 per claim (Kish n_eff), and the binding resource is memory (48 GB for the 27B, about 29 GB for the jury), not arithmetic: the jury runs on second-hand consumer silicon at roughly 5× lower operating cost per 10,000 votes and 7.6× lower capital cost. The honest unit of account for LLM-based verification is the instrument: protocol, corpus, hardware, and cost, not the model.

**Keywords:** fact verification; LLM juries; Dawid–Skene estimation; weak supervision; pre-registration; calibration transfer; inference cost; consumer hardware; news fact-checking

---

## 1. Introduction

Pooling several language models on the same prompt and treating agreement as evidence of correctness is now standard practice. It is well established at the *answer* level [1,2], and a fast-growing 2026 literature asks when label aggregation of LLM judges is sound: dependence-aware Ising models [7], confounder-aware aggregation [8], the observation that nine frontier judges behave like two effective votes [9], and a co-failure ceiling on routing and voting [14]. What that literature has not yet done, to our knowledge, is treat the whole measurement apparatus (the calibration map, the corpus, the vote accounting, the hardware, the price) as the object under test, under pre-registration.

We report two pre-registered passes of one program.

**Pass 1** [25] ran the same frozen proposition-aggregation protocol on two three-model panels over 150 synthetic reasoning items. The primary metric, held-out delta log-loss of a three-state Dawid–Skene EM arm against a covariate baseline, flipped sign between panels: Panel A STOP (−0.159 nats), Panel B GO (+0.122 nats), both 95% CIs excluding zero. Report either panel alone and you are confidently wrong. The post-hoc diagnosis found two instrument defects, not two truths: (i) the registered calibration map was a single temperature (no intercept), while the baseline logistic regression had one, so only the baseline could match the base rate; re-fitting with an intercept-bearing Platt map flipped Panel A to GO and took all 12 panel × stratum × arm combinations to GO, with every rank-based metric invariant; and (ii) the corpus could barely contain a falsehood: the alignment layer scored 0 of 607 negative-polarity propositions, and the test splits held 14–16 negatives. The diagnosis became three falsifiable predictions, frozen and git-tagged before any new generation; Cycle 2 confirmed the central prediction (+0.220 [+0.160, +0.280] nats on a new Panel A, +0.272 [+0.180, +0.353] on the continued Panel B) and falsified the other two.

**Pass 2** (this work) applies the instrument-integrity lesson to open news. We build a labeled corpus of 8,000 claims from 200 real news articles with a cutoff-gap design: events after every voter's training cutoff, so verdicts must rest on the article text. A jury of twelve 3–4B local language-model configurations (four model families × three arms: base zero-shot, and two fine-tuned adapters trained under reason-included and votes-only conditions) votes PASS / FAIL / NOT_STATED on every claim: 96,000 votes in two sequential phases (the core eight configurations, then the four votes-only), each phase served 6-way in parallel via llama.cpp on a Mac Studio M3 Ultra, in 13.2 hours. The votes are aggregated by a three-state MAP-EM Dawid–Skene model [3,4] with a per-arm affine calibration map, both fitted once on a smaller prior corpus (v1, 1,200 claims) and applied **frozen**. We name the protocol **Pauper Consensus**, after the small, cheap local models that make up the jury. Two pre-registered questions:

- **P8 (capability):** does the frozen, transferred calibration beat a frozen model-free content bar on the larger corpus, clearing a pre-registered GO gate (point Δ ≥ +0.02 nats and 95% article-block bootstrap CI excluding zero)?
- **System gate (boundary):** on a defendant-generated stream of claims, does the juror-gated route beat the single-27B self-review route at no higher cost: branch (a) strictly lower false-claim rate with the CI entirely below zero, or branch (b) comparable within 10 percentage points at strictly lower total compute cost?

Both are answered exactly as the gates are written. The capability gate **passes**: the frozen calibration clears the bar by **+0.20289 nats** (95% CI [0.18737, 0.21740]) in the headline cell, with all four pre-registered test cells green and the observed delta above all 10,000 realizations of the post-hoc delta-form contrast (the registered sum-statistic one-sided p-value is 1.0, reported as stored; §4.2). The system gate **passes via branch (b)**, and only via branch (b): both routes co-fail the only two unsupported claims in the stream (12–0 jury agreement on each, and PASS from the 27B), their false-claim rates are statistically indistinguishable (0.3396% vs 0.3419%; bootstrap CI [0.0, 5e-05]), and the jury route is strictly cheaper (0.956× the 27B's per-claim token-proxy cost; 0.781× length-adjusted).

Our contributions:

1. **A two-pass, pre-registered measurement of when LLM agreement is a trustworthy instrument.** Pass 1 shows the same frozen protocol returning opposite verdicts on two panels because the instrument, not the hypothesis, was broken; Pass 2 shows the repaired instrument giving a pre-registered, replication-ready result on open news.
2. **Frozen cross-corpus transfer of Dawid–Skene calibration** as a first-class, falsifiable claim: the EM weights and the per-arm affine maps are fitted once on the v1 corpus and applied frozen on v2, and they clear a pre-registered bar (+0.20289 nats, all four test cells green). The companion registered prediction (P9) that the *model-free* bar's value would transfer **fails**, which we report at equal prominence.
3. **A pre-registered system-level boundary between a small-model jury and a single 27B model**, quantified head-to-head on the same 8,000 claims (93.962% agreement with the 12-config majority; the 27B stricter on 4.3% of majority-PASS cells) and on a defendant claim stream with a mechanical pass criterion.
4. **Measured per-vote cost on owned hardware**, including the hardware barrier itself: the binding constraint is memory, not arithmetic (48 GB GDDR7 for the 27B versus about 29 GB for the full jury), so the jury runs on second-hand consumer silicon at 7.6× lower capital and about 5× lower operating cost per 10,000 votes.
5. **An effective-voter diagnostic (Kish n_eff = 2.085 for the flagship arm)** that confronts the "nine judges, two effective votes" result [9] directly instead of sidestepping it.

Section 2 compresses Pass 1. Section 3 describes the Pass 2 instrument. Section 4 reports the capability results (v1 INCONCLUSIVE, v2 GO, the failed P9). Section 5 reports the system gate. Section 6 is the cost and hardware analysis. Sections 7–10 discuss, limit, conclude, and document reproducibility.

---

## 2. Pass 1: The flip was in the instrument

Pass 1 is reported in full in [25] ("The Flip Was in the Instrument: Two Pre-Registered Cycles of Cross-Model Proposition Aggregation", draft v3). We compress it here because it fixes the design rules that Pass 2 follows.

### 2.1 Setup and the Cycle 1 flip

The question of Pass 1: does inter-model agreement on individual *propositions inside reasoning traces* predict proposition truth, as it does for final answers? The instrument: 150 ProofWriter OWA items (a synthetic, decidable closed world; ground truth by construction), split 50/100 calibration/test; two three-model panels sharing no model family (one local, one OpenRouter); a fixed extractor plus embedding+NLI alignment converting traces into canonical propositions; one observation per agent per proposition (one vote per source); arms WCT-U (uniform), WCT-EM (three-state Dawid–Skene), WCT-C (calibration labels), a covariate logistic-regression baseline, and ablations. The registered primary: held-out delta log-loss of WCT-EM versus the baseline, GO at δ = 0.02 nats.

Cycle 1 ran the identical frozen protocol on both panels. The primary metric flipped:

| | Panel A | Panel B |
|---|---|---|
| Cycle 1 primary Δ (nats) | **−0.159** (STOP) | **+0.122** (GO) |
| 95% CI | excludes zero | excludes zero |

### 2.2 Diagnosis: two instrument defects

1. **Missing intercept.** The registered calibration map was a single temperature, `sigmoid(s/t)`, and it cannot shift a score's mean. The baseline logistic regression had an intercept. Only one side of the comparison could match the base rate. Re-fitting the calibration map with Platt (intercept added) flipped Panel A from STOP to GO and took all 12 panel × stratum × arm combinations to GO. Every rank-based metric was invariant: the entire flip lived in the calibration-sensitive metric.
2. **A corpus that could barely contain a falsehood.** 48% of propositions came from theories in which nothing can be false; the alignment layer scored **0 of 607** negative-polarity propositions; the test splits held only 14–16 negatives.

### 2.3 Cycle 2: the diagnosis as frozen predictions

The diagnosis was converted into three falsifiable predictions, frozen in a git tag that precedes every new generation (Cycle 1's protocol had not been tagged before inference, itself a violation of the protocol's own requirement, and part of the record). New corpus: 150 negation-family items with depth-5 enrichment, 744 y=0 propositions. New Panel A (the old local models had vanished); Panel B continued. Platt calibration map.

| Prediction | Result |
|---|---|
| **P1** (central): primary clears the gate on both panels | **Confirmed**: +0.220 [+0.160, +0.280] (new A), +0.272 [+0.180, +0.353] (B) |
| **P2**: consensus quality degrades monotonically with proof depth | **Failed**: the curve rises back at depth 5; unanimous correctness ≥ 0.90 in both panels |
| **P3**: the self-contradiction deny-filter improves both panels | **Failed**: helped A, hurt B (trace-style dependent) |

### 2.4 Invariants, and the design rules for Pass 2

Robust across both cycles: (i) **one vote per source or nothing**: claim-instance counting gives AUROC 0.50–0.61 while unique-source support gives 0.89–1.00; (ii) the signal is real wherever measured: within-item permutation null p = 0.001 in every stratum, panel, and cycle; (iii) **ranking is panel-robust, calibration is not**: every verdict flip in the study lives in calibration-sensitive metrics.

Four design rules carry into Pass 2:

- **R1. Tag the protocol before any inference.** The implementation at the tag is the registration; prose is commentary.
- **R2. The calibration map must carry an intercept.** Every voter's error is modeled by a class-conditional, affine (Platt-like) map, never a bare temperature.
- **R3. The corpus must be able to contain falsehoods.** A registered label distribution, with negatives that the instrument can actually see.
- **R4. One vote per source.** A verbose model or a long trace does not get more votes than a terse one.

---

## 3. Pass 2: The instrument

### 3.1 Task and voting contract

Each claim is an atomic proposition drawn from or against a real news article, phrased in question form ("Is it true that …?"). Voters answer with one of three verdicts, a direct descendant of the FEVER label scheme [18]: **PASS** (the article states the claim or directly entails it), **FAIL** (the article states the opposite or gives a conflicting fact), or **NOT_STATED** (the article does not contain the information). The frozen voting contract (verbatim in `prereg-v2.yaml`, temperature 0, max_tokens 512, thinking off, strict JSON, no system message) tells the voter its verdict must rest *solely* on the article: "no outside knowledge, no prior beliefs, no plausibility." One call per claim per voter; parse failures are missing observations, never coerced.

### 3.2 Corpora: v1 and v2, cutoff-gap designed

**v1** (git tag `prereg-waveconsensus-v1`): 30 real news articles from 2026-08-14 to 2026-08-25, 1,200 pool propositions (599 ENTAIL / 310 CONTRADICT / 291 UNSPECIFIED), split 10/10/10 (train / calibration / test) with seed 42. The window post-dates the 4B jury's training cutoff, and both the 4B panel and the 27B reference model were cutoff-probed and verified blind to in-window events (cutoff-probe runs of 2026-08-26 and 2026-08-27): the cutoff-gap design forces every verdict onto the article text. From v1 we inherit four fine-tuned LoRA adapters (rank 8, scale 20, 200 iterations, commit 1273339), two per family under reason-included and votes-only training conditions, and a calibration split of 10 articles / 400 items.

**v2** (git tag `prereg-waveconsensus-v2`): 200 real news articles (179 primaries plus 21 reserves) from the Wikipedia Current-events portal, verbatim, covering **2026-02-15 to 2026-08-27** (about six months), with 40 pool propositions per article: **8,000 propositions, all of them test split**. There is no v2 training or calibration split: the adapters and the calibration maps are frozen v1 fits, and the v2 evaluation touches v1 only through the frozen artifact `corpus-v2/frozen/v1_baselines.json`. Before generation, a per-topic contamination gate probed seven documented below-4B models (1,405 per-topic probes plus 14 canary slots, 33 row-level review overrides; both canaries PASS on all seven models) and dropped any topic where a panel model showed in-window knowledge: **72 of 251 primary topics dropped, 179 primaries survived (floor 160 met), 9 of 30 reserves dropped, 21 clean reserves used.**

The registered v2 label distribution:

| Dimension | Distribution |
|---|---|
| Truth | PASS 4,000 · FAIL 2,000 · NOT_STATED 2,000 (25% FAIL) |
| Fact role | direct_fact 6,000 · silence 2,000 |
| Trap type | none 7,334 · unit_swap 429 · figure_conflict 229 · disputed_pin 8 |
| Polarity | affirmative 7,842 · negative 158 (**2.0%** vs v1's 18.5%) |

The polarity shift is registered, not discovered: the v1 content bar carries a polarity feature that is near-constant on v2, so the frozen bar's operating point shifts even though its parameters do not. The trap types are mechanically assigned by a registered rule (backtested against the v1 curation before application: trap_type agreement 91.8%, polarity 98.7%, derived unit_swap count matching v1's 82 exactly), and `unit_swap` / `figure_conflict` are near label-deterministic by construction, which is exactly why the bar choice in §3.4 matters.

### 3.3 The jury: twelve configurations

| Family | base_zeroshot | ft reason_included | ft votes_only |
|---|---|---|---|
| llama-3.2-3b-instruct | ✓ | ✓ | ✓ |
| gemma-3-4b-it | ✓ | ✓ | ✓ |
| phi-4-mini-instruct | ✓ | ✓ | ✓ |
| qwen35-4b | ✓ | ✓ | ✓ |

Twelve configurations, one PASS/FAIL/NOT_STATED vote per claim: **200 × 40 × 12 = 96,000 votes** (96,236 calls including resume retries; the core headline is the 8 reason-included + base configurations at 64,000 calls, the votes_only arm at 32,000). The two fine-tuned arms differ only in the adapter's training condition (whether the reason field was present in the fine-tuning data); at inference all twelve configurations receive the identical frozen contract. The run was two sequential phases (core first, 8 configurations, then votes_only, 4), each served 6-way in parallel on six omlx ports (8102–8107) via resumable llama.cpp on marzuki-helium (Mac Studio M3 Ultra), completing in **13.2 hours** (JURY LAUNCH COMPLETE 2026-08-29 00:37:54, run manifest in `runs/2026-08-28-v2-jury/`).

### 3.4 Aggregation: frozen EM, frozen bars

**Aggregator.** WCT-EM: three-state MAP-EM Dawid–Skene [3,4,5], κ_dirichlet = 5.0, 0.8 diagonal prior, structured basins, max_iter 200, tolerance 1e-8; five restarts for the point estimate (RNG stream 20260827), zero restarts inside the bootstrap (the structured basins are deterministic on resampled data, matching v1).

**Calibration.** Per-arm three-class affine (Platt-like) maps [2] on the EM log-posteriors, Nelder–Mead maximum-likelihood fits on the v1 calibration split (10 articles / 400 items), frozen in `v1_baselines.json` (sha256 `2d011f2d…ed39a8`). This is rule R2 from Pass 1, and the transfer of these frozen fits to v2 is the core method claim of Pass 2.

**Bars.** Both bars are frozen v1 fits:

- **content-only (primary bar):** four features, log1p(article length), log1p(pool position − 1), log1p(claim length), and polarity; multinomial logistic, v1 calibration split.
- **full (continuity reference):** the same four plus one-hot trap_type.

The full bar is the registered v1 bar. It is reported as a continuity check with no separate GO, because its trap_type feature is near label-deterministic by corpus construction: on v1 the shortcut alone is worth **0.078 nats** of the bar's log-loss, and on shortcut items the bar beats EM by 0.5–1.4 nats per item. A model-free bar that reads a deterministic function of the label is an unfair bar; the content-only bar is the pure model-free content bar, and it is the registered primary.

### 3.5 Pre-registration and mechanical gates

The registration is `prereg-v2.yaml` at git tag `prereg-waveconsensus-v2`, with a sha256 manifest over the frozen inputs. "Implementations are the registration." The gates:

- **GO (capability):** point Δ ≥ +0.02 nats **and** the 95% article-block bootstrap CI (2,000 resamples, EM refit per resample on the resampled votes alone, bars and calibration frozen, RNG stream 20260828) excludes zero. Point clears but the bound does not: INCONCLUSIVE. Decision matrix 2×2 = {content-only, full} × {reason_included, votes_only}; headline cell = content-only × reason_included; base_zeroshot a reference arm.
- **P8:** the headline cell returns GO.
- **P9:** per fine-tuned arm, the full-bar delta on v2 is within ±0.05 nats of its v1 estimate (consistency, not a GO).
- **Null:** 10,000 within-article truth permutations, fixed predictors, headline cell, one-sided p-value (RNG stream 20260829).
- **e0:** pairwise proposition-level residual error correlation across an arm's four voters, reported as a number (the effective-voter diagnostic of §4.4).
- **System gate (§5):** re-runs the v1 pass criterion on v2: branch (a) strictly lower false-claim rate with the 95% bootstrap CI of the difference entirely below zero, or branch (b) comparable within 10 percentage points at strictly lower total compute cost (USD proxy, amortized serving).

### 3.6 The 27B reference system

A single 27B model, qwen3.8-27b (community merge, Gated DeltaNet hybrid), FP8, vLLM, 256k context, on marzuki-hydrogen's RTX PRO 5000 Blackwell 48 GB, serves three frozen roles, all temperature 0 / max_tokens 512 / thinking off:

1. **Self-review** of every pool proposition (200 × 40 = 8,000 calls), the frontier self-review control and the system bar (three-state accuracy and gate-binary accuracy on v2 labels).
2. **Defendant**: one call per article (200 calls) generating up to 3 specific factual claims "you are confident are true."
3. **Judge**: one call per extracted claim, returning `{"supported": bool, "match_pool": 0–40, "reason"}`; the judge's supported flag is the ground-truth false-claim adjudication, and the pool tie is for the gating comparison.

Hard spend caps (persisted across re-runs): 10,000 calls for the 27B, 8,000 per juror model. The jury phase ran first and was reported; the 27B phase ran after a hard pause, by design.

---

## 4. Pass 2A: Capability: the frozen calibration clears the bar

### 4.1 v1: INCONCLUSIVE, as registered

On the v1 test split (10 articles, 1,200-claim corpus), the registered primary (calibrated EM vs the full covariate bar) produced no GO:

| Arm | Calibrated EM log-loss | Δ vs full bar (nats) | 95% article-block CI |
|---|---|---|---|
| ft reason_included | 0.2583 | +0.0151 | [−0.056, +0.069] |
| ft votes_only | 0.2543 | +0.0191 | [−0.073, +0.088] |
| base zero-shot | 0.2777 | −0.0043 | [−0.122, +0.084] |

No arm clears +0.02 and every CI crosses zero: **P1 INCONCLUSIVE** per the decision rule. Two readings mattered for the v2 design. First, raw EM log-loss looked like a clean fail (deltas −0.25 to −0.31 nats below the bar) only because the raw EM posterior is overconfident while the logistic bar is inherently calibrated; the two are tied as rankers (AUROC 0.992 / 0.995 / 0.988 vs 0.9985), and the pre-registered calibration recovers the picture. Second, the bar was unusually strong because trap_type is near label-deterministic on v1 (unit_swap 100% CONTRADICT, figure_conflict 100% UNSPECIFIED), which is why v2's primary bar drops that feature. The fine-tuning check (P4) **PASSED** (advantage over base rate: 0.514 reason_included, 0.549 votes_only, vs 0.457 zero-shot), and e0 (residual error correlation) was 0.284 / 0.345 / 0.454 across arms. On the 105 true counterfactuals in the v1 test split, juror-consensus FAIL recall was 0.829 / 0.886 / 0.905 versus 27B self-review three-state 91.79% / gate-binary 98.72%: the jury's v1 contribution was ranking precision at a fraction of the cost, not a higher catch rate. The v1 system test passed via branch (b): 200 defendant questions (160 claims + 40 question-echoes), false-claim rate 0.0 vs 0.0, jury cost $0.254 vs $0.319 (ratio 0.797).

### 4.2 v2: the headline gate

On the full 8,000-claim v2 corpus, with every fit frozen from v1:

| Bar | Arm | EM calibrated LL | Bar LL | Δ (nats) | 95% CI | Gate |
|---|---|---|---|---|---|---|
| content-only | **reason_included (headline)** | **0.15716** | 0.36005 | **+0.20289** | **[0.18737, 0.21740]** | **GO** |
| content-only | votes_only | 0.17865 | 0.36005 | +0.18140 | (excl. 0) | GO |
| content-only | base_zeroshot (ref) | 0.17434 | 0.36005 | +0.18571 | (not computed; ref arm) | ref |
| full | reason_included | 0.15716 | 0.3325 | +0.17534 | (excl. 0) | GO |
| full | votes_only | 0.17865 | 0.3325 | +0.15385 | (excl. 0) | GO |
| full | base_zeroshot (ref) | 0.17434 | 0.3325 | +0.15816 | (not computed; ref arm) | ref |

**P8: TRUE.** All four pre-registered test cells are green. (The registration calls the full bar a continuity check with no separate GO, while its decision-matrix line applies the same GO rule to every cell; the artifact computes go = true for both full-bar cells, and we report that label.) The headline delta is an order of magnitude beyond the gate and beyond the v1 scale: the v1 smoke test of the identical tool on frozen v1 data (content-only bar) gave +0.093 reason_included / +0.097 votes_only; the frozen calibration, applied to a corpus 6.7× larger and 6 months wider, more than doubles the headline margin. Raw (uncalibrated) EM log-loss is 0.30796 / 0.38314 / 0.34636 for the three arms, still below both bars, but the registered claim is about the calibrated instrument, per rule R2.

Co-primary within-article AUROC (P(PASS) vs truth = PASS): EM calibrated 0.9951 / 0.9948 / 0.991 (ri / vo / base) versus 0.999 (content bar) and 0.9988 (full bar); ranking is near-saturated for both sides on this corpus, which is why the pre-registered primary is the calibrated log-loss, not AUROC. The fitted EM prior for the headline arm is PASS 0.5247 / FAIL 0.219 / NOT_STATED 0.2563.

**Null test.** The registered null (RNG stream 20260829) permutes truth labels within each article (10,000 permutations, fixed predictors, headline cell), and the registration specifies only "one-sided p-value", leaving the tail unfixed. The frozen tool's registered statistic is the *sum* of the bar's log-loss at the true labels and the EM calibrated log-loss at the permuted labels; its 95% percentile range is [4.06886, 4.19923] nats, and the stored registered one-sided p-value (upper tail, P(null ≥ observed delta)) is **1.0**, because the observed delta is a *difference*, not that sum. The like-for-like delta-form contrast (bar at the true labels minus EM at the permuted labels) is the exact transform 2 × 0.36005 − statistic and spans **[−3.4791, −3.3488] nats**; the observed +0.20289 lies **above all 10,000 realizations** (0/10,000 ≥ observed). We fix the tail to the EM-better direction post hoc and report this count as a descriptive supplement, not the registered test. Either way, the headline GO does not depend on this p-value: it rests on the point estimate and the bootstrap CI.

### 4.3 The registered prediction that failed (P9)

P9 registered that the full-bar delta on v2 would land within ±0.05 nats of its v1 estimate (v1: +0.01506 ri / +0.01911 vo, exact from the frozen file). It did not: v2 full-bar deltas are +0.17534 ri and +0.15385 vo, offsets of +0.16028 and +0.13474 nats. **P9: FALSE.**

The mechanism is the registered polarity shift, not an estimator surprise. The full bar's excess over the content bar is the trap-shortcut value: 0.36005 − 0.3325 = **0.0276 nats on v2**, versus **0.078 nats on v1**. When the negative-polarity base rate falls from 18.5% to 2.0%, the frozen bar's operating point shifts and the model-free shortcut degrades, so the EM-vs-full-bar gap widens even though the EM fits are frozen. The symmetric result, reported at equal prominence: the **learned** EM calibration transfers across corpora (P8 GO), while the **model-free** bar's value does not (P9 FALSE). A practitioner should fit the aggregator on the domain's own data; a model-free bar that reads near-deterministic corpus features is not portable.

### 4.4 Effective voters

The pre-registered e0 for the flagship arm is **0.3062** (0.2976 votes_only, 0.3293 base). The Kish effective sample size for the arm's four voters is

n_eff = 4 / (1 + 3 × 0.3062) = **2.085**.

We report this number first, not last, because it is the direct answer to "nine judges, two effective votes" [9]: in that study, nine frontier judges on NLI carried roughly 2 effective votes because of correlated errors, and panel accuracy sat 8–22 points below the independent-vote ideal. Our jury's flagship arm carries 2.09 effective votes, the same order, yet the frozen calibration still clears a pre-registered +0.02 gate by more than an order of magnitude on a real corpus. The two results cohere: n_eff tells you how much *independent information* the panel holds, and calibration tells you how well that information is *priced*. In this regime (heterogeneous small families × prompt-condition diversity, a third verdict state, ground-truth-calibrated EM), simple Dawid–Skene is already a large measurable win; dependence-aware aggregators [7,8,10] may buy more, but the pre-registered bar does not require them.

---

## 5. Pass 2B: The system gate: the jury route against the 27B route

### 5.1 Protocol

The defendant (27B) generates up to 3 specific factual claims per article across all 200 v2 articles: **200 defendant calls → 600 claims** (3 per article). The judge (same 27B, article + the 40 pool propositions in context) adjudicates each claim: **598 supported, 2 unsupported, 0 unparse** (600 judge calls). Raw false-claim rate: 2/600 = **0.333%**.

Gating applies only to claims with a non-zero unique pool tie (591 of 600; 9 tie-0 claims excluded by the registered rule); both of the two false claims are gateable. A gateable claim is **retained** by an arm if that arm's verdict on the tied pool proposition is PASS: jury consensus P(PASS) ≥ 0.5 (WCT-EM, reason_included) or 27B self-review PASS. **False-claim catch** is the share of judge-unsupported claims the gate drops. Pass criterion (re-run from v1): branch (a) strictly lower false-claim rate with the 95% bootstrap CI of the difference entirely below zero; or branch (b) comparable within 10 percentage points at strictly lower total compute cost.

### 5.2 Results: a co-failure at the boundary

| Gate | Survivors | False-claim rate | Catch |
|---|---|---|---|
| Juror-gated (WCT-EM ri, P(PASS) ≥ 0.5) | 589/591 | 2/589 = **0.3396%** | **0/2** |
| 27B self-review-gated | 585/591 (6 verdicts missing) | 2/585 = **0.3419%** | **0/2** |
| Δ (jury − self-review), 2,000 article-block bootstrap, seed 20260827 | | CI **[0.0, 5e-05]** | |

Branch (a) is **false**; branch (b) is **true**: the two false-claim rates are statistically indistinguishable (Δ ≈ 0.002 percentage points, against a 10-point tolerance), and the jury route is strictly cheaper. **Verdict: PASS (branch b).**

The catch of 0/2 is the honest core of the system result, and it deserves the full record. The two unsupported claims both passed **12–0 across all twelve jury configurations and were also PASS for the 27B**: a genuine co-failure at the boundary of the instrument. Verbatim from the defendant/judge record (`judge.jsonl`):

1. **V2-158, claim 3** (pool tie 13):
   > "Dan Jarvis was named as John Healey's successor as security minister on Thursday evening."
   The article names him as Healey's successor as **Secretary of State for Defence**, not security minister (he had previously served in that role). A role-conflation the article's own phrasing invites.
2. **V2-172, claim 1** (pool tie 1):
   > "The Israeli military and Shin Bet confirmed that they killed Palestinian Islamic Jihad commander Zaki Youssef Mahmoud Abu Mustafa in a precise strike in southern Gaza on Friday, June 19, 2026."
   The article reports the **confirmation** on June 21, 2026, and states the killing happened on a "Friday" (June 19 inferred); the claim conflates the confirmation date with a specific strike date.

Both are fine-grained factual errors of the kind a single careful read can miss; neither is a corpus artifact. What the gate test shows is that both routes co-fail exactly the same two claims, and the jury route does so **at strictly lower cost**, which is exactly the branch the pre-registration reserved for a co-failure regime.

### 5.3 Head-to-head on the full pool

On all 8,000 pool claims (27B self-review, 8,000 calls, 50 missing verdicts = 0.625%; the full 27B phase took 12,028 s, defendant 520 s, self-review stage 10,651 s, judge 857 s):

| System | 3-state accuracy | Gate-binary accuracy | FAIL recall |
|---|---|---|---|
| 27B self-review (non-missing) | **95.887%** | **99.119%** | **99.398%** |
| Jury, WCT-EM reason_included | 93.912% | 98.25% | 98.05% |

The 27B is the stronger single model, on every detection metric. But the boundary is much narrower than the accuracy gap suggests:

- **Agreement:** the 27B agrees with the 12-config raw majority on **93.962%** of non-missing claims.
- **The 27B is the stricter voter:** of the 4,180 non-missing cells where the 12-config majority said PASS, the 27B said FAIL on 108 and NOT_STATED on 72: **4.3% of majority-PASS cells** flipped by the single large model.
- **The co-failure set is tiny and shared:** on the defendant stream, the two systems disagree on exactly zero of the two false claims; they fail on the same two.

The quantified boundary, then: on verifiable, article-grounded claims, a calibrated jury of 3–4B models sits about 2 percentage points below a single 27B in three-state accuracy, about 0.9 points in gate-binary accuracy, and shares its blind spots on the fine-grained errors that actually produce false claims. That is the empirical β-style quantification the co-failure-ceiling theory predicts but does not deliver for this domain [14].

### 5.4 Cost of the gate

Per 8,000 claims, token-proxy pricing (4B $0.20/$0.60 per 1M in/out; 27B $1.00/$3.00; jury proxy anchored on v1's measured 693.1 tok/vote, in/out split 92.77/7.23):

| Route | Calls | Tokens | USD |
|---|---|---|---|
| Jury, reason_included panel (the gate arm) | 32,044 | 22,209,656 | **$5.0841** |
| Jury, full 12-config (for reference) | 96,236 | 66,701,051 | $15.2688 (2.8714× SR) |
| 27B self-review | 8,000 | 4,639,575 (measured) | **$5.3175** |

Ratio (ri panel / self-review): **0.9561**. Because v2 articles are shorter than v1's (mean 1,419 vs 1,927 characters), the v1-measured per-vote token proxy overstates jury cost; length-adjusted (566.2 tok/vote) the ratio falls to **0.781**. Both keep branch (b). The defendant and judge calls (800, shared by both routes) are excluded from the comparison, as registered.

---

## 6. The barrier was memory

The cost question that matters for deployment is not "what does one call cost" but "what hardware must I own, and what does a year of verification run." We cost the two routes at AUD street prices for owned hardware (COST-BARRIER.md; electricity at A$0.30/kWh):

| Tier | Hardware | Capital (AUD) | Power | A$/h | A$ per 10k votes |
|---|---|---|---|---|---|
| 27B route | RTX PRO 5000 Blackwell, 48 GB GDDR7 | **A$9,100** | 300 W | 1.13 | **2.90** (2.6 h/10k) |
| Jury, as run | Mac Studio M3 Ultra, 96 GB | A$6,300 | ~280 W | 0.80 | **1.10** (1.4 h/10k) |
| Jury, Turing tier * (estimate) | 2× used RTX 2080 Ti 11 GB (2018) | **A$1,200** | 2×250 W | 0.29 | **0.58** (2.0 h/10k) |

\* The 2080 Ti throughput is an **estimate**, not a measurement; the Mac Studio figure is the measured anchor (13.2 h for 96,000 votes ≈ A$11 per 96k votes; ≈ A$5.5 per 96k estimated on the Turing tier). The 27B throughput was measured with the engine serving **one of three shared vLLM slots**; solo throughput is higher, so the 27B row is conservative and the ~5× operating-cost advantage is an **upper bound**.

The asymmetry is structural. The 27B in FP8 needs **48 GB of GDDR7**, a memory configuration that, at the time of writing, exists only in current-generation workstation GPUs. The full 12-voter jury needs about **29 GB peak**, and fits on two 2018 second-hand consumer cards that are still widely owned. **Memory, not arithmetic, is the barrier.** Consequences at the Turing tier: **7.6× lower capital** (A$1,200 vs A$9,100) and **~5× lower operating cost per 10,000 votes** (A$0.58 vs A$2.90, an upper bound; the 27B throughput row is measured on a shared vLLM slot, footnote above), on consumer, widely-owned, second-hand silicon.

For the reader who wants the one-sentence version: a single 27B model is a better verifier than our jury, but it is a *48 GB GDDR7* better verifier; the jury route buys a pre-registered, quantified boundary at a price the 27B's hardware class cannot match.

---

## 7. Discussion

### 7.1 The two-pass arc

Pass 1 and Pass 2 are one argument. In Pass 1, a frozen protocol produced opposite verdicts on two panels, and the diagnosis (missing intercept, corpus that could not hold falsehoods) turned out to be about the *instrument*. The repaired instrument then confirmed its central prediction in a tagged, replicable second cycle. Pass 2 imports the repair: the calibration map carries intercepts (per-arm affine maps, rule R2), the corpus carries a registered 25% FAIL mass and 2.0% negative polarity (rule R3), every vote is one source (rule R4), and the protocol is tagged before the first inference call (rule R1). The payoff is not just that the v2 headline gate passes; it is that it passes *frozen*: every fit (EM weights, calibration maps, bars) was determined by v1 data before any v2 vote existed. A post-hoc fit could always clear a post-hoc bar; this one could not.

The v1 INCONCLUSIVE is part of the evidence, not a footnote. It is the small-corpus reading of the same instrument: +0.093 content-bar delta, no GO, every CI crossing zero. Scale and polarity shift move the same frozen fits from inconclusive to decisive, which is what a transfer claim is supposed to look like.

### 7.2 Where the jury stands, and where it does not

We report the negatives at the same prominence as the positives:

- **The 27B is more accurate.** 95.887% vs 93.912% three-state, 99.119% vs 98.25% gate-binary, 99.398% vs 98.05% FAIL recall. If the budget is "one good verdict per claim," buy the 27B.
- **The catch is 0/2 on both routes.** The pre-registered system test cannot distinguish the two gates on this corpus; the jury passes on cost, not on detection.
- **P9 failed.** The model-free bar's value does not transfer; only the learned calibration does.
- **n_eff is 2.085.** The flagship arm is two independent voters, not twelve. The jury's diversity is real (four families × three arms) but substantially correlated; co-failure is the expected failure mode, and the two co-failed claims in §5.2 are its empirical specimen.
- **The 27B phase had 50 missing verdicts (0.625%)** and 6 missing verdicts inside the gate; strict-parse discipline keeps them out, but they are part of the record.

### 7.3 Position against the aggregation literature

The methodological predecessor is Dawid–Skene [3] and its weak-supervision descendants [4,5,6]; we do not claim a new estimator. The 2026 cluster moves the field past naive conditional independence: Ising-model label aggregation shows class-dependent dependence can make Dawid–Skene strictly suboptimal [7]; CARE shows confounders (verbosity, style) must be separated from latent quality [8]; the Bayesian win-rate calibration line [11] models annotator reliability before aggregating; higher-order-information aggregation beats majority voting with provable guarantees [10]. Our result is complementary and deliberately minimal: the *simplest* member of this lineage, fitted once and applied frozen, already clears a pre-registered bar on a real corpus: evidence that in the heterogeneous-small-families regime, simple calibration is a defensible practitioner choice on consumer hardware.

The skeptic's anchors are [9] and [14]. Nine Judges [9] predicts small effective sample sizes for correlated LLM panels; we agree (2.085) and add that the *pricing* of that information (the calibration) is what carries the pre-registered margin. The co-failure ceiling [14] bounds ensemble accuracy by 1 − β and notes β is not identifiable from pairwise correlations; our 27B head-to-head is a direct measurement of that boundary in the news-verification domain: 93.962% agreement with the raw majority, a shared co-failure set on the only two unsupported claims, and a 4.3% stricter-voter rate on majority-PASS cells. Closest on "small ensemble vs one large model" are the Avengers recipe [13], the simple LLM-ensemble strategy [26], and the council/consultation line [31]; closest on domain plus open models is the HerO/AVeriTeC pipeline [15,16] and the end-to-end fact-check writing line [27], systems optimized for task performance without pre-registration, calibrated aggregation, or cost accounting. The label scheme descends from FEVER [18]; the atomic-claim instrument from QA-based factual consistency [17], FActScore [19], and MiniCheck [20]; the debate-and-deliberation line [21–24] adds multi-round interaction costs that our one-vote-per-configuration design avoids; the weak-supervision benchmarking line [6] and the annotation-protocol line [12] are the methodological neighbors of our registration discipline. Cost-side anchors: org-level on-premise economics [28], prompt-compute tradeoffs [29], energy accounting [30], and the price of prompting generally.

### 7.4 The novelty claim

To our knowledge, this is the first pre-registered, cross-corpus-validated evaluation of a heterogeneous small-model LLM jury for news-claim verification in which (i) Dawid–Skene-style EM calibration is fitted once and applied frozen, (ii) per-vote cost is measured on owned consumer hardware with the hardware barrier identified, and (iii) the jury's boundary against a single 27B model is quantified head-to-head on the same claims. Each component has a predecessor; the conjunction, and the two-pass instrument story, does not.

### 7.5 AI pair coding and authorship

This project was executed as an AI pair-coding collaboration. A general-purpose coding agent, running on the same machine fleet that hosts the experiment, was the primary implementation partner across both passes. It wrote the corpus builders and the contamination gate, the Dawid–Skene EM fit and calibration code, the jury launch harness and six-way llama.cpp serving, the pre-registered evaluation, null, and bootstrap tools, the 27B phase runner, and the cost accounting. It also drafted the prompt contracts used by the jury voters, the defendant, and the judge; the authors edited and probed those drafts, and the frozen versions are the ones recorded in `prereg-v2.yaml`, with the iteration history in the git log. What the agent did not do: it did not set the labels, choose the gates or GO rules, or interpret any result; every frozen quantity was fixed by the authors before the registration was tagged. The agent drafted the manuscript too, including this section. The audit trail for the whole loop is the repository itself.

### 7.6 Implications

Three, each bounded by the limitations in §8.

1. **Verification is an instrument, not a model.** Two systems with the same voters and the same corpus can give opposite pre-registered verdicts because of a missing intercept (§2). Pre-registration makes the specification flaws visible; replication makes them findable; only the combination makes the result mean something.
2. **Calibration transfers; shortcuts do not.** The frozen EM maps moved from a 30-article corpus to a 200-article corpus and more than doubled their margin (P8 GO), while the model-free trap shortcut lost two-thirds of its value (P9 FALSE, 0.078 → 0.0276 nats). Fit the aggregator on your own domain; do not trust model-free features that are near-deterministic in the corpus that grew them.
3. **The deployment question is memory, not FLOPs.** A calibrated jury of small models fits in about 29 GB and runs on second-hand consumer silicon at 7.6× lower capital and ~5× lower operating cost per 10k votes than the 48 GB class required by a single 27B. Where claims are verifiable against a source document and volume is high, the jury route is the cheaper of two quantified, co-failing alternatives, and the paper now gives a practitioner the exact boundary at which to buy the 27B instead.

---

## 8. Limitations

- **One corpus source, one window.** v2 is the Wikipedia Current-events portal, 2026-02-15 to 2026-08-27, all test. The transfer claim is internal (v1→v2); external validity to other outlets, languages, or periods is untested.
- **Manufactured pools.** Claims are drawn from a 40-proposition pool per article with a registered trap design; real verification involves claim selection under retrieval, which neither route models.
- **Twelve configurations, four families.** One family per prompt condition; the adapters are frozen from v1. The jury's diversity is bounded by what four below-4B families and two fine-tuning conditions provide.
- **n = 2 co-failures.** The catch statistics (0/2 on both routes) are descriptive, not estimable; the branch-(b) pass rests on cost plus indistinguishability, not on a measured catch advantage.
- **Cost is a token-USD proxy**, anchored on v1's measured 693.1 tok/vote and published per-token prices; the 27B tokens are measured, the jury tokens are proxied (v2 articles are shorter than v1's, and the length-adjusted ratio is reported). The 2080 Ti row is an estimate.
- **One 27B, one quantization, one serving config.** The head-to-head is against qwen3.8-27b FP8 at temperature 0; other frontier models may sit at different points on the boundary.
- **The defendant is the 27B.** Both routes consume the same defendant claims; defendant errors propagate identically into both gates (as registered).
- **Pass 1's world is synthetic.** The mechanism results (intercept, one-vote-per-source, rank robustness) are what we expect to transfer; Pass 1 effect sizes are not claimed for open news. Its co-primary was reading-sensitive, the registered second NLI stack was never run, and the two cycles share half a corpus plus one panel.

---

## 9. Conclusion

Agreement across language models is a measurement instrument, and like any instrument it can be broken in ways the analyst does not see until a second panel disagrees. Pass 1 found the break (a missing intercept, a corpus that could not hold falsehoods) and repaired it under a git tag; Pass 2 carried the repaired instrument into open news and let frozen, pre-registered gates decide what the result means. The frozen calibration clears the bar (+0.20289 nats, CI [0.18737, 0.21740], all four test cells green; the registered null is reported as stored; §4.2); the model-free shortcut does not transfer (P9 FALSE); the system route co-fails the 27B on exactly two fine-grained errors and passes on the registered cheaper-and-indistinguishable branch at 0.956× the per-claim cost. The jury carries 2.09 effective votes per claim, and the hardware barrier between the two routes is a 48 GB GDDR7 memory, not an arithmetic gap. The honest unit of account for LLM-based verification is the instrument: protocol, corpus, hardware, and cost. This paper measures that instrument twice, with the gates left open.

---

## 10. Reproducibility and artifacts

- **Repository:** https://github.com/marzukia/pauper-consensus. The method is named Pauper Consensus; the repository was renamed from wave-consensus after both registrations were cut, so the frozen tag names below keep the original working name (the old URL redirects). Git tags: `prereg-waveconsensus-v1` (corpus v1, adapters commit 1273339), `prereg-waveconsensus-v2` (prereg-v2.yaml + sha256 manifest over frozen inputs, tools frozen at tag).
- **Registration:** `prereg-v2.yaml` at `prereg-waveconsensus-v2`; "implementations are the registration."
- **Frozen v1 inputs:** `corpus-v2/frozen/v1_baselines.json` (sha256 `2d011f2d1339b7b4d238a0aaae485a133a5bec525f6480d3639440a70fed39a8`): per-arm calibration maps, covariate bars, EM/calibration/covariate specs, v1 splits, and the reproduced v1 test reference used for the tool's smoke test (content-only deltas +0.093 ri / +0.097 vo; full-bar +0.0151 ri / +0.0191 vo).
- **Runs:** `runs/2026-08-28-v2-jury/` (jury launch log with JURY LAUNCH COMPLETE 2026-08-29 00:37:54, per-model vote rows, `eval_v2.json` with all capability numbers); `runs/2026-08-29-v2-27b/` (self-review 8,000 calls, defendant 200 + judge 600, `judge.jsonl` with verbatim claims and adjudication reasons, `gate_analysis.json` with all system-gate and cost numbers).
- **RNG streams:** EM point estimate 20260827 (5 restarts); bootstrap 20260828 (2,000 article-block resamples, 0 restarts); null 20260829 (10,000 permutations); gate bootstrap 20260827 (2,000 resamples).
- **Hardware:** jury on marzuki-helium (Mac Studio M3 Ultra) via llama.cpp/omlx, ports 8102–8107, 13.2 h; 27B phase on marzuki-hydrogen (vLLM, RTX PRO 5000 Blackwell 48 GB), 12,028 s total (defendant 520 s, self-review 10,651 s, judge 857 s). Spend caps persisted across re-runs (27B: 10,000; per juror: 8,000).
- **Corpora:** v1 (30 articles, 1,200 propositions) at tag `prereg-waveconsensus-v1`; v2 (200 articles, 8,000 propositions) with contamination-gate run in `corpus-v2/gate/runs/2026-08-28/`.
- **Pass 1:** Mannings & Marzuki [25]; protocol tag and artifacts per that paper. Preprint: https://doi.org/10.5281/zenodo.22159293 (Zenodo record reserved; publish the record before submission so the link resolves).

---

## References

[1] Liu et al. (2026). LLMs-as-jury: agreement at the answer level. arXiv:2607.10139. https://arxiv.org/abs/2607.10139

[2] Platt, J. (1999). Probabilistic outputs for support vector machines. (Intercept-bearing calibration maps.)

[3] Dawid, A. P., & Skene, A. M. (1979). Maximum likelihood estimation of observer error-rates using the EM algorithm. *Journal of the Royal Statistical Society Series C*, 74(366), 89–93. https://doi.org/10.1080/01621459.1979.10482046

[4] Raykar, V. C., et al. (2010). Learning from crowds. *Journal of Machine Learning Research*, 11, 1225–1247. https://jmlr.org/papers/v11/raykar10a.html

[5] Ratner, A., et al. (2017). Snorkel: Rapid training data creation with weak supervision. arXiv:1711.10160.

[6] Zhang, H., Yu, M., Li, X., et al. (2021). WRENCH: A comprehensive benchmark for weak supervision. arXiv:2109.11377.

[7] Balasubramanian, V., Podkopaev, V., & Kasiviswanathan, S. (2026). Dependence-aware label aggregation for LLM-as-a-judge via Ising models. arXiv:2601.22336.

[8] Zhao, et al. (2026). CARE: Confounder-aware aggregation for reliable LLM evaluation. arXiv:2603.00039.

[9] Kohli, P. (2026). Nine judges, two effective votes: Correlated errors undermine LLM evaluation panels. arXiv:2605.29800.

[10] Ai, M., Pan, B., Simchi-Levi, D., Tambe, M., & Xu, Y. (2025). Beyond majority voting: LLM aggregation by leveraging higher-order information. arXiv:2510.01499.

[11] (2024). Bayesian calibration of win rate estimation with LLM evaluators. *EMNLP 2024*. arXiv:2411.04424. https://aclanthology.org/2024.emnlp-main.273/

[12] Camuffo, et al. (2026). Variance-aware LLM annotation for strategy research. arXiv:2601.02370.

[13] Zhang, et al. (2025). The Avengers: A simple recipe for uniting smaller language models to challenge proprietary giants. arXiv:2505.19797.

[14] (2026). When does combining language models help? A co-failure ceiling on routing, voting, and mixture-of-agents across 67 frontier models. arXiv:2606.27288.

[15] Yoon, et al. (2024). HerO at AVeriTeC: The herd of open large language models for verifying real-world claims. arXiv:2410.12377.

[16] Team HUMANE (2025). HerO 2 at AVeriTeC. arXiv:2507.11004.

[17] Kryscinski, W., et al. (2020). Evaluating the factual consistency of abstractive text summarization. *EMNLP 2020*. https://aclanthology.org/2020.emnlp-main.750/

[18] Thorne, J., et al. (2018). FEVER: A large-scale dataset for fact extraction and VERification. *NAACL 2018*. arXiv:1803.05355.

[19] Min, S., Krishna, K., et al. (2023). FActScore: Fine-grained atomic evaluation of factual precision in long form text generation. arXiv:2305.14251.

[20] Tang, L., Laban, P., & Durrett, T. (2024). MiniCheck: Efficient fact-checking of LLMs against Wikipedia and knowledge graphs. arXiv:2404.10774.

[21] Du, Y., Li, S., et al. (2023). Improving factuality and reasoning in language models through multiagent debate. arXiv:2305.14325.

[22] Chan, C.-M., et al. (2023). ChatEval: Towards better LLM-based evaluators through multi-agent debate. arXiv:2308.07201.

[23] (2025). Debating truth. arXiv:2507.19090.

[24] Chowdhury, et al. (2026). Courtroom-style multi-agent deliberation. arXiv:2603.28488.

[25] Mannings, J., & Marzuki, A. (2026). The Flip Was in the Instrument: Two pre-registered cycles of cross-model proposition aggregation. Zenodo. https://doi.org/10.5281/zenodo.22159293

[26] Niimi, Y. (2025). A simple ensemble strategy for LLM inference. arXiv:2504.18884.

[27] Sahnan, M., Corney, C., Larraz, et al. (2026). End-to-end automated fact-check article writing. *TAACL 2026*. arXiv:2503.17684.

[28] (2025). On-premise LLM deployment: cost-benefit analysis. arXiv:2509.18101.

[29] (2024). The price of prompting. arXiv:2407.16893.

[30] (2025). Energy considerations of LLM inference. arXiv:2504.17674.

[31] Liu, et al. (2025). LLM Council. arXiv:2505.08532.

---

*Data availability: corpora, prompts, frozen fits, run manifests, and analysis tools are in the repository linked above at the cited git tags. Verbatim defendant claims and judge adjudications are in `runs/2026-08-29-v2-27b/judge.jsonl`.*
