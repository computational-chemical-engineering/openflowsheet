"""The verifier: run the check set, grade the verdict, issue or withhold a certificate. §8.

The verdict rules are short and the precedence matters. `FAILED` beats everything, because a
required check that *failed* is a statement about the answer; `UNVERIFIED` beats `RELAXED` and
`VERIFIED`, because a check that could not run, or Jacobian evidence that does not hold, is not
the same as a check that passed. `RELAXED` beats `VERIFIED` so that a loosened policy can never
present itself as the registered one.

A `FAILED` verdict on a solve the solver called `CONVERGED` is the whole point of the package,
and it is recorded as `false_success_detected` rather than left for a reader to infer.

**A certificate is about the declaration the solve solved** (T04 §4.8; ADR 0010 D9; R-035). There
are two entry points onto one check-set engine: `verify` for the nominal declaration of a
`Syn001Flowsheet`, and `verify_bound` for a revision that frees a variable and promotes a
specification (the binding and the revision document). Before any check, both compare their
compiled `(model_version, constants_sha256)` with the solve's — read from its root fingerprint and
its `SolvePlan` — and, when the state is the result's own, its hash with the fingerprint's. A
difference is a refusal, never a verdict: judging a solve against another declaration produced a
`FAILED` on a correct root (HOM-01, the guess judged as a specification).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.canonical import canonical_json, document_sha256, state_sha256
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import state_vector
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models.syn001.flowsheet import STREAMS, Syn001Flowsheet
from openflowsheet.numerics.scaling import Scaling
from openflowsheet.orchestrator.rank import AliasElimination, eliminate_alias_rows
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.run.compare import CURRENT_POLICY_ID
from openflowsheet.thermo import PropertyProvider
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.thermo.syn001 import PROVIDER_ID as SYN001_PROVIDER_ID
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import (
    FAILING_CATEGORIES,
    REQUIRED_CATEGORIES,
    STATEMENTS,
    CheckPolicyError,
    CheckResult,
    Limitation,
    VerificationStatus,
    unsupported,
)
from openflowsheet.verify.checks import (
    KIND_TOLERANCE,
    VerifierError,
    admissibility_checks,
    alias_checks,
    bounds_checks,
    declared_specification_checks,
    energy_checks,
    label_checks,
    material_checks,
    qualification,
    residual_checks,
    routing_tolerances,
    specification_checks,
)
from openflowsheet.verify.projection import PROJECTED_CATEGORIES, Projection, project

if TYPE_CHECKING:
    from openflowsheet.verify.regularity import RegularityEvidence
    from openflowsheet.verify.zero_flow import ZeroFlowSplit

#: §5.4. The registered default: the tolerance table by quantity kind. A supplied policy is an
#: input with a hash, never something the verifier or the solver may adjust on its own.
REGISTERED_POLICY_ID = "K04-check-policy-v1"


@dataclass(frozen=True)
class CheckPolicy:
    """§5.4: the tolerances a verification ran under, and its canonical hash."""

    policy_id: str = REGISTERED_POLICY_ID
    tolerances: Mapping[str, float] = field(default_factory=lambda: dict(KIND_TOLERANCE))

    def __post_init__(self) -> None:
        unknown = sorted(set(self.tolerances) - set(KIND_TOLERANCE))
        if unknown:
            raise CheckPolicyError(
                f"the policy sets tolerances for quantity kinds that do not exist: {unknown}"
            )
        if any(value <= 0.0 for value in self.tolerances.values()):
            raise CheckPolicyError("a tolerance must be positive")

    @property
    def sha256(self) -> str:
        import hashlib

        return hashlib.sha256(
            canonical_json({"policy_id": self.policy_id, "tolerances": dict(self.tolerances)})
        ).hexdigest()

    @property
    def is_registered(self) -> bool:
        return self.policy_id == REGISTERED_POLICY_ID and all(
            self.tolerances.get(kind) == value for kind, value in KIND_TOLERANCE.items()
        )

    def relaxations(self) -> list[Limitation]:
        """Every kind this policy loosens relative to the registered table (§9.4)."""
        return [
            Limitation(
                "relaxation",
                {
                    "check": f"residual.{kind}",
                    "registered": registered,
                    "applied": self.tolerances[kind],
                },
            )
            for kind, registered in KIND_TOLERANCE.items()
            if self.tolerances.get(kind, registered) > registered
        ]


@dataclass(frozen=True)
class CheckReport:
    """§8.3: the check set's output with **no verdict word**, for a partial checkpoint.

    A budget-exhausted iterate that happens to satisfy every check still reads as the failure
    it is, so this type exists precisely so that a failure can carry a diagnosis without the
    diagnosis being mistaken for success.
    """

    checks: tuple[CheckResult, ...]
    target_state_sha256: str

    def as_document(self) -> dict[str, Any]:
        return {
            "checks": [check.as_document() for check in self.checks],
            "target_state_sha256": self.target_state_sha256,
        }


def run_checks(
    flowsheet: Syn001Flowsheet,
    state: Mapping[str, float],
    *,
    policy: CheckPolicy | None = None,
    provider: PropertyProvider | None = None,
) -> tuple[list[CheckResult], str]:
    """§4.1–§4.7 at `state` on the nominal declaration of `flowsheet`. A **fresh provider with no
    cache** unless one is supplied.

    Fresh because blueprint §8.1 says "reevaluate without approximate caches"; the exact cache
    is exact, so this costs nothing at this size and removes the question entirely.
    """
    resolved_policy = policy or CheckPolicy()
    context = EvaluationContext(
        model_version=flowsheet.context.model_version,
        constants_sha256=flowsheet.context.constants_sha256,
        phase_signature=None,
    )
    tear = Syn001TearProblem(flowsheet)
    return _run_checks(
        tear,
        state,
        context=context,
        specifications=specification_checks(flowsheet, state, resolved_policy.tolerances),
        split_fraction=flowsheet.split_fraction,
        policy=resolved_policy,
        provider=provider,
    )


def _run_checks(
    target: Any,
    state: Mapping[str, float],
    *,
    context: EvaluationContext,
    specifications: Sequence[CheckResult],
    split_fraction: float,
    policy: CheckPolicy,
    provider: PropertyProvider | None = None,
) -> tuple[list[CheckResult], str]:
    """The engine of §4.1–§4.7 on any declaration: `target` carries its compiled problem, spec,
    context and certified aliases; the specification checks and `r` are the caller's, derived
    from the declaration's own revision."""
    fresh = provider if provider is not None else Syn001Provider()
    rows, digest = residual_checks(
        target.compiled,
        target.spec,
        state,
        target.context,
        target.spec.row_kinds,
        policy.tolerances,
    )
    checks = _check_set(
        target,
        state,
        state,
        rows=rows,
        context=context,
        specifications=specifications,
        split_fraction=split_fraction,
        policy=policy,
        provider=fresh,
    )
    return checks, digest


