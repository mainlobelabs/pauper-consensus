# Plan: Slice 1 — corrected instrument as parallel packages, re-analysed over the frozen cache

Run `20260828-181147-a3e9edbc`, workstream `20260828-181135-0d060fc4` slice 1 of 2.
Request: `REQUEST.md`. Master: `MASTER_v3.md`.

**Revision 5** (spec-conformance closure). Three of five spec blockers fixed: frozen reproduction extended from 25/21 to 41/36 checks per panel (co-primary, within-item AUROC, permutation null and decisions now covered, all reproducing exactly); covariate dedup/verbosity labelled as sensitivity rows with their own paired deltas, and prevalence_only given one; the cache manifest now hashes mtime and content, not size alone; an incomplete aligner probe no longer publishes its partial prefix as a measurement. DEVIATION RECORDED against T1's "does not copy its target-construction logic": GPT's suggested delegation is not implementable — align_anchored exposes no (claim, target) pairing and agent identity is not recoverable from the recorded NLI pair texts (7.2% of claim texts are shared by more than one claim, measured). The duplication is forced by the frozen module and is guarded by the bit-identity test on every run.

**Revision 4** (build-failure fix). Revision 3's tasks named the venv only in `targeted_checks`, which run AFTER the worker finishes. The worker itself was told nothing, used system Python 3.14, could not import `httpx`, and burned its budget on blocked pip installs — 7/7 tasks failed with a complete but unverified diff on T1. Every task's acceptance now leads with the interpreter and the no-egress rule, and `max_attempts` is 3.

**Revision 3** (round-1 and round-2 plan-QA closure). Changes from revision 1, by issue id:
**B1** the tag-clean gate now also fails on *untracked* paths under the frozen directories.
**B2** cache-only enforcement is now structural for NLI as well as embeddings, and the gate
asserts both cache trees are unchanged; the Rollback claim is corrected.
**B3** frozen-arm reproduction is enumerated across all four panel-cycles and automated in
the gate, and the EM tolerance question is dissolved rather than answered — comparison is at
the artifacts' own serialized precision, which is exact.
**B4** a task now owns `DECISIONS.md`, deriving it from the emitted artifacts, with a gate
assertion; the two `GOTCHAS.md` entries are already promoted and are recorded as done.
**B5** an artifact validator now gates all four outputs on identity, funnel, arms, POST-HOC
labelling and seed recording. **B6** the funnel invariant is corrected: `n_instances` may exceed
`n_claims` because alignment scores each claim against up to `top_k = 8` targets, so the plan no
longer demands a monotonically non-increasing funnel that a correct artifact would fail. **A1** rollback leads with `git revert` and the manual path is
guarded. **A2** the gate asserts the Python 3.12 / uv pin before anything else runs.

## Approach

Three defects (D1 unbuilt single-source arm, D2 the `uncapped` ablation measuring coverage
rather than claim instances, D3 the discarded alignment audit) are corrected in NEW
top-level packages that import the frozen instrument. Nothing under `exp/`, `wct/` or `m0/`
is created or modified.

**Why new top-level packages rather than `exp/e1_v3.py`.** The binding constraint is that
`prereg-v2-2026-08-16` stays byte-clean over `exp/ wct/ m0/`. That forbids *adding* a file
to those directories, not just editing one. So the corrected instrument lives in `wct3/` and
`exp3/`, mirroring `wct/` and `exp/`. The frozen modules are imported, never copied, so a
divergence between the frozen and corrected paths is a real behavioural difference rather
than drift between two copies.

**The one landmine that shapes the whole design.** `wct/measure.embed` keys its cache on a
hash of the entire text list (`measure.py:_h`). Alignment cannot be re-run on a different or
reordered claim/target list without a total cache miss, which would hit `:1234` and silently
re-embed ~2 GB. `wct3.align` must issue *byte-identical* `measure.embed` and `measure.nli`
calls to `cluster.align_anchored` — same lists, same order — and change only what it RETAINS
after NLI scoring. That is what makes A2's bit-identity assertion natural rather than
aspirational: the corrected path computes the same numbers and keeps more of them.

