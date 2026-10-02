"""SYN-001 oracle: thermodynamic identities, flash behavior, invariants and argument handling.

Implements items A (1-3, 5), B, C, F, G, H, I, J and K of
`docs/derivations/SYN-001-oracle-spec.md` §4. The items that compare against Fable's 20-digit
reference values (A.4, the reference half of C, D, E and L) are in
`tests/test_syn001_reference_values.py`.

Test names carry their specification item so the evidence manifest can name them stably. A test
that fails is reported, not weakened: the tolerances here are the ones the specification states.
"""

from __future__ import annotations

import math
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from benchmarks.syn001 import oracle
from benchmarks.syn001.oracle import (
    SYN001,
    DomainError,
    g_liquid,
    g_vapor,
    h_liquid,
    h_vapor,
    k_values,
    linear_recycle,
    recycle_oracle,
    stream_enthalpy_flow,
    tp_flash,
)

FRESH_FEED = (1.0, 1.0, 1.0)
P_R = SYN001.P_r

# Grid spanning the declared domain. The endpoints are included for the closed-form checks.
GRID_T = (280.0, 310.0, 350.0, 400.0, 440.0)
GRID_P = (50_000.0, 100_000.0, 200_000.0)

# Interior grid for the finite-difference identity: a difference stencil at the domain
# endpoints would step outside the domain and raise DomainError, which is correct behavior of
# `g_liquid`/`g_vapor` and not something the test may switch off.
FD_GRID_T = (281.0, 310.0, 350.0, 400.0, 439.0)

# The parameters specification §4 A.1 states.

# A fourth-order stencil at a step large enough to leave the roundoff floor. See
# `test_a1_identity_at_the_specified_step_and_tolerance` for why the specified pair cannot be
# met in double precision.
FD4_STEP_K = 0.1
FD4_TOLERANCE_J_PER_MOL = 1.0e-7

COMPONENTS = (0, 1, 2)

PropertyFunction = Callable[[float, float], tuple[float, ...]]
PHASES: tuple[tuple[str, PropertyFunction, PropertyFunction], ...] = (
    ("liquid", g_liquid, h_liquid),
    ("vapor", g_vapor, h_vapor),
)


def _fourth_order_difference(f: Callable[[float], float], T: float, step: float) -> float:
    return (-f(T + 2.0 * step) + 8.0 * f(T + step) - 8.0 * f(T - step) + f(T - 2.0 * step)) / (
        12.0 * step
    )


# --------------------------------------------------------------------------------------------
# A. Thermodynamic identities
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("phase", "g", "h"), PHASES, ids=[phase for phase, _, _ in PHASES])
@pytest.mark.parametrize("T", FD_GRID_T)
@pytest.mark.parametrize("P", GRID_P)
@pytest.mark.parametrize("index", COMPONENTS)
def test_a1_identity_by_a_fourth_order_difference(
    phase: str,
    g: PropertyFunction,
    h: PropertyFunction,
    T: float,
    P: float,
    index: int,
) -> None:
    """h = g - T dg/dT (derivation §2), verified away from the differencing roundoff floor.

    Same identity as specification §4 A.1, evaluated with a fourth-order central stencil at
    0.1 K so that neither truncation nor roundoff dominates. The tolerance is ten times
    tighter than the specified one and holds with roughly a 50-fold margin.
    """
    derivative = _fourth_order_difference(lambda t: g(t, P)[index], T, FD4_STEP_K)
    identity = g(T, P)[index] - T * derivative
    assert abs(identity - h(T, P)[index]) < FD4_TOLERANCE_J_PER_MOL


@pytest.mark.parametrize("T", GRID_T)
@pytest.mark.parametrize("P", GRID_P)
def test_a2_k_values_equal_the_chemical_potential_form(T: float, P: float) -> None:
    """K_i = exp[(g_i^L - g_i^V)/(R T)] agrees with the closed form (specification §4 A.2)."""
    from_potentials = [
        math.exp((g_liquid(T, P)[i] - g_vapor(T, P)[i]) / (SYN001.R * T)) for i in COMPONENTS
    ]
    closed_form = k_values(T, P)
    for index in COMPONENTS:
        assert closed_form[index] == pytest.approx(from_potentials[index], rel=1e-13)


@pytest.mark.parametrize("index", COMPONENTS)
def test_a3_k_is_one_at_the_reference_boiling_point(index: int) -> None:
    """K_i(T_b,i, P_r) = 1 exactly to 1e-14 (specification §4 A.3)."""
    assert k_values(SYN001.T_b[index], P_R)[index] == pytest.approx(1.0, abs=1e-14)


