"""The TRF runner and its subproblem solver (M05 design note §6.7; ADR 0038 D1, D4, D8; R-260,
R-263).

**The subproblem solver** is `openflowsheet_trsp_ipopt`, registered here at import: Pyomo's `IPOPT`
shell plugin with the executable pinned to the audited `<sys.prefix>/bin/ipopt` (validated, so it
works with no `ipopt` on `PATH`; probe P10) and the options `M05-trsp-ipopt-v1`. TRF needs the ASL
executable: it passes `keepfiles` and `tee` to its subproblem solver, which PyNumero's cyipopt
refuses (probe P8).

**A run** (`run_trf`) checks the pin first — any mismatch raises `TrustRegionUnsupportedError` and
nothing runs — then the basis (R-277, design note §6.6): every `ExternalFunction` of the projection
needs an `EFBasis`, or TRF would silently use its default b ≡ 0, under which a PMP can be infeasible
at iteration 0 (probe P14 a). A missing or incomplete basis, a basis for an unknown EF, or a zero
basis on any projection but TR-E1's exempt oracle raises `TrfConfigurationRefusedError`
(`TRF_CONFIGURATION_REFUSED(<reason>)`) and nothing runs; TR-E1 is given the explicit, test-only
`zero_basis`, which the run records as `basis: zero`. Then it gives every holder of the projection
the run's `RunState` and budgets, and **pre-flights** the start (R-276, design note §4 P13, §16.3):
every holder is asked for its values at x₀ — the request TRF's `EFReplacement.exitNode` makes first,
inside a bare `except:` that swallows a refusal and sets the holder variable to 0. A refusal there
is `TRF_TRUTH_REFUSED(start:<status>:<reason>)` and TRF is never invoked; otherwise TRF's own start
evaluation is a memo hit, and the ledger's `trf_start_value` request is the pre-flight's, so §8.3's
request identity is unchanged. Then it puts a `TrfLogHandler` on `pyomo.contrib.trustregion` at INFO
with propagation off, captures `stdout` (TRF's `EXIT:` prints and its `model.display()`), and calls
`SolverFactory("trustregion").solve(model, decisions, rule, **config)`, with `rule` the basis as
TRF's `ext_fcn_surrogate_map_rule` — the configuration goes to `solve()`, never to the constructor
(probe P8). The outcome is design note §6.7's:

- `TRF_TRUTH_REFUSED(<status>:<reason>)` whenever a holder refused during the run, whatever TRF
  returned or printed (R-276's backstop): a swallowed refusal can be followed by a run that ends
  "optimal", so TRF's own account cannot be trusted after one;
- `TRF_SUBPROBLEM_FAILED` for TRF's `ArithmeticError("EXIT: Model solve failed …")`;
- `TRF_ERROR(<exception class>)` for anything else raised, including the `ValueError` of TRF's DOF
  check, and `TRF_ERROR(exit_mismatch | log | theta_recheck | trf_map)` when what TRF returned does
  not read back;
- otherwise `trf_state.classify_exit`, from the `EXIT:` lines, the log and **θ re-checked from
  the returned model** (R-279): `TRF_CONVERGED` (≥ 1 accepted TRSP step), `TRF_EXIT_WITHOUT_STEP`,
  `TRF_FEASIBLE_STALLED`, `TRF_STALLED_INCONSISTENT` or `TRF_MAX_ITERATIONS`. All but
  `TRF_STALLED_INCONSISTENT` keep TRF's clone.

The re-check is `TRF.py`'s own feasibility measure, Σᵢ |yᵢ − dᵢ(w)| over its holder variables,
evaluated on the returned clone while the holders still serve the run: every truth value it needs
is one TRF requested at that state, so it is all memo hits, recorded in the ledger. It is
`TrfRun.theta_recheck` for every run TRF returned from. TRF itself is not patched (the pin, R-260):
only its labelling is guarded.

For the outcomes that keep the clone, the projection's omitted rows are evaluated at the returned
state and recorded as `TrfRun.omitted_rows_final` (R-274's fact 4), and so are the pins of its
eliminated zero flows, `TrfRun.zero_pins_final` (R-296); the returned state is mapped back to
every spec variable, with +0.0 for each eliminated flow, as `TrfRun.final_state`. Those are the
hooks P2 reads: P2 (stage B's parent checks, design note §7.4) is not built yet, and a failed
check there is `PROJECTION_DISAGREES`; the run's own outcome does not change.

`stdout` capture is process-global, so there is **one TRF run per process**: a second concurrent
call raises rather than interleaving.
"""

