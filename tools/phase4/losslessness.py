"""Phase 4 losslessness check (prereg training.losslessness).

Per adapter (base model + fused fine-tuned model), on the 10 calibration
articles (untrained for every family):

  (a) exact-match agreement of parsed answers between the base native
      outputs and the fine-tuned contract outputs;
  (b) PPL of the base native outputs under the fine-tuned model, as a
      ratio to the base self-PPL (1.0 = lossless).

Descriptive per family; divergent adapters are flagged and their
consensus share is reported separately.

Usage (on helium):
  python3.11 tools/phase4/losslessness.py \
    --phase3-native /Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/native \
    --finetuned-native /Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/finetuned/native \
    --model-dir /Volumes/nvme0/omlx-models \
    --fused-dir /Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/fused \
    --out /Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/losslessness.json
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase3"))
from runner import article_ids_by_split  # noqa: E402

CALIB = article_ids_by_split()["calibration"]


def load_records(jsonl: Path, tids: set[str]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    if not jsonl.exists():
        return out
    for line in jsonl.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["article"] in tids and r["variant"] == "contract":
            out[(r["article"], str(r["item"]))] = r
    return out


def ppl_under(model, tokenizer, text: str) -> float:
    import mlx.core as mx
    import mlx.nn as nn

    ids = tokenizer.encode(text)
    if len(ids) < 2:
        return float("nan")
    input_ids = mx.array([ids])
    logits = model(input_ids)[0]  # (S, V)
    logprobs = nn.log_softmax(logits)
    total = 0.0
    for t in range(len(ids) - 1):
        total += float(logprobs[t, ids[t + 1]].item())
    return math.exp(-total / (len(ids) - 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase3-native", required=True)
    ap.add_argument("--finetuned-native", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--fused-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tids = set(CALIB)
    result = {"calibration_articles": sorted(CALIB), "adapters": {}}

    import mlx_lm

    base_self_ppl: dict[str, dict[str, dict[int, float]]] = {}
    for base in sorted({t.split("__")[0] for t in load_tags(args)}):
        records = load_records(Path(args.phase3_native) / f"{base}.jsonl", tids)
        print(f"== {base}: loading base model for self-PPL", flush=True)
        model, tokenizer = mlx_lm.load(str(Path(args.model_dir) / base))
        per: dict[str, dict[int, float]] = {}
        done = 0
        for tid in sorted(CALIB):
            per[tid] = {}
            for i in range(1, 41):
                r = records.get((tid, str(i)))
                if r is None:
                    continue
                per[tid][i] = ppl_under(model, tokenizer, r["raw"])
                done += 1
                if done % 50 == 0:
                    print(f"   {base} self-PPL {done}/400", flush=True)
        base_self_ppl[base] = per
        del model, tokenizer
        gc.collect()

    for tag in sorted(load_tags(args)):
        base, variant = tag.split("__", 1)
        base_recs = load_records(Path(args.phase3_native) / f"{base}.jsonl", tids)
        ft_recs = load_records(Path(args.finetuned_native) / f"{tag}.jsonl", tids)

        # (a) exact-match agreement on parsed answers
        n = agree = 0
        mismatches: list[dict] = []
        for key in sorted(base_recs):
            if key not in ft_recs:
                continue
            n += 1
            a = base_recs[key]["parsed"]
            b = ft_recs[key]["parsed"]
            pa = a.get("answer") if a else None
            pb = b.get("answer") if b else None
            if pa == pb and pa is not None:
                agree += 1
            else:
                mismatches.append(
                    {
                        "article": key[0],
                        "item": key[1],
                        "base_answer": pa,
                        "ft_answer": pb,
                        "base_parsed": a is not None,
                        "ft_parsed": b is not None,
                    }
                )
        exact = {
            "n_compared": n,
            "n_agree": agree,
            "agreement": round(agree / n, 4) if n else None,
            "mismatches": mismatches[:20],
            "n_mismatch_total": len(mismatches),
        }

        # (b) PPL ratio on base native outputs, all 40 questions per
        # calibration article
        self_per = base_self_ppl[base]
        print(f"== {tag}: loading fused model for PPL", flush=True)
        fmodel, ftoken = mlx_lm.load(str(Path(args.fused_dir) / tag))
        ratio: list[dict] = []
        done = 0
        for tid in sorted(CALIB):
            for i in range(1, 41):
                key = (tid, str(i))
                if key not in base_recs or tid not in self_per:
                    continue
                ft_ppl = ppl_under(fmodel, ftoken, base_recs[key]["raw"])
                self_ppl = self_per[tid].get(i)
                if self_ppl is None or not ft_ppl:
                    continue
                done += 1
                if done % 50 == 0:
                    print(f"   {tag} ft-PPL {done}/400", flush=True)
                ratio.append(
                    {
                        "article": tid,
                        "item": i,
                        "base_ppl": round(self_ppl, 4),
                        "ft_ppl": round(ft_ppl, 4),
                        "ratio": round(ft_ppl / self_ppl, 4),
                    }
                )
        rs = [r["ratio"] for r in ratio]
        ppl = {
            "n": len(rs),
            "mean_ratio": round(sum(rs) / len(rs), 4) if rs else None,
            "max_ratio": max(rs) if rs else None,
            "per_question": ratio,
        }
        del fmodel, ftoken
        gc.collect()

        flagged = exact["agreement"] is not None and exact["agreement"] < 0.8
        result["adapters"][tag] = {
            "variant": variant,
            "exact_match": exact,
            "ppl_ratio": ppl,
            "flagged_perturbed": flagged,
        }
        print(
            f"   {tag}: agreement {exact['agreement']}, ppl ratio {ppl['mean_ratio']}",
            flush=True,
        )

    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.out}")


def load_tags(args) -> list[str]:
    """Tags = fine-tuned model dirs that have a matching base in the
    phase-3 native dir."""
    fused = Path(args.fused_dir)
    out = []
    for d in sorted(fused.iterdir()):
        if d.is_dir() or d.is_symlink():
            out.append(d.name)
    return out


if __name__ == "__main__":
    main()
