#!/usr/bin/env bash
# S19 blind gate runner: one summary line; full log, JSON report and PID in the run directory.
# usage: gate.sh <last accepted sha> [label]          a refactor step, committed provisionally (D14)
#        gate.sh --self-test <path:line[:N]> [label]  the self-test (gate G-SELF)
#        gate.sh --revert <rejected sha> [label]        HEAD exactly undoes <rejected sha> (review reject, D15)
#        gate.sh --no-gain <last accepted sha> [label]  names/docstrings only, no gain check (D15)
#        gate.sh --restructure <last accepted sha> <plan path> [label]  a module split (D18); the plan and the
#                                                       layer entries must be committed at or before that base (the gate reads both at base)
#        gate.sh --interface <plan commit> <plan path> [label]  an ADR 0076 W4 interface step (the plan committed at the base)
#        gate.sh --behaviour-only <wp/S19 sha> [label]  a lane's merge-check: the base's behaviour tiers over base..HEAD,
#                                                       the FULL suite, no static checks, debt reported not gated, not loggable
# W5 gate mode: with S19_W5_BATCH set to a batch file (gate_queue.py --mode w5 sets it for a W5 step, any mode
# above otherwise unchanged), the base's tiers judge the step against the batch base (scripts/w5_gate.py) and the
# frozen list leaves out the batch's admitted paths. The batch file is checked first: batch P (W5-S2) exits 2.
# The map base MB (docs/S19_STATE.md) is passed as --ref-base: the tests tier's map (D13).
# Stop a run with: kill -INT "$(cat <tag>.pid)"
set -u
CB=d90b498f8759b739361016cca7858f71bc647ccc
# S19: CB is the debt baseline; MB (the map base) moves to milestone commits and is read from the state file.
MB=$(sed -n 's/^- `MB` = `\([0-9a-f]\{40\}\)`.*/\1/p' "$(git rev-parse --show-toplevel)/docs/S19_STATE.md" | head -n 1)
[ -n "$MB" ] || { echo "GATE no MB in docs/S19_STATE.md"; exit 2; }
if [ -n "${S19_W5_BATCH:-}" ]; then
    python3 "$(git rev-parse --show-toplevel)/scripts/w5_gate.py" batch "$S19_W5_BATCH" || exit 2
fi
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
elif [ "${1:-}" = "--interface" ]; then
    # an ADR 0076 W4 interface step: behaviour tiers plus the public-API plan check (migration rule 1).
    args=(gate --mode interface --plan "$3" --base "$2" --ref-base "$MB"); label="${4:-interface}"
elif [ "${1:-}" = "--behaviour-only" ]; then
    # merge-check of a gated lane (cce-code-health 1304e31; replaces merge_tiers.sh): tiers only, full suite.
    args=(gate --behaviour-only --mode refactor --cadence campaign --base "$2" --ref-base "$MB"); label="${3:-mc}"
    export S19_GATE_FULL=1
elif [ "${1:-}" = "--no-gain" ]; then
    # names, docstrings or ordering only (review notes): behaviour tiers, no gain check (D15).
    args=(gate --mode refactor --base "$2" --ref-base "$MB"); label="${3:-nogain}"
else
    args=(gate --mode refactor --base "$1" --ref-base "$MB" --require-gain); label="${2:-step}"
fi
# Two gates at a time per clone (Frank, 2026-11-15: "Run more gates at a time if needed"; S19_DECISIONS). Slot 1 is
# the old single lock, so gates queued under the one-slot script share it. The wall-time budget test
# t07_v17_reference f6 fails under two concurrent suites (G-SELF 2026-11-14: 333 s against 300 s), so gates deselect
# it; it runs alone on wp/S19 before each merge into main, and CI runs it on both legs.
# Temporary files on disk, not the RAM-backed /tmp (2026-11-15: two gates and a map build filled /tmp, ENOSPC).
# Outside every repository tree: tests check that their temporary projects cannot see the repo (CLAUDE.md, x05).
mkdir -p "$HOME/.cache/openflowsheet/tmp-gates" && export TMPDIR="$HOME/.cache/openflowsheet/tmp-gates"
# 8 xdist workers per gate with two slots on 16 cores (load 40 to 65 at 12 each pushed tests past the 900 s
# per-test limit); read by the tests tier of .codehealth/config.toml from 2026-11-15 on.
export S19_GATE_WORKERS="${S19_GATE_WORKERS:-8}"
export PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-} --deselect tests/test_t07_v17_reference.py::test_f6_the_forty_runs_fit_their_budget --deselect tests/test_t07_conformance.py::test_the_budget_of_the_scenario_runs"
slot=""
while [ -z "$slot" ]; do
    for s in gate.lock gate.slot2.lock; do
        exec 9>"$OUT/$s"
        if flock -n 9; then slot="$s"; break; fi
        exec 9>&-
    done
    [ -n "$slot" ] || sleep 15
done
tag="$(date +%Y%m%dT%H%M%S)-$label"
"$CH" "${args[@]}" --json "$OUT/$tag.json" --log "$OUT/$tag.tiers.log" > "$OUT/$tag.log" 2>&1 9>&- &
pid=$!
echo "$pid" > "$OUT/$tag.pid"
wait "$pid"; rc=$?
rm -f "$OUT/$tag.pid"
echo "GATE $label rc=$rc | $(tail -n 1 "$OUT/$tag.log") | json $OUT/$tag.json | log $OUT/$tag.log"
exit "$rc"
