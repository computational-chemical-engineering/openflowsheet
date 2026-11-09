"""MSG WO-9, MSG-G6: the beginner-mistake corpus (design note `docs/design/MSG-messages.md` §3.6,
§7; cases in `tests/fixtures/msg/corpus.yaml`).

Each case is one mistake, built by the setup function of its id through the public API, from the
README's Rankine change set, in a fresh project. A case asserts, on every surface it names:

- the explained `code`, its `kind` and the `chain` exactly, and that every code of the chain with a
  catalogue entry is a complete entry with a clean MSG-G4 lint;
- each element id in `explanation.elements` and in the summary text (line 1 and its cause), and
  each `in_summary` text in the summary text;
- the `numbers` names, where the case records them (`null`: a `pending` item does);
- an action containing the case's `action_token`, the `gap`, and a `docs` URL that resolves;
- the complete layered text equal to the stored `text` (an exact golden: `--msg-update` rewrites
  it, and the diff is reviewed);
- for a case on all four surfaces, one document on Python (dispatched), CLI, HTTP and MCP
  (MSG-G8), its explanation equal to the Python one.

A case's mistake must not depend on the machine: what would make it so is patched for every node
of the case, the setup included (`CASE_PATCHES`).

A case records the code the software emits (§3.6, Q8). What the design expects and the software
does not yet emit is a `pending` item: a strict xfail that turns red the day it holds
(`docs/MSG_DECISIONS.md` D9-1, D9-2).
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)
from test_msg_docs import docs_url_problems
from test_opt_request import UNAVAILABLE

from openflowsheet.application import cli
from openflowsheet.application.authz import grant
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import StoreError
from openflowsheet.application.types import Change, SolveFailedError
from openflowsheet.messages.catalogue import CATALOGUE
from openflowsheet.messages.lint import lint_entry
from openflowsheet.studies.nlp import closure

CORPUS = REPO_ROOT / "tests" / "fixtures" / "msg" / "corpus.yaml"
RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"
DOCUMENT: dict[str, Any] = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
CASES: dict[str, dict[str, Any]] = {case["id"]: case for case in DOCUMENT["cases"]}
FOUR = ("python", "cli", "http", "mcp")
TMP = "<tmp>"

#: Why a `pending` item does not hold yet; the keys are the corpus's `reason` values.
PENDING_REASONS: dict[str, str] = {
    "q1c": (
        "MSG review Q1 (c): a number only the thermal kernel knows, in no message text; deferred "
        "to the F6 v2 unit models (ADR 0065)"
    ),
    "ctx": (
        "MSG review Q2: an ApiError renders from its own document (projection, I2); the spec's "
        "unit text and the instance id need the revision document as render context"
    ),
}

# ======================================================================== the corpus file


def _header() -> str:
    lines = CORPUS.read_text(encoding="utf-8").split("\n")
    return "".join(f"{line}\n" for line in lines if line.startswith("#"))


class _Dumper(yaml.SafeDumper):
    """The corpus's own layout: scalar-only lists and maps in flow style, the rest in block
    style, multi-line strings as literal blocks."""


def _scalar(value: Any) -> bool:
    return not isinstance(value, dict | list) and not (isinstance(value, str) and "\n" in value)


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


def _represent_list(dumper: yaml.SafeDumper, value: list[Any]) -> yaml.Node:
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq", value, flow_style=all(map(_scalar, value))
    )


def _represent_dict(dumper: yaml.SafeDumper, value: dict[str, Any]) -> yaml.Node:
    flow = all(
        _scalar(item) or (isinstance(item, list) and all(map(_scalar, item)))
        for item in value.values()
    ) and not {"id", "what"} & set(value)
    return dumper.represent_mapping("tag:yaml.org,2002:map", value, flow_style=flow)


_Dumper.add_representer(str, _represent_str)
_Dumper.add_representer(list, _represent_list)
_Dumper.add_representer(dict, _represent_dict)


def _write_corpus() -> None:
    body = yaml.dump(DOCUMENT, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=4096)
    CORPUS.write_text(_header() + body, encoding="utf-8")


# ======================================================================== the setup functions


@dataclass
class Observed:
    """One case as the software showed it: the explanation per surface (the directory under test
    written `<tmp>`), the layered text per surface, and the transported call, if any."""

    explanations: dict[str, dict[str, Any]]
    texts: dict[str, str]
    project: Path | None = None
    call: tuple[str, dict[str, Any]] | None = None
    at: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


def _portable(value: Any, root: Path) -> Any:
    """`value` with the directory `root` written `<tmp>`."""
    text = json.dumps(value)
    return json.loads(text.replace(json.dumps(str(root))[1:-1], TMP))


def _rankine(edit: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(RANKINE.read_text(encoding="utf-8"))
    if edit is not None:
        edit(document)
    return document


def _member(document: dict[str, Any], path: str) -> list[dict[str, Any]]:
    (value,) = [e["value"] for e in document["edits"] if e["path"] == [path]]
    return value  # type: ignore[no-any-return]


def _spec(document: dict[str, Any], spec_id: str) -> dict[str, Any]:
    (spec,) = [s for s in _member(document, "specifications") if s["id"] == spec_id]
    return spec


def _boiler_hot(document: dict[str, Any]) -> None:
    _spec(document, "boiler-T")["value"] = 973.15


def _s4_vapour(document: dict[str, Any]) -> None:
    _boiler_hot(document)
    (s4,) = [c for c in _member(document, "connections") if c["id"] == "S4"]
    s4["phase_capability"] = "vapor"


def _pump_temperature(document: dict[str, Any]) -> None:
    extra = copy.deepcopy(_spec(document, "boiler-T"))
    extra.update(
        id="pump-T",
        target={"object_type": "instance", "object_id": "P", "path": "outlet.T"},
        value=320.0,
    )
    _member(document, "specifications").append(extra)


def _no_turbine_pressure(document: dict[str, Any]) -> None:
    specifications = _member(document, "specifications")
    specifications.remove(_spec(document, "turbine-P"))


def _degc(document: dict[str, Any]) -> None:
    _spec(document, "boiler-T").update(unit="degc", value=400.0)


def _cold_feed(document: dict[str, Any]) -> None:
    _spec(document, "feed-T")["value"] = 200.0


def _boiler_model(document: dict[str, Any]) -> None:
    (boiler,) = [i for i in _member(document, "instances") if i["id"] == "B"]
    boiler["model"]["id"] = "thermal.boiler"


def _turbine_compresses(document: dict[str, Any]) -> None:
    _spec(document, "turbine-P")["value"] = 5.0e6


def _commit(app: LocalApplication, document: dict[str, Any]) -> str:
    change, expected, key = Change.from_change_set(document)
    committed = app.commit_change(change, expected, key)
    assert committed.revision_id is not None, committed.error
    return committed.revision_id


def _create(base: Path) -> LocalApplication:
    return LocalApplication.create(base / "project", project_id="msg-corpus")


def _run_failure(base: Path, document: dict[str, Any]) -> Observed:
    with _create(base) as app:
        result = app.solve(_commit(app, document), "default")
    assert result.failure is not None, result.outcome
    with pytest.raises(SolveFailedError) as failed:
        result.raise_for_outcome()
    return Observed(
        explanations={"python": result.failure.explanation},
        texts={"python": str(failed.value)},
        project=base / "project",
        call=("get_job_result", {"job_id": result.job_id}),
        at=("run_result", "failure", "explanation"),
    )


def _refused(
    base: Path, document: dict[str, Any], act: Callable[[LocalApplication, str], Any], call: Any
) -> Observed:
    with _create(base) as app:
        revision = _commit(app, document)
        with pytest.raises(ApplicationError) as refused:
            act(app, revision)
    return Observed(
        explanations={"python": refused.value.explanation},
        texts={"python": str(refused.value)},
        project=base / "project",
        call=call(revision),
        at=("detail", "explanation"),
    )


def _refused_solve(base: Path, document: dict[str, Any]) -> Observed:
    def submit(revision: str) -> tuple[str, dict[str, Any]]:
        body = {"revision_id": revision}
        request = {"operation": "solve", "idempotency_key": "msg-corpus", "body": body}
        return "submit_job", request

    return _refused(base, document, lambda app, revision: app.solve(revision, "default"), submit)


def _cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


def _project_refusal(
    base: Path, name: str, prepare: Callable[[Path], None], exist_ok: bool
) -> Observed:
    """C04/C05: `create` on Python, `project init` on the CLI, each in its own directory."""
    explanations, texts, raw = {}, {}, {}
    for surface in ("python", "cli"):
        root = base / surface
        directory = root / name
        prepare(directory)
        with pytest.raises(StoreError) as refused:
            LocalApplication.create(directory, project_id="plant", exist_ok=exist_ok)
        explanations[surface] = _portable(refused.value.explanation(surface), root)
        if surface == "python":
            texts[surface] = _portable(str(refused.value), root)
        else:
            argv = ["project", "init", str(directory), "--project-id", "plant"]
            code, out, err = _cli([*argv, "--exist-ok"] if exist_ok else argv)
            raw["cli"] = (code, out)
            texts[surface] = _portable(err, root)
    return Observed(explanations=explanations, texts=texts, raw=raw)


def _c01(base: Path) -> Observed:
    return _run_failure(base, _rankine(_boiler_hot))


def _c02(base: Path) -> Observed:
    return _run_failure(base, _rankine(_s4_vapour))


def _c03(base: Path) -> Observed:
    with _create(base) as app:
        result = app.solve(_commit(app, _rankine(_boiler_hot)), "default")
        assert result.outcome == "INITIALIZATION_FAILED", result.outcome
        bundle = next(o.artifact_id for o in result.outputs if o.kind == "replay_bundle")
        missing = f"{bundle}/solution-state.json"
        with pytest.raises(ApplicationError) as refused:
            app.artifact_bytes(missing)
    return Observed(
        explanations={"python": refused.value.explanation},
        texts={"python": str(refused.value)},
        project=base / "project",
        call=("get_artifact", {"artifact_id": missing}),
        at=("detail", "explanation"),
    )


def _c04(base: Path) -> Observed:
    def existing(directory: Path) -> None:
        LocalApplication.create(directory, project_id="plant").close()

    return _project_refusal(base, "plant", existing, exist_ok=False)


def _c05(base: Path) -> Observed:
    def other_files(directory: Path) -> None:
        directory.mkdir(parents=True)
        (directory / "notes.txt").write_text("my notes\n", encoding="utf-8")

    return _project_refusal(base, "notes", other_files, exist_ok=True)


def _c12(base: Path) -> Observed:
    # The registered mistake is the default install's: no audited NLP solver (`CASE_PATCHES`).
    assert closure.audited_solver().available is False

    def call(revision: str) -> tuple[str, dict[str, Any]]:
        return "validate", {"revision_id": revision, "task": "optimization"}

    return _refused(
        base, _rankine(), lambda app, revision: app.validate(revision, "optimization"), call
    )


SETUP: dict[str, Callable[[Path], Observed]] = {
    "C01": _c01,
    "C02": _c02,
    "C03": _c03,
    "C04": _c04,
    "C05": _c05,
    "C06": lambda base: _refused_solve(base, _rankine(_pump_temperature)),
    "C07": lambda base: _refused_solve(base, _rankine(_no_turbine_pressure)),
    "C08": lambda base: _refused_solve(base, _rankine(_degc)),
    "C09": lambda base: _run_failure(base, _rankine(_cold_feed)),
    "C10": lambda base: _refused_solve(base, _rankine(_boiler_model)),
    "C11": lambda base: _run_failure(base, _rankine(_turbine_compresses)),
    "C12": _c12,
}


def _no_audited_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(closure, "audited_solver", lambda platform_id=None: UNAVAILABLE)


#: Patches applied to every node of a case, the setup on first use included, so that the case's
#: mistake does not depend on the machine. C12: with an audited solver installed, `validate` for
#: optimisation without a request is `invalid_request`, not the default install's refusal
#: (ruling `docs/reviews/MSG-catalogue-X02-OPT.md` §4, Amendment 1).
CASE_PATCHES: dict[str, Callable[[pytest.MonkeyPatch], None]] = {"C12": _no_audited_solver}


@pytest.fixture(autouse=True)
def _case_patches(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    callspec = getattr(request.node, "callspec", None)
    patch = CASE_PATCHES.get(callspec.params.get("case_id")) if callspec is not None else None
    if patch is not None:
        patch(monkeypatch)


@pytest.fixture(scope="module")
def observe(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Observed]:
    """Each case built once per module, on first use."""
    built: dict[str, Observed] = {}

    def get(case_id: str) -> Observed:
        if case_id not in built:
            observed = SETUP[case_id](tmp_path_factory.mktemp(f"msg-corpus-{case_id}"))
            if observed.call is not None:
                assert observed.project is not None
                name, body = observed.call
                argv = ["api", name, "--project", str(observed.project), "--json", json.dumps(body)]
                code, out, err = _cli(argv)
                is_error = observed.at[0] == "detail"
                document = json.loads(out)
                assert code == (cli.API_EXIT_CODES[document["code"]] if is_error else 0)
                observed.texts["cli"] = err
            built[case_id] = observed
        return built[case_id]

    return get


# ======================================================================== the assertions


def _summary_text(explanation: Mapping[str, Any]) -> str:
    return f"{explanation['summary']}\n{explanation.get('cause') or ''}"


def _element_ids(explanation: Mapping[str, Any]) -> set[str]:
    return {str(element["id"]) for element in explanation["elements"]}


def _assert_values(explanation: Mapping[str, Any], expect: Mapping[str, Any]) -> None:
    """Each named number equals its expectation to relative 1e-12; `above: [a, b]`: a > b."""
    numbers = {number["name"]: number["value"] for number in explanation["numbers"]}
    for name, value in expect.items():
        if name not in ("names", "above"):
            assert name in numbers, (name, sorted(numbers))
            assert numbers[name] == pytest.approx(value, rel=1e-12), name
    if "above" in expect:
        high, low = expect["above"]
        assert numbers[high] > numbers[low], (high, low)


def _assert_facts(case: Mapping[str, Any], explanation: Mapping[str, Any]) -> None:
    assert (explanation["code"], explanation["kind"]) == (case["code"], case["kind"])
    assert list(explanation["chain"]) == case["chain"]
    assert explanation["complete"] is True
    for code in explanation["chain"]:
        entry = CATALOGUE.entry(code)
        if entry is not None:
            assert entry.complete, code
            assert lint_entry(entry) == [], code
    text = _summary_text(explanation)
    for element in case["elements"]:
        assert element in _element_ids(explanation), (element, explanation["elements"])
        assert element in text, (element, text)
    for expected in case["in_summary"]:
        assert expected in text, (expected, text)
    if case["numbers"] is not None:
        assert [number["name"] for number in explanation["numbers"]] == case["numbers"]
    _assert_values(explanation, case.get("values", {}))
    assert case["action_token"] in explanation["action"], explanation["action"]
    if case["gap"] is None:
        assert explanation["gap"] is None
    else:
        gap = explanation["gap"]
        assert gap["limitation"] == case["gap"]["limitation"]
        assert bool(gap["capability"]) is case["gap"]["capability"]
    assert docs_url_problems([explanation["docs"]]) == []


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_g6_the_case_explains_the_mistake(
    case_id: str, observe: Callable[[str], Observed], request: pytest.FixtureRequest
) -> None:
    case, observed = CASES[case_id], observe(case_id)
    assert set(observed.texts) == set(case["surfaces"]) & {"python", "cli"}
    for explanation in observed.explanations.values():
        _assert_facts(case, explanation)
    if "cli" in observed.raw:
        assert observed.raw["cli"] == (2, "")  # project init: exit 2, nothing on stdout
    if request.config.getoption("--msg-update"):
        case["text"] = dict(observed.texts)
        _write_corpus()
    assert observed.texts == case.get("text"), "regenerate with --msg-update and review the diff"


def _without_clock(outcome: tuple[bool, Any]) -> tuple[bool, Any]:
    """The outcome without the validation report's `provenance.timestamp`, a clock reading each
    call makes afresh (as `tests/test_t07_conformance.py` strips it)."""
    is_error, document = outcome
    document = copy.deepcopy(document)
    report = document.get("detail", {}).get("report") if isinstance(document, dict) else None
    if isinstance(report, dict):
        report.get("provenance", {}).pop("timestamp", None)
    return is_error, document


def _at(document: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        document = document[key]
    return document


@pytest.mark.parametrize("case_id", sorted(c for c in CASES if CASES[c]["surfaces"] == list(FOUR)))
def test_g8_a_case_is_one_document_on_every_transport(
    case_id: str,
    observe: Callable[[str], Observed],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    observed = observe(case_id)
    assert observed.project is not None and observed.call is not None
    capability, token = grant(observed.project, principal_id=f"agent-msg-corpus-{case_id}")
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    clients: dict[str, Client] = {
        "python": PythonInline(observed.project),
        "cli": CliClient(observed.project, tmp_path / "raw.bin", out, err),
        "http": HttpClient(observed.project, token),
        "mcp": McpClient(observed.project, capability),
    }
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    try:
        documents = {
            name: _without_clock(client.call(*observed.call)) for name, client in clients.items()
        }
    finally:
        for client in clients.values():
            client.close()
    assert all(document == documents["python"] for document in documents.values()), documents
    is_error, document = documents["python"]
    assert is_error is (observed.at[0] == "detail")
    explanation = _at(document, observed.at)
    _assert_facts(CASES[case_id], explanation)
    python = observed.explanations["python"]
    for member in ("code", "kind", "chain", "summary", "cause", "why", "action", "elements"):
        assert explanation[member] == python[member], member


def _pending() -> Iterator[Any]:
    for case_id, case in sorted(CASES.items()):
        for index, item in enumerate(case["pending"]):
            mark = pytest.mark.xfail(
                strict=True, raises=AssertionError, reason=PENDING_REASONS[item["reason"]]
            )
            yield pytest.param(case_id, index, marks=mark, id=f"{case_id}-{item['what']}")


@pytest.mark.parametrize(("case_id", "index"), list(_pending()))
def test_g6_pending_holds(case_id: str, index: int, observe: Callable[[str], Observed]) -> None:
    """What the design expects of the case and the software does not emit yet (D9-1, D9-2)."""
    item = CASES[case_id]["pending"][index]
    explanation = observe(case_id).explanations["python"]
    expect = item["expect"]
    if item["what"] == "numbers":
        numbers = {number["name"] for number in explanation["numbers"]}
        assert set(expect["names"]) <= numbers, sorted(numbers)
        _assert_values(explanation, expect)
    elif item["what"] == "elements":
        for element in expect:
            assert element in _element_ids(explanation)
            assert element in _summary_text(explanation)
    elif item["what"] == "summary":
        assert expect in _summary_text(explanation)
    elif item["what"] == "action":
        assert expect in explanation["action"]
    else:
        assert item["what"] == "code"
        assert (explanation["code"], explanation["kind"]) == (expect["code"], expect["kind"])
        assert bool((explanation["gap"] or {}).get("capability")) is expect["capability"]


def test_g6_the_values_have_independent_expectations() -> None:
    """Review Q1: the corpus's `values` are not the software's own output. C11's are the case's
    inputs (its turbine outlet pressure and the pump outlet pressure that feeds the turbine,
    the heater's pressure drop being 0); C02's pressure is the turbine outlet's in the change
    set; C09's value is the feed temperature it sets and its range IAPWS-95's own
    (`thermo/iapws95.py` `T_MIN`, `T_MAX`)."""
    from openflowsheet.thermo import iapws95

    document = _rankine(_turbine_compresses)
    assert CASES["C11"]["values"] == {
        "p_spec": _spec(document, "turbine-P")["value"],
        "p_inlet": _spec(document, "pump-P")["value"],
    }
    assert CASES["C02"]["values"]["pressure"] == _spec(_rankine(), "turbine-P")["value"]
    assert CASES["C09"]["values"] == {
        "value": _spec(_rankine(_cold_feed), "feed-T")["value"],
        "low": iapws95.T_MIN,
        "high": iapws95.T_MAX,
    }


def test_g6_c02_saturated_entropy_is_the_providers_and_the_steam_tables(
    observe: Callable[[str], Observed],
) -> None:
    """Review Q1 / WO-5: C02's `s_saturated` equals an independent IAPWS-95 saturation call at
    the case pressure to relative 1e-12, and the steam tables' s_g(10 kPa) = 8.1488 kJ/(kg*K)
    (IAPWS-IF97 saturation-pressure table; molar mass 18.015268 g/mol) to their four decimals.
    The molar basis (J/(mol*K)) is the thermal kernel's."""
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.thermal.kernel import Failure, saturation
    from openflowsheet.thermo.iapws95 import Iapws95Provider

    numbers = {n["name"]: n for n in observe("C02").explanations["python"]["numbers"]}
    pressure, s_saturated = numbers["pressure"], numbers["s_saturated"]
    assert (pressure["unit"], s_saturated["unit"]) == ("Pa", "J/(mol*K)")
    context = EvaluationContext(model_version="msg-c02", constants_sha256="0" * 64)
    sat = saturation(Iapws95Provider(), pressure["value"], context)
    assert not isinstance(sat, Failure)
    assert s_saturated["value"] == pytest.approx(sat.value("VAPOR", "s"), rel=1e-12)
    assert s_saturated["value"] / 18.015268 == pytest.approx(8.1488, abs=5e-5)


def test_g6_the_corpus_is_well_formed() -> None:
    """Twelve cases, C01–C12; each `pending` item has a known reason and kind; `numbers` is null
    exactly when a pending item asserts them; every case has its stored text."""
    assert sorted(CASES) == [f"C{n:02d}" for n in range(1, 13)]
    assert sorted(SETUP) == sorted(CASES)
    for case_id, case in CASES.items():
        whats = [item["what"] for item in case["pending"]]
        assert set(whats) <= {"numbers", "elements", "summary", "action", "code"}, case_id
        assert {item["reason"] for item in case["pending"]} <= set(PENDING_REASONS), case_id
        assert (case["numbers"] is None) is ("numbers" in whats), case_id
        values = set(case.get("values", {})) - {"above"}
        assert values <= set(case["numbers"] or ()), case_id
        assert set(case.get("values", {}).get("above", ())) <= set(case["numbers"] or ()), case_id
        assert set(case.get("text", {})) == set(case["surfaces"]) & {"python", "cli"}, case_id
