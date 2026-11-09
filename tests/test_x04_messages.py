"""X04 WO-3: messages and `get_job_result` in the request's display units (ADR 0075 D7.2, D7.4,
D8, D9; ADR 0019 Amendment 17).

Assertions A15–A20, A31–A33 for `get_job_result`, and A36 of
`docs/derivations/X04-test-specification.md` §5 M, T, C (A33's round trips here, X04 decision
D-1). Display values are `units.display_item`'s, which `tests/test_x04_display_core.py` holds to
the reference (`docs/derivations/scripts/x04_reference.json`); the numbers quoted below are the
reference's DS states named beside them. A20's route is OQ3's default: a `thermal.valve` revision
(TH-V1) whose outlet pressure is above its inlet, refused `pressure_rise` with the sidecar's
numbers.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)

from openflowsheet.application.authz import grant, set_ambient_pressure
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication, _displayed
from openflowsheet.application.operations import OPERATIONS, dispatch, project_response
from openflowsheet.application.store import StoreError
from openflowsheet.application.types import (
    ApiError,
    Change,
    DocumentSchemaError,
    JobResult,
    schema_errors,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.messages.catalogue import CATALOGUE
from openflowsheet.messages.diagnostic import Diagnostic
from openflowsheet.messages.legacy import detail_params
from openflowsheet.messages.lint import lint
from openflowsheet.messages.render import (
    RenderContext,
    entry_document,
    format_number,
    render_code,
    render_error,
    render_failure,
)
from openflowsheet.units import DisplayUnits, DisplayUnitsError, display_item, parse_display_units
from openflowsheet.units.display import DISPLAY_KINDS

REFERENCE: dict[str, Any] = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "x04_reference.json").read_text("utf-8")
)
RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"
TH_V1 = REPO_ROOT / "benchmarks" / "s11" / "thermal" / "TH-V1.json"
JOB_RESULT = "job.schema.json#/$defs/job_result"
EXPLANATION = "application-results.schema.json#/$defs/explanation"
TEXT_FIELDS = ("summary", "cause", "where", "why", "action")
X04_CODES = (
    "display_units_invalid",
    "display_unit_unsupported",
    "ambient_pressure_undeclared",
    "ambient_pressure_invalid",
    "display_out_of_range",
)
pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)


def _from_detail(message: str, code: str, detail: str, units: DisplayUnits | None) -> Any:
    """A run failure's explanation from its sidecar detail line, as `tests/test_msg_engine.py`
    renders it, under the preference `units`."""
    return render_failure(
        outcome="INITIALIZATION_FAILED",
        message=message,
        diagnosis=Diagnostic(code, {"detail": detail}),
        context=RenderContext(display_units=units),
        strict=True,
    )


def _without_display(document: Any) -> Any:
    """`document` with every `display` member of an explanation's `numbers` item removed."""
    if isinstance(document, dict):
        return {
            key: _without_display(value)
            for key, value in document.items()
            if not (key == "display" and {"name", "kind"} <= document.keys())
        }
    if isinstance(document, list):
        return [_without_display(item) for item in document]
    return document


# -- A15. No preference, no change ----------------------------------------------------------------


def test_a15_no_preference_renders_every_example_as_msg_does() -> None:
    """MSG's own tests pass unchanged (the evidence for the corpus); here every catalogue example
    renders identically with no context, `display_units=None` and the empty preference (`si`),
    and no `numbers` item has `display`."""
    si = parse_display_units("si", None)
    assert (dict(si), si.ambient_pressure) == ({}, None)
    rendered = 0
    for entry in CATALOGUE.entries():
        for example in entry.examples:
            chain = example.get("chain")
            params = dict(example.get("params") or {})
            plain = render_code(entry.code, params, chain=chain, strict=True)
            for context in (RenderContext(display_units=None), RenderContext(display_units=si)):
                assert render_code(entry.code, params, chain=chain, context=context) == plain
            assert all("display" not in item for item in plain["numbers"]), entry.code
            rendered += 1
    assert rendered > 100


# -- A16–A18. Messages -----------------------------------------------------------------------------

