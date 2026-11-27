"""Phase ids and phase sets (ADR 0062 D6; Q4.R1, R8): the core grammar, rendered.

A phase is `PhaseId(family, qualifier, ordinal)`. The families are the built-in `phase_family`
descriptors `VAPOR`, `LIQUID`, `FLUID`, `SOLID`, in that registration order; an extension family
needs an amendment of ADR 0062. The qualifier, rendered inside `( )`, is one of::

    qual := cid | cid "," form | "model=" mid

with `cid` a component id, `form` a component form and `mid` an F1 id. `,` and `=` are outside the
component alphabet, so a component, a component form and a model id never render alike, even when a
component id equals a model id (Q4.A5). The rendering is
`family ( "(" qualifier ")" if qualifier ) ( "." ordinal if ordinal >= 2 )`: `VAPOR`, `LIQUID.2`,
`FLUID(water)`, `LIQUID(water).2`, `SOLID(CaCO3,calcite)`, `SOLID(model=langmuir-co2)`. The
unqualified first `LIQUID` and `VAPOR` render as the legacy `Phase` values do.

A phase set (`PhaseSet`) is a tuple of distinct phases in canonical order: family by registration
order, then qualifier (none first, then by UTF-8 bytes), then ordinal; it renders joined by `+`,
which is outside every alphabet above. Production code renders only: the parser is the test-only
left inverse (`tests/f2/phase_id_parse.py`) that proves the rendering injective (E-F2-5).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

__all__ = [
    "COMPONENT_ID",
    "FAMILIES",
    "FORM",
    "MODEL_ID",
    "PhaseId",
    "PhaseSet",
    "phase_set",
    "render_phase_set",
]

#: The built-in `phase_family` descriptors in registration order (D6), which is the canonical order.
FAMILIES: Final = ("VAPOR", "LIQUID", "FLUID", "SOLID")
#: D6: a family id.
FAMILY: Final = re.compile(r"[A-Z][A-Z0-9_]*")
#: The component id alphabet (`schemas/process-revision.schema.json`, `components[].id`).
COMPONENT_ID: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")
#: D6: a component form (ADR 0061's `s:<form>` alphabet).
FORM: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
#: An F1 id (ADR 0060; `registry.tokens.ID_PATTERN`, which a test holds this equal to). Not
#: imported from there: `thermo` re-exports this module and stays clear of the registry's import.
MODEL_ID: Final = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9][A-Za-z0-9_-]*)*")
#: D6: the qualifier spelling that names a phase model.
MODEL_PREFIX: Final = "model="


def _qualifier_ok(qualifier: str) -> bool:
    if qualifier.startswith(MODEL_PREFIX):
        return MODEL_ID.fullmatch(qualifier[len(MODEL_PREFIX) :]) is not None
    component, comma, form = qualifier.partition(",")
    return COMPONENT_ID.fullmatch(component) is not None and (
        not comma or FORM.fullmatch(form) is not None
    )


@dataclass(frozen=True, slots=True)
class PhaseId:
    """A phase (ADR 0062 D6): a built-in family, an optional qualifier, an ordinal from 1.

    Construction refuses (`ValueError`) a family that is not built in, a qualifier outside the
    grammar and an ordinal that is not an integer of at least 1.
    """

    family: str
    qualifier: str | None
    ordinal: int

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"phase family {self.family!r} is not one of {', '.join(FAMILIES)}")
        qualifier = self.qualifier
        if qualifier is not None and not (isinstance(qualifier, str) and _qualifier_ok(qualifier)):
            raise ValueError(f"phase qualifier {self.qualifier!r} is outside the D6 grammar")
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise ValueError(f"phase ordinal {self.ordinal!r} is not an integer >= 1")

    def render(self) -> str:
        """D6's rendering, the phase's id (and its exact-cache key, D2)."""
        qualified = self.family if self.qualifier is None else f"{self.family}({self.qualifier})"
        return qualified if self.ordinal == 1 else f"{qualified}.{self.ordinal}"

    def sort_key(self) -> tuple[int, int, bytes, int]:
        """D6's canonical order: family by registration, no qualifier first, then the qualifier's
        UTF-8 bytes, then the ordinal."""
        qualifier = b"" if self.qualifier is None else self.qualifier.encode("utf-8")
        return (FAMILIES.index(self.family), self.qualifier is not None, qualifier, self.ordinal)


#: Distinct phases in canonical order (D6).
type PhaseSet = tuple[PhaseId, ...]


def phase_set(phases: Iterable[PhaseId]) -> PhaseSet:
    """`phases` as a phase set: canonical order; `ValueError` if empty or a phase repeats."""
    ordered = tuple(sorted(phases, key=PhaseId.sort_key))
    if not ordered:
        raise ValueError("a phase set holds at least one phase")
    if len(set(ordered)) != len(ordered):
        raise ValueError("a phase set holds each phase once")
    return ordered


def render_phase_set(phases: PhaseSet) -> str:
    """D6's phase-set rendering, `+`-joined; `ValueError` unless `phases` is a phase set (canonical
    order, distinct, not empty)."""
    if phase_set(phases) != tuple(phases):
        raise ValueError("not in canonical order")
    return "+".join(phase.render() for phase in phases)
