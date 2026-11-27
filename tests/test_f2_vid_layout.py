"""F2-WO3: the variable ids of ADR 0062 D7 and the material layout of D8.

E-F2-5 (the variable-id part; WO1 did the phase-id part): on 10^4 generated structures with
adversarial user ids and qualified phases on every family, the test-only parser
(`tests/f2/vid_parse.py`) inverts the rendering, no two structures render alike, and no v2 id equals
any legacy-form id of any structure. `nTP-v1` keeps today's ids exactly.

E-F2-6: over generated definitions of every template (true and group bases, partition and
non-partition attributes, classed and not, both thermal coordinates) in a shuffled variable order
with foreign variables mixed in, `layout.state(x, c)` equals, bit for bit, the state built here
independently from the definition (D3's order, written out again below), and the code path holds no
id parsing: `vid_parse` is not importable from `src/`, nothing in `src/` imports it, and the layout
and id modules call no string-splitting method. F2-WO4's fixtures and WO5's probes extend this
check to their states.
"""

from __future__ import annotations

import ast
import json
import random
import struct
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from f2.vid_parse import parse_vid
from test_f2_material_types import ADVERSARIAL_COMPONENTS, _random_phase

from openflowsheet.material.basis import group_molar_masses
from openflowsheet.material.definitions import normalise_instance, species_basis
from openflowsheet.material.layout import (
    AttributeKind,
    ComponentFacts,
    ConnectionInput,
    MaterialFacts,
    MaterialLayout,
    MaterialState,
    SubstreamState,
)
from openflowsheet.material.phase_id import FAMILIES, PhaseId
from openflowsheet.material.vid import (
    CONNECTION_FIELDS,
    POINT_FIELDS,
    VariableId,
    legacy_variable_id,
)
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# ------------------------------------------------------------------------- E-F2-5: variable ids

# Adversarial ids (E-F2-5): a dotted id ending in a digit, field names, family names, a colon,
# digits, `model`, and an id that is both a component id and a model id (`langmuir-co2`).
ADVERSARIAL_IDS = [*ADVERSARIAL_COMPONENTS, "a", "h", "P", "Q", "s", "beta", "v", "1", "2", "10"]
_ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def _uid(rng: random.Random) -> str:
    if rng.random() < 0.6:
        return rng.choice(ADVERSARIAL_IDS)
    return rng.choice(_ALNUM) + "".join(
        rng.choice(_ALNUM + "_.:-") for _ in range(rng.randint(0, 5))
    )


def _random_vid(rng: random.Random) -> VariableId:
    owner = tuple(_uid(rng) for _ in range(rng.choice([1, 1, 1, 2, 3])))
    if rng.random() < 0.5:  # a connection variable
        field = rng.choice(CONNECTION_FIELDS)
        if field == "n":
            return VariableId(
                owner, field, tuple(_uid(rng) for _ in range(rng.randint(1, 2))), _uid(rng)
            )
        if field == "a":
            return VariableId(
                owner, field, tuple(_uid(rng) for _ in range(rng.randint(1, 3))), _uid(rng)
            )
        return VariableId(owner, field)
    substream = _uid(rng) if rng.random() < 0.3 else None
    phase = _random_phase(rng) if rng.random() < 0.7 else None
    index = tuple(_uid(rng) for _ in range(rng.randint(0, 2)))
    return VariableId(owner, rng.choice(POINT_FIELDS), index, substream, _uid(rng), phase)


def _legacy_forms(vid: VariableId) -> set[str]:
    """Every legacy-form id of the structure's owner and indices (`models`' naming)."""
    owner = "/".join(vid.owner)
    names = {owner, *vid.owner}
    forms = {temperature_id(name) for name in names} | {pressure_id(name) for name in names}
    forms |= {duty_id(name) for name in names}
    forms |= {flow_id(name, part) for name in names for part in vid.index}
    return forms


