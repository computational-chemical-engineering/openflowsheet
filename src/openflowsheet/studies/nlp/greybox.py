"""The general NLP gray-box adapter: `CompiledProblem`'s parametric twin as a PyNumero
`ExternalGreyBoxModel`, solved by the audited cyipopt (M03 spec §8; ADR 0032 D1-D5; WO-8).

This is the one `openflowsheet` module that imports Pyomo and cyipopt. It exists only with the
optional `nlp` extra in the audited environment of `docs/m03-ipopt-audit.md` (built by
`scripts/build-m03-ipopt-env.sh`); `closure.optimize` imports it only after
`optimization_readiness` returned `READY_FOR_OPTIMIZATION`, and the default gate never imports it
(gate G6).

**The model** (D1, spec §8.2). The gray box's inputs are the primal `z = (x, d)` of
`FullSpaceNlp` — every state variable, then the decisions — and its equality constraints are the
kept rows `F_K(x; d)`, evaluated by the parametric twin with the decisions symbolic; its Jacobian is
the twin's exact `[F_x,K  F_p,K]`. Pyomo holds only the declared objective and inequality
constraints (linear or quadratic in named variables, never a penalty term), the bounds and the user
scaling. The initial point is the verified simulation state at the start.

**The Hessian** (D2, spec §8.3) is absent: the gray box implements no Hessian method, Ipopt is
configured with `hessian_approximation = limited-memory` (history 6) explicitly, and an exact
Hessian request never reaches this module (`optimization_readiness` refuses it
`HESSIAN_UNAVAILABLE`; `optimize` here refuses it again before any solver call).

**Evaluation errors** (spec §8.2, §14 Q-F4). A property block's domain or block error inside the
twin (`TwinEvaluationError`) is raised as PyNumero's `PyNumeroEvaluationError`, which
`CyIpoptNLP` (Pyomo 6.10.1, cyipopt 1.7.0) turns into `cyipopt.CyIpoptEvaluationError`, which
cyipopt reports to Ipopt as a failed evaluation: at a trial point Ipopt rejects it and cuts the
step. Never a NaN, never a clipped value. Each start records how many evaluations failed.

**The verdict** (D3, spec §8.5 Amendment 1). Ipopt's integer `ApplicationReturnStatus` is read
from `info["status"]`. V1-V6 run on the decisions every start returns, whatever Ipopt's status;
`closure.classify_starts` classifies each start and gives the report's status. This module computes
no status of its own.

**The environment** ([A10], audit §9). Before any solve, `PyNumero`'s ASL library must be the
audited build (its SHA-256 equals `closure.AUDITED_PYNUMERO_ASL_SHA256`; Pyomo otherwise finds an
unaudited `~/.pyomo/lib` build unless `PYOMO_CONFIG_DIR` points at the environment), and no object
of the CasADi wheel's METIS closure and no HSL object may be mapped. Otherwise the report is
`UNSUPPORTED(NLP_SOLVER_UNAVAILABLE)` and nothing is solved.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib.util
import logging
import math
import re
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import cyipopt
import numpy as np
import numpy.typing as npt
import pyomo.environ as pyo
import scipy.sparse as sp
from pyomo.contrib.pynumero.asl import AmplInterface
from pyomo.contrib.pynumero.exceptions import PyNumeroEvaluationError
from pyomo.contrib.pynumero.interfaces.cyipopt_interface import CyIpoptNLP
from pyomo.contrib.pynumero.interfaces.external_grey_box import (
    ExternalGreyBoxBlock,
    ExternalGreyBoxModel,
)
from pyomo.contrib.pynumero.interfaces.pyomo_grey_box_nlp import PyomoNLPWithGreyBoxBlocks

from openflowsheet.compile.casadi_backend import TwinEvaluationError
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.studies.nlp.closure import (
    AUDIT_DOCUMENT,
    AUDIT_GATE,
    AUDIT_VERDICT,
    AUDITED_PYNUMERO_ASL_SHA256,
    OptimizationReport,
    Readiness,
    ReadinessReason,
    StartEvidence,
    StartReadiness,
    classify_starts,
    formulation_record,
    model_record,
    report_limits,
    solver_record,
    unsupported_report,
)
from openflowsheet.studies.nlp.formulation import (
    HESSIAN_APPROXIMATION,
    HESSIAN_POLICY,
    IPOPT_OPTIONS,
    FullSpaceNlp,
    NlpFormulation,
    QuadraticExpression,
)
from openflowsheet.studies.nlp.verification import CandidateVerification, verify_candidate
from openflowsheet.studies.syn001 import with_pinned

#: Ipopt's integer-valued options among spec §8.4's; every other numeric option is a Number.
#: cyipopt picks Ipopt's option type from the Python type, so the recorded values (verbatim, spec
#: §8.4) are passed with their Ipopt type: `bound_relax_factor = 0` is the Number 0.0.
IPOPT_INTEGER_OPTIONS: Final = frozenset(
    {"limited_memory_max_history", "acceptable_iter", "max_iter", "print_level"}
)
#: Spec §8.5: verified decisions more than this apart (scaled, ∞-norm) are distinct solutions.
TAU_DISTINCT: Final = 1e-6
#: Spec §9 G2: what a mapped object under the CasADi package directory may not name.
CASADI_METIS_CLOSURE: Final = re.compile(r"ipopt|mumps|metis|coinmumps|coinmetis", re.IGNORECASE)
#: Spec §9 G4: no HSL object.
HSL_OBJECT: Final = re.compile(r"hsl", re.IGNORECASE)


# -- the gray box ---------------------------------------------------------------------------------


class FullSpaceGreyBox(ExternalGreyBoxModel):  # type: ignore[misc]
    """`FullSpaceNlp`'s equality rows and their exact Jacobian as PyNumero's gray box.

    Inputs `primal_ids` (the state, then the decisions); equality constraints `equality_ids`; no
    outputs, no objective, no Hessian. A twin evaluation error is re-raised as
    `PyNumeroEvaluationError` and counted; any other exception propagates."""

    def __init__(self, nlp: FullSpaceNlp) -> None:
        self.nlp = nlp
        self._z = nlp.initial_point()
        self._pattern: tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]] | None = None
        self.evaluation_errors: list[str] = []

    def input_names(self) -> list[str]:
        return list(self.nlp.primal_ids)

    def equality_constraint_names(self) -> list[str]:
        return list(self.nlp.equality_ids)

    def output_names(self) -> list[str]:
        return []

    def set_input_values(self, input_values: npt.NDArray[np.float64]) -> None:
        self._z = np.array(input_values, dtype=np.float64)

    def get_equality_constraint_scaling_factors(self) -> npt.NDArray[np.float64]:
        return self.nlp.equality_scaling()

    def evaluate_equality_constraints(self) -> npt.NDArray[np.float64]:
        try:
            return self.nlp.equality_residual(self._z)
        except TwinEvaluationError as error:
            raise self._failed("residual", error) from error

    def evaluate_jacobian_equality_constraints(self) -> sp.coo_matrix:
        try:
            jacobian = self.nlp.equality_jacobian(self._z).tocoo()
        except TwinEvaluationError as error:
            raise self._failed("jacobian", error) from error
        # Ipopt is handed the structure once; every later Jacobian must fill exactly that pattern.
        # The twin's CSC is structural and canonical (`_csc_from_triplets`), so this holds by
        # construction, and a violation is a bug, not an evaluation error.
        pattern = (jacobian.row.astype(np.int64), jacobian.col.astype(np.int64))
        if self._pattern is None:
            self._pattern = pattern
        elif not (
            np.array_equal(pattern[0], self._pattern[0])
            and np.array_equal(pattern[1], self._pattern[1])
        ):
            raise RuntimeError("the twin's Jacobian changed its sparsity pattern")
        return jacobian

    def _failed(self, what: str, error: TwinEvaluationError) -> PyNumeroEvaluationError:
        self.evaluation_errors.append(f"{what}: {error}")
        return PyNumeroEvaluationError(f"twin {what} evaluation failed: {error}")


def _expression(expression: QuadraticExpression, variables: Any) -> Any:
    """A declared linear or quadratic expression over the gray box's input variables."""
    terms: list[Any] = [expression.constant]
    terms.extend(coefficient * variables[name] for name, coefficient in expression.linear.items())
    terms.extend(
        coefficient * variables[first] * variables[second]
        for (first, second), coefficient in expression.quadratic.items()
    )
    return sum(terms[1:], terms[0])


