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
base_dir = Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/native")
meta = json.loads((ce.CORPUS/"pool"/"metadata.json").read_text())
articles = {t:(ce.CORPUS/"articles"/f"{t}.md").read_text() for t in test_ids|calib_ids}
feats = ce.build_features(test_ids|calib_ids, labels, meta, articles)

# fixed covariate (fit on calib)
cal_items = sorted(k for k in truth if k[0] in calib_ids)
test_items = sorted(k for k in truth if k[0] in test_ids)
Xc = np.array([feats[k] for k in cal_items]); yc = np.array([truth[k] for k in cal_items])
Wc, norm = ce.fit_mlogit(Xc, yc)
P_cov = {k: ce.mlogit_predict(Wc, norm, np.array([feats[k]]))[0] for k in test_items}

def em_post(native_dir, models, tids, rng):
    votes = ce.load_votes(native_dir, models, tids)
    items = sorted(k for k in truth if k[0] in tids)
    v = [votes.get(k, {}) for k in items]
    post = ce.fit_wct_em(v, rng)["posterior"]
    t = np.array([truth[k] for k in items])
    return post, t, items, votes

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
for j,k in enumerate(test_items): items_by_art[k[0]].append(j)
rng_boot = np.random.default_rng(RNG+1)
B = 2000

for arm, models, d in [
    ("ft_reason_included",[f"{f}__reason_included" for f in ce.FAMILIES],ft_dir),
    ("ft_votes_only",[f"{f}__votes_only" for f in ce.FAMILIES],ft_dir),
    ("base_zeroshot",list(ce.FAMILIES),base_dir),
]:
    t0=time.time()
    # calib map (fit once)
    rng = np.random.default_rng(RNG)
    post_cal, y_cal, _, _ = em_post(d, models, calib_ids, rng)
    a, b = fit_calib(post_cal, y_cal)
    # point estimate on full test
    rng = np.random.default_rng(RNG)
    post_te, t_te, _, _ = em_post(d, models, test_ids, rng)
    q_te = apply_calib(np.log(np.clip(post_te,1e-9,None)), a, b)
    ll_cov_pt = ce.logloss(np.array([P_cov[k] for k in test_items]), t_te)
    ll_em_pt = ce.logloss(q_te, t_te)
    # bootstrap
    deltas = np.empty(B)
    for bi in range(B):
        pick = [art_list[i] for i in rng_boot.integers(0,len(art_list),size=len(art_list))]
        idx = [j for a_ in pick for j in items_by_art[a_]]
        # refit EM on resampled votes
        votes = ce.load_votes(d, models, set(pick))
        v = [votes.get(k, {}) for k in [test_items[i] for i in idx]]
        fb = ce.fit_wct_em(v, np.random.default_rng(RNG), restarts=0)
        post_b = fb["posterior"]
        q_b = apply_calib(np.log(np.clip(post_b,1e-9,None)), a, b)
        tb = np.array([truth[test_items[i]] for i in idx])
        cov_b = np.array([P_cov[test_items[i]] for i in idx])
        deltas[bi] = ce.logloss(cov_b, tb) - ce.logloss(q_b, tb)
    ci = (float(np.percentile(deltas,2.5)), float(np.percentile(deltas,97.5)))
    print(f"{arm}: cov {ll_cov_pt:.4f} | EM-cal {ll_em_pt:.4f} | delta {ll_cov_pt-ll_em_pt:+.4f} | boot CI {ci[0]:+.4f},{ci[1]:+.4f} | passes 0.02+CI>0: {ll_cov_pt-ll_em_pt>=0.02 and ci[0]>0} | {time.time()-t0:.1f}s")
