#!/usr/bin/env bash
# S09 WO-S09-2: the BioSTEAM qualification, run twice (docs/derivations/S09-spec.md §5.7, §10, A17).
#
# Runs every pair of s09_cases.json in its own Python process (one case per process, the tool's
# global thermo set once for that case), writes run 1 into OUT and run 2 into REPEAT, then assembles
# OUT/qualification/biosteam.json with the repeat block: every record of run 2 must equal run 1's
# byte for byte after the wall_time* fields are removed. Prints one summary line; the per-case
# output goes to LOG.
#
#     spikes/references/s09_qualify.sh OUT REPEAT [LOG]
#
# Thread counts of the numerical libraries are fixed to 1 so that a run does not depend on the
# load of the machine. Cases run JOBS at a time (default 6); each is its own process and writes its
# own file. Not part of scripts/check.sh: the gate never runs a tool.
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "usage: $0 OUT REPEAT [LOG]" >&2
    exit 2
fi
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
REPEAT="$(mkdir -p "$2" && cd "$2" && pwd)"
LOG="${3:-$OUT/qualify.log}"
PY="$ROOT/.venv-biosteam/bin/python"
SCRIPT="$ROOT/spikes/references/s09_qualify_biosteam.py"
JOBS="${JOBS:-6}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

PAIRS="$("$PY" -c 'import json, sys; print(" ".join(json.load(open(sys.argv[1]))["pairs"]))' \
    "$ROOT/docs/derivations/scripts/s09_cases.json")"
: > "$LOG"
for dir in "$OUT" "$REPEAT"; do
    mkdir -p "$dir/results"
    echo "== run into $dir" >> "$LOG"
    # shellcheck disable=SC2086
    if ! printf '%s\n' $PAIRS | xargs -P "$JOBS" -I{} \
            "$PY" "$SCRIPT" --case {} --out "$dir" >> "$LOG" 2>&1; then
        echo "s09_qualify FAILED: a case process exited non-zero (see $LOG)"
        exit 1
    fi
done
"$PY" "$SCRIPT" --assemble "$OUT" --repeat "$REPEAT" | tee -a "$LOG"
