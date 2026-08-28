#!/usr/bin/env python3
"""Per-topic contamination gate runner, corpus v2 (GATE_DESIGN.md).

Runs every probe (corpus-v2/gate/probes.jsonl) against the 7 panel base
models on the helium omlx instances, plus 2 global canaries per model.
Stdlib only. Resumable: (model, probe_id) pairs already present in
gate_results.jsonl are skipped.

Scoring: CORRECT / WRONG / UNKNOWN (GATE_DESIGN.md). Automatic match only;
agent review overrides go to gate_review.jsonl.

Usage:
  python3 gate_run.py --probes corpus-v2/gate/probes.jsonl \
      --out corpus-v2/gate/runs/2026-08-28 \
      [--instances 8102 8103 8104 8105 8106 8107] [--host 100.83.162.43] \
      [--models m1 m2 ...] [--workers 24] [--only-topic V2-001] [--limit N]
"""

import argparse
import json
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

MODELS = [
    "llama-3.2-1b-instruct",
    "llama-3.2-3b-instruct",
    "gemma-3-1b-it",
    "gemma-3-4b-it",
    "phi-4-mini-instruct",
    "olmoe-0125-instruct",
    "qwen35-4b",
]

CANARIES = [
    {
        "probe_id": "GC1",
        "q": "Who won the 2022 FIFA World Cup?",
        "key": "Argentina",
        "aliases": [],
        "kind": "name",
        "expect": "CORRECT",  # must KNOW
    },
    {
        "probe_id": "GC2",
        "q": "Who was the former Ukrainian energy minister detained by the NABU in "
        "February 2026 over a kickback scheme involving the state nuclear sector?",
        "key": "German Galushchenko",
        "aliases": ["Galushchenko"],
        "kind": "name",
        "expect": "NOT_CORRECT",  # must NOT KNOW (in-window)
    },
]

UNKNOWN_MARKERS = [
    "don't know",
    "dont know",
    "do not know",
    "no idea",
    "not sure",
    "cannot say",
    "can't say",
    "in the future",
    "no record",
    "no historical",
    "not yet",
    "has not",
    "hasn't",
    "unavailable",
    "no information",
    "not in my",
    "not in the",
    "beyond my",
    "cutoff",
    "cut-off",
    "training data",
    "knowledge cutoff",
    "no way for me",
    "not familiar",
    "not aware",
    "cannot answer",
    "no reliable",
    "after my",
    "prior to my",
    "before my",
    "pre-dates",
    "predates",
    "no data",
    "cannot find",
    "cannot recall",
    "i cannot",
    "i can't",
    "unclear",
    "no publicly",
    "no official",
]


def _num_tokens(s: str):
    """Extract canonical numbers from a string: digits with commas/decimals,
    plus word forms million/billion with optional m/k suffixes."""
    out = set()
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(trillion|billion|million|thousand)?", s):
        val = m.group(1).replace(",", "")
        try:
            n = float(val)
        except ValueError:
            continue
        unit = m.group(2)
        if unit == "thousand":
            n *= 1e3
        elif unit == "million":
            n *= 1e6
        elif unit == "billion":
            n *= 1e9
        elif unit == "trillion":
            n *= 1e12
        out.add(round(n, 6))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([km])\b", s):
        try:
            n = float(m.group(1))
        except ValueError:
            continue
        out.add(round(n * (1e3 if m.group(2) == "k" else 1e6), 6))
    return out


def _canonical_key_numbers(key: str, aliases):
    nums = set()
    for cand in [key] + list(aliases):
        nums |= _num_tokens(cand.lower())
    # also bare digits inside the key/aliases
    for cand in [key] + list(aliases):
        for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", cand):
            try:
                nums.add(round(float(m.group(0).replace(",", "")), 6))
            except ValueError:
                pass
    return nums


def score(q: str, answer: str, key: str, aliases, kind: str) -> str:
    text = (answer or "").strip()
    if not text:
        return "UNKNOWN"
    low = text.lower()
    # explicit unknown first
    if any(mk in low for mk in UNKNOWN_MARKERS):
        # a matching answer quoted inside a refusal still counts as knowledge
        if kind in ("number",):
            if _canonical_key_numbers(key, aliases) & _num_tokens(low):
                return "CORRECT"
        else:
            for cand in [key] + list(aliases):
                if cand and cand.lower() in low:
                    return "CORRECT"
        return "UNKNOWN"
    if kind == "number":
        keys = _canonical_key_numbers(key, aliases)
        if keys & _num_tokens(low):
            return "CORRECT"
        if _num_tokens(low):
            return "WRONG"
        return "UNKNOWN"
    # name / date / place: substring match on key or alias
    for cand in [key] + list(aliases):
        c = cand.lower().strip()
        if c and len(c) >= 3 and c in low:
            return "CORRECT"
    return "WRONG"


def ask(host: str, port: int, model: str, question: str) -> tuple[str, str]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": question}],
        "temperature": 0,
        "max_tokens": 64,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    url = f"http://{host}:{port}/v1/chat/completions"
    last_err = ""
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.load(resp)
            message = data["choices"][0].get("message", {})
            text = (message.get("content") or message.get("reasoning_content") or "").strip()
            if "\n</think>" in text or text.startswith("<think>"):
                if "\n</think>" in text:
                    text = text.split("\n</think>", 1)[1].strip()
                elif "</think>" in text:
                    text = text.split("</think>", 1)[1].strip()
            return text, ""
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            last_err = str(e)
            time.sleep(2 * (attempt + 1))
    return "", last_err


