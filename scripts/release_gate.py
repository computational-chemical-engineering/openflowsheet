"""The generic release gate: a line file's gate set, read at the tag candidate.

The standing release procedure (RP, `docs/derivations/release-procedure.md`) §3 and §8; ADR 0055
D1.2, D1.3 and D3. From the 0.4 line on, one script gates every minor line:
`release/lines/<M>.<m>.json` (format `release-line-v1`) holds the line's gate set, and this script
runs `scripts/v0_2_gate.py`'s engine with it, imported and not copied, as `scripts/v0_3_gate.py`
does with its registry. It judges nothing: every verdict is read from where the design lane
records it, and decides whether a tag `v<version>` may be **proposed** to Frank (the tag is his,
ADR 0021 D5).

**The line file** is read in the candidate's tree, with the line files it inherits, and refused
with exit 2 when any of RP's checks RP.L01–RP.L10 fails (§3.4): the schema, the stem and an
acyclic `inherits` chain, `changed` exact in both directions against the inherited line (§3.2,
REL.A01), the `tests` globs and the `criteria`, `documents` and `scripts` paths at `C` (RP.L05,
RP.L08), the keys of `gates`, the `rc` pairs, the clause grammar, and the decision items. Its
`gate_set` is the engine's `GateSet`, with `acceptances` in the place of `policy_adr`. Every line
admits post-releases as the legacy lines do (RP §7.5, R-922).

**Two modes**, by the acceptances file the gate set names:

- **dated** (no `Scope` column; the 0.3 line's ADR 0053): the engine runs unchanged, so the report
  is `scripts/v0_3_gate.py`'s byte for byte (REL.A03);
- **standing** (`release/acceptances.md`, from the 0.4 line on; RP §8): a row of either table
  stands at `C` iff its answer cell passes the cell rule, and its scope, evaluated at `C` by RP
  §8.2, has the recorded `Fingerprint`. A row that does not is lapsed and counts as absent. A
  standing row's date may precede `Judged`. A new row, whose `Accepted at` is `C` itself (RP §8.4),
  is dated: a failure clause on or after `Judged` (and Table T7's bound), a decision item on or
  after the lapse report's date. Decision items 1–12 are otherwise the engine's. The report lists
  every standing row used, every lapsed row with its terms, and every unused row.

Item 13 (the carry check, ADR 0055 D2) does not exist while D2 is deferred (RP.S06): the scope term
`gate_row:<g>` is always `unsupported`, and nothing is carried.

    PYTHONPATH=src .venv/bin/python scripts/release_gate.py --line M.m --rc C [--candidate R]
    PYTHONPATH=src .venv/bin/python scripts/release_gate.py --line M.m --rc C --markdown
    PYTHONPATH=src .venv/bin/python scripts/release_gate.py --line M.m --rc C --lapses   # RP §8.5
    PYTHONPATH=src .venv/bin/python scripts/release_gate.py --line M.m --rc C --write-tree-record
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Final, Protocol

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
# ADR 0055 D1.3: the v0.2 engine, imported and not copied; it is not edited.
import v0_2_gate as engine  # noqa: E402
from v0_1_gate import (  # noqa: E402
    _bare,
    _tables,
    git,
    has_commit,
    resolve_rc,
    tree_differences,
    tree_record_of,
    version_at,
)
from v0_2_gate import (  # noqa: E402
    ENVELOPE,
    LEDGER,
    LINKS_MODULE,
    GateLine,
    GateSet,
    Policy,
    ReleaseLine,
    acceptance_date,
)

ROOT: Final = engine.ROOT
LINES: Final = "release/lines"
SCHEMA: Final = f"{LINES}/release-line-v1.schema.json"
LINE_NAME: Final = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
#: RP §3.1: the 18 `GateSet` fields, `policy_adr` renamed `acceptances`, in the engine's order.
GATE_SET_FIELDS: Final = (
    "name",
    "covers",
    "claimed",
    "not_claimed",
    "clause",
    "acceptances",
    "verdict_document",
    "rc_record",
    "rc_steps",
    "rc_last_step",
    "evidence_package",
    "packages",
    "envelope_id",
    "required_adrs",
    "frank_items",
    "rejudge_waits",
    "links_item",
    "specification_texts",
)
#: RP §3.2: the fields compared with the inherited line's.
COMPARED: Final = (
    *(f"gate_set.{name}" for name in GATE_SET_FIELDS),
    "gates",
    "rc_items",
    "changelog_what_it_is_not",
)
#: RP §3.3: the RC step whose `rc` pairs name `rc_items` ids.
ITEMS_STEP: Final = 17
#: RP §8.5: the lapse report, `evidence/<pkg>/<C>/acceptance-lapses.txt`.
LAPSES: Final = "acceptance-lapses.txt"
LAPSES_HEADER: Final = re.compile(
    r"acceptance lapses at C = ([0-9a-f]{40}), (\d{4}-\d{2}-\d{2})(?![0-9])"
)
GATE_ROW_DEFERRED: Final = "gate_row needs the evidence fingerprint, ADR 0055 D2, deferred"


class LineError(ValueError):
    """A line file the gate refuses, with RP §3.4's reason (exit 2)."""


# -- the line file (RP §3) --------------------------------------------------------------------


def line_path(name: str) -> str:
    return f"{LINES}/{name}.json"


