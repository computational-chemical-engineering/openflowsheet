"""T07 W1b: the lifecycle checker on programmatic streams (design note §6.3).

One valid stream per way a job can end, then one stream per rule that breaks exactly that rule.
Each violation test asserts the *set of rules* reported, so a checker that reports the right rule
for the wrong reason, or an extra one, fails. These are tests of the checker, not fixtures: real
jobs run it from W4 on (gate G3).
"""

from __future__ import annotations

import dataclasses

import pytest
from t07_support import (
    AT,
    COMPLETED,
    LATER,
    completed_solve,
    event,
    job,
    opaque,
    progress,
    ref,
)

from openflowsheet.application.jobs.model import (
    ENDING_REASONS,
    REQUIRES_STARTED,
    LifecycleViolation,
    check_lifecycle,
    lifecycle_warnings,
)
from openflowsheet.application.types import (
    Job,
    JobEnding,
    JobEvent,
    JobRequest,
    ReproduceBody,
)


def rules(job_: Job, events: list[JobEvent]) -> set[int]:
    return {found.rule for found in check_lifecycle(job_, events)}


def counted(job_: Job, events: list[JobEvent]) -> Job:
    """`job_` with its `event_count` equal to the stream's length, so that a test removing or
    adding an event breaks only the rule it is about, not rule 12 as well."""
    return dataclasses.replace(job_, event_count=len(events))


# ------------------------------------------------------------------------------- valid streams


def test_a_completed_solve_is_valid() -> None:
    finished, events = completed_solve()
    assert check_lifecycle(finished, events) == []
    assert lifecycle_warnings(finished, events) == []


def test_a_queued_job_has_only_its_accepted_event() -> None:
    assert check_lifecycle(job(), [event(0, "accepted")]) == []


def test_a_running_job_has_no_ending_event() -> None:
    events = [
        event(0, "accepted"),
        event(1, "started"),
        event(2, "progress", progress=progress(0, "resolve")),
    ]
    running = job(status="running", started_at=AT, progress=progress(0, "resolve"), event_count=3)
    assert check_lifecycle(running, events) == []


def test_a_job_cancelled_while_queued_never_started() -> None:
    ending = JobEnding(status="cancelled", reason="cancel_requested", interruption=None)
    events = [
        event(0, "accepted"),
        event(1, "cancel_requested"),
        event(2, "ended", ending=ending, error=None),
    ]
    cancelled = job(
        status="cancelled", cancel_requested=True, event_count=3, ended_at=AT, ending=ending
    )
    assert check_lifecycle(cancelled, events) == []


def test_an_interrupted_solve_ends_with_its_partial_trace() -> None:
    """§8.1: the stage in flight finishes, emits the partial trace, and the owner ends the job."""
    ending = JobEnding(status="cancelled", reason="cancel_requested", interruption="cooperative")
    partial = ref("partial_solve_trace", name="partial-solve-events.json")
    events = [
        event(0, "accepted"),
        event(1, "started"),
        event(2, "progress", progress=progress(0, "resolve")),
        event(3, "progress", progress=progress(3, "solve")),
        event(4, "cancel_requested"),
        event(5, "output", output=partial),
        event(6, "ended", ending=ending, error=None),
    ]
    cancelled = job(
        status="cancelled",
        outputs=(partial,),
        progress=progress(3, "solve"),
        cancel_requested=True,
        event_count=7,
        started_at=AT,
        ended_at=LATER,
        ending=ending,
    )
    assert check_lifecycle(cancelled, events) == []
    assert lifecycle_warnings(cancelled, events) == []


def test_a_reproduce_job_without_rerun_has_two_stages() -> None:
    request = JobRequest("reproduce", "key-r", ReproduceBody("import-000001:bundle", rerun=False))
    report = ref("replay_report", name="replay-report.json")
    events = [
        event(0, "accepted"),
        event(1, "started"),
        event(2, "progress", progress=progress(0, "integrity", total=2)),
        event(3, "progress", progress=progress(1, "compare", total=2)),
        event(4, "output", output=report),
        event(5, "ended", ending=COMPLETED, error=None),
    ]
    finished = job(
        operation="reproduce",
        request=request,
        request_sha256=request.request_sha256,
        status="completed",
        outputs=(report,),
        progress=progress(1, "compare", total=2),
        event_count=6,
        started_at=AT,
        ended_at=LATER,
        ending=COMPLETED,
    )
    assert check_lifecycle(finished, events) == []


