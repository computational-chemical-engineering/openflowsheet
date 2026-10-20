#!/usr/bin/env bash
# M07 WO-8b: the local RC steps 2, 6-17 of the 0.2.0 RC job at C (M07 spec §8), in one run, from a
# clean detached worktree at C. Steps 2 and 6-12 are the alpha's C_α² script
# (evidence/M07a/cc73219…/tools/run_local.sh) retargeted to evidence/M07/<C>; steps 13-17 are new.
# Step 17 is exactly §22.2's 17a-17d: every file it writes goes into the fresh $S = $W/s17, outside
# the repository; the first failure ends it. One line per command in $W/summary.txt:
# "<label> exit <code> :: <command>".
#
# Environments: the RC venv, the cross-check venv, the IDAES worktree and venv and the reactor
# environment (steps 11, 12) are built afresh under $W from C's locks, as the alpha's were.
# Steps 14 and 15 run in m05's audited NLP environment (`scripts/m03_nlp_check.sh` re-takes its
# inventory --check against docs/m03-ipopt-audit.md) with the default external root, as M05's
# manifest and the journey at K did (build log J54).
set -u
W=$(cd "$(dirname "$0")/.." && pwd)
RC=$1                                   # the detached worktree at C
C=$(git -C "$RC" rev-parse HEAD)
K=2c508b58bb40a02e1a594e062f1db8fa3b1437a2
A=$RC/evidence/M07/$C/artifacts/rc
NLP=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05/.venv-nlp
NLPCACHE=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m05/.reference-downloads/m03-ipopt
W27A=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts
CAMPAIGN=benchmarks/m06/openidaes450/runs/w27-m07-83f825d
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
# The W27 archive as a real ignored directory (hard links), for steps 16 and 17.
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

# -- step 12 ---------------------------------------------------------------------------------
# The alpha's archived M02 inputs lived in the removed m02 worktree. --previous-v3 and --previous
# are recovered byte-identical from git (bd446ab; sha256 c6a520e0…, fa1b0254…, the alpha
# record's); --d78 (afa7325a…) and --previous-runs (0656f617…) are not recoverable: G11 runs only
# if $W/inputs/g11-exp.json is supplied (WO-8b question Q1).
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
if [ -f "$W/inputs/g11-exp.json" ]; then
    step step12-g11 env -u PYTHONPATH "$PY" benchmarks/m02/g11_coverage_v3.py \
        --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g11-coverage.json \
        --d78 "$W/inputs/g11-exp.json" --previous "$W/inputs/g11-coverage-v3-bd446ab.json" \
        --out "$S12/g11-coverage-v3.json"
else
    echo "step12-g11 exit 99 :: not run: the --d78 input (g11-exp.json, sha256 afa7325a…) is not recoverable" >> "$SUM"
fi
rm -rf "$S12/g12-bundles" "$S12/g12-edges-bundles"
step step12-g12 env -u PYTHONPATH "$PY" "$W/tools/g12keep.py" "$S12/g12-bundles" \
    --out "$S12/g12-real-loop-v3.json" --compare benchmarks/m02/g12-real-loop.json
step step12-g12-edges env -u PYTHONPATH "$PY" "$W/tools/g12keep.py" "$S12/g12-edges-bundles" \
    --t-in 653.15 --t-in 693.15 --out "$S12/g12-real-loop-v3-edges.json"
step step12-m02-tests env -u PYTHONPATH "$PY" -m pytest -q -p no:cacheprovider -m 'pymrm or not pymrm' \
    --junitxml="$S12/m02-tests.junit.xml" tests/test_m02_*.py
for l in step12-g10 step12-g11 step12-g12 step12-g12-edges step12-m02-tests; do [ -f "$LOGS/$l.log" ] && cp "$LOGS/$l.log" "$S12/$l.log"; done
)

# -- step 13 (W23): M04's committed records at C ----------------------------------------------
S13=$A/step13; mkdir -p "$S13"
step step13-generator env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" docs/derivations/scripts/m04_reference.py --check
step step13-fixtures env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" scripts/m04_schema_fixtures.py
step step13-tests env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" -m pytest -q -rs -p no:cacheprovider \
    --junitxml="$S13/m04-tests.junit.xml" tests/test_m04_*.py tests/test_evidence_manifests.py
for l in step13-generator step13-fixtures step13-tests; do cp "$LOGS/$l.log" "$S13/$l.log"; done

# -- step 14 (W24): M03 nlp tier and M05 gates, audited environment ----------------------------
S14=$A/step14; mkdir -p "$S14"
step step14-nlp-check env -u PYTHONPATH -u OPENFLOWSHEET_EXTERNAL_ROOT bash scripts/m03_nlp_check.sh "$NLP" "$NLPCACHE" \
    -- -o junit_family=xunit1 --junitxml="$S14/nlp.junit.xml"
