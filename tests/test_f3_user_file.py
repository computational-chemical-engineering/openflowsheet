"""F3-WO5a: the user-file adapter (ADR 0061 D12, `user-file` 1.0.0), exit test E-F3-12 at the
library level (the operation `register_record` is F3-WO5b's).

Expectations: the round trip's SHAs are the committed legacy index's; the v1 path's entries are the
legacy import's but for provenance and `sources`, as E-F3-12 states; the provenance and the
`sources` entry are D12's `defaults` mapping; without `defaults` the refused values are D12's six
per `m01` record (the molar mass, the formation enthalpy, and the four entries Tc, Pc, ω and
c_p^ig), never the adapter's own list.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.records.importers import legacy
from openflowsheet.records.importers.user_file import ADAPTER_VERSION, import_user_file
from openflowsheet.records.model import RecordOutcome
from openflowsheet.registry.tokens import Coded

AT = "2026-11-18T09:30:00Z"
INDEX = REPO_ROOT / "src" / "openflowsheet" / "records" / "legacy_index.json"
V1 = "component-record-v1-yaml"
DEFAULTS = {
    "origin": ["measured", "computed"],
    "derivation": "direct",
    "source_id": "user.m01-copy",
    "source_version": "2026-11-18",
    "citation": "A copy of benchmarks/m01/components.yaml",
}
#: D12, `m01`: each record's values, by pointer into the normalised record (entries sort by
#: property: acentric factor, Tc, Pc, c_p^ig).
M01_VALUES = {"/molar_mass", "/formation/0/h", *(f"/entries/{n}" for n in range(4))}
M01_IDS = ["H2", "N2", "NH3", "Ar", "CH4"]


@cache
def _index_shas(profile: str) -> dict[str, str]:
    """The committed legacy index's record SHAs of `profile`'s file, by record id."""
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    (entry,) = [f for f in index["files"] if f["profile"] == profile]
    return {record["id"]: record["sha256"] for record in entry["records"]}


@cache
def _legacy(profile: str) -> tuple[Mapping[str, Any], ...]:
    found = legacy.profile_named(profile)
    imported = legacy.import_file(found, (REPO_ROOT / found.file).read_bytes())
    return tuple(imported.projections())


def _m01_copy(tmp_path: Path) -> Path:
    copy = tmp_path / "components.yaml"
    copy.write_bytes((REPO_ROOT / "benchmarks" / "m01" / "components.yaml").read_bytes())
    return copy


def _without_provenance(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _without_provenance(v) for k, v in value.items() if k != "provenance"}
    if isinstance(value, list):
        return [_without_provenance(item) for item in value]
    return value


def _codes(outcome: RecordOutcome) -> list[tuple[str, dict[str, str]]]:
    return [(e.code, dict(e.params)) for e in outcome.errors]


# -- v2: the round trip ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile", ["m01", "s10"])
@pytest.mark.parametrize("file_format", ["record-v2-json", "record-v2-yaml"])
def test_e_f3_12_a_v2_file_round_trips_to_the_same_sha(profile: str, file_format: str) -> None:
    records = [dict(record) for record in _legacy(profile)]
    records[0]["volatile"] = {"retrieved_at": "2020-01-01T00:00:00Z", "host": "elsewhere"}
    if file_format == "record-v2-json":
        content = json.dumps(records, ensure_ascii=False)
    else:
        content = yaml.safe_dump(records, allow_unicode=True, sort_keys=False)
    outcomes = import_user_file(file_format, content, retrieved_at=AT, local_path="/data/r.json")
    assert [o.record_sha256 for o in outcomes] == [_index_shas(profile)[r["id"]] for r in records]
    expected = {"retrieved_at": AT, "local_path": "/data/r.json", "adapter_version": "1.0.0"}
    assert all(o.volatile == expected for o in outcomes)
    assert all(not o.errors for o in outcomes)


@pytest.mark.parametrize("file_format", ["record-v2-json", "record-v2-yaml"])
def test_one_v2_record_without_a_list(file_format: str) -> None:
    record = _legacy("m01")[2]
    content = json.dumps(record) if file_format == "record-v2-json" else yaml.safe_dump(record)
    (outcome,) = import_user_file(file_format, content.encode("utf-8"), retrieved_at=AT)
    assert outcome.record_sha256 == _index_shas("m01")["NH3"]
    assert outcome.volatile == {"retrieved_at": AT, "adapter_version": ADAPTER_VERSION}


def test_a_v2_record_d2_refuses_keeps_its_errors() -> None:
    record = {**_legacy("m01")[0], "charge": 1, "amount_basis": "kg"}
    (outcome,) = import_user_file("record-v2-json", json.dumps(record), retrieved_at=AT)
    assert outcome.record_sha256 is None
    assert ("amount_basis_unsupported", {"basis": "kg"}) in _codes(outcome)


@pytest.mark.parametrize(
    ("file_format", "content"),
    [
        ("record-v2-json", "components: []\n"),  # YAML is not JSON
        ("record-v2-json", '{"a": 1, "a": 2}'),
        ("record-v2-yaml", "a: [1\n"),
        (V1, b"\xff\xfe"),
    ],
)
def test_text_that_is_not_one_document_is_one_refused_outcome(
    file_format: str, content: str | bytes
) -> None:
    (outcome,) = import_user_file(file_format, content, retrieved_at=AT)
    assert outcome.record_sha256 is None
    assert outcome.errors == (Coded("record_schema_invalid", {"pointer": ""}),)


def test_a_list_element_that_is_not_an_object_is_refused_alone() -> None:
    content = json.dumps([_legacy("m01")[0], "H2", 3])
    outcomes = import_user_file("record-v2-json", content, retrieved_at=AT)
    assert outcomes[0].record_sha256 == _index_shas("m01")["H2"]
    assert [_codes(o) for o in outcomes[1:]] == [
        [("record_schema_invalid", {"pointer": ""})],
        [("record_schema_invalid", {"pointer": ""})],
    ]


def test_an_unknown_format_is_a_callers_error() -> None:
    with pytest.raises(ValueError, match="not a user-file format"):
        import_user_file("csv", "", retrieved_at=AT)


# -- v1: m01's YAML with and without `defaults` ---------------------------------------------------


def test_e_f3_12_m01_with_defaults_gives_the_legacy_entries_but_provenance_and_sources(
    tmp_path: Path,
) -> None:
    copy = _m01_copy(tmp_path)
    outcomes = import_user_file(
        V1, copy.read_bytes(), retrieved_at=AT, defaults=DEFAULTS, local_path=str(copy)
    )
    assert [o.record["id"] for o in outcomes] == M01_IDS
    assert all(o.record_sha256 is not None and not o.errors for o in outcomes)
    for outcome, imported in zip(outcomes, _legacy("m01"), strict=True):
        assert _without_provenance(outcome.record["entries"]) == _without_provenance(
            imported["entries"]
        )
        # Beyond E-F3-12: the whole record but provenance, `sources` and `legacy`.
        drop = {"sources", "legacy"}
        assert _without_provenance({k: v for k, v in outcome.record.items() if k not in drop}) == (
            _without_provenance({k: v for k, v in imported.items() if k not in drop})
        )
        assert outcome.record["sources"] == {
            "user.m01-copy": {
                "version": "2026-11-18",
                "citation": "A copy of benchmarks/m01/components.yaml",
            }
        }
        assert "legacy" not in outcome.record
        assert outcome.volatile == {
            "retrieved_at": AT,
            "local_path": str(copy),
            "adapter_version": "1.0.0",
        }


def test_every_v1_value_takes_the_defaults_provenance(tmp_path: Path) -> None:
    (outcome, *_) = import_user_file(
        V1, _m01_copy(tmp_path).read_bytes(), retrieved_at=AT, defaults=DEFAULTS
    )
    record = outcome.record
    values = [record["molar_mass"], record["formation"][0]["h"], *record["entries"]]
    assert len(values) == len(M01_VALUES)
    # D2 sorts `origin`; empty `inputs` and null `transformation` are optional members (step 2a).
    expected = {
        "origin": ["computed", "measured"],
        "derivation": "direct",
        "source": "user.m01-copy",
    }
    assert all(value["provenance"] == expected for value in values)


def test_a_fitted_default_without_inputs_notices_every_value(tmp_path: Path) -> None:
    (outcome, *_) = import_user_file(
        V1,
        _m01_copy(tmp_path).read_bytes(),
        retrieved_at=AT,
        defaults={**DEFAULTS, "derivation": "fitted"},
    )
    assert outcome.record_sha256 is not None
    assert {f.params["entry"] for f in outcome.findings if f.code == "fit_inputs_unhashed"} == (
        M01_VALUES
    )


@pytest.mark.parametrize(
    "defaults",
    [
        None,
        {k: v for k, v in DEFAULTS.items() if k != "citation"},
        {**DEFAULTS, "origin": "measured"},
        {**DEFAULTS, "source_version": 1},
        {**DEFAULTS, "licence": "CC0"},
    ],
    ids=["absent", "no citation", "origin not a list", "version not text", "an extra member"],
)
def test_e_f3_12_without_defaults_every_value_is_provenance_invalid(
    tmp_path: Path, defaults: Mapping[str, Any] | None
) -> None:
    outcomes = import_user_file(
        V1, _m01_copy(tmp_path).read_bytes(), retrieved_at=AT, defaults=defaults
    )
    assert [o.record["id"] for o in outcomes] == M01_IDS
    for outcome in outcomes:
        assert outcome.record_sha256 is None
        assert {code for code, _ in _codes(outcome)} == {"provenance_invalid"}
        assert {params["entry"] for _, params in _codes(outcome)} == M01_VALUES
        assert len(outcome.errors) == len(M01_VALUES)
        assert "sources" not in outcome.record


def test_an_empty_origin_is_d7s_provenance_invalid(tmp_path: Path) -> None:
    outcomes = import_user_file(
        V1, _m01_copy(tmp_path).read_bytes(), retrieved_at=AT, defaults={**DEFAULTS, "origin": []}
    )
    assert all({p["entry"] for _, p in _codes(o)} == M01_VALUES for o in outcomes)


# -- v1: the parameter rule -----------------------------------------------------------------------


def _v1_file(parameters: Mapping[str, Any], **component: Any) -> str:
    """A one-component v1 file (hydrogen's m01 record with `parameters` replaced)."""
    document = yaml.safe_load((REPO_ROOT / "benchmarks" / "m01" / "components.yaml").read_bytes())
    document["components"] = [{**document["components"][0], "parameters": parameters, **component}]
    return yaml.safe_dump(document, sort_keys=False)


def _parameter(value: float, unit: str, kind: str) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "dimension": [0, 0, 0, 0, 0, 0, 0],
        "kind": kind,
        "meaning": "m",
        "role": "fixed",
        "provenance": "p",
    }


