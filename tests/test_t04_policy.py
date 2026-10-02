"""T04 A01: `SolvePolicy.globalization` (ADR 0010 D1).

Every policy document carries the one `globalization` object with the registered constants of T04
§4.3 and §7.7, which are compared here against `benchmarks/t04/reference_values.yaml` (the design
lane's generator), never against this code's own defaults. The schema refuses a policy without the
object or with any single-valued field changed — that refusal is the replay refusal (ADR 0005 D1's
precedent: a replay under a policy that does not declare its rules is refused before it runs).
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from openflowsheet.orchestrator.trace import (
    GlobalizationPolicy,
    HomotopyPolicy,
    PtcPolicy,
    SolvePolicy,
    fraction_string,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "schemas" / "solve_policy" / "valid"
FIXTURE = FIXTURE / "syn001_k03.json"


@pytest.fixture(scope="module")
def ref() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "benchmarks" / "t04" / "reference_values.yaml").read_text()
    )
    return loaded


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads((REPO_ROOT / "schemas" / "solve-policy.schema.json").read_text())
    return Draft202012Validator(schema)


def document() -> dict[str, Any]:
    return SolvePolicy(policy_id="T04", residual_tolerances={}, scales={}).as_document()


def test_a01_the_default_policy_carries_the_registered_constants(ref: dict[str, Any]) -> None:
    globalization = document()["globalization"]
    assert globalization["policy_id"] == "T04-globalization-v1"
    assert globalization["eo_core"] == "newton"
    assert globalization["eo_recovery"] == "homotopy"
    assert globalization["eo_recovery_max_count"] == 1

    registered = ref["constants"]["homotopy"]
    homotopy = globalization["homotopy"]
    assert homotopy["type"] == registered["type"] == "specification_continuation"
    for name in ("delta_lambda_initial", "delta_lambda_min", "shrink"):
        # Exact fractions on both sides: the YAML writes `1/4`, the document `"1/4"`.
        assert homotopy[name] == str(registered[name]), name
        assert Fraction(homotopy[name]) == Fraction(str(registered[name])), name
    for name in ("growth", "corrector_max_iterations", "max_lambda_trials"):
        assert homotopy[name] == registered[name], name

    registered_ptc = ref["constants"]["ptc"]
    ptc = globalization["ptc"]
    assert ptc["status"] == "experimental"
    assert ptc["mass_policy"] == registered_ptc["mass_policy"]
    assert ptc["polish"] == "one_newton_step"
    for name in (
        "residence_time_s",
        "tau_initial_s",
        "tau_min_s",
        "tau_max_s",
        "gamma_min",
        "gamma_max",
        "phi_floor",
        "retry_shrink",
    ):
        # The YAML prints these to three significant figures; each registered value is exact
        # at that precision (1, 1e-4, 1e10, 0.2, 2, 1e-12, 0.5).
        assert ptc[name] == float(registered_ptc[name]), name
    for name in ("retries_max", "max_steps_per_attempt"):
        assert ptc[name] == registered_ptc[name], name


def test_a01_the_lambda_constants_are_exact_fractions() -> None:
    policy = HomotopyPolicy()
    assert policy.delta_lambda_initial == Fraction(1, 4)
    assert policy.delta_lambda_min == Fraction(1, 1024)
    assert policy.shrink == Fraction(1, 2)
    assert fraction_string(Fraction(0)) == "0"
    assert fraction_string(Fraction(1)) == "1"
    assert fraction_string(Fraction(909, 1024)) == "909/1024"


def test_a01_the_policy_and_its_fixture_validate(validator: Draft202012Validator) -> None:
    assert not list(validator.iter_errors(document()))
    fixture = json.loads(FIXTURE.read_text())
    assert not list(validator.iter_errors(fixture))
    assert fixture["globalization"] == document()["globalization"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("policy_id",), "T04-globalization-v2"),
        (("eo_recovery_max_count",), 2),
        (("eo_recovery",), "ptc"),
        (("eo_core",), "anderson"),
        (("homotopy", "type"), "global_newton"),
        (("homotopy", "delta_lambda_initial"), 0.25),
        (("ptc", "status"), "qualified"),
        (("ptc", "mass_policy"), "T04-residence-time-v2"),
        (("ptc", "polish"), "none"),
    ],
)
def test_a01_the_schema_refuses_a_changed_single_valued_field(
    validator: Draft202012Validator, path: tuple[str, ...], value: Any
) -> None:
    changed = document()
    target = changed["globalization"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert list(validator.iter_errors(changed)), path


def test_a01_a_policy_without_globalization_is_refused(validator: Draft202012Validator) -> None:
    """The replay refusal: a recorded policy that does not declare the globalization rules is
    not a valid `SolvePolicy`, so no replay can run under it (ADR 0010 D1)."""
    without = {key: value for key, value in document().items() if key != "globalization"}
    errors = list(validator.iter_errors(without))
    assert errors and "'globalization' is a required property" in errors[0].message


def test_a01_an_override_is_a_new_value_in_the_document(validator: Draft202012Validator) -> None:
    """A28's overrides (`max_lambda_trials = 4`, `max_steps_per_attempt = 5`) and the pinned
    `eo_recovery: none` of T04 §11.2 are recorded values, and still valid policies."""
    policy = SolvePolicy(
        policy_id="T04",
        residual_tolerances={},
        scales={},
        globalization=GlobalizationPolicy(
            eo_recovery="none",
            homotopy=HomotopyPolicy(max_lambda_trials=4),
            ptc=PtcPolicy(max_steps_per_attempt=5),
        ),
    )
    changed = policy.as_document()
    assert changed["globalization"]["eo_recovery"] == "none"
    assert changed["globalization"]["homotopy"]["max_lambda_trials"] == 4
    assert changed["globalization"]["ptc"]["max_steps_per_attempt"] == 5
    assert not list(validator.iter_errors(changed))
