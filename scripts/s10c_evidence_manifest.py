"""Generate `evidence/S10c/<commit>/manifest.json` by running, not by transcribing. S10-C (WO-5).

The specification `docs/derivations/S10C-spec.md` (WO-S, with Amendment 1 §11) is the check list:
§6's numbered assertions S10C.A01–A61, judged against `benchmarks/s10c/reference_values.yaml`;
the design note `docs/derivations/S10C-design.md` §6 adds the gates. Everything recorded is produced
here, at the checked-out commit (the script refuses to run when `HEAD` is not `--commit` or when a
tracked source, test, script, schema or derivation file differs from it; S01's rule):

1. **The S10-C tests and the suites below them** (`tests/test_s10c_*.py`; S01, S02, S06, S03, S08,
   T05/T05b and S10; and the older identity tests of the flowsheet paths, review F6; one
   `pytest --junitxml` run). An S10-C test cites the assertions its function name starts with
   (`test_a40_a45_…` cites A40 and A45); tests named otherwise cite through `CITATIONS`, an explicit
   map read from their docstrings. `S10C.Axx` passes only if at least one node cites it and every
   node citing it passed. **A07** is judged by G1 alone; **A15** (recorded, not gated) by the
   `evaluations` this script measures per PH target; **A60** by the generator's `--check`.
   `S10C.suite` requires every `test_s10c_` node to pass (the tests that cite no assertion too),
   `S10C.suites` every node of the lower suites, `S10C.G1-flowsheets` every node of the identity
   tests (F6).
2. **G1**, `scripts/s10c_identity.py` against the merge base `ffcb387f` (in a detached worktree the
   script creates and removes): `S10C-IDENTITY PASS n=<N> changed=[]`.
3. **G2**, structure: `git diff --stat $(git merge-base main HEAD)..HEAD` is empty over §6 G2's
   frozen paths, and under `tests/` only new files and the edits G2 allows are changed.
4. **A60**, the reference generator's `--check` (`s10c_reference.py`: every claim holds and the YAML
   is byte-identical).
5. **`ruff check`, `ruff format --check`** on S10-C's files and **`mypy`** (the project's own
   configuration).

`scripts/gate.sh` and CI on both architectures (G10) are not run here (they run once before merge):
their checks are `unsupported`. G9's wall times were measured in WO-4 and are recorded in the build
log, not here. `status` is computed, never written: `tested` iff every assertion and every required
check passes; otherwise `implemented`. Both review fields stay `pending`; `reviewed` is the design
lane's `reviewer`'s. The limitations are spec §0's "does NOT establish" items verbatim, then what
this run and the review found.

The work package id is `S10c`: the frozen manifest schema admits `^[PKTMSR][0-9]{2}[a-z]?$`, and the
evidence directory is named after it (T05b's and M07a's precedent; docs/S10C_DECISIONS.md W5-1).

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s10c_evidence_manifest.py [--commit SHA] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
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
from s02_evidence_manifest import _verdict, section  # noqa: E402

PACKAGE = "S10c"
SPEC = ROOT / "docs" / "derivations" / "S10C-spec.md"
NOTE = ROOT / "docs" / "derivations" / "S10C-design.md"
ADR = ROOT / "docs" / "adr" / "0049-s10c-composition-dependent-k.md"
REFERENCE = ROOT / "benchmarks" / "s10c" / "reference_values.yaml"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "s10c_reference.py"
DECISIONS = ROOT / "docs" / "S10C_DECISIONS.md"
REVIEW = ROOT / "docs" / "reviews" / "S10C-review.md"
#: The source files S10-C added or changed (WO-1 to WO-4).
SOURCES = tuple(
    f"src/openflowsheet/{name}.py"
    for name in (
        "models/syn001/cascade",
        "models/syn001/column",
        "models/syn001/column_blocks",
        "models/syn001/column_solve",
        "models/syn001/equilibrium_form",
        "models/syn001/gamma_phi",
        "models/syn001/gamma_phi_blocks",
        "models/syn001/ph_kernel",
        "models/syn001/saturation_band",
        "models/syn001/tp_state",
        "orchestrator/region",
    )
)
SCRIPTS = (
    "scripts/s10c_identity.py",
    "scripts/s10c_band_point_probe.py",
    "scripts/s10c_evidence_manifest.py",
)
#: §6's assertion ids, in the table's order (spec §0: "S10C.A01–A61", numbered with gaps).
ASSERTIONS = (
    *(f"A{index:02d}" for index in range(1, 8)),
    *(f"A{index:02d}" for index in range(10, 16)),
    "A20",
    "A21",
    "A22",
    *(f"A{index:02d}" for index in range(30, 37)),
    *(f"A{index:02d}" for index in range(40, 46)),
    *(f"A{index:02d}" for index in range(50, 57)),
    "A60",
    "A61",
)
#: Amendment 1 E3 rewords these rows (§11; R-779); the rewording is quoted in the check.
AMENDED = {
    "A02": "the number m of temperature solves gamma_phi.band_point makes (_Point.temperature "
    "calls: 1 at β = 0); BandTemperature carries no m; a test counts the solves with a spy, and "
    "no production field is added",
    "A44": "A41 fails, or solve_column does not return an accepted CONVERGED answer (a typed "
    "failure, or AcceptanceDefectError from S02 §8 / S08 §5.5 item 6)",
}
#: The non-assertion checks `status` also requires.
REQUIRED_CHECKS = (
    "S10C.suite",
    "S10C.suites",
    "S10C.G1",
    "S10C.G1-flowsheets",
    "S10C.G2",
    "S10C.ruff",
    "S10C.format",
    "S10C.mypy",
)
#: The S10-C tests whose names cite no assertion, and what their docstrings say they evidence.
CITATIONS: dict[str, tuple[str, ...]] = {
    "tests/test_s10c_ph_kernel.py::test_g4_ph_target_is_the_registered_answer": (
        "A10",
        "A13",
        "A14",
    ),
    "tests/test_s10c_ph_kernel.py::test_g4_band_route_compositions_match_the_reference": ("A10",),
    "tests/test_s10c_ph_kernel.py::test_g4_single_phase_answer_is_exact": ("A11",),
    "tests/test_s10c_ph_kernel.py::test_g4_target_outside_the_domain_is_refused_typed": (
        "A12",
        "A14",
    ),
    "tests/test_s10c_ph_kernel.py::test_e2_states_are_the_registered_thirteen": ("A20",),
    "tests/test_s10c_ph_kernel.py::test_g5_e2_state_is_solved_on_the_band_route": ("A20", "A21"),
    "tests/test_s10c_ph_kernel.py::test_m3_the_tp_flash_bracket_route_fails_g5": ("A22",),
    "tests/test_s10c_columns.py::test_a41_the_state_is_the_registered_root": ("A43",),
    "tests/test_s10c_refusals.py::test_the_admitted_column_passes_validation": ("A45",),
    # S10C.A56 is S03's A04 test as amended by WO-3 (`tests/test_s03_s11_refusal.py:129`).
    "tests/test_s03_s11_refusal.py::test_a04_s11_refuses_every_other_provider_before_any_evaluation": (  # noqa: E501
        "A56",
    ),
}
#: The suites S10-C must leave passing (the acceptance list of WO-4 and the review).
LOWER_SUITES = (
    "test_s01_",
    "test_s02_",
    "test_s06_",
    "test_s03_",
    "test_s08_",
    "test_t05",
    "test_s10_",
)
#: Review F6: the flowsheet paths (K02–T04 units, pr-c1-v1 flowsheets) are held by these
#: identity tests, not by G1; `test_t05*_identity.py` run with `test_t05` above.
FLOWSHEET_IDENTITY = (
    "test_t02_identity.py",
    "test_t06_identity.py",
    "test_t06_w14_identity.py",
    "test_t07_identity.py",
    "test_t08_w1_d2_replay_identity.py",
    "test_t08_w1_identity_substitution.py",
    "test_t08_w2_edge_identity.py",
)
#: §6 G2: the paths S10-C must not touch.
FROZEN = (
    "src/openflowsheet/thermo",
    "src/openflowsheet/compile",
    "src/openflowsheet/numerics",
    "src/openflowsheet/verify",
    "src/openflowsheet/application",
    "src/openflowsheet/models/c1",
    "schemas",
)
#: §6 G2: the existing test files S10-C may edit (the S03 A04 amendment; WO-5's T08 counts).
TEST_EDITS = ("tests/test_s03_s11_refusal.py", "tests/test_m07a_harvest.py")
#: The assertion an S10-C test cites: its name's leading `aNN_` groups (`test_a40_a45_…`).
CITED = re.compile(r"^test_((?:a\d{2}_)+)")
G1_LINE = re.compile(r"^S10C-IDENTITY PASS n=(\d+) changed=\[\]$")
#: `s10c_reference.py --check`'s last line.
GENERATOR_LINE = re.compile(r"^\d+ claims hold; reference_values\.yaml matches$")


# -- the specification ---------------------------------------------------------------------------


def assertion_table(document: str) -> dict[str, tuple[str, str, str]]:
    """§6's rows: id → (assertion, expected, tolerance), exactly `ASSERTIONS`."""
    rows: dict[str, tuple[str, str, str]] = {}
    for line in section(document, 6).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        match = re.fullmatch(r"S10C\.(A\d{2})", cells[0])
        if match and len(cells) == 4:
            rows[match.group(1)] = (cells[1], cells[2], cells[3])
    if tuple(rows) != ASSERTIONS:
        raise SystemExit(f"§6's ids are {list(rows)}, not {list(ASSERTIONS)}")
    return rows


