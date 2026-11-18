"""F3-WO3: the legacy import, the legacy index and the loader views (ADR 0061 D12).

E-F3-1 (the views equal the legacy loaders field by field, floats by `struct.pack("<d")` bytes),
E-F3-2 (all 147 molar masses and positions), E-F3-6 (the committed index, a one-ulp change in a
temporary copy, an unprofiled v1 file failing `--check`) and E-F3-13's legacy part (anchors and
the pinned findings). Every expectation comes from the legacy files, their loaders, the ADR's
counts or hashes computed here, never from the importer's output; the importer's own output is
compared only with itself through the store and the committed index.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
import re
import shutil
import struct
import subprocess
import sys
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

from openflowsheet.canonical import document_sha256
from openflowsheet.models.revision_flowsheet import selectable_bases
from openflowsheet.records.importers import legacy
from openflowsheet.records.importers.legacy import ImportedFile, LegacyImportError
from openflowsheet.records.legacy_views import (
    c1_records,
    legacy_path_for,
    library_records,
    wilson_records,
)
from openflowsheet.records.stack import LegacyStore
from openflowsheet.records.store import RecordStore, RecordStoreError
from openflowsheet.registry import Coded
from openflowsheet.thermo import pr_c1, pr_lib, wilson_ig

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import records_legacy_index  # noqa: E402

#: ADR 0061 D12's profile table: profile, file, component records, parameter sets.
D12_FILES = {
    "syn001": ("benchmarks/syn001/components.yaml", 3, 0),
    "m01": ("benchmarks/m01/components.yaml", 5, 0),
    "l01": ("benchmarks/l01/components.yaml", 9, 0),
    "s05": ("benchmarks/s05/components.yaml", 1, 0),
    "s07": ("benchmarks/s07/components.yaml", 123, 0),
    "s10": ("benchmarks/s10/records.yaml", 3, 1),
    "s10-verification": ("benchmarks/s10/verification-records.yaml", 3, 1),
}
#: D12's fit inputs (ruling 1), by the field they classify.
FIT_INPUTS = {
    "formation": "benchmarks/s10/nasa7-low.json",
    "vapour_pressure": "benchmarks/s10/saturation-points.json",
    "wilson_lambda": "benchmarks/s10/vle/kurihara1993_binaries.csv",
}
INDEX = REPO_ROOT / "src" / "openflowsheet" / "records" / "legacy_index.json"


def _read(root: Path) -> Any:
    return lambda path: root.joinpath(*path.split("/")).read_bytes()


@cache
def _imported() -> dict[str, ImportedFile]:
    return {item.profile: item for item in legacy.import_all(_read(REPO_ROOT))}


def _yaml(profile: str) -> Any:
    return yaml.safe_load((REPO_ROOT / D12_FILES[profile][0]).read_text(encoding="utf-8"))


def _components(profile: str) -> list[Mapping[str, Any]]:
    return [r for r in _imported()[profile].projections() if r["record_type"] == "component"]


def _parameter_set(profile: str) -> Mapping[str, Any]:
    (found,) = [r for r in _imported()[profile].projections() if r["record_type"] != "component"]
    return found


def _stored(records: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """The records after a round trip through a store (canonical JSON bytes and back)."""
    store = RecordStore.in_memory()
    shas = [store.add(record)[0] for record in records]
    return [dict(store.record(sha) or {}) for sha in shas]


def _same(left: Any, right: Any, at: str = "") -> list[str]:
    """Field-by-field differences; floats by `struct.pack("<d")` bytes, types exactly. A
    mapping compares by key set (Python's mapping equality): a record's objects are canonical
    (D2 sorts keys), so `elemental_composition` keeps its members, not the YAML's key order."""
    if type(left) is not type(right):
        return [f"{at}: {type(left).__name__} != {type(right).__name__}"]
    if dataclasses.is_dataclass(left):
        return [
            d
            for f in dataclasses.fields(left)
            for d in _same(getattr(left, f.name), getattr(right, f.name), f"{at}.{f.name}")
        ]
    if isinstance(left, tuple | list):
        if len(left) != len(right):
            return [f"{at}: length {len(left)} != {len(right)}"]
        return [
            d
            for n, (a, b) in enumerate(zip(left, right, strict=True))
            for d in _same(a, b, f"{at}[{n}]")
        ]
    if isinstance(left, Mapping):
        if sorted(left) != sorted(right):
            return [f"{at}: keys {sorted(left)} != {sorted(right)}"]
        return [d for key in sorted(left) for d in _same(left[key], right[key], f"{at}.{key}")]
    if isinstance(left, float):
        return (
            []
            if struct.pack("<d", left) == struct.pack("<d", right)
            else [f"{at}: {left!r} != {right!r}"]
        )
    return [] if left == right else [f"{at}: {left!r} != {right!r}"]


# ---------------------------------------------------------------------- E-F3-1 loader equality


@pytest.mark.parametrize("through", ["import", "store"])
def test_e_f3_1_c1_and_library_views_equal_their_loaders(through: str) -> None:
    m01, l01 = _components("m01"), _components("l01")
    if through == "store":
        m01, l01 = _stored(m01), _stored(l01)
    assert _same(c1_records(m01), pr_c1.load_records()) == []
    assert _same(library_records(reversed(l01)), pr_lib.load_records()) == []
    assert c1_records(m01) == pr_c1.load_records()
    assert library_records(l01) == pr_lib.load_records()


@pytest.mark.parametrize("through", ["import", "store"])
@pytest.mark.parametrize("profile", ["s10", "s10-verification"])
def test_e_f3_1_wilson_views_equal_the_loader(profile: str, through: str) -> None:
    components, parameter_set = _components(profile), _parameter_set(profile)
    if through == "store":
        components, (parameter_set,) = _stored(components), _stored([parameter_set])
    loaded = wilson_ig.load_records(REPO_ROOT / D12_FILES[profile][0])
    assert _same(wilson_records(components, parameter_set), loaded) == []


def test_views_refuse_records_of_two_files_and_a_foreign_parameter_set() -> None:
    with pytest.raises(ValueError, match="2 legacy files"):
        c1_records([*_components("m01"), *_components("l01")])
    with pytest.raises(ValueError, match="positions"):
        c1_records(_components("m01")[1:])
    with pytest.raises(ValueError, match="not of the components' file"):
        wilson_records(_components("s10"), _parameter_set("s10-verification"))


def test_legacy_path_for_names_exactly_one_files_records() -> None:
    assert legacy_path_for(_components("m01")) == pr_c1.RECORDS_PATH
    s10 = [*_components("s10"), _parameter_set("s10")]
    assert legacy_path_for(reversed(s10)) == wilson_ig.RECORDS_PATH
    with pytest.raises(ValueError):
        legacy_path_for(_components("s10"))
    with pytest.raises(ValueError):
        legacy_path_for(_components("m01")[:4])


# ------------------------------------------------------------- E-F3-2 molar masses and order


def test_e_f3_2_molar_masses_and_positions_equal_the_files() -> None:
    compared = 0
    for profile, (_, count, _) in D12_FILES.items():
        v1 = _yaml(profile)["components"]
        records = _components(profile)
        assert len(v1) == len(records) == count, profile
        for position, (old, new) in enumerate(zip(v1, records, strict=True)):
            assert (new["id"], new["legacy"]["position"]) == (old["id"], position)
            value = old["molecular_weight"]["value"]
            assert struct.pack("<d", new["molar_mass"]["value"]) == struct.pack("<d", value)
            compared += 1
    assert compared == 147


def test_e_f3_2_molar_masses_equal_the_selectable_bases() -> None:
    """Review N9: the clause covers the profiles that are bases (SYN-001, C1, IAPWS-95, Wilson
    and the 123 CoolProp fluids)."""
    by_file = {path: profile for profile, (path, _, _) in D12_FILES.items()}
    compared = 0
    for basis in selectable_bases():
        records = {r["id"]: r for r in _components(by_file[basis.record_source])}
        for ident, weight in basis.molecular_weights.items():
            held = records[ident]["molar_mass"]["value"]
            assert struct.pack("<d", held) == struct.pack("<d", weight), (basis.provider_id, ident)
            compared += 1
    assert compared == 3 + 5 + 1 + 3 + 123


# ------------------------------------------------------------------------ E-F3-6 legacy index


def test_e_f3_6_import_reproduces_the_committed_index() -> None:
    document = json.loads(INDEX.read_text(encoding="utf-8"))
    rendered = records_legacy_index.render(legacy.index_document(_imported().values()))
    assert rendered == INDEX.read_text(encoding="utf-8")
    assert [entry["path"] for entry in document["files"]] == sorted(
        path for path, _, _ in D12_FILES.values()
    )
    shas = [r["sha256"] for entry in document["files"] for r in entry["records"]]
    assert len(shas) == len(set(shas)) == 149
    for entry in document["files"]:
        data = (REPO_ROOT / entry["path"]).read_bytes()
        assert entry["file_sha256"] == hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        profile = entry["profile"]
        assert (entry["path"], len(entry["records"])) == (
            D12_FILES[profile][0],
            D12_FILES[profile][1] + D12_FILES[profile][2],
        )
        assert entry["reference_convention"] == _yaml(profile).get("reference_convention")


def test_e_f3_6_object_bytes_hash_to_the_indexed_shas() -> None:
    store = RecordStore.in_memory()
    for imported in _imported().values():
        for outcome in imported.records:
            sha, _ = store.add(outcome.record)
            assert sha == outcome.record_sha256
            assert hashlib.sha256(store.object_bytes(sha) or b"").hexdigest() == sha


def _copy_tree(root: Path) -> None:
    for path, _, _ in D12_FILES.values():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, root / path)
    for path in FIT_INPUTS.values():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / path, root / path)