from __future__ import annotations

import contextlib
import io
import logging
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from pyomo.solvers.plugins.solvers.IPOPT import IPOPT

from openflowsheet.canonical import document_sha256
from openflowsheet.studies.trust_region.holders import ColdBudget, RunState, TruthRefused
from openflowsheet.studies.trust_region.projection import OmittedRowsCheck, Projection
from openflowsheet.studies.trust_region.trf_state import (
    RETURNS_MODEL,
    TRF_PACKAGE,
    TRF_SUBPROBLEM_FAILED,
    TRSP_OPTIONS,
    TRSP_SOLVER_ALIAS,
    EFBasis,
    IterationRecord,
    ReadinessReason,
    TrfLogError,
    TrfLogHandler,
    basis_refusals,
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


class TrfConfigurationRefusedError(ValueError):
    """The run's configuration is refused (`TRF_CONFIGURATION_REFUSED(<reason>)`, R-277); nothing
    was run and no holder was asked for anything."""

    def __init__(self, codes: Sequence[str]) -> None:
        super().__init__("; ".join(codes))
        self.codes = tuple(codes)


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
    #: Each EF's basis kind (`EFBasis.kind`), by EF name: `zero` flags TR-E1's native b ≡ 0.
    basis: Mapping[str, str]
    #: R-279: TRF's θ recomputed from the model it returned; `None` when it returned none.
    theta_recheck: float | None
    #: R-274's fact 4 at the returned state, for the outcomes in `RETURNS_MODEL` only.
    omitted_rows_final: OmittedRowsCheck | None = None
    #: R-296: the zero-flow pins at the returned state, for the outcomes in `RETURNS_MODEL` only.
    zero_pins_final: OmittedRowsCheck | None = None
    #: The returned state through the projection's inverse map (`Projection.state_of`: +0.0 for
    #: every eliminated zero flow, R-296), for the outcomes in `RETURNS_MODEL` only.
    final_state: Mapping[str, float] | None = None

    def source_map(self, projection: Projection) -> dict[str, Any]:
        """The projection's source map with this run's `trf` part filled."""
        return {**projection.source_map, "trf": [dict(entry) for entry in self.trf_map]}

    def source_map_sha256(self, projection: Projection) -> str:
        return document_sha256(self.source_map(projection))


def run_trf(
    projection: Projection,
    config: Mapping[str, Any],
    *,
    basis: Mapping[str, EFBasis] | None = None,
    budgets: Mapping[str, Sequence[ColdBudget]] | None = None,
    run_id: str = "trf-1",
) -> TrfRun:
    """Run TRF once on `projection` with `config` (passed to `solve()`) and `basis` (one
    `EFBasis` per `ExternalFunction`, by EF name), and read back its state.

    `budgets` maps a holder's name to the caps its cold value requests are admitted against.
    Raises `TrustRegionUnsupportedError` before any run if the pin does not hold, and
    `TrfConfigurationRefusedError` if the basis is missing, incomplete or a zero basis off TR-E1."""
    readiness = framework_readiness()
    if readiness.status != "READY":
        raise TrustRegionUnsupportedError(readiness.reasons)
    refused = basis_refusals(
        projection.ef_names.values(), basis, projection.source_map["shape_check"]["status"]
    )
    if refused:
        raise TrfConfigurationRefusedError(refused)
    assert basis is not None  # basis_refusals refuses None
    if not _RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("one TRF run per process: stdout capture is process-global (§6.7)")
    try:
        return _run(projection, config, basis, budgets or {}, run_id)
    finally:
        _RUN_LOCK.release()


def _run(
    projection: Projection,
    config: Mapping[str, Any],
    basis: Mapping[str, EFBasis],
    budgets: Mapping[str, Sequence[ColdBudget]],
    run_id: str,
) -> TrfRun:
    solver = SolverFactory("trustregion")
    effective = solver.config(dict(config))
    kinds = {name: basis[name].kind for name in sorted(basis)}
    run = RunState(run_id)
    handler = TrfLogHandler(run)
    logger = logging.getLogger(TRF_PACKAGE)
    saved = (logger.level, logger.propagate)
    captured = io.StringIO()
    refused_before = {holder.name: len(holder.refusals) for holder in projection.holders}
    for holder in projection.holders:
        holder.begin_run(run, budgets.get(holder.name, ()))
    preflight_start = time.perf_counter()
    refused: TruthRefused | None = None
    preflown = False
    try:
        refused = _preflight(projection)
        preflown = True
    finally:
        if not preflown or refused is not None:
            for holder in projection.holders:
                holder.end_run()
    if refused is not None:
        return TrfRun(
            run_id=run_id,
            outcome=truth_refused(f"start:{refused.code}"),
            iterations=(),
            filter=(),
            exit_lines=(),
            warnings=(),
            log=(),
            config=dict(config),
            final=None,
            model=None,
            trf_map=(),
            refusal=refused,
            error=None,
            wall_s=time.perf_counter() - preflight_start,
            basis=kinds,
            theta_recheck=None,
        )
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    start = time.perf_counter()
    returned: Any = None
    raised: BaseException | None = None
    theta_recheck: float | None = None
    recheck_error: str | None = None
    try:
        with contextlib.redirect_stdout(captured):
            returned = solver.solve(
                projection.model,
                projection.decision_variables,
                _surrogate_map_rule(projection, basis),
                **dict(config),
            )
    except Exception as error:  # noqa: BLE001 - every exception is mapped to a typed outcome
        raised = error
    else:
        try:
            theta_recheck = recheck_theta(returned)
        except TruthRefused:
            pass  # kept on its holder: the outcome below is that refusal
        except Exception as error:  # noqa: BLE001 - mapped to TRF_ERROR(theta_recheck)
            recheck_error = f"{type(error).__name__}: {error}"
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
    elif theta_recheck is None:
        outcome = trf_error("theta_recheck")
        error_text = recheck_error
    else:
        outcome = classify_exit(
            exit_lines=exit_lines,
            warnings=handler.warnings,
            iterations=iterations,
            theta_recheck=theta_recheck,
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
    omitted_rows_final = projection.omitted_rows_at(model) if model is not None else None
    zero_pins_final = projection.zero_pins_at(model) if model is not None else None
    final_state = projection.state_of(model) if model is not None else None
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
        basis=kinds,
        theta_recheck=theta_recheck,
        omitted_rows_final=omitted_rows_final,
        zero_pins_final=zero_pins_final,
        final_state=final_state,
    )


def _preflight(projection: Projection) -> TruthRefused | None:
    """R-276: every holder's values at the start, in the projection's holder order, from the
    model's `x` exactly as TRF's `EFReplacement` reads them; the first refusal, or `None`.

    Stops at the first refusal: the run is refused whatever the other holders would answer, and a
    truth's evaluation is the expensive request the budgets exist for."""
    state = list(projection.state_of().values())
    for holder, inputs in zip(projection.holders, projection.holder_inputs, strict=True):
        try:
            holder.request_values([state[i] for i in inputs])
        except TruthRefused as refusal:
            return refusal
    return None


def _surrogate_map_rule(projection: Projection, basis: Mapping[str, EFBasis]) -> Any:
    """TRF's `ext_fcn_surrogate_map_rule(component, ef_expr)`: the `EFBasis` of the EF that
    `ef_expr` calls, built on its inputs — the first of `ef_expr.args`, the clone's variables; a
    Python-callback `ExternalFunction` appends its function id after them (as the holder reads
    only its first `n_in` arguments). The EF is found by its value callback, which the clone
    shares with the original (as `_trf_map` finds it)."""
    source = projection.source_map
    inputs = {
        entry["ef"]: len(entry["input_variable_ids"])
        for entry in (*source["block_outputs"], *source["external_links"])
    }

    def rule(component: Any, ef_expr: Any) -> Any:
        name = projection.ef_names[ef_expr._fcn._fcn]
        return basis[name].build(list(ef_expr.args[: inputs[name]]))

    return rule


def recheck_theta(model: Any) -> float:
    """R-279: TRF's feasibility measure θ = Σᵢ |yᵢ − dᵢ(w)| recomputed on the model TRF returned —
    `TRFInterface.calculateFeasibility`'s expression, in its order, over `trf_data.ef_outputs` —
    with every dᵢ evaluated through its holder at the state the model holds."""
    data = model.trf_data
    return float(
        sum(
            abs(pyo.value(output) - pyo.value(data.truth_models[output]))
            for _, output in data.ef_outputs.items()
        )
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
