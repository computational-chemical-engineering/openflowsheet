"""The v0.2 gate report: the claimed gates of a registered gate set, read at the tag candidate.

V02 alpha release spec §7 (`docs/derivations/V02-alpha-release-spec.md`); ADR 0028. One script for
the 0.2 line (`release.yml` resolves `scripts/v<major>_<minor>_gate.py`). It holds a registry of
**gate sets**, each covering the versions its pattern fullmatches; today the only one is
`v0.2-alpha-gate-v1`, which covers `0.2.0aN` (N ≥ 1, canonical) and claims V11–V20, W21 and W22.
A version that no set covers is refused, and nothing else is read. It judges nothing: every
verdict is read from where the design lane records it, and decides whether a tag `v<version>` may
be **proposed** to Frank (the tag is his, ADR 0021 D5).

**Inputs**, each read at the candidate commit (`git show <candidate>:<path>`), never from the
working tree (§7.2):

- `docs/requirements.yaml`, `gates[…].verdict` of the claimed and unclaimed gates.
- `docs/reviews/V02-alpha-verdicts.md`, read by column as `scripts/v0_1_gate.py` reads T08's
  (Amendment R3 §R3.3), with §6.3's differences: a header that names `C` once as
  `**Release candidate:** `<40 hex>`` (equal to `--rc`) and one `**Judged:** YYYY-MM-DD`; twelve
  rows `V11` … `V20`, `W21`, `W22` in order; clauses `Gnn (x)` of the row's own gate. A departure
  is an error (exit 2); a travelling limitation id not in the candidate's envelope is a gate
  problem (exit 1).
- `docs/adr/0028-v0.2-pre-release-policy.md`, and not ADR 0021: its D3 table (a `Frank's
  acceptance` column, first cell a clause) and its decisions table (a `Frank's answer` column,
  rows `N3`, `V17 carry`, `M02 N1`). A cell counts iff, with `*` and backticks removed, stripped
  and lower-cased, it matches `ACCEPTANCE` at its start: `accepted`, then only spaces or `,;:`,
  then a calendar date, which is the acceptance date (Table T4, Amendment 1 (review) F1). A D3
  row and each of the three answers count only if that date is on or after the verdicts' `Judged`
  date (Table T6, Amendment 1 (review) F2), so an answer given for one release is not read for a
  later one. A re-judgement of gates `BLOCKED` on a registered answer keeps `Judged` and adds one
  line `**Re-judged:** YYYY-MM-DD (G, …)` (§19.2, R-371; Table T8, else exit 2); an answer some
  listed gate waits on then counts only up to that date, and a D3 row of a listed gate only from
  it (Table T7).
- `docs/v02-alpha-rc-record.md`, by `v0_1_gate.py`'s RC-record grammar (T08 review 3, Ruling 3)
  with this set's steps: 1–12 must each have a row that passed and none that failed or is not
  stated as passed; step 13 is this script and is not required.
- `evidence/M07a/<C>/manifest.json` (M07a at `C`, `tested` or `reviewed`), and for each of M01 and
  M02 at least one `tested` or `reviewed` `evidence/<P>/<c>/manifest.json` whose commit `c` is `C`
  or an ancestor of it (`git merge-base --is-ancestor`); `C` must be in the repository for that.
- `benchmarks/t08/support_envelope.yaml`: `envelope_id` the set's, `release` the version.
- The required ADRs: the first line of each that starts `**Status:**`, `*` removed and stripped,
  starts `Status: Accepted` (Table T5).
- `C` itself: `--rc` resolves by git or by a unique prefix of a record in `release/rc-trees/`
  (R-151, unchanged); its version is read from git or from the record.

**Decision (§7.3).** A tag may be proposed iff: the version is covered (1); `C`'s version is the
candidate's (2); every claimed gate has a verdict in the ledger and the same in the verdict
document (D2.1, 3), none `BLOCKED` (D2.2, 4), and every `FAIL` names its clauses, each accepted in
ADR 0028's D3 table (D2.3, 5); the candidate's D2.4 paths equal `C`'s (`v0_1_gate.py`'s rule and
code, 6); the RC record shows the set's steps passed (7); the manifests hold (8, 9); the envelope is
pinned (10); Frank's three answers are acceptances dated on or after `Judged`, and within a
re-judgement's bound where one applies (11; Table T7); and every
required ADR is Accepted (12). Unclaimed gates are printed `not claimed (<set>)` and never checked.
A `FAIL` is printed `FAIL`, accepted or not. Exit 0 iff a tag may be proposed, 1 if it may not, 2
if the verdict document is malformed or `C` cannot be found.

    PYTHONPATH=src .venv/bin/python scripts/v0_2_gate.py --rc C [--candidate REF] [--json]
    PYTHONPATH=src .venv/bin/python scripts/v0_2_gate.py --rc C --markdown   # the notes' table
    PYTHONPATH=src .venv/bin/python scripts/v0_2_gate.py --rc C --write-tree-record  # R-151
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
# ADR 0028 D2 reuses ADR 0021's D2 unchanged: the tree check (D2.4, R-151), the RC-record grammar
# and the table reader are `v0_1_gate.py`'s, imported and not copied; that script is not edited.
from v0_1_gate import (  # noqa: E402
    RC_TREES,
    _bare,
    _rc_outcome,
    _tables,
    git,
    has_commit,
    resolve_rc,
    tree_differences,
    tree_record,
    tree_record_of,
    version_at,
)
from v0_1_gate import TREES as TREES  # noqa: E402  (D2.4's paths, shared: ADR 0028 D2)
from v0_1_gate import VERSION_FILES as VERSION_FILES  # noqa: E402

ROOT: Final = Path(__file__).resolve().parent.parent
VERDICTS: Final = ("PASS", "FAIL", "BLOCKED")
#: The statuses of a manifest that count (§7.2 item 5).
MANIFEST_STATUSES: Final = ("tested", "reviewed")
LEDGER: Final = "docs/requirements.yaml"
ENVELOPE: Final = "benchmarks/t08/support_envelope.yaml"
ADR_DIRECTORY: Final = "docs/adr"
#: T08.A03's verdict table (Amendment R3 §R3.3), reused by §6.3: its headers, in order.
HEADERS: Final = ("Gate", "Verdict", "Failing clauses", "Travelling limitations", "Basis")
NONE: Final = "—"

CLAUSE: Final = re.compile(r"\b(?:V(?:1[1-9]|20)|W2[12]) \([a-z0-9]+\)")
LIMITATION: Final = re.compile(r"\bL(?:\d{2}|-[A-Z]+-\d+)\b")
DATE: Final = re.compile(r"\d{4}-\d{2}-\d{2}")
#: Table T4's cell rule (§7.2 item 3, Amendment 1 (review) F1), matched against the bare,
#: lower-cased cell: the date comes right after the word, so `accepted (i), …` is no acceptance.
ACCEPTANCE: Final = re.compile(r"^accepted[\s,;:]*(\d{4}-\d{2}-\d{2})(?![0-9])")
RC_COMMIT: Final = re.compile(r"`C` = `([0-9a-f]{40})`")
RELEASE_CANDIDATE: Final = "**Release candidate:**"
RELEASE_CANDIDATE_VALUE: Final = re.compile(r"\*\*Release candidate:\*\* `([0-9a-f]{40})`")
JUDGED: Final = "**Judged:**"
JUDGED_VALUE: Final = re.compile(r"\*\*Judged:\*\* (\d{4}-\d{2}-\d{2})(?![0-9])")
#: §19.2 item 3 (Table T8): the re-judgement line, stripped, fullmatches `REJUDGED_VALUE`.
REJUDGED: Final = "**Re-judged:**"
REJUDGED_VALUE: Final = re.compile(
    r"\*\*Re-judged:\*\* (\d{4}-\d{2}-\d{2}) "
    r"\(((?:V(?:1[1-9]|20)|W2[12])(?:, (?:V(?:1[1-9]|20)|W2[12]))*)\)"
)


@dataclass(frozen=True)
class GateSet:
    """A registered gate set: the versions it covers and what it claims and reads (§7.1)."""

    name: str
    covers: re.Pattern[str]
    claimed: tuple[str, ...]
    not_claimed: tuple[str, ...]
    policy_adr: str
    verdict_document: str
    rc_record: str
    #: The RC job's steps that must pass, and its last step (the gate itself, not required).
    rc_steps: tuple[int, ...]
    rc_last_step: int
    evidence_package: str
    #: Packages that need a `tested` or `reviewed` manifest at an ancestor of `C`.
    packages: tuple[str, ...]
    envelope_id: str
    required_adrs: tuple[str, ...]
    #: The rows of the policy ADR's decisions table, each Frank's acceptance of a default.
    frank_items: tuple[str, ...]
    #: The gates a re-judgement may list, each with the answer it waits on (§19.2 item 2).
    rejudge_waits: tuple[tuple[str, str], ...]

    @property
    def gates(self) -> tuple[str, ...]:
        return (*self.claimed, *self.not_claimed)


#: The registry (§7.1). M07 adds `v0.2-gate-v1` for 0.2.0 beside this entry.
GATE_SETS: Final = (
    GateSet(
        name="v0.2-alpha-gate-v1",
        covers=re.compile(r"0\.2\.0a[1-9][0-9]*"),
        claimed=(*(f"V{n}" for n in range(11, 21)), "W21", "W22"),
        not_claimed=("W23", "W24", "W25", "W26", "W27"),
        policy_adr="docs/adr/0028-v0.2-pre-release-policy.md",
        verdict_document="docs/reviews/V02-alpha-verdicts.md",
        rc_record="docs/v02-alpha-rc-record.md",
        rc_steps=tuple(range(1, 13)),
        rc_last_step=13,
        evidence_package="M07a",
        packages=("M01", "M02"),
        envelope_id="v0.2-alpha-envelope-1",
        required_adrs=("0022", "0026", "0027", "0028", "0033", "0034", "0035"),
        frank_items=("N3", "V17 carry", "M02 N1"),
        # MR-7, F-α2, F-α3: V13 and V17 wait on `V17 carry`, W21 on `M02 N1`.
        rejudge_waits=(("V13", "V17 carry"), ("V17", "V17 carry"), ("W21", "M02 N1")),
    ),
)


def gate_set_of(version: str) -> GateSet | None:
    """The registered gate set covering `version`, if one does (§7.1)."""
    covering = [entry for entry in GATE_SETS if entry.covers.fullmatch(version)]
    if len(covering) > 1:
        raise ValueError(f"version {version} is covered by {len(covering)} gate sets, not 1")
    return covering[0] if covering else None


def not_covered(version: str) -> str:
    return f"version {version} is not covered by a registered v0.2 gate set"


# -- reading the verdict document ------------------------------------------------------------


@dataclass(frozen=True)
class VerdictRow:
    verdict: str
    clauses: tuple[str, ...]
    limitations: tuple[str, ...]
    blocked: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rejudgement:
    """A `**Re-judged:**` line (§19.2): its date, and the gates it lists, in table order."""

    date: datetime.date
    gates: tuple[str, ...]


@dataclass(frozen=True)
class VerdictDocument:
    rc: str
    judged: datetime.date
    rows: dict[str, VerdictRow]
    rejudged: Rejudgement | None = None


def _ids_outside_their_column(cell: str) -> list[str]:
    return [*CLAUSE.findall(cell), *LIMITATION.findall(cell)]


def _failing_clauses(
    where: str, gate: str, verdict: str, cell: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The `Failing clauses` cell: a FAIL's clauses, or a BLOCKED's `clause: missing input`."""
    where = f"{where}, {gate}, Failing clauses"
    if verdict == "PASS":
        if cell != NONE:
            raise ValueError(f"{where}: a PASS has {NONE!r} here, not {cell!r}")
        return (), ()
    if cell == NONE or not cell:
        raise ValueError(f"{where}: a {verdict} names at least one clause")
    clauses: list[str] = []
    blocked: list[str] = []
    for entry in (part.strip() for part in cell.split(";" if verdict == "BLOCKED" else ",")):
        clause, _, missing = entry.partition(":") if verdict == "BLOCKED" else (entry, "", "")
        clause, missing = clause.strip(), missing.strip()
        if not CLAUSE.fullmatch(clause) or not clause.startswith(gate + " "):
            raise ValueError(f"{where}: {entry!r} is not one of {gate}'s clauses as `Gnn (x)`")
        if verdict == "BLOCKED":
            if not missing or _ids_outside_their_column(missing):
                raise ValueError(
                    f"{where}: {entry!r} names its missing input, and no clause or envelope id"
                )
            blocked.append(f"{clause}: {missing}")
        clauses.append(clause)
    if len(set(clauses)) != len(clauses):
        raise ValueError(f"{where}: a clause is named twice")
    return (tuple(clauses) if verdict == "FAIL" else ()), tuple(blocked)


