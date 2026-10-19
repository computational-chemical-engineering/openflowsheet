#!/usr/bin/env bash
# W21 (e): step 12's G11 at C' again, through g11keep.py (M07 WO-8d). As run_local.sh's step12-g11, with the keep dir.
cd /home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-ce99365
git status --porcelain > /home/frankp/.cache/of-rc-ce99365/logs/g11keep-tree-at-start.txt
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENFLOWSHEET_EXTERNAL_ROOT=/home/frankp/.cache/of-rc-ce99365/external
t0=$SECONDS
env -u PYTHONPATH /home/frankp/.cache/of-rc-ce99365/rcvenv/bin/python /home/frankp/.cache/of-rc-ce99365/tools/g11keep.py /home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-ce99365/evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/artifacts/rc/step12/experiments-keep --variant-file benchmarks/m02/variant-v3-provisional.json --compare benchmarks/m02/g11-coverage.json --d78 docs/derivations/scripts/m07_g11_d78_extract.json --previous /home/frankp/.cache/of-rc-ce99365/inputs/g11-coverage-v3-bd446ab.json --out /home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rc-ce99365/evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/artifacts/rc/step12/experiments/g11-coverage-v3.json > /home/frankp/.cache/of-rc-ce99365/logs/step12-g11-keep.log 2>&1
code=$?
git status --porcelain > /home/frankp/.cache/of-rc-ce99365/logs/g11keep-tree-at-end.txt
echo "EXIT step12-g11-keep exit $code $((SECONDS - t0))s"
