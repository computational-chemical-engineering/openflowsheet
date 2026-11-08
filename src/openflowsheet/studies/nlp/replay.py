"""Replay of an optimisation record (OPT design §4.9, ADR 0071): re-check the certified chain, not
the search.

`reproduce` and the CLI's `replay` dispatch here when a directory's `optimization-manifest.json`
names `format == openflowsheet-optimization-v1` (`revision.OPTIMIZATION_FORMAT`); the run-bundle
path is untouched. The steps:

1. **Integrity** of every member against the manifest (missing, tampered, unexpected) and of the
   manifest's identity: `optimization_sha256` recomputed from its five inputs, the request's and
   the revision copy's digests equal to the identity's. A record that fails is not re-run.
2. With `rerun`: `reproduce_bundle` on every `starts/<k>/start` and `starts/<k>/resolve` bundle.
3. With `rerun`: the start phase again on the recorded revision and request under the recorded
   policies (the start bundle's policy documents, their digests the identity's), then V1–V7 at
   the recorded decisions against the recorded optimizer state (`verify_candidate`, as the start
   ran it: the start's held system, phase rows and closure; so §9 A-1's boundary clauses and B and
   A-2's V4 clause are recomputed with it), compared with `verification.json` under the
   registered comparison policy (`run.compare.differences`, ADR 0007 D2's float rules).
4. The report's classification recomputed by `classify_starts` from the recorded Ipopt statuses
   and the recomputed V outcomes, compared with the report's `status`, `reasons` and each start's
   `classification`.

An active-set flip (a member of `verification.json`'s `active_set` in one document and not the
other) whose slack lies within `NEAR_ACTIVE_RELATIVE` of `TAU_ACTIVE` is the verdict changing near
its threshold (§4.9, F8 D8's rule, as ADR 0007 D2.4 for a certificate): the flip and what follows
from the active set alone (`active_set`, `kkt`, V3's `active_set`, V5, and the start's
classification with the report's status and reasons when only such starts moved) are listed under
`verdict_changed_near_threshold`, not as differences. Any other difference stays a difference.

One `ReplayReport` (schema unchanged): `integrity` over all members, `differences` prefixed
`starts/<k>/<member>: `, verdict `MATCH` iff every part matches. Without `rerun`:
`inspected_archived_results`. No Ipopt and no `nlp` extra are needed: nothing here imports Pyomo
or cyipopt.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

import numpy as np

from openflowsheet.canonical import document_sha256
from openflowsheet.run.bundle import MANIFEST_NAME, BundleIntegrity, read_artifact, read_manifest
from openflowsheet.run.compare import CURRENT_POLICY_ID, differences
from openflowsheet.run.manifest import environment
from openflowsheet.run.replay import ReplayMode, ReplayReport, ReplayVerdict

FORMAT: Final = "openflowsheet-optimization-v1"
MANIFEST: Final = "optimization-manifest.json"
#: The identity members of the manifest (`revision.optimization_sha256`'s inputs).
IDENTITY: Final = (
    "request_sha256",
    "revision_sha256",
    "route",
    "solve_policy_sha256",
    "check_policy_sha256",
)
BUNDLES: Final = ("start", "resolve")
#: §4.9: an active-set flip whose slack lies within this relative distance of `TAU_ACTIVE` is a
#: verdict changed near its threshold, not a defect.
NEAR_ACTIVE_RELATIVE: Final = 1e-9


def is_optimization_record(directory: Path) -> bool:
    """Whether `directory` holds an optimisation record (its manifest names the format)."""
    path = Path(directory) / MANIFEST
    if not path.is_file():
        return False
    try:
        manifest = json.loads(path.read_bytes())
    except (ValueError, UnicodeDecodeError):
        return False
    return isinstance(manifest, Mapping) and manifest.get("format") == FORMAT


def _read(directory: Path, relative: str) -> Any:
    return json.loads((directory / relative).read_bytes())


def record_integrity(directory: Path) -> BundleIntegrity:
    """Step 1: every member against the manifest, and the manifest's identity."""
    from openflowsheet.studies.nlp.request import OptimizationRequest
    from openflowsheet.studies.nlp.revision import REQUEST, REVISION, optimization_sha256

    directory = Path(directory)
    manifest = _read(directory, MANIFEST)
    members: Mapping[str, str] = manifest.get("members", {})
    missing, tampered = [], []
    for relative, sha in sorted(members.items()):
        path = directory / relative
        if not path.is_file():
            missing.append(relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            tampered.append(relative)
    present = {
        path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()
    }
    unexpected = sorted(present - set(members) - {MANIFEST})
    identity = {name: manifest.get(name) for name in IDENTITY}
    try:
        ok_identity = optimization_sha256(**identity) == manifest.get("optimization_sha256")
    except (TypeError, ValueError):
        ok_identity = False
    if not ok_identity:
        tampered.append(f"{MANIFEST}#/optimization_sha256")
    if REQUEST not in missing and REQUEST not in tampered and REQUEST in members:
        try:
            request_sha = OptimizationRequest.of(_read(directory, REQUEST)).sha256
        except (ValueError, TypeError, KeyError):
            request_sha = None
        if request_sha != identity["request_sha256"]:
            tampered.append(f"{MANIFEST}#/request_sha256")
    if REVISION not in missing and REVISION not in tampered and REVISION in members:
        if document_sha256(_read(directory, REVISION)) != identity["revision_sha256"]:
            tampered.append(f"{MANIFEST}#/revision_sha256")
    ok = not (missing or tampered or unexpected)
    return BundleIntegrity(ok, tuple(missing), tuple(tampered), tuple(unexpected))


def _starts(directory: Path) -> list[int]:
    return sorted(int(path.name) for path in (directory / "starts").glob("*") if path.is_dir())


def replay_optimization(
    directory: Path,
    *,
    rerun: bool,
    rerun_directory: Path,
    stage: Callable[[str], None] | None = None,
) -> ReplayReport:
    """§4.9 on the record at `directory` (see the module docstring). A rerun's bundles are
    written under `rerun_directory`, at `starts/<k>/<start|resolve>`.

    `stage` is called as `reproduce_bundle` calls it (T07 §6.4): `integrity` on entry, `rerun`
    before the bundles are re-run, `compare` before the report is built; a job's `reproduce`
    passes its stage boundary (OPT design §4.9)."""
    from openflowsheet.application.revision_run import reproduce_bundle

    at = stage if stage is not None else (lambda _: None)
    directory = Path(directory)
    at("integrity")
    integrity = record_integrity(directory)
    manifest = _read(directory, MANIFEST)
    recorded_environment = dict(manifest.get("environment") or {})
    current_environment = {"run": environment().as_document()}
    if not integrity.ok or not rerun:
        reason = (
            "integrity check failed; the record is not re-run"
            if not integrity.ok
            else "rerun not requested: the record was only inspected"
        )
        at("compare")
        return ReplayReport(
            mode="inspected_archived_results",
            verdict="NOT_RUN",
            integrity=integrity,
            recorded_environment=recorded_environment,
            current_environment=current_environment,
            reasons=(reason,),
        )
    found: list[str] = []
    reasons: list[str] = []
    modes: list[str] = []
    near: list[str] = []
    at("rerun")
    for index in _starts(directory):
        for name in BUNDLES:
            bundle = directory / "starts" / str(index) / name
            if not (bundle / MANIFEST_NAME).is_file():
                continue
            prefix = f"starts/{index}/{name}: "
            run_id = read_manifest(bundle)[0].run_id
            report = reproduce_bundle(
                bundle,
                rerun=True,
                rerun_directory=Path(rerun_directory) / "starts" / str(index) / name,
                run_id=run_id,
            ).report
            modes.append(report.mode)
            if report.verdict != "MATCH":
                found.append(f"{prefix}verdict {report.verdict}")
            found += [prefix + item for item in report.differences]
            reasons += [prefix + item for item in report.reasons]
            near += [prefix + item for item in report.verdict_changed_near_threshold]
    chain, chain_reasons, chain_near = _recomputed_chain(directory)
    found += chain
    reasons += chain_reasons
    near += chain_near
    at("compare")
    mode: ReplayMode
    verdict: ReplayVerdict
    if not modes or any(item == "inspected_archived_results" for item in modes):
        mode = "inspected_archived_results"
    elif all(item == "exact_replay" for item in modes):
        mode = "exact_replay"
    else:
        mode = "compatible_reproduction"
    if mode == "inspected_archived_results":
        verdict = "NOT_RUN"
    else:
        verdict = "MATCH" if not found else "MISMATCH"
    return ReplayReport(
        mode=mode,
        verdict=verdict,
        integrity=integrity,
        recorded_environment=recorded_environment,
        current_environment=current_environment,
        reasons=tuple(reasons),
        differences=tuple(found),
        verdict_changed_near_threshold=tuple(near),
    )


def _near_active(slack: Any) -> bool:
    from openflowsheet.studies.nlp.verification import TAU_ACTIVE

    if not isinstance(slack, int | float) or isinstance(slack, bool):
        return False
    return abs(abs(float(slack)) - TAU_ACTIVE) <= NEAR_ACTIVE_RELATIVE * TAU_ACTIVE


def active_set_flips(fresh: Mapping[str, Any], recorded: Mapping[str, Any]) -> tuple[str, ...]:
    """The members of `active_set` in exactly one of two verification documents, by name."""
    names = [{item["name"] for item in doc.get("active_set") or []} for doc in (fresh, recorded)]
    return tuple(sorted(names[0] ^ names[1]))


def _flip_is_near(name: str, holder: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    """A flipped member is near its threshold when its slack in the document that holds it lies
    within `NEAR_ACTIVE_RELATIVE` of `TAU_ACTIVE` and, where the other document records the same
    slack (a declared constraint's side under `slacks`), so does that one."""
    item = next(item for item in holder["active_set"] if item["name"] == name)
    if not _near_active(item.get("slack")):
        return False
    if item.get("kind") == "constraint":
        recorded = (other.get("slacks") or {}).get(item.get("target"), {})
        if item.get("side") in recorded and not _near_active(recorded[item["side"]]):
            return False
    return True


def verification_differences(
    fresh: Mapping[str, Any], recorded: Mapping[str, Any]
) -> tuple[list[str], list[str]]:
    """Step 3's comparison of one start's `verification.json`: `(differences, near)`.

    Every entry of `run.compare.differences` under the registered policy is a difference, except
    when the active set flipped and every flipped member is near `TAU_ACTIVE`
    (`_flip_is_near`): then the flip and the entries that depend on the active set alone
    (`active_set`, `kkt`, V3's `active_set`, every V5 entry) are `near`."""
    found = differences(dict(fresh), dict(recorded), policy_id=CURRENT_POLICY_ID)
    flips = active_set_flips(fresh, recorded)
    if not flips:
        return found, []
    for name in flips:
        in_fresh = any(item["name"] == name for item in fresh.get("active_set") or [])
        holder, other = (fresh, recorded) if in_fresh else (recorded, fresh)
        if not _flip_is_near(name, holder, other):
            return found, []
    checks = [item.get("check") for item in recorded.get("checks") or []]
    dependent = ["<root>.active_set", "<root>.kkt"]
    if "V3" in checks:
        dependent.append(f"<root>.checks[{checks.index('V3')}].active_set")
    if "V5" in checks:
        dependent.append(f"<root>.checks[{checks.index('V5')}].")
    near = [f"active set flip near tau_active: {', '.join(flips)}"]
    real: list[str] = []
    for entry in found:
        (near if entry.startswith(tuple(dependent)) else real).append(entry)
    return real, near


def classification_differences(
    recorded_report: Mapping[str, Any],
    status: str,
    reasons: list[Any],
    classifications: tuple[str, ...],
    near_starts: set[int],
) -> tuple[list[str], list[str]]:
    """Step 4's comparison: `(differences, near)`. A start whose classification moved is near
    when its verification document flipped near `TAU_ACTIVE` (`verification_differences`); the
    report's status and reasons are near when every start that moved is."""
    from openflowsheet.studies.nlp.revision import REPORT

    recorded_starts = recorded_report.get("starts") or []
    moved: list[int] = []
    per_start: list[tuple[int, str]] = []
    for index, classification in enumerate(classifications):
        recorded = (
            recorded_starts[index].get("classification") if index < len(recorded_starts) else None
        )
        if recorded != classification:
            moved.append(index)
            per_start.append(
                (index, f"starts/{index}: classification {recorded} recomputed {classification}")
            )
    report_level: list[str] = []
    if status != recorded_report.get("status"):
        report_level.append(f"{REPORT}: status {recorded_report.get('status')} recomputed {status}")
    if reasons != recorded_report.get("reasons"):
        report_level.append(f"{REPORT}: reasons differ when recomputed")
    forgiven = bool(moved) and all(index in near_starts for index in moved)
    found: list[str] = [] if forgiven else list(report_level)
    near: list[str] = list(report_level) if forgiven else []
    for index, entry in per_start:
        (near if index in near_starts else found).append(entry)
    return found, near


def _recomputed_chain(directory: Path) -> tuple[list[str], list[str], list[str]]:
    """Steps 3 and 4: the differences, the reasons and the near-threshold entries."""
    from openflowsheet.orchestrator.trace import SolvePolicy
    from openflowsheet.run.manifest import policy_sha256
    from openflowsheet.studies.nlp.closure import (
        SolverAvailability,
        StartEvidence,
        _start,
        classify_starts,
    )
    from openflowsheet.studies.nlp.formulation import FullSpaceNlp
    from openflowsheet.studies.nlp.request import OptimizationRequest, static_readiness
    from openflowsheet.studies.nlp.revision import (
        REPORT,
        REQUEST,
        REVISION,
        _bind_assessment,
    )
    from openflowsheet.studies.nlp.revision_host import RevisionNlpHost
    from openflowsheet.studies.nlp.verification import verify_candidate
    from openflowsheet.verify.certificate import CheckPolicy

    manifest = _read(directory, MANIFEST)
    report = _read(directory, REPORT)
    request = _read(directory, REQUEST)
    document = _read(directory, REVISION)
    indices = _starts(directory)
    policies = [directory / "starts" / str(k) / "start" for k in indices]
    policies = [path for path in policies if (path / MANIFEST_NAME).is_file()]
    if not policies:
        return [], ["no start bundle holds the policies: the chain was not recomputed"], []
    solve_policy = SolvePolicy.from_document(read_artifact(policies[0], "solve-policy.json"))
    check_document = read_artifact(policies[0], "check-policy.json")
    check_policy = CheckPolicy(
        policy_id=check_document["policy_id"], tolerances=check_document["tolerances"]
    )
    if (
        policy_sha256(solve_policy) != manifest["solve_policy_sha256"]
        or check_policy.sha256 != manifest["check_policy_sha256"]
    ):
        return (
            ["optimization-manifest.json: the start bundle's policies are not the record's"],
            [],
            [],
        )
    # Replay solves no NLP: the probe gates the solver, which replay does not use.
    available = SolverAvailability(True, "replay: no NLP solver is used")
    static = static_readiness(request, document, solver_probe=lambda: available)
    if not static.ready or static.formulation is None or static.decisions is None:
        return [f"static readiness {list(static.codes)} on replay; the record ran"], [], []
    parsed = OptimizationRequest.of(request)
    formulation = static.formulation
    host = RevisionNlpHost(
        document, static.decisions, solve_policy=solve_policy, check_policy=check_policy
    )
    spec = host.base_spec()
    starts = []
    failures: dict[int, str] = {}
    for index, start in enumerate(formulation.starts):
        readiness, found = _start(formulation, host, index, start, True, spec)
        starts.append(readiness)
        if found or readiness.state is None:
            failures[index] = "start not certified"
    if parsed.assessment is not None:
        bound = _bind_assessment(parsed.assessment, formulation, host, starts, failures)
        formulation = bound.formulation
    out: list[str] = []
    near: list[str] = []
    near_starts: set[int] = set()
    evidence: list[StartEvidence] = []
    recorded_starts = report.get("starts") or []
    for index, readiness in enumerate(starts):
        base = directory / "starts" / str(index)
        recorded_start = recorded_starts[index] if index < len(recorded_starts) else {}
        if not (base / "optimizer.json").is_file():
            evidence.append(StartEvidence(None, {}, recorded_start.get("detail")))
            continue
        optimizer = _read(base, "optimizer.json")
        checks: dict[str, Any] = {}
        if (base / "verification.json").is_file() and readiness.point is not None:
            nlp = FullSpaceNlp(host, formulation, readiness.point, readiness.start)
            primal = optimizer["final_primal"]
            values = np.array([float(primal[name]) for name in nlp.primal_ids], dtype=np.float64)
            x, decided = nlp.split(values)
            decisions = tuple(decided[name] for name in formulation.decision_ids)
            state = dict(zip(nlp.spec.variable_ids, (float(value) for value in x), strict=True))
            held = nlp.system if readiness.point.signature is not None else None
            fresh = verify_candidate(
                host,
                formulation,
                decisions,
                regimes=readiness.regimes or {},
                optimizer_state=state,
                closure=nlp.closure,
                held=held,
                phase=nlp.phase,
            )
            recorded = _read(base, "verification.json")
            real, flipped = verification_differences(fresh.as_document(), recorded)
            out += [f"starts/{index}/verification.json: {item}" for item in real]
            near += [f"starts/{index}/verification.json: {item}" for item in flipped]
            if flipped:
                near_starts.add(index)
            checks = {item.check: item.outcome for item in fresh.checks}
        evidence.append(
            StartEvidence(optimizer.get("ipopt_status"), checks, recorded_start.get("detail"))
        )
    verdict = classify_starts(evidence)
    reasons = [reason.as_document() for reason in verdict.reasons]
    real, flipped = classification_differences(
        report, verdict.status, reasons, verdict.classifications, near_starts
    )
    return out + real, [], near + flipped
