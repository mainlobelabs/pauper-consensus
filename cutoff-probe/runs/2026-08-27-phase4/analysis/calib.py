import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "/Volumes/nvme0/wave-consensus-repo/tools/phase4")
import consensus_eval as ce
from scipy.optimize import minimize_scalar, minimize

splits = ce.article_ids_by_split()
test_ids, calib_ids = set(splits["test"]), set(splits["calibration"])
labels = ce.load_raw_labels()
truth = {
    (t, int(r["id"].split("-")[1])): ce.TRUE.index(ce.EXPECT[r["label"]])
    for t in (test_ids | calib_ids) for r in labels[t]
}
ft_dir = Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase4/finetuned/native")
base_dir = Path("/Volumes/nvme0/wave-consensus/runs/2026-08-26-phase3/native")

def em_post(native_dir, models, tids, rng):
    votes = ce.load_votes(native_dir, models, tids)
    items = sorted(k for k in truth if k[0] in tids)
    v = [votes.get(k, {}) for k in items]
    post = ce.fit_wct_em(v, rng)["posterior"]
    t = np.array([truth[k] for k in items])
    return post, t, items

# covariate on test (fit on calib) as in eval
rng0 = np.random.default_rng(ce.RNG_SEED)
meta = __import__("json").loads((ce.CORPUS/"pool"/"metadata.json").read_text())
articles = {t:(ce.CORPUS/"articles"/f"{t}.md").read_text() for t in test_ids|calib_ids}
feats = ce.build_features(test_ids|calib_ids, labels, meta, articles)
cal_items = sorted(k for k in truth if k[0] in calib_ids)
test_items = sorted(k for k in truth if k[0] in test_ids)
Xc = np.array([feats[k] for k in cal_items]); yc = np.array([truth[k] for k in cal_items])
Wc, norm = ce.fit_mlogit(Xc, yc)
Xt = np.array([feats[k] for k in test_items]); tt = np.array([truth[k] for k in test_items])
P_cov = ce.mlogit_predict(Wc, norm, Xt)
ll_cov = ce.logloss(P_cov, tt)

def calib_map(logpost_cal, y_cal, logpost_test):
    # 3-class affine (Platt-like) on logits: q_c = softmax(a*logpost_c + b_c)
    lp_cal = np.log(np.clip(logpost_cal,1e-9,None))
    lp_te = np.log(np.clip(logpost_test,1e-9,None))
    def nll(p):
        a, b = p[:3], p[3:]
        z = a*lp_cal + b
        z = z - z.max(1,keepdims=True)
        q = np.exp(z); q/=q.sum(1,keepdims=True)
        return -np.mean(np.log(q[np.arange(len(y_cal)), y_cal]+1e-12))
    p0 = np.concatenate([[1.0,1.0,1.0],[0.0,0.0,0.0]])
    res = minimize(nll, p0, method="Nelder-Mead", options={"maxiter":2000,"xatol":1e-6,"fatol":1e-8})
    a, b = res.x[:3], res.x[3:]
    z = a*lp_te + b; z = z - z.max(1,keepdims=True)
    q = np.exp(z); q/=q.sum(1,keepdims=True)
    return q, res.fun

for arm, models, d in [
    ("ft_reason_included",[f"{f}__reason_included" for f in ce.FAMILIES],ft_dir),
    ("ft_votes_only",[f"{f}__votes_only" for f in ce.FAMILIES],ft_dir),
    ("base_zeroshot",list(ce.FAMILIES),base_dir),
]:
    rng = np.random.default_rng(ce.RNG_SEED)
    post_cal, y_cal, _ = em_post(d, models, calib_ids, rng)
    rng = np.random.default_rng(ce.RNG_SEED)
    post_te, t_te, _ = em_post(d, models, test_ids, rng)
    ll_raw = ce.logloss(post_te, t_te)
    q_cal, _ = calib_map(post_cal, y_cal, post_te)
    ll_cal = ce.logloss(q_cal, t_te)
    # temperature only
    def temp_nll(logT):
        T = 1.0/np.clip(logT, -4, 4) if False else np.exp(logT)
        lp = np.log(np.clip(post_te,1e-9,None))/T
        lp = lp-lp.max(1,keepdims=True); q=np.exp(lp); q/=q.sum(1,keepdims=True)
        return ce.logloss(q, t_te)
    # fit T on calib
    def temp_nll_cal(logT):
        T = np.exp(logT)
        lp = np.log(np.clip(post_cal,1e-9,None))/T
        lp=lp-lp.max(1,keepdims=True); q=np.exp(lp); q/=q.sum(1,keepdims=True)
        return ce.logloss(q, y_cal)
    Tfit = minimize_scalar(temp_nll_cal, bounds=(0.3,3.0), method="bounded").x
    T = np.exp(Tfit)
    lp = np.log(np.clip(post_te,1e-9,None))/T
    lp=lp-lp.max(1,keepdims=True); qT=np.exp(lp); qT/=qT.sum(1,keepdims=True)
    ll_temp = ce.logloss(qT, t_te)
    print(f"{arm}: cov {ll_cov:.4f} | EM raw {ll_raw:.4f} (delta {ll_cov-ll_raw:+.4f}) | EM temp {ll_temp:.4f} (T={T:.3f}, delta {ll_cov-ll_temp:+.4f}) | EM 3classPlatt {ll_cal:.4f} (delta {ll_cov-ll_cal:+.4f})")