def gate_set_of_entry(entry: Mapping[str, Any]) -> GateSet:
    """The engine's `GateSet` for a line file's `gate_set` (RP §3.1: `acceptances` is
    `policy_adr`; patterns are compiled, arrays are tuples)."""
    texts = entry["specification_texts"]
    return GateSet(
        name=entry["name"],
        covers=re.compile(entry["covers"]),
        claimed=tuple(entry["claimed"]),
        not_claimed=tuple(entry["not_claimed"]),
        clause=re.compile(entry["clause"]),
        policy_adr=entry["acceptances"],
        verdict_document=entry["verdict_document"],
        rc_record=entry["rc_record"],
        rc_steps=tuple(entry["rc_steps"]),
        rc_last_step=entry["rc_last_step"],
        evidence_package=entry["evidence_package"],
        packages=tuple(entry["packages"]),
        envelope_id=entry["envelope_id"],
        required_adrs=tuple(entry["required_adrs"]),
        frank_items=tuple(entry["frank_items"]),
        rejudge_waits=tuple((gate, item) for gate, item in entry["rejudge_waits"]),
        links_item=entry["links_item"],
        specification_texts=None if texts is None else (texts[0], texts[1]),
    )


class StandingGateSet(GateSet):
    """A gate set read in standing mode: the reports name its acceptances file, not an ADR."""

    @property
    def adr(self) -> str:
        return self.policy_adr


@dataclass(frozen=True)
class Line:
    """A loaded line file: the judged line's document, then each line it inherits, to the root."""

    chain: tuple[Mapping[str, Any], ...]

    @property
    def document(self) -> Mapping[str, Any]:
        return self.chain[0]

    @property
    def name(self) -> str:
        return str(self.document["line"])

    @property
    def gate_set(self) -> GateSet:
        return gate_set_of_entry(self.document["gate_set"])

    def release(self, *, standing: bool = False) -> ReleaseLine:
        """The engine's `ReleaseLine` for this line: `v<M>.<m>`, one gate set, post-releases."""
        gate_set = self.gate_set
        if standing:
            gate_set = StandingGateSet(
                **{f.name: getattr(gate_set, f.name) for f in fields(GateSet)}
            )
        description = (__doc__ or "").splitlines()[0]
        return ReleaseLine(f"v{self.name}", (gate_set,), description, post_releases=True)


def _compared(document: Mapping[str, Any], name: str) -> tuple[bool, Any]:
    """`(present, value)` of a compared field (RP §3.2)."""
    if name.startswith("gate_set."):
        entry = document.get("gate_set", {})
        key = name.removeprefix("gate_set.")
        return key in entry, entry.get(key)
    return name in document, document.get(name)


def _schema_problem(document: Any, schema: Mapping[str, Any]) -> str | None:
    error = jsonschema.exceptions.best_match(
        jsonschema.Draft202012Validator(schema).iter_errors(document)
    )
    if error is None:
        return None
    at = "/".join(str(part) for part in error.absolute_path) or "(the document)"
    return f"{at}: {error.message}"


def load_line(name: str, read: Callable[[str], bytes | None]) -> Line:
    """The line file `name` and the line files it inherits, each read by `read` (the candidate's
    tree), checked by RP.L01–RP.L04, RP.L06, RP.L07, RP.L09, RP.L10 and RP.L08's unique ids.
    RP.L05 and RP.L08's scripts are `tree_problems`', at `C`. A failed check is a `LineError`."""
    if not LINE_NAME.fullmatch(name):
        raise LineError(f"--line {name!r} is not <major>.<minor>")
    schema_text = read(SCHEMA)
    if schema_text is None:
        raise LineError(f"{SCHEMA} does not exist at the candidate")
    schema = json.loads(schema_text)
    chain: list[Mapping[str, Any]] = []
    current: str | None = name
    while current is not None:
        if current in [document["line"] for document in chain]:
            path = " -> ".join([*(str(document["line"]) for document in chain), current])
            raise LineError(f"line {name}: RP.L02: the inherits chain {path} is a cycle")
        text = read(line_path(current))
        if text is None:
            raise LineError(f"line {current}: {line_path(current)} does not exist at the candidate")
        try:
            document = json.loads(text)
        except json.JSONDecodeError as error:
            raise LineError(f"line {current}: RP.L01: not JSON: {error}") from None
        problem = _schema_problem(document, schema)
        if problem is not None:
            raise LineError(f"line {current}: RP.L01: not release-line-v1: {problem}")
        if document["line"] != current:
            raise LineError(
                f"line {current}: RP.L02: `line` is {document['line']!r}, not the file's stem"
            )
        chain.append(document)
        current = document["inherits"]
    problems: list[str] = []
    for child, parent in zip(chain, chain[1:], strict=False):
        problems += inheritance_problems(child, parent)
    line = Line(tuple(chain))
    problems += line_problems(line, read)
    if problems:
        raise LineError("\n".join(problems))
    return line


def inheritance_problems(child: Mapping[str, Any], parent: Mapping[str, Any]) -> list[str]:
    """RP.L03 (REL.A01) and RP.L04: `changed` names exactly the compared fields that differ."""
    problems = []
    named, at, of = set(child["changed"]), child["line"], parent["line"]
    for name in COMPARED:
        differs = _compared(child, name) != _compared(parent, name)
        if differs and name not in named:
            problems.append(f"line {at}: field {name} differs from {of} and is not in changed")
        elif not differs and name in named:
            problems.append(f"line {at}: field {name} is in changed but equals {of}'s")
    return problems


