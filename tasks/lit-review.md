---
title: Lit review — wave-consensus novelty check
description: >
  One-off literature review requested by Andryo (2026-08-29).
  Do not move or delete without telling him.
---

# Goal

Establish the novelty / novel angle of the wave-consensus v2 study for an
arXiv submission (current bar). Stretch goal: a peer-reviewed journal.
Produce a defensible one-sentence novelty claim and a venue recommendation.

# What we did (plain English, for framing searches)

- Corpus: 200 news articles (Jul–Aug 2026). For each, 40 candidate claims
  (propositions) about its content, each labeled true/false by construction
  (some deliberately contradicted by the article). 8,000 labeled claims.
- Jury: 12 configurations of 3–4B LLMs (Qwen3.5-4B, Phi-4-mini, Gemma-3-4B,
  Llama-3.2-3B × three prompt conditions: base / reason-included /
  votes-only). Each config votes once (PASS/FAIL/NOT_STATED) on every claim
  against the article text = 96,000 votes. Run with llama.cpp on a Mac
  Studio M3 Ultra, 13.2 h wall.
- Aggregation: per-config EM calibration (weights + per-class affine maps)
  turns the 12 votes into a probability the claim is true. Evaluated
  against a frozen baseline fitted on a previous (v1) corpus.
- Results (pre-registered GO gate): +0.20 nats log-loss improvement vs the
  frozen baseline, CI [0.187, 0.217], all four test cells green. v1 (smaller
  jury) was +0.09.
- New 27B head-to-head (in progress at writing): single Qwen 27B (FP8, RTX
  PRO 5000 Blackwell 48 GB) answers the same 8,000 claims, plus generates 3
  claims per article that a 27B judge then verifies. At 50%: 94.1% exact
  label agreement with jury consensus; jury-FAIL precision vs 27B 96.9%;
  27B adds ~3% extra catches on jury-PASS cells.
- Cost table (measured): 96k votes ≈ A$11 on the owned Mac (est ~A$5.5 on
  2× used 2018 2080 Ti) vs ~A$28 on the A$9,100 48 GB card. Barrier claim:
  12 voters need ~29 GB VRAM total vs 48 GB GDDR7 for the 27B.
- Protocol: full pre-registration (frozen YAML + sha256 manifest + git tag),
  mechanical decision gates, per-item spend caps.

# Questions to answer

1. **Closest prior work** (8–12 entries, arXiv IDs + links), search hard
   across: LLM ensembles for fact/claim verification; multi-LLM "jury" or
   majority-vote verification; self-consistency (Wang et al. 2022) and
   variants; LLM weak supervision / label aggregation (Snorkel GenIE 2022,
   Dawid-Skene lineage); calibration of LLM or annotator ensembles (EM
   per-annotator quality); news-domain fact-verification pipelines (FEVER
   2018, FactCC 2020, successors 2023–2026); small-model-ensemble vs
   large-model cost/quality Pareto (2024–2026); multi-agent debate for
   factuality.
2. For each: 1–3 sentence summary + **how it differs from us** (what we have
   that they don't, and what they have that we don't).
3. **Verdict:** is this novel? The defensible one-sentence novelty claim.
   The closest work a reviewer would cite first. "We reinvented X" risks
   (e.g. Dawid-Skene 1979, Snorkel 2016) and how to position against them.
4. **Venue fit:** arXiv category (cs.CL vs cs.CY vs cs.AI) and 2–3 stretch
   journals suited to a pre-registered computational fact-checking + cost
   study (consider: JASIST, PeerJ Computer Science, Digital Scholarship in
   the Humanities, New Media & Society, Journal of Computational Social
   Science, EMNLP Findings if the method angle is strong). For each: fit +
   why.
5. **Angle:** recommended title + 3-sentence abstract framing that
   maximizes the novelty (likely axis: calibrated multi-model jury on
   consumer hardware, pre-registered, cost-quantified, with a 27B
   head-to-head).

# Method

- Use tavily_tavily_search / tavily_tavily_research heavily; target arXiv,
  ACL Anthology, Google Scholar snippets. Search 2023–2026 plus a few old
   anchors (Dawid-Skene 1979, Snorkel 2016, FEVER 2018, self-consistency
   2022).
- Every claim about prior work gets a link (arXiv abs URL or anthology).
- Double-check that a paper actually does what its abstract implies before
  calling it "closest" (fetch the abstract page if unsure).

# Output

- Full review → `notes/lit-review.md` in the repo (create `notes/`).
- Post a ~20-line summary in your own thread: top-5 closest works with
  links, the one-sentence novelty verdict, recommended arXiv category + one
  stretch journal.
