"""F3-WO4: the data lock and the rights register (ADR 0061 D10, D11, D5's matching).

E-F3-7 (data lock) in full: permuting `parameter_sets` or `methods` leaves `data_lock_sha256`,
permuting `components` changes it, the committed fixture lock's SHA equals
`tests/fixtures/records/data-lock-sha256.txt`, an absent record is `data_unavailable` and an
unmatched set key `parameter_set_component_missing`. E-F3-5 (rights): assessments in both layers
leave every record SHA and `data_lock_sha256`; D11's four precedence rows each decide one fixture;
`assess_rights` under the default agent grant waits for F3-WO5's operations. The repository
register's seed rows are held to D11's reading of the v1 `redistribution` texts, which are
written out here from the files, and to the legacy import (`--check`).

Records here are built in the test (every value invented, the InChIKey spelling apart). The
fixture lock's SHA is computed in the test by an independent route (`json.dumps`, sorted keys, no
whitespace, UTF-8), never taken from `records.lock`.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator

from openflowsheet.records import identify, rights
from openflowsheet.records.importers import legacy
from openflowsheet.records.lock import (
    DataLockError,
    build_lock,
    data_lock_sha256,
    implementation_sha256,
    method_entry,
)
from openflowsheet.records.rights import Effective
from openflowsheet.records.stack import LegacyStore, StoreStack
from openflowsheet.records.store import RecordStore
from openflowsheet.registry import default_registry

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import records_legacy_index  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "records"
LOCK_FIXTURE = FIXTURES / "data-lock.json"
LOCK_SHA = FIXTURES / "data-lock-sha256.txt"
WATER_KEY = "XLYOFNOQVPJJNP-UHFFFAOYSA-N"


def _component(ident: str, *, source: str = "fixture.lock", **ids: str) -> dict[str, Any]:
    """A valid `mol` component, synthetic when it has no identifiers."""
    record: dict[str, Any] = {
        "record_format": "openflowsheet-record-v2",
        "record_type": "component",
        "type_version": "1.0.0",
        "id": ident,
        "name": f"fixture component {ident}",
        "sources": {source: {"version": "1"}},
        "synthetic": not ids,
        "amount_basis": "mol",
        "charge": 0,
        "elemental_verification": "NOT_APPLICABLE",
        "molar_mass": {
            "value": 0.05,
            "unit": "kg/mol",
            "kind": "molar_mass",
            "provenance": {"origin": ["measured"], "derivation": "direct", "source": source},
        },
    }
    if ids:
        record["identifiers"] = ids
    return record


def _parameter_set(ident: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_format": "openflowsheet-record-v2",
        "record_type": "parameter_set",
        "type_version": "1.0.0",
        "id": ident,
        "name": ident,
        "sources": {"fixture.lock": {"version": "1"}},
        "synthetic": True,
        "components": components,
        "entries": [],
    }


def _register(store: RecordStore | StoreStack, record: dict[str, Any]) -> str:
    outcome = identify(record)
    assert outcome.errors == (), outcome.errors
    return store.register(outcome, principal="tester").record_sha256


#: Three method rows: the version key orders 1.2.0 before 1.10.0 (a string sort would not).
METHODS = [
    {
        "substream": "liquid",
        "method": "fixture.wilson",
        "version": "1.10.0",
        "implementation_sha256": "1" * 64,
    },
    {
        "substream": "gas",
        "method": "fixture.ideal",
        "version": "1.0.0",
        "implementation_sha256": "2" * 64,
    },
    {
        "substream": "liquid",
        "method": "fixture.wilson",
        "version": "1.2.0",
        "implementation_sha256": "3" * 64,
    },
]
OPTIONS = {"fixture.wilson": {"tolerance": 0.5, "label": "Λ fixture"}}


def _fixture() -> tuple[StoreStack, list[tuple[str, str]], list[str]]:
    """A project store holding two components (one carrying an InChIKey) and two parameter sets
    matching them by SHA and by InChIKey; the revision's (id, SHA) pairs in revision order and the
    sets' SHAs."""
    stack = StoreStack(RecordStore.in_memory())
    a = _register(stack, _component("A"))
    water = _register(stack, _component("W", inchikey=WATER_KEY))
    by_sha = _register(stack, _parameter_set("set-by-sha", [{"key": "A", "match": {"record": a}}]))
    by_key = _register(
        stack, _parameter_set("set-by-inchikey", [{"key": "W", "match": {"inchikey": WATER_KEY}}])
    )
    return stack, [("solvent", a), ("feed-water", water)], [by_sha, by_key]


