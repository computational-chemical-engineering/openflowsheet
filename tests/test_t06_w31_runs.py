"""T06 W31: run 2r and `holdout1`, read from the committed run files (A98, A99 (b)–(d), A31, A34).

Spec `docs/derivations/T06-corpus-spec.md` §7.3 (A5), §7.6 (A5), A90 (A5), A98, A99; registers
R-089, R-090. W31 ran both at the closing commit on `ref-x86-64` and in CI dispatch 36278604955
(`ci-x86-64`, `ci-aarch64`); the run files, reports, replays, A98 texts and cross-class
comparisons are committed under `benchmarks/t06/ensemble/runs/` and listed in the registry's
`ensemble.runs` (W29's tests check the hashes and the headlines). Nothing is re-run here: every
figure is read from, or recomputed from, the committed records.

- **A98 (a):** the closing commit's `src/` differs from run 2's (`f636452`) only by W24 (ADR
  0018's docstring sentence; `numerics/newton.py`'s syntax tree without docstrings unchanged) and
  W25 (S5's number reading).
- **A98 (b)–(c):** per class, every start's class and `S` equal run 2's same-class file (434;
  `S^first` 370, 370, 367 — the row's numbers); on `ref-x86-64` the refinements are the verdicts'
  reconstruction (17 fired, 17 kept, none reverted or abandoned, at the 17 listed starts, each in
  its start's last attempt); the committed A98 texts recompute. Bitwise state differences are
  reported by the A98 text, never asserted.
- **A98 (d), A34:** every committed replay is `MATCH` on every line, and replays exactly each
  case's first start and every retained failure.
- **A99 (b):** the commit that added the holdout's starts is an ancestor of every holdout record's
  commit, and no holdout run file exists at it.
- **A99 (c), A31:** every committed report recomputes byte for byte from its run file; the
  holdout's carries its header, no gate line, both Clopper–Pearson bounds, A90's counts and
  `S_holdout − S_run2` against run 2's registered `S` on its class; the committed cross-class
  comparisons recompute.
- **A99 (d):** no holdout `F-CRASH`; its classes, including any `F-OTHER-ROOT`, are the report's.
  The holdout's rate is reported and never gated: no test here compares it with a threshold.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import subprocess
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml, require_archived_history
from t06_ensemble_support import HOLDOUT_FILE, RUNS_DIR

from benchmarks.t06 import ensemble

REGISTRY: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
RUNS: list[dict[str, Any]] = REGISTRY["ensemble"]["runs"]
CLASSES = ("ref-x86-64", "ci-x86-64", "ci-aarch64")
#: Run 2's commit (the registry's run 2 entries), from which A98 (a) measures `src/`.
RUN2_COMMIT = "f636452"
#: A98 (b)'s numbers, from the row: `S` 434 on every class, `S^first` per class.
A98_S = 434
A98_S_FIRST = {"ref-x86-64": 370, "ci-x86-64": 370, "ci-aarch64": 367}
#: A98 (a): the only work orders the row admits in `src/` after run 2 (spec §17 (A5)).
A98_SRC_WORK_ORDERS = ("T06 W24:", "T06 W25:")


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t06_ensemble_script_w31", REPO_ROOT / "scripts" / "t06_ensemble.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _script()


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout


def _entry(run_id: str, machine: str) -> dict[str, Any]:
    (entry,) = [e for e in RUNS if (e["run_id"], e["machine_class"]) == (run_id, machine)]
    return entry


@cache
def _document(run_id: str, machine: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (REPO_ROOT / _entry(run_id, machine)["file"]).read_bytes()
    )
    return document


def _stem(run_id: str, machine: str) -> str:
    return Path(_entry(run_id, machine)["file"]).stem


def test_the_v2_files_are_registered_on_every_class_at_one_clean_commit() -> None:
    """W31 runs once, at one commit (spec §17 (A5)): run 2r and the holdout on every class, v2
    records from a clean tree, the registry's abbreviated `commit` a prefix of the record's."""
    commits = set()
    for run_id in ("run2r", ensemble.HOLDOUT_RUN_ID):
        for machine in CLASSES:
            document = _document(run_id, machine)
            assert document["format"] == ensemble.RESULTS_FORMAT
            assert document["run_id"] == run_id
            assert document["tree_clean"] is True
            assert document["commit"].startswith(_entry(run_id, machine)["commit"])
            commits.add(document["commit"])
    assert len(commits) == 1
    (commit,) = commits
    assert re.fullmatch(r"[0-9a-f]{40}", commit)


# -- A98 (a): src/ after run 2 -------------------------------------------------------------------


def _closing_commit() -> str:
    commit: str = _document("run2r", "ref-x86-64")["commit"]
    return commit


def _without_docstrings(source: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    node.body = body[1:]
    return ast.dump(tree)


def test_a98a_src_differs_from_run_2s_only_by_w24_and_w25() -> None:
    closing = _closing_commit()
    require_archived_history(RUN2_COMMIT, closing)
    changed = set(_git("diff", "--name-only", RUN2_COMMIT, closing, "--", "src/").split())
    commits = [
        line.split(" ", 1)
        for line in _git(
            "log", "--no-merges", "--format=%H %s", f"{RUN2_COMMIT}..{closing}", "--", "src/"
        ).splitlines()
    ]
    subjects = sorted(subject.split(":", 1)[0] + ":" for _, subject in commits)
    assert subjects == sorted(A98_SRC_WORK_ORDERS)
    touched = {
        path
        for sha, _ in commits
        for path in _git("show", "--name-only", "--format=", sha, "--", "src/").split()
    }
    assert changed == touched
    (w24,) = [sha for sha, subject in commits if subject.startswith("T06 W24:")]
    w24_files = set(_git("show", "--name-only", "--format=", w24, "--", "src/").split())
    # The commits are history: they name the package as it was before the rename (R-149).
    newton = "src/process_runtime/numerics/newton.py"
    assert w24_files == {newton}
    before, after = _git("show", f"{RUN2_COMMIT}:{newton}"), _git("show", f"{closing}:{newton}")
    assert before != after
    assert _without_docstrings(before) == _without_docstrings(after)


# -- A98 (b)–(c): run 2r against run 2 -----------------------------------------------------------


@pytest.mark.parametrize("machine", CLASSES)
def test_a98bc_run_2r_equals_run_2_on_its_class(machine: str) -> None:
    expected = ensemble.A90_EXPECTED_REF_X86_64 if machine == ensemble.REFERENCE_CLASS else None
    found = ensemble.a98_discrepancies(
        _document("run2r", machine), _document("run2", machine), expected
    )
    assert found["discrepancies"] == []
    assert found["starts"] == ensemble.N
    assert found["S"] == [A98_S, A98_S]
    assert found["S_first"] == [A98_S_FIRST[machine]] * 2
    if expected is not None:
        counts = found["refinements"]
        assert (counts["fired"], counts["kept"], counts["reverted"], counts["abandoned"]) == (
            len(expected),
            len(expected),
            0,
            0,
        )


def test_a90_the_expected_reconstruction_has_seventeen_starts() -> None:
    assert len(ensemble.A90_EXPECTED_REF_X86_64) == 17


@pytest.mark.parametrize("machine", CLASSES)
def test_a98_the_committed_a98_text_recomputes(
    machine: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The text's first line names the file compared against by its path on the machine that
    ran it; every other line recomputes from the committed run 2r and run 2 files."""
    stem = _stem("run2r", machine)
    arguments = argparse.Namespace(
        results=str(RUNS_DIR / f"{stem}.json"),
        against=str(REPO_ROOT / _entry("run2", machine)["file"]),
    )
    assert SCRIPT.a98(arguments) == 0
    recomputed = capsys.readouterr().out.splitlines()
    committed = (RUNS_DIR / f"{stem}.a98.txt").read_text("utf-8").splitlines()
    assert committed[0].startswith(f"A98: run2r on {machine} ({_closing_commit()}) against ")
    assert committed[0].endswith(f"{Path(_entry('run2', machine)['file']).name}")
    assert committed[1:] == recomputed[1:]
    assert committed[-1] == "0 discrepancies"


