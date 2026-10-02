"""K03 M5 and gate G00: the phase-attempt controller, and the flowsheet solved end to end.

**G00 is "three-component ideal process with all named v0.0 units and one numerical tear".** It
closes here: `solve_tear` runs feed, mixer, heater, flash, splitter and two product sinks, with
the recycle torn, from the registered initializer, to Fable's 20-digit answer.

The controller is blueprint [A01] made structural. A phase set belongs to an *attempt*, not to a
residual call, and the thing that makes that real rather than aspirational is that the Newton
core is handed a signature and an `AttemptContext` and has no way to construct another.

Two details in §9 are easy to get wrong and are tested directly. A phase change is treated as an
*overshoot* first — one halving, not a restart — because a Newton step across a boundary with
the root on this side is the common case and restarting on the first crossing would cycle. And
the restart point is a **rejected trial**, never the last accepted iterate: the traversal at the
last accepted iterate reports the *old* signature, so restarting there would re-open the same
attempt.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.attempts import FLASH_REGIME, flash_signature
from openflowsheet.orchestrator.tear import solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.thermo.syn001 import Syn001Provider

CONTEXT = EvaluationContext(model_version="K03-G00@" + "0" * 64, constants_sha256="0" * 64)

CASE_IDS = [
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
]

#: ADR 0001 D6, registered for SYN-001.
FLOW_TOLERANCE = 1e-9 + 1e-8 * 3.0
ENERGY_TOLERANCE = 1e-5 + 1e-8 * 1e5

OFF_B = (0.05, 0.1, 4.0)


def variants(reference_values: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {entry["case_id"]: entry for entry in reference_values["variants"]}


def flowsheet_for(case: Mapping[str, Any]) -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=CONTEXT,
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


# ============================================================================== G00


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_g00_the_flowsheet_is_solved_at_every_registered_variant(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """**Gate G00.** Feed, mixer, heater, flash, splitter, two sinks, one numerical tear.

    Solved from the registered initializer to Fable's 20-digit recycle, at every registered
    variant, in one attempt each — and the answer is checked against the *independent*
    reference, not against a previous run of this code.
    """
    case = variants(reference_values)[case_id]
    result, trace = solve_tear(flowsheet_for(case))

    assert result.outcome == "CONVERGED", result.message
    assert result.converged
    assert result.attempts == 1, "no registered variant needs a phase restart from G(0)"

    star = np.array([float(value) for value in case["recycle_mol_per_s"]])
    assert np.max(np.abs(result.x - star)) < FLOW_TOLERANCE
    assert result.residual_inf < FLOW_TOLERANCE
    assert trace.of_kind("solve_closed")[0].outcome == "CONVERGED"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_g00_the_solved_flowsheet_reproduces_the_registered_products_and_duties(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """The point of solving it: the *whole flowsheet* at the answer, not just the tear.

    Vapour product, purge and both duties against the 20-digit references, and the overall
    balance and energy identity that no single unit can satisfy.
    """
    case = variants(reference_values)[case_id]
    flowsheet = flowsheet_for(case)
    result, _ = solve_tear(flowsheet)
    assert result.outcome == "CONVERGED"

    from openflowsheet.thermo import StreamState

    traversal = flowsheet.traverse(
        StreamState(
            n=tuple(result.x),
            temperature=flowsheet.flash_temperature,
            pressure=flowsheet.pressure,
        )
    )
    assert traversal.status == "ok"

    for index, expected in enumerate(case["vapor_product_mol_per_s"]):
        assert traversal.streams["S4"].n[index] == pytest.approx(
            float(expected), abs=FLOW_TOLERANCE
        )
    for index, expected in enumerate(case["purge_mol_per_s"]):
        assert traversal.streams["S7"].n[index] == pytest.approx(
            float(expected), abs=FLOW_TOLERANCE
        )
    assert traversal.duties["U-HEAT"] == pytest.approx(
        float(case["Q_heater_W"]), abs=ENERGY_TOLERANCE
    )
    assert traversal.duties["U-FLASH"] == pytest.approx(
        float(case["Q_flash_W"]), abs=ENERGY_TOLERANCE
    )

    for index in range(3):
        closed = traversal.streams["S4"].n[index] + traversal.streams["S7"].n[index]
        assert closed == pytest.approx(flowsheet.feed_flows[index], abs=FLOW_TOLERANCE)
    assert traversal.duties["U-HEAT"] + traversal.duties["U-FLASH"] == pytest.approx(
        float(case["H_products_minus_H_fresh_W"]), abs=ENERGY_TOLERANCE
    )


def test_g00_an_off_ray_start_converges_and_takes_more_than_one_step(
    reference_values: Mapping[str, Any],
) -> None:
    """OFF-A: the registered start that exercises the globalization the variants do not."""
    case = variants(reference_values)["SYN-001-nominal"]
    result, _ = solve_tear(flowsheet_for(case), initial_recycle=(0.1, 0.8, 1.2))
    assert result.outcome == "CONVERGED"
    assert result.attempts == 1
    assert result.iterations >= 2
    star = np.array([float(value) for value in case["recycle_mol_per_s"]])
    assert np.max(np.abs(result.x - star)) < FLOW_TOLERANCE


# ================================================================ the phase restart


@pytest.mark.parametrize("case_id", ["SYN-001-nominal", "SYN-001-high-recycle"])
def test_off_b_restarts_across_the_phase_boundary_and_converges(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """§13.3's registered expectation, number for number.

    `t⁰ = (0.05, 0.1, 4.0)` puts the flash in the all-liquid regime, where the Newton target is
    `rF/(1 − r)` — an equimolar 360 K stream the mixer refuses. The wall is confirmed, the
    attempt closes `PHASE_UPDATE_REQUIRED`, and the restart is a *trial point already inside*
    the two-phase regime.
    """
    case = variants(reference_values)[case_id]
    result, trace = solve_tear(flowsheet_for(case), initial_recycle=OFF_B)

    assert result.outcome == "CONVERGED", result.message
    assert result.attempts == 2
    assert [signature[0][1] for signature in result.signatures] == ["LIQUID", "TWO_PHASE"]

    closures = {event.attempt: event for event in trace.of_kind("attempt_closed")}
    assert closures[0].outcome == "PHASE_UPDATE_REQUIRED"
    assert closures[1].outcome == "CONVERGED"
    # §13.3 registers "≤ 3" and "≤ 4" and *measures* 2 and 2 on Fable's prototype. The measured
    # values are pinned, not the bounds: a patience of 1 would close attempt 1 at iteration 1
    # and still satisfy the bound, so the bound alone cannot see the rule it is there to check.
    assert closures[0].iteration == 2
    assert closures[1].iteration == 2

    star = np.array([float(value) for value in case["recycle_mol_per_s"]])
    assert np.max(np.abs(result.x - star)) < FLOW_TOLERANCE


def test_off_b_rejects_the_liquid_regime_target_as_an_invalid_trial(
    reference_values: Mapping[str, Any],
) -> None:
    """§13.3: the first trial of attempt 1 is exactly `rF/(1 − r)`, which the mixer refuses.

    The map is affine in the liquid regime, so the full Newton step lands on it exactly. It is
    an equimolar 360 K stream with mixer margin −0.38374131925393851449 — the retired
    initializer's own failure mode, met here as a *trial* rather than as a start.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    _, trace = solve_tear(flowsheet_for(case), initial_recycle=OFF_B)

    rejections = [
        event
        for event in trace.of_kind("trial")
        if event.attempt == 0 and event.trial_status == "rejected"
    ]
    reasons = {event.rejection_reason for event in rejections}
    assert "invalid_trial" in reasons
    assert "phase_update_required" in reasons
    assert any("T05" in event.message for event in rejections), (
        "the mixer's typed refusal must reach the trace, not just a generic rejection"
    )


