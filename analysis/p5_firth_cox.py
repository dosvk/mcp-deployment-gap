"""F1 FIX: Firth-penalized Cox for the sparse npm stratum (review finding 1).
lifelines has no native Firth; we implement the Firth penalty on the Cox partial likelihood
directly (Heinze & Schemper 2001): penalized score U*(b) = U(b) + a * trace(I^-1 dI/db) with
a=0.5, maximized by Newton steps on the analytic Cox gradient/Hessian. Profile-likelihood CIs.
Cross-checked against a ridge-penalized lifelines fit as a sanity bound. Reads the same
survival rows as p5_survival.py. Output: p5_firth_cox_results.json (PRELIMINARY).
"""
import json, os, datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
G2 = os.path.join(os.path.dirname(HERE), "gate2")
OUT = os.path.join(HERE, "p5_firth_cox_results.json")
TODAY = datetime.date.today()
ORIGIN = {"rust": datetime.date(2026, 6, 23), "go": datetime.date(2026, 6, 24),
          "npm": datetime.date(2026, 6, 25)}

# ---- rebuild the same rows as p5_survival.py (self-contained) ----
rows = []
for eco in ["rust", "go", "npm"]:
    hyd = {}
    for line in open(os.path.join(G2, f"hydrated_{eco}.jsonl")):
        d = json.loads(line)
        if not d.get("missing"):
            hyd[d["repo"]] = d
    sample = {m["repo"]: m for m in json.load(open(os.path.join(G2, f"sample_{eco}.json")))["members"]}
    events = {}
    for line in open(os.path.join(G2, f"events_{eco}.jsonl")):
        d = json.loads(line)
        if d.get("first_capable_commit"):
            events[d["repo"]] = datetime.date.fromisoformat(d["first_capable_commit"]["date"])
    for repo, m in sample.items():
        h = hyd.get(repo)
        if not h:
            continue
        created = datetime.date.fromisoformat(h["created"][:10])
        start = max(ORIGIN[eco], created)
        ev = events.get(repo)
        if ev and ev < start:
            ev = start
        end = ev or TODAY
        t = max((end - start).days, 0) + 0.5
        rows.append({"eco": eco, "t": t, "event": 1 if ev else 0,
                     "org": 1 if h["owner_type"] == "Organization" else 0,
                     "log_stars": float(np.log1p(h["stars"])),
                     "age_yrs": max((ORIGIN[eco] - created).days, 0) / 365.25})

# design matrix: eco dummies (go = reference), + covariates
def design(rows):
    X, y, e = [], [], []
    for r in rows:
        X.append([1.0 if r["eco"] == "npm" else 0.0,
                  1.0 if r["eco"] == "rust" else 0.0,
                  r["org"], r["log_stars"], r["age_yrs"]])
        y.append(r["t"]); e.append(r["event"])
    return np.array(X), np.array(y), np.array(e)

names = ["eco_npm", "eco_rust", "org", "log_stars", "age_yrs"]
X, y, evt = design(rows)
n, p = X.shape
order = np.argsort(-y)  # descending time -> risk sets are prefixes
Xo, yo, eo = X[order], y[order], evt[order]

def cox_terms(beta):
    """Breslow partial-likelihood gradient U and info I, plus dI/dbeta for Firth."""
    eta = Xo @ beta
    w = np.exp(eta)
    U = np.zeros(p); I = np.zeros((p, p))
    # risk set = all j with yo[j] >= yo[i]; since sorted desc, risk set for i is indices 0..k
    # accumulate from top (largest time) downward
    S0 = 0.0; S1 = np.zeros(p); S2 = np.zeros((p, p))
    for i in range(n):
        S0 += w[i]; S1 += w[i] * Xo[i]; S2 += w[i] * np.outer(Xo[i], Xo[i])
        if eo[i] == 1:
            xbar = S1 / S0
            U += Xo[i] - xbar
            I += S2 / S0 - np.outer(xbar, xbar)
    return U, I

def firth_fit(a=0.5, iters=60):
    beta = np.zeros(p)
    for _ in range(iters):
        U, I = cox_terms(beta)
        try:
            Iinv = np.linalg.inv(I + 1e-8 * np.eye(p))
        except np.linalg.LinAlgError:
            break
        # Firth adjustment via numerical trace term: penalized score
        h = 1e-5; adj = np.zeros(p)
        for k in range(p):
            bk = beta.copy(); bk[k] += h
            _, Ik = cox_terms(bk)
            dI = (Ik - I) / h
            adj[k] = 0.5 * np.trace(Iinv @ dI)
        step = Iinv @ (U + adj)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-6:
            break
    _, I = cox_terms(beta)
    se = np.sqrt(np.diag(np.linalg.inv(I + 1e-8 * np.eye(p))))
    return beta, se

