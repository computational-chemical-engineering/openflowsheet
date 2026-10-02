"""T06 W28: run records, the machine class, ADR 0018's refinement records (A97 (a)–(d), A90, A98).

Spec `docs/derivations/T06-corpus-spec.md` §6.6 (A5), §7.5 (A5), §7.6 (A5), A90 (A5), A97, A98;
register R-090. The harness is `benchmarks/t06/ensemble.py` and `scripts/t06_ensemble.py`;
`generator.py` is not edited (A25 still regenerates the nominal file byte for byte). A97 (a)–(d)
run the harness on single published starts; A90's counts, the holdout's report mode and A98's
comparison are checked on synthetic records, whose expectations are stated here rather than
produced by the code under test.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t06_ensemble_support import RUNS_DIR, STARTS_FILE, ensemble_cases
from t06_support import T06_REVISION_POLICY_V1
from test_t06_w6_ensemble import _record
from test_t06_w6_generator import BY_CASE, PUBLISHED

from benchmarks.t06 import ensemble, generator

SPEC = (REPO_ROOT / "docs" / "derivations" / "T06-corpus-spec.md").read_text("utf-8")
REGISTRY: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "registry.yaml")
CASES = {case.case: case for case in ensemble_cases()}
REFERENCE_CPU = "AMD Ryzen Threadripper PRO 5965WX 24-Cores"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t06_ensemble_script", REPO_ROOT / "scripts" / "t06_ensemble.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _script()


def _start(case: str, index: int) -> dict[str, Any]:
    (start,) = [s for s in BY_CASE[case]["starts"] if s["start"] == index]
    return start


# -- A97 (b): the machine class, decided from the host ---------------------------------------------


@pytest.mark.parametrize(
    ("github", "machine", "cpu", "expected"),
    [
        ("true", "x86_64", "AMD EPYC 7763 64-Core Processor", "ci-x86-64"),
        ("true", "aarch64", "aarch64", "ci-aarch64"),
        (None, "x86_64", REFERENCE_CPU, "ref-x86-64"),
        (None, "x86_64", "Intel(R) Xeon(R) Platinum 8370C", "unregistered(x86_64)"),
        (None, "aarch64", "aarch64", "unregistered(aarch64)"),
        ("false", "x86_64", REFERENCE_CPU, "ref-x86-64"),
        ("true", "x86_64", REFERENCE_CPU, "ci-x86-64"),
        ("true", "riscv64", "riscv", "unregistered(riscv64)"),
    ],
)
def test_a97b_the_machine_class_is_decided_from_the_host(
    monkeypatch: pytest.MonkeyPatch, github: str | None, machine: str, cpu: str, expected: str
) -> None:
    if github is None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    else:
        monkeypatch.setenv("GITHUB_ACTIONS", github)
    monkeypatch.setattr(ensemble.platform, "machine", lambda: machine)
    monkeypatch.setattr(generator, "_cpu_model", lambda: cpu)
    assert ensemble.machine_class() == expected
    assert ensemble.host()["machine_class"] == expected


def test_a97b_the_registered_classes_and_the_generators_literal() -> None:
    """The registry's classes are §7.5's three, the reference CPU is registered, and the harness
    never writes a class as a literal: `host()` is `generator.host()` with the class replaced,
    so on `ref-x86-64` it is the block the published starts record."""
    classes = REGISTRY["ensemble"]["machine_classes"]
    assert set(classes) == {"ref-x86-64", "ci-x86-64", "ci-aarch64"}
    assert classes["ref-x86-64"]["cpu_model"] == REFERENCE_CPU
    assert {name: entry["runner"] for name, entry in classes.items() if "runner" in entry} == {
        "ci-x86-64": "ubuntu-latest",
        "ci-aarch64": "ubuntu-24.04-arm",
    }
    source = Path(ensemble.__file__).read_text("utf-8")
    assert '"ref-x86-64"' not in source.replace('REFERENCE_CLASS: Final = "ref-x86-64"', "")
    host = ensemble.host()
    assert {k: v for k, v in host.items() if k != "machine_class"} == {
        k: v for k, v in generator.host().items() if k != "machine_class"
    }
    if ensemble.machine_class() == ensemble.REFERENCE_CLASS:
        assert host == PUBLISHED["host"]


@pytest.mark.parametrize("holdout", [False, True])
def test_a97b_generate_refuses_off_the_reference_class(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, holdout: bool
) -> None:
    monkeypatch.setattr(ensemble, "machine_class", lambda: "ci-aarch64")
    out = tmp_path / "starts.json"
    arguments = argparse.Namespace(holdout=holdout, force=False, out=str(out))
    assert SCRIPT.generate(arguments) == 2
    assert not out.exists()


def test_generate_refuses_to_overwrite_or_to_force_the_holdout(tmp_path: Path) -> None:
    if ensemble.machine_class() != ensemble.REFERENCE_CLASS:
        pytest.skip("generate writes on ref-x86-64 only (A97 (b) checks the refusal)")
    existing = tmp_path / "starts.json"
    existing.write_text("{}")
    for holdout, force in ((False, False), (True, False), (True, True)):
        arguments = argparse.Namespace(holdout=holdout, force=force, out=str(existing))
        assert SCRIPT.generate(arguments) == 2
        assert existing.read_text() == "{}"


# -- A97 (a): the v2 run document --------------------------------------------------------------


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout


def _run(tmp_path: Path, **overrides: Any) -> tuple[int, Path]:
    out = tmp_path / "run.json"
    fields: dict[str, Any] = {
        "run_id": "a97a",
        "file": "",
        "out": str(out),
        "allow_dirty": True,
        "cases": ["STR-01"],
        "starts": [0],
    }
    fields.update(overrides)
    return SCRIPT.run(argparse.Namespace(**fields)), out


def test_a97a_run_writes_the_v2_record(tmp_path: Path) -> None:
    head = _git("rev-parse", "HEAD").strip()
    clean = _git("status", "--porcelain") == ""
    status, out = _run(tmp_path)
    assert status == 0
    document = json.loads(out.read_text())
    assert document["format"] == ensemble.RESULTS_FORMAT == "t06-ensemble-results-v2"
    assert document["run_id"] == "a97a"
    assert re.fullmatch(r"[0-9a-f]{40}", document["commit"]) and document["commit"] == head
    assert document["tree_clean"] is clean
    lock = hashlib.sha256((REPO_ROOT / "requirements.lock").read_bytes()).hexdigest()
    assert document["environment_lock_sha256"] == lock
    assert document["cache_condition"] == REGISTRY["ensemble"]["cache_condition"]
    assert document["starts_file"] == str(STARTS_FILE.relative_to(REPO_ROOT))
    assert document["starts_sha256"] == REGISTRY["ensemble"]["starts_sha256"]
    assert document["policies"] == ensemble.policies([CASES["STR-01"]])
    assert document["host"] == ensemble.host()
    assert document["host"]["machine_class"] == ensemble.machine_class()
    (record,) = document["records"]
    assert (record["case"], record["start"]) == ("STR-01", 0)
    assert [entry["last"] for entry in record["refinements"]][-1] is True


def test_a97a_run_refuses_a_dirty_tree_without_allow_dirty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dirty = {**ensemble.provenance(REPO_ROOT), "tree_clean": False}
    monkeypatch.setattr(ensemble, "provenance", lambda root: dirty)
    status, out = _run(tmp_path, allow_dirty=False)
    assert status == 2 and not out.exists()


def test_the_holdout_run_id_and_the_holdout_file_go_together(tmp_path: Path) -> None:
    status, out = _run(tmp_path, run_id=ensemble.HOLDOUT_RUN_ID, file=str(STARTS_FILE))
    assert status == 2 and not out.exists()


# -- A97 (c): cold per start ---------------------------------------------------------------------


@pytest.mark.parametrize(("case", "index"), [("THM-09", 1), ("NET-01", 0), ("NET-05", 0)])
def test_a97c_a_start_run_twice_in_one_process_spends_the_same(case: str, index: int) -> None:
    """A provider cache, compiled problem or warm start carried between starts would change
    `cache_hits` or `property_calls` on the second run. *Measured (A5):* 386, 288, 429 calls."""
    first = ensemble.run_start(CASES[case], _start(case, index))
    second = ensemble.run_start(CASES[case], _start(case, index))
    assert first["counters"] == second["counters"]
    assert first["state"] == second["state"]
    # The absolute counts are A97 (c)'s *measured* values on `ref-x86-64`, not its assertion (equal
    # counters within one process); iteration counts, hence property calls, may differ by machine
    # (CI 36278604955: NET-05/0 spends 430 on ci-aarch64). Pinned on the reference class only.
    if ensemble.machine_class() == "ref-x86-64":
        measured = {"THM-09": 386, "NET-01": 288, "NET-05": 429}[case]
        assert first["counters"]["property_calls"] == measured


# -- A97 (d): the refinement records ---------------------------------------------------------------


def test_a97d_thm09_start_1_keeps_one_refinement_in_its_last_attempt() -> None:
    record = ensemble.run_start(CASES["THM-09"], _start("THM-09", 1))
    fired = [entry for entry in record["refinements"] if entry["fired"]]
    assert len(fired) == 1
    (entry,) = fired
    assert entry["result"] == "accepted" and entry["last"] is True
    assert entry["column"] in {"S3.T", "S4.T"}
    assert entry["attempt_outcome"] == "CONVERGED"
    assert isinstance(entry["rho"], float) and entry["rho"] > 1.0
    assert record["refinements"][-1] is entry
    assert [e["last"] for e in record["refinements"]].count(True) == 1


def test_a97d_under_plain_newton_nothing_fires() -> None:
    case = CASES["THM-09"]
    assert T06_REVISION_POLICY_V1.globalization.eo_core == "newton"
    plain = replace(case, policy=T06_REVISION_POLICY_V1)
    record = ensemble.run_start(plain, _start("THM-09", 1))
    # Run 1 (`T06-revision-v1`) scored this start `F-OTHER-ROOT`, one of THM-09's four (A95).
    run1 = json.loads((RUNS_DIR / "run1-ref-x86-64.json").read_text())
    (judged,) = [r for r in run1["records"] if (r["case"], r["start"]) == ("THM-09", 1)]
    assert ensemble.classify(record) == ensemble.classify(judged) == "F-OTHER-ROOT"
    assert record["refinements"] and not any(entry["fired"] for entry in record["refinements"])


def _event(message: str, attempt: int = 1, kind: str = "attempt_closed") -> Any:
    return SimpleNamespace(
        kind=kind, message=message, attempt=attempt, step_index=2, outcome="CONVERGED"
    )


def test_a97d_the_grammar_parses_every_word_of_d5() -> None:
    events = [
        _event("", attempt=1),
        _event("jacobian", kind="jacobian"),
        _event("terminal_refinement(reverted: chord singular): chord 3.5 at S3.T", attempt=2),
        _event(
            "terminal_refinement(abandoned: EVALUATION_ERROR): chord 10.02370482213442 at S3.T\n"
            "second line",
            attempt=3,
        ),
        _event("terminal_refinement(accepted: chord 0.25 at S4.T): chord 12.5 at S4.T", 4),
    ]
    entries = ensemble.refinements(events)
    assert [(e["attempt"], e["fired"], e["result"], e["last"]) for e in entries] == [
        (1, False, None, False),
        (2, True, "reverted", False),
        (3, True, "abandoned", False),
        (4, True, "accepted", True),
    ]
    assert entries[1]["reason"] == "chord singular" and entries[1]["rho"] == 3.5
    assert entries[2]["reason"] == "EVALUATION_ERROR"
    assert entries[2]["rho"] == 10.02370482213442 and entries[2]["column"] == "S3.T"
    assert entries[3]["reason"] == "chord 0.25 at S4.T" and entries[3]["column"] == "S4.T"
    assert all(e["step"] == 2 and e["attempt_outcome"] == "CONVERGED" for e in entries)
    assert ensemble.refinements([]) == []


@pytest.mark.parametrize(
    "message",
    [
        "terminal_refinement(kept: chord 0.1 at S3.T): chord 2.0 at S3.T",
        "terminal_refinement(accepted): chord 2.0 at S3.T",
        "terminal_refinement(accepted: x): chord 2.0",
        # `numerics/newton.py`'s message when the chord back-solve fails before any refinement:
        # it begins `terminal_refinement(` and D5's grammar does not parse it, so §6.6 (A5)
        # stops the run on it (reported to the design lane with W28).
        "terminal_refinement(abandoned: chord singular)",
    ],
)
def test_a97d_a_message_outside_the_grammar_stops_the_run(message: str) -> None:
    with pytest.raises(ensemble.RefinementGrammarError):
        ensemble.refinements([_event(message)])


def test_a97d_run_start_does_not_turn_a_grammar_defect_into_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def defective(events: Any) -> list[dict[str, Any]]:
        raise ensemble.RefinementGrammarError("constructed")

    monkeypatch.setattr(ensemble, "refinements", defective)
    with pytest.raises(ensemble.RefinementGrammarError):
        ensemble.run_start(CASES["STR-01"], _start("STR-01", 0))


# -- A90 (A5): the report's counts, on synthetic records ------------------------------------------


def _entry(
    attempt: int, result: str | None, *, last: bool = False, reason: str = "chord 0.5 at S3.T"
) -> dict[str, Any]:
    return {
        "step": 1,
        "attempt": attempt,
        "attempt_outcome": "CONVERGED",
        "last": last,
        "fired": result is not None,
        "result": result,
        "reason": None if result is None else reason,
        "rho": None if result is None else 4.0,
        "column": None if result is None else "S3.T",
    }


BUDGET = (
    "the property-call budget of 10000 is spent; the call to evaluate_phase(LIQUID) was refused "
    "rather than made, so the recorded count is exactly the cap 10000"
)


def _synthetic() -> list[dict[str, Any]]:
    """Two cases, five starts each. NET-03: 00 kept (last), 01 not fired, 02 reverted (last), 03
    fired and kept in a non-final attempt then not fired, 04 abandoned for budget in its last
    attempt. NET-10: 00 kept (last, worst 0.3), 01 abandoned `LINE_SEARCH_FAILED` (last), 02–04
    not fired."""
    records = [
        _record(case="NET-03", start=0, refinements=[_entry(1, "accepted", last=True)]),
        _record(case="NET-03", start=1, refinements=[_entry(1, None, last=True)]),
        _record(case="NET-03", start=2, refinements=[_entry(1, "reverted", last=True)]),
        _record(
            case="NET-03",
            start=3,
            refinements=[_entry(1, "accepted"), _entry(2, None, last=True)],
        ),
        _record(
            case="NET-03",
            start=4,
            outcome="BUDGET_EXHAUSTED",
            message=BUDGET,
            certificate=None,
            refinements=[_entry(1, "abandoned", last=True, reason="EVALUATION_ERROR")],
        ),
        _record(
            case="NET-10",
            start=0,
            worst=[0.3, "S4.T"],
            refinements=[_entry(1, "accepted", last=True)],
        ),
        _record(
            case="NET-10",
            start=1,
            refinements=[_entry(1, "abandoned", last=True, reason="LINE_SEARCH_FAILED")],
        ),
    ]
    records += [
        _record(case="NET-10", start=s, refinements=[_entry(1, None, last=True)]) for s in (2, 3, 4)
    ]
    return records


FACTS = {case: {"acyclic": False, "column_scales": {}} for case in ("NET-03", "NET-10")}


def test_a90_the_report_counts_fired_kept_reverted_and_abandoned() -> None:
    summary = ensemble.report(_synthetic(), FACTS, PUBLISHED)
    counted = summary["refinements"]
    assert {key: counted[key] for key in ("fired", "kept", "reverted", "abandoned")} == {
        "fired": 6,
        "kept": 3,
        "reverted": 1,
        "abandoned": 2,
    }
    assert counted["abandoned_by_reason"] == {"EVALUATION_ERROR": 1, "LINE_SEARCH_FAILED": 1}
    assert counted["abandoned_budget"] == 1
    assert counted["not_last"] == [["NET-03", 3, 1, 1, "accepted", "chord 0.5 at S3.T", False]]
    assert [(c, s) for c, s, *_ in counted["fired_at"]] == [
        ("NET-03", 0),
        ("NET-03", 2),
        ("NET-03", 3),
        ("NET-03", 4),
        ("NET-10", 0),
        ("NET-10", 1),
    ]
    per_case = summary["per_case"]
    assert per_case["NET-03"]["refinements"]["fired"] == 4
    assert per_case["NET-03"]["refinements"]["abandoned_budget"] == 1
    assert per_case["NET-10"]["refinements"] == {
        "fired": 2,
        "kept": 1,
        "reverted": 0,
        "abandoned": 1,
        "abandoned_budget": 0,
        "abandoned_by_reason": {"LINE_SEARCH_FAILED": 1},
    }
    # S3's worst ratio (reported): kept in the final attempt — NET-03/00 (0.5), NET-10/00 (0.3);
    # did not fire — NET-03/01, /03 and NET-10/02–04 (0.5 each).
    worst = counted["worst_ratio"]
    assert (worst["kept"]["n"], worst["kept"]["max"]) == (2, 0.5)
    assert (worst["not_fired"]["n"], worst["not_fired"]["max"]) == (5, 0.5)
    text = ensemble.render(summary)
    assert "Refinements (ADR 0018; A90 (A5)): fired 6, kept 3, reverted 1, abandoned 2" in text
    assert "abandoned (budget) 1" in text
    assert "Fired outside a start's last attempt (ADR 0018 D4′ (ii)): 1; NET-03 03" in text
    assert "| NET-03 | 4 | 2 | 1 | 1 | 1 |" in text


def test_a90_a_v1_file_reads_as_not_recorded() -> None:
    records = [{k: v for k, v in r.items() if k != "refinements"} for r in _synthetic()]
    summary = ensemble.report(records, FACTS, PUBLISHED)
    assert summary["refinements"] is None
    assert all(case["refinements"] is None for case in summary["per_case"].values())
    assert "Refinements (ADR 0018; A90 (A5)): not recorded." in ensemble.render(summary)


def test_a90_the_expected_reconstruction_is_the_specs() -> None:
    """A90 (A5)'s seventeen starts, read from the spec's text rather than typed twice."""
    (listed,) = re.findall(r"17 fired, 17 kept, 0 reverted, 0 abandoned, at (.*?), each in", SPEC)
    expected: list[tuple[str, int]] = []
    for group in listed.split("; "):
        case, first, *rest = re.split(r"/|, /", group)
        expected += [(case, int(index)) for index in (first, *rest)]
    assert tuple(expected) == ensemble.A90_EXPECTED_REF_X86_64
    assert len(expected) == 17


def test_replay_does_not_compare_refinements_with_a_v1_record() -> None:
    emitted = _record(refinements=[_entry(1, "accepted", last=True)])
    v1 = {k: v for k, v in emitted.items() if k != "refinements"}
    assert ensemble.replay_differences(v1, emitted) == []
    assert ensemble.replay_differences(emitted, emitted) == []
    assert ensemble.replay_differences(emitted, {**emitted, "refinements": []}) != []


# -- the holdout's report mode (§7.6 (A5)) ---------------------------------------------------------


def test_the_holdout_report_has_its_header_and_no_gate_line() -> None:
    summary = ensemble.report(_synthetic(), FACTS, PUBLISHED)
    holdout = {"run_id": "holdout1", "machine_class": "ref-x86-64", "s_run2": 434}
    run = {
        "run_id": "holdout1",
        "commit": "0" * 40,
        "tree_clean": True,
        "machine_class": "ref-x86-64",
        "starts_sha256": "f" * 64,
    }
    text = ensemble.render(summary, run=run, holdout=holdout)
    lines = text.splitlines()
    assert lines[0] == "# HOLDOUT holdout1 — reported, never gated (T06 spec §7.6 (A5))"
    assert "gate" not in lines[2] and "gate S >=" not in text
    assert ": PASS" not in text and ": FAIL" not in text
    assert f"S_holdout − S_run2 = {summary['S'] - 434:+d} (run 2 on ref-x86-64: S = 434)" in text
    assert "Clopper–Pearson lower bound: on S" in text and "on S^first" in text
    assert f"Run holdout1 at {'0' * 40} (tree clean: yes), machine class ref-x86-64" in text
    unregistered = {**holdout, "machine_class": "unregistered(riscv64)", "s_run2": None}
    assert "run 2 has no registered file on unregistered(riscv64)" in ensemble.render(
        summary, holdout=unregistered
    )


# -- A98: run 2r against run 2, on synthetic documents -------------------------------------------


def _document(records: list[dict[str, Any]], **fields: Any) -> dict[str, Any]:
    base = {
        "format": ensemble.RESULTS_FORMAT,
        "tree_clean": True,
        "starts_sha256": "a" * 64,
        "policies": {"T06-revision-v2": "c" * 64},
        "records": records,
    }
    base.update(fields)
    return base


def _pair() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run 2 (v1: no refinements) and a matching run 2r over NET-10 00–03, with NET-10/00
    refined and kept in its last attempt; every state is `[["x", 1.0]]`."""
    run2 = [_record(case="NET-10", start=s, state=[["x", 1.0]]) for s in range(4)]
    rerun = [
        {**r, "refinements": [_entry(1, "accepted" if r["start"] == 0 else None, last=True)]}
        for r in run2
    ]
    return run2, rerun


