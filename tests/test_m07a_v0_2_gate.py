"""M07a.A01–A14: `scripts/v0_2_gate.py` decides whether a 0.2 pre-release tag may be proposed.

V02 alpha release spec §7 and §10; ADR 0028. The gate set `v0.2-alpha-gate-v1` covers exactly the
versions of Table T1's `yes` rows, claims V11–V20, W21 and W22, reads every input at the candidate
commit, reads ADR 0028's two tables (never ADR 0021's) and fails closed on every item of §7.3. Each
refusal of §7.2–§7.3 has its own state here, on an otherwise passing fixture, so a dropped rule
fails its own test.

The inputs are of two kinds, and each says which it is:

- **real records**: ADR 0028, ADR 0021 and ADR 0022 as committed, today's support envelope, the
  committed record of the v0.1 candidate `67c66d9` (R-151), the spec's truth tables T1, T4, T5,
  T6, T7 and T8 as `benchmarks/m07a/reference_values.yaml` registers them (M07a.A00 re-derives
  them), and the v0.1 gate's file hashes there (M07a.A13);
- **constructed test inputs**: minimal ledgers, verdict documents, ADR tables, RC records,
  manifests and envelopes, each carrying the marker `MARK` so that none can be mistaken for a
  record. The end-to-end tests run `main` on a scratch git repository built the same way.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402

REFERENCE = yaml.safe_load(
    (REPO_ROOT / "benchmarks" / "m07a" / "reference_values.yaml").read_text(encoding="utf-8")
)
TRUTH = REFERENCE["truth_tables"]
TARGETS = REFERENCE["targets"]
ALPHA = v0_2_gate.GATE_SETS[0]
CLAIMED = ALPHA.claimed
UNCLAIMED = ALPHA.not_claimed
SET = "v0.2-alpha-gate-v1"

#: Every constructed input carries this, in its own format's comment syntax.
MARK = "TEST INPUT constructed by tests/test_m07a_v0_2_gate.py; not a record"

RC = "c" * 40
CANDIDATE = "d" * 40
M01_AT = "a" * 40
M02_AT = "b" * 40
JUDGED = "2026-10-12"
VERSION = "0.2.0a1"
ADR_0028 = "docs/adr/0028-v0.2-pre-release-policy.md"
VERDICTS = "docs/reviews/V02-alpha-verdicts.md"
RC_RECORD = "docs/v02-alpha-rc-record.md"
ENVELOPE = "benchmarks/t08/support_envelope.yaml"
LEDGER = "docs/requirements.yaml"


def ledger(verdicts: dict[str, str | None]) -> str:
    gates = [
        {"id": gate, "required_evidence": f"req {gate}", "verdict": verdicts.get(gate)}
        for gate in ("G00", *CLAIMED, *UNCLAIMED)
    ]
    return f"# {MARK}\n" + yaml.safe_dump({"gates": gates}, sort_keys=False)


HEADER = "| Gate | Verdict | Failing clauses | Travelling limitations | Basis |"


def document(
    rows: dict[str, tuple[str, str, str]],
    *,
    header: str = HEADER,
    rc: str = RC,
    judged: str | None = JUDGED,
    basis: Callable[[str], str] = lambda gate: f"§{gate}; evidence at C",
    after: str = "",
    rejudged: str | None = None,
) -> str:
    """A verdict document in §6.3's form; each row is `(verdict, failing, travelling)`, written
    in the mapping's order. `rejudged` is a `**Re-judged:**` line, placed directly below the
    header (§19.2 item 2)."""
    judged_part = f"   **Judged:** {judged}" if judged else ""
    lines = [
        "# V02 alpha — verdicts",
        "",
        f"<!-- {MARK} -->",
        "",
        f"**Release candidate:** `{rc}`{judged_part}   **By:** design lane (`verdict`)",
        *([rejudged] if rejudged is not None else []),
        "",
        header,
        "| --- | --- | --- | --- | --- |",
    ]
    for gate, (word, failing, travelling) in rows.items():
        lines.append(f"| {gate} | {word} | {failing} | {travelling} | {basis(gate)} |")
    return "\n".join(lines) + "\n" + after


ALL_PASS = {gate: ("PASS", "—", "L01") for gate in CLAIMED}
ACCEPTED = f"accepted, {JUDGED}"


def adr_0028(
    *,
    d3: str = "pending",
    answers: dict[str, str | None] | None = None,
    extra: str = "",
    clause: str = "V14 (b)",
) -> str:
    """ADR 0028's two tables, as the gate reads them; an answer `None` leaves out its row."""
    answers = {item: ACCEPTED for item in ALPHA.frank_items} | (answers or {})
    lines = [
        "# ADR 0028 (test input)",
        "",
        f"<!-- {MARK} -->",
        "",
        "**Status:** **Accepted**, 2026-10-12",
        "",
        "## Frank's answers for 0.2.0a1",
        "",
        "| Item | Question | Default | Frank's answer |",
        "| --- | --- | --- | --- |",
        *(
            f"| {item} | q | d | {answer} |"
            for item, answer in answers.items()
            if answer is not None
        ),
        "",
        "## D3 for 0.2.0a1",
        "",
        "| Clause | Evidence | Frank's acceptance | Owner after 0.2.0a1 |",
        "| --- | --- | --- | --- |",
        f"| {clause} | the alpha verdict | {d3} | later |",
        "",
    ]
    return "\n".join(lines) + extra


def envelope(*, envelope_id: str = "v0.2-alpha-envelope-1", release: str = VERSION) -> str:
    return f"# {MARK}\n" + yaml.safe_dump(
        {
            "envelope_id": envelope_id,
            "release": release,
            "limitations": [{"id": "L01"}, {"id": "L42"}, {"id": "L-WEB-1"}],
        },
        sort_keys=False,
    )


RC_HEADER = "| Step | Assertion | Where | Result (as the record says) | Record | sha256 |"


