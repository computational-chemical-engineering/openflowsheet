"""The SYN-001 tear problem: `R(t) = G(t) − t`, and its exact derivative. K03 §3.

**Which residual Newton runs on** was the open question of the K03 specification, and the answer
is this one: three variables, `G` is K02's sequential traversal, and `dR/dt` is the exact Schur
complement of the assembled 49x47 Jacobian rather than a finite difference. The reason it is not
the lifted 47-variable system is decisive rather than aesthetic — in the lifted form both
trivial phase splits are *exact* roots of every row, so a bound-aware Newton can land on one and
report a converged answer with a duty 8237.85 W wrong (K02's finding 3). The traversal cannot:
each unit selects its own phase state, which is blueprint §6.3's default v0.0 formulation.

**The Schur complement is exact, and the consistency check is what makes it honest.** The
derivative is of the *lifted* function at `x(t)`; the residual is of the *traversal*. They are
the same function only where the inner rows are satisfied, so every Jacobian evaluation also
evaluates the inner residual and requires `eta <= 1e-10` in scaled units. A Jacobian taken where
that fails is the derivative of something else, and the attempt ends `INNER_SOLVE_INCONSISTENT`
naming the worst row rather than stepping on it.

**A finite-difference derivative is a test oracle and not a path.** Plan §4.2 demotes it
explicitly, and there is a measured reason beyond obedience: at `t*` the central stencil leaves
the mixer's domain on two of three columns, because `t*` is the saturated boundary itself.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from typing import Final

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import state_vector
from openflowsheet.compiled import EvaluationContext, JacobianResult
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.syn001.flash import total_flow_id
from openflowsheet.models.syn001.flowsheet import (
    FLASH_UNIT,
    HEATER_UNIT,
    SPLITTER_UNIT,
    STREAMS,
    InitializerFailedError,
    Syn001Flowsheet,
    Traversal,
)
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    tp_state,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.numerics.linear import LinearSolveRecord, solve_linear
from openflowsheet.numerics.newton import Evaluation, Problem
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.attempts import (
    SIGNATURE_UNITS,
    AttemptContext,
    SolveResult,
    flash_signature,
    solve_with_attempts,
)
from openflowsheet.orchestrator.budget import BudgetedProvider, BudgetExhaustedError
from openflowsheet.orchestrator.phase_contract import jacobian_pattern
from openflowsheet.orchestrator.rank import AliasElimination, eliminate_alias_rows
from openflowsheet.orchestrator.roots import branch_found, root_fingerprint
from openflowsheet.orchestrator.trace import (
    Counters,
    EliminatedRowRecord,
    SolvePlan,
    SolvePolicy,
    Trace,
)
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.cache import ExactPropertyCache

#: §3.4. Five orders above the measured floor of 2.0e-15 and two below the scaled tolerances.
ETA_INNER: Final = 1e-10

#: §3.1: the recycle stream's component flows.
TEAR_STREAM: Final = "S6"
#: The rows that *define* the tear: `n_rec,i − r n_in,i`, which evaluate to `−R_i`.
TEAR_ROW_FAMILY: Final = "SPLIT-recycle"

#: The finite-difference oracle's step, §13.4: `1e-5 × 3 mol/s`. Not a path (plan §4.2).
FD_STEP: Final = 1e-5 * 3.0


#: Derivation §9's registered tear initializer (`benchmarks/registry.yaml`), the K03 §10.1 chain
#: source recorded as item 0's `initializer_source` (T03 §8.1).
INITIALIZER_ID: Final = "SYN-001-tear-init-v2"


class InnerSolveInconsistentError(RuntimeError):
    """`INNER_SOLVE_INCONSISTENT`: the lifted rows are not satisfied at the traversal's state.

    The Schur complement would then be the derivative of a different function from the one the
    residual measures, which is worse than having no derivative at all.
    """

    def __init__(self, eta: float, worst_row: str) -> None:
        super().__init__(
            f"the inner residual at the reconstructed state is {eta:.3e} in scaled units at row "
            f"{worst_row!r}, above the registered {ETA_INNER:g}; the assembled Jacobian is not "
            "the derivative of the function the traversal computed"
        )
        self.eta = eta
        self.worst_row = worst_row


@dataclass(frozen=True)
class TearPartition:
    """§3.1's partition of the assembled system, by id and never by position."""

    tear_variables: tuple[str, ...]
    tear_rows: tuple[str, ...]
    inner_variables: tuple[str, ...]
    inner_rows: tuple[str, ...]
    elimination: AliasElimination

    def __post_init__(self) -> None:
        if len(self.inner_rows) != len(self.inner_variables):
            raise ValueError(
                f"the inner block is {len(self.inner_rows)}x{len(self.inner_variables)} and not "
                "square; UNSUPPORTED_RANK_STRUCTURE"
            )


