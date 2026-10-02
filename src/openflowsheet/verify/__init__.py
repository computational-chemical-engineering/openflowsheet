"""The verifier and its certificate, introduced by package K04 (`K04-certificate-spec.md`).

**The verifier never sees the solver** (§1 invariant 1). Its input is a state vector and a
revision. It evaluates the original 49 rows itself under a fresh provider with no cache,
assembles the material balances by plain summation from the stream flows alone, recomputes every
stream's enthalpy from a fresh flash of its own `(n, T, P)`, recomputes the phase split and
compares it, and factorizes the Jacobian itself. It reuses no factorization, no cache and no
intermediate of K03.

That is not fastidiousness. K02 measured the case it exists for: at the once-through variant a
completely trivial phase split satisfies **all 49 assembled rows to 5.6e-17 scaled**, every
material balance, the overall energy envelope and the rank screen, with both duties wrong by
8237.85 W in opposite directions. The compiled energy rows read the lifted split and cannot see
it. A fresh flash of S3 can, and so can comparing the split against one.

**What a certificate is not** is as much of this package as what it is. It is target-model
verification: not empirical validation, not an optimality claim, and not a proof that the
verifier has no defects (blueprint §8.1). Those two sentences travel on every certificate as
text, and `SolutionCertificate.statements` is where they live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal

CheckCategory = Literal[
    "residual",
    "alias_certificate",
    "material_balance",
    "energy_balance",
    "specification",
    "bounds_and_domain",
    "phase_admissibility",
    "independent_split",
    "derivative_witness",
]

CheckOutcome = Literal["pass", "fail", "unsupported", "not_applicable"]
CheckScope = Literal["evaluated", "unsupported", "not_applicable"]
VerificationStatus = Literal["VERIFIED", "RELAXED", "UNVERIFIED", "FAILED"]
RegularityStatus = Literal[
    "NO_RANK_LOSS_DETECTED", "RANK_DEFICIENT", "ILL_CONDITIONED", "INCONCLUSIVE"
]

#: §8.1. Regularity is required *evidence* whose status is graded rather than pass/fail, so it
#: is not in this list. Nor is the **solution-error bound**, and that is a ruling rather than an
#: omission (§7.4 as amended 2026-09-22): a certificate certifies *residual* accuracy at the
#: registered tolerances, because blueprint §8.1's acceptance rule is on residuals and balances
#: and nothing in the authority promises solution accuracy. The bound is recorded evidence and
#: a disclosure, never a check.
#:
#: The measurement that forced the ruling: `||J^-1||_1` is 80-476 on this flowsheet (144.8 at
#: nominal), so a state converged *to tolerance* rather than to roundoff has `b ~ 145 tau_min`.
#: Making the bound a check would have failed every one of §9's below-threshold twins and, in
#: effect, tightened the registered residual tolerances by ~500x through the back door.
REQUIRED_CATEGORIES: Final[frozenset[CheckCategory]] = frozenset(
    {
        "residual",
        "alias_certificate",
        "material_balance",
        "energy_balance",
        "specification",
        "bounds_and_domain",
        "phase_admissibility",
        "independent_split",
        "derivative_witness",
    }
)

#: §8.1: a `FAILED` verdict comes only from these. A failed derivative witness or solution-error
#: bound is a limitation on what the Jacobian evidence supports, not a false residual.
FAILING_CATEGORIES: Final[frozenset[CheckCategory]] = frozenset(
    {
        "residual",
        "alias_certificate",
        "material_balance",
        "energy_balance",
        "specification",
        "bounds_and_domain",
        "phase_admissibility",
        "independent_split",
    }
)

#: §8.2. The two sentences blueprint §8.1 requires a certificate to carry as text. Frozen as
#: literals on Fable's Q4 recommended default: a sentence that can drift is a claim that can
#: drift.
STATEMENTS: Final[tuple[str, ...]] = (
    "VERIFIED certifies the residuals at the registered tolerances; at first order the scaled "
    "solution is determined to within the recorded solution-error bound b; no solution "
    "accuracy beyond b is claimed.",
    "This is a target-model verification of the stated equations at the stated state. It is "
    "not an experimental validation of any thermodynamic model or correlation, and it is not "
    "an optimality claim.",
    "No finite test suite constitutes a proof that the verifier has no defects.",
)

#: ADR 0007 D2.4: a quantity within this factor of its threshold is flagged, never failed.
NEAR_THRESHOLD_MARGIN: Final = 10.0


class CheckPolicyError(ValueError):
    """A supplied check policy that cannot be used as given (§9.4, A16)."""


@dataclass(frozen=True)
class CheckResult:
    """§12.2. One check, its value, what it was compared against, and what it is independent of.

    `value`, `tolerance` and `reference` are all three reported because blueprint §8.1 requires
    `|e_i| <= a_i + r_i s_i` with all three visible: a tolerance without its reference cannot be
    audited, and `s_i` is the registered scale rather than anything the solver chose.
    """

    id: str
    category: CheckCategory
    subject: str
    result: CheckOutcome
    scope: CheckScope = "evaluated"
    value: float | None = None
    tolerance: float | None = None
    reference: float | None = None
    reason: str = ""
    near_threshold: bool = False
    independence_qualification: str | None = None

    def __post_init__(self) -> None:
        if self.scope == "evaluated":
            if self.result not in ("pass", "fail"):
                raise ValueError(
                    f"{self.id}: an evaluated check is `pass` or `fail`, not {self.result!r}"
                )
        elif not self.reason:
            raise ValueError(f"{self.id}: a check that is {self.scope} must say why")

    def as_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "subject": self.subject,
            "result": self.result,
            "scope": self.scope,
            "value": _finite_or_none(self.value),
            "tolerance": _finite_or_none(self.tolerance),
            "reference": _finite_or_none(self.reference),
            "reason": self.reason,
            "near_threshold": self.near_threshold,
            "independence_qualification": self.independence_qualification,
        }


def _finite_or_none(value: float | None) -> float | None:
    """JSON has no NaN, and a 0.0 standing in for "no value" is the placeholder-success shape."""
    if value is None:
        return None
    return None if value != value or value in (float("inf"), float("-inf")) else float(value)


def evaluated(
    *,
    id: str,
    category: CheckCategory,
    subject: str,
    value: float,
    tolerance: float,
    reference: float | None = None,
    independence_qualification: str | None = None,
) -> CheckResult:
    """A check that ran, judged by `|value| <= tolerance`, with ADR 0007 D2.4's margin flag."""
    magnitude = abs(value)
    return CheckResult(
        id=id,
        category=category,
        subject=subject,
        result="pass" if magnitude <= tolerance else "fail",
        value=value,
        tolerance=tolerance,
        reference=reference,
        near_threshold=(
            tolerance / NEAR_THRESHOLD_MARGIN < magnitude <= tolerance * NEAR_THRESHOLD_MARGIN
        ),
        independence_qualification=independence_qualification,
    )


def dormant(
    *, id: str, category: CheckCategory, subject: str, reason: str = "ZERO_FLOW"
) -> CheckResult:
    """§6 invariant 4: a check that does not apply is recorded saying so, never skipped."""
    return CheckResult(
        id=id,
        category=category,
        subject=subject,
        result="not_applicable",
        scope="not_applicable",
        reason=reason,
    )


def unsupported(*, id: str, category: CheckCategory, subject: str, reason: str) -> CheckResult:
    """§1 invariant 4: unsupported is a result, and it caps the verdict at `UNVERIFIED`."""
    return CheckResult(
        id=id,
        category=category,
        subject=subject,
        result="unsupported",
        scope="unsupported",
        reason=reason,
    )


@dataclass(frozen=True)
class Limitation:
    """§8.2. Typed, never prose alone, so that a reader can enumerate what was not established."""

    kind: str
    detail: dict[str, Any] = field(default_factory=dict)

    def as_document(self) -> dict[str, Any]:
        return {"kind": self.kind, **{k: v for k, v in self.detail.items()}}
