"""Shared loading for the analysis stages. Reads cache only; never generates.

Every analysis in this study re-runs over cached artifacts at zero inference
cost, which is what makes it safe to iterate on the analysis without the
temptation to also re-roll the data.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from wct import cache, data, nodes
from wct.schema import Generation, Item

PREREG = yaml.safe_load(Path("prereg.yaml").read_text())
CELLS = ["same_family_same_role", "same_family_diverse_role",
         "cross_family_same_role", "cross_family_diverse_role"]


def load_dataset() -> tuple[list[Item], set[str], set[str]]:
    d = PREREG["dataset"]
    n = d["n_calibration"] + d["n_test"]
    items = data.load_items(
        config=d["config"], split=d["split"], limit=n,
        min_qdep=d["selection"]["min_target_qdep"],
        require_conjunctive=d["selection"]["require_conjunctive"],
    )
    calib, test = data.split_items(
        items, calib_frac=d["n_calibration"] / n, seed=d["split_seed"]
    )
    return items, {i.item_id for i in calib}, {i.item_id for i in test}


def load_generations(items: list[Item], calib: set[str], backend: str = "local"):
    """Rebuild the generation plan and pull every completed call from cache.

    Returns {cell: {item_id: {agent: Generation}}} plus a coverage report, so a
    partial run is analysable and its incompleteness is visible rather than
    silently averaged over.
    """
    from exp.run_generate import build_plan

    panel = PREREG["panels"][backend]
    plan = build_plan(items, calib, panel)
    out: dict = {c: {} for c in CELLS}
    missing = 0
    for p in plan:
        it = p["item"]
        key = cache.cache_key(
            item=it.item_id, backend=backend, model=p["model"], role=p["role"],
            prompt=nodes.build_prompt(it, p["role"]), seed=p["seed"],
            temperature=PREREG["decode"]["temperature"],
            max_tokens=PREREG["decode"]["max_tokens"],
        )
        hit = cache.get("generation", key)
        if hit is None:
            missing += 1
            continue
        out[p["cell"]].setdefault(it.item_id, {})[p["agent"]] = Generation(**hit)
    total = len(plan)
    return out, {"planned": total, "cached": total - missing, "missing": missing}


def complete_items(cell: dict, min_agents: int = 2) -> list[str]:
    """Items with enough usable traces. Registered exclusion rule."""
    ok = []
    for iid, agents in cell.items():
        usable = [g for g in agents.values() if g.trace.strip() and not g.error]
        if len(usable) >= min_agents:
            ok.append(iid)
    return sorted(ok)