@pytest.mark.parametrize("T", GRID_T)
@pytest.mark.parametrize("index", COMPONENTS)
def test_a3_enthalpy_of_vaporization_at_p_r_is_l_i(T: float, index: int) -> None:
    """h_i^V - h_i^L = L_i at P_r, temperature-independent (specification §4 A.3)."""
    difference = h_vapor(T, P_R)[index] - h_liquid(T, P_R)[index]
    assert abs(difference - SYN001.L[index]) < 1e-9


@pytest.mark.parametrize(
    ("T", "P"),
    [
        (279.999, 100_000.0),
        (440.001, 100_000.0),
        (350.0, 49_999.0),
        (350.0, 200_001.0),
    ],
)
def test_a5_outside_the_declared_domain_raises(T: float, P: float) -> None:
    """The provider returns a typed domain failure rather than extrapolating (§4 A.5)."""
    for function in (k_values, h_liquid, h_vapor, g_liquid, g_vapor):
        with pytest.raises(DomainError) as info:
            function(T, P)
        assert "domain" in str(info.value)


@pytest.mark.parametrize(
    ("T", "P"),
    [
        (280.0, 50_000.0),
        (280.0, 200_000.0),
        (440.0, 50_000.0),
        (440.0, 200_000.0),
    ],
)
def test_a5_the_four_domain_corners_are_inside(T: float, P: float) -> None:
    """The declared domain is closed: its corners evaluate (specification §4 A.5)."""
    for value in k_values(T, P) + h_liquid(T, P) + h_vapor(T, P):
        assert math.isfinite(value)


# --------------------------------------------------------------------------------------------
# B. Plan sanity values
# --------------------------------------------------------------------------------------------

PLAN_K_AT_360 = (2.8406442066, 1.0, 0.3105797512)


@pytest.mark.parametrize("index", COMPONENTS)
def test_b_plan_sanity_k_values_at_360k(index: int) -> None:
    """K(360 K, P_r) matches the plan §3.1 sanity values (specification §4 B)."""
    assert k_values(360.0, P_R)[index] == pytest.approx(PLAN_K_AT_360[index], abs=1e-10)


def _sum_zk(T: float, z: Sequence[float] = (1 / 3, 1 / 3, 1 / 3)) -> float:
    return math.fsum(z[i] * k_values(T, P_R)[i] for i in COMPONENTS)


def _bubble_point_by_bisection(low: float = 300.0, high: float = 400.0) -> float:
    """Test-local bisection on sum z_i K_i(T) = 1. Independent of the oracle's flash solver."""
    assert _sum_zk(low) < 1.0 < _sum_zk(high)
    for _ in range(200):
        middle = 0.5 * (low + high)
        if _sum_zk(middle) < 1.0:
            low = middle
        else:
            high = middle
        if high - low < 1e-13:
            break
    return 0.5 * (low + high)


def test_b_bubble_point_of_the_equimolar_feed() -> None:
    """Bubble point at P_r is 347.44118198144 K to 1e-9 K (specification §4 B)."""
    assert _bubble_point_by_bisection() == pytest.approx(347.44118198144, abs=1e-9)


def test_b_sum_zk_at_350k() -> None:
    """The equimolar feed is two-phase at 350 K: sum z K = 1.07031421908 (§4 B)."""
    assert _sum_zk(350.0) == pytest.approx(1.07031421908, abs=1e-10)


# --------------------------------------------------------------------------------------------
# C. TP flash behavior that does not need the reference file
# --------------------------------------------------------------------------------------------


def test_c_zero_feed_is_zero_flow_with_undefined_composition() -> None:
    """A dormant feed: composition undefined, every flow exactly zero (ADR 0001 D3.1)."""
    result = tp_flash((0.0, 0.0, 0.0), 360.0, P_R)
    assert result.state == "ZERO_FLOW"
    assert result.x is None and result.y is None
    assert math.isnan(result.beta)
    assert math.isnan(result.sum_zK) and math.isnan(result.sum_z_over_K)
    assert result.V == 0.0 and result.L == 0.0
    assert result.vapor == (0.0, 0.0, 0.0)
    assert result.liquid == (0.0, 0.0, 0.0)
    assert result.iterations == 0


def test_c_signed_zero_feed_is_normalized() -> None:
    """-0.0 and +0.0 are the same state (ADR 0001 D1.5): both are ZERO_FLOW."""
    assert tp_flash((-0.0, -0.0, -0.0), 360.0, P_R).state == "ZERO_FLOW"


