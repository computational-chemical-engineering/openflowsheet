"""M07a.A43, A44 and §8.3 (V02 alpha release spec) at 0.2.0's candidate `C′` (M07 spec §24.7
action 8), and R-375's kept G11 experiment records (W21 (e), alpha spec §19.6 A6).

`tests/test_m07a_rc_records.py` judges the alpha candidate `C_α²` and is not edited (R-461, R-475);
this module is its pattern for `C′`. `docs/v02-rc-record.md` cites each record of the RC by its
sha256; `evidence/M07/<C′>/rc/records.json` lists every cited record with its sha256, size and
whether it is committed as is (1 MB or less) or gzip-compressed beside its path. Here: the per-step
table's hashes are exactly the listed ones, each listed record sits on the row that cites it,
every committed file hashes to its entry (a compressed one after decompression), the size rule
holds both ways and the directory holds nothing else. Then A43 over every committed `t08-rc-v1`
and `t08-a43-dist-v1` record and every kept G11 experiment record (`commit` = `C′`,
`tree_clean`, the lock's SHA-256, a registered `machine_class` that agrees with the record), A44
over `release/rc-trees/<C′>.json`, and R-375: G11's two runs at `C′` kept, bound to the re-run's
runs file, and audited by `scripts/m07_g11_experiments_audit.py`.
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
from openflowsheet.adapters import variants

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07_g11_experiments_audit as audit  # noqa: E402
import v0_1_gate  # noqa: E402

#: `C′` (M07 spec Amendment 7 §24.6, R-484).
RC = "ce993651ce37c1343e771b276160bd6623e43500"
RECORDS = REPO_ROOT / "evidence" / "M07" / RC / "rc"
ARTIFACTS = REPO_ROOT / "evidence" / "M07" / RC / "artifacts" / "rc"
RC_RECORD = REPO_ROOT / "docs" / "v02-rc-record.md"
SHA256 = re.compile(r"`([0-9a-f]{64})`")
#: `requirements.lock` at `C′` (unchanged since `C_α`).
LOCK_SHA256 = "ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4"
#: R-375: G11's experiment records of each run, and the re-run's own G11 record and runs file.
EXPERIMENTS = "step12/experiments"
RUN_RECORDS = tuple(f"{EXPERIMENTS}/g11-experiments-run{k}.json" for k in (1, 2))
VARIANT_FILE = REPO_ROOT / "benchmarks" / "m02" / "variant-v3-provisional.json"


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


def _listed(path: str) -> Any:
    """A listed record's document, read from its committed copy (decompressed if need be)."""
    (entry,) = [e for e in _index()["files"] if e["path"] == path]
    if entry["committed"]:
        raw = (RECORDS / path).read_bytes()
    else:
        raw = gzip.decompress((RECORDS / f"{path}.gz").read_bytes())
    return json.loads(raw)


def test_the_index_is_of_this_candidate_and_this_record() -> None:
    index = _index()
    assert index["format"] == "m07a-rc-records-v1"
    assert index["commit"] == RC
    assert index["rc_record"] == "docs/v02-rc-record.md"
    text = RC_RECORD.read_text(encoding="utf-8")
    assert re.findall(r"`C` = `([0-9a-f]{40})`", text) == [RC]


def test_every_step_1_to_17_has_a_row() -> None:
    steps = {int(cells[0]) for cells in _rows()}
    assert steps == set(range(1, 18))


def test_every_hash_of_the_per_step_table_is_listed_and_nothing_else() -> None:
    """Each listed record is cited once; byte-identical records share a hash, so the comparison
    is of multisets (build decision B-AM2-10)."""
    cited = [digest for cells in _rows() for digest in SHA256.findall(cells[-1])]
    listed = [entry["sha256"] for entry in _index()["files"]]
    assert len({entry["path"] for entry in _index()["files"]}) == len(listed)
    assert sorted(listed) == sorted(cited)


def test_each_listed_record_sits_on_the_row_that_cites_it() -> None:
    """The row's Record cell names the path, or a sibling in its directory."""
    by_hash: dict[str, list[str]] = {}
    for entry in _index()["files"]:
        by_hash.setdefault(entry["sha256"], []).append(entry["path"])
    for cells in _rows():
        for digest in SHA256.findall(cells[-1]):
            for path in by_hash[digest]:
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
            if local.is_file():  # on the host that ran the RC only (git-ignored)
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
    """Every committed record that carries a provenance block: the RC steps' and R-375's."""
    found: dict[str, dict[str, Any]] = {}
    for entry in _index()["files"]:
        if not entry["path"].endswith(".json"):
            continue
        document = _listed(entry["path"])
        if isinstance(document, dict) and document.get("format") in (
            "t08-rc-v1",
            "t08-a43-dist-v1",
            audit.FORMAT,
        ):
            found[entry["path"]] = document
    return found


