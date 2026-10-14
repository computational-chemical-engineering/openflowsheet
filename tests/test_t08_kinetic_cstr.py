"""T08 W2: `syn001.kinetic_cstr` — T08.B10–B19 of the build-first spec (§C.1).

Design `docs/derivations/T08-build-first-spec.md` Part A (§A1 the model, §A3 the mapping, §A5 the
expected values), ADR 0023. Every expected number is `benchmarks/t08/build_first_reference.yaml`'s
(the design lane's 40-digit generator) or a closed form from the SYN-001 provider's own functions,
never this code's output. Tolerances are §C.1's.

**What runs at PTC-R1's parameters** (§A4.6): evaluations at the three roots and at the three
off-grid states of §A5, and single steps at the off-grid states. No PTC or Newton *run* is made on
the PTC-R1 flowsheet, from a registered start or any other: the region solves below are of the
dormant flowsheet (B16) and the liquid variant (B19).

**Three components** (Amendment 1 §Am1.1, R-126; see `t08_cstr_support`): the revisions carry `C`
as an inert `2⁻¹⁰` mol/s trace, and the YAML lists its entries (B12, B13), the pencil's second
`−1/θ` (B14) and `d_n_C` (B15). B17 and B18 are §Am1.C's amended rows.

**B13–B15 on the bound revision** (W3): each runs on the W2 fixture (`ptc_r1`) and on the
registered `benchmarks/t08/ptc_r1/revision.json` (`case`), bound by `bind_revision_flowsheet`.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import scipy.linalg as la
import scipy.sparse as sp
from conftest import REPO_ROOT
from t05_w12_support import planned_step
from t08_cstr_support import (
    CAPACITY,
    COLUMN,
    COMPONENTS,
    FEED_N,
    INLET,
    MODEL,
    OUTLET,
    REFERENCE,
    ROOTS,
    SINGLE_STEPS,
    T_F,
    T_SCALE,
    TRACE,
    UNIT,
    cstr_parameters,
    dormant_revision,
    f,
    liquid_variant_revision,
    off_grid_state,
    ptc_r1_revision,
    root_state,
    row,
)

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError
from openflowsheet.models.revision_flowsheet import required_kind
from openflowsheet.models.syn001.kinetic_cstr import (
    EQUATIONS,
    INITIALIZER_LIMITATION,
    MODEL_ID,
    PORTS,
    KineticCSTR,
)
from openflowsheet.numerics.linear import solve_linear
from openflowsheet.numerics.newton import _scale_matrix
from openflowsheet.numerics.ptc import (
    PTC_ROW_SIGN,
    PtcProblem,
    _row_scaled,
    pseudo_step_direction,
    row_signs,
)
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, Scaling
from openflowsheet.orchestrator import revision
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.mass import (
    MappingRefusal,
    RegionMass,
    declared_phases,
    residence_time,
    resolve_mass,
)
from openflowsheet.orchestrator.region import RegionResult, region_ptc_problem
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.syn001 import Syn001Provider, h_liquid, h_vapor
from openflowsheet.verify.certificate import verify_revision

POLICY = SolvePolicy(policy_id="T08-W2", residual_tolerances={}, scales={})
CONTEXT = EvaluationContext(model_version="t08-w2", constants_sha256="0" * 64, phase_signature=None)
ROOT_NAMES = ("LOW", "MID", "HIGH")
OFF_GRID = tuple((f(step["x1"]), f(step["x2"])) for step in SINGLE_STEPS)
STEP_KEYS = ("ptc_dtau_0.5", "ptc_dtau_4", "ptc_dtau_1000000", "newton")
STEP_TAU = {"ptc_dtau_0.5": 0.5, "ptc_dtau_4": 4.0, "ptc_dtau_1000000": 1.0e6}
#: The PTC-R1 bindings B13–B15 run on: the W2 fixture and the registered revision (W3).
PTC_R1_BINDINGS = ("ptc_r1", "case")
CASE_REVISION = REPO_ROOT / "benchmarks" / "t08" / "ptc_r1" / "revision.json"


# -- shared -----------------------------------------------------------------------------------


@cache
def binding(name: str) -> RevisionBinding:
    document = {
        "ptc_r1": ptc_r1_revision,
        "liquid": liquid_variant_revision,
        "dormant": dormant_revision,
        "adiabatic_dormant": lambda: dormant_revision(0.0),
        "case": lambda: json.loads(CASE_REVISION.read_text(encoding="utf-8")),
    }[name]()
    bound = bind_revision_flowsheet(document)
    assert isinstance(bound, RevisionBinding), bound
    return bound


@cache
def compiled(name: str) -> Any:
    return compile_problem(binding(name).spec)


def context_of(name: str) -> EvaluationContext:
    metadata = compiled(name).metadata
    return EvaluationContext(
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        phase_signature=None,
    )


def vector(name: str, state: Mapping[str, float]) -> np.ndarray:
    return np.array([state[column] for column in binding(name).spec.variable_ids])


def residuals(name: str, state: Mapping[str, float]) -> dict[str, float]:
    result = compiled(name).residual(vector(name, state), context_of(name))
    assert result.status == "ok", result.message
    return dict(zip(result.equation_ids, result.values, strict=True))


def jacobian(name: str, state: Mapping[str, float]) -> dict[tuple[str, str], float]:
    result = compiled(name).jacobian(vector(name, state), context_of(name))
    assert result.status == "ok", result.message
    matrix = sp.csc_matrix(
        (result.data, result.indices, result.indptr),
        shape=(len(result.row_ids), len(result.col_ids)),
    ).tocoo()
    return {
        (result.row_ids[i], result.col_ids[j]): float(value)
        for i, j, value in zip(matrix.row, matrix.col, matrix.data, strict=True)
    }


def unit(**overrides: Any) -> KineticCSTR:
    """The realization's unit, constructed directly; `overrides` replace constructor fields."""
    parameters = cstr_parameters()
    fields: dict[str, Any] = {
        "unit_id": UNIT,
        "provider": Syn001Provider(),
        "stoichiometry": tuple(parameters[f"nu.{c}"] for c in COMPONENTS),
        "key_component": "B",
        "damkohler": parameters["damkohler.B"],
        "reference_temperature": parameters["T_ref"],
        "temperature_scale": parameters["T_scale"],
        "coolant_flow": parameters["coolant_flow"],
        "coolant_cp": parameters["coolant_cp"],
        "coolant_temperature": parameters["T_coolant"],
        "phase": "VAPOR",
        "context": CONTEXT,
        "pressure_drop": parameters["pressure_drop"],
        "inlet_phase": "VAPOR",
    }
    fields.update(overrides)
    return KineticCSTR(**fields)


