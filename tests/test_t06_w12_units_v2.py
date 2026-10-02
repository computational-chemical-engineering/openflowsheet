"""T06 W12: `unit-conversion-v2` (ADR 0016; T06 spec §8.5 as amended by A2; register R-077).
Assertions A67–A74.

The expectation is the twin's, not ours: `ref.closed_form.unit_conversion_v2` gives the table
(ADR 0016 D3), each row's known answer as a bit pattern at the first operand where a naive binary64
chain differs, the refusals, the invariance groups and the 23 metamorphic pairs, each of which binds
to its registered SI twin's value. A converted revision is compared with that twin bit for bit (its
binding) and byte for byte (its trace and certificate).

**In-test mutations of a bounded parameter.** A Quantity's `bounds` are in its `unit`, so writing
a parameter "in `%`" writes its bounds in `%` too (`[0, 1]` becomes `[0, 100]`): otherwise the
mutation would be a different Quantity, whose SI twin (`[0, 0.01]`) refuses its own value
(`_in_unit`, which asserts the rewritten bounds convert back to the registered ones bit for bit).
**(A3)** Ratified (spec A3.7, ADR 0016 D1.1–D1.2): the mutation writes the whole Quantity — value,
bounds and `nominal` when it has one — in the new unit, each round-tripping bit for bit.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from fractions import Fraction
from functools import cache
from math import copysign
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_support import T06_REVISION_POLICY
from test_t04_edge3 import plan_run, region_step
from test_t05_w11_cases import _instance, shaped_revision
from test_t06_w5_corpus import _spy

from openflowsheet.application.binding import Binding, Unbound, bind_revision_or_reason
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.validation import ValidationReport, validate
from openflowsheet.canonical import canonical_json
from openflowsheet.graph.analysis import analyse
from openflowsheet.models.revision_flowsheet import (
    MOLECULAR_WEIGHTS,
    parse_revision,
    pin_specifications,
    required_kind,
)
from openflowsheet.orchestrator.execution import ExecutionPlan, declaration_identity
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.units import (
    CONVERSION_ROWS,
    FRACTION_PARAMETERS,
    KIND_SI_UNITS,
    UNIT_CONVERSION_ID,
    UnitConversion,
    UnitConversionError,
    convert_input_value,
)
from openflowsheet.verify.certificate import verify, verify_bound, verify_revision

Document = dict[str, Any]

REFERENCE = load_yaml(REPO_ROOT / "benchmarks" / "t06" / "reference_values.yaml")
UNITS = REFERENCE["closed_form"]["unit_conversion_v2"]
ANSWERS = UNITS["known_answers"]
#: v1's synthetic table of distinct molecular weights, which the v2 known answers reuse.
SYNTHETIC = REFERENCE["closed_form"]["unit_conversion_v1"]["synthetic_molar_mass_kg_per_mol"]

CASE_FILES = {
    "SYN-001-nominal": REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml",
    "SYN-001-A02-360": REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-A02-360.yaml",
    "SYN-001-UL-C1": REPO_ROOT / "benchmarks" / "t05" / "cases" / "SYN-001-UL-C1.yaml",
    "SYN-001-UL-C2": REPO_ROOT / "benchmarks" / "t05" / "cases" / "SYN-001-UL-C2.yaml",
    "SYN-001-UL-C3": REPO_ROOT / "benchmarks" / "t05" / "cases" / "SYN-001-UL-C3.yaml",
    "SYN-001-T06-STR06": REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-STR06.yaml",
    "SYN-001-T06-THM10": REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-THM10.yaml",
    "SYN-001-T06-NET06": REPO_ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-NET06.yaml",
}

#: The seven values `Syn001Flowsheet` is parameterized by.
SETTINGS = (
    "components",
    "feed_flows",
    "feed_temperature",
    "pressure",
    "heater_temperature",
    "flash_temperature",
    "split_fraction",
)


@cache
def _load(case: str) -> Document:
    loaded: Document = load_yaml(CASE_FILES[case])
    return loaded


def document(case: str) -> Document:
    return copy.deepcopy(_load(case))


def specification(revision: Document, name: str) -> Document:
    entry: Document
    (entry,) = (s for s in revision["specifications"] if s["id"] == name)
    return entry


def parameter(revision: Document, where: str) -> Document:
    unit, _, name = where.partition(".")
    quantity: Document = _instance(revision, unit)["parameters"][name]
    return quantity


def _in_unit(quantity: Document, value: float, unit: str, required: str) -> None:
    """Write a parameter Quantity in `unit`: its value, and its bounds and `nominal` (when it has
    one) rewritten in the same unit (the exact inverse of the row's scale), each of which converts
    back to the registered one bit for bit (spec A3.7).
    """
    row = CONVERSION_ROWS[(required, unit)]
    assert row.b == 0

    def rewritten(registered: float) -> float:
        written = float(Fraction(repr(registered)) / row.a)
        assert float(row.a * Fraction(repr(written))).hex() == registered.hex()
        return written

    bounds = quantity.get("bounds") or {}
    for side in ("lower", "upper"):
        if bounds.get(side) is not None:
            bounds[side] = rewritten(float(bounds[side]))
    if quantity.get("nominal") is not None:
        quantity["nominal"] = rewritten(float(quantity["nominal"]))
    quantity.update(value=value, unit=unit)


def checks(report: ValidationReport) -> dict[str, Any]:
    return {check.id: check for check in report.checks}


def bits(value: Any) -> Any:
    """A value with every float as its bit pattern, so equality is bit for bit."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, tuple | list):
        return [bits(item) for item in value]
    return value


def events(trace: Trace) -> tuple[bytes, ...]:
    return tuple(canonical_json(event.as_document()) for event in trace.events)


def legacy(revision: Document) -> Binding:
    binding = bind_revision_or_reason(revision)
    assert isinstance(binding, Binding), binding
    return binding


def revision_bound(revision: Document) -> RevisionBinding:
    binding = bind_revision_flowsheet(revision)
    assert isinstance(binding, RevisionBinding), binding
    return binding


def _target(unit: str) -> tuple[str, str, str | None]:
    """(required kind, target path, component) of an invariance group's spelling."""
    if unit in ("degC", "degF", "K"):
        return "temperature", "state.T", None
    if unit in ("%", "1"):
        return "dimensionless", "parameters.efficiency", None
    if unit in ("kPa", "bar", "MPa", "Pa"):
        return "pressure", "state.P", None
    return "molar_flow", "state.n", "A"


# -- A67: the known answers -----------------------------------------------------------------------


def test_a67_the_table_is_the_registered_one() -> None:
    registered = {
        (row["required_kind"], row["unit"]): (
            row["rule"],
            Fraction(row["a"]),
            Fraction(row["b"]),
            frozenset(row["declared_kinds"]),
            row["target_class"],
        )
        for row in UNITS["rows"]
    }
    assert {
        key: (row.rule, row.a, row.b, row.declared_kinds, row.target_class)
        for key, row in CONVERSION_ROWS.items()
    } == registered
    assert set(UNITS["fraction_parameters"]) == FRACTION_PARAMETERS
    assert CONVERSION_ROWS[("pressure", "psi")].a == Fraction(UNITS["psi_Pa_exact"])
    assert UNIT_CONVERSION_ID == UNITS["id"] == "unit-conversion-v2"


@pytest.mark.parametrize(
    "answer",
    ANSWERS["rows"],
    ids=lambda answer: f"{answer['required_kind']}:{answer['unit']}",
)
def test_a67_every_row_known_answer(answer: dict[str, Any]) -> None:
    value, record = convert_input_value(
        "X",
        float(answer["value"]),
        answer["unit"],
        answer["declared_kinds"][0],
        answer["required_kind"],
        answer["target"],
        answer["component"],
        MOLECULAR_WEIGHTS,
    )
    assert value.hex() == float.fromhex(answer["si_value_hex"]).hex()
    assert record is not None
    assert (record.rule, record.si_unit, record.si_value.hex()) == (
        answer["rule"],
        answer["si_unit"],
        value.hex(),
    )
    assert record.value == float(answer["value"]) and record.unit == answer["unit"]
    if answer["rule"] == "mass_to_molar":
        assert (record.component, record.molar_mass) == (
            answer["component"],
            MOLECULAR_WEIGHTS[answer["component"]],
        )
    else:
        assert (record.component, record.molar_mass) == (None, None)


@pytest.mark.parametrize(
    "answer",
    ANSWERS["v1_known_answers_under_v2"],
    ids=lambda answer: f"{answer['value']}-{answer['unit']}-{answer.get('component', '')}",
)
def test_a67_v1_known_answers_take_the_decimals_value(answer: dict[str, Any]) -> None:
    mass = answer["unit"] == "kg/s"
    table = SYNTHETIC if answer.get("molar_mass_table") == "synthetic" else MOLECULAR_WEIGHTS
    value, _ = convert_input_value(
        "X",
        float(answer["value"]),
        answer["unit"],
        "molar_flow" if mass else "temperature",
        "molar_flow" if mass else "temperature",
        "state.n" if mass else "state.T",
        answer.get("component"),
        table,
    )
    assert value.hex() == float.fromhex(answer["v2_hex"]).hex()


def test_a67_the_synthetic_masses_separate_the_components() -> None:
    results = [
        convert_input_value(
            "X", 0.3, "kg/h", "molar_flow", "molar_flow", "state.n", component, SYNTHETIC
        )[0].hex()
        for component in ("A", "B", "C")
    ]
    registered = [float.fromhex(hex_).hex() for hex_ in ANSWERS["synthetic_mass_kg_per_h_0p3"]]
    assert results == registered
    assert len(set(results)) == 3


def test_a67_a_negative_zero_converts_to_positive_zero() -> None:
    value, record = convert_input_value(
        "X", -0.0, "kg/s", "molar_flow", "molar_flow", "state.n", "A", MOLECULAR_WEIGHTS
    )
    assert value == 0.0 and copysign(1.0, value) == 1.0
    assert record is not None and copysign(1.0, record.si_value) == 1.0


@pytest.mark.parametrize(
    "group", ANSWERS["invariance_groups"], ids=lambda group: "|".join(group["inputs"])
)
def test_a67_every_spelling_of_one_quantity_binds_to_one_double(group: dict[str, Any]) -> None:
    results = set()
    for spelling in group["inputs"]:
        text, unit = spelling.split(" ")
        required, target, component = _target(unit)
        value, _ = convert_input_value(
            "X", float(text), unit, required, required, target, component, MOLECULAR_WEIGHTS
        )
        results.add(value.hex())
    assert results == {float.fromhex(group["si_value_hex"]).hex()}


# -- the steps V0-V5 (ADR 0016 D4) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("unit", "kind", "required", "target", "component", "expected"),
    [
        # V3: already SI, no record.
        ("K", "temperature", "temperature", "state.T", None, 300.0),
        ("mol/s", "molar_flow", "molar_flow", "state.n", "A", 300.0),
        # V1: a path no table names — identity iff the declared kind's SI unit.
        ("W", "heat_rate", None, "work.W", None, 300.0),
        ("degC", "temperature", None, "work.W", None, "unit"),
        ("W", "no_such_kind", None, "work.W", None, "unit"),
        # V2: the declared kind must be the target's (or the mass basis of one component).
        ("K", "temperature", "molar_flow", "state.n", "A", "kind"),
        ("kg/s", "mass_flow", "molar_flow", "state.n", None, "kind"),
        ("K", "temperature_difference", "temperature", "state.T", None, "kind"),
        # V5: a row that does not admit the declared kind or the target, or no row.
        ("kmol/h", "mass_flow", "molar_flow", "state.n", "A", "unit"),
        ("kmol/h", "molar_flow", "molar_flow", "state.n", None, "unit"),
        ("kg/s", "molar_flow", "molar_flow", "state.n", None, "unit"),
        ("%", "dimensionless", "dimensionless", "parameters.nu.A", None, "unit"),
        ("%", "dimensionless", "dimensionless", "parameters.efficiencyX", None, "unit"),
        ("bara", "pressure", "pressure", "state.P", None, "unit"),
        ("KPA", "pressure", "pressure", "state.P", None, "unit"),
    ],
)
def test_the_steps_in_order(
    unit: str,
    kind: str,
    required: str | None,
    target: str,
    component: str | None,
    expected: Any,
) -> None:
    arguments = (unit, kind, required, target, component, MOLECULAR_WEIGHTS)
    if isinstance(expected, str):
        with pytest.raises(UnitConversionError) as refused:
            convert_input_value("X", 300.0, *arguments)
        assert refused.value.reason == expected
        with pytest.raises(UnitConversionError):
            convert_input_value("X", None, *arguments)
    else:
        assert convert_input_value("X", 300.0, *arguments) == (expected, None)
        assert convert_input_value("X", None, *arguments) == (None, None)


