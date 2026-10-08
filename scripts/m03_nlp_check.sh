#!/usr/bin/env bash
# M03 WO-8 (ADR 0032 C2): run the `nlp`-marked tests in the audited NLP environment of
# docs/m03-ipopt-audit.md, which scripts/build-m03-ipopt-env.sh builds. The default gate
# (scripts/check.sh) deselects these tests; this script is the only place they run.
#
# The environment is used as audit §9 requires and WO-8 measured:
#   PYTHONNOUSERSITE=1                 conda-forge's CPython enables the user site otherwise
#   PYOMO_CONFIG_DIR=<env>/share/pyomo Pyomo finds an unaudited ~/.pyomo/lib build otherwise
#   OMP_NUM_THREADS=1                  MUMPS/OpenBLAS under LLVM OpenMP are bitwise reproducible
#                                      run to run only single-threaded
# pytest and its two dependencies are not part of the audited environment. They are pure Python,
# installed by hash from benchmarks/m03/nlp-test.lock into a separate directory under the cache
# and put on PYTHONPATH here only, so that the audited environment stays exactly its locks.
#
# The audited environment's inventory is re-taken with NLP-1 as the workload
# (scripts/m03_ipopt_inventory.py --check, audit §9 item 1) unless --no-inventory is given.
#
# Usage: scripts/m03_nlp_check.sh [--no-inventory] [prefix] [cache] [-- pytest arguments]
#        defaults: .venv-nlp and .reference-downloads/m03-ipopt (the build script's)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
INVENTORY=1
if [ "${1:-}" = "--no-inventory" ]; then
    INVENTORY=0
    shift
fi
PREFIX="$(realpath -m "${1:-.venv-nlp}")"
CACHE="$(realpath -m "${2:-.reference-downloads/m03-ipopt}")"
shift $(($# > 2 ? 2 : $#))
[ "${1:-}" = "--" ] && shift

if [ ! -x "$PREFIX/bin/python" ]; then
    echo "no audited NLP environment at $PREFIX; build it with scripts/build-m03-ipopt-env.sh"
    exit 2
fi

TOOLS="$CACHE/nlp-test-tools"
LOCK="$ROOT/benchmarks/m03/nlp-test.lock"
STAMP="$TOOLS/.lock-sha256"
if [ "$(cat "$STAMP" 2>/dev/null)" != "$(sha256sum "$LOCK" | cut -d' ' -f1)" ]; then
    rm -rf "$TOOLS"
    PYTHONNOUSERSITE=1 "$PREFIX/bin/python" -I -m pip install --quiet --no-deps --no-cache-dir \
        --require-hashes --only-binary=:all: --target "$TOOLS" -r "$LOCK"
    sha256sum "$LOCK" | cut -d' ' -f1 >"$STAMP"
fi

export PYTHONNOUSERSITE=1
export PYOMO_CONFIG_DIR="$PREFIX/share/pyomo"
export OMP_NUM_THREADS=1
export PYTHONPATH="$ROOT/src:$TOOLS"

status=0
echo "=== pytest -m nlp ($PREFIX) ==="
if "$PREFIX/bin/python" -m pytest -q -p no:cacheprovider -m nlp "$@"; then
    echo "--- pytest -m nlp: exit 0"
else
    echo "--- pytest -m nlp: exit $?"
    status=1
fi
if [ "$INVENTORY" -eq 1 ]; then
    echo "=== inventory --check (NLP-1 workload) ==="
    if "$PREFIX/bin/python" -I scripts/m03_ipopt_inventory.py --env "$PREFIX" --check; then
        echo "--- inventory --check: exit 0"
    else
        echo "--- inventory --check: exit $?"
        status=1
    fi
fi
if [ "$status" -ne 0 ]; then
    echo "=== m03_nlp_check.sh: FAILED ==="
else
    echo "=== m03_nlp_check.sh: PASSED ==="
fi
exit "$status"
