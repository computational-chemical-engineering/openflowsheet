"""Replay: which of blueprint §8.3's three reports applies, and what the rerun found. K05.

ADR 0007 D4 is the whole design and its first rule is the important one: **the mode is decided
before anything runs**, by comparing the recorded environment with the current one. That
ordering is what makes gate G05's "changed dependency fails exact replay" structural rather
than hopeful — a changed lock file cannot produce a passing exact replay, because the mode was
already `inspected_archived_results` before the first residual was evaluated.

The verdict is separate from the mode, and both are reported:

    mode     exact_replay | compatible_reproduction | inspected_archived_results
    verdict  MATCH | MISMATCH | NOT_RUN

`MATCH` requires every R0 field identical *and* every float within the declared policy. A
structural difference is `MISMATCH` whatever the floats do, because a structural difference is
a defect and never noise. And the one case where "match" and "same verdict" part company is
D2.4's: a verdict word that changed while a near-threshold flag was present is reported as
`MATCH` with `verdict_changed_near_threshold` listed — visibly, by design, because the
alternative is a verdict that flickers with the last bit of a residual and a replay that calls
it a defect.

**A record is compared under the numerical policy it names** (ADR 0025, D1.3 as replaced by
Frank's answer to its Q4): a `K04-numerical-policy-v1` bundle under v1, whose comparator is frozen
bit for bit, and a `T08-numerical-policy-v2` bundle under v2. A bundle naming a policy this build
does not know is inspected and not compared: a policy is never reinterpreted.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from openflowsheet.run.bundle import BundleIntegrity, read_artifact, read_manifest, verify_bundle
from openflowsheet.run.compare import CURRENT_POLICY_ID, KNOWN_POLICY_IDS, differences
from openflowsheet.run.manifest import Environment, environment

ReplayMode = Literal["exact_replay", "compatible_reproduction", "inspected_archived_results"]
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

    def as_document(self) -> dict[str, Any]:
        return {
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


def decide_mode(recorded: Environment, current: Environment) -> tuple[ReplayMode, tuple[str, ...]]:
    """D4's table, evaluated before anything runs. Every reason is named, not summarized."""
    reasons: list[str] = []

    # M3, from the Fable review: an empty lock hash means the file was not found, and two
    # unknowns are not a match. Measured before the fix: `environment(lock_path=...)` pointing
    # at nothing on both sides replayed as `exact_replay`, which is what a non-editable install
    # outside the repository would have produced.
    if not recorded.lock_sha256 or not current.lock_sha256:
        reasons.append(
            "the dependency set is unknown on "
            + (
                "both sides"
                if not recorded.lock_sha256 and not current.lock_sha256
                else ("the archive's side" if not recorded.lock_sha256 else "this side")
            )
            + ": no lock file was found, and two unknowns are not a match"
        )
        return "inspected_archived_results", tuple(reasons)

    if not recorded.same_dependencies(current):
        reasons.append(
            f"the lock file differs: recorded {recorded.lock_sha256[:12] or '(none)'}, "
            f"current {current.lock_sha256[:12] or '(none)'}"
        )
        return "inspected_archived_results", tuple(reasons)

    identity, current_identity = recorded.identity(), current.identity()
    for label, where in (("recorded on", recorded), ("running on", current)):
        if (where.architecture, where.os_name) not in REGISTERED_PLATFORMS:
            reasons.append(
                f"{label} {where.architecture}/{where.os_name}, which is not a registered "
                "platform; nothing has measured how it differs, so the archive is inspected"
            )
            return "inspected_archived_results", tuple(reasons)

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

    # F4, answered by Frank on 2026-09-22: unset is unknown, and unknown is never exact.
    if not (recorded.threads_known() and current.threads_known()):
        unknown = (
            "both sides"
            if not (recorded.threads_known() or current.threads_known())
            else ("the archive's side" if not recorded.threads_known() else "this side")
        )
        reasons.append(
            f"the thread pins are unset on {unknown}, so the effective thread count is "
            "unknown; pin OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS for an "
            "exact replay, as CI does"
        )
        return "compatible_reproduction", tuple(reasons)

    return "exact_replay", tuple(reasons)


@dataclass(frozen=True)
class Rerun:
    """What a caller hands back after re-running: the documents, by artifact name."""

    artifacts: Mapping[str, Any] = field(default_factory=dict)
    #: ADR 0025 D5: each solution-state variable's declared quantity kind, supplied by the code
    #: that reran, from the compiled problem it solved — never inferred from a name. `None` when
    #: the rerun supplies none; v2 then refuses to compare a solution state (a difference).
    variable_kinds: Mapping[str, str] | None = None


