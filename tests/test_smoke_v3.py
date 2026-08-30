"""exp3.smoke_v3 pins an expected echo per panel member without becoming a data source (B4)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from exp3 import smoke_v3 as S


class FakeResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._p = payload or {}
        self.text = text
    def json(self):
        return self._p


class FakeHTTP:
    """Counts calls, so 'exactly one attempt' is a tested property, not a comment."""
    calls: list = []
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def post(self, url, json=None, headers=None):
        FakeHTTP.calls.append({"url": url, "model": (json or {}).get("model"),
                               "max_tokens": (json or {}).get("max_tokens")})
        return FakeResp(200, {"model": (json or {}).get("model"),
                              "usage": {"total_tokens": 7}})
    def get(self, url):
        return FakeResp(200, {"model_path": "/home/jmannings/.lmstudio/models/unsloth/"
                                            "Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf"})


@pytest.fixture(autouse=True)
def _no_network(monkeypatch, tmp_path):
    import httpx
    FakeHTTP.calls = []
    monkeypatch.setattr(httpx, "Client", FakeHTTP)
    monkeypatch.setattr(S, "SMOKE_DIR", tmp_path / "smoke")
    class FakeClient:
        def __init__(self, backend, timeout=None, base_url=None):
            self.base = base_url or "https://openrouter.ai/api/v1"
            self.key = "sk-secret-value"
    monkeypatch.setattr("wct.nodes.Client", FakeClient)


def test_exactly_one_call_per_endpoint():
    S.run(include_fallback=True)
    assert len(FakeHTTP.calls) == len(S.PANEL) + 1
    models = [c["model"] for c in FakeHTTP.calls]
    assert len(models) == len(set(models)), "an endpoint was probed more than once"


def test_smoke_is_cheap_by_construction():
    S.run(include_fallback=False)
    assert all(c["max_tokens"] == S.SMOKE_MAX_TOKENS <= 64 for c in FakeHTTP.calls)


def test_panel_ordering_and_nested_subsets():
    ranks = [c["rank"] for c in S.PANEL]
    assert ranks == [1, 2, 3, 4, 5, 6]
    assert S.M_SUBSETS[3] == (1, 2, 3)
    assert set(S.M_SUBSETS[3]) < set(S.M_SUBSETS[4]) < set(S.M_SUBSETS[5])
    assert 6 not in S.M_SUBSETS[5], "rank 6 is the declared margin, not a primary member"
    assert S.PANEL[5]["role"] == "declared_margin"


def test_local_member_is_pinned_by_weights_not_by_echo():
    r = S.run(include_fallback=False, only={"qwen"})
    ident = r["records"][0]["identity"]
    assert ident["registered_weights"].endswith("Qwen3.8-27B-Q4_K_M.gguf")
    assert ident["weights_match"] is True
    assert ident["weights_readable"] is True


def test_local_member_fails_when_weights_cannot_be_read(monkeypatch):
    monkeypatch.setattr(S, "local_props", lambda *a, **k: {})
    r = S.run(include_fallback=False, only={"qwen"})
    ident = r["records"][0]["identity"]
    assert ident["matches_expected"] is False
    assert "could not be read" in (ident.get("note") or "")


def test_wrong_weights_behind_the_same_alias_is_caught(monkeypatch):
    monkeypatch.setattr(S, "local_props", lambda *a, **k: {"model_path": "/models/something-else.gguf"})
    res = S.run(include_fallback=False, only={"qwen"})
    with pytest.raises(S.SmokeError, match="DIFFERENT model"):
        S.verify(res)


def test_identity_mismatch_is_a_substitution_not_a_pass(monkeypatch):
    def bad_post(self, url, json=None, headers=None):
        FakeHTTP.calls.append({"url": url, "model": (json or {}).get("model"),
                               "max_tokens": (json or {}).get("max_tokens")})
        return FakeResp(200, {"model": "some/other-model"})
    monkeypatch.setattr(FakeHTTP, "post", bad_post)
    res = S.run(include_fallback=False, only={"glm"})
    with pytest.raises(S.SmokeError, match="DIFFERENT model"):
        S.verify(res)


def test_unreachable_endpoint_is_reported_not_silently_dropped(monkeypatch):
    def dead(self, url, json=None, headers=None):
        return FakeResp(429, {}, text='{"error":{"code":429,"message":"rate limited"}}')
    monkeypatch.setattr(FakeHTTP, "post", dead)
    res = S.run(include_fallback=False, only={"gemma"})
    with pytest.raises(S.SmokeError, match="unreachable"):
        S.verify(res)
    rep = S.verify(res, require_all=False)
    assert rep["unreachable"] == ["gemma"]


def test_no_credential_reaches_the_artifact(monkeypatch):
    def dead(self, url, json=None, headers=None):
        return FakeResp(401, {}, text=json_dumps_with_secret())
    def json_dumps_with_secret():
        return json.dumps({"error": {"code": 401, "message": "bad key",
                                     "metadata": {"raw": {"api_key": "sk-live-DEADBEEF"},
                                                  "billing_email": "a@b.com"}}})
    monkeypatch.setattr(FakeHTTP, "post", dead)
    res = S.run(include_fallback=False, only={"gptoss"})
    blob = json.dumps(res)
    assert "sk-live-DEADBEEF" not in blob
    assert "billing_email" not in blob
    assert "a@b.com" not in blob


def test_writes_only_under_the_smoke_dir(tmp_path):
    res = S.run(include_fallback=False)
    written = list((tmp_path / "smoke").rglob("*"))
    assert [p.name for p in written if p.is_file()] == ["smoke.json"]
    saved = json.loads((tmp_path / "smoke" / "smoke.json").read_text())
    assert saved["attempts_per_endpoint"] == 1
    assert saved["measured_at"].endswith("Z")


def test_expected_echoes_are_produced_for_the_registration():
    res = S.run(include_fallback=False)
    echoes = S.expected_echoes(res)
    assert echoes["glm"] == "zai-org/GLM-5.2"
    assert len(echoes) == len(S.PANEL)


def test_unreadable_weights_file_fails_the_n_params_half(monkeypatch):
    """If the count cannot be read, that is a failed check, not a silent pass."""
    monkeypatch.setattr(S, "local_props", lambda *a, **k: {
        "model_path": "/home/jmannings/.lmstudio/models/unsloth/Qwen3.8-27B-GGUF/"
                      "Qwen3.8-27B-Q4_K_M.gguf", "model_ftype": "Q4_K_M"})
    monkeypatch.setattr(S, "gguf_metadata", lambda p: {})
    r = S.run(include_fallback=False, only={"qwen"})
    ident = r["records"][0]["identity"]
    assert ident["matches_expected"] is False
    assert "could not be checked" in ident["n_params_note"]
    assert ident["weights_match"] is True, "the model_path half must still be checked"


def test_both_halves_of_the_pin_verify_against_the_loaded_file(monkeypatch):
    monkeypatch.setattr(S, "local_props", lambda *a, **k: {
        "model_path": "/home/jmannings/.lmstudio/models/unsloth/Qwen3.8-27B-GGUF/"
                      "Qwen3.8-27B-Q4_K_M.gguf", "model_ftype": "Q4_K_M"})
    monkeypatch.setattr(S, "gguf_metadata", lambda p: {"general.size_label": "27B"})
    # the real :8083 server answers under its registered alias, not the requested id
    def aliased(self, url, json=None, headers=None):
        FakeHTTP.calls.append({"url": url, "model": (json or {}).get("model"),
                               "max_tokens": (json or {}).get("max_tokens")})
        return FakeResp(200, {"model": "ornith35"})
    monkeypatch.setattr(FakeHTTP, "post", aliased)
    r = S.run(include_fallback=False, only={"qwen"})
    ident = r["records"][0]["identity"]
    assert ident["weights_match"] is True
    assert ident["n_params_match"] is True
    assert ident["registered_n_params"] == 27.0
    assert ident["matches_expected"] is True


def test_tag_ready_is_false_when_a_member_was_never_probed():
    res = {"records": [{"agent": "qwen", "status": "ok",
                        "identity": {"matches_expected": True}}]}
    ok, reasons = S.tag_ready(res)
    assert ok is False
    assert any("never probed" in r for r in reasons)


def test_tag_ready_is_false_on_an_unreachable_member():
    recs = [{"agent": c["agent"], "status": "ok", "identity": {"matches_expected": True}}
            for c in S.PANEL] + [{"agent": S.QWEN_FALLBACK["agent"], "status": "ok",
                                  "identity": {"matches_expected": True}}]
    recs[2]["status"] = "error"
    ok, reasons = S.tag_ready({"records": recs})
    assert ok is False and any("no observed echo to pin" in r for r in reasons)


def test_tag_ready_is_false_on_an_identity_mismatch():
    recs = [{"agent": c["agent"], "status": "ok", "identity": {"matches_expected": True}}
            for c in S.PANEL] + [{"agent": S.QWEN_FALLBACK["agent"], "status": "ok",
                                  "identity": {"matches_expected": True}}]
    recs[1]["identity"]["matches_expected"] = False
    ok, reasons = S.tag_ready({"records": recs})
    assert ok is False and any("did not match" in r for r in reasons)


def _complete_records():
    """Every member observed, including the local endpoint's full identity pin."""
    recs = []
    for c in S.PANEL:
        ident = {"matches_expected": True}
        if c["backend"] == "local":
            ident["n_params_match"] = True
        recs.append({"agent": c["agent"], "status": "ok", "identity": ident})
    recs.append({"agent": S.QWEN_FALLBACK["agent"], "status": "ok",
                 "identity": {"matches_expected": True}})
    return recs