def test_the_restart_point_is_a_rejected_trial_and_not_the_last_accepted_iterate(
    reference_values: Mapping[str, Any],
) -> None:
    """§9.3's subtlety, tested because getting it wrong re-opens the same attempt forever.

    The point attempt 2 opens from must report the *new* signature. The last accepted iterate of
    attempt 1 reports the old one by construction — that is why the attempt closed.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    flowsheet = flowsheet_for(case)
    _, trace = solve_tear(flowsheet, initial_recycle=OFF_B)

    opened = [event for event in trace.of_kind("attempt_opened") if event.attempt == 1]
    assert len(opened) == 1
    assert opened[0].signature[0][1] == "TWO_PHASE"
    # T03 §10 re-registration 3 (ADR 0005 D8): the decision is recorded on `attempt_opened` in
    # T03 §4.10's grammar, naming the trigger and the regime change.
    assert opened[0].message == "phase_update(phase_wall(patience, U-FLASH:LIQUID->TWO_PHASE))"

    accepted_in_first = [event for event in trace.of_kind("step_accepted") if event.attempt == 0]
    assert accepted_in_first, "attempt 1 did accept steps, so the distinction is a real one"
    assert opened[0].state_sha256 != accepted_in_first[-1].state_sha256


def test_a_phase_change_is_halved_before_it_is_believed(
    reference_values: Mapping[str, Any],
) -> None:
    """§9.3: one halving first. A restart on the first crossing would cycle on any overshoot.

    The evidence is the order of the step lengths. The full step is tried first and is refused
    by the *mixer* — at OFF-B the liquid-regime Newton target is the equimolar `rF/(1 − r)`,
    which is outside the mixer's subcooled domain, so `α = 1` is an `invalid_trial`. The phase
    change is only visible once the step has been halved, and the controller still treats that
    first crossing as an overshoot rather than restarting on it.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    _, trace = solve_tear(flowsheet_for(case), initial_recycle=OFF_B)
    first_line_search = [
        event
        for event in trace.of_kind("trial")
        if event.attempt == 0 and event.iteration == 0 and event.trial_status == "rejected"
    ]
    assert first_line_search[0].alpha == pytest.approx(1.0)
    assert first_line_search[0].rejection_reason == "invalid_trial"

    phase_alphas = sorted(
        event.alpha
        for event in first_line_search
        if event.rejection_reason == "phase_update_required"
    )
    assert phase_alphas, "the halved steps reach the other regime"
    assert max(phase_alphas) < 1.0, "a phase change is seen only after the step was halved"


