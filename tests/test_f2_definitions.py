"""F2-WO2 (ADR 0062 D3, D5, D6): connection definitions, the built-in templates and families, and
the payload envelopes of ADR 0062's F1 kinds.

- **Template SHAs pinned.** Each built-in template's and family's `descriptor_sha256` is a
  regression constant (self-generated, held so that any edit of a template, of its instance
  grammar or of the generator shows here and in `scripts/registry_builtin.py --check`). `nTP-v1`'s
  is the legacy table's, unchanged by F2. `nTP-v1`'s `definition_sha256` is checked against the
  SHA-256 of its canonical preimage written out byte by byte (D3: body `{}`).
- **Instances.** `schemas/connection-definition.schema.json` admits each template's instance and
  refuses one wrong member at a time; D3's normalisation (groups by id, attributes by (kind,
  components), lists as given) makes the SHA independent of those orders and of key order, while
  every core field moves it.
- **Registration.** The templates and families are built-ins of the process registry, `preview`
  while ADR 0062 is Proposed; the five payload envelopes (D5, D6) validate a descriptor of their
  kind.
- **Bases.** `species_basis` maps a substream's conserved basis onto Q3.R1's (S, A, z, R).
"""

from __future__ import annotations

import copy
import hashlib
from fractions import Fraction
from typing import Any

import pytest

from openflowsheet.material.basis import check_basis
from openflowsheet.material.definitions import (
    LEGACY_TEMPLATE,
    TEMPLATES,
    definition_body,
    definition_sha256,
    instance_problems,
    normalise_instance,
    species_basis,
)
from openflowsheet.material.phase_id import FAMILIES
from openflowsheet.registry import default_registry, discovery
from openflowsheet.registry.descriptor import descriptor_problem, descriptor_sha256, stability

#: Regression constants: `descriptor_sha256` of each built-in of `registry/builtin/material.json`
#: (F2-WO2) and of the legacy `nTP-v1` (F1, unchanged).
PINNED: dict[tuple[str, str], str] = {
    ("connection_definition", "nTP-v1"): (
        "d0a6d025db17189521068be4fca6814ef3f6b1a09382aa9794f504302f77cc1e"
    ),
    ("connection_definition", "mat-v1"): (
        "7d05658de6941ae67bef1bc5f23a89fe26f70ca6f1ff2f05223944bfca23e025"
    ),
    ("connection_definition", "heat-v1"): (
        "e6b7162867fcc3116e85550f496076fbd0d567eed549c8272ae10898d7683ae9"
    ),
    ("connection_definition", "work-v1"): (
        "d987e1973ff5712103f4a3a78dccf2e424eafd2b6a780929de66dbede6add7dd"
    ),
    ("connection_definition", "signal-v1"): (
        "ae61cfa1ae8564ba12f853481a2eb2484a629c7de05a86e14f22d8c471eb705c"
    ),
    ("phase_family", "VAPOR"): "1b3085f71df33b2b1e410d15c3e4e277ab472eaa6d8a0fb8eaa2cd8acae06ff7",
    ("phase_family", "LIQUID"): "20d0ccc6fa07c42571afcd71b26025b309cf36df797b1907c4e4db442418ed13",
    ("phase_family", "FLUID"): "8834a6ef064b3e90cd242e72b864493ed6108d4663c45568d4dd583358da00f8",
    ("phase_family", "SOLID"): "8f1234acf3e0b75cd7c5eebbf06ff7f7b4cb9a49a26bf7f2a600564f864addd7",
}


def _builtins() -> dict[tuple[str, str], dict[str, Any]]:
    tables = discovery.builtin_tables()
    return {
        (row["kind"], row["id"]): row
        for name in ("legacy", "material")
        for row in tables[name]
        if row["kind"] in ("connection_definition", "phase_family")
    }


