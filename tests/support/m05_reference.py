"""TR-E2's independent expectation T_ref (M05 design note §5.2; ADR 0039 D2): the C1 loop solved
at fixed reactor-inlet temperature with a tightly coupled reference, then golden-section search.

Test support, not TRF and not Pyomo:

- the inner EO problem is solved at pinned w = (X̂, ΔT̂) through M02's accessor
  `revision_binding.with_coupling` and the revision route (`plan_revision`, `execute_plan`);
- the synthetic truth `m05-synthetic-interior-v1` is evaluated at the solved reactor inlet in
  closed form (`m05_synthetic.interior`);
- Newton on F(w) = w − (X_E, ΔT_E) uses a 2 × 2 forward-difference Jacobian (h = 1e-7 scaled;
  scales 0.1 and 10 K) and stops at ‖F‖_scaled,∞ ≤ 1e-12;
- golden-section search over T_in ∈ [653.15, 693.15] K narrows the bracket to ≤ 0.05 K (14
  golden steps); T_ref is the best point evaluated.

It has no M02 coupling-tolerance noise. The objective is `c1-obj-nh3-liquid-v1`: the NH₃ flow of
the flash's liquid outlet.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

import m05_synthetic as synthetic

from openflowsheet.application.policies import APPLICATION_POLICIES
from openflowsheet.application.revision_binding import (
    RevisionBinding,
    bind_revision_flowsheet,
    with_coupling,
)
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.thermo.pr_c1 import COMPONENTS

__all__ = ["BOX", "Reference", "coupled", "golden_section", "reactor_of", "with_inlet_temperature"]

POLICY: Final = APPLICATION_POLICIES["T06-revision-v2"]
#: §5.2: TR-E2's decision box, K.
BOX: Final = (653.15, 693.15)
#: §5.2: the coupling scales (0.1, 10 K), the FD step 1e-7 scaled, the stop ‖F‖_scaled ≤ 1e-12.
SCALES: Final = (0.1, 10.0)
STEP: Final = 1e-7
TOLERANCE: Final = 1e-12
MAX_NEWTON: Final = 20
#: §5.2: the bracket's width target, K.
BRACKET: Final = 0.05
GOLDEN: Final = (math.sqrt(5.0) - 1.0) / 2.0


def reactor_of(binding: RevisionBinding) -> C1Reactor:
    (reactor,) = (unit for unit in binding.flowsheet.instances if isinstance(unit, C1Reactor))
    return reactor


def _inlet_stream(binding: RevisionBinding) -> str:
    reactor = reactor_of(binding)
    (stream,) = binding.flowsheet.wiring[reactor.unit_id].streams["inlet"]
    return stream


def with_inlet_temperature(document: Mapping[str, Any], temperature: float) -> dict[str, Any]:
    """The revision with its reactor-inlet temperature specification at `temperature` (the
    specification on the reactor's inlet connection, `state.T`)."""
    edited = copy.deepcopy(dict(document))
    binding = bind_revision_flowsheet(document)
    assert isinstance(binding, RevisionBinding), binding
    stream = _inlet_stream(binding)
    (specification,) = (
        item
        for item in edited["specifications"]
        if item["target"].get("object_id") == stream and item["target"]["path"] == "state.T"
    )
    specification["value"] = float(temperature)
    return edited


def inner(binding: RevisionBinding, w: tuple[float, float]) -> dict[str, float]:
    """The inner EO solve at pinned w (M02's accessor), converged, as the state by column id."""
    pinned = with_coupling(binding, reactor_of(binding).unit_id, w[0], w[1])
    plan, _ = plan_revision(pinned, POLICY)
    run = execute_plan(plan=plan, flowsheet=pinned.flowsheet, spec=pinned.spec, policy=POLICY)
    if run.outcome != "CONVERGED" or run.state is None:
        raise RuntimeError(f"inner solve at w = {w!r}: {run.outcome} ({run.message})")
    return dict(run.state)


def inlet_of(binding: RevisionBinding, state: Mapping[str, float]) -> tuple[float, ...]:
    stream = _inlet_stream(binding)
    return (
        *(state[f"{stream}.n.{name}"] for name in COMPONENTS),
        state[f"{stream}.T"],
        state[f"{stream}.P"],
    )


def residual(binding: RevisionBinding, w: tuple[float, float]) -> tuple[tuple[float, float], Any]:
    """F(w) = w − (X_E, ΔT_E) at the inner solution, scaled by (0.1, 10 K), and the state."""
    state = inner(binding, w)
    truth = synthetic.interior(
        synthetic.process_z(inlet_of(binding, state), reactor_of(binding).n_tubes)
    )
    return ((w[0] - truth[0]) / SCALES[0], (w[1] - truth[1]) / SCALES[1]), state


@dataclass(frozen=True)
class Point:
    """One reference evaluation: T_in, the coupled w, ‖F‖ at it, J and the Newton count."""

    temperature: float
    w: tuple[float, float]
    residual: float
    objective: float
    newton_iterations: int
    state: Mapping[str, float]


def coupled(document: Mapping[str, Any], temperature: float) -> Point:
    """The loop at fixed T_in, coupled to the synthetic truth by Newton (module docstring)."""
    binding = bind_revision_flowsheet(with_inlet_temperature(document, temperature))
    assert isinstance(binding, RevisionBinding), binding
    reactor = reactor_of(binding)
    w = (float(reactor.conversion), float(reactor.temperature_rise))
    for iteration in range(MAX_NEWTON + 1):
        f, state = residual(binding, w)
        norm = max(abs(f[0]), abs(f[1]))
        if norm <= TOLERANCE:
            liquid = _liquid_stream(binding)
            return Point(temperature, w, norm, state[f"{liquid}.n.NH3"], iteration, state)
        if iteration == MAX_NEWTON:
            break
        columns = []
        for k in range(2):
            moved = list(w)
            moved[k] = w[k] + STEP * SCALES[k]
            h = (moved[k] - w[k]) / SCALES[k]
            g, _ = residual(binding, (moved[0], moved[1]))
            columns.append(((g[0] - f[0]) / h, (g[1] - f[1]) / h))
        (a, c), (b, d) = columns  # J = [[a, b], [c, d]] in scaled units
        det = a * d - b * c
        dx = (-f[0] * d + b * f[1]) / det
        dy = (-a * f[1] + c * f[0]) / det
        w = (w[0] + dx * SCALES[0], w[1] + dy * SCALES[1])
    raise RuntimeError(f"Newton at T_in = {temperature!r}: ‖F‖ = {norm!r} after {MAX_NEWTON}")


def _liquid_stream(binding: RevisionBinding) -> str:
    from openflowsheet.models.c1.flash import TPFlash

    (flash,) = (unit for unit in binding.flowsheet.instances if isinstance(unit, TPFlash))
    (stream,) = binding.flowsheet.wiring[flash.unit_id].streams["liquid"]
    return stream


@dataclass(frozen=True)
class Reference:
    """T_ref: the best evaluated point of the golden-section search, its bracket and every point."""

    best: Point
    bracket: tuple[float, float]
    points: tuple[Point, ...]


def golden_section(document: Mapping[str, Any], box: tuple[float, float] = BOX) -> Reference:
    """Maximize J over T_in in `box` until the bracket is ≤ 0.05 K (module docstring)."""
    low, high = box
    points: list[Point] = []

    def at(temperature: float) -> Point:
        point = coupled(document, temperature)
        points.append(point)
        return point

    left = at(high - GOLDEN * (high - low))
    right = at(low + GOLDEN * (high - low))
    while high - low > BRACKET:
        if left.objective >= right.objective:
            high = right.temperature
            right = left
            left = at(high - GOLDEN * (high - low))
        else:
            low = left.temperature
            left = right
            right = at(low + GOLDEN * (high - low))
    best = max(points, key=lambda point: point.objective)
    return Reference(best, (low, high), tuple(points))
