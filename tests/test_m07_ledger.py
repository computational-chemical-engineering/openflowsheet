"""M07 obligation O1 (`docs/design/V02-alpha-main-rulings.md` §5; R-456): the ledger
`docs/requirements.yaml` after the 0.2.0 verdicts, in the pattern of `tests/test_m07a_ledger.py`.

For the seventeen gates `v0.2-gate-v1` claims (V11–V20, W21–W27) the ledger's verdict equals the
verdict document's (`docs/reviews/V02-verdicts.md`, read by `scripts/v0_2_gate.py`'s own parser,
so re-judged rows are read as the gate reads them); each claimed gate's `evidence` includes
`evidence/M07/<C>/manifest.json`; W21's includes an M01 and an M02 manifest, W22's an M01
manifest, as the alpha's do; every cited manifest exists. All seventeen gates are claimed, so
there is no "untouched" test.

Since the release these are checks of a past release (M07 spec §26, R-564; O1's post-release
clause): the ledger is read as 0.2.0 released it, from the tag commit `RELEASE_0_2_0_COMMIT`,
while the verdict document and the cited manifests stay read from the working tree, so a rewrite
of the released verdicts or a deleted release record on `main` is caught against the released
ledger (R-456). The working tree's own ledger is covered for all 27 gates by
`tests/test_requirements_ledger.py`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

import pytest
import yaml
from conftest import RELEASE_0_2_0_COMMIT, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402

LEDGER = "docs/requirements.yaml"
(GATE_SET,) = [entry for entry in v0_2_gate.GATE_SETS if entry.name == "v0.2-gate-v1"]
VERDICTS = REPO_ROOT / GATE_SET.verdict_document
RC = re.compile(r"^\*\*Release candidate:\*\* `([0-9a-f]{40})`", re.MULTILINE)


@pytest.fixture
def verdicts() -> str:
    return VERDICTS.read_text(encoding="utf-8")


def rc(text: str) -> str:
    (found,) = RC.findall(text)
    return found


def git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True)


def ledger() -> dict[str, dict[str, Any]]:
    """The ledger as 0.2.0 released it (R-564)."""
    shown = git("show", f"{RELEASE_0_2_0_COMMIT}:{LEDGER}")
    assert shown.returncode == 0, shown.stderr
    entries = yaml.safe_load(shown.stdout)["gates"]
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


def test_the_tag_commit_is_0_2_0() -> None:
    """`RELEASE_0_2_0_COMMIT` is in `HEAD`'s history and declares 0.2.0; where the tag `v0.2.0`
    is fetched, it resolves to that commit (R-564)."""
    assert git("merge-base", "--is-ancestor", RELEASE_0_2_0_COMMIT, "HEAD").returncode == 0
    assert v0_1_gate.version_at(RELEASE_0_2_0_COMMIT) == "0.2.0"
    tag = git("rev-parse", "--verify", "--quiet", "refs/tags/v0.2.0^{commit}")
    if tag.returncode != 0:
        pytest.skip("the tag v0.2.0 is not fetched here; the commit and its version are checked")
    assert tag.stdout.strip() == RELEASE_0_2_0_COMMIT
