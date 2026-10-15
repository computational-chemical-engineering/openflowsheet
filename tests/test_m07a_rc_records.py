"""M07a.A43, A44 and §8.3 (V02 alpha release spec): the alpha RC record's hashes resolve to
committed records, every record carries its provenance, and the tree record is `C_α`'s.

`docs/v02-alpha-rc-record.md` cites each record of the RC job by its sha256. §8.3 (T08 Amendments
R7 1 and R8 1's form) puts the records of 1 MB or less under `evidence/M07a/<C_α>/rc/`, outside the
trees ADR 0021 D2.4 compares, and a larger one gzip-compressed beside its path; `rc/records.json`
lists every cited record with its sha256, size and whether it is committed as is. Here, as
`tests/test_t08_rc_records.py` checks T08's: the per-step table's hashes are exactly the listed
ones, each listed record sits on the row that cites it, every committed file hashes to its entry
(a compressed one after decompression), and the size rule holds both ways. Then A43 over every
committed `t08-rc-v1` record, A39's step-12 certificates (R-348), and A44 over
`release/rc-trees/<C_α>.json`.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from conftest import REPO_ROOT

from benchmarks.t06 import ensemble

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07a_evidence_manifest  # noqa: E402
import v0_1_gate  # noqa: E402

#: `C_α¹` (spec Amendment 2 §18.4, R-349); `C_α⁰` = `e0e198e`'s evidence is kept, not tested here.
RC = "6fec82232e1c47308a5e1d67338058f352992800"
RECORDS = REPO_ROOT / "evidence" / "M07a" / RC / "rc"
ARTIFACTS = REPO_ROOT / "evidence" / "M07a" / RC / "artifacts" / "rc"
RC_RECORD = REPO_ROOT / "docs" / "v02-alpha-rc-record.md"
SHA256 = re.compile(r"`([0-9a-f]{64})`")
#: `requirements.lock` at `C_α` (T08.A40's value, unchanged).
LOCK_SHA256 = "ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4"
#: The records without a `machine_class`. At `C_α⁰` these were the 13 records of `t08_rc.py`'s
#: `install-check`, `lock-check`, `certificates` and `t08_dist.py` (build decision B-WO10-10); R-347
#: (spec §18.3) adds the member to those four writers, so at `C_α¹` the set is empty (§18.5 item 2).
NO_MACHINE_CLASS: frozenset[str] = frozenset()


def _index() -> dict[str, Any]:
    loaded = json.loads((RECORDS / "records.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _rows() -> list[list[str]]:
    """The per-step table's data rows, as cells."""
    text = RC_RECORD.read_text(encoding="utf-8")
    table = text[text.index("| Step | Assertion") : text.index("**M07a.A43")]
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in table.splitlines()[2:]
        if line.startswith("| ")
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_index_is_of_this_candidate_and_this_record() -> None:
    index = _index()
    assert index["format"] == "m07a-rc-records-v1"
    assert index["commit"] == RC
    assert index["rc_record"] == "docs/v02-alpha-rc-record.md"
    text = RC_RECORD.read_text(encoding="utf-8")
    assert re.findall(r"`C` = `([0-9a-f]{40})`", text) == [RC]


def test_every_step_1_to_12_has_a_row() -> None:
    steps = {int(cells[0]) for cells in _rows()}
    assert steps == set(range(1, 13))


def test_every_hash_of_the_per_step_table_is_listed_and_nothing_else() -> None:
    """Each listed record is cited once. Byte-identical records share a hash (at `C_α¹`, step 12's
    `m02-g12-0` bundle, live and replay certificates, R-348), so the comparison is of multisets:
    a hash appears in the table as often as the index lists it (build decision B-AM2-10)."""
    cited = [digest for cells in _rows() for digest in SHA256.findall(cells[-1])]
    listed = [entry["sha256"] for entry in _index()["files"]]
    assert len({entry["path"] for entry in _index()["files"]}) == len(listed)
    assert sorted(listed) == sorted(cited)


