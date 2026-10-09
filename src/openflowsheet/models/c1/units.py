"""What the six C1 process units share (design note §8, §14.2; M02 WO-8.2).

The units are `c1.feed_source`, `c1.product_sink`, `c1.stream_splitter`, `c1.adiabatic_mixer`,
`c1.tp_heater` and `c1.tp_flash`, one module each, as SYN-001's are. They share their manifests'
domain (the provider's declared box), the check that a unit is built over the C1 component set and
`pr-c1-v1`, and the causal evaluates' reading of a vapour stream: B14's `classify` with B16's
refusal, and the enthalpy flow `Σn · h` the blocks write.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError, UnitEvaluation
from openflowsheet.models.c1 import COMPONENTS, PROVIDER_ID, REFERENCE_CONVENTION, TAU_DEW
from openflowsheet.models.c1.blocks import exactly_dormant
from openflowsheet.models.c1.phase import classify
from openflowsheet.thermo import Phase, PropertyProvider, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import P_MAX, P_MIN, T_MAX, T_MIN

__all__ = [
    "DESIGN_NOTE",
    "PACKAGE",
    "P_RANGE",
    "T_RANGE",
    "c1_components",
    "c1_provider",
    "enthalpy_flow",
    "vapour_refusal",
]

#: Where the C1 units' equations are stated.
DESIGN_NOTE: Final = "docs/design/M02-pymrm-adapter.md §8, §14.2; docs/derivations/M01-spec.md §7"
#: The package that introduced them.
PACKAGE: Final = "M02"
#: The manifests' domain: `pr-c1-v1`'s declared box (M01 spec §5.3).
T_RANGE: Final = (T_MIN, T_MAX)
P_RANGE: Final = (P_MIN, P_MAX)


def c1_components(unit_id: str, components: Sequence[str]) -> None:
    """A C1 unit is built over the C1 component set, in the provider's order."""
    if tuple(components) != COMPONENTS:
        raise SpecificationError(
            f"{unit_id}: a C1 unit is built over the components {COMPONENTS}, not "
            f"{tuple(components)}"
        )


def c1_provider(unit_id: str, provider: PropertyProvider) -> None:
    """A C1 unit that holds a provider holds `pr-c1-v1` (ADR 0001 D5.2: no mixed conventions)."""
    identity = provider.describe().provider_id
    if identity != PROVIDER_ID:
        raise SpecificationError(
            f"{unit_id}: a C1 unit evaluates {PROVIDER_ID}, not {identity!r} (ADR 0001 D5.2)"
        )


def vapour_refusal(
    provider: PropertyProvider, context: EvaluationContext, where: str, stream: StreamState
) -> UnitEvaluation | None:
    """B16: a flowing stream a unit writes as vapour is VAPOR by `classify` (M01 §7 rule 3 with
    τ_dew), or the evaluate refuses `unsupported`, `vapour_phase_inadmissible: <where>: liquid
    NH3 fraction <value> > 1e-10` (`…: LIQUID` for a pure-NH3 liquid). A provider refusal is
    passed through with its own status. `None` for a dormant or an admissible stream."""
    if exactly_dormant(stream.n):
        return None
    regime, value, result = classify(
        provider, context, stream.n, stream.temperature, stream.pressure
    )
    if regime is None:
        return UnitEvaluation(
            status=result.status,
            message=f"{where}: flash: {result.message}",
            reference_convention=REFERENCE_CONVENTION,
        )
    if regime in ("VAPOR", "ZERO_FLOW"):
        return None
    reading = "LIQUID" if regime == "LIQUID" else f"liquid NH3 fraction {value:.3g} > {TAU_DEW:g}"
    return UnitEvaluation(
        status="unsupported",
        message=f"vapour_phase_inadmissible: {where}: {reading}",
        reference_convention=REFERENCE_CONVENTION,
    )


def enthalpy_flow(
    provider: PropertyProvider, context: EvaluationContext, stream: StreamState, phase: Phase
) -> tuple[float, UnitEvaluation | None]:
    """`Ḣ = Σn · h` of `stream` in `phase`, the enthalpy-flow blocks' value (`0.0` at exact
    dormancy, B17), or the provider's refusal as a failed evaluation."""
    if exactly_dormant(stream.n):
        return 0.0, None
    result = provider.evaluate_phase(
        PropertyRequest(state=stream, phase=phase, properties=("h",)), context
    )
    if result.status != "ok":
        return 0.0, UnitEvaluation(
            status=result.status,
            message=f"{phase.lower()} enthalpy: {result.message}",
            reference_convention=REFERENCE_CONVENTION,
        )
    return stream.total_flow * result.values["h"], None
