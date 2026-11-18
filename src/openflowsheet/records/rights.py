"""The rights register (ADR 0061 D11; Q9.R3, R-706, R-926), F3-WO4.

A row is `{source_id, source_sha256, record_sha256, assessment, conditions, basis, decided_by,
date}`: an assessment (`permitted`, `unknown`, `refused`) of one source of one record
(`record_sha256` set), or of a whole source (`record_sha256` null). A whole-source row is keyed by
`source_sha256`, the SHA of the canonical one-member object `{<source id>: <sources entry>}` a
record carries, never by the source id a record chooses (W1 P1 review finding 19). Two layers:

- the **repository register** `records/rights-register.json` (package data, hand-maintained under
  the lane rules), seeded with one whole-source row per legacy source (`seed_rows`; held to the
  legacy import by `scripts/records_legacy_index.py --check`, `seed_problems`);
- the **project register**, the `rights` table of the project's `records.sqlite3`
  (`RecordStore.append_rights`, `RecordStore.rights_rows`), append-only; F3-WO5's operation
  `assess_rights` writes it.

"Latest" is the highest insertion sequence (the project table's sequence, the repository file's
row order), never `date`. The effective assessment of (source, record) is decided by the first of
D11's four precedence rows that has a row (`effective`), else `unknown`. No layer enters any hash:
rights are not identity (Q9.A2) and never enter a data lock.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Final, Literal

from openflowsheet.canonical import document_sha256

if TYPE_CHECKING:
    from openflowsheet.records.importers.legacy import ImportedFile

#: D11: the repository register (package data) and its format id (F3 decision WO4-1).
REGISTER_NAME: Final = "rights-register.json"
REGISTER_FORMAT: Final = "openflowsheet-rights-register-v1"
#: D11: a row's assessments and its fields, in D11's order.
ASSESSMENTS: Final = ("permitted", "unknown", "refused")
ROW_FIELDS: Final = (
    "source_id",
    "source_sha256",
    "record_sha256",
    "assessment",
    "conditions",
    "basis",
    "decided_by",
    "date",
)
#: D11, D12: the source-id prefix reserved for the legacy importer.
LEGACY_PREFIX: Final = "legacy."
#: D11's seed rule: the prefix of a v1 `redistribution` text whose remainder is the conditions.
CONDITIONS_PREFIX: Final = "permitted with conditions:"
#: Who decided a seed row (F3 decision WO4-2).
SEED_DECIDED_BY: Final = "ADR 0061 D11 seed"

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_DATE: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

Layer = Literal["project", "repository"]


class RightsRegisterError(ValueError):
    """A rights row or register document off D11's row shape: the message says where."""


def source_sha256(source_id: str, entry: Mapping[str, Any]) -> str:
    """D11's `source_sha256`: `document_sha256({<source id>: <sources entry>})`, of the entry as
    the normalised record carries it."""
    return document_sha256({source_id: entry})


def record_sources(record: Mapping[str, Any]) -> dict[str, str]:
    """Each source id of the normalised `record` and its `source_sha256`."""
    return {ident: source_sha256(ident, entry) for ident, entry in record["sources"].items()}


def seed_assessment(text: str) -> tuple[str, str | None]:
    """D11's reading of a v1 `redistribution` text: beginning `permitted` or `synthetic` →
    `permitted`, with the text after `permitted with conditions:` as `conditions`; `unresolved`
    or `unknown` → `unknown`; `refused` or `not permitted` → `refused`; anything else →
    `unknown`. Returns (assessment, conditions)."""
    if text.startswith(CONDITIONS_PREFIX):
        return "permitted", text[len(CONDITIONS_PREFIX) :].strip()
    if text.startswith(("permitted", "synthetic")):
        return "permitted", None
    if text.startswith(("refused", "not permitted")):
        return "refused", None
    return "unknown", None


def check_row(row: Mapping[str, Any], where: str) -> dict[str, Any]:
    """D11's row shape: exactly its eight fields, both SHAs 64 lower-case hex digits
    (`record_sha256` or null), an assessment of the three, `conditions` a string or null, a
    non-empty `basis` and `decided_by`, and a `date` `YYYY-MM-DD`. Returns the row's fields in
    D11's order; raises `RightsRegisterError`."""
    if not isinstance(row, Mapping) or set(row) != set(ROW_FIELDS):
        raise RightsRegisterError(f"{where}: the fields are not D11's {list(ROW_FIELDS)}")
    problems = [
        name
        for name, ok in (
            ("source_id", _text(row["source_id"])),
            ("source_sha256", _sha(row["source_sha256"])),
            ("record_sha256", row["record_sha256"] is None or _sha(row["record_sha256"])),
            ("assessment", row["assessment"] in ASSESSMENTS),
            ("conditions", row["conditions"] is None or isinstance(row["conditions"], str)),
            ("basis", _text(row["basis"])),
            ("decided_by", _text(row["decided_by"])),
            ("date", isinstance(row["date"], str) and _DATE.fullmatch(row["date"]) is not None),
        )
        if not ok
    ]
    if problems:
        raise RightsRegisterError(f"{where}: invalid {problems}")
    return {name: row[name] for name in ROW_FIELDS}