class Syn001TearProblem:
    """The three-variable tear of the SYN-001 flowsheet, with its exact derivative."""

    def __init__(
        self,
        flowsheet: Syn001Flowsheet,
        *,
        eta_inner: float = ETA_INNER,
    ) -> None:
        self.flowsheet = flowsheet
        self.eta_inner = eta_inner
        self.spec = flowsheet.spec()
        self.compiled = compile_problem(self.spec)
        metadata = self.compiled.metadata
        # §3.4: the lifted function has no phase switch, so the context pins no signature.
        self.context = EvaluationContext(
            model_version=metadata.model_version,
            constants_sha256=metadata.constants_sha256,
            phase_signature=None,
        )
        self.scaling = Scaling.from_spec(self.spec)
        self.components = flowsheet.components
        #: The evidence of the most recent inner-block solve, for the caller to record. ADR 0004
        #: D2 puts every solve through one function *and* D3 puts its record on a `SolveEvent`;
        #: this problem's inner solve happens inside `jacobian`, where there is no trace, so the
        #: record is handed out rather than dropped.
        self.last_inner_solve: LinearSolveRecord | None = None
        #: §3.4's eta at the most recent Jacobian, for the caller to record. It was computed on
        #: every Jacobian and thrown away, which left A24's trace clause unverifiable.
        self.last_inner_consistency: float = 0.0
        self.partition = self._partition()

    # -- structure -------------------------------------------------------------------------

    def _partition(self) -> TearPartition:
        tear_variables = tuple(flow_id(TEAR_STREAM, component) for component in self.components)
        tear_rows = tuple(
            name
            for name in self.spec.equation_ids
            if name.startswith(f"{SPLITTER_UNIT}:{TEAR_ROW_FAMILY}:")
        )
        if len(tear_rows) != len(tear_variables):
            raise ValueError(f"{len(tear_rows)} tear rows for {len(tear_variables)} tear variables")

        guess = self.flowsheet.initial_recycle()
        state = self.reconstruct(guess)
        jacobian = self._raw_jacobian(state)
        coefficients: dict[str, dict[str, float]] = {n: {} for n in jacobian.row_ids}
        for column, name in enumerate(jacobian.col_ids):
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
                coefficients[jacobian.row_ids[jacobian.indices[offset]]][name] = jacobian.data[
                    offset
                ]

        elimination = eliminate_alias_rows(
            row_ids=self.spec.equation_ids,
            coefficients=coefficients,
            column_kinds=self.spec.variable_kinds,
            residuals=[
                self._raw_rows(self._shift_pressures(state, 0.0)),
                self._raw_rows(self._shift_pressures(state, 997.0)),
            ],
        )
        inner_rows = tuple(name for name in elimination.retained_rows if name not in set(tear_rows))
        inner_variables = tuple(
            name for name in self.spec.variable_ids if name not in set(tear_variables)
        )
        return TearPartition(
            tear_variables=tear_variables,
            tear_rows=tear_rows,
            inner_variables=inner_variables,
            inner_rows=inner_rows,
            elimination=elimination,
        )

    def _shift_pressures(self, state: Mapping[str, float], delta: float) -> dict[str, float]:
        moved = dict(state)
        for index, name in enumerate(self.spec.variable_ids):
            if self.spec.variable_kinds.get(name) == "pressure":
                moved[name] = state[name] + delta * (index + 1)
        return moved

    # -- the traversal, and the state it reconstructs ----------------------------------------

    def tear_state(self, t: Sequence[float] | npt.NDArray[np.float64]) -> StreamState:
        return StreamState(
            n=tuple(float(value) for value in t),
            temperature=self.flowsheet.flash_temperature,
            pressure=self.flowsheet.pressure,
        )

    def reconstruct(
        self, recycle: StreamState, flowsheet: Syn001Flowsheet | None = None
    ) -> dict[str, float]:
        """§3.3: the 47-vector `x(t)`, assembled from one traversal by name.

        With a `flowsheet` (an attempt's: the base one under the attempt's flowsheet context),
        every traversal and re-split call is that attempt's (T03 A03, review M3).
        """
        sheet = flowsheet or self.flowsheet
        traversal = sheet.traverse(recycle)
        if traversal.status != "ok":
            raise ValueError(f"the traversal did not complete: {traversal.status}")
        return self._reconstruct_from(traversal, recycle, sheet)

    def _reconstruct_from(
        self,
        traversal: Traversal,
        recycle: StreamState,
        flowsheet: Syn001Flowsheet | None = None,
    ) -> dict[str, float]:
        sheet = flowsheet or self.flowsheet
        streams = traversal.streams
        duties = traversal.duties
        state = {name: 0.0 for name in self.spec.variable_ids}
        for stream in STREAMS:
            carried = streams[stream]
            state[temperature_id(stream)] = carried.temperature
            state[pressure_id(stream)] = carried.pressure
            for index, component in enumerate(self.components):
                state[flow_id(stream, component)] = carried.n[index]
        state[duty_id(HEATER_UNIT)] = duties[HEATER_UNIT]
        state[duty_id(FLASH_UNIT)] = duties[FLASH_UNIT]

        # The heater outlet's lifted split, from the same kernel the heater used. An exact-cache
        # hit when a cache is in play: the heater already flashed S3 at (T_spec, P).
        split = tp_state(sheet.provider, streams["S3"], sheet.context)
        if split.status != "ok" or split.vapor is None or split.liquid is None:
            raise ValueError(f"the heater outlet could not be re-split: {split.status}")
        for index, component in enumerate(self.components):
            state[vapor_flow_id("S3", component)] = split.vapor.n[index]
            state[liquid_flow_id("S3", component)] = split.liquid.n[index]
        state[vapor_total_id("S3")] = sum(split.vapor.n)
        state[liquid_total_id("S3")] = sum(split.liquid.n)
        state[total_flow_id("S4")] = sum(streams["S4"].n)
        state[total_flow_id("S5")] = sum(streams["S5"].n)
        del recycle
        return state

    # -- the compiled boundary ---------------------------------------------------------------

    def _raw_rows(
        self, state: Mapping[str, float], context: EvaluationContext | None = None
    ) -> dict[str, float]:
        result = self.compiled.residual(
            np.array(state_vector(self.spec, state)), context or self.context
        )
        if result.status != "ok" or result.values is None:
            raise ValueError(f"the lifted residual returned {result.status}: {result.message}")
        return dict(zip(result.equation_ids, result.values, strict=True))

    def _raw_jacobian(
        self, state: Mapping[str, float], context: EvaluationContext | None = None
    ) -> JacobianResult:
        result = self.compiled.jacobian(
            np.array(state_vector(self.spec, state)), context or self.context
        )
        if result.status != "ok":
            raise ValueError(f"the lifted Jacobian returned {result.status}")
        return result

    # -- R(t) ---------------------------------------------------------------------------------

    def residual(
        self, t: npt.NDArray[np.float64], flowsheet: Syn001Flowsheet | None = None
    ) -> Evaluation:
        """`R(t) = G(t) − t`, or the typed reason the traversal produced none."""
        traversal = (flowsheet or self.flowsheet).traverse(self.tear_state(t))
        if traversal.status != "ok" or traversal.recycle_residual is None:
            return Evaluation(
                status=traversal.status,
                message=traversal.message,
            )
        return Evaluation(
            status="ok",
            values=tuple(traversal.recycle_residual),
            # §9.1: the attempt signature covers the phase selections the *residual* depends on,
            # which for this tear is exactly the flash. Reporting every stream's signature here
            # would freeze the heater outlet's regime too, and §9.1 measures the cost of that:
            # the nominal case's one-step landing on t* is then rejected as a phase change,
            # because S3 flips from TWO_PHASE at 0.5 t* to LIQUID at t*.
            signature=flash_signature(
                traversal.phase_signatures.get("S4"), traversal.phase_signatures.get("S5")
            ),
        )

    # -- dR/dt --------------------------------------------------------------------------------

    def jacobian(
        self,
        t: npt.NDArray[np.float64],
        context: EvaluationContext | None = None,
        flowsheet: Syn001Flowsheet | None = None,
    ) -> sp.csc_matrix:
        """§3.4's Schur complement, with the mandatory consistency check first."""
        state = self.reconstruct(self.tear_state(t), flowsheet)
        self.last_inner_consistency = self.check_inner_consistency(state, context)
        jacobian = self._raw_jacobian(state, context)

        row_index = {name: index for index, name in enumerate(jacobian.row_ids)}
        column_index = {name: index for index, name in enumerate(jacobian.col_ids)}
        rows, columns, data = [], [], []
        for column in range(len(jacobian.col_ids)):
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
                rows.append(jacobian.indices[offset])
                columns.append(column)
                data.append(jacobian.data[offset])
        scaled_entries = self.scaling.scale_jacobian_entries(
            data,
            rows,
            columns,
            jacobian.row_ids,
            jacobian.col_ids,
        )
        full = sp.csr_matrix(
            (scaled_entries, (rows, columns)),
            shape=(len(jacobian.row_ids), len(jacobian.col_ids)),
        ).toarray()

        rho = [row_index[name] for name in self.partition.tear_rows]
        phi = [row_index[name] for name in self.partition.inner_rows]
        tear = [column_index[name] for name in self.partition.tear_variables]
        inner = [column_index[name] for name in self.partition.inner_variables]

        j_rho_t = full[np.ix_(rho, tear)]
        j_rho_u = full[np.ix_(rho, inner)]
        j_phi_t = full[np.ix_(phi, tear)]
        j_phi_u = sp.csc_matrix(full[np.ix_(phi, inner)])

        # §3.4: three solves against **one** factorization (ADR 0004 Consequences), which is
        # what the multi-column right-hand side buys. Solving column by column factorized the
        # 44x44 block three times per Jacobian and discarded all three records, so ADR 0004 D3's
        # "recorded on the SolveEvent" held for the 3x3 reduced system and for nothing else.
        inner_sensitivity, inner_record = solve_linear(j_phi_u, j_phi_t)
        self.last_inner_solve = inner_record

        # §3.1's row sign: the tear rows evaluate `−R`, so the derivative of `R` is the negation.
        scaled_derivative = -(j_rho_t - j_rho_u @ inner_sensitivity)

        row_scales = self.scaling.row_vector(self.partition.tear_rows)
        column_scales = self.scaling.column_vector(self.partition.tear_variables)
        unscaled = scaled_derivative * row_scales[:, None] / column_scales[None, :]
        return sp.csc_matrix(unscaled)

    def check_inner_consistency(
        self, state: Mapping[str, float], context: EvaluationContext | None = None
    ) -> float:
        """§3.4: every non-tear row must be satisfied where the derivative is taken.

        **Every** non-tear row, not only the retained ones. An eliminated row is not a discarded
        row (§7.3): it stays assembled precisely so that the claim made when it was removed can
        be checked at every iterate, and checking only the 44 retained rows left the two
        eliminated ones asserted once, at the initial guess, and never again.

        What is checked for an eliminated row is the **certificate identity**, not the row. The
        certificate says the row equals a signed combination of retained rows plus a constant
        `m_e` measured at elimination time, so the quantity that must vanish is `F_e − m_e` and
        not `F_e`. The difference matters exactly where it is meant to: §7.2 tolerates a
        mismatch up to 1e-2 Pa, which is 1e-7 scaled and five decades above `eta_inner`, so
        requiring `F_e` itself to vanish would make any tolerated nonzero mismatch a spurious
        `INNER_SOLVE_INCONSISTENT`. At the registered conflict state, where `m_e` is 50 000 Pa,
        the identity still holds and the conflict is reported by the eliminator — which is
        where a specification conflict belongs — rather than by the derivative.
        """
        values = self._raw_rows(state, context)
        worst_row, worst = "", 0.0
        for name in self.partition.inner_rows:
            scaled = abs(values[name]) / self.scaling.row[name]
            if scaled > worst:
                worst_row, worst = name, scaled
        for row in self.partition.elimination.eliminated:
            scaled = abs(values[row.row_id] - row.constant_mismatch) / self.scaling.row[row.row_id]
            if scaled > worst:
                worst_row, worst = f"{row.row_id} (certificate identity)", scaled
        if worst > self.eta_inner:
            raise InnerSolveInconsistentError(worst, worst_row)
        return worst

    @property
    def checked_rows(self) -> tuple[str, ...]:
        """Every row the consistency check covers: the retained inner rows and the eliminated."""
        return self.partition.inner_rows + tuple(
            row.row_id for row in self.partition.elimination.eliminated
        )

    # -- the test oracle ------------------------------------------------------------------------

    def finite_difference_jacobian(
        self, t: npt.NDArray[np.float64], step: float = FD_STEP
    ) -> npt.NDArray[np.float64]:
        """Central differences of the traversal. A **test oracle**, never a path (plan §4.2).

        Unusable at `t*`: the stencil leaves the mixer's domain on two of three columns there,
        because `t*` is the saturated boundary. It raises rather than returning a one-sided
        substitute, because a mixed stencil would be a different approximation wearing this
        one's error bound.
        """
        columns = []
        for index in range(len(t)):
            plus, minus = np.array(t, dtype=float), np.array(t, dtype=float)
            plus[index] += step
            minus[index] -= step
            up, down = self.residual(plus), self.residual(minus)
            if up.status != "ok" or down.status != "ok":
                raise ValueError(
                    f"the central stencil left the evaluable domain on column {index}: "
                    f"{up.status}/{down.status}. At t* this is expected — t* is the mixer's "
                    "domain boundary — and is why the finite difference is an oracle away from "
                    "the solution and not a derivative path"
                )
            assert up.values is not None and down.values is not None
            columns.append((np.asarray(up.values) - np.asarray(down.values)) / (2.0 * step))
        return np.column_stack(columns)

    # -- the Newton's view ----------------------------------------------------------------------

    def as_newton_problem(self, attempt: AttemptContext | None = None) -> Problem:
        """The three-variable problem `solve_newton` runs on: `t ≥ 0`, registered tolerances.

        With an `attempt`, every residual call traverses under the attempt's flowsheet context and
        every compiled call takes the attempt's evaluation context (T03 §4.2, A03): an attempt's
        calls are its own, told apart from another attempt's by object identity.
        """
        from openflowsheet.models.syn001 import FLOW_TOLERANCE

        residual: Callable[[npt.NDArray[np.float64]], Evaluation] = self.residual
        jacobian: Callable[[npt.NDArray[np.float64]], sp.csc_matrix] = self.jacobian
        if attempt is not None:
            flowsheet = replace(self.flowsheet, context=attempt.flowsheet_context)
            context = attempt.evaluation_context

            def attempt_residual(t: npt.NDArray[np.float64]) -> Evaluation:
                return self.residual(t, flowsheet)

            def attempt_jacobian(t: npt.NDArray[np.float64]) -> sp.csc_matrix:
                return self.jacobian(t, context, flowsheet)

            residual, jacobian = attempt_residual, attempt_jacobian

        return Problem(
            variable_ids=self.partition.tear_variables,
            row_ids=self.partition.tear_rows,
            residual=residual,
            jacobian=jacobian,
            scaling=Scaling(
                column={name: self.scaling.column[name] for name in self.partition.tear_variables},
                row={name: self.scaling.row[name] for name in self.partition.tear_rows},
            ),
            row_tolerance=dict.fromkeys(self.partition.tear_rows, FLOW_TOLERANCE),
            jacobian_evidence=lambda: (
                () if self.last_inner_solve is None else (self.last_inner_solve,)
            ),
            jacobian_diagnostics=lambda: {
                "eta": self.last_inner_consistency,
                "eta_max": self.eta_inner,
                "rows_checked": len(self.checked_rows),
            },
            # ADR 0001 D3.5: a tear component is a flow, bounded below by 0, and a tear vector
            # at exactly 0 is a valid iterate. No log transform (D3.6).
            lower_bounds=dict.fromkeys(self.partition.tear_variables, 0.0),
        )


