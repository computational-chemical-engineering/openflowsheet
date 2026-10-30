"""V03.A26 (`docs/derivations/V03-release-spec.md` §7; WO-8): the ledger `docs/requirements.yaml`
after the 0.3.0 verdicts, in the pattern of `tests/test_m07_ledger.py`.

For the seventeen gates `v0.3-gate-v1` claims (V11–V20, W21–W26, X31) the ledger's verdict equals
the verdict document's (`docs/reviews/V03-verdicts.md`, read by `scripts/v0_2_gate.py`'s own
parser with the set from `scripts/v0_3_gate.py`, so re-judged rows are read as the gate reads
them). X31, the gate 0.3.0 adds, cites S13's manifest at C (`evidence/S13/<C>/manifest.json`),
the package that judged it there; the sixteen carried gates keep their 0.2.0 evidence (A26 names
X31's verdict and evidence only). Every cited manifest of a claimed gate exists. W27 is not
claimed and keeps its 0.2.0 entry. The working tree's own ledger is covered for all 27 gates by
`tests/test_requirements_ledger.py`; the tag commit is pinned after the tag (WO-9).
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
import v0_2_gate  # noqa: E402
import v0_3_gate  # noqa: E402

LEDGER = "docs/requirements.yaml"
(GATE_SET,) = [entry for entry in v0_3_gate.GATE_SETS if entry.name == "v0.3-gate-v1"]
VERDICTS = REPO_ROOT / GATE_SET.verdict_document
RC = re.compile(r"^\*\*Release candidate:\*\* `([0-9a-f]{40})`", re.MULTILINE)


@pytest.fixture
def verdicts() -> str:
    return VERDICTS.read_text(encoding="utf-8")


def rc(text: str) -> str:
    (found,) = RC.findall(text)
    return found


def entries(text: str) -> dict[str, dict[str, Any]]:
    gates = yaml.safe_load(text)["gates"]
    found = {entry["id"]: entry for entry in gates}
    assert len(found) == len(gates), "a gate id is listed twice"
    return found


def ledger() -> dict[str, dict[str, Any]]:
    return entries((REPO_ROOT / LEDGER).read_text(encoding="utf-8"))


def test_the_claimed_verdicts_are_the_documents(verdicts: str) -> None:
    document = v0_2_gate.verdict_document(verdicts, GATE_SET, rc(verdicts))
    assert tuple(document.rows) == GATE_SET.claimed
    found = ledger()
    assert {gate: found[gate]["verdict"] for gate in GATE_SET.claimed} == {
        gate: row.verdict for gate, row in document.rows.items()
    }


def test_x31_cites_s13_at_c(verdicts: str) -> None:
    wanted = f"evidence/{GATE_SET.evidence_package}/{rc(verdicts)}/manifest.json"
    assert (REPO_ROOT / wanted).is_file()
    assert wanted in ledger()["X31"]["evidence"]


def test_every_cited_manifest_exists() -> None:
    found = ledger()
    missing = [
        (gate, path)
        for gate in GATE_SET.claimed
        for path in found[gate]["evidence"]
        if not (REPO_ROOT / path).is_file()
    ]
    assert missing == []


def test_the_unclaimed_gate_is_untouched() -> None:
    """W27 equals its entry in the ledger as 0.2.0 released it."""
    shown = subprocess.run(
        ["git", "show", f"{RELEASE_0_2_0_COMMIT}:{LEDGER}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert shown.returncode == 0, shown.stderr
    released = entries(shown.stdout)
    found = ledger()
    assert GATE_SET.not_claimed == ("W27",)
    assert {gate: found[gate] for gate in GATE_SET.not_claimed} == {
        gate: released[gate] for gate in GATE_SET.not_claimed
    }
