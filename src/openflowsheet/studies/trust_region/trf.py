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
  the returned model** (R-279): `TRF_CONVERGED` (≥ 1 accepted TRSP step, the final one neither
  rejected nor radius-limited), `TRF_EXIT_UNVERIFIED(<reason>)` (R-401: an "Optimal" exit whose
  final step was rejected or radius-limited), `TRF_EXIT_WITHOUT_STEP`, `TRF_FEASIBLE_STALLED`,
  `TRF_STALLED_INCONSISTENT` or `TRF_MAX_ITERATIONS`. All but `TRF_STALLED_INCONSISTENT` keep
  TRF's clone.

The precedence (R-299, design note §17.4): `TRF_TRUTH_REFUSED` (the backstop); then θ_recheck
above the feasibility termination is `TRF_STALLED_INCONSISTENT` whatever the `EXIT:` line claims
(an "Optimal" line whose own logged θ and step agree with it included); then
`TRF_EXIT_WITHOUT_STEP`; then `TRF_EXIT_UNVERIFIED`; then `TRF_CONVERGED` or
`TRF_FEASIBLE_STALLED`. `TRF_ERROR(exit_mismatch)`
stays a line that disagrees with TRF's own log — a defect, never retried. Every run TRF returned
from records `exit_claim` (`optimal`, `feasible` or `None`), `theta_logged` (the last logged
iteration's θ, which TRF's termination read) beside `theta_recheck`, and
`final_state_is_last_truth_point`: whether, for every holder, the inputs the returned model holds
are, bitwise (zeros normalized, as the memo keys them), those of the holder's last request before
the re-check — `False` points at a TRF that terminated on a state other than the one it returned.
Every run with a logged TRSP records R-401's `final_step_ratio` s_K/Δ_K and
`final_step_at_box_bound` (a bounded decision of the returned model within 1e-6 scaled of its box
bound; `None` when TRF returned no model).

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
import hashlib
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

from openflowsheet.canonical import document_sha256, encode_doubles
from openflowsheet.studies.trust_region.checks import AT_BOUND_SCALED
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
    TrfConfigurationRefusedError,
    TrfLogError,
    TrfLogHandler,
    basis_refusals,
    classify_exit,
    exit_claim,
    final_step_ratio,
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

#: A basis built on the projection inside the run, before TRF starts (S33, `run_trf`).
BasisFor = Callable[[Projection], Mapping[str, EFBasis]]


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
    #: Each EF's basis kind (`EFBasis.kind`), by EF name: `zero` flags TR-E1's native b ≡ 0.
    basis: Mapping[str, str]
    #: R-279: TRF's θ recomputed from the model it returned; `None` when it returned none.
    theta_recheck: float | None
    #: R-274's fact 4 at the returned state, for the outcomes in `RETURNS_MODEL` only.
    omitted_rows_final: OmittedRowsCheck | None = None
    #: R-296: the zero-flow pins at the returned state, for the outcomes in `RETURNS_MODEL` only.
    zero_pins_final: OmittedRowsCheck | None = None
    #: R-327: the `feasibility_termination` TRF ran with (its effective configuration), against
    #: which P2 judges θ_recheck.
    feasibility_termination: float | None = None
    #: The returned state through the projection's inverse map (`Projection.state_of`: +0.0 for
    #: every eliminated zero flow, R-296), for the outcomes in `RETURNS_MODEL` only.
    final_state: Mapping[str, float] | None = None
    #: R-299, for every run TRF returned from: the `EXIT:` line's claim (`optimal`, `feasible`,
    #: or `None` for none or several), the last logged iteration's θ, and whether the returned
    #: state is, for every holder, the point of its last request before the re-check.
    exit_claim: str | None = None
    theta_logged: float | None = None
    final_state_is_last_truth_point: bool | None = None
    #: R-401, for every run with a logged TRSP: s_K/Δ_K of the final logged iteration K, and
    #: whether a bounded decision of the returned model is within 1e-6 (scaled) of its box bound
    #: (`None` when TRF returned no model).
    final_step_ratio: float | None = None
    final_step_at_box_bound: bool | None = None
    #: R-400: the run's `basis` block when its basis carries one (`M05-basis-v2`), and the
    #: candidate limitations the basis adds (`basis_without_curvature`).
    basis_record: Mapping[str, Any] | None = None
    basis_limitations: tuple[str, ...] = ()

    def source_map(self, projection: Projection) -> dict[str, Any]:
        """The projection's source map with this run's `trf` part filled."""
        return {**projection.source_map, "trf": [dict(entry) for entry in self.trf_map]}

    def source_map_sha256(self, projection: Projection) -> str:
        return document_sha256(self.source_map(projection))


