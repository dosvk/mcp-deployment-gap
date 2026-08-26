"""RQ1/explanatory-layer survival pipeline (PRELIMINARY; spec freezes with detectors 9/19).
KM per ecosystem (25th pct primary) + Cox PH with owner-level cluster (A2) on the A6 sample.
Time origin per ecosystem = first supporting SDK artifact date (adoption first POSSIBLE):
rust 2026-06-23 (rmcp 1.8.0) · go 2026-06-24 (v1.7.0-pre.1) · npm 2026-06-25 (server-legacy
alpha-2 era). Repos created after origin enter at creation (left truncation). Right-censor at
generation date. maven excluded (no origin exists — structurally blocked; reported as such).
"""
import json, os, datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
G2 = os.path.join(os.path.dirname(HERE), "gate2")
OUT = os.path.join(HERE, "p5_survival_results.json")
TODAY = datetime.date.today()
ORIGIN = {"rust": datetime.date(2026, 6, 23), "go": datetime.date(2026, 6, 24),
          "npm": datetime.date(2026, 6, 25)}

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
        ev_date = events.get(repo)
        if ev_date and ev_date < start:
            ev_date = start  # capable at entry (born-capable/pre-origin edge) -> t=0 event
        end = ev_date or TODAY
        t = max((end - start).days, 0) + 0.5  # avoid zero durations
        rows.append({"eco": eco, "repo": repo, "owner": repo.split("/")[0],
                     "t": t, "event": 1 if ev_date else 0,
                     "org": 1 if h["owner_type"] == "Organization" else 0,
                     "log_stars": float(np.log1p(h["stars"])),
                     "age_yrs": max((ORIGIN[eco] - created).days, 0) / 365.25})

def km(sub):
    """Kaplan-Meier; returns 25th percentile day and adoption share at t=30/60."""
    sub = sorted(sub, key=lambda r: r["t"])
    n = len(sub); S = 1.0; curve = []
    at_risk = n
    for r in sub:
        if r["event"]:
            S *= (1 - 1 / at_risk)
        at_risk -= 1
        curve.append((r["t"], S))
    def s_at(t):
        s = 1.0
        for tt, ss in curve:
            if tt <= t:
                s = ss
            else:
                break
        return s
    q25 = next((tt for tt, ss in curve if ss <= 0.75), None)
    return {"n": n, "events": sum(r["event"] for r in sub),
            "adopted_by_30d": round(1 - s_at(30), 4), "adopted_by_60d": round(1 - s_at(60), 4),
            "q25_days": q25}

res = {"preliminary": True, "generated": TODAY.isoformat(),
       "origins": {k: v.isoformat() for k, v in ORIGIN.items()},
       "km": {eco: km([r for r in rows if r["eco"] == eco]) for eco in ORIGIN},
       "maven": "excluded — no supporting SDK exists (structural zero, reported separately)"}

# Cox PH with cluster-robust SE via lifelines
try:
    import pandas as pd
    from lifelines import CoxPHFitter
    df = pd.DataFrame(rows)
    df = pd.get_dummies(df, columns=["eco"], drop_first=True)  # npm = reference
    cph = CoxPHFitter()
    cph.fit(df.drop(columns=["repo", "owner"]), duration_col="t", event_col="event",
            cluster_col=None, robust=True)
    # cluster: lifelines supports cluster_col in fit via weights? Use cluster_col param:
    cph2 = CoxPHFitter()
    cph2.fit(df.drop(columns=["repo"]), duration_col="t", event_col="event",
             cluster_col="owner", robust=True)
    summ = cph2.summary
    res["cox"] = {i: {"HR": round(float(np.exp(summ.loc[i, "coef"])), 3),
                       "p": float(f"{summ.loc[i, 'p']:.3g}")} for i in summ.index}
    res["cox_note"] = "owner-clustered robust SEs (A2); npm = reference ecosystem"
except Exception as e:
    res["cox"] = {"error": str(e)[:300]}

json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1)[:1800])
print("saved", OUT)
