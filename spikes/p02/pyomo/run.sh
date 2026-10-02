#!/usr/bin/env bash
# P02 Pyomo/PyNumero (ASL) harness — run from the repository root.
#
#     ./spikes/p02/pyomo/run.sh
#
# Writes the result set of specification §10.1 to spikes/p02/results/pyomo/. The venv
# .venv-pyomo must contain pyomo 6.10.1 with a built libpynumero_ASL (see §10.3); the harness
# refuses to produce numbers and writes only environment.json if it is missing.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$repo_root"

exec .venv-pyomo/bin/python spikes/p02/pyomo/harness.py "$@"
