"""Record validation (ADR 0061 D2 step 6, D6's stated-anchor rule, D7), on a normalised record.

`validate` checks the record against `schemas/record-v2.schema.json` first; a record the schema
refuses gets one `record_schema_invalid(<pointer>)` (the first error by path) and no other check,
since every later rule reads the schema's shape. Otherwise it returns every D7 error the record
has and its findings, each list sorted by code and then params (UTF-8). Labels: `<component>` is
the record's `id`, `<entry>` the RFC 6901 pointer of the entry or Constant in the normalised
record (`/entries/2`, `/molar_mass`, `/formation/0/h`).

D7's reaction checks (Q7.A3) take reactions and a record map, not one record: they are
`records.reactions` (F3-WO5), not here.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from functools import cache
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator

from openflowsheet.records.model import (
    ADMITTED_BASES,
    ANCHOR,
    CONSTANT_VARIABLES,
    CORE_PROPERTIES,
    FORMATION_KINDS,
    MOLAR_MASS_KINDS,
    VOLATILE,
    CoreProperty,
    element_symbols,
    pointer,
    record_schema,
)
from openflowsheet.records.normalize import quantities, schema_invalid
from openflowsheet.registry.tokens import Coded
from openflowsheet.units import KIND_SI_UNITS

if TYPE_CHECKING:
    from openflowsheet.registry import Registry

#: D3, D7: a CAS registry number (its check digit is checked apart) and an InChIKey.
_CAS: re.Pattern[str] = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
_INCHIKEY: re.Pattern[str] = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
#: D7: a formula read as element symbols with optional counts (`CH3OH`), in any order.
_FORMULA: re.Pattern[str] = re.compile(r"^(?:[A-Z][a-z]?[0-9]*)+$")
_FORMULA_TERM: re.Pattern[str] = re.compile(r"([A-Z][a-z]?)([0-9]*)")


def validate(
    record: Mapping[str, Any],
    volatile: object,
    *,
    anchor_derived: bool,
    registry: Registry,
) -> tuple[tuple[Coded, ...], tuple[Coded, ...]]:
    """Step 6 on a normalised record and its detached `volatile` block (`None` when absent):
    `(errors, findings)`. The schema reads the record with `volatile` re-attached, so a member
    outside the closed volatile set refuses. A record type or correlation form is known when
    `registry` registers it (`record_type`, `correlation_form`); a stated anchor is checked, a
    derived one (`anchor_derived`) is D6's own."""
    document = dict(record) if volatile is None else {**record, VOLATILE: volatile}
    refused = _schema_pointer(document)
    if refused is not None:
        return (schema_invalid(refused),), ()
    errors = _record_type_errors(record, registry)
    if record["record_type"] == "component":
        errors += _component_errors(record, anchor_derived)
    if record["record_type"] in CORE_PROPERTIES:
        errors += _entry_errors(record, _forms(registry))
    findings = _fit_findings(record) if record["record_type"] in CORE_PROPERTIES else []
    return _sorted(errors), _sorted(findings)


def _schema_pointer(document: Mapping[str, Any]) -> str | None:
    """The pointer of the record schema's first error by path, `None` when there is none. An
    `unevaluatedProperties` error counts only when it is the only kind: a member that fails its
    branch is also reported unevaluated at the record's root, which would hide where it fails."""
    errors = sorted(_validator().iter_errors(document), key=lambda error: list(error.absolute_path))
    primary = [error for error in errors if error.validator != "unevaluatedProperties"] or errors
    if not primary:
        return None
    return "".join(pointer("", part) for part in primary[0].absolute_path)


@cache
def _validator() -> Draft202012Validator:
    """The record schema's validator (the schema holds only local references)."""
    return Draft202012Validator(record_schema())


def _sorted(found: list[Coded]) -> tuple[Coded, ...]:
    return tuple(sorted(found, key=Coded.sort_key))


def _record_type_errors(record: Mapping[str, Any], registry: Registry) -> list[Coded]:
    """`record_schema_invalid(/record_type)` unless (`record_type`, `type_version`) is a
    registered `record_type` descriptor."""
    registered = {(entry.id, entry.version) for entry in registry.descriptors(("record_type",))}
    if (record["record_type"], record["type_version"]) in registered:
        return []
    return [schema_invalid("/record_type")]


