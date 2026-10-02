"""T08.A50 (W4.5): `scripts/v0_1_gate.py` decides whether a v0.1 tag may be proposed.

ADR 0021's acceptance evidence: "exits 0 only when D2's four conditions hold, exits non-zero on any
`BLOCKED`, prints every FAIL as FAIL, and refuses a tag candidate whose code trees or lock differ
from `C`'s; tested with a ledger containing a listed FAIL, an unlisted FAIL, a `BLOCKED`, and a
tree difference." Amendment R3 §R3.3 adds the verdict table's form, read by column, each departure
an error; R3 4 the corrected tree list (ADR 0021 proposed revision 2). Finding G3
(`docs/reviews/T08-verdicts.md`): D2 presupposes D1, so the script reads the RC record and proposes
nothing unless it exists for `C` and every §8.2 step it lists passed (§8.1 item 4). Its residuals
at `67c66d9`: with `--rc`, §8.1 item 5's `tested` manifest is required (G3 (b)), and a Result
cell such as "PASS: Failed to upload" fails (G3 (a)). The ledger, verdict document, ADR text, RC
record and manifest are constructed here; the tree check runs on a scratch git
repository; the real ADR 0021 is read once for its accepted clauses, the real RC record (`C` =
`814e151`, F2) once for its failed step.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402

GATES = v0_1_gate.GATES
#: The RC record at `814e151` (commit `660d815`), frozen; `docs/t08-rc-record.md` moves on.
RC_RECORD_814E151 = REPO_ROOT / "tests" / "fixtures" / "t08" / "rc-record-814e151.md"
ADR = """
| Clause | Evidence | Frank's acceptance | Owner after v0.1 |
| --- | --- | --- | --- |
| V14 (b) one PTC family qualified | verdict | 2026-09-29, "carry as FAIL" | v0.2 |
| V13 (e) warm starts | — | pending | M03 |
"""
ENVELOPE = {"limitations": [{"id": "L01"}, {"id": "L22"}, {"id": "L-WS-1"}]}


def ledger(verdicts: dict[str, str | None]) -> dict[str, Any]:
    return {
        "gates": [
            {"id": gate, "required_evidence": f"req {gate}", "verdict": verdicts.get(gate)}
            for gate in ("G00", *GATES)
        ]
    }


HEADER = "| Gate | Verdict | Failing clauses | Travelling limitations | Basis |"


def document(rows: dict[str, tuple[str, str, str]], *, header: str = HEADER) -> str:
    """A T08.A03 table (Amendment R3 §R3.3); each row is `(verdict, failing, travelling)`, its
    basis `§Vnn; evidence at C`. The rows are written in the mapping's order."""
    lines = [header, "| --- | --- | --- | --- | --- |"]
    for gate, (word, failing, travelling) in rows.items():
        lines.append(f"| {gate} | {word} | {failing} | {travelling} | §{gate}; evidence at C |")
    return "\n".join(lines) + "\n"


RC = "c" * 40
RC_HEADER = "| Step | Assertion | Where | Result (as the record says) | Record | sha256 |"


