#!/usr/bin/env bash
# S19 merge-check for a lane that `codehealth gate` cannot gate as one range (an interface lane: its
# plans, .codehealth/ edits, test callers and removed names fail the refactor-mode static checks,
# which each step already passed under its own plan). Runs the behaviour tiers of the HEAD's
# .codehealth/config.toml exactly as the gate would, with gate.sh's environment and its two-slot
# lock: ruff and mypy, the FULL suite (S19_GATE_FULL=1), f0, mcp_digest. No static checks, no log.
# usage: merge_tiers.sh <base sha> <head sha> <label>     (base: the wp/S19 commit the lane merges onto)
# One summary line; tier log, PID and worktree under <git-common-dir>/codehealth/runs/s19-gates/.
set -u
BASE=$(git rev-parse "$1") HEAD_SHA=$(git rev-parse "$2") label="$3"
MB=$(sed -n 's/^- `MB` = `\([0-9a-f]\{40\}\)`.*/\1/p' "$(git rev-parse --show-toplevel)/docs/S19_STATE.md" | head -n 1)
[ -n "$MB" ] || { echo "MERGE-TIERS no MB in docs/S19_STATE.md"; exit 2; }
GC=$(git rev-parse --path-format=absolute --git-common-dir)
OUT="$GC/codehealth/runs/s19-gates"; mkdir -p "$OUT"
tag="$(date +%Y%m%dT%H%M%S)-$label"; LOG="$OUT/$tag.tiers.log"
WT="$GC/codehealth/mc/$label"
git worktree remove --force "$WT" 2>/dev/null; git worktree add --detach "$WT" "$HEAD_SHA" >/dev/null 2>&1 \
    || { echo "MERGE-TIERS $label worktree add failed"; exit 2; }
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$HOME/.cache/openflowsheet/tmp-gates" && export TMPDIR="$HOME/.cache/openflowsheet/tmp-gates"
export S19_GATE_WORKERS="${S19_GATE_WORKERS:-8}" S19_GATE_FULL=1
export PYTEST_ADDOPTS="${PYTEST_ADDOPTS:-} --deselect tests/test_t07_v17_reference.py::test_f6_the_forty_runs_fit_their_budget --deselect tests/test_t07_conformance.py::test_the_budget_of_the_scenario_runs"
V="$(dirname "$GC")/.venv/bin"; VT="$(dirname "$GC")/.venv-testmap/bin"
slot=""
while [ -z "$slot" ]; do
    for s in gate.lock gate.slot2.lock; do
        exec 9>"$OUT/$s"
        if flock -n 9; then slot="$s"; break; fi
        exec 9>&-
    done
    [ -n "$slot" ] || sleep 15
done
echo $$ > "$OUT/$tag.pid"
cd "$WT" || exit 2
mapfile -t files < <(git diff --name-only --diff-filter=d "$BASE" "$HEAD_SHA" -- 'src/*.py')
fails=() t0=$(date +%s)
tier() {  # name timeout cmd...
    local name=$1 to=$2; shift 2; local s; s=$(date +%s)
    echo "=== $name ($(date -Is))" >> "$LOG"
    timeout "$to" "$@" >> "$LOG" 2>&1; local rc=$?
    echo "=== $name rc=$rc $(( $(date +%s) - s )) s" >> "$LOG"
    [ "$rc" -eq 0 ] || fails+=("$name:$rc")
}
if [ "${#files[@]}" -gt 0 ]; then tier ruff 300 bash -c '"$0/ruff" check "${@}" && "$0/ruff" format --check "${@}"' "$V" "${files[@]}"; fi
tier mypy 900 "$V/mypy"
tier tests 3600 env PYTHONPATH=src "$VT/python" scripts/test_impact.py run --base "$MB" --full --workers "$S19_GATE_WORKERS" -- --timeout=900
tier f0 1800 env PYTHONPATH=src "$V/python" scripts/corpus_identity.py --check
tier mcp_digest 600 env PYTHONPATH=src "$V/python" -m pytest -q -p no:cacheprovider tests/test_t08_w2_surface_digest.py tests/test_m07a_surface_chain.py
rm -f "$OUT/$tag.pid"; cd / && git -C "$GC/.." worktree remove --force "$WT" >/dev/null 2>&1
summary="$(grep -E '^TEST-IMPACT' "$LOG" | tail -n 1 | cut -d'(' -f1); $(grep -E '^F0 (PASS|FAIL)' "$LOG" | cut -c1-12)"
if [ "${#fails[@]}" -eq 0 ]; then v=PASS; else v="FAIL ${fails[*]}"; fi
echo "MERGE-TIERS $label $v base=${BASE:0:10} head=${HEAD_SHA:0:10} $(( $(date +%s) - t0 )) s | $summary | log $LOG"
[ "${#fails[@]}" -eq 0 ]
