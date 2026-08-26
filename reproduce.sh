#!/bin/bash
# reproduce.sh — Paper 5 "The Deployment Gap": regenerate every reported number and figure.
# Promised in draft/main.md header. Run from the paper root. Steps are independent; each
# prints PASS/SKIP/FAIL. SKIP = required raw input not present in this checkout (the public
# artifact package ships all inputs; probe waves additionally regenerate only with network).
set -u
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
FAIL=0
step () {  # step <name> <required-input> <command...>
  local name="$1"; local req="$2"; shift 2
  if [ -n "$req" ] && [ ! -e "$req" ]; then
    echo "SKIP  $name (missing input: $req)"; return
  fi
  if "$@" > "/tmp/repro_$name.log" 2>&1; then
    echo "PASS  $name"
  else
    echo "FAIL  $name (see /tmp/repro_$name.log)"; FAIL=1
  fi
}

echo "== Paper 5 reproduction · $(date -u +%F) =="

# 1. Detector golden tests (self-contained; must always pass)
step goldens "" bash -c "cd gate2/detectors && python3 golden_tests.py"

# 2. Capability states, dependent repos (input: banked manifests)
step capability_repos gate2/manifests_npm.jsonl $PY gate2/derive_capability_state.py

# 3. Survival analyses RQ1 (inputs: events + hydrated frames)
step survival_km  gate2/events_rust.jsonl $PY analysis/p5_survival.py
step logrank      gate2/events_rust.jsonl $PY analysis/p5_logrank.py
step firth_cox    gate2/events_rust.jsonl $PY analysis/p5_firth_cox.py

# 4. RQ4 registry series (input: registry dumps)
step rq4_negbin   data/registry $PY analysis/p5_rq4_negbin.py

# 5. Joint-panel capability + deployment gap Delta (inputs: frozen frame, registry dump,
#    A8 wave file; network only on first run — package ships gate2/pkg_meta_cache/)
WAVE=$(ls gate2/probe_v2_wave_*.json 2>/dev/null | sort | tail -1)
if [ -n "${WAVE:-}" ]; then
  WDATE=$(basename "$WAVE" | sed 's/probe_v2_wave_//;s/.json//')
  step delta_resolver "$WAVE" $PY gate2/resolve_joint_capability.py "$WDATE"
else
  echo "SKIP  delta_resolver (no probe_v2_wave_*.json)"
fi

# 6. Figures (inputs: analysis result JSONs from steps above)
step figures analysis/p5_delta_results.json bash -c "cd draft && $PWD/$PY make_figures.py"

echo "== done =="
exit $FAIL
