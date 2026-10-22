"""Generate `evidence/S06/<commit>/manifest.json` by running, not by transcribing. S06.

Spec `docs/derivations/S06-spec.md` §13 is the check list. Everything recorded is produced here,
at the checked-out commit (the script refuses to run when `HEAD` is not `--commit` or when a
tracked source, test, script, schema or derivation file differs from it; S01's rule):

1. **The S06, S02 and S01 tests** (`tests/test_s06_*.py`, `tests/test_s02_*.py`,
   `tests/test_s01_*.py`, one `pytest --junitxml` run). An S06 test cites the assertions its
   function name carries (`test_a05_…` cites A05). The registered assertions are §10's A01–A16.
   `S06.Axx` passes only if at least one S06 node cites it and every node citing it passed: a
   failure, an error, a skip or an expected failure (a strict xfail holding a measured miss)
   leaves it `fail`. **A16** ("S02's A01–A22 and S01's suite still pass") is judged by the S02
   and S01 nodes: every one passed, each of S02's registered assertions is cited by an S02 node
   and each of S01's A01–A20 by an S01 node.
2. **The reference generators' `--check`** (§13: `s06_reference.py`, 3110 claims, JSON
   byte-identical; `s02_reference.py` still passes).
3. **`ruff check`, `ruff format --check`** on S06's files and **`mypy`** (the project's own
   configuration, no arguments).
4. **The measured deviation** (§10 "needs a fact"): the worst column error of J1–J8 and the
   matched sets on `solve_column`'s path, in units of §10's state tolerance; it passes when every
   value is at most 1/10 (above it, §10 is to be amended).
5. **A09's floor** at `x⁰` and the root of J1, J2 and J6, over every row and over the new rows
   and `u`; it passes at ≤ 1e-8.
6. **A11's branch** on U1 and U2, with the commit; its result is `S06.A11`'s.

`scripts/gate.sh` is not run here (it runs once before merge): its check is `unsupported`.
`status` is computed, never written: `tested` iff every registered assertion check, both
generators, ruff, format and mypy checks, the deviation and A09's floor pass; otherwise
`implemented`. Both review fields stay `pending`. The limitations are §14's items verbatim, then
what this run found.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s06_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s01_evidence_manifest import ASSERTIONS as S01_ASSERTIONS  # noqa: E402
from s01_evidence_manifest import (  # noqa: E402  (S01's generic helpers, unchanged)
    LOCK,
    ROOT,
    SCHEMA,
    Node,
    check,
    command,
    nodes,
    refuse_unless_measuring,
    run,
    sha256_file,
    shown,
    text,
)
from s01_evidence_manifest import cited as s01_cited  # noqa: E402
from s02_evidence_manifest import ASSERTIONS as S02_ASSERTIONS  # noqa: E402
from s02_evidence_manifest import (  # noqa: E402  (S02's reading of a spec, unchanged)
    _verdict,
    bullets,
    cited,
    section,
    table,
)

SPEC = ROOT / "docs" / "derivations" / "S06-spec.md"
REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "s06_reference.json"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s06_reference.py"
S02_GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s02_reference.py"
DECISIONS = ROOT / "docs" / "C11_DECISIONS.md"
#: The source files S06 changed (from `main`).
SOURCES = (
    "src/openflowsheet/models/rows.py",
    "src/openflowsheet/models/syn001/cascade.py",
    "src/openflowsheet/models/syn001/column.py",
    "src/openflowsheet/models/syn001/column_solve.py",
)
#: §10's registered assertion ids.
ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 17))
#: The non-assertion checks `status` also requires.
REQUIRED_CHECKS = (
    "S06.generator",
    "S06.s02-generator",
    "S06.ruff",
    "S06.format",
    "S06.mypy",
    "S06.deviation",
    "S06.A09-floor",
)
#: §10: the deviation margin; A09: the floor.
MARGIN, FD_FLOOR = 0.1, 1e-8


# -- the specification ---------------------------------------------------------------------------


def assertion_table(document: str) -> dict[str, tuple[str, str, str]]:
    """§10's table: id → (assertion, expected, tolerance), exactly A01–A16."""
    rows = table(section(document, 10))
    if tuple(sorted(rows)) != ASSERTIONS:
        raise SystemExit(f"§10's ids are {sorted(rows)}, not {ASSERTIONS}")
    return {identifier: rows[identifier] for identifier in ASSERTIONS}


