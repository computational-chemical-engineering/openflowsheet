"""F2-WO6a: `solution-state-v2` (ADR 0062 D8), E-F2-10, and its R0 part.

- **Schema.** `schemas/solution-state-v2.schema.json` is registered and admits `document_v2`'s
  output; the v1 schema and the v1 cross-check refuse it (never read as the other version).
- **Round trip.** Written, serialised and read back, the document gives each slot's variable by
  its rendered id (D8: `variable_ids` order gives `variable_index`), so every connection's state
  read through the layout is the written one bit for bit (a `-0.0` reads `+0.0`: ADR 0002's
  canonical JSON, as for v1).
- **v1 untouched.** v2's v1 fields are `document`'s output exactly; `inconsistencies_v2` runs v1's
  checks 2 to 5 and the layout's own. `solution-state-v1` bytes of the corpus runs are F0's M4.
- **R0.** `r0_projection` adds `material_layout` and `state_points` for a v2 document only; no
  float enters; a definition SHA moves `r0_sha256`, a state value does not.
"""

from __future__ import annotations

import copy
import json
import random
import struct
from pathlib import Path
from typing import Any

import pytest
from f2.probes import DEFINITION, FACTS, SHA

from openflowsheet.canonical import canonical_json
from openflowsheet.material.layout import (
    ConnectionInput,
    MaterialLayout,
    MaterialState,
    draft_connection,
)
from openflowsheet.material.phase_id import PhaseId, phase_set, render_phase_set
from openflowsheet.run.identity import floats_in, r0_projection, r0_sha256
from openflowsheet.run.solution_state import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_V2,
    document,
    document_v2,
    inconsistencies,
    inconsistencies_v2,
    layout_variable_ids,
)
from openflowsheet.schema_check import DocumentSchemaError, validate_document

ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE_KEY = "target_state_sha256"
INPUTS = (
    ConnectionInput("S1", "crystals", DEFINITION, SHA),
    ConnectionInput("L1", "nTP-v1", {"template": "nTP-v1"}, "a1" * 32),
    ConnectionInput("Q1", "heat-v1", {"template": "heat-v1"}, "b2" * 32),
)
POINTS = (
    ("S1#p1", render_phase_set(phase_set([PhaseId("LIQUID", None, 1)]))),
    ("S1#p2", render_phase_set(phase_set([PhaseId("VAPOR", None, 1), PhaseId("LIQUID", None, 1)]))),
    ("L1#p1", "TWO_PHASE"),
)


def _problem(seed: int) -> tuple[list[str], list[float], MaterialLayout]:
    """The three connections' variables and two unit-owned ones, shuffled; a random state."""
    rng = random.Random(seed)
    ids = ["mix~T_out", "heat~duty"]
    for given in INPUTS:
        draft = draft_connection(given, FACTS)
        ids += [draft.variable_id(slot) for slot in draft.slots]
    rng.shuffle(ids)
    vector = [rng.choice([0.0, -0.0, rng.uniform(-1e6, 1e6), rng.random() * 1e-300]) for _ in ids]
    return ids, vector, MaterialLayout.build(INPUTS, FACTS, ids)


def _written(seed: int = 7) -> tuple[dict[str, Any], list[float], MaterialLayout]:
    ids, vector, layout = _problem(seed)
    return document_v2(ids, vector, layout, POINTS), vector, layout


def _bits(state: MaterialState) -> list[bytes]:
    values = [state.thermal, state.pressure]
    for substream in state.substreams:
        values += [*substream.carried, *substream.attributes]
    return [struct.pack("<d", value) for value in values]


def _certificate(state: dict[str, Any]) -> dict[str, Any]:
    return {CERTIFICATE_KEY: state["state_sha256"]}


# -- schema -------------------------------------------------------------------------------------


def test_e_f2_10_schema_is_registered_and_admits_the_writer() -> None:
    registry = json.loads((ROOT / "schemas" / "registry.json").read_text("utf-8"))
    assert "solution-state-v2.schema.json" in registry
    state, _, _ = _written()
    validate_document("solution-state-v2.schema.json", state)
    assert state["schema_version"] == SCHEMA_VERSION_V2 == "solution-state-v2"
    assert inconsistencies_v2(state, _certificate(state)) == ()


def test_e_f2_10_never_read_as_v1() -> None:
    state, _, _ = _written()
    with pytest.raises(DocumentSchemaError):
        validate_document("solution-state.schema.json", state)
    assert inconsistencies(state, _certificate(state))[0].startswith("schema(")
    v1 = document(state["variable_ids"], list(state["variables"].values()))
    assert inconsistencies_v2(v1, _certificate(v1))[0].startswith("schema(")


