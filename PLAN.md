# Plan: Slice 4 — cycle-3 registration

Run `20260830-221830-30689369`, workstream `20260828-181135-0d060fc4` slice 4 of 4.
Acceptance ids B1–B11 are `REQUEST.md` "Acceptance criteria" (NOT `MASTER_v3.md`'s B1–B9;
round 1 of the plan relay caught that the earlier draft used the wrong numbering).

Revised after plan-verdict round 1 (13 blockers, 1 advisory). Dispositions:

- **B1 (corpus)** — the reviewer was right that changing the corpus needs *a new human
  decision AND a request revision*. The decision existed; the revision did not. `REQUEST.md`
  OQ1 is now SUPERSEDED to 9,805 items, with the prior text retained. Not reverted.
- **B2 (paper)** — accepted without argument. "Any change to `paper.md`" is an explicit
  non-goal, so the paper task is REMOVED from this slice. The fp16 disclosure is already
  durably recorded in `DECISIONS.md` and `GOTCHAS.md`; publishing it belongs to a separately
  authorised paper slice.
- **B5 (smoke tests)** — accepted. The earlier draft wrongly claimed nothing would call an
  endpoint; the constraints explicitly permit smoke tests as the only egress, and B4 cannot
  be satisfied without them. New task T2.
- **B6 (negatives)** — accepted, and it corrects a methodological error: negative-polarity
  canonical propositions are never scored, so a raw FALSE-target fraction does not answer
  B5. T1 now derives the projected count of scored POSITIVE-POLARITY negatives.
- **B3, B4, B7–B13** — accepted as genuine gaps; see the tasks.
- **A1 (rollback)** — accepted; the rollback no longer proposes tag deletion as the general case.

## Approach

Slice 4 writes the registration and the code implementing it, and tags both BEFORE any
cycle-3 generation exists. Slice 1 supplied the measured margins and per-item variance,
slice 2 the corrected paper, slice 3 the measured six-family availability with margin +1.

**The registered primary** is panel vs calibration-selected best single source. From slice 1,
under each cycle's OWN registered calibration map and the BASE instrument, the WCT-EM margin
is +0.0448 (c1_local, temperature, go), +0.0887 (c1_openrouter, temperature, go), +0.0762
(c2_panelA, platt, go) and +0.0329 (c2_panelB, platt, INCONCLUSIVE — its CI spans zero).

**Correction (this plan previously misquoted these).** An earlier revision listed +0.0848 and
+0.0858 for the cycle-2 panels. Those are the registered S1_deny_self_contradiction VARIANT,
not the base instrument. The base reading is the correct one and `REQUEST.md` decides it: the
request states the margin held "on three of four panel-cycles, and inconclusively on the
fourth". Under the base instrument that is exactly what the artifacts say. Under the variant
all four are conclusive, which contradicts the request — and it would also compare cycle 1's
base against cycle 2's variant, since cycle 1 has no variant level at all. Both readings give
the same +0.0448 to +0.0887 range because the endpoints come from cycle 1 either way, so the
range alone cannot distinguish them; the conclusive COUNT can. delta is derived from the
conclusive cycles only, so it is +0.0448 and the inconclusive +0.0329 does not lower the
floor. The variant is reported in the registration as declared sensitivity, and
`exp3/validate_v3.py` re-checks this against REQUEST.md independently of the builder.

**The six families, ordered.** Slice 3 measured six reachable families of which exactly three
still answer under their PINNED ids. That fact supplies the ordering rather than an arbitrary
choice — identity assurance descending:

| # | family | working id | tier | identity basis |
|---|--------|-----------|------|----------------|
| 1 | qwen | local `qwen3.8-27b` | local | weights: `model_path` + `n_params` |
| 2 | zhipu | `zai-org/GLM-5.2` | free | pinned id still answers |
| 3 | nvidia | `nvidia/nemotron-3-super-120b-a12b` | paid | pinned id still answers |
| 4 | openai | `openai/gpt-oss-20b` | paid | paid twin; `:free` withdrawn |
| 5 | google | `google/gemma-4-26b-a4b-it` | paid | paid twin; `:free` rate limited |
| 6 | poolside | `poolside/laguna-xs-2.1` | paid | MARGIN; `:free` returned 429 |

M=3 = {1,2,3} — exactly the set whose pinned ids survive. M=4 = M=3 ∪ {4}. M=5 = M=4 ∪ {5}.
Family 6 is the declared margin, smoke-tested and priced but not in the primary M=5 panel.

