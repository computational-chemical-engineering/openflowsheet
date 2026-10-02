"""Generate `evidence/T05/<commit>/manifest.json` by measuring, not by transcribing. T05.

Every value recorded here is produced by running the code in this process and comparing it with
an independent expectation: `benchmarks/t05/reference_values.yaml` (the design lane's 40-digit twin
of the six unit models, their causal evaluators, four coupled flowsheets and four injected false
successes, emitted by `docs/derivations/scripts/t05_reference.py`), the inertness baseline of
`docs/t05-measurements.md` W0.1 (ADR 0011 D3, measured before any T05 edit), or a closed form
stated in the check itself. Nothing is copied from the specification's prose: a manifest that
quoted the document it is evidence for would be evidence of nothing.

The registered assertions are `docs/derivations/T05-unit-models-spec.md` §15's `A00`…`A30` (A28–A30
added by the ruling round, `docs/briefs/T05-rulings.md` §4), one check each. A28–A30 are retired
by ADR 0012 (T05b spec §16): they are recorded `not_applicable`, `retired by ADR 0012`, with their
replacements named, and not re-measured; T05's manifest at `91ac010` keeps what they measured. The
fixtures — the registered unit cases and trial states, the coupled revisions solved on the common
path, the certificates, the injections' mini-revisions — are imported from the package's tests
(`tests/t05_*.py`, `tests/test_t05_*.py`) so that the manifest and the gate run the same fixtures;
the observation and the comparison with the registered values are stated here. Where an assertion
is established by a family of tests, the numbers it states (worst ratios, counts, exact sets) are
measured here rather than the tests re-run. Every observer records and returns what the code
computed; none alters a value.

Two halves cannot be measured on one machine: A23's structural hash and A24's `t05` identity on
the CI pair (x86-64 and aarch64), which CI's `identity` job establishes. Pass `--identities DIR`
(the downloaded `structural-identity-*` artifacts) and `--ci-run URL`; without them those halves
are `unsupported`, never `pass`. When the CI run's head commit is not the measured one, pass it
as `--ci-commit SHA`: the two may differ only in this generator and the evidence tree (measured by
`git diff`, refused otherwise), and the difference is recorded in `limitations`.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/t05_evidence_manifest.py <gate-stdout> --commit <sha> \
        [--identities DIR] [--ci-run URL] [--ci-commit SHA] [--out PATH]
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
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

# The registered fixtures, shared with the gate (see the module note).
import t05_support as support  # noqa: E402
import t05_trial_states as trial_fixtures  # noqa: E402
import t05_w12_support as w12_support  # noqa: E402
import test_adr_0008_transient_readiness as adr0008_fixtures  # noqa: E402
import test_t05_certificates as certificate_fixtures  # noqa: E402
import test_t05_coupled as coupled_fixtures  # noqa: E402
import test_t05_exchanger as exchanger_fixtures  # noqa: E402
import test_t05_limits as limits_fixtures  # noqa: E402
import test_t05_manifests as manifest_fixtures  # noqa: E402
import test_t05_non_finite_inputs as non_finite_fixtures  # noqa: E402
import test_t05_ph_flash as ph_flash_fixtures  # noqa: E402
import test_t05_pump as pump_fixtures  # noqa: E402
import test_t05_reactor as reactor_fixtures  # noqa: E402
import test_t05_separator as separator_fixtures  # noqa: E402
import test_t05_valve as valve_fixtures  # noqa: E402
import test_t05_w11_cases as w11_fixtures  # noqa: E402
import test_t05_w12_discovery as discovery_fixtures  # noqa: E402
import test_t05_w12_injections as injection_fixtures  # noqa: E402
import test_t05_w12_table as table_fixtures  # noqa: E402
from test_schemas_p01 import schema_errors  # noqa: E402
from test_t04_ptc_region import SpiedCompiled, eo_policy  # noqa: E402

from openflowsheet.canonical import file_sha256  # noqa: E402
from openflowsheet.compile.casadi_backend import compile_problem  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models import SpecificationError, Wiring, origin  # noqa: E402
from openflowsheet.models.syn001.flash import TPFlash  # noqa: E402
from openflowsheet.models.syn001.heater import TPHeater  # noqa: E402
from openflowsheet.models.syn001.ph_flash import PHFlash  # noqa: E402
from openflowsheet.verify.checks import KIND_TOLERANCE  # noqa: E402

REFERENCE = ROOT / "benchmarks" / "t05" / "reference_values.yaml"
SPEC = ROOT / "docs" / "derivations" / "T05-unit-models-spec.md"
ADR = ROOT / "docs" / "adr" / "0011-unit-models-ph-closure-and-reaction-datum.md"
GENERATOR = ROOT / "docs" / "derivations" / "scripts" / "t05_reference.py"
CASES = ROOT / "benchmarks" / "t05" / "cases"
REGISTRY = ROOT / "benchmarks" / "registry.yaml"
FIXTURES = ROOT / "tests" / "fixtures"
SOURCE = ROOT / "src" / "openflowsheet"

#: The coupled cases of spec §11, and the adversarial one outside the denominator.
COUPLED = ("SYN-001-UL-C1", "SYN-001-UL-C2", "SYN-001-UL-C3")
C3X = "SYN-001-UL-C3X"
COMPONENTS = ("A", "B", "C")
#: The assertion ids of spec §15, `A00`…`A30`.
ASSERTIONS = tuple(f"A{index:02d}" for index in range(31))
#: ADR 0011's affected requirements (its header), in its order.
ADR_REQUIREMENTS = ("D08", "V12", "D14", "A09", "D20")

#: ADR 0011 D3's six items as `docs/t05-measurements.md` W0.1 recorded them before any T05 edit
#: (`main` at `279b2eb`). A23 compares today's values with these; none is re-registered here.
BASE_COMMIT = "279b2eb"
W01 = {
    "syn001_py_sha256": "75c9d5bad4f1cb3c8aa28b97d529777949434ebf911c0d9e11568b1e69ddd6ce",
    "structural_sha256": "4ce030cab1e4b4a2402897f480e5194961a1dbe9b8705316ddd4776cbd2d0082",
    "check_policy_sha256": "21c44e105a1b78428047258af3030b8502957aab5d27f0389c2f143bcb3cf390",
    "lifted_splits_repr_sha256": "fc36484e7a89f0e844a0f2e1148ef89052bdd97aaa7a63538685bc505a11e17a",
    "fixture_tree_sha256": "1303efa7b372ff699a2b233f4c48fd24ee9a171db6c8f0f5f64f30e1e2e0f0d1",
    "fixture_files": 78,
    "identity_document_sha256": "b364bb3dc881402fd6e7982532b19f06dba60e5c6b01e70d1aab861bae030b5a",
}
#: The two K02–T04 test files T05 edits, each sanctioned by name and listed in A23's value: spec
#: §21's registry vocabulary (a C3X denominator entry and the closed outcome set), and K04's
#: structural-rank guard found at A28 (a test added, none changed).
SANCTIONED_TEST_EDITS = ("tests/test_k04_regularity.py", "tests/test_schemas_p01.py")
#: A float as `repr` writes one, and a 64-hex digest (T04's patterns, for A24's R0 audit).
FLOAT = re.compile(r"\d\.\d|\de[-+]?\d|\binf\b|\bnan\b")
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


#: ADR 0012 C2 and T05b spec §16: T05 A28, A29 and A30 are retired, each replaced by T05b's
#: assertions (their tests were rewritten against T05b's document). They are recorded as retired,
#: not re-measured: what they measured no longer holds by design (A28's `UNVERIFIED` dormant
#: outlet is `VERIFIED`, A29's refusals are `ok`, A30's `T05-W13` outcomes are T05b's regression
#: values), and T05's manifest at `91ac010`, which measured them, stays as it was.
RETIRED = {"A28": ("T05b.B15",), "A29": ("T05b.B01",), "A30": ("T05b.B08", "T05b.B09")}
RETIRED_BY = "retired by ADR 0012"
#: The last manifest that measured the retired assertions (T05's, unchanged).
RETIRED_EVIDENCE = "evidence/T05/91ac0103c1040175560d74d9afa2a091a8d25b2d/manifest.json"


def retired(identifier: str) -> dict[str, Any]:
    """A retired assertion: `not_applicable` with its replacement named, never `pass` of the
    claim it no longer makes. The registered text stays in the description, marked retired."""
    return check(
        f"T05.{identifier}",
        f"Retired by ADR 0012 (T05b spec §16; ADR 0012 C2), replaced by "
        f"{', '.join(RETIRED[identifier])}; not re-measured. The retired text: "
        + DESCRIPTIONS[identifier],
        "not_applicable",
        {
            "status": RETIRED_BY,
            "replaced_by": list(RETIRED[identifier]),
            "specification": "docs/derivations/T05b-limitations-spec.md §16",
            "last_measured_in": RETIRED_EVIDENCE,
        },
        RETIRED_BY,
    )


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
        (`t05_support.error`); returns the error (`inf` when nothing was measured). A registered
        exact zero is `== 0.0` (§14's exact-zero row), with no tolerance."""
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

    def true(self, where: str, condition: bool) -> bool:
        if not condition:
            self.departures.append(f"{where}: does not hold")
        return condition