# -- A98 (d), A34: the replays ---------------------------------------------------------------------


@pytest.mark.parametrize("run_id", ["run2r", ensemble.HOLDOUT_RUN_ID])
@pytest.mark.parametrize("machine", CLASSES)
def test_a98d_a34_every_replay_matches_and_covers_the_first_starts_and_failures(
    run_id: str, machine: str
) -> None:
    records = _document(run_id, machine)["records"]
    first: dict[str, int] = {}
    for record in records:
        first.setdefault(record["case"], record["start"])
    expected = [
        (record["case"], record["start"])
        for record in records
        if record["start"] == first[record["case"]] or ensemble.classify(record) != "SUCCESS"
    ]
    lines = (RUNS_DIR / f"{_stem(run_id, machine)}.replay.txt").read_text("utf-8").splitlines()
    parsed = [re.fullmatch(r"(\S+)\s+(\d{2}) (MATCH|DIFFER)", line) for line in lines]
    assert all(match is not None for match in parsed), lines
    replayed = [(m[1], int(m[2])) for m in parsed if m is not None]
    assert replayed == expected
    assert {m[3] for m in parsed if m is not None} == {"MATCH"}


# -- A99 (b): the holdout's starts came first ------------------------------------------------------


def test_a99b_the_holdout_starts_commit_precedes_every_holdout_run() -> None:
    require_archived_history(
        *(_document(ensemble.HOLDOUT_RUN_ID, machine)["commit"] for machine in CLASSES),
        in_history_of_head=True,
    )
    relative = str(HOLDOUT_FILE.relative_to(REPO_ROOT))
    (added,) = _git("log", "--diff-filter=A", "--format=%H", "--", relative).split()
    at_addition = _git(
        "ls-tree", "-r", "--name-only", added, "--", str(RUNS_DIR.relative_to(REPO_ROOT))
    )
    assert [name for name in at_addition.split() if "holdout" in Path(name).name] == []
    for machine in CLASSES:
        commit = _document(ensemble.HOLDOUT_RUN_ID, machine)["commit"]
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", added, commit], cwd=REPO_ROOT, check=False
        )
        assert ancestry.returncode == 0, (added, commit)
        assert added != commit


