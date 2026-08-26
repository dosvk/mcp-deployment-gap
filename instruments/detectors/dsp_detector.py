"""DS-P detector (dev v0.1, per DETECTOR-SPEC): parallel package lines.
Signature: a publisher maintains BOTH a current and a '-legacy'-suffixed (or '-v1'/'-old')
package line for the same base identifier, with the legacy line created/updated in the
migration window. Dev corpus: registry dump package identifiers (65,385 entries).
Presence-only; lower-bound phrasing. Dev-set iteration only until freeze commit.
"""
import json, gzip, glob, os, re, datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))  # detectors -> gate2 -> paper5-c1
DUMP = sorted(glob.glob(os.path.join(BASE, "data/registry/registry_*.jsonl.gz")))[-1]
OUT = os.path.join(HERE, "dsp_dev_results.json")

SUFFIXES = ["-legacy", "_legacy", "-old", "-v1", "-classic", "-compat", "-stable"]

# collect package identifiers per registry server + publisher
pkg_index = defaultdict(set)   # identifier -> set(server names)
server_pkgs = defaultdict(set)
for line in gzip.open(DUMP, "rt"):
    d = json.loads(line)
    s = d["server"]
    for p in (s.get("packages") or []):
        ident = (p.get("identifier") or "").strip().lower()
        if ident:
            pkg_index[ident].add(s["name"])
            server_pkgs[s["name"]].add(ident)

hits = []
seen_pairs = set()
for ident in pkg_index:
    for suf in SUFFIXES:
        if ident.endswith(suf):
            base_ident = ident[: -len(suf)]
            if base_ident in pkg_index and (base_ident, ident) not in seen_pairs:
                seen_pairs.add((base_ident, ident))
                hits.append({"base": base_ident, "legacy_line": ident,
                             "servers_base": sorted(pkg_index[base_ident])[:3],
                             "servers_legacy": sorted(pkg_index[ident])[:3]})

res = {"detector": "DS-P", "version": "dev-0.1", "generated": datetime.date.today().isoformat(),
       "dev_corpus": os.path.basename(DUMP), "n_package_identifiers": len(pkg_index),
       "suffix_rules": SUFFIXES, "n_pairs": len(hits), "pairs": hits[:50],
       "known_true_positive_check": any("server-legacy" in h["legacy_line"] for h in hits),
       "caveats": ["suffix heuristic only (dev); npm scope/dist-tag variants pending",
                    "publisher-level linking pending hydration",
                    "presence-only, lower bound"]}
json.dump(res, open(OUT, "w"), indent=1)
print(f"identifiers={len(pkg_index)}  DS-P pairs={len(hits)}  "
      f"known-TP(server-legacy) found={res['known_true_positive_check']}")
for h in hits[:8]:
    print("  ", h["base"], "<->", h["legacy_line"])
print("saved", OUT)
