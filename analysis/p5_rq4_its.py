"""Pre-registered RQ4 ITS + registry cohort descriptives (prereg + A1/A2).
Computes from the daily registry dump. ALL OUTPUT LABELED preliminary=True until the
2026-10-10 freeze; reproduce at freeze regenerates identically-structured JSON.
- RQ4: weekly->2-week-bin version-publication rate, ±8 weeks around 2026-07-28;
  OLS level+slope with HAC(4); placebo at 2026-06-15; robustness excluding release week.
- Cohorts (A1 §6): pre-RC / RC-era / post-release counts + publisher concentration (A2).
"""
import json, gzip, glob, os, datetime
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
DUMP = sorted(glob.glob(os.path.join(BASE, "data/registry/registry_*.jsonl.gz")))[-1]
OUT = os.path.join(HERE, "p5_rq4_results.json")
RELEASE = datetime.date(2026, 7, 28)
RC = datetime.date(2026, 5, 29)
PLACEBO = datetime.date(2026, 6, 15)

pub_dates = []
first_pub = {}
publishers = defaultdict(set)
for line in gzip.open(DUMP, "rt"):
    d = json.loads(line)
    meta = (d.get("_meta") or {}).get("io.modelcontextprotocol.registry/official") or {}
    p = meta.get("publishedAt")
    if not p:
        continue
    dt = datetime.date.fromisoformat(p[:10])
    name = d["server"]["name"]
    pub_dates.append(dt)
    if name not in first_pub or dt < first_pub[name]:
        first_pub[name] = dt
    publishers[name.split("/")[0]].add(name)

def its(center, exclude_release_week=False):
    # 2-week bins, +/- 8 weeks around center (8 bins total: 4 pre, 4 post).
    # PRELIMINARY GUARD: only bins fully elapsed by generation date are included; the
    # full pre-registered window completes at the 2026-10-10 freeze.
    today = datetime.date.today()
    bins = []
    for k in range(-4, 4):
        lo = center + datetime.timedelta(days=14 * k)
        hi = lo + datetime.timedelta(days=13)
        if hi >= today:
            continue  # incomplete bin — excluded until freeze
        if exclude_release_week and lo <= RELEASE <= hi:
            continue
        n = sum(1 for x in pub_dates if lo <= x <= hi)
        bins.append({"k": k, "start": lo.isoformat(), "n": n, "post": 1 if k >= 0 else 0})
    # OLS: n ~ b0 + b1*k + b2*post + b3*k*post ; HAC(4) SEs (Newey-West).
    # PRELIMINARY GUARDS: 0 complete post bins -> not estimable; <3 -> level-only model.
    n_post = sum(b["post"] for b in bins)
    if n_post == 0:
        return {"bins": bins, "n_post_bins": 0, "slope_estimable": False,
                "note": "no complete post bins under this specification yet — estimable at freeze"}
    slope_est = n_post >= 3
    if slope_est:
        X = np.array([[1, b["k"], b["post"], b["k"] * b["post"]] for b in bins], float)
    else:
        X = np.array([[1, b["k"], b["post"]] for b in bins], float)
    y = np.array([b["n"] for b in bins], float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n_, p_ = X.shape
    XtXi = np.linalg.inv(X.T @ X)
    L = 4
    S = np.zeros((p_, p_))
    for i in range(n_):
        S += resid[i] ** 2 * np.outer(X[i], X[i])
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        for i in range(l, n_):
            G = np.outer(X[i], X[i - l]) * resid[i] * resid[i - l]
            S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    se = np.sqrt(np.diag(V))
    return {"bins": bins, "n_post_bins": n_post, "slope_estimable": slope_est,
            "coef": {"level_b2": round(float(beta[2]), 2),
                     "slope_b3": round(float(beta[3]), 2) if slope_est else None},
            "se_hac4": {"level": round(float(se[2]), 2),
                        "slope": round(float(se[3]), 2) if slope_est else None},
            "t": {"level": round(float(beta[2] / se[2]), 2) if se[2] > 0 else None,
                  "slope": (round(float(beta[3] / se[3]), 2) if se[3] > 0 else None) if slope_est else None}}

coh = Counter()
for name, fp in first_pub.items():
    coh["pre_RC" if fp < RC else "RC_era" if fp < RELEASE else "post_release"] += 1
top_pub = sorted(publishers.items(), key=lambda kv: -len(kv[1]))[:5]
n_servers = len(first_pub)
hhi = sum((len(v) / n_servers) ** 2 for v in publishers.values())

res = {
    "preliminary": True, "dump": os.path.basename(DUMP), "generated": datetime.date.today().isoformat(),
    "note": "PRELIMINARY — regenerate at 2026-10-10 freeze; structure frozen",
    "cohorts": dict(coh), "n_servers": n_servers, "n_publishers": len(publishers),
    "publisher_concentration": {"top5": [{"pub": k, "servers": len(v)} for k, v in top_pub],
                                 "hhi": round(hhi, 5)},
    "RQ4_ITS_release": its(RELEASE),
    "RQ4_ITS_placebo_2026-06-15": its(PLACEBO),
    "RQ4_ITS_release_excl_release_week": its(RELEASE, exclude_release_week=True),
}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "RQ4_ITS_release_excl_release_week"}, indent=1)[:2600])
print("saved", OUT)
