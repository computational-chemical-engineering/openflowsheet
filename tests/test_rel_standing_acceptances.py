"""REL.A06–A10 and RP.S07: the standing acceptances of `scripts/release_gate.py` (RP §8).

The standing release procedure (RP, `docs/derivations/release-procedure.md`) §8; ADR 0055 D3 and
§10. A row of `release/acceptances.md` stands at `C` iff its answer cell passes the cell rule and
its scope, evaluated at `C` by RP §8.2, has the recorded fingerprint (§8.3); a lapsed row counts as
absent; a new row (`Accepted at` = `C`) is dated on or after `Judged` (a failure clause) or the
lapse report (a decision item), §8.4.

The inputs are of two kinds, and each says which it is:

- **real records**: the committed 0.4 line file and `release/acceptances.md`'s scopes; and, in
  `test_the_seed_fingerprints_recompute_at_a3e508e3`, the repository at `a3e508e3`, against the
  fingerprints and term hashes the design lane computed with its own implementation (the
  independent expectation of RP §15 Q-9);
- **constructed test inputs**: the trees at `C` and at an earlier `Accepted at`, held in memory,
  and V03.A06's constructed ledgers, verdict documents, RC records, manifests and envelopes
  (`tests/test_v03_v0_3_gate.py`), with the 0.4 line's paths.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
import test_m07_v0_2_gate as m07
import test_v03_v0_3_gate as v03
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import release_gate  # noqa: E402
import v0_2_gate  # noqa: E402

MARK = "TEST INPUT constructed by tests/test_rel_standing_acceptances.py; not a record"
RC = v03.RC
OLD = "a" * 40  # the seed's `Accepted at`: an earlier C
CANDIDATE = v03.CANDIDATE
JUDGED = v03.JUDGED
LAPSED_ON = "2026-11-10"  # the lapse report's date, before `Judged` (RP §8.5)
EARLY = "2026-10-30"  # a standing row's date, before both
VERSION = "0.4.0"


def _read(path: str) -> bytes | None:
    file = REPO_ROOT / path
    return file.read_bytes() if file.is_file() else None


LINE = release_gate.load_line("0.4", _read)
SET = LINE.gate_set
SEEDED = release_gate.standing_acceptances(
    (REPO_ROOT / "release" / "acceptances.md").read_text("utf-8"), "release/acceptances.md"
)
assert SEEDED is not None
SCOPE = {row.item: row.scope for row in (*SEEDED.failures, *SEEDED.decisions)}
VERDICTS = SET.verdict_document
LAPSES = f"evidence/REL040/{RC}/acceptance-lapses.txt"


# -- the trees ------------------------------------------------------------------------------------


def _blob(content: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()


class Trees:
    """`release_gate.Trees` over in-memory commits: commit → path → content."""

    def __init__(self, commits: Mapping[str, Mapping[str, bytes]]) -> None:
        self.commits = commits

    def entries(self, commit: str) -> tuple[bytes, ...] | None:
        if commit not in self.commits:
            return None
        return tuple(
            f"100644 blob {_blob(content)}\t{path}".encode()
            for path, content in self.commits[commit].items()
        )

    def read(self, commit: str, path: str) -> bytes | None:
        return self.commits.get(commit, {}).get(path)


def pyproject(
    version: str = VERSION, nlp: tuple[str, ...] = ("cyipopt==1.7.0", "pyomo==6.10.1")
) -> bytes:
    extras = {
        "nlp": list(nlp),
        "coolprop": ["CoolProp==8.0.0"],
        "lca": ["bw2calc==2.5.0", "bw2data==4.7"],
    }
    lines = [f"# {MARK}", "[project]", 'name = "openflowsheet"', f'version = "{version}"', ""]
    lines.append("[project.optional-dependencies]")
    lines += [f"{name} = {json.dumps(requirements)}" for name, requirements in extras.items()]
    return ("\n".join(lines) + "\n").encode()


def surface(digest: str = "45" * 32) -> bytes:
    chain = [
        {"item": 1, "link": "c_3", "found": digest, "expected": digest},
        {"item": 2, "link": "c_3", "found": "38" * 32},
    ]
    record = {"_comment": MARK, "format": "t08-rc-v1", "step": "surface-alpha", "chain": chain}
    return json.dumps(record).encode()


def rc_records(base: str, *names: str) -> dict[str, bytes]:
    files = [{"path": "a30.log"}, *({"path": name} for name in names)]
    return {
        f"{base}/records.json": json.dumps({"_comment": MARK, "files": files}).encode(),
        f"{base}/a30.log": b"log\n",
    }


TREE = {
    path: f"{MARK}: {path}\n".encode()
    for path in (
        "src/openflowsheet/__init__.py",
        "src/openflowsheet/adapters/external/reactor.py",
        "src/openflowsheet/core/state.py",
        "benchmarks/t08/ptc_r1/r.json",
        "docs/reviews/T08-verdict-V14b.md",
        "docs/reviews/S09-verdicts.md",
        "benchmarks/s03/a.json",
        "benchmarks/s09/b.json",
        "docs/m03-ipopt-audit.md",
        "benchmarks/m03/ipopt-inventory-1.json",
        "scripts/build-m03-ipopt-env.sh",
        "requirements-coolprop.lock",
        "docs/s07-coolprop-licences.json",
        "benchmarks/e01/brightway/lca-pip.lock",
        "docs/e01-lca-licences.json",
    )
} | {"pyproject.toml": pyproject(), v0_2_gate.LINKS_MODULE: m07.LINKS_TEXT.encode()}
#: The candidate's tree: the step-8 records at `OLD` (0.3's package, S13) and at `C` (REL040).
CANDIDATE_TREE = {
    **rc_records(f"evidence/S13/{OLD}/rc", "surface/s.json"),
    f"evidence/S13/{OLD}/rc/surface/s.json": surface(),
    **rc_records(f"evidence/REL040/{RC}/rc", "surface/s.json", "ci/surface/s.json"),
    f"evidence/REL040/{RC}/rc/surface/s.json": surface(),
    f"evidence/REL040/{RC}/rc/ci/surface/s.json": surface(),
}


def trees(at_c: Mapping[str, bytes | None] | None = None, **at_old: bytes) -> Trees:
    """`OLD`'s tree (`TREE` with `at_old`), `C`'s (`TREE` with `at_c`; `None` deletes a path),
    and the candidate's."""
    c = dict(TREE)
    for path, content in (at_c or {}).items():
        if content is None:
            c.pop(path, None)
        else:
            c[path] = content
    old = TREE | {path.replace("__", "/"): content for path, content in at_old.items()}
    return Trees({OLD: old, RC: c, CANDIDATE: CANDIDATE_TREE})


