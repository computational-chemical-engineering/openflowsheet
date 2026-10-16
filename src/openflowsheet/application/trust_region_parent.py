"""The application operations the C1 parent adapter runs (M05 build decision S44; design note
§7.4, §6.4).

`studies.trust_region.parent.C1Parent` binds, routes and solves C1 revisions, which are this
layer's operations; `studies` never imports `application` (M04's rule, R-237's for `adapters`),
so the adapter receives them injected, as M04's binder receives its surrogate resolver
(`bind_revision_flowsheet(..., surrogates=)`, M04 build log E5/E8). `C1ParentServices` is the one
implementation of the adapter's `ParentServices` protocol; each method is the call the adapter
made directly before S44, unchanged:

- `bind`: `revision_binding.bind_revision_flowsheet`, a refusal raised as `ValueError`;
- `coupled_route`: `revision_run.select_route`'s route when it is `revision_coupled`, else
  `None` (the adapter's `unsupported(not_revision_coupled)`);
- `solve_coupled`: `revision_run.solve_route`; a `RunUnsupportedError` comes back as its `code`
  (the adapter's `unsupported(<code>)`). A `VerifierError` propagates: the adapter turns it into
  its outcome;
- `live_experiments`, `inlet_of`, `unit_variant`: `coupled_run`'s;
- `pinned_at`: M02's coupling accessor `coupled_run.at_coupling` at w = (X̂, ΔT̂);
- `policy`: the default solve policy `policies.T06_REVISION_V2`.

Imports nothing of `studies.trust_region` (R-003: no route reaches the projection).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from openflowsheet.adapters.experiments.runner import ExperimentRunner
from openflowsheet.adapters.variants import Variant
from openflowsheet.application.coupled_run import (
    LiveExperiments,
    at_coupling,
    inlet_of,
    unit_variant,
)
from openflowsheet.application.policies import T06_REVISION_V2
from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.application.revision_run import (
    Route,
    RouteRun,
    RunUnsupportedError,
    select_route,
    solve_route,
)
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.orchestrator.coupling import UnitInlet
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.verify.certificate import CheckPolicy

__all__ = ["C1_PARENT_SERVICES", "C1ParentServices", "pinned_at"]


def pinned_at(
    binding: RevisionBinding, unit_id: str, coupling: tuple[float, float]
) -> RevisionBinding:
    """`binding`'s inner problem with the embedded reactor `unit_id` pinned at w = (X̂, ΔT̂).

    The one call site of M02's coupling accessor in M05's library: `coupled_run.at_coupling`
    (R-309: it refuses a `unit_id` that is not a C1 reactor of the binding). The floats are
    passed as Python floats, bit for bit (WO-5c)."""
    return at_coupling(binding, {unit_id: (float(coupling[0]), float(coupling[1]))})


class C1ParentServices:
    """The C1 parent adapter's application operations (module docstring)."""

    policy: Final[SolvePolicy] = T06_REVISION_V2

    def bind(self, document: Mapping[str, Any]) -> RevisionBinding:
        binding = bind_revision_flowsheet(document)
        if not isinstance(binding, RevisionBinding):
            raise ValueError(f"the C1 revision does not bind: {binding!r}")
        return binding

    def coupled_route(self, document: Mapping[str, Any]) -> Route | None:
        route = select_route(document)
        if not isinstance(route, Route) or route.solve_path != "revision_coupled":
            return None
        return route

    def solve_coupled(
        self,
        route: Route,
        document: Mapping[str, Any],
        *,
        policy: SolvePolicy,
        check_policy: CheckPolicy,
        experiments: LiveExperiments,
    ) -> RouteRun | str:
        try:
            return solve_route(
                route,
                document,
                policy=policy,
                check_policy=check_policy,
                experiments=experiments,
            )
        except RunUnsupportedError as error:
            return error.code

    def live_experiments(self, runner: ExperimentRunner) -> LiveExperiments:
        return LiveExperiments(runner)

    def inlet_of(
        self, binding: RevisionBinding, unit: C1Reactor, state: Mapping[str, float]
    ) -> UnitInlet:
        return inlet_of(binding, unit, state)

    def unit_variant(self, unit: C1Reactor) -> Variant:
        return unit_variant(unit)

    def pinned_at(
        self, binding: RevisionBinding, unit_id: str, coupling: tuple[float, float]
    ) -> RevisionBinding:
        return pinned_at(binding, unit_id, coupling)


#: The services every C1 parent of this application runs on.
C1_PARENT_SERVICES: Final = C1ParentServices()