def _forms(registry: Registry) -> dict[str, Mapping[str, Any]]:
    """The registered correlation forms' payloads by id; of several versions, the highest wins
    (`descriptors` sorts by version)."""
    return {entry.id: entry.payload for entry in registry.descriptors(("correlation_form",))}


# -- a component (D3, D6, D7) ---------------------------------------------------------------------


def _component_errors(record: Mapping[str, Any], anchor_derived: bool) -> list[Coded]:
    """D7's component rules in its order: amount basis, units of the formation and transition
    data, identifiers, formula against elements, `elemental_verification`, a stated anchor
    (`_anchor_errors`, skipped when D6 derived it), and the uniqueness of formation phases and
    transitions."""
    errors = _basis_errors(record)
    errors += _formation_unit_errors(record)
    errors += _identifier_errors(record)
    errors += _formula_errors(record)
    if (record.get("elements") is None) != (record["elemental_verification"] == "NOT_APPLICABLE"):
        errors.append(schema_invalid("/elemental_verification"))
    if not anchor_derived:
        errors += _anchor_errors(record)
    errors += _duplicates(record.get("formation", []), "formation", lambda item: item["phase"])
    errors += _duplicates(
        record.get("transitions", []), "transitions", lambda item: (item["from"], item["to"])
    )
    return errors


def _basis_errors(record: Mapping[str, Any]) -> list[Coded]:
    """`amount_basis_unsupported(<basis>)` for a basis not yet admitted, and
    `amount_basis_invalid(<component>, <rule>)` per broken rule: `molar_mass_present` (`kg`),
    `molar_mass_absent` (otherwise), `molar_mass_kind`, `charge_nonzero` (`kg`). Segment types
    (preview) on another basis than `segment_mol` are `record_schema_invalid`."""
    basis = record["amount_basis"]
    found = [] if basis in ADMITTED_BASES else [Coded("amount_basis_unsupported", {"basis": basis})]
    molar_mass = record.get("molar_mass")
    rules = {
        "molar_mass_present": basis == "kg" and molar_mass is not None,
        "molar_mass_absent": basis != "kg" and molar_mass is None,
        "molar_mass_kind": molar_mass is not None
        and molar_mass["kind"] != MOLAR_MASS_KINDS.get(basis),
        "charge_nonzero": basis == "kg" and record["charge"] != 0,
    }
    component = str(record["id"])
    found += [
        Coded("amount_basis_invalid", {"component": component, "rule": rule})
        for rule, broken in rules.items()
        if broken
    ]
    if "segment_types" in record and basis != "segment_mol":
        found.append(schema_invalid("/segment_types"))
    return found


def _formation_unit_errors(record: Mapping[str, Any]) -> list[Coded]:
    """`record_unit_invalid(<entry>)` for a formation or transition `h` not of `molar_enthalpy`,
    an `s` not of `molar_entropy` (not yet registered, ADR 0061 risk 6), or a unit that is not
    the kind's SI unit."""
    found = []
    for name in ("formation", "transitions"):
        for index, item in enumerate(record.get(name, [])):
            for part in ("h", "s"):
                constant = item.get(part)
                if constant is not None and not _unit_ok(constant, FORMATION_KINDS[part]):
                    found.append(_unit_invalid(f"/{name}/{index}/{part}"))
    return found


def _unit_ok(quantity: Mapping[str, Any], kind: str) -> bool:
    return bool(quantity["kind"] == kind and KIND_SI_UNITS.get(kind) == quantity["unit"])


def _unit_invalid(at: str) -> Coded:
    return Coded("record_unit_invalid", {"entry": at})


def _identifier_errors(record: Mapping[str, Any]) -> list[Coded]:
    """`identifier_invalid(<component>, <scheme>)` for every identifier of a synthetic
    component, a CAS number whose check digit fails and a malformed InChIKey."""
    identifiers: Mapping[str, str] = record.get("identifiers", {})
    if record["synthetic"]:
        bad = sorted(identifiers)
    else:
        bad = [scheme for scheme in ("cas", "inchikey") if not _identifier_ok(identifiers, scheme)]
    component = str(record["id"])
    return [Coded("identifier_invalid", {"component": component, "scheme": s}) for s in bad]


def _identifier_ok(identifiers: Mapping[str, str], scheme: str) -> bool:
    """Whether `identifiers[scheme]` is absent or well formed (D3)."""
    value = identifiers.get(scheme)
    if value is None:
        return True
    if scheme == "inchikey":
        return _INCHIKEY.match(value) is not None
    match = _CAS.match(value)
    if match is None:
        return False
    digits = (match[1] + match[2])[::-1]
    return sum(weight * int(d) for weight, d in enumerate(digits, start=1)) % 10 == int(match[3])


