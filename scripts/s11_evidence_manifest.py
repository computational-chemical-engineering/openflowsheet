"""Generate `evidence/S11/<commit>/manifest.json` by running, not by transcribing. S11 (WO-I2).

The check list is the design note `docs/derivations/S11-design.md` (§6.1 S11.A01–A41, §10's
A24′ and A87–A93, §6.2 gates G1–G8) with the units design `docs/derivations/S11-units-design.md`
(§6.1 S11.A42–A86, §6.2 gates G9–G13; §5.4 amendment 3: I2 records G9–G13 beside G1–G8) and the
rulings `docs/reviews/S11-rulings.md` (§5 row I2). Everything recorded is produced here, at the
checked-out commit (the script refuses to run when `HEAD` is not `--commit` or when a tracked
source, test, script, schema or derivation file differs from it; S01's rule):

1. **The tests**, twice (`pytest --junitxml`): run A in the locked environment (no CoolProp, as
   CI's default job) over the S11 tests, the tests S11 amends on purpose (§8.3), the sample,
   surface, envelope, inventory, W27, S03/S10-C and identity tests it touches; run B, the same
   files with CoolProp 8.0.0 importable (`--coolprop-site`, the `coolprop` extra's wheel in a
   scratch site), for the cases that skip without it. A node's outcome is the worse of the two
   (`failed`/`error` in either fails it; `passed` in either passes it; otherwise `skipped`).
   An S11 test cites the assertions its name starts with (`test_a29_a35_…`; `test_s11_a34_…`
   outside the S11 files); tests named otherwise cite through `CITATIONS`. `S11.Axx` passes only
   if at least one node cites it and every node citing it passed.
2. **G1**, `scripts/s11_identity.py` against `8c34ecb0` (`S11-IDENTITY PASS n=‹N› changed=[]`);
   family C runs every `tests/test_*.py` in both trees and requires every shard to exit 0. The
   S08 and S10-C lines (S11.A23, A85) and the `test_*identity*.py` tests.
3. **The generators' `--check`s**: `t08_support_matrix.py`, `w27_registration_v3.py`,
   `s11_w27_s4.py`, `s11_wilson_entropy_reference.py`, `s11_coolprop_records.py`, and
   `s11_thermal_reference.py` with CoolProp importable (its `SKIP` line is not a pass).
4. **Recorded values** (`scripts/s11_recorded_values.py`): G4's premise minima (S11.A07–A08),
   rulings item 2's table (R-831), finding F-1's step series, item 5's A46 worst values (R-834).
5. **Rulings item 4's negative control** (R-833), once per run: in a detached worktree of
   `36ea9175` with the one line of C3-1 reverted, the kernel's bisection test fails
   `not_converged`; unreverted, it passes.
6. **`ruff check`, `ruff format --check`** on the Python files S11 adds or changes, and **`mypy`**.

The gate rows G2–G13 aggregate their assertions (and G7/G13 the generators named there). G8 —
`scripts/gate.sh`, CI on x86-64 and aarch64, and the cross-architecture comparisons — is not run
here (it runs once before merge): `S11.G8`, `S11.gate` and `S11.ci` are `unsupported`. `status`
is computed, never written: `tested` iff every assertion and every required check passes;
otherwise `implemented`. Both review fields stay `pending`; `reviewed` is the design lane's.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/s11_evidence_manifest.py --coolprop-site DIR \\
        [--commit SHA] [--out PATH]
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
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import yaml
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s01_evidence_manifest import (  # noqa: E402  (S01's generic helpers, unchanged)
    LOCK,
    ROOT,
    SCHEMA,
    Node,
    Run,
    check,
    command,
    nodes,
    refuse_unless_measuring,
    sha256_file,
    shown,
    text,
)
from s02_evidence_manifest import _verdict  # noqa: E402

PACKAGE = "S11"
NOTE = ROOT / "docs" / "derivations" / "S11-design.md"
UNITS = ROOT / "docs" / "derivations" / "S11-units-design.md"
RULINGS = ROOT / "docs" / "reviews" / "S11-rulings.md"
ADRS = (
    ROOT / "docs" / "adr" / "0050-s11-binding-package.md",
    ROOT / "docs" / "adr" / "0051-s11-thermal-units-on-the-new-bases.md",
)
ENVELOPE = ROOT / "benchmarks" / "t08" / "support_envelope.yaml"
DECISIONS = tuple(ROOT / "docs" / f"S11{track}_DECISIONS.md" for track in "ABCD")
GENERATORS = ROOT / "docs" / "derivations" / "scripts"
#: The identity base of every S11 comparison (§6, units design §6).
MERGE_BASE = "8c34ecb0"
#: Rulings item 4 (R-833): C3-1's commit, the test it added, and the one line it changed.
C31_COMMIT = "36ea9175"
C31_TEST = (
    "tests/test_s11_thermal_kernel.py::test_solve_keeps_the_newton_correction_through_a_bisection"
)
C31_FIXED = "temperature, previous = 0.5 * (low + high), step"
C31_REVERTED = "temperature, previous = 0.5 * (low + high), math.inf"

#: The assertion ids: §6.1 A01–A41, the units design's A42–A86, §10's A87–A93; A24′ replaces A24
#: (§10.8) and is judged in its place.
ASSERTIONS = (*(f"A{index:02d}" for index in range(1, 94)), "A24′")
#: The documents each id is read from.
SOURCE_OF = {
    **{f"A{index:02d}": NOTE for index in (*range(1, 42), *range(87, 94))},
    **{f"A{index:02d}": UNITS for index in range(42, 87)},
    "A24′": NOTE,
}
#: Gate rows (§6.2 and units design §6.2): their assertions.
GATES: dict[str, tuple[str, tuple[str, ...]]] = {
    "G2": ("bases: S11.A01–A10", tuple(f"A{i:02d}" for i in range(1, 11))),
    "G3": ("routing and refusals: S11.A11–A15", tuple(f"A{i:02d}" for i in range(11, 16))),
    "G4": ("premises: S11.A07–A08, numbers recorded", ("A07", "A08")),
    "G5": ("verifier forms: S11.A16–A19", tuple(f"A{i:02d}" for i in range(16, 20))),
    "G6": (
        "column in flowsheets: S11.A20–A29, A35–A38, with timings (§4.12)",
        (*(f"A{i:02d}" for i in range(20, 30)), "A24′", *(f"A{i:02d}" for i in range(35, 39))),
    ),
    "G7": (
        "W27 v3 and the envelope: S11.A30–A34, A40; t08_support_matrix.py --check",
        (*(f"A{i:02d}" for i in range(30, 35)), "A40"),
    ),
    "G9": ("kernel and blocks: S11.A42–A49", tuple(f"A{i:02d}" for i in range(42, 50))),
    "G10": (
        "thermal units: S11.A50–A66, with the §4.11 timings",
        tuple(f"A{i:02d}" for i in range(50, 67)),
    ),
    "G11": (
        "Wilson units: S11.A67–A74, A69–A71 timings",
        tuple(f"A{i:02d}" for i in range(67, 75)),
    ),
    "G12": ("wilson-ig-v2: S11.A75–A81", tuple(f"A{i:02d}" for i in range(75, 82))),
    "G13": (
        "integration: S11.A82–A86 (its G8 part is S11.G8)",
        tuple(f"A{i:02d}" for i in range(82, 87)),
    ),
}
#: The generator checks a gate row also requires.
GATE_GENERATORS = {
    "G7": ("S11.t08",),
    "G13": ("S11.t08", "S11.w27v3", "S11.s4"),
}
#: The assertions whose nodes' wall times the gate rows record (§4.12, units design §4.11).
TIMED = {
    "G6": ("A29",),
    "G10": ("A59", "A60", "A61", "A62", "A63"),
    "G11": ("A69", "A70", "A71", "A80"),
}
#: Tests whose names cite no assertion, and what their docstrings say they evidence. A key ending
#: in `.py` cites every node of that file.
CITATIONS: dict[str, tuple[str, ...]] = {
    "tests/test_s11_column_solve.py::test_a_column_under_a_v1_policy_is_capability_unavailable": (
        "A28",
    ),
    "tests/test_s11_column_solve.py::test_a_revision_region_has_no_edge_3_continuation": ("A24′",),
    "tests/test_t08_w2_surface_digest.py::test_the_served_digest_is_registered": ("A41",),
    "tests/test_s11_staged_splits.py::test_region_splits_is_the_registry_without_a_staged_unit": (
        "A87",
    ),
    "tests/test_s11_staged_splits.py::test_the_column_stage_splits_are_placed_in_the_region": (
        "A88",
    ),
    "tests/test_s11_staged_splits.py::test_a_staged_unit_missing_one_stage_is_refused": ("A89",),
    "tests/test_s11_staged_splits.py::test_a_recovery_definition_row_must_be_claimed": ("A89",),
    "tests/test_s11_staged_splits.py::test_a_staged_key_equal_to_an_instance_id_is_refused": (
        "A89",
    ),
    "tests/test_s11_staged_splits.py::test_an_instance_in_both_registries_is_refused": ("A89",),
    "tests/test_s11_staged_splits.py::test_the_guard_refuses_a_region_without_its_stage_keys": (
        "A90",
    ),
    "tests/test_s11_column_face.py::test_the_twelve_end_parameters_are_the_end_kinds": ("A92",),
    "tests/test_s11_column_face.py::test_each_end_parameter_configures_its_end_specification": (
        "A92",
    ),
    "tests/test_s11_column_face.py::test_a_dotted_or_foreign_end_parameter_is_unsupported": (
        "A92",
    ),
    "tests/test_s11_column_face.py::test_two_end_parameters_at_one_end_conflict": ("A92",),
    # S11.A86: the sample tables that require a bound sample of every thermal model.
    "tests/test_t07_w5c_signatures.py": ("A86",),
    "tests/test_t08_w2_edge_identity.py": ("A86",),
    "tests/test_t07_r6_hints.py": ("A86",),
    "tests/test_t08_w1_typed_ends.py": ("A86",),
}
#: The test files both runs execute besides `tests/test_s11_*.py`: §8.3's amended tests, the
#: sample, surface, envelope and inventory tests I1/I1b touch, the W27 tests (R-837), the S03 and
#: S10-C tests on the Wilson provider, ADR 0008's (the thermal `EQUATIONS`), and the identity tests.
OTHER_TESTS = (
    "test_m02_join.py",
    "test_t08_w2_support_envelope.py",
    "test_s05_envelope.py",
    "test_s07_registration.py",
    "test_s10_provider.py",
    "test_t05_w1b_revision.py",
    "test_t08_kinetic_cstr.py",
    "test_t08_w2_unsupported.py",
    "test_t07_w5c_signatures.py",
    "test_t08_w2_edge_identity.py",
    "test_m07a_harvest.py",
    "test_l01_*.py",
    "test_t08_b50_surface_content.py",
    "test_m02_wo8_registries.py",
    "test_t08_w2_surface_digest.py",
    "test_t07_r6_hints.py",
    "test_t08_w1_typed_ends.py",
    "test_t08_w2_inventory.py",
    "test_m06_w27_*.py",
    "test_s03_s11_refusal.py",
    "test_s10c_*.py",
    "test_adr_0008_transient_readiness.py",
    "test_*identity*.py",
)
#: The S11 assertion an S11 test cites: its name's leading `aNN_` groups; elsewhere `s11_aNN_`.
CITED = re.compile(r"^test_((?:a\d{2}_)+)")
CITED_ELSEWHERE = re.compile(r"^test_s11_((?:a\d{2}_)+)")
G1_LINE = re.compile(r"^S11-IDENTITY PASS n=(\d+) changed=\[\]$")
S08_LINE = "S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL"
S10C_LINE = "S10C-IDENTITY PASS n=858 changed=[]"
#: Each generator's `--check`: the line it must end with.
GENERATOR_LINES: dict[str, tuple[str, re.Pattern[str], bool]] = {
    "S11.t08": ("scripts/t08_support_matrix.py", re.compile(r"^0 problem\(s\)$"), False),
    "S11.w27v3": (
        "docs/derivations/scripts/w27_registration_v3.py",
        re.compile(r"registration_v3\.json: identical; .* blocks: identical$"),
        False,
    ),
    "S11.s4": ("scripts/s11_w27_s4.py", re.compile(r"^S4 OK: 0 problem\(s\)$"), False),
    "S11.wilson-entropy": (
        "docs/derivations/scripts/s11_wilson_entropy_reference.py",
        re.compile(r"^\d+ claims hold; wilson_entropy_reference\.yaml matches$"),
        False,
    ),
    "S11.coolprop-records": (
        "docs/derivations/scripts/s11_coolprop_records.py",
        re.compile(r"^OK: benchmarks/s07/components\.yaml \(123 records\)$"),
        True,
    ),
    "S11.thermal-reference": (
        "docs/derivations/scripts/s11_thermal_reference.py",
        re.compile(r"^OK: benchmarks/s11/thermal_reference\.yaml matches CoolProp 8\.0\.0$"),
        True,
    ),
}
#: Rulings item 2's measured |Z| (R-831) per Wilson case.
ITEM2_Z = {"C-MW": 63, "C-EW": 63, "C-MW-stripper": 34}
#: The non-assertion checks `status` also requires.
REQUIRED_CHECKS = (
    "S11.suite",
    "S11.suites",
    "S11.G1",
    "S11.G1-identity-tests",
    *(f"S11.{gate}" for gate in GATES),
    *GENERATOR_LINES,
    "S11.R831",
    "S11.F-1",
    "S11.R834",
    "S11.R833",
    "S11.ruff",
    "S11.format",
    "S11.mypy",
)
#: R-796 (`docs/decision-register.md`), carried as the brief states it.
R796 = (
    "T07 THM-09/4 (R-796): the uncapped THM-09/4 length is pinned on ref-x86-64 and ci-aarch64 "
    "only; ci-x86-64 and unregistered machine classes assert len > max(K) and run every record-k "
    "interrupt check against their own uninterrupted run."
)


# -- running -------------------------------------------------------------------------------------


def run(argv: Sequence[str], *, coolprop: Path | None = None, cwd: Path = ROOT) -> Run:
    """S01's `run` with `src` and the repository root importable, and optionally CoolProp."""
    environment = dict(os.environ)
    paths = [str(cwd / "src"), str(cwd)]
    prefix = "PYTHONPATH=src:. "
    if coolprop is not None:
        paths.insert(0, str(coolprop))
        prefix = "PYTHONPATH=$COOLPROP_SITE:src:. "
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    completed = subprocess.run(
        list(argv), cwd=cwd, env=environment, capture_output=True, text=True, check=False
    )
    cmd = prefix + " ".join(_display(part) for part in argv)
    return Run(cmd, completed.returncode, completed.stdout + completed.stderr)


