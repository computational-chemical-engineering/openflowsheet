"""Generate `evidence/S05/<commit>/manifest.json` by running, not by transcribing. S05.

Spec `docs/derivations/S05-IAPWS95-spec.md` §12 is the check list and §6.1 the assertion table.
Everything recorded is produced here, at the checked-out commit (the script refuses to run when
`HEAD` is not `--commit` or when a tracked source, test, script, schema or derivation file
differs from it; S01's rule):

1. **The S05 tests** (`tests/test_s05_*.py`, one `pytest --junitxml` run). A test cites the
   assertions its function name carries (`test_a22_…` cites A22). `S05.Axx` passes only if at
   least one node cites it and every node citing it passed: a failure, an error, a skip or an
   expected failure (a strict xfail holding a measured miss) leaves it `fail`. A26's wheel half
   runs with `OFS_S05_BUILD_PYTHON`, a scratch venv holding T08.A43's pinned setuptools that this
   script builds (a skipped wheel node leaves A26 `fail`).
2. **The reference generator's `--check`** (§11: about 10 minutes; its output lines recorded).
   A27 passes only if its nodes passed and this run exited 0.
3. **The mutation battery** (`scripts/s05_mutations.py`, A29), its logs and summary under
   `evidence/S05/<commit>/artifacts/`; A29 passes only if its nodes passed and the battery did,
   and its value lists every mutation, the assertion that caught it and the log's SHA-256.
4. **`ruff check`, `ruff format --check`** on S05's files and **`mypy`** (the project's own
   configuration, no arguments).

`s05_crosscheck.py --check` is the design lane's (scratch venv with CoolProp and iapws); it is not
re-run here, and its committed output is recorded by hash with the commit that wrote it.
`scripts/gate.sh` is not run here (it runs once before merge): its check is `unsupported`.
`status` is computed, never written: `tested` iff every assertion A01–A30 and the generator,
ruff, format and mypy checks pass; otherwise `implemented`. Both review fields stay `pending`.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s05_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
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

SPEC = ROOT / "docs" / "derivations" / "S05-IAPWS95-spec.md"
SCRIPTS = ROOT / "docs" / "derivations" / "scripts"
REFERENCE = SCRIPTS / "s05_reference.json"
GENERATOR = SCRIPTS / "s05_reference.py"
CROSSCHECK = SCRIPTS / "s05_crosscheck.json"
COEFFICIENTS = ROOT / "benchmarks" / "s05" / "iapws95_coefficients.json"
MODULE = ROOT / "src" / "openflowsheet" / "thermo" / "iapws95.py"
DECISIONS = ROOT / "docs" / "C10_DECISIONS.md"
#: The source files S05 added or changed.
SOURCES = ("src/openflowsheet/thermo/iapws95.py",)
SCRIPT_FILES = ("scripts/s05_evidence_manifest.py", "scripts/s05_mutations.py")
ASSERTIONS = tuple(f"A{index:02d}" for index in range(1, 31))
REQUIRED_CHECKS = ("S05.generator", "S05.ruff", "S05.format", "S05.mypy")
#: An assertion id in a test function's name: `_aNN`, then `_` or the end.
CITED = re.compile(r"(?:^|_)a(\d{2})(?=_|$)")

#: The U02 limitation; T08 C3 requires its harvest note to name the id and library-only.
LIBRARY_ONLY = (
    "`iapws95-v1` is library-only (R-568, R-569): it is not in revision_binding.SELECTABLE_BASES, "
    "so no revision can select it and no development case becomes runnable (U02); it is "
    "registered in the T08 envelope's LIBRARY_ONLY_PROVIDERS and its scanned_providers (spec §8 "
    "F-2). Coverage counts are unchanged."
)
#: Ruling 8 of docs/reviews/S05-review.md (R-599; spec §14, §12): the rights statement.
RIGHTS = (
    "Rights (C10-Q1, R-599): the IAPWS terms of use for R6-95 were not read (iapws.org refused, "
    "2026-10-22); the rights row is `unresolved`. benchmarks/s05/iapws95_coefficients.json is "
    "unpackaged (A26), so `iapws95-v1` runs only from a source checkout; Tables 6-8 are not "
    "compared; ADR 0045 remains Proposed. There is no `released` status and no wheel carrying the "
    "coefficients until C10-Q1 is answered, and `reviewed` would cover numerics only, not rights."
)
#: Spec §12's limitations, with the cross-check's provenance (§12 `commands`).
SPEC_LIMITATIONS = (
    RIGHTS,
    LIBRARY_ONLY,
    "The R6-95(2018) Tables 6-8 are not compared (C10-Q1, spec §10 Q-1): the coefficients and the "
    "admitted values equal two independent transcriptions (CoolProp 8.0.0, iapws 1.5.5) and a "
    "50-digit evaluation of the committed transcription; a transcription error shared by both "
    "would pass every assertion. This is numerical verification of an implementation against a "
    "formulation, not empirical validation (spec §9).",
    "The coefficient file benchmarks/s05/iapws95_coefficients.json is not packaged (R-594, "
    "C10-Q1): no PACKAGED entry covers benchmarks/s05/ and a built wheel holds no copy (A26), so "
    "`iapws95-v1` runs only from a source checkout.",
    "The near_critical box, T in (647.0, 648.0) K and P in [2.20e7, 2.22e7] Pa, is refused "
    "near_critical for both phases and the flash (spec §4.2 step 1); states there are not "
    "evaluated.",
    "The saturation band is eps_sigma = 1e-6 in ln(P/p_sigma) (spec §4.2 step 4): both phases are "
    "answered inside it, metastable states beyond it are refused phase_not_stable, and a TP flash "
    "inside it is refused tp_flash_degenerate.",
)


def crosscheck_limitation() -> str:
    written = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", shown(CROSSCHECK)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return (
        "s05_crosscheck.py --check (CoolProp 8.0.0, iapws 1.5.5) runs only in the design lane's "
        f"scratch venv and is not re-run by the build lane; its committed output "
        f"{shown(CROSSCHECK)} (SHA-256 {sha256_file(CROSSCHECK)}) was last written at "
        f"{written}, and s05_reference.py --check executes the admission against it (spec §7 C3)."
    )


# -- the specification ---------------------------------------------------------------------------


def assertion_table(document: str) -> dict[str, tuple[str, str, str]]:
    """§6.1's table: id → (assertion, expectation, tolerance)."""
    start = document.index("### 6.1 ")
    body = document[start : document.index("### 6.2 ", start)]
    rows: dict[str, tuple[str, str, str]] = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        if len(cells) == 4 and re.fullmatch(r"A\d{2}", cells[0]):
            rows[cells[0]] = (cells[1], cells[2], cells[3])
    if tuple(rows) != ASSERTIONS:
        raise SystemExit(f"§6.1's ids are {list(rows)}, not A01-A30")
    return rows


