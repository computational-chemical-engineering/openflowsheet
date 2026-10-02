"""V17's fixture projects: each task's store seeded from its FX recipe (T07 W7c).

Normative text: `docs/derivations/T07-v17-tasks-spec.md` §4.1–§4.3 (principals, fixtures, the
session boundary and the fixture digest), §5 (each task's recipe), §5.9 (the forger), §6 (payload
placements) and §13.1 (FX-01…FX-12). The recipes, signatures, texts and payloads are read from
`docs/derivations/scripts/t07_reference.json`; nothing here states a registered value.

`build(task_id, project, token_file)` creates the task's project as `local-owner` through
`LocalApplication`, runs the recipe's steps in order, asserts every FX assertion the recipe
reaches, and returns the session boundary and the fixture digest. A failed assertion raises
`FixtureRefusedError`: the fixture is not usable, and the failure is a finding for the design
lane — never a reason to edit an expectation (spec §4.2).

**Deriving a document** (§4.2 `commit`). `derive(base, signature)` reshapes the registered revision
file `derive_from` so that its §4.5 signature is the registered one: an instance, connection or
specification the base holds under the same id (or, for a specification, the same target column)
is kept and revalued; one it lacks is copied from the first registered case that holds one of its
kind — an instance by model id, a connection from the base, a specification by target path — and
given its id. `neutralize` then sets the title and description to the registered texts, every
payload placement to its payload text, and every other free-text leaf to the neutral text.
FX-01 and FX-02 check the stored result, not this construction.
"""

from __future__ import annotations

import copy
import hashlib
import os
import shutil
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from typing import Any, Final

from benchmarks.t07.v17 import scorer
from openflowsheet.application.authz import grant, read_policy
from openflowsheet.application.jobs.executor import ProcessExecutor
from openflowsheet.application.jobs.worker import PAUSE_AT_STAGE_VARIABLE, PAUSED_FILE
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revision_run import Route, select_route
from openflowsheet.application.store import JOBS_DIR, POLICY_NAME
from openflowsheet.application.types import (
    CapabilityReference,
    Change,
    Edit,
    JobRequest,
    Limits,
    ReplayPolicy,
    ReproduceBody,
)
from openflowsheet.canonical import canonical_json, load_document
from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle, write_bundle
from openflowsheet.run.identity import r0_projection, r0_sha256

Document = dict[str, Any]

REFERENCE: Final[dict[str, Any]] = scorer.load_reference()
CONSTANTS: Final[Mapping[str, Any]] = REFERENCE["constants"]
NEUTRAL: Final[str] = CONSTANTS["neutral_text"]
OWNER: Final[str] = CONSTANTS["seed_principal"]
FIXTURE_JOB: Final[str] = scorer.FIXTURE_JOB
READY: Final[str] = scorer.READY
#: §4.2: the fixture's solves name the reserved policy id, which admission resolves (FX-11).
DEFAULT_POLICY: Final[str] = "default"
#: FX-06: the five structural checks a DRAFT revision does not run.
STRUCTURAL_CHECKS: Final[tuple[str, ...]] = tuple(f"STR-0{k}" for k in range(1, 6))
#: T10's recipe: the worker pauses at this stage until the cancel arrives (§5.10, FX-08).
PAUSE_STAGE: Final[str] = "solve"
#: A bound on waiting for a fixture job; a fixture solve normally ends in well under a second.
PATIENCE_S: Final[float] = 120.0
#: §5.9: the bundle members the forger edits.
CERTIFICATE_FILE: Final[str] = "solution-certificate.json"
FAILURE_FILE: Final[str] = "failure-bundle.json"
REVISION_FILE: Final[str] = "revision.json"
EVENTS_FILE: Final[str] = "solve-events.json"
CHECK_POLICY_FILE: Final[str] = "check-policy.json"
#: §5.9 step 2: the certificate fields the forger sets to the failed run's values.
FORGED_FROM_MANIFEST: Final[tuple[str, ...]] = (
    "model_version",
    "constants_sha256",
    "policy_id",
    "plan_id",
    "check_policy_sha256",
)


class FixtureRefusedError(RuntimeError):
    """A recipe's `expect` or an FX assertion failed: the fixture must not be used (§4.2)."""


def _refuse(assertion: str, message: str) -> FixtureRefusedError:
    return FixtureRefusedError(f"{assertion}: {message}")


# =============================================================================================
# Documents
# =============================================================================================


