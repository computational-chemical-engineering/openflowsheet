"""Generate `evidence/S08/<commit>/manifest.json` by running, not by transcribing. S08 (WO-4, WO-5).

The design note `docs/derivations/S08-design.md` (ADR 0048) is the check list: §7's assertion
table (S08.A01–A16), Amendment 1 §13.6's (S08.A17, A18) and §9's gates. Everything recorded is
produced here, at the checked-out commit (the script refuses to run when `HEAD` is not
`--commit` or when a tracked source, test, script, schema or derivation file differs from it;
S01's rule):

1. **The S08, S01, S02, S06 and S03 tests** (`tests/test_s08_*.py`, `tests/test_s01_*.py`,
   `tests/test_s02_*.py`, `tests/test_s06_*.py`, `tests/test_s03_*.py`; one `pytest --junitxml`
   run). An S08 test cites the assertion its function name starts with (`test_a07_…` cites A07,
   `test_a14b_…_fails_a08` A14 only). `S08.Axx` passes only if at least one S08 node cites it
   and every node citing it passed: a failure, an error, a skip or an expected failure leaves it
   `fail`. **A13** (bit-identity, G1) also requires the G1 run below to pass. **G3**'s second
   half, the S01, S02, S06 and S03 suites, is `S08.G3-suites`: every one of their nodes passed.
2. **G1**, `scripts/s08_identity.py` against the merge base `390e0af5` (in a detached worktree
   the script creates and removes): its one line must be §9's
   `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`.
3. **G2**, structure: `git diff --stat $(git merge-base main HEAD)..HEAD` is empty over §9's
   paths.
4. **The reference generator's `--check`** (`s08_reference.py`, WO-G: 84 claims, JSON
   byte-identical).
5. **G5**, the recorded numbers, measured here: P1's Stage-B iterations (≤ 1), P3's, the largest
   item-6 error on the registered roots Stage A converges to (≤ 1e-5 K), and the wall time of
   one `solve_column` on P1 and P3.
6. **`ruff check`, `ruff format --check`** on S08's files and **`mypy`** (the project's own
   configuration).

`scripts/gate.sh` and CI on both architectures (G4) are not run here (they run once before
merge): their checks are `unsupported`. `status` is computed, never written: `tested` iff every
assertion A01–A18 and every required check passes; otherwise `implemented`. Both review fields
stay `pending`; `reviewed` is the design lane's `reviewer`'s. The limitations are §11's items
verbatim, then what this run found. S08 evidences release gate X31's "invalid specs/phases"
clause (§13.10); the frozen manifest schema admits only D/A requirement ids in `requirements`,
so that stays empty, the ledger cites this manifest under X31's `evidence`, and a limitation
says so (docs/S08_DECISIONS.md W5-7).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s08_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
from s02_evidence_manifest import _verdict, bullets, section, subsection  # noqa: E402
from s08_identity import PASS_LINE  # noqa: E402

NOTE = ROOT / "docs" / "derivations" / "S08-design.md"
ADR = ROOT / "docs" / "adr" / "0048-s08-one-phase-column-sections.md"
REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "s08_reference.json"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s08_reference.py"
DECISIONS = ROOT / "docs" / "S08_DECISIONS.md"
#: The source files S08 added or changed (WO-1 to WO-3).
SOURCES = (
    "src/openflowsheet/models/syn001/column_blocks.py",
    "src/openflowsheet/models/syn001/column_solve.py",
)
SCRIPTS = ("scripts/s08_identity.py", "scripts/s08_evidence_manifest.py")
#: §7's assertion ids, then Amendment 1 §13.6's.
NOTE_ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 17))
AMENDMENT_ASSERTIONS = ("A17", "A18")
ASSERTIONS = NOTE_ASSERTIONS + AMENDMENT_ASSERTIONS
#: The manifest's `requirements`. S08 evidences gate X31's "invalid specs/phases" clause (§13.10,
#: R-736), but `schemas/evidence-manifest.schema.json` (frozen) admits only `^[DA][0-9]{2}$`
#: there; the ledger cites the manifest under X31 instead (W5-7).
REQUIREMENTS: list[str] = []
#: The gate S08 evidences, named in the limitations.
GATE = "X31"
#: The non-assertion checks `status` also requires.
REQUIRED_CHECKS = (
    "S08.G1",
    "S08.G2",
    "S08.G3-suites",
    "S08.G5",
    "S08.generator",
    "S08.ruff",
    "S08.format",
    "S08.mypy",
)
#: §9 G2: the paths S08 must not touch.
FROZEN = (
    "src/openflowsheet/orchestrator",
    "src/openflowsheet/numerics",
    "src/openflowsheet/thermo",
    "src/openflowsheet/compile",
    "src/openflowsheet/models/syn001/cascade.py",
    "src/openflowsheet/models/syn001/cascade_solve.py",
    "src/openflowsheet/models/syn001/column.py",
    "schemas",
)
#: The suites G3 requires besides S08's.
LOWER_SUITES = ("test_s01_", "test_s02_", "test_s06_", "test_s03_")
#: The assertion an S08 test cites: its name's leading `test_aNN`, optionally with a mutation
#: letter (`test_a14b_…`); a later `_aNN` (`…_fails_a08`) names the check a mutation breaks.
CITED = re.compile(r"^test_a(\d{2})[a-e]?(?=_|$)")
#: §9 G5's bounds: P1's Stage-B iterations, the largest item-6 error (K).
P1_ITERATIONS, ITEM_6_BOUND = 1, 1e-5
#: `s08_reference.py --check`'s first line.
GENERATOR_LINE = "84 claims passed"


# -- the note ------------------------------------------------------------------------------------


def _table(body: str) -> dict[str, tuple[str, str, str]]:
    rows: dict[str, tuple[str, str, str]] = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        match = re.fullmatch(r"S08\.(A\d{2})", cells[0])
        if match and len(cells) == 4:
            rows[match.group(1)] = (cells[1], cells[2], cells[3])
    return rows


def assertion_table(document: str) -> dict[str, tuple[str, str, str]]:
    """§7's table and §13.6's: id → (assertion, expected, tolerance), exactly S08.A01–A16 from
    §7 and S08.A17, A18 from §13.6."""
    rows = _table(section(document, 7))
    if tuple(sorted(rows)) != NOTE_ASSERTIONS:
        raise SystemExit(f"§7's ids are {sorted(rows)}, not {NOTE_ASSERTIONS}")
    amended = _table(subsection(document, "13.6"))
    if tuple(sorted(amended)) != AMENDMENT_ASSERTIONS:
        raise SystemExit(f"§13.6's ids are {sorted(amended)}, not {AMENDMENT_ASSERTIONS}")
    rows.update(amended)
    return {identifier: rows[identifier] for identifier in ASSERTIONS}


def limitations_of_the_note(document: str) -> list[str]:
    """§11's items verbatim ("What this does not establish")."""
    items = bullets(section(document, 11))
    if not items:
        raise SystemExit("§11 lists no item")
    return items