def feed(n: Sequence[float] = FEED_N, temperature: float = T_F) -> StreamState:
    return StreamState(n=tuple(n), temperature=temperature, pressure=1.0e5)


# -- B10: the contract ------------------------------------------------------------------------

#: §A1.2's pins and their kinds, as the spec writes them (`<U>.<name>`; `nu.<c>` per component).
SPEC_PIN_KINDS = {
    "nu": "dimensionless",
    "damkohler": "dimensionless",
    "T_ref": "temperature",
    "T_scale": "temperature_difference",
    "coolant_flow": "molar_flow",
    "coolant_cp": "molar_heat_capacity",
    "T_coolant": "temperature",
    "pressure_drop": "pressure",
}


def test_b10_the_model_is_the_thirteenth_builder_with_its_signature() -> None:
    # Since M02's join (R-280; design note §14.4 D5, B13's rule) restricted to the `syn001.`
    # keys, the literal unchanged; `tests/test_m02_join.py` pins all twenty-one.
    syn001 = [model for model in MODEL_BUILDERS if model.startswith("syn001.")]
    assert MODEL_ID in syn001 and len(syn001) == 13
    signature = MODEL_SIGNATURES[MODEL_ID]
    assert signature.ports == PORTS
    assert [(p.name, p.kind, p.direction, p.multiplicity) for p in PORTS] == [
        ("inlet", "material", "inlet", 1),
        ("outlet", "material", "outlet", 1),
        ("duty", "energy", "inlet", 1),
    ]
    assert signature.required == (
        "nu.{component}",
        "damkohler.{key}",
        "T_ref",
        "T_scale",
        "coolant_flow",
        "coolant_cp",
        "T_coolant",
        "pressure_drop",
    )
    assert (signature.zero, signature.pins, signature.choices) == ((), (), ())
    for template in signature.required:
        name = template.split(".")[0]
        assert required_kind(f"parameters.{name}") == SPEC_PIN_KINDS[name], template


def test_b10_the_row_parameters_are_the_spec_pins() -> None:
    contribution = unit().contribute(
        binding("ptc_r1").flowsheet.wiring[UNIT], binding("ptc_r1").flowsheet.components
    )
    assert contribution.parameter_ids == (
        *(f"{UNIT}.nu.{c}" for c in COMPONENTS),
        f"{UNIT}.damkohler",
        f"{UNIT}.T_ref",
        f"{UNIT}.T_scale",
        f"{UNIT}.coolant_flow",
        f"{UNIT}.coolant_cp",
        f"{UNIT}.T_coolant",
        f"{UNIT}.pressure_drop",
    )
    assert contribution.variable_ids == (f"{UNIT}.Q",)
    assert [equation.equation_id for equation in contribution.equations] == [
        *(row(f"CSTR-mole:{c}") for c in COMPONENTS),
        row("CSTR-duty"),
        row("CSTR-cooling"),
        row("CSTR-pressure"),
    ]


def test_b10_list_models_reports_it(tmp_path: Path) -> None:
    app = LocalApplication.create(tmp_path / "project", project_id="t08-w2")
    try:
        models = {model["model_id"]: model for model in app.list_models().models}
    finally:
        app.close()
    model = models[MODEL_ID]
    assert model["required"] == list(MODEL_SIGNATURES[MODEL_ID].required)
    assert [port["name"] for port in model["ports"]] == ["inlet", "outlet", "duty"]
    assert (model["pins"], model["choices"]) == ([], [])


