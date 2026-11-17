"""The composite and inspection results of the application contract v1 (T07 design note §4.2,
ADR 0019 D2; ADR 0076 I-12a). None has a schema of its own.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Self

from openflowsheet.application.job_records import Job, JobEvent
from openflowsheet.application.policy_types import Limits, Right
from openflowsheet.schema_check import DocumentSchemaError, validate_document

# ================================================ Composite results (§4.2; no schema of their own)


@dataclass(frozen=True)
class SubmitResult:
    """§4.2: `submit_job`'s result. `replayed`: the key and body matched an existing job."""

    job: Job
    replayed: bool

    def as_document(self) -> dict[str, Any]:
        return {"job": self.job.as_document(), "replayed": self.replayed}

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        if set(document) != {"job", "replayed"} or not isinstance(document["replayed"], bool):
            raise DocumentSchemaError("SubmitResult", "", "a submit result is {job, replayed}")
        return cls(
            job=Job.from_document(document["job"], lenient=lenient), replayed=document["replayed"]
        )


@dataclass(frozen=True)
class JobWait:
    """§4.2: `wait_job`'s result — the job, the events after the caller's sequence, and `ended`."""

    job: Job
    events: tuple[JobEvent, ...]
    ended: bool

    def as_document(self) -> dict[str, Any]:
        return {
            "job": self.job.as_document(),
            "events": [event.as_document() for event in self.events],
            "ended": self.ended,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, lenient: bool = False) -> Self:
        if (
            set(document) != {"job", "events", "ended"}
            or not isinstance(document["events"], list)
            or not isinstance(document["ended"], bool)
        ):
            raise DocumentSchemaError("JobWait", "", "a job wait is {job, events, ended}")
        return cls(
            job=Job.from_document(document["job"], lenient=lenient),
            events=tuple(
                JobEvent.from_document(event, lenient=lenient) for event in document["events"]
            ),
            ended=document["ended"],
        )


# ================================================ Inspection results (§4.2; no schema of their own)


@dataclass(frozen=True)
class ServerInfo:
    """§4.2 `get_project`'s `server`: the package, its commit when known, the store's schema."""

    package_version: str
    git_commit: str | None
    store_schema: str

    def as_document(self) -> dict[str, Any]:
        return {
            "package_version": self.package_version,
            "git_commit": self.git_commit,
            "store_schema": self.store_schema,
        }


@dataclass(frozen=True)
class ProjectSummary:
    """§4.2 `get_project`: the project, its head and counts, the solve policies it offers, and
    the caller as the credential makes it — its principal, capability, rights and limits."""

    project_id: str
    head: str | None
    revision_count: int
    #: Every job status, with the number of the project's jobs in it (zero included).
    job_counts: Mapping[str, int]
    #: `(policy_id, policy_sha256)` of each registered application solve policy.
    solve_policies: tuple[tuple[str, str], ...]
    default_policy_id: str
    principal_id: str
    capability_id: str
    rights: tuple[Right, ...]
    limits: Limits
    server: ServerInfo
    #: ADR 0075 D6.3: the project's declared ambient pressure, Pa, or `None` (undeclared).
    ambient_pressure: float | None = None

    def as_document(self) -> dict[str, Any]:
        ambient = self.ambient_pressure
        return {
            "project_id": self.project_id,
            "head": self.head,
            "revision_count": self.revision_count,
            "job_counts": dict(self.job_counts),
            "solve_policies": [
                {"policy_id": policy_id, "policy_sha256": sha256}
                for policy_id, sha256 in self.solve_policies
            ],
            "default_policy_id": self.default_policy_id,
            "principal_id": self.principal_id,
            "capability_id": self.capability_id,
            "rights": list(self.rights),
            "limits": self.limits.as_document(),
            "server": self.server.as_document(),
            "ambient_pressure": None if ambient is None else {"value": ambient, "unit": "Pa"},
        }


@dataclass(frozen=True)
class ModelRegistryView:
    """§4.2 `list_models`: each registered model's declarative signature as a document —
    `{model_id, ports, required, zero, pins, choices}` — in model-id order, each pin and option
    with the `specifications` that pin it (ADR 0019 Amendment 2). Built from the signatures
    alone; nothing is constructed."""

    models: tuple[Mapping[str, Any], ...]

    def as_document(self) -> dict[str, Any]:
        return {"models": [dict(model) for model in self.models]}