def scopes(tree: Trees) -> release_gate.Scopes:
    return release_gate.Scopes(tree, LINE, RC, CANDIDATE)


# -- the acceptances file -------------------------------------------------------------------------

DEFAULTS = {
    "V17 carry": "carry v17-c2's agent evidence across R-192, R-234 and R-295",
}


def row(
    item: str,
    *,
    date: str = EARLY,
    at: str = OLD,
    tree: Trees | None = None,
    scope: str | None = None,
    cell: str | None = None,
) -> release_gate.Row:
    """A row whose fingerprint is its scope's at `at` in `tree` (default: the unchanged trees)."""
    scope = SCOPE[item] if scope is None else scope
    digest, _ = scopes(tree or trees()).evaluate(scope, at)
    assert digest is not None, (item, at)
    answer = f"accepted, {date} — {MARK}" if cell is None else cell
    return release_gate.Row(item, answer, scope, digest, at)


def acceptances(*rows: release_gate.Row, defaults: Mapping[str, str] = DEFAULTS) -> str:
    """`release/acceptances.md`'s two tables: every decision item of the line with a seeded row
    unless `rows` replaces it, and the failure-clause rows `rows` names."""
    given = {r.item: r for r in rows}
    decisions = [given.get(item) or row(item) for item in SET.frank_items]
    failures = [r for r in rows if r.item not in SET.frank_items]
    lines = [
        "# Standing acceptances (test input)",
        "",
        f"<!-- {MARK} -->",
        "",
        "| D3 clause | Frank's acceptance | Scope | Fingerprint | Accepted at |",
        "| --- | --- | --- | --- | --- |",
        *(
            f"| {r.item} | {r.cell} | `{r.scope}` | `{r.fingerprint}` | `{r.accepted_at}` |"
            for r in failures
        ),
        "",
        "| Frank item | Default | Frank's answer | Scope | Fingerprint | Accepted at |",
        "| --- | --- | --- | --- | --- | --- |",
        *(
            f"| {r.item} | {defaults.get(r.item, 'd')} | {r.cell} | `{r.scope}` | "
            f"`{r.fingerprint}` | "
            f"`{r.accepted_at}` |"
            for r in decisions
        ),
        "",
    ]
    return "\n".join(lines)


X31_FAIL = {
    v03.LEDGER: v03.ledger({gate: "PASS" for gate in v03.CLAIMED} | {"X31": "FAIL"}),
    VERDICTS: v03.document(v03.ALL_PASS | {"X31": ("FAIL", "X31 (c)", "—")}),
}


