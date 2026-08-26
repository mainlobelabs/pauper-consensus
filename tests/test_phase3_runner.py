"""Pin the runner's frozen-prompt extraction to prereg.yaml and the corpus.

The runner reads its prompt templates straight out of prereg.yaml with a small
line parser (so it stays stdlib-only on the fleet). These tests check that
parser against a real YAML parse, and that the assembled prompts match the
frozen wording exactly.
"""

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "phase3"))

import runner  # noqa: E402


def test_frozen_templates_match_yaml():
    prereg = yaml.safe_load((REPO / "prereg.yaml").read_text())
    for kind in ("jury_contract", "solver_baseline"):
        expected = prereg["prompts"][kind]
        assert runner.frozen_template(kind) == expected, kind


def test_jury_prompt_assembly():
    article = "Some article body.\n"
    claim = "Is it true that the canal cut starts on September 3?"
    p = runner.jury_prompt(article, claim)
    assert "<article>\nSome article body.\n</article>" in p
    assert claim in p
    assert "Answer this question only based on the information available on this\narticle." in p
    assert runner.ARTICLE_PH not in p
    assert runner.CLAIM_PH not in p


def test_solver_baseline_prompt_assembly():
    questions = [f"Question number {i}?" for i in range(1, 21)]
    p = runner.solver_baseline_prompt("Article body.", questions)
    assert "1. Question number 1?" in p
    assert "20. Question number 20?" in p
    assert "..." not in p
    assert runner.ARTICLE_PH not in p
    assert "Article body." in p


def test_contamination_prompt_with_and_without():
    w = runner.contamination_prompt("Article body.", "What year was the attack?", True)
    wo = runner.contamination_prompt("Article body.", "What year was the attack?", False)
    assert "<article>\nArticle body.\n</article>" in w
    assert "<article>" not in wo
    assert "What year was the attack?" in wo


def test_parse_contract():
    assert runner.parse_contract('{"answer": "PASS", "reason": "stated"}')["answer"] == "PASS"
    fenced = '```json\n{"answer": "fail", "reason": "r"}\n```'
    assert runner.parse_contract(fenced)["answer"] == "FAIL"
    assert runner.parse_contract("I think it is PASS.") is None
    assert runner.parse_contract('{"answer": "MAYBE", "reason": "r"}') is None
    assert runner.parse_contract('{"answer": "PASS"}') == {"answer": "PASS", "reason": ""}
    assert runner.parse_contract("[1, 2]") is None


def test_extract_targets():
    t = runner.extract_targets("The canal cut starts on September 3 and 34 vessels are queued.")
    assert "34" in t["numbers"]
    assert ("September", "3") in t["month_day"]
    assert runner.answer_hits_targets("the cut started september 3", t)


def test_answer_hits_targets_negative():
    t = {"numbers": ["34"], "month_day": [], "names": []}
    assert not runner.answer_hits_targets("about a dozen vessels", t)
    assert runner.answer_hits_targets("34 vessels were waiting", t)