**The instrument changes and is registered as changed.** Cycles 1–2 ran NLI in fp16 (the
checkpoint declares `dtype=float16`; transformers honours it on CPU), which is device
dependent. Cycle 3 registers fp32 on GPU, device independent to 7.8e-06. The driver must
FAIL CLOSED if that instrument is unavailable rather than silently falling back to fp16.

**Corpus** is 9,805 items pinned at SHA-256
`63ca8131b43b5c81681deed8bc705c6c2f6f1c56fdac929d9b1efb7584e504a1`, with cycle 2's 150 items a
verified complete subset. NLI is no longer the binding constraint (~6.3 h on GPU); generation
spend is, so B7's caps are the real control.

`wct3/gpu.py` + `tests/test_wct3_gpu.py` were written during an investigation while the run was
in `planning` and committed UNREVIEWED in `76d2c49`. T4 brings them under this slice's gates.

## Risks

- **Registering a number the artifacts do not contain.** Already happened twice: "2,353 items"
  was a raw row count (true: 2,277), and the draft's margin range was wrong. Mitigation: no
  numeric literal in `prereg_v3.yaml` is hand-typed; all are emitted by `exp3/prereg_v3_build.py`
  from artifacts and independently RE-DERIVED by the gate, which fails on mismatch.
- **Generation before the tag.** Mitigation: T5's driver refuses any non-dry run unless the
  expected tag resolves to the tested tree; T7 asserts an empty cycle-3 artifact set at tag time.
  Both are needed — an empty-artifact check alone cannot stop someone invoking the driver
  between implementation and tagging (B8).
- **Silent instrument downgrade.** If CUDA is missing the driver could fall back to fp16 and
  void the registration. Mitigation: fail closed, record device/precision/cache-namespace in
  every artifact, and ensure the CUDA check cannot pass by being skipped (B13).
- **Mixing fp16-cached and fp32-computed NLI.** Smallest observed alignment margin is 0.0021,
  exactly 1× the fp16→fp32 perturbation. Mitigation: distinct `WCT_CACHE` root, refuse to run
  against the frozen root, and gate-assert the frozen `out/cache/nli` count is unchanged.
- **Smoke tests contaminating experimental data.** Mitigation: T2 writes only to
  `out/slice4/smoke/`, never the generation cache, and the gate asserts the cycle-3 artifact
  set is empty regardless.
- **Underpowered dose-response.** At n=9,805 the detectable increment is ~0.0101 nats. B2
  requires this be STATED for M=3, M=4 and M=5, and if inadequate, said plainly.

## Rollback

Per-task and additive. `prereg_v3.yaml`, `exp3/corpus_v3.py`, `exp3/prereg_v3_build.py`,
`exp3/smoke_v3.py`, `exp3/run_cycle3.py`, `run_slice4.sh` and their tests are NEW files:
`git rm` them, or `git revert` the slice commit. The four added parquet files under `data/` are
inputs only; deleting them reverts the corpus to the prior local set. `DECISIONS.md` is
append-only — a wrong entry is superseded by a further entry, never edited away. No migration,
no schema change, no state outside the repo. `paper.md` is untouched by this slice.

**On the tag (A1):** `git tag -d` is NOT the general rollback. It is permissible only for a
tag that is local, unpushed, and has no endpoint observation after it. Once the tag has been
pushed or any cycle-3 generation exists, the tag STAYS and a superseding or withdrawn-
registration record is added instead, because deleting it damages the audit trail the
registration exists to provide and cannot retract remote copies.

## Tasks