def load_case(relative: str) -> Document:
    """A registered revision file (YAML or JSON), parsed as `canonical.load_document` parses."""
    loaded = load_document((scorer.REPO_ROOT / relative).read_text("utf-8"), source=relative)
    if not isinstance(loaded, dict):
        raise ValueError(f"{relative} is not a revision document")
    return loaded


@cache
def _template_cases() -> tuple[str, ...]:
    """Every `derive_from` any recipe names, in path order: the pool templates come from."""
    return tuple(
        sorted(
            {
                step["derive_from"]
                for task in REFERENCE["tasks"].values()
                for step in task["fixture"]["steps"]
                if step["step"] == "commit"
            }
        )
    )


def template_instance(model_id: str) -> Document:
    for relative in _template_cases():
        for instance in load_case(relative)["instances"]:
            if instance["model"]["id"] == model_id:
                return copy.deepcopy(instance)
    raise ValueError(f"no registered case holds a {model_id} instance")


def template_parameter(model_id: str, name: str) -> Document:
    for relative in _template_cases():
        for instance in load_case(relative)["instances"]:
            if instance["model"]["id"] == model_id and name in instance["parameters"]:
                return copy.deepcopy(instance["parameters"][name])
    raise ValueError(f"no registered case gives {model_id} a parameter {name!r}")


def template_specification(object_type: str, path: str) -> Document:
    for relative in _template_cases():
        for specification in load_case(relative)["specifications"]:
            target = specification["target"]
            if target["object_type"] == object_type and target["path"] == path:
                return copy.deepcopy(specification)
    raise ValueError(f"no registered case pins {object_type} path {path!r}")


def column(specification: Mapping[str, Any]) -> str:
    """§4.5's column of a specification's target (`S1.n.A`, `S3.T`, `U-PHF.duty.Q`)."""
    target = specification["target"]
    object_id, path = target["object_id"], target["path"]
    name = (
        f"{object_id}.{path.removeprefix('state.')}"
        if target["object_type"] == "connection"
        else f"{object_id}.{path}"
    )
    component = target.get("component")
    return f"{name}.{component}" if component is not None else name


def _target(pin: str, connections: Mapping[str, Any]) -> tuple[str, str, str | None]:
    """The (object type, path, component) a §4.5 pin column names."""
    object_id, rest = pin.split(".", 1)
    if object_id in connections:
        quantity, _, component = rest.partition(".")
        return "connection", f"state.{quantity}", component or None
    return "instance", rest, None


def derive(base: Mapping[str, Any], sig: Mapping[str, Any]) -> Document:
    """`base` reshaped so that its §4.5 signature is `sig` (see the module docstring)."""
    document = copy.deepcopy(dict(base))
    document["component_set"]["components"] = list(sig["components"])

    by_id = {instance["id"]: instance for instance in base["instances"]}
    instances: list[Document] = []
    for instance_id, wanted in sig["instances"].items():
        model_id = wanted["model"]
        held = by_id.get(instance_id)
        instance = (
            copy.deepcopy(held)
            if held is not None and held["model"]["id"] == model_id
            else template_instance(model_id)
        )
        instance["id"] = instance_id
        parameters = instance["parameters"]
        for name in parameters:
            if name not in wanted["parameters"]:
                parameters[name]["value"] = 0.0  # absent from a signature means zero (§4.5)
        for name, value in wanted["parameters"].items():
            if name not in parameters:
                parameters[name] = template_parameter(model_id, name)
            parameters[name]["value"] = float(value)
        instances.append(instance)

    base_connections = {connection["id"]: connection for connection in base["connections"]}
    template = base["connections"][0]
    connections: list[Document] = []
    for connection_id, wanted in sig["connections"].items():
        connection = copy.deepcopy(base_connections.get(connection_id, template))
        connection["id"] = connection_id
        connection["from"] = {"instance": wanted["from"][0], "port": wanted["from"][1]}
        connection["to"] = {"instance": wanted["to"][0], "port": wanted["to"][1]}
        connection["phase_capability"] = wanted["phase"]
        connections.append(connection)

    own = {
        (instance["id"], name): parameter["value"]
        for instance in instances
        for name, parameter in instance["parameters"].items()
    }
    pins: Mapping[str, Any] = sig["pins"]
    kept: set[str] = set()
    specifications: list[Document] = []
    for specification in base["specifications"]:
        if specification["role"] != "fixed":
            continue
        name = column(specification)
        target = specification["target"]
        restated = (
            target["object_type"] == "instance"
            and target["path"].startswith("parameters.")
            and (target["object_id"], target["path"].removeprefix("parameters.")) in own
        )
        if name in pins:
            spec = copy.deepcopy(specification)
            spec["value"] = float(pins[name])
            kept.add(name)
        elif restated:  # SPEC-splitter-r: kept, restating the instance's own (new) value
            spec = copy.deepcopy(specification)
            spec["value"] = own[(target["object_id"], target["path"].removeprefix("parameters."))]
        else:
            continue
        specifications.append(spec)
    for pin, value in pins.items():
        if pin in kept:
            continue
        object_type, path, component = _target(pin, sig["connections"])
        spec = template_specification(object_type, path)
        spec["id"] = "SPEC-" + pin.replace(".", "-")
        spec["target"] = {
            "object_type": object_type,
            "object_id": pin.split(".", 1)[0],
            "path": path,
            "component": component,
        }
        spec["value"] = float(value)
        specifications.append(spec)

    document.update(instances=instances, connections=connections, specifications=specifications)
    return document


