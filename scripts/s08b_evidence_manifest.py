"""Generate `evidence/S08b/<commit>/manifest.json` by running, not by transcribing. S08b (WO-4).

The design note `docs/derivations/S08b-design.md` (R-790 to R-794) is the check list: §7's
assertions A1–A7 and B1–B3 and §9's gates. Everything recorded is produced here, at the
checked-out commit (the script refuses to run when `HEAD` is not `--commit` or when a tracked
source, test, script, schema or derivation file differs from it; S01's rule):

1. **The S08b tests and the suites they touch** (`tests/test_s08b_*.py`; S01, S02, S03, S06 and
   S08, WO-3's acceptance; and WO-2's touched contract tests, `CONTRACT_SUITES`; one
   `pytest --junitxml` run). An S08b test cites the assertion its function name starts with
   (`test_a1_…` cites A1, `test_b3_…` B3); the guards and pins §7 places in older modules (A5, A6)
   and S08's item-6 tests (B3: "pass untouched") cite through `CITATIONS`. `S08b.<id>` passes only
   if at least one node cites it and every node citing it passed. **B2** also requires the value
   this script measures (the largest saturation error over C1–C5, ≤ 1e-5 K). `S08b.suites`
   requires every node of the run to pass.
2. **G1**, `scripts/s08b_identity.py` against the merge base `a13203b8` (both trees, two
   families): `S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/<n>` — WO-2's
   line; `b_only` counts the decisions of tests that exist on the branch only (informational, §9).
   With it, the older gates on the same content: `scripts/s08_identity.py` (S08's line) and
   `scripts/s10c_identity.py` (S10-C's line), each at its own registered merge base.
3. **G3**, the design scan on this commit: `run_suite.py observe` and `scan_report.py`
   (`docs/derivations/scripts/s08b_design/`), judged against `measured.txt`: no test fails, M1
   reports `records 0`, every S01 row of `measured.txt` is reproduced and every S01 row's largest
   error is ≤ 2.5e-6 K. The flash-type rows are judged against the same scan of the merge base
   `a13203b8` (in a detached worktree with the design scripts copied in), and the near-trivial
   buckets (minority fraction < 1e-3) also against `measured.txt`'s: `measured.txt` was taken on
   main `53228775`, before S10-C merged, and S10-C's tests add 46 kernel-agreeing flash splits
   to the `[0.001, 2)` bucket (build decision WO4-2). The suite counts are recorded; their
   equality with G2's is G2's to show.
4. **`ruff check`, `ruff format --check`** on S08b's files and **`mypy`** (the project's own
   configuration).

`scripts/gate.sh` and CI on both architectures (G2) are not run here (they run once before merge):
their checks are `unsupported`. `status` is computed, never written: `tested` iff every assertion
and every required check passes; otherwise `implemented`. Both review fields stay `pending`;
`reviewed` is the design lane's `reviewer`'s. The limitations are §11's items verbatim, then what
this run found.

The work package id is `S08b` (the frozen manifest schema admits `^[PKTMSR][0-9]{2}[a-z]?$`).
`requirements` is `[D09]` (§10 Q5's default; X31, also named there, is a release gate, which the
schema's `^[DA][0-9]{2}$` does not admit; a limitation says so).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s08b_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
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
from s02_evidence_manifest import _verdict, bullets, section  # noqa: E402
from s08_identity import PASS_LINE as S08_PASS_LINE  # noqa: E402

PACKAGE = "S08b"
NOTE = ROOT / "docs" / "derivations" / "S08b-design.md"
DECISIONS = ROOT / "docs" / "S08b_BUILD_DECISIONS.md"
S01_SPEC = ROOT / "docs" / "derivations" / "S01-spec.md"
DESIGN_SCRIPTS = ROOT / "docs" / "derivations" / "scripts" / "s08b_design"
MEASURED = DESIGN_SCRIPTS / "measured.txt"
#: The source files S08b changed (WO-2, WO-3).
SOURCES = (
    "src/openflowsheet/orchestrator/phase_contract.py",
    "src/openflowsheet/orchestrator/region.py",
    "src/openflowsheet/models/syn001/cascade_solve.py",
    "src/openflowsheet/models/syn001/column_solve.py",
)
SCRIPTS = (
    "scripts/s08b_identity.py",
    "scripts/s08b_identity_recorder.py",
    "scripts/s08b_evidence_manifest.py",
)
#: §7's assertion ids, in order.
ASSERTIONS = (*(f"A{index}" for index in range(1, 8)), "B1", "B2", "B3")
#: The manifest's `requirements` (§10 Q5; X31 is a gate id the frozen schema does not admit).
REQUIREMENTS = ["D09"]
#: WO-2's touched contract tests, run with S08b's (`docs/S08b_BUILD_DECISIONS.md` WO-2).
CONTRACT_SUITES = (
    "tests/test_t05b_dormancy.py",
    "tests/test_t05b_zero_flow.py",
    "tests/test_t03_contract.py",
    "tests/test_t04_ptc_region.py",
    "tests/test_k03_attempts.py",
)
#: WO-3's acceptance suites (§8): S01, S02, S03, S06 and S08.
LOWER_SUITES = ("test_s01_", "test_s02_", "test_s03_", "test_s06_", "test_s08_")
#: The nodes outside `tests/test_s08b_*.py` that §7 names, and the S08b nodes whose names cite
#: nothing: node prefix → the assertions it cites.
CITATIONS: dict[str, tuple[str, ...]] = {
    # A5: the T05b guards keep their values (`items=` added, every asserted value unchanged).
    "tests/test_t05b_dormancy.py::test_items_are_one_step_in_the_lattice": ("A5",),
    "tests/test_t05b_dormancy.py::test_b20d_a_screen_reported_switch_names_the_item": ("A5",),
    "tests/test_t05b_zero_flow.py::test_zero_flow_is_adjacent_to_each_regime": ("A5",),
    # A6: P1's held branch pins its stage-A message.
    "tests/test_s02_column_wo3.py::test_a12_p1_measured_branch_is_held": ("A6",),
    "tests/test_s08_reentry.py::test_a06_p1_stage_a_is_the_held_branch": ("A6",),
    # B3: the constants moved, not copied; S08's item-6 tests pass (WO3-1: one stub retargeted).
    "tests/test_s08b_saturation.py::test_the_constants_": ("B3",),
    "tests/test_s08_item6.py::": ("B3",),
}
#: An S08b test's leading assertion id.
CITED = re.compile(r"^test_([ab]\d)_")
#: G1's line: WO-2's, with `b_only`'s branch count free (tests that exist on the branch only).
G1_LINE = re.compile(
    r"S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/(?P<branch_only>\d+)"
)
S10C_PASS_LINE = "S10C-IDENTITY PASS n=858 changed=[]"
#: G1's merge base, where G3's flash-type rows are re-measured.
MERGE_BASE = "a13203b8"
#: §7 B2's bound, and G3's bound on the S01 rows (K).
B2_BOUND, G3_S01_BOUND = 1e-5, 2.5e-6
SUITE_LINE = re.compile(
    r"S08B-SUITE mode=observe passed=(?P<passed>\d+) failed=(?P<failed>\d+) "
    r"skipped=(?P<skipped>\d+)"
)


# -- the note ------------------------------------------------------------------------------------


def assertion_table(document: str) -> dict[str, str]:
    """§7's items: id → the assertion verbatim, exactly A1–A7 and B1–B3."""
    rows: dict[str, str] = {}
    for item in bullets(section(document, 7)):
        match = re.match(r"\*\*([AB]\d)\*\* (.*)", item)
        if match:
            rows[match.group(1)] = match.group(2)
    if tuple(rows) != ASSERTIONS:
        raise SystemExit(f"§7's ids are {list(rows)}, not {list(ASSERTIONS)}")
    return rows