def _display(part: str) -> str:
    """An argument as the manifest shows it: the interpreter and its tools as `.venv/bin/<name>`
    (the virtual environment may live outside a worktree), other paths relative to the root."""
    tools = Path(sys.executable).parent
    if os.path.isabs(part) and Path(part).parent == tools:
        return f".venv/bin/{Path(part).name}"
    return shown(part) if os.path.isabs(part) else part


def _last_line(entry: Run) -> str:
    return entry.stdout.strip().splitlines()[-1] if entry.stdout.strip() else ""


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


# -- the documents -------------------------------------------------------------------------------


def assertion_texts() -> dict[str, str]:
    """Each id's bullet (`- **S11.Axx…**` and its continuation lines), first occurrence."""
    found: dict[str, str] = {}
    for document in (NOTE, UNITS):
        lines = document.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = re.match(r"^- \*\*S11\.(A\d{2}′?)(?![\d′])(.*)$", line)
            if not match or match.group(1) in found or SOURCE_OF.get(match.group(1)) != document:
                continue
            body = [line[2:].strip()]
            for following in lines[index + 1 :]:
                if not following.startswith("  ") or not following.strip():
                    break
                body.append(following.strip())
            found[match.group(1)] = " ".join(body).replace("**", "")
    missing = [identifier for identifier in ASSERTIONS if identifier not in found]
    if missing:
        raise SystemExit(f"assertions not found in the design notes: {missing}")
    return found


