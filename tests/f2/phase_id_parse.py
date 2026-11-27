"""The test-only left inverse of ADR 0062 D6's phase-id rendering (E-F2-5).

Production code renders only (`openflowsheet.material.phase_id`); this parser exists to prove the
rendering injective, by D6's parse rule: the family is the longest `[A-Z0-9_]*` prefix; a `(` opens
the qualifier, closed by the first `)` (neither parenthesis is in any alphabet); a final `.k` needs
k >= 2 without a leading zero, so `LIQUID.1` does not parse. The qualifier's own grammar is checked
by `PhaseId`'s constructor. A phase set splits on `+`, which is outside every alphabet.
"""

from __future__ import annotations

import re
from typing import Final

from openflowsheet.material.phase_id import PhaseId, PhaseSet, phase_set

_FAMILY_PREFIX: Final = re.compile(r"[A-Z0-9_]*")
_ORDINAL: Final = re.compile(r"\.([1-9][0-9]*)")


def parse_phase_id(text: str) -> PhaseId:
    """The phase `text` renders; `ValueError` for text that no phase renders as."""
    family = _FAMILY_PREFIX.match(text)
    assert family is not None  # `*` matches the empty prefix
    rest = text[family.end() :]
    qualifier = None
    if rest.startswith("("):
        close = rest.find(")")
        if close < 0:
            raise ValueError(f"{text!r}: unclosed qualifier")
        qualifier, rest = rest[1:close], rest[close + 1 :]
    ordinal = 1
    if rest:
        found = _ORDINAL.fullmatch(rest)
        if found is None or int(found.group(1)) < 2:
            raise ValueError(f"{text!r}: {rest!r} is not an ordinal of at least 2")
        ordinal = int(found.group(1))
    return PhaseId(family.group(), qualifier, ordinal)


def parse_phase_set(text: str) -> PhaseSet:
    """The phase set `text` renders; `ValueError` unless it is in canonical order."""
    phases = tuple(parse_phase_id(part) for part in text.split("+"))
    if phase_set(phases) != phases:
        raise ValueError(f"{text!r}: not in canonical order")
    return phases