TWO_PHASE = (
    "initializer_failed(T): isentropic_state_two_phase(T)",
    "isentropic_state_two_phase",
    "s* = 139.7797844964916 lies past the saturated VAPOR entropy 146.80317968321518 at 10000.0 Pa",
)
RISE = (
    "initializer_failed(T): pressure_rise(turbine)",
    "pressure_rise",
    "P_spec = 5000000.0 Pa is above the inlet's 3000000.0 Pa",
)


def test_a16_entropy_and_pressure() -> None:
    units = parse_display_units("molar_entropy=kJ/(mol K),pressure=bar", None)
    explanation = _from_detail(*TWO_PHASE, units)
    numbers = {item["name"]: item for item in explanation["numbers"]}
    assert {name: (n["value"], n["unit"], n["kind"]) for name, n in numbers.items()} == {
        "s_star": (139.7797844964916, "J/(mol*K)", "molar_entropy"),
        "s_saturated": (146.80317968321518, "J/(mol*K)", "molar_entropy"),
        "pressure": (10000.0, "Pa", "pressure"),
    }
    assert numbers["s_star"]["display"] == {"value": 0.1397797844964916, "unit": "kJ/(mol K)"}
    assert numbers["s_saturated"]["display"] == {
        "value": 0.14680317968321518,
        "unit": "kJ/(mol K)",
    }
    assert numbers["pressure"]["display"] == {"value": 0.1, "unit": "bar"}
    states = {state["id"]: state for state in REFERENCE["display_states"]}
    for name, state in (("s_star", "DS37"), ("s_saturated", "DS50"), ("pressure", "DS20")):
        assert numbers[name]["display"]["value"] == float(states[state]["display_value"])
    why = explanation["why"]
    for text in ("0.1398 kJ/(mol K)", "0.1468 kJ/(mol K)", "0.1000 bar"):
        assert text in why
    assert "139.8" not in why and "10000 Pa" not in why
    assert schema_errors(EXPLANATION, explanation) == []


def test_a17_gauge_in_a_message() -> None:
    units = parse_display_units("pressure=barg", 101325.0)
    explanation = _from_detail(*RISE, units)
    p_spec, p_inlet = explanation["numbers"]
    assert (p_spec["name"], p_spec["value"], p_spec["unit"]) == ("p_spec", 5000000.0, "Pa")
    assert p_spec["display"] == {"value": 48.98675, "unit": "barg"}  # DS48
    assert p_inlet["display"] == {"value": 28.98675, "unit": "barg"}  # DS49
    # Under the run's outcome the entry's summary is the explanation's `cause`; rendered on its
    # own, with the params the detail line gives, it is the summary.
    assert "(48.99 barg against 28.99 barg)" in explanation["cause"]
    assert "of 28.99 barg" in explanation["action"]
    entry = CATALOGUE.entry("pressure_rise")
    assert entry is not None
    params = {**detail_params(entry, RISE[2]), "machine": "turbine", "unit": "T"}
    alone = render_code(
        "pressure_rise", params, context=RenderContext(display_units=units), strict=True
    )
    assert "(48.99 barg against 28.99 barg)" in alone["summary"]
    assert "of 28.99 barg" in alone["action"]
    # Without an ambient there is no such render: the preference is refused first (A6, PU07),
    # and a gauge map without its ambient cannot be built.
    with pytest.raises(DisplayUnitsError) as refused:
        parse_display_units("pressure=barg", None)
    assert refused.value.reason == "ambient_pressure_undeclared"
    with pytest.raises(ValueError, match="ambient"):
        DisplayUnits({"pressure": "barg"})


def test_a18_no_kind_no_conversion() -> None:
    explanation = _from_detail(
        "initializer_failed(P): out_of_domain",
        "out_of_domain",
        "out_of_domain: temperature 200.0 K outside [273.16, 1273.15] K",
        parse_display_units("eng", None),
    )
    assert [item["value"] for item in explanation["numbers"]] == [200.0, 273.16, 1273.15]
    assert all("display" not in item for item in explanation["numbers"])
    assert "200.0 K" in explanation["why"]


