"""X04 WO-4: the stream table and `openflowsheet streams` in the request's display units (ADR
0075 D7.3, D7.5, D7.6, D8; ADR 0019 Amendment 17).

Assertions A14 and A21–A34 for `get_stream_table` of `docs/derivations/X04-test-specification.md`
§5 P, S, T, I (A33's stream-table round trip here, X04 decision D-1; A35 is F0's
`scripts/corpus_identity.py --check`, run as the work order's gate). The jobs are the README
Rankine cycle (water, `iapws95-v1`) and SYN-001's nominal revision (three components, `syn001`,
no entropies), both solved in one project. Expected display items are `units.display_item`'s, which
`tests/test_x04_display_core.py` holds to the reference; A26's gauge values are the reference
generator's own (`docs/derivations/scripts/x04_reference.py`, loaded by path). The site table
`SPEC_SITES` below is the specification's §4, written out here independently of
`application.stream_table.SITES`.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)

from openflowsheet.application import cli, stream_table, stream_table_format
from openflowsheet.application.authz import grant, set_ambient_pressure
from openflowsheet.application.cli import API_EXIT_CODES
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.store import DATABASE_NAME
from openflowsheet.application.types import Change, schema_errors
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.messages.render import render_error
from openflowsheet.units import DisplayUnits, display_item, parse_display_units

RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"
NOMINAL = "SYN-001-nominal"
SCHEMA = "stream-table.schema.json"
SCRIPT = REPO_ROOT / "docs" / "derivations" / "scripts" / "x04_reference.py"
REFERENCE: dict[str, Any] = json.loads(SCRIPT.with_suffix(".json").read_text(encoding="utf-8"))
pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)

#: A22's preferences, each with the ambient it is resolved against.
PREFERENCES = (
    ("eng", None),
    ("eng,pressure=barg", 101325.0),
    ("si", None),
    ("mole_fraction=%,mass_fraction=%,dimensionless=%", None),
    ("molar_entropy=kJ/(mol K),specific_entropy=kJ/(kg K)", None),
)

#: The specification's §4 site table: object → member → display kind (`None`: never displayed).
SPEC_SITES: dict[str, dict[str, str | None]] = {
    "stream": {"T": "temperature", "P": "pressure"},
    "substream": {
        "n": "molar_flow",
        "n_total": "molar_flow",
        "m": "mass_flow",
        "m_total": "mass_flow",
        "x": "mole_fraction",
        "w": "mass_fraction",
        "H_flow": "enthalpy_flow",
        "h": "molar_enthalpy",
        "h_mass": "specific_enthalpy",
        "s": "molar_entropy",
        "s_mass": "specific_entropy",
        "vapor_fraction_molar": "dimensionless",
        "vapor_fraction_mass": "dimensionless",
        "S_flow": None,
        "V_flow": None,
        "rho": None,
    },
    "phase": {
        "n": "molar_flow",
        "n_total": "molar_flow",
        "m": "mass_flow",
        "m_total": "mass_flow",
        "x": "mole_fraction",
        "w": "mass_fraction",
        "H_flow": "enthalpy_flow",
        "h": "molar_enthalpy",
        "h_mass": "specific_enthalpy",
        "s": "molar_entropy",
        "s_mass": "specific_entropy",
        "phase_fraction_molar": "dimensionless",
        "phase_fraction_mass": "dimensionless",
        "v": "molar_volume",
        "S_flow": None,
        "V_flow": None,
        "rho": None,
    },
    "port": {"H_flow": "enthalpy_flow"},
    "unit": {
        "H_in": "enthalpy_flow",
        "H_out": "enthalpy_flow",
        "Q": "heat_rate",
        "closure": "heat_rate",
        "W": "power",
    },
    "overall": {
        "H_feeds": "enthalpy_flow",
        "H_products": "enthalpy_flow",
        "Q": "heat_rate",
        "closure": "heat_rate",
        "W": "power",
    },
    "component": {"molar_mass": "molar_mass"},
    "quote": {"index": None, "value": None, "tolerance": None},
    "entry": {"params": None},
}


# -- the jobs --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Solved:
    project: Path
    rankine: str
    syn001: str

    @property
    def jobs(self) -> tuple[str, str]:
        return (self.rankine, self.syn001)

    def bundle(self, job_id: str) -> Path:
        return self.project / "jobs" / job_id / "bundle"


def _rankine_change() -> tuple[Any, str]:
    change, _, key = Change.from_change_set(json.loads(RANKINE.read_text(encoding="utf-8")))
    return change, key


@pytest.fixture(scope="module")
def solved(tmp_path_factory: pytest.TempPathFactory) -> Solved:
    project = tmp_path_factory.mktemp("x04-stream-table") / "project"
    with LocalApplication.create(project, project_id="x04-stream-table") as app:
        change, key = _rankine_change()
        committed = app.commit_change(change, None, key)
        assert committed.revision_id is not None
        rankine = app.solve(committed.revision_id, "default")
        assert rankine.outcome == "CONVERGED"
        edits = [
            {"operation": "set", "path": [k], "value": v} for k, v in CORPUS[NOMINAL]().items()
        ]
        request = {
            "edits": edits,
            "expected_revision": committed.revision_id,
            "idempotency_key": "x04-syn001",
        }
        revision = dispatch(app, "commit_change", request)["revision_id"]
        syn001 = app.solve(revision, "default")
        assert syn001.outcome == "CONVERGED"
    return Solved(project, rankine.job_id, syn001.job_id)


@contextmanager
def ambient(project: Path, pascal: float | None) -> Iterator[None]:
    """The project's ambient pressure set to `pascal` for the block, undeclared after it."""
    set_ambient_pressure(project, pascal)
    try:
        yield
    finally:
        set_ambient_pressure(project, None)


