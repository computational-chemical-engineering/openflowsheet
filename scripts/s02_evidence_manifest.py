"""Generate `evidence/S02/<commit>/manifest.json` by running, not by transcribing. S02.

Spec `docs/derivations/S02-spec.md` §13 is the check list. Everything recorded is produced here,
at the checked-out commit (the script refuses to run when `HEAD` is not `--commit` or when a
tracked source, test, script, schema or derivation file differs from it; S01's rule):

1. **The S02 and S01 tests** (`tests/test_s02_*.py`, `tests/test_s01_*.py`, one `pytest
   --junitxml` run). An S02 test cites the assertions its function name carries
   (`test_a06b_…` cites A06b). The registered assertions are §10's A01–A16, §17's A17–A19 and
   §18.6's (A05, A06, A07, A13, A14 restated; A06b, A13b, A20–A22 added); §18.6's wording replaces
   §10's. `S02.Axx` passes only if at least one S02 node cites it and every node citing it
   passed: a failure, an error, a skip or an expected failure (a strict xfail holding a measured
   miss) leaves it `fail`. **A16** ("S01's 20 assertions still pass") is judged by the S01 nodes:
   every S01 node passed and each of S01's A01–A20 is cited by one.
2. **The reference generator's `--check`** (§13: 1074 claims, JSON byte-identical).
3. **`ruff check`, `ruff format --check`** on S02's files and **`mypy`** (the project's own
   configuration, no arguments).
4. **The measured deviation** (§10 "needs a fact", §18.5): the worst column error of every
   registered root on `solve_column`'s path (A06, A07, `R2`) and from the profile endpoint
   (A06b), in units of §10's state tolerance; it passes when every value is at most 1/10.
5. **A10's floor** at `x_K` and the root of M1 and M2 (R-516's step); it passes at ≤ 1e-8.
6. **P1's outcome and attempt list** (§13, A12), with the commit; its result is `S02.A12`'s.

`scripts/gate.sh` is not run here (it runs once before merge): its check is `unsupported`.
`status` is computed, never written: `tested` iff every registered assertion check, the
generator, ruff, format and mypy checks, the deviation and A10's floor pass; otherwise
`implemented`. Both review fields stay `pending`. The limitations are §14's items verbatim,
§18.9 verbatim, then what this run found.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s02_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
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

SPEC = ROOT / "docs" / "derivations" / "S02-spec.md"
REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "s02_reference.json"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s02_reference.py"
ADR_0044 = ROOT / "docs" / "adr" / "0044-edge3-after-restart-into-singular-signature.md"
#: The source files S02 added or changed (from `wp/S01`).
SOURCES = (
    "src/openflowsheet/compile/spec.py",
    "src/openflowsheet/models/rows.py",
    "src/openflowsheet/models/syn001/cascade_solve.py",
    "src/openflowsheet/models/syn001/column.py",
    "src/openflowsheet/models/syn001/column_solve.py",
    "src/openflowsheet/numerics/scaling.py",
    "src/openflowsheet/orchestrator/executor.py",
    "src/openflowsheet/orchestrator/recovery.py",
)
#: The registered assertion ids, in order: §10 A01–A16, §17 A17–A19, §18.6's additions.
ASSERTIONS = (
    *(f"A{index:02d}" for index in range(1, 6)),
    "A06",
    "A06b",
    *(f"A{index:02d}" for index in range(7, 13)),
    "A13",
    "A13b",
    *(f"A{index:02d}" for index in range(14, 23)),
)
#: The ids §10, §17 and §18.6 must each state.
SECTION_IDS = {
    10: tuple(f"A{index:02d}" for index in range(1, 17)),
    17: ("A17", "A18", "A19"),
    18: ("A05", "A06", "A06b", "A07", "A13", "A13b", "A14", "A20", "A21", "A22"),
}
#: The non-assertion checks `status` also requires.
REQUIRED_CHECKS = (
    "S02.generator",
    "S02.ruff",
    "S02.format",
    "S02.mypy",
    "S02.deviation",
    "S02.A10-floor",
)
#: An assertion id in a test function's name: `_aNN` or `_aNNb`, then `_` or the end.
CITED = re.compile(r"(?:^|_)a(\d{2}b?)(?=_|$)")
#: §10: the deviation margin; A10: the floor.
MARGIN, FD_FLOOR = 0.1, 1e-8


# -- the specification ---------------------------------------------------------------------------


def section(document: str, number: int) -> str:
    """The body of `## <number>.` up to the next `## ` heading or the end."""
    match = re.search(rf"^## {number}\. .*?$(.*?)(?=^## |\Z)", document, re.M | re.S)
    if match is None:
        raise SystemExit(f"{SPEC.name} has no section {number}")
    return match.group(1)


def subsection(document: str, number: str) -> str:
    """The body of `### <number> ` up to the next heading."""
    match = re.search(rf"^### {re.escape(number)} .*?$(.*?)(?=^##+ |\Z)", document, re.M | re.S)
    if match is None:
        raise SystemExit(f"{SPEC.name} has no subsection {number}")
    return match.group(1)


def bullets(body: str) -> list[str]:
    """A section's `- ` items verbatim, continuation lines joined by one space."""
    items: list[str] = []
    for line in body.splitlines():
        if line.startswith("- "):
            items.append(line[2:].strip())
        elif line.startswith("  ") and items and line.strip():
            items[-1] += " " + line.strip()
    return items


