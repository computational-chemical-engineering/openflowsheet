"""Generate the M03 round-trip fixtures from real study runs. Register R-015; spec §10 (WO-9).

Every valid fixture is a document a real run emits — a sensitivity at a registered SYN-001 state,
the registered sweep, the two registered fits, `optimize()` in the default environment, the V1-V6
verifier at NLP-1's reference optimum — never one written by hand: a hand-made document tests the
author's reading of the schema, an emitted one tests the code (K03's rule). One invalid fixture per
`$def` and per schema is a valid one with its first required member removed, `{expect_error,
document}` (the `application-results` precedent, `scripts/t07_schema_fixtures.py`).

`optimization-report.schema.json#/$defs/start` has no fixture yet: a start record is what the
gray-box adapter (WO-8) writes for one Ipopt run, and no default-environment run produces one.
`tests/test_m03_schemas.py` names that gap rather than filling it with a constructed record.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/m03_schema_fixtures.py [--write]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import numpy as np  # noqa: E402
from m03_support import (  # noqa: E402
    estimation_problem,
    flowsheet,
    linear_spec,
    nlp_formulation,
    number,
    pressure_parameters,
    reference,
    registered_outputs,
    registered_parameters,
    solved,
    syn001_host,
    toy_host,
    toy_parameter,
)

from openflowsheet.studies.estimation import estimate  # noqa: E402
from openflowsheet.studies.nlp.closure import optimization_readiness, optimize  # noqa: E402
from openflowsheet.studies.nlp.verification import verify_candidate  # noqa: E402
from openflowsheet.studies.sensitivity import (  # noqa: E402
    OutputFunctional,
    SensitivityRequest,
    evaluate_sensitivity,
)
from openflowsheet.studies.study import (  # noqa: E402
    estimation_study,
    sensitivity_study,
    sweep_study,
)
from openflowsheet.studies.sweep import SweepSensitivity, run_sweep  # noqa: E402
from openflowsheet.studies.syn001 import syn001_sensitivity  # noqa: E402
from openflowsheet.verify.certificate import verify  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"
STUDY_SCHEMA = "study.schema.json"
REPORT_SCHEMA = "optimization-report.schema.json"
#: The `$def`s with no real producer yet, and why (module docstring).
PENDING_DEFS = {REPORT_SCHEMA: {"start": "written by the gray-box adapter (WO-8) only"}}


def sensitivity_documents() -> dict[str, Any]:
    """Four real sensitivity results: qualified, partially qualified, refused at a phase boundary,
    and refused because the residual cannot be evaluated (A43's state); and the study of the
    first."""

    def at(state: str, mode: str, parameters: Any) -> Any:
        sheet, result = solved(state)
        return syn001_sensitivity(
            sheet,
            result,
            parameters=parameters,
            outputs=registered_outputs(),
            mode=mode,  # type: ignore[arg-type]
            certificate=verify(sheet, result),
        )

    qualified = at("P1", "both", registered_parameters())
    partial = at("P1", "adjoint", registered_parameters() + pressure_parameters())
    boundary = at("B1", "forward", registered_parameters())
    host, tear, x = syn001_host("P1")
    moved = x.copy()
    moved[tear.spec.variable_ids.index("S2.T")] = 500.0
    unevaluable = evaluate_sensitivity(
        host,
        moved,
        SensitivityRequest(tear.context, registered_parameters(), registered_outputs(), "both"),
    )
    # A45's host: the linear toy with one row eliminated, a non-square reduced system.
    toy, context = toy_host(linear_spec(1.0))
    nonsquare = evaluate_sensitivity(
        dataclasses.replace(toy, eliminated_rows=("R2",)),
        np.array([1.0, 0.0]),
        SensitivityRequest(
            context,
            (toy_parameter("p1"), toy_parameter("p2")),
            (OutputFunctional("C", {"x1": 1.0, "x2": 10.0}, 1.0),),
            "both",
        ),
    )
    expected = {
        "p1_both_qualified": (qualified, "QUALIFIED"),
        "p1_adjoint_pressures_partially_qualified": (partial, "PARTIALLY_QUALIFIED"),
        "b1_forward_phase_boundary": (boundary, "REFUSED"),
        "p1_s2t_500k_root_not_converged": (unevaluable, "REFUSED"),
        "linear_toy_nonsquare_unsupported_rank_structure": (nonsquare, "REFUSED"),
    }
    documents: dict[str, Any] = {}
    for name, (result, status) in expected.items():
        if result.status != status:
            raise SystemExit(f"{name}: expected {status}, the run gave {result.status}")
        documents[f"sensitivity_result/{name}"] = result.as_document()
    documents["study_parameter/u_split_split_fraction"] = qualified.parameters[0].as_document()
    del documents["study_parameter/u_split_split_fraction"]["status"]
    del documents["study_parameter/u_split_split_fraction"]["alias_residual"]
    q_total = next(output for output in qualified.outputs if output.output_id == "Q_total")
    documents["output_functional/q_total"] = {
        "output_id": q_total.output_id,
        "coefficients": dict(q_total.coefficients),
        "scale": q_total.scale,
    }
    documents["study/sensitivity_p1_both"] = sensitivity_study("M03-P1-both", qualified)
    return documents


def sweep_documents() -> dict[str, Any]:
    """The registered sweep (spec §6), whole as a study and with a four-point budget as a
    `sweep_result`; a converged, a refused and an unrun point."""
    section = reference()["sweep"]
    parameter = section["parameter"]
    sheet = flowsheet({"U-SPLIT.split_fraction": section["split_fraction"]})
    values = tuple(number(point[parameter]) for point in section["points"])
    outputs = tuple(
        output for output in registered_outputs() if output.output_id in ("S4.N", "S5.N")
    )
    request = SweepSensitivity(
        parameters=tuple(p for p in registered_parameters() if p.parameter_id == parameter),
        outputs=outputs[:1],
    )
    full = run_sweep(sheet, parameter, values, outputs, sensitivity=request)
    budget = run_sweep(sheet, parameter, values, outputs, sensitivity=request, max_points=4)
    if full.status != "COMPLETE" or budget.status != "INCOMPLETE":
        raise SystemExit(f"the sweeps ended {full.status} and {budget.status}")
    by_outcome = {point.outcome: point for point in full.points}
    return {
        "sweep_result/registered_budget_4_incomplete": budget.as_document(),
        "sweep_point/t_flash_355_converged": full.points[2].as_document(),
        "sweep_point/t_flash_445_specification_refused": (
            by_outcome["SPECIFICATION_REFUSED"].as_document()
        ),
        "sweep_point/t_flash_374_not_run": budget.points[5].as_document(),
        "study/sweep_registered": sweep_study("M03-sweep", sheet, full, max_points=None),
    }


def estimation_documents() -> dict[str, Any]:
    """The two registered fits (spec §7): identifiable and unidentifiable."""
    reports = {fit_id: estimate(estimation_problem(fit_id)) for fit_id in ("FIT-I", "FIT-U")}
    for fit_id, status in (("FIT-I", "IDENTIFIABLE"), ("FIT-U", "UNIDENTIFIABLE")):
        if reports[fit_id].status != status:
            raise SystemExit(f"{fit_id} ended {reports[fit_id].status}")
    return {
        "estimation_report/fit_i_identifiable": reports["FIT-I"].as_document(),
        "estimation_report/fit_u_unidentifiable": reports["FIT-U"].as_document(),
        "study/estimation_fit_u": estimation_study("M03-FIT-U", reports["FIT-U"]),
    }


def optimization_documents() -> dict[str, Any]:
    """`optimize()` without the audited extra (A34), with the limited-memory and with the refused
    exact Hessian; and the verifier's candidate at NLP-1's reference optimum, given the re-solved
    state as the optimizer's (V1-V5 pass, A32 as amended)."""
    sheet = flowsheet({})
    unsupported = optimize(nlp_formulation(), sheet)
    exact = optimize(nlp_formulation(hessian="exact"), sheet)
    for report, codes in (
        (unsupported, ("NLP_SOLVER_UNAVAILABLE",)),
        (exact, ("HESSIAN_UNAVAILABLE", "NLP_SOLVER_UNAVAILABLE")),
    ):
        if report.status != "UNSUPPORTED" or report.reason_codes != codes:
            raise SystemExit(f"optimize ended {report.status} {report.reason_codes}")
    formulation = nlp_formulation()
    regimes = optimization_readiness(formulation, sheet).declared_regimes
    if regimes is None:
        raise SystemExit("NLP-1's starts declare no regimes")
    optimum = reference()["nlp"]["NLP-1"]["reference_optimum"]
    decisions = tuple(number(optimum[d.parameter_id]) for d in formulation.decisions)
    resolved = verify_candidate(sheet, formulation, decisions, regimes=regimes)
    if resolved.simulation_state is None:
        raise SystemExit("the reference optimum did not re-solve")
    candidate = verify_candidate(
        sheet, formulation, decisions, regimes=regimes, optimizer_state=resolved.simulation_state
    )
    if not candidate.passed:
        raise SystemExit(f"the reference optimum failed {candidate.failures}")
    document = unsupported.as_document()
    return {
        "optimization_report/nlp_1_without_the_extra": document,
        "optimization_report/nlp_1_exact_hessian": exact.as_document(),
        "reason/nlp_solver_unavailable": document["reasons"][0],
        "candidate/nlp_1_reference_optimum": candidate.as_document(),
        "check/v5_reference_optimum": candidate.as_document()["checks"][4],
    }


def _valid(schema: str, documents: dict[str, Any]) -> dict[str, Any]:
    """`<dir>/valid/<name>.json` for the schema's own documents, `<dir>/<def>/valid/<name>.json`
    for a `$def`'s, and for each the first required member removed under `invalid/`."""
    directory = schema.removesuffix(".schema.json").replace("-", "_")
    loaded = json.loads((ROOT / "schemas" / schema).read_text(encoding="utf-8"))
    top = directory
    out: dict[str, Any] = {}
    first: dict[str, Any] = {}
    for key, document in documents.items():
        kind, name = key.split("/")
        where = directory if kind == top else f"{directory}/{kind}"
        out[f"{where}/valid/{name}.json"] = document
        first.setdefault(kind, document)
    for kind, document in first.items():
        where = directory if kind == top else f"{directory}/{kind}"
        definition = loaded if kind == top else loaded["$defs"][kind]
        member = definition["required"][0]
        out[f"{where}/invalid/missing_{member}.json"] = {
            "expect_error": f"'{member}' is a required property",
            "document": {key: value for key, value in document.items() if key != member},
        }
    return out


def documents() -> dict[str, Any]:
    """Every M03 fixture, keyed by its path under `tests/fixtures/schemas/`."""
    study = {**sensitivity_documents(), **sweep_documents(), **estimation_documents()}
    return {
        **_valid(STUDY_SCHEMA, study),
        **_valid(REPORT_SCHEMA, optimization_documents()),
    }


def serialize(document: Any) -> str:
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    differing = []
    for name, document in documents().items():
        path = FIXTURE_DIR / name
        text = serialize(document)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            differing.append(name)
            if arguments.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if not differing:
        print("all M03 fixtures match what the code emits")
        return 0
    print(
        f"{'rewrote' if arguments.write else 'differ (rerun with --write)'}: {', '.join(differing)}"
    )
    return 0 if arguments.write else 1


if __name__ == "__main__":
    raise SystemExit(main())
