"""The stability report of a provider that judges phase stability (S10 spec §5.5, ADR 0047 C1).

**Outside the frozen Protocol.** `PropertyProvider` keeps its three methods
(`docs/interfaces-frozen.md` §1); a provider that can judge stability offers
`stability(state, phase, context) -> StabilityReport` as an addition to its concrete class.
`FlashResult` cannot carry a typed report (S10 spec §13 F-2), so a flash states its label in
`message`, and this type is what a caller asks for when it needs the distances themselves.

This module holds only the type. The search that fills it is the provider's (`wilson_ig.py` for
`wilson-ig-v1`), so the provider's `implementation_sha256` covers every line that computes a report.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from openflowsheet.thermo import Phase

#: The three outcomes of a stability judgement (S10 spec §4.3). `STABLE_WITHIN_TESTED_SCOPE` is
#: global only within the scope the report names; `UNKNOWN` says why in `reason`.
StabilityLabel = Literal["STABLE_WITHIN_TESTED_SCOPE", "UNSTABLE", "UNKNOWN"]


@dataclass(frozen=True)
class StabilityReport:
    """One phase judged at one state against the other phase model's trials (S10 spec §5.5)."""

    label: StabilityLabel
    #: The scope id the label is global within, e.g. `"S10-tpd-v1"` (S10 spec §4.3).
    scope: str
    #: The phase judged, as given.
    phase: Phase
    #: The minimum tangent-plane distance per trial model, keyed by the trial model:
    #: `{"VAPOR": tm_V or None, "LIQUID": tm_L or None}`. `None` where that trial was not run.
    tm: Mapping[str, float | None]
    #: The normalised trial composition at the minimum, or `None` where no trial was run.
    trial_composition: tuple[float, ...] | None
    #: Successive-substitution iterations of the liquid trial; 0 when it was not run.
    iterations: int
    #: The last successive-substitution step of the liquid trial, else `None`.
    residual: float | None
    #: The resolution in the tangent-plane distance the label is decided at.
    epsilon: float
    #: `""` when decided; `"<code>: <text>"` when the label is `UNKNOWN`.
    reason: str