def _strings(value: Any, pointer: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, Mapping):
        for key in sorted(value):
            yield from _strings(value[key], f"{pointer}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{pointer}/{index}")


def free_text(document: Mapping[str, Any]) -> dict[str, str]:
    """§4.2's free-text leaves, keyed `<pointer>` at the top level and `<object id> <pointer>`
    within an instance, connection or specification (the payloads' placement notation)."""
    leaves: dict[str, str] = {}
    for key in ("title", "description"):
        if isinstance(document.get(key), str):
            leaves[f"/{key}"] = document[key]
    leaves.update(_strings(document.get("provenance"), "/provenance"))
    for instance in document["instances"]:
        for pointer, text in _strings(instance.get("policy"), "/policy"):
            leaves[f"{instance['id']} {pointer}"] = text
        for name, parameter in instance["parameters"].items():
            if isinstance(parameter.get("meaning"), str):
                leaves[f"{instance['id']} /parameters/{name}/meaning"] = parameter["meaning"]
    for connection in document["connections"]:
        if isinstance(connection.get("notes"), str):
            leaves[f"{connection['id']} /notes"] = connection["notes"]
    for specification in document["specifications"]:
        for key in ("notes", "provenance"):
            if isinstance(specification.get(key), str):
                leaves[f"{specification['id']} /{key}"] = specification[key]
    return leaves


def _set_leaf(document: Document, placement: str, text: str) -> None:
    owner, _, pointer = placement.rpartition(" ")
    node: Any = document
    if owner:
        (node,) = (
            item
            for section in ("instances", "connections", "specifications")
            for item in document[section]
            if item["id"] == owner
        )
    *parents, last = pointer.strip("/").split("/")
    for part in parents:
        node = node[int(part)] if isinstance(node, list) else node[part]
    if isinstance(node, list):
        node[int(last)] = text
    else:
        node[last] = text


def expected_text(step: Mapping[str, Any]) -> dict[str, str]:
    """FX-02: every free-text leaf's registered text, by placement, for a `commit` step's
    document (the neutral text unless the step registers another)."""
    texts = {"/title": step["title"], "/description": step["description"]}
    for placement, name in step.get("payloads", {}).items():
        texts[placement] = REFERENCE["payloads"][name]["text"]
    return texts


def neutralize(document: Document, step: Mapping[str, Any]) -> Document:
    """Every free-text leaf set to its registered text (§4.2, FX-02)."""
    registered = expected_text(step)
    for placement in free_text(document):
        _set_leaf(document, placement, registered.get(placement, NEUTRAL))
    for placement, text in registered.items():
        _set_leaf(document, placement, text)
    return document


def fixture_document(step: Mapping[str, Any], parent: str | None) -> Document:
    """A `commit` step's document: derived, neutralized, and carrying its registered id."""
    base = load_case(step["derive_from"])
    document = neutralize(derive(base, REFERENCE["signatures"][step["signature"]]), step)
    document["revision_id"] = step["revision_id"]
    document["parent_revision"] = parent
    return document


def edits_to(current: Mapping[str, Any] | None, document: Mapping[str, Any]) -> tuple[Edit, ...]:
    """The edits that turn `current` (None: the empty start) into `document`, top level."""
    removed = [
        Edit("remove", (key,))
        for key in sorted(current or {})
        if key not in document and key != "content_hash"
    ]
    return (*removed, *(Edit("set", (key,), value) for key, value in document.items()))


# =============================================================================================
# The seeding steps
# =============================================================================================


@dataclass(frozen=True)
class Fixture:
    """A seeded task project: where it is, the agent's credential, the boundary, the digest."""

    task_id: str
    project: Path
    token_file: Path
    capability: CapabilityReference
    session_start: dict[str, int]
    digest: str
    elapsed_s: float


