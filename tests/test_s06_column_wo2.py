"""S06 WO-2: the solve path of the inverse column specifications — the endpoint's `u⁰` and
continued slots, `solve_column` on the registered sets, §8's items 1–4, edge 3 on the inverse
slots, §7.3's unreached report and §7.5's records.

Every expectation is a value of `docs/derivations/scripts/s06_reference.json` (the design lane's
50-digit generator), of `s02_reference.json` (the matched sets' and U1/U2's root), a code or bound
of `docs/derivations/S06-spec.md`, or arithmetic done here independently of the implementation.
Each test names the assertion of the spec's §10 it closes: A05–A11, A12 (on the answers), A13
(the records), A14, A15. A16 is S01's and S02's suites, run beside this module.
"""

from __future__ import annotations

import json
from fractions import Fraction
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT
from test_s06_column_wo1 import (
    COMPONENTS,
    CONDENSER,
    J_CASES,
    PROVIDER,
    REBOILER,
    REFERENCE,
    U_SETS,
    UNIT,
    V_SETS,
)

import openflowsheet.models.syn001.column_solve as solve_module
import openflowsheet.orchestrator.region as region_module
from openflowsheet.compile.reference import row_values
from openflowsheet.models.syn001 import FLOW_TOLERANCE
from openflowsheet.models.syn001.cascade import (
    CascadeFailure,
    liquid_id,
    liquid_total_id,
    mixed_id,
    stage_duty_id,
    stage_pressure_id,
    stage_temperature_id,
    vapor_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.cascade_solve import AcceptanceDefectError
from openflowsheet.models.syn001.column import (
    ColumnSpec,
    _inflow,
    _inlet_columns,
    distillate_id,
    distillate_total_id,
    product_flow_id,
    product_total_id,
    profile_initial,
    purity_flow_id,
    reflux_fraction_id,
    reflux_id,
)
from openflowsheet.models.syn001.column_solve import (
    CONTINUED_KIND,
    DECLARATION_CONTEXT,
    FD_COLUMN_SCALE,
    QUOTIENT_SLACK,
    BubblePointEndpoint,
    ColumnSolution,
    acceptance_failures,
    bubble_point_endpoint,
    compile_column,
    continuation,
    overall_closure,
    slots,
    solve_column,
    solve_target,
    spec_values,
    stage_unit,
    target_bound,
)
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS
from openflowsheet.orchestrator.region import KIND_TOLERANCE, RegionAttempt, RegionResult

S02_REFERENCE: dict[str, Any] = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "s02_reference.json").read_bytes()
)

#: §10's state tolerance (S02 §10's): flows rel 1e-6 + 10·τ_flow, T 1e-4 K, Q 1e-2 W, ratios
#: rel 1e-6; `u` as a flow.
FLOW_REL, FLOW_ABS, T_ABS, Q_ABS = 1e-6, 10 * FLOW_TOLERANCE, 1e-4, 1e-2
#: §10 A09: the tolerance and the floor the measurement must clear.
FD_TOLERANCE, FD_FLOOR = 1e-6, 1e-8

ALL_SETS: dict[str, ColumnSpec] = {**J_CASES, **V_SETS, **U_SETS}
INVERSE = ("purity", "recovery", "temperature")


def _record(name: str) -> dict[str, Any]:
    for group in ("cases", "matched", "unreached"):
        if name in REFERENCE[group]:
            record: dict[str, Any] = REFERENCE[group][name]
            return record
    raise KeyError(name)


def _feeds(spec: ColumnSpec) -> list[float]:
    """`F_c` summed here in `inlets()` order (S06 §1), independently of the implementation."""
    feeds = [0.0] * len(COMPONENTS)
    for inlet in spec.inlets():
        for i, a in enumerate(inlet.state.n):
            feeds[i] = feeds[i] + a
    return feeds


def _total(spec: ColumnSpec) -> float:
    total = 0.0
    for f in _feeds(spec):
        total = total + f
    return total


def _inverse_ends(spec: ColumnSpec) -> list[str]:
    return [
        end
        for end in (CONDENSER, REBOILER)
        if (given := spec.end_specification(end)) is not None and given.kind in INVERSE
    ]


