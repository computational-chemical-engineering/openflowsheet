#!/usr/bin/env bash
# S19 blind gate runner: one summary line; full log, JSON report and PID in the run directory.
# usage: gate.sh <last accepted sha> [label]          a refactor step, committed provisionally (D14)
#        gate.sh --self-test <path:line[:N]> [label]  the self-test (gate G-SELF)
#        gate.sh --revert <rejected sha> [label]        HEAD exactly undoes <rejected sha> (review reject, D15)
#        gate.sh --no-gain <last accepted sha> [label]  names/docstrings only, no gain check (D15)
#        gate.sh --restructure <last accepted sha> <plan path> [label]  a module split (D18); the plan and the
#                                                       layer entries must be committed at or before that base (the gate reads both at base)
# The map base MB (docs/S19_STATE.md) is passed as --ref-base: the tests tier's map (D13).
# Stop a run with: kill -INT "$(cat <tag>.pid)"
set -u
CB=d90b498f8759b739361016cca7858f71bc647ccc
# S19: CB is the debt baseline; MB (the map base) moves to milestone commits and is read from the state file.
MB=$(sed -n 's/^- `MB` = `\([0-9a-f]\{40\}\)`.*/\1/p' "$(git rev-parse --show-toplevel)/docs/S19_STATE.md" | head -n 1)
[ -n "$MB" ] || { echo "GATE no MB in docs/S19_STATE.md"; exit 2; }
GC=$(git rev-parse --path-format=absolute --git-common-dir)
CH="$(dirname "$GC")/.venv-codehealth/bin/codehealth"
OUT="$GC/codehealth/runs/s19-gates"
mkdir -p "$OUT"
if [ "${1:-}" = "--self-test" ]; then
    args=(gate --self-test --mutate "$2" --ref-base "$MB"); label="${3:-selftest}"
elif [ "${1:-}" = "--revert" ]; then
    # HEAD is a commit that exactly undoes $2 (review reject); base = the commit before HEAD (D15).
    args=(gate --mode refactor --revert "$2" --base "$(git rev-parse HEAD~1)" --ref-base "$MB"); label="${3:-revert}"
elif [ "${1:-}" = "--restructure" ]; then
    # a split under an approved plan: behaviour tiers plus plan checks, no gain check (D18, D20).
    args=(gate --mode restructure --plan "$3" --base "$2" --ref-base "$MB"); label="${4:-restructure}"
elif [ "${1:-}" = "--no-gain" ]; then
    # names, docstrings or ordering only (review notes): behaviour tiers, no gain check (D15).
    args=(gate --mode refactor --base "$2" --ref-base "$MB"); label="${3:-nogain}"
else
    args=(gate --mode refactor --base "$1" --ref-base "$MB" --require-gain); label="${2:-step}"
fi
# One gate at a time per clone: the suite holds wall-time budget tests (t07_v17_reference f6) that fail under the
# load of two concurrent full suites (G-SELF 2026-11-14: 333 s against 300 s). Parallel lanes queue here.
exec 9>"$OUT/gate.lock"
flock 9
tag="$(date +%Y%m%dT%H%M%S)-$label"
"$CH" "${args[@]}" --json "$OUT/$tag.json" --log "$OUT/$tag.tiers.log" > "$OUT/$tag.log" 2>&1 9>&- &
pid=$!
echo "$pid" > "$OUT/$tag.pid"
wait "$pid"; rc=$?
rm -f "$OUT/$tag.pid"
echo "GATE $label rc=$rc | $(tail -n 1 "$OUT/$tag.log") | json $OUT/$tag.json | log $OUT/$tag.log"
exit "$rc"
