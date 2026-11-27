"""Conserved bases in exact rational arithmetic (ADR 0062 D3; foundation rulings Q3.R1, R4, R5, R7).

A connection carries amounts `b = A n_s` over declared groups g, with the integer content matrix A
(`A[g][s]`: units of g in true species s), relative to the fast-reaction set R of a method and the
species charges z. Everything here is decided exactly, in `fractions.Fraction`, with no tolerance
but Q3.R7's one stated bound on the recorded group molar masses:

- `check_basis`: Q3.R1 (i) `A R = 0`; (ii) `ker A ∩ ker zᵀ = span R`; (iii) the declaration admits
  a non-negative content matrix (else the limitation `species_basis_not_monotone`); the full row
  rank of A (else `species_basis_redundant`, Q3.R7); and Q3.R4's charge row ζ (`zᵀ = ζᵀA`) when
  one exists.
- `group_molar_masses`: Q3.R7's (M_g, μ) solving `Aᵀ M_g + μ z = M` on the first independent
  species in declaration order, rounded once, and the species that miss the 4ε bound
  (`molar_mass_inconsistent`).
- `group_amounts`, `negative_groups`: `b = A n_s` on doubles in a fixed order, and the groups a
  state would make negative (`group_amount_negative`, an invalid trial state, never clipped).
- `boundary`: Q3.R5 (Amendment 2): whether a consumer's basis evaluates a producer's stream, its
  projection Π, the unique integer conversion C (`b′ = C b`) and the structural limitations;
  `former_boundary_rule` is the rule Amendment 2 replaced (R′ ⊇ R with S ⊆ S′), kept as Q3.A6's
  control.

The typed refusals and their parameters are the revision validator's (F2-WO4); this module returns
the facts they are decided on.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

__all__ = [
    "EPSILON",
    "BasisCheck",
    "Boundary",
    "GroupMasses",
    "Limitation",
    "SpeciesBasis",
    "boundary",
    "check_basis",
    "former_boundary_rule",
    "group_amounts",
    "group_molar_masses",
    "negative_groups",
]

#: Q3.R7's ε, the binary64 unit roundoff doubled (2⁻⁵²), exactly.
EPSILON: Final = Fraction(1, 2**52)

Vector = tuple[Fraction, ...]
Matrix = tuple[Vector, ...]


@dataclass(frozen=True, slots=True)
class SpeciesBasis:
    """(S, A, z, R) of Q3.R1: true species, groups, content, charges and fast reactions.

    `content[g][s]` is A (one row per group, one column per species, integers); `charges[s]` is z;
    each of `reactions` is one fast reaction's stoichiometric vector over `species` (rationals,
    either sign convention). The true preset is `SpeciesBasis.true_basis`: A = I, R = ∅ (Q3.R2).
    """

    species: tuple[str, ...]
    groups: tuple[str, ...]
    content: tuple[tuple[int, ...], ...]
    charges: tuple[int, ...]
    reactions: tuple[tuple[Fraction, ...], ...] = ()

    def __post_init__(self) -> None:
        width = len(self.species)
        if len(set(self.species)) != width or len(set(self.groups)) != len(self.groups):
            raise ValueError("species and groups must be distinct")
        if len(self.content) != len(self.groups) or len(self.charges) != width:
            raise ValueError("content needs one row per group and charges one entry per species")
        if any(len(row) != width for row in (*self.content, *self.reactions)):
            raise ValueError("every content row and reaction needs one entry per species")

    @classmethod
    def true_basis(cls, species: Sequence[str], charges: Sequence[int]) -> SpeciesBasis:
        """Q3.R2's true preset: one group per species (its own id), A = I, R = ∅."""
        width = len(species)
        identity = tuple(tuple(int(g == s) for s in range(width)) for g in range(width))
        return cls(tuple(species), tuple(species), identity, tuple(charges))