def files(table: str | None = None, **overrides: str | None) -> dict[str, str]:
    """An otherwise passing 0.4.0 candidate: path → text; `None` removes a path."""
    found = {
        v03.LEDGER: v03.ledger({gate: "PASS" for gate in v03.CLAIMED}),
        VERDICTS: v03.document(v03.ALL_PASS),
        SET.policy_adr: acceptances() if table is None else table,
        v03.ENVELOPE: v03.envelope(envelope_id="v0.4-envelope-1", release=VERSION),
        SET.rc_record: v03.rc_record(),
        v0_2_gate.LINKS_MODULE: m07.LINKS_TEXT,
        f"evidence/REL040/{RC}/manifest.json": v03.manifest("REL040", RC),
        **{
            f"evidence/{name}/{at}/manifest.json": v03.manifest(name, at)
            for name, at in v03.PACKAGE_AT.items()
        },
        **{f"docs/adr/{number}-test-input.md": v03.adr() for number in SET.required_adrs},
        LAPSES: f"acceptance lapses at C = {RC}, {LAPSED_ON}\n",
    }
    for path, value in overrides.items():
        if value is None:
            found.pop(path, None)
        else:
            found[path] = value
    return found


def report(
    candidate_files: dict[str, str] | None = None,
    tree: Trees | None = None,
    *,
    version: str = VERSION,
    rc_version: str | None = None,
    differences: Sequence[str] | None = (),
) -> dict[str, Any]:
    return release_gate.build(
        files=files() if candidate_files is None else candidate_files,
        rc=RC,
        rc_version=version if rc_version is None else rc_version,
        rc_in_repository=True,
        candidate=CANDIDATE,
        version=version,
        differences=None if differences is None else list(differences),
        is_ancestor=lambda commit: commit in v03.ANCESTORS,
        line=LINE,
        scopes=scopes(tree or trees()),
    )


def day_before(date: str) -> str:
    return (datetime.date.fromisoformat(date) - datetime.timedelta(days=1)).isoformat()


def standing_line(item: str, date: str = EARLY, at: str = OLD) -> str:
    return f"standing acceptance {item}: accepted {date} at {at}, scope unchanged"


# -- the base fixture -----------------------------------------------------------------------------


def test_the_otherwise_passing_fixture_may_be_proposed() -> None:
    result = report()
    assert result["reasons"] == [] and result["tag_may_be_proposed"] is True
    assert result["acceptances"] == [standing_line(item) for item in SET.frank_items]
    lines = release_gate.text(result, LINE).splitlines()
    assert lines[0] == f"v0.4 gates (v0.4-gate-v1) at C = {RC}; candidate {CANDIDATE}"
    assert lines[-1] == "v0.4.0 tag may be proposed: YES"
    assert lines[-1 - len(SET.frank_items) : -1] == result["acceptances"]
    assert "Frank's answers (release/acceptances.md): every one accepted" in lines


def test_the_mode_is_the_acceptances_file_s() -> None:
    assert release_gate.standing_acceptances(v03.adr_0053(), "adr") is None
    assert release_gate.standing_acceptances(None, "adr") is None
    assert release_gate.standing_acceptances(acceptances(), "a") is not None


@pytest.mark.parametrize(
    ("old", "new", "why"),
    [
        ("`" + "a" * 40 + "` |\n", "`" + "a" * 39 + "` |\n", "is not a commit id"),
        ("| `paths:src/openflowsheet/adapters", "| paths:src/openflowsheet/adapters", "not one `"),
        ("extract:pyproject_extra:nlp", "extract:nlp", "not a registered extractor"),
    ],
)
def test_a_malformed_standing_table_is_an_error(old: str, new: str, why: str) -> None:
    table = acceptances()
    assert old in table
    with pytest.raises(ValueError, match=re.escape(why)):
        release_gate.standing_acceptances(table.replace(old, new, 1), "a")


# -- REL.A06: a standing row dated before Judged --------------------------------------------------


def test_a06_a_standing_row_dated_before_judged_stands() -> None:
    result = report(files(acceptances(row("X31 (c)")), **X31_FAIL))
    assert result["tag_may_be_proposed"] is True, result["reasons"]
    assert standing_line("X31 (c)") in result["acceptances"]
    output = release_gate.text(result, LINE)
    assert f"X31 (c) FAIL, accepted by Frank {EARLY} (release/acceptances.md D3)" in output
    assert re.search(r"^X31  FAIL ", output, flags=re.MULTILINE)


def test_a06_the_dated_rule_would_refuse_it() -> None:
    """The control: the same date read by the engine's dated rule is before `Judged`."""
    assert datetime.date.fromisoformat(EARLY) < datetime.date.fromisoformat(JUDGED)
    dated = v03.report(
        v03.files(
            ledger=X31_FAIL[v03.LEDGER],
            verdicts=X31_FAIL[VERDICTS],
            adr_0053=v03.adr_0053(d3=f"accepted, {EARLY}"),
        )
    )
    assert dated["reasons"] == [
        f"X31: X31 (c): accepted {EARLY}, before the verdict's Judged date {JUDGED} "
        "(D2.3; ADR 0053 D2)"
    ]


