"""OPT WO-3: the optimization request, its starts and formulation, static readiness, `validate`.

Design `docs/design/OPT-revision-optimisation.md` §4.3, §4.5 (static row), §4.11; ADR 0071 D2,
D8, D10. Gates G18 (request schema: round-trip fixtures, one test per static readiness reason,
Halton points within 1 ulp) and G11's default-install part (typed unsupported, no Pyomo or
cyipopt imported; the platform-not-audited path by a named platform). Build decisions D-16…
in `docs/OPT_DECISIONS.md`.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from t07_corpus import A02_FILES, CORPUS

from openflowsheet.application import validation
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import schema_errors
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.studies.nlp import closure
from openflowsheet.studies.nlp.closure import SolverAvailability, audited_solver
from openflowsheet.studies.nlp.request import (
    SCHEMA_REFERENCE,
    STATIC_CODES,
    OptimizationRequest,
    halton_point,
    request_formulation,
    request_problems,
    request_starts,
    static_readiness,
)
from openflowsheet.studies.nlp.revision_host import DecisionMap

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "schemas" / "optimization_request"
S11 = REPO / "benchmarks" / "s11"

AVAILABLE = SolverAvailability(True, "test double: an audited solver")
UNAVAILABLE = SolverAvailability(False, "test double: no audited solver")


def _available() -> SolverAvailability:
    return AVAILABLE


def _fixture(validity: str, name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((FIXTURES / validity / f"{name}.json").read_bytes())
    return document


def _th_r1() -> dict[str, Any]:
    document: dict[str, Any] = json.loads((S11 / "thermal" / "TH-R1.json").read_bytes())
    return document


# -- G18: the schema and its fixtures ------------------------------------------------------------


def test_g18_the_schema_is_a_draft_2020_12_schema_and_registered() -> None:
    schema = json.loads((REPO / "schemas" / SCHEMA_REFERENCE).read_bytes())
    Draft202012Validator.check_schema(schema)
    registry = json.loads((REPO / "schemas" / "registry.json").read_bytes())
    assert SCHEMA_REFERENCE in registry


@pytest.mark.parametrize("name", ["th_r1_minimal", "th_r1_full"])
def test_g18_a_valid_fixture_validates_and_round_trips(name: str) -> None:
    document = _fixture("valid", name)
    assert schema_errors(SCHEMA_REFERENCE, document) == []
    assert request_problems(document) == []
    assert json.loads(canonical_json(document)) == document
    read = OptimizationRequest.of(document)
    assert read.document == document
    assert read.sha256 == document_sha256(document)
    assert OptimizationRequest.of(json.loads(json.dumps(document))) == read


#: Invalid fixture → the pointer of its first problem (schema first, then the rules).
INVALID = {
    "missing_request_format": "",
    "zero_scale": "/decisions/0/scale",
    "unknown_member": "",
    "constraint_without_a_bound": "/constraints/0",
    "explicit_start_of_wrong_length": "/starts/explicit/0",
    "constraint_id_repeats": "/constraints/1/id",
    "expression_names_nothing": "/objective/expression",
    "sixty_five_decisions": "/decisions",
}


@pytest.mark.parametrize("name", sorted(INVALID))
def test_g18_an_invalid_fixture_is_refused_by_the_schema_or_the_rules(name: str) -> None:
    problems = request_problems(_fixture("invalid", name))
    assert problems, name
    assert problems[0][0] == INVALID[name], problems
    with pytest.raises(ValueError, match=r"^request_invalid\("):
        OptimizationRequest.of(_fixture("invalid", name))


def test_a_non_canonical_number_is_refused_naming_its_node() -> None:
    document = _fixture("valid", "th_r1_minimal")
    document["decisions"][0]["upper"] = math.inf
    assert request_problems(document) == [
        ("/decisions/0/upper", "document_not_canonical(/decisions/0/upper)")
    ]


# -- G18: Halton -------------------------------------------------------------------------------


def test_g18_halton_points_one_to_four_in_two_dimensions_within_one_ulp() -> None:
    expected = [(1 / 2, 1 / 3), (1 / 4, 2 / 3), (3 / 4, 1 / 9), (1 / 8, 4 / 9)]
    for k, point in enumerate(expected, start=1):
        found = halton_point(k, 2)
        for value, exact in zip(found, point, strict=True):
            assert abs(value - exact) <= math.ulp(exact), (k, found, point)


def test_starts_are_the_revision_the_explicit_then_halton_scaled_into_the_box() -> None:
    read = OptimizationRequest.of(_fixture("valid", "th_r1_full"))
    starts = request_starts(read, (25000.0, 300.0))
    assert starts[:2] == ((25000.0, 300.0), (22000.0, 295.0))
    for k, start in enumerate(starts[2:], start=1):
        u = halton_point(k, 2)
        assert start == (20000.0 + u[0] * 10000.0, 290.0 + u[1] * 20.0)
    assert len(starts) == read.start_count == 4


# -- the formulation -----------------------------------------------------------------------------


def test_the_formulation_stores_minimize_of_the_signed_scaled_objective() -> None:
    read = OptimizationRequest.of(_fixture("valid", "th_r1_full"))
    mapping = DecisionMap(MappingProxyType({"SPEC-H-Q": "H.Q_spec", "SPEC-S1-T": "S1.T_spec"}))
    formulation = request_formulation(read, mapping, ((25000.0, 300.0),))
    assert formulation.decision_ids == ("H.Q_spec", "S1.T_spec")
    assert [(d.lower, d.upper, d.scale) for d in formulation.decisions] == [
        (20000.0, 30000.0, 10000.0),
        (290.0, 310.0, 10.0),
    ]
    objective = formulation.objective
    assert dict(objective.linear) == {
        "S3.T": (-1.0 * 1.0) / 100.0,
        "H.Q_spec": (-1.0 * -0.001) / 100.0,
        "S1.T_spec": (-1.0 * -0.0006) / 100.0,
    }
    assert dict(objective.quadratic) == {("S1.T_spec", "S1.T_spec"): (-1.0 * 1e-6) / 100.0}
    assert objective.constant == (-1.0 * 0.09) / 100.0
    assert objective.text == "-(S3.T - 0.001*Q + 1e-6*(T1 - 300)^2)/100"
    assert formulation.as_document()["objective"]["sense"] == "minimize"
    (hot, band) = formulation.constraints
    assert (hot.constraint_id, dict(hot.expression.linear), hot.lower, hot.upper) == (
        "outlet-hot-enough",
        {"S3.T": 0.01},
        3.2,
        None,
    )
    assert (band.lower, band.upper) == (2.5, 6.0)
    # Minimised unscaled: the request's own coefficients and text.
    minimal = OptimizationRequest.of(_fixture("valid", "th_r1_minimal"))
    plain = request_formulation(
        minimal, DecisionMap(MappingProxyType({"SPEC-H-Q": "H.Q_spec"})), ((25000.0,),)
    )
    assert dict(plain.objective.linear) == {"H.Q_spec": 0.0001}
    assert plain.objective.text == "Q/1e4"


# -- G18: static readiness, ready and one test per reason ------------------------------------------


def test_static_readiness_on_th_r1_is_ready_with_the_mapped_formulation() -> None:
    found = static_readiness(_fixture("valid", "th_r1_minimal"), _th_r1(), solver_probe=_available)
    assert (found.problems, found.reasons, dict(found.not_run)) == ((), (), {})
    assert found.ready
    assert found.decisions is not None
    assert found.decisions.as_document() == {"SPEC-H-Q": "H.Q_spec"}
    assert found.starts == ((25000.0,),)
    assert found.formulation is not None
    assert found.formulation.decision_ids == ("H.Q_spec",)


def test_the_full_fixture_is_ready_on_th_r1() -> None:
    found = static_readiness(_fixture("valid", "th_r1_full"), _th_r1(), solver_probe=_available)
    assert found.reasons == () and found.ready
    assert found.starts is not None and len(found.starts) == 4
    assert found.starts[0] == (25000.0, 300.0)


def _split_fraction_revision() -> dict[str, Any]:
    from test_opt_revision_host import _split_fraction_as_specification

    document: dict[str, Any] = _split_fraction_as_specification()
    return document


Edit = Callable[[dict[str, Any]], None]


def _decision(**members: Any) -> Edit:
    """Edit the one decision; a new specification id is renamed in the objective too."""

    def edit(request: dict[str, Any]) -> None:
        request["decisions"][0].update(members)
        if "specification_id" in members:
            linear = request["objective"]["expression"]["linear"]
            linear[f"decision:{members['specification_id']}"] = linear.pop("decision:SPEC-H-Q")

    return edit


def _starts(**members: Any) -> Edit:
    return lambda request: request.update(starts=members)


def _objective(linear: dict[str, float]) -> Edit:
    return lambda request: request["objective"]["expression"].update(linear=linear)


#: Code → (request edit, revision, expected subjects). Each case fails that code alone.
REASONS: dict[str, tuple[Edit, Callable[[], dict[str, Any]], tuple[str | None, ...]]] = {
    "REVISION_MISMATCH": (lambda r: r.update(revision_sha256="0" * 64), _th_r1, (None,)),
    "REVISION_UNBOUND": (lambda r: None, CORPUS["SYN-001-T06-STR02"], (None,)),
    "OPTIMIZATION_ROUTE_UNAVAILABLE": (lambda r: None, CORPUS[A02_FILES[0]], ("legacy_eo",)),
    "UNKNOWN_DECISION": (_decision(specification_id="SPEC-NOPE"), _th_r1, ("SPEC-NOPE",)),
    "DECISION_UNIT_NOT_INTERNAL": (
        _decision(lower=20.0, upper=30.0, unit="kW"),
        _th_r1,
        ("SPEC-H-Q",),
    ),
    "DECISION_NOT_CONTINUOUS": (
        _decision(specification_id="SPEC-SP-r", lower=0.5, upper=1.5, scale=1.0, unit="1"),
        _split_fraction_revision,
        ("SPEC-SP-r",),
    ),
    "BOUNDS_UNDECLARED": (_decision(lower=30000.0, upper=20000.0), _th_r1, ("SPEC-H-Q",)),
    "START_OUTSIDE_BOUNDS": (_decision(lower=26000.0), _th_r1, ("SPEC-H-Q",)),
    "TOO_MANY_STARTS": (_starts(include_revision=True, halton=32), _th_r1, (None,)),
    "UNKNOWN_VARIABLE": (
        _objective({"S99.T": 1.0, "decision:SPEC-V-P": 1.0}),
        _th_r1,
        ("S99.T", "decision:SPEC-V-P"),
    ),
    "ASSESSMENT_OUTPUT_UNKNOWN": (_objective({"assessment:tac": 1.0}), _th_r1, ("tac",)),
    "HESSIAN_UNAVAILABLE": (lambda r: r.update(hessian="exact"), _th_r1, (None,)),
}


@pytest.mark.parametrize("code", sorted(REASONS))
def test_g18_each_static_reason_alone(code: str) -> None:
    edit, revision, subjects = REASONS[code]
    request = _fixture("valid", "th_r1_minimal")
    edit(request)
    found = static_readiness(request, revision(), solver_probe=_available)
    assert found.problems == ()
    assert found.codes == (code,), found.reasons
    assert tuple(sorted(r.subject or "" for r in found.reasons)) == tuple(
        sorted(s or "" for s in subjects)
    )
    assert not found.ready and found.formulation is None


def test_g18_nlp_solver_unavailable_is_a_reason_and_the_rest_still_runs() -> None:
    found = static_readiness(
        _fixture("valid", "th_r1_minimal"), _th_r1(), solver_probe=lambda: UNAVAILABLE
    )
    assert found.codes == ("NLP_SOLVER_UNAVAILABLE",)
    assert found.reasons[0].detail == UNAVAILABLE.detail
    assert found.decisions is not None and not found.ready


def test_the_routes_other_than_revision_eo_are_refused() -> None:
    """A coupled revision binds on the revision binder; its route is `revision_coupled`."""
    document = json.loads((REPO / "benchmarks" / "m02" / "c1-loop-real.json").read_bytes())
    from openflowsheet.application.revision_run import select_route

    route = select_route(document)
    request = _fixture("valid", "th_r1_minimal")
    found = static_readiness(request, document, solver_probe=_available)
    if getattr(route, "solve_path", None) != "revision_coupled":
        pytest.skip(f"c1-loop-real does not route revision_coupled here ({route!r:.80})")
    assert "OPTIMIZATION_ROUTE_UNAVAILABLE" in found.codes
    assert "UNKNOWN_DECISION" in found.not_run


def test_zero_starts_is_too_many_starts_and_reasons_keep_the_table_order() -> None:
    request = _fixture("valid", "th_r1_minimal")
    request["starts"] = {"include_revision": False}
    request["hessian"] = "exact"
    request["decisions"][0]["unit"] = "kW"
    found = static_readiness(request, _th_r1(), solver_probe=_available)
    assert found.codes == ("DECISION_UNIT_NOT_INTERNAL", "TOO_MANY_STARTS", "HESSIAN_UNAVAILABLE")
    assert "0 starts" in found.reasons[1].detail


def test_an_ill_formed_request_runs_no_other_check() -> None:
    found = static_readiness(_fixture("invalid", "zero_scale"), _th_r1(), solver_probe=_available)
    assert found.problems and found.reasons == ()
    assert set(found.not_run) == set(STATIC_CODES) - {"NLP_SOLVER_UNAVAILABLE"}


# -- validate(task="optimization") ---------------------------------------------------------------


def test_validate_ready_for_optimization_lists_every_static_check() -> None:
    report = validation.validate(
        _th_r1(),
        "optimization",
        optimization=_fixture("valid", "th_r1_minimal"),
        solver_probe=_available,
    )
    assert report.status == "READY_FOR_OPTIMIZATION"
    assert report.task == "optimization"
    opt = [check for check in report.checks if check.id.startswith("OPT.")]
    assert [check.id for check in opt] == ["OPT.REQUEST_SCHEMA"] + [
        f"OPT.{code}" for code in STATIC_CODES
    ]
    assert {check.result for check in opt} == {"PASS"}
    stages = {check.id: check.stage for check in opt}
    assert stages["OPT.REQUEST_SCHEMA"] == "schema"
    assert stages["OPT.NLP_SOLVER_UNAVAILABLE"] == "capability"
    assert stages["OPT.OPTIMIZATION_ROUTE_UNAVAILABLE"] == "capability"
    assert stages["OPT.DECISION_NOT_CONTINUOUS"] == "structural_analysis"
    assert {check.evidence_class for check in opt} == {"structural"}
    document = report.as_document()
    assert schema_errors("validation-report.schema.json", document) == []
    simulation = validation.validate(_th_r1(), "simulation")
    assert simulation.status == "READY_FOR_SIMULATION"
    assert report.checks[: len(simulation.checks)] == simulation.checks


def test_validate_is_invalid_with_the_failing_check_and_its_subjects() -> None:
    request = _fixture("valid", "th_r1_minimal")
    _decision(specification_id="SPEC-NOPE")(request)
    report = validation.validate(
        _th_r1(), "optimization", optimization=request, solver_probe=_available
    )
    assert report.status == "INVALID"
    (failed,) = [check for check in report.checks if check.result == "FAIL"]
    assert (failed.id, failed.implicated_objects) == ("OPT.UNKNOWN_DECISION", ("SPEC-NOPE",))
    assert schema_errors("validation-report.schema.json", report.as_document()) == []


def test_validate_with_an_ill_formed_request_fails_its_schema_check() -> None:
    report = validation.validate(
        _th_r1(),
        "optimization",
        optimization=_fixture("invalid", "zero_scale"),
        solver_probe=_available,
    )
    assert report.status == "INVALID"
    by_id = {check.id: check for check in report.checks}
    assert by_id["OPT.REQUEST_SCHEMA"].result == "FAIL"
    assert by_id["OPT.REQUEST_SCHEMA"].message.startswith("request_invalid(/decisions/0/scale)")
    assert by_id["OPT.UNKNOWN_DECISION"].result == "NOT_RUN"
    assert by_id["OPT.NLP_SOLVER_UNAVAILABLE"].result == "PASS"


def test_validate_of_a_draft_revision_is_draft_and_runs_no_static_check() -> None:
    document = _th_r1()
    document["specifications"] = [s for s in document["specifications"] if s["id"] != "SPEC-H-Q"]
    simulation = validation.validate(document, "simulation")
    assert simulation.status == "DRAFT"
    report = validation.validate(
        document,
        "optimization",
        optimization=_fixture("valid", "th_r1_minimal"),
        solver_probe=_available,
    )
    assert report.status == "DRAFT"
    opt = {check.id: check.result for check in report.checks if check.id.startswith("OPT.")}
    assert opt.pop("OPT.REQUEST_SCHEMA") == "PASS"
    assert set(opt.values()) == {"NOT_RUN"}


def test_validate_without_a_request_is_invalid_request_at_optimization() -> None:
    with pytest.raises(ApplicationError) as refused:
        validation.validate(_th_r1(), "optimization", solver_probe=_available)
    assert refused.value.error.code == "invalid_request"
    assert refused.value.error.detail == {"pointer": "/optimization"}


# -- G11: the platform and the default install ---------------------------------------------------


def test_g11_an_unaudited_platform_is_unavailable_naming_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # the extra absent: M03's detail, byte for byte, on any platform (OPT review M6)
    with monkeypatch.context() as absent:
        absent.setattr(closure, "NLP_LIBRARIES", ("openflowsheet_no_such_library",))
        solver = audited_solver("linux-aarch64")
        assert not solver.available
        assert solver.detail == audited_solver("linux-x86_64").detail
        assert "platform" not in solver.detail
    # the extra present on an unaudited platform: unavailable, naming the platform
    with monkeypatch.context() as present:
        present.setattr(closure, "NLP_LIBRARIES", ())
        solver = audited_solver("linux-aarch64")
        assert not solver.available
        assert "the platform linux-aarch64 is not audited" in solver.detail
        assert "platform" not in audited_solver("linux-x86_64").detail
    monkeypatch.setattr(closure, "running_platform", lambda: "darwin-arm64")
    with pytest.raises(ApplicationError) as refused:
        validation.validate(
            _th_r1(), "optimization", optimization=_fixture("valid", "th_r1_minimal")
        )
    assert refused.value.error.as_document() == {
        "code": "unsupported",
        "message": "nlp_solver_unavailable",
        "detail": {"pointer": "/task"},
        "retryable": False,
    }


def test_g11_the_application_refuses_before_reading_and_wants_the_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With an audited solver the application's `validate` reads its `optimization` member
    (ADR 0019 Amendment 16, WO-6): missing, `invalid_request` at `/optimization`, audited,
    nothing read; given, the static readiness's report. Without a solver: `unsupported
    nlp_solver_unavailable`, before the request is looked at."""
    from openflowsheet.application.operations import OPERATIONS
    from openflowsheet.application.types import Change, Edit

    with LocalApplication.create(tmp_path / "project", project_id="opt-wo3") as app:
        edits = tuple(Edit("set", (key,), value) for key, value in _th_r1().items())
        revision_id = app.commit_change(Change(edits=edits), None, "seed").revision_id
        assert revision_id is not None
        monkeypatch.setattr(closure, "audited_solver", _available)
        with pytest.raises(ApplicationError) as wanted:
            app.validate(revision_id, "optimization")
        assert (wanted.value.error.code, wanted.value.error.detail) == (
            "invalid_request",
            {"pointer": "/optimization"},
        )
        request = _fixture("valid", "th_r1_minimal")
        report = app.validate(revision_id, "optimization", request)
        assert report.status == "READY_FOR_OPTIMIZATION"
        decoded = OPERATIONS["validate"].decode(
            {"revision_id": revision_id, "task": "optimization", "optimization": request}
        )
        assert app.validate(**decoded) == report
        assert "optimization" in OPERATIONS["validate"].request_schema["properties"]
        assert "optimization" not in OPERATIONS["validate"].request_schema["required"]
        monkeypatch.setattr(closure, "audited_solver", lambda: UNAVAILABLE)
        monkeypatch.setattr(closure, "running_platform", lambda: "linux-aarch64")
        with pytest.raises(ApplicationError) as refused:
            app.validate(revision_id, "optimization", request)
        assert refused.value.error.message == "nlp_solver_unavailable"
        rows = [row for row in app.store.audit_rows() if row["outcome"] == "refused"]
        assert [(row["operation"], row["code"]) for row in rows] == [
            ("validate", "invalid_request"),
            ("validate", "unsupported"),
        ]


