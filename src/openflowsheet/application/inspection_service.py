"""`InspectionService`: the read-only operations about the project, the models, the
capabilities, the message catalogue and the audit log (ADR 0076 I-12d, the lowest service).

`LocalApplication` delegates `get_project`, `list_models`, `list_capabilities`, `explain`,
`list_audit` and `audit_refusal` here; their contract documentation is the facade's. The paged
lists' `limit` check (`check_limit`) is shared with the job and revision lists above.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Sequence
from typing import Any, Final

from openflowsheet.application import capabilities
from openflowsheet.application.contract import Page
from openflowsheet.application.errors import ApiErrorCode, ApplicationError
from openflowsheet.application.inspection_types import (
    AuditOrder,
    AuditRecord,
    CapabilityPage,
    MessageEntry,
    ModelRegistryView,
    ProjectSummary,
    ServerInfo,
)
from openflowsheet.application.jobs.model import JOB_STATUSES
from openflowsheet.application.model_builders import MODEL_BUILDERS
from openflowsheet.application.model_signatures import (
    MODEL_SIGNATURES,
    ModelSignature,
    PinColumn,
    pin_encodings,
)
from openflowsheet.application.projection import MAX_PAGE
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.solve_policy_service import SolvePolicyService
from openflowsheet.application.store import STORE_SCHEMA
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.policies import APPLICATION_POLICIES, DEFAULT_POLICY_ID
from openflowsheet.registry import default_registry

#: ADR 0019 Amendment 3 (A3.3): `list_audit`'s orders, and its `operation` filter's length bound.
AUDIT_ORDERS: Final[tuple[str, ...]] = ("ascending", "descending")
_AUDIT_OPERATION_LIMIT: Final[int] = 128


class InspectionService:
    """The inspection operations over one caller's `ServiceCore`. Each public method is the
    `LocalApplication` method of the same name, documented there; it takes every argument
    explicitly (the defaults are the facade's). Public methods without a facade namesake serve the
    services above this one."""

    def __init__(self, core: ServiceCore, policies: SolvePolicyService) -> None:
        self._core = core
        self._policies = policies

    def get_project(self) -> ProjectSummary:
        from openflowsheet import __version__
        from openflowsheet.run.manifest import policy_sha256

        caller = self._core.authorize("get_project")
        store = self._core.store
        with store.reading() as connection:
            head = store.head(connection)
            revision_count = store.revision_count(connection)
            # Every status is named; a status a newer producer wrote is kept, not dropped (J5).
            job_counts = {status: 0 for status in JOB_STATUSES} | store.job_counts(connection)
        return ProjectSummary(
            project_id=self._core.project_id,
            head=head,
            revision_count=revision_count,
            job_counts=job_counts,
            # ADR 0078 D4.5: the offered policies, then the project's by id.
            solve_policies=tuple(
                (policy_id, policy_sha256(policy))
                for policy_id, policy in sorted(APPLICATION_POLICIES.items())
            )
            + self._policies.summaries(),
            default_policy_id=DEFAULT_POLICY_ID,
            principal_id=caller.principal_id,
            capability_id=caller.capability_id,
            rights=caller.rights,
            limits=caller.limits,
            # No commit is read at run time: the server runs no subprocess for it.
            server=ServerInfo(
                package_version=__version__, git_commit=None, store_schema=STORE_SCHEMA
            ),
            ambient_pressure=self._core.policy.current().ambient_pressure,
        )

    def list_models(self) -> ModelRegistryView:
        self._core.authorize("list_models")
        return ModelRegistryView(
            models=tuple(
                _model_view(MODEL_SIGNATURES[model_id]) for model_id in sorted(MODEL_BUILDERS)
            )
        )

    def list_audit(
        self,
        *,
        principal_id: str | None,
        operation: str | None,
        order: AuditOrder,
        cursor: str | None,
        limit: int,
    ) -> Page[AuditRecord]:
        name = "list_audit"
        self._core.authorize(name, target_principal=principal_id)
        if principal_id is not None and not isinstance(principal_id, str):
            self._core.refuse(
                "invalid_request", "principal_id is an id", operation=name, pointer="/principal_id"
            )
        if operation is not None and (
            not isinstance(operation, str) or not 1 <= len(operation) <= _AUDIT_OPERATION_LIMIT
        ):
            self._core.refuse(
                "invalid_request",
                f"operation is a string of 1 to {_AUDIT_OPERATION_LIMIT} characters",
                operation=name,
                pointer="/operation",
            )
        if order not in AUDIT_ORDERS:
            self._core.refuse(
                "invalid_request",
                f"order is one of {list(AUDIT_ORDERS)}",
                operation=name,
                pointer="/order",
            )
        self.check_limit(limit, MAX_PAGE, name)
        after = self._decode_audit_cursor(cursor, order, name)
        rows, more = self._core.store.list_audit(
            principal_id=principal_id,
            operation=operation,
            descending=order == "descending",
            after_seq=after,
            limit=limit,
        )
        next_cursor = _encode_audit_cursor(order, rows[-1].seq) if more else None
        return Page(items=tuple(rows), next_cursor=next_cursor)

    def explain(self, code: str) -> MessageEntry:
        from openflowsheet.messages.render import entry_document, suggestions  # noqa: PLC0415

        name = "explain"
        self._core.authorize(name)
        if not isinstance(code, str):
            self._core.refuse(
                "invalid_request", "code is a string", operation=name, pointer="/code"
            )
        document = entry_document(code)
        if document is None:
            self._core.refuse(
                "not_found",
                "no such message code",
                operation=name,
                code=code,
                suggestions=suggestions(code),
            )
        return MessageEntry.from_document(document)

    def list_capabilities(
        self,
        *,
        kind: str | Sequence[str] | None,
        id_prefix: str | None,
        cursor: str | None,
        limit: int,
    ) -> CapabilityPage:
        name = "list_capabilities"
        self._core.authorize(name)
        self.check_limit(limit, MAX_PAGE, name)
        try:
            return capabilities.capability_page(
                default_registry(), kind=kind, id_prefix=id_prefix, cursor=cursor, limit=limit
            )
        except ApplicationError as refused:
            self._core.refuse_error(refused.error, name, None)

    def audit_refusal(self, operation: str, code: ApiErrorCode) -> None:
        self._core.audit_refusal(operation, code, None)

    def _decode_audit_cursor(self, cursor: str | None, order: str, operation: str) -> int | None:
        """`list_audit`'s cursor, `{order, seq}`, as the `seq` to continue after; `None` for the
        first page. A cursor of the other order, or one this list did not issue, is refused."""
        if cursor is None:
            return None
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        except (ValueError, TypeError, binascii.Error):
            decoded = None
        seq = decoded.get("seq") if isinstance(decoded, dict) else None
        if (
            not isinstance(decoded, dict)
            or set(decoded) != {"order", "seq"}
            or decoded["order"] not in AUDIT_ORDERS
            or isinstance(seq, bool)
            or not isinstance(seq, int)
            or seq < 0
        ):
            self._core.refuse(
                "invalid_request",
                "cursor is not one this list issued",
                operation=operation,
                pointer="/cursor",
            )
        if decoded["order"] != order:
            self._core.refuse(
                "invalid_request",
                f"cursor was issued for order {decoded['order']!r}, not {order!r}",
                operation=operation,
                pointer="/cursor",
            )
        return int(seq)

    def check_limit(self, limit: int, maximum: int, operation: str) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
            self._core.refuse(
                "invalid_request",
                f"limit is an integer from 1 to {maximum}",
                operation=operation,
                pointer="/limit",
            )


def _model_view(signature: ModelSignature) -> dict[str, Any]:
    """§4.2 `list_models`: one signature as a document — ports (name, direction, multiplicity,
    kind), required and zero-only parameters, the pinned columns always read, and the one-of
    choices of pinned columns; each pin and option with the `specifications` that pin it, its
    `pin_encodings` (ruling round 6, B2 item 4; ADR 0019 Amendment 2)."""

    def pin(column: PinColumn) -> dict[str, Any]:
        return {
            "name": column.name,
            "quantity": column.quantity,
            "port": column.port,
            "specifications": [
                encoding.as_document() for encoding in pin_encodings(signature, column)
            ],
        }

    return {
        "model_id": signature.model_id,
        "ports": [
            {
                "name": port.name,
                "direction": port.direction,
                "multiplicity": port.multiplicity,
                "kind": port.kind,
            }
            for port in signature.ports
        ],
        "required": list(signature.required),
        "zero": list(signature.zero),
        "pins": [pin(column) for column in signature.pins],
        "choices": [
            {"name": choice.name, "options": [pin(option) for option in choice.options]}
            for choice in signature.choices
        ],
    }


def _encode_audit_cursor(order: str, seq: int) -> str:
    """ADR 0019 Amendment 3 (A3.3): `list_audit`'s cursor, `base64url(canonical_json({"order":
    o, "seq": s}))` unpadded, `s` the `seq` of the last row returned."""
    encoded = base64.urlsafe_b64encode(canonical_json({"order": order, "seq": seq}))
    return encoded.decode("ascii").rstrip("=")