def rc_record(results: dict[int, list[str]] | None = None, *, commit: str = RC) -> str:
    """An RC record for `commit` with one row per result (by default every step 1–10 `PASS`),
    a supporting row (`—`) for step 5, and step 11's pre-verdict gate run (exit 1)."""
    results = results or {step: ["PASS (1/1)"] for step in range(1, 11)}
    lines = [
        "# T08 — the release-candidate record at `C`",
        "",
        f"- **`C` = `{commit}`** (the candidate).",
        "",
        RC_HEADER,
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step, outcomes in results.items():
        lines += [
            f"| {step} | T08.A{40 + step} | CI | {result} | `r{step}.json` | `ab` |"
            for result in outcomes
        ]
    lines.append("| 5 | (run file) | CI | — | `r5.txt` | `cd` |")
    lines.append('| 11 | T08.A50 | local | exit 1: "NO (21 reasons)" | `gate.log` | `ef` |')
    return "\n".join(lines) + "\n"


#: §8.1 item 5's manifest for `RC`, as the gate script reads it.
TESTED = {"work_package": "T08", "commit": RC, "status": "tested"}


def report(
    verdicts: dict[str, tuple[str, str, str]],
    *,
    ledger_override: dict[str, str | None] | None = None,
    differences: list[str] | None = None,
    adr: str = ADR,
    record: str | None = None,
    manifest: dict[str, Any] | None = TESTED,
) -> dict[str, Any]:
    words = {gate: word for gate, (word, _, _) in verdicts.items()}
    return v0_1_gate.build(
        ledger=ledger({**words, **(ledger_override or {})}),
        verdict_text=document(verdicts),
        adr_text=adr,
        envelope=ENVELOPE,
        rc=RC,
        candidate="d" * 40,
        differences=[] if differences is None else differences,
        rc_record=rc_record() if record is None else record,
        rc_manifest=manifest,
    )


ALL_PASS = {gate: ("PASS", "—", "L01") for gate in GATES}


def test_all_pass_with_equal_trees_may_be_proposed() -> None:
    result = report(ALL_PASS)
    assert result["tag_may_be_proposed"], result["reasons"]
    assert result["gates"][0]["limitations"] == ["L01"]


def test_a_listed_fail_may_be_proposed_and_is_printed_fail() -> None:
    result = report({**ALL_PASS, "V14": ("FAIL", "V14 (b)", "L22, L-WS-1")})
    assert result["tag_may_be_proposed"], result["reasons"]
    (v14,) = [entry for entry in result["gates"] if entry["gate"] == "V14"]
    assert v14["failing_clauses"] == ["V14 (b)"] and v14["limitations"] == ["L22", "L-WS-1"]
    (row,) = [line for line in v0_1_gate.markdown(result).splitlines() if line.startswith("| V14")]
    assert "| FAIL |" in row and "PASS" not in row
    assert "V14 (b) FAIL, accepted by Frank 2026-09-29" in row
    (line,) = [line for line in v0_1_gate.text(result).splitlines() if line.startswith("V14")]
    assert "FAIL" in line and "PASS" not in line


def test_an_unlisted_fail_blocks() -> None:
    result = report({**ALL_PASS, "V13": ("FAIL", "V13 (e)", "—")})
    assert not result["tag_may_be_proposed"]
    assert any("V13 (e)" in reason and "D2.3" in reason for reason in result["reasons"])


def test_blocked_blocks_and_names_its_missing_inputs() -> None:
    blocked = "V19 (i): Frank's F3; V19 (v): the rights statement"
    result = report({**ALL_PASS, "V19": ("BLOCKED", blocked, "—")})
    assert not result["tag_may_be_proposed"]
    assert any("BLOCKED" in reason for reason in result["reasons"])
    (v19,) = [entry for entry in result["gates"] if entry["gate"] == "V19"]
    assert v19["failing_clauses"] == []
    assert v19["blocked_clauses"] == ["V19 (i): Frank's F3", "V19 (v): the rights statement"]


def test_a_missing_verdict_or_a_disagreeing_ledger_blocks() -> None:
    assert not report(ALL_PASS, ledger_override={"V12": None})["tag_may_be_proposed"]
    assert not report(ALL_PASS, ledger_override={"V12": "FAIL"})["tag_may_be_proposed"]


def test_an_unknown_limitation_id_blocks() -> None:
    assert not report({**ALL_PASS, "V11": ("PASS", "—", "L99")})["tag_may_be_proposed"]


def test_a_tree_difference_or_no_rc_blocks() -> None:
    assert not report(ALL_PASS, differences=["src/x.py"])["tag_may_be_proposed"]
    words = {gate: word for gate, (word, _, _) in ALL_PASS.items()}
    no_rc = v0_1_gate.build(
        ledger=ledger(words),
        verdict_text=document(ALL_PASS),
        adr_text=ADR,
        envelope=ENVELOPE,
        rc=None,
        candidate="d" * 40,
        differences=None,
        rc_record=rc_record(),
    )
    assert not no_rc["tag_may_be_proposed"]


# -- G3: §8.1 item 4, read from the RC record --------------------------------------------------


def _record_reasons(record: str | None) -> list[str]:
    words = {gate: word for gate, (word, _, _) in ALL_PASS.items()}
    result = v0_1_gate.build(
        ledger=ledger(words),
        verdict_text=document(ALL_PASS),
        adr_text=ADR,
        envelope=ENVELOPE,
        rc=RC,
        candidate="d" * 40,
        differences=[],
        rc_record=record,
        rc_manifest=TESTED,
    )
    assert result["tag_may_be_proposed"] is (not result["reasons"])
    assert result["rc_record_problems"] == result["reasons"]
    return list(result["reasons"])


PASSING = {step: ["PASS (1/1)"] for step in range(1, 11)}


def test_g3_a_passing_record_for_c_allows_a_proposal() -> None:
    assert _record_reasons(rc_record()) == []
    lines = v0_1_gate.text(report(ALL_PASS)).splitlines()
    assert "RC record (§8.1 item 4): steps 1–10 passed at C" in lines


def test_g3_a_missing_record_blocks() -> None:
    (reason,) = _record_reasons(None)
    assert "no RC record" in reason and "§8.1 item 4" in reason


def test_g3_a_record_of_another_commit_blocks() -> None:
    (reason,) = _record_reasons(rc_record(commit="e" * 40))
    assert "e" * 40 in reason and RC in reason


@pytest.mark.parametrize(
    "result", ["**FAIL** (3/4): `a45.every_bundle_matches` fail", "failure", "not measured"]
)
def test_g3_a_failed_step_blocks(result: str) -> None:
    (reason,) = _record_reasons(rc_record({**PASSING, 5: ["PASS (4/4)", result]}))
    assert reason.startswith("§8.2 step 5 ") and "failed" in reason


def test_g3_a_result_not_stated_as_passed_blocks() -> None:
    (reason,) = _record_reasons(rc_record({**PASSING, 2: ["PASS (3/3)", "equal across 2"]}))
    assert reason.startswith("§8.2 step 2 ") and "not stated as passed" in reason


def test_g3_a_step_missing_or_only_supporting_blocks() -> None:
    missing = {step: rows for step, rows in PASSING.items() if step != 9}
    (reason,) = _record_reasons(rc_record(missing))
    assert reason.startswith("§8.2 step 9:")
    (reason,) = _record_reasons(rc_record({**PASSING, 6: ["—"]}))
    assert reason.startswith("§8.2 step 6:")


def test_g3_prose_words_are_not_status_words() -> None:
    """`none failed` and a check's lower-case `pass` are prose; `success` is CI's word."""
    rows = {**PASSING, 1: ["success / success"], 7: ["PASS (12/12; none failed/missing)"]}
    assert _record_reasons(rc_record(rows)) == []


def test_g3_the_real_record_at_814e151_blocks_on_f2() -> None:
    text = RC_RECORD_814E151.read_text(encoding="utf-8")
    (commit,) = set(v0_1_gate.RC_COMMIT.findall(text))
    assert commit.startswith("814e151")
    problems = v0_1_gate.rc_record_problems(text, commit)
    assert "§8.2 step 5 (T08.A45 (replay), CI aarch64): failed" in "\n".join(problems)


# -- T08 review 3, Ruling 3: a Result cell is read by its status head ---------------------------

#: CI's conclusions and the record's words Ruling 3 added to the vocabulary: each fails a row,
#: also beside a `success` (a two-runner `success / <conclusion>`).
NEW_STATUS_WORDS = (
    "cancelled",
    "skipped",
    "timed_out",
    "startup_failure",
    "action_required",
    "neutral",
    "stale",
    "FAILED",
)


@pytest.mark.parametrize("word", NEW_STATUS_WORDS)
def test_r3_every_status_word_but_pass_and_success_fails_a_row(word: str) -> None:
    assert v0_1_gate._rc_outcome(f"success / {word} (job 2)") == "failed"
    (reason,) = _record_reasons(rc_record({**PASSING, 1: ["PASS (1/1)", f"success / {word}"]}))
    assert reason.startswith("§8.2 step 1 ") and "failed" in reason


@pytest.mark.parametrize("cell", ["Not measured (job success; …)", "NOT MEASURED", "not measured"])
def test_r3_not_measured_fails_in_any_letter_case(cell: str) -> None:
    assert v0_1_gate._rc_outcome(cell) == "failed"


def test_r3_a_count_must_be_complete() -> None:
    """Where the head is followed by `(k/n`, k = n, else the row is not stated as passed."""
    assert v0_1_gate._rc_outcome("PASS (4/4)") == "passed"
    assert v0_1_gate._rc_outcome("PASS (12/12: A47; none failed/missing/skipped)") == "passed"
    assert v0_1_gate._rc_outcome("PASS (3/4)") == "unstated"
    assert v0_1_gate._rc_outcome("PASS (3/4; aarch64 not run)") == "unstated"
    (reason,) = _record_reasons(rc_record({**PASSING, 3: ["PASS (1/1)", "PASS (3/4)"]}))
    assert reason.startswith("§8.2 step 3 ") and "not stated as passed" in reason


#: Review 3's S1 probes, every one of which the rule before Ruling 3 read as passed, and what
#: the rule reads now. `PASS: Failed to upload` passed under Ruling 3's rule (its head is `PASS`
#: and the cell held none of its failure words); since the verdicts at `67c66d9` (finding G3 (a))
#: `Failed` as a word is one, so it fails.
S1_PROBES = {
    "success / cancelled (job 2)": "failed",
    "success / startup_failure": "failed",
    "success / skipped": "failed",
    "Not measured (job success; …)": "failed",
    "PASS (3/4): FAILS on aarch64": "failed",
    "PASS: Failed to upload": "failed",
}


@pytest.mark.parametrize(("cell", "outcome"), S1_PROBES.items())
def test_r3_review_3_s1_probes(cell: str, outcome: str) -> None:
    assert v0_1_gate._rc_outcome(cell) == outcome


#: The forms Ruling 3 names, from the `814e151` record and the future A45 row, as it reads them.
RULING_3_FORMS = {
    "success / success (6711 p, 11 s; 6714 p, 8 s)": "passed",
    "PASS (4/4; lock sha256 empty; replay `inspected_archived_results` / `NOT_RUN`)": "passed",
    "PASS (12/12: A47 T06.A02–A08; 165 nodes passed, none failed/missing/skipped)": "passed",
    '"A30 PASS" (exit 0): 381 objects': "passed",
    "PASS: 72 certificates audited, 0 violations": "passed",
    "PASS (6/6): controls C1 MISMATCH, C2 MISMATCH, C3 MATCH": "passed",
    "**FAIL** (3/4): `a45.every_bundle_matches` fail": "failed",
    "—": "none",
    "pass": "unstated",
}


@pytest.mark.parametrize(("cell", "outcome"), RULING_3_FORMS.items())
def test_r3_the_forms_the_ruling_names(cell: str, outcome: str) -> None:
    assert v0_1_gate._rc_outcome(cell) == outcome


#: G3 (a): a Result cell whose status word is PASS or success but which holds `Failed`, `FAILED` or
#: `failure` as a word fails; the stem of a longer word and lower-case prose do not.
G3A_FORMS = {
    "PASS: Failed to upload": "failed",
    "success (artifact upload Failed)": "failed",
    "PASS (2/2): FAILED none": "failed",
    "success: upload failure": "failed",
    "PASS (12/12; none failed/missing)": "passed",
    "PASS: A33 failures 0": "passed",
    "PASS: Failedover 0": "passed",
}


@pytest.mark.parametrize(("cell", "outcome"), G3A_FORMS.items())
def test_g3a_a_failure_word_beside_pass_fails_the_row(cell: str, outcome: str) -> None:
    assert v0_1_gate._rc_outcome(cell) == outcome


# -- G3 (b): §8.1 item 5, the `tested` manifest at `C` ------------------------------------------


def _manifest_reasons(manifest: dict[str, Any] | None) -> list[str]:
    result = report(ALL_PASS, manifest=manifest)
    assert result["tag_may_be_proposed"] is (not result["reasons"])
    assert result["rc_manifest_problems"] == result["reasons"]
    return list(result["reasons"])


def test_g3b_a_tested_or_reviewed_manifest_of_c_allows_a_proposal() -> None:
    assert _manifest_reasons(TESTED) == []
    assert _manifest_reasons({**TESTED, "status": "reviewed"}) == []
    lines = v0_1_gate.text(report(ALL_PASS)).splitlines()
    assert "T08 manifest (§8.1 item 5): `tested` at C" in lines


def test_g3b_no_manifest_blocks() -> None:
    (reason,) = _manifest_reasons(None)
    assert "no T08 manifest" in reason and RC in reason and "§8.1 item 5" in reason
    text = v0_1_gate.text(report(ALL_PASS, manifest=None))
    assert "T08 manifest (§8.1 item 5): 1 problems" in text
    assert text.rstrip().endswith("v0.1.0 tag may be proposed: NO (1 reasons)")


@pytest.mark.parametrize("status", ["implemented", "planned", "BLOCKED", None])
def test_g3b_a_manifest_not_tested_blocks(status: str | None) -> None:
    (reason,) = _manifest_reasons({**TESTED, "status": status})
    assert f"status {status!r}" in reason


@pytest.mark.parametrize(
    "override", [{"commit": "e" * 40}, {"work_package": "T07"}], ids=["commit", "package"]
)
def test_g3b_a_manifest_of_another_commit_or_package_blocks(override: dict[str, str]) -> None:
    (reason,) = _manifest_reasons({**TESTED, **override})
    assert "not of T08 at " + RC in reason


def test_g3b_main_reads_the_manifest_of_c(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--rc C` with every gate passing and the RC record in place: NO without the manifest,
    YES once `evidence/T08/<C>/manifest.json` is `tested`."""
    words = {gate: word for gate, (word, _, _) in ALL_PASS.items()}
    files = {
        v0_1_gate.LEDGER: yaml.safe_dump(ledger(words)),
        v0_1_gate.VERDICT_DOCUMENT: document(ALL_PASS),
        v0_1_gate.ADR_0021: ADR,
        v0_1_gate.ENVELOPE: yaml.safe_dump(ENVELOPE),
        v0_1_gate.RC_RECORD: rc_record(),
    }
    for name, content in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(content, encoding="utf-8")
    monkeypatch.setattr(v0_1_gate, "ROOT", tmp_path)
    monkeypatch.setattr(v0_1_gate, "git", lambda *a: RC.encode() + b"\n")
    monkeypatch.setattr(sys, "argv", ["v0_1_gate.py", "--rc", RC])
    monkeypatch.setattr(v0_1_gate, "tree_differences", lambda rc, candidate: [])
    assert v0_1_gate.main() == 1
    assert "no T08 manifest" in capsys.readouterr().out
    manifest = tmp_path / v0_1_gate.EVIDENCE / RC / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(TESTED), encoding="utf-8")
    assert v0_1_gate.main() == 0
    assert capsys.readouterr().out.rstrip().endswith("v0.1.0 tag may be proposed: YES")


def test_r3_the_814e151_record_reads_as_the_ruling_states() -> None:
    """Every row that passed still passes; the three unstated rows of steps 2, 5 and 10 stay
    unstated (with step 11's, which is not required); `**FAIL** (3/4)` fails."""
    text = RC_RECORD_814E151.read_text(encoding="utf-8")
    ((header, rows),) = [
        (header, rows)
        for header, rows in v0_1_gate._tables(text)
        if [v0_1_gate._bare(cell) for cell in header[:2]] == ["Step", "Assertion"]
    ]
    column = [v0_1_gate._bare(cell).startswith("Result") for cell in header].index(True)
    outcomes: dict[str, list[str]] = {}
    for cells in rows:
        outcomes.setdefault(v0_1_gate._rc_outcome(cells[column]), []).append(cells[0])
    assert outcomes["failed"] == ["5"]
    assert outcomes["unstated"] == ["2", "5", "10", "11"]
    assert outcomes["none"] == ["6", "6"]
    assert len(outcomes["passed"]) == 29
    assert set(outcomes) == {"passed", "failed", "unstated", "none"}
    (commit,) = set(v0_1_gate.RC_COMMIT.findall(text))
    problems = v0_1_gate.rc_record_problems(text, commit)
    assert [problem.split(" in ")[0] for problem in problems] == [
        "§8.2 step 2 (T08.A42 (cross-arch), CI identity): not stated as passed",
        "§8.2 step 5 (T08.A45 (write), CI x86-64 bundle-set): not stated as passed",
        "§8.2 step 5 (T08.A45 (replay), CI aarch64): failed",
        "§8.2 step 10 (T08.A34, step 6 ensemble (both classes)): not stated as passed",
    ]


# -- §R3.3: the table's form; every departure is an error, never a guess -----------------------


def _without(gate: str) -> dict[str, tuple[str, str, str]]:
    return {g: row for g, row in ALL_PASS.items() if g != gate}


def _reordered() -> dict[str, tuple[str, str, str]]:
    rows = list(ALL_PASS.items())
    rows[0], rows[1] = rows[1], rows[0]
    return dict(rows)


MALFORMED = {
    "a FAIL naming no clause": document({**ALL_PASS, "V14": ("FAIL", "—", "—")}),
    "a PASS with a failing-clause entry": document({**ALL_PASS, "V11": ("PASS", "V11 (a)", "—")}),
    "a clause of another gate": document({**ALL_PASS, "V14": ("FAIL", "V13 (e)", "—")}),
    "a clause not in Vnn (x) form": document({**ALL_PASS, "V14": ("FAIL", "V14 b", "—")}),
    "a BLOCKED without its missing input": document(
        {**ALL_PASS, "V19": ("BLOCKED", "V19 (i)", "—")}
    ),
    "an envelope id among the clauses": document(
        {**ALL_PASS, "V19": ("BLOCKED", "V19 (i): see L41", "—")}
    ),
    "a clause id among the limitations": document({**ALL_PASS, "V11": ("PASS", "—", "V11 (a)")}),
    "a U-id among the limitations": document({**ALL_PASS, "V11": ("PASS", "—", "U05")}),
    "a verdict word that is not the ledger's": document({**ALL_PASS, "V11": ("MET", "—", "—")}),
    "a bold verdict word": document({**ALL_PASS, "V11": ("**PASS**", "—", "—")}),
    "a missing gate row": document(_without("V16")),
    "a gate out of order": document(_reordered()),
    "a bold gate id": document(ALL_PASS).replace("| V12 |", "| **V12** |"),
    "a missing column": document(
        ALL_PASS, header=HEADER.replace(" Travelling limitations |", "")
    ).replace("| — | L01 |", "| — |"),
    "a reordered column": document(
        ALL_PASS, header="| Gate | Verdict | Travelling limitations | Failing clauses | Basis |"
    ),
    "a renamed column": document(ALL_PASS, header=HEADER.replace("Failing clauses", "Clauses")),
    "a clause id in Basis": document(ALL_PASS).replace("§V14; evidence", "§V14; V14 (b) met"),
    "an envelope id in Basis": document(ALL_PASS).replace("§V11; evidence", "§V11; L07 n/a"),
    "a second verdict table": document(ALL_PASS) + "\n" + document(ALL_PASS),
    "another table with a bare gate id first": document(ALL_PASS)
    + "\n## V11\n\n| Clause | Judged |\n| --- | --- |\n| V11 | met |\n",
    "no verdict table": "| Clause | Judged |\n| --- | --- |\n| V11 (a) | met |\n",
}


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_a_departure_from_the_r3_3_form_is_an_error(case: str) -> None:
    with pytest.raises(ValueError):
        v0_1_gate.verdict_rows(MALFORMED[case])


def test_sections_below_the_table_may_hold_tables_without_gate_rows() -> None:
    text = document(ALL_PASS) + (
        "\n## V11\n\n| Clause | Judged | Evidence |\n| --- | --- | --- |\n"
        "| V11 (a) | met | L01 travels |\n| **V11** | — | bold is not a gate row |\n"
    )
    assert set(v0_1_gate.verdict_rows(text)) == set(GATES)


def test_a_malformed_document_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "docs" / "reviews").mkdir(parents=True)
    (tmp_path / "docs" / "reviews" / "T08-verdicts.md").write_text(MALFORMED["a bold gate id"])
    for name in (v0_1_gate.LEDGER, v0_1_gate.ADR_0021, v0_1_gate.ENVELOPE):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes((REPO_ROOT / name).read_bytes())
    monkeypatch.setattr(v0_1_gate, "ROOT", tmp_path)
    monkeypatch.setattr(v0_1_gate, "git", lambda *a: b"e" * 40 + b"\n")
    monkeypatch.setattr(sys, "argv", ["v0_1_gate.py", "--rc", "e" * 40])
    monkeypatch.setattr(v0_1_gate, "tree_differences", lambda rc, candidate: [])
    assert v0_1_gate.main() == 2


def test_the_real_adr_accepts_exactly_v14_b() -> None:
    text = (REPO_ROOT / "docs" / "adr" / "0021-v0.1-release-policy.md").read_text(encoding="utf-8")
    assert set(v0_1_gate.accepted_clauses(text)) == {"V14 (b)"}


# -- the tree check, on a scratch repository ---------------------------------------------------


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, content in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message],
        cwd=repo,
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_the_tree_check_allows_the_version_string_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    base = {
        "pyproject.toml": '[project]\nname = "p"\nversion = "0.1.0rc1"\ndependencies = ["a==1"]\n',
        "src/openflowsheet/__init__.py": '__version__ = "0.1.0rc1"\n',
        "src/openflowsheet/x.py": "X = 1\n",
        "schemas/a.schema.json": "{}\n",
        "benchmarks/b.yaml": "b: 1\n",
        "requirements.lock": "a==1\n",
        "MANIFEST.in": "graft src\n",
        "README.md": "readme\n",
        "LICENSE": "licence\n",
        "NOTICE": "notice\n",
        "CHANGELOG.md": "draft\n",
        "tests/fixtures/summary.json": '{"package_version": "0.1.0rc1"}\n',
    }
    rc = _commit(tmp_path, base, "rc")
    bumped = _commit(
        tmp_path,
        {
            "pyproject.toml": base["pyproject.toml"].replace("0.1.0rc1", "0.1.0"),
            "src/openflowsheet/__init__.py": '__version__ = "0.1.0"\n',
            "CHANGELOG.md": "final\n",
            "tests/fixtures/summary.json": '{"package_version": "0.1.0"}\n',
        },
        "bump",
    )
    pinned = _commit(
        tmp_path,
        {
            "pyproject.toml": base["pyproject.toml"]
            .replace("a==1", "a==2")
            .replace("0.1.0rc1", "0.1.0")
        },
        "pin",
    )
    edited = _commit(tmp_path, {"src/openflowsheet/x.py": "X = 2\n"}, "edit")
    noticed = _commit(tmp_path, {"README.md": "readme, edited\n", "NOTICE": "notice 2\n"}, "doc")
    monkeypatch.setattr(v0_1_gate, "ROOT", tmp_path)
    assert v0_1_gate.tree_differences(rc, rc) == []
    assert v0_1_gate.tree_differences(rc, bumped) == []
    assert v0_1_gate.tree_differences(rc, pinned) == ["pyproject.toml"]
    assert v0_1_gate.tree_differences(rc, edited) == ["pyproject.toml", "src/openflowsheet/x.py"]
    assert v0_1_gate.tree_differences(bumped, noticed) == [
        "NOTICE",
        "README.md",
        "pyproject.toml",
        "src/openflowsheet/x.py",
    ]


def test_the_tree_list_is_adr_0021_d2_4_revision_2() -> None:
    assert v0_1_gate.TREES == (
        "src",
        "schemas",
        "benchmarks",
        "requirements.lock",
        "pyproject.toml",
        "MANIFEST.in",
        "README.md",
        "LICENSE",
        "NOTICE",
    )