def test_a16_raw_and_out_of_range_show_si() -> None:
    """D7.2: the `!raw` conversion and an out-of-range display render the SI text."""
    entry = CATALOGUE.entry("phase_regime_mismatch")
    assert entry is not None
    (example,) = entry.examples
    units = parse_display_units("pressure=bar,molar_enthalpy=kJ/mol", None)
    explanation = render_code(
        entry.code,
        dict(example["params"]),
        chain=example["chain"],
        context=RenderContext(display_units=units),
        strict=True,
    )
    assert "At 0.1000 bar the" in explanation["why"]
    assert "47.33 kJ/mol" in explanation["why"]
    # A quantity document's own kind decides (D4.1); kg/s → kg/h multiplies by 3600, so
    # 1e308 kg/s has no finite display value: the item says so and the text shows SI.
    units = parse_display_units("mass_flow=kg/h,pressure=psi", None)
    huge = render_code(
        "pressure_rise",
        {
            "machine": "valve",
            "p_spec": {"value": 1.0e308, "unit": "kg/s", "kind": "mass_flow"},
            "p_inlet": {"value": 1.0e5, "unit": "Pa", "kind": "pressure"},
        },
        context=RenderContext(display_units=units),
        strict=True,
    )
    p_spec, p_inlet = huge["numbers"]
    assert p_spec["display"] == {
        "value": None,
        "unit": "kg/h",
        "reason": {"code": "display_out_of_range", "params": {"kind": "mass_flow", "unit": "kg/h"}},
    }
    assert p_inlet["display"] == display_item(1.0e5, "pressure", units)
    assert "(1e+308 kg/s against 14.50 psi)" in huge["summary"]
    assert schema_errors(EXPLANATION, huge) == []


@pytest.mark.parametrize(("preference", "text"), [("eng", "°C"), ("temperature=degF", "°F")])
def test_d7_7_a_converted_temperature_shows_the_degree_sign(preference: str, text: str) -> None:
    """ADR 0075 D7.7 (FQ4, Frank, 2026-11-09): rendered text shows a converted temperature in
    `°C`/`°F`; the `numbers` item's `display.unit` stays the D2 spelling."""
    units = parse_display_units(preference, None)
    unit = units["temperature"]
    params = {
        "unit": "P",
        "what": "temperature",
        "value": {"value": 200.0, "unit": "K", "kind": "temperature"},
        "low": {"value": 273.16, "unit": "K", "kind": "temperature"},
        "high": {"value": 1273.15, "unit": "K", "kind": "temperature"},
    }
    explanation = render_code(
        "out_of_domain",
        params,
        chain=["INITIALIZATION_FAILED", "initializer_failed", "out_of_domain"],
        context=RenderContext(display_units=units),
        strict=True,
    )
    shown = []
    for item in explanation["numbers"]:
        assert item["display"] == display_item(item["value"], "temperature", units)
        assert item["display"]["unit"] == unit
        shown.append(f"{format_number(item['display']['value'])} {text}")
    value, low, high = shown
    assert (
        f"temperature {value} is outside the method's range of {low} to {high}."
        in (explanation["why"])
    )
    assert unit not in explanation["why"] and " K " not in explanation["why"]
    assert schema_errors(EXPLANATION, explanation) == []


@pytest.mark.parametrize(
    ("kind", "unit", "text"),
    [
        ("temperature", "degF", "°F"),
        ("temperature_difference", "degC", "°C"),
        ("mass_flow", "kg/h", "kg/h"),
    ],
)
def test_d7_7_out_of_range_names_the_unit_in_its_text_spelling(
    kind: str, unit: str, text: str
) -> None:
    """X04 D-21 (FQ4's rule, ADR 0075 D7.7): `display_out_of_range`'s rendered text names its
    `unit` param in the text spelling; the param itself, a machine member, keeps the D2 one."""
    entry = CATALOGUE.entry("display_out_of_range")
    assert entry is not None and entry.params["unit"].type == "display_unit"
    params = {"kind": kind, "unit": unit}
    explanation = render_code("display_out_of_range", params, strict=True)
    assert f"is too large to show in {text}, so" in explanation["summary"]
    assert f"Converting the value to {text} gives" in explanation["why"]
    if unit != text:
        assert all(unit not in str(explanation[field] or "") for field in TEXT_FIELDS)
    assert params == {"kind": kind, "unit": unit}
    assert schema_errors(EXPLANATION, explanation) == []