def test_each_listed_record_sits_on_the_row_that_cites_it() -> None:
    """The row's Record cell names the path, or a sibling in its directory (the record's
    shorthand: `.report.txt` after a run file, `summary` after an inventory)."""
    by_hash: dict[str, list[str]] = {}
    for entry in _index()["files"]:
        by_hash.setdefault(entry["sha256"], []).append(entry["path"])
    for cells in _rows():
        for digest in SHA256.findall(cells[-1]):
            for path in by_hash[digest]:  # a shared hash: every record that has it, on this row
                directory = path.rpartition("/")[0]
                named = f"`{path}`" in cells[-2] or (directory and f"`{directory}/" in cells[-2])
                assert named, (cells[:2], path)


def test_committed_records_hash_to_their_entries_and_the_size_rule_holds() -> None:
    index = _index()
    limit = index["size_limit_bytes"]
    assert limit == 1_000_000
    for entry in index["files"]:
        committed = RECORDS / entry["path"]
        assert entry["committed"] == (entry["bytes"] <= limit), entry["path"]
        if entry["committed"]:
            assert committed.is_file(), entry["path"]
            assert committed.stat().st_size == entry["bytes"], entry["path"]
            assert _sha256(committed) == entry["sha256"], entry["path"]
        else:
            assert not committed.exists(), entry["path"]
            compressed = RECORDS / f"{entry['path']}.gz"
            assert compressed.is_file(), entry["path"]
            raw = gzip.decompress(compressed.read_bytes())
            assert len(raw) == entry["bytes"], entry["path"]
            assert hashlib.sha256(raw).hexdigest() == entry["sha256"], entry["path"]
            local = ARTIFACTS / entry["path"]
            if local.is_file():  # on the host that ran the RC job only (git-ignored)
                assert _sha256(local) == entry["sha256"], entry["path"]


def test_the_directory_holds_only_the_listed_records() -> None:
    files = _index()["files"]
    listed = {entry["path"] for entry in files if entry["committed"]}
    listed |= {f"{entry['path']}.gz" for entry in files if not entry["committed"]}
    present = {
        path.relative_to(RECORDS).as_posix() for path in RECORDS.rglob("*") if path.is_file()
    }
    assert present == listed | {"records.json"}


