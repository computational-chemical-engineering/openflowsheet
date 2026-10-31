#!/usr/bin/env bash
# V03 WO-6 (V03 spec §4): the local RC steps 2, 6-17 at C, from a clean detached worktree
# at C. Copied from 0.2.0's run at C' (evidence/M07/ce99365…/tools/run_local.sh), retargeted to
# evidence/S13/<C>, with these changes: step 15 carries the journey recorded at J = 2d945b5d (WO-5)
# with scripts/v0_3_gate.py; step 17 is V03's 17a-17e (not W27's, which v0.3 does not claim); the
# records of steps 15 and 17a-17e are written by C's scripts/v03_rc.py, those of 11-14 and 16 by
# 0.2.0's m07_rc_external.py (output path evidence/S13). One line per command in $W/summary.txt:
# "<label> exit <code> :: <command>".
set -u
W=$(cd "$(dirname "$0")/.." && pwd)
RC=$1                                   # the detached worktree at C
C=$(git -C "$RC" rev-parse HEAD)
J=2d945b5d4a6767e712df16719f842cc12afd4e64
A=$RC/evidence/S13/$C/artifacts/rc
NLP=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05/.venv-nlp
NLPCACHE=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05/.reference-downloads/m03-ipopt
W27A=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts
SYS_PATH=/usr/local/bin:/usr/bin:/bin
LOGS=$W/logs; mkdir -p "$LOGS" "$A"
SUM=$W/summary.txt
step() {  # step <label> <command...>; log to $LOGS/<label>.log
    local label=$1; shift
    local t0=$SECONDS
    "$@" > "$LOGS/$label.log" 2>&1
    local code=$?
    echo "$label exit $code :: $*" >> "$SUM"
    echo "$label $((SECONDS - t0))" >> "$W/durations.txt"
    return $code
}
PY=$W/rcvenv/bin/python
NLPENV=(env -u PYTHONPATH -u OPENFLOWSHEET_EXTERNAL_ROOT OMP_NUM_THREADS=1 PYTHONNOUSERSITE=1
        PYOMO_CONFIG_DIR=$NLP/share/pyomo PYTHONPATH=$RC/src:$NLPCACHE/nlp-test-tools)
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$RC"
git status --porcelain > "$LOGS/tree-at-start.txt"

# -- environments ----------------------------------------------------------------------------
if [ ! -x "$PY" ]; then
    step venv env -u PYTHONPATH PATH=$SYS_PATH /usr/bin/python3 -m venv "$W/rcvenv"
    step venv-lock env -u PYTHONPATH PATH=$SYS_PATH "$W/rcvenv/bin/pip" install -r "$RC/requirements.lock"
    step venv-editable env -u PYTHONPATH PATH=$SYS_PATH "$W/rcvenv/bin/pip" install --no-deps -e "$RC"
fi
git status --porcelain > "$LOGS/tree-after-venv.txt"
mkdir -p evidence/M06/W27/artifacts
[ -e evidence/M06/W27/artifacts/OpenIDAES-450-demo.tar.gz ] || cp -al "$W27A/OpenIDAES-450-demo.tar.gz" evidence/M06/W27/artifacts/
[ -e evidence/M06/W27/artifacts/extracted ] || cp -al "$W27A/extracted" evidence/M06/W27/artifacts/
git status --porcelain > "$LOGS/tree-after-archive.txt"

# -- step 6 in the background (the longest) --------------------------------------------------
( OMP_NUM_THREADS=1 OPENFLOWSHEET_EXTERNAL_ROOT=$W/external \
  step step06-ensemble env -u PYTHONPATH "$PY" scripts/t08_rc.py ensemble --out "$A/ensemble" ) &
ENS=$!