def rc_record(results: dict[int, list[str]] | None = None, *, commit: str = RC) -> str:
    """An RC record for `commit`: one row per result (by default every step 1–12 `PASS`), a
    supporting row (`—`) for step 5, and step 13's pre-verdict gate run (exit 1)."""
    results = {step: ["PASS (1/1)"] for step in range(1, 13)} if results is None else results
    lines = [
        "# V02 alpha — the release-candidate record at `C`",
        "",
        f"<!-- {MARK} -->",
        "",
        f"- **`C` = `{commit}`** (the candidate).",
        "",
        RC_HEADER,
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step, outcomes in results.items():
        lines += [
            f"| {step} | M07a.A{29 + step} | CI | {result} | `r{step}.json` | `ab` |"
            for result in outcomes
        ]
    lines.append("| 5 | (run file) | CI | — | `r5.txt` | `cd` |")
    lines.append('| 13 | M07a.A12 | local | exit 1: "NO (3 reasons)" | `gate.log` | `ef` |')
    return "\n".join(lines) + "\n"


def manifest(package: str, commit: str, status: str = "tested") -> str:
    return json.dumps(
        {"_comment": MARK, "work_package": package, "commit": commit, "status": status}
    )


def adr(status: str = "**Status:** **Accepted**, 2026-10-08") -> str:
    return f"# ADR (test input)\n\n<!-- {MARK} -->\n\n{status}\n\n**Date:** 2026-10-08\n"


def files(**overrides: str | None) -> dict[str, str]:
    """An otherwise passing candidate: path → text. A keyword names a path by its key in
    `PATHS`; `None` removes the file."""
    found: dict[str, str] = {
        LEDGER: ledger({gate: "PASS" for gate in CLAIMED}),
        VERDICTS: document(ALL_PASS),
        ADR_0028: adr_0028(),
        ENVELOPE: envelope(),
        RC_RECORD: rc_record(),
        f"evidence/M07a/{RC}/manifest.json": manifest("M07a", RC),
        f"evidence/M01/{M01_AT}/manifest.json": manifest("M01", M01_AT),
        f"evidence/M02/{M02_AT}/manifest.json": manifest("M02", M02_AT),
        **{
            f"docs/adr/{number}-test-input.md": adr()
            for number in ALPHA.required_adrs
            if number != "0028"
        },
    }
    for key, value in overrides.items():
        path = PATHS.get(key, key)
        if value is None:
            found.pop(path, None)
        else:
            found[path] = value
    return found


PATHS = {
    "ledger": LEDGER,
    "verdicts": VERDICTS,
    "adr_0028": ADR_0028,
    "envelope": ENVELOPE,
    "rc_record": RC_RECORD,
    "m07a": f"evidence/M07a/{RC}/manifest.json",
    "m01": f"evidence/M01/{M01_AT}/manifest.json",
    "m02": f"evidence/M02/{M02_AT}/manifest.json",
    "adr_0022": "docs/adr/0022-test-input.md",
    "adr_0035": "docs/adr/0035-test-input.md",
}
ANCESTORS = frozenset({M01_AT, M02_AT, RC})


def report(
    candidate_files: dict[str, str] | None = None,
    *,
    version: str = VERSION,
    rc_version: str | None = None,
    rc_in_repository: bool = True,
    differences: list[str] | None = None,
) -> dict[str, Any]:
    return v0_2_gate.build(
        files=files() if candidate_files is None else candidate_files,
        rc=RC,
        rc_version=version if rc_version is None else rc_version,
        rc_in_repository=rc_in_repository,
        candidate=CANDIDATE,
        version=version,
        differences=[] if differences is None else differences,
        is_ancestor=lambda commit: commit in ANCESTORS,
    )


def gate_rows(output: str) -> list[str]:
    return re.findall(r"^((?:V1[1-9]|V20|W2[1-7]))  ", output, flags=re.MULTILINE)


def test_the_otherwise_passing_fixture_may_be_proposed() -> None:
    result = report()
    assert result["tag_may_be_proposed"], result["reasons"]
    assert v0_2_gate.text(result).endswith(f"v{VERSION} tag may be proposed: YES\n")


def test_the_registry_is_the_specification_s() -> None:
    """§7.1 and the generator's targets: one gate set, its pattern, claims and inputs."""
    assert [entry.name for entry in v0_2_gate.GATE_SETS] == [TARGETS["gate_set"]] == [SET]
    assert ALPHA.covers.pattern == TARGETS["covers"]
    assert list(CLAIMED) == TARGETS["claimed"] and list(UNCLAIMED) == TARGETS["not_claimed"]
    assert ALPHA.envelope_id == TARGETS["envelope_id"]
    assert list(ALPHA.required_adrs) == TARGETS["required_adrs"]
    assert list(ALPHA.frank_items) == TARGETS["frank_items"]
    assert dict(ALPHA.rejudge_waits) == TARGETS["rejudge_depends"]
    assert v0_2_gate.REJUDGED_VALUE.pattern == TARGETS["rejudged_pattern"]
    assert v0_2_gate.ACCEPTANCE.pattern == TARGETS["frank_cell_pattern"]
    assert list(ALPHA.rc_steps) == TARGETS["rc_steps_required"]
    assert ALPHA.rc_last_step == max(int(step) for step in TARGETS["rc_steps"])
    assert ALPHA.verdict_document == TARGETS["paths"]["verdict_document"]
    assert ALPHA.rc_record == TARGETS["paths"]["rc_record"]
    assert ALPHA.policy_adr == TARGETS["paths"]["adr"]


# -- M07a.A01: version coverage (Table T1) ------------------------------------------------------


@pytest.mark.parametrize(("version", "covered"), TRUTH["T1_coverage"].items())
def test_a01_coverage_is_table_t1(version: str, covered: bool) -> None:
    result = report(files(envelope=envelope(release=version)), version=version)
    output = v0_2_gate.text(result)
    assert result["tag_may_be_proposed"] is covered, result["reasons"]
    if covered:
        assert len(gate_rows(output)) == 17
        assert output.endswith(f"v{version} tag may be proposed: YES\n")
    else:
        reason = f"version {version} is not covered by a registered v0.2 gate set"
        assert result["reasons"] == [reason] and result["gates"] == []
        assert output == f"{reason}\nv{version} tag may be proposed: NO (1 reasons)\n"


# -- M07a.A02: C's version against the candidate's ---------------------------------------------


C_V0_1 = "67c66d98587f23bd7dfe8da28a8facccc92da21e"


def test_a02_c_s_version_must_be_the_candidate_s() -> None:
    assert report(rc_version=VERSION)["tag_may_be_proposed"]  # (i)
    # (ii) the forgotten `rc` input: C is the v0.1 candidate, by its committed record (R-151).
    rc = v0_2_gate.resolve_rc(C_V0_1[:7])
    assert rc == C_V0_1
    recorded = str(v0_1_gate.tree_record_of(rc)["version"])
    assert recorded == "0.1.0rc1"
    forgotten = report(rc_version=recorded)
    assert forgotten["reasons"] == [
        "C's version 0.1.0rc1 is not the candidate's version 0.2.0a1 (ADR 0028 D4)"
    ]
    # (iii) D2.4's version allowance is not used by the alpha.
    bumped = report(files(envelope=envelope(release="0.2.0a2")), version="0.2.0a2")
    assert bumped["tag_may_be_proposed"]
    later = report(
        files(envelope=envelope(release="0.2.0a2")), version="0.2.0a2", rc_version=VERSION
    )
    assert later["reasons"] == [
        "C's version 0.2.0a1 is not the candidate's version 0.2.0a2 (ADR 0028 D4)"
    ]


# -- M07a.A03: the verdict document's form -----------------------------------------------------


def _swap(first: str, second: str) -> dict[str, tuple[str, str, str]]:
    order = list(ALL_PASS)
    i, j = order.index(first), order.index(second)
    order[i], order[j] = order[j], order[i]
    return {gate: ALL_PASS[gate] for gate in order}


MALFORMED = {
    "reordered column": document(
        ALL_PASS, header="| Gate | Verdict | Travelling limitations | Failing clauses | Basis |"
    ),
    "missing column": "\n".join(
        line.rsplit("|", 2)[0] + "|" if line.startswith("|") else line
        for line in document(ALL_PASS).splitlines()
    ),
    "gate out of order": document(_swap("V11", "V12")),
    "W21 after W22": document(_swap("W21", "W22")),
    "bold gate id": document(ALL_PASS).replace("| V13 |", "| **V13** |"),
    "a clause in Basis": document(ALL_PASS, basis=lambda gate: "see W21 (a)"),
    "an L id in Basis": document(ALL_PASS, basis=lambda gate: "travels with L42"),
    "a second Verdict table": document(
        ALL_PASS, after="\n| Item | Verdict |\n| --- | --- |\n| x | PASS |\n"
    ),
    "a W23 row": document({**ALL_PASS, "W23": ("PASS", "—", "—")}),
    "a W22 row missing": document({g: v for g, v in ALL_PASS.items() if g != "W22"}),
    "a header naming another C": document(ALL_PASS, rc="e" * 40),
    "no Judged date": document(ALL_PASS, judged=None),
    "Judged twice": document(ALL_PASS, after="\n**Judged:** 2026-10-13\n"),
    "a Judged date that is not a date": document(ALL_PASS, judged="2026-13-01"),
    "C named twice": document(ALL_PASS, after=f"\n**Release candidate:** `{RC}`\n"),
    "no C": document(ALL_PASS).replace("**Release candidate:**", "**Candidate:**"),
    "another gate's clause": document({**ALL_PASS, "W21": ("FAIL", "W22 (a)", "—")}),
    "a gate row in another table": document(
        ALL_PASS, after="\n| Gate | Note |\n| --- | --- |\n| W21 | x |\n"
    ),
}


def test_a03_the_passing_document_parses() -> None:
    read = v0_2_gate.verdict_document(document(ALL_PASS), ALPHA, RC)
    assert list(read.rows) == list(CLAIMED) and read.judged.isoformat() == JUDGED


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_a03_a_departure_from_the_form_is_an_error(case: str) -> None:
    with pytest.raises(ValueError):
        v0_2_gate.verdict_document(MALFORMED[case], ALPHA, RC)
    with pytest.raises(ValueError):
        report(files(verdicts=MALFORMED[case]))


def test_a03_an_unknown_limitation_id_is_a_gate_problem() -> None:
    result = report(files(verdicts=document({**ALL_PASS, "W22": ("PASS", "—", "L99")})))
    assert result["reasons"] == [f"W22: limitation ids not in {ENVELOPE}: ['L99']"]


def test_a03_no_verdict_document_is_a_reason() -> None:
    result = report(files(verdicts=None))
    assert result["reasons"][0] == f"{VERDICTS} does not exist at the candidate"
    assert not result["tag_may_be_proposed"]


# -- M07a.A04: D2.1–D2.3 with ADR 0028's D3 table ---------------------------------------------


V14_FAIL = {**ALL_PASS, "V14": ("FAIL", "V14 (b)", "L42")}


def _fail_report(d3: str, rows: dict[str, tuple[str, str, str]] = V14_FAIL) -> dict[str, Any]:
    words = {gate: word for gate, (word, _, _) in rows.items()}
    return report(files(ledger=ledger(words), verdicts=document(rows), adr_0028=adr_0028(d3=d3)))


def test_a04_a_all_pass() -> None:
    assert report()["tag_may_be_proposed"]


def test_a04_b_a_fail_accepted_on_the_judged_date_is_printed_fail() -> None:
    result = _fail_report(f"accepted, {JUDGED}")
    assert result["tag_may_be_proposed"], result["reasons"]
    output = v0_2_gate.text(result)
    assert re.search(r"^V14  FAIL", output, flags=re.MULTILINE)
    assert f"V14 (b) FAIL, accepted by Frank {JUDGED} (ADR 0028 D3)" in output
    assert "| V14 | FAIL |" in v0_2_gate.markdown(result)


def test_a04_c_an_acceptance_dated_before_the_verdict_is_refused() -> None:
    result = _fail_report("accepted, 2026-10-11")
    assert result["reasons"] == [
        "V14: V14 (b): accepted 2026-10-11, before the verdict's Judged date 2026-10-12 "
        "(D2.3; ADR 0028 D2)"
    ]


def test_a04_d_an_adr_0021_shaped_acceptance_is_not_read() -> None:
    """ADR 0021's form (a dated cell that does not start `accepted`, a clause with prose) in
    ADR 0028 counts for nothing, and ADR 0021 itself is not an input."""
    shaped = adr_0028().replace(
        "| V14 (b) | the alpha verdict | pending | later |",
        f'| V14 (b) one PTC family qualified | verdict | {JUDGED}, "carry as FAIL" | v0.2 |',
    )
    rows = V14_FAIL
    words = {gate: word for gate, (word, _, _) in rows.items()}
    real_0021 = (REPO_ROOT / "docs" / "adr" / "0021-v0.1-release-policy.md").read_text("utf-8")
    assert set(v0_1_gate.accepted_clauses(real_0021)) == {"V14 (b)"}
    for policy_text in (shaped, adr_0028(d3="pending")):
        result = report(
            files(
                ledger=ledger(words),
                verdicts=document(rows),
                adr_0028=policy_text,
                **{"docs/adr/0021-v0.1-release-policy.md": real_0021},
            )
        )
        assert result["reasons"] == [
            "V14: FAIL clause not accepted in ADR 0028 D3: ['V14 (b)'] (D2.3)"
        ]


def test_a04_e_an_unlisted_fail_is_refused() -> None:
    result = _fail_report(f"accepted, {JUDGED}", {**V14_FAIL, "V13": ("FAIL", "V13 (e)", "—")})
    assert result["reasons"] == ["V13: FAIL clause not accepted in ADR 0028 D3: ['V13 (e)'] (D2.3)"]


def test_a04_f_a_blocked_w21_is_refused() -> None:
    rows = {**ALL_PASS, "W21": ("BLOCKED", "W21 (f): the 4TU data-use statement", "—")}
    words = {gate: word for gate, (word, _, _) in rows.items()}
    result = report(files(ledger=ledger(words), verdicts=document(rows)))
    assert result["reasons"] == ["W21: BLOCKED blocks the tag (D2.2)"]
    assert "blocked: W21 (f): the 4TU data-use statement" in v0_2_gate.text(result)


def test_a04_g_ledger_and_document_disagreeing_is_refused() -> None:
    rows = {**ALL_PASS, "W22": ("FAIL", "W22 (c)", "—")}
    result = report(files(verdicts=document(rows)))
    assert result["reasons"][0] == f"W22: ledger PASS but {VERDICTS} FAIL"
    assert not result["tag_may_be_proposed"]


@pytest.mark.parametrize(("cell", "counts"), TRUTH["T4_frank_cell"].items())
def test_a04_h_the_d3_cell_rule_is_table_t4(cell: str, counts: bool) -> None:
    assert (v0_2_gate.acceptance_date(cell) is not None) is counts
    assert _fail_report(cell)["tag_may_be_proposed"] is counts


D3_ROW = "| V14 (b) | the alpha verdict | {cell} | later |"
RULE = "| --- | --- | --- | --- |\n"
D3_TABLE = "\n| Clause | Evidence | Frank's acceptance | Owner after 0.2.0a1 |\n" + RULE
DECISIONS_TABLE = "\n| Item | Question | Default | Frank's answer |\n" + RULE


def _v14_fail_reasons(policy_text: str) -> list[str]:
    words = {gate: word for gate, (word, _, _) in V14_FAIL.items()}
    return report(files(ledger=ledger(words), verdicts=document(V14_FAIL), adr_0028=policy_text))[
        "reasons"
    ]


def test_a04_i_a_d3_row_counts_only_if_its_first_cell_is_exactly_a_clause() -> None:
    """Review F4.1 (the build lane's choice 3, alone): the acceptance cell passes Table T4, and
    only the first cell carries prose after the clause."""
    accepted = adr_0028(d3=ACCEPTED)
    assert _v14_fail_reasons(accepted) == []
    prose = accepted.replace("| V14 (b) | the alpha verdict |", "| V14 (b) one PTC family | … |")
    assert _v14_fail_reasons(prose) == [
        "V14: FAIL clause not accepted in ADR 0028 D3: ['V14 (b)'] (D2.3)"
    ]


def test_a04_j_two_d3_tables_are_refused() -> None:
    """Review F4.2: even with every gate PASS, so no D3 row is needed."""
    second = D3_TABLE + D3_ROW.format(cell=ACCEPTED) + "\n"
    result = report(files(adr_0028=adr_0028(d3=ACCEPTED, extra=second)))
    assert result["reasons"] == [
        f'{ADR_0028}: D3: 2 tables with a "frank\'s acceptance" column, not 1'
    ]


def test_a04_k_a_d3_clause_listed_twice_is_refused() -> None:
    """Review F4.4: two rows for V14 (b), both acceptances on the judged date."""
    row = D3_ROW.format(cell=ACCEPTED)
    doubled = adr_0028(d3=ACCEPTED).replace(row, f"{row}\n{row}")
    assert _v14_fail_reasons(doubled) == [f"{ADR_0028}: D3 lists V14 (b) twice"]


def test_a04_l_a_d3_acceptance_on_a_non_calendar_date_is_refused() -> None:
    """Review F4.6: `2026-02-30` matches Table T4's pattern and is no date."""
    assert v0_2_gate.acceptance_date("accepted, 2026-02-30") is None
    assert _v14_fail_reasons(adr_0028(d3="accepted, 2026-02-30")) == [
        "V14: FAIL clause not accepted in ADR 0028 D3: ['V14 (b)'] (D2.3)"
    ]


def test_a04_a_missing_ledger_gate_or_verdict_is_refused() -> None:
    gates = yaml.safe_load(ledger({gate: "PASS" for gate in CLAIMED}))["gates"]
    without_w22 = yaml.safe_dump({"gates": [g for g in gates if g["id"] != "W22"]})
    assert report(files(ledger=without_w22))["reasons"] == [
        "W22: no such gate in the ledger (D2.1)"
    ]
    unjudged = ledger({gate: "PASS" for gate in CLAIMED if gate != "W21"})
    assert report(files(ledger=unjudged))["reasons"] == ["W21: no verdict in the ledger (D2.1)"]
    odd = ledger({gate: "PASS" for gate in CLAIMED} | {"W21": "pass"})
    assert report(files(ledger=odd))["reasons"][0] == (
        "W21: ledger verdict 'pass' is not one of ('PASS', 'FAIL', 'BLOCKED') (D2.1)"
    )


# -- M07a.A05: Frank's decisions table ---------------------------------------------------------


@pytest.mark.parametrize("item", ["N3", "V17 carry", "M02 N1"])
@pytest.mark.parametrize(
    "state",
    # `accepted (i), …` is a chosen alternative, not the default (Amendment 1 (review) F1).
    ["pending", "alternative (i), 2026-10-12", "accepted (i), 2026-10-12", None, "2026-10-11"],
)
def test_a05_each_of_frank_s_answers_must_be_an_acceptance(item: str, state: str | None) -> None:
    """The last state is an acceptance dated the day before `Judged` (Amendment 1 (review) F2)."""
    if state == "2026-10-11":
        result = report(files(adr_0028=adr_0028(answers={item: f"accepted, {state}"})))
        assert result["reasons"] == [
            f"Frank's answer to {item}: accepted 2026-10-11, before the verdict's Judged date "
            f"{JUDGED} (§7.3 item 11)"
        ]
        return
    result = report(files(adr_0028=adr_0028(answers={item: state})))
    if state is None:
        expected = f"Frank's answer to {item}: no row {item!r} in {ADR_0028}"
    else:
        expected = (
            f"Frank's answer to {item} is not an acceptance of the default; "
            "amend the alpha specification for it"
        )
    assert result["reasons"] == [expected]


@pytest.mark.parametrize(("cell", "judged", "counts"), TRUTH["T6_frank_dated"])
def test_a05_table_t6_dates_d3_and_each_answer_against_judged(
    cell: str, judged: str, counts: bool
) -> None:
    """Table T6 (Amendment 1 (review) F2) for the D3 row and for each of the three answers in
    turn, the other cells accepted on the judged date."""
    on_judged = f"accepted, {judged}"
    answers = dict.fromkeys(ALPHA.frank_items, on_judged)
    verdicts = document(V14_FAIL, judged=judged)
    words = {gate: word for gate, (word, _, _) in V14_FAIL.items()}
    d3 = report(
        files(
            ledger=ledger(words),
            verdicts=verdicts,
            adr_0028=adr_0028(d3=cell, answers=answers),
        )
    )
    assert d3["tag_may_be_proposed"] is counts, d3["reasons"]
    for item in ALPHA.frank_items:
        result = report(
            files(
                ledger=ledger(words),
                verdicts=verdicts,
                adr_0028=adr_0028(d3=on_judged, answers={**answers, item: cell}),
            )
        )
        assert result["tag_may_be_proposed"] is counts, (item, result["reasons"])
        if not counts:
            frank = [r for r in result["reasons"] if r.startswith("Frank's answer to")]
            assert frank and all(r.startswith(f"Frank's answer to {item}") for r in frank)


def test_a05_a_later_alpha_is_not_proposable_on_the_earlier_alpha_s_answers() -> None:
    """Review F2: `0.2.0a2`, with a new verdict judged after `0.2.0a1`'s answers, refuses on each
    of the three answers, though the same ADR tables pass for `0.2.0a1`."""
    first = adr_0028()  # the three answers accepted on 0.2.0a1's Judged date
    assert report(files(adr_0028=first))["tag_may_be_proposed"]
    later = "2026-11-02"
    result = report(
        files(
            adr_0028=first,
            verdicts=document(ALL_PASS, judged=later),
            envelope=envelope(release="0.2.0a2"),
        ),
        version="0.2.0a2",
    )
    assert result["reasons"] == [
        f"Frank's answer to {item}: accepted {JUDGED}, before the verdict's Judged date {later} "
        "(§7.3 item 11)"
        for item in ALPHA.frank_items
    ]


def test_a05_two_decisions_tables_are_refused() -> None:
    """Review F4.3: a second table with a `Frank's answer` column, itself all accepted."""
    second = DECISIONS_TABLE + "".join(
        f"| {item} | q | d | {ACCEPTED} |\n" for item in ALPHA.frank_items
    )
    result = report(files(adr_0028=adr_0028(extra=second)))
    assert result["reasons"] == [
        f"{ADR_0028}: Frank's answers: 2 tables with a \"frank's answer\" column, not 1"
    ]


@pytest.mark.parametrize("item", ["N3", "V17 carry", "M02 N1"])
def test_a05_a_doubled_decisions_row_is_refused(item: str) -> None:
    """Review F4.4: two rows for one item, both acceptances on the judged date."""
    row = f"| {item} | q | d | {ACCEPTED} |"
    doubled = adr_0028().replace(row, f"{row}\n{row}")
    assert report(files(adr_0028=doubled))["reasons"] == [
        f"Frank's answer to {item}: 2 rows in {ADR_0028}, not 1"
    ]


@pytest.mark.parametrize("item", ["N3", "V17 carry", "M02 N1"])
def test_a05_an_answer_on_a_non_calendar_date_is_refused(item: str) -> None:
    """Review F4.6, for the decisions table."""
    result = report(files(adr_0028=adr_0028(answers={item: "accepted, 2026-02-30"})))
    assert result["reasons"] == [
        f"Frank's answer to {item} is not an acceptance of the default; "
        "amend the alpha specification for it"
    ]


def test_a05_the_real_adr_0028_accepts_all_three() -> None:
    """Frank accepted the defaults on 2026-10-17 (after the verdict's Judged date 2026-10-16): the
    real ADR's three answers raise no refusal of their own. Before that they were `pending`."""
    real = (REPO_ROOT / ADR_0028).read_text(encoding="utf-8")
    result = report(files(adr_0028=real))
    frank = [reason for reason in result["reasons"] if reason.startswith("Frank's answer to")]
    assert frank == []


# -- M07a.A14: the re-judgement (§19.2, R-371; Tables T7 and T8) -------------------------------


@pytest.mark.parametrize(
    ("item", "cell", "judged", "rejudged", "counts"), TRUTH["T7_frank_rejudged"]
)
def test_a14_a_table_t7_bounds_what_a_re_judgement_read(
    item: str, cell: str, judged: str, rejudged: str | None, counts: bool
) -> None:
    """Each row of Table T7 as an ADR 0028 fixture beside a verdict document with the row's
    `Judged` and `**Re-judged:**` line; every other answer accepted on `Judged`, which counts
    under T7; where the item is a clause, the row's gate `FAIL` on it."""
    answers = dict.fromkeys(ALPHA.frank_items, f"accepted, {judged}")
    if item in ALPHA.frank_items:
        rows, clause, d3 = ALL_PASS, "V14 (b)", "pending"
        answers[item] = cell
    else:
        gate = item.split(" ", 1)[0]
        rows, clause, d3 = {**ALL_PASS, gate: ("FAIL", item, "L01")}, item, cell
    words = {gate: word for gate, (word, _, _) in rows.items()}
    line = None if rejudged is None else f"**Re-judged:** {rejudged}"
    result = report(
        files(
            ledger=ledger(words),
            verdicts=document(rows, judged=judged, rejudged=line),
            adr_0028=adr_0028(d3=d3, answers=answers, clause=clause),
        )
    )
    assert result["tag_may_be_proposed"] is counts, result["reasons"]
    if counts:
        return
    (reason,) = result["reasons"]
    named = f"Frank's answer to {item}" if item in ALPHA.frank_items else f"{gate}: {item}: "
    assert reason.startswith(named), reason
    date = v0_2_gate.acceptance_date(cell)
    if date is not None:  # a refusal on a date names it and both verdict dates
        assert date.isoformat() in reason and f"Judged date {judged}" in reason, reason
        assert rejudged is None or f"re-judged {rejudged}" in reason, reason


@pytest.mark.parametrize(("line", "judged", "well_formed"), TRUTH["T8_rejudged_line"])
def test_a14_b_table_t8_is_the_re_judged_line_s_rule(
    line: str, judged: str, well_formed: bool
) -> None:
    text = document(ALL_PASS, judged=judged, rejudged=line)
    if not well_formed:
        with pytest.raises(ValueError, match="Re-judged"):
            v0_2_gate.verdict_document(text, ALPHA, RC)
        with pytest.raises(ValueError, match="Re-judged"):
            report(files(verdicts=text))
        return
    read = v0_2_gate.verdict_document(text, ALPHA, RC)
    found = v0_2_gate.REJUDGED_VALUE.fullmatch(line)
    assert found and read.rejudged is not None and read.judged.isoformat() == judged
    assert read.rejudged.date.isoformat() == found.group(1)
    assert read.rejudged.gates == tuple(found.group(2).split(", "))
    answers = dict.fromkeys(ALPHA.frank_items, f"accepted, {judged}")
    result = report(files(verdicts=text, adr_0028=adr_0028(answers=answers)))
    assert result["tag_may_be_proposed"], result["reasons"]
    assert result["judged"] == judged
    assert result["rejudged"] == {"date": found.group(1), "gates": list(read.rejudged.gates)}


def test_a14_c_two_re_judged_lines_are_an_error() -> None:
    first, second = "**Re-judged:** 2026-10-20 (W21)", "**Re-judged:** 2026-10-21 (V13)"
    text = document(ALL_PASS, rejudged=first, after=f"\n{second}\n")
    with pytest.raises(ValueError, match="2 `\\*\\*Re-judged:\\*\\*` lines"):
        v0_2_gate.verdict_document(text, ALPHA, RC)
    with pytest.raises(ValueError):
        report(files(verdicts=text))


def test_a14_c_a_second_line_that_is_itself_malformed_is_an_error() -> None:
    text = document(ALL_PASS, rejudged="**Re-judged:** 2026-10-20 (W21)", after="**Re-judged:**\n")
    with pytest.raises(ValueError, match="Re-judged"):
        v0_2_gate.verdict_document(text, ALPHA, RC)


def test_a14_d_a_well_formed_line_anywhere_in_the_document_parses() -> None:
    line = "**Re-judged:** 2026-10-20 (V13, V17, W21)"
    text = document(ALL_PASS, after=f"\n## Re-judgement\n\n  {line}\n\nprose\n")
    read = v0_2_gate.verdict_document(text, ALPHA, RC)
    assert read.rejudged == v0_2_gate.Rejudgement(
        date=datetime.date(2026, 10, 20), gates=("V13", "V17", "W21")
    )
    assert report(files(verdicts=text))["tag_may_be_proposed"]


def test_a14_no_re_judgement_is_table_t6() -> None:
    read = v0_2_gate.verdict_document(document(ALL_PASS), ALPHA, RC)
    assert read.rejudged is None
    assert report()["rejudged"] is None


# -- M07a.A06: W23–W27 are not claimed ---------------------------------------------------------


@pytest.mark.parametrize("word", [None, "PASS", "FAIL", "BLOCKED"])
def test_a06_unclaimed_gates_never_block(word: str | None) -> None:
    verdicts = {gate: "PASS" for gate in CLAIMED} | {gate: word for gate in UNCLAIMED}
    result = report(files(ledger=ledger(verdicts)))
    assert result["tag_may_be_proposed"], result["reasons"]
    output, table = v0_2_gate.text(result), v0_2_gate.markdown(result)
    for gate in UNCLAIMED:
        assert f"\n{gate}  not claimed ({SET})\n" in output
        assert f"| {gate} | not claimed | req {gate} | — |" in table.splitlines()
    assert not any(re.search(r"W2[3-7]", reason) for reason in result["reasons"])


# -- M07a.A07: the tree check is v0.1's --------------------------------------------------------


def test_a07_the_tree_check_is_v0_1_gate_s_own() -> None:
    assert v0_2_gate.tree_differences is v0_1_gate.tree_differences
    assert v0_2_gate.TREES == v0_1_gate.TREES and v0_2_gate.VERSION_FILES == v0_1_gate.VERSION_FILES
    assert list(v0_2_gate.TREES) == REFERENCE["registered"]["tree_check"]["trees"]


def test_a07_a_tree_check_not_run_refuses() -> None:
    """Review F3: `build(differences=None)` is a tree check not run, never "equal to C"."""
    result = v0_2_gate.build(
        files=files(),
        rc=RC,
        rc_version=VERSION,
        rc_in_repository=True,
        candidate=CANDIDATE,
        version=VERSION,
        differences=None,
        is_ancestor=lambda commit: commit in ANCESTORS,
    )
    assert result["reasons"] == ["tree check (D2.4) not run"]
    assert not result["tag_may_be_proposed"]
    assert "tree check (D2.4): not run" in v0_2_gate.text(result).splitlines()
    assert "tree check (D2.4): equal to C" in v0_2_gate.text(report()).splitlines()


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, changes: dict[str, str | None], message: str) -> str:
    for name, content in changes.items():
        if content is None:
            (repo / name).unlink()
            continue
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    monkeypatch.setattr(v0_1_gate, "ROOT", repo)
    monkeypatch.setattr(v0_2_gate, "ROOT", repo)
    return repo