def test_e_f2_5_variable_ids_render_injectively_and_parse_back() -> None:
    """[gen] 10^4 variable structures: parse inverts render, no two structures render alike, each
    id holds one `~`, and no v2 id is a legacy-form id of any structure."""
    rng = random.Random(6207)
    seen: dict[str, VariableId] = {}
    legacy: set[str] = set()
    qualified = {family: 0 for family in FAMILIES}
    for _ in range(10_000):
        vid = _random_vid(rng)
        text = vid.render()
        assert parse_vid(text) == vid, text
        assert seen.setdefault(text, vid) == vid, text
        assert text.count("~") == 1
        legacy |= _legacy_forms(vid)
        if vid.phase is not None and vid.phase.qualifier is not None:
            qualified[vid.phase.family] += 1
    print(f"E-F2-5 (variable ids): 10000 structures, {len(seen)} distinct, {len(legacy)} legacy")
    assert len(seen) > 8_000
    assert min(qualified.values()) > 200  # qualified phases on every family (Q4.A5)
    assert not set(seen) & legacy
    assert all("~" not in form for form in legacy)


@pytest.mark.parametrize(
    ("vid", "text"),
    [
        (VariableId(("S1",), "n", ("water",), "mixed"), "S1@mixed~n[water]"),
        (VariableId(("S1",), "n", ("CaCO3", "2"), "solid"), "S1@solid~n[CaCO3][2]"),
        (VariableId(("S1",), "a", ("probe.moments", "2"), "solid"), "S1@solid~a[probe.moments][2]"),
        (VariableId(("S1",), "h"), "S1~h"),
        (VariableId(("E1",), "Q"), "E1~Q"),
        (
            VariableId(("u", "v"), "T", (), None, "p", PhaseId("LIQUID", "a.2", 2)),
            "u/v#p#LIQUID(a.2).2~T",
        ),
        (
            VariableId(("u",), "beta", (), None, "p", PhaseId("SOLID", "model=n", 1)),
            "u#p#SOLID(model=n)~beta",
        ),
        (VariableId(("u",), "n", ("x:y",), "s", "p"), "u@s#p~n[x:y]"),
    ],
)
def test_d7_examples_render_and_parse(vid: VariableId, text: str) -> None:
    assert vid.render() == text
    assert parse_vid(text) == vid


@pytest.mark.parametrize(
    "text",
    [
        "S1",  # no `~`
        "S1~~T",
        "S1~T~P",
        "~T",  # no owner
        "S1/~T",
        "S1~n[water]",  # `n` of a connection is on a substream
        "S1@mixed~T",  # `T` of a connection is not
        "S1~T[1]",  # `T` of a connection takes no index
        "S1@m~n",  # `n` takes an index
        "S1@m~n[a][b][c]",  # at most two
        "S1~x",  # not in the field table
        "u#p~Q",  # `Q` is not a state-point field
        "u#p#LIQUID.1~T",  # D6: `.1` does not parse
        "u#p#GAS~T",
        "u#p#LIQUID#x~T",
        "S1@m~n[a",
        "S1@m~n[]",
        "S1@m~n[a]x",
    ],
)
def test_d7_text_no_variable_renders_as_does_not_parse(text: str) -> None:
    with pytest.raises(ValueError):
        parse_vid(text)


def test_d7_a_phase_needs_a_point_and_ids_are_in_the_alphabet() -> None:
    with pytest.raises(ValueError):
        VariableId(("S1",), "T", (), None, None, PhaseId("VAPOR", None, 1))
    for bad in ("", "a~b", "a#b", "a@b", "a/b", "a[b", "-a", "a b"):
        with pytest.raises(ValueError):
            VariableId(("u",), "T", (), None, bad)
        with pytest.raises(ValueError):
            VariableId((bad,), "h")


def test_d7_ntp_v1_keeps_todays_ids() -> None:
    """`legacy_variable_id` is `models`' naming (the `nTP-v1` layout's ids, E-F2-6 below)."""
    for stream in ("S1", "a.2", "x:y"):
        for component in ADVERSARIAL_COMPONENTS:
            assert legacy_variable_id(stream, "n", component) == flow_id(stream, component)
        assert legacy_variable_id(stream, "T") == temperature_id(stream)
        assert legacy_variable_id(stream, "P") == pressure_id(stream)
    with pytest.raises(ValueError):
        legacy_variable_id("S1", "h")


# ---------------------------------------------------------------------------- E-F2-6: the layout

KINDS = {
    "probe.partition": AttributeKind("component", True, True, "molar_flow"),
    "probe.classes": AttributeKind("substream", False, True, "number_flow"),
    "probe.moments": AttributeKind("component", False, True, "number_flow"),
    "probe.scalar": AttributeKind("substream", False, False, "mass_fraction"),
    "probe.each": AttributeKind("component", False, False, "number_flow"),
}
POOL = ["a.2", "n", "LIQUID", "x:y", "123", "model", "T", "co2", "h2o", "1"]
MASS = {"mol": 0.018, "segment_mol": 0.104, "kg": None}


