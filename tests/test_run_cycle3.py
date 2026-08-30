"""The cycle-3 driver fails closed on every registered precondition (B8, B12, B13)."""
from __future__ import annotations

import json

from pathlib import Path

import pytest

from exp3 import run_cycle3 as R


@pytest.fixture(scope="module")
def reg():
    return R.load_registration()


# ------------------------------------------------------------------ B13 instrument

def test_no_cuda_fails_closed_rather_than_using_fp16(reg, monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(R.RegistrationError, match="NO\n?\\s*fp16 fallback|fp16 fallback"):
        R.assert_registered_instrument(reg)


def test_missing_torch_fails_closed(reg, monkeypatch):
    import builtins
    real = builtins.__import__
    def no_torch(name, *a, **k):
        if name == "torch":
            raise ImportError("boom")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_torch)
    with pytest.raises(R.RegistrationError, match="torch unavailable"):
        R.assert_registered_instrument(reg)


def test_a_registration_demanding_fp16_is_refused():
    with pytest.raises(R.RegistrationError, match="demands fp32/cuda"):
        R.assert_registered_instrument(
            {"instrument": {"precision": "fp16", "device": "cuda", "nli_model": "x"}})


@pytest.mark.skipif(not __import__("torch").cuda.is_available(), reason="no CUDA device")
def test_with_cuda_the_instrument_is_fp32_and_recorded(reg):
    info = R.assert_registered_instrument(reg)
    assert info["device"].startswith("cuda")
    assert info["precision"] == "fp32"
    assert info["gpu_name"] and info["torch"]


# ------------------------------------------------------------------ cache isolation

def test_frozen_cache_root_is_refused(monkeypatch):
    monkeypatch.setenv("WCT_CACHE", str(R.FROZEN_CACHE))
    with pytest.raises(R.RegistrationError, match="frozen root"):
        R.assert_cache_isolation()


def test_unset_cache_root_is_refused(monkeypatch):
    monkeypatch.delenv("WCT_CACHE", raising=False)
    with pytest.raises(R.RegistrationError, match="WCT_CACHE is unset"):
        R.assert_cache_isolation()


def test_separate_cache_root_is_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("WCT_CACHE", str(tmp_path))
    assert R.assert_cache_isolation() == str(tmp_path.resolve())


# ------------------------------------------------------------------ B8 the tag

def test_missing_tag_blocks_generation(reg, monkeypatch):
    monkeypatch.setattr(R, "_git", lambda *a: "")
    with pytest.raises(R.RegistrationError, match="does not exist"):
        R.assert_tagged(reg)


def test_tag_pointing_at_a_different_tree_blocks_generation(reg, monkeypatch):
    def fake(*a):
        if a[0] == "tag":
            return reg["tag"]
        if a[:2] == ("rev-parse", f"{reg['tag']}^{{tree}}"):
            return "a" * 40
        if a[0] == "rev-parse":
            return "b" * 40
        return ""
    monkeypatch.setattr(R, "_git", fake)
    with pytest.raises(R.RegistrationError, match="not the code that was registered"):
        R.assert_tagged(reg)


def test_uncommitted_registered_code_blocks_generation(reg, monkeypatch):
    def fake(*a):
        if a[0] == "tag":
            return reg["tag"]
        if a[0] == "rev-parse":
            return "c" * 40
        if a[0] == "status":
            return " M exp3/run_cycle3.py"
        return ""
    monkeypatch.setattr(R, "_git", fake)
    with pytest.raises(R.RegistrationError, match="uncommitted changes"):
        R.assert_tagged(reg)


# ------------------------------------------------------------------ B12 scheduling

def test_generation_is_model_major():
    s = R.Scheduler()
    s.begin_generation("qwen")
    with pytest.raises(R.RegistrationError, match="MODEL-MAJOR"):
        s.begin_generation("glm")
    s.end_generation("qwen")
    s.begin_generation("glm")           # only now


