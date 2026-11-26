"""Reference for E-F2-7 (ADR 0062): foundation rulings Q3.A1-A3 and Q3.A6, in exact arithmetic.

Every verdict is decided here by exact rational arithmetic on the rulings' definitions
(`docs/roadmap/foundation-rulings.md` Q3.R1, R4, R5 as amended by Amendment 2, R7), by routes chosen
to differ from `openflowsheet.material.basis`, which the tests compare against this file:

- ranks by fraction-free (Bareiss) elimination; dim(ker A ∩ ker zᵀ) by rank-nullity;
- Q3.R1 (iii) by testing every breakpoint λ = -A_gs / z_s of the concave min over s of
  A_gs + λ z_s (the maximum of a concave piecewise-linear function lies at a breakpoint);
- Q3.R7's (M_g, μ) by Cramer's rule on the first independent species (determinants by Bareiss);
- Q3.R5's C by the normal equations C = A′Π Aᵀ (A Aᵀ)⁻¹, then C A = A′Π checked entry by entry;
  Π is the ruling's own stated image (Q3.A6 (a), (d)), checked to satisfy e_s - Π e_s ∈ span R.

Nothing here imports OpenFlowsheet. The ruling's claims are checked and the script refuses to emit
when one fails: Q3.A2's verdicts per case, Q3.A6's C, Π and dropped species, and the control
(the former rule R′ ⊇ R with S ⊆ S′ refuses (a) and (d) and agrees on (b), (c), (e); nothing is
emitted if the new rule refuses (a), (b), (d) or (e) or admits (c)).

Species molar masses are **synthetic test constants**, not validation data: sums of IUPAC
conventional atomic weights (H 1.008, C 12.011, N 14.007, O 15.999, Na 22.98976928, S 32.06,
Cl 35.45, K 39.0983 g/mol), minus z times the electron molar mass (5.48579909065e-4 g/mol), in
kg/mol, each rounded once to binary64: the "record doubles" Q3.R7 computes on.

    python3 -I docs/derivations/scripts/f2_basis_reference.py          # write the JSON
    python3 -I docs/derivations/scripts/f2_basis_reference.py --check  # byte-compare; 1 on drift
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OUT = HERE / "f2_basis_reference.json"
EPSILON = Fraction(1, 2**52)

CLAIMS: list[str] = []


def claim(condition: bool, text: str) -> None:
    if not condition:
        raise SystemExit(f"claim failed, nothing emitted: {text}")
    CLAIMS.append(text)


# -- synthetic species masses ---------------------------------------------------------------------
ATOMIC = {
    "H": Fraction("1.008"),
    "C": Fraction("12.011"),
    "N": Fraction("14.007"),
    "O": Fraction("15.999"),
    "Na": Fraction("22.98976928"),
    "S": Fraction("32.06"),
    "Cl": Fraction("35.45"),
    "K": Fraction("39.0983"),
}
ELECTRON = Fraction("5.48579909065e-4")
#: species id: (atoms, charge). Ids are in the component alphabet; `NaCl` is the salt solid.
SPECIES: dict[str, tuple[dict[str, int], int]] = {
    "Na_p": ({"Na": 1}, 1),
    "K_p": ({"K": 1}, 1),
    "Cl_m": ({"Cl": 1}, -1),
    "SO4_2m": ({"S": 1, "O": 4}, -2),
    "NaCl": ({"Na": 1, "Cl": 1}, 0),
    "H2O": ({"H": 2, "O": 1}, 0),
    "MEA": ({"C": 2, "H": 7, "N": 1, "O": 1}, 0),
    "MEAH_p": ({"C": 2, "H": 8, "N": 1, "O": 1}, 1),
    "MEACOO_m": ({"C": 3, "H": 6, "N": 1, "O": 3}, -1),
    "CO2": ({"C": 1, "O": 2}, 0),
    "HCO3_m": ({"H": 1, "C": 1, "O": 3}, -1),
    "CO3_2m": ({"C": 1, "O": 3}, -2),
    "H3O_p": ({"H": 3, "O": 1}, 1),
    "OH_m": ({"O": 1, "H": 1}, -1),
    # Q3.A6 (c): three abstract species of one (fictitious) mass each.
    "A": ({"C": 1}, 0),
    "B": ({"C": 1}, 0),
    "W": ({"H": 2, "O": 1}, 0),
}


def mass(species: str) -> float:
    atoms, charge = SPECIES[species]
    exact = sum((ATOMIC[a] * k for a, k in atoms.items()), Fraction(0)) - charge * ELECTRON
    return float(exact / 1000)


def charge(species: str) -> int:
    return SPECIES[species][1]


# -- exact linear algebra, fraction-free ---------------------------------------------------------
def bareiss_rank(rows: list[list[Fraction]]) -> int:
    """Rank by fraction-free elimination on the rows scaled to integers."""
    if not rows or not rows[0]:
        return 0
    work = []
    for row in rows:
        scale = 1
        for value in row:
            scale = scale * value.denominator // _gcd(scale, value.denominator)
        work.append([int(value * scale) for value in row])
    m, n = len(work), len(work[0])
    rank, previous = 0, 1
    for column in range(n):
        pivot = next((i for i in range(rank, m) if work[i][column] != 0), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        for i in range(rank + 1, m):
            for j in range(column + 1, n):
                work[i][j] = (
                    work[i][j] * work[rank][column] - work[i][column] * work[rank][j]
                ) // previous
            work[i][column] = 0
        previous = work[rank][column]
        rank += 1
        if rank == m:
            break
    return rank


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return abs(a)


def determinant(square: list[list[Fraction]]) -> Fraction:
    """Laplace expansion along the first row (the systems here are at most 5 x 5)."""
    size = len(square)
    if size == 1:
        return square[0][0]
    total = Fraction(0)
    for j in range(size):
        if square[0][j] == 0:
            continue
        minor = [row[:j] + row[j + 1 :] for row in square[1:]]
        total += (-1) ** j * square[0][j] * determinant(minor)
    return total


def cramer(square: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    det = determinant(square)
    assert det != 0
    found = []
    for j in range(len(square)):
        replaced = [row[:j] + [rhs[i]] + row[j + 1 :] for i, row in enumerate(square)]
        found.append(determinant(replaced) / det)
    return found


def fr(rows: list[list[int]] | list[list[Fraction]]) -> list[list[Fraction]]:
    return [[Fraction(v) for v in row] for row in rows]


def matmul(left: list[list[Fraction]], right: list[list[Fraction]]) -> list[list[Fraction]]:
    return [
        [
            sum((left[i][k] * right[k][j] for k in range(len(right))), Fraction(0))
            for j in range(len(right[0]))
        ]
        for i in range(len(left))
    ]


def transpose(rows: list[list[Fraction]]) -> list[list[Fraction]]:
    return [list(column) for column in zip(*rows, strict=True)]


# -- the cases ----------------------------------------------------------------------------------
def reaction(species: list[str], terms: dict[str, int]) -> list[int]:
    """A fast reaction's vector: products positive, reactants negative."""
    assert set(terms) <= set(species)
    return [terms.get(s, 0) for s in species]


