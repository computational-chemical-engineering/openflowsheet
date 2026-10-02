"""K03 M4: the SYN-001 tear, its exact derivative, and the check that keeps it honest.

This is the package's answer to the question the specification opened with — which residual
Newton runs on. Three variables, `G` is K02's traversal, `dR/dt` is the exact Schur complement
of the assembled 49x47 Jacobian. The reason it is not the lifted system is measured, not
aesthetic: in the lifted form both trivial phase splits are exact roots of every row, so a
bound-aware Newton can converge on a duty 8237.85 W wrong (K02's finding 3).

The derivative is checked three ways that do not share a route: against the closed form Fable
generated with mpmath at 40 digits, against a central finite difference of the traversal itself,
and against the affine-ray identity `J(t*) t* = −(1 − r) t*` differentiated from K02's measured
metamorphic relation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.numerics.newton import solve_newton
from openflowsheet.orchestrator.tear import (
    ETA_INNER,
    InnerSolveInconsistentError,
    Syn001TearProblem,
    solve_tear,
)
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.thermo.syn001 import Syn001Provider

CONTEXT = EvaluationContext(model_version="K03-tear@" + "0" * 64, constants_sha256="0" * 64)
POLICY = SolvePolicy(policy_id="K03-tear", residual_tolerances={}, scales={})

CASE_IDS = [
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
]

#: Closed forms from `benchmarks/k03/reference_values.yaml`, generated with mpmath at 40 digits
#: from derivation §5.1 and importing nothing from this package.
CLOSED_FORM_AT_STAR = np.array(
    [
        [-1.0613778337830190391, 0.0, 0.21026619074827601294],
        [-0.28929128281899621597, -0.64666448196768649764, 0.20915425324949077485],
        [-0.16386921382265989049, 0.0, -0.43862216621698096089],
    ]
)
CLOSED_FORM_AT_OFF_A = np.array(
    [
        [-1.0613778337830190391, 0.0, 0.21026619074827601294],
        [-0.36250584441344508423, -0.56065299951436294183, 0.18125292220672254212],
        [-0.16386921382265989049, 0.0, -0.43862216621698096089],
    ]
)
OFF_A = np.array([0.1, 0.8, 1.2])


def variants(reference_values: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {entry["case_id"]: entry for entry in reference_values["variants"]}


def tear_for(case: Mapping[str, Any]) -> Syn001TearProblem:
    return Syn001TearProblem(
        Syn001Flowsheet(
            provider=Syn001Provider(),
            context=CONTEXT,
            split_fraction=float(case["r"]),
            flash_temperature=float(case["T_flash_K"]),
            heater_temperature=float(case["T_heater_K"]),
            pressure=float(case["P_Pa"]),
        )
    )


def star_of(case: Mapping[str, Any]) -> np.ndarray:
    return np.array([float(value) for value in case["recycle_mol_per_s"]])


# ------------------------------------------------------------------------- the partition


def test_the_partition_is_the_specifications(reference_values: Mapping[str, Any]) -> None:
    """§3.1's table, written out: 3 tear variables, 3 tear rows, 44 inner of each."""
    tear = tear_for(variants(reference_values)["SYN-001-nominal"])
    partition = tear.partition
    assert partition.tear_variables == ("S6.n.A", "S6.n.B", "S6.n.C")
    assert partition.tear_rows == (
        "U-SPLIT:SPLIT-recycle:A",
        "U-SPLIT:SPLIT-recycle:B",
        "U-SPLIT:SPLIT-recycle:C",
    )
    assert len(partition.inner_variables) == 44
    assert len(partition.inner_rows) == 44
    assert partition.elimination.eliminated_ids == {
        "U-FLASH:FLASH-P:inlet",
        "U-SPLIT:SPLIT-P:recycle",
    }
    assert set(partition.tear_variables) & set(partition.inner_variables) == set()
    assert set(partition.tear_rows) & set(partition.inner_rows) == set()