# -- the tests -----------------------------------------------------------------------------------


def cited(node: str) -> tuple[str, ...]:
    """The assertion ids a test node cites, from its function name (parameters ignored)."""
    name = node.rsplit("::", 1)[-1].split("[", 1)[0]
    return tuple(f"A{number}" for number in CITED.findall(name))


def _verdict(citing: Sequence[Node]) -> tuple[str, dict[str, Any]]:
    not_passed = [
        {"node": text(item.node), "outcome": item.outcome, "message": text(item.message[:600])}
        for item in citing
        if item.outcome != "passed"
    ]
    value = {
        "judged_by": "tests",
        "nodes": len(citing),
        "outcomes": dict(sorted(Counter(item.outcome for item in citing).items())),
        "selectors": [text(item.node) for item in citing],
        "not_passed": not_passed,
    }
    return ("pass" if citing and not not_passed else "fail"), value


def _import_provider() -> Any:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from openflowsheet.thermo import iapws95

    return iapws95


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]],
    tests: Sequence[Node],
    extra: Mapping[str, tuple[bool, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """One check per assertion; `extra` adds a measured half (A26, A27, A29) that must also pass."""
    s05 = [item for item in tests if item.node.startswith("tests/test_s05_")]
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        result, value = _verdict([item for item in s05 if identifier in cited(item.node)])
        if identifier in extra:
            passed, measured = extra[identifier]
            value = {**value, "measured": measured}
            result = "pass" if result == "pass" and passed else "fail"
        assertion, expected, tolerance = rows[identifier]
        entries.append(
            check(f"S05.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


# -- the measured halves -------------------------------------------------------------------------


def build_python(work: Path) -> tuple[str, str]:
    """A scratch venv with T08.A43's setuptools pin, for A26's wheel (network: PyPI)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import t08_dist

    python, version = t08_dist.build_environment(work / "build-venv", t08_dist.SETUPTOOLS)
    return str(python), version


def battery(artifacts: Path) -> tuple[bool, dict[str, Any], Any]:
    import s05_mutations

    entry = run(
        [sys.executable, str(ROOT / "scripts" / "s05_mutations.py"), "--logs", str(artifacts)]
    )
    summary_path = artifacts / "s05-mutations.json"
    summary = json.loads(summary_path.read_text("utf-8")) if summary_path.is_file() else {}
    measured = {
        "cmd": entry.cmd,
        "exit_code": entry.exit_code,
        "verdict": entry.stdout.strip().splitlines()[-1:] if entry.stdout.strip() else [],
        "control": summary.get("control"),
        "mutations": [
            {key: item[key] for key in ("id", "mutation", "assertion", "caught", "log_sha256")}
            | {"log": shown(artifacts / item["log"])}
            for item in summary.get("mutations", ())
        ],
        "summary_sha256": sha256_file(summary_path) if summary_path.is_file() else None,
        "registered": len(s05_mutations.MUTATIONS),
    }
    return entry.exit_code == 0 and summary.get("result") == "pass", measured, entry


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every registered assertion and every required check passes."""
    required = {f"S05.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        "requirements is empty: the schema takes D/A requirement ids and none lists S05; ADR 0045 "
        "(IAPWS-95 as a library-only provider) is Proposed, and spec §8's F-1 (ADR 0001 D5 and "
        "interfaces-frozen.md gain IAPWS95-ref-v1) is the design lane's amendment, not made here.",
        "scripts/gate.sh was not run by this generator (it runs once before merge into main); "
        "S05.gate is unsupported here.",
        "Review: the design lane's reviewer pass (docs/reviews/S05-review.md, R-595…R-599) ruled "
        "WO-S05-1's and WO-S05-2's questions, and WO-S05-3 applied the rulings; the reviewer's "
        "check of the WO-S05-3 diff and the human numerical and process-model review are pending, "
        "and this manifest claims neither. WO-S05-3's open QUESTION in docs/C10_DECISIONS.md "
        "(R-595 clause 2: the floor clause tested before the bracket safeguard) goes to that "
        "check.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] == "S05.gate":
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
                "docs/C10_DECISIONS.md)"
            )
        )
    return items


def build(commit: str) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    document = SPEC.read_text(encoding="utf-8")
    rows = assertion_table(document)
    artifacts = ROOT / "evidence" / "S05" / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s05-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(shown(path) for path in (ROOT / "tests").glob("test_s05_*.py"))
    lint = [*SOURCES, *tests, *SCRIPT_FILES, shown(GENERATOR)]

    with tempfile.TemporaryDirectory(prefix="s05-build-") as work:
        builder, setuptools = build_python(Path(work))
        os.environ["OFS_S05_BUILD_PYTHON"] = builder
        try:
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
            }
        finally:
            del os.environ["OFS_S05_BUILD_PYTHON"]
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")
    runs["tests"] = dataclasses.replace(
        runs["tests"],
        cmd=f"OFS_S05_BUILD_PYTHON=build-venv/bin/python {runs['tests'].cmd} "
        f"(build-venv: a scratch venv with setuptools {setuptools})",
    )
    runs["S05.generator"] = run([python, str(GENERATOR), "--check"], pythonpath=True)
    mutations_passed, mutations, runs["mutations"] = battery(artifacts)
    runs["S05.ruff"] = run([str(tools / "ruff"), "check", *lint])
    runs["S05.format"] = run([str(tools / "ruff"), "format", "--check", *lint])
    runs["S05.mypy"] = run([str(tools / "mypy")], pythonpath=True)

    generator = runs["S05.generator"]
    provider = _import_provider()
    identities = provider.Iapws95Provider().describe()
    extra = {
        "A26": (True, {"wheel_built_with_setuptools": setuptools}),
        "A27": (
            generator.exit_code == 0,
            {
                "cmd": generator.cmd,
                "exit_code": generator.exit_code,
                "output": [text(line) for line in generator.stdout.strip().splitlines()[-2:]],
            },
        ),
        "A29": (mutations_passed, mutations),
        "A24": (
            True,
            {
                "implementation_sha256": identities.implementation_sha256,
                "data_sha256": identities.data_sha256,
            },
        ),
    }
    entries = assertion_checks(rows, nodes(junit), extra)
    tool_text = {
        "S05.generator": "§11/§12: s05_reference.py --check re-derives every claim and "
        "byte-compares s05_reference.json",
        "S05.ruff": "ruff check is clean on S05's files",
        "S05.format": "ruff format --check is clean on S05's files",
        "S05.mypy": "mypy (the project's configuration) is clean",
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
    entries.append(
        check(
            "S05.gate",
            "§12: scripts/gate.sh passes before merge",
            "unsupported",
            "not run by this generator; the full gate runs once before merge (CLAUDE.md)",
        )
    )

    manifest: dict[str, Any] = {
        "work_package": "S05",
        "commit": commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "S05 acceptance: docs/derivations/S05-IAPWS95-spec.md §6.1 (A01-A30) "
            "against docs/derivations/scripts/s05_reference.json, check list §12",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S05 test run (ignored; kept by hash)",
            },
            {
                "path": shown(artifacts / "s05-mutations.json"),
                "sha256": mutations["summary_sha256"] or "0" * 64,
                "description": "the A29 battery's summary; its logs sit beside it (ignored)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "the design lane's 50-digit reference values (ref)",
            },
            {
                "path": shown(CROSSCHECK),
                "sha256": sha256_file(CROSSCHECK),
                "description": "the design lane's cross-check record (CoolProp 8.0.0, iapws "
                "1.5.5), not re-run by the build lane",
            },
            {
                "path": shown(COEFFICIENTS),
                "sha256": sha256_file(COEFFICIENTS),
                "description": "the provider's coefficient file (data_sha256; not packaged)",
            },
            {
                "path": shown(MODULE),
                "sha256": sha256_file(MODULE),
                "description": "the iapws95-v1 provider module (implementation_sha256)",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S05 specification the checks are read from (§6.1, §12)",
            },
        ],
        "limitations": [*SPEC_LIMITATIONS, crosscheck_limitation(), *found_limitations(entries)],
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
    parser.add_argument("--out", type=Path, help="default: evidence/S05/<commit>/manifest.json")
    arguments = parser.parse_args()
    commit = (
        arguments.commit
        or subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    manifest = build(commit)
    out = arguments.out or ROOT / "evidence" / "S05" / commit / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["checks"] if entry["result"] == "pass")
    print(
        f"{shown(out)}: status {manifest['status']}, {passed}/{len(manifest['checks'])} checks pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