def test_a06_a_row_for_a_clause_that_does_not_fail_is_not_used() -> None:
    result = report(files(acceptances(row("X31 (c)"))))
    assert result["tag_may_be_proposed"] is True
    assert "acceptance X31 (c): not used" in result["acceptances"]


# -- REL.A07: a changed file in a `paths` scope ---------------------------------------------------

REACTOR = "src/openflowsheet/adapters/external/reactor.py"
CHANGED = trees({REACTOR: b"changed\n"})


def test_a07_a_decision_item_s_changed_path_lapses_it() -> None:
    result = report(tree=CHANGED)
    assert result["tag_may_be_proposed"] is False
    assert result["reasons"] == [f"Frank's answer to M02 N1: lapsed ({REACTOR})"]
    assert f"acceptance M02 N1: lapsed ({REACTOR})" in result["acceptances"]


def test_a07_an_added_or_deleted_path_lapses_it() -> None:
    added = "src/openflowsheet/adapters/external/new.py"
    result = report(tree=trees({added: b"new\n"}))
    assert result["reasons"] == [f"Frank's answer to M02 N1: lapsed ({added})"]
    gone = report(tree=trees({REACTOR: None}))
    assert gone["reasons"] == [
        "Frank's answer to M02 N1: unsupported (paths:src/openflowsheet/adapters/external/** "
        f"matches no tracked file at {RC})"
    ]


def test_a07_re_dated_at_c_on_the_lapse_report_s_date() -> None:
    new = row("M02 N1", date=LAPSED_ON, at=RC, tree=CHANGED)
    result = report(files(acceptances(new)), tree=CHANGED)
    assert result["tag_may_be_proposed"] is True, result["reasons"]
    assert standing_line("M02 N1", LAPSED_ON, RC) in result["acceptances"]


def test_s1_a_replacing_row_that_keeps_the_old_accepted_at_is_not_reproduced() -> None:
    """Amendment A-2 (§8.3 (d), review S-1): a row carrying C's fingerprint but the old
    `Accepted at` would stand at C and skip §8.4's date bound; its scope does not reproduce the
    fingerprint at `Accepted at`, so it is `unsupported` and absent. Control: the same row with
    `Accepted at` = C is new, and §8.4's bound judges its date."""
    at_c = row("M02 N1", date=EARLY, at=RC, tree=CHANGED)
    copied = release_gate.Row(at_c.item, at_c.cell, at_c.scope, at_c.fingerprint, OLD)
    result = report(files(acceptances(copied)), tree=CHANGED)
    assert result["reasons"] == [f"Frank's answer to M02 N1: unsupported (not reproduced at {OLD})"]
    assert f"acceptance M02 N1: unsupported (not reproduced at {OLD})" in result["acceptances"]
    control = report(files(acceptances(at_c)), tree=CHANGED)
    assert control["reasons"] == [
        f"Frank's answer to M02 N1: accepted {EARLY}, before the lapse report's date "
        f"{LAPSED_ON} (RP §8.4)"
    ]
    unchanged = release_gate.Row(at_c.item, at_c.cell, at_c.scope, row("M02 N1").fingerprint, OLD)
    assert report(files(acceptances(unchanged)))["tag_may_be_proposed"] is True


def test_a07_re_dated_one_day_earlier_refuses() -> None:
    early = day_before(LAPSED_ON)
    new = row("M02 N1", date=early, at=RC, tree=CHANGED)
    result = report(files(acceptances(new)), tree=CHANGED)
    assert result["reasons"] == [
        f"Frank's answer to M02 N1: accepted {early}, before the lapse report's date "
        f"{LAPSED_ON} (RP §8.4)"
    ]


def test_a07_re_dated_with_no_lapse_report_refuses() -> None:
    new = row("M02 N1", date=LAPSED_ON, at=RC, tree=CHANGED)
    result = report(files(acceptances(new), **{LAPSES: None}), tree=CHANGED)
    assert result["reasons"] == [
        f"Frank's answer to M02 N1: accepted {LAPSED_ON} at C, and there is no lapse report "
        f"{LAPSES} (RP §8.4)"
    ]
    other = files(acceptances(new), **{LAPSES: f"acceptance lapses at C = {OLD}, {LAPSED_ON}\n"})
    assert report(other, tree=CHANGED)["tag_may_be_proposed"] is False


S03 = "benchmarks/s03/a.json"
S03_CHANGED = trees({S03: b"changed\n"})


