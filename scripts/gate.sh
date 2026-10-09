#!/usr/bin/env bash
# Quiet gate: runs scripts/check.sh with the full log in a file and prints one summary line.
# On failure it also prints the failing lines (grep), never the whole log. Exit code is check.sh's.
# Usage: scripts/gate.sh [log-file]   (default: $TMPDIR or /tmp, gate-<sha>.log)
set -uo pipefail
cd "$(dirname "$0")/.."
sha=$(git rev-parse --short HEAD 2>/dev/null || echo nogit)
log="${1:-${TMPDIR:-/tmp}/gate-${sha}.log}"
./scripts/check.sh >"$log" 2>&1
rc=$?
counts=$(grep -E '^[0-9]+ (passed|failed)' "$log" | tail -1)
if [ "$rc" -eq 0 ]; then
    echo "GATE PASS ${sha}: ${counts} (log ${log})"
else
    echo "GATE FAIL ${sha} (exit ${rc}): ${counts:-no pytest summary} (log ${log})"
    grep -E '^(FAILED|ERROR) |--- .*: exit [1-9]|^Found [0-9]+ error' "$log" | head -20
fi
exit "$rc"