def build_model(nlp: FullSpaceNlp, box: FullSpaceGreyBox) -> Any:
    """The Pyomo model of spec §8.2: the gray box, its bounds and initial point, the declared
    objective and inequality constraints, and the user scaling."""
    formulation = nlp.formulation
    model = pyo.ConcreteModel(name=formulation.problem_id)
    model.greybox = ExternalGreyBoxBlock()
    model.greybox.set_external_model(box)
    inputs = model.greybox.inputs
    lower, upper = nlp.bound_arrays()
    for name, value, low, high in zip(
        nlp.primal_ids, nlp.initial_point(), lower, upper, strict=True
    ):
        inputs[name].value = float(value)
        inputs[name].setlb(None if math.isinf(low) else float(low))
        inputs[name].setub(None if math.isinf(high) else float(high))
    model.objective = pyo.Objective(
        expr=_expression(formulation.objective, inputs), sense=pyo.minimize
    )
    ids = [constraint.constraint_id for constraint in formulation.constraints]
    by_id = {constraint.constraint_id: constraint for constraint in formulation.constraints}
    model.inequalities = pyo.Constraint(
        ids,
        rule=lambda _, name: (
            by_id[name].lower,
            _expression(by_id[name].expression, inputs),
            by_id[name].upper,
        ),
    )
    model.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    for name, factor in zip(nlp.primal_ids, nlp.primal_scaling(), strict=True):
        model.scaling_factor[inputs[name]] = float(factor)
    model.scaling_factor[model.objective] = 1.0
    for name in ids:
        model.scaling_factor[model.inequalities[name]] = 1.0
    return model