def test_a07_t08_a50_s_and_r_151_s_states_give_v0_1_s_answers(
    scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = {
        "pyproject.toml": '[project]\nname = "p"\nversion = "0.2.0a1"\ndependencies = ["a==1"]\n',
        "src/openflowsheet/__init__.py": '__version__ = "0.2.0a1"\n',
        "src/openflowsheet/x.py": "X = 1\n",
        "schemas/a.schema.json": "{}\n",
        "benchmarks/b.yaml": "b: 1\n",
        "requirements.lock": "a==1\n",
        "MANIFEST.in": "graft src\n",
        "README.md": "readme\n",
        "LICENSE": "licence\n",
        "NOTICE": "notice\n",
        "docs/elsewhere.md": "not a D2.4 path\n",
    }
    rc = _commit(scratch, dict(base), "rc")
    bumped = _commit(
        scratch,
        {
            "pyproject.toml": base["pyproject.toml"].replace("0.2.0a1", "0.2.0a2"),
            "src/openflowsheet/__init__.py": '__version__ = "0.2.0a2"\n',
            "docs/elsewhere.md": "edited\n",
        },
        "version only",
    )
    pinned = _commit(
        scratch,
        {
            "pyproject.toml": base["pyproject.toml"]
            .replace("a==1", "a==2")
            .replace("0.2.0a1", "0.2.0a2")
        },
        "pin edit",
    )
    edited = _commit(scratch, {"src/openflowsheet/x.py": "X = 2\n"}, "edit")
    added = _commit(scratch, {"src/openflowsheet/y.py": "Y = 1\n"}, "addition")
    removed = _commit(scratch, {"schemas/a.schema.json": None}, "removal")
    _commit(scratch, {"schemas/a.schema.json": "{}\n"}, "restore")
    (scratch / "schemas/a.schema.json").chmod(0o755)
    moded = _commit(scratch, {}, "mode change")
    twice = _commit(
        scratch,
        {
            "src/openflowsheet/__init__.py": '__version__ = "0.2.0a2"  # "0.2.0a2"\n',
            "src/openflowsheet/x.py": "X = 1\n",
            "src/openflowsheet/y.py": None,
        },
        "doubled version string",
    )
    answers = {
        rc: [],
        bumped: [],
        pinned: ["pyproject.toml"],
        edited: ["pyproject.toml", "src/openflowsheet/x.py"],
        added: ["pyproject.toml", "src/openflowsheet/x.py", "src/openflowsheet/y.py"],
        removed: [
            "pyproject.toml",
            "schemas/a.schema.json",
            "src/openflowsheet/x.py",
            "src/openflowsheet/y.py",
        ],
        moded: [
            "pyproject.toml",
            "schemas/a.schema.json",
            "src/openflowsheet/x.py",
            "src/openflowsheet/y.py",
        ],
        twice: ["pyproject.toml", "schemas/a.schema.json", "src/openflowsheet/__init__.py"],
    }
    record = v0_1_gate.tree_record(rc)
    for candidate, expected in answers.items():
        assert v0_2_gate.tree_differences(rc, candidate) == expected, candidate
        assert v0_1_gate.tree_differences(rc, candidate) == expected
        assert v0_1_gate.recorded_tree_differences(record, candidate) == expected
    # C absent: with its record the same answers; without it, C cannot be found (exit 2).
    monkeypatch.setattr(v0_1_gate, "has_commit", lambda commit: commit != rc)
    with pytest.raises(ValueError, match="is not in this repository"):
        v0_2_gate.tree_differences(rc, edited)
    (scratch / v0_1_gate.RC_TREES).mkdir(parents=True)
    (scratch / v0_1_gate.RC_TREES / f"{rc}.json").write_text(json.dumps(record), "utf-8")
    for candidate, expected in answers.items():
        assert v0_2_gate.tree_differences(rc, candidate) == expected


# -- M07a.A08: the RC record -------------------------------------------------------------------


def _record_reasons(record: str) -> list[str]:
    return v0_2_gate.rc_record_problems(record, RC, ALPHA)


def test_a08_steps_1_to_12_passed() -> None:
    assert _record_reasons(rc_record()) == []


def test_a08_step_13_is_not_required() -> None:
    record = rc_record().replace('exit 1: "NO (3 reasons)"', "FAIL")
    assert _record_reasons(record) == []


def _results(**changes: list[str]) -> dict[int, list[str]]:
    results = {step: ["PASS (1/1)"] for step in range(1, 13)}
    for key, value in changes.items():
        step = int(key[1:])
        if value:
            results[step] = value
        else:
            results.pop(step)
    return results


@pytest.mark.parametrize(
    ("results", "step"),
    [
        (_results(s7=["FAIL (0/1)"]), 7),
        (_results(s12=[]), 12),
        (_results(s12=["—"]), 12),
        (_results(s12=["Not measured (aarch64)"]), 12),
        (_results(s12=["PASS (9/10)"]), 12),
    ],
    ids=["step 7 failed", "step 12 missing", "step 12 supporting only", "not measured", "9 of 10"],
)
def test_a08_a_step_not_passed_is_refused_by_name(results: dict[int, list[str]], step: int) -> None:
    reasons = _record_reasons(rc_record(results))
    assert reasons and all(f"step {step}" in reason for reason in reasons), reasons
    assert not report(files(rc_record=rc_record(results)))["tag_may_be_proposed"]


def test_a08_a_record_of_another_c_or_none_is_refused() -> None:
    assert _record_reasons(rc_record(commit="e" * 40)) == [
        f"{RC_RECORD} is the record of C = {['e' * 40]}, not of {RC}"
    ]
    assert report(files(rc_record=None))["reasons"] == [
        f"no RC record: {RC_RECORD} does not exist at the candidate"
    ]


def test_a08_a_step_beyond_13_is_unreadable() -> None:
    record = rc_record().replace("| 13 | M07a.A12", "| 14 | M07a.A12")
    assert _record_reasons(record) == [f"{RC_RECORD}: unreadable row ['14', 'M07a.A12']"]


# -- M07a.A09: the manifests -------------------------------------------------------------------


def test_a09_a_m07a_tested_at_c() -> None:
    assert report()["manifest_problems"] == []
    assert report(files(m07a=manifest("M07a", RC, "reviewed")))["tag_may_be_proposed"]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"m07a": None}, f"no M07a manifest: evidence/M07a/{RC}/manifest.json does not exist"),
        ({"m07a": manifest("M07a", "e" * 40)}, f"not of M07a at {RC}"),
        ({"m07a": manifest("M07a", RC, "implemented")}, "status 'implemented', not `tested`"),
        ({"m02": manifest("M02", M02_AT, "planned")}, "M02 manifest at C or an ancestor"),
        ({"m01": manifest("M01", M01_AT, "implemented")}, "M01 manifest at C or an ancestor"),
        ({"m02": manifest("M01", M02_AT)}, "M02 manifest at C or an ancestor"),
    ],
    ids=[
        "M07a missing",
        "M07a at another commit",
        "M07a implemented",
        "M02 planned",
        "M01 implemented only",
        "M02 directory holding M01's manifest",
    ],
)
def test_a09_b_d_a_manifest_that_does_not_count_is_refused(
    overrides: dict[str, str | None], expected: str
) -> None:
    result = report(files(**overrides))
    assert len(result["reasons"]) == 1 and expected in result["reasons"][0], result["reasons"]


