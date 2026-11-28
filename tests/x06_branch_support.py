"""E-X06-8 (ADR 0078 D2): the race bodies of the branch tests, run in threads and in spawned
processes. Not collected.

`multiprocessing`'s spawn start method imports these by module name in a fresh interpreter, so
they live in an importable module (as `t07_store_support`'s). Each racer opens its own
`LocalApplication` on the project directory, as a second server would, and runs `trials` rounds;
before each round's write it waits at `wait` (a barrier shared with the other racer), so the two
writes of a round contend for the store's write lock.

The rounds, by `kind`, for trial `t` (the project holds the branches the parent created first):

- `commit`: each racer commits on branch `a<t>` from its tip `base` (one must conflict);
- `create`: each racer creates branch `b<t>` at `base` (one must conflict);
- `mixed`: racer 0 commits on `head` from the head it reads, racer 1 on branch `c<t>` from `base`
  (both must commit, each moving only its own ref).
"""

from __future__ import annotations

from collections.abc import Callable
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Barrier
from typing import Any

from openflowsheet.application.local import LocalApplication
from openflowsheet.application.transaction_types import Change, Edit


def _title(text: str, branch: str | None) -> Change:
    return Change(edits=(Edit("set", ("title",), text),), branch=branch)


def race_trials(
    application: LocalApplication,
    kind: str,
    role: int,
    trials: int,
    base: str,
    wait: Callable[[], Any],
) -> list[tuple[str, str | None]]:
    """`(status, revision_id)` of this racer's write in each round."""
    outcomes: list[tuple[str, str | None]] = []
    for t in range(trials):
        key = f"{kind}-{t}-{role}"
        if kind == "create":
            wait()
            created = application.create_branch(name=f"b{t}", revision_id=base, idempotency_key=key)
            outcomes.append((created.status, created.revision_id))
            continue
        if kind == "commit":
            change, expected = _title(f"{t}-{role}", f"a{t}"), base
        elif role == 0:
            with application.store.reading() as connection:
                expected = application.store.head(connection) or base
            change = _title(f"head-{t}", None)
        else:
            change, expected = _title(f"branch-{t}", f"c{t}"), base
        wait()
        result = application.commit_change(change, expected, key)
        outcomes.append((result.status, result.revision_id))
    return outcomes


def race_process(
    directory: str,
    kind: str,
    role: int,
    trials: int,
    base: str,
    barrier: Barrier,
    results: Queue[Any],
) -> None:
    """One racer in its own process; its outcomes go to `results` as `(role, outcomes)`."""
    application = LocalApplication.open(directory)
    try:
        outcomes = race_trials(application, kind, role, trials, base, barrier.wait)
    finally:
        application.close()
    results.put((role, outcomes))
