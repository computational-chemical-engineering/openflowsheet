"""F8-WO1 (ADR 0067 D2, D3, D5, D6, D8, D9): the v2 `RunManifest` and the F8 schemas.

E-F8-2, schema part: a v2 manifest with every D2 member validates against
`run-manifest.schema.json`; its `structural_sha256` covers `data_lock_sha256`, `extensions_used`,
`run_kind` and `documents` and neither `bundle_format` nor `environment.registry`; a v1 manifest's
`structural_sha256` is unchanged; `records-index` and `run-evidence` documents validate and refuse
an unknown member; a replay report in `forced_replay` is refused
`construct_unavailable(forced_replay, TX)`. E-F8-10's v1 half: every committed 0.3.0 manifest
keeps its recorded structural identity, which is also the one the pre-F8 exclusion list gives.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from openflowsheet.canonical import canonical_json
from openflowsheet.run.bundle import read_manifest
from openflowsheet.run.manifest import NON_STRUCTURAL, RunManifest
from openflowsheet.run.manifest_v2 import (
    BUNDLE_FORMAT,
    MEMBER_CLASSES,
    EnvironmentRegistry,
    ReplayModeRefusedError,
    RunManifestV2,
    extensions_used_rows,
    refuse_reserved_mode,
)

SCHEMAS = REPO_ROOT / "schemas"
SCHEMA_ID = "https://github.com/frankp/process-runtime/schemas/"
BUNDLES = REPO_ROOT / "tests" / "fixtures" / "f0" / "v0.3.0-bundles"
V1_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "schemas" / "run_manifest" / "valid"
RUN_MANIFEST = "https://raw.githubusercontent.com/computational-chemical-engineering/clearsheet/main/schemas/run-manifest.schema.json"
REPLAY_REPORT = "https://raw.githubusercontent.com/computational-chemical-engineering/clearsheet/main/schemas/replay-report.schema.json"
#: `NON_STRUCTURAL` as it stood before F8 (K05, `run/manifest.py`).
PRE_F8_NON_STRUCTURAL = frozenset(
    {
        "run_id",
        "started_at",
        "elapsed_seconds",
        "parent_run_id",
        "hostname",
        "environment",
        "artifacts",
    }
)
SHA_A, SHA_B, SHA_C, SHA_D = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)
EXTENSIONS = (
    ("property_method", "ideal-gas", "1.0.0", SHA_A, SHA_B),
    ("unit_model", "flash", "1.2.0", SHA_C, SHA_D),
)


def _registry() -> Registry:
    resources = []
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        document = load_json(path)
        resources.append((document["$id"], Resource(contents=document, specification=DRAFT202012)))
    return Registry().with_resources(resources)


REGISTRY = _registry()


def schema_errors(reference: str, document: Any) -> list[str]:
    """Every error of `document` against the schema `reference` (a full `$id`, or a name under
    the `frankp` base, with an optional `#` fragment)."""
    if "://" not in reference:
        reference = SCHEMA_ID + reference
    validator = Draft202012Validator({"$ref": reference}, registry=REGISTRY)
    return [error.message for error in validator.iter_errors(document)]


def _v1_manifests() -> list[Path]:
    return sorted(BUNDLES.glob("*/*/run-manifest.json"))


@pytest.fixture(scope="module")
def v1() -> RunManifest:
    manifest, _ = read_manifest(next(iter(_v1_manifests())).parent)
    return manifest


def _v2(v1: RunManifest, **members: Any) -> RunManifestV2:
    base = {entry.name: getattr(v1, entry.name) for entry in dataclasses.fields(RunManifest)}
    defaults: dict[str, Any] = {
        "data_lock_sha256": SHA_A,
        "extensions_used": EXTENSIONS,
        "environment_registry": EnvironmentRegistry(SHA_B, SHA_C),
        "run_kind": ("steady", "1.0.0"),
        "documents": {"revision": SHA_D, "policy": SHA_A},
    }
    return RunManifestV2(**base, **{**defaults, **members})


def _schema(name: str) -> dict[str, Any]:
    document = load_json(SCHEMAS / name)
    assert isinstance(document, dict)
    return document


# ------------------------------------------------------------------------------- the v1 path


def test_e_f8_10_every_committed_v1_manifest_keeps_its_structural_identity() -> None:
    paths = _v1_manifests()
    assert len(paths) == 52
    for path in paths:
        manifest, document = read_manifest(path.parent)
        assert "bundle_format" not in document
        assert manifest.structural_sha256 == document["structural_sha256"], path
        assert manifest.manifest_sha256 == document["manifest_sha256"], path
        pre_f8 = {key: value for key, value in document.items() if key not in PRE_F8_NON_STRUCTURAL}
        pre_f8.pop("structural_sha256")
        pre_f8.pop("manifest_sha256")
        assert hashlib.sha256(canonical_json(pre_f8)).hexdigest() == manifest.structural_sha256


def test_the_v1_manifests_still_validate() -> None:
    documents = [load_json(path) for path in [*_v1_manifests(), *V1_FIXTURE.glob("*.json")]]
    assert len(documents) == 53
    for document in documents:
        assert schema_errors(RUN_MANIFEST, document) == []


def test_bundle_format_is_the_only_member_f8_adds_to_non_structural() -> None:
    assert NON_STRUCTURAL - PRE_F8_NON_STRUCTURAL == {"bundle_format"}


# ------------------------------------------------------------------------------ the v2 manifest


def test_e_f8_2_a_v2_manifest_with_every_d2_member_validates(v1: RunManifest) -> None:
    document = _v2(v1).as_document()
    assert document["bundle_format"] == BUNDLE_FORMAT == "openflowsheet-bundle-v2"
    for member in ("data_lock_sha256", "extensions_used", "run_kind", "documents"):
        assert member in document
    assert document["environment"]["registry"] == {
        "registry_sha256": SHA_B,
        "snapshot_sha256": SHA_C,
    }
    assert schema_errors(RUN_MANIFEST, document) == []


def test_the_v2_manifest_round_trips(v1: RunManifest) -> None:
    for manifest in (_v2(v1), _v2(v1, run_kind=None, documents=None)):
        document = manifest.as_document()
        again = RunManifestV2.from_document(document)
        assert again == manifest
        assert again.as_document() == document


def test_run_kind_and_documents_are_absent_when_unset(v1: RunManifest) -> None:
    document = _v2(v1, run_kind=None, documents=None).as_document()
    assert "run_kind" not in document and "documents" not in document
    assert schema_errors(RUN_MANIFEST, document) == []


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("data_lock_sha256", SHA_D),
        ("extensions_used", EXTENSIONS[:1]),
        ("extensions_used", (EXTENSIONS[0], (*EXTENSIONS[1][:4], SHA_A))),
        ("run_kind", ("steady", "1.0.1")),
        ("run_kind", None),
        ("documents", {"revision": SHA_D, "policy": SHA_B}),
        ("documents", None),
    ],
)
def test_e_f8_2_the_structural_identity_covers_the_r0_members(
    v1: RunManifest, member: str, value: Any
) -> None:
    before = _v2(v1)
    after = _v2(v1, **{member: value})
    assert after.structural_sha256 != before.structural_sha256, member
    assert MEMBER_CLASSES[member] == "R0"


def test_e_f8_2_the_structural_identity_ignores_the_excluded_members(v1: RunManifest) -> None:
    before = _v2(v1)
    moved = _v2(v1, environment_registry=EnvironmentRegistry(SHA_D, SHA_D))
    assert moved.structural_sha256 == before.structural_sha256
    assert moved.manifest_sha256 != before.manifest_sha256
    assert MEMBER_CLASSES["environment.registry"] == "excluded"

    # `bundle_format` is fixed on the class; the structural document never holds it.
    assert "bundle_format" in before.as_document()
    assert "bundle_format" not in before.structural_document
    assert MEMBER_CLASSES["bundle_format"] == "excluded"
    document = before.as_document()
    document["bundle_format"] = "something-else"
    document.pop("structural_sha256")
    document.pop("manifest_sha256")
    structural = {key: value for key, value in document.items() if key not in NON_STRUCTURAL}
    assert hashlib.sha256(canonical_json(structural)).hexdigest() == before.structural_sha256


def test_d9_the_structural_document_holds_exactly_the_r0_members(v1: RunManifest) -> None:
    structural = _v2(v1).structural_document
    for member, kind in MEMBER_CLASSES.items():
        top = member.split(".", 1)[0]
        assert (top in structural) == (kind == "R0"), member
    assert set(structural) - set(v1.structural_document) == {
        member for member, kind in MEMBER_CLASSES.items() if kind == "R0"
    }


def test_a_v2_manifest_differs_from_its_v1_fields_in_identity(v1: RunManifest) -> None:
    assert _v2(v1).structural_sha256 != v1.structural_sha256


def test_extensions_used_rows_sort_and_deduplicate() -> None:
    @dataclasses.dataclass(frozen=True)
    class Entry:
        kind: str
        id: str
        version: str
        descriptor_sha256: str
        self_sha256: str

    entries = [Entry(*EXTENSIONS[1]), Entry(*EXTENSIONS[0]), Entry(*EXTENSIONS[1])]
    entries.append(Entry("unit_model", "flash", "1.10.0", SHA_A, SHA_A))
    rows = extensions_used_rows(entries)  # type: ignore[arg-type]
    assert rows == (*EXTENSIONS, ("unit_model", "flash", "1.10.0", SHA_A, SHA_A))
    with pytest.raises(ValueError, match="once"):
        extensions_used_rows([Entry(*EXTENSIONS[0]), Entry(*EXTENSIONS[0][:4], SHA_C)])  # type: ignore[arg-type]


def test_an_unsorted_extensions_used_is_refused(v1: RunManifest) -> None:
    with pytest.raises(ValueError, match="sorted"):
        _v2(v1, extensions_used=EXTENSIONS[::-1])


def test_from_document_refuses_a_v1_manifest(v1: RunManifest) -> None:
    with pytest.raises(ValueError, match="not a v2 manifest"):
        RunManifestV2.from_document(v1.as_document())


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("data_lock_sha256",), "not-a-sha"),
        (("bundle_format",), "openflowsheet-bundle-v3"),
        (("extensions_used",), [["unit_model", "flash", "1.2.0", SHA_C]]),
        (("run_kind",), ["steady"]),
        (("documents",), {"revision": "x"}),
        (("environment", "registry"), {"registry_sha256": SHA_B}),
        (("an_unknown_member",), 1),
        (("environment", "an_unknown_member"), 1),
    ],
)
def test_the_schema_refuses_a_malformed_v2_member(
    v1: RunManifest, path: tuple[str, ...], value: Any
) -> None:
    document = copy.deepcopy(_v2(v1).as_document())
    node = document
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert schema_errors(RUN_MANIFEST, document) != []


# ---------------------------------------------------------------------------- the new schemas

RECORDS_INDEX = {
    "records": [
        {
            "sha256": SHA_A,
            "embedded": True,
            "sources": [
                {
                    "source_id": "dippr-801",
                    "source_sha256": SHA_B,
                    "assessment": "permitted",
                    "conditions": "attribution",
                }
            ],
        },
        {
            "sha256": SHA_C,
            "embedded": False,
            "sources": [
                {
                    "source_id": "vendor-x",
                    "source_sha256": SHA_D,
                    "assessment": "unknown",
                    "conditions": None,
                }
            ],
        },
    ]
}
RUN_EVIDENCE = {
    "evidence_format": "openflowsheet-run-evidence-v1",
    "verification": {"certificate": "solution-certificate.json", "verification_status": "VERIFIED"},
    "validation": {"entries": []},
    "optimality": {"claim": "none", "basis": "simulation"},
    "extensions": [],
    "notices": [
        {"code": "extension_unreviewed", "params": {"id": "acme.flash", "origin": "installed"}}
    ],
}


@pytest.mark.parametrize(
    ("name", "document"),
    [("records-index.schema.json", RECORDS_INDEX), ("run-evidence.schema.json", RUN_EVIDENCE)],
)
def test_e_f8_2_the_new_documents_validate_and_refuse_an_unknown_member(
    name: str, document: dict[str, Any]
) -> None:
    assert _schema(name)["$id"] == SCHEMA_ID + name
    assert name in load_json(SCHEMAS / "registry.json")
    assert schema_errors(name, document) == []
    assert schema_errors(name, {**document, "an_unknown_member": 1}) != []


def test_the_records_index_refuses_an_assessment_outside_d11() -> None:
    document = copy.deepcopy(RECORDS_INDEX)
    document["records"][0]["sources"][0]["assessment"] = "granted"
    assert schema_errors("records-index.schema.json", document) != []
    document = copy.deepcopy(RECORDS_INDEX)
    document["records"][0]["sources"][0]["extra"] = 1
    assert schema_errors("records-index.schema.json", document) != []


def test_the_run_evidence_envelope_is_closed() -> None:
    for member in ("verification", "validation", "optimality"):
        document = copy.deepcopy(RUN_EVIDENCE)
        document[member]["an_unknown_member"] = 1
        assert schema_errors("run-evidence.schema.json", document) != [], member
    document = copy.deepcopy(RUN_EVIDENCE)
    document["evidence_format"] = "openflowsheet-run-evidence-v2"
    assert schema_errors("run-evidence.schema.json", document) != []
    document = copy.deepcopy(RUN_EVIDENCE)
    document["optimality"]["claim"] = "certain"
    assert schema_errors("run-evidence.schema.json", document) != []


def test_the_replay_members_of_bundle_v2_validate() -> None:
    """D5's `registry_comparison` and `data_availability` shapes (Amendment 12)."""

    def errors(name: str, document: Any) -> list[str]:
        return schema_errors("bundle-v2.schema.json#/$defs/" + name, document)

    comparison = {
        "recorded_registry_sha256": SHA_A,
        "current_registry_sha256": SHA_B,
        "changed": [["unit_model", "flash", "1.2.0"]],
        "missing": [],
        "unused_differences": 3,
    }
    availability = {"embedded": 2, "from_store": 1, "missing": [SHA_C, SHA_D]}
    assert errors("registry_comparison", comparison) == []
    assert errors("data_availability", availability) == []
    assert errors("registry_comparison", {**comparison, "extra": 1}) != []
    assert errors("data_availability", {**availability, "missing": ["x"]}) != []


# ------------------------------------------------------------------------- forced_replay (D8)


def test_d8_a_forced_replay_report_is_refused_construct_unavailable() -> None:
    report = load_json(REPO_ROOT / "tests/fixtures/schemas/replay_report/valid/exact_match.json")
    refuse_reserved_mode(report)  # a v1 report passes
    with pytest.raises(ReplayModeRefusedError) as raised:
        refuse_reserved_mode({**report, "mode": "forced_replay"})
    assert raised.value.coded.as_document() == {
        "code": "construct_unavailable",
        "params": {"construct": "forced_replay", "foundation": "TX"},
    }
    assert str(raised.value) == "construct_unavailable(forced_replay, TX)"


def test_the_replay_report_schema_still_admits_the_v1_reports() -> None:
    for path in sorted((REPO_ROOT / "tests/fixtures/schemas/replay_report/valid").glob("*.json")):
        assert schema_errors(REPLAY_REPORT, load_json(path)) == [], path.name