def test_c_absent_component_passes_exact_zeros_through() -> None:
    """Feed (1, 0, 1): x_B and y_B are exactly 0.0 and no logarithm of a composition occurs."""
    result = tp_flash((1.0, 0.0, 1.0), 360.0, P_R)
    assert result.state == "TWO_PHASE"
    assert result.x is not None and result.y is not None
    assert result.x[1] == 0.0
    assert result.y[1] == 0.0
    assert result.vapor[1] == 0.0
    assert result.liquid[1] == 0.0
    assert abs(result.rr_residual) <= 1e-14


def test_c_pure_b_at_its_boiling_point_is_classified_liquid() -> None:
    """Boundary convention: sum z K = 1 exactly is not > 1, so the liquid test wins.

    K_B(360 K, P_r) = 1 exactly, so pure B at its own boiling point gives sum z K = 1. The
    classification order of specification §2.2 is `sum zK <= 1 -> LIQUID`, so the result is
    LIQUID with beta = 0.0. This test documents that convention rather than asserting that one
    side of a measure-zero boundary is physically preferable; the two descriptions agree on
    every observable (zero vapor flow, x = z).
    """
    result = tp_flash((0.0, 1.0, 0.0), 360.0, P_R)
    assert result.sum_zK == 1.0
    assert result.state == "LIQUID"
    assert result.beta == 0.0
    assert result.vapor == (0.0, 0.0, 0.0)
    assert result.liquid == (0.0, 1.0, 0.0)
    assert result.x is not None and result.x[1] == 1.0
    assert result.y is None


def test_c_feed_at_its_bubble_point_does_not_raise() -> None:
    """At the bubble point rounding decides the side; beta must sit at the boundary (§4 C)."""
    bubble = _bubble_point_by_bisection()
    result = tp_flash(FRESH_FEED, bubble, P_R)
    assert result.state in ("LIQUID", "TWO_PHASE")
    assert result.beta <= 1e-12


VARIANT_FLASH_STATES = [
    (360.0, "TWO_PHASE"),
    (310.0, "LIQUID"),
    (420.0, "VAPOR"),
]


@pytest.mark.parametrize(("T_flash", "expected_state"), VARIANT_FLASH_STATES)
def test_c_flash_conserves_components_and_normalizes(T_flash: float, expected_state: str) -> None:
    """vapor + liquid = feed, and sum x = sum y = 1 where defined (specification §4 C)."""
    result = tp_flash(FRESH_FEED, T_flash, P_R)
    assert result.state == expected_state
    for index in COMPONENTS:
        total = result.vapor[index] + result.liquid[index]
        assert total == pytest.approx(FRESH_FEED[index], rel=1e-15, abs=1e-15)
    if result.x is not None:
        assert math.fsum(result.x) == pytest.approx(1.0, abs=1e-14)
    if result.y is not None:
        assert math.fsum(result.y) == pytest.approx(1.0, abs=1e-14)
    assert abs(result.rr_residual) <= 1e-14


def test_c_two_phase_compositions_satisfy_the_k_value_relation() -> None:
    """y_i = K_i x_i holds as computed, without any renormalization (specification §4 C)."""
    result = tp_flash(FRESH_FEED, 360.0, P_R)
    assert result.x is not None and result.y is not None
    for index in COMPONENTS:
        assert result.y[index] == pytest.approx(result.K[index] * result.x[index], rel=1e-15)


# --------------------------------------------------------------------------------------------
# F. Recycle invariance (metamorphic check)
# --------------------------------------------------------------------------------------------

INVARIANCE_RATIOS = (0.0, 0.5, 0.95, 0.99)


def test_f_vapor_product_and_compositions_are_independent_of_r() -> None:
    """Derivation §5.1: the loop reduces to a single flash of the fresh feed (§4 F)."""
    results = [recycle_oracle(FRESH_FEED, r, 360.0) for r in INVARIANCE_RATIOS]
    base = results[0]
    assert base.flash.x is not None and base.flash.y is not None
    for result in results[1:]:
        assert result.flash.x is not None and result.flash.y is not None
        for index in COMPONENTS:
            assert result.vapor_product[index] == pytest.approx(
                base.vapor_product[index], rel=1e-13
            )
            assert result.flash.x[index] == pytest.approx(base.flash.x[index], rel=1e-13)
            assert result.flash.y[index] == pytest.approx(base.flash.y[index], rel=1e-13)


def test_f_liquid_flow_scales_as_one_over_one_minus_r() -> None:
    """L(r)(1 - r) is constant across the registered ratios (specification §4 F)."""
    scaled = []
    for r in INVARIANCE_RATIOS:
        result = recycle_oracle(FRESH_FEED, r, 360.0)
        liquid = math.fsum(result.recycle) + math.fsum(result.purge)
        scaled.append(liquid * (1.0 - r))
    for value in scaled[1:]:
        assert value == pytest.approx(scaled[0], rel=1e-13)