def build_plan(tear: Syn001TearProblem, policy: SolvePolicy) -> SolvePlan:
    """§12.2: everything decided before a residual is evaluated.

    Built from the partition, the eliminations and the registered scales — no iterate anywhere,
    which is what makes it replayable and what requirement **D06** means by "scales precede
    initialization acceptance".
    """
    metadata = tear.compiled.metadata
    partition = tear.partition
    return SolvePlan(
        plan_id=f"SYN-001-{metadata.model_version.split('@')[0]}-{policy.policy_id}",
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        policy_id=policy.policy_id,
        tear_variable_ids=partition.tear_variables,
        tear_row_ids=partition.tear_rows,
        inner_variable_ids=partition.inner_variables,
        inner_row_ids=partition.inner_rows,
        eliminated_rows=tuple(
            EliminatedRowRecord(
                row_id=row.row_id,
                equals=row.equals,
                constant_mismatch=row.constant_mismatch,
                tolerance=row.tolerance,
            )
            for row in partition.elimination.eliminated
        ),
        column_scales=dict(tear.scaling.column),
        row_scales=dict(tear.scaling.row),
        scale_provenance=tear.scaling.provenance,
        bounds=dict.fromkeys(partition.tear_variables, (0.0, None)),
        signature_units=SIGNATURE_UNITS,
        initializer_chain=(INITIALIZER_ID,),
        estimates={
            "inner_dimension": len(partition.inner_variables),
            "jacobian_nnz": int(
                tear.compiled.jacobian(
                    np.array(
                        state_vector(tear.spec, tear.reconstruct(tear.flowsheet.initial_recycle()))
                    ),
                    tear.context,
                ).nnz
            ),
        },
    )


