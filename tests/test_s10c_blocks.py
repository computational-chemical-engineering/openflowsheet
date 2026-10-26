"""S10-C WO-3, gate G6: the column's γ–φ-IG property blocks (design note
`docs/derivations/S10C-design.md` §4.7; specification `docs/derivations/S10C-spec.md` §5.4,
assertions S10C.A30–A36; mutations M1, M5).

The expectations are the 50-digit generator's (`benchmarks/s10c/reference_values.yaml`, `blocks`)
and the provider's own `evaluate_phase`; the finite differences use §5.4's registered stencils,
which replace the design note's step rule (finding F-1). Not tested here: C-MW's Newton
iterations under M1 (A35's record), which needs WO-4's column solve.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from functools import cache
from typing import Any

import numpy as np
import pytest
import yaml
from conftest import REPO_ROOT

import openflowsheet.models.syn001.gamma_phi_blocks as gamma_phi_blocks
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.cascade import (
    InletState,
    SideFeed,
    declared_problem,
    liquid_id,
    liquid_total_id,
    stage_pressure_id,
    stage_row_id,
    stage_temperature_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.column import (
    ColumnSpec,
    EndSpecification,
    declared_rows,
    regime_form,
)
from openflowsheet.models.syn001.gamma_phi_blocks import (
    GammaPhiLnKBlock,
    MixtureEnthalpyFlowBlock,
)
from openflowsheet.models.syn001.tp_state import lnk_block_id
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyCapabilities,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

CONTEXT = EvaluationContext(model_version="S10C-WO3@" + "0" * 64, constants_sha256="0" * 64)
REFERENCE: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "s10c" / "reference_values.yaml").read_text(encoding="utf-8")
)
BLOCKS = REFERENCE["blocks"]
REAL = WilsonIdealGasProvider(REPO_ROOT / "benchmarks" / "s10" / "records.yaml")
COMPONENTS = REAL.describe().components
COUNT = len(COMPONENTS)
#: §5.4: the FD tolerance and the closed-form tolerance (both relative, with the scales below).
TOL_FD = 1e-6
TOL_CLOSED = 1e-12
#: A35 / claim M1-SIGNAL: M1's relative error at every C-MW and C-EW block state.
M1_SIGNAL = 1e-2
UNIT = "COL"

FD_STATES = {state["id"]: state for state in BLOCKS["fd_states"]}
CLOSED = BLOCKS["closed_form_states"]
PHASES: tuple[Phase, ...] = ("LIQUID", "VAPOR")


class Counting:
    """Delegates to `inner`; records every `evaluate_phase` request (the dormant-request spy)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.requests: list[PropertyRequest] = []

    def describe(self) -> PropertyCapabilities:
        return self._inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.requests.append(request)
        return self._inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return self._inner.flash(request, context)

    @property
    def dormant_requests(self) -> int:
        return sum(request.state.is_dormant for request in self.requests)


def k_block(provider: Any = REAL) -> GammaPhiLnKBlock:
    return GammaPhiLnKBlock(provider, COMPONENTS, CONTEXT, block_id="K")


def h_block(phase: Phase, provider: Any = REAL) -> MixtureEnthalpyFlowBlock:
    return MixtureEnthalpyFlowBlock(provider, COMPONENTS, phase, CONTEXT, block_id=f"H{phase}")


def inputs(state: Mapping[str, Any]) -> list[float]:
    return [float(value) for value in state["n"]] + [float(state["T"]), float(state["P"])]


def dense(block: Any, u: Sequence[float]) -> list[list[float]]:
    """The block's Jacobian as a dense matrix; every declared pattern entry exactly once."""
    triples = list(block.jacobian(u))
    assert sorted((row, column) for row, column, _ in triples) == sorted(block.jacobian_pattern())
    matrix = [[math.nan] * len(block.input_ids) for _ in block.output_ids]
    for row, column, value in triples:
        matrix[row][column] = value
    return matrix


# -- §5.4's stencils -------------------------------------------------------------------------------


