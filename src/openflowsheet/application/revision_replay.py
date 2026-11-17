"""Reproduction of revision-built and registered-case bundles (T07 §12.3; ADR 0020 D4).

The tear path's registered cases (`registered_case`, `registered_flowsheet`, `rerun_registered`,
moved from the CLI) and `reproduce_bundle`, which reruns a bundle along **its recorded route** —
it never re-routes — after the archived policy documents recompute to the manifest's hashes, and
compares through `run.replay`. It sits directly above `revision_run` (ADR 0076 I-12c), whose
routes and `run_revision_session` it reruns.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from openflowsheet.application import revision_run
from openflowsheet.application.coupled_run import (
    COUPLING_NAME,
    CoupledStart,
    RecordedExperiments,
    ReplayDivergenceError,
    compact_differences,
    coupling_record_problem,
    final_constants,
    iterate_differences,
    record_differences,
    recorded_coupling_start,
)
from openflowsheet.application.revision_continuation import ContinuationSource, recorded_source
from openflowsheet.application.revision_run import (
    SOLVE_PATHS,
    Route,
    Stage,
    bind_route,
    no_stage,
)
from openflowsheet.canonical import document_sha256
from openflowsheet.numerics.solve_record import SolvePolicy
from openflowsheet.orchestrator.warm_start import WarmStartCandidate
from openflowsheet.resources import packaged
from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle
from openflowsheet.run.compare import KNOWN_POLICY_IDS
from openflowsheet.run.manifest import RunManifest, environment, policy_sha256
from openflowsheet.run.replay import ReplayReport, Rerun, decide_mode, replay
from openflowsheet.thermo.pr_c1 import PrC1Provider
from openflowsheet.verify.verdict import CheckPolicy

__all__ = [
    "Reproduction",
    "declared_kinds",
    "registered_case",
    "registered_flowsheet",
    "reproduce_bundle",
    "rerun_registered",
]


# -- the tear path's registered cases (moved from the CLI, §12.3) -----------------------------


def registered_case(case_id: str) -> dict[str, Any] | None:
    """A registered SYN-001 variant (`benchmarks/syn001/reference_values.yaml`), or `None`."""
    import yaml

    registry = packaged("benchmarks/syn001/reference_values.yaml")
    if registry.is_file():
        loaded = yaml.safe_load(registry.read_text(encoding="utf-8"))
        for entry in loaded["variants"]:
            if entry["case_id"] == case_id:
                return dict(entry)
    return None


def registered_flowsheet(case: Mapping[str, Any]) -> Any:
    """The tear path's `Syn001Flowsheet` of a registered variant, as the K06 CLI builds it."""
    from openflowsheet.compiled import EvaluationContext
    from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
    from openflowsheet.thermo.syn001 import Syn001Provider

    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(model_version="K06-cli@" + "0" * 64, constants_sha256="0" * 64),
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


def rerun_registered(case: Mapping[str, Any], directory: Path, *, run_id: str) -> Rerun:
    """`run_session` of a registered variant into `directory`, read back as a `Rerun`."""
    from openflowsheet.application.run_session import run_session

    fresh = run_session(registered_flowsheet(case), directory, run_id=run_id)
    return Rerun({name: read_artifact(directory, name) for name in fresh.artifacts})


def declared_kinds(*specs: Any) -> dict[str, str]:
    """ADR 0025 D5 (W4): each variable's declared quantity kind, unioned over the compiled
    problems a rerun solved (`ProblemSpec.variable_kinds`), for comparing its solution state.

    A route's plan steps all solve `route.binding.spec` (`solve_route` hands it to
    `execute_plan`), which is also the spec `solution-state.json` is written over, so a rerun
    passes that one spec. A variable given two kinds is a defect, never a choice: it raises."""
    kinds: dict[str, str] = {}
    for spec in specs:
        for name, kind in spec.variable_kinds.items():
            if kinds.setdefault(name, kind) != kind:
                raise ValueError(
                    f"variable {name!r} is declared both {kinds[name]!r} and {kind!r} "
                    "(ADR 0025 D5: a solution state is compared under one declared kind)"
                )
    return kinds


# -- reproduce (§12.3 "Rerun", R2.5) -----------------------------------------------------------


@dataclass(frozen=True)
class Reproduction:
    """`reproduce`'s result: the replay report, and the rerun's bundle when one was written."""

    report: ReplayReport
    rerun_manifest: RunManifest | None = None


