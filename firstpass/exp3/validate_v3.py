"""Independent validation of prereg_v3.yaml. Does NOT import the builder. (B10/T7)

The gate previously validated the registration by re-running the emitter and diffing.
That can only catch a corrupted FILE, never a wrong BUILDER: a mis-selected artifact node
produces the same wrong answer both times and the check passes. This module recomputes the
load-bearing figures by its own route and cross-checks them against independent anchors --
REQUEST.md's stated margin range, raw parquet contents, and the arithmetic identities the
cost model has to satisfy. It deliberately shares no code with prereg_v3_build.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import yaml

PREREG = Path("prereg_v3.yaml")
REQUEST = Path("REQUEST.md")


class ValidationError(RuntimeError):
    pass


def _fail(msg: str) -> None:
    raise ValidationError(msg)


def check_corpus(doc: dict) -> list[str]:
    """Recount and rehash from the parquet files, independently of corpus_v3."""
    import pandas as pd
    from wct import data

    notes = []
    items = []
    for cfg in ("depth-3", "depth-5"):
        for split in ("test", "dev", "train"):
            items.extend(data.load_items(config=cfg, split=split))
    n = len(items)
    if n != doc["dataset"]["n_items"]:
        _fail(f"corpus: registration says {doc['dataset']['n_items']} items, artifacts give {n}")
    ids = [i.item_id for i in items]
    if len(set(ids)) != n:
        _fail(f"corpus: {n - len(set(ids))} duplicate item_ids")
    h = hashlib.sha256()
    for it in sorted(items, key=lambda x: x.item_id):
        h.update(f"{it.item_id}\x01{it.question}\x01{it.answer}\x01{it.theory}\x00".encode())
    if h.hexdigest() != doc["dataset"]["sha256"]:
        _fail("corpus: recomputed sha256 does not match the registration")
    dec = sum(len(i.decidable()) for i in items)
    if dec != doc["dataset"]["decidable"]:
        _fail(f"corpus: decidable count {dec} != registered {doc['dataset']['decidable']}")
    neg = sum(1 for i in items for p in i.decidable()
              if str(p.answer).lower().startswith("f"))
    if neg != doc["dataset"]["positive_polarity_negatives"]:
        _fail(f"corpus: negatives {neg} != registered "
              f"{doc['dataset']['positive_polarity_negatives']}")
    notes.append(f"corpus {n} items, sha and counts recomputed independently")
    return notes


def check_margins_against_request(doc: dict) -> list[str]:
    """Cross-check delta against REQUEST.md's stated range and the raw artifacts.

    REQUEST.md is written by a human and is not derived from the builder, so it is a
    genuinely external anchor on which artifact node is the registered one.
    """
    notes = []
    txt = REQUEST.read_text()
    m = re.search(r"\+0\.(\d{4}) to \+0\.(\d{4})", txt)
    if not m:
        _fail("REQUEST.md no longer states a margin range; the external anchor is gone")
    lo_req, hi_req = float(f"0.{m.group(1)}"), float(f"0.{m.group(2)}")

    margins = doc["measured_margins_slice1"]
    conclusive = {k: v for k, v in margins.items() if v.get("decision") == "go"}
    pts = [v["point"] for v in conclusive.values()]
    if not pts:
        _fail("no conclusive margins recorded")
    if round(min(pts), 4) != lo_req or round(max(pts), 4) != hi_req:
        _fail(f"conclusive margin range +{min(pts):.4f}..+{max(pts):.4f} contradicts "
              f"REQUEST.md's +{lo_req:.4f} to +{hi_req:.4f}: the wrong artifact node is "
              f"being read")
    if len(conclusive) != len(margins) - 1:
        _fail(f"REQUEST.md describes three of four panel-cycles conclusive and one "
              f"inconclusive; the registration records {len(conclusive)} of {len(margins)}")

    # and re-read each margin straight from its recorded artifact path
    for name, rec in margins.items():
        d = json.loads(Path(f"out/v3/reanalysis_{name}.json").read_text())
        node = d
        for k in rec["artifact_path"]:
            node = node[k]
        if node["delta_log_loss"]["point"] != rec["point"]:
            _fail(f"{name}: recorded point {rec['point']} is not what its own recorded "
                  f"artifact_path contains")
    if doc["delta"]["value"] != round(min(pts), 4):
        _fail(f"delta {doc['delta']['value']} != min conclusive margin {round(min(pts), 4)}")
    notes.append(f"delta {doc['delta']['value']} cross-checked against REQUEST.md and "
                 f"each margin's own artifact path")
    return notes


def check_power(doc: dict) -> list[str]:
    """Recompute the power arithmetic from first principles."""
    z = 1.959963985 + 0.8416212336
    p = doc["power"]
    delta = doc["delta"]["value"]
    sd_hi = p["sd_items_observed"]["max"]
    n = doc["dataset"]["n_items"]
    want_n = math.ceil((z ** 2) * (sd_hi ** 2) / (delta ** 2))
    got = p["primary"]["M=5"]["required_n_at_sd_max"]
    if got != want_n:
        _fail(f"power: required n at sd_max is {got}, recomputed {want_n}")
    want_d = round(z * sd_hi / math.sqrt(n), 4)
    got_d = p["dose_response_increment"]["detectable_at_registered_n"]
    if got_d != want_d:
        _fail(f"power: detectable increment {got_d}, recomputed {want_d}")
    sds = [v["sd_items"] for v in doc["measured_margins_slice1"].values()
           if v.get("decision") == "go"]
    if round(max(sds), 4) != round(sd_hi, 4):
        _fail(f"power: sd_max {sd_hi} is not the max over conclusive cycles {max(sds)}")
    return [f"power recomputed: n>={want_n}, dose floor {want_d}"]


def check_cost(doc: dict) -> list[str]:
    """The cost model must satisfy its own arithmetic identities."""
    c = doc["cost"]
    n = doc["dataset"]["n_items"]
    tok = c["token_projection"]
    for label, panel in c["panels"].items():
        members = panel["per_member"]
        if panel["calls"] != n * len(members):
            _fail(f"cost {label}: calls {panel['calls']} != {n} x {len(members)} members")
        total = 0.0
        for agent, rec in members.items():
            if "rate_in" not in rec:
                if rec["usd"] != 0.0:
                    _fail(f"cost {label}/{agent}: unmetered tier priced at {rec['usd']}")
                continue
            want = round(n * (tok["prompt_tokens_per_call"] * rec["rate_in"]
                              + tok["completion_tokens_per_call"] * rec["rate_out"]) / 1e6, 2)
            if abs(want - rec["usd"]) > 0.02:
                _fail(f"cost {label}/{agent}: {rec['usd']} != recomputed {want}")
            total += rec["usd"]
        if abs(round(total, 2) - panel["usd"]) > 0.02:
            _fail(f"cost {label}: member sum {round(total,2)} != panel usd {panel['usd']}")
        cap = c["hard_cap"]["per_panel_cumulative_calls"][label]
        if cap < panel["calls"]:
            _fail(f"cost {label}: call cap {cap} is below the registered volume {panel['calls']}")
    auth = c["authorised_volume"]
    if auth["calls"] != n * len(doc["panels"]["members"]):
        _fail("cost: authorised volume is not n_items x all registered families")
    if auth["usd_estimated_worst_case"] > c["hard_cap"]["run_total_usd"]:
        _fail(f"cost: worst case {auth['usd_estimated_worst_case']} exceeds the authorised "
              f"cap {c['hard_cap']['run_total_usd']}")
    if not c["contingencies"]:
        _fail("cost: no contingencies priced")
    return [f"cost arithmetic recomputed; worst case "
            f"${auth['usd_estimated_worst_case']} within ${c['hard_cap']['run_total_usd']}"]


def check_required_fields(doc: dict) -> list[str]:
    """EXPERIMENT.md 3.1(4) content must be PRESENT, not merely labelled."""
    missing = []
    if not doc.get("wct_definitions") or len(doc["wct_definitions"]) < 3:
        missing.append("WCT-U/WCT-EM/WCT-C definitions")
    if not doc.get("m0_simulation_grid", {}).get("sha256"):
        missing.append("M0 simulation grid pinned by hash")
    roles = doc.get("generation", {}).get("roles")
    if not isinstance(roles, dict) or not roles.get("prompts"):
        missing.append("pinned role prompts (a label is not a pin)")
    if not doc.get("arms"):
        missing.append("arm list")
    for k in ("exclusions", "analysis_splits", "estimand", "delta"):
        if not doc.get(k):
            missing.append(k)
    if missing:
        _fail(f"EXPERIMENT.md 3.1(4) content missing: {missing}")
    return ["3.1(4) content present"]


def check_subsets(doc: dict) -> list[str]:
    s = {k: set(v) for k, v in doc["panels"]["nested_subsets"].items()}
    if not (s["M=3"] < s["M=4"] < s["M=5"]):
        _fail("panel subsets are not nested")
    ranks = [m["rank"] for m in doc["panels"]["members"]]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        _fail("panel ranks are not a contiguous ordering")
    if doc["panels"]["declared_margin"]["rank"] in s["M=5"]:
        _fail("the declared margin is inside the primary M=5 panel")
    return ["panel ordering and nesting verified"]


def check_adjudication_matches_the_driver(doc: dict) -> list[str]:
    """The registration and the committed driver must implement the SAME rule.

    "The implementations ARE the registration" only holds if the two agree. A yaml that
    says one thing while run_cycle3 does another leaves a reader unable to tell which was
    applied -- and the yaml is what a replicator reads.
    """
    import inspect

    from exp3 import run_cycle3

    dr = inspect.getsource(run_cycle3.dose_response)
    pv = inspect.getsource(run_cycle3.primary_verdict)
    p2 = doc["predictions"]["P2_dose_response"]

    if "non-decreasing at every step" in p2["supports"]:
        if "and monotone" not in dr:
            _fail("P2 registers monotonicity as necessary for support, but "
                  "dose_response does not require it")
    elif "and monotone" in dr:
        _fail("dose_response requires monotonicity for support, but P2 does not register it")

    if "lo > floor" not in dr.replace("lo > floor", "lo > floor"):
        pass
    for needle, where in (("hi < floor", "refutes"), ("lo > floor", "supports")):
        if needle not in dr:
            _fail(f"dose_response does not implement the registered {where} rule")

    pa = doc.get("primary_adjudication", {})
    if pa.get("map") != "platt":
        _fail("the registered primary map is not the one the driver reads")
    if "FROZEN_DELTA" not in pv:
        _fail("primary_verdict does not acknowledge wct3.arms' frozen delta, so it may be "
              "silently adjudicating at 0.02 instead of the registered delta")
    if str(pa.get("arms_frozen_delta")) != "0.02":
        _fail("the registration does not record arms' frozen delta, so a reader cannot "
              "tell which threshold was applied")

    caps = doc["cost"]["hard_cap"]
    if any(v > caps["run_total_calls"] for v in caps["per_panel_cumulative_calls"].values()):
        _fail("a per-panel call cap exceeds the authorised run total, so it is not a cap")
    return ["registration and driver implement the same adjudication"]


def validate(path: Path = PREREG) -> list[str]:
    doc = yaml.safe_load(path.read_text())
    notes: list[str] = []
    for fn in (check_required_fields, check_subsets, check_adjudication_matches_the_driver,
               check_margins_against_request, check_power, check_cost, check_corpus):
        notes.extend(fn(doc))
    return notes


if __name__ == "__main__":
    import sys
    try:
        for n in validate():
            print(f"  OK  {n}")
    except ValidationError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    print("independent validation passed")
