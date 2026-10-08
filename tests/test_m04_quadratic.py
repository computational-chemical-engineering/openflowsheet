"""M04.A09–A15 at the function level: the basis, the fit, the chain rule, admissibility and the
domain status of the surrogate (M04 spec §3).

The unit `c1.reactor_surrogate` (WO-7) wraps these functions; its refusals by the parent's hard
domain, its certificate check and its causal evaluation inside a flowsheet are tested there.
Here the synthetic parents of spec §9.1 are evaluated in the test itself, in binary64, from their
closed form — they are the data the fit is given, not the code under test — and the expectations
come from the design lane's 50-digit generator (`benchmarks/m04/reference_values.json`).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json

from openflowsheet.models.c1 import ELEMENT_MATRIX, NU
from openflowsheet.models.c1.boundary import hard_domain_violations
from openflowsheet.studies.surrogate import conformal as cf
from openflowsheet.studies.surrogate import plan as sp
from openflowsheet.studies.surrogate import quadratic as qd
from openflowsheet.thermo import StreamState

REFERENCE: Mapping[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m04" / "reference_values.json")
CONSTANTS = REFERENCE["constants"]
PIPELINE = REFERENCE["pipeline"]
FULL = sp.registered_plan("it1", synthetic_parent=False)
SYN_A = tuple(float(a) for a in CONSTANTS["synthetic"]["a"])
SYN_B = tuple(float(b) for b in CONSTANTS["synthetic"]["b"])
FIXTURE = qd.QuadraticSurrogate(
    coefficients_x=tuple(REFERENCE["fixture_coefficients"]["X"]),
    coefficients_dt=tuple(REFERENCE["fixture_coefficients"]["dT"]),
)
STATES = {state["id"]: state for state in REFERENCE["jacobian_states"]}


def _z(request: StreamState) -> tuple[float, ...]:
    u = sp.coordinates(request, sp.PLAN_N_TUBES)
    assert u is not None
    return sp.scaled(u)


def synthetic(z: Sequence[float], amplitude: float | None) -> tuple[float, float] | None:
    """Spec §9.1: X = 0.16 exp(A a·z), ΔT = 80 exp(A b·z), failing iff z_T + z_F > 1.6;
    `amplitude` None is the stand-in (X ≡ 0.25, ΔT ≡ 0)."""
    if amplitude is None:
        return 0.25, 0.0
    if z[0] + z[6] > 1.6:
        return None
    eta_x = math.fsum(a * x for a, x in zip(SYN_A, z, strict=True))
    eta_t = math.fsum(b * x for b, x in zip(SYN_B, z, strict=True))
    return 0.16 * math.exp(amplitude * eta_x), 80.0 * math.exp(amplitude * eta_t)


def fit_case(
    amplitude: float | None, count: int, rows: Sequence[sp.Draw] | None = None
) -> tuple[qd.QuadraticFit, list[int]]:
    """Fit the first `count` training draws' `ok` results; return the fit and the failed indices."""
    zs, xs, dts, failed = [], [], [], []
    for row in (FULL.training if rows is None else rows)[:count]:
        z = _z(row.request)
        truth = synthetic(z, amplitude)
        if truth is None:
            failed.append(row.index)
            continue
        zs.append(z)
        xs.append(truth[0])
        dts.append(truth[1])
    return qd.fit_quadratic(zs, xs, dts), failed


def _inlet(state: Mapping[str, Any]) -> StreamState:
    inlet = state["inlet"]
    return StreamState(n=tuple(inlet["n"]), temperature=inlet["T"], pressure=inlet["P"])


# -- A09 ------------------------------------------------------------------------------------------


def test_a09_the_basis_at_the_registered_point() -> None:
    assert list(qd.BASIS_ORDER) == CONSTANTS["basis_order"]
    assert len(qd.BASIS_ORDER) == cf.TERMS == CONSTANTS["terms"] == 36
    point = REFERENCE["basis_at_zstar"]
    phi = qd.basis([float(z) for z in point["z"]])
    worst = max(
        abs(value - float(expected)) / abs(float(expected))
        for value, expected in zip(phi, point["phi"], strict=True)
    )
    assert worst <= 1e-14, worst


def test_a09_the_basis_gradient_is_the_derivative_of_the_basis() -> None:
    """∂φ/∂z against central differences of φ itself at z* (a quadratic: exact up to roundoff)."""
    z = [float(x) for x in REFERENCE["basis_at_zstar"]["z"]]
    analytic = qd.basis_gradient(z)
    step = 1e-4
    for k in range(7):
        plus, minus = list(z), list(z)
        plus[k] += step
        minus[k] -= step
        fd = [(a - b) / (2 * step) for a, b in zip(qd.basis(plus), qd.basis(minus), strict=True)]
        for m in range(36):
            assert abs(fd[m] - analytic[m][k]) <= 1e-11, (m, k)