def content(species: list[str], groups: dict[str, dict[str, int]]) -> list[list[int]]:
    return [[row.get(s, 0) for s in species] for row in groups.values()]


NACL = ["Na_p", "Cl_m", "H2O"]
NACL_SOLID = ["Na_p", "Cl_m", "NaCl", "H2O"]
MEA9 = ["MEA", "MEAH_p", "MEACOO_m", "CO2", "HCO3_m", "CO3_2m", "H2O", "H3O_p", "OH_m"]
MEA8 = [s for s in MEA9 if s != "MEACOO_m"]
RECIPROCAL = ["Na_p", "K_p", "Cl_m", "SO4_2m", "H2O"]
ABW = ["A", "B", "W"]

MEA_GROUPS = {
    "MEA": {"MEA": 1, "MEAH_p": 1, "MEACOO_m": 1},
    "CO2": {"MEACOO_m": 1, "CO2": 1, "HCO3_m": 1, "CO3_2m": 1},
    "H2O": {"HCO3_m": 1, "CO3_2m": 1, "H2O": 1, "H3O_p": 1, "OH_m": 1},
}
MEA_REACTIONS = {
    "water": {"H3O_p": 1, "OH_m": 1, "H2O": -2},
    "mea_protonation": {"MEAH_p": 1, "H2O": 1, "MEA": -1, "H3O_p": -1},
    "co2_hydration": {"HCO3_m": 1, "H3O_p": 1, "CO2": -1, "H2O": -2},
    "bicarbonate": {"CO3_2m": 1, "H3O_p": 1, "HCO3_m": -1, "H2O": -1},
    "carbamate": {"MEACOO_m": 1, "H2O": 1, "MEA": -1, "HCO3_m": -1},
}


