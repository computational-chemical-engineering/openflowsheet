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
    "experiment_coupling": "coupling",
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


# -- A32 over `experiment.schema.json` (register R-317 (b), M02 review F1) -------------------------

#: The coupling record's members a replay copies or serves rather than recomputes: compared
#: exactly, so their rules carry no `compare` (R-317 (a)).
COPIED = re.compile(
    r"\.(variants|frozen|coupling_block)\..*|.*\.units\.[^.]+\.(request|result|attempts)\b.*"
)
#: A rule's `compare`: how a replay compares a float the rerun recomputes.
COMPARES = {"relative", "shape"}


def _number_leaves(node: Any, path: str, definitions: dict[str, Any]) -> Iterator[str]:
    """Every `number` leaf a document of the schema `node` can carry, as a path the addendum's
    rules match (`[0]` for an array index, `u` for a key of a map)."""
    reference = node.get("$ref")
    if isinstance(reference, str):
        if reference.startswith("#/$defs/"):
            yield from _number_leaves(definitions[reference.split("/")[-1]], path, definitions)
        return  # another schema's document (a variant): copied, registered elsewhere
    types = node.get("type")
    if types == "number" or (isinstance(types, list) and "number" in types):
        yield path
    for branch in node.get("anyOf", []):
        yield from _number_leaves(branch, path, definitions)
    for key, child in node.get("properties", {}).items():
        yield from _number_leaves(child, f"{path}.{key}", definitions)
    if isinstance(node.get("additionalProperties"), dict):
        yield from _number_leaves(node["additionalProperties"], f"{path}.u", definitions)
    if isinstance(node.get("items"), dict):
        yield from _number_leaves(node["items"], f"{path}[0]", definitions)


def _rule_of(rules: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    return next((rule for rule in rules if re.fullmatch(rule["path"], path)), None)


def _a32_compare_is_well_formed(compare: Any) -> bool:
    from openflowsheet.run.compare import KIND_FLOOR

    if isinstance(compare, str):
        return compare in COMPARES
    if not isinstance(compare, dict) or len(compare) != 1:
        return False
    ((how, value),) = compare.items()
    return (
        (how == "floor" and isinstance(value, float) and value > 0.0)
        or (how == "block" and value in ("tau_xi_rel", "tau_T_K"))
        or (how == "kind" and value in KIND_FLOOR)
    )


def test_a32_every_number_of_the_coupling_record_and_the_envelope_is_classified() -> None:
    """ADR 0007 D2.3 over the schema, not only the fixtures: every `number` the coupling record
    (`$defs/coupling`) can carry matches an addendum rule, and every one a replay recomputes —
    outside the copied and served members — has a well-formed `compare`; so does every `number`
    of `$defs/envelope`, which an in-process variant's replay re-evaluates (R-317 (b))."""
    schema = load_json(REPO_ROOT / "schemas" / "experiment.schema.json")
    definitions = schema["$defs"]
    coupling_rules = EXTERNAL["rules"]["coupling"]
    recomputed: list[str] = []
    for path in _number_leaves(definitions["coupling"], "", definitions):
        rule = _rule_of(coupling_rules, path)
        assert rule is not None, f"{path} is unclassified"
        if COPIED.fullmatch(path):
            assert "compare" not in rule, f"{path} is copied, compared exactly"
            continue
        recomputed.append(path)
        assert _a32_compare_is_well_formed(rule.get("compare")), (path, rule)
    assert {"rho", "r_xi", "r_T", "du[0]", "B[0][0]", "w[0]"} <= {
        path.rsplit(".", 1)[-1] for path in recomputed
    }
    envelope = list(_number_leaves(definitions["envelope"], ".envelope", definitions))
    assert ".envelope.defect_rel" in envelope and ".envelope.outlet.n[0]" in envelope
    for path in envelope:
        rule = _rule_of(EXTERNAL["rules"]["result"], path)
        assert rule is not None and _a32_compare_is_well_formed(rule.get("compare")), path


def test_r317_the_registered_thresholds() -> None:
    """R-317 (b)'s table, as the addendum carries it."""
    coupling, result = EXTERNAL["rules"]["coupling"], EXTERNAL["rules"]["result"]
    unit = ".iterations[0].units.reactor"
    assert _rule_of(coupling, ".iterations[0].rho")["compare"] == {"floor": 1.0}
    assert _rule_of(coupling, f"{unit}.r_xi")["compare"] == {"block": "tau_xi_rel"}
    assert _rule_of(coupling, f"{unit}.r_T")["compare"] == {"block": "tau_T_K"}
    assert _rule_of(coupling, ".iterations[0].step.du[1]")["compare"] == "shape"
    assert _rule_of(coupling, ".iterations[0].step.B[1][0]")["compare"] == "shape"
    for flow in (f"{unit}.inlet.n[2]", f"{unit}.n_N2_in", f"{unit}.n_tot_in"):
        assert _rule_of(coupling, flow)["compare"] == {"kind": "molar_flow"}
    assert _rule_of(result, ".envelope.defect_rel")["compare"] == {"floor": 1e-6}
    for flow in (".envelope.defect[0]", ".envelope.outlet.n[4]"):
        assert _rule_of(result, flow)["compare"] == {"kind": "molar_flow"}


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
        resolved = r4.resolved_response(operation)
        assert r4._digest(without_m02(resolved)) == before[name], name
        if r4._digest(resolved) != before[name]:
            moved.append(name)
    assert sorted(moved) == sorted(r4.SNAPSHOT_M02)
