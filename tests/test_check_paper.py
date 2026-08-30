"""The paper figure checker must bite, not merely pass."""
from __future__ import annotations

from pathlib import Path

import pytest

from exp3 import check_paper

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/paper_revised_sections.md"


def _check(text: str, tmp_path: Path):
    p = tmp_path / "paper.md"
    p.write_text(text)
    return check_paper.check(p, ROOT)


def test_fixture_passes():
    assert check_paper.check(FIXTURE, ROOT) == []


def test_catches_a_planted_wrong_digit(tmp_path):
    bad = FIXTURE.read_text().replace("| 0.9001 |", "| 0.9002 |")
    fails = _check(bad, tmp_path)
    assert any("0.9002" in f for f in fails)


def test_catches_an_unclassified_new_figure(tmp_path):
    bad = FIXTURE.read_text().replace("on c1_local.", "on c1_local. Accuracy was 0.8137.")
    fails = _check(bad, tmp_path)
    assert any("0.8137" in f for f in fails)


def test_catches_a_retained_v3_figure_that_matches_no_artifact(tmp_path):
    """The failure B2 pointed at: a figure carried over from draft v3 that does not
    correspond to any artifact value must not pass merely by looking like a quotation."""
    bad = FIXTURE.read_text().replace("AUROC 0.502-0.554", "AUROC 0.502-0.771")
    fails = _check(bad, tmp_path)
    assert any("0.771" in f for f in fails)


def test_structural_literals_are_permitted(tmp_path):
    """Dates, file:line refs, section numbers and version ids must NOT fail, or the rule
    would reject the paper this slice is required to produce."""
    ok = ("## Correction notice (2026-08-29)\n\n"
          "See exp/e1.py:76-78, prereg.yaml:166 and plan.md:488; draft v3 stated it in §6.1. "
          "The corrected value is 0.5069 on c1_local.\n")
    assert _check(ok, tmp_path) == []


def test_a_near_miss_structural_literal_still_fails(tmp_path):
    """Something that merely resembles a reference must not slip through."""
    bad = ("## Correction notice (2026-08-29)\n\n"
           "The corrected value is 0.5069 on c1_local, up from notaref.txt:0.7714.\n")
    fails = _check(bad, tmp_path)
    assert fails, "a bare figure dressed as a reference should not be exempt"


def test_reports_missing_evidence_rather_than_passing_vacuously(tmp_path):
    fails = check_paper.check(FIXTURE, tmp_path)   # empty dir: no artifacts
    assert fails and "no artifact values" in fails[0]


def test_positional_check_catches_a_cross_panel_swap(tmp_path):
    """Global membership would accept a row whose cells belong to a different panel."""
    bad = FIXTURE.read_text().replace("| c1_local | 0.9001 | 0.5069 | 0.9664 | 0.4484 |",
                                      "| c1_local | 0.9911 | 0.5239 | 0.9875 | 0.4825 |")
    fails = _check(bad, tmp_path)
    assert any("c1_local.capped_signed" in f for f in fails)


def test_positional_check_catches_a_flipped_interval_and_decision(tmp_path):
    bad = FIXTURE.read_text().replace(
        "| c2_panelB | platt | gptoss | +0.0329 [-0.0109, +0.0703] | **inconclusive** |",
        "| c2_panelB | platt | gptoss | +0.0329 [+0.0109, +0.0703] | **go** |")
    fails = _check(bad, tmp_path)
    assert any("c2_panelB.lo" in f for f in fails)
    assert any("c2_panelB.decision" in f for f in fails)


def test_quotation_check_accepts_a_verbatim_quotation():
    """The fixture quotes draft v3 exactly; the whole-span check must accept it."""
    assert check_paper.check(FIXTURE, ROOT) == []


def test_quotation_check_catches_a_fabricated_range_inside_a_quotation(tmp_path):
    """The failure the whole-span check exists for: each component of `0.569-0.554` occurs
    somewhere in the pinned draft, so per-number checking accepted the fabricated pairing."""
    bad = FIXTURE.read_text().replace("AUROC 0.502–0.554 (cycle 1)",
                                      "AUROC 0.569–0.554 (cycle 1)")
    fails = _check(bad, tmp_path)
    assert any("not verbatim" in f for f in fails), fails


def test_quotation_check_catches_a_wholly_invented_quotation(tmp_path):
    bad = FIXTURE.read_text().replace(
        'Draft v3 reported: "Claim-instance counting:',
        'Draft v3 reported: "Unique-source counting reached AUROC 0.9001 while claim counting:')
    fails = _check(bad, tmp_path)
    assert any("not verbatim" in f for f in fails), fails


def test_quotation_check_fails_when_the_pinned_draft_is_unreadable(tmp_path):
    """A missing pinned draft must FAIL, not silently skip the quotation check."""
    fails = check_paper.check(FIXTURE, tmp_path)   # no git repo here
    assert any("quotation check cannot run" in f or "no artifact values" in f for f in fails)


def test_fabricated_structural_labels_are_rejected(tmp_path):
    """Unbounded label patterns would exempt any invented number dressed as a label."""
    for bad_lit in ("depth-999", "contribution 999", "cycle-999", "slice 99"):
        text = ("## Correction notice (2026-08-29)\n\n"
                f"The corrected value is 0.5069 on c1_local, per {bad_lit}.\n")
        fails = _check(text, tmp_path)
        assert any("999" in f or "99" in f for f in fails), f"{bad_lit} was not rejected"
