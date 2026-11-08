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
# RP §6.10 (ADR 0055 D4.4): with OPENFLOWSHEET_JUNIT_DIR set (CI's `check`), pytest and node also
# write junit there (`pytest.xml`, `node.xml`), uploaded as `junit-<arch>`. Unset, nothing changes.
junit_pytest=()
if [ -n "${OPENFLOWSHEET_JUNIT_DIR:-}" ]; then
    mkdir -p "${OPENFLOWSHEET_JUNIT_DIR}"
    junit_pytest=(--junitxml="${OPENFLOWSHEET_JUNIT_DIR}/pytest.xml")
fi
run_step "pytest" pytest -q -rs "${junit_pytest[@]}"

# M06 (design note §8 Layer B, ADR 0030 D6): the web shell's Node tests, on Node's built-in
# runner (a test-time tool; no package.json, no npm). The quoted glob is expanded by Node >= 22.
web_tests() {
    if [ "${OPENFLOWSHEET_SKIP_WEB_TESTS:-}" = "1" ]; then
        echo "SKIPPED (explicit): OPENFLOWSHEET_SKIP_WEB_TESTS=1"
        return 0
    fi
    local major
    major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
    if [ -z "${major}" ] || [ "${major}" -lt 22 ]; then
        echo "node ${major:-not found}: install Node >= 22 (a test-time tool only) or set OPENFLOWSHEET_SKIP_WEB_TESTS=1"
        return 1
    fi
    if [ -n "${OPENFLOWSHEET_JUNIT_DIR:-}" ]; then
        node --test --test-reporter=spec --test-reporter-destination=stdout \
            --test-reporter=junit --test-reporter-destination="${OPENFLOWSHEET_JUNIT_DIR}/node.xml" \
            "tests/web/*.test.mjs"
    else
        node --test "tests/web/*.test.mjs"
    fi
}
run_step "node --test" web_tests

if [ "${status}" -ne 0 ]; then
    echo "=== check.sh: FAILED ==="
else
    echo "=== check.sh: PASSED ==="
fi
exit "${status}"
