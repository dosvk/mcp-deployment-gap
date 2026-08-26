"""Version-aware capability resolver for the JOINT PANEL (P2-1; estimand per A7, instrument A8).

Resolves capability(s,t) = "the server's published package, as it stands at wave time t,
admits an SDK/implementation version supporting protocol revision 2026-07-28" — A6/DEV-1
rules (package -> SDK resolution, version admitted at t). Three mechanical tiers:

  T1 direct-dep:  the package's registry manifest names a known MCP SDK line; the requirement
                  is evaluated against the frozen supporting-version table (mapping_table.json /
                  sdk_mapping_verified.json).
  T2 one-hop:     the manifest names an mcp-ish framework package (name contains 'mcp' or
                  'modelcontextprotocol'); the framework version admitted by the requirement is
                  resolved (npm packument / pypi releases) and ITS manifest is classified by T1.
  T3 artifact:    no resolvable dep chain (bundlers, opaque frameworks): download the published
                  artifact (npm tarball / pypi wheel-sdist) and scan for the protocol version
                  constants. '2026-07-28' present -> capable(artifact); only '2025-11-25'
                  present -> not-capable(artifact); neither -> unresolved.

Server states (per server, ANY-capable aggregation over its packages):
  capable · not-capable · unresolved   (+ sub-reason strings in evidence)
`unresolved` is FIRST-CLASS MISSINGNESS: it enters the MNAR bounds, never the point estimate.

Then computes the deployment gap Delta(t) per A7 against the A8 behavioral wave
(probe_v2_wave_{date}.json): behavior new = state in {new-only, dual-stack}.
  point estimate: capability-resolved x behavior-observed servers (auth-walled and
                  unreachable excluded; unresolved excluded)
  bounds:         Delta_lo = capability worst (unresolved->not-capable), behavior best
                  (auth-walled->new); Delta_hi = mirror image. Unreachable stay outside the
                  denominator (non-probeable that wave; disclosed).
  Delta_pub:      publisher-level twin (ANY-server aggregation), PRIMARY per A7.

Usage:  python3 resolve_joint_capability.py 2026-08-25
Outputs: joint_capability_{date}.json (per-server) and ../analysis/p5_delta_results.json
Caches all network fetches under pkg_meta_cache/ (safe to rerun; delete cache to force).
"""
import gzip
import hashlib
from math import comb
import io
import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "pkg_meta_cache")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "mcp-ecosystem-study/1.0 (academic measurement; contact in submission)"}

NEEDLE_NEW = b"2026-07-28"
NEEDLE_OLD = b"2025-11-25"

# --- frozen SDK-line rules (from mapping_table.json + sdk_mapping_verified.json) ----------
# npm: the /server family is NEW-family (no pre-2.0 versions exist; every published version
# supports 2026-07-28 per mapping_table.json). The /sdk line has NO supporting version.
NPM_CAPABLE_LINES = {
    "@modelcontextprotocol/server": "server",
    "@modelcontextprotocol/server-legacy": "server-legacy",
    "@modelcontextprotocol/core": "core(family)",
    "@modelcontextprotocol/node": "adapter",
    "@modelcontextprotocol/hono": "adapter",
    "@modelcontextprotocol/fastify": "adapter",
    "@modelcontextprotocol/client": "client(family)",
}
NPM_NOTCAP_LINES = {"@modelcontextprotocol/sdk"}
PYPI_SDK = "mcp"
PYPI_SDK_FIRST_SUPPORTING = "2.0.0a1"  # sdk_mapping_verified.json, published 2026-06-11
CARGO_SDK = "rmcp"
CARGO_FIRST_SUPPORTING = (1, 8, 0)
NUGET_SDK = "modelcontextprotocol"
NUGET_FIRST_SUPPORTING = "2.0.0-preview.1"


