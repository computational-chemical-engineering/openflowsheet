"""The `Records` operations (ADR 0061 D13, ADR 0019 Amendment 8) over a project's record stack.

The stack (`ServiceCore.records`) reads through `[project store, legacy store]` and writes to the
project store (D8); the project rights register is its `rights` table over the repository
register (D11). Each operation first checks its request as `dispatch` does (the canonical form,
then the operation's request schema), so the Python transport refuses what the others refuse
(rule C1), then authorizes. A record refusal travels as an `ApiError` by its catalogue kind
(`input` → `invalid_request`, `not_supported` → `unsupported`, `bug` → `internal_error`), its
code in `detail.reason` and its `{code, params}` in `detail.refusal` (F3 decision WO5b-1).
`register_record` and `assess_rights` write one audit row each.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import cache
from typing import Any, Final, NoReturn

from openflowsheet.application.documents import validate_inline
from openflowsheet.application.errors import ApiErrorCode
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.record_types import (
    RecordPage,
    RecordRegistrationResult,
    RecordValidationReport,
    RecordView,
    RightsAssessmentResult,
)
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.store_records import AuditEntry
from openflowsheet.canonical import canonical_json, document_sha256, first_noncanonical
from openflowsheet.messages.catalogue import CATALOGUE
from openflowsheet.records import resolve, rights
from openflowsheet.records.identity import identify
from openflowsheet.records.importers import legacy
from openflowsheet.records.importers.user_file import import_user_file
from openflowsheet.records.model import RecordOutcome, pointer
from openflowsheet.records.reactions import check_reactions
from openflowsheet.records.stack import StoreStack
from openflowsheet.records.store import RecordStoreError
from openflowsheet.registry.tokens import Coded
from openflowsheet.schema_check import DocumentSchemaError

#: A record refusal's `ApiError` code by its catalogue kind (F3 decision WO5b-1). Not named
#: `*_CODES`: its keys are catalogue kinds, not codes (MSG-G2's scan reads such a table).
API_ERROR_OF_KIND: Final[Mapping[str, ApiErrorCode]] = {
    "input": "invalid_request",
    "not_supported": "unsupported",
    "bug": "internal_error",
}
#: D11: the source-id prefix only the legacy importer writes.
LEGACY_PREFIX: Final = "legacy."


@cache
def legacy_shas() -> frozenset[str]:
    """The record SHAs of the committed legacy index: a submitted record naming a `legacy.`
    source is the importer's exactly when its SHA is one of them (D11, ruling WO4-0)."""
    index = legacy.committed_index()
    return frozenset(item["sha256"] for entry in index["files"] for item in entry["records"])


def forged(outcome: RecordOutcome) -> bool:
    """D11: whether `outcome` names a `legacy.` source without being an indexed legacy record."""
    sources = outcome.record.get("sources") or {}
    claims = any(str(ident).startswith(LEGACY_PREFIX) for ident in sources)
    return claims and outcome.record_sha256 not in legacy_shas()


def effective_document(found: rights.Effective) -> dict[str, Any]:
    """An effective assessment as a response carries it: assessment, conditions, layer."""
    return {"assessment": found.assessment, "conditions": found.conditions, "layer": found.layer}


def _present(**members: Any) -> dict[str, Any]:
    return {name: value for name, value in members.items() if value is not None}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _encode_cursor(sha: str) -> str:
    return base64.urlsafe_b64encode(canonical_json({"after": sha})).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> str | None:
    """The SHA a cursor this list issued continues after; `None` for any other text."""
    try:
        decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError, binascii.Error):
        return None
    if not isinstance(decoded, dict) or set(decoded) != {"after"}:
        return None
    after = decoded["after"]
    return after if isinstance(after, str) and len(after) == 64 else None