step step14-tests "${NLPENV[@]}" "$NLP/bin/python" -m pytest -q -rs -p no:cacheprovider -m "nlp or not nlp" \
    --junitxml="$S14/m03-m05-tests.junit.xml" tests/test_m05_*.py tests/test_m03_nlp_isolation.py \
    tests/test_m03_nlp_greybox.py tests/test_m03_reference.py
step step14-m05-real-replay "${NLPENV[@]}" "$NLP/bin/python" scripts/m05_wo9_real.py --replay
step step14-m03-reference env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" docs/derivations/scripts/m03_reference.py --check
for l in step14-nlp-check step14-tests step14-m05-real-replay step14-m03-reference; do cp "$LOGS/$l.log" "$S14/$l.log"; done

# -- step 15 (W25): the journey of K carried to C; check and replay at C -----------------------
S15=$A/step15; mkdir -p "$S15"
step step15-carry env -u PYTHONPATH PYTHONPATH="$RC/src" "$PY" scripts/v0_2_gate.py --rc "$C" --carry-journey 2c508b5
step step15-check "${NLPENV[@]}" PYTHONPATH="$RC/src" "$NLP/bin/python" scripts/m07_journey.py check "benchmarks/m07/journey/$K"
step step15-replay "${NLPENV[@]}" PYTHONPATH="$RC/src" "$NLP/bin/python" scripts/m07_journey.py replay "benchmarks/m07/journey/$K"
for l in step15-carry step15-check step15-replay; do cp "$LOGS/$l.log" "$S15/$l.log"; done

wait $ENS

# -- step 10 (local, over steps 2, 6, 8 and 12) -----------------------------------------------
step step10-certificates env -u PYTHONPATH "$PY" scripts/t08_rc.py certificates --out "$A/certificates-ref-x86-64.json" \
    "$A/identity" "$A/ensemble" "$A/surface" "$A/step12"

# -- step 16 (W26): M06 G1-G15 at C, local half (after the ensemble: load breaks the browser test)
S16=$A/step16; mkdir -p "$S16"
step step16-tests env -u PYTHONPATH OPENFLOWSHEET_REQUIRE_BROWSER=1 PYTHONPATH="$RC/src:$RC" "$PY" -m pytest -q -rs \
    -p no:cacheprovider --junitxml="$S16/m06-tests.junit.xml" tests/test_m06_*.py
step step16-node node --test --test-reporter=spec tests/web/*.test.mjs
step step16-dryrun env -u PYTHONPATH PYTHONPATH="$RC/src:$RC" "$PY" -m benchmarks.m06.w27.dryrun \
    --out "evidence/M06/W27/artifacts/dry-run/${C:0:7}"
for l in step16-tests step16-node step16-dryrun; do cp "$LOGS/$l.log" "$S16/$l.log"; done

# -- step 17 (W27): §22.2's 17a-17d, into the fresh $S outside the repository ------------------
S=$W/s17; rm -rf "$S"; mkdir -p "$S"
P17=(env -u PYTHONPATH -u CLAUDE_CONFIG_DIR PYTHONPATH="$RC/src")
s17() {
    step step17a-tree git rev-parse "$C:$CAMPAIGN" || return
    [ "$(tail -n1 "$LOGS/step17a-tree.log")" = 95f9fcf2c6a24084b823746959971fc5e183895a ] || { echo "RC step 17: W27 campaign record differs from the judged record" >> "$SUM"; return 1; }
    step step17b-coverage "${P17[@]}" "$PY" -m benchmarks.m06.w27.coverage --out "$S/coverage-at-C.json" || { echo "RC step 17: W27 coverage at C failed" >> "$SUM"; return 1; }
    step step17c-write "${P17[@]}" "$PY" "$W/tools/write_carry.py" "$RC" "$S" || return
    step step17c-carry "${P17[@]}" "$PY" scripts/v0_2_gate.py --rc "$C" --carry-w27 "$S/at-cw.json" "$S/at-c.json" || return
    step step17d-precheck "${P17[@]}" "$PY" -c 'import benchmarks.t07.v17.harness as h; h.operator_address()' || return
    step step17d-copy cp -a "$CAMPAIGN" "$S/w27-m07-83f825d" || return
    step step17d-aggregate "${P17[@]}" "$PY" -m benchmarks.m06.w27.harness --runs-root "$S" aggregate --campaign w27-m07-83f825d || return
    step step17d-diff diff -r "$S/w27-m07-83f825d" "$CAMPAIGN" || return
    step step17d-sha256 sha256sum "$S/w27-m07-83f825d/campaign.json"
}
s17

# -- the t08-rc-v1 records of steps 11-17 ------------------------------------------------------
for s in step11 step12 step13 step14 step15 step16 step17; do
    step "record-$s" env -u PYTHONPATH "$PY" "$W/tools/m07_rc_external.py" "$s" --rc "$RC" --commit "$C" \
        --summary "$SUM" --logs "$LOGS" --s17 "$S"
done
git status --porcelain > "$LOGS/tree-at-end.txt"
echo "EXIT run_local done" >> "$SUM"
