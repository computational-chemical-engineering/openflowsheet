"""X06-WO3: project solve policies, ADR 0078 D4 (E-X06-11 to E-X06-15).

A project registers a `user.` solve-policy document once; a solve names it as it names an
offered policy. These tests drive `LocalApplication` (the Python transport) and the pure check
`solve_policy_problems`; the conformance scenario runs the two operations on every transport
(`tests/test_t07_conformance.py`). The pre-X06 fixture `fixtures/x06/pre_x06_policy_surface.json`
was taken at `main` `aa5822ac` (before X06): `get_project` of a project without registered
policies (project id `x06-get-project`) and the refusal of each benchmark-registered name that
is not offered, and of an unknown id, by `solve`.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit

from openflowsheet.application.errors import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.policy_types import ReplayPolicy
from openflowsheet.application.solve_policy_registry import POLICY_DIR, artifact_id
from openflowsheet.canonical import canonical_json
from openflowsheet.orchestrator.policies import (
    APPLICATION_POLICIES,
    REGISTERED_POLICY_IDS,
    T06_REVISION_V2,
)
from openflowsheet.orchestrator.policy_validation import solve_policy_problems
from openflowsheet.run.manifest import policy_sha256
from openflowsheet.verify.verdict import CheckPolicy

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "solve-policy.schema.json").read_text("utf-8"))
PRE_X06 = json.loads((ROOT / "tests/fixtures/x06/pre_x06_policy_surface.json").read_text("utf-8"))
CASE = "SYN-001-nominal"


def copy_of(policy_id: str, base: Any = T06_REVISION_V2) -> dict[str, Any]:
    """`base`'s document with only `policy_id` changed."""
    return {**base.as_document(), "policy_id": policy_id}


def refused(call: Any) -> dict[str, Any]:
    with pytest.raises(ApplicationError) as caught:
        call()
    return caught.value.error.as_document()


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "p", project_id="x06-get-project")
    yield application
    application.close()


# ------------------------------------------------------------------------------ E-X06-11


def test_e_x06_11a_a_schema_invalid_policy_is_refused_with_its_pointer(
    app: LocalApplication,
) -> None:
    document = copy_of("user.a")
    del document["merit"]
    error = refused(lambda: app.register_solve_policy(policy=document, idempotency_key="k"))
    assert error["code"] == "invalid_request"
    assert error["detail"]["pointer"] == "/policy"
    document = copy_of("user.a")
    document["max_attempts"] = 0
    error = refused(lambda: app.register_solve_policy(policy=document, idempotency_key="k"))
    assert (error["code"], error["detail"]["pointer"]) == (
        "invalid_request",
        "/policy/max_attempts",
    )
    assert [p.code for p in solve_policy_problems(document)] == [None]


@pytest.mark.parametrize("policy_id", ["T06-revision-v2", "copy", "user.", "user._x", "User.x"])
def test_e_x06_11b_an_id_outside_user_is_refused(app: LocalApplication, policy_id: str) -> None:
    error = refused(
        lambda: app.register_solve_policy(policy=copy_of(policy_id), idempotency_key="k")
    )
    assert error["code"] == "invalid_request"
    assert error["detail"] == {"code": "solve_policy_id_invalid", "pointer": "/policy/policy_id"}
    assert error["message"].startswith("solve_policy_id_invalid: ")


def _open_members(schema: dict[str, Any], pointer: str = "") -> list[str]:
    """Every location of `solve-policy.schema.json` the schema leaves open: a string without
    `enum`, `const` or `pattern` (`<pointer>`, an array's items as `<pointer>/0`), and an object
    whose keys are open (`<pointer>/*`: `additionalProperties` not `false`)."""
    found: list[str] = []
    if "enum" in schema or "const" in schema:
        return found
    if schema.get("type") == "string" and "pattern" not in schema:
        found.append(pointer)
    if schema.get("type") == "array":
        found += _open_members(schema["items"], pointer + "/0")
    if schema.get("type") == "object":
        if schema.get("additionalProperties", True) is not False:
            found.append(pointer + "/*")
        for name, member in schema.get("properties", {}).items():
            found += _open_members(member, f"{pointer}/{name}")
    return found


def _set(document: dict[str, Any], path: list[str], value: Any) -> None:
    for name in path[:-1]:
        document = document[name]
    document[path[-1]] = value


