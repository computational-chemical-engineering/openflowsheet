"""The typed refusal of the syn001 cascade and column family (S01 spec §4.5, §5).

A leaf: every syn001 kernel, the column family and the equilibrium-form admission return it, and
`cascade` re-exports both names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: A refusal's category (spec §5). `INVALID_SPECIFICATION` is not a `SolveOutcome` value; see the
#: design-lane question in `docs/S01_DECISIONS.md`.
FailureOutcome = Literal[
    "CAPABILITY_UNAVAILABLE",
    "INVALID_SPECIFICATION",
    "INITIALIZATION_FAILED",
]


@dataclass(frozen=True)
class CascadeFailure:
    """A typed refusal or failure: the outcome and its cause code (spec §4.5, §5)."""

    outcome: FailureOutcome
    cause: str
    message: str = ""
    #: Stable `code(detail)` notices that do not change the outcome (S02 C8: the duty-only
    #: multiplicity warning); empty for every S01 failure.
    warnings: tuple[str, ...] = ()