def _independent_sha256(document: Any) -> str:
    """The SHA-256 of `document`'s JSON with sorted keys and no whitespace, in UTF-8: canonical
    JSON for a document of strings, objects, arrays and short decimal numbers (ADR 0002 D3)."""
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -------------------------------------------------------------------------- E-F3-7 data lock


def test_e_f3_7_permuting_sets_or_methods_leaves_the_sha_and_components_change_it() -> None:
    stack, components, sets = _fixture()
    lock = build_lock(components, sets, METHODS, OPTIONS, stack)
    sha = data_lock_sha256(lock)
    assert lock["parameter_sets"] == sorted(sets)
    assert [(m["substream"], m["version"]) for m in lock["methods"]] == [
        ("gas", "1.0.0"),
        ("liquid", "1.2.0"),
        ("liquid", "1.10.0"),
    ]
    shuffled = random.Random(4).sample(METHODS, k=len(METHODS))
    assert data_lock_sha256(build_lock(components, sets[::-1], METHODS, OPTIONS, stack)) == sha
    assert data_lock_sha256(build_lock(components, sets, shuffled, OPTIONS, stack)) == sha
    assert data_lock_sha256(build_lock(components, sets, METHODS[::-1], OPTIONS, stack)) == sha
    swapped = build_lock(components[::-1], sets, METHODS, OPTIONS, stack)
    assert swapped["components"] == [{"id": i, "record": s} for i, s in components[::-1]]
    assert data_lock_sha256(swapped) != sha