def _one_ulp(text: str) -> str:
    """`text` with its first `value: <float>` moved up by one ulp."""
    match = re.search(r"value: (-?[0-9][0-9.e+-]*)", text)
    assert match is not None
    old = float(match[1])
    new = math.nextafter(old, math.inf)
    assert struct.pack("<d", new) != struct.pack("<d", old)
    return text[: match.start(1)] + repr(new) + text[match.end(1) :]


@pytest.mark.parametrize("profile", list(D12_FILES))
def test_e_f3_6_one_ulp_moves_exactly_that_files_shas(profile: str, tmp_path: Path) -> None:
    _copy_tree(tmp_path)
    target = tmp_path / D12_FILES[profile][0]
    target.write_text(_one_ulp(target.read_text(encoding="utf-8")), encoding="utf-8")
    moved = {item.profile: item for item in legacy.import_all(_read(tmp_path))}
    for name, imported in _imported().items():
        before = [outcome.record_sha256 for outcome in imported.records]
        after = [outcome.record_sha256 for outcome in moved[name].records]
        if name == profile:
            assert not set(before) & set(after)
        else:
            assert before == after


def test_e_f3_6_an_unprofiled_v1_file_fails_the_check(tmp_path: Path) -> None:
    _copy_tree(tmp_path)
    tracked = [path for path, _, _ in D12_FILES.values()]
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "m01.yaml").symlink_to(tmp_path / D12_FILES["m01"][0])
    assert records_legacy_index.problems(tmp_path, [*tracked, "pkg/m01.yaml"]) == []
    extra = tmp_path / "benchmarks" / "x99" / "components.yaml"
    extra.parent.mkdir(parents=True)
    extra.write_text(
        "schema_version: 1\nrecord_schema: schemas/component-record.schema.json\ncomponents: []\n"
    )
    found = records_legacy_index.problems(tmp_path, [*tracked, "benchmarks/x99/components.yaml"])
    assert found == [
        "benchmarks/x99/components.yaml declares schemas/component-record.schema.json and has "
        "no profile"
    ]


