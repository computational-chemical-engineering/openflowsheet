#!/usr/bin/env bash
# S17 blind gate runner: one summary line; full log, JSON report and PID in the run directory.
# usage: gate.sh <last accepted sha> [label]          a refactor step, committed provisionally (D14)
#        gate.sh --self-test <path:line[:N]> [label]  the self-test (gate G-SELF)
#        gate.sh --revert <rejected sha> [label]        HEAD exactly undoes <rejected sha> (review reject, D15)
#        gate.sh --no-gain <last accepted sha> [label]  names/docstrings only, no gain check (D15)
# The campaign base (docs/S17_STATE.md) is passed as --ref-base: the tests tier's map (D13).
# Stop a run with: kill -INT "$(cat <tag>.pid)"
set -u
CB=1fd6826b2f433c73c4c41ef6ccad1dcb903985c8
GC=$(git rev-parse --path-format=absolute --git-common-dir)
CH="$(dirname "$GC")/.venv-codehealth/bin/codehealth"
OUT="$GC/codehealth/runs/s17-gates"
mkdir -p "$OUT"
if [ "${1:-}" = "--self-test" ]; then
    args=(gate --self-test --mutate "$2" --ref-base "$CB"); label="${3:-selftest}"
elif [ "${1:-}" = "--revert" ]; then
    # HEAD is a commit that exactly undoes $2 (review reject); base = the commit before HEAD (D15).
    args=(gate --mode refactor --revert "$2" --base "$(git rev-parse HEAD~1)" --ref-base "$CB"); label="${3:-revert}"
elif [ "${1:-}" = "--no-gain" ]; then
    # names, docstrings or ordering only (review notes): behaviour tiers, no gain check (D15).
    args=(gate --mode refactor --base "$2" --ref-base "$CB"); label="${3:-nogain}"
else
    args=(gate --mode refactor --base "$1" --ref-base "$CB" --require-gain); label="${2:-step}"
fi
tag="$(date +%Y%m%dT%H%M%S)-$label"
"$CH" "${args[@]}" --json "$OUT/$tag.json" --log "$OUT/$tag.tiers.log" > "$OUT/$tag.log" 2>&1 &
pid=$!
echo "$pid" > "$OUT/$tag.pid"
wait "$pid"; rc=$?
rm -f "$OUT/$tag.pid"
echo "GATE $label rc=$rc | $(tail -n 1 "$OUT/$tag.log") | json $OUT/$tag.json | log $OUT/$tag.log"
exit "$rc"