# -- A19. Pressure sites in the catalogue are absolute ---------------------------------------------


def test_a19_pressure_sites_in_the_catalogue_are_absolute() -> None:
    sites: set[str] = set()
    for entry in CATALOGUE.entries():
        for name, declared in entry.params.items():
            if declared.quantity_kind == "pressure":
                sites.add(f"{entry.code}.{name}")
        for example in entry.examples:
            for name, value in (example.get("params") or {}).items():
                if isinstance(value, dict) and value.get("kind") == "pressure":
                    sites.add(f"{entry.code}.{name}")
    assert sites == {
        "phase_regime_mismatch.pressure",
        "isentropic_state_two_phase.pressure",
        "pressure_fall.p_spec",
        "pressure_fall.p_inlet",
        "pressure_rise.p_spec",
        "pressure_rise.p_inlet",
    }


def test_a19_a_kinded_number_is_in_its_kinds_si_unit() -> None:
    """Review S2: `display_item` reads a kinded number's `value` as the kind's SI unit and never
    its `unit`. (a) Every kinded declaration and every kinded example quantity says that SI unit
    (`*` written as a space); (b) no `detail_pattern` captures a `<param>_unit` group for a param
    any entry declares kinded (a chain may type a group by another entry's declarations)."""
    seen = 0
    kinded: set[str] = set()
    for entry in CATALOGUE.entries():
        for name, declared in entry.params.items():
            if declared.quantity_kind is not None:
                kinded.add(name)
                unit = (declared.unit or "").replace("*", " ")
                assert unit == DISPLAY_KINDS[declared.quantity_kind].si_unit, (entry.code, name)
                seen += 1
        for example in entry.examples:
            for name, value in (example.get("params") or {}).items():
                if isinstance(value, dict) and value.get("kind") is not None:
                    unit = str(value.get("unit")).replace("*", " ")
                    assert unit == DISPLAY_KINDS[value["kind"]].si_unit, (entry.code, name)
                    seen += 1
    assert kinded and seen > len(kinded)
    for entry in CATALOGUE.entries():
        if entry.detail_pattern is None:
            continue
        groups = re.compile(entry.detail_pattern).groupindex
        captured = {g[: -len("_unit")] for g in groups if g.endswith("_unit")}
        assert not captured & kinded, (entry.code, sorted(captured & kinded))


# -- A20. `get_job_result` end to end --------------------------------------------------------------


def _valve_change_set() -> dict[str, Any]:
    """TH-V1 with the valve's outlet pressure 2 MPa, above its 1 MPa inlet (OQ3's route), as a
    change set of `set` edits in the README change set's member order."""
    change_set: dict[str, Any] = json.loads(RANKINE.read_text(encoding="utf-8"))
    document: dict[str, Any] = json.loads(TH_V1.read_text(encoding="utf-8"))
    (spec,) = [s for s in document["specifications"] if s["id"] == "SPEC-V-P"]
    spec["value"] = 2.0e6
    for edit in change_set["edits"]:
        edit["value"] = document[edit["path"][0]]
    change_set["idempotency_key"] = "x04-valve-rise"
    return change_set


class Valve:
    def __init__(self, project: Path, job_id: str) -> None:
        self.project, self.job_id = project, job_id


@pytest.fixture(scope="module")
def valve(tmp_path_factory: pytest.TempPathFactory) -> Valve:
    project = tmp_path_factory.mktemp("x04-messages") / "project"
    with LocalApplication.create(project, project_id="x04-messages") as app:
        change, _, key = Change.from_change_set(_valve_change_set())
        committed = app.commit_change(change, None, key)
        assert committed.revision_id is not None
        result = app.solve(committed.revision_id, "default")
    assert result.outcome == "INITIALIZATION_FAILED"
    assert result.failure is not None and result.failure.code == "pressure_rise"
    return Valve(project, result.job_id)


