"""Generate `evidence/S01/<commit>/manifest.json` by running, not by transcribing. S01.

Spec `docs/derivations/S01-spec.md` §13 is the check list. Everything recorded is produced here,
at the checked-out commit (the script refuses to run when `HEAD` is not `--commit` or when a
tracked source, test, script, schema or derivation file differs from it):

1. **The S01 tests** (`tests/test_s01_*.py`, `pytest --junitxml`). Each test cites the §10
   assertions its function name carries (`test_a04_a06_…` cites A04 and A06). The check
   `S01.Axx` passes only if at least one node cites it and every node citing it passed: a
   failure, an error, a skip or an expected failure (a strict xfail holding a measured miss) leaves
   it `fail`, with the node and its message in `value`.
2. **The reference generator's `--check`** (§13: it passes at the manifest commit).
3. **`ruff check`, `ruff format --check`** on S01's files and **`mypy`** (the project's own
   configuration, no arguments).
4. **The A04/A06 measured deviation** (§10 "needs a fact", §13), measured here with the WO-2
   fixtures: the worst column error of every pre-solve and target root against `ref`, in units of
   §10's state tolerance, with the commit it was measured at. It passes when every value is at most
   1/10 (the margin §10 requires).

`scripts/gate.sh` is not run here (it runs once before merge, in the integration worktree): its
check is `unsupported`. `status` is computed, never written: `tested` iff every `S01.A01`–`A20`
check and the generator, ruff, format and mypy checks pass; otherwise `implemented`. `reviewed`
is never set and both review fields stay `pending`. The limitations are §14's items verbatim, then
what this run found.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s01_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "derivations" / "S01-spec.md"
REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "s01_reference.json"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s01_reference.py"
SCHEMA = ROOT / "schemas" / "evidence-manifest.schema.json"
LOCK = ROOT / "requirements.lock"
SOURCES = (
    "src/openflowsheet/models/syn001/cascade.py",
    "src/openflowsheet/models/syn001/cascade_solve.py",
)
#: The tracked paths that must equal `--commit` for the run to measure it.
CLEAN_PATHS = ("src", "tests", "scripts", "schemas", "docs/derivations", "requirements.lock")
#: Spec §10's assertion ids.
ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 21))
#: The non-assertion checks `status` also requires.
TOOL_CHECKS = ("S01.generator", "S01.ruff", "S01.format", "S01.mypy")
#: A §10 id in a test function's name: `_aNN` followed by `_` or the end of the name.
CITED = re.compile(r"(?:^|_)a(\d{2})(?=_|$)")
#: The evidence test's placeholder pattern (`tests/test_evidence_manifests.py`).
ANGLE = re.compile(r"<[^<>]*>")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: str) -> str:
    """A string fit for the manifest: `<=`/`>=` as `≤`/`≥`, and any other angle-bracketed span
    (a spec template such as a unit-id slot) in guillemets, so that it is never read as a
    placeholder value."""
    value = value.replace("<=", "≤").replace(">=", "≥")
    return ANGLE.sub(lambda match: "‹" + match.group(0)[1:-1] + "›", value)


def check(
    identifier: str,
    description: str,
    result: str,
    value: Any,
    expected: Any = None,
    tolerance: Any = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": identifier,
        "description": text(description),
        "result": result,
        "value": value,
    }
    if expected is not None:
        entry["expected"] = expected
    if tolerance is not None:
        entry["tolerance"] = tolerance
    return entry


# -- the specification ---------------------------------------------------------------------------


def section(document: str, number: int) -> str:
    """The body of `## <number>.` up to the next `## ` heading."""
    match = re.search(rf"^## {number}\. .*?$(.*?)(?=^## )", document, re.M | re.S)
    if match is None:
        raise SystemExit(f"{SPEC.name} has no section {number}")
    return match.group(1)


def section_14(document: str) -> list[str]:
    """§14's items verbatim: each `- ` bullet with its continuation lines joined by one space."""
    items: list[str] = []
    for line in section(document, 14).splitlines():
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith("  ") and items and line.strip():
            items[-1] += " " + line.strip()
    if not items:
        raise SystemExit("§14 lists no item")
    return items