```json
[
  {
    "id": "T1",
    "title": "Corpus module: build, verify and pin the 9,805-item corpus (B5)",
    "depends_on": [],
    "files": ["exp3/corpus_v3.py", "tests/test_corpus_v3.py"],
    "acceptance": [
      "load_corpus() returns exactly 9805 items from depth-3 and depth-5 across test/dev/train",
      "corpus_sha256() == 63ca8131b43b5c81681deed8bc705c6c2f6f1c56fdac929d9b1efb7584e504a1",
      "raises if any item_id collides; asserts 0 duplicates across configs and splits",
      "verifies cycle 2's 150 items are a COMPLETE subset and raises if not",
      "derives the PROJECTED COUNT OF SCORED POSITIVE-POLARITY NEGATIVES: candidate propositions whose ground-truth answer is false AND whose canonical surface is positive-polarity, since negative-polarity propositions are never scored; a raw FALSE-target fraction is explicitly NOT acceptable for B5",
      "the projection states its assumptions and is labelled NOT a gate",
      "records the six source parquet SHA-256s",
      "writes no artifact of its own: it returns values for the registration to embed"
    ],
    "targeted_checks": ["PYTHONPATH=. WCT_CACHE=/home/jmannings/dev/waveconv/out/cache /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_corpus_v3.py"],
    "risk": "STANDARD"
  },
  {
    "id": "T2",
    "title": "Bounded endpoint smoke tests to pin an expected echo per panel member (B4)",
    "depends_on": [],
    "files": ["exp3/smoke_v3.py", "tests/test_smoke_v3.py"],
    "acceptance": [
      "probes all six pinned working ids plus the declared qwen OpenRouter fallback, at most ONE call each, and records the exact resolved serving identity returned",
      "the local qwen endpoint is additionally verified by model_path and n_params, not by echoed id alone",
      "fails on any identity mismatch against the expected echo, and records mismatches as substitution candidates rather than silently accepting them",
      "writes ONLY to out/slice4/smoke/ and never to the generation cache, so no smoke output can be mistaken for cycle-3 data",
      "credentials never reach any written artifact: reuse slice 3's allowlist sanitiser",
      "is idempotent and records measured_at, and a test proves a mismatch fails the run"
    ],
    "targeted_checks": ["cd /home/jmannings/dev/waveconv && PYTHONPATH=. /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_smoke_v3.py"],
    "risk": "HIGH-RISK",
    "lane_hint": "sonnet"
  },
  {
    "id": "T3",
    "title": "prereg_v3.yaml and its builder: every figure emitted from artifacts (B1,B2,B3,B5,B6,B7)",
    "depends_on": ["T1", "T2"],
    "files": ["prereg_v3.yaml", "exp3/prereg_v3_build.py", "tests/test_prereg_v3.py"],
    "acceptance": [
      "B1: every field EXPERIMENT.md 3.1(4) requires; primary is panel vs calibration-selected best single source",
      "B2: freezes ONE exact delta with the artifact and formula that produced it, derived from slice 1's WCT-EM margins under each cycle's own registered map (+0.0448, +0.0887, +0.0848, +0.0858), marked immutable-after-results; reports required n for M=3, M=4 AND M=5 against slice 1's measured per-item SD (0.184-0.313) and states the detectable increment at n=9805 (~0.0101 nats), saying plainly if any arm is underpowered",
      "B3: names the six families in a FIXED ordering with working ids and tiers, and names the M=3, M=4, M=5 subsets explicitly as nested sets; declares family 6 (poolside/laguna) as margin with its promotion trigger, whether data accumulated before promotion remain usable, and who adjudicates",
      "B4: pins an expected echo per panel member; registers the qwen local-to-OpenRouter fallback with its trigger, the fact that the fallback is the provider build and NOT the registered quantised weights, and the required disclosure on promotion",
      "B5: corpus pinned by SHA-256 with the projected scored positive-polarity negative count stated as a projection and explicitly not a gate",
      "B6: falsifiable predictions with adjudication rules; freezes the estimand, the uncertainty/test method, multiplicity handling across arms and maps, decision thresholds, and states the precise result that would REFUTE the dose-response",
      "B7: per-tier rates taken from slice 3's measured evidence, calls and cost computed per registered panel including retries and promotion/fallback, a hard cumulative per-panel cap, and persistence semantics across re-runs; asserts paid ids are used wherever a paid tier exists",
      "registers the instrument as fp32/GPU and records that cycles 1-2 were fp16, with the measured device-dependence figures",
      "NO numeric literal is hand-typed: a test asserts every figure in the yaml is reproduced by re-running the builder"
    ],
    "targeted_checks": ["cd /home/jmannings/dev/waveconv && PYTHONPATH=. WCT_CACHE=/home/jmannings/dev/waveconv/out/cache /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_prereg_v3.py"],
    "risk": "HIGH-RISK",
    "lane_hint": "sonnet"
  },
  {
    "id": "T4",
    "title": "Bring the unreviewed GPU instrument under this slice's gates",
    "depends_on": [],
    "files": ["wct3/gpu.py", "tests/test_wct3_gpu.py"],
    "acceptance": [
      "reviewed against wct/measure.py: dedup, longest-first batching, canonical column order and cache key are identical",
      "the precision divergence is deliberate, documented, and pinned by a test asserting fp32 weights despite the checkpoint declaring float16",
      "a CUDA-gated test asserts gpu/fp32 and cpu/fp32 agree below 1e-4 with no argmax flips",
      "install() is reversible and a test proves it restores measure.nli",
      "wct/ is NOT modified: the v2 tag stays byte-clean"
    ],
    "targeted_checks": ["cd /home/jmannings/dev/waveconv && PYTHONPATH=. WCT_CACHE=/home/jmannings/dev/waveconv/out/cache /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_wct3_gpu.py"],
    "risk": "STANDARD"
  },
  {
    "id": "T5",
    "title": "Cycle-3 analysis driver, committed before generation (B8,B12,B13)",
    "depends_on": ["T1", "T3"],
    "files": ["exp3/run_cycle3.py", "tests/test_run_cycle3.py"],
    "acceptance": [
      "implements the registered primary, the nested M=3/M=4/M=5 dose-response, and the declared promotions; reads panels, caps and delta from prereg_v3.yaml and never restates them",
      "B13 FAIL CLOSED: a non-dry run aborts unless the registered fp32/GPU instrument is active with a separate cache root; there is NO fp16 fallback path, and the check cannot pass by being skipped",
      "refuses to run if WCT_CACHE resolves to the frozen out/cache root",
      "records device, precision, model identity and cache namespace into every artifact it writes",
      "B8: refuses any non-dry run unless tag prereg-v3-2026-08-30 exists and resolves to the tested tree",
      "B12: generation is MODEL-MAJOR and strictly precedes analysis: one model completes its whole pass before the next begins, no concurrent model swaps, and no embedding or analysis call is issued while generation is active, because the local server has one model slot",
      "failed or transient-error generations are NEVER written into the immutable artifact cache, and retries interact deterministically with the cumulative caps",
      "enforces B7 per-panel cumulative caps persisted across re-runs, and aborts on cap breach",
      "dry-run mode proves the driver executes end to end with ZERO generation calls"
    ],
    "targeted_checks": ["cd /home/jmannings/dev/waveconv && PYTHONPATH=. WCT_CACHE=/home/jmannings/dev/waveconv/out/cache /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_run_cycle3.py"],
    "risk": "HIGH-RISK",
    "lane_hint": "sonnet"
  },
  {
    "id": "T6",
    "title": "Fingerprinted DECISIONS.md entry derived from the registration (B11)",
    "depends_on": ["T3"],
    "files": ["exp3/decide_v3.py", "tests/test_decide_v3.py"],
    "acceptance": [
      "renders the slice-4 outcome entry FROM prereg_v3.yaml after all choices are frozen, never hand-written",
      "embeds a fingerprint of the source registration so a stale entry is detectable",
      "supersedes an existing stale entry atomically rather than refusing to update, which is the failure slice 2 hit",
      "a planted stale-fingerprint test proves the check fails"
    ],
    "targeted_checks": ["cd /home/jmannings/dev/waveconv && PYTHONPATH=. /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_decide_v3.py"],
    "risk": "STANDARD"
  },
  {
    "id": "T7",
    "title": "One-command slice gate and the human-gated tag workflow (B9,B10)",
    "depends_on": ["T1", "T2", "T3", "T4", "T5", "T6"],
    "files": ["run_slice4.sh", "tests/test_slice4_gate.py"],
    "acceptance": [
      "B10: ONE command builds the emitted registration, runs every slice assertion, runs the full pinned suite, and its EXIT CODE is the sole pass signal; every failed stage propagates non-zero and an integration test proves it",
      "re-derives every numeric figure in prereg_v3.yaml independently and fails on any mismatch",
      "B9 immutability: asserts out/v3/, out/slice3/ and out/e1*_summary*.json are byte-identical to committed content, checking tracked AND untracked files, and asserts the v2 tag is byte-clean over exp/ wct/ m0/",
      "asserts out/cache/nli entry count is unchanged, so no fp32 leaked into the frozen cache",
      "asserts the cycle-3 generation artifact set is EMPTY",
      "re-runs frozen reproduction for all four panels under wct3.strict with WCT_LOCAL_BASE unroutable",
      "tag creation is a SEPARATE explicit human-gated step, not automatic; it records the registration and immutability fingerprints at that commit and verifies the tag resolves to the tested tree",
      "guards against gate-test recursion with SLICE4_GATE_RUNNING, as run_slice3.sh does",
      "a planted-failure test proves EACH assertion fails when violated: no assertion may pass vacuously"
    ],
    "targeted_checks": ["cd /home/jmannings/dev/waveconv && PYTHONPATH=. SLICE4_GATE_RUNNING=1 WCT_CACHE=/home/jmannings/dev/waveconv/out/cache /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_slice4_gate.py"],
    "risk": "HIGH-RISK",
    "lane_hint": "sonnet"
  }
]
```

## Open questions

None outstanding. OQ1 (corpus) superseded to 9,805 items, OQ2 (qwen pinning) resolved,
OQ3 (tag name `prereg-v3-2026-08-30`) and OQ4 (budget cap authorised) resolved by the human
on 2026-08-30. The generation SPEND itself is a later run's gate, not this slice's.
