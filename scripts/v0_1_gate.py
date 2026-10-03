"""The v0.1 gate report: V11–V20, read from the ledger and the verdicts, and the tag-tree check.

T08 release spec §8.2 step 11 and §9 T08.A50; ADR 0021 D2 and D3 (with its revision 1 and the
D3 row of 2026-09-29). It prints each gate's verdict and travelling limitation ids and decides
whether a `v0.1.z` tag may be **proposed** to Frank (the tag itself is his, D5), for the version
`pyproject.toml` declares at the candidate; a version off the 0.1 line is not covered by these
gates and is refused. It judges
nothing: every verdict is read from where the design lane records it, and a gate without one is
reported as such, never inferred.

**Inputs.**

- `docs/requirements.yaml`, `gates[V11…V20].verdict` (`PASS`, `FAIL`, `BLOCKED` or null).
- `docs/reviews/T08-verdicts.md` (T08.A03), read **by column** (release spec Amendment R3 §R3.3):
  exactly one table with a `Verdict` header, whose headers are `Gate | Verdict | Failing clauses
  | Travelling limitations | Basis` in that order and whose ten rows are the bare gate ids `V11`
  … `V20` in order. `Verdict` is a bare `PASS`, `FAIL` or `BLOCKED`. `Failing clauses` is a
  FAIL's own clauses, comma-separated `Vnn (x)`, at least one; a BLOCKED's blocked clauses as
  `Vnn (x): <missing input>`, separated by `;`; a PASS's `—`. `Travelling limitations` is the
  support-envelope ids (`L01`, `L-WS-1`, …), comma-separated, each of which must exist in
  `benchmarks/t08/support_envelope.yaml`, or `—`. Clauses are read only from `Failing clauses`
  and ids only from `Travelling limitations`; a clause or envelope id in any other cell (the
  gate's `Basis` included), a missing or reordered column, a gate out of order, a bold gate id, a
  second verdict table, or another table whose first cell is a bare gate id is an error (exit 2).
- `docs/adr/0021-v0.1-release-policy.md`: the accepted FAIL clauses are the rows of the tables
  whose header has a `Frank's acceptance` column, a row counting only if that cell holds a date
  (D2.3). D3's original table of *proposed* carries has no such column and lists nothing.
- The release candidate `C`: `--rc` (a commit, or a unique prefix of a recorded one, below), else
  the commit of the newest `tested` (or `reviewed`) `evidence/T08/<C>/manifest.json` (§8.1 item
  5). With `--rc` that manifest is read too: it must exist, be T08's, name `C` as its commit and
  have `status` `tested` (or `reviewed`), else no tag may be proposed (T08 verdicts finding G3
  (b)).
- `docs/t08-rc-record.md`, the RC record (§8.1 item 4; verdicts finding G3). It names its
  candidate once as `` `C` = `<40-hex commit>` `` and has one per-step table whose headers begin
  `Step | Assertion` and include a `Result…` column, read by column: the `Step` cell is §8.2's step
  number, the `Result` cell what the step's record says, in the record's status words (T08
  review 3, Ruling 3). A row's Result cell is read by its **status head**: the text before its
  first `(`, `:`, `;` or `.`, with `*`, `` ` `` and `"` removed, split on `/` and white space. The
  **status words** are the record's `PASS`, `FAIL` and `FAILED`, and CI's conclusions `success`,
  `failure`, `cancelled`, `skipped`, `timed_out`, `startup_failure`, `action_required`, `neutral`
  and `stale`. `not measured` is a status word in any letter case. A row **failed** if either its
  head holds a status word other than `PASS` or `success`; or the whole cell contains `FAIL`,
  `FAILED`, `Failed` or `failure` (case-sensitive; `Failed` and `failure` as words, `failure`
  also inside a longer identifier such as `startup_failure`, though neither as the stem of a
  longer word such as `failures`, as Ruling 3's reading of the `814e151` record requires; so
  "PASS: Failed to upload" fails, T08 verdicts finding G3 (a)), or `not measured` in any case.
  A row **passed** if it did not fail, its head holds at least one status word, and every status
  word in its head is `PASS` or `success`. Where the head is followed by a count `(k/n`, k must
  equal n, else the row is not stated as passed. A bare `—` is a supporting row (run files) with
  no result. Anything else is not stated as passed.

**Decision (ADR 0021 D2).** A tag may be proposed iff (1) every gate has a verdict in the ledger
and the same verdict in the verdict document; (2) none is `BLOCKED`; (3) every `FAIL` names its
clauses and each is accepted in D3; and (4) the candidate's distribution sources — `src/`,
`schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`,
`LICENSE`, `NOTICE` — equal `C`'s except one occurrence of the version value in each of
`pyproject.toml` and `src/openflowsheet/__init__.py` (D2.4 as revised by ADR 0021's proposed
revision 2, release spec Amendment R3 4). Where `C` is in the repository, its files are read from
git; where it is not (the public repository starts at v0.1.0 without the development history,
R-150), from `release/rc-trees/<C>.json`, the sha256 and mode of every file under those paths at
`C` and its version, recorded while `C` was present — the same rule on the same files (R-151);
and (5) D2 presupposes D1: `C` is a release candidate
under §8.1 item 4, i.e. the RC record exists for `C` and every §8.2 step 1–10 it lists passed —
each step has at least one row that passed and none that failed or is not stated as passed. Step
11 is this script, whose run at `C` precedes the verdicts; its row is not required to pass. And
(6) §8.1 item 5: `evidence/T08/<C>/manifest.json` exists with `status` `tested` (or `reviewed`).
Exit 0 iff a tag may be proposed, 1 if it may not, 2 if the verdict document is malformed or
`C` cannot be found (neither in the repository nor recorded). A FAIL
is printed `FAIL`, accepted or not.

    PYTHONPATH=src .venv/bin/python scripts/v0_1_gate.py [--rc C] [--candidate REF] [--json]
    PYTHONPATH=src .venv/bin/python scripts/v0_1_gate.py --markdown   # the CHANGELOG's table
    PYTHONPATH=src .venv/bin/python scripts/v0_1_gate.py --rc C --write-tree-record  # R-151
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

ROOT: Final = Path(__file__).resolve().parent.parent
GATES: Final = tuple(f"V{n}" for n in range(11, 21))
VERDICTS: Final = ("PASS", "FAIL", "BLOCKED")
LEDGER: Final = Path("docs/requirements.yaml")
VERDICT_DOCUMENT: Final = Path("docs/reviews/T08-verdicts.md")
ADR_0021: Final = Path("docs/adr/0021-v0.1-release-policy.md")
ENVELOPE: Final = Path("benchmarks/t08/support_envelope.yaml")
RC_RECORD: Final = Path("docs/t08-rc-record.md")
#: §8.2's steps the RC record must show passed (§8.1 item 4); step 11 is this script.
RC_STEPS: Final = tuple(range(1, 11))
EVIDENCE: Final = Path("evidence/T08")
#: §8.1 item 5: the statuses of `evidence/T08/<C>/manifest.json` that make `C` a release candidate.
MANIFEST_STATUSES: Final = ("tested", "reviewed")
#: ADR 0021 D2.4 (proposed revision 2): every input of the sdist and wheel, which the tag commit
#: must share with `C`, and the two files that declare the version (the only difference allowed
#: inside them).
TREES: Final = (
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
VERSION_FILES: Final = ("src/openflowsheet/__init__.py", "pyproject.toml")
#: R-151: `<C>.json` records `C`'s files under `TREES` (mode and sha256) and its version, so the
#: tree check runs where `C` is not in the repository (R-150).
RC_TREES: Final = Path("release/rc-trees")
#: The versions these gates cover: the 0.1 line (`0.1.z`, and its pre-releases such as `C`'s).
V0_1_LINE: Final = re.compile(r"0\.1\.(?:0|[1-9]\d*)(?![0-9.])")

#: T08.A03's verdict table (Amendment R3 §R3.3): its headers, in order.
HEADERS: Final = ("Gate", "Verdict", "Failing clauses", "Travelling limitations", "Basis")
NONE: Final = "—"

CLAUSE: Final = re.compile(r"\bV(?:1[1-9]|20) \([a-z0-9]+\)")
LIMITATION: Final = re.compile(r"\bL(?:\d{2}|-[A-Z]+-\d+)\b")
DATE: Final = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
RC_COMMIT: Final = re.compile(r"`C` = `([0-9a-f]{40})`")
#: The RC record's status words (T08 review 3, Ruling 3): its records' `PASS`, `FAIL` and `FAILED`,
#: and CI's job conclusions, each read as written, so lower-case `pass` / `fail` are prose (a
#: check's status, "none failed"); `not measured` is one in any letter case (`RC_FAILED`).
RC_PASS_WORDS: Final = frozenset({"PASS", "success"})
RC_STATUS_WORDS: Final = RC_PASS_WORDS | frozenset(
    {
        "FAIL",
        "FAILED",
        "failure",
        "cancelled",
        "skipped",
        "timed_out",
        "startup_failure",
        "action_required",
        "neutral",
        "stale",
    }
)
#: A Result cell's status head ends at the first of these.
RC_HEAD_END: Final = re.compile(r"[(:;.]")
#: Anywhere in a Result cell, a failure: `FAIL` / `FAILED` / `Failed` / `failure` as written,
#: `Failed` and `failure` as words (`failure` also inside a longer identifier, `startup_failure`)
#: but not as the stem of a longer word (the `814e151` record's "A33 failures 0", which Ruling 3
#: states still passes), or `not measured` in any letter case. `Failed` is verdicts finding G3 (a):
#: "PASS: Failed to upload" fails.
RC_FAILED: Final = re.compile(r"FAIL|(?<![A-Za-z])(?:Failed|failure)(?![A-Za-z])|(?i:not measured)")
#: The count `(k/n` that may follow a status head.
RC_COUNT: Final = re.compile(r"\((\d+)/(\d+)")


# -- reading -----------------------------------------------------------------------------------


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _bare(cell: str) -> str:
    return cell.replace("*", "").replace("`", "").strip()


def _tables(text: str) -> Iterator[tuple[list[str], list[list[str]]]]:
    """Every markdown table in `text`: its header cells and its data rows' cells, as written."""
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if (
            lines[index].lstrip().startswith("|")
            and index + 1 < len(lines)
            and re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", lines[index + 1])
            and "-" in lines[index + 1]
        ):
            header = _cells(lines[index])
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                rows.append(_cells(lines[index]))
                index += 1
            yield header, rows
        else:
            index += 1