def test_the_reconstruction_uses_the_traversals_own_phase_split(
    reference_values: Mapping[str, Any],
) -> None:
    """§3.3: `S3`'s lifted split comes from the kernel the heater used, not from a guess.

    At a liquid heater outlet the split is `vap = 0` exactly — there the trivial branch *is* the
    physical one. At a two-phase outlet it is the physical split, and the distinction is the
    whole reason the solve runs on the traversal rather than on the lifted system.
    """
    cases = variants(reference_values)
    liquid = cases["SYN-001-nominal"]
    tear = tear_for(liquid)
    state = tear.reconstruct(tear.tear_state(star_of(liquid)))
    assert liquid["heater_outlet_state"] == "LIQUID"
    assert [state[f"S3.vap.{c}"] for c in ("A", "B", "C")] == [0.0, 0.0, 0.0]
    assert state["S3.V"] == 0.0

    two_phase = cases["SYN-001-once-through"]
    tear2 = tear_for(two_phase)
    state2 = tear2.reconstruct(tear2.tear_state(star_of(two_phase)))
    assert two_phase["heater_outlet_state"] == "TWO_PHASE"
    assert state2["S3.V"] > 0.0
    beta = state2["S3.V"] / (state2["S3.V"] + state2["S3.L"])
    assert beta == pytest.approx(float(two_phase["heater_outlet_vapor_fraction"]), abs=1e-12)


# ------------------------------------------------------------------------ the derivative


@pytest.mark.parametrize(
    ("point", "closed_form"), [("star", CLOSED_FORM_AT_STAR), ("off_a", CLOSED_FORM_AT_OFF_A)]
)
def test_the_schur_complement_matches_the_forty_digit_closed_form(
    point: str, closed_form: np.ndarray, reference_values: Mapping[str, Any]
) -> None:
    """§13.4/A20: the 3x3 agrees with `k03_reference.py` to 1e-12 at every registered state."""
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    at = star_of(case) if point == "star" else OFF_A
    derivative = tear.jacobian(at).toarray()
    assert np.max(np.abs(derivative - closed_form)) < 1e-12


def test_the_schur_complement_matches_a_finite_difference_of_the_traversal(
    reference_values: Mapping[str, Any],
) -> None:
    """The oracle plan §4.2 retains: a route sharing nothing with the assembled Jacobian.

    Away from `t*`, because at `t*` the stencil leaves the mixer's domain — see below.
    """
    tear = tear_for(variants(reference_values)["SYN-001-nominal"])
    exact = tear.jacobian(OFF_A).toarray()
    oracle = tear.finite_difference_jacobian(OFF_A)
    assert np.max(np.abs(exact - oracle)) < 1e-9


def test_the_finite_difference_oracle_refuses_at_the_solution(
    reference_values: Mapping[str, Any],
) -> None:
    """Why it is an oracle and not a path: `t*` *is* the mixer's domain boundary.

    The recycle at the fixed point is the flash's own saturated liquid, so a central stencil
    steps off the subcooled side. It raises rather than quietly returning a one-sided difference
    wearing a central difference's error bound.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    with pytest.raises(ValueError, match="left the evaluable domain"):
        tear.finite_difference_jacobian(star_of(case))


def test_the_derivative_satisfies_the_affine_ray_identity(
    reference_values: Mapping[str, Any],
) -> None:
    """K02 measured `R(s t*) = (1 − r)(1 − s) t*`; differentiating in `s` gives `J t* = −(1−r) t*`.

    A third check on the derivative, independent of both the closed form and the finite
    difference, and derived rather than measured.
    """
    for case_id in ("SYN-001-nominal", "SYN-001-high-recycle"):
        case = variants(reference_values)[case_id]
        tear = tear_for(case)
        star = star_of(case)
        derivative = tear.jacobian(star).toarray()
        expected = -(1.0 - float(case["r"])) * star
        assert np.max(np.abs(derivative @ star - expected)) < 1e-12, case_id


def test_the_inner_consistency_check_passes_by_orders_of_magnitude(
    reference_values: Mapping[str, Any],
) -> None:
    """§3.4: `η ≤ 1e-10`. Measured here far below it, which is the margin the bound rests on."""
    for case_id in CASE_IDS:
        case = variants(reference_values)[case_id]
        tear = tear_for(case)
        state = tear.reconstruct(tear.tear_state(star_of(case)))
        eta = tear.check_inner_consistency(state)
        assert eta < 1e-12, (case_id, eta)
        assert eta <= ETA_INNER


def test_an_inconsistent_inner_state_is_refused(reference_values: Mapping[str, Any]) -> None:
    """The state that makes §3.4 bite: perturb one inner variable and the identity breaks.

    A Jacobian taken there is the derivative of a different function from the one the traversal
    measures, which is worse than having no derivative at all.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    state = tear.reconstruct(tear.tear_state(star_of(case)))
    state["S2.T"] = state["S2.T"] + 1.0

    with pytest.raises(InnerSolveInconsistentError) as raised:
        tear.check_inner_consistency(state)
    assert raised.value.eta > ETA_INNER
    assert raised.value.worst_row in tear.partition.inner_rows