beta, se = firth_fit()
res = {"preliminary": True, "generated": TODAY.isoformat(),
       "method": "Firth-penalized Cox (Heinze-Schemper), Breslow ties, numeric trace adjustment",
       "reference": "go ecosystem", "n": n, "events": int(evt.sum()),
       "events_by_eco": {e: int(sum(r["event"] for r in rows if r["eco"] == e)) for e in ORIGIN},
       "coef": {}}
for i, nm in enumerate(names):
    res["coef"][nm] = {"HR": round(float(np.exp(beta[i])), 4),
                        "beta": round(float(beta[i]), 4),
                        "se": round(float(se[i]), 4)}

# sanity comparison: ridge-penalized lifelines
try:
    import pandas as pd
    from lifelines import CoxPHFitter
    df = pd.DataFrame([{**{nm: X[j, k] for k, nm in enumerate(names)},
                        "t": y[j], "event": evt[j]} for j in range(n)])
    cph = CoxPHFitter(penalizer=0.02, l1_ratio=0.0).fit(df, "t", "event")
    res["n_provenance"] = "3,600 = go+rust+npm sampled repos with hydration; maven (666) excluded (no adoption possible, structural zero); 256 events"
    res["light_ridge_check_HR"] = {nm: round(float(np.exp(cph.params_[nm])), 4) for nm in names}
except Exception as ex:
    res["n_provenance"] = "3,600 = go+rust+npm sampled repos with hydration; maven (666) excluded (no adoption possible, structural zero); 256 events"
    res["light_ridge_check_HR"] = {"error": str(ex)[:150]}

json.dump(res, open(OUT, "w"), indent=1)
print("Firth npm HR:", res["coef"]["eco_npm"], "(was raw HR 0.02, p=4.5e-21 on 6 events)")
print("ridge sanity npm HR:", res.get("ridge_check_HR", {}).get("eco_npm"))
print("saved", OUT)

# ---- profile-likelihood CI for eco_npm (the sparse coefficient) ----
def firth_penalized_loglik(beta):
    # penalized log partial likelihood = l(beta) + 0.5*log det I(beta)
    eta = Xo @ beta; w = np.exp(eta)
    S0 = 0.0; ll = 0.0; _, I = cox_terms(beta)
    S0acc = 0.0
    # recompute Breslow log-lik
    S0 = 0.0
    ll = 0.0
    S0v = 0.0
    acc = 0.0
    S0run = 0.0
    S0tot = []
    run = 0.0
    for i in range(n):
        run += w[i]
        if eo[i] == 1:
            ll += eta[i] - np.log(run)
    sign, logdet = np.linalg.slogdet(I + 1e-8*np.eye(p))
    return ll + 0.5*logdet

def profile_ci_npm(beta_hat, se_hat):
    import numpy as _np
    from scipy.optimize import minimize
    idx = 0  # eco_npm
    lmax = firth_penalized_loglik(beta_hat)
    target = lmax - 1.920729  # chi2_1(0.95)/2
    def profile_at(b0):
        # fix beta[idx]=b0, optimize the rest
        free = [k for k in range(p) if k != idx]
        def negll(bf):
            b = _np.array(beta_hat); b[idx] = b0
            for j,k in enumerate(free): b[k] = bf[j]
            return -firth_penalized_loglik(b)
        r = minimize(negll, beta_hat[free], method="Nelder-Mead",
                     options={"xatol":1e-3,"fatol":1e-3,"maxiter":4000})
        return -r.fun
    # search each side
    def find(direction):
        lo, hi = beta_hat[idx], beta_hat[idx] + direction*6*max(se_hat[idx],0.3)
        for _ in range(40):
            mid = (lo+hi)/2
            if profile_at(mid) > target: lo = mid
            else: hi = mid
        return (lo+hi)/2
    return find(-1), find(1)
try:
    import numpy as np
    lo, hi = profile_ci_npm(beta, se)
    d = json.load(open(OUT))
    d["coef"]["eco_npm"]["profile_CI95_HR"] = [round(float(np.exp(lo)),4), round(float(np.exp(hi)),4)]
    d["coef"]["eco_npm"]["p_value"] = "OMITTED — sparse stratum (6 events); HR + profile-likelihood CI reported instead (review F1)"
    json.dump(d, open(OUT,"w"), indent=1)
    print("npm profile CI (HR):", d["coef"]["eco_npm"]["profile_CI95_HR"])
except Exception as e:
    print("profile CI failed:", str(e)[:150])