def test_a_free_start_is_checked_and_stays_absent() -> None:
    assert convert_input_value(
        "X", None, "degF", "temperature", "temperature", "state.T", None, MOLECULAR_WEIGHTS
    ) == (None, None)


# -- A68: refusals --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "refusal",
    ANSWERS["refusals"],
    ids=lambda r: f"{r['value']}-{r['unit']}-{r['declared_kind']}-{r['target']}-{r['component']}",
)
def test_a68_every_registered_refusal_in_the_pure_function(refusal: dict[str, Any]) -> None:
    with pytest.raises(UnitConversionError) as refused:
        convert_input_value(
            "X",
            float(refusal["value"]),
            refusal["unit"],
            refusal["declared_kind"],
            refusal["required_kind"],
            refusal["target"],
            refusal["component"],
            MOLECULAR_WEIGHTS,
        )
    assert refused.value.reason == refusal["reason"]


#: A68 through the readers, on SYN-001-nominal: (specification, changes, code).
NOMINAL_REFUSALS: list[tuple[str, dict[str, Any], str]] = [
    *[
        ("SPEC-feed-T", {"unit": unit}, "specification_unit_unsupported(SPEC-feed-T)")
        for unit in ("°C", "C", "degc")
    ],
    *[
        ("SPEC-feed-P", {"unit": unit}, "specification_unit_unsupported(SPEC-feed-P)")
        for unit in ("barg", "psig", "psia", "mmHg", "degF")
    ],
    (
        "SPEC-feed-P",
        {"value": 1e306, "unit": "kPa"},
        "specification_value_unsupported(SPEC-feed-P)",
    ),
    ("SPEC-feed-n-A", {"unit": "K"}, "specification_unit_unsupported(SPEC-feed-n-A)"),
    (
        "SPEC-feed-n-A",
        {"kind": "mass_flow", "unit": "mol/s"},
        "specification_unit_unsupported(SPEC-feed-n-A)",
    ),
    (
        "SPEC-feed-n-A",
        {"kind": "temperature", "unit": "kg/s"},
        "specification_kind_unsupported(SPEC-feed-n-A)",
    ),
]


