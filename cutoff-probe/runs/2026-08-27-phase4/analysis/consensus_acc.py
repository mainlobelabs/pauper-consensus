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
    for t in test_ids
    for r in labels[t]
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
print("n test items:", len(items), "truth mix:", dict(zip(ce.TRUE, np.bincount(t, minlength=3))))
for arm, ms in arms.items():
    votes = ce.load_votes(ft_dir if arm != "base_zeroshot" else base_dir, ms, test_ids)
    v = [votes.get(k, {}) for k in items]
    fit = ce.fit_wct_em(v, rng)
    post = fit["posterior"]
    pred = post.argmax(axis=1)
    acc = (pred == t).mean()
    # gate = binary FAIL vs not-FAIL
    gate = ((pred == 1) == (t == 1)).mean()
    print(f"{arm}: acc3 {acc:.4f} gate {gate:.4f}")
    for ci, cn in enumerate(ce.TRUE):
        m = t == ci
        if m.sum():
            print(f"   {cn}: recall {(pred[m] == ci).mean():.4f} (n={int(m.sum())})")
    # individual jurors (parse-aware) for context
    for m in ms:
        ok = 0
        n = 0
        for j, k in enumerate(items):
            o = votes.get(k, {}).get(m)
            if o is None or o == "MISSING":
                continue
            n += 1
            ok += int(o == ce.TRUE[t[j]])
        print(f"   juror {m}: {ok}/{n} = {ok/n:.4f}")