def test_the_lifted_function_does_not_depend_on_the_pinned_phase_signature(
    reference_values: Mapping[str, Any],
) -> None:
    """A33: the regime lives in the state, not in the context, so the two must agree bit for bit.

    K02 made every enthalpy block phase-specific by declaration, so the lifted function has no
    phase switch in it. If it did, the attempt's frozen set would be an argument of the compiled
    function rather than orchestration state, and [A01] would mean something different.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    state = tear.reconstruct(tear.tear_state(star_of(case)))

    from openflowsheet.compile.reference import state_vector

    vector = np.array(state_vector(tear.spec, state))
    plain = tear.compiled.residual(vector, tear.context)
    import dataclasses

    for signature in ("LIQUID", "TWO_PHASE", "VAPOR", "ZERO_FLOW"):
        other = dataclasses.replace(tear.context, phase_signature=signature)
        pinned = tear.compiled.residual(vector, other)
        assert pinned.values == plain.values, signature
        assert pinned.state_sha256 == plain.state_sha256


# --------------------------------------------------------------- the tear actually solving


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_tear_converges_to_the_twenty_digit_recycle(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """G00's core: the flowsheet is *solved*, from the registered initializer, at every variant.

    One Newton step at each two-phase variant and none at all where the initializer is already
    the answer — the affine-ray argument of derivation §9 predicts exactly that, and it is why
    the same section warns that these variants exercise the derivative and the convergence test
    but not the globalization.
    """
    case = variants(reference_values)[case_id]
    tear = tear_for(case)
    trace = Trace()
    result = solve_newton(
        tear.as_newton_problem(),
        tear.flowsheet.initial_recycle().n,
        POLICY,
        trace=trace,
    )

    assert result.outcome == "CONVERGED", result.message
    assert result.iterations <= 1
    assert np.max(np.abs(result.x - star_of(case))) < 1e-9 + 1e-8 * 3.0
    assert result.residual_inf < 1e-9 + 1e-8 * 3.0
    assert trace.of_kind("attempt_closed")[0].outcome == "CONVERGED"


def test_the_tear_converges_from_an_off_ray_start(
    reference_values: Mapping[str, Any],
) -> None:
    """The start that exercises more than one step: OFF-A, which is not on the ray through `t*`.

    Registered in specification §13.3 precisely because every registered variant's own
    initializer lands in one step and therefore tests no globalization at all.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    trace = Trace()
    result = solve_newton(tear.as_newton_problem(), OFF_A, POLICY, trace=trace)

    assert result.outcome == "CONVERGED", result.message
    assert result.iterations >= 2, "an off-ray start must take more than the affine single step"
    assert np.max(np.abs(result.x - star_of(case))) < 1e-9 + 1e-8 * 3.0


def test_the_tear_is_bounded_below_by_zero(reference_values: Mapping[str, Any]) -> None:
    """ADR 0001 D3.5: a tear component is a flow, bounded below by 0, and 0 is a valid iterate."""
    tear = tear_for(variants(reference_values)["SYN-001-nominal"])
    problem = tear.as_newton_problem()
    assert problem.lower_bounds == dict.fromkeys(problem.variable_ids, 0.0)
    assert all(value == 0.0 for value in problem.lower_bounds.values())