# -- A99 (c), A31: reports and comparisons ---------------------------------------------------------


@pytest.mark.parametrize("run_id", ["run2r", ensemble.HOLDOUT_RUN_ID])
@pytest.mark.parametrize("machine", CLASSES)
def test_a99c_a31_every_committed_report_recomputes_byte_for_byte(
    run_id: str, machine: str
) -> None:
    text, summary, holdout = SCRIPT.render(_document(run_id, machine))
    committed = (RUNS_DIR / f"{_stem(run_id, machine)}.report.txt").read_text("utf-8")
    assert committed == text
    assert holdout is (run_id == ensemble.HOLDOUT_RUN_ID)
    assert (summary["S"], summary["S_first"], summary["S_rescued"]) == tuple(
        _entry(run_id, machine)[key] for key in ("S", "S_first", "S_rescued")
    )


@pytest.mark.parametrize("machine", CLASSES)
def test_a99c_the_holdout_report_is_reported_and_never_gated(machine: str) -> None:
    document = _document(ensemble.HOLDOUT_RUN_ID, machine)
    text, summary, _ = SCRIPT.render(document)
    lines = text.splitlines()
    assert lines[0] == "# " + ensemble.HOLDOUT_HEADER.format(run_id=ensemble.HOLDOUT_RUN_ID)
    assert not any(re.search(r"\bgate S >=|: (PASS|FAIL)$", line) for line in lines)
    s_run2 = int(_entry("run2", machine)["S"])
    assert (
        f"S_holdout − S_run2 = {summary['S'] - s_run2:+d} (run 2 on {machine}: S = {s_run2})."
        in lines[2]
    )
    bounds = (
        f"One-sided 95 % Clopper–Pearson lower bound: on S {summary['cp_lower']:.6f}; on S^first "
        f"{summary['cp_lower_first']:.6f} (reported, never gated)."
    )
    assert bounds in lines
    assert summary["cp_lower"] == ensemble.clopper_pearson_lower(summary["S"], ensemble.N)
    assert summary["cp_lower_first"] == ensemble.clopper_pearson_lower(
        summary["S_first"], ensemble.N
    )
    counts = summary["refinements"]
    assert (
        f"Refinements (ADR 0018; A90 (A5)): fired {counts['fired']}, kept {counts['kept']}, "
        f"reverted {counts['reverted']}, abandoned {counts['abandoned']}"
    ) in text


@pytest.mark.parametrize("run_id", ["run2r", ensemble.HOLDOUT_RUN_ID])
def test_a99c_a35_the_committed_comparison_recomputes(
    run_id: str, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = argparse.Namespace(
        results=[str(REPO_ROOT / _entry(run_id, machine)["file"]) for machine in CLASSES]
    )
    assert SCRIPT.compare(arguments) == 0
    committed = (RUNS_DIR / f"{run_id}.compare.txt").read_text("utf-8")
    assert capsys.readouterr().out == committed


# -- A99 (d): no holdout crash; its classes are its report's ---------------------------------------


@pytest.mark.parametrize("machine", CLASSES)
def test_a99d_no_holdout_crash_and_its_classes_are_reported(machine: str) -> None:
    document = _document(ensemble.HOLDOUT_RUN_ID, machine)
    classes: dict[str, int] = {}
    for record in document["records"]:
        name = ensemble.classify(record)
        classes[name] = classes.get(name, 0) + 1
    assert classes.get("F-CRASH", 0) == 0
    text = (RUNS_DIR / f"{_stem(ensemble.HOLDOUT_RUN_ID, machine)}.report.txt").read_text("utf-8")
    assert f"Classes: {dict(sorted(classes.items()))}" in text.splitlines()
