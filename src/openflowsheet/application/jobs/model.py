"""The job lifecycle: closed producer vocabularies and the checker (T07 design note §5.4–§6.3).

ADR 0008 Amendment 1 C6 binds the shape. **J1:** outputs are an ordered list of typed references.
**J2:** an output event appends exactly one reference, and nothing is read from the payload of the
event that ends the job. **J3:** the operation is a closed request discriminator. **J5:** kinds are
closed for producers and open for consumers, and whether an event ends the job is `ends_job`, never
`kind`. **J6** (recommended, adopted): sequences are dense from 0, progress is operation-neutral
counts, and exactly one event ends a job with nothing after it.

The tables here are the producer side of J5. They mirror the enums of `schemas/job.schema.json` and
`schemas/job-event.schema.json`, and `tests/test_t07_types.py` holds the two equal. A consumer that
meets a kind outside them keeps it opaque (`JobEvent.known`, `ArtifactRef.known`) and never refuses
the document for it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, get_args

if TYPE_CHECKING:
    from openflowsheet.application.types import Job, JobEvent

#: J3's closed discriminator (§5.3). A later operation is an added value and an added `oneOf`
#: branch in `job.schema.json#/$defs/job_request`; resume would arrive as `solve_resume`.
JobOperation = Literal["solve", "reproduce"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled", "timed_out"]
TerminalStatus = Literal["completed", "failed", "cancelled", "timed_out"]
EventKind = Literal["accepted", "started", "progress", "output", "cancel_requested", "ended"]
Interruption = Literal["cooperative", "forced"]
EndingReason = Literal[
    "operation_completed",
    "operation_error",
    "verifier_refused",
    "worker_lost",
    "owner_lost",
    "store_error",
    "cancel_requested",
    "server_shutdown",
    "keyboard_interrupt",
    "wall_time_exhausted",
]
#: §5.4, producer kinds version 1; `solution_state` added by ruling round 2 and `solve_path` (the
#: bundle's `solve-path.json`, ruling round 1 R2.4) by the W1 follow-up, both additively.
ArtifactKind = Literal[
    "solve_trace",
    "solve_plan",
    "execution_plan",
    "structural_report",
    "solution_certificate",
    "solution_state",
    "failure_bundle",
    "revision_document",
    "solve_policy",
    "check_policy",
    "solve_path",
    "run_manifest",
    "replay_bundle",
    "replay_report",
    "partial_solve_trace",
    "worker_log",
]

JOB_OPERATIONS: Final[tuple[str, ...]] = get_args(JobOperation)
JOB_STATUSES: Final[tuple[str, ...]] = get_args(JobStatus)
TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(get_args(TerminalStatus))
EVENT_KINDS: Final[tuple[str, ...]] = get_args(EventKind)
ARTIFACT_KINDS: Final[tuple[str, ...]] = get_args(ArtifactKind)

#: §5.5: the reasons each terminal status may carry.
ENDING_REASONS: Final[Mapping[str, frozenset[str]]] = {
    "completed": frozenset({"operation_completed"}),
    "failed": frozenset(
        {"operation_error", "verifier_refused", "worker_lost", "owner_lost", "store_error"}
    ),
    "cancelled": frozenset({"cancel_requested", "server_shutdown", "keyboard_interrupt"}),
    "timed_out": frozenset({"wall_time_exhausted"}),
}

#: §6.1's table (ruling round 5b, S6): the endings only a job that ran can reach. Every other
#: pair of `ENDING_REASONS` is reachable from `queued` too. Rule 13(b) of §6.3 checks it.
REQUIRES_STARTED: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("completed", "operation_completed"),
        ("failed", "operation_error"),
        ("failed", "verifier_refused"),
        ("failed", "store_error"),
        ("timed_out", "wall_time_exhausted"),
    }
)

#: §5.6: each producer kind's `ends_job` and the payload members its branch carries.
ENDS_JOB: Final[Mapping[str, bool]] = {kind: kind == "ended" for kind in EVENT_KINDS}
EVENT_PAYLOAD: Final[Mapping[str, tuple[str, ...]]] = {
    "accepted": (),
    "started": (),
    "progress": ("progress",),
    "output": ("output",),
    "cancel_requested": (),
    "ended": ("ending", "error"),
}
PAYLOAD_MEMBERS: Final[tuple[str, ...]] = ("progress", "output", "ending", "error")

#: §5.4: the fixed file name of each producer kind; any other name is a producer defect.
#: `replay_bundle` is a directory and has no fixed name.
ARTIFACT_FILE_NAMES: Final[Mapping[str, str | None]] = {
    "solve_trace": "solve-events.json",
    "solve_plan": "solve-plan.json",
    "execution_plan": "execution-plan.json",
    "structural_report": "structural-report.json",
    "solution_certificate": "solution-certificate.json",
    #: Ruling round 2 (V17 F1): a bundle member beside the certificate, never an output.
    "solution_state": "solution-state.json",
    "failure_bundle": "failure-bundle.json",
    "revision_document": "revision.json",
    "solve_policy": "solve-policy.json",
    "check_policy": "check-policy.json",
    #: Ruling round 1 R2.4's route record; the kind is named as its siblings are, after the file.
    "solve_path": "solve-path.json",
    "run_manifest": "run-manifest.json",
    "replay_bundle": None,
    "replay_report": "replay-report.json",
    "partial_solve_trace": "partial-solve-events.json",
    "worker_log": "worker.log",
}


@dataclass(frozen=True)
class LifecycleViolation:
    """One broken rule of §6.3, by its number there."""

    rule: int
    message: str

    def __str__(self) -> str:
        return f"rule {self.rule}: {self.message}"


def check_lifecycle(job: Job, events: Sequence[JobEvent]) -> list[LifecycleViolation]:
    """§6.3: the violations of a job's recorded lifecycle; empty means valid.

    `events` is the job's whole stream in stored order. An event whose kind this producer does
    not know (J5) is skipped for rules 4, 5 and 7 but counted for rules 1 and 3, so an unknown
    event that ends the job still ends it. Rule 6 compares a *known* ending event's payload; an
    opaque ending event has no payload this checker can read, so it is exempt from rule 6 and
    from rule 13's (b) and last (c) clause. Rule 8 is a warning, not a violation:
    `lifecycle_warnings`.
    """
    found: list[LifecycleViolation] = []

    def violation(rule: int, message: str) -> None:
        found.append(LifecycleViolation(rule, message))

    # Rule 1: dense sequences from 0 (J6).
    sequences = [event.sequence for event in events]
    if sequences != list(range(len(events))):
        violation(1, f"sequences are {sequences}, not 0..{len(events) - 1}")

    # Rule 2: the stream opens with `accepted`.
    if not events or events[0].kind != "accepted":
        first = events[0].kind if events else None
        violation(2, f"the first event is {first!r}, not 'accepted'")

    # Rule 3: exactly one ending event iff the job is terminal, and it is last (J5: `ends_job`).
    enders = [index for index, event in enumerate(events) if event.ends_job]
    terminal = job.status in TERMINAL_STATUSES
    if terminal and len(enders) != 1:
        violation(3, f"a {job.status} job has {len(enders)} ending events, not exactly one")
    if not terminal and enders:
        violation(3, f"a {job.status} job has {len(enders)} ending event(s), not none")
    for index in enders:
        if index != len(events) - 1:
            violation(3, f"the ending event at position {index} is not last")

    known = [event for event in events if event.known]

    # Rule 4: `started` at most once, before any progress or output, and only if the job ran.
    started = [index for index, event in enumerate(known) if event.kind == "started"]
    if len(started) > 1:
        violation(4, f"'started' appears {len(started)} times")
    working = [index for index, event in enumerate(known) if event.kind in ("progress", "output")]
    if working and (not started or started[0] > working[0]):
        violation(4, "a progress or output event precedes 'started'")
    if started and job.started_at is None:
        violation(4, "'started' was recorded for a job that never ran (started_at is null)")

    # Rule 5: the job's outputs are exactly the output events' references, in order (J1, J2).
    emitted = [event.output for event in known if event.kind == "output"]
    if emitted != list(job.outputs):
        violation(5, "the job's outputs are not the output events' references in order")

    # Rule 6: the job's status and ending are the ending event's.
    if len(enders) == 1 and events[enders[0]].known:
        ending = events[enders[0]].ending
        if ending is None or job.status != ending.status:
            ended_as = ending.status if ending is not None else None
            violation(6, f"the job is {job.status!r} but its ending event says {ended_as!r}")
        if job.ending != ending:
            violation(6, "the job's ending is not its ending event's")

    # Rule 7: progress counts never go back, and the total is fixed within a job.
    progress = [event.progress for event in known if event.progress is not None]
    completed = [item.completed for item in progress]
    if completed != sorted(completed):
        violation(7, f"progress.completed decreases: {completed}")
    totals = {item.total for item in progress}
    if len(totals) > 1:
        violation(7, f"progress.total changes within the job: {sorted(totals, key=str)}")

    # Rule 9: the job's operation is its request's.
    if job.operation != job.request.operation:
        violation(9, f"operation {job.operation!r} differs from the request's")

    # Rule 11 (ruling round 1 R6): every event is this job's.
    strangers = sorted({event.job_id for event in events if event.job_id != job.job_id})
    if strangers:
        violation(11, f"events of other jobs {strangers} are in {job.job_id}'s stream")

    # Rule 12 (R6): the job's event count is its stream's length, read in one snapshot.
    if job.event_count != len(events):
        violation(12, f"event_count is {job.event_count}, and the stream has {len(events)} events")

    # Rule 13 (ruling round 5b, S6): §6.1's transition relation. `ran`: a `started` event.
    # (a) The status and `started_at` agree with the stream.
    ran = bool(started)
    if job.status == "queued" and ran:
        violation(13, "a queued job has a 'started' event")
    if job.status == "running" and not ran:
        violation(13, "a running job has no 'started' event")
    if job.started_at is not None and not ran:
        violation(13, "started_at is set, and the stream has no 'started' event")
    # (b) An ending only a job that ran can reach. An opaque ending event is exempt (J5).
    ender = events[enders[0]] if len(enders) == 1 and events[enders[0]].known else None
    ended = ender.ending if ender is not None else None
    pair = (ended.status, ended.reason) if ended is not None else None
    if pair in REQUIRES_STARTED and not ran:
        violation(13, f"the job ended {pair} and never started")
    # (c) At most one request, the flag iff a request, and a request behind a requested cancel.
    requests = sum(1 for event in known if event.kind == "cancel_requested")
    if requests > 1:
        violation(13, f"'cancel_requested' appears {requests} times")
    if job.cancel_requested != (requests > 0):
        violation(13, f"cancel_requested is {job.cancel_requested}, with {requests} request(s)")
    if pair == ("cancelled", "cancel_requested") and not requests:
        violation(13, "the job ended ('cancelled', 'cancel_requested') with no request")

    return found


def lifecycle_warnings(job: Job, events: Sequence[JobEvent]) -> list[LifecycleViolation]:
    """§6.3 rule 8, a warning: work after `cancel_requested` beyond the stage in flight.

    Progress is emitted at the *start* of a stage (§6.4), so the stage in flight at cancellation
    may still finish and emit its outputs — an interrupted solve's partial trace among them
    (§8.1). A `progress` event after `cancel_requested` starts a new stage, and it and any output
    after it are what this rule warns about. `job` is accepted for symmetry with
    `check_lifecycle`; the rule reads only the stream.
    """
    del job
    found: list[LifecycleViolation] = []
    cancelled = False
    new_stage = False
    for event in events:
        if not event.known:
            continue
        if event.kind == "cancel_requested":
            cancelled = True
        elif cancelled and event.kind == "progress":
            new_stage = True
            found.append(
                LifecycleViolation(8, f"event {event.sequence} starts a stage after cancellation")
            )
        elif new_stage and event.kind == "output":
            found.append(
                LifecycleViolation(
                    8, f"event {event.sequence} is an output of a stage started after cancellation"
                )
            )
    return found
