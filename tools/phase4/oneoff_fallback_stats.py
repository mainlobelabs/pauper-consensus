"""One-off: parse rate + 3-state accuracy for base/fallback models.

Usage: python3.11 tools/phase4/oneoff_fallback_stats.py <native-jsonl> <model>
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase3"))
from analyze import EXPECT, article_ids_by_split, load_labels  # noqa: E402

splits = article_ids_by_split()
split_of = {t: s for s, ids in splits.items() for t in ids}
labels = load_labels()
path, model = sys.argv[1], sys.argv[2]
recs = [json.loads(line) for line in open(path) if line.strip()]
stat = defaultdict(lambda: [0, 0, 0])  # split -> [n, parsed, correct]
for r in recs:
    s = split_of[r["article"]]
    tid = r["article"]
    p = r.get("parsed")
    stat[s][0] += 1
    if p:
        stat[s][1] += 1
        want = EXPECT[labels[tid][f"{tid}-{r['item']:03d}"]]
        stat[s][2] += p.get("answer") == want
print(model)
for s in ["train", "calibration", "test"]:
    n, parsed, correct = stat[s]
    if n:
        if parsed:
            print(f"  {s}: n={n} parsed={parsed} ({parsed / n:.4f}) acc={correct / parsed:.4f}")
        else:
            print(f"  {s}: n={n} parsed=0")
