#!/usr/bin/env bash
# Build the two P02 backend candidate environments, outside requirements.lock.
#
# Neither backend is a dependency of this project: each spike gets its own environment so the
# repository environment stays exactly as pinned. `.venv-*/` is git-ignored. What this produces,
# including the PyNumero ASL library that a plain `pip install Pyomo` does not give you, is
# recorded in docs/backend-environments.md.
#
# Usage: scripts/build-backend-envs.sh [log-file]
set -uo pipefail

cd "$(dirname "$0")/.."
LOG="${1:-backend-env-build.log}"
: > "$LOG"

note() { echo "=== $* ===" | tee -a "$LOG"; }

note "host"
{ python3 --version; cmake --version | head -1; gcc --version | head -1; } >>"$LOG" 2>&1

note "candidate A: .venv-casadi"
python3 -m venv .venv-casadi >>"$LOG" 2>&1
.venv-casadi/bin/pip -q install --upgrade pip >>"$LOG" 2>&1
.venv-casadi/bin/pip install \
    "numpy==2.2.4" "scipy==1.15.3" "casadi==3.8.0" "pytest==8.3.5" "pyyaml==6.0.2" >>"$LOG" 2>&1
.venv-casadi/bin/python -c "import casadi; print('casadi', casadi.__version__)" | tee -a "$LOG"

note "candidate B: .venv-pyomo"
python3 -m venv .venv-pyomo >>"$LOG" 2>&1
.venv-pyomo/bin/pip -q install --upgrade pip >>"$LOG" 2>&1
.venv-pyomo/bin/pip install \
    "numpy==2.2.4" "scipy==1.15.3" "Pyomo==6.10.1" "pytest==8.3.5" "pyyaml==6.0.2" >>"$LOG" 2>&1
# build-extensions needs setuptools inside the environment; without it every target fails with
# ModuleNotFoundError and the ASL interface stays unavailable.
.venv-pyomo/bin/pip -q install "setuptools==80.9.0" "wheel==0.48.0" >>"$LOG" 2>&1

note "PyNumero ASL before build-extensions"
.venv-pyomo/bin/python -c \
    "from pyomo.contrib.pynumero.asl import AmplInterface; print('available:', AmplInterface.available())" \
    | tee -a "$LOG"

note "pyomo build-extensions (needs cmake and a C/C++ compiler)"
# Exits nonzero even on success here: APPSI fails for want of pybind11, and the grey-box route
# this project uses does not need APPSI. That is recorded, not worked around.
.venv-pyomo/bin/pyomo build-extensions >>"$LOG" 2>&1
echo "build-extensions exit=$?" | tee -a "$LOG"

note "PyNumero ASL after build-extensions"
.venv-pyomo/bin/python -c \
    "from pyomo.contrib.pynumero.asl import AmplInterface; print('available:', AmplInterface.available())" \
    | tee -a "$LOG"

if [ -f "$HOME/.pyomo/lib/libpynumero_ASL.so" ]; then
    note "libpynumero_ASL.so"
    sha256sum "$HOME/.pyomo/lib/libpynumero_ASL.so" | tee -a "$LOG"
fi

note "done; full log in $LOG"