def _check_set(
    target: Any,
    state: Mapping[str, float],
    judged_at: Mapping[str, float],
    *,
    rows: Sequence[CheckResult],
    context: EvaluationContext,
    specifications: Sequence[CheckResult],
    split_fraction: float,
    policy: CheckPolicy,
    provider: PropertyProvider,
) -> list[CheckResult]:
    """§4.1–§4.7 in the engine's order, `rows` being §4.1's at `state`. The fresh-flash
    categories — §4.4's energy balances and §4.7's admissibility and independent split — are
    evaluated at `judged_at` (ADR 0013 D1: the verifier's projection, or `state` itself);
    everything else at `state`."""
    values = {check.subject: check.value or 0.0 for check in rows}

    checks: list[CheckResult] = list(rows)
    # A `BoundDeclaration` says whether its certificates were witnessed (T06 spec §8.2); the SYN-001
    # tear's partition is K03's, found at its own initial state, and has no such attribute.
    checks += alias_checks(
        target.partition.elimination.eliminated,
        values,
        getattr(target, "alias_unsupported", ""),
    )
    checks += material_checks(state, split_fraction, policy.tolerances)
    checks += energy_checks(provider, judged_at, context, policy.tolerances)
    checks += specifications
    checks += bounds_checks(provider, state)
    checks += admissibility_checks(provider, judged_at, context)
    return checks


def grade(
    checks: Sequence[CheckResult],
    *,
    policy: CheckPolicy,
    regularity_status: str | None = None,
    regularity_reason: str | None = None,
    derivative_ok: bool | None = None,
) -> tuple[VerificationStatus, list[Limitation]]:
    """§8.1's table and its precedence, with the limitations that justify the word."""
    limitations: list[Limitation] = []

    failed = [c for c in checks if c.result == "fail" and c.category in FAILING_CATEGORIES]
    missing = [c for c in checks if c.result == "unsupported" and c.category in REQUIRED_CATEGORIES]
    for check in missing:
        limitations.append(
            Limitation("unsupported_check", {"check": check.id, "reason": check.reason})
        )
    for check in checks:
        if check.near_threshold:
            limitations.append(
                Limitation(
                    "near_threshold",
                    {"check": check.id, "value": check.value, "threshold": check.tolerance},
                )
            )

    if regularity_status is not None and regularity_status != "NO_RANK_LOSS_DETECTED":
        limitations.append(
            Limitation(
                "rank_limitation", {"status": regularity_status, "reason": regularity_reason}
            )
        )
    if derivative_ok is False:
        limitations.append(Limitation("derivative_limitation", {}))
    limitations += policy.relaxations()

    if failed:
        return "FAILED", limitations
    unverified = (
        bool(missing)
        or (regularity_status is not None and regularity_status != "NO_RANK_LOSS_DETECTED")
        or derivative_ok is False
    )
    if unverified:
        return "UNVERIFIED", limitations
    if not policy.is_registered:
        return "RELAXED", limitations
    return "VERIFIED", limitations


def statements_for(provider: PropertyProvider) -> tuple[str, ...]:
    """§8.2's two required sentences, plus the [A09] qualification as a third."""
    return (*STATEMENTS, qualification(provider))


def absent_state_certificate(reason: str = "final_state_absent") -> list[CheckResult]:
    """§3.1: a verifier handed no final state does not rebuild one and proceed.

    It returns `UNVERIFIED` with every check `unsupported`. The traversal that would rebuild
    the state is K02's code and is perfectly good; the objection is not to the arithmetic but
    to who chose the state — a verifier that reconstructs what it then judges has chosen it.
    """
    return [
        unsupported(id=f"{category}.all", category=category, subject="flowsheet", reason=reason)
        for category in sorted(REQUIRED_CATEGORIES)
    ]


@dataclass(frozen=True)
class SolutionCertificate:
    """§12.1. What was checked, what it was compared against, and what is still not claimed."""

    certificate_id: str
    model_version: str
    constants_sha256: str
    policy_id: str
    plan_id: str
    target_state_sha256: str
    check_policy_id: str
    check_policy_sha256: str
    verification_status: VerificationStatus
    false_success_detected: bool
    checks: tuple[CheckResult, ...]
    regularity: Any
    solution_error_bound_scaled: float | None
    phase_branch: Mapping[str, Any]
    branch_provenance: tuple[Mapping[str, Any], ...]
    transformations: Mapping[str, Any]
    derivative_provenance: Mapping[str, Any]
    independence_qualifications: tuple[Mapping[str, str], ...]
    limitations: tuple[Limitation, ...]
    statements: tuple[str, ...]
    #: ADR 0025 D1.2: the policy this build records, from its one source; never a literal (F3).
    numerical_policy_id: str = CURRENT_POLICY_ID
    #: ADR 0005 D7 (T03 §8.2): the solve's root fingerprint; `None` without a converged target.
    root_fingerprint: Mapping[str, Any] | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "model_version": self.model_version,
            "constants_sha256": self.constants_sha256,
            "policy_id": self.policy_id,
            "plan_id": self.plan_id,
            "target_state_sha256": self.target_state_sha256,
            "check_policy_id": self.check_policy_id,
            "check_policy_sha256": self.check_policy_sha256,
            "verification_status": self.verification_status,
            "false_success_detected": self.false_success_detected,
            "checks": [check.as_document() for check in self.checks],
            "regularity": self.regularity.as_document() if self.regularity else None,
            "solution_error_bound_scaled": self.solution_error_bound_scaled,
            "phase_branch": dict(self.phase_branch),
            "branch_provenance": [dict(entry) for entry in self.branch_provenance],
            "root_fingerprint": (
                dict(self.root_fingerprint) if self.root_fingerprint is not None else None
            ),
            "transformations": dict(self.transformations),
            "derivative_provenance": dict(self.derivative_provenance),
            "independence_qualifications": [
                dict(entry) for entry in self.independence_qualifications
            ],
            "limitations": [limitation.as_document() for limitation in self.limitations],
            "statements": list(self.statements),
            "numerical_policy_id": self.numerical_policy_id,
        }