def test_a09_c_m02_s_only_manifest_off_c_s_history_is_refused() -> None:
    elsewhere = "f" * 40
    off_history = {f"evidence/M02/{elsewhere}/manifest.json": manifest("M02", elsewhere)}
    result = report(files(m02=None, **off_history))
    assert result["reasons"] == [
        "no `tested` or `reviewed` M02 manifest at C or an ancestor of C "
        "(evidence/M02/<c>/manifest.json)"
    ]


def test_a09_e_c_absent_refuses_with_7_4_s_reason() -> None:
    result = report(rc_in_repository=False)
    assert result["reasons"] == ["C is not in the repository: the M01/M02 ancestry check needs it"]


# -- M07a.A10: the envelope --------------------------------------------------------------------


def test_a10_the_envelope_must_be_pinned_to_the_alpha() -> None:
    assert report()["envelope_problems"] == []
    # The real envelope in its working form: since the cut pins it (MR-3), the pin is undone
    # here so the fixture stays the file a gate that does not read the envelope would pass.
    today = (REPO_ROOT / ENVELOPE).read_text(encoding="utf-8")
    for pinned, working in (
        ("envelope_id: v0.2-alpha-envelope-1\n", "envelope_id: v0.2-envelope-dev\n"),
        ("release: 0.2.0a1\n", "release: 0.2.0.dev0\n"),
    ):
        today = today.replace(pinned, working, 1)
    assert yaml.safe_load(today)["envelope_id"] == "v0.2-envelope-dev"
    untravelled = document({gate: ("PASS", "—", "—") for gate in CLAIMED})
    working = report(files(envelope=today, verdicts=untravelled))
    assert working["reasons"] == [
        f"{ENVELOPE}: envelope_id 'v0.2-envelope-dev', not 'v0.2-alpha-envelope-1'",
        f"{ENVELOPE}: release '0.2.0.dev0', not '0.2.0a1'",
    ]
    assert report(files(envelope=envelope(release="0.2.0a2")))["reasons"] == [
        f"{ENVELOPE}: release '0.2.0a2', not '0.2.0a1'"
    ]
    assert report(files(envelope=None))["envelope_problems"] == [
        f"{ENVELOPE} does not exist at the candidate"
    ]


