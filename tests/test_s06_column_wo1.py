"""S06 WO-1: inverse column specifications (purity, recovery, stage temperature): their refusals,
declared rows and pinned parameters.

Every expectation is a value of `docs/derivations/scripts/s06_reference.json` (the design lane's
50-digit generator, `s06_reference.py --check`), a code of `docs/derivations/S06-spec.md` §5, or
arithmetic done here independently of the implementation. Each test names the assertion of the
spec's §10 it closes: A01, A02, A03, A04, A12, A13 (the formation part; the records are WO-2's).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest
from conftest import REPO_ROOT

import openflowsheet.models.syn001.cascade_solve as cascade_solve_module
import openflowsheet.models.syn001.column as column_module
import openflowsheet.models.syn001.column_solve as column_solve_module
from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    InletState,
    SideFeed,
    declared_problem,
    liquid_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column import (
    MULTIPLE_STEADY_STATES_WARNING,
    NOT_OFFERED,
    ColumnSpec,
    EndSpecification,
    column_warnings,
    declared_rows,
    distillate_id,
    distillate_total_id,
    purity_flow_id,
    purity_reference,
    purity_reference_parameter,
    reflux_id,
    saturation_temperature,
    slot_column,
    stage_band,
    validate,
)
from openflowsheet.models.syn001.column_solve import solve_column, spec_values
from openflowsheet.thermo import FlashRequest, PropertyRequest
from openflowsheet.thermo.syn001 import Syn001Provider

REFERENCE_PATH = REPO_ROOT / "docs" / "derivations" / "scripts" / "s06_reference.json"
#: The reference this module was written against; a re-emitted reference must be re-read here.
REFERENCE_SHA256 = "c6391195b6c8c184693b674f96dbf41eb89f25cfa16d29fe966dff648320264c"
REFERENCE: dict[str, Any] = json.loads(REFERENCE_PATH.read_bytes())

UNIT = "S06"
COMPONENTS = ("A", "B", "C")
PROVIDER = Syn001Provider()
CONTEXT = EvaluationContext(model_version="S06-WO1@" + "0" * 64, constants_sha256="0" * 64)
FEED = (0.3, 0.4, 0.3)
CONDENSER, REBOILER = "condenser", "reboiler"


def _pressures(count: int) -> tuple[float, ...]:
    """S02 §9: `P_j* = 1.00 + 0.01 (j − 1)` bar."""
    return tuple(1.0e5 + 1.0e3 * j for j in range(count))


def _feed(n: tuple[float, ...] = FEED) -> SideFeed:
    return SideFeed("feed", 4, InletState(n, 340.0, 1.04e5, "LIQUID"))


#: S02 §9's bases, transcribed from S02's table (S06 §9: "Bases are S02's").
BASES: dict[str, ColumnSpec] = {
    "M1": ColumnSpec(
        unit_id=UNIT,
        stage_count=7,
        pressures=_pressures(7),
        duties=(None, 0.0, 0.0, 0.0, 0.0, 0.0, None),
        condenser="partial",
        reboiler="partial",
        condenser_spec=EndSpecification("reflux_ratio", 2.0),
        reboiler_spec=EndSpecification("boilup_ratio", 1.5),
        sides=(_feed(),),
    ),
    "M2": ColumnSpec(
        unit_id=UNIT,
        stage_count=7,
        pressures=_pressures(7),
        duties=(None, 0.0, 0.0, 0.0, 0.0, 0.0, None),
        condenser="total",
        reboiler="partial",
        condenser_spec=EndSpecification("reflux_ratio", 1.5),
        reboiler_spec=EndSpecification("bottoms_rate", 0.55),
        sides=(_feed(),),
    ),
    "M3": ColumnSpec(
        unit_id=UNIT,
        stage_count=5,
        pressures=_pressures(5),
        duties=(0.0, 0.0, 0.0, 0.0, None),
        reboiler="partial",
        reboiler_spec=EndSpecification("duty", 30000.0),
        top=InletState(FEED, 300.0, 1.0e5, "LIQUID"),
    ),
    "M4": ColumnSpec(
        unit_id=UNIT,
        stage_count=5,
        pressures=_pressures(5),
        duties=(None, 0.0, 0.0, 0.0, 0.0),
        condenser="partial",
        condenser_spec=EndSpecification("distillate_rate", 0.5),
        bottom=InletState(FEED, 385.0, 1.04e5, "VAPOR"),
    ),
}


def _end(kind: str, attribute: int | None, value: str | float) -> EndSpecification:
    """A reference end `(kind, attribute, value)`: a component index for `purity`/`recovery` (an
    index past the declared components names a component no column declares), a stage for
    `temperature`, none for a direct kind."""
    number = float(value)
    if kind in ("purity", "recovery"):
        assert attribute is not None
        name = COMPONENTS[attribute] if attribute < len(COMPONENTS) else "D"
        return EndSpecification(kind, number, component=name)
    if kind == "temperature":
        return EndSpecification(kind, number, stage=attribute)
    return EndSpecification(kind, number)


def _from_reference(base: str, ends: dict[str, list[Any]], feed: Any = None) -> ColumnSpec:
    spec = BASES[base]
    changes: dict[str, Any] = {
        f"{end}_spec": _end(*ends[end]) if end in ends else None for end in (CONDENSER, REBOILER)
    }
    if feed is not None:
        changes["sides"] = (_feed(tuple(float(f) for f in feed)),)
    return replace(spec, **changes)


def _j(base: str, condenser: EndSpecification | None, reboiler: EndSpecification | None) -> Any:
    return replace(BASES[base], condenser_spec=condenser, reboiler_spec=reboiler)


#: S06 §9's registered cases J1–J8, transcribed from the spec's table (the reference carries no
#: `spec` for them; `test_the_j_cases_are_the_references` cross-checks kind, value, attribute and
#: the continued partner against `ref.cases.*`).
J_CASES: dict[str, ColumnSpec] = {
    "J1": _j(
        "M1",
        EndSpecification("purity", 0.85, component="A"),
        EndSpecification("boilup_ratio", 1.5),
    ),
    "J2": _j(
        "M2",
        EndSpecification("recovery", 0.9, component="A"),
        EndSpecification("bottoms_rate", 0.7),
    ),
    "J3": _j(
        "M1",
        EndSpecification("reflux_ratio", 2.0),
        EndSpecification("temperature", 368.0, stage=6),
    ),
    "J4": _j(
        "M1",
        EndSpecification("purity", 0.82, component="A"),
        EndSpecification("purity", 0.46, component="C"),
    ),
    "J5": _j("M3", None, EndSpecification("temperature", 395.0, stage=5)),
    "J6": _j(
        "M2",
        EndSpecification("temperature", 330.0, stage=1),
        EndSpecification("bottoms_rate", 0.55),
    ),
    "J7": _j("M4", EndSpecification("recovery", 0.9, component="A"), None),
    "J8": _j(
        "M2",
        EndSpecification("reflux_ratio", 1.5),
        EndSpecification("recovery", 0.99, component="C"),
    ),
}
V_SETS: dict[str, ColumnSpec] = {
    name: _from_reference(record["base"], record["spec"])
    for name, record in REFERENCE["matched"].items()
}
U_SETS: dict[str, ColumnSpec] = {
    name: _from_reference(record["base"], record["spec"])
    for name, record in REFERENCE["unreached"].items()
}
DOF_CASES: dict[str, tuple[ColumnSpec, dict[str, int]]] = {
    **{name: (spec, REFERENCE["cases"][name]["dof"]) for name, spec in J_CASES.items()},
    **{name: (spec, REFERENCE["matched"][name]["dof"]) for name, spec in V_SETS.items()},
}
INVERSE = ("purity", "recovery", "temperature")


def _given(spec: ColumnSpec) -> dict[str, EndSpecification]:
    return {
        end: found
        for end in (CONDENSER, REBOILER)
        if (found := spec.end_specification(end)) is not None
    }


def test_the_reference_is_the_one_this_module_was_written_against() -> None:
    """The generator's output this module reads: its SHA-256 and claim count (S06 §11)."""
    digest = hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest()
    assert digest == REFERENCE_SHA256, digest
    assert REFERENCE["claim_count"] == len(REFERENCE["claims"]) == 3110