class _UnexportedScaling(logging.Filter):
    """Drops the NL writer's note that the gray box's input scaling is not in the NL file: the
    NL file carries only the Pyomo part, and `PyomoNLPWithGreyBoxBlocks` reads the inputs' scaling
    from the same suffix itself."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "not exported as part of the NL file" not in record.getMessage()


@contextlib.contextmanager
def _quiet_unexported_scaling() -> Iterator[None]:
    logger = logging.getLogger("pyomo.repn.plugins.nl_writer")
    note = _UnexportedScaling()
    logger.addFilter(note)
    try:
        yield
    finally:
        logger.removeFilter(note)


# -- one start ------------------------------------------------------------------------------------


@dataclass
class _Iterations:
    """Ipopt's intermediate callback: the last iteration's count and unscaled violations."""

    count: int | None = None
    final: dict[str, float] | None = None

    def __call__(
        self,
        nlp: Any,
        problem: Any,
        alg_mod: int,
        iter_count: int,
        obj_value: float,
        inf_pr: float,
        inf_du: float,
        mu: float,
        d_norm: float,
        regularization_size: float,
        alpha_du: float,
        alpha_pr: float,
        ls_trials: int,
    ) -> bool:
        self.count = int(iter_count)
        violations = problem.get_current_violations(scaled=False)
        if violations is not None:
            self.final = {
                "primal_infeasibility": max(
                    _norm(violations[key])
                    for key in ("g_violation", "x_L_violation", "x_U_violation")
                ),
                "dual_infeasibility": _norm(violations["grad_lag_x"]),
                "complementarity": max(
                    _norm(violations[key]) for key in ("compl_x_L", "compl_x_U", "compl_g")
                ),
            }
        return True


def _norm(values: Any) -> float:
    array = np.asarray(values, dtype=np.float64)
    return float(np.max(np.abs(array))) if array.size else 0.0


@dataclass
class StartRun:
    """One start: what Ipopt returned and what the re-solved simulation says about it."""

    index: int
    start: tuple[float, ...]
    ipopt_status: int | None = None
    ipopt_message: str | None = None
    iterations: int | None = None
    evaluations: dict[str, int] = field(
        default_factory=lambda: {
            "residual_calls": 0,
            "jacobian_calls": 0,
            "property_calls": 0,
            "evaluation_errors": 0,
        }
    )
    wall_time_s: float | None = None
    final_primal: npt.NDArray[np.float64] | None = None
    final_decisions: tuple[float, ...] | None = None
    ipopt_final: dict[str, float] | None = None
    verification: CandidateVerification | None = None
    detail: str | None = None

    def note(self, text: str) -> None:
        """Add to `detail`, which the start's report reason carries (spec §8.5)."""
        self.detail = f"{self.detail}; {text}" if self.detail else text

    def evidence(self) -> StartEvidence:
        checks = (
            {item.check: item.outcome for item in self.verification.checks}
            if self.verification is not None
            else {}
        )
        return StartEvidence(self.ipopt_status, checks, self.detail)

    def record(self, formulation: NlpFormulation) -> dict[str, Any]:
        """Spec §8.6's start record (`optimization-report#/$defs/start`, without its
        classification, which `StatusVerdict.start_records` adds)."""
        return {
            "start": formulation.decision_values(self.start),
            "ipopt_status": self.ipopt_status,
            "ipopt_message": self.ipopt_message,
            "iterations": self.iterations,
            "evaluations": dict(self.evaluations),
            "wall_time_s": self.wall_time_s,
            "final_decisions": (
                formulation.decision_values(self.final_decisions)
                if self.final_decisions is not None
                else None
            ),
            "ipopt_final": dict(self.ipopt_final) if self.ipopt_final is not None else None,
            "checks": (
                [item.as_document() for item in self.verification.checks]
                if self.verification is not None
                else []
            ),
        }