def paragraph(body: str) -> str:
    """A section's first paragraph verbatim, lines joined by one space."""
    lines: list[str] = []
    for line in body.strip().splitlines():
        if not line.strip():
            break
        lines.append(line.strip())
    return " ".join(lines)


def table(body: str) -> dict[str, tuple[str, str, str]]:
    """An assertion table: id → (assertion, expected, tolerance)."""
    rows: dict[str, tuple[str, str, str]] = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        if len(cells) == 4 and re.fullmatch(r"A\d{2}b?", cells[0]):
            rows[cells[0]] = (cells[1], cells[2], cells[3])
    return rows


def assertion_table(document: str) -> dict[str, tuple[str, str, str]]:
    """§10's table, §17's, and §18.6's restatements and additions (which replace §10's rows)."""
    parts = {
        10: table(section(document, 10)),
        17: table(section(document, 17)),
        18: table(subsection(document, "18.6")),
    }
    for number, expected in SECTION_IDS.items():
        if tuple(sorted(parts[number])) != tuple(sorted(expected)):
            raise SystemExit(f"§{number}'s ids are {sorted(parts[number])}, not {expected}")
    merged = {**parts[10], **parts[17], **parts[18]}
    return {identifier: merged[identifier] for identifier in ASSERTIONS}


def limitations_of_the_spec(document: str) -> list[str]:
    """§14's items verbatim, then §18.9 (Amendment 2's "what this does not establish")."""
    items = bullets(section(document, 14))
    if not items:
        raise SystemExit("§14 lists no item")
    amendment = paragraph(subsection(document, "18.9"))
    if not amendment:
        raise SystemExit("§18.9 is empty")
    return [*items, amendment]


# -- the tests -----------------------------------------------------------------------------------


def cited(node: str) -> tuple[str, ...]:
    """The S02 assertion ids a test node cites, from its function name (parameters ignored)."""
    name = node.rsplit("::", 1)[-1].split("[", 1)[0]
    return tuple(f"A{number}" for number in CITED.findall(name))


def _verdict(citing: Sequence[Node]) -> tuple[str, dict[str, Any]]:
    not_passed = [
        {"node": item.node, "outcome": item.outcome, "message": text(item.message[:600])}
        for item in citing
        if item.outcome != "passed"
    ]
    value = {
        "judged_by": "tests",
        "nodes": len(citing),
        "outcomes": dict(sorted(Counter(item.outcome for item in citing).items())),
        "selectors": [item.node for item in citing],
        "not_passed": not_passed,
    }
    return ("pass" if citing and not not_passed else "fail"), value


