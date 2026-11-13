#!/usr/bin/env bash
# S17 blind gate runner: one summary line; full log, JSON report and PID in the run directory.
# usage: gate.sh <last accepted sha> [label]          a refactor step
#        gate.sh --self-test <path:line> [label]      the self-test (gate G-SELF)
# Needs OFS_MAP_BASE (the campaign base, docs/S17_STATE.md). Stop a run with: kill -INT "$(cat <tag>.pid)"
set -u
: "${OFS_MAP_BASE:?set OFS_MAP_BASE to the campaign base (docs/S17_STATE.md)}"
export OFS_MAP_BASE
GC=$(git rev-parse --path-format=absolute --git-common-dir)
CH="$(dirname "$GC")/.venv-codehealth/bin/codehealth"
OUT="$GC/codehealth/runs/s17-gates"
mkdir -p "$OUT"
if [ "${1:-}" = "--self-test" ]; then
    args=(gate --self-test --mutate "$2"); label="${3:-selftest}"
else
    args=(gate --mode refactor --base "$1"); label="${2:-step}"
fi
tag="$(date +%Y%m%dT%H%M%S)-$label"
"$CH" "${args[@]}" --json "$OUT/$tag.json" --log "$OUT/$tag.tiers.log" > "$OUT/$tag.log" 2>&1 &
pid=$!
echo "$pid" > "$OUT/$tag.pid"
wait "$pid"; rc=$?
rm -f "$OUT/$tag.pid"
echo "GATE $label rc=$rc | $(tail -n 1 "$OUT/$tag.log") | log $OUT/$tag.log"
exit "$rc"
