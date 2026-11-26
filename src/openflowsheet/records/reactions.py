"""Reaction consistency (ADR 0061 D7, Q7.A3), F3-WO5a: element, charge and molar-mass balance of
reactions over component records.

`check_reactions` is the check `validate_record` (F3-WO5b) and F2's validator call. It takes
reactions `{id, stoichiometry: {component key: ν}}` and a map from component key to the
component's normalised record, and returns `(errors, findings)` in `validate.validate`'s form:
each list sorted by code and then params (UTF-8). Labels: `<reaction>` is the reaction's `id`,
`<component>` the component key its stoichiometry names (two keys may name records with one `id`,
as `l01`'s and `s10`'s water do), `<element>` the element symbol.

**The arithmetic.** Every number (ν_c, the element counts A_ec, the charges z_c and the molar
masses M_c) is converted exactly to a `Fraction`: a binary64 value is a dyadic rational, so
`Fraction(x)` is its exact value, a ν given as a `Fraction` is taken as it is (R-1054), and every
sum below is exact, independent of the platform and of
the summation order. Per reaction:

- element balance: for each element e of the components, Σ_c ν_c A_ec = 0, else the refusal
  `reaction_element_imbalance(<reaction>, <e>)`. A component whose `elements` is `null` (absent
  in the normalised record) cannot be counted: it gives the notice
  `reaction_element_unchecked(<reaction>, <component>)` instead, and that reaction's element
  balance is not judged;
- charge balance: Σ_c ν_c z_c = 0, else the refusal `reaction_charge_imbalance(<reaction>)`;
- molar mass: |Σ_c ν_c M_c| ≤ 4ε Σ_c |ν_c M_c| with ε = 2⁻⁵² exactly, else the notice
  `molar_mass_inconsistent(<reaction>)`. It never refuses: records from two atomic-weight
  conventions in one reaction are reported, not blocked (E-F3-10). Evaluating the ruling's
  inequality exactly is never stricter than a rounded evaluation, which approximates these exact
  sums of the stored doubles.

These are validation-class findings (Q9), never a verification verdict. Input that is not of this
shape (a stoichiometry key with no record, a ν that is not a finite number, a record without a
molar mass) is a caller's error (`ValueError`): the operation's request schema screens it. A `kg`
record has no molar mass; since F2-WO1 admits the basis it can be registered, and a reaction over
it is refused `invalid_request` by the records service, which catches this `ValueError`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from fractions import Fraction
from typing import Any, Final

from openflowsheet.registry.tokens import Coded

#: D7: the machine epsilon of binary64, 2⁻⁵², exactly; the molar-mass tolerance is 4ε.
EPSILON: Final = Fraction(1, 2**52)
MOLAR_MASS_TOLERANCE: Final = 4 * EPSILON


def check_reactions(
    reactions: Iterable[Mapping[str, Any]], components: Mapping[str, Mapping[str, Any]]
) -> tuple[tuple[Coded, ...], tuple[Coded, ...]]:
    """D7's reaction consistency of `reactions` over `components` (component key -> normalised
    component record): `(errors, findings)`, each sorted by `Coded.sort_key`."""
    errors: list[Coded] = []
    findings: list[Coded] = []
    for reaction in reactions:
        ident = str(reaction["id"])
        terms = [
            (key, exact(nu, f"{ident}: ν of {key}"), _record(components, key, ident))
            for key, nu in reaction["stoichiometry"].items()
        ]
        imbalanced, unchecked = _element_findings(ident, terms)
        errors += imbalanced
        findings += unchecked
        if sum(nu * exact(record["charge"], key) for key, nu, record in terms) != 0:
            errors.append(Coded("reaction_charge_imbalance", {"reaction": ident}))
        if not molar_mass_consistent(
            [(nu, _molar_mass(record, key, ident)) for key, nu, record in terms]
        ):
            findings.append(Coded("molar_mass_inconsistent", {"reaction": ident}))
    return _sorted(errors), _sorted(findings)


def molar_mass_consistent(terms: Iterable[tuple[Fraction, Fraction]]) -> bool:
    """D7: |Σ ν M| ≤ 4ε Σ |ν M| over the exact `(ν, M)` pairs, both sums exact."""
    products = [nu * mass for nu, mass in terms]
    total = sum(products, Fraction(0))
    return abs(total) <= MOLAR_MASS_TOLERANCE * sum((abs(p) for p in products), Fraction(0))


def exact(value: object, where: str) -> Fraction:
    """The exact rational value of an `int`, a finite `float` (`Fraction(x)` of a binary64 value
    is exact) or a `fractions.Fraction` (a rational ν, as F2 holds it; R-1054); `ValueError` for
    anything else, a `bool` included."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{where}: {value!r} is not a number")
    try:
        return Fraction(value)
    except (OverflowError, ValueError) as error:  # inf, nan
        raise ValueError(f"{where}: {value!r} is not finite") from error


Term = tuple[str, Fraction, Mapping[str, Any]]


def _element_findings(ident: str, terms: list[Term]) -> tuple[list[Coded], list[Coded]]:
    """The element balance of one reaction: the imbalanced elements (refusals), or, when a
    component's `elements` is null, a notice for each such component and no balance."""
    unknown = [key for key, _, record in terms if record.get("elements") is None]
    if unknown:
        params = [{"reaction": ident, "component": key} for key in unknown]
        return [], [Coded("reaction_element_unchecked", p) for p in params]
    balance: dict[str, Fraction] = {}
    for key, nu, record in terms:
        for element, count in record["elements"].items():
            amount = nu * exact(count, f"{ident}: {key} {element}")
            balance[element] = balance.get(element, Fraction(0)) + amount
    return [
        Coded("reaction_element_imbalance", {"reaction": ident, "element": element})
        for element, total in balance.items()
        if total != 0
    ], []


def _record(components: Mapping[str, Mapping[str, Any]], key: str, ident: str) -> Mapping[str, Any]:
    if key not in components:
        raise ValueError(f"{ident}: no record for component key {key!r}")
    return components[key]


def _molar_mass(record: Mapping[str, Any], key: str, ident: str) -> Fraction:
    constant = record.get("molar_mass")
    if not isinstance(constant, Mapping):
        raise ValueError(f"{ident}: the record of {key!r} has no molar mass")
    return exact(constant["value"], f"{ident}: M of {key}")


def _sorted(found: list[Coded]) -> tuple[Coded, ...]:
    return tuple(sorted(found, key=Coded.sort_key))
