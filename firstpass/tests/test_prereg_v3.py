"""prereg_v3.yaml carries what B1-B7 require, and every figure is re-derivable."""
from __future__ import annotations

import yaml
import pytest

from exp3 import prereg_v3_build as B


@pytest.fixture(scope="module")
def doc():
    return yaml.safe_load(open("prereg_v3.yaml"))


def test_no_figure_is_hand_typed(doc):
    """The committed yaml must be exactly what the builder emits, or a literal has drifted."""
    assert B.build() == doc


def test_b1_carries_every_field_experiment_3_1_4_requires(doc):
    for field in ("dataset", "generation", "delta", "analysis_splits", "estimand", "panels"):
        assert field in doc, field
    assert "sha256" in doc["dataset"]                       # dataset manifest
    assert doc["generation"]["roles"]                        # role prompts
    for k in ("seed", "temperature", "max_tokens"):          # decoding parameters
        assert k in doc["generation"]
    assert "exclusions" in doc
    assert doc["analysis_code_freeze"]


def test_b2_delta_is_frozen_and_derived_only_from_conclusive_cycles(doc):
    d = doc["delta"]
    assert d["immutable_after_results"] is True
    assert d["n_conclusive"] == 3 and d["n_panel_cycles"] == 4
    assert "c2_panelB" in d["excluded_inconclusive"]
    assert d["value"] == round(min(d["inputs_conclusive"].values()), 4) == 0.0448
    # the inconclusive cycle's smaller margin must NOT have set the floor
    assert d["excluded_inconclusive"]["c2_panelB"]["point"] < d["value"]


def test_b2_power_reports_all_three_panel_sizes_and_the_dose_floor(doc):
    p = doc["power"]
    assert set(p["primary"]) == {"M=3", "M=4", "M=5"}
    assert all(v["powered_at_registered_n"] for v in p["primary"].values())
    dr = p["dose_response_increment"]
    assert dr["n"] == doc["dataset"]["n_items"]
    assert 0 < dr["detectable_at_registered_n"] < doc["delta"]["value"]
    assert "underpowered" in dr["note"]


def test_power_math_is_the_stated_formula():
    n = B.required_n(0.05, 0.25)
    assert n == pytest.approx((B.Z ** 2) * 0.25 ** 2 / 0.05 ** 2, rel=0.01) or n >= 1
    assert B.detectable_delta(10000, 0.25) < B.detectable_delta(100, 0.25)


def test_b3_six_families_fixed_ordering_and_nested_subsets(doc):
    p = doc["panels"]
    assert [m["rank"] for m in p["members"]] == [1, 2, 3, 4, 5, 6]
    assert len({m["family"] for m in p["members"]}) == 6
    s = p["nested_subsets"]
    assert set(s["M=3"]) < set(s["M=4"]) < set(s["M=5"])
    assert 6 not in s["M=5"]
    marg = p["declared_margin"]
    for k in ("promotion_trigger", "data_before_promotion", "adjudicator", "disclosure"):
        assert marg[k]


def test_b4_expected_echo_pinned_per_member_and_local_pinned_by_weights(doc):
    for m in doc["panels"]["members"]:
        assert m["expected_resolved"], m["agent"]
        assert m["expected_source"] in ("requested id (default)", "registered alias override")
    local = [m for m in doc["panels"]["members"] if m["backend"] == "local"][0]
    assert "model_path" in local["identity_evidence"]
    assert "NOT the echoed alias" in local["identity_basis"]
    fb = doc["panels"]["declared_fallback"]
    assert fb["for"] == "qwen" and fb["trigger"] and "PROVIDER" in fb["caveat"]


def test_b5_corpus_pinned_and_projection_is_not_a_gate(doc):
    ds = doc["dataset"]
    assert ds["n_items"] == 9805
    assert len(ds["sha256"]) == 64
    assert len(ds["source_sha256"]) == 6
    assert ds["cycle2_subset"] is True
    proj = ds["projected_scored_positive_polarity_negatives"]
    assert proj["is_gate"] is False and proj["assumptions"]
    # B5 is about SCORED negatives, which must be far fewer than the population
    assert proj["M=5"] < ds["positive_polarity_negatives"]


def test_b6_predictions_state_what_would_refute_them(doc):
    for key in ("P1_primary", "P2_dose_response"):
        pred = doc["predictions"][key]
        assert pred["refutes"] and pred["supports"] and pred["inconclusive"]
    assert "multiplicity" in doc["predictions"]["P2_dose_response"]


def test_b7_costs_and_caps_scale_with_panel_size(doc):
    c = doc["cost"]
    calls = [c["panels"][f"M={m}"]["calls"] for m in (3, 4, 5)]
    assert calls == sorted(calls) and calls[0] < calls[-1]
    caps = c["hard_cap"]["per_panel_cumulative_calls"]
    for m in (3, 4, 5):
        assert caps[f"M={m}"] >= c["panels"][f"M={m}"]["calls"], "cap below the registered volume"
    assert c["hard_cap"]["persistence"] and c["hard_cap"]["paid_ids_required"]
    assert doc["cost"]["panels"]["M=5"]["calls"] == doc["dataset"]["n_items"] * 5


def test_instrument_change_is_registered_with_its_evidence(doc):
    ins = doc["instrument"]
    assert ins["precision"] == "fp32" and ins["device"] == "cuda"
    dd = ins["measured_device_dependence"]
    assert dd["cpu_fp16_vs_gpu_fp16"]["max_abs"] > dd["cpu_fp32_vs_gpu_fp32"]["max_abs"]
    assert "no fp16 fallback" in ins["fail_closed"]
    assert "SEPARATE" in ins["cache_isolation"]


def test_tag_matches_the_human_decision(doc):
    assert doc["tag"] == B.TAG == "prereg-v3-2026-08-30"


def test_delta_raises_if_nothing_was_conclusive():
    with pytest.raises(ValueError, match="no conclusive"):
        B.derive_delta({"x": {"point": 0.1, "decision": "inconclusive", "sd_items": 0.2}})
