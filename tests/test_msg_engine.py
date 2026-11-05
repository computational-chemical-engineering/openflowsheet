"""MSG WO-1: the message engine (design note `docs/design/MSG-messages.md` §4.2–§4.6, §4.11, §4.13).

- §4.3's twelve legacy-grammar examples, lexical and resolved;
- §4.13's four worked entries render exactly the texts printed there from the stated params (the
  Python surface for the text format, surface `null` for documents);
- §4.5's number-format examples;
- MSG-G4, the catalogue lint;
- totality (I9): every entry × (its examples, empty params, 500 random 3-code chains over every
  key, fixed seed) never raises with the audit off;
- `register()`'s four refusals (§4.11).
"""

from __future__ import annotations

import math
import random
from typing import Any, get_args

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.messages import audit
from openflowsheet.messages.catalogue import (
    CATALOGUE,
    DOCS_BASE,
    FAMILY_PAGES,
    KINDS,
    Catalogue,
    CatalogueError,
)
from openflowsheet.messages.diagnostic import Diagnostic, Quantity
from openflowsheet.messages.legacy import PROPERTY_STATUSES, Chain, Segment, parse_chain, resolve
from openflowsheet.messages.lint import jargon, lint, review_count
from openflowsheet.messages.render import (
    RenderContext,
    format_number,
    render_code,
    render_error,
    render_failure,
)
from openflowsheet.messages.text import format_text

DOCS = f"{DOCS_BASE}messages/"
EXPLANATION_KEYS = {
    "code", "family", "kind", "complete", "summary", "cause", "where", "why", "action", "hint",
    "elements", "numbers", "gap", "chain", "docs",
}  # fmt: skip


@pytest.fixture(autouse=True)
def _audit_off() -> Any:
    """Every test here runs with the audit off (production behaviour), restoring it after."""
    saved = audit.auditor
    audit.auditor = None
    yield
    audit.auditor = saved


# -- §4.3: the legacy grammar --------------------------------------------------------------------

PARSE_EXAMPLES: list[tuple[str, list[tuple[str, tuple[str, ...]]], str | None, str | None]] = [
    (
        "initializer_failed(T): phase_regime_mismatch(S4)",
        [("initializer_failed", ("T",)), ("phase_regime_mismatch", ("S4",))],
        None,
        None,
    ),
    (
        "initializer_failed(traversal-G0-v1): unsupported: phase_regime_mismatch(S4)",
        [("initializer_failed", ("traversal-G0-v1",)), ("phase_regime_mismatch", ("S4",))],
        "unsupported",
        None,
    ),
    (
        "initializer_failed(T): isentropic_state_two_phase(T)",
        [("initializer_failed", ("T",)), ("isentropic_state_two_phase", ("T",))],
        None,
        None,
    ),
    ("task_unsupported(optimization)", [("task_unsupported", ("optimization",))], None, None),
    (
        "unsupported(legacy_route_not_admitted)",
        [("unsupported", ("legacy_route_not_admitted",))],
        None,
        None,
    ),
    (
        "internal_error(solution_state_mismatch)",
        [("internal_error", ("solution_state_mismatch",))],
        None,
        None,
    ),
    (
        "out_of_domain: temperature 250.0 K outside [280.0, 440.0] K",
        [("out_of_domain", ())],
        None,
        "temperature 250.0 K outside [280.0, 440.0] K",
    ),
    ("inadmissible_phase(inlet, VAPOR)", [("inadmissible_phase", ("inlet", "VAPOR"))], None, None),
    (
        "failure_bundle_unmapped(STAGNATION,x,y)",
        [("failure_bundle_unmapped", ("STAGNATION", "x", "y"))],
        None,
        None,
    ),
    ("no such artifact", [], None, "no such artifact"),
    (
        "pressure_rise(turbine)\nP_spec = 2e5 Pa is above the inlet's 1e5 Pa",
        [("pressure_rise", ("turbine",))],
        None,
        "P_spec = 2e5 Pa is above the inlet's 1e5 Pa",
    ),
    (
        "restart_initializer_failed: initializer_failed(T): phase_regime_mismatch(S4)",
        [
            ("restart_initializer_failed", ()),
            ("initializer_failed", ("T",)),
            ("phase_regime_mismatch", ("S4",)),
        ],
        None,
        None,
    ),
]