def _facts(rng: random.Random) -> MaterialFacts:
    bases = {c: rng.choice(["mol", "mol", "kg", "segment_mol"]) for c in POOL}
    facts = {
        c: ComponentFacts(b, MASS[b] and MASS[b] * (1 + POOL.index(c))) for c, b in bases.items()
    }
    return MaterialFacts(tuple(POOL), facts, KINDS)


def _grid(rng: random.Random, gid: str) -> dict[str, Any]:
    return {
        "id": gid,
        "quantity_kind": "length",
        "edges": [float(e) for e in range(rng.randint(2, 5))],
    }


def _attribute(kind: str, components: list[str] | None, grid: str | None) -> dict[str, Any]:
    return {"kind": kind, "version": "1.0.0", "components": components, "grid": grid}


def _substream(
    rng: random.Random, sid: str, kind: str, facts: MaterialFacts, used: set[str]
) -> dict[str, Any]:
    free = [c for c in POOL if c not in used]
    if kind == "nonconventional":
        free = [c for c in free if facts.component_facts[c].amount_basis == "kg"]
    components = sorted(rng.sample(free, min(len(free), rng.randint(1, 4))), key=POOL.index)
    used.update(components)
    if not components:
        return {"components": []}
    grids = [_grid(rng, "g1"), _grid(rng, "n")]
    attributes = []
    molar = [c for c in components if facts.component_facts[c].amount_basis == "mol"]
    if kind == "mixed" and len(molar) == len(components) >= 2 and rng.random() < 0.4:
        groups = [
            {"id": "n", "content": {components[0]: 1}},
            {"id": "T", "content": {c: 1 for c in components[1:]}},
        ]
        rng.shuffle(groups)
        basis = {"preset": None, "species": components, "groups": groups, "fast_reactions": None}
    else:
        basis = {"preset": "true"}
        if rng.random() < 0.5:
            attributes.append(
                _attribute("probe.partition", rng.sample(components, 1), rng.choice(["g1", "n"]))
            )
    if rng.random() < 0.5:
        attributes.append(_attribute("probe.classes", None, "g1"))
    if rng.random() < 0.5:
        attributes.append(_attribute("probe.moments", rng.sample(components, len(components)), "n"))
    if rng.random() < 0.5:
        attributes.append(_attribute("probe.scalar", None, None))
    if rng.random() < 0.5:
        attributes.append(_attribute("probe.each", components[-1:], None))
    rng.shuffle(attributes)
    return {
        "id": sid,
        "kind": kind,
        "components": components,
        "conserved_basis": basis,
        "grids": grids,
        "attributes": attributes,
    }


def _instance(rng: random.Random, facts: MaterialFacts) -> dict[str, Any]:
    template = rng.choice(
        ["mat-v1", "mat-v1", "mat-v1", "nTP-v1", "heat-v1", "work-v1", "signal-v1"]
    )
    if template == "signal-v1":
        return {"template": template, "quantity_kind": rng.choice(["temperature", "pressure"])}
    if template != "mat-v1":
        return {"template": template}
    used: set[str] = set()
    substreams = [_substream(rng, "mixed", "mixed", facts, used)]
    for sid, kind in (("s", "solid"), ("NC", "nonconventional")):
        if rng.random() < 0.5 and any(c not in used for c in POOL):
            substreams.append(_substream(rng, sid, kind, facts, used))
    substreams = [s for s in substreams if s["components"]]
    return {
        "template": "mat-v1",
        "thermal_coordinate": rng.choice(["h_mass", "T"]),
        "substreams": substreams,
    }


# The independent expectation: D3's carried-index order written out again, with each id spelled by
# f-string (not by `VariableId`), as (id, substream or None, role) with role "carried", "attribute",
# "thermal", "P" or "value".
Expected = list[tuple[str, str | None, str]]


