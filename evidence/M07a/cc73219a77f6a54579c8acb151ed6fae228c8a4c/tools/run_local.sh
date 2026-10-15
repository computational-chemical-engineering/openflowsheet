#!/usr/bin/env bash
# V02 alpha Amendment 3, action 6 (R-370): the local RC steps 2, 6, 7, 8, 9, 11, 12 and 10 at C_α²,
# all in one run, from a clean detached worktree at C_α². Same commands as C_α¹'s run
# (evidence/M07a/6fec822…/tools/run_local.sh; steps 2 and 6–9 as ci.yml's rc-steps / rc-ensemble
# run them), with step 6 run beside the others. Step 12's G12 runs through g12keep.py (R-348).
# One line per command in $W/summary.txt: "<label> exit <code> :: <command>".
set -u
W=$(cd "$(dirname "$0")/.." && pwd)
RC=$1                                   # the detached worktree at C_α²
C=$(git -C "$RC" rev-parse HEAD)
A=$RC/evidence/M07a/$C/artifacts/rc
M02A=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m02/evidence/M02
SYS_PATH=/usr/local/bin:/usr/bin:/bin
LOGS=$W/logs; mkdir -p "$LOGS" "$A"
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
git status --porcelain > "$LOGS/tree-at-start.txt"

# -- environments ----------------------------------------------------------------------------
if [ ! -x "$PY" ]; then
    step venv env -u PYTHONPATH PATH=$SYS_PATH /usr/bin/python3 -m venv "$W/rcvenv"
    step venv-lock env -u PYTHONPATH PATH=$SYS_PATH "$W/rcvenv/bin/pip" install -r "$RC/requirements.lock"
    step venv-editable env -u PYTHONPATH PATH=$SYS_PATH "$W/rcvenv/bin/pip" install --no-deps -e "$RC"
fi
git status --porcelain > "$LOGS/tree-after-venv.txt"

# -- step 6 in the background (the longest) --------------------------------------------------
( step step06-ensemble env -u PYTHONPATH "$PY" scripts/t08_rc.py ensemble --out "$A/ensemble" ) &
ENS=$!

step reactor-build env -u PYTHONPATH "$PY" -m openflowsheet.adapters.pymrm.env build --variant pymrm-6089593-g2-nz800-s123-v1 --root "$W/external"
step reactor-verify env -u PYTHONPATH "$PY" -m openflowsheet.adapters.pymrm.env verify --variant pymrm-6089593-g2-nz800-s123-v1 --root "$W/external"
step xcheck-venv env -u PYTHONPATH PATH=$SYS_PATH /usr/bin/python3 -m venv "$W/venv-xcheck"
step xcheck-pins env -u PYTHONPATH PATH=$SYS_PATH "$W/venv-xcheck/bin/pip" install chemicals==1.5.2 thermo==0.6.1 CoolProp==8.0.0 cantera==3.2.0 pyyaml==6.0.2
if [ ! -d "$W/idaes-wt" ]; then git -C "$RC" worktree add --detach "$W/idaes-wt" "$C" > "$LOGS/idaes-wt.log" 2>&1; fi
(cd "$W/idaes-wt" && step idaes-env env -u PYTHONPATH PATH=$SYS_PATH bash scripts/build-reference-envs.sh idaes "$LOGS/idaes-env.build.log")

# -- steps 2, 7, 8, 9 ------------------------------------------------------------------------
step step02-identity env -u PYTHONPATH "$PY" scripts/t08_rc.py identity --out "$A/identity"
step step07-corpus env -u PYTHONPATH "$PY" scripts/t08_rc.py corpus --out "$A/corpus-ref-x86-64.json"
step step08-surface env -u PYTHONPATH "$PY" scripts/m07a_rc.py surface --out "$A/surface"
mkdir -p "$A/a30"
step step09-a30 env -u PYTHONPATH "$PY" scripts/p03_binary_inventory.py --a30 --out "$A/a30" --summary-dir "$A/a30"
cp "$LOGS/step09-a30.log" "$A/a30.log"