def _typed_options() -> dict[str, int | float | str]:
    typed: dict[str, int | float | str] = {}
    for name, value in IPOPT_OPTIONS.items():
        if isinstance(value, str):
            typed[name] = value
        elif name in IPOPT_INTEGER_OPTIONS:
            typed[name] = int(value)
        else:
            typed[name] = float(value)
    return typed


def solve_start(
    flowsheet: Syn001Flowsheet,
    formulation: NlpFormulation,
    readiness: StartReadiness,
    index: int,
) -> StartRun:
    """Ipopt from one verified start, then V1-V6 on the decisions it returned (spec §8.5)."""
    run = StartRun(index, tuple(readiness.start))
    if readiness.state is None or readiness.regimes is None:
        raise ValueError(f"start {index} is not a verified start; readiness should have refused")
    nlp: FullSpaceNlp | None = None
    box: FullSpaceGreyBox | None = None
    try:
        sheet = with_pinned(flowsheet, formulation.decision_values(readiness.start))
        nlp = FullSpaceNlp(sheet, formulation, readiness.state, readiness.start)
        box = FullSpaceGreyBox(nlp)
        model = build_model(nlp, box)
        with _quiet_unexported_scaling():
            pynumero = PyomoNLPWithGreyBoxBlocks(model)
        iterations = _Iterations()
        # Explicit, not Pyomo's version-dependent default: an evaluation error is reported to
        # Ipopt (which rejects a trial point), never re-raised to end the run (spec §14 Q-F4).
        problem = CyIpoptNLP(
            pynumero, intermediate_callback=iterations, halt_on_evaluation_error=False
        )
        objective_scaling, primal_scaling, constraint_scaling = problem.scaling_factors()
        problem.set_problem_scaling(
            1.0 if objective_scaling is None else objective_scaling,
            np.ones(pynumero.n_primals()) if primal_scaling is None else primal_scaling,
            np.ones(pynumero.n_constraints()) if constraint_scaling is None else constraint_scaling,
        )
        for name, value in _typed_options().items():
            problem.add_option(name, value)
        began = time.perf_counter()
        try:
            primal, info = problem.solve(problem.x_init())
        finally:
            run.wall_time_s = time.perf_counter() - began
        run.ipopt_status = int(info["status"])
        message = info["status_msg"]
        run.ipopt_message = message.decode() if isinstance(message, bytes) else str(message)
        run.iterations = iterations.count if iterations.count is not None else 0
        run.ipopt_final = iterations.final
        run.final_primal = _by_primal_id(model, pynumero, nlp, np.asarray(primal))
    except Exception as error:  # noqa: BLE001 - spec §8.5 rule 4: an adapter exception is a result
        run.note(f"adapter exception {type(error).__name__}: {_first_line(error)}")
    finally:
        if nlp is not None and box is not None:
            run.evaluations = _evaluations(nlp, box)
    if box is not None and box.evaluation_errors:
        run.note(
            f"{len(box.evaluation_errors)} twin evaluation error(s) reported to Ipopt; first: "
            f"{box.evaluation_errors[0][:300]}"
        )
    if nlp is None or run.final_primal is None:
        return run
    if not np.all(np.isfinite(run.final_primal)):
        run.note("Ipopt returned a non-finite primal; no decisions to verify")
        return run
    x, decisions = nlp.split(run.final_primal)
    run.final_decisions = tuple(decisions[name] for name in formulation.decision_ids)
    optimizer_state = dict(zip(nlp.variable_ids, (float(value) for value in x), strict=True))
    try:
        run.verification = verify_candidate(
            flowsheet,
            formulation,
            run.final_decisions,
            regimes=readiness.regimes,
            optimizer_state=optimizer_state,
        )
    except Exception as error:  # noqa: BLE001 - recorded; the start then has no V outcomes
        run.note(f"verification raised {type(error).__name__}: {_first_line(error)}")
    return run


