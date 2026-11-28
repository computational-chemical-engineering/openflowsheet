"""The v1 replay rules both replays apply: ADR 0007 D4's mode decision, the report, and the
comparison helpers (F8, the cycle `run.replay` <-> `run.replay_v2`).

Split out of `run.replay`, whose docstring states the design, so that `run.replay_v2` reuses them
without importing `run.replay`, which dispatches to it (ADR 0067 D5 step 2). `run.replay`
re-exports every public name here and imports back the helpers its `replay` calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from openflowsheet.run.bundle import BundleIntegrity
from openflowsheet.run.compare import CURRENT_POLICY_ID, KNOWN_POLICY_IDS
from openflowsheet.run.lock import TEMPLATES
from openflowsheet.run.manifest import Environment
from openflowsheet.run.manifest_v2 import refuse_reserved_mode

#: Amendment 12 (ADR 0067 D8) adds `forced_replay`, reserved: a report in it is refused
#: `construct_unavailable(forced_replay, TX)` until F8-WO7 builds it with TX.
ReplayMode = Literal[
    "exact_replay", "compatible_reproduction", "inspected_archived_results", "forced_replay"
]
ReplayVerdict = Literal["MATCH", "MISMATCH", "NOT_RUN"]

#: D4: the platforms a bundle may be *reproduced* on rather than merely inspected. Plan §4.2
#: K05 registers one Linux x86-64 and one of {Linux aarch64, macOS arm64}, and Frank chose
#: `ubuntu-24.04-arm` on 2026-09-22 — so the registered pair is the two Linux entries and
#: **macOS arm64 is not among them**. It was, on the reasoning that the plan named it as an
#: option; the Fable review of K05 pointed out that an option nobody took is not a registered
#: platform, and that promising R2 there promises something no CI run has ever measured.
#:
#: Both sides are checked. An *archive recorded* on an unregistered platform is as unknown as
#: a current one: measured before the fix, a bundle claiming s390x replayed as
#: `compatible_reproduction` on x86-64, which asserted a comparability nothing supports.
#:
#: The set governs reproduction across environments; an exact replay compares a run with itself
#: on one platform identity and needs no registration (ADR 0007 Amendment 3).
REGISTERED_PLATFORMS: frozenset[tuple[str, str]] = frozenset(
    {("x86_64", "Linux"), ("aarch64", "Linux")}
)


@dataclass(frozen=True)
class ReplayReport:
    """What replay did and what it found. Both, always, and never one standing for the other."""

    mode: ReplayMode
    verdict: ReplayVerdict
    integrity: BundleIntegrity
    recorded_environment: Mapping[str, Any]
    current_environment: Mapping[str, Any]
    reasons: tuple[str, ...] = ()
    differences: tuple[str, ...] = ()
    bitwise_floats: bool | None = None
    verdict_changed_near_threshold: tuple[str, ...] = ()
    #: Amendment 12 (ADR 0067 D5 steps 5 and 6): a v2 bundle's registry comparison and data
    #: availability. `None`, and absent from the document, for a v1 bundle, whose report keeps
    #: its bytes.
    registry_comparison: Mapping[str, Any] | None = None
    data_availability: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        refuse_reserved_mode({"mode": self.mode})

    def as_document(self) -> dict[str, Any]:
        document = {
            "mode": self.mode,
            "verdict": self.verdict,
            "integrity": self.integrity.as_document(),
            "recorded_environment": dict(self.recorded_environment),
            "current_environment": dict(self.current_environment),
            "reasons": list(self.reasons),
            "differences": list(self.differences),
            "bitwise_floats": self.bitwise_floats,
            "verdict_changed_near_threshold": list(self.verdict_changed_near_threshold),
        }
        if self.registry_comparison is not None:
            document["registry_comparison"] = dict(self.registry_comparison)
        if self.data_availability is not None:
            document["data_availability"] = dict(self.data_availability)
        return document


def decide_mode(recorded: Environment, current: Environment) -> tuple[ReplayMode, tuple[str, ...]]:
    """D4's table, evaluated before anything runs, the first rung that holds deciding the mode
    with its one reason (`exact_replay`, with none, when no rung holds). Every reason is named,
    not summarized. The first rung is `_unverified_lock_reason`, the last
    `_unset_thread_pins_reason`.

    ADR 0007 Amendment 3: after the lock rungs, equal identity, BLAS version and thread pins,
    known on both sides, are `exact_replay` on any platform, registered or not. Registration
    is checked only for a replay whose environments differ."""
    reasons: list[str] = []

    if (reason := _unverified_lock_reason(recorded, current)) is not None:
        reasons.append(reason)
        return "inspected_archived_results", tuple(reasons)

    if not recorded.same_dependencies(current):
        reasons.append(
            f"the lock file differs: recorded {recorded.lock_sha256[:12] or '(none)'}, "
            f"current {current.lock_sha256[:12] or '(none)'}"
        )
        return "inspected_archived_results", tuple(reasons)

    if _alike_and_pinned(recorded, current):
        return "exact_replay", tuple(reasons)

    for label, where in (("recorded on", recorded), ("running on", current)):
        if (where.architecture, where.os_name) not in REGISTERED_PLATFORMS:
            reasons.append(
                f"{label} {where.architecture}/{where.os_name}, which is not a registered "
                "platform; nothing has measured how it differs, so the archive is inspected"
            )
            return "inspected_archived_results", tuple(reasons)

    identity, current_identity = recorded.identity(), current.identity()
    if identity != current_identity:
        reasons.append(
            f"platform identity differs: recorded {identity}, current {current_identity}"
        )
        return "compatible_reproduction", tuple(reasons)

    # S3: the library the arithmetic went through. A lock hash cannot see a wheel rebuilt
    # under an unchanged lock, and the measured non-portability enters at the factorization.
    if not recorded.same_blas_version(current):
        reasons.append(
            f"the BLAS version differs: recorded {recorded.blas.get('version')}, current "
            f"{current.blas.get('version')}"
        )
        return "compatible_reproduction", tuple(reasons)

    if not recorded.same_threads(current):
        # ADR 0007 D6: a differing thread count is a differing environment, and the best
        # available report is a compatible reproduction.
        reasons.append(
            f"thread pins differ: recorded {dict(recorded.threads)}, "
            f"current {dict(current.threads)}"
        )
        return "compatible_reproduction", tuple(reasons)

    if (reason := _unset_thread_pins_reason(recorded, current)) is not None:
        reasons.append(reason)
        return "compatible_reproduction", tuple(reasons)

    return "exact_replay", tuple(reasons)


def _alike_and_pinned(recorded: Environment, current: Environment) -> bool:
    """ADR 0007 Amendment 3's exact rung: equal identity, BLAS version and thread pins, the pins
    known on both sides."""
    if not (recorded.threads_known() and current.threads_known()):
        return False
    return (
        recorded.identity() == current.identity()
        and recorded.same_blas_version(current)
        and recorded.same_threads(current)
    )


def _unverified_lock_reason(recorded: Environment, current: Environment) -> str | None:
    """D4's first rung: the reason when either side's lock hash is empty, naming which side and,
    for this side, its failing distributions (`current.lock_findings`); None when both sides
    recorded a verified lock.

    M3, from the Fable review: an empty lock hash is an unknown dependency set, and two unknowns
    are not a match. ADR 0069 D5 (X05): from X05 on `""` means the lock did not verify, and the
    reason names this side's failing distributions; the archive's findings are not recorded, so
    its side says only that it recorded no verified lock."""
    if not recorded.lock_sha256 or not current.lock_sha256:
        findings = TEMPLATES["JOIN"].join(current.lock_findings) or TEMPLATES["NONE"]
        if not recorded.lock_sha256 and not current.lock_sha256:
            return TEMPLATES["R_BOTH"].format(findings=findings)
        if not recorded.lock_sha256:
            return TEMPLATES["R_ARCHIVE"]
        return TEMPLATES["R_THIS"].format(findings=findings)
    return None


def _unset_thread_pins_reason(recorded: Environment, current: Environment) -> str | None:
    """D4's last rung: the reason when the thread pins are unset on either side, naming the side
    (`threads_known()` read again per side for the name); None when both sides know theirs.

    F4, answered by Frank on 2026-09-22: unset is unknown, and unknown is never exact."""
    if not (recorded.threads_known() and current.threads_known()):
        unknown = (
            "both sides"
            if not (recorded.threads_known() or current.threads_known())
            else ("the archive's side" if not recorded.threads_known() else "this side")
        )
        return (
            f"the thread pins are unset on {unknown}, so the effective thread count is "
            "unknown; pin OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS for an "
            "exact replay, as CI does"
        )
    return None


@dataclass(frozen=True)
class Rerun:
    """What a caller hands back after re-running: the documents, by artifact name."""

    artifacts: Mapping[str, Any] = field(default_factory=dict)
    #: ADR 0025 D5: each solution-state variable's declared quantity kind, supplied by the code
    #: that reran, from the compiled problem it solved — never inferred from a name. `None` when
    #: the rerun supplies none; v2 then refuses to compare a solution state (a difference).
    variable_kinds: Mapping[str, str] | None = None


def _as_recorded(name: str, fresh: Any, archived: Any, policy_id: str) -> tuple[Any, list[str]]:
    """The rerun's document as the archive's policy reads it, and any difference in the one field
    that names a policy (ADR 0025, Q4).

    A rerun by this build records `CURRENT_POLICY_ID` in each document that carries
    `numerical_policy_id` (the certificate, D1.2); an archive made under an earlier known policy
    records that one. The field says which policy a record is compared under — it is not a result
    of the solve — so it is checked to name what this build records, and the rest of the document
    is compared under the archive's policy with the archive's value in its place. Any other value
    in the field is a difference."""
    if (
        policy_id == CURRENT_POLICY_ID
        or not isinstance(fresh, dict)
        or not isinstance(archived, dict)
        or archived.get("numerical_policy_id") != policy_id
        or "numerical_policy_id" not in fresh
    ):
        return fresh, []
    recorded = fresh["numerical_policy_id"]
    found = (
        []
        if recorded == CURRENT_POLICY_ID
        else [
            f"{name}<root>.numerical_policy_id: {recorded!r}; this build records "
            f"{CURRENT_POLICY_ID!r} (ADR 0025 D1.2)"
        ]
    )
    return {**fresh, "numerical_policy_id": policy_id}, found


def unknown_policy_reason(policy_id: str) -> str:
    """Why a record naming an unknown numerical policy is inspected and not compared."""
    return (
        f"recorded under numerical policy {policy_id!r}, which this build does not know "
        f"(it knows {', '.join(sorted(KNOWN_POLICY_IDS))}): a record is compared under the policy "
        "it names and never reinterpreted (ADR 0025, Q4)"
    )


def _verdict_drift(name: str, fresh: Any, archived: Any) -> list[str]:
    """D2.4's case: the verdict word moved *and* something was flagged near its threshold."""
    if not isinstance(fresh, dict) or not isinstance(archived, dict):
        return []
    before, after = archived.get("verification_status"), fresh.get("verification_status")
    if before is None or before == after:
        return []
    flagged = any(
        check.get("near_threshold") for check in fresh.get("checks", []) if isinstance(check, dict)
    ) or any(
        check.get("near_threshold")
        for check in archived.get("checks", [])
        if isinstance(check, dict)
    )
    return [f"{name}: {before} -> {after}"] if flagged else []


def _is_verdict_only(entry: str, drifted: set[str]) -> bool:
    """D2.4 forgives a verdict difference **only** on an artifact whose drift rule fired."""
    if not entry.startswith(tuple(drifted)):
        return False
    return "<root>.verification_status:" in entry