def test_a98_equal_runs_have_no_discrepancy() -> None:
    run2, rerun = _pair()
    found = ensemble.a98_discrepancies(
        _document(rerun), _document(run2, format="v1"), [("NET-10", 0)]
    )
    assert found["discrepancies"] == []
    assert (found["S"], found["S_first"], found["starts"]) == ([4, 4], [4, 4], 4)
    assert found["state_bitwise_differences"] == []
    assert found["refinements"]["fired"] == found["refinements"]["kept"] == 1


def test_a98_a_changed_class_or_s_is_a_discrepancy_and_a_moved_state_is_reported() -> None:
    run2, rerun = _pair()
    rerun[1] = {**rerun[1], "outcome": "STAGNATION", "certificate": None}
    rerun[2] = {**rerun[2], "state": [["x", 1.0000000000000002]]}
    found = ensemble.a98_discrepancies(_document(rerun), _document(run2), None)
    assert found["discrepancies"] == [
        "NET-10 01: class F-TYPED(STAGNATION), run 2 SUCCESS",
        "S = 3 (S^first 3), run 2 S = 4 (S^first 4)",
    ]
    assert found["state_bitwise_differences"] == ["NET-10 02"]


def test_a98_a_missing_record_a_dirty_tree_or_another_starts_file_is_a_discrepancy() -> None:
    run2, rerun = _pair()
    found = ensemble.a98_discrepancies(
        _document(rerun[:3], tree_clean=False, starts_sha256="b" * 64), _document(run2), None
    )
    assert "NET-10 03: recorded in run 2 only" in found["discrepancies"]
    assert any(line.startswith("tree_clean") for line in found["discrepancies"])
    assert any(line.startswith("starts_sha256") for line in found["discrepancies"])


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("missing", "NET-10 00: refinements [], expected one kept in the last attempt"),
        (
            "extra",
            "NET-10 02: refinements [('accepted', 'chord 0.5 at S3.T', True)], expected none",
        ),
        ("reverted", "NET-10 00: refinements [('reverted', 'chord 0.5 at S3.T', True)]"),
        ("not_last", "NET-10 00: refinements [('accepted', 'chord 0.5 at S3.T', False)]"),
    ],
)
def test_a98_refinements_other_than_the_reconstruction_are_a_discrepancy(
    change: str, expected: str
) -> None:
    run2, rerun = _pair()
    if change == "missing":
        rerun[0] = {**rerun[0], "refinements": [_entry(1, None, last=True)]}
    elif change == "extra":
        rerun[2] = {**rerun[2], "refinements": [_entry(1, "accepted", last=True)]}
    elif change == "reverted":
        rerun[0] = {**rerun[0], "refinements": [_entry(1, "reverted", last=True)]}
    else:
        rerun[0] = {
            **rerun[0],
            "refinements": [_entry(1, "accepted"), _entry(2, None, last=True)],
        }
    found = ensemble.a98_discrepancies(_document(rerun), _document(run2), [("NET-10", 0)])
    assert len(found["discrepancies"]) == 1
    assert found["discrepancies"][0].startswith(expected)
    # Without an expectation (the CI classes) the refinements are counted, not judged.
    assert (
        ensemble.a98_discrepancies(_document(rerun), _document(run2), None)["discrepancies"] == []
    )
