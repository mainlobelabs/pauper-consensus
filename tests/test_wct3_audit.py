"""The restored audit reproduces cycle 1's committed values (D3)."""
from __future__ import annotations

import json

import pytest

from exp.common import complete_items, load_dataset, load_generations
from wct3 import audit as v3audit
from wct3 import observe

# out/e1_summary.json, cycle-1 local panel, all_items — the committed values
FROZEN_C1_LOCAL = {
    "n_probes": 1483, "accuracy": 0.9724, "wrong_proposition": 41,
    "wrong_polarity": 0, "n_reference": 1460, "n_predicted": 1197,
    "recall_mean": 0.6899, "same_agent_conflicts": 853, "claims": 24621,
    "observations": 1197,
}


@pytest.fixture(scope="module")
def c1_local():
    items, calib, _ = load_dataset()
    cells, _ = load_generations(items, calib, backend="local")
    cell = cells["cross_family_diverse_role"]
    iids = complete_items(cell, min_agents=2)
    rows, agents, audits = observe.build_rows(items, cell, iids)
    return items, iids, audits


def test_reproduces_committed_cycle1_audit(c1_local):
    items, iids, audits = c1_local
    got = v3audit.panel_audit(items, iids, audits)
    committed = json.load(open("out/e1_summary.json"))["strata"]["all_items"]["alignment_audit"]
    assert got["aligner_self_identification"]["n_probes"] == committed["aligner_self_identification"]["n_probes"]
    assert got["aligner_self_identification"]["accuracy"] == committed["aligner_self_identification"]["accuracy"]
    assert got["aligner_self_identification"]["wrong_proposition"] == committed["aligner_self_identification"]["wrong_proposition"]
    assert got["aligner_self_identification"]["wrong_polarity"] == committed["aligner_self_identification"]["wrong_polarity"]
    assert got["lexical_reference"]["recall_mean"] == committed["lexical_reference"]["recall_mean"]
    assert got["lexical_reference"]["n_reference"] == committed["lexical_reference"]["n_reference"]
    assert got["same_agent_conflicts"] == committed["same_agent_conflicts"]
    assert got["claims"] == committed["claims"]
    assert got["observations"] == committed["observations"]


def test_funnel_present_and_invariant_holds(c1_local):
    items, iids, audits = c1_local
    got = v3audit.panel_audit(items, iids, audits)
    f = got["funnel"]
    assert f["observations"] <= f["instances"]
    assert f["instances"] > 0
    assert got["status"] == "POST-HOC"
    assert got["aligner_self_identification"]["status"] == "computed"