def _inspected(directory: Path, reason: str | None = None) -> ReplayReport:
    """The archive inspected and not re-run: `inspected_archived_results` / `NOT_RUN`, with the
    environment's reasons and, when given, why no rerun happened (§12.3; Q26 (ii))."""
    report = replay(directory, None)
    reasons = report.reasons
    if reason is not None:
        reasons = (*(entry for entry in reasons if entry != "no rerun was supplied"), reason)
    return replace(report, mode="inspected_archived_results", verdict="NOT_RUN", reasons=reasons)


def _recorded_warm_start(recorded: Any) -> WarmStartCandidate | None:
    """ADR 0024 D5: the candidate a bundle's `solve-path.json` recorded, or `None` (absent, or no
    member: the policy did not name the source)."""
    member = recorded.get("warm_start") if isinstance(recorded, Mapping) else None
    return WarmStartCandidate.from_record(member) if isinstance(member, Mapping) else None


def _recorded_coupled_start(recorded: Any) -> CoupledStart | None:
    """ADR 0070 D9 (X02 design note §5.8): the outer start a bundle's `solve-path.json`
    recorded, or `None` (no `coupling` sub-record: none was declared). The rerun re-runs
    compatibility, bounds and opening, and must write the same record."""
    member = recorded.get("warm_start") if isinstance(recorded, Mapping) else None
    coupling = member.get("coupling") if isinstance(member, Mapping) else None
    if not isinstance(coupling, Mapping):
        return None
    assert isinstance(member, Mapping)
    return recorded_coupling_start(coupling, member.get("external"))


def _recorded_revision_continuation(
    recorded: Any, document: Mapping[str, Any]
) -> ContinuationSource | None:
    """ADR 0072 (RRC design note §5.9): the source a bundle's `solve-path.json` recorded, rebuilt
    without a lookup or a binding (`recorded_source`), or `None` when there is no member."""
    member = recorded.get("revision_continuation") if isinstance(recorded, Mapping) else None
    return recorded_source(member, document) if isinstance(member, Mapping) else None


def _reproduce_registered(
    directory: Path, manifest: RunManifest, rerun_directory: Path, run_id: str, at: Stage
) -> Reproduction:
    """`reproduce_bundle` on a bundle without `revision.json` (K05's SYN-001 shape): a rerun of
    its registered case, or `inspected_archived_results` when `run_id` names none."""
    case = registered_case(manifest.run_id)
    if case is None:
        at("compare")
        return Reproduction(_inspected(directory, "rerun_unsupported(no_revision_document)"))
    at("rerun")
    fresh = rerun_registered(case, Path(rerun_directory), run_id=run_id)
    at("compare")
    return Reproduction(replay(directory, fresh), read_manifest(Path(rerun_directory))[0])


def _recorded_policies(
    directory: Path, manifest: RunManifest
) -> tuple[SolvePolicy, CheckPolicy] | None:
    """`reproduce_bundle`'s policy documents of the bundle in `directory`, or `None` when they do
    not read or do not recompute to `manifest`'s hashes."""
    try:
        policy = SolvePolicy.from_document(read_artifact(directory, "solve-policy.json"))
        check = read_artifact(directory, "check-policy.json")
        check_policy = CheckPolicy(policy_id=check["policy_id"], tolerances=check["tolerances"])
        matches = (
            policy_sha256(policy) == manifest.policy_sha256
            and check_policy.sha256 == manifest.check_policy_sha256
        )
    except (ValueError, TypeError, KeyError):
        return None
    return (policy, check_policy) if matches else None


def _coupling_constants_guard(route: Route, record: Mapping[str, Any]) -> list[str]:
    """`reproduce_bundle`'s difference of a coupling record whose final constants digest does not
    recompute (§14.5 D8 item 2), or none."""
    found: list[str] = []
    # §14.5 D8 (R-308) item 2: the constants digest's R0 guard, by recomputation.
    constants = final_constants(route.binding, record)
    if constants is not None and constants[0] != constants[1]:
        final = record["iterations"][-1]
        found.append(
            f"coupling_constants: {constants[1]} rebuilt at the record's final w "
            f"{final['w']!r} (k = {final['k']}), against the recorded {constants[0]}"
        )
    return found


