"""Generate `evidence/S09/<commit>/manifest.json` by running, not by transcribing. S09 (WO-S09-3).

Spec `docs/derivations/S09-spec.md` §13 (as amended by §18) is the check list. Modelled on
`scripts/s03_evidence_manifest.py`. Everything recorded is produced here, at the checked-out commit
(the script refuses to run when `HEAD` is not `--commit` or when a tracked source, test, script,
schema, derivation or S03/S09 record file differs from it; S01's rule):

1. **The S09 tests and the suites A20 names** (`tests/test_s09_*.py`, `tests/test_s01_*.py`,
   `tests/test_s02_*.py`, `tests/test_s03_*.py`, `tests/test_s06_*.py`, one `pytest --junitxml`
   run). An S09 test cites the assertions its function name carries (`test_a09_…` cites A09).
   `S09.Axx` passes only if at least one S09 node cites it and every node citing it passed.
   **A20** ("S01's, S02's, S03's and S06's suites pass unchanged; the generators check") is judged
   by every S01, S02, S03 and S06 node and S09's `test_a20_…` nodes. **A19** is the `verdict`
   agent's document `docs/reviews/S09-verdicts.md` (WO-S09-4): present, or `fail`.
2. **The generators' `--check`**: `s09_reference.py` (181 claims after Amendment 1) and
   `s03_reference.py` (§13).
3. **The comparison's `--check`**: `comparison.json` and `SHA256SUMS` recompute identically.
4. **`ruff check`, `ruff format --check`** on S09's files.
5. **The comparison record** §13 lists: BioSTEAM's fingerprint, the qualification and comparison
   commits (ancestry checked), the SHA-256 of every record and of `comparison.json`, each pair's
   level, rung and classification, each control's classification, the three-tool table and the
   clause.

`scripts/gate.sh` and CI on both architectures are not run here (they run once before merge):
their checks are `unsupported`. `status` is computed, never written: `tested` iff every registered
assertion check (A01–A20, A19 the verdict document), both generators, the comparison, ruff and
format checks pass; otherwise `implemented`. Both review fields stay `pending`; `reviewed` is the
`reviewer`'s. The limitations are §14's items verbatim, §18.7's, then what this run found.

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/s09_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s09_reference_comparison as comparison  # noqa: E402
from s01_evidence_manifest import (  # noqa: E402  (S01's generic helpers, unchanged)
    CLEAN_PATHS,
    LOCK,
    ROOT,
    SCHEMA,
    Node,
    check,
    command,
    nodes,
    run,
    sha256_file,
    shown,
    text,
)
from s02_evidence_manifest import _verdict, bullets, cited  # noqa: E402
from s03_evidence_manifest import section  # noqa: E402  (S03's section reader, unchanged)

SPEC = ROOT / "docs" / "derivations" / "S09-spec.md"
CASES9 = comparison.CASES9_PATH
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s09_reference.py"
S03_GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s03_reference.py"
VERDICTS = ROOT / "docs" / "reviews" / "S09-verdicts.md"
SCRIPTS = (
    "scripts/s09_reference_comparison.py",
    "scripts/s09_evidence_manifest.py",
    "spikes/references/s09_qualify_biosteam.py",
    "spikes/references/s09_biosteam_syn001.py",
)
#: §11's ids, A01–A20 (amended by §18.5 and §19.5).
ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 21))
REQUIRED_CHECKS = ("S09.generator", "S09.s03_generator", "S09.comparison", "S09.ruff", "S09.format")
CLAIMS = 181
#: The suites A20 names.
A20_SUITES = ("tests/test_s01_", "tests/test_s02_", "tests/test_s03_", "tests/test_s06_")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def refuse_unless_measuring(commit: str) -> None:
    head = git("rev-parse", "HEAD")
    if head != commit:
        raise SystemExit(f"HEAD is {head}, not {commit}: check the commit out to measure it")
    dirty = git(
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        *CLEAN_PATHS,
        "spikes/references",
        "benchmarks/s03",
        "benchmarks/s09",
    )
    if dirty:
        raise SystemExit(f"tracked files differ from {commit}:\n{dirty}")


# -- the specification ---------------------------------------------------------------------------


def assertion_table(document: str) -> dict[str, tuple[str, str, str]]:
    rows: dict[str, tuple[str, str, str]] = {}
    for line in section(document, "## 11.").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        if len(cells) == 4 and re.fullmatch(r"A\d{2}", cells[0]):
            rows[cells[0]] = (cells[1], cells[2], cells[3])
    if tuple(rows) != ASSERTIONS:
        raise SystemExit(f"§11's ids are {list(rows)}, not {list(ASSERTIONS)}")
    return rows


def amendments(document: str) -> dict[str, str]:
    """§18.5's and §19.5's amended assertions per id (§11's rows stand amended by them, in order;
    an id amended twice carries both, §18.5's first)."""
    out: dict[str, str] = {}
    for number in ("18.5", "19.5"):
        for line in section(document, f"### {number}").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
            if len(cells) == 4 and re.fullmatch(r"A\d{2}", cells[0]):
                text = f"{number}: {cells[1]} (expected: {cells[2]})"
                out[cells[0]] = f"{out[cells[0]]}; {text}" if cells[0] in out else text
    return out


def limitations_of_the_spec(document: str) -> list[str]:
    items = bullets(section(document, "## 14."))
    found = bullets(section(document, "### 18.7"))
    if not items or not found:
        raise SystemExit("§14 or §18.7 lists no item")
    return [*items, *(f"18.7: {item}" for item in found)]


# -- the tests -----------------------------------------------------------------------------------


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]], amended: Mapping[str, str], tests: Sequence[Node]
) -> list[dict[str, Any]]:
    s09 = [item for item in tests if item.node.startswith("tests/test_s09_")]
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        if identifier == "A20":
            suites = [item for item in tests if item.node.startswith(A20_SUITES)]
            suites += [item for item in s09 if identifier in cited(item.node)]
            result, value = _verdict(suites)
            del value["selectors"]
            value = {
                **value,
                "judged_by": "the S01, S02, S03 and S06 suites and S09's generator checks",
            }
        elif identifier == "A19":
            present = VERDICTS.is_file()
            result = "pass" if present else "fail"
            value = {
                "judged_by": "the verdict agent's document (WO-S09-4)",
                "path": shown(VERDICTS),
                "present": present,
                "sha256": sha256_file(VERDICTS) if present else None,
            }
        else:
            result, value = _verdict([item for item in s09 if identifier in cited(item.node)])
        assertion, expected, tolerance = rows[identifier]
        if identifier in amended:
            assertion = f"{assertion} [amended: {amended[identifier]}]"
        entries.append(
            check(f"S09.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


# -- the comparison record (§13's list) ----------------------------------------------------------


def comparison_record(document: Mapping[str, Any]) -> dict[str, Any]:
    qualification_path = comparison.QUALIFICATION / "biosteam.json"
    qualification = comparison.load_json(qualification_path)
    qualification_commit = git("log", "-1", "--format=%H", "--", shown(qualification_path))
    table_commit = git("log", "-1", "--format=%H", "--", shown(comparison.TABLE))
    ancestor = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", qualification_commit, table_commit],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
        and qualification_commit != table_commit
    )
    sums = {}
    for line in comparison.SUMS.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    x31 = document["x31_three_tool"]

    def outcome(entry: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "row": entry["row"],
            "outcome": entry["outcome"],
            "classes": {t: p["class"] for t, p in entry["pairs"].items()},
        }

    return {
        "environment_fingerprint": qualification["environment_fingerprint"],
        "qualification_commit": qualification_commit,
        "comparison_commit": table_commit,
        "qualification_commit_is_an_ancestor": ancestor,
        "record_sha256": sums,
        "pairs": {
            cid: {k: p[k] for k in ("level", "rung", "outer_evaluations", "label")}
            for cid, p in document["pairs"].items()
        },
        "not_applicable": document["controls"]["not_applicable"],
        "controls": document["controls"]["per_tool"],
        "control_tool_model_distance": {
            k: {kk: vv for kk, vv in v.items() if kk != "classification"}
            for k, v in document["control_tool_model_distance"].items()
        },
        "comparison_stopped": document["comparison_stopped"],
        "thin_margin": document["margin"]["thin_margin"],
        "x31_three_tool": {
            "clause": x31["clause"],
            "count_row_5": x31["count_row_5"],
            "cases": {c: outcome(v) for c, v in x31["cases"].items()},
            "inverse_kinds": {
                k: {"case": v["case"], **outcome(v)} for k, v in x31["inverse_kinds"].items()
            },
            "reduction_to_s03_equal": document["x31_reduction_to_s03"]["equal"],
        },
    }


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    required = {f"S09.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]], record: Mapping[str, Any]) -> list[str]:
    x31 = record["x31_three_tool"]
    lost = [
        f"{cid}: {p['label']}"
        for cid, p in record["pairs"].items()
        if p["label"].startswith(("NOT_COMPARABLE", "DISAGREE"))
    ]
    items = [
        "requirements lists D19 only: X31 (the reference clause) is a requirement id outside "
        "the manifest schema's D/A pattern. The ledger rows X31 and D19 in "
        "docs/requirements.yaml cite S09's verdict once it exists (§8.5, WO-S09-4); they are "
        "not edited by WO-S09-3.",
        f"Three-tool X31 reference clause as §8.1's table classifies it mechanically: "
        f"{x31['clause']}; {x31['count_row_5']} of 4 counted cases at row 5. Per case: "
        + "; ".join(f"{c} row {v['row']} ({v['outcome']})" for c, v in x31["cases"].items())
        + ". The recorded verdict is the verdict agent's (A19, WO-S09-4).",
        "The controls (positive controls, expected DISAGREE) and every other NOT_COMPARABLE or "
        "DISAGREE pair, with its label: " + (" || ".join(lost) or "none"),
        "Thin margin (a disclosure, §18.4(a)): "
        + (
            "; ".join(f"{e['case']} {e['row']} {e['ratio']:.3g}" for e in record["thin_margin"])
            or "no selected record has a margin-row ratio above 0.1"
        ),
        "scripts/gate.sh and CI on both architectures were not run by this generator (they run "
        "once before merge into main); S09.gate and S09.ci are unsupported here.",
        "Review: the package's single reviewer pass (WO-S09-1 to WO-S09-3) and the human "
        "numerical and process-model review are pending; this manifest claims neither "
        "`reviewed` nor `released`.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] in ("S09.gate", "S09.ci"):
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
    document_text = SPEC.read_text(encoding="utf-8")
    rows = assertion_table(document_text)
    amended = amendments(document_text)
    artifacts = ROOT / "evidence" / "S09" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s09-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        shown(path)
        for pattern in (
            "test_s09_*.py",
            "test_s01_*.py",
            "test_s02_*.py",
            "test_s03_*.py",
            "test_s06_*.py",
        )
        for path in (ROOT / "tests").glob(pattern)
    )
    s09_tests = [path for path in tests if Path(path).name.startswith("test_s09_")]
    lint = [*SCRIPTS, *s09_tests, shown(GENERATOR)]

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
        "S09.generator": run([python, str(GENERATOR), "--check"]),
        "S09.s03_generator": run([python, str(S03_GENERATOR), "--check"]),
        "S09.comparison": run(
            [python, "scripts/s09_reference_comparison.py", "--check"], pythonpath=True
        ),
        "S09.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S09.format": run([str(tools / "ruff"), "format", "--check", *lint]),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")

    entries = assertion_checks(rows, amended, nodes(junit))
    generator_ok = runs["S09.generator"].exit_code == 0 and bool(
        re.search(rf"\b{CLAIMS} claims\b", runs["S09.generator"].stdout)
    )
    tool_text = {
        "S09.generator": (
            f"§13: s09_reference.py --check re-derives every claim ({CLAIMS} after Amendment 1) "
            "and byte-compares s09_cases.json",
            generator_ok,
        ),
        "S09.s03_generator": (
            "§13: s03_reference.py --check passes at the manifest commit",
            runs["S09.s03_generator"].exit_code == 0,
        ),
        "S09.comparison": (
            "§10, A13: comparison.json and SHA256SUMS recompute identically from the committed "
            "records",
            runs["S09.comparison"].exit_code == 0,
        ),
        "S09.ruff": ("§13: ruff check is clean on S09's files", runs["S09.ruff"].exit_code == 0),
        "S09.format": (
            "§13: ruff format --check is clean on S09's files",
            runs["S09.format"].exit_code == 0,
        ),
    }
    for name, (description, ok) in tool_text.items():
        entries.append(
            check(
                name,
                description,
                "pass" if ok else "fail",
                {"cmd": runs[name].cmd, "exit_code": runs[name].exit_code},
                "exit code 0",
            )
        )
    document = comparison.load_json(comparison.TABLE)
    record = comparison_record(document)
    entries.append(
        check(
            "S09.comparison_record",
            "§13's list: BioSTEAM's fingerprint, the qualification and comparison commits "
            "(ancestry), every record's and comparison.json's SHA-256, each pair's level, rung and "
            "classification, each control's classification, the three-tool table and the clause",
            "pass" if record["qualification_commit_is_an_ancestor"] else "fail",
            record,
        )
    )
    entries.append(
        check(
            "S09.gate",
            "§13: scripts/gate.sh passes before the merge",
            "unsupported",
            "not run by this generator; it runs once before merge",
        )
    )
    entries.append(
        check(
            "S09.ci",
            "§13: CI is green on both architectures",
            "unsupported",
            "not measured by this generator; checked before merge",
        )
    )

    manifest: dict[str, Any] = {
        "work_package": "S09",
        "commit": commit,
        "requirements": ["D19"],
        "status": status(entries),
        "inputs": {
            "case_id": "S09 acceptance: docs/derivations/S09-spec.md §11 (A01–A20, amended by "
            "§18.5 and §19.5) against docs/derivations/scripts/s09_cases.json, S03's pinned files "
            "and the committed BioSTEAM records, check list §13",
            "case_hash": sha256_file(CASES9),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S09, S01, S02, S03 and S06 test run "
                "(ignored; kept by hash)",
            },
            {
                "path": shown(comparison.TABLE),
                "sha256": sha256_file(comparison.TABLE),
                "description": "the classification of every (case, BioSTEAM) pair, the controls, "
                "the margin rows and the three-tool X31 table (cmp9, WO-S09-3)",
            },
            {
                "path": shown(comparison.SUMS),
                "sha256": sha256_file(comparison.SUMS),
                "description": "SHA-256 of the qualification record, every tool record and "
                "comparison.json",
            },
            {
                "path": shown(comparison.QUALIFICATION / "biosteam.json"),
                "sha256": sha256_file(comparison.QUALIFICATION / "biosteam.json"),
                "description": "BioSTEAM's qualification record (levels, attempts, rungs, the "
                "repeat run; WO-S09-2)",
            },
            {
                "path": shown(CASES9),
                "sha256": sha256_file(CASES9),
                "description": "the registered settings, thresholds, readback values, controls "
                "and pre-registered X31 outcomes (cases9)",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S09 specification the checks are read from (§11, §13, §14, "
                "§18)",
            },
        ],
        "limitations": [
            *limitations_of_the_spec(document_text),
            *found_limitations(entries, record),
        ],
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
    parser.add_argument("--out", type=Path, help="default: evidence/S09/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = arguments.commit or git("rev-parse", "HEAD")
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S09" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
