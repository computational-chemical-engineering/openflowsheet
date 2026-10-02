"""Generate `evidence/T04/<commit>/manifest.json` by measuring, not by transcribing. T04.

Every value recorded here is produced by running the code in this process and comparing it with
an independent expectation: `benchmarks/t04/reference_values.yaml` (the design lane's 40-digit twin
of the typed homotopy, edge 3, the residence-time mapping and the PTC core, emitted by
`docs/derivations/scripts/t04_reference.py`), `benchmarks/t03/reference_values.yaml` and
`benchmarks/t02/reference_values.yaml` where T04's cases extend theirs, or a closed form stated in
the check itself. Nothing is copied from the specification's prose: a manifest that quoted the
document it is evidence for would be evidence of nothing.

The registered assertions are `docs/derivations/T04-globalization-spec.md` §12's `A00`…`A33`, one
check each. The case builders — HOM-01…05 through the plan executor and directly, the named PTC
runs, the seeds, the basin harness, PHS-05 under PTC, the bound certificates — are imported from
the package's tests (`tests/test_t04_*.py`) so that the manifest and the gate run the same
fixtures; the observation and the comparison with the registered values are stated here. Every
observer records and returns what the solver computed; none alters a value.

Two halves cannot be measured on one machine: A26's cross-platform equality of the R0 fields,
which CI's `identity` job establishes, and A29's green gate on both architectures. Pass
`--identities DIR` (the downloaded `structural-identity-*` artifacts) and `--ci-run URL`; without
them those halves are `unsupported`, never `pass`.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t04_evidence_manifest.py <gate-stdout> --commit <sha> \
        [--identities DIR] [--ci-run URL] [--out PATH]
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

# The registered fixtures, shared with the gate (see the module note).
import test_t02_a02 as a02_fixtures  # noqa: E402
import test_t02_region as region_fixtures  # noqa: E402
import test_t03_contract as contract_fixtures  # noqa: E402
import test_t04_certificate as certificate_fixtures  # noqa: E402
import test_t04_edge3 as edge3_fixtures  # noqa: E402
import test_t04_homotopy as homotopy_fixtures  # noqa: E402
import test_t04_ptc as seed_fixtures  # noqa: E402
import test_t04_ptc_region as ptc_fixtures  # noqa: E402
import test_t04_registry as registry_fixtures  # noqa: E402

import openflowsheet.orchestrator.executor as executor_module  # noqa: E402
import openflowsheet.orchestrator.region as region_module  # noqa: E402
import openflowsheet.orchestrator.tear as tear_module  # noqa: E402
import openflowsheet.verify.certificate as certificate_module  # noqa: E402
from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.compile.casadi_backend import compile_problem  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.orchestrator.trace import (  # noqa: E402
    GlobalizationPolicy,
    HomotopyPolicy,
    PtcPolicy,
    SolvePolicy,
    Trace,
)

REFERENCE = ROOT / "benchmarks" / "t04" / "reference_values.yaml"
T03_REFERENCE = ROOT / "benchmarks" / "t03" / "reference_values.yaml"
T02_REFERENCE = ROOT / "benchmarks" / "t02" / "reference_values.yaml"
SPEC = ROOT / "docs" / "derivations" / "T04-globalization-spec.md"
ADR = ROOT / "docs" / "adr" / "0010-globalization-homotopy-ptc.md"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "t04_reference.py"
CASES = ROOT / "benchmarks" / "syn001" / "cases"
FIXTURES = ROOT / "tests" / "fixtures" / "schemas"
SOURCE = ROOT / "src" / "openflowsheet"

#: The continuation cases of spec §9.2.
HOM = ("HOM-01", "HOM-02", "HOM-03", "HOM-04", "HOM-05")
#: The two stalls and the λ each stalls at, as `ref` registers it (read in `build`).
STALLS = ("HOM-03", "HOM-04")
CONTINUED = "SPEC:SPEC-flash-duty"
#: The named PTC runs of spec §9.5, keyed as `ref.policy_simulation.ptc_named`.
NAMED = ("r=0.95/initializer", "r=0.95/OFF-A", "r=0.95/OFF-B", "r=0.5/initializer")
SEEDS = ("PTC-S1", "PTC-S2", "PTC-S3", "PTC-S4", "PTC-S5")
#: §12 conventions: temperatures on continuation paths and `α_max` 1e-9 relative (on
#: `max(1, |x|)`, the tests' rule); final states by T02 A28's per-kind allowances; the seeds' Δτ,
#: α and x 1e-12 relative and φ max(1e-12 relative, 1e-15) (F13).
RELATIVE = 1e-9
SEED_RELATIVE = 1e-12
PHI_ABSOLUTE = 1e-15
TEMPERATURE, DUTY, FLOW = 1e-5, 1e-2, 3.1e-7
COMPONENTS = ("A", "B", "C")
#: The assertion ids of spec §12, `A00`…`A33`.
ASSERTIONS = tuple(f"A{index:02d}" for index in range(34))
#: ADR 0010's affected requirements (its header), in its order.
ADR_REQUIREMENTS = ("D01", "D07", "A03", "V14", "D09", "D11", "D20")
#: Spec A29 as amended (F16): ADR 0010's list less V14, which the frozen evidence-manifest schema
#: refuses and `limitations` / `docs/requirements.yaml` carry instead.
A29_REQUIREMENTS = ("D01", "D07", "A03", "D09", "D11", "D20")
#: A λ written as ADR 0010 D7 writes it: an exact fraction `p/q`, or `0`, or `1`.
FRACTION = re.compile(r"^(0|[1-9][0-9]*)(/[1-9][0-9]*)?$")
#: A float as `repr` writes one: no R0 string may carry one (spec A12; T03 review S4).
FLOAT = re.compile(r"\d\.\d|\de[-+]?\d|\binf\b|\bnan\b")
HEX64 = re.compile(r"[0-9a-f]{64}")
#: T04 §4.6's registered vocabulary of inferred causes (ADR 0010 D8).
VOCABULARY = re.compile(
    r"^(phase_boundary_on_path\([A-Z0-9-]+\)|singular_path_or_fold|corrector_failure)$"
)


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


def measured(
    identifier: str,
    description: str,
    measure: Callable[[], tuple[bool, Any, Any]],
) -> dict[str, Any]:
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
    return check(identifier, description, verdict(condition), value, expected)


def plain(value: Any) -> Any:
    """A JSON-safe copy: numpy scalars and arrays as Python numbers, fractions as `p/q`,
    non-finite floats as strings."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        items = sorted(value, key=str) if isinstance(value, set | frozenset) else value
        return [plain(item) for item in items]
    if isinstance(value, np.ndarray):
        return [plain(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, Fraction):
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

    def close(
        self,
        where: str,
        value: float | None,
        expected: Any,
        relative: float = RELATIVE,
        absolute: float | None = None,
    ) -> float | None:
        """`|x − x_ref| ≤ relative · max(1, |x_ref|)` (§12's rule), or `≤ absolute` when given."""
        target = float(expected)
        allowed = absolute if absolute is not None else relative * max(1.0, abs(target))
        if value is None or not abs(float(value) - target) <= allowed:
            self.departures.append(
                f"{where}: measured {value!r}, registered {target!r} (allowed {allowed:.3g})"
            )
        return value

    def true(self, where: str, condition: bool) -> bool:
        if not condition:
            self.departures.append(f"{where}: does not hold")
        return condition


def reference(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def signature_text(signature: Any) -> str:
    return ",".join(f"{unit}:{regime}" for unit, regime in signature)


def region_step(result: Any) -> Any:
    return edge3_fixtures.region_step(result)


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


def _errors(validator: Any, document: Any) -> int:
    return len(list(validator.iter_errors(document)))


class Runs:
    """Every solve this manifest measures, run once and shared by the checks that read it. The
    builders are the tests' own, most of them cached in their modules, so the manifest and the
    gate measure the same objects built the same way."""

    def __init__(self) -> None:
        self._seeds: dict[str, tuple[str, list[Any], Trace]] = {}
        self._basin: Any = None
        self._registry: dict[str, Any] = {}
        self._hom_n: Any = None

    @staticmethod
    def plan(case_id: str) -> Any:
        """HOM-0x through the plan executor under its registered policy (`test_t04_edge3`)."""
        return edge3_fixtures.full_run(case_id)

    @staticmethod
    def direct(case_id: str) -> Any:
        """HOM-0x's failed solve and the recovery run by hand, with spies (`test_t04_homotopy`)."""
        return homotopy_fixtures.run(case_id)

    @staticmethod
    def named(key: str, core: str = "ptc") -> tuple[Any, Trace]:
        return ptc_fixtures.named(key, core)

    @staticmethod
    def phs05() -> Any:
        return ptc_fixtures.phs05_run()

    def seed(self, name: str) -> tuple[str, list[Any], Trace]:
        if name not in self._seeds:
            trace = Trace()
            outcome, attempts = seed_fixtures.run_seed(name, trace=trace)
            self._seeds[name] = (outcome, attempts, trace)
        return self._seeds[name]

    def basin(self) -> Any:
        if self._basin is None:
            from benchmarks.t04.basin import basin_comparison

            self._basin = basin_comparison()
        return self._basin

    def registry(self, case_id: str, **globalization: Any) -> Any:
        """A registry entry, run from its revision and `solve_policy_overrides` only."""
        return registry_fixtures.run(case_id, **globalization)

    def hom_n(self) -> Any:
        """HOM-N: PHS-05 with `eo_recovery: none`."""
        if self._hom_n is None:
            self._hom_n = edge3_fixtures.plan_run(
                edge3_fixtures.case_document("HOM-01"),
                edge3_fixtures.case_policy("HOM-01", edge3_fixtures.NONE),
            ).result
        return self._hom_n

    def traces(self) -> Iterator[tuple[str, Trace]]:
        """Every trace this manifest holds, by the case it belongs to."""
        for case_id in HOM:
            yield f"{case_id} (plan)", self.plan(case_id).result.trace
            yield f"{case_id} (direct)", self.direct(case_id).trace
        for key in NAMED:
            for core in ("newton", "ptc"):
                yield f"{key}/{core}", self.named(key, core)[1]
        yield "PHS-05/ptc", self.phs05().trace
        for name in SEEDS:
            yield name, self.seed(name)[2]

    def checkpoints(self) -> Iterator[tuple[str, Any]]:
        """Every checkpoint this manifest's solves left, by where it was found."""
        for case_id in HOM:
            result = self.plan(case_id).result
            for step in result.steps:
                if step.checkpoint is not None:
                    yield f"{case_id} step {step.index}", step.checkpoint
                for label, detail in (("region", step.detail), ("failed", step.recovered_from)):
                    checkpoint = getattr(detail, "checkpoint", None)
                    if checkpoint is not None:
                        yield f"{case_id} step {step.index} {label}", checkpoint
            recovery = self.direct(case_id).recovery
            if recovery.checkpoint is not None:
                yield f"{case_id} (direct)", recovery.checkpoint
        for key in NAMED:
            result, _ = self.named(key)
            if result.checkpoint is not None:
                yield f"{key}/ptc", result.checkpoint
        if self.phs05().failed.checkpoint is not None:
            yield "PHS-05/ptc", self.phs05().failed.checkpoint


class _Counting:
    """A compiled problem that counts its residual and Jacobian calls and delegates them."""

    def __init__(self, inner: Any, calls: list[str]) -> None:
        self._inner, self._calls = inner, calls
        self.metadata = inner.metadata

    def residual(self, x: Any, context: Any) -> Any:
        self._calls.append("residual")
        return self._inner.residual(x, context)

    def jacobian(self, x: Any, context: Any) -> Any:
        self._calls.append("jacobian")
        return self._inner.jacobian(x, context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _spy_verifier_compiles(patch: pytest.MonkeyPatch) -> tuple[list[str], list[Any]]:
    """Every problem the verifier compiles (its own and the nominal tear problem's) counts its
    calls; the declarations compiled are listed."""
    calls: list[str] = []
    compiled: list[Any] = []
    original = certificate_module.compile_problem

    def compile_and_count(spec: Any) -> Any:
        compiled.append(spec)
        return _Counting(original(spec), calls)

    patch.setattr(certificate_module, "compile_problem", compile_and_count)
    patch.setattr(tear_module, "compile_problem", compile_and_count)
    return calls, compiled


def _verifier_refusal(call: Callable[[], Any]) -> str | None:
    """The `VerifierError` message a verifier call raised, or `None` when it issued something."""
    from openflowsheet.verify.checks import VerifierError

    try:
        call()
    except VerifierError as error:
        return str(error)
    return None


# ----------------------------------------------------------------------------------- A00


@dataclass
class Generator:
    """The two generator runs A00 needs, started first because each takes minutes: one
    `--check --emit` (the check and the first emission from one build) and one `--emit`."""

    scratch: Path
    checked: subprocess.Popen[str]
    second: subprocess.Popen[str]

    @classmethod
    def start(cls, scratch: Path) -> Generator:
        def launch(*arguments: str) -> subprocess.Popen[str]:
            return subprocess.Popen(  # noqa: S603
                [sys.executable, str(GENERATOR), *arguments],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=ROOT,
            )

        return cls(
            scratch,
            launch("--check", "--emit", str(scratch / "a.yaml")),
            launch("--emit", str(scratch / "b.yaml")),
        )


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


def _a00(generator: Generator, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    output, _ = generator.checked.communicate()
    generator.second.communicate()
    counted = re.findall(r"^(\d+) checks passed", output, flags=re.MULTILINE)
    printed = re.findall(r"^ok  (.+)$", output, flags=re.MULTILINE)
    digest = file_sha256(REFERENCE)
    header = SPEC.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    first, second = generator.scratch / "a.yaml", generator.scratch / "b.yaml"
    emitted = first.is_file() and second.is_file()
    imports = _imported_siblings(GENERATOR, {GENERATOR.name})
    forbidden = [
        entry
        for entry in imports
        if entry.split(": ", 1)[1].split(".")[0] in {"openflowsheet", "benchmarks"}
    ]
    registered = list(ref["checks_passed"])
    value = {
        "check_exit_code": generator.checked.returncode,
        "second_emit_exit_code": generator.second.returncode,
        "checks_passed": int(counted[-1]) if counted else None,
        "printed_checks_equal_the_yamls_list": printed == registered,
        "reference_sha256": digest,
        "digest_in_spec_header": digest in header,
        "emit_twice_identical": emitted and first.read_bytes() == second.read_bytes(),
        "emit_equals_committed": emitted and first.read_bytes() == REFERENCE.read_bytes(),
        "scripts_read": sorted({entry.split(": ", 1)[0] for entry in imports}),
        "forbidden_imports": forbidden,
    }
    expected = {
        "check_exit_code": 0,
        "second_emit_exit_code": 0,
        "checks_passed": len(registered),
        "printed_checks_equal_the_yamls_list": True,
        "digest_in_spec_header": True,
        "emit_twice_identical": True,
        "emit_equals_committed": True,
        "forbidden_imports": [],
    }
    return all(value[key] == expected[key] for key in expected), value, expected


# ----------------------------------------------------------------------------------- A01


def _fixture_policies() -> dict[str, SolvePolicy]:
    """Every `SolvePolicy` this manifest's fixtures solve under, by the case that uses it."""
    from benchmarks.t04 import basin

    policies: dict[str, SolvePolicy] = {
        f"{case_id} (plan)": edge3_fixtures.case_policy(case_id) for case_id in HOM
    }
    policies |= {f"{case_id} (direct)": homotopy_fixtures.case_policy(case_id) for case_id in HOM}
    policies["HOM-N"] = edge3_fixtures.case_policy("HOM-01", edge3_fixtures.NONE)
    for case_id in registry_fixtures.GLOBALIZATION:
        case = registry_fixtures.CASES[case_id]
        if case.get("revision") and "study" not in case:
            policies[f"registry {case_id}"] = registry_fixtures.policy_for(case)
    policies["named runs (ptc)"] = ptc_fixtures.eo_policy("ptc")
    policies["named runs (newton)"] = ptc_fixtures.eo_policy("newton")
    policies["basin (ptc)"] = basin._policy("ptc")
    policies["basin (newton)"] = basin._policy("newton")
    policies["seeds' bare controller"] = seed_fixtures.POLICY
    policies["family scan"] = SolvePolicy(policy_id="T04-FAM", residual_tolerances={}, scales={})
    policies["A30 T02 states"] = SolvePolicy(policy_id="T04-W12", residual_tolerances={}, scales={})
    return policies


def _flatten(document: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, item in document.items():
        if isinstance(item, Mapping):
            flat |= _flatten(item, f"{prefix}{key}.")
        else:
            flat[f"{prefix}{key}"] = item
    return flat


#: The `globalization` values a fixture's case sets on purpose — the pinned `eo_recovery: none`
#: (HOM-N, the named runs) and `eo_core: ptc` — which its document records as new values.
_OVERRIDABLE = ("eo_core", "eo_recovery")


def _a01(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from k03_schema_fixtures import documents as k03_documents
    from k04_schema_fixtures import documents as k04_documents
    from t04_schema_fixtures import documents as t04_documents

    from openflowsheet.numerics.ptc import PTC_ROW_SIGN
    from openflowsheet.run.compare import differences

    ledger = Ledger()
    validator = _validator("solve-policy.schema.json")
    default = SolvePolicy(policy_id="T04", residual_tolerances={}, scales={}).as_document()
    globalization = default["globalization"]

    # The registered constants of §4.3 and §7.7, from `ref.constants`.
    homotopy, registered = globalization["homotopy"], ref["constants"]["homotopy"]
    ledger.equal("homotopy.type", homotopy["type"], registered["type"])
    for name in ("delta_lambda_initial", "delta_lambda_min", "shrink"):
        ledger.equal(f"homotopy.{name}", homotopy[name], str(registered[name]))
        ledger.true(f"homotopy.{name} is p/q", bool(FRACTION.match(homotopy[name])))
    for name in ("growth", "corrector_max_iterations", "max_lambda_trials"):
        ledger.equal(f"homotopy.{name}", homotopy[name], registered[name])
    ptc, registered_ptc = globalization["ptc"], ref["constants"]["ptc"]
    ledger.equal("ptc.mass_policy", ptc["mass_policy"], registered_ptc["mass_policy"])
    for name in (
        "residence_time_s",
        "tau_initial_s",
        "tau_min_s",
        "tau_max_s",
        "gamma_min",
        "gamma_max",
        "phi_floor",
        "retry_shrink",
    ):
        # `ref` prints these to three significant figures; each registered value is exact there.
        ledger.equal(f"ptc.{name}", ptc[name], float(registered_ptc[name]))
    for name in ("retries_max", "max_steps_per_attempt"):
        ledger.equal(f"ptc.{name}", ptc[name], registered_ptc[name])
    ledger.equal(
        "PTC_ROW_SIGN[holdup_balance]",
        PTC_ROW_SIGN["holdup_balance"],
        registered_ptc["holdup_row_sign"],
    )
    literals = {
        "policy_id": globalization["policy_id"],
        "eo_core": globalization["eo_core"],
        "eo_recovery": globalization["eo_recovery"],
        "eo_recovery_max_count": globalization["eo_recovery_max_count"],
        "ptc.status": ptc["status"],
        "ptc.polish": ptc["polish"],
    }
    expected_literals = {
        "policy_id": "T04-globalization-v1",
        "eo_core": "newton",
        "eo_recovery": "homotopy",
        "eo_recovery_max_count": 1,
        "ptc.status": "experimental",
        "ptc.polish": "one_newton_step",
    }
    ledger.equal("globalization literals", literals, expected_literals)

    # Every policy the fixtures solve under carries the object; it validates, and it differs from
    # the default only in a value its case overrides on purpose.
    per_policy: dict[str, Any] = {}
    for name, policy in _fixture_policies().items():
        document = policy.as_document()
        carried = document.get("globalization")
        errors = _errors(validator, document)
        flat, flat_default = _flatten(carried), _flatten(globalization)
        changed = sorted(key for key in flat_default if flat.get(key) != flat_default[key])
        per_policy[name] = {"schema_errors": errors, "overrides": changed}
        ledger.equal(f"{name}: schema errors", errors, 0)
        ledger.equal(f"{name}: policy_id", carried["policy_id"], "T04-globalization-v1")
        ledger.true(
            f"{name}: overrides {changed} are case overrides",
            all(entry.split(".")[0] in _OVERRIDABLE for entry in changed),
        )

    def refused(path: tuple[str, ...], value: Any) -> bool:
        changed = json.loads(json.dumps(default))
        target = changed["globalization"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return _errors(validator, changed) > 0

    refusals = {
        "without globalization": _errors(
            validator, {key: item for key, item in default.items() if key != "globalization"}
        )
        > 0,
        "policy_id T04-globalization-v2": refused(("policy_id",), "T04-globalization-v2"),
        "ptc.status qualified": refused(("ptc", "status"), "qualified"),
        "eo_recovery_max_count 2": refused(("eo_recovery_max_count",), 2),
        "homotopy.delta_lambda_initial 0.25 (a float)": refused(
            ("homotopy", "delta_lambda_initial"), 0.25
        ),
    }
    ledger.equal("schema refusals", refusals, dict.fromkeys(refusals, True))

    fixtures: dict[str, Any] = {}
    for emitted in (k03_documents(), k04_documents(), t04_documents()):
        for name, emitted_document in emitted.items():
            committed = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
            schema = name.split("/", 1)[0].replace("_", "-") + ".schema.json"
            fixture_validator = _validator(schema)
            payload = committed if isinstance(committed, list) else [committed]
            found = differences(emitted_document, committed, policy_id="K04-numerical-policy-v1")[
                :5
            ]
            errors = sum(_errors(fixture_validator, entry) for entry in payload)
            fixtures[name] = {"differences_from_emitted": found, "schema_errors": errors}
            ledger.equal(f"fixture {name}: differences", found, [])
            ledger.equal(f"fixture {name}: schema errors", errors, 0)
    value = {
        "globalization": globalization,
        "policies": per_policy,
        "schema_refuses": refusals,
        "fixtures": fixtures,
        "departures": ledger.departures,
    }
    expected = {
        "globalization": "ref.constants.homotopy and .ptc exactly; policy_id "
        "T04-globalization-v1, eo_recovery_max_count 1, ptc.status experimental",
        "policies": "every one validates, carries T04-globalization-v1 and differs from the "
        "default only in eo_core / eo_recovery / a budget its case registers",
        "schema_refuses": dict.fromkeys(refusals, True),
        "fixtures": "every one: no difference from what its generator emits, 0 schema errors",
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A02


def _a02() -> tuple[bool, Any, Any]:
    ledger = Ledger()
    per_case: dict[str, Any] = {}
    for case_id in HOM:
        seen = Runs.direct(case_id)
        identity = (seen.target.metadata.model_version, seen.target.metadata.constants_sha256)
        lambdas = {trial.index: trial.lambda_value for trial in seen.record.trials}
        attempt_context = seen.recovery.contexts[0].evaluation_context
        others = {
            f.name: getattr(attempt_context, f.name)
            for f in dataclasses.fields(attempt_context)
            if f.name != "constants_sha256"
        }
        corrector = [call for call in seen.calls if call[1] is not None]
        at_one = [call for call in corrector if lambdas[call[1]] == 1]
        below = [call for call in corrector if lambdas[call[1]] != 1]
        ledger.true(f"{case_id}: corrector calls observed", bool(corrector))
        ledger.true(
            f"{case_id}: every λ = 1 call on the target instance under the target identity",
            all(
                label == "target" and (context.model_version, context.constants_sha256) == identity
                for label, _, _, context in at_one
            ),
        )
        ledger.true(
            f"{case_id}: every call below λ = 1 on a level instance, target model_version, other "
            "constants_sha256",
            all(
                label != "target"
                and context.model_version == identity[0]
                and context.constants_sha256 != identity[1]
                for label, _, _, context in below
            ),
        )
        ledger.true(
            f"{case_id}: every corrector context equals the attempt's but for constants_sha256",
            all(
                {
                    f.name: getattr(context, f.name)
                    for f in dataclasses.fields(context)
                    if f.name != "constants_sha256"
                }
                == others
                for _, _, _, context in corrector
            ),
        )
        ledger.true(
            f"{case_id}: every call outside a corrector is the target's",
            all(call[0] == "target" for call in seen.calls if call[1] is None),
        )

        # The re-binding: one compile per distinct λ < 1, differing at the continued id only, by
        # §4.2's correctly rounded `p(λ) = p* + (1 − λ)(p⁰ − p*)`.
        target = seen.spec.parameters
        opening_state, _ = seen.failed.opening
        start, star = Fraction(opening_state["U-FLASH.Q"]), Fraction(target[CONTINUED])
        compiled = sorted({t.lambda_value for t in seen.record.trials if t.lambda_value != 1})
        values = sorted(level.parameters[CONTINUED] for level in seen.levels)
        exact = sorted(float(star + (1 - lam) * (start - star)) for lam in compiled)
        moved = sorted(
            {key for level in seen.levels for key in target if level.parameters[key] != target[key]}
        )
        ledger.equal(f"{case_id}: level compiles", len(seen.levels), len(compiled))
        ledger.equal(f"{case_id}: parameters moved", moved, [CONTINUED])
        ledger.equal(f"{case_id}: level values", values, exact)
        ledger.true(
            f"{case_id}: every level keeps the declaration's ids, equations and blocks",
            all(
                level.parameter_ids == seen.spec.parameter_ids
                and level.equations == seen.spec.equations
                and level.blocks == seen.spec.blocks
                for level in seen.levels
            ),
        )
        ledger.true(
            f"{case_id}: λ = 1 is never re-bound (p(1) = p*)",
            all(level.parameters[CONTINUED] != target[CONTINUED] for level in seen.levels),
        )

        endpoint: bool | None = None
        final = seen.record.trials[-1]
        if seen.recovery.outcome == "CONVERGED":
            ledger.equal(f"{case_id}: last λ", str(final.lambda_value), "1")
            fresh = compile_problem(seen.spec)
            context = EvaluationContext(
                model_version=fresh.metadata.model_version,
                constants_sha256=fresh.metadata.constants_sha256,
            )
            vector = np.array([seen.recovery.state[name] for name in seen.spec.variable_ids])
            evaluated = fresh.residual(vector, context)
            rows = list(seen.recovery.contexts[0].row_scales)
            at = {name: index for index, name in enumerate(seen.spec.equation_ids)}
            endpoint = evaluated.values is not None and [
                float(v).hex() for v in final.corrector.result.residual
            ] == [float(evaluated.values[at[row]]).hex() for row in rows]
            ledger.true(f"{case_id}: the λ = 1 residual is the target's bit for bit", endpoint)
        per_case[case_id] = {
            "corrector_calls": len(corrector),
            "calls_at_lambda_1": len(at_one),
            "calls_below_lambda_1": len(below),
            "level_compiles": len(seen.levels),
            "distinct_lambdas_below_1": [str(lam) for lam in compiled],
            "parameters_moved": moved,
            "endpoint_residual_bitwise": endpoint,
        }
    fields = sorted(f.name for f in dataclasses.fields(EvaluationContext))
    expected_fields = sorted(
        ["model_version", "constants_sha256", "phase_signature", "accuracy_policy", "workspace"]
    )
    ledger.equal("EvaluationContext fields", fields, expected_fields)
    workspaces = [bool(call[3].workspace) for case_id in HOM for call in Runs.direct(case_id).calls]
    ledger.equal("contexts with a workspace", sum(workspaces), 0)
    value = {"cases": per_case, "context_fields": fields, "departures": ledger.departures}
    expected = {
        "cases": "per case: every λ = 1 call on the target identity and instance, every call "
        "below λ = 1 on a level instance with the target model_version and another "
        "constants_sha256; "
        "one compile per distinct λ below 1 moving only SPEC:SPEC-flash-duty to its exact p(λ); "
        "the converged cases' λ = 1 residual the target's bit for bit",
        "context_fields": expected_fields,
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A03


def _a03(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.application.binding import bind_revision
    from openflowsheet.verify.certificate import verify, verify_bound

    ledger = Ledger()
    below: list[dict[str, Any]] = []
    for where, checkpoint in runs.checkpoints():
        level = checkpoint.continuation_lambda
        if level not in (None, "1"):
            below.append(
                {
                    "where": where,
                    "continuation_lambda": level,
                    "label": checkpoint.label,
                    "verification_scope": checkpoint.verification_scope,
                }
            )
            ledger.equal(
                f"{where}: λ = {level}",
                (checkpoint.label, checkpoint.verification_scope),
                ("partial", "unverified"),
            )
    ledger.true("some checkpoint below λ = 1 was observed", bool(below))

    validator = _validator("checkpoint.schema.json")
    stall = json.loads(
        (FIXTURES / "checkpoint" / "valid" / "t04_hom04_stall.json").read_text(encoding="utf-8")
    )
    schema = {
        "stall fixture": _errors(validator, stall) == 0,
        "refuses candidate_root below 1": _errors(validator, {**stall, "label": "candidate_root"})
        > 0,
        "refuses checked_partial below 1": _errors(
            validator, {**stall, "verification_scope": "checked_partial"}
        )
        > 0,
        "refuses a float λ": _errors(validator, {**stall, "continuation_lambda": 0.75}) > 0,
        "admits candidate_root at 1": _errors(
            validator, {**stall, "continuation_lambda": "1", "label": "candidate_root"}
        )
        == 0,
    }
    ledger.equal("checkpoint schema", schema, dict.fromkeys(schema, True))

    hom = ref["policy_simulation"]["homotopy_cases"]
    refusals: dict[str, Any] = {}
    for case_id in STALLS:
        run = runs.plan(case_id)
        step = region_step(run.result)
        recovery = step.detail
        document = edge3_fixtures.case_document(case_id)
        binding = bind_revision(document)
        message = f"continuation_level({hom[case_id]['homotopy']['lambda_reached']})"
        seen: list[str | None] = []
        with pytest.MonkeyPatch.context() as patch:
            calls, compiled = _spy_verifier_compiles(patch)
            for handed in (recovery.checkpoint, recovery, run.result):
                seen.append(
                    _verifier_refusal(lambda h=handed, b=binding, d=document: verify_bound(b, d, h))
                )
                seen.append(_verifier_refusal(lambda h=handed, b=binding: verify(b.flowsheet, h)))
        refusals[case_id] = {
            "messages": sorted(set(map(str, seen))),
            "compiled": len(compiled),
            "calls": len(calls),
            "root_fingerprint": recovery.root_fingerprint,
        }
        ledger.equal(f"{case_id}: refusals", seen, [message] * 6)
        ledger.equal(f"{case_id}: nothing compiled or evaluated", (compiled, calls), ([], []))
        ledger.equal(f"{case_id}: no root fingerprint", recovery.root_fingerprint, None)

    # No certificate on `BUDGET_EXHAUSTED(homotopy_steps)` either: A28's HOM-04 at four λ-trials.
    budget = _hom04_four_trials()
    budget_refusal = _verifier_refusal(
        lambda: verify_bound(
            bind_revision(homotopy_fixtures.revision_document("HOM-04")),
            homotopy_fixtures.revision_document("HOM-04"),
            budget.recovery,
        )
    )
    # The fourth λ-trial's level (trials 0…4 of `ref.hom.HOM-04`'s path) is the last accepted.
    budget_level = f"continuation_level({hom['HOM-04']['homotopy']['steps'][4]['lambda']})"
    ledger.equal("BUDGET_EXHAUSTED(homotopy_steps): refused", budget_refusal, budget_level)

    issued = {
        name: certificate_fixtures.certificate(name) for name in ("HOM-01", "HOM-02", "HOM-05")
    }
    verdicts = {
        name: (document.verification_status, document.false_success_detected)
        for name, document in issued.items()
    }
    ledger.equal("HOM-01/02/05 certificates", verdicts, dict.fromkeys(issued, ("VERIFIED", False)))
    targets = {
        name: (
            Runs.direct(name).recovery.checkpoint.continuation_lambda,
            Runs.direct(name).recovery.root_fingerprint["constants_sha256"]
            == Runs.direct(name).target.metadata.constants_sha256,
        )
        for name in issued
    }
    ledger.equal(
        "converged checkpoints at λ = 1, target identity",
        targets,
        dict.fromkeys(issued, ("1", True)),
    )
    value = {
        "checkpoints_below_lambda_1": below,
        "schema": schema,
        "verifier_refusals": refusals,
        "budget_exhausted_homotopy_steps": budget_refusal,
        "certificates": verdicts,
        "departures": ledger.departures,
    }
    expected = {
        "checkpoints_below_lambda_1": "every one partial / unverified",
        "schema": dict.fromkeys(schema, True),
        "verifier_refusals": {
            case_id: f"continuation_level({hom[case_id]['homotopy']['lambda_reached']}) from "
            "both entry points for the checkpoint, the region result and the plan result; "
            "nothing compiled, no residual call, no root fingerprint"
            for case_id in STALLS
        },
        "budget_exhausted_homotopy_steps": budget_level,
        "certificates": dict.fromkeys(issued, ["VERIFIED", False]),
    }
    return ledger.ok, value, expected


_HOM04_FOUR: list[Any] = []


def _hom04_four_trials() -> Any:
    """A28: HOM-04 with `max_lambda_trials = 4`, direct (`test_t04_homotopy`)."""
    if not _HOM04_FOUR:
        policy = homotopy_fixtures.case_policy(
            "HOM-04", homotopy=HomotopyPolicy(max_lambda_trials=4)
        )
        _HOM04_FOUR.append(homotopy_fixtures.direct("HOM-04", policy))
    return _HOM04_FOUR[0]


# ------------------------------------------------------------------------------ A04–A08


def _cause_ok(ledger: Ledger, where: str, recorded: str, registered: Any, closing: str) -> None:
    """§12: causes byte for byte in T03 §4.10's grammar; a `terminal` item's is `null` in `ref`
    and is compared with the solve's own closing message (ADR 0005 D7; F11)."""
    if registered is None:
        ledger.equal(f"{where}: terminal cause is the closing message", recorded, closing)
    else:
        ledger.equal(f"{where}: cause", recorded, registered)


def _alpha(trace: Trace, *, step_index: int | None, attempt: int, level: int | None, k: int) -> Any:
    """The `α` of the one `step_accepted` at iteration `k` of an attempt (or λ-trial)."""
    found = [
        float(event.alpha)
        for event in trace.of_kind("step_accepted")
        if event.step_index == step_index
        and event.attempt == attempt
        and event.homotopy_level == level
        and event.iteration == k
    ]
    return found[0] if len(found) == 1 else found


def _hom_case(runs: Runs, ref: Mapping[str, Any], case_id: str) -> tuple[Ledger, dict[str, Any]]:
    """A04–A08's common half, through the executor: the contract's attempts, edge 3, every λ-trial
    and its landings, the outcome, λ reached, the reported state and the recovery's item."""
    ledger = Ledger()
    registered = ref["policy_simulation"]["homotopy_cases"][case_id]
    result = runs.plan(case_id).result
    trace = result.trace
    step = region_step(result)
    failed, recovery = step.recovered_from, step.detail
    record = recovery.homotopy
    ledger.equal("edge 3", step.eo_recovery, registered["edge3"])
    ledger.equal("outcome", result.outcome, registered["outcome"])
    ledger.equal("contract outcome", failed.outcome, registered["contract"]["outcome"])

    items = recovery.branch_provenance
    contract = registered["contract"]["attempts"]
    ledger.equal("provenance items", len(items), len(contract) + 1)
    # The plan trace numbers a step's attempts on from its pre-solve's (T02 review S7).
    offset = trace.of_kind("homotopy_step")[0].attempt - items[-1]["attempt"]
    measured_contract = []
    for k, (item, attempt) in enumerate(zip(items, contract, strict=False)):
        where = f"contract attempt {k}"
        row = {
            "signature": signature_text(item["signature"]),
            "opening_source": item["opening_source"],
            "core": item["core"],
            "core_outcome": item["core_outcome"],
            "iterations": item["iterations"],
            "decision": item["decision"],
        }
        ledger.equal(where, row, {key: attempt[key] for key in row})
        _cause_ok(ledger, where, item["cause"], attempt["cause"], failed.message)
        for landing in attempt.get("landings") or ():
            alpha = _alpha(
                trace,
                step_index=step.index,
                attempt=k + offset,
                level=None,
                k=landing["iteration"],
            )
            ledger.close(f"{where}: α_max at {landing['iteration']}", alpha, landing["alpha_max"])
            row["alpha_max"] = alpha
        measured_contract.append(row)

    last = items[-1]
    steps = registered["homotopy"]["steps"]
    accepted = [str(s["lambda"]) for s in steps[1:] if s["accepted"]]
    ledger.equal(
        "recovery item",
        {
            key: last[key]
            for key in ("attempt", "core", "opening_source", "initializer_source", "continuation")
        },
        {
            "attempt": len(contract),
            "core": "homotopy",
            "opening_source": "eo_recovery_start",
            "initializer_source": items[0]["initializer_source"],
            "continuation": {
                "type": ref["constants"]["homotopy"]["type"],
                "parameter_ids": [CONTINUED],
                "lambda_levels": accepted,
                "lambda_reached": str(registered["homotopy"]["lambda_reached"]),
                "rejected_trials": sum(1 for s in steps if not s["accepted"]),
            },
        },
    )
    ledger.equal(
        "recovery opens at item 0's state",
        last["opening_state_sha256"],
        items[0]["opening_state_sha256"],
    )

    where_t = record.variable_ids.index("S3.T")
    trials = []
    ledger.equal("λ-trials", len(record.trials), len(steps))
    ledger.equal(
        "λ-trials after the easy endpoint",
        len(record.trials) - 1,
        registered["homotopy"]["lambda_trials"],
    )
    for trial, expected in zip(record.trials, steps, strict=False):
        corrector = trial.corrector.result
        where = f"λ-trial {trial.index}"
        row = {
            "lambda": str(trial.lambda_value),
            "delta_lambda": str(trial.delta_lambda),
            "corrector_outcome": corrector.outcome,
            "corrector_iterations": corrector.iterations,
            "accepted": trial.accepted,
        }
        ledger.equal(
            where,
            row,
            {
                "lambda": str(expected["lambda"]),
                "delta_lambda": str(expected["delta_lambda"]),
                "corrector_outcome": expected["corrector_outcome"],
                "corrector_iterations": expected["corrector_iterations"],
                "accepted": expected["accepted"],
            },
        )
        row["S3_T_K"] = ledger.close(
            f"{where}: S3.T", float(corrector.x[where_t]), expected["S3_T_K"]
        )
        for landing in expected.get("landings") or ():
            alpha = _alpha(
                trace,
                step_index=step.index,
                attempt=last["attempt"] + offset,
                level=trial.index,
                k=landing["iteration"],
            )
            ledger.close(f"{where}: α_max at {landing['iteration']}", alpha, landing["alpha_max"])
            ledger.true(
                f"{where}: the corrector carries on past its landing",
                corrector.iterations > landing["iteration"],
            )
            row["alpha_max"] = alpha
        if expected.get("blocked_by"):
            ledger.equal(f"{where}: blocked_by", list(corrector.blocked_by), expected["blocked_by"])
        trials.append(row)
    ledger.equal(
        "λ reached", str(record.lambda_reached), str(registered["homotopy"]["lambda_reached"])
    )
    assert result.state is not None
    ledger.close("reported S3.T", result.state["S3.T"], registered["homotopy"]["end_S3_T_K"])
    ledger.close(
        "reported S3.V",
        result.state["S3.V"],
        registered["homotopy"]["end_S3_V_mol_per_s"],
        absolute=FLOW,
    )
    value = {
        "outcome": result.outcome,
        "edge3": step.eo_recovery,
        "contract": {
            "outcome": failed.outcome,
            "message": failed.message,
            "attempts": measured_contract,
        },
        "lambda_trials": trials,
        "lambda_reached": str(record.lambda_reached),
        "reported_S3_T_K": result.state["S3.T"],
        "reported_S3_V_mol_per_s": result.state["S3.V"],
        "recovery_item": {key: last[key] for key in ("core", "opening_source", "continuation")},
    }
    return ledger, value


def _hom_expected(ref: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    registered = ref["policy_simulation"]["homotopy_cases"][case_id]
    return {
        "outcome": registered["outcome"],
        "edge3": registered["edge3"],
        "contract": registered["contract"],
        "lambda_trials": registered["homotopy"]["steps"],
        "lambda_reached": str(registered["homotopy"]["lambda_reached"]),
        "reported_S3_T_K": registered["homotopy"]["end_S3_T_K"],
        "reported_S3_V_mol_per_s": registered["homotopy"]["end_S3_V_mol_per_s"],
        "tolerances": "outcomes, counts, λ, signatures, sources, causes exact; S3.T and α_max "
        "1e-9 relative; S3.V 3.1e-7 mol/s",
    }


def _t02_row(
    ledger: Ledger, state: Mapping[str, float], t02: Mapping[str, Any], kelvin: int
) -> dict[str, Any]:
    """The final state against T02's closed-form sweep row, by T02 A28's per-kind allowances."""
    row = t02["syn001"]["a02_sweep"][f"T_heater={kelvin}K"]
    ledger.close("S3.T", state["S3.T"], kelvin, absolute=TEMPERATURE)
    ledger.close("U-HEAT.Q", state["U-HEAT.Q"], row["Q_heater_W"], absolute=DUTY)
    ledger.close("U-FLASH.Q", state["U-FLASH.Q"], row["Q_flash_W"], absolute=DUTY)
    worst = 0.0
    for index, component in enumerate(COMPONENTS):
        for phase, key in (("vap", "S3_vapor_mol_per_s"), ("liq", "S3_liquid_mol_per_s")):
            name = f"S3.{phase}.{component}"
            ledger.close(name, state[name], row[key][index], absolute=FLOW)
            worst = max(worst, abs(state[name] - float(row[key][index])))
    return {
        "S3.T_error_K": abs(state["S3.T"] - kelvin),
        "U-HEAT.Q_error_W": abs(state["U-HEAT.Q"] - float(row["Q_heater_W"])),
        "U-FLASH.Q_error_W": abs(state["U-FLASH.Q"] - float(row["Q_flash_W"])),
        "S3_split_error_mol_per_s": worst,
    }


def _certified(ledger: Ledger, case_id: str) -> str:
    issued = certificate_fixtures.certificate(case_id)
    ledger.equal(
        f"{case_id} certificate",
        (issued.verification_status, issued.false_success_detected),
        ("VERIFIED", False),
    )
    return str(issued.verification_status)


def _a04(
    runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any], t03: Mapping[str, Any]
) -> tuple[bool, Any, Any]:
    from openflowsheet.numerics.scaling import Scaling
    from openflowsheet.orchestrator.roots import same_root

    ledger, value = _hom_case(runs, ref, "HOM-01")
    result = runs.plan("HOM-01").result
    step = region_step(result)
    failed = step.recovered_from
    # The contract half is T03 A12 exactly: PHS-05 as T03 registered it.
    registered = t03["policy_simulation"]["cases"]["SYN-001-A02-355-dew-guess"]
    ledger.equal("T03 A12 outcome", failed.outcome, registered["outcome"])
    for k, (item, attempt) in enumerate(
        zip(failed.branch_provenance, registered["attempts"], strict=True)
    ):
        ledger.equal(
            f"T03 attempt {k}",
            (item["core_outcome"], item["iterations"], item["opening_trial"]),
            (attempt["core_outcome"], attempt["core_iterations"], attempt["opening_trial"]),
        )
    ledger.close(
        "T03 attempt 0 end S3.T",
        failed.attempts[0].end_state["S3.T"],
        registered["attempts"][0]["end_S3_T_K"],
    )
    assert result.state is not None
    value["final_vs_t02_355K"] = _t02_row(ledger, result.state, t02, 355)
    newton = a02_fixtures.solve("SYN-001-A02-355")
    spec = certificate_fixtures.solved("HOM-01").binding.spec
    verdict_same = same_root(
        step.detail.root_fingerprint,
        result.state,
        newton.root_fingerprint,
        newton.state,
        Scaling.from_spec(spec).column,
        spec.variable_ids,
    )
    ledger.equal("same_root with SYN-001-A02-355 from 358 K", verdict_same, "SAME")
    value["same_root_with_newton_355"] = verdict_same
    value["certificate"] = _certified(ledger, "HOM-01")
    value["departures"] = ledger.departures
    expected = {
        **_hom_expected(ref, "HOM-01"),
        "contract_is_T03_A12": registered["outcome"],
        "final_vs_t02_355K": "within 1e-5 K, 1e-2 W, 3.1e-7 mol/s",
        "same_root_with_newton_355": "SAME",
        "certificate": "VERIFIED",
    }
    return ledger.ok, value, expected


def _a05(runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger, value = _hom_case(runs, ref, "HOM-02")
    state = runs.plan("HOM-02").result.state
    assert state is not None
    value["final_vs_t02_355K"] = _t02_row(ledger, state, t02, 355)
    value["certificate"] = _certified(ledger, "HOM-02")
    value["departures"] = ledger.departures
    expected = {
        **_hom_expected(ref, "HOM-02"),
        "final_vs_t02_355K": "within 1e-5 K, 1e-2 W, 3.1e-7 mol/s",
        "certificate": "VERIFIED",
    }
    return ledger.ok, value, expected


def _stall_bundle(runs: Runs, case_id: str) -> Any:
    from openflowsheet.verify.failure import region_bundle

    run = runs.plan(case_id)
    step = region_step(run.result)
    return region_bundle(step.detail, run.result.trace, step_index=step.index).as_document()


def _stall(runs: Runs, ref: Mapping[str, Any], case_id: str) -> tuple[Ledger, dict[str, Any]]:
    """A06/A07's stall half: the checkpoint at λ reached, the bundle, no certificate, the
    bracket."""
    ledger, value = _hom_case(runs, ref, case_id)
    registered = ref["policy_simulation"]["homotopy_cases"][case_id]["homotopy"]
    step = region_step(runs.plan(case_id).result)
    checkpoint = step.checkpoint
    ledger.equal(
        "checkpoint",
        (checkpoint.continuation_lambda, checkpoint.label, checkpoint.verification_scope),
        (str(registered["lambda_reached"]), "partial", "unverified"),
    )
    bundle = _stall_bundle(runs, case_id)
    measured_bundle = {
        "taxonomy": bundle["taxonomy"],
        "actions": [entry["action"] for entry in bundle["suggested_actions"]],
        "inferred_causes": [entry["cause"] for entry in bundle["inferred_causes"]],
    }
    ledger.equal(
        "failure bundle",
        measured_bundle,
        {
            "taxonomy": "homotopy/PTC/active-set stalls",
            "actions": ["supply_initial_guess"],
            "inferred_causes": ["phase_boundary_on_path(U-HEAT)"],
        },
    )
    ledger.equal("root fingerprint (no certificate)", step.detail.root_fingerprint, None)
    key = "HOM-03_lambda_dew_vapor_branch" if case_id == "HOM-03" else "HOM-04_lambda_bubble"
    boundary = Fraction(ref["closed_form"]["a02"][key])
    record = step.detail.homotopy
    ledger.true(
        f"λ_reached below {key} below λ_reached + 2⁻⁹",
        record.lambda_reached < boundary < record.lambda_reached + Fraction(1, 512),
    )
    ledger.true(
        "every accepted λ below the boundary, every rejected λ above it",
        all((t.lambda_value < boundary) == t.accepted for t in record.trials),
    )
    ledger.equal("stalled at", record.stalled_at, "resolution")
    value |= {
        "checkpoint": {
            "continuation_lambda": checkpoint.continuation_lambda,
            "label": checkpoint.label,
            "verification_scope": checkpoint.verification_scope,
        },
        "bundle": measured_bundle,
        "boundary": {key: float(boundary), "bracket_width": "1/512"},
    }
    return ledger, value


def _a06(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger, value = _stall(runs, ref, "HOM-03")
    record = region_step(runs.plan("HOM-03").result).detail.homotopy
    rejected = sorted({t.corrector.result.outcome for t in record.trials if not t.accepted})
    ledger.equal("rejected correctors", rejected, ["PHASE_UPDATE_REQUIRED"])
    value["rejected_corrector_outcomes"] = rejected
    value["departures"] = ledger.departures
    expected = {
        **_hom_expected(ref, "HOM-03"),
        "checkpoint": "partial / unverified at ref's lambda_reached",
        "bundle": "homotopy/PTC/active-set stalls, supply_initial_guess, "
        "phase_boundary_on_path(U-HEAT)",
        "rejected_corrector_outcomes": ["PHASE_UPDATE_REQUIRED"],
    }
    return ledger.ok, value, expected


def _a07(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger, value = _stall(runs, ref, "HOM-04")
    record = region_step(runs.plan("HOM-04").result).detail.homotopy
    rejected = [t for t in record.trials if not t.accepted]
    ledger.true(
        "every rejection BOUND_BLOCKED with S3.vap.C in blocked_by",
        bool(rejected)
        and all(
            t.corrector.result.outcome == "BOUND_BLOCKED"
            and "S3.vap.C" in t.corrector.result.blocked_by
            for t in rejected
        ),
    )
    value["rejections"] = len(rejected)
    value["departures"] = ledger.departures
    expected = {
        **_hom_expected(ref, "HOM-04"),
        "checkpoint": "partial / unverified at ref's lambda_reached",
        "bundle": "homotopy/PTC/active-set stalls, supply_initial_guess, "
        "phase_boundary_on_path(U-HEAT)",
        "rejections": "every one BOUND_BLOCKED on S3.vap.C",
    }
    return ledger.ok, value, expected


def _a08(runs: Runs, ref: Mapping[str, Any], t02: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger, value = _hom_case(runs, ref, "HOM-05")
    result = runs.plan("HOM-05").result
    failed = region_step(result).recovered_from
    ledger.equal("contract budget", failed.budget, "newton_iterations")
    assert result.state is not None
    value["contract_budget"] = failed.budget
    value["final_vs_t02_360K"] = _t02_row(ledger, result.state, t02, 360)
    value["certificate"] = _certified(ledger, "HOM-05")
    value["departures"] = ledger.departures
    expected = {
        **_hom_expected(ref, "HOM-05"),
        "contract_budget": "newton_iterations",
        "final_vs_t02_360K": "within 1e-5 K, 1e-2 W, 3.1e-7 mol/s",
        "certificate": "VERIFIED",
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------ A09–A12


def _a09(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator.phase_contract import OpeningRefusal
    from openflowsheet.orchestrator.recovery import EO_RECOVERY_TRIGGERS, eo_recovery_due
    from openflowsheet.orchestrator.region import RegionResult
    from openflowsheet.orchestrator.trace import SolveOutcome

    ledger = Ledger()
    registered = sorted(ref["constants"]["edge3_triggers"])
    ledger.equal("trigger set", sorted(EO_RECOVERY_TRIGGERS), registered)
    fires = {
        outcome: eo_recovery_due(outcome, None)
        for outcome in get_args(SolveOutcome)
        if outcome != "BUDGET_EXHAUSTED"
    }
    ledger.equal(
        "due by outcome",
        fires,
        {outcome: outcome in registered for outcome in fires},
    )
    budgets = {
        budget: eo_recovery_due("BUDGET_EXHAUSTED", budget)
        for budget in ("newton_iterations", "ptc_steps", "property_calls", "homotopy_steps")
    }
    ledger.equal(
        "BUDGET_EXHAUSTED by budget",
        budgets,
        {
            "newton_iterations": True,
            "ptc_steps": True,
            "property_calls": False,
            "homotopy_steps": False,
        },
    )

    # HOM-U, from the registry.
    hom_u = runs.registry("SYN-001-nominal-eo-iteration-capped")
    step = region_step(hom_u)
    closed = hom_u.trace.of_kind("region_closed")[-1].as_document()
    hom_u_value = {
        "outcome": hom_u.outcome,
        "budget": step.detail.budget,
        "eo_recovery": step.eo_recovery,
        "eo_recovery_unsupported": step.eo_recovery_unsupported,
        "region_closed": [closed.get("eo_recovery"), closed.get("eo_recovery_unsupported")],
        "homotopy_steps": len(hom_u.trace.of_kind("homotopy_step")),
    }
    case = registry_fixtures.CASES["SYN-001-nominal-eo-iteration-capped"]["expected"]
    ledger.equal(
        "HOM-U",
        hom_u_value,
        {
            "outcome": case["code"],
            "budget": case["budget"],
            "eo_recovery": case["recovery"],
            "eo_recovery_unsupported": case["recovery_unsupported"],
            "region_closed": [case["recovery"], case["recovery_unsupported"]],
            "homotopy_steps": 0,
        },
    )

    # HOM-N: the edge off; T03 A12's attempts, unchanged.
    hom_n = runs.hom_n()
    n_step = region_step(hom_n)
    with_edge = region_step(runs.plan("HOM-01").result).recovered_from
    hom_n_value = {
        "outcome": hom_n.outcome,
        "eo_recovery": n_step.eo_recovery,
        "homotopy_steps": len(hom_n.trace.of_kind("homotopy_step")),
        "provenance_equals_the_contract_half_of_HOM-01": [
            dict(i) for i in n_step.detail.branch_provenance
        ]
        == [dict(i) for i in with_edge.branch_provenance],
        "message_equals_HOM-01s_failed_solve": n_step.detail.message == with_edge.message,
        "region_closed_has_eo_recovery": "eo_recovery"
        in hom_n.trace.of_kind("region_closed")[-1].as_document(),
    }
    ledger.equal(
        "HOM-N",
        hom_n_value,
        {
            "outcome": ref["policy_simulation"]["homotopy_cases"]["HOM-01"]["contract"]["outcome"],
            "eo_recovery": None,
            "homotopy_steps": 0,
            "provenance_equals_the_contract_half_of_HOM-01": True,
            "message_equals_HOM-01s_failed_solve": True,
            "region_closed_has_eo_recovery": False,
        },
    )

    # Non-triggers: RCY-STALL's `LINEAR_SOLVE_FAILED`, T03 A16's constructed
    # `CHECKPOINT_INCOMPATIBLE`, T03 review S1's `BUDGET_EXHAUSTED(property_calls)` (cap 346).
    stalled = executor_module.StepResult(
        1,
        "solve_eo",
        ("U-HEAT",),
        "LINEAR_SOLVE_FAILED",
        detail=RegionResult(outcome="LINEAR_SOLVE_FAILED", state={}, attempts=()),
    )
    unchanged = executor_module._eo_recovery(
        stalled,
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        SolvePolicy(policy_id="T04", residual_tolerances={}, scales={}),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        {},
        0,
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            region_module,
            "check_opening",
            lambda state, requirement: OpeningRefusal("coverage", "S3.T"),
        )
        document = yaml.safe_load((CASES / "SYN-001-A02-355-liquid-guess.yaml").read_text())
        incompatible = edge3_fixtures.plan_run(
            document, SolvePolicy(policy_id="T04", residual_tolerances={}, scales={})
        ).result
    capped, _ = contract_fixtures.capped_phs_01(346)
    non_triggers = {
        "RCY-STALL LINEAR_SOLVE_FAILED: step unchanged": unchanged[0] is stalled,
        "T03 A16 CHECKPOINT_INCOMPATIBLE": [
            incompatible.outcome,
            region_step(incompatible).eo_recovery,
            len(incompatible.trace.of_kind("homotopy_step")),
        ],
        "T03 S1 BUDGET_EXHAUSTED(property_calls)": [
            capped.result.outcome,
            region_step(capped.result).detail.budget,
            region_step(capped.result).eo_recovery,
            len(capped.result.trace.of_kind("homotopy_step")),
        ],
    }
    ledger.equal(
        "non-triggers",
        non_triggers,
        {
            "RCY-STALL LINEAR_SOLVE_FAILED: step unchanged": True,
            "T03 A16 CHECKPOINT_INCOMPATIBLE": ["CHECKPOINT_INCOMPATIBLE", None, 0],
            "T03 S1 BUDGET_EXHAUSTED(property_calls)": [
                "BUDGET_EXHAUSTED",
                "property_calls",
                None,
                0,
            ],
        },
    )

    # One recovery per region step: one `homotopy_step` sequence, one homotopy item, and a
    # failed recovery does not fire the edge again.
    per_case: dict[str, Any] = {}
    for case_id in HOM:
        result = runs.plan(case_id).result
        steps = result.trace.of_kind("homotopy_step")
        per_case[case_id] = {
            "homotopy_step_iterations_dense": [e.iteration for e in steps]
            == list(range(len(steps))),
            "easy_endpoints": sum(1 for e in steps if e.iteration == 0),
            "region_closed_eo_recovery": [
                e.eo_recovery for e in result.trace.of_kind("region_closed")
            ],
            "homotopy_items": sum(
                1
                for item in region_step(result).detail.branch_provenance
                if item["core"] == "homotopy"
            ),
        }
        ledger.equal(
            case_id,
            per_case[case_id],
            {
                "homotopy_step_iterations_dense": True,
                "easy_endpoints": 1,
                "region_closed_eo_recovery": ["taken"],
                "homotopy_items": 1,
            },
        )
    value = {
        "trigger_set": sorted(EO_RECOVERY_TRIGGERS),
        "due_by_budget": budgets,
        "HOM-U": hom_u_value,
        "HOM-N": hom_n_value,
        "non_triggers": non_triggers,
        "one_recovery_per_step": per_case,
        "departures": ledger.departures,
    }
    expected = {
        "trigger_set": registered,
        "due_by_budget": "newton_iterations and ptc_steps only",
        "HOM-U": "the registry's expectation: BUDGET_EXHAUSTED(newton_iterations), "
        "eo_recovery unsupported (no_continuation_parameter), no homotopy_step",
        "HOM-N": "ACTIVE_SET_CYCLING, no recovery, the contract's items and message unchanged",
        "non_triggers": "no recovery, no homotopy_step",
        "one_recovery_per_step": "one easy endpoint, one homotopy item, one taken, per case",
    }
    return ledger.ok, value, expected


def _a10() -> tuple[bool, Any, Any]:
    """§5.4 on HOM-01…05, the re-binding spied (`test_t04_edge3.test_a10`'s observation)."""
    from openflowsheet.orchestrator import homotopy

    ledger = Ledger()
    per_case: dict[str, Any] = {}
    real = homotopy.rebind
    for case_id in HOM:
        rebound: list[tuple[set[str], bool]] = []

        def spy(spec: Any, values: dict[str, float], log: list[Any] = rebound) -> Any:
            level = real(spec, values)
            changed = {k for k in spec.parameters if level.parameters[k] != spec.parameters[k]}
            same = (
                set(values) == {CONTINUED}
                and changed <= {CONTINUED}
                and level.variable_ids == spec.variable_ids
                and level.equations == spec.equations
            )
            log.append((changed, same))
            return level

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(region_module, "rebind", spy)
            result = edge3_fixtures.plan_run(
                edge3_fixtures.case_document(case_id), edge3_fixtures.case_policy(case_id)
            ).result
        step = region_step(result)
        failed, recovery = step.recovered_from, step.detail
        target = failed.contexts[0].evaluation_context
        at_one = recovery.contexts[0].evaluation_context
        lambdas = {t.lambda_value for t in recovery.homotopy.trials if t.lambda_value != 1}
        levels = result.trace.of_kind("homotopy_step")
        measured_case = {
            "lambda_1_identity_is_the_failed_solves": (
                at_one.model_version,
                at_one.constants_sha256,
            )
            == (target.model_version, target.constants_sha256),
            "rows_columns_signature_are_attempt_0s": (
                list(recovery.contexts[0].row_scales) == list(failed.contexts[0].row_scales)
                and list(recovery.contexts[0].column_scales)
                == list(failed.contexts[0].column_scales)
                and recovery.contexts[0].signature == failed.contexts[0].signature
            ),
            "rebinds": len(rebound),
            "distinct_lambdas_below_1": len(lambdas),
            "every_rebind_moves_the_continued_id_only": all(same for _, same in rebound),
            "level_identity_is_the_targets_exactly_at_lambda_1": all(
                (e.level_constants_sha256 == target.constants_sha256) == (e.lambda_value == "1")
                for e in levels
            ),
            "converged_fingerprint_identity": (
                None
                if recovery.outcome != "CONVERGED"
                else (
                    recovery.root_fingerprint["model_version"],
                    recovery.root_fingerprint["constants_sha256"],
                )
                == (target.model_version, target.constants_sha256)
            ),
        }
        per_case[case_id] = measured_case
        ledger.equal(
            case_id,
            measured_case,
            {
                **measured_case,
                "lambda_1_identity_is_the_failed_solves": True,
                "rows_columns_signature_are_attempt_0s": True,
                "rebinds": len(lambdas),
                "every_rebind_moves_the_continued_id_only": True,
                "level_identity_is_the_targets_exactly_at_lambda_1": True,
                "converged_fingerprint_identity": None if recovery.outcome != "CONVERGED" else True,
            },
        )
    value = {"cases": per_case, "departures": ledger.departures}
    expected = {
        "cases": "per case: the λ = 1 identity and attempt 0's rows, columns and signature are "
        "the failed solve's; one re-binding per distinct λ below 1, each moving "
        "SPEC:SPEC-flash-duty only; a converged fingerprint carries the revision's identity"
    }
    return ledger.ok, value, expected


def _a11(ref: Mapping[str, Any], t03: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    scan = ref["policy_simulation"]["a02_family_scan"]
    failures = {
        (int(entry["T_target_K"]), float(entry["guess_K"])): entry
        for entry in scan["contract_failures"]
    }
    registered_attempts = {
        (int(entry["T_target_K"]), float(entry["guess_K"])): entry
        for entry in scan["contract_attempts"]
    }
    seen: dict[tuple[int, float], tuple[str, str | None, str, int | None]] = {}
    attempts: dict[tuple[int, float], dict[str, Any]] = {}
    for target in scan["targets_K"]:
        duty = edge3_fixtures.family_duty(int(target))
        for guess in scan["guesses_K"]:
            key = (int(target), float(guess))
            result = edge3_fixtures.plan_run(
                edge3_fixtures.document_for(float(guess), duty, f"FAM-{target}-{guess}"),
                SolvePolicy(policy_id="T04-FAM", residual_tolerances={}, scales={}),
            ).result
            step = region_step(result)
            contract = step.recovered_from.outcome if step.recovered_from else step.outcome
            trials = (
                len(step.detail.homotopy.trials) - 1 if step.detail.homotopy is not None else None
            )
            seen[key] = (contract, step.eo_recovery, result.outcome, trials)
            # A11 as amended (review S4, F16): the contract solve's attempts — the failed solve's
            # when edge 3 ran — as (signature, core outcome, iterations, decision), in order.
            solve = step.recovered_from if step.recovered_from is not None else step.detail
            attempts[key] = {
                "contract": contract,
                "attempts": [
                    [
                        ",".join(f"{unit}:{regime}" for unit, regime in item["signature"]),
                        item["core_outcome"],
                        item["iterations"],
                        item["decision"],
                    ]
                    for item in solve.branch_provenance
                ],
            }
    ledger.equal("runs", len(seen), scan["runs"])
    ledger.equal("contract-attempt records", sorted(attempts), sorted(registered_attempts))
    attempt_departures = [
        {"T_target_K": key[0], "guess_K": key[1], "measured": record, "registered": registered}
        for key, record in sorted(attempts.items())
        for registered in [registered_attempts.get(key)]
        if registered is None
        or record != {"contract": registered["contract"], "attempts": registered["attempts"]}
    ]
    ledger.equal("contract attempts departing from ref", attempt_departures, [])
    observed_failures = sorted(
        (key, entry) for key, entry in seen.items() if entry[:3] != ("CONVERGED", None, "CONVERGED")
    )
    ledger.equal(
        "contract failures",
        [(key, list(entry)) for key, entry in observed_failures],
        sorted(
            (key, [e["contract"], e["edge3"], e["outcome"], e["lambda_trials"]])
            for key, e in failures.items()
        ),
    )
    others = [entry for key, entry in seen.items() if key not in failures]
    ledger.true(
        "every other run converges by the contract alone, no recovery",
        all(entry == ("CONVERGED", None, "CONVERGED", None) for entry in others),
    )
    # T03's registered scan (75 runs, contained in this one): its two failures are HOM-01's and
    # HOM-02's, contract `ACTIVE_SET_CYCLING` here too.
    t03_failures = t03["policy_simulation"]["family_scan"]["largest_adjacent (registered)"][
        "failures"
    ]
    t03_keys = []
    for entry in t03_failures:
        match = re.match(r"T_heater=(\d+)K,guess=([\d.]+)K: (\w+)", entry)
        assert match is not None
        key = (int(match.group(1)), float(match.group(2)))
        t03_keys.append(key)
        ledger.equal(f"T03 failure {key}", seen.get(key, ("absent",))[0], match.group(3))
    value = {
        "runs": len(seen),
        "contract_failures": [
            {
                "T_target_K": key[0],
                "guess_K": key[1],
                "contract": entry[0],
                "edge3": entry[1],
                "outcome": entry[2],
                "lambda_trials": entry[3],
            }
            for key, entry in observed_failures
        ],
        "converged_by_the_contract_alone": len(others),
        "t03_registered_failures_here": {
            str(key): seen.get(key, ("absent",))[0] for key in t03_keys
        },
        "contract_attempt_records_compared": len(attempts),
        "contract_attempt_departures": attempt_departures,
        "departures": ledger.departures,
    }
    expected = {
        "runs": scan["runs"],
        "contract_failures": scan["contract_failures"],
        "converged_by_the_contract_alone": scan["runs"] - len(failures),
        "t03_registered_failures_here": t03_failures,
        "contract_attempt_records_compared": len(registered_attempts),
        "contract_attempt_departures": "none: every run's attempts equal "
        "ref.a02_family_scan.contract_attempts exactly",
    }
    return ledger.ok, value, expected


def _a12(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    event_validator = _validator("solve-event.schema.json")
    context_validator = _validator("attempt-context.schema.json")
    checkpoint_validator = _validator("checkpoint.schema.json")
    per_case: dict[str, Any] = {}
    for case_id in HOM:
        seen = Runs.direct(case_id)
        registered = ref["policy_simulation"]["homotopy_cases"][case_id]["homotopy"]
        steps = seen.trace.of_kind("homotopy_step")
        record = seen.record
        ledger.equal(f"{case_id}: homotopy_step per λ-trial", len(steps), len(record.trials))
        for event, trial in zip(steps, record.trials, strict=False):
            result = trial.corrector.result
            where = f"{case_id} λ-trial {trial.index}"
            ledger.equal(
                where,
                (
                    event.iteration,
                    event.lambda_value,
                    event.delta_lambda,
                    event.trial_status,
                    event.corrector_outcome,
                    event.corrector_iterations,
                    event.level_constants_sha256,
                    event.homotopy_level,
                ),
                (
                    trial.index,
                    str(trial.lambda_value),
                    str(trial.delta_lambda),
                    "accepted" if trial.accepted else "rejected",
                    result.outcome,
                    result.iterations,
                    trial.corrector.level_constants_sha256,
                    None,
                ),
            )
            ledger.true(
                f"{where}: λ and Δλ are p/q",
                bool(FRACTION.match(event.lambda_value) and FRACTION.match(event.delta_lambda)),
            )
            ledger.true(
                f"{where}: level digest is the target's exactly at λ = 1",
                bool(HEX64.fullmatch(event.level_constants_sha256))
                and (event.level_constants_sha256 == seen.target.metadata.constants_sha256)
                == (trial.lambda_value == 1),
            )
        messages = [e.message for e in steps]
        if seen.recovery.outcome == "HOMOTOPY_STALLED":
            closing = f"homotopy_stalled({steps[-1].corrector_outcome})"
            ledger.equal(f"{case_id}: messages", messages, [""] * (len(steps) - 1) + [closing])
            ledger.equal(f"{case_id}: solve message", seen.recovery.message, closing)
        else:
            ledger.equal(f"{case_id}: messages", messages, [""] * len(steps))

        # Every corrector event carries its λ-trial's index; the attempt opens and closes once.
        trial_index, unstamped = 0, []
        for event in seen.trace.events:
            if event.kind == "homotopy_step":
                trial_index = event.iteration + 1
            elif event.attempt == 0 and (
                event.kind in ("jacobian", "linear_solve", "trial", "step_accepted")
                or (event.kind == "attempt_closed" and event.homotopy_level is not None)
            ):
                if event.homotopy_level != trial_index:
                    unstamped.append(f"{event.kind} #{event.sequence}")
        ledger.equal(f"{case_id}: corrector events not stamped with their trial", unstamped, [])
        brackets = [
            e.kind
            for e in seen.trace.events
            if e.attempt == 0
            and e.homotopy_level is None
            and e.kind in ("attempt_opened", "attempt_closed")
        ]
        ledger.equal(
            f"{case_id}: the attempt's own brackets", brackets, ["attempt_opened", "attempt_closed"]
        )

        context = seen.recovery.contexts[0]
        continuation = {"type": ref["constants"]["homotopy"]["type"], "parameter_ids": [CONTINUED]}
        ledger.equal(
            f"{case_id}: context",
            (context.core, dict(context.continuation), context.as_document()["continuation"]),
            ("homotopy", continuation, continuation),
        )
        item = seen.recovery.branch_provenance[0]
        accepted = [str(s["lambda"]) for s in registered["steps"][1:] if s["accepted"]]
        ledger.equal(
            f"{case_id}: provenance continuation",
            item["continuation"],
            {
                **continuation,
                "lambda_levels": accepted,
                "lambda_reached": str(registered["lambda_reached"]),
                "rejected_trials": sum(1 for s in registered["steps"] if not s["accepted"]),
            },
        )
        ledger.equal(
            f"{case_id}: opening is the failed solve's item 0",
            item["opening_state_sha256"],
            seen.failed.branch_provenance[0]["opening_state_sha256"],
        )
        # §4.7 as amended (F16): the item's `iterations` counts every corrector.
        ledger.equal(
            f"{case_id}: provenance item iterations",
            item["iterations"],
            registered["provenance_item_iterations"],
        )
        r0_strings = [
            *messages,
            *item["continuation"]["lambda_levels"],
            item["continuation"]["lambda_reached"],
            *(str(i["cause"]) for i in seen.recovery.branch_provenance),
        ]
        carrying = [text for text in r0_strings if FLOAT.search(text)]
        ledger.equal(f"{case_id}: R0 strings carrying a float", carrying, [])

        invalid = 0
        for event in seen.trace.events:
            document = event.as_document()
            json.dumps(document, allow_nan=False)
            invalid += _errors(event_validator, document)
        invalid += sum(_errors(context_validator, c.as_document()) for c in seen.recovery.contexts)
        invalid += _errors(checkpoint_validator, seen.recovery.checkpoint.as_document())
        ledger.equal(f"{case_id}: schema errors", invalid, 0)
        per_case[case_id] = {
            "homotopy_steps": len(steps),
            "lambda_values": [e.lambda_value for e in steps],
            "last_message": messages[-1],
            "events": len(seen.trace.events),
            "context_core": context.core,
            "provenance_continuation": item["continuation"],
            "provenance_item_iterations": item["iterations"],
            "schema_errors": invalid,
        }
    value = {"cases": per_case, "departures": ledger.departures}
    expected = {
        "cases": "per case: one homotopy_step per λ-trial (easy endpoint included) with λ and "
        "Δλ as p/q, verdict, corrector outcome and count, the level digest; every corrector "
        "event stamped with its trial; context core homotopy with its continuation; the "
        "provenance continuation of ref's path and its iterations (the case's "
        "homotopy.provenance_item_iterations); homotopy_stalled(outcome) on a stall; no float "
        "in an R0 string; every document valid"
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------ A13–A18


def _a13(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.numerics.ptc import PTC_ROW_SIGN

    ledger = Ledger()
    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    holdup = ptc_fixtures.holdup_rows(item)
    places: dict[str, Any] = {}
    for where in ("P01 root (r = 0.95)", "OFF-A"):
        state = (
            ptc_fixtures.root(ptc_fixtures.HIGH)[0]
            if where.startswith("P01")
            else ptc_fixtures.start(item, "OFF-A")
        )
        entries = ptc_fixtures.region_mass(item).entries_at(
            state, item.flowsheet.provider, ptc_fixtures.context_of(item)
        )
        nonzero = {row for (row, _), value in entries.items() if value != 0.0}
        closed = ptc_fixtures.closed_form(state)
        worst = max(
            abs(value - closed.get(key, 0.0)) / max(1.0, abs(closed.get(key, 0.0)))
            for key, value in entries.items()
        )
        extra = sorted(
            f"{row} / {column}" for row, column in entries if (row, column) not in closed
        )
        places[where] = {
            "nonzero_rows": sorted(nonzero),
            "units": sorted({row.split(":")[0] for row in nonzero}),
            "entries": len(entries),
            "closed_form_entries_missing": sorted(
                f"{row} / {column}" for row, column in closed if (row, column) not in entries
            ),
            "worst_relative_error_vs_closed_form": worst,
            "entries_outside_the_table": extra,
            "entries_outside_the_table_values": [
                entries[tuple(key.split(" / "))]
                for key in extra  # type: ignore[index]
            ],
        }
        ledger.equal(f"{where}: nonzero-M rows", sorted(nonzero), sorted(holdup))
        ledger.equal(f"{where}: count", len(nonzero), 8)
        ledger.equal(f"{where}: units", places[where]["units"], ["U-FLASH", "U-HEAT"])
        ledger.equal(
            f"{where}: table entries missing", places[where]["closed_form_entries_missing"], []
        )
        ledger.true(f"{where}: every entry the closed form, 1e-9 relative", worst <= RELATIVE)
        ledger.equal(f"{where}: entries outside the table", extra, ["U-FLASH:FLASH-duty / S4.P"])
    definitions = sorted(
        str(path.relative_to(ROOT))
        for path in SOURCE.rglob("*.py")
        if "PTC_ROW_SIGN: Final" in path.read_text(encoding="utf-8")
        or "PTC_ROW_SIGN =" in path.read_text(encoding="utf-8")
    )
    readers = sorted(
        str(path.relative_to(ROOT))
        for path in SOURCE.rglob("*.py")
        if "PTC_ROW_SIGN" in path.read_text(encoding="utf-8")
    )
    ledger.equal("PTC_ROW_SIGN definitions", definitions, ["src/openflowsheet/numerics/ptc.py"])
    ledger.equal(
        "PTC_ROW_SIGN",
        dict(PTC_ROW_SIGN),
        {
            "holdup_balance": ref["constants"]["ptc"]["holdup_row_sign"],
            "zero_holdup_balance": 1,
            "algebraic": 1,
        },
    )
    value = {
        "places": places,
        "PTC_ROW_SIGN": dict(PTC_ROW_SIGN),
        "defined_in": definitions,
        "named_in": readers,
        "departures": ledger.departures,
    }
    expected = {
        "places": "the eight holdup_balance rows of U-HEAT and U-FLASH exactly; every entry "
        "T04 §6.3's closed form from the provider's enthalpies, 1e-9 relative (the vapour "
        "outlet's pressure entry the provider's declared zero)",
        "PTC_ROW_SIGN": "holdup_balance ref.constants.ptc.holdup_row_sign, the others +1",
        "defined_in": ["src/openflowsheet/numerics/ptc.py"],
    }
    return ledger.ok, value, expected


def _a14() -> tuple[bool, Any, Any]:
    from openflowsheet.verify.failure import bundle_for

    ledger = Ledger()
    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    first = ptc_fixtures.first_holdup_row(item)
    cases = {
        "ADV-04 an entry on a mixer row": (
            ptc_fixtures.mixer_double(),
            PtcPolicy(),
            "ptc_mapping_invalid(U-MIX:MIX-mole:A, not_holdup_balance)",
        ),
        "ADV-04 no FLASH-duty entry": (
            ptc_fixtures.flash_without_duty(),
            PtcPolicy(),
            "ptc_mapping_invalid(U-FLASH:FLASH-duty, missing)",
        ),
        "V1 no mapping at all": (None, PtcPolicy(), f"ptc_mapping_invalid({first}, missing)"),
        "V3 residence time 0": (
            "registered",
            PtcPolicy(residence_time_s=0.0),
            f"ptc_mapping_invalid({first}, residence_time)",
        ),
        "V4 a wrong dimension": (
            ptc_fixtures.wrong_dimension(),
            PtcPolicy(),
            f"ptc_mapping_invalid({first}, dimension)",
        ),
    }
    per_case: dict[str, Any] = {}
    for label, (mapping, ptc, message) in cases.items():
        trace = Trace()
        spied = ptc_fixtures.SpiedCompiled(item.compiled, trace)
        result = ptc_fixtures.solve(
            item,
            ptc_fixtures.start(item, "OFF-A"),
            ptc=ptc,
            trace=trace,
            mapping=mapping,
            compiled=spied,
        )
        bundle = bundle_for(
            SimpleNamespace(
                outcome=result.outcome,
                counters=result.counters,
                checkpoint=result.checkpoint,
                message=result.message,
                attempts=0,
                iterations=0,
                residual_inf=float("nan"),
            ),
            trace,
        )
        per_case[label] = {
            "outcome": result.outcome,
            "message": result.message,
            "attempts": len(result.attempts),
            "provenance_items": len(result.branch_provenance),
            "events": len(trace),
            "compiled_calls": len(spied.calls),
            "taxonomy": bundle.taxonomy,
            "action": bundle.suggested_actions[0].action,
        }
        ledger.equal(
            label,
            per_case[label],
            {
                "outcome": "PTC_MAPPING_INVALID",
                "message": message,
                "attempts": 0,
                "provenance_items": 0,
                "events": 0,
                "compiled_calls": 0,
                "taxonomy": "model domain/conservation/derivative defects",
                "action": "report_defect",
            },
        )
    newton = ptc_fixtures.solve(
        item, ptc_fixtures.start(item, "OFF-A"), core="newton", mapping=None
    )
    ledger.equal("Newton needs no mapping", newton.outcome, "CONVERGED")
    value = {
        "cases": per_case,
        "newton_without_a_mapping": newton.outcome,
        "departures": ledger.departures,
    }
    expected = {
        "cases": "each: PTC_MAPPING_INVALID with its ptc_mapping_invalid(row, check) message, no "
        "attempt, no event, no residual or Jacobian call; bundle class model domain/"
        "conservation/derivative defects, action report_defect (ADR 0010 D8)",
        "newton_without_a_mapping": "CONVERGED",
    }
    return ledger.ok, value, expected


def _a15() -> tuple[bool, Any, Any]:
    from openflowsheet.models.syn001 import ENERGY, MOLAR_FLOW, MOLE, POWER

    ledger = Ledger()
    theta = PtcPolicy().residence_time_s
    steps: dict[str, Any] = {}
    for case_id in (ptc_fixtures.NOMINAL, ptc_fixtures.HIGH):
        item = ptc_fixtures.case(case_id)
        state, regimes = ptc_fixtures.root(case_id)
        problem, free, rows, x = ptc_fixtures.ptc_problem_at(item, state, regimes)
        evaluation = problem.problem.residual(x)
        residual = float(
            np.max(np.abs(problem.problem.scaling.scale_residual(evaluation.values, rows)))
        )
        ledger.true(f"{case_id}: the root's scaled residual below 1e-14", residual < 1e-14)
        for tau in (1e-4, 1.0, 1e10):
            step = float(np.max(np.abs(ptc_fixtures.scaled_step(problem, free, x, tau))))
            bound = 1e-12 + 10.0 * (theta / tau) * residual
            steps[f"{case_id} dtau={tau:g}"] = {
                "root_residual_scaled": residual,
                "step_inf_scaled": step,
                "bound": bound,
            }
            ledger.true(f"{case_id} Δτ = {tau:g}: step within the bound", step <= bound)

    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    mapping = ptc_fixtures.syn001_residence_time(COMPONENTS)
    origins = {equation.equation_id: equation.origin for equation in item.spec.equations}
    dimensions: dict[str, Any] = {}
    for row in sorted(ptc_fixtures.holdup_rows(item)):
        model_id, _, equation_id = origins[row].partition("#")
        rule = mapping.rules[model_id]
        declared = rule.declared[equation_id]
        holdup = tuple(rule.holdups[equation_id].dimension)
        per_second = list(declared.dimension)
        per_second[2] += 1
        dimensions[row] = {
            "holdup": list(holdup),
            "manifest_holdup": list(declared.accumulation.holdup.dimension),
            "row": list(declared.dimension),
        }
        ledger.equal(
            f"{row}: holdup is the manifest's",
            holdup,
            tuple(declared.accumulation.holdup.dimension),
        )
        ledger.equal(f"{row}: holdup is the row's times seconds", holdup, tuple(per_second))
        ledger.equal(
            f"{row}: mol for a mole row, J for a duty row",
            holdup,
            tuple(MOLE if ":HEAT-mole:" in row or ":FLASH-mole:" in row else ENERGY),
        )
        ledger.true(
            f"{row}: the row is mol/s or W",
            tuple(declared.dimension) in (tuple(MOLAR_FLOW), tuple(POWER)),
        )
    value = {"steps_at_the_root": steps, "dimensions": dimensions, "departures": ledger.departures}
    expected = {
        "steps_at_the_root": "at r = 0.5 and 0.95, Δτ in {1e-4, 1, 1e10}: step at most "
        "1e-12 + 10 (θ/Δτ) times the root's scaled residual (F14)",
        "dimensions": "each holdup the manifest's, the row's times seconds: mol on the mole "
        "rows, J on the duty rows",
    }
    return ledger.ok, value, expected


def _a16() -> tuple[bool, Any, Any]:
    ledger = Ledger()
    plain_case = ptc_fixtures.case(ptc_fixtures.HIGH)
    shifted_case = ptc_fixtures.case(ptc_fixtures.HIGH, ptc_fixtures.ShiftedProvider())
    opened = ptc_fixtures.solve(
        plain_case, ptc_fixtures.start(plain_case, "OFF-A"), core="newton"
    ).opening
    state, regimes = dict(opened[0]), dict(opened[1])
    state["S3.liq.A"] += 0.1
    steps, duties = [], []
    for item in (plain_case, shifted_case):
        problem, free, rows, x = ptc_fixtures.ptc_problem_at(item, state, regimes)
        evaluation = problem.problem.residual(x)
        duties.append(float(evaluation.values[rows.index("U-HEAT:HEAT-duty")]))
        steps.append(ptc_fixtures.scaled_step(problem, free, x, 1.0))
    difference = float(np.max(np.abs(steps[0] - steps[1])))
    scale = float(np.max(np.abs(steps[0])))
    ledger.true(
        "the shift moves the heater duty residual (not vacuous)", abs(duties[0] - duties[1]) > 1.0
    )
    ledger.true("the step is unchanged, 1e-9 relative", difference <= RELATIVE * scale)
    value = {
        "shift_J_per_mol": ptc_fixtures.SHIFT,
        "heater_duty_residual_moved_W": abs(duties[0] - duties[1]),
        "step_difference_over_step": difference / scale,
        "departures": ledger.departures,
    }
    expected = {
        "heater_duty_residual_moved_W": "above 1 W",
        "step_difference_over_step": "at most 1e-9",
    }
    return ledger.ok, value, expected


def _a17(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    pole = -1.0 / PtcPolicy().residence_time_s
    per_case: dict[str, Any] = {}
    for case_id, key in ((ptc_fixtures.NOMINAL, "r=0.50"), (ptc_fixtures.HIGH, "r=0.95")):
        modes = ptc_fixtures.pencil_modes(case_id)
        registered = [
            float(v) for v in ref["closed_form"]["loop_modes"][key]["finite_modes_per_second"]
        ]
        pair = [v for v in modes if abs(v - pole) <= 1e-6 * abs(pole)]
        simple = sorted((v for v in modes if v not in pair), key=lambda v: v.real)
        targets = [t for t in registered if t != pole]
        ledger.equal(f"{key}: finite modes", len(modes), len(registered))
        ledger.equal(f"{key}: Jordan pair at −1/θ", (len(pair), registered.count(pole)), (2, 2))
        ledger.true(
            f"{key}: the pair's mean is −1/θ, 1e-9",
            abs(sum(pair) / 2 - pole) <= RELATIVE * abs(pole),
        )
        worst = 0.0
        for value, target in zip(simple, targets, strict=False):
            ledger.true(f"{key}: {target} real", abs(value.imag) <= RELATIVE * abs(value))
            ledger.true(f"{key}: {target} stable", value.real < 0.0)
            worst = max(worst, abs(value - target) / abs(target))
        ledger.true(f"{key}: simple modes equal ref, 1e-9 relative", worst <= RELATIVE)
        per_case[key] = {
            "modes": [plain(v) for v in modes],
            "pair_members_offset_from_minus_1_over_theta": [abs(v - pole) for v in pair],
            "simple_worst_relative_error": worst,
        }
    value = {"cases": per_case, "departures": ledger.departures}
    expected = {
        "cases": {
            key: ref["closed_form"]["loop_modes"][key]["finite_modes_per_second"]
            for key in ("r=0.50", "r=0.95")
        },
        "tolerance": "simple modes and the pair's mean 1e-9 relative; each pair member 1e-6 "
        "relative of −1/θ (F14)",
    }
    return ledger.ok, value, expected


def _a18() -> tuple[bool, Any, Any]:
    ledger = Ledger()
    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    registered = PtcPolicy()
    scaled = replace(
        registered,
        residence_time_s=8.0 * registered.residence_time_s,
        tau_initial_s=8.0 * registered.tau_initial_s,
        tau_min_s=8.0 * registered.tau_min_s,
        tau_max_s=8.0 * registered.tau_max_s,
    )
    base = ptc_fixtures.solve(item, ptc_fixtures.start(item, "OFF-A"))
    eight = ptc_fixtures.solve(item, ptc_fixtures.start(item, "OFF-A"), ptc=scaled)
    ledger.equal("outcomes", (base.outcome, eight.outcome), ("CONVERGED", "CONVERGED"))
    ledger.equal(
        "pseudo-step counts",
        [a.iterations for a in eight.attempts],
        [a.iterations for a in base.attempts],
    )
    differing = 0
    for one, other in zip(base.attempts, eight.attempts, strict=False):
        for a, b in zip(one.ptc.steps, other.ptc.steps, strict=False):
            if not (np.array_equal(a.x, b.x) and b.tau == 8.0 * a.tau and a.alpha == b.alpha):
                differing += 1
    ledger.equal("accepted states not bit-identical (or Δτ not ×8, or α different)", differing, 0)
    states = sum(1 for name in base.state if base.state[name] != eight.state[name])
    ledger.equal("final state entries that differ", states, 0)
    value = {
        "outcomes": [base.outcome, eight.outcome],
        "pseudo_steps": [
            [a.iterations for a in base.attempts],
            [a.iterations for a in eight.attempts],
        ],
        "accepted_steps_compared": sum(len(a.ptc.steps) for a in base.attempts),
        "departures": ledger.departures,
    }
    expected = {
        "outcomes": ["CONVERGED", "CONVERGED"],
        "pseudo_steps": "equal",
        "accepted_steps_compared": "every one bit-identical, Δτ exactly ×8",
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------ A19–A25


def _seed_trajectory(
    runs: Runs, ref: Mapping[str, Any], name: str
) -> tuple[Ledger, dict[str, Any]]:
    """A19 for one seed: everything `ref.ptc_seeds.<name>` fixes, trial by trial."""
    ledger = Ledger()
    registered = ref["policy_simulation"]["ptc_seeds"][name]
    outcome, attempts, _ = runs.seed(name)
    ledger.equal("outcome", outcome, registered["outcome"])
    ledger.equal("attempts", len(attempts), len(registered["attempts"]))
    worst = {"tau": 0.0, "alpha": 0.0, "x": 0.0, "tau_next": 0.0, "phi_over_allowance": 0.0}
    rows = []
    for k, (attempt, expected) in enumerate(zip(attempts, registered["attempts"], strict=False)):
        where = f"attempt {k}"
        ledger.equal(
            where,
            (
                attempt.regime,
                attempt.result.outcome,
                attempt.result.iterations,
                list(attempt.result.blocked_by),
            ),
            (
                expected["regime"],
                expected["outcome"],
                expected["pseudo_steps"],
                expected["blocked_by"],
            ),
        )
        seen = seed_fixtures.events(attempt.record)
        ledger.equal(f"{where}: trials", len(seen), len(expected["events"]))
        ledger.equal(
            f"{where}: the order and verdict of every trial",
            [(step, result) for step, _, _, result, _ in seen],
            [(event["step"], event["result"]) for event in expected["events"]],
        )
        for (step, _, tau, _, accepted), event in zip(seen, expected["events"], strict=False):
            there = f"{where} pseudo-step {step}"
            target = float(event["tau"])
            worst["tau"] = max(worst["tau"], abs(tau - target) / abs(target))
            ledger.close(f"{there}: Δτ", tau, target, absolute=SEED_RELATIVE * abs(target))
            if accepted is None:
                continue
            (x,) = event["x"].values()
            alpha = float(event["alpha"])
            worst["alpha"] = max(worst["alpha"], abs(accepted.alpha - alpha) / abs(alpha))
            ledger.close(f"{there}: α", accepted.alpha, alpha, absolute=SEED_RELATIVE * abs(alpha))
            worst["x"] = max(
                worst["x"], abs(float(accepted.x[0]) - float(x)) / max(1.0, abs(float(x)))
            )
            ledger.close(f"{there}: x", float(accepted.x[0]), x, relative=SEED_RELATIVE)
            if event["tau_next"] is None:
                ledger.equal(
                    f"{there}: at the stop", (accepted.tau_next, accepted.ser_ratio), (None, None)
                )
            else:
                proposal = float(event["tau_next"])
                worst["tau_next"] = max(
                    worst["tau_next"], abs(accepted.tau_next - proposal) / proposal
                )
                ledger.close(
                    f"{there}: Δτ next",
                    accepted.tau_next,
                    proposal,
                    absolute=SEED_RELATIVE * proposal,
                )
            phi = float(event["phi"])
            allowance = max(SEED_RELATIVE * abs(phi), PHI_ABSOLUTE)
            worst["phi_over_allowance"] = max(
                worst["phi_over_allowance"], abs(accepted.phi - phi) / allowance
            )
            ledger.close(f"{there}: φ", accepted.phi, phi, absolute=allowance)
        rows.append(
            {
                "regime": attempt.regime,
                "outcome": attempt.result.outcome,
                "pseudo_steps": attempt.result.iterations,
                "trials": len(seen),
                "blocked_by": list(attempt.result.blocked_by),
            }
        )
    return ledger, {"outcome": outcome, "attempts": rows, "worst_relative": worst}


def _a19(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    per_seed: dict[str, Any] = {}
    for name in SEEDS:
        seed_ledger, per_seed[name] = _seed_trajectory(runs, ref, name)
        ledger.departures += [f"{name} {entry}" for entry in seed_ledger.departures]
    # PTC-S1's Δτ are exact powers of two, and PTC-S4 lands on +0.0 by its bit pattern.
    _, (s1,), _ = runs.seed("PTC-S1")
    powers = [step.tau == 2.0**step.index for step in s1.record.steps]
    ledger.true("PTC-S1: Δτ_k = 2^k exactly", all(powers) and bool(powers))
    _, (s4,), _ = runs.seed("PTC-S4")
    landed = [step for step in s4.record.steps if step.landing]
    positive_zero = [
        float(step.x[0]) == 0.0 and math.copysign(1.0, float(step.x[0])) == 1.0 for step in landed
    ]
    ledger.equal("PTC-S4: landings on +0.0", positive_zero, [True])
    per_seed["PTC-S1"]["tau_exact_powers_of_two"] = all(powers)
    per_seed["PTC-S4"]["landing_bits"] = [float(step.x[0]).hex() for step in landed]
    value = {"seeds": per_seed, "departures": ledger.departures}
    expected = {
        "seeds": {
            name: {
                "outcome": ref["policy_simulation"]["ptc_seeds"][name]["outcome"],
                "pseudo_steps": [
                    a["pseudo_steps"]
                    for a in ref["policy_simulation"]["ptc_seeds"][name]["attempts"]
                ],
            }
            for name in SEEDS
        },
        "tolerance": "outcomes, counts, reasons and their order, blocked_by exact; Δτ, α, x "
        "1e-12 relative; φ max(1e-12 relative, 1e-15) (F13); PTC-S1's Δτ exact powers of two; "
        "PTC-S4's landing 0x0.0p+0",
    }
    return ledger.ok, value, expected


#: Spec §9.9's rows that neither a policy value nor one of the core's two ablation seams (`sign`,
#: the per-attempt reset) can express. `ref` registers each; the implementation has no seam to run
#: them, and none is added here — that would put an unregistered rule into the core (the tests'
#: stated reason, `tests/test_t04_ptc.py`).
#: Spec A20 as amended (F16): the rows with no seam in production code, each discharged by an
#: assertion that already pins the value its ablation would change.
_DISCHARGED_ABLATIONS = {
    "stop_on_phi_floor (PTC-S1)": ("A19", "PTC-S1"),
    "proposed_tau_in_update (PTC-S2)": ("A19", "PTC-S2"),
    "rejected_residual_in_ratio (PTC-S2)": ("A19", "PTC-S2"),
}


def _a20(runs: Runs, ref: Mapping[str, Any], checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    description = (
        "Ablations, spec §9.9 row by row against `ref.policy_simulation.ablations` (A20 as "
        "amended, F16). Measured here: the γ clip removed (PTC-S1), σ = +1 (PTC-S1; its first "
        "matrix exactly singular, then bound_blocked), τ_max = 16 (a policy override), no reset "
        "on restart (PTC-S5), φ_floor removed (every seed, inert: no count or Δτ changes); λ "
        "growth 1, λ shrink 0 (stall on the first rejection), corrector cap 50 (HOM-01, HOM-04: "
        "inert), Δλ₀ in {1, 1/2, 1/8} (not fitted), edge 3 from the failed end state (HOM-01: "
        "HOMOTOPY_STALLED at λ = 0); the polish row by A22's unpolished OFF-B stop, the mapping "
        "row by A14, the trigger-set row by A09. Discharged, with no seam in production code: "
        "the rollback row by A07 (F15: the reported state against the ablated one); the stop on "
        "‖F̂‖ ≤ φ_floor, the proposed Δτ in the update and a rejected residual in the ratio by "
        "A19 (each ablated count differs from the seed count A19 registers); the stream-total "
        "heater holdup by A13 and A16. `pass` when every measured row agrees and every "
        "discharging assertion passes."
    )
    try:
        ok, value, expected = _a20_measured(runs, ref)
    except Exception as error:  # noqa: BLE001
        return check(
            "T04.A20", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    results = {entry["id"]: entry["result"] for entry in checks}
    ablations = ref["policy_simulation"]["ablations"]
    seeds = ref["policy_simulation"]["ptc_seeds"]
    discharged: list[dict[str, Any]] = []
    for row, (assertion, seed) in _DISCHARGED_ABLATIONS.items():
        ablated = ablations[row]["pseudo_steps"]
        pinned = [attempt["pseudo_steps"] for attempt in seeds[seed]["attempts"]]
        entry = {
            "row": row,
            "ablated_pseudo_steps": ablated,
            "discharged_by": f"T04.{assertion}",
            "registered_by_it": {seed: pinned},
            "differs": ablated != pinned,
            "discharging_result": results.get(f"T04.{assertion}"),
        }
        discharged.append(entry)
    rollback = value["rows"]["no_rollback (HOM-04), by A07"]
    discharged.append(
        {
            "row": "no_rollback (HOM-04)",
            "ablated_S3_T_K": rollback["ablated_S3_T_K"],
            "discharged_by": "T04.A07",
            "registered_by_it": "the last accepted root to 1e-9 relative",
            "differs": rollback["ablated_off_the_registered_end_relative"] > RELATIVE,
            "discharging_result": results.get("T04.A07"),
        }
    )
    discharged.append(
        {
            "row": "phase-resolved heater mole holdup vs the stream total S3.n",
            "ablated": "spec §9.9 / §6.2: a step that moves off the split manifold (> 1e-6 "
            "scaled, generator-checked) with entries on S3.n",
            "discharged_by": ["T04.A13", "T04.A16"],
            "registered_by_it": "A13: the phase-resolved entries on S3.vap / S3.liq; A16: the "
            "step invariant to 1e-9 relative",
            "differs": True,
            "discharging_result": [results.get("T04.A13"), results.get("T04.A16")],
        }
    )
    discharged_ok = all(
        entry["differs"]
        and all(
            result == "pass"
            for result in (
                entry["discharging_result"]
                if isinstance(entry["discharging_result"], list)
                else [entry["discharging_result"]]
            )
        )
        for entry in discharged
    )
    value["discharged"] = discharged
    expected["discharged"] = (
        "each row's ablated value differs from what its discharging assertion registers, and that "
        "assertion passes"
    )
    return check("T04.A20", description, verdict(ok and discharged_ok), value, expected)


def _a20_measured(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, dict[str, Any], Any]:
    from openflowsheet.numerics.ptc import PTC_ROW_SIGN

    ledger = Ledger()
    ablations = ref["policy_simulation"]["ablations"]
    settings = seed_fixtures.SETTINGS
    plus_one = {"holdup_balance": 1, "zero_holdup_balance": 1, "algebraic": 1}
    rows: dict[str, Any] = {}
    for name, seed, policy, reset, sign in (
        (
            "no_gamma_clip (PTC-S1)",
            "PTC-S1",
            replace(settings, gamma_min=0.0, gamma_max=math.inf),
            True,
            PTC_ROW_SIGN,
        ),
        ("row_sign_plus_one (PTC-S1)", "PTC-S1", settings, True, plus_one),
        (
            "tau_max_16 (PTC-S1, a policy override, not an ablation)",
            "PTC-S1",
            replace(settings, tau_max_s=16.0),
            True,
            PTC_ROW_SIGN,
        ),
        ("no_reset_on_restart (PTC-S5)", "PTC-S5", settings, False, PTC_ROW_SIGN),
    ):
        outcome, attempts = seed_fixtures.run_seed(seed, policy, reset=reset, sign=sign)
        rows[name] = {"outcome": outcome, "pseudo_steps": [a.result.iterations for a in attempts]}
        ledger.equal(
            name, rows[name], {key: ablations[name][key] for key in ("outcome", "pseudo_steps")}
        )
        if name.startswith("row_sign"):
            (attempt,) = attempts
            reasons = [r.reason for r in attempt.record.rejections]
            rows[name]["rejection_reasons"] = reasons
            ledger.equal(
                f"{name}: the first matrix exactly singular, then bound_blocked",
                reasons[:1] + sorted(set(reasons[1:])),
                ["linear_solve_failed", "bound_blocked"],
            )
    unfloored: dict[str, bool] = {}
    for seed in SEEDS:
        registered = [
            (a.result.iterations, [s.tau for s in a.record.steps]) for a in runs.seed(seed)[1]
        ]
        removed = [
            (a.result.iterations, [s.tau for s in a.record.steps])
            for a in seed_fixtures.run_seed(seed, replace(settings, phi_floor=0.0))[1]
        ]
        unfloored[seed] = removed == registered
    rows["no_phi_floor (every seed)"] = {"no_count_or_tau_changes": unfloored}
    ledger.equal("φ_floor removed changes nothing", unfloored, dict.fromkeys(SEEDS, True))
    ledger.equal(
        "no_phi_floor registered outcome",
        ablations["no_phi_floor (every seed)"]["outcome"],
        ref["policy_simulation"]["ptc_seeds"]["PTC-S1"]["outcome"],
    )

    for name, case_id, homotopy in (
        ("no_growth (HOM-01)", "HOM-01", HomotopyPolicy(growth=1)),
        ("no_shrink (HOM-04)", "HOM-04", HomotopyPolicy(shrink=Fraction(0))),
        ("corrector_cap_50 (HOM-01)", "HOM-01", HomotopyPolicy(corrector_max_iterations=50)),
        ("corrector_cap_50 (HOM-04)", "HOM-04", HomotopyPolicy(corrector_max_iterations=50)),
        (
            "delta_lambda_initial_1 (HOM-01, sensitivity)",
            "HOM-01",
            HomotopyPolicy(delta_lambda_initial=Fraction(1)),
        ),
        (
            "delta_lambda_initial_1/2 (HOM-01, sensitivity)",
            "HOM-01",
            HomotopyPolicy(delta_lambda_initial=Fraction(1, 2)),
        ),
        (
            "delta_lambda_initial_1/8 (HOM-01, sensitivity)",
            "HOM-01",
            HomotopyPolicy(delta_lambda_initial=Fraction(1, 8)),
        ),
    ):
        seen = homotopy_fixtures.direct(
            case_id, homotopy_fixtures.case_policy(case_id, homotopy=homotopy)
        )
        registered = ablations[name]
        measured_row: dict[str, Any] = {"outcome": seen.recovery.outcome}
        if "lambda_trials" in registered:
            measured_row["lambda_trials"] = len(seen.record.trials) - 1
        if "lambda_reached" in registered:
            measured_row["lambda_reached"] = str(seen.record.lambda_reached)
        ledger.equal(name, measured_row, {key: registered[key] for key in measured_row})
        if "end_S3_T_K" in registered:
            # `ref` prints these to 1e-9 K.
            measured_row["end_S3_T_K"] = seen.recovery.state["S3.T"]
            ledger.close(
                f"{name}: end S3.T",
                seen.recovery.state["S3.T"],
                registered["end_S3_T_K"],
                absolute=1e-8,
            )
        rows[name] = measured_row
    edge = homotopy_fixtures.direct("HOM-01", from_end_state=True)
    rows["edge3_from_failed_end_state (HOM-01)"] = {
        "outcome": edge.recovery.outcome,
        "lambda_reached": str(edge.record.lambda_reached),
    }
    ledger.equal(
        "edge3_from_failed_end_state (HOM-01)",
        rows["edge3_from_failed_end_state (HOM-01)"],
        ablations["edge3_from_failed_end_state (HOM-01)"],
    )

    # The rollback row, discharged by A07: the reported state is the last accepted root, and the
    # ablated boundary state lies outside A07's 1e-9 relative (F15).
    reported = runs.plan("HOM-04").result.state["S3.T"]
    ablated = float(ablations["no_rollback (HOM-04)"]["end_S3_T_K"])
    registered_end = float(
        ref["policy_simulation"]["homotopy_cases"]["HOM-04"]["homotopy"]["end_S3_T_K"]
    )
    rows["no_rollback (HOM-04), by A07"] = {
        "reported_S3_T_K": reported,
        "ablated_S3_T_K": ablated,
        "ablated_off_the_registered_end_relative": abs(ablated - registered_end) / registered_end,
    }
    ledger.true(
        "the rollback ablation's state is outside A07's tolerance",
        abs(ablated - registered_end) > RELATIVE * registered_end,
    )
    ledger.close("HOM-04 reported S3.T", reported, registered_end)

    # The polish row: A22's unpolished OFF-B stop, K04 `FAILED` by its envelope rule.
    from openflowsheet.verify.certificate import verify

    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    result, _ = runs.named("r=0.95/OFF-B")
    last = result.attempts[-1]
    stopped = verify(
        item.flowsheet,
        result,
        state=ptc_fixtures.full(item, result, last.ptc.stopped_x, last.signature),
    )
    rows["polish none (OFF-B r = 0.95), by A22"] = stopped.verification_status
    ledger.equal("unpolished OFF-B verdict", stopped.verification_status, "FAILED")
    value = {"rows": rows, "departures": ledger.departures}
    expected = {
        "rows": {name: ablations[name] for name in ablations if name not in _DISCHARGED_ABLATIONS},
    }
    return ledger.ok, value, expected


def _a21(runs: Runs) -> tuple[bool, Any, Any]:
    """§6.5 on every registered SYN-001 PTC run: the four named runs, the 18 admitted basin starts
    under PTC (A23) and PHS-05 under PTC (A24) — the tests check the named runs only (review S3)."""
    ledger = Ledger()
    theta = PtcPolicy().residence_time_s
    eps = float(np.finfo(np.float64).eps)
    high = ptc_fixtures.case(ptc_fixtures.HIGH)
    phs05 = runs.phs05()
    solves: list[tuple[str, Any, Any]] = [
        (key, ptc_fixtures.case(ptc_fixtures.NAMED_RUNS[key][0]), runs.named(key)[0])
        for key in NAMED
    ]
    # The basin harness binds the registered revision; its region is `case(HIGH)`'s, id for id.
    solves += [
        (f"basin {start.magnitude:g} {list(start.quarters)}", high, start.runs["ptc"].result)
        for start in runs.basin().admitted
    ]
    solves.append(
        (
            "PHS-05/ptc",
            SimpleNamespace(
                flowsheet=phs05.item.binding.flowsheet,
                spec=phs05.item.binding.spec,
                region=phs05.region,
                compiled=compile_problem(phs05.item.binding.spec),
            ),
            phs05.failed,
        )
    )
    per_run: dict[str, Any] = {}
    for key, item, result in solves:
        defects = ptc_fixtures.identity_defects(item, result)
        ratios = [
            entry.defect / (RELATIVE * entry.scale + 1e-13 * (1.0 + theta / entry.tau))
            for entry in defects
        ]
        floor = [entry.defect / (4.0 * eps * entry.operands) for entry in defects if entry.operands]
        per_run[key] = {
            "identities_checked": len(defects),
            "largest_defect_mol_per_s": max(entry.defect for entry in defects),
            "largest_defect_over_the_registered_bound": max(ratios),
            "largest_defect_over_four_ulps_of_its_operands": max(floor) if floor else 0.0,
        }
        ledger.true(f"{key}: every identity within §12's bound", max(ratios) <= 1.0)
    value = {
        "runs": per_run,
        "identities_checked": sum(entry["identities_checked"] for entry in per_run.values()),
        "largest_defect_over_the_registered_bound": max(
            entry["largest_defect_over_the_registered_bound"] for entry in per_run.values()
        ),
        "departures": ledger.departures,
    }
    expected = {
        "runs": "the four named runs, the 18 admitted basin starts under PTC and PHS-05 under PTC",
        "largest_defect_over_the_registered_bound": "at most 1: |lhs − rhs| at most "
        "1e-9 max(|F_r(x_k)|, |F_r(x_k+1)|, tol_r) + 1e-13 (1 + θ/Δτ) mol/s (F14) on every "
        "accepted pseudo-step and mole row",
    }
    return ledger.ok, value, expected


def _a22(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.certificate import verify
    from openflowsheet.verify.checks import material_checks

    ledger = Ledger()
    named = ref["policy_simulation"]["ptc_named"]
    per_run: dict[str, Any] = {}
    for key in NAMED:
        item = ptc_fixtures.case(ptc_fixtures.NAMED_RUNS[key][0])
        result, trace = runs.named(key)
        last = result.attempts[-1]
        polish_trials = [
            (e.message, e.trial_status, e.pseudo_step)
            for e in trace.of_kind("trial")
            if e.message.startswith("polish")
        ]

        def envelope(
            state: Mapping[str, float], split: float = item.flowsheet.split_fraction
        ) -> float:
            return max(
                abs(c.value) / c.tolerance
                for c in material_checks(state, split)
                if c.id.startswith("material_balance.envelope") and c.value is not None
            )

        stopped_state = ptc_fixtures.full(item, result, last.ptc.stopped_x, last.signature)
        unpolished = envelope(stopped_state)
        registered = str(named[key]["ptc"]["unpolished_envelope_over_tolerance"])
        digits = len(registered.split(".")[1])
        polished = verify(item.flowsheet, result)
        stopped = verify(item.flowsheet, result, state=stopped_state)
        per_run[key] = {
            "polish": last.ptc.polish,
            "polish_trials": [list(entry) for entry in polish_trials],
            "unpolished_envelope_over_tolerance": unpolished,
            "polished_envelope_over_tolerance": envelope(result.state),
            "polished_verdict": [polished.verification_status, polished.false_success_detected],
            "polished_tear": polished.transformations["tear"],
            "unpolished_verdict": [stopped.verification_status, stopped.false_success_detected],
            "unpolished_failing": sorted(c.id for c in stopped.checks if c.result == "fail"),
        }
        ledger.equal(f"{key}: polish", last.ptc.polish, named[key]["ptc"]["attempts"][-1]["polish"])
        ledger.equal(
            f"{key}: one polish trial, accepted", polish_trials, [("polish", "accepted", None)]
        )
        ledger.close(
            f"{key}: unpolished envelope / τ",
            unpolished,
            registered,
            absolute=0.5 * 10.0**-digits,
        )
        ledger.true(f"{key}: polished envelope at roundoff", envelope(result.state) < 1e-6)
        ledger.equal(
            f"{key}: polished verdict", per_run[key]["polished_verdict"], ["VERIFIED", False]
        )
        ledger.equal(
            f"{key}: polished tear empty",
            polished.transformations["tear"],
            {"variable_ids": [], "row_ids": []},
        )
        ledger.equal(
            f"{key}: fingerprint the solve's", polished.root_fingerprint, result.root_fingerprint
        )
        if key == "r=0.95/OFF-B":
            ledger.true("OFF-B: unpolished envelope at least 1.3 τ", unpolished >= 1.3)
            ledger.equal(
                "OFF-B unpolished",
                (per_run[key]["unpolished_verdict"], per_run[key]["unpolished_failing"]),
                (["FAILED", True], ["material_balance.envelope.C"]),
            )
        else:
            ledger.equal(f"{key}: unpolished verdict", stopped.verification_status, "VERIFIED")
    seeds: dict[str, Any] = {}
    for name in SEEDS:
        outcome, attempts, _ = runs.seed(name)
        final = attempts[-1]
        stop = final.result.outcome == "CONVERGED" and final.result.iterations >= 1
        seeds[name] = {"stopped_after_a_pseudo_step": stop, "polish": final.record.polish}
        ledger.equal(f"{name}: polish", final.record.polish, "accepted" if stop else None)
    value = {"named_runs": per_run, "seeds": seeds, "departures": ledger.departures}
    expected = {
        "named_runs": {
            key: {
                "polish": "accepted, one trial `polish` with no pseudo-step",
                "unpolished_envelope_over_tolerance": named[key]["ptc"][
                    "unpolished_envelope_over_tolerance"
                ],
                "polished_verdict": ["VERIFIED", False],
                "unpolished_verdict": (
                    "FAILED, false success, material_balance.envelope.C"
                    if key == "r=0.95/OFF-B"
                    else "VERIFIED"
                ),
            }
            for key in NAMED
        },
        "seeds": "every stop after at least one pseudo-step polished, accepted",
    }
    return ledger.ok, value, expected


def _named_attempts(
    ledger: Ledger, where: str, result: Any, registered: Mapping[str, Any], core: str
) -> list[dict[str, Any]]:
    """One run's attempts against `ref`'s record, per §12's conventions, every departure named."""
    ledger.equal(f"{where}: outcome", result.outcome, registered["outcome"])
    ledger.equal(f"{where}: attempts", len(result.attempts), len(registered["attempts"]))
    rows = []
    for k, (attempt, item, expected) in enumerate(
        zip(result.attempts, result.branch_provenance, registered["attempts"], strict=False)
    ):
        there = f"{where} attempt {k}"
        row: dict[str, Any] = {
            "signature": signature_text(attempt.signature),
            "opening_source": item["opening_source"],
            "core": item["core"],
            "core_outcome": attempt.solver_outcome,
            "iterations": attempt.iterations,
            "decision": item["decision"],
        }
        ledger.equal(there, row, {name: expected[name] for name in row})
        ledger.equal(
            f"{there}: provenance agrees",
            (item["core_outcome"], item["iterations"]),
            (attempt.solver_outcome, attempt.iterations),
        )
        _cause_ok(ledger, there, item["cause"], expected["cause"], result.message)
        if core == "ptc":
            row["rejected_trials"] = len(attempt.ptc.rejections)
            row["polish"] = attempt.ptc.polish
            ledger.equal(
                f"{there}: rejected trials, polish",
                (row["rejected_trials"], row["polish"]),
                (expected["rejected_trials"], expected["polish"]),
            )
            landings = [s for s in attempt.ptc.steps if s.landing]
            registered_landings = expected.get("landings") or []
            ledger.equal(f"{there}: landings", len(landings), len(registered_landings))
            for step, landing in zip(landings, registered_landings, strict=False):
                ledger.equal(
                    f"{there}: landing",
                    (step.index, list(step.landing)),
                    (landing["iteration"], landing["variables"]),
                )
                ledger.close(f"{there}: α_max", step.alpha, landing["alpha_max"])
                row["alpha_max"] = step.alpha
        if expected.get("blocked_by"):
            ledger.equal(f"{there}: BOUND_BLOCKED", attempt.solver_outcome, "BOUND_BLOCKED")
        rows.append(row)
    return rows


def _a23(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from benchmarks.t04.basin import criterion, lattice_guesses

    ledger = Ledger()
    registered = ref["policy_simulation"]["basin_comparison_r095"]
    basin = runs.basin()
    guesses = lattice_guesses()
    ledger.equal("lattice", len(guesses), len(registered))
    for (magnitude, quarters, _), entry in zip(guesses, registered, strict=False):
        ledger.equal(
            "lattice order",
            (magnitude, list(quarters)),
            (float(entry["magnitude_mol_per_s"]), entry["direction_quarters"]),
        )
    refused, admitted = 0, 0
    successes: dict[str, set[int]] = {"newton": set(), "ptc": set()}
    for index, (start, entry) in enumerate(zip(basin.starts, registered, strict=False)):
        where = f"start {start.magnitude:g} {list(start.quarters)}"
        if entry.get("start") == "refused_by_the_mixer":
            refused += 1
            ledger.true(
                f"{where}: refused by U-MIX", str(start.refused).startswith("unsupported: U-MIX:")
            )
            ledger.equal(f"{where}: nothing run", len(start.runs), 0)
            continue
        admitted += 1
        ledger.equal(f"{where}: admitted", start.refused, None)
        for core in ("newton", "ptc"):
            run, expected = start.runs[core], entry[core]
            measured_run = {
                "outcome": run.outcome,
                "attempts": [list(a) for a in run.attempts],
                "same_root": run.same_root,
            }
            if core == "ptc":
                measured_run["polish"] = run.polish
            ledger.equal(
                f"{where} {core}", measured_run, {name: expected[name] for name in measured_run}
            )
            if run.outcome == "CONVERGED":
                successes[core].add(index)
    fields = criterion(frozenset(successes["newton"]), frozenset(successes["ptc"]))
    study = registry_fixtures.CASES["SYN-001-high-recycle-ptc-basin"]["expected"]
    ledger.equal(
        "criterion (§8.1)",
        (fields["verdict"], fields["v14_qualified_ptc_clause"]),
        (study["verdict"], study["v14_qualified_ptc_clause"]),
    )

    named = ref["policy_simulation"]["ptc_named"]
    per_run: dict[str, Any] = {}
    for key in NAMED:
        item = ptc_fixtures.case(ptc_fixtures.NAMED_RUNS[key][0])
        per_run[key] = {}
        for core in ("newton", "ptc"):
            result, _ = runs.named(key, core)
            rows = _named_attempts(ledger, f"{key}/{core}", result, named[key][core], core)
            disagreement = region_fixtures.disagreement(item, result.state)
            ledger.equal(f"{key}/{core}: final state vs P01's root", disagreement, [])
            per_run[key][core] = {
                "outcome": result.outcome,
                "attempts": rows,
                "vs_P01": disagreement,
            }
    value = {
        "lattice": len(guesses),
        "refused_by_the_mixer": refused,
        "admitted": admitted,
        "converged": {core: len(found) for core, found in successes.items()},
        "criterion": fields,
        "named_runs": per_run,
        "departures": ledger.departures,
    }
    expected = {
        "lattice": len(registered),
        "refused_by_the_mixer": sum(
            1 for e in registered if e.get("start") == "refused_by_the_mixer"
        ),
        "admitted": sum(1 for e in registered if e.get("start") != "refused_by_the_mixer"),
        "starts": "each admitted start's Newton and PTC outcome, attempt signatures, counts, "
        "same_root and polish equal ref.basin_comparison_r095",
        "criterion": {
            "verdict": study["verdict"],
            "v14_qualified_ptc_clause": study["v14_qualified_ptc_clause"],
        },
        "named_runs": "ref.ptc_named, both cores; every final state P01's root by T02 A28's "
        "per-kind allowances",
    }
    return ledger.ok, value, expected


def _a24(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    import scipy.sparse as sp

    from openflowsheet.numerics.linear import solve_linear

    ledger = Ledger()
    registered = ref["policy_simulation"]["ptc_phs05"]
    run = runs.phs05()
    result = run.failed
    rows = _named_attempts(ledger, "PHS-05/ptc", result, registered, "ptc")
    reasons = [sorted({r.reason for r in attempt.ptc.rejections}) for attempt in result.attempts]
    first = result.attempts[0].ptc
    (landing,) = [step for step in first.steps if step.landing]
    newton_alpha = ref["policy_simulation"]["homotopy_cases"]["HOM-01"]["contract"]["attempts"][0][
        "landings"
    ][0]["alpha_max"]
    ledger.close("the first pseudo-step's α_max is Newton's", landing.alpha, newton_alpha)

    opened = result.opening
    state, regimes = dict(opened[0]), dict(opened[1])
    item = SimpleNamespace(
        flowsheet=run.item.binding.flowsheet,
        spec=run.item.binding.spec,
        region=run.region,
        compiled=compile_problem(run.item.binding.spec),
    )
    problem, free, rows_, x = ptc_fixtures.ptc_problem_at(item, state, regimes)
    evaluation = problem.problem.residual(x)
    scaling = problem.problem.scaling
    j_hat = (
        sp.diags(1.0 / scaling.row_vector(rows_))
        @ sp.csc_matrix(problem.problem.jacobian(x))
        @ sp.diags(scaling.column_vector(free))
    )
    newton, _ = solve_linear(
        sp.csc_matrix(j_hat), -scaling.scale_residual(evaluation.values, rows_)
    )
    algebraic = [
        j
        for j, name in enumerate(free)
        if name != "U-HEAT.Q" and not name.startswith(("S2.", "S4.", "S5.", "S6.", "S7.", "S3.n"))
    ]
    others = [j for j in range(len(free)) if j not in algebraic]
    scale = float(np.max(np.abs(newton)))
    components: dict[str, Any] = {}
    for tau in (1e-3, 1.0, 1e3):
        step = ptc_fixtures.scaled_step(problem, free, x, tau)
        same = float(np.max(np.abs(step[algebraic] - newton[algebraic]))) / scale
        moved = float(np.max(np.abs(step[others] - newton[others]))) / scale
        components[f"dtau={tau:g}"] = {"algebraic_vs_newton": same, "inventory_vs_newton": moved}
        ledger.true(f"Δτ = {tau:g}: S3.T, split, U-FLASH.Q are Newton's (1e-9)", same <= RELATIVE)
        ledger.true(f"Δτ = {tau:g}: the inventory is not (not vacuous)", moved > 1e-6)
    ledger.true(
        "the algebraic components include S3.T, U-FLASH.Q and the S3.C split",
        {free[j] for j in algebraic} >= {"S3.T", "U-FLASH.Q", "S3.vap.C", "S3.liq.C"},
    )

    policy = edge3_fixtures.case_policy("HOM-01", GlobalizationPolicy(eo_core="ptc"))
    with_edge = edge3_fixtures.plan_run(edge3_fixtures.case_document("HOM-01"), policy).result
    edge_step = region_step(with_edge)
    edge_value = {
        "outcome": with_edge.outcome,
        "eo_recovery": edge_step.eo_recovery,
        "failed": edge_step.recovered_from.outcome,
        "cores": [item_["core"] for item_ in edge_step.detail.branch_provenance],
    }
    ledger.equal(
        "with edge 3",
        edge_value,
        {
            "outcome": registered["with_edge3"],
            "eo_recovery": "taken",
            "failed": registered["outcome"],
            "cores": ["ptc"] * len(registered["attempts"]) + ["homotopy"],
        },
    )
    value = {
        "outcome": result.outcome,
        "message": result.message,
        "attempts": rows,
        "rejection_reasons": reasons,
        "first_alpha_max": landing.alpha,
        "step_components_at_the_opening": components,
        "with_edge3": edge_value,
        "departures": ledger.departures,
    }
    expected = {
        "outcome": registered["outcome"],
        "attempts": registered["attempts"],
        "first_alpha_max": newton_alpha,
        "step_components_at_the_opening": "algebraic components Newton's to 1e-9 relative at "
        "Δτ in {1e-3, 1, 1e3}; the inventory's not",
        "with_edge3": registered["with_edge3"],
    }
    return ledger.ok, value, expected


def _a25(runs: Runs, ref: Mapping[str, Any], gate: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.orchestrator import phase_contract
    from openflowsheet.orchestrator.mass import RegionMass

    ledger = Ledger()
    # [A01] on a two-attempt PTC solve (OFF-B, r = 0.95): every compiled call and every enthalpy
    # the mass matrix asks for takes the context of the attempt in progress.
    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    trace = Trace()
    spied = ptc_fixtures.SpiedCompiled(item.compiled, trace)
    mass_contexts: list[tuple[int | None, Any]] = []
    original = RegionMass.entries_at

    def recording(self: Any, state: Any, provider: Any, context: Any) -> Any:
        mass_contexts.append((trace.events[-1].attempt if len(trace) else None, context))
        return original(self, state, provider, context)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(RegionMass, "entries_at", recording)
        result = ptc_fixtures.solve(
            item, ptc_fixtures.start(item, "OFF-B"), trace=trace, compiled=spied
        )
    contexts = [c.evaluation_context for c in result.contexts]
    ptc_spy = {
        "attempts": len(result.attempts),
        "distinct_contexts": len({id(c) for c in contexts}),
        "compiled_calls": len(spied.calls),
        "mass_evaluations": len(mass_contexts),
        "calls_outside_their_attempts_context": sum(
            1
            for _, attempt, context in spied.calls
            if attempt is None or context is not contexts[attempt]
        ),
        "mass_outside_their_attempts_context": sum(
            1
            for attempt, context in mass_contexts
            if attempt is None or context is not contexts[attempt]
        ),
        "cores": [c.core for c in result.contexts],
    }
    ledger.equal(
        "OFF-B under PTC, spied",
        {
            key: ptc_spy[key]
            for key in (
                "attempts",
                "distinct_contexts",
                "calls_outside_their_attempts_context",
                "mass_outside_their_attempts_context",
                "cores",
            )
        },
        {
            "attempts": 2,
            "distinct_contexts": 2,
            "calls_outside_their_attempts_context": 0,
            "mass_outside_their_attempts_context": 0,
            "cores": ["ptc", "ptc"],
        },
    )
    # …and per level for the homotopy: every corrector call takes its level's context, which is
    # the attempt's but for `constants_sha256` (A02 measures the identities).
    per_level = {
        case_id: all(
            {
                f.name: getattr(call[3], f.name)
                for f in dataclasses.fields(call[3])
                if f.name != "constants_sha256"
            }
            == {
                f.name: getattr(
                    Runs.direct(case_id).recovery.contexts[0].evaluation_context, f.name
                )
                for f in dataclasses.fields(call[3])
                if f.name != "constants_sha256"
            }
            for call in Runs.direct(case_id).calls
            if call[1] is not None
        )
        for case_id in HOM
    }
    ledger.equal(
        "homotopy correctors on their level's context", per_level, dict.fromkeys(HOM, True)
    )

    # The first trial of every PTC attempt at τ₀.
    tau_initial = float(ref["constants"]["ptc"]["tau_initial_s"])
    firsts: dict[str, Any] = {}
    for key in NAMED:
        named_result, named_trace = runs.named(key)
        first: dict[int, float] = {}
        for event in named_trace.events:
            if event.pseudo_step is not None and event.attempt not in first:
                first[event.attempt] = event.pseudo_step
        firsts[key] = [first.get(k) for k in range(len(named_result.attempts))]
        ledger.equal(
            f"{key}: first pseudo-step of each attempt",
            firsts[key],
            [tau_initial] * len(named_result.attempts),
        )

    # `decide` is the one function, and rows 4–5 take the PTC outcomes (PHS-05 under PTC, spied).
    seen: list[list[Any]] = []
    real = region_module.decide

    def spy(result_: Any, **kwargs: Any) -> Any:
        decision = real(result_, **kwargs)
        seen.append([result_.outcome, decision.kind, decision.cause or decision.message])
        return decision

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(region_module, "decide", spy)
        phs05 = ptc_fixtures.phs05().failed
    attempts = ref["policy_simulation"]["ptc_phs05"]["attempts"]
    ledger.equal(
        "decide on PHS-05 under PTC",
        [entry[:2] for entry in seen],
        [
            [a["core_outcome"], "restart" if a["decision"] == "restart" else "terminal"]
            for a in attempts
        ],
    )
    ledger.equal("row 4's cause", seen[1][2] if len(seen) > 1 else None, attempts[1]["cause"])
    ledger.equal(
        "PHS-05 under PTC", phs05.outcome, ref["policy_simulation"]["ptc_phs05"]["outcome"]
    )

    rows: dict[str, Any] = {}
    for label, outcome, budget, wall_at, asked, kind in (
        (
            "row 4: PTC_STALLED, wall in window",
            "PTC_STALLED",
            None,
            (2,),
            ["at_candidate"],
            "restart",
        ),
        ("row 5: PTC_STALLED, no wall", "PTC_STALLED", None, (), ["kernel_disagrees"], "terminal"),
        ("row 5: ptc_steps", "BUDGET_EXHAUSTED", "ptc_steps", (), ["kernel_disagrees"], "terminal"),
        ("row 6: property budget", "BUDGET_EXHAUSTED", "property_calls", (), [], "terminal"),
    ):
        ops = contract_fixtures.StubOps()
        decision = phase_contract.decide(
            contract_fixtures.newton(outcome, iterations=3, budget=budget),
            attempt_index=0,
            frozen=contract_fixtures.LIQ,
            wall=contract_fixtures.walled(wall_at),
            ops=ops,
            policy=contract_fixtures.POLICY,
            used=[contract_fixtures.LIQ],
        )
        rows[label] = {"asked": list(ops.asked), "decision": decision.kind}
        ledger.true(
            f"{label}: asked", ops.asked[: len(asked)] == asked and len(ops.asked) <= len(asked) + 1
        )
        ledger.equal(f"{label}: decision", decision.kind, kind)
    families = gate.get("families", {})
    ledger.true(
        "K03, T02 and T03 registered trajectories: their test families ran green in the gate",
        gate["passed"] and all(families.get(name, 0) > 0 for name in ("k03", "t02", "t03")),
    )
    value = {
        "ptc_attempt_contexts": ptc_spy,
        "homotopy_level_contexts": per_level,
        "first_pseudo_steps": firsts,
        "decide_on_phs05_ptc": seen,
        "decide_rows": rows,
        "gate_families": {name: families.get(name, 0) for name in ("k03", "t02", "t03")},
        "departures": ledger.departures,
    }
    expected = {
        "ptc_attempt_contexts": "every call and mass evaluation on its attempt's own context",
        "first_pseudo_steps": f"τ₀ = {tau_initial} s on every attempt",
        "decide_on_phs05_ptc": [[a["core_outcome"], a["decision"], a["cause"]] for a in attempts],
        "decide_rows": "rows 4 and 5 take PTC_STALLED and BUDGET_EXHAUSTED(ptc_steps); the "
        "property budget asks nothing",
        "gate_families": "every family collected and passed in the gate (A29)",
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------ A26–A29


#: A26's cases: the spec's (HOM-01, HOM-04, PTC-S1, PTC-S5, OFF-B under PTC) and W11's additions
#: (HOM-03, a stall; HOM-U, the unsupported edge; PHS-05 under PTC).
IDENTITY_CASES = [
    "HOM-01",
    "HOM-03",
    "HOM-04",
    "HOM-U",
    "OFF-B/ptc",
    "PHS-05/ptc",
    "PTC-S1",
    "PTC-S5",
]


def _a26(runs: Runs, identities: Path | None) -> dict[str, Any]:
    description = (
        "Records and schemas. The committed T04 fixtures (`t04_*.json`) validate, round-trip and "
        "are what `scripts/t04_schema_fixtures.py` emits today (the reproducibility rule); every "
        "field ADR 0010 D7 adds is present in a fixture a real run emitted; no event of any "
        "solve in this manifest serializes a non-finite number. The R0 fields of §10 for "
        "HOM-01, HOM-04, PTC-S1, PTC-S5 and OFF-B under PTC — with HOM-03, HOM-U and PHS-05 "
        "under PTC — are in `scripts/t04_identity.py`: floats-free (the only float-shaped "
        "strings are the policy's registered constants and T03's registered δ_root, written "
        "exactly), identical on two runs in one process, and carried by "
        "`scripts/k05_structural_identity.py` under `t04`. From the two CI artifacts: the "
        "x86-64 and aarch64 `identity.json` are equal key for key — the `identity` job's "
        "comparison — with `t04` equal. Without `--identities` that half is not measured and "
        "the check is `unsupported`."
    )
    try:
        local, value = _a26_local(runs)
    except Exception as error:  # noqa: BLE001
        return check(
            "T04.A26", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    expected: dict[str, Any] = {
        "fixtures": "every one: validates, no difference from what its generator emits",
        "new_fields_in_fixtures": [],
        "events_with_a_non_finite_number": 0,
        "identity": {
            "cases": sorted(IDENTITY_CASES),
            "floats": [],
            "float_shaped_strings_outside_registered_constants": [],
            "same_twice": True,
            "k05_carries_t04": True,
        },
        "ci": {"platforms": 2, "identity_differences": [], "t04_equal": True},
    }
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("T04.A26", description, "unsupported" if local else "fail", value, expected)
    value["ci"] = _ci_comparison(identities)
    agrees = all(value["ci"][key] == expected["ci"][key] for key in expected["ci"])
    return check("T04.A26", description, verdict(local and agrees), value, expected)


def _a26_local(runs: Runs) -> tuple[bool, dict[str, Any]]:
    from k05_structural_identity import identity as k05_identity
    from t04_identity import identity
    from t04_schema_fixtures import FIXTURE_NAMES, documents

    from openflowsheet.run.compare import differences
    from openflowsheet.run.identity import floats_in

    ledger = Ledger()
    emitted = documents()
    fixtures: dict[str, Any] = {}
    for name in FIXTURE_NAMES:
        committed = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        schema = name.split("/", 1)[0].replace("_", "-") + ".schema.json"
        payload = committed if isinstance(committed, list) else [committed]
        fixtures[name] = {
            "schema_errors": sum(_errors(_validator(schema), entry) for entry in payload),
            "round_trips": json.loads(json.dumps(committed)) == committed,
            "differences_from_emitted": differences(
                emitted[name], committed, policy_id="K04-numerical-policy-v1"
            )[:5],
        }
        ledger.equal(
            name,
            fixtures[name],
            {"schema_errors": 0, "round_trips": True, "differences_from_emitted": []},
        )
    ledger.equal("fixture set", sorted(emitted), sorted(FIXTURE_NAMES))

    events = [
        event
        for trace in ("t04_hom05_recovery_trace", "t04_ptc_nominal_region_trace")
        for event in json.loads(
            (FIXTURES / "solve_event" / "valid" / f"{trace}.json").read_text(encoding="utf-8")
        )
    ]
    present = set().union(*(event.keys() for event in events))
    new_fields = [
        "lambda_value",
        "delta_lambda",
        "corrector_outcome",
        "corrector_iterations",
        "level_constants_sha256",
        "homotopy_level",
        "eo_recovery",
        "pseudo_step",
        "pseudo_step_next",
        "ser_ratio",
    ]
    missing = [name for name in new_fields if name not in present]
    contexts = {
        name: json.loads(
            (FIXTURES / "attempt_context" / "valid" / f"{name}.json").read_text(encoding="utf-8")
        )
        for name in ("t04_hom05_homotopy", "t04_ptc_restart")
    }
    stall = json.loads(
        (FIXTURES / "checkpoint" / "valid" / "t04_hom04_stall.json").read_text(encoding="utf-8")
    )
    certificate = json.loads(
        (FIXTURES / "solution_certificate" / "valid" / "t04_hom01_bound_verified.json").read_text(
            encoding="utf-8"
        )
    )
    exercised = {
        "homotopy_step kind": "homotopy_step" in {event["kind"] for event in events},
        "bound_blocked reason": "bound_blocked"
        in {event.get("rejection_reason") for event in events},
        "polish trial": any(event["message"] == "polish" for event in events),
        "context core homotopy with continuation": contexts["t04_hom05_homotopy"]["core"]
        == "homotopy"
        and contexts["t04_hom05_homotopy"]["continuation"] is not None,
        "context core ptc": contexts["t04_ptc_restart"]["core"] == "ptc",
        "checkpoint continuation_lambda": bool(stall.get("continuation_lambda")),
        "provenance continuation": any(
            item.get("continuation") for item in certificate["branch_provenance"]
        ),
        "provenance eo_recovery_start": any(
            item.get("opening_source") == "eo_recovery_start"
            for item in certificate["branch_provenance"]
        ),
    }
    ledger.equal("new event fields absent from every fixture", missing, [])
    ledger.equal("new fields exercised", exercised, dict.fromkeys(exercised, True))

    non_finite = 0
    for _, trace in runs.traces():
        for event in trace.events:
            try:
                json.dumps(event.as_document(), allow_nan=False)
            except ValueError:
                non_finite += 1
    ledger.equal("events with a non-finite number", non_finite, 0)

    first, second = identity(), identity()
    float_shaped = sorted(
        {
            path
            for path, text in _strings(first)
            if FLOAT.search(HEX64.sub("", text))
            and not path.startswith(".globalization.")
            and not path.endswith(".root_fingerprint.delta_scaled_inf")
        }
    )
    k05 = k05_identity().get("t04")
    identity_value = {
        "cases": sorted(key for key in first if key != "globalization"),
        "floats": floats_in(first)[:10],
        "float_shaped_strings_outside_registered_constants": float_shaped[:10],
        "same_twice": first == second,
        "k05_carries_t04": k05 == json.loads(json.dumps(first)),
    }
    ledger.equal(
        "identity",
        identity_value,
        {
            "cases": sorted(IDENTITY_CASES),
            "floats": [],
            "float_shaped_strings_outside_registered_constants": [],
            "same_twice": True,
            "k05_carries_t04": True,
        },
    )
    value = {
        "fixtures": fixtures,
        "new_fields_in_fixtures": missing,
        "new_fields_exercised": exercised,
        "events_with_a_non_finite_number": non_finite,
        "identity": identity_value,
        "departures": ledger.departures,
    }
    return ledger.ok, value


def _strings(node: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for key, item in node.items():
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item, f"{path}[]")
    elif isinstance(node, str):
        yield path, node


def _ci_comparison(directory: Path) -> dict[str, Any]:
    """The CI `identity` job's comparison, applied to its downloaded artifacts."""
    found = sorted(directory.rglob("identity.json"))
    documents = {path.parent.name: json.loads(path.read_text(encoding="utf-8")) for path in found}
    names = sorted(documents)
    differing: list[str] = []
    if len(names) < 2:
        differing.append(f"two platforms needed; found {len(names)}")
    first = documents[names[0]] if names else {}
    for name in names[1:]:
        other = documents[name]
        differing += [
            f"{key}: {names[0]} != {name}"
            for key in sorted(set(first) | set(other))
            if first.get(key) != other.get(key)
        ]
    t04 = [document.get("t04") for document in documents.values()]
    return {
        "platforms": len(names),
        "identity_differences": differing,
        "t04_equal": len(t04) >= 2 and bool(t04[0]) and all(item == t04[0] for item in t04),
        # The implementation review's Q2(4): the artefacts compared, by hash.
        "artifact_sha256": {str(path.relative_to(directory)): file_sha256(path) for path in found},
    }


def _a27(runs: Runs) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.failure import ACTIONS, OUTCOME_ACTIONS, TAXONOMY, region_bundle

    ledger = Ledger()
    mapping = {
        outcome: [TAXONOMY[outcome], OUTCOME_ACTIONS.get(outcome, ACTIONS[TAXONOMY[outcome]])]
        for outcome in ("HOMOTOPY_STALLED", "PTC_STALLED", "PTC_MAPPING_INVALID")
    }
    ledger.equal(
        "ADR 0010 D8",
        mapping,
        {
            "HOMOTOPY_STALLED": ["homotopy/PTC/active-set stalls", "supply_initial_guess"],
            "PTC_STALLED": ["homotopy/PTC/active-set stalls", "supply_initial_guess"],
            "PTC_MAPPING_INVALID": [
                "model domain/conservation/derivative defects",
                "report_defect",
            ],
        },
    )
    validator = _validator("failure-bundle.schema.json")
    bundles: dict[str, Any] = {}
    for case_id in STALLS:
        bundle = _stall_bundle(runs, case_id)
        bundles[case_id] = {
            "schema_errors": _errors(validator, bundle),
            "inferred_causes": [[c["cause"], c["kind"]] for c in bundle["inferred_causes"]],
            "taxonomy": bundle["taxonomy"],
            "actions": [a["action"] for a in bundle["suggested_actions"]],
            "claims_infeasibility": "infeasib" in json.dumps(bundle).lower(),
        }
        causes = bundles[case_id]["inferred_causes"]
        ledger.equal(f"{case_id}: one hypothesis", [kind for _, kind in causes], ["hypothesis"])
        ledger.true(
            f"{case_id}: from the registered vocabulary",
            all(VOCABULARY.match(c) for c, _ in causes),
        )
        ledger.equal(
            f"{case_id}: bundle",
            {
                key: bundles[case_id][key]
                for key in ("schema_errors", "taxonomy", "actions", "claims_infeasibility")
            },
            {
                "schema_errors": 0,
                "taxonomy": "homotopy/PTC/active-set stalls",
                "actions": ["supply_initial_guess"],
                "claims_infeasibility": False,
            },
        )
    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    refused_trace = Trace()
    refused = ptc_fixtures.solve(
        item,
        ptc_fixtures.start(item, "OFF-A"),
        trace=refused_trace,
        mapping=ptc_fixtures.mixer_double(),
    )
    phs05 = runs.phs05()
    for label, result, trace, action in (
        ("PHS-05 under PTC", phs05.failed, phs05.trace, "supply_initial_guess"),
        ("ADV-04", refused, refused_trace, "report_defect"),
    ):
        bundle = region_bundle(result, trace, step_index=None).as_document()
        bundles[label] = {
            "outcome": result.outcome,
            "schema_errors": _errors(validator, bundle),
            "inferred_causes": bundle["inferred_causes"],
            "actions": [a["action"] for a in bundle["suggested_actions"]],
            "claims_infeasibility": "infeasib" in json.dumps(bundle).lower(),
        }
        ledger.equal(
            label,
            {
                key: bundles[label][key]
                for key in ("schema_errors", "inferred_causes", "actions", "claims_infeasibility")
            },
            {
                "schema_errors": 0,
                "inferred_causes": [],
                "actions": [action],
                "claims_infeasibility": False,
            },
        )
    value = {"taxonomy": mapping, "bundles": bundles, "departures": ledger.departures}
    expected = {
        "taxonomy": "ADR 0010 D8",
        "bundles": "stalls: one registered hypothesis; PTC outcomes: none; every bundle valid, "
        "no claim of infeasibility",
    }
    return ledger.ok, value, expected


def _a28(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    hom04 = ref["policy_simulation"]["homotopy_cases"]["HOM-04"]["homotopy"]["steps"]
    seen = _hom04_four_trials()
    recovery = seen.recovery
    lambda_budget = {
        "outcome": recovery.outcome,
        "budget": recovery.budget,
        "lambda_values": [str(t.lambda_value) for t in seen.record.trials],
        "lambda_reached": str(seen.record.lambda_reached),
        "checkpoint": [recovery.checkpoint.continuation_lambda, recovery.checkpoint.label],
        "provenance": [
            len(recovery.branch_provenance),
            recovery.branch_provenance[0]["continuation"]["lambda_reached"],
            recovery.branch_provenance[0]["core_outcome"],
        ],
        "S3_T_K": recovery.state["S3.T"],
    }
    last_accepted = [str(s["lambda"]) for s in hom04[:5] if s["accepted"]][-1]
    ledger.equal(
        "HOM-04 at four λ-trials",
        {
            key: lambda_budget[key]
            for key in (
                "outcome",
                "budget",
                "lambda_values",
                "lambda_reached",
                "checkpoint",
                "provenance",
            )
        },
        {
            "outcome": "BUDGET_EXHAUSTED",
            "budget": "homotopy_steps",
            "lambda_values": [str(s["lambda"]) for s in hom04[:5]],
            "lambda_reached": last_accepted,
            "checkpoint": [last_accepted, "partial"],
            "provenance": [1, last_accepted, "BUDGET_EXHAUSTED"],
        },
    )
    ledger.close("HOM-04 at four λ-trials: S3.T", recovery.state["S3.T"], hom04[4]["S3_T_K"])

    item = ptc_fixtures.case(ptc_fixtures.HIGH)
    capped = ptc_fixtures.solve(
        item, ptc_fixtures.start(item, "OFF-A"), ptc=PtcPolicy(max_steps_per_attempt=5)
    )
    step_budget = {
        "outcome": capped.outcome,
        "budget": capped.budget,
        "pseudo_steps": [a.iterations for a in capped.attempts],
        "recorded_steps": [len(a.ptc.steps) for a in capped.attempts],
        "checkpoint": capped.checkpoint.label if capped.checkpoint else None,
        "core": capped.branch_provenance[0]["core"],
    }
    ledger.equal(
        "OFF-A at five pseudo-steps",
        step_budget,
        {
            "outcome": "BUDGET_EXHAUSTED",
            "budget": "ptc_steps",
            "pseudo_steps": [5],
            "recorded_steps": [5],
            "checkpoint": "partial",
            "core": "ptc",
        },
    )

    # A property refusal inside a corrector (HOM-01, the cap between λ = 1/4 and 3/4) and inside a
    # pseudo-step (the high-recycle plan under PTC, the cap between steps 11 and 12): T03 review
    # S1's shape — the attempts, the checkpoint and the provenance kept.
    free = runs.plan("HOM-01").result
    steps = free.trace.of_kind("homotopy_step")
    cap = (steps[1].counters.property_calls + steps[2].counters.property_calls) // 2
    result = edge3_fixtures.plan_run(
        edge3_fixtures.case_document("HOM-01"),
        replace(edge3_fixtures.case_policy("HOM-01"), max_property_calls=cap),
    ).result
    step = region_step(result)
    corrector_refusal = {
        "outcome": result.outcome,
        "property_calls_equal_the_cap": result.counters.property_calls == cap,
        "budget": step.detail.budget,
        "eo_recovery": step.eo_recovery,
        "contract_items": len(step.recovered_from.branch_provenance),
        "cores": [i["core"] for i in step.detail.branch_provenance],
        "lambda_reached": step.detail.branch_provenance[-1]["continuation"]["lambda_reached"],
        "checkpoint": [step.checkpoint.continuation_lambda, step.checkpoint.label],
    }
    hom01 = ref["policy_simulation"]["homotopy_cases"]["HOM-01"]
    quarter = str(hom01["homotopy"]["steps"][1]["lambda"])
    ledger.equal(
        "a property refusal inside a corrector",
        corrector_refusal,
        {
            "outcome": "BUDGET_EXHAUSTED",
            "property_calls_equal_the_cap": True,
            "budget": "property_calls",
            "eo_recovery": "taken",
            "contract_items": len(hom01["contract"]["attempts"]),
            "cores": ["newton"] * len(hom01["contract"]["attempts"]) + ["homotopy"],
            "lambda_reached": quarter,
            "checkpoint": [quarter, "partial"],
        },
    )
    ledger.close(
        "… its reported S3.T", result.state["S3.T"], hom01["homotopy"]["steps"][1]["S3_T_K"]
    )

    document = yaml.safe_load((CASES / f"{ptc_fixtures.HIGH}.yaml").read_text(encoding="utf-8"))
    unbounded = edge3_fixtures.plan_run(document, ptc_fixtures.eo_policy()).result
    accepted = [
        event.counters.property_calls
        for event in unbounded.trace.of_kind("step_accepted")
        if event.pseudo_step is not None
    ]
    cap = (accepted[10] + accepted[11]) // 2
    bounded = edge3_fixtures.plan_run(
        document, ptc_fixtures.eo_policy(max_property_calls=cap)
    ).result
    detail = region_step(bounded).detail
    pseudo_step_refusal = {
        "outcome": bounded.outcome,
        "property_calls_equal_the_cap": bounded.counters.property_calls == cap,
        "budget": detail.budget,
        "attempt_pseudo_steps": [a.iterations for a in detail.attempts],
        "cores": [i["core"] for i in detail.branch_provenance],
        "checkpoint": region_step(bounded).checkpoint.label
        if region_step(bounded).checkpoint
        else None,
    }
    ledger.equal(
        "a property refusal inside a pseudo-step",
        pseudo_step_refusal,
        {
            "outcome": "BUDGET_EXHAUSTED",
            "property_calls_equal_the_cap": True,
            "budget": "property_calls",
            "attempt_pseudo_steps": [11],
            "cores": ["ptc"],
            "checkpoint": "partial",
        },
    )
    value = {
        "lambda_trial_budget": lambda_budget,
        "pseudo_step_budget": step_budget,
        "property_refusal_in_a_corrector": corrector_refusal,
        "property_refusal_in_a_pseudo_step": pseudo_step_refusal,
        "departures": ledger.departures,
    }
    expected = {
        "lambda_trial_budget": f"BUDGET_EXHAUSTED(homotopy_steps) after 4 λ-trials, checkpoint "
        f"partial at {last_accepted}, S3.T of ref's fourth trial",
        "pseudo_step_budget": "BUDGET_EXHAUSTED(ptc_steps) after 5 pseudo-steps, checkpoint "
        "partial",
        "property_refusals": "BUDGET_EXHAUSTED(property_calls) at the cap, attempts, checkpoint "
        "and provenance kept",
    }
    return ledger.ok, value, expected


def _a29(
    checks: Sequence[Mapping[str, Any]],
    gate: Mapping[str, Any],
    requirements: Sequence[str],
    refused: Sequence[str],
    limitations: Sequence[str],
    ci_run: str | None,
) -> dict[str, Any]:
    covered = [entry["id"] for entry in checks] + ["T04.A29"]
    ordered = sorted(covered, key=lambda i: int(i.split(".A")[1]))
    registered = [f"T04.{identifier}" for identifier in ASSERTIONS]
    families = gate.get("families", {})
    value = {
        "gate": {key: gate[key] for key in ("passed", "pytest_counts", "collected")},
        "families": families,
        "entries": len(covered),
        "ids": ordered == registered and len(set(covered)) == len(covered),
        "requirements": list(requirements),
        "refused_by_the_frozen_schema": list(refused),
        "v14_incomplete_in_limitations": any(
            "V14" in text and "incomplete" in text and "experimental" in text
            for text in limitations
        ),
        "review": {"numerical": "pending", "process_model": "pending"},
        "ci_run": ci_run,
    }
    expected = {
        "gate": "passed, pytest passed only, collected equal to the gate's passed count",
        "families": "K03, T02, T03, K04, K05 and T04 each at least 1 test",
        "entries": len(registered),
        "ids": True,
        "requirements": list(A29_REQUIREMENTS),
        "refused_by_the_frozen_schema": ["V14"],
        "v14_incomplete_in_limitations": True,
        "review": {"numerical": "pending", "process_model": "pending"},
        "ci_run": "a workflow run URL",
    }
    ok = (
        gate["passed"]
        and not gate["pytest_failed_or_errors"]
        and set(gate["pytest_counts"]) == {"passed"}
        and gate["collected"] == gate["pytest_passed"] > 0
        and all(families.get(name, 0) > 0 for name in ("k03", "t02", "t03", "k04", "k05", "t04"))
        and value["ids"]
        and value["entries"] == len(registered)
        and list(requirements) == expected["requirements"]
        and list(refused) == ["V14"]
        and value["v14_incomplete_in_limitations"]
    )
    description = (
        "Regression and manifest. The gate's pytest run passed with no failure, error or skip, "
        "and the number it passed equals the number `pytest --collect-only` finds here, among "
        "them K03's, T02's, T03's, K04's, K05's and T04's own test files (counted per family) — "
        "every registered assertion of those packages green, with §11's re-registrations "
        "already in the tests. This manifest has one `checks[]` entry per `T04.A00`…`T04.A33`; "
        "`requirements` are A29's as amended (F16) — D01, D07, A03, D09, D11, D20: ADR 0010's "
        "affected requirements less V14, which the frozen evidence-manifest schema refuses "
        "(measured) and `limitations` carries; `limitations` "
        "restate spec §14 including V14's qualified-PTC clause incomplete, PTC experimental; "
        "`review` is `pending` in both fields. The two-architecture half is the named CI run: "
        "without `--ci-run` the check is `unsupported`."
    )
    if ci_run:
        return check("T04.A29", description, verdict(ok), value, expected)
    return check("T04.A29", description, "unsupported" if ok else "fail", value, expected)


# ------------------------------------------------------------------------------ A30–A33


def _a30(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.certificate import alias_document

    ledger = Ledger()
    bound = ref["bound_declaration_certificate"]
    states = [
        name for name, entry in bound["certificate_states"].items() if entry["verdict_promised"]
    ]
    aliases = ["U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle"]
    evaluated = ["S1.T", "S1.P", "S1.n.A", "S1.n.B", "S1.n.C", "S4.T", "S5.T", "U-FLASH.Q"]
    per_state: dict[str, Any] = {}
    for name in states:
        issued = certificate_fixtures.certificate(name)
        item = certificate_fixtures.solved(name)
        checks = {c.id: c for c in issued.checks}
        residuals = sorted(c.subject for c in issued.checks if c.category == "residual")
        specifications = {c.id: c for c in issued.checks if c.category == "specification"}
        freed = specifications.get("specification.S3.T")
        eliminated = issued.transformations["eliminated_rows"]
        regularity = issued.regularity
        metadata = compile_problem(item.binding.spec).metadata
        measured_state = {
            "verdict": [issued.verification_status, issued.false_success_detected],
            "fail_or_unsupported": [
                c.id for c in issued.checks if c.result in ("fail", "unsupported")
            ],
            "near_threshold": [c.id for c in issued.checks if c.near_threshold],
            "residual_rows": len(residuals),
            "residual_rows_are_the_declarations": residuals
            == sorted(item.binding.spec.equation_ids),
            "promoted_row_checked": "SPEC:SPEC-flash-duty" in residuals,
            "removed_row_checked": "U-HEAT:HEAT-T" in residuals,
            "aliases": sorted(row["row_id"] for row in eliminated),
            "alias_mismatches": [row["constant_mismatch"] for row in eliminated],
            "aliases_equal_the_plans": [
                {**row, "equals": sorted(row["equals"])} for row in eliminated
            ]
            == [alias_document(row) for row in item.solve_plan.eliminated_rows],
            "specification_ids": sorted(
                key.removeprefix("specification.") for key in specifications
            ),
            "specifications_evaluated_pass": sorted(
                key.removeprefix("specification.")
                for key, c in specifications.items()
                if c.result == "pass"
            ),
            "freed": [freed.result, freed.reason, freed.value] if freed else None,
            "regularity": [regularity.status, regularity.dimension],
            "witness": [
                checks[f"derivative_witness.{side}"].value for side in ("on_pattern", "off_pattern")
            ],
            "derivative_path": issued.derivative_provenance["path"],
            "tear": issued.transformations["tear"],
            "declaration": issued.transformations["declaration"],
            "identity_is_the_revisions": (issued.model_version, issued.constants_sha256)
            == (metadata.model_version, metadata.constants_sha256),
            "identity_is_the_failed_solves": None
            if item.failed is None
            else (issued.model_version, issued.constants_sha256)
            == (
                item.failed.contexts[0].evaluation_context.model_version,
                item.failed.contexts[0].evaluation_context.constants_sha256,
            ),
            "provenance_and_fingerprint_are_the_solves": issued.root_fingerprint
            == item.result.root_fingerprint
            and issued.branch_provenance == tuple(dict(i) for i in item.result.branch_provenance),
        }
        ledger.equal(
            name,
            {key: measured_state[key] for key in measured_state if key != "witness"},
            {
                "verdict": ["VERIFIED", False],
                "fail_or_unsupported": [],
                "near_threshold": [],
                "residual_rows": 49,
                "residual_rows_are_the_declarations": True,
                "promoted_row_checked": True,
                "removed_row_checked": False,
                "aliases": aliases,
                "alias_mismatches": [0.0, 0.0],
                "aliases_equal_the_plans": True,
                "specification_ids": sorted([*evaluated, "S3.T"]),
                "specifications_evaluated_pass": sorted(evaluated),
                "freed": ["not_applicable", "freed(GUESS-heater-outlet-T)", None],
                "regularity": ["NO_RANK_LOSS_DETECTED", 47],
                "derivative_path": "assembled_schur",
                "tear": {"variable_ids": [], "row_ids": []},
                "declaration": {
                    "removed_specification_rows": ["U-HEAT:HEAT-T"],
                    "freed": {"U-HEAT:HEAT-T": "S3.T"},
                    "promoted": {CONTINUED: "U-FLASH.Q"},
                },
                "identity_is_the_revisions": True,
                "identity_is_the_failed_solves": None if item.failed is None else True,
                "provenance_and_fingerprint_are_the_solves": True,
            },
        )
        ledger.true(
            f"{name}: witness at most 1e-7 on and off the pattern",
            all(w is not None and w <= 1e-7 for w in measured_state["witness"]),
        )
        if name in bound["target_regularity"]:
            registered = bound["target_regularity"][name]
            norms = {}
            for attribute, key in (
                ("one_norm", "one_norm"),
                ("inverse_one_norm_estimate", "inverse_one_norm"),
                ("rcond_1", "rcond_1"),
            ):
                norms[attribute] = getattr(regularity, attribute)
                ledger.close(
                    f"{name}: {attribute}",
                    norms[attribute],
                    registered[key],
                    absolute=1e-6 * float(registered[key]),
                )
            nominal = float(registered["nominal_declaration_rcond_1_same_state"])
            ledger.true(
                f"{name}: the nominal declaration's rcond_1 differs by at least 20%",
                abs(regularity.rcond_1 - nominal) >= 0.2 * regularity.rcond_1,
            )
            measured_state["target_norms"] = norms
        per_state[name] = measured_state
    value = {"states": per_state, "departures": ledger.departures}
    expected = {
        "states": states,
        "each": "VERIFIED, no fail / unsupported / near_threshold; the bound declaration's 49 "
        "rows; the two pressure aliases with m_e = 0, equal to the plan's; the eight evaluated "
        "specifications pass and S3.T not_applicable freed(GUESS-heater-outlet-T); regularity "
        "NO_RANK_LOSS_DETECTED at 47; witness at most 1e-7; empty tear and §4.8's declaration; "
        "the revision's identity; the solve's provenance and fingerprint",
        "target_norms": {
            name: bound["target_regularity"][name] for name in bound["target_regularity"]
        },
        "tolerance": "norms 1e-6 relative",
    }
    return ledger.ok, value, expected


def _a31() -> tuple[bool, Any, Any]:
    from openflowsheet.verify.certificate import verify, verify_bound

    ledger = Ledger()
    refusals: dict[str, Any] = {}
    for name in ("HOM-01", "SYN-001-A02-360"):
        item = certificate_fixtures.solved(name)
        with pytest.MonkeyPatch.context() as patch:
            calls, _ = _spy_verifier_compiles(patch)
            message = _verifier_refusal(lambda i=item: verify(i.binding.flowsheet, i.result))
        refusals[f"(i) nominal entry, {name}"] = [message, len(calls)]
        ledger.equal(
            f"(i) {name}",
            refusals[f"(i) nominal entry, {name}"],
            ["declaration_mismatch(model_version)", 0],
        )
    declared, other = (
        certificate_fixtures.solved("SYN-001-A02-360"),
        certificate_fixtures.solved("SYN-001-A02-365"),
    )
    with pytest.MonkeyPatch.context() as patch:
        calls, _ = _spy_verifier_compiles(patch)
        message = _verifier_refusal(
            lambda: verify_bound(declared.binding, declared.document, other.result)
        )
    refusals["(ii) A02-360's declaration, A02-365's result"] = [message, len(calls)]
    ledger.equal(
        "(ii)",
        refusals["(ii) A02-360's declaration, A02-365's result"],
        ["declaration_mismatch(constants_sha256)", 0],
    )
    moved = dict(declared.result.state)
    moved["S3.T"] += 1e-9
    constructed = replace(declared.result, state=moved)
    refusals["(iii) a state that is not the fingerprinted one"] = _verifier_refusal(
        lambda: verify_bound(declared.binding, declared.document, constructed)
    )
    ledger.equal(
        "(iii)",
        refusals["(iii) a state that is not the fingerprinted one"],
        "state_mismatch(full_state_sha256)",
    )
    injected = verify_bound(declared.binding, declared.document, declared.result, state=moved)
    refusals["(iii) the same state by state= (K04 §9's path)"] = injected.verification_status
    ledger.true(
        "(iii) state= skips the hash comparison",
        injected.verification_status in ("VERIFIED", "FAILED", "UNVERIFIED", "RELAXED"),
    )
    anonymous = SimpleNamespace(outcome="CONVERGED", state=dict(declared.result.state))
    refusals["(iv) neither fingerprint nor plan"] = [
        _verifier_refusal(lambda: verify_bound(declared.binding, declared.document, anonymous)),
        # Review S1: a caller-supplied `solve_plan` never identifies the solve.
        _verifier_refusal(
            lambda: verify_bound(
                declared.binding, declared.document, anonymous, solve_plan=declared.solve_plan
            )
        ),
        _verifier_refusal(lambda: verify(declared.binding.flowsheet, anonymous)),
    ]
    ledger.equal(
        "(iv)", refusals["(iv) neither fingerprint nor plan"], ["declaration_unidentified"] * 3
    )
    # (vi), review S2: the revision document must be the one the binding was bound from.
    with pytest.MonkeyPatch.context() as patch:
        calls, _ = _spy_verifier_compiles(patch)
        message = _verifier_refusal(
            lambda: verify_bound(
                declared.binding,
                other.document,
                declared.result,
                solve_plan=declared.solve_plan,
            )
        )
    refusals["(vi) A02-360's binding, A02-365's document, A02-360's result"] = [
        message,
        len(calls),
    ]
    ledger.equal(
        "(vi)",
        refusals["(vi) A02-360's binding, A02-365's document, A02-360's result"],
        ["declaration_mismatch(revision)", 0],
    )
    control = verify_bound(
        declared.binding, declared.document, declared.result, solve_plan=declared.solve_plan
    )
    refusals["(vi) the same binding with its own document"] = control.verification_status
    ledger.equal("(vi) control", control.verification_status, "VERIFIED")
    value = {"refusals": refusals, "departures": ledger.departures}
    expected = {
        "refusals": {
            "(i)": "declaration_mismatch(model_version), no residual call",
            "(ii)": "declaration_mismatch(constants_sha256), no residual call",
            "(iii)": "state_mismatch(full_state_sha256); with state= a verdict",
            "(iv)": "declaration_unidentified from both entry points, with or without a "
            "caller-supplied solve_plan",
            "(vi)": "declaration_mismatch(revision), no residual call; the matching pair VERIFIED",
            "(v)": "K04's registered injections: tests/test_k04_injections.py in the gate (A29); "
            "the nominal state= path is A22's unpolished stop",
        }
    }
    return ledger.ok, value, expected


def _a32() -> tuple[bool, Any, Any]:
    from openflowsheet.verify.certificate import verify_bound

    ledger = Ledger()
    five = sorted(certificate_fixtures.FIVE)
    item = certificate_fixtures.solved("SYN-001-A02-365")
    q_spec = next(
        e["value"] for e in item.document["specifications"] if e["id"] == "SPEC-flash-duty"
    )
    per_delta: dict[str, Any] = {}
    for delta, status, failing in (
        (2e-3, "FAILED", five),
        (-2e-3, "FAILED", five),
        (5e-4, "VERIFIED", []),
    ):
        state = dict(item.result.state)
        state["U-FLASH.Q"] += delta
        issued = verify_bound(item.binding, item.document, item.result, state=state)
        checks = {c.id: c for c in issued.checks}
        measured_delta = {
            "verdict": [issued.verification_status, issued.false_success_detected],
            "failing": sorted(c.id for c in issued.checks if c.result == "fail"),
            "near_threshold": sorted(c.id for c in issued.checks if c.near_threshold),
            "values_minus_delta_W": {name: checks[name].value - delta for name in five},
        }
        per_delta[f"{delta:+g} W"] = measured_delta
        ledger.equal(
            f"δ = {delta:+g}",
            {key: measured_delta[key] for key in ("verdict", "failing", "near_threshold")},
            {"verdict": [status, status == "FAILED"], "failing": failing, "near_threshold": five},
        )
        ledger.true(
            f"δ = {delta:+g}: each value δ within 1e-7 W",
            all(abs(v) <= 1e-7 for v in measured_delta["values_minus_delta_W"].values()),
        )
    value = {"Q_spec_W": q_spec, "deltas": per_delta, "departures": ledger.departures}
    expected = {
        "deltas": {
            "+0.002 W": "FAILED, false success, exactly the five checks that read U-FLASH.Q, "
            "each +δ",
            "-0.002 W": "the same set, each −δ",
            "+0.0005 W": "VERIFIED with near_threshold on those five",
        },
        "five": five,
        "tolerance": "values within 1e-7 W of ±δ",
    }
    return ledger.ok, value, expected


def _a33(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.verify.certificate import verify_bound

    ledger = Ledger()
    registered = ref["bound_declaration_certificate"]["finding_F9"]
    promised = ref["bound_declaration_certificate"]["certificate_states"]["SYN-001-A02-355"][
        "verdict_promised"
    ]
    item = certificate_fixtures.solved_355()
    (attempt,) = item.result.attempts
    issued = verify_bound(item.binding, item.document, item.result, solve_plan=item.solve_plan)
    checks = {c.id: c for c in issued.checks}
    residuals = [c for c in issued.checks if c.category == "residual"]
    worst = max(residuals, key=lambda c: abs(c.value) / c.tolerance)
    ledger.equal(
        "the state",
        (attempt.iterations, dict(attempt.signature)),
        (3, {"U-HEAT": "TWO_PHASE", "U-FLASH": "TWO_PHASE"}),
    )
    ledger.equal("worst row", worst.subject, registered["worst_row"])
    over = abs(worst.value) / worst.tolerance
    ledger.close(
        "worst row / τ",
        over,
        registered["worst_row_over_tolerance"],
        absolute=1e-5 * float(registered["worst_row_over_tolerance"]),
    )
    values: dict[str, Any] = {}
    for name, key, sign in (
        ("independent_split.S3.total", "independent_split_S3_total_mol_per_s", 1.0),
        ("energy_balance.heater", "energy_heater_W", 1.0),
        ("energy_balance.flash", "energy_heater_W", -1.0),
    ):
        target = sign * float(registered[key])
        values[name] = {"value": checks[name].value, "near_threshold": checks[name].near_threshold}
        ledger.close(name, checks[name].value, target, absolute=1e-5 * abs(target))
        ledger.equal(f"{name}: near_threshold", checks[name].near_threshold, True)
    ledger.equal("verdict promised by ref", promised, False)
    value = {
        "worst_row": worst.subject,
        "worst_row_over_tolerance": over,
        "checks": values,
        # Recorded, not asserted (ADR 0007 D2.4; F9 identifies a FAILED here as a false alarm).
        "verdict_recorded_not_asserted": [
            issued.verification_status,
            issued.false_success_detected,
        ],
        "departures": ledger.departures,
    }
    expected = {
        "worst_row": registered["worst_row"],
        "worst_row_over_tolerance": registered["worst_row_over_tolerance"],
        "checks": {
            "independent_split.S3.total": registered["independent_split_S3_total_mol_per_s"],
            "energy_balance.heater": registered["energy_heater_W"],
            "energy_balance.flash": f"-{registered['energy_heater_W']}",
            "each": "near_threshold",
        },
        "tolerance": "1e-5 relative",
        "verdict_recorded_not_asserted": "no expectation (verdict_promised: false)",
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------ the manifest


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
        "pytest_passed": counts.get("passed", 0),
        "pytest_counts": counts,
        "pytest_failed_or_errors": bool(
            counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
        ),
        "collected": len(collected),
        "families": {
            family: sum(1 for line in collected if line.startswith(f"tests/test_{family}_"))
            for family in ("k03", "t02", "t03", "k04", "k05", "t04")
        },
    }


def _pytest_counts(text: str) -> dict[str, int]:
    """The last pytest summary line (`3 failed, 1511 passed in 27.1s`), as counts by word."""
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


def _status(checks: Sequence[Mapping[str, Any]]) -> str:
    """`tested` when nothing failed. An `unsupported` check carries its reason in its own
    description, which is T01's, K05's, T02's and T03's rule; a `fail` anywhere leaves the package
    `implemented`, never `tested`."""
    return "implemented" if any(entry["result"] == "fail" for entry in checks) else "tested"


def _case_hash() -> str:
    """One digest over every registered revision this package ran, in name order."""
    names = {
        case["revision"]
        for case_id, case in registry_fixtures.CASES.items()
        if case_id in registry_fixtures.GLOBALIZATION and case.get("revision")
    }
    names |= {
        f"benchmarks/syn001/cases/{name}.yaml"
        for name in (
            "SYN-001-A02-355-liquid-guess",
            "SYN-001-A02-355",
            "SYN-001-A02-360",
            "SYN-001-A02-365",
            "SYN-001-high-recycle",
        )
    }
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()


def _limitations(ci_run: bool, identities: bool, refused: Sequence[str]) -> list[str]:
    stated = [
        # Spec §14, restated item by item.
        "Spec §14: correctness of any solver is not established. The specification registers "
        "what a correct implementation must produce; the twin's agreement with the implementation "
        "is evidence that the twin is the implementation's system. This manifest measures the "
        "implementation against those registrations — numerical verification, not empirical "
        "validation.",
        "Spec §14 and ADR 0010 D5 (V14): the residence-time PTC family is not qualified. It "
        "improves no tested basin (A23: the 18 admitted starts converge under both cores, the "
        "criterion of §8.1 gives `experimental`), and on the A02 region it cannot help by "
        "structure (§6.7). PTC is experimental — selectable only by `eo_core = ptc` — and V14's "
        "qualified-PTC clause is recorded incomplete; V14 stays incomplete until a later package "
        "qualifies a family on a preregistered case (§8.4, PTC-R1). This is Frank's open default "
        "F1 (option a).",
        "Spec §14: that the continuation converges wherever a root exists is not established. A "
        "frozen-signature path cannot cross a phase boundary (HOM-03 and HOM-04 stall there, "
        "typed and bracketed); folds and turning points are not followed (arclength deferred); "
        "a specification whose path has no root at some λ stalls. The family scan found one "
        "natural stall in 180 runs.",
        "Spec §14: the homotopy's type covers promoted specifications only. A region without one "
        "has no continuation (`unsupported`, HOM-U); SYN-001 under `eo` is such a region.",
        "Spec §14: attraction far from the root and dynamic stability of the process are not "
        "assessed; §6.6 is local, and `claims.dynamic_stability` stays NOT_ASSESSED. PTC can "
        "favour some roots over others and does not prove dynamic stability (blueprint §7.5).",
        "Spec §14: the residence-time model is the pseudo-time model of §6.2 — a vessel under "
        "ideal proportional control with a common residence time — with no vessel data behind θ; "
        "it is not a physical model of the SYN-001 vessels.",
        "Spec §14: behaviour on energy dynamics is not exercised. With pinned temperatures the "
        "energy rows carry no mode; no registered case has a free vessel temperature with a "
        "genuine thermal mode (NET-07, T06).",
        "Spec §14: the A04-ensemble comparison of §8.3 is exploration, not a registered result.",
        "Spec §14: the basin comparison is not broad. The registered lattice admits 18 starts in "
        "six compositions (F14); the verdict rests on them and on the structural result of "
        "§6.7, not on coverage of the start space.",
        "Spec §14: performance (the recompilation per λ-level, the PTC cost of 1.9–8.8× Newton's) "
        "is measured on SYN-001 only; nothing is empirically valid (synthetic fixture); human "
        "numerical and process-modelling review are `pending` and no agent sets them.",
        # Handed on, and not closed here.
        "Spec §14 and F9 (Q8), handed to a K04 follow-up: K04's fresh-flash tolerances (the "
        "independent split τ_flow and the fresh-flash energy balances τ_E) are tighter than the "
        "lifted equilibrium rows' tolerance implies at a lifted two-phase stream. T04 promises "
        "certificate verdicts only outside ADR 0007 D2.4's band and does not amend K04's "
        "tolerances. A33 registers T02's SYN-001-A02-355 from 358 K as evidence: every row at "
        "0.0813 τ, the independent split at 1.092 τ_flow, both fresh-flash energy balances "
        "`near_threshold`; its verdict is recorded and not asserted (on the measured platform "
        "it is a false alarm). Decide before T06 certifies EO solves in bulk. K04 §4.7's "
        "flash-outlet clause (F10) is not implemented either; the same follow-up.",
        "PTC is experimental and V14's qualified-PTC clause is incomplete (spec §8, ADR 0010 D5, "
        "Frank's default F1); the release-gate ledger records the clause as a failed item, never "
        "removed from the denominator.",
        "Handed on, open (implementation review M1, must-fix): a failed Jacobian evaluation is "
        "not a typed outcome on the region path. `_region_problem.jacobian` ignores the compiled "
        "Jacobian's status and hands the PTC core a zero matrix, so a failure at the polish "
        "becomes `rejected:linear_solve_failed` and `CONVERGED` at the unpolished stop (where "
        "ruling F15(h) says `EVALUATION_ERROR`), one at a pseudo-step becomes `PTC_STALLED` (an "
        "edge-3 trigger), and one on the A02 region can crash SuperLU (review S5). The generic "
        "core's `_polish` calls `problem.jacobian(x)` unguarded too, as K03's Newton core does. "
        "No registered Jacobian evaluation fails, so no assertion here reaches it.",
        "Q6, handed to K03: the tear path's budget-refusal shape (T03 review S1) is not folded "
        "into T04. A `BudgetExhaustedError` on the tear path still returns `attempts = 0`, "
        "`x = start` and no provenance (K03's registered capped-budget shape). T04's own cores "
        "keep the attempts, the checkpoint and the provenance (A28). A K03 follow-up before "
        "T06's ensemble, which counts budget outcomes.",
        "Frank's open defaults, in force: F1 — PTC experimental and V14 incomplete for v0.1 "
        "(option a; the alternatives are qualifying on the preregistered CSTR PTC-R1, or "
        "dropping PTC from v0.1); F2 — edge 3 on by default (`eo_recovery: homotopy`), which "
        "changes PHS-05's registered outcome from ACTIVE_SET_CYCLING to CONVERGED and is "
        "reversible by one policy default.",
        # What the measurements here do and do not reach.
        "A20 is `unsupported`, not `pass`: three of spec §9.9's rows — the stop on ‖F̂‖ at most "
        "φ_floor, the proposed Δτ in the SER update, a rejected trial's residual in the ratio — "
        "and the stream-total heater holdup (ADR 0010's rejected alternative) have no ablation "
        "seam in the implementation, and none is added to the core for evidence. The twin "
        "registers them (`ref.policy_simulation.ablations`); every row the implementation can "
        "express was measured and agrees. Whether the twin's registration discharges them is "
        "the design lane's ruling (as F15 ruled for the rollback row).",
        "A01's replay clause is measured as the schema's refusal of a recorded policy document "
        "without `globalization` (ADR 0005 D1's precedent). v0.1 has no path from a recorded "
        "policy document back to a `SolvePolicy`, so no replay can run under one; `replay()` "
        "itself does not validate the recorded policy.",
        "A11 checks the 170 runs that converge by the contract alone by their outcome only "
        "(CONVERGED, no recovery). Spec A11 also names their attempts and counts, which the "
        "twin computes but `ref` does not register (review S4, owned by the design lane: register "
        "them or strike the clause).",
        "A26's R0 document leaves the compared floats (pseudo_step, pseudo_step_next, "
        "ser_ratio, a PTC trial's α below 1: R1/R2 under ADR 0007 D2) and the digests "
        "(level_constants_sha256, whose preimage holds the solved p⁰; state hashes) out; they "
        "are neither rounded nor compared across platforms by this manifest.",
    ]
    stated += [
        f"Spec A29 and ADR 0010 list {identifier} among the requirements; the frozen "
        "evidence-manifest schema takes D/A ids only (measured: it refuses "
        f"`{identifier}`), so `requirements` omits it and `docs/requirements.yaml` carries it "
        "(T02's and T03's precedent for V13/V15)."
        for identifier in refused
    ]
    stated.append(
        "`requirements` also names D20, which ADR 0010 lists (every new field classified R0 or "
        "R1/R2 under blueprint §8.3) and spec A29's list does not."
    )
    if not identities:
        stated.append(
            "The cross-platform half of A26 was not measured by this run: no `--identities` "
            "directory was given, so the check is `unsupported`, not `pass`."
        )
    if not ci_run:
        stated.append(
            "No CI run was named (`--ci-run`), so `commands` records the local gate only and "
            "A29's two-architecture half is `unsupported`."
        )
    return stated


#: One line per assertion: what is measured, in the manifest's words (the value says how).
DESCRIPTIONS = {
    "A00": "Generator self-check: `t04_reference.py --check` passes with the number of checks the "
    "committed YAML lists (and prints exactly that list); the committed YAML's SHA-256 is the one "
    "in the specification header; `--emit` twice (two processes) gives identical bytes, equal to "
    "the committed file; the generator and every sibling script it imports, transitively, import "
    "nothing from `openflowsheet` or `benchmarks` (every import statement, from the syntax "
    "tree).",
    "A01": "`SolvePolicy.globalization`: the default policy carries `T04-globalization-v1` with "
    "exactly `ref.constants`' homotopy and PTC constants (λ constants as `p/q` strings), "
    "`eo_recovery_max_count` 1 and `ptc.status` experimental; every policy this manifest's "
    "fixtures solve under validates, carries the object and departs from the default only in a "
    "value its case sets on purpose; the schema refuses a policy without the object, with "
    "another `policy_id`, `ptc.status` or `eo_recovery_max_count`, or a float λ constant (the "
    "replay refusal, see `limitations`); K03's, K04's and T04's committed fixtures are what their "
    "generators emit today and validate.",
    "A02": "Endpoint identity on HOM-01…05 (compiled instances spied): every λ = 1 corrector call "
    "on the target instance under the target's `(model_version, constants_sha256)`; every call "
    "below λ = 1 on a level instance with the target's `model_version` and another "
    "`constants_sha256`, its context otherwise the attempt's; one compile per distinct λ below 1, "
    "each declaration differing from the target's only at `SPEC:SPEC-flash-duty`, by the exact "
    "`p(λ)`; λ = 1 never re-bound; the converged cases' λ = 1 residual at the final state the "
    "freshly compiled target's bit for bit; `EvaluationContext`'s field set is the pinned one and "
    "no context carries a workspace.",
    "A03": "λ below 1 is never target-verified: every checkpoint of this manifest's solves with "
    "`continuation_lambda` other than null or `1` is partial / unverified, and the schema "
    "refuses it otherwise; `verify` and `verify_bound` handed HOM-03's and HOM-04's stall "
    "checkpoint, recovery result or plan result refuse with `continuation_level(λ reached)` "
    "before compiling anything; `BUDGET_EXHAUSTED(homotopy_steps)` (A28's case) is refused the "
    "same way; HOM-01's, HOM-02's and HOM-05's certificates are `VERIFIED` on the target "
    "identity by §4.8's verifier.",
    "A04": "HOM-01 (PHS-05) through the plan executor under the default policy: the contract's "
    "attempts as `ref.hom.HOM-01.contract` (and T03 A12's registered trajectory), edge 3 taken, "
    "every λ-trial (λ, Δλ, corrector outcome and iterations, verdict, S3.T) as registered, "
    "`CONVERGED`, the recovery's provenance item, the reported state T02's 355 K row, "
    "`same_root` with SYN-001-A02-355 from 358 K `SAME`, and the certificate `VERIFIED`.",
    "A05": "HOM-02 (355 K from 377 K) as A04 with `ref.hom.HOM-02`, including the λ = 3/4 "
    "corrector's landing on `S3.vap.C` at the registered `α_max` that does not close it.",
    "A06": "HOM-03 (352 K from 410 K): contract `ACTIVE_SET_CYCLING` as registered; edge 3 → "
    "`HOMOTOPY_STALLED` at `ref`'s λ reached with its λ-trials, verdicts and corrector outcomes "
    "(every rejection `PHASE_UPDATE_REQUIRED`); the reported S3.T the last accepted root; the "
    "bracket on the dew-branch boundary; bundle class, action and inferred cause; no "
    "certificate; checkpoint partial at λ reached.",
    "A07": "HOM-04 (PHS-04, `max_attempts = 1`): `ATTEMPTS_EXHAUSTED` → edge 3 → "
    "`HOMOTOPY_STALLED` at `ref`'s λ reached, every rejection `BOUND_BLOCKED` on `S3.vap.C`; the "
    "reported state (S3.T, S3.V) the last accepted root, not a corrector's end state; the "
    "bubble-point bracket from `ref.closed_form.a02`.",
    "A08": "HOM-05 (A02-360 from 358 K, `max_iterations_per_attempt = 1`): "
    "`BUDGET_EXHAUSTED(newton_iterations)` → edge 3 → the registered λ-trials → `CONVERGED` at "
    "T02's 360 K row; the contract's terminal item's cause the failed solve's closing message; "
    "certificate `VERIFIED`.",
    "A09": "Trigger discipline: the trigger set is `ref.constants.edge3_triggers`, "
    "`BUDGET_EXHAUSTED` only for `newton_iterations` / `ptc_steps`; HOM-U from the registry "
    "(unsupported, `no_continuation_parameter`, on `region_closed`); HOM-N (the edge off: T03 "
    "A12's cycling, unchanged); RCY-STALL's `LINEAR_SOLVE_FAILED`, T03 A16's constructed "
    "`CHECKPOINT_INCOMPATIBLE` and T03 review S1's `BUDGET_EXHAUSTED(property_calls)` (cap 346) "
    "fire nothing; one easy endpoint, one homotopy item and one `taken` per recovery, a failed "
    "one included.",
    "A10": "Unchanged physics and specifications across edge 3 on HOM-01…05 (re-binding spied): "
    "the λ = 1 identity and attempt 0's rows, columns and signature are the failed solve's; one "
    "re-binding per distinct λ below 1, each moving `SPEC:SPEC-flash-duty` only; each "
    "`homotopy_step`'s level digest is the target's exactly at λ = 1; a converged fingerprint "
    "carries the revision's identity.",
    "A11": "The A02 family scan: the 180 runs of §9.3 through the plan executor under the "
    "default policy give exactly `ref.a02_family_scan.contract_failures` (contract outcome, edge "
    "3, outcome, λ-trials) and every other run converges by the contract alone, with no "
    "recovery; T03's two registered scan failures are among them; and every run's contract "
    "attempts — signature, core outcome, iterations, decision, in order — equal "
    "`ref.a02_family_scan.contract_attempts` exactly, all 180 records (A11 as amended, review "
    "S4).",
    "A12": "Homotopy records on HOM-01…05: one `homotopy_step` per λ-trial (easy endpoint "
    "included) with λ and Δλ as `p/q`, verdict, corrector outcome and iterations, level digest "
    "(the target's exactly at λ = 1), no `homotopy_level` of its own; every corrector event "
    "stamped with its trial; the attempt's own brackets once; context core `homotopy` with its "
    "continuation; the provenance continuation of `ref`'s path and the item's `iterations` = "
    "each case's `homotopy.provenance_item_iterations` (§4.7 as amended); "
    "`homotopy_stalled(outcome)` on a stall; no float in an R0 string; every event, context and "
    "checkpoint valid.",
    "A13": "The mapping at the P01 root (r = 0.95) and OFF-A: the nonzero-M rows are exactly "
    "the eight `holdup_balance` rows; every entry is §6.3's closed form from the provider's "
    "enthalpies to 1e-9 relative; `PTC_ROW_SIGN` is defined once, in `numerics/ptc.py`, with "
    "`ref.constants.ptc.holdup_row_sign`.",
    "A14": "ADV-04 and the validator: an entry on a mixer row and a missing `FLASH-duty` "
    "(and V1, V3, V4) end `PTC_MAPPING_INVALID` with their R0 message, no attempt, no event, "
    "no residual or Jacobian call; the bundle's class and action are ADR 0010 D8's; Newton "
    "needs no mapping.",
    "A15": "Steady-state equivalence and dimensions: at the P01 roots (r = 0.5, 0.95) the PTC "
    "step at Δτ in {1e-4, 1, 1e10} is within 1e-12 + 10 (θ/Δτ) of the root's own scaled "
    "residual (F14); every mapped holdup has its manifest's dimension, the row's times seconds.",
    "A16": "Reference invariance: with every enthalpy shifted by (1000, −2000, 500) J/mol, the "
    "PTC step at the off-manifold probe (OFF-A, `S3.liq.A` + 0.1 mol/s) is unchanged to 1e-9 "
    "relative, while the heater's duty residual moves.",
    "A17": "Modes: the six finite generalized eigenvalues of the pencil at the P01 root, r = 0.5 "
    "and 0.95 — the four simple ones real and equal to `ref.closed_form.loop_modes` to 1e-9 "
    "relative, the Jordan pair at −1/θ within 1e-6 each with its mean −1/θ to 1e-9 (F14).",
    "A18": "Time-scale invariance: OFF-A (r = 0.95) under PTC with θ, τ₀, τ_min, τ_max all ×8 "
    "gives the same attempts and pseudo-step counts, bit-identical accepted states and final "
    "state, and every Δτ exactly ×8.",
    "A19": "Seeds PTC-S1…S5 on the generic core against `ref.ptc_seeds`: outcomes, attempts, "
    "pseudo-step counts, every trial's order and verdict, `blocked_by`; Δτ, α, x and the SER "
    "proposal to 1e-12 relative; φ to max(1e-12 relative, 1e-15) (F13); PTC-S1's Δτ exact "
    "powers of two; PTC-S4's landing on +0.0 by its bit pattern.",
    "A21": "The accumulation identity (§6.5) on every accepted pseudo-step of every registered "
    "SYN-001 PTC run — the four named runs, the 18 admitted basin starts under PTC and PHS-05 "
    "under PTC — each mole holdup row, within §12's amended bound (F14).",
    "A22": "The polish: every named PTC stop after a pseudo-step records one polish trial, "
    "accepted (and every seed that stops after one); the unpolished stop's K04 material "
    "envelope is `ref`'s (OFF-B at least 1.3 τ), the polished one's at roundoff; K04 `VERIFIED` "
    "on every polished stop (region solves of the nominal declaration, §4.8's guard, empty "
    "tear), `FAILED` with false success on the unpolished OFF-B by its envelope rule.",
    "A23": "Basin comparison (F14): the 45 lattice guesses in `ref`'s order, the 27 refused by "
    "the mixer and nothing run for them, the 18 others with Newton's and PTC's outcomes, "
    "attempts, same_root and polish equal `ref.basin_comparison_r095`; §8.1's criterion gives "
    "`experimental` and V14's PTC clause `incomplete`, as the registry's study entry says; the "
    "named runs of §9.5 as `ref.ptc_named` under both cores, every final state P01's root.",
    "A24": "PHS-05 under PTC (edge 3 off): attempts, reasons and outcome as `ref.ptc_phs05`; "
    "the first pseudo-step's `α_max` is Newton's (`ref.hom.HOM-01`'s contract landing); at the "
    "opening the PTC step's S3.T, split and U-FLASH.Q components are Newton's at Δτ in "
    "{1e-3, 1, 1e3} and the inventory's are not; with the default edge 3 it converges.",
    "A25": "Composition: [A01] on a two-attempt PTC solve (every compiled call and mass "
    "evaluation on its attempt's own context) and per level on the homotopy; the first trial of "
    "every PTC attempt at τ₀; `decide` (spied) closes PHS-05 under PTC's attempts as registered "
    "(row 4's cause included), and T03's stub rows 4–5 take `PTC_STALLED` and "
    "`BUDGET_EXHAUSTED(ptc_steps)`; K03's, T02's and T03's registered trajectories are their test "
    "families, green in the gate.",
    "A27": "Taxonomy: the three outcomes map to ADR 0010 D8's classes and actions; HOM-03's and "
    "HOM-04's bundles carry exactly one registered inferred cause, a hypothesis; the PTC "
    "outcomes' bundles infer nothing; every bundle validates and none claims infeasibility.",
    "A28": "Budgets: HOM-04 with `max_lambda_trials = 4` ends `BUDGET_EXHAUSTED(homotopy_steps)` "
    "after `ref`'s first four λ-trials with the last accepted checkpoint; OFF-A with "
    "`max_steps_per_attempt = 5` ends `BUDGET_EXHAUSTED(ptc_steps)`; a property-budget refusal "
    "inside a corrector (HOM-01) and inside a pseudo-step (the high-recycle plan under PTC) keeps "
    "the attempts, the checkpoint and the provenance (T03 review S1's shape).",
    "A30": "K04 on the bound declaration at the registered certificate states whose verdict "
    "`ref` promises (HOM-01, HOM-02, HOM-05, SYN-001-A02-360, -365): `VERIFIED`, no fail, "
    "unsupported or near-threshold; the declaration's 49 residual rows; the two pressure aliases "
    "with m_e = 0, the plan's; the specification checks of §4.8 with S3.T freed; regularity at "
    "47; witness at most 1e-7; the transformations, identity, provenance and fingerprint; the "
    "target norms equal `ref.bound.target_regularity` to 1e-6 relative.",
    "A31": "Refusals before any check: (i) the nominal entry point handed a bound solve, "
    "(ii) another revision's solve, (iii) a state that is not the fingerprinted one, (iv) a "
    "`CONVERGED` result with neither fingerprint nor plan, with or without a caller-supplied "
    "`solve_plan` (review S1), (vi) A02-360's binding with A02-365's revision document "
    "(`declaration_mismatch(revision)`, review S2; its own document `VERIFIED`) — each its typed "
    "`VerifierError`, no residual call; (v) is K04's own suite, in the gate.",
    "A32": "The promoted specification judged against the revision, both ways, at "
    "SYN-001-A02-365's root: U-FLASH.Q ± 2e-3 W fails exactly the five checks that read it, "
    "each by ±δ; + 5e-4 W is `VERIFIED` with those five near the threshold.",
    "A33": "F9's evidence: SYN-001-A02-355 from 358 K (one TWO_PHASE attempt, 3 iterations) — "
    "the worst row, the independent split of S3 and the heater and flash fresh-flash balances "
    "are `ref.bound.finding_F9`'s to 1e-5 relative, each `near_threshold`; the verdict is "
    "recorded and not asserted (ADR 0007 D2.4).",
}


def build(
    commit: str,
    gate_stdout: Path,
    identities: Path | None,
    ci_run: str | None,
) -> dict[str, Any]:
    ref = reference(REFERENCE)
    t03 = reference(T03_REFERENCE)
    t02 = reference(T02_REFERENCE)
    with tempfile.TemporaryDirectory() as scratch:
        # The generator's two builds run beside everything below (minutes each).
        generator = Generator.start(Path(scratch))
        gate = _gate(gate_stdout)
        runs = Runs()
        checks: list[dict[str, Any]] = []

        def add(identifier: str, measure: Callable[[], tuple[bool, Any, Any]]) -> None:
            checks.append(measured(f"T04.{identifier}", DESCRIPTIONS[identifier], measure))

        add("A01", lambda: _a01(ref))
        add("A02", _a02)
        add("A03", lambda: _a03(runs, ref))
        add("A04", lambda: _a04(runs, ref, t02, t03))
        add("A05", lambda: _a05(runs, ref, t02))
        add("A06", lambda: _a06(runs, ref))
        add("A07", lambda: _a07(runs, ref))
        add("A08", lambda: _a08(runs, ref, t02))
        add("A09", lambda: _a09(runs, ref))
        add("A10", _a10)
        add("A11", lambda: _a11(ref, t03))
        add("A12", lambda: _a12(ref))
        add("A13", lambda: _a13(ref))
        add("A14", _a14)
        add("A15", _a15)
        add("A16", _a16)
        add("A17", lambda: _a17(ref))
        add("A18", _a18)
        add("A19", lambda: _a19(runs, ref))
        checks.append(_a20(runs, ref, checks))
        add("A21", lambda: _a21(runs))
        add("A22", lambda: _a22(runs, ref))
        add("A23", lambda: _a23(runs, ref))
        add("A24", lambda: _a24(runs, ref))
        add("A25", lambda: _a25(runs, ref, gate))
        checks.append(_a26(runs, identities))
        add("A27", lambda: _a27(runs))
        add("A28", lambda: _a28(runs, ref))
        add("A30", lambda: _a30(ref))
        add("A31", _a31)
        add("A32", _a32)
        add("A33", lambda: _a33(ref))
        # A00 last in time (its builds ran beside the rest), first in the list.
        checks.insert(0, measured("T04.A00", DESCRIPTIONS["A00"], lambda: _a00(generator, ref)))

    refused = [
        identifier for identifier in ADR_REQUIREMENTS if _schema_refuses_requirement(identifier)
    ]
    requirements = [identifier for identifier in ADR_REQUIREMENTS if identifier not in refused]
    if tuple(requirements) != A29_REQUIREMENTS:
        raise SystemExit(
            f"ADR 0010's requirements less the schema's refusals are {requirements}, not A29's "
            f"{list(A29_REQUIREMENTS)}"
        )
    limitations = _limitations(ci_run is not None, identities is not None, refused)
    checks.append(_a29(checks, gate, requirements, refused, limitations, ci_run))
    checks.sort(key=lambda entry: int(entry["id"].split(".A")[1]))

    failed = [entry["id"] for entry in checks if entry["result"] == "fail"]
    a00 = checks[0]["value"]
    commands = [
        {
            "cmd": "PATH=.venv/bin:$PATH ./scripts/check.sh",
            "cwd": ".",
            "exit_code": 0 if gate["passed"] else 1,
            "stdout_sha256": hashlib.sha256(gate_stdout.read_bytes()).hexdigest(),
        },
        {
            "cmd": "PATH=.venv/bin:$PATH .venv/bin/python "
            "docs/derivations/scripts/t04_reference.py --check --emit A_YAML",
            "cwd": ".",
            "exit_code": int(a00.get("check_exit_code", 1)) if isinstance(a00, dict) else 1,
        },
        {
            "cmd": "PYTHONPATH=. .venv/bin/python scripts/t04_evidence_manifest.py "
            f"GATE_STDOUT --commit {commit}"
            + (f" --identities {identities.name}" if identities else "")
            + (f" --ci-run {ci_run}" if ci_run else ""),
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
                f"ubuntu-24.04-arm) and `identity`: {ci_run}",
                "cwd": ".",
                "exit_code": 0,
            }
        )

    return {
        "work_package": "T04",
        "commit": commit,
        # The frozen schema takes D/A requirement ids only; V14 is a verification item of plan
        # §5, carried in `docs/requirements.yaml`, which points back here.
        "requirements": requirements,
        "status": _status(checks),
        "inputs": {
            "case_id": "The continuation cases HOM-01..05 (SYN-001-A02-355-dew-guess, "
            "-355-dew-guess-377, -352-vapor-guess-410, -340-two-phase-guess-capped, "
            "-360-iteration-capped), HOM-U (SYN-001-nominal-eo-iteration-capped) and HOM-N; the "
            "A02 family scan (180 runs); the synthetic seeds PTC-S1..S5; the named PTC runs and "
            "the basin comparison on SYN-001-high-recycle and SYN-001-nominal; PHS-05 under PTC; "
            "ADV-04's mapping doubles; T02's SYN-001-A02-355/360/365 from 358 K for the bound "
            "certificates; judged against "
            f"benchmarks/t04/reference_values.yaml ({file_sha256(REFERENCE)}), "
            f"benchmarks/t03/reference_values.yaml ({file_sha256(T03_REFERENCE)}), "
            f"benchmarks/t02/reference_values.yaml ({file_sha256(T02_REFERENCE)}) and "
            f"docs/derivations/T04-globalization-spec.md ({file_sha256(SPEC)})",
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
    parser.add_argument("--out", type=Path, default=None)
    arguments = parser.parse_args()

    manifest = plain(
        build(arguments.commit, arguments.gate_stdout, arguments.identities, arguments.ci_run)
    )
    placeholders = [text for _, text in _strings(manifest) if ANGLE_PLACEHOLDER.search(text)]
    destination = arguments.out or (ROOT / "evidence" / "T04" / arguments.commit / "manifest.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=1, allow_nan=False) + "\n", encoding="utf-8")

    counts = {
        name: sum(entry["result"] == name for entry in manifest["checks"])
        for name in ("pass", "fail", "unsupported", "not_applicable")
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
    return 1 if counts["fail"] or placeholders else 0


if __name__ == "__main__":
    raise SystemExit(main())