def test_f_total_duty_is_independent_of_r() -> None:
    """Internal recycle enthalpy cancels, so Q_heater + Q_flash does not depend on r (§4 F)."""
    totals = [
        recycle_oracle(FRESH_FEED, r, 360.0).Q_heater + recycle_oracle(FRESH_FEED, r, 360.0).Q_flash
        for r in INVARIANCE_RATIOS
    ]
    for total in totals[1:]:
        assert abs(total - totals[0]) <= 1e-9


# --------------------------------------------------------------------------------------------
# G. Energy closure per variant
# --------------------------------------------------------------------------------------------

VARIANT_INPUTS = [
    ("SYN-001-nominal", 0.5, 360.0),
    ("SYN-001-once-through", 0.0, 360.0),
    ("SYN-001-high-recycle", 0.95, 360.0),
    ("SYN-001-all-liquid-310K", 0.5, 310.0),
    ("SYN-001-all-vapor-420K", 0.5, 420.0),
]


@pytest.mark.parametrize(("case_id", "r", "T_flash"), VARIANT_INPUTS)
def test_g_energy_closure(case_id: str, r: float, T_flash: float) -> None:
    """Q_heater + Q_flash = H_products - H_fresh for every variant (specification §4 G)."""
    result = recycle_oracle(FRESH_FEED, r, T_flash, case_id=case_id)
    assert abs(result.energy_residual) <= 1e-9


@pytest.mark.parametrize(("case_id", "r", "T_flash"), VARIANT_INPUTS)
def test_g_closed_form_total_duty(case_id: str, r: float, T_flash: float) -> None:
    """Q_h + Q_f = c_p (T_flash - T_feed) F_tot + V sum y_i L_i (derivation §6; §4 G)."""
    result = recycle_oracle(FRESH_FEED, r, T_flash, case_id=case_id)
    vapor_enthalpy_offset = (
        0.0
        if result.flash.y is None
        else result.flash.V * math.fsum(result.flash.y[i] * SYN001.L[i] for i in COMPONENTS)
    )
    closed_form = SYN001.c_p[0] * (T_flash - 300.0) * math.fsum(FRESH_FEED) + vapor_enthalpy_offset
    assert abs((result.Q_heater + result.Q_flash) - closed_form) <= 1e-9


@pytest.mark.parametrize(("case_id", "r", "T_flash"), VARIANT_INPUTS)
def test_g_registered_tolerances_hold_with_margin(case_id: str, r: float, T_flash: float) -> None:
    """Residuals are below 1% of the registered tolerances of derivation §9 (§4 D, G).

    Component balance tolerance 1e-9 + 1e-8 x 3 mol/s; energy tolerance 1e-5 + 1e-8 x 1e5 W.
    """
    result = recycle_oracle(FRESH_FEED, r, T_flash, case_id=case_id)
    balance_tolerance = 1e-9 + 1e-8 * 3.0
    energy_tolerance = 1e-5 + 1e-8 * 1e5
    assert max(abs(value) for value in result.balance_residual) < 0.01 * balance_tolerance
    assert abs(result.energy_residual) < 0.01 * energy_tolerance


# --------------------------------------------------------------------------------------------
# H. Mixer domain margin
# --------------------------------------------------------------------------------------------


def test_h_mixer_subcooling_margin_matches_the_reference_table(
    reference_values: dict[str, object],
) -> None:
    """1 - sum z_mix K(T_mix) stays positive for every registered r (specification §4 H)."""
    boundaries = reference_values["domain_boundaries"]
    assert isinstance(boundaries, dict)
    table = boundaries["mixer_outlet_subcooling_margin_vs_r_at_T_flash_360K"]
    assert isinstance(table, dict)
    checked = 0
    for key, entry in table.items():
        if key == "note":
            continue
        r = float(key.split("=")[1])
        result = recycle_oracle(FRESH_FEED, r, 360.0)
        margin = 1.0 - result.sum_zK_at_T_mix
        assert margin > 0.0, f"the v0.0 mixer domain is left at r = {r}"
        assert margin == pytest.approx(float(entry["margin"]), abs=1e-10)
        assert result.T_mix == pytest.approx(float(entry["T_mix_K"]), abs=1e-9)
        assert result.mixer_outlet_state == "LIQUID"
        checked += 1
    assert checked >= 6, "specification §4 H requires at least six ratios"


