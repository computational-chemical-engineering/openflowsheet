"""Material model layer: the state of material at the provider boundary and its phase ids.

This layer was introduced by package F2 (ADR 0062). `state` holds the provider-level state types
(D2): `StreamState` (`nTP-v1`, K02's) and `EvaluationState` (one substream, any definition);
`phase_id` the phase ids and phase sets (D6). Both are re-exported from `openflowsheet.thermo`.
It sits below `thermo`, whose contract it serves, and imports nothing above it.
"""

from __future__ import annotations

from openflowsheet.material.phase_id import PhaseId, PhaseSet, phase_set, render_phase_set
from openflowsheet.material.state import EvaluationState, StreamState

__all__ = [
    "EvaluationState",
    "PhaseId",
    "PhaseSet",
    "StreamState",
    "phase_set",
    "render_phase_set",
]
