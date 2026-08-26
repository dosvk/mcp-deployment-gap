"""Golden test set for the detector freeze commit (A4 discipline).
Known-answer cases every detector must pass at freeze and before every production run.
Run: python3 golden_tests.py  -> exits nonzero on any failure.
"""
import json, os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
G2 = os.path.dirname(HERE)

# load parsers from derive_capability_state.py (same import pattern as extract_events)
src = open(os.path.join(HERE, "_parsers_snapshot.py")).read()
ns = {"__file__": os.path.join(HERE, "_parsers_snapshot.py")}
exec(src.split("PARSERS =")[0], ns)

FAILS = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)

# --- capability parser goldens (npm)
p = ns["parse_npm"]
check("npm: new server line 2.x => capable",
      p('{"dependencies":{"@modelcontextprotocol/server":"^2.0.0"}}')[0] == "capable")
check("npm: legacy line 2.x => capable-legacy-line",
      p('{"dependencies":{"@modelcontextprotocol/server-legacy":"^2.0.0"}}')[0] == "capable-legacy-line")
check("npm: old sdk line => not-capable-old-line",
      p('{"dependencies":{"@modelcontextprotocol/sdk":"^1.30.0"}}')[0] == "not-capable-old-line")
check("npm: no mcp dep => no-mcp-dep-now",
      p('{"dependencies":{"express":"^4.0.0"}}')[0] == "no-mcp-dep-now")
check("npm: garbage => unparseable", p('not json{{{')[0] == "unparseable")
# --- rust
p = ns["parse_rust"]
check("rust: rmcp 1.8 => capable", p('rmcp = "1.8.0"')[0] == "capable")
check("rust: rmcp 1.7 pinned => not-capable", p('rmcp = "=1.7.0"')[0] == "not-capable")
check("rust: rmcp ^1.5 range => range-admits", p('rmcp = "^1.5"')[0] == "range-admits")
check("rust: table form version => capable",
      p('rmcp = { version = "1.9.0", features = ["server"] }')[0] == "capable")
# --- go
p = ns["parse_go"]
check("go: v1.7.0-pre.1 => capable",
      p("require github.com/modelcontextprotocol/go-sdk v1.7.0-pre.1")[0] == "capable")
check("go: v1.6.0 => not-capable",
      p("require github.com/modelcontextprotocol/go-sdk v1.6.0")[0] == "not-capable")

# --- DS-P golden: known TP manifest (both lines)
import re
dsp_src = open(os.path.join(HERE, "detectors_v2.py")).read()
ns2 = {"__file__": os.path.join(HERE, "detectors_v2.py")}
exec(dsp_src.split("res =")[0], ns2)
lines = ns2["npm_lines"]('{"dependencies":{"@modelcontextprotocol/server":"^2.0.0","@modelcontextprotocol/server-legacy":"^2.0.0"}}')
check("DS-P: both lines detected", bool(lines and lines["new"] and lines["legacy"]))
lines2 = ns2["npm_lines"]('{"dependencies":{"@modelcontextprotocol/server":"^2.0.0"}}')
check("DS-P: single line NOT flagged", bool(lines2 and lines2["new"] and not lines2["legacy"]))

# --- mapping table sanity (frozen expectations from artifact verification D-008/D-017)
mt = json.load(open(os.path.join(G2, "mapping_table.json")))
check("mapping: npm server first_supporting == 2.0.0-alpha.3",
      mt["lines"]["npm:@modelcontextprotocol/server"]["first_supporting"] == "2.0.0-alpha.3")
check("mapping: npm sdk main line has NO supporting version",
      not mt["lines"]["npm:@modelcontextprotocol/sdk"]["supporting"])
check("mapping: maven java empty (structural)",
      not mt["lines"]["maven:io.modelcontextprotocol.sdk:mcp"]["supporting"])

print(f"\n{len(FAILS)} failures" if FAILS else "\nALL GOLDEN TESTS PASS")
sys.exit(1 if FAILS else 0)