def reproduce_bundle(
    directory: Path,
    *,
    rerun: bool,
    rerun_directory: Path,
    run_id: str,
    stage: Stage | None = None,
) -> Reproduction:
    """§12.3's rerun rule, as amended by R2.5.

    Nothing is re-run when `rerun` is false, when the archive fails its integrity check, or when
    the environment already decides `inspected_archived_results` (ADR 0007 D4: the mode is
    decided before anything runs). A bundle with `revision.json` reruns its **recorded** route
    after its policy documents recompute to the manifest's hashes; one without is K05's SYN-001
    shape and reruns only when `run_id` is a registered case. There is no fallback to
    SYN-001-nominal (§12.3, D-Q6): comparing an unknown run with nominal's rerun would be a
    misleading `MISMATCH`. The CLI's `replay --rerun` is this function (T08 review 2, Ruling 11).

    `stage` (§6.4) is called with `integrity` on entry, `rerun` before a rerun, and `compare`
    before the report is built; a rerun's bundle is complete in `rerun_directory` by `compare`.

    The rungs that re-run nothing are `_rerunnable_manifest`, `_rerun_inputs` and
    `_valid_coupling_record`, in that order; each stages `compare` before its reproduction.
    """
    at = stage if stage is not None else no_stage
    directory = Path(directory)
    at("integrity")
    manifest = _rerunnable_manifest(directory, rerun, at)
    if isinstance(manifest, Reproduction):
        return manifest

    if "revision.json" not in manifest.artifacts:
        return _reproduce_registered(directory, manifest, rerun_directory, run_id, at)

    rerun_inputs = _rerun_inputs(directory, manifest, at)
    if isinstance(rerun_inputs, Reproduction):
        return rerun_inputs
    recorded, (policy, check_policy), document, route = rerun_inputs
    coupling = _valid_coupling_record(directory, manifest, route, at)
    if isinstance(coupling, Reproduction):
        return coupling
    coupling_found: list[str] = []
    classified_bitwise = True
    if coupling is not None:
        coupling_found += _coupling_constants_guard(route, coupling)
    at("rerun")
    with tempfile.TemporaryDirectory(prefix="ofs-replay-") as scratch:
        experiments = _recorded_experiments(coupling, scratch, manifest)
        try:
            # Read from revision_run at call time, as before ADR 0076 I-12c moved this code.
            rerun_manifest = revision_run.run_revision_session(
                route,
                document,
                Path(rerun_directory),
                run_id=run_id,
                policy=policy,
                check_policy=check_policy,
                policy_requested=str(recorded.get("policy_requested")),
                # ADR 0024 D5: the recorded candidate, never a store lookup.
                warm_start=_recorded_warm_start(recorded),
                coupled_start=_recorded_coupled_start(recorded),
                experiments=experiments,
                # ADR 0072 (§5.9): the recorded source, never a store lookup.
                revision_continuation=_recorded_revision_continuation(recorded, document),
            )
        except ReplayDivergenceError as error:
            at("compare")
            report = _diverged(directory, error.difference)
            return Reproduction(_with_differences(report, coupling_found))
    artifacts = {
        name: read_artifact(Path(rerun_directory), name) for name in rerun_manifest.artifacts
    }
    if coupling is not None:
        artifacts, classified_bitwise = _shape_coupled_artifacts(
            directory, manifest, artifacts, coupling, coupling_found
        )
    at("compare")
    # On `revision_coupled` the state is written over the final inner spec, whose columns and
    # kinds are the route's binding's (w moves constants only).
    rerun_result = Rerun(artifacts, variable_kinds=declared_kinds(route.binding.spec))
    report = replay(directory, rerun_result)
    if not classified_bitwise and report.bitwise_floats:
        report = replace(report, bitwise_floats=False)
    if experiments is not None and coupling is not None:
        report = _replayed_from_record(report, experiments, coupling)
    return Reproduction(_with_differences(report, coupling_found), rerun_manifest)


def _rerunnable_manifest(directory: Path, rerun: bool, at: Stage) -> RunManifest | Reproduction:
    """`reproduce_bundle`'s first rungs: the manifest of a bundle that may be re-run, or, after
    `compare` is staged, the archive's reproduction when `rerun` is false, when the archive fails
    its integrity check, when the environment already decides `inspected_archived_results`
    (ADR 0007 D4) or when the manifest's numerical policy is not one this build knows."""
    if not rerun:
        at("compare")
        return Reproduction(_inspected(directory))
    if not verify_bundle(directory).ok:
        at("compare")
        return Reproduction(replay(directory, None))
    manifest, _ = read_manifest(directory)
    if decide_mode(manifest.environment, environment())[0] == "inspected_archived_results":
        at("compare")
        return Reproduction(_inspected(directory))
    if manifest.numerical_policy_id not in KNOWN_POLICY_IDS:
        # ADR 0025 (Q4): a record under a policy this build does not know is not re-run;
        # `replay` names the policy as the reason.
        at("compare")
        return Reproduction(replay(directory, None))
    return manifest