# -- M07a.A11: the required ADRs ---------------------------------------------------------------


@pytest.mark.parametrize(("line", "accepted"), TRUTH["T5_adr_status"].items())
def test_a11_the_status_rule_is_table_t5(line: str, accepted: bool) -> None:
    result = report(files(adr_0022=adr(line)))
    assert result["tag_may_be_proposed"] is accepted
    if not accepted:
        assert result["reasons"] == [f"ADR 0022 is not Accepted: {line}"]


def test_a11_a_missing_or_doubled_adr_is_refused() -> None:
    assert report(files(adr_0035=None))["reasons"] == [
        "ADR 0035: 0 files docs/adr/0035-*.md at the candidate, not 1"
    ]
    doubled = files(**{"docs/adr/0035-another.md": adr()})
    assert report(doubled)["reasons"] == [
        "ADR 0035: 2 files docs/adr/0035-*.md at the candidate, not 1"
    ]
    assert report(files(adr_0022=adr("Accepted, without a status line")))["reasons"] == [
        "ADR 0022: docs/adr/0022-test-input.md has no **Status:** line"
    ]


def test_a11_the_real_adrs_0022_and_0028() -> None:
    real_0022 = (REPO_ROOT / "docs/adr/0022-v0.2-real-chemistry-selection.md").read_text("utf-8")
    assert report(files(adr_0022=real_0022))["tag_may_be_proposed"]
    real_0028 = (REPO_ROOT / ADR_0028).read_text(encoding="utf-8")
    line = v0_2_gate.status_line(real_0028)
    assert line is not None and line.startswith("**Status:** Proposed")
    reasons = report(files(adr_0028=real_0028))["reasons"]
    assert f"ADR 0028 is not Accepted: {line}" in reasons


