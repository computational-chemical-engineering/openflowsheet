"""The check set and its verdict: the policy, the check-set engine, grading, the certificate. §8.

`run_checks` evaluates the check set at a state under a `CheckPolicy`, `grade` turns the results
into a verification status, and `SolutionCertificate` and `ExternalEvidence` are the records the
verifier issues and takes. Issuing or withholding a certificate for a solve (`verify`,
`verify_bound`, `verify_revision`) is `verify.certificate`'s, which re-exports every name here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from openflowsheet.canonical import canonical_json
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.run.compare import CURRENT_POLICY_ID
from openflowsheet.thermo import PropertyProvider
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
    admissibility_checks,
    alias_checks,
    bounds_checks,
    energy_checks,
    material_checks,
    qualification,
    residual_checks,
    specification_checks,
)

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


@dataclass(frozen=True)
class ExternalEvidence:
    """What a coupled run's driver supplies about its external units (M02 design note §4.4;
    ADR 0034 D3): two `residual` checks per unit, judged with the rest of the check set; an
    `external_model` limitation per unit; and, per unit, the derivative the external map does not
    have (`unavailable`), recorded under `derivative_provenance.external_map`."""

    checks: tuple[CheckResult, ...]
    limitations: tuple[Limitation, ...]
    derivatives: Mapping[str, str]