@pytest.mark.parametrize(("text", "segments", "status", "detail"), PARSE_EXAMPLES)
def test_the_legacy_grammar_parses_the_twelve_examples(
    text: str, segments: list[tuple[str, tuple[str, ...]]], status: str | None, detail: str | None
) -> None:
    assert parse_chain(text, CATALOGUE) == Chain(
        tuple(Segment(code, args) for code, args in segments), status, detail
    )


@pytest.mark.parametrize(
    ("text", "codes", "named"),
    [
        (
            "unsupported(legacy_route_not_admitted)",
            ["unsupported", "legacy_route_not_admitted"],
            {"reason": "legacy_route_not_admitted"},
        ),
        (
            "internal_error(solution_state_mismatch)",
            ["internal_error", "solution_state_mismatch"],
            {"reason": "solution_state_mismatch"},
        ),
        ("initializer_failed(T): phase_regime_mismatch(S4)", None, {"unit": "T"}),
    ],
)
def test_resolution_names_args_and_expands_code_args(
    text: str, codes: list[str] | None, named: dict[str, str]
) -> None:
    links = resolve(parse_chain(text, CATALOGUE), CATALOGUE)
    if codes is not None:
        assert [link.code for link in links] == codes
        assert links[1].expanded
    assert links[0].params == named


def test_a_status_is_a_code_where_no_code_follows_it() -> None:
    """Rule 3: `unsupported` followed by detail text is the catalogue's code (rule 2), not a
    status; `out_of_domain` followed by text is the code `out_of_domain`."""
    assert parse_chain("unsupported: whatever follows", CATALOGUE).codes == ("unsupported",)
    assert parse_chain("unsupported", ()).codes == ()


def test_the_restated_property_statuses_are_thermos() -> None:
    from openflowsheet.thermo import PropertyStatus

    assert frozenset(get_args(PropertyStatus)) == PROPERTY_STATUSES


DETAIL_CATALOGUE = {
    "kinds.yaml": (REPO_ROOT / "src/openflowsheet/messages/catalogue/kinds.yaml").read_text(),
    "vocabulary.yaml": "catalogue: openflowsheet-messages-v1\nvocabulary: {}\n",
    "test.yaml": """
catalogue: openflowsheet-messages-v1
namespace: null
entries:
  - code: out_of_domain
    family: refusal
    kind: input
    complete: false
    title: A value outside the range the property method covers
    detail_pattern: >-
      (?P<what>[a-z]+) (?P<value>[-0-9.e]+) (?P<value_unit>\\S+)
      outside \\[(?P<low>[-0-9.e]+), (?P<high>[-0-9.e]+)\\] (?P<low_unit>\\S+)
    params:
      what: {type: text, optional: true}
      value: {type: quantity, optional: true, quantity_kind: temperature}
      low: {type: quantity, optional: true, unit: K}
      high: {type: number, optional: true}
      detail: {type: text, optional: true}
    summary: "The {what} {value} is outside [[{low}, {high}]]."
""",
}