def _quantity(spec: ColumnSpec, end: str, state: Any) -> float:
    """§7.3's formula, written here: `n_c / P`, `n_c / F_c` or `T_s`."""
    given = spec.end_specification(end)
    assert given is not None
    if given.kind == "temperature":
        assert given.stage is not None
        return float(state[stage_temperature_id(UNIT, given.stage)])
    assert given.component is not None
    i = COMPONENTS.index(given.component)
    if end == REBOILER:
        flow = state[liquid_id(UNIT, spec.stage_count, given.component)]
        total = state[liquid_total_id(UNIT, spec.stage_count)]
    elif spec.total_condenser:
        flow, total = state[distillate_id(UNIT, given.component)], state[distillate_total_id(UNIT)]
    else:
        flow, total = state[vapor_id(UNIT, 1, given.component)], state[vapor_total_id(UNIT, 1)]
    return float(flow) / (_feeds(spec)[i] if given.kind == "recovery" else float(total))


def stages_state(spec: ColumnSpec, stages: list[dict[str, Any]]) -> dict[str, float]:
    """A recorded `stages` list (the generator's `(l, v, L, V, T, Q)` per equilibrium stage and
    `(φ, r, d, T, Q)` at a total condenser) on `spec`'s columns: `P_j` at `P_j*`, `D = Σ d`, `m`
    from the `mix` rows, inlets as given, and per purity end `u = F·n_c/P` (§2's definition)."""
    values = _inlet_columns(spec)
    for record in stages:
        j = record["stage"]
        if record.get("kind") == "total_condenser":
            for c, r, d in zip(COMPONENTS, record["reflux"], record["distillate"], strict=True):
                values[reflux_id(UNIT, c)] = float(r)
                values[distillate_id(UNIT, c)] = float(d)
            values[reflux_fraction_id(UNIT)] = float(record["phi"])
            values[distillate_total_id(UNIT)] = sum(float(d) for d in record["distillate"])
        else:
            for c, liquid, vapor in zip(COMPONENTS, record["l"], record["v"], strict=True):
                values[liquid_id(UNIT, j, c)] = float(liquid)
                values[vapor_id(UNIT, j, c)] = float(vapor)
            values[liquid_total_id(UNIT, j)] = float(record["L"])
            values[vapor_total_id(UNIT, j)] = float(record["V"])
        values[stage_temperature_id(UNIT, j)] = float(record["T"])
        values[stage_duty_id(UNIT, j)] = float(record["Q"])
        values[stage_pressure_id(UNIT, j)] = spec.pressures[j - 1]
    for j in spec.equilibrium_stages():
        for c in COMPONENTS:
            values[mixed_id(UNIT, j, c)] = sum(values[name] for name in _inflow(spec, j, c))
    for end in _inverse_ends(spec):
        given = spec.end_specification(end)
        assert given is not None
        if given.kind == "purity":
            assert given.component is not None
            flow = values[product_flow_id(spec, end, given.component)]
            values[purity_flow_id(UNIT, spec.end_stage(end))] = (
                _total(spec) * flow / values[product_total_id(spec, end)]
            )
    return values


def deviation_from(spec: ColumnSpec, expected: dict[str, float], state: Any) -> dict[str, float]:
    """The worst error of `state` against `expected`, per column class in units of §10's state
    tolerance (≤ 1 passes): flows (`l, v, L, V, r, d, D, m, u`), `T`, `Q`, and `φ` (rel 1e-6)."""
    worst = {"flow": 0.0, "T": 0.0, "Q": 0.0, "ratio": 0.0}
    for name, target in expected.items():
        if name.endswith((".T", ".Q", ".phi", ".P")) or ".n." in name or ".flow." in name:
            continue
        error = abs(state[name] - target)
        worst["flow"] = max(worst["flow"], error / (FLOW_REL * abs(target) + FLOW_ABS))
    for j in range(1, spec.stage_count + 1):
        for key, column, tolerance in (
            ("T", stage_temperature_id, T_ABS),
            ("Q", stage_duty_id, Q_ABS),
        ):
            name = column(UNIT, j)
            worst[key] = max(worst[key], abs(state[name] - expected[name]) / tolerance)
    if spec.total_condenser:
        phi = reflux_fraction_id(UNIT)
        worst["ratio"] = abs(state[phi] - expected[phi]) / (FLOW_REL * abs(expected[phi]))
    return worst


def expected_root(name: str) -> dict[str, float]:
    """The root a set must return: `ref.cases.*.target` for a J case, S02's registered root of
    the base (`s02ref.cases.<base>.target`) for a matched set and for U1, U2 (A07, A11)."""
    spec = ALL_SETS[name]
    if name in J_CASES:
        return stages_state(spec, REFERENCE["cases"][name]["target"]["stages"])
    base = _record(name)["base"]
    return stages_state(spec, S02_REFERENCE["cases"][base]["target"]["stages"])


