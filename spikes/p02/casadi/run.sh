#!/usr/bin/env bash
# P02 CasADi harness (specification §10.1). Run from the repository root.
set -euo pipefail

cd "$(dirname "$0")/../../.."

if [ ! -x .venv-casadi/bin/python ]; then
    echo "missing .venv-casadi; see docs/backend-environments.md" >&2
    exit 2
fi

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONPATH=.

exec .venv-casadi/bin/python spikes/p02/casadi/harness.py "$@"
