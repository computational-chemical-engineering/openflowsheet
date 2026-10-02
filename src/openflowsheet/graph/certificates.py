"""The affine-copy certificate, issued from the declaration and the parameters.

T01 specification §8.2. This is K03 §7.2's algorithm (register R-011) moved off the Jacobian and
onto the declaration trace, which is what lets it run at *validation*, before anything is
compiled or solved and with no state to run at.

**The shape it reads.** A row of a certifiable kind that is affine with literal coefficients, all
exactly `+/-1`, over at most two columns of that kind, and — when there are two — with the
coefficients *cancelling*: a copy is a difference, never a sum.

Those rows form a graph whose nodes are the columns plus one node for the constant; each row is an
edge. Visiting in declaration order, a
row whose two endpoints are *already connected* closes a cycle and is therefore a signed sum of
the rows on the tree path between them. Because every row on that path has exactly two `+/-1`
columns, the variable parts telescope **identically** — so the identity `F_e - sum s_k F_k = m_e`
holds at every state, and `m_e` is the signed sum of the rows' constants, a function of the
parameters alone. K03 needed two evaluated states to witness that; the declaration does not.

**Consistent is not the same as redundant.** `|m_e| <= tau` makes the redundancy *consistent* and
the row certified; beyond it the declared specifications contradict each other and there is no
state satisfying both, which is `SPECIFICATION_CONFLICT` and is a finding about the revision, not
a failure of the tool.

**Eliminated is not discarded** (blueprint §7.7). A certified row is removed from the closure
*count* only; it stays in the residual, is evaluated by the solver and re-evaluated by the
verifier. The report says so in its own words.

A row of a certifiable kind that is affine but has a coefficient other than `+/-1`, or more than
two columns, is `uncertified_affine`: retained, listed, never silently certified or dropped. K03
refuses there with `UNSUPPORTED_RANK_STRUCTURE`; T01 reports the row and lets the closure rule
decide from the graph.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from openflowsheet.compile.spec import QuantityKind
from openflowsheet.graph.trace import Declaration

__all__ = [
    "CERTIFIABLE_KINDS",
    "CONST",
    "Certificate",
    "CertifiedRedundancy",
    "certify",
]

#: The graph node standing for the constant term of a specification row.
CONST: Final = "<const>"

#: ADR 0001 D6's registered tolerances, by the kind of the rows a certificate is issued over.
#: There is no `heat_rate` entry: D6 registers none, so a duty alias is `uncertified_affine`
#: rather than certified against an invented bound (specification §19 finding 9).
CERTIFIABLE_KINDS: Final[Mapping[QuantityKind, float]] = {
    "pressure": 1e-2,
    "temperature": 1e-6,
}


@dataclass(frozen=True)
class Certificate:
    """One certified redundant row, with the identity that certifies it."""

    row_id: str
    #: The retained rows it repeats, as `(row_id, sign)`. An unordered *set* of signed rows: a
    #: traversal order is not part of the identity (specification §19 finding 5).
    equals: tuple[tuple[str, int], ...]
    constant_mismatch: float
    tolerance: float
    kind: QuantityKind

    @property
    def consistent(self) -> bool:
        return abs(self.constant_mismatch) <= self.tolerance

    def as_document(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "equals": [[row, sign] for row, sign in self.equals],
            "constant_mismatch": self.constant_mismatch,
            "tolerance": self.tolerance,
            "kind": self.kind,
            "consistent": self.consistent,
        }


@dataclass(frozen=True)
class CertifiedRedundancy:
    """Everything the certificate pass found: what it certified and what it refused to."""

    certificates: tuple[Certificate, ...]
    uncertified_affine_rows: tuple[str, ...]

    @property
    def certified_rows(self) -> tuple[str, ...]:
        """The rows that are actually certified: consistent ones only.

        A row whose mismatch exceeds its tolerance has an *identity* but not a certificate — it is
        a `SPECIFICATION_CONFLICT`, and §8.2 only admits a row to `E` when `|m_e| <= tau`. Listing
        it as certified would be doubly wrong: a reader would see it as discharged, and the
        closure count would quietly remove a row nothing justifies removing.
        """
        return tuple(
            certificate.row_id for certificate in self.certificates if certificate.consistent
        )

    @property
    def conflicts(self) -> tuple[Certificate, ...]:
        return tuple(certificate for certificate in self.certificates if not certificate.consistent)


class _Forest:
    """A spanning forest with signed paths: union-find that can report *how* two nodes connect."""

    def __init__(self) -> None:
        self._parent: dict[str, str | None] = {}
        #: For a node, the edge to its parent as `(row_id, sign)`, where `sign` is `+1` when the
        #: row reads `parent - node` and `-1` when it reads `node - parent`.
        self._edge: dict[str, tuple[str, int]] = {}

    def add(self, node: str) -> None:
        self._parent.setdefault(node, None)

    def _root_path(self, node: str) -> list[str]:
        path = [node]
        while self._parent[path[-1]] is not None:
            parent = self._parent[path[-1]]
            assert parent is not None
            path.append(parent)
        return path

    def connected(self, left: str, right: str) -> bool:
        return self._root_path(left)[-1] == self._root_path(right)[-1]

    def link(self, positive: str, negative: str, row_id: str) -> None:
        """Attach `negative`'s tree under `positive`, re-rooting it so parents stay acyclic."""
        chain = self._root_path(negative)
        for index in range(len(chain) - 1, 0, -1):
            child, parent = chain[index - 1], chain[index]
            row, sign = self._edge[child]
            self._parent[parent] = child
            self._edge[parent] = (row, -sign)
        self._parent[negative] = positive
        self._edge[negative] = (row_id, 1)

    def path(self, positive: str, negative: str) -> tuple[tuple[str, int], ...]:
        """The signed rows on the tree path: their signed sum equals `positive - negative`."""
        left, right = self._root_path(positive), self._root_path(negative)
        common = set(right)
        meeting = next(node for node in left if node in common)

        signed: dict[str, int] = {}

        def walk(chain: Sequence[str], sign: int) -> None:
            for node in chain:
                if node == meeting:
                    return
                row, edge_sign = self._edge[node]
                signed[row] = signed.get(row, 0) + sign * edge_sign

        walk(left, -1)
        walk(right, 1)
        return tuple(sorted((row, sign) for row, sign in signed.items() if sign != 0))