def test_e_f3_6_the_check_is_clean_on_the_checkout() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "records_legacy_index.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.strip() == "records_legacy_index --check: clean, 149 records in 7 files"


def test_the_fit_input_constants_are_the_files_hashes() -> None:
    for field, path in FIT_INPUTS.items():
        expected = hashlib.sha256(
            (REPO_ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        row = legacy.profile_named("s10").provenance[field]
        assert row["inputs"] == [{"scheme": "file", "sha256": expected, "path": path}]
    assert records_legacy_index.stale_inputs(REPO_ROOT) == []


# ------------------------------------------------------------------ the legacy store's loader


def test_the_loader_gives_every_available_record_and_refuses_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LegacyStore(legacy.available_records).store()
    document = json.loads(INDEX.read_text(encoding="utf-8"))
    for entry in document["files"]:
        for record in entry["records"]:
            assert store.record(record["sha256"]) is not None
    original = legacy.available_bytes

    def edited(path: str) -> bytes | None:
        data = original(path)
        if path != D12_FILES["l01"][0] or data is None:
            return data
        return _one_ulp(data.decode("utf-8")).encode("utf-8")

    monkeypatch.setattr(legacy, "available_bytes", edited)
    with pytest.raises(RecordStoreError) as caught:
        legacy.available_records()
    assert caught.value.coded == Coded(
        "legacy_record_drift", {"file": D12_FILES["l01"][0], "id": "H2"}
    )


def test_a_record_whose_sha_differs_from_the_index_is_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = copy.deepcopy(dict(legacy.committed_index()))
    (s10,) = [entry for entry in index["files"] if entry["profile"] == "s10"]
    s10["records"][3]["sha256"] = "0" * 64
    monkeypatch.setattr(legacy, "committed_index", lambda: index)
    with pytest.raises(RecordStoreError) as caught:
        legacy.available_records()
    assert caught.value.coded == Coded(
        "legacy_record_drift", {"file": D12_FILES["s10"][0], "id": _yaml("s10")["data_set"]}
    )


# --------------------------------------------------------------- E-F3-13 legacy anchors, findings


def test_e_f3_13_legacy_anchors_and_pinned_findings() -> None:
    """D12: `ig` from formation data for m01, l01, s10 and s10-verification; `ig` by default,
    with `anchor_defaulted(<id>)`, for the 127 records of syn001, s05 and s07; none null. The 17
    molar masses of m01, l01 and s10 are `fit_inputs_unhashed(/molar_mass)`."""
    document = json.loads(INDEX.read_text(encoding="utf-8"))
    findings = {
        (entry["profile"], r["id"]): r["findings"]
        for entry in document["files"]
        for r in entry["records"]
    }
    defaulted = unhashed = 0
    for profile in D12_FILES:
        for record in _components(profile):
            assert record["anchor_phase"] == "ig"
            found = findings[(profile, record["id"])]
            if profile in ("syn001", "s05", "s07"):
                assert found == [
                    {"code": "anchor_defaulted", "params": {"component": record["id"]}}
                ]
                defaulted += 1
            elif profile in ("m01", "l01", "s10"):
                assert found == [
                    {"code": "fit_inputs_unhashed", "params": {"entry": "/molar_mass"}}
                ]
                unhashed += 1
            else:
                assert found == []
            assert any(item["phase"] == "ig" for item in record.get("formation", [])) == (
                profile not in ("syn001", "s05", "s07")
            )
    assert (defaulted, unhashed) == (127, 17)
    sets = [
        r for e in document["files"] for r in e["records"] if r["record_type"] == "parameter_set"
    ]
    assert [r["findings"] for r in sets] == [[], []]


# ------------------------------------------------------------------ D12's mapping, spot checks


def test_d12_mapping_of_an_m01_record() -> None:
    v1 = _yaml("m01")["components"][0]
    (record,) = [r for r in _components("m01") if r["id"] == v1["id"]]
    parameters = v1["parameters"]
    source_id, source = next(iter(record["sources"].items()))
    assert source_id == "legacy.m01"
    assert source == {
        "version": record["legacy"]["file_sha256"],
        "citation": legacy.profile_named("m01").citation,
    }
    assert (record["amount_basis"], record["charge"], record["synthetic"]) == ("mol", 0, False)
    assert record["identifiers"] == v1["identifiers"]
    assert record["elements"] == v1["elemental_composition"]
    entries = {e["property"]: e for e in record["entries"]}
    assert set(entries) == {
        "critical_temperature",
        "critical_pressure",
        "acentric_factor",
        "ideal_gas_cp",
    }
    tc = entries["critical_temperature"]
    assert (tc["value"], tc["meaning"], tc["note"]) == (
        parameters["critical_temperature"]["value"],
        parameters["critical_temperature"]["meaning"],
        parameters["critical_temperature"]["provenance"],
    )
    assert tc["provenance"] == {
        "origin": ["measured"],
        "derivation": "direct",
        "source": "legacy.m01",
    }
    cp = entries["ideal_gas_cp"]
    names = [f"ideal_gas_cp_b{k}" for k in range(5)]
    bounds = ["ideal_gas_cp_lower_temperature", "ideal_gas_cp_upper_temperature"]
    assert cp["coefficients"] == {f"b{k}": parameters[n]["value"] for k, n in enumerate(names)}
    assert cp["validity"] == {"T": [parameters[n]["value"] for n in bounds]}
    assert "meaning" not in cp
    assert cp["note"] == "\n".join(
        dict.fromkeys(parameters[n]["provenance"] for n in names + bounds)
    )
    (formation,) = record["formation"]
    assert formation["phase"] == "ig"
    assert formation["h"]["value"] == parameters["standard_formation_enthalpy"]["value"]
    assert formation["h"]["provenance"]["origin"] == ["computed", "measured"]
    assert record["molar_mass"]["provenance"] == {
        "origin": ["measured"],
        "derivation": "generated",
        "source": "legacy.m01",
    }
    assert record["molar_mass"]["note"] == "\n".join(
        (v1["molecular_weight"]["provenance"], v1["rights"]["source"])
    )


def test_wo4_0_one_citation_and_one_source_sha_per_legacy_source() -> None:
    """F3 decision WO4-0: each file's records carry its profile's citation, the parameter set's
    as its components' (WO3-5 as ruled in F3 ruling round 1), so the import gives one
    `source_sha256` per legacy source over components and sets together, seven in all; a file
    whose components cite one text cites it verbatim, and every component's own `rights.source`
    ends its molar mass's `note`."""
    shas: dict[str, set[str]] = {}
    for profile, imported in _imported().items():
        v1 = _yaml(profile)["components"]
        texts = {component["rights"]["source"] for component in v1}
        if len(texts) == 1:
            assert {legacy.profile_named(profile).citation} == texts
        for outcome in imported.records:
            ((source_id, entry),) = outcome.record["sources"].items()
            assert source_id == legacy.profile_named(profile).source
            shas.setdefault(source_id, set()).add(document_sha256({source_id: entry}))
        for component, outcome in zip(v1, imported.records, strict=False):
            note = outcome.record["molar_mass"]["note"]
            assert note.split("\n")[-1] == component["rights"]["source"]
    assert {key: len(found) for key, found in shas.items()} == dict.fromkeys(shas, 1)
    assert len(shas) == 7


#: F3 ruling round 1 (B2): each templated profile citation's placeholder phrase, which stands for
#: the component's own reference EOS text; written out here from `legacy_profiles.yaml`.
PLACEHOLDERS = {
    "m01": "the reference EOS of each fluid (named in its molar mass note)",
    "l01": "the reference EOS of each fluid (named in its molar mass note)",
    "s07": "the equation of state of each fluid is named in its molar mass note",
    "s10": "the equation of state of each fluid is named in its molar mass note",
}


def _departures(citations: Mapping[str, str]) -> dict[str, set[str]]:
    """By templated profile, the components whose v1 `rights.source` is not `citations[profile]`
    with its placeholder phrase replaced by a non-empty text of the component's own."""
    found: dict[str, set[str]] = {}
    for profile, phrase in PLACEHOLDERS.items():
        assert citations[profile].count(phrase) == 1, profile
        head, tail = citations[profile].split(phrase)
        for component in _yaml(profile)["components"]:
            text = component["rights"]["source"]
            own = text[len(head) : len(text) - len(tail)]
            if not (text.startswith(head) and text.endswith(tail) and own and own != phrase):
                found.setdefault(profile, set()).add(component["id"])
    return found


def test_b2_templated_citations_equal_the_files_but_for_each_fluids_eos() -> None:
    """F3 ruling round 1 (B2, WO4-0): in the four templated profiles every component's own
    `rights.source` is the citation with the placeholder replaced by its own EOS text, except
    l01's O2 ("formation enthalpy: zero by definition"); a file whose components cite one text is
    no templated profile. One word changed outside the placeholder makes every component of that
    profile depart."""
    citations = {profile: legacy.profile_named(profile).citation for profile in D12_FILES}
    assert _departures(citations) == {"l01": {"O2"}}
    for profile in D12_FILES:
        texts = {c["rights"]["source"] for c in _yaml(profile)["components"]}
        assert (len(texts) > 1) == (profile in PLACEHOLDERS), profile
    for profile, phrase in PLACEHOLDERS.items():
        head, tail = citations[profile].split(phrase)
        word, upper = re.compile(r"\b[a-z]{4,}\b"), lambda m: m.group().upper()
        if word.search(tail):
            tail = word.sub(upper, tail, count=1)
        else:
            head = word.sub(upper, head, count=1)
        edited = {**citations, profile: head + phrase + tail}
        everyone = {c["id"] for c in _yaml(profile)["components"]}
        assert _departures(edited)[profile] == everyone, profile


def test_d12_mapping_of_the_s10_parameter_set_and_a_syn001_record() -> None:
    v1 = _yaml("s10")
    found = _parameter_set("s10")
    assert (found["id"], found["data_set"], found["synthetic"]) == (v1["data_set"],) * 2 + (False,)
    assert found["uncertainty_statement"] == v1["uncertainty"]
    assert found["validity"] == v1["domain"]
    assert found["legacy"]["file_fields"] == {
        "reference_convention": v1["reference_convention"],
        "data_provenance": v1["data_provenance"],
    }
    keys = [item["key"] for item in found["components"]]
    assert keys == sorted(c["id"] for c in v1["components"])
    pairs = {tuple(e["indices"]): (e["value"], e.get("note")) for e in found["entries"]}
    assert pairs == {(e["i"], e["j"]): (e["value"], e["provenance"]) for e in v1["wilson_lambda"]}
    syn = _components("syn001")[0]
    names = {e["property"] for e in syn["entries"]}
    assert names == {f"syn001.{name}" for name in _yaml("syn001")["components"][0]["parameters"]}
    assert {e["provenance"]["origin"][0] for e in syn["entries"]} == {"synthetic"}


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: d.update(extra=1), "not in D12's mapping table"),
        (lambda d: d["components"][0].update(synonyms=["x"]), "not in D12's mapping table"),
        (lambda d: d["components"][0]["identifiers"].update(smiles="[HH]"), "identifiers"),
        (lambda d: d["components"][0]["parameters"].update(boiling_point={}), "parameters"),
        (lambda d: d["components"][0]["parameters"].pop("acentric_factor"), "missing"),
        (lambda d: d["components"][0]["parameters"]["acentric_factor"].update(role="free"), "role"),
        (lambda d: d["components"][0]["rights"].update(licence="x"), "rights"),
    ],
)
def test_d12_a_key_outside_the_closed_table_fails(edit: Any, message: str) -> None:
    document = _yaml("m01")
    edit(document)
    data = yaml.safe_dump(document, sort_keys=False).encode("utf-8")
    with pytest.raises(LegacyImportError, match=message):
        legacy.import_file(legacy.profile_named("m01"), data)