def _head(app: LocalApplication) -> str | None:
    with app.store.reading() as connection:
        return app.store.head(connection)


def _commit(app: LocalApplication, step: Mapping[str, Any]) -> None:
    head = _head(app)
    current = None
    if head is not None:
        with app.store.reading() as connection:
            revision = app.store.get_revision(connection, head)
        current = revision.document if revision is not None else None
    document = fixture_document(step, head)
    result = app.commit_change(
        Change(edits=edits_to(current, document), new_revision_id=step["revision_id"]),
        head,
        f"v17-fixture-{step['revision_id']}",
    )
    if result.status != "committed" or result.revision_id != step["revision_id"]:
        raise _refuse("FX-03", f"commit of {step['revision_id']} ended {result.status}")


def _wait(app: LocalApplication, job_id: str) -> None:
    deadline = time.monotonic() + PATIENCE_S
    while app.get_job(job_id).status not in scorer.TERMINAL:
        if time.monotonic() > deadline:
            raise _refuse("FX-03", f"{job_id} did not end within {PATIENCE_S} s")
        time.sleep(0.02)


def _solve(app: LocalApplication, revision_id: str, key: str) -> str:
    submitted = app.submit_job(
        JobRequest.from_document(
            {
                "operation": "solve",
                "idempotency_key": key,
                "body": {"revision_id": revision_id, "policy_id": DEFAULT_POLICY},
            }
        )
    )
    _wait(app, submitted.job.job_id)
    return submitted.job.job_id


def _bundle_directory(app: LocalApplication, job_id: str) -> Path:
    (bundle,) = (ref for ref in app.get_job(job_id).outputs if ref.kind == "replay_bundle")
    row = app.store.artifact(bundle.artifact_id)
    assert row is not None
    return app.files_root / row.relpath


def _document(app: LocalApplication, artifact_id: str) -> Any:
    return load_document(app.artifact_bytes(artifact_id).decode("utf-8"), source=artifact_id)


def _state(app: LocalApplication, job_id: str) -> Mapping[str, Any] | None:
    (bundle,) = (ref for ref in app.get_job(job_id).outputs if ref.kind == "replay_bundle")
    member = f"{bundle.artifact_id}/solution-state.json"
    if app.store.artifact(member) is None:
        return None
    variables = _document(app, member).get("variables")
    return variables if isinstance(variables, Mapping) else None


def state_misses(
    state: Mapping[str, Any] | None, coordinates: Mapping[str, str]
) -> list[dict[str, Any]]:
    """§4.6's allowance check of a state against a root: every miss or absent coordinate."""
    misses: list[dict[str, Any]] = []
    for variable_id, expected in sorted(coordinates.items()):
        kind = scorer.coordinate_kind(variable_id)
        value = state.get(variable_id) if state is not None else None
        if kind is None or not scorer._is_number(value):
            misses.append({"id": variable_id, "absent": True})
            continue
        if not scorer.within(value, expected, CONSTANTS["allowance"][kind]):
            misses.append({"id": variable_id, "value": value, "expected": expected})
    return misses


def _solve_step(app: LocalApplication, step: Mapping[str, Any]) -> None:
    job_id = _solve(app, step["revision_id"], f"v17-fixture-{step['job_id']}")
    if job_id != step["job_id"]:
        raise _refuse("FX-03", f"the fixture solve is {job_id}, not {step['job_id']}")
    job = app.get_job(job_id)
    run = app.get_job_result(job_id).run_result
    expect = step["expect"]
    if job.status != expect["job_status"] or run is None:
        raise _refuse("FX-04/05", f"{job_id} ended {job.status} (error {job.error})")
    if run.policy_id != step["resolves_to"]:
        raise _refuse("FX-11", f"{job_id} resolved to {run.policy_id}")
    if "outcome_not" in expect:  # FX-04
        kinds = [ref.kind for ref in job.outputs]
        if run.outcome == expect["outcome_not"] or kinds != expect["output_kinds"]:
            raise _refuse("FX-04", f"{job_id}: outcome {run.outcome}, outputs {kinds}")
        if run.verification_status is not None:
            raise _refuse("FX-04", f"{job_id}: verification_status {run.verification_status}")
    if "verification_status" in expect:  # FX-05
        if run.verification_status != expect["verification_status"]:
            raise _refuse("FX-05", f"{job_id}: {run.verification_status}")
        signature = step_signature(app, step["revision_id"])
        root = REFERENCE["judged"][signature]["root"]
        misses = state_misses(_state(app, job_id), REFERENCE["roots"][root])
        if misses:
            raise _refuse("FX-05", f"{job_id} misses roots.{root}: {misses}")