# -- round trip ---------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(25))
def test_e_f2_10_round_trip_gives_each_state_bitwise(seed: int) -> None:
    state, vector, layout = _written(seed)
    read = json.loads(canonical_json(state))
    assert read == state
    assert canonical_json(read) == canonical_json(state)
    positions = {name: i for i, name in enumerate(read["variable_ids"])}
    indices = []
    for entry in read["material_layout"]:
        indices += [positions[name] for name in layout_variable_ids([entry])]
    assert indices == [slot.variable_index for c in layout.connections for slot in c.slots]
    x = [read["variables"][name] for name in read["variable_ids"]]
    written = [value + 0.0 for value in vector]  # ADR 0002's canonical JSON writes -0.0 as 0
    for connection in ("S1", "L1"):
        assert _bits(layout.state(x, connection)) == _bits(layout.state(written, connection))
    assert struct.pack("<d", layout.value(x, "Q1")) == struct.pack(
        "<d", layout.value(written, "Q1")
    )
    assert [(p["point"], p["signature"]) for p in read["state_points"]] == list(POINTS)


def test_v1_fields_are_document_exactly() -> None:
    """D8: v1's fields, unchanged; the v1 writer is not touched (its bytes are F0's M4)."""
    state, vector, _ = _written()
    v1 = document(state["variable_ids"], vector)
    assert v1["schema_version"] == SCHEMA_VERSION
    shared = {key: state[key] for key in ("state_sha256", "variable_ids", "variables")}
    assert canonical_json(shared) == canonical_json(
        {k: v for k, v in v1.items() if k != "schema_version"}
    )
    assert set(state) == set(v1) | {"material_layout", "state_points"}


# -- the writer's refusals and the cross-check --------------------------------------------------


def test_writer_refuses_an_unrecorded_definition_sha() -> None:
    ids, vector, _ = _problem(1)
    unrecorded = (
        INPUTS[0],
        INPUTS[1],
        ConnectionInput("Q1", "heat-v1", {"template": "heat-v1"}, ""),
    )
    layout = MaterialLayout.build(unrecorded, FACTS, ids)
    with pytest.raises(ValueError, match="Q1: no definition SHA-256"):
        document_v2(ids, vector, layout, POINTS)


def test_writer_refuses_a_layout_of_another_problem() -> None:
    ids, vector, layout = _problem(1)
    other = list(reversed(ids))
    with pytest.raises(ValueError, match="is not variable"):
        document_v2(other, vector, layout, POINTS)


def test_writer_refuses_a_repeated_or_empty_state_point() -> None:
    ids, vector, layout = _problem(1)
    with pytest.raises(ValueError, match="repeated"):
        document_v2(ids, vector, layout, (*POINTS, POINTS[0]))
    with pytest.raises(ValueError, match="empty"):
        document_v2(ids, vector, layout, (("p", ""),))


def test_cross_check_finds_each_forgery() -> None:
    state, _, _ = _written()
    certificate = _certificate(state)
    forged = copy.deepcopy(state)
    forged["material_layout"][0]["connection"] = "S9"
    assert inconsistencies_v2(forged, certificate) == ("layout_variable_ids",)
    forged = copy.deepcopy(state)
    first = forged["variable_ids"][0]
    forged["variables"][first] = forged["variables"][first] + 1.0
    assert inconsistencies_v2(forged, certificate) == ("state_sha256_mismatch",)
    assert inconsistencies_v2(state, None) == ("certificate_missing",)
    forged = copy.deepcopy(state)
    forged["material_layout"][1]["definition_sha256"] = ""
    reasons = inconsistencies_v2(forged, certificate)
    assert len(reasons) == 1 and reasons[0].startswith(
        "schema(/material_layout/1/definition_sha256"
    )


# -- R0 -----------------------------------------------------------------------------------------


def test_r0_carries_layout_and_points_for_v2_only() -> None:
    state, vector, _ = _written()
    v1 = document(state["variable_ids"], vector)
    assert r0_projection({"solution-state.json": v1}) == {
        "solution_state": {"variable_ids": v1["variable_ids"]}
    }
    projection = r0_projection({"solution-state.json": state})
    assert projection["solution_state"] == {
        "variable_ids": state["variable_ids"],
        "material_layout": state["material_layout"],
        "state_points": state["state_points"],
    }
    assert floats_in(projection) == []


def test_r0_moves_with_a_definition_sha_not_with_a_value() -> None:
    state, _, _ = _written()
    digest = r0_sha256(r0_projection({"solution-state.json": state}))
    moved = copy.deepcopy(state)
    moved["material_layout"][0]["definition_sha256"] = "0" * 64
    assert r0_sha256(r0_projection({"solution-state.json": moved})) != digest
    moved = copy.deepcopy(state)
    moved["state_points"][0]["signature"] = "VAPOR"
    assert r0_sha256(r0_projection({"solution-state.json": moved})) != digest
    valued = copy.deepcopy(state)
    first = valued["variable_ids"][0]
    valued["variables"][first] = valued["variables"][first] + 1.0
    assert r0_sha256(r0_projection({"solution-state.json": valued})) == digest


def test_r0_of_a_v2_label_without_its_members_is_defined() -> None:
    """`test_t07_w3e_solution_state`'s forgery: a v1 file relabelled v2 projects, None for the
    members it lacks, and the cross-check names the schema."""
    state, vector, _ = _written()
    forged = document(state["variable_ids"], vector) | {"schema_version": SCHEMA_VERSION_V2}
    projection = r0_projection({"solution-state.json": forged})["solution_state"]
    assert projection["material_layout"] is None and projection["state_points"] is None
    assert inconsistencies_v2(forged, _certificate(forged))[0].startswith("schema(")
