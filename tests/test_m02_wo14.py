"""M02 WO-14 (design note §14.5): D9's `at_coupling` guard (AC-1).

- AC-1 (D9, R-309): `coupled_run.at_coupling(binding, w)` raises `ValueError` naming every key of
  `w`, sorted, that is not the `unit_id` of a `C1Reactor` of the binding — another unit's id or no
  unit's — and changes nothing; the binding's own reactor ids are accepted, and the values reach
  the rebuilt unit as passed (no coercion).
"""

from __future__ import annotations

import json
import math
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.application.coupled_run import at_coupling, external_units
from openflowsheet.application.revision_run import Route, select_route
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.orchestrator.execution import declaration_identity

LOOP_PATH = REPO_ROOT / "benchmarks" / "m02" / "c1-loop-standin.json"


def binding() -> Any:
    route = select_route(json.loads(LOOP_PATH.read_text(encoding="utf-8")))
    assert isinstance(route, Route)
    return route.binding


# == D9: at_coupling refuses unknown unit ids (AC-1) ===============================================


def test_ac1_at_coupling_refuses_every_key_that_is_not_a_reactor_of_the_binding() -> None:
    bound = binding()
    (reactor,) = external_units(bound)
    other = next(m.unit_id for m in bound.flowsheet.instances if not isinstance(m, C1Reactor))
    w = {"zz-nowhere": (0.2, 1.0), reactor.unit_id: (0.25, 0.0), other: (0.2, 1.0)}
    with pytest.raises(ValueError) as raised:
        at_coupling(bound, w)
    named = sorted(["zz-nowhere", other])
    assert str(raised.value) == (
        "not an embedded C1 reactor of this flowsheet: " + ", ".join(map(repr, named))
    )
    with pytest.raises(ValueError, match="'R'"):
        at_coupling(bound, {"R": (0.25, 0.0)})


def test_ac1_at_coupling_accepts_the_bindings_reactors_and_passes_the_floats_through() -> None:
    bound = binding()
    (reactor,) = external_units(bound)
    x = math.nextafter(0.25, 1.0)
    moved = at_coupling(bound, {reactor.unit_id: (x, -0.0)})
    (unit,) = external_units(moved)
    assert unit.conversion is x
    assert math.copysign(1.0, unit.temperature_rise) == -1.0  # −0.0 kept, bit for bit
    assert declaration_identity(at_coupling(bound, {}).spec) == declaration_identity(bound.spec)