def _expected(connection: str, instance: Mapping[str, Any], facts: MaterialFacts) -> Expected:
    template = instance["template"]
    if template == "nTP-v1":
        rows: Expected = [(f"{connection}.n.{c}", "mixed", "carried") for c in facts.components]
        return [*rows, (f"{connection}.T", None, "thermal"), (f"{connection}.P", None, "P")]
    if template != "mat-v1":
        field = {"heat-v1": "Q", "work-v1": "W", "signal-v1": "s"}[template]
        return [(f"{connection}~{field}", None, "value")]
    rows = []
    for sub in normalise_instance(instance)["substreams"]:
        sid, grids = sub["id"], {g["id"]: len(g["edges"]) - 1 for g in sub["grids"]}
        head = f"{connection}@{sid}"
        if "groups" in sub["conserved_basis"]:
            rows += [
                (f"{head}~n[{g['id']}]", sid, "carried") for g in sub["conserved_basis"]["groups"]
            ]
        else:
            partition = {
                c: grids[a["grid"]]
                for a in sub["attributes"]
                if a["kind"] == "probe.partition"
                for c in a["components"]
            }
            for c in sub["components"]:
                if c in partition:
                    rows += [
                        (f"{head}~n[{c}][{k}]", sid, "carried") for k in range(1, partition[c] + 1)
                    ]
                else:
                    rows.append((f"{head}~n[{c}]", sid, "carried"))
        for a in sub["attributes"]:
            kind = KINDS[a["kind"]]
            if kind.partition:
                continue
            targets = (
                [""]
                if a["components"] is None
                else [f"[{c}]" for c in sub["components"] if c in a["components"]]
            )
            classes = [f"[{k}]" for k in range(1, grids[a["grid"]] + 1)] if kind.classed else [""]
            rows += [
                (f"{head}~a[{a['kind']}]{t}{k}", sid, "attribute") for t in targets for k in classes
            ]
    thermal = "h" if instance["thermal_coordinate"] == "h_mass" else "T"
    return [*rows, (f"{connection}~{thermal}", None, "thermal"), (f"{connection}~P", None, "P")]


def _value(rng: random.Random) -> float:
    return rng.choice([0.0, -0.0, 5e-324, 1.0, rng.uniform(-1e3, 1e3), rng.uniform(0.0, 1e-300)])


def _bits(state: MaterialState) -> list[bytes]:
    values = [state.thermal, state.pressure]
    for sub in state.substreams:
        values += [*sub.carried, *sub.attributes]
    return [struct.pack("<d", v) for v in values]


def _expected_state(
    connection: str,
    instance: Mapping[str, Any],
    sha: str,
    rows: Expected,
    value: Mapping[str, float],
) -> MaterialState:
    order: list[str] = []
    for _, sid, _ in rows:
        if sid is not None and sid not in order:
            order.append(sid)
    substreams = tuple(
        SubstreamState(
            sid,
            tuple(value[v] for v, s, role in rows if s == sid and role == "carried"),
            tuple(value[v] for v, s, role in rows if s == sid and role == "attribute"),
        )
        for sid in order
    )
    (thermal,) = [value[v] for v, _, role in rows if role == "thermal"]
    (pressure,) = [value[v] for v, _, role in rows if role == "P"]
    coordinate = "T" if instance["template"] == "nTP-v1" else instance["thermal_coordinate"]
    return MaterialState(connection, sha, coordinate, substreams, thermal, pressure)


def _cases(
    seed: int, count: int
) -> Iterator[tuple[MaterialFacts, list[ConnectionInput], dict[str, Expected]]]:
    rng = random.Random(seed)
    for case in range(count):
        facts = _facts(rng)
        given, expected = [], {}
        for k in range(rng.randint(1, 5)):
            connection = rng.choice(["S", "n", "a.2", "x:y", "LIQUID"]) + str(k)
            instance = _instance(rng, facts)
            sha = f"{case:032x}{k:032x}"
            given.append(ConnectionInput(connection, instance.get("template", ""), instance, sha))
            expected[connection] = _expected(connection, instance, facts)
        yield facts, given, expected