#: E-X06-11 (c): for each open member, how an unregistered value is put there, and the pointer
#: the refusal names. `/policy_id` is (b)'s, tested above.
UNREGISTERED: dict[str, tuple[list[str], Any, str]] = {
    "/residual_tolerances/*": (
        ["residual_tolerances", "mole_count"],
        {"absolute": 1.0, "relative": 0.0, "scale": 1.0},
        "/residual_tolerances/mole_count",
    ),
    "/scales/*": (["scales", "mole_count"], 1.0, "/scales/mole_count"),
    "/linear_solver/*": (["linear_solver", "fill_factor"], 10, "/linear_solver/fill_factor"),
    "/linear_solver/name": (
        ["linear_solver", "name"],
        "scipy.sparse.linalg.spsolve",
        "/linear_solver/name",
    ),
    "/initializer_chain/0": (["initializer_chain"], ["user_guess"], "/initializer_chain/0"),
    "/recycle/policy_id": (["recycle", "policy_id"], "T02-recycle-policy-v9", "/recycle/policy_id"),
    "/recycle/tear_streams/0": (["recycle", "tear_streams"], ["S1"], "/recycle/tear_streams"),
}


def test_e_x06_11c_every_open_member_is_checked_against_its_registry(
    app: LocalApplication,
) -> None:
    walked = _open_members(SCHEMA)
    unchecked = sorted(set(walked) - {"/policy_id"} - set(UNREGISTERED))
    assert not unchecked, f"open members without a registration check: {unchecked}"
    assert sorted(set(UNREGISTERED) - set(walked)) == []  # no stale entry
    for key, (path, value, pointer) in UNREGISTERED.items():
        document = copy_of("user.c")
        _set(document, path, value)
        (problem,) = solve_policy_problems(document)
        assert (problem.code, problem.pointer) == ("solve_policy_invalid", pointer), key
        error = refused(lambda d=document: app.register_solve_policy(policy=d, idempotency_key="k"))
        assert error["code"] == "invalid_request", key
        assert error["detail"] == {"code": "solve_policy_invalid", "pointer": "/policy" + pointer}
    # The registered values of each open member pass (every offered policy, as a copy).
    for offered in APPLICATION_POLICIES.values():
        assert solve_policy_problems(copy_of("user.ok", offered)) == []


def test_e_x06_11d_a_member_the_solver_would_rewrite_is_refused(app: LocalApplication) -> None:
    document = copy_of("user.d")
    document["globalization"]["homotopy"]["delta_lambda_initial"] = "2/8"  # the solver reads 1/4
    (problem,) = solve_policy_problems(document)
    assert (problem.code, problem.pointer) == (
        "solve_policy_invalid",
        "/globalization/homotopy/delta_lambda_initial",
    )
    error = refused(lambda: app.register_solve_policy(policy=document, idempotency_key="k"))
    assert error["detail"]["code"] == "solve_policy_invalid"


def test_e_x06_11e_exists_conflict_and_replay_leave_the_stored_file(app: LocalApplication) -> None:
    document = copy_of("user.e")
    first = app.register_solve_policy(policy=document, idempotency_key="k1")
    data = canonical_json(document)
    sha = hashlib.sha256(data).hexdigest()
    assert first.as_document() == {
        "status": "registered",
        "policy_id": "user.e",
        "policy_sha256": sha,
        "conflict": None,
    }
    assert sha == policy_sha256(T06_REVISION_V2.__class__.from_document(document))
    row = app.store.artifact(artifact_id("user.e"))
    assert row is not None and (row.job_id, row.kind, row.name) == (
        None,
        "solve_policy",
        "user.e.json",
    )
    assert row.relpath == f"{POLICY_DIR}/{sha}.json"
    path = app.files_root / row.relpath
    assert path.read_bytes() == data
    assert app.register_solve_policy(policy=document, idempotency_key="k2").status == "exists"
    other = copy_of("user.e")
    other["max_attempts"] = 3
    conflict = app.register_solve_policy(policy=other, idempotency_key="k3")
    other_sha = hashlib.sha256(canonical_json(other)).hexdigest()
    assert conflict.as_document() == {
        "status": "conflict",
        "policy_id": "user.e",
        "policy_sha256": sha,
        "conflict": {"expected_sha256": other_sha, "actual_sha256": sha},
    }
    assert path.read_bytes() == data
    assert app.store.artifact(artifact_id("user.e")) == row
    assert sorted(p.name for p in path.parent.iterdir()) == [f"{sha}.json"]
    replay = app.register_solve_policy(policy=document, idempotency_key="k1")
    assert (replay.status, replay.policy_sha256) == ("replayed", sha)
    error = refused(lambda: app.register_solve_policy(policy=other, idempotency_key="k1"))
    assert error["code"] == "idempotency_key_reused"
    view = app.get_solve_policy(policy_id="user.e")
    assert (view.origin, view.policy_sha256, dict(view.document)) == ("project", sha, document)


# ------------------------------------------------------------------- E-X06-12, E-X06-13