def line_problems(line: Line, read: Callable[[str], bytes | None]) -> list[str]:
    """RP.L06, RP.L07, RP.L08's unique ids, RP.L09 and RP.L10, on the judged line."""
    document, at = line.document, f"line {line.name}"
    entry = document["gate_set"]
    claimed, not_claimed = list(entry["claimed"]), list(entry["not_claimed"])
    gates: Mapping[str, Any] = document.get("gates", {})
    items: Sequence[Mapping[str, Any]] = document.get("rc_items", [])
    problems = []
    if document["role"] == "gate" and set(gates) != set(claimed):
        problems.append(
            f"{at}: RP.L06: the keys of gates are not the claimed gates: missing "
            f"{sorted(set(claimed) - set(gates))}, extra {sorted(set(gates) - set(claimed))}"
        )
    ids = [item["id"] for item in items]
    for gate, lists in gates.items():
        for step, check in lists["rc"]:
            if step not in entry["rc_steps"]:
                problems.append(
                    f"{at}: RP.L07: {gate} rc [{step}, {check!r}]: not an rc_steps step"
                )
            elif step == ITEMS_STEP and check not in ids:
                problems.append(f"{at}: RP.L07: {gate} rc [{step}, {check!r}]: not an rc_items id")
            elif step != ITEMS_STEP and check in ids:
                problems.append(
                    f"{at}: RP.L07: {gate} rc [{step}, {check!r}]: an rc_items id at step {step}"
                )
    duplicated = sorted({item for item in ids if ids.count(item) > 1})
    if duplicated:
        problems.append(f"{at}: RP.L08: rc_items ids {duplicated} are not unique")
    clause = re.compile(entry["clause"])
    for gate in claimed:
        if not clause.fullmatch(f"{gate} (a)"):
            problems.append(f"{at}: RP.L09: the clause grammar does not parse '{gate} (a)'")
    for gate in not_claimed:
        if clause.fullmatch(f"{gate} (a)"):
            problems.append(f"{at}: RP.L09: the clause grammar parses '{gate} (a)', not claimed")
    frank = list(entry["frank_items"])
    text = read(entry["acceptances"])
    answers, why = engine.frank_table(
        "" if text is None else text.decode("utf-8"), "frank's answer"
    )
    if answers is None:
        problems.append(f"{at}: RP.L10: {entry['acceptances']}: {why}")
    else:
        for item in frank:
            count = sum(first == item for first, _ in answers)
            if count != 1:
                problems.append(
                    f"{at}: RP.L10: {count} rows {item!r} in {entry['acceptances']}, not 1"
                )
    if entry["links_item"] is not None and entry["links_item"] not in frank:
        problems.append(f"{at}: RP.L10: links_item {entry['links_item']!r} is not a frank item")
    for gate, item in entry["rejudge_waits"]:
        if item not in frank:
            problems.append(f"{at}: RP.L10: rejudge_waits [{gate}, {item}]: not a frank item")
        if gate not in claimed:
            problems.append(f"{at}: RP.L10: rejudge_waits [{gate}, {item}]: {gate} is not claimed")
    return problems


def tree_problems(line: Line, paths: Sequence[str]) -> list[str]:
    """RP.L05 and RP.L08 at `C`, whose tracked paths are `paths`: every `tests` glob matches one,
    every `criteria` and `documents` path is one or a directory of them, every script is one."""
    at, tracked = f"line {line.name}", set(paths)
    directories = {path.rsplit("/", n)[0] for path in paths for n in range(1, path.count("/") + 1)}
    problems = []
    for gate, lists in line.document.get("gates", {}).items():
        for glob in lists["tests"]:
            pattern = glob_pattern(glob)
            if not any(pattern.fullmatch(path) for path in paths):
                problems.append(f"{at}: RP.L05: {gate} tests {glob}: matches no tracked file at C")
        for kind in ("criteria", "documents"):
            for path in lists[kind]:
                if path not in tracked and path not in directories:
                    problems.append(f"{at}: RP.L05: {gate} {kind} {path}: does not exist at C")
    for item in line.document.get("rc_items", []):
        if item["script"] not in tracked:
            problems.append(f"{at}: RP.L08: {item['id']} script {item['script']}: not at C")
    return problems


# -- scope terms and fingerprints (RP §8.2) ---------------------------------------------------


def glob_pattern(glob: str) -> re.Pattern[str]:
    """RP §8.2 (P1): `**` is any sequence, `*` any sequence without `/`, `?` one character other
    than `/`, every other character itself; a glob matches a whole repository-relative path."""
    parts = []
    for token in re.findall(r"\*\*|\*|\?|[^*?]+", glob):
        parts.append({"**": ".*", "*": "[^/]*", "?": "[^/]"}.get(token, re.escape(token)))
    return re.compile("".join(parts), re.DOTALL)


