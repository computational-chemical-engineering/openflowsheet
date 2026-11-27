"""Variable ids (ADR 0062 D7, S6): the core grammar, rendered.

A v2 variable id is::

    vid   := owner ("@" sub)? ("#" point ("#" phase)?)? "~" field ("[" index "]")*
    owner := uid ("/" uid)*
    point := uid

with `uid` the revision's id alphabet (`^[A-Za-z0-9][A-Za-z0-9_.:-]*$`, ADR 0062 D11), `sub` a
substream id, `phase` a D6 phase rendering and every `index` in the id alphabet too (a component,
group or attribute-kind id, or a 1-based class index in decimal). None of `/ @ # ~ [ ]` is in any
of those alphabets or in a phase rendering, so each delimiter is unambiguous and every v2 id holds
exactly one `~`, which no legacy id holds.

**Field table** (closed, core; additions by an amendment of ADR 0062). Connection fields: `n`
(carried amount; indices `[component]`, `[component][class]` or `[group]`; on a substream), `a`
(non-partition attribute; `[kind][component]?[class]?`; on a substream), and `h`, `T`, `P`, `Q`,
`W`, `s` (one per connection, no substream, no index). State-point fields: `n`, `T`, `h`, `P`,
`beta`, `v` (their indices are ADR-F5's and F6's). Fields of unit-owned variables are added by
ADR-F6.

Production code renders only; ids stay opaque (R-019). `tests/f2/vid_parse.py` is the test-only
left inverse that proves the rendering injective (E-F2-5), and the layout (`material.layout`) reads
a state by index, never by parsing an id (E-F2-6). An `nTP-v1` connection keeps today's ids
exactly: `legacy_variable_id` renders them as `openflowsheet.models`' `flow_id`, `temperature_id`
and `pressure_id` do (a test holds the two equal; this layer sits below `models`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from openflowsheet.material.phase_id import PhaseId

__all__ = [
    "CONNECTION_FIELDS",
    "POINT_FIELDS",
    "UID",
    "VariableId",
    "legacy_variable_id",
]

#: The revision's id alphabet (ADR 0062 D11; `connection-definition.schema.json`'s `uid`), which
#: also holds every component id, F1 id and decimal class index an `index` can be.
UID: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")
#: D7's connection fields.
CONNECTION_FIELDS: Final = ("n", "a", "h", "T", "P", "Q", "W", "s")
#: D7's state-point fields (ADR-F5, F6).
POINT_FIELDS: Final = ("n", "T", "h", "P", "beta", "v")
#: How many indices a connection field takes, and whether it is on a substream.
_CONNECTION_SHAPE: Final = {
    "n": (True, 1, 2),
    "a": (True, 1, 3),
    **{field: (False, 0, 0) for field in ("h", "T", "P", "Q", "W", "s")},
}


def _uid(text: object, what: str) -> None:
    if not (isinstance(text, str) and UID.fullmatch(text)):
        raise ValueError(f"{what} {text!r} is not in the id alphabet")


@dataclass(frozen=True, slots=True)
class VariableId:
    """One variable's structure (D7): its owner path, substream, state point and phase, field and
    indices. Construction refuses (`ValueError`) anything outside the grammar or the field table;
    `render()` is its id."""

    owner: tuple[str, ...]
    field: str
    index: tuple[str, ...] = ()
    substream: str | None = None
    point: str | None = None
    phase: PhaseId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.owner, tuple) or not self.owner:
            raise ValueError("a variable's owner is a non-empty tuple of ids")
        for part in self.owner:
            _uid(part, "owner id")
        if self.substream is not None:
            _uid(self.substream, "substream id")
        if not isinstance(self.index, tuple):
            raise ValueError("a variable's index is a tuple of ids")
        for part in self.index:
            _uid(part, "index")
        if self.point is None:
            if self.phase is not None:
                raise ValueError("a phase qualifies a state point only")
            if self.field not in CONNECTION_FIELDS:
                raise ValueError(f"{self.field!r} is not a connection field of D7's table")
            on_substream, least, most = _CONNECTION_SHAPE[self.field]
            if (self.substream is not None) != on_substream:
                where = "on a substream" if on_substream else "once per connection"
                raise ValueError(f"connection field {self.field!r} is {where}")
            if not least <= len(self.index) <= most:
                raise ValueError(f"connection field {self.field!r} takes {least} to {most} indices")
        else:
            _uid(self.point, "state point id")
            if self.phase is not None and not isinstance(self.phase, PhaseId):
                raise ValueError("a state point's phase is a PhaseId")
            if self.field not in POINT_FIELDS:
                raise ValueError(f"{self.field!r} is not a state-point field of D7's table")

    def render(self) -> str:
        """D7's rendering, the variable's id."""
        text = "/".join(self.owner)
        if self.substream is not None:
            text += f"@{self.substream}"
        if self.point is not None:
            text += f"#{self.point}"
            if self.phase is not None:
                text += f"#{self.phase.render()}"
        return text + f"~{self.field}" + "".join(f"[{part}]" for part in self.index)


def legacy_variable_id(stream: str, field: str, component: str | None = None) -> str:
    """Today's id of an `nTP-v1` connection's variable (D7: kept exactly): `<stream>.n.<component>`
    for a flow, `<stream>.T` and `<stream>.P` (`models.flow_id`, `temperature_id`,
    `pressure_id`)."""
    if field == "n" and component is not None:
        return f"{stream}.n.{component}"
    if field in ("T", "P") and component is None:
        return f"{stream}.{field}"
    raise ValueError(f"nTP-v1 has no variable {field!r} with component {component!r}")
