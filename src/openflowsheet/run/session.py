"""One run, start to finish: solve, verify, bundle. K05.

This is the application layer's shape and K06 owns that layer, so this is written to be
*replaced* by a CLI and a transaction boundary rather than grown. What it must not be is what
it was — a function in a package `__init__` with `object`-typed parameters and four
`type: ignore`s, reaching into K03 and K04 from the top of the namespace (S6 of the Fable
review of K05).

The artifacts are the documents a third party needs to judge the run without trusting it: the
plan, the trace, and the certificate **or** the failure bundle. Never both, and never neither.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Final

from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
from openflowsheet.orchestrator.trace import SolvePolicy
from openflowsheet.run.bundle import write_bundle
from openflowsheet.run.identity import r0_projection, r0_sha256
from openflowsheet.run.manifest import RunManifest, environment, policy_sha256, started_now
from openflowsheet.verify.certificate import CheckPolicy, verify
from openflowsheet.verify.failure import bundle_for


def run_session(
    flowsheet: Syn001Flowsheet,
    directory: Path,
    *,
    run_id: str = "run-1",
    policy: SolvePolicy | None = None,
    check_policy: CheckPolicy | None = None,
    initial_recycle: Any = None,
    reproducibility_class: str | None = None,
) -> RunManifest:
    """Solve, verify and write the bundle. Returns the manifest with its index filled in.

    SYN-001's only (T05 §2.3; design Q-G): a revision-built flowsheet has no session, bundle or CLI
    in T05, and is refused with a `TypeError` before anything runs.
    """
    if not isinstance(flowsheet, Syn001Flowsheet):
        raise TypeError("syn001_only(run_session)")
    resolved_policy = policy or SolvePolicy(
        policy_id="SYN-001-K03", residual_tolerances={}, scales={}
    )
    resolved_check_policy = check_policy or CheckPolicy()

    started = started_now()
    clock = time.monotonic()
    result, trace = solve_tear(flowsheet, policy=resolved_policy, initial_recycle=initial_recycle)

    artifacts: dict[str, Any] = {
        "solve-events.json": [event.as_document() for event in trace.events],
        # T01 Q4: every solve carries its structural report. It is integers, ids and booleans, so
        # it costs almost nothing, and A22 needs it inside the artifact set that gate G05 compares
        # between the two CI architectures on every push.
        "structural-report.json": _structural_report(flowsheet),
    }
    if result.plan is not None:
        artifacts["solve-plan.json"] = result.plan.as_document()

    certificate = None
    if result.outcome == "CONVERGED":
        certificate = verify(flowsheet, result, policy=resolved_check_policy)
        artifacts["solution-certificate.json"] = certificate.as_document()
    else:
        artifacts["failure-bundle.json"] = bundle_for(result, trace).as_document()

    # S6: read the model identity from the compiled problem, not from the plan. A solve that
    # failed before a plan existed recorded `""` for both, so two different models that both
    # failed at planning shared a structural identity — while §8.2 requires a failure bundle to
    # carry its replay identity.
    metadata = Syn001TearProblem(flowsheet).compiled.metadata

    manifest = RunManifest(
        run_id=run_id,
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        policy_id=resolved_policy.policy_id,
        plan_id=result.plan.plan_id if result.plan else "",
        check_policy_sha256=resolved_check_policy.sha256,
        policy_sha256=policy_sha256(resolved_policy),
        artifact_r0_sha256=r0_sha256(r0_projection(artifacts)),
        numerical_policy_id=_numerical_policy_id(),
        environment=environment(),
        artifacts={},
        outcome=result.outcome,
        verification_status=certificate.verification_status if certificate else None,
        reproducibility_class=reproducibility_class or _reproducibility_class(flowsheet),
        started_at=started,
        elapsed_seconds=time.monotonic() - clock,
    )
    return write_bundle(Path(directory), manifest, artifacts)


def _structural_report(flowsheet: Syn001Flowsheet) -> dict[str, Any]:
    """T01's analysis of this flowsheet's declaration. Evaluates nothing (T01 A03)."""
    from openflowsheet.application.binding import structural_inputs
    from openflowsheet.graph.analysis import analyse

    spec, graph, row_units = structural_inputs(flowsheet)
    metadata = Syn001TearProblem(flowsheet).compiled.metadata
    report = analyse(
        spec,
        graph,
        model_version=metadata.model_version,
        constants_sha256=metadata.constants_sha256,
        row_units=row_units,
    )
    return report.as_document()


def _numerical_policy_id() -> str:
    """From the registry, never a literal (M4): the policy this build records (ADR 0025 D1.2)."""
    from openflowsheet.run.compare import CURRENT_POLICY_ID

    return CURRENT_POLICY_ID


#: §14.5 D7 (R-307): the ids of the property providers that evaluate outside this process. A run
#: is R3 iff its provider is one of them. Empty today; a provider that evaluates out of process is
#: added here in the commit that ships it.
EXTERNAL_PROVIDERS: Final[frozenset[str]] = frozenset()


def _reproducibility_class(flowsheet: Any) -> str:
    """R3 iff the run's provider is registered in `EXTERNAL_PROVIDERS`; R1 otherwise. Computed,
    never claimed.

    Reads only `flowsheet.provider`, so a revision-built flowsheet's run (T07 §12.3,
    `application.revision_run`) computes its class by this same rule; the coupled route adds
    §7.2's variant rule on top (`coupled_run.reproducibility_class`).

    The class comes from that registered set, never from provenance text (§14.5 D7, R-307): the
    former test, "external" in `data_provenance`, matched `pr-c1-v1`, whose provenance names a
    file `external-crosscheck.json` while the provider is in process (M02 build log D55).

    It was the dataclass default on every manifest — true today, because nothing here uses an
    external provider, and a field that is a claim rather than a measurement is exactly the
    shape of thing that stays true until it silently is not (S6).
    """
    provider_id = flowsheet.provider.describe().provider_id
    return "R3" if provider_id in EXTERNAL_PROVIDERS else "R1"


def solve_and_bundle(flowsheet: Syn001Flowsheet, directory: Path, **kwargs: Any) -> RunManifest:
    """The former name, kept so existing callers do not break. Prefer `run_session`."""
    return run_session(flowsheet, directory, **kwargs)