export OMP_NUM_THREADS=1
(
export OPENFLOWSHEET_EXTERNAL_ROOT=$W/external
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

# -- step 12 (0.2.0's inputs: bd446ab's v3 records, the registered D78 extract) ---------------
S12=$A/step12; mkdir -p "$S12" "$W/inputs"
git show bd446ab:benchmarks/m02/g10-adapter-halves-v3.json > "$W/inputs/g10-adapter-halves-v3-bd446ab.json"
git show bd446ab:benchmarks/m02/g11-coverage-v3.json > "$W/inputs/g11-coverage-v3-bd446ab.json"
{ uname -a; lscpu; } > "$S12/host.txt"
cp "$W"/external/pymrm-6089593-*/env-manifest.json "$S12/env-manifest.json"
cp benchmarks/m02/g11-coverage.json "$S12/g11-coverage.json"
sha256sum "$W"/inputs/*.json > "$S12/archived-inputs.sha256"
sha256sum "$W/tools/g12keep.py" > "$S12/g12keep.sha256"
step step12-g10 env -u PYTHONPATH "$PY" benchmarks/m02/g10_adapter_halves.py \
    --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g10-adapter-halves.json \
    --previous-v3 "$W/inputs/g10-adapter-halves-v3-bd446ab.json" --out "$S12/g10-adapter-halves-v3.json"
sha256sum docs/derivations/scripts/m07_g11_d78_extract.json > "$S12/d78-extract.sha256"
step step12-g11 env -u PYTHONPATH "$PY" benchmarks/m02/g11_coverage_v3.py \
    --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g11-coverage.json \
    --d78 docs/derivations/scripts/m07_g11_d78_extract.json --previous "$W/inputs/g11-coverage-v3-bd446ab.json" \
    --out "$S12/g11-coverage-v3.json"
rm -rf "$S12/g12-bundles" "$S12/g12-edges-bundles"
step step12-g12 env -u PYTHONPATH "$PY" "$W/tools/g12keep.py" "$S12/g12-bundles" \
    --out "$S12/g12-real-loop-v3.json" --compare benchmarks/m02/g12-real-loop.json
step step12-g12-edges env -u PYTHONPATH "$PY" "$W/tools/g12keep.py" "$S12/g12-edges-bundles" \
    --t-in 653.15 --t-in 693.15 --out "$S12/g12-real-loop-v3-edges.json"
step step12-m02-tests env -u PYTHONPATH "$PY" -m pytest -q -p no:cacheprovider -m 'pymrm or not pymrm' --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step12 \
    --junitxml="$S12/m02-tests.junit.xml" tests/test_m02_*.py
for l in step12-g10 step12-g11 step12-g12 step12-g12-edges step12-m02-tests; do [ -f "$LOGS/$l.log" ] && cp "$LOGS/$l.log" "$S12/$l.log"; done
)

# -- step 13 (W23) ---------------------------------------------------------------------------
S13=$A/step13; mkdir -p "$S13"
step step13-generator env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" docs/derivations/scripts/m04_reference.py --check
step step13-fixtures env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" scripts/m04_schema_fixtures.py
step step13-tests env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" -m pytest -q -rs -p no:cacheprovider --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step13 \
    --junitxml="$S13/m04-tests.junit.xml" tests/test_m04_*.py tests/test_evidence_manifests.py
for l in step13-generator step13-fixtures step13-tests; do cp "$LOGS/$l.log" "$S13/$l.log"; done

# -- step 14 (W24), clean nlp worktree, env -i ------------------------------------------------
bash "$W/tools/run_step14.sh" "$RC" > "$LOGS/run_step14.out" 2>&1

# -- step 15 (W25): the journey of J carried to C; check and replay at C -----------------------
S15=$A/step15; mkdir -p "$S15"
step step15-carry env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" scripts/v0_3_gate.py --rc "$C" --carry-journey "${J:0:8}"
step step15-check "${NLPENV[@]}" PYTHONPATH="$RC/src" "$NLP/bin/python" scripts/m07_journey.py check "benchmarks/m07/journey/$J"
step step15-replay "${NLPENV[@]}" PYTHONPATH="$RC/src" "$NLP/bin/python" scripts/m07_journey.py replay "benchmarks/m07/journey/$J"
for l in step15-carry step15-check step15-replay; do cp "$LOGS/$l.log" "$S15/$l.log"; done

wait $ENS

# -- step 10 (local, over steps 2, 6, 8 and 12) -----------------------------------------------
step step10-certificates env -u PYTHONPATH "$PY" scripts/t08_rc.py certificates --out "$A/certificates-ref-x86-64.json" \
    "$A/identity" "$A/ensemble" "$A/surface" "$A/step12"

# -- step 16 (W26), after the ensemble -------------------------------------------------------
S16=$A/step16; mkdir -p "$S16"
step step16-tests env -u PYTHONPATH OPENFLOWSHEET_REQUIRE_BROWSER=1 PYTHONPATH="$RC/src:$RC" "$PY" -m pytest -q -rs \
    -p no:cacheprovider --junitxml="$S16/m06-tests.junit.xml" tests/test_m06_*.py --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step16
step step16-node node --test --test-reporter=spec tests/web/*.test.mjs
step step16-dryrun env -u PYTHONPATH PYTHONPATH="$RC/src:$RC" "$PY" -m benchmarks.m06.w27.dryrun \
    --out "evidence/M06/W27/artifacts/dry-run/${C:0:7}"
for l in step16-tests step16-node step16-dryrun; do cp "$LOGS/$l.log" "$S16/$l.log"; done

# -- step 17 (V03 17a-17e) -------------------------------------------------------------------
S17=$A/step17; mkdir -p "$S17"
P=(env -u PYTHONPATH PYTHONPATH="$RC/src:$RC")
# 17b, and 17c's coolprop check: the main lock, then the coolprop lock (--no-deps --require-hashes)
step step17b-venv env -u PYTHONPATH PATH=$SYS_PATH /usr/bin/python3 -m venv "$W/cpvenv"
step step17b-lock env -u PYTHONPATH PATH=$SYS_PATH "$W/cpvenv/bin/pip" install -r "$RC/requirements.lock"
step step17b-coolprop-lock env -u PYTHONPATH PATH=$SYS_PATH "$W/cpvenv/bin/pip" install --no-deps --require-hashes -r "$RC/requirements-coolprop.lock"
step step17b-editable env -u PYTHONPATH PATH=$SYS_PATH "$W/cpvenv/bin/pip" install --no-deps -e "$RC"
BUILD_PY=$(env -u PYTHONPATH "$W/cpvenv/bin/python" -c 'import pathlib, sys; sys.path.insert(0, "scripts"); import t08_dist; print(t08_dist.build_environment(pathlib.Path(sys.argv[1]), t08_dist.SETUPTOOLS)[0])' "$W/build-venv" 2> "$LOGS/step17b-build-python.log")
echo "$BUILD_PY" >> "$LOGS/step17b-build-python.log"
grep -lE 'CoolProp|s07_coolprop_support' tests/test_s07_*.py tests/test_s11_*.py > "$S17/17b-modules.txt"
step step17b-tests "${P[@]}" OPENFLOWSHEET_REQUIRE_COOLPROP=1 OFS_S07_BUILD_PYTHON="$BUILD_PY" "$W/cpvenv/bin/python" -m pytest -q -rs \
    -p no:cacheprovider --junitxml="$S17/17b.junit.xml" --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step17b $(cat "$S17/17b-modules.txt")
step step17c-coolprop "${P[@]}" "$W/cpvenv/bin/python" scripts/t07_licence_inventory.py --extra coolprop --out "$S17/17c-coolprop-inventory.json"
step step17c-lca "${P[@]}" "$PY" scripts/e01_d04_inventory.py --check
# 17d: the lca environment (A24, A25); the audited nlp environment in the clean nlp worktree (A33-A36)
step step17d-lca-env env -u PYTHONPATH PATH=$SYS_PATH bash scripts/build-lca-env.sh "$W/venv-lca" /usr/bin/python3
step step17d-lca-tests "${P[@]}" "$W/venv-lca/bin/python" -m pytest -q -rs -p no:cacheprovider --junitxml="$S17/17d-lca.junit.xml" --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step17d-lca \
    tests/test_e01_b_brightway.py tests/test_e01_b_lca.py tests/test_e01_b_tables.py tests/test_e01_b_cost_hand.py
(cd "$W/nlp-wt" && [ "$(git rev-parse HEAD)" = "$C" ] && \
 step step17d-nlp-check env -i HOME="$HOME" PATH="$PATH" LANG="${LANG:-C.UTF-8}" bash scripts/m03_nlp_check.sh "$NLP" "$NLPCACHE" \
    -- -m "nlp or not nlp" -o junit_family=xunit1 --junitxml="$S17/17d-nlp.junit.xml" --basetemp=/home/frankp/.cache/v03rc-tmp/rc-a3e508e/step17d-nlp tests/test_e01_b_nlp.py tests/test_e01_integration.py)
# 17e: the wheel from C (T08.A43), inspected (A17), a fresh venv installed from it (A19)
step step17e-dist "$PY" scripts/t08_dist.py --out "$S17/dist" --commit "$C"
step step17e-venv env -u PYTHONPATH PATH=$SYS_PATH /usr/bin/python3 -m venv "$W/wheelvenv"
step step17e-lock env -u PYTHONPATH PATH=$SYS_PATH "$W/wheelvenv/bin/pip" install -r "$RC/requirements.lock"
step step17e-wheel env -u PYTHONPATH PATH=$SYS_PATH "$W/wheelvenv/bin/pip" install --no-deps "$S17"/dist/dist/*.whl
mkdir -p "$W/probe-cwd"
(cd "$W/probe-cwd" && step step17e-probe env -u PYTHONPATH "$W/wheelvenv/bin/python" -I "$RC/scripts/v03_rc.py" probe --out "$S17/a19-installed.json")
step step17e-checkout env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" scripts/v03_rc.py probe --in-checkout --out "$S17/a19-checkout.json"
for l in step17b-tests step17c-coolprop step17c-lca step17d-lca-tests step17d-nlp-check step17e-dist step17e-probe; do [ -f "$LOGS/$l.log" ] && cp "$LOGS/$l.log" "$S17/$l.log"; done

# -- the t08-rc-v1 records -------------------------------------------------------------------
for s in step11 step12 step13 step16; do  # step14: run_step14.sh records it
    step "record-$s" env -u PYTHONPATH "$PY" "$W/tools/m07_rc_external.py" "$s" --rc "$RC" --commit "$C" \
        --summary "$SUM" --logs "$LOGS"
done
R=(--rc "$A" --commit "$C" --summary "$SUM" --logs "$LOGS")
step record-step15 env -u PYTHONPATH "$PY" scripts/v03_rc.py step15 "${R[@]}" --journey "${J:0:8}"
step record-step17a env -u PYTHONPATH "$PY" scripts/v03_rc.py step17a --rc "$A" --commit "$C"
step record-step17b env -u PYTHONPATH "$PY" scripts/v03_rc.py step17b "${R[@]}" --modules "$S17/17b-modules.txt"
step record-step17c env -u PYTHONPATH "$PY" scripts/v03_rc.py step17c "${R[@]}"
step record-step17d env -u PYTHONPATH "$PY" scripts/v03_rc.py step17d "${R[@]}"
step record-step17e env -u PYTHONPATH "$PY" scripts/v03_rc.py step17e "${R[@]}" --dist "$S17/dist" \
    --installed "$S17/a19-installed.json" --checkout "$S17/a19-checkout.json"
git status --porcelain > "$LOGS/tree-at-end.txt"
echo "EXIT run_local done" >> "$SUM"