def basis(
    species: list[str], groups: dict[str, dict[str, int]], reactions: dict[str, dict[str, int]]
) -> dict[str, Any]:
    return {
        "species": species,
        "groups": list(groups),
        "content": content(species, groups),
        "charges": [charge(s) for s in species],
        "reactions": [reaction(species, r) for r in reactions.values()],
        "reaction_names": list(reactions),
        "masses": [mass(s) for s in species],
    }


def identity_groups(species: list[str]) -> dict[str, dict[str, int]]:
    return {s: {s: 1} for s in species}


DISSOLUTION = {"NaCl_dissolution": {"Na_p": 1, "Cl_m": 1, "NaCl": -1}}
APPARENT_NACL = {"NaCl": {"Na_p": 1}, "H2O": {"H2O": 1}}
APPARENT_NACL_SOLID = {"NaCl": {"Na_p": 1, "NaCl": 1}, "H2O": {"H2O": 1}}
NEUTRAL_RECIPROCAL = {
    "NaCl": {"K_p": -1, "Cl_m": 1},
    "KCl": {"K_p": 1},
    "Na2SO4": {"SO4_2m": 1},
    "H2O": {"H2O": 1},
}
FOUR = {name: r for name, r in MEA_REACTIONS.items() if name != "carbamate"}

BASES: dict[str, dict[str, Any]] = {
    # Q3.A2
    "a2a_nacl_apparent": basis(NACL, APPARENT_NACL, {}),
    "a2b_nacl_solid": basis(NACL_SOLID, APPARENT_NACL_SOLID, DISSOLUTION),
    "a2b_nacl_solid_no_dissolution": basis(NACL_SOLID, APPARENT_NACL_SOLID, {}),
    "a2c_mea": basis(MEA9, MEA_GROUPS, MEA_REACTIONS),
    "a2c_mea_no_carbamate": basis(MEA9, MEA_GROUPS, FOUR),
    "a2d_neutral_reciprocal": basis(RECIPROCAL, NEUTRAL_RECIPROCAL, {}),
    "a2d_charged_groups": basis(RECIPROCAL, identity_groups(RECIPROCAL), {}),
    # Q3.A6's other bases
    "a6c_ab_lumped": basis(
        ABW, {"AB": {"A": 1, "B": 1}, "W": {"W": 1}}, {"A_to_B": {"A": -1, "B": 1}}
    ),
    "a6c_true": basis(ABW, identity_groups(ABW), {}),
    "a6d_mea_no_carbamate_species": basis(
        MEA8,
        {g: {s: v for s, v in row.items() if s != "MEACOO_m"} for g, row in MEA_GROUPS.items()},
        FOUR,
    ),
    "a6e_nacl_true": basis(NACL, identity_groups(NACL), {}),
}

#: Q3.A2's stated verdict per basis: (i), (ii), (iii), dim(ker A ∩ ker zᵀ).
STATED_A2 = {
    "a2a_nacl_apparent": (True, True, True, 0),
    "a2b_nacl_solid": (True, True, True, 1),
    "a2b_nacl_solid_no_dissolution": (True, False, True, 1),
    "a2c_mea": (True, True, True, 5),
    "a2c_mea_no_carbamate": (True, False, True, 5),
    "a2d_neutral_reciprocal": (True, True, False, 0),
    "a2d_charged_groups": (True, True, True, 0),
}