_ENDPOINT: dict[str, BubblePointEndpoint] = {}
_SOLVED: dict[str, ColumnSolution | CascadeFailure] = {}


def endpoint(name: str) -> BubblePointEndpoint:
    if name not in _ENDPOINT:
        spec = ALL_SETS[name]
        initial = profile_initial(spec, PROVIDER, DECLARATION_CONTEXT)
        assert not isinstance(initial, CascadeFailure), initial
        found = bubble_point_endpoint(spec, PROVIDER, initial)
        assert isinstance(found, BubblePointEndpoint), found
        _ENDPOINT[name] = found
    return _ENDPOINT[name]


def solved(name: str) -> ColumnSolution:
    """`solve_column` on a registered set, once per session."""
    if name not in _SOLVED:
        _SOLVED[name] = solve_column(ALL_SETS[name], PROVIDER)
    answer = _SOLVED[name]
    assert isinstance(answer, ColumnSolution), answer
    return answer


def _regimes(spec: ColumnSpec, answer: ColumnSolution) -> dict[int, Any]:
    return dict(zip(spec.equilibrium_stages(), answer.signature, strict=True))


def deviation(name: str) -> float:
    """§10 "needs a fact": the worst column error of the set's `solve_column` root against its
    registered root, in units of the state tolerance."""
    worst = deviation_from(ALL_SETS[name], expected_root(name), solved(name).state)
    return max(worst.values())


def _p0_tolerance(spec: ColumnSpec, stage: str, record: dict[str, Any]) -> float:
    """A05's `p⁰` tolerance: T 1e-4 K, Q 1e-2 W, flows rel 1e-6."""
    if record["kind"] == "Q":
        return Q_ABS
    if record["kind"] == "temperature":
        return T_ABS
    return FLOW_REL * abs(_expected_p0(spec, record))


def _expected_p0(spec: ColumnSpec, record: dict[str, Any]) -> float:
    """The generator's `p0` on the implementation's slot column: a purity slot pins `u = F·x`, so
    its `p⁰` is `F·q⁰` (the generator has no `u`); every other `p0` is the column's value."""
    if record["kind"] == "purity":
        return _total(spec) * float(record["q0"])
    return float(record["p0"])


def _letter(record: dict[str, Any]) -> str:
    kind: str = record["kind"]
    return CONTINUED_KIND[kind] if kind in INVERSE else kind


FLOWING = (*sorted(J_CASES), *sorted(V_SETS))


# -- A05: the endpoint's u⁰ and continued slots --------------------------------------------------


@pytest.mark.parametrize("name", FLOWING)
def test_a05_the_endpoint(name: str) -> None:
    """A05: `x⁰` (S02's endpoint at the CMO end ratio) is the generator's `bubble_point` within
    the state tolerance (J cases; the V-sets' `x⁰` is their base's, checked through `p⁰`), `u⁰`
    included; every target row except the continued slot rows within its kind tolerance at
    `x⁰`, the purity definition row among them."""
    spec = ALL_SETS[name]
    found = endpoint(name)
    if name in J_CASES:
        expected = stages_state(spec, REFERENCE["cases"][name]["bubble_point"]["stages"])
        worst = deviation_from(spec, expected, found.state)
        assert max(worst.values()) <= 1.0, worst
    target = compile_column(spec, PROVIDER).spec
    initial = profile_initial(spec, PROVIDER, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure)
    continued_rows = {s.target_row for s in slots(spec, initial.profile) if s.parameter}
    values = row_values(target, found.state)
    assert continued_rows <= set(values)
    over = {
        row: abs(value) / KIND_TOLERANCE[target.row_kinds[row]]
        for row, value in values.items()
        if row not in continued_rows
    }
    assert max(over.values()) <= 1.0, max(over.items(), key=lambda item: item[1])
    for end in _inverse_ends(spec):
        given = spec.end_specification(end)
        assert given is not None
        if given.kind == "purity":
            definition = f"{UNIT}:stage:{spec.end_stage(end)}:spec:purity_definition"
            assert abs(values[definition]) <= KIND_TOLERANCE["molar_flow_squared"]