def limitations_of_the_spec(document: str) -> list[str]:
    """§0's numbered "What this document does NOT establish" items verbatim."""
    body = section(document, 0)
    marker = "**What this document does NOT establish.**"
    if marker not in body:
        raise SystemExit("§0 has no 'does NOT establish' list")
    items: list[str] = []
    for line in body[body.index(marker) :].splitlines()[1:]:
        numbered = re.match(r"^\d+\. (.*)$", line)
        if numbered:
            items.append(numbered.group(1).strip())
        elif line.startswith("   ") and items and line.strip():
            items[-1] += " " + line.strip()
    if len(items) != 7:
        raise SystemExit(f"§0 lists {len(items)} items, not 7")
    return items


# -- the tests -----------------------------------------------------------------------------------


def cited(node: str) -> tuple[str, ...]:
    """The assertions a node cites: by its name (S10-C tests only), else by `CITATIONS`."""
    function = node.split("[", 1)[0]
    explicit = CITATIONS.get(function, ())
    if not node.startswith("tests/test_s10c_"):
        return explicit
    match = CITED.match(function.rsplit("::", 1)[-1])
    named = tuple(
        f"A{number}" for number in re.findall(r"a(\d{2})_", match.group(1) if match else "")
    )
    return named + explicit


def assertion_checks(
    rows: Mapping[str, tuple[str, str, str]],
    tests: Sequence[Node],
    special: Mapping[str, tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        if identifier in special:
            result, value = special[identifier]
        else:
            result, value = _verdict([item for item in tests if identifier in cited(item.node)])
        assertion, expected, tolerance = rows[identifier]
        if identifier in AMENDED:
            assertion = f"{assertion} [amended by §11 E3: {AMENDED[identifier]}]"
        entries.append(
            check(f"S10C.{identifier}", assertion, result, value, text(expected), text(tolerance))
        )
    return entries


def suite_check(
    identifier: str, description: str, tests: Sequence[Node], prefixes: Sequence[str]
) -> dict[str, Any]:
    """Every node of the named test files passed, and each prefix has at least one node."""
    chosen = [item for item in tests if item.node.startswith(tuple(f"tests/{p}" for p in prefixes))]
    result, value = _verdict(chosen)
    del value["selectors"]
    per_prefix = {
        prefix.removesuffix("_").removesuffix(".py"): sum(
            1 for item in chosen if item.node.startswith(f"tests/{prefix}")
        )
        for prefix in prefixes
    }
    value = {**value, "judged_by": "tests", "per_file_prefix": per_prefix}
    if not all(per_prefix.values()):
        result = "fail"
    return check(identifier, description, result, value, "every node passed")


# -- the gates -----------------------------------------------------------------------------------


def identity_check(entry: Any) -> dict[str, Any]:
    line = entry.stdout.strip().splitlines()[-1] if entry.stdout.strip() else ""
    passed = entry.exit_code == 0 and G1_LINE.match(line) is not None
    return check(
        "S10C.G1",
        "§6 G1: scripts/s10c_identity.py, SYN-001's column and cascade digests (S08's 52 "
        "configurations) and every ph_state call of the T05/T05b tests, on the merge base "
        "ffcb387f and on this commit; every digest equal",
        "pass" if passed else "fail",
        {"cmd": entry.cmd, "exit_code": entry.exit_code, "line": line},
        "S10C-IDENTITY PASS n=‹N› changed=[]",
    )


def structure_check() -> dict[str, Any]:
    base = subprocess.run(
        ["git", "merge-base", "main", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

    def git(*arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    frozen = git("diff", "--stat", f"{base}..HEAD", "--", *FROZEN)
    tests = git("diff", "--name-status", f"{base}..HEAD", "--", "tests")
    edited = sorted(
        line.split("\t")[-1] for line in tests.splitlines() if line and not line.startswith("A")
    )
    unexpected = [path for path in edited if path not in TEST_EDITS]
    return check(
        "S10C.G2",
        "§6 G2: git diff --stat $(git merge-base main HEAD)..HEAD is empty over thermo, compile, "
        "numerics, verify, application, models/c1 and schemas; in tests/ only new files, the S03 "
        "A04 amendment and WO-5's T08 registration counts",
        "pass" if not frozen and not unexpected else "fail",
        {
            "merge_base": base,
            "paths": list(FROZEN),
            "diff_stat": frozen,
            "edited_tests": edited,
            "unexpected_test_edits": unexpected,
        },
        "empty; edited tests within " + ", ".join(TEST_EDITS),
    )


def recorded_evaluations(commit: str) -> tuple[str, dict[str, Any]]:
    """A15 (recorded, not gated): `evaluations` of `ph_state` per registered PH target, beside the
    generator transcription's `evaluations_measured`."""
    for path in (ROOT / "src", ROOT / "tests"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from test_s10c_ph_kernel import CONTEXT, PH_TARGETS, REAL, VERIFICATION, _document, _write

    from openflowsheet.models.syn001.ph_kernel import ph_state
    from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

    recorded: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as directory:
        ideal = _document(VERIFICATION)
        for entry in ideal["wilson_lambda"]:
            entry["value"] = 1.0
        narrowed = _document(VERIFICATION)
        narrowed["domain"]["T"] = [342.0, 365.0]
        providers = {
            "real": WilsonIdealGasProvider(REAL),
            "verification": WilsonIdealGasProvider(VERIFICATION),
            "ideal": WilsonIdealGasProvider(_write(ideal, Path(directory) / "ideal.yaml")),
            "narrowed": WilsonIdealGasProvider(_write(narrowed, Path(directory) / "narrow.yaml")),
        }
        for key in sorted(PH_TARGETS):
            target = PH_TARGETS[key]
            answer = ph_state(
                providers[target["records"]],
                tuple(target["n"]),
                float(target["P"]),
                float(target["H_target"]),
                CONTEXT,
            )
            recorded[key] = {
                "status": answer.status,
                "evaluations": answer.evaluations,
                "evaluations_measured": target.get("evaluations_measured"),
            }
    return "pass", {
        "judged_by": "recorded, not gated: every registered target returned a PHState",
        "measured_at": commit,
        "targets": recorded,
    }


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every assertion and every required check passes; never `reviewed`."""
    required = {f"S10C.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        "`wilson-ig-v1` has library-level support for the column (solve_column), the PH kernel "
        "(ph_state) and the orchestrator's single-phase admissibility (S10-C); flowsheet "
        "selection is not offered: it stays library-only, not in SELECTABLE_BASES (U02; the T08 "
        "envelope's LIBRARY_ONLY_PROVIDERS keeps it). This restates the earlier S10 manifests' "
        "harvested 'no column, PH-flash or flowsheet claim' for the column and the PH kernel; "
        "those harvest entries are not rewritten (HG(b), R-617; docs/S10C_DECISIONS.md W5-3).",
        "T1–T5 are certified for the committed record sets only (records.real.sha256, "
        "records.verification.sha256) and the test-built copies of spec §5.1, on their declared "
        "T domains; a record file admitted under WILSON-IG-ref-v1 or S10-VER-ref-v1 has P1–P3 "
        "unchecked, and an admission-time check is deferred to the package that makes the "
        "provider selectable in flowsheets (spec §11 E4, R-781).",
        "requirements is empty: neither the design note nor the specification assigns S10-C a "
        "D/A requirement id. S10-C has no package entry in docs/requirements.yaml because the "
        "frozen ledger schema admits only ^[PKTMSR][0-9]{2}$ package ids; the ledger records it "
        "in a comment under S10 (docs/S10C_DECISIONS.md W5-2).",
        "scripts/gate.sh and CI on x86-64 and aarch64 (§6 G10) were not run by this generator "
        "(they run once before merge into main); S10C.gate and S10C.ci are unsupported here. "
        "G9's wall times were measured in WO-4 (docs/S10C_DECISIONS.md, WO-4 run log; review "
        "R-780), not here.",
        "Review: the design lane's one reviewer pass on WO-1 to WO-4 (docs/reviews/S10C-review.md) "
        "set one must-fix (F1: G3 against its registered references, A60, A61) before reviewed; "
        "WO-6 carries it (tests/test_s10c_band_references.py). Whether it is closed is the "
        "reviewer's to judge: the review fields stay pending and the human numerical and "
        "process-model review is pending; this manifest claims neither.",
        "The agreement with the YAML is numerical verification of wilson-ig-v1's equations "
        "against the specification's 50-digit generator (s10c_reference.py, which imports nothing "
        "from src/), not empirical validation; W4-7's Stage-B specification is a build-lane "
        "fixture, not a registered case.",
        "The T08 support envelope's harvest of this manifest follows its generation, in a later "
        "commit.",
    ]
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] in ("S10C.gate", "S10C.ci"):
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
    document = SPEC.read_text(encoding="utf-8")
    rows = assertion_table(document)
    artifacts = ROOT / "evidence" / PACKAGE / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junit = artifacts / "s10c-tests.junit.xml"
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        shown(path)
        for pattern in (
            "test_s10c_*.py",
            *(f"{prefix}*.py" for prefix in LOWER_SUITES),
            *FLOWSHEET_IDENTITY,
        )
        for path in (ROOT / "tests").glob(pattern)
    )
    s10c_tests = [path for path in tests if Path(path).name.startswith("test_s10c_")]
    lint = [*SOURCES, *s10c_tests, *SCRIPTS, shown(GENERATOR)]

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
        "S10C.G1": run([python, str(ROOT / "scripts" / "s10c_identity.py")], pythonpath=True),
        "S10C.A60": run([python, str(GENERATOR), "--check"]),
        "S10C.ruff": run([str(tools / "ruff"), "check", *lint]),
        "S10C.format": run([str(tools / "ruff"), "format", "--check", *lint]),
        "S10C.mypy": run([str(tools / "mypy")], pythonpath=True),
    }
    if not junit.is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests'].exit_code})")

    found = nodes(junit)
    g1 = identity_check(runs["S10C.G1"])
    generator = runs["S10C.A60"]
    generator_line = generator.stdout.strip().splitlines()[-1] if generator.stdout.strip() else ""
    special = {
        "A07": (
            g1["result"],
            {"judged_by": "gate G1 (spec §6: covered by G1)", "G1": g1["value"]["line"]},
        ),
        "A15": recorded_evaluations(commit),
        "A60": (
            "pass" if generator.exit_code == 0 and GENERATOR_LINE.match(generator_line) else "fail",
            {"cmd": generator.cmd, "exit_code": generator.exit_code, "line": generator_line},
        ),
    }
    entries = assertion_checks(rows, found, special)
    entries += [
        suite_check(
            "S10C.suite",
            "every node of tests/test_s10c_*.py passed, including those that cite no assertion "
            "(WO-1's band point, forms, region; M4; the Stage-B fixture)",
            found,
            ("test_s10c_",),
        ),
        suite_check(
            "S10C.suites",
            "the S01, S02, S06, S03, S08, T05/T05b and S10 suites pass",
            found,
            LOWER_SUITES,
        ),
        suite_check(
            "S10C.G1-flowsheets",
            "review F6: the identity tests of the flowsheet paths G1 does not see (K02–T04 units "
            "through tp_state.enthalpy_flow, single_phase_admissible and region._admissible; "
            "pr-c1-v1 flowsheets) pass",
            found,
            FLOWSHEET_IDENTITY,
        ),
        g1,
        structure_check(),
    ]
    tool_text = {
        "S10C.ruff": "ruff check is clean on S10-C's files",
        "S10C.format": "ruff format --check is clean on S10-C's files",
        "S10C.mypy": "mypy (the project's configuration) is clean",
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
        ("S10C.gate", "§6 G10: scripts/gate.sh passes before merge"),
        ("S10C.ci", "§6 G10: CI is green on x86-64 and aarch64 before merge"),
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
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "S10-C acceptance: docs/derivations/S10C-spec.md §6 and §11 (S10C.A01–A61) "
            "against benchmarks/s10c/reference_values.yaml, gates S10C-design §6",
            "case_hash": sha256_file(REFERENCE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": [command(entry) for entry in runs.values()],
        "checks": entries,
        "artifacts": [
            {
                "path": shown(junit),
                "sha256": sha256_file(junit),
                "description": "JUnit report of the S10-C, lower-suite and flowsheet-identity "
                "test run (ignored; kept by hash)",
            },
            {
                "path": shown(REFERENCE),
                "sha256": sha256_file(REFERENCE),
                "description": "WO-S's 50-digit expectations, registered states and tolerances",
            },
            {
                "path": shown(SPEC),
                "sha256": sha256_file(SPEC),
                "description": "the S10-C specification the checks are read from (§0, §6, §11)",
            },
            {
                "path": shown(NOTE),
                "sha256": sha256_file(NOTE),
                "description": "the S10-C design note (§6's gates)",
            },
            {
                "path": shown(ADR),
                "sha256": sha256_file(ADR),
                "description": "ADR 0049, the decision S10-C implements",
            },
            {
                "path": shown(REVIEW),
                "sha256": sha256_file(REVIEW),
                "description": "the design lane's review of WO-1 to WO-4",
            },
            {
                "path": shown(DECISIONS),
                "sha256": sha256_file(DECISIONS),
                "description": "S10-C's build decisions with the measured facts",
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
    parser.add_argument(
        "--out", type=Path, help=f"default: evidence/{PACKAGE}/<commit>/manifest.json"
    )
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