def _mat() -> dict[str, Any]:
    """A `mat-v1` instance with a `mixed` and a `solid` substream, a group basis over NaCl-H2O
    with the salt solid, and a classed attribute on a grid (E-F2-2's ingredients)."""
    return {
        "template": "mat-v1",
        "thermal_coordinate": "h_mass",
        "substreams": [
            {
                "id": "liquor",
                "kind": "mixed",
                "components": ["Na_p", "Cl_m", "NaCl", "H2O"],
                "conserved_basis": {
                    "preset": "apparent",
                    "species": ["Na_p", "Cl_m", "NaCl", "H2O"],
                    "groups": [
                        {"id": "NaCl", "content": {"Na_p": 1, "NaCl": 1}},
                        {"id": "H2O", "content": {"H2O": 1}},
                    ],
                    "fast_reactions": "speciation",
                },
                "grids": [],
                "attributes": [],
            },
            {
                "id": "crystals",
                "kind": "solid",
                "components": ["NaCl"],
                "conserved_basis": {"preset": "true"},
                "grids": [
                    {"id": "psd", "quantity_kind": "dimensionless", "edges": [1e-6, 1e-5, 1e-4]}
                ],
                "attributes": [
                    {
                        "kind": "probe.partition",
                        "version": "1.0.0",
                        "components": ["NaCl"],
                        "grid": "psd",
                    },
                    {"kind": "probe.moments", "version": "1.0.0", "components": None, "grid": None},
                ],
            },
        ],
    }


# -- template SHAs ------------------------------------------------------------------------------


def test_every_built_in_template_and_family_is_pinned() -> None:
    found = _builtins()
    assert set(found) == set(PINNED)
    assert {name for kind, name in found if kind == "connection_definition"} == {
        LEGACY_TEMPLATE,
        *TEMPLATES,
    }
    assert {name for kind, name in found if kind == "phase_family"} == set(FAMILIES)


@pytest.mark.parametrize("key", sorted(PINNED))
def test_template_sha_is_pinned(key: tuple[str, str]) -> None:
    assert descriptor_sha256(_builtins()[key]) == PINNED[key]


def test_ntp_v1_definition_sha_is_its_canonical_preimage() -> None:
    held = PINNED[("connection_definition", "nTP-v1")]
    preimage = b'{"body":{},"template":["nTP-v1","1.0.0","' + held.encode("ascii") + b'"]}'
    assert definition_sha256({"template": "nTP-v1"}, "1.0.0", held) == (
        hashlib.sha256(preimage).hexdigest()
    )
    assert definition_body({"template": "nTP-v1"}) == {}


def test_a_template_names_its_instance_grammar() -> None:
    for name, template in TEMPLATES.items():
        payload = _builtins()[("connection_definition", name)]["payload"]
        named = payload["instance_schema"]
        assert (named["path"], named["pointer"]) == (
            "_data/schemas/connection-definition.schema.json",
            template.pointer,
        )


def test_the_built_ins_are_registered_and_preview_while_adr_0062_is_proposed() -> None:
    registry = default_registry()
    for kind, name in PINNED:
        entry = registry.resolve(kind, name)
        assert entry.origin == "builtin"
        expected = "core" if name == LEGACY_TEMPLATE else "preview"
        assert entry.stability == expected, (kind, name)
    assert [registry.resolve("phase_family", name).id for name in FAMILIES] == [
        "VAPOR",
        "LIQUID",
        "FLUID",
        "SOLID",
    ]


# -- instances ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "instance",
    [
        {"template": "nTP-v1"},
        {"template": "heat-v1"},
        {"template": "work-v1"},
        {"template": "signal-v1", "quantity_kind": "temperature"},
        _mat(),
    ],
    ids=lambda instance: instance["template"],
)
def test_each_template_instance_is_schema_valid(instance: dict[str, Any]) -> None:
    assert instance_problems(instance) == []


def _broken(path: tuple[Any, ...], value: Any) -> dict[str, Any]:
    instance = _mat()
    node: Any = instance
    for part in path[:-1]:
        node = node[part]
    if value is KeyError:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return instance


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("template",), "mat-v2"),
        (("thermal_coordinate",), "s_mass"),
        (("substreams",), []),
        (("substreams", 0, "kind"), "liquid"),
        (("substreams", 0, "components"), []),
        (("substreams", 0, "grids"), KeyError),
        (("substreams", 0, "conserved_basis", "groups", 0, "content", "Cl_m"), 0),
        (("substreams", 0, "conserved_basis", "groups", 0, "content", "Na_p"), 1.5),
        (("substreams", 0, "conserved_basis", "preset"), "true"),
        (("substreams", 1, "grids", 0, "edges"), [1e-6]),
        (("substreams", 1, "grids", 0, "quantity_kind"), "furlong"),
        (("substreams", 1, "attributes", 0, "version"), "1.0"),
        (("substreams", 1, "id"), "a/b"),
        (("extra",), 1),
    ],
    ids=lambda item: "/".join(map(str, item)) if isinstance(item, tuple) else str(item)[:12],
)
def test_one_wrong_member_is_refused(path: tuple[Any, ...], value: Any) -> None:
    assert instance_problems(_broken(path, value)) != []