def in_domain(point: Sequence[float]) -> bool:
    """Claim FD-DOMAIN: a stencil point is a flowing, non-negative state in the provider's box."""
    domain = REAL.describe().domain
    flows, t, p = point[:COUNT], point[COUNT], point[COUNT + 1]
    (t_lo, t_hi), (p_lo, p_hi) = domain["T"], domain["P"]
    return (
        all(v >= 0.0 for v in flows)
        and sum(flows) > 0.0
        and t_lo <= t <= t_hi
        and p_lo <= p <= p_hi
    )


def fd_column(fun: Callable[[list[float]], list[float]], u: list[float], k: int) -> list[float]:
    """The registered stencil along input k: central `h = 1e-6 |u|` for T and P; central
    `h = min(1e-6 max(u, 1), u/2)` for a flow `u > 0`; one-sided second order `h = 1e-6` at an
    absent flow. Every stencil point is checked in the domain."""
    value = u[k]
    if k >= COUNT or value > 0.0:
        h = 1e-6 * abs(value) if k >= COUNT else min(1e-6 * max(value, 1.0), 0.5 * value)
        up, um = list(u), list(u)
        up[k] += h
        um[k] -= h
        assert in_domain(up) and in_domain(um)
        return [(a - b) / (2.0 * h) for a, b in zip(fun(up), fun(um), strict=True)]
    h = 1e-6
    u1, u2 = list(u), list(u)
    u1[k] += h
    u2[k] += 2.0 * h
    assert in_domain(u1) and in_domain(u2)
    return [
        (-3.0 * a + 4.0 * b - c) / (2.0 * h)
        for a, b, c in zip(fun(u), fun(u1), fun(u2), strict=True)
    ]


def k_fd_error(block: Any, u: list[float]) -> float:
    """The K-block's largest `|FD − J| / max(|J|, s)` (s = 1/n_tot, 1e-2 K⁻¹, 1/P)."""
    jacobian = dense(block, u)
    total, pressure = sum(u[:COUNT]), u[COUNT + 1]
    worst = 0.0
    for k in range(COUNT + 2):
        column = fd_column(lambda v: list(block.values(v)), u, k)
        scale = 1.0 / total if k < COUNT else (1e-2 if k == COUNT else 1.0 / pressure)
        for i in range(COUNT):
            exact = jacobian[i][k]
            worst = max(worst, abs(column[i] - exact) / max(abs(exact), scale))
    return worst


def h_fd_error(block: Any, u: list[float]) -> float:
    """The H block's largest relative error (s = 1e3 J/mol, 10 n_tot W/K); `∂H/∂P` and its
    central difference are exactly 0.0 (claim FD-HP-ZERO)."""
    jacobian = dense(block, u)[0]
    total = sum(u[:COUNT])
    worst = 0.0
    for k in range(COUNT + 2):
        column = fd_column(lambda v: list(block.values(v)), u, k)[0]
        if k == COUNT + 1:
            assert jacobian[k] == 0.0 and column == 0.0
            continue
        scale = 1e3 if k < COUNT else 10.0 * total
        worst = max(worst, abs(column - jacobian[k]) / max(abs(jacobian[k]), scale))
    return worst


# -- A30: FD against the block Jacobians -----------------------------------------------------------


@pytest.mark.parametrize("state_id", sorted(FD_STATES))
def test_a30_finite_differences_agree_with_the_block_jacobians(state_id: str) -> None:
    u = inputs(FD_STATES[state_id])
    assert k_fd_error(k_block(), u) <= TOL_FD
    for phase in PHASES:
        assert h_fd_error(h_block(phase), u) <= TOL_FD, phase


# -- A31: the K-block's Jacobian is the provider's, bitwise ----------------------------------------


