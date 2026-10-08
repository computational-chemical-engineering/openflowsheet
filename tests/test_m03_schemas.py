"""M03 WO-9: the study and optimization-report schemas (spec §10; ADR 0031 D7, ADR 0032 D6).

- **The schemas.** `schemas/study.schema.json` (`$defs` `study_parameter`, `output_functional`,
  `sensitivity_result`, `sweep_point`, `sweep_result`, `estimation_report`; the `study` document)
  and `schemas/optimization-report.schema.json` (`$defs` `reason`, `check`, `candidate`, `start`;
  the report), draft 2020-12, under the published `$id` base.
- **Fixtures (R-015).** One valid fixture per `$def` and per schema at least, each emitted by a
  real run (`scripts/m03_schema_fixtures.py`), and one invalid fixture each, a valid one with its
  first required member removed. The start records and the solved reports are the gray-box
  adapter's (WO-8), emitted by real Ipopt runs in the audited environment
  (`m03_schema_fixtures.NLP_FIXTURES`): the default gate validates them and checks their rules, and
  `tests/test_m03_nlp_greybox.py` (marked `nlp`) checks that they are what the adapter emits today.
- **Rules a JSON Schema cannot express** (spec §10), checked on every valid fixture and on every
  sensitivity result nested in one: a refused column's values are `null`; `status` agrees with
  `refusals`; a `determined: false` parameter carries no standard error; `KKT_POINT_VERIFIED`
  requires V1-V5 recorded as passed — and (Amendment 1) every start's classification and the
  report's status follow from the records by `classify_starts`.
- **Amendment 1 in the schemas.** Every sensitivity result records Q2′ in its place, a real
  `LINEAR_SOLVE_FAILED` refusal (A44's fault injection) validates, and a start record carries its
  `classification`.
"""

from __future__ import annotations

import copy
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator

from openflowsheet.application.types import SCHEMA_BASE, schema_errors
from openflowsheet.studies import sensitivity as sensitivity_module
from openflowsheet.studies.nlp.closure import StartEvidence, classify_starts
from openflowsheet.studies.nlp.verification import CHECKS
from openflowsheet.studies.sensitivity import QUALIFICATIONS

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m03_schema_fixtures  # noqa: E402

STUDY = "study.schema.json"
REPORT = "optimization-report.schema.json"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas"
DEFS = {
    STUDY: {
        "study_parameter",
        "output_functional",
        "sensitivity_result",
        "sweep_point",
        "sweep_result",
        "estimation_report",
    },
    REPORT: {"reason", "check", "candidate", "start"},
}
#: `$def`s whose first real producer is a later work order (module docstring): none since WO-8.
PENDING: dict[str, set[str]] = {}


def directory(schema: str) -> Path:
    return FIXTURES / schema.removesuffix(".schema.json").replace("-", "_")


def fixtures(schema: str, name: str | None, validity: str) -> list[Path]:
    """The fixtures of the schema itself (`name` None) or of one `$def`."""
    base = directory(schema) if name is None else directory(schema) / name
    return sorted((base / validity).glob("*.json"))


def reference(schema: str, name: str | None) -> str:
    return schema if name is None else f"{schema}#/$defs/{name}"


# -- the schemas ----------------------------------------------------------------------------------


@pytest.mark.parametrize("schema", [STUDY, REPORT])
def test_the_schema_is_draft_2020_12_with_its_id_and_a_description(schema: str) -> None:
    document = load_json(REPO_ROOT / "schemas" / schema)
    Draft202012Validator.check_schema(document)
    assert document["$id"] == SCHEMA_BASE + schema
    assert len(document["description"]) > 80
    assert set(document["$defs"]) == DEFS[schema]


@pytest.mark.parametrize(
    ("schema", "name"),
    [(schema, None) for schema in DEFS]
    + [(schema, name) for schema, names in DEFS.items() for name in sorted(names)],
    ids=lambda value: str(value),
)
def test_every_def_has_a_valid_and_an_invalid_fixture_emitted_by_a_real_run(
    schema: str, name: str | None
) -> None:
    valid, invalid = fixtures(schema, name, "valid"), fixtures(schema, name, "invalid")
    if name in PENDING.get(schema, set()):
        assert valid == invalid == [], f"{name} has fixtures now: take it off PENDING"
        assert name in m03_schema_fixtures.PENDING_DEFS[schema]
        return
    assert valid and invalid, (schema, name)
    for path in valid:
        assert schema_errors(reference(schema, name), load_json(path)) == [], path
    for path in invalid:
        fixture = load_json(path)
        assert set(fixture) == {"expect_error", "document"}, path
        errors = schema_errors(reference(schema, name), fixture["document"])
        assert any(fixture["expect_error"] in error for error in errors), (path, errors)