#: ADR 0010 D9: the `transformations.declaration` of a nominal certificate — nothing freed or
#: promoted. R0.
NOMINAL_DECLARATION: Final[Mapping[str, Any]] = {
    "removed_specification_rows": [],
    "freed": {},
    "promoted": {},
}


@dataclass(frozen=True)
class _Solved:
    """The solve a certificate is about, as the guard resolved it (T04 §4.8 items 1–2)."""

    #: The result the identity was read from: the argument, or a plan's last solve step's.
    source: Any
    #: `x_final` over the declaration's variables, `None` when the result carries none.
    final_state: Mapping[str, float] | None
    #: The solve's tear, `{variable_ids, row_ids}`; empty for a region or plan solve without one.
    tear: Mapping[str, list[str]]


def _last_solve(result: Any) -> Any:
    """A plan result's identity is its last step's solve result's (T04 §4.8 item 1)."""
    steps = getattr(result, "steps", None)
    if steps is None:
        return result
    solved = [step.detail for step in steps if getattr(step, "detail", None) is not None]
    return solved[-1] if solved else result


def _guard(
    spec: ProblemSpec,
    compiled: CompiledProblem,
    result: Any,
    state: Mapping[str, float] | None,
    *,
    solve_plan: Any = None,
    revision_matches: bool = True,
) -> _Solved:
    """T04 §4.8 item 1 (ADR 0010 D9.2): refuse, before any check, a result that is not a solve of
    this declaration at this state.

    The solve's identity is read from its root fingerprint and from its `SolvePlan` (the result's,
    or the region plan the caller holds); `x_final` from `state=`, else `final_state`, else
    `state`. Refusals are `VerifierError`s with an R0 message: `declaration_unidentified`,
    `declaration_mismatch(<field>)`, `state_mismatch(full_state_sha256)`. Only the hash
    comparison is skipped under `state=` (K04 §9's injections)."""
    source = _last_solve(result)
    fingerprint = getattr(source, "root_fingerprint", None)
    own_plan = getattr(source, "plan", None)
    # T04 review S1: only the result identifies the solve — its fingerprint or its own plan. The
    # caller's `solve_plan` is a further claim to compare (and §4.2's alias input), never a
    # substitute: an object that carries neither is not a solve result.
    if fingerprint is None and own_plan is None:
        raise VerifierError("declaration_unidentified")
    plans = [plan for plan in (own_plan, solve_plan) if plan is not None]
    metadata = compiled.metadata
    claimed: list[tuple[str, str]] = []
    if fingerprint is not None:
        claimed.append((fingerprint["model_version"], fingerprint["constants_sha256"]))
    claimed += [(plan.model_version, plan.constants_sha256) for plan in plans]
    for model_version, constants in claimed:
        if model_version != metadata.model_version:
            raise VerifierError("declaration_mismatch(model_version)")
        if constants != metadata.constants_sha256:
            raise VerifierError("declaration_mismatch(constants_sha256)")
    # §4.8 item 1: the first differing of `model_version`, `constants_sha256` and `revision`.
    if not revision_matches:
        raise VerifierError("declaration_mismatch(revision)")

    own = getattr(source, "final_state", None)
    if own is None:
        own = getattr(source, "state", None)
    if own is None:
        own = getattr(result, "state", None)
    if state is None and own is not None and fingerprint is not None:
        vector = state_vector(spec, own)
        if state_sha256(vector, spec.variable_ids) != fingerprint["full_state_sha256"]:
            raise VerifierError("state_mismatch(full_state_sha256)")
    final_state = state if state is not None else own

    tear_plan = getattr(source, "plan", None) if hasattr(source, "final_state") else None
    tear = {
        "variable_ids": list(tear_plan.tear_variable_ids) if tear_plan is not None else [],
        "row_ids": list(tear_plan.tear_row_ids) if tear_plan is not None else [],
    }
    return _Solved(source, final_state, tear)


def verify(
    flowsheet: Syn001Flowsheet,
    result: Any,
    *,
    policy: CheckPolicy | None = None,
    state: Mapping[str, float] | None = None,
) -> SolutionCertificate:
    """The whole of §4, §7 and §8 on the **nominal** declaration of `flowsheet`, in one call.
    `state` overrides the solve's, for §9's injections.

    A solve that is not `CONVERGED` receives no certificate (K04 §3); nor does one of another
    declaration (T04 §4.8 item 1: a bound solve handed here is refused
    `declaration_mismatch(model_version)`, never judged). A converged solve of this declaration
    that carries no final state gets a certificate all the same — `UNVERIFIED`, every check
    `unsupported`, and the limitation named. Returning nothing would make silence
    indistinguishable from a pass.
    """
    # T05 design note §4.4: SYN-001's entry point, and only SYN-001's; a revision-built flowsheet
    # is judged by `verify_revision`, against its revision.
    if not isinstance(flowsheet, Syn001Flowsheet):
        raise VerifierError("syn001_only(verify)")
    _require_converged(result)
    spec = flowsheet.spec()
    solved = _guard(spec, compile_problem(spec), result, state)
    resolved = policy or CheckPolicy()
    if solved.final_state is None:
        return _absent(flowsheet.context, result, resolved)

    tear = Syn001TearProblem(flowsheet)
    final_state = solved.final_state
    context = EvaluationContext(
        model_version=flowsheet.context.model_version,
        constants_sha256=flowsheet.context.constants_sha256,
        phase_signature=None,
    )
    return _certify(
        tear,
        result,
        solved,
        final_state,
        context=context,
        specifications=specification_checks(flowsheet, final_state, resolved.tolerances),
        split_fraction=flowsheet.split_fraction,
        policy=resolved,
        declaration=NOMINAL_DECLARATION,
    )


