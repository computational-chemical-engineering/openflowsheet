"""F3-WO2: the record store, the store stack and identity-key resolution (ADR 0061 D8, D9).

E-F3-8 (store) in full: one object per record, object bytes hashing to the name, a flipped byte
refused `store_object_corrupt`, two processes registering 200 overlapping records concurrently,
the simulated Windows replace failures and the 167/168 path-length boundary. E-F3-9 (resolution)
on synthetic records, and its source-checkout part (`methanol` across `s07` and `s10`) on the
legacy store filled by the legacy import (F3-WO3). Records here are built in the test: every
identifier and value is invented apart from the CAS and InChIKey spellings, which must pass D7.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.canonical import canonical_json
from openflowsheet.models.revision_flowsheet import COOLPROP_RECORDS, WILSON_RECORDS
from openflowsheet.records import identify
from openflowsheet.records.importers import legacy
from openflowsheet.records.resolve import (
    Ambiguous,
    formula_key,
    identity_classes,
    name_key,
    query_keys,
    resolve,
    search,
)
from openflowsheet.records.stack import LegacyStore, StoreStack
from openflowsheet.records.store import (
    DATABASE_NAME,
    SCHEMA_ID,
    TMP_PREFIX,
    RecordStore,
    RecordStoreError,
    path_too_long,
)
from openflowsheet.registry import Coded

WATER_CAS = "7732-18-5"
WATER_KEY = "XLYOFNOQVPJJNP-UHFFFAOYSA-N"
METHANOL_CAS = "67-56-1"
ETHANOL_KEY = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
DME_KEY = "LCGLNKUTAGEVQW-UHFFFAOYSA-N"


def _component(
    ident: str, name: str, *, source: str = "s", synonyms: tuple[str, ...] = (), **ids: str
) -> dict[str, Any]:
    """A valid `mol` component: synthetic when it has no identifiers."""
    record: dict[str, Any] = {
        "record_format": "openflowsheet-record-v2",
        "record_type": "component",
        "type_version": "1.0.0",
        "id": ident,
        "name": name,
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
    if synonyms:
        record["synonyms"] = list(synonyms)
    return record


def _parameter_set(ident: str, name: str) -> dict[str, Any]:
    """A valid empty parameter set."""
    return {
        "record_format": "openflowsheet-record-v2",
        "record_type": "parameter_set",
        "type_version": "1.0.0",
        "id": ident,
        "name": name,
        "sources": {"s": {"version": "1"}},
        "synthetic": True,
        "components": [],
        "entries": [],
    }


def _register(store: RecordStore | StoreStack, record: dict[str, Any], **kw: Any) -> str:
    outcome = identify(record)
    assert outcome.errors == (), outcome.errors
    return store.register(outcome, principal="tester", **kw).record_sha256


def _object_files(root: Path) -> list[Path]:
    return sorted((root / "records" / "objects").glob("*/*/*"))


def _code(error: RecordStoreError) -> tuple[str, dict[str, str]] | None:
    return None if error.coded is None else (error.coded.code, dict(error.coded.params))


# --------------------------------------------------------------------------------- E-F3-8 store


def test_e_f3_8_registering_twice_gives_one_object(tmp_path: Path) -> None:
    store = RecordStore.at(tmp_path)
    outcome = identify(_component("W", "Water", cas=WATER_CAS, inchikey=WATER_KEY))
    first = store.register(outcome, principal="a")
    second = store.register(outcome, principal="b")
    assert (first.created, second.created) == (True, False)
    assert first.record_sha256 == second.record_sha256 == outcome.record_sha256
    files = _object_files(tmp_path)
    assert len(files) == 1
    sha = first.record_sha256
    assert files[0] == tmp_path / "records" / "objects" / sha[:2] / sha[2:4] / f"{sha}.json"
    assert hashlib.sha256(files[0].read_bytes()).hexdigest() == sha
    assert files[0].read_bytes() == canonical_json(outcome.record)
    assert store.record(sha) == outcome.record
    assert [row.sha for row in store.objects()] == [sha]


def test_e_f3_8_the_database_is_d8s(tmp_path: Path) -> None:
    store = RecordStore.at(tmp_path)
    assert not (tmp_path / "records").exists()  # lazily opened
    _register(store, _component("W", "Water"))
    connection = sqlite3.connect(tmp_path / "records" / DATABASE_NAME)
    try:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}
        assert {"meta", "objects", "keys", "registrations", "rights"} <= tables
        meta = connection.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
        assert meta == (SCHEMA_ID,)
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        connection.close()
    assert not (tmp_path / "project.sqlite3").exists()


def _flip_one_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01
    path.write_bytes(bytes(data))


def test_e_f3_8_a_flipped_byte_is_store_object_corrupt(tmp_path: Path) -> None:
    store = RecordStore.at(tmp_path)
    record = _component("W", "Water", cas=WATER_CAS)
    sha = _register(store, record)
    _flip_one_byte(_object_files(tmp_path)[0])
    expected = ("store_object_corrupt", {"sha": sha})
    for read in (store.object_bytes, store.record, StoreStack(store).record):
        with pytest.raises(RecordStoreError) as caught:
            read(sha)
        assert _code(caught.value) == expected
    with pytest.raises(RecordStoreError) as caught:
        _register(store, record)  # D8: an existing target is verified, not replaced
    assert _code(caught.value) == expected
    assert store.rebuild() == (Coded("store_object_corrupt", {"sha": sha}),)
    assert store.objects() == []


_WORKER = textwrap.dedent(
    """
    import random, sys, time
    from pathlib import Path
    from openflowsheet.records import identify
    from openflowsheet.records.store import RecordStore

    root, first, seed, go = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
    numbers = list(range(first, first + 200))
    random.Random(seed).shuffle(numbers)
    outcomes = []
    for n in numbers:
        outcome = identify({
            "record_format": "openflowsheet-record-v2", "record_type": "component",
            "type_version": "1.0.0", "id": f"C{n}", "name": f"compound {n}",
            "sources": {"s": {"version": "1"}}, "synthetic": True, "amount_basis": "mol",
            "charge": 0, "elemental_verification": "NOT_APPLICABLE",
            "molar_mass": {"value": 0.05, "unit": "kg/mol", "kind": "molar_mass",
                           "provenance": {"origin": ["synthetic"], "derivation": "direct",
                                          "source": "s"}},
        })
        assert not outcome.errors, outcome.errors
        outcomes.append(outcome)
    store = RecordStore.at(root)
    while not go.exists():
        time.sleep(0.001)
    started = time.monotonic()
    for outcome in outcomes:
        store.register(outcome, principal=f"worker{first}")
    print(started, time.monotonic())
    """
)


def test_e_f3_8_two_processes_register_200_overlapping_records(tmp_path: Path) -> None:
    script = tmp_path / "worker.py"
    script.write_text(_WORKER, encoding="utf-8")
    root = tmp_path / "project"
    go = tmp_path / "go"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(REPO_ROOT / "src"), env.get("PYTHONPATH", "")) if p
    )
    workers = [
        subprocess.Popen(
            [sys.executable, str(script), str(root), str(first), str(seed), str(go)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        for first, seed in ((0, 1), (100, 2))
    ]
    time.sleep(3.0)  # both workers identify their records, then wait for `go`
    go.touch()
    results = [worker.communicate(timeout=300) for worker in workers]
    assert [(w.returncode, err) for w, (_, err) in zip(workers, results, strict=True)] == [
        (0, ""),
        (0, ""),
    ]
    spans = [[float(t) for t in out.split()] for out, _ in results]
    assert max(s for s, _ in spans) < min(e for _, e in spans)  # the registrations overlapped
    files = _object_files(root)
    assert not [p for p in files if p.name.startswith(TMP_PREFIX)]
    assert len(files) == 300
    for path in files:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == path.stem
    store = RecordStore.at(root)
    assert sorted(row.sha for row in store.objects()) == sorted(p.stem for p in files)
    assert store.rebuild() == ()
    connection = sqlite3.connect(root / "records" / DATABASE_NAME)
    try:
        assert connection.execute("SELECT COUNT(*) FROM registrations").fetchone() == (300,)
        assert connection.execute("SELECT COUNT(DISTINCT sha) FROM keys").fetchone() == (300,)
    finally:
        connection.close()


def _replace_failing(exception: type[OSError], target_bytes: bytes | None) -> Any:
    """An `os.replace` that behaves as Windows does while another process holds the target
    open: the other writer's target appears (`target_bytes`, unless `None`), then it raises."""

    def replace(source: Any, destination: Any) -> None:
        if target_bytes is not None:
            Path(destination).write_bytes(target_bytes)
        raise exception(13, "simulated: the target is open in another process")

    return replace