def test_no_measurement_during_an_open_generation_pass():
    s = R.Scheduler()
    s.begin_generation("qwen")
    with pytest.raises(R.RegistrationError, match="during an open generation pass"):
        s.guard_measurement()
    with pytest.raises(R.RegistrationError, match="cannot analyse while"):
        s.begin_analysis()


def test_generation_cannot_restart_after_analysis():
    s = R.Scheduler()
    s.begin_generation("qwen"); s.end_generation("qwen"); s.begin_analysis()
    with pytest.raises(R.RegistrationError, match="cannot start after analysis"):
        s.begin_generation("glm")


def test_a_model_cannot_run_two_passes():
    s = R.Scheduler()
    s.begin_generation("qwen"); s.end_generation("qwen")
    with pytest.raises(R.RegistrationError, match="already completed"):
        s.begin_generation("qwen")


# ------------------------------------------------------------------ B7 caps

def test_caps_persist_across_runs(reg, tmp_path):
    p = tmp_path / "caps.json"
    c = R.Caps.load(reg, p)
    start = c.remaining("M=5")
    c.charge("M=5", 10)
    again = R.Caps.load(reg, p)
    assert again.remaining("M=5") == start - 10, "a re-run reset the counter"


def test_cap_breach_aborts(reg, tmp_path):
    c = R.Caps.load(reg, tmp_path / "caps.json")
    c.run_total_calls = None                     # isolate the per-panel cap
    with pytest.raises(R.RegistrationError, match="cumulative CALL cap"):
        c.charge("M=5", c.limits["M=5"] + 1)


def test_run_total_call_authorisation_is_a_ceiling(reg, tmp_path):
    """A per-panel cap above the authorised volume would not be a cap at all."""
    c = R.Caps.load(reg, tmp_path / "caps.json")
    assert c.run_total_calls == 58830
    assert all(v <= c.run_total_calls for v in c.limits.values()), \
        "a per-panel cap exceeds the authorised run total"
    with pytest.raises(R.RegistrationError, match="run-total CALL authorisation"):
        c.charge("M=3", c.run_total_calls + 1)


def test_run_total_call_cap_spans_panels(reg, tmp_path):
    """Spend on one panel must consume the shared authorisation, not sit in a silo."""
    p = tmp_path / "caps.json"
    c = R.Caps.load(reg, p)
    c.charge("M=3", 100)
    c.charge("M=4", 100)
    again = R.Caps.load(reg, p)
    assert sum(again.used.values()) == 200


def test_cap_is_charged_before_the_call(reg, tmp_path):
    """Charging after the call would let a crash re-run for free."""
    p = tmp_path / "caps.json"
    c = R.Caps.load(reg, p)
    c.charge("M=3", 5)
    assert json.loads(p.read_text())["used"]["M=3"] == 5


# ------------------------------------------------------------------ panels + dry run

def test_nested_subsets_are_actually_nested(reg):
    a = {m["agent"] for m in R.panel_members(reg, 3)}
    b = {m["agent"] for m in R.panel_members(reg, 4)}
    c = {m["agent"] for m in R.panel_members(reg, 5)}
    assert a < b < c and len(a) == 3 and len(c) == 5


def test_dry_run_issues_zero_generation_calls(monkeypatch):
    called = []
    monkeypatch.setattr(R, "assert_tagged", lambda r: called.append("tag"))
    out = R.run(dry_run=True)
    assert out["generated"] == 0
    assert called == [], "a dry run must not even check the tag; it issues nothing"
    assert out["planned_calls"] == out["n_items"] * 5, "the union is the largest panel"
    assert out["preflight"]["dry_run"] is True
    assert out["sizes"] == [3, 4, 5]


# ------------------------------------------------------------------ generation workflow

class FakeGen:
    def __init__(self, error=None):
        self.error = error
        self.trace = "step 1: the cat is kind."