def test_a_job_with_no_outputs_and_a_null_total_is_valid() -> None:
    failed = JobEnding(status="failed", reason="operation_error", interruption=None)
    events = [
        event(0, "accepted"),
        event(1, "started"),
        event(2, "progress", progress=progress(0, "resolve", total=None)),
        event(3, "progress", progress=progress(1, "bind", total=None)),
        event(4, "ended", ending=failed, error=None),
    ]
    ended = job(status="failed", event_count=5, started_at=AT, ended_at=AT, ending=failed)
    assert check_lifecycle(ended, events) == []


# ------------------------------------------------------------------- each rule, broken alone


def test_rule_1_sequences_are_dense_from_zero() -> None:
    finished, events = completed_solve()
    events[4] = dataclasses.replace(events[4], sequence=40)
    assert rules(finished, events) == {1}
    shorter = [*events[:3], *events[4:]]
    assert rules(counted(finished, shorter), shorter) == {1}


def test_rule_2_the_stream_opens_with_accepted() -> None:
    events = [event(0, "started")]
    assert rules(job(status="running", started_at=AT), events) == {2}
    assert rules(job(event_count=0), []) == {2}


def test_rule_3_a_terminal_job_has_exactly_one_ending_event() -> None:
    finished, events = completed_solve()
    assert rules(counted(finished, events[:-1]), events[:-1]) == {3}
    second = dataclasses.replace(events[-1], sequence=len(events))
    assert rules(counted(finished, [*events, second]), [*events, second]) == {3}


def test_rule_3_a_live_job_has_no_ending_event() -> None:
    finished, events = completed_solve()
    assert rules(dataclasses.replace(finished, status="running"), events) == {3, 6}


def test_rule_3_the_ending_event_is_last() -> None:
    finished, events = completed_solve()
    ending = dataclasses.replace(events[-1], sequence=len(events) - 2)
    late = dataclasses.replace(events[-2], sequence=len(events) - 1)
    reordered = [*events[:-2], ending, late]
    # The output that now follows the ending is still an output event, so rule 5 holds.
    assert rules(finished, reordered) == {3}


def test_rule_4_started_at_most_once() -> None:
    finished, events = completed_solve()
    extra = event(2, "started")
    shifted = [dataclasses.replace(item, sequence=item.sequence + 1) for item in events[2:]]
    assert rules(
        dataclasses.replace(finished, event_count=len(events) + 1), [*events[:2], extra, *shifted]
    ) == {4}


def test_rule_4_started_precedes_progress_and_output() -> None:
    finished, events = completed_solve()
    swapped = [
        events[0],
        dataclasses.replace(events[2], sequence=1),
        dataclasses.replace(events[1], sequence=2),
        *events[3:],
    ]
    assert rules(finished, swapped) == {4}
    missing = [
        dataclasses.replace(item, sequence=index)
        for index, item in enumerate([events[0], *events[2:]])
    ]
    # With no `started` at all, a completed job with `started_at` also breaks rule 13 (a), (b).
    assert rules(counted(finished, missing), missing) == {4, 13}


def test_rule_4_started_only_if_the_job_ran() -> None:
    finished, events = completed_solve()
    assert rules(dataclasses.replace(finished, started_at=None), events) == {4}


def test_rule_5_the_outputs_are_the_output_events_in_order() -> None:
    finished, events = completed_solve()
    reversed_outputs = dataclasses.replace(finished, outputs=finished.outputs[::-1])
    assert rules(reversed_outputs, events) == {5}
    assert rules(dataclasses.replace(finished, outputs=finished.outputs[:2]), events) == {5}
    assert rules(dataclasses.replace(finished, outputs=()), events) == {5}


def test_rule_6_the_status_and_ending_are_the_ending_events() -> None:
    finished, events = completed_solve()
    failed = JobEnding(status="failed", reason="operation_error", interruption=None)
    assert rules(dataclasses.replace(finished, status="failed", ending=failed), events) == {6}
    other_reason = JobEnding(
        status="completed", reason="operation_completed", interruption="cooperative"
    )
    assert rules(dataclasses.replace(finished, ending=other_reason), events) == {6}
    assert rules(dataclasses.replace(finished, ending=None), events) == {6}


def test_rule_7_progress_never_goes_back() -> None:
    finished, events = completed_solve()
    events[5] = dataclasses.replace(events[5], progress=progress(0, "plan"))
    assert rules(finished, events) == {7}


