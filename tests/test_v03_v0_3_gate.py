"""V03.A01–A08 and A16: `scripts/v0_3_gate.py`, the gate set `v0.3-gate-v1` for 0.3.0 (V03 spec §2).

The 0.3 line's gate script runs `scripts/v0_2_gate.py`'s engine with its own registry, line name
and specification texts (§2.2). Its one entry covers 0.3.0, 0.3.0bN and 0.3.0rcN (Table T-V3),
claims V11–V20, W21–W26 and X31, does not claim W27, reads ADR 0053, `docs/reviews/V03-verdicts.md`,
`docs/v03-rc-record.md` (steps 1–17), S13's manifest at `C` and the twenty packages' at ancestors
of `C`. The decision items are the alpha's §7.3 items 1–12 with this entry's values; each has its
own refusing state here on an otherwise passing fixture, so a dropped rule fails its own test. The
v0.2 engine's own behaviour (V03.A03) is held by `tests/test_m07_v0_2_gate.py` and
`tests/test_m07a_v0_2_gate.py`, and A10's pairs (V03.A04) by the first of them; here are the
controls that make those checks bite.

The inputs are of two kinds, and each says which it is:

- **real records**: the specification `docs/derivations/V03-release-spec.md` (its §2.2 table, its
  Table T-V3 and its §8 list, read from the committed text) and the registration
  `benchmarks/v03/registration.json` that transcribes them (WO-1);
- **constructed test inputs**: minimal ledgers, verdict documents, ADR tables, RC records,
  manifests and envelopes, each carrying the marker `MARK` so that none can be mistaken for a
  record.
"""

from __future__ import annotations

import ast
import datetime
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
import test_m07_v0_2_gate as m07  # noqa: E402
import v0_1_gate  # noqa: E402
import v0_2_gate  # noqa: E402
import v0_3_gate  # noqa: E402

SPEC = (REPO_ROOT / "docs" / "derivations" / "V03-release-spec.md").read_text(encoding="utf-8")
REGISTRATION = json.loads(
    (REPO_ROOT / "benchmarks" / "v03" / "registration.json").read_text(encoding="utf-8")
)
SET = "v0.3-gate-v1"
(V03,) = v0_3_gate.GATE_SETS
CLAIMED = V03.claimed

#: Every constructed input carries this, in its own format's comment syntax.
MARK = "TEST INPUT constructed by tests/test_v03_v0_3_gate.py; not a record"

RC = "c" * 40
CANDIDATE = "d" * 40
PACKAGE_AT = {name: f"{index:040x}" for index, name in enumerate(V03.packages, start=1)}
JUDGED = "2026-11-20"
ACCEPTED = f"accepted, {JUDGED}"
VERSION = "0.3.0"
ADR_0053 = "docs/adr/0053-v0.3.0-release-policy.md"
VERDICTS = "docs/reviews/V03-verdicts.md"
RC_RECORD = "docs/v03-rc-record.md"
ENVELOPE = "benchmarks/t08/support_envelope.yaml"
LEDGER = "docs/requirements.yaml"
S13_MANIFEST = f"evidence/S13/{RC}/manifest.json"


# -- the specification's text, read as committed --------------------------------------------------


def _section(heading: str) -> str:
    """The body of the specification's section `heading` (a `##`/`###` line), up to the next."""
    start = SPEC.index(f"{heading}\n")
    following = re.search(r"^#{2,3} ", SPEC[start + len(heading) + 1 :], flags=re.MULTILINE)
    end = start + len(heading) + 1 + following.start() if following else len(SPEC)
    return SPEC[start:end]


def _registry_table() -> dict[str, list[str]]:
    """§2.2's table: each field to its cell's backticked strings, `\\|` read as `|`."""
    rows: dict[str, list[str]] = {}
    section = _section("### 2.2 Registry entry (the `GateSet` fields of `scripts/v0_2_gate.py`)")
    for line in section.splitlines():
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) == 2 and not cells[0].startswith(("Field", "---")):
            rows[cells[0]] = [
                value.replace("\\|", "|") for value in re.findall(r"`([^`]*)`", cells[1])
            ]
            rows[cells[0] + " (text)"] = [cells[1]]
    return rows