def s01_suite(tests: Sequence[Node]) -> tuple[str, dict[str, Any]]:
    """A16: every S01 node passed and each of S01's A01–A20 is cited by at least one."""
    s01 = [item for item in tests if item.node.startswith("tests/test_s01_")]
    result, value = _verdict(s01)
    uncited = [
        identifier
        for identifier in S01_ASSERTIONS
        if not any(identifier in s01_cited(item.node) for item in s01)
    ]
    value = {**value, "judged_by": "the S01 suite", "s01_assertions_uncited": uncited}
    del value["selectors"]
    return ("pass" if result == "pass" and not uncited else "fail"), value


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]], tests: Sequence[Node]
) -> list[dict[str, Any]]:
    s02 = [item for item in tests if item.node.startswith("tests/test_s02_")]
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        if identifier == "A16":
            result, value = s01_suite(tests)
        else:
            result, value = _verdict([item for item in s02 if identifier in cited(item.node)])
        assertion, expected, tolerance = rows[identifier]
        entries.append(
            check(f"S02.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


# -- the measurements ----------------------------------------------------------------------------


def _import_tests() -> None:
    for path in (ROOT / "src", ROOT / "tests"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def deviation_check(commit: str) -> dict[str, Any]:
    """§10/§18.5: the worst deviation of each registered root, per column class, in units of the
    state tolerance, with the tests' own fixtures and measure."""
    _import_tests()
    from test_s02_column_wo1 import CASES, REFERENCE
    from test_s02_column_wo2 import deviation, deviation_from, from_x0, stages_state
    from test_s02_column_wo2b import MATCHED, R2, _spec, solved

    measured: dict[str, dict[str, float]] = {}
    for case in CASES:
        measured[f"{case} solve_column (A06)"] = deviation(case, solved(case).state)
        measured[f"{case} from the profile endpoint (A06b)"] = deviation(
            case, from_x0(case)[0].state
        )
    for case, variant in MATCHED:
        measured[f"V-{case} {variant} (A07)"] = deviation(case, solved(case, variant).state)
    second = REFERENCE["variants"][R2[0]][R2[1]]["second_root"]["stages"]
    spec = _spec(*R2)
    measured[f"V-{R2[0]} {R2[1]} against R2 (A07)"] = deviation_from(
        spec, stages_state(spec, second), solved(*R2).state
    )
    worst = max(max(part.values()) for part in measured.values())
    short = sorted(name for name, part in measured.items() if max(part.values()) > MARGIN)
    return check(
        "S02.deviation",
        "§10/§18.5: the measured maximum deviation of every registered root (solve_column's "
        "path for M1–M4, the variant sets and R2; the profile endpoint's for M1–M4) from ref, "
        "per column class, in units of §10's state tolerance (1 is the tolerance); §10 requires "
        "the tolerance to be at least 10x the measurement",
        "pass" if worst <= MARGIN else "fail",
        {"measured_at": commit, "worst": worst, "below_10x_margin": short, "cases": measured},
        "every value ≤ 0.1",
    )


def floor_check(commit: str) -> dict[str, Any]:
    """§10 A10 / §13: the measured floor of the compiled Jacobian against central differences."""
    _import_tests()
    from test_s02_column_wo1 import PROVIDER, SPECS
    from test_s02_column_wo2 import fd_errors, ref_state

    from openflowsheet.models.syn001.cascade import CascadeFailure
    from openflowsheet.models.syn001.column import profile_initial
    from openflowsheet.models.syn001.column_solve import DECLARATION_CONTEXT

    measured: dict[str, dict[str, Any]] = {}
    for case in ("M2", "M1"):
        initial = profile_initial(SPECS[case], PROVIDER, DECLARATION_CONTEXT)
        assert not isinstance(initial, CascadeFailure), initial
        points = {"x_K": dict(initial.state), "root": ref_state(case, "target")}
        for point, state in points.items():
            errors = fd_errors(case, state)
            (column, row), value = max(errors.items(), key=lambda item: item[1])
            measured[f"{case} {point}"] = {"worst": value, "column": column, "row": row}
    worst = max(entry["worst"] for entry in measured.values())
    return check(
        "S02.A10-floor",
        "§10 A10 / §13: the measured floor of D_r⁻¹ J D_x against central differences at "
        "h = 1e-6·max(D_x, |x|) (R-516), at x_K and the root of M1 and M2; it must be ≤ 1e-8",
        "pass" if worst <= FD_FLOOR else "fail",
        {"measured_at": commit, "worst": worst, "points": measured},
        "≤ 1e-8",
    )


def p1_record(commit: str, a12: Mapping[str, Any]) -> dict[str, Any]:
    """§13: P1's actual outcome and attempt list (A12), with the commit; judged by `S02.A12`."""
    _import_tests()
    from test_s02_column_wo3 import attempt_list, p1

    answer = p1()
    return check(
        "S02.P1-outcome",
        "§13 / A12: P1's actual outcome and the attempts of the target and of edge 3, each with "
        "its attempted signature; the result is S02.A12's",
        a12["result"],
        {
            "measured_at": commit,
            "outcome": answer.outcome,
            "cause": answer.cause,
            "attempts": attempt_list(answer),
        },
        "CONVERGED at the closed form (LIQUID x5), or a typed outcome naming every attempt",
    )


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every registered assertion and every required check passes."""
    required = {f"S02.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        "requirements is empty: the schema takes D/A requirement ids and none lists S02; "
        "S02 supplies part of X31's evidence (docs/requirements.yaml: owners S02, S03) — the "
        "four matched column cases, the invalid specifications and the phase case against this "
        "package's generator; X31's two independent references and perturbation studies are "
        "S03's (§14). The mapping and the verdict are the design lane's.",
        "ADR 0044 (edge 3 after a restart that ends LINEAR_SOLVE_FAILED, D1 narrowed to an "
        "attempt 0 that ended in a core globalization failure, §19 item 1) is Proposed until "
        "R-550's conditions hold: this manifest tested, scripts/gate.sh green on the merge "
        "candidate with CI green on both architectures and C2 rewritten from that run, and a "
        "workstation scan of registered step records logged; the decisions it rests on are "
        "R-546 to R-550. A20's clause that the full gate moves no registered outcome outside S02 "
        "is not measured here.",
        "scripts/gate.sh was not run by this generator (it runs once before merge into main); "
        "S02.gate is unsupported here.",
        "Review: the design lane's reviewer pass is docs/reviews/S02-review.md (rulings R-550 to "
        "R-554); its fix work order items 1-3 are in this commit. The reviewer's check of those "
        "fixes and the human numerical and process-model review are pending; this manifest "
        "claims neither.",
        "The reference agreement is numerical verification against a 50-digit generator that "
        "shares SYN-001 and the §6/§18.2 definitions, not empirical validation.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] == "S02.gate":
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
                "docs/S02_DECISIONS.md)"
            )
        )
    return items


def build(commit: str) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    document = SPEC.read_text(encoding="utf-8")
    rows = assertion_table(document)
    artifacts = ROOT / "evidence" / "S02" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s02-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        shown(path)
        for pattern in ("test_s02_*.py", "test_s01_*.py")
        for path in (ROOT / "tests").glob(pattern)
    )
    s02_tests = [path for path in tests if Path(path).name.startswith("test_s02_")]
    lint = [*SOURCES, *s02_tests, "scripts/s02_evidence_manifest.py", shown(GENERATOR)]

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
        "S02.generator": run([python, str(GENERATOR), "--check"]),
        "S02.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S02.format": run([str(tools / "ruff"), "format", "--check", *lint]),
        "S02.mypy": run([str(tools / "mypy")], pythonpath=True),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")

    entries = assertion_checks(rows, nodes(junit))
    tool_text = {
        "S02.generator": "§13: s02_reference.py --check re-derives every claim (1074) and "
        "byte-compares s02_reference.json",
        "S02.ruff": "§13: ruff check is clean on S02's files",
        "S02.format": "§13: ruff format --check is clean on S02's files",
        "S02.mypy": "mypy (the project's configuration) is clean",
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
    a12 = next(entry for entry in entries if entry["id"] == "S02.A12")
    entries.append(p1_record(commit, a12))
    entries.append(
        check(
            "S02.gate",
            "§13: scripts/gate.sh passes before merge",
            "unsupported",
            "not run by this generator; the full gate runs once before merge (CLAUDE.md)",
        )
    )

    manifest: dict[str, Any] = {
        "work_package": "S02",
        "commit": commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "S02 acceptance: docs/derivations/S02-spec.md §10, §17 and §18.6 "
            "(A01–A22, A06b, A13b) against docs/derivations/scripts/s02_reference.json, "
            "check list §13",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S02 and S01 test run (ignored; kept by hash)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "the design lane's 50-digit reference values (ref)",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S02 specification the checks are read from (§10, §13, §14, "
                "§17, §18)",
            },
            {
                "path": shown(ADR_0044),
                "sha256": sha256_file(ADR_0044),
                "description": "ADR 0044 (Proposed): edge 3 after LINEAR_SOLVE_FAILED in a "
                "restart (R-547); S02's other Amendment 2 decisions are R-546, R-548, R-549",
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
    parser.add_argument("--out", type=Path, help="default: evidence/S02/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S02" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