@pytest.mark.parametrize("name", FLOWING)
def test_a05_the_continued_slots_and_p0(name: str) -> None:
    """A05: the continued slots are `ref.*.continued`'s stages and kinds (inverse slots `T`, `N`,
    `U`), in stage order, exactly `continuation`'s parameter ids; `p⁰` is the slot column at
    `x⁰` (`T_s⁰`, `n_c⁰`, `u⁰`) and equals the generator's `p0` (`F·q⁰` for `u`)."""
    spec = ALL_SETS[name]
    record = _record(name)["continued"]
    answer = solved(name)
    replaced = {s.stage: s for s in slots(spec, answer.initial.profile) if s.parameter}
    assert sorted(replaced) == sorted(int(j) for j in record)
    assert tuple(answer.continued) == continuation(spec, answer.initial.profile).parameter_ids
    for stage, expected in record.items():
        slot = replaced[int(stage)]
        assert slot.continued == _letter(expected), stage
        p0 = answer.continued[slot.parameter]
        assert p0 == answer.endpoint.state[slot.variable]
        error = abs(p0 - _expected_p0(spec, expected))
        assert error <= _p0_tolerance(spec, stage, expected), (stage, error)


# -- A06, A07, A08: through solve_column ---------------------------------------------------------


def _spec_value_tolerance(key: str, expected: float) -> float:
    if key.endswith("_duty"):
        return Q_ABS
    if key.endswith("_ratio"):
        return FLOW_REL * abs(expected)
    return FLOW_REL * abs(expected) + FLOW_ABS


@pytest.mark.parametrize("name", sorted(J_CASES))
def test_a06_the_registered_cases(name: str) -> None:
    """A06: J1–J8 through `solve_column` are `CONVERGED` with every stage `TWO_PHASE` at
    `ref.cases.*.target` (state tolerance, `u` as a flow), products and `spec_values` as
    recorded, and each inverse quantity within §8 item 4's bound of its target; no unreached
    entry."""
    spec = J_CASES[name]
    reference = REFERENCE["cases"][name]
    answer = solved(name)
    assert answer.outcome == "CONVERGED", answer.cause
    assert answer.signature == ("TWO_PHASE",) * len(spec.equilibrium_stages())
    recorded = list(reference["signature"])
    if spec.total_condenser:
        # The generator lists the total condenser (no split here) as `SATURATED_LIQUID`.
        assert recorded.pop(0) == "SATURATED_LIQUID"
    assert list(answer.signature) == recorded
    assert deviation(name) <= 1.0
    values = spec_values(spec, answer.state)
    for key, text in reference["spec_values"].items():
        expected = float(text)
        assert abs(values[key] - expected) <= _spec_value_tolerance(key, expected), key
    for end, inverse in reference["inverse_values"].items():
        key = f"{end}_{inverse['kind']}"
        bound = target_bound(spec, end, answer.state)
        assert abs(values[key] - float(inverse["value"])) <= bound, key
        assert values[key] == _quantity(spec, end, answer.state)
    for port, key in (("top_product", CONDENSER), ("bottom_product", REBOILER)):
        flows = [
            answer.state[name]
            for name in (
                [distillate_id(UNIT, c) for c in COMPONENTS]
                if key == CONDENSER and spec.total_condenser
                else [vapor_id(UNIT, 1, c) for c in COMPONENTS]
                if key == CONDENSER
                else [liquid_id(UNIT, spec.stage_count, c) for c in COMPONENTS]
            )
        ]
        for got, text in zip(flows, reference["target"][port], strict=True):
            assert abs(got - float(text)) <= FLOW_REL * abs(float(text)) + FLOW_ABS, port
    assert answer.unreached == ()


@pytest.mark.parametrize("name", sorted(V_SETS))
def test_a07_each_matched_set_returns_s02s_root(name: str) -> None:
    """A07: each matched set (inverse values at S02's M1 root) returns `s02ref.cases.M1.target`
    within the state tolerance."""
    answer = solved(name)
    assert answer.outcome == "CONVERGED" and set(answer.signature) == {"TWO_PHASE"}
    assert deviation(name) <= 1.0


@pytest.mark.parametrize("name", FLOWING)
def test_a08_closure_and_section_8(name: str) -> None:
    """A08: overall component and energy closure within `n_rows·τ_kind`, and §8 (items 1–4
    included) passes at the converged answer."""
    spec = ALL_SETS[name]
    answer = solved(name)
    assert answer.outcome == "CONVERGED"
    target = compile_column(spec, PROVIDER)
    rows = len(target.spec.equation_ids)
    closure = overall_closure(spec, PROVIDER, answer.state)
    assert max(abs(e) for e in closure.components) <= rows * KIND_TOLERANCE["molar_flow"]
    assert abs(closure.energy) <= rows * KIND_TOLERANCE["heat_rate"]
    regimes = _regimes(spec, answer)
    assert acceptance_failures(spec, PROVIDER, target.spec, answer.state, regimes) == ()
    for end in _inverse_ends(spec):
        given = spec.end_specification(end)
        assert given is not None
        quantity = _quantity(spec, end, answer.state)
        assert abs(quantity - given.value) <= target_bound(spec, end, answer.state)