def envelope_limitations() -> list[str]:
    """The envelope's L-S11-*, L-COL-*, L-TH-* and L-GP-* rows, `id: text` verbatim."""
    envelope = yaml.safe_load(ENVELOPE.read_text(encoding="utf-8"))
    rows = [
        f"{row['id']}: {' '.join(row['text'].split())}"
        for row in envelope["limitations"]
        if re.match(r"^L-(S11|COL|TH|GP)-\d+$", row["id"])
    ]
    if len(rows) != 3 + 10 + 8 + 3:
        raise SystemExit(f"the envelope holds {len(rows)} S11 limitation rows, not 24")
    return rows


# -- the tests -----------------------------------------------------------------------------------


def merged(first: Sequence[Node], second: Sequence[Node]) -> list[Node]:
    """The worse outcome of a node over the two runs (see the module docstring)."""
    rank = {"failed": 3, "error": 3, "passed": 2, "xfailed": 1, "skipped": 0}
    by_node: dict[str, Node] = {}
    for item in (*first, *second):
        held = by_node.get(item.node)
        if held is None or rank[item.outcome] > rank[held.outcome]:
            by_node[item.node] = item
    return [by_node[name] for name in sorted(by_node)]


def wall_times(*junits: Path) -> dict[str, float]:
    """Each node's longest wall time over the runs, from the JUnit reports."""
    times: dict[str, float] = {}
    for junit in junits:
        for case in ElementTree.parse(junit).getroot().iter("testcase"):
            node = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name', '')}"
            times[node] = max(times.get(node, 0.0), float(case.get("time", "0")))
    return times


