"""Generate `evidence/T05b/<commit>/manifest.json` by measuring, not by transcribing. T05b.

T05b's package carries two assertion catalogues: `docs/derivations/T05b-limitations-spec.md` §14
(`B00`…`B36`, as amended through the ruling rounds of `docs/briefs/T05b-rulings.md` §4) and, T04's
F9 folded in (ADR 0013), `docs/derivations/K04-F9-spec.md` §8 (`X00`…`X26`, as amended). Every
value recorded here is produced by running the code in this process and comparing it with an
independent expectation: `benchmarks/t05b/reference_values.yaml` and
`benchmarks/k04f9/reference_values.yaml` (the design lane's 40-digit twins, emitted by
`docs/derivations/scripts/t05b_reference.py` and `k04f9_reference.py`), the inertness baselines of
`docs/t05b-measurements.md` (W0.1, measured at `b8c6442` before any T05b edit, and the
re-registrations recorded there with their reasons), or a closed form stated in the check itself.
A regression value (a self-generated number the specification pins beside its assertion) is
compared with the pin the gate's test holds, imported from that test, never re-pinned here.

The fixtures — the registered revisions, starts, injections, doubles and sweeps — are imported
from the package's tests (`tests/t05b_support.py`, `tests/k04f9_support.py`,
`tests/test_t05b_*.py`, `tests/test_k04f9_*.py`) so that the manifest and the gate run the same
cases built the same way; the observation and the comparison are stated here, and where an
assertion is established by a family of tests the numbers it states (worst ratios, counts, exact
sets) are measured here. A clause that states no number (a typed refusal at a constructed
function-level state, a spy's record) is observed through the test's own construction and its
observation recorded. Every observer records and returns what the code computed; none alters a
value.

Two halves cannot be measured on one machine: B22's `t05b` key and X19's identities on the CI
pair (x86-64 and aarch64), which CI's `identity` job establishes. Pass `--identities DIR` (the
downloaded `structural-identity-*` artifacts) and `--ci-run URL`; without them those halves are
`unsupported`, never `pass`. When the CI run's head commit is not the measured one, pass it as
`--ci-commit SHA`: the two may differ only in this generator, the evidence tree and the design
lane's review notes (measured by `git diff`, refused otherwise), and the difference is recorded in
`limitations`.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t05b_evidence_manifest.py <gate-stdout> --commit <sha> \
        [--identities DIR] [--ci-run URL] [--ci-commit SHA] [--out PATH]
"""

# ruff: noqa: E402 - the imports after the first block follow the `sys.path` setup that
# makes the gate's `tests/` and the earlier packages' `scripts/` importable.

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

# The registered fixtures and references, shared with the gate (see the module note).
import dataclasses
import glob
import typing
from collections import Counter
from contextlib import contextmanager
from decimal import InvalidOperation

import k04_evidence_manifest as k04m
import k04_schema_fixtures
import k04f9_support as f9_support
import pytest
import scipy.sparse as sp
import t04_evidence_manifest as t04m
import t04_schema_fixtures
import t05_evidence_manifest as t05m
import t05b_ph_baseline as ph_baseline
import t05b_support as support
import test_k04_checks as k04_checks
import test_k04f9_family as f9_family
import test_k04f9_projection as f9_projection
import test_k04f9_rules as f9_rules
import test_k04f9_t05b as f9_t05b
import test_t04_certificate as t04_certificate
import test_t05_dormant_outlet as dormant_outlet_test
import test_t05_single_component_eo as t05_single
import test_t05_table_independence as table_independence
import test_t05_w1d_verifier as w1d
import test_t05b_band as band_fixtures
import test_t05b_band_screen as band_screen
import test_t05b_candidate_answers as candidates
import test_t05b_contract as contract
import test_t05b_dormancy as dormancy
import test_t05b_kernel as kernel_fixtures
import test_t05b_leaving_flash as leaving
import test_t05b_literal as literal_fixtures
import test_t05b_near_pure_restarts as near_pure_tests
import test_t05b_openings as openings
import test_t05b_r007 as r007_fixtures
import test_t05b_release_opening as release
import test_t05b_seeding as seeding
import test_t05b_verifier as verifier_tests
import test_t05b_zero_flow as zero_flow_tests
import yaml
from t05_support import CONTEXT, PROVIDER, first_line
from t05_support import REF as T05_REF
from t05_syn001_shaped import shaped_revision
from t05_w12_support import bind
from t05_w12_support import planned_step as p5_planned_step
from t05b_identity import REGISTERED_STARTS
from t05b_identity import _builders as _t05b_builders
from t05b_support import DORMANT_NON_LIFTED_CASES, Biased, Jump, number

import openflowsheet.verify.certificate as p5_certificate_module
from openflowsheet.canonical import canonical_json, file_sha256
from openflowsheet.models.revision_flowsheet import parse_revision
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.admission import admitted_enthalpy
from openflowsheet.models.syn001.ph_kernel import (
    MAX_BAND_EVALUATIONS,
    PHState,
    ph_state,
    port_enthalpy,
)
from openflowsheet.models.syn001.saturation_band import degeneracy_distance
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.numerics.newton import _trial_point, solve_newton
from openflowsheet.orchestrator import region as region_module
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.region import (
    TP_REGIME,
    DormancyForm,
    RegionResult,
    _band_regime,
    _contract_kernel,
    _items,
    _kernel,
    _rederive,
    _settle,
    _split_enthalpy,
    _trigger_dormant,
)
from openflowsheet.orchestrator.revision import (
    InitialStateFailure,
    TraversalStart,
    initial_state,
    plan_revision,
    traversal_start,
)
from openflowsheet.orchestrator.splits import DORMANCY_RULES, closure_types, lifted_splits
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.orchestrator.trace import PhaseContract, SolvePolicy, Trace
from openflowsheet.run.compare import differences
from openflowsheet.run.identity import floats_in, r0_projection
from openflowsheet.thermo import FlashRequest, StreamState
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import (
    CheckReport,
    SolutionCertificate,
    run_checks,
    verify,
    verify_bound,
    verify_revision,
)
from openflowsheet.verify.checks import KIND_TOLERANCE
from openflowsheet.verify.projection import PROJECTED_CATEGORIES
from openflowsheet.verify.saturation import (
    UNRESOLVED_FLOOR_OVER_TOLERANCE,
    band_ends,
    resolution_floor,
    split_route,
)
from openflowsheet.verify.table import (
    SPLIT_ENTHALPY_NOTE,
    UNRESOLVED_ENTHALPY_NOTE,
)
from openflowsheet.verify.zero_flow import DORMANT_OUTLETS

REFERENCE = ROOT / "benchmarks" / "t05b" / "reference_values.yaml"
F9_REFERENCE = ROOT / "benchmarks" / "k04f9" / "reference_values.yaml"
SPEC = ROOT / "docs" / "derivations" / "T05b-limitations-spec.md"
F9_SPEC = ROOT / "docs" / "derivations" / "K04-F9-spec.md"
RULINGS = ROOT / "docs" / "briefs" / "T05b-rulings.md"
MEASUREMENTS = ROOT / "docs" / "t05b-measurements.md"
SCRIPTS = ROOT / "docs" / "derivations" / "scripts"
GENERATOR = SCRIPTS / "t05b_reference.py"
F9_GENERATOR = SCRIPTS / "k04f9_reference.py"
T05_GENERATOR = SCRIPTS / "t05_reference.py"
FIXTURES = ROOT / "tests" / "fixtures"
SOURCE = ROOT / "src" / "openflowsheet"

#: The registered references, read once (the tests' own loads).
REF: dict[str, Any] = support.REF
F9_REF: dict[str, Any] = f9_support.REF

#: The assertion ids: T05b spec §14 `B00`…`B36`, K04-F9 spec §8 `X00`…`X26`.
B_IDS = tuple(f"B{index:02d}" for index in range(37))
X_IDS = tuple(f"X{index:02d}" for index in range(27))
#: ADR 0012's and ADR 0013's affected requirements (their headers), in order, once each.
ADR_REQUIREMENTS = ("V12", "D09", "A01", "D11", "V15", "A08", "A09", "D20", "D14")

#: The W0.1 base of T05b (`docs/t05b-measurements.md` W0.1, spec §20): the commit every
#: inertness statement is measured against.
BASE_COMMIT = "b8c6442"
#: The registered identities (`docs/t05b-measurements.md`: W0.1, and W9.4's re-registration of
#: the `t05b` key with its reason, Q-S11 (a); the hash conventions of that file's protocol).
REGISTERED = {
    "syn001_py_sha256": "75c9d5bad4f1cb3c8aa28b97d529777949434ebf911c0d9e11568b1e69ddd6ce",
    "identity_document_sha256": (
        "91fac60822ddcebe1a34205fbfca54ab391dba833ef9b2e91671c4efba5cdf06"
    ),
    "identity_minus_t05b_sha256": (
        "622463f5fbc8716f1196bc971633877e2d218e1c9744e3d4ad7d49608be0415b"
    ),
    "identity_minus_t05_t05b_sha256": (
        "b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a"
    ),
    "t05_key_sha256": "ddbd0f7135ee5310a1ce65865fab69b69cafe542851a038086941740360687a3",
    "t05b_key_sha256": "4f29500e31139133cd2304d848390665ec9c298d55a2a952321df3da11e89c54",
    "structural_sha256": "4ce030cab1e4b4a2402897f480e5194961a1dbe9b8705316ddd4776cbd2d0082",
    "check_policy_sha256": "21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390",
    "t02_floats_sha256": "9a8a5baf14e4f04f5d852a0998f7914f7bdcc81c056787e117a09980e25a2fb2",
    "gate_count_at_base": 2548,
}
#: The reference files the twins build on, as their specifications register them (B00, X00).
REFERENCE_FILES = {
    "t04": "4dda7ebe0d7255724e1632487a0a488ed6536b179ed424f29846f22cd27f9467",
    "t05": "af4a543f8dab3d95c32764117be00afbc9e8d49478998e8538a1daf359385a6a",
    "t05b": "cf1a86067f3de92266b1e121ee9711e6e5f235d0bf87657afd231996f5fc807b",
    "k04": "2a1b5ecb25da26f5e381e73e189f21848ce6f2a4fe4a4a47878351d605424c9e",
    "k04f9": "73be8df910d13425273f1ef2ad87d4771e4e1c92e66bd128e69231b98a13e3b7",
}
#: A float as `repr` writes one, and a 64-hex digest (T04's and T05's patterns).
FLOAT = re.compile(r"\d\.\d|\d[eE][-+]?\d|\binf\b|\bnan\b")
HEX64 = re.compile(r"[0-9a-f]{64}")


def check(
    identifier: str, description: str, result: str, value: Any, expected: Any
) -> dict[str, Any]:
    return {
        "id": identifier,
        "description": description,
        "result": result,
        "value": value,
        "expected": expected,
    }


def verdict(condition: bool) -> str:
    return "pass" if condition else "fail"


#: A measurement returns `(condition, value, expected)`: a bool (`pass`/`fail`), or one of the
#: results a check may carry when the condition is not a verdict (`unsupported`,
#: `not_applicable`), whose reason the value states.
Measure = Callable[[], tuple[Any, Any, Any]]
RESULTS = ("pass", "fail", "unsupported", "not_applicable")


def measured(identifier: str, description: str, measure: Measure) -> dict[str, Any]:
    """Run one assertion's measurement. An exception is a failed measurement, recorded as such:
    a check that could not run did not pass, and hiding the error would hide the finding."""
    try:
        condition, value, expected = measure()
    except Exception as error:  # noqa: BLE001 - every failure is recorded, none is swallowed
        return check(
            identifier,
            description,
            "fail",
            {"error": f"{type(error).__name__}: {error}"},
            "the measurement runs to completion",
        )
    if isinstance(condition, str):
        if condition not in RESULTS:
            raise ValueError(f"{identifier}: result {condition!r} is not one of {RESULTS}")
        return check(identifier, description, condition, value, expected)
    return check(identifier, description, verdict(bool(condition)), value, expected)


def plain(value: Any) -> Any:
    """A JSON-safe copy: numpy scalars and arrays as Python numbers, fractions and decimals as
    strings, non-finite floats as strings."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        items = sorted(value, key=str) if isinstance(value, set | frozenset) else value
        return [plain(item) for item in items]
    if isinstance(value, np.ndarray):
        return [plain(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, Fraction | Decimal):
        return str(value)
    if isinstance(value, complex):
        return [plain(value.real), plain(value.imag)]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


@dataclass
class Ledger:
    """The departures of one check from its registration, each named where it occurred. A check
    passes when there are none; every departure is recorded in the check's value."""

    departures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.departures

    def equal(self, where: str, value: Any, expected: Any) -> Any:
        if value != expected:
            self.departures.append(f"{where}: measured {value!r}, registered {expected!r}")
        return value

    def within(self, where: str, value: float | None, expected: Any, tolerance: float) -> float:
        """`|x − x_ref| ≤ tolerance`, the registered value taken at its full decimal precision
        (`t05b_support.error`); returns the error (`inf` when nothing was measured). A registered
        exact zero with a zero tolerance is `== 0.0`."""
        if value is None:
            self.departures.append(f"{where}: nothing measured, registered {expected}")
            return math.inf
        if Decimal(str(expected)) == 0 and tolerance == 0.0:
            if value != 0.0:
                self.departures.append(f"{where}: measured {value!r}, registered exactly 0")
            return abs(float(value))
        found = support.error(float(value), str(expected))
        if not found <= tolerance:
            self.departures.append(
                f"{where}: measured {value!r}, registered {expected} "
                f"(error {found:.3g}, allowed {tolerance:.3g})"
            )
        return found

    def at_most(self, where: str, value: float | None, bound: float) -> float | None:
        """`value ≤ bound` (a one-sided registered bound); returns the value."""
        if value is None or not value <= bound:
            self.departures.append(f"{where}: measured {value!r}, bound {bound!r}")
        return value

    def true(self, where: str, condition: bool) -> bool:
        if not condition:
            self.departures.append(f"{where}: does not hold")
        return condition


def worst(ratios: Mapping[str, float]) -> dict[str, Any]:
    """The largest of a set of named ratios, as `{"ratio", "where", "count"}`."""
    if not ratios:
        return {"ratio": None, "where": None, "count": 0}
    where = max(ratios, key=lambda key: ratios[key])
    return {"ratio": ratios[where], "where": where, "count": len(ratios)}


def _git(*arguments: str) -> str:
    completed = subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    return completed.stdout


def _document_sha256(document: Mapping[str, Any]) -> str:
    """The digest of an identity document as `k05_structural_identity.py --out` writes it."""
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _key_sha256(document: Any) -> str:
    """The digest of one key of the identity document (`docs/t05b-measurements.md`'s protocol:
    `json.dumps(key, sort_keys=True)`)."""
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


@cache
def identity_document() -> dict[str, Any]:
    """K05's identity document on this machine, built once (the `t05` and `t05b` keys included);
    as `k05_structural_identity.py --out` writes it, read back through JSON."""
    from k05_structural_identity import identity as k05_identity

    document: dict[str, Any] = json.loads(json.dumps(k05_identity(), allow_nan=False))
    return document


# ------------------------------------------------------------------------- B00, X00


@dataclass
class Generators:
    """The generator runs B00 and X00 need, started first so that they run beside everything
    else: for each twin one `--check --emit` (the check and the first emission from one build)
    and one `--emit`; and T05's `--check` (B00: T05's reference unchanged and still derived)."""

    scratch: Path
    runs: dict[str, subprocess.Popen[str]]
    outputs: dict[str, tuple[int, str]] = field(default_factory=dict)

    @classmethod
    def start(cls, scratch: Path) -> Generators:
        def launch(script: Path, *arguments: str) -> subprocess.Popen[str]:
            return subprocess.Popen(  # noqa: S603
                [sys.executable, str(script), *arguments],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=ROOT,
            )

        return cls(
            scratch,
            {
                "t05b_check": launch(GENERATOR, "--check", "--emit", str(scratch / "t05b_a.yaml")),
                "t05b_emit": launch(GENERATOR, "--emit", str(scratch / "t05b_b.yaml")),
                "f9_check": launch(F9_GENERATOR, "--check", "--emit", str(scratch / "f9_a.yaml")),
                "f9_emit": launch(F9_GENERATOR, "--emit", str(scratch / "f9_b.yaml")),
                "t05_check": launch(T05_GENERATOR, "--check"),
            },
        )

    def output(self, name: str) -> tuple[int, str]:
        """The run's exit code and output, waited for once."""
        if name not in self.outputs:
            stdout, _ = self.runs[name].communicate()
            self.outputs[name] = (self.runs[name].returncode, stdout)
        return self.outputs[name]


def _imported_siblings(script: Path, seen: set[str]) -> list[str]:
    """Every import of `script` and of the sibling scripts it imports, transitively, by name."""
    names: list[str] = []
    tree = ast.parse(script.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        found: list[str] = []
        if isinstance(node, ast.Import):
            found = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            found = [node.module]
        for name in found:
            names.append(f"{script.name}: {name}")
            sibling = script.parent / f"{name.split('.')[0]}.py"
            if sibling.is_file() and sibling.name not in seen:
                seen.add(sibling.name)
                names += _imported_siblings(sibling, seen)
    return names


def _generator_value(
    generators: Generators,
    prefix: str,
    script: Path,
    reference: Path,
    spec: Path,
    ref: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One twin's self-check (T05's A00 pattern): `--check` passes with the claims its YAML lists
    and prints exactly that list; the YAML's digest is in the specification's header; `--emit`
    twice gives identical bytes, equal to the committed file; the twin and its siblings import
    nothing from `openflowsheet` or `benchmarks` (the syntax tree)."""
    check_code, output = generators.output(f"{prefix}_check")
    emit_code, _ = generators.output(f"{prefix}_emit")
    counted = re.findall(r"^(\d+) claims passed", output, flags=re.MULTILINE)
    printed = re.findall(r"^ok  (.+)$", output, flags=re.MULTILINE)
    digest = file_sha256(reference)
    header = spec.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    first = generators.scratch / f"{prefix}_a.yaml"
    second = generators.scratch / f"{prefix}_b.yaml"
    emitted = first.is_file() and second.is_file()
    imports = _imported_siblings(script, {script.name})
    forbidden = [
        entry
        for entry in imports
        if entry.split(": ", 1)[1].split(".")[0] in {"openflowsheet", "benchmarks"}
    ]
    registered = list(ref["generator_claims"]["names"])
    value = {
        "check_exit_code": check_code,
        "second_emit_exit_code": emit_code,
        "claims_passed": int(counted[-1]) if counted else None,
        "claims_listed_in_the_yaml": int(ref["generator_claims"]["count"]),
        "printed_claims_equal_the_yamls_list": printed == registered,
        "reference_sha256": digest,
        "digest_in_spec_header": digest in header,
        "emit_twice_identical": emitted and first.read_bytes() == second.read_bytes(),
        "emit_equals_committed": emitted and first.read_bytes() == reference.read_bytes(),
        "scripts_read": sorted({entry.split(": ", 1)[0] for entry in imports}),
        "forbidden_imports": forbidden,
    }
    expected = {
        "check_exit_code": 0,
        "second_emit_exit_code": 0,
        "claims_passed": len(registered),
        "claims_listed_in_the_yaml": len(registered),
        "printed_claims_equal_the_yamls_list": True,
        "digest_in_spec_header": True,
        "emit_twice_identical": True,
        "emit_equals_committed": True,
        "forbidden_imports": [],
    }
    return value, expected


def _reference_files(names: Sequence[str]) -> dict[str, str]:
    return {
        name: file_sha256(ROOT / "benchmarks" / name / "reference_values.yaml") for name in names
    }


def _b00(generators: Generators) -> tuple[bool, Any, Any]:
    value, expected = _generator_value(generators, "t05b", GENERATOR, REFERENCE, SPEC, REF)
    t05_code, t05_output = generators.output("t05_check")
    counted = re.findall(r"^(\d+) claims passed", t05_output, flags=re.MULTILINE)
    value["reference_sha256_registered"] = REFERENCE_FILES["t05b"]
    value["t05_reference_check_exit_code"] = t05_code
    value["t05_reference_claims_passed"] = int(counted[-1]) if counted else None
    value["t05_reference_sha256"] = _reference_files(["t05"])["t05"]
    expected.update(
        {
            "reference_sha256": REFERENCE_FILES["t05b"],
            "t05_reference_check_exit_code": 0,
            "t05_reference_sha256": REFERENCE_FILES["t05"],
        }
    )
    ok = all(value[key] == expected[key] for key in expected)
    return ok, value, expected


def _x00(generators: Generators) -> tuple[bool, Any, Any]:
    value, expected = _generator_value(
        generators, "f9", F9_GENERATOR, F9_REFERENCE, F9_SPEC, F9_REF
    )
    value["reference_files"] = _reference_files(["t04", "t05", "t05b", "k04"])
    expected.update(
        {
            "reference_sha256": REFERENCE_FILES["k04f9"],
            "reference_files": {
                name: REFERENCE_FILES[name] for name in ("t04", "t05", "t05b", "k04")
            },
        }
    )
    ok = all(value[key] == expected[key] for key in expected)
    return ok, value, expected


# ------------------------------------------------------------------ B21, B22, X19


def _strings(node: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for key, item in node.items():
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item, f"{path}[]")
    elif isinstance(node, str):
        yield path, node


def _ci_documents(directory: Path) -> dict[str, dict[str, Any]]:
    """The downloaded `identity.json` of each platform, by artifact directory name."""
    return {
        path.parent.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.rglob("identity.json"))
    }


#: The CI artifact directory of the x86-64 runner, whose T02 floats are the registered bytes.
X86_ARTIFACT = "structural-identity-ubuntu-latest"


def _ci_floats(directory: Path) -> dict[str, Any]:
    """The downloaded `t02-floats.json` of each platform: its SHA-256 by artifact directory, and
    the CI comparator's rule across the pair (R-026, ADR 0007 D2 as amended: least-squares floats
    compared within their comparability window, never byte for byte) — `run.compare.differences`
    of every platform's floats against the x86-64 runner's, as the `identity` job computes them."""
    from openflowsheet.run.compare import differences

    paths = {path.parent.name: path for path in sorted(directory.rglob("t02-floats.json"))}
    loaded = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    reference = loaded.get(X86_ARTIFACT)
    return {
        "sha256": {name: file_sha256(path) for name, path in paths.items()},
        "differences_from_x86_64": {
            name: differences(
                document, reference, "t02_floats", policy_id="K04-numerical-policy-v1"
            )
            if reference is not None
            else [f"no {X86_ARTIFACT} artifact"]
            for name, document in loaded.items()
        },
    }


@cache
def _t02_floats_sha256() -> str:
    """T02's floats artifact on this machine (`t02_identity.py --floats-out`, as CI emits it)."""
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "t02-floats.json"
        subprocess.run(  # noqa: S603
            [sys.executable, str(ROOT / "scripts" / "t02_identity.py"), "--floats-out", str(out)],
            capture_output=True,
            cwd=ROOT,
            check=True,
        )
        return file_sha256(out)


def _identities_local() -> dict[str, Any]:
    """The registered identities on this machine (`docs/t05b-measurements.md`'s protocol)."""
    from openflowsheet.verify.certificate import CheckPolicy

    document = identity_document()
    return {
        "syn001_py_sha256": file_sha256(SOURCE / "thermo" / "syn001.py"),
        "identity_document_sha256": _document_sha256(document),
        "identity_minus_t05b_sha256": _document_sha256(
            {key: item for key, item in document.items() if key != "t05b"}
        ),
        "identity_minus_t05_t05b_sha256": _document_sha256(
            {key: item for key, item in document.items() if key not in ("t05", "t05b")}
        ),
        "t05_key_sha256": _key_sha256(document["t05"]),
        "t05b_key_sha256": _key_sha256(document["t05b"]),
        "structural_sha256": document["structural_sha256"],
        "check_policy_sha256": CheckPolicy().sha256,
        "t02_floats_sha256": _t02_floats_sha256(),
    }


@cache
def _r015_fixtures() -> dict[str, Any]:
    """R-015: every committed schema fixture that a generator emits, compared with what it emits
    today (K03's, K04's, K05's and T04's generators; T05 and T05b add none)."""
    from k03_schema_fixtures import documents as k03_documents
    from k04_schema_fixtures import documents as k04_documents
    from k05_schema_fixtures import documents as k05_documents
    from t04_schema_fixtures import documents as t04_documents

    from openflowsheet.run.compare import differences

    compared: dict[str, Any] = {}
    for generator, emit in (
        ("k03_schema_fixtures", k03_documents),
        ("k04_schema_fixtures", k04_documents),
        ("k05_schema_fixtures", k05_documents),
        ("t04_schema_fixtures", t04_documents),
    ):
        for name, emitted in emit().items():
            committed = json.loads((FIXTURES / "schemas" / name).read_text(encoding="utf-8"))
            compared[name] = {
                "generator": generator,
                "differences": differences(emitted, committed, policy_id="K04-numerical-policy-v1")[
                    :5
                ],
            }
    return compared


#: B21's "every K02–T05 test passes unchanged except the retired T05 A28–A30 tests": each K02–T05
#: test file edited since the W0.1 base, with the registered change that edits it. A file edited
#: outside this table is a departure.
SANCTIONED_TEST_EDITS = {
    "tests/test_t05_dormant_outlet.py": "T05 A28 retired, rewritten against B15 (T05b spec §16)",
    "tests/test_t05_ph_kernel.py": "T05 A29 retired, its near-pure grid rewritten against B01 "
    "(T05b spec §16)",
    "tests/test_t05_single_component_eo.py": "T05 A30 retired, rewritten against B08–B09 "
    "(T05b spec §16)",
    "tests/test_t05_manifests.py": "T05 A01 on the manifests' limitation texts of T05b spec §16 "
    "(W8, W10.5, W10.6c)",
    "tests/test_t05_table_independence.py": "B23: the verifier's dormancy table from its own "
    "transcription, by that file's rule (W7b)",
    "tests/test_t05_w1d_verifier.py": "K04-F9 §10.7: W1.d's harness compares the engines at one "
    "state (X22)",
    "tests/test_t04_certificate.py": "K04-F9 §10.1–§10.2: T04 A32's 5e-4 W half and A33 "
    "re-registered (X05, X06)",
    "tests/test_t04_edge3.py": "K04-F9 §10.8: T04's fixtures regenerated for "
    "`transformations.projection` (X17)",
    "tests/test_k05_schemas.py": "Q-S7: the run_manifest fixture's certificate hash compared "
    "with the emitted one (R-015)",
}


def _test_edits() -> dict[str, Any]:
    """The K02–T05 test files edited since the W0.1 base, with the lines added and removed and
    the commits that edited each."""
    numstat = [
        line.split("\t")
        for line in _git("diff", "--numstat", BASE_COMMIT, "HEAD", "--", "tests/").splitlines()
    ]
    edited = {
        path: {"added": int(plus), "removed": int(minus)}
        for plus, minus, path in numstat
        if re.fullmatch(r"tests/test_(k0[2-5]|t0[2-5])_[a-z0-9_]+\.py", path)
        and _git("cat-file", "-t", f"{BASE_COMMIT}:{path}").strip() == "blob"
    }
    for path, entry in edited.items():
        entry["commits"] = _git(
            "log", "--format=%h %s", f"{BASE_COMMIT}..HEAD", "--", path
        ).splitlines()
    return edited


def _b21(gate: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    local = _identities_local()
    base = subprocess.run(  # noqa: S603
        ["git", "show", "main:src/openflowsheet/thermo/syn001.py"],  # noqa: S607
        capture_output=True,
        cwd=ROOT,
        check=True,
    ).stdout
    syn001_equal_to_main = (SOURCE / "thermo" / "syn001.py").read_bytes() == base
    ledger.equal("thermo/syn001.py byte-identical to main", syn001_equal_to_main, True)
    for key in (
        "syn001_py_sha256",
        "identity_minus_t05_t05b_sha256",
        "structural_sha256",
        "check_policy_sha256",
        "t02_floats_sha256",
    ):
        ledger.equal(key, local[key], REGISTERED[key])
    r015 = _r015_fixtures()
    differing = sorted(name for name, entry in r015.items() if entry["differences"])
    ledger.equal("R-015: fixtures regenerate identically", differing, [])
    edits = _test_edits()
    unsanctioned = sorted(path for path in edits if path not in SANCTIONED_TEST_EDITS)
    ledger.equal("K02–T05 test files edited outside the registered changes", unsanctioned, [])
    counts = gate["pytest_counts"]
    ledger.true("the gate passed", bool(gate["passed"]))
    ledger.equal("the gate's outcomes", sorted(counts), sorted(set(counts) & {"passed", "xfailed"}))
    value = {
        "syn001_py": {"sha256": local["syn001_py_sha256"], "equal_to_main": syn001_equal_to_main},
        "identity_minus_t05_t05b_sha256": local["identity_minus_t05_t05b_sha256"],
        "structural_sha256": local["structural_sha256"],
        "check_policy_sha256": local["check_policy_sha256"],
        "t02_floats_sha256": local["t02_floats_sha256"],
        "fixtures_r015": {
            "compared": len(r015),
            "generators": sorted({entry["generator"] for entry in r015.values()}),
            "differences": differing,
        },
        "k02_t05_test_files_edited": {
            path: {**entry, "registered_change": SANCTIONED_TEST_EDITS.get(path)}
            for path, entry in edits.items()
        },
        "gate": {
            "passed": gate["passed"],
            "pytest_counts": counts,
            "collected": gate["collected"],
            "count_at_base": REGISTERED["gate_count_at_base"],
            "count_now": counts.get("passed", 0) + counts.get("xfailed", 0),
            "added_minus_retired": counts.get("passed", 0)
            + counts.get("xfailed", 0)
            - REGISTERED["gate_count_at_base"],
        },
        "departures": ledger.departures,
    }
    expected = {
        "syn001_py": {"sha256": REGISTERED["syn001_py_sha256"], "equal_to_main": True},
        "identity_minus_t05_t05b_sha256": REGISTERED["identity_minus_t05_t05b_sha256"],
        "structural_sha256": REGISTERED["structural_sha256"],
        "check_policy_sha256": REGISTERED["check_policy_sha256"],
        "t02_floats_sha256": REGISTERED["t02_floats_sha256"],
        "fixtures_r015": {"differences": []},
        "k02_t05_test_files_edited": "only the registered changes, each named",
        "gate": "passed; both counts reported (W0.1's 2548 and today's)",
    }
    return ledger.ok, value, expected


def _b22_local() -> tuple[bool, dict[str, Any]]:
    """B22's local half: the `t05b` key's cases, its R0 audit, the same twice, its registered
    hash (W9.4's re-registration), and every other key unchanged."""
    from t05b_identity import CONFLICTS, FULL, OUTCOME_ONLY, identity

    from openflowsheet.run.identity import floats_in

    ledger = Ledger()
    document = identity_document()
    key = document["t05b"]
    second = json.loads(json.dumps(identity(), allow_nan=False))
    local = _identities_local()
    strings = list(_strings(key))
    digests = sorted(
        {
            path.split(".", 2)[-1]
            for path, text in strings
            if HEX64.search(text)
            and path.rsplit(".", 1)[-1]
            not in ("constants_sha256", "model_version", "variable_ids_sha256")
        }
    )
    messages = {case: entry.get("message") for case, entry in key.items()}
    value = {
        "cases": list(key),
        "outcomes": {case: entry.get("outcome") for case, entry in key.items()},
        "verification_status": {
            case: entry["certificate"]["verification_status"]
            for case, entry in key.items()
            if isinstance(entry.get("certificate"), dict)
        },
        "messages": messages,
        "floats": floats_in(key)[:10],
        "digests_outside_declared_inputs": digests[:10],
        "float_shaped_messages": sorted(
            case for case, text in messages.items() if text and FLOAT.search(text)
        ),
        "same_twice": second == key,
        "t05b_key_sha256": local["t05b_key_sha256"],
        "t05_key_sha256": local["t05_key_sha256"],
        "identity_minus_t05b_sha256": local["identity_minus_t05b_sha256"],
        "identity_document_sha256": local["identity_document_sha256"],
    }
    expected_cases = [*FULL, *CONFLICTS, *OUTCOME_ONLY]
    ledger.equal("cases", value["cases"], expected_cases)
    ledger.equal("floats", value["floats"], [])
    ledger.equal("digests outside declared inputs", value["digests_outside_declared_inputs"], [])
    ledger.equal("float-shaped messages", value["float_shaped_messages"], [])
    ledger.equal("same twice", value["same_twice"], True)
    for name in (
        "t05b_key_sha256",
        "t05_key_sha256",
        "identity_minus_t05b_sha256",
        "identity_document_sha256",
    ):
        ledger.equal(name, value[name], REGISTERED[name])
    for case in CONFLICTS:
        expected = REF["zero_flow_conflicts"][case]["expected"]
        ledger.equal(
            f"{case}",
            key[case],
            {"outcome": "SPECIFICATION_CONFLICT", "message": expected["message"]},
        )
    ledger.equal("NP-G outcome only", key.get("NP-G"), {"outcome": "CONVERGED"})
    value["departures"] = ledger.departures
    return ledger.ok, value


def _b22(identities: Path | None) -> dict[str, Any]:
    description = DESCRIPTIONS["B22"]
    expected: dict[str, Any] = {
        "t05b_key_sha256": REGISTERED["t05b_key_sha256"],
        "t05_key_sha256": REGISTERED["t05_key_sha256"],
        "identity_minus_t05b_sha256": REGISTERED["identity_minus_t05b_sha256"],
        "floats": [],
        "same_twice": True,
        "ci": {
            "platforms": 2,
            "identity_differences": [],
            "t05b_equal": True,
            "t05b_equal_to_this_machines": True,
        },
    }
    try:
        local, value = _b22_local()
    except Exception as error:  # noqa: BLE001
        return check(
            "T05b.B22", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("T05b.B22", description, "unsupported" if local else "fail", value, expected)
    documents = _ci_documents(identities)
    names = sorted(documents)
    differing: list[str] = [] if len(names) >= 2 else [f"two platforms needed; found {len(names)}"]
    first = documents[names[0]] if names else {}
    for name in names[1:]:
        other = documents[name]
        differing += [
            f"{key}: {names[0]} != {name}"
            for key in sorted(set(first) | set(other))
            if first.get(key) != other.get(key)
        ]
    keys = [document.get("t05b") for document in documents.values()]
    mine = identity_document()["t05b"]
    value["ci"] = {
        "platforms": len(names),
        "identity_differences": differing,
        "t05b_equal": len(keys) >= 2 and bool(keys[0]) and all(item == keys[0] for item in keys),
        "t05b_equal_to_this_machines": bool(keys) and all(item == mine for item in keys),
        "artifact_sha256": {
            str(path.relative_to(identities)): file_sha256(path)
            for path in sorted(identities.rglob("identity.json"))
        },
    }
    agrees = all(value["ci"][key] == expected["ci"][key] for key in expected["ci"])
    return check("T05b.B22", description, verdict(local and agrees), value, expected)


def _x19(identities: Path | None) -> dict[str, Any]:
    description = DESCRIPTIONS["X19"]
    keys = (
        "identity_minus_t05b_sha256",
        "identity_minus_t05_t05b_sha256",
        "t05_key_sha256",
        "structural_sha256",
        "check_policy_sha256",
        "t02_floats_sha256",
        "syn001_py_sha256",
    )
    expected: dict[str, Any] = {key: REGISTERED[key] for key in keys}
    expected["ci"] = {
        "platforms": 2,
        "identity_minus_t05b_sha256": [REGISTERED["identity_minus_t05b_sha256"]] * 2,
        "structural_sha256": [REGISTERED["structural_sha256"]] * 2,
        "t02_floats_x86_64_sha256": REGISTERED["t02_floats_sha256"],
        "t02_floats_platforms": 2,
        "t02_floats_differences": [],
    }
    try:
        local_values = _identities_local()
    except Exception as error:  # noqa: BLE001
        return check(
            "K04F9.X19", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    value: dict[str, Any] = {key: local_values[key] for key in keys}
    local = all(value[key] == expected[key] for key in keys)
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("K04F9.X19", description, "unsupported" if local else "fail", value, expected)
    documents = _ci_documents(identities)
    floats = _ci_floats(identities)
    value["ci"] = {
        "platforms": len(documents),
        "identity_minus_t05b_sha256": [
            _document_sha256({key: item for key, item in document.items() if key != "t05b"})
            for document in documents.values()
        ],
        "structural_sha256": [document.get("structural_sha256") for document in documents.values()],
        "t02_floats_x86_64_sha256": floats["sha256"].get(X86_ARTIFACT),
        "t02_floats_platforms": len(floats["sha256"]),
        "t02_floats_differences": [
            found for listed in floats["differences_from_x86_64"].values() for found in listed
        ],
        "t02_floats_sha256_by_platform": floats["sha256"],
    }
    agrees = all(value["ci"][key] == expected["ci"][key] for key in expected["ci"])
    return check("K04F9.X19", description, verdict(local and agrees), value, expected)


# ------------------------------------------------------------------------------------ gate


def _gate(gate_stdout: Path) -> dict[str, Any]:
    """The gate's log, and the tests `pytest --collect-only` finds here, by package family."""
    text = gate_stdout.read_text(encoding="utf-8")
    counts = _pytest_counts(text)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    collected = [line for line in completed.stdout.splitlines() if "::" in line]
    return {
        "passed": "=== check.sh: PASSED ===" in text and completed.returncode == 0,
        "pytest_counts": counts,
        "collected": len(collected),
        "families": {
            family: sum(1 for line in collected if line.startswith(f"tests/test_{family}_"))
            for family in ("k02", "k03", "k04", "k05", "t02", "t03", "t04", "t05", "t05b", "k04f9")
        },
    }


def _pytest_counts(text: str) -> dict[str, int]:
    """The last pytest summary line (`3135 passed in 175.9s`), as counts by word."""
    lines = re.findall(r"^((?:\d+ [a-z]+(?:, )?)+) in [\d.]+s", text, flags=re.MULTILINE)
    if not lines:
        return {}
    return {word: int(count) for count, word in re.findall(r"(\d+) ([a-z]+)", lines[-1])}


def _schema_refuses_requirement(identifier: str) -> bool:
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (ROOT / "schemas" / "evidence-manifest.schema.json").read_text(encoding="utf-8")
    )
    return bool(
        list(Draft202012Validator(schema["properties"]["requirements"]).iter_errors([identifier]))
    )


def _validator(name: str) -> Any:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "schemas").glob("*.schema.json")
    ]
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document))
        for document in documents
        if "$id" in document
    )
    (schema,) = [
        document for document in documents if str(document.get("$id", "")).endswith("/" + name)
    ]
    return Draft202012Validator(schema, registry=registry)


def _status(checks: Sequence[Mapping[str, Any]]) -> str:
    """`tested` when nothing failed. An `unsupported` or `not_applicable` check carries its
    reason in its own value and in `limitations`; a `fail` anywhere leaves the package
    `implemented`, never `tested`."""
    return "implemented" if any(entry["result"] == "fail" for entry in checks) else "tested"


def _case_hash() -> str:
    """One digest over the two registered references and the case builders, in that order."""
    digest = hashlib.sha256()
    for path in (
        REFERENCE,
        F9_REFERENCE,
        ROOT / "tests" / "t05b_support.py",
        ROOT / "tests" / "k04f9_support.py",
    ):
        digest.update(path.read_bytes())
    return digest.hexdigest()


# ----------------------------------------------------------------------------- limitations


def _limitations(identities: bool, ci_run: bool, refused: Sequence[str]) -> list[str]:
    stated = [
        # T05b spec §17 and §18, restated item by item.
        "T05b spec §17, §18 Q9 (Frank's; default: not in T05b, queued as a K04 follow-up beside "
        "T04 Q8): a lifted flash whose root lies exactly on its dew or bubble point with the "
        "other product zero — a zero-duty, zero-pressure-drop flash fed a saturated vapour or "
        "liquid — is not certified. A solve that ends there is certified UNVERIFIED with "
        "regularity RANK_DEFICIENT, rank loss one per such flash (B31 (b): CH-UP, CH-DZ12, CH-3). "
        "A solve that approaches it in the two-phase form can stop at a nearby state, which the "
        "verifier fails as a detected false success: six runs of B34 (a)'s sweep, "
        "(Q2, Q_s, Q_t) = (0, 90/115/125 kW, 30 kW) in both declaration orders, end CONVERGED "
        "and are certified FAILED with false_success_detected. Nothing false is certified. Why "
        "the region's per-row test passed while the verifier's balance of the same unit failed "
        "at the same state (by at least 0.37 mW) is not established; it goes with Q9 to the K04 "
        "follow-up.",
        "T05b spec §17: a zero-flow conflict is not searched past. SPECIFICATION_CONFLICT "
        "closes the region when a swapped row fails after the contract's closure checks found no "
        "lifted regime to change (DZ-11, DZ-2C); in a recycle another signature might have a "
        "root, which T05b does not search for (a T04 decision). The outcome is typed, never a "
        "false CONVERGED.",
        "T05b spec §17: a model outside SYN-001's library whose dormant outlet temperature no "
        "row reads is not covered until it registers a dormancy form (§7.6); the regularity "
        "screen reports it (RANK_DEFICIENT, UNVERIFIED), typed.",
        "T05b spec §17: no second-law judgement at a dormant exchanger side; the terminal "
        "differences are not_applicable there (§9.3), and nothing is claimed about a dormant "
        "side's label temperature beyond its row.",
        "T05b spec §17: traversal accuracy downstream of a degenerate lifted stream is not "
        "established — the traversal passes (n, T, P), so a consumer's causal start misplaces "
        "the stream's latent heat (SC-3 is registered on exactly this); the EO solve corrects "
        "it. Starts, not results.",
        "T05b spec §17: a TP-specified outlet of one component at exactly T_sat (a K02 heater "
        "with T_spec = T_sat) has no row for β; the regularity screen reports it "
        "(RANK_DEFICIENT, UNVERIFIED), the correct outcome of an ill-posed specification.",
        "T05b spec §17: conditioning near β → 0 or 1 for one component is decided by the "
        "regularity screen (the reduced determinant is proportional to V L); no registered case "
        "is within β = 0.016 of either end.",
        "T05b spec §17: no real substance (SYN-001 only: invented constants, ideal VLE) — "
        "agreement with the twins is numerical verification, not empirical validation; the "
        "kernel's cost at large band routes inside a region's property budget is measured only "
        "on the registered cases (W0.6, B32 (b)); performance is not established.",
        "T05b spec §17 (closed by ADR 0013, kept for the record): near-pure EO certification in "
        "T04 F9's band. After ADR 0013 every W0.7 run from 3e-8 to 3e-6 mol/s is CONVERGED and "
        "VERIFIED; the former band is D3's unresolved routing (§18 Q5).",
        # K04-F9 spec §11.
        "K04-F9 spec §11: a certificate certifies residual accuracy at the registered "
        "tolerances (K04 §7.4); the projection is an evaluation point for the independent "
        "comparisons, not a promise about the final state's distance from the root beyond the "
        "disclosed b, which bounds nothing at a stated confidence (X26 asserts the realized "
        "deviation of the registered comparisons only).",
        "K04-F9 spec §11: verdicts with a residual near_threshold flag are not promised across "
        "platforms under ADR 0007 D2.4 — 15 A02 family states, DZ-3, DZ-10, NP-G and PRJ-B2 carry "
        "flags on residual rows at the final state (Newton stopped at 0.1–0.4 τ). B22's key keeps "
        "DZ-3's, DZ-10's and NP-2's flags as R0 fields (Q-S8 (5)) and NP-G's outcome only.",
        "K04-F9 spec §11: a state whose projection is refused is judged at its final state, F9's "
        "exposure intact — a possible false alarm, never a false pass; linearly convergent stops "
        "(T04 F3) are judged at the final state; near-pure heater-style splits in the unresolved "
        "band outside any registered case, and near-pure mixtures far from 2 mol/s, are covered "
        "by the same rules but not measured.",
        "K04-F9 spec §11: T05 §11.5's b ≤ 1e-8 rule for C1–C3 has the form X26 abandoned; C1–C3 "
        "meet it and it is left to a T05/K04 revision.",
        # Open questions at their defaults, and findings handed on.
        "Scope items at their defaults: T05b §18 Q7 (a signature item keyed U.port under v2 is "
        "no frozen-schema change — Frank's, if he reads the freeze otherwise) and Q9 (above); "
        "K04-F9 §12 Q1 (F10's five checks are not added to SYN-001's legacy set, D4 — Frank's; "
        "it would move SYN-001's identity), Q4 (material balances are not judged at the "
        "projection), Q5 (the projection's step is not recorded as a float), Q6 (the T05b "
        "generator's INJ-B2 entry is kept as PRJ-B2's final-state value). The re-review's N-W5 "
        "(augment's recursion) and N-W6 (the release acts only at α_max = 0) are not ruled and "
        "stay on the design lane's list (T05b spec §20 W10).",
        "K04-F9 finding F4, handed on: K04 §5.4 names the check policy as the tolerance table "
        "plus §7's thresholds and the required-check list, while CheckPolicy.sha256 covers the "
        "tolerance table only; pre-existing, for a later K04 revision.",
        "Finding handed on (measured by this manifest's X24, 20 seeds): the certificate's "
        "inverse_one_norm_estimate, rcond_1 and solution_error_bound_scaled come from scipy's "
        "onenormest, which draws a starting column from numpy's global random state, so at T05's "
        "C2 and C3 they depend on what ran earlier in the process (C2's bound 3.009e-15 to "
        "3.880e-15, C3's 2.990e-9 to 3.396e-9); no R0 field moves (verdicts, ids, results, flags, "
        "regularity status), every other registered certificate is unaffected, and X24 judges R0 "
        "identity as it states. Floats of C2's and C3's certificates in this manifest are "
        "therefore not reproducible bit for bit across process histories; for the design lane.",
        "B11's pre-change clause (before T05b the same revision ends INITIALIZATION_FAILED, "
        "initializer_failed(U-PHF2): inadmissible_phase(inlet, VAPOR)) is W0.1's measurement at "
        "the base b8c6442 (docs/t05b-measurements.md, W0.1), cited, not re-measured: the "
        "pre-change code does not exist at the head (Q-S3 (4)).",
        "T05b spec §17 and K04-F9 §11: human numerical and process-modelling review is not "
        "claimed; `review` is `pending` in both fields and no agent sets it.",
    ]
    stated += [
        f"ADR 0012/0013 list {identifier} among the requirements served; the frozen "
        f"evidence-manifest schema takes D/A ids only (measured: it refuses `{identifier}`), so "
        "`requirements` omits it and `docs/requirements.yaml` carries it (T02's to T05's "
        "precedent for V-items)."
        for identifier in refused
    ]
    if not identities:
        stated.append(
            "The cross-platform halves of B22 (the `t05b` key on the CI pair) and X19 (the "
            "identities on the CI pair) were not measured by this run: no `--identities` "
            "directory was given, so those checks are `unsupported`, not `pass`."
        )
    if not ci_run:
        stated.append(
            "No CI run was named (`--ci-run`), so `commands` records the local gate only."
        )
    return stated


#: The files a measured commit may add to the CI run's head commit: this generator, the evidence
#: tree and the design lane's review notes (`docs/reviews/*.md`), none of which a CI job's tests or
#: its identity document read.
_EVIDENCE_ONLY = re.compile(
    r"^(scripts/t05b_evidence_manifest\.py|evidence/.*|docs/reviews/[A-Za-z0-9_.-]+\.md)$"
)


def _ci_commit_difference(ci_commit: str, commit: str) -> str:
    """The files by which the measured commit differs from the CI run's head commit (measured by
    `git diff`); anything beyond `_EVIDENCE_ONLY` refuses to write a manifest that would claim
    the CI pair for code it did not run."""
    changed = _git("diff", "--name-only", ci_commit, commit).split()
    foreign = [path for path in changed if not _EVIDENCE_ONLY.match(path)]
    if foreign:
        raise SystemExit(f"the CI run's commit {ci_commit} differs from {commit} in {foreign}")
    return (
        f"The CI pair was measured at the run's head commit {ci_commit}, not at {commit}: "
        f"`git diff --name-only` between them lists only {changed}, which neither CI job's tests "
        "nor its identity document import; this machine's `t05b` key and identities at the "
        "measured commit are compared with both artifacts in B22 and X19, and the gate recorded "
        "in `commands` ran at the measured commit."
    )


# ---------------------------------------------------------------------------- the checks


#: One paragraph per assertion: what is measured, in the manifest's words (the value says how).
DESCRIPTIONS: dict[str, str] = {
    "B00": "Generator self-check: `t05b_reference.py --check` passes with the number of claims "
    "the committed YAML lists (630 after the Q-S9 addendum; 585 and 454 before) and prints "
    "exactly that list; the committed YAML's SHA-256 is the one in the specification header "
    "(`cf1a8606…`); `--emit` twice (two processes) gives identical bytes, equal to the committed "
    "file; the twin and every sibling script it imports, transitively, import nothing from "
    "`openflowsheet` or `benchmarks` (the syntax tree); `t05_reference.py --check` passes and "
    "`benchmarks/t05/reference_values.yaml` is unchanged (`af4a543f…`).",
    "B21": "Bit identity and inertness: `thermo/syn001.py` byte-identical to `main` (and "
    "`75c9d5ba…`); the K05 identity document minus {`t05`, `t05b`} `b364bb3d…`, structural "
    "`4ce030ca…`, K04 `check_policy_sha256` `21c44e10…`, T02's floats `9a8a5baf…` on this "
    "machine; every schema fixture a generator emits regenerates identically (R-015: K03's, "
    "K04's, K05's, T04's generators); every K02–T05 test file edited since the W0.1 base "
    "`b8c6442` is one of the registered changes (T05's retired A28–A30 tests, §16's limitation "
    "texts, K04-F9 §10's amendments, Q-S7), each named with its commits and lines; the gate "
    "passes, and both counts are reported (W0.1's 2548 and today's).",
    "B22": "R0 identity: the K05 identity document's `t05b` key (`scripts/t05b_identity.py`) on "
    "this machine — the cases in B22's order (SC-1…SC-4, NP-1…NP-3, DZ-1…DZ-10, DZ-12 with the "
    "full R0 projection; DZ-11, DZ-2C outcome and message; NP-G outcome only), floats-free, "
    "digests only of declared inputs, no float-shaped message, the same twice, hashing to the "
    "key W9.4 re-registered (`4f29500e…`, reason Q-S11 (a)); the `t05` key (`ddbd0f71…`) and "
    "the document minus `t05b` (`622463f5…`) unchanged. The CI pair's half: every key of the "
    "two platforms' documents equal, and the `t05b` key equal to this machine's (`unsupported` "
    "without the downloaded artifacts).",
    "X00": "Generator self-check: `k04f9_reference.py --check` passes with the 25 claims the "
    "committed YAML lists and prints exactly that list; the YAML's SHA-256 is the "
    "specification's (`73be8df9…`); `--emit` twice gives identical bytes, equal to the "
    "committed file; the twin and its sibling twins import nothing from `openflowsheet` or "
    "`benchmarks` (the syntax tree); T04's, T05's, T05b's and K04's reference files are the "
    "registered ones.",
    "X19": "Identity: K05's identity document minus `t05b` `622463f5…` (minus `t05` too "
    "`b364bb3d…`; the `t05` key `ddbd0f71…`), structural `4ce030ca…`, `check_policy_sha256` "
    "`21c44e10…`, T02's floats `9a8a5baf…`, `thermo/syn001.py` `75c9d5ba…` — on this machine "
    "(x86-64); and from the CI artifacts of x86-64 and aarch64: the document minus `t05b` and "
    "the structural hash on both, T02's floats `9a8a5baf…` on x86-64 and aarch64's agreeing "
    "with them under the CI comparator's rule (R-026: `run.compare.differences`, the "
    "comparability window, not bytes) — `unsupported` without the artifacts.",
}

#: The measurements of the checks that need nothing but the process: `id -> measure`. The
#: generator, identity and gate checks (B00, B21, B22, X00, X19) are wired in `build`.
MEASURES: dict[str, Measure] = {}


# ---------------------------------------------------------------- B01-B06, B19, B23: the unit layer


def _p1_grid() -> dict[str, tuple[PHState, tuple[float, ...], float]]:
    """B01's 40 `ph_state` calls, once each (the test's `grid_inputs`): `id -> (answer, n, H*)`."""
    found: dict[str, tuple[PHState, tuple[float, ...], float]] = {}
    for state_id, state in REF["kernel_grid"].items():
        n, pressure, target = kernel_fixtures.grid_inputs(state)
        found[state_id] = (ph_state(PROVIDER, n, pressure, target, CONTEXT), n, target)
    return found


def _b01() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """Per grid state: status, route (against the test's pinned `B01_BRACKET` and the twin's
    53-bit emulation), the §5.3 rows evaluated from the provider (the test's `rows`) as ratios to
    `τ_flow`, `τ_eq`, `τ_E`, and the errors of `T`, `V` and every flowing `q_i` against
    `ref.kernel_grid` (§13's grid tolerances). Also §13's band-route floor (the test's
    `test_b01_the_band_routes_floor`)."""
    ledger = Ledger()
    tau = {
        "material": kernel_fixtures.TAU_FLOW,
        "equilibrium": kernel_fixtures.TAU_EQ,
        "energy": kernel_fixtures.TAU_E,
    }
    grid = {"T": kernel_fixtures.GRID_T, "V": kernel_fixtures.GRID_V, "q": kernel_fixtures.GRID_Q}
    per_state: dict[str, Any] = {}
    row_ratios: dict[str, dict[str, float]] = {kind: {} for kind in tau}
    errors: dict[str, dict[str, float]] = {kind: {} for kind in grid}
    band_floor: dict[str, dict[str, float]] = {kind: {} for kind in grid}
    band_evaluations: dict[str, int] = {}
    routes: dict[str, int] = {}
    for state_id, (answer, n, target) in _p1_grid().items():
        state = REF["kernel_grid"][state_id]
        expected = state["expected"]
        entry: dict[str, Any] = {"status": answer.status, "route": answer.route}
        per_state[state_id] = entry
        routes[str(answer.route)] = routes.get(str(answer.route), 0) + 1
        ledger.equal(f"{state_id} status", answer.status, expected["status"])
        ledger.true(f"{state_id} route in {{bracket, band}}", answer.route in {"bracket", "band"})
        epsilon, phi = min(value for value in n if value > 0.0), state_id.rsplit("-", 1)[1]
        if epsilon <= 1e-9 and phi != "0.5":
            ledger.equal(f"{state_id} route at eps ≤ 1e-9, phi ≠ 0.5", answer.route, "band")
        pinned = "bracket" if state_id in kernel_fixtures.B01_BRACKET else "band"
        ledger.equal(f"{state_id} route (regression pin)", answer.route, pinned)
        ledger.equal(
            f"{state_id} route (twin's emulation)", answer.route, state["measured_53_bit"]["route"]
        )
        if answer.status != "ok" or answer.temperature is None or answer.split is None:
            ledger.true(f"{state_id} carries an answer", False)
            continue
        assert answer.split.vapor is not None
        ledger.equal(f"{state_id} signature", answer.split.phase_signature, "TWO_PHASE")
        rows = dict(zip(tau, kernel_fixtures.rows(answer, n, target), strict=True))
        entry["row_ratios"] = {kind: rows[kind] / tau[kind] for kind in tau}
        for kind, ratio in entry["row_ratios"].items():
            row_ratios[kind][state_id] = ratio
            ledger.at_most(f"{state_id} {kind} row / tau", ratio, 1.0)
        found = {
            "T": ledger.within(f"{state_id} T", answer.temperature, expected["T_K"], grid["T"]),
            "V": ledger.within(
                f"{state_id} V", sum(answer.split.vapor.n), expected["V_mol_per_s"], grid["V"]
            ),
        }
        q_errors: list[float] = []
        for index, q in enumerate(expected["vapour_fraction_by_component"]):
            if q is None:
                ledger.true(
                    f"{state_id} q[{index}] not flowing",
                    answer.split.vapor.n[index] == 0.0 and n[index] == 0.0,
                )
                continue
            share = answer.split.vapor.n[index] / n[index]
            q_errors.append(ledger.within(f"{state_id} q[{index}]", share, q, grid["q"]))
        found["q"] = max(q_errors)
        entry["errors"] = found
        for kind, value in found.items():
            errors[kind][state_id] = value
            if answer.route == "band":
                band_floor[kind][state_id] = value
        if answer.route == "band":
            band_evaluations[state_id] = answer.evaluations
            ledger.true(
                f"{state_id} band evaluations in (2, {MAX_BAND_EVALUATIONS}]",
                2 < answer.evaluations <= MAX_BAND_EVALUATIONS,
            )
    # §13's floors on the band route, as the test bounds them (1e-12 K, 1e-14 mol/s, 1e-14).
    floor_bounds = {"T": 1e-12, "V": 1e-14, "q": 1e-14}
    floors = {kind: worst(values) for kind, values in band_floor.items()}
    for kind, bound in floor_bounds.items():
        ledger.at_most(f"band-route floor {kind}", floors[kind]["ratio"], bound)
    value = {
        "states": len(per_state),
        "route_counts": routes,
        "worst_row_ratio": {kind: worst(values) for kind, values in row_ratios.items()},
        "worst_error": {kind: worst(values) for kind, values in errors.items()},
        "band_route_floor": floors,
        "band_route_evaluations": {
            "min": min(band_evaluations.values()),
            "max": max(band_evaluations.values()),
        },
        "per_state": per_state,
        "departures": ledger.departures,
    }
    expected = {
        "states": len(REF["kernel_grid"]),
        "route_counts": {
            "bracket": len(kernel_fixtures.B01_BRACKET),
            "band": len(REF["kernel_grid"]) - len(kernel_fixtures.B01_BRACKET),
        },
        "status": "ok at every state",
        "routes": "the regression pin `test_t05b_kernel.B01_BRACKET` (bracket; band elsewhere), "
        "equal to `ref.kernel_grid.*.measured_53_bit.route`; band at every eps ≤ 1e-9, phi ≠ 0.5",
        "row_ratios": "material, equilibrium, energy rows over tau_flow 3.1e-8 mol/s, tau_eq "
        "9.3e-8 (mol/s)^2, tau_E 1.01e-3 W: each at most 1 (spec §5.3)",
        "grid_tolerances": {"T_K": grid["T"], "V_mol_per_s": grid["V"], "q": grid["q"]},
        "band_route_floor_bounds": floor_bounds,
        "band_route_evaluations": f"in (2, {MAX_BAND_EVALUATIONS}]",
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- B02

#: T05's checks B02 names as passing unchanged (T05 spec §15), run by T05's own generator.
_P1_T05_CHECKS = ("A06", "A07", "A08", "A09", "A10", "A13", "A14")


@cache
def _p1_t05_reference() -> dict[str, Any]:
    return t05m.reference(t05m.REFERENCE)


@cache
def _p1_t05_check(identifier: str) -> tuple[Any, Any]:
    """One of T05's checks as its generator measures it: `(condition, value)`."""
    measure: Callable[[Mapping[str, Any]], tuple[Any, Any, Any]] = getattr(
        t05m, f"_{identifier.lower()}"
    )
    condition, value, _ = measure(_p1_t05_reference())
    return condition, value


def _b02() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """A live run of `scripts/t05b_ph_baseline.py` (the committed generator of the W0.1
    baseline) against `tests/fixtures/t05b/ph_state_baseline.json`: the rendered text byte for
    byte, and per case every recorded call (inputs and every field of the answer, floats as
    `float.hex()`); then T05's own measurements of A06–A10, A13, A14 (T05's generator), each
    one's condition and departures."""
    ledger = Ledger()
    live = json.loads(ph_baseline.render(ph_baseline.collect()))
    text = ph_baseline.FIXTURE.read_text()
    committed = json.loads(text)
    identical = ph_baseline.render(live) == text
    ledger.true("the live render equals the committed file byte for byte", identical)
    groups: dict[str, Any] = {}
    for group in ("unit_cases", "kernel_targets", "coupled_cases"):
        ledger.equal(f"{group}: case ids", sorted(live[group]), sorted(committed[group]))
        moved = sorted(
            case_id
            for case_id, recorded in committed[group].items()
            if live[group].get(case_id) != recorded
        )
        ledger.equal(f"{group}: cases differing from the baseline", moved, [])
        calls = (
            len(committed[group])
            if group == "kernel_targets"
            else sum(len(case["calls"]) for case in committed[group].values())
        )
        groups[group] = {"cases": len(committed[group]), "ph_state_calls": calls, "moved": moved}
    t05: dict[str, Any] = {}
    for identifier in _P1_T05_CHECKS:
        condition, value = _p1_t05_check(identifier)
        t05[identifier] = {"condition": condition, "departures": value.get("departures", [])}
        ledger.true(f"T05 {identifier}", condition is True)
    value = {
        "render_byte_identical": identical,
        "groups": groups,
        "t05_checks": t05,
        "departures": ledger.departures,
    }
    expected = {
        "render_byte_identical": True,
        "baseline": "tests/fixtures/t05b/ph_state_baseline.json (W0.1, measured at b8c6442 "
        "before any T05b edit): every call's inputs and answer (status, code, message, route, "
        "T, split, evaluations, residual) and every unit case's answer (duty, outlets), "
        "as float.hex, compared exactly",
        "moved": [],
        "t05_checks": {
            identifier: {"condition": True, "departures": []} for identifier in _P1_T05_CHECKS
        },
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- B03, B04


def _b03() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """The JUMP double at its registered inputs (the test's construction), and the double's
    jump `1 000 · V(360 K)` for `(1, 1, 1)` against `ref.kernel_doubles.JUMP.jump_W`."""
    ledger = Ledger()
    case = REF["kernel_doubles"]["JUMP"]
    n, pressure, target = kernel_fixtures.grid_inputs(case)
    answer = ph_state(Jump(PROVIDER), n, pressure, target, CONTEXT)
    ledger.equal("status", answer.status, case["expected"]["status"])
    ledger.equal("code", answer.code, case["expected"]["code"])
    ledger.equal("first message line", first_line(answer.message), case["expected"]["code"])
    carried = (answer.temperature, answer.split, answer.route)
    ledger.equal("(temperature, split, route)", carried, (None, None, None))
    names = {
        "bracket route named": "bracket route at T = " in answer.message,
        "band route named": "band route at T = " in answer.message,
        "closest named": "closest: the " in answer.message,
    }
    for where, held in names.items():
        ledger.true(where, held)
    # The double's jump, as `test_b03_the_double_is_what_the_spec_registers` measures it.
    flashed = PROVIDER.flash(
        FlashRequest(state=StreamState(n=(1.0, 1.0, 1.0), temperature=360.0, pressure=1.0e5)),
        CONTEXT,
    )
    assert flashed.vapor is not None
    jump = 1_000.0 * sum(flashed.vapor.n)
    jump_error = ledger.within("jump_W", jump, case["jump_W"], 1e-9)
    value = {
        "status": answer.status,
        "code": answer.code,
        "first_message_line": first_line(answer.message),
        "temperature": answer.temperature,
        "split": None if answer.split is None else "present",
        "route": answer.route,
        "message_names": names,
        "jump_W": jump,
        "jump_error_W": jump_error,
        "departures": ledger.departures,
    }
    expected = {
        "status": case["expected"]["status"],
        "code": case["expected"]["code"],
        "first_message_line": case["expected"]["code"],
        "temperature": None,
        "split": None,
        "route": None,
        "jump_W": case["jump_W"],
        "jump_tolerance_W": 1e-9,
    }
    return ledger.ok, value, expected


def _b04() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """PHF-1's inputs `(1, 1, 1)` mol/s, `P_r`, `H* = 50 000 W` (the test's construction)
    through the BIASED double: status, route, `T` and split against
    `ref.kernel_doubles.BIASED` (T05 §14: 1e-6 K, 3.1e-8 mol/s); the twin's emulated
    temperature-route answer (the energy-only acceptance) and the honest flash on the same
    inputs (bracket route, the registered `T` to 1e-12 K)."""
    ledger = Ledger()
    case = REF["kernel_doubles"]["BIASED"]
    expected_answer = case["expected"]
    n, target = (1.0, 1.0, 1.0), 50_000.0
    answer = ph_state(Biased(PROVIDER), n, 1.0e5, target, CONTEXT)
    ledger.equal("status", answer.status, expected_answer["status"])
    ledger.equal("route", answer.route, expected_answer["route"])
    flows: dict[str, list[float]] = {}
    t_error = math.inf
    if answer.temperature is not None and answer.split is not None:
        t_error = ledger.within("T", answer.temperature, expected_answer["T_K"], 1e-6)
        for port, key in (("vapor", "vapor_mol_per_s"), ("liquid", "liquid_mol_per_s")):
            stream = getattr(answer.split, port)
            ledger.true(f"{port} present", stream is not None)
            if stream is not None:
                flows[port] = [
                    ledger.within(f"{port}[{index}]", got, registered, kernel_fixtures.TAU_FLOW)
                    for index, (got, registered) in enumerate(
                        zip(stream.n, expected_answer[key], strict=True)
                    )
                ]
    else:
        ledger.true("an answer is carried", False)
    emulated = case["measured_53_bit"]
    energy_only_miss = abs(
        float(emulated["temperature_route_T_K"]) - number(expected_answer["T_K"])
    )
    equilibrium_ratio = float(emulated["temperature_route_max_equilibrium_row"]) / (
        kernel_fixtures.TAU_EQ
    )
    ledger.true("energy-only acceptance misses T by more than 1e-4 K", energy_only_miss > 1e-4)
    ledger.true("its equilibrium row exceeds 10 tau_eq", equilibrium_ratio > 10.0)
    honest = ph_state(PROVIDER, n, 1.0e5, target, CONTEXT)
    ledger.equal("honest flash status", honest.status, "ok")
    ledger.equal("honest flash route", honest.route, "bracket")
    honest_error = ledger.within(
        "honest flash T", honest.temperature, expected_answer["T_K"], 1e-12
    )
    value = {
        "status": answer.status,
        "route": answer.route,
        "T_error_K": t_error,
        "split_errors_mol_per_s": flows,
        "worst_split_error_mol_per_s": max((e for v in flows.values() for e in v), default=None),
        "twin_energy_only_T_miss_K": energy_only_miss,
        "twin_energy_only_equilibrium_row_over_tau_eq": equilibrium_ratio,
        "honest_flash": {"status": honest.status, "route": honest.route, "T_error_K": honest_error},
        "departures": ledger.departures,
    }
    expected = {
        "status": expected_answer["status"],
        "route": expected_answer["route"],
        "T_K": expected_answer["T_K"],
        "T_tolerance_K": 1e-6,
        "split_tolerance_mol_per_s": kernel_fixtures.TAU_FLOW,
        "twin_energy_only_T_miss_K": "more than 1e-4 (spec §12.2: 2.2e-4 K)",
        "twin_energy_only_equilibrium_row_over_tau_eq": "more than 10 (spec §12.2: 84)",
        "honest_flash": {"status": "ok", "route": "bracket", "T_tolerance_K": 1e-12},
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- B05


def _b05() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """In each layer (the unit layer's `saturation_band`, the verifier's `verify.saturation`;
    the test's `LAYERS`): the bubble and dew ends of the 8 grid compositions against
    `ref.kernel_grid.*.band` (1e-10 K); `δ` at NP-1…NP-G's roots against `ref` (1e-10 K) and
    its classification; the classification and `δ` of §12.7's R7-1…R7-4 (1e-12 K, R7-4's
    12-digit registration 1e-9 K) and of T05's registered refusals (1e-6 K, six decimals); and
    the two layers' ends agreeing to 1e-12 K."""
    ledger = Ledger()
    tolerance = band_fixtures.BAND_TOLERANCE
    layers: dict[str, Any] = {}
    for layer, (ends, distance, degenerate) in band_fixtures.LAYERS.items():
        end_errors: dict[str, float] = {}
        for composition, (n, pressure, band) in band_fixtures.GRID.items():
            bubble, dew = ends(n, pressure)
            end_errors[f"{composition} T_b"] = ledger.within(
                f"{layer} {composition} T_b", bubble, band["T_bubble_K"], tolerance
            )
            end_errors[f"{composition} T_d"] = ledger.within(
                f"{layer} {composition} T_d", dew, band["T_dew_K"], tolerance
            )
        near_pure: dict[str, Any] = {}
        for case_id, (n, temperature, case) in band_fixtures.NEAR_PURE.items():
            delta = distance(n, temperature, 1.0e5)
            near_pure[case_id] = {
                "delta_error_K": ledger.within(
                    f"{layer} {case_id} delta", delta, case["degeneracy_K"], tolerance
                ),
                "degenerate": ledger.equal(
                    f"{layer} {case_id} degenerate", degenerate(delta), case["degenerate"]
                ),
            }
        r007: dict[str, Any] = {}
        for state_id, state in REF["r007_states"].items():
            delta = distance(
                band_fixtures.flows(state["n_mol_per_s"]),
                number(state["T_K"]),
                number(state["P_Pa"]),
            )
            bound = 1e-12 if number(state["degeneracy_K"]) < 1.0 else 1e-9
            r007[state_id] = {
                "delta_error_K": ledger.within(
                    f"{layer} {state_id} delta", delta, state["degeneracy_K"], bound
                ),
                "degenerate": ledger.equal(
                    f"{layer} {state_id} degenerate",
                    degenerate(delta),
                    number(state["degeneracy_K"]) <= 1e-6,
                ),
            }
        refusals: dict[str, Any] = {}
        for case_id, registered in REF["t05_registered_refusals_degeneracy_K"].items():
            n, temperature, pressure = band_fixtures._refused_stream(case_id)
            delta = distance(n, temperature, pressure)
            refusals[case_id] = {
                "delta_K": delta,
                "delta_error_K": ledger.within(f"{layer} {case_id} delta", delta, registered, 1e-6),
                "degenerate": ledger.equal(
                    f"{layer} {case_id} degenerate", degenerate(delta), False
                ),
            }
        layers[layer] = {
            "grid_band_ends": worst(end_errors),
            "near_pure": near_pure,
            "r007_states": r007,
            "t05_registered_refusals": refusals,
        }
    agreement: dict[str, float] = {}
    for composition, (n, pressure, _) in band_fixtures.GRID.items():
        ours = band_fixtures.unit_ends(n, pressure)
        theirs = band_fixtures.verifier_ends(n, pressure)
        for name, a, b in zip(("T_b", "T_d"), ours, theirs, strict=True):
            if a is None or b is None:
                ledger.true(f"{composition} {name} computed in both layers", False)
                continue
            agreement[f"{composition} {name}"] = abs(a - b)
            ledger.at_most(f"{composition} {name} unit vs verifier", abs(a - b), 1e-12)
    value = {
        "grid_compositions": len(band_fixtures.GRID),
        "layers": layers,
        "layers_agree": worst(agreement),
        "departures": ledger.departures,
    }
    expected = {
        "grid_compositions": 8,
        "band_end_and_near_pure_delta_tolerance_K": tolerance,
        "near_pure": {
            case_id: {"degeneracy_K": case["degeneracy_K"], "degenerate": case["degenerate"]}
            for case_id, (_, _, case) in band_fixtures.NEAR_PURE.items()
        },
        "r007_states": {
            state_id: {
                "degeneracy_K": state["degeneracy_K"],
                "degenerate": number(state["degeneracy_K"]) <= 1e-6,
                "tolerance_K": 1e-12 if number(state["degeneracy_K"]) < 1.0 else 1e-9,
            }
            for state_id, state in REF["r007_states"].items()
        },
        "t05_registered_refusals": {
            case_id: {"degeneracy_K": registered, "degenerate": False, "tolerance_K": 1e-6}
            for case_id, registered in REF["t05_registered_refusals_degeneracy_K"].items()
        },
        "layers_agree_K": 1e-12,
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- B06


def _p1_scan_policies() -> dict[str, Any]:
    """`test_t05b_literal.test_b06_no_registered_policy_names_v2`'s scan, measured: every
    `phase_contract=` keyword in `src`, `scripts`, `benchmarks`, `tests` outside the two
    exemptions; the keywords in `t05b_support.py`; the committed documents spelling v2."""
    exempt = (ROOT / "tests" / "test_t05b_literal.py", literal_fixtures.T05B_V2_SOURCE)
    sources = literal_fixtures._sources()
    offenders: list[str] = []
    for path in sources:
        if path in exempt:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.keyword) and node.arg == "phase_contract":
                offenders.append(f"{path.relative_to(ROOT)}:{node.value.lineno}")
    constructed = sum(
        1
        for node in ast.walk(ast.parse(literal_fixtures.T05B_V2_SOURCE.read_text(encoding="utf-8")))
        if isinstance(node, ast.keyword) and node.arg == "phase_contract"
    )
    documents = sorted(
        str(path.relative_to(ROOT))
        for root in ("tests/fixtures", "benchmarks")
        for pattern in ("*.json", "*.yaml")
        for path in (ROOT / root).rglob(pattern)
        if literal_fixtures.V2 in path.read_text(encoding="utf-8")
    )
    return {
        "sources_scanned": len(sources) - sum(1 for path in exempt if path in sources),
        "offenders": offenders,
        "v2_constructions_in_t05b_support": constructed,
        "documents_spelling_v2": documents,
    }


def _b06() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """The schema (`test_k03_schemas.errors_for`) on a policy document carrying each literal
    and none; `PhaseContract`'s arguments and `SolvePolicy`'s default; the committed policy
    fixtures; the registered-policy scan; and R-015: the two policy fixtures as their
    generators serialize them, byte for byte, and every schema fixture a generator emits
    (K03's, K04's, K05's, T04's) compared with the committed file."""
    ledger = Ledger()
    v1, v2 = literal_fixtures.V1, literal_fixtures.V2
    # Each literal on the default policy's document, as for the refused values below: a policy
    # document, not a policy. Constructing one with a `phase_contract` keyword outside the
    # exemptions is what B06's own registered-policy scan refuses, and this script is scanned.
    default = literal_fixtures._policy().as_document()
    accepted = {
        value: len(
            literal_fixtures.errors_for("solve_policy", {**default, "phase_contract": value})
        )
        for value in (v1, v2)
    }
    for literal, count in accepted.items():
        ledger.equal(f"schema errors for {literal}", count, 0)
    refused_values: list[Any] = ["T03-phase-contract-v2", "T02-interim", "", None, 1]
    refused: dict[str, int] = {}
    for literal in refused_values:
        document = {**literal_fixtures._policy().as_document(), "phase_contract": literal}
        refused[repr(literal)] = len(literal_fixtures.errors_for("solve_policy", document))
    absent = literal_fixtures._policy().as_document()
    del absent["phase_contract"]
    refused["absent"] = len(literal_fixtures.errors_for("solve_policy", absent))
    for literal, count in refused.items():
        ledger.true(f"schema refuses {literal} ({count} errors)", count > 0)
    (field_default,) = [
        field.default for field in dataclasses.fields(SolvePolicy) if field.name == "phase_contract"
    ]
    defaults = {
        "PhaseContract_arguments": list(typing.get_args(PhaseContract)),
        "SolvePolicy_field_default": field_default,
        "policy_with_defaults": literal_fixtures._policy().phase_contract,
        "as_document": literal_fixtures._policy().as_document()["phase_contract"],
    }
    ledger.equal("PhaseContract", defaults["PhaseContract_arguments"], [v1, v2])
    for key in ("SolvePolicy_field_default", "policy_with_defaults", "as_document"):
        ledger.equal(key, defaults[key], v1)
    fixtures = {
        path.name: json.loads(path.read_text(encoding="utf-8"))["phase_contract"]
        for path in literal_fixtures.POLICY_FIXTURES
    }
    ledger.equal("committed policy fixtures", sorted(fixtures), ["syn001_k03.json", "t04_ptc.json"])
    for name, literal in fixtures.items():
        ledger.equal(f"{name} phase_contract", literal, v1)
    scan = _p1_scan_policies()
    ledger.equal("phase_contract keywords outside the exemptions", scan["offenders"], [])
    ledger.equal("v2 constructions in t05b_support.py", scan["v2_constructions_in_t05b_support"], 1)
    ledger.equal("committed documents spelling v2", scan["documents_spelling_v2"], [])
    from t05b_support import POLICY_V2

    ledger.equal("POLICY_V2", (POLICY_V2.policy_id, POLICY_V2.phase_contract), ("T05b-v2", v2))
    import k03_schema_fixtures as k03
    import t04_schema_fixtures as t04

    from openflowsheet.orchestrator.trace import GlobalizationPolicy, RecyclePolicy

    ptc = t04.policy(
        "ptc",
        recycle=RecyclePolicy(method="eo"),
        globalization=GlobalizationPolicy(eo_core="ptc", eo_recovery="none"),
    )
    policy_bytes: dict[str, bool] = {}
    for name, policy, serialize in (
        ("syn001_k03.json", k03.POLICY, k03.serialize),
        ("t04_ptc.json", ptc, t04.serialize),
    ):
        path = literal_fixtures.FIXTURE_DIR / "solve_policy" / "valid" / name
        policy_bytes[name] = serialize(policy.as_document()) == path.read_text(encoding="utf-8")
        ledger.true(f"{name} regenerates byte for byte", policy_bytes[name])
    compared = _r015_fixtures()
    differing = sorted(name for name, entry in compared.items() if entry["differences"])
    ledger.equal("R-015 fixtures differing", differing, [])
    value = {
        "schema_errors_accepted": accepted,
        "schema_errors_refused": refused,
        "defaults": defaults,
        "committed_policy_fixtures": fixtures,
        "registered_policy_scan": scan,
        "policy_fixtures_byte_identical": policy_bytes,
        "r015": {
            "fixtures_compared": len(compared),
            "by_generator": {
                generator: sum(1 for entry in compared.values() if entry["generator"] == generator)
                for generator in sorted({entry["generator"] for entry in compared.values()})
            },
            "differing": differing,
        },
        "departures": ledger.departures,
    }
    expected = {
        "schema_errors_accepted": {v1: 0, v2: 0},
        "schema_errors_refused": "at least one error for each of "
        "T03-phase-contract-v2, T02-interim, the empty string, None, 1 and absence",
        "defaults": {
            "PhaseContract_arguments": [v1, v2],
            "SolvePolicy_field_default": v1,
            "policy_with_defaults": v1,
            "as_document": v1,
        },
        "committed_policy_fixtures": {"syn001_k03.json": v1, "t04_ptc.json": v1},
        "registered_policy_scan": {
            "offenders": [],
            "v2_constructions_in_t05b_support": 1,
            "documents_spelling_v2": [],
        },
        "policy_fixtures_byte_identical": {"syn001_k03.json": True, "t04_ptc.json": True},
        "r015": {"differing": []},
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- B19

#: T05's checks carrying its five registered R-007 refusals (T05 spec §15 A07, A09, A11, A12).
_P1_REFUSAL_CHECKS = {
    "PHF-F3": "A07",
    "PUMP-F1": "A09",
    "PUMP-F2": "A09",
    "SEP-F2": "A11",
    "HX-F4": "A12",
}


def _b19() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """`tp_state.single_phase_admissible` at R7-1…R7-4 (the test's streams): verdict against
    `ref.r007_states.*.admitted`, the reported gap against `degeneracy_K` (1e-12 K) when
    admitted, against `tp_gap_K` (relative 1e-6) when refused; the two T05 routes into R-007
    (`port_enthalpy`, `admitted_enthalpy`) and their refusal code; T05's five registered
    refusals: `δ` against `ref.t05_registered_refusals_degeneracy_K` (1e-6 K) and still refused,
    and each case's own T05 check (A07, A09, A11, A12, T05's generator) passing."""
    ledger = Ledger()
    components = r007_fixtures.COMPONENTS
    states: dict[str, Any] = {}
    for state_id, entry in REF["r007_states"].items():
        stream, phase = r007_fixtures._stream(entry), r007_fixtures._phase(entry)
        admissible, _, gap, status, message = single_phase_admissible(
            PROVIDER, stream, phase, components, CONTEXT
        )
        ledger.equal(f"{state_id} (status, message)", (status, message), ("ok", ""))
        ledger.equal(f"{state_id} admitted", admissible, entry["admitted"])
        record: dict[str, Any] = {"admitted": admissible, "reported_gap_K": gap}
        if admissible:
            record["gap_error_vs_delta_K"] = ledger.within(
                f"{state_id} gap", gap, entry["degeneracy_K"], r007_fixtures.GAP_TOLERANCE
            )
        else:
            record["gap_error_vs_tp_gap_K"] = ledger.within(
                f"{state_id} gap", gap, entry["tp_gap_K"], 1e-6 * number(entry["tp_gap_K"])
            )
        port = port_enthalpy(PROVIDER, stream, phase, components, CONTEXT, port="inlet")
        admitted = admitted_enthalpy(
            PROVIDER,
            components,
            CONTEXT,
            unit_id="U-TEST",
            port="inlet",
            stream=stream,
            phase=phase,
        )
        if entry["admitted"]:
            ledger.equal(f"{state_id} port_enthalpy status", port.status, "ok")
            ledger.true(
                f"{state_id} admitted_enthalpy equals port_enthalpy",
                admitted == port.enthalpy_flow,
            )
            record["port_admissibility_error_K"] = ledger.within(
                f"{state_id} port_enthalpy admissibility",
                port.admissibility,
                entry["degeneracy_K"],
                r007_fixtures.GAP_TOLERANCE,
            )
        else:
            code = f"inadmissible_phase(inlet, {phase})"
            port_code = None if port.failure is None else first_line(port.failure.message)
            admitted_code = None if isinstance(admitted, float) else first_line(admitted.message)
            record["refusal_codes"] = {
                "port_enthalpy": port_code,
                "admitted_enthalpy": admitted_code,
            }
            ledger.equal(f"{state_id} port_enthalpy status", port.status, "unsupported")
            ledger.equal(f"{state_id} port_enthalpy code", port_code, code)
            ledger.equal(f"{state_id} admitted_enthalpy code", admitted_code, code)
        states[state_id] = record
    ledger.equal("R7-1 reported gap exactly", states["R7-1"]["reported_gap_K"], 0.0)
    refusals: dict[str, Any] = {}
    for case, (port_name, phase, fraction, temperature) in r007_fixtures._REFUSED.items():
        inputs = T05_REF["unit_cases"][case]["inputs"][port_name]
        stream = StreamState(
            n=tuple(fraction * number(value) for value in inputs["n_mol_per_s"]),
            temperature=temperature or number(inputs["T_K"]),
            pressure=number(inputs["P_Pa"]),
        )
        distance = degeneracy_distance(
            PROVIDER, stream.n, stream.temperature, stream.pressure, CONTEXT
        )
        admissible, _, gap, status, _ = single_phase_admissible(
            PROVIDER,
            stream,
            phase,
            components,
            CONTEXT,  # type: ignore[arg-type]
        )
        check_id = _P1_REFUSAL_CHECKS[case]
        condition, t05_value = _p1_t05_check(check_id)
        refusals[case] = {
            "delta_K": distance,
            "delta_error_K": ledger.within(
                f"{case} delta", distance, REF["t05_registered_refusals_degeneracy_K"][case], 1e-6
            ),
            "admitted": admissible,
            "gap_K": gap,
            "t05_check": check_id,
            "t05_case_result": t05_value["cases"].get(case),
        }
        ledger.equal(f"{case} status", status, "ok")
        ledger.equal(f"{case} admitted", admissible, False)
        ledger.true(f"{case} gap above tau_T", gap > TEMPERATURE_TOLERANCE)
        ledger.equal(f"{case} in T05 {check_id}", t05_value["cases"].get(case), "pass")
    value = {
        "r007_states": states,
        "t05_registered_refusals": refusals,
        "departures": ledger.departures,
    }
    expected = {
        "r007_states": {
            state_id: {
                "admitted": entry["admitted"],
                "reported_gap_K": entry["degeneracy_K"] if entry["admitted"] else entry["tp_gap_K"],
                "tolerance_K": r007_fixtures.GAP_TOLERANCE
                if entry["admitted"]
                else "1e-6 relative",
            }
            for state_id, entry in REF["r007_states"].items()
        },
        "R7-1_reported_gap_K": 0.0,
        "refusal_code": "inadmissible_phase(inlet, PHASE) with the declared phase, from both "
        "port_enthalpy and admitted_enthalpy",
        "t05_registered_refusals": {
            case: {
                "delta_K": registered,
                "tolerance_K": 1e-6,
                "admitted": False,
                "t05_case_result": "pass",
            }
            for case, registered in REF["t05_registered_refusals_degeneracy_K"].items()
        },
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- B23


def _p1_registered_forms() -> dict[str, list[dict[str, Any]]]:
    """`ref.dormancy_forms` as data, the `‹U›` placeholder parsed away: per key, each entry's
    outlet, trigger port, swapped row family, label row side and declared phase — the parse
    checked to reproduce every field's registered string exactly."""
    parsed: dict[str, list[dict[str, Any]]] = {}
    for key, entries in REF["dormancy_forms"].items():
        rows: list[dict[str, Any]] = []
        for entry in entries:
            outlet = entry["item"].split(".", 1)[1]
            trigger = entry["trigger"].removeprefix("every stream of port ").split(" ", 1)[0]
            swapped = entry["swapped_row"].split(":", 1)[1]
            label_row = entry["label_row"].split(":", 1)[1]
            side = label_row.split(":", 2)[1] if label_row.count(":") else None
            rows.append(
                {
                    "outlet": outlet,
                    "trigger": trigger,
                    "swapped": swapped,
                    "side": side,
                    "declared_phase": entry["declared_phase"],
                }
            )
        parsed[key] = rows
    return parsed


def _p1_render(outlet: str, trigger: str, swapped: str, side: str | None) -> dict[str, str]:
    """One registry row in `ref.dormancy_forms`' notation (the test's `_rendered`)."""
    return {
        "item": f"<U>.{outlet}",
        "trigger": f"every stream of port {trigger} exactly dormant",
        "swapped_row": f"<U>:{swapped}",
        "label_row": "<U>:zero-flow-label" + (f":{side}" if side else ""),
        "label": f"T({outlet}) - T(first stream of {trigger})",
    }


def _p1_key(model: str, configuration: str | None) -> str:
    return model if configuration is None else f"{model}(specification={configuration})"


def _b23() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """The solver's `splits.DORMANCY_RULES` rendered in `ref.dormancy_forms`' notation and
    compared with it exactly (every field); the verifier's own `zero_flow.DORMANT_OUTLETS`
    rendered the same way per model and exchanger specification and compared with `ref`
    (every field but the declared phase, which the verifier does not transcribe) and with the
    solver's rows as data; the verifier module's imports under the table-independence rule
    (`test_t05_table_independence.violations`) and no import of the solver's registry at all;
    `check_agreement` on the test's five constructed disagreements (the two B23 names — a
    swapped row not reading the outlet's temperature, an unwired port — among them); and each
    DZ case's forms at its registered root against its registered items, swapped rows and label
    rows."""
    ledger = Ledger()
    registered = _p1_registered_forms()
    ledger.true(
        "the parse of ref.dormancy_forms reproduces it",
        {
            key: [
                {
                    **_p1_render(r["outlet"], r["trigger"], r["swapped"], r["side"]),
                    "declared_phase": r["declared_phase"],
                }
                for r in rows
            ]
            for key, rows in registered.items()
        }
        == REF["dormancy_forms"],
    )
    solver = {
        _p1_key(model, configuration): [
            {
                "outlet": rule.outlet,
                "trigger": rule.trigger,
                "swapped": rule.swapped,
                "side": rule.side,
                "declared_phase": rule.declared_phase,
            }
            for rule in rules
        ]
        for (model, configuration), rules in DORMANCY_RULES.items()
    }
    ledger.equal("solver registry keys", sorted(solver), sorted(registered))
    ledger.equal("solver registry (as data)", solver, registered)
    solver_rendered = {
        _p1_key(model, configuration): dormancy._rendered(model, configuration)
        for model, configuration in DORMANCY_RULES
    }
    ledger.true(
        "solver registry rendered equals ref.dormancy_forms exactly",
        solver_rendered == REF["dormancy_forms"],
    )
    configurations: dict[str, list[str | None]] = {
        "syn001.liquid_pump": [None],
        "syn001.adiabatic_mixer": [None],
        "syn001.heat_exchanger": ["duty", "hot_outlet_temperature", "cold_outlet_temperature"],
    }
    ledger.equal("verifier table models", sorted(DORMANT_OUTLETS), sorted(configurations))
    verifier = {
        _p1_key(model, configuration): [
            {
                "outlet": entry.outlet,
                "trigger": entry.trigger,
                "swapped": entry.swapped,
                "side": entry.side,
            }
            for entry in DORMANT_OUTLETS[model]
            if entry.unless is None or entry.unless != configuration
        ]
        for model, keys in configurations.items()
        for configuration in keys
    }
    without_phase = {
        key: [{k: v for k, v in row.items() if k != "declared_phase"} for row in rows]
        for key, rows in registered.items()
    }
    ledger.equal("verifier table vs ref (as data)", verifier, without_phase)
    ledger.true(
        "verifier table rendered equals ref.dormancy_forms (declared phase aside)",
        {
            key: [_p1_render(r["outlet"], r["trigger"], r["swapped"], r["side"]) for r in rows]
            for key, rows in verifier.items()
        }
        == {
            key: [{k: v for k, v in e.items() if k != "declared_phase"} for e in entries]
            for key, entries in REF["dormancy_forms"].items()
        },
    )
    solver_rows = {
        key: [{k: v for k, v in row.items() if k != "declared_phase"} for row in rows]
        for key, rows in solver.items()
    }
    ledger.equal("verifier table vs solver registry (as data)", verifier, solver_rows)
    source = table_independence.ZERO_FLOW.read_text(encoding="utf-8")
    violations = table_independence.violations(source)
    ledger.equal("verify/zero_flow.py import violations", violations, [])
    solver_imports = [
        f"{module}: {names}"
        for module, names in table_independence._imports(source)
        if table_independence._within(module, "openflowsheet.orchestrator.splits")
        or "DORMANCY_RULES" in names
    ]
    ledger.equal("verify/zero_flow.py imports of the solver's registry", solver_imports, [])
    # `check_agreement` on the test's own constructed disagreements (its parametrization).
    (marker,) = [
        mark
        for mark in dormancy.test_b23_agreement_refuses_a_form_that_disagrees.pytestmark
        if mark.name == "parametrize"
    ]
    constructions = marker.args[1]
    names = marker.kwargs["ids"]
    agreement: dict[str, Any] = {}
    for name, (build, corrupt, pattern) in zip(names, constructions, strict=True):
        binding = bind(build())
        forms = dormancy._forms(binding)
        dormancy._agreement(binding, forms)  # the uncorrupted forms agree
        try:
            dormancy._agreement(binding, (corrupt(forms[0]), *forms[1:]))
        except ValueError as refused:
            message = str(refused)
            agreement[name] = {
                "raised": "ValueError",
                "first_line": first_line(message).replace("<", "‹"),
                "prefix": message.startswith("dormancy_form_disagrees("),
                "registered_pattern": re.search(pattern, message) is not None,
            }
        else:
            agreement[name] = {"raised": None}
        ledger.equal(f"check_agreement {name} raises", agreement[name]["raised"], "ValueError")
        if agreement[name]["raised"]:
            ledger.true(f"check_agreement {name} prefix", agreement[name]["prefix"])
            ledger.true(f"check_agreement {name} message", agreement[name]["registered_pattern"])
    for required in ("swapped-not-reading-T", "unwired-trigger", "unwired-outlet"):
        ledger.true(f"B23's construction {required} is exercised", required in agreement)
    # Each DZ case's forms at its registered root (the test's `each_cases_forms`).
    cases: dict[str, Any] = {}
    for case, build in DORMANT_NON_LIFTED_CASES.items():
        binding = bind(build())
        forms = dormancy._forms(binding)
        entry = dormancy._registered(case)
        state = entry["root"] if "root" in entry else entry["end_state"]
        active = [f for f in forms if all(float(state[c]) == 0.0 for c in f.trigger_flows)]
        items = [f.item for f in active]
        swapped = [f.swapped for f in active]
        cases[case] = {"items": items, "swapped_rows": swapped}
        if case in dormancy.CASES:
            labels = {
                label: {"T_out": outlet, "T_label": source}
                for label, outlet, source in (f.label for f in active)
            }
            cases[case]["label_rows"] = labels
            ledger.equal(f"{case} items", items, entry["items"])
            ledger.equal(f"{case} swapped rows", swapped, entry["swapped_rows"])
            ledger.equal(f"{case} label rows", labels, entry["label_rows"])
        else:
            ledger.equal(f"{case} items", items, [item for item, _ in entry["signature"]])
            ledger.equal(f"{case} swapped rows", swapped, list(entry["swapped_row_at_end_W"]))
        dormancy._agreement(binding, forms)
    value = {
        "solver_registry": solver,
        "verifier_table": verifier,
        "verifier_import_violations": violations,
        "verifier_imports_of_the_solver_registry": solver_imports,
        "check_agreement": agreement,
        "cases": cases,
        "departures": ledger.departures,
    }
    expected = {
        "registry": registered,
        "registry_source": "ref.dormancy_forms (item, trigger, swapped_row, label_row, label, "
        "declared_phase), parsed as data and rendered back exactly",
        "verifier_table": "ref.dormancy_forms without the declared phase; equal to the solver's",
        "verifier_import_violations": [],
        "verifier_imports_of_the_solver_registry": [],
        "check_agreement": "ValueError, message prefix dormancy_form_disagrees(, and the "
        "test's registered pattern, for every construction",
        "cases": "ref.dormant_non_lifted_cases.*.items, swapped_rows, label_rows; "
        "ref.zero_flow_conflicts.*.signature and swapped_row_at_end_W",
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- registration

DESCRIPTIONS.update(
    {
        "B01": "Kernel grid (replaces T05 A29): the 40 `ph_state` calls of `ref.kernel_grid` "
        "(`(ε, 2, 0)` and `(0, 2, ε)`, ε ∈ {1e-12, 1e-9, 1e-7, 1e-6}, five φ) through "
        "`test_t05b_kernel.grid_inputs`: every status `ok`; route ∈ {bracket, band}, band at "
        "every ε ≤ 1e-9 with φ ≠ 0.5, and every route equal to the regression pin "
        "`B01_BRACKET` and the twin's 53-bit emulation; the three §5.3 rows evaluated from the "
        "provider over τ_flow, τ_eq, τ_E, each ≤ 1; `T`, `V` and every flowing `q_i` against "
        "`ref` within §13's grid tolerances (1e-6 K, 1e-7 mol/s, 1e-6); the band route's "
        "worst errors (§13's floors) and evaluation counts.",
        "B02": "The kernel is inert on T05's registered calls: a live run of "
        "`scripts/t05b_ph_baseline.py` (every `ph_state` call of PHF-*, VLV-*, RX-*, T05's "
        "eight direct kernel targets, and C1, C2, C3, C3X solved on the general path) equals "
        "the committed W0.1 baseline `tests/fixtures/t05b/ph_state_baseline.json` byte for "
        "byte (status, code, message, route, `T`, split, duty, evaluations, residual as "
        "`float.hex`), per case and per call; and T05's A06–A10, A13, A14, measured by T05's "
        "own generator (`scripts/t05_evidence_manifest.py`), pass with no departure.",
        "B03": "JUMP: `ph_state` through `t05b_support.Jump` at `ref.kernel_doubles.JUMP`'s "
        "inputs returns `not_converged`, code and first message line `ph_ill_conditioned`, no "
        "temperature, split or route, its message naming both routes; the double's jump "
        "`1 000 · V(360 K)` within 1e-9 W of `ref`'s 1 360.81 W.",
        "B04": "BIASED: PHF-1's inputs through `t05b_support.Biased` return `ok` by the band "
        "route with `T` within 1e-6 K and every vapour and liquid flow within 3.1e-8 mol/s of "
        "`ref.kernel_doubles.BIASED`; the twin's emulated energy-only answer misses `T` by more "
        "than 1e-4 K with its equilibrium row above 10 τ_eq; the honest flash on the same "
        "inputs takes the bracket route to the registered `T` within 1e-12 K.",
        "B05": "The band primitive and the degeneracy test, in the unit layer and the verifier "
        "(each its own code): the 8 grid compositions' `T_b`, `T_d` within 1e-10 K of "
        "`ref.kernel_grid.*.band`; `δ` at NP-1…NP-G's roots within 1e-10 K of `ref` and the "
        "degenerate classification equal to `ref`'s; §12.7's R7-1…R7-4 (`δ` to 1e-12 K, R7-4 "
        "to 1e-9 K) and T05's five registered refusals (`δ` to 1e-6 K) classified as "
        "registered; the two layers' band ends within 1e-12 K of each other.",
        "B06": "The literal: the `solve_policy` schema accepts `T03-phase-contract-v1` and "
        "`T05b-phase-contract-v2` and refuses `T03-phase-contract-v2`, `T02-interim`, the "
        "empty string, `None`, `1` and absence; `PhaseContract` is exactly the two literals and "
        "`SolvePolicy` defaults to v1; both committed policy fixtures are v1; no source outside "
        "the two exemptions passes `phase_contract=`, `t05b_support.py` constructs v2 once "
        "(`T05b-v2`), and no committed fixture or benchmark spells v2; the policy fixtures "
        "regenerate byte for byte, and every schema fixture a generator emits (K03, K04, K05, "
        "T04) regenerates identically (R-015).",
        "B19": "R-007 in the unit layer (`tp_state.single_phase_admissible`) at "
        "`ref.r007_states`: R7-1 admitted with reported gap exactly 0.0, R7-3 admitted with "
        "gap `δ` = 5e-7 K (1e-12 K), R7-2 and R7-4 refused with their TP gap; through T05's two "
        "declared-port routes (`port_enthalpy`, `admitted_enthalpy`) the same verdicts, a "
        "refusal's code `inadmissible_phase(inlet, PHASE)`; T05's five registered refusals "
        "(PHF-F3, PUMP-F1, PUMP-F2, SEP-F2, HX-F4) have `δ` within 1e-6 K of `ref` (≥ 14.27 K), "
        "stay refused, and pass their T05 checks (A07, A09, A11, A12, T05's generator).",
        "B23": "The dormancy-form registry: `splits.DORMANCY_RULES` equals `ref.dormancy_forms` "
        "for every model and configuration — outlets, item keys, trigger ports, swapped rows, "
        "label rows, label ports and declared phases, rendered and compared exactly; "
        "`check_agreement` raises `ValueError` with prefix `dormancy_form_disagrees(` for each "
        "of the test's five constructed disagreements (a swapped row not reading the outlet's "
        "temperature, a foreign row, an unwired trigger port, an unwired outlet port, a wrong "
        "label source); each DZ case's forms at its root are the registered ones; the "
        "verifier's `zero_flow.DORMANT_OUTLETS` names the same outlets and rows as `ref` and "
        "the solver (compared as data), and `verify/zero_flow.py` imports nothing the "
        "table-independence rule forbids and nothing of the solver's registry (AST).",
    }
)
MEASURES.update(
    {
        "B01": _b01,
        "B02": _b02,
        "B03": _b03,
        "B04": _b04,
        "B05": _b05,
        "B06": _b06,
        "B19": _b19,
        "B23": _b23,
    }
)


# ------------------------------------------------------------- B07-B14, B20, X09, X10: the contract


_P2_COMPONENTS = contract.COMPONENTS
#: Spec §13's EO allowances (T02 §6.4), as the contract test reads them from `ref`.
_P2_ALLOWANCE: Mapping[str, float] = contract.ALLOWANCE
#: T05b spec B08 ("the saturation value is within ulps of `T_sat`"; the contract test's bound).
_P2_SATURATION_BOUND_K = 1e-9
#: K04-F9 spec X09: the energy balances at NP-G are `≤ 1e-3 τ_E`.
_P2_ENERGY_FRACTION = 1e-3
#: B20 (b): the kernel's temperature and vapour fraction against `ref.contract_kernel_states` at
#: the contract test's tolerances (§13's grid `T` row, 1e-6 K; β to 1e-9) and its conservation
#: bound on each component, 3.1e-8 mol/s.
_P2_KS_T_K = 1e-6
_P2_KS_BETA = 1e-9
_P2_KS_CONSERVATION = 3.1e-8
#: B20 (d): the item DZ-12 carries at its opening (`ref…DZ-12.attempt0.signature`).
_P2_DZ12 = REF["dormant_non_lifted_cases"]["DZ-12"]


def _p2_safe(text: str) -> str:
    """A measured string for the manifest: `<` replaced by `‹` (the placeholder rule)."""
    return text.replace("<", "‹")


def _p2_near(
    ledger: Ledger, ratios: dict[str, float], where: str, got: float, expected: str, kind: str
) -> None:
    """One registered value against the state at spec §13's allowance of its kind; records the
    deviation over the allowance by name."""
    allowance = _P2_ALLOWANCE[kind]
    ratios[where] = ledger.within(where, got, expected, allowance) / allowance


def _p2_stream(
    ledger: Ledger,
    ratios: dict[str, float],
    state: Mapping[str, float],
    stream: str,
    entry: Mapping[str, Any],
) -> None:
    """`test_t05b_contract._stream`: the registered flows, phase flows, `T` and `P` of a stream."""
    for index, component in enumerate(_P2_COMPONENTS):
        if "n_mol_per_s" in entry:
            column = f"{stream}.n.{component}"
            _p2_near(ledger, ratios, column, state[column], entry["n_mol_per_s"][index], "flow")
        for key, prefix in (("vapor_mol_per_s", "vap"), ("liquid_mol_per_s", "liq")):
            if key in entry:
                column = f"{stream}.{prefix}.{component}"
                _p2_near(ledger, ratios, column, state[column], entry[key][index], "flow")
    if "T_K" in entry:
        _p2_near(ledger, ratios, f"{stream}.T", state[f"{stream}.T"], entry["T_K"], "T")
    if "P_Pa" in entry:
        _p2_near(ledger, ratios, f"{stream}.P", state[f"{stream}.P"], entry["P_Pa"], "P")


def _p2_sc_state(ledger: Ledger, case: str, result: contract.Solved) -> dict[str, Any]:
    """`ref.single_component_cases.<case>.root` against the solved state (the contract test's
    `_root`: every stream entry, and each `.Q`/`.W`)."""
    ratios: dict[str, float] = {}
    state = result.run.state
    if not ledger.true(f"{case}: a final state", state is not None):
        return worst(ratios)
    assert state is not None
    for key, entry in REF["single_component_cases"][case]["root"].items():
        if isinstance(entry, dict):
            _p2_stream(ledger, ratios, state, key, entry)
        elif key.endswith((".Q", ".W")):
            _p2_near(ledger, ratios, key, state[key], entry, "duty")
    return worst(ratios)


def _p2_np_state(ledger: Ledger, case: str, result: contract.Solved) -> dict[str, Any]:
    """`ref.near_pure_cases.<case>.root` against the solved state (the contract test's
    `_near_pure_root`: `S2` the vapour, `S3` the liquid, both at the root's `T`)."""
    ratios: dict[str, float] = {}
    state = result.run.state
    if not ledger.true(f"{case}: a final state", state is not None):
        return worst(ratios)
    assert state is not None
    root = REF["near_pure_cases"][case]["root"]
    for index, component in enumerate(_P2_COMPONENTS):
        for stream, key in (("S2", "vapor_mol_per_s"), ("S3", "liquid_mol_per_s")):
            column = f"{stream}.n.{component}"
            _p2_near(ledger, ratios, column, state[column], root[key][index], "flow")
    for stream in ("S2", "S3"):
        _p2_near(ledger, ratios, f"{stream}.T", state[f"{stream}.T"], root["T_K"], "T")
    return worst(ratios)


def _p2_certificate(
    ledger: Ledger, case: str, result: contract.Solved
) -> tuple[dict[str, CheckResult], dict[str, Any]]:
    """The contract test's `_verified`: `VERIFIED`, `NO_RANK_LOSS_DETECTED`, every
    `energy_balance.*` passing. Returns the checks by id and the observed facts."""
    certificate = result.certificate
    if not ledger.true(f"{case}: a certificate", certificate is not None):
        return {}, {"certificate": None}
    assert certificate is not None
    checks = result.checks()
    regularity = certificate.regularity.status if certificate.regularity is not None else None
    energy_failing = sorted(
        name
        for name, check in checks.items()
        if name.startswith("energy_balance.") and check.result != "pass"
    )
    facts = {
        "verification_status": certificate.verification_status,
        "regularity": regularity,
        "not_passing": sorted(
            f"{check.id}: {check.result}" for check in certificate.checks if check.result != "pass"
        ),
        "energy_balance_checks": sum(name.startswith("energy_balance.") for name in checks),
        "energy_balance_not_passing": energy_failing,
        "projection": certificate.transformations["projection"],
    }
    ledger.equal(f"{case}: verdict", facts["verification_status"], "VERIFIED")
    ledger.equal(f"{case}: regularity", regularity, "NO_RANK_LOSS_DETECTED")
    ledger.equal(f"{case}: energy checks not passing", energy_failing, [])
    return checks, facts


def _p2_degenerate(
    ledger: Ledger,
    case: str,
    checks: Mapping[str, CheckResult],
    unit: str,
    feed: str,
    bound: float | None = _P2_SATURATION_BOUND_K,
) -> dict[str, Any]:
    """Spec §9.1's judgement of a degenerate split (the contract test's `_degenerate`):
    `.saturation` present and passing (within `bound` of 0 when one is given),
    `independent_split` `not_applicable(temperature_degenerate)`, no fresh-flash ids."""
    saturation = checks.get(f"phase_admissibility.{unit}.{feed}.saturation")
    split = checks.get(f"independent_split.{unit}.{feed}")
    fresh = sorted(name for name in checks if name.startswith(f"independent_split.{unit}.{feed}."))
    facts = {
        "saturation": None
        if saturation is None
        else {
            "result": saturation.result,
            "value_K": saturation.value,
            "tolerance_K": saturation.tolerance,
        },
        "independent_split": None if split is None else [split.result, split.reason],
        "fresh_flash_ids": fresh,
    }
    where = f"{case}: {unit}.{feed}"
    ledger.true(f"{where} .saturation present", saturation is not None)
    if saturation is not None:
        ledger.equal(f"{where} .saturation result", saturation.result, "pass")
        if bound is not None:
            ledger.at_most(
                f"{where} |.saturation| K",
                None if saturation.value is None else abs(saturation.value),
                bound,
            )
    ledger.equal(
        f"{where} independent_split",
        facts["independent_split"],
        ["not_applicable", "temperature_degenerate"],
    )
    ledger.equal(f"{where} fresh-flash ids", fresh, [])
    return facts


def _p2_notes(
    ledger: Ledger,
    case: str,
    checks: Mapping[str, CheckResult],
    names: Sequence[str],
    note: str,
    streams: Sequence[str],
) -> dict[str, list[str]]:
    """Which of `note` (formatted per stream) each named check's qualification carries."""
    found: dict[str, list[str]] = {}
    for name in names:
        check = checks.get(name)
        qualification = (check.independence_qualification or "") if check is not None else ""
        found[name] = [s for s in streams if note.format(stream=s) in qualification]
        ledger.equal(f"{case}: {name} notes for", found[name], list(streams))
    return found


def _p2_v1(ledger: Ledger, case: str) -> dict[str, Any]:
    """The `T05-W13` run of the same revision: its outcome (the contract test's regression pin
    `V1_OUTCOME`) and no certificate — never `VERIFIED`."""
    result = contract.solved(case, "v1")
    ledger.equal(f"{case} under T05-W13: outcome", result.run.outcome, contract.V1_OUTCOME[case])
    ledger.equal(f"{case} under T05-W13: certificate", result.certificate is None, True)
    return {"outcome": result.run.outcome, "certificate": result.certificate is not None}


def _p2_diff(first: Any, second: Any, path: str = "") -> list[str]:
    """Every place two documents differ, exactly, by path (`==` on leaves)."""
    if isinstance(first, dict) and isinstance(second, dict):
        found: list[str] = []
        for key in sorted(set(first) | set(second), key=str):
            where = f"{path}.{key}"
            if key not in first or key not in second:
                found.append(f"{where}: present in one document only")
            else:
                found += _p2_diff(first[key], second[key], where)
        return found
    if isinstance(first, list | tuple) and isinstance(second, list | tuple):
        if len(first) != len(second):
            return [f"{path}: lengths {len(first)} and {len(second)}"]
        found = []
        for index, (a, b) in enumerate(zip(first, second, strict=True)):
            found += _p2_diff(a, b, f"{path}[{index}]")
        return found
    return [] if first == second else [_p2_safe(f"{path}: {first!r} vs {second!r}")]


# ------------------------------------------------------------------------------------ B07


def _b07() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """Each coupled case under `T05-W13` and `T05b-v2` through the contract test's `_coupled_r0`
    (plan, outcome, R0 events, structural report, certificate R0, the whole root fingerprint, the
    message, and the attempt records), each policy id asserted in its own run, then compared
    after the test's substitution `_without_policy` (the policy id out, and the plan ids that
    embed it)."""
    ledger = Ledger()
    cases: dict[str, Any] = {}
    for case in ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X"):
        v1 = contract._coupled_r0(case, contract.POLICY_V1)
        v2 = contract._coupled_r0(case, contract.POLICY_V2)
        ledger.equal(f"{case}: v1 policy_id", v1["plan"]["policy_id"], contract.POLICY_V1.policy_id)
        ledger.equal(f"{case}: v2 policy_id", v2["plan"]["policy_id"], contract.POLICY_V2.policy_id)
        differing = _p2_diff(
            contract._without_policy(v2, contract.POLICY_V2.policy_id),
            contract._without_policy(v1, contract.POLICY_V1.policy_id),
        )
        ledger.equal(f"{case}: differences after the substitution", len(differing), 0)
        certificate = v2.get("certificate") or {}
        cases[case] = {
            "policy_ids": [v1["plan"]["policy_id"], v2["plan"]["policy_id"]],
            "outcome": [v1["outcome"], v2["outcome"]],
            "verification_status": certificate.get("verification_status"),
            "compared_keys": sorted(v2),
            "events": len(v2.get("events", [])),
            "equal_after_substitution": not differing,
            "differences": len(differing),
            "first_differences": differing[:5],
        }
    value = {"cases": cases, "departures": ledger.departures}
    expected = {
        "cases": "C1, C2, C3, C3X: each policy id in its own run; equal after the substitution "
        "(the v2 id for the v1 id in `policy_id` and in the plan ids that embed it), 0 "
        "differences",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B07"] = (
    "v2 a conservative extension on T05's coupled cases: C1, C2, C3 and C3X solved under "
    "`T05-W13` and under `T05b-v2` by `test_t05b_contract._coupled_r0` (the plan's R0 projection, "
    "the outcome, `r0_projection` of the events, structural report and certificate, the whole "
    "root fingerprint, the message's first line, and every attempt record); each run's "
    "`policy_id` is its own policy's; after the test's substitution (Q-S3 (3): the policy id "
    "removed and replaced in the plan ids that embed it) the two documents are compared leaf by "
    "leaf and the number of differences recorded per case (registered: 0)."
)
MEASURES["B07"] = _b07


# --------------------------------------------------------------------------------- B08–B11


def _b08() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    result = contract.solved("SC-1")
    ledger.equal("SC-1: outcome", result.run.outcome, "CONVERGED")
    signatures = contract._signatures(result)
    ledger.equal("SC-1: signatures", signatures, [[["U-VLV", "TWO_PHASE"]]])
    candidates = result.messages("initializer_candidate")
    ledger.equal("SC-1: initializer_candidate records", candidates, [])
    state = _p2_sc_state(ledger, "SC-1", result)
    checks, certificate = _p2_certificate(ledger, "SC-1", result)
    degenerate = _p2_degenerate(ledger, "SC-1", checks, "U-VLV", "S2")
    notes = _p2_notes(
        ledger,
        "SC-1",
        checks,
        ("energy_balance.U-VLV", "energy_balance.envelope"),
        SPLIT_ENTHALPY_NOTE,
        ("S2",),
    )
    fingerprint = result.region.root_fingerprint
    branch = None if fingerprint is None else fingerprint["branch_found"]
    ledger.equal("SC-1: branch_found", branch, [["U-VLV", "TWO_PHASE"]])
    value = {
        "outcome": result.run.outcome,
        "signatures": signatures,
        "initializer_candidate": candidates,
        "state_vs_ref_worst_deviation_over_allowance": state,
        "certificate": certificate,
        "degenerate_judgement": degenerate,
        "split_enthalpy_note_streams": notes,
        "branch_found": branch,
        "under_T05_W13": _p2_v1(ledger, "SC-1"),
        "departures": ledger.departures,
    }
    expected = {
        "outcome": "CONVERGED",
        "signatures": [[["U-VLV", "TWO_PHASE"]]],
        "initializer_candidate": [],
        "state_vs_ref_worst_deviation_over_allowance": "≤ 1 (spec §13: T02 §6.4's 3.1e-7 mol/s, "
        "1e-5 K, 0.1 Pa, 1e-2 W; ref.single_component_cases.SC-1.root)",
        "certificate": "VERIFIED, NO_RANK_LOSS_DETECTED, every energy_balance check passing",
        "degenerate_judgement": {
            "saturation": f"present, passing, |value| ≤ {_P2_SATURATION_BOUND_K} K",
            "independent_split": ["not_applicable", "temperature_degenerate"],
            "fresh_flash_ids": [],
        },
        "split_enthalpy_note_streams": {
            "energy_balance.U-VLV": ["S2"],
            "energy_balance.envelope": ["S2"],
        },
        "branch_found": [["U-VLV", "TWO_PHASE"]],
        "under_T05_W13": {"outcome": contract.V1_OUTCOME["SC-1"], "certificate": False},
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B08"] = (
    "SC-1 under `T05b-v2` (the contract test's cached solve): outcome `CONVERGED`; the attempt "
    "signatures `[[U-VLV, TWO_PHASE]]`; no `initializer_candidate` record; every registered "
    "value of `ref.single_component_cases.SC-1.root` against the state at spec §13's EO "
    "allowances (the worst deviation over its allowance recorded, with where); the certificate "
    "`VERIFIED`, `NO_RANK_LOSS_DETECTED`, every `energy_balance.*` passing; "
    "`phase_admissibility.U-VLV.S2.saturation` present, passing, `|value| ≤ 1e-9 K` (recorded); "
    "`independent_split.U-VLV.S2` `not_applicable(temperature_degenerate)` with no fresh-flash "
    "ids; the degenerate-split note for `S2` on `energy_balance.U-VLV` and the envelope; "
    "`branch_found` `[[U-VLV, TWO_PHASE]]`; under `T05-W13` the outcome is the test's regression "
    "pin and no certificate is issued."
)
MEASURES["B08"] = _b08


def _b09() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    result = contract.solved("SC-2")
    ledger.equal("SC-2: outcome", result.run.outcome, "CONVERGED")
    signatures = contract._signatures(result)
    ledger.equal("SC-2: signatures", signatures, [[["U-PHF", "TWO_PHASE"]]])
    candidates = result.messages("initializer_candidate")
    ledger.equal("SC-2: initializer_candidate records", candidates, [])
    state = _p2_sc_state(ledger, "SC-2", result)
    checks, certificate = _p2_certificate(ledger, "SC-2", result)
    degenerate = _p2_degenerate(ledger, "SC-2", checks, "U-PHF", "S1")
    notes = _p2_notes(
        ledger,
        "SC-2",
        checks,
        ("energy_balance.U-PHF", "energy_balance.envelope"),
        SPLIT_ENTHALPY_NOTE,
        ("S2", "S3"),
    )
    fingerprint = result.region.root_fingerprint
    branch = None if fingerprint is None else fingerprint["branch_found"]
    ledger.equal("SC-2: branch_found", branch, [["U-PHF", "TWO_PHASE"]])
    value = {
        "outcome": result.run.outcome,
        "signatures": signatures,
        "initializer_candidate": candidates,
        "state_vs_ref_worst_deviation_over_allowance": state,
        "certificate": certificate,
        "degenerate_judgement": degenerate,
        "split_enthalpy_note_streams": notes,
        "branch_found": branch,
        "under_T05_W13": _p2_v1(ledger, "SC-2"),
        "departures": ledger.departures,
    }
    expected = {
        "outcome": "CONVERGED",
        "signatures": [[["U-PHF", "TWO_PHASE"]]],
        "initializer_candidate": [],
        "state_vs_ref_worst_deviation_over_allowance": "≤ 1 (spec §13's EO allowances; "
        "ref.single_component_cases.SC-2.root)",
        "certificate": "VERIFIED, NO_RANK_LOSS_DETECTED, every energy_balance check passing",
        "degenerate_judgement": {
            "saturation": f"present, passing, |value| ≤ {_P2_SATURATION_BOUND_K} K",
            "independent_split": ["not_applicable", "temperature_degenerate"],
            "fresh_flash_ids": [],
        },
        "split_enthalpy_note_streams": {
            "energy_balance.U-PHF": ["S2", "S3"],
            "energy_balance.envelope": ["S2", "S3"],
        },
        "branch_found": [["U-PHF", "TWO_PHASE"]],
        "under_T05_W13": {"outcome": contract.V1_OUTCOME["SC-2"], "certificate": False},
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B09"] = (
    "SC-2 under `T05b-v2`, as B08 for the products-style `U-PHF`: `CONVERGED`, signatures "
    "`[[U-PHF, TWO_PHASE]]`, no `initializer_candidate`; `ref.single_component_cases.SC-2.root` "
    "(streams and `U-PHF.Q`) at spec §13's EO allowances; `VERIFIED`, `NO_RANK_LOSS_DETECTED`, "
    "every energy check passing; `phase_admissibility.U-PHF.S1.saturation` `≤ 1e-9 K`, "
    "`independent_split.U-PHF.S1` `not_applicable(temperature_degenerate)`, no fresh-flash ids; "
    "the degenerate-split note for `S2` and `S3` on `energy_balance.U-PHF` and the envelope; "
    "`branch_found`; the `T05-W13` outcome against the test's regression pin, no certificate."
)
MEASURES["B09"] = _b09


def _b10() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    result = contract.solved("SC-3")
    entry = REF["single_component_cases"]["SC-3"]
    ledger.equal("SC-3: outcome", result.run.outcome, "CONVERGED")
    signatures = contract._signatures(result)
    ledger.equal("SC-3: attempt 0 signature", signatures[0], entry["signatures"]["opening"])
    ledger.equal("SC-3: final signature", signatures[-1], entry["signatures"]["final"])
    opened = result.messages("attempt_opened")
    updates = [message for message in opened if message.startswith("phase_update(")]
    registered_update = "phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE))"
    ledger.equal("SC-3: phase updates", updates, [registered_update])
    ledger.equal("SC-3: fallback items in the causes", [m for m in updates if "fallback(" in m], [])
    state = _p2_sc_state(ledger, "SC-3", result)
    checks, certificate = _p2_certificate(ledger, "SC-3", result)
    degenerate = {
        f"{unit}.{feed}": _p2_degenerate(ledger, "SC-3", checks, unit, feed)
        for unit, feed in (("U-VLV", "S2"), ("U-PHF", "S2"))
    }
    iterations = tuple(attempt.iterations for attempt in result.region.attempts)
    ledger.equal("SC-3: attempt iterations (regression)", iterations, contract.SC3_ITERATIONS)
    value = {
        "outcome": result.run.outcome,
        "signatures": signatures,
        "attempt_opened": opened,
        "phase_updates": updates,
        "attempt_count": len(iterations),
        "attempt_iterations": list(iterations),
        "state_vs_ref_worst_deviation_over_allowance": state,
        "certificate": certificate,
        "degenerate_judgement": degenerate,
        "under_T05_W13": _p2_v1(ledger, "SC-3"),
        "departures": ledger.departures,
    }
    expected = {
        "outcome": "CONVERGED",
        "signatures": {
            "opening": entry["signatures"]["opening"],
            "final": entry["signatures"]["final"],
        },
        "phase_updates": [registered_update],
        "attempt_count": len(contract.SC3_ITERATIONS),
        "attempt_iterations": list(contract.SC3_ITERATIONS),
        "state_vs_ref_worst_deviation_over_allowance": "≤ 1 (spec §13's EO allowances; "
        "ref.single_component_cases.SC-3.root)",
        "certificate": "VERIFIED, NO_RANK_LOSS_DETECTED, every energy_balance check passing",
        "degenerate_judgement": "U-VLV.S2 and U-PHF.S2 judged degenerate, as B08",
        "under_T05_W13": {"outcome": contract.V1_OUTCOME["SC-3"], "certificate": False},
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B10"] = (
    "SC-3 under `T05b-v2`: `CONVERGED`; attempt 0's and the final attempt's signatures against "
    "`ref.single_component_cases.SC-3.signatures`; the `attempt_opened` records hold exactly one "
    "phase update, `phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE))`, with no "
    "`fallback(…)` item (KS-1's primary answer); the state against `ref` at spec §13's EO "
    "allowances; `VERIFIED` with both splits (`U-VLV.S2`, `U-PHF.S2`) judged degenerate as in "
    "B08; the attempt count and iterations against the test's regression pin (W9.4's "
    "re-registration); the `T05-W13` outcome against its regression pin, no certificate."
)
MEASURES["B10"] = _b10


def _b11() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    result = contract.solved("SC-4")
    entry = REF["single_component_cases"]["SC-4"]
    flowsheet = result.binding.flowsheet
    start = traversal_start(flowsheet, result.binding.spec.variable_ids)
    ledger.true("SC-4: the traversal start", isinstance(start, TraversalStart))
    traversed = flowsheet.traverse({})
    ledger.equal("SC-4: traversal status", traversed.status, "ok")
    admitted = port_enthalpy(
        flowsheet.provider,
        traversed.streams["S2"],
        "VAPOR",
        flowsheet.components,
        flowsheet.context,
        port="inlet",
    )
    registered_inlet = entry["r007"]["U-PHF2.inlet_degeneracy_K"]
    ledger.equal("SC-4: U-PHF2 causal inlet failure", admitted.failure, None)
    ledger.within(
        "SC-4: U-PHF2 causal inlet admissibility K", admitted.admissibility, registered_inlet, 0.0
    )
    ledger.equal("SC-4: outcome", result.run.outcome, "CONVERGED")
    signatures = contract._signatures(result)
    ledger.equal("SC-4: signatures", signatures, [[list(item) for item in entry["signature"]]])
    state = _p2_sc_state(ledger, "SC-4", result)
    checks, certificate = _p2_certificate(ledger, "SC-4", result)
    inlets: dict[str, Any] = {}
    for name in ("phase_admissibility.U-PHF2.inlet", "phase_admissibility.U-PUMP.inlet"):
        check = checks.get(name)
        inlets[name] = None if check is None else {"result": check.result, "value_K": check.value}
        ledger.true(f"SC-4: {name} present", check is not None)
        if check is not None:
            ledger.equal(f"SC-4: {name} result", check.result, "pass")
            ledger.at_most(
                f"SC-4: |{name}| K",
                None if check.value is None else abs(check.value),
                _P2_SATURATION_BOUND_K,
            )
    work = None if result.run.state is None else result.run.state["U-PUMP.W"]
    work_error = ledger.within(
        "SC-4: U-PUMP.W", work, entry["root"]["U-PUMP.W"], _P2_ALLOWANCE["duty"]
    )
    value = {
        "traversal_start": isinstance(start, TraversalStart),
        "traversal_status": traversed.status,
        "U-PHF2_causal_inlet_admissibility_K": admitted.admissibility,
        "outcome": result.run.outcome,
        "signatures": signatures,
        "state_vs_ref_worst_deviation_over_allowance": state,
        "certificate": certificate,
        "inlet_admissibility": inlets,
        "U-PUMP.W": {"W": work, "error_W": work_error},
        "pre_change": "cited: docs/t05b-measurements.md W0.1 at b8c6442, not re-measured",
        "departures": ledger.departures,
    }
    expected = {
        "traversal_start": True,
        "traversal_status": "ok",
        "U-PHF2_causal_inlet_admissibility_K": registered_inlet,
        "outcome": "CONVERGED",
        "signatures": [[list(item) for item in entry["signature"]]],
        "state_vs_ref_worst_deviation_over_allowance": "≤ 1 (spec §13's EO allowances; "
        "ref.single_component_cases.SC-4.root)",
        "certificate": "VERIFIED, NO_RANK_LOSS_DETECTED, every energy_balance check passing",
        "inlet_admissibility": f"both present and passing, |value| ≤ {_P2_SATURATION_BOUND_K} K",
        "U-PUMP.W": {"W": entry["root"]["U-PUMP.W"], "error_W": f"≤ {_P2_ALLOWANCE['duty']}"},
        "pre_change": "INITIALIZATION_FAILED, initializer_failed(U-PHF2): "
        "inadmissible_phase(inlet, VAPOR) — W0.1's measurement at b8c6442, cited (Q-S3 (4))",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B11"] = (
    "SC-4 under `T05b-v2`: the traversal start exists and the traversal closes (`ok`); the PH "
    "kernel's causal admissibility of `U-PHF2`'s `VAPOR` inlet at the traversed `S2` is exactly "
    "`ref…SC-4.r007.U-PHF2.inlet_degeneracy_K` (0.0 K); `CONVERGED` with the registered "
    "signature; the state against `ref` at spec §13's EO allowances; `VERIFIED`, "
    "`NO_RANK_LOSS_DETECTED`; `phase_admissibility.U-PHF2.inlet` and `.U-PUMP.inlet` passing "
    "within 1e-9 K of 0; `U-PUMP.W` against `ref` at 1e-2 W. The pre-change clause (before T05b, "
    "`INITIALIZATION_FAILED`) is W0.1's measurement at the base `b8c6442`, cited, not re-measured "
    "(ruled Q-S3 (4)): the pre-change code does not exist at the head."
)
MEASURES["B11"] = _b11


# --------------------------------------------------------------------------- B12, B13, X09, X10


def _p2_band_routes(case: str) -> dict[str, Any]:
    """The traversal's band routes (the seeding test's source of `closure_route`) against the
    twin's 53-bit emulation `ref.near_pure_cases.<case>.measured_53_bit_traversal_route`."""
    start = seeding._start(bind(contract.near_pure(case)))
    routes = list(start.band_routes) if isinstance(start, TraversalStart) else None
    emulated = REF["near_pure_cases"][case]["measured_53_bit_traversal_route"]
    return {
        "band_routes": routes,
        "expected": ["U-PHF"] if emulated == "band" else [],
        "emulated": emulated,
    }


def _b12() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    cases: dict[str, Any] = {}
    for case in ("NP-1", "NP-2", "NP-3"):
        result = contract.solved(case)
        ledger.equal(f"{case}: outcome", result.run.outcome, "CONVERGED")
        signatures = contract._signatures(result)
        ledger.equal(f"{case}: signatures", signatures, [[["U-PHF", "TWO_PHASE"]]])
        state = _p2_np_state(ledger, case, result)
        checks, certificate = _p2_certificate(ledger, case, result)
        ledger.equal(
            f"{case}: judged at",
            certificate.get("projection"),
            {"judged_at": "projection", "reason": "", "categories": support.PROJECTED},
        )
        entry: dict[str, Any] = {
            "outcome": result.run.outcome,
            "signatures": signatures,
            "state_vs_ref_worst_deviation_over_allowance": state,
            "certificate": certificate,
        }
        if REF["near_pure_cases"][case]["degenerate"]:
            # §13: at NP-1's and NP-2's roots the saturation value's tolerance is τ_T (it is
            # the selection); B08's 1e-9 K is SC's ("as B09" names the checks, not that bound).
            entry["degenerate_judgement"] = _p2_degenerate(
                ledger, case, checks, "U-PHF", "S1", bound=None
            )
            entry["split_enthalpy_note_streams"] = _p2_notes(
                ledger,
                case,
                checks,
                ("energy_balance.U-PHF", "energy_balance.envelope"),
                SPLIT_ENTHALPY_NOTE,
                ("S2", "S3"),
            )
        else:
            entry["saturation_present"] = "phase_admissibility.U-PHF.S1.saturation" in checks
            ledger.equal(f"{case}: .saturation present", entry["saturation_present"], False)
            fresh = {}
            for suffix in ("total", *_P2_COMPONENTS):
                check = checks.get(f"independent_split.U-PHF.S1.{suffix}")
                fresh[suffix] = None if check is None else check.result
                ledger.equal(f"{case}: independent_split.U-PHF.S1.{suffix}", fresh[suffix], "pass")
            entry["fresh_flash_split"] = fresh
        unresolved = sorted(
            name
            for name, check in checks.items()
            if "fresh flash unresolved" in (check.independence_qualification or "")
        )
        ledger.equal(f"{case}: checks carrying the D3 note", unresolved, [])
        entry["d3_note_on"] = unresolved
        candidates = result.messages("initializer_candidate")
        entry["initializer_candidate"] = candidates
        entry["traversal"] = _p2_band_routes(case)
        ledger.equal(
            f"{case}: traversal band routes",
            entry["traversal"]["band_routes"],
            entry["traversal"]["expected"],
        )
        if case == "NP-1":
            ledger.equal(
                f"{case}: initializer_candidate", candidates, ["closure_route(U-PHF, band)"]
            )
            kinds = [event.kind for event in result.run.trace.events]
            at = kinds.index("initializer_candidate") if "initializer_candidate" in kinds else -1
            following = kinds[at + 1] if 0 <= at < len(kinds) - 1 else None
            first_opened = kinds.index("attempt_opened") if "attempt_opened" in kinds else -1
            ledger.equal(
                f"{case}: the record after the candidate", following, "initializer_accepted"
            )
            ledger.true(f"{case}: the first attempt opens after acceptance", first_opened > at + 1)
            entry["events_from_candidate"] = kinds[max(at, 0) : max(at, 0) + 3]
        cases[case] = entry
    value = {"cases": cases, "departures": ledger.departures}
    expected = {
        "outcome": "CONVERGED, signatures [[U-PHF, TWO_PHASE]], VERIFIED, NO_RANK_LOSS_DETECTED, "
        "judged at the projection",
        "state": "≤ 1 (spec §13's EO allowances; ref.near_pure_cases.*.root)",
        "NP-1, NP-2": "degenerate: .saturation present and passing (τ_T, §13), independent_split "
        "not_applicable(temperature_degenerate), no fresh-flash ids, the degenerate-split note on "
        "energy_balance.U-PHF and the envelope for S2 and S3",
        "NP-3": "no .saturation; independent_split.U-PHF.S1.total, .A, .B, .C present and passing",
        "d3_note_on": [],
        "NP-1 trace": "initializer_candidate closure_route(U-PHF, band), then "
        "initializer_accepted, then the first attempt_opened",
        "traversal band routes": "the twin's 53-bit emulation: NP-1, NP-2 band; NP-3 none",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B12"] = (
    "NP-1, NP-2, NP-3 under `T05b-v2`: `CONVERGED`, signatures `[[U-PHF, TWO_PHASE]]`; "
    "`ref.near_pure_cases.*.root` (both products' flows and `T`) at spec §13's EO allowances; "
    "`VERIFIED`, `NO_RANK_LOSS_DETECTED`, every energy check passing, judged at the projection; "
    "NP-1 and NP-2 judged degenerate as B09 (`.saturation` present and passing — its value "
    "recorded, at τ_T per §13 — `independent_split.U-PHF.S1` "
    "`not_applicable(temperature_degenerate)`, no fresh-flash ids, the degenerate-split note on "
    "the energy checks); NP-3 judged by the fresh flash (`.total`, `.A`, `.B`, `.C` present and "
    "passing, no `.saturation`); no check carries the D3 (unresolved) note; NP-1's trace "
    "`initializer_candidate` `closure_route(U-PHF, band)` then `initializer_accepted` before "
    "the first attempt; the traversal's band routes against the twin's 53-bit emulation."
)
MEASURES["B12"] = _b12


@cache
def _p2_floor(case: str) -> dict[str, Any]:
    """ADR 0013 D3's routing of `U-PHF` at the verifier's projection of the solved state (the
    contract test's `_floor_at_the_projection`), against the closed form `N ulp(T) / (w τ_flow)`
    of `ref.closed_form.routing`'s 20-digit fields at spec §7's tolerance `max(1e-6, 4 ulp(T)/w)`
    (`test_k04f9_rules`); and the printed six digits as that closed form rounded."""
    route, floor = contract._floor_at_the_projection(contract.solved(case))
    entry = F9_REF["closed_form"]["routing"][f"{case}:U-PHF.S1"]
    exact = f9_rules._exact_floor(entry)
    tolerance = f9_rules._floor_tolerance(entry)
    relative = None if floor is None else float(abs(Fraction(floor) - exact) / exact)
    return {
        "route": route,
        "floor_over_tau_flow": floor,
        "closed_form": float(exact),
        "relative_error": relative,
        "tolerance_relative": float(tolerance),
        "within": floor is not None and abs(Fraction(floor) - exact) <= tolerance * exact,
        "registered_printed": entry["floor_over_tau_flow"],
        "printed_is_closed_form_rounded": Decimal(entry["floor_over_tau_flow"])
        == f9_rules._six_digits(exact),
        "registered_route": entry["route"],
    }


def _p2_np_g(ledger: Ledger) -> dict[str, Any]:
    """NP-G's facts common to B13 and X09."""
    result = contract.solved("NP-G")
    certificate = result.certificate
    ledger.equal("NP-G: outcome", result.run.outcome, "CONVERGED")
    ledger.true("NP-G: a certificate", certificate is not None)
    if certificate is None:
        return {"outcome": result.run.outcome, "certificate": None}
    checks = result.checks()
    split = checks.get("independent_split.U-PHF.S1")
    return {
        "outcome": result.run.outcome,
        "verification_status": certificate.verification_status,
        "projection": certificate.transformations["projection"],
        "saturation_present": "phase_admissibility.U-PHF.S1.saturation" in checks,
        "independent_split": None if split is None else [split.result, split.reason],
        "fresh_flash_ids": sorted(n for n in checks if n.startswith("independent_split.U-PHF.S1.")),
        "failing": sorted(c.id for c in certificate.checks if c.result == "fail"),
        "unsupported": sorted(c.id for c in certificate.checks if c.result == "unsupported"),
        "failing_residual": sorted(
            c.id for c in certificate.checks if c.category == "residual" and c.result == "fail"
        ),
        "checks": checks,
    }


#: B13's set of checks a `FAILED` NP-G may fail (T04 F9's mechanism, spec B13).
_P2_NP_G_MAY_FAIL = ("energy_balance.U-PHF", "energy_balance.envelope")


def _b13() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    facts = _p2_np_g(ledger)
    facts.pop("checks", None)
    if "verification_status" in facts:
        ledger.equal("NP-G: .saturation present", facts["saturation_present"], False)
        verdict = facts["verification_status"]
        ledger.true("NP-G: verdict VERIFIED or FAILED", verdict in ("VERIFIED", "FAILED"))
        ledger.equal("NP-G: verdict (regression pin)", verdict, contract.NP_G_VERDICT)
        outside = [
            name
            for name in facts["failing"]
            if name not in _P2_NP_G_MAY_FAIL and not name.startswith("independent_split.U-PHF.S1.")
        ]
        ledger.equal("NP-G: failing checks outside B13's set", outside, [])
        ledger.equal("NP-G: unsupported checks", facts["unsupported"], [])
        ledger.equal("NP-G: failing residual rows", facts["failing_residual"], [])
        ledger.equal(
            "NP-G: independent split (X09's amendment)",
            facts["independent_split"],
            ["not_applicable", "fresh_flash_unresolved"],
        )
    value = {**facts, "departures": ledger.departures}
    expected = {
        "outcome": "CONVERGED",
        "saturation_present": False,
        "verification_status": f"VERIFIED or FAILED; the regression pin {contract.NP_G_VERDICT}",
        "failing": "a subset of {energy_balance.U-PHF, energy_balance.envelope, "
        "independent_split.U-PHF.S1.*}",
        "unsupported": [],
        "failing_residual": [],
        "independent_split": ["not_applicable", "fresh_flash_unresolved"],
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B13"] = (
    "NP-G, the residual limitation, as amended by K04-F9 X09: under `T05b-v2` `CONVERGED`; not "
    "degenerate (no `phase_admissibility.U-PHF.S1.saturation`); the verdict is `VERIFIED` or "
    "`FAILED` and equals the contract test's regression pin (`VERIFIED`); the failing checks "
    "(recorded) lie in {`energy_balance.U-PHF`, `energy_balance.envelope`, "
    "`independent_split.U-PHF.S1.*`}; no `unsupported` check and no failing residual row; "
    "`independent_split.U-PHF.S1` `not_applicable(fresh_flash_unresolved)` (ADR 0013 D3)."
)
MEASURES["B13"] = _b13


def _p2_energy(
    ledger: Ledger, case: str, checks: Mapping[str, CheckResult], note_expected: bool
) -> dict[str, Any]:
    """`energy_balance.U-PHF` and the envelope: `|value|/τ_E`, and which streams' D3 note each
    carries."""
    found: dict[str, Any] = {}
    for name in ("energy_balance.U-PHF", "energy_balance.envelope"):
        check = checks.get(name)
        if not ledger.true(f"{case}: {name} present", check is not None):
            continue
        assert check is not None
        qualification = check.independence_qualification or ""
        streams = [
            s for s in ("S2", "S3") if UNRESOLVED_ENTHALPY_NOTE.format(stream=s) in qualification
        ]
        ratio = (
            abs(check.value) / check.tolerance
            if check.value is not None and check.tolerance
            else None
        )
        found[name] = {
            "result": check.result,
            "value_W": check.value,
            "over_tau_E": ratio,
            "d3_note_streams": streams,
        }
        ledger.equal(f"{case}: {name} result", check.result, "pass")
        ledger.equal(
            f"{case}: {name} D3 note streams", streams, ["S2", "S3"] if note_expected else []
        )
        if note_expected:
            ledger.at_most(f"{case}: |{name}| / τ_E", ratio, _P2_ENERGY_FRACTION)
    return found


def _p2_floor_ledger(ledger: Ledger, case: str, route: str) -> dict[str, Any]:
    floor = _p2_floor(case)
    ledger.equal(f"{case}: route at the projection", floor["route"], route)
    ledger.equal(f"{case}: registered route", floor["registered_route"], route)
    ledger.true(
        f"{case}: floor ratio within max(1e-6, 4 ulp(T)/w) of the closed form", floor["within"]
    )
    ledger.true(
        f"{case}: the printed six digits are the closed form rounded",
        floor["printed_is_closed_form_rounded"],
    )
    return floor


def _x09() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    facts = _p2_np_g(ledger)
    checks: dict[str, CheckResult] = facts.pop("checks", {})
    value: dict[str, Any] = dict(facts)
    if checks:
        ledger.equal("NP-G: verdict", facts["verification_status"], "VERIFIED")
        ledger.equal(
            "NP-G: independent split",
            facts["independent_split"],
            ["not_applicable", "fresh_flash_unresolved"],
        )
        ledger.equal("NP-G: .total/.c ids", facts["fresh_flash_ids"], [])
        ledger.equal("NP-G: .saturation present", facts["saturation_present"], False)
        closure = checks.get("phase_admissibility.U-PHF.S1.closure")
        value["closure"] = (
            None if closure is None else {"result": closure.result, "value": closure.value}
        )
        ledger.true("NP-G: .closure evaluated", closure is not None and closure.value is not None)
        ledger.equal("NP-G: .closure result", None if closure is None else closure.result, "pass")
        value["energy"] = _p2_energy(ledger, "NP-G", checks, note_expected=True)
        ledger.equal("NP-G: unsupported checks", facts["unsupported"], [])
        ledger.equal("NP-G: failing residual rows", facts["failing_residual"], [])
    value["routing"] = _p2_floor_ledger(ledger, "NP-G", "unresolved")
    value["departures"] = ledger.departures
    entry = F9_REF["closed_form"]["routing"]["NP-G:U-PHF.S1"]
    expected = {
        "outcome": "CONVERGED",
        "verification_status": "VERIFIED",
        "independent_split": ["not_applicable", "fresh_flash_unresolved"],
        "fresh_flash_ids": [],
        "saturation_present": False,
        "closure": "evaluated and passing",
        "energy": "energy_balance.U-PHF and the envelope pass, carry the D3 note for S2 and S3, "
        f"and are ≤ {_P2_ENERGY_FRACTION} τ_E",
        "unsupported": [],
        "failing_residual": [],
        "routing": {
            "route": "unresolved",
            "closed_form_of": {
                key: entry[key] for key in ("T_K", "N_mol_per_s", "T_bubble_K", "T_dew_K")
            },
            "registered_printed": entry["floor_over_tau_flow"],
            "tolerance": "relative ≤ max(1e-6, 4 ulp(T)/w) (K04-F9 spec §7, amended Q-S2)",
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X09"] = (
    "T05b B13 amended, NP-G under `T05b-v2`: `CONVERGED`, `VERIFIED`; "
    "`independent_split.U-PHF.S1` `not_applicable(fresh_flash_unresolved)` with no `.total`/`.c` "
    "ids and no `.saturation`; `phase_admissibility.U-PHF.S1.closure` evaluated and passing; "
    "`energy_balance.U-PHF` and the envelope passing, carrying the D3 note for `S2` and `S3`, "
    "with `|value|/τ_E ≤ 1e-3` (recorded); no `unsupported` check, no failing residual; the "
    "routing at the verifier's projection of the solved state is `unresolved` and its floor "
    "ratio is compared with the closed form `N ulp(T) / ((T_d − T_b) τ_flow)` of "
    "`ref.closed_form.routing.NP-G:U-PHF.S1`'s 20-digit fields at spec §7's tolerance "
    "`max(1e-6, 4 ulp(T)/w)` relative (the relative error recorded); the printed six digits are "
    "that closed form rounded."
)
MEASURES["X09"] = _x09


def _x10() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    result = contract.solved("NP-3")
    checks, certificate = _p2_certificate(ledger, "NP-3", result)
    fresh = {}
    for suffix in ("total", *_P2_COMPONENTS):
        check = checks.get(f"independent_split.U-PHF.S1.{suffix}")
        fresh[suffix] = None if check is None else check.result
        ledger.equal(f"NP-3: independent_split.U-PHF.S1.{suffix}", fresh[suffix], "pass")
    unresolved = sorted(
        name
        for name, check in checks.items()
        if "fresh flash unresolved" in (check.independence_qualification or "")
    )
    ledger.equal("NP-3: checks carrying the D3 note", unresolved, [])
    value = {
        "certificate": certificate,
        "fresh_flash_split": fresh,
        "d3_note_on": unresolved,
        "routing": _p2_floor_ledger(ledger, "NP-3", "resolved"),
        "departures": ledger.departures,
    }
    entry = F9_REF["closed_form"]["routing"]["NP-3:U-PHF.S1"]
    expected = {
        "certificate": "VERIFIED, NO_RANK_LOSS_DETECTED",
        "fresh_flash_split": {suffix: "pass" for suffix in ("total", *_P2_COMPONENTS)},
        "d3_note_on": [],
        "routing": {
            "route": "resolved",
            "closed_form_of": {
                key: entry[key] for key in ("T_K", "N_mol_per_s", "T_bubble_K", "T_dew_K")
            },
            "registered_printed": entry["floor_over_tau_flow"],
            "tolerance": "relative ≤ max(1e-6, 4 ulp(T)/w) (K04-F9 spec §7, amended Q-S2)",
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X10"] = (
    "NP-3 under `T05b-v2` (T05b B12 unchanged): `VERIFIED`; resolved — "
    "`independent_split.U-PHF.S1.total`, `.A`, `.B`, `.C` present and passing, no check "
    "carrying the D3 note; the routing at the verifier's projection is `resolved` and its floor "
    "ratio is compared with the closed form of `ref.closed_form.routing.NP-3:U-PHF.S1`'s "
    "20-digit fields at `max(1e-6, 4 ulp(T)/w)` relative (the relative error recorded); the "
    "printed six digits are that closed form rounded."
)
MEASURES["X10"] = _x10


# ------------------------------------------------------------------------------------ B14


def _p2_distances(view: Any, state: Mapping[str, float]) -> dict[str, float]:
    """`test_t05b_verifier._distances`, by name: the verifier's `δ` at every flowing stream's
    own `(n, T, P)` and at every flowing lifted split's feed at the split's `(T, P)`."""
    from openflowsheet.models import flow_id, pressure_id, temperature_id
    from openflowsheet.verify import saturation as verifier_band

    provider, context = verifier_tests.PROVIDER, verifier_tests.CONTEXT
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    found: dict[str, float] = {}
    for stream in view.streams:
        n = tuple(state[flow_id(stream, c)] for c in view.components)
        if any(value > 0.0 for value in n):
            found[stream] = verifier_band.degeneracy_distance(
                provider, n, state[temperature_id(stream)], state[pressure_id(stream)], context
            )
    for split in splits:
        n = tuple(state[column] for column in split.feed)
        if any(value > 0.0 for value in n):
            found[f"split:{split.unit}"] = verifier_band.degeneracy_distance(
                provider, n, state[split.temperature], state[split.pressure], context
            )
    return found


def _p2_w1d_pairing() -> dict[str, Any]:
    """W1.d's bitwise legacy/general pairing (`test_t05_w1d_verifier`'s helpers): at the root,
    the legacy set judged where the certificate judges against the certificate, and each engine
    at `x_final` and at `x̃`; at the start `x⁰`, the two engines. Counts of differing bits and
    uncovered ids."""
    document = w1d.shaped_revision()
    binding, plan, run = w1d._solve(document)
    assert run.state is not None
    certificate = verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    judged_at, projected = w1d._projection(binding, document, run.state)
    at_final, _ = w1d.run_checks(w1d._legacy(), run.state)
    at_projection, _ = w1d.run_checks(w1d._legacy(), projected)
    legacy = w1d._at_one_state(at_final, at_projection)
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert isinstance(start, dict), start
    legacy_start, _ = w1d.run_checks(w1d._legacy(), start)
    pairs = w1d._pairs(legacy)
    return {
        "certificate_verdict": certificate.verification_status,
        "judged_at": judged_at,
        "pairs": len(pairs),
        "root": {
            "legacy_vs_certificate": w1d._cross_validate(legacy, list(certificate.checks)),
            "uncovered": w1d._uncovered(legacy, list(certificate.checks), pairs),
            "at_x_final": w1d._cross_validate(at_final, w1d._general_at(document, run.state)),
            "at_projection": w1d._cross_validate(
                at_projection, w1d._general_at(document, projected)
            ),
        },
        "start": {
            "engines": w1d._cross_validate(legacy_start, w1d._general_at(document, start)),
        },
    }


def _b14() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    t05_key = _key_sha256(identity_document()["t05"])
    ledger.equal("the t05 key", t05_key, REGISTERED["t05_key_sha256"])
    pairing = _p2_w1d_pairing()
    ledger.equal("W1.d: judged at", pairing["judged_at"], "projection")
    for where, found in (*pairing["root"].items(), *pairing["start"].items()):
        ledger.equal(f"W1.d pairing: {where}", found, [])
    states: dict[str, Any] = {}
    overall: dict[str, float] = {}
    roots: dict[str, float] = {}
    for label, (document, state, registered) in verifier_tests._registered_states().items():
        view = parse_revision(document)
        splits = lifted_splits(
            [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
        )
        found = verifier_tests.degeneracy(
            view, splits, state, verifier_tests.PROVIDER, verifier_tests.CONTEXT
        )
        ledger.equal(
            f"{label}: degeneracy finds nothing", found == verifier_tests.Degeneracy(), True
        )
        distances = _p2_distances(view, state)
        ledger.equal(
            f"{label}: the named distances are the test's",
            sorted(distances.values()),
            sorted(verifier_tests._distances(view, state)),
        )
        ledger.true(
            f"{label}: every δ finite",
            bool(distances) and all(map(math.isfinite, distances.values())),
        )
        where = min(distances, key=lambda key: distances[key])
        least = distances[where]
        ledger.true(f"{label}: min δ ≥ 1 K ({least!r} at {where})", least >= 1.0)
        named = {f"{label} {key}": item for key, item in distances.items()}
        overall.update(named)
        entry: dict[str, Any] = {"count": len(distances), "min_K": least, "where": where}
        if registered is not None:
            registered_min = verifier_tests._registered_minimum(registered)
            entry["registered_min_K"] = registered_min
            entry["error_K"] = abs(least - registered_min)
            ledger.at_most(f"{label}: |min δ − registered min| K", entry["error_K"], 1e-6)
            roots.update(named)
        states[label] = entry
    least_where = min(overall, key=lambda key: overall[key])
    root_where = min(roots, key=lambda key: roots[key])
    registered_min = min(
        support.number(item)
        for case in REF["degeneracy_at_registered_states_K"].values()
        for item in case.values()
    )
    value = {
        "t05_key_sha256": t05_key,
        "w1d_pairing": pairing,
        "states": states,
        "min_delta_K": {"value": overall[least_where], "where": least_where, "count": len(overall)},
        "min_delta_at_the_roots_K": {
            "value": roots[root_where],
            "where": root_where,
            "over_tau_T": roots[root_where] / KIND_TOLERANCE["temperature"],
            "registered": registered_min,
        },
        "departures": ledger.departures,
    }
    expected = {
        "t05_key_sha256": REGISTERED["t05_key_sha256"],
        "w1d_pairing": "judged at the projection; every pair bitwise equal at the root (legacy "
        "judged where the certificate judges, each engine at x_final and at the projection) and "
        "at the start x0; no uncovered legacy id",
        "states": "degeneracy finds nothing; every δ ≥ 1 K; at the roots the minimum within 1e-6 "
        "K of ref.degeneracy_at_registered_states_K's",
        "min_delta_K": "≥ 1 K",
        "min_delta_at_the_roots_K": {
            "registered": registered_min,
            "over_tau_T": "≥ 1.7e7 (spec B14's margin)",
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B14"] = (
    "Degeneracy inert on registered certificates: the K05 identity document's `t05` key (C1–C3 "
    "certificates' R0) hashes to the registered `ddbd0f71…`; W1.d's bitwise legacy/general "
    "pairing (`test_t05_w1d_verifier`'s helpers) — at its root the legacy set judged where the "
    "certificate judges against the certificate, each engine at `x_final` and at the "
    "projection, and at its start `x⁰` — has no differing bit and no uncovered id; at W1.d's "
    "root and start and C1–C3's roots (`test_t05b_verifier._registered_states`) `degeneracy` "
    "finds nothing, and the verifier's `δ` at every flowing stream and flowing lifted split is "
    "≥ 1 K (the minimum and where recorded), at the roots within 1e-6 K of "
    "`ref.degeneracy_at_registered_states_K`'s minimum for that case (17.53 K the least, "
    "recorded with its margin in τ_T)."
)
MEASURES["B14"] = _b14


# ------------------------------------------------------------------------------------ B20


#: The DZ cases (B20 (a), (c)): every dormant case of spec §12.5 and its amendment.
_P2_DZ_CASES = (
    "DZ-1",
    "DZ-2",
    "DZ-3",
    "DZ-4",
    "DZ-5",
    "DZ-6",
    "DZ-7",
    "DZ-8",
    "DZ-9",
    "DZ-10",
    "DZ-11",
    "DZ-12",
    "DZ-2C",
)


def _p2_dz_run(case: str) -> dict[str, Any]:
    """One solve of a DZ case as `scripts/t05b_identity._case` (B22's) runs it — the common path,
    or the planned region from `ref`'s registered start for DZ-3, DZ-10, DZ-11, DZ-12, DZ-2C —
    keeping the event messages: the outcome, the message's first line, the records, the R0
    projection (events, structural report, the certificate when `CONVERGED`) and the root
    fingerprint."""
    document = _t05b_builders()[case]()
    binding = bind(dict(document))
    plan, report = plan_revision(binding, support.POLICY_V2)
    assert isinstance(plan, ExecutionPlan), plan
    solve_plan = plan.steps[-1].solve_plan
    state: dict[str, float] | None = None
    claim: Any
    if case in REGISTERED_STARTS:
        start = support.registered_state(support.REF[REGISTERED_STARTS[case]][case]["start"])
        trace = Trace()
        region = support.solve_from_v2(binding, start, support.POLICY_V2, trace=trace)
        outcome, message, events = region.outcome, region.message, trace.events
        state = dict(region.state) if outcome == "CONVERGED" else None
        detail: Any = region
        claim = region
    else:
        run = execute_plan(
            plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=support.POLICY_V2
        )
        outcome, message, events = run.outcome, run.message, run.trace.events
        detail = run.steps[-1].detail if run.steps else None
        claim = run
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in events],
        "structural-report.json": report.as_document(),
    }
    if outcome == "CONVERGED":
        certificate = verify_revision(
            binding, dict(document), claim, state=state, solve_plan=solve_plan
        )
        artifacts["solution-certificate.json"] = certificate.as_document()
    converged = outcome == "CONVERGED" and isinstance(detail, RegionResult)
    return {
        "outcome": outcome,
        "message": message.splitlines()[0] if message else "",
        "records": [(event.kind, event.message) for event in events],
        "r0": r0_projection(artifacts),
        "fingerprint": detail.root_fingerprint if converged else None,
    }


@cache
def _p2_dz_first(case: str) -> dict[str, Any]:
    return _p2_dz_run(case)


def _p2_contract_projection(result: contract.Solved) -> dict[str, Any]:
    """`test_b20c_deterministic_and_float_free`'s projection: the R0 projection of the events and
    the certificate, the outcome, every record and the whole root fingerprint."""
    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in result.run.trace.events]
    }
    if result.certificate is not None:
        artifacts["solution-certificate.json"] = result.certificate.as_document()
    return {
        "r0": r0_projection(artifacts),
        "outcome": result.run.outcome,
        "records": [(event.kind, event.message) for event in result.run.trace.events],
        "fingerprint": result.region.root_fingerprint,
    }


#: The R0 fields that identify declared inputs, not a state (B22's audit: `model_version` embeds
#: short digests such as `65e88d404f97`, whose `5e8` is float-shaped text computed from nothing).
_P2_DECLARED_INPUTS = ("constants_sha256", "model_version", "variable_ids_sha256")


def _p2_float_shaped(r0: Any, records: Sequence[tuple[str, str]], message: str) -> list[str]:
    """Float-shaped text (`FLOAT`) in an R0 projection's strings (the declared inputs' identifiers
    and 64-hex digests set aside, as B22's audit sets them aside), in the records the contract
    test scans (`attempt_opened`, `initializer_candidate`, `initializer_accepted`) and in the
    message's first line; and every float the projection holds (`floats_in`)."""
    found = [f"float at {path}" for path in floats_in(r0)]
    for path, text in _strings(r0):
        if path.rsplit(".", 1)[-1] in _P2_DECLARED_INPUTS:
            continue
        if FLOAT.search(HEX64.sub("", text)):
            found.append(_p2_safe(f"{path}: {text}"))
    for kind, text in records:
        scanned = kind in ("attempt_opened", "initializer_candidate", "initializer_accepted")
        if scanned and FLOAT.search(text):
            found.append(_p2_safe(f"{kind}: {text}"))
    if FLOAT.search(message):
        found.append(_p2_safe(f"message: {message}"))
    return found


def _p2_b20a(ledger: Ledger) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for case in sorted(contract.CASES):
        found = [
            m
            for m in contract.solved(case).messages("initializer_candidate")
            if m.startswith("closure_route(")
        ]
        expected = ["closure_route(U-PHF, band)"] * contract.BAND_RECORDS.get(case, 0)
        ledger.equal(f"(a) {case}: closure_route records", found, expected)
        records[case] = found
    for case in _P2_DZ_CASES:
        found = [
            message
            for kind, message in _p2_dz_first(case)["records"]
            if kind == "initializer_candidate" and message.startswith("closure_route(")
        ]
        ledger.equal(f"(a) {case}: closure_route records", found, [])
        records[case] = found
    return records


def _p2_b20b(ledger: Ledger) -> dict[str, Any]:
    """`test_b20b_the_contract_kernel_of_a_ph_type_split`'s construction: SC-1's valve outlet
    frozen `LIQUID` at each KS state, the contract's kernel with `U-VLV` a PH-type unit, and the
    TP flash's answer (no PH units)."""
    binding = bind(contract.sc1())
    flowsheet = binding.flowsheet
    (split,) = lifted_splits(
        [
            (unit.unit_id, unit.model_id, flowsheet.wiring[unit.unit_id])
            for unit in flowsheet.units()
        ],
        flowsheet.components,
    )
    ledger.equal("(b) closure types", closure_types(flowsheet.units()), {"U-VLV": "PH"})
    found: dict[str, Any] = {}
    for state_id in ("KS-1", "KS-2", "KS-3"):
        entry = REF["contract_kernel_states"][state_id]
        state = contract._kernel_state(entry)
        answer = _contract_kernel(
            flowsheet.provider, flowsheet.context, split, state, frozenset({"U-VLV"})
        )
        record = f"fallback(U-VLV, {answer.fallback})" if answer.fallback else ""
        tp = _contract_kernel(flowsheet.provider, flowsheet.context, split, state, frozenset())
        observed: dict[str, Any] = {
            "regime": answer.regime,
            "record": record,
            "tp_answer": [tp.regime, tp.fallback],
        }
        ledger.equal(f"(b) {state_id} regime", answer.regime, entry["expected_regime"])
        ledger.equal(f"(b) {state_id} record", record, entry["expected_record"])
        ledger.equal(f"(b) {state_id} TP answer", observed["tp_answer"], [entry["tp_regime"], ""])
        if "expected_T_K" in entry:
            temperature = answer.values.get("S2.T")
            feed = sum(support.number(value) for value in entry["feed_mol_per_s"])
            beta = answer.values["S2.V"] / feed
            observed["T_K"] = temperature
            observed["T_error_K"] = ledger.within(
                f"(b) {state_id} T", temperature, entry["expected_T_K"], _P2_KS_T_K
            )
            observed["beta"] = beta
            observed["beta_error"] = ledger.within(
                f"(b) {state_id} beta", beta, entry["expected_beta"], _P2_KS_BETA
            )
            conservation = max(
                abs(
                    answer.values[f"S2.vap.{c}"] + answer.values[f"S2.liq.{c}"] - state[f"S2.n.{c}"]
                )
                for c in _P2_COMPONENTS
            )
            observed["component_conservation_mol_per_s"] = conservation
            ledger.at_most(f"(b) {state_id} conservation", conservation, _P2_KS_CONSERVATION)
        else:
            # The TP flash's answer carries no temperature: the trial's stays.
            observed["T_in_answer"] = "S2.T" in answer.values
            observed["V"] = answer.values.get("S2.V")
            ledger.equal(f"(b) {state_id} no T in the answer", observed["T_in_answer"], False)
            ledger.equal(f"(b) {state_id} V", observed["V"], 0.0)
        found[state_id] = observed
    return found


def _p2_b20c(ledger: Ledger) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for case in sorted(contract.CASES):
        first = _p2_contract_projection(contract.solved(case))
        second = _p2_contract_projection(contract.solve(contract.CASES[case](), support.POLICY_V2))
        differing = _p2_diff(first, second)
        message = contract.solved(case).run.message
        shaped = _p2_float_shaped(
            first["r0"], first["records"], message.splitlines()[0] if message else ""
        )
        ledger.equal(f"(c) {case}: differences between the two solves", len(differing), 0)
        ledger.equal(f"(c) {case}: float-shaped R0 text", shaped, [])
        found[case] = {"differences": len(differing), "float_shaped": shaped[:3]}
    for case in _P2_DZ_CASES:
        first, second = _p2_dz_first(case), _p2_dz_run(case)
        differing = _p2_diff(first, second)
        shaped = _p2_float_shaped(first["r0"], first["records"], first["message"])
        ledger.equal(f"(c) {case}: differences between the two solves", len(differing), 0)
        ledger.equal(f"(c) {case}: float-shaped R0 text", shaped, [])
        found[case] = {"differences": len(differing), "float_shaped": shaped[:3]}
    return found


def _p2_b20d(ledger: Ledger) -> dict[str, Any]:
    from openflowsheet.orchestrator.phase_contract import _changes
    from openflowsheet.orchestrator.region import _attempt_screen

    # DZ-12: the item is in attempt 0's signature, absent from attempt 1's, in no cause string.
    result, trace = dormancy._dz12()
    (item,) = [tuple(entry) for entry in _P2_DZ12["attempt0"]["signature"] if "." in entry[0]]
    signatures = [[tuple(entry) for entry in attempt.signature] for attempt in result.attempts]
    opened = [event.message for event in trace.events if event.kind == "attempt_opened"]
    naming = [event.message for event in trace.events if item[0] in event.message]
    ledger.equal("(d) DZ-12 outcome", result.outcome, "CONVERGED")
    ledger.equal("(d) DZ-12 attempts", len(signatures), 2)
    ledger.true("(d) DZ-12 item in attempt 0", bool(signatures) and item in signatures[0])
    ledger.true(
        "(d) DZ-12 item absent from attempt 1", len(signatures) > 1 and item not in signatures[1]
    )
    ledger.equal("(d) DZ-12 records naming the item", naming, [])
    ledger.equal(
        "(d) DZ-12 attempt_opened", opened, ["initial", _P2_DZ12["attempt1"]["opening_message"]]
    )
    dz12 = {
        "item": list(item),
        "signatures": [[list(entry) for entry in signature] for signature in signatures],
        "attempt_opened": opened,
        "records_naming_the_item": naming,
    }
    # The screen-reported switch (`test_b20d_a_screen_reported_switch_names_the_item`'s
    # construction): DZ-6's pump outlet at its root and with its feed flowing, and the wall text.
    binding = bind(dormancy.dz6())
    flowsheet = binding.flowsheet
    (form,) = dormancy._forms(binding)
    root = support.registered_state(dormancy.CASES["DZ-6"]["root"])

    def reported(state: dict[str, float]) -> Any:
        screen = _attempt_screen(
            splits=(),
            regimes={},
            provider=flowsheet.provider,
            context=flowsheet.context,
            epsilon=support.POLICY_V2.admissibility_epsilon,
            ph_units=frozenset(),
            v2=True,
            dormancy=(form,),
        )
        return screen(dict(state))

    declared = {form.item: form.declared}
    pump = (("U-PUMP.outlet", "ZERO_FLOW"),)
    (hot, _) = dormancy._forms(bind(dormancy.dz12()))
    screen = {
        "DZ-6 root": [list(entry) for entry in reported(root)],
        "DZ-6 feed flowing": [list(entry) for entry in reported({**root, "S1.n.B": 1.0})],
        "entering": _changes((), pump, declared),
        "leaving": _changes(pump, (), declared),
        "with a lifted change": _changes(
            (("U-PHF", "LIQUID"), *pump), (("U-PHF", "TWO_PHASE"),), declared
        ),
        "exchanger hot side leaving": _changes(
            (("U-HX.hot_outlet", "ZERO_FLOW"),), (), {hot.item: hot.declared}
        ),
    }
    # Spec §7.8 (iii): `phase_wall(…, U.port:from->to)`, the absent side by the declared phase
    # (the dormancy test's literals).
    screen_expected = {
        "DZ-6 root": [["U-PUMP.outlet", "ZERO_FLOW"]],
        "DZ-6 feed flowing": [],
        "entering": "U-PUMP.outlet:LIQUID->ZERO_FLOW",
        "leaving": "U-PUMP.outlet:ZERO_FLOW->LIQUID",
        "with a lifted change": "U-PHF:LIQUID->TWO_PHASE, U-PUMP.outlet:ZERO_FLOW->LIQUID",
        "exchanger hot side leaving": "U-HX.hot_outlet:ZERO_FLOW->VAPOR",
    }
    for key, expected in screen_expected.items():
        ledger.equal(f"(d) screen: {key}", screen[key], expected)
    # A conflict closes with `zero_flow_conflict(row)` (B28): DZ-11 and DZ-2C.
    conflicts: dict[str, Any] = {}
    for case in ("DZ-11", "DZ-2C"):
        run = _p2_dz_first(case)
        registered = REF["zero_flow_conflicts"][case]["expected"]
        conflicts[case] = [run["outcome"], run["message"]]
        ledger.equal(f"(d) {case}", conflicts[case], [registered["outcome"], registered["message"]])
    return {"DZ-12": dz12, "screen": screen, "conflicts": conflicts}


def _b20() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    value = {
        "a_closure_route_records": _p2_b20a(ledger),
        "b_contract_kernel": _p2_b20b(ledger),
        "c_twice": _p2_b20c(ledger),
        "d_form_switches": _p2_b20d(ledger),
        "departures": ledger.departures,
    }
    expected = {
        "a_closure_route_records": "none on SC-1…SC-4, NP-3, DZ-*; NP-1 exactly one "
        "`closure_route(U-PHF, band)`; NP-2's and NP-G's the test's regression pins "
        f"({contract.BAND_RECORDS['NP-2']} and {contract.BAND_RECORDS['NP-G']})",
        "b_contract_kernel": {
            state_id: {
                "regime": entry["expected_regime"],
                "record": entry["expected_record"],
                "tp_answer": [entry["tp_regime"], ""],
                **(
                    {
                        "T_K": entry["expected_T_K"],
                        "T_error_K": f"≤ {_P2_KS_T_K}",
                        "beta": entry["expected_beta"],
                        "beta_error": f"≤ {_P2_KS_BETA}",
                        "component_conservation_mol_per_s": f"≤ {_P2_KS_CONSERVATION}",
                    }
                    if "expected_T_K" in entry
                    else {"T_in_answer": False, "V": 0.0}
                ),
            }
            for state_id, entry in REF["contract_kernel_states"].items()
        },
        "c_twice": "every case: 0 differences between two solves in one process; no float, and "
        "no float-shaped text, in any R0 string or cause record",
        "d_form_switches": {
            "DZ-12": "the item in attempt 0's signature, absent from attempt 1's, named in no "
            "record",
            "screen": "the screen reports the item at a dormant feed and none at a flowing one; "
            "the wall names it `U.port:from->to`",
            "conflicts": {
                case: [entry["expected"]["outcome"], entry["expected"]["message"]]
                for case, entry in REF["zero_flow_conflicts"].items()
            },
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B20"] = (
    "Every switch recorded, deterministically. (a) The `closure_route(…)` records of every "
    "contract case (SC-1…SC-4, NP-1…NP-3, NP-G; the contract test's cached solves) and of every "
    "DZ case (DZ-1…DZ-12, DZ-2C, solved as B22's identity solves them): none except NP-1's one "
    "`closure_route(U-PHF, band)` and the test's regression pins for NP-2 (one) and NP-G "
    "(none). (b) The contract's kernel of SC-1's PH-type valve outlet at KS-1…KS-3 (the test's "
    'construction): regime, record (`""`, `fallback(U-VLV, ph-band)`, `fallback(U-VLV, tp)`), '
    "temperature to 1e-6 K and vapour fraction to 1e-9 of `ref.contract_kernel_states`, each "
    "component conserved to 3.1e-8 mol/s, and the TP flash's answer. (c) Each of those cases "
    "solved twice in one process: the R0 projections, records and root fingerprints compared "
    "leaf by leaf (the count of differences recorded), and no float or float-shaped text in any "
    "R0 string (the declared inputs' identifiers and digests aside, as in B22), cause record or "
    "message. (d) DZ-12's dormancy "
    "item is in attempt 0's signature, absent from attempt 1's, named in no record; the screen "
    "reports DZ-6's pump item at a dormant feed and not at a flowing one, and the wall text "
    "names a switch `U.port:from->to` (a constructed function-level state, the dormancy test's "
    "construction); DZ-11 and DZ-2C close `SPECIFICATION_CONFLICT` with "
    "`zero_flow_conflict(row)` as registered."
)
MEASURES["B20"] = _b20


# -------------------------------------------------- B15-B18, B24-B30: zero flow and dormant outlets


#: Spec §13's EO allowances (T02 §6.4), as `ref.tolerances.coupled_allowances` states them.
_P3_ALLOWANCE = zero_flow_tests.ALLOWANCE
#: The state columns that are flows (`test_t05b_zero_flow`'s and `test_t05b_dormancy`'s rule).
_P3_FLOW_KINDS = ("n", "vap", "liq", "V", "L", "N")


def _p3_flows(state: Mapping[str, float]) -> dict[str, float]:
    return {
        column: value for column, value in state.items() if column.split(".")[1] in _P3_FLOW_KINDS
    }


def _p3_signatures(attempts: Sequence[Any]) -> list[list[list[str]]]:
    return [[list(entry) for entry in attempt.signature] for attempt in attempts]


def _p3_residuals(certificate: Any) -> dict[str, Any]:
    return {check.id: check for check in certificate.checks if check.category == "residual"}


def _p3_certificate_record(certificate: Any, dimension: int, ledger: Ledger, where: str) -> Any:
    """`VERIFIED`, `NO_RANK_LOSS_DETECTED` at the registered dimension; the verdict recorded."""
    regularity = certificate.regularity
    record = {
        "verification_status": certificate.verification_status,
        "regularity": None if regularity is None else regularity.status,
        "dimension": None if regularity is None else regularity.dimension,
        "failing": sorted(c.id for c in certificate.checks if c.result == "fail"),
    }
    ledger.equal(f"{where} verdict", record["verification_status"], "VERIFIED")
    ledger.equal(f"{where} regularity", record["regularity"], "NO_RANK_LOSS_DETECTED")
    ledger.equal(f"{where} regularity dimension", record["dimension"], dimension)
    return record


def _p3_labels_and_rows(
    certificate: Any, labels: Sequence[str], ledger: Ledger, where: str
) -> dict[str, Any]:
    """Each label check present with value `0.0` and passing, no other label check; every other
    (compiled) residual `== 0.0`."""
    residuals = _p3_residuals(certificate)
    present = [check_id for check_id in residuals if ":zero-flow-label" in check_id]
    ledger.equal(f"{where} label checks", present, list(labels))
    values = {
        check_id: [residuals[check_id].value, residuals[check_id].result] for check_id in present
    }
    for check_id in labels:
        check = residuals.get(check_id)
        ledger.equal(
            f"{where} {check_id}",
            None if check is None else (check.value, check.result),
            (0.0, "pass"),
        )
    compiled = {k: c.value for k, c in residuals.items() if ":zero-flow-label" not in k}
    nonzero = sorted(k for k, v in compiled.items() if v != 0.0)
    ledger.true(f"{where} compiled residuals present", bool(compiled))
    ledger.equal(f"{where} compiled residuals not exactly 0.0", nonzero, [])
    return {"label_checks": values, "compiled_residuals": len(compiled), "nonzero": nonzero}


def _p3_state_against(
    state: Mapping[str, float], registered: Mapping[str, str], ledger: Ledger, where: str
) -> dict[str, Any]:
    """`|x − ref| ≤ allowance` per column, §13's EO allowances by column kind; the worst ratio."""
    ratios: dict[str, float] = {}
    for column, value in registered.items():
        allowance = dormancy._allowance(column)
        found = ledger.within(f"{where} {column}", state.get(column), value, allowance)
        ratios[column] = found / allowance
    where_worst = max(ratios, key=lambda key: ratios[key])
    return {"columns": len(ratios), "worst_ratio": ratios[where_worst], "at": where_worst}


def _p3_projection(certificate: Any) -> Any:
    return certificate.transformations.get("projection")


@cache
def _p3_dz_root(case: str) -> tuple[Any, dict[str, Any], dict[str, float], Any]:
    """`(binding, document, x_final, certificate)` of a DZ root, as K04-F9's X03/X26 build it."""
    return f9_t05b._dz_root(case)


# ----------------------------------------------------------------------------- B15, B17


@cache
def _p3_b15_v1(name: str) -> tuple[Any, Any]:
    """B15's `T05-W13` half, as `test_t05_dormant_outlet` solves and certifies it."""
    case = dormant_outlet_test.CASES[name]
    solved = dormant_outlet_test._solve(case)
    return solved, dormant_outlet_test._certificate(case, solved)


def _p3_lifted_at_the_start(case: str, ledger: Ledger) -> dict[str, Any]:
    """B15/B17's v2 facts for one of DZ-1, DZ-2, DZ-4, DZ-5 (`test_t05b_zero_flow`'s solve)."""
    unit, outlets, has_label = zero_flow_tests.AT_THE_START[case]
    registered = zero_flow_tests.DORMANT[case]
    form = registered["zero_flow_form"]
    solved = zero_flow_tests._solved(case)
    run, region = solved.run, solved.region
    state = run.state
    ledger.equal(f"{case} outcome", run.outcome, "CONVERGED")
    ledger.equal(f"{case} Jacobian calls", run.counters.jacobian_calls, 0)
    iterations = [attempt.iterations for attempt in region.attempts]
    ledger.equal(f"{case} attempt iterations", iterations, [0])
    signatures = _p3_signatures(region.attempts)
    ledger.equal(f"{case} signatures", signatures, [[[unit, "ZERO_FLOW"]]])
    (context,) = region.contexts
    rows, columns = list(context.row_scales), list(context.column_scales)
    ledger.equal(f"{case} rows", sorted(map(zero_flow_tests._renamed, rows)), sorted(form["rows"]))
    ledger.equal(f"{case} free columns", sorted(columns), sorted(form["columns"]))
    pattern = context.jacobian_pattern or {}
    ledger.equal(f"{case} jacobian_pattern.rows", pattern.get("rows"), form["dimension"])
    ledger.equal(f"{case} jacobian_pattern.columns", pattern.get("columns"), form["dimension"])
    root = support.registered_state(registered["root"])
    differing = sorted(column for column in root if state[column] != root[column])
    ledger.equal(f"{case} registered root columns not exact", differing, [])
    flows = _p3_flows(state)
    ledger.true(f"{case} flows present", bool(flows))
    ledger.equal(f"{case} flows not 0.0", sorted(k for k, v in flows.items() if v != 0.0), [])
    labels = {f"{stream}.T": state[f"{stream}.T"] for stream in outlets}
    ledger.equal(f"{case} dormant outlet T", labels, _p3_dormant_outlet_t(case))
    duties = {k: v for k, v in state.items() if k.rsplit(".", 1)[-1] in ("Q", "W")}
    ledger.equal(f"{case} duties and work", duties, dict.fromkeys(duties, 0.0))
    fingerprint = region.root_fingerprint or {}
    ledger.equal(f"{case} branch_found", fingerprint.get("branch_found"), [[unit, "ZERO_FLOW"]])
    label_rows = [row for row in rows if ":zero-flow-label" in row]
    label_row = [registered["label"]["row"]] if has_label else []
    ledger.equal(f"{case} label rows in the attempt", label_rows, label_row)
    if has_label:
        ledger.equal(f"{case} label row last", rows[-1], label_row[0])
    certificate = solved.certificate
    labels_expected = [f"residual.{unit}:zero-flow-label"] if has_label else []
    return {
        "outcome": run.outcome,
        "jacobian_calls": run.counters.jacobian_calls,
        "iterations": iterations,
        "signatures": signatures,
        "rows": len(rows),
        "free_columns": len(columns),
        "jacobian_pattern_rows": pattern.get("rows"),
        "label_rows": label_rows,
        "last_row": rows[-1],
        "flows_checked": len(flows),
        "dormant_outlet_T": labels,
        "duties_and_work": duties,
        "branch_found": fingerprint.get("branch_found"),
        "certificate": _p3_certificate_record(certificate, form["dimension"], ledger, case),
        **_p3_labels_and_rows(certificate, labels_expected, ledger, case),
    }


def _p3_dormant_outlet_t(case: str) -> dict[str, float]:
    """Each dormant outlet's registered temperature: B15 states `330.0` for DZ-1 and DZ-2 (the
    feed's label); B17's cases carry their `ref` roots' (DZ-5's heater outlet is specified)."""
    _, outlets, _ = zero_flow_tests.AT_THE_START[case]
    root = support.registered_state(zero_flow_tests.DORMANT[case]["root"])
    if case in ("DZ-1", "DZ-2"):
        return {f"{stream}.T": 330.0 for stream in outlets}
    return {f"{stream}.T": root[f"{stream}.T"] for stream in outlets}


def _p3_expected_lifted(case: str) -> dict[str, Any]:
    unit, _, has_label = zero_flow_tests.AT_THE_START[case]
    form = zero_flow_tests.DORMANT[case]["zero_flow_form"]
    registered_label = zero_flow_tests.DORMANT[case]["label"]
    return {
        "outcome": "CONVERGED",
        "jacobian_calls": 0,
        "iterations": [0],
        "signatures": [[[unit, "ZERO_FLOW"]]],
        "rows_and_free_columns": f"ref.dormant_cases.{case}.zero_flow_form ({form['dimension']})",
        "jacobian_pattern_rows": form["dimension"],
        "label_rows": [registered_label["row"]] if registered_label else [],
        "last_row": registered_label["row"] if registered_label else "any compiled row",
        "root": f"ref.dormant_cases.{case}.root exactly; every flow == 0.0",
        "dormant_outlet_T": _p3_dormant_outlet_t(case),
        "duties_and_work": "every one == 0.0",
        "branch_found": [[unit, "ZERO_FLOW"]],
        "certificate": {
            "verification_status": "VERIFIED",
            "regularity": "NO_RANK_LOSS_DETECTED",
            "dimension": form["dimension"],
        },
        "label_checks": [f"residual.{unit}:zero-flow-label == 0.0, pass"] if has_label else [],
        "nonzero": [],
    }


def _b15() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    value: dict[str, Any] = {
        case: _p3_lifted_at_the_start(case, ledger) for case in ("DZ-1", "DZ-2")
    }
    expected: dict[str, Any] = {case: _p3_expected_lifted(case) for case in ("DZ-1", "DZ-2")}
    # The `T05-W13` half (`test_t05_dormant_outlet`): the TWO_PHASE form at iteration 0, and the
    # same verdict (§9.3) and `branch_found` as v2.
    for name, case in (("valve", "DZ-1"), ("ph_flash", "DZ-2")):
        unit = dormant_outlet_test.CASES[name].unit
        solved, certificate = _p3_b15_v1(name)
        (step,) = solved.run.steps
        detail = step.detail
        where = f"{case} v1"
        record = {
            "outcome": ledger.equal(f"{where} outcome", solved.run.outcome, "CONVERGED"),
            "jacobian_calls": ledger.equal(
                f"{where} Jacobian calls", solved.run.counters.jacobian_calls, 0
            ),
            "iterations": ledger.equal(
                f"{where} iterations", [a.iterations for a in detail.attempts], [0]
            ),
            "signatures": ledger.equal(
                f"{where} signatures",
                _p3_signatures(detail.attempts),
                [[[unit, "TWO_PHASE"]]],
            ),
            "branch_found": ledger.equal(
                f"{where} branch_found",
                (detail.root_fingerprint or {}).get("branch_found"),
                value[case]["branch_found"],
            ),
            "certificate": _p3_certificate_record(
                certificate, value[case]["certificate"]["dimension"], ledger, where
            ),
        }
        ledger.equal(
            f"{where} verdict equals v2's",
            certificate.verification_status,
            value[case]["certificate"]["verification_status"],
        )
        value[f"{case} (T05-W13)"] = record
        expected[f"{case} (T05-W13)"] = {
            "outcome": "CONVERGED",
            "jacobian_calls": 0,
            "iterations": [0],
            "signatures": [[[unit, "TWO_PHASE"]]],
            "branch_found": [[unit, "ZERO_FLOW"]],
            "certificate": "as under T05b-v2: VERIFIED, NO_RANK_LOSS_DETECTED, dimension 10",
        }
    value["departures"] = ledger.departures
    return ledger.ok, value, expected


def _b17() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    value: dict[str, Any] = {
        case: _p3_lifted_at_the_start(case, ledger) for case in ("DZ-4", "DZ-5")
    }
    expected: dict[str, Any] = {case: _p3_expected_lifted(case) for case in ("DZ-4", "DZ-5")}
    ledger.equal("DZ-5 label rows in the attempt", value["DZ-5"]["label_rows"], [])
    ledger.equal("DZ-5 label checks", value["DZ-5"]["label_checks"], {})
    value["departures"] = ledger.departures
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------- B16, B26


def _p3_moving_label(
    case: str,
    result: Any,
    certificate: Any,
    item: tuple[str, str],
    phf1_t: str,
    ledger: Ledger,
    item_last: bool,
) -> dict[str, Any]:
    """B16/B26's shared facts: `CONVERGED`; the item in every attempt; the label back on its
    source to 1e-9 K; the source on PHF-1's `T` to 1e-5 K; the dormant flows exactly 0.0;
    `VERIFIED` at the verifier's projection with every fresh-flash value `≤ 1e-3 τ` (K04-F9
    X07/X08, which amend B16/B26)."""
    state = result.state
    ledger.equal(f"{case} outcome", result.outcome, "CONVERGED")
    signatures = _p3_signatures(result.attempts)
    if item_last:
        held = all(signature[-1] == list(item) for signature in signatures)
    else:
        held = all(list(item) in signature for signature in signatures)
    ledger.true(f"{case} {item[0]} {item[1]} in every attempt", held and bool(signatures))
    label = abs(state["S5.T"] - state["S4.T"])
    ledger.at_most(f"{case} |S5.T − S4.T|", label, 1e-9)
    source = ledger.within(f"{case} S4.T vs PHF-1's T", state["S4.T"], phf1_t, _P3_ALLOWANCE["T"])
    dormant = {
        f"S{k}.{kind}.{c}": state[f"S{k}.{kind}.{c}"]
        for k, kinds in ((4, ("n",)), (5, ("n", "vap", "liq")))
        for kind in kinds
        for c in "ABC"
        if f"S{k}.{kind}.{c}" in state
    }
    ledger.equal(f"{case} dormant flows", dormant, dict.fromkeys(dormant, 0.0))
    ledger.equal(f"{case} verdict", certificate.verification_status, "VERIFIED")
    projection = _p3_projection(certificate) or {}
    ledger.equal(f"{case} judged at", projection.get("judged_at"), "projection")
    ratios = support.fresh_flash_ratios(certificate.checks)
    worst = max(ratios.items(), key=lambda entry: entry[1]) if ratios else (None, None)
    ledger.true(f"{case} fresh-flash checks evaluated", bool(ratios))
    ledger.at_most(f"{case} worst fresh-flash |value|/τ", worst[1], 1e-3)
    return {
        "outcome": result.outcome,
        "attempts": len(signatures),
        "signatures": signatures,
        "abs_S5T_minus_S4T_K": label,
        "S4T_error_vs_PHF1_K": source,
        "dormant_flows_checked": len(dormant),
        "verification_status": certificate.verification_status,
        "judged_at": projection.get("judged_at"),
        "fresh_flash_worst": {"ratio": worst[1], "where": worst[0], "count": len(ratios)},
        "failing": sorted(c.id for c in certificate.checks if c.result == "fail"),
    }


def _b16() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    _, result = zero_flow_tests._dz3()
    _, _, _, certificate = _p3_dz_root("DZ-3")
    value = _p3_moving_label(
        "DZ-3",
        result,
        certificate,
        ("U-VLV", "ZERO_FLOW"),
        zero_flow_tests.DORMANT["DZ-3"]["root"]["S4.T"],
        ledger,
        item_last=False,
    )
    _, v1 = zero_flow_tests._dz3("v1")
    pinned = zero_flow_tests.V1_FROM_THE_START["DZ-3"]
    ledger.true("DZ-3 under T05-W13 not CONVERGED", v1.outcome != "CONVERGED")
    value["T05-W13_outcome"] = ledger.equal("DZ-3 under T05-W13 (regression)", v1.outcome, pinned)
    value["departures"] = ledger.departures
    expected = {
        "outcome": "CONVERGED",
        "signatures": "U-VLV ZERO_FLOW in every attempt",
        "abs_S5T_minus_S4T_K": "≤ 1e-9",
        "S4T_error_vs_PHF1_K": "≤ 1e-5 (ref.dormant_cases.DZ-3.root.S4.T)",
        "dormant_flows_checked": "every S4, S5 flow == 0.0",
        "verification_status": "VERIFIED",
        "judged_at": "projection (K04-F9 X07)",
        "fresh_flash_worst": "≤ 1e-3 of its tolerance (K04-F9 X07)",
        "T05-W13_outcome": f"not CONVERGED; regression {pinned}",
    }
    return ledger.ok, value, expected


def _b26() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    result, trace = dormancy._dz10()
    _, _, _, certificate = _p3_dz_root("DZ-10")
    value = _p3_moving_label(
        "DZ-10",
        result,
        certificate,
        ("U-PUMP.outlet", "ZERO_FLOW"),
        dormancy.DZ10["phf1_T_K"],
        ledger,
        item_last=True,
    )
    causes = [attempt.reason for attempt in result.attempts] + [e.message for e in trace.events]
    naming = [cause for cause in causes if "U-PUMP.outlet" in cause]
    value["cause_strings_checked"] = len(causes)
    value["cause_strings_naming_the_item"] = ledger.equal(
        "DZ-10 cause strings naming U-PUMP.outlet", naming, []
    )
    s5 = {
        k: v
        for k, v in result.state.items()
        if k.startswith("S5.") and k.split(".")[1] in _P3_FLOW_KINDS
    }
    ledger.equal("DZ-10 S5 flows", s5, dict.fromkeys(s5, 0.0))
    value["S5_flows"] = s5
    v1, _ = dormancy._dz10("v1")
    ledger.true("DZ-10 under T05-W13 not CONVERGED", v1.outcome != "CONVERGED")
    value["T05-W13_outcome"] = ledger.equal(
        "DZ-10 under T05-W13 (regression)", v1.outcome, dormancy.DZ10_V1
    )
    value["departures"] = ledger.departures
    expected = {
        "outcome": "CONVERGED",
        "signatures": "every attempt's ends with [U-PUMP.outlet, ZERO_FLOW]",
        "cause_strings_naming_the_item": [],
        "S5_flows": "every one == 0.0",
        "abs_S5T_minus_S4T_K": "≤ 1e-9",
        "S4T_error_vs_PHF1_K": "≤ 1e-5 (ref.dormant_non_lifted_cases.DZ-10.phf1_T_K)",
        "verification_status": "VERIFIED",
        "judged_at": "projection (K04-F9 X08)",
        "fresh_flash_worst": "≤ 1e-3 of its tolerance (K04-F9 X08)",
        "T05-W13_outcome": f"not CONVERGED; regression {dormancy.DZ10_V1}",
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- B18

#: Spec §12.6 / §13: an injection fails by at least `10³ τ` (INJ-B2p stays `10×` inside).
_P3_DETECTION = verifier_tests.DETECTION_FACTOR


@cache
def _p3_judged() -> dict[str, Any]:
    """`test_t05b_verifier`'s module fixture: SC-1's v2 claim, each injected state judged
    against it (SC-1, INJ-B1, PRJ-B2, INJ-B2p, INJ-B2′)."""
    judged: dict[str, Any] = verifier_tests.judged.__wrapped__()
    return judged


def _p3_verify(solved: Any, state: Mapping[str, float]) -> Any:
    """`verify_revision` of an injected `state` against a solved case's own claim and plan (K04
    §9's injection route, as the gate's injection tests call it)."""
    from openflowsheet.verify.certificate import verify_revision

    return verify_revision(
        solved.binding,
        solved.document,
        solved.run,
        state=dict(state),
        solve_plan=solved.plan.steps[-1].solve_plan,
    )


def _p3_registered(
    check: Any,
    expected: str,
    ledger: Ledger,
    where: str,
    factor: float | None = None,
    result: str | None = None,
) -> dict[str, Any]:
    """A check's value within its own `τ_kind` of the registered closed form; when `factor` is
    given, also `≥ factor · τ` from its threshold; when `result` is given, that result."""
    if check is None:
        ledger.true(f"{where} present", False)
        return {"value": None}
    error = ledger.within(where, check.value, expected, check.tolerance)
    record = {
        "value": check.value,
        "result": check.result,
        "tolerance": check.tolerance,
        "error": error,
    }
    if factor is not None:
        ratio = abs(check.value) / check.tolerance
        record["over_tolerance"] = ratio
        ledger.true(f"{where} ≥ {factor:g} τ ({ratio:.3g} τ)", ratio >= factor)
    if result is not None:
        ledger.equal(f"{where} result", check.result, result)
    return record


def _p3_degenerate(by_id: Mapping[str, Any], degeneracy: str, ledger: Ledger, where: str) -> Any:
    """The degenerate judgement in force: `.saturation` passes at the registered `δ` (to 1e-12 K,
    as the gate reads it) and the split's independent check is `not_applicable`
    (`temperature_degenerate`)."""
    saturation = by_id.get("phase_admissibility.U-VLV.S2.saturation")
    split = by_id.get("independent_split.U-VLV.S2")
    record = {
        "saturation": None if saturation is None else [saturation.result, saturation.value],
        "independent_split": None if split is None else [split.result, split.reason],
    }
    ledger.equal(f"{where} .saturation result", saturation and saturation.result, "pass")
    if saturation is not None and saturation.value is not None:
        found = support.error(saturation.value, degeneracy)
        record["saturation_error_K"] = found
        ledger.at_most(f"{where} .saturation vs δ = {degeneracy} K", found, 1e-12)
    ledger.equal(
        f"{where} independent_split.U-VLV.S2",
        record["independent_split"],
        ["not_applicable", "temperature_degenerate"],
    )
    return record


def _p3_judged_at(certificate: Any) -> Any:
    return (_p3_projection(certificate) or {}).get("judged_at")


def _b18() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    judged = _p3_judged()
    injections = verifier_tests.INJECTIONS
    value: dict[str, Any] = {}

    # INJ-B1: V = 0 at T_sat — FAILED, the degenerate judgement in force, exactly three failing
    # checks, each 2 016 W as inlet minus outlet (spec §12.6 as ruled).
    entry = injections["INJ-B1"]
    certificate = judged["INJ-B1"]
    by_id = {check.id: check for check in certificate.checks}
    registered_failing = [
        "energy_balance.U-VLV",
        "energy_balance.envelope",
        "residual.U-VLV:VLV-energy",
    ]
    value["INJ-B1"] = {
        "verification_status": ledger.equal(
            "INJ-B1 verdict", certificate.verification_status, "FAILED"
        ),
        "false_success_detected": ledger.equal(
            "INJ-B1 false_success_detected", certificate.false_success_detected, True
        ),
        "judged_at": _p3_judged_at(certificate),
        "degenerate_judgement": _p3_degenerate(by_id, entry["degeneracy_K"], ledger, "INJ-B1"),
        "failing": ledger.equal(
            "INJ-B1 failing set",
            sorted(c.id for c in certificate.checks if c.result == "fail"),
            registered_failing,
        ),
        **{
            name: _p3_registered(
                by_id.get(name), entry[key], ledger, f"INJ-B1 {name}", _P3_DETECTION, "fail"
            )
            for name, key in (
                ("energy_balance.U-VLV", "energy_balance_U-VLV_W"),
                ("residual.U-VLV:VLV-energy", "compiled_energy_row_W"),
                ("energy_balance.envelope", "energy_balance_envelope_in_minus_out_W"),
            )
        },
    }

    # INJ-B2's state, re-registered as PRJ-B2 (K04-F9 X12): VERIFIED, judged at the projection,
    # every compiled residual row passing; T05b's INJ-B2 values still hold at x_final, judged by
    # the fresh flash (the table there, unprojected; K04-F9 §10.5).
    entry = injections["INJ-B2"]
    certificate = judged["PRJ-B2"]
    certified = {check.id: check for check in certificate.checks}
    at_x_final = verifier_tests._at_x_final("PRJ-B2")
    value["PRJ-B2 (INJ-B2's state; K04-F9 X12)"] = {
        "verification_status": ledger.equal(
            "PRJ-B2 verdict", certificate.verification_status, "VERIFIED"
        ),
        "judged_at": ledger.equal("PRJ-B2 judged at", _p3_judged_at(certificate), "projection"),
        "compiled_residuals_not_passing": ledger.equal(
            "PRJ-B2 compiled residuals not passing",
            sorted(k for k, c in _p3_residuals(certificate).items() if c.result != "pass"),
            [],
        ),
        **{
            name: _p3_registered(certified.get(name), entry[key], ledger, f"INJ-B2 {name}")
            for name, key in (
                ("residual.U-VLV:VLV-energy", "compiled_energy_row_W"),
                ("residual.U-VLV:VLV-equilibrium:B", "compiled_equilibrium_row_B"),
            )
        },
        "at_x_final": {
            "saturation_check_present": ledger.equal(
                "INJ-B2 at x_final: .saturation present (degenerate)",
                "phase_admissibility.U-VLV.S2.saturation" in at_x_final,
                False,
            ),
            **{
                name: _p3_registered(
                    at_x_final.get(name),
                    entry[key],
                    ledger,
                    f"INJ-B2 at x_final {name}",
                    _P3_DETECTION,
                    "fail",
                )
                for name, key in (
                    ("independent_split.U-VLV.S2.total", "independent_split_total_mol_per_s"),
                    ("energy_balance.U-VLV", "energy_balance_U-VLV_W"),
                )
            },
        },
    }

    # INJ-B2′ (K04-F9 X14) takes INJ-B2's place: FAILED, judged at x_final by the fresh flash.
    entry = F9_REF["closed_form"]["injections"]["INJ-B2-prime"]
    certificate = judged["INJ-B2′"]
    by_id = {check.id: check for check in certificate.checks}
    value["INJ-B2′ (K04-F9 X14)"] = {
        "verification_status": ledger.equal(
            "INJ-B2′ verdict", certificate.verification_status, "FAILED"
        ),
        "false_success_detected": ledger.equal(
            "INJ-B2′ false_success_detected", certificate.false_success_detected, True
        ),
        "judged_at": ledger.equal("INJ-B2′ judged at", _p3_judged_at(certificate), "final_state"),
        "failing": sorted(c.id for c in certificate.checks if c.result == "fail"),
        **{
            name: _p3_registered(
                by_id.get(name), entry[key], ledger, f"INJ-B2′ {name}", _P3_DETECTION, "fail"
            )
            for name, key in (
                ("independent_split.U-VLV.S2.total", "independent_split_total_mol_per_s"),
                ("energy_balance.U-VLV", "energy_balance_U-VLV_W"),
            )
        },
    }

    # INJ-B2p (K04-F9 X13): VERIFIED, judged at the projection; at x_final T05b's registered
    # degenerate judgement and −1e-4 W, 10× inside τ_E.
    entry = injections["INJ-B2p"]
    certificate = judged["INJ-B2p"]
    at_x_final = verifier_tests._at_x_final("INJ-B2p")
    unprojected = at_x_final.get("energy_balance.U-VLV")
    balance = _p3_registered(
        unprojected,
        entry["energy_balance_U-VLV_W"],
        ledger,
        "INJ-B2p at x_final energy_balance.U-VLV",
        result="pass",
    )
    if unprojected is not None:
        # "10× inside", as `test_b18_inj_b2p_inside_the_window_balances` reads it: −1e-4 W
        # against τ_E = 1e-3 W sits on the boundary up to rounding, hence its 1e-6 relative slack.
        balance["ten_times_inside"] = ledger.true(
            "INJ-B2p at x_final 10× inside τ_E",
            abs(unprojected.value) * 10.0 <= unprojected.tolerance * (1.0 + 1e-6),
        )
    value["INJ-B2p (K04-F9 X13)"] = {
        "verification_status": ledger.equal(
            "INJ-B2p verdict", certificate.verification_status, "VERIFIED"
        ),
        "judged_at": ledger.equal("INJ-B2p judged at", _p3_judged_at(certificate), "projection"),
        "at_x_final": {
            "degenerate_judgement": _p3_degenerate(
                at_x_final, entry["degeneracy_K"], ledger, "INJ-B2p at x_final"
            ),
            "energy_balance.U-VLV": balance,
        },
    }

    # INJ-B3: DZ-1's root with S2.T = 331 K, judged against DZ-1's v2 claim (the gate's build).
    state = dict(support.registered_state(zero_flow_tests.DORMANT["DZ-1"]["root"]))
    state["S2.T"] = 331.0
    certificate = _p3_verify(zero_flow_tests._solved("DZ-1"), state)
    by_id = {check.id: check for check in certificate.checks}
    value["INJ-B3"] = {
        "verification_status": ledger.equal(
            "INJ-B3 verdict", certificate.verification_status, "FAILED"
        ),
        "failing": sorted(c.id for c in certificate.checks if c.result == "fail"),
        "residual.U-VLV:zero-flow-label": _p3_registered(
            by_id.get("residual.U-VLV:zero-flow-label"),
            REF["injections"]["INJ-B3"]["label_residual_K"],
            ledger,
            "INJ-B3 residual.U-VLV:zero-flow-label",
            _P3_DETECTION,
            "fail",
        ),
    }

    # T05's INJ-T1…T4 (A22), as T05's own generator measures them.
    a22_ok, a22_value, _ = t05m._a22(t05m.reference(t05m.REFERENCE))
    value["T05 A22 (INJ-T1…T4)"] = {"condition": a22_ok, "departures": a22_value["departures"]}
    ledger.true("T05 A22 (INJ-T1…T4) unchanged", bool(a22_ok))
    value["departures"] = ledger.departures
    expected = {
        "INJ-B1": {
            "verification_status": "FAILED",
            "false_success_detected": True,
            "degenerate_judgement": ".saturation passes at δ = 0 K; the split's independent "
            "check not_applicable (temperature_degenerate)",
            "failing": registered_failing,
            "each failing value": "+2 016 W within its τ_kind (ref.injections.INJ-B1), ≥ 10³ τ",
        },
        "PRJ-B2 (INJ-B2's state; K04-F9 X12)": {
            "verification_status": "VERIFIED",
            "judged_at": "projection",
            "compiled_residuals_not_passing": [],
            "compiled rows": "ref.injections.INJ-B2's compiled energy and equilibrium-B rows "
            "within τ_kind",
            "at_x_final": "not degenerate (δ = 2e-6 K), judged by the fresh flash: "
            "independent_split total −1.9328 mol/s, energy_balance.U-VLV −57 984.0004 W, each "
            "failing within τ_kind, ≥ 10³ τ",
        },
        "INJ-B2′ (K04-F9 X14)": {
            "verification_status": "FAILED",
            "false_success_detected": True,
            "judged_at": "final_state",
            "failing values": "k04f9 ref closed_form.injections.INJ-B2-prime within τ_kind, "
            "≥ 10³ τ",
        },
        "INJ-B2p (K04-F9 X13)": {
            "verification_status": "VERIFIED",
            "judged_at": "projection",
            "at_x_final": "degenerate (δ = 5e-7 K); energy_balance.U-VLV −1e-4 W within τ_E, "
            "passing, 10× inside",
        },
        "INJ-B3": {
            "verification_status": "FAILED",
            "residual.U-VLV:zero-flow-label": "1 K within τ_T (ref.injections.INJ-B3), failing, "
            "≥ 10³ τ",
        },
        "T05 A22 (INJ-T1…T4)": {"condition": True, "departures": []},
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------- B24, B25


def _p3_non_lifted_at_the_start(case: str, ledger: Ledger) -> dict[str, Any]:
    """B24/B25's v2 facts for one of DZ-6…DZ-9 (`test_t05b_dormancy`'s solve), and its
    `T05-W13` half (§7.10: the declared form at iteration 0, the same verdict)."""
    item, exact = dormancy.AT_THE_START_V2[case]
    registered = dormancy.CASES[case]
    form = registered["zero_flow_form"]
    labels, dimension = dormancy.AT_THE_START[case]
    solved = dormancy._solved(case, "v2")
    run, region = solved.run, solved.region
    state = run.state
    ledger.equal(f"{case} outcome", run.outcome, "CONVERGED")
    ledger.equal(f"{case} Jacobian calls", run.counters.jacobian_calls, 0)
    iterations = [attempt.iterations for attempt in region.attempts]
    ledger.equal(f"{case} iterations", iterations, [0])
    signatures = _p3_signatures(region.attempts)
    ledger.equal(f"{case} signatures", signatures, [[[item, "ZERO_FLOW"]]])
    step = solved.plan.steps[-1]
    signature_units = None if step.region is None else list(step.region.signature_units)
    ledger.equal(f"{case} plan signature_units", signature_units, [])
    fingerprint = region.root_fingerprint or {}
    ledger.equal(f"{case} branch_found", fingerprint.get("branch_found"), [])
    (context,) = region.contexts
    rows = list(context.row_scales)
    ledger.equal(
        f"{case} rows (as sets)",
        sorted(map(support.registered_name, rows)),
        sorted(form["rows"]),
    )
    ledger.equal(
        f"{case} free columns (as sets)", sorted(context.column_scales), sorted(form["columns"])
    )
    pattern = context.jacobian_pattern or {}
    ledger.equal(f"{case} jacobian_pattern.rows", pattern.get("rows"), form["dimension"])
    eliminated = [row.row_id for row in step.solve_plan.eliminated_rows]
    ledger.equal(f"{case} plan eliminated_rows", eliminated, registered["eliminated_rows"])
    root = support.registered_state(registered["root"])
    differing = sorted(column for column in root if state[column] != root[column])
    ledger.equal(f"{case} registered root columns not exact", differing, [])
    exact_found = {column: state[column] for column in exact}
    ledger.equal(f"{case} outlet labels, duty, work", exact_found, exact)
    flows = _p3_flows(state)
    nonzero_flows = sorted(k for k, v in flows.items() if v != 0.0)
    if case != "DZ-7":  # DZ-7's cold side flows; its registered root pins every column.
        ledger.equal(f"{case} flows not 0.0", nonzero_flows, [])
    certificate = solved.certificate
    record: dict[str, Any] = {
        "outcome": run.outcome,
        "jacobian_calls": run.counters.jacobian_calls,
        "iterations": iterations,
        "signatures": signatures,
        "signature_units": signature_units,
        "branch_found": fingerprint.get("branch_found"),
        "rows": len(rows),
        "label_row_last": rows[-1],
        "jacobian_pattern_rows": pattern.get("rows"),
        "eliminated_rows": eliminated,
        "root_columns_exact": len(root) - len(differing),
        "exact": exact_found,
        "flows_checked": len(flows),
        "nonzero_flows": nonzero_flows,
        "certificate": _p3_certificate_record(certificate, dimension, ledger, case),
        **_p3_labels_and_rows(certificate, labels, ledger, case),
    }
    (swapped,) = registered["swapped_rows"]
    ledger.equal(f"{case} label row last", rows[-1], labels[0].removeprefix("residual."))
    ledger.equal(f"{case} swapped row not in the attempt", swapped in rows, False)
    v1 = dormancy._solved(case, "v1")
    where = f"{case} v1"
    record["T05-W13"] = {
        "outcome": ledger.equal(f"{where} outcome", v1.run.outcome, "CONVERGED"),
        "jacobian_calls": ledger.equal(
            f"{where} Jacobian calls", v1.run.counters.jacobian_calls, 0
        ),
        "attempts": ledger.equal(
            f"{where} (iterations, signature)",
            [[a.iterations, _p3_signatures([a])[0]] for a in v1.region.attempts],
            [[0, []]],
        ),
        "certificate": _p3_certificate_record(v1.certificate, dimension, ledger, where),
    }
    return record


def _p3_expected_non_lifted(case: str) -> dict[str, Any]:
    item, exact = dormancy.AT_THE_START_V2[case]
    registered = dormancy.CASES[case]
    labels, dimension = dormancy.AT_THE_START[case]
    certificate = {
        "verification_status": "VERIFIED",
        "regularity": "NO_RANK_LOSS_DETECTED",
        "dimension": dimension,
    }
    return {
        "outcome": "CONVERGED",
        "jacobian_calls": 0,
        "iterations": [0],
        "signatures": [[[item, "ZERO_FLOW"]]],
        "signature_units": [],
        "branch_found": [],
        "rows": f"ref.dormant_non_lifted_cases.{case}.zero_flow_form's, as sets; the swapped "
        f"{registered['swapped_rows'][0]} out",
        "label_row_last": labels[0].removeprefix("residual."),
        "jacobian_pattern_rows": registered["zero_flow_form"]["dimension"],
        "eliminated_rows": registered["eliminated_rows"],
        "root": f"ref.dormant_non_lifted_cases.{case}.root exactly",
        "exact": exact,
        "nonzero_flows": "none" if case != "DZ-7" else "the cold side's (S3, S4), as its root",
        "certificate": certificate,
        "label_checks": [f"{label} == 0.0, pass" for label in labels],
        "nonzero": [],
        "T05-W13": {
            "outcome": "CONVERGED",
            "jacobian_calls": 0,
            "attempts": [[0, []]],
            "certificate": certificate,
        },
    }


@cache
def _p3_dz9_mixer_first() -> Any:
    return dormancy._solve(support.dz9(mixer_first=True), support.POLICY_V2)


def _b24() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    value: dict[str, Any] = {
        case: _p3_non_lifted_at_the_start(case, ledger) for case in ("DZ-6", "DZ-9")
    }
    expected: dict[str, Any] = {case: _p3_expected_non_lifted(case) for case in ("DZ-6", "DZ-9")}
    # Q-S4 (1): DZ-9 declared mixer first — the other redundant pressure row out (regression).
    solved = _p3_dz9_mixer_first()
    region, step = solved.region, solved.plan.steps[-1]
    registered = dormancy.CASES["DZ-9"]
    eliminated = [support.registered_name(row.row_id) for row in step.solve_plan.eliminated_rows]
    form = {*registered["zero_flow_form"]["rows"], *registered["eliminated_rows"]}
    (context,) = region.contexts
    rows = sorted(map(support.registered_name, context.row_scales))
    state = solved.run.state
    labels, dimension = dormancy.AT_THE_START["DZ-9"]
    where = "DZ-9 mixer first"
    value["DZ-9 (mixer first)"] = {
        "first_instance": ledger.equal(
            f"{where}: first instance", solved.document["instances"][0]["id"], "U-MIX"
        ),
        "outcome": ledger.equal(f"{where} outcome", solved.run.outcome, "CONVERGED"),
        "attempts": ledger.equal(
            f"{where} (iterations, signature)",
            [[a.iterations, _p3_signatures([a])[0]] for a in region.attempts],
            [[0, [["U-MIX.outlet", "ZERO_FLOW"]]]],
        ),
        "eliminated_rows": ledger.equal(
            f"{where} eliminated_rows (regression)", eliminated, ["U-FEED2:FEED-P"]
        ),
        "rows_are_the_form_minus_eliminated": ledger.true(
            f"{where} rows", rows == sorted(form - set(eliminated))
        ),
        "jacobian_pattern_rows": ledger.equal(
            f"{where} jacobian_pattern.rows",
            (context.jacobian_pattern or {}).get("rows"),
            registered["zero_flow_form"]["dimension"],
        ),
        "S3.T": ledger.equal(f"{where} S3.T", state["S3.T"], 330.0),
        "nonzero_flows": ledger.equal(
            f"{where} flows not 0.0",
            sorted(k for k, v in _p3_flows(state).items() if v != 0.0),
            [],
        ),
        "certificate": _p3_certificate_record(solved.certificate, dimension, ledger, where),
        **_p3_labels_and_rows(solved.certificate, labels, ledger, where),
    }
    expected["DZ-9 (mixer first)"] = {
        "first_instance": "U-MIX",
        "outcome": "CONVERGED",
        "attempts": [[0, [["U-MIX.outlet", "ZERO_FLOW"]]]],
        "eliminated_rows": ["U-FEED2:FEED-P"],
        "rows_are_the_form_minus_eliminated": True,
        "jacobian_pattern_rows": 15,
        "S3.T": 330.0,
        "nonzero_flows": [],
        "certificate": {
            "verification_status": "VERIFIED",
            "regularity": "NO_RANK_LOSS_DETECTED",
            "dimension": 15,
        },
        "label_checks": [f"{label} == 0.0, pass" for label in labels],
        "nonzero": [],
    }
    value["departures"] = ledger.departures
    return ledger.ok, value, expected


def _b25() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    value: dict[str, Any] = {
        case: _p3_non_lifted_at_the_start(case, ledger) for case in ("DZ-7", "DZ-8")
    }
    expected: dict[str, Any] = {case: _p3_expected_non_lifted(case) for case in ("DZ-7", "DZ-8")}
    for case in ("DZ-7", "DZ-8"):
        certificate = dormancy._solved(case, "v2").certificate
        by_id = {check.id: check for check in certificate.checks}
        terminal = {
            end: [by_id[f"bounds_and_domain.U-HX.{end}"].result]
            + [by_id[f"bounds_and_domain.U-HX.{end}"].reason]
            for end in ("hot_end", "cold_end")
        }
        ledger.equal(
            f"{case} terminal checks",
            terminal,
            dict.fromkeys(terminal, ["not_applicable", "ZERO_FLOW"]),
        )
        heat_flow = by_id["bounds_and_domain.U-HX.heat_flow"].result
        ledger.equal(f"{case} heat_flow", heat_flow, "pass")
        value[case]["terminal_checks"] = terminal
        value[case]["heat_flow"] = heat_flow
        expected[case]["terminal_checks"] = dict.fromkeys(terminal, ["not_applicable", "ZERO_FLOW"])
        expected[case]["heat_flow"] = "pass"
    # DZ-8 swaps the cold side only: no hot item, no hot label row or check.
    solved = dormancy._solved("DZ-8", "v2")
    (context,) = solved.region.contexts
    ids = {check.id for check in solved.certificate.checks}
    value["DZ-8"]["hot_label_row"] = ledger.equal(
        "DZ-8 hot label row", "U-HX:zero-flow-label:hot" in context.row_scales, False
    )
    value["DZ-8"]["hot_label_check"] = ledger.equal(
        "DZ-8 hot label check", "residual.U-HX:zero-flow-label:hot" in ids, False
    )
    expected["DZ-8"]["hot_label_row"] = False
    expected["DZ-8"]["hot_label_check"] = False
    value["departures"] = ledger.departures
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- B27


def _b27() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    registered = dormancy.DZ12
    result, trace = dormancy._dz12()
    first, second = result.attempts[0], result.attempts[-1]
    rows0, rows1 = result.contexts[0].row_scales, result.contexts[-1].row_scales
    opened = [event.message for event in trace.events if event.kind == "attempt_opened"]
    causes = [attempt.reason for attempt in result.attempts] + [e.message for e in trace.events]
    _, _, state, certificate = _p3_dz_root("DZ-12")
    v1, _ = dormancy._dz12("v1")
    attempt0, attempt1 = registered["attempt0"], registered["attempt1"]
    value = {
        "outcome": ledger.equal("DZ-12 outcome", result.outcome, "CONVERGED"),
        "attempts": ledger.equal("DZ-12 attempts", len(result.attempts), 2),
        "attempt0": {
            "signature": ledger.equal(
                "attempt 0 signature", _p3_signatures([first])[0], attempt0["signature"]
            ),
            "core": ledger.equal(
                "attempt 0 core (outcome, iterations)",
                [first.solver_outcome, first.iterations],
                ["CONVERGED", 0],
            ),
            "jacobian_pattern_rows": ledger.equal(
                "attempt 0 jacobian_pattern.rows",
                (result.contexts[0].jacobian_pattern or {}).get("rows"),
                attempt0["form"]["dimension"],
            ),
            "includes U-HX:zero-flow-label:hot": ledger.equal(
                "attempt 0 includes U-HX:zero-flow-label:hot",
                "U-HX:zero-flow-label:hot" in rows0,
                True,
            ),
            "includes U-HX:HX-energy-hot": ledger.equal(
                "attempt 0 includes U-HX:HX-energy-hot", "U-HX:HX-energy-hot" in rows0, False
            ),
        },
        "attempt1": {
            "attempt_opened": ledger.equal(
                "attempt_opened messages", opened, ["initial", attempt1["opening_message"]]
            ),
            "fallback_items": ledger.equal(
                "attempt_opened fallback items",
                [message for message in opened if "fallback(" in message],
                [],
            ),
            "signature": ledger.equal(
                "attempt 1 signature", _p3_signatures([second])[0], attempt1["signature"]
            ),
            "jacobian_pattern_rows": ledger.equal(
                "attempt 1 jacobian_pattern.rows",
                (result.contexts[-1].jacobian_pattern or {}).get("rows"),
                attempt1["opening_with_outlet_reset"]["dimension"],
            ),
            "includes U-HX:HX-energy-hot": ledger.equal(
                "attempt 1 includes U-HX:HX-energy-hot", "U-HX:HX-energy-hot" in rows1, True
            ),
            "core_outcome": ledger.equal(
                "attempt 1 core outcome", second.solver_outcome, "CONVERGED"
            ),
            "iterations": ledger.equal(
                "attempt 1 iterations (regression)",
                second.iterations,
                dormancy.DZ12_ATTEMPT1_ITERATIONS,
            ),
        },
        "cause_strings_checked": len(causes),
        "cause_strings_naming_an_item": ledger.equal(
            "cause strings naming U-HX.hot_outlet",
            [cause for cause in causes if "U-HX.hot_outlet" in cause],
            [],
        ),
        "root": _p3_state_against(state, registered["root"], ledger, "DZ-12 root"),
        "certificate": _p3_certificate_record(
            certificate, registered["zero_flow_form"]["dimension"], ledger, "DZ-12"
        ),
        "T05-W13_outcome": ledger.equal(
            "DZ-12 under T05-W13 (regression)", v1.outcome, dormancy.DZ12_V1
        ),
    }
    value["departures"] = ledger.departures
    expected = {
        "outcome": "CONVERGED",
        "attempts": 2,
        "attempt0": {
            "signature": attempt0["signature"],
            "core": ["CONVERGED", 0],
            "jacobian_pattern_rows": attempt0["form"]["dimension"],
            "includes U-HX:zero-flow-label:hot": True,
            "includes U-HX:HX-energy-hot": False,
        },
        "attempt1": {
            "attempt_opened": ["initial", attempt1["opening_message"]],
            "fallback_items": [],
            "signature": attempt1["signature"],
            "jacobian_pattern_rows": attempt1["opening_with_outlet_reset"]["dimension"],
            "includes U-HX:HX-energy-hot": True,
            "core_outcome": "CONVERGED (not LINEAR_SOLVE_FAILED)",
            "iterations": f"regression {dormancy.DZ12_ATTEMPT1_ITERATIONS}",
        },
        "cause_strings_naming_an_item": [],
        "root": "ref.dormant_non_lifted_cases.DZ-12.root within §13's EO allowances",
        "certificate": {
            "verification_status": "VERIFIED",
            "regularity": "NO_RANK_LOSS_DETECTED",
            "dimension": registered["zero_flow_form"]["dimension"],
        },
        "T05-W13_outcome": f"regression {dormancy.DZ12_V1}",
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- B28

#: B28's traversal refusals (spec §12.9), as the gate's refusal tests pin them.
_P3_REFUSALS = {
    "DZ-11": "initializer_failed(U-HX): specification_unsatisfiable_with_dormant_side",
    "DZ-2C": "initializer_failed(U-PHF): duty_into_dormant_stream",
}


@cache
def _p3_traversal(case: str) -> Any:
    """The plan's own start (the traversal) under `T05b-v2`, as the gate's refusal tests run it."""
    if case == "DZ-11":
        return dormancy._solve(support.dz11(), support.POLICY_V2)
    return zero_flow_tests._solve(support.dz2c(), support.POLICY_V2)


def _p3_first_line(message: str) -> str:
    return message.splitlines()[0] if message else ""


def _p3_conflict(case: str, result: Any, v1: Any, v1_pin: str, ledger: Ledger) -> dict[str, Any]:
    """B28 for one conflict: outcome, message, no root and no certificate, the end state, the
    swapped row's observed value, the traversal's refusal, the `T05-W13` outcome."""
    registered = REF["zero_flow_conflicts"][case]
    expected = registered["expected"]
    ((row, observed_ref),) = registered["swapped_row_at_end_W"].items()
    attempts = result.attempts
    observed = attempts[0].observations.get(f"swapped_row:{row}") if attempts else None
    traversal = _p3_traversal(case).run
    record = {
        "outcome": ledger.equal(f"{case} outcome", result.outcome, expected["outcome"]),
        "message": ledger.equal(
            f"{case} message first line", _p3_first_line(result.message), expected["message"]
        ),
        "attempts": ledger.equal(
            f"{case} attempts (signature, outcome, core outcome)",
            [[_p3_signatures([a])[0], a.outcome, a.solver_outcome] for a in attempts],
            [[registered["signature"], "SPECIFICATION_CONFLICT", "CONVERGED"]],
        ),
        "root_fingerprint": ledger.equal(f"{case} root", result.root_fingerprint, None),
        "checkpoint": ledger.equal(
            f"{case} checkpoint", result.checkpoint and result.checkpoint.label, "partial"
        ),
        "identity_entry": ledger.equal(
            f"{case} t05b identity entry (no certificate)",
            sorted(identity_document()["t05b"][case]),
            ["message", "outcome"],
        ),
        "end_state": _p3_state_against(result.state, registered["end_state"], ledger, case),
        "swapped_row": row,
        "swapped_row_observed_W": observed,
        "swapped_row_error_W": ledger.within(
            f"{case} observed {row}", observed, observed_ref, _P3_ALLOWANCE["duty"]
        ),
        "value_in_message": ledger.equal(
            f"{case} 1000 in message", "1000" in result.message, False
        ),
        "traversal": ledger.equal(
            f"{case} traversal",
            [traversal.outcome, _p3_first_line(traversal.message)],
            ["INITIALIZATION_FAILED", _P3_REFUSALS[case]],
        ),
        "T05-W13_outcome": ledger.equal(f"{case} under T05-W13 (regression)", v1.outcome, v1_pin),
    }
    ledger.true(f"{case} under T05-W13 not CONVERGED", v1.outcome != "CONVERGED")
    return record


def _p3_swapped_rows(case: str) -> list[str]:
    """A DZ root's swapped rows: its dormancy forms' (`ref.dormant_non_lifted_cases.<case>.
    swapped_rows`), or the swapped row of the lifted split `ref` registers dormant there (the
    unit of `ref.dormant_cases.<case>.label.row`; `splits.zero_flow_forms`' row). A TP-type
    split (DZ-5) swaps nothing."""
    if case in dormancy.CASES:
        return list(dormancy.CASES[case]["swapped_rows"])
    label = zero_flow_tests.DORMANT[case]["label"]
    if label is None:
        return []
    forms = zero_flow_tests._forms(zero_flow_tests.bind(support.DORMANT_CASES[case]()))
    return [forms[label["row"].split(":", 1)[0]].swapped]


def _b28() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    value: dict[str, Any] = {
        "DZ-11": _p3_conflict(
            "DZ-11",
            dormancy._dz11(),
            dormancy._dz11("v1"),
            dormancy.DZ11_V1,
            ledger,
        ),
        "DZ-2C": _p3_conflict(
            "DZ-2C",
            zero_flow_tests._dz2c(),
            zero_flow_tests._dz2c("v1"),
            zero_flow_tests.V1_FROM_THE_START["DZ-2C"],
            ledger,
        ),
    }
    # Every other DZ root's swapped rows hold there (the certificates of B15–B17, B24–B27).
    certificates = {case: zero_flow_tests._solved(case).certificate for case in ("DZ-1", "DZ-2")}
    certificates.update(
        {case: zero_flow_tests._solved(case).certificate for case in ("DZ-4", "DZ-5")}
    )
    certificates.update(
        {case: dormancy._solved(case, "v2").certificate for case in ("DZ-6", "DZ-7")}
    )
    certificates.update(
        {case: dormancy._solved(case, "v2").certificate for case in ("DZ-8", "DZ-9")}
    )
    certificates.update({case: _p3_dz_root(case)[3] for case in ("DZ-3", "DZ-10", "DZ-12")})
    held: dict[str, Any] = {}
    for case, certificate in certificates.items():
        by_id = {check.id: check for check in certificate.checks}
        for row in _p3_swapped_rows(case):
            check = by_id.get(f"residual.{row}")
            held[f"{case} {row}"] = None if check is None else [check.result, check.value]
            ledger.equal(f"{case} residual.{row}", check and check.result, "pass")
    value["swapped_rows_at_the_other_roots"] = held
    value["departures"] = ledger.departures
    expected: dict[str, Any] = {
        case: {
            "outcome": "SPECIFICATION_CONFLICT",
            "message": REF["zero_flow_conflicts"][case]["expected"]["message"],
            "attempts": [
                [REF["zero_flow_conflicts"][case]["signature"], "SPECIFICATION_CONFLICT"]
                + ["CONVERGED"]
            ],
            "root_fingerprint": None,
            "checkpoint": "partial",
            "identity_entry": ["message", "outcome"],
            "end_state": f"ref.zero_flow_conflicts.{case}.end_state within §13's allowances",
            "swapped_row_observed_W": REF["zero_flow_conflicts"][case]["swapped_row_at_end_W"],
            "swapped_row_error_W": "≤ 1e-2",
            "value_in_message": False,
            "traversal": ["INITIALIZATION_FAILED", _P3_REFUSALS[case]],
            "T05-W13_outcome": f"not CONVERGED; regression {pin}",
        }
        for case, pin in (
            ("DZ-11", dormancy.DZ11_V1),
            ("DZ-2C", zero_flow_tests.V1_FROM_THE_START["DZ-2C"]),
        )
    }
    expected["swapped_rows_at_the_other_roots"] = "every one passes"
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- B29

#: Spec B29: each injected value `≥ 10⁵ τ` from its threshold.
_P3_B29_DETECTION = 1e5


def _b29() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    import pytest

    from openflowsheet.verify.certificate import verify_revision

    ledger = Ledger()
    injections = REF["dormant_non_lifted_injections"]

    # INJ-B4: DZ-11's end state, with the `CONVERGED` claim a region without the swapped-row test
    # makes there (the gate's construction).
    entry = injections["INJ-B4"]
    with pytest.MonkeyPatch.context() as monkeypatch:
        claim = dormancy._without_the_swapped_row_test(monkeypatch)
    binding = dormancy.bind(support.dz11())
    step = dormancy.planned_step(binding, support.POLICY_V2)
    certificate = verify_revision(
        binding,
        support.dz11(),
        claim,
        state=support.registered_state(dormancy.DZ11["end_state"]),
        solve_plan=step.solve_plan,
    )
    by_id = {check.id: check for check in certificate.checks}
    failing = [check.id for check in certificate.checks if check.result == "fail"]
    ruled = sorted(
        ["residual.U-HX:HX-energy-hot", "energy_balance.U-HX.hot", "energy_balance.envelope"]
    )
    label = by_id.get("residual.U-HX:zero-flow-label:hot")
    cold = by_id.get("energy_balance.U-HX.cold")
    value: dict[str, Any] = {
        "INJ-B4": {
            "claim": ledger.equal("INJ-B4 claim", claim.outcome, "CONVERGED"),
            "verification_status": ledger.equal(
                "INJ-B4 verdict", certificate.verification_status, "FAILED"
            ),
            "false_success_detected": ledger.equal(
                "INJ-B4 false_success_detected", certificate.false_success_detected, True
            ),
            "failing": failing,
            "failing_outside_the_ruled_set": ledger.equal(
                "INJ-B4 failing outside the ruled set", sorted(set(failing) - set(ruled)), []
            ),
            "first_failing": ledger.equal(
                "INJ-B4 first failing check", failing[:1], ["residual.U-HX:HX-energy-hot"]
            ),
            **{
                name: _p3_registered(
                    by_id.get(name), entry[key], ledger, f"INJ-B4 {name}", _P3_B29_DETECTION
                )
                for name, key in (
                    ("residual.U-HX:HX-energy-hot", "residual_U-HX:HX-energy-hot_W"),
                    ("energy_balance.U-HX.hot", "energy_balance_U-HX_in_minus_out_W"),
                    ("energy_balance.envelope", "energy_balance_envelope_in_minus_out_W"),
                )
            },
            "residual.U-HX:zero-flow-label:hot": ledger.equal(
                "INJ-B4 label check",
                None if label is None else [label.result, label.value],
                ["pass", 0.0],
            ),
            "energy_balance.U-HX.cold": ledger.equal(
                "INJ-B4 energy_balance.U-HX.cold", cold and cold.result, "pass"
            ),
        }
    }
    ledger.equal(
        "INJ-B4 residual.U-HX:HX-energy-hot fails",
        "residual.U-HX:HX-energy-hot" in failing,
        True,
    )

    # INJ-B5: DZ-9's root with S3.T = 310 K, against DZ-9's v1 claim (the gate's construction).
    entry = injections["INJ-B5"]
    state = dict(support.registered_state(dormancy.CASES["DZ-9"]["root"]))
    state["S3.T"] = 310.0
    certificate = _p3_verify(dormancy._solved("DZ-9", "v1"), state)
    by_id = {check.id: check for check in certificate.checks}
    compiled = [
        check
        for check in certificate.checks
        if check.category == "residual" and check.id != "residual.U-MIX:zero-flow-label"
    ]
    compiled_max = max((abs(check.value or 0.0) for check in compiled), default=None)
    regularity = certificate.regularity
    ledger.true("INJ-B5 compiled residuals present", bool(compiled))
    value["INJ-B5"] = {
        "verification_status": ledger.equal(
            "INJ-B5 verdict", certificate.verification_status, "FAILED"
        ),
        "failing": sorted(check.id for check in certificate.checks if check.result == "fail"),
        "residual.U-MIX:zero-flow-label": _p3_registered(
            by_id.get("residual.U-MIX:zero-flow-label"),
            entry["residual_U-MIX:zero-flow-label_K"],
            ledger,
            "INJ-B5 residual.U-MIX:zero-flow-label",
            _P3_B29_DETECTION,
            "fail",
        ),
        "compiled_residuals": len(compiled),
        "compiled_not_passing": ledger.equal(
            "INJ-B5 compiled residuals not passing",
            sorted(check.id for check in compiled if check.result != "pass"),
            [],
        ),
        "compiled_rows_max": compiled_max,
        "compiled_rows_max_error": ledger.within(
            "INJ-B5 compiled rows max", compiled_max, entry["compiled_rows_max"], 0.0
        ),
        "regularity": ledger.equal(
            "INJ-B5 regularity",
            None if regularity is None else regularity.status,
            "NO_RANK_LOSS_DETECTED",
        ),
    }
    value["departures"] = ledger.departures
    expected = {
        "INJ-B4": {
            "claim": "CONVERGED (a region without the swapped-row test)",
            "verification_status": "FAILED",
            "false_success_detected": True,
            "failing": "a subset of " + ", ".join(ruled) + ", containing (first) "
            "residual.U-HX:HX-energy-hot",
            "residual.U-HX:HX-energy-hot": "−1 000 W within τ_E, failing, ≥ 10⁵ τ",
            "energy_balance.U-HX.hot": "−1 000 W within τ_E, ≥ 10⁵ τ (Q-S4 (3): the table's "
            "energy_balance.U-HX read as the dormant side's)",
            "energy_balance.envelope": "−1 000 W within τ_E, ≥ 10⁵ τ",
            "residual.U-HX:zero-flow-label:hot": ["pass", 0.0],
            "energy_balance.U-HX.cold": "pass",
        },
        "INJ-B5": {
            "verification_status": "FAILED",
            "residual.U-MIX:zero-flow-label": "−20 K within τ_T, failing, ≥ 10⁵ τ",
            "compiled_not_passing": [],
            "compiled_rows_max": "exactly 0.0 (ref…INJ-B5.compiled_rows_max)",
            "regularity": "NO_RANK_LOSS_DETECTED",
        },
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- B30

#: B30 (a)'s registered cases, in `test_t05b_dormancy._registered_runs`' order of names.
_P3_B30A_CASES = (
    "SYN-001-UL-C1",
    "SYN-001-UL-C2",
    "SYN-001-UL-C3",
    "SYN-001-UL-C3X",
    "SC-1",
    "SC-2",
    "SC-3",
    "SC-4",
    "NP-1",
    "NP-2",
    "NP-3",
    "NP-G",
    "DZ-1",
    "DZ-2",
    "DZ-4",
    "DZ-5",
    "DZ-3",
)
#: A stream-flow column of a committed state (`<S>.n.<c>`), W0.10's rule.
_P3_FLOW_COLUMN = re.compile(r"^(?P<stream>[A-Za-z0-9_-]+)\.n\.[A-Za-z0-9_]+$")
_P3_REGIMES = ("LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW")
#: The T05b reference sections that register the amendment's own dormant cases.
_P3_DZ_SECTIONS = ("dormant_cases", "dormant_non_lifted_cases", "zero_flow_conflicts")


def _p3_number(item: Any) -> Decimal | None:
    if isinstance(item, bool) or not isinstance(item, int | float | str):
        return None
    try:
        return Decimal(str(item))
    except InvalidOperation:
        return None


def _p3_scan(node: Any, path: str, found: dict[str, list[Any]]) -> None:
    """W0.10's walk of one record: each mapping with stream-flow keys whose streams are all
    exactly dormant (`found["dormant"]`), and each signature pair whose entry is an item
    `<U>.<port>` (`found["items"]`). A flow value that is not a number (a note, a nested
    record) is not an exact zero."""
    if isinstance(node, dict):
        streams: dict[str, list[Decimal | None]] = {}
        for key, item in node.items():
            match = _P3_FLOW_COLUMN.match(key) if isinstance(key, str) else None
            if match:
                streams.setdefault(match["stream"], []).append(_p3_number(item))
        if streams:
            found["states"].append(path)
            dormant = sorted(
                s for s, flows in streams.items() if all(f is not None and f == 0 for f in flows)
            )
            if dormant:
                found["dormant"].append([path, dormant])
        for key, item in node.items():
            _p3_scan(item, f"{path}/{key}", found)
    elif isinstance(node, list):
        if (
            len(node) == 2
            and all(isinstance(entry, str) for entry in node)
            and node[1] in _P3_REGIMES
            and "." in node[0]
        ):
            found["items"].append([path, node])
        for index, item in enumerate(node):
            _p3_scan(item, f"{path}[{index}]", found)


def _p3_committed_records() -> dict[str, Any]:
    """W0.10 over every committed JSON/YAML record under `tests/fixtures`, `benchmarks` and
    `evidence` (`git ls-files`), and over the K05 identity document."""
    files = [
        name
        for name in _git("ls-files", "tests/fixtures", "benchmarks", "evidence").split()
        if name.endswith((".json", ".yaml", ".yml"))
    ]
    found: dict[str, list[Any]] = {"states": [], "dormant": [], "items": []}
    for name in files:
        text = (ROOT / name).read_text(encoding="utf-8")
        document = json.loads(text) if name.endswith(".json") else yaml.safe_load(text)
        _p3_scan(document, name, found)
    identity: dict[str, list[Any]] = {"states": [], "dormant": [], "items": []}
    _p3_scan(identity_document(), "identity", identity)
    return {"files": len(files), "records": found, "identity": identity}


def _p3_in_the_dz_sections(path: str) -> bool:
    """A path inside a DZ case of the T05b reference's dormant-case sections."""
    prefix = "benchmarks/t05b/reference_values.yaml/"
    if not path.startswith(prefix):
        return False
    section, case = (path.removeprefix(prefix).split("/") + ["", ""])[:2]
    return section in _P3_DZ_SECTIONS and case.split("[")[0].startswith("DZ-")


def _p3_signature_units(node: Any, path: str, found: dict[str, Any]) -> None:
    if isinstance(node, dict):
        for key, item in node.items():
            if key == "signature_units":
                found[f"{path}/{key}"] = item
            else:
                _p3_signature_units(item, f"{path}/{key}", found)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _p3_signature_units(item, f"{path}[{index}]", found)


def _p3_registered_signature_units() -> dict[str, list[str]]:
    """The T05b plans' `signature_units` a registration implies: the lifted (unit) entries of
    `ref`'s signature (SC-1…SC-4, DZ-6…DZ-10, DZ-12; SC-3's final one), and the lifted unit of
    DZ-1, DZ-2, DZ-4, DZ-5 (`test_t05b_zero_flow.AT_THE_START`)."""
    registered: dict[str, list[str]] = {}
    for case, entry in REF["single_component_cases"].items():
        signature = entry.get("signature") or entry["signatures"]["final"]
        registered[case] = [unit for unit, _ in signature if "." not in unit]
    for case in ("DZ-6", "DZ-7", "DZ-8", "DZ-9", "DZ-10", "DZ-12"):
        signature = REF["dormant_non_lifted_cases"][case]["signature"]
        registered[case] = [unit for unit, _ in signature if "." not in unit]
    for case, (unit, _, _) in zero_flow_tests.AT_THE_START.items():
        registered[case] = [unit]
    return registered


def _b30() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    document = identity_document()

    # (a) No dormancy item in any attempt signature (or provenance item) of the registered cases
    # under T05b-v2 (`test_t05b_dormancy`'s own runs).
    runs = dormancy._registered_runs()
    items = {
        case: [list(entry) for signature in signatures for entry in signature if "." in entry[0]]
        for case, signatures in runs.items()
    }
    ledger.equal("(a) cases", sorted(runs), sorted(_P3_B30A_CASES))
    ledger.equal("(a) items", {case: v for case, v in items.items() if v}, {})
    part_a = {
        "signatures_per_case": {case: len(signatures) for case, signatures in runs.items()},
        "cases_with_an_item": sorted(case for case, found in items.items() if found),
    }

    # (b) W0.10: no committed record has a dormancy-form outlet with its trigger exactly dormant;
    # every dormant stream and every item in a record is one of the amendment's DZ cases.
    scan = _p3_committed_records()
    records, identity = scan["records"], scan["identity"]
    outside = [hit for hit in records["dormant"] if not _p3_in_the_dz_sections(hit[0])]
    items_outside = [hit for hit in records["items"] if not _p3_in_the_dz_sections(hit[0])]
    identity_items = [hit for hit in identity["items"] if not hit[0].startswith("identity/t05b/")]
    triggers = REF["registered_dormancy_trigger_flows_mol_per_s"]
    not_positive = sorted(name for name, flow in triggers.items() if not Decimal(flow) > 0)
    ledger.equal("(b) dormant streams outside the DZ cases", outside, [])
    ledger.equal("(b) items outside the DZ cases", items_outside, [])
    ledger.equal("(b) items in the identity document outside t05b", identity_items, [])
    ledger.equal("(b) registered trigger flows not > 0", not_positive, [])
    part_b = {
        "files": scan["files"],
        "state_mappings": len(records["states"]),
        "mappings_with_a_dormant_stream": len(records["dormant"]),
        "all_in_the_dz_sections": not outside,
        "dormant_outside_the_dz_sections": outside,
        "items_in_records": len(records["items"]),
        "items_outside_the_dz_sections": items_outside,
        "identity_items_outside_t05b": identity_items,
        "identity_items_in_t05b": len(identity["items"]) - len(identity_items),
        "registered_trigger_flows_mol_per_s": {
            name: float(Decimal(flow)) for name, flow in triggers.items()
        },
    }

    # (c) Every plan's `signature_units`: T02–T05's are in the identity document outside `t05b`
    # (its digest W0.1's, measured before any T05b edit); T05b's are the lifted units its
    # registrations imply, never an item.
    units: dict[str, Any] = {}
    _p3_signature_units(document, "identity", units)
    t05b_units = {path: v for path, v in units.items() if path.startswith("identity/t05b/")}
    others = {path: v for path, v in units.items() if path not in t05b_units}
    minus_t05b = _document_sha256({k: v for k, v in document.items() if k != "t05b"})
    ledger.equal("(c) identity minus t05b", minus_t05b, REGISTERED["identity_minus_t05b_sha256"])
    with_items = sorted(path for path, v in units.items() if any("." in unit for unit in v))
    ledger.equal("(c) signature_units carrying an item", with_items, [])
    plans = {
        case: entry["plan"]["steps"][-1]["signature_units"]
        for case, entry in document["t05b"].items()
        if "plan" in entry
    }
    registered_units = _p3_registered_signature_units()
    differing = {
        case: [plans.get(case), expected]
        for case, expected in registered_units.items()
        if plans.get(case) != expected
    }
    ledger.equal("(c) T05b plans against their registrations", differing, {})
    t05b_key = _key_sha256(document["t05b"])
    ledger.equal("(c) t05b key", t05b_key, REGISTERED["t05b_key_sha256"])
    part_c = {
        "t02_t05_lists": len(others),
        "t02_t05_distinct": sorted({json.dumps(v) for v in others.values()}),
        "identity_minus_t05b_sha256": minus_t05b,
        "t05b_plans": plans,
        "t05b_compared_with_a_registration": sorted(registered_units),
        "differing": differing,
        "with_an_item": with_items,
        "t05b_key_sha256": t05b_key,
    }

    # (d) The `t05` key and the document minus {t05, t05b}; the T05b cases' check ids against
    # the W8 baseline (T05's are in the `t05` key, SYN-001's in the rest).
    t05_key = _key_sha256(document["t05"])
    minus = _document_sha256({k: v for k, v in document.items() if k not in ("t05", "t05b")})
    ledger.equal("(d) t05 key", t05_key, REGISTERED["t05_key_sha256"])
    ledger.equal(
        "(d) identity minus t05, t05b", minus, REGISTERED["identity_minus_t05_t05b_sha256"]
    )
    baseline = json.loads((FIXTURES / "t05b" / "check_ids.json").read_text(encoding="utf-8"))
    baseline = baseline["check_ids"]
    changes: dict[str, Any] = {}
    for case, ids in baseline.items():
        live = document["t05b"].get(case, {}).get("certificate", {}).get("check_ids")
        if live != ids:
            live = live or []
            changes[case] = {
                "gained": sorted(set(live) - set(ids)),
                "lost": sorted(set(ids) - set(live)),
                "order_changed": sorted(live) == sorted(ids),
            }
    full = [case for case, entry in document["t05b"].items() if "certificate" in entry]
    ledger.equal("(d) baseline cases", list(baseline), full)
    ledger.equal("(d) check ids gained or lost", changes, {})
    part_d = {
        "t05_key_sha256": t05_key,
        "identity_minus_t05_t05b_sha256": minus,
        "check_id_cases": len(baseline),
        "check_ids": sum(len(ids) for ids in baseline.values()),
        "changes": changes,
    }
    value = {"a": part_a, "b": part_b, "c": part_c, "d": part_d, "departures": ledger.departures}
    expected = {
        "a": {"cases": list(_P3_B30A_CASES), "cases_with_an_item": []},
        "b": {
            "all_in_the_dz_sections": True,
            "dormant_outside_the_dz_sections": [],
            "items_outside_the_dz_sections": [],
            "identity_items_outside_t05b": [],
            "registered_trigger_flows_mol_per_s": "every one > 0",
        },
        "c": {
            "identity_minus_t05b_sha256": REGISTERED["identity_minus_t05b_sha256"],
            "differing": {},
            "with_an_item": [],
            "t05b_key_sha256": REGISTERED["t05b_key_sha256"],
        },
        "d": {
            "t05_key_sha256": REGISTERED["t05_key_sha256"],
            "identity_minus_t05_t05b_sha256": REGISTERED["identity_minus_t05_t05b_sha256"],
            "changes": {},
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS.update(
    {
        "B15": "DZ-1 and DZ-2 (`test_t05b_zero_flow`'s solves: `plan_revision` → `execute_plan` → "
        "`verify_revision` under `T05b-v2`): `CONVERGED` with no Jacobian call, one attempt at "
        "iteration 0 with signature `[[U, ZERO_FLOW]]`; the attempt's rows (compiled, then the "
        "label) and free columns exactly `ref…zero_flow_form`'s, `jacobian_pattern.rows` and "
        "`.columns` its dimension 10; every registered root column `==` `ref`, every flow `== "
        "0.0`, every dormant outlet `T == 330.0`, every duty `== 0.0`; `branch_found` `[[U, "
        "ZERO_FLOW]]`; `VERIFIED`, `NO_RANK_LOSS_DETECTED` at dimension 10; "
        "`residual.U:zero-flow-label` present, `0.0` and passing; every compiled residual `== "
        "0.0`. The `T05-W13` half (`test_t05_dormant_outlet`'s solves): `CONVERGED` at iteration "
        "0 with no Jacobian call in the `TWO_PHASE` form, `branch_found` and the certificate's "
        "verdict, regularity and dimension as under `T05b-v2`.",
        "B16": "DZ-3 from `ref…DZ-3.start` under `T05b-v2` (`test_t05b_zero_flow._dz3`, the "
        "planned region from the supplied start): `CONVERGED`; `U-VLV` `ZERO_FLOW` in every "
        "attempt's signature; `|S5.T − S4.T| ≤ 1e-9 K`; `S4.T` within 1e-5 K of PHF-1's `T` "
        "(`ref…DZ-3.root.S4.T`, full precision); every `S4` and `S5` flow `== 0.0`; `VERIFIED` "
        "through the verifier's projection (as amended by K04-F9 X07: `judged_at = projection`, "
        "every fresh-flash value `≤ 1e-3` of its tolerance, the worst recorded; the certificate "
        "as K04-F9's tests build it). From the same start under `T05-W13`: not `CONVERGED`, the "
        "outcome equal to the gate's regression pin.",
        "B17": "DZ-4 and DZ-5 as B15's `T05b-v2` half with their `ref` sets (12 × 12, 11 × 11); "
        "DZ-5's attempt has no label row and its certificate no `residual.U-HEAT:zero-flow-label` "
        "check.",
        "B18": "The injections, judged by `verify_revision(..., state=…)` against a solved "
        "claim (`test_t05b_verifier`'s fixture: SC-1's `T05b-v2` solve): INJ-B1 `FAILED`, "
        "`false_success_detected`, the degenerate judgement in force (`.saturation` passes at "
        "`δ = 0` to 1e-12 K, the split's independent check `not_applicable`, "
        "`temperature_degenerate`), the failing set exactly {`residual.U-VLV:VLV-energy`, "
        "`energy_balance.U-VLV`, `energy_balance.envelope`}, each `+2 016 W` within its own "
        "`τ_kind` and `≥ 10³ τ`. As amended by K04-F9 X12–X14: INJ-B2's state (PRJ-B2) is "
        "`VERIFIED`, judged at the projection, every compiled residual passing and its compiled "
        "energy and equilibrium-B rows `ref…INJ-B2`'s within `τ_kind`; at `x_final` (the table "
        "unprojected) the fresh flash judges it — no `.saturation`, "
        "`independent_split.U-VLV.S2.total` `−1.9328 mol/s` and `energy_balance.U-VLV` "
        "`−57 984.0004 W` failing within `τ_kind`, `≥ 10³ τ`; INJ-B2′ (2e-5 K) `FAILED`, "
        "`false_success_detected`, judged at the final state, its split total and balance "
        "K04-F9's `ref` values within `τ_kind`, `≥ 10³ τ`; INJ-B2p `VERIFIED` judged at the "
        "projection, and at `x_final` degenerate (`δ = 5e-7 K`) with `energy_balance.U-VLV` "
        "`−1e-4 W` within `τ_E`, passing and 10× inside. INJ-B3 (DZ-1's root at `S2.T = 331 K`, "
        "against DZ-1's `T05b-v2` claim): `FAILED`, `residual.U-VLV:zero-flow-label` `1 K` "
        "within `τ_T`, failing, `≥ 10³ τ`. T05's INJ-T1…T4: T05's generator's A22 measurement, "
        "its condition and departures.",
        "B24": "DZ-6 (pump) and DZ-9 (mixer) under `T05b-v2` (`test_t05b_dormancy`'s solves): "
        "`CONVERGED` with no Jacobian call, one attempt at iteration 0 with signature "
        "`[[U-PUMP.outlet, ZERO_FLOW]]` / `[[U-MIX.outlet, ZERO_FLOW]]`; the attempt's rows and "
        "free columns `ref…zero_flow_form`'s as sets (the label row last, the swapped row out; "
        "DZ-9's `U-MIX:MIX-pressure:1` in the plan's `eliminated_rows`, `ref`'s list); "
        "`jacobian_pattern.rows` 11 / 15; every registered root column `==` `ref`; every flow "
        "`== 0.0`; DZ-6 `S2.T == 330.0`, `U-PUMP.W == 0.0`; DZ-9 `S3.T == 330.0`; the plan's "
        "`signature_units == []`; `branch_found == []`; `VERIFIED`, `NO_RANK_LOSS_DETECTED` at "
        "11 / 15; the label check present, `0.0`, passing; every compiled residual `== 0.0`. "
        "Under `T05-W13`: `CONVERGED` at iteration 0 with no Jacobian call, signature `[]`, and "
        "the same verdict, regularity and dimension. DZ-9 declared mixer first (Q-S4 (1)): "
        "`CONVERGED` at iteration 0, `VERIFIED` at dimension 15, `S3.T == 330.0`, every flow "
        "`== 0.0`, its rows the zero-flow form minus the plan's `eliminated_rows`, which are "
        "exactly the second feed's `FEED-P` (regression pin).",
        "B25": "DZ-7 and DZ-8 (exchanger) as B24: DZ-7 signature `[[U-HX.hot_outlet, "
        "ZERO_FLOW]]`, label row `U-HX:zero-flow-label:hot`, `S2.T == 290.0`, `S4.T == 300.0`, "
        "`U-HX.Q == 0.0`, its registered root exact (the cold side flows); DZ-8 signature "
        "`[[U-HX.cold_outlet, ZERO_FLOW]]` only, no `…:zero-flow-label:hot` row or check, `S2.T "
        "== 345.0`, `S4.T == 300.0`, `U-HX.Q == 0.0`; both `VERIFIED` at dimension 21; on both "
        "`T05b-v2` certificates `bounds_and_domain.U-HX.hot_end` and `.cold_end` "
        "`not_applicable` with reason `ZERO_FLOW` (Q-S4 (4)) and `.heat_flow` passing; the "
        "`T05-W13` half as B24's.",
        "B26": "DZ-10 from `ref…DZ-10.start` under `T05b-v2` (`test_t05b_dormancy._dz10`, with "
        "its trace): `CONVERGED`; every attempt's signature ends with `[U-PUMP.outlet, "
        "ZERO_FLOW]`; no cause string (attempt reasons, trace event messages) names "
        "`U-PUMP.outlet`; every `S5` flow `== 0.0` (and `S4`'s); `|S5.T − S4.T| ≤ 1e-9 K`; "
        "`S4.T` within 1e-5 K of `ref…DZ-10.phf1_T_K`; `VERIFIED` through the verifier's "
        "projection (K04-F9 X08: `judged_at = projection`, every fresh-flash value `≤ 1e-3` of "
        "its tolerance, the worst recorded). Under `T05-W13`: not `CONVERGED`, the outcome equal "
        "to the gate's regression pin.",
        "B27": "DZ-12 from `ref…DZ-12.start` under `T05b-v2` (`test_t05b_dormancy._dz12`, with "
        "its trace): `CONVERGED` with exactly two attempts; attempt 0's signature "
        "`ref…attempt0`'s, its core `CONVERGED` at iteration 0, `jacobian_pattern.rows == 30` "
        "including `U-HX:zero-flow-label:hot` and excluding `U-HX:HX-energy-hot`; the "
        "`attempt_opened` messages `initial` and `phase_update(inadmissible(S1, all_liquid))` "
        "(`ref`'s), no `fallback(…)` item; attempt 1's signature `[[U-PHF, TWO_PHASE]]`, "
        "`jacobian_pattern.rows == 34` including `U-HX:HX-energy-hot`, core outcome `CONVERGED`; "
        "no cause string names `U-HX.hot_outlet`; the final state within §13's EO allowances of "
        "`ref…DZ-12.root` (worst ratio recorded); `VERIFIED`, `NO_RANK_LOSS_DETECTED` at 34. "
        "Regression pins compared with the gate's: attempt 1's iterations, the `T05-W13` "
        "outcome.",
        "B28": "DZ-11 and DZ-2C from their `ref` starts under `T05b-v2`: `SPECIFICATION_CONFLICT`; "
        "message first line `zero_flow_conflict(U-HX:HX-energy-hot)` / "
        "`zero_flow_conflict(U-PHF:PHF-duty)`; one attempt, its signature `ref`'s, outcome "
        "`SPECIFICATION_CONFLICT` over a `CONVERGED` core; no certificate (no root fingerprint, "
        "the checkpoint `partial`, the `t05b` identity entry only outcome and message); the end "
        "state within §13's allowances of `ref…end_state`; the observed swapped-row value "
        "`−1 000 W` / `+1 000 W` within 1e-2 W in the attempt's observations, and not in the "
        "message. Every other DZ root's swapped rows pass there (the certificates of B15–B17, "
        "B24–B27). The traversal ends `INITIALIZATION_FAILED` with "
        "`initializer_failed(U-HX): specification_unsatisfiable_with_dormant_side` / "
        "`initializer_failed(U-PHF): duty_into_dormant_stream`. Under `T05-W13`: not "
        "`CONVERGED`, the gate's regression pins.",
        "B29": "INJ-B4: DZ-11's end state judged against the `CONVERGED` claim of a region "
        "without the swapped-row test (the gate's construction): `FAILED`, "
        "`false_success_detected`; `residual.U-HX:HX-energy-hot` fails at `−1 000 W` within "
        "`τ_E`; `energy_balance.U-HX.hot` (Q-S4 (3)'s reading of `energy_balance.U-HX`) and "
        "`energy_balance.envelope` `−1 000 W` within `τ_E`; each `≥ 10⁵ τ`; "
        "`residual.U-HX:zero-flow-label:hot` passes at `0.0`; the failing checks a subset of "
        "{`residual.U-HX:HX-energy-hot`, `energy_balance.U-HX.hot`, `energy_balance.envelope`}, "
        "the first `residual.U-HX:HX-energy-hot`; `energy_balance.U-HX.cold` passes. INJ-B5: "
        "DZ-9's root at `S3.T = 310 K` against DZ-9's `T05-W13` claim: `FAILED`; "
        "`residual.U-MIX:zero-flow-label` `−20 K` within `τ_T`, failing, `≥ 10⁵ τ`; every "
        "compiled residual passes, their largest `|value|` exactly `ref`'s `0.0`; "
        "`NO_RANK_LOSS_DETECTED`.",
        "B30": "(a) `test_t05b_dormancy`'s runs of C1, C2, C3, C3X, SC-1…SC-4, NP-1…NP-3, NP-G, "
        "DZ-1…DZ-5 under `T05b-v2`: no item (`U.port`) in any attempt signature or provenance "
        "signature. (b) W0.10, measured here (the gate does not scan records): every committed "
        "JSON/YAML under `tests/fixtures`, `benchmarks`, `evidence` (`git ls-files`) and the K05 "
        "identity document walked; every state mapping with a stream all of whose flows are "
        "exactly 0, and every signature item, lies in a DZ case of the T05b reference's "
        "`dormant_cases`, `dormant_non_lifted_cases` or `zero_flow_conflicts` (the amendment's "
        "own cases), none in the identity document outside `t05b`; every "
        "`ref.registered_dormancy_trigger_flows_mol_per_s` `> 0`. (c) Every plan's "
        "`signature_units` in the identity document: T02–T05's all outside the `t05b` key, whose "
        "digest (document minus `t05b`) is W0.1's `622463f5…`, measured before any T05b edit; "
        "the T05b plans' equal to the lifted units their registrations imply (`ref`'s signatures "
        "without items, DZ-1/2/4/5's unit), none carrying an item, and the `t05b` key W9.4's "
        "`4f29500e…`. (d) The `t05` key `ddbd0f71…` and the document minus {`t05`, `t05b`} "
        "`b364bb3d…`; each T05b case's certificate check ids equal to "
        "`tests/fixtures/t05b/check_ids.json` (W8's baseline; T05's cases are in the `t05` key, "
        "SYN-001's in the rest).",
    }
)
MEASURES.update(
    {
        "B15": _b15,
        "B16": _b16,
        "B17": _b17,
        "B18": _b18,
        "B24": _b24,
        "B25": _b25,
        "B26": _b26,
        "B27": _b27,
        "B28": _b28,
        "B29": _b29,
        "B30": _b30,
    }
)


# -------------------------------------------- B31-B36: openings, screen, release, candidate answers


#: B31 (b)'s dew-point restarts, its downstream flashes, and (i)'s companions.
_P4_DEW = ("CH-UP", "CH-DZ12", "CH-3")
_P4_DOWNSTREAM = ("U-PHF2", "U-PHF3")
#: The flow columns' kinds, as `test_b31d_ch_dormant` reads them.
_P4_FLOW_KINDS = ("n", "vap", "liq", "N", "V", "L")


def _p4_text(text: str) -> str:
    """A measured string as recorded: `<` (the manifest's placeholder mark) replaced by `‹`."""
    return text.replace("<", "‹")


def _p4_attempts(result: RegionResult) -> list[tuple[str, int, list[list[str]], str]]:
    """Each attempt's `(outcome, iterations, signature, reason)`, as the tests compare them."""
    return [
        (a.outcome, a.iterations, [list(e) for e in a.signature], a.reason) for a in result.attempts
    ]


def _p4_certificate(certificate: Any) -> dict[str, Any]:
    """The verdict, the regularity status, the screened dimension and escalated rank, and the
    checks that failed, are unsupported, or are not applicable."""
    if certificate is None:
        return {"verification_status": None}
    regularity = certificate.regularity
    escalation = None if regularity is None else regularity.escalation
    return {
        "verification_status": certificate.verification_status,
        "regularity": None if regularity is None else regularity.status,
        "dimension": None if regularity is None else regularity.dimension,
        "rank": None if escalation is None else escalation["rank"],
        "false_success_detected": certificate.false_success_detected,
        "fail_or_unsupported": [
            c.id for c in certificate.checks if c.result in ("fail", "unsupported")
        ],
        "not_applicable": [c.id for c in certificate.checks if c.result == "not_applicable"],
    }


def _p4_leavings(run: Any) -> list[dict[str, Any]]:
    """Every attempt whose opening takes a downstream flash out of `ZERO_FLOW`, and whether its
    `attempt_opened` carries `fallback(U, tp)` for it."""
    found: list[dict[str, Any]] = []
    attempts = run.result.attempts
    for index in range(1, len(attempts)):
        before, after = dict(attempts[index - 1].signature), dict(attempts[index].signature)
        for unit in _P4_DOWNSTREAM:
            if before.get(unit) == "ZERO_FLOW" and after.get(unit) != "ZERO_FLOW":
                found.append(
                    {
                        "attempt": index,
                        "unit": unit,
                        "fallback_recorded": f"fallback({unit}, tp)" in run.opened[index],
                    }
                )
    return found


def _p4_state_ratio(
    got: Mapping[str, float], reference: Mapping[str, float], allowance: Any
) -> dict[str, Any]:
    """The largest `|got − reference| / allowance(column)` over the reference's columns."""
    return worst(
        {
            column: abs(got[column] - value) / allowance(column)
            for column, value in reference.items()
        }
    )


def _p4_b31_records(ledger: Ledger) -> dict[str, Any]:
    """B31's leaving records as registered (W9.3, re-registered at W10.4 for B36): the dew-point
    cases' attempts and `attempt_opened` messages (`RESTARTS`) and the companions' outcomes,
    signatures, reasons, messages and iteration counts (`OFF_DEW_ITERATIONS`)."""
    records: dict[str, Any] = {}
    for case in _P4_DEW:
        run = openings.solved(case)
        attempts, opened = openings.RESTARTS[case]
        records[case] = {"attempts": _p4_attempts(run.result), "attempt_opened": run.opened}
        ledger.equal(f"{case}: attempts (regression)", records[case]["attempts"], attempts)
        ledger.equal(f"{case}: attempt_opened (regression)", run.opened, opened)
    for case, dew in openings.OFF_DEW.items():
        run = openings.solved(case)
        attempts, opened = openings.RESTARTS[dew]
        measured = [(o, s, r) for o, _, s, r in _p4_attempts(run.result)]
        records[case] = {
            "attempts": _p4_attempts(run.result),
            "attempt_opened": run.opened,
        }
        ledger.equal(
            f"{case}: outcomes, signatures, reasons as {dew}'s",
            measured,
            [(o, s, r) for o, _, s, r in attempts],
        )
        ledger.equal(f"{case}: attempt_opened as {dew}'s", run.opened, opened)
        ledger.equal(
            f"{case}: iterations (regression)",
            [a.iterations for a in run.result.attempts],
            openings.OFF_DEW_ITERATIONS[case],
        )
    return records


def _p4_b34_counts(ledger: Ledger) -> dict[str, Any]:
    """B34 (a)'s outcome counts and certificate tally against the test's re-registered pins."""
    counts = candidates._counts()
    certified = candidates.certificates()
    tally = dict(Counter(c.verification_status for c in certified.values()))
    ledger.equal("B34 (a) outcome counts (regression, Q-S15 (1))", counts, candidates.OUTCOMES)
    ledger.equal("B34 (a) certificate tally (regression, Q-S15 (1))", tally, candidates.TALLY)
    return {"outcome_counts": counts, "certificate_tally": tally}


# ------------------------------------------------------------------------------------ B31


def _p4_b31_rank(case: str, entry: Mapping[str, Any], ledger: Ledger) -> None:
    """The screened dimension and rank against the twin's (`ref.downstream_flash_cases`) where
    it registers the flowsheet (CH-UP, CH-3; the order variant as CH-UP)."""
    base = case.split("/")[0]
    dp = "dp=10000" if base.endswith("-DP") else "dp=0"
    twin = openings.DOWNSTREAM.get(f"{base.removesuffix('-DP')}/{dp}")
    if twin is None:
        return
    ledger.equal(f"{case}: dimension as the twin's", entry["dimension"], int(twin["dimension"]))
    if entry["rank"] is not None:
        ledger.equal(f"{case}: rank as the twin's", entry["rank"], int(twin["declared_rank"]))
    else:
        ledger.equal(
            f"{case}: the twin's form regular", int(twin["declared_rank"]), entry["dimension"]
        )


def _p4_b31_function_level(ledger: Ledger) -> dict[str, Any]:
    """(f) the chain of resets at the function level and its single-pass control; (g) the fixed
    point stubbed never to settle, at attempt 0 and at a restart."""
    value: dict[str, Any] = {}
    reference = frozenset({"U-PUMP1.outlet", "U-PUMP2.outlet"})
    for pump2_first in (False, True):
        (_, _, forms), order, state = openings._chain_opening(pump2_first)
        opened, regimes, records, changes = _settle(
            state,
            {"U-PHF": "TWO_PHASE"},
            order=order,
            reference=reference,
            leave=openings._no_leave,
        )
        copies = all(
            repr(opened[f"S4.n.{c}"]) == repr(opened[f"S3.n.{c}"])
            and repr(opened[f"S5.n.{c}"]) == repr(opened[f"S4.n.{c}"])
            for c in "ABC"
        )
        items = _items(forms, opened)
        where = "U-PUMP2 first" if pump2_first else "declared order"
        value[f"(f) {where}"] = {
            "S4.n == S3.n and S5.n == S4.n bitwise": copies,
            "items": [list(item) for item in items],
            "regimes": regimes,
            "records": records,
            "changes": list(changes),
            "order": [getattr(e, "item", getattr(e, "unit", "")) for e in order],
        }
        ledger.true(f"(f) {where}: S4.n == S3.n, S5.n == S4.n bitwise", copies)
        ledger.equal(f"(f) {where}: no pump item", items, ())
        ledger.equal(f"(f) {where}: no split changes", regimes, {"U-PHF": "TWO_PHASE"})
        ledger.equal(f"(f) {where}: no records, no changes", (records, changes), ({}, []))
        ledger.equal(
            f"(f) {where}: the fixed point's order",
            value[f"(f) {where}"]["order"],
            ["U-PHF", "U-PUMP2.outlet", "U-PUMP1.outlet"]
            if pump2_first
            else ["U-PHF", "U-PUMP1.outlet", "U-PUMP2.outlet"],
        )
    # (f)'s control: one pass with `U-PUMP2` declared first.
    (_, _, forms), order, state = openings._chain_opening(True)
    control_regimes: dict[str, Any] = {"U-PHF": "TWO_PHASE"}
    present_at_visit: dict[str, bool] = {}
    for entry in order:
        if isinstance(entry, DormancyForm):
            present_at_visit[entry.item] = _trigger_dormant(entry, state)
        _rederive(entry, state, control_regimes, reference, openings._no_leave, {}, [])
    stale = all(state[f"S5.n.{c}"] == 0.0 for c in "ABC")
    value["(f) control, single pass"] = {
        "item present at visit": present_at_visit,
        "S5 stays 0.0": stale,
    }
    ledger.equal(
        "(f) control: U-PUMP2's item present at its visit",
        present_at_visit,
        {"U-PUMP2.outlet": True, "U-PUMP1.outlet": False},
    )
    ledger.true("(f) control: S5 left stale at 0.0", stale)
    # (g) at attempt 0.
    document, start = openings.CASES["CH-UP"]()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "_rederive", openings._never_settles)
        result = openings.solve_from_v2(openings.bind(document), start)
    value["(g) attempt 0"] = {
        "outcome": result.outcome,
        "message_first_line": _p4_text(result.message.splitlines()[0]),
        "attempts": len(result.attempts),
    }
    ledger.equal("(g) attempt 0: outcome", result.outcome, "ACTIVE_SET_CYCLING")
    ledger.equal(
        "(g) attempt 0: message", result.message.splitlines()[0], "opening_not_settled(U-PHF)"
    )
    ledger.equal("(g) attempt 0: no attempt", result.attempts, ())
    # (g) at a restart: the stub switched on inside the restart's `_settled` only.
    real, settled = region_module._rederive, region_module._LiftedOps._settled
    at_restart = {"on": False}

    def rederive(entry: Any, *args: Any) -> Any:
        return openings._never_settles(entry) if at_restart["on"] else real(entry, *args)

    def restart(self: Any, *args: Any, **kwargs: Any) -> Any:
        at_restart["on"] = True
        try:
            return settled(self, *args, **kwargs)
        finally:
            at_restart["on"] = False

    document, start = openings.CASES["CH-UP"]()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "_rederive", rederive)
        patch.setattr(region_module._LiftedOps, "_settled", restart)
        result = openings.solve_from_v2(openings.bind(document), start)
    value["(g) restart"] = {
        "outcome": result.outcome,
        "message_first_line": _p4_text(result.message.splitlines()[0]),
        "attempts": [a.outcome for a in result.attempts],
    }
    ledger.equal("(g) restart: outcome", result.outcome, "ACTIVE_SET_CYCLING")
    ledger.equal(
        "(g) restart: message", result.message.splitlines()[0], "opening_not_settled(U-PHF)"
    )
    ledger.equal(
        "(g) restart: attempt 0 kept", [a.outcome for a in result.attempts], ["ACTIVE_SET_CYCLING"]
    )
    return value


def _b31() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """B31 on `test_t05b_openings`'s cases and cached solves (`solved`: `solve_from_v2`, then
    `verify_revision` when `CONVERGED`); closed forms by the test's `closed_form` from DZ-12's
    registered root, compared by its `realized_ratio` (Decimal differences over §13's EO
    allowances)."""
    ledger = Ledger()
    cases: dict[str, Any] = {}
    for case in openings.CASES:
        run = openings.solved(case)
        result = run.result
        entry: dict[str, Any] = {
            "outcome": result.outcome,
            "attempts": _p4_attempts(result),
            "attempt_opened": run.opened,
            "final_regimes": openings._final_regimes(result),
            **_p4_certificate(run.certificate),
        }
        if entry.get("rank") is not None:
            entry["rank_loss"] = entry["dimension"] - entry["rank"]
        if "/" not in case and case != "CH-DORMANT":
            ratio, column = openings.realized_ratio(case)
            entry["closed_form_ratio"] = {"ratio": ratio, "where": column}
        cases[case] = entry
        # (a) a typed outcome, no exception (an exception would propagate from `solved`).
        ledger.true(f"(a) {case}: typed outcome {result.outcome}", result.outcome in openings.TYPED)

    # (b) CH-UP, CH-DZ12, CH-3 (and the order variant's verdict, (e)).
    records = _p4_b31_records(ledger)
    for case in (*_P4_DEW, "CH-UP/PHF2-first"):
        entry, run = cases[case], openings.solved(case)
        ledger.equal(f"(b) {case}: outcome", entry["outcome"], "CONVERGED")
        leavings = _p4_leavings(run)
        entry["leaving_attempts"] = leavings
        ledger.true(f"(b) {case}: an opening leaves ZERO_FLOW", bool(leavings))
        for found in leavings:
            ledger.true(
                f"(b) {case}: fallback({found['unit']}, tp) on attempt {found['attempt']}",
                found["fallback_recorded"],
            )
        ledger.equal(f"(b) {case}: verdict", entry["verification_status"], "UNVERIFIED")
        ledger.equal(f"(b) {case}: regularity", entry["regularity"], "RANK_DEFICIENT")
        ledger.equal(f"(b) {case}: rank loss", entry.get("rank_loss"), openings.RANK_LOSS[case])
        ledger.equal(f"(b) {case}: no check fail/unsupported", entry["fail_or_unsupported"], [])
        _p4_b31_rank(case, entry, ledger)
        base = case.split("/")[0]
        zero = {
            column.split(".")[0]
            for column, expected in openings.closed_form(base).items()
            if ".n." in column and expected == "0"
        }
        aside = [c for c in entry["not_applicable"] if c.rsplit(".", 1)[-1] not in zero]
        ledger.equal(f"(b) {case}: not_applicable only on the zero liquid products", aside, [])
        if "closed_form_ratio" in entry:
            ledger.at_most(
                f"(b) {case}: closed form at {entry['closed_form_ratio']['where']}",
                entry["closed_form_ratio"]["ratio"],
                1.0,
            )

    # (c) CH-DOWN.
    run = openings.solved("CH-DOWN")
    entry, state = cases["CH-DOWN"], run.result.state
    zero_flows = all(state[f"{s}.n.{c}"] == 0.0 for s in ("S4", "S5") for c in "ABC")
    entry["S4_S5_flows_exactly_zero"] = zero_flows
    entry["abs_S4T_minus_S2T_K"] = abs(state["S4.T"] - state["S2.T"])
    ledger.equal("(c) CH-DOWN: outcome", entry["outcome"], "CONVERGED")
    ledger.equal("(c) CH-DOWN: verdict", entry["verification_status"], "VERIFIED")
    ledger.equal(
        "(c) CH-DOWN: final regimes",
        entry["final_regimes"],
        {"U-PHF": "LIQUID", "U-PHF2": "ZERO_FLOW"},
    )
    ledger.true("(c) CH-DOWN: every flow of S4, S5 == 0.0", zero_flows)
    ledger.at_most("(c) CH-DOWN: |S4.T − S2.T| K", entry["abs_S4T_minus_S2T_K"], 1e-9)
    ledger.at_most("(c) CH-DOWN: closed form", entry["closed_form_ratio"]["ratio"], 1.0)
    # Regression values held by `test_b31c_ch_down` (W9.3).
    ledger.equal(
        "(c) CH-DOWN: attempts (regression, test_b31c_ch_down)",
        [(a.outcome, a.iterations, a.reason) for a in run.result.attempts],
        [
            ("PHASE_UPDATE_REQUIRED", 1, "phase_disappeared(U-PHF, vapor, S2.n.C)"),
            ("CONVERGED", 1, ""),
        ],
    )
    ledger.equal(
        "(c) CH-DOWN: attempt_opened (regression, test_b31c_ch_down)",
        run.opened,
        ["initial", "phase_update(phase_disappeared(U-PHF, vapor, S2.n.C))"],
    )

    # (d) CH-DORMANT, both orders.
    for case in ("CH-DORMANT", "CH-DORMANT/PHF2-first"):
        run = openings.solved(case)
        entry, result = cases[case], run.result
        flows = [v for k, v in result.state.items() if k.split(".")[1] in _P4_FLOW_KINDS]
        entry["initializer"] = run.initializer
        entry["projections"] = list(result.projections)
        entry["every_flow_exactly_zero"] = bool(flows) and all(v == 0.0 for v in flows)
        entry["T_minus_300_K"] = {s: abs(result.state[f"{s}.T"] - 300.0) for s in ("S2", "S4")}
        ledger.equal(f"(d) {case}: outcome", entry["outcome"], "CONVERGED")
        ledger.equal(f"(d) {case}: verdict", entry["verification_status"], "VERIFIED")
        ledger.equal(
            f"(d) {case}: attempt 0's signature, plan order",
            entry["attempts"][0][2],
            [[unit, "ZERO_FLOW"] for unit in run.signature_units],
        )
        ledger.equal(f"(d) {case}: the two splits", set(run.signature_units), {"U-PHF", "U-PHF2"})
        ledger.true(
            f"(d) {case}: one attempt, iteration 0 or 1",
            len(result.attempts) == 1 and result.attempts[0].iterations in (0, 1),
        )
        ledger.equal(
            f"(d) {case}: the overwrites recorded",
            run.initializer,
            [
                "projected(S1, two_phase, ZERO_FLOW)",
                "projected(S2, all_vapor, ZERO_FLOW)",
                "the start with 2 split(s) projected onto the kernel's",
            ],
        )
        ledger.equal(f"(d) {case}: projections", entry["projections"], ["S1", "S2"])
        ledger.true(f"(d) {case}: every flow == 0.0", entry["every_flow_exactly_zero"])
        for stream, difference in entry["T_minus_300_K"].items():
            ledger.at_most(f"(d) {case}: |{stream}.T − 300| K", difference, 1e-9)

    # (e) each order variant as its declared-first case.
    variants: dict[str, Any] = {}
    for case in ("CH-UP", "CH-DOWN", "CH-DORMANT"):
        first, variant = openings.solved(case), openings.solved(f"{case}/PHF2-first")
        ratio = _p4_state_ratio(variant.result.state, first.result.state, openings._allowance)
        variants[case] = {
            "outcome": [first.result.outcome, variant.result.outcome],
            "verdict": [
                cases[case]["verification_status"],
                cases[f"{case}/PHF2-first"]["verification_status"],
            ],
            "attempts": [len(first.result.attempts), len(variant.result.attempts)],
            "state_ratio": ratio,
        }
        where = f"(e) {case}/PHF2-first"
        ledger.equal(f"{where}: outcome", variant.result.outcome, first.result.outcome)
        ledger.equal(
            f"{where}: verdict",
            cases[f"{case}/PHF2-first"]["verification_status"],
            cases[case]["verification_status"],
        )
        ledger.equal(
            f"{where}: final regimes",
            openings._final_regimes(variant.result),
            openings._final_regimes(first.result),
        )
        ledger.equal(
            f"{where}: attempt count (regression)",
            len(variant.result.attempts),
            len(first.result.attempts),
        )
        ledger.at_most(f"{where}: state within the allowances", ratio["ratio"], 1.0)

    # (f), (g) at the function level.
    function_level = _p4_b31_function_level(ledger)

    # (i) the companions off the dew point.
    for case in openings.OFF_DEW:
        run, entry = openings.solved(case), cases[case]
        downstream = [unit for unit in _P4_DOWNSTREAM if unit in run.signature_units]
        final = entry["final_regimes"]
        state = run.result.state
        entry["products_P_Pa"] = {
            f"{product}.P": state[f"{product}.P"]
            for product in openings.DP_STAGES[case.removesuffix("-DP")]
        }
        ledger.equal(f"(i) {case}: outcome", entry["outcome"], "CONVERGED")
        ledger.equal(f"(i) {case}: verdict", entry["verification_status"], "VERIFIED")
        ledger.equal(f"(i) {case}: regularity", entry["regularity"], "NO_RANK_LOSS_DETECTED")
        ledger.equal(f"(i) {case}: no check fail/unsupported", entry["fail_or_unsupported"], [])
        _p4_b31_rank(case, entry, ledger)
        ledger.true(
            f"(i) {case}: every downstream flash VAPOR",
            bool(downstream) and all(final[unit] == "VAPOR" for unit in downstream),
        )
        for found in _p4_leavings(run):
            ledger.true(
                f"(i) {case}: fallback({found['unit']}, tp) on attempt {found['attempt']}",
                found["fallback_recorded"],
            )
        ledger.at_most(
            f"(i) {case}: closed form (P included) at {entry['closed_form_ratio']['where']}",
            entry["closed_form_ratio"]["ratio"],
            1.0,
        )

    ratios = {
        case: entry["closed_form_ratio"]["ratio"]
        for case, entry in cases.items()
        if "closed_form_ratio" in entry
    }
    value = {
        "cases": cases,
        "worst_closed_form_ratio": worst(ratios),
        "leaving_records": records,
        "order_variants": variants,
        "function_level": function_level,
        "h_on_its_own_commit": {
            "cited": "docs/t05b-measurements.md W9.3: the `t05b` key, B07, B21's identities "
            "and B30 unchanged on the fixed point's commit (historical); today's identity "
            "hashes are measured under B21 and B22",
            "section_present": "## 2026-09-25 — W9.3" in MEASUREMENTS.read_text(encoding="utf-8"),
        },
        "departures": ledger.departures,
    }
    expected = {
        "a": "every case a typed outcome (CONVERGED, ACTIVE_SET_CYCLING, LINEAR_SOLVE_FAILED, "
        "BOUND_BLOCKED), no exception",
        "b": {
            "outcome": "CONVERGED",
            "verdict": "UNVERIFIED",
            "regularity": "RANK_DEFICIENT",
            "rank_loss": openings.RANK_LOSS,
            "twin_ranks": {
                name: [int(entry["dimension"]), int(entry["declared_rank"])]
                for name, entry in openings.DOWNSTREAM.items()
                if isinstance(entry, dict) and "dimension" in entry
            },
            "checks": "none fail or unsupported; not_applicable only on the zero liquid products",
            "leaving": "fallback(U, tp) on the attempt_opened of the opening that leaves",
            "attempts_and_messages": "RESTARTS (regression, W9.3; W10.4)",
            "closed_form": "ratio to §13's EO allowances at most 1 (DZ-12's registered root)",
        },
        "c": "CONVERGED, VERIFIED, U-PHF LIQUID, U-PHF2 ZERO_FLOW, S4 and S5 flows == 0.0, "
        "|S4.T − S2.T| ≤ 1e-9 K, S3 = (1,1,1) at 300 K within the allowances",
        "d": "both orders: attempt 0 both splits ZERO_FLOW in plan order, the projected(...) "
        "records, CONVERGED at iteration 0 or 1, VERIFIED, every flow == 0.0, S2.T and S4.T "
        "within 1e-9 K of 300 K",
        "e": "each variant: outcome, verdict, final regimes as its declared-first case, state "
        "ratio at most 1",
        "f_g": "the chain settles bitwise in either order with no pump item, the single pass "
        "leaves U-PUMP2 stale; the unsettled fixed point ACTIVE_SET_CYCLING, "
        "opening_not_settled(U-PHF)",
        "h": "historical (cited, not measured here)",
        "i": {
            "outcome": "CONVERGED",
            "verdict": "VERIFIED",
            "regularity": "NO_RANK_LOSS_DETECTED",
            "downstream_final": "VAPOR",
            "iterations": openings.OFF_DEW_ITERATIONS,
            "pressure_drop_Pa": openings.DOWNSTREAM["downstream_pressure_drop_Pa"],
            "closed_form": "ratio at most 1, products at P_in − 10 000 Pa per stage",
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B31"] = (
    "An opening agrees with exact dormancy, on `tests/test_t05b_openings.py`'s cases solved from "
    "their registered starts under `T05b-v2` and certified by `verify_revision`: (a) all eleven "
    "cases (CH-UP, CH-DOWN, CH-DZ12, CH-3, CH-DORMANT, three order variants, three `-DP` "
    "companions) end in a typed outcome; (b) CH-UP, CH-DZ12, CH-3 (and CH-UP/PHF2-first) "
    "`CONVERGED`, `UNVERIFIED`, `RANK_DEFICIENT` with rank loss 1, 1, 2 (1) — the screened "
    "dimension and rank equal to the twin's (`ref.downstream_flash_cases`: 31/30, 44/42) — no "
    "check `fail` or `unsupported` and `not_applicable` only on the zero liquid products, "
    "`fallback(U, tp)` on the leaving attempt, the attempt records and messages as registered, "
    "and the final state within §13's EO allowances of DZ-12's registered root (worst ratio "
    "recorded); (c) CH-DOWN `VERIFIED`, `LIQUID`/`ZERO_FLOW`, exact zero flows, `S4.T` on `S2.T` "
    "to 1e-9 K; (d) CH-DORMANT in both orders; (e) each order variant as its declared-first case "
    "(state ratio recorded); (f), (g) at the function level (the settled chain bitwise, its "
    "single-pass control, the unsettled fixed point typed); (h) cited as historical "
    "(`docs/t05b-measurements.md` W9.3; today's identities are B21's and B22's); (i) the three "
    "companions `CONVERGED`, `VERIFIED`, `NO_RANK_LOSS_DETECTED`, downstream `VAPOR`, products "
    "at `P_in − 10 kPa` within the allowances of the closed form."
)
MEASURES["B31"] = _b31


# ------------------------------------------------------------------------------------ B32


def _p4_b32_kernel_states(ledger: Ledger) -> dict[str, Any]:
    """(a) at KS-1…KS-3: the screen's regime at SC-1's valve outlet against the contract's
    kernel at the same state (`test_b32a_the_contract_kernel_states`)."""
    found: dict[str, Any] = {}
    flowsheet = band_screen.bind(band_screen.sc1()).flowsheet
    (split,) = lifted_splits(
        [(u.unit_id, u.model_id, flowsheet.wiring[u.unit_id]) for u in flowsheet.units()],
        flowsheet.components,
    )
    ledger.equal("(a) SC-1's closure types", closure_types(flowsheet.units()), {"U-VLV": "PH"})
    for state_id in ("KS-1", "KS-2", "KS-3"):
        entry = REF["contract_kernel_states"][state_id]
        state = band_screen._kernel_state(entry)
        target = _split_enthalpy(flowsheet.provider, flowsheet.context, split, state)
        feed = tuple(state[name] for name in split.feed)
        screened = (
            None
            if target is None
            else _band_regime(flowsheet.provider, flowsheet.context, feed, state["S2.P"], target)
        )
        kernel = _contract_kernel(
            flowsheet.provider, flowsheet.context, split, state, frozenset({"U-VLV"})
        )
        record = {
            "screened": screened,
            "kernel_regime": kernel.regime,
            "kernel_fallback": kernel.fallback,
        }
        ledger.equal(f"(a) {state_id}: kernel regime", kernel.regime, entry["expected_regime"])
        if state_id == "KS-3":
            regime, _ = _kernel(flowsheet.provider, flowsheet.context, split, state)
            record["tp_flash_regime"] = regime
            ledger.equal(f"(a) {state_id}: (s1)", screened, TP_REGIME)
            ledger.equal(f"(a) {state_id}: fallback", kernel.fallback, "tp")
            ledger.equal(f"(a) {state_id}: the TP flash's regime", regime, kernel.regime)
        else:
            ledger.equal(f"(a) {state_id}: screened = kernel", screened, kernel.regime)
        found[state_id] = record
    return found


def _p4_b32_grid(ledger: Ledger) -> dict[str, Any]:
    """(a) on §12.1's eight compositions × fifteen points (`test_b32a_*`'s `_targets`): (s3)
    exactly at the `± τ_E/2` points; elsewhere the screened regime equals `ph_state`'s, or is
    (s1) exactly where `ph_state` refuses `ph_outside_domain`."""
    counts = {"points": 0, "s1": 0, "s2": 0, "s3": 0, "zone_points": 0}
    per_composition: dict[str, Any] = {}
    for name in sorted(band_screen.COMPOSITIONS):
        n, pressure, _, _ = band_screen.COMPOSITIONS[name]
        points = list(band_screen._targets(name))
        ledger.equal(f"(a) {name}: points", len(points), 15)
        labels: dict[str, Any] = {}
        for label, target, zone in points:
            counts["points"] += 1
            counts["zone_points"] += zone
            screened = _band_regime(band_screen.PROVIDER, band_screen.CONTEXT, n, pressure, target)
            labels[label] = screened
            where = f"(a) {name} {label}"
            if screened is None:
                counts["s3"] += 1
                ledger.true(f"{where}: (s3) only at a ± tau/2 point", zone)
                continue
            ledger.true(f"{where}: (s3) at a ± tau/2 point", not zone)
            closure = ph_state(band_screen.PROVIDER, n, pressure, target, band_screen.CONTEXT)
            if screened == TP_REGIME:
                counts["s1"] += 1
                ledger.equal(f"{where}: ph_state refuses", closure.status, "out_of_domain")
                ledger.true(
                    f"{where}: ph_outside_domain", closure.code.startswith("ph_outside_domain(")
                )
                continue
            counts["s2"] += 1
            ledger.equal(f"{where}: ph_state answers", closure.status, "ok")
            regime = (
                None
                if closure.split is None
                else band_screen._regime(closure.split.phase_signature)
            )
            ledger.equal(f"{where}: regime as ph_state's", screened, regime)
        ledger.equal(
            f"(a) {name}: domain ends (s1), band ends by enthalpy order",
            [
                labels["T_min - 1 W"],
                labels["T_max + 1 W"],
                labels["H_0 -1 2 tau"],
                labels["H_0 +1 2 tau"],
                labels["H_1 -1 2 tau"],
                labels["H_1 +1 2 tau"],
            ],
            [TP_REGIME, TP_REGIME, "LIQUID", "TWO_PHASE", "TWO_PHASE", "VAPOR"],
        )
        per_composition[name] = {label: labels[label] for label in labels}
    return {"counts": counts, "regimes": per_composition}


def _p4_b32_metered(ledger: Ledger) -> dict[str, Any]:
    """(b) NP-1…NP-G from the liquid-form start through `execute_plan` with the region's
    property meter (`test_b32b_near_pure_restarts_fit_the_region_meter`)."""
    found: dict[str, Any] = {}
    for case in ("NP-1", "NP-2", "NP-3", "NP-G"):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                band_screen.revision,
                "traversal_start",
                band_screen._liquid_form(band_screen.revision.traversal_start),
            )
            binding = band_screen.bind(band_screen.near_pure(case))
            plan, _ = band_screen.plan_revision(binding, band_screen.POLICY_V2)
            ledger.true(f"(b) {case}: planned", isinstance(plan, band_screen.ExecutionPlan))
            run = band_screen.executor.execute_plan(
                plan=plan,
                flowsheet=binding.flowsheet,
                spec=binding.spec,
                policy=band_screen.POLICY_V2,
            )
        (step,) = run.steps
        found[case] = {
            "outcome": run.outcome,
            "property_calls_metered": run.counters.property_calls,
            "signatures": [[list(e) for e in a.signature] for a in step.detail.attempts],
        }
        ledger.true(f"(b) {case}: not BUDGET_EXHAUSTED", run.outcome != "BUDGET_EXHAUSTED")
        ledger.equal(f"(b) {case}: outcome (the test's)", run.outcome, "CONVERGED")
        ledger.true(
            f"(b) {case}: calls within the meter",
            run.counters.property_calls < band_screen.POLICY_V2.max_property_calls,
        )
        ledger.equal(
            f"(b) {case}: attempts' signatures",
            found[case]["signatures"],
            [[["U-PHF", "LIQUID"]], [["U-PHF", "TWO_PHASE"]]],
        )
    return {"cases": found, "max_property_calls": band_screen.POLICY_V2.max_property_calls}


def _p4_coupled_r0_equal(case: str) -> bool:
    """B07's comparison on one of T05's coupled cases (`test_b07_…`): the R0 documents of the
    two literals equal with the policy's identity taken out."""
    v1 = contract._coupled_r0(case, contract.POLICY_V1)
    v2 = contract._coupled_r0(case, contract.POLICY_V2)
    return bool(
        contract._without_policy(v2, contract.POLICY_V2.policy_id)
        == contract._without_policy(v1, contract.POLICY_V1.policy_id)
    )


def _b32() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    kernel_states = _p4_b32_kernel_states(ledger)
    grid = _p4_b32_grid(ledger)
    counts = grid["counts"]
    ledger.equal(
        "(a) (s3) taken at exactly the ± tau/2 points", counts["s3"], counts["zone_points"]
    )
    ledger.equal("(a) ± tau/2 points: four per composition", counts["zone_points"], 4 * 8)
    metered = _p4_b32_metered(ledger)
    # (c) inert on R0.
    key = _key_sha256(identity_document()["t05b"])
    ledger.equal("(c) the t05b key (W9.4's)", key, REGISTERED["t05b_key_sha256"])
    b07 = {
        case: _p4_coupled_r0_equal(case)
        for case in ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3", "SYN-001-UL-C3X")
    }
    for case, equal in b07.items():
        ledger.true(f"(c) B07 {case}: v2's R0 is v1's", equal)
    sc3 = contract.solved("SC-3")
    sc3_updates = [m for m in sc3.messages("attempt_opened") if m.startswith("phase_update(")]
    sc3_iterations = tuple(a.iterations for a in sc3.region.attempts)
    ledger.equal(
        "(c) SC-3's attempt_opened (test_b10_sc3)",
        sc3_updates,
        ["phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE))"],
    )
    ledger.equal("(c) SC-3's iterations (regression)", sc3_iterations, contract.SC3_ITERATIONS)
    value = {
        "a_kernel_states": kernel_states,
        "a_grid": grid,
        "b_metered": metered,
        "c": {
            "t05b_key_sha256": key,
            "b07_equal": b07,
            "sc3_attempt_opened_updates": sc3_updates,
            "sc3_iterations": sc3_iterations,
        },
        "departures": ledger.departures,
    }
    expected = {
        "a": "KS-1, KS-2 (s2) TWO_PHASE equal to the contract kernel's; KS-3 (s1) with the TP "
        "flash's LIQUID and fallback tp; on 8 compositions × 15 points the screened regime "
        "equals ph_state's, (s1) exactly where ph_state refuses ph_outside_domain, (s3) "
        "exactly at the 32 ± tau_E/2 points",
        "b": "none BUDGET_EXHAUSTED; property calls recorded (regression, not R0; W9.6 measured "
        "3 419, 3 565, 547, 530 metered)",
        "c": {
            "t05b_key_sha256": REGISTERED["t05b_key_sha256"],
            "b07_equal": dict.fromkeys(b07, True),
            "sc3_attempt_opened_updates": [
                "phase_update(phase_wall(patience, U-PHF:LIQUID->TWO_PHASE))"
            ],
            "sc3_iterations": contract.SC3_ITERATIONS,
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B32"] = (
    "The screen's regime by band-end enthalpies: (a) at KS-1…KS-3 `_band_regime` against the "
    "contract kernel at SC-1's valve outlet (KS-3 by (s1), the TP flash's regime with "
    "`fallback(…, tp)`), and on §12.1's eight compositions at the fifteen points of "
    "`tests/test_t05b_band_screen.py` (five grid targets, `H_0 ± τ_E/2`, `H_0 ± 2τ_E`, "
    "`H_1 ± τ_E/2`, `H_1 ± 2τ_E`, the domain ends ∓ 1 W) against `ph_state` — (s1) exactly where "
    "it refuses `ph_outside_domain`, (s3) exactly at the `± τ_E/2` points (counted); (b) NP-1…NP-G "
    "from the liquid-form start through `execute_plan`: none `BUDGET_EXHAUSTED`, metered "
    "provider calls recorded (regression, not R0); (c) the `t05b` key's hash (W9.4's), B07's "
    "R0 equality on T05's four coupled cases, and SC-3's `attempt_opened` records and "
    "iterations unchanged."
)
MEASURES["B32"] = _b32


# ------------------------------------------------------------------------------------ B33


def _p4_b33_openings(ledger: Ledger) -> dict[str, Any]:
    """(a) the test's `openings` spy (its fixture's function, driven with a monkeypatch) over
    each registered run: every restart opening where a products-style PH-type split took a PH
    closure's answer, both products' temperatures against the closure's `T`, bitwise."""
    spy = near_pure_tests.openings.__wrapped__
    found: dict[str, Any] = {}
    for case, run in near_pure_tests.RUNS.items():
        with pytest.MonkeyPatch.context() as patch:
            generator = spy(patch)
            seen = next(generator)
            run()
            generator.close()
        bitwise = [
            repr(o.vapor_temperature) == repr(o.closure_temperature)
            and repr(o.liquid_temperature) == repr(o.closure_temperature)
            for o in seen
        ]
        found[case] = {
            "openings": [
                {"unit": o.unit, "closure_T_K": o.closure_temperature, "bitwise": equal}
                for o, equal in zip(seen, bitwise, strict=True)
            ],
        }
        ledger.true(f"(a) {case}: a restart opening took a PH closure's answer", bool(seen))
        ledger.true(f"(a) {case}: both products at the closure's T bitwise", all(bitwise))
    return found


def _p4_b33_near_pure(ledger: Ledger) -> dict[str, Any]:
    """(b) NP-1…NP-G from the liquid-form start (`from_liquid`, the test's cache)."""
    allowance = near_pure_tests.ALLOWANCE
    found: dict[str, Any] = {}
    for case in ("NP-1", "NP-2", "NP-3", "NP-G"):
        run = near_pure_tests.from_liquid(case)
        result, certificate = run.result, run.certificate
        entry = REF["near_pure_cases"][case]
        root, state = entry["root"], result.state
        record: dict[str, Any] = {
            "outcome": result.outcome,
            "signatures": [[list(e) for e in a.signature] for a in result.attempts],
            "iterations": tuple(a.iterations for a in result.attempts),
            "attempt_1_opened": run.opened[1] if len(run.opened) > 1 else None,
            **_p4_certificate(certificate),
        }
        where = f"(b) {case}"
        ledger.equal(f"{where}: outcome", result.outcome, "CONVERGED")
        ledger.equal(
            f"{where}: signatures",
            record["signatures"],
            [[["U-PHF", "LIQUID"]], [["U-PHF", "TWO_PHASE"]]],
        )
        ledger.true(
            f"{where}: attempt 1 names U-PHF LIQUID->TWO_PHASE",
            record["attempt_1_opened"] is not None
            and record["attempt_1_opened"].startswith(near_pure_tests.CAUSE),
        )
        ledger.equal(
            f"{where}: fallback(U-PHF, ph-band) item (regression)",
            "fallback(U-PHF, ph-band)" in (record["attempt_1_opened"] or ""),
            near_pure_tests.BAND_ITEM[case],
        )
        ledger.equal(
            f"{where}: iterations (regression)",
            record["iterations"],
            near_pure_tests.ITERATIONS[case],
        )
        ledger.equal(f"{where}: verdict", record["verification_status"], "VERIFIED")
        checks = {} if certificate is None else {c.id: c for c in certificate.checks}
        split = checks.get("independent_split.U-PHF.S1")
        if case == "NP-G":
            record["T_error_K"] = {
                stream: ledger.within(
                    f"{where}: {stream}.T",
                    state[f"{stream}.T"],
                    root["T_K"],
                    near_pure_tests.NP_G_TEMPERATURE,
                )
                for stream in ("S2", "S3")
            }
            record["judged"] = None if split is None else [split.result, split.reason]
            ledger.equal(
                f"{where}: unresolved",
                record["judged"],
                ["not_applicable", "fresh_flash_unresolved"],
            )
            found[case] = record
            continue
        flows = {}
        for index, component in enumerate(near_pure_tests.COMPONENTS):
            for stream, key in (("S2", "vapor_mol_per_s"), ("S3", "liquid_mol_per_s")):
                flows[f"{stream}.n.{component}"] = ledger.within(
                    f"{where}: {stream}.n.{component}",
                    state[f"{stream}.n.{component}"],
                    root[key][index],
                    allowance["flow"],
                )
        largest = worst(flows)
        record["flow_error_worst"] = {
            "error_mol_s": largest["ratio"],
            "where": largest["where"],
            "allowance_mol_s": allowance["flow"],
        }
        record["T_error_K"] = {
            stream: ledger.within(
                f"{where}: {stream}.T", state[f"{stream}.T"], root["T_K"], allowance["T"]
            )
            for stream in ("S2", "S3")
        }
        if entry["degenerate"]:
            saturation = checks.get("phase_admissibility.U-PHF.S1.saturation")
            record["judged"] = {
                "saturation": None if saturation is None else saturation.result,
                "independent_split": None if split is None else [split.result, split.reason],
            }
            ledger.equal(
                f"{where}: degenerate",
                record["judged"],
                {
                    "saturation": "pass",
                    "independent_split": ["not_applicable", "temperature_degenerate"],
                },
            )
        else:
            record["judged"] = {
                suffix: checks[f"independent_split.U-PHF.S1.{suffix}"].result
                for suffix in ("total", *near_pure_tests.COMPONENTS)
                if f"independent_split.U-PHF.S1.{suffix}" in checks
            }
            ledger.equal(
                f"{where}: resolved",
                record["judged"],
                dict.fromkeys(("total", *near_pure_tests.COMPONENTS), "pass"),
            )
            ledger.true(
                f"{where}: no saturation check",
                "phase_admissibility.U-PHF.S1.saturation" not in checks,
            )
        found[case] = record
    return found


def _p4_b33_release(ledger: Ledger) -> dict[str, Any]:
    """(c) K03 §5.3's release at the level of the bound-aware step (the test's two-column
    problems, `near_pure_tests._step` and the direct calls)."""
    found: dict[str, Any] = {}
    # (i) row 0 `F = 2a`, zero at `a = +0.0`: `{a}` released, the step at `α_max = 1`.
    direction, alpha, landing, released = near_pure_tests._step(
        (0.0, 0.5), [[2.0, 0.0], [1.0, 1.0]]
    )
    trial = _trial_point(near_pure_tests.X, direction, alpha, near_pure_tests.LOWER, landing)
    positive_zero = bool(trial[0] == 0.0 and math.copysign(1.0, trial[0]) == 1.0)
    found["i"] = {
        "alpha_max": alpha,
        "released": list(released),
        "landing": list(landing),
        "trial": [float(v) for v in trial],
        "trial_a_is_plus_zero": positive_zero,
    }
    ledger.equal("(c)(i) released", released, (0,))
    ledger.true("(c)(i) α_max > 0", alpha > 0.0)
    ledger.equal("(c)(i) α_max, landing", (alpha, landing), (1.0, ()))
    ledger.true("(c)(i) the column is +0.0 in the trial", positive_zero)
    # (ii) the same with row 0 at `F ≠ 0`: `BOUND_BLOCKED` on `a` (K03 BND-02).
    direction, alpha, blocked, released = near_pure_tests._step(
        (1e-3, 0.5), [[2.0, 0.0], [1.0, 1.0]]
    )
    found["ii"] = {"alpha_max": alpha, "blocked_by": list(blocked), "released": list(released)}
    ledger.equal("(c)(ii) blocked on a", (alpha, blocked, released), (0.0, (0,), ()))
    ledger.true("(c)(ii) the direction unchanged", direction is near_pure_tests.DIRECTION)
    # (iii) `a` not on its bound at the attempt's opening: never released.
    opening = np.array([0.25, 1.0])
    _, alpha, blocked, released = near_pure_tests._step(
        (0.0, 0.5), [[2.0, 0.0], [1.0, 1.0]], opening
    )
    found["iii"] = {"alpha_max": alpha, "blocked_by": list(blocked), "released": list(released)}
    ledger.equal("(c)(iii) not released", (alpha, blocked, released), (0.0, (0,), ()))
    # (iv) fewer closed rows than columns: not released.
    x = np.array([0.0, 0.0])
    _, alpha, blocked, released = near_pure_tests._bound_aware_step(
        x,
        np.array([-1e-30, 0.5]),
        near_pure_tests.LOWER,
        opening=x,
        residual=(0.0, 1.0),
        jacobian=near_pure_tests.sp.csc_matrix(np.array([[1.0, 1.0], [0.0, 1.0]])),
    )
    found["iv"] = {"alpha_max": alpha, "blocked_by": list(blocked), "released": list(released)}
    ledger.equal("(c)(iv) not released", (alpha, blocked, released), (0.0, (0,), ()))
    return found


def _b33() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    restarts = _p4_b33_openings(ledger)
    near_pure = _p4_b33_near_pure(ledger)
    step = _p4_b33_release(ledger)
    # (d) SC-2 under `T05-W13` (and T05 A30's P4, the same revision), reported, never VERIFIED.
    sc2 = contract.solved("SC-2", "v1")
    p4_outcome, p4_status = t05_single.run(t05_single.p4()[0])
    moved = {
        "SC-2 (T05-W13)": {
            "outcome": sc2.run.outcome,
            "verification_status": None
            if sc2.certificate is None
            else sc2.certificate.verification_status,
        },
        "T05 A30 P4": {"outcome": p4_outcome, "verification_status": p4_status or None},
    }
    ledger.equal(
        "(d) SC-2's v1 outcome (regression, W9.5)", sc2.run.outcome, contract.V1_OUTCOME["SC-2"]
    )
    ledger.true(
        "(d) SC-2's v1 run not VERIFIED",
        moved["SC-2 (T05-W13)"]["verification_status"] != "VERIFIED",
    )
    ledger.equal(
        "(d) T05 P4's outcome (regression, W9.5)", p4_outcome, t05_single.MEASURED_OUTCOME["P4"]
    )
    ledger.true("(d) T05 P4 not VERIFIED", p4_status != "VERIFIED")
    value = {
        "a_restart_openings": restarts,
        "b_near_pure_from_the_liquid_form_start": near_pure,
        "c_bound_aware_step": step,
        "d_what_moved": moved,
        "d_identities": "SYN-001's identity, T02's floats, the T02–T04 fixtures and keys and "
        "the t05 key are measured under B21 and B22 (the t05b key as re-registered at W9.4)",
        "departures": ledger.departures,
    }
    expected = {
        "a": "at every such opening of SC-3, DZ-12, CH-UP, CH-DZ12, CH-3, CH-UP/PHF2-first "
        "both products' T equal the closure's T bitwise (and at least one opening each)",
        "b": {
            "outcome": "CONVERGED",
            "verdict": "VERIFIED",
            "within": "§13's EO allowances of ref.near_pure_cases (NP-G: T within 1e-5 K only)",
            "judged": "NP-1, NP-2 degenerate; NP-3 resolved; NP-G unresolved",
            "cause": near_pure_tests.CAUSE,
            "band_item_regression": near_pure_tests.BAND_ITEM,
            "iterations_regression": near_pure_tests.ITERATIONS,
        },
        "c": {
            "i": "released (0,), α_max 1, the column +0.0 in the trial",
            "ii": "BOUND_BLOCKED on a, direction unchanged",
            "iii": "not released, BOUND_BLOCKED on a",
            "iv": "not released, BOUND_BLOCKED on a",
        },
        "d": {
            "SC-2 (T05-W13)": {
                "outcome": contract.V1_OUTCOME["SC-2"],
                "verification_status": "not VERIFIED",
            },
            "T05 A30 P4": {
                "outcome": t05_single.MEASURED_OUTCOME["P4"],
                "verification_status": "not VERIFIED",
            },
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B33"] = (
    "Near-pure feeds restart into two phases: (a) with the test's spy on the contract kernel and "
    "the restart's `_settled`, at every restart opening where a products-style PH-type split "
    "took a PH closure's answer (SC-3, DZ-12, CH-UP, CH-DZ12, CH-3, CH-UP/PHF2-first) both "
    "products' temperatures equal the closure's `T` bitwise; (b) NP-1, NP-2, NP-3, NP-G from "
    "the liquid-form start: `CONVERGED`, `VERIFIED`, flows and `T` within §13's EO allowances "
    "of `ref.near_pure_cases` (NP-G's `T` within 1e-5 K only), NP-1 and NP-2 judged "
    "degenerate, NP-3 resolved, NP-G unresolved, attempt 1 named `U-PHF` `LIQUID->TWO_PHASE`, "
    "the band item and iterations as registered; (c) the bound-aware step's release (i)–(iv) on "
    "the test's two-column problems; (d) SC-2's `T05-W13` outcome and T05 A30's P4 reported "
    "and not `VERIFIED` (the identities are B21's and B22's)."
)
MEASURES["B33"] = _b33


# ------------------------------------------------------------------------------------ B34


def _p4_b34_sweep(ledger: Ledger) -> dict[str, Any]:
    """(a) the registered sweep (`sweep`, `certificates`: the test's caches)."""
    results = candidates.sweep()
    refused = {k: r for k, r in results.items() if isinstance(r, InitialStateFailure)}
    solved = {k: r for k, r in results.items() if isinstance(r, RegionResult)}
    refusals = sorted({(r.unit, r.code.splitlines()[0]) for r in refused.values()})
    ledger.equal("(a) runs", len(results), 120)
    ledger.equal(
        "(a) refused starts: Q2 ≠ 0, Q_s = 0",
        set(refused),
        {key for key in candidates.RUNS if key[0] != 0.0 and key[1] == 0.0},
    )
    ledger.equal("(a) refused starts", len(refused), 16)
    ledger.equal("(a) refusals", refusals, [("U-PHF2", "duty_into_dormant_stream")])
    ledger.equal("(a) solved runs", len(solved), 104)
    untyped = [k for k, r in solved.items() if not (isinstance(r.outcome, str) and r.outcome)]
    ledger.equal("(a) typed outcomes", untyped, [])
    # Both orders: outcome; when CONVERGED, final regimes and final state within the allowances.
    differing: list[Any] = []
    ratios: dict[str, float] = {}
    for triple in sorted({key[:3] for key in candidates.RUNS}):
        first, variant = results[(*triple, False)], results[(*triple, True)]
        if isinstance(first, InitialStateFailure) or isinstance(variant, InitialStateFailure):
            if first != variant:
                differing.append([*triple, "refusal"])
            continue
        if first.outcome != variant.outcome:
            differing.append([*triple, first.outcome, variant.outcome])
            continue
        if first.outcome != "CONVERGED":
            continue
        if candidates._final_regimes(first) != candidates._final_regimes(variant):
            differing.append([*triple, "final regimes"])
        if set(first.state) != set(variant.state):
            differing.append([*triple, "columns"])
            continue
        pair = _p4_state_ratio(variant.state, first.state, candidates._allowance)
        ratios[f"{triple} {pair['where']}"] = pair["ratio"]
    order_ratio = worst(ratios)
    ledger.equal("(a) both orders agree", differing, [])
    ledger.at_most("(a) both orders' states within the allowances", order_ratio["ratio"], 1.0)
    counts_and_tally = _p4_b34_counts(ledger)
    # The tally's structure.
    certified = candidates.certificates()
    ledger.equal("(a) certified = CONVERGED", len(certified), candidates.OUTCOMES["CONVERGED"])
    regularity = dict(
        Counter(
            None if c.regularity is None else c.regularity.status
            for c in certified.values()
            if c.verification_status == "UNVERIFIED"
        )
    )
    ledger.equal(
        "(a) UNVERIFIED regularity (regression)", regularity, candidates.UNVERIFIED_REGULARITY
    )
    failed = {k for k, c in certified.items() if c.verification_status == "FAILED"}
    ledger.equal("(a) the six FAILED", failed, candidates.FAILED)
    undetected = sorted(k for k in failed if not certified[k].false_success_detected)
    ledger.equal("(a) every FAILED a detected false success", undetected, [])
    dew_point = {k for k in certified if k[0] == 0.0 and k[2] in (30_000.0, 90_000.0)}
    verified = {k for k, c in certified.items() if c.verification_status == "VERIFIED"}
    ledger.equal(
        "(a) non-VERIFIED = {Q2 = 0, Q_t ∈ {30, 90} kW}", set(certified) - verified, dew_point
    )
    ledger.equal("(a) no VERIFIED inside that set", sorted(dew_point & verified), [])
    status_differs = sorted(
        triple
        for triple in {key[:3] for key in certified}
        if certified[(*triple, False)].verification_status
        != certified[(*triple, True)].verification_status
    )
    ledger.equal("(a) both orders agree on the status", status_differs, [])
    # The re-registration's statements (spec B34 (a), Q-S15 (1)): (0, 0, 115 kW) converges in
    # both orders at the root the other three 115 kW starts reach, VERIFIED; (0, 0, 90 kW)
    # ends with U-PHF2 VAPOR (a dew-point regression value); the six FAILED end U-PHF2 TWO_PHASE.
    leaving_115: dict[str, Any] = {}
    for first in (False, True):
        key = (0.0, 0.0, 115_000.0, first)
        result = solved[key]
        others = {
            str(source): _p4_state_ratio(
                result.state, solved[(0.0, source, 115_000.0, first)].state, candidates._allowance
            )
            for source in (30_000.0, 90_000.0, 125_000.0)
        }
        leaving_115["U-PHF2 first" if first else "U-PHF first"] = {
            "outcome": result.outcome,
            "final_regimes": sorted(candidates._final_regimes(result)),
            "verification_status": None
            if key not in certified
            else certified[key].verification_status,
            "ratio_to_the_other_115_kW_roots": worst(
                {source: entry["ratio"] for source, entry in others.items()}
            ),
        }
        where = f"(a) (0, 0, 115 kW), {'U-PHF2' if first else 'U-PHF'} first"
        ledger.equal(f"{where}: outcome", result.outcome, "CONVERGED")
        ledger.equal(
            f"{where}: final regimes",
            candidates._final_regimes(result),
            frozenset({("U-PHF", "VAPOR"), ("U-PHF2", "VAPOR")}),
        )
        ledger.equal(
            f"{where}: verdict",
            leaving_115["U-PHF2 first" if first else "U-PHF first"]["verification_status"],
            "VERIFIED",
        )
        ledger.at_most(
            f"{where}: the other 115 kW starts' root",
            max(entry["ratio"] for entry in others.values()),
            1.0,
        )
    leaving_90 = {
        str(first): dict(solved[(0.0, 0.0, 90_000.0, first)].attempts[-1].signature).get("U-PHF2")
        for first in (False, True)
    }
    ledger.equal(
        "(a) (0, 0, 90 kW): U-PHF2's final regime",
        leaving_90,
        dict.fromkeys(("False", "True"), "VAPOR"),
    )
    # The six FAILED: U-PHF2's final regime, and how far each ends off B31's dew-point closed form
    # (CH-UP's at 30 kW: `U-PHF` at DZ-12's root, `S4` its vapour, `S5` 0) — recorded.
    closed = openings.closed_form("CH-UP")
    off: dict[str, Any] = {}
    for key in sorted(failed):
        result = solved[key]
        regime = dict(result.attempts[-1].signature).get("U-PHF2")
        ledger.equal(f"(a) FAILED {key}: U-PHF2's final regime", regime, "TWO_PHASE")
        flows = max(
            float(abs(Decimal(result.state[c]) - Decimal(v)))
            for c, v in closed.items()
            if ".n." in c
        )
        temperature = max(
            float(abs(Decimal(result.state[c]) - Decimal(v)))
            for c, v in closed.items()
            if c.endswith(".T")
        )
        liquid = sum(result.state[f"S5.n.{c}"] for c in "ABC")
        off[str(key)] = {
            "U-PHF2": regime,
            "flow_mol_s": flows,
            "liquid_product_total_mol_s": liquid,
            "T_K": temperature,
        }
    return {
        "runs": len(results),
        "refused": len(refused),
        "refusals": refusals,
        "solved": len(solved),
        "orders_differing": differing,
        "orders_state_ratio": order_ratio,
        **counts_and_tally,
        "unverified_regularity": regularity,
        "failed": sorted(failed),
        "non_verified_equals_dew_point_set": set(certified) - verified == dew_point,
        "status_differs_between_orders": status_differs,
        "leaving_115_kW": leaving_115,
        "leaving_90_kW_U-PHF2_final": leaving_90,
        "failed_off_the_dew_point_root": {
            "runs": off,
            "worst_flow_mol_s": max(e["flow_mol_s"] for e in off.values()) if off else None,
            "worst_liquid_product_total_mol_s": max(
                e["liquid_product_total_mol_s"] for e in off.values()
            )
            if off
            else None,
            "worst_T_K": max(e["T_K"] for e in off.values()) if off else None,
        },
    }


def _p4_b34_candidate(ledger: Ledger) -> dict[str, Any]:
    """(b) at P11's candidate (`p11_candidate`, the test's cache): `U-PHF2`'s kernel asked with
    `S2` bitwise the candidate's; the opening bitwise the same in either listing order; the
    pre-ruling loop raises P11's `RuntimeError` (the control)."""
    caught = candidates.p11_candidate()
    asked: dict[str, dict[str, float]] = {}
    real = caught.ops._answer

    def answer(split: Any, state: Any) -> Any:
        asked[split.unit] = candidates._feed(dict(state))
        return real(split, state)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(caught.ops, "_answer", answer)
        conversion = caught.ops.at_candidate(caught.candidate, caught.cause)
    at = candidates._feed(candidates._candidate_state(caught))
    bitwise = set(asked.get("U-PHF2", {})) == set(at) and all(
        repr(asked["U-PHF2"][name]) == repr(value) for name, value in at.items()
    )
    opened, _ = conversion.opening
    rewritten = candidates._feed(opened) != at
    ledger.equal("(b) both kernels asked", set(asked), {"U-PHF", "U-PHF2"})
    ledger.true("(b) U-PHF2 asked with S2 bitwise the candidate's", bitwise)
    ledger.true("(b) U-PHF's answer rewrites S2", rewritten)
    listed = caught.candidate
    swapped = dataclasses.replace(listed, signature=tuple(reversed(listed.signature)))
    one = caught.ops.at_candidate(listed, caught.cause)
    other = caught.ops.at_candidate(swapped, caught.cause)
    (state_one, regimes_one), (state_other, regimes_other) = one.opening, other.opening
    same = (
        one.signature == other.signature
        and regimes_one == regimes_other
        and list(state_one) == list(state_other)
        and all(repr(state_one[name]) == repr(state_other[name]) for name in state_one)
    )
    ledger.equal(
        "(b) swapped listing", [unit for unit, _ in swapped.signature], ["U-PHF2", "U-PHF"]
    )
    ledger.true("(b) the opening bitwise the same in either listing order", same)
    raised: str | None = None
    try:
        candidates._pre_ruling(caught)
    except RuntimeError as error:
        raised = str(error)
    ledger.true(
        "(b) control: the pre-ruling loop raises P11's RuntimeError",
        raised is not None
        and raised.startswith(
            "defect: the kernel reports U-PHF2 VAPOR at the candidate the screen reported TWO_PHASE"
        ),
    )
    return {
        "candidate_signature": [list(e) for e in listed.signature],
        "regimes_before": dict(caught.ops._regimes),
        "asked": sorted(asked),
        "U-PHF2_asked_at_the_candidate_bitwise": bitwise,
        "S2_rewritten_by_U-PHF": rewritten,
        "opening_order_independent_bitwise": same,
        "control_raised": None if raised is None else _p4_text(raised.splitlines()[0]),
    }


def _b34() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    sweep = _p4_b34_sweep(ledger)
    candidate = _p4_b34_candidate(ledger)
    value = {
        "a_sweep": sweep,
        "b_function_level": candidate,
        "c_on_its_own_commit": {
            "cited": "docs/t05b-measurements.md W10 (W10.2, protocol after every commit) and "
            "Q-S12's measurement (historical); today's identity hashes are measured under B21 "
            "and B22, B07 under B32 (c)",
            "section_present": "## 2026-09-25 — W10:" in MEASUREMENTS.read_text(encoding="utf-8"),
        },
        "departures": ledger.departures,
    }
    expected = {
        "a": {
            "runs": 120,
            "refused": 16,
            "refusals": [["U-PHF2", "duty_into_dormant_stream"]],
            "solved": 104,
            "orders": "same outcome; when CONVERGED same final regimes and state within §13's "
            "EO allowances (ratio at most 1)",
            "outcome_counts": candidates.OUTCOMES,
            "certificate_tally": candidates.TALLY,
            "unverified_regularity": candidates.UNVERIFIED_REGULARITY,
            "failed": sorted(candidates.FAILED),
            "failed_detected": "every FAILED false_success_detected",
            "non_verified": "exactly the CONVERGED runs with Q2 = 0 and Q_t ∈ {30, 90} kW",
            "orders_agree_on_status": True,
            "leaving_115_kW": "CONVERGED both orders, (U-PHF, VAPOR), (U-PHF2, VAPOR), VERIFIED, "
            "at the other three 115 kW starts' root within the allowances (spec B34 (a), "
            "Q-S15 (1): 1.14e-8)",
            "leaving_90_kW_U-PHF2_final": "VAPOR (spec B34 (a), Q-S15 (1))",
            "failed_off_the_dew_point_root": "U-PHF2 TWO_PHASE; the distance from CH-UP's "
            "closed form recorded (spec B34 (a): up to 1.0e-4 mol/s and 0.059 K off the "
            "dew-point root)",
        },
        "b": "U-PHF2 asked at S2 bitwise the candidate's, the opening order-independent "
        "bitwise, the pre-ruling loop raises RuntimeError",
        "c": "historical (cited, not measured here)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B34"] = (
    "Every kernel answer at a phase-rejected candidate is taken at the candidate: (a) the "
    "registered sweep of `tests/test_t05b_candidate_answers.py` (CH-UP's flowsheet, "
    "`Q2 ∈ {0, ±3 kW}`, ordered pairs of `U-PHF` duties in {0, 30, 90, 115, 125} kW, both "
    "declaration orders): 120 runs, the 16 refused starts exactly `Q2 ≠ 0`, `Q_s = 0` "
    "(`duty_into_dormant_stream` at `U-PHF2`), 104 solved without an exception to typed "
    "outcomes, both orders agreeing (outcome, final regimes, state — worst ratio to §13's EO "
    "allowances recorded); the outcome counts 82/10/6/4/2 and the certificate tally 66 "
    "`VERIFIED`, 10 `UNVERIFIED` (6 `RANK_DEFICIENT`, 4 `ILL_CONDITIONED`), 6 `FAILED` against "
    "the test's re-registered pins, the six `FAILED` exactly `(0, {90, 115, 125} kW, 30 kW)` in "
    "both orders, each `false_success_detected`, the non-`VERIFIED` set exactly `Q2 = 0`, "
    "`Q_t ∈ {30, 90} kW`, both orders agreeing on every status; the re-registration's "
    "statements measured ((0, 0, 115 kW) `CONVERGED`, `VAPOR`/`VAPOR`, `VERIFIED` at the other "
    "115 kW starts' root; (0, 0, 90 kW) `U-PHF2` `VAPOR`; the `FAILED` runs' distance from the "
    "dew-point closed form recorded); (b) at P11's candidate the downstream kernel asked with "
    "`S2` bitwise the candidate's, the opening bitwise independent of the listing order, and "
    "the pre-ruling loop raising P11's `RuntimeError`; (c) cited as historical "
    "(`docs/t05b-measurements.md` W10; today's identities are B21's and B22's)."
)
MEASURES["B34"] = _b34


# ------------------------------------------------------------------------------------ B35


def _b35() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    # (a) the affine 3×3 problem of `test_t05b_release_opening.py`.
    default = solve_newton(release.affine(), release.START, release.POLICY, trace=Trace())
    relative = [
        abs(float(default.x[index]) - release.ROOT[index]) / abs(release.ROOT[index])
        for index in (1, 2)
    ]
    explicit = solve_newton(
        release.affine(), release.START, release.POLICY, trace=Trace(), opening=release.START.copy()
    )
    opening = np.array([0.25, 1.0, 1.0])
    blocked = solve_newton(
        release.affine(), release.START, release.POLICY, trace=Trace(), opening=opening
    )
    refused: str | None = None
    try:
        solve_newton(
            release.affine(), release.START, release.POLICY, trace=Trace(), opening=[0.0, 1.0]
        )
    except ValueError as error:
        refused = str(error)
    a_plus_zero = bool(default.x[0] == 0.0 and math.copysign(1.0, float(default.x[0])) == 1.0)
    ledger.equal(
        "(a) without opening=: released", (default.outcome, default.iterations), ("CONVERGED", 1)
    )
    ledger.true("(a) without opening=: a stays +0.0", a_plus_zero)
    for index, error in zip((1, 2), relative, strict=True):
        ledger.at_most(f"(a) x[{index}] relative to the root (the test's rel 1e-14)", error, 1e-14)
    ledger.true(
        "(a) opening= the start: the same call, bitwise",
        explicit.outcome == default.outcome and explicit.x.tobytes() == default.x.tobytes(),
    )
    ledger.equal(
        "(a) opening off the bound: BOUND_BLOCKED on a at iteration 0",
        (blocked.outcome, blocked.iterations, blocked.blocked_by),
        ("BOUND_BLOCKED", 0, ("a",)),
    )
    ledger.true("(a) the iterate unchanged", blocked.x.tobytes() == release.START.tobytes())
    ledger.true(
        "(a) an opening of another length refused",
        refused is not None and "opening has 2 components" in refused,
    )
    # (b) the spy on T04's HOM-01 (`test_b35b_the_corrector_passes_its_attempts_opening`).
    calls: list[tuple[bool, Any]] = []
    openings_x0: list[Any] = []
    inside = {"depth": 0}
    real_homotopy, real_solve = region_module._homotopy, region_module.solve_newton

    def homotopy(**kwargs: Any) -> Any:
        openings_x0.append(np.array(kwargs["x0"], dtype=np.float64, copy=True))
        inside["depth"] += 1
        try:
            return real_homotopy(**kwargs)
        finally:
            inside["depth"] -= 1

    def solve(*args: Any, **kwargs: Any) -> Any:
        calls.append((inside["depth"] > 0, kwargs.get("opening")))
        return real_solve(*args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "_homotopy", homotopy)
        patch.setattr(region_module, "solve_newton", solve)
        run = release.plan_run(release.case_document("HOM-01"), release.case_policy("HOM-01"))
    step = release.region_step(run.result)
    corrector = [opening for inside_homotopy, opening in calls if inside_homotopy]
    others = [opening for inside_homotopy, opening in calls if not inside_homotopy]
    bitwise = len(openings_x0) == 1 and all(
        o is not None and np.asarray(o).tobytes() == openings_x0[0].tobytes() for o in corrector
    )
    ledger.equal(
        "(b) HOM-01: EO recovery taken, CONVERGED",
        (step.eo_recovery, step.outcome),
        ("taken", "CONVERGED"),
    )
    ledger.equal("(b) one homotopy attempt", len(openings_x0), 1)
    ledger.true("(b) corrector calls: at least two", len(corrector) >= 2)
    ledger.true("(b) every corrector call passes x0 bitwise", bitwise)
    ledger.true("(b) every other call passes none", all(o is None for o in others))
    value = {
        "a": {
            "default": {
                "outcome": default.outcome,
                "iterations": default.iterations,
                "a_plus_zero": a_plus_zero,
                "relative_error_b_c": relative,
            },
            "explicit_start_bitwise_equal": explicit.x.tobytes() == default.x.tobytes(),
            "opening_off_bound": {
                "outcome": blocked.outcome,
                "iterations": blocked.iterations,
                "blocked_by": list(blocked.blocked_by),
            },
            "other_length_refused": None if refused is None else _p4_text(refused),
        },
        "b": {
            "eo_recovery": step.eo_recovery,
            "outcome": step.outcome,
            "corrector_calls": len(corrector),
            "corrector_calls_with_x0_bitwise": bitwise,
            "other_calls": len(others),
            "other_calls_passing_none": all(o is None for o in others),
        },
        "c": {
            "cited": "docs/t05b-measurements.md W10.3: the census of every homotopy corrector "
            "call of the suite (424 calls, 99 reaching the release test, 0 non-empty with either "
            "opening, 0 differing) — historical; the registered records are measured across "
            "this manifest (B21, B22, B31, B34)",
            "section_present": "W10.3 (B35). Census" in MEASUREMENTS.read_text(encoding="utf-8"),
        },
        "departures": ledger.departures,
    }
    expected = {
        "a": "without opening= (the call's start) {a} released: CONVERGED in 1 iteration, "
        "a +0.0, b and c the root (0.6875, 1.1875) to rel 1e-14; the start passed explicitly the "
        "same bitwise; opening= with a = 0.25: BOUND_BLOCKED on a at iteration 0 (K03 BND-02)",
        "b": "every corrector solve_newton call passes the attempt's x0 bitwise; every other "
        "call passes none",
        "c": "historical (cited, not measured here)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B35"] = (
    "The release's opening is the attempt's: (a) on the affine 3×3 problem of "
    "`tests/test_t05b_release_opening.py`, `solve_newton` without `opening=` releases `{a}` "
    "(`CONVERGED` in one iteration, `a` `+0.0`, `b`, `c` at the root to rel 1e-14), the start "
    "passed as `opening=` gives the same bits, an `opening=` with `a = 0.25` ends "
    "`BOUND_BLOCKED` on `a` at iteration 0 with the iterate unchanged, and an opening of "
    "another length is refused; (b) with the test's spies on T04's HOM-01, every `solve_newton` "
    "call inside `_homotopy` passes the attempt's `x⁰` bitwise and every other call passes "
    "none; (c) the census is cited (`docs/t05b-measurements.md` W10.3), the records being "
    "measured elsewhere in this manifest."
)
MEASURES["B35"] = _b35


# ------------------------------------------------------------------------------------ B36


def _b36() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    # (a) the leaving flash at CH-UP's restart opening.
    flowsheet, split, _, state, ph_units, temperatures = leaving._ch_up_opening()
    provider = leaving._Recording(flowsheet.provider)
    answer = _contract_kernel(
        provider,  # type: ignore[arg-type]
        flowsheet.context,
        split,
        state,
        ph_units,
        v2=True,
        regime="ZERO_FLOW",
        temperatures=temperatures,
    )
    (asked,) = provider.requests
    written = {
        column: repr(answer.values[column]) == repr(state["S2.T"]) for column in temperatures
    }
    control, _ = _kernel(flowsheet.provider, flowsheet.context, split, state)
    ledger.equal("(a) temperature columns", temperatures, ("S4.T", "S5.T"))
    ledger.equal("(a) asked at S2.n", tuple(asked.n), tuple(state[f"S2.n.{c}"] for c in "ABC"))
    ledger.equal("(a) asked at S2.T", asked.temperature, state["S2.T"])
    ledger.equal("(a) asked at S4.P", asked.pressure, state["S4.P"])
    ledger.equal("(a) answer", (answer.regime, answer.fallback), ("VAPOR", "tp"))
    ledger.true("(a) S4.T, S5.T equal S2.T bitwise", all(written.values()))
    ledger.true("(a) control: the split's own T answers another regime", control != "VAPOR")
    # (b) CH-UP-DP end to end.
    document, start = openings.CASES["CH-UP-DP"]()
    seen: list[tuple[float, float, float, float, float]] = []
    real = region_module._kernel

    def kernel(provider: Any, context: Any, split: Any, state: Any, **kwargs: Any) -> Any:
        if split.unit == "U-PHF2" and kwargs.get("temperature") is not None:
            seen.append(
                (
                    state[split.pressure],
                    state["S2.P"],
                    state["S4.P"],
                    state[kwargs["temperature"]],
                    state["S2.T"],
                )
            )
        return real(provider, context, split, state, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "_kernel", kernel)
        result = openings.solve_from_v2(openings.bind(document), start)
    outlet = 100_000.0 - openings.DP
    ledger.equal("(b) CH-UP-DP outcome", result.outcome, "CONVERGED")
    ledger.true("(b) a leaving flash asked", bool(seen))
    ledger.true(
        "(b) every leaving flash at S4.P = 90 000 Pa, not S2.P, at the feed's T",
        all(p == o == outlet and f != p and t == ft for p, f, o, t, ft in seen),
    )
    # (c), (d) (iii): what moved and nothing else — B31's leaving records and B34 (a)'s counts
    # and tally as re-registered (the same caches as B31 and B34).
    inert = Ledger()
    _p4_b31_records(inert)
    counts = _p4_b34_counts(inert)
    for departure in inert.departures:
        ledger.departures.append(f"(c)/(d)(iii) {departure}")
    # (d) (i) the screen's leaving report, and its control.
    reported = leaving._screened(ph_units)
    pre_ruling = leaving._screened(frozenset())
    ledger.equal(
        "(d)(i) the v2 screen's report", reported, (("U-PHF", "TWO_PHASE"), ("U-PHF2", "VAPOR"))
    )
    ledger.equal("(d)(i) the report is the leaving answer", dict(reported)["U-PHF2"], answer.regime)
    ledger.equal("(d)(i) control: U-PHF reported TWO_PHASE", dict(pre_ruling)["U-PHF"], "TWO_PHASE")
    ledger.true(
        "(d)(i) control: the pre-ruling screen reports another regime",
        dict(pre_ruling)["U-PHF2"] != "VAPOR",
    )
    # (d) (ii) the reported regime stubbed LIQUID raises N4's error; VAPOR opens the answer.
    ops, candidate = leaving._leaving_candidate("LIQUID")
    leaving_split = next(entry for entry in ops._splits if entry.unit == "U-PHF2")
    at = dict(ops._end)
    at.update(zip(ops._free, (float(v) for v in candidate.x), strict=True))
    stub_answer = ops._answer(leaving_split, at)
    raised: str | None = None
    try:
        ops.at_candidate(candidate, "stub")
    except RuntimeError as error:
        raised = str(error)
    ops, matching = leaving._leaving_candidate("VAPOR")
    conversion = ops.at_candidate(matching, "stub")
    ledger.equal(
        "(d)(ii) the leaving answer", (stub_answer.regime, stub_answer.fallback), ("VAPOR", "tp")
    )
    ledger.true(
        "(d)(ii) at_candidate raises N4's RuntimeError",
        raised is not None
        and raised.startswith(
            "defect: the kernel reports U-PHF2 VAPOR at the candidate the screen reported LIQUID"
        ),
    )
    ledger.equal(
        "(d)(ii) control: VAPOR opens VAPOR", dict(conversion.signature)["U-PHF2"], "VAPOR"
    )
    ledger.true("(d)(ii) control: fallback(U-PHF2, tp)", ("U-PHF2", "tp") in conversion.fallbacks)
    value = {
        "a": {
            "asked": {
                "n": list(asked.n),
                "T_K": asked.temperature,
                "P_Pa": asked.pressure,
                "S2.T_K": state["S2.T"],
                "S4.P_Pa": state["S4.P"],
            },
            "answer": [answer.regime, answer.fallback],
            "written_bitwise": written,
            "control_regime_at_the_splits_own_T": control,
        },
        "b": {
            "outcome": result.outcome,
            "leaving_flashes_asked": len(seen),
            "pressures_Pa": sorted({p for p, *_ in seen}),
            "feed_pressures_Pa": sorted({f for _, f, *_ in seen}),
        },
        "c_d_iii": {
            "b31_leaving_records_as_registered": not any(
                d.startswith("CH-") for d in inert.departures
            ),
            **counts,
            "identities": "the t05b, t05 and SYN-001 keys and the T02–T04 fixtures are measured "
            "under B21 and B22; the full gate under B21",
        },
        "d_i": {
            "reported": [list(e) for e in reported],
            "pre_ruling": [list(e) for e in pre_ruling],
        },
        "d_ii": {
            "leaving_answer": [stub_answer.regime, stub_answer.fallback],
            "raised": None if raised is None else _p4_text(raised.splitlines()[0]),
            "control_opened": dict(conversion.signature),
            "control_fallbacks": [list(f) for f in conversion.fallbacks],
        },
        "departures": ledger.departures,
    }
    expected = {
        "a": "the flash at (S2.n, S2.T, S4.P), VAPOR recorded tp, S4.T and S5.T equal S2.T "
        "bitwise; at the split's own T (300 K) a regime other than VAPOR",
        "b": "every leaving flash of U-PHF2 at S4.P = 90 000 Pa (not S2.P), at the feed's T",
        "c_d_iii": {
            "b31_leaving_records_as_registered": True,
            "outcome_counts": candidates.OUTCOMES,
            "certificate_tally": candidates.TALLY,
        },
        "d_i": "the v2 screen reports (U-PHF, TWO_PHASE), (U-PHF2, VAPOR) = the leaving answer; "
        "the pre-ruling screen reports U-PHF2 otherwise",
        "d_ii": "reported LIQUID: RuntimeError 'defect: the kernel reports U-PHF2 VAPOR at the "
        "candidate the screen reported LIQUID'; reported VAPOR: opens VAPOR with "
        "fallback(U-PHF2, tp)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["B36"] = (
    "The leaving TP flash reads the feed: (a) at CH-UP's restart opening with `U-PHF2` leaving "
    "`ZERO_FLOW` and `S4.T = S5.T = 300 K` (`tests/test_t05b_leaving_flash.py`'s construction, "
    "a recording provider), the flash is asked at `(S2.n, S2.T, S4.P)`, answers `VAPOR` "
    "recorded `tp`, and writes `S2.T` to `S4.T`, `S5.T` bitwise; the pre-ruling flash at the "
    "split's own `T` answers another regime; (b) CH-UP-DP end to end: every leaving flash at "
    "`S4.P = 90 000 Pa`, not `S2.P`, at the feed's `T`; (c), (d) (iii) B31's leaving records "
    "and B34 (a)'s counts and tally as re-registered (the same solves as B31, B34; the keys and "
    "the gate are B21's and B22's); (d) (i) the v2 screen reports `U-PHF2` `VAPOR`, the "
    "leaving answer, where the pre-ruling screen does not; (ii) with the reported regime "
    "stubbed `LIQUID`, `at_candidate` raises N4's `RuntimeError`, and reported `VAPOR` opens "
    "`VAPOR` with `fallback(U-PHF2, tp)`."
)
MEASURES["B36"] = _b36


# --------------------------------------------- X01-X08, X11-X18, X20-X26: the verifier's projection


#: K04-F9 §5.5's grammar at a projected state, and the reasons a refusal may carry.
P5_PROJECTED: dict[str, Any] = dict(f9_support.PROJECTED)
P5_REASONS = (
    "residual_not_passed",
    "regularity_RANK_DEFICIENT",
    "regularity_ILL_CONDITIONED",
    "regularity_INCONCLUSIVE",
    "linear_solve_failed",
    "projection_outside_domain",
    "projection_rows_not_passed",
)
#: K04-F9 §7 row 3 and row 1: a fresh-flash value at the projection is ≤ 1e-3 of its threshold.
P5_BOUND = f9_support.PROJECTED_BOUND
#: The registered SYN-001 variants, as K04's tests load them.
P5_VARIANTS: dict[str, Any] = {
    entry["case_id"]: entry
    for entry in yaml.safe_load(
        (ROOT / "benchmarks" / "syn001" / "reference_values.yaml").read_text()
    )["variants"]
}
#: K04's reference (`benchmarks/k04/reference_values.yaml`), as K04's tests load it.
P5_K04_REF: dict[str, Any] = yaml.safe_load(
    (ROOT / "benchmarks" / "k04" / "reference_values.yaml").read_text()
)
#: T04's and T05's references, as their evidence generators load them.
P5_T04_REF: dict[str, Any] = t04m.reference(t04m.REFERENCE)
P5_T05_REF: dict[str, Any] = t05m.reference(t05m.REFERENCE)


def _p5_recorded(package: str) -> dict[str, Any]:
    """The committed evidence manifest of an earlier package, by check id (its one commit)."""
    (path,) = glob.glob(str(ROOT / "evidence" / package / "*" / "manifest.json"))
    document = json.loads((ROOT / path).read_text())
    return {check["id"]: check for check in document["checks"]}


def _p5_text(value: str) -> str:
    """A measured string as recorded: `<` (the manifest's placeholder mark) written `‹`."""
    return value.replace("<", "‹")


def _p5_ratio(check: Any) -> float | None:
    if check is None or check.value is None or not check.tolerance:
        return None
    return float(abs(check.value) / check.tolerance)


def _p5_relative(value: float | None, registered: str) -> float:
    """`|x − ref| / |ref|`, `ref` at its full decimal precision."""
    if value is None:
        return math.inf
    return float(abs(Decimal(value) - Decimal(registered)) / abs(Decimal(registered)))


def _p5_by_id(certificate: Any) -> dict[str, Any]:
    return {check.id: check for check in certificate.checks}


def _p5_failing(certificate: Any) -> list[str]:
    return sorted(check.id for check in certificate.checks if check.result == "fail")


def _p5_flags(certificate: Any) -> list[str]:
    return sorted(check.id for check in certificate.checks if check.near_threshold)


@contextmanager
def _p5_spied(*modules: Any) -> Iterator[list[SolutionCertificate]]:
    """Record every certificate `verify`, `verify_bound` or `verify_revision` issues while the
    block runs, through the certificate module's attributes and the named modules' own imports
    of them (an earlier generator's functions issue their certificates there). The originals
    are called unchanged; the spy only keeps what they return."""
    issued: list[SolutionCertificate] = []
    with pytest.MonkeyPatch.context() as patch:
        for module in (p5_certificate_module, *modules):
            for name in ("verify", "verify_bound", "verify_revision"):
                original = getattr(module, name, None)
                if original is None:
                    continue

                def spy(*args: Any, _original: Any = original, **kwargs: Any) -> Any:
                    certificate = _original(*args, **kwargs)
                    issued.append(certificate)
                    return certificate

                patch.setattr(module, name, spy)
        yield issued


# ---------------------------------------------------------------- the part's cached fixtures


@cache
def _p5_dz_root(case: str) -> tuple[Any, dict[str, Any], dict[str, float], SolutionCertificate]:
    """`test_k04f9_t05b._dz_root`, issued once (its regions are the tests' cached solves)."""
    return f9_t05b._dz_root(case)


def _p5_t05b_certificate(case: str) -> SolutionCertificate:
    """A T05b EO case's certificate as `test_k04f9_t05b._certificate` issues it, once."""
    if case == "NP-GC":
        certificate = f9_t05b._np_gc().certificate
    elif case in f9_t05b.DZ_ROOTS:
        certificate = _p5_dz_root(case)[3]
    else:
        certificate = contract.solved(case).certificate
    assert certificate is not None, case
    return certificate


def _p5_t05b_state(case: str) -> dict[str, float]:
    if case == "NP-GC":
        state = f9_t05b._np_gc().run.state
    elif case in f9_t05b.DZ_ROOTS:
        state = _p5_dz_root(case)[2]
    else:
        state = contract.solved(case).run.state
    assert state is not None, case
    return dict(state)


#: The T05b EO cases K04-F9 X26 (b) records `b` for (`test_k04f9_t05b.SOLUTION_ERROR_BOUNDS`).
P5_T05B_CASES = tuple(f9_t05b.SOLUTION_ERROR_BOUNDS)


@cache
def _p5_judged() -> dict[str, SolutionCertificate]:
    """`test_t05b_verifier.judged` (a module fixture), its body: SC-1's v2 solve claims
    `CONVERGED`, and each of `JUDGED`'s states is judged against that claim."""
    document = verifier_tests.sc1()
    binding = verifier_tests.bind(document)
    plan, _ = plan_revision(binding, support.POLICY_V2)
    assert isinstance(plan, ExecutionPlan), plan
    claim = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=support.POLICY_V2
    )
    assert claim.outcome == "CONVERGED", claim.message
    solve_plan = plan.steps[-1].solve_plan
    return {
        name: verify_revision(
            binding, document, claim, state=verifier_tests._injected(name), solve_plan=solve_plan
        )
        for name in verifier_tests.JUDGED
    }


@cache
def _p5_inj_f10() -> SolutionCertificate:
    flowsheet, result, state = f9_t05b.inj_f10()
    return verify(flowsheet, result, state=state)


@cache
def _p5_inj2() -> tuple[Any, dict[str, float], SolutionCertificate]:
    """K04's INJ-2 (A18) as `test_k04f9_t05b.test_x03_inj_2…` builds it: `(flowsheet, x_final,
    certificate)`."""
    flowsheet, result, base = f9_t05b.solved_syn001(P5_VARIANTS, "SYN-001-once-through")
    state = dict(base)
    for component in "ABC":
        state[f"S3.liq.{component}"] = state[f"S3.n.{component}"]
        state[f"S3.vap.{component}"] = 0.0
    state["S3.L"] = sum(state[f"S3.n.{c}"] for c in "ABC")
    state["S3.V"] = 0.0
    state["U-HEAT.Q"] -= f9_t05b.TRIVIAL_ROOT_OFFSET
    state["U-FLASH.Q"] += f9_t05b.TRIVIAL_ROOT_OFFSET
    return flowsheet, state, verify(flowsheet, result, state=state)


@cache
def _p5_a02_355() -> SolutionCertificate:
    item = t04_certificate.solved_355()
    return verify_bound(item.binding, item.document, item.result, solve_plan=item.solve_plan)


@cache
def _p5_a32() -> dict[float, SolutionCertificate]:
    """T04 A32 at A02-365's root with `U-FLASH.Q + δ` (the test's construction), per `δ`."""
    item = t04_certificate.solved("SYN-001-A02-365")
    issued: dict[float, SolutionCertificate] = {}
    for delta in (2e-3, -2e-3, 5e-4):
        state = dict(item.result.state)
        state["U-FLASH.Q"] += delta
        issued[delta] = verify_bound(item.binding, item.document, item.result, state=state)
    return issued


@cache
def _p5_k04() -> tuple[dict[str, Any], dict[str, SolutionCertificate]]:
    """K04's own measurements (`k04_evidence_manifest`: A15's verdicts, A17/A27/A28's injections
    and twins, A18's trivial root, A16's supplied policies at INJ-3), and the certificates they
    issued, in their order, labelled."""
    with _p5_spied(k04m) as issued:
        measured = {
            "A15": k04m.measure_verdicts(k04m.variants()),
            "A17_A27_A28": k04m.measure_injections(k04m.variants()),
            "A18": k04m.measure_trivial_root(),
            "A16": k04m.measure_relaxation(k04m.variants()),
        }
    labels = [
        *(f"K04 A15 {case}" for case in k04m.CASE_IDS),
        *(
            f"K04 {name} {side}"
            for name in ("INJ-1", "INJ-6", "INJ-7")
            for side in ("above", "twin")
        ),
        "K04 INJ-2",
        *(f"K04 INJ-3 {policy}" for policy in ("registered", "loosened", "tightened")),
    ]
    assert len(issued) == len(labels), (len(issued), len(labels))
    return measured, dict(zip(labels, issued, strict=True))


@cache
def _p5_t05_a22() -> tuple[tuple[bool, Any, Any], list[SolutionCertificate]]:
    """T05 A22 (INJ-T1…T4) by T05's own measurement, and the certificates it issued."""
    with _p5_spied() as issued:
        outcome = t05m._a22(P5_T05_REF)
    return outcome, list(issued)


@cache
def _p5_t05_runs() -> Any:
    return t05m.Runs()


@cache
def _p5_t05_coupled() -> dict[str, tuple[bool, Any, Any]]:
    """T05 A17–A21 by T05's own measurements, on one shared `Runs`."""
    runs = _p5_t05_runs()
    return {
        "A17": t05m._a17(runs, P5_T05_REF),
        "A18": t05m._a18(runs, P5_T05_REF),
        "A19": t05m._a19(runs, P5_T05_REF),
        "A20": t05m._a20(runs, P5_T05_REF),
        "A21": t05m._a21(runs, P5_T05_REF),
    }


@cache
def _p5_t05b_injections() -> dict[str, SolutionCertificate]:
    """T05b B18's INJ-B3 and B29's INJ-B4, INJ-B5 as their tests build them."""
    issued: dict[str, SolutionCertificate] = {}
    dz1 = zero_flow_tests._solved("DZ-1")
    state = dict(support.registered_state(zero_flow_tests.DORMANT["DZ-1"]["root"]))
    state["S2.T"] = 331.0
    issued["INJ-B3"] = verify_revision(
        dz1.binding, dz1.document, dz1.run, state=state, solve_plan=dz1.plan.steps[-1].solve_plan
    )
    dz9 = dormancy._solved("DZ-9", "v1")
    state = dict(support.registered_state(dormancy.CASES["DZ-9"]["root"]))
    state["S3.T"] = 310.0
    issued["INJ-B5"] = verify_revision(
        dz9.binding, dz9.document, dz9.run, state=state, solve_plan=dz9.plan.steps[-1].solve_plan
    )
    with pytest.MonkeyPatch.context() as patch:
        claim = dormancy._without_the_swapped_row_test(patch)
    binding = bind(support.dz11())
    step = p5_planned_step(binding, support.POLICY_V2)
    end_state = support.registered_state(dormancy.DZ11["end_state"])
    issued["INJ-B4"] = verify_revision(
        binding, support.dz11(), claim, state=end_state, solve_plan=step.solve_plan
    )
    return issued


@cache
def _p5_w1d() -> dict[str, Any]:
    """T05 W1.d's three states (`test_t05_w1d_verifier`): the shaped root, its start and the
    shaped trivial root, each with its certificate and the pieces the harness compares."""
    document = shaped_revision()
    binding, plan, run = w1d._solve(document)
    solve_plan = plan.steps[-1].solve_plan
    root_certificate = verify_revision(binding, document, run, solve_plan=solve_plan)
    start = initial_state(binding.flowsheet, binding.spec.variable_ids)
    assert not isinstance(start, InitialStateFailure), start
    start_certificate = verify_revision(binding, document, run, solve_plan=solve_plan, state=start)
    trivial_document = shaped_revision()
    (splitter,) = (i for i in trivial_document["instances"] if i["id"] == "U-SPLIT")
    splitter["parameters"]["split_fraction"]["value"] = 0.0
    (ratio,) = (s for s in trivial_document["specifications"] if s["id"] == "SPEC-splitter-r")
    ratio["value"] = 0.0
    trivial_binding, trivial_plan, trivial_run = w1d._solve(trivial_document)
    assert trivial_run.state is not None
    trivial = dict(trivial_run.state)
    for component in "ABC":
        trivial[f"S3.liq.{component}"] = trivial[f"S3.n.{component}"]
        trivial[f"S3.vap.{component}"] = 0.0
    trivial["S3.L"] = sum(trivial[f"S3.n.{c}"] for c in "ABC")
    trivial["S3.V"] = 0.0
    trivial["U-HEAT.Q"] -= w1d.TRIVIAL_ROOT_OFFSET
    trivial["U-FLASH.Q"] += w1d.TRIVIAL_ROOT_OFFSET
    trivial_certificate = verify_revision(
        trivial_binding,
        trivial_document,
        trivial_run,
        state=trivial,
        solve_plan=trivial_plan.steps[-1].solve_plan,
    )
    return {
        "document": document,
        "binding": binding,
        "run": run,
        "root_certificate": root_certificate,
        "start": start,
        "start_certificate": start_certificate,
        "trivial_document": trivial_document,
        "trivial_binding": trivial_binding,
        "trivial_state": trivial,
        "trivial_certificate": trivial_certificate,
    }


@cache
def _p5_fixtures() -> tuple[dict[str, Any], dict[str, Any], list[SolutionCertificate]]:
    """K04's and T04's schema fixtures as their generators emit them today, and the
    certificates those generators issued."""
    with _p5_spied(k04_schema_fixtures, t04_schema_fixtures) as issued:
        k04_documents = k04_schema_fixtures.documents()
        t04_documents = t04_schema_fixtures.documents()
    return k04_documents, t04_documents, list(issued)


# ------------------------------------------------------------------------------------ X02


def _p5_observed(projection: Any, state: Mapping[str, float]) -> dict[str, Any]:
    """What a projection says, and whether it handed back the certified state itself (every
    category then judged at `x_final`)."""
    return {
        "judged_at": projection.judged_at,
        "reason": projection.reason,
        "state_is_x_final": projection.state is state,
        "document": projection.as_document(),
    }


def _x02() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """`verify.projection.project` driven with `test_k04f9_projection`'s stub declaration (one
    stream of five columns, rows `x_j − c_j`) through that module's own `_project`, `_near`,
    `_target` and `_residual`: each precondition made to fail alone and in combination."""
    p = f9_projection
    ledger = Ledger()
    observed: dict[str, Any] = {}
    columns = len(p.COLUMNS)
    singular = sp.csc_matrix((columns, columns))

    def refusal(name: str, projection: Any, state: Mapping[str, float], reason: str) -> None:
        seen = _p5_observed(projection, state)
        observed[name] = {key: seen[key] for key in ("judged_at", "reason", "state_is_x_final")}
        ledger.equal(
            name,
            [seen["judged_at"], seen["reason"], seen["state_is_x_final"], seen["document"]],
            ["final_state", reason, True, f9_support.refused(reason)],
        )

    # Inside every tolerance: projected onto the linear rows' root, Python floats only.
    state = p._near(S1__n__A=2.0e-8, S1__T=4.0e-7, S1__P=5.0e-3)
    kept = dict(state)
    projection = p._project(state)
    inside = {
        "judged_at": projection.judged_at,
        "reason": projection.reason,
        "state_equals_root": projection.state == p.TARGET,
        "python_floats": all(type(v) is float for v in projection.state.values()),
        "x_final_untouched": state == kept,
    }
    observed["inside_tolerances"] = inside
    ledger.equal(
        "inside tolerances",
        [
            projection.as_document(),
            inside["state_equals_root"],
            inside["python_floats"],
            inside["x_final_untouched"],
        ],
        [P5_PROJECTED, True, True, True],
    )
    # 1: a failing residual names the refusal first, even when 2 and 3 would fail too.
    failing = p._near(S1__n__A=4.0e-8)
    refusal("1 residual (1.3 τ_flow)", p._project(failing), failing, "residual_not_passed")
    refusal(
        "1 before 2 and 3 (RANK_DEFICIENT, singular)",
        p._project(failing, status="RANK_DEFICIENT", matrix=singular),
        failing,
        "residual_not_passed",
    )
    # 2: each regularity status, before the solve.
    passing = p._near(S1__n__A=2.0e-8)
    for status in ("RANK_DEFICIENT", "ILL_CONDITIONED", "INCONCLUSIVE"):
        refusal(f"2 {status}", p._project(passing, status=status), passing, f"regularity_{status}")
        refusal(
            f"2 {status} before 3 (singular)",
            p._project(passing, status=status, matrix=singular),
            passing,
            f"regularity_{status}",
        )
    # 3: a factorization that raises.
    structural = sp.csc_matrix(np.diag([1.0, 1.0, 0.0, 1.0, 1.0]))
    refusal(
        "3 structurally singular factorization",
        p._project(passing, matrix=structural),
        passing,
        "linear_solve_failed",
    )
    # 4: a flow made negative; a flowing T off the domain. A dormant stream's T and a signed
    # extent are not judged by the guard (ADR 0001 D3.1; Q-S5 (2)).
    targets = dict(p.TARGET, **{"S1.n.B": -1.0e-8})
    state = dict(p.TARGET, **{"S1.n.B": 1.0e-9})
    refusal(
        "4 a flow stepped negative",
        p._project(state, target=p._target(targets), scaled=p._residual(state, targets)),
        state,
        "projection_outside_domain",
    )
    targets = dict(p.TARGET, **{"S1.T": 440.0000005})
    state = dict(p.TARGET, **{"S1.T": 440.0})
    refusal(
        "4 a flowing T stepped off [280, 440] K",
        p._project(state, target=p._target(targets), scaled=p._residual(state, targets)),
        state,
        "projection_outside_domain",
    )
    dormant_targets = dict(targets, **{"S1.n.A": 0.0, "S1.n.B": 0.0})
    dormant_state = dict(state, **{"S1.n.A": 0.0, "S1.n.B": 0.0})
    projection = p._project(
        dormant_state,
        target=p._target(dormant_targets),
        scaled=p._residual(dormant_state, dormant_targets),
    )
    observed["4 a dormant stream's T is not judged"] = {
        "judged_at": projection.judged_at,
        "S1.T": projection.state["S1.T"],
    }
    ledger.equal(
        "4 dormant T", [projection.judged_at, projection.state["S1.T"]], ["projection", 440.0000005]
    )
    kinds = dict(p.KINDS, **{"U-RX.xi": "molar_flow"})
    targets = dict(p.TARGET, **{"U-RX.xi": -1.0e-8})
    state = dict(p.TARGET, **{"U-RX.xi": 1.0e-9})
    projection = p._project(
        state,
        target=p._target(targets, kinds=kinds),
        matrix=sp.csc_matrix(np.eye(len(kinds))),
        scaled=np.array([state[name] - targets[name] for name in kinds]),
    )
    extent = projection.state["U-RX.xi"]
    observed["4 a signed extent stepped negative is inside"] = {
        "judged_at": projection.judged_at,
        "extent": extent,
    }
    ledger.equal("4 extent judged at", projection.judged_at, "projection")
    ledger.true(
        "4 extent at its root (1e-12 relative), negative",
        extent < 0.0 and abs(extent + 1.0e-8) <= 1e-12 * 1.0e-8,
    )
    # 5: a row failing at x̃ — a wrong matrix; a row the problem cannot evaluate; a label row.
    wrong = sp.csc_matrix(np.eye(columns) * 0.1)
    refusal(
        "5 a step after which a row fails",
        p._project(passing, matrix=wrong),
        passing,
        "projection_rows_not_passed",
    )
    target = p._target()
    residual = p._rows(target, passing)
    target.compiled.status = "domain_error"
    refusal(
        "5 a row not evaluable at x̃",
        p._project(passing, target=target, residual=residual),
        passing,
        "projection_rows_not_passed",
    )
    label = p.ZeroFlowSplit(unit="U", columns=(), rows=(), label=("U:label", "S1.T", "S1.P"))
    refusal(
        "5 a failing label row at x̃",
        p._project(passing, residual=p._rows(p._target(), passing), zero_flow=(label,)),
        passing,
        "projection_rows_not_passed",
    )
    # The matrix must be the screened one.
    raised: str | None = None
    try:
        p._project(passing, matrix=sp.csc_matrix(np.eye(columns - 1)))
    except RuntimeError as error:
        raised = _p5_text(str(error).splitlines()[0])
    observed["a matrix that is not the screened one"] = {"raises_RuntimeError": raised}
    ledger.true(
        "a matrix of other columns raises",
        raised is not None and "not the screened matrix" in raised,
    )
    value = {"cases": observed, "departures": ledger.departures}
    expected = {
        "inside_tolerances": "projection, reason '', x̃ the rows' root, Python floats, x_final "
        "untouched",
        "refusals": "judged_at final_state, the first failing precondition's code in §5.1's order "
        "(residual_not_passed, regularity_STATUS, linear_solve_failed, projection_outside_domain, "
        "projection_rows_not_passed), the certified state itself handed back",
        "inside the domain": "a dormant stream's T and a signed extent are not judged by guard 4",
        "matrix": "RuntimeError: not the screened matrix",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X02"] = (
    "Each refusal code at a constructed state of the projection function "
    "(`verify/projection.project`, driven through `test_k04f9_projection`'s stub declaration: "
    "one stream of five columns, rows `x_j − c_j`): inside every tolerance it projects onto the "
    "root in Python floats; a failing residual → `residual_not_passed` (also when the status is "
    "`RANK_DEFICIENT` and the matrix singular); each non-`NO_RANK_LOSS_DETECTED` status → "
    "`regularity_STATUS` (also with a singular matrix); a structurally singular factorization "
    "→ `linear_solve_failed`; a flow stepped negative or a flowing `T` stepped off `[280, 440] "
    "K` → `projection_outside_domain` (a signed reaction extent and a dormant stream's `T` are "
    "not, Q-S5 (2)); a wrong matrix, a row the problem cannot evaluate, or a failing label row "
    "at `x̃` → `projection_rows_not_passed`; each refusal hands back `x_final` itself with §5.5's "
    "document; a matrix of other columns raises `RuntimeError`."
)
MEASURES["X02"] = _x02


# ------------------------------------------------------------------------------------ X03


def _p5_zeros(
    kinds: Mapping[str, str], state: Mapping[str, float], projection: Any
) -> dict[str, Any]:
    """X03's observation: every molar-flow column exactly zero at `x_final`, and those not
    `+0.0` at `x̃`; the largest discarded step component."""
    zeros = [c for c, v in state.items() if kinds.get(c) == "molar_flow" and v == 0.0]
    moved = [
        [c, projection.state[c]]
        for c in zeros
        if projection.state[c] != 0.0 or math.copysign(1.0, projection.state[c]) < 0.0
    ]
    return {
        "judged_at": projection.judged_at,
        "zero_flow_columns": len(zeros),
        "not_plus_zero_at_projection": moved,
        "discarded_mol_per_s": projection.discarded,
    }


def _x03() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    per_state: dict[str, Any] = {}

    def judge(name: str, certificate: Any, observed: dict[str, Any], ids_equal: bool) -> None:
        observed["certificate_judged_at"] = certificate.transformations["projection"]["judged_at"]
        observed["projected_category_ids_equal_unprojected"] = ids_equal
        per_state[name] = observed
        ledger.equal(f"{name} judged at", observed["judged_at"], "projection")
        ledger.equal(
            f"{name} certificate judged at", observed["certificate_judged_at"], "projection"
        )
        ledger.equal(f"{name} zeros moved", observed["not_plus_zero_at_projection"], [])
        ledger.at_most(f"{name} discarded", observed["discarded_mol_per_s"], f9_t05b.DISCARD_BOUND)
        ledger.true(f"{name} ids", ids_equal)

    flowsheet, state, certificate = _p5_inj2()
    projection = f9_t05b._legacy_projection(flowsheet, state)
    kinds = Syn001TearProblem(flowsheet).spec.variable_kinds
    unprojected, _ = run_checks(flowsheet, state)
    observed = _p5_zeros(kinds, state, projection)
    ledger.true("INJ-2 at least S3.vap.{A,B,C}, S3.V", observed["zero_flow_columns"] >= 4)
    observed["bubble_id_kept"] = "phase_admissibility.S3.bubble" in _p5_by_id(certificate)
    ledger.true("INJ-2 .bubble kept", observed["bubble_id_kept"])
    judge(
        "INJ-2",
        certificate,
        observed,
        f9_t05b._projected_ids(certificate.checks) == f9_t05b._projected_ids(unprojected),
    )
    for case in ("SC-1", *f9_t05b.DZ_ROOTS):
        if case == "SC-1":
            solved = contract.solved("SC-1")
            binding, document = solved.binding, solved.document
            state = _p5_t05b_state(case)
        else:
            binding, document, state, _ = _p5_dz_root(case)
        certificate = _p5_t05b_certificate(case)
        projection, unprojected_table = support.revision_projection(binding, document, state)
        observed = _p5_zeros(binding.spec.variable_kinds, state, projection)
        observed["verification_status"] = certificate.verification_status
        ledger.equal(f"{case} status", certificate.verification_status, "VERIFIED")
        judge(
            case,
            certificate,
            observed,
            f9_t05b._projected_ids(certificate.checks) == f9_t05b._projected_ids(unprojected_table),
        )
    discarded = [entry["discarded_mol_per_s"] for entry in per_state.values()]
    value = {
        "states": per_state,
        "largest_discarded_mol_per_s": max(discarded),
        "departures": ledger.departures,
    }
    expected = {
        "each": "judged at the projection; every molar-flow column exactly +0.0 at x_final is "
        "+0.0 at x̃; the fresh-flash category ids equal the unprojected ones",
        "discarded_mol_per_s": f"at most {f9_t05b.DISCARD_BOUND:g} (spec §7)",
        "INJ-2": "phase_admissibility.S3.bubble kept (never .closure); at least 4 exact zeros",
        "SC-1 and the DZ roots": "VERIFIED",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X03"] = (
    "Exact zeros at the certificate path's projection (`certificate._project`, through "
    "`test_k04f9_t05b._legacy_projection` for SYN-001 and `t05b_support.revision_projection` "
    "for revisions): at K04's INJ-2 (`S3.vap = 0`, `S3.V = 0`), SC-1 and each DZ root (DZ-1…"
    "DZ-10, DZ-12), the projection is taken, every molar-flow column exactly `+0.0` at "
    "`x_final` is `+0.0` at `x̃` (sign included), the largest discarded step component is "
    "`≤ 1e-20 mol/s`, and the certificate's fresh-flash category ids equal the unprojected "
    "check set's (INJ-2 keeps `phase_admissibility.S3.bubble`)."
)
MEASURES["X03"] = _x03


# ------------------------------------------------------------------------------- X04, X25


def _p5_family_key(member: Any) -> str:
    return f"{member.target} K from {member.guess:g} K"


def _x04() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """The A02 family as `test_k04f9_family.family()` scans and certifies it (cached; its S3
    ratios at `x_final` through the unprojected check functions)."""
    family = F9_REF["closed_form"]["a02_family_projection"]
    ledger = Ledger()
    members, elapsed = f9_family.family()
    converged = [m for m in members if m.certificate is not None]
    ledger.equal("runs", len(members), int(family["runs"]))
    ledger.equal("converged", len(converged), int(family["converged"]))
    not_verified = [
        [_p5_family_key(m), m.certificate.verification_status]
        for m in converged
        if m.certificate.verification_status != "VERIFIED"
    ]
    not_projected = [
        [_p5_family_key(m), m.certificate.transformations["projection"]]
        for m in converged
        if m.certificate.transformations["projection"] != P5_PROJECTED
    ]
    ledger.equal("converged states not VERIFIED", not_verified, [])
    ledger.equal("converged states not judged at the projection", not_projected, [])
    by_key = {(m.target, m.guess): m for m in converged}
    exposed = f9_family.EXPOSED
    ledger.equal("exposed states registered", len(exposed), 24)
    ledger.true("every exposed state converged", set(exposed) <= set(by_key))
    projected: dict[str, float] = {}
    raw: dict[str, float] = {}
    for key in exposed:
        member = by_key[key]
        name = _p5_family_key(member)
        ratios = f9_support.s3_ratios(member.certificate.checks)
        ledger.true(f"{name}: S3 checks present", bool(ratios))
        projected[name] = max(ratios.values()) if ratios else math.inf
        raw[name] = max(member.raw.values())
        ledger.at_most(
            f"{name}: largest S3 value at x̃ over its threshold", projected[name], P5_BOUND
        )
        ledger.true(f"{name}: raw largest {raw[name]:.3g} at least 0.1", raw[name] >= 0.1)
    others = {
        _p5_family_key(m): max(m.raw.values()) for key, m in by_key.items() if key not in exposed
    }
    for name, ratio in others.items():
        ledger.true(f"{name}: not exposed, raw {ratio:.3g} below 0.1", ratio < 0.1)
    flagged = {
        _p5_family_key(m): [c for c in m.certificate.checks if c.near_threshold]
        for m in converged
        if any(c.near_threshold for c in m.certificate.checks)
    }
    off_residual = [
        [name, c.id] for name, flags in flagged.items() for c in flags if c.category != "residual"
    ]
    counts = [len(flagged), sum(len(flags) for flags in flagged.values())]
    ledger.equal("flags off the residual category", off_residual, [])
    ledger.equal(
        "flagged states, flags (regression)",
        counts,
        [f9_family.FLAGGED_STATES, f9_family.FLAGS],
    )
    value = {
        "runs": len(members),
        "converged": len(converged),
        "outcomes_not_converged": sorted({m.outcome for m in members if m.certificate is None}),
        "not_verified": not_verified,
        "not_judged_at_projection": not_projected,
        "exposed_projected_S3_over_threshold": worst(projected),
        "exposed_raw_S3_over_threshold_smallest": min(raw.values()),
        "not_exposed_raw_S3_over_threshold_largest": worst(others),
        "flagged_states": counts[0],
        "flags": counts[1],
        "flags_off_residual": off_residual,
        "family_certification_seconds": round(elapsed, 1),
        "departures": ledger.departures,
    }
    expected = {
        "runs": int(family["runs"]),
        "converged": int(family["converged"]),
        "each_converged": "VERIFIED, transformations.projection judged_at projection",
        "exposed_projected_S3_over_threshold": f"at most {P5_BOUND:g} at each of the 24 exposed "
        "states (ref…exposed_states, by (T_target, guess)); raw at x_final at least 0.1 there, "
        "below 0.1 elsewhere",
        "flags": "every near_threshold flag on a residual check; 15 states, 29 flags "
        "(regression pins of test_k04f9_family)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X04"] = (
    "The A02 family (T04 A11's 10 targets × 18 guesses under the default policy, "
    "`test_k04f9_family.family()`): the run count and the 179 converged, each certificate "
    "(`verify_bound` on its bound declaration with its region plan) `VERIFIED` with "
    "`transformations.projection` judged at the projection; at each of `ref…exposed_states`' 24 "
    "states (by `(T_target, guess)`) the largest S3 check (`independent_split.S3.*`, "
    "`energy_balance.heater`, `energy_balance.flash`) over its tolerance at `x̃` `≤ 1e-3` (the "
    "raw value at `x_final`, through the unprojected check functions, `≥ 0.1` there and below 0.1 "
    "at every other state); every `near_threshold` flag on a `residual` check, 15 states and 29 "
    "flags (regression pins)."
)
MEASURES["X04"] = _x04


def _x25() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    members, _ = f9_family.family()
    by_key = {(m.target, m.guess): m for m in members if m.certificate is not None}
    per_state: dict[str, Any] = {}
    ratios: dict[str, float] = {}
    for key, entry in f9_family.EXPOSED.items():
        member = by_key[key]
        name = _p5_family_key(member)
        got = max(f9_support.s3_ratios(member.certificate.checks).values())
        registered = str(entry["projected_largest_over_threshold"])
        reference = float(Decimal(registered))
        allowance = max(0.05 * reference, 1e-5)
        error = support.error(got, registered)
        per_state[name] = {
            "measured": got,
            "twin": registered,
            "error": error,
            "allowance": allowance,
        }
        ratios[name] = error / allowance
        ledger.within(name, got, registered, allowance)
    value = {
        "states": per_state,
        "worst_error_over_allowance": worst(ratios),
        "departures": ledger.departures,
    }
    expected = {
        "each": "the largest S3 value over its threshold at x̃ within max(0.05 · ref, 1e-5) of "
        "ref…exposed_states.projected_largest_over_threshold (spec §7 row 2)",
        "states": 24,
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X25"] = (
    "The implementation's projection is the specified map: at each of the 24 exposed family "
    "states (`test_k04f9_family.family()`'s certificates) the largest S3 value over its "
    "threshold at `x̃` against the twin's 40-digit `ref…exposed_states."
    "projected_largest_over_threshold`, to `max(0.05 · ref, 1e-5)`; the error over that "
    "allowance recorded per state and at worst."
)
MEASURES["X25"] = _x25


# ------------------------------------------------------------------------------- X05, X06


def _x05() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """T02's A02-355 from 358 K (`test_t04_certificate.solved_355`), certified by
    `verify_bound`; F9's evidence through `test_t04_certificate._unprojected` at `x_final`."""
    registered = t04_certificate.BOUND["finding_F9"]
    twin = F9_REF["closed_form"]["t02_states_from_358K"]["SYN-001-A02-355"]
    ledger = Ledger()
    item = t04_certificate.solved_355()
    (attempt,) = item.result.attempts
    certificate = _p5_a02_355()
    ledger.equal("iterations", attempt.iterations, 3)
    ledger.equal(
        "signature", dict(attempt.signature), {"U-HEAT": "TWO_PHASE", "U-FLASH": "TWO_PHASE"}
    )
    ledger.equal(
        "verdict",
        [certificate.verification_status, certificate.false_success_detected],
        ["VERIFIED", False],
    )
    flags = _p5_flags(certificate)
    failing = _p5_failing(certificate)
    ledger.equal("near_threshold anywhere", flags, [])
    ledger.equal("failing anywhere", failing, [])
    ledger.equal("projection", certificate.transformations["projection"], P5_PROJECTED)
    projected = f9_support.s3_ratios(certificate.checks)
    ledger.true("S3 checks present", bool(projected))
    largest = max(projected.values())
    ledger.at_most("largest S3 value at x̃ over its threshold", largest, P5_BOUND)
    residuals = [c for c in certificate.checks if c.category == "residual"]
    worst_row = max(residuals, key=lambda c: abs(c.value) / c.tolerance)
    worst_ratio = abs(worst_row.value) / worst_row.tolerance
    ledger.equal("worst row", worst_row.subject, registered["worst_row"])
    ledger.within(
        "worst row over tolerance",
        worst_ratio,
        registered["worst_row_over_tolerance"],
        1e-5 * float(registered["worst_row_over_tolerance"]),
    )
    raw = t04_certificate.by_id_list(t04_certificate._unprojected(item))
    evidence: dict[str, Any] = {}
    for name, key, sign in (
        ("independent_split.S3.total", "independent_split_S3_total_mol_per_s", 1.0),
        ("energy_balance.heater", "energy_heater_W", 1.0),
        ("energy_balance.flash", "energy_heater_W", -1.0),
    ):
        target = sign * float(registered[key])
        check = raw[name]
        evidence[name] = {
            "value_at_x_final": check.value,
            "registered": target,
            "relative_error": abs(check.value - target) / abs(target),
            "near_threshold": check.near_threshold,
        }
        ledger.true(
            f"{name} at x_final within 1e-5 relative of T04's finding_F9",
            abs(check.value - target) <= 1e-5 * abs(target),
        )
        ledger.equal(f"{name} near_threshold at x_final", check.near_threshold, True)
    raw_s3 = f9_support.s3_ratios(t04_certificate._unprojected(item))
    value = {
        "verdict": [certificate.verification_status, certificate.false_success_detected],
        "projection": certificate.transformations["projection"],
        "near_threshold": flags,
        "failing": failing,
        "largest_S3_over_threshold_at_projection": largest,
        "twin_projected_largest_over_threshold": twin["projected_largest_over_threshold"],
        "largest_S3_over_threshold_at_x_final": max(raw_s3.values()),
        "twin_raw_largest_over_threshold": twin["raw_largest_over_threshold"],
        "worst_row": [worst_row.subject, worst_ratio],
        "finding_F9_at_x_final": evidence,
        "departures": ledger.departures,
    }
    expected = {
        "verdict": ["VERIFIED", False],
        "projection": P5_PROJECTED,
        "near_threshold": [],
        "largest_S3_over_threshold_at_projection": f"at most {P5_BOUND:g}",
        "worst_row": [registered["worst_row"], registered["worst_row_over_tolerance"]],
        "finding_F9_at_x_final": "independent_split.S3.total, energy_balance.heater, "
        "energy_balance.flash (−heater) equal T04's ref.bound.finding_F9 to 1e-5 relative, each "
        "near_threshold",
        "twin values": "recorded beside the measured ones, not thresholded (X05 states none)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X05"] = (
    "T04 A33 as amended: T02's `SYN-001-A02-355` solved from 358 K by the region Newton (one "
    "`TWO_PHASE` attempt, 3 iterations) and certified by `verify_bound`: `VERIFIED`, no "
    "`near_threshold` flag and no failure anywhere, judged at the projection; the largest S3 "
    "value over its threshold at `x̃` `≤ 1e-3`; the worst row `U-HEAT:HEAT-equilibrium:A` at "
    "T04's 0.0813 τ to 1e-5 relative; F9's evidence kept at `x_final` through K04 §4.4/§4.7's "
    "unprojected check functions (`checks.energy_checks`, `checks.admissibility_checks`): "
    "`independent_split.S3.total`, `energy_balance.heater`, `energy_balance.flash` equal T04's "
    "`ref.bound.finding_F9` to 1e-5 relative and `near_threshold` there; the twin's raw and "
    "projected largest values recorded beside the measured ones."
)
MEASURES["X05"] = _x05


def _x06() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """T04 A32 at A02-365's root (`test_t04_certificate.solved`), `U-FLASH.Q + δ` injected and
    judged by `verify_bound` with `state=`; the test's sets `FIVE`, `AT_FINAL_STATE`,
    `BALANCES`."""
    ledger = Ledger()
    five = sorted(t04_certificate.FIVE)
    at_final = sorted(t04_certificate.AT_FINAL_STATE)
    per_delta: dict[str, Any] = {}
    for delta, certificate in _p5_a32().items():
        checks = _p5_by_id(certificate)
        failed = delta != 5e-4
        read = five if failed else at_final
        record: dict[str, Any] = {
            "verdict": [certificate.verification_status, certificate.false_success_detected],
            "failing": _p5_failing(certificate),
            "near_threshold": _p5_flags(certificate),
            "projection": certificate.transformations["projection"],
            "values_minus_delta_W": {name: checks[name].value - delta for name in read},
        }
        where = f"δ = {delta:+g} W"
        ledger.equal(
            where,
            [record["verdict"], record["failing"], record["near_threshold"], record["projection"]],
            [
                ["FAILED", True] if failed else ["VERIFIED", False],
                five if failed else [],
                five if failed else at_final,
                f9_support.refused("residual_not_passed") if failed else P5_PROJECTED,
            ],
        )
        for name, offset in record["values_minus_delta_W"].items():
            ledger.at_most(f"{where}: {name} − δ", abs(offset), 1e-7)
        if not failed:
            balances: dict[str, Any] = {}
            for name in sorted(t04_certificate.BALANCES):
                check = checks[name]
                balances[name] = {
                    "value_W": check.value,
                    "over_tau_E": abs(check.value) / check.tolerance,
                    "result": check.result,
                    "near_threshold": check.near_threshold,
                }
                ledger.equal(
                    f"{where}: {name} result, flag",
                    [check.result, check.near_threshold],
                    ["pass", False],
                )
                ledger.at_most(
                    f"{where}: {name} over τ_E", abs(check.value) / check.tolerance, P5_BOUND
                )
            record["balances_at_projection"] = balances
        per_delta[where] = record
    value = {"deltas": per_delta, "departures": ledger.departures}
    expected = {
        "±2e-3 W": {
            "verdict": ["FAILED", True],
            "failing": five,
            "near_threshold": five,
            "projection": f9_support.refused("residual_not_passed"),
            "values": "each ±δ within 1e-7 W",
        },
        "5e-4 W": {
            "verdict": ["VERIFIED", False],
            "near_threshold": at_final,
            "projection": P5_PROJECTED,
            "values": "the three x_final checks δ within 1e-7 W; energy_balance.flash and "
            "energy_balance.envelope pass, unflagged, at most 1e-3 τ_E (spec: measured −2.5e-10 "
            "W, −7.3e-12 W)",
        },
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X06"] = (
    "T04 A32 as amended: at `SYN-001-A02-365`'s root with `U-FLASH.Q + δ` injected "
    "(`verify_bound(..., state=)`): `δ = ±2e-3 W` → `FAILED` with `false_success_detected`, "
    "failing and flagged exactly the five checks that read the flash duty, each by `±δ` to "
    "1e-7 W, judged at `x_final` (`residual_not_passed`); `δ = 5e-4 W` → `VERIFIED`, judged at "
    "the projection, `near_threshold` exactly on `{residual.SPEC:SPEC-flash-duty, "
    "residual.U-FLASH:FLASH-duty, specification.U-FLASH.Q}` (each δ to 1e-7 W), and "
    "`energy_balance.flash`, `energy_balance.envelope` passing, unflagged, `≤ 1e-3 τ_E`."
)
MEASURES["X06"] = _x06


# ------------------------------------------------------------------------------- X07, X08


def _p5_dormant_verified(
    case: str, label: str, dimension: int, rcond: float | None, flags_pin: Mapping[str, float]
) -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """B16 / B26 as amended: the DZ root's v2 certificate (`test_k04f9_t05b._dz_root`)."""
    ledger = Ledger()
    certificate = _p5_t05b_certificate(case)
    by_id = _p5_by_id(certificate)
    ledger.equal("status", certificate.verification_status, "VERIFIED")
    ledger.equal("projection", certificate.transformations["projection"], P5_PROJECTED)
    ratios = support.fresh_flash_ratios(certificate.checks)
    ledger.true("fresh-flash values present", bool(ratios))
    largest = worst(ratios)
    ledger.at_most("largest fresh-flash value over its tolerance", largest["ratio"], P5_BOUND)
    ledger.equal(f"{label} result", by_id[label].result, "pass")
    residual_not_pass = [
        c.id for c in certificate.checks if c.category == "residual" and c.result != "pass"
    ]
    ledger.equal("residuals not passing", residual_not_pass, [])
    regularity = certificate.regularity
    screen = [regularity.status, regularity.dimension, regularity.rcond_1]
    ledger.equal("regularity status", regularity.status, "NO_RANK_LOSS_DETECTED")
    ledger.equal("regularity dimension", regularity.dimension, dimension)
    if rcond is not None:
        ledger.at_most(
            "rcond_1 against its regression pin (5e-7)", abs(regularity.rcond_1 - rcond), 5e-7
        )
    flags = _p5_flags(certificate)
    equilibrium = [f"residual.U-PHF:PHF-equilibrium:{c}" for c in "ABC"]
    ledger.equal("near_threshold", flags, equilibrium)
    flag_ratios = {}
    for component, pin in flags_pin.items():
        ratio = _p5_ratio(by_id[f"residual.U-PHF:PHF-equilibrium:{component}"])
        flag_ratios[component] = ratio
        ledger.at_most(
            f"PHF-equilibrium:{component} against its pin {pin} (5e-4)",
            None if ratio is None else abs(ratio - pin),
            5e-4,
        )
    value = {
        "verification_status": certificate.verification_status,
        "projection": certificate.transformations["projection"],
        "largest_fresh_flash_over_tolerance": largest,
        "label_row": [label, by_id[label].result, by_id[label].value],
        "residuals_not_passing": residual_not_pass,
        "regularity": screen,
        "near_threshold": flags,
        "equilibrium_over_tau_eq": flag_ratios,
        "departures": ledger.departures,
    }
    expected = {
        "verification_status": "VERIFIED",
        "projection": P5_PROJECTED,
        "largest_fresh_flash_over_tolerance": f"at most {P5_BOUND:g}",
        "label_row": "pass",
        "regularity": ["NO_RANK_LOSS_DETECTED", dimension, rcond],
        "near_threshold": equilibrium,
        "equilibrium_over_tau_eq": dict(flags_pin),
        "tolerances": "rcond_1 to 5e-7, the flags' ratios to 5e-4 (the tests' regression pins)",
    }
    return ledger.ok, value, expected


def _p5_xfail_markers(function: Callable[..., Any]) -> list[str]:
    return [mark.name for mark in getattr(function, "pytestmark", []) if mark.name == "xfail"]


def _x07() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    dimension, rcond = zero_flow_tests.DZ3_SCREEN
    ok, value, expected = _p5_dormant_verified(
        "DZ-3",
        "residual.U-VLV:zero-flow-label",
        dimension,
        rcond,
        zero_flow_tests.DZ3_EQUILIBRIUM_FLAGS,
    )
    markers = _p5_xfail_markers(zero_flow_tests.test_b16_dz3_verified)
    value["xfail_markers_on_the_gate_test"] = markers
    expected["xfail_markers_on_the_gate_test"] = []
    return ok and markers == [], value, expected


DESCRIPTIONS["X07"] = (
    "T05b B16 as amended: DZ-3's v2 root (the registered perturbed start, the test's cached "
    "region; `verify_revision` with its plan) — `VERIFIED`, judged at the projection; every "
    "fresh-flash value (`t05b_support.fresh_flash_ratios`) `≤ 1e-3` of its tolerance; the label "
    "row `residual.U-VLV:zero-flow-label` and every residual pass; the screen "
    "`NO_RANK_LOSS_DETECTED` at dimension 33, `rcond₁` 0.013055 (regression, to 5e-7); "
    "`near_threshold` exactly on `residual.U-PHF:PHF-equilibrium:{A,B,C}` at 0.173, 0.197, "
    "0.119 τ_eq (regression, to 5e-4); the gate's test carries no xfail marker."
)
MEASURES["X07"] = _x07


def _x08() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    dimension = int(dormancy.DZ10["zero_flow_form"]["dimension"])
    ok, value, expected = _p5_dormant_verified(
        "DZ-10",
        "residual.U-PUMP:zero-flow-label",
        dimension,
        None,
        dormancy.DZ10_EQUILIBRIUM_FLAGS,
    )
    markers = _p5_xfail_markers(dormancy.test_b26_dz10_verified)
    value["xfail_markers_on_the_gate_test"] = markers
    expected["xfail_markers_on_the_gate_test"] = []
    ok = ok and dimension == 34 and markers == []
    return ok, value, expected


DESCRIPTIONS["X08"] = (
    "T05b B26 as amended: DZ-10's v2 root, as X07 — `VERIFIED` at the projection, every "
    "fresh-flash value `≤ 1e-3` of its tolerance, the dormancy form's label row "
    "`residual.U-PUMP:zero-flow-label` and every residual pass, the screen at dimension 34 "
    "(`rcond₁` recorded; no pin is registered for it), `near_threshold` exactly on the PH "
    "flash's three equilibrium rows at 0.173, 0.197, 0.119 τ_eq (regression, to 5e-4); the "
    "gate's test carries no xfail marker."
)
MEASURES["X08"] = _x08


# ------------------------------------------------------------------------------------ X11


def _x11() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """NP-GC (`t05b_support.np_gc`) solved under v2 by `test_k04f9_t05b._np_gc` (cached)."""
    ledger = Ledger()
    solved = f9_t05b._np_gc()
    certificate = solved.certificate
    ledger.equal("outcome", solved.run.outcome, "CONVERGED")
    assert certificate is not None, solved.run.message
    checks = _p5_by_id(certificate)
    ledger.equal("status", certificate.verification_status, "VERIFIED")
    ledger.equal("projection", certificate.transformations["projection"], P5_PROJECTED)
    split = checks["independent_split.U-PHF.S1"]
    ledger.equal(
        "independent_split.U-PHF.S1",
        [split.result, split.reason],
        ["not_applicable", "fresh_flash_unresolved"],
    )
    sub_ids = sorted(name for name in checks if name.startswith("independent_split.U-PHF.S1."))
    ledger.equal("independent_split.U-PHF.S1.* present", sub_ids, [])
    saturation = "phase_admissibility.U-PHF.S1.saturation" in checks
    ledger.equal(".saturation present", saturation, False)
    closure = checks["phase_admissibility.U-PHF.S1.closure"]
    ledger.equal("closure", closure.result, "pass")
    balances: dict[str, Any] = {}
    for name in ("energy_balance.U-PHF", "energy_balance.U-SPLIT", "energy_balance.envelope"):
        check = checks[name]
        balances[name] = {"value_W": check.value, "over_tau_E": _p5_ratio(check)}
        ledger.at_most(f"{name} over τ_E", _p5_ratio(check), P5_BOUND)
    note = checks["energy_balance.U-PHF"].independence_qualification or ""
    notes = {
        stream: support_note in note
        for stream, support_note in (
            (s, f9_t05b.UNRESOLVED_ENTHALPY_NOTE.format(stream=s)) for s in ("S2", "S3")
        )
    }
    ledger.equal("D3 note on energy_balance.U-PHF for S2, S3", notes, {"S2": True, "S3": True})
    failing_rows = [
        c.id for c in certificate.checks if c.category == "residual" and c.result == "fail"
    ]
    ledger.equal("failing residuals", failing_rows, [])
    unsupported = [c.id for c in certificate.checks if c.result == "unsupported"]
    ledger.equal("unsupported checks", unsupported, [])
    state = solved.run.state
    case = F9_REF["closed_form"]["cases"]["NP-GC"]
    copies: dict[str, float] = {}
    for stream in ("S4", "S5"):
        for component, registered in zip("ABC", case[f"{stream}_n_mol_per_s"], strict=True):
            column = f"{stream}.n.{component}"
            copies[column] = ledger.within(
                column, state[column], registered, f9_t05b.FLOW_ALLOWANCE
            )
    value = {
        "outcome": solved.run.outcome,
        "verification_status": certificate.verification_status,
        "projection": certificate.transformations["projection"],
        "independent_split.U-PHF.S1": [split.result, split.reason],
        "independent_split.U-PHF.S1.*": sub_ids,
        "saturation_present": saturation,
        "closure": [closure.result, _p5_ratio(closure)],
        "balances": balances,
        "d3_note_on_energy_balance.U-PHF": notes,
        "failing_residuals": failing_rows,
        "unsupported": unsupported,
        "copies_error_mol_per_s": copies,
        "largest_copy_error_mol_per_s": max(copies.values()),
        "departures": ledger.departures,
    }
    expected = {
        "outcome": "CONVERGED",
        "verification_status": "VERIFIED",
        "projection": P5_PROJECTED,
        "independent_split.U-PHF.S1": ["not_applicable", "fresh_flash_unresolved"],
        "independent_split.U-PHF.S1.*": [],
        "saturation_present": False,
        "closure": "pass",
        "balances": f"each at most {P5_BOUND:g} τ_E",
        "d3_note_on_energy_balance.U-PHF": {"S2": True, "S3": True},
        "copies_error_mol_per_s": f"each within {f9_t05b.FLOW_ALLOWANCE:g} of "
        "ref…cases.NP-GC.S4/S5 (T02 §6.4)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X11"] = (
    "NP-GC (NP-G's flowsheet with `S3 → U-SPLIT (0.5) → S4, S5 → sinks`, "
    "`t05b_support.np_gc`) under `T05b-v2`: `CONVERGED`, `VERIFIED`, judged at the projection; "
    "`U-PHF` unresolved as X09 states it — `independent_split.U-PHF.S1` `not_applicable` "
    "(`fresh_flash_unresolved`), no `.total`/`.c`, no `.saturation`, the two-phase closure "
    "passing, the D3 note for S2 and S3 on `energy_balance.U-PHF`; no failing residual, nothing "
    "`unsupported`; `energy_balance.U-PHF`, `energy_balance.U-SPLIT` and the envelope `≤ 1e-3 "
    "τ_E`; `S4` and `S5` each within T02 §6.4's 3.1e-7 mol/s of `ref…cases.NP-GC`."
)
MEASURES["X11"] = _x11


# ------------------------------------------------------------------------------- X12–X14


def _x12() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """PRJ-B2 judged against SC-1's v2 claim (`test_t05b_verifier`'s fixture, its body)."""
    entry = F9_REF["closed_form"]["cases"]["PRJ-B2"]
    ledger = Ledger()
    certificate = _p5_judged()["PRJ-B2"]
    by_id = _p5_by_id(certificate)
    ledger.equal("status", certificate.verification_status, "VERIFIED")
    ledger.equal("projection", certificate.transformations["projection"], P5_PROJECTED)
    saturation = by_id["phase_admissibility.U-VLV.S2.saturation"]
    ledger.equal(".saturation result", saturation.result, "pass")
    ledger.at_most(
        ".saturation K", None if saturation.value is None else abs(saturation.value), 1e-9
    )
    balances = {}
    for name in ("energy_balance.U-VLV", "energy_balance.envelope"):
        balances[name] = {"value_W": by_id[name].value, "over_tau_E": _p5_ratio(by_id[name])}
        ledger.at_most(f"{name} over τ_E", _p5_ratio(by_id[name]), P5_BOUND)
    row = by_id["residual.U-VLV:VLV-energy"]
    ledger.equal("VLV-energy row result, flag", [row.result, row.near_threshold], ["pass", True])
    row_error = ledger.within("VLV-energy row W", row.value, entry["compiled_energy_row_W"], 1e-9)
    value = {
        "verification_status": certificate.verification_status,
        "projection": certificate.transformations["projection"],
        "saturation_K": saturation.value,
        "balances": balances,
        "VLV-energy_row": {
            "value_W": row.value,
            "error_W": row_error,
            "result": row.result,
            "near_threshold": row.near_threshold,
        },
        "departures": ledger.departures,
    }
    expected = {
        "verification_status": "VERIFIED",
        "projection": P5_PROJECTED,
        "saturation_K": "pass, at most 1e-9 K",
        "balances": f"each at most {P5_BOUND:g} τ_E",
        "VLV-energy_row": f"{entry['compiled_energy_row_W']} W to 1e-9 W, pass, near_threshold",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X12"] = (
    "PRJ-B2 (SC-1's registered root with `S2.T = 360.000002 K`, the lever-rule split kept, "
    "judged by `verify_revision(..., state=)` against SC-1's v2 `CONVERGED` claim with its "
    "plan): `VERIFIED`, judged at the projection; `phase_admissibility.U-VLV.S2.saturation` "
    "passing and `≤ 1e-9 K`; `energy_balance.U-VLV` and the envelope `≤ 1e-3 τ_E`; "
    "`residual.U-VLV:VLV-energy` equal to `ref…cases.PRJ-B2.compiled_energy_row_W` (−4.0e-4 "
    "W) to 1e-9 W, passing and `near_threshold`."
)
MEASURES["X12"] = _x12


def _x13() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    certificate = _p5_judged()["INJ-B2p"]
    by_id = _p5_by_id(certificate)
    ledger.equal("status", certificate.verification_status, "VERIFIED")
    ledger.equal("projection", certificate.transformations["projection"], P5_PROJECTED)
    saturation = by_id["phase_admissibility.U-VLV.S2.saturation"]
    ledger.equal(".saturation result", saturation.result, "pass")
    ledger.at_most(
        ".saturation K", None if saturation.value is None else abs(saturation.value), 1e-9
    )
    balance = by_id["energy_balance.U-VLV"]
    ledger.equal("energy_balance.U-VLV result", balance.result, "pass")
    ledger.at_most("energy_balance.U-VLV over τ_E", _p5_ratio(balance), P5_BOUND)
    at_x_final = verifier_tests._at_x_final("INJ-B2p")["energy_balance.U-VLV"]
    registered = REF["injections"]["INJ-B2p"]["energy_balance_U-VLV_W"]
    value = {
        "verification_status": certificate.verification_status,
        "projection": certificate.transformations["projection"],
        "saturation_K": saturation.value,
        "energy_balance.U-VLV": {"value_W": balance.value, "over_tau_E": _p5_ratio(balance)},
        "energy_balance.U-VLV_at_x_final_W": at_x_final.value,
        "departures": ledger.departures,
    }
    expected = {
        "verification_status": "VERIFIED",
        "projection": P5_PROJECTED,
        "saturation_K": "pass, at most 1e-9 K",
        "energy_balance.U-VLV": f"pass, at most {P5_BOUND:g} τ_E",
        "energy_balance.U-VLV_at_x_final_W": f"recorded (T05b ref…INJ-B2p {registered} W; "
        "T05b B18's own check)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X13"] = (
    "INJ-B2p (SC-1's root with `S2.T = 360.0000005 K`) judged against SC-1's v2 claim: "
    "`VERIFIED`, judged at the projection; `.saturation` passing and `≤ 1e-9 K`; "
    "`energy_balance.U-VLV` passing and `≤ 1e-3 τ_E` (the balance at `x_final`, through the "
    "table evaluated there unprojected, recorded beside it: T05b's −1.0e-4 W)."
)
MEASURES["X13"] = _x13


def _x14() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    entry = F9_REF["closed_form"]["injections"]["INJ-B2-prime"]
    ledger = Ledger()
    certificate = _p5_judged()["INJ-B2′"]
    by_id = _p5_by_id(certificate)
    failing = _p5_failing(certificate)
    ledger.equal(
        "verdict",
        [certificate.verification_status, certificate.false_success_detected],
        ["FAILED", True],
    )
    ledger.equal(
        "projection",
        certificate.transformations["projection"],
        f9_support.refused("residual_not_passed"),
    )
    row = by_id["residual.U-VLV:VLV-energy"]
    ledger.true("VLV-energy row in the failing set", row.id in failing)
    registered: dict[str, Any] = {
        "residual.U-VLV:VLV-energy": {
            "value": row.value,
            "error_W": ledger.within(
                "VLV-energy row W", row.value, entry["compiled_energy_row_W"], 1e-9
            ),
        }
    }
    for name, key in (
        ("energy_balance.U-VLV", "energy_balance_U-VLV_W"),
        ("energy_balance.envelope", "energy_balance_U-VLV_W"),
        ("independent_split.U-VLV.S2.total", "independent_split_total_mol_per_s"),
        ("independent_split.U-VLV.S2.B", "independent_split_B_mol_per_s"),
    ):
        check = by_id[name]
        ledger.true(f"{name} in the failing set", name in failing)
        allowed = 1e-9 * abs(float(Decimal(entry[key])))
        error = ledger.within(name, check.value, entry[key], allowed)
        registered[name] = {
            "value": check.value,
            "relative_error": error / abs(float(Decimal(entry[key]))),
            "over_tau": _p5_ratio(check),
        }
    equilibrium = by_id["residual.U-VLV:VLV-equilibrium:B"]
    ledger.equal("VLV-equilibrium:B result", equilibrium.result, "pass")
    allowed = 1e-9 * abs(float(Decimal(entry["compiled_equilibrium_row_B"])))
    error = ledger.within(
        "VLV-equilibrium:B", equilibrium.value, entry["compiled_equilibrium_row_B"], allowed
    )
    registered["residual.U-VLV:VLV-equilibrium:B"] = {
        "value": equilibrium.value,
        "relative_error": error / abs(float(Decimal(entry["compiled_equilibrium_row_B"]))),
        "result": equilibrium.result,
    }
    saturation = "phase_admissibility.U-VLV.S2.saturation" in by_id
    ledger.equal(".saturation present", saturation, False)
    value = {
        "verdict": [certificate.verification_status, certificate.false_success_detected],
        "projection": certificate.transformations["projection"],
        "failing": failing,
        "registered_checks": registered,
        "saturation_present": saturation,
        "departures": ledger.departures,
    }
    expected = {
        "verdict": ["FAILED", True],
        "projection": f9_support.refused("residual_not_passed"),
        "failing": "contains residual.U-VLV:VLV-energy, energy_balance.U-VLV, "
        "energy_balance.envelope, independent_split.U-VLV.S2.total and .B",
        "registered_checks": {
            "residual.U-VLV:VLV-energy": f"{entry['compiled_energy_row_W']} W to 1e-9 W",
            "energy_balance.U-VLV and .envelope": f"{entry['energy_balance_U-VLV_W']} W to 1e-9 "
            "relative",
            "independent_split.U-VLV.S2.total and .B": f"{entry['independent_split_B_mol_per_s']}"
            " mol/s to 1e-9 relative",
            "residual.U-VLV:VLV-equilibrium:B": f"pass, {entry['compiled_equilibrium_row_B']} to "
            "1e-9 relative",
        },
        "saturation_present": False,
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X14"] = (
    "INJ-B2′ (SC-1's root with `S2.T = 360.00002 K`, the lever-rule split kept) judged "
    "against SC-1's v2 claim: `FAILED` with `false_success_detected`, judged at `x_final` "
    "(`residual_not_passed`); the failing set contains `residual.U-VLV:VLV-energy` "
    "(`ref…INJ-B2-prime` −4.0e-3 W, to 1e-9 W), `energy_balance.U-VLV` and "
    "`energy_balance.envelope` (−57 984.004 W) and `independent_split.U-VLV.S2.total` and `.B` "
    "(−1.9328 mol/s), each to 1e-9 relative; `residual.U-VLV:VLV-equilibrium:B` passes at "
    "−7.2322e-8 (1e-9 relative); no `.saturation` check."
)
MEASURES["X14"] = _x14


# ------------------------------------------------------------------------------------ X15


def _x15() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """INJ-F10 as `test_k04f9_t05b.inj_f10` builds it, judged by `verify(..., state=)`."""
    entry = F9_REF["closed_form"]["injections"]["INJ-F10"]
    ledger = Ledger()
    certificate = _p5_inj_f10()
    failing = _p5_failing(certificate)
    ledger.equal(
        "verdict",
        [certificate.verification_status, certificate.false_success_detected],
        ["FAILED", True],
    )
    ledger.equal("projection", certificate.transformations["projection"], P5_PROJECTED)
    ledger.equal("failing", failing, ["energy_balance.envelope", "energy_balance.flash"])
    by_id = _p5_by_id(certificate)
    registered = entry["energy_balance_flash_W"]
    allowed = 1e-9 * abs(float(Decimal(registered)))
    balances = {}
    for name in ("energy_balance.flash", "energy_balance.envelope"):
        error = ledger.within(name, by_id[name].value, registered, allowed)
        balances[name] = {
            "value_W": by_id[name].value,
            "relative_error": error / abs(float(Decimal(registered))),
        }
    rows_not_pass = [
        c.id for c in certificate.checks if c.category == "residual" and c.result != "pass"
    ]
    ledger.equal("residuals not passing", rows_not_pass, [])
    status = certificate.regularity.status if certificate.regularity is not None else None
    ledger.equal("regularity", status, "NO_RANK_LOSS_DETECTED")
    value = {
        "verdict": [certificate.verification_status, certificate.false_success_detected],
        "projection": certificate.transformations["projection"],
        "failing": failing,
        "balances": balances,
        "residuals_not_passing": rows_not_pass,
        "regularity": [
            status,
            None if certificate.regularity is None else certificate.regularity.rcond_1,
        ],
        "departures": ledger.departures,
    }
    expected = {
        "verdict": ["FAILED", True],
        "projection": P5_PROJECTED,
        "failing": ["energy_balance.envelope", "energy_balance.flash"],
        "balances": f"each {registered} W to 1e-9 relative",
        "residuals_not_passing": [],
        "regularity": "NO_RANK_LOSS_DETECTED (rcond₁ recorded; spec measured 1.8508e-3)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X15"] = (
    "INJ-F10 (SYN-001 once-through `x(t*)` with the flash forced all-liquid — `S4 = 0`, "
    "`S5 = S3.n`, `S7 = S5`, `S6 = 0` — and `U-FLASH.Q` closed; `test_k04f9_t05b.inj_f10`), "
    "judged by `verify(..., state=)`: `FAILED` with `false_success_detected`; failing set "
    "exactly `{energy_balance.flash, energy_balance.envelope}`, each "
    "`ref…INJ-F10.energy_balance_flash_W` (−38 338.069 446 743 53 W) to 1e-9 relative; every "
    "residual passes; regularity `NO_RANK_LOSS_DETECTED`; judged at the projection."
)
MEASURES["X15"] = _x15


# ------------------------------------------------------------------------------------ X16

P5_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"


def _p5_x16_k04(ledger: Ledger) -> dict[str, Any]:
    """K04's injections by K04's own measurements (`k04_evidence_manifest.measure_*`), their
    structural fields against K04's committed evidence manifest, and the registered values of
    `benchmarks/k04/reference_values.yaml` (at the K04 tests' tolerances) read off the
    certificates those measurements issued."""
    measured, issued = _p5_k04()
    recorded = _p5_recorded("K04")
    injections = P5_K04_REF["injections"]
    out: dict[str, Any] = {}

    # A17 (INJ-1), A27 (INJ-6), A28 (INJ-7) and their twins.
    then = recorded["K04.A17_A27_A28.injections_and_twins"]["value"]
    for name, pair in measured["A17_A27_A28"].items():
        for side, entry in pair.items():
            now = {key: entry[key] for key in ("delta", "verdict", "failing")}
            before = {key: then[name][side][key] for key in ("delta", "verdict", "failing")}
            ledger.equal(f"K04 {name} {side}", now, before)
    out["A17_A27_A28"] = {
        name: {side: [entry["verdict"], entry["failing"]] for side, entry in pair.items()}
        for name, pair in measured["A17_A27_A28"].items()
    }
    inj1 = issued["K04 INJ-1 above"]
    bound = inj1.solution_error_bound_scaled
    ledger.equal("K04 INJ-1 detected", inj1.false_success_detected, True)
    ledger.equal("K04 INJ-1 regularity", inj1.regularity.status, "NO_RANK_LOSS_DETECTED")
    ledger.true(
        "K04 INJ-1 bound 1.4481555e-3 to 1e-3 relative (the test's pin)",
        bound is not None and abs(bound - 1.4481555e-3) <= 1e-3 * 1.4481555e-3,
    )
    inj6 = _p5_by_id(issued["K04 INJ-6 above"])
    shifted = [
        *injections["INJ-6-one-coordinate"]["rows_shifted_by_delta"],
        injections["INJ-6-one-coordinate"]["row_shifted_by_delta_h"],
    ]
    for identifier in [f"residual.{row}" for row in shifted] + [
        "material_balance.mixer.A",
        "material_balance.ratio.A",
        "energy_balance.mixer",
    ]:
        ledger.equal(f"K04 INJ-6 {identifier}", inj6[identifier].result, "fail")
    inj7 = _p5_by_id(issued["K04 INJ-7 above"])
    entry = injections["INJ-7-tampered-specification"]
    duty = inj7["residual.U-HEAT:HEAT-duty"].value
    target = float(entry["HEAT_duty_shift_per_K_W"]) * float(entry["fails_at_K"])
    ledger.true(
        "K04 INJ-7 HEAT-duty row = shift × δ to 1e-6 relative",
        abs(duty - target) <= 1e-6 * abs(target),
    )
    out["INJ-1_bound"] = bound
    out["INJ-7_HEAT-duty_row_W"] = [duty, target]
    for twin in ("INJ-1 twin", "INJ-6 twin", "INJ-7 twin"):
        certificate = issued[f"K04 {twin}"]
        ledger.equal(
            f"K04 {twin}",
            [
                certificate.verification_status,
                _p5_failing(certificate),
                certificate.regularity.ill_conditioned_reason,
            ],
            ["VERIFIED", [], None],
        )

    # A18 (INJ-2): the trivial root, against K04's evidence and the committed fixture.
    trivial = measured["A18"]
    then = recorded["K04.A18.injected_false_success"]["value"]
    structural = (
        "verdict",
        "false_success_detected",
        "residual_rows_passing",
        "residual_rows",
        "material_all_pass",
        "energy_envelope",
        "regularity",
    )
    ledger.equal(
        "K04 INJ-2 structure",
        {key: trivial[key] for key in structural},
        {key: then[key] for key in structural},
    )
    registered = injections["INJ-2-trivial-root"]
    offset = registered["offset_W"]
    failing = trivial["failing"]
    ledger.within("K04 INJ-2 heater", failing["energy_heater_W"], f"-{offset}", 1e-6)
    ledger.within("K04 INJ-2 flash", failing["energy_flash_W"], offset, 1e-6)
    excess = str(Decimal(registered["S3_sum_xK_350K"]) - 1)
    ledger.within(
        "K04 INJ-2 Σ x K − 1", failing["sum_xK_minus_one"], excess, 1e-12 * float(Decimal(excess))
    )
    split = abs(failing["split_total_mol_per_s"])
    ledger.within(
        "K04 INJ-2 |split total|",
        split,
        registered["S3_true_V_mol_per_s"],
        1e-12 * float(Decimal(registered["S3_true_V_mol_per_s"])),
    )
    fixture = json.loads(
        (
            P5_FIXTURE_DIR / "solution_certificate" / "valid" / "syn001_trivial_root_failed.json"
        ).read_text()
    )
    fixture_failing = sorted(c["id"] for c in fixture["checks"] if c["result"] == "fail")
    ledger.equal("K04 INJ-2 failing set", _p5_failing(issued["K04 INJ-2"]), fixture_failing)
    out["A18"] = {key: trivial[key] for key in structural} | {
        "failing_values": failing,
        "failing": _p5_failing(issued["K04 INJ-2"]),
    }

    # A19 (INJ-3) and A16 (INJ-4: the supplied policies at INJ-3's state).
    inj3 = _p5_by_id(issued["K04 INJ-3 registered"])
    residuals = injections["INJ-3-consistent-near-state"]["R_mol_per_s"]
    recycle: dict[str, Any] = {}
    for component, value in zip("ABC", residuals, strict=True):
        check = inj3[f"residual.U-SPLIT:SPLIT-recycle:{component}"]
        recycle[component] = [check.value, check.result]
        ledger.within(
            f"K04 INJ-3 SPLIT-recycle:{component} = −R", check.value, str(-Decimal(value)), 1e-12
        )
        ledger.equal(f"K04 INJ-3 SPLIT-recycle:{component}", check.result, "fail")
        ledger.equal(
            f"K04 INJ-3 ratio.{component}",
            inj3[f"material_balance.ratio.{component}"].result,
            "fail",
        )
    other = sorted(
        c.id
        for c in issued["K04 INJ-3 registered"].checks
        if c.category
        in ("energy_balance", "specification", "alias_certificate", "phase_admissibility")
        and c.result == "fail"
    )
    ledger.equal("K04 INJ-3 energy, specification, alias, phase failures", other, [])
    out["A19"] = {
        "verdict": issued["K04 INJ-3 registered"].verification_status,
        "SPLIT-recycle": recycle,
    }
    ledger.equal("K04 INJ-3 verdict", out["A19"]["verdict"], "FAILED")
    policies = measured["A16"]
    ledger.equal("K04 INJ-4 policies", policies, recorded["K04.A16.supplied_policy"]["value"])
    out["A16"] = {label: entry["verdict"] for label, entry in policies.items()}
    return out


def _p5_x16_t05b(ledger: Ledger) -> dict[str, Any]:
    """T05b B18's INJ-B1 and INJ-B3, B29's INJ-B4 and INJ-B5, as their tests build them."""
    out: dict[str, Any] = {}
    certificate = _p5_judged()["INJ-B1"]
    entry = REF["injections"]["INJ-B1"]
    by_id = _p5_by_id(certificate)
    three = ["energy_balance.U-VLV", "energy_balance.envelope", "residual.U-VLV:VLV-energy"]
    ledger.equal(
        "INJ-B1",
        [
            certificate.verification_status,
            certificate.false_success_detected,
            _p5_failing(certificate),
        ],
        ["FAILED", True, three],
    )
    values = {}
    for name, key in (
        ("energy_balance.U-VLV", "energy_balance_U-VLV_W"),
        ("residual.U-VLV:VLV-energy", "compiled_energy_row_W"),
        ("energy_balance.envelope", "energy_balance_envelope_in_minus_out_W"),
    ):
        check = by_id[name]
        values[name] = check.value
        ledger.within(f"INJ-B1 {name}", check.value, entry[key], check.tolerance)
    ledger.true(
        "INJ-B1 balance at least 1e3 τ_E", (_p5_ratio(by_id["energy_balance.U-VLV"]) or 0.0) >= 1e3
    )
    saturation = by_id["phase_admissibility.U-VLV.S2.saturation"]
    ledger.within("INJ-B1 .saturation", saturation.value, entry["degeneracy_K"], 1e-12)
    split = by_id["independent_split.U-VLV.S2"]
    ledger.equal(
        "INJ-B1 split", [split.result, split.reason], ["not_applicable", "temperature_degenerate"]
    )
    out["INJ-B1"] = {
        "verdict": certificate.verification_status,
        "failing": _p5_failing(certificate),
        "values_W": values,
    }

    injected = _p5_t05b_injections()
    certificate = injected["INJ-B3"]
    label = _p5_by_id(certificate)["residual.U-VLV:zero-flow-label"]
    ledger.equal(
        "INJ-B3 status, label", [certificate.verification_status, label.result], ["FAILED", "fail"]
    )
    ledger.within(
        "INJ-B3 label K",
        label.value,
        REF["injections"]["INJ-B3"]["label_residual_K"],
        label.tolerance,
    )
    ledger.true("INJ-B3 at least 1e3 τ_T", (_p5_ratio(label) or 0.0) >= 1e3)
    out["INJ-B3"] = {
        "verdict": certificate.verification_status,
        "failing": _p5_failing(certificate),
        "label_K": label.value,
    }

    registered = REF["dormant_non_lifted_injections"]["INJ-B5"]
    certificate = injected["INJ-B5"]
    by_id = _p5_by_id(certificate)
    label = by_id["residual.U-MIX:zero-flow-label"]
    ledger.equal(
        "INJ-B5 status, label", [certificate.verification_status, label.result], ["FAILED", "fail"]
    )
    ledger.within(
        "INJ-B5 label K",
        label.value,
        registered["residual_U-MIX:zero-flow-label_K"],
        label.tolerance,
    )
    compiled = [c for c in certificate.checks if c.category == "residual" and c.id != label.id]
    largest = max(abs(c.value or 0.0) for c in compiled)
    ledger.equal("INJ-B5 compiled rows pass", all(c.result == "pass" for c in compiled), True)
    ledger.within("INJ-B5 compiled rows max", largest, registered["compiled_rows_max"], 0.0)
    ledger.equal("INJ-B5 regularity", certificate.regularity.status, "NO_RANK_LOSS_DETECTED")
    out["INJ-B5"] = {
        "verdict": certificate.verification_status,
        "failing": _p5_failing(certificate),
        "label_K": label.value,
        "compiled_rows_max": largest,
    }

    registered = REF["dormant_non_lifted_injections"]["INJ-B4"]
    certificate = injected["INJ-B4"]
    by_id = _p5_by_id(certificate)
    swapped = by_id["residual.U-HX:HX-energy-hot"]
    failing = [c.id for c in certificate.checks if c.result == "fail"]
    ledger.equal(
        "INJ-B4 verdict",
        [certificate.verification_status, certificate.false_success_detected],
        ["FAILED", True],
    )
    ledger.within(
        "INJ-B4 HX-energy-hot W",
        swapped.value,
        registered["residual_U-HX:HX-energy-hot_W"],
        swapped.tolerance,
    )
    ledger.equal(
        "INJ-B4 label",
        [
            by_id["residual.U-HX:zero-flow-label:hot"].result,
            by_id["residual.U-HX:zero-flow-label:hot"].value,
        ],
        ["pass", 0.0],
    )
    allowed = {"residual.U-HX:HX-energy-hot", "energy_balance.U-HX.hot", "energy_balance.envelope"}
    ledger.equal("INJ-B4 failing outside B29's set", sorted(set(failing) - allowed), [])
    ledger.equal("INJ-B4 first failing", failing[:1], ["residual.U-HX:HX-energy-hot"])
    ledger.equal(
        "INJ-B4 energy_balance.U-HX.cold", by_id["energy_balance.U-HX.cold"].result, "pass"
    )
    allowance = float(Decimal(REF["tolerances"]["coupled_allowances"]["duty"]))
    for name, key in (
        ("energy_balance.U-HX.hot", "energy_balance_U-HX_in_minus_out_W"),
        ("energy_balance.envelope", "energy_balance_envelope_in_minus_out_W"),
    ):
        ledger.within(f"INJ-B4 {name}", by_id[name].value, registered[key], allowance)
    out["INJ-B4"] = {
        "verdict": certificate.verification_status,
        "failing": sorted(failing),
        "HX-energy-hot_W": swapped.value,
    }
    return out


def _x16() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    k04 = _p5_x16_k04(ledger)
    a32 = {
        f"{delta:+g} W": [certificate.verification_status, _p5_failing(certificate)]
        for delta, certificate in _p5_a32().items()
        if delta != 5e-4
    }
    five = sorted(t04_certificate.FIVE)
    for where, entry in a32.items():
        ledger.equal(f"T04 A32 {where}", entry, ["FAILED", five])
    (t05_ok, t05_value, _), _ = _p5_t05_a22()
    ledger.true("T05 A22 (T05's own measurement) holds", bool(t05_ok))
    t05 = {
        "condition": bool(t05_ok),
        "departures": [_p5_text(d) for d in t05_value["departures"]],
        "verdicts": {
            name: [t05_value[name]["verification_status"], t05_value[name]["failing"]]
            for name in ("INJ-T1", "INJ-T2", "INJ-T3", "INJ-T4")
        },
    }
    t05b = _p5_x16_t05b(ledger)
    value = {
        "K04": k04,
        "T04_A32": a32,
        "T05_A22": t05,
        "T05b": t05b,
        "departures": ledger.departures,
    }
    expected = {
        "K04": "A17/A27/A28 verdicts and failing sets as K04's committed evidence manifest "
        "records them (twins VERIFIED, nothing failing, no ill-conditioning); INJ-1's bound "
        "1.4481555e-3 (1e-3 relative); INJ-6's shifted rows, mixer and ratio checks failing; "
        "INJ-7's HEAT-duty row −463.919093078 W/K × 1e-5 K (1e-6 relative); INJ-2's structure "
        "as recorded, its values the registered closed forms (heater/flash ∓8237.850393069453 W "
        "to 1e-6 W, Σ x K − 1 and the split to 1e-12 relative) and its failing set the committed "
        "fixture's; INJ-3's SPLIT-recycle rows −R (1e-12), failing with the ratio rows, nothing "
        "else of energy, specification, alias or phase failing; INJ-4's three policies exactly "
        "as recorded (FAILED / RELAXED / FAILED, hashes, relaxations)",
        "T04_A32": {"±0.002 W": ["FAILED", five]},
        "T05_A22": "T05's own `_a22` measurement passes (INJ-T1…T4 FAILED, false success, the "
        "registered checks at their registered values and ≥ 10³ τ, the 'what passes' checks)",
        "T05b": "INJ-B1 FAILED, false success, exactly its three checks at 2016 W (τ each), "
        "degenerate; INJ-B3's label at 1 K (τ_T), ≥ 10³ τ; INJ-B5's label at −20 K with every "
        "compiled row exactly 0.0, regular; INJ-B4 FAILED, false success, HX-energy-hot −1000 W "
        "first and failing only among B29's three, the label 0.0, the cold balance passing, the "
        "hot and envelope balances −1000 W (1e-2 W)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X16"] = (
    "Every registered false success keeps its verdict, failing set and registered values. "
    "K04 A16–A19, A27, A28 by K04's own measurements (`k04_evidence_manifest.measure_injections`,"
    " `measure_trivial_root`, `measure_relaxation`), their verdicts and failing sets equal to "
    "K04's committed evidence manifest and their values read off the certificates they issued "
    "against `benchmarks/k04/reference_values.yaml` at the K04 tests' tolerances (INJ-2's "
    "failing set the committed fixture's); T04 A32's ±2e-3 W half (FAILED, the five checks); "
    "T05 A22 by T05's own `_a22` (its condition and departures); T05b B18's INJ-B1 and INJ-B3 "
    "and B29's INJ-B4 and INJ-B5 as their tests build and judge them."
)
MEASURES["X16"] = _x16


# ------------------------------------------------------------------------------------ X17

#: The fresh-flash categories (K04-F9 §5.1's judged-at-`x̃` list).
P5_FRESH = tuple(PROJECTED_CATEGORIES)


def _p5_certificate_fields(document: Mapping[str, Any]) -> dict[str, Any]:
    """A certificate document's R0 fields X17 names: ids, results, flags, statuses, limitation
    kinds (and `transformations.projection`)."""
    return {
        "ids": [c["id"] for c in document["checks"]],
        "results": [c["result"] for c in document["checks"]],
        "near_threshold": [c["id"] for c in document["checks"] if c["near_threshold"]],
        "verification_status": document["verification_status"],
        "false_success_detected": document["false_success_detected"],
        "regularity_status": (document.get("regularity") or {}).get("status"),
        "limitation_kinds": [entry["kind"] for entry in document["limitations"]],
        "projection": document.get("transformations", {}).get("projection"),
    }


def _x17() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    k04_documents, t04_documents, _ = _p5_fixtures()
    fixtures: dict[str, Any] = {}
    for name, document in {**k04_documents, **t04_documents}.items():
        committed = json.loads((P5_FIXTURE_DIR / name).read_text())
        found = differences(document, committed, policy_id="K04-numerical-policy-v1")
        record: dict[str, Any] = {
            "differences": [_p5_text(item) for item in found[:5]],
            "difference_count": len(found),
        }
        ledger.equal(f"{name}: ADR 0007 D2 differences", len(found), 0)
        if name.startswith("solution_certificate/"):
            now, then = _p5_certificate_fields(document), _p5_certificate_fields(committed)
            for field_name in now:
                ledger.equal(f"{name}: {field_name}", now[field_name], then[field_name])
            fresh = {
                c["id"]: abs(c["value"] - o["value"]) / c["tolerance"]
                for c, o in zip(document["checks"], committed["checks"], strict=True)
                if c["category"] in P5_FRESH
                and c["value"] is not None
                and o["value"] is not None
                and c["tolerance"]
            }
            for identifier, ratio in fresh.items():
                ledger.at_most(
                    f"{name}: {identifier} |now − fixture| over its threshold", ratio, 1.0
                )
            record["r0_fields_equal"] = now == then
            record["status"] = now["verification_status"]
            record["projection"] = now["projection"]
            record["fresh_flash_change_over_threshold"] = worst(fresh)
        fixtures[name] = record
    # K04 A03–A15: the five SYN-001 variants' certificates, against K04's recorded evidence.
    measured, _ = _p5_k04()
    then = _p5_recorded("K04")["K04.A15.verdicts"]["value"]
    verdicts: dict[str, Any] = {}
    for case, entry in measured["A15"].items():
        structural = (
            "verdict",
            "checks",
            "failing",
            "unsupported",
            "not_applicable",
            "limitations",
            "regularity",
        )
        now = {key: entry[key] for key in structural}
        ledger.equal(f"K04 {case}", now, {key: then[case][key] for key in structural})
        floats = differences(
            {key: entry[key] for key in ("rcond_1", "inverse_one_norm")},
            {key: then[case][key] for key in ("rcond_1", "inverse_one_norm")},
            policy_id="K04-numerical-policy-v1",
        )
        ledger.equal(f"K04 {case} rcond_1, inverse norm (ADR 0007 D2)", floats, [])
        verdicts[case] = now | {"solution_error_bound_scaled": entry["solution_error_bound_scaled"]}
    # T04 A30 and A31 by T04's own measurements, their recorded values unchanged.
    recorded = _p5_recorded("T04")
    t04: dict[str, Any] = {}
    for label, run in (("A30", lambda: t04m._a30(P5_T04_REF)), ("A31", t04m._a31)):
        condition, value, _ = run()
        t04[label] = {
            "condition": bool(condition),
            "departures": [_p5_text(d) for d in value["departures"]],
        }
        ledger.true(f"T04 {label} (T04's own measurement) holds", bool(condition))
        before = recorded[f"T04.{label}"]["value"]
        if label == "A31":
            ledger.equal("T04 A31 refusals as recorded", value["refusals"], before["refusals"])
        else:
            structural = (
                "verdict",
                "fail_or_unsupported",
                "near_threshold",
                "residual_rows",
                "aliases",
                "specification_ids",
                "specifications_evaluated_pass",
                "freed",
                "regularity",
                "derivative_path",
                "tear",
                "declaration",
            )
            for state, entry in value["states"].items():
                ledger.equal(
                    f"T04 A30 {state} as recorded",
                    {key: entry[key] for key in structural},
                    {key: before["states"][state][key] for key in structural},
                )
            t04[label]["states"] = {s: e["verdict"] for s, e in value["states"].items()}
    value = {
        "fixtures": fixtures,
        "K04_A15_variants": verdicts,
        "T04": t04,
        "departures": ledger.departures,
    }
    expected = {
        "fixtures": "every K04 and T04 schema fixture its generator emits today equal to the "
        "committed one under ADR 0007 D2 (`run.compare.differences`: structure exactly, floats "
        "1e-9 relative with the registered floors, a check value within its own tolerance); on "
        "each certificate fixture the ids, results, near_threshold flags, status, detection, "
        "regularity status, limitation kinds and transformations.projection equal, and each "
        "fresh-flash value within its threshold of the fixture's (D2.2's floor)",
        "K04_A15_variants": "verdict, check count, failing / unsupported / not_applicable, "
        "limitations and regularity status as K04's committed evidence records them; rcond_1 and "
        "the inverse norm under ADR 0007 D2",
        "T04": "T04's own A30 and A31 measurements pass, their structural values equal to T04's "
        "committed evidence manifest",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X17"] = (
    "SYN-001's legacy certificates unchanged: every K04 and T04 schema fixture "
    "(`k04_schema_fixtures.documents()`, `t04_schema_fixtures.documents()`: SYN-001's nominal "
    "and trivial-root certificates, its regularity evidence and budget bundle, HOM-01's bound "
    "certificate and T04's other fixtures) against the committed file under ADR 0007 D2 "
    "(`run.compare.differences`, K04 A31/A32, T04 A26); on each certificate fixture ids, "
    "results, `near_threshold` flags, status, regularity status, limitation kinds and "
    "`transformations.projection` equal, and each fresh-flash value's change within its "
    "threshold (D2.2's floor); K04 A03–A15's five variants (`measure_verdicts`) equal to K04's "
    "committed evidence; T04 A30 and A31 by T04's own measurements, their structural values "
    "equal to T04's committed evidence."
)
MEASURES["X17"] = _x17


# ------------------------------------------------------------------------------------ X18


def _x18() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    key = _key_sha256(identity_document()["t05"])
    ledger.equal("the t05 key", key, REGISTERED["t05_key_sha256"])
    measured: dict[str, Any] = {}
    for label, (condition, value, _) in _p5_t05_coupled().items():
        measured[label] = {
            "condition": bool(condition),
            "departures": [_p5_text(d) for d in value["departures"]],
        }
        ledger.true(f"T05 {label} (T05's own measurement) holds", bool(condition))
    bounds = {case: entry["bound"] for case, entry in _p5_t05_coupled()["A21"][1]["cases"].items()}
    for case, bound in bounds.items():
        ledger.at_most(f"{case} exact bound", bound["bound_exact"], t05m.SOLUTION_ERROR_BOUND)
    runs = _p5_t05_runs()
    projections = {
        case: runs.certificate(case).transformations["projection"] for case in t05m.COUPLED
    }
    value = {
        "t05_key_sha256": key,
        "T05": measured,
        "A21_bound": {
            case: {"exact": b["bound_exact"], "recorded": b["bound_recorded"]}
            for case, b in bounds.items()
        },
        "projection": projections,
        "departures": ledger.departures,
    }
    expected = {
        "t05_key_sha256": REGISTERED["t05_key_sha256"],
        "T05": "T05's own A17–A21 measurements pass (C1–C3 solved and certified as T05 "
        "registers them, C3X's failure)",
        "A21_bound": f"the exact bound at x_final at most {t05m.SOLUTION_ERROR_BOUND:g} per case",
        "projection": "recorded (X01 judges it)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X18"] = (
    "T05 C1–C3 unchanged: the K05 identity document's `t05` key (C1, C2, C3, C3X: plan, "
    "outcome, events, structural report, certificate R0 projection, fingerprint) hashes to "
    "`ddbd0f71…`; T05's own A17–A21 measurements (`t05_evidence_manifest._a17`…`_a21` on one "
    "`Runs`) pass, their conditions and departures recorded; A21's bound — the exact dense "
    "`‖Ĵ⁻¹‖₁` times the recorded `‖F̂‖∞` at `x_final` — `≤ 1e-8` per case."
)
MEASURES["X18"] = _x18


# ------------------------------------------------------------------------------- X20, X21


def _x20() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """D2 through `checks.enthalpy_flow`, with `test_k04f9_rules`' own streams (SYN-001's feed
    at `P_r` placed by `_offset` from the verifier's band ends), excesses (`_excesses`, §4.7's
    arithmetic) and references (`_phase_value`, `_provider_value`)."""
    r = f9_rules
    ledger = Ledger()
    eps = r.EPS
    t_bubble, t_dew = band_ends(r.PROVIDER, r.FEED, r.P_R, r.CONTEXT)
    assert t_bubble is not None and t_dew is not None
    cases: dict[str, Any] = {}

    def phase_of(stream: Any) -> str:
        return r.PROVIDER.flash(FlashRequest(state=stream), r.CONTEXT).phase_signature

    for label, end, which, sign, phase in (
        ("liquid", t_bubble, 0, +1.0, "LIQUID"),
        ("vapour", t_dew, 1, -1.0, "VAPOR"),
    ):
        stream = r._offset(end, 0.5 * eps, which, sign)
        excesses = r._excesses(stream)
        value = r.enthalpy_flow(r.PROVIDER, stream, r.CONTEXT)
        single = r._phase_value(stream, phase)
        provider = r._provider_value(stream)
        cases[f"{label} within ε_adm"] = {
            "excess": excesses[which],
            "provider_phase": phase_of(stream),
            "equals_single_phase_value": value == single,
            "provider_value_differs": provider != single,
        }
        ledger.true(f"{label} within ε_adm: excess in (0, ε_adm]", 0.0 < excesses[which] <= eps)
        if label == "vapour":
            ledger.true("vapour within ε_adm: bubble excess past ε_adm", excesses[0] > eps)
        ledger.equal(
            f"{label} within ε_adm",
            [phase_of(stream), value == single, provider != single],
            ["TWO_PHASE", True, True],
        )
        stream = r._offset(end, 2.0 * eps, which, sign)
        excess = r._excesses(stream)[which]
        value = r.enthalpy_flow(r.PROVIDER, stream, r.CONTEXT)
        single = r._phase_value(stream, phase)
        record: dict[str, Any] = {
            "excess": excess,
            "equals_provider_value": value == r._provider_value(stream),
            "differs_from_single_phase_value": value != single,
        }
        ledger.true(f"{label} at 2 ε_adm: excess in (1.5, 3] ε_adm", 1.5 * eps < excess <= 3 * eps)
        ledger.equal(
            f"{label} at 2 ε_adm",
            [record["equals_provider_value"], record["differs_from_single_phase_value"]],
            [True, True],
        )
        if label == "liquid":
            constants = r.k_values(r.PROVIDER, stream.temperature, stream.pressure, r.CONTEXT)
            request = r.PropertyRequest
            liquid_h = r.PROVIDER.evaluate_phase(
                request(state=stream, phase="LIQUID", properties=("h",)), r.CONTEXT
            ).values
            vapor_h = r.PROVIDER.evaluate_phase(
                request(state=stream, phase="VAPOR", properties=("h",)), r.CONTEXT
            ).values
            total = sum(stream.n)
            x = [flow / total for flow in stream.n]
            amplification = (
                total
                * sum(
                    xi * k * (vapor_h[f"h_{c}"] - liquid_h[f"h_{c}"])
                    for xi, k, c in zip(x, constants, r.COMPONENTS, strict=True)
                )
                / sum(xi * (k - 1.0) ** 2 for xi, k in zip(x, constants, strict=True))
            )
            kink = value - single
            record["kink_W"] = kink
            record["A_L_times_excess_W"] = amplification * excess
            record["relative_difference"] = abs(kink / (amplification * excess) - 1.0)
            ledger.at_most(
                "liquid at 2 ε_adm: kink against A_L · b (1e-2 relative)",
                record["relative_difference"],
                1e-2,
            )
        cases[f"{label} at 2 ε_adm"] = record
        outside: dict[str, Any] = {}
        for offset in (1.0, 1e-6, 1e-9):
            stream = r._at(end - sign * offset)
            excess = r._excesses(stream)[which]
            same = r.enthalpy_flow(r.PROVIDER, stream, r.CONTEXT) == r._provider_value(stream)
            outside[f"{offset:g} K"] = [excess, phase_of(stream), same]
            ledger.true(f"{label} {offset:g} K outside: excess ≤ 0", excess <= 0.0)
            ledger.equal(f"{label} {offset:g} K outside", [phase_of(stream), same], [phase, True])
        cases[f"{label} outside its band (bit for bit)"] = outside
    inside = r._at(0.5 * (t_bubble + t_dew))
    dormant = r.enthalpy_flow(r.PROVIDER, r._at(350.0, (0.0, 0.0, 0.0)), r.CONTEXT)
    cases["inside the band"] = r.enthalpy_flow(r.PROVIDER, inside, r.CONTEXT) == r._provider_value(
        inside
    )
    cases["dormant"] = [dormant, math.copysign(1.0, dormant)]
    ledger.equal("inside the band: the provider's value", cases["inside the band"], True)
    ledger.equal("dormant: +0.0", cases["dormant"], [0.0, 1.0])
    value = {"band_K": [t_bubble, t_dew], "cases": cases, "departures": ledger.departures}
    expected = {
        "within ε_adm": "the provider splits it (TWO_PHASE); enthalpy_flow gives Σ n h of the "
        "single phase exactly, which differs from the provider's value",
        "at 2 ε_adm": "the provider's two-phase value exactly, not the single phase's; the "
        "liquid's kink A_L · b to 1e-2 relative (§4.2)",
        "outside the band": "the provider's value bit for bit (1, 1e-6, 1e-9 K)",
        "inside the band": "the provider's value",
        "dormant": [0.0, 1.0],
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X20"] = (
    "D2 at the function level (`checks.enthalpy_flow`, the one function both engines call), "
    "with `test_k04f9_rules`' streams: SYN-001's feed at `P_r` placed from the verifier's band "
    "ends, its excesses in `admissibility_checks`' arithmetic — a liquid at bubble excess "
    "`ε_adm/2` gets `Σ n h^L` exactly (the provider splits it); at `2 ε_adm` the provider's "
    "two-phase value exactly, off the liquid's by `A_L · b` to 1e-2 relative; at 1 K, 1e-6 K and "
    "1e-9 K below its bubble point the provider's value bit for bit; the symmetric three for a "
    "vapour at its dew point; inside the band the provider's value, a dormant stream `+0.0`."
)
MEASURES["X20"] = _x20


def _x21() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """D3's routing (`verify.saturation.split_route`) at every entry of `ref.closed_form.routing`
    through `test_k04f9_rules._route`, against the closed form of the registered 20-digit
    fields (`_exact_floor`, `_floor_tolerance`, `_six_digits`)."""
    r = f9_rules
    ledger = Ledger()
    per_entry: dict[str, Any] = {}
    ratios: dict[str, float] = {}
    for key in sorted(r.ROUTING):
        entry = r.ROUTING[key]
        route, floor = r._route(entry)
        record: dict[str, Any] = {"route": route, "registered_route": entry["route"]}
        ledger.equal(f"{key} route", route, entry["route"])
        ledger.equal(f"{key} inside the band", floor is not None, bool(entry["inside_band"]))
        if entry["inside_band"] and floor is not None:
            registered = entry["floor_over_tau_flow"]
            if registered == "inf":
                record["floor"] = "inf"
                ledger.true(
                    f"{key} zero width", math.isinf(floor) and Fraction(entry["width_K"]) == 0
                )
            else:
                exact = r._exact_floor(entry)
                tolerance = r._floor_tolerance(entry)
                relative = float(abs(Fraction(floor) - exact) / exact)
                record.update(
                    {
                        "floor": floor,
                        "relative_error": relative,
                        "tolerance": float(tolerance),
                        "printed_is_closed_form_rounded": Decimal(registered)
                        == r._six_digits(exact),
                    }
                )
                ratios[key] = relative / float(tolerance)
                ledger.true(f"{key} printed six digits", record["printed_is_closed_form_rounded"])
                ledger.at_most(f"{key} floor relative error over its tolerance", ratios[key], 1.0)
        elif not entry["inside_band"]:
            ledger.equal(f"{key} registered floor", entry["floor_over_tau_flow"], None)
        per_entry[key] = record
    np1 = per_entry["NP-1:U-PHF.S1"]
    ledger.true(
        "NP-1 tolerance 1.06e-2 (5e-3 relative)", abs(np1["tolerance"] - 1.06e-2) <= 5e-3 * 1.06e-2
    )
    ledger.true(
        "NP-1 relative error at its pin 4.8e-4 (5e-2 relative)",
        abs(np1["relative_error"] - r.NP1_FLOOR_ERROR) <= 5e-2 * r.NP1_FLOOR_ERROR,
    )
    route_g, floor_g = r._route(r.ROUTING["NP-G:U-PHF.S1"])
    route_3, floor_3 = r._route(r.ROUTING["NP-3:U-PHF.S1"])
    margins = {
        "NP-G": [route_g, None if floor_g is None else floor_g / 0.1],
        "NP-G single-phase stored branch": r._route(r.ROUTING["NP-G:U-PHF.S1"], two_phase=False)[0],
        "NP-3": [route_3, None if floor_3 is None else 0.1 / floor_3],
        "threshold": UNRESOLVED_FLOOR_OVER_TOLERANCE,
    }
    ledger.true(
        "NP-G unresolved, more than 8.8 over",
        route_g == "unresolved" and floor_g is not None and floor_g / 0.1 > 8.8,
    )
    ledger.equal(
        "NP-G on a single-phase branch", margins["NP-G single-phase stored branch"], "resolved"
    )
    ledger.true(
        "NP-3 resolved, more than 5.8 under",
        route_3 == "resolved" and floor_3 is not None and 0.1 / floor_3 > 5.8,
    )
    ledger.equal("threshold", UNRESOLVED_FLOOR_OVER_TOLERANCE, 0.1)
    entry = r.ROUTING["INJ-B2':S2"]
    t_bubble, t_dew = band_ends(r.PROVIDER, (0.0, 2.0, 0.0), r.P_R, r.CONTEXT)
    pure = {
        "band_K": [t_bubble, t_dew],
        "route": list(
            split_route(
                float(entry["T_K"]), 2.0, t_bubble, t_dew, two_phase=True, flow_tolerance=r.TAU_FLOW
            )
        ),
        "floor_at_zero_width": resolution_floor(2.0, 360.0, 0.0, r.TAU_FLOW),
    }
    ledger.equal("INJ-B2′ zero-width band", t_bubble == t_dew, True)
    ledger.equal("INJ-B2′ route", pure["route"], ["resolved", None])
    ledger.true("INJ-B2′ floor at zero width is inf", math.isinf(pure["floor_at_zero_width"]))
    value = {
        "entries": len(per_entry),
        "per_entry": per_entry,
        "worst_floor_error_over_tolerance": worst(ratios),
        "margins": margins,
        "INJ-B2-prime": pure,
        "departures": ledger.departures,
    }
    expected = {
        "entries": 51,
        "each": "the registered route and inside_band; where inside with w > 0 the floor ratio "
        "within max(1e-6, 4 ulp(T)/w) relative of the closed form of ref's 20-digit fields, the "
        "printed six digits that closed form rounded; a zero-width entry inf",
        "NP-1": "tolerance 1.06e-2, relative error 4.8e-4 (regression pin, 5e-2 relative)",
        "margins": "NP-G unresolved, floor/0.1 above 8.8 (resolved on a single-phase branch); "
        "NP-3 resolved, 0.1/floor above 5.8; threshold 0.1",
        "INJ-B2-prime": "pure B's band of zero width; resolved with no floor; the floor at zero "
        "width inf",
    }
    ok = ledger.ok and len(per_entry) == 51
    return ok, value, expected


DESCRIPTIONS["X21"] = (
    "D3's routing at the function level (`verify.saturation.split_route`): every entry of "
    "`ref.closed_form.routing` (51) routed from its registered `T`, `N` and band ends as "
    "registered (`degenerate` / `unresolved` / `resolved`) with its `inside_band`; where inside "
    "with `w > 0` the floor ratio within `max(1e-6, 4 ulp(T)/w)` relative of the closed form of "
    "`ref`'s 20-digit fields and the printed six digits that closed form rounded; zero-width "
    "entries `inf`; NP-1's tolerance 1.06e-2 and its error 4.8e-4 (pin); the margins (NP-G "
    "unresolved above 8.8×, resolved on a single-phase branch; NP-3 resolved above 5.8×; the "
    "threshold 0.1); INJ-B2′'s pure stream outside its zero-width band."
)
MEASURES["X21"] = _x21


# ------------------------------------------------------------------------------------ X22


def _x22() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """T05 W1.d's harness (`test_t05_w1d_verifier`'s `_projection`, `_at_one_state`,
    `_cross_validate`, `_uncovered`, `_general_at`, `_legacy`) at its three states."""
    ledger = Ledger()
    shaped = _p5_w1d()
    document, binding, run = shaped["document"], shaped["binding"], shaped["run"]
    certificate = shaped["root_certificate"]
    judged_at, projected = w1d._projection(binding, document, run.state)
    at_final, _ = run_checks(w1d._legacy(), run.state)
    at_projection, _ = run_checks(w1d._legacy(), projected)
    legacy = w1d._at_one_state(at_final, at_projection)
    root = {
        "judged_at": judged_at,
        "certificate_judged_at": certificate.transformations["projection"]["judged_at"],
        "projection_moved_the_state": projected != run.state,
        "pairs": len(w1d._pairs(legacy)),
        "legacy_at_one_state_vs_certificate": w1d._cross_validate(legacy, list(certificate.checks)),
        "uncovered": w1d._uncovered(legacy, list(certificate.checks), w1d._pairs(legacy)),
        "both_engines_at_x_final": w1d._cross_validate(
            at_final, w1d._general_at(document, run.state)
        ),
        "both_engines_at_projection": w1d._cross_validate(
            at_projection, w1d._general_at(document, projected)
        ),
    }
    ledger.equal(
        "root",
        [
            root["judged_at"],
            root["certificate_judged_at"],
            root["projection_moved_the_state"],
            root["pairs"],
        ],
        ["projection", "projection", True, 43],
    )
    for name in (
        "legacy_at_one_state_vs_certificate",
        "uncovered",
        "both_engines_at_x_final",
        "both_engines_at_projection",
    ):
        ledger.equal(f"root {name}", root[name], [])
    start_state = shaped["start"]
    start_legacy, _ = run_checks(w1d._legacy(), start_state)
    whole = shaped["start_certificate"]
    start = {
        "legacy_vs_general": w1d._cross_validate(
            start_legacy, w1d._general_at(document, start_state)
        ),
        "certificate_projection": whole.transformations["projection"],
        "uncovered": w1d._uncovered(start_legacy, list(whole.checks), w1d._pairs(start_legacy)),
    }
    ledger.equal("start legacy vs general", start["legacy_vs_general"], [])
    ledger.equal(
        "start projection",
        start["certificate_projection"],
        f9_support.refused("residual_not_passed"),
    )
    ledger.equal("start uncovered", start["uncovered"], [])
    trivial_certificate = shaped["trivial_certificate"]
    trivial_state = shaped["trivial_state"]
    judged_at, projected = w1d._projection(
        shaped["trivial_binding"], shaped["trivial_document"], trivial_state
    )
    legacy = w1d._at_one_state(
        run_checks(w1d._legacy(split_fraction=0.0), trivial_state)[0],
        run_checks(w1d._legacy(split_fraction=0.0), projected)[0],
    )
    old = {check.id: check.value for check in legacy}
    by_id = _p5_by_id(trivial_certificate)
    differing = [
        general_id
        for legacy_id, general_id in (
            ("energy_balance.heater", "energy_balance.U-HEAT"),
            ("energy_balance.flash", "energy_balance.U-FLASH"),
            ("phase_admissibility.S3.bubble", "phase_admissibility.U-HEAT.S3.bubble"),
            ("independent_split.S3.total", "independent_split.U-HEAT.S3.total"),
        )
        if w1d._bits(by_id[general_id].value) != w1d._bits(old[legacy_id])
    ]
    trivial = {
        "judged_at": judged_at,
        "certificate": [
            trivial_certificate.verification_status,
            trivial_certificate.transformations["projection"]["judged_at"],
        ],
        "detections_differing_in_a_bit": differing,
    }
    ledger.equal(
        "trivial root",
        [judged_at, trivial["certificate"], differing],
        ["projection", ["FAILED", "projection"], []],
    )
    value = {
        "shaped_root": {
            k: [_p5_text(s) for s in v] if isinstance(v, list) else v for k, v in root.items()
        },
        "shaped_start": {
            k: [_p5_text(s) for s in v] if isinstance(v, list) else v for k, v in start.items()
        },
        "shaped_trivial_root": trivial,
        "departures": ledger.departures,
    }
    expected = {
        "shaped_root": "judged at the projection (x̃ ≠ x_final); 43 pairs; the legacy set judged "
        "where the certificate judges equal to the certificate bitwise, no uncovered id; each "
        "engine at x_final and at x̃ equal bitwise",
        "shaped_start": "legacy and general equal bitwise at x⁰; the certificate there refused "
        "(residual_not_passed); no uncovered id",
        "shaped_trivial_root": "judged at the projection, FAILED; the four legacy detections "
        "equal to their general counterparts bitwise",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X22"] = (
    "T05 W1.d with the amended harness: the legacy and table engines agree bitwise at one "
    "state — at the shaped root, `run_checks` at `x_final` with its fresh-flash categories from "
    "`run_checks` at the certificate's `x̃` equals the certificate on all 43 pairs with no "
    "uncovered id, and each engine at `x_final` and each at `x̃` agree on every pair; at the "
    "shaped start `x⁰` both engines agree and the certificate is refused "
    "(`residual_not_passed`) with no uncovered id; at the shaped trivial root (judged at the "
    "projection, `FAILED`) the four legacy detections equal their general counterparts to the "
    "bit."
)
MEASURES["X22"] = _x22


# ------------------------------------------------------------------------------------ X23


def _x23() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    flowsheet, state = k04_checks.solved(P5_VARIANTS["SYN-001-once-through"])
    for component in "ABC":
        state[f"S3.liq.{component}"] = state[f"S3.n.{component}"]
        state[f"S3.vap.{component}"] = 0.0
    state["S3.L"] = sum(state[f"S3.n.{c}"] for c in "ABC")
    state["S3.V"] = 0.0
    state["U-HEAT.Q"] -= k04_checks.TRIVIAL_ROOT_OFFSET
    state["U-FLASH.Q"] += k04_checks.TRIVIAL_ROOT_OFFSET
    checks, digest = run_checks(flowsheet, state)
    by_id = {check.id: check for check in checks}
    registered = P5_K04_REF["injections"]["INJ-2-trivial-root"]
    offset = registered["offset_W"]
    excess = str(Decimal(registered["S3_sum_xK_350K"]) - 1)
    must_pass = sorted(
        c.id
        for c in checks
        if c.category in ("residual", "material_balance", "alias_certificate", "specification")
        and c.result == "fail"
    )
    ledger.equal("residual, material, alias, specification failing", must_pass, [])
    ledger.equal("envelope", by_id["energy_balance.envelope"].result, "pass")
    values = {
        "energy_balance.heater": by_id["energy_balance.heater"].value,
        "energy_balance.flash": by_id["energy_balance.flash"].value,
        "phase_admissibility.S3.bubble": by_id["phase_admissibility.S3.bubble"].value,
        "independent_split.S3.total": by_id["independent_split.S3.total"].value,
    }
    ledger.within("heater", values["energy_balance.heater"], f"-{offset}", 1e-6)
    ledger.within("flash", values["energy_balance.flash"], offset, 1e-6)
    ledger.within(
        "Σ x K − 1", values["phase_admissibility.S3.bubble"], excess, 1e-12 * float(Decimal(excess))
    )
    ledger.within(
        "|split total|",
        abs(values["independent_split.S3.total"]),
        registered["S3_true_V_mol_per_s"],
        1e-12 * float(Decimal(registered["S3_true_V_mol_per_s"])),
    )
    ledger.equal(
        "bubble, split results",
        [by_id["phase_admissibility.S3.bubble"].result, by_id["independent_split.S3.total"].result],
        ["fail", "fail"],
    )
    recorded = _p5_recorded("K04")["K04.A18.injected_false_success"]["value"]["failing"]
    bitwise = {
        "energy_heater_W": values["energy_balance.heater"] == recorded["energy_heater_W"],
        "energy_flash_W": values["energy_balance.flash"] == recorded["energy_flash_W"],
        "sum_xK_minus_one": values["phase_admissibility.S3.bubble"] == recorded["sum_xK_minus_one"],
        "split_total_mol_per_s": values["independent_split.S3.total"]
        == recorded["split_total_mol_per_s"],
    }
    # A02-355 from 358 K: run_checks is F9's raw set bit for bit, not the certificate's.
    item = t04_certificate.solved_355()
    reported, report_digest = run_checks(item.binding.flowsheet, item.result.state)
    reported_by_id = {c.id: c for c in reported}
    raw = t04_certificate.by_id_list(t04_certificate._unprojected(item))
    s3 = [name for name in raw if name.startswith("independent_split.S3.")] + [
        "energy_balance.heater",
        "energy_balance.flash",
    ]
    differing = [name for name in s3 if reported_by_id[name].value != raw[name].value]
    ledger.equal("A02-355 run_checks S3 values against the unprojected functions", differing, [])
    ledger.equal(
        "A02-355 heater flagged", reported_by_id["energy_balance.heater"].near_threshold, True
    )
    certified = _p5_by_id(_p5_a02_355())
    total = "independent_split.S3.total"
    moved = reported_by_id[total].value != certified[total].value
    ledger.equal("A02-355 certificate's split differs from run_checks'", moved, True)
    report = CheckReport(checks=tuple(reported), target_state_sha256=report_digest)
    keys = sorted(report.as_document())
    ledger.equal("CheckReport keys", keys, ["checks", "target_state_sha256"])
    value = {
        "trivial_root_run_checks": values,
        "trivial_root_failing": sorted(c.id for c in checks if c.result == "fail"),
        "bitwise_equal_to_K04_recorded_evidence": bitwise,
        "A02-355": {
            "S3_values_differing_from_unprojected": differing,
            "certificate_split_differs": moved,
            "run_checks_split": reported_by_id[total].value,
            "certificate_split": certified[total].value,
        },
        "check_report_keys": keys,
        "departures": ledger.departures,
    }
    expected = {
        "trivial_root_run_checks": f"heater/flash ∓{offset} W (1e-6 W), Σ x K − 1 {excess} and "
        f"the split {registered['S3_true_V_mol_per_s']} mol/s (1e-12 relative), both failing; "
        "residual, material, alias, specification and the envelope passing",
        "bitwise_equal_to_K04_recorded_evidence": "recorded, not asserted",
        "A02-355": "run_checks' S3 values equal the unprojected functions' bit for bit (the "
        "heater flagged); the certificate's projected split differs",
        "check_report_keys": ["checks", "target_state_sha256"],
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X23"] = (
    "`run_checks` is never projected: K04 A18's trivial root (once-through, S3 forced "
    "all-liquid, both duties closed) through `run_checks` gives K04's registered closed forms "
    "(heater and flash `∓8237.850393069453 W` to 1e-6 W, `Σ x K − 1` and the split to 1e-12 "
    "relative, both failing; residual, material, alias and specification checks and the envelope "
    "passing), its values compared bitwise with K04's committed evidence (recorded); at "
    "A02-355 from 358 K `run_checks`' S3 values equal the unprojected check functions' bit for "
    "bit and differ from the certificate's; a `CheckReport` document has only `checks` and "
    "`target_state_sha256`."
)
MEASURES["X23"] = _x23


# ------------------------------------------------------------------------------------ X24


def _p5_issuers() -> dict[str, Callable[[], SolutionCertificate]]:
    """Each registered certificate's issuing call, with the inputs its gate test uses."""
    issuers: dict[str, Callable[[], SolutionCertificate]] = {}
    flowsheet, result = t04_certificate._nominal()
    issuers["SYN-001-nominal"] = lambda: verify(flowsheet, result)
    for name, item in (
        ("HOM-01", t04_certificate.solved("HOM-01")),
        ("SYN-001-A02-355", t04_certificate.solved_355()),
        ("SYN-001-A02-365", t04_certificate.solved("SYN-001-A02-365")),
    ):
        issuers[name] = lambda i=item: verify_bound(
            i.binding, i.document, i.result, solve_plan=i.solve_plan
        )
    for case in P5_T05B_CASES:
        if case in ("DZ-3", "DZ-10", "DZ-12"):
            binding, document, state, _ = _p5_dz_root(case)
            regions = {
                "DZ-3": lambda: zero_flow_tests._dz3()[1],
                "DZ-10": lambda: dormancy._dz10()[0],
                "DZ-12": lambda: dormancy._dz12()[0],
            }
            region = regions[case]()
            plan = p5_planned_step(binding, support.POLICY_V2).solve_plan
            issuers[case] = lambda b=binding, d=document, r=region, s=state, p=plan: (
                verify_revision(b, d, r, state=dict(s), solve_plan=p)
            )
            continue
        if case == "NP-GC":
            solved = f9_t05b._np_gc()
        elif case in f9_t05b.DZ_ROOTS:
            solved = (
                zero_flow_tests._solved(case)
                if case in ("DZ-1", "DZ-2", "DZ-4", "DZ-5")
                else dormancy._solved(case, "v2")
            )
        else:
            solved = contract.solved(case)
        issuers[case] = lambda s=solved: verify_revision(
            s.binding, s.document, s.run, solve_plan=s.plan.steps[-1].solve_plan
        )
    runs = _p5_t05_runs()
    from test_t05_certificates import certify

    for case in t05m.COUPLED:
        issuers[case] = lambda c=case: certify(runs.solved(c), c)
    flowsheet_f10, result_f10, state_f10 = f9_t05b.inj_f10()
    issuers["INJ-F10"] = lambda: verify(flowsheet_f10, result_f10, state=state_f10)
    return issuers


#: The certificates `test_t04_certificate.test_x24…` holds byte-identical in canonical JSON.
P5_X24_CANONICAL = ("SYN-001-nominal", "HOM-01", "SYN-001-A02-355")


def _p5_moved(first: Any, second: Any, path: str = "") -> list[str]:
    """The paths at which two documents differ (at most a handful are expected: floats)."""
    if isinstance(first, dict) and isinstance(second, dict):
        return [
            moved
            for key in sorted(set(first) | set(second))
            for moved in _p5_moved(first.get(key), second.get(key), f"{path}.{key}")
        ]
    if isinstance(first, list) and isinstance(second, list) and len(first) == len(second):
        return [
            moved
            for index, (left, right) in enumerate(zip(first, second, strict=True))
            for moved in _p5_moved(left, right, f"{path}[{index}]")
        ]
    return [] if first == second and type(first) is type(second) else [path]


def _x24() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    """Each certificate issued twice in succession from the same inputs. R0 is the identity's
    certificate projection (`run.identity.r0_projection`: status, detection, ids, results,
    flags, regularity status and dimension, limitation kinds) and `transformations.projection`;
    the whole canonical document is compared too, and judged where the gate's test judges it."""
    ledger = Ledger()
    per_case: dict[str, Any] = {}
    for name, issue in _p5_issuers().items():
        first, second = issue().as_document(), issue().as_document()
        r0 = [
            r0_projection({"solution-certificate.json": document})["certificate"]
            for document in (first, second)
        ]
        projections = [document["transformations"]["projection"] for document in (first, second)]
        identical = canonical_json(first) == canonical_json(second)
        per_case[name] = {
            "r0_identical": r0[0] == r0[1],
            "projection_identical": projections[0] == projections[1],
            "judged_at": projections[0]["judged_at"],
            "canonical_documents_identical": identical,
            "fields_differing": _p5_moved(first, second),
        }
        ledger.true(f"{name}: identical R0", r0[0] == r0[1])
        ledger.true(
            f"{name}: identical transformations.projection", projections[0] == projections[1]
        )
        if name in P5_X24_CANONICAL:
            ledger.true(f"{name}: identical canonical documents (the gate's test)", identical)
    differing = sorted(name for name, entry in per_case.items() if entry["fields_differing"])
    value = {
        "certificates": len(per_case),
        "cases": per_case,
        "not_byte_identical": differing,
        "departures": ledger.departures,
    }
    expected = {
        "each": "the two issues' R0 (run.identity.r0_projection's certificate projection) and "
        "transformations.projection identical",
        "canonical": f"byte-identical canonical JSON at {list(P5_X24_CANONICAL)} (the gate's "
        "test); elsewhere recorded, not judged (ADR 0007 promises floats within a tolerance, "
        "never bitwise)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X24"] = (
    "Determinism: each registered certificate issued twice in one process from the same inputs "
    "— SYN-001's nominal (`verify`), HOM-01, A02-355 and A02-365 (`verify_bound`), every T05b "
    "EO case with a certificate (SC-1…SC-4, NP-1…NP-3, NP-G, DZ-1…DZ-10, DZ-12) and NP-GC "
    "(`verify_revision`), T05's C1–C3 (`test_t05_certificates.certify`) and INJ-F10 — has "
    "identical R0 (`run.identity.r0_projection`'s certificate projection) and identical "
    "`transformations.projection`; the whole canonical document byte-identical at SYN-001's "
    "nominal, HOM-01 and A02-355 (the gate's test), and at the others the fields that differ "
    "between the two issues recorded."
)
MEASURES["X24"] = _x24


# ------------------------------------------------------------------------------------ X26


def _p5_realized(case: str) -> tuple[float, str]:
    """X26 (a) as `test_k04f9_t05b.realized_ratio` computes it, on the part's cached states."""
    if case.startswith("CH-"):
        ratio, column = openings.realized_ratio(case)
        return float(ratio), column
    state = _p5_t05b_state(case)
    return max(
        (float(abs(Decimal(state[column]) - Decimal(value))) / f9_t05b._allowance(column), column)
        for column, value in f9_t05b._registered_comparison(case).items()
    )


def _p5_b33b_realized(case: str) -> tuple[float, str]:
    """B33 (b)'s comparisons (`test_t05b_near_pure_restarts`): NP-1…NP-3's split and `T` at
    §13's allowances, NP-G's `T` only."""
    module = near_pure_tests
    state = module.from_liquid(case).result.state
    root = REF["near_pure_cases"][case]["root"]
    compared: dict[str, tuple[str, float]] = {}
    for stream in ("S2", "S3"):
        allowance = module.NP_G_TEMPERATURE if case == "NP-G" else module.ALLOWANCE["T"]
        compared[f"{stream}.T"] = (root["T_K"], allowance)
    if case != "NP-G":
        for index, component in enumerate(module.COMPONENTS):
            flow = module.ALLOWANCE["flow"]
            compared[f"S2.n.{component}"] = (root["vapor_mol_per_s"][index], flow)
            compared[f"S3.n.{component}"] = (root["liquid_mol_per_s"][index], flow)
    return max(
        (float(abs(Decimal(state[column]) - Decimal(value))) / allowance, column)
        for column, (value, allowance) in compared.items()
    )


def _x26() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    fraction = f9_t05b.REALIZED_FRACTION
    realized: dict[str, Any] = {}
    for case in f9_t05b.REALIZED_CASES:
        ratio, column = _p5_realized(case)
        realized[case] = {"ratio": ratio, "column": column}
        ledger.at_most(f"(a) {case} at {column}", ratio, fraction)
    for case in ("NP-1", "NP-2", "NP-3", "NP-G"):
        ratio, column = _p5_b33b_realized(case)
        realized[f"B33 (b) {case}"] = {"ratio": ratio, "column": column}
        ledger.at_most(f"(a) B33 (b) {case} at {column}", ratio, fraction)
    bounds: dict[str, Any] = {}
    for case, pin in f9_t05b.SOLUTION_ERROR_BOUNDS.items():
        bound = _p5_t05b_certificate(case).solution_error_bound_scaled
        if pin < f9_t05b.ROUNDOFF_FLOOR:
            held = bound is not None and bound < f9_t05b.ROUNDOFF_FLOOR
            rule = f"below {f9_t05b.ROUNDOFF_FLOOR:g} (roundoff-set)"
        else:
            held = bound is not None and abs(bound - pin) <= max(1e-3 * pin, 1e-18)
            rule = f"{pin:g} to 1e-3 relative (truncation-set)"
        bounds[case] = {"b": bound, "pin": pin, "rule": rule, "holds": held}
        ledger.true(f"(b) {case} b {bound!r} against its regression pin: {rule}", held)
    value = {
        "a_realized_over_allowance": realized,
        "a_worst": worst({case: entry["ratio"] for case, entry in realized.items()}),
        "b_solution_error_bound_scaled": bounds,
        "departures": ledger.departures,
    }
    expected = {
        "a_realized_over_allowance": f"each at most {fraction:g} (ADR 0007 D2.4's band edge) of "
        "its kind's T02 §6.4 allowance (3.1e-7 mol/s, 1e-5 K, 0.1 Pa, 1e-2 W); population: "
        "SC-1…SC-4, NP-1…NP-3, DZ-3, DZ-10 (S4.T), DZ-12, NP-GC (S4, S5), B31 (b)–(c) (CH-UP, "
        "CH-DZ12, CH-3, CH-DOWN), B33 (b) (NP-1…NP-3 from the liquid-form start, NP-G's T only)",
        "b_solution_error_bound_scaled": "recorded for every T05b EO case and NP-GC against the "
        "test's regression pins (truncation-set to 1e-3 relative, roundoff-set below 1e-12); no "
        "threshold (K04 §7.4)",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X26"] = (
    "W0.9's rule as amended (Q-S1, R-063). (a) For every case whose final state is compared "
    "with `ref` at T02 §6.4's allowances — SC-1…SC-4, NP-1…NP-3, DZ-3 and DZ-10 (`S4.T`), "
    "DZ-12, NP-GC (`S4`, `S5`), B31 (b)–(c)'s CH-UP, CH-DZ12, CH-3, CH-DOWN (their closed forms, "
    "`test_t05b_openings.realized_ratio`) and B33 (b)'s NP-1…NP-3 from the liquid-form start "
    "with NP-G's temperature only — the largest compared deviation over its kind's allowance, "
    "recorded per case with its column, `≤ 1/10`. (b) K04's `solution_error_bound_scaled` `b` "
    "recorded for every T05b EO case and NP-GC against the test's regression pins "
    "(truncation-set values to 1e-3 relative, roundoff-set values below 1e-12), never against "
    "an allowance."
)
MEASURES["X26"] = _x26


# ------------------------------------------------------------------------------------ X01


def _p5_population() -> dict[str, SolutionCertificate]:
    """Every certificate the K04-F9 checks issue, labelled (the builders are cached: a certificate
    another check issued is read, not issued again)."""
    population: dict[str, SolutionCertificate] = {}
    members, _ = f9_family.family()
    for member in members:
        if member.certificate is not None:
            population[f"A02 family {_p5_family_key(member)}"] = member.certificate
    for name in t04_certificate.STATES:
        population[f"T04 {name}"] = t04_certificate.certificate(name)
    population["T04 SYN-001-A02-355"] = _p5_a02_355()
    for delta, certificate in _p5_a32().items():
        population[f"T04 A32 δ = {delta:+g} W"] = certificate
    for case in P5_T05B_CASES:
        population[f"T05b {case}"] = _p5_t05b_certificate(case)
    for case in ("NP-1", "NP-2", "NP-3", "NP-G"):
        certificate = near_pure_tests.from_liquid(case).certificate
        if certificate is not None:
            population[f"T05b B33 (b) {case}"] = certificate
    for name, certificate in _p5_judged().items():
        population[f"SC-1 claim, {name}"] = certificate
    for name, certificate in _p5_t05b_injections().items():
        population[f"T05b {name}"] = certificate
    population["INJ-F10"] = _p5_inj_f10()
    population["K04 INJ-2 (X03)"] = _p5_inj2()[2]
    for label, certificate in _p5_k04()[1].items():
        population[label] = certificate
    for index, certificate in enumerate(_p5_t05_a22()[1]):
        population[f"T05 A22 certificate {index + 1}"] = certificate
    runs = _p5_t05_runs()
    for case in t05m.COUPLED:
        population[f"T05 {case}"] = runs.certificate(case)
    shaped = _p5_w1d()
    for key in ("root_certificate", "start_certificate", "trivial_certificate"):
        population[f"W1.d {key.removesuffix('_certificate')}"] = shaped[key]
    for index, certificate in enumerate(_p5_fixtures()[2]):
        population[f"schema fixture certificate {index + 1}"] = certificate
    return population


def _p5_expected_projection(certificate: SolutionCertificate) -> dict[str, Any]:
    """X01's expectation from the certificate's own `x_final` judgement: projected when every
    residual check passes and the screen says `NO_RANK_LOSS_DETECTED`; refused with the first
    failing precondition's code otherwise (§5.1: residual rows first, then regularity)."""
    rows_pass = all(c.result == "pass" for c in certificate.checks if c.category == "residual")
    status = certificate.regularity.status if certificate.regularity is not None else None
    if not rows_pass:
        return f9_support.refused("residual_not_passed")
    if status != "NO_RANK_LOSS_DETECTED":
        return f9_support.refused(f"regularity_{status}")
    return P5_PROJECTED


def _x01() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    ledger = Ledger()
    population = _p5_population()
    counts: dict[str, int] = {}
    departures_by_certificate: list[list[Any]] = []
    grammar: list[str] = []
    for label, certificate in population.items():
        document = certificate.transformations.get("projection")
        expected = _p5_expected_projection(certificate)
        if document is None:
            grammar.append(f"{label}: no transformations.projection")
            continue
        well_formed = (
            set(document) == {"judged_at", "reason", "categories"}
            and document["categories"] == list(PROJECTED_CATEGORIES)
            and (
                (document["judged_at"] == "projection" and document["reason"] == "")
                or (document["judged_at"] == "final_state" and document["reason"] in P5_REASONS)
            )
        )
        if not well_formed:
            grammar.append(f"{label}: {document}")
        key = f"{document['judged_at']}/{document['reason'] or '(empty)'}"
        counts[key] = counts.get(key, 0) + 1
        if document != expected:
            departures_by_certificate.append([label, document, expected])
    ledger.equal("certificates outside §5.5's grammar", grammar, [])
    ledger.equal(
        "certificates judged elsewhere than their x_final judgement names",
        departures_by_certificate,
        [],
    )
    value = {
        "certificates": len(population),
        "by_point_and_reason": counts,
        "outside_grammar": grammar,
        "judged_elsewhere": departures_by_certificate,
        "departures": ledger.departures,
    }
    expected = {
        "population": "every certificate the K04-F9 checks issue: the A02 family's 179, "
        "T04's bound certificates and A32's three, every T05b EO case, B33 (b)'s four, SC-1's "
        "claim with its five judged states, INJ-B3/B4/B5, INJ-F10, K04's injections and variants "
        "(K04's own measurements), T05's A22 injections and C1–C3, W1.d's three, the schema "
        "fixtures' certificates",
        "each": "transformations.projection in §5.5's grammar (judged_at projection with reason "
        "'' or final_state with a registered code; categories the fixed list); projection/'' "
        "where every residual check passes and the regularity is NO_RANK_LOSS_DETECTED; "
        "final_state/residual_not_passed where a residual check fails; final_state/"
        "regularity_STATUS where the rows pass and the screen does not",
    }
    return ledger.ok, value, expected


DESCRIPTIONS["X01"] = (
    "`transformations.projection` on every certificate the K04-F9 checks issue (the "
    "A02 family, T04's bound certificates and A32's injections, every T05b EO case and B33 "
    "(b)'s restarts, SC-1's claim with PRJ-B2, INJ-B1, INJ-B2p, INJ-B2′, INJ-B3/B4/B5, INJ-F10, "
    "K04's variants and injections as K04's measurements issue them, T05's A22 injections and "
    "C1–C3, W1.d's three states, the schema fixtures' certificates; counted in the value): "
    '§5.5\'s grammar and fixed `categories`; `judged_at = projection`, `reason = ""` wherever '
    "every residual check passes and the regularity is `NO_RANK_LOSS_DETECTED`; `final_state` / "
    "`residual_not_passed` wherever a residual check fails (every residual-failing injection)."
)
MEASURES["X01"] = _x01


def build(
    commit: str,
    gate_stdout: Path,
    identities: Path | None,
    ci_run: str | None,
    ci_commit: str | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as scratch:
        # The generators' builds run beside everything below.
        generators = Generators.start(Path(scratch))
        gate = _gate(gate_stdout)
        by_id: dict[str, dict[str, Any]] = {}
        for identifier, measure in MEASURES.items():
            prefix = "T05b" if identifier.startswith("B") else "K04F9"
            by_id[identifier] = measured(
                f"{prefix}.{identifier}", DESCRIPTIONS[identifier], measure
            )
        by_id["B21"] = measured("T05b.B21", DESCRIPTIONS["B21"], lambda: _b21(gate))
        by_id["B22"] = _b22(identities)
        by_id["X19"] = _x19(identities)
        # B00 and X00 last in time (their builds ran beside the rest), first in their lists.
        by_id["B00"] = measured("T05b.B00", DESCRIPTIONS["B00"], lambda: _b00(generators))
        by_id["X00"] = measured("K04F9.X00", DESCRIPTIONS["X00"], lambda: _x00(generators))

    missing = [identifier for identifier in (*B_IDS, *X_IDS) if identifier not in by_id]
    if missing:
        raise SystemExit(f"no measurement for {missing}")
    checks = [by_id[identifier] for identifier in (*B_IDS, *X_IDS)]
    refused = [
        identifier for identifier in ADR_REQUIREMENTS if _schema_refuses_requirement(identifier)
    ]
    requirements = [identifier for identifier in ADR_REQUIREMENTS if identifier not in refused]
    limitations = _limitations(identities is not None, ci_run is not None, refused)
    failed = [entry["id"] for entry in checks if entry["result"] == "fail"]
    limitations += [
        f"{identifier} is `fail`: its value names every measured departure."
        for identifier in failed
    ]
    commands = [
        {
            "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate["passed"] else 1,
            "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
        },
        {
            "cmd": "PATH=.venv/bin:$PATH .venv/bin/python "
            "docs/derivations/scripts/t05b_reference.py --check --emit A_YAML",
            "cwd": ".",
            "exit_code": int(by_id["B00"]["value"].get("check_exit_code", 1))
            if isinstance(by_id["B00"]["value"], dict)
            else 1,
        },
        {
            "cmd": "PATH=.venv/bin:$PATH .venv/bin/python "
            "docs/derivations/scripts/k04f9_reference.py --check --emit A_YAML",
            "cwd": ".",
            "exit_code": int(by_id["X00"]["value"].get("check_exit_code", 1))
            if isinstance(by_id["X00"]["value"], dict)
            else 1,
        },
        {
            "cmd": "PYTHONPATH=. .venv/bin/python scripts/t05b_evidence_manifest.py "
            f"GATE_STDOUT --commit {commit}"
            + (f" --identities {identities.name}" if identities else "")
            + (f" --ci-run {ci_run}" if ci_run else "")
            + (f" --ci-commit {ci_commit}" if ci_commit else ""),
            "cwd": ".",
            "exit_code": 1 if failed else 0,
        },
    ]
    if ci_run:
        # The `commands` schema has no field for a reference (K05's precedent): the run URL goes
        # in the command string, where a reader looking for how the pair was run will find it.
        commands.append(
            {
                "cmd": "GitHub Actions workflow `ci`, jobs `check` (ubuntu-latest, "
                f"ubuntu-24.04-arm) and `identity`: {ci_run}"
                + (f" (head commit {ci_commit})" if ci_commit else ""),
                "cwd": ".",
                "exit_code": 0,
            }
        )
    if ci_commit and ci_commit != commit:
        limitations.append(_ci_commit_difference(ci_commit, commit))

    return {
        "work_package": "T05b",
        "commit": commit,
        # The frozen schema takes D/A requirement ids only; V12 and V15 are verification items
        # of plan §5, carried in `docs/requirements.yaml`.
        "requirements": requirements,
        "status": _status(checks),
        "inputs": {
            "case_id": "T05b's registered cases (spec §12: the kernel grid and doubles, SC-1…SC-4, "
            "NP-1…NP-3 and NP-G, DZ-1…DZ-12 and DZ-2C, the injections INJ-B1…INJ-B5, the R-007 "
            "states, the contract's kernel states, the B31 chains and companions, the B34 sweep) "
            "and K04-F9's (spec §6: the A02 family, A02-355/360/365 from 358 K, NP-GC, PRJ-B2, "
            "INJ-B2′, INJ-F10 and the registered false successes), built by tests/t05b_support.py "
            "and tests/k04f9_support.py; judged against benchmarks/t05b/reference_values.yaml "
            f"({file_sha256(REFERENCE)}), benchmarks/k04f9/reference_values.yaml "
            f"({file_sha256(F9_REFERENCE)}), docs/derivations/T05b-limitations-spec.md "
            f"({file_sha256(SPEC)}), docs/derivations/K04-F9-spec.md ({file_sha256(F9_SPEC)}) "
            "and the baselines of docs/t05b-measurements.md",
            "case_hash": _case_hash(),
            "environment_lock_hash": file_sha256(ROOT / "requirements.lock"),
        },
        "commands": commands,
        "checks": checks,
        "artifacts": [],
        "limitations": limitations,
        "review": {"numerical": "pending", "process_model": "pending"},
    }


#: The evidence-manifest rule: an angle-bracketed span is a template placeholder, never evidence.
ANGLE_PLACEHOLDER = re.compile(r"<[^<>]*>")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("gate_stdout", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--identities",
        type=Path,
        default=None,
        help="directory holding the downloaded structural-identity-* CI artifacts",
    )
    parser.add_argument("--ci-run", default=None, help="the workflow run that compared platforms")
    parser.add_argument(
        "--ci-commit",
        default=None,
        help="the CI run's head commit, when it is not --commit (see `_ci_commit_difference`)",
    )
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = plain(
        build(
            arguments.commit,
            arguments.gate_stdout,
            arguments.identities,
            arguments.ci_run,
            arguments.ci_commit,
        )
    )
    placeholders = [text for _, text in _strings(manifest) if ANGLE_PLACEHOLDER.search(text)]
    schema_errors = len(list(_validator("evidence-manifest.schema.json").iter_errors(manifest)))
    destination = arguments.out or (ROOT / "evidence" / "T05b" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1, allow_nan=False) + "\n", encoding="utf-8")

    counts = {
        name: sum(entry["result"] == name for entry in manifest["checks"]) for name in RESULTS
    }
    print(f"wrote {destination}")
    print(
        f"checks: {counts['pass']} pass, {counts['fail']} fail, "
        f"{counts['unsupported']} unsupported, {counts['not_applicable']} not applicable; "
        f"status {manifest['status']}"
    )
    for entry in manifest["checks"]:
        if entry["result"] != "pass":
            print(f"  {entry['id']}: {entry['result']}")
    if placeholders:
        print(f"angle-bracketed text in the manifest (never valid evidence): {placeholders[:5]}")
    if schema_errors:
        print(f"the manifest has {schema_errors} evidence-manifest schema errors")
    return 1 if counts["fail"] or placeholders or schema_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