def test_rule_7_the_total_is_fixed_within_a_job() -> None:
    finished, events = completed_solve()
    events[5] = dataclasses.replace(events[5], progress=progress(2, "plan", total=7))
    assert rules(finished, events) == {7}
    events[5] = dataclasses.replace(events[5], progress=progress(2, "plan", total=None))
    assert rules(finished, events) == {7}


def test_rule_8_a_new_stage_after_cancellation_is_a_warning_not_a_violation() -> None:
    finished, events = completed_solve()
    cancel = event(3, "cancel_requested")
    shifted = [dataclasses.replace(item, sequence=item.sequence + 1) for item in events[3:]]
    stream = [*events[:3], cancel, *shifted]
    late = dataclasses.replace(finished, cancel_requested=True, event_count=len(stream))
    assert check_lifecycle(late, stream) == []
    warned = lifecycle_warnings(late, stream)
    assert {found.rule for found in warned} == {8}
    # Five stages start after the cancellation, and all three outputs belong to them.
    assert len(warned) == 5 + 3


def test_rule_9_the_operation_is_the_requests() -> None:
    finished, events = completed_solve()
    assert rules(dataclasses.replace(finished, operation="reproduce"), events) == {9}


def test_rule_11_every_event_is_the_jobs() -> None:
    """Ruling round 1 R6: an event of another job in the stream, whatever its kind — an opaque
    one included — is a violation."""
    finished, events = completed_solve()
    stranger = dataclasses.replace(events[3], job_id="job-000002")
    assert rules(finished, [*events[:3], stranger, *events[4:]]) == {11}
    unknown = opaque(3, "note_v2", ends_job=False)
    stream = [*events[:3], dataclasses.replace(unknown, job_id="job-000009"), *events[4:]]
    assert rules(finished, stream) == {11}
    started = dataclasses.replace(events[1], job_id="job-000002")
    assert rules(finished, [events[0], started, *events[2:]]) == {11}


def test_rule_12_the_event_count_is_the_streams_length() -> None:
    """R6: `event_count` (the next sequence) equals the number of events in one snapshot."""
    finished, events = completed_solve()
    assert finished.event_count == len(events)
    assert rules(dataclasses.replace(finished, event_count=len(events) + 1), events) == {12}
    assert rules(dataclasses.replace(finished, event_count=len(events) - 1), events) == {12}
    assert rules(job(), [event(0, "accepted")]) == set()
    assert rules(job(event_count=2), [event(0, "accepted")]) == {12}


# ------------------------------------------------------------------- rule 10: unknown kinds (J5)


def test_rule_10_an_unknown_kind_counts_for_sequences_and_endings_only() -> None:
    finished, events = completed_solve()
    # An unknown kind mid-stream with a payload that looks like an output and a regressing
    # progress: skipped for rules 4, 5 and 7.
    stranger = opaque(
        4,
        "simulated_time_progress",
        ends_job=False,
        output=ref("trajectory").as_document(),
        progress={"completed": 0, "total": 99, "stage": None},
    )
    shifted = [dataclasses.replace(item, sequence=item.sequence + 1) for item in events[4:]]
    stream = [*events[:4], stranger, *shifted]
    grown = dataclasses.replace(finished, event_count=len(stream))
    assert check_lifecycle(grown, stream) == []
    # Counted for rule 1: its sequence must be dense like any other.
    assert rules(grown, [*events[:4], dataclasses.replace(stranger, sequence=77), *shifted]) == {1}


def test_rule_10_an_unknown_kind_that_ends_the_job_ends_it() -> None:
    finished, events = completed_solve()
    ender = opaque(len(events) - 1, "ended_v2", ends_job=True, verdict="done")
    stream = [*events[:-1], ender]
    # Rule 3 is satisfied through `ends_job`; rule 6 has no payload it can read.
    assert check_lifecycle(finished, stream) == []
    # And a second ending, of any kind, is still a second ending.
    doubled = [*stream, dataclasses.replace(events[-1], sequence=len(events))]
    assert rules(counted(finished, doubled), doubled) == {3}
    # A live job with an unknown ending event is still a live job with an ending event.
    assert rules(dataclasses.replace(finished, status="running", ending=None), stream) == {3}


def test_a_violation_names_its_rule() -> None:
    assert str(LifecycleViolation(5, "outputs differ")) == "rule 5: outputs differ"


