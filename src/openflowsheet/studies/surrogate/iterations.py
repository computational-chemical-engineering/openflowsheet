"""When a later iteration of a surrogate study may run, and what it records about the earlier ones
(M04 spec §5.5, §18 A1.2; ADR 0036 Amendment 1 D2; R-290).

An iteration may follow automatically only when the previous verdict's only reason is
`coverage_bound_below_minimum` — which happens by chance with probability ≈ 0.10 for a correct
pipeline. Any other outcome is a measured limitation that needs a design-lane amendment, so the
admission of `it<i>` (i ≥ 2) enforces the rule: every `it<j>`, j < i, of the same parent has a
manifest with verdict NOT_PROMOTABLE, `not_promotable == ["coverage_bound_below_minimum"]` and no
INSUFFICIENT_EVIDENCE reason; otherwise `iteration_not_permitted`. The `it<i>` manifest lists those
manifests' SHA-256s as `predecessors`, in iteration order.

`predecessors(variant, plan_id, manifests)` is that guard over the manifests a caller found (the
application reads them from its artifact table); it is a pure function of them. A manifest counts
only when it passes `check_manifest` — the stored verdict is re-derived, never trusted — and its
own `predecessors` are the chain found for the iterations before it. Exactly one distinct manifest
of each earlier iteration must exist for the parent: with several, the predecessor is ambiguous and
the iteration is refused rather than chosen (a build-lane decision, reported to the design lane).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from openflowsheet.adapters.variants import Variant
from openflowsheet.studies.surrogate.manifest import check_manifest
from openflowsheet.studies.surrogate.plan import REGISTERED_PLANS, PlanRefusedError

__all__ = ["CODE", "StoredManifest", "coverage_only_failure", "predecessors"]

#: The admission guard's code (spec §18 A1.2, A1.5).
CODE: Final = "iteration_not_permitted"


@dataclass(frozen=True)
class StoredManifest:
    """A SurrogateManifest as stored: its SHA-256 (the surrogate's identity) and its document."""

    sha256: str
    document: Mapping[str, Any]


def coverage_only_failure(promotion: Mapping[str, Any]) -> bool:
    """The one outcome that permits another iteration (spec §5.5): NOT_PROMOTABLE with
    `coverage_bound_below_minimum` as the only reason and no INSUFFICIENT_EVIDENCE reason."""
    return (
        promotion["verdict"] == "NOT_PROMOTABLE"
        and list(promotion["not_promotable"]) == ["coverage_bound_below_minimum"]
        and list(promotion["insufficient"]) == []
    )


def _same_parent(document: Mapping[str, Any], variant: Variant) -> bool:
    parent = document["parent"]
    return (parent["model_id"], parent["variant_id"], parent["variant_sha256"]) == (
        variant.model_id,
        variant.variant_id,
        variant.sha256,
    )


def predecessors(
    variant: Variant, plan_id: str, manifests: Iterable[StoredManifest]
) -> tuple[str, ...]:
    """The SHA-256s of the manifests of iterations 1 … i−1 that permit `plan_id` = `it<i>`, in
    iteration order; `()` for an iteration-1 plan. `PlanRefusedError` with `CODE` otherwise.
    `plan_id` must be registered (`plan.registered_plan` refuses an unregistered one first)."""
    iteration = REGISTERED_PLANS[plan_id][0]
    if iteration == 1:
        return ()
    found: dict[int, dict[str, Mapping[str, Any]]] = {j: {} for j in range(1, iteration)}
    for stored in manifests:
        document = stored.document
        earlier = document.get("plan_id")
        for j in found:
            if earlier == f"it{j}" and _same_parent(document, variant):
                found[j][stored.sha256] = document
    chain: list[str] = []
    for j in range(1, iteration):
        candidates = found[j]
        where = f"{plan_id} of {variant.variant_id}: it{j}"
        if not candidates:
            raise PlanRefusedError(CODE, f"{where} has no manifest")
        if len(candidates) > 1:
            raise PlanRefusedError(
                CODE,
                f"{where} has {len(candidates)} distinct manifests; the predecessor is "
                f"ambiguous ({sorted(candidates)})",
            )
        ((sha256, document),) = candidates.items()
        findings = check_manifest(document)
        if findings:
            raise PlanRefusedError(
                CODE, f"{where}'s manifest {sha256} fails the checker: {findings}"
            )
        if list(document["predecessors"]) != chain:
            raise PlanRefusedError(
                CODE,
                f"{where}'s manifest {sha256} lists predecessors {document['predecessors']}, "
                f"not {chain}",
            )
        promotion = document["promotion"]
        if not coverage_only_failure(promotion):
            raise PlanRefusedError(
                CODE,
                f"{where} ended {promotion['verdict']} (insufficient {promotion['insufficient']}, "
                f"not_promotable {promotion['not_promotable']}); only a failure on "
                "coverage_bound_below_minimum alone permits another iteration (spec §5.5)",
            )
        chain.append(sha256)
    return tuple(chain)
