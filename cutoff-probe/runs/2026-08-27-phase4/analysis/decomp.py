import sys, json, time
from pathlib import Path
from collections import defaultdict
import numpy as np
sys.path.insert(0, "/Volumes/nvme0/wave-consensus-repo/tools/phase4")
import consensus_eval as ce
from scipy.optimize import minimize

RNG = ce.RNG_SEED
splits = ce.article_ids_by_split()
test_ids, calib_ids = set(splits["test"]), set(splits["calibration"])
labels = ce.load_raw_labels()
truth = {
    (t, int(r["id"].split("-")[1])): ce.TRUE.index(ce.EXPECT[r["label"]])
    for t in (test_ids | calib_ids) for r in labels[t]
}
ft_dir = Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/finetuned/native")
meta = json.loads((ce.CORPUS/"pool"/"metadata.json").read_text())
articles = {t:(ce.CORPUS/"articles"/f"{t}.md").read_text() for t in test_ids|calib_ids}
feats = ce.build_features(test_ids|calib_ids, labels, meta, articles)

# trap_type per item
trap = {}
for tid in test_ids:
    for r in labels[tid]:
        i = int(r["id"].split("-")[1])
        m = next(x for x in meta[tid] if x["id"] == r["id"])
        trap[(tid, i)] = m["trap_type"]
trap_vocab = sorted({v for v in trap.values()})

cal_items = sorted(k for k in truth if k[0] in calib_ids)
test_items = sorted(k for k in truth if k[0] in test_ids)
t_te = np.array([truth[k] for k in test_items])

# full covariate (5 features incl trap_type), fit on calib
Xc = np.array([feats[k] for k in cal_items]); yc = np.array([truth[k] for k in cal_items])
Wc, norm = ce.fit_mlogit(Xc, yc)
ll_cov_i = np.empty(len(test_items))
for j, k in enumerate(test_items):
    P = ce.mlogit_predict(Wc, norm, np.array([feats[k]]))[0]
    ll_cov_i[j] = -np.log(P[t_te[j]] + 1e-12)
# content-only covariate (first 4 features), fit on calib
Wc2, norm2 = ce.fit_mlogit(Xc[:, :4], yc)
ll_cov2_i = np.empty(len(test_items))
for j, k in enumerate(test_items):
    P = ce.mlogit_predict(Wc2, norm2, np.array([feats[k][:4]]))[0]
    ll_cov2_i[j] = -np.log(P[t_te[j]] + 1e-12)

def em_post(native_dir, models, tids, rng, restarts=5):
    votes = ce.load_votes(native_dir, models, tids)
    items = sorted(k for k in truth if k[0] in tids)
    v = [votes.get(k, {}) for k in items]
    post = ce.fit_wct_em(v, rng, restarts=restarts)["posterior"]
    return post

def fit_calib(post_cal, y_cal):
    lp_cal = np.log(np.clip(post_cal,1e-9,None))
    def nll(p):
        a, b = p[:3], p[3:]
        z = a*lp_cal + b; z = z - z.max(1,keepdims=True)
        q = np.exp(z); q/=q.sum(1,keepdims=True)
        return -np.mean(np.log(q[np.arange(len(y_cal)), y_cal]+1e-12))
    res = minimize(nll, np.concatenate([[1,1,1],[0,0,0]]), method="Nelder-Mead",
                   options={"maxiter":3000,"xatol":1e-7,"fatol":1e-9})
    return res.x[:3], res.x[3:]

def apply_calib(lp, a, b):
    z = a*lp + b; z = z - z.max(1,keepdims=True)
    q = np.exp(z); q/=q.sum(1,keepdims=True)
    return q

art_list = sorted(set(k[0] for k in test_items))
items_by_art = defaultdict(list)
for j, k in enumerate(test_items): items_by_art[k[0]].append(j)
trap_idx = {t: [j for j, k in enumerate(test_items) if trap[k] == t] for t in trap_vocab}
rng_boot = np.random.default_rng(RNG+1)
B = 2000

print("trap sizes (test):", {t: len(v) for t, v in trap_idx.items()}, " total", len(test_items))
# content-only covariate point estimate + CI (fixed per-item losses, cheap)
d_full = ll_cov_i.mean() - 0  # placeholder
# per-article delta consistency + content-only CI in same loop? separate cheap loop:
delta_full_i = ll_cov_i  # will combine with em per arm below