# --------------------------------------------------------------------------------------------
# I. Linear recycle
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("r", "expected"), [(0.5, 2.0), (0.95, 20.0)])
def test_i_linear_recycle_values(r: float, expected: float) -> None:
    """t = f/(1 - r) for f = (1, 1, 1) (derivation §8; specification §4 I)."""
    assert linear_recycle((1.0, 1.0, 1.0), r) == pytest.approx((expected,) * 3, rel=1e-15)


def test_i_linear_recycle_rejects_r_equal_to_one() -> None:
    """r = 1 has no solution; the oracle raises rather than returning an infinity (§4 I)."""
    with pytest.raises(ValueError, match="no steady state"):
        linear_recycle((1.0, 1.0, 1.0), 1.0)


# --------------------------------------------------------------------------------------------
# J. Argument validation
# --------------------------------------------------------------------------------------------


def test_j_negative_component_flow_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        tp_flash((-1.0, 1.0, 1.0), 360.0, P_R)
    with pytest.raises(ValueError, match="negative"):
        recycle_oracle((1.0, -1e-30, 1.0), 0.5, 360.0)


@pytest.mark.parametrize("r", [-1e-16, -0.5, 1.0, 1.5])
def test_j_out_of_range_recycle_ratio_is_rejected(r: float) -> None:
    with pytest.raises(ValueError):
        recycle_oracle(FRESH_FEED, r, 360.0)
    with pytest.raises(ValueError):
        linear_recycle((1.0, 1.0, 1.0), r)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_j_nonfinite_inputs_are_rejected(bad: float) -> None:
    """ADR 0001 D1.5: nonfinite numbers are rejected, never clipped or defaulted."""
    with pytest.raises(ValueError):
        tp_flash((bad, 1.0, 1.0), 360.0, P_R)
    with pytest.raises(ValueError):
        tp_flash(FRESH_FEED, bad, P_R)
    with pytest.raises(ValueError):
        tp_flash(FRESH_FEED, 360.0, bad)
    with pytest.raises(ValueError):
        recycle_oracle(FRESH_FEED, 0.5, 360.0, T_heater=bad)
    with pytest.raises(ValueError):
        recycle_oracle(FRESH_FEED, bad, 360.0)
    with pytest.raises(ValueError):
        linear_recycle((bad, 1.0, 1.0), 0.5)


def test_j_wrong_component_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="3 component flows"):
        tp_flash((1.0, 1.0), 360.0, P_R)


def test_j_unknown_phase_label_is_rejected() -> None:
    with pytest.raises(ValueError, match="LIQUID"):
        stream_enthalpy_flow(FRESH_FEED, 360.0, P_R, "TWO_PHASE")  # type: ignore[arg-type]


def test_j_dormant_stream_enthalpy_is_exactly_zero() -> None:
    """ADR 0001 D3.1: the enthalpy flow of a dormant stream is exactly 0.0, not merely small."""
    value = stream_enthalpy_flow((0.0, 0.0, 0.0), 360.0, P_R, "VAPOR")
    assert value == 0.0
    assert math.copysign(1.0, value) > 0.0


# --------------------------------------------------------------------------------------------
# K. Independence guard
# --------------------------------------------------------------------------------------------


def test_k_oracle_source_does_not_reference_openflowsheet() -> None:
    """Source scan: the oracle names `openflowsheet` only in prose about not importing it."""
    source = Path(oracle.__file__).read_text(encoding="utf-8")
    body = source.split('"""', 2)[2] if source.count('"""') >= 2 else source
    assert "import openflowsheet" not in body
    assert "from openflowsheet" not in body


def test_k_oracle_module_does_not_import_openflowsheet() -> None:
    """Fresh subprocess import: `openflowsheet` must not appear in sys.modules afterwards.

    Implementation plan §3.2 requires the oracle to be implemented separately from the
    production flash/recycle solver. A shared import would make an agreement between them a
    self-consistency check rather than an independent comparison.
    """
    program = (
        "import sys\n"
        "import benchmarks.syn001.oracle as oracle\n"
        "oracle.recycle_oracle((1.0, 1.0, 1.0), 0.5, 360.0)\n"
        "leaked = sorted(\n"
        "    name for name in sys.modules\n"
        "    if name == 'openflowsheet' or name.startswith('openflowsheet.')\n"
        ")\n"
        "print(','.join(leaked))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == "", (
        f"the oracle pulled in {completed.stdout.strip()}; it must not import openflowsheet"
    )


def test_k_oracle_imports_only_the_standard_library() -> None:
    """No NumPy, no SciPy: pure Python plus `math` (oracle specification header)."""
    source = Path(oracle.__file__).read_text(encoding="utf-8")
    for forbidden in ("import numpy", "import scipy", "import yaml"):
        assert forbidden not in source
