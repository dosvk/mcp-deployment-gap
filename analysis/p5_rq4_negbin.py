"""A3 PRIMARY RQ4 model: Negative-Binomial (log link) segmented regression on WEEKLY
registry version-publication counts. Null = exponential growth (log-linear trend).
Dual placebos (2026-06-15, 2026-05-04) + release-week-exclusion robustness.
PRELIMINARY until 2026-10-10 freeze; incomplete trailing weeks excluded.
"""
import json, gzip, glob, os, datetime
import numpy as np
import statsmodels.api as sm

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
DUMP = sorted(glob.glob(os.path.join(BASE, "data/registry/registry_*.jsonl.gz")))[-1]
OUT = os.path.join(HERE, "p5_rq4_negbin_results.json")
RELEASE = datetime.date(2026, 7, 28)

pub_dates = []
for line in gzip.open(DUMP, "rt"):
    d = json.loads(line)
    meta = (d.get("_meta") or {}).get("io.modelcontextprotocol.registry/official") or {}
    p = meta.get("publishedAt")
    if p:
        pub_dates.append(datetime.date.fromisoformat(p[:10]))

def weekly_counts(center, weeks=8):
    """weeks pre + weeks post (week 0 = week starting at center); only complete weeks."""
    today = datetime.date.today()
    rows = []
    for k in range(-weeks, weeks):
        lo = center + datetime.timedelta(days=7 * k)
        hi = lo + datetime.timedelta(days=6)
        if hi >= today:
            continue
        n = sum(1 for x in pub_dates if lo <= x <= hi)
        rows.append({"k": k, "start": lo.isoformat(), "n": n, "post": 1 if k >= 0 else 0})
    return rows

def negbin_segmented(center, exclude_release_week=False):
    rows = weekly_counts(center)
    if exclude_release_week:
        rows = [r for r in rows
                if not (datetime.date.fromisoformat(r["start"]) <= RELEASE
                        <= datetime.date.fromisoformat(r["start"]) + datetime.timedelta(days=6))]
    n_post = sum(r["post"] for r in rows)
    if n_post == 0:
        return {"rows": rows, "n_post_weeks": 0, "note": "no complete post weeks — at freeze"}
    slope_est = n_post >= 3
    y = np.array([r["n"] for r in rows], float)
    cols = [np.ones(len(rows)), np.array([r["k"] for r in rows], float),
            np.array([r["post"] for r in rows], float)]
    names = ["const", "trend", "level"]
    if slope_est:
        cols.append(np.array([r["k"] * r["post"] for r in rows], float))
        names.append("slope")
    X = np.column_stack(cols)
    try:
        m = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=1.0)).fit()
        # profile alpha crudely over a grid (statsmodels GLM needs fixed alpha)
        best = (None, np.inf)
        for a in [0.01, 0.05, 0.1, 0.3, 0.5, 1.0]:
            try:
                fit = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=a)).fit()
                if fit.aic < best[1]:
                    best = (fit, best[1] if fit is None else fit.aic, a) if False else (fit, fit.aic)
                    best_alpha = a
            except Exception:
                continue
        m = best[0] if best[0] is not None else m
        out = {"rows": rows, "n_post_weeks": int(n_post), "slope_estimable": bool(slope_est),
               "alpha_grid_best": best_alpha,
               "coef_multiplicative": {}, "p": {}}
        for i, nm in enumerate(names):
            out["coef_multiplicative"][nm] = round(float(np.exp(m.params[i])), 4)
            out["p"][nm] = float(f"{m.pvalues[i]:.4g}")
        return out
    except Exception as e:
        return {"rows": rows, "error": str(e)[:200]}

res = {
    "preliminary": True, "generated": datetime.date.today().isoformat(),
    "dump": os.path.basename(DUMP), "model": "NegBin log-link segmented (A3 primary)",
    "release": negbin_segmented(RELEASE),
    "release_excl_week": negbin_segmented(RELEASE, exclude_release_week=True),
    "placebo_2026-06-15": negbin_segmented(datetime.date(2026, 6, 15)),
    "placebo_2026-05-04": negbin_segmented(datetime.date(2026, 5, 4)),
}
json.dump(res, open(OUT, "w"), indent=1)
for k in ["release", "release_excl_week", "placebo_2026-06-15", "placebo_2026-05-04"]:
    r = res[k]
    if "coef_multiplicative" in r:
        lvl = r["coef_multiplicative"].get("level"); pl = r["p"].get("level")
        sl = r["coef_multiplicative"].get("slope"); ps = r["p"].get("slope")
        print(f"{k:28s} level x{lvl} (p={pl})  slope x{sl} (p={ps})  post_weeks={r['n_post_weeks']}")
    else:
        print(f"{k:28s} {r.get('note') or r.get('error')}")
print("saved", OUT)