def test_a_detail_pattern_names_numbers_and_quantities() -> None:
    catalogue = Catalogue(DETAIL_CATALOGUE)
    text = "out_of_domain: temperature 250.0 K outside [280.0, 440.0] K"
    (link,) = resolve(parse_chain(text, catalogue), catalogue)
    assert link.params == {
        "detail": "temperature 250.0 K outside [280.0, 440.0] K",
        "what": "temperature",
        "value": {"value": 250.0, "unit": "K", "kind": "temperature"},
        "low": {"value": 280.0, "unit": "K", "kind": None},
        "high": 440.0,
    }
    explanation = render_failure(outcome="X", message=text, catalogue=catalogue, strict=True)
    assert explanation["summary"] == "The temperature 250.0 K is outside [280.0 K, 440.0]."
    assert [n["name"] for n in explanation["numbers"]] == ["value", "low", "high"]


# -- §4.5: numbers -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (2627345.1, "2627000"),
        (10000.0, "10000"),
        (0.0812345, "0.08123"),
        (373.124, "373.1"),
        (0.0, "0"),
        (47330.0, "47330"),
        (140.2, "140.2"),
        (1.5e-5, "1.5e-05"),
        (2.5e9, "2.5e+09"),
        (-373.124, "-373.1"),
    ],
)
def test_the_number_format(value: float, text: str) -> None:
    assert format_number(value) == text


def test_a_diagnostic_drops_non_finite_numbers() -> None:
    diagnostic = Diagnostic(
        "x",
        {"a": math.nan, "b": 1.0, "q": Quantity(math.inf, "Pa", "pressure"), "s": "S4", "n": 3},
    )
    assert diagnostic.as_document() == {"code": "x", "params": {"b": 1.0, "s": "S4", "n": 3}}


# -- §4.13: the worked entries ---------------------------------------------------------------------

REVISION = {
    "instances": [
        {"id": "F", "model": {"id": "syn001.feed_source"}},
        {"id": "P", "model": {"id": "thermal.pump"}},
        {"id": "T", "model": {"id": "thermal.turbine"}},
    ],
    "connections": [{"id": "S1"}, {"id": "S2"}, {"id": "S3"}, {"id": "S4"}],
}


def _q(value: float, unit: str, kind: str) -> dict[str, Any]:
    return {"value": value, "unit": unit, "kind": kind}


def _c01() -> dict[str, Any]:
    return render_failure(
        outcome="INITIALIZATION_FAILED",
        message="initializer_failed(T): phase_regime_mismatch(S4)",
        diagnosis={
            "code": "phase_regime_mismatch",
            "params": {
                "stream": "S4",
                "unit": "T",
                "declared": "vapor_liquid",
                "landed": "vapor",
                "property": "h",
                "value": _q(47330.0, "J/mol", "molar_enthalpy"),
                "saturated_vapour": _q(46570.0, "J/mol", "molar_enthalpy"),
                "pressure": _q(10000.0, "Pa", "pressure"),
            },
        },
        context=RenderContext(
            revision=REVISION,
            revision_id="rev-000005",
            job_id="job-000004",
            bundle_id="job-000004:bundle",
        ),
        strict=True,
    )


C01_TEXT = """\
The solve of revision 'rev-000005' stopped before its first iteration: unit 'T' (thermal.turbine) could not compute its outlets from the starting values.
  Cause:   Stream 'S4' is not in its declared phase: it is declared wet (vapour + liquid), but at these conditions it is vapour.
  Why:     At 10000 Pa the enthalpy of 'S4' is 47330 J/mol, above the saturated-vapour value 46570 J/mol, so the stream is vapour, not wet (vapour + liquid).
  Do:      Declare 'S4' as vapour: set connections[3].phase_capability to "vapor". If you expected wet (vapour + liquid), check the specifications that set the conditions upstream of 'S4'.
  Kind:    Input problem: something in the flowsheet or the request needs to change.
  Code:    phase_regime_mismatch, in INITIALIZATION_FAILED → initializer_failed (openflowsheet explain phase_regime_mismatch)
  Docs:    https://computational-chemical-engineering.github.io/openflowsheet/messages/refusals/#phase_regime_mismatch
  Details: initializer_failed(T): phase_regime_mismatch(S4) — job-000004:bundle/failure-bundle.json"""  # noqa: E501


