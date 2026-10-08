"""The registered reaction-consistent reference conventions (ADR 0011 D2, amended by ADR 0026 D4).

A reactor balances total enthalpy, `Q + Hdot_in − Hdot_out = 0`, with no separate `xi dh_r` term
(ADR 0011 D2). That form is right only over a provider whose component enthalpies share one
formation datum, so that `Σ ν_i h_i` is an enthalpy of reaction; the conventions registered as such
are listed here. ADR 0026 D4 adds `PR-C1-ref-v1` (M01 spec §6: each C1 component's ideal gas at
298.15 K has h = Δ_fH°) to D2's `SYN-001-ref-v1`.

**Why a new module and not an edit.** `models/syn001/conversion_reactor.py` holds SYN-001's copy of
the set, `{"SYN-001-ref-v1"}`; its source is part of SYN-001's model versions, so editing it would
move SYN-001's registered identity (M01 spec §6, M01.A33). The C1 units check against this registry
instead, and M01.A24 asserts that SYN-001's constant is unchanged and a subset of it. Extending the
set takes a new decision recorded the same way, naming the convention's datum.
"""

from __future__ import annotations

from typing import Final

#: ADR 0011 D2's registered set as amended by ADR 0026 D4.
REACTION_CONSISTENT_CONVENTIONS: Final = frozenset({"SYN-001-ref-v1", "PR-C1-ref-v1"})


def is_reaction_consistent(convention: str) -> bool:
    """Whether `Σ ν_i h_i` is an enthalpy of reaction under `convention` (a registered datum)."""
    return convention in REACTION_CONSISTENT_CONVENTIONS


def reference_convention_not_reaction_consistent(convention: str) -> str:
    """The reason code a reacting unit refuses construction with (ADR 0011 D2, T05 spec §6)."""
    return f"reference_convention_not_reaction_consistent({convention})"