class FakeClient:
    """Records every call so scheduling and retry behaviour are observable."""
    calls: list = []
    fail_first_n = 0

    def __init__(self, backend, base_url=None, **k):
        self.backend = backend

    def generate(self, item, agent, model, role, seed, temperature, max_tokens,
                 expected_resolved=None):
        FakeClient.calls.append({"agent": agent, "item": item.item_id, "role": role})
        n = len([c for c in FakeClient.calls if c["item"] == item.item_id
                 and c["agent"] == agent])
        if n <= FakeClient.fail_first_n:
            return FakeGen(error="transient")
        return FakeGen()


class FakeItem:
    def __init__(self, i):
        self.item_id = f"item-{i}"


@pytest.fixture
def fake_gen(monkeypatch):
    FakeClient.calls = []
    FakeClient.fail_first_n = 0
    monkeypatch.setattr("wct.nodes.Client", FakeClient)
    # panel rank 1 is the local endpoint, and generation now re-checks its loaded
    # weights at run time; return the registered path so these tests stay about
    # scheduling and caps rather than about the endpoint being up.
    monkeypatch.setattr(
        "exp3.smoke_v3.local_props",
        lambda *a, **k: {"model_path": "/home/jmannings/.lmstudio/models/unsloth/"
                                       "Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf",
                         "model_ftype": "Q4_K_M", "n_params": None,
                         "n_params_endpoint_verifiable": False})
    return FakeClient


def test_generation_is_model_major_across_the_panel(reg, fake_gen, tmp_path):
    members = R.panel_members(reg, 3)
    items = [FakeItem(i) for i in range(4)]
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    sched = R.Scheduler()
    cell, reports = R.generate_panel(reg, members, items, caps, "M=3", sched)
    order = [c["agent"] for c in fake_gen.calls]
    # each agent's calls must be contiguous: one model completes before the next starts
    seen, blocks = set(), []
    for a in order:
        if not blocks or blocks[-1] != a:
            assert a not in seen, f"{a} resumed after another model ran"
            blocks.append(a); seen.add(a)
    assert len(blocks) == len(members)
    assert len(cell) == len(items)
    assert sched.completed == [m["agent"] for m in members]


def test_every_attempt_including_retries_charges_the_cap(reg, fake_gen, tmp_path):
    fake_gen.fail_first_n = 1                    # each item fails once, then succeeds
    members = R.panel_members(reg, 3)[:1]
    items = [FakeItem(i) for i in range(3)]
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    before = caps.remaining("M=3")
    R.generate_panel(reg, members, items, caps, "M=3", R.Scheduler())
    spent = before - caps.remaining("M=3")
    assert spent == 6, f"3 items x 2 attempts should charge 6, charged {spent}"


def test_retries_are_bounded_and_failures_are_not_cached(reg, fake_gen, tmp_path):
    fake_gen.fail_first_n = 99                   # never succeeds
    members = R.panel_members(reg, 3)[:1]
    items = [FakeItem(i) for i in range(2)]
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    cell, reports = R.generate_panel(reg, members, items, caps, "M=3", R.Scheduler())
    assert cell == {}, "a failing generation must not enter the cell"
    assert reports[0]["n_failed_items"] == 2
    assert len(fake_gen.calls) == 4, "retries must be bounded at max_attempts"


def test_cap_breach_stops_generation(reg, fake_gen, tmp_path):
    members = R.panel_members(reg, 3)[:1]
    items = [FakeItem(i) for i in range(5)]
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    caps.used["M=3"] = caps.limits["M=3"] - 2     # only two calls left
    with pytest.raises(R.RegistrationError, match="cumulative CALL cap"):
        R.generate_panel(reg, members, items, caps, "M=3", R.Scheduler())


# ------------------------------------------------------------------ promotion

AUTH = {"decided_by": "jerry.mannings@gmail.com", "decisions_md_ref": "2026-08-31 entry"}


