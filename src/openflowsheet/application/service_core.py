"""`ServiceCore`: what the services behind `LocalApplication` share (ADR 0076 I-12d).

One core per caller: the store, the record stack (ADR 0061 D8), the project policy, the
caller's capability, the owner instance, the executor and an in-memory project's scratch
directory, with the cross-cutting steps every
operation takes: who the caller is (`caller`), whether it may (`authorize`), and an audited
refusal (`refuse`, `refuse_error`, `audit_refusal`). `LocalApplication.authenticated` acts as
another grant through `acting_as`: the same store, policy, executor and owner, another
capability. The services hold a core and call only it and the services below them.
"""

from __future__ import annotations

import copy
import sqlite3
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, NoReturn

from openflowsheet.application.admission import surrogate_resolver
from openflowsheet.application.authz import LOCAL_OWNER, PolicyFile, StaticPolicy, authorize
from openflowsheet.application.documents import validate_inline
from openflowsheet.application.errors import ApiError, ApiErrorCode, ApplicationError, api_error
from openflowsheet.application.jobs.executor import InlineExecutor, ProcessExecutor
from openflowsheet.application.jobs.runner import RunContext
from openflowsheet.application.model_builders import SurrogateResolver
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.policy_types import CapabilityReference, ProjectPolicy
from openflowsheet.application.store import ProjectStore
from openflowsheet.application.store_records import AuditEntry
from openflowsheet.canonical import first_noncanonical
from openflowsheet.records.importers.legacy import available_records
from openflowsheet.records.stack import LegacyStore, StoreStack
from openflowsheet.records.store import RecordStore
from openflowsheet.schema_check import DocumentSchemaError

#: ADR 0061 D8: the legacy store, one per process: it imports the available legacy files at its
#: first access (F3 decision WO5b-2).
LEGACY_STORE: Final = LegacyStore(available_records)
#: The refusal of a caller whose capability the policy no longer holds.
UNAUTHENTICATED_MESSAGE: Final = (
    "this capability is not in the project policy (revoked or never granted)"
)


def record_stack(directory: Path | None) -> StoreStack:
    """D8's stack of a project: its `<directory>/records/` store, opened at its first operation
    (never at project open), or an in-memory store for an in-memory project; then the legacy
    store."""
    project = RecordStore.in_memory() if directory is None else RecordStore.at(directory)
    return StoreStack(project, LEGACY_STORE)