def test_a08_the_bounds_are_section_8s() -> None:
    """A08 / §8 item 4: the bounds are `1e-6 K`, `τ_mf/F_c + 2⁻⁵²` and `(τ_mf + τ_eq/P)/F +
    2⁻⁵²` with `τ_mf = 3.1e-8` mol/s and `τ_eq = 9.3e-8` (mol/s)²."""
    assert QUOTIENT_SLACK == 2.0**-52
    assert KIND_TOLERANCE["temperature"] == 1e-6
    assert KIND_TOLERANCE["molar_flow"] == pytest.approx(3.1e-8, rel=1e-15)
    assert KIND_TOLERANCE["molar_flow_squared"] == pytest.approx(9.3e-8, rel=1e-15)
    state = solved("J1").state
    total = state[vapor_total_id(UNIT, 1)]
    expected = (3.1e-8 + 9.3e-8 / total) / _total(J_CASES["J1"]) + 2.0**-52
    assert target_bound(J_CASES["J1"], CONDENSER, state) == pytest.approx(expected, rel=1e-14)
    expected = 3.1e-8 / 0.3 + 2.0**-52
    assert target_bound(J_CASES["J2"], CONDENSER, state) == pytest.approx(expected, rel=1e-14)
    assert target_bound(J_CASES["J3"], REBOILER, state) == 1e-6


@pytest.mark.parametrize(
    ("name", "end", "column", "shift"),
    [
        ("J3", REBOILER, stage_temperature_id(UNIT, 6), 2e-6),
        ("J2", CONDENSER, distillate_id(UNIT, "A"), 1e-6),
        ("J1", CONDENSER, vapor_id(UNIT, 1, "A"), 1e-6),
    ],
)
def test_a08_item_4_refuses_what_it_names(name: str, end: str, column: str, shift: float) -> None:
    """§8 item 4 names a quantity off its target: the converged state with the quantity's column
    moved past the bound fails with `S06 §8.4` on that end."""
    spec = ALL_SETS[name]
    answer = solved(name)
    state = {**answer.state, column: answer.state[column] + shift}
    given = spec.end_specification(end)
    assert given is not None
    assert abs(_quantity(spec, end, state) - given.value) > target_bound(spec, end, state)
    target = compile_column(spec, PROVIDER).spec
    failures = acceptance_failures(spec, PROVIDER, target, state, _regimes(spec, answer))
    assert any(f.startswith(f"S06 §8.4: {end} {given.kind}") for f in failures), failures


# -- A09: the compiled Jacobian on the new rows --------------------------------------------------


def fd_matrix(spec: ColumnSpec, state: Any) -> tuple[Any, tuple[str, ...], tuple[str, ...]]:
    """§10 A09: `|D_r⁻¹ J D_x − FD|` per entry, relative to `max(1, |exact|)`, with central
    differences at `h = 1e-6·max(D_x, |x|)` (R-516); rows and columns in declaration order."""
    target = compile_column(spec, PROVIDER)
    problem, compiled = target.spec, target.compiled
    context = target.context()
    x = np.array([state[name] for name in problem.variable_ids], dtype=np.float64)
    result = compiled.jacobian(x, context)
    assert result.status == "ok" and tuple(result.col_ids) == problem.variable_ids
    exact = np.zeros((len(result.row_ids), len(result.col_ids)))
    for column in range(len(result.col_ids)):
        for k in range(result.indptr[column], result.indptr[column + 1]):
            exact[result.indices[k], column] = result.data[k]
    d_x = np.array([FD_COLUMN_SCALE[problem.variable_kinds[n]] for n in problem.variable_ids])
    d_r = np.array([REGISTERED_NOMINALS[problem.row_kinds[n]] for n in problem.equation_ids])
    errors = np.zeros_like(exact)
    for column in range(len(x)):
        h = 1e-6 * max(d_x[column], abs(x[column]))
        up, down = x.copy(), x.copy()
        up[column] += h
        down[column] -= h
        f_up, f_down = compiled.residual(up, context), compiled.residual(down, context)
        assert f_up.values is not None and f_down.values is not None
        fd = (np.asarray(f_up.values) - np.asarray(f_down.values)) / (2 * h)
        scaled_exact = exact[:, column] * d_x[column] / d_r
        errors[:, column] = np.abs(fd * d_x[column] / d_r - scaled_exact) / np.maximum(
            1.0, np.abs(scaled_exact)
        )
    return errors, problem.equation_ids, problem.variable_ids


