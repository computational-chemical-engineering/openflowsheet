#!/usr/bin/env bash
# WO-10 local RC steps 11, 12 and 10 at C_α (second session; the first session's scratch was lost).
# One line per command in $W/summary.txt: "<label> exit <code> :: <command>".
set -u
W=/home/frankp/.cache/of-rca-e0e198e
RC=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-e0e198e
C=e0e198e4632224612671db5b07445639d272d6da
A=$RC/evidence/M07a/$C/artifacts/rc
M02A=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m02/evidence/M02
SYS_PATH=/usr/local/bin:/usr/bin:/bin
LOGS=$W/logs; mkdir -p $LOGS
SUM=$W/summary.txt
step() {  # step <label> <command...>; log to $LOGS/<label>.log
    local label=$1; shift
    "$@" > "$LOGS/$label.log" 2>&1
    local code=$?
    echo "$label exit $code :: $*" >> "$SUM"
    return $code
}
PY=$W/rcvenv/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export OPENFLOWSHEET_EXTERNAL_ROOT=$W/external
cd "$RC"
S12=$A/step12
step step12-g12 env -u PYTHONPATH $PY $W/tools/g12keep.py $S12/g12-bundles \
    --out $S12/g12-real-loop-v3.json --compare benchmarks/m02/g12-real-loop.json
step step12-g12-edges env -u PYTHONPATH $PY $W/tools/g12keep.py $S12/g12-edges-bundles \
    --t-in 653.15 --t-in 693.15 --out $S12/g12-real-loop-v3-edges.json
step step12-m02-tests env -u PYTHONPATH $PY -m pytest -q -p no:cacheprovider -m 'pymrm or not pymrm' \
    --junitxml=$S12/m02-tests.junit.xml tests/test_m02_*.py
for l in step12-g10 step12-g11 step12-g12 step12-g12-edges step12-m02-tests; do cp $LOGS/$l.log $S12/$l.log; done

# -- step 10 (local, over steps 2, 6, 7, 8 and 12) ----------------------------------------------
step step10-certificates env -u PYTHONPATH $PY scripts/t08_rc.py certificates --out $A/certificates-ref-x86-64.json \
    $A/identity $A/ensemble $A/surface $A/step12
git -C "$RC" status --porcelain > $LOGS/tree-at-end.txt
echo "EXIT run_local done" >> "$SUM"