def _gate_range(text: str) -> list[str]:
    """`V11–V20, W21–W26, X31` as its gate ids, in order."""
    gates: list[str] = []
    for part in text.split(", "):
        first, _, last = part.partition("–")
        if not last:
            gates.append(first)
            continue
        prefix = first[0]
        gates += [f"{prefix}{n}" for n in range(int(first[1:]), int(last[1:]) + 1)]
    return gates


def _numbers(text: str) -> list[str]:
    """`1–17 / 18` style cells: the integers and ranges of the text, each as written."""
    return re.findall(r"\d+(?:–\d+)?", text)


# -- constructed inputs ---------------------------------------------------------------------------


def ledger(verdicts: dict[str, str | None]) -> str:
    gates = [
        {"id": gate, "required_evidence": f"req {gate}", "verdict": verdicts.get(gate)}
        for gate in ("G00", *V03.gates)
    ]
    return f"# {MARK}\n" + yaml.safe_dump({"gates": gates}, sort_keys=False)


def document(
    rows: dict[str, tuple[str, str, str]], *, rc: str = RC, rejudged: str | None = None
) -> str:
    """A verdict document in the alpha's §6.3 form; each row is `(verdict, failing,
    travelling)`, in the mapping's order."""
    lines = [
        "# v0.3 — verdicts",
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


def adr_0053(
    *,
    d3: str = "pending",
    clause: str = "X31 (c)",
    answers: dict[str, str | None] | None = None,
) -> str:
    """ADR 0053's two tables, as the gate reads them; an answer `None` leaves out its row."""
    answers = {item: ACCEPTED for item in V03.frank_items} | (answers or {})
    defaults = {item: "d" for item in V03.frank_items} | {
        "V17 carry": "carry v0.1's paid evidence across R-192, R-234 and R-295"
    }
    lines = [
        "# ADR 0053 (test input)",
        "",
        f"<!-- {MARK} -->",
        "",
        "**Status:** **Accepted**, 2026-11-20",
        "",
        "| D3 clause | Evidence | Frank's acceptance | Owner after 0.3.0 |",
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


def envelope(*, envelope_id: str = "v0.3-envelope-1", release: str = VERSION) -> str:
    return f"# {MARK}\n" + yaml.safe_dump(
        {"envelope_id": envelope_id, "release": release, "limitations": [{"id": "L01"}]},
        sort_keys=False,
    )


def rc_record(results: dict[int, list[str]] | None = None, *, commit: str = RC) -> str:
    """An RC record for `commit`: one row per result (by default every step 1–17 `PASS`) and
    step 18's pre-verdict gate run (exit 1)."""
    results = {step: ["PASS (1/1)"] for step in V03.rc_steps} if results is None else results
    lines = [
        "# v0.3 — the release-candidate record at `C`",
        "",
        f"<!-- {MARK} -->",
        "",
        f"- **`C` = `{commit}`** (the candidate).",
        "",
        "| Step | Assertion | Where | Result (as the record says) | Record | sha256 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for step, outcomes in results.items():
        lines += [
            f"| {step} | A{step} | CI | {result} | `r{step}.json` | `ab` |" for result in outcomes
        ]
    lines.append('| 18 | V03.A27 | local | exit 1: "NO (3 reasons)" | `gate.log` | `ef` |')
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
    "adr_0053": ADR_0053,
    "envelope": ENVELOPE,
    "rc_record": RC_RECORD,
    "links": v0_2_gate.LINKS_MODULE,
    "s13": S13_MANIFEST,
    **{name.lower(): f"evidence/{name}/{at}/manifest.json" for name, at in PACKAGE_AT.items()},
    **{
        f"adr_{number}": f"docs/adr/{number}-test-input.md"
        for number in V03.required_adrs
        if number != "0053"
    },
}


def files(**overrides: str | None) -> dict[str, str]:
    """An otherwise passing candidate: path → text. A keyword names a path by its key in
    `PATHS`; `None` removes the file."""
    found: dict[str, str] = {
        LEDGER: ledger({gate: "PASS" for gate in CLAIMED}),
        VERDICTS: document(ALL_PASS),
        ADR_0053: adr_0053(),
        ENVELOPE: envelope(),
        RC_RECORD: rc_record(),
        v0_2_gate.LINKS_MODULE: m07.LINKS_TEXT,
        S13_MANIFEST: manifest("S13", RC),
        **{
            f"evidence/{name}/{at}/manifest.json": manifest(name, at)
            for name, at in PACKAGE_AT.items()
        },
        **{
            f"docs/adr/{number}-test-input.md": adr()
            for number in V03.required_adrs
            if number != "0053"
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
    return v0_3_gate.build(
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
    return re.findall(r"^((?:V1[1-9]|V20|W2[1-9]|X3[0-9]))  ", output, flags=re.MULTILINE)


def test_the_otherwise_passing_fixture_may_be_proposed() -> None:
    result = report()
    assert result["gate_set"] == SET
    assert result["tag_may_be_proposed"], result["reasons"]


# -- V03.A01: the registry is §2.2's and the registration's ---------------------------------------


def _fields(entry: v0_2_gate.GateSet) -> dict[str, Any]:
    return {
        "name": entry.name,
        **m07._fields(entry),
        "specification_texts": list(entry.specification_texts or ()),
    }


def test_a01_the_registry_is_the_registration_s_one_entry() -> None:
    assert len(v0_3_gate.GATE_SETS) == 1
    assert _fields(V03) == REGISTRATION["gate_set"]
    assert (V03.specification, V03.rc_section) == ("the V03 release specification", "§4")
    assert V03.adr == "ADR 0053"
    assert V03.rejudged.pattern.startswith(r"\*\*Re-judged:\*\* ")


def test_a01_the_entry_is_the_specification_s_table() -> None:
    table = _registry_table()
    assert table["covers"] == [V03.covers.pattern]
    assert table["clause"] == [V03.clause.pattern]
    assert table["policy_adr"] == [V03.policy_adr]
    assert table["verdict_document / rc_record"] == [V03.verdict_document, V03.rc_record]
    assert table["envelope_id"] == [V03.envelope_id]
    assert table["frank_items"] == list(V03.frank_items)
    assert table["links_item"] == [V03.links_item]
    assert table["evidence_package"] == [
        V03.evidence_package,
        '("the V03 release specification", "§4")',
    ]
    assert V03.specification_texts == ("the V03 release specification", "§4")
    claimed, not_claimed = table["claimed / not_claimed (text)"][0].split(" (in this order) / ")
    assert _gate_range(claimed) == list(V03.claimed)
    assert _gate_range(not_claimed) == list(V03.not_claimed) == ["W27"]
    (packages,) = table["packages (20) (text)"]
    assert packages.split(", ") == list(V03.packages) and len(V03.packages) == 20
    (adrs,) = table["required_adrs (25) (text)"]
    assert adrs.split(", ") == list(V03.required_adrs) and len(V03.required_adrs) == 25
    (steps,) = table["rc_steps / rc_last_step (text)"]
    assert _numbers(steps) == ["1–17", "18"]
    assert V03.rc_steps == tuple(range(1, 18)) and V03.rc_last_step == 18
    (waits,) = table["rejudge_waits (text)"]
    assert re.findall(r"\((\w+), ([^)]+)\)", waits) == list(V03.rejudge_waits)


# -- V03.A02: Table T-V3 --------------------------------------------------------------------------


def _table_t_v3() -> tuple[list[str], list[str]]:
    rows = [
        line
        for line in _section("### 2.3 Version table T-V3 (V03.A02)").splitlines()
        if line.startswith("| `")
    ]
    (row,) = rows
    covered, uncovered = (re.findall(r"`([^`]*)`", cell) for cell in row.split(" | ")[:2])
    return covered, uncovered


def test_a02_the_registration_is_table_t_v3() -> None:
    covered, uncovered = _table_t_v3()
    assert REGISTRATION["versions"] == [
        *({"version": version, "gate_set": SET} for version in covered),
        *({"version": version, "gate_set": None} for version in uncovered),
    ]
    assert (len(covered), len(uncovered)) == (4, 13)
    assert "0.3.0 " in uncovered


@pytest.mark.parametrize(
    ("version", "gate_set"),
    [(row["version"], row["gate_set"]) for row in REGISTRATION["versions"]],
)
def test_a02_gate_set_of_is_table_t_v3(version: str, gate_set: str | None) -> None:
    found = v0_3_gate.gate_set_of(version)
    assert (found.name if found else None) == gate_set


def test_a02_no_version_is_covered_by_both_lines() -> None:
    versions = [row["version"] for row in REGISTRATION["versions"]]
    versions += [row["version"] for row in m07.GATE["versions"]]
    for version in versions:
        assert v0_3_gate.gate_set_of(version) is None or v0_2_gate.gate_set_of(version) is None
    assert v0_2_gate.gate_set_of("0.2.0") is not None
    assert v0_2_gate.gate_set_of("0.2.0rc1") is not None
    assert v0_2_gate.gate_set_of("0.3.0") is None


def test_a02_a_version_two_sets_cover_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v0_3_gate, "GATE_SETS", (V03, V03))
    with pytest.raises(ValueError, match="covered by 2 gate sets, not 1"):
        v0_3_gate.gate_set_of(VERSION)


# -- V03.A03: the v0.2 engine keeps v0.2's defaults ------------------------------------------------


def test_a03_the_v0_2_line_is_the_default() -> None:
    assert [entry.name for entry in v0_2_gate.GATE_SETS] == ["v0.2-alpha-gate-v1", "v0.2-gate-v1"]
    assert all(entry.specification_texts is None for entry in v0_2_gate.GATE_SETS)
    assert v0_2_gate.not_covered("0.3.0") == (
        "version 0.3.0 is not covered by a registered v0.2 gate set"
    )
    assert v0_3_gate.not_covered("0.2.0") == (
        "version 0.2.0 is not covered by a registered v0.3 gate set"
    )
    first = v0_2_gate.text(m07.report()).splitlines()[0]
    assert first == f"v0.2 gates (v0.2-gate-v1) at C = {m07.RC}; candidate {m07.CANDIDATE}"


# -- V03.A04: A10's pairs, and a control that swaps them -------------------------------------------


def _alpha_tests_with(pairs: tuple[tuple[str, str], ...]) -> str:
    """The alpha's gate test as committed, with `test_a10_…`'s loop tuple replaced by `pairs`."""
    source = (REPO_ROOT / m07.ALPHA_TESTS).read_text(encoding="utf-8")
    _, loop = m07._a10(source)
    lines = source.splitlines(keepends=True)
    start, end = loop.iter.lineno - 1, loop.iter.end_lineno or loop.iter.lineno
    replacement = "(" + ", ".join(repr(pair) for pair in pairs) + "):\n"
    head = lines[start][: loop.iter.col_offset]
    return "".join([*lines[:start], head + replacement, *lines[end:]])


def _a31_b_holds(source: str) -> bool:
    """`test_a31_b_test_a10_…`'s comparison, applied to `source` as the alpha's test."""
    tagged_def, tagged_for = m07._a10(m07._tagged_alpha_tests())
    now_def, now_for = m07._a10(source)
    if ast.literal_eval(now_for.iter) != (
        ast.literal_eval(tagged_for.iter) + m07.A10_PINS_0_2_0 + m07.A10_PINS_0_3_0
    ):
        return False
    now_for.iter = tagged_for.iter
    return ast.dump(now_def) == ast.dump(tagged_def)


def test_a04_the_pairs_are_the_specification_s() -> None:
    assert m07.A10_PINS_0_3_0 == (
        ("envelope_id: v0.3-envelope-1\n", "envelope_id: v0.2-envelope-dev\n"),
        ("release: 0.3.0\n", "release: 0.2.0.dev0\n"),
    )
    assert m07.ALPHA_TESTS_EDITED[-1] == "test_a10_the_envelope_must_be_pinned_to_the_alpha"
    assert len(m07.ALPHA_TESTS_EDITED) == 4


def test_a04_the_committed_test_holds_and_a_swap_fails() -> None:
    _, loop = m07._a10((REPO_ROOT / m07.ALPHA_TESTS).read_text(encoding="utf-8"))
    pairs = ast.literal_eval(loop.iter)
    assert _a31_b_holds(_alpha_tests_with(pairs))
    tagged = pairs[: len(pairs) - 4]
    swapped = tagged + m07.A10_PINS_0_3_0 + m07.A10_PINS_0_2_0
    assert not _a31_b_holds(_alpha_tests_with(swapped))
    assert not _a31_b_holds(_alpha_tests_with(tagged + m07.A10_PINS_0_2_0))


def test_a04_the_pairs_undo_a_0_3_0_pin() -> None:
    """At K3 the envelope reads `v0.3-envelope-1` / `0.3.0`; the pairs return it to the token."""
    _, loop = m07._a10((REPO_ROOT / m07.ALPHA_TESTS).read_text(encoding="utf-8"))
    pinned = envelope().replace(f"# {MARK}\n", "")
    for old, new in ast.literal_eval(loop.iter):
        pinned = pinned.replace(old, new, 1)
    assert yaml.safe_load(pinned) | {"limitations": []} == {
        "envelope_id": "v0.2-envelope-dev",
        "release": "0.2.0.dev0",
        "limitations": [],
    }


# -- V03.A05: the clause grammar ------------------------------------------------------------------

V03_ONLY = ["X31 (c)"]
BOTH = ["V11 (a)", "V20 (c)", "W21 (f)", "W26 (b)"]
V02_ONLY = ["W27 (a)"]
NEITHER = ["W28 (a)", "V10 (a)", "X32 (a)", "X31 (A)"]


@pytest.mark.parametrize(
    ("label", "in_v03", "in_v02"),
    [(label, True, False) for label in V03_ONLY]
    + [(label, True, True) for label in BOTH]
    + [(label, False, True) for label in V02_ONLY]
    + [(label, False, False) for label in NEITHER],
)
def test_a05_the_clause_grammars(label: str, in_v03: bool, in_v02: bool) -> None:
    assert bool(V03.clause.fullmatch(label)) is in_v03
    assert bool(m07.V02.clause.fullmatch(label)) is in_v02


def test_a05_the_counts_are_the_specification_s() -> None:
    parse = [label for label in (*V03_ONLY, *BOTH) if V03.clause.fullmatch(label)]
    refuse = [label for label in (*V02_ONLY, *NEITHER) if not V03.clause.fullmatch(label)]
    assert (len(parse), len(refuse)) == (5, 5)
    assert [label for label in ("X31 (c)", "W27 (a)") if m07.V02.clause.fullmatch(label)] == [
        "W27 (a)"
    ]


def test_a05_a_re_judgement_may_list_w24_and_not_x31() -> None:
    line = f"**Re-judged:** {JUDGED} (V17, W24)"
    parsed = v0_2_gate.verdict_document(document(ALL_PASS, rejudged=line), V03, RC)
    assert parsed.rejudged is not None and parsed.rejudged.gates == ("V17", "W24")
    with pytest.raises(ValueError, match="not blocked on a registered answer"):
        line = f"**Re-judged:** {JUDGED} (X31)"
        v0_2_gate.verdict_document(document(ALL_PASS, rejudged=line), V03, RC)


# -- V03.A06: decision items 1–12 -----------------------------------------------------------------

STEP_15 = {step: ["PASS (1/1)"] for step in V03.rc_steps} | {15: ["FAIL (re-run required)"]}
NO = {
    # R-922 admits 0.3.0.postN as a post-release of 0.3.0 (tests/test_v03_post_release.py), so
    # item 1's uncovered version is another of Table T-V3's.
    1: (
        {"version": "0.3.1"},
        "version 0.3.1 is not covered by a registered v0.3 gate set",
    ),
    2: (
        {"rc_version": "0.3.0rc1"},
        "C's version 0.3.0rc1 is not the candidate's version 0.3.0 (ADR 0053 D4)",
    ),
    3: (
        {"files": {"ledger": ledger({gate: "PASS" for gate in CLAIMED} | {"X31": None})}},
        "X31: no verdict in the ledger (D2.1)",
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
                "ledger": ledger({gate: "PASS" for gate in CLAIMED} | {"X31": "FAIL"}),
                "verdicts": document(ALL_PASS | {"X31": ("FAIL", "X31 (c)", "—")}),
            }
        },
        "X31: FAIL clause not accepted in ADR 0053 D3: ['X31 (c)'] (D2.3)",
    ),
    6: (
        {"differences": ["src/openflowsheet/x.py"]},
        "candidate dddddddddddd differs from C in ['src/openflowsheet/x.py'] (D2.4)",
    ),
    7: (
        {"files": {"rc_record": rc_record(STEP_15)}},
        f"§4 step 15 (A15, CI): failed in {RC_RECORD}",
        f"§4 step 15: no row of {RC_RECORD} states that it passed",
    ),
    8: (
        {"files": {"s13": manifest("S13", RC, "planned")}},
        f"{S13_MANIFEST} has status 'planned', not `tested`",
    ),
    9: (
        {"files": {"s10c": None}},
        "no `tested` or `reviewed` S10c manifest at C or an ancestor of C "
        "(evidence/S10c/<c>/manifest.json)",
    ),
    10: (
        {"files": {"envelope": envelope(envelope_id="v0.2-envelope-dev")}},
        f"{ENVELOPE}: envelope_id 'v0.2-envelope-dev', not 'v0.3-envelope-1'",
    ),
    11: (
        {"files": {"adr_0053": adr_0053(answers={"M03 N1": "pending"})}},
        "Frank's answer to M03 N1 is not an acceptance of the default; "
        "amend the V03 release specification for it",
    ),
    12: (
        {"files": {"adr_0052": adr("**Status:** Proposed, 2026-10-28")}},
        "ADR 0052 is not Accepted: **Status:** Proposed, 2026-10-28",
    ),
}


def test_a06_the_yes_fixture() -> None:
    result = report()
    assert result["reasons"] == [] and result["tag_may_be_proposed"] is True


@pytest.mark.parametrize("item", sorted(NO))
def test_a06_each_item_refuses_alone(item: int) -> None:
    state, *reasons = NO[item]
    result = report(
        files(**state.get("files", {})),
        version=state.get("version", VERSION),
        rc_version=state.get("rc_version"),
        differences=state.get("differences"),
    )
    assert result["tag_may_be_proposed"] is False
    assert result["reasons"] == reasons


def test_a06_twelve_items() -> None:
    assert sorted(NO) == list(range(1, 13))


# -- V03.A07: X31 FAIL (c) and its D3 row; a W27 row is malformed ---------------------------------


def _x31_fail(**overrides: str | None) -> dict[str, Any]:
    return report(
        files(
            ledger=ledger({gate: "PASS" for gate in CLAIMED} | {"X31": "FAIL"}),
            verdicts=document(ALL_PASS | {"X31": ("FAIL", "X31 (c)", "—")}),
            **overrides,
        )
    )


def test_a07_x31_fail_c_without_a_d3_row_refuses() -> None:
    result = _x31_fail(adr_0053=adr_0053(d3=ACCEPTED, clause="X31 (a)"))
    assert result["reasons"] == ["X31: FAIL clause not accepted in ADR 0053 D3: ['X31 (c)'] (D2.3)"]


def test_a07_x31_fail_c_accepted_on_judged_may_be_proposed() -> None:
    result = _x31_fail(adr_0053=adr_0053(d3=ACCEPTED))
    assert result["tag_may_be_proposed"] is True, result["reasons"]
    output = v0_3_gate.text(result)
    assert f"X31 (c) FAIL, accepted by Frank {JUDGED} (ADR 0053 D3)" in output
    assert re.search(r"^X31  FAIL ", output, flags=re.MULTILINE)


def test_a07_x31_fail_c_accepted_the_day_before_refuses() -> None:
    before = (datetime.date.fromisoformat(JUDGED) - datetime.timedelta(days=1)).isoformat()
    result = _x31_fail(adr_0053=adr_0053(d3=f"accepted, {before}"))
    assert result["reasons"] == [
        f"X31: X31 (c): accepted {before}, before the verdict's Judged date {JUDGED} "
        "(D2.3; ADR 0053 D2)"
    ]


def test_a07_a_w27_row_is_a_malformed_document() -> None:
    rows = ALL_PASS | {"W27": ("PASS", "—", "—")}
    with pytest.raises(ValueError, match=r"rows for gates v0\.3-gate-v1 does not claim: \['W27'\]"):
        report(files(verdicts=document(rows)))


# -- V03.A08: the output --------------------------------------------------------------------------


def test_a08_the_text_report_yes() -> None:
    lines = v0_3_gate.text(report()).splitlines()
    assert lines[0] == f"v0.3 gates ({SET}) at C = {RC}; candidate {CANDIDATE}"
    assert gate_rows("\n".join(lines)) == [*CLAIMED, "W27"]
    assert len(CLAIMED) == 17
    assert [line for line in lines if "not claimed" in line] == [f"W27  not claimed ({SET})"]
    assert lines.index(f"W27  not claimed ({SET})") > max(
        index for index, line in enumerate(lines) if line.startswith("X31  ")
    )
    assert "Frank's answers (ADR 0053): every one accepted" in lines
    assert lines[-1] == "v0.3.0 tag may be proposed: YES"


def test_a08_the_text_report_no() -> None:
    refused = report(files(adr_0050=None, envelope=envelope(release="0.3.0rc1")))
    lines = v0_3_gate.text(refused).splitlines()
    assert len(refused["reasons"]) == 2
    assert lines[-1] == "v0.3.0 tag may be proposed: NO (2 reasons)"
    assert lines[-3:-1] == [f"  - {reason}" for reason in refused["reasons"]]


def test_a08_the_uncovered_text() -> None:
    lines = v0_3_gate.text(report(version="0.3.1")).splitlines()
    assert lines == [
        "version 0.3.1 is not covered by a registered v0.3 gate set",
        "v0.3.1 tag may be proposed: NO (1 reasons)",
    ]


def test_a08_markdown_has_18_rows_w27_unclaimed() -> None:
    table = v0_3_gate.markdown(report()).splitlines()
    assert len(table) == 2 + 18
    assert [row.split(" | ")[0].lstrip("| ") for row in table[2:]] == [*CLAIMED, "W27"]
    assert table[-1] == "| W27 | not claimed | req W27 | — |"


# -- end to end: `main` on a scratch repository ---------------------------------------------------


@pytest.fixture
def scratch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    m07._git(repo, "init", "-q")
    monkeypatch.setattr(v0_1_gate, "ROOT", repo)
    return repo


def _build_scratch(repo: Path) -> tuple[str, str, dict[str, str]]:
    """A package commit P (the twenty packages' manifests name it), `C` at 0.3.0 with the D2.4
    files, and a candidate that adds every record after `C`."""
    package = m07._commit(repo, {"docs/package.md": f"{MARK}\n"}, "package")
    rc = m07._commit(
        repo,
        {
            "pyproject.toml": '[project]\nname = "p"\nversion = "0.3.0"\n',
            "src/openflowsheet/__init__.py": '__version__ = "0.3.0"\n',
            ENVELOPE: envelope(),
        },
        "C",
    )
    records = files()
    records[VERDICTS] = document(ALL_PASS, rc=rc)
    records[RC_RECORD] = rc_record(commit=rc)
    records.pop(S13_MANIFEST)
    records[f"evidence/S13/{rc}/manifest.json"] = manifest("S13", rc)
    for name, at in PACKAGE_AT.items():
        records.pop(f"evidence/{name}/{at}/manifest.json")
        records[f"evidence/{name}/{package}/manifest.json"] = manifest(name, package)
    records.pop(ENVELOPE)
    candidate = m07._commit(repo, records, "records")
    return rc, candidate, records


def test_a08_main_on_a_scratch_repository(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, candidate, _ = _build_scratch(scratch)
    code = v0_3_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 0, out
    assert out.splitlines()[0] == f"v0.3 gates ({SET}) at C = {rc}; candidate {candidate}"
    assert out.splitlines()[-1] == "v0.3.0 tag may be proposed: YES"
    m07._commit(scratch, {"docs/adr/0046-test-input.md": adr("**Status:** Proposed")}, "proposed")
    code = v0_3_gate.main(["--rc", rc])
    out = capsys.readouterr().out
    assert code == 1
    assert out.splitlines()[-1] == "v0.3.0 tag may be proposed: NO (1 reasons)"


def test_a07_main_exits_2_on_a_w27_row(scratch: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, _, _ = _build_scratch(scratch)
    rows = ALL_PASS | {"W27": ("PASS", "—", "—")}
    m07._commit(scratch, {VERDICTS: document(rows, rc=rc)}, "a W27 row")
    assert v0_3_gate.main(["--rc", rc]) == 2
    assert "rows for gates v0.3-gate-v1 does not claim: ['W27']" in capsys.readouterr().err


def test_a08_the_v0_2_script_refuses_a_0_3_0_candidate(
    scratch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, _, _ = _build_scratch(scratch)
    assert v0_2_gate.main(["--rc", rc]) == 1
    assert capsys.readouterr().out == (
        "version 0.3.0 is not covered by a registered v0.2 gate set\n"
        "v0.3.0 tag may be proposed: NO (1 reasons)\n"
    )


def test_a08_the_command_line_names_the_line() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "v0_3_gate.py"), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "The v0.3 gate report" in result.stdout


# -- V03.A16: the release notes' phrases ----------------------------------------------------------


def test_a16_the_registration_s_phrases_are_the_specification_s() -> None:
    section = _section('## 8. Release notes: `CHANGELOG.md` `## v0.3.0`, "What it is not"')
    phrases = re.findall(r"^\d+\. `([^`]+)`$", section, flags=re.MULTILINE)
    assert len(phrases) == 17
    assert REGISTRATION["changelog_what_it_is_not"] == phrases
    assert "no equilibrium-stage subsystem" not in phrases


def test_the_registration_s_other_transcriptions() -> None:
    """§4's step table (18 rows, its assertions) and §9.1's ship set, as registered."""
    steps = REGISTRATION["rc_steps"]
    assert [row["step"] for row in steps] == list(range(1, 19))
    assert {row["step"]: row["assertion"] for row in steps if row["assertion"] != "V03.A20"} == {
        15: "V03.A21",
        17: "V03.A22",
        18: "V03.A27",
    }
    ship = REGISTRATION["ship_set"]
    assert ship["ships"] == [
        "benchmarks/s10/records.yaml",
        "benchmarks/s10/vle/kurihara1993_binaries.csv",
    ]
    for path in (*ship["ships"], *ship["repository_only"]):
        assert (REPO_ROOT / path).is_file(), path
    assert len(ship["repository_only"]) == 10