def fd_floor(name: str, point: str) -> tuple[float, float]:
    """A09's measurement: the worst entry over every row, and over the new rows (each inverse
    slot row, the purity definition row) and the new column `u`."""
    spec = J_CASES[name]
    state = endpoint(name).state if point == "x0" else expected_root(name)
    errors, rows, columns = fd_matrix(spec, state)
    new = (*INVERSE, "purity_definition")
    new_rows = [k for k, row in enumerate(rows) if ":spec:" in row and row.endswith(new)]
    new_columns = [k for k, column in enumerate(columns) if column.endswith(".purity_flow")]
    assert new_rows, name
    worst_new = float(errors[new_rows, :].max())
    if new_columns:
        worst_new = max(worst_new, float(errors[:, new_columns].max()))
    return float(errors.max()), worst_new


@pytest.mark.parametrize("name", ["J1", "J2", "J6"])
@pytest.mark.parametrize("point", ["x0", "root"])
def test_a09_the_compiled_jacobian(name: str, point: str) -> None:
    """A09 at `x⁰` and at the root (`ref.target` rounded to binary64, `u` from its definition) of
    J1 (`u` and its definition row), J2 (recovery on `d`) and J6 (the `T_c` slot): within 1e-6,
    and the floor under 1e-8 (measured: `docs/C11_DECISIONS.md`)."""
    worst, worst_new = fd_floor(name, point)
    assert worst <= FD_TOLERANCE
    assert worst <= FD_FLOOR, worst
    assert worst_new <= FD_FLOOR, worst_new


# -- A10: edge 3 carries the inverse slots -------------------------------------------------------


def _dyadic(value: Fraction) -> bool:
    return 0 <= value <= 1 and value.denominator & (value.denominator - 1) == 0


