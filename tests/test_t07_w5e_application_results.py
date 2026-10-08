"""T07 W5e: the JobControl and Inspection result shapes are frozen in
`schemas/application-results.schema.json` (design note ruling round 4, W5a-Q2, §11.3–§11.4 as
amended; ADR 0019 Amendment 1; gates R4-G3 and R4-G4).

- **The move is inert (R4-G3).** For each of the 20 operations, `canonical_json` of its response
  schema with every `$ref` inlined equals the snapshot taken at `b13d556`, whose `operations.py`
  is `9b541df`'s. The snapshot is pinned here as SHA-256 digests; `artifact_bytes` has no
  response schema (its response is bytes).
- **The schema.** One `$def` per response shape in `OPERATIONS` with no published schema of its
  own, named in snake_case after its Python result type, a page `<item>_page`; each such operation
  `$ref`s its `$def`.
- **Fixtures (R4-G3).** At least one valid fixture per `$def`, emitted from real responses through
  `dispatch` (`scripts/t07_schema_fixtures.py`, the job-fixture precedent, R-015), and one invalid
  fixture per `$def`: the valid one with a required member removed.
- **Responses (R4-G3).** Every response the W4 and W5 tests produce is held to its operation's
  response schema — now the published `$def` — by `test_t07_w5a_operations` (every operation
  through `dispatch`, and G13) and by `t07_jobs_support.response_schema_violations` at the
  teardown of the W4 test projects.
- **The frozen list (R4-G4).** `docs/interfaces-frozen.md` §2 lists the file, and ADR 0019 carries
  Amendment 1.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from m02_schema_support import without_m02

from openflowsheet.application.operations import OPERATIONS, Operation
from openflowsheet.application.types import SCHEMA_BASE, schema_errors
from openflowsheet.canonical import canonical_json

SCHEMA = "application-results.schema.json"
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas" / "application_results"
#: The operation each `$def` answers (§4.3), by the rule: the snake_case of its result type.
DEF_OF_OPERATION: dict[str, str] = {
    "submit_job": "submit_result",
    "list_jobs": "job_page",
    "list_job_events": "job_event_page",
    "wait_job": "job_wait",
    "get_project": "project_summary",
    "list_models": "model_registry_view",
    "list_revisions": "revision_page",
    "get_revision": "projection",
    "inspect_structure": "projection",
    "get_artifact": "projection",
    "diff_revisions": "semantic_diff",
}
#: `revision_summary` is a page's item, and its own `$def`.
DEFS = frozenset({*DEF_OF_OPERATION.values(), "revision_summary"})
#: R4-G3: SHA-256 of `canonical_json` of each operation's fully resolved response schema, taken at
#: `b13d556` with `resolved_response` below (`None`: no response schema).
SNAPSHOT_AT_B13D556: dict[str, str | None] = {
    "validate": "dbbdaa6c1e6859398c5d685df7c881b8739fa786b4db981d00c071ed4aff7582",
    "commit_change": "d416001ea57015e2f08b602623c845d4fb3606575fd03eb363d888b813b58941",
    "solve": "9a9b75207b7d94467ade4dff227760dbe059451f94fc5d573fae35ff687498c7",
    "reproduce": "8e62572a35ecd04613e194db6cbf82cd53da11cd150d7360a1056b0fbb31cd66",
    "submit_job": "0cd08fb1d03d1ff16f89db5d9a6c6602bcac8772740d30ed2ff49595cf2e3995",
    "get_job": "599ebcdb703795bae609c5a804dfbd54b7f9b489ee9cf328cf879948dddcb736",
    "list_jobs": "cf3c8df4f34064a7ee04a5ef098fe5304b25b0ccede5aa69d180de9571dce660",
    "list_job_events": "8784978e7d6a6cde8a94b70c14252f0f4a9dfa3b6d2ddd2f771fde74dfe4a835",
    "wait_job": "347d746a0ef4806b14a83d7c7d3cb4bc909a488c30d65fc0f4cea4afaf537986",
    "cancel_job": "599ebcdb703795bae609c5a804dfbd54b7f9b489ee9cf328cf879948dddcb736",
    "get_job_result": "7a8610722f2d4644e792e571879f9c01d43693ea3f767d3be724839bd53a4598",
    "get_project": "0eb1108f60e26c855b4e72747118184be043d60fdcf4237355f6f5a4e415253b",
    "list_models": "6b4d0be4dbe3e7f309f53c192fbbc7ec1fb3cbe005a6a88b45274bdf1616203f",
    "list_revisions": "33627ba534225466aed55586e31158b1c703f72a533cf6337255f59a0baa19fc",
    "get_revision": "951b77ea0f69a0eb8f5cb7d44a9c1c570dd6d05d57b7c72de05a7a7e61208465",
    "diff_revisions": "9544ff03264e46a0684f8a89e45197b37319db193c21ec97d7f0ecde908e1dea",
    "inspect_structure": "951b77ea0f69a0eb8f5cb7d44a9c1c570dd6d05d57b7c72de05a7a7e61208465",
    "preview_change": "d416001ea57015e2f08b602623c845d4fb3606575fd03eb363d888b813b58941",
    "get_artifact": "951b77ea0f69a0eb8f5cb7d44a9c1c570dd6d05d57b7c72de05a7a7e61208465",
    "artifact_bytes": None,
}


# -------------------------------------------------------------------------- $ref resolution


def _published() -> dict[str, Any]:
    documents = (load_json(path) for path in sorted(SCHEMA_DIR.glob("*.schema.json")))
    return {document["$id"]: document for document in documents}


def _target(document: Any, fragment: str) -> Any:
    """RFC 6901 over a JSON Schema document (a `$ref` fragment is a pointer here)."""
    node = document
    for token in fragment.split("/")[1:] if fragment else ():
        node = node[token.replace("~1", "/").replace("~0", "~")]
    return node


def _resolved(schema: Any, base: str, published: dict[str, Any], seen: tuple[str, ...]) -> Any:
    if isinstance(schema, list):
        return [_resolved(item, base, published, seen) for item in schema]
    if not isinstance(schema, dict):
        return schema
    members = {
        key: _resolved(value, base, published, seen)
        for key, value in schema.items()
        if key != "$ref"
    }
    if "$ref" not in schema:
        return members
    absolute = urljoin(base, schema["$ref"])
    if absolute in seen:
        raise ValueError(f"a cyclic $ref: {absolute}")
    uri, fragment = urldefrag(absolute)
    target = _resolved(_target(published[uri], fragment), uri, published, (*seen, absolute))
    if not members:
        return target
    assert "allOf" not in members, "a $ref beside an allOf"
    return {**members, "allOf": [target]}


def resolved_response(operation: Operation) -> Any:
    """The operation's response schema with every `$ref` inlined, recursively: a `$ref` alone is
    replaced by its target, one with siblings becomes `allOf: [target]` beside them."""
    if operation.response_schema is None:
        return None
    return _resolved(dict(operation.response_schema), "", _published(), ())


def _digest(document: Any) -> str | None:
    return None if document is None else hashlib.sha256(canonical_json(document)).hexdigest()


# ----------------------------------------------------------------------------------- R4-G3


#: ADR 0019 Amendment 2 (approved by Frank on 2026-09-27; T07 ruling round 6, B2 item 4, gate
#: G-R6-6): `model_registry_view`'s pins and choice options gain the required member
#: `specifications`. `list_models`'s snapshot is re-taken; every other operation's stands.
SNAPSHOT_AMENDMENT_2: dict[str, str | None] = {
    "list_models": "12d8824519a37a41eafa12a88308bbafa563ccd706d226c60f3f39310b6cad85",
}


#: M02 (ADR 0033-0035, design note §3.6): the operations whose resolved response embeds a schema
#: M02 widened additively (`job`, `run-result`, `solve-event`, `api-error`, `transaction-result`).
#: Re-taken; with M02's additions removed every one is its earlier snapshot again (G1 (c),
#: `tests/test_m02_schemas.py`). The `job.schema.json`-embedding ones re-taken again at WO-6,
#: where `job_result`'s `experiment` member admits null for a job ended before any attempt.
SNAPSHOT_M02: dict[str, str | None] = {
    "commit_change": "c44597cdfdff995b96c491f8b4de0e71d17c79d442519e4b8e5cbeee81a28207",
    "preview_change": "c44597cdfdff995b96c491f8b4de0e71d17c79d442519e4b8e5cbeee81a28207",
    "solve": "892799e0e9385badcd353ae38e1ec483b6510abb04983647a922d87f6a929505",
    "submit_job": "e9abdbeb0d5cdfcabb497a0961bf1472852954c148f520f51ec93d9630a704da",
    "get_job": "1d3c46e2e941994d4f946f1b8de9cd31a256b0d9306c18d298a2af70f25325c4",
    "cancel_job": "1d3c46e2e941994d4f946f1b8de9cd31a256b0d9306c18d298a2af70f25325c4",
    "list_jobs": "0ae6014c2dba7c1801b3ae33b8ce87125ecaa0005e1671214537c1dbe60d1a81",
    "list_job_events": "9e7f7152392798eec6d79c2be32ca7c90287dcce754cfb4c9d2cb5c3dab561fa",
    "wait_job": "1b119ce8f27d361d598aef22268d9c5046daa73814670687909c6f4719142ccb",
    "get_job_result": "e76fcd6c22749c16c55c2246e2542ede607bca861661c7be2ebc7d10425a07f4",
}


def _without_specifications(schema: Any) -> Any:
    """`schema` with Amendment 2's member taken out of every pin and option: its property and its
    entry in `required`."""
    if isinstance(schema, list):
        return [_without_specifications(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = {key: _without_specifications(value) for key, value in schema.items()}
    properties = out.get("properties")
    if isinstance(properties, dict) and {"name", "port", "quantity"} <= set(properties):
        properties.pop("specifications", None)
        out["required"] = [member for member in out["required"] if member != "specifications"]
    return out


def test_r4_g3_every_resolved_response_schema_equals_the_snapshot() -> None:
    measured = {name: _digest(resolved_response(op)) for name, op in OPERATIONS.items()}
    assert len(measured) == 20
    assert measured == {**SNAPSHOT_AT_B13D556, **SNAPSHOT_AMENDMENT_2, **SNAPSHOT_M02}
    for operation in OPERATIONS.values():
        assert "$ref" not in canonical_json(resolved_response(operation)).decode("utf-8")


def test_g_r6_6_list_models_moved_only_by_the_approved_additive_member() -> None:
    """R4-G3 differs only in `model_registry_view`, and only by `specifications`: with that member
    removed from its pins and options, `list_models`'s resolved schema is the `b13d556`
    snapshot again, and no other `$def` of the file moved."""
    resolved = resolved_response(OPERATIONS["list_models"])
    assert _digest(resolved) != SNAPSHOT_AT_B13D556["list_models"]
    assert _digest(_without_specifications(resolved)) == SNAPSHOT_AT_B13D556["list_models"]
    # M02's additive members are taken out first (G1 (c)); they are M02's, not Amendment 2's.
    moved = [
        name
        for name in OPERATIONS
        if _digest(without_m02(resolved_response(OPERATIONS[name]))) != SNAPSHOT_AT_B13D556[name]
    ]
    assert moved == ["list_models"]


def test_g_r6_6_every_pin_lists_its_pin_encodings() -> None:
    """The response validates against the amended schema, and each pin's and each option's
    `specifications` is its `pin_encodings`."""
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.revision_binding import MODEL_SIGNATURES, pin_encodings

    with tempfile.TemporaryDirectory() as scratch:
        with LocalApplication.create(Path(scratch) / "p", project_id="g-r6-6") as application:
            view = application.list_models().as_document()
    assert schema_errors(f"{SCHEMA}#/$defs/model_registry_view", view) == []
    checked = 0
    for model in view["models"]:
        signature = MODEL_SIGNATURES[model["model_id"]]
        options = [o for c in signature.choices for o in c.options]
        listed = [*model["pins"], *(o for c in model["choices"] for o in c["options"])]
        for entry, pin in zip(listed, (*signature.pins, *options), strict=True):
            assert entry["name"] == pin.name
            expected = [e.as_document() for e in pin_encodings(signature, pin)]
            assert entry["specifications"] == expected
            checked += 1
    assert checked == 16


def test_the_schema_is_draft_2020_12_with_an_id_and_a_description() -> None:
    document = load_json(SCHEMA_DIR / SCHEMA)
    Draft202012Validator.check_schema(document)
    assert document["$id"] == SCHEMA_BASE + SCHEMA
    assert len(document["description"]) > 80


def test_one_def_per_unpublished_shape_and_each_operation_refs_it() -> None:
    assert set(load_json(SCHEMA_DIR / SCHEMA)["$defs"]) == DEFS
    for name, operation in OPERATIONS.items():
        expected = DEF_OF_OPERATION.get(name)
        if expected is not None:
            assert operation.response_schema == {
                "$ref": f"{SCHEMA_BASE}{SCHEMA}#/$defs/{expected}"
            }, name
        elif operation.response_schema is not None:
            # Every other response is a published schema of its own, referenced whole.
            (reference,) = operation.response_schema.values()
            assert list(operation.response_schema) == ["$ref"], name
            assert SCHEMA not in reference, name


def _valid(name: str) -> list[Path]:
    return sorted((FIXTURES / name / "valid").glob("*.json"))


def _invalid(name: str) -> list[Path]:
    return sorted((FIXTURES / name / "invalid").glob("*.json"))


@pytest.mark.parametrize("name", sorted(DEFS))
def test_r4_g3_every_def_has_a_valid_and_an_invalid_fixture(name: str) -> None:
    reference = f"{SCHEMA}#/$defs/{name}"
    assert _valid(name) and _invalid(name), name
    for path in _valid(name):
        assert schema_errors(reference, load_json(path)) == [], path
    for path in _invalid(name):
        fixture = load_json(path)
        assert set(fixture) == {"expect_error", "document"}, path
        errors = schema_errors(reference, fixture["document"])
        assert any(fixture["expect_error"] in error for error in errors), (path, errors)


def test_the_fixtures_are_what_real_responses_emit_today() -> None:
    """R-015: regenerated from real responses, the fixtures are equal with the members that differ
    between generations masked (timestamps, output digests and sizes, the git commit)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from t07_schema_fixtures import application_results_documents, stable

    emitted = application_results_documents()
    committed = sorted(str(path.relative_to(FIXTURES.parent)) for path in FIXTURES.rglob("*.json"))
    assert sorted(emitted) == committed
    for name, document in emitted.items():
        assert stable(document) == stable(load_json(FIXTURES.parent / name)), name


# ----------------------------------------------------------------------------------- R4-G4


def test_r4_g4_the_frozen_list_and_the_adr_carry_the_schema() -> None:
    frozen = (REPO_ROOT / "docs" / "interfaces-frozen.md").read_text("utf-8")
    section = frozen.split("## 2.", 1)[1].split("## 3.", 1)[0]
    assert f"schemas/{SCHEMA}" in section
    adr = (REPO_ROOT / "docs" / "adr" / "0019-application-contract-v1.md").read_text("utf-8")
    assert "## Amendment 1" in adr and SCHEMA in adr
