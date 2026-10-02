"""Which root a solve returned: the root fingerprint and `same_root`. ADR 0005 D7; T03 §8.2–§8.3.

Blueprint §7.6: "A solve returns one admissible root unless a root-search study was requested.
Store branch provenance, starting point, continuation history, and a root fingerprint with
comparison tolerances." The fingerprint holds only structural fields and an identity digest — never
the state's floats (ADR 0005, alternatives: a fingerprint of floats would need a new ADR 0007 class,
and a hash of a quantized state splits one root across a grid boundary on one platform and not the
other). `same_root` reads the two states themselves, under its own tolerance `δ_root`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, Protocol

from openflowsheet.canonical import document_sha256

__all__ = [
    "DELTA_ROOT",
    "ROOT_FINGERPRINT_POLICY",
    "RootComparisonError",
    "branch_found",
    "root_fingerprint",
    "same_root",
]

ROOT_FINGERPRINT_POLICY: Final = "T03-root-fingerprint-v1"

#: T03 §8.3: ≥ 50× every registered solution-error bound (REC-05 `2 b̂` = 1.28e-6 at `t*`; SYN-001's
#: largest state allowance 1e-6 scaled) and 1/9 629 of the only registered root separation
#: (0.963 scaled, REC-05). Roots closer than this are reported `SAME`.
DELTA_ROOT: Final = 1e-4

RootComparison = Literal["SAME", "DISTINCT", "NOT_COMPARABLE"]


class _HasSplit(Protocol):
    @property
    def unit(self) -> str: ...

    @property
    def vapor_total(self) -> str: ...

    @property
    def liquid_total(self) -> str: ...


class RootComparisonError(ValueError):
    """`same_root` was handed states it cannot vouch for (T03 §8.3 as amended, review S3): a
    state that is not its fingerprint's, variable ids that are not the fingerprint's, or scales
    that do not cover every id. A typed refusal, never one of the three verdicts."""


def branch_found(splits: Sequence[_HasSplit], state: Mapping[str, float]) -> list[tuple[str, str]]:
    """K03 §8.2's branch found, per unit with a lifted split, **from the state** (T03 §8.2 as
    amended, review M1): `V = L = 0` → ZERO_FLOW, `V = 0 < L` → LIQUID, `L = 0 < V` → VAPOR,
    else TWO_PHASE. A property of where the root is, never of the path that reached it.

    The `ZERO_FLOW` arm is ADR 0012 D6 (T05b spec §8; amends R-029) and applies under every
    phase-contract literal, because the fingerprint describes the state: a dormant split's state
    is dormancy, whatever form the attempt ran in. No registered fingerprint has a split with
    `V = L = 0` (T05b W0.4), so `T03-root-fingerprint-v1` is unchanged."""
    found: list[tuple[str, str]] = []
    for split in splits:
        vapor, liquid = state[split.vapor_total], state[split.liquid_total]
        if vapor == 0.0 and liquid == 0.0:
            found.append((split.unit, "ZERO_FLOW"))
        elif vapor == 0.0 and liquid > 0.0:
            found.append((split.unit, "LIQUID"))
        elif liquid == 0.0 and vapor > 0.0:
            found.append((split.unit, "VAPOR"))
        else:
            found.append((split.unit, "TWO_PHASE"))
    return found


def root_fingerprint(
    *,
    model_version: str,
    constants_sha256: str,
    variable_ids: Sequence[str],
    branch_found: Sequence[tuple[str, str]],
    full_state_sha256: str,
) -> dict[str, Any]:
    """T03 §8.2. Issued only on a converged, admissible solve; every field R0 but the digest."""
    return {
        "policy": ROOT_FINGERPRINT_POLICY,
        "model_version": model_version,
        "constants_sha256": constants_sha256,
        "variable_ids_sha256": document_sha256(list(variable_ids)),
        "branch_found": [[unit, regime] for unit, regime in branch_found],
        "full_state_sha256": full_state_sha256,
        "delta_scaled_inf": DELTA_ROOT,
        "claims": {"uniqueness": "NOT_ASSESSED", "dynamic_stability": "NOT_ASSESSED"},
    }


def same_root(
    fingerprint_a: Mapping[str, Any],
    state_a: Mapping[str, float],
    fingerprint_b: Mapping[str, Any],
    state_b: Mapping[str, float],
    scales: Mapping[str, float],
    variable_ids: Sequence[str],
) -> RootComparison:
    """T03 §8.3: `NOT_COMPARABLE` across problems; `DISTINCT` on another branch or beyond
    `δ_root` in scaled coordinates; `SAME` otherwise.

    A root of another problem is neither the same nor a different root of this one, so a
    differing policy, model, constants or variable set is `NOT_COMPARABLE` before any number is
    read. The comparison reads states, so it is told which: each state's ADR 0008 D2 hash over
    `variable_ids` must be its fingerprint's `full_state_sha256`, the ids' hash its
    `variable_ids_sha256`, and every id must have a positive scale — else `RootComparisonError`.
    The maximum runs over the ids, never over whatever keys `scales` holds.
    """
    from openflowsheet.canonical import state_sha256

    for key in ("policy", "model_version", "constants_sha256", "variable_ids_sha256"):
        if fingerprint_a[key] != fingerprint_b[key]:
            return "NOT_COMPARABLE"
    if document_sha256(list(variable_ids)) != fingerprint_a["variable_ids_sha256"]:
        raise RootComparisonError("the variable ids are not the fingerprints' variable set")
    for label, fingerprint, state in (("a", fingerprint_a, state_a), ("b", fingerprint_b, state_b)):
        if state_sha256(state, variable_ids) != fingerprint["full_state_sha256"]:
            raise RootComparisonError(f"state {label} is not the state its fingerprint identifies")
    unscaled = [name for name in variable_ids if not scales.get(name, 0.0) > 0.0]
    if unscaled:
        raise RootComparisonError(f"no positive scale for {unscaled[:3]}")
    if fingerprint_a["branch_found"] != fingerprint_b["branch_found"]:
        return "DISTINCT"
    distance = max(
        (abs(state_a[name] - state_b[name]) / scales[name] for name in variable_ids), default=0.0
    )
    return "DISTINCT" if distance > DELTA_ROOT else "SAME"