@pytest.mark.parametrize("exception", [PermissionError, FileExistsError])
def test_e_f3_8_windows_replace_failure_with_a_valid_target_is_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exception: type[OSError]
) -> None:
    outcome = identify(_component("W", "Water"))
    assert outcome.record_sha256 is not None
    store = RecordStore.at(tmp_path, windows=True, long_paths=False)
    monkeypatch.setattr(os, "replace", _replace_failing(exception, canonical_json(outcome.record)))
    registration = store.register(outcome, principal="p")
    assert (registration.record_sha256, registration.created) == (outcome.record_sha256, False)
    assert [p.stem for p in _object_files(tmp_path)] == [outcome.record_sha256]  # tmp removed
    assert store.record(outcome.record_sha256) == outcome.record


@pytest.mark.parametrize("exception", [PermissionError, FileExistsError])
def test_e_f3_8_windows_replace_failure_with_a_corrupt_target_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exception: type[OSError]
) -> None:
    outcome = identify(_component("W", "Water"))
    store = RecordStore.at(tmp_path, windows=True, long_paths=False)
    monkeypatch.setattr(os, "replace", _replace_failing(exception, b"{}"))
    with pytest.raises(RecordStoreError) as caught:
        store.register(outcome, principal="p")
    assert _code(caught.value) == ("store_object_corrupt", {"sha": outcome.record_sha256})
    assert store.objects() == []  # the object is written before its rows (N7)