@dataclass(frozen=True, slots=True)
class BasisCheck:
    """Q3.R1 and Q3.R7 decided for one `SpeciesBasis` (exact; no tolerance)."""

    #: (i) A R = 0: every fast reaction conserves every group.
    reactions_conserve_groups: bool
    #: dim(ker A ∩ ker zᵀ), the number of reaction invariants b leaves free.
    invariant_dimension: int
    #: (ii) ker A ∩ ker zᵀ = span R: on electroneutral compositions b fixes the speciated state.
    invariants_fixed: bool
    #: (iii) some A + Λzᵀ ≥ 0 (one rational λ per group row), so b ≥ 0 on every electroneutral
    #: n_s ≥ 0; False carries `species_basis_not_monotone`.
    monotone: bool
    #: Q3.R7: A has full row rank (else `species_basis_redundant`).
    full_row_rank: bool
    #: Q3.R4: ζ with zᵀ = ζᵀA (exact), or None (neutral groups: no charge row exists).
    charge_row: Vector | None

    @property
    def valid(self) -> bool:
        """Q3.R1 (i) and (ii) with Q3.R7's rank: the definition is valid against the method; (iii)
        is a recorded limitation, not a refusal."""
        return self.reactions_conserve_groups and self.invariants_fixed and self.full_row_rank


@dataclass(frozen=True, slots=True)
class GroupMasses:
    """Q3.R7's group molar masses, each rounded once from its exact value."""

    #: M_g per group, binary64, kg/mol.
    group_masses: tuple[float, ...]
    #: μ, binary64 (exactly 0.0 when zᵀ is in A's row space).
    mu: float
    #: The species whose equation decided (M_g, μ), in declaration order.
    deciding_species: tuple[str, ...]
    #: The other species that miss |M_s − (Aᵀ M_g + μ z)_s| ≤ 4ε(M_s + Σ_g |A_gs M_g| + |μ z_s|),
    #: in declaration order (`molar_mass_inconsistent(<S>, <species>)`).
    inconsistent: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Limitation:
    """A structural limitation of a boundary (Q3.R5): `code(subject)`; the method id is the
    caller's (`solid_candidate_dropped(<method>, <phase>)`, `species_dropped(<method>, <species>)`,
    `species_basis_not_monotone`)."""

    code: str
    subject: str


@dataclass(frozen=True, slots=True)
class Boundary:
    """Q3.R5's verdict for one producer stream and one consumer basis."""

    admitted: bool
    #: Π e_s over the consumer's species, for each producer species not in the consumer
    #: (`species`, in producer order); empty when refused before Π was found.
    projection: tuple[tuple[str, tuple[int, ...]], ...]
    #: The unique integer C with C A = A′ Π (consumer groups × producer groups), or None.
    conversion: tuple[tuple[int, ...], ...] | None
    limitations: tuple[Limitation, ...]
    #: Why a refused boundary was refused (empty when admitted).
    reason: str = ""


# -- exact linear algebra ---------------------------------------------------------------------


def _matrix(rows: Sequence[Sequence[int | Fraction]]) -> Matrix:
    return tuple(tuple(Fraction(entry) for entry in row) for row in rows)


def _echelon(rows: Matrix, width: int) -> tuple[list[list[Fraction]], list[int]]:
    """The reduced row echelon form of `rows` (`width` columns) and its pivot columns."""
    work = [list(row) for row in rows]
    pivots: list[int] = []
    rank = 0
    for column in range(width):
        found = next((i for i in range(rank, len(work)) if work[i][column] != 0), None)
        if found is None:
            continue
        work[rank], work[found] = work[found], work[rank]
        lead = work[rank][column]
        work[rank] = [entry / lead for entry in work[rank]]
        for i in range(len(work)):
            if i != rank and work[i][column] != 0:
                factor = work[i][column]
                work[i] = [a - factor * b for a, b in zip(work[i], work[rank], strict=True)]
        pivots.append(column)
        rank += 1
    return work[:rank], pivots


def _rank(rows: Matrix, width: int) -> int:
    return len(_echelon(rows, width)[1])


