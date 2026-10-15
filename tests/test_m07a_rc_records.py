"""M07a.A43, A44 and §8.3 (V02 alpha release spec): the alpha RC record's hashes resolve to
committed records, every record carries its provenance, and the tree record is `C_α`'s.

`docs/v02-alpha-rc-record.md` cites each record of the RC job by its sha256. §8.3 (T08 Amendments
R7 1 and R8 1's form) puts the records of 1 MB or less under `evidence/M07a/<C_α>/rc/`, outside the
trees ADR 0021 D2.4 compares, and a larger one gzip-compressed beside its path; `rc/records.json`
lists every cited record with its sha256, size and whether it is committed as is. Here, as
`tests/test_t08_rc_records.py` checks T08's: the per-step table's hashes are exactly the listed
ones, each listed record sits on the row that cites it, every committed file hashes to its entry
(a compressed one after decompression), and the size rule holds both ways. Then A43 over every
committed `t08-rc-v1` record, and A44 over `release/rc-trees/<C_α>.json`.
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

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402

RC = "e0e198e4632224612671db5b07445639d272d6da"
RECORDS = REPO_ROOT / "evidence" / "M07a" / RC / "rc"
ARTIFACTS = REPO_ROOT / "evidence" / "M07a" / RC / "artifacts" / "rc"
RC_RECORD = REPO_ROOT / "docs" / "v02-alpha-rc-record.md"
SHA256 = re.compile(r"`([0-9a-f]{64})`")
#: `requirements.lock` at `C_α` (T08.A40's value, unchanged).
LOCK_SHA256 = "ead4edf1ea3577287a7576d56a9e5db550e5a5be459dd634b10806fdc655b9c4"
#: The records `scripts/t08_rc.py` writes without a `machine_class` (its steps 3, 4 and 10 carry
#: `architecture` and `github_actions` only); M07a.A43 names the machine class (build decision
#: B-WO10-10, a question for the design lane). Pinned so that a change is seen.
NO_MACHINE_CLASS = frozenset(
    {
        "certificates-ref-x86-64.json",
        "ci/rc-bundle-set-certificates/rc-certificates.json",
        "ci/rc-dist/t08-a43-dist.json",
        "ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json",
        "ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json",
        "ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json",
        "ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json",
        "ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json",
        "ci/rc-install-ubuntu-latest/install-ubuntu-latest.json",
        "ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json",
        "ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json",
        "ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json",
        "ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json",
    }
)


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
    cited = [digest for cells in _rows() for digest in SHA256.findall(cells[-1])]
    listed = [entry["sha256"] for entry in _index()["files"]]
    assert len(cited) == len(set(cited)) == len(listed)
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


def test_a44_the_tree_record_is_c_alphas_byte_for_byte() -> None:
    path = REPO_ROOT / v0_1_gate.RC_TREES / f"{RC}.json"
    record = v0_1_gate.tree_record(RC)
    assert record["trees"] == list(v0_1_gate.TREES)
    assert path.read_text(encoding="utf-8") == json.dumps(record, indent=1, sort_keys=True) + "\n"