def section_10(document: str) -> dict[str, tuple[str, str, str]]:
    """§10's table: id → (assertion, expected, tolerance). Every id A01–A20 must be there."""
    rows: dict[str, tuple[str, str, str]] = {}
    for line in section(document, 10).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        if len(cells) == 4 and re.fullmatch(r"A\d{2}", cells[0]):
            rows[cells[0]] = (cells[1], cells[2], cells[3])
    if tuple(sorted(rows)) != ASSERTIONS:
        raise SystemExit(f"§10's ids are {sorted(rows)}, not A01–A20")
    return rows


# -- the commands --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Run:
    cmd: str
    exit_code: int
    stdout: str


def shown(path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run(argv: Sequence[str], *, pythonpath: bool = False) -> Run:
    environment = dict(os.environ)
    prefix = ""
    if pythonpath:
        environment["PYTHONPATH"] = str(ROOT / "src")
        prefix = "PYTHONPATH=src "
    completed = subprocess.run(
        list(argv),
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    cmd = prefix + " ".join(shown(part) if os.path.isabs(part) else part for part in argv)
    return Run(cmd, completed.returncode, completed.stdout + completed.stderr)


def command(entry: Run) -> dict[str, Any]:
    return {
        "cmd": entry.cmd,
        "cwd": ".",
        "exit_code": entry.exit_code,
        "stdout_sha256": hashlib.sha256(entry.stdout.encode()).hexdigest(),
    }


# -- the tests -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    node: str
    outcome: str  # passed, failed, error, skipped, xfailed
    message: str


def nodes(junit: Path) -> list[Node]:
    found: list[Node] = []
    for case in ElementTree.parse(junit).getroot().iter("testcase"):
        module = case.get("classname", "").replace(".", "/")
        node = f"{module}.py::{case.get('name', '')}"
        outcome, message = "passed", ""
        for child in case:
            if child.tag in ("failure", "error"):
                outcome, message = (
                    ("failed" if child.tag == "failure" else "error"),
                    (child.get("message") or ""),
                )
            elif child.tag == "skipped":
                expected = child.get("type") == "pytest.xfail"
                outcome = "xfailed" if expected else "skipped"
                message = child.get("message") or ""
        found.append(Node(node, outcome, message))
    return found


def cited(node: str) -> tuple[str, ...]:
    """The §10 ids a test node cites, from its function name (parameters ignored)."""
    name = node.rsplit("::", 1)[-1].split("[", 1)[0]
    return tuple(f"A{number}" for number in CITED.findall(name))


def assertion_checks(
    table: Mapping[str, tuple[str, str, str]], tests: Sequence[Node]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        citing = [item for item in tests if identifier in cited(item.node)]
        outcomes = Counter(item.outcome for item in citing)
        not_passed = [
            {"node": item.node, "outcome": item.outcome, "message": text(item.message[:600])}
            for item in citing
            if item.outcome != "passed"
        ]
        assertion, expected, tolerance = table[identifier]
        entries.append(
            check(
                f"S01.{identifier}",
                assertion,
                "pass" if citing and not not_passed else "fail",
                {
                    "judged_by": "tests",
                    "nodes": len(citing),
                    "outcomes": dict(sorted(outcomes.items())),
                    "selectors": [item.node for item in citing],
                    "not_passed": not_passed,
                },
                text(expected),
                text(tolerance),
            )
        )
    return entries


# -- the A04/A06 deviation record ----------------------------------------------------------------


def deviation_check(commit: str) -> dict[str, Any]:
    """§10/§13: the measured worst deviation of each pre-solve and target root against `ref`, in
    units of the state tolerance, with the WO-2 fixtures (the tests' own measure)."""
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "tests"))
    from test_s01_cascade_wo1 import REFERENCE as RECORDS
    from test_s01_cascade_wo2 import CASES, deviation, solved

    measured: dict[str, dict[str, dict[str, float]]] = {}
    for case in CASES:
        answer = solved(case)
        measured[case] = {
            "presolve": deviation(answer.presolve.state, RECORDS["cases"][case]["presolve"]),
            "target": deviation(answer.state, RECORDS["cases"][case]["target"]),
        }
    worst = max(max(part.values()) for record in measured.values() for part in record.values())
    short = sorted(
        f"{case}.{which}"
        for case, record in measured.items()
        for which, part in record.items()
        if max(part.values()) > 0.1
    )
    return check(
        "S01.A04-A06-deviation",
        "§10/§13: the measured maximum deviation of every pre-solve and target root from ref, "
        "per column class, in units of §10's state tolerance (1 is the tolerance); §10 requires "
        "the tolerance to be at least 10x the measurement",
        "pass" if worst <= 0.1 else "fail",
        {"measured_at": commit, "worst": worst, "below_10x_margin": short, "cases": measured},
        "every value ≤ 0.1",
    )


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every A01–A20 check and every tool check passes; never `reviewed`."""
    required = {f"S01.{identifier}" for identifier in ASSERTIONS} | set(TOOL_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        "requirements is empty: no docs/requirements.yaml entry lists S01 among its packages; "
        "the D/A mapping of S01 is the design lane's to register.",
        "scripts/gate.sh was not run by this generator (it runs once before merge into main, in "
        "the integration worktree); S01.gate is unsupported here.",
        "Review is pending: numerical and process-model review are the design lane's and the "
        "human reviewer's; this manifest does not claim either.",
        "The reference agreement is numerical verification against an independent 50-digit "
        "generator, not empirical validation.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] == "S01.gate":
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
                "docs/S01_DECISIONS.md)"
            )
        )
    return items


def refuse_unless_measuring(commit: str) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != commit:
        raise SystemExit(f"HEAD is {head}, not {commit}: check the commit out to measure it")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", *CLEAN_PATHS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if dirty:
        raise SystemExit(f"tracked files differ from {commit}:\n{dirty}")


def build(commit: str) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    document = SPEC.read_text(encoding="utf-8")
    table = section_10(document)
    artifacts = ROOT / "evidence" / "S01" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s01-tests.junit.xml"
    junit_shown = shown(junit)
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(shown(path) for path in (ROOT / "tests").glob("test_s01_*.py"))
    lint = [*SOURCES, *tests, "scripts/s01_evidence_manifest.py", shown(GENERATOR)]

    runs = {
        "tests": run(
            [
                python,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={junit_shown}",
                *tests,
            ],
            pythonpath=True,
        ),
        "S01.generator": run([python, str(GENERATOR), "--check"]),
        "S01.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S01.format": run([str(tools / "ruff"), "format", "--check", *lint]),
        "S01.mypy": run([str(tools / "mypy")], pythonpath=True),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")

    entries = assertion_checks(table, nodes(junit))
    tool_text = {
        "S01.generator": "§13: s01_reference.py --check re-derives every claim and byte-compares "
        "s01_reference.json",
        "S01.ruff": "§13: ruff check is clean on S01's files",
        "S01.format": "§13: ruff format --check is clean on S01's files",
        "S01.mypy": "mypy (the project's configuration) is clean",
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
    entries.append(
        check(
            "S01.gate",
            "§13: scripts/gate.sh passes before merge",
            "unsupported",
            "not run by this generator; the full gate runs once before merge (CLAUDE.md)",
        )
    )

    manifest: dict[str, Any] = {
        "work_package": "S01",
        "commit": commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "S01 acceptance: docs/derivations/S01-spec.md §10 A01–A20 against "
            "docs/derivations/scripts/s01_reference.json, check list §13",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S01 test run (ignored; kept by hash)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "the design lane's 50-digit reference values (ref)",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S01 specification the checks are read from (§10, §13, §14)",
            },
        ],
        "limitations": [*section_14(document), *found_limitations(entries)],
        "review": {"numerical": "pending", "process_model": "pending"},
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(manifest)]
    if errors:
        raise SystemExit(f"the manifest does not validate: {errors}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--commit", help="the measured commit (default: HEAD)")
    parser.add_argument("--out", type=Path, help="default: evidence/S01/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S01" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