@pytest.mark.parametrize("state_id", sorted(FD_STATES))
def test_a31_the_jacobian_is_the_providers_derivatives_bitwise(state_id: str) -> None:
    state = FD_STATES[state_id]
    u = inputs(state)
    flows = tuple(f"n_{c}" for c in COMPONENTS)
    lnphi = tuple(f"lnphi_{c}" for c in COMPONENTS)
    stream = StreamState(n=tuple(u[:COUNT]), temperature=u[COUNT], pressure=u[COUNT + 1])
    provider = REAL.evaluate_phase(
        PropertyRequest(
            state=stream, phase="LIQUID", properties=lnphi, derivatives=(*flows, "T", "P")
        ),
        CONTEXT,
    )
    assert provider.status == "ok"
    block = k_block()
    assert list(block.values(u)) == [provider.values[name] for name in lnphi]
    assert dense(block, u) == [
        [provider.derivatives[name][wrt] for wrt in (*flows, "T", "P")] for name in lnphi
    ]
    for phase in PHASES:
        result = REAL.evaluate_phase(
            PropertyRequest(
                state=stream, phase=phase, properties=("h",), derivatives=(*flows, "T", "P")
            ),
            CONTEXT,
        )
        h, by, total = result.values["h"], result.derivatives["h"], stream.total_flow
        assert list(h_block(phase).values(u)) == [total * h]
        assert dense(h_block(phase), u)[0] == [
            *(h + total * by[wrt] for wrt in flows),
            total * by["T"],
            total * by["P"],
        ]


# -- A32: closed forms -----------------------------------------------------------------------------


def within(got: float, ref: float, scale: float) -> bool:
    return abs(got - ref) <= TOL_CLOSED * max(abs(ref), scale)


@pytest.mark.parametrize("state_id", sorted(CLOSED))
def test_a32_values_and_jacobians_match_the_closed_forms(state_id: str) -> None:
    state = CLOSED[state_id]
    u = inputs(state)
    total, pressure = sum(u[:COUNT]), u[COUNT + 1]
    reference = state["K_block"]
    block = k_block()
    values, jacobian = list(block.values(u)), dense(block, u)
    for i in range(COUNT):
        assert within(values[i], float(reference["values"][i]), 1.0)
        for k in range(COUNT + 2):
            scale = 1.0 / total if k < COUNT else (1e-2 if k == COUNT else 1.0 / pressure)
            assert within(jacobian[i][k], float(reference["jacobian"][i][k]), scale), (i, k)
    for phase in PHASES:
        reference = state[f"H_block_{phase}"]
        block_h = h_block(phase)
        assert within(list(block_h.values(u))[0], float(reference["value"]), 1e3 * total)
        row = dense(block_h, u)[0]
        for k in range(COUNT + 1):
            scale = 1e3 if k < COUNT else 10.0 * total
            assert within(row[k], float(reference["jacobian"][k]), scale), (phase, k)
        assert row[COUNT + 1] == 0.0 and float(reference["jacobian"][COUNT + 1]) == 0.0


# -- A33, A34: the dormant convention --------------------------------------------------------------

DORMANT = BLOCKS["dormant"]
DORMANT_INPUTS: dict[str, list[float]] = {
    "zeros": [0.0] * COUNT + [float(DORMANT["T"]), float(DORMANT["P"])],
    "signed": [-0.0, 0.0, -0.0] + [float(DORMANT["T"]), float(DORMANT["P"])],
}


@pytest.mark.parametrize("which", sorted(DORMANT_INPUTS))
def test_a33_a_dormant_k_block_reads_the_probe_and_stores_zero_n_columns(which: str) -> None:
    u = DORMANT_INPUTS[which]
    spy = Counting(REAL)
    block = k_block(spy)
    values, jacobian = list(block.values(u)), dense(block, u)
    assert spy.requests and spy.dormant_requests == 0
    lnphi = tuple(f"lnphi_{c}" for c in COMPONENTS)
    probe = REAL.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=(1.0,) * COUNT, temperature=u[COUNT], pressure=u[COUNT + 1]),
            phase="LIQUID",
            properties=lnphi,
            derivatives=("T", "P"),
        ),
        CONTEXT,
    )
    reference = DORMANT["K_block_at_probe"]
    for i, name in enumerate(lnphi):
        assert values[i] == probe.values[name]
        assert jacobian[i][COUNT] == probe.derivatives[name]["T"]
        assert jacobian[i][COUNT + 1] == probe.derivatives[name]["P"]
        assert all(jacobian[i][k] == 0.0 for k in range(COUNT))
        assert within(values[i], float(reference["values"][i]), 1.0)
        assert within(jacobian[i][COUNT], float(reference["T_column"][i]), 1e-2)
        assert within(jacobian[i][COUNT + 1], float(reference["P_column"][i]), 1.0 / u[-1])


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("which", sorted(DORMANT_INPUTS))
def test_a34_a_dormant_h_block_is_zero_with_pure_component_flow_derivatives(
    which: str, phase: Phase
) -> None:
    u = DORMANT_INPUTS[which]
    spy = Counting(REAL)
    block = h_block(phase, spy)
    assert list(block.values(u)) == [0.0]
    assert spy.requests == []
    row = dense(block, u)[0]
    assert spy.dormant_requests == 0 and len(spy.requests) == COUNT
    assert row[COUNT] == 0.0 and row[COUNT + 1] == 0.0
    reference = DORMANT[f"H_block_dH_dn_{phase}"]
    for j in range(COUNT):
        pure = REAL.evaluate_phase(
            PropertyRequest(
                state=StreamState(
                    n=tuple(1.0 if k == j else 0.0 for k in range(COUNT)),
                    temperature=u[COUNT],
                    pressure=u[COUNT + 1],
                ),
                phase=phase,
                properties=("h",),
            ),
            CONTEXT,
        )
        assert row[j] == pure.values["h"]
        assert within(row[j], float(reference[j]), 1e3)