# ---------------------------------------------------------------- the signature itself


def test_the_signature_is_the_flash_and_only_the_flash() -> None:
    """§9.1's map, written out. Freezing more than the residual depends on has a measured cost."""
    assert flash_signature("VAPOR", "LIQUID") == (("U-FLASH", "TWO_PHASE"),)
    assert flash_signature("ZERO_FLOW", "LIQUID") == (("U-FLASH", "LIQUID"),)
    assert flash_signature("VAPOR", "ZERO_FLOW") == (("U-FLASH", "VAPOR"),)

    # Exactly §9.1's three, and `regime` in exactly §9.1's three values. A fourth entry
    # `(ZERO_FLOW, ZERO_FLOW) -> ZERO_FLOW` was here; the Fable review found it unregistered,
    # and §9.1 says dormancy is not a phase selection at all. It fired on no state any
    # registered case reaches, which made it worse rather than harmless: it read as coverage
    # of a regime the specification does not have.
    assert len(FLASH_REGIME) == 3
    assert set(FLASH_REGIME.values()) == {"TWO_PHASE", "LIQUID", "VAPOR"}
    for refused in (("LIQUID", "VAPOR"), ("ZERO_FLOW", "ZERO_FLOW")):
        with pytest.raises(ValueError, match="registered combinations"):
            flash_signature(*refused)


def test_the_heater_outlet_regime_is_not_frozen(
    reference_values: Mapping[str, Any],
) -> None:
    """§9.1's measured reason for the narrow signature, reproduced as behaviour.

    Three of the five variants have a two-phase heater outlet and two have a liquid one, and all
    five solve in a single attempt. If `S3`'s regime were in the signature, the nominal case's
    one-step landing on `t*` would be rejected as a phase change — `S3` is `TWO_PHASE` at
    `0.5 t*` and `LIQUID` at `t*` — and the solve would restart for no reason.
    """
    cases = variants(reference_values)
    for case_id in CASE_IDS:
        case = cases[case_id]
        result, trace = solve_tear(flowsheet_for(case))
        assert result.attempts == 1, case_id
        assert {event.signature for event in trace.of_kind("attempt_opened")} == {
            result.signatures[0]
        }
        assert len(result.signatures[0]) == 1
        assert result.signatures[0][0][0] == "U-FLASH"