def test_s07_spin_isomer_labels_are_dropped_and_the_rest_copied() -> None:
    """F3 decision WO3-2: CoolProp's `1333-74-0o`-style labels are not CAS numbers."""
    v1 = {c["id"]: c for c in _yaml("s07")["components"]}
    for record in _components("s07"):
        stated = v1[record["id"]].get("identifiers", {})
        kept = {k: v for k, v in stated.items() if not re.fullmatch(r"\d+-\d\d-\d[op]", v)}
        assert record.get("identifiers", {}) == kept
    assert sum(1 for c in v1.values() if c["identifiers"]["cas"][-1] in "op") == 3


@pytest.mark.parametrize(
    ("profile", "dropped"),
    [("m01", {"H2": ["cas"]}), ("m01", {"H2": ["inchikey"]}), ("m01", {"H2": ["formula"]})],
)
def test_b3_a_dropped_identifier_must_be_one_d3_refuses(
    profile: str, dropped: dict[str, list[str]]
) -> None:
    """F3 ruling round 1 (B3, WO3-2): a profile may drop only a `cas` or `inchikey` whose stated
    value D3 refuses; dropping H2's valid CAS number, InChIKey or its formula fails the import.
    The committed profiles still import to the committed index (E-F3-6)."""
    v1 = {c["id"]: c for c in _yaml(profile)["components"]}
    assert set(dropped["H2"]) <= set(v1["H2"]["identifiers"])
    edited = dataclasses.replace(legacy.profile_named(profile), dropped_identifiers=dropped)
    data = (REPO_ROOT / D12_FILES[profile][0]).read_bytes()
    with pytest.raises(LegacyImportError, match="are not ones D3 refuses"):
        legacy.import_file(edited, data)
    assert records_legacy_index.regenerated() == INDEX.read_text(encoding="utf-8")