def cache_path(kind, ident, version):
    safe = hashlib.sha1(f"{kind}|{ident}|{version}".encode()).hexdigest()[:16]
    ident_s = re.sub(r"[^A-Za-z0-9._-]", "_", str(ident))[:60]
    return os.path.join(CACHE, f"{kind}__{ident_s}__{version}__{safe}.json")


def cached(kind, ident, version, fn):
    cp = cache_path(kind, ident, version)
    if os.path.exists(cp):
        return json.load(open(cp))
    try:
        out = fn()
    except urllib.error.HTTPError as e:
        out = {"error": f"http-{e.code}"}
    except Exception as e:  # noqa: BLE001 — cache the failure verbatim
        out = {"error": f"{type(e).__name__}: {e}"[:200]}
    json.dump(out, open(cp, "w"))
    return out


def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_bytes(url, timeout=60, cap=30 * 1024 * 1024):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(cap)


# --- npm ---------------------------------------------------------------------------------
def npm_manifest(ident, version):
    def go():
        iq = urllib.parse.quote(ident, safe="@").replace("/", "%2F")
        d = fetch_json(f"https://registry.npmjs.org/{iq}/{version or 'latest'}")
        return {
            "deps": {**(d.get("dependencies") or {}), **(d.get("peerDependencies") or {})},
            "resolved_version": d.get("version"),
            "tarball": (d.get("dist") or {}).get("tarball"),
        }
    return cached("npm", ident, version, go)


def npm_packument(name):
    def go():
        iq = urllib.parse.quote(name, safe="@").replace("/", "%2F")
        d = fetch_json(f"https://registry.npmjs.org/{iq}")
        return {
            "versions": sorted((d.get("versions") or {}).keys()),
            "latest": (d.get("dist-tags") or {}).get("latest"),
        }
    return cached("npm-packument", name, "all", go)


_SV = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?")


def semver_key(v):
    m = _SV.match(v.strip())
    if not m:
        return None
    pre = m.group(4)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre is None, pre or "")


def npm_range_max(spec, versions):
    """Minimal npm range resolution: highest version admitted by common range forms
    (^ ~ >= > <= < = exact bare x *). Returns None when the form is not recognized."""
    spec = (spec or "").strip()
    keyed = [(semver_key(v), v) for v in versions]
    keyed = [(k, v) for k, v in keyed if k]
    keyed.sort()
    if not keyed:
        return None
    if spec in ("", "*", "latest", "x"):
        return keyed[-1][1]
    best = None
    for clause in [c.strip() for c in spec.split("||")]:
        m = re.match(r"^[\^~]?v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?$", clause)
        comps = re.findall(r"(>=|<=|>|<|=)\s*v?(\d+(?:\.\d+)?(?:\.\d+)?(?:-[0-9A-Za-z.-]+)?)", clause)
        for k, v in keyed:
            ok = None
            if m:
                maj = int(m.group(1))
                mnr = int(m.group(2)) if m.group(2) is not None else None
                pat = int(m.group(3)) if m.group(3) is not None else None
                lo = (maj, mnr or 0, pat or 0, m.group(4) is None, m.group(4) or "")
                if clause.startswith("^"):
                    hi_major = maj if maj > 0 else None  # ^0.x pins minor
                    ok = k >= lo and (k[0] == maj if maj > 0 else (k[0] == 0 and k[1] == (mnr or 0)))
                elif clause.startswith("~"):
                    ok = k >= lo and k[0] == maj and (mnr is None or k[1] == mnr)
                elif mnr is None or pat is None:  # bare '2' / '2.1' x-range
                    ok = k[0] == maj and (mnr is None or k[1] == mnr)
                else:  # exact
                    ok = k == lo
            elif comps:
                ok = True
                for op, val in comps:
                    kv = semver_key(val if val.count(".") >= 2 else val + ".0" * (2 - val.count(".")))
                    if kv is None:
                        ok = None
                        break
                    if op == ">=" and not k >= kv:
                        ok = False
                    if op == ">" and not k > kv:
                        ok = False
                    if op == "<=" and not k <= kv:
                        ok = False
                    if op == "<" and not k < kv:
                        ok = False
                    if op == "=" and not k == kv:
                        ok = False
            if ok:
                # skip prerelease versions unless the clause itself carries a prerelease tag
                if not k[3] and "-" not in clause:  # k[3]=True means stable
                    continue
                if best is None or semver_key(v) > semver_key(best):
                    best = v
    return best


