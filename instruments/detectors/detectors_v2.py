"""Detectors v2 (dev iteration; freeze commit 2026-09-19).
- DS-P (dual-stack parallel lines): manifest_now declares BOTH a stateless-era line AND a
  legacy line (npm: server + server-legacy, or new family + old sdk line; rust/go: n/a at
  manifest level - single crate/module). LOCAL, zero API.
- HC (cut-signature): event-walk shows a not-capable -> capable transition where no walk
  state ever had both lines (npm) / straight version jump (rust/go). LOCAL.
- Outputs detectors_v2_results.json with per-ecosystem signature counts (lower bounds).
"""
import json, os, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
G2 = os.path.dirname(HERE)  # detectors/ -> gate2/

def npm_lines(text):
    try:
        m = json.loads(text)
    except Exception:
        return None
    deps = {}
    for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps.update(m.get(k) or {})
    fam = {k for k in deps if k.startswith("@modelcontextprotocol/")}
    new_family = {"@modelcontextprotocol/server", "@modelcontextprotocol/node",
                  "@modelcontextprotocol/hono", "@modelcontextprotocol/fastify"} & fam
    legacy = ({"@modelcontextprotocol/server-legacy"} & fam) or \
             ({"@modelcontextprotocol/sdk"} & fam if new_family else set())
    return {"new": sorted(new_family), "legacy": sorted(legacy)}

res = {"built": datetime.date.today().isoformat(), "version": "dev-2",
       "note": "presence-only lower bounds; freeze 2026-09-19", "ecosystems": {}}

for eco in ["npm", "rust", "go"]:
    dsp = []; hc = []; n = 0
    walks = {}
    epath = os.path.join(G2, f"events_{eco}.jsonl")
    if os.path.exists(epath):
        for line in open(epath):
            d = json.loads(line)
            if not d.get("error"):
                walks[d["repo"]] = d
    for line in open(os.path.join(G2, f"manifests_{eco}.jsonl")):
        d = json.loads(line)
        if d.get("error"):
            continue
        n += 1
        if eco == "npm":
            lines = npm_lines(d.get("manifest_now") or "")
            if lines and lines["new"] and lines["legacy"]:
                dsp.append({"repo": d["repo"], "new": lines["new"], "legacy": lines["legacy"]})
        w = walks.get(d["repo"])
        if w and w.get("first_capable_commit"):
            states = [s["state"] for s in w.get("walk", [])]
            # cut-signature: direct not-capable -> capable transition, no intermediate dual state
            idx = next((i for i, s in enumerate(states) if s in
                        ("capable", "capable-legacy-line", "capable-via-adapter")), None)
            if idx is not None and idx > 0 and states[idx - 1].startswith("not-capable"):
                hc.append(d["repo"])
    res["ecosystems"][eco] = {"n_manifests": n, "DS-P_hits": len(dsp),
                                "DS-P_examples": dsp[:5], "HC_cut_signatures": len(hc),
                                "HC_examples": hc[:5]}
    print(f"{eco:5s} n={n} DS-P={len(dsp)} HC={len(hc)}", flush=True)

json.dump(res, open(os.path.join(G2, "detectors_v2_results.json"), "w"), indent=1)
print("saved detectors_v2_results.json")
