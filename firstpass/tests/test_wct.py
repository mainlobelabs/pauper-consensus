"""Unit tests for the inference-free parts of the pipeline.

These run with no server and no API calls, so they can gate every commit. The
statistical behaviour of the estimators is checked separately against simulated
ground truth in m0/simulate.py; what is tested here is the machinery those
checks rely on being correct.
"""
from __future__ import annotations

import numpy as np
import pytest

from wct import aggregate as agg
from wct import cache, stats
from wct.extract import answer_of, extract
from wct.schema import Generation, Item, Proposition


# --------------------------------------------------------------- cache
def test_cache_is_write_once(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)
    k = cache.cache_key(a=1)
    cache.put("ns", k, {"v": 1})
    cache.put("ns", k, {"v": 1})            # identical rewrite is a no-op
    with pytest.raises(cache.CacheConflict):
        cache.put("ns", k, {"v": 2})        # divergent rewrite must fail loudly


def test_cache_key_covers_every_generation_parameter():
    base = dict(item="i", model="m", role="r", prompt="p", seed=1, temperature=0.7)
    k = cache.cache_key(**base)
    for field, other in [("model", "m2"), ("role", "r2"), ("prompt", "p2"),
                         ("seed", 2), ("temperature", 0.8)]:
        assert cache.cache_key(**{**base, field: other}) != k, field


# ----------------------------------------------------------- aggregation
def _V(rows):
    return np.array(rows, dtype=np.int8)


def test_wct_u_ignores_missing_and_signs_correctly():
    V = _V([[1, 1, 0], [1, -1, 0], [-1, -1, -1]])
    assert list(agg.wct_u(V)) == [2.0, 0.0, -3.0]


def test_one_vote_cap_is_what_makes_duplication_harmless():
    V = _V([[1, -1, -1]])
    dup = np.hstack([V, V[:, [0]], V[:, [0]]])   # agent 0 repeated
    assert agg.wct_u(V)[0] == -1.0
    assert agg.wct_u(dup)[0] == 1.0              # uncapped, verbosity flips it
    assert agg.wct_u(dup[:, :3])[0] == -1.0      # capped, it does not


def test_em_recovers_truth_on_a_clean_panel():
    rng = np.random.default_rng(0)
    y = (rng.random(600) < 0.5).astype(int)
    V = np.where(rng.random((600, 5)) < 0.85,
                 np.where(y[:, None] == 1, 1, -1),
                 np.where(y[:, None] == 1, -1, 1)).astype(np.int8)
    q, p = agg.wct_em(V)
    assert ((q > 0.5).astype(int) == y).mean() > 0.95
    assert p.sens.mean() > 0.7 and p.fpr.mean() < 0.3


def test_em_estimates_per_agent_reliability_without_labels():
    """The heterogeneous case D9 is about: a strong agent and a coin-flip agent."""
    rng = np.random.default_rng(3)
    y = (rng.random(1500) < 0.5).astype(int)
    truth = np.where(y == 1, 1, -1)
    good = np.where(rng.random(1500) < 0.95, truth, -truth)
    bad = np.where(rng.random(1500) < 0.52, truth, -truth)
    V = np.stack([good, good, bad], 1).astype(np.int8)
    _, p = agg.wct_em(V)
    informative = p.sens - p.fpr          # 0 for a useless source, high for a good one
    assert informative[0] > informative[2] + 0.3


def test_silence_is_not_a_denial():
    V_missing = _V([[1, 0, 0]])
    V_denied = _V([[1, -1, -1]])
    assert agg.wct_u(V_missing)[0] == 1.0
    assert agg.wct_u(V_denied)[0] == -1.0


def test_temperature_is_monotone_so_ranking_is_untouched():
    rng = np.random.default_rng(1)
    s = rng.normal(size=400) * 3
    y = (rng.random(400) < agg.sigmoid(s)).astype(int)
    t = agg.fit_temperature(s, y)
    assert t > 0
    assert np.array_equal(np.argsort(s), np.argsort(s / t))