def limitations_of_the_note(document: str) -> list[str]:
    """§11's items verbatim ("What this does not establish")."""
    items = bullets(section(document, 11))
    if not items:
        raise SystemExit("§11 lists no item")
    return items


# -- the tests -----------------------------------------------------------------------------------


def cited(node: str) -> tuple[str, ...]:
    found: list[str] = []
    if node.startswith("tests/test_s08b_"):
        name = node.rsplit("::", 1)[-1].split("[", 1)[0]
        found += [match.upper() for match in CITED.findall(name)]
    for prefix, identifiers in CITATIONS.items():
        if node.startswith(prefix):
            found += identifiers
    return tuple(dict.fromkeys(found))


def assertion_checks(
    rows: Mapping[str, str], tests: Sequence[Node], b2: Mapping[str, Any]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        result, value = _verdict([item for item in tests if identifier in cited(item.node)])
        expected = "every citing node passed"
        if identifier == "B2":
            value = {**value, "judged_by": "tests and the value measured here", **b2}
            within = b2["largest_error_K"] <= B2_BOUND
            result = "pass" if result == "pass" and within else "fail"
            expected = f"every citing node passed; largest error ≤ {B2_BOUND!r} K"
        entries.append(check(f"S08b.{identifier}", rows[identifier], result, value, expected))
    return entries


def suites_check(tests: Sequence[Node]) -> dict[str, Any]:
    result, value = _verdict(list(tests))
    del value["selectors"]
    prefixes = ("test_s08b_", *LOWER_SUITES)
    value = {
        **value,
        "judged_by": "the S08b tests, WO-3's suites and WO-2's touched contract tests",
        "per_suite": {
            **{
                prefix.rstrip("_"): sum(
                    1 for item in tests if item.node.startswith(f"tests/{prefix}")
                )
                for prefix in prefixes
            },
            **{
                Path(path).stem: sum(1 for item in tests if item.node.startswith(f"{path}::"))
                for path in CONTRACT_SUITES
            },
        },
    }
    if not all(value["per_suite"].values()):
        result = "fail"
    return check(
        "S08b.suites",
        "§8 WO-3: the S01, S02, S03, S06 and S08 test modules pass, with S08b's and WO-2's "
        "touched contract tests",
        result,
        value,
        "every node passed",
    )


def measured_b2(commit: str) -> dict[str, Any]:
    """§7 B2, measured: `max_j max(saturation_pairs(…)[j])` over C1–C5 as registered."""
    for path in (ROOT / "src", ROOT / "tests"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from test_s01_cascade_wo1 import CASES, REFERENCE, UNIT, _spec
    from test_s01_cascade_wo2 import PROVIDER, solved

    from openflowsheet.models.syn001.cascade_solve import saturation_pairs

    per_case: dict[str, float] = {}
    for case in CASES:
        answer = solved(case)
        spec = _spec(REFERENCE["cases"][case])
        regimes = dict(enumerate(answer.signature, start=1))
        pairs = saturation_pairs(UNIT, spec.components, PROVIDER, answer.state, regimes)
        per_case[case] = max(max(errors) for errors in pairs.values())
    return {
        "measured_at": commit,
        "per_case_K": per_case,
        "largest_error_K": max(per_case.values()),
    }


# -- the gates -----------------------------------------------------------------------------------


def _last_line(entry: Any) -> str:
    return entry.stdout.strip().splitlines()[-1] if entry.stdout.strip() else ""


def identity_checks(runs: Mapping[str, Any]) -> list[dict[str, Any]]:
    g1 = runs["S08b.G1"]
    line = _last_line(g1)
    match = G1_LINE.fullmatch(line)
    entries = [
        check(
            "S08b.G1",
            "§9 G1: scripts/s08b_identity.py, two families on the merge base a13203b8 and on this "
            "commit: the 52 configurations' digests equal and their texts equal except §6.1's "
            "eleven; the suite's decision log equal except empty stage change lists filled in",
            "pass" if g1.exit_code == 0 and match else "fail",
            {
                "cmd": g1.cmd,
                "exit_code": g1.exit_code,
                "line": line,
                "branch_only_keys": None if match is None else int(match["branch_only"]),
            },
            "S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/<branch-only "
            "decisions>",
        )
    ]
    for name, expected, description in (
        (
            "S08b.G1-S08",
            S08_PASS_LINE,
            "S08's identity gate (scripts/s08_identity.py, merge base 390e0af5) still passes",
        ),
        (
            "S08b.G1-S10C",
            S10C_PASS_LINE,
            "S10-C's identity gate (scripts/s10c_identity.py, merge base ffcb387f) still passes",
        ),
    ):
        entry = runs[name]
        line = _last_line(entry)
        entries.append(
            check(
                name,
                description,
                "pass" if entry.exit_code == 0 and line == expected else "fail",
                {"cmd": entry.cmd, "exit_code": entry.exit_code, "line": line},
                expected,
            )
        )
    return entries


def _section(report: str, heading: str) -> list[str]:
    """The lines under `## <heading>` up to the next `## ` heading."""
    lines = report.splitlines()
    try:
        start = lines.index(f"## {heading}") + 1
    except ValueError:
        return []
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            body.append(line)
    return body


def _s01_rows(report: str) -> list[str]:
    return [
        line
        for line in _section(report, "S1 stages by unit and test file")
        if line.startswith("S01 ")
    ]


def _flash_rows(report: str) -> list[str]:
    accepted = [
        line
        for line in _section(report, "S1 accepted lifted TWO_PHASE splits")
        if line.startswith("flash/")
    ]
    buckets = [
        line
        for line in _section(
            report, "S1 flash-type SYN-001 splits by minority fraction min(V, L)/n"
        )
        if line.startswith("[")
    ]
    return accepted + buckets


def _near_trivial(rows: Sequence[str]) -> list[str]:
    """The flash-type buckets below a minority fraction of 1e-3, with their example lines."""
    return [line for line in rows if line.startswith("[") and not line.startswith("[0.001, 2)")]


def base_scan(artifacts: Path) -> tuple[Any, Any]:
    """G3's scan on the merge base: a detached worktree with this commit's design scripts."""
    out = artifacts / "g3-base-observe"
    with tempfile.TemporaryDirectory(prefix="s08b-g3-base-") as temporary:
        tree = Path(temporary) / "base"
        subprocess.run(
            ["git", "worktree", "add", "--detach", "--quiet", str(tree), MERGE_BASE],
            cwd=ROOT,
            check=True,
        )
        try:
            scripts = tree / DESIGN_SCRIPTS.relative_to(ROOT)
            shutil.copytree(DESIGN_SCRIPTS, scripts, ignore=shutil.ignore_patterns("__pycache__"))
            python = sys.executable
            suite = run(
                [python, str(scripts / "run_suite.py"), "observe", str(out), "--shards", "16"]
            )
            scan = run([python, str(scripts / "scan_report.py"), str(out)])
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)], cwd=ROOT, check=True
            )
    return suite, scan


