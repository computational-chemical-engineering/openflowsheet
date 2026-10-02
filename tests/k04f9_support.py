"""Shared helpers for the K04-F9 tests (spec `docs/derivations/K04-F9-spec.md`; ADR 0013).

`ref` is `benchmarks/k04f9/reference_values.yaml`. `projection_of` recomputes the verifier's own
projection at a certified state by the certificate path's own private steps — the screen at
`x_final` (`certificate._screen`) and the projection (`certificate._project`) — so that a test
can evaluate the unprojected and projected check functions side by side; it is the same call the
certificate makes, not a second implementation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import yaml

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.models.syn001.flowsheet import STREAMS
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import CheckResult
from openflowsheet.verify.certificate import (
    BoundDeclaration,
    CheckPolicy,
    _project,
    _screen,
)
from openflowsheet.verify.checks import label_checks, residual_checks
from openflowsheet.verify.projection import PROJECTED_CATEGORIES, Projection

REPO_ROOT = Path(__file__).resolve().parents[1]
REF: Final[dict[str, Any]] = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "k04f9" / "reference_values.yaml").read_text()
)
#: Spec §7 row 1 and §5.5: a fresh-flash value at the projection is ≤ 1e-3 of its threshold.
PROJECTED_BOUND: Final = 1e-3
#: The §5.5 grammar of `transformations.projection` at a projected state.
PROJECTED: Final = {
    "judged_at": "projection",
    "reason": "",
    "categories": list(PROJECTED_CATEGORIES),
}


def refused(reason: str) -> dict[str, Any]:
    """The §5.5 grammar of `transformations.projection` at a refused state."""
    return {"judged_at": "final_state", "reason": reason, "categories": list(PROJECTED_CATEGORIES)}


def projection_of(
    target: Any,
    final_state: Mapping[str, float],
    *,
    streams: Sequence[str] = STREAMS,
    zero_flow: Sequence[Any] = (),
    policy: CheckPolicy | None = None,
) -> Projection:
    """The certificate path's projection at `final_state` on `target`'s declaration."""
    resolved = policy or CheckPolicy()
    rows, _ = residual_checks(
        target.compiled,
        target.spec,
        final_state,
        target.context,
        target.spec.row_kinds,
        resolved.tolerances,
    )
    rows += label_checks(zero_flow, final_state, resolved.tolerances)
    screened = _screen(target, final_state, zero_flow)
    return _project(
        target,
        final_state,
        rows,
        screened,
        zero_flow=zero_flow,
        streams=streams,
        provider=Syn001Provider(),
        policy=resolved,
    )


def bound_target(binding: Any, final_state: Mapping[str, float]) -> BoundDeclaration:
    """`verify_bound`'s declaration object for `binding` at `final_state`."""
    return BoundDeclaration(binding.spec, compile_problem(binding.spec), final_state)


def ratios(checks: Iterable[CheckResult], ids: Iterable[str] | None = None) -> dict[str, float]:
    """`|value| / tolerance` of each evaluated check (of `ids`, when given)."""
    wanted = None if ids is None else set(ids)
    return {
        check.id: abs(check.value) / check.tolerance
        for check in checks
        if check.value is not None and check.tolerance and (wanted is None or check.id in wanted)
    }


#: T04 F9's S3 checks: the independent split of S3 and the two balances that read S3's fresh flash.
def is_s3_check(identifier: str) -> bool:
    return identifier.startswith("independent_split.S3.") or identifier in (
        "energy_balance.heater",
        "energy_balance.flash",
    )


def s3_ratios(checks: Iterable[CheckResult]) -> dict[str, float]:
    return {name: value for name, value in ratios(checks).items() if is_s3_check(name)}
