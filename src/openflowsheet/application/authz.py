"""Authorization: rights, the one decision function, credentials and the policy file (§10).

**The guarantee is the signature.** `authorize(capability, operation, target_principal)` is pure
and reads the capability's `rights` and `expires_at`, the operation name and — for `cancel_job`
only — the target job's principal. No other input exists, so no name, citation, comment, stdout
line or request field can grant a permission: there is nowhere for it to enter (blueprint §11.3,
design note §10.1, ADR 0019 D4). Limits are the capability's too, and admission checks them.

**Credentials.** A bearer token is `prt_` plus 43 base64url characters (32 random bytes); only
its SHA-256 is stored. `authenticate` compares that hash with every grant's in constant time and
never matches a grant whose `token_sha256` is null, which is how `LOCAL_OWNER` — all rights, no
limits, null token — is unreachable from any transport (§10.2).

**Policy.** `project-policy.json` is changed only by the operator's CLI (`project init`, `grant`,
`revoke`), each an atomic replace plus an audit row. `PolicyFile` hot-reloads it on a changed
`(st_mtime_ns, st_size, st_ino)`; a file that fails its schema is refused and never defaulted —
the last valid policy stays in force and the refusal is logged, and with no valid policy at all
nothing opens (§10.3).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal

from openflowsheet.application.store import (
    POLICY_NAME,
    AuditEntry,
    ProjectStore,
    atomic_write_bytes,
    policy_file_bytes,
)
from openflowsheet.application.types import (
    LOCAL_OWNER_PRINCIPAL,
    RIGHTS,
    CapabilityReference,
    Limits,
    ProjectPolicy,
    Right,
)
from openflowsheet.application.validation import utc_timestamp

_LOG = logging.getLogger(__name__)

#: §10.1: the one right each operation needs — the 19 protocol methods and `artifact_bytes`.
#: `cancel_job` of *another* principal's job needs `policy` as well (`CANCEL_OTHERS_RIGHT`).
OPERATION_RIGHTS: Final[Mapping[str, Right]] = {
    # Application (frozen)
    "validate": "read",
    "commit_change": "draft",
    "solve": "execute",
    "reproduce": "execute",
    # JobControl
    "submit_job": "execute",
    "get_job": "read",
    "list_jobs": "read",
    "list_job_events": "read",
    "wait_job": "read",
    "cancel_job": "execute",
    "get_job_result": "read",
    # Inspection
    "get_project": "read",
    "list_models": "read",
    "list_revisions": "read",
    "get_revision": "read",
    "diff_revisions": "read",
    "inspect_structure": "read",
    "preview_change": "read",
    "get_artifact": "read",
    # raw export (Python, CLI, HTTP)
    "artifact_bytes": "read",
}
CANCEL_OTHERS_RIGHT: Final[Right] = "policy"

#: §10.2: the in-process caller. It owns the files; restricting it would be theatre.
LOCAL_OWNER: Final[CapabilityReference] = CapabilityReference(
    capability_id=LOCAL_OWNER_PRINCIPAL,
    principal_id=LOCAL_OWNER_PRINCIPAL,
    rights=tuple(sorted(RIGHTS)),  # type: ignore[arg-type]
    token_sha256=None,
    limits=Limits(),
    expires_at=None,
    note="the built-in in-process owner; no transport can present it",
)

TOKEN_PREFIX: Final[str] = "prt_"
_TOKEN: Final[re.Pattern[str]] = re.compile(r"^prt_[A-Za-z0-9_-]{43}$")

#: §5.9 `project grant`'s agent defaults.
GRANT_DEFAULT_RIGHTS: Final[tuple[Right, ...]] = ("draft", "execute", "read")
GRANT_DEFAULT_LIMITS: Final[Limits] = Limits(
    default_wall_time_s=300, max_wall_time_s=1800, max_active_jobs=4
)


# ============================================================================ the decision


@dataclass(frozen=True)
class Decision:
    """`authorize`'s answer. `code` is the `ApiError` code of a refusal, `None` when allowed."""

    allowed: bool
    code: Literal["forbidden", "unauthenticated"] | None
    required: tuple[Right, ...]
    message: str