def solve_tear(
    flowsheet: Syn001Flowsheet,
    *,
    initial_recycle: Sequence[float] | None = None,
    policy: SolvePolicy | None = None,
    trace: Trace | None = None,
) -> tuple[SolveResult, Trace]:
    """Solve the SYN-001 flowsheet: bounded attempts over the three-variable tear.

    This is the whole of gate **G00** in one call — "three-component ideal process with all
    named v0.0 units and one numerical tear". `initial_recycle` defaults to derivation §9's
    registered initializer `t⁰ = G(0)`; §10's full candidate chain, which *checks* a supplied
    guess and falls through, is the orchestrator's initialization step and is not yet wired.

    §11.2's property-call budget is enforced here, by wrapping the flowsheet's provider in a
    guard and then in K02's exact cache. Wrapping is invisible to identity — both pass
    `describe()` through unchanged, so the flowsheet label and `model_version` name the same
    provider they would have named — and it is what makes the counters on every event real
    rather than structurally zero.

    SYN-001's only: a revision-built flowsheet is solved as one region (T05 §2.3, register R-045),
    and anything else is a `TypeError`, never a tear guessed at.
    """
    if not isinstance(flowsheet, Syn001Flowsheet):
        raise TypeError("syn001_only(solve_tear)")
    resolved_policy = policy or SolvePolicy(
        policy_id="SYN-001-K03", residual_tolerances={}, scales={}
    )
    guard = BudgetedProvider(flowsheet.provider, resolved_policy.max_property_calls)
    cache = ExactPropertyCache(guard)
    flowsheet = replace(flowsheet, provider=cache)

    def sample() -> dict[str, int]:
        # `property_calls` is the **guard's** count and not the cache's, because the cache
        # increments its `provider_calls` before making the call and so counts the one the
        # guard refuses: at a cap of 20 that reads 21, and A15 registers exactly 20. The guard
        # counts calls it actually let through, which is what the budget is on.
        return {
            "property_calls": guard.calls,
            "cache_hits": cache.counters.cache_hits,
            "requested_evaluations": cache.counters.cache_hits + cache.counters.cache_misses,
        }

    resolved_trace = trace if trace is not None else Trace(property_sampler=sample)
    plan: SolvePlan | None = None
    start: tuple[float, ...] = ()

    try:
        # Building the partition and the plan costs real provider calls, so it is inside the
        # budget. A cap small enough to be spent here leaves a trace of exactly one event —
        # `solve_closed`, `BUDGET_EXHAUSTED` — and `plan=None`, which is the honest report: no
        # plan was built, and a `plan_built` event would say one was.
        tear = Syn001TearProblem(flowsheet)

        # D06 and §12.2: the plan is built, and its scales fixed, *before* the initializer
        # chain runs. `plan_built` is therefore the first event of every trace that has one,
        # and A05 asserts it precedes every initializer event.
        plan = build_plan(tear, resolved_policy)
        resolved_trace.record(
            kind="plan_built",
            attempt=0,
            iteration=0,
            signature=(),
            state_sha256="",
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=Counters(),
            message=plan.plan_id,
        )
        start = flowsheet.initial_recycle().n if initial_recycle is None else tuple(initial_recycle)

        def signature_of(t: npt.NDArray[np.float64]) -> object:
            traversal = flowsheet.traverse(tear.tear_state(t))
            if traversal.status != "ok":
                return None
            return flash_signature(
                traversal.phase_signatures.get("S4"), traversal.phase_signatures.get("S5")
            )

        result = solve_with_attempts(
            problem_for=tear.as_newton_problem,
            x0=start,
            signature_of=signature_of,  # type: ignore[arg-type]
            policy=resolved_policy,
            trace=resolved_trace,
            evaluation_context=tear.context,
            flowsheet_context=flowsheet.context,
            column_scales=dict(tear.scaling.column),
            row_scales=dict(tear.scaling.row),
            variable_ids=tear.partition.tear_variables,
            # T02 §4.2: every SYN-001 unit declares exact residual derivatives, so `auto` is
            # `newton_tear` here; an explicit `anderson` is honoured (the registered SYN-001 ×
            # Anderson cases, A04–A06). `eo` is a plan-level choice and never reaches a tear.
            method="anderson" if resolved_policy.recycle.method == "anderson" else "newton_tear",
            # ADR 0005 D5: the tear path's EO block is the plan's inner block; the compiled
            # problem is regime-free (K03 A33), so the pattern is the same for every attempt.
            jacobian_pattern=jacobian_pattern(
                tear.compiled.structural_pattern(), plan.inner_row_ids, plan.inner_variable_ids
            ),
            initializer_source=(INITIALIZER_ID if initial_recycle is None else "user_guess"),
        )
    except BudgetExhaustedError as exhausted:
        # §11.2: the orchestrator converts the typed refusal to the outcome. It closes the trace
        # rather than propagating, because a solve that ended without a `solve_closed` event is
        # a trace a reader cannot tell from one that is still running.
        counters = Counters(**sample())
        resolved_trace.record(
            kind="solve_closed",
            attempt=0,
            iteration=0,
            signature=(),
            state_sha256="",
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=counters,
            outcome="BUDGET_EXHAUSTED",
            message=str(exhausted),
        )
        return (
            SolveResult(
                outcome="BUDGET_EXHAUSTED",
                x=np.array(start, dtype=np.float64),
                residual_inf=float("nan"),
                attempts=0,
                iterations=0,
                counters=counters,
                checkpoint=None,
                signatures=(),
                message=str(exhausted),
                plan=plan,
            ),
            resolved_trace,
        )
    except InitializerFailedError as failed:
        # T06 spec §8.7 (ADR 0014 D10, R-078): the registered initializer is evaluated while the
        # partition and the plan are built, so a feed its once-through pass cannot take ends the
        # solve before a plan exists. Typed, as the revision path already types the same
        # condition, and closed as `BUDGET_EXHAUSTED` above closes: one `solve_closed` event and
        # `plan=None` — a `plan_built` event would say a plan was built. Exactly this subclass:
        # any other `SpecificationError` still escapes.
        counters = Counters(**sample())
        message = f"initializer_failed({INITIALIZER_ID}): {failed.status}: {failed.first_line}"
        resolved_trace.record(
            kind="solve_closed",
            attempt=0,
            iteration=0,
            signature=(),
            state_sha256="",
            residual_inf_unscaled=float("nan"),
            merit=float("nan"),
            counters=counters,
            outcome="INITIALIZATION_FAILED",
            message=message,
        )
        return (
            SolveResult(
                outcome="INITIALIZATION_FAILED",
                x=np.array(start, dtype=np.float64),
                residual_inf=float("nan"),
                attempts=0,
                iterations=0,
                counters=counters,
                checkpoint=None,
                signatures=(),
                message=message,
                plan=plan,
            ),
            resolved_trace,
        )
    final_state: dict[str, float] | None = None
    checkpoint = result.checkpoint
    if result.outcome == "CONVERGED":
        # A01, and the Fable review of K03's finding S2. The certificate is about the full
        # 47-vector, and `Checkpoint.state_sha256` covers only the three the solver iterated
        # on (ADR 0008 D2.1's coverage rule). The hash recorded here is the compiled
        # residual's own, so the verifier can assert it against its own evaluation rather
        # than trusting a digest computed by a different route.
        final_state = tear.reconstruct(tear.tear_state(result.x))
        evaluation = tear.compiled.residual(
            np.array(state_vector(tear.spec, final_state)), tear.context
        )
        if evaluation.status != "ok":
            raise ValueError(f"the converged state could not be re-evaluated: {evaluation.status}")
        if checkpoint is not None:
            checkpoint = replace(checkpoint, full_state_sha256=evaluation.state_sha256)
        # T03 §8.2: the fingerprint identifies the reconstructed full state where one exists.
        from openflowsheet.orchestrator.region import syn001_lifted_splits

        if result.root_fingerprint is not None:
            result = replace(
                result,
                root_fingerprint=root_fingerprint(
                    model_version=tear.compiled.metadata.model_version,
                    constants_sha256=tear.compiled.metadata.constants_sha256,
                    variable_ids=tear.spec.variable_ids,
                    # Review M1: from the reconstructed state, for every lifted split — the
                    # tear signature holds the flash alone, by K03's measured choice, but the
                    # root's branch is the state's.
                    branch_found=branch_found(
                        syn001_lifted_splits(flowsheet.components), final_state
                    ),
                    full_state_sha256=evaluation.state_sha256,
                ),
            )

    return replace(
        result,
        plan=plan,
        checkpoint=checkpoint,
        final_state=final_state,
        counters=Counters(
            **{**{f.name: getattr(result.counters, f.name) for f in fields(Counters)}, **sample()}
        ),
    ), resolved_trace