def limitations_of_the_spec(document: str) -> list[str]:
    """§14's items verbatim (§13: "§14 listed verbatim as limitations")."""
    items = bullets(section(document, 14))
    if not items:
        raise SystemExit("§14 lists no item")
    return items


# -- the tests -----------------------------------------------------------------------------------


def lower_suites(tests: Sequence[Node]) -> tuple[str, dict[str, Any]]:
    """A16: every S02 and S01 node passed, each of S02's registered assertions is cited by an
    S02 node and each of S01's A01–A20 by an S01 node."""
    s01 = [item for item in tests if item.node.startswith("tests/test_s01_")]
    s02 = [item for item in tests if item.node.startswith("tests/test_s02_")]
    result, value = _verdict([*s02, *s01])
    s02_uncited = [
        identifier
        for identifier in S02_ASSERTIONS
        if not any(identifier in cited(item.node) for item in s02)
    ]
    s01_uncited = [
        identifier
        for identifier in S01_ASSERTIONS
        if not any(identifier in s01_cited(item.node) for item in s01)
    ]
    value = {
        **value,
        "judged_by": "the S02 and S01 suites",
        "s02_nodes": len(s02),
        "s01_nodes": len(s01),
        "s02_assertions_uncited": s02_uncited,
        "s01_assertions_uncited": s01_uncited,
    }
    del value["selectors"]
    passed = result == "pass" and not s02_uncited and not s01_uncited and bool(s01 and s02)
    return ("pass" if passed else "fail"), value


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]], tests: Sequence[Node]
) -> list[dict[str, Any]]:
    s06 = [item for item in tests if item.node.startswith("tests/test_s06_")]
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        if identifier == "A16":
            result, value = lower_suites(tests)
        else:
            result, value = _verdict([item for item in s06 if identifier in cited(item.node)])
        assertion, expected, tolerance = rows[identifier]
        entries.append(
            check(f"S06.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


# -- the measurements ----------------------------------------------------------------------------


def _import_tests() -> None:
    for path in (ROOT / "src", ROOT / "tests"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def deviation_check(commit: str) -> dict[str, Any]:
    """§10 "needs a fact": the worst deviation of each registered root on `solve_column`'s path,
    in units of the state tolerance, with the tests' own fixtures and measure."""
    _import_tests()
    from test_s06_column_wo2 import FLOWING, deviation

    measured = {name: deviation(name) for name in FLOWING}
    worst = max(measured.values())
    over = sorted(name for name, value in measured.items() if value > MARGIN)
    return check(
        "S06.deviation",
        "§10 'needs a fact': the measured maximum deviation of J1–J8 (from ref.cases.*.target) "
        "and the matched sets (from s02ref.cases.M1.target) on solve_column's path, in units of "
        "§10's state tolerance (1 is the tolerance); above 1/10 §10 is to be amended",
        "pass" if worst <= MARGIN else "fail",
        {"measured_at": commit, "worst": worst, "above_one_tenth": over, "sets": measured},
        "every value ≤ 0.1",
    )


def floor_check(commit: str) -> dict[str, Any]:
    """§10 A09 / §13: the measured floor of the compiled Jacobian against central differences."""
    _import_tests()
    from test_s06_column_wo2 import fd_floor

    measured: dict[str, dict[str, float]] = {}
    for name in ("J1", "J2", "J6"):
        for point in ("x0", "root"):
            every, new = fd_floor(name, point)
            measured[f"{name} {point}"] = {"worst": every, "worst_new_rows_and_u": new}
    worst = max(max(entry.values()) for entry in measured.values())
    return check(
        "S06.A09-floor",
        "§10 A09 / §13: the measured floor of D_r⁻¹ J D_x against central differences at "
        "h = 1e-6·max(D_x, |x|) (R-516), at x⁰ and the root of J1, J2 and J6, over every row "
        "and over the new rows (inverse slots, purity definition) and u; it must be ≤ 1e-8",
        "pass" if worst <= FD_FLOOR else "fail",
        {"measured_at": commit, "worst": worst, "points": measured},
        "≤ 1e-8",
    )


def a11_record(commit: str, a11: Mapping[str, Any]) -> dict[str, Any]:
    """§13: A11's branch on U1 and U2, with the commit; judged by `S06.A11`."""
    _import_tests()
    from test_s06_column_wo2 import a11_branch

    return check(
        "S06.A11-branch",
        "§13 / A11: the branch solve_column took on U1 and U2 (CONVERGED at s02ref's M2 root, "
        "or a typed outcome with its unreached report); the result is S06.A11's",
        a11["result"],
        {"measured_at": commit, "U1": a11_branch("U1"), "U2": a11_branch("U2")},
        "either branch of A11",
    )


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every registered assertion and every required check passes."""
    required = {f"S06.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        "requirements is empty: the schema takes D/A requirement ids and none lists S06; S06 "
        "extends S02's part of X31's evidence with inverse column specifications against this "
        "package's generator. The mapping and the verdict are the design lane's.",
        "scripts/gate.sh was not run by this generator (it runs once before merge into main); "
        "S06.gate is unsupported here.",
        "Review: the design lane's reviewer pass and the human numerical and process-model "
        "review are pending; this manifest claims neither. Open questions: Q-S06-WO1-1, "
        "Q-S06-WO2-1 (docs/C11_DECISIONS.md); Frank's Q-S06-1, Q-S06-2.",
        "The reference agreement is numerical verification against a 50-digit generator that "
        "shares SYN-001, S02's endpoint and §5's rules, not empirical validation.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] == "S06.gate":
            continue
        value = entry.get("value")
        detail = (
            "; ".join(f"{item['node']} {item['outcome']}" for item in value["not_passed"])
            if isinstance(value, dict) and value.get("not_passed")
            else "see its value"
        )
        items.append(
            text(
                f"{entry['id']} is {entry['result']}: {detail} (open design-lane questions in "
                "docs/C11_DECISIONS.md)"
            )
        )
    return items


def build(commit: str) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    document = SPEC.read_text(encoding="utf-8")
    rows = assertion_table(document)
    artifacts = ROOT / "evidence" / "S06" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s06-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        shown(path)
        for pattern in ("test_s06_*.py", "test_s02_*.py", "test_s01_*.py")
        for path in (ROOT / "tests").glob(pattern)
    )
    s06_tests = [path for path in tests if Path(path).name.startswith("test_s06_")]
    lint = [*SOURCES, *s06_tests, "scripts/s06_evidence_manifest.py", shown(GENERATOR)]

    runs = {
        "tests": run(
            [
                python,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={shown(junit)}",
                *tests,
            ],
            pythonpath=True,
        ),
        "S06.generator": run([python, str(GENERATOR), "--check"]),
        "S06.s02-generator": run([python, str(S02_GENERATOR), "--check"]),
        "S06.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S06.format": run([str(tools / "ruff"), "format", "--check", *lint]),
        "S06.mypy": run([str(tools / "mypy")], pythonpath=True),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")

    entries = assertion_checks(rows, nodes(junit))
    tool_text = {
        "S06.generator": "§13: s06_reference.py --check re-derives every claim (3110) and "
        "byte-compares s06_reference.json",
        "S06.s02-generator": "§13: s02_reference.py --check still passes",
        "S06.ruff": "§13: ruff check is clean on S06's files",
        "S06.format": "§13: ruff format --check is clean on S06's files",
        "S06.mypy": "§13: mypy (the project's configuration) is clean",
    }
    for name, description in tool_text.items():
        entries.append(
            check(
                name,
                description,
                "pass" if runs[name].exit_code == 0 else "fail",
                {"cmd": runs[name].cmd, "exit_code": runs[name].exit_code},
                "exit code 0",
            )
        )
    entries.append(deviation_check(commit))
    entries.append(floor_check(commit))
    a11 = next(entry for entry in entries if entry["id"] == "S06.A11")
    entries.append(a11_record(commit, a11))
    entries.append(
        check(
            "S06.gate",
            "§13: scripts/gate.sh passes before merge",
            "unsupported",
            "not run by this generator; the full gate runs once before merge (CLAUDE.md)",
        )
    )

    manifest: dict[str, Any] = {
        "work_package": "S06",
        "commit": commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "S06 acceptance: docs/derivations/S06-spec.md §10 (A01–A16) against "
            "docs/derivations/scripts/s06_reference.json, check list §13",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S06, S02 and S01 test run (ignored; kept by "
                "hash)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "the design lane's 50-digit reference values (ref)",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S06 specification the checks are read from (§10, §13, §14)",
            },
            {
                "path": shown(DECISIONS),
                "sha256": sha256_file(DECISIONS),
                "description": "the build and design decisions of C11/S06, with the measured "
                "facts and open questions",
            },
        ],
        "limitations": [*limitations_of_the_spec(document), *found_limitations(entries)],
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(manifest)]
    if errors:
        raise SystemExit(f"the manifest does not validate: {errors}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--commit", help="the measured commit (default: HEAD)")
    parser.add_argument("--out", type=Path, help="default: evidence/S06/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S06" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
