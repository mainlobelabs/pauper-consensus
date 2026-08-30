"""The probe must reject catalogue-shaped success, never leak credentials, and never
overlap local calls."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from exp3 import availability as A

ROOT = Path(__file__).resolve().parent.parent


class _Resp:
    """Minimal httpx.Response stand-in: the probe issues its own request now, so the tests
    patch the TRANSPORT rather than the client."""
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._p, self.text = status, payload or {}, text or ""
    def json(self):
        return self._p


def _msg(content="", reasoning="", model=None, usage=None):
    return {"choices": [{"message": {"content": content, "reasoning": reasoning}}],
            "model": model, "usage": usage or {}}


class _FakeHttp:
    def __init__(self, resp, sink=None, hook=None):
        self._r, self._sink, self._hook = resp, sink, hook
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def post(self, url, json=None, headers=None):
        if self._sink is not None:
            self._sink.append(url)
        if self._hook:
            self._hook()
        return self._r


def _probe(monkeypatch, resp, cand, sink=None, hook=None):
    class FakeClient:
        def __init__(self, backend, timeout=0, base_url=None):
            self.backend, self.base, self.key = backend, base_url or "http://x/v1", "k"
    monkeypatch.setattr("wct.nodes.Client", FakeClient)
    monkeypatch.setattr("wct.nodes.build_prompt", lambda item, role: "probe prompt")
    monkeypatch.setattr("httpx.Client", lambda **k: _FakeHttp(resp, sink, hook))
    return A._probe_one(cand, object(), 5.0)


CAND = {"panel": "p", "agent": "x", "family": "fam", "backend": "openrouter",
        "model": "m", "base": None, "expected_resolved": None}


def test_candidates_come_from_the_registration():
    fams = {c["family"] for c in A.candidates(ROOT)}
    assert fams == {"qwen", "poolside", "zhipu", "nvidia", "openai", "google"}
    assert not any(f.startswith("UNMAPPED") for f in fams)


def test_probe_never_uses_the_generation_cache():
    """nodes.Client.generate consults the cache and its key omits the agent, so a probe
    would be served from the August smoke-test entry. Availability is a property of the
    endpoint NOW."""
    import inspect
    src = inspect.getsource(A._probe_one)
    assert "client.generate" not in src and ".generate(" not in src
    assert "h.post" in src


def test_empty_completion_is_not_success(monkeypatch):
    r = _probe(monkeypatch, _Resp(200, _msg(content="")), CAND)
    assert r["status"] == "fail" and "empty completion" in r["error"]


def test_whitespace_only_completion_is_not_success(monkeypatch):
    r = _probe(monkeypatch, _Resp(200, _msg(content="   \n ")), CAND)
    assert r["status"] == "fail"


def test_usable_content_is_ok(monkeypatch):
    # real endpoints echo the served model; the fixture must too, or identity is
    # unverifiable and the result is correctly NOT counted as the registered model
    r = _probe(monkeypatch, _Resp(200, _msg(content="The cat is bright.", model="m")), CAND)
    assert r["status"] == "ok" and r["content_chars"] > 0 and r["live_call"] is True


def test_non_200_is_a_failure_with_its_status(monkeypatch):
    r = _probe(monkeypatch, _Resp(404, {}, text='{"error":"gone"}'), CAND)
    assert r["status"] == "fail" and r["http_status"] == 404


def test_unexpected_identity_is_substituted_not_ok(monkeypatch):
    cand = dict(CAND, expected_resolved="ornith35")
    r = _probe(monkeypatch, _Resp(200, _msg(content="x", model="something-else")), cand)
    assert r["status"] == "substituted"
    assert "ornith35" in r["note"] and "something-else" in r["note"]


def test_expected_identity_echo_is_ok_even_when_it_differs_from_the_request(monkeypatch):
    """qwen: requested qwen3.8-27b, served under alias ornith35, which IS the expected echo."""
    cand = dict(CAND, model="qwen3.8-27b", expected_resolved="ornith35")
    r = _probe(monkeypatch, _Resp(200, _msg(content="x", model="ornith35")), cand)
    assert r["status"] == "ok"


def test_credentials_never_reach_the_artifact(monkeypatch):
    leak = '{"error":"401 Bearer sk-abcdef0123456789 rejected"}'
    r = _probe(monkeypatch, _Resp(401, {}, text=leak), CAND)
    assert "sk-abcdef0123456789" not in r["error"] and "REDACTED" in r["error"]


def test_sanitise_covers_common_credential_shapes():
    for s in ("Authorization: Bearer abc123", "api_key=secret999",
              'token": "xyz789"', "sk-livekey1234567890"):
        assert "REDACTED" in A.sanitise(f"error {s} end"), s


def test_exactly_one_attempt_per_endpoint(monkeypatch):
    """Client._call retries a model failure twice and waits out six 429s; the probe must not."""
    calls = []
    r = _probe(monkeypatch, _Resp(500, {}, text="boom"), CAND, sink=calls)
    assert r["status"] == "fail"
    assert len(calls) == 1, f"expected exactly one request, got {len(calls)}"


def test_local_probes_never_overlap(monkeypatch):
    """GOTCHAS: the local server holds ONE model slot; overlapping calls 400/500 and a good
    model would be recorded unavailable purely from contention."""
    import threading
    inflight, overlaps = [], []
    lock = threading.Lock()

    def hook():
        with lock:
            if inflight:
                overlaps.append(1)
            inflight.append(1)
        try:
            pass
        finally:
            with lock:
                inflight.pop()

    class FakeClient:
        def __init__(self, backend, timeout=0, base_url=None):
            self.backend, self.base, self.key = backend, "http://x/v1", "k"
    monkeypatch.setattr("wct.nodes.Client", FakeClient)
    monkeypatch.setattr("wct.nodes.build_prompt", lambda item, role: "probe prompt")
    monkeypatch.setattr("httpx.Client",
                        lambda **k: _FakeHttp(_Resp(200, _msg(content="ok")), None, hook))
    monkeypatch.setattr(A, "candidates", lambda root: [
        dict(CAND, backend="local", agent=f"L{i}", family=f"f{i}") for i in range(3)])
    monkeypatch.setattr("exp.envfile.load_harness_env", lambda: [])
    A.run(ROOT, timeout=1.0)
    assert not overlaps, "local probes overlapped; the single model slot would 400"


def test_paid_spend_is_calculated_not_just_counted():
    recs = [{"backend": "hoonify", "usage": {"prompt_tokens": 1_000_000,
                                             "completion_tokens": 1_000_000}},
            {"backend": "openrouter", "usage": {}}]
    s = A.spend(recs)
    assert s["paid_calls"] == 1
    assert s["usd"] == pytest.approx(1.40 + 4.40)
    assert s["is_upper_bound"] is False


def test_openrouter_paid_twin_is_metered_too():
    s = A.spend([{"backend": "openrouter", "tier": "paid", "model": "openai/gpt-oss-20b",
                  "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}}])
    assert s["paid_calls"] == 1 and s["usd"] == pytest.approx(0.03 + 0.13)


def test_spend_falls_back_to_a_conservative_upper_bound():
    s = A.spend([{"backend": "hoonify", "usage": {}}])
    assert s["is_upper_bound"] is True and s["usd"] > 0


def test_reprobe_supersedes_without_erasing():
    """A prior 429 that later succeeds is evidence, not noise: the superseded attempt must
    survive in the artifact."""
    prior = {"measured_at": "T1", "candidates": [
        {"agent": "gemma", "family": "google", "backend": "openrouter", "status": "fail", "error": "429", "latency_s": 201.0},
        {"agent": "qwen", "family": "qwen", "backend": "local", "status": "ok", "error": "", "latency_s": 1.0}]}
    fresh = {"measured_at": "T2", "candidates": [
        {"agent": "gemma", "family": "google", "backend": "openrouter", "status": "ok", "error": "", "latency_s": 2.0}]}
    m = A.merge_reprobe(prior, fresh, {"gemma"})
    g = [c for c in m["candidates"] if c["agent"] == "gemma"][0]
    assert g["status"] == "ok" and g["measured_at"] == "T2"
    assert g["superseded_by_reprobe"][0]["status"] == "fail"
    assert g["superseded_by_reprobe"][0]["error"] == "429"
    assert [c for c in m["candidates"] if c["agent"] == "qwen"][0]["status"] == "ok"
    assert m["reprobes"][0]["agents"] == ["gemma"]


def test_reprobe_leaves_untargeted_candidates_untouched():
    prior = {"measured_at": "T1", "candidates": [
        {"agent": "gptoss", "family": "openai", "backend": "openrouter", "status": "fail", "error": "404", "latency_s": 4.0},
        {"agent": "gemma", "family": "google", "backend": "openrouter", "status": "fail", "error": "429", "latency_s": 201.0}]}
    fresh = {"measured_at": "T2", "candidates": [
        {"agent": "gemma", "family": "google", "backend": "openrouter", "status": "ok", "error": "", "latency_s": 2.0}]}
    m = A.merge_reprobe(prior, fresh, {"gemma"})
    got = [c for c in m["candidates"] if c["agent"] == "gptoss"][0]
    assert got["status"] == "fail" and got["error"] == "404"
    assert "superseded_by_reprobe" not in got


def test_reprobe_appends_candidates_absent_from_the_prior_artifact():
    """The paid twins are NEW agents. An earlier merge dropped them silently: the probes
    ran, the spend happened, and the results never reached the file."""
    prior = {"measured_at": "T1", "candidates": [
        {"agent": "gptoss", "family": "openai", "backend": "openrouter",
         "status": "fail", "error": "404", "latency_s": 4.0}]}
    fresh = {"measured_at": "T2", "candidates": [
        {"agent": "gptoss_paid", "family": "openai", "backend": "openrouter",
         "tier": "paid", "model": "openai/gpt-oss-20b", "status": "ok",
         "error": "", "latency_s": 3.0}]}
    m = A.merge_reprobe(prior, fresh, {"gptoss_paid"})
    agents = {c["agent"] for c in m["candidates"]}
    assert "gptoss_paid" in agents, "a new candidate was dropped by the merge"
    assert "gptoss" in agents, "the prior candidate was lost"


def test_merge_refuses_to_claim_a_probe_it_does_not_contain():
    prior = {"measured_at": "T1", "candidates": []}
    fresh = {"measured_at": "T2", "candidates": []}
    with pytest.raises(RuntimeError, match="absent from the merged artifact"):
        A.merge_reprobe(prior, fresh, {"ghost"})


def test_failed_candidates_still_carry_an_identity_record(monkeypatch):
    """E2 wants identity for EVERY candidate: 'no echo observed' is itself the finding, and
    the gate rejects an artifact missing it."""
    r = _probe(monkeypatch, _Resp(404, {}, text='{"error":"gone"}'), CAND)
    assert r["status"] == "fail"
    assert r["identity"]["requested"] == "m"
    assert r["identity"]["echoed"] is None and r["identity"]["echo_present"] is False


def test_identity_is_always_checkable_by_defaulting_to_the_requested_id(monkeypatch):
    """Previously a null `expected_resolved` meant 'nothing to check', so any 200 with
    content became `ok` and an upstream route to other weights passed silently."""
    r = _probe(monkeypatch, _Resp(200, _msg(content="x", model="m")), CAND)
    assert r["identity"]["checkable"] is True
    assert r["identity"]["expected"] == "m"
    assert r["identity"]["expected_source"] == "requested id (default)"
    assert r["status"] == "ok" and r["identity_verified"] is True


def test_unexpected_echo_is_substituted_even_without_a_registered_alias(monkeypatch):
    r = _probe(monkeypatch, _Resp(200, _msg(content="x", model="someone-elses-model")), CAND)
    assert r["status"] == "substituted"
    assert r["identity_verified"] is False


def test_transport_failure_still_carries_an_identity_record(monkeypatch):
    """Connection refused is a valid recorded failure; it must not produce an empty identity
    that the gate then rejects as malformed."""
    class Boom:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): raise ConnectionError("[Errno 111] Connection refused")

    class FakeClient:
        def __init__(self, backend, timeout=0, base_url=None):
            self.backend, self.base, self.key = backend, "http://x/v1", "k"
    monkeypatch.setattr("wct.nodes.Client", FakeClient)
    monkeypatch.setattr("wct.nodes.build_prompt", lambda item, role: "p")
    monkeypatch.setattr("httpx.Client", lambda **k: Boom())
    r = A._probe_one(dict(CAND), object(), 5.0)
    assert r["status"] == "fail"
    assert r["identity"]["requested"] == "m"
    assert r["identity"]["echoed"] is None
    assert r["identity"]["expected_source"] == "requested id (default)"


def test_answer_without_an_echoed_id_is_not_counted_as_the_registered_model(monkeypatch):
    """200 with content but no model field: identity is unverifiable, so it must not
    inflate the family margin the registration rests on."""
    r = _probe(monkeypatch, _Resp(200, _msg(content="hello", model=None)), CAND)
    assert r["status"] == "substituted"
    assert "echoed NO model id" in r["note"]
    assert r["identity_verified"] is False