class ServiceCore:
    """The state and the authorization steps one caller's services share.

    `policy` is the policy source (a `PolicyFile`, hot-reloaded, or a `StaticPolicy`); its
    `current()` is the policy in force now. `executor` is the inline executor until `open`
    starts a process executor.
    """

    def __init__(
        self,
        store: ProjectStore,
        *,
        owner_instance: str,
        policy: PolicyFile | StaticPolicy,
        capability: CapabilityReference | None,
    ) -> None:
        self.store = store
        self.policy = policy
        self._capability = capability
        self.owner_instance = owner_instance
        self.executor: InlineExecutor | ProcessExecutor = InlineExecutor()
        #: An in-memory project's files (bundles, imports) live in a directory of its own,
        #: removed on `close`.
        self._scratch: tempfile.TemporaryDirectory[str] | None = None
        #: ADR 0061 D8, D11: the record stack and, in its project store, the project register.
        self.records: StoreStack = record_stack(store.directory)
        #: ADR 0078 D5.3: the serving process binds a non-loopback interface (`serve-http`
        #: sets it before serving); in-band policy writes are then refused. Stdio and
        #: in-process callers are local. `acting_as` views share it.
        self.serving_remote = False

    def acting_as(self, capability: CapabilityReference) -> ServiceCore:
        """This core acting as `capability`: the same store, policy, executor and owner."""
        view = copy.copy(self)
        view._capability = capability
        return view

    def close(self) -> None:
        """Shut the executor down (§9.3), then release the store and the owner lock."""
        self.executor.shutdown()
        self.store.close()
        if self._scratch is not None:
            self._scratch.cleanup()
            self._scratch = None

    @property
    def project_id(self) -> str:
        return self.store.project_id

    @property
    def principal_id(self) -> str:
        return (self._capability or LOCAL_OWNER).principal_id

    @property
    def capability_id(self) -> str:
        return (self._capability or LOCAL_OWNER).capability_id

    @property
    def files_root(self) -> Path:
        """The directory `jobs/` and `imports/` live under: the project's, or an in-memory
        project's scratch directory."""
        if self.store.directory is not None:
            return self.store.directory
        if self._scratch is None:
            self._scratch = tempfile.TemporaryDirectory(prefix="openflowsheet-")
        return Path(self._scratch.name)

    def surrogates(self) -> SurrogateResolver:
        """The binder's SurrogateManifest resolver over this project's artifacts (M04 spec §8.2).
        Lazy: the store and `files_root` are read only when a revision binds a surrogate."""

        def resolve(sha256: str) -> Mapping[str, Any] | None:
            return surrogate_resolver(self.store, self.files_root)(sha256)

        return resolve

    def context(self) -> RunContext:
        return RunContext(
            store=self.store, root=self.files_root, owner_instance=self.owner_instance
        )

    # ---------------------------------------------------------------------- authorization

    def caller(self, operation: str) -> CapabilityReference:
        """The caller's capability as the current policy states it; 401 if it is gone."""
        caller = self.caller_in(self.policy.current())
        if caller is None:
            return self.refuse("unauthenticated", UNAUTHENTICATED_MESSAGE, operation=operation)
        return caller

    def caller_in(self, policy: ProjectPolicy) -> CapabilityReference | None:
        """The caller's capability as `policy` states it, by `(capability_id, token_sha256)`;
        `LOCAL_OWNER` for the local owner; `None` if `policy` does not hold it."""
        if self._capability is None:
            return LOCAL_OWNER
        for capability in policy.capabilities:
            if (
                capability.capability_id == self._capability.capability_id
                and capability.token_sha256 == self._capability.token_sha256
                and capability.token_sha256 is not None
            ):
                return capability
        return None

    def authorize(
        self,
        operation: str,
        *,
        target_principal: str | None = None,
        request_sha256: str | None = None,
    ) -> CapabilityReference:
        """§10.1 for this call; a refusal is audited and raised."""
        caller = self.caller(operation)
        decision = authorize(caller, operation, target_principal)
        if not decision.allowed:
            assert decision.code is not None
            self.refuse(
                decision.code,
                decision.message,
                operation=operation,
                request_sha256=request_sha256,
                required=list(decision.required),
            )
        return caller

    def check_request(self, operation: str, request: Mapping[str, Any]) -> None:
        """`dispatch`'s steps 1 and 2 for a Python caller (rule C1): the canonical form, then the
        operation's request schema, over `request` as given; a refusal is audited and raised."""
        at = first_noncanonical(request)
        if at is not None:
            self.refuse(
                "document_not_canonical",
                "a value has no canonical JSON form",
                operation=operation,
                pointer=at,
            )
        try:
            validate_inline(operation, OPERATIONS[operation].request_schema, request)
        except DocumentSchemaError as error:
            self.refuse(
                "invalid_request", error.message, operation=operation, pointer=error.pointer
            )

    def audit_allowed(
        self,
        connection: sqlite3.Connection,
        caller: CapabilityReference,
        operation: str,
        request_sha256: str,
        effect: str,
    ) -> None:
        """The `allowed` audit row of a write by `caller`, in the write's transaction."""
        self.store.audit(
            connection,
            AuditEntry(
                principal_id=caller.principal_id,
                capability_id=caller.capability_id,
                operation=operation,
                outcome="allowed",
                request_sha256=request_sha256,
                effect=effect,
            ),
        )

    def refuse(
        self,
        code: ApiErrorCode,
        message: str,
        /,
        *,
        operation: str,
        request_sha256: str | None = None,
        **detail: Any,
    ) -> NoReturn:
        """§10.7: audit a refusal of `operation`, then raise it."""
        self.audit_refusal(operation, code, request_sha256)
        raise api_error(code, message, **detail)

    def refuse_error(self, error: ApiError, operation: str, request_sha256: str | None) -> NoReturn:
        """§10.7: audit a typed refusal, then raise it as it is."""
        self.audit_refusal(operation, error.code, request_sha256)
        raise ApplicationError(error)

    def audit_refusal(self, operation: str, code: str, request_sha256: str | None) -> None:
        self.store.record_audit(
            AuditEntry(
                principal_id=self.principal_id,
                capability_id=self.capability_id,
                operation=operation,
                outcome="refused",
                code=code,
                request_sha256=request_sha256,
            )
        )
