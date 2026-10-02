#!/usr/bin/env bash
# T06 M6: run the blind reference qualification in both tools and summarize it (flags only).
#
# Needs the environments of scripts/build-reference-envs.sh. Writes one JSON record per
# (tool, fixture) plus the Ipopt logs to OUT (default: evidence/T06/artifacts/m6-qualification,
# git-ignored), then prints the flag table and the records' SHA-256 (t06_qualification_summary.py).
# Not part of scripts/check.sh: the gate never runs a tool.
#
# Usage: spikes/references/t06_qualify.sh [idaes|dwsim|all] [OUT]
set -uo pipefail

cd "$(dirname "$0")/../.."
WHICH="${1:-all}"
OUT="${2:-evidence/T06/artifacts/m6-qualification}"
mkdir -p "$OUT"
status=0

if [ "$WHICH" = "all" ] || [ "$WHICH" = "idaes" ]; then
    .venv-idaes/bin/python spikes/references/t06_qualify_idaes.py --out "$OUT" \
        >"$OUT/idaes-run.log" 2>&1 || status=1
    grep -E '^idaes ' "$OUT/idaes-run.log"
fi
if [ "$WHICH" = "all" ] || [ "$WHICH" = "dwsim" ]; then
    .venv-dwsim/bin/python spikes/references/t06_qualify_dwsim.py --out "$OUT" \
        >"$OUT/dwsim-run.log" 2>&1 || status=1
    grep -E '^dwsim ' "$OUT/dwsim-run.log"
fi
.venv-dwsim/bin/python spikes/references/t06_qualification_summary.py "$OUT" --markdown \
    >"$OUT/summary.md" || status=1
echo "summary: $OUT/summary.md"
echo "EXIT $status"
exit "$status"