# -- M07a.A12: output and exit codes -----------------------------------------------------------


def test_a12_the_text_report() -> None:
    result = report()
    lines = v0_2_gate.text(result).splitlines()
    assert lines[0] == f"v0.2 gates ({SET}) at C = {RC}; candidate {CANDIDATE}"
    assert gate_rows("\n".join(lines)) == [*CLAIMED, *UNCLAIMED]
    for prefix in (
        "tree check (D2.4): ",
        "RC record (§8.1 item 4): ",
        "manifests (§8.1 item 5; §7.2 item 5): ",
        "envelope (§7.2 item 6): ",
        "ADRs (§7.2 item 7): ",
        "Frank's answers (ADR 0028): ",
    ):
        assert sum(line.startswith(prefix) for line in lines) == 1, prefix
    assert lines[-1] == "v0.2.0a1 tag may be proposed: YES"
    refused = report(files(adr_0035=None, envelope=envelope(release="0.2.0a2")))
    refused_lines = v0_2_gate.text(refused).splitlines()
    assert refused_lines[-1] == "v0.2.0a1 tag may be proposed: NO (2 reasons)"
    assert refused_lines[-3:-1] == [f"  - {reason}" for reason in refused["reasons"]]


def test_a12_markdown_and_json() -> None:
    result = report()
    table = v0_2_gate.markdown(result).splitlines()
    assert table[0] == (
        "| Gate | Verdict at C | Required evidence | Clauses and travelling limitations |"
    )
    assert [row.split(" | ")[0].lstrip("| ") for row in table[2:]] == [*CLAIMED, *UNCLAIMED]
    assert table[2] == "| V11 | PASS | req V11 | limitations: L01 |"
    assert set(result) == {
        "gate_set",
        "rc",
        "candidate",
        "version",
        "rc_version",
        "judged",
        "rejudged",
        "gates",
        "tree_differences",
        "rc_record_problems",
        "manifest_problems",
        "envelope_problems",
        "adr_problems",
        "frank_problems",
        "tag_may_be_proposed",
        "reasons",
    }
    assert json.loads(json.dumps(result)) == result