def _formula_errors(record: Mapping[str, Any]) -> list[Coded]:
    """`formula_elements_invalid(<component>)` for a `mol` record whose formula does not read as
    element symbols with counts, or whose counts differ from `elements`. A record without a
    formula or with `elements` null is not checked."""
    formula = record.get("identifiers", {}).get("formula")
    elements = record.get("elements")
    if record["amount_basis"] != "mol" or formula is None or elements is None:
        return []
    if _formula_counts(formula) == elements:
        return []
    return [Coded("formula_elements_invalid", {"component": str(record["id"])})]


def _formula_counts(formula: str) -> dict[str, int] | None:
    """The element counts a formula states (`CH3OH`: C 1, H 4, O 1); `None` when it is not a
    sequence of element symbols with optional counts."""
    if _FORMULA.match(formula) is None:
        return None
    counts: dict[str, int] = {}
    symbols = element_symbols()
    for symbol, count in _FORMULA_TERM.findall(formula):
        if symbol not in symbols:
            return None
        counts[symbol] = counts.get(symbol, 0) + (int(count) if count else 1)
    return counts


def _anchor_errors(record: Mapping[str, Any]) -> list[Coded]:
    """D6 on a stated anchor: `anchor_phase_invalid(<component>, <phase>)` when the component is
    charged and the anchor is not `aq`, or the record has formation data and none in the
    anchor's phase. A stated `null` never reaches here (step 2a removes it; D6 derives)."""
    anchor = record[ANCHOR]
    phases = {item["phase"] for item in record.get("formation", [])}
    if (record["charge"] != 0 and anchor != "aq") or (phases and anchor not in phases):
        return [
            Coded("anchor_phase_invalid", {"component": str(record["id"]), "phase": str(anchor)})
        ]
    return []


def _duplicates(items: list[Mapping[str, Any]], name: str, key: Any) -> list[Coded]:
    """`record_schema_invalid` at every element of `name` whose key an earlier element has."""
    seen: set[str] = set()
    found = []
    for index, item in enumerate(items):
        spelled = repr(key(item))
        if spelled in seen:
            found.append(schema_invalid(pointer(f"/{name}", index)))
        seen.add(spelled)
    return found


# -- entries and Constants (D4, D5, D7) -----------------------------------------------------------


def _entry_errors(record: Mapping[str, Any], forms: Mapping[str, Mapping[str, Any]]) -> list[Coded]:
    """The rules on every entry and Constant of a component or parameter set: units, the core
    property table, correlation forms and coefficients, validity ranges and provenance; the
    uniqueness of entry keys; for a parameter set its component keys, entry indices and domain."""
    found: list[Coded] = []
    core = CORE_PROPERTIES[record["record_type"]]
    for at, quantity in quantities(record):
        found += _provenance_errors(at, quantity, record["sources"])
        if at.startswith("/entries/"):
            found += _entry_rules(at, quantity, core, forms)
        elif not at.startswith(("/formation/", "/transitions/")) and not _si(quantity):
            found.append(_unit_invalid(at))  # `molar_mass`, a segment type's
    found += _duplicates(record.get("entries", []), "entries", _entry_key)
    if record["record_type"] == "parameter_set":
        found += _set_errors(record)
    return found


def _si(quantity: Mapping[str, Any]) -> bool:
    """Whether the quantity's kind is registered and its unit is the kind's SI unit."""
    return bool(KIND_SI_UNITS.get(quantity["kind"]) == quantity["unit"])


def _entry_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    return (entry["property"], entry.get("phase"), tuple(entry.get("indices", ())))


def _provenance_errors(
    at: str, quantity: Mapping[str, Any], sources: Mapping[str, Any]
) -> list[Coded]:
    """`provenance_invalid(<entry>)`: an empty origin, or a source that is not a key of
    `sources`."""
    provenance = quantity["provenance"]
    if provenance["origin"] and provenance["source"] in sources:
        return []
    return [Coded("provenance_invalid", {"entry": at})]


