"""Maximum matching, the canonical matching, and the coarse Dulmage-Mendelsohn partition.

T01 specification §6. Three things are separated here on purpose:

**The sets are invariant, the sequences are canonical.** The structural rank and the four DM parts
are properties of the incidence graph: any maximum matching yields the same partition, which is a
theorem and is asserted (A05) against twenty seeded permutations. The *matching itself* is not
unique, so what gets recorded is a defined object — the lexicographically least maximum matching
under declaration order (§6.2) — and not whatever an algorithm happened to produce. Gate G05
compares structural artifacts between two CI architectures on every push, so "whatever the
algorithm produced" is not good enough: the recorded object has to be a minimum, provably.

**Declaration order, not byte order of ids.** ADR 0002 D2 already pins `variable_ids` and
`equation_ids` in order inside `model_version`, so declaration order is the order the structure
digest fixes. Byte order of the ids is not: it sorts the units alphabetically, which is not
flowsheet order and fixes nothing that the declaration order does not already fix.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "DulmageMendelsohn",
    "canonical_matching",
    "dulmage_mendelsohn",
    "maximum_matching",
]


def _augment(
    column: int,
    incidence: Sequence[frozenset[int]],
    row_mate: list[int],
    seen: list[bool],
) -> bool:
    """Kuhn's augmenting search from `column`, over rows it references."""
    for row in incidence[column]:
        if seen[row]:
            continue
        seen[row] = True
        if row_mate[row] < 0 or _augment(row_mate[row], incidence, row_mate, seen):
            row_mate[row] = column
            return True
    return False


def _match_indices(
    incidence: Sequence[frozenset[int]], row_count: int, columns: Sequence[int]
) -> dict[int, int]:
    """A maximum matching over `columns`, as `column -> row`. Any maximum matching will do here."""
    row_mate = [-1] * row_count
    for column in columns:
        _augment(column, incidence, row_mate, [False] * row_count)
    return {column: row for row, column in enumerate(row_mate) if column >= 0}


def maximum_matching(
    row_ids: Sequence[str], column_ids: Sequence[str], incidence: Mapping[str, frozenset[str]]
) -> dict[str, str]:
    """Some maximum matching, as `column_id -> row_id`. Its *size* is the structural rank."""
    rows = {name: index for index, name in enumerate(row_ids)}
    by_column: list[frozenset[int]] = [
        frozenset(rows[row] for row in row_ids if column in incidence[row]) for column in column_ids
    ]
    matched = _match_indices(by_column, len(row_ids), range(len(column_ids)))
    return {column_ids[column]: row_ids[row] for column, row in matched.items()}


def canonical_matching(
    row_ids: Sequence[str], column_ids: Sequence[str], incidence: Mapping[str, frozenset[str]]
) -> dict[str, str]:
    """The lexicographically least maximum matching under declaration order (§6.2).

    Constructively: for each column in order, take the least row not yet taken such that a
    maximum matching extending the assignments so far still exists; leave the column unmatched
    when no row does. The result is the minimum of a finite non-empty set under a total order, so
    it exists, is unique, and leaves no tie — which is §6.2's totality argument, and the reason
    this is defined as an object rather than as an algorithm's output.
    """
    rows = {name: index for index, name in enumerate(row_ids)}
    by_column: list[frozenset[int]] = [
        frozenset(rows[row] for row in row_ids if column in incidence[row]) for column in column_ids
    ]
    target = len(_match_indices(by_column, len(row_ids), range(len(column_ids))))

    fixed: dict[int, int] = {}
    for column in range(len(column_ids)):
        taken = set(fixed.values())
        for row in sorted(by_column[column]):
            if row in taken:
                continue
            trial = {**fixed, column: row}
            used_rows = set(trial.values())
            free_columns = [
                other for other in range(len(column_ids)) if other not in trial and other > column
            ]
            remainder: list[frozenset[int]] = [
                by_column[other] - used_rows if other in free_columns else frozenset()
                for other in range(len(column_ids))
            ]
            if len(trial) + len(_match_indices(remainder, len(row_ids), free_columns)) == target:
                fixed = trial
                break
    return {column_ids[column]: row_ids[row] for column, row in fixed.items()}