def classify_npm_deps(deps):
    """(state, evidence) from an npm dependency dict — T1 only."""
    for line in NPM_CAPABLE_LINES:
        if line in deps:
            return "capable", {line: deps[line], "via": NPM_CAPABLE_LINES[line]}
    for line in NPM_NOTCAP_LINES:
        if line in deps:
            return "not-capable", {line: deps[line], "via": "sdk-old-line"}
    return None, None


# --- pypi --------------------------------------------------------------------------------
def pypi_manifest(ident, version):
    def go():
        url = f"https://pypi.org/pypi/{ident}/{version}/json" if version else f"https://pypi.org/pypi/{ident}/json"
        d = fetch_json(url)
        urls = d.get("urls") or []
        art = next((u["url"] for u in urls if u.get("packagetype") == "bdist_wheel"), None) or next(
            (u["url"] for u in urls if u.get("packagetype") == "sdist"), None)
        return {
            "requires_dist": d["info"].get("requires_dist") or [],
            "resolved_version": d["info"].get("version"),
            "artifact": art,
        }
    return cached("pypi", ident, version, go)


def pypi_releases(name):
    def go():
        d = fetch_json(f"https://pypi.org/pypi/{name}/json")
        return {"releases": sorted((d.get("releases") or {}).keys())}
    return cached("pypi-releases", name, "all", go)