def _travelling(where: str, gate: str, cell: str) -> tuple[str, ...]:
    if cell == NONE:
        return ()
    entries = [part.strip() for part in cell.split(",")]
    malformed = [entry for entry in entries if not LIMITATION.fullmatch(entry)]
    if malformed or len(set(entries)) != len(entries):
        raise ValueError(
            f"{where}, {gate}, Travelling limitations: envelope ids comma-separated, "
            f"each once, or {NONE!r} (found {malformed or entries})"
        )
    return tuple(entries)


def _header(where: str, text: str, rc: str) -> datetime.date:
    """§6.3's header: `C` named once and equal to `rc`; one `Judged` date."""
    if text.count(RELEASE_CANDIDATE) != 1:
        raise ValueError(f"{where} names {RELEASE_CANDIDATE} {text.count(RELEASE_CANDIDATE)} times")
    named = RELEASE_CANDIDATE_VALUE.search(text)
    if named is None:
        raise ValueError(f"{where}: {RELEASE_CANDIDATE} is not followed by `<40-hex commit>`")
    if named.group(1) != rc:
        raise ValueError(f"{where} is the verdict at C = {named.group(1)}, not at {rc}")
    judged = JUDGED_VALUE.findall(text)
    if text.count(JUDGED) != 1 or len(judged) != 1:
        raise ValueError(f"{where} has no single `{JUDGED} YYYY-MM-DD`")
    try:
        return datetime.date.fromisoformat(judged[0])
    except ValueError:
        raise ValueError(f"{where}: Judged {judged[0]!r} is not a date") from None