_NO_NLP_IMPORT = """
import json, sys
sys.path.insert(0, sys.argv[1])
from openflowsheet.application import validation
from openflowsheet.application.contract import ApplicationError
from openflowsheet.studies.nlp.closure import SolverAvailability
from openflowsheet.studies.nlp.request import static_readiness
revision = json.loads(open(sys.argv[2], "rb").read())
request = json.loads(open(sys.argv[3], "rb").read())
try:
    validation.validate(revision, "optimization", optimization=request)
    real = "report"
except ApplicationError as error:
    real = error.error.message
ready = validation.validate(
    revision, "optimization", optimization=request,
    solver_probe=lambda: SolverAvailability(True, "double"),
).status
static = static_readiness(request, revision, solver_probe=lambda: SolverAvailability(True, "d"))
print(json.dumps({"real": real, "ready": ready, "static": static.ready,
                  "loaded": sorted(m for m in ("pyomo", "cyipopt") if m in sys.modules)}))
"""


def test_g11_validate_and_static_readiness_never_import_pyomo_or_cyipopt() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _NO_NLP_IMPORT,
            str(REPO / "src"),
            str(S11 / "thermal" / "TH-R1.json"),
            str(FIXTURES / "valid" / "th_r1_minimal.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    found = json.loads(result.stdout.strip().splitlines()[-1])
    assert found["loaded"] == []
    assert (found["ready"], found["static"]) == ("READY_FOR_OPTIMIZATION", True)
    if not audited_solver().available:
        assert found["real"] == "nlp_solver_unavailable"


def test_reason_codes_keep_m03s_relative_order() -> None:
    m03 = [
        "UNKNOWN_DECISION",
        "BOUNDS_UNDECLARED",
        "START_OUTSIDE_BOUNDS",
        "DECISION_INCONSISTENT_WITH_ELIMINATED_ROWS",
        "UNKNOWN_VARIABLE",
        "ASSESSMENT_OUTPUT_UNKNOWN",
        "ASSESSMENT_OUTPUT_UNAVAILABLE",
        "ASSESSMENT_PARAMETER_STRUCTURAL",
        "ASSESSMENT_PARAMETER_DECISION",
        "HESSIAN_UNAVAILABLE",
        "SIMULATION_NOT_READY",
        "ASSESSMENT_REGIME_INADMISSIBLE",
        "ASSESSMENT_OBJECTIVE_UNSCALED",
        "NLP_SOLVER_UNAVAILABLE",
    ]
    assert [code for code in closure.READINESS_ORDER if code in m03] == m03
    assert [code for code in closure.READINESS_ORDER if code in STATIC_CODES] == list(STATIC_CODES)