def run_trf(
    projection: Projection,
    config: Mapping[str, Any],
    *,
    basis: Mapping[str, EFBasis] | BasisFor | None = None,
    budgets: Mapping[str, Sequence[ColdBudget]] | None = None,
    run_id: str = "trf-1",
    gradient_check: Callable[[Projection], Any] | None = None,
    check_budgets: Mapping[str, Sequence[ColdBudget]] | None = None,
) -> TrfRun:
    """Run TRF once on `projection` with `config` (passed to `solve()`) and `basis` (one
    `EFBasis` per `ExternalFunction`, by EF name), and read back its state.

    `basis` may instead be a builder, called on `projection` once the holders serve the run and
    before TRF starts (S33): its requests are the run's (§8.3's `basis_fd_point`) and are admitted
    against the run's budgets, but carry no call-order purpose (`RunState.forming_basis`).
    `budgets` maps a holder's name to the caps its cold value requests are admitted against.
    `gradient_check`, when given, is called on `projection` inside the run before the basis
    (R-406: the study's gradient-quality check belongs to the run whose w₀ it is at): its requests
    carry the run id and stage `fdcheck`, and are admitted against `check_budgets` (the study's
    cap, never the run's) instead of `budgets`.
    Raises `TrustRegionUnsupportedError` before any run if the pin does not hold, and
    `TrfConfigurationRefusedError` if the basis is missing, incomplete or a zero basis off TR-E1
    (a built basis is judged when built, before TRF starts)."""
    readiness = framework_readiness()
    if readiness.status != "READY":
        raise TrustRegionUnsupportedError(readiness.reasons)
    if not callable(basis):
        _refuse_basis(projection, basis)
        assert basis is not None  # _refuse_basis refuses None
    if not _RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("one TRF run per process: stdout capture is process-global (§6.7)")
    try:
        return _run(
            projection, config, basis, budgets or {}, run_id, gradient_check, check_budgets or {}
        )
    finally:
        _RUN_LOCK.release()


def _refuse_basis(projection: Projection, basis: Mapping[str, EFBasis] | None) -> None:
    """Raise `TrfConfigurationRefusedError` if `basis` may not be used on `projection` (R-277)."""
    refused = basis_refusals(
        projection.ef_names.values(), basis, projection.source_map["shape_check"]["status"]
    )
    if refused:
        raise TrfConfigurationRefusedError(refused)