def test_a_traversal_that_cannot_complete_is_a_typed_invalid_trial(
    reference_values: Mapping[str, Any],
) -> None:
    """§3.2 and §5.5: no residual, a recorded reason, and nothing clipped.

    The retired `r F` guess is the registered state for this: the mixer refuses it.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    retired = tear.flowsheet.retired_guess()
    evaluation = tear.residual(np.array(retired.n))
    assert evaluation.status == "unsupported"
    assert evaluation.values is None
    assert "T05" in evaluation.message


# --------------------------------------------- the rules SYN-001's own symmetry hides


def test_the_derivative_is_transformed_back_out_of_scaled_units(
    reference_values: Mapping[str, Any],
) -> None:
    """`dR/dt = S_ρ (dR̂/dt̂) S_t⁻¹`, on a problem where that is not the identity.

    §3.4 warns about this directly: for SYN-001 `S_ρ = S_t = 3 mol/s`, so the transformation is
    the identity and *any* handling of it — omitting it, or transposing the two scales — gives
    the same numbers. A sweep confirmed that: both mutations passed the whole suite. The state
    that makes it bite is unequal tear scales, so the check is done on a doctored scaling.
    """
    from openflowsheet.numerics.scaling import Scaling

    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    at = OFF_A
    reference = tear.jacobian(at).toarray()

    # Row scale 6, column scale 2: the transformation is now a factor of 3 per entry.
    doctored = Scaling(
        column={
            name: (2.0 if name in tear.partition.tear_variables else tear.scaling.column[name])
            for name in tear.spec.variable_ids
        },
        row={
            name: (6.0 if name in tear.partition.tear_rows else tear.scaling.row[name])
            for name in tear.spec.equation_ids
        },
    )
    tear.scaling = doctored
    transformed = tear.jacobian(at).toarray()

    assert np.max(np.abs(transformed - reference)) < 1e-9, (
        "dR/dt is a physical derivative and must not depend on the scales chosen to compute it; "
        "leaving it scaled, or transposing the row and column scales, changes it by 3x here"
    )


def test_the_jacobian_itself_runs_the_consistency_check(
    reference_values: Mapping[str, Any],
) -> None:
    """§3.4 makes the check mandatory *on every Jacobian evaluation*, not merely available.

    Calling `check_inner_consistency` from a test proves only that the method works. The state
    that makes the omission bite is a reconstruction that does not satisfy the inner rows, so
    one is injected here; `jacobian` must refuse rather than differentiate a different function.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    honest = tear.reconstruct

    def wrong(recycle: Any, flowsheet: Any = None) -> dict[str, float]:
        state = honest(recycle, flowsheet)
        state["S2.T"] = state["S2.T"] + 1.0
        return state

    tear.reconstruct = wrong  # type: ignore[method-assign]
    with pytest.raises(InnerSolveInconsistentError) as raised:
        tear.jacobian(star_of(case))
    assert raised.value.eta > ETA_INNER


