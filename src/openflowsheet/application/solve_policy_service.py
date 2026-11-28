"""The `SolvePolicies` operations (ADR 0078 D4, ADR 0019 Amendment 18): project-registered,
immutable, `user.`-named solve policies.

`register_solve_policy` (right `draft`, ADR 0078 Q5) checks the document
(`orchestrator.policy_validation.solve_policy_problems`, D4.3) and binds its id to its canonical
bytes once (`solve_policy_registry`, D4.4), under the idempotency ledger (ADR 0019 D3, scope
`(principal, operation, key)`): the same id and bytes again is `exists`, other bytes `conflict`,
and nothing is re-bound. `get_solve_policy` (right `read`) shows an offered or a registered
policy and refuses any other id as admission does (`admission.policy_id_refusal`). Each
operation first checks its request as `dispatch` does (rule C1), then authorizes.

The services above call `project_policies` (admission, a job's result) and `summaries`
(`get_project`), so the project's policies are read through one place (D4.7).
`LocalApplication` delegates the two operations here; their documentation is the facade's.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from openflowsheet.application.admission import policy_id_refusal
from openflowsheet.application.inspection_types import SolvePolicyRegistration, SolvePolicyView
from openflowsheet.application.policy_types import CapabilityReference
from openflowsheet.application.service_core import ServiceCore
from openflowsheet.application.solve_policy_registry import (
    ARTIFACT_PREFIX,
    SolvePolicyStoreError,
    artifact_id,
    bind,
    load,
    registered_rows,
)
from openflowsheet.application.store_records import LedgerRow
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.numerics.solve_record import SolvePolicy
from openflowsheet.orchestrator.policies import APPLICATION_POLICIES
from openflowsheet.orchestrator.policy_validation import (
    is_project_policy_id,
    solve_policy_problems,
)


class SolvePolicyService:
    """The solve-policy operations over one caller's `ServiceCore`. Each public method named as
    an operation is the `LocalApplication` method of the same name, documented there."""

    def __init__(self, core: ServiceCore) -> None:
        self._core = core

    def register_solve_policy(
        self, *, policy: Mapping[str, Any], idempotency_key: str
    ) -> SolvePolicyRegistration:
        operation = "register_solve_policy"
        request = {"policy": policy, "idempotency_key": idempotency_key}
        self._checked(operation, request)
        caller = self._core.authorize(operation)
        request_sha256 = document_sha256(request)
        problems = solve_policy_problems(policy)
        if problems:
            first = problems[0]
            detail: dict[str, Any] = {"pointer": "/policy" + first.pointer}
            if first.code is not None:
                detail["code"] = first.code
            self._core.refuse(
                "invalid_request",
                first.message,
                operation=operation,
                request_sha256=request_sha256,
                **detail,
            )
        policy_id = str(policy["policy_id"])
        prior, result = self._bind(caller, policy_id, policy, idempotency_key, request_sha256)
        if prior is not None:
            if prior.request_sha256 != request_sha256:
                self._core.refuse(
                    "idempotency_key_reused",
                    "this idempotency key was used with a different request; use a new key for "
                    "a new request",
                    operation=operation,
                    request_sha256=request_sha256,
                    original_request_sha256=prior.request_sha256,
                )
            original = SolvePolicyRegistration._build(prior.result)
            return SolvePolicyRegistration(
                "replayed", original.policy_id, original.policy_sha256, original.conflict
            )
        assert result is not None
        return result

    def get_solve_policy(self, *, policy_id: str) -> SolvePolicyView:
        operation = "get_solve_policy"
        self._checked(operation, {"policy_id": policy_id})
        self._core.authorize(operation)
        offered = APPLICATION_POLICIES.get(policy_id)
        if offered is not None:
            document = offered.as_document()
            sha256 = hashlib.sha256(canonical_json(document)).hexdigest()
            return SolvePolicyView(policy_id, sha256, "builtin", document)
        project = self._project_policies(operation, policy_id)
        if policy_id not in project:
            refused = policy_id_refusal(policy_id, project)
            if refused is not None:
                self._core.refuse_error(refused, operation, None)
            # `"default"` resolves per route at admission; it names no policy of its own.
            self._core.refuse(
                "not_found",
                f"no registered solve policy {policy_id!r}",
                operation=operation,
                policy_id=policy_id,
                registered=sorted(APPLICATION_POLICIES),
            )
        document = project[policy_id].as_document()
        sha256 = hashlib.sha256(canonical_json(document)).hexdigest()
        return SolvePolicyView(policy_id, sha256, "project", document)

    # ------------------------------------------------------- for the services above (D4.7)

    def project_policies(self, operation: str, policy_id: str) -> Mapping[str, SolvePolicy]:
        """D4.6: the project's registered policies for resolving `policy_id`, read only when it
        is a project policy's id (an offered or unknown id resolves without the store). A
        damaged registration is `internal_error`, audited against `operation`."""
        return self._project_policies(operation, policy_id)

    def summaries(self) -> tuple[tuple[str, str], ...]:
        """D4.5: `(policy_id, policy_sha256)` of each registered policy, by id in bytewise
        ascending order (`get_project` lists them after the offered ones)."""
        return tuple(
            (row.artifact_id.removeprefix(ARTIFACT_PREFIX), row.sha256)
            for row in registered_rows(self._core.store)
        )

    # ------------------------------------------------------------------------------ helpers

    def _bind(
        self,
        caller: CapabilityReference,
        policy_id: str,
        policy: Mapping[str, Any],
        idempotency_key: str,
        request_sha256: str,
    ) -> tuple[LedgerRow | None, SolvePolicyRegistration | None]:
        """D4.4 under the ledger, in one write transaction: the prior row of the same key
        (nothing written), else the registration's result; `registered` writes the policy, its
        ledger row and its `allowed` audit row there."""
        operation = "register_solve_policy"
        data = canonical_json(policy)
        sha256 = hashlib.sha256(data).hexdigest()
        store = self._core.store
        with store.writing() as connection:
            prior = store.ledger_lookup(connection, caller.principal_id, operation, idempotency_key)
            bound = store.artifact_in(connection, artifact_id(policy_id))
            if prior is not None:
                return prior, None
            if bound is not None and bound.sha256 == sha256:
                return None, SolvePolicyRegistration("exists", policy_id, sha256)
            if bound is not None:
                return None, SolvePolicyRegistration(
                    "conflict",
                    policy_id,
                    bound.sha256,
                    {"expected_sha256": sha256, "actual_sha256": bound.sha256},
                )
            bind(connection, self._core.files_root, policy_id, data)
            result = SolvePolicyRegistration("registered", policy_id, sha256)
            store.ledger_insert(
                connection,
                caller.principal_id,
                operation,
                idempotency_key,
                request_sha256,
                result.as_document(),
            )
            effect = f"solve_policy:{policy_id}:registered"
            self._core.audit_allowed(connection, caller, operation, request_sha256, effect)
            return None, result

    def _project_policies(self, operation: str, policy_id: str) -> Mapping[str, SolvePolicy]:
        if not is_project_policy_id(policy_id):
            return {}
        try:
            return load(self._core.store, self._core.files_root)
        except SolvePolicyStoreError as error:
            self._core.refuse(
                "internal_error",
                str(error),
                operation=operation,
                policy_id=error.policy_id,
            )

    def _checked(self, name: str, request: Mapping[str, Any]) -> None:
        """`ServiceCore.check_request` over the members given."""
        self._core.check_request(
            name, {key: value for key, value in request.items() if value is not None}
        )
