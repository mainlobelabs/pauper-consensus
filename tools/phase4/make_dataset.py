#!/usr/bin/env python3
"""Build self-distillation training data for the phase 4 LoRAs.

For each panel model, reads the phase 3 native run (train split only)
and writes mlx_lm.lora data:

    <out>/<model>_<variant>/train.jsonl   <- training slice (frozen)
    <out>/<model>_<variant>/valid.jsonl   <- calibration slice (fit only)
    <out>/<model>_<variant>/test.jsonl    <- test slice (monitor only)

Each line: {"prompt": <frozen jury message>, "completion": <target JSON>}

Target construction (prereg training section): the completion is the
JSON object whose answer field is the answer parsed from the model's
own native output and whose reason field is the native output verbatim
(reason_included variant), or the answer object alone (votes_only).
Native outputs that do not parse to a contract answer are excluded:
they carry no valid target.

Usage:
    python3 tools/phase4/make_dataset.py \
        --native-dir <runs/.../native> \
        --out <runs/.../datasets> \
        --models llama-3.2-3b-instruct,gemma-3-4b-it,phi-4-mini-instruct,qwen35-4b \
        --variants reason_included,votes_only

Stdlib only. Deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase3"))

from runner import (  # noqa: E402
    article_ids_by_split,
    jury_prompt,
    read_article,
    read_question_form,
)


def native_records(native_dir: Path, model: str, tids: set[str]) -> list[dict]:
    f = native_dir / f"{model}.jsonl"
    recs = []
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["article"] in tids:
            recs.append(r)
    return recs


def target_completion(rec: dict, variant: str) -> str | None:
    parsed = rec.get("parsed")
    if not parsed:
        return None
    answer = parsed["answer"]
    if variant == "votes_only":
        return json.dumps({"answer": answer}, ensure_ascii=False)
    # reason_included: the full JSON contract object, reason verbatim
    return json.dumps({"answer": answer, "reason": rec["raw"]}, ensure_ascii=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--native-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--variants", default="reason_included,votes_only")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    native_dir = Path(args.native_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    splits = article_ids_by_split()

    report = {}
    for m in models:
        for v in variants:
            d = out / f"{m}__{v}"
            d.mkdir(parents=True, exist_ok=True)
            counts = {}
            for sname in ("train", "calibration", "test"):
                tids = set(splits[sname])
                recs = native_records(native_dir, m, tids)
                # canonical order: article id, item number
                recs.sort(key=lambda r: (r["article"], r["item"]))
                lines = []
                n_excluded = 0
                for r in recs:
                    # rebuild the exact frozen prompt (must match inference)
                    prompt = jury_prompt(
                        read_article(r["article"]), read_question_form(r["article"])[r["item"] - 1]
                    )
                    if prompt != r["prompt"]:
                        raise RuntimeError(
                            f"prompt mismatch {m} {r['article']} {r['item']}: "
                            "reconstructed prompt differs from the recorded one"
                        )
                    completion = target_completion(r, v)
                    if completion is None:
                        n_excluded += 1
                        continue
                    lines.append(
                        json.dumps(
                            {"prompt": prompt, "completion": completion},
                            ensure_ascii=False,
                        )
                    )
                fname = {"train": "train", "calibration": "valid", "test": "test"}[sname]
                (d / f"{fname}.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""))
                counts[sname] = {"kept": len(lines), "excluded_unparsed": n_excluded}
            report[f"{m}__{v}"] = counts
            print(f"{m}__{v}: {counts}")
    (out / "dataset_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