def ledger_gates(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    found = {entry["id"]: dict(entry) for entry in document["gates"] if entry["id"] in GATES}
    missing = [gate for gate in GATES if gate not in found]
    if missing:
        raise ValueError(f"the ledger has no gate {missing}")
    return found


@dataclass(frozen=True)
class VerdictRow:
    verdict: str | None
    clauses: tuple[str, ...]
    limitations: tuple[str, ...]
    blocked: tuple[str, ...] = ()


def _ids_outside_their_column(cell: str) -> list[str]:
    return [*CLAUSE.findall(cell), *LIMITATION.findall(cell)]


def _failing_clauses(gate: str, verdict: str, cell: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The `Failing clauses` cell: a FAIL's clauses, or a BLOCKED's `clause: missing input`."""
    where = f"{VERDICT_DOCUMENT}, {gate}, Failing clauses"
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
            raise ValueError(f"{where}: {entry!r} is not one of {gate}'s clauses as `Vnn (x)`")
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


def _travelling(gate: str, cell: str) -> tuple[str, ...]:
    if cell == NONE:
        return ()
    entries = [part.strip() for part in cell.split(",")]
    malformed = [entry for entry in entries if not LIMITATION.fullmatch(entry)]
    if malformed or len(set(entries)) != len(entries):
        raise ValueError(
            f"{VERDICT_DOCUMENT}, {gate}, Travelling limitations: envelope ids comma-separated, "
            f"each once, or {NONE!r} (found {malformed or entries})"
        )
    return tuple(entries)


def verdict_rows(text: str) -> dict[str, VerdictRow]:
    """T08.A03's verdict table, read by column (Amendment R3 §R3.3). Anything off the form is a
    `ValueError` rather than a guess."""
    tables = list(_tables(text))
    verdict_tables = [
        (header, rows)
        for header, rows in tables
        if "verdict" in (_bare(cell).lower() for cell in header)
    ]
    if len(verdict_tables) != 1:
        raise ValueError(
            f"{VERDICT_DOCUMENT} has {len(verdict_tables)} tables with a Verdict header, not 1"
        )
    ((header, rows),) = verdict_tables
    if any(
        cells and cells[0] in GATES
        for other_header, other_rows in tables
        if other_header is not header
        for cells in other_rows
    ):
        raise ValueError(
            f"{VERDICT_DOCUMENT}: a table other than the verdict table has a bare "
            "gate id as a first cell"
        )
    if tuple(header) != HEADERS:
        raise ValueError(f"{VERDICT_DOCUMENT}: the verdict table's headers are not {HEADERS}")
    if [cells[0] for cells in rows] != list(GATES):
        raise ValueError(
            f"{VERDICT_DOCUMENT}: the verdict table's rows are not the bare gate ids "
            f"{GATES[0]}…{GATES[-1]} in order"
        )
    found: dict[str, VerdictRow] = {}
    for cells in rows:
        gate = cells[0]
        if len(cells) != len(HEADERS):
            raise ValueError(f"{VERDICT_DOCUMENT}, {gate}: {len(cells)} cells, not {len(HEADERS)}")
        _, word, failing, travelling, basis = cells
        if word not in VERDICTS:
            raise ValueError(
                f"{VERDICT_DOCUMENT}, {gate}: verdict {word!r} is not one of {VERDICTS}"
            )
        if _ids_outside_their_column(basis):
            raise ValueError(
                f"{VERDICT_DOCUMENT}, {gate}, Basis: holds {_ids_outside_their_column(basis)}; "
                "clauses and envelope ids belong in their own columns"
            )
        clauses, blocked = _failing_clauses(gate, word, failing)
        found[gate] = VerdictRow(
            verdict=word,
            clauses=clauses,
            limitations=_travelling(gate, travelling),
            blocked=blocked,
        )
    return found


def accepted_clauses(text: str) -> dict[str, str]:
    """ADR 0021 D3's accepted FAIL clauses: clause → the acceptance cell (with its date)."""
    found: dict[str, str] = {}
    for header, rows in _tables(text):
        lowered = [_bare(cell).lower() for cell in header]
        if "frank's acceptance" not in lowered:
            continue
        column = lowered.index("frank's acceptance")
        for cells in rows:
            match = CLAUSE.match(_bare(cells[0])) if cells else None
            acceptance = cells[column] if column < len(cells) else ""
            if match and DATE.search(acceptance):
                found[match.group(0)] = acceptance
    return found


def envelope_limitations(document: Mapping[str, Any]) -> set[str]:
    return {str(entry["id"]) for entry in document.get("limitations", [])}


def _rc_outcome(result: str) -> str:
    """One row's `Result` cell: `failed`, `passed`, `none` (a bare `—`) or `unstated`, read by its
    status head (T08 review 3, Ruling 3; the module docstring)."""
    end = RC_HEAD_END.search(result)
    head = result[: end.start()] if end else result
    words = re.split(r"[/\s]+", re.sub(r'[*`"]', "", head))
    status = [word for word in words if word in RC_STATUS_WORDS]
    if RC_FAILED.search(result) or any(word not in RC_PASS_WORDS for word in status):
        return "failed"
    count = RC_COUNT.match(result, len(head))
    if status and (count is None or int(count.group(1)) == int(count.group(2))):
        return "passed"
    return "none" if _bare(result) == NONE else "unstated"


def rc_record_problems(text: str | None, rc: str) -> list[str]:
    """Why the RC record does not show `rc` to be a release candidate (§8.1 item 4); empty if it
    does. Read by column; anything off the form is a problem, never a guess."""
    where = f"{RC_RECORD} (§8.1 item 4)"
    if text is None:
        return [f"no RC record: {RC_RECORD} does not exist (§8.1 item 4)"]
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
        if not step.isdigit() or not 1 <= int(step) <= 11 or len(cells) != len(header):
            problems.append(f"{where}: unreadable row {cells[:2]}")
            continue
        outcome = _rc_outcome(cells[column])
        outcomes.setdefault(int(step), []).append(outcome)
        if int(step) in RC_STEPS and outcome in ("failed", "unstated"):
            said = "failed" if outcome == "failed" else "not stated as passed"
            problems.append(
                f"§8.2 step {step} ({_bare(cells[1])}, {_bare(cells[2])}): {said} in {where}"
            )
    for step in RC_STEPS:
        if "passed" not in outcomes.get(step, []):
            problems.append(f"§8.2 step {step}: no row of {where} states that it passed")
    return problems


def rc_manifest_problems(manifest: Mapping[str, Any] | None, rc: str) -> list[str]:
    """Why `evidence/T08/<rc>/manifest.json` does not meet §8.1 item 5; empty if it does."""
    path = EVIDENCE / rc / "manifest.json"
    if manifest is None:
        return [f"no T08 manifest: {path} does not exist (§8.1 item 5)"]
    problems = []
    if manifest.get("work_package") != "T08" or manifest.get("commit") != rc:
        problems.append(
            f"{path} is the manifest of {manifest.get('work_package')} at "
            f"{manifest.get('commit')}, not of T08 at {rc} (§8.1 item 5)"
        )
    if manifest.get("status") not in MANIFEST_STATUSES:
        problems.append(f"{path} has status {manifest.get('status')!r}, not `tested` (§8.1 item 5)")
    return problems


# -- judging what was read ----------------------------------------------------------------------


@dataclass
class GateLine:
    gate: str
    requirement: str
    ledger: str | None
    document: VerdictRow | None
    accepted: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def releasable(self) -> bool:
        return not self.problems


def judge_gate(
    gate: str,
    entry: Mapping[str, Any],
    row: VerdictRow | None,
    accepted: Mapping[str, str],
    known_limitations: set[str],
) -> GateLine:
    line = GateLine(
        gate=gate,
        requirement=str(entry["required_evidence"]),
        ledger=entry.get("verdict"),
        document=row,
        accepted={c: a for c, a in accepted.items() if c.startswith(gate + " ")},
    )
    if line.ledger is None:
        line.problems.append("no verdict in the ledger (D2.1)")
    if row is None:
        line.problems.append(f"no row in {VERDICT_DOCUMENT} (D2.1)")
    elif line.ledger is not None and row.verdict != line.ledger:
        line.problems.append(f"ledger {line.ledger} but {VERDICT_DOCUMENT} {row.verdict}")
    if row is not None:
        unknown = [lid for lid in row.limitations if lid not in known_limitations]
        if unknown:
            line.problems.append(f"limitation ids not in {ENVELOPE}: {unknown}")
    if "BLOCKED" in (line.ledger, row.verdict if row else None):
        line.problems.append("BLOCKED blocks the tag (D2.2)")
    if "FAIL" in (line.ledger, row.verdict if row else None):
        clauses = row.clauses if row else ()
        if not clauses:
            line.problems.append("a FAIL that names no clause (T08.A03)")
        unaccepted = [clause for clause in clauses if clause not in accepted]
        if unaccepted:
            line.problems.append(f"FAIL clause not accepted in ADR 0021 D3: {unaccepted} (D2.3)")
    return line


# -- the tree check (D2.4) -------------------------------------------------------------------


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def has_commit(commit: str) -> bool:
    try:
        git("cat-file", "-e", f"{commit}^{{commit}}")
    except subprocess.CalledProcessError:
        return False
    return True


def tree(commit: str) -> dict[str, str]:
    listing = git("ls-tree", "-r", commit, "--", *TREES).decode("utf-8")
    entries: dict[str, str] = {}
    for line in listing.splitlines():
        meta, path = line.split("\t", 1)
        mode, _, blob = meta.split()
        entries[path] = f"{mode} {blob}"
    return entries


def version_at(commit: str) -> str:
    document = tomllib.loads(git("show", f"{commit}:pyproject.toml").decode("utf-8"))
    return str(document["project"]["version"])


def tree_differences(rc: str, candidate: str) -> list[str]:
    """Paths under `TREES` where `candidate` differs from `rc`, beyond the version string in the
    two files that declare it. Read from git where `rc` is in the repository, else from its
    recorded file hashes (R-151)."""
    if not has_commit(rc):
        return recorded_tree_differences(tree_record_of(rc), candidate)
    ours, theirs = tree(rc), tree(candidate)
    rc_version, candidate_version = version_at(rc), version_at(candidate)
    differing: list[str] = []
    for path in sorted(set(ours) | set(theirs)):
        if ours.get(path) == theirs.get(path):
            continue
        if path in VERSION_FILES and path in ours and path in theirs:
            before = git("show", f"{rc}:{path}")
            after = git("show", f"{candidate}:{path}")
            quoted = (f'"{candidate_version}"'.encode(), f'"{rc_version}"'.encode())
            if after.count(quoted[0]) == 1 and after.replace(*quoted) == before:
                continue
        differing.append(path)
    return differing


# -- C's recorded tree (R-151) -----------------------------------------------------------------


def _contents(entries: Mapping[str, str]) -> dict[str, bytes]:
    """The content of each `path → "mode blob"` entry of `tree`, read by one `git cat-file`."""
    paths = sorted(entries)
    blobs = [entries[path].split()[1] for path in paths]
    out = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=ROOT,
        input="".join(f"{blob}\n" for blob in blobs).encode(),
        capture_output=True,
        check=True,
    ).stdout
    contents: dict[str, bytes] = {}
    at = 0
    for path, blob in zip(paths, blobs, strict=True):
        end = out.index(b"\n", at)
        name, kind, size = out[at:end].decode().split()
        if name != blob or kind != "blob":
            raise ValueError(f"{path}: git cat-file gave {name} {kind}, not the blob {blob}")
        contents[path] = out[end + 1 : end + 1 + int(size)]
        at = end + 1 + int(size) + 1
    return contents


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def tree_record(commit: str) -> dict[str, Any]:
    """`commit`'s record (R-151): the mode and sha256 of every file under `TREES`, its version,
    and the lines of the two version files where the version occurs."""
    entries = tree(commit)
    contents = _contents(entries)
    version = version_at(commit)
    quoted = f'"{version}"'
    return {
        "commit": commit,
        "committer_time": int(git("log", "-1", "--format=%ct", commit).strip()),
        "version": version,
        "version_occurrences": {
            path: [line for line in contents[path].decode("utf-8").splitlines() if quoted in line]
            for path in VERSION_FILES
            if path in contents
        },
        "trees": list(TREES),
        "files": {
            path: f"{entries[path].split()[0]} {_sha256(contents[path])}" for path in entries
        },
    }


def tree_record_of(rc: str) -> dict[str, Any]:
    """`release/rc-trees/<rc>.json`, which must be `rc`'s record over the current `TREES`."""
    path = ROOT / RC_TREES / f"{rc}.json"
    if not path.is_file():
        raise ValueError(
            f"C = {rc} is not in this repository and {RC_TREES / path.name} does not exist"
        )
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if record.get("commit") != rc or record.get("trees") != list(TREES):
        raise ValueError(f"{RC_TREES / path.name} is not the record of {rc} over {list(TREES)}")
    return record


def recorded_tree_differences(record: Mapping[str, Any], candidate: str) -> list[str]:
    """`tree_differences` against `C`'s record: the same rule, a file compared by mode and sha256
    where git compares mode and blob id."""
    ours: Mapping[str, str] = record["files"]
    entries = tree(candidate)
    contents = _contents(entries)
    theirs = {path: f"{entries[path].split()[0]} {_sha256(contents[path])}" for path in entries}
    rc_version, candidate_version = str(record["version"]), version_at(candidate)
    differing: list[str] = []
    for path in sorted(set(ours) | set(theirs)):
        if ours.get(path) == theirs.get(path):
            continue
        if path in VERSION_FILES and path in ours and path in theirs:
            after = contents[path]
            quoted = (f'"{candidate_version}"'.encode(), f'"{rc_version}"'.encode())
            if (
                after.count(quoted[0]) == 1
                and _sha256(after.replace(*quoted)) == ours[path].split()[1]
            ):
                continue
        differing.append(path)
    return differing


def resolve_rc(name: str) -> str:
    """`--rc`'s full commit id: from git, or else a unique prefix of a recorded `C` (R-151)."""
    try:
        return git("rev-parse", "--verify", "--quiet", f"{name}^{{commit}}").decode().strip()
    except subprocess.CalledProcessError:
        pass
    recorded = sorted(path.stem for path in (ROOT / RC_TREES).glob("*.json"))
    found = [
        commit
        for commit in recorded
        if re.fullmatch(r"[0-9a-f]{4,40}", name) and commit.startswith(name)
    ]
    if len(found) != 1:
        raise ValueError(
            f"--rc {name}: not a commit of this repository, nor of one record in {RC_TREES}"
        )
    return found[0]


def recorded_rc() -> str | None:
    """The commit of the newest `tested` or `reviewed` T08 manifest, if there is one; a commit
    not in the repository is dated by its record (R-151)."""
    found: list[tuple[int, str]] = []
    for path in sorted((ROOT / EVIDENCE).glob("*/manifest.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("status") in ("tested", "reviewed"):
            commit = str(document["commit"])
            if has_commit(commit):
                time = int(git("log", "-1", "--format=%ct", commit).strip())
            else:
                time = int(tree_record_of(commit)["committer_time"])
            found.append((time, commit))
    return max(found)[1] if found else None


# -- the report -------------------------------------------------------------------------------


def build(
    *,
    ledger: Mapping[str, Any],
    verdict_text: str | None,
    adr_text: str,
    envelope: Mapping[str, Any],
    rc: str | None,
    candidate: str,
    version: str,
    differences: Sequence[str] | None,
    rc_record: str | None,
    rc_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    gates = ledger_gates(ledger)
    rows = verdict_rows(verdict_text) if verdict_text is not None else {}
    accepted = accepted_clauses(adr_text)
    known = envelope_limitations(envelope)
    lines = [judge_gate(g, gates[g], rows.get(g), accepted, known) for g in GATES]
    reasons = [f"{line.gate}: {problem}" for line in lines for problem in line.problems]
    if verdict_text is None:
        reasons.insert(0, f"{VERDICT_DOCUMENT} does not exist (T08.A03)")
    if V0_1_LINE.match(version) is None:
        reasons.append(f"version {version} is not on the 0.1 line: the v0.1 gates do not cover it")
    record_problems = None if rc is None else rc_record_problems(rc_record, rc)
    manifest_problems = None if rc is None else rc_manifest_problems(rc_manifest, rc)
    if rc is None:
        reasons.append("no release candidate recorded (no tested evidence/T08/<C>/manifest.json)")
    else:
        if differences:
            reasons.append(
                f"candidate {candidate[:12]} differs from C in {list(differences)} (D2.4)"
            )
        reasons.extend(record_problems or [])
        reasons.extend(manifest_problems or [])
    return {
        "rc": rc,
        "candidate": candidate,
        "version": version,
        "gates": [
            {
                "gate": line.gate,
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
        "rc_record_problems": record_problems,
        "rc_manifest_problems": manifest_problems,
        "tag_may_be_proposed": not reasons,
        "reasons": reasons,
    }


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
            f"{clause} FAIL, accepted by Frank {date.group(0) if date else ''} (ADR 0021 D3)"
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
        lines.append(
            f"| {entry['gate']} | {_verdict_word(entry)} | {entry['requirement']} | "
            f"{_notes(entry) or '—'} |"
        )
    return "\n".join(lines) + "\n"


def text(report: Mapping[str, Any]) -> str:
    out = [f"v0.1 gates at C = {report['rc'] or 'not recorded'}; candidate {report['candidate']}"]
    for entry in report["gates"]:
        out.append(f"{entry['gate']}  {_verdict_word(entry):<11}{entry['requirement']}")
        notes = _notes(entry)
        if notes:
            out.append(f"      {notes}")
        for problem in entry["problems"]:
            out.append(f"      not releasable: {problem}")
    differences = report["tree_differences"]
    out.append("")
    if differences is None:
        out.append("tree check (D2.4): not run — no release candidate recorded")
    else:
        out.append(
            "tree check (D2.4): "
            + ("equal to C" if not differences else f"differs in {len(differences)} paths")
        )
    problems = report["rc_record_problems"]
    if problems is None:
        out.append("RC record (§8.1 item 4): not read — no release candidate recorded")
    else:
        out.append(
            "RC record (§8.1 item 4): "
            + (
                f"steps {RC_STEPS[0]}–{RC_STEPS[-1]} passed at C"
                if not problems
                else f"{len(problems)} problems"
            )
        )
    manifest = report["rc_manifest_problems"]
    if manifest is None:
        out.append("T08 manifest (§8.1 item 5): not read — no release candidate recorded")
    else:
        out.append(
            "T08 manifest (§8.1 item 5): "
            + ("`tested` at C" if not manifest else f"{len(manifest)} problems")
        )
    out.append(
        f"v{report['version']} tag may be proposed: "
        + ("YES" if report["tag_may_be_proposed"] else f"NO ({len(report['reasons'])} reasons)")
    )
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rc", default=None, help="the release candidate C (default: recorded)")
    parser.add_argument("--candidate", default="HEAD", help="the tag candidate (default HEAD)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--markdown", action="store_true")
    output.add_argument(
        "--write-tree-record",
        action="store_true",
        help=f"write {RC_TREES}/<C>.json for --rc C, which must be in the repository (R-151)",
    )
    arguments = parser.parse_args()

    try:
        candidate = git("rev-parse", f"{arguments.candidate}^{{commit}}").decode().strip()
        rc = arguments.rc or recorded_rc()
        if rc is not None:
            rc = resolve_rc(rc)
        if arguments.write_tree_record:
            if rc is None or not has_commit(rc):
                raise ValueError("--write-tree-record needs --rc, a commit of this repository")
            path = ROOT / RC_TREES / f"{rc}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(tree_record(rc), indent=1, sort_keys=True) + "\n", "utf-8")
            print(f"wrote {RC_TREES / path.name}")
            return 0
        verdicts = ROOT / VERDICT_DOCUMENT
        record = ROOT / RC_RECORD
        manifest = None if rc is None else ROOT / EVIDENCE / rc / "manifest.json"
        report = build(
            ledger=yaml.safe_load((ROOT / LEDGER).read_text(encoding="utf-8")),
            verdict_text=verdicts.read_text(encoding="utf-8") if verdicts.is_file() else None,
            adr_text=(ROOT / ADR_0021).read_text(encoding="utf-8"),
            envelope=yaml.safe_load((ROOT / ENVELOPE).read_text(encoding="utf-8")),
            rc=rc,
            candidate=candidate,
            version=version_at(candidate),
            differences=None if rc is None else tree_differences(rc, candidate),
            rc_record=record.read_text(encoding="utf-8") if record.is_file() else None,
            rc_manifest=(
                json.loads(manifest.read_text(encoding="utf-8"))
                if manifest is not None and manifest.is_file()
                else None
            ),
        )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    elif arguments.markdown:
        print(markdown(report), end="")
    else:
        print(text(report), end="")
        for reason in report["reasons"]:
            if not reason.startswith(GATES):  # each gate's own reasons are printed under it
                print(f"  - {reason}")
    return 0 if report["tag_may_be_proposed"] else 1


if __name__ == "__main__":
    sys.exit(main())