def _sorted_lists(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted_lists(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((_sorted_lists(item) for item in value), key=canonical_json)
    return value


def canonical_json(value: Any) -> bytes:
    """RP §8.2 (D2.2's rule): sorted keys, no spaces, UTF-8, every list sorted by the UTF-8 bytes
    of its elements' own canonical JSON."""
    return json.dumps(
        _sorted_lists(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Trees(Protocol):
    """The repository's trees, read by commit."""

    def entries(self, commit: str) -> tuple[bytes, ...] | None:
        """`git ls-tree -r -z --full-tree <commit>`'s records, or `None` if there is no commit."""

    def read(self, commit: str, path: str) -> bytes | None:
        """`path`'s content at `commit`, or `None`."""


class GitTrees:
    """`Trees` read with git in the repository at `root`, each answer kept."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self._entries: dict[str, tuple[bytes, ...] | None] = {}
        self._read: dict[tuple[str, str], bytes | None] = {}

    def _git(self, *arguments: str) -> bytes | None:
        result = subprocess.run(["git", *arguments], cwd=self.root, capture_output=True)
        return result.stdout if result.returncode == 0 else None

    def entries(self, commit: str) -> tuple[bytes, ...] | None:
        if commit not in self._entries:
            listing = self._git("ls-tree", "-r", "-z", "--full-tree", f"{commit}^{{commit}}")
            self._entries[commit] = (
                None if listing is None else tuple(r for r in listing.split(b"\0") if r)
            )
        return self._entries[commit]

    def read(self, commit: str, path: str) -> bytes | None:
        if (commit, path) not in self._read:
            self._read[commit, path] = self._git("show", f"{commit}:{path}")
        return self._read[commit, path]


def record_path(record: bytes) -> str:
    return record.split(b"\t", 1)[1].decode("utf-8", "surrogateescape")


@dataclass(frozen=True)
class TermValue:
    """A scope term evaluated at a commit: its hash, or why it is `unsupported`."""

    term: str
    digest: str | None
    reason: str = ""
    #: A `paths:` term's selected records (RP §8.2, P2).
    records: frozenset[bytes] = frozenset()


EXTRACTORS: Final = ("claim_set", "links", "served_digest")


def scope_terms(scope: str) -> list[str]:
    """A scope's terms (RP §8.2), each well-formed; a `ValueError` otherwise."""
    terms = scope.split(" + ")
    for term in terms:
        kind, _, argument = term.partition(":")
        if kind == "paths":
            globs = argument.split(",")
            if not argument or any(not glob or " " in glob for glob in globs):
                raise ValueError(f"scope term {term!r}: not paths:<glob>,<glob>,…")
        elif kind == "extract":
            extra = argument.removeprefix("pyproject_extra:")
            if argument not in EXTRACTORS and (extra == argument or not extra):
                raise ValueError(f"scope term {term!r}: not a registered extractor (RP §8.2)")
        elif kind != "gate_row" or not argument:
            raise ValueError(f"scope term {term!r}: not paths:, extract: or gate_row:")
    return terms


def fingerprint(values: Sequence[TermValue]) -> str | None:
    """RP §8.2 (F1): SHA-256 of the term hashes joined by `\\n`; `None` if one is unsupported."""
    digests = [value.digest for value in values]
    if any(digest is None for digest in digests):
        return None
    return _sha256("\n".join(digest for digest in digests if digest).encode("ascii"))


class Scopes:
    """RP §8.2 evaluated for the judged `line` at `C` = `rc`, reading the candidate's tree for
    the line files and RC records the extractors name."""

    def __init__(self, trees: Trees, line: Line, rc: str, candidate: str) -> None:
        self.trees, self.line, self.rc, self.candidate = trees, line, rc, candidate

    def gate_set_at(self, commit: str) -> Mapping[str, Any]:
        """E1's line at `commit`: the judged line at `C`; elsewhere the newest line of the chain
        whose file `commit` holds, or else the chain's root, read in the candidate's tree (the
        seed rule: `a3e508e3` has no line file and reads `release/lines/0.3.json`)."""
        if commit == self.rc:
            return dict(self.line.document["gate_set"])
        for document in self.line.chain:
            text = self.trees.read(commit, line_path(document["line"]))
            if text is not None:
                try:
                    return dict(json.loads(text)["gate_set"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    break
        return dict(self.line.chain[-1]["gate_set"])

    def term(self, term: str, at: str) -> TermValue:
        kind, _, argument = term.partition(":")
        if kind == "paths":
            return self._paths(term, argument.split(","), at)
        if kind == "gate_row":
            return TermValue(term, None, GATE_ROW_DEFERRED)
        try:
            value = self._extract(argument, at)
        except LookupError as error:
            return TermValue(term, None, str(error.args[0]))
        return TermValue(term, _sha256(canonical_json(value)))

    def _paths(self, term: str, globs: Sequence[str], at: str) -> TermValue:
        entries = self.trees.entries(at)
        if entries is None:
            return TermValue(term, None, f"{at} is not a commit of this repository")
        selected: set[bytes] = set()
        for glob in globs:
            pattern = glob_pattern(glob)
            matched = {record for record in entries if pattern.fullmatch(record_path(record))}
            if not matched:
                return TermValue(term, None, f"paths:{glob} matches no tracked file at {at}")
            selected |= matched
        digest = _sha256(b"".join(record + b"\n" for record in sorted(selected)))
        return TermValue(term, digest, records=frozenset(selected))

    def _extract(self, name: str, at: str) -> Any:
        """E1–E4's value at `at`; a `LookupError` with the reason it is unsupported."""
        if name == "claim_set":
            entry = self.gate_set_at(at)
            return {"claimed": list(entry["claimed"]), "not_claimed": list(entry["not_claimed"])}
        if name.startswith("pyproject_extra:"):
            extra = name.removeprefix("pyproject_extra:")
            text = self.trees.read(at, "pyproject.toml")
            if text is None:
                raise LookupError(f"no pyproject.toml at {at}")
            extras = tomllib.loads(text.decode("utf-8")).get("project", {})
            requirements = extras.get("optional-dependencies", {}).get(extra)
            if not isinstance(requirements, list):
                raise LookupError(f"pyproject.toml has no optional-dependencies.{extra} at {at}")
            return requirements
        if name == "links":
            text = self.trees.read(at, LINKS_MODULE)
            if text is None:
                raise LookupError(f"no {LINKS_MODULE} at {at}")
            try:
                return list(engine.link_registers(text.decode("utf-8")))
            except (SyntaxError, ValueError) as error:
                raise LookupError(f"links at {at}: {error}") from None
        return self._served_digest(at)

    def _served_digest(self, at: str) -> str:
        """E4: the `found` of the item-1 chain entry of every step-8 record listed in
        `evidence/<pkg>/<at>/rc/records.json`, in the candidate's tree; all equal."""
        base = f"evidence/{self.gate_set_at(at)['evidence_package']}/{at}/rc"
        listing = self.trees.read(self.candidate, f"{base}/records.json")
        if listing is None:
            raise LookupError(f"no {base}/records.json in the candidate's tree")
        found: dict[str, str] = {}
        for listed in json.loads(listing).get("files", []):
            path = str(listed.get("path", ""))
            text = (
                self.trees.read(self.candidate, f"{base}/{path}")
                if path.endswith(".json")
                else None
            )
            try:
                record = json.loads(text) if text is not None else None
            except json.JSONDecodeError:
                record = None
            if not (
                isinstance(record, dict)
                and record.get("format") == "t08-rc-v1"
                and record.get("step") == "surface-alpha"
            ):
                continue
            first = [entry for entry in record.get("chain", []) if entry.get("item") == 1]
            if len(first) != 1 or not isinstance(first[0].get("found"), str):
                raise LookupError(f"{base}/{path}: not one chain entry with item 1 and a `found`")
            found[path] = first[0]["found"]
        if not found:
            raise LookupError(f"no step-8 record (t08-rc-v1, surface-alpha) in {base}/records.json")
        if len(set(found.values())) != 1:
            raise LookupError(f"the step-8 records in {base} differ: {sorted(found)}")
        return next(iter(found.values()))

    def evaluate(self, scope: str, at: str) -> tuple[str | None, list[TermValue]]:
        """The row fingerprint of `scope` at `at`, and its terms."""
        values = [self.term(term, at) for term in scope_terms(scope)]
        return fingerprint(values), values


# -- the standing acceptances (RP §8.1, §8.3–§8.5) -----------------------------------------------


@dataclass(frozen=True)
class Row:
    """A row of `release/acceptances.md`: the clause or item, its answer cell as written, and its
    `Scope`, `Fingerprint` and `Accepted at`."""

    item: str
    cell: str
    scope: str
    fingerprint: str
    accepted_at: str


@dataclass(frozen=True)
class Acceptances:
    failures: tuple[Row, ...]
    decisions: tuple[Row, ...]


_STANDING_COLUMNS: Final = ("scope", "fingerprint", "accepted at")
_TABLES: Final = (("failures", "frank's acceptance"), ("decisions", "frank's answer"))


def _between_backticks(cell: str) -> str | None:
    match = re.fullmatch(r"`([^`]*)`", cell.strip())
    return match.group(1) if match else None


def standing_acceptances(text: str | None, where: str) -> Acceptances | None:
    """The two tables of a standing acceptances file (RP §8.1), or `None` if neither has a
    `Scope` column (dated mode, REL.A03). A standing file that departs from RP §8.1 is a
    `ValueError` (exit 2)."""
    if text is None:
        return None
    found: dict[str, list[tuple[list[str], list[list[str]]]]] = {}
    for header, rows in _tables(text):
        names = [_bare(cell).lower() for cell in header]
        for kind, column in _TABLES:
            if column in names:
                found.setdefault(kind, []).append((names, rows))
    tables = [table for kind in found for table in found[kind]]
    if not any("scope" in names for names, _ in tables):
        return None
    parsed: dict[str, tuple[Row, ...]] = {}
    for kind, column in _TABLES:
        if len(found.get(kind, [])) != 1:
            raise ValueError(
                f"{where}: {len(found.get(kind, []))} tables with a {column!r} column, not 1"
            )
        ((names, rows),) = found[kind]
        missing = [name for name in _STANDING_COLUMNS if name not in names]
        if missing:
            raise ValueError(f"{where}: the {column!r} table has no {missing} column")
        index = {name: names.index(name) for name in (column, *_STANDING_COLUMNS)}
        table = []
        for cells in rows:
            cells = cells + [""] * (len(names) - len(cells))
            item = _bare(cells[0])
            scope = _between_backticks(cells[index["scope"]])
            digest, commit = (_bare(cells[index[name]]) for name in _STANDING_COLUMNS[1:])
            if scope is None:
                raise ValueError(f"{where}: {item}: the Scope cell is not one `…` span")
            scope_terms(scope)
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"{where}: {item}: Fingerprint {digest!r} is not 64 hex digits")
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError(f"{where}: {item}: Accepted at {commit!r} is not a commit id")
            table.append(Row(item, cells[index[column]], scope, digest, commit))
        parsed[kind] = tuple(table)
    return Acceptances(parsed["failures"], parsed["decisions"])


@dataclass(frozen=True)
class RowState:
    """A row at `C` (RP §8.3 (b)): `stands`, `lapsed` or `unsupported`, and why."""

    state: str
    why: str = ""

    @property
    def stands(self) -> bool:
        return self.state == "stands"

    def word(self) -> str:
        return self.state if self.stands else f"{self.state} ({self.why})"


def _differing(row: Row, at_c: Sequence[TermValue], scopes: Scopes) -> str:
    """A lapsed row's differing terms, from its scope at `Accepted at`: each `paths:` term by
    the paths that differ, each `extract:` term by itself. When `Accepted at` does not reproduce
    the recorded fingerprint, only that is said."""
    recorded, at_a = scopes.evaluate(row.scope, row.accepted_at)
    if recorded != row.fingerprint:
        return f"the fingerprint at C is not the one recorded at {row.accepted_at[:12]}"
    terms = []
    for before, after in zip(at_a, at_c, strict=True):
        if before.digest == after.digest:
            continue
        if before.term.startswith("paths:"):
            paths = {record_path(record) for record in before.records ^ after.records}
            terms.append(", ".join(sorted(paths)))
        else:
            terms.append(before.term)
    return "; ".join(terms)


def row_state(row: Row, scopes: Scopes) -> RowState:
    """RP §8.3 (b) at `C`."""
    digest, values = scopes.evaluate(row.scope, scopes.rc)
    if digest is None:
        return RowState("unsupported", "; ".join(v.reason for v in values if v.digest is None))
    if digest == row.fingerprint:
        return RowState("stands")
    return RowState("lapsed", _differing(row, values, scopes))


def lapses_date(text: str | None, rc: str) -> datetime.date | None:
    """The lapse report's date (RP §8.5): its first line `acceptance lapses at C = <C>, <date>`,
    for this `C`; `None` if there is no such report."""
    first = (text or "").partition("\n")[0]
    match = LAPSES_HEADER.fullmatch(first)
    if match is None or match.group(1) != rc:
        return None
    try:
        return datetime.date.fromisoformat(match.group(2))
    except ValueError:
        return None


@dataclass(frozen=True)
class Standing:
    """The engine's `Policy` under the standing rule, and each usable row's state."""

    policy: Policy
    failures: dict[str, tuple[Row, RowState]]
    decisions: dict[str, tuple[Row, RowState]]


def standing(
    table: Acceptances,
    gate_set: GateSet,
    *,
    rc: str,
    scopes: Scopes,
    judged: datetime.date | None,
    rejudged: engine.Rejudgement | None,
    lapses: datetime.date | None,
) -> Standing:
    """RP §8.3–§8.4 as the engine's `Policy`. A failure clause's row counts in `accepted` only if
    it stands: with its own date where it is new (`Accepted at` = `C`), so that the engine's
    `Judged` and Table T7 bounds apply (§8.4), and with no lower bound where it is a standing row
    (`datetime.date.max`, D3.4). A decision item needs a standing row; a new one is dated on or
    after the lapse report, and Table T7's upper bound is the engine's."""
    where = gate_set.policy_adr
    problems: list[str] = []
    accepted: dict[str, tuple[str, datetime.date | None]] = {}
    failures: dict[str, tuple[Row, RowState]] = {}
    for row in table.failures:
        if not gate_set.clause.fullmatch(row.item):
            continue
        if row.item in failures:
            problems.append(f"{where}: the failure-clause table lists {row.item} twice")
        state = row_state(row, scopes)
        failures[row.item] = (row, state)
        date = acceptance_date(row.cell) if state.stands else None
        if date is not None and row.accepted_at != rc:
            date = datetime.date.max
        accepted[row.item] = (row.cell, date)
    frank: list[str] = []
    decisions: dict[str, tuple[Row, RowState]] = {}
    for item in gate_set.frank_items:
        rows = [row for row in table.decisions if row.item == item]
        if not rows:
            frank.append(f"Frank's answer to {item}: no row {item!r} in {where}")
            continue
        if len(rows) > 1:
            frank.append(f"Frank's answer to {item}: {len(rows)} rows in {where}, not 1")
            continue
        (row,) = rows
        state = row_state(row, scopes)
        decisions[item] = (row, state)
        date = acceptance_date(row.cell)
        if date is None:
            frank.append(
                f"Frank's answer to {item} is not an acceptance of the default; "
                f"amend {gate_set.specification} for it"
            )
        elif not state.stands:
            frank.append(f"Frank's answer to {item}: {state.word()}")
        elif row.accepted_at == rc and lapses is None:
            frank.append(
                f"Frank's answer to {item}: accepted {date.isoformat()} at C, and there is no "
                f"lapse report evidence/{gate_set.evidence_package}/{rc}/{LAPSES} (RP §8.4)"
            )
        elif row.accepted_at == rc and lapses is not None and date < lapses:
            frank.append(
                f"Frank's answer to {item}: accepted {date.isoformat()}, before the lapse "
                f"report's date {lapses.isoformat()} (RP §8.4)"
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
                    f"({engine._verdict_dates(judged, rejudged)}; §19.2 Table T7)"
                )
    return Standing(Policy(accepted, problems, frank), failures, decisions)


def _date_word(row: Row) -> str:
    date = acceptance_date(row.cell)
    return date.isoformat() if date else "(no date)"


def acceptance_lines(found: Standing, lines: Sequence[GateLine]) -> list[str]:
    """RP §8.5's report lines: every standing row used, as `standing acceptance <item>: accepted
    <date> at <commit>, scope unchanged`; every lapsed or unsupported row with its reason; every
    failure-clause row whose clause does not fail at `C`, `not used`."""
    used = {clause for line in lines for clause in line.accepted}
    failing = {clause for line in lines if line.document for clause in line.document.clauses}
    out = []
    usable = [*found.decisions.items(), *found.failures.items()]
    for item, (row, state) in usable:
        if not state.stands:
            out.append(f"acceptance {item}: {state.word()}")
        elif item in found.failures and item not in failing:
            out.append(f"acceptance {item}: not used")
        elif item in found.decisions or item in used:
            out.append(
                f"standing acceptance {item}: accepted {_date_word(row)} at {row.accepted_at}, "
                "scope unchanged"
            )
    return out


def lapse_report(
    table: Acceptances, gate_set: GateSet, scopes: Scopes, today: datetime.date
) -> str:
    """RP §8.5's lapse report: its header, then one line per row the line can use."""
    out = [f"acceptance lapses at C = {scopes.rc}, {today.isoformat()}"]
    for row in table.failures:
        if gate_set.clause.fullmatch(row.item):
            out.append(f"{row.item}: {row_state(row, scopes).word()}")
    for row in table.decisions:
        if row.item in gate_set.frank_items:
            out.append(f"{row.item}: {row_state(row, scopes).word()}")
    return "\n".join(out) + "\n"


# -- the report ---------------------------------------------------------------------------------


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
    line: Line,
    released: bool | None = None,
    scopes: Scopes | None = None,
) -> dict[str, Any]:
    """`v0_2_gate.build` over the line's gate set. In dated mode it is the engine's report
    unchanged; in standing mode the policy is RP §8's and the report gains `acceptances`, its
    lines (RP §8.5). `scopes` evaluates the scopes at `C`; standing mode needs it."""
    table = standing_acceptances(files.get(line.gate_set.policy_adr), line.gate_set.policy_adr)
    release = line.release(standing=table is not None)
    arguments: dict[str, Any] = {
        "files": files,
        "rc": rc,
        "rc_version": rc_version,
        "rc_in_repository": rc_in_repository,
        "candidate": candidate,
        "version": version,
        "differences": differences,
        "is_ancestor": is_ancestor,
        "release": release,
        "released": released,
    }
    of = engine.post_release_of(version, release)
    gate_set = engine.gate_set_of(of or version, release)
    if table is None or gate_set is None:
        return engine.build(**arguments)
    if scopes is None:
        raise ValueError(f"{gate_set.policy_adr}: standing acceptances need the scopes at C")
    return _build_standing(table, gate_set, scopes, of=of, **arguments)


def _build_standing(
    table: Acceptances,
    gate_set: GateSet,
    scopes: Scopes,
    *,
    of: str | None,
    files: Mapping[str, str],
    rc: str,
    rc_version: str,
    rc_in_repository: bool,
    candidate: str,
    version: str,
    differences: Sequence[str] | None,
    is_ancestor: Callable[[str], bool],
    release: ReleaseLine,
    released: bool | None,
) -> dict[str, Any]:
    """`v0_2_gate.build`'s items 1–12 in its order, from its own parts, with RP §8's policy in
    the place of the dated one (items 5 and 11)."""
    gated = of or version
    ledger = yaml.safe_load(files[LEDGER]) if LEDGER in files else None
    entries = {
        str(entry.get("id")): dict(entry)
        for entry in (ledger or {}).get("gates", [])
        if isinstance(entry, dict)
    }
    verdict_text = files.get(gate_set.verdict_document)
    document = None if verdict_text is None else engine.verdict_document(verdict_text, gate_set, rc)
    rows = document.rows if document else {}
    judged = document.judged if document else None
    rejudged = document.rejudged if document else None
    lapses = lapses_date(files.get(f"evidence/{gate_set.evidence_package}/{rc}/{LAPSES}"), rc)
    found = standing(
        table, gate_set, rc=rc, scopes=scopes, judged=judged, rejudged=rejudged, lapses=lapses
    )
    known = {
        str(item["id"])
        for item in engine.envelope_document(files.get(ENVELOPE)).get("limitations", [])
    }
    lines = [
        engine.judge_gate(
            gate, entries.get(gate), rows.get(gate), found.policy, judged, known, gate_set, rejudged
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
    if rc_version != gated:
        reasons.append(
            f"C's version {rc_version} is not the candidate's version {gated} ({gate_set.adr} D4)"
        )
    if of is not None and released is not True:
        reasons.append(
            f"{version} is a post-release of {of}, which is not released: no tag v{of} on an "
            f"ancestor of the candidate ({engine.POST_RELEASE_REGISTER})"
        )
    if differences is None:
        reasons.append("tree check (D2.4) not run")
    elif differences:
        reasons.append(f"candidate {candidate[:12]} differs from C in {list(differences)} (D2.4)")
    record = engine.rc_record_problems(files.get(gate_set.rc_record), rc, gate_set)
    manifests = engine.manifest_problems(
        files, gate_set, rc, rc_in_repository=rc_in_repository, is_ancestor=is_ancestor
    )
    envelope = engine.envelope_problems(files.get(ENVELOPE), gate_set, gated)
    adrs = engine.adr_problems(files, gate_set)
    frank = [
        *found.policy.frank,
        *engine.links_problems(files.get(gate_set.policy_adr), files.get(LINKS_MODULE), gate_set),
    ]
    for group in (record, manifests, envelope, adrs, found.policy.problems, frank):
        reasons.extend(group)
    post = {} if of is None else {"post_release": {"of": of, "released": released}}
    return {
        **post,
        "gate_set": gate_set.name,
        "rc": rc,
        "candidate": candidate,
        "version": version,
        "rc_version": rc_version,
        "judged": judged.isoformat() if judged else None,
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
        "frank_problems": found.policy.problems + frank,
        "acceptances": acceptance_lines(found, lines),
        "tag_may_be_proposed": not reasons,
        "reasons": reasons,
    }


def text(report: Mapping[str, Any], line: Line) -> str:
    """The engine's text report; in standing mode RP §8.5's acceptance lines precede the last."""
    rows = report.get("acceptances")
    out = engine.text(report, line.release(standing=rows is not None))
    if not rows:
        return out
    *body, last = out.rstrip("\n").split("\n")
    return "\n".join([*body, *rows, last]) + "\n"


def markdown(report: Mapping[str, Any], line: Line) -> str:
    return engine.markdown(report, line.release(standing="acceptances" in report))


# -- the command line ---------------------------------------------------------------------------


def _read_at(candidate: str) -> Callable[[str], bytes | None]:
    def read(path: str) -> bytes | None:
        try:
            return git("show", f"{candidate}:{path}")
        except subprocess.CalledProcessError:
            return None

    return read


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--line", required=True, help="the release line <major>.<minor>")
    parser.add_argument("--rc", required=True, help="the release candidate C")
    parser.add_argument("--candidate", default="HEAD", help="the tag candidate (default HEAD)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--markdown", action="store_true")
    output.add_argument("--lapses", action="store_true", help="RP §8.5's lapse report at C")
    output.add_argument("--write-tree-record", action="store_true", help="R-151 (the engine's)")
    output.add_argument("--carry-journey", metavar="J", help="RC step 15 (the engine's)")
    output.add_argument("--carry-w27", nargs=2, metavar=("AT_C_W", "AT_C"), help="the engine's")
    arguments = parser.parse_args(argv)
    passed = ["--rc", arguments.rc, "--candidate", arguments.candidate]
    for flag in ("json", "markdown", "write_tree_record"):
        if getattr(arguments, flag):
            passed.append("--" + flag.replace("_", "-"))
    if arguments.carry_journey is not None:
        passed += ["--carry-journey", arguments.carry_journey]
    if arguments.carry_w27 is not None:
        passed += ["--carry-w27", *arguments.carry_w27]
    try:
        candidate = git("rev-parse", f"{arguments.candidate}^{{commit}}").decode().strip()
        line = load_line(arguments.line, _read_at(candidate))
        carry = arguments.carry_journey is not None or arguments.carry_w27 is not None
        if arguments.write_tree_record or carry:  # the engine's own, with this line's gate set
            return engine.main(passed, line.release())
        rc = resolve_rc(arguments.rc)
        trees = GitTrees()
        if line.document.get("gates") or line.document.get("rc_items"):
            entries = trees.entries(rc)
            if entries is None:
                raise LineError(
                    f"line {line.name}: RP.L05 and RP.L08 are checked at C = {rc}, "
                    "which is not a commit of this repository"
                )
            problems = tree_problems(line, [record_path(record) for record in entries])
            if problems:
                raise LineError("\n".join(problems))
        where = line.gate_set.policy_adr
        policy_text = _read_at(candidate)(where)
        table = standing_acceptances(
            None if policy_text is None else policy_text.decode("utf-8"), where
        )
        if table is None:
            if arguments.lapses:
                raise ValueError(f"line {line.name}: {where} has no standing acceptances")
            return engine.main(passed, line.release())
        scopes = Scopes(trees, line, rc, candidate)
        if arguments.lapses:
            today = datetime.datetime.now(datetime.UTC).date()
            print(lapse_report(table, line.gate_set, scopes, today), end="")
            return 0
        report = _report(line, rc, candidate, scopes)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    elif arguments.markdown:
        if report["gate_set"] is None:
            print(f"error: {report['reasons'][0]}", file=sys.stderr)
            return 1
        print(markdown(report, line), end="")
    else:
        print(text(report, line), end="")
    return 0 if report["tag_may_be_proposed"] else 1


def _report(line: Line, rc: str, candidate: str, scopes: Scopes) -> dict[str, Any]:
    """The engine's `main` steps for a standing line: the candidate's files, and `C`'s facts."""
    release = line.release(standing=True)
    rc_in_repository = has_commit(rc)
    version = version_at(candidate)
    of = engine.post_release_of(version, release)
    gate_set = engine.gate_set_of(of or version, release)
    files = {} if gate_set is None else engine.files_at(candidate, rc, gate_set)
    if gate_set is not None:
        lapses = f"evidence/{gate_set.evidence_package}/{rc}/{LAPSES}"
        text_at = engine.read_at(candidate, lapses)
        if text_at is not None:
            files[lapses] = text_at
    return build(
        files=files,
        rc=rc,
        rc_version=(version_at(rc) if rc_in_repository else str(tree_record_of(rc)["version"])),
        rc_in_repository=rc_in_repository,
        candidate=candidate,
        version=version,
        differences=(
            None
            if gate_set is None
            else tree_differences(rc, candidate)
            if of is None
            else engine.post_release_differences(rc, candidate)
        ),
        is_ancestor=engine.is_ancestor_of(rc),
        line=line,
        released=None if of is None else engine.is_released(of, candidate),
        scopes=scopes,
    )


if __name__ == "__main__":
    sys.exit(main())
