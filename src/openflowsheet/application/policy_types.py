"""The project policy documents of the application contract v1 (T07 design note §5.9, ADR 0019
D2 and D4; ADR 0076 I-12a): rights, capability references, `ProjectPolicy` and `ReplayPolicy`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Self, get_args

from openflowsheet.application.documents import checked
from openflowsheet.canonical import document_sha256
from openflowsheet.schema_check import DocumentSchemaError, validate_document

#: Blueprint §11.3's six rights (ADR 0019 D4).
Right = Literal["read", "draft", "execute", "install", "policy", "publish"]
RIGHTS: Final[tuple[str, ...]] = get_args(Right)
#: §10.2: the built-in in-process owner's principal and capability id. Reserved: no grant in a
#: project policy may carry either, so no credential can share the owner's ledger scope or jobs.
LOCAL_OWNER_PRINCIPAL: Final[str] = "local-owner"


# ================================================== CapabilityReference and ProjectPolicy §5.9


@dataclass(frozen=True)
class Limits:
    """§5.9: a capability's budget ceilings. `None`: no limit.

    Each non-null wall time is finite and `> 0`, and a default is at most the ceiling (ruling
    round 5b, S5). A violating grant is refused, never clamped.
    """

    default_wall_time_s: float | None = None
    max_wall_time_s: float | None = None
    max_active_jobs: int | None = None

    def __post_init__(self) -> None:
        for name in ("default_wall_time_s", "max_wall_time_s"):
            value = getattr(self, name)
            if value is not None and not (math.isfinite(value) and value > 0):
                raise ValueError(f"{name} {value} is not a finite number > 0")
        default, ceiling = self.default_wall_time_s, self.max_wall_time_s
        if default is not None and ceiling is not None and default > ceiling:
            raise ValueError(f"default_wall_time_s {default} exceeds max_wall_time_s {ceiling}")

    def as_document(self) -> dict[str, Any]:
        return {
            "default_wall_time_s": self.default_wall_time_s,
            "max_wall_time_s": self.max_wall_time_s,
            "max_active_jobs": self.max_active_jobs,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(
            default_wall_time_s=document["default_wall_time_s"],
            max_wall_time_s=document["max_wall_time_s"],
            max_active_jobs=document["max_active_jobs"],
        )


@dataclass(frozen=True)
class CapabilityReference:
    """§5.9 and §10.1: what a credential grants. `note` is untrusted and never read for authority.

    `rights` is unique and sorted; an unsorted or repeated list is refused, not reordered.
    """

    capability_id: str
    principal_id: str
    rights: tuple[Right, ...]
    token_sha256: str | None
    limits: Limits = field(default_factory=Limits)
    expires_at: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        unknown = sorted(right for right in self.rights if right not in RIGHTS)
        if unknown:
            raise ValueError(f"unknown rights {unknown}")
        if list(self.rights) != sorted(set(self.rights)):
            raise ValueError(f"rights are unique and sorted, not {list(self.rights)}")

    def as_document(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "principal_id": self.principal_id,
            "rights": list(self.rights),
            "token_sha256": self.token_sha256,
            "limits": self.limits.as_document(),
            "expires_at": self.expires_at,
            "note": self.note,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        reference = "capability-reference.schema.json"
        validate_document(reference, document)
        return checked(reference, cls._build, document)

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        try:
            limits = Limits._build(document["limits"])
        except ValueError as error:  # name the grant, so the operator can find it (S5)
            raise ValueError(f"capability {document['capability_id']!r}: {error}") from error
        return cls(
            capability_id=document["capability_id"],
            principal_id=document["principal_id"],
            rights=tuple(document["rights"]),
            token_sha256=document["token_sha256"],
            limits=limits,
            expires_at=document["expires_at"],
            note=document["note"],
        )


@dataclass(frozen=True)
class ExecutorSettings:
    """§5.9 `executor`: worker count and the forced-stop grace period (§8.2)."""

    max_workers: int = 1
    grace_s: float = 10

    def as_document(self) -> dict[str, Any]:
        return {"max_workers": self.max_workers, "grace_s": self.grace_s}

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        return cls(max_workers=document.get("max_workers", 1), grace_s=document.get("grace_s", 10))


@dataclass(frozen=True)
class ProjectPolicy:
    """§5.9 and §10.3: `project-policy.json`. An invalid file is refused, never defaulted.

    `capability_id` and every non-null `token_sha256` are unique: a presented token must name one
    capability. A null token is never presentable (§10.2), so several may coexist. No grant may
    name `LOCAL_OWNER_PRINCIPAL`, as principal or as capability: a credential sharing the owner's
    principal would share its idempotency scope and its jobs.
    """

    project_id: str
    capabilities: tuple[CapabilityReference, ...]
    executor: ExecutorSettings = field(default_factory=ExecutorSettings)
    schema_version: Literal["project-policy-v1"] = "project-policy-v1"
    #: ADR 0075 D6: the project's declared ambient pressure, Pa — read by gauge display rows
    #: only, never by a run. Absent from the document until declared, so an undeclaring
    #: project's file and `policy_sha256` are what they were before X04.
    ambient_pressure: float | None = None
    #: ADR 0078 D5.1: the operator's switch for in-band administration. Off unless the document
    #: carries `administration: {in_band: true}`; off is absent from the document, so every
    #: policy written before X06 keeps its bytes and `policy_sha256`.
    administration_in_band: bool = False

    def __post_init__(self) -> None:
        if self.ambient_pressure is not None and not (
            isinstance(self.ambient_pressure, float)
            and math.isfinite(self.ambient_pressure)
            and self.ambient_pressure > 0.0
        ):
            raise ValueError(
                f"ambient_pressure {self.ambient_pressure!r} is not a finite pressure > 0 Pa"
            )
        ids = [capability.capability_id for capability in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError(f"capability ids repeat: {sorted(ids)}")
        tokens = [c.token_sha256 for c in self.capabilities if c.token_sha256 is not None]
        if len(tokens) != len(set(tokens)):
            raise ValueError("two capabilities share a token_sha256")
        reserved = [
            c.capability_id
            for c in self.capabilities
            if LOCAL_OWNER_PRINCIPAL in (c.principal_id, c.capability_id)
        ]
        if reserved:
            raise ValueError(
                f"{LOCAL_OWNER_PRINCIPAL!r} is reserved for the in-process owner; "
                f"grants {reserved} name it"
            )

    @property
    def policy_sha256(self) -> str:
        """The document hash a job records at acceptance (§5.5 `policy_sha256`)."""
        return document_sha256(self.as_document())

    def as_document(self) -> dict[str, Any]:
        return (
            {
                "schema_version": self.schema_version,
                "project_id": self.project_id,
                "capabilities": [capability.as_document() for capability in self.capabilities],
                "executor": self.executor.as_document(),
            }
            | ({} if self.ambient_pressure is None else {"ambient_pressure": self.ambient_pressure})
            | ({"administration": {"in_band": True}} if self.administration_in_band else {})
        )

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        reference = "project-policy.schema.json"
        validate_document(reference, document)
        return checked(
            reference,
            lambda d: cls(
                project_id=d["project_id"],
                capabilities=tuple(CapabilityReference._build(c) for c in d["capabilities"]),
                executor=ExecutorSettings._build(d["executor"]),
                schema_version=d["schema_version"],
                ambient_pressure=(
                    None if d.get("ambient_pressure") is None else float(d["ambient_pressure"])
                ),
                administration_in_band="administration" in d,
            ),
            document,
        )


# ================================================ Composite results (§4.2; no schema of their own)


@dataclass(frozen=True)
class ReplayPolicy:
    """§4.2: `reproduce`'s policy. The comparison policy is always `run.compare.POLICY_ID`."""

    rerun: bool = True

    def as_document(self) -> dict[str, Any]:
        return {"rerun": self.rerun}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Self:
        if set(document) != {"rerun"} or not isinstance(document["rerun"], bool):
            raise DocumentSchemaError("ReplayPolicy", "", "a replay policy is {rerun: boolean}")
        return cls(rerun=document["rerun"])