# -- A10 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "amplitude", "count"),
    [("smooth_full", 1.0, 144), ("smooth_prefix", 1.0, 72), ("rough_prefix", 4.0, 72)],
)
def test_a10_the_fit_reproduces_the_registered_coefficients(
    case: str, amplitude: float, count: int
) -> None:
    expected = PIPELINE[case]
    fit, failed = fit_case(amplitude, count)
    assert failed == expected["failed_indices"]["training"]
    assert fit.refusal is None and fit.surrogate is not None
    assert fit.training_ok == expected["training_ok"]
    assert fit.singular_value_ratio is not None
    ratio = float(expected["singular_value_ratio"])
    # The registered ratio is printed to 12 digits: 1e-8 relative is A10's tolerance, met by far.
    assert abs(fit.singular_value_ratio - ratio) <= 1e-8 * ratio
    for name, beta in (
        ("X", fit.surrogate.coefficients_x),
        ("dT", fit.surrogate.coefficients_dt),
    ):
        reference = [float(b) for b in expected["coefficients"][name]]
        scale = max(abs(b) for b in reference)
        worst = max(abs(b - r) for b, r in zip(beta, reference, strict=True)) / scale
        assert worst <= 1e-10, (name, worst)
    assert fit.training_rms is not None
    for value, name in zip(fit.training_rms, ("X", "dT"), strict=True):
        registered = float(expected["training_rms"][name])
        assert abs(value - registered) <= 1e-6 * registered, name


def test_a10_the_stand_in_is_fitted_exactly() -> None:
    """X ≡ 0.25, ΔT ≡ 0: β_X = 0.25 e₀ and β_T = 0 to roundoff (spec §9.1; A16's fit)."""
    fit, failed = fit_case(None, 72)
    assert failed == [] and fit.surrogate is not None and fit.training_ok == 72
    beta_x, beta_t = fit.surrogate.coefficients_x, fit.surrogate.coefficients_dt
    assert abs(beta_x[0] - 0.25) <= 1e-14
    assert max(abs(b) for b in beta_x[1:]) <= 1e-14
    assert max(abs(b) for b in beta_t) <= 1e-12


def test_a10_the_fit_against_the_registered_scores_and_band() -> None:
    """The smooth full case's calibration and test scores, q̂ and H from the fitted predictor —
    the statistics A17 judges, reached here without M02's runner (the parent is closed form)."""
    expected = PIPELINE["smooth_full"]
    fit, _ = fit_case(1.0, 144)
    assert fit.surrogate is not None

    def scores(rows: Sequence[sp.Draw]) -> list[float | None]:
        out: list[float | None] = []
        for row in rows:
            z = _z(row.request)
            truth = synthetic(z, 1.0)
            if truth is None:
                out.append(None)
                continue
            x, dt = fit.surrogate.predict(z)  # type: ignore[union-attr]
            out.append(cf.score(truth[0], truth[1], x, dt))
        return out

    calibration, test = scores(FULL.calibration), scores(FULL.test)
    worst = 0.0
    for values, registered in (
        (calibration, expected["calibration_scores"]),
        (test, expected["test_scores"]),
    ):
        for value, reference in zip(values, registered, strict=True):
            assert (value is None) == (reference is None)
            if value is not None:
                worst = max(worst, abs(value - float(reference)))
    assert worst <= 1e-10, worst
    band = cf.conformal_band(calibration)
    assert band.k == 114 and band.q_hat is not None
    assert abs(band.q_hat - float(expected["result"]["q_hat"])) <= 1e-10
    assert cf.coverage_hits(test, band.q_hat) == expected["result"]["hits"] == 283


# -- A11 ------------------------------------------------------------------------------------------


def test_a11_a_constant_flow_coordinate_is_unidentifiable() -> None:
    """The prefix training set with every F at the box centre: z₇ ≡ 0 (to roundoff), so every
    column carrying z₇ vanishes and the fit is refused, not returned."""
    centre = sp.BOX[6].centre
    rows = []
    for row in FULL.training[:72]:
        u = (*row.u[:6], centre)
        rows.append(dataclasses.replace(row, u=u, request=sp.request_of(u)))
    assert max(abs(_z(row.request)[6]) for row in rows) <= 1e-13
    fit, failed = fit_case(1.0, 72, rows)
    assert failed == []
    assert fit.refusal == "training_unidentifiable" and fit.surrogate is None
    assert fit.singular_value_ratio is not None and fit.singular_value_ratio < cf.TAU_ID