def _transpose(rows: Matrix, width: int) -> Matrix:
    return tuple(tuple(row[j] for row in rows) for j in range(width))


def _null_space(rows: Matrix, width: int) -> list[Vector]:
    """A basis of {x : rows · x = 0}."""
    reduced, pivots = _echelon(rows, width)
    basis = []
    for free in (j for j in range(width) if j not in pivots):
        vector = [Fraction(0)] * width
        vector[free] = Fraction(1)
        for row, pivot in zip(reduced, pivots, strict=True):
            vector[pivot] = -row[free]
        basis.append(tuple(vector))
    return basis


def _solve(rows: Matrix, width: int, target: Vector) -> Vector | None:
    """The particular solution x of `rows · x = target` with every free coordinate 0, or None."""
    augmented = tuple((*row, value) for row, value in zip(rows, target, strict=True))
    reduced, pivots = _echelon(augmented, width + 1)
    if pivots and pivots[-1] == width:
        return None
    solution = [Fraction(0)] * width
    for row, pivot in zip(reduced, pivots, strict=True):
        solution[pivot] = row[width]
    return tuple(solution)


def _dot(left: Sequence[Fraction], right: Sequence[Fraction]) -> Fraction:
    return sum((a * b for a, b in zip(left, right, strict=True)), Fraction(0))


def _row_admits_nonnegative_shift(row: Sequence[int], charges: Sequence[int]) -> bool:
    """Whether some rational λ makes `row + λ z` ≥ 0 entrywise: an interval intersection."""
    low: Fraction | None = None
    high: Fraction | None = None
    for entry, charge in zip(row, charges, strict=True):
        if charge == 0:
            if entry < 0:
                return False
            continue
        bound = Fraction(-entry, charge)
        if charge > 0:
            low = bound if low is None else max(low, bound)
        else:
            high = bound if high is None else min(high, bound)
    return low is None or high is None or low <= high


# -- Q3.R1, R4, R7 ----------------------------------------------------------------------------


def check_basis(basis: SpeciesBasis) -> BasisCheck:
    """Q3.R1 (i)–(iii), Q3.R7's rank and Q3.R4's charge row, exactly."""
    width = len(basis.species)
    content = _matrix(basis.content)
    charges = tuple(Fraction(z) for z in basis.charges)
    reactions = _matrix(basis.reactions)
    conserve = all(_dot(row, reaction) == 0 for row in content for reaction in reactions)
    invariants = _null_space((*content, charges), width)
    reaction_rank = _rank(reactions, width)
    in_invariants = all(
        _dot(row, reaction) == 0 for row in (*content, charges) for reaction in reactions
    )
    fixed = in_invariants and reaction_rank == len(invariants)
    monotone = all(_row_admits_nonnegative_shift(row, basis.charges) for row in basis.content)
    full = _rank(content, width) == len(basis.groups)
    zeta = _solve(_transpose(content, width), len(basis.groups), charges) if basis.groups else None
    return BasisCheck(conserve, len(invariants), fixed, monotone, full, zeta)


def _independent_rows(rows: Matrix, width: int, wanted: int) -> list[int]:
    """The first `wanted` rows, in order, each independent of those taken before it."""
    taken: list[int] = []
    for index in range(len(rows)):
        if _rank(tuple(rows[i] for i in (*taken, index)), width) == len(taken) + 1:
            taken.append(index)
            if len(taken) == wanted:
                break
    return taken


