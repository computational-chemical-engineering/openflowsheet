"""M06 WO-1: `inspect_structure`'s row/column index and the unroutable analysis (Asks 1 and 2).

Design note `docs/design/M06-web-shell.md` §4.1, gates G3 and G4; ADR 0019 Amendment 3, A3.1. The
expectations are the note's: NET-02's counts and its `U-HEAT.Q` row, STR-03's excess and its nine
candidates (read from the `STR-03` check's message, which a test may parse and product code may
not), and the snapshots of `g3_structure_snapshots.json`, taken before WO-1 on a tree whose `src/`
and corpus inputs are `67029fa`'s.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS

import openflowsheet.application.revision_run as revision_run
import openflowsheet.graph.analysis as graph_analysis
from openflowsheet.application.binding import Binding, bind_revision_or_reason
from openflowsheet.application.revision_binding import (
    RevisionBinding,
    bind_revision_flowsheet,
    specification_rows,
)
from openflowsheet.application.revision_run import (
    Route,
    route_analysis,
    route_declaration,
    route_structure,
    select_route,
)
from openflowsheet.application.validation import structural_analysis, validate
from openflowsheet.canonical import canonical_json
from openflowsheet.graph.trace import StructureUnavailableError
from openflowsheet.models import flow_id, pressure_id, temperature_id

SNAPSHOTS: Mapping[str, Mapping[str, str | None]] = json.loads(
    (Path(__file__).parent / "fixtures" / "m06" / "g3_structure_snapshots.json").read_text("utf-8")
)["snapshots"]
#: A3.1's members: what dropping restores the pre-amendment document.
ROUTED_ADDED = ("rows", "columns")
UNROUTED_ADDED = ("validation_structural_report", "rows", "columns")
ROW_MEMBERS = {
    "row_id",
    "unit_id",
    "instance_id",
    "role",
    "specification_id",
    "kind",
    "si_unit",
    "columns",
}
COLUMN_MEMBERS = {
    "column_id",
    "kind",
    "si_unit",
    "owner_unit",
    "owner_instance",
    "connection",
    "coordinate",
    "component",
}
NET02 = "SYN-001-T06-NET02"
STR03 = "SYN-001-conflicting-heater-spec"


def _sha256(document: Any) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


@pytest.fixture(scope="module")
def structures() -> dict[str, dict[str, Any]]:
    return {name: route_structure(make()) for name, make in CORPUS.items()}


def test_the_snapshots_cover_the_corpus() -> None:
    assert sorted(SNAPSHOTS) == sorted(CORPUS)
    assert len(SNAPSHOTS) == 50


# -- G3: nothing hashed moves ---------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_g3_route_analysis_and_validate_are_unchanged(name: str) -> None:
    route = select_route(CORPUS[name]())
    analysed = route_analysis(route).as_document() if isinstance(route, Route) else None
    assert (None if analysed is None else _sha256(analysed)) == SNAPSHOTS[name]["route_analysis"]
    report = validate(CORPUS[name](), "simulation").as_document()
    report.pop("provenance")  # a clock reading (T07 ruling round 1 R3)
    assert _sha256(report) == SNAPSHOTS[name]["validate"]


def test_g3_routed_and_unrouted_counts() -> None:
    routed = [name for name, snapshot in SNAPSHOTS.items() if snapshot["route_analysis"]]
    assert len(routed) == 47


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_g3_dropping_the_new_members_restores_the_old_document(
    name: str, structures: dict[str, dict[str, Any]]
) -> None:
    structure = structures[name]
    added = ROUTED_ADDED if "solve_path" in structure else UNROUTED_ADDED
    assert set(added) <= set(structure)
    old = {key: value for key, value in structure.items() if key not in added}
    assert _sha256(old) == SNAPSHOTS[name]["route_structure"]


# -- G4: the index describes the declaration ------------------------------------------------------


def _index(structure: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, columns = structure["rows"], structure["columns"]
    assert isinstance(rows, list) and isinstance(columns, list)
    return rows, columns


def _report(structure: Mapping[str, Any]) -> dict[str, Any]:
    report = structure.get("structural_report") or structure["validation_structural_report"]
    assert isinstance(report, dict)
    return report


def test_g4_net02_counts_and_the_heater_duty_row(structures: dict[str, dict[str, Any]]) -> None:
    structure = structures[NET02]
    assert structure["solve_path"] == "revision_eo"
    rows, columns = _index(structure)
    report = structure["structural_report"]
    assert (len(rows), len(columns)) == (48, 47)
    assert sum(len(row["columns"]) for row in rows) == report["nnz"] == 172
    (duty,) = [row for row in rows if row["row_id"] == "U-HEAT:HEAT-duty"]
    assert duty["instance_id"] == "U-HEAT"
    assert duty["unit_id"] == "U-HEAT"
    assert (duty["kind"], duty["si_unit"]) == ("heat_rate", "W")
    assert "U-HEAT.Q" in duty["columns"]
    assert report["canonical_matching"]["U-HEAT.Q"] == "U-HEAT:HEAT-duty"
    # The revision binder's attribution of NET-02's specification rows.
    assert {
        row["row_id"]: row["specification_id"] for row in rows if row["role"] == "specification"
    } == {
        "U-FEED:FEED-n:A": "SPEC-S1-n-A",
        "U-FEED:FEED-n:B": "SPEC-S1-n-B",
        "U-FEED:FEED-n:C": "SPEC-S1-n-C",
        "U-FEED:FEED-T": "SPEC-S1-T",
        "U-FEED:FEED-P": "SPEC-S1-P",
        "U-HEAT:HEAT-T": "SPEC-heater-outlet-T",
        "U-PHF:PHF-Q": "SPEC-phf-Q",
    }
    (q,) = [column for column in columns if column["column_id"] == "U-HEAT.Q"]
    assert q == {
        "column_id": "U-HEAT.Q",
        "kind": "heat_rate",
        "si_unit": "W",
        "owner_unit": "U-HEAT",
        "owner_instance": "U-HEAT",
        "connection": None,
        "coordinate": None,
        "component": None,
    }


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_g4_the_index_describes_the_declaration(
    name: str, structures: dict[str, dict[str, Any]]
) -> None:
    structure = structures[name]
    if structure["rows"] is None:
        # No analysis ran (the binders refuse before one): both members are null together.
        assert structure["columns"] is None
        assert structure.get("validation_structural_report") is None
        return
    rows, columns = _index(structure)
    report = _report(structure)
    assert all(set(row) == ROW_MEMBERS for row in rows)
    assert all(set(column) == COLUMN_MEMBERS for column in columns)
    column_ids = [column["column_id"] for column in columns]
    assert len(set(column_ids)) == len(column_ids)
    assert sum(len(row["columns"]) for row in rows) == report["nnz"]
    assert all(set(row["columns"]) <= set(column_ids) for row in rows)
    assert set(report["canonical_matching"]) <= set(column_ids)
    assert set(report["canonical_matching"].values()) <= {row["row_id"] for row in rows}
    roles = {row["row_id"]: row["role"] for row in rows}
    for unit in report["unit_degrees_of_freedom"]:
        assert all(roles[row_id] == "specification" for row_id in unit["specification_rows"])
    assert all(row["specification_id"] is None or row["role"] == "specification" for row in rows)


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_g4_positional_coordinates_agree_with_the_binders_naming(
    name: str, structures: dict[str, dict[str, Any]]
) -> None:
    """The positional rule against the binders' coordinate naming, which only a test may read."""
    structure = structures[name]
    if structure["rows"] is None:
        return
    _, columns = _index(structure)
    document = CORPUS[name]()
    components = document["component_set"]["components"]
    ntp = {c["id"] for c in document["connections"] if c["state_definition"] == "nTP-v1"}
    by_connection: dict[str, list[dict[str, Any]]] = {}
    for column in columns:
        if column["connection"] is not None:
            by_connection.setdefault(column["connection"], []).append(column)
        if column["coordinate"] is None:
            assert column["component"] is None
    assert set(by_connection) == ntp
    for stream, members in by_connection.items():
        assert len(members) == len(components) + 2
        expected = {
            **{flow_id(stream, c): ("n", c) for c in components},
            temperature_id(stream): ("T", None),
            pressure_id(stream): ("P", None),
        }
        assert {m["column_id"]: (m["coordinate"], m["component"]) for m in members} == expected