def test_signal_v1_needs_its_quantity_kind() -> None:
    assert instance_problems({"template": "signal-v1"}) != []
    assert instance_problems({"template": "heat-v1", "quantity_kind": "heat_rate"}) != []


def test_normalisation_sorts_groups_and_attributes_and_is_idempotent() -> None:
    normal = normalise_instance(_mat())
    liquor, crystals = normal["substreams"]
    assert [group["id"] for group in liquor["conserved_basis"]["groups"]] == ["H2O", "NaCl"]
    assert [(a["kind"], a["components"]) for a in crystals["attributes"]] == [
        ("probe.moments", None),
        ("probe.partition", ["NaCl"]),
    ]
    assert liquor["components"] == ["Na_p", "Cl_m", "NaCl", "H2O"]
    assert normalise_instance(normal) == normal
    assert "template" not in definition_body(_mat())


def test_attributes_of_one_kind_order_by_components() -> None:
    instance = _mat()
    attributes = instance["substreams"][1]["attributes"]
    attributes[:] = [
        {"kind": "k", "version": "1.0.0", "components": ["b"], "grid": None},
        {"kind": "k", "version": "1.0.0", "components": ["a", "c"], "grid": None},
        {"kind": "k", "version": "1.0.0", "components": None, "grid": None},
        {"kind": "k", "version": "1.0.0", "components": ["a"], "grid": None},
    ]
    found = normalise_instance(instance)["substreams"][1]["attributes"]
    assert [a["components"] for a in found] == [None, ["a"], ["a", "c"], ["b"]]


SHA = PINNED[("connection_definition", "mat-v1")]


def test_the_sha_ignores_group_attribute_and_key_order() -> None:
    reference = definition_sha256(_mat(), "1.0.0", SHA)
    shuffled = _mat()
    shuffled["substreams"][0]["conserved_basis"]["groups"].reverse()
    shuffled["substreams"][1]["attributes"].reverse()
    reordered = {key: shuffled[key] for key in reversed(list(shuffled))}
    assert definition_sha256(reordered, "1.0.0", SHA) == reference


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("thermal_coordinate",), "T"),
        (("substreams", 0, "components"), ["Cl_m", "Na_p", "NaCl", "H2O"]),
        (("substreams", 0, "id"), "brine"),
        (("substreams", 0, "conserved_basis", "preset"), None),
        (("substreams", 0, "conserved_basis", "fast_reactions"), None),
        (("substreams", 0, "conserved_basis", "groups", 1, "content", "H2O"), 2),
        (("substreams", 1, "kind"), "nonconventional"),
        (("substreams", 1, "grids", 0, "edges"), [1e-6, 1e-5, 2e-4]),
        (("substreams", 1, "attributes", 0, "version"), "1.1.0"),
    ],
    ids=lambda item: "/".join(map(str, item)) if isinstance(item, tuple) else str(item)[:12],
)
def test_every_core_field_moves_the_sha(path: tuple[Any, ...], value: Any) -> None:
    changed = _broken(path, value)
    assert instance_problems(changed) == []
    assert definition_sha256(changed, "1.0.0", SHA) != definition_sha256(_mat(), "1.0.0", SHA)


def test_the_template_identity_moves_the_sha() -> None:
    base = definition_sha256(_mat(), "1.0.0", SHA)
    assert definition_sha256(_mat(), "1.0.1", SHA) != base
    assert definition_sha256(_mat(), "1.0.0", "0" * 64) != base


# -- payload envelopes (D5, D6) -----------------------------------------------------------------