def test_a11_too_few_training_results_are_refused_before_the_fit() -> None:
    fit, _ = fit_case(1.0, 36)  # 36 draws, none failed: identifiable
    assert fit.refusal is None and fit.training_ok == 36
    zs = [_z(row.request) for row in FULL.training[:35]]
    fit = qd.fit_quadratic(zs, [0.1] * 35, [10.0] * 35)
    assert (fit.refusal, fit.singular_value_ratio, fit.training_ok) == (
        "training_unidentifiable",
        None,
        35,
    )


# -- A12 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state_id", ["J1", "J2", "J3"])
def test_a12_the_inlet_jacobian_at_the_registered_states(state_id: str) -> None:
    state = STATES[state_id]
    inlet = _inlet(state)
    outlet = state["outlet"]
    rows = qd.extent_rows(
        FIXTURE, inlet, state["n_tubes"], float(outlet["xi"]), float(outlet["T_out"])
    )
    assert rows is not None
    assert list(qd.ROW_COLUMNS) == state["columns"]
    worst = 0.0
    for r in range(2):
        for c in range(7):
            expected = float(state["jacobian"][r][c])
            worst = max(worst, abs(rows.jacobian[r][c] - expected) / abs(expected))
    assert worst <= 1e-10, worst
    assert (rows.jacobian[0][7:], rows.jacobian[1][7:]) == ((1.0, 0.0), (0.0, 1.0))
    n_tot = sum(inlet.n)
    assert abs(rows.residuals[0]) <= 1e-15 * n_tot, rows.residuals
    assert abs(rows.residuals[1]) <= 1e-15 * inlet.temperature, rows.residuals


@pytest.mark.parametrize("state_id", ["J1", "J2", "J3"])
def test_a12_the_rows_vanish_at_the_causal_outlet(state_id: str) -> None:
    state = STATES[state_id]
    inlet = _inlet(state)
    outlet = qd.causal_outlet(FIXTURE, inlet, state["n_tubes"])
    assert outlet.status == "ok" and outlet.xi is not None and outlet.outlet_temperature is not None
    assert abs(outlet.xi - float(state["outlet"]["xi"])) <= 1e-13 * abs(outlet.xi)
    assert abs(outlet.outlet_temperature - float(state["outlet"]["T_out"])) <= 1e-13 * 800.0
    rows = qd.extent_rows(FIXTURE, inlet, state["n_tubes"], outlet.xi, outlet.outlet_temperature)
    assert rows is not None
    assert abs(rows.residuals[0]) <= 1e-15 * sum(inlet.n)
    assert abs(rows.residuals[1]) <= 1e-15 * inlet.temperature


def test_a12_the_residual_and_its_jacobian_describe_the_same_function() -> None:
    """Central differences of the production rows against the analytic Jacobian at J2 (every z_k
    distinct), with relative steps 1e-6: agreement to the difference's truncation, ~1e-9."""
    state = STATES["J2"]
    inlet = _inlet(state)
    xi, t_out = float(state["outlet"]["xi"]), float(state["outlet"]["T_out"])
    rows = qd.extent_rows(FIXTURE, inlet, state["n_tubes"], xi, t_out)
    assert rows is not None
    base = [*inlet.n, inlet.temperature, inlet.pressure]
    for c in range(7):
        step = 1e-6 * abs(base[c])
        values = []
        for sign in (1.0, -1.0):
            moved = list(base)
            moved[c] += sign * step
            shifted = StreamState(n=tuple(moved[:5]), temperature=moved[5], pressure=moved[6])
            result = qd.extent_rows(FIXTURE, shifted, state["n_tubes"], xi, t_out)
            assert result is not None
            values.append(result.residuals)
        for r in range(2):
            fd = (values[0][r] - values[1][r]) / (2 * step)
            assert abs(fd - rows.jacobian[r][c]) <= 1e-6 * abs(rows.jacobian[r][c]), (r, c)


# -- A13 ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state_id", ["J1", "J2", "J3"])
def test_a13_conservation_at_the_causal_outlet(state_id: str) -> None:
    state = STATES[state_id]
    inlet = _inlet(state)
    outlet = qd.causal_outlet(FIXTURE, inlet, state["n_tubes"])
    assert outlet.n_out is not None
    n_tot = sum(inlet.n)
    for element in ELEMENT_MATRIX:
        change = math.fsum(
            e * (o - i) for e, o, i in zip(element, outlet.n_out, inlet.n, strict=True)
        )
        assert abs(change) <= 1e-14 * n_tot
    for k, nu in enumerate(NU):
        if nu == 0:
            assert outlet.n_out[k].hex() == inlet.n[k].hex()


