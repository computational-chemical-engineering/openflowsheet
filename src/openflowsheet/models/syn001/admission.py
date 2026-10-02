"""Declared-phase admission (R-007) and the typed refusals T05's declared-phase units share.

T05 spec §3.4: a unit that writes a stream's enthalpy in a **declared** phase applies R-007's
criterion, `|Hdot_TP - Hdot_phase| / (dHdot_phase/dT) <= 1e-6 K`, exactly as K02's heater and
mixer do — the check is `tp_state.single_phase_admissible`, and this module only turns its answer
into the spec's typed failure grammar (§3.5): a non-`ok` evaluation's message starts with a
registered code on its own line, and free text follows.
"""

from __future__ import annotations

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import UnitEvaluation
from openflowsheet.models.syn001 import REFERENCE_CONVENTION, TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.tp_state import single_phase_admissible
from openflowsheet.thermo import Phase, PropertyProvider, PropertyStatus, StreamState


def inadmissible_phase(port: str, phase: Phase) -> str:
    """The registered code for a declared phase R-007 refuses (spec §13.3)."""
    return f"inadmissible_phase({port}, {phase})"


def state_outside_domain(port: str) -> str:
    """The registered code for a port state the provider refuses as out of domain (§13.3)."""
    return f"state_outside_domain({port})"


def provider_refusal(port: str, status: PropertyStatus, message: str) -> UnitEvaluation:
    """A provider's refusal of a port's state, passed through with its own status.

    `out_of_domain` carries `state_outside_domain(<port>)` as its first line. The SYN-001 provider
    refuses a well-formed state for no other reason; any other status is passed through with the
    provider's message rather than being dressed up as a code the spec does not register.
    """
    detail = f"{port} state: {message}"
    if status == "out_of_domain":
        detail = f"{state_outside_domain(port)}\n{detail}"
    return UnitEvaluation(status=status, message=detail, reference_convention=REFERENCE_CONVENTION)


def admitted_enthalpy(
    provider: PropertyProvider,
    components: tuple[str, ...],
    context: EvaluationContext,
    *,
    unit_id: str,
    port: str,
    stream: StreamState,
    phase: Phase,
) -> float | UnitEvaluation:
    """`stream`'s enthalpy flow written in `phase`, W, or the typed refusal R-007 requires.

    A dormant stream is admissible with exactly zero enthalpy and no property evaluated (ADR 0001
    D3.1). An inadmissible one is `unsupported`, `inadmissible_phase(<port>, <PHASE>)`.
    """
    admissible, enthalpy, equivalent, status, message = single_phase_admissible(
        provider, stream, phase, components, context
    )
    if status != "ok":
        return provider_refusal(port, status, message)
    if not admissible:
        return UnitEvaluation(
            status="unsupported",
            message=(
                f"{inadmissible_phase(port, phase)}\n"
                f"{unit_id}: the {port} stream was declared {phase}, and writing its enthalpy that "
                f"way would be wrong by {equivalent:.3g} K, past the registered "
                f"{TEMPERATURE_TOLERANCE:g} K (R-007). The rows were written for the declared "
                "phase, so answering would be answering about a different function"
            ),
            reference_convention=REFERENCE_CONVENTION,
        )
    return enthalpy
