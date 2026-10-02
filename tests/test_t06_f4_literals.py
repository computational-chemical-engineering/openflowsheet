"""T06 F4 WO1: the two additive enum widenings of ADR 0015 (D1, D4), approved by Frank on
2026-09-26 (`docs/T06_DECISIONS.md`).

`solve-policy`'s `globalization.eo_recovery` gains `homotopy_or_sequential_restart`, and
`solve-event`'s `eo_recovery_unsupported` gains `no_restart_initializer`,
`restart_start_unchanged` and `restart_initializer_failed`; the Python `Literal`s widen with them
(design note `docs/design/T06-F4-recovery.md` §0, §5.6). The default stays `homotopy`, and no
committed document spells the new policy value, so no registered policy document moves (§5.8).
The fixtures' byte-for-byte regeneration is `test_t05b_literal.py`'s, `test_k03_schemas.py`'s and
`test_t04_schemas.py`'s, whose generators run unchanged.
"""

from __future__ import annotations

import typing
from pathlib import Path

import pytest
from conftest import load_json
from test_k03_schemas import SCHEMA_DIR, errors_for

from openflowsheet.orchestrator import executor
from openflowsheet.orchestrator.trace import (
    Counters,
    EoRecoveryUnsupported,
    GlobalizationPolicy,
    SolvePolicy,
    Trace,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RESTART = "homotopy_or_sequential_restart"
REASONS = (
    "no_continuation_parameter",
    "no_restart_initializer",
    "restart_start_unchanged",
    "restart_initializer_failed",
)


def _policy(eo_recovery: str) -> SolvePolicy:
    return SolvePolicy(
        policy_id="T06-F4-WO1",
        residual_tolerances={},
        scales={},
        globalization=GlobalizationPolicy(eo_recovery=eo_recovery),  # type: ignore[arg-type]
    )


def _closed(reason: str | None) -> dict[str, typing.Any]:
    trace = Trace()
    executor._bracket(
        trace,
        "region_closed",
        Counters(),
        outcome="BOUND_BLOCKED",
        eo_recovery="unsupported" if reason is not None else None,
        eo_recovery_unsupported=reason,  # type: ignore[arg-type]
    )
    (event,) = trace.events
    return event.as_document()


def test_wo1_the_literals_are_the_schema_enums() -> None:
    policy_schema = load_json(SCHEMA_DIR / "solve-policy.schema.json")
    event_schema = load_json(SCHEMA_DIR / "solve-event.schema.json")
    recovery = policy_schema["properties"]["globalization"]["properties"]["eo_recovery"]["enum"]
    hints = typing.get_type_hints(GlobalizationPolicy)
    assert typing.get_args(hints["eo_recovery"]) == tuple(recovery) == ("homotopy", "none", RESTART)
    assert typing.get_args(EoRecoveryUnsupported) == REASONS
    assert event_schema["properties"]["eo_recovery_unsupported"]["enum"] == [*REASONS, None]


def test_wo1_the_default_is_unchanged() -> None:
    assert GlobalizationPolicy().eo_recovery == "homotopy"
    assert GlobalizationPolicy().as_document()["eo_recovery"] == "homotopy"


@pytest.mark.parametrize("value", ["homotopy", "none", RESTART])
def test_wo1_the_policy_schema_accepts_each_value(value: str) -> None:
    document = _policy(value).as_document()
    assert document["globalization"]["eo_recovery"] == value
    assert errors_for("solve_policy", document) == []


@pytest.mark.parametrize("value", ["sequential_restart", "restart", "", None])
def test_wo1_the_policy_schema_refuses_every_other_value(value: object) -> None:
    document = _policy("homotopy").as_document()
    document["globalization"] = {**document["globalization"], "eo_recovery": value}
    assert errors_for("solve_policy", document) != [], value


@pytest.mark.parametrize("reason", [*REASONS, None])
def test_wo1_the_event_schema_accepts_each_reason(reason: str | None) -> None:
    document = _closed(reason)
    assert document.get("eo_recovery_unsupported") == reason
    assert errors_for("solve_event", document) == []


@pytest.mark.parametrize("reason", ["no_restart", "restart_failed", ""])
def test_wo1_the_event_schema_refuses_every_other_reason(reason: str) -> None:
    document = {**_closed(None), "eo_recovery": "unsupported", "eo_recovery_unsupported": reason}
    assert errors_for("solve_event", document) != [], reason


def test_wo1_no_committed_document_names_the_new_policy_value() -> None:
    """§5.8: no registered case, fixture or reference document carries the new value, so no
    registered policy document or trace moves (the T06 revision policy is built in code)."""
    documents = [
        path.relative_to(REPO_ROOT)
        for root in ("tests/fixtures", "benchmarks")
        for pattern in ("*.json", "*.yaml")
        for path in (REPO_ROOT / root).rglob(pattern)
        if RESTART in path.read_text(encoding="utf-8")
    ]
    assert documents == []
