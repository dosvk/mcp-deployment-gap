"""A8 corrected behavioral probe v0.3 (server/discover + _meta protocolVersion + echo control).

Classifies each server: new-only / dual-stack / legacy-only / unreachable / auth-walled.
- server/discover: MUST-implement on 2026-07-28 -> positive = speaks new revision, but ONLY
  when VERIFIED: a same-session negative control (a nonsense method) must be REJECTED by the
  endpoint (JSON-RPC error or HTTP error). An endpoint that returns a result for any method
  (echo/permissive gateway) cannot count as answering server/discover (K1 fix, 2026-08-25;
  5/13 wave-1 joint "dual-stack" positives showed this signature).
- Per A8 item 1, every request carries _meta io.modelcontextprotocol/protocolVersion.
- initialize: legacy handshake (removed in 2026-07-28) -> positive = still implements it.
- A5.2 arms: EVEN frame indices are always offered 2026-07-28 (longitudinal series);
  from wave 3 the ODD half is offered the prior revision 2025-11-25 (negotiation experiment).
  Parity is by position in the FROZEN frame order. Arm + offer recorded per result.
Read-only, max 3 requests/server (discover, control, initialize), 1 rps, identifying UA.

MODES:
  python3 probe_v2.py smoke [n]     -> quick n-server validation (default 60)
  python3 probe_v2.py wave          -> full wave over general + joint frames, one file/day
  python3 probe_v2.py revalidate F  -> re-probe only the new-capable positives recorded in
                                       wave file F (instrument-validation run, small n)
"""
import json, glob, os, sys, time, ssl, urllib.request, urllib.error
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
GEN_FRAME = os.path.join(HERE, "probe_frame.json")
JOINT_FRAME = os.path.join(HERE, "probe_frame_joint.json")
NEW_REV = "2026-07-28"
PRIOR_REV = "2025-11-25"
META_KEY = "io.modelcontextprotocol/protocolVersion"
CONTROL_METHOD = "server/nonexistent_control_a8_2026"

def rpc(url, method, params, offer):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
        "User-Agent": "mcp-research-probe/0.3 (academic measurement; read-only; no data access)",
        "MCP-Protocol-Version": offer})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
        raw = r.read(65536).decode("utf-8", "replace")
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            for ln in raw.splitlines():
                if ln.startswith("data:"):
                    raw = ln[5:].strip(); break
        return r.status, json.loads(raw)

def probe_one(url, offer=NEW_REV):
    """Three requests: server/discover, echo control, legacy initialize."""
    disc = ctrl = init = None; wall = False; disc_result = None
    meta = {"_meta": {META_KEY: offer}}
    # 1) server/discover (with per-request _meta version, per A8 item 1)
    try:
        st, j = rpc(url, "server/discover", meta, offer)
        if j.get("result") is not None:
            disc = "ok"; disc_result = j["result"]
        else:
            disc = "err:" + str((j.get("error") or {}).get("code"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403): wall = True
        disc = f"http-{e.code}"
    except Exception as e:
        disc = "conn:" + type(e).__name__
    time.sleep(0.5)
    # 2) negative control — ONLY when discover returned a result (verification is what it buys)
    if disc == "ok":
        try:
            st, j = rpc(url, CONTROL_METHOD, meta, offer)
            ctrl = "echo" if j.get("result") is not None else \
                   "rejected:" + str((j.get("error") or {}).get("code"))
        except urllib.error.HTTPError as e:
            ctrl = f"rejected:http-{e.code}"
        except Exception as e:
            ctrl = "conn:" + type(e).__name__
        time.sleep(0.5)
    # 3) legacy initialize (offer = arm's version)
    try:
        st, j = rpc(url, "initialize", {"protocolVersion": offer, "capabilities": {},
                    "clientInfo": {"name": "academic-measurement-probe", "version": "0.3"},
                    **meta}, offer)
        pv = (j.get("result") or {}).get("protocolVersion")
        init = ("nego:" + pv) if pv else ("err:" + str((j.get("error") or {}).get("code")))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403): wall = True
        init = f"http-{e.code}"
    except Exception as e:
        init = "conn:" + type(e).__name__
    # verification: discover "ok" counts ONLY if the control was rejected
    disc_verified = disc == "ok" and isinstance(ctrl, str) and ctrl.startswith("rejected")
    # extra evidence, recorded not required: does the discover result carry the new revision?
    version_evidence = bool(disc_result) and NEW_REV in json.dumps(disc_result)
    disc_ok = disc_verified
    init_ok = isinstance(init, str) and init.startswith("nego:")
    if disc_ok and init_ok: state = "dual-stack"
    elif disc_ok: state = "new-only"
    elif init_ok: state = "legacy-only"
    elif wall: state = "auth-walled"
    else: state = "unreachable"
    out = {"disc": disc, "ctrl": ctrl, "init": init, "state": state,
           "disc_verified": disc_verified, "version_evidence": version_evidence, "offer": offer}
    if disc == "ok" and not disc_verified:
        out["suspect_echo"] = True
    return out

