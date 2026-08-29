"""Unregistered v5.1 sensitivity: refit the model-free bars on v2 itself.

The registered bars are frozen from v1 (fit on the v1 calibration split,
applied to v2). The v2 content bar's polarity feature shifts regime
(negative-polarity base rate 18.5% v1 -> 2.0% v2), so part of the headline
delta's growth (+0.093 v1 smoke -> +0.203 v2) is comparator weakening, not
jury improvement. This script quantifies that: refit the content-only and
full covariate bars on the full v2 corpus (fit == eval; UNREGISTERED,
descriptive only) and re-compute the headline deltas.

Deterministic (fit_mlogit seed 0, same L2/lr/iters as the frozen fits).
Usage (repo .venv python, needs numpy):
  .venv/bin/python tools/corpus_v2/v2_refit_sensitivity.py
Output: runs/2026-08-29-v51/v2_refit_sensitivity.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "phase4"))
sys.path.insert(0, str(REPO / "tools" / "corpus_v2"))
import consensus_eval as ce  # noqa: E402
import eval_v2 as ev  # noqa: E402

CORPUS = REPO / "corpus-v2"
FROZEN = REPO / "corpus-v2/frozen/v1_baselines.json"
EVAL = REPO / "runs/2026-08-28-v2-jury/eval_v2.json"
OUT = REPO / "runs/2026-08-29-v51/v2_refit_sensitivity.json"


def main() -> None:
    frozen = json.loads(FROZEN.read_text())
    c = ev.load_corpus(CORPUS)
    data = ev.build_items(c, frozen["covariate_spec"]["trap_vocab_order"])
    items, truth, X8 = data["items"], data["truth"], data["X8"]
    n = len(items)
    assert n == 8000, n

    # v2 truth label mix (polarity of the latent-truth distribution)
    mix = np.bincount(truth, minlength=3) / n
    pol = {t: float(x) for t, x in zip(ce.TRUE, mix, strict=True)}

    # Refit on all of v2 (fit == eval, unregistered)
    Wc, nc = ce.fit_mlogit(X8[:, :4], truth)
    Wf, nf = ce.fit_mlogit(X8, truth)
    ll_content = ce.logloss(ce.mlogit_predict(Wc, nc, X8[:, :4]), truth)
    ll_full = ce.logloss(ce.mlogit_predict(Wf, nf, X8), truth)

    # Frozen v2 numbers (from the verified eval run)
    cells = json.loads(EVAL.read_text())["cells"]
    em_ll = {arm: cells[f"content_{arm}"]["em_cal_logloss"] for arm in
             ("ft_reason_included", "ft_votes_only")}
    frozen_bar = {"content": cells["content_ft_reason_included"]["bar_logloss"],
                  "full": cells["full_ft_reason_included"]["bar_logloss"]}

    out = {
        "description": (
            "Unregistered v5.1 sensitivity: v2-refit model-free bars (fit == eval). "
            "Headline deltas vs v2-refit bars quantify how much of the v1->v2 delta "
            "growth is comparator weakening under the polarity-shift regime. "
            "NOT a pre-registered quantity."
        ),
        "n_items": n,
        "v2_truth_mix": pol,
        "refit_content_bar_ll": round(float(ll_content), 5),
        "refit_full_bar_ll": round(float(ll_full), 5),
        "frozen_content_bar_ll_v2": frozen_bar["content"],
        "frozen_full_bar_ll_v2": frozen_bar["full"],
        "em_cal_logloss_v2": em_ll,
        "headline_delta_frozen_bar": round(frozen_bar["content"] - em_ll["ft_reason_included"], 5),
        "headline_delta_refit_bar": round(float(ll_content) - em_ll["ft_reason_included"], 5),
        "votes_only_delta_refit_bar": round(float(ll_content) - em_ll["ft_votes_only"], 5),
        "fullbar_delta_refit_bar": round(float(ll_full) - em_ll["ft_reason_included"], 5),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for k, v in out.items():
        if k != "description":
            print(f"{k}: {v}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
