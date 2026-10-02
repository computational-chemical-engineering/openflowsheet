#!/usr/bin/env bash
# Full local check: lint, format, type, test. Exits nonzero if any step fails.
# Run from the repository root, inside the project environment (see Makefile target `venv`).
set -uo pipefail

cd "$(dirname "$0")/.."

status=0

run_step() {
    local name="$1"
    shift
    echo "=== ${name}: $* ==="
    if "$@"; then
        echo "--- ${name}: exit 0"
    else
        local rc=$?
        echo "--- ${name}: exit ${rc}"
        status=1
    fi
}

run_step "ruff check" ruff check .
run_step "ruff format" ruff format --check .
# No path argument: mypy uses the `files` list in pyproject.toml, which covers `src` and, since
# P01, `benchmarks` (the SYN-001 oracle is an acceptance reference and is type-checked strictly).
run_step "mypy" mypy
run_step "pytest" pytest -q

if [ "${status}" -ne 0 ]; then
    echo "=== check.sh: FAILED ==="
else
    echo "=== check.sh: PASSED ==="
fi
exit "${status}"