def test_a20_get_job_result_end_to_end(valve: Valve) -> None:
    with LocalApplication.open(valve.project) as app:
        plain = dispatch(app, "get_job_result", {"job_id": valve.job_id})
        shown = dispatch(
            app, "get_job_result", {"job_id": valve.job_id, "display_units": "pressure=bar"}
        )
    units = parse_display_units("pressure=bar", None)
    assert "display_units" not in plain
    assert shown["display_units"] == {"units": {"pressure": "bar"}, "ambient_pressure": None}
    explanation = shown["run_result"]["failure"]["explanation"]
    pressures = [item for item in explanation["numbers"] if item["kind"] == "pressure"]
    assert [item["name"] for item in pressures] == ["p_spec", "p_inlet"]
    for item in pressures:
        assert item["display"] == display_item(item["value"], "pressure", units)
    assert [item["display"]["value"] for item in pressures] == [20.0, 10.0]
    assert "(20.00 bar against 10.00 bar)" in explanation["cause"]
    assert "of 10.00 bar" in explanation["action"]
    # The SI content: with every `display` and the echo removed, the result is the one without
    # a preference except in the explanation's text fields.
    stripped = _without_display({k: v for k, v in shown.items() if k != "display_units"})
    for document in (stripped, plain):
        for field in TEXT_FIELDS:
            document["run_result"]["failure"]["explanation"].pop(field)
    assert stripped == plain
    with LocalApplication.open(valve.project) as app:
        unshown = dispatch(app, "get_job_result", {"job_id": valve.job_id})
    assert (
        "(2000000 Pa against 1000000 Pa)"
        in unshown["run_result"]["failure"]["explanation"]["cause"]
    )
    # A33: the responses validate and round-trip.
    for document in (unshown, shown):
        assert schema_errors(JOB_RESULT, document) == []
        assert JobResult.from_document(document).as_document() == document


def test_a20_error_documents_are_explained_under_the_preference() -> None:
    """D7.4: the `error` documents' explanations are rendered under the preference, and the
    projection every transport applies keeps them (`operations.explained_detail`)."""
    error = ApiError(
        code="unsupported",
        message="pressure_rise(turbine)",
        retryable=False,
        detail={
            "reason": "pressure_rise(turbine)",
            "p_spec": {"value": 5.0e6, "unit": "Pa", "kind": "pressure"},
            "p_inlet": {"value": 3.0e6, "unit": "Pa", "kind": "pressure"},
        },
    )
    result = JobResult(operation="reproduce", run_result=None, replay_report=None, error=error)
    units = parse_display_units("pressure=bar", None)
    operation = OPERATIONS["get_job_result"]
    plain = project_response(operation, result.as_document())
    shown = project_response(operation, _displayed(result, units).as_document())
    explanation = shown["error"]["detail"]["explanation"]
    assert explanation == render_error(
        error.as_document(), context=RenderContext(display_units=units)
    )
    assert explanation["code"] == "pressure_rise"
    assert [item["display"] for item in explanation["numbers"]] == [
        {"value": 50.0, "unit": "bar"},
        {"value": 30.0, "unit": "bar"},
    ]
    assert "(50.00 bar against 30.00 bar)" in explanation["summary"]
    assert shown["display_units"] == units.as_document()
    stripped = _without_display({k: v for k, v in shown.items() if k != "display_units"})
    for document in (stripped, plain):
        for field in TEXT_FIELDS:
            document["error"]["detail"]["explanation"].pop(field)
    assert stripped == plain
    assert schema_errors(JOB_RESULT, shown) == []


# -- A31, A36. Parity, refusals, `explain` --------------------------------------------------------

#: A31's preferences: (text, the ambient declared when it is sent).
PARITY = (
    ("eng", None),
    ("eng,pressure=barg", 101325.0),
    ("temp=degC", None),
    ("temperature=celsius", None),
    ("eng,pressure=barg", None),
    ("mole_fraction=%,molar_entropy=kJ/(mol K)", None),
)


