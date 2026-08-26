#!/usr/bin/env python3
"""Phase 4 LoRA training and fusion driver.

For each (model, variant) of the panel: runs mlx_lm.lora on the
self-distillation dataset, then mlx_lm.fuse to produce a standalone
model directory that oMLX can serve like any other model.

Writes phase4_recipe.json (every command, the mlx_lm defaults that
apply, seeds, git hash, model weight hashes) and one log per step.

Usage:
    python3 tools/phase4/train_lora.py --run-dir <runs/2026-08-27-phase4> \
        --datasets <run-dir>/datasets \
        --model-dir /Volumes/nvme0/omlx-models \
        --models llama-3.2-3b-instruct,gemma-3-4b-it,phi-4-mini-instruct,qwen35-4b \
        [--variants reason_included,votes_only] [--skip-fuse]

Stdlib only (subprocess). Deterministic per recipe manifest.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase3"))

from runner import weight_hashes  # noqa: E402

MLX_LM = "/opt/homebrew/bin/mlx_lm"
PYTHON311 = "/opt/homebrew/opt/python@3.11/bin/python3.11"

# distinct seed per family (prereg: distinct seeds, different recipe
# where possible); same seed across both variants of a family
SEEDS = {
    "llama-3.2-3b-instruct": 7,
    "gemma-3-4b-it": 13,
    "phi-4-mini-instruct": 42,
    "qwen35-4b": 99,
}

# mlx_lm.lora defaults that apply (verified against the installed
# mlx_lm: lora_parameters rank 8, dropout 0.0, scale 20.0)
MLX_LM_DEFAULTS = {
    "lora_parameters": {"rank": 8, "dropout": 0.0, "scale": 20.0},
    "optimizer": "adamw",
    "num_layers": 16,
    "batch_size": 4,
    "iters": 200,
    "learning_rate": 1e-4,
    "max_seq_length": 2048,
    "mask_prompt": True,
    "val_batches": 50,
    "steps_per_report": 10,
    "steps_per_eval": 50,
}


def git_hash() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def run_step(cmd: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as log:
        log.write("\n$ " + " ".join(cmd) + f"\n\n{datetime.now(UTC).isoformat()}\n\n")
        log.flush()
        p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    return p.returncode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--datasets", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--variants", default="reason_included,votes_only")
    ap.add_argument("--skip-fuse", action="store_true")
    ap.add_argument("--parallel", type=int, default=1, help="concurrent trainings (1 = sequential)")
    ap.add_argument(
        "--tag", default="", help="comma-separated model__variant tags to run (default: full grid)"
    )
    ap.add_argument("--lr", default="1e-4", help="learning rate override for this run")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    run_dir = Path(args.run_dir)
    datasets = Path(args.datasets)
    model_dir = Path(args.model_dir)

    recipe_path = run_dir / "phase4_recipe.json"
    if recipe_path.exists():
        recipe = json.loads(recipe_path.read_text())
        recipe["generated_utc"] = datetime.now(UTC).isoformat()
        recipe["git_hash"] = git_hash()
        recipe["parallel"] = args.parallel
    else:
        recipe = {
            "generated_utc": datetime.now(UTC).isoformat(),
            "repo": str(REPO),
            "git_hash": git_hash(),
            "mlx_lm": MLX_LM,
            "mlx_lm_defaults": MLX_LM_DEFAULTS,
            "parallel": args.parallel,
            "seeds": SEEDS,
            "base_weight_hashes": {},
            "adapters": {},
        }

    def train_one(m: str, v: str) -> tuple[str, dict]:
        tag = f"{m}__{v}"
        base = model_dir / m
        dset = datasets / tag
        adapter = run_dir / "adapters" / tag
        fused = run_dir / "fused" / tag
        cmd = [
            MLX_LM,
            "lora",
            "--model",
            str(base),
            "--train",
            "--data",
            str(dset),
            "--fine-tune-type",
            "lora",
            "--optimizer",
            "adamw",
            "--mask-prompt",
            "--num-layers",
            "16",
            "--batch-size",
            "4",
            "--iters",
            "200",
            "--learning-rate",
            args.lr,
            "--max-seq-length",
            "2048",
            "--val-batches",
            "50",
            "--steps-per-report",
            "10",
            "--steps-per-eval",
            "50",
            "--seed",
            str(SEEDS[m]),
            "--adapter-path",
            str(adapter),
        ]
        log = run_dir / "logs" / f"{tag}.train.log"
        print(f"== training {tag}", flush=True)
        rc = run_step(cmd, log)
        entry = {"cmd": cmd, "train_log": str(log), "train_rc": rc}
        if rc != 0:
            entry["status"] = "train_failed"
            return tag, entry
        if args.skip_fuse:
            entry["status"] = "trained"
            return tag, entry
        fcmd = [
            "/opt/homebrew/bin/mlx_lm.fuse",
            "--model",
            str(base),
            "--adapter-path",
            str(adapter),
            "--save-path",
            str(fused),
        ]
        flog = run_dir / "logs" / f"{tag}.fuse.log"
        print(f"== fusing {tag}", flush=True)
        frc = run_step(fcmd, flog)
        entry["fuse_cmd"] = fcmd
        entry["fuse_log"] = str(flog)
        entry["fuse_rc"] = frc
        entry["fused_dir"] = str(fused)
        entry["status"] = "fused" if frc == 0 else "fuse_failed"
        return tag, entry

    for m in models:
        recipe["base_weight_hashes"][m] = weight_hashes(model_dir / m)
    tasks = [(m, v) for m in models for v in variants]
    if args.tag:
        wanted = {t.strip() for t in args.tag.split(",") if t.strip()}
        tasks = [t for t in tasks if f"{t[0]}__{t[1]}" in wanted]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        for tag, entry in ex.map(lambda t: train_one(t[0], t[1]), tasks):
            recipe["adapters"][tag] = entry

    (run_dir / "phase4_recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    print(f"wrote {run_dir / 'phase4_recipe.json'}")
    bad = [t for t, e in recipe["adapters"].items() if e["status"].endswith("failed")]
    if bad:
        print("FAILED:", bad)
        sys.exit(1)


if __name__ == "__main__":
    main()