def test_the_consistency_threshold_is_the_registered_one(
    reference_values: Mapping[str, Any],
) -> None:
    """A bound loosened a millionfold still passes every honest state; this pins the value.

    The discriminating state is a perturbation whose scaled inner residual lands between
    `1e-10` and `1e-4`: refused by the registered bound, accepted by a loose one.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    state = tear.reconstruct(tear.tear_state(star_of(case)))
    # S2.T is scaled by 100 K, so a 1e-6 K nudge is about 1e-8 scaled in MIX-energy's row.
    state["S2.T"] = state["S2.T"] + 1e-5

    with pytest.raises(InnerSolveInconsistentError) as raised:
        tear.check_inner_consistency(state)
    assert ETA_INNER < raised.value.eta < 1e-4, (
        f"the discriminating case moved: eta is now {raised.value.eta:.3e}, which no longer "
        "separates the registered 1e-10 from a millionfold-looser bound"
    )
    assert ETA_INNER == 1e-10


def test_the_lifted_context_pins_no_phase_signature(
    reference_values: Mapping[str, Any],
) -> None:
    """§3.4: the attempt's frozen set is orchestration state, not an argument of the function.

    Pinning a signature here is numerically inert — the lifted function has no phase switch,
    which the bit-identity test above establishes — so no measurement can catch it. It is still
    wrong: a context that pins a regime claims the compiled function depends on one, and [A01]
    would then mean something different. The contract is asserted directly.
    """
    tear = tear_for(variants(reference_values)["SYN-001-nominal"])
    assert tear.context.phase_signature is None


# --------------------------------------------- what the Fable review of K03 found (M1 and M5)


def test_the_consistency_check_covers_the_eliminated_rows_too(
    reference_values: Mapping[str, Any],
) -> None:
    """§3.4 and §7.3: an eliminated row is not a discarded row.

    It stays assembled so that the claim made when it was removed can be checked at every
    iterate. The check covered only the 44 retained rows, which left the two eliminated ones
    asserted once — at the initial guess, inside `_partition` — and never again.
    """
    tear = tear_for(variants(reference_values)["SYN-001-nominal"])
    eliminated = [row.row_id for row in tear.partition.elimination.eliminated]
    assert len(eliminated) == 2

    assert len(tear.checked_rows) == 46
    assert set(eliminated) <= set(tear.checked_rows)
    assert len(tear.partition.inner_rows) == 44
    assert set(eliminated).isdisjoint(tear.partition.inner_rows)


def test_the_eliminated_rows_are_checked_by_their_certificate_and_not_by_their_value(
    reference_values: Mapping[str, Any],
) -> None:
    """What must vanish is `F_e − m_e`, not `F_e`.

    §7.2 tolerates a constant mismatch up to 1e-2 Pa — 1e-7 scaled, five decades above
    `eta_inner` — so a check on `F_e` itself would turn every tolerated nonzero mismatch into a
    spurious `INNER_SOLVE_INCONSISTENT`. Here the mismatch is forced nonzero to show that the
    identity, and not the row, is what is being required to hold.
    """
    from dataclasses import replace as replace_dataclass

    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    state = tear.reconstruct(tear.tear_state(star_of(case)))

    honest = tear.check_inner_consistency(state)
    assert honest <= 1e-10

    # Claim a mismatch that is not there. The row's own value is unchanged and small, so a check
    # on `F_e` would still pass; a check on `F_e − m_e` must now fail, and name that row.
    row = tear.partition.elimination.eliminated[0]
    scale = tear.scaling.row[row.row_id]
    poisoned = replace_dataclass(row, constant_mismatch=1e-2 * scale)
    tear.partition = replace_dataclass(
        tear.partition,
        elimination=replace_dataclass(
            tear.partition.elimination,
            eliminated=(poisoned,) + tear.partition.elimination.eliminated[1:],
        ),
    )
    with pytest.raises(InnerSolveInconsistentError, match="certificate identity"):
        tear.check_inner_consistency(state)


def test_assembling_the_derivative_factorizes_the_inner_block_exactly_once(
    reference_values: Mapping[str, Any],
) -> None:
    """§3.4: "three solves against one factorization". It was three factorizations."""
    from openflowsheet.numerics import linear as linear_module

    case = variants(reference_values)["SYN-001-nominal"]
    tear = tear_for(case)
    point = star_of(case)

    factorizations = []
    original = linear_module.splu

    def counting(*args: Any, **kwargs: Any) -> Any:
        factorizations.append(1)
        return original(*args, **kwargs)

    linear_module.splu = counting
    try:
        derivative = tear.jacobian(point)
    finally:
        linear_module.splu = original

    assert len(factorizations) == 1
    assert derivative.shape == (3, 3)


def test_the_inner_solves_evidence_reaches_the_trace(
    reference_values: Mapping[str, Any],
) -> None:
    """ADR 0004 D2/D3: every solve on a K03 path carries its record onto a `SolveEvent`.

    The inner block's solve happens inside `jacobian`, where there is no trace, and its record
    was dropped on the floor — so the only recorded solve in a whole SYN-001 trace was the 3 x 3
    reduced system, and both the factorization count and the recorded evidence understated the
    solve by its larger half.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    result, trace = solve_tear(tear_for(case).flowsheet)
    assert result.outcome == "CONVERGED"

    jacobians = trace.of_kind("jacobian")
    solves = trace.of_kind("linear_solve")
    assert len(jacobians) >= 1
    assert len(solves) == 2 * len(jacobians), "one inner solve and one reduced solve per Jacobian"

    inner = [event for event in solves if "assembling the derivative" in event.message]
    assert len(inner) == len(jacobians)
    for event in inner:
        assert event.linear is not None
        assert event.message == "assembling the derivative: 44x44"
        assert event.linear.residual_normalized <= 1e-12
        assert event.linear.nnz_l > 100, "the 44x44 block, not the 3x3 one"

    assert result.counters.factorizations == len(solves)


def test_the_consistency_measure_reaches_the_trace(reference_values: Mapping[str, Any]) -> None:
    """A24's trace clause: eta is computed on every Jacobian, so it must be *readable*.

    It was computed and dropped, which left `SolveEvent.inner_consistency` a field with no
    writer — a reader of a trace could not tell a Jacobian taken at a consistent state from one
    taken anywhere else.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    _, trace = solve_tear(tear_for(case).flowsheet)
    jacobians = trace.of_kind("jacobian")
    assert jacobians
    for event in jacobians:
        assert event.inner_consistency is not None
        assert event.inner_consistency["rows_checked"] == 46
        assert event.inner_consistency["eta_max"] == ETA_INNER
        assert 0.0 <= event.inner_consistency["eta"] <= ETA_INNER