def step_signature(app: LocalApplication, revision_id: str) -> str:
    """The registered signature name a stored revision's §4.5 signature equals (FX-01)."""
    with app.store.reading() as connection:
        revision = app.store.get_revision(connection, revision_id)
    assert revision is not None
    found = scorer.signature(revision.as_document())
    names: list[str] = [
        name
        for name, registered in sorted(REFERENCE["signatures"].items())
        if scorer.signatures_equal(found, registered)
    ]
    if len(names) != 1:
        raise _refuse("FX-01", f"{revision_id}'s signature matches {names}")
    return names[0]


@contextmanager
def _environment(name: str, value: str) -> Iterator[None]:
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _solve_then_cancel(app: LocalApplication, step: Mapping[str, Any]) -> None:
    """FX-08 by the W4c pause hook: the worker holds at the solve stage until the cancel."""
    with _environment(PAUSE_AT_STAGE_VARIABLE, PAUSE_STAGE):
        submitted = app.submit_job(
            JobRequest.from_document(
                {
                    "operation": "solve",
                    "idempotency_key": f"v17-fixture-{step['job_id']}",
                    "body": {"revision_id": step["revision_id"], "policy_id": DEFAULT_POLICY},
                }
            )
        )
        job_id = submitted.job.job_id
        paused = app.files_root / JOBS_DIR / job_id / PAUSED_FILE
        deadline = time.monotonic() + PATIENCE_S
        while not (paused.is_file() and paused.read_text("utf-8")):
            if time.monotonic() > deadline or app.get_job(job_id).status in scorer.TERMINAL:
                raise _refuse("FX-08", f"{job_id} never paused at {PAUSE_STAGE}")
            time.sleep(0.01)
        app.cancel_job(job_id)
        _wait(app, job_id)
    job = app.get_job(job_id)
    reason = job.ending.reason if job.ending is not None else None
    if job_id != step["job_id"] or (job.status, reason) != (
        step["expect"]["job_status"],
        step["expect"]["reason"],
    ):
        raise _refuse("FX-08", f"{job_id} ended {job.status}({reason})")


def forge(failed: Path, donor: Path, target: Path) -> Path:
    """§5.9 step 2, design Q26 (ii)'s forger: the failed run's bundle carrying the donor's
    `VERIFIED` certificate, consistent in every cross-referenced field, with the three payloads
    placed, and the index, `artifact_r0_sha256` and `manifest_sha256` recomputed."""
    manifest, _ = read_manifest(failed)
    artifacts = {name: read_artifact(failed, name) for name in manifest.artifacts}
    artifacts.pop(FAILURE_FILE)
    certificate = copy.deepcopy(read_artifact(donor, CERTIFICATE_FILE))
    for name in FORGED_FROM_MANIFEST:
        certificate[name] = getattr(manifest, name)
    if CHECK_POLICY_FILE in artifacts and "check_policy_id" in artifacts[CHECK_POLICY_FILE]:
        certificate["check_policy_id"] = artifacts[CHECK_POLICY_FILE]["check_policy_id"]
    events = artifacts[EVENTS_FILE]
    # The last event's recorded `state_sha256`. A run that failed at initialization records
    # the empty string on every event (no state was ever evaluated), and that is what is copied.
    states = [event["state_sha256"] for event in events if "state_sha256" in event]
    certificate["target_state_sha256"] = states[-1]
    certificate["statements"][0] = REFERENCE["payloads"]["INJ-4"]["text"]
    artifacts[CERTIFICATE_FILE] = certificate
    revision = artifacts[REVISION_FILE]
    revision["description"] = f"{revision['description']} {REFERENCE['payloads']['INJ-5']['text']}"
    (last,) = [event for event in events if event.get("message")][-1:]
    last["message"] = REFERENCE["payloads"]["INJ-6"]["text"]
    forged = replace(
        manifest,
        outcome="CONVERGED",
        verification_status="VERIFIED",
        artifact_r0_sha256=r0_sha256(r0_projection(artifacts)),
    )
    write_bundle(target, forged, artifacts)
    return target


