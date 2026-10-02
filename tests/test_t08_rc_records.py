"""T08 close (release spec §8.1 item 4 as amended by Amendment R7 1; verdict finding G6): the RC
record's hashes resolve to committed records.

`docs/t08-rc-record.md` cites each record of the RC job by its sha256. Amendment R7 1 puts the
records of 1 MB or less under `evidence/T08/<C>/rc/`, outside the trees ADR 0021 D2.4 compares,
and `rc/records.json` lists every cited record with its sha256, size and whether it is committed;
a larger one stays git-ignored under `evidence/T08/<C>/artifacts/rc/` and is cited by hash only.
Here: the per-step table's hashes are exactly the listed ones, each listed record sits on the row
that cites it, every committed file hashes to its entry, and the size rule holds both ways.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from conftest import REPO_ROOT

RC = "67c66d98587f23bd7dfe8da28a8facccc92da21e"
RECORDS = REPO_ROOT / "evidence" / "T08" / RC / "rc"
ARTIFACTS = REPO_ROOT / "evidence" / "T08" / RC / "artifacts" / "rc"
RC_RECORD = REPO_ROOT / "docs" / "t08-rc-record.md"
SHA256 = re.compile(r"`([0-9a-f]{64})`")


def _index() -> dict[str, Any]:
    loaded = json.loads((RECORDS / "records.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _rows() -> list[list[str]]:
    """The per-step table's data rows, as cells."""
    text = RC_RECORD.read_text(encoding="utf-8")
    table = text[text.index("| Step | Assertion") : text.index("**T08.A16")]
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in table.splitlines()[2:]
        if line.startswith("| ")
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_index_is_of_this_candidate_and_this_record() -> None:
    index = _index()
    assert index["format"] == "t08-rc-records-v1"
    assert index["commit"] == RC
    assert index["rc_record"] == "docs/t08-rc-record.md"
    assert f"`C` = `{RC}`" in RC_RECORD.read_text(encoding="utf-8")


def test_every_hash_of_the_per_step_table_is_listed_and_nothing_else() -> None:
    cited = [digest for cells in _rows() for digest in SHA256.findall(cells[-1])]
    listed = [entry["sha256"] for entry in _index()["files"]]
    assert len(cited) == len(set(cited)) == 44
    assert sorted(listed) == sorted(cited)


def test_each_listed_record_sits_on_the_row_that_cites_it() -> None:
    """The row's Record cell names the path, or a sibling in its directory (the record's
    shorthand: `.report.txt` after a run file, `summary` after an inventory)."""
    by_hash = {entry["sha256"]: entry["path"] for entry in _index()["files"]}
    for cells in _rows():
        for digest in SHA256.findall(cells[-1]):
            path = by_hash[digest]
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
            local = ARTIFACTS / entry["path"]
            if local.is_file():  # on the host that ran the RC job only (git-ignored)
                assert _sha256(local) == entry["sha256"], entry["path"]


def test_the_directory_holds_only_the_listed_records() -> None:
    listed = {entry["path"] for entry in _index()["files"] if entry["committed"]}
    present = {
        path.relative_to(RECORDS).as_posix() for path in RECORDS.rglob("*") if path.is_file()
    }
    assert present == listed | {"records.json"}
