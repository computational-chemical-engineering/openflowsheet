"""K03 §5.3's released set `Z*` without recursion (R-786;
`docs/derivations/S10C-absent-component.md` §8.4, gate G-R8).

R-064 found `Z*` by a recursive augmenting search (Kuhn) and a fixed-point loop; a long chain of
closed rows (one absent component over many stages) raised `RecursionError` once the augmenting
path outgrew Python's recursion limit. R-786 keeps the name, signature, contract and result, and
replaces the algorithm: SciPy's iterative Hopcroft–Karp and a worklist over alternating paths.
The result cannot change — both compute the columns some maximum matching leaves uncovered
(Gallai–Edmonds) — and these tests check it:

- **Oracle (G-R8 1).** 2 000 seeded instances, `|Z₀|` 1–10, closed rows with a planted injective
  row → column assignment: `_released` equals the union of every tight `Z ⊆ Z₀`
  (`closed(Z) == |Z|`), found by enumeration, and that union is itself tight.
- **Old against new (G-R8 2).** 2 000 seeded instances, `|Z₀|` up to 300, including Hall
  violations, stored zeros, duplicate entries and `−0.0` residuals: identical tuples with
  R-064's implementation, copied verbatim below as `_released_r064`.
- **Long chains (G-R8 3).** 2 000 and 10 000 on-bound columns in one bidiagonal closed block,
  rows in stage order and reversed: every column released, where R-064 raised `RecursionError`.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from itertools import combinations
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest
import scipy.sparse as sp

from openflowsheet.numerics.newton import _released

# -- R-064's implementation, verbatim (the reference for G-R8 2) --------------------------------


def _released_r064(
    x: npt.NDArray[np.float64],
    opening: npt.NDArray[np.float64],
    lower: npt.NDArray[np.float64],
    residual: Sequence[float],
    jacobian: sp.csc_matrix,
) -> tuple[int, ...]:
    """§5.3 as amended (T05b ruling Q-S11 (b), R-064): the largest released set `Z*`, as indices.

    `Z₀` are the components exactly on a finite lower bound at the attempt's `opening` and at `x`.
    A set `Z ⊆ Z₀` is released when the rows closed on it — `F_r(x) == 0.0` exactly and every
    nonzero `J_{r,c}(x)` in a column of `Z` — number exactly `|Z|`; with `J` nonsingular the exact
    step on `Z` is then zero. The union of released sets is released, so `Z*` is unique. Found by
    a maximum matching of the closed rows into `Z₀`: a column is outside `Z*` exactly when an
    unmatched column is reachable from it through its matched row's support (the Dulmage–Mendelsohn
    over-determined part). The count is re-checked on the answer; a set that fails it (a singular
    `J`, which the factorization has just excluded) releases nothing."""
    on_bound = np.isfinite(lower) & (x == lower) & (opening == lower)
    columns = frozenset(int(index) for index in np.flatnonzero(on_bound))
    if not columns:
        return ()
    rows = sp.csr_matrix(jacobian)
    supports: list[tuple[int, ...]] = []
    for row, value in enumerate(residual):
        if value != 0.0:
            continue
        start, end = rows.indptr[row], rows.indptr[row + 1]
        support = tuple(
            int(column)
            for column, entry in zip(rows.indices[start:end], rows.data[start:end], strict=True)
            if entry != 0.0
        )
        if support and columns.issuperset(support):
            supports.append(tuple(sorted(support)))
    matched: dict[int, int] = {}  # column -> row (an index into `supports`)

    def augment(row: int, seen: set[int]) -> bool:
        for column in supports[row]:
            if column in seen:
                continue
            seen.add(column)
            if column not in matched or augment(matched[column], seen):
                matched[column] = row
                return True
        return False

    for row in range(len(supports)):
        augment(row, set())
    outside = set(columns) - set(matched)
    grew = True
    while grew:
        grew = False
        for column, row in matched.items():
            if column not in outside and not outside.isdisjoint(supports[row]):
                outside.add(column)
                grew = True
    released = columns - outside
    closed = sum(1 for support in supports if released.issuperset(support))
    if not released or closed != len(released):
        return ()
    return tuple(sorted(released))


# -- instances ------------------------------------------------------------------------------------

Entry = tuple[int, int, float]  # (row, column, value)


def _bounds(
    rng: np.random.Generator, n: int, z0: Sequence[int]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """`x`, `opening`, `lower`: the `z0` columns at `+0.0` on a finite bound at both; every other
    column misses one condition (off its bound, an infinite bound, or open at the opening)."""
    x = np.zeros(n)
    opening = np.zeros(n)
    lower = np.zeros(n)
    members = set(z0)
    for column in range(n):
        if column in members:
            continue
        kind = rng.integers(3)
        if kind == 0:
            x[column] = 1.0 + rng.random()
        elif kind == 1:
            lower[column] = -np.inf
        else:
            opening[column] = 0.5
    return x, opening, lower


def _jacobian(entries: Sequence[Entry], m: int, n: int) -> sp.csc_matrix:
    """CSC with every entry stored as given: explicit zeros and duplicates kept."""
    order = sorted(range(len(entries)), key=lambda e: (entries[e][1], entries[e][0]))
    indices = np.array([entries[e][0] for e in order], dtype=np.int32)
    data = np.array([entries[e][2] for e in order], dtype=np.float64)
    counts = np.bincount([entries[e][1] for e in order], minlength=n)
    indptr = np.concatenate(([0], np.cumsum(counts))).astype(np.int32)
    return sp.csc_matrix((data, indices, indptr), shape=(m, n))


def _value(rng: np.random.Generator) -> float:
    return float(rng.choice((-1.0, 1.0)) * 10.0 ** rng.uniform(-8.0, 3.0))


def _instance(
    rng: np.random.Generator, size: int, *, planted: bool, density: float
) -> tuple[Any, ...]:
    """One `_released` input with `|Z₀| = size`: closed rows (planted, or with random supports
    inside a small subset of `Z₀` so Hall's condition can fail), open rows of every kind, stored
    zeros, duplicate entries, `−0.0` residuals. Returns `(x, opening, lower, residual, J, z0,
    closed_supports)`, the last the closed rows' nonzero supports as built (for the oracle)."""
    extra = int(rng.integers(0, 6))
    n = size + extra
    z0 = sorted(int(c) for c in rng.choice(n, size=size, replace=False))
    others = [c for c in range(n) if c not in set(z0)]
    rows: list[tuple[float, list[tuple[int, float]]]] = []
    closed_supports: list[frozenset[int]] = []
    if planted:
        count = int(rng.integers(0, size + 1))
        target = rng.permutation(size)[:count]
        for i in range(count):
            support = {z0[int(target[i])]}
            support |= {c for c in z0 if rng.random() < density}
            rows.append((0.0, [(c, _value(rng)) for c in sorted(support)]))
            closed_supports.append(frozenset(support))
    else:
        pool = [
            z0[int(i)] for i in rng.choice(size, size=int(rng.integers(1, size + 1)), replace=False)
        ]
        count = int(rng.integers(0, size + 3))
        for _ in range(count):
            width = int(rng.integers(1, min(len(pool), 4) + 1))
            support = {pool[int(i)] for i in rng.choice(len(pool), size=width, replace=False)}
            support |= {c for c in z0 if rng.random() < density}
            rows.append((0.0, [(c, _value(rng)) for c in sorted(support)]))
            closed_supports.append(frozenset(support))
    for _ in range(int(rng.integers(1, 4))):
        kind = int(rng.integers(4)) if others else int(rng.choice((0, 2, 3)))
        support = {c for c in z0 if rng.random() < density} or {z0[int(rng.integers(size))]}
        if kind == 0:  # a nonzero residual
            rows.append((_value(rng), [(c, _value(rng)) for c in sorted(support)]))
        elif kind == 1:  # residual zero, an entry outside Z₀
            outside = others[int(rng.integers(len(others)))]
            rows.append((0.0, [(c, _value(rng)) for c in sorted(support | {outside})]))
        elif kind == 2:  # residual zero, only stored zeros
            rows.append((0.0, [(c, 0.0) for c in sorted(support)]))
        else:  # a NaN residual
            rows.append((float("nan"), [(c, _value(rng)) for c in sorted(support)]))
    entries: list[Entry] = []
    residual: list[float] = []
    for r, row in enumerate(rng.permutation(len(rows))):
        value, row_entries = rows[int(row)]
        residual.append(-0.0 if value == 0.0 and rng.random() < 0.3 else value)
        entries.extend((r, c, v) for c, v in row_entries)
        if rng.random() < 0.3:  # a stored zero anywhere, outside Z₀ included
            entries.append((r, int(rng.integers(n)), 0.0))
        if row_entries and rng.random() < 0.2:  # a duplicate, sometimes cancelling
            c, v = row_entries[int(rng.integers(len(row_entries)))]
            if v == 0.0:  # a stored zero's duplicate stays zero: the row's support is unchanged
                entries.append((r, c, 0.0))
            else:
                entries.append((r, c, -v if rng.random() < 0.5 else _value(rng)))
    m = len(rows)
    x, opening, lower = _bounds(rng, n, z0)
    jacobian = _jacobian(entries, m, n)
    return x, opening, lower, residual, jacobian, z0, closed_supports


# -- G-R8 1: against enumeration ------------------------------------------------------------------


def _tight_union(z0: Sequence[int], supports: Sequence[frozenset[int]]) -> tuple[int, ...]:
    """The union of every nonempty `Z ⊆ Z₀` with `closed(Z) == |Z|`, by enumeration; asserts the
    union is tight itself (true when the closed rows match injectively into `Z₀`)."""
    union: set[int] = set()
    for width in range(1, len(z0) + 1):
        for subset in combinations(z0, width):
            members = set(subset)
            if sum(1 for s in supports if s <= members) == width:
                union |= members
    if union:
        assert sum(1 for s in supports if s <= union) == len(union)
    return tuple(sorted(union))


def test_g_r8_1_released_equals_the_union_of_tight_sets() -> None:
    rng = np.random.default_rng(786_1)
    for case in range(2000):
        size = int(rng.integers(1, 11))
        density = float(rng.choice((0.1, 0.3, 0.6)))
        x, opening, lower, residual, jacobian, z0, supports = _instance(
            rng, size, planted=True, density=density
        )
        assert _released(x, opening, lower, residual, jacobian) == _tight_union(z0, supports), case


# -- G-R8 2: against R-064 ------------------------------------------------------------------------


def test_g_r8_2_identical_to_r064_on_2000_instances() -> None:
    rng = np.random.default_rng(786_2)
    released_nonempty = 0
    for case in range(2000):
        size = int(np.exp(rng.uniform(0.0, np.log(300.0))) + 0.5)
        size = min(max(size, 1), 300)
        density = float(rng.choice((0.1, 0.3, 0.6))) * min(1.0, 10.0 / size)
        x, opening, lower, residual, jacobian, _, _ = _instance(
            rng, size, planted=bool(rng.random() < 0.5), density=density
        )
        new = _released(x, opening, lower, residual, jacobian)
        assert new == _released_r064(x, opening, lower, residual, jacobian), case
        assert all(type(index) is int for index in new)
        released_nonempty += bool(new)
    assert 200 < released_nonempty < 1800  # both outcomes are well exercised


# -- G-R8 3: long chains --------------------------------------------------------------------------


def _chain(size: int, *, reversed_rows: bool) -> tuple[Any, ...]:
    """`size` on-bound columns and `size` closed rows, row `i` reading columns `i − 1` and `i`
    (one absent component's flows along the stages); rows stored in stage order or reversed."""
    order = list(range(size))[::-1] if reversed_rows else list(range(size))
    entries: list[Entry] = []
    for r, i in enumerate(order):
        entries.append((r, i, 1.0))
        if i > 0:
            entries.append((r, i - 1, -0.5))
    x = np.zeros(size)
    return x, x.copy(), x.copy(), [0.0] * size, _jacobian(entries, size, size)


@pytest.mark.parametrize("reversed_rows", [False, True])
def test_g_r8_3_a_2000_column_chain_releases_every_column(
    reversed_rows: bool, record_property: Any
) -> None:
    args = _chain(2000, reversed_rows=reversed_rows)
    start = time.perf_counter()
    assert _released(*args) == tuple(range(2000))
    record_property("seconds", time.perf_counter() - start)


def test_g_r8_3_r064_raised_recursion_error_on_the_chain() -> None:
    """The motivating failure: R-064's recursive search on the 2 000-column chain, stage order."""
    with pytest.raises(RecursionError):
        _released_r064(*_chain(2000, reversed_rows=False))


def test_g_r8_3_a_10000_column_chain_completes(record_property: Any) -> None:
    args = _chain(10_000, reversed_rows=False)
    start = time.perf_counter()
    assert _released(*args) == tuple(range(10_000))
    record_property("seconds", time.perf_counter() - start)