def authorize(
    capability: CapabilityReference,
    operation: str,
    target_principal: str | None = None,
    *,
    at: str | None = None,
) -> Decision:
    """§10.1: may `capability` perform `operation`? Pure; `at` defaults to the clock.

    `target_principal` is read for `cancel_job` alone: a job not the caller's own needs `policy`
    as well as `execute`, and an unstated owner counts as another's. An operation outside the
    table is refused — a defect, and the safe side of one.
    """
    right = OPERATION_RIGHTS.get(operation)
    if right is None:
        return Decision(False, "forbidden", (), f"no operation {operation!r} is authorized")
    required: tuple[Right, ...] = (right,)
    if operation == "cancel_job" and target_principal != capability.principal_id:
        required = (right, CANCEL_OTHERS_RIGHT)
    if capability.expires_at is not None and capability.expires_at <= (at or utc_timestamp()):
        return Decision(False, "unauthenticated", required, "the credential has expired")
    missing = [needed for needed in required if needed not in capability.rights]
    if missing:
        return Decision(
            False,
            "forbidden",
            required,
            f"{operation} needs the right(s) {', '.join(missing)}, which this capability "
            "does not hold",
        )
    return Decision(True, None, required, "allowed")


# ============================================================================= credentials


def new_token() -> str:
    """A fresh bearer token: `prt_` + base64url of 32 random bytes, unpadded (43 characters)."""
    return TOKEN_PREFIX + base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def token_sha256(token: str) -> str:
    """What the policy stores: the SHA-256 of the whole token text, `prt_` included."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(
    policy: ProjectPolicy, token: str, *, at: str | None = None
) -> CapabilityReference | None:
    """The grant `token` presents, or `None` (unknown, malformed or expired: 401).

    Every grant with a token hash is compared, in constant time, whatever matched earlier; a
    grant whose `token_sha256` is null is never compared, so it is never presented.
    """
    if not _TOKEN.fullmatch(token):
        return None
    digest = token_sha256(token)
    found: CapabilityReference | None = None
    for capability in policy.capabilities:
        if capability.token_sha256 is None:
            continue
        if hmac.compare_digest(capability.token_sha256, digest):
            found = capability
    if found is None:
        return None
    if found.expires_at is not None and found.expires_at <= (at or utc_timestamp()):
        return None
    return found


# ========================================================================= the policy file


class PolicyRefusedError(RuntimeError):
    """No valid project policy is in force: nothing may open on an invalid one (§10.3)."""


def read_policy(path: Path) -> ProjectPolicy:
    """Parse and schema-validate `path`; any defect raises (`ValueError` or `OSError`)."""

    def refuse_constant(name: str) -> float:
        raise ValueError(f"{name} is not a JSON number")

    document = json.loads(path.read_text(encoding="utf-8"), parse_constant=refuse_constant)
    policy = ProjectPolicy.from_document(document)
    policy.policy_sha256  # noqa: B018 — a policy whose hash has no canonical form is refused
    return policy


class PolicyFile:
    """`project-policy.json`, hot-reloaded on a changed `(st_mtime_ns, st_size, st_ino)`."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._key: tuple[int, int, int] | None = None
        self._policy: ProjectPolicy | None = None
        self.refusals = 0
        self.current()

    def current(self) -> ProjectPolicy:
        """The policy in force: the file's if it changed and is valid, else the last valid one."""
        with self._lock:
            try:
                stat = self.path.stat()
                key: tuple[int, int, int] | None = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
            except OSError:
                key = None
            if key is None or key != self._key:
                try:
                    self._policy = read_policy(self.path)
                except (OSError, ValueError) as error:
                    self.refusals += 1
                    _LOG.warning(
                        "refused project policy %s (%s); %s",
                        self.path,
                        error,
                        "keeping the last valid policy"
                        if self._policy is not None
                        else "no valid policy is in force",
                    )
                    if self._policy is None:
                        raise PolicyRefusedError(
                            f"{self.path} is not a valid project policy: {error}"
                        ) from error
                self._key = key
            assert self._policy is not None
            return self._policy