def test_a07_a_failure_clause_s_changed_path_lapses_it() -> None:
    result = report(files(acceptances(row("X31 (c)")), **X31_FAIL), tree=S03_CHANGED)
    assert result["reasons"] == [
        "X31: FAIL clause not accepted in release/acceptances.md D3: ['X31 (c)'] (D2.3)"
    ]
    assert f"acceptance X31 (c): lapsed ({S03})" in result["acceptances"]


def test_a07_a_failure_clause_re_dated_on_judged() -> None:
    new = row("X31 (c)", date=JUDGED, at=RC, tree=S03_CHANGED)
    result = report(files(acceptances(new), **X31_FAIL), tree=S03_CHANGED)
    assert result["tag_may_be_proposed"] is True, result["reasons"]
    assert standing_line("X31 (c)", JUDGED, RC) in result["acceptances"]


def test_a07_a_failure_clause_re_dated_the_day_before_judged() -> None:
    early = day_before(JUDGED)
    new = row("X31 (c)", date=early, at=RC, tree=S03_CHANGED)
    result = report(files(acceptances(new), **X31_FAIL), tree=S03_CHANGED)
    assert result["reasons"] == [
        f"X31: X31 (c): accepted {early}, before the verdict's Judged date {JUDGED} "
        "(D2.3; release/acceptances.md D2)"
    ]


def test_a07_a_re_judgement_s_bound_applies_to_a_new_row() -> None:
    rejudged = "**Re-judged:** 2026-11-25 (V17, W24)"
    verdicts = v03.document(v03.ALL_PASS | {"W24": ("FAIL", "W24 (b)", "—")}, rejudged=rejudged)
    ledger = v03.ledger({gate: "PASS" for gate in v03.CLAIMED} | {"W24": "FAIL"})
    scope = SCOPE["X31 (c)"]
    for date, passes in (("2026-11-25", True), ("2026-11-24", False)):
        new = row("W24 (b)", date=date, at=RC, scope=scope)
        result = report(files(acceptances(new), **{VERDICTS: verdicts, v03.LEDGER: ledger}))
        assert result["tag_may_be_proposed"] is passes, (date, result["reasons"])
    standing = row("W24 (b)", scope=scope)
    result = report(files(acceptances(standing), **{VERDICTS: verdicts, v03.LEDGER: ledger}))
    assert result["tag_may_be_proposed"] is True, result["reasons"]


# -- REL.A08: a failing clause with no row ---------------------------------------------------------


@pytest.mark.parametrize("rows", [(), ("V14 (c)",)], ids=["no row", "another gate's row"])
def test_a08_a_failing_clause_without_its_row_is_not_accepted(rows: tuple[str, ...]) -> None:
    table = acceptances(*(row(item, scope=SCOPE["X31 (c)"]) for item in rows))
    result = report(files(table, **X31_FAIL))
    assert result["reasons"] == [
        "X31: FAIL clause not accepted in release/acceptances.md D3: ['X31 (c)'] (D2.3)"
    ]


def test_a08_a_row_that_is_not_an_acceptance_is_not_accepted() -> None:
    pending = row("X31 (c)", cell="pending")
    result = report(files(acceptances(pending), **X31_FAIL))
    assert result["tag_may_be_proposed"] is False
    assert "not accepted" in result["reasons"][0]


# -- RP.S06 in standing mode: decision items 1–12, each refusing alone (review M-1) ---------------

