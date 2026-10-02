"""T08 D1's substitution, reversed: how the T07 report registrations stay checkable.

T08 D1 (release spec §6.1, T08.A10) makes STR-03's message name the revision's instance instead of
the legacy binder's unit id. Over the registered corpora exactly one message moves — the STR-03
message of `SYN-001-conflicting-heater-spec` — and it moves by this substitution only (measured on
`wp/T08` at `2476186`, old code against new, field by field over the 94 documents). With it
reversed, every report is the one T07 registered, byte for byte; so the T07 digests stay the
expectations, checked through this reversal, and the new digests are registered beside them.

**D1 extended to STR-05** (Frank, 2026-09-29, Q-P1-2): a loop's units and the attempt signature
are named by instance too. Over the same 94 documents 38 STR-05 messages move, every one by the
list substitutions below only (measured on `wp/T08` at `f9a7f66`, old code against new, field by
field: the legacy binder's `U-MIX`, `U-HEAT`, `U-FLASH`, `U-SPLIT` become the instances that
authored them).
"""

from __future__ import annotations

from typing import Any

#: (new, old): the one text D1 changes in STR-03.
D1_SUBSTITUTION = ("over-specified units ['heater']", "over-specified units ['U-HEAT']")
#: (new, old): the texts D1's extension changes in STR-05.
D1_STR05_SUBSTITUTIONS = (
    (
        "loop ['mixer', 'heater', 'flash', 'splitter']",
        "loop ['U-MIX', 'U-HEAT', 'U-FLASH', 'U-SPLIT']",
    ),
    (
        "loop ['U-MIX', 'U-RX', 'U-FLASH', 'U-SPLIT']",
        "loop ['U-MIX', 'U-HEAT', 'U-FLASH', 'U-SPLIT']",
    ),
    ("attempt signature ['flash']", "attempt signature ['U-FLASH']"),
)


def d1_str05_reversed_message(message: str) -> str:
    """An STR-05 message with D1's extension undone."""
    for new, old in D1_STR05_SUBSTITUTIONS:
        message = message.replace(new, old)
    return message


def d1_reversed(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`checks` (a report document's) with D1's substitutions undone in STR-03's and STR-05's
    messages."""
    new, old = D1_SUBSTITUTION
    return [
        {**check, "message": check["message"].replace(new, old)}
        if check["id"] == "STR-03"
        else {**check, "message": d1_str05_reversed_message(check["message"])}
        if check["id"] == "STR-05"
        else check
        for check in checks
    ]