def certify(
    declaration: Declaration, *, row_ids: Sequence[str] | None = None
) -> CertifiedRedundancy:
    """Apply §8.2 to every certifiable kind independently, in declaration order."""
    considered = tuple(row_ids) if row_ids is not None else declaration.row_ids
    certificates: list[Certificate] = []
    uncertified: list[str] = []

    for kind, tolerance in CERTIFIABLE_KINDS.items():
        forest = _Forest()
        forest.add(CONST)
        for row_id in considered:
            row = declaration.rows[row_id]
            if row.kind != kind:
                continue
            if row.coefficients is None:
                uncertified.append(row_id)
                continue
            over = {
                name: value
                for name, value in row.coefficients.items()
                if declaration.column_kinds.get(name) == kind
            }
            if len(over) != len(row.coefficients) or not over:
                uncertified.append(row_id)
                continue
            if len(over) > 2 or any(abs(value) != 1.0 for value in over.values()):
                uncertified.append(row_id)
                continue
            # A *copy* is a difference. `P1 - P2` and `P1 - s` are copies; `P1 + P2 - s` is a
            # sum, and treating it as an edge between `P1` and the constant node certifies it as
            # equal to `P1 - s`, which is false at every state. The Fable review of T01 measured
            # exactly that (M4) and it was wrong in three places at once: here, the specification's
            # §8.2 wording, and the reference generator. Requiring the two coefficients to cancel
            # is what makes the telescoping argument true.
            if len(over) == 2 and sum(over.values()) != 0.0:
                uncertified.append(row_id)
                continue

            positive = next((name for name, value in over.items() if value > 0.0), CONST)
            negative = next((name for name, value in over.items() if value < 0.0), CONST)
            forest.add(positive)
            forest.add(negative)

            if not forest.connected(positive, negative):
                forest.link(positive, negative, row_id)
                continue

            equals = forest.path(positive, negative)
            mismatch = row.constant(declaration.parameters) - sum(
                sign * declaration.rows[name].constant(declaration.parameters)
                for name, sign in equals
            )
            certificates.append(
                Certificate(
                    row_id=row_id,
                    equals=equals,
                    constant_mismatch=mismatch,
                    tolerance=tolerance,
                    kind=kind,
                )
            )

    order = {row_id: index for index, row_id in enumerate(considered)}
    return CertifiedRedundancy(
        certificates=tuple(sorted(certificates, key=lambda entry: order[entry.row_id])),
        uncertified_affine_rows=tuple(sorted(set(uncertified), key=lambda name: order[name])),
    )