def _rc_records() -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(RECORDS.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and document.get("format") in (
            "t08-rc-v1",
            "t08-a43-dist-v1",
        ):
            found[path.relative_to(RECORDS).as_posix()] = document
    return found


def _machine_class(document: dict[str, Any]) -> Any:
    """In the provenance block, or beside it (`t08_rc.py identity` writes it in the body)."""
    return (document.get("provenance") or {}).get("machine_class") or document.get("machine_class")


def test_a43_every_record_carries_commit_tree_clean_and_the_lock() -> None:
    records = _rc_records()
    assert records
    for path, document in records.items():
        provenance = document.get("provenance") or document
        assert provenance.get("commit") == RC, path
        assert provenance.get("tree_clean") is True, path
        assert provenance.get("environment_lock_sha256") == LOCK_SHA256, path


def test_a43_the_records_without_a_machine_class_are_the_known_ones() -> None:
    """The rest carry a registered class; the known exceptions are pinned, not passed."""
    records = _rc_records()
    missing = {path for path, document in records.items() if not _machine_class(document)}
    assert missing == NO_MACHINE_CLASS
    classes = {
        _machine_class(document) for path, document in records.items() if path not in missing
    }
    assert classes == {"ref-x86-64", "ci-x86-64", "ci-aarch64"}
    # R-347: a carried class agrees with the record's own architecture and CI flag.
    registered = ensemble.registered()["machine_classes"]
    for path, document in records.items():
        if path in missing:
            continue
        provenance = document.get("provenance") or document
        entry = registered[_machine_class(document)]
        architecture = provenance.get("architecture") or document.get("machine")
        if architecture is not None:
            assert architecture == entry["architecture"], path
        if "github_actions" in provenance:
            assert provenance["github_actions"] == entry["github_actions"], path


# -- A39: step 12's kept certificates (spec §18.2, R-348) ------------------------------------


def _mr11(evidence: Path) -> tuple[str, Any]:
    inputs = m07a_evidence_manifest.Inputs(commit=RC, tests=None, evidence=evidence)  # type: ignore[arg-type]
    return m07a_evidence_manifest._m_mr11_step12(inputs)  # noqa: SLF001


def test_a39_step12_certificates_are_committed_audited_counted_and_bound() -> None:
    result, value = _mr11(REPO_ROOT / "evidence" / "M07a")
    edges = json.loads((RECORDS / "step12" / "g12-real-loop-v3-edges.json").read_text("utf-8"))
    assert value["step12_certificates"] == value["step12_certificates_expected"]
    assert value["step12_certificates"] == 3 + len(edges["edges"]) == 5
    assert value["step12_violations"] == {}
    assert value["bundle_document_sha256"] == value["recorded_certificate_sha256"]
    assert result == "pass"


def _copy_for_a39(tmp_path: Path) -> Path:
    rc = tmp_path / RC / "rc"
    for path in [
        "certificates-ref-x86-64.json",
        "step12/g12-real-loop-v3.json",
        "step12/g12-real-loop-v3-edges.json",
        *(
            p.relative_to(RECORDS).as_posix()
            for p in (RECORDS / "step12" / "certificates").rglob("*.json")
        ),
    ]:
        (rc / path).parent.mkdir(parents=True, exist_ok=True)
        (rc / path).write_bytes((RECORDS / path).read_bytes())
    return rc / "step12" / "certificates"


def test_a39_fails_a_dropped_certificate(tmp_path: Path) -> None:
    kept = _copy_for_a39(tmp_path)
    (kept / "g12-bundles/m02-g12-0/live/solution-certificate.json").unlink()
    result, value = _mr11(tmp_path)
    assert (result, value["step12_certificates"], value["step12_certificates_expected"]) == (
        "fail",
        4,
        5,
    )


def test_a39_fails_a_bundle_certificate_that_does_not_bind(tmp_path: Path) -> None:
    kept = _copy_for_a39(tmp_path)
    bundle = kept / m07a_evidence_manifest.STEP12_BUNDLE
    document = json.loads(bundle.read_text("utf-8"))
    document["statements"] = [*document.get("statements", []), "edited after the run"]
    bundle.write_text(json.dumps(document), "utf-8")
    result, value = _mr11(tmp_path)
    assert result == "fail"
    assert value["bundle_document_sha256"] != value["recorded_certificate_sha256"]
    assert value["step12_violations"] == {}


def test_a39_fails_a_certificate_that_breaks_a34(tmp_path: Path) -> None:
    kept = _copy_for_a39(tmp_path)
    edge = kept / "g12-edges-bundles/m02-g12v3-2-0/bundle/solution-certificate.json"
    document = json.loads(edge.read_text("utf-8"))
    document["independence_qualifications"] = document["independence_qualifications"][1:]
    edge.write_text(json.dumps(document), "utf-8")
    result, value = _mr11(tmp_path)
    assert result == "fail"
    assert list(value["step12_violations"]) == [
        "g12-edges-bundles/m02-g12v3-2-0/bundle/solution-certificate.json"
    ]


# -- the generator's A43 measurement (`scripts/m07a_evidence_manifest.py`, R-347) --------------


def _provenance_of(
    tmp_path: Path,
    records: dict[str, dict[str, Any]],
    dist: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, Any]:
    """A43 over constructed records: `records` in the `t08-rc-v1` form (a `provenance` block),
    `dist` in `t08_dist.py`'s form (`t08-a43-dist-v1`, the members at top level, `machine`)."""
    commit = "c" * 40
    rc = tmp_path / commit / "rc"
    lock = _sha256(REPO_ROOT / "requirements.lock")
    provenance = {"commit": commit, "tree_clean": True, "environment_lock_sha256": lock}
    documents: dict[str, dict[str, Any]] = {
        name: {"format": "t08-rc-v1", "provenance": {**provenance, **members}}
        for name, members in records.items()
    }
    for name, members in (dist or {}).items():
        documents[name] = {"format": "t08-a43-dist-v1", **provenance, **members}
    for name, document in documents.items():
        (rc / name).parent.mkdir(parents=True, exist_ok=True)
        (rc / name).write_text(json.dumps(document), encoding="utf-8")
    inputs = m07a_evidence_manifest.Inputs(commit=commit, tests=None, evidence=tmp_path)  # type: ignore[arg-type]
    return m07a_evidence_manifest._m_provenance(inputs)  # noqa: SLF001


def test_a43_generator_passes_registered_agreeing_classes(tmp_path: Path) -> None:
    result, value = _provenance_of(
        tmp_path,
        {
            "a.json": {"machine_class": "ref-x86-64", "architecture": "x86_64"},
            "b.json": {
                "machine_class": "ci-aarch64",
                "architecture": "aarch64",
                "github_actions": True,
            },
        },
    )
    assert (result, value["records"]) == ("pass", 2)


def test_a43_generator_fails_a_missing_unregistered_or_disagreeing_class(tmp_path: Path) -> None:
    result, value = _provenance_of(
        tmp_path,
        {
            "good.json": {"machine_class": "ci-x86-64", "github_actions": True},
            "none.json": {"architecture": "x86_64"},
            "unregistered.json": {"machine_class": "unregistered(x86_64)"},
            "architecture.json": {"machine_class": "ci-aarch64", "architecture": "x86_64"},
            "ci.json": {"machine_class": "ref-x86-64", "github_actions": True},
        },
    )
    assert result == "fail"
    assert value["no_machine_class"] == ["none.json"]
    assert value["unregistered_machine_class"] == ["unregistered.json"]
    assert value["machine_class_disagrees"] == ["architecture.json", "ci.json"]
    assert value["not_attributable"] == []


def test_a43_generator_passes_a_dist_record_whose_class_agrees(tmp_path: Path) -> None:
    # Review S1 (docs/reviews/V02-alpha-am2-read.md): the dist record's class sits at top level,
    # beside `machine`, and the record has no `CI` flag, so only the architecture is compared.
    result, value = _provenance_of(
        tmp_path,
        {},
        dist={"ci/rc-dist/t08-a43-dist.json": {"machine": "x86_64", "machine_class": "ci-x86-64"}},
    )
    assert (result, value["records"]) == ("pass", 1)


def test_a43_generator_fails_a_dist_record_whose_class_disagrees(tmp_path: Path) -> None:
    result, value = _provenance_of(
        tmp_path,
        {},
        dist={
            "ci/rc-dist/t08-a43-dist.json": {"machine": "x86_64", "machine_class": "ci-aarch64"},
            "none/t08-a43-dist.json": {"machine": "x86_64"},
        },
    )
    assert result == "fail"
    assert value["machine_class_disagrees"] == ["ci/rc-dist/t08-a43-dist.json"]
    assert value["no_machine_class"] == ["none/t08-a43-dist.json"]
    assert (value["unregistered_machine_class"], value["not_attributable"]) == ([], [])


def test_a44_the_tree_record_is_c_alphas_byte_for_byte() -> None:
    path = REPO_ROOT / v0_1_gate.RC_TREES / f"{RC}.json"
    record = v0_1_gate.tree_record(RC)
    assert record["trees"] == list(v0_1_gate.TREES)
    assert path.read_text(encoding="utf-8") == json.dumps(record, indent=1, sort_keys=True) + "\n"