# ========================================== in-band administration results (ADR 0078 D5.2)


@dataclass(frozen=True)
class GrantResult:
    """ADR 0078 D5.2: `grant_capability`'s result. `token` is the new grant's bearer token, in
    this response only: the ledger keeps the result with `token` null, so a replay (`replayed`)
    returns it null (D5.4)."""

    status: Literal["granted", "replayed"]
    capability: CapabilityReference
    token: str | None
    policy_sha256: str

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "capability": self.capability.as_document(),
            "token": self.token,
            "policy_sha256": self.policy_sha256,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        """The inverse of `as_document`, unvalidated: for documents this code wrote itself."""
        return cls(
            status=document["status"],
            capability=CapabilityReference._build(document["capability"]),
            token=document["token"],
            policy_sha256=document["policy_sha256"],
        )


@dataclass(frozen=True)
class RevokeResult:
    """ADR 0078 D5.2: `revoke_capability`'s result: the grant removed and the policy's new hash."""

    status: Literal["revoked", "replayed"]
    capability: CapabilityReference
    policy_sha256: str

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "capability": self.capability.as_document(),
            "policy_sha256": self.policy_sha256,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        """The inverse of `as_document`, unvalidated: for documents this code wrote itself."""
        return cls(
            status=document["status"],
            capability=CapabilityReference._build(document["capability"]),
            policy_sha256=document["policy_sha256"],
        )


@dataclass(frozen=True)
class AmbientPressureResult:
    """ADR 0078 D5.2: `set_ambient_pressure`'s result: the declared pressure in Pa (null when
    cleared) and the policy's new hash."""

    status: Literal["set", "replayed"]
    ambient_pressure_pa: float | None
    policy_sha256: str

    def as_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ambient_pressure_pa": self.ambient_pressure_pa,
            "policy_sha256": self.policy_sha256,
        }

    @classmethod
    def _build(cls, document: Mapping[str, Any]) -> Self:
        """The inverse of `as_document`, unvalidated: for documents this code wrote itself."""
        return cls(
            status=document["status"],
            ambient_pressure_pa=document["ambient_pressure_pa"],
            policy_sha256=document["policy_sha256"],
        )