def test_e_f3_8_windows_replace_failure_without_a_target_is_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RecordStore.at(tmp_path, windows=True, long_paths=False)
    monkeypatch.setattr(os, "replace", _replace_failing(PermissionError, None))
    with pytest.raises(PermissionError):
        store.register(identify(_component("W", "Water")), principal="p")


def test_e_f3_8_a_failing_unlink_of_the_temporary_file_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W1 P1 review N7: once the target is verified, a temporary file that cannot be removed is
    left behind, and a rebuild skips it."""
    outcome = identify(_component("W", "Water"))
    store = RecordStore.at(tmp_path, windows=True, long_paths=False)
    monkeypatch.setattr(
        os, "replace", _replace_failing(PermissionError, canonical_json(outcome.record))
    )

    def unlink(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "simulated: in use")

    monkeypatch.setattr(Path, "unlink", unlink)
    assert store.register(outcome, principal="p").created is False
    monkeypatch.undo()
    names = [p.name for p in _object_files(tmp_path)]
    assert len(names) == 2 and sum(n.startswith(TMP_PREFIX) for n in names) == 1
    assert store.rebuild() == ()
    assert [row.sha for row in store.objects()] == [outcome.record_sha256]


def test_e_f3_8_the_object_is_written_before_its_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N7: a failure while writing the rows leaves the object and no row; a retry completes."""
    store = RecordStore.at(tmp_path)
    outcome = identify(_component("W", "Water"))

    def failing_index(self: RecordStore, sha: str, record: Any) -> None:
        raise sqlite3.OperationalError("simulated")

    monkeypatch.setattr(RecordStore, "_index", failing_index)
    with pytest.raises(sqlite3.OperationalError):
        store.register(outcome, principal="p")
    monkeypatch.undo()
    assert [p.stem for p in _object_files(tmp_path)] == [outcome.record_sha256]
    assert store.objects() == []
    assert store.register(outcome, principal="p").created is False
    assert [row.sha for row in store.objects()] == [outcome.record_sha256]


def test_e_f3_8_path_length_boundary() -> None:
    """D8: `len(root) + 92 > 259` on Windows with long paths off: 168 refused, 167 not."""
    at_167, at_168 = Path("/" + "a" * 166), Path("/" + "a" * 167)
    assert (len(str(at_167)), len(str(at_168))) == (167, 168)
    assert path_too_long(at_167, windows=True, long_paths=False) is None
    assert path_too_long(at_168, windows=True, long_paths=False) == Coded(
        "store_path_too_long", {"root": str(at_168)}
    )
    assert path_too_long(at_168, windows=True, long_paths=True) is None
    assert path_too_long(at_168, windows=False, long_paths=False) is None


def _root_of_length(tmp_path: Path, length: int) -> Path:
    base = tmp_path.resolve()
    root = base / ("p" * (length - len(str(base)) - 1))
    assert len(str(root.resolve())) == length
    return root