def test_promotion_without_a_recorded_human_adjudication_is_refused(reg):
    """The registration names the human owner as adjudicator; the machine must not
    substitute a panel member on its own authority."""
    members = R.panel_members(reg, 5)
    with pytest.raises(R.RegistrationError, match="recorded human"):
        R.promote(reg, members, members[2]["agent"], authorisation=None)


def test_an_incomplete_promotion_record_is_refused(reg, tmp_path):
    p = tmp_path / "promotions.json"
    p.write_text(json.dumps({"nemotron": {"decided_by": "someone"}}))   # no DECISIONS ref
    with pytest.raises(R.RegistrationError, match="incomplete"):
        R.promotion_authorised("nemotron", p)


def test_a_complete_promotion_record_is_accepted(reg, tmp_path):
    p = tmp_path / "promotions.json"
    p.write_text(json.dumps({"nemotron": AUTH}))
    assert R.promotion_authorised("nemotron", p)["decided_by"] == AUTH["decided_by"]
    assert R.promotion_authorised("gemma", p) is None


def test_margin_is_promoted_into_the_vacated_rank(reg):
    members = R.panel_members(reg, 5)
    failed = members[2]["agent"]
    promoted, event = R.promote(reg, members, failed, authorisation=AUTH)
    assert event["adjudicated_by"] == AUTH["decided_by"]
    assert event["decisions_md_ref"] == AUTH["decisions_md_ref"]
    assert event["promoted"] == R.margin_member(reg)["agent"]
    assert event["vacated"] == failed
    assert [m["rank"] for m in promoted] == [m["rank"] for m in members]
    assert failed not in {m["agent"] for m in promoted}
    assert "retained" in event["prior_data"]


def test_promoting_an_agent_not_in_the_panel_is_refused(reg):
    with pytest.raises(R.RegistrationError, match="not in this panel"):
        R.promote(reg, R.panel_members(reg, 3), "nobody", authorisation=AUTH)


def test_no_reserve_left_is_refused(reg):
    members = R.panel_members(reg, 5) + [R.margin_member(reg)]
    with pytest.raises(R.RegistrationError, match="no reserve left"):
        R.promote(reg, members, members[0]["agent"], authorisation=AUTH)


def test_qwen_declares_a_fallback(reg):
    assert R.fallback_for(reg, "qwen") is not None
    assert R.fallback_for(reg, "glm") is None


# ------------------------------------------------------------------ dose response

def _margins(vals_by_m, n=400, spread=0.02, seed=0):
    """Synthetic per-item margins with a known mean, for adjudication tests."""
    import numpy as np
    rng = np.random.default_rng(seed)
    ids = [f"i{k}" for k in range(n)]
    return {m: {"margin": rng.normal(v, spread, n), "item_ids": ids,
                "selected_single": "x", "map": "platt"}
            for m, v in vals_by_m.items()}


def test_dose_response_supports_when_the_ci_clears_the_floor():
    d = R.dose_response(_margins({3: 0.02, 5: 0.10}), floor=0.0071, n_boot=300)
    assert d["verdict"] == "supports"
    assert d["ci"]["lo"] > d["detectable_floor"]
    assert d["monotone_increasing"] is True


def test_dose_response_refutes_when_the_ci_is_below_the_floor():
    d = R.dose_response(_margins({3: 0.06, 5: 0.06}, spread=0.005), floor=0.05, n_boot=300)
    assert d["verdict"] == "refutes"
    assert d["ci"]["hi"] < d["detectable_floor"]


def test_dose_response_inconclusive_when_the_ci_spans_the_floor():
    d = R.dose_response(_margins({3: 0.05, 5: 0.058}, spread=0.08), floor=0.0071, n_boot=300)
    assert d["verdict"] == "inconclusive"
    assert d["ci"]["lo"] <= d["detectable_floor"] <= d["ci"]["hi"]


