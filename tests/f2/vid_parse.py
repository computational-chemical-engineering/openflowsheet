"""The test-only left inverse of ADR 0062 D7's variable-id rendering (E-F2-5).

Production code renders only (`openflowsheet.material.vid`); this parser exists to prove the
rendering injective, and E-F2-6 asserts that `src/` cannot import it. The parse follows the
delimiters, none of which is in the id alphabet or a phase rendering: the one `~` splits the head
from the field; the field runs to the first `[`, and each `[...]` is one index; the head splits on
`#` into the owner (with its `@` substream), the state point and its phase; the owner splits on
`/`. The parts' own grammar is checked by `VariableId`'s constructor and, for the phase, by D6's
parser (`f2.phase_id_parse`).
"""

from __future__ import annotations

import re
from typing import Final

from f2.phase_id_parse import parse_phase_id

from openflowsheet.material.vid import VariableId

_FIELD: Final = re.compile(r"[^\[\]]+")
_INDICES: Final = re.compile(r"(?:\[[^\[\]]*\])*")


def parse_vid(text: str) -> VariableId:
    """The variable `text` renders; `ValueError` for text that no variable renders as."""
    head, tilde, tail = text.partition("~")
    if not tilde or "~" in tail:
        raise ValueError(f"{text!r}: a variable id holds exactly one '~'")
    field = _FIELD.match(tail)
    if field is None:
        raise ValueError(f"{text!r}: no field")
    indices = tail[field.end() :]
    if _INDICES.fullmatch(indices) is None:
        raise ValueError(f"{text!r}: {indices!r} is not a sequence of [index]")
    index = tuple(part[1:] for part in indices.split("]")[:-1])
    parts = head.split("#")
    if len(parts) > 3:
        raise ValueError(f"{text!r}: more than a point and a phase")
    owner_part, at, substream = parts[0].partition("@")
    point = parts[1] if len(parts) > 1 else None
    phase = parse_phase_id(parts[2]) if len(parts) > 2 else None
    return VariableId(
        owner=tuple(owner_part.split("/")),
        field=field.group(),
        index=index,
        substream=substream if at else None,
        point=point,
        phase=phase,
    )