@pytest.mark.parametrize(("length", "refused"), [(167, False), (168, True)])
def test_e_f3_8_path_length_is_checked_lazily_at_the_first_operation(
    tmp_path: Path, length: int, refused: bool
) -> None:
    """D8, review item 21: constructing the store touches nothing; the first operation checks
    the absolute resolved root."""
    root = _root_of_length(tmp_path, length)
    store = RecordStore.at(root, windows=True, long_paths=False)
    assert not root.exists()
    outcome = identify(_component("W", "Water"))
    if not refused:
        assert store.register(outcome, principal="p").created is True
        return
    with pytest.raises(RecordStoreError) as caught:
        store.register(outcome, principal="p")
    assert _code(caught.value) == ("store_path_too_long", {"root": str(root.resolve())})
    assert not root.exists()


def test_e_f3_8_registrations_keep_each_submissions_findings(tmp_path: Path) -> None:
    """F3-WO1 review N1: a defaulted and a stated `ig` anchor share one SHA; the notice belongs
    to the submission. The first registration of one (record, volatile) pair is kept; another
    volatile block adds a row."""
    store = RecordStore.at(tmp_path)
    defaulted = _component("W", "Water")
    stated = dict(defaulted, anchor_phase="ig")
    first = store.register(identify(defaulted), principal="a", at="2026-11-18T00:00:00Z")
    second = store.register(identify(stated), principal="b", at="2026-11-18T00:00:01Z")
    assert first.record_sha256 == second.record_sha256
    assert first.findings == (Coded("anchor_defaulted", {"component": "W"}),)
    assert second.findings == ()
    fetched = dict(stated, volatile={"host": "elsewhere"})
    third = store.register(identify(fetched), principal="c", at="2026-11-18T00:00:02Z")
    assert third.record_sha256 == first.record_sha256
    rows = store.registrations(first.record_sha256)
    assert [(r["principal"], r["volatile"], r["findings"]) for r in rows] == [
        ("a", {}, [{"code": "anchor_defaulted", "params": {"component": "W"}}]),
        ("c", {"host": "elsewhere"}, []),
    ]


def test_e_f3_8_a_refused_record_is_not_stored(tmp_path: Path) -> None:
    store = RecordStore.at(tmp_path)
    record = _component("W", "Water", cas="7732-18-4")  # wrong check digit
    with pytest.raises(RecordStoreError) as caught:
        store.register(identify(record), principal="p")
    assert _code(caught.value) == ("identifier_invalid", {"component": "W", "scheme": "cas"})
    assert not (tmp_path / "records").exists() or _object_files(tmp_path) == []


def test_e_f3_8_in_memory_store() -> None:
    store = RecordStore.in_memory()
    outcome = identify(_component("W", "Water"))
    assert store.register(outcome, principal="p").created is True
    assert store.register(outcome, principal="p").created is False
    assert outcome.record_sha256 is not None
    assert store.record(outcome.record_sha256) == outcome.record
    assert store.rebuild() == ()
    assert len(store.objects()) == 1


# ---------------------------------------------------------------------------------- the stack


def test_stack_reads_through_and_copies_legacy_records(tmp_path: Path) -> None:
    """D8: reads go project then legacy; registering or adopting a legacy record copies it
    into the project store; an absent SHA is `data_unavailable`."""
    legacy_records = [_component("L1", "Legacy one"), _component("L2", "Legacy two")]
    projections = [dict(identify(r).record) for r in legacy_records]
    calls: list[int] = []

    def loader() -> list[dict[str, Any]]:
        calls.append(1)
        return projections

    stack = StoreStack(RecordStore.at(tmp_path), LegacyStore(loader))
    shas = [identify(r).record_sha256 for r in legacy_records]
    assert calls == []
    assert stack.record(str(shas[0])) == projections[0]
    assert resolve(stack, "id:L2") == shas[1]
    assert calls == [1]
    assert _object_files(tmp_path) == []
    assert stack.adopt(str(shas[1])) is True
    assert stack.adopt(str(shas[1])) is False
    assert _register(stack, legacy_records[0]) == shas[0]
    assert sorted(p.stem for p in _object_files(tmp_path)) == sorted(str(s) for s in shas)
    missing = "0" * 64
    with pytest.raises(RecordStoreError) as caught:
        stack.record(missing)
    assert _code(caught.value) == ("data_unavailable", {"sha": missing})
    with pytest.raises(RecordStoreError) as caught:
        stack.adopt(missing)
    assert _code(caught.value) == ("data_unavailable", {"sha": missing})