def test_4_13_1_phase_regime_mismatch_text() -> None:
    details = (
        "initializer_failed(T): phase_regime_mismatch(S4) — job-000004:bundle/failure-bundle.json"
    )
    assert format_text(_c01(), details) == C01_TEXT


def test_4_13_1_phase_regime_mismatch_document() -> None:
    explanation = _c01()
    assert set(explanation) == EXPLANATION_KEYS
    assert explanation == {
        "code": "phase_regime_mismatch",
        "family": "refusal",
        "kind": "input",
        "complete": True,
        "summary": C01_TEXT.split("\n")[0],
        "cause": C01_TEXT.split("\n")[1][len("  Cause:   ") :],
        "where": "stream 'S4', an outlet of unit 'T' (thermal.turbine)",
        "why": C01_TEXT.split("\n")[2][len("  Why:     ") :],
        "action": C01_TEXT.split("\n")[3][len("  Do:      ") :],
        "hint": None,
        "elements": [
            {"type": "unit", "id": "T", "path": ["instances", 2]},
            {"type": "stream", "id": "S4", "path": ["connections", 3]},
        ],
        "numbers": [
            {
                "name": "value",
                "label": "computed value",
                "value": 47330.0,
                "unit": "J/mol",
                "kind": "molar_enthalpy",
            },
            {
                "name": "saturated_vapour",
                "label": "saturated-vapour value",
                "value": 46570.0,
                "unit": "J/mol",
                "kind": "molar_enthalpy",
            },
            {
                "name": "pressure",
                "label": "pressure",
                "value": 10000.0,
                "unit": "Pa",
                "kind": "pressure",
            },
        ],  # fmt: skip
        "gap": None,
        "chain": ["INITIALIZATION_FAILED", "initializer_failed", "phase_regime_mismatch"],
        "docs": f"{DOCS}refusals/#phase_regime_mismatch",
    }


def test_without_the_sidecar_the_legacy_text_still_explains() -> None:
    """§3.1: every existing message is explainable without touching its producer; the numbers
    missing from it are simply not shown."""
    explanation = render_failure(
        outcome="INITIALIZATION_FAILED",
        message="initializer_failed(T): phase_regime_mismatch(S4)",
        context=RenderContext(revision=REVISION, revision_id="rev-000005"),
        strict=True,
    )
    assert explanation["cause"] == "Stream 'S4' is not in its declared phase."
    assert explanation["why"] == (
        "Each stream carries a declared phase, and a unit computes its outlet only in that phase."
    )
    assert explanation["numbers"] == []


def test_a_sidecar_for_another_element_is_ignored() -> None:
    """§4.4: the diagnosis applies only when its element params agree with the chain's."""
    kwargs: dict[str, Any] = {
        "outcome": "INITIALIZATION_FAILED",
        "message": "initializer_failed(T): phase_regime_mismatch(S4)",
        "diagnosis": {
            "code": "phase_regime_mismatch",
            "params": {"stream": "S5", "landed": "vapor"},
        },
    }
    assert render_failure(**kwargs)["cause"] == "Stream 'S4' is not in its declared phase."
    audit.enable()
    try:
        with pytest.raises(Exception, match="does not match the chain"):
            render_failure(**kwargs)
    finally:
        audit.disable()