#: V03.A06's twelve NO fixtures (`tests/test_v03_v0_3_gate.py`) on the 0.4 line, through
#: `release_gate.build` with the standing table: each flips only its item and asserts that item's
#: reasons, so that `_build_standing` cannot drop an item (or the version or tree check) unseen.
#: Item 11 has two: Frank's answer, and the links row (`links_problems`, M07 O3).
STEP_15 = {step: ["PASS (1/1)"] for step in SET.rc_steps} | {15: ["FAIL (re-run required)"]}
S10C = f"evidence/S10c/{v03.PACKAGE_AT['S10c']}/manifest.json"
NO: dict[str, tuple[dict[str, Any], list[str]]] = {
    "1": (
        {"version": "0.4.1"},
        ["version 0.4.1 is not covered by a registered v0.4 gate set"],
    ),
    "2": (
        {"rc_version": "0.4.0rc1"},
        ["C's version 0.4.0rc1 is not the candidate's version 0.4.0 (release/acceptances.md D4)"],
    ),
    "3": (
        {"files": {v03.LEDGER: v03.ledger({g: "PASS" for g in v03.CLAIMED} | {"X31": None})}},
        ["X31: no verdict in the ledger (D2.1)"],
    ),
    "4": (
        {
            "files": {
                v03.LEDGER: v03.ledger({g: "PASS" for g in v03.CLAIMED} | {"W26": "BLOCKED"}),
                VERDICTS: v03.document(v03.ALL_PASS | {"W26": ("BLOCKED", "W26 (b): CI run", "—")}),
            }
        },
        ["W26: BLOCKED blocks the tag (D2.2)"],
    ),
    "5": (
        {"files": X31_FAIL},
        ["X31: FAIL clause not accepted in release/acceptances.md D3: ['X31 (c)'] (D2.3)"],
    ),
    "6": (
        {"differences": ["src/openflowsheet/x.py"]},
        [f"candidate {CANDIDATE[:12]} differs from C in ['src/openflowsheet/x.py'] (D2.4)"],
    ),
    "6 (not run)": ({"differences": None}, ["tree check (D2.4) not run"]),
    "7": (
        {"files": {SET.rc_record: v03.rc_record(STEP_15)}},
        [
            f"§6 step 15 (A15, CI): failed in {SET.rc_record}",
            f"§6 step 15: no row of {SET.rc_record} states that it passed",
        ],
    ),
    "8": (
        {"files": {f"evidence/REL040/{RC}/manifest.json": v03.manifest("REL040", RC, "planned")}},
        [f"evidence/REL040/{RC}/manifest.json has status 'planned', not `tested`"],
    ),
    "9": (
        {"files": {S10C: None}},
        [
            "no `tested` or `reviewed` S10c manifest at C or an ancestor of C "
            "(evidence/S10c/<c>/manifest.json)"
        ],
    ),
    "10": (
        {"files": {v03.ENVELOPE: v03.envelope(envelope_id="v0.3-envelope-1", release=VERSION)}},
        [f"{v03.ENVELOPE}: envelope_id 'v0.3-envelope-1', not 'v0.4-envelope-1'"],
    ),
    "11": (
        {"table": {"rows": (row("M03 N1", cell="pending"),)}},
        [
            "Frank's answer to M03 N1 is not an acceptance of the default; amend the standing "
            "release procedure for it"
        ],
    ),
    "11 (links)": (
        {"table": {"defaults": {"V17 carry": "carry v17-c2's agent evidence across R-192, R-234"}}},
        ["V17 carry does not name R-295"],
    ),
    "12": (
        {"files": {"docs/adr/0052-test-input.md": v03.adr("**Status:** Proposed, 2026-10-28")}},
        ["ADR 0052 is not Accepted: **Status:** Proposed, 2026-10-28"],
    ),
}


def test_s06_the_standing_yes_fixture() -> None:
    result = report()
    assert result["reasons"] == [] and result["tag_may_be_proposed"] is True
    assert "acceptances" in result  # standing mode, not the engine's dated build


@pytest.mark.parametrize("item", list(NO))
def test_s06_standing_each_item_refuses_alone(item: str) -> None:
    state, reasons = NO[item]
    table = state.get("table", {})
    rows, defaults = table.get("rows", ()), table.get("defaults", DEFAULTS)
    result = report(
        files(acceptances(*rows, defaults=defaults), **state.get("files", {})),
        version=state.get("version", VERSION),
        rc_version=state.get("rc_version"),
        differences=state.get("differences", ()),
    )
    assert result["tag_may_be_proposed"] is False
    assert result["reasons"] == reasons


def test_s06_standing_twelve_items() -> None:
    assert sorted({int(key.split()[0]) for key in NO}) == list(range(1, 13))


# -- REL.A09: a claim-set change -------------------------------------------------------------------

#: The line file at `OLD` claimed W27 too, so the `Claim set` row was answered for another set.
OLD_LINE = json.loads(json.dumps(LINE.document))
OLD_LINE["gate_set"]["claimed"].append("W27")
OLD_LINE["gate_set"]["not_claimed"] = []
#: ... and its records are where `OLD`'s are (`CANDIDATE_TREE`: S13's), so that every other row,
#: recorded at `OLD`, reproduces there (§8.3 (d)).
OLD_LINE["gate_set"]["evidence_package"] = "S13"
OLD_CLAIM = trees(**{"release__lines__0.4.json": json.dumps(OLD_LINE).encode()})


def test_a09_a_claim_set_change_lapses_claim_set() -> None:
    claim = row("Claim set", tree=OLD_CLAIM)
    result = report(files(acceptances(claim)), tree=OLD_CLAIM)
    assert result["reasons"] == ["Frank's answer to Claim set: lapsed (extract:claim_set)"]


def test_a09_no_until_re_dated() -> None:
    for date, passes in ((LAPSED_ON, True), (day_before(LAPSED_ON), False)):
        claim = row("Claim set", date=date, at=RC, tree=OLD_CLAIM)
        result = report(files(acceptances(claim)), tree=OLD_CLAIM)
        assert result["tag_may_be_proposed"] is passes, (date, result["reasons"])


# -- REL.A10: `extract:pyproject_extra:nlp` --------------------------------------------------------


