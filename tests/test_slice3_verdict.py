"""The margin rule must be applied mechanically, including at its boundary."""
from __future__ import annotations

from exp3.slice3_verdict import verdict


def art(*statuses):
    fams = ["qwen", "poolside", "zhipu", "nvidia", "openai", "google"]
    return {"candidates": [{"agent": f"a{i}", "family": fams[i], "status": s,
                            "error": "", "note": ""}
                           for i, s in enumerate(statuses)]}


def test_more_than_five_families_registers_m5():
    v = verdict(art("ok", "ok", "ok", "ok", "ok", "ok"))
    assert v["n_families_reachable"] == 6 and v["margin"] == 1
    assert v["registrable"] == "M=5 registrable"


def test_exactly_five_is_the_boundary_and_does_not_register_m5():
    v = verdict(art("ok", "ok", "ok", "ok", "ok", "fail"))
    assert v["n_families_reachable"] == 5 and v["margin"] == 0
    assert "stretch arm" in v["registrable"]
    assert "M=5 registrable" != v["registrable"]


def test_fewer_than_five_registers_neither():
    v = verdict(art("ok", "ok", "ok", "ok", "fail", "fail"))
    assert v["n_families_reachable"] == 4 and v["margin"] == -1
    assert v["registrable"].startswith("neither")


def test_substituted_never_counts_toward_the_margin():
    """Five ok plus one substituted must NOT be read as six."""
    v = verdict(art("ok", "ok", "ok", "ok", "ok", "substituted"))
    assert v["n_families_reachable"] == 5, "a substitution inflated the family count"
    assert v["margin"] == 0
    assert "stretch arm" in v["registrable"]
    assert v["substituted"] and v["substituted"][0]["family"] == "google"


def test_two_variants_of_one_family_count_once():
    """The cycle-1 ornith error: two model ids, one family, one source."""
    a = {"candidates": [
        {"agent": "ornith35", "family": "ornith", "status": "ok", "error": "", "note": ""},
        {"agent": "ornith35-mtp", "family": "ornith", "status": "ok", "error": "", "note": ""},
        {"agent": "qwen", "family": "qwen", "status": "ok", "error": "", "note": ""}]}
    v = verdict(a)
    assert v["n_families_reachable"] == 2, "two variants of one family were counted twice"


def test_m3_subsets_are_family_disjoint_and_complete():
    v = verdict(art("ok", "ok", "ok", "ok", "ok", "ok"))
    assert v["n_m3_subsets"] == 20                     # C(6,3)
    for s in v["m3_subsets"]:
        parts = s.split("+")
        assert len(parts) == len(set(parts)) == 3


def test_failed_is_not_described_as_unavailable():
    v = verdict(art("ok", "ok", "ok", "ok", "ok", "fail"))
    note = v["failed_note"].lower()
    assert "one attempt" in note, v["failed_note"]
    # the word may appear only in the disclaimer itself, never as the claim
    assert note.count("unavailable") == 1 and "not 'unavailable'" in note



def test_paid_twin_does_not_count_as_the_pinned_id_answering():
    """The error that made the first verdict wrong: two pinned ids failed while their
    paid twins answered, and the count reported six families as if the pinned six worked."""
    a = {"candidates": [
        {"agent": "qwen", "family": "qwen", "status": "ok", "error": "", "note": ""},
        {"agent": "gptoss", "family": "openai", "status": "fail", "error": "404", "note": ""},
        {"agent": "gptoss_paid", "family": "openai", "tier": "paid", "status": "ok",
         "error": "", "note": ""}]}
    v = verdict(a)
    assert v["n_families_pinned_ok"] == 1, "a paid twin was counted as the pinned id"
    assert v["n_families_reachable"] == 2
    assert v["reachable_only_via_non_pinned_id"] == ["openai"]
    assert [f["agent"] for f in v["failed_pinned"]] == ["gptoss"]


def test_decision_text_follows_the_branch_not_a_hardcoded_claim(tmp_path, monkeypatch):
    """build() asserted the dose-response 'IS runnable' unconditionally, so a four-family
    measurement would have produced an entry contradicting its own verdict."""
    import json
    from exp3 import slice3_decide as D
    (tmp_path / "out/slice3").mkdir(parents=True)
    art = {"measured_at": "2026-08-30T00:00:00Z", "source_commit": "abc",
           "registration_sha256": "d" * 64,
           "spend": {"usd": 0.0, "paid_calls": 0, "is_upper_bound": False},
           "candidates": [{"agent": "a", "family": "f1", "backend": "local",
                           "status": "ok", "error": "", "note": ""}]}
    (tmp_path / "out/slice3/availability.json").write_text(json.dumps(art))
    from exp3.slice3_verdict import verdict
    (tmp_path / "out/slice3/verdict.json").write_text(json.dumps(verdict(art)))
    text = D.build(tmp_path)
    assert "CANNOT be run as designed" in text
    assert "IS runnable" not in text
