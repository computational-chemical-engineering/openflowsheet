"""M07.A30–A38: `scripts/v0_2_gate.py`'s gate set `v0.2-gate-v1` for 0.2.0 (M07 spec §7, §8, §9).

The registry gains `v0.2-gate-v1` beside the alpha's entry: it covers 0.2.0, 0.2.0bN and 0.2.0rcN
(Table T-V), claims all seventeen gates, reads its own clause grammar (V11–V20, W21–W27), ADR 0042,
`docs/reviews/V02-verdicts.md`, `docs/v02-rc-record.md` (steps 1–17), M07's manifest at `C` and the
six packages' at ancestors of `C`. The decision items are the alpha's §7.3 items 1–12 with this
entry's values (§7.2); each has its own refusing state here on an otherwise passing fixture, so a
dropped rule fails its own test. With item 11, ADR 0042's `V17 carry` row must name the register
entry of every link of the surface chain (`scripts/m07a_rc.py`'s `LINKS` at the candidate; R-457,
obligation O3 of `docs/design/V02-alpha-main-rulings.md` §5). The alpha's entry is unchanged
(A31): its own tests are `tests/test_m07a_v0_2_gate.py`.

The inputs are of two kinds, and each says which it is:

- **real records**: the registration `benchmarks/m07/registration.json` (`gate.gate_sets`,
  `gate.versions`, the carry sets), written by `m07_reference.py` (M07.A00 checks it);
- **constructed test inputs**: minimal ledgers, verdict documents, ADR tables, RC records,
  manifests and envelopes, each carrying the marker `MARK` so that none can be mistaken for a
  record.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402

REGISTRATION = json.loads(
    (REPO_ROOT / "benchmarks" / "m07" / "registration.json").read_text(encoding="utf-8")
)
GATE = REGISTRATION["gate"]
SET = "v0.2-gate-v1"
(V02,) = [entry for entry in v0_2_gate.GATE_SETS if entry.name == SET]
ALPHA = v0_2_gate.GATE_SETS[0]
CLAIMED = V02.claimed

#: Every constructed input carries this, in its own format's comment syntax.
MARK = "TEST INPUT constructed by tests/test_m07_v0_2_gate.py; not a record"

RC = "c" * 40
CANDIDATE = "d" * 40
PACKAGE_AT = {name: str(index) * 40 for index, name in enumerate(V02.packages, start=1)}
JUDGED = "2026-11-02"
ACCEPTED = f"accepted, {JUDGED}"
VERSION = "0.2.0"
ADR_0042 = "docs/adr/0042-v0.2.0-release-policy.md"
VERDICTS = "docs/reviews/V02-verdicts.md"
RC_RECORD = "docs/v02-rc-record.md"
ENVELOPE = "benchmarks/t08/support_envelope.yaml"
LEDGER = "docs/requirements.yaml"
M07_MANIFEST = f"evidence/M07/{RC}/manifest.json"


def ledger(verdicts: dict[str, str | None]) -> str:
    gates = [
        {"id": gate, "required_evidence": f"req {gate}", "verdict": verdicts.get(gate)}
        for gate in ("G00", *CLAIMED)
    ]
    return f"# {MARK}\n" + yaml.safe_dump({"gates": gates}, sort_keys=False)


def document(
    rows: dict[str, tuple[str, str, str]], *, rc: str = RC, rejudged: str | None = None
) -> str:
    """A verdict document in the alpha's §6.3 form; each row is `(verdict, failing,
    travelling)`, in the mapping's order."""
    lines = [
        "# v0.2 — verdicts",
        "",
        f"<!-- {MARK} -->",
        "",
        f"**Release candidate:** `{rc}`   **Judged:** {JUDGED}   **By:** design lane (`verdict`)",
        *([rejudged] if rejudged is not None else []),
        "",
        "| Gate | Verdict | Failing clauses | Travelling limitations | Basis |",
        "| --- | --- | --- | --- | --- |",
    ]
    for gate, (word, failing, travelling) in rows.items():
        lines.append(f"| {gate} | {word} | {failing} | {travelling} | §{gate}; evidence at C |")
    return "\n".join(lines) + "\n"


ALL_PASS = {gate: ("PASS", "—", "L01") for gate in CLAIMED}


def adr_0042(
    *,
    d3: str = "pending",
    clause: str = "V14 (b)",
    answers: dict[str, str | None] | None = None,
    v17_default: str = "carry v0.1's paid evidence across R-192, R-234 and R-295",
) -> str:
    """ADR 0042's two tables, as the gate reads them; an answer `None` leaves out its row."""
    answers = {item: ACCEPTED for item in V02.frank_items} | (answers or {})
    defaults = {item: "d" for item in V02.frank_items} | {"V17 carry": v17_default}
    lines = [
        "# ADR 0042 (test input)",
        "",
        f"<!-- {MARK} -->",
        "",
        "**Status:** **Accepted**, 2026-11-02",
        "",
        "| D3 clause | Evidence | Frank's acceptance | Owner after 0.2.0 |",
        "| --- | --- | --- | --- |",
        f"| {clause} | the verdict | {d3} | later |",
        "",
        "| Frank item | Default | Frank's answer |",
        "| --- | --- | --- |",
        *(
            f"| {item} | {defaults[item]} | {answer} |"
            for item, answer in answers.items()
            if answer is not None
        ),
        "",
    ]
    return "\n".join(lines)


def envelope(*, envelope_id: str = "v0.2-envelope-1", release: str = VERSION) -> str:
    return f"# {MARK}\n" + yaml.safe_dump(
        {
            "envelope_id": envelope_id,
            "release": release,
            "limitations": [{"id": "L01"}, {"id": "L42"}],
        },
        sort_keys=False,
    )


RC_HEADER = "| Step | Assertion | Where | Result (as the record says) | Record | sha256 |"


def rc_record(results: dict[int, list[str]] | None = None, *, commit: str = RC) -> str:
    """An RC record for `commit`: one row per result (by default every step 1–17 `PASS`) and
    step 18's pre-verdict gate run (exit 1)."""
    results = {step: ["PASS (1/1)"] for step in V02.rc_steps} if results is None else results
    lines = [
        "# v0.2 — the release-candidate record at `C`",
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
            f"| {step} | A{step} | CI | {result} | `r{step}.json` | `ab` |" for result in outcomes
        ]
    lines.append('| 18 | M07.A36 | local | exit 1: "NO (3 reasons)" | `gate.log` | `ef` |')
    return "\n".join(lines) + "\n"


def manifest(package: str, commit: str, status: str = "tested") -> str:
    return json.dumps(
        {"_comment": MARK, "work_package": package, "commit": commit, "status": status}
    )


def adr(status: str = "**Status:** **Accepted**, 2026-10-20") -> str:
    return f"# ADR (test input)\n\n<!-- {MARK} -->\n\n{status}\n"


PATHS = {
    "ledger": LEDGER,
    "verdicts": VERDICTS,
    "adr_0042": ADR_0042,
    "envelope": ENVELOPE,
    "rc_record": RC_RECORD,
    "links": v0_2_gate.LINKS_MODULE,
    "m07": M07_MANIFEST,
    **{name.lower(): f"evidence/{name}/{at}/manifest.json" for name, at in PACKAGE_AT.items()},
    **{
        f"adr_{number}": f"docs/adr/{number}-test-input.md"
        for number in V02.required_adrs
        if number != "0042"
    },
}


#: A constructed surface chain: `LINKS` as `scripts/m07a_rc.py` writes it.
LINKS_TEXT = f"""# {MARK}
LINKS: Final = (
    Link("c_1", "R-192", strip_a3_2, "6c"),
    Link("c_2", "R-234", strip_m02, "38"),
    Link("c_3", "R-295", strip_m04, "45"),
)
"""


def files(**overrides: str | None) -> dict[str, str]:
    """An otherwise passing candidate: path → text. A keyword names a path by its key in
    `PATHS`; `None` removes the file."""
    found: dict[str, str] = {
        LEDGER: ledger({gate: "PASS" for gate in CLAIMED}),
        VERDICTS: document(ALL_PASS),
        ADR_0042: adr_0042(),
        ENVELOPE: envelope(),
        RC_RECORD: rc_record(),
        v0_2_gate.LINKS_MODULE: LINKS_TEXT,
        M07_MANIFEST: manifest("M07", RC),
        **{
            f"evidence/{name}/{at}/manifest.json": manifest(name, at)
            for name, at in PACKAGE_AT.items()
        },
        **{
            f"docs/adr/{number}-test-input.md": adr()
            for number in V02.required_adrs
            if number != "0042"
        },
    }
    for key, value in overrides.items():
        path = PATHS.get(key, key)
        if value is None:
            found.pop(path, None)
        else:
            found[path] = value
    return found


ANCESTORS = frozenset({*PACKAGE_AT.values(), RC})


def report(
    candidate_files: dict[str, str] | None = None,
    *,
    version: str = VERSION,
    rc_version: str | None = None,
    differences: list[str] | None = None,
) -> dict[str, Any]:
    return v0_2_gate.build(
        files=files() if candidate_files is None else candidate_files,
        rc=RC,
        rc_version=version if rc_version is None else rc_version,
        rc_in_repository=True,
        candidate=CANDIDATE,
        version=version,
        differences=[] if differences is None else differences,
        is_ancestor=lambda commit: commit in ANCESTORS,
    )


def gate_rows(output: str) -> list[str]:
    return re.findall(r"^((?:V1[1-9]|V20|W2[1-9]|V10))  ", output, flags=re.MULTILINE)


def test_the_otherwise_passing_fixture_may_be_proposed() -> None:
    result = report()
    assert result["gate_set"] == SET
    assert result["tag_may_be_proposed"], result["reasons"]


# -- M07.A30: the registry reproduces Table T-V ---------------------------------------------


@pytest.mark.parametrize(
    ("version", "gate_set"), [(row["version"], row["gate_set"]) for row in GATE["versions"]]
)
def test_a30_gate_set_of_is_table_t_v(version: str, gate_set: str | None) -> None:
    found = v0_2_gate.gate_set_of(version)
    assert (found.name if found else None) == gate_set


def test_a30_table_t_v_has_29_rows_and_no_version_is_covered_twice() -> None:
    versions = [row["version"] for row in GATE["versions"]]
    assert len(versions) == len(set(versions)) == 29
    for version in versions:
        assert sum(bool(entry.covers.fullmatch(version)) for entry in v0_2_gate.GATE_SETS) <= 1


def test_a30_a_version_two_sets_cover_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v0_2_gate, "GATE_SETS", (*v0_2_gate.GATE_SETS, V02))
    with pytest.raises(ValueError, match="covered by 2 gate sets, not 1"):
        v0_2_gate.gate_set_of(VERSION)


# -- M07.A31, A32: the alpha entry unchanged; the new entry is the registration's ------------


def test_a31_the_alpha_entry_reads_the_alpha_s_grammar() -> None:
    assert ALPHA.name == "v0.2-alpha-gate-v1"
    assert ALPHA.clause is v0_2_gate.CLAUSE
    assert ALPHA.rejudged.pattern == v0_2_gate.REJUDGED_VALUE.pattern
    assert ALPHA.adr == "ADR 0028" and V02.adr == "ADR 0042"


#: The released alpha's tag commit (v0.2.0a1) and the three functions of its gate test that
#: `039cbd8` edited, the only edits M07 spec §20 A3.1 (R-461) admits.
ALPHA_TAG = "423ae9c54d903f9dcf0ea90fe9639222c1acbda4"
ALPHA_TESTS = "tests/test_m07a_v0_2_gate.py"
ALPHA_TESTS_EDITED = (
    "test_the_registry_is_the_specification_s",
    "test_a01_coverage_is_table_t1",
    "test_a12_main_on_an_uncovered_version",
)


def _top_level(source: str) -> list[str]:
    """Each top-level node of a module as its `ast.dump`, an admitted edit as its name only."""
    return [
        f"edited {node.name}"
        if isinstance(node, ast.FunctionDef) and node.name in ALPHA_TESTS_EDITED
        else ast.dump(node)
        for node in ast.parse(source).body
    ]


def test_a31_b_the_alpha_s_tests_are_the_tagged_ones_but_the_three_edited() -> None:
    tagged = subprocess.run(
        ["git", "show", f"{ALPHA_TAG}:{ALPHA_TESTS}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    now = (REPO_ROOT / ALPHA_TESTS).read_text(encoding="utf-8")
    for edited in ALPHA_TESTS_EDITED:
        assert f"edited {edited}" in _top_level(tagged)
    assert _top_level(now) == _top_level(tagged)


def _fields(entry: v0_2_gate.GateSet) -> dict[str, Any]:
    return {
        "claimed": list(entry.claimed),
        "clause": entry.clause.pattern,
        "covers": entry.covers.pattern,
        "envelope_id": entry.envelope_id,
        "evidence_package": entry.evidence_package,
        "frank_items": list(entry.frank_items),
        "links_item": entry.links_item,
        "not_claimed": list(entry.not_claimed),
        "packages": list(entry.packages),
        "policy_adr": entry.policy_adr,
        "rc_last_step": entry.rc_last_step,
        "rc_record": entry.rc_record,
        "rc_steps": list(entry.rc_steps),
        "rejudge_waits": [list(wait) for wait in entry.rejudge_waits],
        "required_adrs": list(entry.required_adrs),
        "verdict_document": entry.verdict_document,
    }


@pytest.mark.parametrize("name", sorted(GATE["gate_sets"]))
def test_a32_each_entry_equals_the_registration_s(name: str) -> None:
    (entry,) = [entry for entry in v0_2_gate.GATE_SETS if entry.name == name]
    assert _fields(entry) == GATE["gate_sets"][name]


def test_a32_the_registry_is_the_registration_s_two_sets() -> None:
    assert [entry.name for entry in v0_2_gate.GATE_SETS] == [
        "v0.2-alpha-gate-v1",
        SET,
    ]
    assert sorted(GATE["gate_sets"]) == sorted(entry.name for entry in v0_2_gate.GATE_SETS)


# -- M07.A33: the clause grammar --------------------------------------------------------------

W_NEW = [f"{gate} ({clause})" for gate, clauses in GATE["w_clauses"].items() for clause in clauses]
BOTH = [f"V{n} (a)" for n in range(11, 21)] + ["W21 (a)", "W22 (c)"]
NEITHER = ["W28 (a)", "V10 (a)", "W20 (a)", "V21 (a)"]


@pytest.mark.parametrize(
    ("label", "in_v02", "in_alpha"),
    [(label, True, False) for label in W_NEW]
    + [(label, True, True) for label in BOTH]
    + [(label, False, False) for label in NEITHER],
)
def test_a33_the_clause_grammars(label: str, in_v02: bool, in_alpha: bool) -> None:
    assert bool(V02.clause.fullmatch(label)) is in_v02
    assert bool(ALPHA.clause.fullmatch(label)) is in_alpha


def test_a33_a_w23_fail_parses_under_v0_2_s_grammar_only() -> None:
    rows = ALL_PASS | {"W23": ("FAIL", "W23 (d)", "—")}
    parsed = v0_2_gate.verdict_document(document(rows), V02, RC)
    assert parsed.rows["W23"].clauses == ("W23 (d)",)
    alpha_rows = {gate: ALL_PASS[gate] for gate in ALPHA.claimed} | {
        "W22": ("FAIL", "W23 (d)", "—")
    }
    with pytest.raises(ValueError, match="is not one of W22's clauses"):
        v0_2_gate.verdict_document(document(alpha_rows), ALPHA, RC)


def test_a33_a_d3_row_is_read_under_the_set_s_grammar() -> None:
    text = adr_0042(d3=ACCEPTED, clause="W24 (a)")
    judged = v0_2_gate.datetime.date.fromisoformat(JUDGED)
    assert "W24 (a)" in v0_2_gate.policy(text, V02, judged).accepted
    assert "W24 (a)" not in v0_2_gate.policy(text, ALPHA, judged).accepted


def test_a33_a_clause_in_basis_is_refused_under_v0_2_s_grammar() -> None:
    text = document(ALL_PASS).replace("§W25; evidence at C |", "§W25; see W27 (h) |")
    with pytest.raises(ValueError, match=r"W25, Basis: holds \['W27 \(h\)'\]"):
        v0_2_gate.verdict_document(text, V02, RC)


def test_a33_a_re_judgement_may_list_w24() -> None:
    line = f"**Re-judged:** {JUDGED} (V17, W24)"
    parsed = v0_2_gate.verdict_document(document(ALL_PASS, rejudged=line), V02, RC)
    assert parsed.rejudged is not None and parsed.rejudged.gates == ("V17", "W24")
    assert v0_2_gate.REJUDGED_VALUE.fullmatch(line) is None  # the alpha's grammar
    with pytest.raises(ValueError, match="not blocked on a registered answer"):
        line = f"**Re-judged:** {JUDGED} (W25)"
        v0_2_gate.verdict_document(document(ALL_PASS, rejudged=line), V02, RC)


# -- M07.A34: decision items 1–12 --------------------------------------------------------------

STEP_15 = {step: ["PASS (1/1)"] for step in V02.rc_steps} | {15: ["FAIL (re-run required)"]}
NO = {
    1: (
        {"version": "0.2.0.post1"},
        "version 0.2.0.post1 is not covered by a registered v0.2 gate set",
    ),
    2: (
        {"rc_version": "0.2.0rc1"},
        "C's version 0.2.0rc1 is not the candidate's version 0.2.0 (ADR 0042 D4)",
    ),
    3: (
        {"files": {"ledger": ledger({gate: "PASS" for gate in CLAIMED} | {"W25": None})}},
        "W25: no verdict in the ledger (D2.1)",
    ),
    4: (
        {
            "files": {
                "ledger": ledger({gate: "PASS" for gate in CLAIMED} | {"W26": "BLOCKED"}),
                "verdicts": document(ALL_PASS | {"W26": ("BLOCKED", "W26 (b): CI run", "—")}),
            }
        },
        "W26: BLOCKED blocks the tag (D2.2)",
    ),
    5: (
        {
            "files": {
                "ledger": ledger({gate: "PASS" for gate in CLAIMED} | {"W23": "FAIL"}),
                "verdicts": document(ALL_PASS | {"W23": ("FAIL", "W23 (d)", "—")}),
            }
        },
        "W23: FAIL clause not accepted in ADR 0042 D3: ['W23 (d)'] (D2.3)",
    ),
    6: (
        {"differences": ["src/openflowsheet/x.py"]},
        "candidate dddddddddddd differs from C in ['src/openflowsheet/x.py'] (D2.4)",
    ),
    7: (
        {"files": {"rc_record": rc_record(STEP_15)}},
        f"§8.2 step 15 (A15, CI): failed in {RC_RECORD}",
        f"§8.2 step 15: no row of {RC_RECORD} states that it passed",
    ),
    8: (
        {"files": {"m07": manifest("M07", RC, "planned")}},
        f"{M07_MANIFEST} has status 'planned', not `tested`",
    ),
    9: (
        {"files": {"m05": None}},
        "no `tested` or `reviewed` M05 manifest at C or an ancestor of C "
        "(evidence/M05/<c>/manifest.json)",
    ),
    10: (
        {"files": {"envelope": envelope(envelope_id="v0.2-envelope-dev")}},
        f"{ENVELOPE}: envelope_id 'v0.2-envelope-dev', not 'v0.2-envelope-1'",
    ),
    11: (
        {"files": {"adr_0042": adr_0042(answers={"M03 N1": "pending"})}},
        "Frank's answer to M03 N1 is not an acceptance of the default; "
        "amend the alpha specification for it",
    ),
    12: (
        {"files": {"adr_0039": adr("**Status:** Proposed, 2026-10-14")}},
        "ADR 0039 is not Accepted: **Status:** Proposed, 2026-10-14",
    ),
}


def test_a34_the_yes_fixture() -> None:
    result = report()
    assert result["reasons"] == [] and result["tag_may_be_proposed"] is True


@pytest.mark.parametrize("item", sorted(NO))
def test_a34_each_item_refuses_alone(item: int) -> None:
    state, *reasons = NO[item]
    result = report(
        files(**state.get("files", {})),
        version=state.get("version", VERSION),
        rc_version=state.get("rc_version"),
        differences=state.get("differences"),
    )
    assert result["tag_may_be_proposed"] is False
    assert result["reasons"] == reasons


# -- M07.A35: W24 blocked on M03 N1; an unlisted FAIL; an early acceptance --------------------


def _with(gate: str, verdict: str, failing: str, **overrides: str | None) -> dict[str, Any]:
    return report(
        files(
            ledger=ledger({gate_: "PASS" for gate_ in CLAIMED} | {gate: verdict}),
            verdicts=document(ALL_PASS | {gate: (verdict, failing, "—")}),
            **overrides,
        )
    )


def test_a35_w24_blocked_on_m03_n1_blocks_the_tag() -> None:
    result = _with("W24", "BLOCKED", "W24 (a): M03 N1, Frank's answer on the nlp extra")
    assert result["reasons"] == ["W24: BLOCKED blocks the tag (D2.2)"]
    (w24,) = [entry for entry in result["gates"] if entry["gate"] == "W24"]
    assert w24["blocked_clauses"] == ["W24 (a): M03 N1, Frank's answer on the nlp extra"]


def test_a35_a_fail_without_a_d3_row_refuses() -> None:
    result = _with("V14", "FAIL", "V14 (b)", adr_0042=adr_0042(d3=ACCEPTED, clause="V14 (a)"))
    assert result["reasons"] == ["V14: FAIL clause not accepted in ADR 0042 D3: ['V14 (b)'] (D2.3)"]


def test_a35_an_acceptance_dated_before_judged_refuses() -> None:
    result = _with("V14", "FAIL", "V14 (b)", adr_0042=adr_0042(d3="accepted, 2026-11-01"))
    assert result["reasons"] == [
        "V14: V14 (b): accepted 2026-11-01, before the verdict's Judged date 2026-11-02 "
        "(D2.3; ADR 0042 D2)"
    ]


def test_a35_a_fail_accepted_on_the_judged_date_is_printed_fail() -> None:
    result = _with("V14", "FAIL", "V14 (b)", adr_0042=adr_0042(d3=ACCEPTED))
    assert result["tag_may_be_proposed"] is True, result["reasons"]
    output = v0_2_gate.text(result)
    assert f"V14 (b) FAIL, accepted by Frank {JUDGED} (ADR 0042 D3)" in output
    assert re.search(r"^V14  FAIL ", output, flags=re.MULTILINE)


# -- M07.A36: the output ----------------------------------------------------------------------


def test_a36_the_text_report_yes() -> None:
    lines = v0_2_gate.text(report()).splitlines()
    assert lines[0] == f"v0.2 gates ({SET}) at C = {RC}; candidate {CANDIDATE}"
    assert gate_rows("\n".join(lines)) == list(CLAIMED)
    assert len(CLAIMED) == 17
    assert not any("not claimed" in line for line in lines)
    assert "Frank's answers (ADR 0042): every one accepted" in lines
    assert lines[-1] == "v0.2.0 tag may be proposed: YES"


def test_a36_the_text_report_no() -> None:
    refused = report(files(adr_0035=None, envelope=envelope(release="0.2.0rc1")))
    lines = v0_2_gate.text(refused).splitlines()
    assert len(refused["reasons"]) == 2
    assert lines[-1] == "v0.2.0 tag may be proposed: NO (2 reasons)"
    assert lines[-3:-1] == [f"  - {reason}" for reason in refused["reasons"]]


def test_a36_markdown_has_17_rows_none_unclaimed() -> None:
    table = v0_2_gate.markdown(report()).splitlines()
    assert len(table) == 2 + 17
    assert [row.split(" | ")[0].lstrip("| ") for row in table[2:]] == list(CLAIMED)
    assert not any("not claimed" in row for row in table)


# -- obligation O3 (R-457): the V17 carry names every link of the surface chain ---------------


def test_o3_the_real_links_are_read_as_the_module_defines_them() -> None:
    import m07a_rc  # noqa: PLC0415

    text = (REPO_ROOT / v0_2_gate.LINKS_MODULE).read_text(encoding="utf-8")
    assert v0_2_gate.link_registers(text) == tuple(link.register for link in m07a_rc.LINKS)
    assert v0_2_gate.link_registers(LINKS_TEXT) == ("R-192", "R-234", "R-295")
    assert V02.links_item == "V17 carry" and ALPHA.links_item is None


@pytest.mark.parametrize(
    "default",
    [
        "carry v0.1's paid evidence across R-192 and R-234",
        "carry across R-192, R-234 and R-2950",
        "carry across R-192, R-234 and AR-295",
    ],
)
def test_o3_a_v17_carry_that_does_not_name_a_link_refuses(default: str) -> None:
    result = report(files(adr_0042=adr_0042(v17_default=default)))
    assert result["reasons"] == ["V17 carry does not name R-295"]
    assert result["frank_problems"] == ["V17 carry does not name R-295"]


def test_o3_the_register_may_be_named_in_any_cell_of_the_row() -> None:
    answers = {"V17 carry": f"accepted, {JUDGED}; carries `R-192`, `R-234`, `R-295`"}
    result = report(files(adr_0042=adr_0042(v17_default="carry", answers=answers)))
    assert result["reasons"] == []


def test_o3_unreadable_links_refuse() -> None:
    missing = report(files(links=None))
    assert missing["reasons"] == [
        "scripts/m07a_rc.py does not exist at the candidate: V17 carry's links cannot be read"
    ]
    unlinked = report(files(links=f"# {MARK}\nLINKS = ()\n"))
    assert unlinked["reasons"] == [
        "V17 carry: scripts/m07a_rc.py has no `LINKS = (Link(name, register, …), …)`"
    ]


def test_o3_no_v17_carry_row_is_policy_s_refusal_alone() -> None:
    result = report(files(adr_0042=adr_0042(answers={"V17 carry": None})))
    assert result["reasons"] == [f"Frank's answer to V17 carry: no row 'V17 carry' in {ADR_0042}"]


# -- end to end: `main` on a scratch repository -------------------------------------------------


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, changes: dict[str, str], message: str) -> str:
    for name, content in changes.items():
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
    return repo


def _build_scratch(repo: Path) -> tuple[str, str]:
    """A package commit P (the six packages' manifests name it), `C` at 0.2.0 with the D2.4
    files, and a candidate that adds every record after `C`."""
    package = _commit(repo, {"docs/package.md": f"{MARK}\n"}, "package")
    rc = _commit(
        repo,
        {
            "pyproject.toml": '[project]\nname = "p"\nversion = "0.2.0"\n',
            "src/openflowsheet/__init__.py": '__version__ = "0.2.0"\n',
            ENVELOPE: envelope(),
        },
        "C",
    )
    records = files()
    records[VERDICTS] = document(ALL_PASS, rc=rc)
    records[RC_RECORD] = rc_record(commit=rc)
    records.pop(M07_MANIFEST)
    records[f"evidence/M07/{rc}/manifest.json"] = manifest("M07", rc)
    for name, at in PACKAGE_AT.items():
        records.pop(f"evidence/{name}/{at}/manifest.json")
        records[f"evidence/{name}/{package}/manifest.json"] = manifest(name, package)
    records.pop(ENVELOPE)
    candidate = _commit(repo, records, "records")
    return rc, candidate


def test_a36_main_on_a_scratch_repository(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, candidate = _build_scratch(scratch)
    code = v0_2_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 0, out
    assert out.splitlines()[0] == f"v0.2 gates ({SET}) at C = {rc}; candidate {candidate}"
    assert out.splitlines()[-1] == "v0.2.0 tag may be proposed: YES"
    _commit(scratch, {"docs/adr/0039-test-input.md": adr("**Status:** Proposed")}, "proposed")
    code = v0_2_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 1
    assert out.splitlines()[-1] == "v0.2.0 tag may be proposed: NO (1 reasons)"


# -- M07.A37: the W27 carry from C_W to C (RC step 17, spec §9) -------------------------------

W27_MEMBERS = GATE["w27_carry"]
SURFACE = {
    "served_tool_list_sha256": "6c" * 32,
    "list_models": {"models": [{"id": "pfr-c1"}, {"id": "cstr"}]},
    "coverage_rows": [["V11", "pfr-c1", "covered"], ["W27", "cstr", "covered"]],
}


def test_a37_an_equal_triple_carries() -> None:
    assert W27_MEMBERS == ["served_tool_list_sha256", "list_models", "coverage_rows"]
    carry = v0_2_gate.w27_carry(SURFACE, json.loads(json.dumps(SURFACE)), W27_MEMBERS)
    assert carry == v0_2_gate.Carry(True)
    assert carry.line(17, "the W27 campaign") == "RC step 17: the W27 campaign carried"


@pytest.mark.parametrize("member", W27_MEMBERS)
def test_a37_any_member_different_fails_step_17(member: str) -> None:
    at_c = SURFACE | {member: "changed"}
    carry = v0_2_gate.w27_carry(SURFACE, at_c, W27_MEMBERS)
    assert carry == v0_2_gate.Carry(
        False, "W27 campaign surface differs between C_W and C", (member,)
    )
    assert carry.line(17, "the W27 campaign") == (
        f"RC step 17: W27 campaign surface differs between C_W and C (differs: {member})"
    )
    missing = {key: value for key, value in SURFACE.items() if key != member}
    for at_cw, at_c in ((missing, SURFACE), (SURFACE, missing)):
        assert v0_2_gate.w27_carry(at_cw, at_c, W27_MEMBERS) == v0_2_gate.Carry(
            False, "W27 campaign surface differs between C_W and C", (member,)
        )


def test_a37_the_command_line(
    scratch: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _commit(scratch, {"docs/c.md": f"{MARK}\n"}, "C")
    at_cw, at_c = tmp_path / "cw.json", tmp_path / "c.json"
    at_cw.write_text(json.dumps(SURFACE), "utf-8")
    at_c.write_text(json.dumps(SURFACE), "utf-8")
    assert v0_2_gate.main(["--rc", rc, "--carry-w27", str(at_cw), str(at_c)]) == 0
    assert capsys.readouterr().out == "RC step 17: the W27 campaign carried\n"
    at_c.write_text(json.dumps(SURFACE | {"list_models": {"models": []}}), "utf-8")
    assert v0_2_gate.main(["--rc", rc, "--carry-w27", str(at_cw), str(at_c)]) == 1
    assert capsys.readouterr().out == (
        "RC step 17: W27 campaign surface differs between C_W and C (differs: list_models)\n"
    )


# -- M07.A38: the journey carry from J to C (RC step 15, spec §4.6) ---------------------------

JOURNEY_FILES = {
    "src/openflowsheet/model.py": "X = 1\n",
    "benchmarks/m05/study.json": "{}\n",
    "scripts/m07_journey.py": "# journey\n",
    "benchmarks/m07/registration.json": "{}\n",
}


@pytest.mark.parametrize(
    ("changed", "carried"),
    [
        ({"docs/notes.md": "after J\n"}, True),
        ({"benchmarks/m07/journey/abc/journey.json": "{}\n"}, True),
        ({"src/openflowsheet/model.py": "X = 2\n"}, False),
        ({"benchmarks/m05/study.json": '{"a": 1}\n'}, False),
        ({"scripts/m07_journey.py": "# changed\n"}, False),
        ({"benchmarks/m07/registration.json": '{"b": 2}\n'}, False),
    ],
)
def test_a38_the_journey_carries_iff_its_files_are_equal(
    scratch: Path, changed: dict[str, str], carried: bool
) -> None:
    journey = _commit(scratch, JOURNEY_FILES, "J")
    rc = _commit(scratch, changed, "C")
    carry = v0_2_gate.journey_carry(journey, rc)
    if carried:
        assert carry == v0_2_gate.Carry(True)
    else:
        assert carry == v0_2_gate.Carry(
            False, "step 15 requires a re-run of the journey at C", tuple(changed)
        )


def test_a38_an_unknown_j_and_the_command_line(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    journey = _commit(scratch, JOURNEY_FILES, "J")
    rc = _commit(scratch, {"docs/notes.md": "after J\n"}, "C")
    carry = v0_2_gate.journey_carry("e" * 40, rc)
    assert carry == v0_2_gate.Carry(
        False, "step 15 requires a re-run of the journey at C", (f"{'e' * 40} is not a commit",)
    )
    assert v0_2_gate.main(["--rc", rc, "--carry-journey", journey]) == 0
    assert capsys.readouterr().out == f"RC step 15: the journey at {journey} carried\n"
    rc = _commit(scratch, {"src/openflowsheet/model.py": "X = 3\n"}, "C2")
    assert v0_2_gate.main(["--rc", rc, "--carry-journey", journey]) == 1
    assert capsys.readouterr().out == (
        "RC step 15: step 15 requires a re-run of the journey at C "
        "(differs: src/openflowsheet/model.py)\n"
    )


@pytest.mark.parametrize(
    "options",
    [
        ["--carry-journey", "J", "--carry-w27", "a.json", "b.json"],
        ["--carry-journey", "J", "--json"],
        ["--carry-journey", "J", "--markdown"],
        ["--carry-w27", "a.json", "b.json", "--json"],
        ["--carry-w27", "a.json", "b.json", "--markdown"],
    ],
)
def test_a37_a38_the_carry_options_exclude_each_other_and_the_report_formats(
    options: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec §20 A3.4: no answer is silently dropped; argparse refuses the pair (exit 2)."""
    with pytest.raises(SystemExit) as refused:
        v0_2_gate.main(["--rc", "HEAD", *options])
    assert refused.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