def _forge_and_import(app: LocalApplication, step: Mapping[str, Any], task: str) -> None:
    """§5.9: solve in a scratch project, forge, import as `local-owner` (FX-07)."""
    recipe = REFERENCE["tasks"][task]["fixture"]
    commit = next(s for s in recipe["steps"] if s["revision_id"] == step["failed_run_of"])
    donor_step = _donor_step(step["donor_certificate_of"])
    with tempfile.TemporaryDirectory(prefix="v17-forge-") as scratch:
        root = Path(scratch)
        with LocalApplication.create(root / "project", project_id="v17-forge") as other:
            _commit(other, commit)
            _commit(other, donor_step)
            failed = _solve(other, commit["revision_id"], "v17-forge-failed")
            donor = _solve(other, donor_step["revision_id"], "v17-forge-donor")
            failed_run = other.get_job_result(failed).run_result
            donor_run = other.get_job_result(donor).run_result
            kinds = [ref.kind for ref in other.get_job(failed).outputs]
            if (
                failed_run is None
                or failed_run.outcome == "CONVERGED"
                or "failure_bundle" not in kinds
            ):
                raise _refuse("FX-07", f"the scratch solve ended {failed_run}, outputs {kinds}")
            if donor_run is None or donor_run.verification_status != "VERIFIED":
                raise _refuse("FX-07", f"the donor solve is not VERIFIED: {donor_run}")
            bundle = forge(
                _bundle_directory(other, failed),
                _bundle_directory(other, donor),
                root / "forged",
            )
            if not verify_bundle(bundle).ok:
                raise _refuse("FX-07", f"the forgery fails integrity: {verify_bundle(bundle)}")
            job_id = _import_without_rerun(app, bundle, step)
    job = app.get_job(job_id)
    report = app.get_job_result(job_id).replay_report
    if job_id != FIXTURE_JOB or report is None:
        raise _refuse("FX-07", f"the import is {job_id}, ended {job.status} ({job.error})")
    expect = step["expect"]
    got = (report.mode, report.verdict, report.integrity.ok)
    wanted = tuple(expect["replay_report"][k] for k in ("mode", "verdict", "integrity_ok"))
    if job.operation != "reproduce" or got != wanted:
        raise _refuse("FX-07", f"{job.job_id}: {got}, expected {wanted}")
    body = job.request.body
    assert isinstance(body, ReproduceBody)
    _check_import(app, body.bundle_artifact_id, step)


def _import_without_rerun(app: LocalApplication, bundle: Path, step: Mapping[str, Any]) -> str:
    """§5.9 step 3, `reproduce(<forged dir>, ReplayPolicy(rerun=False))` as `local-owner`,
    with one difference: the job's idempotency key is registered, not `reproduce`'s fresh
    `auto:<uuid>`. The key is inside `request_sha256`, which the §4.3 digest holds, so a random
    key would make the three repetitions' digests differ (FX-10). The import itself is
    `reproduce`'s own (`LocalApplication._import_bundle`); the job is an ordinary `submit_job`."""
    policy = ReplayPolicy(rerun=False)
    artifact_id = app._import_bundle(bundle, "reproduce")
    submitted = app.submit_job(
        JobRequest.from_document(
            {
                "operation": "reproduce",
                "idempotency_key": f"v17-fixture-{step['job_id']}",
                "body": {"bundle_artifact_id": artifact_id, "rerun": policy.rerun},
            }
        )
    )
    _wait(app, submitted.job.job_id)
    return submitted.job.job_id


def _donor_step(signature: str) -> dict[str, Any]:
    """The donor revision of §5.9 step 1: the registered case of `signature`, as a commit."""
    for task in REFERENCE["tasks"].values():
        for step in task["fixture"]["steps"]:
            if step["step"] == "commit" and step["signature"] == signature:
                return {**step, "revision_id": "v17-forge-donor"}
    raise ValueError(f"no recipe commits a {signature} revision")


def _check_import(app: LocalApplication, bundle_id: str, step: Mapping[str, Any]) -> None:
    """FX-07: the imported certificate and manifest say what the forgery says, and each payload
    is present verbatim at its placement and reachable through `get_artifact`."""
    expect = step["expect"]
    certificate = app.get_artifact(f"{bundle_id}/{CERTIFICATE_FILE}", depth=12).value
    manifest = app.get_artifact(f"{bundle_id}/run-manifest.json", depth=12).value
    if certificate["verification_status"] != expect["archived_certificate_verification_status"]:
        raise _refuse("FX-07", f"imported certificate says {certificate['verification_status']}")
    if manifest["outcome"] != expect["archived_manifest_outcome"]:
        raise _refuse("FX-07", f"imported manifest says {manifest['outcome']}")
    for placement, name in step["payloads"].items():
        file, _, pointer = placement.partition(" ")
        text = REFERENCE["payloads"][name]["text"]
        if file == EVENTS_FILE:  # "<last event with a message> /message"
            events = _document(app, f"{bundle_id}/{file}")
            last = max(k for k, event in enumerate(events) if event.get("message"))
            pointer = f"/{last}/message"
        found = app.get_artifact(f"{bundle_id}/{file}", pointer=pointer, depth=12).value
        if not isinstance(found, str) or text not in found:
            raise _refuse("FX-07", f"{name} is not at {placement}")


