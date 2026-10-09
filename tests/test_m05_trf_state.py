"""M05 WO-3: TRF's state read from its log, its outcomes, its registered configurations and its
pin (design note §6.7; ADR 0038 D1, D4, D8), in the default gate. `trf_state` imports no Pyomo;
the log fixture below is TRF 6.10.1's own record of TR-E1 (`tests/test_m05_trf.py` reproduces it
in the audited environment).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from openflowsheet.studies.trust_region.holders import RunState
from openflowsheet.studies.trust_region.trf_state import (
    EXIT_FEASIBLE,
    EXIT_OPTIMAL,
    PYOMO_VERSION,
    TRF_CONFIG_V1,
    TRF_MODULE_SHA256,
    TRSP_EXECUTABLE_SHA256,
    TRSP_OPTIONS,
    WARNING_INSUFFICIENT_PROGRESS,
    IterationRecord,
    TrfLogError,
    TrfLogHandler,
    classify_exit,
    framework_readiness,
    last_accepted,
    reconstruct_filter,
    step_size_termination,
    trf_config_v1,
)

#: TRF 6.10.1's INFO records of TR-E1 through `openflowsheet_trsp_ipopt` (measured, WO-3).
TR_E1_LOG = """\
****** Iteration 0 ******
trustRadius = 1.0
feasibility = 0.39409145195691153
objectiveValue = 0.33780685817104034
stepNorm = 0
****** Iteration 1 ******
trustRadius = 0.06886655497881056
feasibility = 0.020618399647490016
objectiveValue = 0.2759713000394235
stepNorm = 0.1377331099576211
INFO: theta-type step
****** Iteration 2 ******
trustRadius = 0.002965276432002395
feasibility = 8.062946323050824e-06
objectiveValue = 0.2770443672997913
stepNorm = 0.00593055286400479
INFO: theta-type step
****** Iteration 3 ******
trustRadius = 0.002965276432002395
feasibility = 2.2818900546894838e-08
objectiveValue = 0.2770447875414949
stepNorm = 7.224864113797302e-05
INFO: theta-type step
****** Iteration 4 ******
trustRadius = 0.002965276432002395
feasibility = 5.525213619961278e-11
objectiveValue = 0.2770447887637415
stepNorm = 3.446238002746682e-06
INFO: theta-type step"""


def parsed(text: str = TR_E1_LOG) -> tuple[TrfLogHandler, tuple[IterationRecord, ...]]:
    handler = TrfLogHandler(RunState("trf-1"))
    for line in text.splitlines():
        handler.consume(line)
    return handler, handler.iterations()


def record(k: int, theta: float, f: float, kind: str | None) -> IterationRecord:
    return IterationRecord(k, theta, f, 1.0, 0.1, kind)  # type: ignore[arg-type]


# -- the parser -----------------------------------------------------------------------------------


def test_the_log_parses_exactly_and_advances_the_run_state() -> None:
    handler, iterations = parsed()
    assert [r.k for r in iterations] == [0, 1, 2, 3, 4]
    assert [r.step_type for r in iterations] == [None, "theta", "theta", "theta", "theta"]
    assert iterations[4].theta == 5.525213619961278e-11
    assert iterations[1].radius == 0.06886655497881056
    assert iterations[0].step_norm == 0.0
    assert handler.run is not None and handler.run.last_logged_iteration == 4
    assert iterations[1].as_document()["radius_logged"] == "updated"


def test_the_float_round_trip_through_the_log_is_exact() -> None:
    """`%s` of a float is its `repr`, so `float()` of the logged text is the binary64 TRF held."""
    value = 0.1 + 0.2
    handler = TrfLogHandler()
    lines = (
        "****** Iteration 0 ******",
        f"trustRadius = {value}",
        "feasibility = %s" % (value,),  # noqa: UP031 - the format TRF itself uses
        "objectiveValue = 1e-300",
        "stepNorm = 0",
    )
    for line in lines:
        handler.consume(line)
    (only,) = handler.iterations()
    assert only.radius == value and only.theta == value and only.objective == 1e-300


def test_a_rejected_step_logs_the_radius_it_used() -> None:
    handler = TrfLogHandler()
    text = (
        "****** Iteration 0 ******\ntrustRadius = 0.25\nfeasibility = 1.0\n"
        "objectiveValue = 2.0\nstepNorm = 0\n****** Iteration 1 ******\ntrustRadius = 0.25\n"
        "feasibility = 3.0\nobjectiveValue = 1.0\nstepNorm = 0.25\nINFO: step rejected"
    )
    for line in text.splitlines():
        handler.consume(line)
    rejected = handler.iterations()[1]
    assert rejected.step_type == "rejected"
    assert rejected.as_document()["radius_logged"] == "used"


def test_warnings_are_kept_apart() -> None:
    handler, _ = parsed()
    handler.consume("EXIT: Maximum iterations reached: 4.", logging.WARNING)
    assert handler.warnings == ["EXIT: Maximum iterations reached: 4."]
    handler.iterations()  # a warning does not disturb the records


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda t: t.replace("stepNorm = 0.00593055286400479\n", ""), "logged"),
        (lambda t: t.replace("Iteration 3", "Iteration 7"), "position"),
        (lambda t: t.replace("INFO: theta-type step", "INFO: something else", 1), "unrecognized"),
        (lambda t: t + "\nfeasibility = not-a-number", "unrecognized"),
        (lambda t: t.replace("****** Iteration 2 ******\n", "", 1), "unrecognized"),
    ],
)
def test_a_log_that_is_not_trf_6_10_1s_is_refused(mutation: object, message: str) -> None:
    handler = TrfLogHandler()
    for line in mutation(TR_E1_LOG).splitlines():  # type: ignore[operator]
        handler.consume(line)
    with pytest.raises(TrfLogError, match=message):
        handler.iterations()


# -- the filter -----------------------------------------------------------------------------------


def test_the_filter_of_tr_e1_is_every_theta_step_offered() -> None:
    _, iterations = parsed()
    rebuilt = reconstruct_filter(iterations, 0.01, 0.01)
    assert rebuilt == tuple(
        (r.objective - 0.01 * r.theta, (1 - 0.01) * r.theta) for r in iterations[1:]
    )


def test_the_filter_follows_add_to_filter_dominance() -> None:
    iterations = (
        record(0, 9.0, 9.0, None),
        record(1, 1.0, 1.0, "theta"),  # offered (0.99, 0.99)
        record(2, 2.0, 0.5, "theta"),  # (0.48, 1.98): neither dominates (0.99, 0.99)
        record(3, 3.0, 3.0, "theta"),  # dominated by (0.99, 0.99): skipped
        record(4, 0.5, 0.1, "theta"),  # dominates both: they are removed
        record(5, 0.1, 0.0, "f"),  # f-type steps do not enter the filter
    )
    assert reconstruct_filter(iterations, 0.01, 0.01) == ((0.1 - 0.01 * 0.5, 0.99 * 0.5),)
    assert reconstruct_filter(iterations[:4], 0.01, 0.01) == (
        (1.0 - 0.01, 0.99),
        (0.5 - 0.02, 0.99 * 2.0),
    )


def test_the_final_iterate_is_the_last_accepted_one() -> None:
    iterations = (record(0, 1.0, 1.0, None), record(1, 0.5, 0.9, "f"), record(2, 2, 2, "rejected"))
    accepted = last_accepted(iterations)
    assert accepted is not None and accepted.k == 1
    assert last_accepted(iterations[:1]) == iterations[0]


# -- the outcome ----------------------------------------------------------------------------------


def classify(
    exit_lines: list[str],
    warnings: list[str],
    iterations: tuple[IterationRecord, ...],
    maximum: int = 50,
) -> str:
    return classify_exit(
        exit_lines=exit_lines,
        warnings=warnings,
        iterations=iterations,
        feasibility_termination=1e-5,
        step_size_termination=1e-5,
        maximum_iterations=maximum,
    )


def test_converged_needs_the_exit_line_and_the_logged_values_to_agree() -> None:
    _, iterations = parsed()
    assert classify([EXIT_OPTIMAL], [], iterations) == "TRF_CONVERGED"
    assert classify([EXIT_OPTIMAL], [], iterations[:4]) == "TRF_ERROR(exit_mismatch)"
    assert classify([EXIT_OPTIMAL, EXIT_OPTIMAL], [], iterations) == "TRF_ERROR(exit_mismatch)"
    assert classify([], [], iterations) == "TRF_ERROR(exit_mismatch)"
    assert classify([EXIT_OPTIMAL], [], ()) == "TRF_ERROR(exit_mismatch)"


def test_converged_on_the_last_permitted_iteration_is_still_converged() -> None:
    """`TRF.py` logs the maximum-iterations warning whenever `iteration >= maximum_iterations`,
    including after a `break` on convergence at the last permitted iteration."""
    _, iterations = parsed()
    warning = ["EXIT: Maximum iterations reached: 5."]
    assert classify([EXIT_OPTIMAL], warning, iterations, maximum=5) == "TRF_CONVERGED"


def test_feasible_stalled_needs_the_insufficient_progress_warning() -> None:
    _, iterations = parsed()
    warning = [WARNING_INSUFFICIENT_PROGRESS]
    assert classify([EXIT_FEASIBLE], warning, iterations) == "TRF_FEASIBLE_STALLED"
    assert classify([EXIT_FEASIBLE], [], iterations) == "TRF_ERROR(exit_mismatch)"


def test_max_iterations_needs_the_warning_and_that_many_logged_iterations() -> None:
    _, iterations = parsed()
    reached = ["EXIT: Maximum iterations reached: 4."]
    assert classify([], reached, iterations, maximum=4) == "TRF_MAX_ITERATIONS"
    assert classify([], reached, iterations, maximum=5) == "TRF_ERROR(exit_mismatch)"
    assert classify([], reached, iterations[:4], maximum=4) == "TRF_ERROR(exit_mismatch)"


# -- the registered configurations ----------------------------------------------------------------


def test_the_trsp_options_are_the_design_notes_table() -> None:
    assert dict(TRSP_OPTIONS) == {
        "linear_solver": "mumps",
        "hessian_approximation": "exact",
        "bound_relax_factor": 0.0,
        "honor_original_bounds": "yes",
        "mu_strategy": "monotone",
        "tol": 1e-8,
        "constr_viol_tol": 1e-8,
        "compl_inf_tol": 1e-8,
        "dual_inf_tol": 1e-6,
        "acceptable_iter": 0,
        "max_iter": 500,
        "max_wall_time": 120.0,
        "nlp_scaling_method": "user-scaling",
        "print_level": 0,
    }


def test_the_step_size_termination_is_half_the_scaled_decision_tolerance() -> None:
    """§6.7: 0.005556 for C1 REAL (δ = 0.5 K, h = 45 K) and 0.0125 for TR-E2 (h = 20 K)."""
    assert step_size_termination([0.5], [45.0]) == pytest.approx(0.005556, abs=5e-7)
    assert step_size_termination([0.5], [20.0]) == 0.0125
    assert step_size_termination([0.5, 0.01], [20.0, 0.1]) == 0.0125
    config = trf_config_v1(0.0125)
    assert config["step_size_termination"] == 0.0125
    assert config["maximum_radius"] == 1.0 and config["solver"] == "openflowsheet_trsp_ipopt"
    assert "step_size_termination" not in TRF_CONFIG_V1
    with pytest.raises(ValueError):
        step_size_termination([], [])


# -- the pin and readiness (G2's default-gate half) -----------------------------------------------


def test_readiness_names_every_failing_pin_item(tmp_path: Path) -> None:
    """A patched version, a module with a changed byte, a missing module and an unaudited
    executable each give their reason, all of them listed."""
    modules = tmp_path / "trustregion"
    modules.mkdir()
    for name in TRF_MODULE_SHA256:
        (modules / name).write_bytes(b"not the pinned module\n")
    (modules / "util.py").unlink()
    executable = tmp_path / "ipopt"
    executable.write_bytes(b"not the audited executable")
    readiness = framework_readiness(version="6.10.2", module_dir=modules, executable=executable)
    assert readiness.status == "UNSUPPORTED"
    assert readiness.codes == ("TRUST_REGION_FRAMEWORK_UNPINNED", "TRSP_SOLVER_UNAUDITED")
    details = " ".join(reason.detail for reason in readiness.reasons)
    assert "'6.10.2'" in details and PYOMO_VERSION in details
    assert all(name in details for name in TRF_MODULE_SHA256)
    assert "SHA-256 None" in details  # the missing module
    missing = framework_readiness(
        version=PYOMO_VERSION, module_dir=modules, executable=tmp_path / "absent"
    )
    assert "no subproblem executable" in missing.reasons[-1].detail


def test_without_pyomo_the_framework_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Design note §6.8: in the default install readiness is
    `UNSUPPORTED(TRUST_REGION_FRAMEWORK_UNAVAILABLE)` naming the audit. Pyomo is hidden from
    the lookup, so the case is checked whichever environment runs it."""
    import importlib.util

    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name, *a: None if name == "pyomo" else real(name, *a)
    )
    readiness = framework_readiness()
    assert readiness.status == "UNSUPPORTED"
    assert readiness.codes == ("TRUST_REGION_FRAMEWORK_UNAVAILABLE",)
    assert "docs/m03-ipopt-audit.md" in readiness.reasons[0].detail


#: WO-1's [A10] audit record of the Ipopt executable (audit §11), merged at `aef41bf`.
TRSP_INVENTORY = REPO_ROOT / "benchmarks" / "m05" / "trsp-inventory-x86_64.json"


def test_the_pin_is_what_wo1_audited() -> None:
    """The adapter's pin (WO-3) and the audit record (WO-1) name the same framework and the same
    executable: the five TRF module hashes, the Pyomo version, and `bin/ipopt`'s SHA-256 — as the
    workload measured it and as the object inventory lists it."""
    record = json.loads(TRSP_INVENTORY.read_text(encoding="utf-8"))
    run = record["workload"]["executable"]
    assert run["trf_modules"] == dict(TRF_MODULE_SHA256)
    assert run["versions"]["pyomo"] == PYOMO_VERSION
    assert run["executable_pinned"] == "$ENV/bin/ipopt"
    assert run["executable"] == TRSP_EXECUTABLE_SHA256
    (inventoried,) = [entry for entry in record["objects"] if entry["path"] == "$ENV/bin/ipopt"]
    assert inventoried["sha256"] == TRSP_EXECUTABLE_SHA256