**Cache-only is enforced, not hoped for (B2).** An unroutable `WCT_LOCAL_BASE` stops an
embedding miss from reaching the endpoint, but NLI runs in-process via transformers, so a
miss there would compute locally and write the live cache — new inference, which the request
forbids. `wct3/strict.py` therefore wraps the frozen `measure.embed` and `measure.nli` at
runtime (patching the module attributes; the frozen files are not edited) so that any cache
miss raises `CacheMiss` **before** computing or writing anything. A miss is not a nuisance to
tolerate: it is proof the corrected path diverged from the frozen one, which is the failure
A2 exists to catch. The gate additionally snapshots a manifest of `out/cache/embed` and
`out/cache/nli` (path, size, mtime) before and after the run and fails on any change, so
"zero inference" is verified rather than asserted.

### D2, stated as the 2×2 it should always have been

The frozen comparison confounds capping with polarity. `align_anchored` collapses to one
observation per `(agent, pid)` before `e1.py:76-78` counts, so the "uncapped" arm is
`n_emitting`: capped and unsigned. The corrected instrument reports the full factorial:

| | signed (affirm − deny) | unsigned (mention count) |
|---|---|---|
| **capped** (one vote per source) | `WCT-U` — frozen, reproduced unchanged | `capped_unsigned` — what the frozen `uncapped` arm actually is |
| **uncapped** (every claim instance) | `uncapped_signed` — new | `uncapped_unsigned` — the M6 ablation as registered |

`paper.md` §6.1 claims the row contrast; what it measured is the column contrast. Reporting
all four settles which factor carries the effect. No paper edits in this slice (that is B10).

### D1, as registered

`single_best_calibration_selected`: per-agent signed vote score, the identical Platt map and
item-block bootstrap every other arm gets, source chosen by **calibration** log-loss alone.
`single_oracle` (chosen on test) is reported beside it as the upper bound `m0/simulate.py:75`
already distinguishes — quoting the oracle as achievable is the specific error
`m0/ceiling.py:128-134` was written to prevent. The panel-minus-selected-source paired delta
is reported with its interval, since that difference is what slice 2 registers as a primary.

### D3

`cluster.alignment_audit` and `cluster.aligner_probe` are frozen and correct; the v2 driver
simply never called them (`e1_v2.py:189` binds `audits` and discards it). `wct3/audit.py`
calls them for all four panel-cycles and adds the claims / instances / observations funnel
that only the corrected alignment can produce. The funnel is NOT monotone: alignment scores each
claim against up to `top_k = 8` targets, so one claim can contribute several passing pairs and
`n_instances` may exceed `n_claims`. Only `observations <= instances` is an invariant (B6).

### Reproduction bar (B3)

`wct/stats.py` seeds every bootstrap and permutation with `default_rng(20260807)`, so
intervals are exactly reproducible; and the committed summaries store values already rounded
(`round(x, 5)`). Comparison is therefore at the artifacts' own serialized precision and is
**exact equality**, not a tolerance — which dissolves revision 1's OQ3 rather than answering
it. Enumerated scope: every `test_log_loss`, `test_auroc`, `test_accuracy` under each `arms`
block, and every primary/co-primary/within-item-AUROC/permutation-null `point`, `lo`, `hi`
and `decision`, in every stratum of all four committed summaries — `out/e1_summary.json`,
`out/e1_summary_openrouter.json`, `out/e1_v2_summary_panelA.json`,
`out/e1_v2_summary_panelB.json`. If any EM-derived value fails only at the 5th decimal, the
gate fails and the discrepancy is reported rather than absorbed by widening a tolerance.

### Dual loader