def pep503(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def parse_req(rd):
    m = re.match(r"\s*([A-Za-z0-9._-]+)\s*(\[[^\]]*\])?\s*([^;]*)\s*(?:;(.*))?$", rd or "")
    if not m:
        return None, None
    return pep503(m.group(1)), (m.group(3) or "").strip()


def pypi_spec_admits_supporting(spec, releases, first_supporting):
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version, InvalidVersion
    try:
        ss = SpecifierSet(spec or "")
        fs = Version(first_supporting)
    except Exception:
        return None
    admitted = []
    for r in releases:
        try:
            v = Version(r)
        except InvalidVersion:
            continue
        if ss.contains(v, prereleases=None):
            admitted.append(v)
    if not admitted:
        return None
    return any(v >= fs for v in admitted)


def pypi_max_admitted(spec, releases):
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version, InvalidVersion
    try:
        ss = SpecifierSet(spec or "")
    except Exception:
        return None
    best = None
    for r in releases:
        try:
            v = Version(r)
        except InvalidVersion:
            continue
        if ss.contains(v, prereleases=None) and (best is None or v > best):
            best = v
    return str(best) if best else None


# --- artifact scan (T3) --------------------------------------------------------------------
def scan_artifact(kind, ident, version, url):
    def go():
        blob = fetch_bytes(url)
        hits_new = hits_old = 0
        names_new = []
        if url.endswith(".whl") or url.endswith(".zip"):
            zf = zipfile.ZipFile(io.BytesIO(blob))
            for n in zf.namelist():
                try:
                    b = zf.read(n)
                except Exception:
                    continue
                if NEEDLE_NEW in b:
                    hits_new += 1
                    names_new.append(n)
                if NEEDLE_OLD in b:
                    hits_old += 1
        else:  # npm .tgz / pypi sdist .tar.gz
            tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")
            for m in tf.getmembers():
                if not m.isfile() or m.size > 20 * 1024 * 1024:
                    continue
                b = tf.extractfile(m).read()
                if NEEDLE_NEW in b:
                    hits_new += 1
                    names_new.append(m.name)
                if NEEDLE_OLD in b:
                    hits_old += 1
        return {"hits_new": hits_new, "hits_old": hits_old, "files_new": names_new[:5], "bytes": len(blob)}
    return cached(f"scan-{kind}", ident, version, go)


# --- per-package resolution ----------------------------------------------------------------
def resolve_npm_pkg(ident, version, depth=0):
    man = npm_manifest(ident, version)
    if man.get("error"):
        return "unresolved", {"reason": f"npm-manifest-{man['error']}", "pkg": ident}
    deps = man.get("deps") or {}
    st, ev = classify_npm_deps(deps)
    if st:
        ev["tier"] = "T1-direct" if depth == 0 else f"T2-onehop(depth{depth})"
        return st, ev
    if depth == 0:
        # T2: one hop through mcp-ish framework deps
        fw = [(d, s) for d, s in deps.items() if "mcp" in d.lower() or "modelcontextprotocol" in d.lower()]
        verdicts = []
        for dn, spec in fw:
            pk = npm_packument(dn)
            if pk.get("error"):
                verdicts.append(("unresolved", {"reason": f"packument-{pk['error']}", "fw": dn}))
                continue
            vmax = npm_range_max(spec, pk.get("versions") or []) or pk.get("latest")
            if not vmax:
                verdicts.append(("unresolved", {"reason": "range-unresolvable", "fw": dn, "spec": spec}))
                continue
            st2, ev2 = resolve_npm_pkg(dn, vmax, depth=1)
            if st2 in ("capable", "not-capable"):
                verdicts.append((st2, {"fw": f"{dn}@{vmax}", "spec": spec, **(ev2 or {})}))
            else:
                verdicts.append((st2, {"fw": f"{dn}@{vmax}", "spec": spec, **(ev2 or {})}))
        for st2, ev2 in verdicts:
            if st2 == "capable":
                ev2["tier"] = "T2-onehop"
                return st2, ev2
        for st2, ev2 in verdicts:
            if st2 == "not-capable":
                ev2["tier"] = "T2-onehop"
                return st2, ev2
        # T3: artifact scan (bundlers / opaque frameworks / no dep at all)
        if man.get("tarball"):
            sc = scan_artifact("npm", ident, version or man.get("resolved_version"), man["tarball"])
            if not sc.get("error"):
                if sc["hits_new"]:
                    return "capable", {"tier": "T3-artifact", "hits_new": sc["hits_new"], "files": sc["files_new"]}
                if sc["hits_old"]:
                    return "not-capable", {"tier": "T3-artifact", "hits_old": sc["hits_old"]}
                return "unresolved", {"tier": "T3-artifact", "reason": "no-protocol-constant"}
            return "unresolved", {"tier": "T3-artifact", "reason": f"scan-{sc['error']}"}
    return "unresolved", {"reason": "no-sdk-dep-found", "pkg": ident}


def resolve_pypi_pkg(ident, version, depth=0):
    man = pypi_manifest(ident, version)
    if man.get("error"):
        return "unresolved", {"reason": f"pypi-manifest-{man['error']}", "pkg": ident}
    reqs = [parse_req(rd) for rd in (man.get("requires_dist") or [])]
    for name, spec in reqs:
        if name == PYPI_SDK:
            rel = pypi_releases(PYPI_SDK)
            if rel.get("error"):
                return "unresolved", {"reason": "sdk-releases-unfetchable"}
            adm = pypi_spec_admits_supporting(spec, rel["releases"], PYPI_SDK_FIRST_SUPPORTING)
            if adm is None:
                return "unresolved", {"reason": "spec-unresolvable", "spec": spec}
            tier = "T1-direct" if depth == 0 else f"T2-onehop(depth{depth})"
            return ("capable" if adm else "not-capable"), {"mcp": spec, "tier": tier}
    if depth == 0:
        fw = [(n, s) for n, s in reqs if n and "mcp" in n and n != PYPI_SDK]
        verdicts = []
        for dn, spec in fw:
            rel = pypi_releases(dn)
            if rel.get("error"):
                verdicts.append(("unresolved", {"reason": f"fw-releases-{rel['error']}", "fw": dn}))
                continue
            vmax = pypi_max_admitted(spec, rel["releases"])
            if not vmax:
                verdicts.append(("unresolved", {"reason": "fw-range-unresolvable", "fw": dn, "spec": spec}))
                continue
            st2, ev2 = resolve_pypi_pkg(dn, vmax, depth=1)
            verdicts.append((st2, {"fw": f"{dn}@{vmax}", "spec": spec, **(ev2 or {})}))
        for st2, ev2 in verdicts:
            if st2 == "capable":
                ev2["tier"] = "T2-onehop"
                return st2, ev2
        for st2, ev2 in verdicts:
            if st2 == "not-capable":
                ev2["tier"] = "T2-onehop"
                return st2, ev2
        if man.get("artifact"):
            sc = scan_artifact("pypi", ident, version or man.get("resolved_version"), man["artifact"])
            if not sc.get("error"):
                if sc["hits_new"]:
                    return "capable", {"tier": "T3-artifact", "hits_new": sc["hits_new"], "files": sc["files_new"]}
                if sc["hits_old"]:
                    return "not-capable", {"tier": "T3-artifact", "hits_old": sc["hits_old"]}
                return "unresolved", {"tier": "T3-artifact", "reason": "no-protocol-constant"}
            return "unresolved", {"tier": "T3-artifact", "reason": f"scan-{sc['error']}"}
    return "unresolved", {"reason": "no-sdk-dep-found", "pkg": ident}


def resolve_cargo_pkg(ident, version):
    def go():
        d = fetch_json(f"https://crates.io/api/v1/crates/{ident}/{version}/dependencies")
        return {"deps": [(x["crate_id"], x["req"]) for x in d.get("dependencies", [])]}
    man = cached("cargo", ident, version, go)
    if man.get("error"):
        return "unresolved", {"reason": f"cargo-{man['error']}"}
    for cid, req in man.get("deps", []):
        if cid == CARGO_SDK:
            m = re.match(r"[\^~>=\s]*(\d+)\.(\d+)", req)
            if not m:
                return "unresolved", {"reason": "req-unparseable", "rmcp": req}
            maj, mnr = int(m.group(1)), int(m.group(2))
            # caret semantics: ^1.x admits every 1.y>=x; supporting = >=1.8
            cap = (maj, mnr) >= CARGO_FIRST_SUPPORTING[:2] or (maj == 1 and req.strip().startswith(("^1", "1")))
            exact_below = req.strip().startswith("=") and (maj, mnr) < CARGO_FIRST_SUPPORTING[:2]
            return ("not-capable" if exact_below else ("capable" if cap else "not-capable")), {"rmcp": req, "tier": "T1-direct"}
    return "unresolved", {"reason": "no-sdk-dep-found"}


def resolve_nuget_pkg(ident, version):
    def go():
        il, vl = ident.lower(), (version or "").lower()
        url = f"https://api.nuget.org/v3-flatcontainer/{il}/{vl}/{il}.nuspec"
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return {"nuspec": r.read().decode("utf-8", "replace")}
    man = cached("nuget", ident, version, go)
    if man.get("error"):
        return "unresolved", {"reason": f"nuget-{man['error']}"}
    deps = re.findall(r'<dependency\s+id="([^"]+)"\s+version="([^"]+)"', man["nuspec"])
    for did, dver in deps:
        if did.lower() == NUGET_SDK:
            m = re.match(r"\[?v?(\d+)\.", dver)
            cap = bool(m) and int(m.group(1)) >= 2
            return ("capable" if cap else "not-capable"), {"ModelContextProtocol": dver, "tier": "T1-direct"}
    return "unresolved", {"reason": "no-sdk-dep-found"}


def resolve_pkg(key):
    rtype, ident, version = key
    if rtype == "npm":
        return resolve_npm_pkg(ident, version)
    if rtype == "pypi":
        return resolve_pypi_pkg(ident, version)
    if rtype == "cargo":
        return resolve_cargo_pkg(ident, version)
    if rtype == "nuget":
        return resolve_nuget_pkg(ident, version)
    return "unresolved", {"reason": f"opaque-artifact-type:{rtype}"}


# --- main ----------------------------------------------------------------------------------
def main(wave_date):
    frame = json.load(open(os.path.join(HERE, "probe_frame_joint.json")))
    members = frame["members"]

    # registry snapshot at t (same-date dump, else latest earlier dump, else frame source)
    regdir = os.path.join(ROOT, "data", "registry")
    dumps = sorted(f for f in os.listdir(regdir) if f.startswith("registry_") and f.endswith(".jsonl.gz"))
    usable = [f for f in dumps if f[len("registry_"):-len(".jsonl.gz")] <= wave_date]
    dump = usable[-1] if usable else frame["source_dump"]
    reg = {}
    with gzip.open(os.path.join(regdir, dump), "rt") as f:
        for line in f:
            e = json.loads(line)
            meta = e.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
            if meta.get("isLatest"):
                reg[e["server"]["name"]] = e["server"]
    fallback = None
    if any(m["name"] not in reg for m in members):
        fallback = {}
        with gzip.open(os.path.join(regdir, frame["source_dump"]), "rt") as f:
            for line in f:
                e = json.loads(line)
                meta = e.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
                if meta.get("isLatest"):
                    fallback[e["server"]["name"]] = e["server"]

    jobs, srv_pkgs = {}, {}
    for m in members:
        s = reg.get(m["name"]) or (fallback or {}).get(m["name"]) or {}
        keys = []
        for p in s.get("packages") or []:
            key = (p.get("registryType", "?"), p.get("identifier"), p.get("version"))
            keys.append(key)
            jobs.setdefault(key, []).append(m["name"])
        srv_pkgs[m["name"]] = keys

    print(f"wave {wave_date} · dump {dump} · {len(members)} servers · {len(jobs)} distinct packages", flush=True)
    pkg_states = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(resolve_pkg, k): k for k in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            k = futs[fut]
            try:
                pkg_states[k] = fut.result()
            except Exception as e:  # noqa: BLE001
                pkg_states[k] = ("unresolved", {"reason": f"resolver-crash:{type(e).__name__}"})
            if i % 100 == 0:
                print(f"  {i}/{len(jobs)} pkgs · {time.time()-t0:.0f}s", flush=True)

    # per-server aggregation: ANY capable > ANY not-capable > unresolved
    per_server = {}
    for m in members:
        name = m["name"]
        pub = name.split("/")[0]
        verdicts = [(pkg_states[k], k) for k in srv_pkgs[name] if k in pkg_states]
        state, evidence = "unresolved", {"reason": "no-packages-in-registry-entry"}
        for (st, ev), k in verdicts:
            if st == "capable":
                state, evidence = st, {"pkg": f"{k[0]}:{k[1]}@{k[2]}", **(ev or {})}
                break
        else:
            for (st, ev), k in verdicts:
                if st == "not-capable":
                    state, evidence = st, {"pkg": f"{k[0]}:{k[1]}@{k[2]}", **(ev or {})}
                    break
            else:
                if verdicts:
                    (st, ev), k = verdicts[0]
                    state, evidence = "unresolved", {"pkg": f"{k[0]}:{k[1]}@{k[2]}", **(ev or {})}
        per_server[name] = {"publisher": pub, "capability": state, "evidence": evidence}

    cap_counts = Counter(v["capability"] for v in per_server.values())
    tier_counts = Counter(v["evidence"].get("tier", v["evidence"].get("reason", "?"))
                          for v in per_server.values())
    print("server capability:", dict(cap_counts), flush=True)
    print("tiers/reasons:", dict(tier_counts.most_common(12)), flush=True)

    # --- join behavior (A8 wave) and compute Delta ------------------------------------------
    wave_path = os.path.join(HERE, f"probe_v2_wave_{wave_date}.json")
    wave = json.load(open(wave_path))
    beh = {r["name"]: r["state"] for r in wave["joint"]["results"]}
    # K1 fix overlay (D-033): if a same-date validation run exists, wave positives count as
    # "new" ONLY when verified (echo control rejected). Unverified positives fall back to
    # legacy-only when their wave initialize negotiated, else to unreachable (non-probeable).
    # Waves probed with instrument >= v0.3 verify inline (disc_verified in the record).
    val_path = os.path.join(HERE, f"probe_v2_validation_{wave_date}.json")
    verified_overlay = None
    if any("disc_verified" in r for r in wave["joint"]["results"]):
        verified_overlay = "inline"
        for r in wave["joint"]["results"]:
            if r["state"] in ("new-only", "dual-stack") and not r.get("disc_verified"):
                beh[r["name"]] = "legacy-only" if str(r.get("init", "")).startswith("nego:") else "unreachable"
    elif os.path.exists(val_path):
        verified_overlay = os.path.basename(val_path)
        val = {r["name"]: r for r in json.load(open(val_path))["results"]}
        init_by_name = {r["name"]: str(r.get("init", "")) for r in wave["joint"]["results"]}
        for name, state in list(beh.items()):
            if state in ("new-only", "dual-stack") and name in val:
                v = val[name]
                if not (v["state"] in ("new-only", "dual-stack") and v.get("disc_verified")):
                    beh[name] = "legacy-only" if init_by_name.get(name, "").startswith("nego:") else "unreachable"
    NEW = {"new-only", "dual-stack"}

    rows = []
    for name, d in per_server.items():
        b = beh.get(name, "unreachable")
        rows.append({"name": name, "publisher": d["publisher"], "capability": d["capability"],
                     "behavior": b, "evidence": d["evidence"]})

    def delta_block(units):
        """units: list of dicts with 'capability' in {capable,not-capable,unresolved} and
        'behavior' in {new,legacy,auth,unreachable}."""
        pt = [u for u in units if u["capability"] != "unresolved" and u["behavior"] in ("new", "legacy")]
        a = sum(1 for u in pt if u["capability"] == "capable" and u["behavior"] == "new")
        b_ = sum(1 for u in pt if u["capability"] == "capable" and u["behavior"] == "legacy")
        c = sum(1 for u in pt if u["capability"] == "not-capable" and u["behavior"] == "new")
        d_ = sum(1 for u in pt if u["capability"] == "not-capable" and u["behavior"] == "legacy")
        n = len(pt)
        delta = ((a + b_) / n - (a + c) / n) if n else None
        # bounds: add auth-walled (behavior unknown) + unresolved capability (both ways);
        # unreachable stays outside the denominator (non-probeable that wave).
        bnd = [u for u in units if u["behavior"] != "unreachable"]
        nb = len(bnd)
        cap_lo = sum(1 for u in bnd if u["capability"] == "capable")
        cap_hi = sum(1 for u in bnd if u["capability"] != "not-capable")
        new_lo = sum(1 for u in bnd if u["behavior"] == "new")
        new_hi = sum(1 for u in bnd if u["behavior"] in ("new", "auth"))
        d_lo = (cap_lo - new_hi) / nb if nb else None
        d_hi = (cap_hi - new_lo) / nb if nb else None
        # STAT-P0 sensitivity: FULL-panel bounds, unreachable included both ways (capability is
        # ~6x enriched among unreachable servers, so excluding them narrows bounds flatteringly)
        nf = len(units)
        f_cap_lo = sum(1 for u in units if u["capability"] == "capable")
        f_cap_hi = sum(1 for u in units if u["capability"] != "not-capable")
        f_new_lo = sum(1 for u in units if u["behavior"] == "new")
        f_new_hi = sum(1 for u in units if u["behavior"] in ("new", "auth", "unreachable"))
        d_lo_full = (f_cap_lo - f_new_hi) / nf if nf else None
        d_hi_full = (f_cap_hi - f_new_lo) / nf if nf else None
        mcn = None
        if b_ + c:
            k = min(b_, c)
            mcn = min(1.0, 2 * sum(comb(b_ + c, i) for i in range(k + 1)) / 2 ** (b_ + c))
        # stratum counts so the MNAR bounds reproduce from this JSON alone (THEORIST v0.16 GAP)
        strata = {
            "n_units": len(units),
            "behavior": {k: sum(1 for u in units if u["behavior"] == k)
                         for k in ("new", "legacy", "auth", "unreachable")},
            "capability": {k: sum(1 for u in units if u["capability"] == k)
                           for k in ("capable", "not-capable", "unresolved")},
            "capable_by_behavior": {k: sum(1 for u in units if u["behavior"] == k and u["capability"] == "capable")
                                    for k in ("new", "legacy", "auth", "unreachable")},
            "resolved_by_behavior": {k: sum(1 for u in units if u["behavior"] == k and u["capability"] != "unresolved")
                                     for k in ("new", "legacy", "auth", "unreachable")},
        }
        return {"n_point": n, "strata": strata,
                "paired": {"cap&new": a, "cap&legacy": b_, "notcap&new": c, "notcap&legacy": d_},
                "P_capable": (a + b_) / n if n else None, "P_new": (a + c) / n if n else None,
                "delta_point": delta, "discordant_b_c": [b_, c], "mcnemar_exact_p": mcn,
                "n_bounds": nb, "delta_lo": d_lo, "delta_hi": d_hi,
                "n_fullpanel": nf, "delta_lo_fullpanel": d_lo_full, "delta_hi_fullpanel": d_hi_full}

    BMAP = {"new-only": "new", "dual-stack": "new", "legacy-only": "legacy",
            "auth-walled": "auth", "unreachable": "unreachable"}
    srv_units = [{"capability": r["capability"], "behavior": BMAP[r["behavior"]]} for r in rows]
    srv_delta = delta_block(srv_units)

    pubs = {}
    for r in rows:
        p = pubs.setdefault(r["publisher"], {"cap": set(), "beh": set()})
        p["cap"].add(r["capability"])
        p["beh"].add(BMAP[r["behavior"]])
    pub_units = []
    for p, d in pubs.items():
        cap = ("capable" if "capable" in d["cap"] else
               "not-capable" if "not-capable" in d["cap"] else "unresolved")
        beh_p = ("new" if "new" in d["beh"] else
                 "legacy" if "legacy" in d["beh"] else
                 "auth" if "auth" in d["beh"] else "unreachable")
        pub_units.append({"capability": cap, "behavior": beh_p})
    pub_delta = delta_block(pub_units)

    out = {
        "instrument": "P2-1 version-aware capability resolver (T1 direct / T2 one-hop / T3 artifact-scan)",
        "estimand": "A7 deployment gap Delta(t); behavior per A8 (new = new-only|dual-stack)",
        "wave": wave_date, "registry_dump": dump,
        "behavior_verification": verified_overlay or "NONE (v0.2 wave, no validation run — positives unverified)",
        "server_capability_counts": dict(cap_counts),
        "resolution_tiers_note": "counts are per-server EVIDENCE tiers incl. unresolved attempts; "
                                 "resolved-only totals are in server_capability_counts",
        "resolution_tiers": dict(tier_counts.most_common(20)),
        "delta_server": srv_delta,
        "delta_publisher_PRIMARY": pub_delta,
        "n_servers": len(rows), "n_publishers": len(pubs),
        "preliminary": True,
        "marker": "[PW] corrected A8 series; regenerate at 2026-10-10 freeze",
    }
    json.dump({"meta": out, "servers": rows},
              open(os.path.join(HERE, f"joint_capability_{wave_date}.json"), "w"), indent=1)
    json.dump(out, open(os.path.join(ROOT, "analysis", "p5_delta_results.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "resolution_tiers"}, indent=1), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y-%m-%d"))