def test_4_13_2_isentropic_state_two_phase() -> None:
    explanation = render_failure(
        outcome="INITIALIZATION_FAILED",
        message="initializer_failed(T): isentropic_state_two_phase(T)",
        diagnosis=Diagnostic(
            "isentropic_state_two_phase",
            {
                "unit": "T",
                "outlet": "S4",
                "phase": "VAPOR",
                "s_star": Quantity(140.2, "J/(mol*K)", "molar_entropy"),
                "s_saturated": Quantity(146.3, "J/(mol*K)", "molar_entropy"),
                "pressure": Quantity(10000.0, "Pa", "pressure"),
            },
        ),
        context=RenderContext(revision=REVISION, revision_id="rev-000006", surface="python"),
        strict=True,
    )
    details = (
        "initializer_failed(T): isentropic_state_two_phase(T) — "
        "job-000005:bundle/failure-bundle.json"
    )
    lines = format_text(explanation, details).split("\n")
    # The note prints this text abbreviated; each printed prefix must hold.
    printed = [
        "The solve of revision 'rev-000006' stopped before its first iteration: unit 'T' "
        "(thermal.turbine) could not compute its outlets from the starting values.",
        "  Cause:   Unit 'T' needs a case this version does not support: its outlet 'S4' is "
        "declared vapour, but its ideal (isentropic) outlet state would be wet.",
        "  Why:     This version computes a turbine's ideal outlet in the phase declared for the "
        "real outlet. Here the ideal outlet entropy 140.2 J/(mol*K) is below ",
        "  Do:      Re-declare the outlet 'S4' as wet (\"vapor_liquid\") if it can be wet at your "
        "conditions. ",
        "  Kind:    Not supported in this version: a limitation of OpenFlowsheet, not an error in "
        "your flowsheet.",
        "  Code:    isentropic_state_two_phase, in INITIALIZATION_FAILED → initializer_failed "
        "(openflowsheet explain isentropic_state_two_phase)",
        f"  Docs:    {DOCS}refusals/#isentropic_state_two_phase",
        f"  Details: {details}",
    ]
    assert len(lines) == len(printed)
    for line, prefix in zip(lines, printed, strict=True):
        assert line.startswith(prefix)
    assert lines[2].endswith(
        "This is a limitation of the software (L-TH-4), not an error in your flowsheet."
    )
    assert explanation["kind"] == "not_supported"
    assert explanation["gap"] == {
        "limitation": "L-TH-4",
        "capability": "a vapour turbine outlet with a two-phase isentropic reference",
    }
    assert [n["name"] for n in explanation["numbers"]] == ["s_star", "s_saturated", "pressure"]


NOT_FOUND = {
    "code": "not_found",
    "message": "no such artifact",
    "retryable": False,
    "detail": {
        "operation": "artifact_bytes",
        "artifact_id": "job-000004:bundle/solution-state.json",
        "bundle_id": "job-000004:bundle",
        "member": "solution-state.json",
        "members": ["failure-bundle.json", "run-manifest.json"],
        "job_id": "job-000004",
        "run_outcome": "INITIALIZATION_FAILED",
    },
}


def test_4_13_3_not_found_document() -> None:
    assert render_error(NOT_FOUND, strict=True) == {
        "code": "not_found",
        "family": "api_error",
        "kind": "input",
        "complete": True,
        "summary": "Bundle 'job-000004:bundle' has no file 'solution-state.json': its run ended "
        "INITIALIZATION_FAILED and wrote no solution.",
        "cause": None,
        "where": None,
        "why": "A run that does not converge writes a failure bundle instead of a solution state "
        "and a certificate. This bundle holds failure-bundle.json, run-manifest.json.",
        "action": "Check the run's outcome before reading its results; the run result's failure "
        "says why it failed, and 'job-000004:bundle/failure-bundle.json' holds the evidence.",
        "hint": None,
        "elements": [
            {"type": "artifact", "id": "job-000004:bundle/solution-state.json", "path": None},
            {"type": "bundle", "id": "job-000004:bundle", "path": None},
            {"type": "job", "id": "job-000004", "path": None},
        ],
        "numbers": [],
        "gap": None,
        "chain": ["not_found"],
        "docs": f"{DOCS}api-errors/#not_found",
    }


def test_4_13_3_not_found_python_text_ends_with_the_old_string() -> None:
    text = format_text(
        render_error(NOT_FOUND, context=RenderContext(surface="python")),
        "not_found: no such artifact",
    )
    assert text.startswith("Bundle 'job-000004:bundle' has no file ")
    assert text.endswith("\n  Details: not_found: no such artifact")


