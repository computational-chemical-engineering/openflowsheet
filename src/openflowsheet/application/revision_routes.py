"""The revision routes OPT's revision NLP host runs (OPT review M2): `studies.nlp.host.
RevisionRoutes` implemented by `revision_run`'s binder, solve, bundle writer and bundle replay.

`studies` never imports `application` (M04's rule), so the revision host, the decision map, the
static readiness and the replay take these operations as `routes`; the application hands them
`REVISION_ROUTES` where it runs them (the job runner, the CLI, validation's static readiness).
Each method is the named `revision_run`/`binding` function, called as the studies modules called
it before the inversion.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from openflowsheet.application.binding import Unbound, refusal_code
from openflowsheet.application.policies import DEFAULT_POLICY_ID, SolvePath
from openflowsheet.application.revision_binding import SurrogateResolver
from openflowsheet.application.revision_run import (
    NoRoute,
    Reproduction,
    Route,
    RouteRun,
    RunUnsupportedError,
    bind_route,
    reproduce_bundle,
    select_route,
    solve_route,
    write_revision_bundle,
)
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.orchestrator.warm_start import WarmStartCandidate
from openflowsheet.verify.certificate import CheckPolicy

__all__ = ["REVISION_ROUTES", "ApplicationRevisionRoutes"]


class ApplicationRevisionRoutes:
    """`studies.nlp.host.RevisionRoutes` on `revision_run` (module docstring)."""

    default_policy_id: Final[str] = DEFAULT_POLICY_ID
    unsupported: Final[type[RunUnsupportedError]] = RunUnsupportedError

    def bind(
        self,
        solve_path: SolvePath,
        document: Mapping[str, Any],
        *,
        surrogates: SurrogateResolver | None = None,
    ) -> Route | Unbound:
        return bind_route(solve_path, document, surrogates=surrogates)

    def select(
        self, document: Mapping[str, Any], *, surrogates: SurrogateResolver | None = None
    ) -> Route | NoRoute:
        return select_route(document, surrogates=surrogates)

    def is_route(self, bound: Any) -> bool:
        return isinstance(bound, Route)

    def refusal_code(self, detail: str) -> str:
        return refusal_code(detail)

    def solve(
        self,
        route: Route,
        document: Mapping[str, Any],
        *,
        policy: SolvePolicy,
        check_policy: CheckPolicy,
        warm_start: WarmStartCandidate | None = None,
    ) -> RouteRun:
        return solve_route(
            route, document, policy=policy, check_policy=check_policy, warm_start=warm_start
        )

    def write_bundle(
        self,
        run: RouteRun,
        document: Mapping[str, Any],
        directory: Path,
        *,
        run_id: str,
        policy: SolvePolicy,
        check_policy: CheckPolicy,
        policy_requested: str,
        started: str,
        clock: float,
    ) -> None:
        write_revision_bundle(
            run,
            document,
            directory,
            run_id=run_id,
            policy=policy,
            check_policy=check_policy,
            policy_requested=policy_requested,
            started=started,
            clock=clock,
        )

    def reproduce(
        self, directory: Path, *, rerun: bool, rerun_directory: Path, run_id: str
    ) -> Reproduction:
        return reproduce_bundle(
            directory, rerun=rerun, rerun_directory=rerun_directory, run_id=run_id
        )


#: The routes the application hands `studies.nlp` (the job runner, the CLI, validation).
REVISION_ROUTES: Final = ApplicationRevisionRoutes()
