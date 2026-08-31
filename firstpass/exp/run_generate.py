"""Generation driver for E0 and E1. Sequential, model-major, fully cached.

Model-major ordering is not a style choice: the local server serves one model at
a time and JIT-evicts, so item-major ordering would reload a model on every item
(GOTCHAS.md). Grouping by model loads each one once.

Every call is content-hash cached and write-once, so re-running this script
after an interruption costs nothing for work already done, and all downstream
analysis re-runs over the cache with no inference at all.

Usage:
    .venv/bin/python -m exp.run_generate            # local panel
    .venv/bin/python -m exp.run_generate --backend openrouter
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

from wct import cache, data, nodes
from wct.schema import Item

PREREG = yaml.safe_load(Path("prereg.yaml").read_text())


def build_plan(items: list[Item], calib: set[str], panel: dict) -> list[dict]:
    """Every (item, agent, model, role, seed) the two experiments need.

    E0's four factorial cells run on calibration items only; E1's treatment cell
    (cross-family, diverse-role) additionally runs on every test item.
    """
    cross = panel["cross_family"]
    same = panel["same_family"]
    cross_agents, same_agents = list(cross), list(same)
    diverse_roles = ["forward", "backward", "skeptic"]
    plan: list[dict] = []

    # A panel may run the E0 factorial on a SUBSET of the calibration items so
    # the request cap fits its measured quota with retry allowance (R0 A5). The
    # E1 treatment cell always covers every item, because that is the primary.
    subset = panel.get("e0_calib_subset")
    e0_calib = set(sorted(calib)[:subset]) if subset else set(calib)

    for idx, it in enumerate(items):
        is_calib = it.item_id in e0_calib
        rot = nodes.latin_square(cross_agents, diverse_roles, idx)
        rot_same = nodes.latin_square(same_agents, diverse_roles, idx)

        # E1 treatment cell: every item
        for a in cross_agents:
            plan.append(dict(item=it, agent=a, model=cross[a], role=rot[a],
                             seed=1, cell="cross_family_diverse_role"))
        if not is_calib:
            continue
        # E0 remaining three cells: calibration items only
        for a in cross_agents:
            plan.append(dict(item=it, agent=a, model=cross[a], role="neutral",
                             seed=1, cell="cross_family_same_role"))
        for i, a in enumerate(same_agents):
            plan.append(dict(item=it, agent=a, model=same[a], role="neutral",
                             seed=i + 1, cell="same_family_same_role"))
        for i, a in enumerate(same_agents):
            plan.append(dict(item=it, agent=a, model=same[a], role=rot_same[a],
                             seed=i + 1, cell="same_family_diverse_role"))
    return plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="local", choices=["local", "openrouter"])
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    panel = PREREG["panels"][args.backend]
    if panel.get("status") == "BLOCKED":
        print(f"panel '{args.backend}' is BLOCKED: {panel['blocker']}", file=sys.stderr)
        return 2

    d = PREREG["dataset"]
    n_total = d["n_calibration"] + d["n_test"]
    items = data.load_items(
        config=d["config"], split=d["split"], limit=args.limit or n_total,
        min_qdep=d["selection"]["min_target_qdep"],
        require_conjunctive=d["selection"]["require_conjunctive"],
    )
    calib_items, test_items = data.split_items(
        items, calib_frac=d["n_calibration"] / n_total, seed=d["split_seed"]
    )
    calib = {i.item_id for i in calib_items}
    data.save_manifest(items)
    print(f"items {len(items)} (calib {len(calib_items)} / test {len(test_items)})")

    plan = build_plan(items, calib, panel)
    # model-major: load each model once
    plan.sort(key=lambda p: (p["model"], p["item"].item_id, p["agent"], p["seed"]))
    print(f"planned generations: {len(plan)}")

    client = nodes.Client(args.backend)
    done = errors = 0
    t0 = time.time()
    index: list[dict] = []
    for n, p in enumerate(plan, 1):
        g = client.generate(
            p["item"], p["agent"], p["model"], p["role"], seed=p["seed"],
            temperature=PREREG["decode"]["temperature"],
            max_tokens=PREREG["decode"]["max_tokens"],
        )
        done += 1
        errors += bool(g.error)
        index.append(dict(item_id=p["item"].item_id, agent=p["agent"],
                          model=p["model"], role=p["role"], seed=p["seed"],
                          cell=p["cell"], chars=len(g.trace), error=g.error))
        if n % 10 == 0 or n == len(plan):
            el = time.time() - t0
            print(f"  {n}/{len(plan)}  errors={errors}  "
                  f"{el/60:.1f}min elapsed  eta {(el/n)*(len(plan)-n)/60:.0f}min",
                  flush=True)

    Path("out").mkdir(exist_ok=True)
    Path("out/generation_index.json").write_text(json.dumps(index, indent=2))
    print(f"done: {done} generations, {errors} errors, cache={cache.stats()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
