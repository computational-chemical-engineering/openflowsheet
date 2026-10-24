"""Generate `evidence/S03/<commit>/manifest.json` by running, not by transcribing. S03 (WO-S03-4).

Spec `docs/derivations/S03-spec.md` §13 (as amended by §17.10 and §18.8) is the check list.
Everything recorded is produced here, at the checked-out commit (the script refuses to run when
`HEAD` is not `--commit` or when a tracked source, test, script, schema, derivation or S03 record
file differs from it; S01's rule):

1. **The S03 tests and the suites A15 names** (`tests/test_s03_*.py`, `tests/test_s01_*.py`,
   `tests/test_s02_*.py`, `tests/test_s06_*.py`, one `pytest --junitxml` run). An S03 test cites the
   assertions its function name carries (`test_a08_…` cites A08). `S03.Axx` passes only if at least
   one S03 node cites it and every node citing it passed. **A15** ("S01's, S02's and S06's suites
   pass unchanged") is judged by every S01, S02 and S06 node. **A17** is the `verdict` agent's
   document `docs/reviews/S03-verdicts.md` (WO-S03-5): present, or `fail`.
2. **The reference generator's `--check`** (§13: 4577 claims, both JSON files byte-identical).
3. **The comparison's `--check`**: `comparison.json` and `SHA256SUMS` recompute identically.
4. **`ruff check`, `ruff format --check`** on S03's files.
5. **The comparison record** §13 lists: each tool's environment fingerprint, the qualification and
   comparison commits (ancestry checked), the SHA-256 of every committed record and of
   `comparison.json`, the DWSIM rung per case, each pair's level (IDAES with its position) and
   classification, §17.5's table with the X31 count, each control's classification and PC-LI's
   tool-model distance.

`scripts/gate.sh` and CI on both architectures are not run here (they run once before merge):
their checks are `unsupported`. `status` is computed, never written: `tested` iff every registered
assertion check (A01–A17), the generator, the comparison, ruff and format checks pass; otherwise
`implemented`. Both review fields stay `pending`; `reviewed` is the `reviewer`'s. The limitations
are §14's items verbatim, §17.11's and §18.9's, then what this run found.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s03_evidence_manifest.py [--commit SHA] [--out PATH]
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
import s03_reference_comparison as comparison  # noqa: E402
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

SPEC = ROOT / "docs" / "derivations" / "S03-spec.md"
REFERENCE = comparison.TWIN_PATH
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s03_reference.py"
VERDICTS = ROOT / "docs" / "reviews" / "S03-verdicts.md"
#: The source files S03 changed (S11, WO-S03-1).
SOURCES = (
    "src/openflowsheet/models/syn001/cascade.py",
    "src/openflowsheet/models/syn001/column.py",
)
SCRIPTS = (
    "scripts/s03_reference_comparison.py",
    "scripts/s03_references_ours.py",
    "scripts/s03_evidence_manifest.py",
)
#: §11's ids, A01–A17 (amended in place by §17.9 and §18.7).
ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 18))
REQUIRED_CHECKS = ("S03.generator", "S03.comparison", "S03.ruff", "S03.format")
CLAIMS = 4577
#: The suites A15 names.
A15_SUITES = ("tests/test_s01_", "tests/test_s02_", "tests/test_s06_")


def refuse_unless_measuring(commit: str) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != commit:
        raise SystemExit(f"HEAD is {head}, not {commit}: check the commit out to measure it")
    dirty = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            *CLEAN_PATHS,
            "benchmarks/s03",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if dirty:
        raise SystemExit(f"tracked files differ from {commit}:\n{dirty}")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


# -- the specification ---------------------------------------------------------------------------


def section(document: str, heading: str) -> str:
    """The body under the heading that starts with `heading` (`## 14.`, `### 17.11`)."""
    level = heading.split(" ", 1)[0]
    match = re.search(
        rf"^{re.escape(heading)} .*?$(.*?)(?=^#{{2,{len(level)}}} |\Z)", document, re.M | re.S
    )
    if match is None:
        raise SystemExit(f"{SPEC.name} has no {heading}")
    return match.group(1)


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
    """§17.9's and §18.7's changes per id (§11's rows stand amended by them)."""
    out: dict[str, list[str]] = {}
    for heading in ("### 17.9", "### 18.7"):
        for line in section(document, heading).splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
            if len(cells) == 2 and re.fullmatch(r"A\d{2}", cells[0]):
                out.setdefault(cells[0], []).append(f"{heading[4:]}: {cells[1]}")
    return {k: " ".join(v) for k, v in out.items()}


def limitations_of_the_spec(document: str) -> list[str]:
    items = bullets(section(document, "## 14."))
    for heading in ("### 17.11", "### 18.9"):
        found = bullets(section(document, heading))
        if not found:
            raise SystemExit(f"{heading} lists no item")
        items += [f"{heading[4:]}: {item}" for item in found]
    return items


# -- the tests -----------------------------------------------------------------------------------


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]], amended: Mapping[str, str], tests: Sequence[Node]
) -> list[dict[str, Any]]:
    s03 = [item for item in tests if item.node.startswith("tests/test_s03_")]
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        if identifier == "A15":
            suites = [item for item in tests if item.node.startswith(A15_SUITES)]
            result, value = _verdict(suites)
            del value["selectors"]
            value = {**value, "judged_by": "the S01, S02 and S06 suites"}
        elif identifier == "A17":
            present = VERDICTS.is_file()
            result = "pass" if present else "fail"
            value = {
                "judged_by": "the verdict agent's document (WO-S03-5)",
                "path": shown(VERDICTS),
                "present": present,
                "sha256": sha256_file(VERDICTS) if present else None,
            }
        else:
            result, value = _verdict([item for item in s03 if identifier in cited(item.node)])
        assertion, expected, tolerance = rows[identifier]
        if identifier in amended:
            assertion = f"{assertion} [amended: {amended[identifier]}]"
        entries.append(
            check(f"S03.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


# -- the comparison record (§13's list) ----------------------------------------------------------


def comparison_record(document: Mapping[str, Any]) -> dict[str, Any]:
    qualification = {
        tool: comparison.load_json(comparison.QUALIFICATION / f"{tool.lower()}.json")
        for tool in comparison.TOOLS
    }
    table_commit = git("log", "-1", "--format=%H", "--", shown(comparison.TABLE))
    ancestry = {
        commit: subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, table_commit], cwd=ROOT, check=False
        ).returncode
        == 0
        for commits in comparison.QUALIFICATION_COMMITS.values()
        for commit in commits
    }
    sums = {}
    for line in comparison.SUMS.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    pairs = {}
    for r in document["rows"]:
        entry: dict[str, Any] = {"classification": r["label"], "rule": r["rule"]}
        if "level" in r:
            entry["level"] = r["level"]
        if "position" in r:
            entry["position"] = r["position"]
        if "rung" in r:
            entry["rung"] = r["rung"]
        pairs[f"{r['case']}/{r['tool']}"] = entry
    x31 = document["x31"]
    return {
        "environment_fingerprints": {
            tool: q["environment_fingerprint"] for tool, q in qualification.items()
        },
        "qualification_commits": comparison.QUALIFICATION_COMMITS,
        "comparison_commit": table_commit,
        "qualification_commits_are_ancestors": ancestry,
        "record_sha256": sums,
        "dwsim_rung_selected": {
            "uniform": qualification["DWSIM"]["selection"].get("uniform"),
            "per_case": {
                k.split("/")[0]: v["rung"]
                for k, v in pairs.items()
                if k.endswith("/DWSIM") and "rung" in v
            },
        },
        "pairs": pairs,
        "x31": {
            "clause": x31["clause"],
            "cases_with_two_references": x31["cases_with_two_references"],
            "cases": {
                c: {
                    "row": v["row"],
                    "outcome": v["outcome"],
                    "classes": {t: p["class"] for t, p in v["pairs"].items()},
                }
                for c, v in x31["cases"].items()
            },
            "inverse_kinds": {
                k: {"case": v["case"], "row": v["row"], "outcome": v["outcome"]}
                for k, v in x31["inverse_kinds"].items()
            },
        },
        "controls": document["controls"]["per_tool"],
        "control_tool_model_distance": {
            k: {kk: vv for kk, vv in v.items() if kk != "classification"}
            for k, v in document["control_tool_model_distance"].items()
        },
        "comparison_stopped": document["comparison_stopped"],
    }


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    required = {f"S03.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]], record: Mapping[str, Any]) -> list[str]:
    x31 = record["x31"]
    lost = [
        f"{k}: {v['classification']}"
        for k, v in record["pairs"].items()
        if v["classification"].startswith(("NOT_COMPARABLE", "DISAGREE"))
    ]
    items = [
        "requirements lists D19 only: X31 (the reference clause) is a requirement id outside "
        "the manifest schema's D/A pattern. Its verdict and D19's evidence fields in "
        "docs/requirements.yaml are filled from the verdict agent's document "
        "(docs/reviews/S03-verdicts.md, A17), not by the build lane (§13).",
        f"X31 reference clause as §17.5's table classifies it mechanically: {x31['clause']}; "
        f"{x31['cases_with_two_references']} of 4 cases with two references. Per case: "
        + "; ".join(f"{c} row {v['row']} ({v['outcome'][:120]})" for c, v in x31["cases"].items())
        + ". The recorded verdict is A17's.",
        "Every NOT_COMPARABLE and DISAGREE pair, with its reason: " + " || ".join(lost),
        "scripts/gate.sh and CI on both architectures were not run by this generator (they run "
        "once before merge into main); S03.gate and S03.ci are unsupported here.",
        "Review: the package's single reviewer pass (WO-S03-1 to WO-S03-4, WO-S03-2b) and the "
        "human numerical and process-model review are pending; this manifest claims neither.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] in ("S03.gate", "S03.ci"):
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
    artifacts = ROOT / "evidence" / "S03" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s03-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        shown(path)
        for pattern in ("test_s03_*.py", "test_s01_*.py", "test_s02_*.py", "test_s06_*.py")
        for path in (ROOT / "tests").glob(pattern)
    )
    s03_tests = [path for path in tests if Path(path).name.startswith("test_s03_")]
    lint = [*SOURCES, *SCRIPTS, *s03_tests, shown(GENERATOR)]

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
        "S03.generator": run([python, str(GENERATOR), "--check"]),
        "S03.comparison": run(
            [python, "scripts/s03_reference_comparison.py", "--check"], pythonpath=True
        ),
        "S03.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S03.format": run([str(tools / "ruff"), "format", "--check", *lint]),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")

    entries = assertion_checks(rows, amended, nodes(junit))
    generator_ok = runs["S03.generator"].exit_code == 0 and bool(
        re.search(rf"^{CLAIMS} claims passed$", runs["S03.generator"].stdout, re.M)
    )
    tool_text = {
        "S03.generator": (
            f"§13: s03_reference.py --check re-derives every claim ({CLAIMS}) and "
            "byte-compares both JSON files",
            generator_ok,
        ),
        "S03.comparison": (
            "§8, A10: comparison.json and SHA256SUMS recompute identically from "
            "the committed records",
            runs["S03.comparison"].exit_code == 0,
        ),
        "S03.ruff": ("§13: ruff check is clean on S03's files", runs["S03.ruff"].exit_code == 0),
        "S03.format": (
            "§13: ruff format --check is clean on S03's files",
            runs["S03.format"].exit_code == 0,
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
            "S03.comparison_record",
            "§13's list: fingerprints, qualification and comparison commits (ancestry), record "
            "hashes, the DWSIM rung, each pair's level/position and classification, §17.5's "
            "table and X31 count, each control's classification and tool-model distance",
            "pass" if all(record["qualification_commits_are_ancestors"].values()) else "fail",
            record,
        )
    )
    entries.append(
        check(
            "S03.gate",
            "§13: scripts/gate.sh passes before the merge",
            "unsupported",
            "not run by this generator; it runs once before merge",
        )
    )
    entries.append(
        check(
            "S03.ci",
            "§13: CI is green on both architectures",
            "unsupported",
            "not measured by this generator; checked before merge",
        )
    )

    manifest: dict[str, Any] = {
        "work_package": "S03",
        "commit": commit,
        "requirements": ["D19"],
        "status": status(entries),
        "inputs": {
            "case_id": "S03 acceptance: docs/derivations/S03-spec.md §11 (A01–A17, amended by "
            "§17.9 and §18.7) against docs/derivations/scripts/s03_reference.json and the "
            "committed tool records, check list §13",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S03, S01, S02 and S06 test run (ignored; kept "
                "by hash)",
            },
            {
                "path": shown(comparison.TABLE),
                "sha256": sha256_file(comparison.TABLE),
                "description": "the classification of every (case, tool) pair (WO-S03-4)",
            },
            {
                "path": shown(comparison.SUMS),
                "sha256": sha256_file(comparison.SUMS),
                "description": "SHA-256 of every committed qualification and tool record and of "
                "comparison.json",
            },
            *(
                {
                    "path": shown(p),
                    "sha256": sha256_file(p),
                    "description": f"{p.stem.upper()} qualification record (levels, attempts, "
                    "structural inspections, selection)",
                }
                for p in sorted(comparison.QUALIFICATION.glob("*.json"))
            ),
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "the design lane's 50-digit twin values and control "
                "discriminations (ref)",
            },
            {
                "path": shown(comparison.CASES_PATH),
                "sha256": sha256_file(comparison.CASES_PATH),
                "description": "the registered inputs and tool settings (cases)",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S03 specification the checks are read from (§11, §13, §14, "
                "§17, §18)",
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
    parser.add_argument("--out", type=Path, help="default: evidence/S03/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = arguments.commit or git("rev-parse", "HEAD")
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S03" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