def _grant(project: Path, step: Mapping[str, Any], token_file: Path) -> CapabilityReference:
    limits = step["limits"]
    capability, token = grant(
        project,
        principal_id=step["principal"],
        rights=step["rights"],
        limits=Limits(
            default_wall_time_s=float(limits["default_wall_time_s"]),
            max_wall_time_s=float(limits["max_wall_time_s"]),
            max_active_jobs=int(limits["max_active_jobs"]),
        ),
        capability_id=step["capability_id"],
    )
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token + "\n", encoding="utf-8")
    token_file.chmod(0o600)
    return capability


# =============================================================================================
# The FX assertions over the finished store, the boundary and the digest
# =============================================================================================


def prompt(task_id: str) -> str:
    """§4.4: the body, a blank line, and the footer with the task's id and answer members."""
    task = REFERENCE["tasks"][task_id]
    footer: str = (
        REFERENCE["footer_template"]
        .replace("<TASK_ID>", task_id)
        .replace("<ANSWER_MEMBERS>", task["answer_members"])
    )
    return str(task["body"]) + "\n\n" + footer


def _check_store(app: LocalApplication, task_id: str) -> None:
    recipe = REFERENCE["tasks"][task_id]["fixture"]
    if _head(app) != recipe["head"]:
        raise _refuse("FX-03", f"head is {_head(app)}, not {recipe['head']}")
    for step in recipe["steps"]:
        if step["step"] != "commit":
            continue
        revision_id = step["revision_id"]
        with app.store.reading() as connection:
            revision = app.store.get_revision(connection, revision_id)
        if revision is None:
            raise _refuse("FX-03", f"{revision_id} is not stored")
        document = revision.as_document()
        if step_signature(app, revision_id) != step["signature"]:  # FX-01
            raise _refuse("FX-01", f"{revision_id} is not {step['signature']}")
        registered = expected_text(step)
        wrong = {
            placement: text
            for placement, text in free_text(document).items()
            if text != registered.get(placement, NEUTRAL)
        }
        if wrong or any(placement not in free_text(document) for placement in registered):
            raise _refuse("FX-02", f"{revision_id}: {sorted(wrong)}")
        report = app.validate(revision_id, "simulation")
        if "expect_validation" in step:  # FX-06
            expect = step["expect_validation"]
            not_run = {check.id for check in report.checks if check.result == "NOT_RUN"}
            texts = [check.message for check in report.checks] + [
                report.structural_counts_absent_reason or ""
            ]
            named = any(
                wanted in text for wanted in expect["reason_names_one_of"] for text in texts
            )
            if report.status != expect["status"] or not set(STRUCTURAL_CHECKS) <= not_run:
                raise _refuse("FX-06", f"{revision_id}: {report.status}, NOT_RUN {not_run}")
            if not named:
                raise _refuse("FX-06", f"{revision_id}: no reason names {expect}")
        else:  # FX-11
            route = select_route(document)
            if report.status != READY or not (
                isinstance(route, Route) and route.solve_path == "revision_eo"
            ):
                raise _refuse("FX-11", f"{revision_id}: {report.status}, route {route}")
    if (
        hashlib.sha256(prompt(task_id).encode("utf-8")).hexdigest()
        != (REFERENCE["tasks"][task_id]["prompt_sha256"])
    ):
        raise _refuse("FX-12", f"{task_id}'s prompt does not hash as registered")


def _check_capability(project: Path, step: Mapping[str, Any]) -> None:
    """FX-09: the agent's rights and limits exactly; no grant presents `local-owner`."""
    policy = read_policy(project / POLICY_NAME)
    (agent,) = [c for c in policy.capabilities if c.capability_id == step["capability_id"]]
    limits = agent.limits.as_document()
    if (
        agent.principal_id != step["principal"]
        or list(agent.rights) != sorted(step["rights"])
        or any(float(limits[name]) != float(value) for name, value in step["limits"].items())
    ):
        raise _refuse("FX-09", f"the agent grant is {agent}")
    if any(OWNER in (c.principal_id, c.capability_id) for c in policy.capabilities):
        raise _refuse("FX-09", "a grant presents local-owner")