def _rejudgement(
    where: str, text: str, judged: datetime.date, gate_set: GateSet
) -> Rejudgement | None:
    """§19.2 item 3 (Table T8): at most one line starting `**Re-judged:**`, anywhere; stripped,
    it fullmatches `REJUDGED_VALUE`, its date is a calendar date on or after `judged`, and its
    gates are a non-empty selection of the gates a re-judgement may list, in strictly increasing
    table order. Anything else is a `ValueError`."""
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith(REJUDGED)]
    if not lines:
        return None
    if len(lines) > 1:
        raise ValueError(f"{where} has {len(lines)} `{REJUDGED}` lines, not at most 1")
    (line,) = lines
    found = REJUDGED_VALUE.fullmatch(line)
    if found is None:
        raise ValueError(f"{where}: {line!r} is not `{REJUDGED} YYYY-MM-DD (G, …)`")
    try:
        date = datetime.date.fromisoformat(found.group(1))
    except ValueError:
        raise ValueError(f"{where}: Re-judged {found.group(1)!r} is not a date") from None
    if date < judged:
        raise ValueError(
            f"{where}: Re-judged {date.isoformat()} is before Judged {judged.isoformat()}"
        )
    gates = tuple(found.group(2).split(", "))
    listable = [gate for gate, _ in gate_set.rejudge_waits]
    strays = [gate for gate in gates if gate not in listable]
    if strays:
        raise ValueError(
            f"{where}: Re-judged lists {strays}, not blocked on a registered answer "
            f"({', '.join(listable)})"
        )
    order = [gate_set.claimed.index(gate) for gate in gates]
    if any(later <= earlier for earlier, later in zip(order, order[1:], strict=False)):
        raise ValueError(
            f"{where}: Re-judged lists {list(gates)}, not in strictly increasing order"
        )
    return Rejudgement(date=date, gates=gates)


