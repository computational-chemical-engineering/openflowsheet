"""F1-WO1 (ADR 0060): the registry core, its two schemas, and exit tests E-F1-5, E-F1-8, E-F1-9.

- The schemas: both are draft 2020-12 schemas published by `$id`; a valid descriptor and a built
  registry's snapshot pass; each invalid descriptor is wrong in one way and is refused there.
- D2 normalisation, D3 self-hash, D4 tokens: spelled examples, and recomputation independent of
  `openflowsheet.canonical` (`json.dumps` equals canonical JSON on ASCII strings and arrays).
- **E-F1-5** on synthetic built-ins (`tests/fixtures/registry/synthetic/`): `registry_sha256` is
  the same in two fresh processes with `PYTHONHASHSEED=0` and `=random`, equals the committed
  constant `synthetic-builtin-sha256.txt` and an independent recomputation, and does not depend on
  the order of the tables or of their entries.
- **E-F1-8**: a status change or an attestation leaves every `descriptor_sha256`,
  `registry_sha256` and admission verdict unchanged and changes only `effective_status`,
  `evidence_class` and the notices.
- **E-F1-9** [gen]: 10⁴ random triples, `admit` against a brute-force D5 written here from the ADR;
  raising a provided level never turns an admission into a refusal; normalisation is idempotent;
  the fixed counterexample of the W1 P1 review's finding 1.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator

from openflowsheet.application.types import SCHEMA_BASE, published_schemas, schema_errors
from openflowsheet.registry import (
    Attestation,
    Coded,
    ExtensionPackage,
    Registered,
    Registry,
    RegistryBuildError,
    admit,
)
from openflowsheet.registry.descriptor import descriptor_sha256, normalise
from openflowsheet.registry.selfhash import SelfHashUnavailableError, implementation_sha256
from openflowsheet.registry.selfhash import self_sha256 as compute_self_sha256
from openflowsheet.registry.tokens import (
    normalise_provides,
    normalise_requires,
    parse,
    satisfied,
    token_problem,
)

SYNTHETIC = REPO_ROOT / "tests" / "fixtures" / "registry" / "synthetic"
SYNTHETIC_ROOT = SYNTHETIC / "root"
CONSTANT = REPO_ROOT / "tests" / "fixtures" / "registry" / "synthetic-builtin-sha256.txt"
SCHEMAS = ("extension-descriptor.schema.json", "registry-snapshot.schema.json")
EMPTY_SET_SHA = hashlib.sha256(b"[]").hexdigest()


def _tables() -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = json.loads(
        (SYNTHETIC / "builtin.json").read_text(encoding="utf-8")
    )
    return tables


def _build(**kwargs: Any) -> Registry:
    kwargs.setdefault("builtin_tables", _tables())
    return Registry.build(builtin_root=SYNTHETIC_ROOT, builtin_version="0.0.0", **kwargs)


def _descriptor(kind: str, identifier: str, **fields: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "descriptor_format": "openflowsheet-extension-v1",
        "kind": kind,
        "id": identifier,
        "version": "1.0.0",
        "title": identifier,
        "status": "declared",
        "requires": [],
        "provides": [],
        "limitations": [],
        "platforms": ["any"],
        "pip_extra": None,
        "data_rights": None,
        "implementation": {"modules": [], "factory": None},
        "payload": {},
    }
    document.update(fields)
    return document


def _package(namespace: str, descriptors: list[dict[str, Any]], **fields: Any) -> ExtensionPackage:
    document = {
        "package_format": "openflowsheet-extension-package-v1",
        "namespace": namespace,
        "descriptors": descriptors,
    }
    return ExtensionPackage(
        distribution=fields.get("distribution", f"{namespace}-dist"),
        distribution_version="1.2.3",
        entry_point=namespace,
        import_root=fields.get("import_root", SYNTHETIC_ROOT),
        document=document,
    )


def _acme(**unit_fields: Any) -> ExtensionPackage:
    """An installed package: a v2 method, a unit and a contributed unit, on `nTP-v1`."""
    method = _descriptor(
        "property_method",
        "acme.method",
        provides=["conn:nTP-v1", "x:acme.surface:2"],
        implementation={"modules": ["synth_ext/kernel.py"], "factory": None},
    )
    unit = _descriptor(
        "unit_model",
        "acme.unit",
        requires=[["conn:nTP-v1"], ["x:acme.surface:1"]],
        payload={"bindable": True},
        **unit_fields,
    )
    contributed = _descriptor(
        "unit_model",
        "acme.agent_unit",
        requires=[["conn:nTP-v1"]],
        contributed_by={"actor": "agent", "session": None, "date": "2026-11-11"},
    )
    return _package("acme", [method, unit, contributed])


# ---------------------------------------------------------------------------------------------
# The two schemas


@pytest.mark.parametrize("name", SCHEMAS)
def test_each_schema_is_a_draft_2020_12_schema_published_by_its_id(name: str) -> None:
    document = json.loads((REPO_ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(document)
    assert document["$id"] == SCHEMA_BASE + name
    assert document["description"].startswith("DRAFT until ADR 0060 is Accepted")
    assert published_schemas()[SCHEMA_BASE + name] == document


def test_d1_the_kind_enum_is_the_closed_list_of_22() -> None:
    """D1's table, transcribed here; the package states it once, in the schema's enum."""
    document = json.loads((REPO_ROOT / "schemas" / SCHEMAS[0]).read_text(encoding="utf-8"))
    assert document["properties"]["kind"]["enum"] == [
        "property_method",
        "property_source",
        "unit_model",
        "connection_definition",
        "attribute_kind",
        "derived_quantity",
        "kinetics_kind",
        "stability_trial_set",
        "phase_family",
        "discrete_coordinate",
        "record_type",
        "correlation_form",
        "data_source",
        "record_generator",
        "solver_route",
        "run_kind",
        "functional_contributor",
        "exchange_format",
        "revision_section",
        "semantic_role",
        "equipment_class",
        "message_entries",
    ]


def test_a_built_registrys_snapshot_and_descriptors_pass_their_schemas() -> None:
    registry = _build(packages=[_acme()])
    assert schema_errors("registry-snapshot.schema.json", registry.snapshot()) == []
    for entry in registry.descriptors():
        assert schema_errors("extension-descriptor.schema.json", dict(entry.document)) == []


INVALID: tuple[tuple[str, dict[str, Any], str], ...] = (
    ("an id with a colon (rule C1)", {"id": "acme:unit"}, "/id"),
    ("a version with a leading zero", {"version": "01.0.0"}, "/version"),
    ("an unknown kind", {"kind": "plugin"}, "/kind"),
    ("a token outside D4's grammar", {"provides": ["Conn:nTP-v1"]}, "/provides/0"),
    ("a level with a leading zero", {"provides": ["conn:nTP-v1:01"]}, "/provides/0"),
    ("an empty clause", {"requires": [[]]}, "/requires/0"),
    ("`any` beside a platform", {"platforms": ["any", "linux-x86_64"]}, "/platforms"),
    ("an absolute module path", {"implementation": {"modules": ["/x.py"], "factory": None}}, ""),
    ("a `..` segment", {"implementation": {"modules": ["a/../x.py"], "factory": None}}, ""),
    ("an undeclared member", {"self_sha256": EMPTY_SET_SHA}, ""),
    ("a status outside D2's list", {"status": "approved"}, "/status"),
)


@pytest.mark.parametrize(("why", "change", "pointer"), INVALID, ids=[i[0] for i in INVALID])
def test_each_invalid_descriptor_is_refused_where_it_is_wrong(
    why: str, change: dict[str, Any], pointer: str
) -> None:
    document = _descriptor("unit_model", "acme.unit") | change
    errors = schema_errors("extension-descriptor.schema.json", document)
    assert errors, why
    assert any(error.startswith(pointer) for error in errors), errors


# ---------------------------------------------------------------------------------------------
# D2 normalisation and D4 tokens


def test_d2_normalisation_spelled_out() -> None:
    document = _descriptor(
        "unit_model",
        "acme.unit",
        status="tested",
        requires=[["x:acme.b", "conn:nTP-v1:0", "x:acme.b"], ["conn:nTP-v1"], ["phase:L:2"]],
        provides=["x:acme.p:1", "x:acme.p:3", "x:acme.a:0", "x:acme.p"],
        implementation={"modules": ["b.py", "a.py"], "factory": None},
        limitations=[{"code": "z", "params": {}}, {"code": "a", "params": {"n": 1}}],
    )
    normal = normalise(document)
    assert normal["requires"] == [["conn:nTP-v1"], ["conn:nTP-v1", "x:acme.b"], ["phase:L:2"]]
    assert normal["provides"] == ["x:acme.a", "x:acme.p:3"]
    assert normal["implementation"]["modules"] == ["a.py", "b.py"]
    assert [entry["code"] for entry in normal["limitations"]] == ["a", "z"]
    # The hash is of the normal form without `status`, so spelling, order and status do not move it.
    shuffled = copy.deepcopy(document)
    shuffled["requires"].reverse()
    shuffled["provides"].reverse()
    shuffled["status"] = "released"
    assert descriptor_sha256(shuffled) == descriptor_sha256(document)
    without_status = {key: value for key, value in normal.items() if key != "status"}
    independent = json.dumps(without_status, sort_keys=True, separators=(",", ":"))
    assert descriptor_sha256(document) == hashlib.sha256(independent.encode()).hexdigest()


def test_d4_token_grammar_levels_and_satisfaction() -> None:
    assert parse("vocab:h:2") == ("vocab", "h", 2)
    assert parse("conn:nTP-v1").level == 0
    assert normalise_provides(["conn:a:0"]) == ("conn:a",)
    for bad in ("conn:", "Conn:a", "conn:a:01", "conn:a:-1", "conn:.a", "conn:a:1:2"):
        with pytest.raises(ValueError):
            parse(bad)

    def everything(_: object) -> bool:
        return True

    assert satisfied("x:acme.h:1", ["x:acme.h:2"], everything)
    assert satisfied("x:acme.h:2", ["x:acme.h:2"], everything)
    assert not satisfied("x:acme.h:3", ["x:acme.h:2"], everything)
    assert not satisfied("x:acme.h", ["x:acme.g:5"], everything)
    assert not satisfied("x:acme.h", ["x:acme.h"], lambda _: False)


@pytest.mark.parametrize(
    ("token", "providing", "builtin", "namespace", "code"),
    [
        ("nope:a", False, True, None, "capability_unknown"),
        ("flash:PH", False, True, None, "capability_unknown"),
        ("convention:SYN-001-ref-v1", False, False, "acme", None),
        ("vocab:h", True, True, None, "capability_unknown"),
        ("legacy:syn001", True, True, None, None),
        ("legacy:not-a-provider", False, True, None, "capability_unknown"),
        ("legacy:syn001", True, False, "acme", "reserved_capability"),
        ("legacy:pr-c1-v1", False, False, "acme", "reserved_capability"),
        ("x:acme.f", True, False, "acme", None),
        ("x:other.f", True, False, "acme", "reserved_capability"),
        ("x:other.f", False, False, "acme", None),
        ("x:acme.f", True, True, None, "reserved_capability"),
        ("x:nonamespace", False, False, "acme", "capability_unknown"),
        ("conn:acme.slurry", False, False, "acme", None),
        ("phase:1L", False, False, "acme", "capability_unknown"),
    ],
)
def test_d4_token_validation(
    token: str, providing: bool, builtin: bool, namespace: str | None, code: str | None
) -> None:
    found = token_problem(token, providing=providing, builtin=builtin, namespace=namespace)
    assert (None if found is None else found.code) == code
    if found is not None:
        assert dict(found.params) == {"token": parse(token).spelling}


# ---------------------------------------------------------------------------------------------
# D3 self-hash


def test_d3_self_hash_is_recomputed_independently_and_ignores_crlf(tmp_path: Path) -> None:
    modules = ["synth_ext/kernel.py", "synth_ext/data.json", "synth_ext/__init__.py"]
    rows = [
        [path, hashlib.sha256((SYNTHETIC_ROOT / path).read_bytes()).hexdigest()]
        for path in sorted(modules)
    ]
    independent = hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
    assert compute_self_sha256(SYNTHETIC_ROOT, modules) == independent
    assert compute_self_sha256(SYNTHETIC_ROOT, reversed(modules)) == independent
    assert compute_self_sha256(SYNTHETIC_ROOT, []) == EMPTY_SET_SHA
    # A CRLF copy of every module in a temporary import root hashes the same (E-F1-4's control).
    for path in modules:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SYNTHETIC_ROOT / path).read_bytes().replace(b"\n", b"\r\n"))
    assert b"\r\n" in (tmp_path / "synth_ext" / "kernel.py").read_bytes()
    assert compute_self_sha256(tmp_path, modules) == independent
    # A lone CR is not a line ending D3 normalises.
    (tmp_path / "synth_ext" / "kernel.py").write_bytes(b"a\rb")
    assert compute_self_sha256(tmp_path, modules) != independent
    with pytest.raises(SelfHashUnavailableError) as raised:
        compute_self_sha256(SYNTHETIC_ROOT, ["synth_ext/missing.py"])
    assert raised.value.path == "synth_ext/missing.py"
    with pytest.raises(SelfHashUnavailableError):
        compute_self_sha256(SYNTHETIC_ROOT, ["synth_ext"])  # a directory is not a regular file


def test_d3_v2_implementation_sha256_formula() -> None:
    a, b = "a" * 64, "b" * 64
    expected = hashlib.sha256(json.dumps([a, b], separators=(",", ":")).encode()).hexdigest()
    assert implementation_sha256(a, b) == expected


# ---------------------------------------------------------------------------------------------
# Build, closing, quarantine


def test_the_built_registry_is_closed_and_sorted() -> None:
    registry = _build()
    assert registry.closed
    with pytest.raises(RuntimeError, match="^registry_closed$"):
        registry.register(registry.descriptors()[0])
    keys = [(e.kind, e.id) for e in registry.descriptors()]
    assert keys == sorted(keys)
    assert registry.resolve("unit_model", "syn001.pump").self_sha256 != EMPTY_SET_SHA
    assert registry.resolve("unit_model", "syn001.cascade").self_sha256 == EMPTY_SET_SHA
    with pytest.raises(KeyError):
        registry.resolve("unit_model", "syn001.absent")


def test_admission_on_the_synthetic_built_ins() -> None:
    registry = _build()
    verdicts = {
        (v.unit.id, v.method.id): (v.admission.admitted, v.admission.refusal)
        for v in registry.admission_matrix("nTP-v1")
    }
    assert verdicts == {
        ("syn001.cascade", "syn001"): (
            False,
            Coded("model_unsupported", {"model": "syn001.cascade"}),
        ),
        ("syn001.cascade", "wilson-ig-v2"): (
            False,
            Coded("model_unsupported", {"model": "syn001.cascade"}),
        ),
        ("syn001.flash", "syn001"): (True, None),
        ("syn001.flash", "wilson-ig-v2"): (True, None),
        ("syn001.pump", "syn001"): (True, None),
        ("syn001.pump", "wilson-ig-v2"): (
            False,
            Coded(
                "capability_missing",
                {"unit": "syn001.pump", "method": "wilson-ig-v2", "capability": "legacy:syn001"},
            ),
        ),
    }
    flash = registry.admit("syn001.flash", "wilson-ig-v2", "nTP-v1")
    assert flash.notices == ()  # every descriptor of the triple is released and legacy-form core


def test_a_package_is_registered_whole_with_its_computed_fields() -> None:
    registry = _build(packages=[_acme()])
    unit = registry.resolve("unit_model", "acme.unit")
    assert (unit.origin, unit.distribution, unit.entry_point) == ("installed", "acme-dist", "acme")
    assert (unit.evidence_class, unit.stability) == ("unreviewed", "preview")
    assert registry.resolve("unit_model", "acme.agent_unit").origin == "contributed"
    admission = registry.admit("acme.unit", "acme.method", "nTP-v1")
    assert admission.admitted
    assert [n.as_document() for n in admission.notices] == [
        {"code": "extension_unreviewed", "params": {"id": "acme.method", "origin": "installed"}},
        {"code": "extension_unreviewed", "params": {"id": "acme.unit", "origin": "installed"}},
        {"code": "preview_kind", "params": {"kind": "property_method", "id": "acme.method"}},
        {"code": "preview_kind", "params": {"kind": "unit_model", "id": "acme.unit"}},
    ]
    document = unit.as_document()
    assert document["descriptor_sha256"] == unit.descriptor_sha256
    assert "unresolved" not in document


def test_an_unregistered_name_is_never_satisfied_and_is_flagged() -> None:
    """D4: `conn:nTP-v1 | conn:acme.slurry` without `acme.slurry` registered is admitted on
    `nTP-v1` with `capability_unresolved(conn:acme.slurry)`; a unit needing only the unregistered
    name is refused, with the same notice."""
    either = _descriptor(
        "unit_model", "beta.either", requires=[["conn:nTP-v1", "conn:acme.slurry"]]
    )
    only = _descriptor("unit_model", "beta.only", requires=[["conn:acme.slurry"]])
    claim = _descriptor(
        "property_method", "beta.method", provides=["conn:nTP-v1", "conn:acme.slurry"]
    )
    registry = _build(packages=[_package("beta", [either, only, claim])])
    flag = Coded("capability_unresolved", {"token": "conn:acme.slurry"})
    admitted = registry.admit("beta.either", "syn001", "nTP-v1")
    assert admitted.admitted and flag in admitted.notices
    refused = registry.admit("beta.only", "beta.method", "nTP-v1")
    assert not refused.admitted and refused.notices == (flag,)
    assert refused.refusal == Coded(
        "capability_missing",
        {"unit": "beta.only", "method": "beta.method", "capability": "conn:acme.slurry"},
    )


QUARANTINES: tuple[tuple[str, dict[str, Any], Coded], ...] = (
    (
        "schema",
        {"title": ""},
        Coded("extension_invalid", {"entry_point": "bad", "pointer": "/descriptors/0/title"}),
    ),
    (
        "namespace prefix",
        {"id": "other.unit"},
        Coded("extension_invalid", {"entry_point": "bad", "pointer": "/descriptors/0/id"}),
    ),
    (
        "static name",
        {"requires": [["flash:PQ"]]},
        Coded("capability_unknown", {"token": "flash:PQ"}),
    ),
    (
        "legacy provided",
        {"provides": ["legacy:syn001"]},
        Coded("reserved_capability", {"token": "legacy:syn001"}),
    ),
    (
        "legacy required",
        {"requires": [["legacy:pr-c1-v1"]]},
        Coded("reserved_capability", {"token": "legacy:pr-c1-v1"}),
    ),
    (
        "x outside the namespace",
        {"provides": ["x:acme.surface"]},
        Coded("reserved_capability", {"token": "x:acme.surface"}),
    ),
    (
        "missing self-hash file",
        {"implementation": {"modules": ["synth_ext/missing.py"], "factory": None}},
        Coded("self_hash_unavailable", {"id": "bad.unit", "path": "synth_ext/missing.py"}),
    ),
)


@pytest.mark.parametrize(("why", "change", "reason"), QUARANTINES, ids=[q[0] for q in QUARANTINES])
def test_a_bad_package_is_quarantined_alone(
    why: str, change: dict[str, Any], reason: Coded
) -> None:
    good = _descriptor("unit_model", "bad.good", requires=[["conn:nTP-v1"]])
    bad = _descriptor("unit_model", "bad.unit", **change)
    clean = _build(packages=[_acme()])
    registry = _build(packages=[_package("bad", [bad, good]), _acme()])
    assert [record.reason for record in registry.quarantined] == [reason], why
    assert [record.as_document() for record in registry.quarantined] == [
        {"distribution": "bad-dist", "distribution_version": "1.2.3", "entry_point": "bad"}
        | reason.as_document()
    ]
    # Atomic: nothing of `bad` is registered, and `acme` is as if `bad` were absent.
    assert registry.registry_sha256 == clean.registry_sha256
    assert registry.snapshot()["extensions"] == clean.snapshot()["extensions"]
    assert schema_errors("registry-snapshot.schema.json", registry.snapshot()) == []


def test_a_bad_built_in_fails_the_build() -> None:
    for change, code in (
        ({"requires": [["vocab:h"]]}, "capability_unknown"),
        ({"provides": ["x:acme.f"]}, "reserved_capability"),
        (
            {"implementation": {"modules": ["synth_ext/none.py"], "factory": None}},
            "self_hash_unavailable",
        ),
        ({"version": "1.0"}, "extension_invalid"),
    ):
        tables = _tables()
        tables["core"].append(_descriptor("unit_model", "std.bad", **change))
        with pytest.raises(RegistryBuildError) as raised:
            _build(builtin_tables=tables)
        assert raised.value.reason.code == code
    tables = _tables()
    tables["core"].append(_descriptor("connection_definition", "std.def", provides=[]))
    with pytest.raises(RegistryBuildError, match="/provides"):
        _build(builtin_tables=tables)


# ---------------------------------------------------------------------------------------------
# E-F1-5 Determinism (synthetic built-ins)

_PRINT_SHA = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "from openflowsheet.registry import Registry\n"
    "root = Path(sys.argv[1])\n"
    "tables = json.loads((root / 'builtin.json').read_text(encoding='utf-8'))\n"
    "registry = Registry.build(builtin_tables=tables, builtin_root=root / 'root')\n"
    "print(registry.registry_sha256)\n"
)


def _fresh_process_sha(seed: str) -> str:
    environment = dict(os.environ, PYTHONHASHSEED=seed)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), *filter(None, [environment.get("PYTHONPATH")])]
    )
    completed = subprocess.run(
        [sys.executable, "-c", _PRINT_SHA, str(SYNTHETIC)],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_e_f1_5_registry_sha256_is_the_same_in_fresh_processes_and_equals_the_constant() -> None:
    committed = CONSTANT.read_text(encoding="utf-8").strip()
    assert len(committed) == 64
    assert _fresh_process_sha("0") == committed
    assert _fresh_process_sha("random") == committed
    assert _fresh_process_sha("random") == committed
    assert _build().registry_sha256 == committed


def test_e_f1_5_registry_sha256_is_recomputed_independently() -> None:
    registry = _build()
    rows = []
    for table in _tables().values():
        for document in table:
            normal = normalise(document)
            del normal["status"]
            digest = hashlib.sha256(
                json.dumps(normal, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            files = sorted(document["implementation"]["modules"])
            selfs = [
                [p, hashlib.sha256((SYNTHETIC_ROOT / p).read_bytes()).hexdigest()] for p in files
            ]
            own = hashlib.sha256(json.dumps(selfs, separators=(",", ":")).encode()).hexdigest()
            version = tuple(int(part) for part in document["version"].split("."))
            rows.append(
                (
                    (document["kind"], document["id"], version),
                    [document["kind"], document["id"], document["version"], digest, own],
                )
            )
    ordered = [row for _, row in sorted(rows)]
    expected = hashlib.sha256(json.dumps(ordered, separators=(",", ":")).encode()).hexdigest()
    assert registry.registry_sha256 == expected
    assert registry.snapshot()["registry_sha256"] == expected


def test_e_f1_5_input_order_is_irrelevant() -> None:
    reference = _build()
    shuffle = random.Random(5)
    for _ in range(5):
        tables = _tables()
        for entries in tables.values():
            shuffle.shuffle(entries)
            for entry in entries:
                for clause in entry["requires"]:
                    clause.reverse()
                entry["requires"].reverse()
                entry["provides"].reverse()
        names = list(tables)
        shuffle.shuffle(names)
        built = _build(builtin_tables={name: tables[name] for name in names})
        assert built.snapshot() == reference.snapshot()
    two = _build(packages=[_acme(), _package("beta", [_descriptor("unit_model", "beta.u")])])
    owt = _build(packages=[_package("beta", [_descriptor("unit_model", "beta.u")]), _acme()])
    assert json.dumps(two.snapshot()) == json.dumps(owt.snapshot())


def test_e_f1_5_registry_sha256_excludes_evidence_and_distribution_versions() -> None:
    reference = _build(packages=[_acme()])
    other = Registry.build(
        builtin_tables=_tables(),
        builtin_root=SYNTHETIC_ROOT,
        builtin_version="9.9.9",
        packages=[_acme()],
    )
    assert other.registry_sha256 == reference.registry_sha256
    assert other.snapshot() != reference.snapshot()


# ---------------------------------------------------------------------------------------------
# E-F1-8 Evidence non-interference


def _observables(registry: Registry) -> dict[str, Any]:
    """What evidence must not move: hashes and verdicts; and what it may: evidence and notices."""
    definition = "nTP-v1"
    matrix = registry.admission_matrix(definition)
    return {
        "registry_sha256": registry.registry_sha256,
        "descriptor_sha256": {(e.kind, e.id): e.descriptor_sha256 for e in registry.descriptors()},
        "self_sha256": {(e.kind, e.id): e.self_sha256 for e in registry.descriptors()},
        "verdicts": [
            (v.unit.id, v.method.id, v.admission.admitted, v.admission.refusal) for v in matrix
        ],
        "evidence": {
            (e.kind, e.id): (e.effective_status, e.evidence_class) for e in registry.descriptors()
        },
        "notices": [(v.unit.id, v.method.id, v.admission.notices) for v in matrix],
    }


def _with_status(package: ExtensionPackage, identifier: str, status: str) -> ExtensionPackage:
    document = copy.deepcopy(package.document)
    assert isinstance(document, dict)
    for descriptor in document["descriptors"]:
        if descriptor["id"] == identifier:
            descriptor["status"] = status
    return ExtensionPackage(
        package.distribution,
        package.distribution_version,
        package.entry_point,
        package.import_root,
        document,
    )


def _attestation(registry: Registry, kind: str, identifier: str) -> Attestation:
    entry = registry.resolve(kind, identifier)
    return Attestation(entry.id, entry.version, entry.descriptor_sha256, entry.self_sha256)


def _only_evidence_moved(before: dict[str, Any], after: dict[str, Any]) -> None:
    for fixed in ("registry_sha256", "descriptor_sha256", "self_sha256", "verdicts"):
        assert after[fixed] == before[fixed], fixed
    assert after["evidence"] != before["evidence"] or after["notices"] != before["notices"]


def test_e_f1_8_a_built_in_status_change_moves_only_evidence() -> None:
    before = _observables(_build(packages=[_acme()]))
    tables = _tables()
    for entry in tables["legacy"]:
        if entry["id"] == "wilson-ig-v2":
            entry["status"] = "tested"
    after = _observables(_build(builtin_tables=tables, packages=[_acme()]))
    _only_evidence_moved(before, after)
    assert after["evidence"][("property_method", "wilson-ig-v2")] == ("tested", "unreviewed")
    flagged = Coded("extension_unreviewed", {"id": "wilson-ig-v2", "origin": "builtin"})
    # Exactly the admitted pairs that use it carry the flag; refused pairs carry no evidence.
    assert [(u, m) for u, m, notices in after["notices"] if flagged in notices] == [
        ("acme.agent_unit", "wilson-ig-v2"),
        ("syn001.flash", "wilson-ig-v2"),
    ]


def test_e_f1_8_an_installed_status_is_capped_without_an_attestation() -> None:
    before = _observables(_build(packages=[_acme()]))
    claimed = _with_status(_acme(), "acme.unit", "released")
    after = _observables(_build(packages=[claimed]))
    for fixed in ("registry_sha256", "descriptor_sha256", "self_sha256", "verdicts", "notices"):
        assert after[fixed] == before[fixed], fixed
    assert before["evidence"][("unit_model", "acme.unit")] == ("declared", "unreviewed")
    assert after["evidence"][("unit_model", "acme.unit")] == ("tested", "unreviewed")


def test_e_f1_8_an_attestation_moves_only_evidence_and_only_when_it_matches() -> None:
    claimed = _with_status(_acme(), "acme.unit", "released")
    plain = _build(packages=[claimed])
    before = _observables(plain)
    attestation = _attestation(plain, "unit_model", "acme.unit")
    attested = _build(packages=[claimed], attestations=[attestation])
    after = _observables(attested)
    _only_evidence_moved(before, after)
    assert after["evidence"][("unit_model", "acme.unit")] == ("released", "reviewed")
    notices = attested.admit("acme.unit", "acme.method", "nTP-v1").notices
    assert Coded("extension_unreviewed", {"id": "acme.unit", "origin": "installed"}) not in notices
    assert Coded("preview_kind", {"kind": "unit_model", "id": "acme.unit"}) in notices
    # An attestation of other code or of another descriptor counts for nothing.
    for stale in (
        Attestation(attestation.id, attestation.version, attestation.descriptor_sha256, "0" * 64),
        Attestation(attestation.id, attestation.version, "0" * 64, attestation.self_sha256),
        Attestation(
            attestation.id, "2.0.0", attestation.descriptor_sha256, attestation.self_sha256
        ),
    ):
        assert _observables(_build(packages=[claimed], attestations=[stale])) == before


# ---------------------------------------------------------------------------------------------
# E-F1-9 Token semantics [gen]

#: The random universe. `conn:C`, `phase:V` and `x:acme.q` are never registered; static names are
#: valid ones.
RESOLVED = {("conn", "A"), ("conn", "B"), ("phase", "L"), ("x", "acme.p")}
NAMES = (
    ("conn", "A"),
    ("conn", "B"),
    ("conn", "C"),
    ("phase", "L"),
    ("phase", "V"),
    ("flash", "TP"),
    ("convention", "SYN-001-ref-v1"),
    ("x", "acme.p"),
    ("x", "acme.q"),
)


def _brute_parse(token: str) -> tuple[str, str, int]:
    space, name, *level = token.split(":")
    return space, name, int(level[0]) if level else 0


def _brute_spelling(token: str) -> str:
    space, name, level = _brute_parse(token)
    return f"{space}:{name}" + (f":{level}" if level else "")


def _brute_resolved(token: str) -> bool:
    space, name, _ = _brute_parse(token)
    return space in ("flash", "convention", "vocab", "legacy") or (space, name) in RESOLVED


def _brute_satisfied(token: str, provisions: Sequence[str]) -> bool:
    space, name, level = _brute_parse(token)
    return _brute_resolved(token) and any(
        _brute_parse(p)[:2] == (space, name) and _brute_parse(p)[2] >= level for p in provisions
    )


def _brute_clauses(requires: Sequence[Sequence[str]]) -> list[list[str]]:
    clauses = {tuple(sorted({_brute_spelling(t) for t in clause})) for clause in requires}
    return [list(clause) for clause in sorted(clauses)]


def _brute_provides(document: Mapping[str, Any]) -> list[str]:
    best: dict[tuple[str, str], int] = {}
    for space, name, level in map(_brute_parse, document["provides"]):
        best[(space, name)] = max(level, best.get((space, name), 0))
    return [f"{s}:{n}" + (f":{lvl}" if lvl else "") for (s, n), lvl in best.items()]


def _brute_admit(
    unit: Mapping[str, Any], method: Mapping[str, Any], definition: Mapping[str, Any]
) -> tuple[bool, dict[str, Any] | None, list[dict[str, Any]]]:
    """D5, transcribed from ADR 0060 over the raw (unnormalised) declared documents."""
    # The tokens each descriptor names, in its normal form (D2): the registry stores that form,
    # so two spellings of one descriptor carry the same notices.
    tokens = [
        t
        for d in (unit, method, definition)
        for t in [*(t for c in _brute_clauses(d["requires"]) for t in c), *_brute_provides(d)]
    ]
    flags = sorted({t for t in tokens if not _brute_resolved(t)})
    notices = [{"code": "capability_unresolved", "params": {"token": t}} for t in flags]

    def refuse(capability: str) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
        params = {"unit": unit["id"], "method": method["id"], "capability": capability}
        return False, {"code": "capability_missing", "params": params}, notices

    if unit["payload"].get("bindable") is False:
        return False, {"code": "model_unsupported", "params": {"model": unit["id"]}}, notices
    p_m, p_d = method["provides"], definition["provides"]
    if not _brute_satisfied(f"conn:{definition['id']}", p_m):
        return refuse(f"conn:{definition['id']}")
    for clause in _brute_clauses(unit["requires"]):
        if not any(
            _brute_satisfied(t, p_d if t.startswith("conn:") else [*p_m, *p_d]) for t in clause
        ):
            return refuse("|".join(clause))
    for clause in _brute_clauses(method["requires"]):
        if not any(_brute_satisfied(t, p_d) for t in clause):
            return refuse("|".join(clause))
    evidence = []
    for d, entry in ((unit, "u"), (method, "m"), (definition, "d")):
        if d["_evidence_class"] == "unreviewed":
            evidence.append(
                {"code": "extension_unreviewed", "params": {"id": d["id"], "origin": entry}}
            )
        if d["_stability"] == "preview":
            evidence.append({"code": "preview_kind", "params": {"kind": d["kind"], "id": d["id"]}})
    every = {json.dumps(n, sort_keys=True): n for n in [*evidence, *notices]}
    ordered = sorted(every.values(), key=lambda n: (n["code"], sorted(n["params"].items())))
    return True, None, ordered


def _random_token(rng: random.Random) -> str:
    space, name = rng.choice(NAMES)
    level = rng.choice((None, 0, 0, 1, 2, 3))
    return f"{space}:{name}" if level is None else f"{space}:{name}:{level}"


def _random_requires(rng: random.Random) -> list[list[str]]:
    return [
        [_random_token(rng) for _ in range(rng.randint(1, 3))] for _ in range(rng.randint(0, 3))
    ]


def _random_triple(rng: random.Random) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    def evidence(document: dict[str, Any]) -> dict[str, Any]:
        document["_evidence_class"] = rng.choice(("core", "reviewed", "unreviewed"))
        document["_stability"] = rng.choice(("core", "preview"))
        return document

    definition_id = rng.choice(("A", "B"))
    definition = _descriptor(
        "connection_definition",
        definition_id,
        provides=[f"conn:{definition_id}", *(_random_token(rng) for _ in range(rng.randint(0, 2)))],
    )
    supported = [f"conn:{definition_id}"] if rng.random() < 0.6 else []
    method = _descriptor(
        "property_method",
        "M",
        provides=[*supported, *(_random_token(rng) for _ in range(rng.randint(0, 4)))],
        requires=_random_requires(rng),
    )
    unit = _descriptor(
        "unit_model",
        "U",
        requires=_random_requires(rng),
        provides=[_random_token(rng) for _ in range(rng.randint(0, 1))],
        payload={"bindable": rng.random() > 0.05},
    )
    return evidence(unit), evidence(method), evidence(definition)


def _registered_for(document: Mapping[str, Any], origin: str) -> Registered:
    """A registered descriptor built directly (10⁴ registry builds would be slow): the normal
    form, and `unresolved` from the fixed universe."""
    declared = {key: value for key, value in document.items() if not key.startswith("_")}
    normal = normalise(declared)
    tokens = {t for clause in normal["requires"] for t in clause} | set(normal["provides"])
    return Registered(
        document=normal,
        descriptor_sha256=descriptor_sha256(declared),
        self_sha256=EMPTY_SET_SHA,
        origin=origin,
        distribution="test",
        distribution_version="0",
        entry_point=None,
        effective_status="declared",
        evidence_class=document["_evidence_class"],
        stability=document["_stability"],
        unresolved=tuple(sorted(t for t in tokens if not _brute_resolved(t))),
    )


def _admit_documents(
    unit: Mapping[str, Any], method: Mapping[str, Any], definition: Mapping[str, Any]
) -> tuple[bool, dict[str, Any] | None, list[dict[str, Any]]]:
    admission = admit(
        _registered_for(unit, "u"), _registered_for(method, "m"), _registered_for(definition, "d")
    )
    document = admission.as_document()
    return document["admitted"], document["refusal"], document["notices"]


def test_e_f1_9_admit_equals_brute_force_d5_over_random_triples() -> None:
    rng = random.Random(20261111)
    outcomes: dict[str, int] = {}
    for _ in range(10_000):
        unit, method, definition = _random_triple(rng)
        expected = _brute_admit(unit, method, definition)
        assert _admit_documents(unit, method, definition) == expected, (unit, method, definition)
        key = "admitted" if expected[0] else str(expected[1]["code"] if expected[1] else None)
        outcomes[key] = outcomes.get(key, 0) + 1
    # The generator must reach every branch, or the comparison proves little.
    assert set(outcomes) == {"admitted", "capability_missing", "model_unsupported"}
    assert min(outcomes.values()) >= 200, outcomes


def test_e_f1_9_raising_a_provided_level_never_refuses_an_admission() -> None:
    rng = random.Random(9)
    checked = 0
    for _ in range(10_000):
        unit, method, definition = _random_triple(rng)
        if not _admit_documents(unit, method, definition)[0]:
            continue
        for document in (method, definition):
            document["provides"] = [
                f"{s}:{n}:{lvl + rng.randint(0, 3)}"
                for s, n, lvl in map(_brute_parse, document["provides"])
            ]
        assert _admit_documents(unit, method, definition)[0], (unit, method, definition)
        checked += 1
    assert checked >= 500  # 694 admitted triples of 10⁴ with this seed


def test_e_f1_9_normalisation_is_idempotent() -> None:
    rng = random.Random(77)
    for _ in range(10_000):
        for document in _random_triple(rng):
            declared = {k: v for k, v in document.items() if not k.startswith("_")}
            once = normalise(declared)
            assert normalise(once) == once
            assert descriptor_sha256(once) == descriptor_sha256(declared)
            assert normalise_requires(once["requires"]) == tuple(map(tuple, once["requires"]))


def test_e_f1_9_fixed_counterexample_a_conn_requirement_is_the_definitions_alone() -> None:
    """W1 P1 review, finding 1: M supports A and B, U accepts only A; U on B is refused."""
    tables = {
        "core": [
            _descriptor("connection_definition", "std.A", provides=["conn:std.A"]),
            _descriptor("connection_definition", "std.B", provides=["conn:std.B"]),
            _descriptor("property_method", "std.M", provides=["conn:std.A", "conn:std.B"]),
            _descriptor("unit_model", "std.U", requires=[["conn:std.A"]]),
        ]
    }
    registry = _build(builtin_tables=tables)
    assert registry.admit("std.U", "std.M", "std.A").admitted
    refused = registry.admit("std.U", "std.M", "std.B")
    assert refused.refusal == Coded(
        "capability_missing", {"unit": "std.U", "method": "std.M", "capability": "conn:std.A"}
    )