def _nlp(content: bytes) -> str | None:
    tree = Trees({RC: {"pyproject.toml": content}, CANDIDATE: {}})
    return scopes(tree).term("extract:pyproject_extra:nlp", RC).digest


def test_a10_a_version_bump_leaves_the_extra_equal() -> None:
    assert _nlp(pyproject("0.4.0")) == _nlp(pyproject("0.4.1.dev0")) is not None
    assert pyproject("0.4.0") != pyproject("0.4.1.dev0")


def test_a10_a_package_added_to_nlp_differs() -> None:
    added = pyproject(nlp=("cyipopt==1.7.0", "pyomo==6.10.1", "packaging==26.3"))
    assert _nlp(added) != _nlp(pyproject())


def test_a10_the_value_is_the_sorted_canonical_list() -> None:
    expected = hashlib.sha256(b'["cyipopt==1.7.0","pyomo==6.10.1"]').hexdigest()
    assert _nlp(pyproject(nlp=("pyomo==6.10.1", "cyipopt==1.7.0"))) == expected


def test_a10_an_absent_extra_is_unsupported() -> None:
    tree = Trees({RC: {"pyproject.toml": b'[project]\nname = "p"\n'}, CANDIDATE: {}})
    value = scopes(tree).term("extract:pyproject_extra:nlp", RC)
    assert value.digest is None and "optional-dependencies.nlp" in value.reason


# -- RP §8.2: the terms and the fingerprint --------------------------------------------------------


@pytest.mark.parametrize(
    ("glob", "path", "matches"),
    [
        ("benchmarks/s03/**", "benchmarks/s03/a/b.json", True),
        ("benchmarks/s03/**", "benchmarks/s03", False),
        ("benchmarks/m03/ipopt-inventory-*.json", "benchmarks/m03/ipopt-inventory-1.json", True),
        ("benchmarks/m03/ipopt-inventory-*.json", "benchmarks/m03/ipopt-inventory-a/1.json", False),
        ("tests/test_?.py", "tests/test_a.py", True),
        ("tests/test_?.py", "tests/test_ab.py", False),
        ("docs/a.md", "docs/a_md", False),
        ("docs/a.md", "xdocs/a.md", False),
    ],
)
def test_p1_the_glob_grammar(glob: str, path: str, matches: bool) -> None:
    assert bool(release_gate.glob_pattern(glob).fullmatch(path)) is matches


def test_p4_a_paths_term_hashes_its_sorted_records() -> None:
    term = "paths:benchmarks/s09/**,benchmarks/s03/**,benchmarks/s03/a.json"
    selected = ("benchmarks/s03/a.json", "benchmarks/s09/b.json")
    records = sorted(f"100644 blob {_blob(TREE[path])}\t{path}\n".encode() for path in selected)
    value = scopes(trees()).term(term, RC)
    assert value.digest == hashlib.sha256(b"".join(records)).hexdigest()


def test_f1_the_row_fingerprint_joins_the_term_hashes() -> None:
    digest, values = scopes(trees()).evaluate(SCOPE["V17 carry"], RC)
    hashes = [value.digest for value in values]
    assert hashes[0] == hashlib.sha256(b'["R-192","R-234","R-295"]').hexdigest()
    assert hashes[1] == hashlib.sha256(json.dumps("45" * 32).encode()).hexdigest()
    assert digest == hashlib.sha256(f"{hashes[0]}\n{hashes[1]}".encode()).hexdigest()


def test_e4_differing_or_absent_step_8_records_are_unsupported() -> None:
    differing = dict(CANDIDATE_TREE) | {
        f"evidence/REL040/{RC}/rc/ci/surface/s.json": surface("46" * 32)
    }
    tree = Trees({RC: TREE, CANDIDATE: differing})
    assert "differ" in scopes(tree).term("extract:served_digest", RC).reason
    tree = Trees({RC: TREE, CANDIDATE: {}})
    assert scopes(tree).term("extract:served_digest", RC).digest is None


def test_gate_row_is_unsupported_while_d2_is_deferred() -> None:
    value = scopes(trees()).term("gate_row:V14", RC)
    assert (value.digest, value.reason) == (None, release_gate.GATE_ROW_DEFERRED)
    # A row with such a term never stands (RP §8.2), so a clause it answers is not accepted.
    table = acceptances(
        release_gate.Row("X31 (c)", f"accepted, {EARLY}", "gate_row:X31", "0" * 64, OLD)
    )
    result = report(files(table, **X31_FAIL))
    assert result["tag_may_be_proposed"] is False
    assert (
        f"acceptance X31 (c): unsupported ({release_gate.GATE_ROW_DEFERRED})"
        in result["acceptances"]
    )


# -- RP §8.5: the lapse report ---------------------------------------------------------------------