def wave_number():
    return len(glob.glob(os.path.join(HERE, "probe_v2_wave_*.json"))) + 1

def offer_for(idx, wave_no):
    """A5.2: even frame indices always NEW_REV; odd half alternates from wave 3."""
    if idx % 2 == 0 or wave_no < 3:
        return NEW_REV
    return PRIOR_REV if (wave_no % 2 == 1) else NEW_REV  # alternate odd-arm offers by wave

DEADLINE = time.time() + float(os.environ.get("PROBE_BUDGET_SEC", "1e9"))
def run_frame(members, tag, partial_path=None, wave_no=1):
    done = {}
    if partial_path and os.path.exists(partial_path):
        for ln in open(partial_path):
            try:
                d = json.loads(ln); done[d["name"]] = d
            except Exception: pass
    res = []
    pf = open(partial_path, "a") if partial_path else None
    for i, s in enumerate(members):
        if s["name"] in done:
            res.append(done[s["name"]]); continue
        if time.time() > DEADLINE:
            if pf: pf.close()
            print(f"  {tag} budget hit at {i}/{len(members)} — resume next run", flush=True)
            raise SystemExit(0)
        r = probe_one(s["url"], offer_for(i, wave_no))
        r["name"] = s["name"]; r["publisher"] = s["name"].split("/")[0]
        r["arm"] = "even" if i % 2 == 0 else "odd"
        res.append(r)
        if pf: pf.write(json.dumps(r) + "\n"); pf.flush()
        time.sleep(0.6)
        if (i + 1) % 100 == 0: print(f"  {tag} {i+1}/{len(members)}", flush=True)
    if pf: pf.close()
    return res

def summ(res):
    c = Counter(r["state"] for r in res)
    newcap = {r["publisher"] for r in res if r["state"] in ("new-only", "dual-stack")}
    allpub = {r["publisher"] for r in res if r["state"] != "unreachable"}
    return {"states": dict(c.most_common()), "n": len(res),
            "suspect_echo": sum(1 for r in res if r.get("suspect_echo")),
            "publishers_new_capable": len(newcap), "publishers_total": len(allpub)}

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    if mode == "smoke":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        res = run_frame(json.load(open(JOINT_FRAME))["members"][:n], "smoke")
        out = os.path.join(HERE, f"probe_v2_smoke_{time.strftime('%Y-%m-%d')}.json")
        json.dump({"instrument": "A8v0.3", "mode": "smoke", "n": len(res),
                   "states": dict(Counter(r["state"] for r in res).most_common()),
                   "results": res}, open(out, "w"), indent=1)
        print("STATES:", dict(Counter(r["state"] for r in res).most_common()))
        print("saved", out); return

    if mode == "revalidate":
        src = sys.argv[2]
        w = json.load(open(src))
        targets = []
        frames = {m["name"]: m for f in (GEN_FRAME, JOINT_FRAME)
                  for m in json.load(open(f))["members"]}
        for panel in ("general", "joint"):
            for r in w[panel]["results"]:
                if r["state"] in ("new-only", "dual-stack") and r["name"] in frames:
                    targets.append({"panel": panel, **frames[r["name"]], "wave_state": r["state"]})
        print(f"revalidating {len(targets)} wave positives with instrument v0.3", flush=True)
        res = []
        for t in targets:
            r = probe_one(t["url"])
            r["name"] = t["name"]; r["publisher"] = t["name"].split("/")[0]
            r["panel"] = t["panel"]; r["wave_state_v02"] = t["wave_state"]
            res.append(r); print(" ", t["name"], "v0.2:", t["wave_state"], "-> v0.3:", r["state"],
                                 "| ctrl:", r["ctrl"], "| ver_evid:", r["version_evidence"], flush=True)
            time.sleep(0.6)
        out = os.path.join(HERE, f"probe_v2_validation_{time.strftime('%Y-%m-%d')}.json")
        json.dump({"instrument": "A8v0.3 revalidation of v0.2 positives", "source_wave": src,
                   "n": len(res), "results": res}, open(out, "w"), indent=1)
        print("saved", out); return

    # wave mode
    today = time.strftime("%Y-%m-%d")
    out = os.path.join(HERE, f"probe_v2_wave_{today}.json")
    if os.path.exists(out):
        print(f"{out} exists — one wave/day"); return
    wn = wave_number()
    gen = json.load(open(GEN_FRAME))["members"]
    joint = json.load(open(JOINT_FRAME))["members"]
    r_gen = run_frame(gen, "general", out + ".gen.partial", wn)
    r_joint = run_frame(joint, "joint", out + ".joint.partial", wn)
    json.dump({"instrument": "A8v0.3 server/discover+control", "mode": "wave", "date": today,
               "wave_number": wn,
               "general": {"summary": summ(r_gen), "results": r_gen},
               "joint": {"summary": summ(r_joint), "results": r_joint}}, open(out, "w"), indent=1)
    print("GENERAL:", summ(r_gen)); print("JOINT:", summ(r_joint)); print("saved", out)

if __name__ == "__main__":
    main()