def _rerun_inputs(
    directory: Path, manifest: RunManifest, at: Stage
) -> tuple[Any, tuple[SolvePolicy, CheckPolicy], Any, Route] | Reproduction:
    """R2.5's rerun inputs of a bundle with `revision.json`: the `solve-path.json` record, the
    policy documents (`_recorded_policies`), the revision document and the recorded route bound
    to it.
    Or, after `compare` is staged, the archive inspected with the reason no rerun happens: no
    `solve-path.json`, policy documents that do not recompute to the manifest's hashes, or a
    recorded solve path that does not bind."""
    if "solve-path.json" not in manifest.artifacts:
        at("compare")
        return Reproduction(_inspected(directory, "rerun_unsupported(no_solve_path)"))
    recorded = read_artifact(directory, "solve-path.json")
    policies = _recorded_policies(directory, manifest)
    if policies is None:
        at("compare")
        return Reproduction(_inspected(directory, "policy_document_mismatch"))

    solve_path = recorded.get("solve_path") if isinstance(recorded, Mapping) else None
    document = read_artifact(directory, "revision.json")
    route = bind_route(solve_path, document) if solve_path in SOLVE_PATHS else None
    if not isinstance(route, Route):
        at("compare")
        return Reproduction(
            _inspected(directory, f"rerun_unsupported(route_unbound({solve_path}))")
        )
    return recorded, policies, document, route


def _valid_coupling_record(
    directory: Path, manifest: RunManifest, route: Route, at: Stage
) -> Mapping[str, Any] | None | Reproduction:
    """The bundle's external coupling record on `revision_coupled` (`None` on any other route).
    Or, after `compare` is staged, the archive inspected with the reason no rerun happens: no
    record, or one that fails its check."""
    if route.solve_path != "revision_coupled":
        return None
    # M02 design note §7.2 step 1: the record against its schema, and each embedded request's
    # key against its content.
    if COUPLING_NAME not in manifest.artifacts:
        at("compare")
        return Reproduction(_inspected(directory, "rerun_unsupported(no_external_coupling)"))
    record: Mapping[str, Any] = read_artifact(directory, COUPLING_NAME)
    problem = coupling_record_problem(record)
    if problem is not None:
        at("compare")
        return Reproduction(
            _inspected(directory, f"rerun_unsupported(external_coupling_invalid({problem}))")
        )
    return record


def _shape_coupled_artifacts(
    directory: Path,
    manifest: RunManifest,
    artifacts: dict[str, Any],
    coupling: Mapping[str, Any],
    found: list[str],
) -> tuple[dict[str, Any], bool]:
    """`reproduce_bundle`'s rerun `artifacts` of a `revision_coupled` bundle, shaped against the
    archive in `directory` and its recorded `coupling`; the differences found are added to
    `found`, and the flag is false when a float was taken from the record."""
    classified_bitwise = True
    # R-341's R0 guard digests the rerun record as written, before any digest in it is
    # replaced for shape.
    fresh_record_sha256 = (
        document_sha256(artifacts[COUPLING_NAME]) if COUPLING_NAME in artifacts else None
    )
    # §14.5 D8 (R-308) items 1 and 3: the inner solves' constants digests for shape, in the
    # record and in every artifact that carries the final one (build log D94; item 2 guards
    # it; the manifest is not compared), and the iterates under the archive's policy.
    artifacts = {
        name: _constants_for_shape(document, read_artifact(directory, name))
        if name in manifest.artifacts
        else document
        for name, document in artifacts.items()
    }
    if COUPLING_NAME in artifacts:
        fresh_record = artifacts[COUPLING_NAME]
        found += iterate_differences(fresh_record, coupling, manifest.numerical_policy_id)
        # R-317 (b): the record's floats at their registered floors; `replay` compares the
        # rest. A float taken from the record is not a bitwise match.
        shaped, floored = record_differences(fresh_record, coupling, manifest.numerical_policy_id)
        found += floored
        artifacts[COUPLING_NAME] = shaped
        classified_bitwise = shaped == fresh_record
    # Build log D130 (D124): a failure bundle's compact copy of the record by the same rules,
    # its `record_sha256` for shape, each side's guarded by its own record's digest (R-341).
    failure = artifacts.get(FAILURE_NAME)
    if FAILURE_NAME in manifest.artifacts and isinstance(failure, dict):
        archived = read_artifact(directory, FAILURE_NAME)
        fresh_copy = failure.get("observations", {}).get("external_coupling")
        archived_copy = archived.get("observations", {}).get("external_coupling")
        if isinstance(fresh_copy, dict) and isinstance(archived_copy, dict):
            shaped_copy, floored = compact_differences(
                fresh_copy,
                archived_copy,
                coupling["coupling_block"],
                manifest.numerical_policy_id,
                fresh_record_sha256=fresh_record_sha256,
                recorded_record_sha256=document_sha256(coupling),
            )
            found += floored
            classified_bitwise = classified_bitwise and shaped_copy == fresh_copy
            observations = {**failure["observations"], "external_coupling": shaped_copy}
            artifacts[FAILURE_NAME] = {**failure, "observations": observations}
    return artifacts, classified_bitwise