def test_e_f2_6_the_layout_reads_each_state_as_built_from_its_definition() -> None:
    """[gen] 2000 revisions, a shuffled variable order with foreign variables: every material
    connection's `layout.state(x, c)` is the independently built state bit for bit, every
    energy and signal connection's `value` its variable, each slot's `variable_index` its id's
    place."""
    rng = random.Random(6206)
    states = slots = 0
    seen: Counter[str] = Counter()
    templates: set[str] = set()
    for facts, given, expected in _cases(6206, 2_000):
        ids = [v for rows in expected.values() for v, _, _ in rows]
        ids += [f"U{k}.x" for k in range(rng.randint(0, 4))] + [f"U~W{k}" for k in range(2)]
        rng.shuffle(ids)
        x = [_value(rng) for _ in ids]
        value = dict(zip(ids, x, strict=True))
        layout = MaterialLayout.build(given, facts, ids)
        for item in given:
            rows = expected[item.connection]
            placed = layout.connection(item.connection)
            templates.add(placed.template)
            for sub in item.instance.get("substreams", ()):
                seen["group basis"] += "groups" in sub["conserved_basis"]
                seen.update(a["kind"] for a in sub["attributes"])
            seen.update(slot.field for slot in placed.slots if slot.substream is None)
            assert [ids[s.variable_index] for s in placed.slots] == [v for v, _, _ in rows]
            assert [placed.variable_id(s) for s in placed.slots] == [v for v, _, _ in rows]
            slots += len(rows)
            if rows[0][2] == "value":
                assert struct.pack("<d", layout.value(x, item.connection)) == struct.pack(
                    "<d", value[rows[0][0]]
                )
                with pytest.raises(ValueError):
                    layout.state(x, item.connection)
                continue
            found = layout.state(x, item.connection)
            built = _expected_state(
                item.connection, item.instance, item.definition_sha256, rows, value
            )
            assert found == built and _bits(found) == _bits(built)
            assert found.is_dormant == all(
                v == 0.0 for v, s, r in [(value[i], s, r) for i, s, r in rows] if r == "carried"
            )
            states += 1
    print(f"E-F2-6: {states} material states, {slots} slots, {sorted(templates)}, {dict(seen)}")
    assert templates == {"nTP-v1", "mat-v1", "heat-v1", "work-v1", "signal-v1"}
    assert states > 3_000
    assert min(seen[k] for k in [*KINDS, "group basis", "h", "T", "P", "Q", "W", "s"]) > 50


def test_d8_the_molar_masses_and_quantity_kinds_per_slot() -> None:
    """M per carried slot: the record's, 1 for `kg`, a class its component's, M_g for a group basis
    (Q3.R7, `material.basis`); each slot's quantity kind by its field and basis."""
    facts = MaterialFacts(
        ("A", "B", "C", "K"),
        {
            "A": ComponentFacts("mol", 0.016),
            "B": ComponentFacts("mol", 0.030),
            "C": ComponentFacts("segment_mol", 0.104),
            "K": ComponentFacts("kg", None),
        },
        KINDS,
    )
    instance = {
        "template": "mat-v1",
        "thermal_coordinate": "h_mass",
        "substreams": [
            {
                "id": "aq",
                "kind": "mixed",
                "components": ["A", "B"],
                "conserved_basis": {
                    "preset": None,
                    "species": ["A", "B"],
                    "groups": [
                        {"id": "g2", "content": {"B": 1}},
                        {"id": "g1", "content": {"A": 1, "B": 1}},
                    ],
                    "fast_reactions": None,
                },
                "grids": [],
                "attributes": [],
            },
            {
                "id": "s",
                "kind": "solid",
                "components": ["C", "K"],
                "conserved_basis": {"preset": "true"},
                "grids": [{"id": "g", "quantity_kind": "length", "edges": [0.0, 1.0, 2.0]}],
                "attributes": [_attribute("probe.partition", ["K"], "g")],
            },
        ],
    }
    ids = ["S~h", "S~P", "S@aq~n[g1]", "S@aq~n[g2]", "S@s~n[C]", "S@s~n[K][1]", "S@s~n[K][2]"]
    layout = MaterialLayout.build([ConnectionInput("S", "d1", instance, "0" * 64)], facts, ids)
    placed = layout.connection("S")
    aq, s = placed.substreams
    basis = species_basis(normalise_instance(instance)["substreams"][0], {"A": 0, "B": 0})
    assert aq.molar_masses == group_molar_masses(basis, [0.016, 0.030]).group_masses
    assert aq.molar_masses == pytest.approx((0.016, 0.014), rel=1e-15)
    assert s.molar_masses == (0.104, 1.0, 1.0)
    assert [(slot.field, slot.index, slot.quantity_kind) for slot in placed.slots] == [
        ("n", ("g1",), "molar_flow"),
        ("n", ("g2",), "molar_flow"),
        ("n", ("C",), "segment_molar_flow"),
        ("n", ("K", 1), "mass_flow"),
        ("n", ("K", 2), "mass_flow"),
        ("h", (), "specific_enthalpy"),
        ("P", (), "pressure"),
    ]
    assert [slot.variable_index for slot in placed.slots] == [2, 3, 4, 5, 6, 0, 1]