def test_the_fixtures_are_what_real_runs_emit_today() -> None:
    """R-015: regenerated, every fixture is byte-identical — sensitivities, sweeps, fits and the
    verifier are bitwise reproducible on one platform (spec §3.7). The audited environment's
    fixtures are regenerated there (`test_m03_nlp_greybox.py`); here they need only exist."""
    emitted = m03_schema_fixtures.documents()
    committed = sorted(
        str(path.relative_to(FIXTURES))
        for schema in DEFS
        for path in directory(schema).rglob("*.json")
    )
    nlp = sorted(m03_schema_fixtures.NLP_FIXTURES)
    assert set(nlp) <= set(committed)
    assert not set(nlp) & set(emitted)
    assert sorted(emitted) == sorted(set(committed) - set(nlp))
    for name, document in emitted.items():
        assert (FIXTURES / name).read_text(encoding="utf-8") == m03_schema_fixtures.serialize(
            document
        ), name


# -- the rules a JSON Schema cannot express -------------------------------------------------------


def sensitivity_results(document: Any) -> Iterator[dict[str, Any]]:
    """Every `sensitivity_result` inside a document (a study, a sweep or a point, or itself)."""
    if isinstance(document, dict):
        if document.get("policy_id") == "M03-sensitivity-v1":
            yield document
            return
        for value in document.values():
            yield from sensitivity_results(value)
    elif isinstance(document, list):
        for value in document:
            yield from sensitivity_results(value)


def sensitivity_violations(result: dict[str, Any]) -> list[str]:
    """Spec §3.5 and §3.7: `status` agrees with `refusals`, and refused columns are `null`."""
    found: list[str] = []
    order = {name: index for index, name in enumerate(QUALIFICATIONS)}
    refusals = result["refusals"]
    positions = [order[refusal["qualification"]] for refusal in refusals]
    if positions != sorted(positions):
        found.append("refusals are not in the specification's table order")
    request = [r for r in refusals if r["scope"] == "request"]
    refused_columns = {r["parameter_id"] for r in refusals if r["scope"] == "column"}
    columns = [column["parameter_id"] for column in result["parameters"]]
    if any(r["parameter_id"] not in columns for r in refusals if r["scope"] == "column"):
        found.append("a column refusal names no requested parameter")
    qualified = [not request and name not in refused_columns for name in columns]
    expected = (
        "REFUSED"
        if not any(qualified)
        else "QUALIFIED"
        if all(qualified)
        else "PARTIALLY_QUALIFIED"
    )
    if result["status"] != expected:
        found.append(f"status {result['status']} but the refusals say {expected}")
    for column, ok in zip(result["parameters"], qualified, strict=True):
        if column["status"] != ("QUALIFIED" if ok else "REFUSED"):
            found.append(f"column {column['parameter_id']} is {column['status']}")
    for mode in ("forward", "adjoint"):
        block = result[mode]
        if block is None:
            continue
        for matrix in (block["scaled"], block["unscaled"]):
            for row in matrix:
                for value, ok in zip(row, qualified, strict=True):
                    if (value is None) == ok:
                        found.append(
                            f"{mode}: a {'qualified' if ok else 'refused'} column has "
                            f"{'no value' if ok else 'a value'}"
                        )
    return found


def estimation_violations(report: dict[str, Any]) -> list[str]:
    """Spec §7.4: an undetermined parameter carries no estimate and no standard error."""
    return [
        f"{item['id']} is undetermined but carries a value"
        for item in report.get("parameters", [])
        if item["determined"] is False
        and (item["standard_error"] is not None or item["estimate"] is not None)
    ]


def report_violations(report: dict[str, Any]) -> list[str]:
    """Spec §8.5 (Amendment 1): `KKT_POINT_VERIFIED` requires V1-V5 recorded as passed, and every
    start's classification and the report's status follow from the records."""
    found: list[str] = []

    def outcomes(checks: list[dict[str, Any]]) -> dict[str, Any]:
        return {item["check"]: item["outcome"] for item in checks}

    if report["status"] == "KKT_POINT_VERIFIED":
        candidate = report["candidate"]
        if candidate is None or any(
            outcomes(candidate["checks"]).get(check) != "pass" for check in CHECKS[:5]
        ):
            found.append("KKT_POINT_VERIFIED without V1-V5 recorded as passed")
    starts = report["starts"]
    if report["status"] == "UNSUPPORTED":
        return found
    if not starts:
        return [*found, "a solved report without starts"]
    verdict = classify_starts(
        [StartEvidence(start["ipopt_status"], outcomes(start["checks"])) for start in starts]
    )
    for index, (start, classification) in enumerate(
        zip(starts, verdict.classifications, strict=True)
    ):
        if start["classification"] != classification:
            found.append(f"start {index} says {start['classification']}, the rule {classification}")
    if report["status"] != verdict.status:
        found.append(f"status {report['status']}, the starts say {verdict.status}")
    if [(r["code"], r["subject"]) for r in report["reasons"]] != [
        (r.code, r.subject) for r in verdict.reasons
    ]:
        found.append("the reasons are not one per start not verified, in start order")
    return found