def check(b: dict[str, Any]) -> dict[str, Any]:
    width = len(b["species"])
    a = fr(b["content"])
    z = [Fraction(v) for v in b["charges"]]
    r = fr(b["reactions"])
    conserve = all(sum(x * y for x, y in zip(row, rx, strict=True)) == 0 for row in a for rx in r)
    stacked_rank = bareiss_rank(a + [z])
    dimension = width - stacked_rank
    in_kernel = all(
        sum(x * y for x, y in zip(row, rx, strict=True)) == 0 for row in [*a, z] for rx in r
    )
    fixed = in_kernel and bareiss_rank(r) == dimension
    monotone = True
    for row in a:
        breakpoints = [-row[s] / z[s] for s in range(width) if z[s] != 0] or [Fraction(0)]
        if not any(all(row[s] + lam * z[s] >= 0 for s in range(width)) for lam in breakpoints):
            monotone = False
    full = bareiss_rank(a) == len(a)
    return {
        "reactions_conserve_groups": conserve,
        "invariants_fixed": fixed,
        "monotone": monotone,
        "invariant_dimension": dimension,
        "full_row_rank": full,
    }


def group_masses(b: dict[str, Any], masses: list[float]) -> dict[str, Any]:
    """Q3.R7 by Cramer's rule on the first independent species rows."""
    width, count = len(b["species"]), len(b["groups"])
    a = fr(b["content"])
    z = [Fraction(v) for v in b["charges"]]
    with_mu = bareiss_rank(a + [z]) > bareiss_rank(a)
    rows = [[a[g][s] for g in range(count)] + ([z[s]] if with_mu else []) for s in range(width)]
    unknowns = count + int(with_mu)
    deciding: list[int] = []
    for s in range(width):
        if bareiss_rank([rows[i] for i in deciding + [s]]) == len(deciding) + 1:
            deciding.append(s)
        if len(deciding) == unknowns:
            break
    exact = cramer([rows[s] for s in deciding], [Fraction(masses[s]) for s in deciding])
    rounded = [float(v) for v in exact]
    mg, mu = rounded[:count], (rounded[count] if with_mu else 0.0)
    inconsistent = []
    worst = Fraction(0)
    for s in range(width):
        if s in deciding:
            continue
        terms = [a[g][s] * Fraction(mg[g]) for g in range(count)]
        zterm = Fraction(mu) * z[s]
        deficit = abs(Fraction(masses[s]) - sum(terms, Fraction(0)) - zterm)
        scale = Fraction(masses[s]) + sum(abs(t) for t in terms) + abs(zterm)
        worst = max(worst, deficit / (EPSILON * scale))
        if deficit > 4 * EPSILON * scale:
            inconsistent.append(b["species"][s])
    return {
        "group_masses": mg,
        "mu": mu,
        "deciding_species": [b["species"][s] for s in deciding],
        "inconsistent": inconsistent,
        "worst_deficit_in_epsilon_scale": float(worst),
    }


# -- Q3.R5 -------------------------------------------------------------------------------------
def boundary(
    producer: dict[str, Any],
    consumer: dict[str, Any],
    images: dict[str, dict[str, int]],
    solids: dict[str, str],
) -> dict[str, Any]:
    """The new rule with the ruling's stated Π; C by the normal equations."""
    s_p, s_c = producer["species"], consumer["species"]
    width = len(s_p)
    dropped = [s for s in s_p if s not in s_c]
    claim(
        sorted(dropped) == sorted(images), f"Π is stated for exactly the dropped species {dropped}"
    )
    r = fr(producer["reactions"])
    projection = []
    for s in dropped:
        image = images[s]
        assert set(image) <= set(s_c) and set(image) <= set(s_p)
        difference = [Fraction(int(t == s) - image.get(t, 0)) for t in s_p]
        in_span = bool(r) and bareiss_rank(r + [difference]) == bareiss_rank(r)
        if not in_span:
            return {"admitted": False, "reason": f"e_{s} - Π e_{s} is not in span R"}
        projection.append([s, [image.get(t, 0) for t in s_c]])
    pi = []  # |S′| x |S|
    for t in s_c:
        pi.append([Fraction(images[s].get(t, 0) if s in images else int(s == t)) for s in s_p])
    target = matmul(fr(consumer["content"]), pi)
    a = fr(producer["content"])
    gram = matmul(a, transpose(a))
    right = matmul(a, transpose(target))  # (A Aᵀ) Cᵀ = A Tᵀ
    columns = [cramer(gram, [right[i][j] for i in range(len(a))]) for j in range(len(target))]
    c = columns  # row j of C is the j-th solution
    if matmul(c, a) != target:
        return {"admitted": False, "reason": "no C solves C A = A′ Π", "projection": projection}
    if any(v.denominator != 1 for row in c for v in row):
        return {"admitted": False, "reason": "C is not integer", "projection": projection}
    limitations = [
        ["solid_candidate_dropped", solids[s]] if s in solids else ["species_dropped", s]
        for s in dropped
    ]
    if any(v < 0 for row in c for v in row):
        limitations.append(["species_basis_not_monotone", "C"])
    _ = width
    return {
        "admitted": True,
        "conversion": [[int(v) for v in row] for row in c],
        "projection": projection,
        "limitations": limitations,
    }