def scan_check(suite: Any, scan: Any, base_suite: Any, base: Any) -> dict[str, Any]:
    """§9 G3, judged against `measured.txt` (main 53228775's scan) and, for the flash-type rows,
    against the merge base's scan (WO4-2)."""
    measured = MEASURED.read_text(encoding="utf-8")
    report = scan.stdout
    counts = SUITE_LINE.search(suite.stdout)
    m1 = _section(report, "M1 item/unit classification")
    s01_then, s01_now = _s01_rows(measured), _s01_rows(report)
    worst = [
        float(match.group(1))
        for line in s01_now
        if (match := re.search(r"max_sat_error=(\S+) K", line))
    ]
    flash_then, flash_now = _flash_rows(measured), _flash_rows(report)
    flash_base = _flash_rows(base.stdout)
    base_counts = SUITE_LINE.search(base_suite.stdout)
    findings = {
        "suite_ran_and_no_test_failed": bool(
            suite.exit_code == 0 and counts and int(counts["failed"]) == 0
        ),
        "m1_records_0": bool(m1) and m1[0].startswith("records 0;"),
        "s01_rows_of_measured_reproduced": bool(s01_then)
        and all(line in s01_now for line in s01_then),
        "s01_largest_error_within_bound": bool(worst) and max(worst) <= G3_S01_BOUND,
        "base_scan_ran_and_no_test_failed": bool(
            base_suite.exit_code == 0
            and base.exit_code == 0
            and base_counts
            and int(base_counts["failed"]) == 0
        ),
        "flash_rows_equal_merge_base": bool(flash_base) and flash_now == flash_base,
        "near_trivial_flash_rows_equal_measured": bool(_near_trivial(flash_then))
        and _near_trivial(flash_now) == _near_trivial(flash_then),
    }
    return check(
        "S08b.G3",
        "§9 G3: the design scan (run_suite.py observe, scan_report.py) on this commit: S1's S01 "
        "rows unchanged (largest error ≤ 2.5e-6 K), M1 records 0; S1's flash-type rows identical "
        "to the merge base's scan (measured.txt predates S10-C) and the near-trivial ones to "
        "measured.txt's (WO4-2); the suite counts are recorded (their equality with G2's is "
        "G2's)",
        "pass" if scan.exit_code == 0 and all(findings.values()) else "fail",
        {
            "suite_cmd": suite.cmd,
            "scan_cmd": scan.cmd,
            "suite_line": counts.group(0) if counts else _last_line(suite),
            "base_suite_cmd": base_suite.cmd,
            "base_suite_line": base_counts.group(0) if base_counts else _last_line(base_suite),
            "findings": findings,
            "m1": m1[:1],
            "s01_rows": s01_now,
            "s01_rows_new": [line for line in s01_now if line not in s01_then],
            "s01_largest_error_K": max(worst) if worst else None,
            "flash_rows": flash_now,
            "flash_rows_merge_base": flash_base,
            "flash_rows_measured": flash_then,
        },
        "every finding true",
    )


