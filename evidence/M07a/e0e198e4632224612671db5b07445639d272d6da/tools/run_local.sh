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

# -- environments ----------------------------------------------------------------------------
if [ ! -x "$PY" ]; then
    step venv env -u PYTHONPATH PATH=$SYS_PATH /usr/bin/python3 -m venv $W/rcvenv
    step venv-lock env -u PYTHONPATH PATH=$SYS_PATH $W/rcvenv/bin/pip install -r $RC/requirements.lock
    step venv-editable env -u PYTHONPATH PATH=$SYS_PATH $W/rcvenv/bin/pip install --no-deps -e $RC
fi
git -C "$RC" status --porcelain > $LOGS/tree-after-venv.txt
step reactor-build env -u PYTHONPATH $PY -m openflowsheet.adapters.pymrm.env build --variant pymrm-6089593-g2-nz800-s123-v1 --root $W/external
step reactor-verify env -u PYTHONPATH $PY -m openflowsheet.adapters.pymrm.env verify --variant pymrm-6089593-g2-nz800-s123-v1 --root $W/external
step xcheck-venv env -u PYTHONPATH PATH=$SYS_PATH /usr/bin/python3 -m venv $W/venv-xcheck
step xcheck-pins env -u PYTHONPATH PATH=$SYS_PATH $W/venv-xcheck/bin/pip install chemicals==1.5.2 thermo==0.6.1 CoolProp==8.0.0 cantera==3.2.0 pyyaml==6.0.2
if [ ! -d $W/idaes-wt ]; then git -C "$RC" worktree add --detach $W/idaes-wt $C > $LOGS/idaes-wt.log 2>&1; fi
(cd $W/idaes-wt && step idaes-env env -u PYTHONPATH PATH=$SYS_PATH bash scripts/build-reference-envs.sh idaes $LOGS/idaes-env.build.log)

# -- step 11 ---------------------------------------------------------------------------------
S11=$A/step11; mkdir -p $S11
env -u PYTHONPATH $W/venv-xcheck/bin/pip freeze > $S11/venv-xcheck.freeze.txt
step step11-xcheck env -u PYTHONPATH $W/venv-xcheck/bin/python -I benchmarks/m01/external_crosscheck.py --check
cp $LOGS/step11-xcheck.log $S11/external-crosscheck-check.stdout.txt
step step11-idaes env -u PYTHONPATH IDAES_DATA=$W/idaes-wt/.venv-idaes/idaes-data $W/idaes-wt/.venv-idaes/bin/python -I benchmarks/m01/idaes_conformance.py --out $S11/idaes-conformance.json
cp $LOGS/step11-idaes.log $S11/idaes-conformance.stdout.txt
env -u PYTHONPATH $W/idaes-wt/.venv-idaes/bin/pip freeze | LC_ALL=C sort > $S11/venv-idaes.freeze.txt

# -- step 12 ---------------------------------------------------------------------------------
S12=$A/step12; mkdir -p $S12
{ uname -a; lscpu; } > $S12/host.txt
cp $W/external/pymrm-6089593-032a050c6cf3/env-manifest.json $S12/env-manifest.json
cp benchmarks/m02/g11-coverage.json $S12/g11-coverage.json   # G11's --compare input (m02 manifest's superseded record)
sha256sum $M02A/wo12a-double-prime/artifacts/g10-adapter-halves-v3-d83.json $M02A/wo12a-experiment/artifacts/g11-exp.json \
    $M02A/wo12a-double-prime/artifacts/g11-coverage-v3-wo12a-prime.json $M02A/wo12a-prime/artifacts/g11-coverage-v3.runs.json > $S12/archived-inputs.sha256
step step12-g10 env -u PYTHONPATH $PY benchmarks/m02/g10_adapter_halves.py \
    --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g10-adapter-halves.json \
    --previous-v3 $M02A/wo12a-double-prime/artifacts/g10-adapter-halves-v3-d83.json --out $S12/g10-adapter-halves-v3.json
step step12-g11 env -u PYTHONPATH $PY benchmarks/m02/g11_coverage_v3.py \
    --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g11-coverage.json \
    --d78 $M02A/wo12a-experiment/artifacts/g11-exp.json \
    --previous $M02A/wo12a-double-prime/artifacts/g11-coverage-v3-wo12a-prime.json \
    --previous-runs $M02A/wo12a-prime/artifacts/g11-coverage-v3.runs.json --out $S12/g11-coverage-v3.json
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