def verdict_document(text: str, gate_set: GateSet, rc: str) -> VerdictDocument:
    """The verdict document read by column (§6.3, §7.2 item 2). Anything off the form is a
    `ValueError` rather than a guess."""
    where = gate_set.verdict_document
    judged = _header(where, text, rc)
    rejudged = _rejudgement(where, text, judged, gate_set)
    tables = list(_tables(text))
    verdict_tables = [
        (header, rows)
        for header, rows in tables
        if "verdict" in (_bare(cell).lower() for cell in header)
    ]
    if len(verdict_tables) != 1:
        raise ValueError(f"{where} has {len(verdict_tables)} tables with a Verdict header, not 1")
    ((header, rows),) = verdict_tables
    if any(
        cells and cells[0] in gate_set.gates
        for other_header, other_rows in tables
        if other_header is not header
        for cells in other_rows
    ):
        raise ValueError(
            f"{where}: a table other than the verdict table has a bare gate id as a first cell"
        )
    if tuple(header) != HEADERS:
        raise ValueError(f"{where}: the verdict table's headers are not {HEADERS}")
    unclaimed = [cells[0] for cells in rows if _bare(cells[0]) in gate_set.not_claimed]
    if unclaimed:
        raise ValueError(f"{where}: rows for gates {gate_set.name} does not claim: {unclaimed}")
    if [cells[0] for cells in rows] != list(gate_set.claimed):
        raise ValueError(
            f"{where}: the verdict table's rows are not the bare gate ids "
            f"{', '.join(gate_set.claimed)} in order"
        )
    found: dict[str, VerdictRow] = {}
    for cells in rows:
        gate = cells[0]
        if len(cells) != len(HEADERS):
            raise ValueError(f"{where}, {gate}: {len(cells)} cells, not {len(HEADERS)}")
        _, word, failing, travelling, basis = cells
        if word not in VERDICTS:
            raise ValueError(f"{where}, {gate}: verdict {word!r} is not one of {VERDICTS}")
        if _ids_outside_their_column(basis):
            raise ValueError(
                f"{where}, {gate}, Basis: holds {_ids_outside_their_column(basis)}; "
                "clauses and envelope ids belong in their own columns"
            )
        clauses, blocked = _failing_clauses(where, gate, word, failing)
        found[gate] = VerdictRow(
            verdict=word,
            clauses=clauses,
            limitations=_travelling(where, gate, travelling),
            blocked=blocked,
        )
    return VerdictDocument(rc=rc, judged=judged, rows=found, rejudged=rejudged)


# -- reading the policy ADR (Frank's tables) ---------------------------------------------------


def acceptance_date(cell: str) -> datetime.date | None:
    """Table T4's cell rule: with `*` and backticks removed, stripped and lower-cased, the cell
    matches `ACCEPTANCE` at its start, and the date it captures is the acceptance date. `None` if
    the cell is not an acceptance (or that date is not a calendar date)."""
    date = ACCEPTANCE.match(_bare(cell).lower())
    if date is None:
        return None
    try:
        return datetime.date.fromisoformat(date.group(1))
    except ValueError:
        return None


def frank_table(text: str, column: str) -> tuple[list[tuple[str, str]] | None, str | None]:
    """The rows `(first cell, column cell)` of the one table whose header has `column`
    (lower-cased, bare); or `None` and why, if there is not exactly one such table."""
    found = [
        (header, rows)
        for header, rows in _tables(text)
        if column in [_bare(cell).lower() for cell in header]
    ]
    if len(found) != 1:
        return None, f"{len(found)} tables with a {column!r} column, not 1"
    ((header, rows),) = found
    index = [_bare(cell).lower() for cell in header].index(column)
    return [
        (_bare(cells[0]) if cells else "", cells[index] if index < len(cells) else "")
        for cells in rows
    ], None


@dataclass(frozen=True)
class Policy:
    #: D3: clause → (its acceptance cell, its acceptance date or `None` if it is not one).
    accepted: dict[str, tuple[str, datetime.date | None]]
    problems: list[str]
    frank: list[str]


def _verdict_dates(judged: datetime.date | None, rejudged: Rejudgement | None) -> str:
    """The verdict's dates as a refusal names them: `Judged`, and the re-judgement if any."""
    named = f"Judged date {judged.isoformat() if judged else '(none)'}"
    if rejudged is not None:
        named += f", re-judged {rejudged.date.isoformat()} ({', '.join(rejudged.gates)})"
    return named