def valid_documents() -> Iterator[tuple[Path, Any]]:
    for schema in DEFS:
        for path in sorted(directory(schema).rglob("valid/*.json")):
            yield path, load_json(path)


def test_the_non_schema_rules_hold_on_every_valid_fixture() -> None:
    checked = {"sensitivity": 0, "estimation": 0, "report": 0}
    for path, document in valid_documents():
        for result in sensitivity_results(document):
            assert sensitivity_violations(result) == [], path
            checked["sensitivity"] += 1
        for report in [document, document.get("result")]:
            if isinstance(report, dict) and "covariance_basis" in report:
                assert estimation_violations(report) == [], path
                checked["estimation"] += 1
        if document.get("schema_version") == "optimization-report-v1":
            assert report_violations(document) == [], path
            checked["report"] += 1
    # Five results of their own, the P1 study's, the registered sweep's eight converged points,
    # the four-point budget sweep's four and the converged point's own.
    assert checked["sensitivity"] == 5 + 1 + 8 + 4 + 1
    assert checked["estimation"] == 3
    # Two `UNSUPPORTED` reports of the default environment, NLP-1 and NLP-INF solved (WO-8).
    assert checked["report"] == 4


def qualified_fixture() -> dict[str, Any]:
    path = directory(STUDY) / "sensitivity_result" / "valid" / "p1_both_qualified.json"
    document: dict[str, Any] = load_json(path)
    return document


def test_the_sensitivity_rules_catch_what_they_exist_for() -> None:
    zeroed = qualified_fixture()
    zeroed["status"] = "REFUSED"
    zeroed["refusals"] = [
        {
            "code": "PHASE_BOUNDARY",
            "scope": "request",
            "qualification": "Q4",
            "detail": "a refusal whose numbers were kept",
            "parameter_id": None,
        }
    ]
    for column in zeroed["parameters"]:
        column["status"] = "REFUSED"
    # The schema accepts this document; only the rule sees the published numbers.
    assert schema_errors(f"{STUDY}#/$defs/sensitivity_result", zeroed) == []
    assert any("refused column has a value" in v for v in sensitivity_violations(zeroed))

    mislabelled = qualified_fixture()
    mislabelled["status"] = "PARTIALLY_QUALIFIED"
    assert any("the refusals say QUALIFIED" in v for v in sensitivity_violations(mislabelled))


def test_the_estimation_rule_catches_a_standard_error_on_an_undetermined_parameter() -> None:
    path = directory(STUDY) / "estimation_report" / "valid" / "fit_u_unidentifiable.json"
    report = load_json(path)
    (split,) = [item for item in report["parameters"] if not item["determined"]]
    split["standard_error"] = 1e-3
    assert estimation_violations(report) == [f"{split['id']} is undetermined but carries a value"]
    # The schema states the same rule for the parameter record, so it rejects it too.
    assert schema_errors(f"{STUDY}#/$defs/estimation_report", report) != []


def start_record(
    ipopt_status: int | None, checks: list[dict[str, Any]], classification: str
) -> Any:
    """A start record in the `start` shape, for testing the rule and the schema (not a fixture)."""
    return {
        "start": {"U-SPLIT.split_fraction": 0.6, "U-FLASH.T_spec": 360.0},
        "ipopt_status": ipopt_status,
        "ipopt_message": None,
        "iterations": 12,
        "evaluations": {
            "residual_calls": 13,
            "jacobian_calls": 13,
            "property_calls": 0,
            "evaluation_errors": 0,
        },
        "wall_time_s": 0.5,
        "final_decisions": {"U-SPLIT.split_fraction": 0.89, "U-FLASH.T_spec": 361.5},
        "ipopt_final": {
            "primal_infeasibility": 1e-12,
            "dual_infeasibility": 1e-9,
            "complementarity": 1e-11,
        },
        "checks": checks,
        "classification": classification,
    }


def report_with_starts(*starts: Any, status: str) -> dict[str, Any]:
    """The real `UNSUPPORTED` report with synthetic starts, a status and per-start reasons."""
    path = directory(REPORT) / "valid" / "nlp_1_without_the_extra.json"
    report: dict[str, Any] = load_json(path)
    candidate = load_json(
        directory(REPORT) / "candidate" / "valid" / "nlp_1_reference_optimum.json"
    )
    report["starts"] = list(starts)
    report["status"] = status
    report["candidate"] = candidate if status == "KKT_POINT_VERIFIED" else None
    report["claims"]["local_stationarity"] = status == "KKT_POINT_VERIFIED"
    report["distinct_local_solutions"] = int(status == "KKT_POINT_VERIFIED")
    report["reasons"] = [
        {"code": start["classification"], "detail": "-", "subject": f"start {index}"}
        for index, start in enumerate(starts)
        if start["classification"] != "KKT_POINT_VERIFIED"
    ]
    return report