def test_tag_ready_is_true_only_when_every_member_and_the_fallback_are_observed():
    ok, reasons = S.tag_ready({"records": _complete_records()})
    assert ok is True and reasons == []


def test_tag_ready_is_false_when_only_half_the_local_identity_pin_is_checkable():
    """model_path alone is not the registered pin; n_params is the other half."""
    recs = _complete_records()
    local = next(r for r in recs if r["agent"] == "qwen")
    local["identity"]["n_params_match"] = False
    ok, reasons = S.tag_ready({"records": recs})
    assert ok is False
    assert any("n_params" in r for r in reasons)


def test_n_params_is_read_from_the_gguf_not_from_props():
    """/props does not expose n_params; the loaded weights file does."""
    meta = S.gguf_metadata("/home/jmannings/.lmstudio/models/unsloth/"
                           "Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf")
    if not meta:
        pytest.skip("weights file not present")
    assert S.parse_n_params_billions(meta) == 27.0
    assert meta["general.size_label"] == "27B"


def test_a_missing_or_unreadable_gguf_yields_no_count():
    assert S.gguf_metadata("/nonexistent/model.gguf") == {}
    assert S.parse_n_params_billions({}) is None


def test_registered_n_params_is_parsed_from_the_evidence():
    q = next(c for c in S.PANEL if c["backend"] == "local")
    assert S.registered_n_params(q) == 27.0
    assert S.registered_n_params({"identity_evidence": "model_path /x.gguf"}) is None


def test_a_wrong_parameter_count_fails_the_identity_check(monkeypatch):
    monkeypatch.setattr(S, "local_props", lambda *a, **k: {
        "model_path": "/home/jmannings/.lmstudio/models/unsloth/"
                      "Qwen3.8-27B-GGUF/Qwen3.8-27B-Q4_K_M.gguf"})
    monkeypatch.setattr(S, "gguf_metadata", lambda p: {"general.size_label": "7B"})
    res = S.run(include_fallback=False, only={"qwen"})
    ident = res["records"][0]["identity"]
    assert ident["n_params_match"] is False
    assert ident["matches_expected"] is False
    with pytest.raises(S.SmokeError, match="DIFFERENT model"):
        S.verify(res)