def test_the_lapse_report() -> None:
    table = release_gate.standing_acceptances(
        acceptances(row("X31 (c)"), row("W28 (a)", scope=SCOPE["X31 (c)"])), "a"
    )
    assert table is not None
    text = release_gate.lapse_report(table, SET, scopes(CHANGED), datetime.date(2026, 11, 10))
    assert text.splitlines() == [
        f"acceptance lapses at C = {RC}, 2026-11-10",
        "X31 (c): stands",
        "Claim set: stands",
        "V17 carry: stands",
        f"M02 N1: lapsed ({REACTOR})",
        "M03 N1: stands",
        "coolprop and lca licences: stands",
    ]
    assert release_gate.lapses_date(text, RC) == datetime.date(2026, 11, 10)
    assert release_gate.lapses_date(text, OLD) is None


# -- the seed, recomputed (REL.A19's values; RP §8.2's sanity table) -------------------------------


def test_the_seed_fingerprints_recompute_at_a3e508e3() -> None:
    """Every row of the committed `release/acceptances.md` at its `Accepted at`, against the
    fingerprints the design lane recorded there with its own implementation."""
    head = release_gate.git("rev-parse", "HEAD").decode().strip()
    seeded = release_gate.Scopes(release_gate.GitTrees(), LINE, head, head)
    rows = (*SEEDED.failures, *SEEDED.decisions)
    assert len(rows) == 7 and {r.accepted_at for r in rows} == {
        "a3e508e35fc5451fe56fa7b70941621992d35b50"
    }
    for seed in rows:
        digest, _ = seeded.evaluate(seed.scope, seed.accepted_at)
        assert digest == seed.fingerprint, seed.item


# -- REL.A19: the seed is ADR 0053's six cells verbatim, at a3e508e3 (ADR 0055 D3.6) ---------------

ADR_0053 = REPO_ROOT / "docs" / "adr" / "0053-v0.3.0-release-policy.md"
C_0_3 = "a3e508e35fc5451fe56fa7b70941621992d35b50"
LICENCES = "coolprop and lca licences"  # ADR 0055 N-7: V03 spec §11 N-11, the seventh row


def a19_problems(seed: release_gate.Acceptances, adr_text: str) -> list[str]:
    """REL.A19's text part: each of ADR 0053's six answer cells is a seeded row's cell, verbatim,
    accepted at C₀.₃; the only other row is N-7's licence row. (The fingerprints recomputed at
    `Accepted at` are `test_the_seed_fingerprints_recompute_at_a3e508e3`'s.)"""
    answers = {
        v0_2_gate._bare(cells[0]): cells[1 if len(header) == 2 else 2]
        for header, table in v0_2_gate._tables(adr_text)
        for cells in table
        if [v0_2_gate._bare(c) for c in header][-1] in ("Frank's acceptance", "Frank's answer")
    }
    rows = {r.item: r for r in (*seed.failures, *seed.decisions)}
    problems = [f"ADR 0053 has {len(answers)} cells, not six"] if len(answers) != 6 else []
    for item, cell in answers.items():
        if item not in rows:
            problems.append(f"{item}: no seeded row")
        elif rows[item].cell != cell:
            problems.append(f"{item}: the answer cell is not ADR 0053's verbatim")
    problems += [f"{item}: not D3.6's" for item in rows if item not in answers and item != LICENCES]
    problems += [
        f"{r.item}: accepted at {r.accepted_at}" for r in rows.values() if r.accepted_at != C_0_3
    ]
    return problems


def test_rel_a19_the_seed_is_adr_0053_s_six_cells_verbatim() -> None:
    """Base: no problem. Controls: one character of one cell changed, a row dropped, a row at
    another commit."""
    adr_text = ADR_0053.read_text(encoding="utf-8")
    assert a19_problems(SEEDED, adr_text) == []
    first = SEEDED.decisions[1]
    edited = release_gate.Acceptances(
        SEEDED.failures,
        (
            SEEDED.decisions[0],
            dataclasses.replace(first, cell=first.cell + "."),
            *SEEDED.decisions[2:],
        ),
    )
    assert a19_problems(edited, adr_text) == [
        f"{first.item}: the answer cell is not ADR 0053's verbatim"
    ]
    dropped = release_gate.Acceptances(SEEDED.failures[1:], SEEDED.decisions)
    assert a19_problems(dropped, adr_text) == [f"{SEEDED.failures[0].item}: no seeded row"]
    moved = release_gate.Acceptances(
        SEEDED.failures,
        (*SEEDED.decisions[:-1], dataclasses.replace(SEEDED.decisions[-1], accepted_at=OLD)),
    )
    assert a19_problems(moved, adr_text) == [f"{SEEDED.decisions[-1].item}: accepted at {OLD}"]