#: §A1.2's eleven construction codes, each raised by one constructed input.
CONSTRUCTION = {
    "stoichiometry_not_mass_conserving": {"stoichiometry": (1.0, -1.0, 0.5)},
    "key_not_reactant": {"key_component": "A"},
    "reference_convention_not_reaction_consistent(SYN-001-shifted)": {"provider": "shifted"},
    "damkohler_negative": {"damkohler": -1e-3},
    "temperature_scale_not_positive": {"temperature_scale": 0.0},
    "coolant_flow_negative": {"coolant_flow": -0.1},
    "coolant_cp_not_positive": {"coolant_cp": 0.0},
    "reference_temperature_outside_domain": {"reference_temperature": 279.0},
    "coolant_temperature_outside_domain": {"coolant_temperature": 441.0},
    "pressure_drop_negative": {"pressure_drop": -1.0},
    "rate_exponent_overflow": {"temperature_scale": 0.1},
}


class _ShiftedConvention(Syn001Provider):
    """The SYN-001 provider declaring a convention outside ADR 0011 D2's set."""

    def describe(self) -> Any:
        import dataclasses

        return dataclasses.replace(super().describe(), reference_convention="SYN-001-shifted")


@pytest.mark.parametrize("code", list(CONSTRUCTION))
def test_b10_each_construction_code_is_raised_by_one_input(code: str) -> None:
    overrides = dict(CONSTRUCTION[code])
    if overrides.get("provider") == "shifted":
        overrides["provider"] = _ShiftedConvention()
    with pytest.raises(SpecificationError) as raised:
        unit(**overrides)
    assert str(raised.value).splitlines()[0] == code


def test_b10_the_realization_constructs_and_its_exponent_is_25_6() -> None:
    built = unit()
    assert (440.0 - built.reference_temperature) / built.temperature_scale == 25.6


def test_b10_the_revision_refuses_a_lifted_outlet() -> None:
    document = ptc_r1_revision()
    document["connections"][1]["phase_capability"] = "vapor_liquid"
    refused = bind_revision_flowsheet(document)
    assert not isinstance(refused, RevisionBinding)
    assert refused.detail == f"port_phase_unsupported({UNIT}.outlet)"


def test_b10_the_manifest_and_accumulation_are_t05_13_2s_row() -> None:
    manifest = unit().manifest()
    assert manifest["id"] == MODEL_ID and manifest["introduced_by_package"] == "T08"
    kinds = {equation.equation_id: equation.accumulation.kind for equation in EQUATIONS}
    assert kinds == {
        "CSTR-mole": "holdup_balance",
        "CSTR-duty": "holdup_balance",
        "CSTR-cooling": "algebraic",
        "CSTR-pressure": "algebraic",
    }
    holdups = {
        equation.equation_id: (
            equation.accumulation.holdup.symbol,
            equation.accumulation.holdup.dimension,
        )
        for equation in EQUATIONS
        if equation.accumulation.holdup is not None
    }
    assert holdups == {
        "CSTR-mole": ("N_i", (0, 0, 0, 0, 1, 0, 0)),
        "CSTR-duty": ("U", (2, 1, -2, 0, 0, 0, 0)),
    }
    statements = {equation.equation_id: equation.statement for equation in EQUATIONS}
    assert statements["CSTR-mole"] == (
        "n_in,i - n_out,i + nu_i r = 0, r = Da exp((T_out - T_ref)/T_s) n_out,k "
        "(synthetic rate law)"
    )
    assert statements["CSTR-duty"] == (
        "Q + Hdot_in - Hdot_out = 0 on the provider's formation datum (ADR 0011 D2); the heat "
        "of reaction is carried by Hdot"
    )
    spec = binding("ptc_r1").spec
    assert {
        name: spec.row_accumulation[name] for name in spec.equation_ids if name.startswith(UNIT)
    } == {
        **{row(f"CSTR-mole:{c}"): "holdup_balance" for c in COMPONENTS},
        row("CSTR-duty"): "holdup_balance",
        row("CSTR-cooling"): "algebraic",
        row("CSTR-pressure"): "algebraic",
    }


# -- B11: rows at the three roots -------------------------------------------------------------


@pytest.mark.parametrize("name", ROOT_NAMES)
def test_b11_the_rows_vanish_at_the_roots(name: str) -> None:
    values = residuals("ptc_r1", root_state(name))
    tolerances = MODEL["tolerances"]
    for c in ("A", "B"):
        assert abs(values[row(f"CSTR-mole:{c}")]) <= float(tolerances["mole_mol_s"]), c
    assert values[row("CSTR-mole:C")] == 0.0
    assert abs(values[row("CSTR-duty")]) <= float(tolerances["heat_W"])
    assert abs(values[row("CSTR-cooling")]) <= float(tolerances["heat_W"])
    assert values[row("CSTR-pressure")] == 0.0
    assert all(values[r] == 0.0 for r in values if r.startswith("U-FEED"))