def test_the_j_cases_are_the_references() -> None:
    """The transcription of §9's J table against `ref.cases.*`: per inverse end its kind and
    value (`inverse_values`) and its attribute (`continued`), and the continued direct partners'
    targets."""
    for name, spec in J_CASES.items():
        record = REFERENCE["cases"][name]
        inverse = {end: found for end, found in _given(spec).items() if found.kind in INVERSE}
        assert set(inverse) == set(record["inverse_values"]), name
        for end, found in inverse.items():
            entry = record["inverse_values"][end]
            assert (entry["kind"], float(entry["value"])) == (found.kind, found.value), name
            continued = record["continued"][str(spec.end_stage(end))]
            assert continued["kind"] == found.kind and continued["end"] == end
            expected = found.stage if found.kind == "temperature" else found.component
            attribute = continued["attribute"]
            got = attribute if found.kind == "temperature" else COMPONENTS[attribute]
            assert got == expected, name
        for end, found in _given(spec).items():
            stage = str(spec.end_stage(end))
            if found.kind in ("distillate_rate", "bottoms_rate"):
                assert float(record["continued"][stage]["target"]) == found.value, name


# -- A01 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(DOF_CASES))
def test_a01_dof(name: str) -> None:
    """A01 / §3: columns = rows = `ref.*.dof.columns`; `u` and its definition row exactly on the
    `purity` ends; one slot row per end; row and column ids unique; the problem declares."""
    spec, expected = DOF_CASES[name]
    assert validate(spec, PROVIDER, CONTEXT) is None
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    row_ids = [equation.equation_id for equation in rows.equations]
    assert len(rows.variable_ids) == len(row_ids) == expected["columns"] == expected["rows"]
    assert len(set(row_ids)) == len(row_ids)
    assert len(set(rows.variable_ids)) == len(rows.variable_ids)
    assert set(rows.row_kinds) == set(row_ids)
    assert set(rows.variable_ids) == set(rows.variable_kinds)
    purity_ends = [end for end, found in _given(spec).items() if found.kind == "purity"]
    assert len(purity_ends) == expected["purity_columns"]
    assert expected["columns"] - expected["s02_columns"] == len(purity_ends)
    slots = [row for row in row_ids if ":spec:" in row and not row.endswith("purity_definition")]
    assert len(slots) == expected["column_specifications"]
    for stage in range(1, spec.stage_count + 1):
        u = purity_flow_id(UNIT, stage)
        definition = f"{UNIT}:stage:{stage}:spec:purity_definition"
        on_purity = any(spec.end_stage(end) == stage for end in purity_ends)
        assert (u in rows.variable_ids) == on_purity, (stage, u)
        assert (definition in row_ids) == on_purity, (stage, definition)
        if on_purity:
            assert rows.variable_kinds[u] == "molar_flow"
            assert rows.row_kinds[definition] == "molar_flow_squared"
    declared_problem(rows)


