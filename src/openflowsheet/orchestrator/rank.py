"""Structural alias elimination of consistent-redundant rows. K03 specification §7, R-011.

K02 assembled the SYN-001 flowsheet exactly as its manifests declare it and found the result
over-determined: nine declared pressure rows over seven pressure columns, rank 7. A square
Newton cannot run on 46 inner rows and 44 inner unknowns, and blueprint §7.7 is explicit that a
regularized least-squares step is "numerical recovery" and "never permission to discard
equations". So the two dependent rows are removed **structurally, with a certificate**, and not
numerically.

**The rows are a graph.** Each declared pressure row is linear in the pressure columns with
coefficients `±1` and a constant: `P_a − P_b = 0`, or `P_a − P_spec = 0`. Nodes are the pressure
columns plus one node for the constant; each row is an edge. A row whose two nodes are *already
connected* closes a cycle and is therefore a linear combination of the rows on the tree path
between them. That is a structural fact about the declarations, decided before any number is
evaluated — no singular value, no threshold, no rank tolerance.

**The certificate is what makes it safe.** For each eliminated row `e` the path gives signs
`σ_k` and the identity `F_e(x) − Σ σ_k F_k(x) = m_e` must hold *for every* `x`. It is checked at
two states differing in every pressure coordinate: agreeing values witness the linearity, and
`|m_e| ≤ 1e-2 Pa` (ADR 0001 D6) witnesses that the redundancy is *consistent*. An inconsistent
one is `SPECIFICATION_CONFLICT` and the plan is not built — which is the right answer, because a
flowsheet whose declared pressures contradict each other has no solution to find.

**Eliminated is not discarded.** The rows stay in the assembled system, are evaluated at every
accepted iterate as part of the inner-consistency check, are listed on the plan with their
certificates, and K04 re-evaluates all of them. This is blueprint §7.2's "alias elimination",
done by the orchestrator, where the whole flowsheet is visible — which is why K02 was right to
refuse to do it inside a unit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

#: ADR 0001 D6's registered pressure tolerance: the bound on a consistent mismatch.
PRESSURE_TOLERANCE: Final = 1e-2
#: The linearity witness: two evaluations of the same constant must agree to `1e-9 x 1e5 Pa`.
LINEARITY_TOLERANCE: Final = 1e-9 * 1e5

#: The graph node standing for the constant term of a specification row.
CONST: Final = "<const>"


class SpecificationConflictError(ValueError):
    """`SPECIFICATION_CONFLICT`: a redundant row that is not consistent with the rows it repeats.

    The plan is not built. A flowsheet declaring both `P_feed = 100 kPa` and, through a chain of
    zero drops, `P_feed = 150 kPa` has no solution, and reporting that is more useful than
    factorizing something that averages them.
    """


class UnsupportedRankStructureError(ValueError):
    """`UNSUPPORTED_RANK_STRUCTURE`: the redundancy is real but not of the shape this policy reads.

    Three or more columns in a qualifying row, a coefficient that is not `±1`, or a block that is
    still not square afterwards. Generalizing is T01/T06's; guessing is nobody's.
    """


@dataclass(frozen=True)
class EliminatedRow:
    """One row removed, with the retained rows it equals and the certificate for that claim."""

    row_id: str
    equals: tuple[tuple[str, int], ...]
    constant_mismatch: float
    tolerance: float = PRESSURE_TOLERANCE

    def as_document(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "equals": [[name, sign] for name, sign in self.equals],
            "constant_mismatch": self.constant_mismatch,
            "tolerance": self.tolerance,
        }


@dataclass(frozen=True)
class AliasElimination:
    """The result: which rows stay, which go, and why each one that goes may."""

    retained_rows: tuple[str, ...]
    eliminated: tuple[EliminatedRow, ...]

    @property
    def eliminated_ids(self) -> frozenset[str]:
        return frozenset(row.row_id for row in self.eliminated)


class _Forest:
    """Union–find with the path needed to justify an elimination, not merely detect one."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}
        #: node -> list of (neighbour, row_id, sign when traversed node -> neighbour)
        self._edges: dict[str, list[tuple[str, str, int]]] = {}

    def add_node(self, node: str) -> None:
        self._parent.setdefault(node, node)
        self._edges.setdefault(node, [])

    def find(self, node: str) -> str:
        self.add_node(node)
        root = node
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[node] != root:
            self._parent[node], node = root, self._parent[node]
        return root

    def connected(self, a: str, b: str) -> bool:
        return self.find(a) == self.find(b)

    def link(self, positive: str, negative: str, row_id: str) -> None:
        """Add the retained edge for `F = x_positive − x_negative + g`."""
        self._edges[positive].append((negative, row_id, +1))
        self._edges[negative].append((positive, row_id, -1))
        self._parent[self.find(positive)] = self.find(negative)

    def path(self, start: str, goal: str) -> tuple[tuple[str, int], ...]:
        """The retained rows between two connected nodes, with their traversal signs."""
        stack: list[tuple[str, tuple[tuple[str, int], ...]]] = [(start, ())]
        seen = {start}
        while stack:
            node, taken = stack.pop()
            if node == goal:
                return taken
            for neighbour, row_id, sign in self._edges[node]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append((neighbour, (*taken, (row_id, sign))))
        raise UnsupportedRankStructureError(
            f"no path from {start!r} to {goal!r} in the retained forest, although the union-find "
            "reported them connected; the forest and the union-find disagree"
        )