def test_auroc_matches_known_values_and_handles_ties():
    assert agg.auroc(np.array([1.0, 2, 3, 4]), np.array([0, 0, 1, 1])) == 1.0
    assert agg.auroc(np.array([4.0, 3, 2, 1]), np.array([0, 0, 1, 1])) == 0.0
    assert agg.auroc(np.array([1.0, 1, 1, 1]), np.array([0, 0, 1, 1])) == 0.5
    assert agg.auroc(np.array([1.0, 2]), np.array([1, 1])) is None


# ------------------------------------------------------------- statistics
def test_bootstrap_resamples_whole_items_not_rows():
    ids = ["a"] * 50 + ["b"] * 50
    seen = []
    stats.item_bootstrap(ids, lambda rows: seen.append(sorted(set(
        ids[r] for r in rows))) or 1.0, n_boot=30)
    # every resample is built from whole items, so a resample can only ever
    # contain items, never a fraction of one
    assert all(set(s) <= {"a", "b"} for s in seen)


def test_permutation_null_is_centred_at_chance():
    rng = np.random.default_rng(5)
    ids = [f"i{i // 10}" for i in range(400)]
    y = (rng.random(400) < 0.5).astype(int)
    r = stats.within_item_permutation(
        ids, rng.normal(size=400), y, lambda s, yy: agg.auroc(s, yy), n_perm=200)
    assert abs(r["null_mean"] - 0.5) < 0.03
    assert r["p"] > 0.01          # pure noise must not be significant


def test_permutation_p_value_is_never_zero():
    ids = ["i0"] * 20
    y = np.array([0] * 10 + [1] * 10)
    r = stats.within_item_permutation(
        ids, y.astype(float), y, lambda s, yy: agg.auroc(s, yy), n_perm=50)
    assert r["p"] > 0


def test_m_eff_matches_the_kish_design_effect():
    rng = np.random.default_rng(2)
    correct = rng.random((4000, 4)) < 0.7          # independent sources
    d = stats.error_correlation(correct)
    assert abs(d["rho"]) < 0.05
    assert d["m_eff"] > 3.5                        # ~4 independent votes
    shared = rng.random((4000, 1)) < 0.7
    dep = stats.error_correlation(np.repeat(shared, 4, axis=1))
    assert dep["rho"] > 0.95 and dep["m_eff"] < 1.2   # one vote, four times


def test_decision_rule_separates_stop_from_inconclusive():
    assert stats.decision({"point": 0.10, "lo": 0.05, "hi": 0.15}, 0.02) == "go"
    assert stats.decision({"point": 0.001, "lo": -0.002, "hi": 0.004}, 0.02) == "stop"
    # CI includes zero but is wide: absence of evidence, not evidence of absence
    assert stats.decision({"point": 0.03, "lo": -0.01, "hi": 0.09}, 0.02) == "inconclusive"


# ------------------------------------------------------------- extraction
def _item():
    props = (
        Proposition("p1", "The mouse sees the bald eagle.",
                    '("mouse" "sees" "bald eagle" "+")', "True", 0, ""),
        Proposition("p2", "The mouse does not see the bald eagle.",
                    '("mouse" "sees" "bald eagle" "-")', "False", 0, ""),
    )
    return Item("i1", "The mouse sees the bald eagle.", "The mouse is cold.",
                "True", 2, "formal", props)


def _gen(text):
    return Generation("i1", "a", "m", "neutral", text, "", 1, 0.7)


def test_extractor_drops_narration_but_keeps_claims():
    g = _gen("The user wants me to determine the answer.\n"
             "The mouse sees the bald eagle.\n"
             "Let me check the rules.")
    texts = [c.text for c in extract(g, _item())]
    assert texts == ["The mouse sees the bald eagle"]   # _clean strips terminal punctuation


def test_extractor_caps_verbatim_repetition_within_an_agent():
    g = _gen("The mouse sees the bald eagle. The mouse sees the bald eagle.")
    assert len(extract(g, _item())) == 1


def test_answer_parsing_takes_the_final_verdict():
    assert answer_of(_gen("ANSWER: False\nwait\nANSWER: True")) == "True"
    assert answer_of(_gen("no verdict here")) is None
