#!/usr/bin/env bash
# Build the audited environment of the optional `lca` extra (E01 WO-B1; design §4.8.4, §7 Q11;
# ADR 0052 D7), outside requirements.lock and outside the project .venv.
#
# The environment is a plain venv of the project's own interpreter with
#   - requirements.lock, --no-deps (the default closure at its pins; the lock carries no hashes,
#     as in CI), and
#   - benchmarks/e01/brightway/lca-pip.lock, --no-deps --require-hashes --only-binary (bw2data 4.7,
#     bw2calc 2.5.0 and their increment over requirements.lock; no bw2io, no pypardiso, no MKL),
# then a `.pth` line naming the checkout's src/, so `openflowsheet` imports from the checkout (no
# build backend is installed here, so no editable install).
# Brightway never runs inside a solve, an optimization or a replay: this environment exists for the
# offline table builder (`assessment/lca/brightway.py`), A24 and A25, and the licence inventory
# (`scripts/e01_d04_inventory.py --packages`).
#
# Brightway writes its projects under platformdirs' user data directory unless BRIGHTWAY2_DIR is
# set; the tests and the adapter's checks set it to a scratch directory, never the user's own.
#
# Usage: scripts/build-lca-env.sh [prefix] [python]
#        defaults: .venv-lca (git-ignored) and .venv/bin/python
set -euo pipefail
cd "$(dirname "$0")/.."
PREFIX="$(realpath -m "${1:-.venv-lca}")"
PYTHON="${2:-.venv/bin/python}"
LOG="$PREFIX.build.log"
: >"$LOG"
rm -rf "$PREFIX"
"$PYTHON" -m venv "$PREFIX" >>"$LOG" 2>&1
PIP=("$PREFIX/bin/python" -I -m pip install --no-deps --no-cache-dir --only-binary=:all:)
"${PIP[@]}" -r requirements.lock >>"$LOG" 2>&1
"${PIP[@]}" --require-hashes -r benchmarks/e01/brightway/lca-pip.lock >>"$LOG" 2>&1
SITE="$("$PREFIX/bin/python" -I -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
echo "$PWD/src" >"$SITE/openflowsheet-checkout.pth"
"$PREFIX/bin/python" -I -m pip check >>"$LOG" 2>&1
"$PREFIX/bin/python" -I -c "import bw2calc, bw2data, openflowsheet; print('lca env:', bw2data.__version__, bw2calc.__version__)" \
    | tee -a "$LOG"