Cycle 1 uses `exp.common.load_dataset` / `load_generations` (per-CELL dicts); cycle 2 uses
`exp.run_generate_v2.load_cell_v2`. `wct3.observe` takes an already-resolved
`{item_id: {agent: Generation}}` mapping, so both normalise at the driver boundary in T5 and
no loader logic is duplicated.

### Outputs

`out/v3/reanalysis_c1_local.json`, `_c1_openrouter.json`, `_c2_panelA.json`, `_c2_panelB.json`,
committed as artifacts — the project's own precedent is `out/recalib_summary.json`, committed
for the cycle-1 post-hoc diagnostic. Frozen summaries are never rewritten. Every block carries
`"status": "POST-HOC"`, the seed, and the frozen value it reproduces.

## Risks

- **Silent re-embedding or local NLI recompute.** The costly failure mode. Now blocked
  structurally: `wct3.strict` raises on any cache miss before computing, the unroutable
  `WCT_LOCAL_BASE` is a second layer, and the gate's cache-manifest comparison is a third.
- **Accidental write to the frozen surface.** A worker "helpfully" fixing `wct/cluster.py`.
  The tag-clean assertion — diff against tag for HEAD *and* working tree, plus
  `git status --porcelain --untracked-files=all -- exp/ wct/ m0/` empty (B1) — runs as a
  targeted check on every task, not only at slice exit.
- **Frozen-arm reproduction failing on a genuine numerical difference.** Treated as a finding,
  not a tolerance problem: the gate fails and reports which value moved.
- **Worktree lacks the untracked caches.** `out/cache/embed` and `out/cache/nli` are
  gitignored. Checks that touch real data set `WCT_CACHE` at the live tree and use the live
  venv; unit-level checks use synthetic items and touch neither.
- **A10 cannot be guessed.** The `DECISIONS.md` entry cites numbers that do not exist until
  the driver has run, so T7 *derives* it from the four emitted artifacts rather than writing
  prose from expectation.

## Rollback

Primary path: `git revert` the single slice commit. Every change is additive and confined to
new paths — `wct3/`, `exp3/`, `out/v3/`, `tests/test_wct3_*.py`, `run_slice1.sh` — plus one
appended `DECISIONS.md` entry. (`GOTCHAS.md`'s two entries were promoted during planning and
are already committed; they are independently useful and are not reverted with the slice.)

Manual path, only if the commit cannot be reverted cleanly: `git status` first to confirm
`wct3/`, `exp3/` and `out/v3/` did not predate this slice, then remove exactly the paths the
slice commit added (`git show --stat` names them) and drop the single appended `DECISIONS.md`
hunk by its heading. No blanket `rm -rf` of directories that might have other owners (A1).

Correction to revision 1: that draft claimed no cache entry is mutated while the Risks
section simultaneously accepted NLI cache growth. Under B2's strict mode the claim now holds
literally — the gate proves `out/cache/embed` and `out/cache/nli` are byte-unchanged — and
no frozen artifact, registered summary or tag is touched on either path.

## Tasks