@pytest.mark.parametrize("kind", ["accepted", "started", "cancel_requested"])
def test_payload_free_kinds_carry_nothing(kind: str) -> None:
    assert set(event(0 if kind == "accepted" else 1, kind).as_document()) == {
        "job_id",
        "sequence",
        "kind",
        "ends_job",
        "recorded_at",
    }


# ------------------------------------------- rule 13: the transition relation (ruling round 5b)


def _ended_from(
    status: str, reason: str, *, ran: bool, cancel: bool | None = None
) -> tuple[Job, list[JobEvent]]:
    """`accepted [→ started] [→ cancel_requested] → ended(status, reason)`; the request is in the
    stream and the flag set iff `cancel` (default: iff the reason is `cancel_requested`)."""
    cancel = reason == "cancel_requested" if cancel is None else cancel
    ending = JobEnding(status=status, reason=reason, interruption=None)  # type: ignore[arg-type]
    kinds = ["accepted", *(["started"] if ran else []), *(["cancel_requested"] if cancel else [])]
    events = [event(index, kind) for index, kind in enumerate(kinds)]
    events.append(event(len(events), "ended", ending=ending, error=None))
    ended = job(
        status=status,
        cancel_requested=cancel,
        event_count=len(events),
        started_at=AT if ran else None,
        ended_at=LATER,
        ending=ending,
    )
    return ended, events


PAIRS = sorted((status, reason) for status, reasons in ENDING_REASONS.items() for reason in reasons)


def test_s6_t1_the_reviews_probes_break_rule_13() -> None:
    """T07 review S6: each gave `violations=[]` before rule 13."""
    assert rules(*_ended_from("completed", "operation_completed", ran=False)) == {13}
    assert rules(*_ended_from("timed_out", "wall_time_exhausted", ran=False)) == {13}
    for flag in (False, True):  # a requested cancel with no request event, flag set or not
        ended, events = _ended_from("cancelled", "cancel_requested", ran=False, cancel=False)
        assert rules(dataclasses.replace(ended, cancel_requested=flag), events) == {13}


@pytest.mark.parametrize("pair", PAIRS)
def test_s6_t2_each_ending_from_queued_and_from_running(pair: tuple[str, str]) -> None:
    assert len(PAIRS) == 10
    from_queued = rules(*_ended_from(*pair, ran=False))
    assert from_queued == ({13} if pair in REQUIRES_STARTED else set())
    assert rules(*_ended_from(*pair, ran=True)) == set()


def test_s6_t3_every_ending_is_classified() -> None:
    """A new reason fails here until §6.1's table classifies it."""
    assert set(PAIRS) >= REQUIRES_STARTED
    assert set(PAIRS) - REQUIRES_STARTED == {
        ("failed", "worker_lost"),
        ("failed", "owner_lost"),
        ("cancelled", "cancel_requested"),
        ("cancelled", "server_shutdown"),
        ("cancelled", "keyboard_interrupt"),
    }


def test_s6_t4_the_status_and_started_at_agree_with_the_stream() -> None:
    accepted, started = event(0, "accepted"), event(1, "started")
    assert rules(job(started_at=AT, event_count=2), [accepted, started]) == {13}
    assert rules(job(status="running"), [accepted]) == {13}
    assert rules(job(started_at=AT), [accepted]) == {13}


def test_s6_t5_the_cancel_flag_agrees_with_one_request() -> None:
    running = job(status="running", started_at=AT)
    head = [event(0, "accepted"), event(1, "started")]
    twice = [*head, event(2, "cancel_requested"), event(3, "cancel_requested")]
    flagged = dataclasses.replace(running, cancel_requested=True)
    assert rules(counted(flagged, twice), twice) == {13}
    assert rules(counted(flagged, head), head) == {13}
    once = [*head, event(2, "cancel_requested")]
    assert rules(counted(running, once), once) == {13}
    assert rules(counted(flagged, once), once) == set()


def test_s6_t6_an_opaque_ending_imposes_no_transition_requirement() -> None:
    """J5: a newer producer's ending of an unknown kind stays checkable; rule 13's (b) and last
    (c) clause have no payload to read."""
    cancelled = JobEnding(status="cancelled", reason="cancel_requested", interruption=None)
    for status, ending in (("completed", COMPLETED), ("cancelled", cancelled)):
        ended = job(status=status, event_count=2, ended_at=AT, ending=ending)
        stream = [event(0, "accepted"), opaque(1, "ended_v2", ends_job=True, verdict="done")]
        assert rules(ended, stream) == set()