# --------------------------------------------------------------------------- E-F3-9 resolution


def _stack(*records: dict[str, Any]) -> tuple[StoreStack, list[str]]:
    store = RecordStore.in_memory()
    return StoreStack(store), [_register(store, r) for r in records]


def test_e_f3_9_two_sources_of_one_inchikey_are_source_ambiguous() -> None:
    stack, shas = _stack(
        _component("W1", "Water", source="a", inchikey=WATER_KEY),
        _component("W2", "water", source="b", inchikey=WATER_KEY, cas=WATER_CAS),
    )
    found = resolve(stack, WATER_KEY)
    assert isinstance(found, Ambiguous)
    assert found.refusal == Coded("component_ambiguous", {"key": WATER_KEY})
    assert found.detail["ambiguity"] == "source"
    by_sha = {sha: ident for sha, ident in zip(shas, ("a", "b"), strict=True)}
    assert found.detail["candidates"] == [
        {
            "class": [f"cas:{WATER_CAS}", f"inchikey:{WATER_KEY}"],
            "records": [
                {
                    "sha": sha,
                    "source_ids": [by_sha[sha]],
                    "name": "Water" if by_sha[sha] == "a" else "water",
                }
                for sha in sorted(shas)
            ],
        }
    ]


def test_e_f3_9_one_formula_for_two_compounds_is_identity_ambiguous() -> None:
    stack, shas = _stack(
        _component("EtOH", "ethanol", inchikey=ETHANOL_KEY, formula="C2H5OH"),
        _component("DME", "dimethyl ether", inchikey=DME_KEY, formula="CH3OCH3"),
    )
    assert search(stack, "C2H6O").scheme == "formula"
    found = resolve(stack, "C2H6O")
    assert isinstance(found, Ambiguous)
    assert found.detail["ambiguity"] == "identity"
    assert len(found.detail["candidates"]) == 2
    assert sorted(c["records"][0]["sha"] for c in found.detail["candidates"]) == sorted(shas)
    assert resolve(stack, f"inchikey:{ETHANOL_KEY}") == shas[0]
    assert resolve(stack, ETHANOL_KEY) == shas[0]


def test_e_f3_9_a_unique_key_resolves_and_sha256_is_exact() -> None:
    stack, shas = _stack(
        _component("W", "Water", cas=WATER_CAS, inchikey=WATER_KEY, formula="H2O"),
        _component("EtOH", "ethanol", inchikey=ETHANOL_KEY),
    )
    for query in (WATER_KEY, WATER_CAS, "W", "water", " WATER ", "formula:H2O", "H2O"):
        assert resolve(stack, query) == shas[0], query
    assert resolve(stack, f"sha256:{shas[1]}") == shas[1]
    assert resolve(stack, f"sha256:{shas[1][:-1]}") is None
    assert resolve(stack, "nothing") is None


def test_e_f3_9_a_synthetic_analogue_of_methanol_across_two_sources() -> None:
    """The source-checkout case on synthetic records: one record with a CAS, one with the name
    only. `methanol` is two identity classes; `cas:` and `id:` each resolve one."""
    stack, shas = _stack(
        _component("Methanol", "Methanol", source="x.s07", cas=METHANOL_CAS),
        _component("CH3OH", "methanol", source="x.s10"),
    )
    found = resolve(stack, "methanol")
    assert isinstance(found, Ambiguous)
    assert found.detail["ambiguity"] == "identity"
    assert [c["class"] for c in found.detail["candidates"]] == [[f"cas:{METHANOL_CAS}"], []]
    assert resolve(stack, f"cas:{METHANOL_CAS}") == shas[0]
    assert resolve(stack, "id:CH3OH") == shas[1]