def test_e_f3_7_the_committed_fixture_locks_sha() -> None:
    """The committed lock's SHA (`document_sha256`) equals the committed text on every leg, the
    text is the independent route's SHA of the committed document, the document is
    `data-lock.schema.json`-valid, and `build_lock` rebuilds it from the fixture's inputs."""
    document = json.loads(LOCK_FIXTURE.read_text(encoding="utf-8"))
    expected = LOCK_SHA.read_text(encoding="utf-8").strip()
    assert data_lock_sha256(document) == expected
    assert _independent_sha256(document) == expected
    schema = json.loads((REPO_ROOT / "schemas" / "data-lock.schema.json").read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    assert list(Draft202012Validator(schema).iter_errors(document)) == []
    stack, components, sets = _fixture()
    assert build_lock(components, sets, METHODS, OPTIONS, stack) == document


def test_e_f3_7_an_absent_record_is_data_unavailable() -> None:
    stack, components, sets = _fixture()
    absent = "f" * 64
    for args in (
        ([*components, ("ghost", absent)], sets),
        (components, [*sets, absent]),
    ):
        with pytest.raises(DataLockError) as caught:
            build_lock(*args, METHODS, OPTIONS, stack)
        assert caught.value.coded is not None
        assert (caught.value.coded.code, dict(caught.value.coded.params)) == (
            "data_unavailable",
            {"sha": absent},
        )


def test_e_f3_7_an_unmatched_set_key_is_parameter_set_component_missing() -> None:
    """D5: a set matched by SHA needs that record bound; one matched by InChIKey needs a bound
    record carrying it."""
    stack, components, sets = _fixture()
    for kept, set_id, key in (
        (components[1:], "set-by-sha", "A"),
        (components[:1], "set-by-inchikey", "W"),
    ):
        with pytest.raises(DataLockError) as caught:
            build_lock(kept, sets, METHODS, OPTIONS, stack)
        assert caught.value.coded is not None
        assert (caught.value.coded.code, dict(caught.value.coded.params)) == (
            "parameter_set_component_missing",
            {"set": set_id, "key": key},
        )


def test_d10_inputs_off_the_shape_are_refused_uncoded() -> None:
    stack, components, sets = _fixture()
    bad: list[tuple[Any, ...]] = [
        ([*components, ("solvent", components[1][1])], sets, METHODS, OPTIONS),
        (components, sets, [*METHODS, METHODS[0]], OPTIONS),
        (components, sets, METHODS, {**OPTIONS, "fixture.other": {}}),
        ([("set", sets[0])], [], [], {}),
        (components, [components[0][1]], [], {}),
    ]
    for args in bad:
        with pytest.raises(DataLockError) as caught:
            build_lock(*args, stack)
        assert caught.value.coded is None


def test_d8_a_lock_copies_the_legacy_records_it_names_into_the_project_store() -> None:
    """D8 (review item 20): the legacy records a lock names are copied into the project store;
    a refused lock copies nothing. On the `s10` records and their parameter set (matched by SHA)."""
    entry = next(e for e in legacy.committed_index()["files"] if e["profile"] == "s10")
    shas = [(r["id"], r["sha256"]) for r in entry["records"] if r["record_type"] == "component"]
    (set_sha,) = [r["sha256"] for r in entry["records"] if r["record_type"] == "parameter_set"]
    stack = StoreStack(RecordStore.in_memory(), LegacyStore(legacy.available_records))
    with pytest.raises(DataLockError):
        build_lock(shas[1:], [set_sha], [], {}, stack)
    assert stack.project.objects() == []
    lock = build_lock(shas, [set_sha], [], {}, stack)
    assert lock["components"] == [{"id": i, "record": s} for i, s in shas]
    assert {row.sha for row in stack.project.objects()} == {s for _, s in shas} | {set_sha}


def test_d10_implementation_sha256_of_a_registered_method() -> None:
    """D10, ADR 0060 D3: `sha256(canonical_json([descriptor_sha256, self_sha256]))`."""
    (method, *_) = default_registry().descriptors(["property_method"])
    preimage = json.dumps([method.descriptor_sha256, method.self_sha256], separators=(",", ":"))
    expected = hashlib.sha256(preimage.encode()).hexdigest()
    assert implementation_sha256(method) == expected
    assert method_entry("vapour", method) == {
        "substream": "vapour",
        "method": method.id,
        "version": method.version,
        "implementation_sha256": expected,
    }


# ------------------------------------------------------------------------------ E-F3-5 rights


def _row(
    source_sha256: str,
    record_sha256: str | None = None,
    assessment: str = "permitted",
    *,
    date: str = "2026-11-18",
    source_id: str = "fixture.lock",
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_sha256": source_sha256,
        "record_sha256": record_sha256,
        "assessment": assessment,
        "conditions": None,
        "basis": "fixture",
        "decided_by": "tester",
        "date": date,
    }


def _source(record: Mapping[str, Any]) -> str:
    ((_, sha),) = rights.record_sources(identify(record).record).items()
    return sha


def test_e_f3_5_assessments_in_both_layers_leave_record_and_lock_shas() -> None:
    stack, components, sets = _fixture()
    records = {sha: stack.object_bytes(sha) for sha in [s for _, s in components] + sets}
    lock_sha = data_lock_sha256(build_lock(components, sets, METHODS, OPTIONS, stack))
    source = _source(_component("A"))
    for sha in records:
        stack.project.append_rights(_row(source, sha, "refused"))
    stack.project.append_rights(_row(source, None, "refused"))
    repository = (_row(source, None, "refused"), _row(source, components[0][1], "refused"))
    for sha in records:
        record = stack.record(sha)
        assessed = rights.record_rights(
            record, sha, project=stack.project.rights_rows(), repository=repository
        )
        assert {item.assessment for item in assessed.values()} == {"refused"}
    for sha, data in records.items():
        assert stack.object_bytes(sha) == data
        assert identify(json.loads(data)).record_sha256 == sha
        assert hashlib.sha256(data).hexdigest() == sha
    assert data_lock_sha256(build_lock(components, sets, METHODS, OPTIONS, stack)) == lock_sha


def test_e_f3_5_the_four_precedence_rows_each_decide_one_fixture() -> None:
    """D11: latest project row for (source, record) → latest project whole-source row → latest
    repository row for (source, record) → latest repository whole-source row → `unknown`. Each
    fixture has rows at its own level and every lower one; the deciding row is the first."""
    store = RecordStore.in_memory()
    record = _component("A")
    sha = identify(record).record_sha256
    assert sha is not None
    source = _source(record)
    other = "e" * 64
    repository = (
        _row(source, None, "refused"),
        _row(source, sha, "permitted"),
        _row(source, other, "refused"),
    )
    project = (
        _row(source, None, "unknown"),
        _row(source, sha, "refused"),
        _row(source, other, "permitted"),
    )
    for row in project:
        store.append_rights(row)
    rows = store.rights_rows()
    assert [row["sequence"] for row in rows] == [1, 2, 3]
    cases = [
        (rows, repository, ("refused", "project", rows[1])),
        (rows[:1], repository, ("unknown", "project", rows[0])),
        ((), repository, ("permitted", "repository", repository[1])),
        ((), repository[:1], ("refused", "repository", repository[0])),
        ((), (), ("unknown", None, None)),
    ]
    for project_rows, repository_rows, (assessment, layer, row) in cases:
        found = rights.effective(sha, source, project=project_rows, repository=repository_rows)
        assert (found.assessment, found.layer, found.row) == (assessment, layer, row)


def test_d11_latest_is_insertion_order_and_a_source_is_its_sha_not_its_id() -> None:
    """D11: "latest" is the highest insertion sequence, never `date`; a whole-source row is keyed
    by `source_sha256`, so a record naming the same source id with another entry inherits
    nothing (W1 P1 review finding 19)."""
    record = _component("A")
    sha = identify(record).record_sha256
    assert sha is not None
    source = _source(record)
    rows = (
        _row(source, None, "refused", date="2026-12-31"),
        _row(source, None, "permitted", date="2026-01-01"),
    )
    assert rights.effective(sha, source, repository=rows).row == rows[1]
    claimant = copy.deepcopy(record)
    claimant["sources"]["fixture.lock"]["version"] = "2"
    claimant["molar_mass"]["value"] = 0.06
    claimed = identify(claimant)
    assert claimed.record_sha256 is not None
    assessed = rights.record_rights(claimed.record, claimed.record_sha256, repository=rows)
    assert assessed == {"fixture.lock": Effective("unknown", None, None, None)}
    assert not rights.embeddable(assessed)


def test_e_f3_5_assess_rights_with_the_default_agent_grant_is_forbidden(tmp_path: Path) -> None:
    """E-F3-5's third clause (D13: the right `policy`, which the default agent grant lacks): the
    call is refused `forbidden` naming `policy`, writes no rights row, and is audited."""
    from openflowsheet.application.authz import grant
    from openflowsheet.application.errors import ApplicationError
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.operations import dispatch

    owner = LocalApplication.create(tmp_path / "project")
    sha = owner.register_record(record=_component("fixture.agent")).results[0]["record_sha256"]
    owner.close()
    capability, _ = grant(tmp_path / "project", principal_id="agent")  # the default grant
    request = {
        "source_id": "fixture.lock",
        "record_sha256": sha,
        "scope": "record",
        "assessment": "permitted",
        "basis": "an agent vetting data",
    }
    with LocalApplication.open(tmp_path / "project", capability=capability) as agent:
        with pytest.raises(ApplicationError) as refused:
            dispatch(agent, "assess_rights", request)
        assert refused.value.code == "forbidden"
        assert refused.value.error.detail["required"] == ["policy"]
        assert agent.get_record(sha).rows == ()
    with LocalApplication.open(tmp_path / "project") as reopened:
        rows = reopened.store.audit_rows()
    last = rows[-1]
    assert (last["operation"], last["outcome"], last["code"]) == (
        "assess_rights",
        "refused",
        "forbidden",
    )


def test_d11_rows_off_the_shape_are_refused() -> None:
    good = _row("a" * 64)
    assert rights.check_row(good, "x") == good
    for edit in (
        {"assessment": "allowed"},
        {"source_sha256": "A" * 64},
        {"record_sha256": "a" * 63},
        {"basis": ""},
        {"date": "18-11-2026"},
        {"extra": 1},
    ):
        with pytest.raises(rights.RightsRegisterError):
            rights.check_row({**good, **edit}, "x")
    with pytest.raises(rights.RightsRegisterError):
        RecordStore.in_memory().append_rights({**good, "assessment": "maybe"})


# ------------------------------------------------------------------- the repository register

#: D11's reading, on the seven v1 `redistribution` texts (written out from the files) and on
#: each of the rule's other prefixes.
SEED_READINGS = {
    "synthetic; no restrictions": ("permitted", None),
    "permitted: published numerical constants quoted with their citations": ("permitted", None),
    "permitted: project-authored synthetic values": ("permitted", None),
    "permitted with conditions: Publication in whole or in part is allowed": (
        "permitted",
        "Publication in whole or in part is allowed",
    ),
    "unresolved: see docs/s10-rights-check.md": ("unknown", None),
    "unknown terms": ("unknown", None),
    "refused by the publisher": ("refused", None),
    "not permitted: database extraction": ("refused", None),
    "public domain": ("unknown", None),
}

S05_CONDITIONS = (
    "Publication in whole or in part is allowed in all countries provided that attribution is "
    "given to the International Association for the Properties of Water and Steam"
)
S07_CONDITIONS = "cite CoolProp with its MIT notice and the equation of state's source (R-715)"
#: F3 ruling round 1 (B5): the `s07` row carrying H2O's v1 `rights.notes` condition.
S07_ROW = {
    "source_id": "legacy.s07",
    "record_sha256": None,
    "assessment": "permitted",
    "conditions": S07_CONDITIONS + "; for the H2O record: attribution to the International "
    "Association for the Properties of Water and Steam (S05 spec §16.3)",
    "basis": "benchmarks/s07/components.yaml: v1 rights.notes of H2O; docs/reviews/F3-rulings-1.md",
    "decided_by": "design lane (reviewer), F3 ruling round 1",
    "date": "2026-11-18",
}
#: The seed's (assessment, conditions) per legacy source, from the files' texts by D11's rule.
SEEDS = {
    "legacy.syn001": ("permitted", None),
    "legacy.m01": ("permitted", None),
    "legacy.l01": ("permitted", None),
    "legacy.s05": ("permitted", S05_CONDITIONS),
    "legacy.s07": ("permitted", S07_CONDITIONS),
    "legacy.s10": ("unknown", None),
    "legacy.s10-verification": ("permitted", None),
}


def test_d11_the_seed_reading_of_a_redistribution_text() -> None:
    for text, reading in SEED_READINGS.items():
        assert rights.seed_assessment(text) == reading, text


def _imported() -> list[legacy.ImportedFile]:
    return legacy.import_all(lambda path: (REPO_ROOT / path).read_bytes())


def test_d11_the_register_holds_one_seed_row_per_legacy_source_and_r880() -> None:
    """Seven seed rows, one per legacy source (a parameter set carries its components' `sources`
    entry, F3 decisions WO4-0 and WO3-5 as ruled in F3 ruling round 1), then D11's one S10 row
    (R-880), then the `s07` row of H2O's condition (ruling round 1, B5); nine in all. Every
    legacy record's every source is effectively `permitted`, S10's by the R-880 row and S07's by
    the `s07` row."""
    rows = rights.repository_rows()
    seeds = [row for row in rows if row["decided_by"] == rights.SEED_DECIDED_BY]
    assert len(seeds) == 7 and rows[: len(seeds)] == tuple(seeds)
    imported = _imported()
    pairs = {
        pair
        for item in imported
        for o in item.records
        for pair in rights.record_sources(o.record).items()
    }
    assert {(row["source_id"], row["source_sha256"]) for row in seeds} == pairs
    for row in seeds:
        assert row["record_sha256"] is None
        assert (row["assessment"], row["conditions"]) == SEEDS[row["source_id"]]
    (s10,) = {sha for ident, sha in pairs if ident == "legacy.s10"}
    r880 = [row for row in rows[len(seeds) :] if row["basis"].startswith("R-880")]
    assert len(r880) == 1 and r880[0]["source_sha256"] == s10
    for row in r880:
        assert (row["source_id"], row["assessment"], row["conditions"]) == (
            "legacy.s10",
            "permitted",
            "NOTICE Wilson block",
        )
    (s07,) = {sha for ident, sha in pairs if ident == "legacy.s07"}
    assert len(rows) == 9 and rows[7] == r880[0]
    assert rows[8] == {**S07_ROW, "source_sha256": s07}
    deciding = {"s10": r880[0], "s07": rows[8]}
    for item in imported:
        for outcome in item.records:
            assessed = rights.record_rights(outcome.record, outcome.record_sha256)
            assert rights.embeddable(assessed), outcome.record["id"]
            if item.profile in deciding:
                assert [a.row for a in assessed.values()] == [deciding[item.profile]]


def test_d11_the_check_fails_when_a_seed_row_is_stale() -> None:
    """`scripts/records_legacy_index.py --check`: a seed row whose `source_sha256` differs from
    the import's, and a `legacy.` row naming a SHA the import does not give, each fail it."""
    rows = [dict(row) for row in rights.repository_rows()]
    assert records_legacy_index.problems(tracked=[], register=rows) == []
    stale = copy.deepcopy(rows)
    stale[1]["source_sha256"] = "0" * 64
    found = records_legacy_index.problems(tracked=[], register=stale)
    m01 = rows[1]
    assert found == [
        f"rights-register.json: no seed row for legacy.m01 {m01['source_sha256']}",
        f"rights-register.json: legacy.m01 row names an unknown source_sha256 {'0' * 64}",
    ]
    reread = copy.deepcopy(rows)
    reread[5]["assessment"] = "permitted"
    assert len(records_legacy_index.problems(tracked=[], register=reread)) == 1


def test_the_packaged_register_is_its_file() -> None:
    text = (REPO_ROOT / "src" / "openflowsheet" / "records" / rights.REGISTER_NAME).read_text(
        encoding="utf-8"
    )
    assert rights.register_rows(json.loads(text)) == rights.repository_rows()
