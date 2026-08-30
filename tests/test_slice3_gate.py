"""The slice-3 gate must FAIL on each thing it claims to check.

A gate whose assertions are only exercised by the happy path is the failure mode this
project keeps producing: it reports success having verified nothing. Each test here plants
the specific defect and asserts a non-zero exit.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "out/slice3/availability.json"
GATE = ROOT / "run_slice3.sh"


def _run() -> int:
    return subprocess.run(["bash", str(GATE)], cwd=ROOT,
                          capture_output=True, text=True).returncode


@pytest.fixture
def restore_artifact():
    backup = ART.read_bytes()
    yield
    ART.write_bytes(backup)


def _mutate(fn):
    d = json.loads(ART.read_text())
    fn(d)
    ART.write_text(json.dumps(d, indent=2, sort_keys=True))


import os

# These tests SPAWN the gate, and the gate runs this suite. Skipping when the gate is the
# caller is what stops run_slice3.sh recursing into itself; run them directly
# (pytest tests/test_slice3_gate.py) to exercise them.
pytestmark = [
    pytest.mark.skipif(not ART.exists(), reason="no availability artifact"),
    pytest.mark.skipif(os.environ.get("SLICE3_GATE_RUNNING") == "1",
                       reason="invoked from run_slice3.sh; running these would recurse"),
]


def test_gate_passes_on_the_real_artifact():
    assert _run() == 0


def test_missing_artifact_fails(restore_artifact):
    ART.rename(ART.with_suffix(".hidden"))
    try:
        assert _run() != 0
    finally:
        ART.with_suffix(".hidden").rename(ART)


def test_malformed_artifact_fails(restore_artifact):
    ART.write_text("{not json")
    assert _run() != 0


def test_incomplete_candidate_coverage_fails(restore_artifact):
    _mutate(lambda d: d["candidates"].pop(0))
    assert _run() != 0


def test_catalogue_only_success_fails(restore_artifact):
    """An `ok` with no content is a listed-but-broken model counting toward the margin."""
    def f(d):
        for c in d["candidates"]:
            if c["status"] == "ok":
                c["content_chars"] = 0
                break
    _mutate(f)
    assert _run() != 0


def test_missing_identity_record_fails(restore_artifact):
    _mutate(lambda d: d["candidates"][0].pop("identity", None))
    assert _run() != 0


def test_registration_digest_mismatch_fails(restore_artifact):
    _mutate(lambda d: d.update(registration_sha256="0" * 64))
    assert _run() != 0


def test_duplicate_candidate_records_fail(restore_artifact):
    _mutate(lambda d: d["candidates"].append(dict(d["candidates"][0])))
    assert _run() != 0


def test_non_live_call_fails(restore_artifact):
    """A cache-served result must never pass as a measurement of availability."""
    _mutate(lambda d: d["candidates"][0].update(live_call=False))
    assert _run() != 0


def test_untracked_file_under_the_frozen_surface_fails():
    intruder = ROOT / "exp/INTRUDER_TEST.py"
    intruder.write_text("# planted by the gate test\n")
    try:
        assert _run() != 0
    finally:
        intruder.unlink(missing_ok=True)


def test_paid_call_count_mismatch_fails(restore_artifact):
    _mutate(lambda d: d["spend"].update(paid_calls=99))
    assert _run() != 0
