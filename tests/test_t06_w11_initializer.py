"""T06 W11: the legacy tear path types a failed registered initializer (T06 spec §8.7, Amendment 1;
ADR 0014 D10; register R-078). Assertion A62.

SYN-001-nominal with its feed at 450.0 K and 279.0 K (outside the provider's [280, 440] K) and at
400.0 K (inside it, above the feed's bubble point) validates `READY_FOR_SIMULATION`, binds, and —
before this chunk — `solve_tear` raised `SpecificationError` from the partition's evaluation of
the registered initializer, before `plan_built`. Now the solve returns `INITIALIZATION_FAILED`
with a trace of exactly one `solve_closed` event and `plan=None`. That no registered SYN-001 trace
moves is the inertness protocol's (K05's `t02`…`t05b` keys, T02's floats), not this module's.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml

from openflowsheet.application.binding import Binding, bind_revision_or_reason
from openflowsheet.application.validation import validate
from openflowsheet.models import SpecificationError
from openflowsheet.models.syn001.flowsheet import InitializerFailedError, Syn001Flowsheet
from openflowsheet.orchestrator.tear import INITIALIZER_ID, solve_tear

NOMINAL = load_yaml(REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml")

#: §8.7's three feeds and the typed message each must end with (A62). 400.0 K: the prefix up to
#: the colon after `liquid`.
FEEDS: dict[float, tuple[str, bool]] = {
    450.0: (
        "initializer_failed(SYN-001-tear-init-v2): out_of_domain: U-MIX: liquid enthalpy: "
        "temperature 450.0 K outside [280.0, 440.0] K",
        True,
    ),
    279.0: (
        "initializer_failed(SYN-001-tear-init-v2): out_of_domain: U-MIX: liquid enthalpy: "
        "temperature 279.0 K outside [280.0, 440.0] K",
        True,
    ),
    400.0: (
        "initializer_failed(SYN-001-tear-init-v2): unsupported: U-MIX: inlet 0 is not "
        "admissible as a liquid:",
        False,
    ),
}


def flowsheet(feed_temperature: float) -> Syn001Flowsheet:
    revision: dict[str, Any] = copy.deepcopy(NOMINAL)
    (entry,) = (s for s in revision["specifications"] if s["id"] == "SPEC-feed-T")
    entry["value"] = feed_temperature
    assert validate(revision).status == "READY_FOR_SIMULATION"
    binding = bind_revision_or_reason(revision)
    assert isinstance(binding, Binding), binding
    sheet: Syn001Flowsheet = binding.flowsheet
    return sheet


@pytest.mark.parametrize("temperature", FEEDS)
def test_a62_the_tear_path_returns_initialization_failed(temperature: float) -> None:
    expected, exact = FEEDS[temperature]
    result, trace = solve_tear(flowsheet(temperature))
    assert result.outcome == "INITIALIZATION_FAILED"
    if exact:
        assert result.message == expected
    else:
        assert result.message.startswith(expected)
    assert "\n" not in result.message
    assert result.plan is None
    assert (result.attempts, result.iterations, result.checkpoint) == (0, 0, None)
    assert result.x.shape == (0,)
    (event,) = trace.events
    assert event.kind == "solve_closed"
    assert event.outcome == "INITIALIZATION_FAILED"
    assert event.message == result.message
    assert INITIALIZER_ID == "SYN-001-tear-init-v2"


@pytest.mark.parametrize("temperature", FEEDS)
def test_the_initializer_still_raises_a_specification_error(temperature: float) -> None:
    """Every existing `except SpecificationError` still holds: the subclass carries the status
    and the first line, and its text is the one the base class carried."""
    with pytest.raises(SpecificationError) as raised:
        flowsheet(temperature).initial_recycle()
    assert isinstance(raised.value, InitializerFailedError)
    status = "unsupported" if temperature == 400.0 else "out_of_domain"
    assert raised.value.status == status
    assert str(raised.value).startswith(
        f"the once-through pass that defines the registered initializer failed: {status}: "
        f"{raised.value.first_line}"
    )