def _build_scratch(repo: Path) -> tuple[str, str]:
    """A scratch repository: a package commit P (M01's and M02's manifests name it), `C` at
    `0.2.0a1` with the D2.4 files, and a candidate that adds every record after `C`."""
    package = _commit(repo, {"docs/package.md": f"{MARK}\n"}, "package")
    rc = _commit(
        repo,
        {
            "pyproject.toml": '[project]\nname = "p"\nversion = "0.2.0a1"\n',
            "src/openflowsheet/__init__.py": '__version__ = "0.2.0a1"\n',
            ENVELOPE: envelope(),
        },
        "C",
    )
    records = files()
    records[VERDICTS] = document(ALL_PASS, rc=rc)
    records[RC_RECORD] = rc_record(commit=rc)
    records[f"evidence/M07a/{rc}/manifest.json"] = manifest("M07a", rc)
    records[f"evidence/M01/{package}/manifest.json"] = manifest("M01", package)
    records[f"evidence/M02/{package}/manifest.json"] = manifest("M02", package)
    for stale in (PATHS["m07a"], PATHS["m01"], PATHS["m02"], ENVELOPE):
        records.pop(stale)
    candidate = _commit(repo, dict(records), "records")
    return rc, candidate


def _main(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = v0_2_gate.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_a12_main_exit_codes_on_a_scratch_repository(
    scratch: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    rc, candidate = _build_scratch(scratch)
    code, out, _ = _main(capsys, "--rc", rc)
    assert code == 0, out
    assert out.splitlines()[0] == f"v0.2 gates ({SET}) at C = {rc}; candidate {candidate}"
    assert out.splitlines()[-1] == "v0.2.0a1 tag may be proposed: YES"
    code, out, _ = _main(capsys, "--rc", rc[:10], "--json")
    assert code == 0 and json.loads(out)["tag_may_be_proposed"] is True
    code, out, _ = _main(capsys, "--rc", rc, "--markdown")
    assert code == 0 and len(out.splitlines()) == 2 + 17
    # Inputs are read at the candidate, not from the working tree.
    (scratch / VERDICTS).write_text("not a verdict document\n", "utf-8")
    assert _main(capsys, "--rc", rc)[0] == 0
    _git(scratch, "checkout", "-q", "--", VERDICTS)
    # A refusal: a D2.4 path edited after C.
    _commit(scratch, {"src/openflowsheet/x.py": "X = 1\n"}, "edit")
    code, out, _ = _main(capsys, "--rc", rc)
    assert code == 1
    assert "differs from C in ['src/openflowsheet/x.py'] (D2.4)" in out
    assert out.splitlines()[-1] == "v0.2.0a1 tag may be proposed: NO (1 reasons)"
    code, out, _ = _main(capsys, "--rc", rc, "--candidate", candidate)
    assert code == 0, out
    # Exit 2: a malformed verdict document, and a C that cannot be found.
    _commit(scratch, {VERDICTS: document(_swap("V11", "V12"), rc=rc)}, "malformed")
    code, _, err = _main(capsys, "--rc", rc)
    assert code == 2 and "in order" in err
    code, _, err = _main(capsys, "--rc", "f" * 40)
    assert code == 2 and "--rc" in err
    # C absent, its record written while it was present: refused by §7.4's reason (exit 1).
    assert _main(capsys, "--rc", rc, "--write-tree-record")[0] == 0
    assert json.loads((scratch / "release/rc-trees" / f"{rc}.json").read_text("utf-8")) == (
        v0_1_gate.tree_record(rc)
    )
    absent = lambda commit: commit != rc  # noqa: E731
    monkeypatch.setattr(v0_1_gate, "has_commit", absent)
    monkeypatch.setattr(v0_2_gate, "has_commit", absent)
    code, out, _ = _main(capsys, "--rc", rc, "--candidate", candidate)
    assert code == 1
    assert "  - C is not in the repository: the M01/M02 ancestry check needs it" in out
    assert out.splitlines()[-1] == "v0.2.0a1 tag may be proposed: NO (1 reasons)"


def test_a12_main_on_an_uncovered_version(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _commit(scratch, {"pyproject.toml": '[project]\nname = "p"\nversion = "0.2.0"\n'}, "C")
    code, out, _ = _main(capsys, "--rc", rc)
    assert code == 1
    assert out == (
        "version 0.2.0 is not covered by a registered v0.2 gate set\n"
        "v0.2.0 tag may be proposed: NO (1 reasons)\n"
    )


# -- M07a.A13: the v0.1 gate is untouched ------------------------------------------------------


def test_a13_the_v0_1_gate_and_its_test_are_byte_identical_to_the_base() -> None:
    registered = REFERENCE["registered"]["v0_1_gate_files_sha256"]
    for path in ("scripts/v0_1_gate.py", "tests/test_t08_w4_v0_1_gate.py"):
        assert hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest() == registered[path]