def test_e_f3_9_methanol_in_a_source_checkout() -> None:
    """E-F3-9 in a source checkout: `methanol` is `component_ambiguous`, ambiguity `identity`,
    two classes (`s07`'s `Methanol`, CAS 67-56-1; `s10`'s `CH3OH`, name `methanol`, no
    identifiers); `cas:67-56-1` resolves to the `s07` record and `id:CH3OH` to the `s10` one."""
    stack = StoreStack(RecordStore.in_memory(), LegacyStore(legacy.available_records))
    found = resolve(stack, "methanol")
    assert isinstance(found, Ambiguous)
    assert found.refusal == Coded("component_ambiguous", {"key": "methanol"})
    assert found.detail["ambiguity"] == "identity"
    candidates = found.detail["candidates"]
    assert [c["class"] for c in candidates] == [[f"cas:{METHANOL_CAS}"], []]
    named = [[(r["name"], r["source_ids"]) for r in c["records"]] for c in candidates]
    assert named == [[("Methanol", ["legacy.s07"])], [("methanol", ["legacy.s10"])]]
    s07 = stack.record(str(resolve(stack, f"cas:{METHANOL_CAS}")))
    assert (s07["id"], s07["legacy"]["file"]) == ("Methanol", COOLPROP_RECORDS)
    s10 = stack.record(str(resolve(stack, "id:CH3OH")))
    assert (s10["name"], s10["legacy"]["file"], "identifiers" in s10) == (
        "methanol",
        WILSON_RECORDS,
        False,
    )


def test_e_f3_9_classes_join_through_shared_cas_or_inchikey() -> None:
    """D9: `l01`'s H2O (InChIKey and CAS) and two CAS-only records are one class; the join is
    transitive."""
    records = {
        "a": {"identifiers": {"inchikey": WATER_KEY, "cas": WATER_CAS}},
        "b": {"identifiers": {"cas": WATER_CAS}},
        "c": {"identifiers": {"cas": WATER_CAS}},
        "d": {"identifiers": {"inchikey": "X"}},
        "e": {"identifiers": {"cas": "1-1-1"}},
        "f": {"identifiers": {"cas": "1-1-1", "inchikey": "X"}},
        "g": {},
        "h": {},
    }
    assert identity_classes(records) == [["a", "b", "c"], ["d", "e", "f"], ["g"], ["h"]]


def test_e_f3_9_bare_query_order_and_key_spelling() -> None:
    assert [s for s, _ in query_keys(WATER_KEY)] == ["inchikey", "id", "name", "formula"]
    assert [s for s, _ in query_keys(WATER_CAS)] == ["cas", "id", "name", "formula"]
    assert [s for s, _ in query_keys("Water")] == ["id", "name", "formula"]
    assert query_keys("name:  Dihydrogen   OXIDE ") == (("name", "dihydrogen oxide"),)
    assert [s for s, _ in query_keys("unknown:x")] == ["id", "name", "formula"]
    assert name_key("Café") == name_key("CAFÉ") == "café"
    assert [formula_key(f) for f in ("CH3OH", "HCl", "ClH", "NaCl", "CO2", "H2O")] == [
        "CH4O",
        "ClH",
        "ClH",
        "ClNa",
        "CO2",
        "H2O",
    ]
    stack, shas = _stack(
        _component("Water", "aqua", synonyms=("Water",)),
        _component("W2", "Water"),
    )
    assert resolve(stack, "Water") == shas[0]  # `id` is tried before `name`
    assert search(stack, "name:water") == (
        "name",
        tuple(sorted(shas)),
    )


def test_e_f3_9_resolution_reads_components_only_and_search_lists_every_type() -> None:
    stack, shas = _stack(_parameter_set("P", "pair"), _component("C", "pair"))
    assert resolve(stack, "pair") == shas[1]
    assert resolve(stack, "id:P") is None
    assert resolve(stack, "id:P", record_type="parameter_set") == shas[0]
    assert search(stack, "pair").shas == tuple(sorted(shas))


def test_e_f3_9_candidates_do_not_depend_on_registration_order() -> None:
    records = [
        _component(f"M{n}", "methanol", source=f"s{n}", **({"cas": METHANOL_CAS} if n % 2 else {}))
        for n in range(6)
    ]
    details = []
    for seed in range(3):
        shuffled = list(records)
        random.Random(seed).shuffle(shuffled)
        found = resolve(_stack(*shuffled)[0], "methanol")
        assert isinstance(found, Ambiguous)
        details.append(canonical_json(found.detail))
    assert len(set(details)) == 1
    detail = json.loads(details[0])
    assert detail["ambiguity"] == "identity"
    assert [len(c["records"]) for c in detail["candidates"]] == [3, 1, 1, 1]