def _h2_parameters() -> dict[str, Any]:
    document = yaml.safe_load((REPO_ROOT / "benchmarks" / "m01" / "components.yaml").read_bytes())
    return dict(document["components"][0]["parameters"])


def test_a_name_d12_does_not_map_is_a_user_constant_entry() -> None:
    parameters = {"critical_temperature": _h2_parameters()["critical_temperature"]}
    parameters["kij_reference"] = _parameter(0.25, "1", "dimensionless")
    (outcome,) = import_user_file(V1, _v1_file(parameters), retrieved_at=AT, defaults=DEFAULTS)
    assert outcome.record_sha256 is not None
    entries = {entry["property"]: entry for entry in outcome.record["entries"]}
    assert set(entries) == {"critical_temperature", "user.kij_reference"}
    assert entries["user.kij_reference"]["form"] == "constant"
    assert entries["user.kij_reference"]["value"] == 0.25
    assert "phase" not in entries["user.kij_reference"]  # null, removed by step 2a
    assert "formation" not in outcome.record


def test_heat_capacity_without_bounds_has_no_validity() -> None:
    parameters = {
        name: p for name, p in _h2_parameters().items() if name.startswith("ideal_gas_cp_b")
    }
    (outcome,) = import_user_file(V1, _v1_file(parameters), retrieved_at=AT, defaults=DEFAULTS)
    (entry,) = outcome.record["entries"]
    assert (entry["property"], entry["form"]) == ("ideal_gas_cp", "cp_ig_poly4_theta")
    assert "validity" not in entry