@pytest.mark.parametrize(
    ("name", "changes", "code"),
    NOMINAL_REFUSALS,
    ids=[f"{name}-{'-'.join(map(str, changes.values()))}" for name, changes, _ in NOMINAL_REFUSALS],
)
def test_a68_a_refusal_through_every_reader(
    name: str, changes: dict[str, Any], code: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = document("SYN-001-nominal")
    specification(revision, name).update(changes)
    calls = _spy(monkeypatch)
    report = validate(revision)
    assert report.status == "INVALID"
    found = checks(report)["DIM-01"]
    assert bind_revision_or_reason(revision) == Unbound("unsupported", code, (name,))
    refused = bind_revision_flowsheet(revision)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", code)
    # T07 ruling round 6, B2: DIM-01 reports the code with its hint, the binders' own (the kind
    # and unit refusals have one; `specification_value_unsupported` has none).
    assert (refused.hint is None) == code.startswith("specification_value_unsupported")
    assert bind_revision_or_reason(revision).hint == refused.hint  # type: ignore[union-attr]
    message = code if refused.hint is None else f"{code}. {refused.hint}"
    assert (found.result, found.message, found.implicated_objects) == ("FAIL", message, (name,))
    assert calls == []


@pytest.mark.parametrize(
    ("name", "value"), [("SPEC-feed-T", float("nan")), ("SPEC-feed-P", float("inf"))], ids=repr
)
def test_a68_a_nonfinite_value_is_refused_at_entry(
    name: str, value: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A68's NaN and infinity rows. V0 still refuses them (`specification_value_unsupported`, the
    pure function's rows above), but a non-finite number has no canonical JSON form, so
    `validate()` and both bindings refuse the document at entry, naming the node, before a reader
    runs (T07 §12.5, R-088 Q29). Superseded pending the design lane's ruling (T07 W2d)."""
    revision = document("SYN-001-nominal")
    specification(revision, name)["value"] = value
    (index,) = [k for k, s in enumerate(revision["specifications"]) if s["id"] == name]
    code = f"document_not_canonical(/specifications/{index}/value)"
    calls = _spy(monkeypatch)
    report = validate(revision)
    assert report.status == "INVALID"
    (found,) = report.checks
    assert (found.id, found.result, found.message, found.implicated_objects) == (
        "SCHEMA-01",
        "FAIL",
        code,
        (f"/specifications/{index}/value",),
    )
    assert bind_revision_or_reason(revision) == Unbound("unsupported", code)
    assert bind_revision_flowsheet(revision) == Unbound("unsupported", code)
    assert calls == []


def test_a68_percent_on_a_stoichiometric_coefficient_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2's `U-RX.nu.A` in `%`: a stoichiometric coefficient is not a fraction (ADR 0016 D8).
    The legacy binding knows only SYN-001's topology and refuses C2 before reading a parameter,
    so this row runs through `validate()` and the revision binding."""
    revision = document("SYN-001-UL-C2")
    parameter(revision, "U-RX.nu.A")["unit"] = "%"
    code = "parameter_unit_unsupported(U-RX.nu.A)"
    calls = _spy(monkeypatch)
    found = checks(validate(revision))["DIM-01"]
    assert (found.result, found.message, found.implicated_objects) == (
        "FAIL",
        code,
        ("U-RX.nu.A",),
    )
    refused = bind_revision_flowsheet(revision)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", code)
    assert calls == []


# -- the metamorphic pairs (A69, A70) -------------------------------------------------------------


def _pair_id(pair: dict[str, Any]) -> str:
    return f"{pair['case']}:{pair['input']}={pair['value']}{pair['unit']}"


def pair_record(pair: dict[str, Any]) -> UnitConversion:
    """The record a pair's conversion must yield (ADR 0016 D6)."""
    mass = pair["rule"] == "mass_to_molar"
    return UnitConversion(
        source=pair["source"],
        input_id=pair["input"],
        value=float(pair["value"]),
        unit=pair["unit"],
        si_value=float.fromhex(pair["si_value_hex"]),
        si_unit=KIND_SI_UNITS[pair["required_kind"]],
        rule=pair["rule"],
        component=pair["component"] if mass else None,
        molar_mass=MOLECULAR_WEIGHTS[pair["component"]] if mass else None,
    )


def converted(pair: dict[str, Any]) -> Document:
    """The pair's case with its one input written as the pair writes it."""
    revision = document(pair["case"])
    if pair["source"] == "specification":
        specification(revision, pair["input"]).update(value=float(pair["value"]), unit=pair["unit"])
    else:
        _in_unit(
            parameter(revision, pair["input"]),
            float(pair["value"]),
            pair["unit"],
            pair["required_kind"],
        )
    return revision


def twin(pair: dict[str, Any]) -> Document:
    """The pair's SI twin: its case with the input at the pair's `registered_si_value`, in SI.

    A70 as amended (A3.5) compares every pair with this twin, not with its case document. For 18 of
    the 23 pairs the twin is the registered case document unchanged; for exactly five parameter
    pairs it is not, by design — C1 efficiency 0.751 (case 0.75), C2 conversion.A 0.51 (0.5),
    split.C 0.051 (0.05), C3 split_fraction 0.61 (0.6), and A71's 2500 Pa drop (0.0). `75.1 %` is
    the pair a binary reading breaks, where C1's own 0.75 would not discriminate; the twin's
    `registered_si_value` is the value the pair must bind to, so the twin is not changed. See
    `test_the_pairs_twins_are_the_registered_cases_but_five`.
    """
    revision = document(pair["case"])
    registered = float(pair["registered_si_value"])
    if pair["source"] == "specification":
        entry = specification(revision, pair["input"])
    else:
        entry = parameter(revision, pair["input"])
    assert entry["unit"] == KIND_SI_UNITS[pair["required_kind"]]
    entry["value"] = registered
    return revision


PAIRS = {_pair_id(pair): pair for pair in ANSWERS["metamorphic_pairs"]}
TEAR_PAIRS = [key for key, pair in PAIRS.items() if pair["case"] == "SYN-001-nominal"]
REVISION_PAIRS = [
    key
    for key, pair in PAIRS.items()
    if pair["case"] not in ("SYN-001-nominal", "SYN-001-A02-360")
    and pair["input"] != "U-RX.pressure_drop"
]


def test_the_pairs_are_the_registered_twenty_three() -> None:
    assert len(PAIRS) == 23
    assert len(TEAR_PAIRS) == 10 and len(REVISION_PAIRS) == 11
    for pair in PAIRS.values():
        assert pair["required_kind"] == required_kind(pair["target"])
        assert float.fromhex(pair["si_value_hex"]) == float(pair["registered_si_value"])


def test_the_pairs_twins_are_the_registered_cases_but_five() -> None:
    """Every specification pair's registered SI value is its case document's; exactly five
    parameter pairs register a value the case does not declare, by design (A70 (A3): each pair is
    compared with its SI twin, the case at the registered SI value; A3.5)."""
    differing = []
    for key, pair in PAIRS.items():
        revision = document(pair["case"])
        if pair["source"] == "specification":
            declared = specification(revision, pair["input"])["value"]
        else:
            declared = parameter(revision, pair["input"])["value"]
        if float(declared) != float(pair["registered_si_value"]):
            differing.append((key, float(declared)))
    assert differing == [
        ("SYN-001-UL-C1:U-PUMP.efficiency=75.1%", 0.75),
        ("SYN-001-UL-C2:U-RX.conversion.A=51.0%", 0.5),
        ("SYN-001-UL-C2:U-SEP.split.C=5.1%", 0.05),
        ("SYN-001-UL-C2:U-RX.pressure_drop=2.5kPa", 0.0),
        ("SYN-001-UL-C3:U-SPLIT.split_fraction=61.0%", 0.6),
    ]


FIVE_OFF_CASE = [
    "SYN-001-UL-C1:U-PUMP.efficiency=75.1%",
    "SYN-001-UL-C2:U-RX.conversion.A=51.0%",
    "SYN-001-UL-C2:U-SEP.split.C=5.1%",
    "SYN-001-UL-C2:U-RX.pressure_drop=2.5kPa",
    "SYN-001-UL-C3:U-SPLIT.split_fraction=61.0%",
]


@pytest.mark.parametrize("key", FIVE_OFF_CASE)
def test_a70_each_of_the_five_si_twins_moves_constants_sha256(key: str) -> None:
    """A70 (A3): the five SI twins are different problems from their cases — each one's
    `constants_sha256` differs from its registered case's — and the converted pair binds to its
    twin's, not its case's."""
    pair = PAIRS[key]
    registered = revision_bound(document(pair["case"]))
    bound_twin = revision_bound(twin(pair))
    constants = declaration_identity(bound_twin.spec)[1]
    assert constants != declaration_identity(registered.spec)[1]
    assert declaration_identity(revision_bound(converted(pair)).spec)[1] == constants


@pytest.mark.parametrize("key", TEAR_PAIRS)
def test_a69_the_legacy_binding_reads_nominal_bit_for_bit(key: str) -> None:
    pair = PAIRS[key]
    revision = converted(pair)
    report = validate(revision)
    assert report.status == "READY_FOR_SIMULATION"
    found = checks(report)["DIM-01"]
    record = pair_record(pair)
    assert found.result == "PASS"
    assert found.implicated_objects == (pair["input"],)
    assert found.message.startswith(f"converted by unit-conversion-v2: {pair['input']} ")
    assert "; " not in found.message
    binding, nominal = legacy(revision), legacy(document("SYN-001-nominal"))
    assert binding.input_mapping.conversions == (record,)
    for setting in SETTINGS:
        assert bits(getattr(binding.flowsheet, setting)) == bits(
            getattr(nominal.flowsheet, setting)
        ), setting
    assert bits(list(binding.spec.parameters.items())) == bits(
        list(nominal.spec.parameters.items())
    )
    assert binding.spec.variable_ids == nominal.spec.variable_ids


@cache
def tear_solved(key: str | None) -> tuple[tuple[bytes, ...], bytes, str]:
    """`solve_tear` (`SYN-001-K03`) + `verify` of nominal, or of a pair's converted nominal."""
    revision = document("SYN-001-nominal") if key is None else converted(PAIRS[key])
    flowsheet = legacy(revision).flowsheet
    result, trace = solve_tear(flowsheet)
    assert result.outcome == "CONVERGED", result.message
    certificate = verify(flowsheet, result)
    return events(trace), canonical_json(certificate.as_document()), certificate.verification_status


@pytest.mark.parametrize(
    "key",
    [
        "SYN-001-nominal:SPEC-feed-n-A=3.6kmol/h",
        "SYN-001-nominal:SPEC-feed-T=80.33degF",
    ],
)
def test_a69_the_tear_solve_and_certificate_are_nominals(key: str) -> None:
    trace, certificate, status = tear_solved(key)
    nominal_trace, nominal_certificate, _ = tear_solved(None)
    assert status == "VERIFIED"
    assert trace == nominal_trace
    assert certificate == nominal_certificate


@cache
def a02_solved(fahrenheit: bool) -> tuple[Binding, tuple[bytes, ...], bytes]:
    """A02-360 on the legacy EO path (the plan's pre-solve and region, `verify_bound`)."""
    revision = (
        converted(PAIRS["SYN-001-A02-360:SPEC-flash-T=188.33degF"])
        if fahrenheit
        else document("SYN-001-A02-360")
    )
    run = plan_run(revision, SolvePolicy(policy_id="T04-W12", residual_tolerances={}, scales={}))
    step = region_step(run.result)
    assert step.outcome == "CONVERGED"
    (planned,) = [s for s in run.plan.steps if s.kind == "solve_eo"]
    binding = legacy(revision)
    certificate = verify_bound(binding, revision, step.detail, solve_plan=planned.solve_plan)
    assert certificate.verification_status == "VERIFIED"
    return binding, events(run.result.trace), canonical_json(certificate.as_document())


def test_a69_control_verify_bound_reads_the_converted_value() -> None:
    """Reader R3: `SPEC-flash-T` `188.33 degF` is 360 K exactly; the binding, the executor trace
    and the `verify_bound` certificate are A02-360's."""
    binding, trace, certificate = a02_solved(True)
    twin, twin_trace, twin_certificate = a02_solved(False)
    pair = PAIRS["SYN-001-A02-360:SPEC-flash-T=188.33degF"]
    assert binding.input_mapping.conversions == (pair_record(pair),)
    assert bits(list(binding.guesses.items())) == bits(list(twin.guesses.items()))
    assert bits(list(binding.spec.parameters.items())) == bits(list(twin.spec.parameters.items()))
    for setting in SETTINGS:
        assert bits(getattr(binding.flowsheet, setting)) == bits(getattr(twin.flowsheet, setting))
    assert trace == twin_trace
    assert certificate == twin_certificate


def assert_binds_as(binding: RevisionBinding, twin: RevisionBinding) -> None:
    """Parameters, label, `configuration_sha256`, `constants_sha256`, `variable_ids`."""
    assert binding.flowsheet.label == twin.flowsheet.label
    assert binding.flowsheet.configuration_sha256 == twin.flowsheet.configuration_sha256
    assert declaration_identity(binding.spec) == declaration_identity(twin.spec)
    assert binding.spec.variable_ids == twin.spec.variable_ids
    assert bits(list(binding.spec.parameters.items())) == bits(list(twin.spec.parameters.items()))


def pins(revision: Document) -> dict[str, Any]:
    """Each instance's pins and parameters as `parse_revision` read them, bit for bit."""
    view = parse_revision(revision)
    return {
        i.unit_id: (bits(list(i.pins.items())), bits(list(i.parameters.items())))
        for i in view.instances
    }


@pytest.mark.parametrize("key", REVISION_PAIRS)
def test_a70_the_revision_binding_reads_the_twin_bit_for_bit(key: str) -> None:
    pair = PAIRS[key]
    revision, twin_revision = converted(pair), twin(pair)
    binding, bound_twin = revision_bound(revision), revision_bound(twin_revision)
    assert binding.input_mapping.conversions == (pair_record(pair),)
    assert bound_twin.input_mapping.conversions == ()
    assert_binds_as(binding, bound_twin)
    assert pins(revision) == pins(twin_revision)
    assert binding.revision_sha256 != bound_twin.revision_sha256


def solved_on_the_revision_path(revision: Document) -> tuple[tuple[bytes, ...], bytes]:
    """Plan, `execute_plan` and `verify_revision` under `T06-revision-v2`: the trace's events and
    the certificate, canonical bytes."""
    policy = T06_REVISION_POLICY
    binding = revision_bound(revision)
    plan, _ = plan_revision(binding, policy)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=policy)
    assert run.outcome == "CONVERGED", run.outcome
    certificate = verify_revision(binding, revision, run, solve_plan=plan.steps[-1].solve_plan)
    assert certificate.verification_status == "VERIFIED"
    return events(run.trace), canonical_json(certificate.as_document())


@pytest.mark.parametrize(
    "key",
    ["SYN-001-UL-C3:U-SPLIT.split_fraction=61.0%", "SYN-001-UL-C1:SPEC-pump-P=180.0kPa"],
)
def test_a70_the_revision_solve_and_certificate_are_the_twins(key: str) -> None:
    pair = PAIRS[key]
    assert solved_on_the_revision_path(converted(pair)) == solved_on_the_revision_path(twin(pair))


def test_a70_the_binary_reading_would_break_a_pair() -> None:
    """`75.1 %` is the pair a binary64 reading breaks: `75.1 / 100` is 0.7509999999999999, not
    the registered 0.751 (`units_v2.the_binary_reading_would_break_a_pair`)."""
    pair = PAIRS["SYN-001-UL-C1:U-PUMP.efficiency=75.1%"]
    assert float(pair["binary_reading_value"]) == 75.1 / 100 != float(pair["registered_si_value"])
    assert pair_record(pair).si_value == 0.751


# -- A71: a nonzero pressure drop -----------------------------------------------------------------


def _c2_drop(value: float, unit: str) -> Document:
    revision = document("SYN-001-UL-C2")
    _in_unit(parameter(revision, "U-RX.pressure_drop"), value, unit, "pressure")
    return revision


def test_a71a_a_nonzero_pressure_drop_in_kpa_binds_as_its_pa_twin() -> None:
    """A71 (a), the binding half, on C2: the `kPa` and `Pa` bindings are equal bit for bit, the
    `kPa` one records exactly the twin's pair record and the `Pa` one none, and the drop reached
    the problem (`constants_sha256` differs from C2's)."""
    pascal = twin(PAIRS["SYN-001-UL-C2:U-RX.pressure_drop=2.5kPa"])
    kilopascal = _c2_drop(2.5, "kPa")
    pa_binding, kpa_binding = revision_bound(pascal), revision_bound(kilopascal)
    assert kpa_binding.input_mapping.conversions == (
        pair_record(PAIRS["SYN-001-UL-C2:U-RX.pressure_drop=2.5kPa"]),
    )
    assert pa_binding.input_mapping.conversions == ()
    assert_binds_as(kpa_binding, pa_binding)
    assert pins(kilopascal) == pins(pascal)
    c2 = revision_bound(document("SYN-001-UL-C2"))
    assert declaration_identity(pa_binding.spec)[1] != declaration_identity(c2.spec)[1]


def _c2_drop_in_pa(value: float) -> Document:
    revision = document("SYN-001-UL-C2")
    parameter(revision, "U-RX.pressure_drop")["value"] = value
    return revision


def _finding(revision: Document) -> str:
    """T01's finding on the revision's declaration, analysed as `plan_revision` analyses it."""
    binding = revision_bound(revision)
    model_version, constants = declaration_identity(binding.spec)
    report = analyse(
        binding.spec,
        binding.graph,
        model_version=model_version,
        constants_sha256=constants,
        specification_ids={},
        row_units=binding.row_units,
    )
    return str(report.finding)


REFUSED_FOR_A_CONFLICT = (
    "an execution plan needs a structurally closed declaration; T01 reports SPECIFICATION_CONFLICT"
)


def test_a71b_c2_refuses_any_nonzero_reactor_drop_before_a_solve() -> None:
    """A71 (b): C2's recycle (mixer → reactor → separator → mixer) has no unit that raises
    pressure, so its pressure rows admit a nonzero reactor drop only by contradiction. T01 reports
    `SPECIFICATION_CONFLICT` at 1 Pa, 2500 Pa and `2.5 kPa` (C2 as registered is
    `STRUCTURALLY_CLOSED`), and `plan_revision` refuses before any solve, with one message for
    both spellings."""
    assert _finding(document("SYN-001-UL-C2")) == "STRUCTURALLY_CLOSED"
    drops = {
        "1.0 Pa": _c2_drop_in_pa(1.0),
        "2500.0 Pa": _c2_drop_in_pa(2500.0),
        "2.5 kPa": _c2_drop(2.5, "kPa"),
    }
    refusals = {}
    for spelling, revision in drops.items():
        assert _finding(revision) == "SPECIFICATION_CONFLICT", spelling
        with pytest.raises(ValueError) as refused:
            plan_revision(revision_bound(revision), T06_REVISION_POLICY)
        refusals[spelling] = str(refused.value)
    assert refusals["2.5 kPa"] == refusals["2500.0 Pa"] == REFUSED_FOR_A_CONFLICT
    assert refusals["1.0 Pa"] == REFUSED_FOR_A_CONFLICT


def _net06_drop(value: float, unit: str) -> Document:
    revision = document("SYN-001-T06-NET06")
    quantity = parameter(revision, "U-PHF.pressure_drop")
    assert quantity.get("bounds") is None and quantity["unit"] == "Pa"
    if unit == "Pa":
        quantity["value"] = value
    else:
        _in_unit(quantity, value, unit, "pressure")
    return revision


@cache
def net06_solved(unit: str) -> tuple[tuple[bytes, ...], bytes, dict[str, float]]:
    """NET-06 with `U-PHF.pressure_drop` 2500.0 Pa or 2.5 kPa: plan, `execute_plan` and
    `verify_revision` under `T06-revision-v2` — the trace's events, the certificate (canonical
    bytes) and the certified state."""
    revision = _net06_drop(2500.0 if unit == "Pa" else 2.5, unit)
    binding = revision_bound(revision)
    plan, _ = plan_revision(binding, T06_REVISION_POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    run = execute_plan(
        plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=T06_REVISION_POLICY
    )
    assert run.outcome == "CONVERGED", (unit, run.outcome, run.message)
    assert run.state is not None
    certificate = verify_revision(binding, revision, run, solve_plan=plan.steps[-1].solve_plan)
    assert certificate.verification_status == "VERIFIED", unit
    return events(run.trace), canonical_json(certificate.as_document()), dict(run.state)


def test_a71c_a_nonzero_flash_drop_in_a_recycle_binds_alike_in_either_unit() -> None:
    """A71 (c), the binding: NET-06's `U-PHF.pressure_drop` as `{2500.0, Pa}` and `{2.5, kPa}` —
    the twin's C2 pair's conversion, `2.5 kPa -> 2500.0 Pa` — bind equal bit for bit; the `kPa`
    one records the single conversion with the C2 pair's `rule` and `si_value_hex`; the drop
    reaches the problem (`constants_sha256` differs from NET-06's)."""
    c2_pair = PAIRS["SYN-001-UL-C2:U-RX.pressure_drop=2.5kPa"]
    pascal, kilopascal = _net06_drop(2500.0, "Pa"), _net06_drop(2.5, "kPa")
    pa_binding, kpa_binding = revision_bound(pascal), revision_bound(kilopascal)
    assert kpa_binding.input_mapping.conversions == (
        pair_record({**c2_pair, "input": "U-PHF.pressure_drop"}),
    )
    (record,) = kpa_binding.input_mapping.conversions
    written = (record.value, record.unit, record.si_value, record.si_unit)
    assert written == (2.5, "kPa", 2500.0, "Pa")
    assert record.si_value.hex() == float.fromhex(c2_pair["si_value_hex"]).hex()
    assert pa_binding.input_mapping.conversions == ()
    assert_binds_as(kpa_binding, pa_binding)
    assert pins(kilopascal) == pins(pascal)
    net06 = revision_bound(document("SYN-001-T06-NET06"))
    assert declaration_identity(pa_binding.spec)[1] != declaration_identity(net06.spec)[1]


def test_a71c_the_drop_is_solved_and_certified_alike_in_either_unit() -> None:
    """A71 (c), the solve: `CONVERGED` and `VERIFIED` in both spellings, traces and certificates
    byte-identical to each other, and the certified state carries the drop — `S3.P = S4.P = S5.P
    = 97 500.0 Pa` exactly (`1e5 − 2500`, the rows `P_out = P_in − ΔP`, ADR 0001 D4.5) with
    `S1.P = S2.P = 100 000.0 Pa`."""
    pa_trace, pa_certificate, pa_state = net06_solved("Pa")
    kpa_trace, kpa_certificate, kpa_state = net06_solved("kPa")
    assert kpa_trace == pa_trace
    assert kpa_certificate == pa_certificate
    assert bits(list(kpa_state.items())) == bits(list(pa_state.items()))
    pressures = {column: pa_state[column] for column in ("S1.P", "S2.P", "S3.P", "S4.P", "S5.P")}
    assert pressures == {
        "S1.P": 100000.0,
        "S2.P": 100000.0,
        "S3.P": 97500.0,
        "S4.P": 97500.0,
        "S5.P": 97500.0,
    }


# -- A72: the reader rules ------------------------------------------------------------------------


@pytest.mark.parametrize("unit", ["mol/s", "kg/s", "kg/h"])
def test_a72a_a_component_outside_the_set_is_judged_before_the_unit(unit: str) -> None:
    revision = document("SYN-001-T06-STR06")
    specification(revision, "SPEC-feed-n-B")["unit"] = unit
    report = validate(revision)
    assert report.status == "INVALID"
    found = checks(report)
    assert (found["COMP-03"].result, found["COMP-03"].implicated_objects) == (
        "FAIL",
        ("SPEC-feed-n-B",),
    )
    dimensions = found["DIM-01"]
    assert (dimensions.result, dimensions.message, dimensions.implicated_objects) == (
        "PASS",
        "every judged specification and parameter is in its kind's internal SI unit; "
        "not judged for a component outside the set: SPEC-feed-n-B",
        (),
    )
    registered = validate(document("SYN-001-T06-STR06"))
    assert [c.as_document() for c in report.checks] == [c.as_document() for c in registered.checks]
    assert bind_revision_or_reason(revision) == Unbound(
        "conflict", "component_unknown(SPEC-feed-n-B, D)", ("SPEC-feed-n-B",)
    )
    refused = bind_revision_flowsheet(revision)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == (
        "unsupported",
        "specification_unsupported(SPEC-feed-n-B)",
    )


def _c3_split_pinned(pinned: float) -> Document:
    """C3 with `U-SPLIT.split_fraction` `{61, %}` and a specification pinning it in SI."""
    revision = document("SYN-001-UL-C3")
    _in_unit(parameter(revision, "U-SPLIT.split_fraction"), 61, "%", "dimensionless")
    pin = copy.deepcopy(specification(revision, "SPEC-phf-Q"))
    pin.update(
        id="SPEC-split-r",
        target={
            "object_type": "instance",
            "object_id": "U-SPLIT",
            "path": "parameters.split_fraction",
        },
        kind="dimensionless",
        unit="1",
        value=pinned,
    )
    revision["specifications"].append(pin)
    return revision


def test_a72b_a_parameter_pinned_twice_is_compared_on_converted_values() -> None:
    bound = revision_bound(_c3_split_pinned(0.61))
    registered = revision_bound(twin(PAIRS["SYN-001-UL-C3:U-SPLIT.split_fraction=61.0%"]))
    assert bound.flowsheet.label == registered.flowsheet.label
    assert bits(list(bound.spec.parameters.items())) == bits(
        list(registered.spec.parameters.items())
    )
    refused = bind_revision_flowsheet(_c3_split_pinned(0.6100000000000001))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == (
        "conflict",
        "specification_conflict(SPEC-split-r, U-SPLIT.split_fraction)",
    )


def _c2_drop_bounded(upper: float) -> Document:
    revision = document("SYN-001-UL-C2")
    parameter(revision, "U-RX.pressure_drop").update(
        value=2.5, unit="kPa", bounds={"lower": 0.0, "upper": upper}
    )
    return revision


def test_a72c_a_parameter_is_checked_as_its_si_twin() -> None:
    """Bounds `[0, 10]` kPa hold 2.5 kPa — converted with the value; read as Pa they would not
    hold 2500 Pa — and bounds `[0, 2]` kPa refuse it."""
    bound = revision_bound(_c2_drop_bounded(10.0))
    assert [r.si_value for r in bound.input_mapping.conversions] == [2500.0]
    assert checks(validate(_c2_drop_bounded(10.0)))["DIM-01"].result == "PASS"
    code = "parameter_quantity_invalid(U-RX.pressure_drop)"
    refused = bind_revision_flowsheet(_c2_drop_bounded(2.0))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", code)
    found = checks(validate(_c2_drop_bounded(2.0)))["DIM-01"]
    assert (found.result, found.message) == ("FAIL", code)


# -- A73: T05's refusals after W12 ----------------------------------------------------------------


# T05's four unit mutations before W12 (ADR 0016 D9.1), exactly as they were registered there.


def _kilopascal_drop(document: Document) -> None:
    drop = _instance(document, "U-HEAT")["parameters"]["pressure_drop"]
    drop["unit"] = "kPa"


def _percent_split(document: Document) -> None:
    _instance(document, "U-SPLIT")["parameters"]["split_fraction"]["unit"] = "%"


def _feed_pressure_in_bar(document: Document) -> None:
    specification(document, "SPEC-feed-P")["unit"] = "bar"


def _split_specification_in_percent(document: Document) -> None:
    specification(document, "SPEC-splitter-r")["unit"] = "%"


def _t05(change: Callable[[Document], None]) -> Document:
    revision = shaped_revision()
    change(revision)
    return revision


def test_a73_a_kpa_drop_binds_with_one_record() -> None:
    revision = _t05(_kilopascal_drop)
    assert parameter(revision, "U-HEAT.pressure_drop")["value"] == 0.0
    binding = revision_bound(revision)
    assert binding.input_mapping.conversions == (
        UnitConversion(
            source="parameter",
            input_id="U-HEAT.pressure_drop",
            value=0.0,
            unit="kPa",
            si_value=0.0,
            si_unit="Pa",
            rule="scale",
        ),
    )
    assert_binds_as(binding, revision_bound(shaped_revision()))


def test_a73_a_bar_pin_binds_at_1e10_pa() -> None:
    revision = _t05(_feed_pressure_in_bar)
    assert specification(revision, "SPEC-feed-P")["value"] == 100000.0
    binding = revision_bound(revision)
    (record,) = binding.input_mapping.conversions
    assert (record.input_id, record.si_value, record.si_unit) == ("SPEC-feed-P", 1e10, "Pa")
    (column,) = [c for c, names in pin_specifications(revision).items() if "SPEC-feed-P" in names]
    (pinned,) = [i.pins[column] for i in parse_revision(revision).instances if column in i.pins]
    assert pinned == 1e10


@pytest.mark.parametrize(
    "change", [_percent_split, _split_specification_in_percent], ids=["%-split", "%-pin"]
)
def test_a73_a_percent_split_now_conflicts(change: Callable[[Document], None]) -> None:
    refused = bind_revision_flowsheet(_t05(change))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == (
        "conflict",
        "specification_conflict(SPEC-splitter-r, U-SPLIT.split_fraction)",
    )


# -- A74: DIM-01's message and the records' order -------------------------------------------------


def test_a74_the_message_lists_specifications_then_parameters() -> None:
    revision = document("SYN-001-UL-C3")
    specification(revision, "SPEC-phf-Q").update(value=48, unit="kW")
    _in_unit(parameter(revision, "U-SPLIT.split_fraction"), 61, "%", "dimensionless")
    found = checks(validate(revision))["DIM-01"]
    assert found.message == (
        "converted by unit-conversion-v2: SPEC-phf-Q 48.0 kW -> 48000.0 W; "
        "U-SPLIT.split_fraction 61.0 % -> 0.61 1"
    )
    assert found.implicated_objects == ("SPEC-phf-Q", "U-SPLIT.split_fraction")
    assert [r.input_id for r in revision_bound(revision).input_mapping.conversions] == [
        "SPEC-phf-Q",
        "U-SPLIT.split_fraction",
    ]


def test_a74_parameters_are_ordered_by_name_not_by_key_order() -> None:
    revision = document("SYN-001-UL-C2")
    separator = _instance(revision, "U-SEP")
    _in_unit(separator["parameters"]["split.C"], 5.1, "%", "dimensionless")
    _in_unit(separator["parameters"]["split.A"], 91, "%", "dimensionless")
    reordered = {"split.C": separator["parameters"].pop("split.C")}
    reordered.update(separator["parameters"])
    separator["parameters"] = reordered
    assert next(iter(separator["parameters"])) == "split.C"
    expected = ["U-SEP.split.A", "U-SEP.split.C"]
    assert [r.input_id for r in revision_bound(revision).input_mapping.conversions] == expected
    assert list(checks(validate(revision))["DIM-01"].implicated_objects) == expected