for arm, models in [
    ("ft_votes_only",[f"{f}__votes_only" for f in ce.FAMILIES]),
    ("ft_reason_included",[f"{f}__reason_included" for f in ce.FAMILIES]),
]:
    t0 = time.time()
    rng = np.random.default_rng(RNG)
    post_cal = em_post(ft_dir, models, calib_ids, rng)
    y_cal = np.array([truth[k] for k in sorted(truth) if k[0] in calib_ids])
    a, b = fit_calib(post_cal, y_cal)
    post_te = em_post(ft_dir, models, test_ids, rng)
    q_te = apply_calib(np.log(np.clip(post_te,1e-9,None)), a, b)
    ll_em_i = -np.log(q_te[np.arange(len(test_items)), t_te] + 1e-12)
    # point estimates
    d_all = ll_cov_i.mean() - ll_em_i.mean()
    d_cov2 = ll_cov2_i.mean() - ll_em_i.mean()
    per_art = {}
    for art in art_list:
        js = items_by_art[art]
        per_art[art] = ll_cov_i[js].mean() - ll_em_i[js].mean()
    print(f"\n== {arm} ==")
    print(f"FULL delta {d_all:+.4f} | content-only cov delta {d_cov2:+.4f} (cov-only ll {ll_cov2_i.mean():.4f} vs full {ll_cov_i.mean():.4f})")
    print(f"per-article delta: " + " ".join(f"{a}:{v:+.3f}" for a, v in sorted(per_art.items())))
    print(f"articles with delta>0: {sum(1 for v in per_art.values() if v>0)}/{len(per_art)}")
    # bootstrap: one EM refit pass, aggregate everything inside
    boot_all = np.empty(B); boot_cov2 = np.empty(B)
    boot_trap = {t: np.empty(B) for t in trap_vocab}
    for bi in range(B):
        pick = [art_list[i] for i in rng_boot.integers(0, len(art_list), size=len(art_list))]
        idx = [j for art in pick for j in items_by_art[art]]
        votes = ce.load_votes(ft_dir, models, set(pick))
        v = [votes.get(test_items[j], {}) for j in idx]
        fb = ce.fit_wct_em(v, np.random.default_rng(RNG), restarts=0)
        q_b = apply_calib(np.log(np.clip(fb["posterior"],1e-9,None)), a, b)
        tb = np.array([truth[test_items[j]] for j in idx])
        llb = -np.log(q_b[np.arange(len(idx)), tb] + 1e-12)
        pos = {j: p for p, j in enumerate(idx)}
        def sel(arr): return arr[idx]
        boot_all[bi] = sel(ll_cov_i).mean() - llb.mean()
        boot_cov2[bi] = sel(ll_cov2_i).mean() - llb.mean()
        for t in trap_vocab:
            js_t = [j for j in idx if trap[test_items[j]] == t]
            if len(js_t) >= 10:
                pmap = [pos[j] for j in js_t]
                boot_trap[t][bi] = sel(ll_cov_i)[[pos[j] for j in js_t]].mean() - llb[[pos[j] for j in js_t]].mean()
            else:
                boot_trap[t][bi] = np.nan
    def ci(x):
        x = x[~np.isnan(x)]
        return float(np.percentile(x,2.5)), float(np.percentile(x,97.5)), len(x)
    c_all = ci(boot_all); c_cov2 = ci(boot_cov2)
    print(f"boot FULL delta {d_all:+.4f} CI [{c_all[0]:+.4f},{c_all[1]:+.4f}]")
    print(f"boot CONTENT-ONLY cov delta {d_cov2:+.4f} CI [{c_cov2[0]:+.4f},{c_cov2[1]:+.4f}]")
    for t in trap_vocab:
        dt = ll_cov_i[trap_idx[t]].mean() - ll_em_i[trap_idx[t]].mean()
        c = ci(boot_trap[t])
        print(f"  trap {t:16s} n={len(trap_idx[t]):3d} delta {dt:+.4f} CI [{c[0]:+.4f},{c[1]:+.4f}] (B={c[2]})")
    print(f"{time.time()-t0:.0f}s")
