"""The TRF runner and its subproblem solver (M05 design note §6.7; ADR 0038 D1, D4, D8; R-260,
R-263).

**The subproblem solver** is `openflowsheet_trsp_ipopt`, registered here at import: Pyomo's `IPOPT`
shell plugin with the executable pinned to the audited `<sys.prefix>/bin/ipopt` (validated, so it
works with no `ipopt` on `PATH`; probe P10) and the options `M05-trsp-ipopt-v1`. TRF needs the ASL
executable: it passes `keepfiles` and `tee` to its subproblem solver, which PyNumero's cyipopt
refuses (probe P8).

**A run** (`run_trf`) checks the pin first — any mismatch raises `TrustRegionUnsupportedError` and
nothing runs — then gives every holder of the projection the run's `RunState` and budgets, puts a
`TrfLogHandler` on `pyomo.contrib.trustregion` at INFO with propagation off, captures `stdout`
(TRF's `EXIT:` prints and its `model.display()`), and calls
`SolverFactory("trustregion").solve(model, decisions, basis_rule, **config)` — the configuration
goes to `solve()`, never to the constructor (probe P8). The outcome is design note §6.7's:

- `TRF_TRUTH_REFUSED(<status>:<reason>)` whenever a holder refused during the run, whether or not
  TRF saw the exception: Pyomo 6.10.1's `EFReplacement.exitNode` swallows any exception from the
  start-value evaluation and sets the holder variable to 0, so TRF's own account cannot be trusted
  after a refusal;
- `TRF_SUBPROBLEM_FAILED` for TRF's `ArithmeticError("EXIT: Model solve failed …")`;
- `TRF_ERROR(<exception class>)` for anything else raised, including the `ValueError` of TRF's DOF
  check, and `TRF_ERROR(exit_mismatch | log | trf_map)` when what TRF returned does not read back;
- otherwise `trf_state.classify_exit`: `TRF_CONVERGED`, `TRF_FEASIBLE_STALLED` or
  `TRF_MAX_ITERATIONS`, the three outcomes that return TRF's clone.

`stdout` capture is process-global, so there is **one TRF run per process**: a second concurrent
call raises rather than interleaving.
"""

from __future__ import annotations

import contextlib
import io
import logging
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from pyomo.solvers.plugins.solvers.IPOPT import IPOPT

from openflowsheet.canonical import document_sha256
from openflowsheet.studies.trust_region.holders import ColdBudget, RunState, TruthRefused
from openflowsheet.studies.trust_region.projection import Projection
from openflowsheet.studies.trust_region.trf_state import (
    RETURNS_MODEL,
    TRF_PACKAGE,
    TRF_SUBPROBLEM_FAILED,
    TRSP_OPTIONS,
    TRSP_SOLVER_ALIAS,
    IterationRecord,
    ReadinessReason,
    TrfLogError,
    TrfLogHandler,
    classify_exit,
    framework_readiness,
    last_accepted,
    reconstruct_filter,
    trf_error,
    trsp_executable,
    truth_refused,
)

#: TRF's message when a subproblem does not terminate optimally (`interface.solveModel`).
_SUBPROBLEM_FAILED_PREFIX: Final = "EXIT: Model solve failed"
_RUN_LOCK = threading.Lock()


@SolverFactory.register(TRSP_SOLVER_ALIAS, doc="M05-trsp-ipopt-v1: the audited Ipopt executable")
class TrspIpopt(IPOPT):  # type: ignore[misc]
    """The `ipopt` shell plugin, pinned to the audited executable with `M05-trsp-ipopt-v1`."""

    def __init__(self, **kwds: Any) -> None:
        super().__init__(**kwds)
        self.set_executable(str(trsp_executable()), validate=True)
        self.options.update(TRSP_OPTIONS)