def reference(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


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


def worst(ratios: Mapping[str, float]) -> dict[str, Any]:
    """The largest of a set of named ratios, as `{"ratio", "where", "count"}` (A04–A06's
    measured numbers)."""
    if not ratios:
        return {"ratio": None, "where": None, "count": 0}
    where = max(ratios, key=lambda key: ratios[key])
    return {"ratio": ratios[where], "where": where, "count": len(ratios)}


class Runs:
    """Every coupled solve and certificate this manifest measures, run once and shared by the
    checks that read it (A17–A22, A26). The builders are the tests' own — `test_t05_coupled.solve`
    and `test_t05_certificates.certify`, design note §2.1 steps 1–4 verbatim — so the manifest and
    the gate measure the same objects built the same way."""

    def __init__(self) -> None:
        self._solved: dict[str, Any] = {}
        self._certified: dict[str, Any] = {}

    def solved(self, case: str) -> Any:
        if case not in self._solved:
            self._solved[case] = coupled_fixtures.solve(case)
        return self._solved[case]

    def certificate(self, case: str) -> Any:
        if case not in self._certified:
            self._certified[case] = certificate_fixtures.certify(self.solved(case), case)
        return self._certified[case]


# ----------------------------------------------------------------------------------- A00


@dataclass
class Generator:
    """The two generator runs A00 needs, started first so that they run beside everything else:
    one `--check --emit` (the check and the first emission from one build) and one `--emit`."""

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
    counted = re.findall(r"^(\d+) claims passed", output, flags=re.MULTILINE)
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
    registered = list(ref["generator_claims"]["names"])
    value = {
        "check_exit_code": generator.checked.returncode,
        "second_emit_exit_code": generator.second.returncode,
        "claims_passed": int(counted[-1]) if counted else None,
        "claims_listed_in_the_yaml": int(ref["generator_claims"]["count"]),
        "printed_claims_equal_the_yamls_list": printed == registered,
        "import_rule_among_the_claims": "imports_nothing_from_openflowsheet_or_benchmarks"
        in printed,
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
        "claims_passed": len(registered),
        "claims_listed_in_the_yaml": len(registered),
        "printed_claims_equal_the_yamls_list": True,
        "import_rule_among_the_claims": True,
        "digest_in_spec_header": True,
        "emit_twice_identical": True,
        "emit_equals_committed": True,
        "forbidden_imports": [],
    }
    return all(value[key] == expected[key] for key in expected), value, expected


# ----------------------------------------------------------------------------------- A01


def _configuration_label(model_id: str, changes: Mapping[str, Any]) -> str:
    return model_id + "".join(f" {axis}={value}" for axis, value in changes.items())


def _a01(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    models = manifest_fixtures.MODELS
    measured_configurations: dict[str, Any] = {}
    schema_error_count = 0
    statuses: set[str] = set()
    for model_id in manifest_fixtures.MODEL_IDS:
        model = models[model_id]
        for changes in manifest_fixtures.configurations(model):
            where = _configuration_label(model_id, changes)
            document = dict(model.unit(**changes).manifest())
            errors = schema_errors("model_manifest", document)
            schema_error_count += len(errors)
            ledger.equal(f"{where}: schema errors", errors[:3], [])
            ledger.equal(f"{where}: id", document["id"], model_id)
            ledger.equal(
                f"{where}: introduced_by_package", document["introduced_by_package"], "T05"
            )
            ledger.equal(
                f"{where}: planned_package",
                document["implementation_artifact"]["planned_package"],
                "T05",
            )
            statuses.add(document["status"])
            ledger.true(
                f"{where}: status {document['status']!r} is neither reviewed nor released",
                document["status"] not in {"reviewed", "released"},
            )
            requirements = document["execution_requirements"]
            ledger.equal(
                f"{where}: property_provider, reference_convention",
                (requirements["property_provider"], requirements["reference_convention"]),
                ("syn001", "SYN-001-ref-v1"),
            )
            ports = tuple(
                (
                    port["name"],
                    port["kind"],
                    port["direction"],
                    port["multiplicity"],
                    tuple(port["phase_capabilities"]),
                )
                for port in document["ports"]
            )
            ledger.equal(f"{where}: ports", ports, model.ports)
            equations = {entry["id"]: entry for entry in document["mathematics"]["equations"]}
            ledger.equal(f"{where}: equations", list(equations), list(model.equations))
            classes = {key: entry.get("conditional_class") for key, entry in equations.items()}
            ledger.equal(
                f"{where}: conditional classes",
                classes,
                {key: entry[2] for key, entry in model.equations.items()},
            )
            derivatives = {entry["output"]: entry for entry in document["derivatives"]}
            residuals = derivatives.pop("residuals", {})
            ledger.equal(
                f"{where}: residuals derivative",
                (residuals.get("method"), residuals.get("regime")),
                ("ad", "all"),
            )
            outlets = {f"{port[0]}.state" for port in model.ports if port[2] == "outlet"}
            ledger.true(f"{where}: every outlet sensitivity declared", outlets <= set(derivatives))
            methods = {output: entry["method"] for output, entry in derivatives.items()}
            ledger.equal(
                f"{where}: sensitivities", methods, dict.fromkeys(derivatives, "unavailable")
            )
            measured_configurations[where] = {
                "schema_errors": len(errors),
                "status": document["status"],
                "ports": len(ports),
                "equations": len(equations),
                "sensitivities_unavailable": sum(m == "unavailable" for m in methods.values()),
            }

    # Spec §5.1 as amended by T05b (T05b spec §16): the near-pure limitation and §4.7 (a), (b)
    # are retired; the PH-type manifests state the kernel's acceptance (T05b §5.1–§5.3) and the
    # EO outcome under each literal (T05b §6.6, §11), each once, each citing its section.
    citations = manifest_fixtures.REGISTERED_LIMITATION_CITATIONS
    retired = manifest_fixtures.RETIRED_LIMITATION_CITATIONS
    limitations: dict[str, Any] = {}
    for model_id in ("syn001.ph_flash", "syn001.valve", "syn001.conversion_reactor"):
        stated = models[model_id].unit().manifest()["validity"]["limitations"]
        counts = {citation: sum(citation in text for text in stated) for citation in citations}
        ledger.equal(f"{model_id}: limitation citations", counts, dict.fromkeys(citations, 1))
        ledger.equal(
            f"{model_id}: retired citations",
            [citation for citation in retired if any(citation in text for text in stated)],
            [],
        )
        kernel = [text for text in stated if citations[0] in text]
        eo = [text for text in stated if citations[1] in text]
        ledger.true(
            f"{model_id}: the kernel's statement names ph_ill_conditioned and tau_E",
            all("ph_ill_conditioned" in text and "tau_E" in text for text in kernel),
        )
        ledger.true(
            f"{model_id}: the EO statement names both literals",
            all(all(literal in text for literal in manifest_fixtures.LITERALS) for text in eo),
        )
        # T05b spec §16 (Q-S9 addendum): the PH flash alone states the dew/bubble-point
        # exception to "solved and certified", verbatim.
        ledger.equal(
            f"{model_id}: the dew-point limitation",
            stated.count(manifest_fixtures.DEW_POINT_LIMITATION),
            int(model_id == "syn001.ph_flash"),
        )
        limitations[model_id] = counts

    per_model = Counter(label.split(" ", 1)[0] for label in measured_configurations)
    value = {
        "configurations": len(measured_configurations),
        "configurations_per_model": dict(sorted(per_model.items())),
        "schema_errors": schema_error_count,
        "statuses": sorted(statuses),
        "limitation_citations": limitations,
        "per_configuration": measured_configurations,
        "departures": ledger.departures,
    }
    expected = {
        "configurations": sum(
            len(manifest_fixtures.configurations(models[m])) for m in manifest_fixtures.MODEL_IDS
        ),
        "schema_errors": 0,
        "statuses": "neither reviewed nor released",
        "per_configuration": "id, T05 packages, provider syn001, convention SYN-001-ref-v1, the "
        "port and equation tables of spec §5-§10, residuals ad/all, every sensitivity "
        "unavailable",
        "limitation_citations": "T05b spec §5.1-§5.3 and §6.6 each cited exactly once, and no "
        "retired citation (spec §4.4, §4.7 (a), §4.7 (b); T05b spec §16), in the PH flash's, the "
        "valve's and the reactor's manifests; the PH flash alone states T05b §16's dew-point "
        "sentence verbatim",
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A02


def _a02(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    # Every equation of the six manifests at every configuration; a key carries one accumulation
    # block across configurations (measured, not assumed: the first departure is recorded).
    equations: dict[tuple[str, str], dict[str, Any]] = {}
    for model_id in manifest_fixtures.MODEL_IDS:
        model = manifest_fixtures.MODELS[model_id]
        for changes in manifest_fixtures.configurations(model):
            for equation in dict(model.unit(**changes).manifest())["mathematics"]["equations"]:
                key = (model_id, equation["id"])
                if key in equations:
                    ledger.equal(
                        f"{key}: accumulation across configurations",
                        equation["accumulation"],
                        equations[key]["accumulation"],
                    )
                else:
                    equations[key] = equation
    kinds = {key: equation["accumulation"]["kind"] for key, equation in equations.items()}
    ledger.equal("classification", kinds, manifest_fixtures.REGISTERED_KINDS)
    counts = Counter(kinds.values())

    holdups: dict[str, Any] = {}
    time_index = manifest_fixtures.TIME_INDEX
    for equation_id, (symbol, dimension) in sorted(manifest_fixtures.REGISTERED_HOLDUPS.items()):
        (equation,) = [eq for (_, eq_id), eq in equations.items() if eq_id == equation_id]
        holdup = equation["accumulation"]["holdup"]
        row = list(dimension)
        row[time_index] -= 1
        holdups[equation_id] = {
            "symbol": holdup["symbol"],
            "dimension": holdup["dimension"],
            "row_dimension": equation["dimension"],
        }
        ledger.equal(
            f"{equation_id}: holdup",
            holdups[equation_id],
            {"symbol": symbol, "dimension": dimension, "row_dimension": row},
        )
    statements = {
        eq_id: equation["statement"]
        for (_, eq_id), equation in equations.items()
        if equation["accumulation"]["kind"] != "algebraic"
    }
    ledger.equal("balance statements", statements, manifest_fixtures.REGISTERED_STATEMENTS)
    reasons = {
        f"{model_id}:{eq_id}": equation["accumulation"]["reason"]
        for (model_id, eq_id), equation in equations.items()
        if equation["accumulation"]["kind"] == "zero_holdup_balance"
    }
    ledger.equal(
        "zero-holdup reasons",
        reasons,
        {
            f"{model_id}:{eq_id}": manifest_fixtures.REGISTERED_REASONS[model_id]
            for (model_id, eq_id), kind in manifest_fixtures.REGISTERED_KINDS.items()
            if kind == "zero_holdup_balance"
        },
    )

    # ADR 0008 M1-M5 on the six P01 manifests, with the ADR's own registered tables (the pins of
    # `tests/test_adr_0008_transient_readiness.py`, unchanged since 279b2eb: A23 (ii)).
    p01 = adr0008_fixtures.declared_equations()
    # Every manifest in the directory M1-M5 read (the sink declares no equation, so it is counted
    # from the files, not from the equations).
    p01_models = sorted(
        str(yaml.safe_load(path.read_text(encoding="utf-8"))["id"])
        for path in adr0008_fixtures.MANIFEST_DIR.glob("*.yaml")
    )
    p01_kinds = {key: equation["accumulation"]["kind"] for key, equation in p01.items()}
    m_items: dict[str, bool] = {"M1": p01_kinds == adr0008_fixtures.REGISTERED_KINDS}
    m2 = True
    for equation_id, (symbol, dimension) in adr0008_fixtures.REGISTERED_HOLDUPS.items():
        equation = next(eq for (_, eq_id), eq in p01.items() if eq_id == equation_id)
        row = list(dimension)
        row[adr0008_fixtures.TIME_INDEX] -= 1
        holdup = equation["accumulation"]["holdup"]
        m2 = m2 and (holdup["symbol"], holdup["dimension"], equation["dimension"]) == (
            symbol,
            dimension,
            row,
        )
    m_items["M2"] = m2
    p01_counts = Counter(p01_kinds.values())
    m_items["M3"] = p01_counts == Counter(
        {"algebraic": 15, "zero_holdup_balance": 2, "holdup_balance": 4}
    )
    m_items["M4"] = all(
        next(eq for (_, eq_id), eq in p01.items() if eq_id == equation_id)["statement"] == text
        for equation_id, text in adr0008_fixtures.REGISTERED_STATEMENTS.items()
    )
    m_items["M5"] = all(
        "junction" in equation["accumulation"]["reason"].lower()
        for equation in p01.values()
        if equation["accumulation"]["kind"] == "zero_holdup_balance"
    )
    ledger.equal("ADR 0008 M1-M5 on the P01 manifests", m_items, dict.fromkeys(m_items, True))
    overlap = sorted(set(p01_models) & set(manifest_fixtures.MODELS))
    ledger.equal("T05 manifests among the P01 fixtures (F4)", overlap, [])
    ledger.equal("P01 manifests", len(p01_models), 6)

    value = {
        "equations": len(kinds),
        "kinds": dict(sorted(counts.items())),
        "holdups": holdups,
        "balance_statements": len(statements),
        "zero_holdup_reasons": len(reasons),
        "adr_0008_on_p01": {
            "manifests": p01_models,
            "rows": len(p01_kinds),
            "kinds": dict(sorted(p01_counts.items())),
            **m_items,
        },
        "t05_manifests_among_p01_fixtures": overlap,
        "departures": ledger.departures,
    }
    expected = {
        "equations": len(manifest_fixtures.REGISTERED_KINDS),
        "kinds": {"algebraic": 17, "holdup_balance": 8, "zero_holdup_balance": 6},
        "classification": "spec §13.2's table as a literal dict, key for key",
        "holdups": "spec §13.2's symbol and dimension; the row's time exponent one lower (D3.2)",
        "balance_statements": len(manifest_fixtures.REGISTERED_STATEMENTS),
        "zero_holdup_reasons": "spec §7-§9's reason, verbatim",
        "adr_0008_on_p01": {
            "rows": 21,
            "kinds": {"algebraic": 15, "holdup_balance": 4, "zero_holdup_balance": 2},
            **dict.fromkeys(m_items, True),
        },
        "t05_manifests_among_p01_fixtures": [],
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A03


def _a03_contribution(
    model: Any, changes: Mapping[str, Any], ledger: Ledger, where: str
) -> dict[str, Any]:
    """The unit's contribution at one configuration against the declared tables (§5-§10)."""
    model_id = model.model_id
    unit = model.unit(**changes)
    contribution = unit.contribute(Wiring(dict(model.wiring)), COMPONENTS)
    equations = {eq_id: (count, kind) for eq_id, (count, kind, _) in model.equations.items()}
    pinned = list(model.pinned)
    selected, selected_kind, selected_pin = manifest_fixtures.expected_specification(model, changes)
    if selected:
        equations[selected] = (1, selected_kind)
        pinned[-1] = selected_pin
    declared = {
        origin(model_id, equation.equation_id): equation.accumulation.kind
        for equation in unit.declared_equations()
    }
    ledger.equal(
        f"{where}: declared origins",
        sorted(declared),
        sorted(origin(model_id, eq_id) for eq_id in model.equations),
    )
    lifting = origin(model_id, "lifting")
    rows = Counter(equation.origin for equation in contribution.equations)
    expected_rows = Counter({origin(model_id, eq_id): n for eq_id, (n, _) in equations.items()})
    if model.lifting:
        expected_rows[lifting] = model.lifting
    ledger.equal(f"{where}: rows per origin", dict(rows), dict(expected_rows))
    kind_departures = []
    for equation in contribution.equations:
        kind = contribution.row_kinds[equation.equation_id]
        if equation.origin == lifting:
            if (equation.accumulation, kind) != ("algebraic", "molar_flow"):
                kind_departures.append(equation.equation_id)
            continue
        eq_id = equation.origin.split("#", 1)[1]
        if (
            equation.accumulation != declared.get(equation.origin)
            or kind != equations[eq_id][1]
            or not equation.equation_id.startswith(f"{unit.unit_id}:{eq_id}")
        ):
            kind_departures.append(equation.equation_id)
    ledger.equal(f"{where}: rows off their declared kind, accumulation or id", kind_departures, [])
    ids = [equation.equation_id for equation in contribution.equations]
    ledger.equal(f"{where}: duplicated row ids", len(ids) - len(set(ids)), 0)
    ledger.equal(f"{where}: owned variables", dict(contribution.variable_kinds), dict(model.owned))
    ledger.equal(f"{where}: owned order", list(contribution.variable_ids), list(model.owned))
    ledger.equal(f"{where}: pinned inputs", list(contribution.parameter_ids), pinned)
    unknowns = len(model.outlet_streams) * (len(COMPONENTS) + 2) + len(contribution.variable_ids)
    ledger.equal(f"{where}: rows = unknowns given the inlets", len(ids), unknowns)
    return {"rows": len(ids), "unknowns": unknowns, "lifting_rows": rows.get(lifting, 0)}


def _a03(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    models = manifest_fixtures.MODELS
    contributions: dict[str, Any] = {}
    for model_id in manifest_fixtures.MODEL_IDS:
        model = models[model_id]
        for changes in manifest_fixtures.configurations(model):
            where = _configuration_label(model_id, changes)
            contributions[where] = _a03_contribution(model, changes, ledger, where)
    square = sum(entry["rows"] == entry["unknowns"] for entry in contributions.values())

    # Unit level: a pinned-input change keeps `model_version` and moves `constants_sha256`.
    pinned_changes: dict[str, Any] = {}
    for model_id in manifest_fixtures.MODEL_IDS:
        model = models[model_id]
        nominal = manifest_fixtures._metadata(model, {})
        moved = manifest_fixtures._metadata(model, manifest_fixtures.PINNED_CHANGES[model_id])
        pinned_changes[model_id] = {
            "model_version_equal": moved.model_version == nominal.model_version,
            "constants_sha256_differs": moved.constants_sha256 != nominal.constants_sha256,
        }
        ledger.equal(
            f"pinned change {model_id}",
            pinned_changes[model_id],
            {"model_version_equal": True, "constants_sha256_differs": True},
        )
    # Unit level: a configuration that moves an id moves `model_version` through the ids.
    structural: dict[str, bool] = {}
    for model_id, before, after in manifest_fixtures.STRUCTURAL_CONFIGURATIONS:
        where = f"{_configuration_label(model_id, before)} -> {dict(after)}"
        model = models[model_id]
        structural[where] = (
            manifest_fixtures._metadata(model, before).model_version
            != manifest_fixtures._metadata(model, after).model_version
        )
        ledger.true(f"structural configuration {where}: model_version moves", structural[where])
    # Unit level: a configuration that moves no id keeps the structure hash and the ids, and the
    # rows differ at one state (the function differs).
    label_axes: dict[str, Any] = {}
    for model_id, before, after in manifest_fixtures.LABEL_CONFIGURATIONS:
        where = f"{_configuration_label(model_id, before)} -> {dict(after)}"
        model = models[model_id]
        first, names = manifest_fixtures._compiled(model, before)
        second, other_names = manifest_fixtures._compiled(model, after)
        x = manifest_fixtures._generic_state(names)
        residuals = []
        for problem in (first, second):
            context = EvaluationContext(
                model_version=problem.metadata.model_version,
                constants_sha256=problem.metadata.constants_sha256,
            )
            result = problem.residual(x, context)
            residuals.append(np.asarray(result.values) if result.status == "ok" else None)
        differ = (
            residuals[0] is not None
            and residuals[1] is not None
            and not np.array_equal(residuals[0], residuals[1])
        )
        label_axes[where] = {
            "ids_equal": other_names == names
            and first.metadata.equation_ids == second.metadata.equation_ids,
            "structure_hash_equal": first.metadata.model_version.split("@")[1]
            == second.metadata.model_version.split("@")[1],
            "rows_differ": differ,
            "rows_changed": int(np.count_nonzero(residuals[0] != residuals[1])) if differ else 0,
        }
        ledger.equal(
            f"label configuration {where}",
            {key: label_axes[where][key] for key in ("ids_equal", "structure_hash_equal")},
            {"ids_equal": True, "structure_hash_equal": True},
        )
        ledger.true(f"label configuration {where}: rows differ", differ)
    # Flowsheet level (R-047): a configuration change moves the revision flowsheet's label and
    # `model_version`; a pinned value moves neither and moves `constants_sha256`.
    flowsheet_configuration: dict[str, bool] = {}
    for name, (make, change) in sorted(w11_fixtures.CONFIGURATION_CHANGES.items()):
        base, changed = make(), make()
        change(changed)
        (label, version), (moved, moved_version) = (
            w11_fixtures._label(base),
            w11_fixtures._label(changed),
        )
        flowsheet_configuration[name] = moved != label and moved_version != version
        ledger.true(f"flowsheet configuration {name}: label moves", moved != label)
        ledger.true(
            f"flowsheet configuration {name}: model_version moves", moved_version != version
        )
    flowsheet_value: dict[str, Any] = {}
    for name, (make, change) in sorted(w11_fixtures.VALUE_CHANGES.items()):
        base, changed = make(), make()
        change(changed)
        first_binding, second_binding = w11_fixtures._bind(base), w11_fixtures._bind(changed)
        flowsheet_value[name] = {
            "label_and_model_version_equal": w11_fixtures._label(changed)
            == w11_fixtures._label(base),
            "constants_sha256_differs": w11_fixtures.declaration_identity(second_binding.spec)[1]
            != w11_fixtures.declaration_identity(first_binding.spec)[1],
        }
        ledger.equal(
            f"flowsheet pinned value {name}",
            flowsheet_value[name],
            {"label_and_model_version_equal": True, "constants_sha256_differs": True},
        )

    value = {
        "configurations": len(contributions),
        "square_given_inlets": square,
        "rows_per_configuration": {key: entry["rows"] for key, entry in contributions.items()},
        "unit_pinned_changes": pinned_changes,
        "unit_configurations_moving_an_id": structural,
        "unit_configurations_moving_no_id": label_axes,
        "flowsheet_configurations": flowsheet_configuration,
        "flowsheet_pinned_values": flowsheet_value,
        "departures": ledger.departures,
    }
    expected = {
        "configurations": len(contributions),
        "square_given_inlets": len(contributions),
        "rows": "per declared equation its §5-§10 row count, kind and accumulation; lifting rows "
        "origin model#lifting, algebraic, molar_flow; owned variables and pinned-input ids as "
        "§5-§10",
        "unit_pinned_changes": "model_version equal, constants_sha256 differs (ADR 0008 D4.1)",
        "unit_configurations_moving_an_id": "model_version differs",
        "unit_configurations_moving_no_id": "ids and structure hash equal, rows differ",
        "flowsheet_configurations": dict.fromkeys(flowsheet_configuration, True),
        "flowsheet_pinned_values": "label and model_version equal, constants_sha256 differs",
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A16


def _catalogue_pattern(line: str) -> list[str]:
    """The §13.3 patterns a first line matches (as the regular expressions, which carry no
    angle-bracketed placeholder)."""
    return [manifest_fixtures.CATALOGUE[code] for code in manifest_fixtures.catalogued(line)]


def _non_finite_refusals(ledger: Ledger) -> dict[str, Any]:
    """Spec §3.5/§5.1 as amended (ruling round, U1 (2)): every numeric constructor input of the
    six models × {nan, +inf, -inf} is refused at construction, with its registered code or
    `ValueError` (the table of `tests/test_t05_non_finite_inputs.py`)."""
    outcomes: Counter[str] = Counter()
    for parameter in non_finite_fixtures.TABLE:
        model_id, changes, field_name, index, label, expected = parameter.values
        nominal = manifest_fixtures.MODELS[model_id].unit(**changes)
        number = non_finite_fixtures.NON_FINITE[label]
        if index is None:
            replacement: Any = number
        else:
            vector = list(getattr(nominal, field_name))
            vector[index] = number
            replacement = tuple(vector)
        where = f"{model_id}.{field_name}{'' if index is None else f'[{index}]'}={label}"
        try:
            dataclasses.replace(nominal, **{field_name: replacement})
        except SpecificationError as error:
            got = support.first_line(str(error))
        except ValueError as error:
            got = None if "not finite" in str(error) else f"ValueError: {error}"
        else:
            got = "accepted"
        outcomes["ValueError" if got is None else "registered code"] += got == expected
        ledger.equal(f"non-finite {where}", got, expected)
    return {"inputs": len(non_finite_fixtures.TABLE), "refused_as_registered": dict(outcomes)}


def _a16(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    lines = manifest_fixtures.registered_first_lines()
    per_case: dict[str, Any] = {}
    for case_id, line in lines.items():
        registered = (
            ref["unit_cases"][case_id]["expected"]["code"]
            if case_id in ref["unit_cases"]
            else ref["specification_errors"][case_id]["code"]
        )
        matched = _catalogue_pattern(line)
        per_case[case_id] = line
        ledger.equal(f"{case_id}: first line", line, registered)
        ledger.equal(f"{case_id}: §13.3 codes matched", len(matched), 1)
    constructed = manifest_fixtures.constructed_first_lines()
    constructed_codes = {name: _catalogue_pattern(line) for name, line in constructed.items()}
    ledger.equal(
        "constructed cases",
        constructed_codes,
        {
            name: [manifest_fixtures.CATALOGUE[code]]
            for name, code in (
                ("PHF-1 at 450 K", "state_outside_domain(<port>)"),
                ("HX-3 at 1 MW", "outlet_outside_domain"),
                # T05b spec §16 (commit `09a7feb`): PHF-6's near-pure construction no longer
                # refuses (the band route answers it); A16's `ph_ill_conditioned` case is PHF-1
                # on the JUMP double, the one registered way the kernel refuses.
                ("PHF-1 on the JUMP double", "ph_ill_conditioned"),
                ("PHF-1 with a 10-evaluation budget", "ph_not_converged"),
            )
        },
    )
    by_registered = {code for line in lines.values() for code in manifest_fixtures.catalogued(line)}
    produced = by_registered | {
        code for line in constructed.values() for code in manifest_fixtures.catalogued(line)
    }
    unproduced = sorted(
        manifest_fixtures.CATALOGUE[code] for code in set(manifest_fixtures.CATALOGUE) - produced
    )
    ledger.equal("§13.3 codes produced by registered cases", len(by_registered), 22)
    ledger.equal("§13.3 codes produced by no case", unproduced, [])
    non_finite = _non_finite_refusals(ledger)
    unit_failures = sum(case_id in ref["unit_cases"] for case_id in lines)
    value = {
        "registered_failure_cases": unit_failures,
        "construction_cases": len(lines) - unit_failures,
        "first_lines": per_case,
        "constructed_first_lines": constructed,
        "catalogue_codes": len(manifest_fixtures.CATALOGUE),
        "codes_produced_by_registered_cases": len(by_registered),
        "codes_produced": len(produced),
        "codes_produced_by_no_case": unproduced,
        "non_finite_constructor_inputs": non_finite,
        "departures": ledger.departures,
    }
    expected = {
        "first_lines": "each registered failure and construction case's registered code, byte "
        "for byte, matching exactly one §13.3 code",
        "catalogue_codes": 26,
        "codes_produced_by_registered_cases": 22,
        "codes_produced": 26,
        "codes_produced_by_no_case": [],
        "non_finite_constructor_inputs": "every one refused at construction, with its registered "
        "code or ValueError (not finite)",
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- A04, A05

#: The six models' trial-state builders, the tests' own (`build_trial` of each model's module).
TRIAL_BUILDERS = {
    module.MODEL_ID: module.build_trial
    for module in (
        ph_flash_fixtures,
        valve_fixtures,
        pump_fixtures,
        reactor_fixtures,
        separator_fixtures,
        exchanger_fixtures,
    )
}
_TRIALS: dict[tuple[str, str], dict[str, Any]] = {}


def _trial(model_id: str, state_id: str) -> dict[str, Any]:
    """One unit at `ref.trial_states.<model>.<state>`: assembled by the tests' harness
    (`t05_trial_states.assemble_trial` on the model test's `build_trial`), compiled through K01,
    and its rows and stored Jacobian entries evaluated at the registered `x`. Shared by A04 and
    A05; nothing is compared here."""
    key = (model_id, state_id)
    if key in _TRIALS:
        return _TRIALS[key]
    entry = support.REF["trial_states"][model_id]["states"][state_id]
    trial = TRIAL_BUILDERS[model_id](entry["configuration"], entry["parameters"])
    spec = trial_fixtures.assemble_trial(trial, label=f"T05-trial-{model_id}-{state_id}")
    measured_trial: dict[str, Any] = {
        "entry": entry,
        "columns": set(spec.variable_ids),
        "row_ids": [equation.equation_id for equation in spec.equations],
        "row_kinds": dict(spec.row_kinds),
        "rows": None,
        "stored": None,
        "errors": [],
    }
    _TRIALS[key] = measured_trial
    if measured_trial["columns"] != set(entry["x"]):
        measured_trial["errors"].append("columns differ from the registered x")
        return measured_trial
    problem = compile_problem(spec)
    context = EvaluationContext(
        model_version=problem.metadata.model_version,
        constants_sha256=problem.metadata.constants_sha256,
    )
    x = np.array([float(entry["x"][name]) for name in spec.variable_ids])
    residual = problem.residual(x, context)
    if residual.status != "ok" or residual.values is None:
        measured_trial["errors"].append(f"residual: {residual.status} {residual.message}")
    else:
        measured_trial["rows"] = {
            row: float(value)
            for row, value in zip(residual.equation_ids, residual.values, strict=True)
        }
    jacobian = problem.jacobian(x, context)
    if jacobian.status != "ok":
        measured_trial["errors"].append(f"jacobian: {jacobian.status} {jacobian.message}")
    else:
        stored: dict[tuple[str, str], float] = {}
        for column, column_id in enumerate(jacobian.col_ids):
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
                row = jacobian.row_ids[jacobian.indices[offset]]
                stored[(row, column_id)] = float(jacobian.data[offset])
        measured_trial["stored"] = stored
    return measured_trial


def _trial_keys() -> list[tuple[str, str]]:
    return [
        (model_id, state_id)
        for model_id in support.REF["trial_states"]
        for state_id in trial_fixtures.trial_states(model_id)
    ]


def _a04(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    tolerance = float(ref["constants"]["row_relative_tolerance"])
    per_model: dict[str, dict[str, float]] = {}
    per_state: dict[str, Any] = {}
    overall: dict[str, float] = {}
    for model_id, state_id in _trial_keys():
        where = f"{model_id} {state_id}"
        trial = _trial(model_id, state_id)
        entry = trial["entry"]
        registered_rows: Mapping[str, Mapping[str, str]] = entry["rows"]
        for error in trial["errors"]:
            ledger.true(f"{where}: {error}", False)
        ledger.equal(f"{where}: columns", sorted(trial["columns"]), sorted(entry["x"]))
        ledger.equal(f"{where}: row ids", sorted(trial["row_ids"]), sorted(registered_rows))
        ledger.equal(
            f"{where}: no duplicate row", len(set(trial["row_ids"])), len(trial["row_ids"])
        )
        kinds = {row: trial["row_kinds"].get(row) for row in registered_rows}
        ledger.equal(
            f"{where}: row kinds",
            kinds,
            {row: registered["kind"] for row, registered in registered_rows.items()},
        )
        ratios: dict[str, float] = {}
        for row, value in (trial["rows"] or {}).items():
            registered = registered_rows.get(row)
            if registered is None:
                continue
            allowed = tolerance * float(registered["term_scale"])
            ratios[row] = support.error(value, str(registered["value"])) / allowed
            ledger.true(
                f"{where}: {row} = {value!r}, registered {registered['value']}", ratios[row] <= 1.0
            )
        per_state[where] = {"rows": len(trial["row_ids"]), "worst": worst(ratios)}
        per_model.setdefault(model_id, {}).update(
            {f"{state_id} {row}": ratio for row, ratio in ratios.items()}
        )
        overall.update({f"{where} {row}": ratio for row, ratio in ratios.items()})
    value = {
        "states": len(per_state),
        "per_state": per_state,
        "worst_row_ratio_per_model": {model: worst(r) for model, r in per_model.items()},
        "worst_row_ratio": worst(overall),
        "departures": ledger.departures,
    }
    expected = {
        "states": 12,
        "per_state": "the registered row-id set, kinds and columns; every row within "
        f"{tolerance:g} x its registered term_scale",
        "worst_row_ratio": "at most 1 (the ratio is |row - ref| / (1e-12 x term_scale))",
    }
    ledger.equal("trial states", len(per_state), 12)
    return ledger.ok, value, expected


def _a05(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    relative = float(ref["constants"]["jacobian_relative_tolerance"])
    nonzero: dict[str, float] = {}
    cancelling: dict[str, float] = {}
    per_state: dict[str, Any] = {}
    off_registration_nonzero: list[str] = []
    for model_id, state_id in _trial_keys():
        where = f"{model_id} {state_id}"
        trial = _trial(model_id, state_id)
        entry = trial["entry"]
        stored: dict[tuple[str, str], float] | None = trial["stored"]
        if stored is None:
            ledger.true(f"{where}: Jacobian evaluated ({trial['errors']})", False)
            continue
        checked: set[tuple[str, str]] = set()
        state_nonzero: dict[str, float] = {}
        state_cancelling: dict[str, float] = {}
        for row, column, registered in entry["jacobian"]:
            checked.add((row, column))
            got = stored.get((row, column), 0.0)
            scale = abs(Decimal(registered))
            ratio = float(abs(Decimal(got) - Decimal(registered)) / scale) / relative
            state_nonzero[f"{row} / {column}"] = ratio
            ledger.true(
                f"{where}: d({row})/d({column}) = {got!r}, registered {registered}", ratio <= 1.0
            )
        for row, column, partial_scale in entry["cancelling_partials"]:
            checked.add((row, column))
            got = stored.get((row, column), 0.0)
            ratio = abs(got) / (relative * float(partial_scale))
            state_cancelling[f"{row} / {column}"] = ratio
            ledger.true(
                f"{where}: cancelling d({row})/d({column}) = {got!r}, scale {partial_scale}",
                ratio <= 1.0,
            )
        unregistered = [key for key in stored if key not in checked]
        stray = [
            f"{where}: d({r})/d({c}) = {stored[(r, c)]!r}"
            for r, c in unregistered
            if stored[(r, c)] != 0.0
        ]
        off_registration_nonzero += stray
        per_state[where] = {
            "registered_nonzeros": len(entry["jacobian"]),
            "cancelling_partials": len(entry["cancelling_partials"]),
            "other_stored_entries": len(unregistered),
            "other_entries_not_exactly_zero": len(stray),
            "worst_nonzero": worst(state_nonzero),
        }
        nonzero.update({f"{where} {key}": ratio for key, ratio in state_nonzero.items()})
        cancelling.update({f"{where} {key}": ratio for key, ratio in state_cancelling.items()})
    ledger.equal(
        "entries off the registration that are not exactly 0.0", off_registration_nonzero, []
    )
    value = {
        "states": len(per_state),
        "per_state": per_state,
        "worst_nonzero_ratio": worst(nonzero),
        "cancelling_partials": {key: ratio for key, ratio in cancelling.items()},
        "worst_cancelling_ratio": worst(cancelling),
        "other_entries_not_exactly_zero": off_registration_nonzero,
        "departures": ledger.departures,
    }
    expected = {
        "states": 12,
        "worst_nonzero_ratio": f"at most 1 (relative error / {relative:g})",
        "worst_cancelling_ratio": f"at most 1 (|entry| / ({relative:g} x partial scale))",
        "other_entries_not_exactly_zero": [],
    }
    ledger.equal("trial states", len(per_state), 12)
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------- A06, A15


def _a06(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """The tests' `rows_at_solution`: each case's unit alone, at the twin's causal solution with
    every coordinate rounded once to a double; each row's `|value| / τ_kind` (K04's
    `KIND_TOLERANCE`)."""
    ledger = Ledger()
    ledger.equal(
        "A06's cases",
        list(limits_fixtures.A06_CASES),
        [
            "PHF-1",
            "PHF-5",
            "PHF-6",
            "VLV-2",
            "VLV-5",
            "PUMP-1",
            "RX-3",
            "RX-4",
            "RX-5",
            "SEP-2",
            "HX-1",
            "HX-4",
        ],
    )
    per_case: dict[str, Any] = {}
    overall: dict[str, float] = {}
    for case_id in limits_fixtures.A06_CASES:
        ledger.equal(
            f"{case_id}: registered status", ref["unit_cases"][case_id]["expected"]["status"], "ok"
        )
        rows = limits_fixtures.rows_at_solution(case_id)
        ratios = {row: size / KIND_TOLERANCE[kind] for row, (size, kind) in rows.items()}
        found = worst(ratios)
        per_case[case_id] = found
        overall.update({f"{case_id} {row}": ratio for row, ratio in ratios.items()})
        ledger.true(
            f"{case_id}: {found['where']} at {found['ratio']:.3g} of tau", found["ratio"] <= 1.0
        )
    value = {
        "per_case": per_case,
        "worst_ratio": worst(overall),
        "departures": ledger.departures,
    }
    expected = {
        "per_case": "every row's |value| / tau_kind at most 1 (the expected value is 0)",
        "tau_kind": dict(KIND_TOLERANCE),
    }
    return ledger.ok, value, expected


def _a15(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """At each registered dormant state (the tests' `DORMANT_STATES`), the rows in which each
    listed temperature's Jacobian column holds a nonzero entry."""
    ledger = Ledger()
    structure: Mapping[str, Mapping[str, list[str]]] = ref["dormant_temperature_columns"][
        "structure"
    ]
    ledger.equal("dormant states", sorted(limits_fixtures.DORMANT_STATES), sorted(structure))
    measured_rows: dict[str, dict[str, list[str]]] = {}
    for key in sorted(limits_fixtures.DORMANT_STATES):
        case_id, changes = limits_fixtures.DORMANT_STATES[key]
        case = ref["unit_cases"][case_id]
        model = limits_fixtures.MODELS[case["model"]]
        inputs = {**case["inputs"], **changes}
        evaluated = limits_fixtures.evaluate_at(
            model,
            model.build(inputs),
            inputs.get("inlet_phase", "LIQUID"),
            limits_fixtures.registered_state(case_id),
        )
        jacobian = evaluated.problem.jacobian(evaluated.x, evaluated.context)
        if jacobian.status != "ok":
            ledger.true(f"{key}: Jacobian {jacobian.status} {jacobian.message}", False)
            continue
        columns = list(jacobian.col_ids)
        measured_rows[key] = {}
        for column_id, registered in structure.get(key, {}).items():
            column = columns.index(column_id)
            reading = sorted(
                {
                    jacobian.row_ids[jacobian.indices[offset]]
                    for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1])
                    if jacobian.data[offset] != 0.0
                }
            )
            measured_rows[key][column_id] = reading
            ledger.equal(f"{key} ({case_id}): column {column_id}", reading, sorted(registered))
    value = {
        "states": {key: limits_fixtures.DORMANT_STATES[key][0] for key in measured_rows},
        "nonzero_rows": measured_rows,
        "departures": ledger.departures,
    }
    expected = {
        key: {c: sorted(rows) for c, rows in cols.items()} for key, cols in structure.items()
    }
    return ledger.ok, value, expected


# ------------------------------------------------------------------------------ A07–A14

#: Spec §14's unit-case tolerances by quantity (`ref.constants.tolerances`; `β` is ADR 0001 D6's
#: composition tolerance, which the YAML's per-kind table does not carry).
UNIT_TOLERANCES = {
    "temperature": support.TEMPERATURE_TOLERANCE,
    "flow": support.FLOW_TOLERANCE,
    "energy": support.ENERGY_TOLERANCE,
    "pressure": support.PRESSURE_TOLERANCE,
    "beta": support.BETA_TOLERANCE,
}


class _UnitCases:
    """One model's registered unit cases judged as its test file judges them: status, code
    (first line), signature and route exact; `T`, flows, `β`, duty, work and extent to §14; a
    registered zero flow `== 0.0`. Each quantity's error is kept as a ratio to its tolerance so
    the value can report the worst one."""

    def __init__(self) -> None:
        self.ledger = Ledger()
        self.ratios: dict[str, dict[str, float]] = {}
        self.cases: dict[str, str] = {}

    def run(self, case_id: str, measure: Callable[[], None]) -> None:
        before = len(self.ledger.departures)
        try:
            measure()
        except Exception as error:  # noqa: BLE001 - a case that raised did not pass
            self.ledger.departures.append(f"{case_id}: {type(error).__name__}: {error}")
        self.cases[case_id] = "pass" if len(self.ledger.departures) == before else "fail"

    def close(self, kind: str, where: str, value: float | None, registered: Any) -> None:
        tolerance = UNIT_TOLERANCES[kind]
        found = self.ledger.within(where, value, registered, tolerance)
        if math.isfinite(found):
            self.ratios.setdefault(kind, {})[where] = found / tolerance

    def flows(self, where: str, got: Any, registered: Any) -> None:
        if not self.ledger.true(
            f"{where}: {len(registered)} components", len(got) == len(registered)
        ):
            return
        for component, value, entry in zip(COMPONENTS, got, registered, strict=True):
            if Decimal(str(entry)) == 0:
                # §14's exact-zero row: a registered zero is exact, never "small".
                self.ledger.within(f"{where}.{component}", value, entry, 0.0)
            else:
                self.close("flow", f"{where}.{component}", value, entry)

    def stream(self, where: str, got: Any, registered: Mapping[str, Any], exact_p: bool) -> None:
        """An outlet's flows, `T` and `P`. The separator's and exchanger's tests compare `P`
        exactly (a copy); the others to §14's pressure tolerance."""
        self.flows(f"{where}.n", got.n, registered["n_mol_per_s"])
        self.close("temperature", f"{where}.T", got.temperature, registered["T_K"])
        if exact_p:
            self.ledger.within(f"{where}.P", got.pressure, registered["P_Pa"], 0.0)
        else:
            self.close("pressure", f"{where}.P", got.pressure, registered["P_Pa"])

    def outcome(self, case_id: str, result: Any, expected: Mapping[str, Any]) -> bool:
        """Status and code exact; a failure carries no answer. `True` when the case is `ok`."""
        self.ledger.equal(f"{case_id} status", result.status, expected["status"])
        self.ledger.equal(f"{case_id} code", support.first_line(result.message), expected["code"])
        if expected["status"] == "ok":
            return bool(result.status == "ok")
        carried = (
            dict(result.outlets),
            result.duty,
            result.work,
            result.extent,
            result.transferred_duty,
        )
        self.ledger.equal(
            f"{case_id} a failure carries no answer", carried, ({}, None, None, None, None)
        )
        return False

    def refusals(
        self, model_id: str, nominal: str, build: Callable[[Mapping[str, Any]], Any]
    ) -> None:
        """The registered construction refusals (`ref.specification_errors`): the nominal
        case's inputs with the registered change, refused with the registered code."""
        registered_errors = support.REF["specification_errors"]
        nominal_inputs = support.REF["unit_cases"][nominal]["inputs"]
        for case_id in support.specification_errors(model_id):
            registered = registered_errors[case_id]

            def refuse(registered: Mapping[str, Any] = registered, case_id: str = case_id) -> None:
                inputs = {**nominal_inputs, **registered["change_from_nominal"]}
                try:
                    build(inputs)
                except SpecificationError as refused:
                    code: str | None = support.first_line(str(refused))
                else:
                    code = None
                self.ledger.equal(f"{case_id} refusal code", code, registered["code"])

            self.run(case_id, refuse)

    def value(self) -> dict[str, Any]:
        return {
            "cases": self.cases,
            "count": len(self.cases),
            "failed": sorted(case for case, result in self.cases.items() if result != "pass"),
            "worst_error_over_tolerance": {
                kind: worst(ratios) for kind, ratios in sorted(self.ratios.items())
            },
            "departures": self.ledger.departures,
        }


def _registered(model_id: str) -> list[str]:
    return [*support.cases(model_id), *support.specification_errors(model_id)]


def _unit_expected(model_id: str, what: str) -> dict[str, Any]:
    return {
        "cases": dict.fromkeys(_registered(model_id), "pass"),
        "failed": [],
        "registration": f"ref.unit_cases and ref.specification_errors of {model_id}: {what}",
        "tolerances": "§14: T 1e-6 K, flows and extent 3.1e-8 mol/s, duty and work 1.01e-3 W, "
        "beta 1e-10, P 0.01 Pa (the separator's and exchanger's P exact); status, code, "
        "signature and route exact; a registered zero flow == 0.0",
        "departures": [],
    }


def _inlet(inputs: Mapping[str, Any]) -> dict[str, list[Any]]:
    return {"inlet": [support.stream(inputs["inlet"])]}


def _phf_case(judge: _UnitCases, case_id: str) -> None:
    inputs, expected = (support.REF["unit_cases"][case_id][key] for key in ("inputs", "expected"))
    result, closure = ph_flash_fixtures.unit_for(inputs).evaluate_with_closure(
        _inlet(inputs), support.CONTEXT
    )
    if not judge.outcome(case_id, result, expected):
        return
    judge.ledger.equal(f"{case_id} signature", result.phase_signature, expected["signature"])
    # A dormant case registers no route: the kernel is never reached (spec §4.7).
    judge.ledger.equal(
        f"{case_id} route", None if closure is None else closure.route, expected.get("route")
    )
    judge.close("energy", f"{case_id} duty", result.duty, expected["duty_W"])
    for port in ("vapor", "liquid"):
        judge.stream(f"{case_id} {port}", result.outlets[port], expected[port], exact_p=False)
    if "T_K" in expected:
        temperature = None if closure is None else closure.temperature
        judge.close("temperature", f"{case_id} T", temperature, expected["T_K"])
    if "beta" in expected:
        split = None if closure is None else closure.split
        beta = None if split is None else split.vapor_fraction
        judge.close("beta", f"{case_id} beta", beta, expected["beta"])


def _a07(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.models.syn001.ph_flash import MODEL_ID

    judge = _UnitCases()
    for case_id in support.cases(MODEL_ID):
        judge.run(case_id, lambda case_id=case_id: _phf_case(judge, case_id))
    judge.refusals(MODEL_ID, "PHF-1", ph_flash_fixtures.unit_for)
    value = judge.value()
    expected = _unit_expected(MODEL_ID, "PHF-1…7, Z0, Z1, F1…F4, S1")
    return judge.ledger.ok and value["count"] == 14, value, expected


def _vlv_case(judge: _UnitCases, case_id: str) -> None:
    inputs, expected = (support.REF["unit_cases"][case_id][key] for key in ("inputs", "expected"))
    result, closure = valve_fixtures.unit_for(inputs).evaluate_with_closure(
        _inlet(inputs), support.CONTEXT
    )
    if not judge.outcome(case_id, result, expected):
        return
    # No energy port: the valve reports no duty and no work at all, not zero ones.
    judge.ledger.equal(f"{case_id} (duty, work)", (result.duty, result.work), (None, None))
    judge.ledger.equal(f"{case_id} signature", result.phase_signature, expected["signature"])
    registered = expected["outlet"]
    judge.stream(f"{case_id} outlet", result.outlets["outlet"], registered, exact_p=False)
    if expected["signature"] == "ZERO_FLOW":
        judge.ledger.equal(f"{case_id} kernel reached", closure is not None, False)
        return
    split = None if closure is None else closure.split
    if not judge.ledger.true(f"{case_id} a lifted split", split is not None):
        return
    assert split is not None
    judge.ledger.equal(f"{case_id} regime", split.phase_signature, registered["regime"])
    judge.flows(f"{case_id} vapour", split.vapor.n, registered["vapor_n_mol_per_s"])
    judge.flows(f"{case_id} liquid", split.liquid.n, registered["liquid_n_mol_per_s"])


def _a08(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.models.syn001.valve import MODEL_ID

    judge = _UnitCases()
    for case_id in support.cases(MODEL_ID):
        judge.run(case_id, lambda case_id=case_id: _vlv_case(judge, case_id))
    judge.refusals(MODEL_ID, "VLV-1", valve_fixtures.unit_for)
    value = judge.value()
    expected = _unit_expected(MODEL_ID, "VLV-1…5, Z, F1, S1; no duty or work (no energy port)")
    return judge.ledger.ok and value["count"] == 8, value, expected


def _pump_case(judge: _UnitCases, case_id: str) -> None:
    inputs, expected = (support.REF["unit_cases"][case_id][key] for key in ("inputs", "expected"))
    result = pump_fixtures.unit_for(inputs).evaluate(_inlet(inputs), support.CONTEXT)
    if not judge.outcome(case_id, result, expected):
        return
    judge.ledger.equal(f"{case_id} duty (no heat port)", result.duty, None)
    judge.ledger.equal(f"{case_id} signature", result.phase_signature, expected["signature"])
    judge.close("energy", f"{case_id} work", result.work, expected["work_W"])
    if "work_ideal_W" in expected and result.work is not None:
        ideal = result.work * float(inputs["efficiency"])
        judge.close("energy", f"{case_id} ideal work", ideal, expected["work_ideal_W"])
    judge.stream(f"{case_id} outlet", result.outlets["outlet"], expected["outlet"], exact_p=False)


def _a09(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.models.syn001.pump import MODEL_ID

    judge = _UnitCases()
    for case_id in support.cases(MODEL_ID):
        judge.run(case_id, lambda case_id=case_id: _pump_case(judge, case_id))
    judge.refusals(MODEL_ID, "PUMP-1", pump_fixtures.unit_for)
    value = judge.value()
    expected = _unit_expected(
        MODEL_ID, "PUMP-1…4, F1…F3, Z, S1, S2; `W` reported (and η W the ideal work)"
    )
    return judge.ledger.ok and value["count"] == 10, value, expected


def _rx_case(judge: _UnitCases, case_id: str, old_form: dict[str, bool]) -> None:
    inputs, expected = (support.REF["unit_cases"][case_id][key] for key in ("inputs", "expected"))
    feed = _inlet(inputs)
    result, split = reactor_fixtures.unit_for(inputs).evaluate_with_split(feed, support.CONTEXT)
    if not judge.outcome(case_id, result, expected):
        # RX-F1 registers the extent the twin computed (0.6) as a diagnostic; the output is
        # `None` (spec §6.4 as amended, ruling round U3 (5)), which `outcome` asserts.
        judge.ledger.equal(f"{case_id} split", split, None)
        return
    judge.ledger.equal(f"{case_id} signature", result.phase_signature, expected["signature"])
    judge.ledger.equal(
        f"{case_id} (work, transferred duty)", (result.work, result.transferred_duty), (None, None)
    )
    judge.close("energy", f"{case_id} duty", result.duty, expected["duty_W"])
    judge.close("flow", f"{case_id} extent", result.extent, expected["extent_mol_per_s"])
    registered = expected["outlet"]
    outlet = result.outlets["outlet"]
    judge.stream(f"{case_id} outlet", outlet, registered, exact_p=False)
    # §6.3 as amended (R-051): the key's outlet is `n_in − X·n_in`; the registered cases have
    # |ν_k| ∈ {1, 2}, where the old form `n_in + ν_k ξ` is bitwise the same. Measured here on
    # the answer: the old form recomputed from the reported ξ, compared bit for bit.
    key = COMPONENTS.index(inputs["key"])
    if result.extent is not None:
        old = feed["inlet"][0].n[key] + float(inputs["nu"][key]) * result.extent
        old_form[case_id] = old == outlet.n[key]
    if expected["signature"] == "ZERO_FLOW":
        judge.ledger.equal(f"{case_id} split computed", split is not None, False)
        return
    if not judge.ledger.true(f"{case_id} a split", split is not None):
        return
    assert split is not None
    judge.ledger.equal(f"{case_id} regime", split.phase_signature, registered["regime"])
    judge.flows(f"{case_id} vapour", split.vapor.n, registered["vapor_n_mol_per_s"])
    judge.flows(f"{case_id} liquid", split.liquid.n, registered["liquid_n_mol_per_s"])


def _full_conversion(judge: _UnitCases) -> dict[str, Any]:
    """Ruling Q-R7's acceptance (review S2): the P2 input, and the deterministic 1 000-feed sweep
    of `test_t05_reactor` (`SWEEP`) at `X ∈ {1, 0.25, 0.5, 0.75}` for `ν_A ∈ {−3, −5, −7}`."""
    p2 = reactor_fixtures.full_conversion_reactor((-3.0, 1.0, 2.0), 1.0).evaluate(
        reactor_fixtures.vapour_feed(1.7383439417747188), support.CONTEXT
    )
    p2_value = {
        "status": p2.status,
        "n_out_A": p2.outlets["outlet"].n[0] if p2.status == "ok" else None,
    }
    judge.ledger.equal("Q-R7 P2", p2_value, {"status": "ok", "n_out_A": 0.0})
    sweep: dict[str, Any] = {}
    for nu in ((-3.0, 1.0, 2.0), (-5.0, 2.0, 3.0), (-7.0, 3.0, 4.0)):
        for conversion in (1.0, 0.25, 0.5, 0.75):
            unit = reactor_fixtures.full_conversion_reactor(nu, conversion)
            refused: list[str] = []
            nonzero_key = 0
            worst_row = 0.0
            for n_a in reactor_fixtures.SWEEP:
                result = unit.evaluate(reactor_fixtures.vapour_feed(n_a), support.CONTEXT)
                if result.status != "ok" or result.extent is None:
                    refused.append(support.first_line(result.message))
                    continue
                n_out = result.outlets["outlet"].n[0]
                nonzero_key += conversion == 1.0 and n_out != 0.0
                produced = nu[0] * result.extent
                scale = max(abs(n_a), abs(produced), abs(n_out))
                worst_row = max(worst_row, abs(n_a + produced - n_out) / scale)
            label = f"nu_A={nu[0]:g} X={conversion:g}"
            sweep[label] = {
                "feeds": len(reactor_fixtures.SWEEP),
                "refused": len(refused),
                "refusal_codes": sorted(set(refused)),
                "key_outlet_not_exactly_zero": nonzero_key if conversion == 1.0 else None,
                "worst_rx_mole_A_over_term_scale": worst_row,
            }
            judge.ledger.equal(f"Q-R7 sweep {label} refused", len(refused), 0)
            judge.ledger.equal(f"Q-R7 sweep {label} key outlet != 0", nonzero_key, 0)
            judge.ledger.true(f"Q-R7 sweep {label} RX-mole:A ≤ 1e-12", worst_row <= 1e-12)
    return {"p2": p2_value, "sweep": sweep}


def _a10(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.models.syn001.conversion_reactor import MODEL_ID

    judge = _UnitCases()
    old_form: dict[str, bool] = {}
    for case_id in support.cases(MODEL_ID):
        judge.run(case_id, lambda case_id=case_id: _rx_case(judge, case_id, old_form))
    # RX-S4's provider is `test_t05_reactor.ConventionDouble` (convention `SYN-001-ref-v0`),
    # which the tests' `unit_for` builds from the registered change.
    judge.refusals(MODEL_ID, "RX-1", reactor_fixtures.unit_for)
    judge.ledger.equal(
        "the key outlet by the old form, bitwise",
        sorted(case for case, same in old_form.items() if not same),
        [],
    )
    full = _full_conversion(judge)
    value = {
        **judge.value(),
        "key_outlet_equals_old_form_bitwise": old_form,
        "full_conversion_q_r7": full,
    }
    expected = {
        **_unit_expected(
            MODEL_ID,
            "RX-1…8, Z, F1, F5, S1…S5; ξ reported on ok cases, RX-F1's extent None, RX-S4 "
            "through a provider test double declaring SYN-001-ref-v0",
        ),
        "key_outlet_equals_old_form_bitwise": "every ok case (|ν_k| ∈ {1, 2})",
        "full_conversion_q_r7": "P2 ok with n_out,A == 0.0; the 1 000-feed sweep: nothing "
        "refused, n_out,A == 0.0 at X = 1, RX-mole:A within 1e-12 of its term scale",
    }
    return judge.ledger.ok and len(judge.cases) == 16, value, expected


def _sep_case(judge: _UnitCases, case_id: str) -> None:
    inputs, expected = (support.REF["unit_cases"][case_id][key] for key in ("inputs", "expected"))
    result = separator_fixtures.separator(inputs).evaluate(_inlet(inputs), support.CONTEXT)
    if not judge.outcome(case_id, result, expected):
        return
    judge.ledger.equal(f"{case_id} signature", result.phase_signature, expected["signature"])
    judge.ledger.equal(
        f"{case_id} (work, extent, transferred duty)",
        (result.work, result.extent, result.transferred_duty),
        (None, None, None),
    )
    judge.close("energy", f"{case_id} duty", result.duty, expected["duty_W"])
    for port in ("top", "bottom"):
        judge.stream(f"{case_id} {port}", result.outlets[port], expected[port], exact_p=True)


def _a11(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.models.syn001.component_separator import MODEL_ID

    judge = _UnitCases()
    for case_id in support.cases(MODEL_ID):
        judge.run(case_id, lambda case_id=case_id: _sep_case(judge, case_id))
    judge.refusals(MODEL_ID, "SEP-1", separator_fixtures.separator)
    value = judge.value()
    expected = _unit_expected(MODEL_ID, "SEP-1…4, Z, F2, S1")
    return judge.ledger.ok and value["count"] == 7, value, expected


def _hx_case(judge: _UnitCases, case_id: str, failures: dict[str, Any]) -> None:
    inputs, expected = (support.REF["unit_cases"][case_id][key] for key in ("inputs", "expected"))
    unit = exchanger_fixtures.exchanger(inputs)
    feed = exchanger_fixtures.inlets(inputs)
    result = unit.evaluate(feed, support.CONTEXT)
    # No energy port: the unit has no duty at all, which is not a zero duty.
    judge.ledger.equal(f"{case_id} duty (no energy port)", result.duty, None)
    # A12: `assess` runs §10.2's checks (5)–(8) all; the list is exactly the registered one, so a
    # failure case fails its registered check and passes every other, and an ok case fails none.
    assessment = unit.assess(feed, support.CONTEXT)
    registered = expected.get("failures", [expected["code"]] if expected["code"] else [])
    failures[case_id] = {"assessed": list(assessment.failures), "registered": registered}
    judge.ledger.equal(f"{case_id} assessed failures", list(assessment.failures), registered)
    if "duty_W" in expected:
        judge.close(
            "energy", f"{case_id} assessed duty", assessment.transferred_duty, expected["duty_W"]
        )
    for key, found in (("hot_end_K", assessment.hot_end), ("cold_end_K", assessment.cold_end)):
        if key in expected:
            judge.close("temperature", f"{case_id} {key}", found, expected[key])
    for port in ("hot_outlet", "cold_outlet"):
        if port in expected and expected["status"] != "ok":
            got = assessment.hot_outlet if port == "hot_outlet" else assessment.cold_outlet
            if judge.ledger.true(f"{case_id} assessed {port}", got is not None):
                judge.stream(f"{case_id} assessed {port}", got, expected[port], exact_p=True)
    if not judge.outcome(case_id, result, expected):
        return
    judge.ledger.equal(f"{case_id} signature", result.phase_signature, expected["signature"])
    judge.ledger.equal(f"{case_id} (work, extent)", (result.work, result.extent), (None, None))
    judge.close("energy", f"{case_id} duty", result.transferred_duty, expected["duty_W"])
    for port in ("hot_outlet", "cold_outlet"):
        judge.stream(f"{case_id} {port}", result.outlets[port], expected[port], exact_p=True)


def _a12(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.models.syn001.heat_exchanger import MODEL_ID

    judge = _UnitCases()
    failures: dict[str, Any] = {}
    for case_id in support.cases(MODEL_ID):
        judge.run(case_id, lambda case_id=case_id: _hx_case(judge, case_id, failures))
    judge.refusals(MODEL_ID, "HX-1", exchanger_fixtures.exchanger)
    value = {**judge.value(), "failure_lists": failures}
    expected = {
        **_unit_expected(
            MODEL_ID,
            "HX-1…5, Z0, Z1, F1…F4, S1; the transferred duty reported (no energy port)",
        ),
        "failure_lists": "each case's assessed list equals ref…expected.failures (F1…F4: "
        "their one registered check), or its code, or empty",
    }
    return judge.ledger.ok and value["count"] == 12, value, expected


def _a13(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    cases = ref["unit_cases"]
    temperature, flow, energy = (
        support.TEMPERATURE_TOLERANCE,
        support.FLOW_TOLERANCE,
        support.ENERGY_TOLERANCE,
    )

    def split_difference(ours: Any, theirs: Any) -> float:
        return max(abs(got - want) for got, want in zip(ours.n, theirs.n, strict=True))

    # PHF-2: PH of TP is the identity at 360 K, against K02's TP flash on the same stream.
    phf2 = cases["PHF-2"]["inputs"]
    feed = support.stream(phf2["inlet"])
    flashed = ph_flash_fixtures.unit_for(phf2).evaluate({"inlet": [feed]}, support.CONTEXT)
    k02 = TPFlash(
        unit_id="U-FLASH",
        provider=support.PROVIDER,
        temperature=360.0,
        pressure=feed.pressure,
        context=support.CONTEXT,
        inlet_phase="LIQUID",
    ).evaluate({"inlet": [feed]}, support.CONTEXT)
    ledger.equal("PHF-2 and K02 status", (flashed.status, k02.status), ("ok", "ok"))
    assert k02.duty is not None
    phf2_value = {
        "T_minus_360_K": max(abs(o.temperature - 360.0) for o in flashed.outlets.values()),
        "split_minus_k02_mol_per_s": max(
            split_difference(flashed.outlets[port], k02.outlets[port])
            for port in ("vapor", "liquid")
        ),
        "k02_duty_minus_registered_duty_W": abs(k02.duty - float(phf2["duty"])),
    }
    ledger.true("PHF-2 T", phf2_value["T_minus_360_K"] <= temperature)
    ledger.true("PHF-2 split", phf2_value["split_minus_k02_mol_per_s"] <= flow)
    ledger.true("PHF-2 duty loop", phf2_value["k02_duty_minus_registered_duty_W"] <= energy)

    # PHF-7 (Q = 0 across a drop) and VLV-2 (to 1e5 Pa) are the same PH problem.
    phf7, vlv2 = cases["PHF-7"]["inputs"], cases["VLV-2"]["inputs"]
    ledger.equal("PHF-7 and VLV-2 inlets", phf7["inlet"], vlv2["inlet"])
    across, flash_closure = PHFlash(
        unit_id="U-PHF",
        provider=support.PROVIDER,
        duty=float(phf7["duty"]),
        context=support.CONTEXT,
        pressure_drop=float(phf7["pressure_drop"]),
        inlet_phase=phf7["inlet_phase"],
    ).evaluate_with_closure(_inlet(phf7), support.CONTEXT)
    throttled, valve_closure = valve_fixtures.unit_for(vlv2).evaluate_with_closure(
        _inlet(vlv2), support.CONTEXT
    )
    ledger.equal("PHF-7 and VLV-2 status", (across.status, throttled.status), ("ok", "ok"))
    assert flash_closure is not None and valve_closure is not None
    assert flash_closure.split is not None and valve_closure.split is not None
    assert flash_closure.temperature is not None and valve_closure.temperature is not None
    valve_value = {
        "T_difference_K": abs(flash_closure.temperature - valve_closure.temperature),
        "split_difference_mol_per_s": max(
            split_difference(getattr(flash_closure.split, port), getattr(valve_closure.split, port))
            for port in ("vapor", "liquid")
        ),
        "signatures": [across.phase_signature, throttled.phase_signature],
        "pressures": [across.outlets["vapor"].pressure, throttled.outlets["outlet"].pressure],
    }
    ledger.true("PHF-7/VLV-2 T", valve_value["T_difference_K"] <= temperature)
    ledger.true("PHF-7/VLV-2 split", valve_value["split_difference_mol_per_s"] <= flow)
    ledger.true("PHF-7/VLV-2 signature", across.phase_signature == throttled.phase_signature)
    ledger.true("PHF-7/VLV-2 pressure", len(set(valve_value["pressures"])) == 1)

    # RX-7 (X = 0) is K02's TPHeater on the same stream.
    rx7 = cases["RX-7"]["inputs"]
    reacted = reactor_fixtures.unit_for(rx7).evaluate(_inlet(rx7), support.CONTEXT)
    heated = TPHeater(
        unit_id="U-HEAT",
        provider=support.PROVIDER,
        outlet_temperature=float(rx7["value"]),
        context=support.CONTEXT,
        inlet_phase=rx7["inlet_phase"],
        pressure_drop=float(rx7["pressure_drop"]),
    ).evaluate(_inlet(rx7), support.CONTEXT)
    ledger.equal("RX-7 and TPHeater status", (reacted.status, heated.status), ("ok", "ok"))
    assert reacted.duty is not None and heated.duty is not None
    heater_value = {
        "duty_difference_W": abs(reacted.duty - heated.duty),
        "signatures": [reacted.phase_signature, heated.phase_signature],
        "outlets_equal": reacted.outlets["outlet"] == heated.outlets["outlet"],
    }
    ledger.true("RX-7 duty", heater_value["duty_difference_W"] <= energy)
    ledger.true("RX-7 signature", reacted.phase_signature == heated.phase_signature)
    ledger.true("RX-7 outlet", heater_value["outlets_equal"])

    # HX-1, HX-2 and HX-3 fix one exchanger by the three specification modes.
    results = {case_id: exchanger_fixtures.run(case_id) for case_id in ("HX-1", "HX-2", "HX-3")}
    ledger.equal("HX-1…3 status", [r.status for r in results.values()], ["ok"] * 3)
    reference_run = results["HX-1"]
    assert reference_run.transferred_duty is not None
    exchanger_value: dict[str, Any] = {}
    for case_id in ("HX-2", "HX-3"):
        other = results[case_id]
        assert other.transferred_duty is not None
        exchanger_value[case_id] = {
            "duty_difference_W": abs(other.transferred_duty - reference_run.transferred_duty),
            "T_difference_K": max(
                abs(other.outlets[port].temperature - reference_run.outlets[port].temperature)
                for port in ("hot_outlet", "cold_outlet")
            ),
            "flows_and_pressures_equal": all(
                (other.outlets[port].n, other.outlets[port].pressure)
                == (reference_run.outlets[port].n, reference_run.outlets[port].pressure)
                for port in ("hot_outlet", "cold_outlet")
            ),
        }
        entry = exchanger_value[case_id]
        ledger.true(f"{case_id} vs HX-1 duty", entry["duty_difference_W"] <= energy)
        ledger.true(f"{case_id} vs HX-1 T", entry["T_difference_K"] <= temperature)
        ledger.true(f"{case_id} vs HX-1 flows and P", entry["flows_and_pressures_equal"])

    value = {
        "PHF-2_vs_K02_TP_flash_360K": phf2_value,
        "PHF-7_vs_VLV-2": valve_value,
        "RX-7_vs_K02_TPHeater": heater_value,
        "HX-2_HX-3_vs_HX-1": exchanger_value,
        "departures": ledger.departures,
    }
    expected = {
        "PHF-2_vs_K02_TP_flash_360K": "T within 1e-6 K of 360 K; split within 3.1e-8 mol/s of "
        "K02's TP flash at 360 K; K02's duty the registered one to 1.01e-3 W",
        "PHF-7_vs_VLV-2": "T within 1e-6 K, split within 3.1e-8 mol/s, one signature, one P",
        "RX-7_vs_K02_TPHeater": "duty within 1.01e-3 W, one signature, the same outlet",
        "HX-2_HX-3_vs_HX-1": "duty within 1.01e-3 W, T within 1e-6 K, flows and P equal",
    }
    return ledger.ok, value, expected


#: Spec §14's exact-zero row: (case, where, index of the component) — RX-6, RX-8 `n_A`; PHF-5
#: `n_B` in both products; SEP-2 `n_top,C`. The dormant outlets of SEP-3/4 and of every dormant
#: case are judged whole below.
_EXACT_ZEROS = (
    ("RX-6", "outlet", 0),
    ("RX-8", "outlet", 0),
    ("PHF-5", "vapor", 1),
    ("PHF-5", "liquid", 1),
    ("SEP-2", "top", 2),
)
#: The dormant cases: each is `ok` with a zero-flow side, or its registered typed error.
_DORMANT = ("PHF-Z0", "PHF-Z1", "VLV-Z", "PUMP-Z", "RX-Z", "SEP-Z", "HX-Z0", "HX-Z1")


def _evaluate_case(case_id: str) -> Any:
    """A registered unit case through its test module's builder."""
    case = support.REF["unit_cases"][case_id]
    inputs, model = case["inputs"], case["model"]
    if model == "syn001.heat_exchanger":
        return exchanger_fixtures.run(case_id)
    build: Callable[[Mapping[str, Any]], Any] = {
        "syn001.ph_flash": ph_flash_fixtures.unit_for,
        "syn001.valve": valve_fixtures.unit_for,
        "syn001.liquid_pump": pump_fixtures.unit_for,
        "syn001.conversion_reactor": reactor_fixtures.unit_for,
        "syn001.component_separator": separator_fixtures.separator,
    }[model]
    return build(inputs).evaluate(_inlet(inputs), support.CONTEXT)


def _a14(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    ledger = Ledger()
    zeros: dict[str, Any] = {}
    for case_id, port, index in _EXACT_ZEROS:
        result = _evaluate_case(case_id)
        found = result.outlets[port].n[index] if result.status == "ok" else None
        where = f"{case_id} {port}.n.{COMPONENTS[index]}"
        zeros[where] = found
        ledger.equal(where, found, 0.0)
        ledger.equal(
            f"{where} registered",
            Decimal(ref["unit_cases"][case_id]["expected"][port]["n_mol_per_s"][index]),
            Decimal(0),
        )

    phf6 = ref["unit_cases"]["PHF-6"]["inputs"]
    _, closure = ph_flash_fixtures.unit_for(phf6).evaluate_with_closure(
        _inlet(phf6), support.CONTEXT
    )
    route = None if closure is None else closure.route
    ledger.equal("PHF-6 route", route, "saturation")

    dormant: dict[str, Any] = {}
    for case_id in (*_DORMANT, "SEP-3", "SEP-4"):
        expected = ref["unit_cases"][case_id]["expected"]
        result = _evaluate_case(case_id)
        entry: dict[str, Any] = {
            "status": result.status,
            "code": support.first_line(result.message),
            "signature": result.phase_signature,
        }
        ledger.equal(
            f"{case_id} (status, code)",
            (entry["status"], entry["code"]),
            (expected["status"], expected["code"]),
        )
        if expected["status"] == "ok":
            # Exactly zero duty, work, extent and transferred heat where the model reports one.
            energies = {
                name: getattr(result, name)
                for name in ("duty", "work", "extent", "transferred_duty")
                if getattr(result, name) is not None
            }
            entry["energies"] = energies
            ledger.equal(f"{case_id} energies", energies, dict.fromkeys(energies, 0.0))
            labels: dict[str, Any] = {}
            for port, outlet in result.outlets.items():
                registered = expected[port]
                if all(Decimal(str(v)) == 0 for v in registered["n_mol_per_s"]):
                    labels[port] = {"n": list(outlet.n), "T_K": outlet.temperature}
                    ledger.equal(f"{case_id} {port} flows", outlet.n, (0.0, 0.0, 0.0))
                    # The label: the registered temperature, exactly.
                    ledger.equal(
                        f"{case_id} {port} label", outlet.temperature, float(registered["T_K"])
                    )
            entry["zero_flow_outlets"] = labels
            ledger.true(f"{case_id} has a zero-flow outlet", bool(labels))
        dormant[case_id] = entry

    value = {
        "exact_zeros": zeros,
        "phf6_route": route,
        "dormant": dormant,
        "departures": ledger.departures,
    }
    expected_value = {
        "exact_zeros": dict.fromkeys(zeros, 0.0),
        "phf6_route": "saturation",
        "dormant": "PHF-Z0, VLV-Z, PUMP-Z, RX-Z, SEP-Z, HX-Z0 (and SEP-3/4's dormant outlet): ok, "
        "every zero-flow outlet (0.0, 0.0, 0.0) at its registered label exactly, duty, work, "
        "extent and transferred heat == 0.0; PHF-Z1 duty_into_dormant_stream, HX-Z1 "
        "specification_unsatisfiable_with_dormant_side",
    }
    return ledger.ok, value, expected_value


# ------------------------------------------------------------------------------ A17–A19


def _coupled(runs: Runs, ref: Mapping[str, Any], case: str) -> tuple[bool, Any, Any]:
    """One coupled case on the common path against `ref.coupled_cases.<case>`: the outcome, one
    `solve_eo` step and one attempt from `traversal-G0-v1`; both directions of the column mapping
    (`test_t05_coupled.reference_columns`); the worst `|x − x_ref|` per kind against §11.5's
    allowance; every unit's phase signature."""
    from openflowsheet.orchestrator.revision import INITIALIZER_ID

    ledger = Ledger()
    solved = runs.solved(case)
    run = solved.run
    ledger.equal("outcome", run.outcome, "CONVERGED")
    ledger.equal("plan steps", [step.kind for step in solved.plan.steps], ["solve_eo"])
    ledger.equal("step outcomes", [step.outcome for step in run.steps], ["CONVERGED"])
    region = solved.region
    ledger.equal("attempts", len(region.attempts), 1)
    ledger.equal("initializer", region.branch_provenance[0]["initializer_source"], INITIALIZER_ID)
    expected, primary = coupled_fixtures.reference_columns(case)
    columns = set(solved.binding.spec.variable_ids)
    unmapped = sorted(columns - set(expected))
    unchecked = sorted(primary - columns)
    ledger.equal("solver columns with no reference value", unmapped, [])
    ledger.equal("registered values with no solver column", unchecked, [])
    deviations = coupled_fixtures.deviations(solved, case)
    per_kind: dict[str, Any] = {}
    for kind, (error, column) in sorted(deviations.items()):
        allowance = coupled_fixtures.ALLOWANCE[kind]
        per_kind[kind] = {
            "worst_error": error,
            "column": column,
            "allowance": allowance,
            "ratio": error / allowance,
        }
        ledger.true(f"{kind} at {column}: {error:.3g} within {allowance:g}", error <= allowance)
    (signature,) = region.signatures
    registered = ref["coupled_cases"][case]["signatures"]
    ledger.equal("signature", dict(signature), registered)
    value = {
        "outcome": run.outcome,
        "iterations": region.iterations,
        "attempts": len(region.attempts),
        "columns_compared": len(columns),
        "deviation_by_kind": per_kind,
        "signature": dict(signature),
        "departures": ledger.departures,
    }
    expected_value = {
        "outcome": "CONVERGED, one solve_eo step, one attempt from traversal-G0-v1",
        "deviation_by_kind": {
            kind: f"worst error at most {allowance:g}"
            for kind, allowance in coupled_fixtures.ALLOWANCE.items()
        },
        "signature": registered,
        "mapping": "every solver column registered and every registered value a column",
    }
    return ledger.ok, value, expected_value


def _a17(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    return _coupled(runs, ref, "SYN-001-UL-C1")


def _a18(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    return _coupled(runs, ref, "SYN-001-UL-C2")


def _a19(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    condition, value, expected = _coupled(runs, ref, "SYN-001-UL-C3")
    phf = value["signature"].get("U-PHF")
    value["u_phf_regime"] = phf
    expected["u_phf_regime"] = "TWO_PHASE"
    return condition and phf == "TWO_PHASE", value, expected


# ----------------------------------------------------------------------------------- A20

#: Spec A20 / §11.4: the one failing check of the second branch and its value, K.
C3X_FAILING = ["bounds_and_domain.U-HX.cold_end"]
C3X_COLD_END_K, C3X_ALLOWANCE_K = 10.0, 1e-5


def _a20(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """Both of A20's branches measured: the path the traversal takes (the first), and the second
    exercised from the twin's state as W12 does (`test_t05_w12_table._twin_certificate`), its
    certificate judged at the solve's own final state and at the twin's."""
    from openflowsheet.orchestrator.revision import InitialStateFailure, initial_state

    ledger = Ledger()
    solved = runs.solved(C3X)
    steps = [(step.outcome, step.message) for step in solved.run.steps]
    failure = initial_state(solved.binding.flowsheet, solved.binding.spec.variable_ids)
    refusal = [failure.unit, failure.code] if isinstance(failure, InitialStateFailure) else None
    first = {
        "outcome": solved.run.outcome,
        "steps": [list(step) for step in steps],
        "initial_state_refusal": refusal,
    }
    code = "initializer_failed(U-HX): temperature_cross(cold_end)"
    ledger.equal("first branch: steps", steps, [("INITIALIZATION_FAILED", code)])
    ledger.equal("first branch: initial_state", refusal, ["U-HX", "temperature_cross(cold_end)"])
    second: dict[str, Any] = {}
    for label, at_twin in (("solved_state", False), ("twin_state", True)):
        certificate = table_fixtures._twin_certificate(C3X, at_twin=at_twin)
        failing = [check for check in certificate.checks if check.result == "fail"]
        others = [c.id for c in certificate.checks if c.result not in ("pass", "fail")]
        cold_end = failing[0].value if len(failing) == 1 else None
        second[label] = {
            "verification_status": certificate.verification_status,
            "false_success_detected": certificate.false_success_detected,
            "failing_checks": [check.id for check in failing],
            "cold_end_K": cold_end,
            "cold_end_error_K": None if cold_end is None else abs(cold_end - C3X_COLD_END_K),
            "neither_pass_nor_fail": others,
        }
        ledger.equal(f"{label}: status", certificate.verification_status, "FAILED")
        ledger.equal(f"{label}: failing set", [c.id for c in failing], C3X_FAILING)
        ledger.true(
            f"{label}: cold end {cold_end!r} within {C3X_ALLOWANCE_K:g} K of +10 K",
            cold_end is not None and abs(cold_end - C3X_COLD_END_K) <= C3X_ALLOWANCE_K,
        )
    value = {
        "first_branch": first,
        "second_branch": second,
        "verified_anywhere": any(
            entry["verification_status"] == "VERIFIED" for entry in second.values()
        ),
        "departures": ledger.departures,
    }
    expected = {
        "first_branch": {"steps": [["INITIALIZATION_FAILED", code]]},
        "second_branch": {
            "verification_status": "FAILED",
            "failing_checks": C3X_FAILING,
            "cold_end_K": f"+10 within {C3X_ALLOWANCE_K:g}",
        },
        "verified_anywhere": False,
    }
    return ledger.ok and not value["verified_anywhere"], value, expected


# ----------------------------------------------------------------------------------- A21

#: Spec §11.5 as amended (ruling round Q-R6): the solution-error bound on the exact norm.
SOLUTION_ERROR_BOUND = 1e-8


def _a21(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.thermo.syn001 import Syn001Provider
    from openflowsheet.verify.certificate import BoundDeclaration
    from openflowsheet.verify.checks import qualification
    from openflowsheet.verify.regularity import target_jacobian
    from openflowsheet.verify.table import REACTION_DATUM_NOTE

    ledger = Ledger()
    provider = Syn001Provider()
    note = qualification(provider)
    reaction = note + REACTION_DATUM_NOTE.format(
        convention=provider.describe().reference_convention
    )
    per_case: dict[str, Any] = {}
    for case in COUPLED:
        solved, certificate = runs.solved(case), runs.certificate(case)
        checks = certificate.checks
        ids = [c.id for c in checks]
        table = [i for i in ids if not i.startswith(table_fixtures._GENERIC)]
        (step,) = solved.plan.steps
        aliases = [
            f"alias_certificate.{kind}.{row.row_id}"
            for row in step.solve_plan.eliminated_rows
            for kind in ("identity", "satisfied")
        ]
        (two, two_at), (one, one_at) = table_fixtures.worst_ratios(certificate)
        # [A09] on every energy, admissibility and independent-split check and on nothing else;
        # ADR 0011 D2's note on the reactor's energy balance and the envelope's with a reactor.
        misqualified = []
        for c in checks:
            shares = c.category in ("energy_balance", "phase_admissibility", "independent_split")
            if (c.independence_qualification is not None) != shares:
                misqualified.append(c.id)
            elif c.category == "energy_balance":
                carries = case == "SYN-001-UL-C2" and c.id in (
                    "energy_balance.U-RX",
                    "energy_balance.envelope",
                )
                if c.independence_qualification != (reaction if carries else note):
                    misqualified.append(c.id)
        # The exact ‖Ĵ⁻¹‖₁ (dense inverse) times the recorded ‖F̂‖∞, at the final state.
        state = solved.run.state
        target = BoundDeclaration(solved.binding.spec, compile_problem(solved.binding.spec), state)
        matrix, scaled_residual, _ = target_jacobian(target, state)
        exact = float(np.linalg.norm(np.linalg.inv(matrix.toarray()), 1))
        residual = float(np.max(np.abs(scaled_residual)))
        recorded = certificate.solution_error_bound_scaled
        per_case[case] = {
            "verification_status": certificate.verification_status,
            "limitations": [limitation.kind for limitation in certificate.limitations],
            "false_success_detected": certificate.false_success_detected,
            "checks": len(checks),
            "not_pass": [[c.id, c.result] for c in checks if c.result != "pass"],
            "near_threshold": [c.id for c in checks if c.near_threshold],
            "table_ids_equal_spec_12_2": table == table_fixtures.TABLE_IDS[case],
            "table_ids": len(table),
            "missing_from_table": [i for i in table_fixtures.TABLE_IDS[case] if i not in table],
            "residual_ids_equal_rows": [i for i in ids if i.startswith("residual.")]
            == [f"residual.{row}" for row in solved.binding.spec.equation_ids],
            "alias_ids_equal_plan": [i for i in ids if i.startswith("alias_certificate.")]
            == aliases,
            "derivative_witness_ids": [i for i in ids if i.startswith("derivative_witness.")],
            "energy_balance_U-SPLIT": "energy_balance.U-SPLIT" in ids,
            "worst_two_sided_ratio": {"ratio": two, "check": two_at},
            "worst_one_sided_ratio": {"ratio": one, "check": one_at},
            "misqualified": misqualified,
            "bound": {
                "n": matrix.shape[0],
                "residual_inf_scaled": residual,
                "inverse_one_norm_exact": exact,
                "inverse_one_norm_estimate": None if not residual else (recorded or 0.0) / residual,
                "bound_exact": exact * residual,
                "bound_recorded": recorded,
                "margin_to_1e-8": SOLUTION_ERROR_BOUND / (exact * residual)
                if exact * residual
                else math.inf,
            },
        }
        entry = per_case[case]
        ledger.equal(f"{case}: status", entry["verification_status"], "VERIFIED")
        ledger.equal(f"{case}: limitations", entry["limitations"], [])
        ledger.equal(f"{case}: false success", entry["false_success_detected"], False)
        ledger.equal(f"{case}: checks not pass", entry["not_pass"], [])
        ledger.equal(f"{case}: near threshold", entry["near_threshold"], [])
        ledger.equal(f"{case}: §12.2 ids in order", entry["table_ids_equal_spec_12_2"], True)
        ledger.equal(f"{case}: residual ids", entry["residual_ids_equal_rows"], True)
        ledger.equal(f"{case}: alias ids", entry["alias_ids_equal_plan"], True)
        ledger.equal(
            f"{case}: witness ids",
            entry["derivative_witness_ids"],
            ["derivative_witness.on_pattern", "derivative_witness.off_pattern"],
        )
        ledger.true(f"{case}: worst ratios below 1/10", two < 0.1 and one < 0.1)
        ledger.equal(f"{case}: qualification", misqualified, [])
        ledger.true(
            f"{case}: exact bound {exact * residual:.3g} at most 1e-8",
            exact * residual <= SOLUTION_ERROR_BOUND,
        )
        ledger.true(
            f"{case}: recorded bound {recorded!r} present and at most the exact one",
            recorded is not None and recorded <= exact * residual * (1.0 + 1e-10),
        )
    ledger.equal(
        "C3 carries energy_balance.U-SPLIT",
        per_case["SYN-001-UL-C3"]["energy_balance_U-SPLIT"],
        True,
    )
    value = {"cases": per_case, "departures": ledger.departures}
    expected = {
        "verification_status": "VERIFIED, no limitation, no false success",
        "checks": "every one pass, none near_threshold, worst ratios below 1/10",
        "ids": "§12.2's list for the case in §4.3's order (C3 with energy_balance.U-SPLIT), "
        "every residual row, the plan's aliases, the two witness checks",
        "qualification": "[A09] on energy, admissibility and independent-split checks only; "
        "ADR 0011 D2's note on C2's U-RX and envelope energy checks",
        "bound_exact": "at most 1e-8 (exact dense inverse times the recorded residual norm)",
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A22


def _judge_injection(
    document: dict[str, Any],
    binding: Any,
    result: Any,
    solve_plan: Any,
    state: Mapping[str, float],
    registered: Mapping[str, tuple[str, float]],
    passing: Sequence[str],
    ledger: Ledger,
    name: str,
    factor: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The injected state through `verify_revision`: status, detection, the failing set, each
    registered check's value against `ref` (§14's tolerance) with its margin over `10³ τ`, and
    every check under the "what passes" prefixes passing. Returns the record and the checks."""
    from openflowsheet.verify.certificate import verify_revision

    certificate = verify_revision(binding, document, result, state=state, solve_plan=solve_plan)
    by_id = {check.id: check for check in certificate.checks}
    failing = sorted(check.id for check in certificate.checks if check.result == "fail")
    checks: dict[str, Any] = {}
    for identifier, (expected, tolerance) in registered.items():
        check_result = by_id.get(identifier)
        measured_value = None if check_result is None else check_result.value
        found = ledger.within(f"{name} {identifier}", measured_value, expected, tolerance)
        margin = (
            abs(measured_value) / check_result.tolerance
            if check_result is not None and measured_value is not None and check_result.tolerance
            else None
        )
        checks[identifier] = {
            "result": None if check_result is None else check_result.result,
            "value": measured_value,
            "registered": expected,
            "error": found,
            "tolerance": tolerance,
            "value_over_tau": margin,
        }
        ledger.equal(f"{name} {identifier} result", checks[identifier]["result"], "fail")
        ledger.true(
            f"{name} {identifier}: |value| at least {factor:g} τ",
            margin is not None and margin >= factor,
        )
    passes: dict[str, Any] = {}
    for prefix in passing:
        found_ids = [identifier for identifier in by_id if identifier.startswith(prefix)]
        not_passing = [i for i in found_ids if by_id[i].result != "pass"]
        passes[prefix] = {"checks": len(found_ids), "not_passing": not_passing}
        ledger.true(f"{name} what passes: {prefix} present", bool(found_ids))
        ledger.equal(f"{name} what passes: {prefix}", not_passing, [])
    ledger.equal(f"{name} status", certificate.verification_status, "FAILED")
    ledger.equal(f"{name} false success detected", certificate.false_success_detected, True)
    missing = sorted(set(registered) - set(failing))
    ledger.equal(f"{name} registered checks outside the failing set", missing, [])
    record = {
        "verification_status": certificate.verification_status,
        "false_success_detected": certificate.false_success_detected,
        "failing": failing,
        "registered": checks,
        "what_passes": passes,
    }
    return record, by_id


def _a22(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """INJ-T1…T4 as `test_t05_w12_injections` builds and solves them (its fixtures), judged here
    by recording rather than asserting. The failing set is required to contain the registered
    checks, not to equal them (§12.5 as amended)."""
    from openflowsheet.verify.certificate import verify_revision

    fixtures = injection_fixtures
    injections, cases = ref["injections"], ref["unit_cases"]
    temperature, energy = support.TEMPERATURE_TOLERANCE, support.ENERGY_TOLERANCE
    flow, beta = support.FLOW_TOLERANCE, support.BETA_TOLERANCE
    factor = float(ref["constants"]["detection_factor"])
    ledger = Ledger()
    value: dict[str, Any] = {}

    # INJ-T1: VLV-2 solved, its outlet split forced LIQUID at the PH trivial root.
    entry = injections["INJ-T1"]
    document = fixtures._valve()
    binding, solve_plan, run = fixtures._executed(document)
    true_t = ledger.within("INJ-T1 true T", run.state["S2.T"], entry["true_T_K"], temperature)
    state = dict(run.state)
    state["S2.T"] = float(entry["T_trivial_K"])
    for c in COMPONENTS:
        state[f"S2.vap.{c}"] = 0.0
        state[f"S2.liq.{c}"] = state[f"S2.n.{c}"]
    state["S2.V"] = 0.0
    state["S2.L"] = sum(state[f"S2.n.{c}"] for c in COMPONENTS)
    record, by_id = _judge_injection(
        document,
        binding,
        run,
        solve_plan,
        state,
        {
            "phase_admissibility.U-VLV.S2.bubble": (entry["admissibility_sum_xK_minus_1"], beta),
            "energy_balance.U-VLV": (f"-{entry['fresh_flash_energy_gap_W']}", energy),
            "independent_split.U-VLV.S2.total": (
                f"-{entry['independent_split_V_gap_mol_s']}",
                flow,
            ),
        },
        ["residual.U-VLV:", "material_balance."],
        ledger,
        "INJ-T1",
        factor,
    )
    row = by_id.get("residual.U-VLV:VLV-energy")
    record["solved_true_T_error_K"] = true_t
    record["VLV-energy_row_W"] = None if row is None else row.value
    ledger.true(
        "INJ-T1 VLV-energy row within τ_E",
        row is not None and row.value is not None and abs(row.value) <= energy,
    )
    value["INJ-T1"] = record

    # INJ-T2: HX-F1's rows solved across the hot-end cross, from the twin's state.
    entry = injections["INJ-T2"]
    document = fixtures._exchanger()
    binding = w12_support.bind(document)
    result, step = w12_support.solve_from(binding, fixtures._hx_f1_state())
    ledger.equal("INJ-T2 region outcome", result.outcome, "CONVERGED")
    record, by_id = _judge_injection(
        document,
        binding,
        result,
        step.solve_plan,
        dict(result.state),
        {
            "bounds_and_domain.U-HX.hot_end": (str(-Decimal(entry["hot_end_K"])), temperature),
        },
        [
            "residual.U-HX:",
            "material_balance.U-HX.",
            "energy_balance.U-HX.",
            "specification.U-HX.",
            "bounds_and_domain.U-HX.cold_end",
            "bounds_and_domain.U-HX.heat_flow",
        ],
        ledger,
        "INJ-T2",
        factor,
    )
    cold, heat = by_id["bounds_and_domain.U-HX.cold_end"], by_id["bounds_and_domain.U-HX.heat_flow"]
    record["cold_end_error_K"] = ledger.within(
        "INJ-T2 cold end", -(cold.value or 0.0), entry["cold_end_K"], temperature
    )
    record["heat_flow_error_W"] = ledger.within(
        "INJ-T2 heat flow", -(heat.value or 0.0), entry["duty_W"], energy
    )
    value["INJ-T2"] = record

    # INJ-T3: RX-2 solved, its outlet rebuilt from the permuted ν' at the solved extent.
    entry = injections["INJ-T3"]
    document = fixtures._reactor()
    binding, solve_plan, run = fixtures._executed(document)
    extent = run.state["U-RX.xi"]
    extent_error = ledger.within(
        "INJ-T3 extent", extent, cases["RX-2"]["expected"]["extent_mol_per_s"], flow
    )
    state = dict(run.state)
    for c, nu in zip(COMPONENTS, fixtures.NU_PERMUTED, strict=True):
        flow_c = state[f"S1.n.{c}"] + nu * extent
        state[f"S2.n.{c}"] = flow_c
        state[f"S2.vap.{c}"] = flow_c
        state[f"S2.liq.{c}"] = 0.0
    state["S2.V"] = sum(state[f"S2.vap.{c}"] for c in COMPONENTS)
    state["S2.L"] = 0.0
    probe = verify_revision(binding, document, run, state=state, solve_plan=solve_plan)
    gap = next(c for c in probe.checks if c.id == "energy_balance.U-RX").value
    state["U-RX.Q"] = state["U-RX.Q"] - (gap or 0.0)
    balances = entry["component_balance_mol_s"]
    registered = {
        f"material_balance.U-RX.{c}": (expected, flow)
        for c, expected in zip(COMPONENTS, balances, strict=True)
        if Decimal(expected) != 0
    }
    record, by_id = _judge_injection(
        document,
        binding,
        run,
        solve_plan,
        state,
        registered,
        [
            "energy_balance.U-RX",
            "phase_admissibility.U-RX.S2.dew",
            "independent_split.U-RX.S2.",
        ],
        ledger,
        "INJ-T3",
        factor,
    )
    values = [by_id[f"material_balance.U-RX.{c}"].value or 0.0 for c in COMPONENTS]
    zero = [c for c, expected in zip(COMPONENTS, balances, strict=True) if Decimal(expected) == 0]
    for c in zero:
        check_c = by_id[f"material_balance.U-RX.{c}"]
        ledger.equal(f"INJ-T3 material_balance.U-RX.{c} result", check_c.result, "pass")
        ledger.within(f"INJ-T3 material_balance.U-RX.{c}", check_c.value, "0.0", flow)
    from openflowsheet.models.syn001.conversion_reactor import MOLAR_MASSES

    record["solved_extent_error"] = extent_error
    record["component_balances"] = values
    record["total_moles_error"] = ledger.within(
        "INJ-T3 total moles", sum(values), entry["total_moles_mol_s"], flow
    )
    record["mass_balance_error"] = ledger.within(
        "INJ-T3 mass",
        sum(m * v for m, v in zip(MOLAR_MASSES, values, strict=True)),
        entry["mass_balance_kg_s"],
        flow,
    )
    value["INJ-T3"] = record

    # INJ-T4: PUMP-1 solved, then W = W_s at the balancing outlet temperature.
    entry = injections["INJ-T4"]
    document = fixtures._pump()
    binding, solve_plan, run = fixtures._executed(document)
    work_error = ledger.within(
        "INJ-T4 solved work", run.state["U-PUMP.W"], cases["PUMP-1"]["expected"]["work_W"], energy
    )
    state = dict(run.state)
    state["U-PUMP.W"] = float(cases["PUMP-1"]["expected"]["work_ideal_W"])
    state["S2.T"] = state["S1.T"]
    record, by_id = _judge_injection(
        document,
        binding,
        run,
        solve_plan,
        state,
        {"energy_balance.U-PUMP.work_relation": (entry["work_relation_W"], energy)},
        [],
        ledger,
        "INJ-T4",
        factor,
    )
    # What passes: the energy balance (its id is a prefix of the work relation's, so it is
    # read by id, not by prefix).
    balance = by_id["energy_balance.U-PUMP"]
    ledger.equal("INJ-T4 energy_balance.U-PUMP result", balance.result, "pass")
    record["what_passes"] = {"energy_balance.U-PUMP": balance.result}
    record["solved_work_error_W"] = work_error
    record["energy_balance_error_W"] = ledger.within(
        "INJ-T4 energy balance", balance.value, entry["energy_balance_W"], energy
    )
    value["INJ-T4"] = record
    ledger.equal("registered injections", sorted(injections), sorted(value))
    value["departures"] = ledger.departures
    expected = {
        "each": "FAILED with false_success_detected; the registered failing checks among the "
        "failures, each at its registered value to §14's tolerance and at least "
        f"{factor:g} τ; the 'what passes' checks passing",
        "INJ-T1": [
            "phase_admissibility.U-VLV.S2.bubble",
            "energy_balance.U-VLV",
            "independent_split.U-VLV.S2.total",
        ],
        "INJ-T2": ["bounds_and_domain.U-HX.hot_end"],
        "INJ-T3": ["material_balance.U-RX.A", "material_balance.U-RX.B"],
        "INJ-T4": ["energy_balance.U-PUMP.work_relation"],
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A25


def _a25(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """The registry's family `SYN-001-UL` and its four cases as spec §21 states them. The
    registry has no JSON schema; "validate" is measured as: the family's fields and SYN-001's
    shared values; each case's revision schema-valid (`process-revision.schema.json`) and bound
    by `bind_revision_flowsheet`; its reference hash and key resolving in `ref`; its expected
    outcome and denominator as §21's table; C3X's accepted outcomes exactly A20's two."""
    from openflowsheet.application.revision_binding import (
        RevisionBinding,
        bind_revision_flowsheet,
    )

    ledger = Ledger()
    registry = reference(REGISTRY)
    families = {family["id"]: family for family in registry["families"]}
    family = families.get("SYN-001-UL", {})
    reference_sha = file_sha256(REFERENCE)
    spec_path = str(SPEC.relative_to(ROOT))
    shared = (
        "property_domain",
        "reference_convention",
        "state_definition",
        "tolerances",
        "scales",
        "budgets",
    )

    def numbers(entry: Any) -> Any:
        if isinstance(entry, dict):
            return {
                key: numbers(item)
                for key, item in entry.items()
                if key not in ("source", "applicability", "note")
            }
        return entry

    family_value = {
        "present": bool(family),
        "kind": family.get("kind"),
        "derivation": family.get("derivation"),
        "specification": family.get("specification"),
        "semantics": family.get("semantics"),
        "components": family.get("components"),
        "oracle": family.get("oracle"),
        "reference": family.get("reference"),
        "reference_sha256_is_the_yamls": family.get("reference_sha256") == reference_sha,
        "reference_convention": family.get("reference_convention"),
        "shared_with_syn001": {
            key: numbers(family.get(key)) == numbers(families["SYN-001"].get(key)) for key in shared
        },
    }
    ledger.equal(
        "family",
        {key: family_value[key] for key in family_value if key != "shared_with_syn001"},
        {
            "present": True,
            "kind": "synthetic",
            "derivation": spec_path,
            "specification": spec_path,
            "semantics": [
                "docs/adr/0001-state-units-zero-flow.md",
                "docs/adr/0011-unit-models-ph-closure-and-reaction-datum.md",
            ],
            "components": "benchmarks/syn001/components.yaml",
            "oracle": None,
            "reference": "benchmarks/t05/reference_values.yaml",
            "reference_sha256_is_the_yamls": True,
            "reference_convention": "SYN-001-ref-v1",
        },
    )
    ledger.equal(
        "family values shared with SYN-001",
        family_value["shared_with_syn001"],
        dict.fromkeys(shared, True),
    )

    validator = _validator("process-revision.schema.json")
    registered = {
        "SYN-001-UL-C1": ("oracle_values", True),
        "SYN-001-UL-C2": ("oracle_values", True),
        "SYN-001-UL-C3": ("oracle_values", True),
        C3X: ("typed_failure_or_failed_certificate", False),
    }
    in_family = [
        case["case_id"] for case in registry["cases"] if case.get("family") == "SYN-001-UL"
    ]
    ledger.equal("cases of the family", in_family, list(registered))
    cases: dict[str, Any] = {}
    for entry in registry["cases"]:
        case_id = entry["case_id"]
        if case_id not in registered:
            continue
        revision_path = ROOT / entry["revision"]
        document = yaml.safe_load(revision_path.read_text(encoding="utf-8"))
        key = entry.get("reference_key", "")
        node: Any = ref
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        expected = entry["expected"]
        cases[case_id] = {
            "revision": entry["revision"],
            "schema_errors": _errors(validator, document),
            "binds": isinstance(bind_revision_flowsheet(document), RevisionBinding),
            "reference_sha256_is_the_yamls": entry.get("reference_sha256") == reference_sha,
            "reference_key_resolves": node is not None,
            "outcome": expected["outcome"],
            "in_success_denominator": expected["in_success_denominator"],
        }
        outcome, denominator = registered[case_id]
        ledger.equal(
            case_id,
            cases[case_id],
            {
                "revision": f"benchmarks/t05/cases/{case_id}.yaml",
                "schema_errors": 0,
                "binds": True,
                "reference_sha256_is_the_yamls": True,
                "reference_key_resolves": True,
                "outcome": outcome,
                "in_success_denominator": denominator,
            },
        )
        if case_id == C3X:
            accepted = expected.get("accepted", [])
            summary = [
                {
                    key: item.get(key)
                    for key in (
                        "outcome",
                        "code",
                        "message",
                        "failing_checks",
                        "value_K",
                        "value_allowance_K",
                    )
                    if key in item
                }
                for item in accepted
            ]
            cases[case_id]["accepted"] = summary
            ledger.equal(
                "C3X accepted",
                summary,
                [
                    {
                        "outcome": "typed_failure",
                        "code": "INITIALIZATION_FAILED",
                        "message": "initializer_failed(U-HX): temperature_cross(cold_end)",
                    },
                    {
                        "outcome": "failed_certificate",
                        "failing_checks": C3X_FAILING,
                        "value_K": C3X_COLD_END_K,
                        "value_allowance_K": C3X_ALLOWANCE_K,
                    },
                ],
            )
    ledger.equal("cases found", sorted(cases), sorted(registered))
    value = {"family": family_value, "cases": cases, "departures": ledger.departures}
    expected_value = {
        "family": "SYN-001-UL with §21's fields, the YAML's SHA-256, SYN-001's shared values",
        "cases": {
            case_id: {"outcome": outcome, "in_success_denominator": denominator}
            for case_id, (outcome, denominator) in registered.items()
        },
        "each_case": "revision schema-valid and bound; reference hash and key resolve",
        "C3X_accepted": "exactly A20's two outcomes",
    }
    return ledger.ok, value, expected_value


# ----------------------------------------------------------------------------------- A26


def _a26(runs: Runs, ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """§12.3's lifted-split descriptors field by field (`test_t05_w12_discovery.DESCRIPTORS`, the
    design note's §3.1 applied to each case's wiring) and the converged roots' `branch_found`
    (`test_t05_coupled.BRANCH_FOUND`, spec A26's literal) in declaration order."""
    from dataclasses import fields as dataclass_fields

    from openflowsheet.orchestrator.region import LiftedSplit
    from openflowsheet.orchestrator.revision import instances_of
    from openflowsheet.orchestrator.splits import lifted_splits

    ledger = Ledger()
    per_case: dict[str, Any] = {}
    for case in COUPLED:
        solved = runs.solved(case)
        flowsheet = solved.binding.flowsheet
        found = lifted_splits(instances_of(flowsheet), flowsheet.components)
        wanted = discovery_fixtures.DESCRIPTORS[case]
        differing = [
            f"{got.unit}.{item.name}"
            for got, want in zip(found, wanted, strict=False)
            for item in dataclass_fields(LiftedSplit)
            if getattr(got, item.name) != getattr(want, item.name)
        ]
        fingerprint = solved.region.root_fingerprint
        branch = [list(entry) for entry in fingerprint["branch_found"]] if fingerprint else None
        order = [unit.unit_id for unit in flowsheet.units()]
        in_order = branch is not None and [u for u, _ in branch] == sorted(
            (u for u, _ in branch), key=order.index
        )
        per_case[case] = {
            "descriptor_units": [split.unit for split in found],
            "descriptor_fields_differing": differing,
            "branch_found": branch,
            "branch_found_in_declaration_order": in_order,
        }
        ledger.equal(
            f"{case} descriptor units",
            per_case[case]["descriptor_units"],
            [split.unit for split in wanted],
        )
        ledger.equal(f"{case} descriptor fields", differing, [])
        ledger.equal(f"{case} branch_found", branch, coupled_fixtures.BRANCH_FOUND[case])
        ledger.true(f"{case} branch_found in declaration order", in_order)
    value = {"cases": per_case, "departures": ledger.departures}
    expected = {
        "descriptors": {
            case: [split.unit for split in discovery_fixtures.DESCRIPTORS[case]] for case in COUPLED
        },
        "branch_found": dict(coupled_fixtures.BRANCH_FOUND),
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A27


def _a27(ref: Mapping[str, Any]) -> tuple[bool, Any, Any]:
    """PTC over each coupled case's region (T04's `eo_policy("ptc")`), on the region solve
    directly and through `plan_revision` → `execute_plan` with the executor's compiled problem
    spied; residual and Jacobian calls counted as T04's A14 counts them. The row named is the
    first T05 `holdup_balance` row in region row order (`FIRST_UNMAPPED_ROW`, measured)."""
    import openflowsheet.orchestrator.executor as executor_module
    from openflowsheet.compile.casadi_backend import compile_problem
    from openflowsheet.orchestrator.executor import execute_plan
    from openflowsheet.orchestrator.mass import residence_time
    from openflowsheet.orchestrator.region import solve_region
    from openflowsheet.orchestrator.revision import (
        InitialStateFailure,
        initial_state,
        instances_of,
        plan_revision,
    )
    from openflowsheet.orchestrator.splits import lifted_splits
    from openflowsheet.orchestrator.trace import Trace

    ledger = Ledger()
    per_case: dict[str, Any] = {}
    for case in COUPLED:
        policy = eo_policy("ptc")
        binding = w12_support.bind(w11_fixtures.case_document(case))
        flowsheet, spec = binding.flowsheet, binding.spec
        step = w12_support.planned_step(binding, policy)
        start = initial_state(flowsheet, spec.variable_ids)
        if isinstance(start, InitialStateFailure):
            raise RuntimeError(f"{case}: the traversal refused, {start}")
        trace = Trace()
        spied = SpiedCompiled(compile_problem(spec), trace)
        result = solve_region(
            compiled=spied,
            spec=spec,
            region=step.region,
            state=start,
            splits=lifted_splits(instances_of(flowsheet), flowsheet.components),
            provider=flowsheet.provider,
            policy=policy,
            trace=trace,
            initializer_source="traversal-G0-v1",
            mass_mapping=residence_time(flowsheet.wiring, flowsheet.components),
        )
        spies: list[Any] = []

        def spied_compile(declaration: Any, spies: list[Any] = spies) -> Any:
            spies.append(SpiedCompiled(compile_problem(declaration)))
            return spies[-1]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(executor_module, "compile_problem", spied_compile)
            plan, _ = plan_revision(binding, policy)
            run = execute_plan(plan=plan, flowsheet=flowsheet, spec=spec, policy=policy)
        row = discovery_fixtures.FIRST_UNMAPPED_ROW[case]
        per_case[case] = {
            "row": row,
            "row_in_region": row in step.region.row_ids,
            "region": {
                "outcome": result.outcome,
                "message": result.message,
                "attempts": len(result.attempts),
                "events": len(trace),
                "compiled_calls": len(spied.calls),
            },
            "plan": {
                "steps": [[s.outcome, s.message] for s in run.steps],
                "compiled_problems": len(spies),
                "compiled_calls": sum(len(spy.calls) for spy in spies),
            },
        }
        message = f"ptc_mapping_invalid({row}, missing)"
        ledger.equal(
            case,
            per_case[case],
            {
                "row": row,
                "row_in_region": True,
                "region": {
                    "outcome": "PTC_MAPPING_INVALID",
                    "message": message,
                    "attempts": 0,
                    "events": 0,
                    "compiled_calls": 0,
                },
                "plan": {
                    "steps": [["PTC_MAPPING_INVALID", message]],
                    "compiled_problems": per_case[case]["plan"]["compiled_problems"],
                    "compiled_calls": 0,
                },
            },
        )
        ledger.true(f"{case}: the executor compiled the step", bool(spies))
    value = {"cases": per_case, "departures": ledger.departures}
    expected = {
        "each_case": "PTC_MAPPING_INVALID with ptc_mapping_invalid(row, missing) naming the "
        "first T05 holdup_balance row, no attempt, no event, no residual or Jacobian call — on "
        "the region solve and through the plan",
        "rows": dict(discovery_fixtures.FIRST_UNMAPPED_ROW),
    }
    return ledger.ok, value, expected


# ----------------------------------------------------------------------------------- A23


def _git(*arguments: str) -> str:
    completed = subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    return completed.stdout


def _fixture_tree() -> tuple[str, int]:
    """W0.1's fixture-tree digest: every file under `tests/fixtures/`, sorted by path, each as
    path + NUL + bytes + NUL."""
    digest = hashlib.sha256()
    files = sorted(path for path in FIXTURES.rglob("*") if path.is_file())
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest(), len(files)


def _document_sha256(document: Mapping[str, Any]) -> str:
    """The digest of an identity document as `k05_structural_identity.py --out` writes it."""
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _r015_fixtures() -> dict[str, Any]:
    """R-015: every committed fixture that a generator emits, compared with what it emits today
    (K03's, K04's, K05's and T04's generators; T05 adds none)."""
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


def _a23(
    identity_document: Mapping[str, Any], identities: Path | None, gate: Mapping[str, Any]
) -> dict[str, Any]:
    description = DESCRIPTIONS["A23"]
    try:
        local, value = _a23_local(identity_document)
        gate_ok, value["gate"] = _gate_value(gate)
        local = local and gate_ok
    except Exception as error:  # noqa: BLE001
        return check(
            "T05.A23", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    expected: dict[str, Any] = {
        "syn001_py": {"sha256": W01["syn001_py_sha256"], "equal_to_base": True},
        "tests": {
            "k02_t04_files_changed": list(SANCTIONED_TEST_EDITS),
            "k02_t04_lines_removed": 0,
            "added_outside_t05": [],
        },
        "gate": "passed; pytest collected = passed (+ xfailed, each a T05 mark); no failure or "
        "error; K02, K03, K04, K05, T02, T03, T04 and T05 families each at least one test",
        "structural_sha256_local": W01["structural_sha256"],
        "check_policy_sha256": W01["check_policy_sha256"],
        "lifted_splits_repr_sha256": W01["lifted_splits_repr_sha256"],
        "fixtures": {
            "tree_sha256": W01["fixture_tree_sha256"],
            "files": W01["fixture_files"],
            "r015_differences": [],
        },
        "identity_document_minus_t05_sha256": W01["identity_document_sha256"],
        "ci": {"platforms": 2, "structural_sha256": [W01["structural_sha256"]] * 2},
    }
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("T05.A23", description, "unsupported" if local else "fail", value, expected)
    documents = _ci_documents(identities)
    hashes = [document.get("structural_sha256") for document in documents.values()]
    value["ci"] = {
        "platforms": len(documents),
        "structural_sha256": hashes,
        "artifact_sha256": {name: _document_sha256(doc) for name, doc in documents.items()},
    }
    agrees = len(documents) == 2 and hashes == [W01["structural_sha256"]] * 2
    return check("T05.A23", description, verdict(local and agrees), value, expected)


def _a23_local(identity_document: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    from openflowsheet.orchestrator.region import syn001_lifted_splits
    from openflowsheet.verify.certificate import CheckPolicy

    ledger = Ledger()
    # (i) The provider's source, byte for byte against the base commit.
    syn001 = SOURCE / "thermo" / "syn001.py"
    base = subprocess.run(  # noqa: S603
        ["git", "show", f"{BASE_COMMIT}:src/openflowsheet/thermo/syn001.py"],  # noqa: S607
        capture_output=True,
        cwd=ROOT,
        check=True,
    ).stdout
    syn001_value = {
        "sha256": file_sha256(syn001),
        "equal_to_base": syn001.read_bytes() == base,
    }
    ledger.equal(
        "(i) thermo/syn001.py",
        syn001_value,
        {"sha256": W01["syn001_py_sha256"], "equal_to_base": True},
    )

    # (ii) K02–T04's tests: which files changed since the base, and how.
    status = [
        line.split("\t")
        for line in _git("diff", "--name-status", BASE_COMMIT, "--", "tests/").splitlines()
    ]
    added = sorted(path for kind, path, *_ in status if kind == "A")
    changed = sorted(path for kind, path, *_ in status if kind != "A")
    numstat = (
        {
            parts[2]: (int(parts[0]), int(parts[1]))
            for parts in (
                line.split("\t")
                for line in _git("diff", "--numstat", BASE_COMMIT, "--", *changed).splitlines()
            )
        }
        if changed
        else {}
    )
    foreign = [
        path
        for path in added
        if not re.fullmatch(r"tests/(test_t05_[a-z0-9_]+|t05_[a-z0-9_]+)\.py", path)
    ]
    tests_value = {
        "added_files": added,
        "added_outside_t05": foreign,
        "k02_t04_files_changed": changed,
        "k02_t04_lines": {
            path: {"added": plus, "removed": minus} for path, (plus, minus) in numstat.items()
        },
        "k02_t04_lines_removed": sum(minus for _, minus in numstat.values()),
    }
    ledger.equal("(ii) tests added outside T05's names", foreign, [])
    ledger.equal("(ii) K02–T04 test files changed", changed, list(SANCTIONED_TEST_EDITS))
    ledger.equal("(ii) K02–T04 test lines removed", tests_value["k02_t04_lines_removed"], 0)

    # (iii) K05's structural hash on this machine (the CI pair is the caller's half).
    ledger.equal(
        "(iii) structural_sha256", identity_document["structural_sha256"], W01["structural_sha256"]
    )
    # (iv) K04's registered check policy.
    policy = CheckPolicy().sha256
    ledger.equal("(iv) check_policy_sha256", policy, W01["check_policy_sha256"])
    # (v) The two SYN-001 lifted-split descriptors.
    splits = hashlib.sha256(repr(syn001_lifted_splits(COMPONENTS)).encode("utf-8")).hexdigest()
    ledger.equal("(v) syn001_lifted_splits repr", splits, W01["lifted_splits_repr_sha256"])
    # (vi) The committed fixtures: the tree, and R-015's generators against it.
    tree, files = _fixture_tree()
    r015 = _r015_fixtures()
    differing = sorted(name for name, entry in r015.items() if entry["differences"])
    ledger.equal(
        "(vi) fixture tree", (tree, files), (W01["fixture_tree_sha256"], W01["fixture_files"])
    )
    ledger.equal("(vi) R-015 differences", differing, [])
    # And the identity document less T05's own key — and T05b's (spec B21, B22), a later
    # package's key that T05's W0.1 baseline predates.
    minus_t05 = _document_sha256(
        {key: item for key, item in identity_document.items() if key not in ("t05", "t05b")}
    )
    ledger.equal("identity document minus t05", minus_t05, W01["identity_document_sha256"])

    value = {
        "syn001_py": syn001_value,
        "tests": tests_value,
        "structural_sha256_local": identity_document["structural_sha256"],
        "check_policy_sha256": policy,
        "lifted_splits_repr_sha256": splits,
        "fixtures": {
            "tree_sha256": tree,
            "files": files,
            "r015_compared": len(r015),
            "r015_generators": sorted({entry["generator"] for entry in r015.values()}),
            "r015_differences": differing,
        },
        "identity_document_minus_t05_sha256": minus_t05,
        "departures": ledger.departures,
    }
    return ledger.ok, value


# ----------------------------------------------------------------------------------- A24


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


#: A24's "In" (ruling round Q-R5): digests of declared inputs, by the key that holds them — the
#: model and constants identities and T03's `variable_ids_sha256` — and declared constants as
#: shortest decimal strings: the plan's scales and bounds and T03's registered δ_root. Identifier
#: fields (`model_version`, `plan_id`) are hash-derived labels, not numbers.
_DECLARED_DIGEST_KEYS = ("constants_sha256", "model_version", "variable_ids_sha256")
_DECLARED_CONSTANT_PATH = re.compile(
    r"\.solve_plan\.(bounds|column_scales|row_scales)\.|\.root_fingerprint\.delta_scaled_inf$"
)
_IDENTIFIER_KEYS = ("model_version", "plan_id")


def _a24(identity_document: Mapping[str, Any], identities: Path | None) -> dict[str, Any]:
    description = DESCRIPTIONS["A24"]
    try:
        local, value = _a24_local(identity_document)
    except Exception as error:  # noqa: BLE001
        return check(
            "T05.A24", description, "fail", {"error": f"{type(error).__name__}: {error}"}, ""
        )
    expected: dict[str, Any] = {
        "cases": [*COUPLED, C3X],
        "floats": [],
        "digests_outside_declared_inputs": [],
        "float_shaped_strings_outside_declared_constants": [],
        "messages": {
            **dict.fromkeys(COUPLED, ""),
            C3X: "initializer_failed(U-HX): temperature_cross(cold_end)",
        },
        "same_twice": True,
        "k05_carries_t05": True,
        "ci": {
            "platforms": 2,
            "identity_differences": [],
            "t05_equal": True,
            "t05_equal_to_this_machines": True,
        },
    }
    if identities is None:
        value["ci"] = "not measured: no --identities directory given"
        return check("T05.A24", description, "unsupported" if local else "fail", value, expected)
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
    t05 = [document.get("t05") for document in documents.values()]
    mine = json.loads(json.dumps(identity_document["t05"]))
    value["ci"] = {
        "platforms": len(names),
        "identity_differences": differing,
        "t05_equal": len(t05) >= 2 and bool(t05[0]) and all(item == t05[0] for item in t05),
        "t05_equal_to_this_machines": bool(t05) and all(item == mine for item in t05),
        "artifact_sha256": {
            str(path.relative_to(identities)): file_sha256(path)
            for path in sorted(identities.rglob("identity.json"))
        },
    }
    agrees = all(value["ci"][key] == expected["ci"][key] for key in expected["ci"])
    return check("T05.A24", description, verdict(local and agrees), value, expected)


def _a24_local(identity_document: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    from t05_identity import identity

    from openflowsheet.run.identity import floats_in

    first, second = identity(), identity()
    strings = list(_strings(first))
    digests = sorted(
        {
            path.split(".", 2)[-1]
            for path, text in strings
            if HEX64.search(text) and path.rsplit(".", 1)[-1] not in _DECLARED_DIGEST_KEYS
        }
    )
    float_shaped = sorted(
        {
            path.split(".", 2)[-1]
            for path, text in strings
            if FLOAT.search(HEX64.sub("", text))
            and not _DECLARED_CONSTANT_PATH.search(path)
            and path.rsplit(".", 1)[-1] not in _IDENTIFIER_KEYS
        }
    )
    value = {
        "cases": list(first),
        "floats": floats_in(first)[:10],
        "digests_outside_declared_inputs": digests[:10],
        "float_shaped_strings_outside_declared_constants": float_shaped[:10],
        "declared_constant_strings": sum(
            1 for path, text in strings if _DECLARED_CONSTANT_PATH.search(path)
        ),
        "messages": {case: entry.get("message") for case, entry in first.items()},
        "outcomes": {case: entry.get("outcome") for case, entry in first.items()},
        "same_twice": first == second,
        "k05_carries_t05": json.loads(json.dumps(identity_document.get("t05")))
        == json.loads(json.dumps(first)),
        "t05_sha256": _document_sha256(first),
        "identity_document_sha256": _document_sha256(identity_document),
    }
    expected = {
        "cases": [*COUPLED, C3X],
        "floats": [],
        "digests_outside_declared_inputs": [],
        "float_shaped_strings_outside_declared_constants": [],
        "messages": {
            **dict.fromkeys(COUPLED, ""),
            C3X: "initializer_failed(U-HX): temperature_cross(cold_end)",
        },
        "same_twice": True,
        "k05_carries_t05": True,
    }
    return all(value[key] == expected[key] for key in expected), value


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
        "pytest_passed": counts.get("passed", 0),
        "pytest_counts": counts,
        "pytest_failed_or_errors": bool(
            counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
        ),
        "collected": len(collected),
        "families": {
            family: sum(1 for line in collected if line.startswith(f"tests/test_{family}_"))
            for family in ("k02", "k03", "k04", "k05", "t02", "t03", "t04", "t05")
        },
    }


def _pytest_counts(text: str) -> dict[str, int]:
    """The last pytest summary line (`2534 passed, 1 xfailed in 27.1s`), as counts by word."""
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
    """`tested` when nothing failed. An `unsupported` check carries its reason in its own value
    and in `limitations`, which is T01's to T04's rule; a `fail` anywhere leaves the package
    `implemented`, never `tested`."""
    return "implemented" if any(entry["result"] == "fail" for entry in checks) else "tested"


def _case_hash() -> str:
    """One digest over every registered revision this package ran, in name order."""
    digest = hashlib.sha256()
    for path in sorted(CASES.glob("*.yaml")):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _xfails() -> list[str]:
    """Every `xfail` mark in the test tree, by file and line (from the syntax tree): a K02–T04
    test may not be one."""
    found: list[str] = []
    for path in sorted((ROOT / "tests").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr == "xfail":
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def _gate_value(gate: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    """A23 (ii)'s second half: the gate ran and passed every collected test (an xfail would have
    to be T05's own, and there is none to allow for unless the tree marks one); K02's to T04's
    families are among them."""
    xfails = _xfails()
    counts = gate["pytest_counts"]
    value = {
        "passed": gate["passed"],
        "pytest_counts": counts,
        "collected": gate["collected"],
        "families": gate["families"],
        "xfail_marks": xfails,
    }
    ok = (
        gate["passed"]
        and not gate["pytest_failed_or_errors"]
        and set(counts) <= {"passed", "xfailed"}
        and gate["collected"] == counts.get("passed", 0) + counts.get("xfailed", 0) > 0
        and counts.get("xfailed", 0) == len(xfails)
        and all(mark.startswith("tests/test_t05_") for mark in xfails)
        and all(
            gate["families"].get(name, 0) > 0
            for name in ("k02", "k03", "k04", "k05", "t02", "t03", "t04", "t05")
        )
    )
    return ok, value


def _limitations(identities: bool, ci_run: bool, refused: Sequence[str]) -> list[str]:
    stated = [
        # Spec §18, restated item by item.
        "Spec §18: no T05 model is shown right for any real substance. Everything is SYN-001: "
        "invented constants, ideal VLE, equal c_p and v_i. Agreement with the twin verifies "
        "algebra and bookkeeping — numerical verification, not empirical validation.",
        "Spec §18: component discrimination in liquid enthalpy is not tested. SYN-001's liquid "
        "enthalpy is the same function for every component, so a permuted component inside a "
        "liquid enthalpy is invisible at every state (§13.5); liquid reactions are thermoneutral "
        "and liquid energy balances composition-blind for the same reason. The pump's work "
        "relation's inlet-temperature dependence is untested (it cancels exactly).",
        "Spec §18: heat of reaction in a liquid is not exercised. Every registered liquid "
        "reaction has Δh_r = 0 under ADR 0011 D2's formation datum; a non-thermoneutral liquid "
        "reaction needs other data (§19 Q8, Frank's preference, default no).",
        "Spec §18: exchanger feasibility with a phase change, or with temperature-dependent c_p, "
        "is not established. The terminal second-law check is exact only for §10.4's class; "
        "v0.1 refuses the rest (§19 Q2).",
        "Spec §18's three registered v0.1 limitations — the dormant PH-type outlet (§4.7 (a), "
        "A28), a single flowing component in the latent jump on the EO path (§4.7 (b), A30) and "
        "the near-pure PH kernel (§4.4, A29) — are retired by ADR 0012 (T05b spec §16; R-049 and "
        "R-050 reversed). A28–A30 are recorded `not_applicable` (`retired by ADR 0012`), not "
        "re-measured and never `pass` of the retired claim; their measurements stand in T05's "
        f"manifest at `91ac010` ({RETIRED_EVIDENCE}), and T05b's evidence carries their "
        "replacements (B15, B01, B08–B09).",
        "Spec §18: the solution accuracy of the coupled cases is established only as far as "
        "K04's recorded bound shows (W0.6; A21 judges the exact ‖Ĵ⁻¹‖₁, on which C3's margin to "
        "1e-8 is about 3×, a tolerance stop, not a guarantee), and certificate robustness to "
        "T04's F9 on the EO path is not established (§12.6).",
        "Spec §18: external validation is separate. T06's comparisons with DWSIM and IDAES are "
        "not part of T05; the representability notes show the tools can express these models, "
        "not that they agree.",
        "Spec §18: that C3 is NET-07 is T06's decision; its fixed point reduces to one scalar "
        "equation.",
        "Spec §18: human numerical and process-modelling review is not claimed; `review` is "
        "`pending` in both fields and no agent sets it.",
        # Findings handed on (spec §20), not closed here.
        "Spec §20 F10: K04's recorded solution-error bound uses `onenormest`, a lower estimate; "
        "at C3 it is 6 % low (16.63 against an exact 17.76). The certificate keeps K04's value; "
        "A21 judges the exact product. A K04 amendment, if wanted, is the design lane's.",
        "Spec §20 F7: K02's TPFlash.evaluate does not apply R-007 to a declared inlet phase; "
        "harmless in SYN-001 (its inlet is lifted), handed to the build lane as a K02 finding.",
    ]
    stated += [
        f"ADR 0011 lists {identifier} among the requirements served; the frozen evidence-manifest "
        f"schema takes D/A ids only (measured: it refuses `{identifier}`), so `requirements` omits "
        "it and `docs/requirements.yaml` carries it (T02's to T04's precedent for V-items)."
        for identifier in refused
    ]
    if not identities:
        stated.append(
            "The cross-platform halves of A23 (structural_sha256 on the CI pair) and A24 (the "
            "`t05` identity on the CI pair) were not measured by this run: no `--identities` "
            "directory was given, so those checks are `unsupported`, not `pass`."
        )
    if not ci_run:
        stated.append(
            "No CI run was named (`--ci-run`), so `commands` records the local gate only."
        )
    return stated


#: One paragraph per assertion: what is measured, in the manifest's words (the value says how).
DESCRIPTIONS: dict[str, str] = {
    "A00": "Generator self-check: `t05_reference.py --check` passes with the number of claims "
    "the committed YAML lists (438) and prints exactly that list, the AST import rule among "
    "them; the committed YAML's SHA-256 is the one in the specification header; `--emit` twice "
    "(two processes) gives identical bytes, equal to the committed file; the generator and every "
    "sibling script it imports, transitively, import nothing from `openflowsheet` or "
    "`benchmarks` (every import statement, from the syntax tree).",
    "A01": "The six T05 manifests at every configuration their tables allow (the PH flash's and "
    "the valve's inlet phase, the reactor's key, energy mode and inlet phase, the separator's "
    "outlet and inlet phases, the exchanger's specification and side phases; the pump's nominal "
    "alone): each validates against the frozen model-manifest schema; its id, "
    "`introduced_by_package` and `planned_package` `T05`; ports (name, kind, direction, "
    "multiplicity, phase capabilities) and equations (ids in order, conditional class) exactly "
    "spec §5-§10's tables; `residuals` `ad` regime `all` and every other derivative, each outlet "
    "state's included, `unavailable`; `property_provider` `syn001`, `reference_convention` "
    "`SYN-001-ref-v1`; `status` neither `reviewed` nor `released`. The PH flash's, valve's and "
    "reactor's `validity.limitations` cite T05b spec §5.1-§5.3 and §6.6 once each and none of "
    "the retired spec §4.4, §4.7 (a), (b) (spec §5.1 as amended by T05b spec §16).",
    "A02": "The accumulation classification of every equation of the six manifests, over every "
    "configuration (one block per key), equals spec §13.2's table as a literal dict (8 "
    "`holdup_balance`, 6 `zero_holdup_balance`, 17 `algebraic`); the eight holdups' symbols and "
    "dimensions are §13.2's with each row's dimension one time power lower (ADR 0008 D3.2); the "
    "fourteen balance statements and three zero-holdup reasons are §5-§10's text verbatim; ADR "
    "0008 M1-M5, with that ADR's own registered tables, hold on the six P01 manifests, and no "
    "T05 manifest is among them (F4).",
    "A03": "Each unit's contribution at every configuration: rows per declared equation with "
    "origin `model#EQ`, their row kinds and accumulation as declared, lifting rows "
    "`model#lifting` `algebraic` `molar_flow`, unique row ids, owned variables and pinned-input "
    "ids as §5-§10 (the configured specification row and pin included), and rows = the outlets' "
    "unknowns plus owned variables (square given the inlets). A pinned-input change keeps the "
    "unit's `model_version` and moves `constants_sha256`; a configuration that moves an id moves "
    "`model_version`; one that moves no id keeps every id and the structure hash while the rows "
    "differ at one state. At flowsheet level (R-047) each configuration change moves the "
    "revision flowsheet's label and `model_version`, and each pinned-value change moves neither "
    "and moves `constants_sha256`.",
    "A04": "Rows at the twelve trial states (two per model, `ref.trial_states`): each model's "
    "unit assembled alone through `models.assemble` by the tests' harness "
    "(`t05_trial_states.assemble_trial` on each model test's `build_trial`, a lifted inlet's "
    "split added as free columns), compiled through K01 and evaluated at the registered `x`; the "
    "columns, the row-id set and the row kinds are exactly the registered ones, and every row is "
    "within `1e-12 x` its registered term scale, the registered value taken at full precision. "
    "The worst ratio per model and overall is recorded.",
    "A05": "Jacobians at the same twelve states: every registered nonzero within `1e-11` "
    "relative; every registered cancelling partial within `1e-11 x` its registered partial "
    "scale; every other entry the compiled structure stores in the unit's rows exactly `0.0` "
    "(counted per state). The worst nonzero ratio and every cancelling partial's ratio are "
    "recorded.",
    "A06": "Rows at the twin's causal solutions of PHF-1, 5, 6, VLV-2, 5, PUMP-1, RX-3, 4, 5, "
    "SEP-2, HX-1 and HX-4 (every coordinate the double its registered string rounds to; VLV-5's "
    "lifted inlet split VLV-2's registered outlet split), the unit assembled alone and compiled "
    "through K01 (`test_t05_limits.rows_at_solution`): every row within K04's `tau_kind`; the "
    "worst `|row| / tau_kind` per case is recorded.",
    "A07": "PH flash cases PHF-1…7, Z0, Z1, F1…F4 through `test_t05_ph_flash.unit_for` "
    "(`evaluate_with_closure`) and the construction refusal PHF-S1: status, code (the message's "
    "first line), signature and route exact; T, both products' flows, T and P, β and duty to "
    "§14 against `ref.unit_cases`, every registered zero flow `== 0.0`; a failure carries no "
    "answer. The value lists each case and the worst error over its tolerance per quantity.",
    "A08": "Valve cases VLV-1…5, Z, F1 (`test_t05_valve.unit_for`) and VLV-S1: status, code, "
    "signature exact; no duty and no work (no energy port); the outlet and the PH kernel's lifted "
    "split (regime, vapour and liquid flows) to §14; the dormant case never reaches the kernel.",
    "A09": "Pump cases PUMP-1…4, F1…F3, Z (`test_t05_pump.unit_for`) and PUMP-S1, S2: status, "
    "code, signature exact; no duty; the work `W` and, where registered, the ideal work `η W` "
    "to 1.01e-3 W; the outlet to §14.",
    "A10": "Reactor cases RX-1…8, Z, F1, F5 (`test_t05_reactor.unit_for`, `evaluate_with_split`) "
    "and RX-S1…S5 (RX-S4 through the tests' `ConventionDouble`, convention SYN-001-ref-v0): "
    "status, code, signature exact; ξ, duty, outlet and split to §14 on ok cases, RX-F1's extent "
    "`None`; on every ok case the key's outlet equals the pre-amendment form `n_in + ν_k ξ` bit "
    "for bit (§6.3 as amended, |ν_k| ∈ {1, 2}); and ruling Q-R7's acceptance: the P2 input ok "
    "with `n_out,A == 0.0`, and the 1 000-feed sweep for ν_A ∈ {−3, −5, −7} at X ∈ {1, 0.25, "
    "0.5, 0.75} with nothing refused, `n_out,A == 0.0` at X = 1 and RX-mole:A within 1e-12 of "
    "its term scale.",
    "A11": "Separator cases SEP-1…4, Z, F2 (`test_t05_separator.separator`) and SEP-S1: status, "
    "code, signature exact; duty to 1.01e-3 W; both outlets' flows and T to §14 and P exactly; "
    "no work, extent or transferred duty.",
    "A12": "Exchanger cases HX-1…5, Z0, Z1, F1…F4 (`test_t05_exchanger.exchanger`) and HX-S1: "
    "status, code, signature exact; no duty (no energy port); the transferred duty and both "
    "outlets to §14 (P exactly); `assess`'s full list of failed checks equals "
    "`ref…expected.failures` — each failure case fails exactly its registered check and passes "
    "every other — with the assessed duty, terminal differences and outlets as registered.",
    "A13": "Metamorphic identities on the implementation, with the measured differences: PHF-2's "
    "T within 1e-6 K of 360 K and its split within 3.1e-8 mol/s of K02's TP flash at 360 K (whose "
    "duty is the registered one); PHF-7 and VLV-2 agree in T, split, signature and P; RX-7's duty "
    "equals K02's `TPHeater` duty on the same stream to 1.01e-3 W, with the same outlet; HX-2 "
    "and HX-3 agree with HX-1 to §14.",
    "A14": "Exact limits: §14's exact zeros (RX-6, RX-8 `n_A`; PHF-5 `n_B` in both products; "
    "SEP-2 `n_top,C`) are `== 0.0`; PHF-6 takes the saturation route; every dormant case "
    "(PHF-Z0, VLV-Z, PUMP-Z, RX-Z, SEP-Z, HX-Z0, and SEP-3/4's dormant outlets) returns its "
    "zero-flow outlets at the registered label exactly with duty, work, extent and transferred "
    "heat `== 0.0`, and PHF-Z1 and HX-Z1 their registered typed errors.",
    "A15": "Dormant singularity: at the registered dormant states (VLV-Z, PHF-Z0, RX-Z in both "
    "energy modes, PUMP-Z, SEP-Z, HX-Z0 with its hot side dormant), the Jacobian column of each "
    "temperature listed in `ref.dormant_temperature_columns` is nonzero in exactly the listed "
    "rows (an empty list: a zero column).",
    "A16": "Every registered failure case (`ref.unit_cases` not `ok`) run through its unit and "
    "every construction case (`ref.specification_errors`) built: the message's first line is "
    "the registered code byte for byte and matches exactly one code of spec §13.3; four "
    "constructed changes to registered cases reach the four codes no registered case reaches, "
    "so all 26 catalogued codes are produced (22 by registered cases). Every numeric "
    "constructor input × {nan, +inf, -inf} is refused at construction with its registered code "
    "or `ValueError` (spec §3.5, §5.1 as amended).",
    "A17": "C1 (pressure chain: pump, valve, PH flash) through `bind_revision_flowsheet` → "
    "`plan_revision` → `execute_plan` under policy `T05-W13` (`test_t05_coupled.solve`): "
    "`CONVERGED` in one `solve_eo` step and one attempt from `traversal-G0-v1`; every solver "
    "column mapped to `ref.coupled_cases.SYN-001-UL-C1` and every registered stream coordinate, "
    "duty and work a solver column; the worst `|x − x_ref|` per kind (at full registered "
    "precision) within §11.5's allowance (3.1e-7 mol/s, 1e-5 K, 0.1 Pa, 1e-2 W); the unit phase "
    "signature the twin's.",
    "A18": "C2 (reaction with recycle: mixer, reactor, separator) as A17, against "
    "`ref.coupled_cases.SYN-001-UL-C2`, the reactor's extent `U-RX.xi` included among the "
    "compared columns.",
    "A19": "C3 (thermally coupled recycle: exchanger, PH flash) as A17, against "
    "`ref.coupled_cases.SYN-001-UL-C3`, with `U-PHF`'s regime `TWO_PHASE`.",
    "A20": "C3X: the plan's path ends `INITIALIZATION_FAILED` with "
    "`initializer_failed(U-HX): temperature_cross(cold_end)` (and `initial_state` returns that "
    "typed refusal); the second accepted branch, exercised from the twin's state as W12 does "
    "(region solve `CONVERGED`), is `FAILED` with exactly "
    "`{bounds_and_domain.U-HX.cold_end}` failing at +10 K within 1e-5 K, judged at the solve's "
    "final state and at the twin's. Never `VERIFIED`.",
    "A21": "C1–C3's certificates from `verify_revision` on the actual solves "
    "(`test_t05_certificates.certify`): `VERIFIED`, no limitation, no false success; every check "
    "`pass`, none `near_threshold`, the worst two- and one-sided ratios below 1/10; the §12.2 ids "
    "of the case exactly and in §4.3's order (`TABLE_IDS`; C3's includes "
    "`energy_balance.U-SPLIT`), every residual row, the plan's aliases and the two witness "
    "checks; [A09] on exactly the energy, admissibility and independent-split checks, ADR 0011 "
    "D2's note on C2's reactor and envelope energy checks; the solution-error bound recomputed "
    "with the exact `‖Ĵ⁻¹‖₁` (dense inverse of the target Jacobian at the final state) times "
    "`‖F̂‖∞` at most 1e-8, and the recorded estimate never above it.",
    "A22": "INJ-T1…T4 on `test_t05_w12_injections`' mini-revisions, the state from a real solve "
    "(INJ-T2 from the twin's HX-F1 state) then injected, judged by `verify_revision(..., "
    "state=injected)`: `FAILED` with `false_success_detected`; the registered failing checks "
    "among the failures, each at `ref.injections`' value to §14's tolerance and at least 10³ τ; "
    "the full failing set recorded; the 'what passes' checks (the unit's rows and material "
    "balances for INJ-T1; the exchanger's rows, balances, specification, cold end and heat flow "
    "for INJ-T2; the reactor's energy balance, dew admissibility and independent split, with "
    "moles and mass conserved, for INJ-T3; the pump's energy balance for INJ-T4) passing.",
    "A23": "Bit identity of SYN-001 (ADR 0011 D3), each item against `docs/t05-measurements.md` "
    "W0.1, recorded before any T05 edit: (i) `thermo/syn001.py` byte-identical to `git show "
    "279b2eb:` and its SHA-256 W0.1's; (ii) K02–T04's tests unchanged — `git diff 279b2eb -- "
    "tests/` adds only `tests/test_t05_*.py` and `tests/t05_*.py`, and changes exactly the two "
    "sanctioned files (spec §21's registry vocabulary in `test_schemas_p01.py`, the added "
    "structural-rank test in `test_k04_regularity.py`), with no line removed — and the gate "
    "passes every collected test, K02's to T05's families among them; (iii) K05's "
    "`structural_sha256` locally and on the CI pair; (iv) `CheckPolicy().sha256`; (v) the "
    "SHA-256 of `repr(syn001_lifted_splits(('A','B','C')))`; (vi) the fixture tree digest (78 "
    "files) and every fixture R-015's generators (K03, K04, K05, T04) emit today equal to the "
    "committed file; and the K05 identity document less its `t05` key equal to W0.1's whole "
    "document. Without `--identities` the CI half is not measured and the check is "
    "`unsupported`.",
    "A24": "R0 identity of C1–C3 and of C3X's failure trace (`scripts/t05_identity.py`, carried "
    "by `k05_structural_identity.py` under `t05`): the four cases; no float anywhere; every "
    "64-hex digest under a declared-input key (`constants_sha256`, `model_version`, "
    "`variable_ids_sha256`) and every float-shaped string a declared constant (the plan's "
    "bounds and scales, T03's δ_root) or an identifier; each case's message the first line of "
    "its typed message (C1–C3 empty, C3X `initializer_failed(U-HX): "
    "temperature_cross(cold_end)`); the same twice in one process. From the two CI artifacts: "
    "the x86-64 and aarch64 `identity.json` equal key for key — the `identity` job's comparison "
    "— with `t05` equal to each other and to this machine's. Without `--identities` that half "
    "is not measured and the check is `unsupported`.",
    "A25": "The registry (`benchmarks/registry.yaml`, which has no JSON schema): family "
    "`SYN-001-UL` with spec §21's fields (kind, derivation and specification this spec, ADR "
    "0001 and 0011 semantics, components, no oracle, the reference YAML with its SHA-256, "
    "`SYN-001-ref-v1`) and SYN-001's domain, tolerances, scales and budgets; exactly the four "
    "cases, each revision valid against `process-revision.schema.json` and bound, reference "
    "hash and key resolving; C1–C3 `oracle_values` in the success denominator, C3X "
    "`typed_failure_or_failed_certificate` outside it with exactly A20's two accepted outcomes.",
    "A26": "Phase contract: the lifted-split descriptors discovered on C1–C3's bindings equal "
    "§12.3's field by field (`test_t05_w12_discovery.DESCRIPTORS`); the converged roots' "
    "fingerprints list `branch_found` = `[[U-HEAT, LIQUID], [U-VLV, TWO_PHASE], [U-PHF, "
    "TWO_PHASE]]`, `[[U-RX, LIQUID]]`, `[[U-PHF, TWO_PHASE]]`, in declaration order.",
    "A27": "PTC (`eo_core = ptc`) over C1–C3's regions, which contain T05 `holdup_balance` rows: "
    "the region solve from the traversal's start and the plan end to end both end "
    "`PTC_MAPPING_INVALID`, `ptc_mapping_invalid(row, missing)` naming the first unmapped T05 "
    "row, with no attempt, no event and no residual or Jacobian call on any compiled problem "
    "(spied).",
    "A28": "§19 Q4 registered (§4.7 (a); ruling round Q-R4): W0.8's two mini-flowsheets "
    "(`test_t05_dormant_outlet.CASES`: a dormant `(0, 0, 0)` feed at 330 K and P_r into C1's "
    "`U-VLV` at 9e4 Pa, and into C1's `U-PHF` at Q = 0, ΔP = 0) through `plan_revision` → "
    "`execute_plan` (policy `T05-W13`) → `verify_revision`. Per flowsheet: (1) `CONVERGED`, "
    "attempt iterations [0], no Jacobian call; (2) every flow column `== 0.0`, every outlet T "
    "`== 330.0`, `U-PHF.Q == 0.0`; (3) in the 18 × 18 target Jacobian at the root exactly the "
    "three equilibrium rows (`U-VLV:VLV-equilibrium:{A,B,C}`, `U-PHF:PHF-equilibrium:{A,B,C}`) "
    "are all zero, K04's screen `RANK_DEFICIENT` at rank 15; "
    "(4) the certificate `UNVERIFIED` with limitations exactly [`rank_limitation` "
    "`RANK_DEFICIENT`] and no failing check; (5) `branch_found` [[U, TWO_PHASE]] and "
    "`phase_branch` `ZERO_FLOW` on every stream. Never `VERIFIED`.",
    "A29": "The near-pure PH kernel (§4.4; ruling round Q-R1): `ph_state` at P_r on (ε, 2, 0) "
    "and (0, 2, ε), ε in {2e-12, 1e-9}, targets 12 000 + φ · 60 000 W, φ in {0.1, 0.3, 0.5, 0.7, "
    "0.9} (20 calls): each answer `ok` with |f| ≤ 1.01e-3 W, |T* − 360 K| ≤ 1e-6 K and "
    "|V − 2φ| ≤ 1e-7 mol/s, or `not_converged`/`ph_ill_conditioned` with no temperature and no "
    "split; at least one of each; the closed forms H_L = 12 000 W and 2 L_B = 60 000 W are the "
    "provider's; the pinned regression pattern (`ok` exactly at φ = 0.5, every refused |f| ≥ "
    "2.6e-2 W) with the smallest refused |f| measured; the control ε = 1e-6: all ten `ok`, "
    "T* strictly increasing in φ, within 1e-4 K and 1e-7 + 3ε mol/s. The check also carries the "
    "ruling's build-lane acceptance for the saturation route's own budget: as first ruled, "
    "PHF-6's inputs with `max_evaluations = 5` → `ph_not_converged`, unmeetable because PHF-6's "
    "T_sat is the domain's midpoint (measured at budgets 1–5 and 200); the replacement the "
    "design lane ratified (pure B at 1.5e5 Pa: budgets 5 and 52 → `ph_not_converged` with no "
    "evaluation of f, 53 → `ok`) with PHF-6's pattern pinned positively (1, 2 → "
    "`ph_not_converged`; 3 and above → `ok` at 360 K). That sub-item passes when the first "
    "acceptance holds, or when `docs/briefs/T05-rulings.md` §4 Q-R1 records the replacement (the "
    "section names 1.5e5 Pa; the excerpt is recorded), the replacement holds and PHF-6's pattern "
    "holds; `grid_items_1_to_3_hold` shows the rest separately.",
    "A30": "A single flowing component in the jump on the EO path (§4.7 (b); ruling round Q-R8), "
    "`test_t05_single_component_eo`'s P3 (feed (0, 2, 0), 370 K, 1.8e5 Pa → C1's `U-VLV` at "
    "P_r) and P4 (PHF-6's inputs → C1's `U-PHF`, Q = 42 000 W): (1) the bound units' causal "
    "answers — P3 `ok`, route saturation, `TWO_PHASE`, T = 360 K to 1e-6 K, β = 2 016/60 000 to "
    "1e-10; P4 PHF-6's registered status, signature, route, T, β, duty and flows; (2) "
    "`plan_revision` → `execute_plan` → (if `CONVERGED`) `verify_revision` is never `VERIFIED`, "
    "with the measured outcomes P3 `ACTIVE_SET_CYCLING` and P4 `BOUND_BLOCKED` compared as "
    "regression values; (3) the control, P4 with 1e-6 mol/s of A, ends `CONVERGED`.",
}


#: What may differ between the measured commit and the CI run's head commit: this generator and
#: the evidence it writes, neither of which the CI jobs' tests or identity document import.
_EVIDENCE_ONLY = re.compile(r"^(scripts/t05_evidence_manifest\.py|evidence/.*)$")


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
        "nor its identity document import; this machine's `t05` identity at the measured commit "
        "is compared with both artifacts in A24 (`t05_equal_to_this_machines`), and the gate "
        "recorded in `commands` ran at the measured commit."
    )


def build(
    commit: str,
    gate_stdout: Path,
    identities: Path | None,
    ci_run: str | None,
    ci_commit: str | None = None,
) -> dict[str, Any]:
    from k05_structural_identity import identity as k05_identity

    ref = reference(REFERENCE)
    with tempfile.TemporaryDirectory() as scratch:
        # The generator's two builds run beside everything below.
        generator = Generator.start(Path(scratch))
        gate = _gate(gate_stdout)
        runs = Runs()
        identity_document = k05_identity()
        checks: list[dict[str, Any]] = []

        def add(identifier: str, measure: Callable[[], tuple[bool, Any, Any]]) -> None:
            checks.append(measured(f"T05.{identifier}", DESCRIPTIONS[identifier], measure))

        add("A01", lambda: _a01(ref))
        add("A02", lambda: _a02(ref))
        add("A03", lambda: _a03(ref))
        add("A04", lambda: _a04(ref))
        add("A05", lambda: _a05(ref))
        add("A06", lambda: _a06(ref))
        add("A07", lambda: _a07(ref))
        add("A08", lambda: _a08(ref))
        add("A09", lambda: _a09(ref))
        add("A10", lambda: _a10(ref))
        add("A11", lambda: _a11(ref))
        add("A12", lambda: _a12(ref))
        add("A13", lambda: _a13(ref))
        add("A14", lambda: _a14(ref))
        add("A15", lambda: _a15(ref))
        add("A16", lambda: _a16(ref))
        add("A17", lambda: _a17(runs, ref))
        add("A18", lambda: _a18(runs, ref))
        add("A19", lambda: _a19(runs, ref))
        add("A20", lambda: _a20(runs, ref))
        add("A21", lambda: _a21(runs, ref))
        add("A22", lambda: _a22(ref))
        checks.append(_a23(identity_document, identities, gate))
        checks.append(_a24(identity_document, identities))
        add("A25", lambda: _a25(ref))
        add("A26", lambda: _a26(runs, ref))
        add("A27", lambda: _a27(ref))
        checks.extend(retired(identifier) for identifier in RETIRED)
        # A00 last in time (its builds ran beside the rest), first in the list.
        checks.insert(0, measured("T05.A00", DESCRIPTIONS["A00"], lambda: _a00(generator, ref)))

    if [entry["id"] for entry in checks] != [f"T05.{identifier}" for identifier in ASSERTIONS]:
        raise SystemExit("the checks are not one per T05.A00…T05.A30, in order")
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
            "docs/derivations/scripts/t05_reference.py --check --emit A_YAML",
            "cwd": ".",
            "exit_code": int(a00.get("check_exit_code", 1)) if isinstance(a00, dict) else 1,
        },
        {
            "cmd": "PYTHONPATH=. .venv/bin/python scripts/t05_evidence_manifest.py "
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
        "work_package": "T05",
        "commit": commit,
        # The frozen schema takes D/A requirement ids only; V12 is a verification item of plan
        # §5, carried in `docs/requirements.yaml`.
        "requirements": requirements,
        "status": _status(checks),
        "inputs": {
            "case_id": "The six T05 unit models' registered unit cases, specification errors and "
            "trial states; the dormant temperature columns; the coupled cases SYN-001-UL-C1, "
            "-C2, -C3 and the adversarial -C3X (benchmarks/t05/cases); the injections "
            "INJ-T1..T4 (A28–A30 retired by ADR 0012, not re-measured); judged against "
            f"benchmarks/t05/reference_values.yaml ({file_sha256(REFERENCE)}), "
            f"docs/derivations/T05-unit-models-spec.md ({file_sha256(SPEC)}) and the W0.1 "
            "inertness baseline of docs/t05-measurements.md",
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
    schema_errors = _errors(_validator("evidence-manifest.schema.json"), manifest)
    destination = arguments.out or (ROOT / "evidence" / "T05" / arguments.commit / "manifest.json")
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
    if schema_errors:
        print(f"the manifest has {schema_errors} evidence-manifest schema errors")
    return 1 if counts["fail"] or placeholders or schema_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