def former_rule(producer: dict[str, Any], consumer: dict[str, Any]) -> bool:
    s_p, s_c = producer["species"], consumer["species"]
    if not set(s_p) <= set(s_c):
        return False
    own = fr(consumer["reactions"])
    embedded = [
        [Fraction(rx[s_p.index(t)]) if t in s_p else Fraction(0) for t in s_c]
        for rx in producer["reactions"]
    ]
    return bareiss_rank(own + embedded) == bareiss_rank(own)


#: Q3.A6: (producer, consumer, the ruling's Π, solid candidates, stated verdict, stated C, stated
#: drops, the former rule's verdict).
A6 = {
    "a": (
        "a2b_nacl_solid",
        "a2a_nacl_apparent",
        {"NaCl": {"Na_p": 1, "Cl_m": 1}},
        {"NaCl": "SOLID(NaCl)"},
        True,
        [[1, 0], [0, 1]],
        [["solid_candidate_dropped", "SOLID(NaCl)"]],
        False,
    ),
    "b": ("a2a_nacl_apparent", "a2b_nacl_solid", {}, {}, True, [[1, 0], [0, 1]], [], True),
    "c": ("a6c_ab_lumped", "a6c_true", {}, {}, False, None, None, False),
    "c_reverse": ("a6c_true", "a6c_ab_lumped", {}, {}, True, [[1, 1, 0], [0, 0, 1]], [], True),
    "d": (
        "a2c_mea",
        "a6d_mea_no_carbamate_species",
        {"MEACOO_m": {"MEA": 1, "HCO3_m": 1, "H2O": -1}},
        {},
        True,
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        [["species_dropped", "MEACOO_m"]],
        False,
    ),
    "e": ("a6e_nacl_true", "a2a_nacl_apparent", {}, {}, True, [[1, 0, 0], [0, 0, 1]], [], True),
}

#: Q3.A3: a K2SO4-rich, electroneutral equilibrium outlet over (Na+, K+, Cl-, SO4 2-, H2O), mol/s.
A3_STATE = [Fraction(1, 10), Fraction(2), Fraction(1, 10), Fraction(1), Fraction(10)]