def cited(node: str) -> tuple[str, ...]:
    function = node.split("[", 1)[0]
    module, _, name = function.partition("::")
    explicit = CITATIONS.get(function, ()) + CITATIONS.get(module, ())
    pattern = CITED if module.startswith("tests/test_s11_") else CITED_ELSEWHERE
    match = pattern.match(name)
    named = tuple(
        f"A{number}" for number in re.findall(r"a(\d{2})_", match.group(1) if match else "")
    )
    return named + explicit


def _judged(citing: Sequence[Node]) -> tuple[str, dict[str, Any]]:
    """S02's verdict, with the node ids made manifest-safe (a parametrize id may hold `<…>`)."""
    result, value = _verdict(citing)
    return result, {**value, "selectors": [text(node) for node in value["selectors"]]}


def suite_check(identifier: str, description: str, chosen: Sequence[Node]) -> dict[str, Any]:
    """Every chosen node passed (and there is at least one)."""
    result, value = _verdict(chosen)
    del value["selectors"]
    return check(identifier, description, result, value, "every node passed")


def skips(chosen: Sequence[Node]) -> dict[str, int]:
    """The skipped nodes, counted by file and reason."""
    counted: dict[str, int] = {}
    for item in chosen:
        if item.outcome == "skipped":
            key = text(f"{item.node.split('::', 1)[0]}: {item.message[:120]}")
            counted[key] = counted.get(key, 0) + 1
    return dict(sorted(counted.items()))


def suites_check(chosen: Sequence[Node]) -> dict[str, Any]:
    """No node failed or errored, and no skipped node is cited by an assertion. A skip is never
    counted as a pass: each is listed with its reason (and in the limitations)."""
    _, value = _verdict(chosen)
    del value["selectors"]
    failed = [item for item in value["not_passed"] if item["outcome"] in ("failed", "error")]
    cited_skips = [item.node for item in chosen if item.outcome == "skipped" and cited(item.node)]
    value = {**value, "not_passed": failed, "skipped": skips(chosen), "cited_skips": cited_skips}
    passed = bool(chosen) and not failed and not cited_skips
    return check(
        "S11.suites",
        "the other test files run here (§8.3's amended tests; the sample, surface, envelope, "
        "inventory, W27 (R-837: read through v2_binder()), S03, S10-C, ADR 0008 and identity "
        "tests): no node failed or errored in either run, and no skipped node is cited by an "
        "assertion; the skipped nodes are listed with their reasons",
        "pass" if passed else "fail",
        value,
        "no failure; skips listed, none cited",
    )