def policy(
    text: str | None,
    gate_set: GateSet,
    judged: datetime.date | None,
    rejudged: Rejudgement | None = None,
) -> Policy:
    """ADR 0028's two tables (§7.2 item 3): the D3 acceptances, and Frank's answers, each of
    which must be dated on or after the verdict's `judged` date (Table T6) and, where a gate the
    re-judgement lists waits on it, on or before the re-judgement's date (Table T7); the D3 dates
    are compared in `judge_gate`, clause by clause."""
    where = gate_set.policy_adr
    if text is None:
        missing = f"{where} does not exist at the candidate"
        return Policy({}, [missing], [f"Frank's answers: {missing}"])
    problems: list[str] = []
    accepted: dict[str, tuple[str, datetime.date | None]] = {}
    d3, why = frank_table(text, "frank's acceptance")
    if d3 is None:
        if why is not None and not why.startswith("0 "):  # no D3 table accepts nothing
            problems.append(f"{where}: D3: {why}")
    else:
        for first, cell in d3:
            if not CLAUSE.fullmatch(first):
                continue
            if first in accepted:
                problems.append(f"{where}: D3 lists {first} twice")
            accepted[first] = (cell, acceptance_date(cell))
    frank: list[str] = []
    answers, why = frank_table(text, "frank's answer")
    if answers is None:
        frank.append(f"{where}: Frank's answers: {why}")
    else:
        for item in gate_set.frank_items:
            cells = [cell for first, cell in answers if first == item]
            if not cells:
                frank.append(f"Frank's answer to {item}: no row {item!r} in {where}")
            elif len(cells) > 1:
                frank.append(f"Frank's answer to {item}: {len(cells)} rows in {where}, not 1")
            elif (date := acceptance_date(cells[0])) is None:
                frank.append(
                    f"Frank's answer to {item} is not an acceptance of the default; "
                    "amend the alpha specification for it"
                )
            elif judged is None or date < judged:
                frank.append(
                    f"Frank's answer to {item}: accepted {date.isoformat()}, before the verdict's "
                    f"{_verdict_dates(judged, rejudged)} (§7.3 item 11)"
                )
            elif rejudged is not None and date > rejudged.date:
                waiting = [
                    gate
                    for gate, waits_on in gate_set.rejudge_waits
                    if waits_on == item and gate in rejudged.gates
                ]
                if waiting:
                    frank.append(
                        f"Frank's answer to {item}: accepted {date.isoformat()}, after the "
                        f"re-judgement of {', '.join(waiting)} that read it "
                        f"({_verdict_dates(judged, rejudged)}; §19.2 Table T7)"
                    )
    return Policy(accepted, problems, frank)


# -- the RC record, the manifests, the envelope and the ADRs -----------------------------------


def rc_record_problems(text: str | None, rc: str, gate_set: GateSet) -> list[str]:
    """Why the RC record does not show `rc` to be a release candidate (§7.2 item 4); empty if it
    does. `v0_1_gate.py`'s grammar (Ruling 3) over this set's steps."""
    where = gate_set.rc_record
    if text is None:
        return [f"no RC record: {where} does not exist at the candidate"]
    named = sorted(set(RC_COMMIT.findall(text)))
    if named != [rc]:
        return [f"{where} is the record of C = {named or 'no commit'}, not of {rc}"]
    tables = [
        (header, rows)
        for header, rows in _tables(text)
        if [_bare(cell) for cell in header[:2]] == ["Step", "Assertion"]
        and any(_bare(cell).startswith("Result") for cell in header)
    ]
    if len(tables) != 1:
        return [f"{where} has {len(tables)} per-step tables, not 1"]
    ((header, rows),) = tables
    column = [_bare(cell).startswith("Result") for cell in header].index(True)
    outcomes: dict[int, list[str]] = {}
    problems: list[str] = []
    for cells in rows:
        step = _bare(cells[0])
        if (
            not step.isdigit()
            or not 1 <= int(step) <= gate_set.rc_last_step
            or len(cells) != len(header)
        ):
            problems.append(f"{where}: unreadable row {cells[:2]}")
            continue
        outcome = _rc_outcome(cells[column])
        outcomes.setdefault(int(step), []).append(outcome)
        if int(step) in gate_set.rc_steps and outcome in ("failed", "unstated"):
            said = "failed" if outcome == "failed" else "not stated as passed"
            problems.append(
                f"§8.2 step {step} ({_bare(cells[1])}, {_bare(cells[2])}): {said} in {where}"
            )
    for required in gate_set.rc_steps:
        if "passed" not in outcomes.get(required, []):
            problems.append(f"§8.2 step {required}: no row of {where} states that it passed")
    return problems


def _manifest(text: str) -> Mapping[str, Any] | None:
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return None
    return document if isinstance(document, dict) else None


def manifest_problems(
    files: Mapping[str, str],
    gate_set: GateSet,
    rc: str,
    *,
    rc_in_repository: bool,
    is_ancestor: Callable[[str], bool],
) -> list[str]:
    """§7.2 item 5: the set's own manifest at `C`, and its packages' at ancestors of `C`."""
    problems: list[str] = []
    package = gate_set.evidence_package
    path = f"evidence/{package}/{rc}/manifest.json"
    text = files.get(path)
    own = None if text is None else _manifest(text)
    if text is None:
        problems.append(f"no {package} manifest: {path} does not exist at the candidate")
    elif own is None:
        problems.append(f"{path} is not a JSON object")
    else:
        if own.get("work_package") != package or own.get("commit") != rc:
            problems.append(
                f"{path} is the manifest of {own.get('work_package')} at {own.get('commit')}, "
                f"not of {package} at {rc}"
            )
        if own.get("status") not in MANIFEST_STATUSES:
            problems.append(f"{path} has status {own.get('status')!r}, not `tested`")
    if not rc_in_repository:
        problems.append(
            "C is not in the repository: the "
            + "/".join(gate_set.packages)
            + " ancestry check needs it"
        )
        return problems
    for name in gate_set.packages:
        prefix = f"evidence/{name}/"
        qualifying = []
        for candidate_path, content in sorted(files.items()):
            parts = candidate_path.split("/")
            if not (candidate_path.startswith(prefix) and len(parts) == 4):
                continue
            document = _manifest(content)
            if (
                parts[3] == "manifest.json"
                and document is not None
                and document.get("work_package") == name
                and document.get("commit") == parts[2]
                and document.get("status") in MANIFEST_STATUSES
                and is_ancestor(parts[2])
            ):
                qualifying.append(candidate_path)
        if not qualifying:
            problems.append(
                f"no `tested` or `reviewed` {name} manifest at C or an ancestor of C "
                f"(evidence/{name}/<c>/manifest.json)"
            )
    return problems