@pytest.mark.parametrize("name", ["J1", "J4", "J6"])
def test_a10_forced_edge_3_from_x0(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """A10: edge 3 forced from `x⁰` (S02 A13b's harness): every re-binding names exactly the
    replaced slots, each inverse slot's parameter among them; `p⁰` is A05's; λ dyadic; the λ = 1
    instance is the target's; the recovery is `CONVERGED` at `ref.cases.*.target`."""
    rebound: list[dict[str, float]] = []
    real = region_module.rebind

    def rebind(spec: Any, values: dict[str, float]) -> Any:
        rebound.append(dict(values))
        return real(spec, values)

    monkeypatch.setattr(solve_module, "eo_recovery_due", lambda outcome, budget, *, attempts: True)
    monkeypatch.setattr(region_module, "rebind", rebind)
    spec = J_CASES[name]
    found = endpoint(name)
    initial = profile_initial(spec, PROVIDER, DECLARATION_CONTEXT)
    assert not isinstance(initial, CascadeFailure)
    target = compile_column(spec, PROVIDER)
    result, failed, regimes = solve_target(spec, PROVIDER, target, found.state, initial.profile)
    assert result.outcome == "CONVERGED" and failed is not None
    assert set(regimes.values()) == {"TWO_PHASE"}
    expected = continuation(spec, initial.profile).parameter_ids
    by_id = {s.parameter: s for s in slots(spec, initial.profile) if s.parameter}
    inverse_parameters = {p for p, s in by_id.items() if s.continued in ("T", "N", "U")}
    assert len(inverse_parameters) == len(_inverse_ends(spec))
    assert inverse_parameters <= set(expected)
    assert rebound and all(tuple(level) == expected for level in rebound)
    for parameter, value in rebound[0].items():
        slot = by_id[parameter]
        assert value == found.state[slot.variable], parameter
        record = REFERENCE["cases"][name]["continued"][str(slot.stage)]
        error = abs(value - _expected_p0(spec, record))
        assert error <= _p0_tolerance(spec, str(slot.stage), record), parameter
    record = result.homotopy
    assert record is not None and record.lambda_reached == 1
    assert all(_dyadic(trial.lambda_value) for trial in record.trials)
    assert result.branch_provenance[len(failed.branch_provenance)]["core"] == "homotopy"
    at_one = result.contexts[0].evaluation_context
    compiled = target.compiled.metadata
    assert (at_one.model_version, at_one.constants_sha256) == (
        compiled.model_version,
        compiled.constants_sha256,
    )
    worst = deviation_from(spec, expected_root(name), result.state)
    assert max(worst.values()) <= 1.0, worst


# -- A11: the unreached sets ---------------------------------------------------------------------


def a11_branch(name: str) -> dict[str, Any]:
    """A11's record: the branch `solve_column` took on U1/U2 and what it reported."""
    answer = solved(name)
    homotopy = answer.result.homotopy
    return {
        "outcome": answer.outcome,
        "cause": answer.cause,
        "recovered_from": None if answer.recovered_from is None else answer.recovered_from.outcome,
        "lambda_reached": None if homotopy is None else str(homotopy.lambda_reached),
        "unreached": [
            {"code": u.code, "lambda_reached": u.lambda_reached, "value": u.value}
            for u in answer.unreached
        ],
    }


def _lambda_state(answer: ColumnSolution) -> dict[str, float]:
    """The state of edge 3's last accepted λ, rebuilt here: the failed solve's opening with the
    accepted corrector's `x` on the homotopy's free columns."""
    failed, record = answer.recovered_from, answer.result.homotopy
    assert failed is not None and failed.opening is not None and record is not None
    trial = [t for t in record.trials if t.accepted and t.lambda_value == record.lambda_reached][-1]
    state = dict(failed.opening[0])
    state.update(
        zip(record.variable_ids, (float(v) for v in trial.corrector.result.x), strict=False)
    )
    return state


@pytest.mark.parametrize("name", sorted(U_SETS))
def test_a11_the_unreached_sets(name: str) -> None:
    """A11: U1 and U2 through `solve_column` are either `CONVERGED` at `s02ref.cases.M2.target`
    passing §8, or a non-`CONVERGED` outcome whose `unreached` holds one entry per inverse end
    with its code, and, where `lambda_reached` is not `None`, `value` equal bit for bit to §7.3's
    quantity at that λ's state. Never an empty `unreached` on a failure."""
    spec = U_SETS[name]
    answer = solved(name)
    if answer.outcome == "CONVERGED":
        assert answer.unreached == ()
        assert deviation(name) <= 1.0
        target = compile_column(spec, PROVIDER).spec
        regimes = _regimes(spec, answer)
        assert acceptance_failures(spec, PROVIDER, target, answer.state, regimes) == ()
        return
    ends = _inverse_ends(spec)
    assert [u.end for u in answer.unreached] == ends
    state = _lambda_state(answer) if answer.unreached[0].lambda_reached is not None else None
    for entry, end in zip(answer.unreached, ends, strict=True):
        given = spec.end_specification(end)
        assert given is not None
        assert entry.code == f"inverse_specification_not_reached({given.kind}:{end})"
        assert (entry.kind, entry.target) == (given.kind, given.value)
        assert entry.attribute == (given.stage if given.kind == "temperature" else given.component)
        if entry.lambda_reached is None:
            assert entry.value is None
            continue
        assert state is not None and answer.result.homotopy is not None
        reached = Fraction(entry.lambda_reached)
        assert reached == answer.result.homotopy.lambda_reached and _dyadic(reached)
        assert entry.value == _quantity(spec, end, state)


# -- A12 on the answers --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ALL_SETS))
def test_a12_no_warning_on_the_answers(name: str) -> None:
    """A12: `solve_column`'s answers for J1–J8, the V-sets, U1 and U2 carry no warning."""
    assert solved(name).warnings == ()


# -- A13: the records ----------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["J1", "J2", "J3"])
def test_a13_the_records(name: str) -> None:
    """A13 / §7.5: per inverse end, the kind, the attribute and the user's value; `π* =
    fl(x*·F)`, `ν* = fl(r*·F_c)`, `T*`, with `F`, `F_c` summed here in `inlets()` order, at the
    declaration's pinned parameter id; `q⁰` and `p⁰` as A05."""
    spec = J_CASES[name]
    answer = solved(name)
    pinned = compile_column(spec, PROVIDER).spec.parameters
    assert [r.end for r in answer.inverse] == _inverse_ends(spec)
    for record in answer.inverse:
        given = spec.end_specification(record.end)
        assert given is not None
        assert (record.kind, record.value) == (given.kind, given.value)
        if given.kind == "temperature":
            assert record.attribute == given.stage and record.reference is None
            assert record.parameter == given.value
        else:
            assert record.attribute == given.component and given.component is not None
            feed = _feeds(spec)[COMPONENTS.index(given.component)]
            reference = _total(spec) if given.kind == "purity" else feed
            assert record.reference == reference
            assert record.parameter == given.value * reference
        assert pinned[record.parameter_id] == record.parameter
        assert answer.continued[record.parameter_id] == record.p0
        reference_record = REFERENCE["cases"][name]["continued"][str(spec.end_stage(record.end))]
        q0 = float(reference_record["q0"])
        assert record.q0 == _quantity(spec, record.end, answer.endpoint.state)
        q0_tolerance = T_ABS if given.kind == "temperature" else FLOW_REL * abs(q0)
        assert abs(record.q0 - q0) <= q0_tolerance
        error = abs(record.p0 - _expected_p0(spec, reference_record))
        assert error <= _p0_tolerance(spec, "", reference_record)


# -- A14: the phase scope ------------------------------------------------------------------------


def _stubbed(monkeypatch: pytest.MonkeyPatch, spec: ColumnSpec, stage: int, regime: str) -> None:
    """`run_region` stubbed to a `CONVERGED` result at its start state, every equilibrium stage
    `TWO_PHASE` but `stage`, which is `regime`."""

    def run_region(target: Any, provider: Any, state: Any, policy: Any, **_: Any) -> RegionResult:
        signature = tuple(
            (stage_unit(UNIT, j), regime if j == stage else "TWO_PHASE")
            for j in spec.equilibrium_stages()
        )
        attempt = RegionAttempt(signature=signature, outcome="CONVERGED", iterations=0)
        return RegionResult(outcome="CONVERGED", state=dict(state), attempts=(attempt,))

    monkeypatch.setattr(solve_module, "run_region", run_region)


def test_a14_a_single_phase_specified_stage_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A14 / §8 item 3: J5 with stage 5 single-phase at a `CONVERGED` (stubbed) result that
    passes every defect clause (`acceptance_failures` stubbed to `()`, S06 §17.3) is
    `CAPABILITY_UNAVAILABLE` `unsupported(temperature_specification_on_single_phase_stage:5)`,
    never a success and not a defect."""
    _stubbed(monkeypatch, J_CASES["J5"], 5, "LIQUID")
    monkeypatch.setattr(solve_module, "acceptance_failures", lambda *_: ())
    answer = solve_column(J_CASES["J5"], PROVIDER)
    assert isinstance(answer, CascadeFailure), answer
    assert answer.outcome == "CAPABILITY_UNAVAILABLE"
    assert answer.cause == "unsupported(temperature_specification_on_single_phase_stage:5)"


def test_a14_a_defective_single_phase_specified_stage_is_a_defect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A14 / S06 §17.3 (R-610): J5's stubbed state, not a root, with stage 5 `LIQUID` fails
    both §8 item 3 and the defect clauses; the defect is the answer, never the scope limit."""
    _stubbed(monkeypatch, J_CASES["J5"], 5, "LIQUID")
    with pytest.raises(AcceptanceDefectError) as raised:
        solve_column(J_CASES["J5"], PROVIDER)
    assert any(failure.startswith("row ") for failure in raised.value.failures), (
        raised.value.failures
    )


def test_a14_a_vapour_end_under_purity_is_a_defect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A14 / §8 item 2: J1 with stage 1 `VAPOR` at a `CONVERGED` (stubbed) result is a defect."""
    _stubbed(monkeypatch, J_CASES["J1"], 1, "VAPOR")
    with pytest.raises(AcceptanceDefectError) as raised:
        solve_column(J_CASES["J1"], PROVIDER)
    assert "§8.2: condenser stage 1 under purity is VAPOR" in raised.value.failures


# -- A15: reproducibility ------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["J1", "J6"])
def test_a15_solved_twice_is_identical(name: str) -> None:
    """A15: J1 and J6 solved twice: identical `state_sha256` (`x_K`, `x⁰`, answer), states and
    records (§7.5, provenance, signatures, root fingerprint)."""
    first = solve_column(J_CASES[name], PROVIDER)
    second = solve_column(J_CASES[name], PROVIDER)
    assert isinstance(first, ColumnSolution) and isinstance(second, ColumnSolution)
    assert first.outcome == "CONVERGED"
    assert (first.initial_sha256, first.endpoint_sha256, first.final_sha256) == (
        second.initial_sha256,
        second.endpoint_sha256,
        second.final_sha256,
    )
    assert first.state == second.state
    assert (first.inverse, first.unreached, first.continued) == (
        second.inverse,
        second.unreached,
        second.continued,
    )
    assert repr([dict(i) for i in first.result.branch_provenance]) == repr(
        [dict(i) for i in second.result.branch_provenance]
    )
    assert first.result.signatures == second.result.signatures
    assert repr(first.result.root_fingerprint) == repr(second.result.root_fingerprint)
