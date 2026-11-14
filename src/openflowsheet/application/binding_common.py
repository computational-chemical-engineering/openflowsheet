"""The binders' shared vocabulary: the refusal type, its hint bound and code, column ownership.

`Unbound` is why a revision could not be bound, in the kinds that call for different statuses;
`HINT_LIMIT` bounds its hint and `refusal_code` reads its code token. `_column_owners` is the
naming convention that assigns a column to the unit that owns it. Both binders, the legacy one in
`binding` and the revision binder in `revision_binding`, use these, so they live in a module that
imports neither; `binding` re-exports every public name.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from openflowsheet.messages import audit


@dataclass(frozen=True)
class Unbound:
    """Why a revision could not be bound, in the kinds that call for different statuses.

    Decided by Frank on 2026-09-24 (register R-022), refining F1 of the T01 review. The kinds are
    not interchangeable: a revision whose specifications contradict each other has a real defect;
    one missing a specification is incomplete, which blueprint §4.3 calls `DRAFT` in so many
    words; and one this binding cannot read may be perfectly fine, so reporting it as a fault
    would repeat the old `UNSUPPORTED_RANK_STRUCTURE` mistake of describing the tool as if it were
    the revision.

    T07 ruling round 5, S3 adds `inadmissible`: a value the document *fixes* that the model it
    names refuses at construction (`SpecificationError`), outside that model's declared domain.
    A finding about the document, like `conflict`. A refused *start* is `incomplete` (blueprint
    §4.3: "a poor guess is not proof that the specified process is impossible").
    """

    kind: Literal["conflict", "inadmissible", "incomplete", "unsupported"]
    detail: str
    implicated: tuple[str, ...] = ()
    #: What would be accepted (T07 ruling round 6, B2), beside the unchanged code in `detail`;
    #: bounded to `HINT_LIMIT` code points by `bound_text` (§10.4). Not part of equality: two
    #: refusals with one code are one refusal.
    hint: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if audit.auditor is not None:  # MSG-G3; frame 1 is the generated `__init__`
            audit.auditor.observe(self.detail, sys._getframe(2).f_globals.get("__name__", ""))
        if self.hint is not None:
            from openflowsheet.application.projection import bound_text

            object.__setattr__(self, "hint", bound_text(self.hint, HINT_LIMIT))


#: Ruling round 6, B2: `bound_text` bounds each hint to 512 code points.
HINT_LIMIT: Final = 512


def refusal_code(detail: str) -> str:
    """A refusal's code token: its `detail` up to the first `(` (T07 ruling round 6, B1)."""
    return detail.split("(", 1)[0]


def _column_owners(
    columns: Sequence[str], streams: Mapping[str, str], units: Sequence[str]
) -> dict[str, str]:
    """Which unit owns each column: the producer of its stream, or the unit its id names.

    The naming convention lives here, in the layer that knows this flowsheet, and not in the
    structural layer (register R-019). `streams` maps a stream id to its producing unit; a column
    belongs to a stream when its id begins with that stream and a separator, which covers the
    lifted split (`<stream>.vap.<component>`) as well as the declared state.
    """
    owners: dict[str, str] = {}
    for column in columns:
        head = column.split(".", 1)[0]
        if head in units:
            owners[column] = head
        elif head in streams:
            owners[column] = streams[head]
    return owners
