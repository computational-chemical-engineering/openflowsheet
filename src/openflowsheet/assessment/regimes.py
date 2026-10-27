"""Held regimes of an assessment: the discrete choices a cost or impact functional depends on.

E01 design §4.3, ADR 0052 D3 (register R-852). A functional never contains `max`, `min`, `abs` or
`ceil` and is never smoothed. Each non-smooth choice — parallel units or the minimum size, a
correlation piece, the heating or cooling service, the utility, the controlling member of a
maximum, a dormant stream — is an *entry* whose choice is made on floats at a state by the rule of
§4.3.2 and then **held**: the builders receive the choice as data and never branch on a symbol.
Each held choice carries admissibility rows `a/nominal ≥ 0`; inside that set the held functional is
the exact cost of a realisable design, so its gradient is the true one.

This module holds the data types, the regime's identity and the float selection rules. Which
entries an item has, and the expressions of its admissibility rows, are the contributor's
(`program.Contributor`); holding at a new state is `AssessmentProgram.select`'s.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final, Literal

from openflowsheet.canonical import canonical_json, document_sha256

__all__ = [
    "ENTRY_KINDS",
    "AdmissibilityRow",
    "EntryKind",
    "Regime",
    "RegimeEntry",
    "select_argmax",
    "select_dormancy",
    "select_piece",
    "select_service",
    "select_size",
    "size_units",
]

EntryKind = Literal["service", "utility", "size", "piece", "argmax", "dormant"]
#: §4.3.1's entry kinds, in its table order.
ENTRY_KINDS: Final[tuple[EntryKind, ...]] = (
    "service",
    "utility",
    "size",
    "piece",
    "argmax",
    "dormant",
)

#: `(Symbols, Algebra) -> Expr`, `program.FunctionalBuilder`; restated here to avoid the import.
_Builder = Callable[[Any, Any], Any]


@dataclass(frozen=True)
class AdmissibilityRow:
    """One row `a(x)/nominal ≥ 0` of a held choice (§4.3.1).

    `row_id` is the row's local name; the program publishes it as `adm.<entry_id>.<row_id>`.
    `nominal` is the absolute value of the row's leading quantity at the selection state, a
    positive constant (§4.3.1: a zero one is replaced by the quantity's K03 nominal or by 1, which
    is the contributor's to apply before it reaches here).
    """

    row_id: str
    build: _Builder
    nominal: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.nominal) and self.nominal > 0.0):
            raise ValueError(
                f"admissibility row {self.row_id!r}: nominal {self.nominal!r} must be finite and "
                "positive; it divides the row"
            )


@dataclass(frozen=True)
class RegimeEntry:
    """One held choice: its id, kind, choice, the rule text that chose it, and its rows."""

    entry_id: str
    kind: EntryKind
    choice: str
    rule_text: str
    admissibility: tuple[AdmissibilityRow, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in ENTRY_KINDS:
            raise ValueError(f"regime entry {self.entry_id!r}: unknown kind {self.kind!r}")
        if not self.choice:
            raise ValueError(f"regime entry {self.entry_id!r}: empty choice")


@dataclass(frozen=True)
class Regime:
    """The held choices `{entry_id: choice}` of one program (§4.1).

    Identity: `signature` is the canonical JSON (ADR 0002 D3) of the entries sorted by id, and
    `sha256` its hash. Kinds and rules are not part of it: two regimes with the same choices are
    the same regime.
    """

    entries: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ordered = {name: str(self.entries[name]) for name in sorted(self.entries)}
        object.__setattr__(self, "entries", MappingProxyType(ordered))

    @classmethod
    def of(cls, entries: Sequence[RegimeEntry]) -> Regime:
        names = [entry.entry_id for entry in entries]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(f"regime entries repeat: {repeated}")
        return cls({entry.entry_id: entry.choice for entry in entries})

    @property
    def signature(self) -> str:
        return canonical_json(dict(self.entries)).decode("utf-8")

    @property
    def sha256(self) -> str:
        return document_sha256(dict(self.entries))

    def choice(self, entry_id: str) -> str | None:
        return self.entries.get(entry_id)

    def without(self, entry_ids: Sequence[str]) -> Regime:
        """This regime with `entry_ids` released to the selection rule."""
        released = set(entry_ids)
        return Regime({k: v for k, v in self.entries.items() if k not in released})


# -- the float selection rules (§4.3.2) ----------------------------------------------------------


def select_service(duty: float, declared: str | None = None) -> str:
    """Rule 1. `Q > 0` heating, `Q < 0` cooling; `Q == 0.0` heating unless the item declares one."""
    if duty > 0.0:
        return "heating"
    if duty < 0.0:
        return "cooling"
    if math.isnan(duty):
        raise ValueError("the duty is NaN; no service can be selected")
    return declared if declared is not None else "heating"


def select_dormancy(total_flow: float) -> str:
    """Rule 3. A stream whose total flow is exactly 0.0 is `dormant`, else `active`."""
    return "dormant" if total_flow == 0.0 else "active"


def select_size(size: float, size_min: float, size_max: float) -> str:
    """Rule 4. `floor` below `S_min`; else `units:N`, N the smallest integer ≥ 1 with
    `S ≤ N·S_max` evaluated in binary64 (ties select N)."""
    if not (math.isfinite(size) and math.isfinite(size_min) and math.isfinite(size_max)):
        raise ValueError(f"size {size!r} or range [{size_min!r}, {size_max!r}] is not finite")
    if size_max < 2.0 * size_min:
        raise ValueError(
            f"size range [{size_min!r}, {size_max!r}] violates S_max ≥ 2 S_min (§4.3.2), which "
            "guarantees S/N ≥ S_min for N ≥ 2"
        )
    if size < size_min:
        return "floor"
    units = max(1, math.ceil(size / size_max))
    while units * size_max < size:
        units += 1
    while units > 1 and (units - 1) * size_max >= size:
        units -= 1
    return f"units:{units}"


def size_units(choice: str) -> int | None:
    """N of a `units:N` choice; `None` for `floor`. Anything else is a malformed choice."""
    if choice == "floor":
        return None
    prefix, _, count = choice.partition(":")
    if prefix != "units" or not count.isdigit() or int(count) < 1:
        raise ValueError(f"size choice {choice!r} is neither 'floor' nor 'units:N' with N ≥ 1")
    return int(count)


def select_piece(value: float, pieces: Sequence[tuple[float, float]]) -> int:
    """Rule 5. The first piece, in declared order, with `lo ≤ z < hi`; the last piece's upper bound
    is closed. Returns its index; a value in no piece raises (the caller refuses the item
    `CORRELATION_OUT_OF_RANGE`)."""
    last = len(pieces) - 1
    for index, (low, high) in enumerate(pieces):
        if low <= value < high or (index == last and low <= value <= high):
            return index
    raise ValueError(f"{value!r} lies in no piece of {list(pieces)}")


def select_argmax(values: Sequence[float]) -> int:
    """Rule 6. The member with the largest value; ties go to the lowest index."""
    if not values:
        raise ValueError("an argmax over no members")
    if any(math.isnan(value) for value in values):
        raise ValueError(f"an argmax over {list(values)} with a NaN member")
    best = 0
    for index, value in enumerate(values):
        if value > values[best]:
            best = index
    return best
