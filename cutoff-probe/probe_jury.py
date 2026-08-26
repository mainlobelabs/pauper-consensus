#!/usr/bin/env python3
"""Cutoff probe for jury candidate models, via an OpenAI-compatible server.

Frozen question set: cutoff-probe/probes.md (batch 1 + batch 2 locators).
Scoring:
  CORRECT  answer matches expected.
  WRONG    confident but different.
  UNKNOWN  hedged, "I don't know", or no answer.
Jury eligibility: C1 CORRECT (model functional), P1/P2/P3/C2 not CORRECT
(no in-window leak). P4/P5/P0 are cutoff locators, recorded only.

Usage: python3 probe_jury.py <base_url> <model_id> [model_id ...]
Output: JSON to stdout, one object per (model, probe).
"""

import json
import sys
import time
import urllib.request

PROBES = [
    ("C1", "Who won the 2022 FIFA World Cup?", "Argentina"),
    (
        "P1",
        "A magnitude 7.7 earthquake struck off Flores island, Indonesia, on 15 August 2026. "
        "How many people were killed, as reported in late August 2026?",
        "at least 73",
    ),
    (
        "P2",
        "What was the name of the hurricane that passed south of Hawaii's Big Island "
        "as a Category 1 storm on 15 August 2026?",
        "Lala",
    ),
    (
        "P3",
        "How many consecutive days at sea had the USS Abraham Lincoln completed when it "
        "headed back to San Diego in August 2026 after a record deployment?",
        "272 days",
    ),
    (
        "C2",
        "What was the name of the wildfire near Reno, Nevada, that on 22 August 2026 had "
        "burned over 10,500 acres and prompted a state of emergency for Washoe County?",
        "Hawk Fire",
    ),
    ("P4", "On what date did the 2026 US-Iran Strait of Hormuz war begin?", "2026-02-28"),
    ("P5", "Who won the 70th Eurovision Song Contest, Vienna, May 2026?", "Dara (BG)"),
    ("P0", "What is your knowledge cutoff date?", ""),
]

UNKNOWN_MARKERS = [
    "don't know",
    "dont know",
    "i do not know",
    "i don't know",
    "no idea",
    "unclear",
    "not sure",
    "cannot say",
    "can't say",
    "in the future",
    "no record",
    "no historical",
    "false",
    "not yet",
    "has not",
    "unavailable",
    "no information",
]


def ask(base_url: str, model: str, question: str) -> str:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "temperature": 0,
        "max_tokens": 64,
        # Qwen3.5: keep the 64-token budget for the answer, not the think block.
        # Servers without chat template kwargs ignore this field.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.load(resp)
    message = data["choices"][0].get("message", {})
    text = (message.get("content") or message.get("reasoning_content") or "").strip()
    # strip thinking block if the template left one in
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    return text


def score(question_kind: str, answer: str, expected: str) -> str:
    low = answer.lower()
    if not expected:
        return "RECORDED"
    if expected.lower() in low:
        return "CORRECT"
    if any(m in low for m in UNKNOWN_MARKERS):
        return "UNKNOWN"
    return "WRONG"


def main() -> None:
    base_url = sys.argv[1]
    models = sys.argv[2:]
    out = []
    for model in models:
        for pid, question, expected in PROBES:
            t0 = time.time()
            try:
                answer = ask(base_url, model, question)
                err = None
            except Exception as e:  # noqa: BLE001
                answer, err = "", str(e)
            rec = {
                "model": model,
                "probe": pid,
                "expected": expected,
                "answer": answer[:400],
                "score": score(pid, answer, expected) if not err else "ERROR",
                "error": err,
                "seconds": round(time.time() - t0, 1),
            }
            out.append(rec)
            print(json.dumps(rec), flush=True)
    print("PROBE_DONE", flush=True)


if __name__ == "__main__":
    main()
