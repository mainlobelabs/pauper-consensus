#!/usr/bin/env python3
"""Cutoff probe batch 4: window extension for prereg v2, qwen3.8-27b only.

Purpose: confirm the 27B solver is blind to 2026-02-15..2026-08-27 events
so the v2 corpus can use that window. Batches 1-3 already covered
2026-08-14..25 (blind), 2026-02-28 (blind, P4), 2026-05 (blind, P5).
This batch adds interior points: mid-Feb (window start), March, June,
mid-July, late-July, plus a January 2026 locator (P13) to pin the
cutoff's lower bound for the report.

Params: same frozen convention as batches 1-3. One concurrent request,
temperature 0, max_tokens 64, thinking off.

Scoring (inherited): CORRECT = expected substring present, UNKNOWN =
hedged / future / no-record, WRONG = confident but different.
P13 is a cutoff LOCATOR (recorded only): CORRECT there means the cutoff
is after 2026-01-03; it is NOT a window violation because the window
starts 2026-02-15.

Usage: python3 probe_batch4.py <base_url> <model_id>
Output: JSON to stdout, one object per probe.
"""

import json
import sys
import time
import urllib.request

PROBES = [
    ("C1", "Who won the 2022 FIFA World Cup?", "Argentina"),
    (
        "P13",
        "On 3 January 2026, which Venezuelan leader was captured by US forces "
        "during an airstrike on Caracas?",
        "Maduro",
    ),
    (
        "P8",
        "Who won Super Bowl LX, played in February 2026?",
        "Seahawks",
    ),
    (
        "P9",
        "Who won the 68th running of the Daytona 500, held in February 2026?",
        "Reddick",
    ),
    (
        "P10",
        "Which US Navy submarine sank the Iranian frigate IRIS Dena in March 2026?",
        "Charlotte",
    ),
    (
        "P11",
        "Which horse won the 158th Belmont Stakes in June 2026?",
        "Golden Tempo",
    ),
    (
        "P12",
        "In the 2026 FIFA World Cup round of 16, which country did Norway beat on 5 July 2026?",
        "Brazil",
    ),
    (
        "P14",
        "A magnitude 7.1 earthquake struck Kumamoto Prefecture, Japan on 28 July "
        "2026. An explosion damaged a large shopping mall in Kashima town during "
        "the quake. What was the name of the mall?",
        "Aeon",
    ),
]

# Cutoff locators: recorded, never a window violation.
LOCATORS = {"P13"}

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
    if "\n</think>" in text:
        text = text.split("\n</think>", 1)[1].strip()
    return text


def score(pid: str, answer: str, expected: str) -> str:
    if pid in LOCATORS:
        if not answer.strip():
            return "UNKNOWN"
        low = answer.lower()
        if expected.lower() in low:
            return "CORRECT"
        if any(m in low for m in UNKNOWN_MARKERS):
            return "UNKNOWN"
        return "WRONG"
    low = answer.lower()
    if expected.lower() in low:
        return "CORRECT"
    if any(m in low for m in UNKNOWN_MARKERS):
        return "UNKNOWN"
    return "WRONG"


def main() -> None:
    base_url = sys.argv[1]
    model = sys.argv[2]
    out = []
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
