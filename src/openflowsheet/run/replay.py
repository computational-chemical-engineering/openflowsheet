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

from pathlib import Path

from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle
from openflowsheet.run.compare import CURRENT_POLICY_ID, KNOWN_POLICY_IDS, differences
from openflowsheet.run.manifest import Environment, environment

# F8: the v1 rules `replay_v2` reuses live in `run.replay_rules`, which imports neither replay
# module; this module re-exports its public names, so every import path keeps working.
from openflowsheet.run.replay_rules import (
    REGISTERED_PLATFORMS,
    ReplayMode,
    ReplayReport,
    ReplayVerdict,
    Rerun,
    _as_recorded,
    _is_verdict_only,
    _verdict_drift,
    decide_mode,
    unknown_policy_reason,
)

__all__ = [
    "REGISTERED_PLATFORMS",
    "ReplayMode",
    "ReplayReport",
    "ReplayVerdict",
    "Rerun",
    "decide_mode",
    "replay",
    "unknown_policy_reason",
]


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
    # ADR 0067 D5 step 2: a manifest with `bundle_format` is D5's; one without reads on as v1,
    # unchanged. `replay_v2` is imported here, as it was while it imported this module, so that
    # importing `run.replay` stays as light as before (it reuses `run.replay_rules`, not this).
    from openflowsheet.run import replay_v2  # noqa: PLC0415

    if replay_v2.bundle_format(directory) is not None:
        return replay_v2.replay_v2(directory, rerun, current=current)
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
