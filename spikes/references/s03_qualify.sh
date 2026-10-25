#!/usr/bin/env bash
# S03: run the blind column qualification and runs in one reference tool (spec §2.3, §8, §12).
#
# Needs the environments of scripts/build-reference-envs.sh. Each tool script reads
# docs/derivations/scripts/s03_cases.json and nothing else of this project, and writes
#   OUT/qualification/<tool>.json   levels, attempts, structural inspections, ladder selection
#   OUT/results/<tool>-<case>.json  one tool record per case, controls included
# (OUT default: benchmarks/s03/references). The full run log goes to LOG_DIR (default:
# evidence/S03/artifacts/s03-qualification, git-ignored); this prints the per-case lines and the
# summary line only. Not part of scripts/check.sh: the gate never runs a tool.
#
# Usage: spikes/references/s03_qualify.sh idaes|dwsim [OUT] [LOG_DIR] [SCRIPT ARGS ...]
# (SCRIPT ARGS go to the tool script, e.g. `--only RC3 RC4` for a top-up run.)
set -uo pipefail

cd "$(dirname "$0")/../.."
WHICH="${1:?usage: s03_qualify.sh idaes|dwsim [OUT] [LOG_DIR] [SCRIPT ARGS ...]}"
OUT="${2:-benchmarks/s03/references}"
LOG_DIR="${3:-evidence/S03/artifacts/s03-qualification}"
EXTRA=("${@:4}")
mkdir -p "$OUT" "$LOG_DIR"

case "$WHICH" in
    idaes) PY=.venv-idaes/bin/python ;;
    dwsim) PY=.venv-dwsim/bin/python ;;
    *) echo "unknown tool: $WHICH (idaes|dwsim)" >&2; exit 2 ;;
esac
SCRIPT="spikes/references/s03_qualify_${WHICH}.py"
if [ ! -f "$SCRIPT" ]; then
    echo "missing $SCRIPT" >&2
    exit 2
fi

LOG="$LOG_DIR/${WHICH}-run.log"
"$PY" "$SCRIPT" --out "$OUT" "${EXTRA[@]}" >"$LOG" 2>&1
status=$?
grep -E "^${WHICH} [^ ]+: |^${WHICH} SUMMARY" "$LOG"
echo "log: $LOG"
echo "EXIT $status"
exit "$status"