@pytest.mark.parametrize("name", ROOT_NAMES)
def test_b11_b19_the_duty_row_carries_the_reaction_heat(name: str) -> None:
    """At each root, `Ḣ_in − Ḣ_out` minus its sensible part is the YAML's reaction heat: a model
    that dropped it would miss `CSTR-duty` by that much (426.878 W at LOW, rule 3)."""
    state = root_state(name)
    # `Ḣ_in − Ḣ_out = Σ n_out,i (h_i(T_F) − h_i(T)) + Σ (n_in,i − n_out,i) h_i(T_F)`: the first
    # sum is sensible, the second the reaction heat `Σ ν_i L_i` times the extent (`Σ ν_i = 0`).
    reaction = sum(
        (state[f"{INLET}.n.{c}"] - state[f"{OUTLET}.n.{c}"]) * h_vapor(T_F, i)
        for i, c in enumerate(COMPONENTS)
    )
    expected = f(MODEL["at_roots"][name]["reaction_heat_in_duty_row_W"])
    assert reaction == pytest.approx(expected, rel=1e-12)


# -- B12: the Jacobian ------------------------------------------------------------------------


def _yaml_entries(name: str) -> dict[tuple[str, str], float]:
    return {
        (row(label.split("|")[0]), COLUMN[label.split("|")[1]]): f(value)
        for label, value in MODEL["at_roots"][name]["jacobian_nonzeros"].items()
    }


@pytest.mark.parametrize("name", ROOT_NAMES)
def test_b12a_the_jacobian_at_the_roots_is_the_yamls(name: str) -> None:
    state = root_state(name)
    entries = jacobian("ptc_r1", state)
    expected = _yaml_entries(name)
    outlet_columns = {*COLUMN.values()}
    cstr_rows = {r for r, _ in entries if r.startswith(f"{UNIT}:")}
    assert cstr_rows == {r for r, _ in expected}
    for r in cstr_rows:
        scale = max(abs(v) for (rr, c), v in expected.items() if rr == r)
        for column in outlet_columns:
            got = entries.get((r, column), 0.0)
            want = expected.get((r, column), 0.0)
            assert abs(got - want) <= 1e-12 * scale, (r, column, got, want)


def _states_b12() -> list[tuple[str, dict[str, float]]]:
    return [(name, root_state(name)) for name in ROOT_NAMES] + [
        (f"off-grid {x1}, {x2}", off_grid_state(x1, x2)) for x1, x2 in OFF_GRID
    ]


@pytest.mark.parametrize("where", range(6))
def test_b12b_central_differences_agree(where: str) -> None:
    label, state = _states_b12()[int(where)]
    spec = binding("ptc_r1").spec
    analytic = jacobian("ptc_r1", state)
    kinds = spec.variable_kinds
    worst = 0.0
    rows = [r for r in spec.equation_ids if r.startswith(f"{UNIT}:")]
    columns = list(spec.variable_ids)
    fd: dict[tuple[str, str], float] = {}
    for column in columns:
        step = 1e-6 * REGISTERED_NOMINALS[kinds[column]]
        plus, minus = dict(state), dict(state)
        plus[column] += step
        minus[column] -= step
        high, low = residuals("ptc_r1", plus), residuals("ptc_r1", minus)
        for r in rows:
            fd[(r, column)] = (high[r] - low[r]) / (2.0 * step)
    for r in rows:
        scale = max(abs(analytic.get((r, c), 0.0)) for c in columns)
        error = max(abs(fd[(r, c)] - analytic.get((r, c), 0.0)) for c in columns) / scale
        worst = max(worst, error)
    assert worst <= float(REFERENCE["float64"]["derivative_floor"]["registered_tolerance"]), (
        label,
        worst,
    )


# -- B13: the mapping on the region -----------------------------------------------------------


def region_mass(name: str = "ptc_r1", theta: float = 1.0) -> RegionMass | MappingRefusal:
    bound = binding(name)
    step = planned_step(bound, POLICY)
    assert step.region is not None
    return resolve_mass(
        residence_time(
            bound.flowsheet.wiring,
            bound.flowsheet.components,
            declared_phases(bound.flowsheet.units()),
        ),
        spec=bound.spec,
        rows=step.region.row_ids,
        residence_time=theta,
    )


@pytest.mark.parametrize("bound_name", PTC_R1_BINDINGS)
@pytest.mark.parametrize("name", ROOT_NAMES)
def test_b13_the_mapping_is_the_yamls_mass(name: str, bound_name: str) -> None:
    mass = region_mass(bound_name)
    assert isinstance(mass, RegionMass)
    assert {entry.row for entry in mass.entries} == {
        *(row(f"CSTR-mole:{c}") for c in COMPONENTS),
        row("CSTR-duty"),
    }
    state = root_state(name)
    bound = binding(bound_name)
    entries = mass.entries_at(state, bound.flowsheet.provider, context_of(bound_name))
    expected = {
        (row(label.split("|")[0]), COLUMN[label.split("|")[1]]): f(value)
        for label, value in MODEL["at_roots"][name]["mass_nonzeros_theta_1s"].items()
    }
    for key, want in expected.items():
        assert entries[key] == pytest.approx(want, rel=1e-13), key
    extra = {key: value for key, value in entries.items() if key not in expected and value != 0.0}
    assert extra == {}


