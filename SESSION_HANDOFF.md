# Session handoff — waveconv, 2026-08-28 to 2026-08-30

Written so this session can be compacted without losing state. Everything here is
either committed or reproducible from committed artifacts.

## Where the work stands

| slice | title | status | commit |
| --- | --- | --- | --- |
| 1 | Corrected instrument and zero-cost re-analysis | done | `e63f946` |
| 2 | Paper corrections from slice 1's findings | done | `87bfb7f` |
| 3 | Five-family availability, measured | done | `32fead0`, `1bf61ba` |
| 4 | Cycle-3 registration | **in progress** — `REQUEST.md` written, decisions recorded, no `PLAN.md` yet | — |

Workstream `20260828-181135-0d060fc4`; slice-4 run `20260830-221830-30689369`.
Branch `e1-results-and-paper`. **Four commits are local and UNPUSHED** — the harness
push-guard blocks the agent, so a human must run:

    cd ~/dev/waveconv && git push origin e1-results-and-paper

`origin` has two push URLs (AWS CodeCommit + the private mirror
`github.com/jwmannings/waveconv1.git`), so one push goes to both.

## What was found (the science)

Three defects in the frozen instrument, all corrected in `wct3/` + `exp3/` without
touching `exp/`, `wct/`, `m0/` (tag `prereg-v2-2026-08-16` is byte-clean at HEAD):

- **D1 — a registered arm was never implemented.** `single_best_calibration_selected`
  (`prereg.yaml:166`, `plan.md:488`) was registered and never run in either cycle. Built
  and measured: the panel beats the source its own calibration split selects by only
  **+0.0448 to +0.0887 nats** on three of four panel-cycles, and **inconclusively** on
  c2_panelB (+0.0329 [-0.0109, +0.0703]). So no REGISTERED result in either cycle
  distinguishes cross-model agreement from one good model.
- **D2 — the M6 ablation measured the wrong thing.** `align_anchored` collapses to one
  observation per (agent, proposition) before `exp/e1.py:76-78` counts, so `n_claims`
  equals `n_emitting` identically: the "claim-instance" arm is capped and UNSIGNED.
  Separating capping from polarity (raw AUROC): uncapped signed beats capped on three of
  four panels and is 0.0036 lower on the fourth, while no unsigned arm exceeds 0.6063.
  **The effect is polarity, not capping.** Draft v3's arithmetic was right; its label was
  wrong.
- **D3 — cycle 2 discarded its own audit.** `exp/e1_v2.py:189` binds the alignment audit
  and never uses it. Restored for all four panel-cycles; the cycle-2 mapper scores 0.9721
  against cycle 1's 0.9724, so the depth-5 enrichment did not degrade it.

`paper.md` was corrected in nine marked passages (slice 2), including a dated correction
notice, a retitled §6.1, and a §9 that closes on the single-source finding.

## Availability, measured (slice 3)

Six families reachable, margin **+1** → **M=5 registrable**. Total probe spend $0.0014.

| family | working id | tier |
| --- | --- | --- |
| google | `google/gemma-4-26b-a4b-it` | paid |
| nvidia | `nvidia/nemotron-3-super-120b-a12b` | paid (`:free` 429s) |
| openai | `openai/gpt-oss-20b` | paid (`:free` withdrawn, 404) |
| poolside | `poolside/laguna-xs-2.1` | paid (`:free` 429s) |
| qwen | `qwen3.8-27b` local `:8083` | pinned; fallback `qwen/qwen3.8-27b` |
| zhipu | `zai-org/GLM-5.2` | paid (Hoonify) |

- **Neither cycle-2 panel is reproducible as registered.** Panel A broken by `laguna`,
  panel B by `gptoss` and `gemma`. `prereg_v2`'s rule is exact-pinned-id-or-drop.
- `:free` is a TIER SUFFIX, not part of the model id. That mistake made an early reading
  say "gpt-oss is gone"; the paid id answers fine.
- Only the local endpoint had a registered expected echo, so identity was unverifiable for
  the rest. Fixed: expected identity now defaults to the requested id.

## Decisions recorded (all in `DECISIONS.md`)

1. M=5 registrable only WITH MARGIN; exactly five ⇒ M=3/M=4 with a declared stretch arm.
2. Paid OpenRouter tier authorised; twins reported separately, never counted as pinned.
3. Cycle 3 pins ALL SIX families; nested M=3 ⊂ M=4 ⊂ M=5; sixth family is the margin.
4. qwen pinned LOCAL with `qwen/qwen3.8-27b` as a declared fallback.
5. **Corpus: all 2,353 local items** (1,405 depth-3 + 948 depth-5). Supersedes the earlier
   "reuse cycle 2's 150" decision.

## The power calculation that drove the corpus decision

From slice 1's measured margins (SD per item 0.16–0.25), for 80% power:

| to detect | items |
| --- | --- |
| the margin at 0.045 nats | 245 |
| a 0.03-nat M=3→M=5 increment | 1,103 |
| a 0.02-nat increment | 2,481 |

2,353 items powers roughly a 0.02-nat increment. Cycle 2's 150 could not power the
dose-response at all.

## The binding constraint: CPU NLI

**Measured on this box: 30 NLI pairs/sec** (DeBERTa-v3-base, 32 threads).

| corpus | NLI pairs | CPU time |
| --- | --- | --- |
| 2,353 × 6 (registered) | 12.4M | **~114 h / 4.8 days** |
| 10,000 × 6 | 52.5M | ~20 days |

Generation: 14,118 calls, ~$29. **Two GPUs are present** (RTX 3090 24GB, RTX 3080 Ti
12GB) but this venv's torch is `2.13.0+cpu`, so they are unusable. The protocol's
"No GPU" constraint is STALE, like the RAM table `GOTCHAS.md` already flags. A CUDA torch
in a SEPARATE venv would cut the run to ~a day, but would change the numerical environment
that the frozen-reproduction checks depend on — decide deliberately.

## What slice 4 still needs

- `PLAN.md` for slice 4 (not yet written), then plan-QA, build, gate, spec, commit.
- `prereg_v3.yaml`: primary = panel vs calibration-selected best single source; nested
  subsets; δ derived from the margins above and frozen; power stated honestly.
- An expected echo pinned per panel member (only qwen has one today).
- Paid tiers priced for 14,118 calls with a hard per-panel cap.
- The analysis driver committed and git-tagged BEFORE any cycle-3 generation exists.
- Registration precedes generation. "Getting the CPU pumping" cannot start before the tag.

## Working practices this session established

- **Verify a gate by its EXIT CODE**, never by grepping its output. Reporting a pass from a
  grep was wrong once here.
- **Verify a review actually ran**: compare the verdict's mtime against the prompt's and
  check `state.json`'s round count. Cached verdicts were reported as fresh several times.
- **Every check needs a planted failure** before it is trusted. Seven vacuous-pass bugs were
  found this way, including three where the fix reintroduced the fault.
- **Never `t.replace(old, new)` without `assert t.count(old) == 1`.** An empty slice from a
  reversed `t.index()` pair inserted a paragraph between every character and produced a
  9.3MB `PLAN.md`.
- Gate tests that invoke the gate must be guarded against recursion (`SLICE3_GATE_RUNNING`).
