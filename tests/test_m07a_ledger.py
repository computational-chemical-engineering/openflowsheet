"""M07a.A64 (V02 alpha release spec §10; WO-11): the ledger `docs/requirements.yaml`, after the
verdicts.

For the twelve gates `v0.2-alpha-gate-v1` claims (V11–V20, W21, W22) the ledger's verdict equals the
verdict document's (`docs/reviews/V02-alpha-verdicts.md`, read by `scripts/v0_2_gate.py`'s own
parser, so the re-judged rows are read as the gate reads them); each claimed gate's `evidence`
includes `evidence/M07a/<C_α>/manifest.json`; W21's includes an M01 and an M02 manifest, W22's an
M01 manifest; every cited manifest exists. W23–W27 are untouched: their entries equal the ledger's
at `C_α`, the commit the verdict document names.

Judged at the tag candidate after §9.2 step 5, with M07a.A52 (Amendment 3 §19.4, R-373). Since the
release these are checks of a past release: the ledger is read as 0.2.0a1 released it, from the tag
commit `ALPHA_TAG_COMMIT`, while the verdict document and the cited manifests stay read from the
working tree, so a rewrite of the released verdicts or a deleted release record on `main` is caught
against the released ledger (R-456). The working tree's own ledger is covered for all 27 gates by
`tests/test_requirements_ledger.py`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

import pytest
import yaml
from conftest import ALPHA_TAG_COMMIT, REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402

LEDGER = "docs/requirements.yaml"
(GATE_SET,) = [entry for entry in v0_2_gate.GATE_SETS if entry.name == "v0.2-alpha-gate-v1"]
VERDICTS = REPO_ROOT / GATE_SET.verdict_document
RC = re.compile(r"^\*\*Release candidate:\*\* `([0-9a-f]{40})`", re.MULTILINE)


def rc() -> str:
    (found,) = RC.findall(VERDICTS.read_text(encoding="utf-8"))
    return found


def gates(text: str) -> dict[str, dict[str, Any]]:
    entries = yaml.safe_load(text)["gates"]
    found = {entry["id"]: entry for entry in entries}
    assert len(found) == len(entries), "a gate id is listed twice"
    return found


def git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True, text=True)


def ledger() -> dict[str, dict[str, Any]]:
    """The ledger as 0.2.0a1 released it (R-456)."""
    shown = git("show", f"{ALPHA_TAG_COMMIT}:{LEDGER}")
    assert shown.returncode == 0, shown.stderr
    return gates(shown.stdout)


def test_the_claimed_verdicts_are_the_documents() -> None:
    document = v0_2_gate.verdict_document(VERDICTS.read_text(encoding="utf-8"), GATE_SET, rc())
    assert tuple(document.rows) == GATE_SET.claimed
    found = ledger()
    assert {gate: found[gate]["verdict"] for gate in GATE_SET.claimed} == {
        gate: row.verdict for gate, row in document.rows.items()
    }


def test_every_claimed_gate_cites_m07a_at_c_alpha() -> None:
    wanted = f"evidence/{GATE_SET.evidence_package}/{rc()}/manifest.json"
    assert (REPO_ROOT / wanted).is_file()
    found = ledger()
    assert [gate for gate in GATE_SET.claimed if wanted not in found[gate]["evidence"]] == []


def test_w21_and_w22_cite_their_packages_manifests() -> None:
    found = ledger()
    for gate, packages in (("W21", ("M01", "M02")), ("W22", ("M01",))):
        cited = found[gate]["evidence"]
        for package in packages:
            pattern = re.compile(rf"evidence/{package}/[0-9a-f]{{40}}/manifest\.json")
            matching = [path for path in cited if pattern.fullmatch(path)]
            assert matching, f"{gate} cites no {package} manifest"
            assert all((REPO_ROOT / path).is_file() for path in matching), matching


def test_every_cited_manifest_exists() -> None:
    found = ledger()
    missing = [
        (gate, path)
        for gate in GATE_SET.claimed
        for path in found[gate]["evidence"]
        if not (REPO_ROOT / path).is_file()
    ]
    assert missing == []


def test_the_unclaimed_gates_are_untouched() -> None:
    shown = git("show", f"{rc()}:{LEDGER}")
    assert shown.returncode == 0, shown.stderr
    at_rc = shown.stdout
    before, now = gates(at_rc), ledger()
    assert {gate: now[gate] for gate in GATE_SET.not_claimed} == {
        gate: before[gate] for gate in GATE_SET.not_claimed
    }


def test_the_tag_commit_is_0_2_0a1() -> None:
    """`ALPHA_TAG_COMMIT` is in `HEAD`'s history and declares 0.2.0a1; where the tag `v0.2.0a1` is
    fetched, it resolves to that commit (R-456, AM-06)."""
    assert git("merge-base", "--is-ancestor", ALPHA_TAG_COMMIT, "HEAD").returncode == 0
    assert v0_1_gate.version_at(ALPHA_TAG_COMMIT) == "0.2.0a1"
    tag = git("rev-parse", "--verify", "--quiet", "refs/tags/v0.2.0a1^{commit}")
    if tag.returncode != 0:
        pytest.skip("the tag v0.2.0a1 is not fetched here; the commit and its version are checked")
    assert tag.stdout.strip() == ALPHA_TAG_COMMIT
