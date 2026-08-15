"""V2 corpus: 78 reused depth-3 negation items + 72 depth-5 negation items.

The ordered item list is FROZEN in prereg_v2.yaml; this module reconstructs the
Item objects and verifies every property the registration depends on. It never
chooses anything — all selection happened before the v2 freeze and is recorded
in the prereg. If any check here fails, generation must not run.

Why ordering matters enough to freeze: run_generate assigns roles by
latin_square(agents, roles, item_index), so an item's role assignment — and
therefore its cache key — depends on its POSITION mod 3. The 78 reused items
are placed at v2 indices congruent (mod 3) to their v1 indices, which makes
their v1 cached generations exact cache hits (234 per panel) instead of 234
re-paid calls. verify() asserts this congruence rather than trusting it.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from wct import data
from wct.schema import Item

PREREG_V2 = yaml.safe_load(Path("prereg_v2.yaml").read_text())


def load_v2_items() -> tuple[list[Item], set[str], set[str]]:
    """Items in frozen v2 order, plus calib/test id sets.

    Returns (items, calib_ids, test_ids). Raises on any registration mismatch.
    """
    spec = PREREG_V2["dataset"]
    order = [e["id"] for e in spec["items"]]
    sources = {e["id"]: e["source"] for e in spec["items"]}
    v1_idx = {e["id"]: e["v1_idx"] for e in spec["items"] if e["v1_idx"] is not None}

    # depth-3 loaded EXACTLY as v1 loaded it, so target choices reproduce.
    d3 = data.load_items(config="depth-3", split="test", limit=150,
                         min_qdep=2, require_conjunctive=True)
    d5 = data.load_items(config="depth-5", split="test", limit=None,
                         min_qdep=2, require_conjunctive=True)
    by_id = {i.item_id: i for i in d3} | {i.item_id: i for i in d5}

    missing = [x for x in order if x not in by_id]
    if missing:
        raise RuntimeError(
            f"{len(missing)} frozen item ids failed to reproduce from the "
            f"loaders (target choice drifted?): {missing[:5]}"
        )
    items = [by_id[x] for x in order]
    verify(items, order, sources, v1_idx, d3)

    calib_items, test_items = data.split_items(
        items, calib_frac=spec["n_calibration"] / len(items),
        seed=spec["split_seed"],
    )
    calib_ids = {i.item_id for i in calib_items}
    if len(calib_ids) != spec["n_calibration"]:
        raise RuntimeError("split did not produce the registered calib size")
    return items, calib_ids, {i.item_id for i in test_items}


def _require(cond: bool, msg: str) -> None:
    """Not `assert`: registration tripwires must survive `python -O`."""
    if not cond:
        raise RuntimeError(f"v2 corpus verification failed: {msg}")


def verify(items, order, sources, v1_idx, d3) -> None:
    import hashlib

    spec = PREREG_V2["dataset"]
    v1_pos = {it.item_id: i for i, it in enumerate(d3)}

    # the parquet snapshots are the ground truth the whole corpus derives from
    for cfg, want in spec["source_sha256"].items():
        got = hashlib.sha256(
            Path(f"data/proofwriter_{cfg}_test.parquet").read_bytes()).hexdigest()
        _require(got == want, f"{cfg} parquet sha256 {got[:12]} != frozen {want[:12]}")

    _require(len(items) == 150 and len(set(order)) == 150, "corpus size")
    # every item is negation-family: the corpus-level fix for the noneg defect
    for it in items:
        _require(it.item_id.split("-")[0] in ("RelNeg", "AttNeg"),
                 f"non-negation item {it.item_id}")
        want = sources[it.item_id]
        got = "depth-5" if "-D5-" in it.item_id else "depth-3"
        _require(got == want, f"{it.item_id}: source {got} != frozen {want}")
    # cache-preservation congruence: reused items keep v1 index mod 3
    reused = [x for x in order if x in v1_pos]
    _require(len(reused) == spec["n_reused_depth3"] == 78, "reused count")
    for i, x in enumerate(order):
        if x in v1_pos:
            _require(v1_pos[x] % 3 == i % 3,
                     f"{x}: v2 idx {i} breaks mod-3 congruence with v1 idx {v1_pos[x]}")
            _require(v1_idx[x] == v1_pos[x], f"{x}: frozen v1_idx stale")
    # frozen corpus-level counts
    y0 = sum(1 for it in items for p in it.propositions if p.y == 0)
    y0pos = sum(1 for it in items for p in it.propositions
                if p.y == 0 and '"+"' in p.representation.replace(" ", ""))
    _require(y0 == spec["counts"]["y0_props"], f"y0 {y0}")
    _require(y0pos == spec["counts"]["y0_positive_polarity"], f"y0pos {y0pos}")