# -- step 11 ---------------------------------------------------------------------------------
S11=$A/step11; mkdir -p "$S11"
env -u PYTHONPATH "$W/venv-xcheck/bin/pip" freeze > "$S11/venv-xcheck.freeze.txt"
step step11-xcheck env -u PYTHONPATH "$W/venv-xcheck/bin/python" -I benchmarks/m01/external_crosscheck.py --check
cp "$LOGS/step11-xcheck.log" "$S11/external-crosscheck-check.stdout.txt"
step step11-idaes env -u PYTHONPATH IDAES_DATA="$W/idaes-wt/.venv-idaes/idaes-data" "$W/idaes-wt/.venv-idaes/bin/python" -I benchmarks/m01/idaes_conformance.py --out "$S11/idaes-conformance.json"
cp "$LOGS/step11-idaes.log" "$S11/idaes-conformance.stdout.txt"
env -u PYTHONPATH "$W/idaes-wt/.venv-idaes/bin/pip" freeze | LC_ALL=C sort > "$S11/venv-idaes.freeze.txt"

# -- step 12 ---------------------------------------------------------------------------------
S12=$A/step12; mkdir -p "$S12"
{ uname -a; lscpu; } > "$S12/host.txt"
cp "$W"/external/pymrm-6089593-*/env-manifest.json "$S12/env-manifest.json"
cp benchmarks/m02/g11-coverage.json "$S12/g11-coverage.json"   # G11's --compare input (m02 manifest's superseded record)
sha256sum "$M02A/wo12a-double-prime/artifacts/g10-adapter-halves-v3-d83.json" "$M02A/wo12a-experiment/artifacts/g11-exp.json" \
    "$M02A/wo12a-double-prime/artifacts/g11-coverage-v3-wo12a-prime.json" "$M02A/wo12a-prime/artifacts/g11-coverage-v3.runs.json" > "$S12/archived-inputs.sha256"
sha256sum "$W/tools/g12keep.py" > "$S12/g12keep.sha256"
step step12-g10 env -u PYTHONPATH "$PY" benchmarks/m02/g10_adapter_halves.py \
    --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g10-adapter-halves.json \
    --previous-v3 "$M02A/wo12a-double-prime/artifacts/g10-adapter-halves-v3-d83.json" --out "$S12/g10-adapter-halves-v3.json"
step step12-g11 env -u PYTHONPATH "$PY" benchmarks/m02/g11_coverage_v3.py \
    --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g11-coverage.json \
    --d78 "$M02A/wo12a-experiment/artifacts/g11-exp.json" \
    --previous "$M02A/wo12a-double-prime/artifacts/g11-coverage-v3-wo12a-prime.json" \
    --previous-runs "$M02A/wo12a-prime/artifacts/g11-coverage-v3.runs.json" --out "$S12/g11-coverage-v3.json"
rm -rf "$S12/g12-bundles" "$S12/g12-edges-bundles"   # g12keep makes fresh directories only
step step12-g12 env -u PYTHONPATH "$PY" "$W/tools/g12keep.py" "$S12/g12-bundles" \
    --out "$S12/g12-real-loop-v3.json" --compare benchmarks/m02/g12-real-loop.json
step step12-g12-edges env -u PYTHONPATH "$PY" "$W/tools/g12keep.py" "$S12/g12-edges-bundles" \
    --t-in 653.15 --t-in 693.15 --out "$S12/g12-real-loop-v3-edges.json"
step step12-m02-tests env -u PYTHONPATH "$PY" -m pytest -q -p no:cacheprovider -m 'pymrm or not pymrm' \
    --junitxml="$S12/m02-tests.junit.xml" tests/test_m02_*.py
for l in step12-g10 step12-g11 step12-g12 step12-g12-edges step12-m02-tests; do cp "$LOGS/$l.log" "$S12/$l.log"; done

wait $ENS

# -- step 10 (local, over steps 2, 6, 8 and 12) -----------------------------------------------
step step10-certificates env -u PYTHONPATH "$PY" scripts/t08_rc.py certificates --out "$A/certificates-ref-x86-64.json" \
    "$A/identity" "$A/ensemble" "$A/surface" "$A/step12"

# -- the t08-rc-v1 records of steps 11 and 12 (B-WO10-8) ---------------------------------------
step record-step11 env -u PYTHONPATH "$PY" "$W/tools/m07a_rc_external.py" step11 --rc "$RC" --summary "$SUM"
step record-step12 env -u PYTHONPATH "$PY" "$W/tools/m07a_rc_external.py" step12 --rc "$RC" --summary "$SUM"
git status --porcelain > "$LOGS/tree-at-end.txt"
echo "EXIT run_local done" >> "$SUM"
