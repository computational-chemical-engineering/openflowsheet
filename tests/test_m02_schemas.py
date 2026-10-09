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

import re
import sys
from collections.abc import Iterator
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json, load_yaml
from jsonschema import Draft202012Validator
from m02_schema_support import without_m02
from m04_schema_support import without_m04

from openflowsheet.application.types import SCHEMA_BASE, published_schemas, schema_errors

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


# -- G1 (a): the fixtures -------------------------------------------------------------------------

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas"


def _fixture_module() -> Any:
    import m02_schema_fixtures

    return m02_schema_fixtures


@pytest.mark.parametrize("directory", sorted(_fixture_module().REFERENCES))
def test_g1a_every_def_has_a_valid_and_an_invalid_fixture(directory: str) -> None:
    reference = _fixture_module().REFERENCES[directory]
    valid = sorted((FIXTURES / directory / "valid").glob("*.json"))
    invalid = sorted((FIXTURES / directory / "invalid").glob("*.json"))
    assert valid and invalid, directory
    for path in valid:
        assert schema_errors(reference, load_json(path)) == [], path
    for path in invalid:
        fixture = load_json(path)
        assert set(fixture) == {"expect_error", "document"}, path
        errors = schema_errors(reference, fixture["document"])
        assert any(fixture["expect_error"] in error for error in errors), (path, errors)


def test_g1a_the_fixtures_are_what_the_code_emits_today() -> None:
    module = _fixture_module()
    for name, document in module.documents().items():
        assert module.stable(load_json(FIXTURES / name)) == module.stable(document), name


#: The addendum's rules table of each fixture directory.
RULES_OF = {
    "model_variant": "model_variant",
    "experiment_request": "request",
    "experiment_result": "result",
    "experiment_attempt": "attempt",
    "experiment_body": "experiment_body",
}


def _floats(node: Any, path: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _floats(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _floats(value, f"{path}[{index}]")
    elif isinstance(node, float):
        yield path


@pytest.mark.parametrize("directory", sorted(RULES_OF))
def test_g1_a32_every_float_of_every_m02_fixture_is_classified(directory: str) -> None:
    """ADR 0007 D2.3 for M02's floats: each one matches a rule of the addendum."""
    rules = [
        (re.compile(rule["path"]), rule["class"]) for rule in EXTERNAL["rules"][RULES_OF[directory]]
    ]
    found = 0
    for path in sorted((FIXTURES / directory / "valid").glob("*.json")):
        for where in _floats(load_json(path)):
            found += 1
            classes = [cls for pattern, cls in rules if pattern.fullmatch(where)]
            assert classes, f"{path.name}: {where} is unclassified"
    assert found > 0, directory


# -- G1 (c): R4-G3's method -----------------------------------------------------------------------


def test_g1c_without_m02s_additions_every_response_is_its_pre_m02_snapshot() -> None:
    """Every operation's fully resolved response schema, with M02's enum values, `experiment`
    branches and members and widened descriptions removed, equals its snapshot before M02."""
    import test_t07_w5e_application_results as r4

    from openflowsheet.application.operations import OPERATIONS

    # The base is `main`'s at M02's merge of it: M06's Amendment 3 (R-192) included.
    before = {**r4.SNAPSHOT_AT_B13D556, **r4.SNAPSHOT_AMENDMENT_2, **r4.SNAPSHOT_AMENDMENT_3}
    moved = []
    for name, operation in OPERATIONS.items():
        # M04's additions (ADR 0037 D6) are taken out first: they postdate this snapshot.
        resolved = without_m04(r4.resolved_response(operation))
        assert r4._digest(without_m02(resolved)) == before[name], name
        if r4._digest(resolved) != before[name]:
            moved.append(name)
    assert sorted(moved) == sorted(r4.SNAPSHOT_M02)
