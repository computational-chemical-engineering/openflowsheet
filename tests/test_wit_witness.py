"""K04 amendment WIT (§4.8.1-§4.8.9, ADR 0073): the derivative witness at small and dormant flows.

The analytic cases W0-W3 (WIT.A01-A07) are the generator's test doubles
(`docs/derivations/scripts/wit_reference.py`): columns `S1.n.A`, `S1.n.B` (scale 3) and `S1.T`
(scale 100), components (A, B); rows `R1 = theta n_A / (n_A + n_B)` (scale 1),
`R2 = n_A + n_B - N0` (scale 3) and `R3 = T - T0` (scale 1); the AD Jacobian is the closed form
rounded to binary64, and a trial point with a negative flow returns `invalid_trial_state`. W3 is
one column `S1.n.A` = 0.5 and one row `R4 = n_A + 1e-10 saw(n_A 2^40)` with its AD entry declared
1. W4 (WIT.A15, review F-1) is one column `S1.n.A` with rows `R1` and
`R4' = (BIG + c n_A) - BIG - c x0` (scale 3), its AD entry declared 0.0. The expected values are
`wit_reference.json`'s; the system cases (A08-A14) are in
`tests/test_wit_system.py`.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_json

from openflowsheet.orchestrator.region import LiftedSplit
from openflowsheet.verify.checks import (
    DERIVATIVE_TOLERANCE,
    ESCALATION_LEVELS,
    FD_RELATIVE_STEP,
    RESOLUTION_TOLERANCE,
    Escalation,
    derivative_witness,
    escalate_column,
    witness_classes,
)

GENERATOR = REPO_ROOT / "docs" / "derivations" / "scripts" / "wit_reference.py"
WIT: dict[str, Any] = load_json(
    REPO_ROOT / "docs" / "derivations" / "scripts" / "wit_reference.json"
)
CLAIMS = 56

COLUMNS = ("S1.n.A", "S1.n.B", "S1.T")
COLUMN_SCALE = {"S1.n.A": 3.0, "S1.n.B": 3.0, "S1.T": 100.0}
ROWS = ("R1", "R2", "R3")
ROW_SCALE = {"R1": 1.0, "R2": 3.0, "R3": 1.0}
COMPONENTS = ("A", "B")


class _Value:
    def __init__(self, values: Sequence[float] | None, status: str = "ok") -> None:
        self.values = None if values is None else np.array(values, dtype=float)
        self.status = status


class _Jacobian:
    """A CSC Jacobian as the compiled problem returns it."""

    def __init__(
        self, entries: Mapping[tuple[str, str], float], rows: Sequence[str], cols: Sequence[str]
    ) -> None:
        self.status = "ok"
        self.row_ids = tuple(rows)
        self.col_ids = tuple(cols)
        indptr, indices, data = [0], [], []
        for column in cols:
            for row_index, row in enumerate(rows):
                if (row, column) in entries:
                    indices.append(row_index)
                    data.append(entries[(row, column)])
            indptr.append(len(indices))
        self.indptr, self.indices, self.data = indptr, indices, data


class _Compiled:
    """The compiled double: `residual` (counted) and `jacobian`."""

    def __init__(
        self,
        residual: Callable[[Sequence[float]], Sequence[float] | None],
        jacobian: _Jacobian,
    ) -> None:
        self._residual = residual
        self._jacobian = jacobian
        self.evaluations = 0

    def residual(self, x: Sequence[float], context: object) -> _Value:
        self.evaluations += 1
        values = self._residual(x)
        return _Value(None, "invalid_trial_state") if values is None else _Value(values)

    def jacobian(self, x: Sequence[float], context: object) -> _Jacobian:
        return self._jacobian


class _ResidualOnly:
    """WIT.A07: a residual-only double, with no `jacobian` attribute."""

    def __init__(self, residual: Callable[[Sequence[float]], Sequence[float] | None]) -> None:
        self._residual = residual

    def residual(self, x: Sequence[float], context: object) -> _Value:
        values = self._residual(x)
        return _Value(None, "invalid_trial_state") if values is None else _Value(values)


def smooth_case(
    theta: str, n_a: str, n_b: str, t: str
) -> tuple[dict[str, float], Callable[[Sequence[float]], list[float] | None], dict[Any, float]]:
    """W0-W2: the state, the binary64 residual and the closed-form AD Jacobian (rounded once)."""
    th, a, b = Fraction(theta), Fraction(n_a), Fraction(n_b)
    state = {"S1.n.A": float(a), "S1.n.B": float(b), "S1.T": float(Fraction(t))}
    n0 = state["S1.n.A"] + state["S1.n.B"]
    t0 = state["S1.T"]
    theta_64 = float(th)

    def residual(x: Sequence[float]) -> list[float] | None:
        if x[0] < 0 or x[1] < 0:
            return None
        total = x[0] + x[1]
        return [theta_64 * x[0] / total, total - n0, x[2] - t0]

    total = a + b
    jacobian = {
        ("R1", "S1.n.A"): float(th * b / total**2),
        ("R1", "S1.n.B"): float(-th * a / total**2),
        ("R2", "S1.n.A"): 1.0,
        ("R2", "S1.n.B"): 1.0,
        ("R3", "S1.T"): 1.0,
    }
    return state, residual, jacobian


def tear(
    residual: Callable[[Sequence[float]], Sequence[float] | None],
    jacobian: Mapping[tuple[str, str], float],
    columns: Sequence[str] = COLUMNS,
    rows: Sequence[str] = ROWS,
    column_scale: Mapping[str, float] = COLUMN_SCALE,
    row_scale: Mapping[str, float] = ROW_SCALE,
) -> Any:
    return SimpleNamespace(
        spec=SimpleNamespace(variable_ids=tuple(columns)),
        compiled=_Compiled(residual, _Jacobian(jacobian, rows, columns)),
        context=None,
        scaling=SimpleNamespace(column=dict(column_scale), row=dict(row_scale)),
    )


def run(
    target: Any, state: Mapping[str, float], components: Sequence[str] = COMPONENTS
) -> tuple[dict[str, Any], dict[str, Escalation]]:
    escalations: dict[str, Escalation] = {}
    checks = derivative_witness(target, state, components=components, escalations=escalations)
    return {c.id: c for c in checks}, escalations


def escalated_discrepancy(
    escalation: Escalation, column: str, jacobian: Mapping[Any, float]
) -> float:
    """max over the rows of |J-hat - D-hat_k*| for one escalated column (an absent entry is 0)."""
    assert escalation.scaled is not None
    return max(
        abs(
            jacobian.get((row, column), 0.0) * COLUMN_SCALE[column] / ROW_SCALE[row]
            - escalation.scaled[i]
        )
        for i, row in enumerate(ROWS)
    )


def w1() -> tuple[dict[str, float], Callable[..., Any], dict[Any, float]]:
    case = WIT["W1"]
    return smooth_case(
        str(case["theta_K"]), case["state"]["S1.n.A"], case["state"]["S1.n.B"], "600"
    )


# -- WIT.A01 ---------------------------------------------------------------------------------------


def test_a01_the_generator_rederives_its_claims_and_the_committed_bytes() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert re.search(rf"^OK: .*\({CLAIMS} claims hold\)$", completed.stdout, re.MULTILINE), output


def test_the_constants_are_the_specifications() -> None:
    constants = WIT["constants"]
    assert DERIVATIVE_TOLERANCE == constants["DERIVATIVE_TOLERANCE"]
    assert RESOLUTION_TOLERANCE == constants["EPS_RES"]
    assert FD_RELATIVE_STEP == constants["FD_RELATIVE_STEP"]
    assert ESCALATION_LEVELS == constants["K_MAX"]


# -- WIT.A02, A03 (W1) -----------------------------------------------------------------------------


def test_a02_w1_both_component_columns_escalate_and_resolve() -> None:
    state, residual, jacobian = w1()
    checks, escalations = run(tear(residual, jacobian), state)
    expected = WIT["W1"]["columns"]
    assert set(escalations) == {"S1.n.A", "S1.n.B"}  # S1.T is not escalated
    assert (escalations["S1.n.A"].level, escalations["S1.n.B"].level) == (3, 2)
    for column in ("S1.n.A", "S1.n.B"):
        assert escalations[column].level == expected[column]["k_star"]
        bound = float(expected[column]["escalated_error_bound_scaled"])
        assert escalated_discrepancy(escalations[column], column, jacobian) <= bound + 1e-11
    assert checks["derivative_witness.on_pattern"].result == "pass"
    assert checks["derivative_witness.off_pattern"].result == "pass"


def test_a02_s1_t_passes_the_registered_stencil_unescalated() -> None:
    state, residual, jacobian = w1()
    target = tear(residual, jacobian)
    _, escalations = run(target, state)
    assert "S1.T" not in escalations
    # The registered central difference of S1.T alone (its binary64 roundoff, ~2.36e-9).
    only_t = derivative_witness(
        target,
        state,
        unstenciled=frozenset({"S1.n.A", "S1.n.B"}),
        components=COMPONENTS,
    )
    assert only_t[0].result == "pass"
    assert only_t[0].value is not None and 1e-10 < only_t[0].value <= DERIVATIVE_TOLERANCE / 10


def test_a03_a_defect_of_three_tolerances_is_not_absorbed() -> None:
    state, residual, jacobian = w1()
    raised = dict(jacobian)
    # (R1, S1.n.A) scaled by S_x / S_F = 3: an unscaled raise of tau_D gives 3 tau_D scaled.
    raised[("R1", "S1.n.A")] = jacobian[("R1", "S1.n.A")] + 3.0 * DERIVATIVE_TOLERANCE / 3.0
    checks, escalations = run(tear(residual, raised), state)
    assert escalations["S1.n.A"].level == 3
    on = checks["derivative_witness.on_pattern"]
    assert on.result == "fail"
    assert on.value is not None
    assert 3 * DERIVATIVE_TOLERANCE - 1e-9 <= on.value <= 3 * DERIVATIVE_TOLERANCE + 1e-9


# -- WIT.A04 (W2) ----------------------------------------------------------------------------------


def test_a04_w2_inadmissible_levels_are_skipped_and_e_k_needs_two_admissible_levels() -> None:
    case = WIT["W2"]
    state, residual, jacobian = smooth_case(
        str(case["theta_K"]), case["state"]["S1.n.A"], case["state"]["S1.n.B"], "600"
    )
    checks, escalations = run(tear(residual, jacobian), state)
    a, b = escalations["S1.n.A"], escalations["S1.n.B"]
    assert a.admissible[:5] == (False, False, False, False, True)
    assert a.gaps[4] is None  # level 3 is inadmissible: no e_4
    assert (a.level, b.level) == (6, 4)
    assert (a.level, b.level) == (
        case["columns"]["S1.n.A"]["k_star"],
        case["columns"]["S1.n.B"]["k_star"],
    )
    for column, escalation in (("S1.n.A", a), ("S1.n.B", b)):
        bound = float(case["columns"][column]["escalated_error_bound_scaled"])
        assert escalated_discrepancy(escalation, column, jacobian) <= bound + 1e-11
    assert checks["derivative_witness.on_pattern"].result == "pass"
    assert checks["derivative_witness.off_pattern"].result == "pass"


# -- WIT.A05 (W3) ----------------------------------------------------------------------------------

ETA = 1e-10


def _r4(n_a: float) -> float:
    u = n_a * 2.0**40
    return n_a + ETA * (u - math.floor(u) - 0.5)


def test_a05_w3_an_unresolved_escalation_leaves_the_registered_result_untouched() -> None:
    x = float(WIT["W3"]["state"]["S1.n.A"])
    target = tear(
        lambda point: None if point[0] < 0 else [_r4(point[0])],
        {("R4", "S1.n.A"): 1.0},
        columns=("S1.n.A",),
        rows=("R4",),
        column_scale={"S1.n.A": 3.0},
        row_scale={"R4": 3.0},
    )
    checks, escalations = run(target, {"S1.n.A": x}, components=("A",))
    escalation = escalations["S1.n.A"]
    assert escalation.level is None and escalation.scaled is None
    assert all(escalation.admissible)
    gaps = [gap for gap in escalation.gaps if gap is not None]
    assert len(gaps) == ESCALATION_LEVELS
    assert min(gaps) >= 100 * RESOLUTION_TOLERANCE
    # The registered central discrepancy, computed here in the witness's form.
    h = FD_RELATIVE_STEP * 3.0
    scaled = (_r4(x + h) - _r4(x - h)) / (2.0 * h) * 3.0 / 3.0
    registered = abs(1.0 * 3.0 / 3.0 - scaled)
    assert registered == pytest.approx(WIT["W3"]["tier1_error_scaled"], rel=1e-6)
    on = checks["derivative_witness.on_pattern"]
    assert on.result == "fail"
    assert on.value == registered  # bitwise


# -- WIT.A06 (W0) ----------------------------------------------------------------------------------


def test_a06_w0_a_passing_column_is_never_escalated() -> None:
    state, residual, jacobian = smooth_case("0.3", "2", "5", "600")
    target = tear(residual, jacobian)
    checks, escalations = run(target, state)
    assert target.compiled.evaluations == 2 * len(COLUMNS)  # the central points only
    assert escalations == {}
    # The registered central values, computed here in the witness's form.
    base = [state[c] for c in COLUMNS]
    worst_on = worst_off = 0.0
    worst_column: dict[str, float] = {}
    for j, name in enumerate(COLUMNS):
        h = FD_RELATIVE_STEP * COLUMN_SCALE[name]
        plus, minus = list(base), list(base)
        plus[j] += 1.0 * h
        minus[j] += -1.0 * h
        f_plus, f_minus = residual(plus), residual(minus)
        assert f_plus is not None and f_minus is not None
        column_worst = 0.0
        for i, row in enumerate(ROWS):
            scaled = (f_plus[i] - f_minus[i]) / (2.0 * h) * COLUMN_SCALE[name] / ROW_SCALE[row]
            entry = jacobian.get((row, name))
            if entry is None:
                worst_off = max(worst_off, abs(scaled))
            else:
                gap = abs(entry * COLUMN_SCALE[name] / ROW_SCALE[row] - scaled)
                worst_on = max(worst_on, gap)
                column_worst = max(column_worst, gap)
        worst_column[name] = column_worst
    assert checks["derivative_witness.on_pattern"].value == worst_on  # bitwise
    assert checks["derivative_witness.off_pattern"].value == worst_off  # bitwise
    assert checks["derivative_witness.on_pattern"].result == "pass"
    # wit's exact truncation is at most 1.7e-12; binary64 roundoff adds to it (measured 6.6e-12).
    tier1 = WIT["W0"]["tier1_error_scaled"]
    for name in ("S1.n.A", "S1.n.B"):
        assert float(tier1[name]) <= 1.7e-12
        assert worst_column[name] <= DERIVATIVE_TOLERANCE / 1000


# -- WIT.A07 ---------------------------------------------------------------------------------------


def test_a07_the_escalation_never_reads_the_jacobian() -> None:
    state, residual, jacobian = w1()
    _, escalations = run(tear(residual, jacobian), state)
    base = np.array([state[c] for c in COLUMNS])
    alone = escalate_column(
        _ResidualOnly(residual),
        None,
        base,
        0,
        FD_RELATIVE_STEP * COLUMN_SCALE["S1.n.A"],
        COLUMN_SCALE["S1.n.A"],
        [ROW_SCALE[row] for row in ROWS],
    )
    assert alone.level == 3
    assert alone.scaled is not None
    assert alone.scaled == escalations["S1.n.A"].scaled  # bitwise


# -- WIT.A15 (W4, review F-1) ----------------------------------------------------------------------
#
# W1's curved row R1 = theta n_A / (n_A + n_B0) beside R4' = (BIG + c n_A) - BIG - c x0, whose true
# scaled slope is c S_x / S_F = 2e-7 = 2 tau_D and whose AD entry is declared 0.0 (a dropped term).
# Roundoff quantizes R4' to multiples of ulp(BIG): its stencil is flat at the fine levels R1 needs,
# so two flat levels agreed on 0.0 and resolved the column to a pass before §4.8.3 (c)'s flat rule.

W4_C = float(WIT["W4"]["c"])
W4_N_B = float(WIT["W4"]["n_B_mol_per_s"])


@pytest.mark.parametrize("big", [1e4, 3e4, 1e5])
@pytest.mark.parametrize("x0", [2e-4, 2.5e-4, 3e-4])
def test_a15_a_flat_stencil_does_not_resolve_a_column_whose_coarser_stencil_was_not_flat(
    big: float, x0: float
) -> None:
    theta = float(WIT["W4"]["theta_K"])
    expected = WIT["W4"]["configurations"][f"BIG={big:g},x0={x0:g}"]

    def residual(point: Sequence[float]) -> list[float] | None:
        if point[0] < 0:
            return None
        return [theta * point[0] / (point[0] + W4_N_B), (big + W4_C * point[0]) - big - W4_C * x0]

    jacobian = {("R1", "S1.n.A"): theta * W4_N_B / (x0 + W4_N_B) ** 2, ("R4", "S1.n.A"): 0.0}
    target = tear(
        residual,
        jacobian,
        columns=("S1.n.A",),
        rows=("R1", "R4"),
        column_scale={"S1.n.A": 3.0},
        row_scale={"R1": 1.0, "R4": 3.0},
    )
    checks, escalations = run(target, {"S1.n.A": x0}, components=("A",))
    escalation = escalations["S1.n.A"]
    assert escalation.level is None and escalation.scaled is None
    if expected["k_star_without_flat_rule"] is not None:
        # The rule, not the gaps, is what keeps the column unresolved here.
        assert any(escalation.barred)
    # The registered central discrepancy, computed here in the witness's form.
    h = FD_RELATIVE_STEP * 3.0
    f_plus, f_minus = residual([x0 + h]), residual([x0 - h])
    assert f_plus is not None and f_minus is not None
    registered = 0.0
    for i, (row, scale) in enumerate((("R1", 1.0), ("R4", 3.0))):
        scaled = (f_plus[i] - f_minus[i]) / (2.0 * h) * 3.0 / scale
        registered = max(registered, abs(jacobian[(row, "S1.n.A")] * 3.0 / scale - scaled))
    assert registered == pytest.approx(expected["tier1_error_scaled"], rel=1e-6)
    on = checks["derivative_witness.on_pattern"]
    assert on.result == "fail"
    assert on.value == registered  # bitwise


# -- WIT.A12, review F-2: a ZERO_FLOW split has no class 2 or 4 ----------------------------------


def _split(feed: tuple[str, ...], vapor: tuple[str, ...], liquid: tuple[str, ...]) -> LiftedSplit:
    return LiftedSplit(
        unit="U",
        stream="S1",
        feed=feed,
        temperature="U.T",
        pressure="U.P",
        vapor=vapor,
        liquid=liquid,
        vapor_total="S2.n_tot",
        liquid_total="S3.n_tot",
        equilibrium_rows=("U:eq:A", "U:eq:B"),
        vapor_definition="U:vdef",
        liquid_definition="U:ldef",
    )


@pytest.mark.parametrize("negative_zero", [False, True])
def test_a12_a_zero_flow_split_falls_to_class_5_on_a_gamma_phi_basis(negative_zero: bool) -> None:
    """§4.8.2 / §4.8.8: both sides and the feed exactly 0.0 (a `ZERO_FLOW` split) on
    `wilson-ig-v2`: classes 2 and 4 are empty and every component column is class 5."""
    feed, vapor, liquid = ("S1.n.A", "S1.n.B"), ("S2.n.A", "S2.n.B"), ("S3.n.A", "S3.n.B")
    columns = (*feed, *vapor, *liquid, "U.T")
    zero = -0.0 if negative_zero else 0.0
    state = dict.fromkeys(columns, 0.0) | {"S1.n.A": zero, "U.T": 350.0}
    classes = witness_classes(
        columns, state, COMPONENTS, basis="wilson-ig-v2", splits=[_split(feed, vapor, liquid)]
    )
    assert classes == dict.fromkeys(columns, 5)


def test_a12_a_fed_split_with_a_dormant_liquid_side_keeps_classes_2_and_4() -> None:
    """The counter-case: the same split with a positive feed. Its dormant liquid side is class 2,
    and a dormant vapour side (both sides dormant, as a classifier input) class 4."""
    feed, vapor, liquid = ("S1.n.A", "S1.n.B"), ("S2.n.A", "S2.n.B"), ("S3.n.A", "S3.n.B")
    columns = (*feed, *vapor, *liquid)
    state = dict.fromkeys(columns, 0.0) | {"S1.n.A": 1.0}
    classes = witness_classes(
        columns, state, COMPONENTS, basis="wilson-ig-v2", splits=[_split(feed, vapor, liquid)]
    )
    assert {name for name, k in classes.items() if k == 2} == set(liquid)
    assert {name for name, k in classes.items() if k == 4} == set(vapor)