@dataclass(frozen=True)
class StaticPolicy:
    """The policy of an in-memory project: nobody but the local owner, never changing."""

    policy: ProjectPolicy

    def current(self) -> ProjectPolicy:
        return self.policy


# =================================================== policy administration (operator CLI, §10.3)


class PolicyAdministrationError(ValueError):
    """An operator request the policy cannot take: an unknown right, a reserved principal…"""


#: A policy transformation: `(policy) -> (updated policy, the capability it concerns)`.
type PolicyChange = Callable[[ProjectPolicy], tuple[ProjectPolicy, CapabilityReference]]


def _administer(
    directory: Path, operation: str, change: str, apply: PolicyChange
) -> CapabilityReference:
    """Read-modify-write the policy under the store's write lock, audited in the same step."""
    store = ProjectStore.open(directory)
    try:
        path = directory / POLICY_NAME
        with store.writing() as connection:
            try:
                policy = read_policy(path)
            except (OSError, ValueError) as error:
                raise PolicyAdministrationError(
                    f"{path} is not a valid project policy; repair it before changing it ({error})"
                ) from error
            updated, subject = apply(policy)
            atomic_write_bytes(path, policy_file_bytes(updated))
            store.audit(
                connection,
                AuditEntry(
                    principal_id=LOCAL_OWNER_PRINCIPAL,
                    capability_id=LOCAL_OWNER_PRINCIPAL,
                    operation=operation,
                    outcome="allowed",
                    request_sha256=updated.policy_sha256,
                    effect=f"{change}:{subject.capability_id}",
                ),
            )
        return subject
    finally:
        store.close()


def grant(
    directory: Path,
    *,
    principal_id: str,
    rights: Iterable[str] = GRANT_DEFAULT_RIGHTS,
    limits: Limits = GRANT_DEFAULT_LIMITS,
    expires_at: str | None = None,
    note: str = "",
    capability_id: str | None = None,
) -> tuple[CapabilityReference, str]:
    """Add a grant; return it and its token, which is never stored and never shown again."""
    wanted = sorted(set(rights))
    unknown = [right for right in wanted if right not in RIGHTS]
    if unknown:
        raise PolicyAdministrationError(f"unknown rights {unknown}; the rights are {list(RIGHTS)}")
    if LOCAL_OWNER_PRINCIPAL in (principal_id, capability_id):
        raise PolicyAdministrationError(
            f"{LOCAL_OWNER_PRINCIPAL!r} is the in-process owner and cannot be granted"
        )
    token = new_token()
    capability = CapabilityReference(
        capability_id=capability_id if capability_id is not None else f"cap-{secrets.token_hex(6)}",
        principal_id=principal_id,
        rights=tuple(wanted),  # type: ignore[arg-type]
        token_sha256=token_sha256(token),
        limits=limits,
        expires_at=expires_at,
        note=note,
    )
    # Validates the ids, the timestamp and the note against the schema before anything is written.
    CapabilityReference.from_document(capability.as_document())

    def add(policy: ProjectPolicy) -> tuple[ProjectPolicy, CapabilityReference]:
        if any(c.capability_id == capability.capability_id for c in policy.capabilities):
            raise PolicyAdministrationError(
                f"capability {capability.capability_id!r} already exists"
            )
        return replace(policy, capabilities=(*policy.capabilities, capability)), capability

    return _administer(Path(directory), "project_grant", "grant", add), token


def revoke(directory: Path, capability_id: str) -> CapabilityReference:
    """Remove a grant. A server re-reads the policy on its next call, so it takes effect then."""

    def remove(policy: ProjectPolicy) -> tuple[ProjectPolicy, CapabilityReference]:
        kept = tuple(c for c in policy.capabilities if c.capability_id != capability_id)
        if len(kept) == len(policy.capabilities):
            raise PolicyAdministrationError(f"no capability {capability_id!r} to revoke")
        (removed,) = (c for c in policy.capabilities if c.capability_id == capability_id)
        return replace(policy, capabilities=kept), removed

    return _administer(Path(directory), "project_revoke", "revoke", remove)