def test_the_three_verdicts_are_mutually_exclusive():
    """lo > floor and hi < floor cannot both hold, so exactly one verdict applies."""
    for vals, spread, floor in (({3: 0.02, 5: 0.10}, 0.02, 0.0071),
                                ({3: 0.06, 5: 0.06}, 0.005, 0.05),
                                ({3: 0.05, 5: 0.058}, 0.08, 0.0071)):
        d = R.dose_response(_margins(vals, spread=spread), floor=floor, n_boot=300)
        lo, hi = d["ci"]["lo"], d["ci"]["hi"]
        assert lo <= hi
        assert sum([lo > floor, hi < floor]) <= 1, "two verdicts fired at once"
        assert d["verdict"] in {"supports", "refutes", "inconclusive"}
    assert d["adjudication"]["mutually_exclusive"] is True


def test_monotonicity_is_reported_but_not_part_of_the_verdict():
    d = R.dose_response(_margins({3: 0.10, 5: 0.02}), floor=0.0071, n_boot=300)
    assert d["monotone_increasing"] is False
    assert d["verdict"] == "refutes"          # decided by the CI, not by monotonicity


def test_dose_response_uses_the_item_block_bootstrap():
    d = R.dose_response(_margins({3: 0.02, 5: 0.10}), floor=0.0071, n_boot=300)
    assert d["ci"]["n_boot"] > 0 and d["ci"]["alpha"] == 0.05
    assert d["n_shared_items"] == 400


# ------------------------------------------------------------------ dollar caps (B7)

def test_dollar_cap_is_enforced_not_just_calls(reg, tmp_path):
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    paid = next(a for a in caps.rates)
    assert caps.price(paid) > 0, "a metered agent must have a nonzero per-call price"
    caps.usd_limits[list(caps.usd_limits)[0]] = 0.0001
    panel = list(caps.usd_limits)[0]
    with pytest.raises(R.RegistrationError, match="USD cap"):
        caps.charge(panel, 1, agent=paid)


def test_run_total_usd_authorisation_is_enforced(reg, tmp_path):
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    paid = next(a for a in caps.rates)
    caps.run_total_usd = 0.0001
    for p in caps.usd_limits:
        caps.usd_limits[p] = 1e9
    with pytest.raises(R.RegistrationError, match="run-total USD authorisation"):
        caps.charge("M=3", 1, agent=paid)


def test_usd_spend_persists_across_runs(reg, tmp_path):
    p = tmp_path / "caps.json"
    caps = R.Caps.load(reg, p)
    paid = next(a for a in caps.rates)
    caps.charge("M=3", 2, agent=paid)
    again = R.Caps.load(reg, p)
    assert again.usd_used["M=3"] == pytest.approx(caps.usd_used["M=3"])
    assert again.usd_used["M=3"] > 0


def test_unmetered_tier_costs_nothing(reg, tmp_path):
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    assert caps.price("qwen") == 0.0
    caps.charge("M=3", 1, agent="qwen")
    assert caps.usd_used.get("M=3", 0.0) == 0.0


# ------------------------------------------------------------------ latin square

def test_roles_rotate_across_models_not_just_items(reg, fake_gen, tmp_path):
    members = R.panel_members(reg, 3)
    items = [FakeItem(i) for i in range(4)]
    caps = R.Caps.load(reg, tmp_path / "caps.json")
    R.generate_panel(reg, members, items, caps, "M=3", R.Scheduler())
    by_item = {}
    for c in fake_gen.calls:
        by_item.setdefault(c["item"], set()).add(c["role"])
    assert any(len(v) > 1 for v in by_item.values()), \
        "every model got the same role on an item: role is confounded with item"


def test_missing_registration_is_an_error(tmp_path):
    with pytest.raises(R.RegistrationError, match="is missing"):
        R.load_registration(tmp_path / "nope.yaml")


# ------------------------------------------------------------------ per-item aggregation