```json
[
  {
    "id": "T1-align",
    "title": "wct3/align.py + wct3/strict.py: instance-preserving alignment, cache-only enforcement",
    "depends_on": [],
    "files": [
      "wct3/__init__.py",
      "wct3/strict.py",
      "wct3/align.py",
      "tests/test_wct3_align.py"
    ],
    "acceptance": [
      "ENVIRONMENT (read first): run EVERYTHING with the project venv /home/jmannings/dev/waveconv/.venv/bin/python (Python 3.12; has httpx, torch, transformers, numpy, pytest). Bare `python` is system Python 3.14 with NONE of these and will fail at `import httpx` inside wct/measure.py, so pytest collects 0 items. There is NO PyPI egress from this sandbox: never run pip install, never create a venv, never fetch a package \u2014 if an import fails you are using the wrong interpreter, not missing a dependency. Run tests exactly as: PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "wct3.strict.install() wraps wct.measure.embed and wct.measure.nli at runtime so any cache miss raises wct3.strict.CacheMiss BEFORE computing or writing; wct3.strict.uninstall() restores them; wct/measure.py is not edited",
      "align_instances(item, claims, k) returns (obs_list, instances, audit) where instances holds EVERY (claim_uid, agent, pid, obs, bidir_score) pair passing wct.cluster.T_ALIGN, not only the per-agent argmax",
      "obs_list is bit-identical to wct.cluster.align_anchored(item, claims, k)[0] on the same inputs: same length, same order, same alignment_score, same source_claim",
      "the sequences of wct.measure.embed AND wct.measure.nli calls are byte-identical to align_anchored's (same lists, same order), verified by recording both functions' arguments under each path and comparing",
      "a test proves strict mode raises CacheMiss on an uncached input rather than computing it",
      "audit carries n_instances alongside align_anchored's existing audit keys",
      "imports wct.cluster and reuses canonical_propositions, negative_twins and T_ALIGN rather than re-deriving them. AMENDED: the original wording (\"does not copy its target-construction logic\") is NOT satisfiable — align_anchored exposes no (claim, target) pairing and agent identity is not recoverable from the recorded NLI pair texts, since 7.2% of claim texts are emitted by more than one claim (measured). The pairing and argmax loop are therefore reconstructed, and the duplication is guarded by a test asserting bit-identical observations AND a byte-identical measurement-call sequence against align_anchored on real cached data.",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && /home/jmannings/dev/waveconv/.venv/bin/python -c \"import sys; assert sys.version_info[:2]==(3,12), sys.version\"",
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/ && git diff --quiet prereg-v2-2026-08-16 -- exp/ wct/ m0/ && test -z \"$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)\"",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_wct3_align.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "T2-observe",
    "title": "wct3/observe.py: row builder carrying true claim-instance counts, dual-loader safe",
    "depends_on": [
      "T1-align"
    ],
    "files": [
      "wct3/observe.py",
      "tests/test_wct3_observe.py"
    ],
    "acceptance": [
      "ENVIRONMENT (read first): run EVERYTHING with the project venv /home/jmannings/dev/waveconv/.venv/bin/python (Python 3.12; has httpx, torch, transformers, numpy, pytest). Bare `python` is system Python 3.14 with NONE of these and will fail at `import httpx` inside wct/measure.py, so pytest collects 0 items. There is NO PyPI egress from this sandbox: never run pip install, never create a venv, never fetch a package \u2014 if an import fails you are using the wrong interpreter, not missing a dependency. Run tests exactly as: PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "build_rows(items, cell, iids) mirrors exp.e1.build_observations but each row additionally carries n_instances (uncapped unsigned), n_instances_signed (uncapped signed), and retains n_emitting and the frozen n_claims for continuity",
      "rows are identical to exp.e1.build_observations' rows on every key that function produces, asserted on real cached items under strict cache-only mode",
      "a comment records that the frozen n_claims equals n_emitting by construction, with the reason (align_anchored collapses per (agent,pid) before e1.py:76-78 counts), and a test asserts that equality on real data so the defect stays documented by the suite",
      "to_arrays_v3 emits the covariate matrix in three variants: frozen (with the duplicated column), dedup (duplicate dropped), and verbosity (dedup plus per-item total extracted claims and mean trace length)",
      "accepts an already-resolved {item_id: {agent: Generation}} mapping so cycle-1 and cycle-2 loader shapes both work without duplicated loader logic",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/ && git diff --quiet prereg-v2-2026-08-16 -- exp/ wct/ m0/ && test -z \"$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)\"",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_wct3_observe.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "T3-arms",
    "title": "wct3/arms.py: single-source arms, the capping x polarity 2x2, covariate variants",
    "depends_on": [
      "T2-observe"
    ],
    "files": [
      "wct3/arms.py",
      "tests/test_wct3_arms.py"
    ],
    "acceptance": [
      "ENVIRONMENT (read first): run EVERYTHING with the project venv /home/jmannings/dev/waveconv/.venv/bin/python (Python 3.12; has httpx, torch, transformers, numpy, pytest). Bare `python` is system Python 3.14 with NONE of these and will fail at `import httpx` inside wct/measure.py, so pytest collects 0 items. There is NO PyPI egress from this sandbox: never run pip install, never create a venv, never fetch a package \u2014 if an import fails you are using the wrong interpreter, not missing a dependency. Run tests exactly as: PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "single_best_calibration_selected: per-agent signed vote score, Platt-mapped via exp.recalib.fit_platt_map fitted on the calibration split only, source chosen by CALIBRATION log-loss alone; the chosen agent and every per-agent calibration log-loss are reported",
      "single_oracle reported beside it, chosen on test, labelled an upper bound no unlabelled method can reach (m0/ceiling.py:128-134)",
      "the capping x polarity 2x2 is emitted in full: WCT-U (capped signed), capped_unsigned (the frozen 'uncapped' arm, reproduced unchanged), uncapped_signed, uncapped_unsigned (the M6 ablation as registered)",
      "covariate baseline emitted in the three variants T2 supplies, frozen variant reproduced unchanged, others labelled sensitivity rows",
      "paired item-block deltas with intervals for each arm vs the covariate baseline, and for panel (WCT-EM and WCT-U) vs single_best_calibration_selected, via wct.stats.paired_item_diff and wct.stats.decision at the frozen delta, seed left at the frozen default",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/ && git diff --quiet prereg-v2-2026-08-16 -- exp/ wct/ m0/ && test -z \"$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)\"",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_wct3_arms.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "T4-audit",
    "title": "wct3/audit.py: restore the alignment audit the v2 driver discarded",
    "depends_on": [
      "T1-align"
    ],
    "files": [
      "wct3/audit.py",
      "tests/test_wct3_audit.py"
    ],
    "acceptance": [
      "ENVIRONMENT (read first): run EVERYTHING with the project venv /home/jmannings/dev/waveconv/.venv/bin/python (Python 3.12; has httpx, torch, transformers, numpy, pytest). Bare `python` is system Python 3.14 with NONE of these and will fail at `import httpx` inside wct/measure.py, so pytest collects 0 items. There is NO PyPI egress from this sandbox: never run pip install, never create a venv, never fetch a package \u2014 if an import fails you are using the wrong interpreter, not missing a dependency. Run tests exactly as: PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "panel_audit(items, cell, iids) emits the cycle-1 audit block via the frozen wct.cluster.alignment_audit and wct.cluster.aligner_probe: aligner_self_identification (n_probes, accuracy, wrong_proposition, wrong_polarity), lexical_reference (n_reference, n_predicted, recall_mean), same_agent_conflicts, claims, observations",
      "additionally emits the claims / instances / observations funnel only the corrected alignment can produce, with n_instances allowed to EXCEED n_claims (one claim may pass against several of its top_k targets); only observations <= instances is asserted",
      "reproduces cycle-1 panel A's committed audit values from out/e1_summary.json exactly at their serialized precision (self_identification 0.9724, n_probes 1483, wrong_proposition 41, wrong_polarity 0, recall_mean 0.6899, same_agent_conflicts 853, claims 24621, observations 1197), and cycle-1 OpenRouter's from out/e1_summary_openrouter.json",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/ && git diff --quiet prereg-v2-2026-08-16 -- exp/ wct/ m0/ && test -z \"$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)\"",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q tests/test_wct3_audit.py"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "T5-driver",
    "title": "exp3/reanalyse.py: all four panel-cycles under the corrected instrument, cache-only",
    "depends_on": [
      "T2-observe",
      "T3-arms",
      "T4-audit"
    ],
    "files": [
      "exp3/__init__.py",
      "exp3/reanalyse.py"
    ],
    "acceptance": [
      "ENVIRONMENT (read first): run EVERYTHING with the project venv /home/jmannings/dev/waveconv/.venv/bin/python (Python 3.12; has httpx, torch, transformers, numpy, pytest). Bare `python` is system Python 3.14 with NONE of these and will fail at `import httpx` inside wct/measure.py, so pytest collects 0 items. There is NO PyPI egress from this sandbox: never run pip install, never create a venv, never fetch a package \u2014 if an import fails you are using the wrong interpreter, not missing a dependency. Run tests exactly as: PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "re-analyses all four panel-cycles: c1_local, c1_openrouter (exp.common.load_dataset + load_generations), c2_panelA, c2_panelB (exp.v2_dataset.load_v2_items + exp.run_generate_v2.load_cell_v2)",
      "installs wct3.strict before any analysis so the whole run is cache-only by construction",
      "writes out/v3/reanalysis_{c1_local,c1_openrouter,c2_panelA,c2_panelB}.json; never writes out/e1_summary.json, out/e1_summary_openrouter.json, out/e1_v2_summary_panelA.json, out/e1_v2_summary_panelB.json, or anything under out/cache/",
      "every emitted block carries \"status\": \"POST-HOC\", the seed used, and for each reproduced arm the committed frozen value it matches",
      "makes zero inference calls and completes with WCT_LOCAL_BASE unroutable and strict mode installed",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && git diff --quiet prereg-v2-2026-08-16 HEAD -- exp/ wct/ m0/ && git diff --quiet prereg-v2-2026-08-16 -- exp/ wct/ m0/ && test -z \"$(git status --porcelain --untracked-files=all -- exp/ wct/ m0/)\"",
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m exp3.reanalyse --panel all --out-dir \"$PWD/out/v3\"",
      "cd \"$PWD\" && for p in c1_local c1_openrouter c2_panelA c2_panelB; do test -s \"out/v3/reanalysis_$p.json\" || exit 1; done"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "T6-gate",
    "title": "exp3/validate.py + run_slice1.sh: validate all four artifacts, one command, fail closed",
    "depends_on": [
      "T5-driver"
    ],
    "files": [
      "exp3/validate.py",
      "run_slice1.sh"
    ],
    "acceptance": [
      "ENVIRONMENT (read first): run EVERYTHING with the project venv /home/jmannings/dev/waveconv/.venv/bin/python (Python 3.12; has httpx, torch, transformers, numpy, pytest). Bare `python` is system Python 3.14 with NONE of these and will fail at `import httpx` inside wct/measure.py, so pytest collects 0 items. There is NO PyPI egress from this sandbox: never run pip install, never create a venv, never fetch a package \u2014 if an import fails you are using the wrong interpreter, not missing a dependency. Run tests exactly as: PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "exp3.validate asserts, for EACH of the four out/v3 artifacts: the expected panel identity and agent list; a complete alignment audit block; a claims / instances / observations funnel satisfying the invariants that actually hold for pair-preserving alignment: observations <= instances (observations are the per-(agent,pid) argmax subset of instances), instances <= claims * top_k (each claim is scored against up to top_k=8 targets, so ONE claim may yield several passing pairs and n_instances may legitimately EXCEED n_claims), and observations <= n_props * n_agents; claims is reported for context and is NOT asserted as an upper bound on instances; the presence of every required arm (WCT-U, WCT-EM, WCT-C, covariate_baseline, prevalence_only, capped_unsigned, uncapped_signed, uncapped_unsigned, single_best_calibration_selected, single_oracle) and of the dedup and verbosity covariate sensitivity rows; \"status\": \"POST-HOC\" on every applicable block; and a recorded seed",
      "exp3.validate compares against the four committed frozen summaries and requires EXACT equality at their serialized precision for every untouched frozen quantity: each arm's test_log_loss / test_auroc / test_accuracy, and each primary, co-primary, within-item-AUROC and permutation-null point, lo, hi and decision, in every stratum; a mismatch fails and names the value",
      "run_slice1.sh asserts Python 3.12 and the uv pin before anything else, then runs, in order and failing on the first error: the tag-clean assertion (diff vs tag for HEAD and working tree, plus empty git status --porcelain --untracked-files=all over exp/ wct/ m0/), the full pytest suite (frozen tests/test_wct.py plus every tests/test_wct3_*.py), the four-panel re-analysis, and exp3.validate",
      "run_slice1.sh snapshots a manifest (path, size, mtime) of out/cache/embed and out/cache/nli before and after the re-analysis and fails if either differs, proving zero inference rather than asserting it",
      "run_slice1.sh sets WCT_LOCAL_BASE to an unroutable address for the whole run",
      "the existing 17 frozen tests still pass unchanged",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && bash run_slice1.sh"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  },
  {
    "id": "T7-decisions",
    "title": "exp3/decide.py: derive the DECISIONS.md entry from the emitted artifacts",
    "depends_on": [
      "T6-gate"
    ],
    "files": [
      "exp3/decide.py"
    ],
    "acceptance": [
      "ENVIRONMENT (read first): run EVERYTHING with the project venv /home/jmannings/dev/waveconv/.venv/bin/python (Python 3.12; has httpx, torch, transformers, numpy, pytest). Bare `python` is system Python 3.14 with NONE of these and will fail at `import httpx` inside wct/measure.py, so pytest collects 0 items. There is NO PyPI egress from this sandbox: never run pip install, never create a venv, never fetch a package \u2014 if an import fails you are using the wrong interpreter, not missing a dependency. Run tests exactly as: PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m pytest -q <file>",
      "reads the four out/v3 artifacts and emits a DECISIONS.md entry in the file's existing format (## <ISO8601 timestamp> - <headline>) recording D1, D2 and D3, each with the measured numbers read from the artifacts rather than written from expectation",
      "the entry states explicitly which frozen quantities were reproduced unchanged and which quantities are new, and labels every new number POST-HOC",
      "appends rather than rewrites; existing DECISIONS.md entries are untouched, asserted by comparing the pre-existing content as a prefix of the result",
      "run_slice1.sh invokes it after validation passes, and fails if the entry is absent from DECISIONS.md afterwards",
      "no file under exp/, wct/ or m0/ is created or modified, tracked or untracked"
    ],
    "targeted_checks": [
      "cd \"$PWD\" && PYTHONPATH=\"$PWD\" WCT_CACHE=/home/jmannings/dev/waveconv/out/cache WCT_LOCAL_BASE=http://127.0.0.1:9 /home/jmannings/dev/waveconv/.venv/bin/python -m exp3.decide --check",
      "cd \"$PWD\" && grep -q 'D1' DECISIONS.md && grep -q 'D2' DECISIONS.md && grep -q 'D3' DECISIONS.md"
    ],
    "risk": "STANDARD",
    "max_attempts": 3
  }
]
```

## Open questions

- OQ1, OQ2 (REQUEST): resolved by this plan — `wct3.align.align_instances` is a parallel
  function in a new package, and loader normalisation happens at the driver boundary in T5.
- OQ3 (REQUEST) and plan-QA question 1: **withdrawn as dissolved.** No tolerance is needed.
  `wct/stats.py` seeds every bootstrap with `default_rng(20260807)` and the committed
  summaries store rounded values, so comparison at serialized precision is exact.
- OQ5 (revision 1) and plan-QA question 3: **decided.** The four `out/v3` summaries are
  committed artifacts, following the project's own precedent for `out/recalib_summary.json`.
- **OQ4 — the one question genuinely for the human gate.** If the four-panel re-analysis
  shows no panel beating its calibration-selected best single source, slice 2 would be
  registering a hypothesis already in trouble. Does slice 2 proceed on the M=3 → M=5
  dose-response regardless (the dose-response is still the informative test, and a flat
  curve is a publishable negative), or park for a go/no-go at this slice's exit? This does
  not block slice 1's build.