# -- M1, M5: the gates detect the mutations --------------------------------------------------------


class M1Block(GammaPhiLnKBlock):
    """M1: the K-block's `n` columns set to 0.0."""

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        return [
            (row, column, 0.0 if column < COUNT else value)
            for row, column, value in super().jacobian(inputs)
        ]


class M5Block(GammaPhiLnKBlock):
    """M5: the K-block forwards a dormant liquid to the provider."""

    def _evaluated(self, inputs: Sequence[float]) -> tuple[StreamState, bool]:
        return gamma_phi_blocks._state(inputs, COUNT), False


COLUMN_STAGES = sorted(sid for sid in FD_STATES if sid.startswith("C-"))


@pytest.mark.parametrize("state_id", COLUMN_STAGES)
def test_m1_zeroed_n_columns_fail_a30_at_every_column_state(state_id: str) -> None:
    """A35: M1 fails A30 with a relative error >= 1e-2 at every C-MW and C-EW block state."""
    u = inputs(FD_STATES[state_id])
    error = k_fd_error(M1Block(REAL, COMPONENTS, CONTEXT, block_id="K"), u)
    assert error >= M1_SIGNAL and error > TOL_FD


def m5_detected(block_type: type[GammaPhiLnKBlock]) -> bool:
    """M5's detector: a counting spy sees a dormant request, or the evaluation raises."""
    spy = Counting(REAL)
    block = block_type(spy, COMPONENTS, CONTEXT, block_id="K")
    try:
        block.values(DORMANT_INPUTS["zeros"])
        block.jacobian(DORMANT_INPUTS["zeros"])
    except (ArithmeticError, RuntimeError, ValueError):
        return True
    return spy.dormant_requests > 0


def test_m5_a_dormant_request_is_detected() -> None:
    assert not m5_detected(GammaPhiLnKBlock)
    assert m5_detected(M5Block)


# -- A36: the dormant convention moves nothing the VAPOR regime solves for -------------------------


def column_spec(case: str) -> ColumnSpec:
    """`ref.columns.<case>` (S10C-spec §4) as a `ColumnSpec` on the real records."""
    definition = REFERENCE["columns"][case]["definition"]
    feed = definition["feed"]

    def end(entry: Mapping[str, Any]) -> EndSpecification:
        return EndSpecification(entry["kind"], float(entry["value"]))

    return ColumnSpec(
        unit_id=UNIT,
        stage_count=int(definition["stage_count"]),
        pressures=tuple(float(p) for p in definition["pressures"]),
        duties=tuple(None if q is None else float(q) for q in definition["duties"]),
        condenser=definition["condenser"],
        reboiler=definition["reboiler"],
        condenser_spec=end(definition["condenser_spec"]),
        reboiler_spec=end(definition["reboiler_spec"]),
        sides=(
            SideFeed(
                "feed",
                int(feed["stage"]),
                InletState(
                    tuple(float(a) for a in feed["n"]),
                    float(feed["T"]),
                    float(feed["P"]),
                    feed["phase"],
                ),
            ),
        ),
        components=COMPONENTS,
    )


