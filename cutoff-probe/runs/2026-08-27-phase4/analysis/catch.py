import sys
from pathlib import Path
sys.path.insert(0, "/Volumes/nvme0/wave-consensus-repo/tools/phase4")
import numpy as np
import consensus_eval as ce

rng = np.random.default_rng(ce.RNG_SEED)
splits = ce.article_ids_by_split()
test_ids = set(splits["test"])
labels = ce.load_raw_labels()
truth = {
    (t, int(r["id"].split("-")[1])): ce.TRUE.index(ce.EXPECT[r["label"]])
    for t in test_ids for r in labels[t]
}
ft_dir = Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/finetuned/native")
base_dir = Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/native")
arms = {
    "ft_reason_included": [f"{f}__reason_included" for f in ce.FAMILIES],
    "ft_votes_only": [f"{f}__votes_only" for f in ce.FAMILIES],
    "base_zeroshot": list(ce.FAMILIES),
}
items = sorted(truth)
t = np.array([truth[k] for k in items])
fail_idx = t == 1   # CONTRADICT = the "false claims" to catch

for arm, ms in arms.items():
    votes = ce.load_votes(ft_dir if arm != "base_zeroshot" else base_dir, ms, test_ids)
    # per-juror catch: among true FAILs, how many did the juror vote FAIL
    print(f"== {arm} ==  (n true FAIL={int(fail_idx.sum())})")
    best = None
    for m in ms:
        catch = 0; flagged = 0; n_flag_truth = 0
        for j, k in enumerate(items):
            o = votes.get(k, {}).get(m)
            if o is None or o == "MISSING":
                continue
            pred_fail = (o == "FAIL")
            if pred_fail:
                flagged += 1
                if t[j] == 1: catch += 1
                else: n_flag_truth += 1
        recall = catch / fail_idx.sum()
        prec = catch / max(flagged, 1)
        print(f"   {m}: catch_recall {recall:.3f}  flag_prec {prec:.3f}  (flagged {flagged})")
        if best is None or recall > best[1]:
            best = (m, recall)
    # consensus catch
    v = [votes.get(k, {}) for k in items]
    post = ce.fit_wct_em(v, rng)["posterior"]
    pred = post.argmax(axis=1)
    cons_catch = ((pred[fail_idx] == 1).mean())
    cons_flagged = int((pred == 1).sum())
    cons_prec = int(((pred == 1) & (t == 1)).sum()) / max(cons_flagged,1)
    print(f"   CONSENSUS: catch_recall {cons_catch:.3f}  flag_prec {cons_prec:.3f}  (flagged {cons_flagged})")
    print(f"   best single = {best[0]} {best[1]:.3f}  -> consensus {'BEATS' if cons_catch>best[1] else '<='} best single by {cons_catch-best[1]:+.3f}")