def test_g4_str03_returns_its_analysis(structures: dict[str, dict[str, Any]]) -> None:
    structure = structures[STR03]
    assert "solve_path" not in structure
    report = structure["validation_structural_report"]
    assert report is not None
    assert report == structural_analysis(CORPUS[STR03]()).report.as_document()
    assert report["excess"] == 1
    (message,) = [
        check.message
        for check in validate(CORPUS[STR03](), "simulation").checks
        if check.id == "STR-03"
    ]
    listed = message.split("candidate specifications ", 1)[1].split("]", 1)[0] + "]"
    candidates = ast.literal_eval(listed)
    assert len(candidates) == 9
    assert report["candidate_specifications"] == candidates
    rows, columns = _index(structure)
    assert len(rows) == report["structural_counts"]["equations"] == 50
    assert len(columns) == report["structural_counts"]["free_variables"] == 47


def test_a_document_refused_before_the_structural_stage_has_null_members() -> None:
    structure = route_structure({"title": "nothing to bind"})
    assert structure == {
        "not_run_reason": "the revision is not well formed",
        "hint": None,
        "validation_structural_report": None,
        "rows": None,
        "columns": None,
    }


# -- the index comes from the report's own declaration --------------------------------------------


@pytest.mark.parametrize("name", [NET02, "SYN-001-A02-360", "SYN-001-nominal"])
def test_the_index_is_in_declaration_order(
    name: str, structures: dict[str, dict[str, Any]]
) -> None:
    route = select_route(CORPUS[name]())
    assert isinstance(route, Route)
    report, declaration = route_declaration(route)
    assert declaration is not None
    rows, columns = _index(structures[name])
    assert [row["row_id"] for row in rows] == list(declaration.row_ids)
    assert [column["column_id"] for column in columns] == list(declaration.column_ids)
    assert report.as_document() == structures[name]["structural_report"]