def verify_bound(
    binding: Any,
    revision: Mapping[str, Any],
    result: Any,
    *,
    policy: CheckPolicy | None = None,
    state: Mapping[str, float] | None = None,
    solve_plan: Any = None,
) -> SolutionCertificate:
    """K04 on the **bound** declaration of a revision (T04 §4.8; ADR 0010 D9): the binding's
    declaration (a freed column, a promoted specification row), judged with K04's check set
    unchanged in kind.

    A certificate is a function of that declaration, the revision's specification values,
    `x_final` and the check policy only — never of the binding's flowsheet, which carries the
    freed coordinate at its guess. `solve_plan` is the region's `SolvePlan` where the caller holds
    one: its identity is guarded like the result's, and its certified aliases must be the ones
    found here (§4.8 item 3).
    """
    _require_converged(result)
    compiled = compile_problem(binding.spec)
    # T04 review S2 (§4.8 item 1): the revision's values judge the solve, the binding's declaration
    # defines it; a document that is not the one the binding was bound from is refused.
    solved = _guard(
        binding.spec,
        compiled,
        result,
        state,
        solve_plan=solve_plan,
        revision_matches=document_sha256(revision) == binding.revision_sha256,
    )
    resolved = policy or CheckPolicy()
    metadata = compiled.metadata
    context = EvaluationContext(
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        phase_signature=None,
    )
    if solved.final_state is None:
        return _absent(context, result, resolved)

    final_state = solved.final_state
    target = BoundDeclaration(binding.spec, compiled, final_state)
    if solve_plan is not None:
        found = [alias_document(row) for row in target.partition.elimination.eliminated]
        planned = [alias_document(row) for row in solve_plan.eliminated_rows]
        if found != planned:
            raise VerifierError(
                "the certified aliases of the declaration at x_final are not the region plan's: "
                f"{[row['row_id'] for row in found]} against "
                f"{[row['row_id'] for row in planned]}"
            )

    values, freed, split_fraction = _revision_values(binding, revision)
    promoted = tuple(binding.promoted.values())
    specifications = declared_specification_checks(
        final_state,
        values=values,
        kinds=binding.spec.variable_kinds,
        freed=freed,
        promoted=promoted,
        tolerances=resolved.tolerances,
    )
    return _certify(
        target,
        result,
        solved,
        final_state,
        context=context,
        specifications=specifications,
        split_fraction=split_fraction,
        policy=resolved,
        declaration={
            "removed_specification_rows": list(binding.removed_specification_rows),
            "freed": dict(binding.freed),
            "promoted": dict(binding.promoted),
        },
    )


#: M02 design note §14.2 B15: the verifier's own table from a revision's basis to its fresh
#: provider. It never calls the binder's constructor (`revision_binding.basis_provider`).
FRESH_PROVIDERS: Final[Mapping[str, Callable[[], PropertyProvider]]] = {
    SYN001_PROVIDER_ID: Syn001Provider,
    "pr-c1-v1": PrC1Provider,
}


def fresh_provider(provider_id: str) -> PropertyProvider:
    """A fresh provider of `provider_id` from `FRESH_PROVIDERS`; any other id is refused."""
    construct = FRESH_PROVIDERS.get(provider_id)
    if construct is None:
        raise VerifierError(f"provider_unknown({provider_id})")
    return construct()


