"""E01 WO-B3: assessment outputs in studies (design §4.10.1, §4.10.4, §4.11, §9.1).

On TH-C1 (P1's Rankine units) with P4's document (cost, LCA on `test-background-v1`, derived):
- A30 (on TH-C1; I1 repeats it on the registered P1): `d tac/dp` and `d impact/dp` for the boiler
  outlet T and the pump outlet P via the wrapper, against central differences of re-solved states
  (step `1e-4·s_p`), rel ≤ 1e-5. The difference quotient evaluates the program at the re-solved
  state with the moved pin as a decision, so the direct term `∂G/∂p` is in it.
- A31: forward and adjoint agree, rel ≤ 1e-10.
- A32: with no assessment output nothing is linearized, and the result is bitwise the direct
  `evaluate_sensitivity`'s.
- A37: the trust-region hook refuses `UNSUPPORTED(ASSESSMENT_OUTPUT_IN_TRF)`.
- A38 (study schemas): every existing study and optimization-report fixture validates against the
  widened schemas; the two link objects validate through the `$ref`s.
"""

from __future__ import annotations

import copy
import json
import sys
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s11_thermal_support import committed_case, solve  # noqa: E402
from test_e01_a_report import _solved, registered  # noqa: E402, F401
from test_e01_b_lca import P4_DOC, RATE, _program  # noqa: E402