def _bundle(application: LocalApplication, job_id: str) -> Path:
    job = application.get_job(job_id)
    (bundle,) = [output for output in job.outputs if output.kind == "replay_bundle"]
    row = application.store.artifact(bundle.artifact_id)
    assert row is not None
    return application.files_root / row.relpath


def _find(document: Any, key: str) -> list[Any]:
    if isinstance(document, dict):
        found = [document[key]] if key in document else []
        return found + [hit for value in document.values() for hit in _find(value, key)]
    if isinstance(document, list):
        return [hit for value in document for hit in _find(value, key)]
    return []


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """One corpus revision solved under `T06-revision-v2` and under `user.copy` (its document
    with only `policy_id` changed)."""
    application = LocalApplication.create(tmp_path_factory.mktemp("x06") / "p")
    try:
        revision = commit(application, CORPUS[CASE]())
        document = copy_of("user.copy")
        application.register_solve_policy(policy=document, idempotency_key="copy")
        results = {
            name: application.solve(revision, name) for name in ("T06-revision-v2", "user.copy")
        }
        yield {
            "app": application,
            "document": document,
            "results": results,
            "bundles": {name: _bundle(application, r.job_id) for name, r in results.items()},
        }
    finally:
        application.close()


def test_e_x06_12_a_renamed_copy_solves_to_the_same_state(runs: dict[str, Any]) -> None:
    """Q7, the solve: nothing the solver computes depends on the policy's name. Measured at
    X06-WO3: `solution-state.json` is byte-identical; the certificate differs only in the two
    members that name the policy (`policy_id`, and `plan_id`, which embeds it); the manifest
    records `user.copy`'s hash. (The bundle check is another matter: E-X06-13.)"""
    base, copy_run = (runs["results"][n] for n in ("T06-revision-v2", "user.copy"))
    assert (base.outcome, base.verification_status) == ("CONVERGED", "VERIFIED")
    assert (copy_run.outcome, copy_run.verification_status) == (
        base.outcome,
        base.verification_status,
    )
    files = {name: _files(root) for name, root in runs["bundles"].items()}
    left, right = files["T06-revision-v2"], files["user.copy"]
    assert sorted(left) == sorted(right)
    state = "artifacts/solution-state.json"
    assert left[state] == right[state]
    certificates = [json.loads(f["artifacts/solution-certificate.json"]) for f in (left, right)]
    names = {"policy_id", "plan_id"}
    assert {k for k in certificates[0] if certificates[0][k] != certificates[1].get(k)} == names
    assert [{k: v for k, v in c.items() if k not in names} for c in certificates][0] == {
        k: v for k, v in certificates[1].items() if k not in names
    }
    hashes = [_find(json.loads(f[state]), "state_sha256") for f in (left, right)]
    assert hashes[0] and hashes[0] == hashes[1]
    manifest = json.loads(right["run-manifest.json"])
    copy_sha = hashlib.sha256(canonical_json(runs["document"])).hexdigest()
    assert manifest["policy_sha256"] == copy_sha
    assert json.loads(right["artifacts/solve-policy.json"]) == runs["document"]


@pytest.mark.xfail(
    strict=True,
    reason="Q7 STOP (X06-WO3, reported to the design lane): run.bundle._cross_check_solve_path "
    "resolves solve-path.json's policy_requested by name through the application registry, so "
    "a project policy's bundle fails its integrity check (tampered: solve-path.json) and "
    "reproduces inspected_archived_results/NOT_RUN instead of compatible_reproduction/MATCH",
)
def test_e_x06_13_the_copy_bundle_replays_without_the_project(
    runs: dict[str, Any], tmp_path: Path
) -> None:
    fresh = LocalApplication.create(tmp_path / "fresh")
    try:
        reports = {
            name: fresh.reproduce(root, ReplayPolicy(rerun=True)).as_document()
            for name, root in runs["bundles"].items()
        }
    finally:
        fresh.close()
    base, copy_report = reports["T06-revision-v2"], reports["user.copy"]
    assert (copy_report["mode"], copy_report["verdict"]) == (base["mode"], base["verdict"])
    assert copy_report["integrity"] == base["integrity"]


def test_q7_the_bundle_check_resolves_the_requested_policy_by_name(runs: dict[str, Any]) -> None:
    """The measured cause of E-X06-13's failure, pinned until the design lane rules (Q7):
    `verify_bundle` marks the project policy's `solve-path.json` tampered, and only it."""
    from openflowsheet.run.bundle import verify_bundle

    integrity = {name: verify_bundle(root).as_document() for name, root in runs["bundles"].items()}
    assert integrity["T06-revision-v2"]["ok"] is True
    assert integrity["user.copy"] == {
        "ok": False,
        "missing": [],
        "tampered": ["solve-path.json"],
        "unexpected": [],
    }


