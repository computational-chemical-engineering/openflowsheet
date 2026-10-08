"""The `study` document (M03 spec §10; ADR 0031 D7): one study, its request and its result.

`schemas/study.schema.json` describes `{schema_version: "study-v1", study_id, kind, model,
parameters, outputs, request, result}`, with `kind` one of `sensitivity`, `sweep`, `estimation`
and `result` that kind's record (`sensitivity_result`, `sweep_result`, `estimation_report`).
`model` is the base problem's identity — for a sweep and a fit, the flowsheet before any pinned
input is moved, since every point or iterate moves one. `request` is what the study was asked
beyond its parameters and outputs: a sensitivity's mode and state; a sweep's input, values, start
and point budget; a fit's id, start and pinned estimator settings.

A study document is assembled from a finished result and adds no number of its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, Literal

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.studies.estimation import EstimationReport
from openflowsheet.studies.sensitivity import OutputFunctional, SensitivityResult, StudyParameter
from openflowsheet.studies.sweep import SweepResult

SCHEMA_VERSION: Final = "study-v1"
StudyKind = Literal["sensitivity", "sweep", "estimation"]


def sensitivity_study(study_id: str, result: SensitivityResult) -> dict[str, Any]:
    """A sensitivity request and its result, at the state the result names."""
    return _study(
        study_id,
        "sensitivity",
        {"model_version": result.model_version, "constants_sha256": result.constants_sha256},
        [column.parameter_id for column in result.parameters],
        [
            {"parameter_id": c.parameter_id, "scale": c.scale, "domain": [c.lower, c.upper]}
            for c in result.parameters
        ],
        result.outputs,
        {"mode": result.mode, "state_sha256": result.state_sha256},
        result.as_document(),
    )


def sweep_study(
    study_id: str,
    flowsheet: Syn001Flowsheet,
    result: SweepResult,
    *,
    max_points: int | None,
) -> dict[str, Any]:
    """A sweep of `flowsheet` and its result; `max_points` is the budget `run_sweep` was given."""
    parameters = result.sensitivity.parameters if result.sensitivity is not None else ()
    return _study(
        study_id,
        "sweep",
        _model(flowsheet),
        [parameter.parameter_id for parameter in parameters],
        [_parameter(parameter) for parameter in parameters],
        result.outputs,
        {
            "parameter_id": result.parameter_id,
            "values": list(result.values),
            "start": result.start,
            "max_points": max_points,
        },
        result.as_document(),
    )


def estimation_study(study_id: str, report: EstimationReport) -> dict[str, Any]:
    """A fit and its report; the outputs are the fitted measurements and the held-out ones."""
    problem = report.problem
    return _study(
        study_id,
        "estimation",
        _model(problem.flowsheet),
        [parameter.parameter_id for parameter in problem.parameters],
        [_parameter(parameter) for parameter in problem.parameters],
        tuple(item.output for item in problem.measurements + problem.validation),
        {
            "fit_id": problem.fit_id,
            "start": list(problem.start),
            "estimator": dict(report.estimator),
        },
        report.as_document(),
    )


def _study(
    study_id: str,
    kind: StudyKind,
    model: dict[str, Any],
    parameter_ids: Sequence[str],
    parameters: list[dict[str, Any]],
    outputs: Sequence[OutputFunctional],
    request: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    if len(set(parameter_ids)) != len(parameter_ids):
        raise ValueError(f"parameter ids repeat: {list(parameter_ids)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "study_id": study_id,
        "kind": kind,
        "model": model,
        "parameters": parameters,
        "outputs": [_output(output) for output in outputs],
        "request": request,
        "result": result,
    }


def _model(flowsheet: Syn001Flowsheet) -> dict[str, Any]:
    metadata = compile_problem(flowsheet.spec()).metadata
    return {"model_version": metadata.model_version, "constants_sha256": metadata.constants_sha256}


def _parameter(parameter: StudyParameter) -> dict[str, Any]:
    return {
        "parameter_id": parameter.parameter_id,
        "scale": parameter.scale,
        "domain": [parameter.lower, parameter.upper],
    }


def _output(output: OutputFunctional) -> dict[str, Any]:
    return {
        "output_id": output.output_id,
        "coefficients": dict(output.coefficients),
        "scale": output.scale,
    }
