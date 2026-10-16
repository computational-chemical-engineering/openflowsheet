"""M04.A35 (WO-6): the two M04 schemas, their fixtures, and the replacement facet enum.

- `surrogate-manifest.schema.json` and `model-evidence.schema.json` are draft 2020-12 schemas
  published under the project's base, by `$id`, beside the others (this branch has no
  `schemas/registry.json`; the published set is `application.types.published_schemas()` and the
  packaged count, `tests/test_t08_w4_package_data.py`).
- One valid fixture each, emitted from M04.A19's run (and the `surrogate_study` body and answer from
  a stand-in job), and one invalid each with a required member removed
  (`scripts/m04_schema_fixtures.py`); the fixtures are what the code emits today, volatile members
  masked.
- `model-replacement.schema.json`'s facet enum contains `surrogate_evidence` (ADR 0037 D3).
- The M04 digest addendum names exactly the two schemas, and the closed partition of `sha256`
  names holds over them (ADR 0007 D2.3).
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json, load_yaml
from jsonschema import Draft202012Validator

from openflowsheet.application.types import SCHEMA_BASE, published_schemas, schema_errors
from openflowsheet.canonical import document_sha256
from openflowsheet.studies.surrogate.manifest import check_manifest

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m04_schema_fixtures  # noqa: E402
import t08_numerical_policy  # noqa: E402

M04_SCHEMAS = ("model-evidence.schema.json", "surrogate-manifest.schema.json")
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas"


@pytest.mark.parametrize("name", M04_SCHEMAS)
def test_a35_each_new_schema_is_published_by_its_id(name: str) -> None:
    document = load_json(REPO_ROOT / "schemas" / name)
    Draft202012Validator.check_schema(document)
    assert document["$id"] == SCHEMA_BASE + name
    assert published_schemas()[document["$id"]] == document


@pytest.mark.parametrize("directory", sorted(m04_schema_fixtures.REFERENCES))
def test_a35_every_document_has_a_valid_and_an_invalid_fixture(directory: str) -> None:
    reference = m04_schema_fixtures.REFERENCES[directory]
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


def test_a35_the_fixtures_are_what_the_code_emits_today() -> None:
    for name, document in m04_schema_fixtures.documents().items():
        stored = load_json(FIXTURES / name)
        assert m04_schema_fixtures.stable(stored) == m04_schema_fixtures.stable(document), name


def test_a35_the_manifest_fixture_is_a19s_and_passes_the_checker() -> None:
    manifest: dict[str, Any] = load_json(
        FIXTURES / "surrogate_manifest" / "valid" / "a19_smooth_prefix.json"
    )
    assert check_manifest(manifest) == []
    assert manifest["surrogate_id"] == "m04q7-m04-synthetic-smooth-v1-it1-prefix"
    assert manifest["promotion"]["verdict"] == "PROMOTABLE"
    assert abs(manifest["calibration"]["q_hat"] - 0.024916065269) <= 1e-10
    # M04.A38: the evidence fixture names this manifest; the manifest names no evidence.
    evidence = load_json(FIXTURES / "model_evidence" / "valid" / "a19_smooth_prefix.json")
    assert evidence["subject"]["artifact_ref"] == document_sha256(manifest)
    assert "evidence_sha256" not in manifest


def test_a35_the_replacement_facet_enum_contains_surrogate_evidence() -> None:
    schema = load_json(REPO_ROOT / "schemas" / "model-replacement.schema.json")
    facets = schema["properties"]["facets"]["items"]["properties"]["facet"]["enum"]
    assert facets[-1] == "surrogate_evidence"
    assert len(facets) == len(set(facets)) == 10


def test_the_digest_addendum_covers_exactly_m04s_schemas_and_the_partition_holds() -> None:
    surrogate = load_yaml(REPO_ROOT / "benchmarks" / "m04" / "numerical_policy_surrogate.yaml")[
        "numerical_policy_surrogate"
    ]
    assert tuple(surrogate["schemas"]) == M04_SCHEMAS
    policy = load_yaml(REPO_ROOT / "benchmarks" / "t08" / "numerical_policy_v2.yaml")[
        "numerical_policy"
    ]
    external = t08_numerical_policy.external_policy()
    assert t08_numerical_policy.surrogate_audit(policy, external, surrogate) == []
    # The v2 partition and M02's are computed without M04's files, so neither moves.
    added = set(surrogate["exact_sha256"])
    assert not added & t08_numerical_policy.schema_sha256_names()
    assert not added & t08_numerical_policy.schema_sha256_names(external=True)
    unclassified = {**surrogate, "exact_sha256": sorted(added - {"keys_sha256"})}
    (problem,) = t08_numerical_policy.surrogate_audit(policy, external, unclassified)
    assert problem == "(m04) unclassified sha256 names: ['keys_sha256']"


def test_the_schemas_readme_lists_m04s_schemas() -> None:
    readme = (REPO_ROOT / "schemas" / "README.md").read_text(encoding="utf-8")
    for name in M04_SCHEMAS:
        assert f"`{name}`" in readme, name