def test_dose_response_averages_propositions_within_an_item():
    """per_item_margin is proposition-level; ids repeat. Weighting by proposition count,
    or keeping only the last proposition per item, are both wrong for an item-level estimand."""
    import numpy as np
    # item A has 3 propositions (last one an outlier), item B has 1
    lo = {"margin": np.array([0.0, 0.0, 0.0, 0.0]),
          "item_ids": ["A", "A", "A", "B"], "selected_single": "x", "map": "platt"}
    hi = {"margin": np.array([0.10, 0.10, 1.00, 0.10]),
          "item_ids": ["A", "A", "A", "B"], "selected_single": "x", "map": "platt"}
    d = R.dose_response({3: lo, 5: hi}, floor=0.0, n_boot=200)
    # A's mean is (0.10+0.10+1.00)/3 = 0.40, B's is 0.10 -> increment mean = 0.25
    assert d["increment"] == pytest.approx(0.25, abs=1e-9)
    assert d["n_shared_items"] == 2, "items, not propositions"
    # last-proposition indexing would give (1.00 + 0.10)/2 = 0.55
    assert d["increment"] != pytest.approx(0.55, abs=1e-9)


# ------------------------------------------------------------------ registered delta

def _contrast(point, lo, hi):
    return {"panel_vs_single_best_calibration_selected": {"platt": {"WCT-EM": {
        "delta_log_loss": {"point": point, "lo": lo, "hi": hi}}}}}


def test_primary_is_adjudicated_at_the_registered_delta_not_arms_frozen_002():
    """A CI clearing 0.02 but not 0.0448 must NOT count as support."""
    from wct3.arms import FROZEN_DELTA
    assert FROZEN_DELTA == 0.02, "this test exists because arms is frozen at 0.02"
    res = _contrast(0.035, 0.025, 0.045)
    v = R.primary_verdict(res, delta=0.0448, mapname="platt")
    assert v["verdict"] == "inconclusive"
    assert v["delta_applied"] == 0.0448
    # the same interval WOULD have supported at arms' frozen delta
    assert R.primary_verdict(res, delta=0.02, mapname="platt")["verdict"] == "supports"


def test_primary_verdicts_are_mutually_exclusive():
    for point, lo, hi in ((0.09, 0.06, 0.12), (0.01, 0.00, 0.02), (0.05, 0.01, 0.09)):
        v = R.primary_verdict(_contrast(point, lo, hi), delta=0.0448, mapname="platt")
        assert v["verdict"] in {"supports", "refutes", "inconclusive"}
        assert sum([lo > 0.0448, hi < 0.0448]) <= 1


# ------------------------------------------------------------------ panel size means panel size

def test_an_M5_result_requires_five_sources(reg, fake_gen, tmp_path, monkeypatch):
    """min_agents=2 would let an 'M=5' item rest on two sources -- the very quantity
    the dose-response varies."""
    import inspect
    src = inspect.getsource(R.run)
    assert "min_agents=m" in src, "analysis must require the full panel"
    assert "len(ags) >= m" in src, "subset filter must require the full panel"


# ------------------------------------------------------------------ contingencies execute

def test_fallback_generates_the_replacement_and_reaches_the_cell(reg, fake_gen, tmp_path,
                                                                 monkeypatch):
    """A recorded contingency that never generates leaves the panel a source short."""
    import inspect
    src = inspect.getsource(R.run)
    assert "generate_member(reg, repl" in src, "the replacement is never generated"
    assert "cell.setdefault(iid, {})[repl" in src, "replacement never reaches the cell"
    assert "substitutions" in src, "subset filtering must follow substitutions"


def test_latin_square_comes_from_the_frozen_helper(reg):
    import inspect
    from wct import nodes
    src = inspect.getsource(R.generate_member)
    assert "nodes.latin_square" in src, "the registered schedule names wct.nodes.latin_square"
    roles = ["forward", "backward", "skeptic"]
    a = nodes.latin_square(["x", "y", "z"], roles, 0)
    assert len(set(a.values())) == 3, "each agent gets a distinct role at a given index"


# ------------------------------------------------------------------ runtime identity