def test_legacy_rows_carry_the_legacy_binders_specification_ids(
    structures: dict[str, dict[str, Any]],
) -> None:
    route = select_route(CORPUS["SYN-001-A02-360"]())
    assert isinstance(route, Route) and route.solve_path == "legacy_eo"
    rows, _ = _index(structures["SYN-001-A02-360"])
    named = {row["row_id"]: row["specification_id"] for row in rows if row["specification_id"]}
    assert named == dict(route.binding.specification_ids)
    instances = {row["row_id"]: row["instance_id"] for row in rows}
    assert instances["U-FEED:FEED-T"] == "feed"


def test_the_revision_attribution_agrees_with_the_legacy_binders() -> None:
    """R3: where both binders bind, the revision binder's `(instance, specification)` pairs are the
    legacy binder's, which names them independently (8 of the corpus)."""
    compared = 0
    for make in CORPUS.values():
        revision, legacy = bind_revision_flowsheet(make()), bind_revision_or_reason(make())
        if not (isinstance(revision, RevisionBinding) and isinstance(legacy, Binding)):
            continue
        _, declaration = route_declaration(Route("revision_eo", revision))
        assert declaration is not None
        ours = {
            (revision.graph.instance_ids[str(declaration.rows[row].unit)], specification)
            for row, specification in specification_rows(revision, declaration).items()
        }
        theirs = {
            (legacy.graph.instance_ids.get(legacy.row_units.get(row, "")), specification)
            for row, specification in legacy.specification_ids.items()
        }
        assert ours == theirs
        compared += 1
    assert compared == 8


def test_an_untraceable_declaration_has_no_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """`analyse`'s `UNSUPPORTED` report, and null `rows`/`columns`: no declaration to index."""

    def refuse(*_: Any, **__: Any) -> Any:
        raise StructureUnavailableError("U-HEAT:HEAT-duty", "probe")

    monkeypatch.setattr(revision_run, "trace_declaration", refuse)
    monkeypatch.setattr(graph_analysis, "trace_declaration", refuse)
    structure = route_structure(CORPUS[NET02]())
    assert structure["structural_report"]["finding"] == "UNSUPPORTED"
    assert (structure["rows"], structure["columns"]) == (None, None)
