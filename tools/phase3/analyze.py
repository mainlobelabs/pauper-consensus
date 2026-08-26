#!/usr/bin/env python3
"""Phase 3 analysis: parse rates, zero-shot accuracy, difficulty check,
cost accounting, contamination summary.

Reads run JSONLs from the phase 3 run directory and the frozen corpus,
writes <run_dir>/analysis/analysis.json plus a readable summary to stdout.

Usage:
    python3 tools/phase3/analyze.py --run-dir <runs/2026-08-26-phase3>

Stdlib only. Deterministic.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "corpus"

EXPECT = {"ENTAIL": "PASS", "CONTRADICT": "FAIL", "UNSPECIFIED": "NOT_STATED"}
JURORS = [
    "llama-3.2-1b-instruct",
    "gemma-3-1b-it",
    "phi-4-mini-instruct",
    "olmoe-0125-instruct",
    "qwen35-4b",
]


def article_ids_by_split() -> dict[str, list[str]]:
    man = json.loads((CORPUS / "manifest.json").read_text())
    splits: dict[str, list[str]] = defaultdict(list)
    for e in man["articles"]:
        splits[e["split_role"]].append(e["id"])
    return {k: sorted(v) for k, v in splits.items()}


def load_labels() -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    for f in sorted(CORPUS.glob("labels/T*.json")):
        tid = f.stem
        labels[tid] = {rec["id"]: rec["label"] for rec in json.loads(f.read_text())}
    return labels


def load_records(run_dir: Path, sub: str) -> list[dict]:
    d = run_dir / sub
    if not d.is_dir():
        return []
    recs = []
    for f in sorted(d.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                recs.append(json.loads(line))
    return recs


def accuracy(records: list[dict], labels: dict[str, dict[str, str]], tids: set[str]) -> dict:
    """3-state accuracy vs corpus labels + gate (binary) accuracy."""
    n = ok = gate_n = gate_ok = 0
    by_class = Counter()
    wrong = []
    for r in records:
        tid = r["article"]
        if tid not in tids:
            continue
        if not r.get("parsed"):
            continue
        n += 1
        want = EXPECT[labels[tid][f"{tid}-{r['item']:03d}"]]
        got = r["parsed"]["answer"]
        if got == want:
            ok += 1
        else:
            wrong.append({"article": tid, "item": r["item"], "want": want, "got": got})
        by_class[want] += 1
        true_gate = want == "PASS"
        pred_gate = got == "PASS"
        gate_n += 1
        gate_ok += true_gate == pred_gate
    return {
        "n": n,
        "correct": ok,
        "accuracy": round(ok / n, 4) if n else None,
        "gate_accuracy": round(gate_ok / gate_n, 4) if gate_n else None,
        "class_counts": dict(by_class),
        "n_wrong": len(wrong),
        "wrong_sample": wrong[:20],
    }


def parse_stats(records: list[dict]) -> dict:
    n = len(records)
    parsed = sum(1 for r in records if r.get("parsed"))
    ans = Counter(r["parsed"]["answer"] for r in records if r.get("parsed"))
    usage = [r["usage"] for r in records if r.get("usage")]
    in_tok = sum(u.get("prompt_tokens", 0) or 0 for u in usage)
    out_tok = sum(u.get("completion_tokens", 0) or 0 for u in usage)
    lat = [r["latency_ms"] for r in records if r.get("latency_ms") is not None]
    ttft = [r["ttft_ms"] for r in records if r.get("ttft_ms") is not None]
    return {
        "n": n,
        "parsed": parsed,
        "parse_rate": round(parsed / n, 4) if n else None,
        "answer_dist": dict(ans),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "latency_ms_median": round(statistics.median(lat), 1) if lat else None,
        "ttft_ms_median": round(statistics.median(ttft), 1) if ttft else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)

    splits = article_ids_by_split()
    labels = load_labels()
    out: dict = {
        "run_dir": str(run_dir),
        "splits": splits,
    }

    # native: per model, per split
    native = load_records(run_dir, "native")
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in native:
        by_model[r["model"]].append(r)
    out["native"] = {}
    for m in JURORS:
        recs = by_model.get(m, [])
        d = {"all": parse_stats(recs), "splits": {}}
        for sname in ("train", "calibration", "test"):
            tids = set(splits[sname])
            d["splits"][sname] = {
                "parse": parse_stats([r for r in recs if r["article"] in tids]),
                "accuracy": accuracy(recs, labels, tids),
            }
        d["splits"]["test"]["difficulty_check"] = d["splits"]["test"]["accuracy"]["accuracy"]
        out["native"][m] = d

    # contamination
    cont = load_records(run_dir, "contamination")
    out["contamination"] = {m: {} for m in JURORS}
    for m in JURORS:
        recs = [r for r in cont if r["model"] == m]
        without = [r for r in recs if r.get("variant", "").endswith("without")]
        flagged = [r for r in without if r.get("flag")]
        out["contamination"][m] = {
            "n_calls": len(recs),
            "n_without_article": len(without),
            "n_flagged": len(flagged),
            "flagged": [
                {
                    "article": r["article"],
                    "question": r["item"],
                    "raw": r["raw"][:200],
                }
                for r in flagged
            ],
        }

    # solver baseline + self-review
    for sub in ("solver-baseline", "self-review"):
        recs = load_records(run_dir, sub)
        if not recs:
            continue
        d = parse_stats(recs)
        if sub == "self-review":
            d["accuracy_test"] = accuracy(recs, labels, set(splits["test"]))
        out[sub] = d

    # smoke (if present)
    smoke = load_records(run_dir, "smoke")
    if smoke:
        out["smoke"] = parse_stats(smoke)

    out_dir = run_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "analysis.json").write_text(json.dumps(out, indent=2) + "\n")

    # readable summary
    print("== parse rates (native, all splits)")
    for m in JURORS:
        s = out["native"][m]["all"]
        print(f"  {m:24s} {s['parsed']}/{s['n']} = {s['parse_rate']}")
    print("== task 14: zero-shot accuracy on TEST slice")
    for m in JURORS:
        a = out["native"][m]["splits"]["test"]["accuracy"]
        cal = out["native"][m]["splits"]["calibration"]["accuracy"]
        need_fb = cal["accuracy"] is not None and cal["accuracy"] < 0.75
        fb = "  <-- FALLBACK (<75% on calib)" if need_fb else ""
        line = (
            f"  {m:24s} test acc {a['accuracy']} "
            f"(gate {a['gate_accuracy']}) | calib acc {cal['accuracy']}{fb}"
        )
        print(line)
    print("== contamination flags (registered rule)")
    for m in JURORS:
        c = out["contamination"][m]
        print(f"  {m:24s} {c['n_flagged']}/{c['n_without_article']}")
    if "self-review" in out:
        s = out["self-review"]
        print(
            "== 27B self-review: "
            f"{s['parsed']}/{s['n']} parsed, "
            f"test acc {s['accuracy_test']['accuracy']}"
        )
    if "solver-baseline" in out:
        s = out["solver-baseline"]
        print(
            "== 27B solver baseline: "
            f"{s['n']} calls, {s['input_tokens'] + s['output_tokens']} tokens"
        )
    print(f"\nwrote {out_dir / 'analysis.json'}")


if __name__ == "__main__":
    main()