class TrustRegionUnsupportedError(RuntimeError):
    """The framework is not the pinned one (`UNSUPPORTED(<codes>)`); nothing was run."""

    def __init__(self, reasons: Sequence[ReadinessReason]) -> None:
        codes = ", ".join(dict.fromkeys(reason.code for reason in reasons))
        super().__init__(f"UNSUPPORTED({codes}): " + "; ".join(r.detail for r in reasons))
        self.reasons = tuple(reasons)


@dataclass(frozen=True)
class TrfFinal:
    """The iterate TRF returned: decisions as parameter values, and the logged objective (in
    the problem's own sense) and θ of the last accepted iteration."""

    decisions: Mapping[str, float]
    objective: float
    theta: float

    def as_document(self) -> dict[str, Any]:
        return {"decisions": dict(self.decisions), "objective": self.objective, "theta": self.theta}


@dataclass(frozen=True)
class TrfRun:
    run_id: str
    outcome: str
    iterations: tuple[IterationRecord, ...]
    filter: tuple[tuple[float, float], ...]
    exit_lines: tuple[str, ...]
    warnings: tuple[str, ...]
    log: tuple[str, ...]
    config: Mapping[str, Any]
    final: TrfFinal | None
    #: TRF's returned clone, for the outcomes in `RETURNS_MODEL` only.
    model: Any
    #: §6.2's `trf` part: `trf_data.ef_outputs[i]` → the `ExternalFunction` it replaced.
    trf_map: tuple[Mapping[str, str], ...]
    refusal: TruthRefused | None
    error: str | None
    wall_s: float

    def source_map(self, projection: Projection) -> dict[str, Any]:
        """The projection's source map with this run's `trf` part filled."""
        return {**projection.source_map, "trf": [dict(entry) for entry in self.trf_map]}

    def source_map_sha256(self, projection: Projection) -> str:
        return document_sha256(self.source_map(projection))


BasisRule = Callable[[Any, Any], Any]


def run_trf(
    projection: Projection,
    config: Mapping[str, Any],
    *,
    basis_rule: BasisRule | None = None,
    budgets: Mapping[str, Sequence[ColdBudget]] | None = None,
    run_id: str = "trf-1",
) -> TrfRun:
    """Run TRF once on `projection` with `config` (passed to `solve()`) and read back its state.

    `budgets` maps a holder's name to the caps its cold value requests are admitted against.
    Raises `TrustRegionUnsupportedError` before any run if the pin does not hold."""
    readiness = framework_readiness()
    if readiness.status != "READY":
        raise TrustRegionUnsupportedError(readiness.reasons)
    if not _RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("one TRF run per process: stdout capture is process-global (§6.7)")
    try:
        return _run(projection, config, basis_rule, budgets or {}, run_id)
    finally:
        _RUN_LOCK.release()


