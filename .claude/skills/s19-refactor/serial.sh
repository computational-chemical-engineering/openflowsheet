#!/bin/bash
# Rule 4 (ADR 0076, amendment 2026-11-16): serial full suite at one commit, for the MSG counts.
# Usage: serial.sh <worktree at the commit> <label>   (run detached; ~2.2 h; no gate or map build alongside)
# Log: <git-common-dir>/codehealth/runs/serial/<label>.log; last lines: EXIT n and one SERIAL summary line.
# Compare base and head: MSG WO-5a bundles, MSG WO-6 run results and "with a failure", passed, skipped,
# xfailed, deselected must all be equal (S19_DECISIONS 2026-11-16 22:24: 1061/801/100 at be115b6a).
set -u
W=$(cd "$1" && pwd -P); L=$2
R=$(git -C "$W" rev-parse --path-format=absolute --git-common-dir)/codehealth/runs/serial
mkdir -p "$R"; LOG=$R/$L.log
export PYTHONPATH=$W/src PYTHONHASHSEED=0 TMPDIR=$HOME/.cache/openflowsheet/tmp-ser-$L
mkdir -p "$TMPDIR"
P=/home/eajfpeters/Code/OpenFlowsheet/.venv-testmap/bin/python
echo "SERIAL $L head=$(git -C "$W" rev-parse HEAD) start=$(date -Is) pid=$$" > "$LOG"
cd "$W" && $P -m pytest -p no:xdist -q -p no:cacheprovider --timeout=900 \
 --deselect tests/test_t07_v17_reference.py::test_f6_the_forty_runs_fit_their_budget \
 --deselect tests/test_t07_conformance.py::test_the_budget_of_the_scenario_runs \
 >> "$LOG" 2>&1
RC=$?
echo "EXIT $RC" >> "$LOG"
SUM=$(grep -E 'MSG WO-5a|MSG WO-6' "$LOG" | tr '\n' ' '; grep -E '(passed|failed).* in [0-9.]+s' "$LOG" | tail -1)
echo "SERIAL $L rc=$RC $SUM" | tee -a "$LOG"