def resolution(records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """D9's resolution over the matched `records`: `none`, `unique`, `ambiguous_identity` (more
    than one identity class) or `ambiguous_source` (one class, several records), and the
    classes in `detail.candidates`' form."""
    if not records:
        return {"status": "none", "classes": []}
    classes = resolve.identity_classes(records)
    if len(records) == 1:
        status = "unique"
    else:
        status = "ambiguous_identity" if len(classes) > 1 else "ambiguous_source"
    return {"status": status, "classes": resolve.candidates(classes, records)}


class RecordsService:
    """ADR 0061 D13's five operations for one caller (`ServiceCore`)."""

    def __init__(self, core: ServiceCore) -> None:
        self._core = core

    @property
    def stack(self) -> StoreStack:
        return self._core.records

    # ------------------------------------------------------------------------------ reading

    def search_records(
        self,
        *,
        key: str | None,
        scheme: str | None,
        record_type: str | None,
        cursor: str | None,
        limit: int,
    ) -> RecordPage:
        name = "search_records"
        self._checked(
            name,
            _present(key=key, scheme=scheme, record_type=record_type, cursor=cursor, limit=limit),
        )
        self._core.authorize(name)
        after = None if cursor is None else _decode_cursor(cursor)
        if cursor is not None and after is None:
            self._core.refuse(
                "invalid_request",
                "a cursor this list did not issue",
                operation=name,
                pointer="/cursor",
            )
        try:
            shas = self._matches(key, scheme, record_type)
            records = {sha: self.stack.record(sha) for sha in shas}
            project = self.stack.project.rights_rows()
            held = {row.sha for row in self.stack.project.objects()}
        except RecordStoreError as error:
            self._refuse_store(name, error)
        page = [sha for sha in shas if after is None or sha > after][:limit]
        more = bool(page) and page[-1] != shas[-1]
        items = tuple(
            self._item(sha, records[sha], "project" if sha in held else "legacy", project)
            for sha in page
        )
        return RecordPage(items, resolution(records), _encode_cursor(page[-1]) if more else None)

    def _matches(self, key: str | None, scheme: str | None, record_type: str | None) -> list[str]:
        """The SHAs `key` matches (D9; in `scheme` when given), or every stored SHA, sorted."""
        if key is not None:
            query = key if scheme is None else f"{scheme}:{key}"
            return list(resolve.search(self.stack, query, record_type=record_type).shas)
        return sorted(
            {
                row.sha
                for layer in self.stack.layers()
                for row in layer.objects()
                if record_type is None or row.record_type == record_type
            }
        )

    @staticmethod
    def _item(
        sha: str, record: Mapping[str, Any], store: str, project: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        found = rights.record_rights(record, sha, project=project)
        return {
            "record_sha256": sha,
            "record_type": record["record_type"],
            "id": record["id"],
            "name": record["name"],
            "identifiers": dict(record.get("identifiers") or {}),
            "amount_basis": record.get("amount_basis"),
            "source_ids": sorted(record.get("sources") or {}),
            "store": store,
            "effective_rights": {
                ident: effective_document(item) for ident, item in sorted(found.items())
            },
        }

    def get_record(self, record_sha256: str) -> RecordView:
        name = "get_record"
        self._checked(name, {"record_sha256": record_sha256})
        self._core.authorize(name)
        record = self._read(record_sha256, name, "/record_sha256")
        try:
            registrations = tuple(self.stack.project.registrations(record_sha256))
            held = self.stack.project.object_bytes(record_sha256) is not None
            project = self.stack.project.rights_rows()
        except RecordStoreError as error:
            self._refuse_store(name, error)
        sources = rights.record_sources(record)
        found = rights.record_rights(record, record_sha256, project=project)
        rows = [
            {**row, "layer": layer, **({} if "sequence" in row else {"sequence": position})}
            for layer, layer_rows in (
                ("project", project),
                ("repository", rights.repository_rows()),
            )
            for position, row in enumerate(layer_rows, start=1)
            if row["source_sha256"] in sources.values()
            and row["record_sha256"] in (record_sha256, None)
        ]
        return RecordView(
            record_sha256,
            record,
            registrations,
            "project" if held else "legacy",
            {ident: effective_document(item) for ident, item in sorted(found.items())},
            tuple(rows),
        )

    # ------------------------------------------------------------------------------ writing

    def register_record(
        self,
        *,
        record: Mapping[str, Any] | None,
        file: Mapping[str, Any] | None,
        defaults: Mapping[str, Any] | None,
    ) -> RecordRegistrationResult:
        name = "register_record"
        request = _present(record=record, file=file, defaults=defaults)
        self._checked(name, request)
        caller = self._core.authorize(name)
        at = _now()
        if record is not None:
            outcomes: tuple[RecordOutcome, ...] = (identify(record),)
            where = "/record"
        else:
            assert file is not None
            outcomes = import_user_file(
                file["format"],
                file["content"],
                retrieved_at=at,
                defaults=defaults,
                local_path=file.get("local_path"),
            )
            where = "/file/content"
        # Every record is judged before any is stored: a refused submission stores nothing.
        for index, outcome in enumerate(outcomes):
            at_record = {} if record is not None else {"record_index": index}
            if forged(outcome):
                self._refuse_coded(
                    name, Coded("reserved_namespace", {"namespace": "legacy"}), where, **at_record
                )
            if outcome.refused:
                self._refuse_coded(name, outcome.errors[0], where, **at_record)
        try:
            stored = [
                self.stack.register(outcome, principal=caller.principal_id, at=at)
                for outcome in outcomes
            ]
        except RecordStoreError as error:
            self._refuse_store(name, error)
        shas = [item.record_sha256 for item in stored]
        self._audit(name, caller.principal_id, request, f"records:{document_sha256(shas)}")
        return RecordRegistrationResult(
            tuple(
                {
                    "record_sha256": item.record_sha256,
                    "created": item.created,
                    "findings": [finding.as_document() for finding in item.findings],
                }
                for item in stored
            )
        )

    def validate_record(
        self,
        *,
        record: Mapping[str, Any] | None,
        records: Sequence[str | Mapping[str, Any]] | None,
        components: Mapping[str, str] | None,
        reactions: Sequence[Mapping[str, Any]] | None,
    ) -> RecordValidationReport:
        name = "validate_record"
        self._checked(
            name,
            _present(record=record, records=records, components=components, reactions=reactions),
        )
        self._core.authorize(name)
        errors: list[Coded] = []
        findings: list[Coded] = []
        known: dict[str, Mapping[str, Any]] = {}
        own: str | None = None
        if record is not None:
            own = self._identified(identify(record), errors, findings, known)
        for index, item in enumerate(records or ()):
            if isinstance(item, str):
                known[item] = self._read(item, name, pointer("/records", index))
            else:
                self._identified(identify(item), errors, findings, known)
        named = {
            key: known.get(sha) or self._read(sha, name, pointer("/components", key))
            for key, sha in (components or {}).items()
        }
        if reactions:
            more_errors, more_findings = self._reactions(name, reactions, named)
            errors += more_errors
            findings += more_findings
        return RecordValidationReport(
            [item.as_document() for item in sorted(errors, key=Coded.sort_key)],
            [item.as_document() for item in sorted(findings, key=Coded.sort_key)],
            own,
        )

    @staticmethod
    def _identified(
        outcome: RecordOutcome,
        errors: list[Coded],
        findings: list[Coded],
        known: dict[str, Mapping[str, Any]],
    ) -> str | None:
        errors += outcome.errors
        findings += outcome.findings
        if outcome.record_sha256 is not None:
            known[outcome.record_sha256] = outcome.record
        return outcome.record_sha256

    def _reactions(
        self,
        name: str,
        reactions: Sequence[Mapping[str, Any]],
        named: Mapping[str, Mapping[str, Any]],
    ) -> tuple[tuple[Coded, ...], tuple[Coded, ...]]:
        """D7's reaction checks, after the screening WO5a-3 asks of the request: every
        stoichiometry key a `components` key naming a component record."""
        for key, found in named.items():
            if found["record_type"] != "component":
                self._core.refuse(
                    "invalid_request",
                    f"components {key!r} is a {found['record_type']} record, not a component",
                    operation=name,
                    pointer=pointer("/components", key),
                )
        for index, reaction in enumerate(reactions):
            for key in reaction["stoichiometry"]:
                if key not in named:
                    self._core.refuse(
                        "invalid_request",
                        f"stoichiometry key {key!r} is not a components key",
                        operation=name,
                        pointer=pointer(f"/reactions/{index}/stoichiometry", key),
                    )
        try:
            return check_reactions(reactions, named)
        except (ValueError, KeyError) as error:  # a record without molar_mass or charge
            self._core.refuse(
                "invalid_request",
                f"the reactions cannot be checked: {error}",
                operation=name,
                pointer="/reactions",
            )

    def assess_rights(
        self,
        *,
        source_id: str,
        record_sha256: str,
        scope: str,
        assessment: str,
        basis: str,
        conditions: str | None,
    ) -> RightsAssessmentResult:
        name = "assess_rights"
        request = {
            "source_id": source_id,
            "record_sha256": record_sha256,
            "scope": scope,
            "assessment": assessment,
            "basis": basis,
            **({} if conditions is None else {"conditions": conditions}),
        }
        self._checked(name, request)
        caller = self._core.authorize(name)
        record = self._read(record_sha256, name, "/record_sha256")
        sources = rights.record_sources(record)
        if source_id not in sources:
            self._core.refuse(
                "invalid_request",
                f"{source_id!r} is not a source of record {record_sha256}",
                operation=name,
                pointer="/source_id",
                sources=sorted(sources),
            )
        row = {
            "source_id": source_id,
            "source_sha256": sources[source_id],
            "record_sha256": record_sha256 if scope == "record" else None,
            "assessment": assessment,
            "conditions": conditions,
            "basis": basis,
            "decided_by": caller.principal_id,
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        }
        try:
            sequence = self.stack.project.append_rights(row)
            project = self.stack.project.rights_rows()
        except RecordStoreError as error:
            self._refuse_store(name, error)
        self._audit(name, caller.principal_id, request, f"rights:{sequence}")
        found = rights.effective(record_sha256, sources[source_id], project=project)
        return RightsAssessmentResult(
            {**row, "layer": "project", "sequence": sequence}, effective_document(found)
        )

    # ------------------------------------------------------------------------------ helpers

    def _checked(self, name: str, request: Mapping[str, Any]) -> None:
        """`dispatch`'s steps 1 and 2 for a Python caller: the canonical form, then the request
        schema; a refusal is audited and raised."""
        at = first_noncanonical(request)
        if at is not None:
            self._core.refuse(
                "document_not_canonical",
                "a value has no canonical JSON form",
                operation=name,
                pointer=at,
            )
        try:
            validate_inline(name, OPERATIONS[name].request_schema, request)
        except DocumentSchemaError as error:
            self._core.refuse(
                "invalid_request", error.message, operation=name, pointer=error.pointer
            )

    def _read(self, sha: str, name: str, at: str) -> Mapping[str, Any]:
        """Record `sha` through the stack; one no layer holds is `not_found` (D13), with the
        reason `data_unavailable` when the committed legacy index names it (WO2-6)."""
        try:
            return self.stack.record(sha)
        except RecordStoreError as error:
            if error.coded is None or error.coded.code != "data_unavailable":
                self._refuse_store(name, error)
            unavailable = {"reason": "data_unavailable"} if sha in legacy_shas() else {}
            self._core.refuse(
                "not_found",
                f"no record {sha} in this project or the legacy store",
                operation=name,
                pointer=at,
                record_sha256=sha,
                **unavailable,
            )

    def _refuse_coded(self, name: str, coded: Coded, at: str, **detail: Any) -> NoReturn:
        """A record refusal as an `ApiError` (WO5b-1). The refusal's params travel as `detail`
        members too, where no member of the error's own has the name, so MSG renders the
        `reason` link with them (F3 decision WO5b-9); `detail.refusal` holds them all."""
        entry = CATALOGUE.entry(coded.code)
        code = API_ERROR_OF_KIND.get(entry.kind if entry is not None else "bug", "internal_error")
        members = {"operation": name, "pointer": at, "reason": coded.code, **detail}
        params = {key: value for key, value in coded.params.items() if key not in members}
        self._core.refuse(
            code,
            f"the record is refused: {coded.code}",
            **params,
            **members,
            refusal=coded.as_document(),
        )

    def _refuse_store(self, name: str, error: RecordStoreError) -> NoReturn:
        if error.coded is None:  # a database that is not an `f3-records-v1` store
            self._core.refuse("internal_error", str(error), operation=name)
        self._refuse_coded(name, error.coded, "")

    def _audit(self, name: str, principal: str, request: Mapping[str, Any], effect: str) -> None:
        self._core.store.record_audit(
            AuditEntry(
                principal_id=principal,
                capability_id=self._core.capability_id,
                operation=name,
                outcome="allowed",
                request_sha256=document_sha256(request),
                effect=effect,
            )
        )