def test_d8_material_layout_document_holds_no_float_and_no_variable_index() -> None:
    """`solution-state-v2`'s `material_layout`: the slots in order without `variable_index`, and no
    float anywhere (it is R0, D8)."""

    def floats(node: object) -> int:
        if isinstance(node, float):
            return 1
        if isinstance(node, dict):
            return sum(floats(v) for v in node.values())
        if isinstance(node, list):
            return sum(floats(v) for v in node)
        return 0

    for facts, given, expected in _cases(17, 200):
        ids = [v for rows in expected.values() for v, _, _ in rows]
        document = MaterialLayout.build(given, facts, ids).document()
        assert json.loads(json.dumps(document)) == document
        assert floats(document) == 0
        for item, entry in zip(given, document, strict=True):
            assert set(entry) == {"connection", "definition", "definition_sha256", "slots"}
            assert entry["definition_sha256"] == item.definition_sha256
            assert all(
                set(slot) == {"substream", "field", "index", "quantity_kind"}
                for slot in entry["slots"]
            )
            assert len(entry["slots"]) == len(expected[item.connection])


def test_d8_build_refuses_what_it_cannot_place() -> None:
    facts = MaterialFacts(("A",), {"A": ComponentFacts("mol", 0.016)}, KINDS)
    ntp = ConnectionInput("S", "nTP-v1", {"template": "nTP-v1"}, "0" * 64)
    with pytest.raises(ValueError, match="not in the variable order"):
        MaterialLayout.build([ntp], facts, ["S.n.A", "S.T"])
    with pytest.raises(ValueError, match="twice"):
        MaterialLayout.build([ntp], facts, ["S.n.A", "S.T", "S.P", "S.T"])
    with pytest.raises(ValueError, match="once"):
        MaterialLayout.build([ntp, ntp], facts, ["S.n.A", "S.T", "S.P"])
    layout = MaterialLayout.build([ntp], facts, ["S.P", "S.n.A", "S.T"])
    assert layout.state([1e5, 2.5, 300.0], "S") == MaterialState(
        "S", "0" * 64, "T", (SubstreamState("mixed", (2.5,), ()),), 300.0, 1e5
    )
    with pytest.raises(ValueError):
        layout.value([1e5, 2.5, 300.0], "S")


# --------------------------------------------------------------------- E-F2-6: no id parsing


def test_e_f2_6_vid_parse_is_not_importable_from_src() -> None:
    """With only `src/` on the path, neither parser imports; no module of `src/` names them."""
    probe = "\n".join(
        [
            "import importlib.util, sys",
            f"sys.path.insert(0, {str(SRC)!r})",
            "def absent(name):",
            "    try:",
            "        return importlib.util.find_spec(name) is None",
            "    except ModuleNotFoundError:",
            "        return True",
            "names = ('vid_parse', 'f2', 'f2.vid_parse', 'phase_id_parse',",
            "         'openflowsheet.material.vid_parse')",
            "print([absent(n) for n in names])",
        ]
    )
    found = subprocess.run(
        [sys.executable, "-I", "-c", probe],
        capture_output=True,
        text=True,
        check=True,
    )
    assert found.stdout.strip() == "[True, True, True, True, True]"
    for path in (SRC / "openflowsheet").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or "", *(alias.name for alias in node.names)]
            else:
                continue
            assert not [n for n in names if "_parse" in n or n.split(".")[0] == "f2"], path


@pytest.mark.parametrize("module", ["layout.py", "vid.py"])
def test_e_f2_6_the_layout_and_id_modules_split_no_string(module: str) -> None:
    tree = ast.parse((SRC / "openflowsheet" / "material" / module).read_text(encoding="utf-8"))
    splitting = {"split", "rsplit", "partition", "rpartition", "find", "rfind", "removeprefix"}
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert not splitting & set(calls)
    assert "re.match" not in ast.unparse(tree) and "re.search" not in ast.unparse(tree)