def test_every_event_of_an_attempt_carries_that_attempts_signature(
    reference_values: Mapping[str, Any],
) -> None:
    """[A01] made checkable: no event of one attempt carries another's frozen phase set."""
    case = variants(reference_values)["SYN-001-nominal"]
    result, trace = solve_tear(flowsheet_for(case), initial_recycle=OFF_B)
    assert result.attempts == 2

    for event in trace.events:
        if event.kind in ("solve_closed", "plan_built"):
            # `plan_built` precedes every attempt — that ordering *is* requirement D06 — so it
            # carries no signature. `solve_closed` reports the last one.
            continue
        if event.kind == "trial" and event.trial_status == "rejected":
            continue  # a rejected trial records the signature it *found*, which is the point
        assert event.signature == result.signatures[event.attempt], event


# ------------------------------------------------------------------- bounds and cycles


REGIME_A = (("U-FLASH", "LIQUID"),)
REGIME_B = (("U-FLASH", "TWO_PHASE"),)


def two_regime_problem(
    *, boundary: float = 1.0, root_in_a: float = 3.0, root_in_b: float = 0.0
) -> tuple[Any, Any]:
    """A one-variable problem whose two regimes each have their root in the *other* one.

    Constructed because no registered SYN-001 case cycles, exhausts its attempts, or converges
    inside an attempt that also hit a wall. Here each regime's Newton target is across the
    boundary, so the controller is forced through restart, cycling and exhaustion in turn.
    """
    import numpy as np
    import scipy.sparse as sp

    from openflowsheet.numerics.newton import Evaluation, Problem
    from openflowsheet.numerics.scaling import Scaling

    def regime(x: float) -> Any:
        return REGIME_A if x < boundary else REGIME_B

    def target(x: float) -> float:
        return root_in_a if regime(x) == REGIME_A else root_in_b

    def signature_of(x: np.ndarray) -> Any:
        return regime(float(x[0]))

    def residual(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        return Evaluation(status="ok", values=(value - target(value),), signature=regime(value))

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=residual,
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
    )
    return problem, signature_of


def run_controller(problem: Any, signature_of: Any, x0: Any, **policy_fields: Any) -> Any:
    from openflowsheet.orchestrator.attempts import solve_with_attempts

    trace = Trace()
    result = solve_with_attempts(
        problem_for=lambda context: problem,
        x0=x0,
        signature_of=signature_of,
        policy=SolvePolicy(
            policy_id="constructed", residual_tolerances={}, scales={}, **policy_fields
        ),
        trace=trace,
        evaluation_context=CONTEXT,
        flowsheet_context=CONTEXT,
        column_scales={"x": 1.0},
        row_scales={"r": 1.0},
        variable_ids=("x",),
    )
    return result, trace


def test_restarting_into_a_used_signature_is_reported_as_cycling() -> None:
    """§9.4: a signature may be the signature of at most one attempt per solve.

    Each regime's root lies in the other, so the controller restarts back and forth. The second
    restart is into a signature already used and must stop rather than loop.
    """
    problem, signature_of = two_regime_problem()
    result, _ = run_controller(problem, signature_of, [0.0])

    assert result.outcome == "ACTIVE_SET_CYCLING"
    assert len(set(result.signatures)) == len(result.signatures)
    # T03 §4.10's grammar (ADR 0005 D8): the terminal decision names the signature it would
    # have re-entered and the cause that led there.
    assert result.message.startswith("active_set_cycling(U-FLASH:LIQUID; phase_wall(")