def test_local_weights_are_checked_at_run_time_not_just_at_smoke(monkeypatch):
    """The single-slot local server can be restarted with different weights between
    smoke and generation, so the pin must be re-checked before generating."""
    member = {"agent": "qwen", "backend": "local", "base": "http://127.0.0.1:8083/v1",
              "identity_evidence": "model_path /models/Qwen3.8-27B-Q4_K_M.gguf"}
    monkeypatch.setattr("exp3.smoke_v3.local_props",
                        lambda *a, **k: {"model_path": "/models/something-else.gguf"})
    with pytest.raises(R.RegistrationError, match="are not the registered"):
        R.assert_local_identity(member)


def test_unreadable_local_props_refuses_to_generate(monkeypatch):
    member = {"agent": "qwen", "backend": "local", "base": "http://127.0.0.1:8083/v1",
              "identity_evidence": "model_path /models/Qwen3.8-27B-Q4_K_M.gguf"}
    monkeypatch.setattr("exp3.smoke_v3.local_props", lambda *a, **k: {})
    with pytest.raises(R.RegistrationError, match="could not be read"):
        R.assert_local_identity(member)


def test_matching_local_weights_pass(monkeypatch):
    member = {"agent": "qwen", "backend": "local", "base": "http://127.0.0.1:8083/v1",
              "identity_evidence": "model_path /models/Qwen3.8-27B-Q4_K_M.gguf"}
    monkeypatch.setattr("exp3.smoke_v3.local_props",
                        lambda *a, **k: {"model_path": "/models/Qwen3.8-27B-Q4_K_M.gguf"})
    assert R.assert_local_identity(member)["model_path"].endswith("Q4_K_M.gguf")


def test_remote_members_skip_the_local_check():
    assert R.assert_local_identity({"agent": "glm", "backend": "openrouter"}) is None


def test_the_primary_map_comes_from_the_registration_not_the_code(reg):
    assert reg["primary_adjudication"]["map"] == "platt"
    import inspect
    src = inspect.getsource(R.run)
    assert 'reg.get("primary_adjudication", {}).get("map")' in src
    assert 'mapname = "platt"' not in src, "the map must not be hard-coded in the driver"


def test_weight_mismatch_triggers_the_declared_fallback_rather_than_aborting(reg):
    """The registered trigger is 'unreachable OR weights mismatch'. Raising inside
    generation would abort the run and make that trigger unreachable."""
    import inspect
    src = inspect.getsource(R.run)
    assert "assert_local_identity(m)" in src, "identity must be checked BEFORE generating"
    assert "fallback_for(reg, m[\"agent\"])" in src, "a mismatch must consult the fallback"
    assert "weights mismatch" in src
    gen = inspect.getsource(R.generate_member)
    assert "assert_local_identity" not in gen, \
        "checking inside generation aborts instead of triggering the fallback"


def test_dose_response_requires_growth_at_every_step_for_support():
    """A dip at M=4 that recovers at M=5 contradicts 'grows through M=3 -> M=4 -> M=5'."""
    dip = {3: _margins({3: 0.02}, seed=1)[3],
           4: _margins({4: 0.00}, seed=2)[4],
           5: _margins({5: 0.12}, seed=3)[5]}
    d = R.dose_response(dip, floor=0.0071, n_boot=300)
    assert d["ci"]["lo"] > d["detectable_floor"], "endpoint contrast does clear the floor"
    assert d["monotone_increasing"] is False
    assert d["verdict"] == "inconclusive", "a non-monotone rise must not read as support"
    assert any(not s["non_decreasing"] for s in d["steps"])


def test_smooth_growth_through_every_step_supports():
    grow = {3: _margins({3: 0.02}, seed=1)[3],
            4: _margins({4: 0.06}, seed=2)[4],
            5: _margins({5: 0.12}, seed=3)[5]}
    d = R.dose_response(grow, floor=0.0071, n_boot=300)
    assert d["monotone_increasing"] is True
    assert d["verdict"] == "supports"
    assert all(s["non_decreasing"] for s in d["steps"])