# -- the tests -----------------------------------------------------------------------------------


def cited(node: str) -> tuple[str, ...]:
    name = node.rsplit("::", 1)[-1].split("[", 1)[0]
    return tuple(f"A{number}" for number in CITED.findall(name))


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]], tests: Sequence[Node], g1: Mapping[str, Any]
) -> list[dict[str, Any]]:
    s08 = [item for item in tests if item.node.startswith("tests/test_s08_")]
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        result, value = _verdict([item for item in s08 if identifier in cited(item.node)])
        if identifier == "A13":
            value = {**value, "judged_by": "tests and gate G1", "G1": g1["result"]}
            result = "pass" if result == "pass" and g1["result"] == "pass" else "fail"
        assertion, expected, tolerance = rows[identifier]
        entries.append(
            check(f"S08.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


def lower_suites(tests: Sequence[Node]) -> dict[str, Any]:
    """§9 G3's second half: every S01, S02, S06 and S03 node passed."""
    lower = [
        item for item in tests if item.node.startswith(tuple(f"tests/{p}" for p in LOWER_SUITES))
    ]
    result, value = _verdict(lower)
    del value["selectors"]
    value = {
        **value,
        "judged_by": "the S01, S02, S06 and S03 suites",
        "per_suite": {
            prefix.rstrip("_"): sum(1 for item in lower if item.node.startswith(f"tests/{prefix}"))
            for prefix in LOWER_SUITES
        },
    }
    if not all(value["per_suite"].values()):
        result = "fail"
    return check(
        "S08.G3-suites",
        "§9 G3: the S01, S02, S06 and S03 suites pass (S08's A01–A18 are judged per assertion)",
        result,
        value,
        "every node passed",
    )


# -- the gates -----------------------------------------------------------------------------------


def identity_check(entry: Any) -> dict[str, Any]:
    line = entry.stdout.strip().splitlines()[-1] if entry.stdout.strip() else ""
    passed = entry.exit_code == 0 and line == PASS_LINE
    return check(
        "S08.G1",
        "§9 G1: scripts/s08_identity.py, the pre-existing fields of the 52 registered "
        "configurations on the merge base 390e0af5 and on this commit; equal except P1, whose "
        "reentry.stage_a equals P1's merge-base digest",
        "pass" if passed else "fail",
        {"cmd": entry.cmd, "exit_code": entry.exit_code, "line": line},
        PASS_LINE,
    )


def structure_check() -> dict[str, Any]:
    base = subprocess.run(
        ["git", "merge-base", "main", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "--stat", f"{base}..HEAD", "--", *FROZEN],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return check(
        "S08.G2",
        "§9 G2: git diff --stat $(git merge-base main HEAD)..HEAD is empty over orchestrator, "
        "numerics, thermo, compile, models/syn001/cascade.py, cascade_solve.py, column.py and "
        "schemas",
        "pass" if not diff else "fail",
        {"merge_base": base, "paths": list(FROZEN), "diff_stat": diff},
        "empty",
    )


def recorded_numbers(commit: str) -> dict[str, Any]:
    """§9 G5, measured: P1's and P3's Stage-B iterations and wall time (best of three warm
    calls after one cold call, one process), and the largest item-6 error over the registered
    roots Stage A converges to (`tests/test_s08_item6.py`'s set and measure)."""
    for path in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from test_s02_column_wo1 import PROVIDER, SPECS
    from test_s08_blocks import P3
    from test_s08_item6 import _regimes, _registered

    from openflowsheet.models.syn001.column_solve import (
        ColumnSolution,
        saturation_errors,
        solve_column,
    )

    timed: dict[str, Any] = {}
    for name, spec in (("P1", SPECS["P1"]), ("P3", P3)):
        times = []
        for _ in range(4):
            start = time.perf_counter()
            answer = solve_column(spec, PROVIDER)
            times.append(time.perf_counter() - start)
        assert isinstance(answer, ColumnSolution) and answer.reentry is not None
        timed[name] = {
            "outcome": answer.outcome,
            "stage_b_iterations": [attempt.iterations for attempt in answer.result.attempts],
            "first_call_s": round(times[0], 3),
            "warm_best_s": round(min(times[1:]), 3),
        }
    worst, roots = 0.0, 0
    for spec in _registered().values():
        answer = solve_column(spec, PROVIDER)
        if not isinstance(answer, ColumnSolution) or answer.outcome != "CONVERGED":
            continue
        if answer.reentry is not None:
            continue  # P1, through Stage B at LIQUID ×5: no TWO_PHASE stage (W3-8)
        roots += 1
        errors = saturation_errors(spec, PROVIDER, answer.state, _regimes(spec, answer))
        worst = max(worst, *errors.values())
    p1 = timed["P1"]["stage_b_iterations"]
    passed = len(p1) == 1 and p1[0] <= P1_ITERATIONS and worst <= ITEM_6_BOUND and roots == 42
    return check(
        "S08.G5",
        "§9 G5: P1's Stage-B iterations (≤ 1), P3's iterations, the largest item-6 error on the "
        "registered roots (≤ 1e-5 K) and the wall times of P1 and P3",
        "pass" if passed else "fail",
        {
            "measured_at": commit,
            "P1": timed["P1"],
            "P3": timed["P3"],
            "item_6_roots": roots,
            "item_6_largest_error_K": worst,
        },
        "P1 one attempt, ≤ 1 iteration; 42 roots, largest item-6 error ≤ 1e-5 K",
    )


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every assertion and every required check passes; never `reviewed`."""
    required = {f"S08.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        f"S08 evidences release gate {GATE}'s 'invalid specs/phases' clause only (S08-design "
        "§13.10, R-736): it changes the expected outcome of S02's phase case P1 and adds P2, P3, "
        f"F1, D1 and item 6. It does not touch {GATE}'s reference clause, and {GATE}'s verdict "
        "stays null (the design lane's). requirements is empty because the frozen manifest "
        "schema admits only D/A requirement ids there (§13.10's requirements: [X31] does not "
        f"validate); docs/requirements.yaml cites this manifest under {GATE}'s evidence instead "
        "(docs/S08_DECISIONS.md W5-7).",
        "scripts/gate.sh and CI on x86-64 and aarch64 (§9 G4) were not run by this generator "
        "(they run once before merge into main); S08.gate and S08.ci are unsupported here. "
        "Item 6's margin across architectures (§10 Q5) is therefore not yet shown on aarch64.",
        "Review: the design lane's one reviewer pass on WO-1 to WO-4 (docs/reviews/S08-review.md) "
        "set a build-lane work order before reviewed; WO-5 carries it (A14 (b) per §13.5, A17, "
        "A18, bubble_point_refused per §13.3). Whether it is closed is the reviewer's to judge: "
        "the review fields stay pending and the human numerical and process-model review is "
        "pending; this manifest claims neither.",
        "The root agreement is numerical verification against WO-G's 50-digit generator "
        "(s08_reference.py, which imports nothing from src/ but shares SYN-001 and S02's rows), "
        "not empirical validation.",
        "The T08 support envelope's harvest of this manifest follows its generation, in a later "
        "commit.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] in ("S08.gate", "S08.ci"):
            continue
        value = entry.get("value")
        detail = (
            "; ".join(f"{item['node']} {item['outcome']}" for item in value["not_passed"])
            if isinstance(value, dict) and value.get("not_passed")
            else "see its value"
        )
        items.append(text(f"{entry['id']} is {entry['result']}: {detail}"))
    return items


def build(commit: str) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    document = NOTE.read_text(encoding="utf-8")
    rows = assertion_table(document)
    artifacts = ROOT / "evidence" / "S08" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s08-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        shown(path)
        for pattern in ("test_s08_*.py", *(f"{prefix}*.py" for prefix in LOWER_SUITES))
        for path in (ROOT / "tests").glob(pattern)
    )
    s08_tests = [path for path in tests if Path(path).name.startswith("test_s08_")]
    lint = [*SOURCES, *s08_tests, *SCRIPTS, shown(GENERATOR)]

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
        "S08.G1": run([python, str(ROOT / "scripts" / "s08_identity.py")], pythonpath=True),
        "S08.generator": run([python, str(GENERATOR), "--check"]),
        "S08.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S08.format": run([str(tools / "ruff"), "format", "--check", *lint]),
        "S08.mypy": run([str(tools / "mypy")], pythonpath=True),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")

    found = nodes(junit)
    g1 = identity_check(runs["S08.G1"])
    entries = assertion_checks(rows, found, g1)
    entries += [g1, structure_check(), lower_suites(found), recorded_numbers(commit)]
    generator = runs["S08.generator"]
    entries.append(
        check(
            "S08.generator",
            "WO-G: s08_reference.py --check re-derives every claim (84) and byte-compares "
            "s08_reference.json",
            "pass"
            if generator.exit_code == 0 and generator.stdout.startswith(GENERATOR_LINE)
            else "fail",
            {"cmd": generator.cmd, "exit_code": generator.exit_code},
            f"exit code 0, '{GENERATOR_LINE}'",
        )
    )
    tool_text = {
        "S08.ruff": "ruff check is clean on S08's files",
        "S08.format": "ruff format --check is clean on S08's files",
        "S08.mypy": "mypy (the project's configuration) is clean",
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
    for name, description in (
        ("S08.gate", "§9 G4: scripts/gate.sh passes before merge"),
        ("S08.ci", "§9 G4: CI is green on x86-64 and aarch64 before merge"),
    ):
        entries.append(
            check(
                name,
                description,
                "unsupported",
                "not run by this generator; it runs once before merge (CLAUDE.md)",
            )
        )

    manifest: dict[str, Any] = {
        "work_package": "S08",
        "commit": commit,
        "requirements": REQUIREMENTS,
        "status": status(entries),
        "inputs": {
            "case_id": "S08 acceptance: docs/derivations/S08-design.md §7 and §13.6 (S08.A01–A18) "
            "against docs/derivations/scripts/s08_reference.json (P2, P3, F1, D1) and "
            "s02_reference.json (P1), gates §9",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S08, S01, S02, S06 and S03 test run "
                "(ignored; kept by hash)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "WO-G's 50-digit reference roots and candidate lists (R-732)",
            },
            {
                "path": shown(NOTE),
                "sha256": sha256_file(NOTE),
                "description": "the S08 design note the checks are read from (§7, §9, §11, §13.6)",
            },
            {
                "path": shown(ADR),
                "sha256": sha256_file(ADR),
                "description": "ADR 0048, the decision S08 implements",
            },
            {
                "path": shown(DECISIONS),
                "sha256": sha256_file(DECISIONS),
                "description": "S08's build decisions with the measured facts",
            },
        ],
        "limitations": [*limitations_of_the_note(document), *found_limitations(entries)],
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
    parser.add_argument("--out", type=Path, help="default: evidence/S08/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S08" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