# ------------------------------------------------------------------------------ E-X06-14


def test_e_x06_14_a_looser_solver_tolerance_never_loosens_verification(
    app: LocalApplication,
) -> None:
    from openflowsheet.models.lifted_tolerance import KIND_TOLERANCE

    document = copy_of("user.loose")
    document["residual_tolerances"] = {
        kind: {"absolute": value * 1e6, "relative": 0.0, "scale": 1.0}
        for kind, value in sorted(KIND_TOLERANCE.items())
    }
    assert app.register_solve_policy(policy=document, idempotency_key="l").status == "registered"
    revision = commit(app, CORPUS[CASE]())
    run = app.solve(revision, "user.loose")
    registered = CheckPolicy()
    files = _files(_bundle(app, run.job_id))
    certificate = json.loads(files["artifacts/solution-certificate.json"])
    assert run.check_policy_sha256 == registered.sha256
    assert certificate["check_policy_sha256"] == registered.sha256
    recorded = json.loads(files["artifacts/check-policy.json"])
    check = CheckPolicy(policy_id=recorded["policy_id"], tolerances=recorded["tolerances"])
    assert check.sha256 == registered.sha256 and check.is_registered
    # Verified under the registered tolerances (measured), never under the policy's.
    assert (run.outcome, run.verification_status) == ("CONVERGED", "VERIFIED")


def test_e_x06_14_the_verifier_imports_no_solve_policy() -> None:
    package = ROOT / "src" / "openflowsheet" / "verify"
    offenders = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                names = {alias.name for alias in node.names}
                if "SolvePolicy" in names or node.module.endswith(
                    ("orchestrator.policies", "policy_validation", "solve_policy_registry")
                ):
                    offenders.append(f"{path.name}: from {node.module} import {sorted(names)}")
            if isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}: import {a.name}" for a in node.names if "polic" in a.name
                ]
    assert offenders == []


# ------------------------------------------------------------------------------ E-X06-15


def test_e_x06_15_get_project_lists_the_offered_then_the_projects(app: LocalApplication) -> None:
    from openflowsheet import __version__

    expected = copy.deepcopy(PRE_X06["get_project"])
    expected["server"]["package_version"] = __version__
    assert canonical_json(app.get_project().as_document()) == canonical_json(expected)
    for name in ("user.zz", "user.B", "user.a"):
        app.register_solve_policy(policy=copy_of(name), idempotency_key=name)
    listed = [entry["policy_id"] for entry in app.get_project().as_document()["solve_policies"]]
    assert listed == [*sorted(APPLICATION_POLICIES), "user.B", "user.a", "user.zz"]


def test_e_x06_15_the_benchmark_names_keep_their_refusals(app: LocalApplication) -> None:
    revision = commit(app, CORPUS[CASE]())
    names = sorted(REGISTERED_POLICY_IDS - set(APPLICATION_POLICIES))
    assert len(names) == 7
    assert sorted(PRE_X06["refusals"]) == [*names, "no-such-policy"]
    for name, document in PRE_X06["refusals"].items():
        assert refused(lambda n=name: app.solve(revision, n)) == document, name
        if name != "no-such-policy":
            view = refused(lambda n=name: app.get_solve_policy(policy_id=n))
            assert view == document, name
    error = refused(lambda: app.solve(revision, "user.absent"))
    assert error["code"] == "not_found"
    assert error["detail"] == {"code": "solve_policy_not_found", "policy_id": "user.absent"}


def test_get_solve_policy_shows_an_offered_policy_as_its_runs_record_it(
    app: LocalApplication,
) -> None:
    for name, policy in APPLICATION_POLICIES.items():
        view = app.get_solve_policy(policy_id=name)
        assert (view.origin, view.policy_sha256) == ("builtin", policy_sha256(policy))
        assert dict(view.document) == policy.as_document()
    for name in ("default", "user.absent", "no-such-policy"):
        assert refused(lambda n=name: app.get_solve_policy(policy_id=n))["code"] == "not_found"


def test_a_damaged_registration_is_refused_at_admission(app: LocalApplication) -> None:
    app.register_solve_policy(policy=copy_of("user.bad"), idempotency_key="b")
    revision = commit(app, CORPUS[CASE]())
    row = app.store.artifact(artifact_id("user.bad"))
    assert row is not None
    (app.files_root / row.relpath).write_bytes(b"{}")
    assert refused(lambda: app.solve(revision, "user.bad"))["code"] == "internal_error"
    # An offered policy does not read the registrations.
    assert app.solve(revision, "T06-revision-v2").outcome == "CONVERGED"