def load_done(results_path: str) -> set:
    done = set()
    try:
        with open(results_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                done.add((r["model"], r["probe_id"], r.get("topic_id") or ""))
    except FileNotFoundError:
        pass
    return done


def git_hash() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", required=True, nargs="+", help="one or more probes jsonl files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--host", default="100.83.162.43")
    DEFAULT_INSTANCES = ["8102", "8103", "8104", "8105", "8106", "8107"]
    ap.add_argument("--instances", nargs="+", default=DEFAULT_INSTANCES)
    ap.add_argument("--models", nargs="+", default=MODELS)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--only-topic", default=None)
    ap.add_argument("--limit", type=int, default=0, help="cap total calls (0 = all)")
    args = ap.parse_args()

    import os

    os.makedirs(args.out, exist_ok=True)
    results_path = os.path.join(args.out, "gate_results.jsonl")
    done = load_done(results_path)

    probes = []
    seen_keys = set()
    for path in args.probes:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                p = json.loads(line)
                k = (p["topic_id"], p["probe_id"])
                if k in seen_keys:
                    raise SystemExit(f"duplicate probe {k} in {path}")
                seen_keys.add(k)
                probes.append(p)
    if args.only_topic:
        probes = [p for p in probes if p["topic_id"] == args.only_topic]
    # canaries first (they gate the run's validity)
    items = [(c["probe_id"], None, c) for c in CANARIES]
    items += [(p["probe_id"], p["topic_id"], p) for p in probes]
    if args.limit:
        items = items[: args.limit]

    # model -> instance mapping (round-robin; small models may share)
    inst_of = {m: args.instances[i % len(args.instances)] for i, m in enumerate(args.models)}

    tasks = []
    for model in args.models:
        for probe_id, topic_id, probe in items:
            if (model, probe_id, topic_id or "") in done:
                continue
            tasks.append((model, probe_id, topic_id, probe))

    t0 = datetime.now(UTC).isoformat()
    write_lock = threading.Lock()
    counters = {"done": 0, "correct": 0, "wrong": 0, "unknown": 0, "errors": 0}
    total = len(tasks)
    print(
        f"gate run: {total} calls ({len(args.models)} models x {len(items)} probes/canaries), "
        f"resume-skipped {len(args.models) * len(items) - total}",
        flush=True,
    )
    if not total:
        print("nothing to do")
        return

    manifest = {
        "started": t0,
        "git": git_hash(),
        "host": args.host,
        "instances": sorted(set(inst_of.values())),
        "model_instance": inst_of,
        "models": args.models,
        "params": {
            "temperature": 0,
            "max_tokens": 64,
            "enable_thinking": False,
            "retries": 3,
            "timeout_s": 300,
        },
        "probe_file": args.probes,
        "probes_total": len(probes),
        "canaries": [c["probe_id"] for c in CANARIES],
    }

    def work(task):
        model, probe_id, topic_id, probe = task
        port = inst_of[model]
        text, err = ask(args.host, int(port), model, probe["q"])
        if err:
            st = "ERROR"
        else:
            st = score(probe["q"], text, probe["key"], probe.get("aliases", []), probe["kind"])
        rec = {
            "model": model,
            "probe_id": probe_id,
            "topic_id": topic_id,
            "q": probe["q"],
            "key": probe["key"],
            "kind": probe["kind"],
            "instance": port,
            "resp": text,
            "score": st,
            "err": err,
            "ts": datetime.now(UTC).isoformat(),
        }
        with write_lock:
            with open(results_path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counters[st.lower()] = counters.get(st.lower(), 0) + 1
            counters["done"] += 1
            n = counters["done"]
        if n % 25 == 0 or n == total:
            print(
                f"  {n}/{total} C={counters['correct']} W={counters['wrong']} "
                f"U={counters['unknown']} E={counters['errors']}",
                flush=True,
            )
        return rec

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, tasks))

    manifest["finished"] = datetime.now(UTC).isoformat()
    manifest["counters"] = counters
    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"done: {counters}", flush=True)

    # canary report
    can = {}
    with open(results_path) as f:
        for line in f:
            r = json.loads(line)
            if r["probe_id"].startswith("GC"):
                can.setdefault(r["probe_id"], {})[r["model"]] = r["score"]
    flagged = []
    for model in args.models:
        gc1 = can.get("GC1", {}).get(model)
        gc2 = can.get("GC2", {}).get(model)
        if gc1 not in ("CORRECT",):
            flagged.append((model, f"GC1={gc1} (must KNOW failed)"))
        if gc2 == "CORRECT":
            flagged.append((model, "GC2=CORRECT (must NOT KNOW failed)"))
    print("canaries:", json.dumps(can, indent=1), flush=True)
    if flagged:
        print("FLAGGED MODELS:", flagged, flush=True)
        with open(os.path.join(args.out, "flagged_models.json"), "w") as f:
            json.dump(flagged, f, indent=2)


if __name__ == "__main__":
    main()