def test_a_start_record_carries_its_classification_and_the_report_rule_holds() -> None:
    candidate = load_json(
        directory(REPORT) / "candidate" / "valid" / "nlp_1_reference_optimum.json"
    )
    passed = candidate["checks"]
    refuted = copy.deepcopy(passed)
    refuted[4]["outcome"] = "fail"
    verified = start_record(0, passed, "KKT_POINT_VERIFIED")
    claimed = start_record(0, refuted, "NOT_VERIFIED")
    assert schema_errors(f"{REPORT}#/$defs/start", verified) == []
    unclassified = {key: value for key, value in verified.items() if key != "classification"}
    assert any(
        "'classification' is a required property" in error
        for error in schema_errors(f"{REPORT}#/$defs/start", unclassified)
    )

    # A47 case j as a document: a verified candidate beside a refuted claim.
    good = report_with_starts(verified, claimed, status="KKT_POINT_VERIFIED")
    assert schema_errors(REPORT, good) == []
    assert report_violations(good) == []

    # The schema cannot see that a start's classification contradicts its own record; the rule can.
    wrong = report_with_starts(
        start_record(0, refuted, "KKT_POINT_VERIFIED"), status="KKT_POINT_VERIFIED"
    )
    assert schema_errors(REPORT, wrong) == []
    assert "start 0 says KKT_POINT_VERIFIED, the rule NOT_VERIFIED" in report_violations(wrong)

    # Case e: Ipopt's infeasibility verdict does not mask a refuted claim.
    masked = report_with_starts(
        start_record(2, refuted, "INFEASIBLE_REPORTED"),
        claimed,
        status="INFEASIBLE_REPORTED",
    )
    assert schema_errors(REPORT, masked) == []
    assert "status INFEASIBLE_REPORTED, the starts say NOT_VERIFIED" in report_violations(masked)


def test_kkt_point_verified_without_v1_to_v5_passed_is_caught() -> None:
    candidate = load_json(
        directory(REPORT) / "candidate" / "valid" / "nlp_1_reference_optimum.json"
    )
    without_v2 = copy.deepcopy(candidate["checks"])
    without_v2[1] = {"check": "V2", "outcome": "not_evaluated", "reason": "no optimizer state"}
    report = report_with_starts(
        start_record(0, candidate["checks"], "KKT_POINT_VERIFIED"), status="KKT_POINT_VERIFIED"
    )
    report["candidate"]["checks"] = without_v2
    assert schema_errors(REPORT, report) == []
    assert "KKT_POINT_VERIFIED without V1-V5 recorded as passed" in report_violations(report)
    # And the schema refuses a candidate beside any other status.
    claimed = report_with_starts(start_record(0, without_v2, "NOT_VERIFIED"), status="NOT_VERIFIED")
    assert schema_errors(REPORT, claimed) == []
    claimed["candidate"] = candidate
    assert schema_errors(REPORT, claimed) != []


# -- Amendment 1 in the sensitivity schema --------------------------------------------------------


def test_every_sensitivity_result_records_q2_prime_in_its_place() -> None:
    for path, document in valid_documents():
        for result in sensitivity_results(document):
            names = [item["qualification"] for item in result["qualification"]["outcomes"]]
            assert names == list(QUALIFICATIONS), path
            assert names[6] == "Q2'"
    without = qualified_fixture()
    del without["qualification"]["outcomes"][6]
    assert schema_errors(f"{STUDY}#/$defs/sensitivity_result", without) != []


def test_a_linear_solve_failed_refusal_from_a_real_run_validates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A44's fault injection at P1 (the forward solve fails ADR 0004 D3 after a clean screen):
    the result document is a valid `sensitivity_result` carrying `LINEAR_SOLVE_FAILED`."""
    from test_m03_sensitivity_core import failing_solve, p1_sensitivity

    monkeypatch.setattr(sensitivity_module, "solve_linear_kept", failing_solve)
    document = p1_sensitivity("both").as_document()
    assert [refusal["code"] for refusal in document["refusals"]] == ["LINEAR_SOLVE_FAILED"]
    assert schema_errors(f"{STUDY}#/$defs/sensitivity_result", document) == []
    assert sensitivity_violations(document) == []
    q2_prime = document["qualification"]["outcomes"][6]
    assert (q2_prime["outcome"], q2_prime["reason"]) == ("fail", "residual")
    # A failed Q2′ without its reason is refused by the schema.
    del q2_prime["reason"]
    assert schema_errors(f"{STUDY}#/$defs/sensitivity_result", document) != []
