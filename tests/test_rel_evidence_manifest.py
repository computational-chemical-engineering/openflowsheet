"""ADR 0055 WO-R6: `scripts/release_evidence_manifest.py` (RP §11). The catalogue is RP.S01–S22
as §11.1 states them; the changed-form assertions RP.S10, S13, S17, S20 and S21 each have a record
that meets the standing form and one failing control per changed rule (§11.2); REL.A20 runs the
generator over 0.3.0's committed records (S13's manifest)."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import release_evidence_manifest as rem  # noqa: E402
import release_gate as rg  # noqa: E402
import v0_2_gate as engine  # noqa: E402

C = "c" * 40
S13 = ROOT / "evidence" / "S13" / "a3e508e35fc5451fe56fa7b70941621992d35b50"
CI = ROOT / "tests" / "fixtures" / "rel" / "s13-ci"
AUDIT = (
    "G11 experiments audit: 2 runs, 210 boundary points, 210 results, 210 attempts, 0 without a "
    "result, 32 direct points (no records); 6 items + schema: 0 problems; context (job_id): 420 "
    "findings: PASS"
)


def _inputs(tmp_path: Path, **kwargs: Any) -> rem.Inputs:
    return rem.Inputs(rem.load_line("0.4"), C, evidence=tmp_path, **kwargs)


def _write(inputs: rem.Inputs, records: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
    """`t08-rc-v1` records at C under `rc/`, and `rc/records.json` listing them."""
    files = []
    for path, checks in records.items():
        file = inputs.rc_dir / path
        file.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "format": "t08-rc-v1",
            "step": path,
            "passed": all(check["result"] == "pass" for check in checks),
            "provenance": {"commit": C, "tree_clean": True, "machine_class": "ref-x86-64"},
            "checks": [dict(check) for check in checks],
        }
        file.write_text(json.dumps(document), encoding="utf-8")
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        files.append({"path": path, "sha256": digest, "committed": True})
    (inputs.rc_dir / "records.json").write_text(json.dumps({"commit": C, "files": files}), "utf-8")


# -- the catalogue ----------------------------------------------------------------------------


def test_the_catalogue_is_rp_s01_to_s22_with_their_forms() -> None:
    listed = rem.catalogue()
    assert list(listed) == [f"S{n:02d}" for n in range(1, 23)]
    assert [s.id for s in rem.SPECS] == list(listed)
    assert {k for k, a in listed.items() if not a.same_form} == set(rem.CHANGED_FORM)
    assert listed["S11"].counterpart == "V03.A20" and listed["S22"].counterpart is None
    d_gated = {k for k, a in listed.items() if "D" in a.gates}
    assert d_gated == {"S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S22"}


def test_a_catalogue_that_loses_an_assertion_stops() -> None:
    text = rem.RP.read_text(encoding="utf-8")
    start = text.index("- **RP.S12**")
    with pytest.raises(SystemExit, match="forms differ"):
        rem.catalogue(text[:start] + text[text.index("- **RP.S13**") :])


# -- D: the line's own measures -----------------------------------------------------------------


def test_s02_the_version_table_is_t_v3_for_0_3() -> None:
    covered, not_covered = rem.version_table("0.3")
    assert (len(covered), len(not_covered)) == (4, 13)
    assert "0.30.0" in not_covered and "0.3.0 " in not_covered and "0.2.0rc1" in not_covered
    assert rem.version_table("1.0")[1][-1] == "1.0.0 "


@pytest.mark.parametrize("line", ["0.3", "0.4"])
def test_s02_and_s05_hold_for_the_committed_lines(line: str, tmp_path: Path) -> None:
    inputs = rem.Inputs(rem.load_line(line), C, evidence=tmp_path)
    assert rem._m_version_table(inputs)[0] == "pass"
    assert rem._m_clause(inputs)[0] == "pass"


def test_s02_and_s05_controls(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    document = dict(inputs.line.document)
    wide = {**document["gate_set"], "covers": r"0\.4\.0(?:(?:a|b|rc)[0-9]+)?"}
    clause = document["gate_set"]["clause"].replace("W2[1-6]", "W2[1-7]")  # W27 added
    loose = {**document["gate_set"], "clause": clause}
    for gate_set, measure in ((wide, rem._m_version_table), (loose, rem._m_clause)):
        line = rg.Line(({**document, "gate_set": gate_set}, *inputs.line.chain[1:]))
        result, value = measure(rem.Inputs(line, C, evidence=tmp_path))
        assert result == "fail", value


# -- R: the changed-form assertions, a passing record and one control per changed rule ----------


def test_s21_exactly_r375_audit_with_its_line(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    audit = {"id": "r375.audit", "result": "pass", "exit_code": 0, "last_line": AUDIT}
    _write(inputs, {rem.STEP12_EXPERIMENTS: [audit]})
    assert rem._m_experiments(inputs)[0] == "pass"
    # Control (the changed rule): 0.3.0's record, with the re-run checks (a) and (b) beside it.
    rerun = [{"id": i, "result": "pass"} for i in ("r375.g11_rerun", "r375.same_computation")]
    _write(inputs, {rem.STEP12_EXPERIMENTS: [audit, *rerun]})
    assert rem._m_experiments(inputs)[0] == "fail"
    # Control: an empty audit's line.
    empty = {**audit, "last_line": AUDIT.replace("210 results", "0 results")}
    _write(inputs, {rem.STEP12_EXPERIMENTS: [empty]})
    assert rem._m_experiments(inputs)[0] == "fail"


def _step14(n: int, *, equal: bool = True) -> list[dict[str, Any]]:
    selection = {
        "id": "a60.w24.nlp_selection",
        "result": "pass",
        "modules": ["tests/test_m05_trf.py"],
        "selected_count": n,
        "all_count": n,
        "equal": equal,
        "selected_exit_code": 0,
    }
    return [{"id": "a60.w24.nlp_tier_and_inventory", "result": "pass"}, selection]


def test_s20_equal_sets_and_n_at_least_one_not_190(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    _write(inputs, {rem.STEP_RECORD[14]: _step14(7)})
    assert rem._m_nlp_selection(inputs)[0] == "pass"  # 0.3.0 required n = 190
    # Control (the changed rule): an empty selection that compares equal to an empty collection.
    _write(inputs, {rem.STEP_RECORD[14]: _step14(0)})
    assert rem._m_nlp_selection(inputs)[0] == "fail"
    _write(inputs, {rem.STEP_RECORD[14]: _step14(7, equal=False)})
    assert rem._m_nlp_selection(inputs)[0] == "fail"


def test_s13_one_record_per_item(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    ids = [str(item["id"]) for item in inputs.items]
    records = {rem.item_record(i): [{"id": i, "result": "pass"}] for i in ids}
    _write(inputs, records)
    assert rem._m_items(inputs)[0] == "pass"
    assert all(rem.item_part(item, inputs)[0] == "pass" for item in inputs.items)
    # Control (the changed rule): a record that is not one check named for its item (17a-style).
    _write(inputs, {**records, rem.item_record(ids[0]): [{"id": "a17.wheel", "result": "pass"}]})
    assert rem._m_items(inputs)[0] == "fail"
    # Control: `unsupported` is not a pass; an absent record fails.
    _write(inputs, {**records, rem.item_record(ids[1]): [{"id": ids[1], "result": "unsupported"}]})
    assert rem._m_items(inputs)[0] != "pass"
    _write(inputs, {k: v for k, v in records.items() if k != rem.item_record(ids[2])})
    assert rem._m_items(inputs)[0] == "fail"


def _verdict(
    order: Sequence[str], failing: Mapping[str, tuple[str, ...]]
) -> engine.VerdictDocument:
    rows = {
        gate: engine.VerdictRow("FAIL" if gate in failing else "PASS", failing.get(gate, ()), ())
        for gate in order
    }
    return engine.VerdictDocument(C, datetime.date(2027, 1, 4), rows)


def _row(item: str) -> rg.Row:
    return rg.Row(item, "accepted, 2027-01-05", "`paths:docs/x.md`", "f" * 64, C)


@pytest.fixture
def standing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """A verdict document with V14 (b) failing, and a standing table whose rows all stand unless
    named in `lapsed`."""
    state: dict[str, Any] = {"lapsed": set(), "table": None}
    inputs = _inputs(tmp_path, version="0.4.0")
    claimed = inputs.gate_set.claimed
    state["verdict"] = _verdict(claimed, {"V14": ("V14 (b)",)})
    decisions = tuple(_row(item) for item in inputs.gate_set.frank_items)
    state["table"] = rg.Acceptances((_row("V14 (b)"),), decisions)
    monkeypatch.setattr(rem, "_verdict", lambda _: state["verdict"])
    monkeypatch.setattr(rem, "_standing_rows", lambda _: (state["table"], None))
    monkeypatch.setattr(
        rg,
        "row_state",
        lambda row, _: rg.RowState("lapsed", "paths")
        if row.item in state["lapsed"]
        else rg.RowState("stands"),
    )
    state["inputs"] = inputs
    return state


def _changelog(tmp_path: Path, phrases: Sequence[str], lines: Sequence[str]) -> Path:
    body = "\n".join(f"- {phrase}" for phrase in phrases) + "\n" + "\n".join(lines)
    path = tmp_path / "CHANGELOG.md"
    path.write_text(f"# Changelog\n\n## v0.4.0\n\n{body}\n\n## v0.3.0\n\n- x\n", "utf-8")
    return path


def test_s10_phrases_once_and_the_failure_lines(
    standing: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    inputs = standing["inputs"]
    phrases = list(inputs.line.document["changelog_what_it_is_not"])
    line = "- V14 (b) FAIL, accepted by Frank 2027-01-05 (release/acceptances.md)"
    monkeypatch.setattr(rem, "CHANGELOG", _changelog(tmp_path, phrases, [line]))
    assert rem._m_changelog(inputs)[0] == "pass"
    # Control (the changed rule, D3.5): the accepted failure clause's line is missing.
    monkeypatch.setattr(rem, "CHANGELOG", _changelog(tmp_path, phrases, []))
    assert rem._m_changelog(inputs)[0] == "fail"
    # Control (the changed rule): a phrase twice.
    monkeypatch.setattr(rem, "CHANGELOG", _changelog(tmp_path, [*phrases, phrases[0]], [line]))
    assert rem._m_changelog(inputs)[0] == "fail"
    # A lapsed row's clause is not in force, so its line is not required.
    standing["lapsed"] = {"V14 (b)"}
    monkeypatch.setattr(rem, "CHANGELOG", _changelog(tmp_path, phrases, []))
    assert rem._m_changelog(inputs)[0] == "pass"


def test_s17_the_verdict_document_and_the_standing_table(standing: dict[str, Any]) -> None:
    inputs = standing["inputs"]
    assert rem._m_verdict_document(inputs)[0] == "pass"
    assert rem._m_acceptances(inputs)[0] == "pass"
    # Control (the changed rule): a row the gate needs has lapsed.
    standing["lapsed"] = {inputs.gate_set.frank_items[0]}
    assert rem._m_acceptances(inputs)[0] == "fail"
    standing["lapsed"] = set()
    # Control: the failing clause has no row; and a dated (non-standing) acceptances file.
    standing["table"] = rg.Acceptances((), standing["table"].decisions)
    assert rem._m_acceptances(inputs)[0] == "fail"
    standing["table"] = None
    assert rem._m_acceptances(inputs)[0] == "fail"
    # Control: rows out of claimed order.
    claimed = inputs.gate_set.claimed
    standing["verdict"] = _verdict((claimed[1], claimed[0], *claimed[2:]), {})
    assert rem._m_verdict_document(inputs)[0] == "fail"


def test_s15_step1_record_holds_exactly_its_four_checks(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    checks = [{"id": i, "result": "pass"} for i in rem.STEP1_CHECKS]
    _write(inputs, {rem.STEP_RECORD[1]: checks})
    assert rem._m_step1(inputs)[0] == "pass"
    _write(inputs, {rem.STEP_RECORD[1]: checks[:3]})
    assert rem._m_step1(inputs)[0] == "fail"


# -- REL.A20 (§11.2) ----------------------------------------------------------------------------


def test_the_ci_fixtures_are_the_runs_s13_read() -> None:
    commands = json.loads((S13 / "manifest.json").read_text(encoding="utf-8"))["commands"]
    read = {c["cmd"].split()[3]: c["stdout_sha256"] for c in commands if c["cmd"].startswith("gh ")}
    for path in sorted(CI.glob("ci-run-*.json")):
        run_id = path.stem.removeprefix("ci-run-")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == read[run_id]


def test_rel_a20_over_0_3_0s_committed_records(tmp_path: Path) -> None:
    """REL.A20 (RP §11.2 with amendment A-1): the generator over 0.3.0's records gives every
    same-form assertion S13's `pass`, and RP.S18 fails only through changed-form assertions, which
    cannot pass over 0.3.0's records by construction. Controls: a same-form check that fails, the
    same with S13's counterpart failing too (A-1's sub-check alone), and zero commands."""
    command = [
        sys.executable,
        str(ROOT / "scripts" / "release_evidence_manifest.py"),
        "--line",
        "0.3",
        "--commit",
        S13.name,
        "--k3",
        "295a2e652c6746b0621350112d6e43945d8b114a",
        *(f"--ci-json={path}" for path in sorted(CI.glob("ci-run-*.json"))),
        "--manifest-adr=0053",
        "--manifest-adr=0054",
        "--evidence=evidence/S13",
        f"--out={tmp_path / 'manifest.json'}",
        f"--tmp={tmp_path / 'tmp'}",
        f"--rel-a20={S13 / 'manifest.json'}",
    ]
    environment = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}"}
    environment.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True, check=False
    )
    lines = completed.stdout.splitlines()
    assert not [line for line in lines if line.startswith("invalid:")], completed.stdout
    for key in rem.SAME_FORM:
        (said,) = [line for line in lines if line.startswith(f"RP.{key} same form: ")]
        assert said.endswith(": equal"), said
    for key in rem.CHANGED_FORM:
        assert any(line.startswith(f"RP.{key} changed form: ") for line in lines)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    results = {entry["id"]: entry["result"] for entry in manifest["checks"]}
    (own,) = [entry for entry in manifest["checks"] if entry["id"] == "RP.S18"]
    not_pass = own["value"]["self"]["not_pass"]
    assert not_pass and {i.removeprefix("RP.") for i in not_pass} <= set(rem.CHANGED_FORM)
    assert results["RP.S20"] == "pass"  # 0.3.0's n = 190 meets n >= 1
    assert results["RP.S13"] == "unsupported"  # the 0.3 line has no rc_items
    assert any(line.startswith("RP.S18 (A-1): ") and line.endswith(": holds") for line in lines)
    assert lines[-1] == "REL.A20: PASS" and completed.returncode == 0, completed.stdout
    s13 = json.loads((S13 / "manifest.json").read_text(encoding="utf-8"))
    assert rem.rel_a20(manifest, s13)[0] is True
    assert rem.rel_a20(*_same_form_fails(manifest, s13, counterpart="pass"))[0] is False
    equal, said = rem.rel_a20(*_same_form_fails(manifest, s13, counterpart="fail"))
    assert equal is False and said[-1].endswith("FAILS") and "RP.S02" in said[-1]
    assert [ln for ln in said if ln.startswith("RP.S02 ")] == [
        "RP.S02 same form: fail; S13 V03.A02 fail: equal"
    ]
    no_commands = json.loads(json.dumps(manifest))
    (own,) = [entry for entry in no_commands["checks"] if entry["id"] == "RP.S18"]
    own["value"]["self"]["commands"] = 0
    assert rem.rel_a20(no_commands, s13)[0] is False


def _same_form_fails(
    manifest: Mapping[str, Any], s13: Mapping[str, Any], *, counterpart: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """REL.A20's control: RP.S02 (same form) fails, and RP.S18 says so; S13's counterpart of
    RP.S02 is given `counterpart`."""
    ours, theirs = json.loads(json.dumps(manifest)), json.loads(json.dumps(s13))
    for entry in ours["checks"]:
        if entry["id"] == "RP.S02":
            entry["result"] = "fail"
        if entry["id"] == "RP.S18":
            entry["value"]["self"]["not_pass"].append("RP.S02")
    for entry in theirs["checks"]:
        if entry["id"] == rem.catalogue()["S02"].counterpart:
            entry["result"] = counterpart
    return ours, theirs


def test_s18_the_generator_s_own_rule(tmp_path: Path) -> None:
    """RP.S18 (a)'s own acceptance (A-1): every other check passes and commands were run gives
    `pass`; one check failing, or zero commands, gives `fail`."""
    others = [{"id": f"RP.S{n:02d}", "result": "pass"} for n in (1, 2, 3)]

    def decided(entries: list[dict[str, Any]], commands: int) -> str:
        own: dict[str, Any] = {"id": "RP.S18", "result": "pass", "value": {}}
        rem._self(own, entries, _inputs(tmp_path, commands=commands))
        return str(own["result"])

    assert decided(others, 3) == "pass"
    assert decided([*others[:2], {"id": "RP.S03", "result": "fail"}], 3) == "fail"
    assert decided([*others[:2], {"id": "RP.S03", "result": "unsupported"}], 3) == "fail"
    assert decided(others, 0) == "fail"


# -- amendment A-4 (RP §6.2, §6.10; review S-3): exactly the push run and the dispatch ------------


def _ci(run_id: int, event: str, conclusion: str = "success", **more: Any) -> dict[str, Any]:
    return {"databaseId": run_id, "event": event, "headSha": C, "conclusion": conclusion, **more}


LISTED = [
    _ci(5, "push", attempt=1),
    _ci(8, "push", attempt=1),
    _ci(10, "workflow_dispatch", "failure", attempt=1),
    _ci(12, "workflow_dispatch", attempt=2),
]


def test_a4_the_manifest_reads_exactly_the_push_run_and_the_dispatch() -> None:
    """One red and one green dispatch at C passed RP.S11 before A-4 (`t08._jobs` takes `success`
    from any run). Now: two dispatches, a run at another commit, an older dispatch or push than
    step 1 lists, or another attempt are refused. Controls: 0.3.0's two runs (no step 1 record),
    and the listed push run and dispatch."""
    saved = [json.loads(path.read_text("utf-8")) for path in sorted(CI.glob("ci-run-*.json"))]
    assert rem.ci_selection_problems(saved, S13.name, None) == []
    assert (
        rem.ci_selection_problems([_ci(8, "push"), _ci(12, "workflow_dispatch")], C, LISTED) == []
    )
    red_and_green = [
        _ci(8, "push"),
        _ci(10, "workflow_dispatch", "failure"),
        _ci(12, "workflow_dispatch"),
    ]
    assert rem.ci_selection_problems(red_and_green, C, None) == [
        "runs [10, 12]: 2 workflow_dispatch runs given, not one (A-4)"
    ]
    elsewhere = {**_ci(12, "workflow_dispatch"), "headSha": "d" * 40}
    assert rem.ci_selection_problems([elsewhere], C, None) == [
        f"run 12: its head {'d' * 40} is not C"
    ]
    older = [_ci(5, "push"), _ci(10, "workflow_dispatch")]
    assert rem.ci_selection_problems(older, C, LISTED) == [
        "run 5 is not the push run step 1 lists for C (8; A-4)",
        "run 10 is not the workflow_dispatch run step 1 lists for C (12; A-4)",
    ]
    attempt = [_ci(12, "workflow_dispatch", attempt=1)]
    assert rem.ci_selection_problems(attempt, C, LISTED) == [
        "run 12: attempt 1, not the latest listed, 2 (A-4)"
    ]
    assert rem.ci_selection_problems([_ci(3, "schedule")], C, None) == [
        "runs [3]: event 'schedule' is neither push nor workflow_dispatch"
    ]


def test_a4_step_1_s_listing(tmp_path: Path) -> None:
    assert rem.listed_runs(tmp_path, C) is None
    record = tmp_path / rem.STEP_RECORD[1]
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"checks": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="no `runs_at_c`"):
        rem.listed_runs(tmp_path, C)
    record.write_text(json.dumps({"runs_at_c": [{"databaseId": 8, "event": "push"}]}), "utf-8")
    assert rem.listed_runs(tmp_path, C) == [{"databaseId": 8, "event": "push", "headSha": C}]


def test_a4_the_generator_refuses_before_it_runs_anything(tmp_path: Path) -> None:
    dispatch = CI / "ci-run-41108983463.json"
    argv = ["--line", "0.3", "--commit", S13.name, f"--ci-json={dispatch}", f"--ci-json={dispatch}"]
    argv += [
        "--evidence=evidence/S13",
        f"--out={tmp_path / 'm.json'}",
        f"--rel-a20={S13 / 'manifest.json'}",
    ]
    with pytest.raises(SystemExit, match="2 workflow_dispatch runs given"):
        rem.main(argv)
    assert not (tmp_path / "m.json").exists()
