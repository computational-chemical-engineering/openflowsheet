"""ST WO-2: `stream-table-v1`'s schema (`_data/schemas/stream-table.schema.json`, note §5).

Every WO-1 corpus document, every served 0.3.0 bundle and the test-local states of Amendment 5
validate; the committed valid fixtures (one per basis, WO-1 output) validate; each invalid fixture
of note §10 row 2 is rejected, at the member it breaks. The schema's `schemas/registry.json`
entry waits for `wp/MSG` (the file is shared), so the schema is read from its path here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import st_support as support
from jsonschema import Draft202012Validator

from openflowsheet.application import stream_table
from openflowsheet.models import flow_id, pressure_id, temperature_id

ROOT = support.ROOT
SCHEMA_PATH = ROOT / "src" / "openflowsheet" / "_data" / "schemas" / "stream-table.schema.json"
FIXTURES = ROOT / "tests" / "fixtures" / "st"
#: Each invalid fixture, and the last members of the path its first error is reported at.
INVALID = {
    "rendered-phase-key": ("substreams", 0, "phases"),
    "null-without-absent": ("substreams", 0, "absent"),
    "missing-convention": ("substreams", 0),
    "family-lower-case": ("phases", 0, "id", "family"),
    "extra-member-in-phase-id": ("phases", 0, "id"),
}


def _schema() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return document


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def _errors(document: Any) -> list[Any]:
    return sorted(_validator().iter_errors(document), key=lambda e: list(e.absolute_path))


def test_the_schema_is_a_draft_2020_12_schema() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].endswith("/stream-table.schema.json")
    assert schema["properties"]["schema_version"] == {"const": stream_table.SCHEMA_VERSION}
    assert schema["properties"]["evaluator"]["properties"]["phase_rule"] == {
        "const": stream_table.PHASE_RULE
    }


def test_q4_a13_e_no_schema_member_is_called_quality() -> None:
    assert not re.search("quality", SCHEMA_PATH.read_text(encoding="utf-8"), re.IGNORECASE)


@pytest.mark.parametrize("path", sorted((FIXTURES / "valid").glob("*.json")), ids=lambda p: p.stem)
def test_a_valid_fixture_validates(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["basis"]["provider_id"] == path.stem
    assert _errors(document) == []


def test_there_is_one_valid_fixture_per_served_basis() -> None:
    stems = {path.stem for path in (FIXTURES / "valid").glob("*.json")}
    assert stems == {"syn001", "pr-c1-v1", "iapws95-v1", "wilson-ig-v2"}


@pytest.mark.parametrize("name", sorted(INVALID))
def test_an_invalid_fixture_is_rejected_where_it_breaks(name: str) -> None:
    document = json.loads((FIXTURES / "invalid" / f"{name}.json").read_text(encoding="utf-8"))
    errors = _errors(document)
    assert errors, name
    expected = INVALID[name]
    assert any(tuple(error.absolute_path)[-len(expected) :] == expected for error in errors), [
        list(error.absolute_path) for error in errors
    ]


def test_every_corpus_document_validates() -> None:
    documents = support.documents()
    assert documents
    for run, document in documents.items():
        assert _errors(document) == [], run


def test_g10_every_served_v030_document_validates() -> None:
    served = 0
    for manifest in sorted(support.V030_BUNDLES.rglob("run-manifest.json")):
        try:
            document = stream_table.from_bundle(manifest.parent)
        except stream_table.StreamTableError:
            continue
        assert _errors(document) == [], manifest.parent.name
        served += 1
    assert served > 0


def _probe_states() -> dict[str, support.Members]:
    """Amendment 5's absence-heavy test-local states: a refused `Tsat`, a negative carried vapour,
    a dormant, a refused-flash and a subnormal SYN-001 stream."""
    th_c1 = support.members("s11-th/TH-C1")
    n5 = th_c1.variables["S5.n.H2O"]
    states = {
        "tsat-refused": support.with_state(
            th_c1, {"S4.P": 2.5e7, "S4.sat.V": 0.5, "S4.sat.L": 0.5, "S4.n.H2O": 1.0}
        ),
        "negative-vapour": support.with_state(
            th_c1, {"S5.sat.V": -1e-12 * n5, "S5.sat.L": n5 + 1e-12 * n5}
        ),
    }
    run, name = next(
        (run, entry["id"])
        for run, document in support.documents().items()
        if document["basis"]["provider_id"] == "syn001"
        for entry in document["streams"]
        if entry["substreams"][0]["phase_source"] == "flash"
    )
    syn = support.members(run)
    for label, flows, temperature in (
        ("dormant", (0.0, -0.0, 0.0), 1234.5),
        ("flash-refused", (1.0, 1.0, 1.0), 450.0),
        ("subnormal", (5e-324, 0.0, 0.0), 350.0),
    ):
        updates = {flow_id(name, c): n for c, n in zip(("A", "B", "C"), flows, strict=True)}
        updates[temperature_id(name)] = temperature
        updates[pressure_id(name)] = 1e5
        states[label] = support.with_state(syn, updates)
    return states


def test_amendment_5_test_local_documents_validate() -> None:
    for label, state in _probe_states().items():
        assert _errors(support.build(state)) == [], label