@pytest.mark.parametrize("name", sorted(J_CASES))
def test_a01_inverse_slot_rows(name: str) -> None:
    """A01 / §2: each inverse end's slot row `<U>:stage:<j>:spec:<kind>` is of its row kind and
    pins `slot_column` at S02's parameter id (`<column>*`); no `Q_j − Q_j*` remains there."""
    spec = J_CASES[name]
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    row_ids = {equation.equation_id for equation in rows.equations}
    for end, found in _given(spec).items():
        if found.kind not in INVERSE:
            continue
        stage = spec.end_stage(end)
        row = f"{UNIT}:stage:{stage}:spec:{found.kind}"
        assert row in row_ids and f"{UNIT}:stage:{stage}:Q" not in row_ids
        assert rows.row_kinds[row] == (
            "temperature" if found.kind == "temperature" else "molar_flow"
        )
        expected_column = {
            "temperature": stage_temperature_id(UNIT, found.stage or 0),
            "purity": purity_flow_id(UNIT, stage),
        }.get(found.kind)
        if found.kind == "recovery":
            c = found.component
            assert c is not None
            expected_column = (
                liquid_id(UNIT, spec.stage_count, c)
                if end == REBOILER
                else distillate_id(UNIT, c)
                if spec.total_condenser
                else vapor_id(UNIT, 1, c)
            )
        assert slot_column(spec, end, found.kind) == expected_column
        assert f"{expected_column}*" in rows.parameters