def eliminate_alias_rows(
    *,
    row_ids: Sequence[str],
    coefficients: Mapping[str, Mapping[str, float]],
    column_kinds: Mapping[str, str],
    residuals: Sequence[Mapping[str, float]],
    eligible_kind: str = "pressure",
    pressure_tolerance: float = PRESSURE_TOLERANCE,
    linearity_tolerance: float = LINEARITY_TOLERANCE,
) -> AliasElimination:
    """Apply §7.2's algorithm. `residuals` are the row values at two differing states.

    `coefficients` is each row's Jacobian row by column id. The pattern is state-invariant for
    these rows (they are affine), which A30 asserts separately; this reads it once.
    """
    if len(residuals) < 2:
        raise ValueError(
            "the certificate needs two states: one value of a constant is not evidence that it "
            "is constant"
        )

    forest = _Forest()
    forest.add_node(CONST)
    retained: list[str] = []
    eliminated: list[EliminatedRow] = []

    for row_id in row_ids:
        row = {name: value for name, value in coefficients.get(row_id, {}).items() if value != 0.0}
        if not row or any(column_kinds.get(name) != eligible_kind for name in row):
            retained.append(row_id)
            continue

        offending = sorted(name for name, value in row.items() if abs(value) != 1.0)
        if offending:
            raise UnsupportedRankStructureError(
                f"row {row_id!r} is over {eligible_kind} columns but has coefficients that are "
                f"not ±1 at {offending}; this policy reads pressure *copies*, and a ratio or a "
                "scaled drop is T01/T06's to generalize"
            )
        if len(row) > 2:
            raise UnsupportedRankStructureError(
                f"row {row_id!r} touches {len(row)} {eligible_kind} columns {sorted(row)}; this "
                "policy reads two-node edges and a specification, not a general cycle"
            )
        # A copy is a *difference*. Two `+1` coefficients are a sum: `P_a + P_b − P_spec` would
        # otherwise take `P_a` as its positive node and the constant as its negative, and be
        # certified as `P_a − P_spec`, false at every state. The two-state witness below does
        # catch it — measured, the mismatch varies by the second pressure — but it catches it
        # *numerically*, and R-011's whole point is that this elimination is structural. T01's
        # review found the same gap in its own declaration-side rule (M4, register R-021), where
        # there is no witness to fall back on.
        if len(row) == 2 and sum(row.values()) != 0.0:
            raise UnsupportedRankStructureError(
                f"row {row_id!r} is over two {eligible_kind} columns {sorted(row)} whose "
                "coefficients do not cancel; a copy is a difference, and a sum is not one"
            )

        positive = next((name for name, value in row.items() if value > 0.0), CONST)
        negative = next((name for name, value in row.items() if value < 0.0), CONST)
        for node in (positive, negative):
            forest.add_node(node)

        if forest.connected(positive, negative):
            path = forest.path(positive, negative)

            # **Why two probe states are enough here, and would not be in general.** They
            # witness that the *mismatch* is constant; they say nothing about the linear part,
            # being two points on a line chosen to vary in one direction. What covers the
            # linear part is structural and has already been enforced above: every row on the
            # path has exactly two eligible columns with coefficients ±1, so the signed sum
            # along a path telescopes to the endpoints *identically*, and the combination
            # cannot differ from the row it certifies. An explicit `c_e == Σ σ_k c_k` check
            # was written here and removed: under those two guards it can never fail, and a
            # check that cannot fail reads as coverage it does not provide.
            # `test_a_path_of_two_node_edges_telescopes_exactly` holds the argument.
            # A policy that relaxed either guard — a ratio, a scaled drop, a general cycle —
            # would need that check back, which is why the reasoning is written down and not
            # merely relied on.
            mismatches = [
                values[row_id] - sum(sign * values[name] for name, sign in path)
                for values in residuals
            ]
            spread = max(mismatches) - min(mismatches)
            if spread > linearity_tolerance:
                raise UnsupportedRankStructureError(
                    f"row {row_id!r} is structurally redundant but its mismatch is not constant: "
                    f"{mismatches} over the probe states, spread {spread:.3e} above "
                    f"{linearity_tolerance:g}. The identity must hold for every state or it is "
                    "not an identity"
                )
            mismatch = mismatches[0]
            if abs(mismatch) > pressure_tolerance:
                raise SpecificationConflictError(
                    f"SPECIFICATION_CONFLICT: row {row_id!r} repeats "
                    f"{[(name, sign) for name, sign in path]} but disagrees with them by "
                    f"{mismatch:g}, beyond the registered {pressure_tolerance:g}. The declared "
                    "specifications contradict each other; there is no state satisfying both"
                )
            eliminated.append(
                EliminatedRow(
                    row_id=row_id,
                    equals=path,
                    constant_mismatch=mismatch,
                    tolerance=pressure_tolerance,
                )
            )
        else:
            forest.link(positive, negative, row_id)
            retained.append(row_id)

    return AliasElimination(retained_rows=tuple(retained), eliminated=tuple(eliminated))