_HEX64: Final = re.compile(r"[0-9a-f]{64}")
FAILURE_NAME: Final = "failure-bundle.json"


def _constants_for_shape(fresh: Any, archived: Any) -> Any:
    """§14.5 D8 (R-308) item 1. On `revision_coupled` every `constants_sha256` digests an inner
    solve's X̂ and ΔT̂, which Broyden computes in floating point: by ADR 0007's criterion a digest
    of an R1/R2 quantity, compared for shape, never for value. `fresh` with each well-formed
    `constants_sha256` that the archive also has, well-formed, at the same place replaced by the
    archive's; anything else is left for `replay` to compare, so a malformed digest is a
    difference. The final digest's R0 guard is `final_constants`'s recomputation."""
    if isinstance(fresh, dict) and isinstance(archived, dict):
        shaped: dict[str, Any] = {}
        for key, value in fresh.items():
            theirs = archived.get(key)
            if (
                key == "constants_sha256"
                and isinstance(value, str)
                and isinstance(theirs, str)
                and _HEX64.fullmatch(value)
                and _HEX64.fullmatch(theirs)
            ):
                shaped[key] = theirs
            else:
                shaped[key] = _constants_for_shape(value, theirs) if key in archived else value
        return shaped
    if isinstance(fresh, list) and isinstance(archived, list):
        return [
            _constants_for_shape(value, archived[index]) if index < len(archived) else value
            for index, value in enumerate(fresh)
        ]
    return fresh


def _recorded_experiments(
    coupling: Mapping[str, Any] | None, scratch: str, manifest: RunManifest
) -> RecordedExperiments | None:
    """`reproduce_bundle`'s replay backend of a recorded coupling (M02 design note §7.2), in the
    `scratch` directory; `None` without a coupling."""
    return (
        None
        if coupling is None
        else RecordedExperiments(
            coupling,
            provider=PrC1Provider(),
            scratch=Path(scratch),
            policy_id=manifest.numerical_policy_id,
        )
    )


def _with_differences(report: ReplayReport, found: list[str]) -> ReplayReport:
    """`report` with the coupled route's own differences (§14.5 D8) added: any one is a
    `MISMATCH`."""
    if not found:
        return report
    return replace(report, differences=(*report.differences, *found), verdict="MISMATCH")


def _diverged(directory: Path, difference: str) -> ReplayReport:
    """§7.2: a recomputed external request that is not the record's — `MISMATCH`, naming it."""
    report = replay(directory, None)
    reasons = tuple(entry for entry in report.reasons if entry != "no rerun was supplied")
    return replace(report, verdict="MISMATCH", reasons=reasons, differences=(difference,))


def _replayed_from_record(
    report: ReplayReport, experiments: RecordedExperiments, coupling: Mapping[str, Any]
) -> ReplayReport:
    """§7.2 step 4: `reasons` gains how the external results were obtained, `recorded_environment`
    the frozen fingerprints, and an in-process re-evaluation that differs from the record is a
    difference (`external_result(<k>, <unit>)…`)."""
    reasons = (
        *report.reasons,
        f"external_results_replayed_from_record({experiments.replayed})",
        *(
            (f"external_results_reevaluated({experiments.reevaluated})",)
            if experiments.reevaluated
            else ()
        ),
    )
    environment = {**report.recorded_environment, "external_fingerprints": coupling["frozen"]}
    found = (*report.differences, *experiments.differences)
    verdict = report.verdict if not experiments.differences else "MISMATCH"
    return replace(
        report,
        reasons=reasons,
        recorded_environment=environment,
        differences=found,
        verdict=verdict,
    )