# -- recorded values and the negative control ----------------------------------------------------


def recorded_checks(entry: Run) -> list[dict[str, Any]]:
    try:
        values = json.loads(_last_line(entry))
    except json.JSONDecodeError:
        values = None
    if entry.exit_code != 0 or values is None:
        failed = {"cmd": entry.cmd, "exit_code": entry.exit_code, "tail": text(entry.stdout[-600:])}
        return [
            check(name, "scripts/s11_recorded_values.py did not run", "fail", failed)
            for name in ("S11.G4-values", "S11.R831", "S11.F-1", "S11.R834")
        ]
    witness = values["witness"]
    tolerance = witness["derivative_tolerance"]
    item2 = witness["item2"]
    item2_ok = set(item2) == set(ITEM2_Z) and all(
        row["Z"] == ITEM2_Z[name]
        and row["one_sided_worst"] <= tolerance / 10
        and row["central_worst"] <= tolerance
        and row["one_sided_results"] == row["central_results"] == ["pass", "pass"]
        for name, row in item2.items()
    )
    series = witness["f1_cmw_central_worst_by_step"]
    a46 = values["a46"]
    g4 = values["g4"]
    g4_ok = all(m["value_3sf"] == m["registered"] for w in ("real", "verification") for m in g4[w])
    g4_ok = g4_ok and (
        g4["a08_widened_300_800_K"]["premise"],
        g4["a08_widened_300_800_K"]["component"],
    ) == ("P2", "H2O")
    return [
        check(
            "S11.G4-values",
            "G4: S11.A07's premise minima (real and verification records) and S11.A08's first "
            "violation on the real records widened to [300, 800] K, measured",
            "pass" if g4_ok else "fail",
            {"cmd": entry.cmd, **g4},
            "every minimum rounds (3 s.f.) to its benchmarks/s10c positivity entry; A08: P2, H2O",
        ),
        check(
            "S11.R831",
            "rulings item 2 (R-831): per Wilson column certificate, |Z|, the one-sided worst "
            "(forward five-point stencil on Z alone), the central worst (every other column) and "
            "the smallest nonzero scaled AD entry in Z",
            "pass" if item2_ok else "fail",
            {"cmd": entry.cmd, "derivative_tolerance": tolerance, "cases": item2},
            "|Z| = 63, 63, 34; one-sided ≤ DERIVATIVE_TOLERANCE/10; central ≤ DERIVATIVE_TOLERANCE",
        ),
        check(
            "S11.F-1",
            "rulings finding F-1: C-MW's central witness against the relative step (O(h²), "
            "deterministic); recorded, gated only at the registered step",
            "pass" if series[f"{witness['registered_step']:g}"] <= tolerance else "fail",
            {"cmd": entry.cmd, "registered_step": witness["registered_step"], "by_step": series},
            "the registered step's value ≤ DERIVATIVE_TOLERANCE (1e-7); the rest recorded",
        ),
        check(
            "S11.R834",
            "rulings item 5 (R-834): the worst value of each S11.A46 test on this machine "
            "(ref-x86-64); aarch64's come from CI",
            "pass" if all(row["worst"] <= row["bound"] for row in a46.values()) else "fail",
            {"cmd": entry.cmd, "rows": a46},
            "each worst ≤ its bound",
        ),
    ]


def negative_control() -> tuple[dict[str, Any], list[Run]]:
    """R-833: the C3-1 test passes at 36ea9175 and fails `not_converged` with the line reverted."""
    with tempfile.TemporaryDirectory() as directory:
        tree = Path(directory) / "c31"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(tree), C31_COMMIT],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        try:
            argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", C31_TEST]
            fixed = run(argv, cwd=tree)
            kernel = tree / "src" / "openflowsheet" / "models" / "thermal" / "kernel.py"
            source = kernel.read_text(encoding="utf-8")
            occurrences = source.count(C31_FIXED)
            kernel.write_text(source.replace(C31_FIXED, C31_REVERTED), encoding="utf-8")
            reverted = run(argv, cwd=tree)
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
    fixed = dataclasses.replace(fixed, cmd=f"(worktree of {C31_COMMIT}) {fixed.cmd}")
    reverted = dataclasses.replace(
        reverted, cmd=f"(worktree of {C31_COMMIT}, C3-1's line reverted) {reverted.cmd}"
    )
    passed = (
        occurrences == 1
        and fixed.exit_code == 0
        and reverted.exit_code == 1
        and "not_converged" in reverted.stdout
    )
    entry = check(
        "S11.R833",
        f"rulings item 4 (R-833), the negative control: in a detached worktree of {C31_COMMIT}, "
        f"{C31_TEST} passes; with C3-1's one line reverted ({C31_FIXED} → {C31_REVERTED}) it "
        "fails not_converged",
        "pass" if passed else "fail",
        {
            "line_occurrences": occurrences,
            "fixed": {"exit_code": fixed.exit_code, "line": _last_line(fixed)},
            "reverted": {
                "exit_code": reverted.exit_code,
                "line": _last_line(reverted),
                "names_not_converged": "not_converged" in reverted.stdout,
            },
        },
        "fixed: exit 0; reverted: exit 1 naming not_converged",
    )
    return entry, [fixed, reverted]