def verify_revision(
    binding: Any,
    revision: Mapping[str, Any],
    result: Any,
    *,
    policy: CheckPolicy | None = None,
    state: Mapping[str, float] | None = None,
    solve_plan: Any = None,
) -> SolutionCertificate:
    """K04 on a **revision-built** flowsheet (T05 design note §4.2): the binding's declaration,
    judged by the table of `verify.table` against the revision's own values.

    The guard, the residual rows, the alias certificates and everything after the check set
    (`_issue`) are the ones `verify_bound` runs; only the check set in between is the table's. The
    table reads the revision through `parse_revision` (ids, pins, parameters) and a fresh
    provider, never the binding's flowsheet or units (R-016). `binding` is an
    `application.revision_binding.RevisionBinding`; `revision` must be the document it was bound
    from, else `declaration_mismatch(revision)`.
    """
    from openflowsheet.models.revision_flowsheet import (
        RevisionError,
        component_basis,
        parse_revision,
    )
    from openflowsheet.orchestrator.splits import lifted_splits
    from openflowsheet.verify.table import revision_checks, revision_phase_branch
    from openflowsheet.verify.zero_flow import dormant_outlets, zero_flow_splits

    _require_converged(result)
    # M02 design note §14.2 B15: the fresh provider of the revision's basis (the basis
    # `parse_revision` reads into `view.basis`), from the verifier's own table.
    basis = component_basis(revision).provider_id
    fresh = fresh_provider(basis)
    compiled = compile_problem(binding.spec)
    solved = _guard(
        binding.spec,
        compiled,
        result,
        state,
        solve_plan=solve_plan,
        revision_matches=document_sha256(revision) == binding.revision_sha256,
    )
    resolved = policy or CheckPolicy()
    metadata = compiled.metadata
    context = EvaluationContext(
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        phase_signature=None,
    )
    if solved.final_state is None:
        return _absent(context, result, resolved, provider=fresh)

    final_state = solved.final_state
    target = BoundDeclaration(
        binding.spec, compiled, final_state, pressure_domain=fresh.describe().domain["P"]
    )
    if solve_plan is not None:
        found = [alias_document(row) for row in target.partition.elimination.eliminated]
        planned = [alias_document(row) for row in solve_plan.eliminated_rows]
        if found != planned:
            raise VerifierError(
                "the certified aliases of the declaration at x_final are not the region plan's: "
                f"{[row['row_id'] for row in found]} against "
                f"{[row['row_id'] for row in planned]}"
            )

    try:
        view = parse_revision(revision)
    except RevisionError as error:
        raise VerifierError(f"revision_unreadable({error.code})") from error
    if view.basis.provider_id != basis:
        raise VerifierError(f"basis_mismatch({view.basis.provider_id}, {basis})")
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )

    rows, digest = residual_checks(
        target.compiled,
        target.spec,
        final_state,
        target.context,
        target.spec.row_kinds,
        resolved.tolerances,
    )
    values = {check.subject: check.value or 0.0 for check in rows}
    checks: list[CheckResult] = list(rows)
    # T05b spec §9.3 (ADR 0012 D7): a split whose branch is `ZERO_FLOW` and whose feed is dormant
    # is judged on its zero-flow form, and so is a dormancy-form outlet whose trigger streams are
    # all dormant (ADR 0012 D12); each label row is checked after the compiled rows.
    zero_flow = (
        *zero_flow_splits(view, splits, final_state),
        *dormant_outlets(view, final_state),
    )
    labels = label_checks(zero_flow, final_state, resolved.tolerances)
    checks += labels
    checks += alias_checks(
        target.partition.elimination.eliminated, values, target.alias_unsupported
    )
    screened = _screen(target, final_state, zero_flow)
    projection = _project(
        target,
        final_state,
        [*rows, *labels],
        screened,
        zero_flow=zero_flow,
        streams=view.streams,
        provider=fresh,
        policy=resolved,
        components=view.components,
    )
    checks += _judged_at(
        lambda judged_at: revision_checks(
            view,
            splits,
            final_state,
            provider=fresh,
            context=context,
            tolerances=resolved.tolerances,
            judged_at=judged_at,
        ),
        final_state,
        projection,
    )
    return _issue(
        target,
        result,
        solved,
        final_state,
        checks=checks,
        digest=digest,
        policy=resolved,
        declaration=NOMINAL_DECLARATION,
        phase_branch=revision_phase_branch(
            final_state, view.streams, splits, components=view.components
        ),
        screened=screened,
        projection=projection,
        provider=fresh,
    )


def alias_document(row: Any) -> dict[str, Any]:
    """An alias certificate by id and by certificate, in a canonical form for comparison —
    `row_id`, the signed rows it equals (sorted: K03 §7.2's procedure lists them in path order, a
    plan by id), its constant mismatch and tolerance — whether K03's `EliminatedRow` or a plan's
    record."""
    return {
        "row_id": row.row_id,
        "equals": sorted([name, sign] for name, sign in row.equals),
        "constant_mismatch": row.constant_mismatch,
        "tolerance": row.tolerance,
    }


def _continuation_level(result: Any) -> str | None:
    """The λ of what the verifier was handed: a checkpoint itself, a result's checkpoint, or a
    plan result's last step's (ADR 0010 D7.4)."""
    if hasattr(result, "continuation_lambda"):
        level: str | None = result.continuation_lambda
        return level
    checkpoint = getattr(result, "checkpoint", None)
    steps = getattr(result, "steps", None)
    if steps:
        checkpoint = getattr(steps[-1], "checkpoint", None) or checkpoint
    return getattr(checkpoint, "continuation_lambda", None)


def _require_converged(result: Any) -> None:
    # T04 §4.4 / A03: a state accepted at λ < 1 is a root of a *modified* problem, whose identity
    # is not the target's. Refused first, before anything is compiled or evaluated — and before
    # the outcome, so the refusal names what the state is.
    level = _continuation_level(result)
    if level is not None and level != "1":
        raise VerifierError(f"continuation_level({level})")
    # K04 §3 and A20, restated by the T03 review's A21 ruling: a solve that did not converge
    # "receives no certificate and a FailureBundle". Certifying it anyway produced a certificate
    # its own schema refuses (`regularity: null`) about a state nobody claimed was a root.
    outcome = getattr(result, "outcome", None)
    if outcome != "CONVERGED":
        raise VerifierError(
            f"a solve that ended {outcome} receives no certificate (K04 §3); its record is the "
            "failure bundle"
        )


def _revision_values(
    binding: Any, revision: Mapping[str, Any]
) -> tuple[dict[str, float], dict[str, str], float]:
    """The revision's §4.5 values by column, its freed columns with their `role: free` ids, and
    `r` — all read from the revision document through the binding's targets (T04 §4.8 item 3).

    Each value in SI by `unit-conversion-v2`, as the binding read it (ADR 0016 D5, reader R3):
    a converted revision is judged against the number it declares, not the number as written."""
    from openflowsheet.models.revision_flowsheet import RevisionError, convert_specification
    from openflowsheet.units import read_number

    def si_value(entry: Mapping[str, Any]) -> float:
        # As the legacy binding reads it (R1): a number by S5's one reading, else `float()`.
        raw = entry["value"]
        number = read_number(raw)
        try:
            return convert_specification(entry, float(raw) if number is None else number)[0]
        except RevisionError as error:
            raise VerifierError(f"the revision's value is unreadable: {error.code}") from None

    entries = {str(entry.get("id")): entry for entry in revision.get("specifications") or ()}
    targets: Mapping[str, Sequence[str]] = binding.specification_targets
    values: dict[str, float] = {}
    freed: dict[str, str] = {}
    split_fraction: float | None = None
    for name, entry in entries.items():
        role = entry.get("role")
        if role == "free":
            for column in targets.get(name, ()):
                if column in binding.freed.values():
                    freed[column] = name
            continue
        if role != "fixed":
            continue
        for column in targets.get(name, ()):
            values[column] = si_value(entry)
        if (entry.get("target") or {}).get("path") == "parameters.split_fraction":
            split_fraction = si_value(entry)
    if split_fraction is None:
        raise VerifierError("the revision declares no split fraction; §4.3 cannot be judged")
    return values, freed, split_fraction


