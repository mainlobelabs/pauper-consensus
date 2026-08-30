"""The slice-4 gate must FAIL on each thing it claims to check.

A gate whose assertions are only exercised by the happy path reports success having
verified nothing -- the failure mode this project keeps producing. Each test plants the
specific defect and asserts a non-zero exit. The gate fails fast (set -e), so a defect
planted in an early step exits without paying for reproduction or the full suite.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "run_slice4.sh"
PREREG = ROOT / "prereg_v3.yaml"
NLI = ROOT / "out/cache/nli"

# These tests SPAWN the gate, and the gate runs this suite. Skipping when the gate is the
# caller is what stops run_slice4.sh recursing; run them directly to exercise them.
pytestmark = [
    # Skip whenever ANY slice gate is the caller. Guarding only on SLICE4 meant slice 3's
    # gate -- which runs the same suite -- spawned a slice-4 gate per planted test, each
    # of which runs the whole suite again.
    pytest.mark.skipif(
        bool(os.environ.get("SLICE4_GATE_RUNNING")
             or os.environ.get("SLICE3_GATE_RUNNING")
             or int(os.environ.get("SLICE4_GATE_DEPTH", "0") or 0) >= 2),
        reason="invoked by a slice gate; would recurse"),
    pytest.mark.skipif(not GATE.exists(), reason="no gate script"),
]


def _run(timeout: int = 1800, *args: str) -> subprocess.CompletedProcess:
    """Invoke the gate. --allow-incomplete-smoke keeps these tests about the assertion
    under test rather than about the (separately gated) smoke evidence."""
    return subprocess.run(["bash", str(GATE), "--allow-incomplete-smoke", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=timeout)


@pytest.fixture
def restore_prereg():
    backup = PREREG.read_bytes()
    yield
    PREREG.write_bytes(backup)


def test_gate_script_declares_every_required_assertion():
    """Structural: the acceptance ids must actually appear as steps."""
    t = GATE.read_text()
    for needle in ("byte-clean", "out/v3", "out/slice3", "e1", "nli", "EMPTY",
                   "re-derived", "corpus", "reproduction", "pytest", "decide_v3"):
        assert needle in t, f"gate does not mention {needle!r}"
    assert "SLICE4_GATE_DEPTH" in t, "missing recursion guard"
    assert "suite stage skipped to break recursion" in t, \
        "the guard must limit DEPTH, not disable the planted tests entirely"
    assert "set -euo pipefail" in t, "gate does not fail fast"


def test_tag_is_not_created_without_an_explicit_flag():
    t = GATE.read_text()
    assert 'DOTAG=0' in t and '--tag' in t
    assert "TAG NOT CREATED" in t, "tagging must be opt-in and visibly skipped by default"


def test_registration_drift_fails(restore_prereg):
    """A hand-edited figure must be caught by re-derivation."""
    d = yaml.safe_load(PREREG.read_text())
    d["dataset"]["n_items"] = 12345
    PREREG.write_text(yaml.safe_dump(d, sort_keys=False))
    r = _run()
    assert r.returncode != 0
    # A planted figure propagates: n_items feeds the power calc, so the independent
    # validator may catch it at whichever cross-check fires first, before step 6b's
    # rebuild-diff. Assert the CATCH, not which check did the catching -- pinning the
    # message would make this test brittle against exactly the kind of extra validation
    # it wants to encourage.
    assert ("FAIL: independent validation" in r.stdout
            or "differs from the builder" in r.stdout), r.stdout[-1500:]


def test_wrong_delta_fails(restore_prereg):
    d = yaml.safe_load(PREREG.read_text())
    d["delta"]["value"] = 0.999
    PREREG.write_text(yaml.safe_dump(d, sort_keys=False))
    r = _run()
    assert r.returncode != 0
    assert ("differs from the builder" in r.stdout
            or "delta" in r.stdout.lower()), r.stdout[-1500:]


def test_extra_entry_in_the_frozen_nli_cache_fails():
    """An fp32 write into the frozen fp16 cache must be caught."""
    planted = NLI / "planted_fp32_contaminant.json"
    planted.write_text('{"probs": [[0.1, 0.2, 0.7]]}')
    try:
        r = _run()
        assert r.returncode != 0
        assert "fp32 leaked" in r.stdout
    finally:
        planted.unlink(missing_ok=True)


def test_untracked_file_under_the_frozen_surface_fails():
    planted = ROOT / "wct" / "_planted_slice4.py"
    planted.write_text("# planted\n")
    try:
        r = _run()
        assert r.returncode != 0
        assert "untracked paths under the frozen surface" in r.stdout
    finally:
        planted.unlink(missing_ok=True)


def test_modified_frozen_evidence_fails():
    target = ROOT / "out/v3/reanalysis_c2_panelA.json"
    backup = target.read_bytes()
    try:
        target.write_bytes(backup + b"\n")
        r = _run()
        assert r.returncode != 0
        assert "differs from" in r.stdout
    finally:
        target.write_bytes(backup)


def test_modified_slice3_evidence_fails():
    target = ROOT / "out/slice3/availability.json"
    backup = target.read_bytes()
    try:
        target.write_bytes(backup + b"\n")
        r = _run()
        assert r.returncode != 0
        assert "out/slice3" in r.stdout and "differs from" in r.stdout, r.stdout[-1200:]
    finally:
        target.write_bytes(backup)


def test_untracked_file_under_slice3_evidence_fails():
    planted = ROOT / "out/slice3/_planted.json"
    planted.write_text("{}")
    try:
        r = _run()
        assert r.returncode != 0
        assert "path set differs" in r.stdout, r.stdout[-1200:]
    finally:
        planted.unlink(missing_ok=True)


def test_cycle3_generation_artifact_before_the_tag_fails():
    d = ROOT / "out/cycle3"
    created = not d.exists()
    d.mkdir(parents=True, exist_ok=True)
    planted = d / "gen_planted.json"
    planted.write_text("{}")
    try:
        r = _run()
        assert r.returncode != 0
        assert "generation artifacts exist before the tag" in r.stdout
    finally:
        planted.unlink(missing_ok=True)
        if created:
            shutil.rmtree(d, ignore_errors=True)


def test_corpus_hash_mismatch_fails(monkeypatch, restore_prereg):
    """Re-derivation must catch a corpus that no longer hashes to the registered value."""
    d = yaml.safe_load(PREREG.read_text())
    d["dataset"]["sha256"] = "0" * 64
    PREREG.write_text(yaml.safe_dump(d, sort_keys=False))
    r = _run()
    assert r.returncode != 0


def test_gate_passes_on_the_real_tree():
    """The happy path, last: an always-failing gate proves nothing either."""
    r = _run()
    assert r.returncode == 0, r.stdout[-3000:]
    assert "SLICE 4 GATE PASSED" in r.stdout


def test_incomplete_smoke_evidence_fails_the_default_command():
    """B4 unmet must be a non-zero exit, not a note under a PASSED banner."""
    r = subprocess.run(["bash", str(GATE)], cwd=ROOT, capture_output=True,
                       text=True, timeout=1800)
    ok, _ = __import__("exp3.smoke_v3", fromlist=["x"]).tag_ready()
    if ok:
        assert r.returncode == 0
    else:
        assert r.returncode != 0, "gate passed while B4 was unmet"
        assert "B4 is unmet" in r.stdout


def test_banner_does_not_claim_taggable_when_smoke_is_incomplete():
    r = _run()
    assert r.returncode == 0
    ok, _ = __import__("exp3.smoke_v3", fromlist=["x"]).tag_ready()
    if not ok:
        assert "B4 UNMET" in r.stdout and "NOT taggable" in r.stdout
        assert "ready to tag" not in r.stdout
