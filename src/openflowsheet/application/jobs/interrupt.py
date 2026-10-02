"""Cooperative interruption of a running job (T07 design note §8.1).

A job body runs inside `interruptible(...)`, which installs a check in
`orchestrator.trace.INTERRUPT_CHECK`. Every `Trace.record` calls it before building its event, and
the runner calls the yielded check again at each stage boundary. The check raises `JobInterrupted`
once cancellation has been requested or the wall-time deadline has passed; otherwise it returns.

**`JobInterrupted` is a `BaseException`**, so the solver's and verifier's `except Exception`
handlers cannot turn a cancellation into a numerical outcome, and `finally` blocks still run (the
`inverse_one_norm_estimate` restore of numpy's global generator among them).
`tests/test_t07_interrupt.py` holds `src/` to handlers that cannot swallow it: no bare `except:`,
and an `except BaseException` only where it re-raises unconditionally.

This module holds the exception and the hook's installation only. The runner that catches
`JobInterrupted` and writes `partial-solve-events.json` and the `worker_result`, and the executors
that own the cancel event, the deadline and the forced stop (§8.2), are W4a's and W4c's.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Literal, Protocol

from openflowsheet.orchestrator.trace import INTERRUPT_CHECK

__all__ = ["CancelSignal", "InterruptReason", "JobInterrupted", "interrupt_check", "interruptible"]

#: §8.1's closed set: why a job stopped before it finished.
InterruptReason = Literal["cancel_requested", "wall_time_exhausted", "server_shutdown"]
#: The two reasons a set cancel signal can carry (wall time is the deadline's, not the signal's).
CancelReason = Literal["cancel_requested", "server_shutdown"]


class JobInterrupted(BaseException):  # noqa: N818 - the design note's name (§8.1)
    """The running job was told to stop. Never a solver outcome; the runner alone catches it."""

    def __init__(self, reason: InterruptReason) -> None:
        super().__init__(reason)
        self.reason: InterruptReason = reason


class CancelSignal(Protocol):
    """What a cancel token must offer: `threading.Event` inline, `multiprocessing.Event` in a
    worker (§8.1)."""

    def is_set(self) -> bool: ...


def interrupt_check(
    cancel: CancelSignal,
    deadline: float | None,
    *,
    cancel_reason: Callable[[], CancelReason] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Callable[[], None]:
    """The check §8.1 installs: raise `JobInterrupted` when `cancel.is_set()` (reason
    `cancel_reason()`, default `cancel_requested`) or when `clock() >= deadline`
    (`wall_time_exhausted`); return otherwise. `deadline` is on `clock`'s scale (`time.monotonic`
    unless a test substitutes one); `None` is no wall-time limit (§8.3). A requested cancellation
    is reported ahead of an exhausted deadline when both hold."""

    def check() -> None:
        if cancel.is_set():
            raise JobInterrupted(
                cancel_reason() if cancel_reason is not None else "cancel_requested"
            )
        if deadline is not None and clock() >= deadline:
            raise JobInterrupted("wall_time_exhausted")

    return check


@contextmanager
def interruptible(
    cancel: CancelSignal,
    deadline: float | None,
    *,
    cancel_reason: Callable[[], CancelReason] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[Callable[[], None]]:
    """Install `interrupt_check(...)` as `INTERRUPT_CHECK` for the body, and yield it for the
    runner's stage-boundary checks. The previous value (normally `None`) is restored on every exit,
    `JobInterrupted` included. The ContextVar is per thread (and per asyncio task), so a check
    installed here reaches only the solve running in this context."""
    check = interrupt_check(cancel, deadline, cancel_reason=cancel_reason, clock=clock)
    token = INTERRUPT_CHECK.set(check)
    try:
        yield check
    finally:
        INTERRUPT_CHECK.reset(token)
