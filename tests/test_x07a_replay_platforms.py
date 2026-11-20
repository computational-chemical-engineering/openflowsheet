"""X07a: ADR 0007 D4's mode decision over a grid of complete environments (ruling R1.2, WO3 A1).

ADR 0007 Amendment 3 (proposed; `docs/X07a-platform-ruling.md` section 5.1): after the lock rungs,
a replay whose identity, BLAS version and thread pins are equal and known on both sides is
`exact_replay` on any platform, registered or not. The registered set governs only a replay whose
environments differ: there, either side outside it is `inspected_archived_results` with a reason
naming that side, and never `compatible_reproduction`.

The grid holds 288 environments, every axis with at least two values so that each rung changes the
counts: two registered and two unregistered platforms, two Python versions and two BLAS names
(identity members), two BLAS versions, thread pins at "1", "4" or unset, and two locks or none.
Every one of its 82 944 ordered pairs is decided by `decide_mode` and compared with the table T
written out here; the five counts are asserted in closed form.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import replace

from conftest import HOST_PLATFORM, TERMINAL_REPORT

from openflowsheet.run.lock import TEMPLATES
from openflowsheet.run.manifest import THREAD_VARIABLES, Environment, environment
from openflowsheet.run.replay import REGISTERED_PLATFORMS, decide_mode

PLATFORMS = (("x86_64", "Linux"), ("aarch64", "Linux"), ("arm64", "Darwin"), ("AMD64", "Windows"))
LOCKS = ("a" * 64, "b" * 64, "")

GRID: tuple[Environment, ...] = tuple(
    Environment(
        architecture=architecture,
        os_name=os_name,
        os_release="r",
        python_version=python_version,
        lock_sha256=lock,
        blas={"name": name, "version": version},
        threads={variable: threads for variable in THREAD_VARIABLES},
    )
    for (architecture, os_name) in PLATFORMS
    for python_version in ("3.13.1", "3.12.8")
    for name in ("openblas", "accelerate")
    for version in ("0.3.28", "0.3.29")
    for threads in ("1", "4", None)
    for lock in LOCKS
)

#: The ADR 0069 reasons an empty lock gives; a constructed environment has no lock findings.
LOCK_REASONS = {
    TEMPLATES["R_BOTH"].format(findings=TEMPLATES["NONE"]),
    TEMPLATES["R_ARCHIVE"],
    TEMPLATES["R_THIS"].format(findings=TEMPLATES["NONE"]),
}


def _registered(environment: Environment) -> bool:
    return (environment.architecture, environment.os_name) in REGISTERED_PLATFORMS


def _pins_known(environment: Environment) -> bool:
    return all(value is not None for value in environment.threads.values())


def expected(recorded: Environment, current: Environment) -> tuple[str, str]:
    """The table T, its first holding row deciding: the row's label and its mode."""
    if not recorded.lock_sha256 or not current.lock_sha256:
        return "unverified lock", "inspected_archived_results"
    if recorded.lock_sha256 != current.lock_sha256:
        return "differing lock", "inspected_archived_results"
    if (
        recorded.architecture == current.architecture
        and recorded.os_name == current.os_name
        and recorded.python_version == current.python_version
        and recorded.blas == current.blas
        and dict(recorded.threads) == dict(current.threads)
        and _pins_known(recorded)
        and _pins_known(current)
    ):
        return "exact", "exact_replay"
    if not _registered(recorded):
        return "recorded on", "inspected_archived_results"
    if not _registered(current):
        return "running on", "inspected_archived_results"
    return "compatible", "compatible_reproduction"


def test_the_grid_is_the_one_the_ruling_counts() -> None:
    assert len(GRID) == 288
    assert len({repr(env.as_document()) for env in GRID}) == 288
    registered = {platform for platform in PLATFORMS if platform in REGISTERED_PLATFORMS}
    assert len(registered) == 2, "two registered and two unregistered platforms"


def test_every_pair_is_decided_as_the_table_says() -> None:
    """WO3 A1: every ordered pair against T, every non-exact decision with exactly one reason of
    the rung's kind, and the five counts in closed form."""
    counts: Counter[str] = Counter()
    exact_registered = 0
    wrong: list[str] = []
    for recorded, current in itertools.product(GRID, GRID):
        row, mode = expected(recorded, current)
        counts[row] += 1
        got_mode, reasons = decide_mode(recorded, current)
        if row == "exact":
            exact_registered += _registered(recorded)
            ok = got_mode == mode and reasons == ()
        elif len(reasons) != 1 or got_mode != mode:
            ok = False
        elif row == "unverified lock":
            ok = reasons[0] in LOCK_REASONS
        elif row == "differing lock":
            ok = reasons[0].startswith("the lock file differs")
        elif row in ("recorded on", "running on"):
            side = recorded if row == "recorded on" else current
            ok = reasons[0].startswith(
                f"{row} {side.architecture}/{side.os_name}, which is not a registered platform"
            )
        else:
            ok = True
        if not ok and len(wrong) < 5:
            wrong.append(f"{recorded} -> {current}: {got_mode} {reasons}, expected {row}")
    assert not wrong, "\n".join(wrong)

    assert counts["exact"] == 4 * 2 * 2 * 2 * 2 * 2 == 128
    assert exact_registered == 64
    assert counts["compatible"] == 4 * 1152 - 64 == 4544
    assert counts["unverified lock"] + counts["differing lock"] == 82944 * 7 // 9 == 64512
    assert counts["recorded on"] == 2 * 4 * 1152 - 64 == 9152
    assert counts["running on"] == 2 * 2 * 1152 == 4608
    assert sum(counts.values()) == 82944


def test_registration_still_governs_a_replay_whose_environments_differ() -> None:
    """Amendment 3 does not register a platform: on an unregistered platform, two environments
    that differ only in their thread pins are inspected, never reproduced."""
    for architecture, os_name in sorted(set(PLATFORMS) - REGISTERED_PLATFORMS):
        one = replace(GRID[0], architecture=architecture, os_name=os_name)
        other = replace(one, threads={variable: "4" for variable in THREAD_VARIABLES})
        assert decide_mode(one, one) == ("exact_replay", ())
        mode, reasons = decide_mode(one, other)
        assert mode == "inspected_archived_results", architecture
        assert len(reasons) == 1, reasons
        assert reasons[0].startswith(f"recorded on {architecture}/{os_name}, which is not"), reasons


def test_a6_this_hosts_lock_is_verified_and_its_platform_is_the_reported_one() -> None:
    """WO3 A6, logged per leg: the host's `lock_sha256` is non-empty (the lock verifies, Q-6) and
    its `(architecture, os_name)` is `platform.machine(), platform.system()`, the pair the CI
    matrix guard and `REGISTERED_PLATFORMS` are written in."""
    host = environment()
    TERMINAL_REPORT.append(
        f"X07a-A6: lock_sha256 {host.lock_sha256 or '(none)'} on {host.architecture}/{host.os_name}"
    )
    assert host.lock_sha256
    assert (host.architecture, host.os_name) == HOST_PLATFORM