@dataclass(frozen=True)
class DulmageMendelsohn:
    """The coarse partition. Every field is in declaration order and matching-independent."""

    over_rows: tuple[str, ...]
    over_cols: tuple[str, ...]
    under_rows: tuple[str, ...]
    under_cols: tuple[str, ...]
    square_rows: tuple[str, ...]
    square_cols: tuple[str, ...]
    structural_rank: int

    @property
    def excess(self) -> int:
        return len(self.over_rows) - len(self.over_cols)

    @property
    def deficit(self) -> int:
        return len(self.under_cols) - len(self.under_rows)

    def as_document(self) -> dict[str, object]:
        return {
            "over_rows": list(self.over_rows),
            "over_cols": list(self.over_cols),
            "under_rows": list(self.under_rows),
            "under_cols": list(self.under_cols),
            "square_rows": list(self.square_rows),
            "square_cols": list(self.square_cols),
            "structural_rank": self.structural_rank,
            "excess": self.excess,
            "deficit": self.deficit,
        }


def dulmage_mendelsohn(
    row_ids: Sequence[str],
    column_ids: Sequence[str],
    incidence: Mapping[str, frozenset[str]],
    matching: Mapping[str, str] | None = None,
) -> DulmageMendelsohn:
    """The coarse DM partition (§6.3), from any maximum matching.

    `R+` is the unmatched rows together with everything reachable from them by alternating paths
    (row -> any column it references -> that column's matched row). It is exactly the set of rows
    unmatched in *some* maximum matching, which is what makes it the honest extent of an excess:
    any row in it could be the one left out, and §11's statement S4 says so. `R-`/`C-` is the
    mirror image. Nothing here depends on which maximum matching was supplied.
    """
    pairs = (
        dict(matching) if matching is not None else maximum_matching(row_ids, column_ids, incidence)
    )
    row_mate = {row: column for column, row in pairs.items()}
    references = {row: incidence[row] for row in row_ids}
    by_column: dict[str, list[str]] = {column: [] for column in column_ids}
    for row in row_ids:
        for column in references[row]:
            by_column[column].append(row)

    over_rows: set[str] = set()
    over_cols: set[str] = set()
    stack = [row for row in row_ids if row not in row_mate]
    over_rows.update(stack)
    while stack:
        row = stack.pop()
        for column in references[row]:
            if column in over_cols:
                continue
            over_cols.add(column)
            mate = pairs.get(column)
            if mate is not None and mate not in over_rows:
                over_rows.add(mate)
                stack.append(mate)

    under_cols: set[str] = set()
    under_rows: set[str] = set()
    columns = [column for column in column_ids if column not in pairs]
    under_cols.update(columns)
    while columns:
        column = columns.pop()
        for row in by_column[column]:
            if row in under_rows:
                continue
            under_rows.add(row)
            mate = row_mate.get(row)
            if mate is not None and mate not in under_cols:
                under_cols.add(mate)
                columns.append(mate)

    def ordered(names: Sequence[str], chosen: set[str]) -> tuple[str, ...]:
        return tuple(name for name in names if name in chosen)

    return DulmageMendelsohn(
        over_rows=ordered(row_ids, over_rows),
        over_cols=ordered(column_ids, over_cols),
        under_rows=ordered(row_ids, under_rows),
        under_cols=ordered(column_ids, under_cols),
        square_rows=ordered(row_ids, set(row_ids) - over_rows - under_rows),
        square_cols=ordered(column_ids, set(column_ids) - over_cols - under_cols),
        structural_rank=len(pairs),
    )