@dataclass(frozen=True)
class MessageEntry:
    """ADR 0058 D7 (MSG §3.5, §4.9) `explain`: one message-catalogue entry. The five templates
    (`summary`, `context`, `where`, `why`, `action`) are display forms, `{p}` → `<p>`; `examples`
    are explanations rendered from the entry's example params; `catalogue` is `{id, sha256}`,
    which enters no identity. Read from the catalogue alone; no project state."""

    code: str
    family: str
    kind: str
    complete: bool
    title: str
    summary: str | None
    context: str | None
    where: str | None
    why: str | None
    action: str | None
    params: tuple[Mapping[str, Any], ...]
    gap: Mapping[str, Any] | None
    see_also: tuple[str, ...]
    examples: tuple[Mapping[str, Any], ...]
    docs: str
    deprecated: bool
    replaced_by: str | None
    catalogue: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "family": self.family,
            "kind": self.kind,
            "complete": self.complete,
            "title": self.title,
            "summary": self.summary,
            "context": self.context,
            "where": self.where,
            "why": self.why,
            "action": self.action,
            "params": [dict(param) for param in self.params],
            "gap": None if self.gap is None else dict(self.gap),
            "see_also": list(self.see_also),
            "examples": copy.deepcopy([dict(example) for example in self.examples]),
            "docs": self.docs,
            "deprecated": self.deprecated,
            "replaced_by": self.replaced_by,
            "catalogue": dict(self.catalogue),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        validate_document("application-results.schema.json#/$defs/message_entry", document)
        return cls(
            code=document["code"],
            family=document["family"],
            kind=document["kind"],
            complete=document["complete"],
            title=document["title"],
            summary=document["summary"],
            context=document["context"],
            where=document["where"],
            why=document["why"],
            action=document["action"],
            params=tuple(dict(param) for param in document["params"]),
            gap=None if document["gap"] is None else dict(document["gap"]),
            see_also=tuple(document["see_also"]),
            examples=tuple(copy.deepcopy(dict(example)) for example in document["examples"]),
            docs=document["docs"],
            deprecated=document["deprecated"],
            replaced_by=document["replaced_by"],
            catalogue=dict(document["catalogue"]),
        )


@dataclass(frozen=True)
class RevisionSummary:
    """§4.2 `list_revisions`: one stored revision without its document. `title` is the
    document's own (untrusted) text, or `None` when it has no string title."""

    revision_id: str
    parent_revision: str | None
    content_sha256: str
    title: str | None
    principal_id: str
    created_at: str
    head: bool

    def as_document(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "parent_revision": self.parent_revision,
            "content_sha256": self.content_sha256,
            "title": self.title,
            "principal_id": self.principal_id,
            "created_at": self.created_at,
            "head": self.head,
        }


AuditOutcome = Literal["allowed", "refused"]
AuditOrder = Literal["ascending", "descending"]


@dataclass(frozen=True)
class AuditRecord:
    """ADR 0019 Amendment 3 (A3.3; M06 design note §4.3) `list_audit`: one row of the project's
    audit (§10.7) — an effect or a refusal — as the store holds it. `effect` is `<kind>:<id>`;
    `idempotency_key` is the ledger's key of an `allowed` row whose principal, operation and
    request hash it shares (a keyed request's hash covers its key), else `None`."""

    seq: int
    at: str
    principal_id: str
    capability_id: str
    operation: str
    outcome: AuditOutcome
    code: str | None
    request_sha256: str | None
    effect: str | None
    idempotency_key: str | None

    def as_document(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "at": self.at,
            "principal_id": self.principal_id,
            "capability_id": self.capability_id,
            "operation": self.operation,
            "outcome": self.outcome,
            "code": self.code,
            "request_sha256": self.request_sha256,
            "effect": self.effect,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class CapabilityDescriptor:
    """ADR 0060 D11 (ADR 0019 Amendment 7) `list_capabilities`: one registered descriptor — its
    declared fields, normalised (D2), and the registry's computed ones (`self_sha256`,
    `descriptor_sha256`, `origin`, `distribution`, `distribution_version`, `entry_point`,
    `effective_status`, `evidence_class`, `stability`): `Registered.as_document()`."""

    document: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.document))


@dataclass(frozen=True)
class CapabilityPage:
    """ADR 0060 D11 `list_capabilities`: one page of registered descriptors, sorted by (kind, id,
    version key), with the registry's identity (`registry_sha256`, D10). `next_cursor` continues
    after this page's last item, or is `None` on the last page."""

    registry_sha256: str
    items: tuple[CapabilityDescriptor, ...]
    next_cursor: str | None

    def as_document(self) -> dict[str, Any]:
        return {
            "registry_sha256": self.registry_sha256,
            "items": [item.as_document() for item in self.items],
            "next_cursor": self.next_cursor,
        }


@dataclass(frozen=True)
class AdmissionPair:
    """ADR 0060 D11: D5's verdict on one (unit, method, definition) triple, with the versions it
    was taken on. `instance` is the revision's unit instance (the draft form), else `None`;
    `refusal` and each notice are the registry's `{code, params}`."""

    instance: str | None
    unit: str
    unit_version: str
    method: str
    method_version: str
    definition: str
    admitted: bool
    refusal: Mapping[str, Any] | None
    notices: tuple[Mapping[str, Any], ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "instance": self.instance,
            "unit": self.unit,
            "unit_version": self.unit_version,
            "method": self.method,
            "method_version": self.method_version,
            "definition": self.definition,
            "admitted": self.admitted,
            "refusal": None if self.refusal is None else copy.deepcopy(dict(self.refusal)),
            "notices": [copy.deepcopy(dict(notice)) for notice in self.notices],
        }


@dataclass(frozen=True)
class AdmissionReport:
    """ADR 0060 D11 `check_admission`: the verdict on each pair, `admitted` their conjunction,
    and `notices` every pair's notices, sorted and without repeats (F1 decision W4a-4)."""

    registry_sha256: str
    admitted: bool
    pairs: tuple[AdmissionPair, ...]
    notices: tuple[Mapping[str, Any], ...]

    def as_document(self) -> dict[str, Any]:
        return {
            "registry_sha256": self.registry_sha256,
            "admitted": self.admitted,
            "pairs": [pair.as_document() for pair in self.pairs],
            "notices": [copy.deepcopy(dict(notice)) for notice in self.notices],
        }