def table(project: Path, job_id: str, text: str | None = None, **view: Any) -> dict[str, Any]:
    """`get_stream_table` through `dispatch`, as its `Projection` document."""
    request: dict[str, Any] = {"job_id": job_id, **view}
    if text is not None:
        request["display_units"] = text
    with LocalApplication.open(project) as app:
        return dict(dispatch(app, "get_stream_table", request))


def _strip(value: Any) -> Any:
    """`value` with every `display` member and the root `display_units` removed."""
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in ("display", "display_units")}
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


def _objects(document: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Every open object of the document that may hold a converted number, with its §4 name."""
    for stream in document["streams"]:
        yield "stream", stream
        for substream in stream["substreams"]:
            yield "substream", substream
            for phase in substream["phases"]:
                yield "phase", phase
    for unit in document["energy"]["units"]:
        yield "unit", unit
        for port in unit["ports"]:
            yield "port", port
    yield "overall", document["energy"]["overall"]


def _dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _dicts(item)


def _resolved(text: str, pascal: float | None) -> DisplayUnits:
    return parse_display_units(text, pascal)


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("x04_reference_stream_table", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


# -- A21. No preference, no change -----------------------------------------------------------------


def test_a21_without_a_preference_the_document_is_sts(solved: Solved) -> None:
    for job_id in solved.jobs:
        view = table(solved.project, job_id)
        document = view["value"]
        built = stream_table.from_bundle(
            solved.bundle(job_id), source={"job_id": job_id, "bundle_id": f"{job_id}:bundle"}
        )
        assert canonical_json(document) == canonical_json(built)
        assert view["sha256"] == document_sha256(built)
        assert "display_units" not in document
        assert not any("display" in holder for holder in _dicts(document))


# -- A22, A23, A25. Strip invariance, coverage and values, echo ------------------------------------


@pytest.mark.parametrize(("text", "pascal"), PREFERENCES, ids=[p[0] for p in PREFERENCES])
def test_a22_a23_a25_displayed_documents(solved: Solved, text: str, pascal: float | None) -> None:
    units = _resolved(text, pascal)
    converted = 0
    for job_id in solved.jobs:
        plain = table(solved.project, job_id)["value"]
        with ambient(solved.project, pascal):
            view = table(solved.project, job_id, text)
        shown = view["value"]
        # A22: the SI content is the plain document, byte for byte.
        assert canonical_json(_strip(shown)) == canonical_json(plain), (job_id, text)
        # A25: the root echo, present iff the request had `display_units`.
        assert shown["display_units"] == {
            "units": dict(units),
            "ambient_pressure": None if pascal is None else {"value": pascal, "unit": "Pa"},
        }
        # A23: every converted number at a §4 site has its display item, nothing else has one.
        visited: set[int] = set()
        for site, holder in _objects(shown):
            visited.add(id(holder))
            expected: dict[str, Any] = {}
            for member, kind in SPEC_SITES[site].items():
                value = holder.get(member)
                if value is None or kind is None or kind not in units:
                    continue
                if isinstance(value, list):
                    expected[member] = [
                        None if v is None else display_item(float(v), kind, units) for v in value
                    ]
                    assert len(holder["display"][member]) == len(value)
                else:
                    expected[member] = display_item(float(value), kind, units)
            if expected:
                converted += len(expected)
                assert holder["display"] == expected, (job_id, text, site)
            else:
                assert "display" not in holder, (job_id, text, site)
        for holder in _dicts(shown):
            if "display" in holder:  # only at a §4 site: no quote, entry or component has one
                assert id(holder) in visited, holder
        assert schema_errors(SCHEMA, shown) == []
    assert (converted > 0) == bool(units), text  # SYN-001 has no entropies; Rankine has


def test_a23_the_jobs_exercise_arrays_absences_and_every_object(solved: Solved) -> None:
    """The two jobs reach every §4 object and an array site with more than one element, so A23
    walks real arrays (SYN-001: three components) and both phase-carrying stream kinds."""
    units = _resolved("mole_fraction=%,mass_fraction=%,dimensionless=%", None)
    shown = table(solved.project, solved.syn001, "mole_fraction=%,mass_fraction=%,dimensionless=%")
    sites = {site for site, holder in _objects(shown["value"]) if "display" in holder}
    assert {"substream", "phase"} <= sites
    arrays = [
        holder["display"]["x"]
        for site, holder in _objects(shown["value"])
        if "x" in holder.get("display", {})
    ]
    assert arrays and max(len(a) for a in arrays) == 3
    eng = table(solved.project, solved.rankine, "eng")["value"]
    reached = {site for site, holder in _objects(eng) if "display" in holder}
    assert reached == {"stream", "substream", "phase", "unit", "port", "overall"}
    assert "mole_fraction" in units  # the SYN-001 arrays above are `x`'s
    # SYN-001 gives no entropies: null SI values with a reason, which A23 requires undisplayed.
    entropies = table(solved.project, solved.syn001, "molar_entropy=kJ/(mol K)")["value"]
    nulls = [holder for _, holder in _objects(entropies) if "s" in holder and holder["s"] is None]
    assert nulls and all("display" not in holder for holder in nulls)


# -- A24. The site table is complete ---------------------------------------------------------------


def _number_typed(schema: dict[str, Any], node: dict[str, Any]) -> bool:
    """A schema node whose instances may be a number or an array of numbers."""
    if "$ref" in node:
        pointer = node["$ref"].removeprefix("#/")
        target: Any = schema
        for part in pointer.split("/"):
            target = target[part]
        return _number_typed(schema, target)
    kinds = node.get("type")
    kinds = [kinds] if isinstance(kinds, str) else (kinds or [])
    if "number" in kinds or "integer" in kinds:
        return True
    if "array" in kinds and isinstance(node.get("items"), dict):
        return _number_typed(schema, node["items"])
    if kinds == ["object"] and isinstance(node.get("additionalProperties"), dict):
        return _number_typed(schema, node["additionalProperties"])
    return any(_number_typed(schema, alt) for alt in node.get("oneOf", node.get("anyOf", [])))


def test_a24_the_site_table_is_complete_and_equals_the_specification() -> None:
    schema = json.loads((REPO_ROOT / "schemas" / SCHEMA).read_text(encoding="utf-8"))
    objects = {
        "component": schema["properties"]["components"]["items"],
        **{name: schema["$defs"][name] for name in schema["$defs"]},
    }
    found: dict[str, set[str]] = {}
    for name, node in objects.items():
        properties = node.get("properties", {})
        numbers = {
            member
            for member, sub in properties.items()
            if member != "display" and _number_typed(schema, sub)
        }
        if numbers:
            found[name] = numbers
    # The display members themselves carry numbers, but are not sites.
    assert {name: set(members) for name, members in stream_table.SITES.items()} == found
    # §4, plus the phase id's ordinal: an identity integer, as a quote's `index` (D-6).
    assert dict(stream_table.SITES) == {**SPEC_SITES, "phase_id": {"ordinal": None}}
    for name, members in stream_table.SITES.items():
        for member, kind in members.items():
            # D4.2: the only `pressure` site is the stream's absolute `P`.
            assert (kind == "pressure") == ((name, member) == ("stream", "P"))


# -- A14, A26. Gauge and the ambient through the operation -----------------------------------------


def test_a26_gauge_pressures_read_the_declared_ambient(solved: Solved) -> None:
    generator = _load_generator()
    for job_id in solved.jobs:
        shown: dict[float, dict[str, Any]] = {}
        for pascal in (101325.0, 95000.0):
            with ambient(solved.project, pascal):
                shown[pascal] = table(solved.project, job_id, "pressure=barg")["value"]
            for stream in shown[pascal]["streams"]:
                reference = generator.display(stream["P"], "pressure", "barg", pascal)
                assert stream["display"]["P"] == {"value": reference["value"], "unit": "barg"}
        for one, other in zip(shown[101325.0]["streams"], shown[95000.0]["streams"], strict=True):
            assert one["display"]["P"]["value"] != other["display"]["P"]["value"]
        with LocalApplication.open(solved.project) as app, pytest.raises(ApplicationError) as no:
            dispatch(app, "get_stream_table", {"job_id": job_id, "display_units": "pressure=barg"})
        refused = no.value.error.as_document()
        assert refused["code"] == "invalid_request"
        assert refused["message"] == 'ambient_pressure_undeclared(pressure): "barg"'
        assert refused["detail"]["pointer"] == "/display_units"
        bare = {
            **refused,
            "detail": {k: v for k, v in refused["detail"].items() if k != "explanation"},
        }
        strict = render_error(bare, strict=True)
        assert (strict["code"], strict["complete"]) == ("ambient_pressure_undeclared", True)


def _solved_elsewhere(root: Path, name: str, pascal: float | None) -> tuple[Path, str]:
    project = root / name
    with LocalApplication.create(project, project_id="x04-a14") as app:
        change, key = _rankine_change()
        committed = app.commit_change(change, None, key)
        assert committed.revision_id is not None
        result = app.solve(committed.revision_id, "default")
        assert result.outcome == "CONVERGED"
    if pascal is not None:
        set_ambient_pressure(project, pascal)
    return project, result.job_id


def test_a14_the_ambient_reaches_only_gauge_displays(tmp_path: Path) -> None:
    """One revision solved in three projects (undeclared, 101325 Pa, 95000 Pa), as A13."""
    projects = {
        pascal: _solved_elsewhere(tmp_path, f"p{index}", pascal)
        for index, pascal in enumerate((None, 101325.0, 95000.0))
    }
    eng = {
        pascal: canonical_json(table(project, job_id, "eng")["value"])
        for pascal, (project, job_id) in projects.items()
    }
    assert len(set(eng.values())) == 1  # PU08: no ambient echo, no ambient dependence
    gauge = {
        pascal: table(project, job_id, "eng,pressure=barg")["value"]
        for pascal, (project, job_id) in projects.items()
        if pascal is not None
    }
    one, other = gauge[101325.0], gauge[95000.0]
    assert one["display_units"]["ambient_pressure"] == {"value": 101325.0, "unit": "Pa"}
    assert other["display_units"]["ambient_pressure"] == {"value": 95000.0, "unit": "Pa"}
    for document in (one, other):
        document["display_units"]["ambient_pressure"] = None
        for stream in document["streams"]:
            stream["display"]["P"] = None
    assert canonical_json(one) == canonical_json(other)


# -- A27. Paging -----------------------------------------------------------------------------------


def test_a27_every_page_carries_the_displayed_documents_sha256(solved: Solved) -> None:
    whole = table(solved.project, solved.syn001, "eng")
    sha256 = document_sha256(whole["value"])
    assert whole["sha256"] == sha256 != table(solved.project, solved.syn001)["sha256"]
    pages: list[Any] = []
    cursor = None
    while True:
        view: dict[str, Any] = {"pointer": "/streams", "limit": 1}
        if cursor is not None:
            view["cursor"] = cursor
        page = table(solved.project, solved.syn001, "eng", **view)
        assert page["sha256"] == sha256
        pages.extend(page["value"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert pages == whole["value"]["streams"] and len(pages) > 1
    with LocalApplication.open(solved.project) as app:

        def fetch(pointer: str, depth: int, cursor: str | None, limit: int) -> Any:
            request: dict[str, Any] = {
                "job_id": solved.syn001,
                "pointer": pointer,
                "depth": depth,
                "limit": limit,
                "display_units": "eng",
            }
            if cursor is not None:
                request["cursor"] = cursor
            return dispatch(app, "get_stream_table", request)

        assembled = stream_table_format.assemble(fetch, depth=1, limit=1)
    assert canonical_json(assembled) == canonical_json(whole["value"])


# -- A28, A29, A30. The CLI's three forms ----------------------------------------------------------


def streams(*argv: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = cli.main(["streams", *argv])
    out, err = capsys.readouterr()
    return code, out, err


def _by_job(solved: Solved, job_id: str) -> list[str]:
    return ["--project", str(solved.project), "--job", job_id]


@pytest.mark.parametrize("form", ["text", "csv", "json"])
def test_a28_a29_a30_without_the_flag_and_with_si_the_forms_are_sts(
    solved: Solved, form: str, capsys: pytest.CaptureFixture[str]
) -> None:
    for job_id in solved.jobs:
        code, plain, _ = streams(*_by_job(solved, job_id), "--format", form, capsys=capsys)
        assert code == 0
        document = table(solved.project, job_id)["value"]
        render = {
            "text": stream_table_format.to_text,
            "csv": stream_table_format.to_csv,
            "json": stream_table_format.to_json,
        }[form]
        assert plain == render(document)
        code, si, _ = streams(
            *_by_job(solved, job_id), "--format", form, "--display-units", "si", capsys=capsys
        )
        assert code == 0
        if form == "json":  # the displayed document: the echo is its one addition
            assert _strip(json.loads(si)) == json.loads(plain)
            assert json.loads(si)["display_units"] == {"units": {}, "ambient_pressure": None}
        else:
            assert si == plain


def _cells(line: str) -> list[str]:
    return line[stream_table_format.LABEL_WIDTH :].split()


def _shown_value(holder: dict[str, Any], member: str) -> str:
    """A28's cell: `{:.6g}` of the display value, or of the SI value where there is none."""
    item = holder.get("display", {}).get(member)
    value = holder[member] if item is None else item["value"]
    return f"{value:.6g}"


def test_a28_the_text_form_in_display_units(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    code, text, err = streams(
        *_by_job(solved, solved.rankine), "--display-units", "eng", capsys=capsys
    )
    assert (code, err) == (0, "")
    lines = text.splitlines()
    assert "SI units" not in lines
    pu01 = next(p for p in REFERENCE["preferences"] if p["id"] == "PU01")
    canonical = ",".join(f"{k}={u}" for k, u in sorted(pu01["expected"]["units"].items()))
    assert lines[7] == f"display units:       {canonical}"
    assert lines[8] == ""
    document = table(solved.project, solved.rankine, "eng")["value"]
    streams_ = document["streams"]
    assert len(streams_) <= stream_table_format.TEXT_COLUMNS  # one block
    substreams = [stream["substreams"][0] for stream in streams_]
    rows = {line[: stream_table_format.LABEL_WIDTH].rstrip(): line for line in lines}
    expected_rows = {
        "T [degC]": (streams_, "T"),
        "P [bar]": (streams_, "P"),
        "n [kmol/h]": (substreams, "n_total"),
        "m [kg/h]": (substreams, "m_total"),
        "h [kJ/mol]": (substreams, "h"),
        "h [kJ/kg]": (substreams, "h_mass"),
        "s [J/(mol K)]": (substreams, "s"),
        "s [kJ/(kg K)]": (substreams, "s_mass"),
        "rho [kg/m3]": (substreams, "rho"),
        "H [kW]": (substreams, "H_flow"),
    }
    for label, (holders, member) in expected_rows.items():
        assert _cells(rows[label]) == [_shown_value(h, member) for h in holders], label
    header = next(line for line in lines if line.startswith("unit "))
    width = stream_table_format.VALUE_WIDTH
    start = 2 * stream_table_format.LABEL_WIDTH
    names = [header[start + i * width : start + (i + 1) * width].strip() for i in range(5)]
    assert names == ["H_in [kW]", "H_out [kW]", "Q [kW]", "W [kW]", "closure [kW]"]
    units = {line[: stream_table_format.LABEL_WIDTH].rstrip(): line for line in lines}
    for unit in document["energy"]["units"]:
        cells = units[unit["id"]][start:].split()[:5]
        members = ("H_in", "H_out", "Q", "W", "closure")
        assert cells == [_shown_value(unit, m) for m in members], unit["id"]
    with ambient(solved.project, 101325.0):
        code, gauge, _ = streams(
            *_by_job(solved, solved.rankine), "--display-units", "eng,pressure=barg", capsys=capsys
        )
    assert code == 0
    gauge_lines = gauge.splitlines()
    assert gauge_lines[7].startswith("display units:       ")
    assert gauge_lines[8] == "ambient pressure:    101325 Pa"
    assert any(line.startswith("P [barg] ") for line in gauge_lines)


def test_a28_fraction_rows_and_a_partial_energy_conversion(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rows without an SI unit gain `[%]` (X04 decision D-10); with one energy kind converted,
    every energy header names its unit, `W` for the SI ones."""
    text = "mole_fraction=%,dimensionless=%,heat_rate=MW"
    code, out, _ = streams(*_by_job(solved, solved.syn001), "--display-units", text, capsys=capsys)
    assert code == 0
    labels = {line[: stream_table_format.LABEL_WIDTH].rstrip() for line in out.splitlines()}
    assert {"vf molar [%]", "vf mass [%]", "T [K]", "H [W]"} <= labels
    components = table(solved.project, solved.syn001)["value"]["components"]
    assert all(f"x[{c['id']}] [%]" in labels for c in components)
    header = next(line for line in out.splitlines() if line.startswith("unit "))
    assert header.split()[1:] == [
        "model", "H_in", "[W]", "H_out", "[W]", "Q", "[MW]", "W", "[W]", "closure", "[MW]",
        "verifier",
    ]  # fmt: skip


def test_a29_the_csv_form_in_display_units(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    components = [c["id"] for c in table(solved.project, solved.syn001)["value"]["components"]]
    code, out, _ = streams(
        *_by_job(solved, solved.syn001), "--format", "csv", "--display-units", "eng", capsys=capsys
    )
    assert code == 0
    rows = list(csv.reader(io.StringIO(out)))
    renamed = {
        "T_K": "T_degC",
        "P_Pa": "P_bar",
        "n_total_mol_s": "n_total_kmol_h",
        "m_total_kg_s": "m_total_kg_h",
        "h_J_mol": "h_kJ_mol",
        "h_J_kg": "h_kJ_kg",
        "s_J_kgK": "s_kJ_kgK",
        "H_flow_W": "H_flow_kW",
        **{f"n_{c}_mol_s": f"n_{c}_kmol_h" for c in components},
    }
    si_header = [
        *stream_table_format.CSV_COLUMNS,
        *(f"n_{c}_mol_s" for c in components),
        *(f"x_{c}" for c in components),
    ]
    assert rows[0] == [renamed.get(column, column) for column in si_header]
    assert "s_J_molK" in rows[0]
    document = table(solved.project, solved.syn001, "eng")["value"]
    first = document["streams"][0]
    total = dict(zip(rows[0], rows[1], strict=True))
    assert total["T_degC"] == repr(first["display"]["T"]["value"])
    assert total["P_bar"] == repr(first["display"]["P"]["value"])
    substream = first["substreams"][0]
    assert total["n_total_kmol_h"] == repr(substream["display"]["n_total"]["value"])
    index = substream["components"].index(components[0])
    assert total[f"n_{components[0]}_kmol_h"] == repr(substream["display"]["n"][index]["value"])
    code, out, _ = streams(
        *_by_job(solved, solved.syn001),
        "--format",
        "csv",
        "--display-units",
        "mole_fraction=%,dimensionless=%",
        capsys=capsys,
    )
    header = next(csv.reader(io.StringIO(out)))
    for column in (
        *(f"x_{c}_pct" for c in components),
        "phase_fraction_molar_pct",
        "vapor_fraction_molar_pct",
        "vapor_fraction_mass_pct",
    ):
        assert column in header, column
    assert "T_K" in header and "n_total_mol_s" in header


def test_a30_the_json_form_is_the_displayed_documents_canonical_json(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = streams(
        *_by_job(solved, solved.syn001), "--format", "json", "--display-units", "eng", capsys=capsys
    )
    assert code == 0
    document = table(solved.project, solved.syn001, "eng")["value"]
    assert out == canonical_json(document).decode("utf-8") + "\n"


def test_d9_an_out_of_range_display_prints_as_an_absent_value(solved: Solved) -> None:
    """X04 decision D-9: a display item without a value prints `-` with its reason (`text`) and
    an empty cell (`csv`). No registered stream reaches one; the document is edited to hold it."""
    document = stream_table.from_bundle(solved.bundle(solved.rankine))
    shown = stream_table.displayed(document, DisplayUnits({"temperature": "degF"}))
    stream = next(s for s in shown["streams"] if s["T"] is not None)
    reason = {"code": "display_out_of_range", "params": {"kind": "temperature", "unit": "degF"}}
    stream["display"]["T"] = {"value": None, "unit": "degF", "reason": reason}
    text = stream_table_format.to_text(shown)
    assert "*1 display_out_of_range(kind=temperature, unit=degF)" in text.splitlines()
    rows = list(csv.reader(io.StringIO(stream_table_format.to_csv(shown))))
    row = dict(zip(rows[0], next(r for r in rows[1:] if r[0] == stream["id"]), strict=True))
    assert row["T_degF"] == ""


def test_d8_a_bundle_directory_takes_a_preference_without_an_ambient(
    solved: Solved, capsys: pytest.CaptureFixture[str]
) -> None:
    """X04 decision D-8: `streams DIR --display-units` resolves the preference with no ambient
    pressure; the display members are the project mode's, and a gauge unit is refused as the
    operation refuses it in a project without an ambient."""
    bundle = solved.bundle(solved.rankine)
    code, out, _ = streams(str(bundle), "--format", "json", "--display-units", "eng", capsys=capsys)
    assert code == 0
    by_directory = json.loads(out)
    by_job = table(solved.project, solved.rankine, "eng")["value"]
    by_directory["source"] = by_job["source"]
    assert by_directory == json.loads(canonical_json(by_job))
    code, out, err = streams(
        str(bundle), "--format", "json", "--display-units", "pressure=barg", capsys=capsys
    )
    assert code == API_EXIT_CODES["invalid_request"]
    refused = json.loads(out)
    assert refused["message"] == 'ambient_pressure_undeclared(pressure): "barg"'
    assert refused["detail"]["pointer"] == "/display_units"
    assert err


@pytest.mark.parametrize("text", ["", "x" * 1025])
def test_d8_a_bundle_directory_applies_the_request_bound_first(
    solved: Solved, text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """X04 review S4: `--display-units` outside 1 to 1024 characters is refused for a bundle
    directory exactly as for a project's job — by the request schema, at `/display_units`."""
    printed = []
    for argv in ([str(solved.bundle(solved.rankine))], _by_job(solved, solved.rankine)):
        code, out, _ = streams(*argv, "--format", "json", "--display-units", text, capsys=capsys)
        assert code == API_EXIT_CODES["invalid_request"]
        refused = json.loads(out)
        assert refused["detail"]["pointer"] == "/display_units"
        printed.append((refused["code"], refused["message"], refused["detail"]))
    assert printed[0] == printed[1]


# -- A31. Parity on every transport ----------------------------------------------------------------

PARITY = (
    ("eng", None),
    ("eng,pressure=barg", 101325.0),
    ("temp=degC", None),
    ("temperature=celsius", None),
    ("eng,pressure=barg", None),
    ("mole_fraction=%,molar_entropy=kJ/(mol K)", None),
)


@pytest.fixture
def clients(solved: Solved, tmp_path: Path) -> Iterator[dict[str, Client]]:
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    capability, token = grant(
        solved.project, principal_id=f"agent-{tmp_path.name}", rights=("read",)
    )
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    opened: dict[str, Client] = {
        "python": PythonInline(solved.project),
        "cli": CliClient(solved.project, tmp_path / "raw.bin", out, err),
        "http": HttpClient(solved.project, token),
        "mcp": McpClient(solved.project, capability),
    }
    try:
        yield opened
    finally:
        for client in opened.values():
            client.close()
        set_ambient_pressure(solved.project, None)


def test_a31_parity_on_every_transport(
    solved: Solved, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli_client = clients["cli"]
    assert isinstance(cli_client, CliClient)
    monkeypatch.setattr(sys, "stdout", cli_client.out)
    monkeypatch.setattr(sys, "stderr", cli_client.err)
    outcomes: dict[str, tuple[bool, str]] = {}
    for text, pascal in PARITY:
        set_ambient_pressure(solved.project, pascal)
        request = {"job_id": solved.syn001, "display_units": text}
        seen: dict[str, tuple[bool, bytes]] = {}
        for name, client in clients.items():
            refused, document = client.call("get_stream_table", request)
            if refused:
                document = {k: document[k] for k in ("code", "message", "detail")}
                document["detail"] = {
                    k: v for k, v in document["detail"].items() if k != "explanation"
                }
            else:
                assert schema_errors(SCHEMA, document["value"]) == [], name
            seen[name] = (refused, canonical_json(document))
        assert len(set(seen.values())) == 1, (text, pascal, seen)
        refused, body = seen["python"]
        outcomes[f"{text}|{pascal}"] = (refused, json.loads(body).get("code", "ok"))
    assert outcomes == {
        "eng|None": (False, "ok"),
        "eng,pressure=barg|101325.0": (False, "ok"),
        "temp=degC|None": (True, "invalid_request"),
        "temperature=celsius|None": (True, "unsupported"),
        "eng,pressure=barg|None": (True, "invalid_request"),
        "mole_fraction=%,molar_entropy=kJ/(mol K)|None": (False, "ok"),
    }


@pytest.mark.parametrize(("text", "pascal"), PARITY, ids=[f"{t}|{a}" for t, a in PARITY])
def test_a31_the_streams_command_agrees_with_the_operation(
    solved: Solved, text: str, pascal: float | None, capsys: pytest.CaptureFixture[str]
) -> None:
    with ambient(solved.project, pascal):
        code, out, _ = streams(
            *_by_job(solved, solved.syn001), "--format", "json", "--display-units", text,
            capsys=capsys,
        )  # fmt: skip
        try:
            document: Any = table(solved.project, solved.syn001, text)["value"]
            expected = 0
        except ApplicationError as refused:
            document = refused.error.as_document()
            expected = API_EXIT_CODES[document["code"]]
    assert code == expected
    printed = json.loads(out)
    if expected == 0:
        assert printed == json.loads(canonical_json(document))
    else:
        assert (printed["code"], printed["message"]) == (document["code"], document["message"])


# -- A32, A33. Schemas -----------------------------------------------------------------------------


def test_a33_the_request_schema_declares_display_units() -> None:
    schema = OPERATIONS["get_stream_table"].request_schema
    assert schema["properties"]["display_units"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 1024,
    }
    assert "display_units" not in schema.get("required", [])
    assert schema.get("additionalProperties") is False


def test_a33_a_displayed_document_round_trips_and_its_display_members_are_closed(
    solved: Solved,
) -> None:
    with ambient(solved.project, 101325.0):
        shown = table(solved.project, solved.syn001, "eng,pressure=barg")["value"]
    assert schema_errors(SCHEMA, shown) == []
    assert canonical_json(json.loads(canonical_json(shown))) == canonical_json(shown)
    stream = shown["streams"][0]
    for bad in (
        {**stream["display"], "rho": {"value": 1.0, "unit": "kg/m3"}},  # not a site
        {**stream["display"], "T": {"value": 1.0}},  # no unit
        {},  # never empty
    ):
        edited = json.loads(canonical_json(shown))
        edited["streams"][0]["display"] = bad
        assert schema_errors(SCHEMA, edited) != [], bad
    edited = json.loads(canonical_json(shown))
    edited["display_units"]["ambient_pressure"] = {"value": 0.0, "unit": "Pa"}
    assert schema_errors(SCHEMA, edited) != []


# -- A34. Reads write nothing ----------------------------------------------------------------------


def _state(project: Path) -> dict[str, Any]:
    files = {
        str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(project.rglob("*"))
        if path.is_file() and not path.name.startswith(DATABASE_NAME)
    }
    connection = sqlite3.connect(project / DATABASE_NAME)
    try:
        tables = [
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            if row[0] != "audit"
        ]
        rows = {
            name: sorted(map(repr, connection.execute(f"SELECT * FROM {name}"))) for name in tables
        }
    finally:
        connection.close()
    return {"files": files, "rows": rows}


def test_a34_reads_write_nothing_but_audit_rows(solved: Solved) -> None:
    with ambient(solved.project, 101325.0):
        before = _state(solved.project)
        with LocalApplication.open(solved.project) as app:
            for text, _ in PREFERENCES:
                for job_id in solved.jobs:
                    app.get_stream_table(job_id, display_units=text)
                    app.get_job_result(job_id, display_units=text)
        after = _state(solved.project)
    assert after == before
    assert len(before["files"]) > 0 and "jobs" in before["rows"]