def envelope_document(text: str | None) -> Mapping[str, Any]:
    if text is None:
        return {}
    document = yaml.safe_load(text)
    return document if isinstance(document, dict) else {}


def envelope_problems(text: str | None, gate_set: GateSet, version: str) -> list[str]:
    """§7.2 item 6: the envelope pinned to the set's id and to the version being cut."""
    if text is None:
        return [f"{ENVELOPE} does not exist at the candidate"]
    document = envelope_document(text)
    problems = []
    if document.get("envelope_id") != gate_set.envelope_id:
        problems.append(
            f"{ENVELOPE}: envelope_id {document.get('envelope_id')!r}, not {gate_set.envelope_id!r}"
        )
    if str(document.get("release")) != version:
        problems.append(f"{ENVELOPE}: release {document.get('release')!r}, not {version!r}")
    return problems


def status_line(text: str) -> str | None:
    return next((line for line in text.splitlines() if line.startswith("**Status:**")), None)


def adr_problems(files: Mapping[str, str], gate_set: GateSet) -> list[str]:
    """§7.2 item 7: every required ADR exists once and its status line starts `Status: Accepted`
    (Table T5)."""
    problems = []
    for number in gate_set.required_adrs:
        paths = sorted(
            path
            for path in files
            if path.startswith(f"{ADR_DIRECTORY}/{number}-") and path.endswith(".md")
        )
        if len(paths) != 1:
            problems.append(
                f"ADR {number}: {len(paths)} files {ADR_DIRECTORY}/{number}-*.md at the "
                "candidate, not 1"
            )
            continue
        line = status_line(files[paths[0]])
        if line is None:
            problems.append(f"ADR {number}: {paths[0]} has no **Status:** line")
        elif not line.replace("*", "").strip().startswith("Status: Accepted"):
            problems.append(f"ADR {number} is not Accepted: {line}")
    return problems


# -- judging what was read ----------------------------------------------------------------------


@dataclass
class GateLine:
    gate: str
    claimed: bool
    requirement: str
    ledger: str | None
    document: VerdictRow | None
    accepted: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def judge_gate(
    gate: str,
    entry: Mapping[str, Any] | None,
    row: VerdictRow | None,
    found: Policy,
    judged: datetime.date | None,
    known_limitations: set[str],
    gate_set: GateSet,
    rejudged: Rejudgement | None = None,
) -> GateLine:
    line = GateLine(
        gate=gate,
        claimed=True,
        requirement=str(entry["required_evidence"]) if entry else "",
        ledger=entry.get("verdict") if entry else None,
        document=row,
    )
    if entry is None:
        line.problems.append("no such gate in the ledger (D2.1)")
    elif line.ledger is None:
        line.problems.append("no verdict in the ledger (D2.1)")
    elif line.ledger not in VERDICTS:
        line.problems.append(f"ledger verdict {line.ledger!r} is not one of {VERDICTS} (D2.1)")
    if row is None:
        line.problems.append(f"no row in {gate_set.verdict_document} (D2.1)")
    elif line.ledger is not None and row.verdict != line.ledger:
        line.problems.append(f"ledger {line.ledger} but {gate_set.verdict_document} {row.verdict}")
    if row is not None:
        unknown = [lid for lid in row.limitations if lid not in known_limitations]
        if unknown:
            line.problems.append(f"limitation ids not in {ENVELOPE}: {unknown}")
    if "BLOCKED" in (line.ledger, row.verdict if row else None):
        line.problems.append("BLOCKED blocks the tag (D2.2)")
    if "FAIL" in (line.ledger, row.verdict if row else None):
        clauses = row.clauses if row else ()
        if not clauses:
            line.problems.append("a FAIL that names no clause (D2.3)")
        unaccepted = []
        for clause in clauses:
            cell, date = found.accepted.get(clause, ("", None))
            if date is None:
                unaccepted.append(clause)
            elif judged is None or date < judged:
                line.problems.append(
                    f"{clause}: accepted {date.isoformat()}, before the verdict's "
                    f"{_verdict_dates(judged, rejudged)} (D2.3; ADR 0028 D2)"
                )
            elif rejudged is not None and gate in rejudged.gates and date < rejudged.date:
                line.problems.append(
                    f"{clause}: accepted {date.isoformat()}, before the re-judgement of {gate} "
                    f"that judged it ({_verdict_dates(judged, rejudged)}; D2.3; §19.2 Table T7)"
                )
            else:
                line.accepted[clause] = cell
        if unaccepted:
            line.problems.append(f"FAIL clause not accepted in ADR 0028 D3: {unaccepted} (D2.3)")
    return line


# -- the report -------------------------------------------------------------------------------