class BoundDeclaration:
    """The declaration a bound solve solved, as the check-set engine reads it (T04 §4.8 item 3):
    its compiled problem and context, its registered scales, and its certified aliases, found by
    K03 §7.2's procedure applied to this declaration at `x_final` and its pressure-shifted copy.
    A region or plan solve has no tear.

    The shifted copy is a state the verifier constructs, so it stays inside the provider's
    declared domain (T06 spec §8.2; ADR 0014 D5): a pressure column moves up by its distinct
    amount when the domain admits the result, else down, and when neither — or when two
    pressures distinct at `x_final` coincide after the move, or the copy cannot be evaluated —
    the alias certificates are `unsupported` with the reason in `alias_unsupported`, and the
    eliminated rows are the procedure's structural answer at `x_final` only."""

    #: K03 §7.2's second state: every pressure moved by a distinct amount, as the tear's.
    PRESSURE_SHIFT: Final = 997.0

    def __init__(
        self,
        spec: ProblemSpec,
        compiled: CompiledProblem,
        state: Mapping[str, float],
        *,
        pressure_domain: tuple[float, float] | None = None,
    ) -> None:
        self.spec = spec
        self.compiled = compiled
        #: The fresh provider's declared pressure range the shifted copy stays inside (ADR 0014
        #: D5): SYN-001's unless given (M02 design note §14.2 B15: the revision's basis's).
        self.pressure_domain = (
            pressure_domain
            if pressure_domain is not None
            else Syn001Provider().describe().domain["P"]
        )
        metadata = compiled.metadata
        self.context = EvaluationContext(
            model_version=metadata.model_version,
            constants_sha256=metadata.constants_sha256,
            phase_signature=None,
        )
        self.scaling = Scaling.from_spec(spec)
        #: T06 spec §8.2: why the alias certificates could not be witnessed; `""` when they were.
        self.alias_unsupported = ""
        self.partition = _BoundPartition(self._aliases(state))

    def _rows(self, state: Mapping[str, float]) -> dict[str, float]:
        result = self.compiled.residual(np.array(state_vector(self.spec, state)), self.context)
        if result.status != "ok" or result.values is None:
            raise VerifierError(f"the residual for the alias certificates returned {result.status}")
        return dict(zip(result.equation_ids, result.values, strict=True))

    def _shifted(self, state: Mapping[str, float]) -> tuple[dict[str, float], str]:
        """K03 §7.2's second state under ADR 0014 D5's direction rule, and `""` or the reason it
        cannot be built: `pressure_shift_outside_domain` when a column's move leaves the
        provider's pressure domain both ways, `pressure_shift_not_generic` when two pressures
        distinct at `state` coincide after the moves (equal ones never can: the amounts are
        distinct and each is positive)."""
        low, high = self.pressure_domain
        shifted = dict(state)
        moved: list[str] = []
        for index, name in enumerate(self.spec.variable_ids):
            if self.spec.variable_kinds.get(name) != "pressure":
                continue
            step = self.PRESSURE_SHIFT * (index + 1)
            if low <= state[name] + step <= high:
                shifted[name] = state[name] + step
            elif low <= state[name] - step <= high:
                shifted[name] = state[name] - step
            else:
                return shifted, "pressure_shift_outside_domain"
            moved.append(name)
        original_at: dict[float, float] = {}
        for name in moved:
            if original_at.setdefault(shifted[name], state[name]) != state[name]:
                return shifted, "pressure_shift_not_generic"
        return shifted, ""

    def _aliases(self, state: Mapping[str, float]) -> AliasElimination:
        jacobian = self.compiled.jacobian(np.array(state_vector(self.spec, state)), self.context)
        if jacobian.status != "ok":
            raise VerifierError(
                f"the Jacobian for the alias certificates returned {jacobian.status}"
            )
        coefficients: dict[str, dict[str, float]] = {name: {} for name in jacobian.row_ids}
        for column, name in enumerate(jacobian.col_ids):
            for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
                row = jacobian.row_ids[jacobian.indices[offset]]
                coefficients[row][name] = float(jacobian.data[offset])
        at_final = self._rows(state)
        shifted, reason = self._shifted(state)
        second = at_final
        if not reason:
            result = self.compiled.residual(
                np.array(state_vector(self.spec, shifted)), self.context
            )
            if result.status == "ok" and result.values is not None:
                second = dict(zip(result.equation_ids, result.values, strict=True))
            else:
                reason = f"shifted_state_{result.status}"
        # Without a second state the procedure's answer is structural only — which rows are
        # copies, and their mismatch at `x_final` — and the constancy of that mismatch is not
        # witnessed: `alias_checks` reports every such certificate `unsupported`, never passed.
        self.alias_unsupported = reason
        return eliminate_alias_rows(
            row_ids=self.spec.equation_ids,
            coefficients=coefficients,
            column_kinds=self.spec.variable_kinds,
            residuals=[at_final, second],
        )


@dataclass(frozen=True)
class _BoundPartition:
    elimination: AliasElimination
    tear_variables: tuple[str, ...] = ()
    tear_rows: tuple[str, ...] = ()