PAYLOADS: dict[str, dict[str, Any]] = {
    "attribute_kind": {
        "scope": "component",
        "partition": False,
        "classed": True,
        "quantity_kind": "number_flow",
        "parent_kind": "molar_flow",
        "inequalities": [
            {"lhs": [[1.0, "m0"], [1.0, "m2"]], "rhs": [[1.0, "m1"]], "allowance": "tau_mono"}
        ],
    },
    "derived_quantity": {
        "inputs": [{"role": "stream", "endpoint_kind": "connection"}],
        "auxiliary_points": [
            {
                "name": "bubble",
                "spec": [["P", "pressure"], ["beta", "phase_fraction"]],
                "candidates": "method",
            }
        ],
        "output": "builtin",
        "quantity_kind": "temperature",
        "degeneracy": None,
        "expression": "builtin",
    },
    "kinetics_kind": {"writes": "source_terms", "indices": "any_carried"},
    "phase_family": {},
    "revision_section": {
        "schema": "https://example.org/schemas/acme-notes.schema.json",
        "reason": "site notes",
    },
}

BAD: list[tuple[str, dict[str, Any], str]] = [
    ("attribute_kind", {"scope": "stream"}, "/payload/scope"),
    ("attribute_kind", {"parent_kind": 3}, "/payload/parent_kind"),
    ("derived_quantity", {"expression": "a + b"}, "/payload/expression"),
    ("derived_quantity", {"output": {"vocabulary_item": "h", "x": 1}}, "/payload/output"),
    ("kinetics_kind", {"writes": "rates"}, "/payload/writes"),
    ("phase_family", {"order": 1}, "/payload"),
    ("revision_section", {"reason": ""}, "/payload/reason"),
]


def _descriptor(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "descriptor_format": "openflowsheet-extension-v1",
        "kind": kind,
        "id": "acme.thing",
        "version": "1.0.0",
        "title": "A thing",
        "status": "tested",
        "requires": [],
        "provides": [],
        "limitations": [],
        "platforms": ["any"],
        "pip_extra": None,
        "data_rights": None,
        "implementation": {"modules": [], "factory": None},
        "payload": payload,
    }


@pytest.mark.parametrize("kind", sorted(PAYLOADS))
def test_each_payload_envelope_admits_its_example(kind: str) -> None:
    assert descriptor_problem(_descriptor(kind, PAYLOADS[kind])) is None
    assert stability(kind, builtin=False, legacy_form=False) == "preview"


@pytest.mark.parametrize(("kind", "change", "pointer"), BAD, ids=lambda item: str(item)[:24])
def test_each_payload_envelope_refuses_a_wrong_member(
    kind: str, change: dict[str, Any], pointer: str
) -> None:
    payload = {**copy.deepcopy(PAYLOADS[kind]), **change}
    assert descriptor_problem(_descriptor(kind, payload)) == pointer


def test_derived_quantity_admits_a_vocabulary_output_and_listed_candidates() -> None:
    payload = copy.deepcopy(PAYLOADS["derived_quantity"])
    payload["output"] = {"vocabulary_item": "h_molar"}
    payload["auxiliary_points"][0]["candidates"] = ["LIQUID", "VAPOR"]
    assert descriptor_problem(_descriptor("derived_quantity", payload)) is None


# -- conserved bases ----------------------------------------------------------------------------


def test_species_basis_of_a_true_and_a_group_basis() -> None:
    liquor, crystals = _mat()["substreams"]
    charges = {"Na_p": 1, "Cl_m": -1, "NaCl": 0, "H2O": 0}
    dissolution = {"Na_p": 1, "Cl_m": 1, "NaCl": -1}
    grouped = species_basis(liquor, charges, [dissolution])
    assert grouped.groups == ("NaCl", "H2O")
    assert grouped.content == ((1, 0, 1, 0), (0, 0, 0, 1))
    assert grouped.reactions == ((Fraction(1), Fraction(1), Fraction(-1), Fraction(0)),)
    assert check_basis(grouped).valid
    assert not check_basis(species_basis(liquor, charges)).invariants_fixed  # Q3.A2 (b), R = ∅
    true = species_basis(crystals, charges)
    assert (true.species, true.content, true.reactions) == (("NaCl",), ((1,),), ())
    with pytest.raises(ValueError, match="outside the basis"):
        species_basis(liquor, charges, [{"K_p": 1}])
