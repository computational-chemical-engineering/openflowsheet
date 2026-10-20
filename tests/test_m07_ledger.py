"""M07 obligation O1 (`docs/design/V02-alpha-main-rulings.md` §5; R-456): the ledger
`docs/requirements.yaml` after the 0.2.0 verdicts, in the pattern of `tests/test_m07a_ledger.py`.

For the seventeen gates `v0.2-gate-v1` claims (V11–V20, W21–W27) the ledger's verdict equals the
verdict document's (`docs/reviews/V02-verdicts.md`, read by `scripts/v0_2_gate.py`'s own parser,
so re-judged rows are read as the gate reads them); each claimed gate's `evidence` includes
`evidence/M07/<C>/manifest.json`; W21's includes an M01 and an M02 manifest, W22's an M01
manifest, as the alpha's do; every cited manifest exists. All seventeen gates are claimed, so
there is no "untouched" test.

Read on the working tree at `C`: the tests judge wherever the 0.2.0 gate could say YES, that is
when the working tree's version is one `v0.2-gate-v1` covers (0.2.0, 0.2.0bN, 0.2.0rcN) and the
verdict document exists. At a covered version without the document (C included: WO-7 writes it
after the RC steps) each test skips and names the document (R-476); the gate itself refuses a
candidate without it. The tests are judged at the candidate, after the verdicts. Between releases
`main` carries a `.devN` version (R-460), so each test skips and says so (build log J43). After
0.2.0 is released the ledger is read from its tag commit, as R-456 does for the alpha. The working
tree's own ledger is covered for all 27 gates by `tests/test_requirements_ledger.py`.
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
    candidate, and naming the document where it does not exist yet (M07 spec §23.2, R-476)."""
    if not GATE_SET.covers.fullmatch(version):
        pytest.skip(
            f"the working tree's version {version} is not one {GATE_SET.name} covers: the 0.2.0 "
            "ledger is judged at the candidate (O1; M07 spec §23.2)"
        )
    if not VERDICTS.is_file():
        pytest.skip(
            f"{GATE_SET.verdict_document} does not exist yet at this {version} tree: the 0.2.0 "
            "ledger is judged at the candidate, after the verdicts (M07 spec §23.2)"
        )
    return VERDICTS.read_text(encoding="utf-8")


@pytest.fixture
def verdicts() -> str:
    return at_c(openflowsheet.__version__)


def test_the_ledger_is_judged_wherever_the_gate_could_say_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The skip predicate is "not covered, or no verdict document", in that order (R-476)."""
    covered = ("0.2.0", "0.2.0b1", "0.2.0rc2")
    uncovered = ("0.2.0a2.dev0", "0.2.0a1", "0.2.1.dev0")
    module = sys.modules[__name__]
    present = tmp_path / "V02-verdicts.md"
    present.write_text("document\n", encoding="utf-8")
    monkeypatch.setattr(module, "VERDICTS", present)
    for version in covered:  # (a)
        assert at_c(version) == "document\n"
    for version in uncovered:  # (b)
        with pytest.raises(pytest.skip.Exception, match="is not one v0.2-gate-v1 covers"):
            at_c(version)
    monkeypatch.setattr(module, "VERDICTS", tmp_path / "absent.md")
    for version in covered:  # (c)
        with pytest.raises(
            pytest.skip.Exception, match=r"V02-verdicts\.md does not exist yet at this 0\.2\.0"
        ):
            at_c(version)
    for version in uncovered:  # (d)
        with pytest.raises(pytest.skip.Exception, match="is not one v0.2-gate-v1 covers"):
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