def _machine_class(document: dict[str, Any]) -> Any:
    """In the provenance block, or beside it (`t08_rc.py identity` writes it in the body)."""
    return (document.get("provenance") or {}).get("machine_class") or document.get("machine_class")


def test_a43_every_record_carries_commit_tree_clean_and_the_lock() -> None:
    records = _rc_records()
    assert set(RUN_RECORDS) <= set(records)
    for path, document in records.items():
        provenance = document.get("provenance") or document
        assert provenance.get("commit") == RC, path
        assert provenance.get("tree_clean") is True, path
        assert provenance.get("environment_lock_sha256") == LOCK_SHA256, path


def test_a43_every_record_carries_a_registered_class_that_agrees() -> None:
    """R-347 (alpha spec §18.5 item 2): no record without a class; a class agrees with the
    record's own architecture and CI flag."""
    records = _rc_records()
    assert all(_machine_class(document) for document in records.values())
    classes = {_machine_class(document) for document in records.values()}
    assert classes == {"ref-x86-64", "ci-x86-64", "ci-aarch64"}
    registered = ensemble.registered()["machine_classes"]
    for path, document in records.items():
        provenance = document.get("provenance") or document
        entry = registered[_machine_class(document)]
        architecture = provenance.get("architecture") or document.get("machine")
        if architecture is not None:
            assert architecture == entry["architecture"], path
        if "github_actions" in provenance:
            assert provenance["github_actions"] == entry["github_actions"], path


def test_a44_the_tree_record_is_c_primes_byte_for_byte() -> None:
    path = REPO_ROOT / v0_1_gate.RC_TREES / f"{RC}.json"
    record = v0_1_gate.tree_record(RC)
    assert record["trees"] == list(v0_1_gate.TREES)
    assert path.read_text(encoding="utf-8") == json.dumps(record, indent=1, sort_keys=True) + "\n"


# -- R-375: G11's experiment records at C′, kept and audited -------------------------------------


def test_r375_both_runs_are_kept_and_bound_to_the_re_runs_runs_file() -> None:
    runs_path = f"{EXPERIMENTS}/g11-coverage-v3.runs.json"
    (entry,) = [e for e in _index()["files"] if e["path"] == runs_path]
    runs = _listed(runs_path)
    record = _listed(f"{EXPERIMENTS}/g11-coverage-v3.json")
    assert len(runs) == 2 and all(len(run) == 121 for run in runs)
    assert record["summary"]["G11v3-5"]["runs"] == 2
    assert record["summary"]["G11v3-5"]["points_per_run"] == 121
    for k, path in enumerate(RUN_RECORDS, start=1):
        document = _listed(path)
        assert document["format"] == audit.FORMAT
        assert document["run"] == k
        assert document["runs_file_sha256"] == entry["sha256"]
        assert [p["label"] for p in document["points"]] == [p["label"] for p in runs[k - 1]]


def test_r375_every_result_and_its_attempts_pass_the_six_items() -> None:
    """Measured at C′: 105 boundary points per run (89 `ok`, 14 ended at `S1`, 2 at
    `certificate`), one experiment each with one attempt and a result; 16 direct points per run
    have no experiment records. The only schema findings are the 420 `job_id`s G11 names
    `m02-g11v3-<label>` (one per result and per attempt): context, reported apart (J78)."""
    variant = variants.variant_from_document(json.loads(VARIANT_FILE.read_text("utf-8")))
    runs = _listed(f"{EXPERIMENTS}/g11-coverage-v3.runs.json")
    report = audit.audit([_listed(path) for path in RUN_RECORDS], variant, runs)
    assert report["structural"] == []
    assert {item: v["problems"] for item, v in report["items"].items()} == dict.fromkeys(
        audit.ITEMS, 0
    )
    assert report["counts"] == {
        "runs": 2,
        "points": 242,
        "boundary_points": 210,
        "direct_points": 32,
        "experiments": 210,
        "results": 210,
        "attempts": 210,
        "without_result": 0,
    }
    assert report["context"]["findings"] == 420
    assert report["context"]["where"] == ["attempt job_id", "result produced_by/job_id"]
    assert report["passed"] is True
