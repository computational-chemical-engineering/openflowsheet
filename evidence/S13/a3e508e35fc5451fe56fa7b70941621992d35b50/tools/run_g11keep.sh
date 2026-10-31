#!/usr/bin/env bash
# V03 WO-7b (W21 (e), verdict finding F1): step 12's G11 at C again, through 0.2.0's g11keep.py (M07 WO-8d, R-375),
# which keeps each point's store. As run_local.sh's step12-g11 (same arguments, same environment), with the keep dir;
# TMPDIR private under ~/.cache/v03rc-tmp (inert: G11's stores go to the keep dir).
RC=/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-v03-a3e508e
W=/home/frankp/.cache/of-rc-v03-a3e508e
C=$(git -C "$RC" rev-parse HEAD)
A=$RC/evidence/S13/$C/artifacts/rc/step12
cd "$RC"
git status --porcelain > "$W/logs/g11keep-tree-at-start.txt"
rm -rf "$A/experiments-keep" "$A/experiments"; mkdir -p "$A/experiments"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENFLOWSHEET_EXTERNAL_ROOT=$W/external
export TMPDIR=/home/frankp/.cache/v03rc-tmp/wo7b/tmp
t0=$SECONDS
env -u PYTHONPATH "$W/rcvenv/bin/python" "$W/tools/g11keep.py" "$A/experiments-keep" \
    --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g11-coverage.json \
    --d78 docs/derivations/scripts/m07_g11_d78_extract.json --previous "$W/inputs/g11-coverage-v3-bd446ab.json" \
    --out "$A/experiments/g11-coverage-v3.json" > "$W/logs/step12-g11-keep.log" 2>&1
code=$?
git status --porcelain > "$W/logs/g11keep-tree-at-end.txt"
echo "EXIT step12-g11-keep exit $code $((SECONDS - t0))s"