# -- A14 ------------------------------------------------------------------------------------------


def test_a14_the_reference_domain_status() -> None:
    for state_id in ("J1", "J2"):
        outlet = qd.causal_outlet(FIXTURE, _inlet(STATES[state_id]), STATES[state_id]["n_tubes"])
        assert outlet.domain == qd.ReferenceDomain("within_reference_domain", 0.0, ())
        assert STATES[state_id]["domain"]["status"] == "within_reference_domain"
    outlet = qd.causal_outlet(FIXTURE, _inlet(STATES["J3"]), 1.0)
    assert outlet.domain is not None
    assert outlet.domain.status == "outside_reference_domain" == STATES["J3"]["domain"]["status"]
    assert abs(outlet.domain.scaled_excess - 0.5) <= 1e-12
    assert outlet.domain.coordinates == ("T",)
    assert hard_domain_violations(_inlet(STATES["J3"])) == []  # J3 is inside the hard domain


def test_a14_j4_lies_outside_the_parents_hard_domain_in_t_only() -> None:
    """J1 with T_in = 780 K: the parent's own check (which the unit applies, WO-7) fails on T
    alone; the surrogate itself still evaluates (a polynomial), outside the reference box."""
    j4 = dataclasses.replace(_inlet(STATES["J1"]), temperature=780.0)
    violated = hard_domain_violations(j4)
    assert len(violated) == 1 and violated[0].startswith("T_in ")
    outlet = qd.causal_outlet(FIXTURE, j4, 1.0)
    assert outlet.status == "ok" and outlet.domain is not None
    assert outlet.domain.coordinates == ("T",)


def test_a14_j5_an_inlet_without_n2_has_no_input() -> None:
    j1 = _inlet(STATES["J1"])
    j5 = dataclasses.replace(j1, n=(j1.n[0], 0.0, *j1.n[2:]))
    assert sp.coordinates(j5, 1.0) is None
    assert qd.causal_outlet(FIXTURE, j5, 1.0).status == "input_undefined"
    assert qd.extent_rows(FIXTURE, j5, 1.0, 0.0, 700.0) is None
    assert qd.inlet_sensitivity(FIXTURE, j5, 1.0) is None


def test_a14_j6_a_dormant_inlet() -> None:
    j6 = dataclasses.replace(_inlet(STATES["J1"]), n=(0.0,) * 5)
    outlet = qd.causal_outlet(FIXTURE, j6, 1.0)
    assert outlet.status == "dormant"
    assert outlet.xi == 0.0 and outlet.outlet_temperature == j6.temperature
    assert outlet.n_out == (0.0,) * 5 and outlet.x is None


# -- A15 ------------------------------------------------------------------------------------------


def _constant(x: float = 0.0, dt: float = 0.0) -> qd.QuadraticSurrogate:
    return qd.QuadraticSurrogate((x,) + (0.0,) * 35, (dt,) + (0.0,) * 35)


@pytest.mark.parametrize(
    ("beta_x", "beta_t", "h2_over_n2", "expected"),
    [
        (-0.01, 0.0, None, ("X",)),
        (0.96, 0.0, None, ("X",)),
        (0.5, 0.0, 1.2, ("X",)),  # r/3 = 0.4 < 0.5 < 0.95: the H2 bound
        (0.5, 0.0, None, ()),
        (0.0, 260.0, None, ("dT",)),
        (0.0, -50.0, None, ()),
        (0.95, 250.0, None, ()),
    ],
)
def test_a15_admissibility(
    beta_x: float, beta_t: float, h2_over_n2: float | None, expected: tuple[str, ...]
) -> None:
    inlet = _inlet(STATES["J1"])
    if h2_over_n2 is not None:
        inlet = dataclasses.replace(inlet, n=(h2_over_n2 * inlet.n[1], *inlet.n[1:]))
        assert hard_domain_violations(inlet) == []  # H2/N2 = 1.2 is inside the hard domain
    outlet = qd.causal_outlet(_constant(beta_x, beta_t), inlet, 1.0)
    assert outlet.status == "ok"
    assert outlet.inadmissible == expected


def test_the_predictor_refuses_malformed_coefficients() -> None:
    with pytest.raises(ValueError, match="35 entries"):
        qd.QuadraticSurrogate((0.0,) * 35, (0.0,) * 36)
    with pytest.raises(ValueError, match="non-finite"):
        qd.QuadraticSurrogate((math.nan,) + (0.0,) * 35, (0.0,) * 36)
