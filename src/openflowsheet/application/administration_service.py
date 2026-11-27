"""The `Administration` operations (ADR 0078 D5, ADR 0019 Amendment 18): in-band policy
administration, audited, off by default, never beyond the caller, never on a remote server.

Every operation needs `policy` (`authz.OPERATION_RIGHTS`). `get_policy` reads the policy in force.
The three writes (`grant_capability`, `revoke_capability`, `set_ambient_pressure`) are refused,
after `authorize` allowed them and in this order (D5.3): when the project's operator has not
switched in-band administration on (`administration_disabled`), when the serving process binds a
non-loopback interface (`administration_remote_refused`), then by the delegation rule
(`authz.delegation_refusal`, `grant_exceeds_caller`). Inside the write transaction a grant's
existing `capability_id` is `capability_exists`, a revoke's unknown one `capability_not_found`
and a target holding a right the caller lacks `revoke_exceeds_caller`.

A write is `authz.change_policy` inside the transaction that also holds its ledger row (ADR 0019
D3, scope `(principal, operation, key)`): one `allowed` audit row naming the caller, one ledger
row, one atomic replace of the policy file, all or none. A grant's token is in its response only:
the ledger keeps the result with `token` null, so a replay returns it null (D5.4).

`LocalApplication` delegates the four operations here; their documentation is the facade's.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any, NoReturn

from openflowsheet.application.authz import (
    GRANT_DEFAULT_LIMITS,
    GRANT_DEFAULT_RIGHTS,
    PolicyAdministrationError,
    ambient_change,
    ambient_pressure_pa,
    change_policy,
    delegation_refusal,
    new_capability,
    revoke_refusal,
)
from openflowsheet.application.documents import validate_inline
from openflowsheet.application.errors import ApiErrorCode
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.policy_types import (
    AmbientPressureResult,
    CapabilityReference,
    GrantResult,
    Limits,
    ProjectPolicy,
    RevokeResult,
    Right,
)
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.store_records import LedgerRow, StoreError
from openflowsheet.canonical import document_sha256, first_noncanonical
from openflowsheet.schema_check import DocumentSchemaError


class _RefusedError(Exception):
    """A refusal found inside the write transaction: it rolls back, then is audited and raised."""

    def __init__(self, code: ApiErrorCode, message: str, detail: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.code: ApiErrorCode = code
        self.message = message
        self.detail = detail


class AdministrationService:
    """The administration operations over one caller's `ServiceCore`. Each public method named
    as an operation is the `LocalApplication` method of the same name, documented there."""

    def __init__(self, core: ServiceCore) -> None:
        self._core = core

    def get_policy(self) -> ProjectPolicy:
        operation = "get_policy"
        self._checked(operation, {})
        self._core.authorize(operation)
        return self._core.policy.current()

    def grant_capability(
        self,
        *,
        principal_id: str,
        idempotency_key: str,
        rights: Sequence[str] | None = None,
        limits: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        note: str | None = None,
        capability_id: str | None = None,
    ) -> GrantResult:
        operation = "grant_capability"
        request = {
            "principal_id": principal_id,
            "rights": None if rights is None else list(rights),
            "limits": None if limits is None else dict(limits),
            "expires_at": expires_at,
            "note": note,
            "capability_id": capability_id,
            "idempotency_key": idempotency_key,
        }
        request_sha256 = self._admitted(operation, request)
        caller = self._core.caller(operation)
        wanted: tuple[Right, ...] = (
            GRANT_DEFAULT_RIGHTS if rights is None else tuple(sorted(set(rights)))  # type: ignore[arg-type]
        )
        try:
            granted_limits = GRANT_DEFAULT_LIMITS if limits is None else Limits._build(limits)
        except ValueError as error:
            self._invalid(operation, request_sha256, str(error), "/limits")
        requested = CapabilityReference(
            capability_id=capability_id if capability_id is not None else "cap-requested",
            principal_id=principal_id,
            rights=wanted,
            token_sha256=None,
            limits=granted_limits,
            expires_at=expires_at,
            note=note or "",
        )
        refused = delegation_refusal(caller, requested)
        if refused is not None:
            self._core.refuse(
                "forbidden",
                f"grant_exceeds_caller: {refused}",
                operation=operation,
                request_sha256=request_sha256,
                code="grant_exceeds_caller",
            )
        try:
            capability, token = new_capability(
                principal_id=principal_id,
                rights=wanted,
                limits=granted_limits,
                expires_at=expires_at,
                note=note or "",
                capability_id=capability_id,
            )
        except (PolicyAdministrationError, ValueError) as error:
            self._invalid(operation, request_sha256, str(error), "")

        def add(policy: ProjectPolicy) -> tuple[ProjectPolicy, str]:
            if any(c.capability_id == capability.capability_id for c in policy.capabilities):
                raise _RefusedError(
                    "invalid_request",
                    f"capability_exists: capability {capability.capability_id!r} already exists",
                    {"code": "capability_exists", "capability_id": capability.capability_id},
                )
            updated = replace(policy, capabilities=(*policy.capabilities, capability))
            return updated, f"grant:{capability.capability_id}"

        def result(updated: ProjectPolicy) -> GrantResult:
            return GrantResult("granted", capability, None, updated.policy_sha256)

        prior, done = self._write(operation, idempotency_key, request_sha256, caller, add, result)
        if prior is not None:
            original = GrantResult._build(prior.result)
            return GrantResult("replayed", original.capability, None, original.policy_sha256)
        assert isinstance(done, GrantResult)
        return replace(done, token=token)

    def revoke_capability(self, *, capability_id: str, idempotency_key: str) -> RevokeResult:
        operation = "revoke_capability"
        request = {"capability_id": capability_id, "idempotency_key": idempotency_key}
        request_sha256 = self._admitted(operation, request)
        caller = self._core.caller(operation)
        removed: list[CapabilityReference] = []

        def remove(policy: ProjectPolicy) -> tuple[ProjectPolicy, str]:
            found = [c for c in policy.capabilities if c.capability_id == capability_id]
            if not found:
                raise _RefusedError(
                    "not_found",
                    f"capability_not_found: no capability {capability_id!r} to revoke",
                    {"code": "capability_not_found", "capability_id": capability_id},
                )
            refused = revoke_refusal(caller, found[0])
            if refused is not None:
                raise _RefusedError(
                    "forbidden",
                    f"revoke_exceeds_caller: {refused}",
                    {"code": "revoke_exceeds_caller"},
                )
            removed.append(found[0])
            kept = tuple(c for c in policy.capabilities if c.capability_id != capability_id)
            return replace(policy, capabilities=kept), f"revoke:{capability_id}"

        def result(updated: ProjectPolicy) -> RevokeResult:
            return RevokeResult("revoked", removed[0], updated.policy_sha256)

        prior, done = self._write(
            operation, idempotency_key, request_sha256, caller, remove, result
        )
        if prior is not None:
            original = RevokeResult._build(prior.result)
            return RevokeResult("replayed", original.capability, original.policy_sha256)
        assert isinstance(done, RevokeResult)
        return done

    def set_ambient_pressure(
        self, *, value: float | None, idempotency_key: str, unit: str | None = None
    ) -> AmbientPressureResult:
        operation = "set_ambient_pressure"
        request = {"value": value, "unit": unit, "idempotency_key": idempotency_key}
        request_sha256 = self._admitted(operation, request, nullable=("value",))
        caller = self._core.caller(operation)
        pressure: float | None = None
        if value is None and unit is not None:
            self._invalid(
                operation, request_sha256, "a cleared ambient pressure takes no unit", "/unit"
            )
        if value is not None:
            try:
                pressure = ambient_pressure_pa(value, "Pa" if unit is None else unit)
            except StoreError as error:
                self._core.refuse(
                    "invalid_request",
                    str(error),
                    operation=operation,
                    request_sha256=request_sha256,
                    code=error.code,
                    **error.params,
                )

        def result(updated: ProjectPolicy) -> AmbientPressureResult:
            return AmbientPressureResult("set", pressure, updated.policy_sha256)

        prior, done = self._write(
            operation, idempotency_key, request_sha256, caller, ambient_change(pressure), result
        )
        if prior is not None:
            original = AmbientPressureResult._build(prior.result)
            return AmbientPressureResult(
                "replayed", original.ambient_pressure_pa, original.policy_sha256
            )
        assert isinstance(done, AmbientPressureResult)
        return done

    # ------------------------------------------------------------------------------ helpers

    def _admitted(
        self, operation: str, request: Mapping[str, Any], *, nullable: tuple[str, ...] = ()
    ) -> str:
        """The request checked, the caller authorized and the switch and the binding judged
        (D5.3's first two refusals); returns the request's hash."""
        present = {
            key: value for key, value in request.items() if value is not None or key in nullable
        }
        self._checked(operation, present)
        request_sha256 = document_sha256(present)
        self._core.authorize(operation, request_sha256=request_sha256)
        if not self._core.policy.current().administration_in_band:
            self._core.refuse(
                "unsupported",
                "administration_disabled: in-band policy administration is off for this project; "
                "its operator switches it on with `openflowsheet project administration on`",
                operation=operation,
                request_sha256=request_sha256,
                code="administration_disabled",
            )
        if self._core.serving_remote:
            self._core.refuse(
                "unsupported",
                "administration_remote_refused: this server binds a non-loopback interface "
                "without TLS; in-band policy writes are refused on it",
                operation=operation,
                request_sha256=request_sha256,
                code="administration_remote_refused",
            )
        return request_sha256

    def _write(
        self,
        operation: str,
        idempotency_key: str,
        request_sha256: str,
        caller: CapabilityReference,
        apply: Callable[[ProjectPolicy], tuple[ProjectPolicy, str]],
        result: Callable[[ProjectPolicy], Any],
    ) -> tuple[LedgerRow | None, Any]:
        """The ledger lookup, then `change_policy` and the ledger row, in one write transaction.
        Returns the prior ledger row of the same key (nothing written), or the new result."""
        store = self._core.store
        # An in-memory project's policy is static, its switch off: no write reaches here.
        assert store.directory is not None
        done: Any = None
        try:
            with store.writing() as connection:
                prior = store.ledger_lookup(
                    connection, caller.principal_id, operation, idempotency_key
                )
                if prior is None:
                    done = result(
                        change_policy(
                            store,
                            store.directory,
                            operation,
                            apply,
                            actor=caller,
                            request_sha256=request_sha256,
                            connection=connection,
                        )
                    )
                    store.ledger_insert(
                        connection,
                        caller.principal_id,
                        operation,
                        idempotency_key,
                        request_sha256,
                        done.as_document(),
                    )
        except _RefusedError as refusal:
            self._core.refuse(
                refusal.code,
                refusal.message,
                operation=operation,
                request_sha256=request_sha256,
                **refusal.detail,
            )
        except PolicyAdministrationError as error:
            self._core.refuse(
                "internal_error", str(error), operation=operation, request_sha256=request_sha256
            )
        if prior is not None and prior.request_sha256 != request_sha256:
            self._core.refuse(
                "idempotency_key_reused",
                "this idempotency key was used with a different request; use a new key for a new "
                "request",
                operation=operation,
                request_sha256=request_sha256,
                original_request_sha256=prior.request_sha256,
            )
        return prior, done

    def _invalid(self, operation: str, request_sha256: str, message: str, pointer: str) -> NoReturn:
        self._core.refuse(
            "invalid_request",
            message,
            operation=operation,
            request_sha256=request_sha256,
            pointer=pointer,
        )

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