def group_molar_masses(basis: SpeciesBasis, masses: Sequence[float]) -> GroupMasses:
    """Q3.R7: (M_g, μ) solving `Aᵀ M_g + μ z = M` exactly on the record doubles `masses` (one per
    species, kg/mol) at the first independent species in declaration order, each rounded once;
    μ = 0 when zᵀ is in A's row space. Every other species is checked against the 4ε bound with
    the rounded values. A must have full row rank (`check_basis`), else `ValueError`."""
    width = len(basis.species)
    count = len(basis.groups)
    content = _matrix(basis.content)
    if _rank(content, width) != count:
        raise ValueError("A has no full row rank: species_basis_redundant")
    charges = tuple(Fraction(z) for z in basis.charges)
    with_mu = _rank((*content, charges), width) > count
    unknowns = count + int(with_mu)
    equations = tuple(
        tuple(content[g][s] for g in range(count)) + ((charges[s],) if with_mu else ())
        for s in range(width)
    )
    deciding = _independent_rows(equations, unknowns, unknowns)
    exact = _solve(
        tuple(equations[s] for s in deciding),
        unknowns,
        tuple(Fraction(masses[s]) for s in deciding),
    )
    if exact is None:  # unreachable: the deciding rows are independent
        raise ValueError("the deciding species admit no solution")
    rounded = tuple(float(value) for value in exact)
    group_masses = rounded[:count]
    mu = rounded[count] if with_mu else 0.0
    inconsistent = []
    for s in range(width):
        if s in deciding:
            continue
        terms = [content[g][s] * Fraction(group_masses[g]) for g in range(count)]
        charge_term = Fraction(mu) * charges[s]
        model = sum(terms, Fraction(0)) + charge_term
        bound = 4 * EPSILON * (Fraction(masses[s]) + sum(abs(t) for t in terms) + abs(charge_term))
        if abs(Fraction(masses[s]) - model) > bound:
            inconsistent.append(basis.species[s])
    return GroupMasses(
        group_masses, mu, tuple(basis.species[s] for s in deciding), tuple(inconsistent)
    )


def group_amounts(content: Sequence[Sequence[int]], n: Sequence[float]) -> tuple[float, ...]:
    """`b = A n_s` on doubles: per group, the terms with a non-zero content in species order,
    one rounding per product and sum, no fma. A unit entry multiplies exactly, so the true preset
    (A = I) returns `n` bitwise (Q3.A1)."""
    found = []
    for row in content:
        total: float | None = None
        for entry, amount in zip(row, n, strict=True):
            if entry == 0:
                continue
            term = amount if entry == 1 else float(entry) * amount
            total = term if total is None else total + term
        found.append(0.0 if total is None else total)
    return tuple(found)


def negative_groups(groups: Sequence[str], b: Sequence[float | Fraction]) -> tuple[str, ...]:
    """The groups whose amount is negative: each an invalid trial state
    (`group_amount_negative(<S>, <g>)`, Q3.R1 (iii)), never clipped."""
    return tuple(group for group, value in zip(groups, b, strict=True) if value < 0)


# -- Q3.R5: method boundaries -----------------------------------------------------------------


def _refused(reason: str, projection: tuple[tuple[str, tuple[int, ...]], ...] = ()) -> Boundary:
    return Boundary(False, projection, None, (), reason)


def _projection(
    producer: SpeciesBasis, consumer: SpeciesBasis
) -> tuple[tuple[str, tuple[int, ...]], ...] | str:
    """Π e_s over the consumer's species for each producer species it lacks (Q3.R5 (i)), or the
    reason none exists. Π e_s = e_s − R c with c the particular solution (free coefficients 0) of
    R c = e_s on the dropped coordinates, so e_s − Π e_s ∈ span R and Π e_s vanishes off S ∩ S′."""
    width = len(producer.species)
    dropped = [s for s, name in enumerate(producer.species) if name not in consumer.species]
    reactions = _matrix(producer.reactions)
    columns = _transpose(reactions, width) if reactions else tuple(() for _ in range(width))
    found = []
    for s in dropped:
        target = tuple(Fraction(int(t == s)) for t in dropped)
        rows = tuple(columns[t] for t in dropped)
        coefficients = _solve(rows, len(reactions), target) if reactions else None
        if coefficients is None:
            return f"{producer.species[s]} has no image in span R"
        image = [
            Fraction(int(t == s)) - _dot([reaction[t] for reaction in reactions], coefficients)
            for t in range(width)
        ]
        if any(value.denominator != 1 for value in image):
            return f"{producer.species[s]} has no integer image"
        by_name = {producer.species[t]: int(image[t]) for t in range(width) if t not in dropped}
        found.append(
            (producer.species[s], tuple(by_name.get(name, 0) for name in consumer.species))
        )
    return tuple(found)