def main() -> int:
    out: dict[str, Any] = {
        "description": __doc__.split("\n", 1)[0],
        "bases": {},
        "boundaries": {},
    }
    for name, b in BASES.items():
        verdict = check(b)
        entry = {**b, "verdict": verdict}
        if name in STATED_A2:
            stated = STATED_A2[name]
            got = (
                verdict["reactions_conserve_groups"],
                verdict["invariants_fixed"],
                verdict["monotone"],
                verdict["invariant_dimension"],
            )
            claim(got == stated, f"Q3.A2 {name}: (i), (ii), (iii), dim = {stated}")
        else:
            claim(
                verdict["reactions_conserve_groups"] and verdict["invariants_fixed"],
                f"Q3.A6 basis {name} is valid on its own (Q3.R1)",
            )
        claim(verdict["full_row_rank"], f"{name}: A has full row rank (Q3.R7)")
        masses = group_masses(b, b["masses"])
        claim(not masses["inconsistent"], f"{name}: every species meets Q3.R7's 4ε bound")
        entry["group_masses"] = masses
        out["bases"][name] = entry
    # Q3.R7's own limiting case: M_NaCl = M_Na+ + M_Cl-, μ = -M_Cl- (exact before rounding).
    a2a = out["bases"]["a2a_nacl_apparent"]["group_masses"]
    claim(
        a2a["mu"] == -mass("Cl_m")
        and a2a["group_masses"][0] == float(Fraction(mass("Na_p")) + Fraction(mass("Cl_m"))),
        "Q3 argument: M_NaCl = M_Na+ + M_Cl-, μ = -M_Cl- (each rounded once)",
    )
    # The electron-mass control (Q7.A3's case on Q3.A2 (b)): Na+ given the neutral atom's mass.
    shifted = list(BASES["a2b_nacl_solid"]["masses"])
    shifted[0] = float(ATOMIC["Na"] / 1000)
    control = group_masses(BASES["a2b_nacl_solid"], shifted)
    claim(
        control["inconsistent"] == ["NaCl"],
        "Q3.A2 (b) with Na+ off by the electron mass: NaCl reported",
    )
    out["electron_mass_control"] = {"masses": shifted, "group_masses": control}
    # Q3.A3
    neutral, charged = BASES["a2d_neutral_reciprocal"], BASES["a2d_charged_groups"]
    b_neutral = [
        sum((Fraction(x) * y for x, y in zip(row, A3_STATE, strict=True)), Fraction(0))
        for row in neutral["content"]
    ]
    b_charged = [
        sum((Fraction(x) * y for x, y in zip(row, A3_STATE, strict=True)), Fraction(0))
        for row in charged["content"]
    ]
    z = neutral["charges"]
    neutrality = sum(Fraction(q) * n for q, n in zip(z, A3_STATE, strict=True))
    claim(neutrality == 0, "Q3.A3's state is electroneutral")
    negative = [g for g, v in zip(neutral["groups"], b_neutral, strict=True) if v < 0]
    claim(negative == ["NaCl"], "Q3.A3: the neutral reciprocal declaration gives b_NaCl < 0")
    claim(all(v >= 0 for v in b_charged), "Q3.A3: the charged groups give b >= 0")
    out["negative_decomposition"] = {
        "state": [str(v) for v in A3_STATE],
        "neutral_amounts": [str(v) for v in b_neutral],
        "neutral_negative_groups": negative,
        "charged_amounts": [str(v) for v in b_charged],
    }
    # Q3.A6
    for case, (prod, cons, images, solids, admitted, c, drops, former) in A6.items():
        producer, consumer = BASES[prod], BASES[cons]
        new = boundary(producer, consumer, images, solids)
        old = former_rule(producer, consumer)
        claim(
            new["admitted"] == admitted,
            f"Q3.A6 ({case}): the new rule {'admits' if admitted else 'refuses'}",
        )
        if admitted:
            claim(new["conversion"] == c, f"Q3.A6 ({case}): C = {c}")
            claim(new["limitations"] == drops, f"Q3.A6 ({case}): limitations {drops}")
        claim(
            old == former,
            f"Q3.A6 ({case}) control: the former rule {'admits' if former else 'refuses'}",
        )
        out["boundaries"][case] = {
            "producer": prod,
            "consumer": cons,
            "solid_candidates": solids,
            "new_rule": new,
            "former_rule_admitted": old,
        }
    agree = [
        case
        for case in A6
        if out["boundaries"][case]["new_rule"]["admitted"]
        == out["boundaries"][case]["former_rule_admitted"]
    ]
    claim(
        sorted(agree) == ["b", "c", "c_reverse", "e"],
        "control: the rules agree on (b), (c), (e) and differ on (a), (d)",
    )
    out["claims"] = CLAIMS
    text = json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if "--check" in sys.argv[1:]:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != text:
            print(f"FAIL f2_basis_reference --check: {OUT.name} differs from the regenerated one")
            return 1
        print(f"PASS f2_basis_reference --check: {len(CLAIMS)} claims hold; {OUT.name} unchanged")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"PASS f2_basis_reference: {len(CLAIMS)} claims hold; wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
