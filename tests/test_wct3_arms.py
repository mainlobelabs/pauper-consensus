"""Arms reproduce the frozen values and add the two corrections."""
from __future__ import annotations

import json

import numpy as np
import pytest

from exp.common import complete_items
from exp.run_generate_v2 import load_cell_v2
from exp.v2_dataset import load_v2_items
from wct3 import arms as v3arms
from wct3 import observe


@pytest.fixture(scope="module")
def panelA():
    items, calib, _ = load_v2_items()
    cell, _ = load_cell_v2(items, "panelA")
    iids = complete_items(cell, min_agents=2)
    rows, agents, audits = observe.build_rows(items, cell, iids)
    y, V, riids, X = observe.to_arrays(rows, agents)
    is_calib = np.array([i in calib for i in riids])
    u, s = observe.instance_arrays(rows)
    return v3arms.analyse(rows, agents, y, V, riids, X, is_calib, u, s)


@pytest.fixture(scope="module")
def committed():
    return json.load(open("out/e1_v2_summary_panelA.json"))["strata"]["all_items"]["instrument_primary"]


def test_frozen_score_arms_reproduce_exactly(panelA, committed):
    """Serialized precision, exact equality — no tolerance (the bootstraps are
    seeded at default_rng(20260807) and the summaries store rounded values)."""
    for name in ("WCT-U", "WCT-EM", "WCT-C"):
        assert panelA["arms"][name]["platt"]["test_log_loss"] == committed["arms"][name]["test_log_loss"], name
        assert panelA["arms"][name]["platt"]["test_auroc"] == committed["arms"][name]["test_auroc"], name
        assert panelA["arms"][name]["platt_params"] == committed["arms"][name]["platt_params"], name
        assert panelA["arms"][name]["temperature_t"] == committed["arms"][name]["temperature_ablation_t"], name


def test_frozen_uncapped_arm_is_the_capped_unsigned_cell(panelA, committed):
    """The frozen 'uncapped' arm reproduces — as capped_unsigned, its real identity."""
    assert panelA["arms"]["capped_unsigned"]["platt"]["test_auroc"] == committed["arms"]["uncapped"]["test_auroc"]
    assert panelA["arms"]["capped_unsigned"]["platt"]["test_log_loss"] == committed["arms"]["uncapped"]["test_log_loss"]


def test_frozen_covariate_and_prevalence_reproduce(panelA, committed):
    assert panelA["arms"]["covariate_frozen"]["platt"]["test_log_loss"] == committed["covariate_test_log_loss"]["gd"]
    assert panelA["arms"]["covariate_frozen_ml"]["platt"]["test_log_loss"] == committed["covariate_test_log_loss"]["ml"]
    assert panelA["arms"]["prevalence_only"]["platt"]["test_log_loss"] == committed["arms"]["prevalence_only"]["test_log_loss"]


def test_frozen_primary_deltas_reproduce(panelA, committed):
    for arm in ("WCT-EM", "WCT-U", "WCT-C"):
        got = panelA["primary_vs_covariate_frozen"]["platt"][arm]["delta_log_loss"]
        exp = committed["primary"][f"{arm}_vs_covariate_gd"]["delta_log_loss"]
        for k in ("point", "lo", "hi"):
            assert round(got[k], 5) == round(exp[k], 5), (arm, k)


def test_single_source_arm_exists_and_is_calibration_selected(panelA):
    root = panelA["single_source"]
    assert set(root["by_map"]) == {"platt", "temperature"}
    for m, ss in root["by_map"].items():
        ll = ss["calibration_log_loss_per_agent"]
        assert ss["calibration_selected"] in ll
        # selection must minimise CALIBRATION loss, not test loss
        assert ll[ss["calibration_selected"]] <= min(ll.values()) + 1e-9, m
        assert f"single:{ss['calibration_selected']}" in panelA["arms"]
    assert panelA["single_best_vs_covariate"]["platt"]["decision"] in ("go", "stop", "inconclusive")


def test_source_selection_is_not_assumed_map_invariant(panelA):
    """The selected source can differ by calibration map (c1_local: temperature
    picks qwen, Platt picks ornith). Selecting under one map and reporting the
    contrast under another silently mixes them; the named rows must agree with
    the per-map selection."""
    for m, ss in panelA["single_source"]["by_map"].items():
        named = panelA["arms"]["single_best_calibration_selected"][m]
        assert named["agent"] == ss["calibration_selected"], m
        assert (named["test_log_loss"]
                == panelA["arms"][f"single:{ss['calibration_selected']}"][m]["test_log_loss"])


def test_panel_vs_single_source_contrast_present(panelA):
    for arm in ("WCT-EM", "WCT-U", "WCT-C"):
        d = panelA["panel_vs_single_best_calibration_selected"]["platt"][arm]
        assert set(d["delta_log_loss"]) >= {"point", "lo", "hi"}
        assert d["decision"] in ("go", "stop", "inconclusive")


def test_m6_2x2_separates_capping_from_polarity(panelA):
    cells = panelA["m6_2x2"]["cells"]
    assert set(cells) == {"capped_signed", "capped_unsigned",
                          "uncapped_signed", "uncapped_unsigned"}
    # the corrected uncapped arm must differ from the frozen (capped) one
    assert cells["uncapped_unsigned"]["raw_auroc"] != cells["capped_unsigned"]["raw_auroc"]
    # polarity carries the effect; capping does not
    assert cells["capped_signed"]["raw_auroc"] > 0.85
    assert cells["uncapped_signed"]["raw_auroc"] > 0.85
    assert cells["capped_unsigned"]["raw_auroc"] < 0.70
    assert cells["uncapped_unsigned"]["raw_auroc"] < 0.70


def test_m6_cells_carry_raw_auroc_and_both_maps(panelA):
    """A fitted calibration map may take a NEGATIVE slope on a signal-free arm,
    reversing the ranking and flipping mapped AUROC about 0.5 (c1_local
    capped_unsigned: Platt a=-0.0639, 0.50691 -> 0.49309). raw_auroc is the
    map-independent quantity; both mapped variants are kept so each cycle reads
    the map it registered."""
    for name, c in panelA["m6_2x2"]["cells"].items():
        assert isinstance(c["raw_auroc"], float), name
        assert "platt" in c and "temperature" in c, name
        assert "platt_slope" in c, name


def test_frozen_uncapped_reproduces_under_cycle2s_own_map(panelA, committed):
    """cycle 2 registered Platt, so its frozen uncapped arm must match the
    Platt cell -- the bug this guards against was reading the wrong map."""
    assert (panelA["m6_2x2"]["cells"]["capped_unsigned"]["platt"]["test_auroc"]
            == committed["arms"]["uncapped"]["test_auroc"])