def test_b13_the_liquid_outlet_maps_liquid_enthalpies() -> None:
    mass = region_mass("liquid")
    assert isinstance(mass, RegionMass)
    state = revision.initial_state(binding("liquid").flowsheet, binding("liquid").spec.variable_ids)
    assert isinstance(state, dict)
    entries = mass.entries_at(state, binding("liquid").flowsheet.provider, context_of("liquid"))
    for i, c in enumerate(COMPONENTS):
        assert entries[(row("CSTR-duty"), f"{OUTLET}.n.{c}")] == h_liquid(
            state[f"{OUTLET}.T"], state[f"{OUTLET}.P"], i
        )


def test_b13_a_t05_holdup_row_beside_the_cstr_is_still_refused() -> None:
    """The CSTR's entries do not reach a T05 model's rows: CSTR → conversion reactor ends
    `ptc_mapping_invalid(<RX-mole row>, missing)` (T05 §12.4, A27)."""
    import copy

    from t05_w12_support import unit_instance
    from test_t05_w11_cases import case_document

    document = ptc_r1_revision()
    reactor = unit_instance("SYN-001-UL-C2", "U-RX")
    document["instances"].insert(2, reactor)
    to_sink = copy.deepcopy(document["connections"][1])
    document["connections"][1]["to"] = {"instance": "U-RX", "port": "inlet"}
    to_sink.update(
        id="S3", phase_capability="vapor_liquid", **{"from": {"instance": "U-RX", "port": "outlet"}}
    )
    document["connections"].append(to_sink)
    pin = next(
        entry
        for entry in case_document("SYN-001-UL-C2")["specifications"]
        if entry["target"].get("object_id") == "S3" and entry["target"]["path"] == "state.T"
    )
    document["specifications"].append(pin)
    bound = bind_revision_flowsheet(document)
    assert isinstance(bound, RevisionBinding), bound
    step = planned_step(bound, POLICY)
    assert step.region is not None
    refused = resolve_mass(
        residence_time(
            bound.flowsheet.wiring,
            bound.flowsheet.components,
            declared_phases(bound.flowsheet.units()),
        ),
        spec=bound.spec,
        rows=step.region.row_ids,
        residence_time=1.0,
    )
    assert isinstance(refused, MappingRefusal)
    assert refused.check == "missing" and refused.row.startswith("U-RX:RX-")
    assert refused.message == f"ptc_mapping_invalid({refused.row}, missing)"


# -- B14, B15: the implementation's pencil and its single steps -------------------------------


def ptc_problem(
    state: Mapping[str, float], name: str = "ptc_r1"
) -> tuple[PtcProblem, tuple[str, ...], np.ndarray]:
    """The PTC problem the region's first attempt would solve at `state` (as T04's tests build
    it): the planned region's rows and columns, no split, the registered scales."""
    bound = binding(name)
    step = planned_step(bound, POLICY)
    assert step.region is not None
    mass = region_mass(name)
    assert isinstance(mass, RegionMass)
    free = tuple(step.region.variable_ids)
    x = np.array([state[name] for name in free], dtype=np.float64)
    problem = region_ptc_problem(
        region_mass=mass,
        compiled=compiled(name),
        spec=bound.spec,
        scaling=Scaling.from_spec(bound.spec),
        base=state,
        free=free,
        rows=tuple(step.region.row_ids),
        splits=lifted_splits(revision.instances_of(bound.flowsheet), bound.flowsheet.components),
        regimes={},
        provider=bound.flowsheet.provider,
        policy=POLICY,
        context=context_of(name),
        opening=x,
    )
    return problem, free, x


def pencil(state: Mapping[str, float], name: str = "ptc_r1") -> tuple[np.ndarray, np.ndarray]:
    """`(Ĵ_σ, M̂)`, dense, as `pseudo_step_direction` forms them."""
    problem, _, x = ptc_problem(state, name)
    inner = problem.problem
    sigma = row_signs(inner.row_ids, problem.row_accumulation, PTC_ROW_SIGN)
    jacobian_hat = _row_scaled(_scale_matrix(sp.csc_matrix(inner.jacobian(x)), inner), sigma)
    mass_hat = _scale_matrix(sp.csc_matrix(problem.mass(x)), inner)
    return jacobian_hat.toarray(), mass_hat.toarray()