@pytest.mark.parametrize(
    "drop", ["ideal_gas_cp_b3", "ideal_gas_cp_upper_temperature"], ids=["a coefficient", "a bound"]
)
def test_an_incomplete_correlation_is_refused_at_the_parameters(drop: str) -> None:
    parameters = {k: v for k, v in _h2_parameters().items() if k != drop}
    (outcome,) = import_user_file(V1, _v1_file(parameters), retrieved_at=AT, defaults=DEFAULTS)
    assert _codes(outcome) == [("record_schema_invalid", {"pointer": "/components/0/parameters"})]


def test_a_v1_component_off_its_schema_is_refused_at_its_pointer() -> None:
    content = _v1_file(_h2_parameters(), elemental_verification="MAYBE")
    (outcome,) = import_user_file(V1, content, retrieved_at=AT, defaults=DEFAULTS)
    assert _codes(outcome) == [
        ("record_schema_invalid", {"pointer": "/components/0/elemental_verification"})
    ]


@pytest.mark.parametrize(
    ("change", "at"),
    [
        ({"schema_version": 2}, "/schema_version"),
        ({"record_schema": "schemas/other.json"}, "/record_schema"),
        ({"wilson_lambda": []}, "/wilson_lambda"),
        ({"components": {}}, "/components"),
    ],
)
def test_a_v1_envelope_off_d12s_file_row_is_refused(change: dict[str, Any], at: str) -> None:
    document = {**yaml.safe_load(_v1_file(_h2_parameters())), **change}
    (outcome,) = import_user_file(V1, yaml.safe_dump(document), retrieved_at=AT, defaults=DEFAULTS)
    assert _codes(outcome) == [("record_schema_invalid", {"pointer": at})]