def _run(
    projection: Projection,
    config: Mapping[str, Any],
    basis_rule: BasisRule | None,
    budgets: Mapping[str, Sequence[ColdBudget]],
    run_id: str,
) -> TrfRun:
    solver = SolverFactory("trustregion")
    effective = solver.config(dict(config))
    run = RunState(run_id)
    handler = TrfLogHandler(run)
    logger = logging.getLogger(TRF_PACKAGE)
    saved = (logger.level, logger.propagate)
    captured = io.StringIO()
    refused_before = {holder.name: len(holder.refusals) for holder in projection.holders}
    for holder in projection.holders:
        holder.begin_run(run, budgets.get(holder.name, ()))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    start = time.perf_counter()
    returned: Any = None
    raised: BaseException | None = None
    try:
        with contextlib.redirect_stdout(captured):
            returned = solver.solve(
                projection.model, projection.decision_variables, basis_rule, **dict(config)
            )
    except Exception as error:  # noqa: BLE001 - every exception is mapped to a typed outcome
        raised = error
    finally:
        wall = time.perf_counter() - start
        logger.removeHandler(handler)
        logger.setLevel(saved[0])
        logger.propagate = saved[1]
        for holder in projection.holders:
            holder.end_run()

    exit_lines = tuple(
        line for line in captured.getvalue().splitlines() if line.startswith("EXIT:")
    )
    refusals = sorted(
        (
            refusal
            for holder in projection.holders
            for refusal in holder.refusals[refused_before[holder.name] :]
        ),
        key=lambda refusal: refusal.order,
    )
    try:
        iterations = handler.iterations()
        log_error = None
    except TrfLogError as error:
        iterations = ()
        log_error = str(error)

    outcome: str
    refusal = refusals[0] if refusals else None
    error_text = None if raised is None else f"{type(raised).__name__}: {raised}"
    if refusal is not None:
        outcome = truth_refused(refusal.code)
    elif raised is not None:
        if type(raised) is ArithmeticError and str(raised).startswith(_SUBPROBLEM_FAILED_PREFIX):
            outcome = TRF_SUBPROBLEM_FAILED
        else:
            outcome = trf_error(type(raised).__name__)
    elif log_error is not None:
        outcome = trf_error("log")
        error_text = log_error
    else:
        outcome = classify_exit(
            exit_lines=exit_lines,
            warnings=handler.warnings,
            iterations=iterations,
            feasibility_termination=float(effective.feasibility_termination),
            step_size_termination=float(effective.step_size_termination),
            maximum_iterations=int(effective.maximum_iterations),
        )

    model = returned if outcome in RETURNS_MODEL else None
    trf_map: tuple[Mapping[str, str], ...] = ()
    final = None
    if model is not None:
        try:
            trf_map = _trf_map(projection, model)
        except ValueError as error:
            outcome, model, error_text = trf_error("trf_map"), None, str(error)
    if model is not None:
        accepted = last_accepted(iterations)
        assert accepted is not None  # classify_exit refused an empty log
        sign = -1.0 if projection.source_map["objective"]["sense"] == "maximize" else 1.0
        final = TrfFinal(
            decisions=projection.decision_parameters(model),
            objective=sign * accepted.objective,
            theta=accepted.theta,
        )
    return TrfRun(
        run_id=run_id,
        outcome=outcome,
        iterations=iterations,
        filter=reconstruct_filter(
            iterations,
            float(effective.param_filter_gamma_f),
            float(effective.param_filter_gamma_theta),
        ),
        exit_lines=exit_lines,
        warnings=tuple(handler.warnings),
        log=tuple(handler.messages),
        config=dict(config),
        final=final,
        model=model,
        trf_map=trf_map,
        refusal=refusal,
        error=error_text,
        wall_s=wall,
    )


def _trf_map(projection: Projection, model: Any) -> tuple[Mapping[str, str], ...]:
    """§6.2's `trf` part, checked: every `trf_data.ef_outputs[i]` replaced exactly one of the
    projection's `ExternalFunction`s, and every one of them was replaced exactly once.

    The EF is found by its value callback, which TRF's clone shares with the original (the
    closures are atomic under `deepcopy`); TRF deletes the `ExternalFunction` components from its
    clone, so their names are not read from it."""
    data = model.trf_data
    entries = []
    for index in data.ef_outputs:
        truth = data.truth_models[data.ef_outputs[index]]
        callback: Any = getattr(truth._fcn, "_fcn", None)
        if callback not in projection.ef_names:
            raise ValueError(f"trf_data.ef_outputs[{index}] replaced an unknown function")
        entries.append(
            {"holder": f"trf_data.ef_outputs[{index}]", "ef": projection.ef_names[callback]}
        )
    replaced = [entry["ef"] for entry in entries]
    if sorted(replaced) != sorted(projection.ef_names.values()):
        raise ValueError(
            f"TRF replaced {sorted(replaced)}; the projection has "
            f"{sorted(projection.ef_names.values())}"
        )
    return tuple(entries)


def objective_value(model: Any) -> float:
    """The value of a model's active objective (TRF's clone minimizes −J for a maximization)."""
    (objective,) = list(model.component_data_objects(pyo.Objective, active=True))
    return float(pyo.value(objective))