def build(
    *,
    files: Mapping[str, str],
    rc: str,
    rc_version: str,
    rc_in_repository: bool,
    candidate: str,
    version: str,
    differences: Sequence[str] | None,
    is_ancestor: Callable[[str], bool],
) -> dict[str, Any]:
    """The report, from the candidate's files (path → text; a missing path is a missing file)
    and the facts about `C` that git gives. `differences` is the D2.4 tree check's result
    (`tree_differences`); `None` means it was not run, which refuses. A malformed verdict
    document is a `ValueError`."""
    gate_set = gate_set_of(version)
    if gate_set is None:
        return {
            "gate_set": None,
            "rc": rc,
            "candidate": candidate,
            "version": version,
            "gates": [],
            "tag_may_be_proposed": False,
            "reasons": [not_covered(version)],
        }
    ledger = yaml.safe_load(files[LEDGER]) if LEDGER in files else None
    entries = {
        str(entry.get("id")): dict(entry)
        for entry in (ledger or {}).get("gates", [])
        if isinstance(entry, dict)
    }
    verdict_text = files.get(gate_set.verdict_document)
    document = None if verdict_text is None else verdict_document(verdict_text, gate_set, rc)
    rows = document.rows if document else {}
    rejudged = document.rejudged if document else None
    found = policy(
        files.get(gate_set.policy_adr),
        gate_set,
        document.judged if document else None,
        rejudged,
    )
    envelope_text = files.get(ENVELOPE)
    known = {str(item["id"]) for item in envelope_document(envelope_text).get("limitations", [])}
    lines = [
        judge_gate(
            gate,
            entries.get(gate),
            rows.get(gate),
            found,
            document.judged if document else None,
            known,
            gate_set,
            rejudged,
        )
        for gate in gate_set.claimed
    ]
    for gate in gate_set.not_claimed:
        entry = entries.get(gate)
        lines.append(
            GateLine(
                gate=gate,
                claimed=False,
                requirement=str(entry["required_evidence"]) if entry else "",
                ledger=entry.get("verdict") if entry else None,
                document=None,
            )
        )
    reasons = [f"{line.gate}: {problem}" for line in lines for problem in line.problems]
    if verdict_text is None:
        reasons.insert(0, f"{gate_set.verdict_document} does not exist at the candidate")
    if rc_version != version:
        reasons.append(
            f"C's version {rc_version} is not the candidate's version {version} (ADR 0028 D4)"
        )
    if differences is None:
        # Review F3: a caller that does not run the tree check gets no YES (D2.4 fails closed).
        reasons.append("tree check (D2.4) not run")
    elif differences:
        reasons.append(f"candidate {candidate[:12]} differs from C in {list(differences)} (D2.4)")
    record = rc_record_problems(files.get(gate_set.rc_record), rc, gate_set)
    manifests = manifest_problems(
        files, gate_set, rc, rc_in_repository=rc_in_repository, is_ancestor=is_ancestor
    )
    envelope = envelope_problems(envelope_text, gate_set, version)
    adrs = adr_problems(files, gate_set)
    for group in (record, manifests, envelope, adrs, found.problems, found.frank):
        reasons.extend(group)
    return {
        "gate_set": gate_set.name,
        "rc": rc,
        "candidate": candidate,
        "version": version,
        "rc_version": rc_version,
        "judged": document.judged.isoformat() if document else None,
        "rejudged": (
            {"date": rejudged.date.isoformat(), "gates": list(rejudged.gates)} if rejudged else None
        ),
        "gates": [
            {
                "gate": line.gate,
                "claimed": line.claimed,
                "requirement": line.requirement,
                "ledger": line.ledger,
                "verdict_document": line.document.verdict if line.document else None,
                "failing_clauses": list(line.document.clauses) if line.document else [],
                "blocked_clauses": list(line.document.blocked) if line.document else [],
                "limitations": list(line.document.limitations) if line.document else [],
                "accepted_fail_clauses": line.accepted,
                "problems": line.problems,
            }
            for line in lines
        ],
        "tree_differences": None if differences is None else list(differences),
        "rc_record_problems": record,
        "manifest_problems": manifests,
        "envelope_problems": envelope,
        "adr_problems": adrs,
        "frank_problems": found.problems + found.frank,
        "tag_may_be_proposed": not reasons,
        "reasons": reasons,
    }


def _not_claimed(report: Mapping[str, Any]) -> str:
    return f"not claimed ({report['gate_set']})"


def _verdict_word(entry: Mapping[str, Any]) -> str:
    return str(entry["ledger"]) if entry["ledger"] else "no verdict"


def _notes(entry: Mapping[str, Any]) -> str:
    notes = []
    if entry["failing_clauses"]:
        notes.append("failing: " + ", ".join(entry["failing_clauses"]))
    if entry["blocked_clauses"]:
        notes.append("blocked: " + "; ".join(entry["blocked_clauses"]))
    for clause, acceptance in entry["accepted_fail_clauses"].items():
        date = DATE.search(acceptance)
        notes.append(
            f"{clause} FAIL, accepted by Frank {date.group(0) if date else ''} (ADR 0028 D3)"
        )
    if entry["limitations"]:
        notes.append("limitations: " + ", ".join(entry["limitations"]))
    return "; ".join(notes)


def markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "| Gate | Verdict at C | Required evidence | Clauses and travelling limitations |",
        "| --- | --- | --- | --- |",
    ]
    for entry in report["gates"]:
        if entry["claimed"]:
            word, notes = _verdict_word(entry), _notes(entry) or NONE
        else:
            word, notes = "not claimed", NONE
        lines.append(f"| {entry['gate']} | {word} | {entry['requirement']} | {notes} |")
    return "\n".join(lines) + "\n"


def _summary(problems: Sequence[str], good: str) -> str:
    return good if not problems else f"{len(problems)} problems"