# -- the manifest --------------------------------------------------------------------------------


def status(entries: Sequence[Mapping[str, Any]]) -> str:
    """`tested` iff every assertion and every required check passes; never `reviewed`."""
    required = {f"S11.{identifier}" for identifier in ASSERTIONS} | set(REQUIRED_CHECKS)
    results = {entry["id"]: entry["result"] for entry in entries}
    missing = required - set(results)
    if missing:
        raise SystemExit(f"checks missing: {sorted(missing)}")
    return "tested" if all(results[name] == "pass" for name in required) else "implemented"


def found_limitations(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    items = [
        R796,
        "requirements is empty: neither design note assigns S11 a D/A requirement id, and "
        "docs/requirements.yaml has no S11 entry.",
        "G8 (scripts/gate.sh, CI on x86-64 and aarch64, and the Wilson, CoolProp, thermal and "
        "Wilson-flowsheet results compared across architectures by tolerance, worst value "
        "recorded) was not run by this generator: it runs once before merge into main. S11.G8, "
        "S11.gate and S11.ci are unsupported here, and G13's G8 part with them. Rulings item "
        "5's aarch64 A46 values come from that CI run.",
        "Review: the design lane's single reviewer pass over tracks A–D, I1, I1b and the rulings "
        "(design note §5 row I2, units design §5.4 amendment 3, rulings §5 row I2) has not "
        "happened; the review fields stay pending and the human numerical and process-model "
        "review is pending. This manifest claims neither.",
        "O-C6-1, ruled by R-844 (docs/reviews/S11-review.md M2): the SYN-001 pump's dormant "
        "case under T04-W12 certifies VERIFIED/NO_RANK_LOSS_DETECTED while A62's thermal heater "
        "at Q = 0 certifies UNVERIFIED/RANK_DEFICIENT under v1 and v2 (pinned; "
        "verify.zero_flow.DORMANT_OUTLETS holds no thermal.* entry). L-TH-7 states it; the "
        "verifier's thermal entries are a follow-on package, not S11.",
        "The CoolProp-dependent checks (run B of the tests, s11_thermal_reference.py --check, "
        "s11_coolprop_records.py --check) were run with CoolProp 8.0.0 importable from a scratch "
        "site holding the coolprop extra's wheel, outside requirements.lock; run A is the locked "
        "environment without it.",
        "G1's family C runs every tests/test_*.py in the base and this tree and requires every "
        "shard to exit 0, so the whole suite passed in this tree without CoolProp; it is not "
        "the full gate (no ruff/mypy over the repository, no packaging or wheel checks).",
        "The agreement with the committed references is numerical verification (CoolProp 8.0.0 "
        "HEOS for the thermal reference; the 50-digit mpmath generator for wilson-ig-v2's "
        "entropy), not empirical validation; the SYN-001 columns are synthetic (L-COL-8). "
        "Self-generated cases (the committed flowsheet JSONs) are regression fixtures.",
        "The wall times in S11.G6, S11.G10 and S11.G11 are the JUnit times of the cited nodes "
        "in this run (each includes binding, planning and verification where the test does); "
        "§4.12's ratio gate is judged by the build logs' measurements, not here.",
        "The T08 support envelope's harvest of this manifest follows its generation, in a later "
        "commit.",
    ]
    for entry in entries:
        if entry["id"] == "S11.suites" and entry["value"].get("skipped"):
            listed = "; ".join(f"{n} × {key}" for key, n in entry["value"]["skipped"].items())
            items.append(
                text(
                    "Skipped in both test runs (not counted as passed; none cited by an S11 "
                    f"assertion): {listed}."
                    + (
                        " The W27 tests that need the pinned OpenIDAES-450 archive therefore did "
                        "not run here (the archive is absent on this workstation); R-837's 'all "
                        "existing W27 tests pass' is evidenced here by the archive-free W27 tests "
                        "only."
                        if "pinned archive absent" in listed
                        else ""
                    )
                )
            )
    for entry in entries:
        if entry["result"] == "pass" or entry["id"] in ("S11.G8", "S11.gate", "S11.ci"):
            continue
        value = entry.get("value")
        detail = (
            "; ".join(f"{item['node']} {item['outcome']}" for item in value["not_passed"])
            if isinstance(value, dict) and value.get("not_passed")
            else "see its value"
        )
        items.append(text(f"{entry['id']} is {entry['result']}: {detail}"))
    return items


def build(commit: str, coolprop: Path | None) -> dict[str, Any]:
    refuse_unless_measuring(commit)
    texts = assertion_texts()
    artifacts = ROOT / "evidence" / PACKAGE / commit / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    junits = {"A": artifacts / "s11-tests-a.junit.xml", "B": artifacts / "s11-tests-b.junit.xml"}
    python = sys.executable
    tools = Path(python).parent
    tests = sorted(
        {
            shown(path)
            for pattern in ("test_s11_*.py", *OTHER_TESTS)
            for path in (ROOT / "tests").glob(pattern)
        }
    )
    base = _git("merge-base", "main", "HEAD")
    changed = [
        path
        for path in _git("diff", "--name-only", "--diff-filter=AM", f"{base}..HEAD").splitlines()
        if path.endswith(".py")
    ]

    def pytest(junit: Path) -> list[str]:
        return [
            python,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={shown(junit)}",
        ]

    runs: dict[str, Run] = {"tests-A": run([*pytest(junits["A"]), *tests])}
    if coolprop is not None:
        runs["tests-B"] = run([*pytest(junits["B"]), *tests], coolprop=coolprop)
    runs["recorded"] = run([python, str(ROOT / "scripts" / "s11_recorded_values.py")])
    for name, (script, _, needs_coolprop) in GENERATOR_LINES.items():
        if needs_coolprop and coolprop is None:
            continue
        runs[name] = run(
            [python, str(ROOT / script), "--check"], coolprop=coolprop if needs_coolprop else None
        )
    runs["S11.ruff"] = run([str(tools / "ruff"), "check", *changed])
    runs["S11.format"] = run([str(tools / "ruff"), "format", "--check", *changed])
    runs["S11.mypy"] = run([str(tools / "mypy")])
    runs["S08"] = run([python, str(ROOT / "scripts" / "s08_identity.py")])
    runs["S10C"] = run([python, str(ROOT / "scripts" / "s10c_identity.py")])
    runs["S11.G1"] = run([python, str(ROOT / "scripts" / "s11_identity.py")])
    control, control_runs = negative_control()

    if not junits["A"].is_file():
        raise SystemExit(f"pytest wrote no report (exit {runs['tests-A'].exit_code})")
    found_a = nodes(junits["A"])
    found_b = nodes(junits["B"]) if coolprop is not None and junits["B"].is_file() else []
    found = merged(found_a, found_b)
    times = wall_times(*(path for path in junits.values() if path.is_file()))

    g1_line = _last_line(runs["S11.G1"])
    g1 = check(
        "S11.G1",
        "§6.2 G1: scripts/s11_identity.py on the base 8c34ecb0 and this commit — family A (S08's "
        "52 configurations and S01 C1–C5), family B (every ph_state call of the T05/T05b tests), "
        "family C (every bind_revision_flowsheet call of the whole suite, keyed by test node id "
        "and call index; every shard exits 0 in both trees); keys present in both equal except "
        "AMENDED_TESTS, no base-only keys",
        "pass" if runs["S11.G1"].exit_code == 0 and G1_LINE.match(g1_line) else "fail",
        {"cmd": runs["S11.G1"].cmd, "exit_code": runs["S11.G1"].exit_code, "line": g1_line},
        "S11-IDENTITY PASS n=‹N› changed=[]",
    )
    lines = {
        name: (runs[name].exit_code, _last_line(runs[name]), expected)
        for name, expected in (("S08", S08_LINE), ("S10C", S10C_LINE))
    }
    lines_ok = all(code == 0 and line == expected for code, line, expected in lines.values())
    lines_value = {
        name: {"cmd": runs[name].cmd, "exit_code": code, "line": line}
        for name, (code, line, _) in lines.items()
    }
    special: dict[str, tuple[str, dict[str, Any]]] = {
        "A23": (
            "pass" if lines_ok else "fail",
            {"judged_by": "the identity scripts", **lines_value},
        ),
        "A85": (
            "pass" if lines_ok and g1["result"] == "pass" else "fail",
            {"judged_by": "G1 and the identity scripts", "G1": g1_line, **lines_value},
        ),
    }
    entries: list[dict[str, Any]] = []
    for identifier in ASSERTIONS:
        if identifier in special:
            result, value = special[identifier]
        elif identifier == "A24":
            result, value = _judged([item for item in found if "A24′" in cited(item.node)])
            value = {**value, "judged_by": "S11.A24′, which replaces A24 (design note §10.8)"}
        else:
            result, value = _judged([item for item in found if identifier in cited(item.node)])
        entries.append(check(f"S11.{identifier}", texts[identifier], result, value))
    results = {entry["id"]: entry["result"] for entry in entries}

    entries += [
        suite_check(
            "S11.suite",
            "every node of tests/test_s11_*.py passed (the worse of runs A and B), including "
            "those that cite no assertion",
            [item for item in found if item.node.startswith("tests/test_s11_")],
        ),
        suites_check([item for item in found if not item.node.startswith("tests/test_s11_")]),
        g1,
        suite_check(
            "S11.G1-identity-tests",
            "§6.2 G1: the existing tests/test_*identity*.py tests pass",
            [item for item in found if "identity" in item.node.split("::", 1)[0]],
        ),
    ]
    for name, (script, pattern, needs_coolprop) in GENERATOR_LINES.items():
        if name not in runs:
            entries.append(
                check(name, f"{script} --check", "unsupported", "CoolProp was not importable")
            )
            continue
        line = _last_line(runs[name])
        entries.append(
            check(
                name,
                f"{script} --check" + (" (CoolProp 8.0.0 importable)" if needs_coolprop else ""),
                "pass" if runs[name].exit_code == 0 and pattern.search(line) else "fail",
                {"cmd": runs[name].cmd, "exit_code": runs[name].exit_code, "line": line},
                pattern.pattern,
            )
        )
    entries += recorded_checks(runs["recorded"])
    entries.append(control)
    results.update({entry["id"]: entry["result"] for entry in entries})

    for gate, (description, members) in GATES.items():
        extra = GATE_GENERATORS.get(gate, ())
        if gate == "G4":
            extra = ("S11.G4-values",)
        parts = {f"S11.{member}": results[f"S11.{member}"] for member in members}
        parts.update({name: results[name] for name in extra})
        value: dict[str, Any] = {"judged_by": "its assertions and checks", "parts": parts}
        if gate in TIMED:
            value["wall_time_s"] = {
                item.node: round(times.get(item.node, 0.0), 3)
                for item in found
                if any(a in cited(item.node) for a in TIMED[gate])
            }
        passed = all(result == "pass" for result in parts.values())
        entries.append(
            check(f"S11.{gate}", f"§6.2 {gate}, {description}", "pass" if passed else "fail", value)
        )
    for name, description in (
        ("S11.ruff", "ruff check is clean on the Python files S11 adds or changes"),
        ("S11.format", "ruff format --check is clean on the Python files S11 adds or changes"),
        ("S11.mypy", "mypy (the project's configuration) is clean"),
    ):
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
        (
            "S11.G8",
            "§6.2 G8 (and G13's G8 part): full scripts/gate.sh once before merge; CI green on "
            "x86-64 and aarch64; Wilson and CoolProp compared across architectures by tolerance, "
            "and the thermal and Wilson flowsheet results within 1e-9 relative (worst recorded)",
        ),
        ("S11.gate", "scripts/gate.sh passes before merge"),
        ("S11.ci", "CI is green on x86-64 and aarch64 before merge"),
    ):
        entries.append(
            check(
                name,
                description,
                "unsupported",
                "not run by this generator; it runs once before merge (CLAUDE.md)",
            )
        )

    commands = [command(entry) for entry in runs.values()]
    commands += [command(entry) for entry in control_runs]
    documents = [
        (NOTE, "the S11 design note (§6 assertions and gates G1–G8, §10 amendments)"),
        (UNITS, "the S11 units design (§6 assertions S11.A42–A86, gates G9–G13)"),
        (RULINGS, "the design lane's rulings on S11's build decisions (R-830…R-842)"),
        *((adr, "the decision S11 implements") for adr in ADRS),
        (ENVELOPE, "the T08 support envelope, the source of the L-rows below"),
        *((path, "S11's build decisions with the measured facts") for path in DECISIONS),
    ]
    manifest: dict[str, Any] = {
        "work_package": PACKAGE,
        "commit": commit,
        "requirements": [],
        "status": status(entries),
        "inputs": {
            "case_id": "S11 acceptance: docs/derivations/S11-design.md §6 and §10 (S11.A01–A41, "
            "A24′, A87–A93) and docs/derivations/S11-units-design.md §6 (S11.A42–A86), gates "
            "G1–G13, rulings docs/reviews/S11-rulings.md §5 row I2",
            "case_hash": sha256_file(NOTE),
            "environment_lock_hash": sha256_file(LOCK),
        },
        "commands": commands,
        "checks": entries,
        "artifacts": [
            *(
                {
                    "path": shown(path),
                    "sha256": sha256_file(path),
                    "description": f"JUnit report of test run {run_id} (ignored; kept by hash)",
                }
                for run_id, path in junits.items()
                if path.is_file()
            ),
            *(
                {"path": shown(path), "sha256": sha256_file(path), "description": description}
                for path, description in documents
            ),
        ],
        "limitations": [*envelope_limitations(), *found_limitations(entries)],
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
        "--coolprop-site",
        type=Path,
        help="a directory holding CoolProp 8.0.0 (the coolprop extra's wheel, unpacked); without "
        "it the CoolProp checks are unsupported and the status cannot be tested",
    )
    parser.add_argument(
        "--out", type=Path, help=f"default: evidence/{PACKAGE}/<commit>/manifest.json"
    )
    arguments = parser.parse_args()
    commit = arguments.commit or _git("rev-parse", "HEAD")
    manifest = build(commit, arguments.coolprop_site)
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
