"""The slice-4 decision entry is rendered from the registration and detects staleness (B11)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from exp3 import decide_v3 as D


@pytest.fixture
def sandbox(tmp_path):
    prereg = tmp_path / "prereg_v3.yaml"
    shutil.copy("prereg_v3.yaml", prereg)
    decisions = tmp_path / "DECISIONS.md"
    decisions.write_text("# Decisions\n\n## Something earlier\n\nprior text\n")
    return prereg, decisions


def test_entry_is_rendered_from_the_registration_not_typed(sandbox):
    prereg, _ = sandbox
    reg = yaml.safe_load(prereg.read_text())
    body = D.build(prereg)
    assert str(reg["dataset"]["n_items"]) in body
    assert str(reg["delta"]["value"]) in body
    assert reg["delta"]["argmin"] in body
    assert D.fingerprint(prereg) in body


def test_created_then_superseded_not_refused(sandbox):
    prereg, decisions = sandbox
    assert D.apply(prereg, decisions) == "created"
    assert D.check(prereg, decisions)[0] is True
    # slice 2's bug: a second run refused and left the entry stale forever
    assert D.apply(prereg, decisions) == "superseded"
    assert D.check(prereg, decisions)[0] is True
    assert decisions.read_text().count(f"## {D.MARK}") == 1, "the entry was duplicated"


def test_prior_content_is_preserved(sandbox):
    prereg, decisions = sandbox
    D.apply(prereg, decisions)
    assert "## Something earlier" in decisions.read_text()
    assert "prior text" in decisions.read_text()


def test_stale_fingerprint_is_detected(sandbox):
    prereg, decisions = sandbox
    D.apply(prereg, decisions)
    reg = yaml.safe_load(prereg.read_text())
    reg["dataset"]["n_items"] = 1234                    # registration moves on
    prereg.write_text(yaml.safe_dump(reg, sort_keys=False))
    ok, msg = D.check(prereg, decisions)
    assert ok is False and "STALE" in msg


def test_stale_entry_can_be_superseded_to_current(sandbox):
    prereg, decisions = sandbox
    D.apply(prereg, decisions)
    reg = yaml.safe_load(prereg.read_text())
    reg["dataset"]["n_items"] = 1234
    prereg.write_text(yaml.safe_dump(reg, sort_keys=False))
    assert D.check(prereg, decisions)[0] is False
    D.apply(prereg, decisions)
    assert D.check(prereg, decisions)[0] is True


def test_missing_entry_is_not_current(sandbox):
    prereg, decisions = sandbox
    ok, msg = D.check(prereg, decisions)
    assert ok is False and "no '" in msg


def test_hand_edited_body_is_detected_even_with_a_matching_fingerprint(sandbox):
    prereg, decisions = sandbox
    D.apply(prereg, decisions)
    t = decisions.read_text().replace("comfortably powered", "TOTALLY powered")
    decisions.write_text(t)
    ok, msg = D.check(prereg, decisions)
    assert ok is False and "differs from what the registration renders" in msg


def test_write_is_atomic_leaving_no_temp_files(sandbox):
    prereg, decisions = sandbox
    D.apply(prereg, decisions)
    leftovers = [p.name for p in decisions.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


@pytest.mark.parametrize("path,newval", [
    (("dataset", "n_items"), 4321),
    (("dataset", "sha256"), "f" * 64),
    (("delta", "value"), 0.1234),
    (("delta", "argmin"), "c9_nowhere"),
    (("power", "dose_response_increment", "detectable_at_registered_n"), 0.4242),
    (("instrument", "precision"), "bfloat16"),
    (("cost", "hard_cap", "run_total_usd"), 999.0),
    (("cost", "retry_allowance"), 0.99),
    (("panels", "ordering_rule"), "arbitrary"),
])
def test_every_material_field_actually_reaches_the_entry(sandbox, path, newval):
    """If a registration field can change without changing the entry, the entry is hard-coded."""
    prereg, _ = sandbox
    before = D.build(prereg)
    reg = yaml.safe_load(prereg.read_text())
    node = reg
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = newval
    prereg.write_text(yaml.safe_dump(reg, sort_keys=False))
    after = D.build(prereg)
    assert after != before, f"changing {'.'.join(map(str,path))} did not change the entry"


def test_entry_quotes_no_number_absent_from_the_registration(sandbox):
    """Catches a re-introduced hard-coded figure such as 150 items or +0.220/+0.272."""
    import re
    prereg, _ = sandbox
    body = D.build(prereg)
    blob = prereg.read_text()
    fp = D.fingerprint(prereg)
    suspicious = []
    for tok in re.findall(r"(?<![\w.])\d+\.\d+(?![\w])", body):
        if tok in blob or tok in fp:
            continue
        # percentages and thousands separators are rendered, not quoted
        suspicious.append(tok)
    assert not suspicious, f"decimals in the entry not found in the registration: {suspicious}"