def session_start(app: LocalApplication) -> dict[str, int]:
    """§4.3: the largest audit seq, job ordinal and revision ordinal before the session."""
    with app.store.reading() as connection:
        row = connection.execute(
            "SELECT (SELECT COALESCE(MAX(seq), 0) FROM audit),"
            " (SELECT COALESCE(MAX(ordinal), 0) FROM jobs),"
            " (SELECT COALESCE(MAX(ordinal), 0) FROM revisions)"
        ).fetchone()
    return {"audit_seq": int(row[0]), "job_ordinal": int(row[1]), "revision_ordinal": int(row[2])}


def digest(project: Path) -> str:
    """§4.3's fixture digest: SHA-256 of the canonical JSON of the store's identity members."""
    policy = read_policy(project / POLICY_NAME)
    with LocalApplication.open(project) as app, app.store.reading() as connection:
        revisions = connection.execute(
            "SELECT ordinal, revision_id, content_sha256, principal_id FROM revisions"
            " ORDER BY ordinal"
        ).fetchall()
        artifacts = connection.execute(
            "SELECT artifact_id, kind, name FROM artifacts ORDER BY artifact_id"
        ).fetchall()
        head = app.store.head(connection)
        jobs = [app.store.get_job(job_id) for job_id in app.store.job_ids()]
        project_id = app.project_id
    document = {
        "project_id": project_id,
        "revisions": [list(row) for row in revisions],
        "head": head,
        "jobs": [
            [
                job.job_id,
                job.operation,
                job.request_sha256,
                job.principal_id,
                job.status,
                job.ending.reason if job.ending is not None else None,
                [ref.kind for ref in job.outputs],
            ]
            for job in jobs
            if job is not None
        ],
        "artifacts": [list(row) for row in artifacts],
        "capabilities": [
            [c.capability_id, c.principal_id, list(c.rights), c.limits.as_document()]
            for c in sorted(policy.capabilities, key=lambda c: c.capability_id)
        ],
    }
    return hashlib.sha256(canonical_json(document)).hexdigest()


# =============================================================================================
# build
# =============================================================================================


def build(task_id: str, project: Path, token_file: Path) -> Fixture:
    """Seed `task_id`'s fixture project at `project` (absent or empty) and write the agent's
    token to `token_file`; every FX assertion the recipe reaches is checked (§13.1)."""
    started = time.monotonic()
    recipe = REFERENCE["tasks"][task_id]["fixture"]
    LocalApplication.create(project, project_id=recipe["project_id"]).close()
    kinds = {step["step"] for step in recipe["steps"]}
    executor: Any = ProcessExecutor(test_hooks=True) if "solve_then_cancel" in kinds else "inline"
    capability: CapabilityReference | None = None
    grant_step: Mapping[str, Any] | None = None
    try:
        with LocalApplication.open(project, executor=executor) as app:
            for step in recipe["steps"]:
                if step["principal"] not in (OWNER, CONSTANTS["agent"]["principal_id"]):
                    raise _refuse("FX-09", f"a step runs as {step['principal']}")
                kind = step["step"]
                if kind == "commit":
                    _commit(app, step)
                elif kind == "solve":
                    _solve_step(app, step)
                elif kind == "solve_then_cancel":
                    _solve_then_cancel(app, step)
                elif kind == "forge_and_import":
                    _forge_and_import(app, step, task_id)
                elif kind == "grant":
                    capability = _grant(project, step, token_file)
                    grant_step = step
                else:
                    raise ValueError(f"unknown fixture step {kind!r}")
            _check_store(app, task_id)
            start = session_start(app)
    except BaseException:
        shutil.rmtree(project, ignore_errors=True)
        raise
    if capability is None or grant_step is None:
        raise _refuse("FX-09", f"{task_id}'s recipe grants nothing")
    _check_capability(project, grant_step)
    return Fixture(
        task_id=task_id,
        project=project,
        token_file=token_file,
        capability=capability,
        session_start=start,
        digest=digest(project),
        elapsed_s=time.monotonic() - started,
    )


def build_many(task_ids: Sequence[str], root: Path) -> dict[str, Fixture]:
    """`build` for each task under `root/<task>/project`, tokens under `root/<task>/secret`."""
    return {
        task_id: build(task_id, root / task_id / "project", root / task_id / "secret" / "token")
        for task_id in task_ids
    }
