"""M02 G1 (design note §3.6, §10.1): the schemas M02 adds, and the classification of their numbers.

- The three new files are draft 2020-12 schemas published under the project's base, by `$id`.
- `benchmarks/m02/numerical_policy_external.yaml` (ADR 0007 D2.3 for M02's floats) names exactly
  those three files, classifies every `$def` that carries floats, and uses only its own four
  classes; T08's closed partition of `sha256` names holds over them and refuses an unclassified or
  a re-classified name.

The fixtures of each `$def` — one valid, emitted by a real run, and one invalid with a required
member removed — and A32's rule applied to them arrive with the work orders that emit them.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json, load_yaml
from jsonschema import Draft202012Validator

from openflowsheet.application.types import SCHEMA_BASE, published_schemas

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import t08_numerical_policy  # noqa: E402

M02_SCHEMAS = (
    "experiment.schema.json",
    "model-replacement.schema.json",
    "model-variant.schema.json",
)
EXTERNAL: dict[str, Any] = load_yaml(
    REPO_ROOT / "benchmarks" / "m02" / "numerical_policy_external.yaml"
)["numerical_policy_external"]
CLASSES = {"exact", "r3_recorded_external", "r1_r2_existing_floors", "excluded"}


@pytest.mark.parametrize("name", M02_SCHEMAS)
def test_g1_each_new_schema_is_published_by_its_id(name: str) -> None:
    document = load_json(REPO_ROOT / "schemas" / name)
    Draft202012Validator.check_schema(document)
    assert document["$id"] == SCHEMA_BASE + name
    assert published_schemas()[document["$id"]] == document


def test_g1_the_addendum_covers_exactly_m02s_schemas_with_its_four_classes() -> None:
    assert tuple(EXTERNAL["schemas"]) == M02_SCHEMAS
    assert set(EXTERNAL["classes"]) == CLASSES
    experiment = load_json(REPO_ROOT / "schemas" / "experiment.schema.json")
    float_defs = {"request", "result", "attempt", "coupling", "experiment_body"}
    assert float_defs <= set(experiment["$defs"])
    assert set(EXTERNAL["rules"]) == float_defs | {"model_variant", "model_replacement"}
    for rules in EXTERNAL["rules"].values():
        assert all(rule["class"] in CLASSES for rule in rules)


def test_g1_the_sha256_partition_holds_over_m02s_schemas() -> None:
    policy = load_yaml(REPO_ROOT / "benchmarks" / "t08" / "numerical_policy_v2.yaml")[
        "numerical_policy"
    ]
    assert t08_numerical_policy.external_audit(policy, EXTERNAL) == []
    declared = t08_numerical_policy.schema_sha256_names(external=True)
    assert set(EXTERNAL["exact_sha256"]) <= declared
    # The v2 partition is computed without M02's files, so v2's content does not move.
    assert not set(EXTERNAL["exact_sha256"]) & t08_numerical_policy.schema_sha256_names()


def test_g1_the_partition_refuses_an_unclassified_and_a_reclassified_name() -> None:
    policy = load_yaml(REPO_ROOT / "benchmarks" / "t08" / "numerical_policy_v2.yaml")[
        "numerical_policy"
    ]
    missing = {**EXTERNAL, "exact_sha256": EXTERNAL["exact_sha256"][1:]}
    (problem,) = t08_numerical_policy.external_audit(policy, missing)
    assert problem.startswith("(m02) unclassified sha256 names")
    doubled = {**EXTERNAL, "exact_sha256": [*EXTERNAL["exact_sha256"], "request_sha256"]}
    problems = t08_numerical_policy.external_audit(policy, doubled)
    assert any(entry.startswith("(m02) already classified by v2") for entry in problems)
