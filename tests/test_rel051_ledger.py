"""RP.S17 (`docs/derivations/release-procedure.md`; RP §9.2 step 3): the ledger
`docs/requirements.yaml` after the 0.5.1 verdicts, in the pattern of `tests/test_rel050_ledger.py`.

For the seventeen gates the 0.5 line's gate set claims (`release/lines/0.5.json` in the working
tree, 0.5.1's: REL051, R-1069), read by `scripts/release_gate.py`'s own loader, the ledger's verdict
equals the verdict document's (`docs/reviews/REL051-verdicts.md`, read by the engine's parser as the
gate reads it). At C' = `ee934680` that is 15 PASS, V14 FAIL (V14 (b)) and X31 FAIL (X31 (c)), as
0.5.0 released them, so the ledger moves no verdict against 0.5.0's released ledger. Every cited
manifest of a claimed gate exists; W27 is not claimed and keeps its 0.5.0 entry. No gate cites
`evidence/REL051/<C'>/manifest.json`: it does not exist at the candidate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import release_gate  # noqa: E402
import v0_2_gate  # noqa: E402

LEDGER = "docs/requirements.yaml"
RC = re.compile(r"^\*\*Release candidate:\*\* `([0-9a-f]{40})`", re.MULTILINE)
C = "ee934680d94879032b34ae8649baa31ff5a210c8"
#: The commit tagged `v0.5.0` (`git rev-list -n1 v0.5.0`; `tests/test_v02_main_version.py`).
RELEASE_0_5_0_COMMIT = "63b005046f34ff25a1f4dacb34645a78ce49f79b"


def read(path: str) -> bytes | None:
    file = REPO_ROOT / path
    return file.read_bytes() if file.is_file() else None


GATE_SET = release_gate.load_line("0.5", read).gate_set
VERDICTS = REPO_ROOT / GATE_SET.verdict_document


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


def released() -> dict[str, dict[str, Any]]:
    """The ledger as 0.5.0 released it."""
    shown = subprocess.run(
        ["git", "show", f"{RELEASE_0_5_0_COMMIT}:{LEDGER}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert shown.returncode == 0, shown.stderr
    return entries(shown.stdout)


def test_the_document_is_judged_at_c(verdicts: str) -> None:
    assert GATE_SET.verdict_document == "docs/reviews/REL051-verdicts.md"
    assert rc(verdicts) == C


def test_the_claimed_verdicts_are_the_documents(verdicts: str) -> None:
    document = v0_2_gate.verdict_document(verdicts, GATE_SET, rc(verdicts))
    assert tuple(document.rows) == GATE_SET.claimed
    found = ledger()
    assert {gate: found[gate]["verdict"] for gate in GATE_SET.claimed} == {
        gate: row.verdict for gate, row in document.rows.items()
    }


def test_the_failing_clauses_are_v14_b_and_x31_c(verdicts: str) -> None:
    document = v0_2_gate.verdict_document(verdicts, GATE_SET, rc(verdicts))
    assert {gate: row.clauses for gate, row in document.rows.items() if row.verdict != "PASS"} == {
        "V14": ("V14 (b)",),
        "X31": ("X31 (c)",),
    }


def test_the_ledger_moves_only_what_the_document_moves(verdicts: str) -> None:
    """Against 0.5.0's released ledger, a claimed gate's verdict changes iff the document's
    differs from it (at C: none)."""
    document = v0_2_gate.verdict_document(verdicts, GATE_SET, rc(verdicts))
    before = released()
    moved = {
        gate: (before[gate]["verdict"], row.verdict)
        for gate, row in document.rows.items()
        if before[gate]["verdict"] != row.verdict
    }
    found = ledger()
    assert {
        gate: (before[gate]["verdict"], found[gate]["verdict"])
        for gate in GATE_SET.claimed
        if before[gate]["verdict"] != found[gate]["verdict"]
    } == moved


def test_every_cited_manifest_exists() -> None:
    found = ledger()
    missing = [
        (gate, path)
        for gate in GATE_SET.claimed
        for path in found[gate]["evidence"]
        if not (REPO_ROOT / path).is_file()
    ]
    assert missing == []


def test_no_gate_cites_the_release_manifest() -> None:
    found = ledger()
    prefix = f"evidence/{GATE_SET.evidence_package}/"
    assert [
        (gate, path)
        for gate in GATE_SET.claimed + GATE_SET.not_claimed
        for path in found[gate].get("evidence") or []
        if path.startswith(prefix)
    ] == []


def test_the_unclaimed_gate_is_untouched() -> None:
    """W27 equals its entry in the ledger as 0.5.0 released it."""
    before = released()
    found = ledger()
    assert GATE_SET.not_claimed == ("W27",)
    assert {gate: found[gate] for gate in GATE_SET.not_claimed} == {
        gate: before[gate] for gate in GATE_SET.not_claimed
    }