# -- the manifest --------------------------------------------------------------------------------


REQUIRED_CHECKS = (
    "S08b.suites",
    "S08b.G1",
    "S08b.G1-S08",
    "S08b.G1-S10C",
    "S08b.G3",
    "S08b.ruff",
    "S08b.format",
    "S08b.mypy",
)


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every assertion and every required check passes; never `reviewed`."""
    required = {f"S08b.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        "requirements is [D09] (S08b-design §10 Q5's default). Q5 also names release gate X31 "
        "('invalid specs/phases' in column-family cases); the frozen manifest schema admits only "
        "D/A requirement ids there, so X31 is not listed (S08's precedent, docs/S08_DECISIONS.md "
        "W5-7). Neither verdict is claimed.",
        "scripts/gate.sh and CI on x86-64 and aarch64 (§9 G2) were not run by this generator "
        "(they run once before merge into main); S08b.gate and S08b.ci are unsupported here. "
        "G3's suite counts are recorded, not compared with G2's.",
        "CoolProp 8.0.0 is not installed on the workstation that ran G1 and G3, so its tests "
        "skipped there; CoolProp-backed lifted splits were not scanned (§10 Q2).",
        "Review: the design lane's one reviewer pass (the package touches phase logic, §8 WO-4) "
        "follows this manifest; the review fields stay pending and the human numerical and "
        "process-model review is pending. This manifest claims neither.",
        "The T08 support envelope's harvest of this manifest follows its generation, in a later "
        "commit.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] in ("S08b.gate", "S08b.ci"):
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
    artifacts = ROOT / "evidence" / PACKAGE / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s08b-tests.junit.xml"
    scan_out = artifacts / "g3-observe"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        {
            shown(path)
            for pattern in ("test_s08b_*.py", *(f"{prefix}*.py" for prefix in LOWER_SUITES))
            for path in (ROOT / "tests").glob(pattern)
        }
        | set(CONTRACT_SUITES)
    )
    s08b_tests = [path for path in tests if Path(path).name.startswith("test_s08b_")]
    lint = [*SOURCES, *s08b_tests, *SCRIPTS]

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
        "S08b.G1": run([python, str(ROOT / "scripts" / "s08b_identity.py")], pythonpath=True),
        "S08b.G1-S08": run([python, str(ROOT / "scripts" / "s08_identity.py")], pythonpath=True),
        "S08b.G1-S10C": run([python, str(ROOT / "scripts" / "s10c_identity.py")], pythonpath=True),
        "S08b.G3-suite": run(
            [
                python,
                str(DESIGN_SCRIPTS / "run_suite.py"),
                "observe",
                str(scan_out),
                "--shards",
                "16",
            ],
            pythonpath=True,
        ),
        "S08b.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S08b.format": run([str(tools / "ruff"), "format", "--check", *lint]),
        "S08b.mypy": run([str(tools / "mypy")], pythonpath=True),
    }
    runs["S08b.G3-scan"] = run(
        [python, str(DESIGN_SCRIPTS / "scan_report.py"), str(scan_out)], pythonpath=True
    )
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")
    runs["S08b.G3-base-suite"], runs["S08b.G3-base-scan"] = base_scan(artifacts)
    scan_report = artifacts / "g3-scan-report.txt"
    scan_report.write_text(runs["S08b.G3-scan"].stdout, encoding="utf-8")
    base_report = artifacts / "g3-base-scan-report.txt"
    base_report.write_text(runs["S08b.G3-base-scan"].stdout, encoding="utf-8")

    found = nodes(junit)
    entries = assertion_checks(rows, found, measured_b2(commit))
    entries += [suites_check(found), *identity_checks(runs)]
    entries.append(
        scan_check(
            runs["S08b.G3-suite"],
            runs["S08b.G3-scan"],
            runs["S08b.G3-base-suite"],
            runs["S08b.G3-base-scan"],
        )
    )
    tool_text = {
        "S08b.ruff": "ruff check is clean on S08b's files",
        "S08b.format": "ruff format --check is clean on S08b's files",
        "S08b.mypy": "mypy (the project's configuration) is clean",
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
        ("S08b.gate", "§9 G2: scripts/gate.sh passes before merge"),
        ("S08b.ci", "§9 G2: CI is green on x86-64 and aarch64 before merge"),
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
        "work_package": PACKAGE,
        "commit": commit,
        "requirements": REQUIREMENTS,
        "status": status(entries),
        "inputs": {
            "case_id": "S08b acceptance: docs/derivations/S08b-design.md §7 (A1–A7, B1–B3) and §9 "
            "(G1, G3) against S08's 52 configurations, S01's registered cases C1–C5 and the "
            "design scan's measured.txt",
            "case_hash": sha256_file(MEASURED),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S08b, S01, S02, S03, S06, S08 and contract "
                "test run (ignored; kept by hash)",
            },
            {
                "path": shown(scan_report),
                "sha256": sha256_file(scan_report),
                "description": "G3's scan report on this commit (ignored; kept by hash)",
            },
            {
                "path": shown(base_report),
                "sha256": sha256_file(base_report),
                "description": "G3's scan report on the merge base a13203b8 (ignored; kept by "
                "hash)",
            },
            {
                "path": shown(MEASURED),
                "sha256": sha256_file(MEASURED),
                "description": "the design scan's measurements G3 is judged against",
            },
            {
                "path": shown(NOTE),
                "sha256": sha256_file(NOTE),
                "description": "the S08b design note the checks are read from (§7, §9, §11)",
            },
            {
                "path": shown(S01_SPEC),
                "sha256": sha256_file(S01_SPEC),
                "description": "the S01 spec with Amendment 2 (§18), the clause WO-3 implements",
            },
            {
                "path": shown(DECISIONS),
                "sha256": sha256_file(DECISIONS),
                "description": "S08b's build decisions and gate log",
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
    parser.add_argument("--out", type=Path, help="default: evidence/S08b/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / PACKAGE / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