def _first_line(error: BaseException) -> str:
    return (str(error).splitlines() or [""])[0][:300]


def _by_primal_id(
    model: Any, pynumero: Any, nlp: FullSpaceNlp, primal: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Ipopt's primal, which PyNumero orders its own way, in `nlp.primal_ids` order."""
    position = {name: index for index, name in enumerate(pynumero.primals_names())}
    inputs = model.greybox.inputs
    return np.array(
        [primal[position[inputs[name].getname(fully_qualified=True)]] for name in nlp.primal_ids],
        dtype=np.float64,
    )


def _evaluations(nlp: FullSpaceNlp, box: FullSpaceGreyBox) -> dict[str, int]:
    """Spec §8.6's counters since the start's twin was built: full-space residuals and
    Jacobians, property-block callbacks (value and Jacobian), and failed evaluations."""
    property_calls = sum(
        counts["value_calls"] + counts["jacobian_calls"]
        for counts in nlp.twin.block_calls().values()
    )
    return {
        "residual_calls": nlp.counters["residual_calls"],
        "jacobian_calls": nlp.counters["jacobian_calls"],
        "property_calls": property_calls,
        "evaluation_errors": len(box.evaluation_errors),
    }


# -- the environment ------------------------------------------------------------------------------


def pynumero_asl() -> tuple[str | None, str | None]:
    """The ASL library PyNumero will load, and its SHA-256 (`None` when it finds none)."""
    if not AmplInterface.available():
        return None, None
    path = Path(AmplInterface.libname)
    return str(path), hashlib.sha256(path.read_bytes()).hexdigest()


def forbidden_mapped_objects() -> list[str]:
    """Mapped objects the [A10] audit forbids: any from the CasADi wheel's METIS closure (G2) and
    any HSL object (G4). Read from `/proc/self/maps` (the audited platform is linux x86-64)."""
    # Located, not imported: only the compile backend imports CasADi (ADR 0003 D5.7).
    package = importlib.util.find_spec("casadi")
    if package is None or not package.submodule_search_locations:
        return []
    casadi_directory = Path(package.submodule_search_locations[0]).resolve()
    found = set()
    for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) < 6 or not parts[5].startswith("/"):
            continue
        path = Path(parts[5].removesuffix(" (deleted)"))
        under_casadi = casadi_directory in path.parents
        if (under_casadi and CASADI_METIS_CLOSURE.search(path.name)) or HSL_OBJECT.search(
            path.name
        ):
            found.add(str(path))
    return sorted(found)


