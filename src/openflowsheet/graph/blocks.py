"""Strongly connected components, the block-triangular form, and its canonical order.

T01 specification §7. On a square, perfectly matched incidence, row `r` **depends on** row `r'`
when the column matched to `r'` appears in `r`. The strongly connected components of that digraph
are the diagonal blocks and the condensation is acyclic: solving the blocks in a topological order
solves the system.

**The blocks are unique; their order is not.** The fine Dulmage-Mendelsohn decomposition is a
theorem — the block set, the sizes and the dependency DAG do not depend on which perfect matching
produced them (A12 proves it on twenty seeded permutations). The *sequence* is a choice, and it
is made canonical here because gate G05 compares structural artifacts between two CI
architectures on every push and "whatever the topological sort happened to emit" would not
survive that.

**The rule (§7.2).** Among the blocks whose predecessors are all placed, take the one whose first
row has the least declaration index. `BTF-1` registers a four-block case where a plain FIFO queue
places `d` before `c`; this rule places `a, b, c, d`. Totality: at every step the ready set is
finite and non-empty (the condensation is acyclic) and the key is a distinct integer per block.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = ["Block", "BlockTriangularForm", "block_triangular_form"]


@dataclass(frozen=True)
class Block:
    """One diagonal block: its rows, the columns matched to them, and what it reads."""

    rows: tuple[str, ...]
    cols: tuple[str, ...]
    #: Indices of the blocks this one depends on, in the canonical order. Ancestors are not
    #: expanded here: the transitive closure is `BlockTriangularForm.ancestors_of`.
    depends_on: tuple[int, ...]

    @property
    def size(self) -> int:
        return len(self.rows)

    def as_document(self) -> dict[str, object]:
        return {
            "rows": list(self.rows),
            "cols": list(self.cols),
            "size": self.size,
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class BlockTriangularForm:
    """The blocks in canonical order, with the metrics blueprint §7.2 asks for."""

    blocks: tuple[Block, ...]

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def block_sizes_sorted(self) -> tuple[int, ...]:
        return tuple(sorted((block.size for block in self.blocks), reverse=True))

    @property
    def largest_block_fraction(self) -> float:
        """The largest block as a fraction of the system. One IEEE division of small integers."""
        total = sum(block.size for block in self.blocks)
        return 0.0 if total == 0 else max(block.size for block in self.blocks) / total

    def index_of_row(self, row_id: str) -> int | None:
        for index, block in enumerate(self.blocks):
            if row_id in block.rows:
                return index
        return None

    def index_of_column(self, column_id: str) -> int | None:
        for index, block in enumerate(self.blocks):
            if column_id in block.cols:
                return index
        return None

    def ancestors_of(self, indices: Sequence[int]) -> frozenset[int]:
        """`indices` and everything they transitively depend on: what must be solved first."""
        seen: set[int] = set()
        stack = list(indices)
        while stack:
            index = stack.pop()
            if index in seen:
                continue
            seen.add(index)
            stack.extend(self.blocks[index].depends_on)
        return frozenset(seen)

    def as_document(self) -> dict[str, object]:
        return {
            "blocks": [block.as_document() for block in self.blocks],
            "block_count": self.block_count,
            "block_sizes_sorted": list(self.block_sizes_sorted),
            "largest_block_fraction": self.largest_block_fraction,
        }


def _components(
    row_ids: Sequence[str], dependencies: Mapping[str, frozenset[str]]
) -> list[list[str]]:
    """Tarjan's strongly connected components, iteratively, in declaration order of entry."""
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    found: list[list[str]] = []
    counter = 0

    for start in row_ids:
        if start in index_of:
            continue
        work: list[tuple[str, list[str]]] = [(start, sorted(dependencies[start]))]
        index_of[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)

        while work:
            node, pending = work[-1]
            if pending:
                target = pending.pop()
                if target not in index_of:
                    index_of[target] = low[target] = counter
                    counter += 1
                    stack.append(target)
                    on_stack.add(target)
                    work.append((target, sorted(dependencies[target])))
                elif target in on_stack:
                    low[node] = min(low[node], index_of[target])
                continue

            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index_of[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                found.append(component)
    return found


def block_triangular_form(
    row_ids: Sequence[str],
    incidence: Mapping[str, frozenset[str]],
    matching: Mapping[str, str],
) -> BlockTriangularForm:
    """§7's decomposition of a square, perfectly matched system.

    `matching` is `column -> row` and must cover every row exactly once; a system that is not
    perfectly matched has no block-triangular form and this refuses rather than producing one for
    part of it.
    """
    order = {row_id: index for index, row_id in enumerate(row_ids)}
    column_of = {row: column for column, row in matching.items()}
    missing = [row_id for row_id in row_ids if row_id not in column_of]
    if missing:
        raise ValueError(
            f"the block-triangular form needs a perfect matching; {len(missing)} rows are "
            f"unmatched, first {missing[0]!r}"
        )

    row_of_column = dict(matching)
    dependencies = {
        row_id: frozenset(
            row_of_column[column]
            for column in incidence[row_id]
            if column in row_of_column and row_of_column[column] != row_id
        )
        for row_id in row_ids
    }

    components = _components(list(row_ids), dependencies)
    membership: dict[str, int] = {}
    grouped: list[list[str]] = []
    for component in components:
        rows = sorted(component, key=lambda name: order[name])
        for row_id in rows:
            membership[row_id] = len(grouped)
        grouped.append(rows)

    raw_edges = {
        index: frozenset(
            membership[target]
            for row_id in rows
            for target in dependencies[row_id]
            if membership[target] != index
        )
        for index, rows in enumerate(grouped)
    }

    # §7.2's canonical order: of the blocks whose predecessors are all placed, the one whose first
    # row has the least declaration index. Not a FIFO queue -- `BTF-1` distinguishes them.
    remaining = {index: set(edges) for index, edges in raw_edges.items()}
    placed: list[int] = []
    while remaining:
        ready = [index for index, waiting in remaining.items() if not waiting]
        if not ready:  # pragma: no cover - the condensation of an SCC digraph is acyclic
            raise ValueError("the block condensation is cyclic, which cannot happen")
        chosen = min(ready, key=lambda index: order[grouped[index][0]])
        placed.append(chosen)
        del remaining[chosen]
        for waiting in remaining.values():
            waiting.discard(chosen)

    position = {old: new for new, old in enumerate(placed)}
    blocks = tuple(
        Block(
            rows=tuple(grouped[old]),
            cols=tuple(column_of[row_id] for row_id in grouped[old]),
            depends_on=tuple(sorted(position[target] for target in raw_edges[old])),
        )
        for old in placed
    )
    return BlockTriangularForm(blocks=blocks)
