"""M07 obligation O1 (`docs/design/V02-alpha-main-rulings.md` §5; R-456): the ledger
`docs/requirements.yaml` after the 0.2.0 verdicts, in the pattern of `tests/test_m07a_ledger.py`.

For the seventeen gates `v0.2-gate-v1` claims (V11–V20, W21–W27) the ledger's verdict equals the
verdict document's (`docs/reviews/V02-verdicts.md`, read by `scripts/v0_2_gate.py`'s own parser,
so re-judged rows are read as the gate reads them); each claimed gate's `evidence` includes
`evidence/M07/<C>/manifest.json`; W21's includes an M01 and an M02 manifest, W22's an M01
manifest, as the alpha's do; every cited manifest exists. All seventeen gates are claimed, so
there is no "untouched" test.

Read on the working tree at `C`: the tests judge when the working tree's version is one
`v0.2-gate-v1` covers (0.2.0, 0.2.0bN, 0.2.0rcN), and there a missing verdict document fails.
Between releases `main` carries a `.devN` version (R-460) and the verdict document does not exist
yet, so each test skips and says so (build log J43). After 0.2.0 is released the ledger is read
from its tag commit, as R-456 does for the alpha. The working tree's own ledger is covered for all
27 gates by `tests/test_requirements_ledger.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

import openflowsheet

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_2_gate  # noqa: E402

LEDGER = REPO_ROOT / "docs" / "requirements.yaml"
(GATE_SET,) = [entry for entry in v0_2_gate.GATE_SETS if entry.name == "v0.2-gate-v1"]
VERDICTS = REPO_ROOT / GATE_SET.verdict_document
RC = re.compile(r"^\*\*Release candidate:\*\* `([0-9a-f]{40})`", re.MULTILINE)


def at_c(version: str) -> str:
    """The verdict document at `C`; a skip, naming the version, where the tree is not a 0.2.0
    candidate."""
    if not GATE_SET.covers.fullmatch(version):
        pytest.skip(
            f"the working tree's version {version} is not one {GATE_SET.name} covers: the 0.2.0 "
            "ledger is judged at C (O1)"
        )
    assert VERDICTS.is_file(), f"{GATE_SET.verdict_document} is missing at a {version} tree"
    return VERDICTS.read_text(encoding="utf-8")


@pytest.fixture
def verdicts() -> str:
    return at_c(openflowsheet.__version__)


def test_a_0_2_0_tree_without_its_verdict_document_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scope rule cannot hide a missing document at `C`: a covered version judges."""
    monkeypatch.setattr(sys.modules[__name__], "VERDICTS", tmp_path / "absent.md")
    for version in ("0.2.0", "0.2.0b1", "0.2.0rc2"):
        with pytest.raises(AssertionError, match="is missing at a"):
            at_c(version)
    for version in ("0.2.0a2.dev0", "0.2.0a1", "0.2.1.dev0"):
        with pytest.raises(pytest.skip.Exception):
            at_c(version)


def rc(text: str) -> str:
    (found,) = RC.findall(text)
    return found


def ledger() -> dict[str, dict[str, Any]]:
    entries = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))["gates"]
    found = {entry["id"]: entry for entry in entries}
    assert len(found) == len(entries), "a gate id is listed twice"
    return found


def test_the_claimed_verdicts_are_the_documents(verdicts: str) -> None:
    document = v0_2_gate.verdict_document(verdicts, GATE_SET, rc(verdicts))
    assert tuple(document.rows) == GATE_SET.claimed
    found = ledger()
    assert {gate: found[gate]["verdict"] for gate in GATE_SET.claimed} == {
        gate: row.verdict for gate, row in document.rows.items()
    }


def test_every_claimed_gate_cites_m07_at_c(verdicts: str) -> None:
    wanted = f"evidence/{GATE_SET.evidence_package}/{rc(verdicts)}/manifest.json"
    assert (REPO_ROOT / wanted).is_file()
    found = ledger()
    assert [gate for gate in GATE_SET.claimed if wanted not in found[gate]["evidence"]] == []


def test_w21_and_w22_cite_their_packages_manifests(verdicts: str) -> None:
    found = ledger()
    for gate, packages in (("W21", ("M01", "M02")), ("W22", ("M01",))):
        cited = found[gate]["evidence"]
        for package in packages:
            pattern = re.compile(rf"evidence/{package}/[0-9a-f]{{40}}/manifest\.json")
            matching = [path for path in cited if pattern.fullmatch(path)]
            assert matching, f"{gate} cites no {package} manifest"
            assert all((REPO_ROOT / path).is_file() for path in matching), matching


def test_every_cited_manifest_exists(verdicts: str) -> None:
    found = ledger()
    missing = [
        (gate, path)
        for gate in GATE_SET.claimed
        for path in found[gate]["evidence"]
        if not (REPO_ROOT / path).is_file()
    ]
    assert missing == []