def replay(
    directory: Path,
    rerun: Rerun | None = None,
    *,
    current: Environment | None = None,
) -> ReplayReport:
    """Replay a bundle. `rerun` is the fresh result; without one, nothing is re-run.

    The integrity check happens first and unconditionally. A bundle whose bytes disagree with
    its index is not re-run at all: re-running a tampered archive and reporting `MATCH` on the
    parts that happened to survive is the injected-false-success shape in a different costume.
    """
    directory = Path(directory)
    integrity = verify_bundle(directory)
    manifest, _ = read_manifest(directory)
    here = current if current is not None else environment()

    mode, reasons = decide_mode(manifest.environment, here)
    recorded_document = manifest.environment.as_document()
    current_document = here.as_document()

    if not integrity.ok:
        return ReplayReport(
            mode="inspected_archived_results",
            verdict="NOT_RUN",
            integrity=integrity,
            recorded_environment=recorded_document,
            current_environment=current_document,
            reasons=(
                *reasons,
                "the archive failed its integrity check and was not re-run",
            ),
        )

    # ADR 0025 (Q4): the integrity check first, then the policy the record names. One this
    # build does not know is refused before anything is compared; it is never reinterpreted.
    policy_id = manifest.numerical_policy_id
    if policy_id not in KNOWN_POLICY_IDS:
        return ReplayReport(
            mode="inspected_archived_results",
            verdict="NOT_RUN",
            integrity=integrity,
            recorded_environment=recorded_document,
            current_environment=current_document,
            reasons=(*reasons, unknown_policy_reason(policy_id)),
        )

    if mode == "inspected_archived_results" or rerun is None:
        return ReplayReport(
            mode="inspected_archived_results" if mode == "inspected_archived_results" else mode,
            verdict="NOT_RUN",
            integrity=integrity,
            recorded_environment=recorded_document,
            current_environment=current_document,
            reasons=(*reasons, *(() if rerun is not None else ("no rerun was supplied",))),
        )

    found: list[str] = []
    bitwise = True
    changed_near_threshold: list[str] = []
    drifted: set[str] = set()
    kinds = rerun.variable_kinds if policy_id == CURRENT_POLICY_ID else None
    for name in sorted(manifest.artifacts):
        archived = read_artifact(directory, name)
        fresh = rerun.artifacts.get(name)
        if fresh is None:
            found.append(f"{name}: the rerun produced no such artifact")
            continue
        fresh, recorded_differently = _as_recorded(name, fresh, archived, policy_id)
        found += recorded_differently
        found += [
            f"{name}{entry}"
            for entry in differences(fresh, archived, policy_id=policy_id, variable_kinds=kinds)
        ]
        if fresh != archived:
            bitwise = False
        drift = _verdict_drift(name, fresh, archived)
        changed_near_threshold += drift
        if drift:
            drifted.add(name)

    # S4: the loop walks the *archive's* index, so an artifact the rerun produced and the
    # archive lacks was never seen. Measured: a rerun carrying a failure bundle beside the
    # certificate reported MATCH — which is exactly the "never both" case `run_session`
    # forbids, arriving unnoticed.
    for name in sorted(set(rerun.artifacts) - set(manifest.artifacts)):
        found.append(f"{name}: the rerun produced an artifact the archive does not have")
        bitwise = False

    # D2.4: a verdict that moved **while a near-threshold flag was present** is reported as a
    # match with the drift listed. It is the one place "match" and "same verdict" separate,
    # and it applies only where `_verdict_drift` actually fired.
    #
    # The suppression was unconditional, and the Fable review measured the consequence: a
    # certificate whose `verification_status` flipped to FAILED with no near-threshold flag
    # anywhere still reported MATCH. That is the exact failure D4 exists to prevent.
    real = [entry for entry in found if not _is_verdict_only(entry, drifted)]
    verdict: ReplayVerdict = "MATCH" if not real else "MISMATCH"
    return ReplayReport(
        mode=mode,
        verdict=verdict,
        integrity=integrity,
        recorded_environment=recorded_document,
        current_environment=current_document,
        reasons=reasons,
        differences=tuple(found),
        bitwise_floats=bitwise,
        verdict_changed_near_threshold=tuple(changed_near_threshold),
    )


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