def _absent(
    context: EvaluationContext,
    result: Any,
    resolved: CheckPolicy,
    *,
    provider: PropertyProvider | None = None,
) -> SolutionCertificate:
    """§3.1: a converged solve of this declaration that carries no final state. `provider` is the
    fresh provider the statements name: SYN-001's unless given (M02 design note §14.2 B15)."""
    plan_id = getattr(getattr(result, "plan", None), "plan_id", "")
    checks = absent_state_certificate()
    status, limitations = grade(checks, policy=resolved)
    limitations.append(Limitation("final_state_absent", {}))
    return SolutionCertificate(
        certificate_id=f"cert-{plan_id or 'unknown'}",
        model_version=context.model_version,
        constants_sha256=context.constants_sha256,
        policy_id=getattr(getattr(result, "plan", None), "policy_id", ""),
        plan_id=plan_id,
        target_state_sha256="",
        check_policy_id=resolved.policy_id,
        check_policy_sha256=resolved.sha256,
        verification_status=status,
        false_success_detected=False,
        checks=tuple(checks),
        regularity=None,
        solution_error_bound_scaled=None,
        phase_branch={},
        branch_provenance=(),
        transformations={},
        derivative_provenance={},
        independence_qualifications=(),
        limitations=tuple(limitations),
        statements=statements_for(provider if provider is not None else Syn001Provider()),
    )


def _certify(
    target: Any,
    result: Any,
    solved: _Solved,
    final_state: Mapping[str, float],
    *,
    context: EvaluationContext,
    specifications: Sequence[CheckResult],
    split_fraction: float,
    policy: CheckPolicy,
    declaration: Mapping[str, Any],
) -> SolutionCertificate:
    """§4, §7 and §8 on `target`'s declaration at `final_state`: the one engine both entry points
    share. The regularity screen runs before the fresh-flash categories (ADR 0013 D1)."""
    fresh = Syn001Provider()
    rows, digest = residual_checks(
        target.compiled,
        target.spec,
        final_state,
        target.context,
        target.spec.row_kinds,
        policy.tolerances,
    )
    screened = _screen(target, final_state)
    projection = _project(
        target,
        final_state,
        rows,
        screened,
        zero_flow=(),
        streams=STREAMS,
        provider=fresh,
        policy=policy,
    )
    checks = _judged_at(
        lambda judged_at: _check_set(
            target,
            final_state,
            judged_at,
            rows=rows,
            context=context,
            specifications=specifications,
            split_fraction=split_fraction,
            policy=policy,
            provider=fresh,
        ),
        final_state,
        projection,
    )
    return _issue(
        target,
        result,
        solved,
        final_state,
        checks=checks,
        digest=digest,
        policy=policy,
        declaration=declaration,
        phase_branch=_phase_branch(final_state),
        screened=screened,
        projection=projection,
    )


@dataclass(frozen=True)
class _Screened:
    """K04 §7.1–§7.2 at the certified state: the scaled target Jacobian and residual, their
    pairing identity, and the screen's evidence."""

    matrix: sp.csc_matrix
    scaled_residual: npt.NDArray[np.float64]
    identity: dict[str, Any]
    regularity: RegularityEvidence


def _screen(
    target: Any, final_state: Mapping[str, float], zero_flow: Sequence[ZeroFlowSplit] = ()
) -> _Screened:
    """§7's screen on `target`'s declaration at `final_state`, `zero_flow` its splits' forms.

    The screen is given the identity of the residual evaluated at `final_state` in the same call
    as its target (T06 §8.4 (A2), R-084): equal to the Jacobian's by construction here, so the
    refusal never fires on this path, and it is what any later reuse path must also pass."""
    from openflowsheet.verify.regularity import assemble_target, screen

    assembled = assemble_target(target, final_state, zero_flow)
    regularity = screen(
        assembled.matrix,
        jacobian_identity=assembled.jacobian_identity,
        target_identity=assembled.residual_identity,
        scaled_residual=assembled.scaled_residual,
    )
    return _Screened(
        assembled.matrix, assembled.scaled_residual, assembled.jacobian_identity, regularity
    )


def _project(
    target: Any,
    final_state: Mapping[str, float],
    residual: Sequence[CheckResult],
    screened: _Screened,
    *,
    zero_flow: Sequence[ZeroFlowSplit],
    streams: Sequence[str],
    provider: PropertyProvider,
    policy: CheckPolicy,
    components: Sequence[str] | None = None,
) -> Projection:
    """ADR 0013 D1: where the fresh-flash categories are judged — the verifier's one Newton
    step of the screened matrix from `final_state`, or `final_state` itself when a precondition
    fails (K04-F9 spec §5.1). `residual` is the certificate's residual checks at `final_state`.

    The guards route, so they read the routing tolerances of `policy`, never a tighter τ (ADR
    0013 Amendment 2): a policy that only tightens is projected exactly as the registered one."""
    return project(
        target,
        final_state,
        residual=residual,
        regularity_status=screened.regularity.status,
        matrix=screened.matrix,
        scaled_residual=screened.scaled_residual,
        zero_flow=zero_flow,
        streams=streams,
        domain=provider.describe().domain,
        tolerances=routing_tolerances(policy.tolerances),
        **({} if components is None else {"components": components}),
    )


def _judged_at(
    evaluate: Callable[[Mapping[str, float]], list[CheckResult]],
    final_state: Mapping[str, float],
    projection: Projection,
) -> list[CheckResult]:
    """A check set whose fresh-flash categories are judged at `projection.state` (ADR 0013 D1),
    `evaluate` mapping that state to the set.

    The projection `x̃` is a state the verifier constructs, so a fresh evaluation that fails
    there is a typed result, never a raise (T06 spec §8.2; ADR 0014 D5): the set is evaluated
    again with those categories at `final_state` — everything else is judged there in either
    case — only to name their checks, and each of them is `unsupported` with the reason. No value
    judged at `x_final` stands in for one that was to be judged at `x̃`. A failure at
    `final_state` itself is not about a constructed state and still raises."""
    try:
        return evaluate(projection.state)
    except VerifierError as error:
        if projection.judged_at != "projection":
            raise
        reason = f"projection_unevaluable({str(error).splitlines()[0]})"
    return [
        unsupported(id=check.id, category=check.category, subject=check.subject, reason=reason)
        if check.category in PROJECTED_CATEGORIES and check.scope == "evaluated"
        else check
        for check in evaluate(final_state)
    ]