@pytest.fixture
def clients(valve: Valve, tmp_path: Path) -> Iterator[dict[str, Client]]:
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    capability, token = grant(
        valve.project, principal_id=f"agent-{tmp_path.name}", rights=("read",)
    )
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    opened: dict[str, Client] = {
        "python": PythonInline(valve.project),
        "cli": CliClient(valve.project, tmp_path / "raw.bin", out, err),
        "http": HttpClient(valve.project, token),
        "mcp": McpClient(valve.project, capability),
    }
    try:
        yield opened
    finally:
        for client in opened.values():
            client.close()
        set_ambient_pressure(valve.project, None)


def _cli_streams(clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch) -> None:
    cli = clients["cli"]
    assert isinstance(cli, CliClient)
    # The CLI client's streams, set in the test body (pytest resets capture after setup).
    monkeypatch.setattr(sys, "stdout", cli.out)
    monkeypatch.setattr(sys, "stderr", cli.err)


def test_a31_parity_on_every_transport(
    valve: Valve, clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli_streams(clients, monkeypatch)
    outcomes: dict[str, tuple[bool, str]] = {}
    for text, ambient in PARITY:
        set_ambient_pressure(valve.project, ambient)
        request = {"job_id": valve.job_id, "display_units": text}
        seen: dict[str, tuple[bool, bytes]] = {}
        for name, client in clients.items():
            refused, document = client.call("get_job_result", request)
            if refused:
                document = {k: document[k] for k in ("code", "message", "detail")}
                document["detail"] = {
                    k: v for k, v in document["detail"].items() if k != "explanation"
                }
            else:
                assert schema_errors(JOB_RESULT, document) == [], name
            seen[name] = (refused, canonical_json(document))
        assert len(set(seen.values())) == 1, (text, ambient, seen)
        refused, body = seen["python"]
        outcomes[f"{text}|{ambient}"] = (refused, json.loads(body).get("code", "ok"))
    assert outcomes == {
        "eng|None": (False, "ok"),
        "eng,pressure=barg|101325.0": (False, "ok"),
        "temp=degC|None": (True, "invalid_request"),
        "temperature=celsius|None": (True, "unsupported"),
        "eng,pressure=barg|None": (True, "invalid_request"),
        "mole_fraction=%,molar_entropy=kJ/(mol K)|None": (False, "ok"),
    }


def test_a31_the_gauge_echo_carries_the_ambient(valve: Valve) -> None:
    set_ambient_pressure(valve.project, 101325.0)
    try:
        with LocalApplication.open(valve.project) as app:
            shown = dispatch(
                app, "get_job_result", {"job_id": valve.job_id, "display_units": "pressure=barg"}
            )
    finally:
        set_ambient_pressure(valve.project, None)
    assert shown["display_units"] == {
        "units": {"pressure": "barg"},
        "ambient_pressure": {"value": 101325.0, "unit": "Pa"},
    }
    p_spec, p_inlet = shown["run_result"]["failure"]["explanation"]["numbers"]
    assert (p_spec["display"]["value"], p_inlet["display"]["value"]) == (18.98675, 8.98675)


def test_a36_explain_returns_each_code_on_every_transport(
    clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli_streams(clients, monkeypatch)
    for code in X04_CODES:
        expected = entry_document(code)
        assert expected is not None and expected["complete"] is True, code
        for name, client in clients.items():
            refused, document = client.call("explain", {"code": code})
            assert not refused, (name, code, document)
            assert document["code"] == code, name


def _refusal(project: Path, text: str, ambient: float | None) -> dict[str, Any]:
    set_ambient_pressure(project, ambient)
    try:
        with LocalApplication.open(project) as app, pytest.raises(ApplicationError) as refused:
            dispatch(app, "get_job_result", {"job_id": "job-999999", "display_units": text})
    finally:
        set_ambient_pressure(project, None)
    return refused.value.error.as_document()


@pytest.mark.parametrize(
    "case",
    [c for c in REFERENCE["preferences"] if "refused" in c["expected"]],
    ids=lambda case: str(case["id"]),
)
def test_a36_every_preference_refusal_renders_strictly_with_its_entry(
    case: dict[str, Any], valve: Valve
) -> None:
    """A6's refusals, raised through `dispatch` (before the job is looked up): the `ApiError`
    the reference names, and its explanation is its own entry's, rendered strictly. PU16 is the
    request schema's."""
    expected = case["expected"]["refused"]
    ambient = None if case["ambient_pressure"] is None else float(case["ambient_pressure"])
    document = _refusal(valve.project, case["text"], ambient)
    assert document["code"] == expected["api_error"]
    if expected["reason"] == "schema":
        assert document["detail"]["pointer"] == expected["pointer"]
        return
    assert document["message"] == expected["message"]
    if expected["api_error"] == "invalid_request":
        assert document["detail"]["pointer"] == "/display_units"
    else:
        assert document["detail"]["reason"] == expected["message"]
    bare = {
        **document,
        "detail": {k: v for k, v in document["detail"].items() if k != "explanation"},
    }
    strict = render_error(bare, strict=True)
    assert strict["code"] == expected["reason"]
    assert strict["complete"] is True
    assert document["detail"]["explanation"] == render_error(bare)


def test_a36_the_ambient_refusal_renders_strictly_with_its_entry(tmp_path: Path) -> None:
    """A10's coded `StoreError`, rendered as the CLI renders it, strictly."""
    project = tmp_path / "project"
    with LocalApplication.create(project, project_id="x04-a36"):
        pass
    for pascal, part in ((0.0, "value"), (float("nan"), "value")):
        with pytest.raises(StoreError) as caught:
            set_ambient_pressure(project, pascal)
        assert caught.value.code == "ambient_pressure_invalid"
        explanation = render_code(
            "ambient_pressure_invalid", caught.value.params, context=RenderContext(), strict=True
        )
        assert explanation["code"] == "ambient_pressure_invalid", part
        assert explanation["complete"] is True


def test_a36_the_codes_have_complete_entries_and_lint_clean() -> None:
    for code in X04_CODES:
        entry = CATALOGUE.entry(code)
        assert entry is not None and entry.complete, code
    assert lint(CATALOGUE) == []


# -- A32. Closed elsewhere ------------------------------------------------------------------------


def test_a32_every_other_request_schema_refuses_display_units() -> None:
    from jsonschema import Draft202012Validator

    from openflowsheet.application.types import _registry

    registry = _registry(False)
    open_to = set()
    for name, operation in OPERATIONS.items():
        schema = operation.request_schema
        validator = Draft202012Validator(schema, registry=registry)
        errors = list(validator.iter_errors({"display_units": "eng"}))
        named = any("'display_units' was unexpected" in error.message for error in errors)
        properties = schema.get("properties", {})
        if "display_units" in properties:
            assert properties["display_units"] == {
                "type": "string",
                "minLength": 1,
                "maxLength": 1024,
            }, name
            assert not named, name
            open_to.add(name)
        else:
            assert schema.get("additionalProperties") is False or named, name
    # WO-4 adds `get_stream_table`; no other operation ever.
    assert "get_job_result" in open_to <= {"get_job_result", "get_stream_table"}


def test_a32_the_mcp_input_schemas_name_display_units_where_the_requests_do() -> None:
    pytest.importorskip("mcp")
    from openflowsheet.application.bindings.mcp import input_schema

    open_to = {
        name
        for name, operation in OPERATIONS.items()
        if "display_units" in operation.request_schema.get("properties", {})
    }
    mcp_named = {
        name
        for name, operation in OPERATIONS.items()
        if "mcp" in operation.transports and "display_units" in json.dumps(input_schema(operation))
    }
    assert mcp_named == open_to


#: A32's dynamic probe: operations whose valid request is cheap, on Python `dispatch` and HTTP.
CLOSED = (
    ("get_project", {}),
    ("list_jobs", {}),
    ("list_revisions", {}),
    ("list_models", {}),
    ("get_job", {"job_id": "@job"}),
    ("list_job_events", {"job_id": "@job"}),
    ("wait_job", {"job_id": "@job", "timeout_s": 0}),
    ("get_revision", {"revision_id": "rev-000001"}),
    ("explain", {"code": "pressure_rise"}),
    ("validate", {"revision_id": "rev-000001", "task": "simulation"}),
)


def test_a32_other_operations_refuse_display_units_on_dispatch_and_http(
    valve: Valve, clients: dict[str, Client]
) -> None:
    for name, template in CLOSED:
        request = {k: valve.job_id if v == "@job" else v for k, v in template.items()}
        for transport in ("python", "http"):
            refused, accepted = clients[transport].call(name, copy.deepcopy(request))
            assert not refused, (transport, name, accepted)
            refused, document = clients[transport].call(name, {**request, "display_units": "eng"})
            assert refused and document["code"] == "invalid_request", (transport, name)
            assert "display_units" in document["message"], (transport, name)


# -- A33. Schemas and fixtures ---------------------------------------------------------------------


def test_a33_the_request_schema_declares_display_units() -> None:
    schema = OPERATIONS["get_job_result"].request_schema
    assert schema["properties"]["display_units"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 1024,
    }
    assert schema["required"] == ["job_id"]
    assert schema["additionalProperties"] is False


def test_a33_explanation_display_items_validate() -> None:
    explanation = _from_detail(*RISE, parse_display_units("pressure=barg", 101325.0))
    assert schema_errors(EXPLANATION, explanation) == []
    out_of_range = copy.deepcopy(explanation)
    out_of_range["numbers"][0]["display"] = {
        "value": None,
        "unit": "psi",
        "reason": {"code": "display_out_of_range", "params": {"kind": "pressure", "unit": "psi"}},
    }
    assert schema_errors(EXPLANATION, out_of_range) == []
    for bad in (
        {"value": 1.0},
        {"value": None, "unit": "bar"},
        {"value": 1.0, "unit": "bar", "extra": 0},
        {"value": None, "unit": "bar", "reason": {"code": "other", "params": {}}},
    ):
        broken = copy.deepcopy(explanation)
        broken["numbers"][0]["display"] = bad
        assert schema_errors(EXPLANATION, broken) != [], bad


@pytest.mark.parametrize(
    "echo",
    [
        {"units": {}, "ambient_pressure": None},
        {"units": {"pressure": "bar", "temperature": "degC"}, "ambient_pressure": None},
        {"units": {"pressure": "barg"}, "ambient_pressure": {"value": 101325.0, "unit": "Pa"}},
    ],
)
def test_a33_job_result_with_display_units_round_trips(echo: dict[str, Any]) -> None:
    document = {
        "operation": "reproduce",
        "run_result": None,
        "replay_report": None,
        "error": None,
        "display_units": echo,
    }
    assert schema_errors(JOB_RESULT, document) == []
    result = JobResult.from_document(document)
    assert result.display_units is not None
    assert result.as_document() == document


@pytest.mark.parametrize(
    "echo",
    [
        {"units": {"pressure": "bar"}, "ambient_pressure": {"value": 101325.0, "unit": "Pa"}},
        {"units": {"pressure": "barg"}, "ambient_pressure": None},
        {"units": {"pressure": "parsec"}, "ambient_pressure": None},
    ],
)
def test_a33_an_inconsistent_echo_is_refused(echo: dict[str, Any]) -> None:
    document = {
        "operation": "reproduce",
        "run_result": None,
        "replay_report": None,
        "error": None,
        "display_units": echo,
    }
    assert schema_errors(JOB_RESULT, document) == []  # what the schema cannot state
    with pytest.raises(DocumentSchemaError):
        JobResult.from_document(document)


def test_a33_the_echo_is_closed() -> None:
    for echo in (
        {"units": {}},
        {"units": {}, "ambient_pressure": None, "extra": 1},
        {"units": {}, "ambient_pressure": {"value": 0.0, "unit": "Pa"}},
        {"units": {}, "ambient_pressure": {"value": 1.0, "unit": "bar"}},
        {"units": {"pressure": ""}, "ambient_pressure": None},
    ):
        document = {
            "operation": "reproduce",
            "run_result": None,
            "replay_report": None,
            "error": None,
            "display_units": echo,
        }
        assert schema_errors(JOB_RESULT, document) != [], echo
