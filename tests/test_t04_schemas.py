"""T04 W9: records, schemas, fixtures and taxonomy (T04 §10; ADR 0010 D7, D8). A26, A27.

The T04 fixtures (`t04_*.json` beside K03's and K04's) are emitted by
`scripts/t04_schema_fixtures.py` from real plan runs of registered cases (R-015): HOM-01's bound
certificate, HOM-04's stall checkpoint and bundle, HOM-05's recovery trace and homotopy attempt,
and the nominal region under PTC. Here they are validated against their schemas, compared with
what the code emits today under the reproducibility rule of `tests/reproducibility.py`
(`run.compare.differences`), and read for the fields ADR 0010 D7 adds. A27's bundles are built by
`verify.failure.region_bundle` from the registered stalls and refusal.

A26's cross-architecture clause (R0 fields byte-identical on x86-64 and aarch64, and
`scripts/k05_structural_identity.py` including them) is W11's, not this file's.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import load_json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.run.compare import differences
from openflowsheet.verify.failure import ACTIONS, OUTCOME_ACTIONS, TAXONOMY, region_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "schemas"
SCHEMAS = {
    "solve_policy": "solve-policy.schema.json",
    "solve_event": "solve-event.schema.json",
    "attempt_context": "attempt-context.schema.json",
    "checkpoint": "checkpoint.schema.json",
    "solution_certificate": "solution-certificate.schema.json",
    "failure_bundle": "failure-bundle.schema.json",
}
REGISTRY = Registry().with_resources(
    (document["$id"], Resource(contents=document, specification=DRAFT202012))
    for document in (load_json(path) for path in sorted(SCHEMA_DIR.glob("*.schema.json")))
)
#: T04 §4.6's registered vocabulary of inferred causes.
VOCABULARY = re.compile(
    r"^(phase_boundary_on_path\([A-Z0-9-]+\)|singular_path_or_fold|corrector_failure)$"
)


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_json(SCHEMA_DIR / SCHEMAS[name]), registry=REGISTRY)


def errors(name: str, document: Any) -> list[str]:
    return [
        f"{list(error.absolute_path)}: {error.message}"
        for error in validator(name).iter_errors(document)
    ]


def t04_fixtures() -> list[tuple[str, Path]]:
    return [
        (name, path)
        for name in sorted(SCHEMAS)
        for path in sorted((FIXTURE_DIR / name / "valid").glob("t04_*.json"))
    ]


@pytest.fixture(scope="module")
def emitted() -> dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t04_schema_fixtures import documents

    produced: dict[str, Any] = documents()
    return produced


@pytest.mark.parametrize(("name", "path"), t04_fixtures(), ids=lambda v: getattr(v, "stem", v))
def test_a26_the_t04_fixtures_validate_and_round_trip(name: str, path: Path) -> None:
    document = load_json(path)
    for entry in document if isinstance(document, list) else [document]:
        assert errors(name, entry) == [], f"{path.name}: {errors(name, entry)}"
    assert json.loads(json.dumps(document)) == document


def test_a26_the_t04_fixtures_are_what_the_code_emits_today(emitted: dict[str, Any]) -> None:
    """Generated, not written (R-015): the committed files are the generator's, one for one, and
    equal under the reproducibility rule to what a live run emits now."""
    from t04_schema_fixtures import FIXTURE_NAMES

    committed = {str(path.relative_to(FIXTURE_DIR)) for _, path in t04_fixtures()}
    assert set(emitted) == committed == set(FIXTURE_NAMES)
    for name, document in emitted.items():
        found = differences(
            document, load_json(FIXTURE_DIR / name), policy_id="K04-numerical-policy-v1"
        )
        assert not found, (
            f"{name} is not what the code emits:\n  "
            + "\n  ".join(found)
            + "\nIf intended, regenerate with `python scripts/t04_schema_fixtures.py --write`."
        )


def test_a26_every_new_field_is_exercised_by_a_fixture() -> None:
    """ADR 0010 D7's fields, each present in a fixture a real run emitted — so the schema has had
    to accept a real value of every one — and no event serializes a non-finite number."""
    events = [
        event
        for trace in ("t04_hom05_recovery_trace", "t04_ptc_nominal_region_trace")
        for event in load_json(FIXTURE_DIR / "solve_event" / "valid" / f"{trace}.json")
    ]
    for event in events:
        json.dumps(event, allow_nan=False)
    kinds = {event["kind"] for event in events}
    assert "homotopy_step" in kinds
    present = set().union(*(event.keys() for event in events))
    assert {
        "lambda_value",
        "delta_lambda",
        "corrector_outcome",
        "corrector_iterations",
        "level_constants_sha256",
        "homotopy_level",
        "eo_recovery",
        "pseudo_step",
        "pseudo_step_next",
        "ser_ratio",
    } <= present
    assert {e.get("rejection_reason") for e in events} >= {"bound_blocked"}
    assert any(e["message"] == "polish" for e in events)

    homotopy = load_json(FIXTURE_DIR / "attempt_context" / "valid" / "t04_hom05_homotopy.json")
    ptc = load_json(FIXTURE_DIR / "attempt_context" / "valid" / "t04_ptc_restart.json")
    assert (homotopy["core"], ptc["core"]) == ("homotopy", "ptc")
    assert homotopy["continuation"]["parameter_ids"] == ["SPEC:SPEC-flash-duty"]
    assert ptc["continuation"] is None

    stall = load_json(FIXTURE_DIR / "checkpoint" / "valid" / "t04_hom04_stall.json")
    assert (stall["continuation_lambda"], stall["label"]) == ("909/1024", "partial")

    certificate = load_json(
        FIXTURE_DIR / "solution_certificate" / "valid" / "t04_hom01_bound_verified.json"
    )
    items = certificate["branch_provenance"]
    assert [item["core"] for item in items] == ["newton", "newton", "homotopy"]
    assert items[2]["opening_source"] == "eo_recovery_start"
    assert items[2]["continuation"]["lambda_levels"] == ["1/4", "3/4", "1"]
    assert all(item["continuation"] is None for item in items[:2])
    policy = load_json(FIXTURE_DIR / "solve_policy" / "valid" / "t04_ptc.json")
    assert policy["globalization"]["eo_core"] == "ptc"


def test_a26_the_schema_refuses_a_lambda_below_one_that_claims_more() -> None:
    """ADR 0010 D7.4, schema-enforced: a checkpoint at λ < 1 is `partial` and `unverified`."""
    stall = load_json(FIXTURE_DIR / "checkpoint" / "valid" / "t04_hom04_stall.json")
    assert errors("checkpoint", stall) == []
    for field, value in (("label", "candidate_root"), ("verification_scope", "checked_partial")):
        assert errors("checkpoint", {**stall, field: value}), field
    assert (
        errors("checkpoint", {**stall, "continuation_lambda": "1", "label": "candidate_root"}) == []
    )


# ------------------------------------------------------------------ A27: the taxonomy


def test_a27_the_three_outcomes_map_to_adr_0010_d8() -> None:
    expected = {
        "HOMOTOPY_STALLED": ("homotopy/PTC/active-set stalls", "supply_initial_guess"),
        "PTC_STALLED": ("homotopy/PTC/active-set stalls", "supply_initial_guess"),
        "PTC_MAPPING_INVALID": ("model domain/conservation/derivative defects", "report_defect"),
    }
    for outcome, (taxonomy, action) in expected.items():
        assert TAXONOMY[outcome] == taxonomy
        assert OUTCOME_ACTIONS.get(outcome, ACTIONS[taxonomy]) == action


def stalled(case_id: str) -> Any:
    from test_t04_edge3 import full_run, region_step

    run = full_run(case_id)
    step = region_step(run.result)
    assert step.outcome == "HOMOTOPY_STALLED"
    return region_bundle(step.detail, run.result.trace, step_index=step.index)


@pytest.mark.parametrize(
    ("case_id", "cause"),
    [("HOM-03", "phase_boundary_on_path(U-HEAT)"), ("HOM-04", "phase_boundary_on_path(U-HEAT)")],
)
def test_a27_a_homotopy_stall_carries_exactly_one_registered_hypothesis(
    case_id: str, cause: str
) -> None:
    """ADR 0010 D8 / T04 §4.6: one inferred cause from the registered vocabulary, marked a
    hypothesis; class and action as D8; the bundle validates and claims no infeasibility."""
    bundle = stalled(case_id).as_document()
    assert errors("failure_bundle", bundle) == []
    (inferred,) = bundle["inferred_causes"]
    assert VOCABULARY.match(inferred["cause"]) and inferred["cause"] == cause
    assert inferred["kind"] == "hypothesis"
    assert bundle["taxonomy"] == "homotopy/PTC/active-set stalls"
    assert [a["action"] for a in bundle["suggested_actions"]] == ["supply_initial_guess"]
    assert "infeasib" not in json.dumps(bundle).lower()


def test_a27_the_ptc_outcomes_bundle_with_their_class_and_infer_nothing() -> None:
    """PHS-05 under PTC (`PTC_STALLED`) and ADV-04's refused mapping (`PTC_MAPPING_INVALID`): the
    class and action of D8, no inferred cause, no claim of infeasibility."""
    from test_t04_ptc_region import HIGH, case, mixer_double, phs05, solve, start

    from openflowsheet.orchestrator.trace import Trace

    run = phs05()
    refused_trace = Trace()
    item = case(HIGH)
    refused = solve(item, start(item, "OFF-A"), trace=refused_trace, mapping=mixer_double())
    for result, trace, outcome, action in (
        (run.failed, run.trace, "PTC_STALLED", "supply_initial_guess"),
        (refused, refused_trace, "PTC_MAPPING_INVALID", "report_defect"),
    ):
        assert result.outcome == outcome
        bundle = region_bundle(result, trace, step_index=None).as_document()
        assert errors("failure_bundle", bundle) == []
        assert bundle["inferred_causes"] == []
        assert [a["action"] for a in bundle["suggested_actions"]] == [action]
        assert "infeasib" not in json.dumps(bundle).lower()