def _last_line(report: Mapping[str, Any]) -> str:
    return f"v{report['version']} tag may be proposed: " + (
        "YES" if report["tag_may_be_proposed"] else f"NO ({len(report['reasons'])} reasons)"
    )


def text(report: Mapping[str, Any]) -> str:
    if report["gate_set"] is None:
        return "\n".join([*report["reasons"], _last_line(report)]) + "\n"
    out = [
        f"v0.2 gates ({report['gate_set']}) at C = {report['rc']}; candidate {report['candidate']}"
    ]
    for entry in report["gates"]:
        if not entry["claimed"]:
            out.append(f"{entry['gate']}  {_not_claimed(report)}")
            continue
        out.append(f"{entry['gate']}  {_verdict_word(entry):<11}{entry['requirement']}")
        notes = _notes(entry)
        if notes:
            out.append(f"      {notes}")
        for problem in entry["problems"]:
            out.append(f"      not releasable: {problem}")
    out.append("")
    differences = report["tree_differences"]
    out.append(
        "tree check (D2.4): "
        + (
            "not run"
            if differences is None
            else f"differs in {len(differences)} paths"
            if differences
            else "equal to C"
        )
    )
    out.append(
        "RC record (§8.1 item 4): "
        + _summary(report["rc_record_problems"], "the required steps passed at C")
    )
    out.append(
        "manifests (§8.1 item 5; §7.2 item 5): "
        + _summary(report["manifest_problems"], "tested at C and at ancestors of C")
    )
    out.append("envelope (§7.2 item 6): " + _summary(report["envelope_problems"], "pinned"))
    out.append("ADRs (§7.2 item 7): " + _summary(report["adr_problems"], "every one Accepted"))
    out.append(
        "Frank's answers (ADR 0028): " + _summary(report["frank_problems"], "every one accepted")
    )
    gates = tuple(entry["gate"] for entry in report["gates"])
    for reason in report["reasons"]:
        if not reason.startswith(gates):  # each gate's own reasons are printed under it
            out.append(f"  - {reason}")
    out.append(_last_line(report))
    return "\n".join(out) + "\n"


# -- reading the candidate ---------------------------------------------------------------------


def read_at(commit: str, path: str) -> str | None:
    """`path`'s text at `commit`, or `None` if it has no such file."""
    try:
        return git("show", f"{commit}:{path}").decode("utf-8")
    except subprocess.CalledProcessError:
        return None


def files_at(candidate: str, rc: str, gate_set: GateSet) -> dict[str, str]:
    """Every input of §7.2 items 1–7, read at `candidate`."""
    listed = git(
        "ls-tree",
        "-r",
        "--name-only",
        candidate,
        "--",
        *(f"evidence/{name}/" for name in gate_set.packages),
        f"{ADR_DIRECTORY}/",
    ).decode("utf-8")
    paths = [
        LEDGER,
        ENVELOPE,
        gate_set.policy_adr,
        gate_set.verdict_document,
        gate_set.rc_record,
        f"evidence/{gate_set.evidence_package}/{rc}/manifest.json",
        *(
            path
            for path in listed.splitlines()
            if path.endswith("/manifest.json")
            or any(path.startswith(f"{ADR_DIRECTORY}/{n}-") for n in gate_set.required_adrs)
        ),
    ]
    found = {path: read_at(candidate, path) for path in dict.fromkeys(paths)}
    return {path: content for path, content in found.items() if content is not None}


def is_ancestor_of(rc: str) -> Callable[[str], bool]:
    def check(commit: str) -> bool:
        try:
            git("merge-base", "--is-ancestor", commit, rc)
        except subprocess.CalledProcessError:
            return False
        return True

    return check


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rc", required=True, help="the release candidate C")
    parser.add_argument("--candidate", default="HEAD", help="the tag candidate (default HEAD)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--markdown", action="store_true")
    output.add_argument(
        "--write-tree-record",
        action="store_true",
        help=f"write {RC_TREES}/<C>.json for --rc C, which must be in the repository (R-151)",
    )
    arguments = parser.parse_args(argv)

    try:
        rc = resolve_rc(arguments.rc)
        rc_in_repository = has_commit(rc)
        if arguments.write_tree_record:
            if not rc_in_repository:
                raise ValueError("--write-tree-record needs --rc, a commit of this repository")
            path = ROOT / RC_TREES / f"{rc}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(tree_record(rc), indent=1, sort_keys=True) + "\n", "utf-8")
            print(f"wrote {RC_TREES / path.name}")
            return 0
        candidate = git("rev-parse", f"{arguments.candidate}^{{commit}}").decode().strip()
        version = version_at(candidate)
        gate_set = gate_set_of(version)
        report = build(
            files={} if gate_set is None else files_at(candidate, rc, gate_set),
            rc=rc,
            rc_version=(version_at(rc) if rc_in_repository else str(tree_record_of(rc)["version"])),
            rc_in_repository=rc_in_repository,
            candidate=candidate,
            version=version,
            differences=None if gate_set is None else tree_differences(rc, candidate),
            is_ancestor=is_ancestor_of(rc),
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    elif arguments.markdown:
        if report["gate_set"] is None:
            print(f"error: {report['reasons'][0]}", file=sys.stderr)
            return 1
        print(markdown(report), end="")
    else:
        print(text(report), end="")
    return 0 if report["tag_may_be_proposed"] else 1


if __name__ == "__main__":
    sys.exit(main())
