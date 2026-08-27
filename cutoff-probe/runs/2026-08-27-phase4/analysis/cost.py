import sys, json
from pathlib import Path
sys.path.insert(0,"/Volumes/nvme0/wave-consensus-repo/tools/phase4")
import consensus_eval as ce
test_ids=set(ce.article_ids_by_split()["test"])
FAM=list(ce.FAMILIES); models=[f"{f}__reason_included" for f in FAM]
ft_dir=Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/finetuned/native")
ti=to=0
for m in models:
    for r in ce.read_jsonl(ft_dir/f"{m}.jsonl"):
        if r["article"] in test_ids:
            u=r.get("usage") or {}; ti+=u.get("input_tokens",0); to+=u.get("completion_tokens",u.get("output_tokens",0))
sr=[r for r in ce.read_jsonl(Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/self-review/qwen3.8-27b.jsonl")) if r["article"] in test_ids]
si=sum((r.get("usage") or {}).get("prompt_tokens",0) for r in sr)
so=sum((r.get("usage") or {}).get("completion_tokens",0) for r in sr)
print(f"jury (4 fam x 400): in {ti} out {to} total {ti+to}")
print(f"self-review (27B x {len(sr)}): in {si} out {so} total {si+so}")
jtp=sum([3.2e9,4e9,3.8e9,4e9]); jeff=jtp*(ti+to); seff=27e9*(si+so)
print(f"raw compute effort: jury {jeff/1e18:.4f} Ptok  self-review {seff/1e18:.4f} Ptok  jury={jeff/seff*100:.1f}% of 27B")
def usd(t,o,pi,po): return t/1e6*pi+o/1e6*po
ju=usd(ti,to,0.20,0.60); su=usd(si,so,1.00,3.00)
print(f"USD proxy (4B .20/.60, 27B 1.00/3.00 per 1M): jury ${ju:.4f} self-review ${su:.4f} ratio {ju/su:.3f}")
print(f"tokens ratio jury/self-review = {(ti+to)/(si+so):.2f}x")