def _text(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _sha(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def register_rows(document: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """The rows of a repository register document `{register_format, rows}`, each checked
    (`check_row`), in file order; raises `RightsRegisterError`."""
    if not isinstance(document, Mapping) or set(document) != {"register_format", "rows"}:
        raise RightsRegisterError(f"{REGISTER_NAME}: members are not register_format and rows")
    if document["register_format"] != REGISTER_FORMAT:
        raise RightsRegisterError(f"{REGISTER_NAME}: register_format is not {REGISTER_FORMAT}")
    rows = document["rows"]
    if not isinstance(rows, list):
        raise RightsRegisterError(f"{REGISTER_NAME}: rows is not a list")
    return tuple(check_row(row, f"{REGISTER_NAME} rows[{n}]") for n, row in enumerate(rows))


@cache
def repository_rows() -> tuple[dict[str, Any], ...]:
    """The repository register's rows (`records/rights-register.json`, package data)."""
    text = files("openflowsheet.records").joinpath(REGISTER_NAME).read_text(encoding="utf-8")
    return register_rows(json.loads(text))


# -- the effective assessment (D11's precedence) -------------------------------------------------


@dataclass(frozen=True)
class Effective:
    """The effective assessment of one source of one record: the deciding row's assessment and
    conditions, its layer and the row itself; `unknown` with no layer and no row when no row
    decides."""

    assessment: str
    conditions: str | None
    layer: Layer | None
    row: Mapping[str, Any] | None


UNKNOWN: Final = Effective("unknown", None, None, None)


def effective(
    record_sha256: str,
    source_sha256: str,
    *,
    project: Sequence[Mapping[str, Any]] = (),
    repository: Sequence[Mapping[str, Any]] | None = None,
) -> Effective:
    """D11's effective assessment of the source `source_sha256` of record `record_sha256`:
    the latest project row for (source, record), else the latest project whole-source row for
    the source, else the latest repository row for (source, record), else the latest repository
    whole-source row for the source, else `unknown`. Each layer's rows are given in insertion
    order (`project`: `RecordStore.rights_rows()`; `repository`: `repository_rows()` when
    `None`), so "latest" is the last match."""
    layers: tuple[tuple[Layer, Sequence[Mapping[str, Any]]], ...] = (
        ("project", project),
        ("repository", repository_rows() if repository is None else repository),
    )
    for layer, rows in layers:
        for scope in (record_sha256, None):
            row = _latest(rows, source_sha256, scope)
            if row is not None:
                return Effective(row["assessment"], row["conditions"], layer, row)
    return UNKNOWN


def _latest(
    rows: Sequence[Mapping[str, Any]], source: str, record: str | None
) -> Mapping[str, Any] | None:
    for row in reversed(rows):
        if row["source_sha256"] == source and row["record_sha256"] == record:
            return row
    return None


def record_rights(
    record: Mapping[str, Any],
    record_sha256: str,
    *,
    project: Sequence[Mapping[str, Any]] = (),
    repository: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Effective]:
    """The effective assessment (`effective`) of each source of the normalised `record`, whose
    SHA is `record_sha256`, by source id."""
    return {
        ident: effective(record_sha256, sha, project=project, repository=repository)
        for ident, sha in record_sources(record).items()
    }


def embeddable(rights: Mapping[str, Effective]) -> bool:
    """D11, Q9.R7: a bundle embeds a record only when every source of it is `permitted` (else it
    references the record by SHA)."""
    return bool(rights) and all(item.assessment == "permitted" for item in rights.values())


# -- the seed rows (D11, D12) ------------------------------------------------------------------


def seed_rows(imported: Iterable[ImportedFile], *, date: str) -> list[dict[str, Any]]:
    """D11's seed: one whole-source row per legacy source, in import order, for each distinct
    `source_sha256` of a file's records (its components' and its parameter set's are one, F3
    decisions WO4-0 and WO3-5 as ruled in F3 ruling round 1), assessed from the file's v1
    `redistribution` text (`seed_assessment`)."""
    rows = []
    for item in imported:
        assessment, conditions = seed_assessment(item.redistribution)
        for source_id, sha in _file_sources(item):
            rows.append(
                {
                    "source_id": source_id,
                    "source_sha256": sha,
                    "record_sha256": None,
                    "assessment": assessment,
                    "conditions": conditions,
                    "basis": f"{item.path}: v1 rights.redistribution {item.redistribution!r}",
                    "decided_by": SEED_DECIDED_BY,
                    "date": date,
                }
            )
    return rows


def _file_sources(item: ImportedFile) -> list[tuple[str, str]]:
    """The distinct (source id, `source_sha256`) pairs of an imported file's records, in record
    order."""
    pairs = (pair for outcome in item.records for pair in record_sources(outcome.record).items())
    return list(dict.fromkeys(pairs))


def seed_problems(imported: Iterable[ImportedFile], rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Why `rows` (a repository register) no longer holds the legacy import's seed: for each
    seed row (`seed_rows`), the register's first whole-source row of that `source_sha256` must
    exist with the seed's source id, assessment and conditions; and every row naming a `legacy.`
    source must carry a `source_sha256` the import gives (else a regenerated index left it
    stale)."""
    seeds = seed_rows(imported, date="0000-00-00")
    found = []
    for seed in seeds:
        first = next(
            (
                row
                for row in rows
                if row["source_sha256"] == seed["source_sha256"] and row["record_sha256"] is None
            ),
            None,
        )
        decided = ("source_id", "assessment", "conditions")
        if first is None or any(first[name] != seed[name] for name in decided):
            found.append(f"no seed row for {seed['source_id']} {seed['source_sha256']}")
    known = {seed["source_sha256"] for seed in seeds}
    found += [
        f"{row['source_id']} row names an unknown source_sha256 {row['source_sha256']}"
        for row in rows
        if row["source_id"].startswith(LEGACY_PREFIX) and row["source_sha256"] not in known
    ]
    return found
