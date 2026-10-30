#!/usr/bin/env bash
# M07 WO-8c: RC step 14 at C' as attempt 3 at C (called from run_local.sh). WO-8b: RC step 14 re-run (attempt 2). Attempt 1 ran in the RC worktree, where the RC venv's
# editable install had written src/openflowsheet.egg-info: with PYTHONPATH=<RC>/src that is an 18th
# distribution in the audited environment's fingerprint (17 recorded), and run_local.sh's exported
# OPENBLAS/MKL_NUM_THREADS=1 entered the NLP fixtures' thread_variables. Attempt 2 runs in a clean
# detached worktree at C with no install into it, with only the variables m03_nlp_check.sh and
# M05's manifest set. Records go to the RC worktree's artifacts as before.
# V03 WO-6: the nlp check gets the modules that hold `mark.nlp` (E01 run N's selection; -m nlp
# selects the same 190 nodes as over tests/), since tests/test_s10_*.py import mpmath at module level.
# Attempt 3: tests/test_m03_reference.py dropped from step14-tests: it needs mpmath, which belongs to the
# project env (step14-m03-reference runs the generator --check there); the nlp env does not carry it.
set -u
W=$(cd "$(dirname "$0")/.." && pwd)
RC=$1; WT=$W/nlp-wt
C=$(git -C "$RC" rev-parse HEAD)
A=$RC/evidence/S13/$C/artifacts/rc
NLP=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05/.venv-nlp
NLPCACHE=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05/.reference-downloads/m03-ipopt
LOGS=$W/logs; SUM=$W/summary.txt
step() { local label=$1; shift; local t0=$SECONDS; "$@" > "$LOGS/$label.log" 2>&1; local code=$?
    echo "$label exit $code :: $*" >> "$SUM"; echo "$label $((SECONDS - t0))" >> "$W/durations.txt"; return $code; }
[ -d "$WT" ] || git -C "$RC" worktree add --detach "$WT" "$C" > "$LOGS/nlp-wt.log" 2>&1
cd "$WT"
[ "$(git rev-parse HEAD)" = "$C" ] || exit 2
git status --porcelain --ignored > "$LOGS/nlp-wt-at-start.txt"
NLPENV=(env -i HOME="$HOME" PATH="$PATH" LANG="${LANG:-C.UTF-8}" OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1
        PYOMO_CONFIG_DIR=$NLP/share/pyomo PYTHONPATH=$WT/src:$NLPCACHE/nlp-test-tools)
S14=$A/step14; mkdir -p "$S14"
grep -l 'mark.nlp' tests/test_*.py > "$S14/nlp-modules.txt"
step step14-nlp-check env -i HOME="$HOME" PATH="$PATH" LANG="${LANG:-C.UTF-8}" bash scripts/m03_nlp_check.sh "$NLP" "$NLPCACHE" \
    -- -o junit_family=xunit1 --junitxml="$S14/nlp.junit.xml" --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step14-nlp $(grep -l 'mark.nlp' tests/test_*.py)
# V03 Amendment 2 (R-907, V03.A33): -m nlp collects the same node ids over the modules as over tests/.
step step14-nlp-collect-selected "${NLPENV[@]}" "$NLP/bin/python" -m pytest --collect-only -q -p no:cacheprovider -m nlp $(cat "$S14/nlp-modules.txt")
step step14-nlp-collect-all "${NLPENV[@]}" "$NLP/bin/python" -m pytest --collect-only -q -p no:cacheprovider -m nlp tests/
step step14-tests "${NLPENV[@]}" "$NLP/bin/python" -m pytest -q -rs -p no:cacheprovider -m "nlp or not nlp" \
    --junitxml="$S14/m03-m05-tests.junit.xml" --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step14-tests tests/test_m05_*.py tests/test_m03_nlp_isolation.py \
    tests/test_m03_nlp_greybox.py
step step14-m05-real-replay "${NLPENV[@]}" "$NLP/bin/python" scripts/m05_wo9_real.py --replay
step step14-m03-reference env -i HOME="$HOME" PATH="$PATH" PYTHONPATH="$WT/src" "$W/rcvenv/bin/python" docs/derivations/scripts/m03_reference.py --check
for l in step14-nlp-check step14-nlp-collect-selected step14-nlp-collect-all step14-tests step14-m05-real-replay step14-m03-reference; do cp "$LOGS/$l.log" "$S14/$l.log"; done
git status --porcelain --ignored > "$LOGS/nlp-wt-at-end.txt"
step record-step14 env -u PYTHONPATH "$W/rcvenv/bin/python" "$W/tools/m07_rc_external.py" step14 --rc "$RC" --commit "$C" --summary "$SUM" --logs "$LOGS"
echo "EXIT run_step14 done" >> "$SUM"