PROJECT_EXISTS_TEXT = """\
Directory 'plant' is not empty: it already holds a project, and create() needs a new or empty directory.
  Why:     create() makes a new project and never reuses a directory, so a re-run cannot overwrite work silently.
  Do:      To use the existing project, call LocalApplication.open("plant"), or call LocalApplication.create("plant", exist_ok=True), which opens it.
  Kind:    Input problem: something in the flowsheet or the request needs to change.
  Code:    project_exists (openflowsheet explain project_exists)
  Docs:    https://computational-chemical-engineering.github.io/openflowsheet/messages/refusals/#project_exists
  Details: project_exists: plant"""  # noqa: E501


def test_4_13_4_project_exists_text() -> None:
    explanation = render_code(
        "project_exists",
        {"directory": "plant"},
        context=RenderContext(surface="python"),
        strict=True,
    )
    assert format_text(explanation, "project_exists: plant") == PROJECT_EXISTS_TEXT


def test_4_13_4_the_surfaces_and_directory_not_empty() -> None:
    cli = render_code(
        "project_exists", {"directory": "plant"}, context=RenderContext(surface="cli"), strict=True
    )
    assert cli["summary"] == (
        "Directory 'plant' is not empty: it already holds a project, and project init needs a new "
        "or empty directory."
    )
    assert cli["action"].endswith("or run project init with --exist-ok.")
    document = render_code("project_exists", {"directory": "plant"}, strict=True)
    assert document["action"] == "To use the existing project, open it instead."
    other = render_code("directory_not_empty", {"directory": "notes"}, strict=True)
    assert other["summary"] == (
        "Directory 'notes' is not empty and does not hold a project; a project needs a new or "
        "empty directory."
    )
    assert "not empty" in document["summary"]  # existing `match="not empty"` tests still pass


# -- MSG-G4 ----------------------------------------------------------------------------------------


def test_g4_the_catalogue_lint_is_clean() -> None:
    assert lint() == []
    print(f"MSG-G4: {len(CATALOGUE.keys())} entries, review: true on {review_count()}")


@pytest.mark.parametrize(
    ("template", "found"),
    [
        ("The closure {x} failed.", ["the word 'closure'"]),
        ("The initializer stopped.", ["the word 'initializer'"]),
        ("It is None here.", ["the word None 'None'"]),
        ("Use phase_capability here.", ["a snake_case token 'phase_capability'"]),
        ("See K05 for this.", ["a document id 'K05'"]),
        ("A RunResult was returned.", ["a class name 'RunResult'"]),
        ("Set it to 'vapor_liquid' and {x_y}.", []),
        ("The turbine's outlet and the run's state.", []),
    ],
)
def test_the_jargon_lint(template: str, found: list[str]) -> None:
    assert jargon(template) == found


def test_the_lint_finds_an_infeasibility_claim_and_an_undeclared_name() -> None:
    catalogue = Catalogue(
        {
            **{k: v for k, v in DETAIL_CATALOGUE.items() if k != "test.yaml"},
            "test.yaml": """
catalogue: openflowsheet-messages-v1
namespace: null
entries:
  - code: bad_entry
    family: refusal
    kind: input
    complete: false
    title: A bad entry
    summary: "This flowsheet has no solution at {nowhere}."
    see_also: [missing_code]
""",
        }
    )
    assert lint(catalogue) == [
        "bad_entry: summary: undeclared param 'nowhere'",
        "bad_entry: see_also: 'missing_code' does not resolve",
        "bad_entry: summary: says or implies that no solution exists ('has no solution')",
    ]