# -- A02 -----------------------------------------------------------------------------------------


class _R5OnlyProvider:
    """SYN-001 answering only while S01's R5 (`single_phase_admissible`, the inlet admissibility
    check that precedes S02's and S06's rules) runs. Any other request (a row, a block, a band
    search, the initializer) raises, so a refusal returned through it was decided before any
    evaluation."""

    def __init__(self) -> None:
        self.inside_r5 = False
        self.calls = 0

    def _check(self, request: Any) -> None:
        if not self.inside_r5:
            raise AssertionError(f"A02: evaluation before the refusal: {request}")
        self.calls += 1

    def describe(self) -> Any:
        return PROVIDER.describe()

    def evaluate_phase(self, request: PropertyRequest, context: EvaluationContext) -> Any:
        self._check(request)
        return PROVIDER.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> Any:
        self._check(request)
        return PROVIDER.flash(request, context)


def _refusal_spec(name: str) -> ColumnSpec:
    record = REFERENCE["refusals"][name]
    return _from_reference(record["base"], record["spec"], record["feed"])


#: Every refusal probe is at its base's inlet state and passes S01's R5 there (S06 §17.1, R-608):
#: the provider below answers inside R5, so a probe R5 refused would fail here.
PROBES = sorted(REFERENCE["refusals"])


@pytest.mark.parametrize("name", PROBES)
def test_a02_refusal_probes(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A02 / §5: every `ref.refusals` probe gives its code through `solve_column` with the region
    solve, the initializer and the declared rows stubbed to raise and the provider answering
    only inside S01's R5 inlet check; the pass probe (`expected: null`) passes `validate`."""
    spec = _refusal_spec(name)
    expected = REFERENCE["refusals"][name]["expected"]
    if expected is None:
        assert validate(spec, PROVIDER, CONTEXT) is None
        return

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"A02: {name} reached evaluation")

    for attribute in ("profile_initial", "declared_rows", "bubble_point_endpoint"):
        monkeypatch.setattr(column_solve_module, attribute, refuse)
    monkeypatch.setattr(cascade_solve_module, "solve_region", refuse)
    provider = _R5OnlyProvider()
    admissible = column_module.single_phase_admissible

    def r5(*args: Any, **kwargs: Any) -> Any:
        provider.inside_r5 = True
        try:
            return admissible(*args, **kwargs)
        finally:
            provider.inside_r5 = False

    monkeypatch.setattr(column_module, "single_phase_admissible", r5)
    answer = solve_column(spec, provider)  # type: ignore[arg-type]
    assert isinstance(answer, CascadeFailure), answer
    assert answer.outcome == "INVALID_SPECIFICATION"
    assert answer.cause == expected