def test_the_attempt_budget_is_a_typed_outcome() -> None:
    """§9.4: exceeding `max_attempts` is `ATTEMPTS_EXHAUSTED`, not an unbounded loop.

    Cycle detection would normally stop this construction first, so the signatures are made to
    alternate among more regimes than the budget allows.
    """
    import numpy as np
    import scipy.sparse as sp

    from openflowsheet.numerics.newton import Evaluation, Problem
    from openflowsheet.numerics.scaling import Scaling

    def regime_of(x: float) -> Any:
        return ((f"U-{int(abs(x) // 10)}", "LIQUID"),)

    def signature_of(x: np.ndarray) -> Any:
        return regime_of(float(x[0]))

    def residual(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        # Each band's Newton target is two bands further out, so the signature always changes.
        return Evaluation(status="ok", values=(value - (value + 25.0),), signature=regime_of(value))

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=residual,
        jacobian=lambda x: sp.csc_matrix(np.array([[1.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
    )
    result, _ = run_controller(problem, signature_of, [0.0], max_attempts=3)
    assert result.outcome in ("ATTEMPTS_EXHAUSTED", "ACTIVE_SET_CYCLING")
    assert result.attempts <= 3


def test_an_armijo_rejection_is_not_a_phase_wall() -> None:
    """§9.3 counts `phase_update_required` rejections and nothing else.

    A line search that damps for ordinary reasons must not look like a wall — if it did, a
    single-regime problem needing damping would restart into the signature it already has and
    be reported as cycling.
    """
    import numpy as np
    import scipy.sparse as sp

    from openflowsheet.numerics.newton import Evaluation, Problem
    from openflowsheet.numerics.scaling import Scaling

    only = (("U-FLASH", "LIQUID"),)

    def residual(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        return Evaluation(status="ok", values=(value**3 - 2.0 * value + 2.0,), signature=only)

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        residual=residual,
        jacobian=lambda x: sp.csc_matrix(np.array([[3.0 * float(x[0]) ** 2 - 2.0]])),
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-10},
    )
    result, trace = run_controller(problem, lambda x: only, [0.0])

    armijo = [event for event in trace.of_kind("trial") if event.rejection_reason == "armijo"]
    assert armijo, "this problem must actually damp, or the test proves nothing"
    assert result.outcome != "ACTIVE_SET_CYCLING"
    assert result.attempts == 1


def test_a_converged_attempt_is_not_restarted_even_if_it_met_a_wall() -> None:
    """Convergence ends the solve. A wall met on the way is history, not a reason to restart."""
    import numpy as np
    import scipy.sparse as sp

    from openflowsheet.numerics.newton import Evaluation, Problem
    from openflowsheet.numerics.scaling import Scaling

    here = (("U-FLASH", "TWO_PHASE"),)
    there = (("U-FLASH", "LIQUID"),)

    def signature_of(x: np.ndarray) -> Any:
        return here if float(x[0]) > 3.5 else there

    def residual(x: np.ndarray) -> Evaluation:
        value = float(x[0])
        return Evaluation(status="ok", values=(value - 4.0,), signature=signature_of(x))

    problem = Problem(
        variable_ids=("x",),
        row_ids=("r",),
        # A deliberately soft derivative, so the full step overshoots by a factor of two and
        # crosses the boundary while the halved step lands exactly on the root, in-regime.
        jacobian=lambda x: sp.csc_matrix(np.array([[0.5]])),
        residual=residual,
        scaling=Scaling(column={"x": 1.0}, row={"r": 1.0}),
        row_tolerance={"r": 1e-12},
    )
    result, trace = run_controller(problem, signature_of, [5.0])

    crossed = [
        event
        for event in trace.of_kind("trial")
        if event.rejection_reason == "phase_update_required"
    ]
    assert crossed, "the full step must cross the boundary, or the test proves nothing"
    assert result.outcome == "CONVERGED"
    assert result.attempts == 1, "a wall met on the way to convergence is history, not a restart"
    assert result.x[0] == pytest.approx(4.0)


def test_the_restart_point_is_the_largest_step_that_crossed(
    reference_values: Mapping[str, Any],
) -> None:
    """§9.4's tie-break: largest `α`, first encountered — checked against the trace itself."""
    case = variants(reference_values)["SYN-001-nominal"]
    result, trace = solve_tear(flowsheet_for(case), initial_recycle=OFF_B)
    assert result.attempts == 2

    closing = max(
        event.iteration
        for event in trace.of_kind("trial")
        if event.attempt == 0 and event.rejection_reason == "phase_update_required"
    )
    crossed = [
        event
        for event in trace.of_kind("trial")
        if event.attempt == 0
        and event.iteration == closing
        and event.rejection_reason == "phase_update_required"
    ]
    largest = max(crossed, key=lambda event: event.alpha)
    opened = [event for event in trace.of_kind("attempt_opened") if event.attempt == 1][0]
    assert opened.state_sha256 == largest.state_sha256, (
        "attempt 2 must open from the largest-alpha trial that crossed, not another one"
    )
    assert all(event.alpha <= largest.alpha for event in crossed)


def test_a_failed_solve_carries_a_partial_checkpoint_and_claims_nothing(
    reference_values: Mapping[str, Any],
) -> None:
    """§11.1 and §12.5: label `partial`, scope `unverified`. K03 certifies nothing."""
    case = variants(reference_values)["SYN-001-nominal"]
    capped = SolvePolicy(
        policy_id="capped",
        residual_tolerances={},
        scales={},
        max_iterations_per_attempt=1,
    )
    result, _ = solve_tear(flowsheet_for(case), initial_recycle=(0.1, 0.8, 1.2), policy=capped)
    assert result.outcome == "BUDGET_EXHAUSTED"
    assert not result.converged
    assert result.checkpoint is not None
    assert result.checkpoint.label == "partial"
    assert result.checkpoint.verification_scope == "unverified"


def test_a_converged_solve_labels_its_checkpoint_a_candidate_and_no_more(
    reference_values: Mapping[str, Any],
) -> None:
    """`candidate_root`, not `verified`: verifying it is K04's and K03 may not claim it."""
    case = variants(reference_values)["SYN-001-nominal"]
    result, _ = solve_tear(flowsheet_for(case), initial_recycle=(0.1, 0.8, 1.2))
    assert result.checkpoint is not None
    assert result.checkpoint.label == "candidate_root"
    assert result.checkpoint.verification_scope == "unverified"


# ------------------------------------------------- what the Fable review of K03 found (M2, M3)


def test_the_stagnation_trigger_is_not_a_tautology() -> None:
    """§9.3's second restart trigger, which read `a >= a - window` and so was always true.

    A single phase rejection at iteration 0 made every later line-search failure or stagnation
    in that attempt a restart — from iteration 0's rejected trial, twenty iterations stale. No
    registered case reaches the predicate, because OFF-B closes on `phase_wall_patience` first,
    which is exactly why 1155 green tests said nothing about it.
    """
    # T03 W2: the one wall observer both controllers share (ADR 0005 D4), same rule.
    from openflowsheet.orchestrator.phase_contract import WallObserver

    policy = SolvePolicy(
        policy_id="stagnation-window",
        residual_tolerances={},
        scales={},
        stagnation_window=5,
    )
    wall = WallObserver(policy)
    wall.iterations_with_wall = [0]

    assert wall.stalled_at_the_wall("STAGNATION", 2) is True, "0 is inside a window of 5 from 2"
    assert wall.stalled_at_the_wall("STAGNATION", 20) is False, "and stale from 20"
    assert wall.stalled_at_the_wall("LINE_SEARCH_FAILED", 20) is False

    wall.iterations_with_wall = [0, 18]
    assert wall.stalled_at_the_wall("STAGNATION", 20) is True, "the most recent wall is what counts"

    # An outcome that is neither is never a wall stall, whatever the iterations say.
    assert wall.stalled_at_the_wall("CONVERGED", 1) is False
    wall.iterations_with_wall = []
    assert wall.stalled_at_the_wall("STAGNATION", 0) is False


def test_a_failed_solve_reports_the_state_its_residual_belongs_to() -> None:
    """M3: `x` and `residual_inf` came from different states on the two give-up paths.

    On `ACTIVE_SET_CYCLING` and `ATTEMPTS_EXHAUSTED` the controller returned the restart point
    — a rejected trial no line search ever accepted — while the residual and merit came from
    the last Newton result. The two coincide whenever the closing attempt accepted nothing,
    which is why the registered cases and the first construction here both missed it; they
    separate when an attempt accepts a step and *then* meets the wall. Measured with the
    defect restored: `x = −2.0` reported alongside `residual_inf = 3.28` when the residual at
    −2.0 is −5.0.
    """
    for max_attempts, expected in ((2, "ATTEMPTS_EXHAUSTED"), (3, "ACTIVE_SET_CYCLING")):
        problem, signature_of = two_regime_problem(root_in_b=-2.0)
        result, _ = run_controller(problem, signature_of, [0.0], max_attempts=max_attempts)
        assert result.outcome == expected

        at_reported_state = problem.residual(result.x)
        assert at_reported_state.values is not None
        assert abs(at_reported_state.values[0]) == pytest.approx(result.residual_inf, rel=1e-12), (
            f"{expected}: the reported residual must be the residual of the reported state"
        )