def test_the_docs_base_is_the_sites() -> None:
    document = yaml.safe_load(
        (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8").split("\nnav:")[0]
    )
    assert document["site_url"] == DOCS_BASE


# -- I9: totality ---------------------------------------------------------------------------------


def _valid(explanation: dict[str, Any]) -> None:
    assert set(explanation) == EXPLANATION_KEYS
    assert explanation["family"] in FAMILY_PAGES
    assert explanation["kind"] in KINDS
    assert isinstance(explanation["summary"], str) and explanation["summary"]
    assert isinstance(explanation["action"], str) and explanation["action"]
    assert explanation["docs"].startswith(DOCS)


def test_rendering_is_total() -> None:
    keys = CATALOGUE.keys()
    for entry in CATALOGUE.entries():
        for example in entry.examples:
            _valid(render_code(entry.code, dict(example["params"]), chain=example.get("chain")))
        _valid(render_code(entry.code, {}))
        _valid(render_failure(outcome=entry.code, message=None))
        _valid(render_error({"code": entry.code, "message": entry.code, "detail": {}}))
    draws = random.Random(20261105)
    for _ in range(500):
        chain = [draws.choice(keys) for _ in range(3)]
        _valid(render_code(chain[-1], {}, chain=chain))
        message = ": ".join(f"{code}(X)" for code in chain[1:])
        _valid(render_failure(outcome=chain[0], message=message))
        _valid(render_error({"code": chain[0], "message": message, "detail": {"reason": message}}))
    _valid(render_error({"code": "no_such_code", "message": "anything"}))
    _valid(render_failure(outcome="NO_SUCH_OUTCOME", message="nothing: known"))


# -- §4.11: register ------------------------------------------------------------------------------


def _extension(*codes: str, namespace: str | None = "ext") -> dict[str, Any]:
    return {
        "catalogue": "openflowsheet-messages-v1",
        "namespace": namespace,
        "entries": [
            {"code": code, "family": "refusal", "kind": "input", "complete": False,
             "title": "An extension refusal", "summary": "An extension refused."}
            for code in codes
        ],
    }  # fmt: skip


def test_register_adds_an_extensions_entries() -> None:
    catalogue = Catalogue()
    catalogue.register(_extension("ext.refused"), namespace="ext")
    assert "ext.refused" in catalogue
    assert render_code("ext.refused", catalogue=catalogue)["summary"] == "An extension refused."


def test_register_refuses_an_invalid_document() -> None:
    document = _extension("ext.refused")
    del document["entries"][0]["summary"]
    with pytest.raises(CatalogueError, match="summary"):
        Catalogue().register(document, namespace="ext")


def test_register_refuses_another_namespace_or_a_key_outside_it() -> None:
    with pytest.raises(CatalogueError, match="namespace"):
        Catalogue().register(_extension("ext.refused"), namespace="other")
    with pytest.raises(CatalogueError, match="not in namespace"):
        Catalogue().register(_extension("other.refused"), namespace="ext")


def test_register_refuses_a_key_already_present() -> None:
    catalogue = Catalogue()
    catalogue.register(_extension("ext.refused"), namespace="ext")
    with pytest.raises(CatalogueError, match="already in the catalogue"):
        catalogue.register(_extension("ext.refused"), namespace="ext")


def test_register_refuses_after_the_first_lookup() -> None:
    catalogue = Catalogue()
    assert "not_found" in catalogue
    with pytest.raises(RuntimeError, match="frozen"):
        catalogue.register(_extension("ext.refused"), namespace="ext")


def test_the_packaged_catalogue_is_schema_valid() -> None:
    """A production load skips the schema pass over the package's own files; this is that pass."""
    validated = Catalogue(validate_core=True)
    assert validated.keys() == CATALOGUE.keys()
    assert validated.sha256() == Catalogue(validate_core=False).sha256()


def test_the_catalogue_digest_is_a_sha256() -> None:
    digest = CATALOGUE.sha256()
    assert len(digest) == 64 and digest == Catalogue().sha256()