def _run(
    projection: Projection,
    config: Mapping[str, Any],
    basis: Mapping[str, EFBasis] | BasisFor,
    budgets: Mapping[str, Sequence[ColdBudget]],
    run_id: str,
    gradient_check: Callable[[Projection], Any] | None = None,
    check_budgets: Mapping[str, Sequence[ColdBudget]] | None = None,
) -> TrfRun:
    solver = SolverFactory("trustregion")
    effective = solver.config(dict(config))
    run = RunState(run_id)
    handler = TrfLogHandler(run)
    logger = logging.getLogger(TRF_PACKAGE)
    saved = (logger.level, logger.propagate)
    captured = io.StringIO()
    checked = check_budgets or {}
    for holder in projection.holders:
        holder.begin_run(run, budgets.get(holder.name, ()), checked.get(holder.name, ()))
    preflight_start = time.perf_counter()
    refused: TruthRefused | None = None
    refused_phase = "start:"
    built: Mapping[str, EFBasis] | None = None if callable(basis) else basis
    preflown = False
    try:
        try:
            if gradient_check is not None:
                run.checking_gradient = True
                try:
                    gradient_check(projection)
                finally:
                    run.checking_gradient = False
            if callable(basis):
                run.forming_basis = True
                try:
                    built = basis(projection)
                finally:
                    run.forming_basis = False
        except TruthRefused as unhandled:
            # R-400 step 9: a refusal the check or the basis did not handle (a budget refusal)
            # is the run's outcome, `TRF_TRUTH_REFUSED(<code>)`; nothing more is asked.
            refused, refused_phase = unhandled, ""
        else:
            assert built is not None
            _refuse_basis(projection, built)
            refused = _preflight(projection)
        preflown = True
    finally:
        if not preflown or refused is not None:
            for holder in projection.holders:
                holder.end_run()
    # The backstop (R-276) counts the refusals from here on: one the basis handled itself (R-400
    # step 9: the curvature's fallback) is recorded in its basis block, not the run's outcome.
    refused_before = {holder.name: len(holder.refusals) for holder in projection.holders}
    basis_record = getattr(built, "record", None)
    basis_limitations = tuple(getattr(built, "limitations", ()))
    kinds = {} if built is None else {name: built[name].kind for name in sorted(built)}
    if refused is not None:
        return TrfRun(
            feasibility_termination=float(effective.feasibility_termination),
            run_id=run_id,
            outcome=truth_refused(f"{refused_phase}{refused.code}"),
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
            basis_record=basis_record,
            basis_limitations=basis_limitations,
            theta_recheck=None,
        )
    assert built is not None  # no refusal: the basis was built
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    start = time.perf_counter()
    returned: Any = None
    raised: BaseException | None = None
    theta_recheck: float | None = None
    recheck_error: str | None = None
    last_points: dict[str, str | None] = {}
    try:
        with contextlib.redirect_stdout(captured):
            returned = solver.solve(
                projection.model,
                projection.decision_variables,
                _surrogate_map_rule(projection, built),
                **dict(config),
            )
    except Exception as error:  # noqa: BLE001 - every exception is mapped to a typed outcome
        raised = error
    else:
        last_points = {holder.name: _last_point(holder) for holder in projection.holders}
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

    # R-401: the final step against the radius it was solved with, and the returned decision.
    radius_rule = {
        "trust_radius": float(effective.trust_radius),
        "minimum_radius": float(effective.minimum_radius),
        "gamma_c": float(effective.radius_update_param_gamma_c),
    }
    step_ratio = final_step_ratio(iterations, **radius_rule)
    at_box_bound = None
    if returned is not None and step_ratio is not None:
        at_box_bound = _at_box_bound(projection, returned)

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
            **radius_rule,
            box_bound_exempt=len(projection.decisions) == 1 and bool(at_box_bound),
        )

    model = returned if outcome in RETURNS_MODEL else None
    claim = theta_logged = same_point = None
    if returned is not None:
        claim = exit_claim(exit_lines)
        theta_logged = iterations[-1].theta if iterations else None
        same_point = _returned_at_last_points(projection, returned, last_points)
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
        feasibility_termination=float(effective.feasibility_termination),
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
        basis_record=basis_record,
        basis_limitations=basis_limitations,
        theta_recheck=theta_recheck,
        omitted_rows_final=omitted_rows_final,
        zero_pins_final=zero_pins_final,
        final_state=final_state,
        exit_claim=claim,
        theta_logged=theta_logged,
        final_state_is_last_truth_point=same_point,
        final_step_ratio=step_ratio,
        final_step_at_box_bound=at_box_bound,
    )


def _at_box_bound(projection: Projection, model: Any) -> bool:
    """R-401's exception: a bounded decision of `model` within 1e-6 (scaled) of a box bound, the
    poll's at-bound rule (§7.4, `checks.AT_BOUND_SCALED`; R-404)."""
    for j, decision in enumerate(projection.decisions):
        if not decision.bounded:
            continue
        scaled = float(pyo.value(model.d[j]))
        if min(abs(scaled + 1.0), abs(scaled - 1.0)) <= AT_BOUND_SCALED:
            return True
    return False


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


def _last_point(holder: Any) -> str | None:
    """The `inputs_sha256` of the holder's last ledger entry (its last request), or `None`."""
    ledger = holder.ledger
    return ledger[-1].inputs_sha256 if ledger else None


def _returned_at_last_points(
    projection: Projection, model: Any, last_points: Mapping[str, str | None]
) -> bool:
    """R-299's `final_state_is_last_truth_point`: every holder's inputs at the returned state
    (through the inverse map) hash as its last request before the re-check did."""
    state = list(projection.state_of(model).values())
    for holder, inputs in zip(projection.holders, projection.holder_inputs, strict=True):
        point = encode_doubles([state[i] for i in inputs])
        if hashlib.sha256(point).hexdigest() != last_points[holder.name]:
            return False
    return True


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
