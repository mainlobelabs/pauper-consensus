"""V2 generation driver: E1 treatment cell only, both panels, frozen corpus.

Differences from exp/run_generate.py, all of them registration requirements
(prereg_v2.yaml `generation` / `panels`):

- No E0 factorial. The plan is the cross_family_diverse_role cell over the 150
  frozen v2 items: 450 (item, agent) pairs per panel.
- Panels are MIXED-BACKEND: each agent carries its own {backend, model}, and
  the cache key uses the AGENT's backend, which is what lets panelB (all
  openrouter, unchanged from v1) reuse its 234 v1-cached generations while
  panelA (new panel: local + openrouter + hoonify) starts cold at 450 calls.
- Preflight is mandatory and aborts before any network call: reuse counts must
  match the registration exactly (panelB 234/216, panelA 0/450), and pinned
  local models must actually be served — substitution is forbidden.
- Hard per-panel caps (panelB 260, panelA 540) on CUMULATIVE attempted calls,
  persisted in out/attempts_v2_<panel>.json across re-runs — a persistently
  failing panel cannot be re-run into unbounded spend, which is the registered
  semantics ("abort if attempted calls would exceed the cap"). nodes.Client
  does one retry internally (plus bounded 429 backoff retries, which the
  provider does not serve) and never caches errors, so a re-run repairs
  failures without re-spending successes.

Usage:
    .venv/bin/python -m exp.run_generate_v2 --panel panelB --dry
    .venv/bin/python -m exp.run_generate_v2 --panel panelB
    .venv/bin/python -m exp.run_generate_v2 --panel panelA
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from exp.envfile import load_harness_env
from exp.v2_dataset import PREREG_V2, load_v2_items
from wct import cache, nodes
from wct.schema import Generation


def build_plan(items, panel: dict) -> list[dict]:
    cross = panel["cross_family"]
    agents = list(cross)                       # key order = latin-square order
    roles = ["forward", "backward", "skeptic"]
    plan = []
    for idx, it in enumerate(items):
        rot = nodes.latin_square(agents, roles, idx)
        for a in agents:
            plan.append(dict(item=it, agent=a, backend=cross[a]["backend"],
                             model=cross[a]["model"], role=rot[a],
                             seed=1, cell="cross_family_diverse_role"))
    return plan


def keyed(plan):
    dec = PREREG_V2["generation"]
    for p in plan:
        yield p, cache.cache_key(
            item=p["item"].item_id, backend=p["backend"], model=p["model"],
            role=p["role"], prompt=nodes.build_prompt(p["item"], p["role"]),
            seed=p["seed"], temperature=dec["temperature"],
            max_tokens=dec["max_tokens"],
        )


def load_cell_v2(items, panel_name: str):
    """Cache-only loader for analysis: {item_id: {agent: Generation}}."""
    panel = PREREG_V2["panels"][panel_name]
    cell: dict = {}
    missing = 0
    for p, key in keyed(build_plan(items, panel)):
        hit = cache.get("generation", key)
        if hit is None:
            missing += 1
            continue
        cell.setdefault(p["item"].item_id, {})[p["agent"]] = Generation(**hit)
    return cell, {"planned": len(items) * 3, "cached": len(items) * 3 - missing,
                  "missing": missing}


def preflight(plan, panel_name: str) -> list[tuple[dict, str]]:
    """Verify the registered reuse contract; return work still to generate."""
    spec = PREREG_V2["generation"]["quota_cap"][panel_name]
    want_new = spec["planned_new_calls"]
    want_reused = 450 - want_new
    hits = 0
    todo = []
    for p, key in keyed(plan):
        if cache.get("generation", key) is not None:
            hits += 1
        else:
            todo.append((p, key))
    print(f"preflight[{panel_name}]: reused hits {hits} (expect {want_reused}), "
          f"new calls {len(todo)} (expect {want_new})")
    if hits != want_reused or len(todo) != want_new:
        raise SystemExit(
            "ABORT: preflight does not match the registration; either the "
            "ordering contract broke (panelB) or unexpected cache entries "
            "exist. No calls were made.")
    return todo


def assert_local_models_served(panel: dict) -> None:
    pinned = {c["model"] for c in panel["cross_family"].values()
              if c["backend"] == "local"}
    if not pinned:
        return
    with urllib.request.urlopen(f"{nodes.LOCAL_BASE}/models", timeout=15) as r:
        served = {m["id"] for m in json.load(r)["data"]}
    absent = pinned - served
    if absent:
        raise SystemExit(
            f"ABORT: pinned local models not served: {sorted(absent)}. "
            "Substitution is forbidden (prereg_v2 resolution_rule). "
            "No calls were made.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="panelB", choices=["panelA", "panelB"])
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    panel = PREREG_V2["panels"][args.panel]
    items, _calib, _test = load_v2_items()     # verifies the frozen corpus
    plan = build_plan(items, panel)
    todo = preflight(plan, args.panel)

    if args.dry:
        by = {}
        for p, _ in todo:
            k = f"{p['backend']}:{p['model']}"
            by[k] = by.get(k, 0) + 1
        print(f"dry run: {len(todo)} calls would be made: {json.dumps(by, indent=1)}")
        return 0

    load_harness_env()                          # keys for openrouter/hoonify
    assert_local_models_served(panel)
    cap = PREREG_V2["generation"]["quota_cap"][args.panel]["cap_with_retry_allowance"]
    dec = PREREG_V2["generation"]

    # cumulative attempt ledger: the cap binds across re-runs, not per run
    Path("out").mkdir(exist_ok=True)
    ledger = Path(f"out/attempts_v2_{args.panel}.json")
    attempts = json.loads(ledger.read_text())["attempts"] if ledger.exists() else 0

    # Backend-major then model-major: the local single-slot server loads each
    # model once (GOTCHAS), and remote backends batch together.
    todo.sort(key=lambda pk: (pk[0]["backend"], pk[0]["model"], pk[0]["item"].item_id))

    clients: dict[str, nodes.Client] = {}
    index, errors = [], 0
    t0 = time.time()
    for n, (p, _key) in enumerate(todo, 1):
        if attempts + 1 > cap:
            print(f"ABORT: cumulative attempt cap {cap} reached "
                  f"({attempts} attempted across all runs) with work "
                  "remaining; the registered envelope is exhausted.",
                  file=sys.stderr)
            break
        attempts += 1
        ledger.write_text(json.dumps({"attempts": attempts}))
        cl = clients.setdefault(p["backend"], nodes.Client(p["backend"]))
        g = cl.generate(
            p["item"], p["agent"], p["model"], p["role"], seed=p["seed"],
            temperature=dec["temperature"], max_tokens=dec["max_tokens"],
        )
        errors += bool(g.error)
        index.append(dict(item_id=p["item"].item_id, agent=p["agent"],
                          backend=p["backend"], model=p["model"], role=p["role"],
                          seed=p["seed"], cell=p["cell"], chars=len(g.trace),
                          error=g.error))
        if n % 10 == 0 or n == len(todo):
            el = time.time() - t0
            print(f"  {n}/{len(todo)}  errors={errors}  {el/60:.1f}min  "
                  f"eta {(el/n)*(len(todo)-n)/60:.0f}min", flush=True)

    # merge-on-write: a resumed run must not erase earlier runs' index entries
    idx_path = Path(f"out/generation_index_v2_{args.panel}.json")
    if idx_path.exists():
        prior = json.loads(idx_path.read_text())
        have = {(e["item_id"], e["agent"], e["role"], e["seed"]) for e in index}
        index = [e for e in prior
                 if (e["item_id"], e["agent"], e["role"], e["seed"]) not in have] + index
    idx_path.write_text(json.dumps(index, indent=2))
    print(f"done[{args.panel}]: {len(index)} indexed generations, "
          f"{errors} errors this run, {attempts} cumulative attempts")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