from openflowsheet.application.types import schema_errors  # noqa: E402
from openflowsheet.assessment.program import AssessmentProgram, Refusal  # noqa: E402
from openflowsheet.studies import assessment as study_assessment  # noqa: E402
from openflowsheet.studies.sensitivity import (  # noqa: E402
    OutputFunctional,
    SensitivityRequest,
    StudyParameter,
    evaluate_sensitivity,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "schemas"
#: A30's two pinned inputs, with their specification ids in TH-C1 and their scales `s_p`.
PINS = {"B.T_spec": ("SPEC-B-T", 673.15), "P.P_spec": ("SPEC-P-P", 3.0e6)}
OUTPUTS = ("tac", RATE)


def _request(context: Any, mode: str = "both") -> SensitivityRequest:
    return SensitivityRequest(
        context=context,
        parameters=tuple(
            StudyParameter(pin, scale, 0.5 * scale, 1.5 * scale) for pin, (_, scale) in PINS.items()
        ),
        outputs=(OutputFunctional.of_variable("S1.T", 300.0),),
        mode=mode,  # type: ignore[arg-type]
    )


@cache
def _base() -> tuple[AssessmentProgram, Any, np.ndarray, dict[str, float]]:
    program, state, _ = _program(copy.deepcopy(P4_DOC))
    binding, _, _ = _solved("TH-C1")
    host = study_assessment.revision_sensitivity_host(binding.flowsheet, state)
    x = np.array([state[name] for name in host.spec.variable_ids])
    return program, host, x, state


def _resolved(spec_id: str, value: float) -> dict[str, float]:
    document = copy.deepcopy(committed_case("TH-C1"))
    for spec in document["specifications"]:
        if spec["id"] == spec_id:
            spec["value"] = value
    _, run = solve(document)
    assert run.state is not None
    return dict(run.state)


def test_the_revision_host_is_the_bound_problem(registered: None) -> None:  # noqa: F811
    program, host, _, _ = _base()
    _, spec, _ = _solved("TH-C1")
    assert host.spec.variable_ids == spec.variable_ids
    assert host.spec.equation_ids == spec.equation_ids
    assert set(PINS) <= set(program.parameter_ids)


def test_a30_a31_tac_and_impact_sensitivities_match_resolved_differences(
    registered: None,  # noqa: F811
) -> None:
    program, host, x, _ = _base()
    context = study_assessment.evaluation_context(host.compiled)
    result = study_assessment.assessment_sensitivity(program, host, _request(context), x, OUTPUTS)
    assert result.refusals == ()
    assert result.base is not None and result.base.status == "QUALIFIED", result.base.refusals
    assert result.forward is not None and result.adjoint is not None
    assert dict(result.dependence) == dict.fromkeys(OUTPUTS, "STATE_DEPENDENT")
    for j, (pin, (spec_id, scale)) in enumerate(PINS.items()):
        step = 1e-4 * scale
        values = []
        for sign in (1.0, -1.0):
            moved = scale + sign * step
            evaluated = program.evaluate(_resolved(spec_id, moved), {pin: moved})
            assert not isinstance(evaluated, Refusal)
            values.append(evaluated)
        for i, output in enumerate(OUTPUTS):
            difference = (values[0][output] - values[1][output]) / (2.0 * step)
            forward = result.forward.unscaled[i][j]
            adjoint = result.adjoint.unscaled[i][j]
            assert forward is not None and adjoint is not None
            assert abs(forward - difference) <= 1e-5 * abs(difference), (output, pin)
            assert abs(forward - adjoint) <= 1e-10 * max(abs(forward), abs(adjoint))


def test_the_direct_term_is_added_once_to_the_host_rows(registered: None) -> None:  # noqa: F811
    """`dy/dp = ∇ₓG·X + ∂G/∂p`: the wrapper's value minus the host's functional row is the
    program's own `∂G/∂p`, bitwise."""
    program, host, x, state = _base()
    context = study_assessment.evaluation_context(host.compiled)
    result = study_assessment.assessment_sensitivity(
        program, host, _request(context, "forward"), x, OUTPUTS
    )
    assert result.base is not None and result.base.forward is not None
    assert result.forward is not None and result.adjoint is None
    lin = program.linearize(state, {}, list(OUTPUTS), list(PINS))
    assert not isinstance(lin, Refusal)
    for i, _ in enumerate(OUTPUTS):
        host_row = result.base.forward.unscaled[1 + i]
        for j, pin in enumerate(PINS):
            column = lin.d_dp.col_ids.index(pin)
            direct = {
                lin.d_dp.indices[k]: lin.d_dp.data[k]
                for k in range(lin.d_dp.indptr[column], lin.d_dp.indptr[column + 1])
            }.get(i, 0.0)
            assert host_row[j] is not None
            assert result.forward.unscaled[i][j] == host_row[j] + direct


def test_a32_no_assessment_output_is_the_direct_evaluation(registered: None) -> None:  # noqa: F811
    program, host, x, _ = _base()
    request = _request(study_assessment.evaluation_context(host.compiled))
    calls: list[Any] = []
    original = program.linearize

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return original(*args, **kwargs)

    program.linearize = spy  # type: ignore[method-assign]
    try:
        wrapped = study_assessment.assessment_sensitivity(program, host, request, x, ())
    finally:
        del program.linearize
    direct = evaluate_sensitivity(host, x, request)
    assert calls == []
    assert wrapped.base is not None
    assert json.dumps(wrapped.base.as_document(), sort_keys=True) == json.dumps(
        direct.as_document(), sort_keys=True
    )


def test_an_unavailable_output_is_refused_before_the_host_runs(
    registered: None,  # noqa: F811
) -> None:
    program, host, x, _ = _base()
    request = _request(study_assessment.evaluation_context(host.compiled))
    result = study_assessment.assessment_sensitivity(program, host, request, x, ("no.such",))
    assert result.base is None
    assert [r.code for r in result.refusals] == ["ASSESSMENT_OUTPUT_UNKNOWN"]


class _AtBoundary:
    """A test `cost` contributor on TH-C1: `size.TOY.area = S3.T` held at its `max` boundary
    (zero slack at x*), `size.FAR.area = S4.T` with half its range left (E01 review S2)."""

    name = "cost"

    def plan(self, ctx: Any, state: Any) -> Any:
        from openflowsheet.assessment.program import ContributionPlan, OutputDef
        from openflowsheet.assessment.regimes import AdmissibilityRow, RegimeEntry

        toy = OutputDef("size.TOY.area", "m2", lambda s, a: s.x("S3.T"))
        far = OutputDef("size.FAR.area", "m2", lambda s, a: s.x("S4.T"))
        at = ctx.evaluate(state, [toy, far])
        entries = tuple(
            RegimeEntry(
                f"{item}.size",
                "size",
                "units:1",
                "test",
                (
                    AdmissibilityRow(
                        "max",
                        lambda s, a, i=output.output_id, h=room * at[output.output_id]: (
                            h - s.out(i)
                        ),
                        room * at[output.output_id],
                    ),
                ),
            )
            for item, output, room in (("TOY", toy, 1.0), ("FAR", far, 2.0))
        )
        return ContributionPlan(outputs=(toy, far), regime_entries=entries)


def test_an_active_regime_boundary_is_listed_and_labels_the_outputs_it_bounds(
    registered: None,  # noqa: F811
) -> None:
    from openflowsheet.assessment.spec import load_assessment
    from openflowsheet.assessment.views import view_of

    _, host, x, state = _base()
    binding, spec, _ = _solved("TH-C1")
    program = AssessmentProgram.build(
        view_of(binding.flowsheet),
        spec,
        load_assessment(
            {
                "schema_version": "assessment-v1",
                "assessment_id": "e01-review-s2",
                "basis": {"currency": "USD", "year": 2024},
            }
        ),
        state,
        contributors=[_AtBoundary()],
    )
    assert isinstance(program, AssessmentProgram), program
    context = study_assessment.evaluation_context(host.compiled)
    outputs = ("size.TOY.area", "size.FAR.area")
    result = study_assessment.assessment_sensitivity(
        program, host, _request(context, "forward"), x, outputs
    )
    assert result.refusals == ()
    ((row, slack),) = result.regime_bounds_active
    assert row == "adm.TOY.size.max" and abs(slack) <= 1e-12
    assert [(lim.code, lim.target, dict(lim.detail)) for lim in result.limitations] == [
        ("REGIME_BOUNDARY_ACTIVE", "size.TOY.area", {"row": "adm.TOY.size.max"})
    ]
    toy_slack, far_slack = (result.regime_slack[name] for name in outputs)
    assert toy_slack is not None and abs(toy_slack) <= 1e-12
    assert far_slack == pytest.approx(0.5, rel=1e-12)
    document = result.as_document()
    assert document["regime_bounds_active"] == [{"id": row, "slack": slack}]
    assert document["limitations"] == [
        {"code": "REGIME_BOUNDARY_ACTIVE", "target": "size.TOY.area", "row": "adm.TOY.size.max"}
    ]
    # P4 at the same state has no active row: nothing listed, nothing labelled.
    p4, _, _, _ = _base()
    plain = study_assessment.assessment_sensitivity(
        p4, host, _request(context, "forward"), x, OUTPUTS
    )
    assert plain.regime_bounds_active == () and plain.limitations == ()


def test_a37_a_trust_region_objective_from_an_assessment_is_unsupported(
    registered: None,  # noqa: F811
) -> None:
    program, _, _, _ = _base()
    refusal = study_assessment.trf_objective_from_assessment(program, "tac")
    assert refusal == Refusal(
        "ASSESSMENT_OUTPUT_IN_TRF",
        "tac",
        "a trust-region objective naming an assessment output is not offered (design §7 Q1)",
        kind="unsupported",
    )


SHA = "0" * 63 + "1"


@pytest.mark.parametrize(
    ("schema", "directory"),
    [
        ("study.schema.json", "study"),
        ("optimization-report.schema.json", "optimization_report"),
    ],
)
def test_a38_existing_fixtures_validate_against_the_widened_schemas(
    schema: str, directory: str
) -> None:
    valid = sorted((FIXTURES / directory / "valid").glob("*.json"))
    invalid = sorted((FIXTURES / directory / "invalid").glob("*.json"))
    assert valid and invalid
    for path in valid:
        assert schema_errors(schema, json.loads(path.read_bytes())) == [], path.name
    for path in invalid:
        assert schema_errors(schema, json.loads(path.read_bytes())) != [], path.name


def test_a38_the_study_link_validates_through_its_ref() -> None:
    study = json.loads((FIXTURES / "study" / "valid" / "sensitivity_p1_both.json").read_bytes())
    linked = {**study, "assessment": {"assessment_id": "p1", "assessment_sha256": SHA}}
    assert schema_errors("study.schema.json", linked) == []
    held = {**linked, "assessment": {**linked["assessment"], "regime_sha256": SHA}}
    assert schema_errors("study.schema.json", held) == []
    for bad in (
        {"assessment_id": "p1"},
        {"assessment_id": "p1", "assessment_sha256": "XYZ"},
        {"assessment_id": "p1", "assessment_sha256": SHA, "extra": 1},
    ):
        assert schema_errors("study.schema.json", {**study, "assessment": bad}) != [], bad


def test_a38_the_formulation_link_validates_through_its_ref() -> None:
    report = json.loads(
        (FIXTURES / "optimization_report" / "valid" / "nlp_1_solved.json").read_bytes()
    )
    link = {
        "assessment_id": "p2",
        "assessment_sha256": SHA,
        "regime_sha256": SHA,
        "regime_entries": {"HX1.size_regime": "primary"},
        "outputs": [{"id": "tac", "scale": 1.0e5}],
        "admissibility": [{"id": "adm.HX1.size_regime.lo", "nominal": 10.0}],
        "regime_bounds_active": [],
    }
    linked = copy.deepcopy(report)
    linked["formulation"]["assessment"] = link
    assert schema_errors("optimization-report.schema.json", linked) == []
    broken = copy.deepcopy(linked)
    broken["formulation"]["assessment"]["outputs"][0]["scale"] = 0.0
    assert schema_errors("optimization-report.schema.json", broken) != []