@cache
def _compiled(case: str) -> tuple[Any, Any]:
    spec = column_spec(case)
    problem = declared_problem(declared_rows(spec, REAL, CONTEXT))
    return problem, compile_problem(problem)


def _evaluate(case: str, values: Mapping[str, float]) -> tuple[dict[str, float], dict[Any, float]]:
    problem, compiled = _compiled(case)
    metadata = compiled.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    x = np.array(state_vector(problem, values))
    residual = compiled.residual(x, context)
    jacobian = compiled.jacobian(x, context)
    assert residual.status == "ok" and jacobian.status == "ok", residual.message
    rows = dict(zip(residual.equation_ids, residual.values, strict=True))
    entries: dict[Any, float] = {}
    for column, col_id in enumerate(jacobian.col_ids):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            entries[(jacobian.row_ids[jacobian.indices[offset]], col_id)] = jacobian.data[offset]
    return rows, entries


def test_a36_the_probe_moves_nothing_the_vapor_regime_solves_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A36: at a VAPOR-regime stage (`l = 0`) the rows' values and every Jacobian entry the
    regime keeps are bitwise unchanged when the probe is `(2, 1, 1)` instead of `(1, 1, 1)`.

    The only entries that move are the equilibrium rows' direct flow entries
    `∂(v_i L − K_i l_i V)/∂l_i = −K_i V` at the probe's K, in the liquid columns the VAPOR
    regime pins (and in rows it drops) — asserted here so that the test states exactly what the
    convention touches (`docs/S10C_DECISIONS.md`, WO-3 finding)."""
    stage = 15
    problem, _ = _compiled("C-MW")
    root = REFERENCE["columns"]["C-MW"]["root"]["stages"]
    values: dict[str, float] = {}
    for name in problem.variable_ids:
        kind = problem.variable_kinds.get(name)
        values[name] = 345.0 if kind == "temperature" else 101325.0 if kind == "pressure" else 0.5
    for j, entry in root.items():
        values[stage_temperature_id(UNIT, int(j))] = float(entry["T"])
    form = regime_form(column_spec("C-MW"), stage, "VAPOR")
    for name in form.pinned:
        values[name] = 0.0
    assert set(form.pinned) == {
        *(liquid_id(UNIT, stage, c) for c in COMPONENTS),
        liquid_total_id(UNIT, stage),
    }
    rows_1, entries_1 = _evaluate("C-MW", values)
    probe = REAL.evaluate_phase(
        PropertyRequest(
            state=StreamState(
                n=(1.0,) * COUNT,
                temperature=values[stage_temperature_id(UNIT, stage)],
                pressure=values[stage_pressure_id(UNIT, stage)],
            ),
            phase="LIQUID",
            properties=tuple(f"lnphi_{c}" for c in COMPONENTS),
        ),
        CONTEXT,
    )
    monkeypatch.setattr(
        gamma_phi_blocks, "probe_flows", lambda count: (2.0,) + (1.0,) * (count - 1)
    )
    rows_2, entries_2 = _evaluate("C-MW", values)
    shifted = k_block().values(
        [0.0] * COUNT
        + [values[stage_temperature_id(UNIT, stage)], values[stage_pressure_id(UNIT, stage)]]
    )
    assert list(shifted) != [probe.values[f"lnphi_{c}"] for c in COMPONENTS]  # not vacuous
    assert {k: v.hex() for k, v in rows_1.items()} == {k: v.hex() for k, v in rows_2.items()}
    assert entries_1.keys() == entries_2.keys()
    direct = {
        (stage_row_id(UNIT, stage, "eq", c), liquid_id(UNIT, stage, c)): c for c in COMPONENTS
    }
    vapor = values[vapor_total_id(UNIT, stage)]
    for key, value in entries_1.items():
        if key in direct:
            c = direct[key]
            assert value == -math.exp(probe.values[f"lnphi_{c}"]) * vapor
            assert key[1] in form.pinned and key[0] in form.dropped
            continue
        assert value.hex() == entries_2[key].hex(), key
    assert lnk_block_id(f"{UNIT}_s{stage}") in problem.block_inputs