def _issue(
    target: Any,
    result: Any,
    solved: _Solved,
    final_state: Mapping[str, float],
    *,
    checks: list[CheckResult],
    digest: str,
    policy: CheckPolicy,
    declaration: Mapping[str, Any],
    phase_branch: Mapping[str, Any],
    screened: _Screened,
    projection: Projection,
    provider: PropertyProvider | None = None,
) -> SolutionCertificate:
    """§4.8, §7 and §8 after the check set: the derivative witness, the grade and the certificate
    (T05 design note §4.2). Shared by `_certify` (SYN-001's check set) and `verify_revision` (the
    table's); `checks` and `digest` are the caller's check set and its residual state hash,
    `phase_branch` the caller's record of the branch, `screened` the regularity screen the caller
    ran at `final_state` before its fresh-flash categories (ADR 0013 D1), on the zero-flow form of
    its `ZERO_FLOW` splits (T05b spec §9.3; none for SYN-001), and `projection` where those
    categories were judged, recorded as `transformations.projection` (K04-F9 spec §5.5)."""
    from openflowsheet.verify.checks import derivative_witness
    from openflowsheet.verify.regularity import solution_error_bound

    resolved = policy
    plan = getattr(result, "plan", None)
    plan_id = getattr(plan, "plan_id", "")
    checks += derivative_witness(target, final_state)

    matrix, scaled_residual = screened.matrix, screened.scaled_residual
    identity, regularity = screened.identity, screened.regularity
    # §7.4 as amended: recorded evidence and a disclosure, never a check. A certificate
    # certifies residual accuracy; `b` says what that implies for the solution, and the third
    # required statement says exactly that. It is `||J^-1|| ||F||`, so on this flowsheet a
    # state converged to tolerance rather than to roundoff has `b ~ 145 tau_min` — making it a
    # check would have tightened the registered residual tolerances by ~500x by the back door.
    bound = regularity.solution_error_bound_scaled
    if bound is None:
        bound = solution_error_bound(matrix, scaled_residual)

    derivative_ok = all(
        check.result == "pass" for check in checks if check.category == "derivative_witness"
    )
    status, limitations = grade(
        checks,
        policy=resolved,
        regularity_status=regularity.status,
        regularity_reason=regularity.ill_conditioned_reason,
        derivative_ok=derivative_ok,
    )
    # M02 design note §14.2 B15: the fresh provider the checks ran on, which the independence
    # qualifications and the statements name; SYN-001's unless given.
    if provider is None:
        provider = Syn001Provider()
    capabilities = provider.describe()

    return SolutionCertificate(
        certificate_id=f"cert-{plan_id or digest[:12]}",
        model_version=target.compiled.metadata.model_version,
        constants_sha256=target.compiled.metadata.constants_sha256,
        policy_id=getattr(plan, "policy_id", ""),
        plan_id=plan_id,
        target_state_sha256=digest,
        check_policy_id=resolved.policy_id,
        check_policy_sha256=resolved.sha256,
        verification_status=status,
        # §8.1: a `FAILED` verdict on a solve the solver called `CONVERGED` is the detection
        # G04 requires, and it is recorded rather than left for a reader to infer.
        false_success_detected=(
            status == "FAILED" and getattr(result, "outcome", None) == "CONVERGED"
        ),
        checks=tuple(checks),
        regularity=regularity,
        solution_error_bound_scaled=bound,
        phase_branch=phase_branch,
        # ADR 0005 D7 (T03 §8.1): the solve's own attempt history, item for item.
        branch_provenance=tuple(
            dict(item) for item in getattr(solved.source, "branch_provenance", ()) or ()
        ),
        root_fingerprint=getattr(solved.source, "root_fingerprint", None),
        transformations={
            "scales": {"column": dict(target.scaling.column), "row": dict(target.scaling.row)},
            "eliminated_rows": [
                row.as_document() for row in target.partition.elimination.eliminated
            ],
            "tear": dict(solved.tear),
            # ADR 0010 D9.4: what the binding removed, freed and promoted; empty when nominal.
            "declaration": {key: _plain(value) for key, value in declaration.items()},
            # ADR 0013 D5: where the fresh-flash categories were judged, and why. R0, no float.
            "projection": projection.as_document(),
        },
        derivative_provenance={
            "path": "assembled_schur",
            "pattern_provenance": identity.get("pattern_provenance", "declared-by-compiler"),
            # `None` when the witness did not run (T06 spec §8.2): a 0.0 would read as a pass.
            "witness_max_diff": max(
                (
                    c.value
                    for c in checks
                    if c.category == "derivative_witness" and c.value is not None
                ),
                default=None,
            ),
        },
        independence_qualifications=tuple(
            {
                "check_id": check.id,
                "provider_id": capabilities.provider_id,
                "implementation_sha256": capabilities.implementation_sha256,
                "data_sha256": capabilities.data_sha256,
                "reference_convention": capabilities.reference_convention,
            }
            for check in checks
            if check.independence_qualification is not None
        ),
        limitations=tuple(limitations),
        statements=statements_for(provider),
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list | tuple):
        return list(value)
    return value


def _phase_branch(state: Mapping[str, float]) -> dict[str, Any]:
    """§11: every stream's regime and S3's split, recorded on the certificate."""
    from openflowsheet.models.syn001.flowsheet import STREAMS
    from openflowsheet.verify.checks import COMPONENTS, stream_of

    branch: dict[str, Any] = {}
    for stream in STREAMS:
        carried = stream_of(state, stream)
        branch[stream] = "ZERO_FLOW" if carried.is_dormant else "FLOWING"
    branch["S3_split"] = {
        "vapor_total": state["S3.V"],
        "liquid_total": state["S3.L"],
        "vapor": [state[f"S3.vap.{c}"] for c in COMPONENTS],
        "liquid": [state[f"S3.liq.{c}"] for c in COMPONENTS],
    }
    return branch