@pytest.mark.parametrize("bound_name", PTC_R1_BINDINGS)
@pytest.mark.parametrize("name", ROOT_NAMES)
def test_b14_the_finite_eigenvalues_are_the_yamls(name: str, bound_name: str) -> None:
    jacobian_hat, mass_hat = pencil(root_state(name), bound_name)
    values = la.eig(-jacobian_hat, mass_hat, right=False)
    finite = sorted(float(v.real) for v in values if np.isfinite(v))
    assert all(abs(v.imag) <= 1e-12 for v in values if np.isfinite(v))
    expected = sorted(f(v) for v in ROOTS[name]["pencil_finite_eigenvalues_per_s"])
    assert len(finite) == len(expected)
    for got, want in zip(finite, expected, strict=True):
        assert got == pytest.approx(want, rel=1e-9), (finite, expected)


@pytest.mark.parametrize("bound_name", PTC_R1_BINDINGS)
def test_b14_the_step_matrix_at_the_saddle_changes_sign_at_the_singular_step(
    bound_name: str,
) -> None:
    jacobian_hat, mass_hat = pencil(root_state("MID"), bound_name)
    singular = f(REFERENCE["closed_form"]["saddle"]["dtau_singular_over_theta"])

    def sign(factor: float) -> float:
        return float(np.sign(np.linalg.det(mass_hat / (factor * singular) + jacobian_hat)))

    assert sign(0.99) != sign(1.01)
    assert len({sign(factor) for factor in np.linspace(0.5, 0.9, 9)}) == 1
    assert len({sign(factor) for factor in np.linspace(1.1, 2.0, 10)}) == 1


def _mapped(problem: PtcProblem, free: Sequence[str], direction: np.ndarray) -> tuple[float, float]:
    step = dict(zip(free, (float(v) for v in direction), strict=True))
    return -step[f"{OUTLET}.n.B"] / 0.5, step[f"{OUTLET}.T"] / T_SCALE


@pytest.mark.parametrize("bound_name", PTC_R1_BINDINGS)
@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("key", STEP_KEYS)
def test_b15_single_steps_at_the_off_grid_states_are_the_yamls(
    index: int, key: str, bound_name: str
) -> None:
    x1, x2 = OFF_GRID[index]
    state = off_grid_state(x1, x2)
    problem, free, x = ptc_problem(state, bound_name)
    evaluation = problem.problem.residual(x)
    assert evaluation.values is not None
    if key == "newton":
        inner = problem.problem
        scaled = _scale_matrix(sp.csc_matrix(inner.jacobian(x)), inner)
        step_scaled, _ = solve_linear(
            scaled, -inner.scaling.scale_residual(evaluation.values, inner.row_ids)
        )
        direction = inner.scaling.unscale_state(step_scaled, inner.variable_ids)
    else:
        direction = pseudo_step_direction(problem, x, evaluation.values, STEP_TAU[key])
    got = _mapped(problem, free, direction)
    want = (f(SINGLE_STEPS[index][key]["d_x1"]), f(SINGLE_STEPS[index][key]["d_x2"]))
    error = max(abs(g - w) for g, w in zip(got, want, strict=True)) / max(abs(w) for w in want)
    assert error <= 1e-8, (got, want, error)
    step = dict(zip(free, (float(v) for v in direction), strict=True))
    # B04's invariants, exact in the generator's arithmetic (the YAML's `d_n_C` is 0.0), to binary64
    # roundoff here: the LU pivots mix rows, so `dn_C` and `dP` are roundoff, not exact zeros.
    assert f(SINGLE_STEPS[index][f"{key}_dimensional"]["d_n_C"]) == 0.0
    assert abs(step[f"{OUTLET}.n.C"]) <= 1e-15
    assert abs(sum(step[f"{OUTLET}.n.{c}"] for c in COMPONENTS)) <= 1e-15
    assert abs(step[f"{UNIT}.Q"] + CAPACITY * step[f"{OUTLET}.T"]) <= 1e-12
    assert abs(step[f"{OUTLET}.P"]) <= 1e-9


# -- B16: zero flow ---------------------------------------------------------------------------


def _run(name: str) -> tuple[Any, RevisionBinding]:
    bound = binding(name)
    plan, _ = revision.plan_revision(bound, POLICY)
    assert isinstance(plan, ExecutionPlan), plan
    return execute_plan(plan=plan, flowsheet=bound.flowsheet, spec=bound.spec, policy=POLICY), bound


def test_b16_a_dormant_inlet_is_an_exact_regular_root_at_iteration_0() -> None:
    evaluation = unit().evaluate({"inlet": (feed((0.0, 0.0, 0.0)),)}, CONTEXT)
    assert evaluation.status == "ok"
    outlet = evaluation.outlets["outlet"]
    assert outlet.n == (0.0, 0.0, 0.0) and outlet.temperature == 360.0 and evaluation.duty == 0.0
    run, bound = _run("dormant")
    assert run.outcome == "CONVERGED", run.message
    (step,) = [s for s in run.steps if s.kind == "solve_eo"]
    assert isinstance(step.detail, RegionResult)
    assert step.detail.iterations == 0
    state = run.state
    assert [state[f"{OUTLET}.n.{c}"] for c in COMPONENTS] == [0.0, 0.0, 0.0]
    assert state[f"{OUTLET}.T"] == 360.0 and state[f"{UNIT}.Q"] == 0.0
    result = compiled("dormant").jacobian(vector("dormant", state), context_of("dormant"))
    dense = sp.csc_matrix(
        (result.data, result.indices, result.indptr),
        shape=(len(result.row_ids), len(result.col_ids)),
    ).toarray()
    assert np.linalg.matrix_rank(dense) == dense.shape[0] == dense.shape[1]


