import sys, json
from pathlib import Path
from collections import defaultdict
import numpy as np
sys.path.insert(0, "/Volumes/nvme0/wave-consensus-repo/tools/phase4")
import consensus_eval as ce

RNG=ce.RNG_SEED
splits=ce.article_ids_by_split(); test_ids=set(splits["test"])
labels=ce.load_raw_labels()
meta=json.loads((ce.CORPUS/"pool"/"metadata.json").read_text())
truth={(t,int(r["id"].split("-")[1])):ce.TRUE.index(ce.EXPECT[r["label"]]) for t in test_ids for r in labels[t]}
ft_dir=Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/finetuned/native")
FAM=list(ce.FAMILIES)
claims=json.load(open("/tmp/claims_final.json"))
# attach primary_prop
q2props=defaultdict(list)
for tid in test_ids:
    for r in meta[tid]:
        for q in r["seeded_by"]: q2props[(tid,q)].append(r["id"])
for c in claims:
    props=q2props.get((c["article"],c["question"]),[])
    c["primary_prop"]=props[0] if props else None
sr={}
for r in ce.read_jsonl(Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/self-review/qwen3.8-27b.jsonl")):
    p=r.get("parsed") or {}; sr[(r["article"],int(r["item"]))]=p.get("answer")
models=[f"{f}__reason_included" for f in FAM]
votes=ce.load_votes(ft_dir, models, test_ids)
items=sorted(truth); v=[votes.get(k,{}) for k in items]
post=ce.fit_wct_em(v, np.random.default_rng(RNG))["posterior"]
item_pos={k:j for j,k in enumerate(items)}
ppass={k: post[item_pos[k],0] for k in items}

real=[c for c in claims if not c["non_claim"] and c.get("judge_verdict")]
false_claims=[c for c in real if c["judge_verdict"]=="NO"]
gateable=[c for c in real if c["primary_prop"]]
print("defendant real claims:",len(real)," false:",len(false_claims),
      " abstain:",sum(1 for c in claims if c["non_claim"])," gateable:",len(gateable))
print("defendant raw false-claim rate (of answered):",round(len(false_claims)/len(real),4))
print("defendant answer rate:",round(len(real)/len(claims),4))

def jury_pass(tid,i): return ppass[(tid,i)]>=0.5
def sr_pass(tid,i): return sr.get((tid,i))=="PASS"
for name,gf in [("jury-gated",jury_pass),("self-review-gated",sr_pass)]:
    keep=[c for c in gateable if gf(c["article"],int(c["primary_prop"].split("-")[1]))]
    nf=sum(1 for c in keep if c["judge_verdict"]=="NO")
    print(f"{name}: survivors {len(keep)}/{len(gateable)}  false-claim rate {nf}/{len(keep)} = {round(nf/len(keep),4) if keep else 0}")

art_list=sorted(set(c["article"] for c in real))
by_art=defaultdict(list)
for c in real: by_art[c["article"]].append(c)
rngb=np.random.default_rng(RNG+2); diffs=np.empty(2000)
for bi in range(2000):
    pick=[art_list[i] for i in rngb.integers(0,len(art_list),size=len(art_list))]
    sub=[c for a in pick for c in by_art[a]]
    def rate(gf):
        keep=[c for c in sub if c["primary_prop"] and gf(c["article"],int(c["primary_prop"].split("-")[1]))]
        return sum(1 for c in keep if c["judge_verdict"]=="NO")/len(keep) if keep else 0.0
    diffs[bi]=rate(jury_pass)-rate(sr_pass)
print("boot CI (jury - self-review) false-claim rate:",
      round(float(np.percentile(diffs,2.5)),4), round(float(np.percentile(diffs,97.5)),4))

def usage(dir_, models_):
    ti=to=0
    for m in models_:
        for r in ce.read_jsonl(dir_/f"{m}.jsonl"):
            if r["article"] in test_ids:
                u=r.get("usage") or {}; ti+=u.get("input_tokens",0); to+=u.get("output_tokens",0)
    return ti,to
jt_i,jt_o=usage(ft_dir, models)
sr_recs=[r for r in ce.read_jsonl(Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/self-review/qwen3.8-27b.jsonl")) if r["article"] in test_ids]
st_i=sum((r.get("usage") or {}).get("input_tokens",0) for r in sr_recs)
st_o=sum((r.get("usage") or {}).get("output_tokens",0) for r in sr_recs)
print("\nCOST (test split, per 10 articles):")
print(f"  jury (4 fam reason_included x 400): in {jt_i} out {jt_o} total {jt_i+jt_o}")
print(f"  self-review (27B x 400): in {st_i} out {st_o} total {st_i+st_o}")
jt_params=sum([3.2e9,4e9,3.8e9,4e9]); jt_eff=jt_params*(jt_i+jt_o)
sr_eff=27e9*(st_i+st_o)
print(f"  raw compute effort: jury {jt_eff/1e18:.3f} Ptok  self-review {sr_eff/1e18:.3f} Ptok")
print(f"  jury effort = {jt_eff/sr_eff*100:.1f}% of 27B")
# USD under stated amortized serving price assumption (per 1M tokens)
# assume 4B class ~ $0.20/1M in, $0.60/1M out ; 27B ~ $1.00/1M in, $3.00/1M out (amortized homelab proxy)
def usd(ti,to,pi,po): return ti/1e6*pi + to/1e6*po
print(f"  USD proxy (4B $0.20/$0.60 per 1M; 27B $1.00/$3.00 per 1M):")
print(f"    jury ${usd(jt_i,jt_o,0.20,0.60):.4f}   self-review ${usd(st_i,st_o,1.00,3.00):.4f}")
print(f"    ratio jury/self-review = {usd(jt_i,jt_o,0.20,0.60)/usd(st_i,st_o,1.00,3.00):.3f}")
