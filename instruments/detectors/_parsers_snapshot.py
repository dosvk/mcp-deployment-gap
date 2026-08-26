"""Stage-2a: CURRENT capability state per sampled repo, from banked manifests + mapping table.
Conservative classification (dev iteration; freezes with detectors):
- npm: capable iff deps include @modelcontextprotocol/server or /server-legacy at a 2.x
  requirement (the stateless-era package family). Old @modelcontextprotocol/sdk line (<=1.x,
  LATEST protocol 2025-11-25) = not-capable. Adapter lines (node/hono/fastify) 2.x = capable-
  via-family (flagged separately). Anything unparseable = ambiguous.
- rust: rmcp requirement admitting >=1.8 = capable; <1.8 pinned = not; ranges like "1" = ambiguous-passive.
- go: go-sdk >= v1.7.0-pre.1 (or v1.7+/v2+) = capable; else not.
- maven: no supporting versions exist -> structurally not-capable (finding).
Output: capability_state.json (aggregates) + capability_{eco}.jsonl (per repo).
"""
import json, os, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))

def parse_npm(text):
    try:
        m = json.loads(text)
    except Exception:
        return "unparseable", None
    deps = {}
    for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps.update(m.get(k) or {})
    fam = {k: v for k, v in deps.items() if k.startswith("@modelcontextprotocol/")}
    if not fam:
        return "no-mcp-dep-now", None
    for line in ("@modelcontextprotocol/server", "@modelcontextprotocol/server-legacy"):
        if line in fam:
            req = str(fam[line])
            if re.search(r"(^|[^\d.])2\.", req) or req in ("*", "latest"):
                return ("capable" if line.endswith("/server") else "capable-legacy-line"), {line: req}
            return "not-capable", {line: req}
    for line in ("@modelcontextprotocol/node", "@modelcontextprotocol/hono", "@modelcontextprotocol/fastify"):
        if line in fam:
            req = str(fam[line])
            if re.search(r"(^|[^\d.])2\.", req) or req in ("*", "latest"):
                return "capable-via-adapter", {line: req}
    if "@modelcontextprotocol/sdk" in fam:
        return "not-capable-old-line", {"@modelcontextprotocol/sdk": str(fam["@modelcontextprotocol/sdk"])}
    return "ambiguous", dict(list(fam.items())[:2])

def parse_rust(text):
    m = re.search(r'rmcp\s*=\s*(?:"([^"]+)"|\{[^}]*version\s*=\s*"([^"]+)")', text)
    if not m:
        return "no-mcp-dep-now", None
    req = m.group(1) or m.group(2)
    mm = re.match(r"[\^~>=]*\s*(\d+)\.(\d+)", req)
    if mm:
        maj, mnr = int(mm.group(1)), int(mm.group(2))
        if maj > 1 or (maj == 1 and mnr >= 8):
            return "capable", {"rmcp": req}
        if req.startswith("^1.") and mnr < 8:
            return "range-admits", {"rmcp": req}  # ^1.x admits 1.8 -> passive-capable
        return "not-capable", {"rmcp": req}
    if re.match(r"[\^~]?1$", req.strip()) or req.strip() == "*":
        return "range-admits", {"rmcp": req}
    return "ambiguous", {"rmcp": req}

def parse_go(text):
    m = re.search(r"github\.com/modelcontextprotocol/go-sdk\s+v(\d+)\.(\d+)\.?(\S*)", text)
    if not m:
        return "no-mcp-dep-now", None
    maj, mnr = int(m.group(1)), int(m.group(2))
    req = f"v{m.group(1)}.{m.group(2)}.{m.group(3)}"
    if maj > 1 or (maj == 1 and mnr >= 7):
        return "capable", {"go-sdk": req}
    return "not-capable", {"go-sdk": req}

PARSERS = {"npm": parse_npm, "rust": parse_rust, "go": parse_go}
agg = {"generated": datetime.date.today().isoformat(), "preliminary": True, "ecosystems": {}}
for eco in ["npm", "rust", "go", "maven"]:
    path = os.path.join(HERE, f"manifests_{eco}.jsonl")
    if not os.path.exists(path):
        continue
    out = open(os.path.join(HERE, f"capability_{eco}.jsonl"), "w")
    counts = {}
    for line in open(path):
        d = json.loads(line)
        if d.get("error") or not d.get("manifest_now"):
            state, ev = "extract-error", None
        elif eco == "maven":
            state, ev = "not-capable-structural", None  # no supporting java/kotlin release exists
        else:
            state, ev = PARSERS[eco](d["manifest_now"])
        counts[state] = counts.get(state, 0) + 1
        out.write(json.dumps({"repo": d["repo"], "state": state, "evidence": ev}) + "\n")
    out.close()
    agg["ecosystems"][eco] = counts
    print(eco, counts, flush=True)
json.dump(agg, open(os.path.join(HERE, "capability_state.json"), "w"), indent=1)
print("saved capability_state.json")