def test_b16_an_adiabatic_dormant_outlet_is_labelled_with_the_inlet_and_is_singular() -> None:
    evaluation = unit(coolant_flow=0.0).evaluate(
        {"inlet": (feed((0.0, 0.0, 0.0), temperature=375.0),)}, CONTEXT
    )
    assert evaluation.status == "ok"
    assert evaluation.outlets["outlet"].temperature == 375.0 and evaluation.duty == 0.0
    limitations = unit(coolant_flow=0.0).manifest()["validity"]["limitations"]
    assert any("T05 spec §4.7 (a)" in text and "F_c c_c = 0" in text for text in limitations)
    start = revision.initial_state(
        binding("adiabatic_dormant").flowsheet, binding("adiabatic_dormant").spec.variable_ids
    )
    assert isinstance(start, dict)
    entries = jacobian("adiabatic_dormant", start)
    assert all(v == 0.0 for (_, c), v in entries.items() if c == f"{OUTLET}.T")


# -- B17: out of domain -----------------------------------------------------------------------


@pytest.mark.parametrize("temperature", [441.0, 1.0e4])
def test_b17_the_evaluator_refuses_before_the_exponential(temperature: float) -> None:
    """B17 (a) and (c) (§Am1.C): `out_of_domain` with `temperature_outside_domain(outlet)`, and no
    number returned (so none is `inf` or `nan`; `exp` would overflow at 1e4 K)."""
    evaluation = unit().evaluate({"inlet": (feed(temperature=temperature),)}, CONTEXT)
    assert evaluation.status == "out_of_domain"
    assert evaluation.message.splitlines()[0] == "temperature_outside_domain(outlet)"
    assert not evaluation.outlets and evaluation.duty is None


def test_b17_the_evaluator_refuses_an_outlet_pressure_off_the_domain() -> None:
    evaluation = unit(pressure_drop=60_000.0).evaluate({"inlet": (feed(),)}, CONTEXT)
    assert evaluation.status == "out_of_domain"
    assert evaluation.message.splitlines()[0] == "pressure_outside_domain(outlet)"


@pytest.mark.parametrize("temperature", [441.0, 1.0e4])
def test_b17_the_eo_rows_are_a_typed_trial_failure_with_no_inf_or_nan(temperature: float) -> None:
    """B17 (b) and (c) (§Am1.C, §Am1.2): the compiled EO residual (and Jacobian) ends
    `invalid_trial_state`, the frozen `evaluation-result` enum's status for a state off a declared
    domain, with the domain's message (the provider's enthalpy block meets it first); neither is
    `ok`, and no returned number is `inf` or `nan`."""
    state = root_state("LOW")
    state[f"{OUTLET}.T"] = temperature
    x = vector("ptc_r1", state)
    residual = compiled("ptc_r1").residual(x, context_of("ptc_r1"))
    jacobian_result = compiled("ptc_r1").jacobian(x, context_of("ptc_r1"))
    for result in (residual, jacobian_result):
        assert result.status == "invalid_trial_state"
        match = re.search(r"temperature (\S+) K outside \[280\.0, 440\.0\] K", result.message)
        assert match is not None, result.message
        assert float(match.group(1)) == temperature
    assert residual.values is None or all(math.isfinite(v) for v in residual.values)
    assert jacobian_result.data is None or all(math.isfinite(v) for v in jacobian_result.data)


# -- B18: the causal evaluator at the feed ----------------------------------------------------


def test_b18_the_initializer_at_the_ptc_r1_feed() -> None:
    evaluation = unit().evaluate({"inlet": (feed(),)}, CONTEXT)
    assert evaluation.status == "ok"
    assert evaluation.message == INITIALIZER_LIMITATION
    expected = MODEL["causal_initializer_at_feed"]
    outlet = evaluation.outlets["outlet"]
    assert outlet.n[1] == pytest.approx(f(expected["n_B_mol_s"]), rel=1e-14)
    assert outlet.n[0] == pytest.approx(f(expected["n_A_mol_s"]), rel=1e-14)
    assert outlet.n[0] == pytest.approx(1.0 - TRACE - outlet.n[1], rel=1e-14)
    assert outlet.n[2] == f(expected["n_C_mol_s"]) == TRACE
    assert outlet.temperature == 360.0 and outlet.pressure == 1.0e5 and evaluation.duty == 0.0
    limitations = unit().manifest()["validity"]["limitations"]
    assert any(INITIALIZER_LIMITATION in text for text in limitations)
    # Its mole, cooling and pressure rows hold; the energy row does not (it is not a root).
    start = revision.initial_state(binding("ptc_r1").flowsheet, binding("ptc_r1").spec.variable_ids)
    assert isinstance(start, dict)
    values = residuals("ptc_r1", start)
    assert all(abs(values[row(f"CSTR-mole:{c}")]) <= 1e-15 for c in COMPONENTS)
    assert values[row("CSTR-cooling")] == 0.0 and values[row("CSTR-pressure")] == 0.0
    assert abs(values[row("CSTR-duty")]) > 1.0