def boundary(
    producer: SpeciesBasis,
    consumer: SpeciesBasis,
    solid_candidates: Mapping[str, str] | None = None,
) -> Boundary:
    """Q3.R5 (Amendment 2): whether the consumer's basis evaluates the producer's stream.

    Both bases are assumed valid on their own (Q3.R1) with full row rank. Species match by id and
    must carry equal charges. `solid_candidates` maps a producer species that forms a solid
    candidate of the producer's method to that phase's rendering, so dropping it reports
    `solid_candidate_dropped(<phase>)`; any other dropped species reports
    `species_dropped(<species>)`. A negative entry of C adds `species_basis_not_monotone`."""
    for name, charge in zip(consumer.species, consumer.charges, strict=True):
        if name in producer.species and producer.charges[producer.species.index(name)] != charge:
            return _refused(f"{name} has another charge in the consumer")
    projection = _projection(producer, consumer)
    if isinstance(projection, str):
        return _refused(projection)
    images = dict(projection)
    width = len(producer.species)
    consumer_content = _matrix(consumer.content)
    # T = A′ Π, one column per producer species.
    target_columns = []
    for name in producer.species:
        image = (
            images[name]
            if name in images
            else tuple(int(other == name) for other in consumer.species)
        )
        target_columns.append(
            tuple(_dot(row, tuple(Fraction(v) for v in image)) for row in consumer_content)
        )
    content = _matrix(producer.content)
    count = len(producer.groups)
    pivots = _independent_rows(_transpose(content, width), count, count)
    if len(pivots) != count:
        raise ValueError("the producer's A has no full row rank")
    # C A_P = T_P: each row c of C solves A_Pᵀ c = (row of T_P).
    square = tuple(tuple(content[g][p] for g in range(count)) for p in pivots)
    conversion = []
    for row in range(len(consumer.groups)):
        solved = _solve(square, count, tuple(target_columns[p][row] for p in pivots))
        if solved is None:  # unreachable: A_P is invertible
            raise ValueError("A_P is singular")
        conversion.append(solved)
    for s in range(width):
        product = tuple(
            _dot(c_row, tuple(content[g][s] for g in range(count))) for c_row in conversion
        )
        if product != target_columns[s]:
            return _refused("no C solves C A = A′ Π", projection)
    if any(value.denominator != 1 for c_row in conversion for value in c_row):
        return _refused("the C solving C A = A′ Π is not integer", projection)
    integral = tuple(tuple(int(value) for value in c_row) for c_row in conversion)
    candidates = solid_candidates or {}
    limitations = [
        Limitation("solid_candidate_dropped", candidates[name])
        if name in candidates
        else Limitation("species_dropped", name)
        for name, _ in projection
    ]
    if any(value < 0 for c_row in integral for value in c_row):
        limitations.append(Limitation("species_basis_not_monotone", "C"))
    return Boundary(True, projection, integral, tuple(limitations))


def former_boundary_rule(producer: SpeciesBasis, consumer: SpeciesBasis) -> bool:
    """The rule Q3.R5 had before Amendment 2: admitted iff S ⊆ S′ (equal charges) and
    span R ⊆ span R′. Kept as Q3.A6's control; sufficient, not necessary, under the new rule."""
    shared = all(
        name in consumer.species and consumer.charges[consumer.species.index(name)] == charge
        for name, charge in zip(producer.species, producer.charges, strict=True)
    )
    if not shared:
        return False
    width = len(consumer.species)
    embedded = tuple(
        tuple(
            Fraction(reaction[producer.species.index(name)])
            if name in producer.species
            else Fraction(0)
            for name in consumer.species
        )
        for reaction in producer.reactions
    )
    own = _matrix(consumer.reactions)
    return _rank((*own, *embedded), width) == _rank(own, width)
