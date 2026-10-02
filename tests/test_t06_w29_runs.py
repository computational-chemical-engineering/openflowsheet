"""T06 W29: the committed run files and the registry's `ensemble.runs` (A97 (e), A95).

Spec `docs/derivations/T06-corpus-spec.md` §6.6 (A5), §7.5 (A5), A95, A97 (e); register R-090.
Every committed file under `benchmarks/t06/ensemble/runs/` is listed in its `SHA256SUMS`; every
run file is the registry's entry by SHA-256, and runs 1 and 2 are the bytes the verdicts judged
(their §0, read from `docs/reviews/T06-verdicts.md`). Each file's machine class is the entry's —
from `architecture` and the CI job for a v1 file, whose `machine_class` is the pre-A5 literal —
and its headline recomputes from its records with the harness's `report`: run 1 `S` = 431
(367 + 64), gate FAIL; run 2 434 (370 + 64) on `ref-x86-64` and `ci-x86-64`, 434 (367 + 67) on
`ci-aarch64`, gate PASS. The judged report of run 2 on `ref-x86-64` recomputes byte for byte,
with A90's "not recorded" line appended.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_ensemble_support import RUNS_DIR, STARTS_FILE

from benchmarks.t06 import ensemble

REGISTRY: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
RUNS: list[dict[str, Any]] = REGISTRY["ensemble"]["runs"]
TEXTS: list[dict[str, Any]] = REGISTRY["ensemble"]["judged_texts"]
VERDICTS = (REPO_ROOT / "docs" / "reviews" / "T06-verdicts.md").read_text("utf-8")
#: A97 (e)'s headlines, from the spec's text: `(run_id, class) -> (S, S^first, S^rescued, pass)`.
HEADLINES = {
    ("run1", "ref-x86-64"): (431, 367, 64, False),
    ("run2", "ref-x86-64"): (434, 370, 64, True),
    ("run2", "ci-x86-64"): (434, 370, 64, True),
    ("run2", "ci-aarch64"): (434, 367, 67, True),
    # A98 (b): run 2r's `S` and `S^first` equal run 2's per class (the row's numbers).
    ("run2r", "ref-x86-64"): (434, 370, 64, True),
    ("run2r", "ci-x86-64"): (434, 370, 64, True),
    ("run2r", "ci-aarch64"): (434, 367, 67, True),
}


def _sums() -> dict[str, str]:
    sums: dict[str, str] = {}
    for line in (RUNS_DIR / "SHA256SUMS").read_text("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    return sums


@cache
def _document(file: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((REPO_ROOT / file).read_bytes())
    return document


def test_every_committed_file_is_in_sha256sums_with_its_bytes() -> None:
    sums = _sums()
    committed = sorted(
        str(path.relative_to(RUNS_DIR))
        for path in RUNS_DIR.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    assert sorted(sums) == committed
    for name, digest in sums.items():
        assert hashlib.sha256((RUNS_DIR / name).read_bytes()).hexdigest() == digest, name


def test_a95_a97e_the_registry_names_every_run_file_by_its_hash() -> None:
    """Every committed run file (`*.json`) is an `ensemble.runs` entry — W31's run 2r and
    holdout files included; the judged texts are listed too. W31's reports, replays, A98 texts and
    comparisons are in `SHA256SUMS` (`tests/test_t06_w31_runs.py` recomputes them)."""
    sums = _sums()
    committed = {str((RUNS_DIR / name).relative_to(REPO_ROOT)) for name in sums}
    assert {entry["file"] for entry in RUNS} == {f for f in committed if f.endswith(".json")}
    assert {text["file"] for text in TEXTS} <= committed
    for entry in [*RUNS, *TEXTS]:
        name = str((REPO_ROOT / entry["file"]).relative_to(RUNS_DIR))
        raw = (REPO_ROOT / entry["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"] == sums[name], name


def test_a95_runs_1_and_2_are_the_bytes_the_verdicts_judged() -> None:
    """The verdicts' §0: the four run files by their full SHA-256, the judged texts by the
    prefixes the verdicts print."""
    section = VERDICTS.split("## 0.", 1)[1].split("\n## ", 1)[0]
    full = set(re.findall(r"`([0-9a-f]{64})`", section))
    runs = {entry["sha256"] for entry in RUNS if entry["run_id"] in ("run1", "run2")}
    assert len(runs) == 4 and runs <= full
    prefixes = re.findall(r"`([0-9a-f]{8})…`", section.split("Run 2 report / replay", 1)[1])
    assert [text["sha256"][:8] for text in TEXTS] == prefixes[:2]


@pytest.mark.parametrize("entry", RUNS, ids=lambda entry: Path(entry["file"]).name)
def test_a97e_each_files_class_is_its_entrys(entry: dict[str, Any]) -> None:
    document = _document(entry["file"])
    classes = REGISTRY["ensemble"]["machine_classes"]
    assert entry["machine_class"] in classes
    assert document["host"]["architecture"] == entry["architecture"]
    assert classes[entry["machine_class"]]["architecture"] == entry["architecture"]
    if document["format"] == ensemble.RESULTS_FORMAT:
        assert document["host"]["machine_class"] == entry["machine_class"]
        return
    assert document["format"] == ensemble.RESULTS_FORMAT_V1
    # The pre-A5 literal on every v1 host (the verdicts' P2); the class comes from elsewhere.
    assert document["host"]["machine_class"] == "ref-x86-64"
    registered = classes[entry["machine_class"]]
    if entry["ci_runner"] is None:
        assert not registered["github_actions"] and entry["ci_run"] is None
        assert document["host"]["cpu_model"] == registered["cpu_model"]
    else:
        assert registered["github_actions"] and registered["runner"] == entry["ci_runner"]
        assert isinstance(entry["ci_run"], int)


@pytest.mark.parametrize("entry", RUNS, ids=lambda entry: Path(entry["file"]).name)
def test_a97e_each_headline_recomputes_from_its_records(entry: dict[str, Any]) -> None:
    """The headline recomputes to the entry's; for runs 1 and 2 also to A97 (e)'s numbers. The
    holdout's entry has no gate (`gate: null`, §7.6 (A5))."""
    document = _document(entry["file"])
    section = REGISTRY["ensemble"]
    holdout = entry["run_id"] == ensemble.HOLDOUT_RUN_ID
    starts = section["holdout"] if holdout else section
    assert document["starts_file"] == starts["starts_file"]
    assert document["starts_sha256"] == starts["starts_sha256"]
    assert entry["revision_policy"] in document["policies"]
    published = json.loads((REPO_ROOT / starts["starts_file"]).read_bytes())
    summary = ensemble.report(document["records"], document["cases"], published)
    recomputed = (summary["S"], summary["S_first"], summary["S_rescued"])
    assert recomputed == (entry["S"], entry["S_first"], entry["S_rescued"])
    assert summary["N"] == ensemble.N and summary["gate"]["complete"]
    if holdout:
        assert entry["gate"] is None
        return
    assert entry["gate"] == ("PASS" if summary["gate"]["pass"] else "FAIL")
    key = (entry["run_id"], entry["machine_class"])
    if key in HEADLINES:
        assert (*recomputed, summary["gate"]["pass"]) == HEADLINES[key]


def test_a97e_the_judged_report_recomputes_byte_for_byte() -> None:
    (report,) = [text for text in TEXTS if text["file"].endswith(".report.txt")]
    (run,) = [e for e in RUNS if (e["run_id"], e["machine_class"]) == ("run2", "ref-x86-64")]
    document = _document(run["file"])
    published = json.loads(STARTS_FILE.read_bytes())
    text = ensemble.render(ensemble.report(document["records"], document["cases"], published))
    judged = (REPO_ROOT / report["file"]).read_text("utf-8")
    # W28 appends A90's line for a v1 file; the judged text is `report`'s standard output, so it
    # ends in `print`'s newline after the rendered text's own.
    appended = "\nRefinements (ADR 0018; A90 (A5)): not recorded.\n"
    assert text.endswith(appended)
    assert judged == text.removesuffix(appended) + "\n"