def test_b18_an_exhausted_non_key_reactant_is_refused() -> None:
    built = unit(stoichiometry=(-1.0, -1.0, 2.0), key_component="B")
    evaluation = built.evaluate({"inlet": (feed((0.0, 0.5, 0.0)),)}, CONTEXT)
    assert evaluation.status == "out_of_domain"
    assert evaluation.message.splitlines()[0] == "reactant_exhausted(A)"


def test_b18_an_inadmissible_declared_outlet_is_refused() -> None:
    """A vapour outlet below its dew point: `inadmissible_phase(outlet, VAPOR)` (T05 §13.3)."""
    built = unit(inlet_phase="LIQUID", reference_temperature=300.0, coolant_temperature=300.0)
    evaluation = built.evaluate({"inlet": (feed(temperature=300.0),)}, CONTEXT)
    assert evaluation.status == "unsupported"
    assert evaluation.message.splitlines()[0] == "inadmissible_phase(outlet, VAPOR)"


# -- B19: the liquid variant ------------------------------------------------------------------


def test_b19_the_liquid_variant_converges_at_iteration_0_and_is_verified() -> None:
    expected = MODEL["liquid_variant_root"]
    run, bound = _run("liquid")
    assert run.outcome == "CONVERGED", run.message
    (step,) = [s for s in run.steps if s.kind == "solve_eo"]
    assert isinstance(step.detail, RegionResult) and step.detail.iterations == 0
    state = run.state
    assert state[f"{OUTLET}.T"] == 300.0 and state[f"{UNIT}.Q"] == 0.0
    assert state[f"{OUTLET}.n.B"] == pytest.approx(f(expected["n_B_mol_s"]), rel=1e-14)
    assert state[f"{OUTLET}.n.A"] == pytest.approx(f(expected["n_A_mol_s"]), rel=1e-14)
    certificate = verify_revision(bound, liquid_variant_revision(), run)
    assert certificate.verification_status == "VERIFIED", [
        (c.id, c.result) for c in certificate.checks if c.result not in ("pass", "not_applicable")
    ]
    ids = [c.id for c in certificate.checks]
    for c in COMPONENTS:
        assert f"material_balance.{UNIT}.{c}" in ids
    assert f"energy_balance.{UNIT}" in ids
    assert f"energy_balance.{UNIT}.cooling_relation" in ids
    assert f"phase_admissibility.{UNIT}.outlet" in ids


def test_b19_the_liquid_reaction_is_thermoneutral() -> None:
    """ADR 0011 D2: every liquid `h_i` is the same function, so `Σ ν_i h_i^L = 0` exactly."""
    temperature, pressure = 300.0, 1.0e5
    assert h_liquid(temperature, pressure, 0) - h_liquid(temperature, pressure, 1) == 0.0
    assert h_vapor(T_F, 0) - h_vapor(T_F, 1) == f(
        REFERENCE["case"]["identities"]["delta_h_reaction_vapor_J_mol"]
    )


# -- the verifier's added checks (§A1.6) ------------------------------------------------------


def test_the_verifier_checks_fail_on_a_wrong_rate() -> None:
    """`material_balance.<U>.<c>` recomputes `r` itself: a state off the mole rows fails it."""
    from openflowsheet.verify.table import MODEL_CHECKS

    assert MODEL_ID in MODEL_CHECKS
    run, bound = _run("liquid")
    state = dict(run.state)
    state[f"{OUTLET}.n.B"] *= 1.0 + 1e-6
    certificate = verify_revision(bound, liquid_variant_revision(), run, state=state)
    failed = {c.id for c in certificate.checks if c.result == "fail"}
    assert f"material_balance.{UNIT}.B" in failed


def test_the_verifier_checks_fail_on_a_wrong_coolant_duty() -> None:
    """`energy_balance.<U>.cooling_relation` reads the revision's `F_c`, `c_c`, `T_c`: a duty off
    the cooling relation by 1 W fails it (a 1 % UA error at LOW is ≥ 0.98 W, §C.1 B11)."""
    run, bound = _run("liquid")
    state = dict(run.state)
    state[f"{UNIT}.Q"] += 1.0
    certificate = verify_revision(bound, liquid_variant_revision(), run, state=state)
    failed = {c.id for c in certificate.checks if c.result == "fail"}
    assert f"energy_balance.{UNIT}.cooling_relation" in failed