def _entry_rules(
    at: str,
    entry: Mapping[str, Any],
    core: Mapping[str, CoreProperty],
    forms: Mapping[str, Mapping[str, Any]],
) -> list[Coded]:
    """One entry: the core property table (`_core_errors`), its form (`_form_errors`) and its
    validity ranges against the form's variables (`T`, `P` for a constant)."""
    found = _core_errors(at, entry, core)
    form = forms.get(entry["form"])
    found += _form_errors(at, entry, form)
    if entry["form"] == "constant":
        variables: tuple[str, ...] = CONSTANT_VARIABLES
    else:
        variables = tuple(item["name"] for item in (form or {}).get("variables", ()))
    found += _validity_errors(at, entry.get("validity"), variables)
    return found


def _core_errors(
    at: str, entry: Mapping[str, Any], core: Mapping[str, CoreProperty]
) -> list[Coded]:
    """D4's table for an un-namespaced property: unknown to the record type, or with another form
    or phase, is `record_schema_invalid` at that member; with another kind (a constant's, or a
    form's result kind) `record_unit_invalid`. A namespaced property is the extension's own."""
    name = entry["property"]
    if "." in name:
        return []
    row = core.get(name)
    if row is None:
        return [schema_invalid(pointer(at, "property"))]
    if entry["form"] != row.form:
        return [schema_invalid(pointer(at, "form"))]
    if entry.get("phase") != row.phase:
        return [schema_invalid(pointer(at, "phase"))]
    if entry["form"] == "constant" and entry["kind"] != row.kind:
        return [_unit_invalid(at)]
    return []


def _form_errors(at: str, entry: Mapping[str, Any], form: Mapping[str, Any] | None) -> list[Coded]:
    """A constant's unit against its kind (`record_unit_invalid`); a correlation's form, unknown
    (`correlation_form_unknown`) or with other coefficient names
    (`correlation_coefficients_invalid`)."""
    if entry["form"] == "constant":
        return [] if _si(entry) else [_unit_invalid(at)]
    params = {"entry": at, "form": entry["form"]}
    if form is None:
        return [Coded("correlation_form_unknown", params)]
    names = {item["name"] for item in form["coefficients"]}
    if set(entry["coefficients"]) != names:
        return [Coded("correlation_coefficients_invalid", params)]
    return []


def _validity_errors(
    at: str, validity: Mapping[str, Any] | None, variables: tuple[str, ...]
) -> list[Coded]:
    """`validity_range_invalid(<entry>, <variable>)` for a variable the form does not have, or a
    range whose lower bound is not below its upper."""
    return [
        Coded("validity_range_invalid", {"entry": at, "variable": variable})
        for variable, (low, high) in (validity or {}).items()
        if variable not in variables or not low < high
    ]


# -- a parameter set (D5) -------------------------------------------------------------------------


def _set_errors(record: Mapping[str, Any]) -> list[Coded]:
    """D5: component keys unique; every entry index a component key; a `wilson_lambda` entry with
    two distinct indices and a value above 0; the set's domain in `T` and `P`. A broken rule is
    `record_schema_invalid` at the member, the domain's `validity_range_invalid`."""
    found = _duplicates(record["components"], "components", lambda item: item["key"])
    keys = {item["key"] for item in record["components"]}
    for index, entry in enumerate(record["entries"]):
        found += _indices_errors(pointer("/entries", index), entry, keys)
    found += _validity_errors("/validity", record.get("validity"), CONSTANT_VARIABLES)
    return found


def _indices_errors(at: str, entry: Mapping[str, Any], keys: set[str]) -> list[Coded]:
    indices = entry["indices"]
    found = [
        schema_invalid(pointer(pointer(at, "indices"), position))
        for position, key in enumerate(indices)
        if key not in keys
    ]
    if entry["property"] == "wilson_lambda":
        if len(indices) != 2 or indices[0] == indices[1]:
            found.append(schema_invalid(pointer(at, "indices")))
        if entry.get("value", 0) <= 0:
            found.append(schema_invalid(pointer(at, "value")))
    return found


# -- findings -------------------------------------------------------------------------------------


def _fit_findings(record: Mapping[str, Any]) -> list[Coded]:
    """`fit_inputs_unhashed(<entry>)` for every fitted or generated entry or Constant without
    `inputs` (D4, R-924)."""
    return [Coded("fit_inputs_unhashed", {"entry": at}) for at in _unhashed(record)]


def _unhashed(record: Mapping[str, Any]) -> Iterator[str]:
    for at, quantity in quantities(record):
        provenance = quantity["provenance"]
        if provenance["derivation"] != "direct" and not provenance.get("inputs"):
            yield at