def environment_problems() -> list[str]:
    """Why the loaded NLP stack is not the audited one, or `[]` (audit §9 items 1, 2 and 4)."""
    problems = []
    library, digest = pynumero_asl()
    if library is None:
        problems.append("PyNumero finds no libpynumero_ASL")
    elif digest != AUDITED_PYNUMERO_ASL_SHA256:
        problems.append(
            f"PyNumero loads {library} (sha256 {digest}), not the audited build "
            f"{AUDITED_PYNUMERO_ASL_SHA256}; set PYOMO_CONFIG_DIR=<env>/share/pyomo"
        )
    forbidden = forbidden_mapped_objects()
    if forbidden:
        problems.append(f"objects the audit forbids are mapped: {forbidden}")
    return problems


def ipopt_version() -> str:
    return ".".join(str(part) for part in cyipopt.IPOPT_VERSION)


# -- the report -----------------------------------------------------------------------------------


def optimize(
    formulation: NlpFormulation, flowsheet: Syn001Flowsheet, readiness: Readiness
) -> OptimizationReport:
    """Multistart Ipopt over the full-space gray box and the report (spec §8.5-§8.6).

    Called by `closure.optimize` only with a `READY_FOR_OPTIMIZATION` readiness. Each registered
    start is solved, its returned decisions verified (V1-V6) whatever Ipopt's status, and
    `classify_starts` gives each start's classification and the report's status."""
    if readiness.status != "READY_FOR_OPTIMIZATION":
        raise ValueError(f"the adapter needs a ready formulation, not {readiness.status!r}")
    if formulation.hessian != HESSIAN_APPROXIMATION:
        raise ValueError(f"Hessian {formulation.hessian!r}: refused before any solver call")
    solver = dataclasses.replace(
        readiness.solver, versions={**readiness.solver.versions, "ipopt": ipopt_version()}
    )
    problems = environment_problems()
    if problems:
        refused = Readiness(
            status="unsupported",
            reasons=(
                ReadinessReason(
                    "NLP_SOLVER_UNAVAILABLE",
                    "; ".join(problems)
                    + f" — see {AUDIT_DOCUMENT} ({AUDIT_GATE}: {AUDIT_VERDICT})",
                    AUDIT_DOCUMENT,
                ),
            ),
            solver=solver,
            starts=readiness.starts,
        )
        return unsupported_report(formulation, flowsheet, refused)

    runs = [
        solve_start(flowsheet, formulation, start, index)
        for index, start in enumerate(readiness.starts)
    ]
    verdict = classify_starts([run.evidence() for run in runs])
    records = verdict.start_records([run.record(formulation) for run in runs])
    verified = [runs[index] for index in verdict.verified_starts]
    candidate = _candidate(verified)
    return OptimizationReport(
        formulation=formulation_record(formulation, readiness.declared_regimes),
        model=model_record(flowsheet),
        solver=solver_record(solver),
        hessian_policy=dict(HESSIAN_POLICY),
        starts=records,
        candidate=candidate.as_document() if candidate is not None else None,
        distinct_local_solutions=_distinct(formulation, verified),
        status=verdict.status,
        reasons=verdict.reasons,
        claims={
            "global_optimality": False,
            "local_stationarity": verdict.local_stationarity,
            "second_order": (
                candidate.kkt.second_order
                if candidate is not None and candidate.kkt is not None
                else "not_assessed"
            ),
        },
        limits=report_limits(),
    )


def _candidate(verified: Sequence[StartRun]) -> CandidateVerification | None:
    """The verified start with the lowest objective on the re-solved simulation, the first in
    start order on a tie (spec §8.5)."""
    best: CandidateVerification | None = None
    for run in verified:
        assert run.verification is not None and run.verification.objective is not None
        if best is None or run.verification.objective < best.objective:  # type: ignore[operator]
            best = run.verification
    return best


def _distinct(formulation: NlpFormulation, verified: Sequence[StartRun]) -> int:
    """Verified decisions more than `TAU_DISTINCT` apart, scaled, greedy in start order."""
    scales = np.array([decision.scale for decision in formulation.decisions])
    representatives: list[npt.NDArray[np.float64]] = []
    for run in verified:
        assert run.final_decisions is not None
        point = np.array(run.final_decisions) / scales
        if all(np.max(np.abs(point - other)) > TAU_DISTINCT for other in representatives):
            representatives.append(point)
    return len(representatives)