@pytest.mark.parametrize("end", [CONDENSER, REBOILER])
@pytest.mark.parametrize("kind", NOT_OFFERED)
def test_a02_not_offered(kind: str, end: str) -> None:
    """A02 / §1, §5 S2: a kind of the narrowed `NOT_OFFERED`, `mole_fraction` among them, is
    `unsupported(specification:<kind>)` at either end."""
    assert NOT_OFFERED == (
        "mole_fraction",
        "reflux_rate",
        "boilup_rate",
        "distillate_to_feed_ratio",
    )
    spec = replace(BASES["M1"], **{f"{end}_spec": EndSpecification(kind, 0.5, component="A")})
    failure = validate(spec, PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert (failure.outcome, failure.cause) == (
        "CAPABILITY_UNAVAILABLE",
        f"unsupported(specification:{kind})",
    )


#: §5 I1's clauses the registered probes do not reach: an attribute on a direct kind, the wrong
#: attribute on an inverse kind, a missing attribute, and a stage that is a `bool`.
I1_MORE: dict[str, tuple[str, EndSpecification, str]] = {
    "direct-with-component": (
        REBOILER,
        EndSpecification("boilup_ratio", 1.5, component="A"),
        "invalid_spec(boilup_ratio:reboiler)",
    ),
    "direct-with-stage": (
        CONDENSER,
        EndSpecification("reflux_ratio", 2.0, stage=3),
        "invalid_spec(reflux_ratio:condenser)",
    ),
    "purity-without-component": (
        CONDENSER,
        EndSpecification("purity", 0.8),
        "invalid_spec(purity:condenser)",
    ),
    "recovery-with-stage": (
        REBOILER,
        EndSpecification("recovery", 0.8, component="C", stage=7),
        "invalid_spec(recovery:reboiler)",
    ),
    "temperature-with-component": (
        REBOILER,
        EndSpecification("temperature", 360.0, component="A", stage=6),
        "invalid_spec(temperature:reboiler)",
    ),
    "temperature-stage-zero": (
        REBOILER,
        EndSpecification("temperature", 360.0, stage=0),
        "invalid_spec(temperature:reboiler)",
    ),
    "temperature-stage-bool": (
        REBOILER,
        EndSpecification("temperature", 360.0, stage=True),
        "invalid_spec(temperature:reboiler)",
    ),
    "recovery-infinite": (
        REBOILER,
        EndSpecification("recovery", math.inf, component="C"),
        "invalid_spec(recovery:reboiler)",
    ),
    "temperature-negative": (
        # S4 is for direct kinds only: a negative T* is I4's (below every band), not S4's.
        REBOILER,
        EndSpecification("temperature", -1.0, stage=6),
        "infeasible_spec(temperature_outside_band:6)",
    ),
}


@pytest.mark.parametrize("name", sorted(I1_MORE))
def test_a02_attribute_and_value_clauses(name: str) -> None:
    """A02 / §5 I1, I2 beyond the registered probes; each violates one rule on M1."""
    end, given, cause = I1_MORE[name]
    failure = validate(replace(BASES["M1"], **{f"{end}_spec": given}), PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert failure.cause == cause


def test_a02_s06_rules_follow_s02s() -> None:
    """§5: I1–I6 run after S10. A probe violating S5 and I6 at once answers S5's code; one
    violating S9 (a falling pressure profile) and I4 answers S9's."""
    spec = _refusal_spec("I6-boundary")
    both = replace(spec, condenser_spec=EndSpecification("distillate_rate", 2.0))
    failure = validate(both, PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert failure.cause == "infeasible_spec(distillate_rate_exceeds_feed)"
    falling = replace(
        _refusal_spec("I4-above"), pressures=(1.0e5, 1.01e5, 1.02e5, 1.03e5, 1.04e5, 1.03e5, 1.06e5)
    )
    failure = validate(falling, PROVIDER, CONTEXT)
    assert isinstance(failure, CascadeFailure)
    assert failure.cause == "invalid_spec(pressure_profile)"


VALID: dict[str, ColumnSpec] = {**J_CASES, **V_SETS, **U_SETS}


@pytest.mark.parametrize("name", sorted(VALID))
def test_a02_every_registered_set_passes(name: str) -> None:
    """A02: every J, V and U set passes §5."""
    assert validate(VALID[name], PROVIDER, CONTEXT) is None


# -- A03 -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("pressure", sorted(REFERENCE["band"]))
def test_a03_saturation_temperatures(pressure: str) -> None:
    """A03 / §4: the implementation's `T_sat,i(P)` against `ref.band` (1e-9 K; floor a few
    roundings at 400 K), and its ordering A < B < C."""
    values = [saturation_temperature(c, float(pressure)) for c in COMPONENTS]
    for got, expected in zip(values, REFERENCE["band"][pressure], strict=True):
        assert abs(got - float(expected)) <= 1e-9, (got, expected)
    assert values[0] < values[1] < values[2]


def test_a03_stage_band_is_over_the_present_components() -> None:
    """§4: a stage's band at `P_s*` is (T_sat,A, T_sat,C) with every component fed and
    (T_sat,A, T_sat,B) when C is absent (`ref.band` at 1.05 bar, stage 6 of M1)."""
    band = REFERENCE["band"]["105000"]
    low, high = stage_band(BASES["M1"], 6)
    assert abs(low - float(band[0])) <= 1e-9 and abs(high - float(band[2])) <= 1e-9
    absent = replace(BASES["M1"], sides=(_feed((0.5, 0.5, 0.0)),))
    low, high = stage_band(absent, 6)
    assert abs(low - float(band[0])) <= 1e-9 and abs(high - float(band[1])) <= 1e-9


# -- A04 -----------------------------------------------------------------------------------------


TRIAL = REFERENCE["trial_rows"]


def _q(text: str) -> float:
    value = Fraction(text)
    assert float(value) == value, text  # the trial operands are dyadic
    return float(value)


def _trial_specs() -> dict[str, ColumnSpec]:
    """`ref.trial_rows.spec`: on M1's structure with feed (0.25, 0.5, 0.25), condenser purity of B
    3/4 with (a) reboiler recovery of C 1/2, (b) reboiler temperature of stage 6 at 721/2 K."""
    end, index, value = TRIAL["spec"]["purity"]
    assert end == CONDENSER
    purity = EndSpecification("purity", _q(value), component=COMPONENTS[index])
    end, index, value = TRIAL["spec"]["recovery"]
    assert end == REBOILER
    recovery = EndSpecification("recovery", _q(value), component=COMPONENTS[index])
    end, stage, value = TRIAL["spec"]["temperature"]
    assert end == REBOILER
    temperature = EndSpecification("temperature", _q(value), stage=stage)
    base = replace(BASES["M1"], sides=(_feed((0.25, 0.5, 0.25)),), condenser_spec=purity)
    return {
        "recovery": replace(base, reboiler_spec=recovery),
        "temperature": replace(base, reboiler_spec=temperature),
    }


def _trial_state(spec: ColumnSpec) -> dict[str, float]:
    """`ref.trial_rows.state` on the declared columns; every other column arbitrary but inside
    the domain (flows 0.1 mol/s, T 350 K, P its stage's)."""
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    state: dict[str, float] = {}
    for name in rows.variable_ids:
        kind = rows.variable_kinds[name]
        state[name] = {"temperature": 350.0, "pressure": 1.0e5, "heat_rate": 0.0}.get(kind, 0.1)
    for stage in range(1, spec.stage_count + 1):
        state[stage_pressure_id(UNIT, stage)] = spec.pressures[stage - 1]
    trial = TRIAL["state"]
    for c, value in zip(COMPONENTS, trial["v_1"], strict=True):
        state[vapor_id(UNIT, 1, c)] = _q(value)
    for c, value in zip(COMPONENTS, trial["l_7"], strict=True):
        state[liquid_id(UNIT, 7, c)] = _q(value)
    state[vapor_total_id(UNIT, 1)] = _q(trial["V_1"])
    state[purity_flow_id(UNIT, 1)] = _q(trial["u"])
    state[stage_temperature_id(UNIT, 5)] = _q(trial["T_5"])
    state[stage_temperature_id(UNIT, 6)] = _q(trial["T_6"])
    return state


def _trial_rows(name: str) -> dict[str, float]:
    spec = _trial_specs()[name]
    assert validate(spec, PROVIDER, CONTEXT) is None
    problem = declared_problem(declared_rows(spec, PROVIDER, CONTEXT))
    return row_values(problem, _trial_state(spec))


def test_a04_the_trial_values_are_distinct() -> None:
    """A04: the reference's claim that a permuted component, a wrong stage or a flipped sign gives
    a different residual, so the exact matches below catch each."""
    for key, others in (
        ("purity_definition", TRIAL["purity_definition_other_components"]),
        ("recovery_slot", TRIAL["recovery_slot_other_components"]),
        ("temperature_slot", [TRIAL["temperature_slot_other_stage"]]),
        ("purity_slot", []),
    ):
        value = Fraction(TRIAL[key])
        alternatives = {Fraction(other) for other in others} | {-value}
        assert value not in alternatives, key


def test_a04_purity_and_recovery_rows() -> None:
    """A04 / §2 on declaration (a): `F v_1,B − u V_1` = −3/64, `u − π*` = −1/4,
    `l_7,C − ν*` = 1/16, exactly."""
    rows = _trial_rows("recovery")
    assert rows[f"{UNIT}:stage:1:spec:purity_definition"] == Fraction(TRIAL["purity_definition"])
    assert rows[f"{UNIT}:stage:1:spec:purity"] == Fraction(TRIAL["purity_slot"])
    assert rows[f"{UNIT}:stage:7:spec:recovery"] == Fraction(TRIAL["recovery_slot"])


def test_a04_temperature_row() -> None:
    """A04 / §2 on declaration (b): `T_6 − T*` = 3/4 exactly (the reboiler's slot names stage 6);
    the condenser's purity rows are (a)'s."""
    rows = _trial_rows("temperature")
    assert rows[f"{UNIT}:stage:7:spec:temperature"] == Fraction(TRIAL["temperature_slot"])
    assert rows[f"{UNIT}:stage:1:spec:purity_definition"] == Fraction(TRIAL["purity_definition"])
    assert rows[f"{UNIT}:stage:1:spec:purity"] == Fraction(TRIAL["purity_slot"])


def test_a04_purity_at_a_total_condenser() -> None:
    """A04 / S06 §17.4: on M2's structure (total condenser) with condenser purity of A 0.75 and
    reboiler bottoms rate 0.875 (R-613), at a state whose columns are distinct dyadic values, the
    purity definition row is `F·d_A − u·D` exactly and differs from the top vapour's
    `F·v_2,A − u·V_2` and the reflux's `F·r_A − u·Σ r`. The feed is (1/4, 1/2, 3/8) so that `F` =
    9/8 is dyadic and not 1. The set is admissible through `validate` at M2's feed and at the
    test's (S06 §17.5); the former set, bottoms rate 0.55, stays as the refused control
    (`infeasible_spec(mass_balance)`: no top product holds `d_A = 0.75 D` with `D = F − 0.55`)."""
    condenser = EndSpecification("purity", 0.75, component="A")
    for feed in (_feed(), _feed((0.25, 0.5, 0.375))):
        spec = replace(
            BASES["M2"],
            sides=(feed,),
            condenser_spec=condenser,
            reboiler_spec=EndSpecification("bottoms_rate", 0.875),
        )
        assert validate(spec, PROVIDER, CONTEXT) is None
        control = replace(spec, reboiler_spec=EndSpecification("bottoms_rate", 0.55))
        refused = validate(control, PROVIDER, CONTEXT)
        assert isinstance(refused, CascadeFailure)
        assert refused.cause == "infeasible_spec(mass_balance)"
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    state: dict[str, float] = {}
    for k, name in enumerate(rows.variable_ids):
        kind = rows.variable_kinds[name]
        base = {"temperature": 300.0, "pressure": 1.0e5, "heat_rate": 1.0e3}.get(kind, 0.0)
        state[name] = base + (k + 1) / 128
    assert len(set(state.values())) == len(state)
    total = Fraction(purity_reference(spec))
    assert total == Fraction(9, 8)
    u = Fraction(state[purity_flow_id(UNIT, 1)])

    def definition(part: str, whole: Fraction) -> Fraction:
        return total * Fraction(state[part]) - u * whole

    expected = definition(distillate_id(UNIT, "A"), Fraction(state[distillate_total_id(UNIT)]))
    top_vapour = definition(vapor_id(UNIT, 2, "A"), Fraction(state[vapor_total_id(UNIT, 2)]))
    reflux = definition(
        reflux_id(UNIT, "A"), sum(Fraction(state[reflux_id(UNIT, c)]) for c in COMPONENTS)
    )
    assert expected not in (top_vapour, reflux)
    values = row_values(declared_problem(rows), state)
    assert values[f"{UNIT}:stage:1:spec:purity_definition"] == expected
    assert values[f"{UNIT}:stage:1:spec:purity"] == u - Fraction(3, 4) * total


def test_a04_spec_values_carry_the_inverse_quantities() -> None:
    """§7.3's quantities through `spec_values` at the trial state, formed here: purity
    `v_1,B / V_1`, recovery `l_7,C / F_C`, temperature `T_6`."""
    specs = _trial_specs()
    trial = TRIAL["state"]
    values = spec_values(specs["recovery"], _trial_state(specs["recovery"]))
    assert values["condenser_purity"] == _q(trial["v_1"][1]) / _q(trial["V_1"])
    assert values["reboiler_recovery"] == _q(trial["l_7"][2]) / 0.25
    values = spec_values(specs["temperature"], _trial_state(specs["temperature"]))
    assert values["reboiler_temperature"] == _q(trial["T_6"])


# -- A12 -----------------------------------------------------------------------------------------


def test_a12_warnings() -> None:
    """A12 / §7.4: no warning on J1–J8, the V-sets, U1 and U2; a duty-only column still carries
    C8's `multiple_steady_states_possible(duty_only)`."""
    for name, spec in VALID.items():
        assert column_warnings(spec) == (), name
    assert column_warnings(BASES["M3"]) == (MULTIPLE_STEADY_STATES_WARNING,)
    duty_duty = replace(
        BASES["M1"],
        condenser_spec=EndSpecification("duty", -2.0e4),
        reboiler_spec=EndSpecification("duty", 3.0e4),
    )
    assert column_warnings(duty_duty) == (MULTIPLE_STEADY_STATES_WARNING,)


# -- A13 (formation) -----------------------------------------------------------------------------


def _component_feeds(spec: ColumnSpec) -> list[float]:
    """`F_c` summed here over `inlets()` in order, binary64."""
    totals = [0.0] * len(COMPONENTS)
    for inlet in spec.inlets():
        for i, flow in enumerate(inlet.state.n):
            totals[i] += flow
    return totals


@pytest.mark.parametrize("name", ["J1", "J2", "J3", "J4", "J7", "J8"])
def test_a13_pinned_parameters(name: str) -> None:
    """A13 / §2 "Derived parameters": the pinned `π* = fl(x*·F)`, `ν* = fl(r*·F_c)`, `T*`, and
    `F` at `purity_reference*`, bit for bit against the formation here, and within one ulp of
    the generator's exact `ref.cases.*.inverse_values.parameter`."""
    spec = J_CASES[name]
    rows = declared_rows(spec, PROVIDER, CONTEXT)
    feeds = _component_feeds(spec)
    total = 0.0
    for feed in feeds:
        total += feed
    for end, found in _given(spec).items():
        if found.kind not in INVERSE:
            continue
        stage = spec.end_stage(end)
        if found.kind == "temperature":
            expected = found.value
        elif found.kind == "recovery":
            expected = found.value * feeds[COMPONENTS.index(found.component or "")]
        else:
            expected = found.value * total
            assert rows.parameters[purity_reference_parameter(UNIT, stage)] == total
        pinned = rows.parameters[f"{slot_column(spec, end, found.kind)}*"]
        assert pinned == expected, (end, pinned, expected)
        exact = float(REFERENCE["cases"][name]["inverse_values"][end]["parameter"])
        assert abs(pinned - exact) <= math.ulp(exact), (end, pinned, exact)
