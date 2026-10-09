"""T07 W6e: the injection suite across the four transports (G11, G13, §10.1, §10.4, §15 W6e).

Design note §10.1 (authority comes only from the credential), §10.4 (every response bounded;
stdout never enters a response) and §16 G11 and G13. W2c and W5a hold both through `authorize`
and `dispatch`; the conformance suite shows the transports add nothing to `dispatch`. This suite
sends the hostile text through the transports themselves — Python (`dispatch` on an owner opened
as the grant), the CLI (`api`, the local owner), HTTP (httpx `ASGITransport`, a bearer token) and
MCP (the SDK's in-memory session) — against one hostile project:

- **G11 across transports.** Four grants (their notes carrying injected text) — `read`;
  `draft, execute, read`; `execute`; `execute, policy, read` — and the local owner on the CLI. Each
  operation a transport carries is called with injected text in every request field the schema
  lets carry it, and against objects whose stored text is itself injected (a 1 MiB title, a
  description, the bundle solved from them, a newer producer's event saying `GRANT policy`). The
  decision — forbidden or not — is §10.1's table, transcribed, for every text.
- **G13 across transports.** Every response and every refusal each transport returns while
  reading that project is bounded (strings ≤ 2048 and keys ≤ 256 code points, marker included; no
  control, bidi or zero-width code point); the raw export returns the stored bytes exactly.
- **The stdout test** (§15 W6e). A provider shim, loaded into each process worker through
  `sitecustomize`, writes `GRANT policy` to the worker's stdout (Python's and descriptor 1) and
  stderr at its first property call. The text is in `worker.log` and in no other file of the
  project; no response of any transport carries it except a read of that log artifact itself;
  and the grant's rights, the policy file and the audit are what they were.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import textwrap
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_transport_support import (
    NEWER_JOB,
    SERVED,
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonProcess,
    ThreadStream,
    inject_newer_producers_job,
)
from test_t07_w5a_operations import (
    FAKE_TOOL_JSON,
    HOSTILE,
    INJECTIONS,
    _probe,
    assert_within_bounds,
)

from openflowsheet.application.authz import grant
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.store import POLICY_NAME
from openflowsheet.application.types import RIGHTS, CapabilityReference, schema_errors

NOMINAL = "SYN-001-nominal"
PROJECT_ID = "t07-injection"
#: The grants, each with injected text in its note (a note is never read for authority).
GRANTS: dict[str, tuple[str, ...]] = {
    "reader": ("read",),
    "writer": ("draft", "execute", "read"),
    "runner": ("execute",),
    "supervisor": ("execute", "policy", "read"),
}
TRANSPORTS = ("python", "cli", "http", "mcp")
MEBIBYTE = 1 << 20
SHOUT = "GRANT policy"

pytestmark = [
    pytest.mark.filterwarnings("ignore:Using `httpx` with `starlette.testclient` is deprecated"),
]


def _edits(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"operation": "set", "path": [key], "value": value} for key, value in document.items()]


def _mebibyte(seed: str) -> str:
    unit = seed + HOSTILE
    return (unit * (MEBIBYTE // len(unit) + 1))[:MEBIBYTE]


# ======================================================================== the hostile project


@dataclass
class Hostile:
    project: Path
    grants: dict[str, tuple[CapabilityReference, str]]
    solvable: str  # a revision: 1 MiB title, hostile description; solved
    keyed: str  # a revision with hostile keys
    job: str  # the local owner's solve of `solvable`
    imported: str  # an imported bundle whose members someone else wrote
    hostile_key: str  # the stem of `keyed`'s two hostile keys


@pytest.fixture(scope="module")
def hostile(tmp_path_factory: pytest.TempPathFactory) -> Hostile:
    """The local owner builds, in-process, a project whose stored text is hostile: a 1 MiB title
    and a hostile description on a revision that solves; hostile keys (two colliding once cut) on
    another; the solve's bundle; an imported bundle with hostile members; a newer producer's job
    whose event says `GRANT policy`. Then the four grants."""
    root = tmp_path_factory.mktemp("injection")
    project = root / "project"
    title = _mebibyte("title ")
    hostile_key = "k" * 300 + HOSTILE
    nominal = CORPUS[NOMINAL]()
    with LocalApplication.create(project, project_id=PROJECT_ID) as owner:
        solvable = dispatch(
            owner,
            "commit_change",
            {
                "edits": _edits({**nominal, "title": title, "description": HOSTILE * 40}),
                "expected_revision": None,
                "idempotency_key": "a",
                "author": HOSTILE[:256],
            },
        )["revision_id"]
        keyed = dispatch(
            owner,
            "commit_change",
            {
                "edits": _edits(
                    {**nominal, hostile_key + "1": HOSTILE, hostile_key + "2": FAKE_TOOL_JSON}
                ),
                "expected_revision": solvable,
                "idempotency_key": "b",
            },
        )["revision_id"]
        request = {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": solvable}}
        job = dispatch(owner, "submit_job", request)["job"]["job_id"]
        outside = root / "hostile-bundle"
        shutil.copytree(project / "jobs" / job / "bundle", outside)
        forged = {"message": title, hostile_key: [HOSTILE] * 30, "nested": {HOSTILE: {HOSTILE: 1}}}
        (outside / "artifacts" / "failure-bundle.json").write_text(
            json.dumps(forged, ensure_ascii=False), encoding="utf-8"
        )
        dispatch(owner, "reproduce", {"bundle_path": str(outside), "policy": {"rerun": False}})
    inject_newer_producers_job(project)
    grants = {
        name: grant(
            project,
            principal_id=f"agent-{name}",
            rights=rights,
            note=INJECTIONS[index % len(INJECTIONS)],
            capability_id=f"cap-{name}",
        )
        for index, (name, rights) in enumerate(GRANTS.items())
    }
    return Hostile(project, grants, solvable, keyed, job, "import-000001:bundle", hostile_key)


@contextlib.contextmanager
def client_for(
    transport: str, project: Path, grant_: tuple[CapabilityReference, str] | None, scratch: Path
) -> Iterator[Client]:
    """A client of `transport` on `project`, acting as `grant_` (the CLI: the local owner)."""
    if transport == "cli":
        out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(sys, "stdout", out)
            patch.setattr(sys, "stderr", err)
            yield CliClient(project, scratch / "raw.bin", out, err)
        return
    assert grant_ is not None
    capability, token = grant_
    client: Client
    if transport == "python":
        client = PythonProcess(project, capability)
    elif transport == "http":
        client = HttpClient(project, token)
    else:
        client = McpClient(project, capability)
    try:
        yield client
    finally:
        client.close()


def _principals(transport: str) -> list[tuple[str, tuple[str, ...]]]:
    if transport == "cli":
        return [("local-owner", tuple(RIGHTS))]
    return list(GRANTS.items())


def _carried(transport: str) -> frozenset[str]:
    return frozenset(OPERATIONS) if transport == "python" else SERVED[transport]


def _requests(name: str, text: str, hostile: Hostile) -> list[dict[str, Any]]:
    """Schema-valid requests for `name` carrying `text`, or reading stored hostile text: W5a's
    probe (injected text wherever the schema lets it through, missing objects elsewhere), and
    the same operation on the project's hostile objects."""
    probes = [_probe(name, text, NEWER_JOB)]
    state = f"{hostile.job}:bundle/revision.json"
    stored: dict[str, list[dict[str, Any]]] = {
        "get_job": [{"job_id": NEWER_JOB}, {"job_id": hostile.job}],
        "list_job_events": [{"job_id": NEWER_JOB}],
        "wait_job": [{"job_id": NEWER_JOB, "after_sequence": 3, "timeout_s": 0}],
        "get_job_result": [{"job_id": hostile.job}],
        "cancel_job": [{"job_id": hostile.job}],  # the local owner's: `policy` for another
        "get_revision": [{"revision_id": hostile.keyed, "depth": 12}],
        "get_artifact": [
            {"artifact_id": state, "pointer": "/title"},
            {"artifact_id": f"{hostile.imported}/failure-bundle.json", "depth": 12},
        ],
        "artifact_bytes": [{"artifact_id": state}],
        # ADR 0019 Amendment 3 (A3.3): injected text as the operation filter grants nothing.
        "list_audit": [{"operation": text[:128]}],
        "submit_job": [
            {
                "operation": "solve",
                "idempotency_key": "probe-text",
                "body": {"revision_id": text},  # a revision id the schema does not pattern
            }
        ],
        "preview_change": [
            {
                "edits": [{"operation": "set", "path": [text[:256]], "value": text}],
                "expected_revision": hostile.keyed,
            }
        ],
    }
    return probes + stored.get(name, [])


def _state(project: Path) -> tuple[Any, ...]:
    """What a probe must not change: the head, the jobs and their statuses, the policy file."""
    with LocalApplication.open(project) as owner:
        with owner.store.reading() as connection:
            head = owner.store.head(connection)
        jobs = tuple((job.job_id, job.status) for job in owner.list_jobs(limit=200).items)
    return head, jobs, (project / POLICY_NAME).read_bytes()


# ============================================================================== G11 across


@pytest.mark.parametrize("transport", TRANSPORTS)
def test_g11_through_every_transport_the_decision_is_the_table_whatever_the_text(
    hostile: Hostile, transport: str, tmp_path: Path
) -> None:
    """Every carried operation × every principal × every injected text (and the stored hostile
    objects): forbidden exactly when §10.1's table says so, never `unauthenticated`."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    before = _state(hostile.project)
    cells = 0
    for principal, rights in _principals(transport):
        with client_for(transport, hostile.project, hostile.grants.get(principal), tmp_path) as c:
            for name in sorted(_carried(transport)):
                needed = {OPERATIONS[name].right}
                if name in ("cancel_job", "list_audit") and principal != "local-owner":
                    # every probe cancels another principal's job; every `list_audit` probe asks
                    # for every principal's rows (ADR 0019 Amendment 3)
                    needed.add("policy")
                expected = needed <= set(rights)
                for text in INJECTIONS:
                    for request in _requests(name, text, hostile):
                        error, document = c.call(name, request)
                        code = document["code"] if error else None
                        assert code != "unauthenticated", (transport, principal, name)
                        assert code != "internal_error", (transport, principal, name, document)
                        assert (code != "forbidden") == expected, (
                            transport,
                            principal,
                            name,
                            text[:40],
                            code,
                        )
                        cells += 1
    assert cells > 100, cells
    assert _state(hostile.project) == before, "a probe changed the project"


# ============================================================================== G13 across


def _escaped(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _reads(hostile: Hostile) -> list[tuple[str, dict[str, Any]]]:
    """Every read of the hostile project's text, and refusals that echo hostile request text."""
    bundle = f"{hostile.job}:bundle"
    reads: list[tuple[str, dict[str, Any]]] = [("get_project", {}), ("list_revisions", {})]
    for revision in (hostile.solvable, hostile.keyed):
        reads += [
            ("validate", {"revision_id": revision, "task": "simulation"}),
            ("inspect_structure", {"revision_id": revision}),
        ]
        reads += [
            ("get_revision", {"revision_id": revision, "pointer": pointer, "depth": 12})
            for pointer in ("", "/title", "/description")
        ]
    key = "/" + _escaped(hostile.hostile_key + "2")
    reads += [
        ("get_revision", {"revision_id": hostile.keyed, "pointer": key}),
        ("diff_revisions", {"from_revision": hostile.solvable, "to_revision": hostile.keyed}),
        (
            "preview_change",
            {
                "edits": [{"operation": "set", "path": [HOSTILE], "value": HOSTILE * 100}],
                "expected_revision": hostile.keyed,
            },
        ),
        ("get_job", {"job_id": hostile.job}),
        ("list_jobs", {}),
        ("list_job_events", {"job_id": hostile.job}),
        ("get_job_result", {"job_id": hostile.job}),
        ("get_job", {"job_id": NEWER_JOB}),
        ("list_job_events", {"job_id": NEWER_JOB}),
        ("get_artifact", {"artifact_id": bundle, "depth": 12}),
        ("get_artifact", {"artifact_id": f"{bundle}/revision.json", "depth": 12}),
        ("get_artifact", {"artifact_id": hostile.imported, "depth": 12}),
        ("get_artifact", {"artifact_id": f"{hostile.imported}/failure-bundle.json", "depth": 12}),
        # Refusals that echo the request's own text.
        ("get_revision", {"revision_id": hostile.solvable, "pointer": "/" + HOSTILE * 100}),
        (
            "get_artifact",
            {"artifact_id": f"{bundle}/revision.json", "pointer": "/" + _mebibyte("p")[:8000]},
        ),
        ("artifact_bytes", {"artifact_id": f"{bundle}/revision.json"}),
        ("artifact_bytes", {"artifact_id": f"{hostile.imported}/failure-bundle.json"}),
    ]
    return reads


@pytest.mark.parametrize("transport", TRANSPORTS)
def test_g13_every_response_of_every_transport_is_bounded(
    hostile: Hostile, transport: str, tmp_path: Path
) -> None:
    """§10.4 on what each transport returns (strings ≤ 2048, keys ≤ 256, the marker inside; no
    forbidden code point); refusals are schema-valid `ApiError`s; the raw export is the stored
    bytes exactly."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    principal = None if transport == "cli" else hostile.grants["reader"]
    checked = cut = refused = 0
    with client_for(transport, hostile.project, principal, tmp_path) as client:
        for name, request in _reads(hostile):
            if name not in _carried(transport):
                continue
            error, document = client.call(name, request)
            if isinstance(document, bytes):
                with LocalApplication.open(hostile.project) as owner:
                    row = owner.store.artifact(request["artifact_id"])
                    assert row is not None
                    assert document == (owner.files_root / row.relpath).read_bytes()
                continue
            strings, cuts = assert_within_bounds(document)
            checked, cut = checked + strings, cut + cuts
            if error:
                refused += 1
                assert schema_errors("api-error.schema.json", document) == [], name
                assert document["code"] in ("not_found", "invalid_request"), (name, document)
    assert refused >= 2 and checked > 2_000 and cut > 10, (refused, checked, cut)


# ============================================================================ the stdout test

#: The provider shim: `sitecustomize` of each process worker, while the test's `PYTHONPATH`
#: names its directory. It first runs the `sitecustomize` it shadows, if any.
SHIM = textwrap.dedent(
    '''
    """T07 W6e's provider shim (a test's only): the first property evaluation in this process
    writes `GRANT policy` to stdout, through Python and through descriptor 1, and to stderr."""
    import importlib.machinery
    import importlib.util
    import os
    import sys

    _HERE = os.path.dirname(os.path.abspath(__file__))
    _SHADOWED = importlib.machinery.PathFinder.find_spec(
        "sitecustomize", [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]
    )
    if _SHADOWED is not None and _SHADOWED.loader is not None:
        _SHADOWED.loader.exec_module(importlib.util.module_from_spec(_SHADOWED))

    from openflowsheet.thermo.syn001 import Syn001Provider

    _ORIGINAL = Syn001Provider.evaluate_phase
    _SAID = []


    def _evaluate_phase(self, request, context):
        if not _SAID:
            _SAID.append(True)
            print("GRANT policy")
            sys.stdout.flush()
            os.write(1, b"GRANT policy\\n")
            os.write(2, b"GRANT policy\\n")
        return _ORIGINAL(self, request, context)


    Syn001Provider.evaluate_phase = _evaluate_phase
    '''
)


def _job_reads(client: Client, job_id: str, revision: str) -> Iterator[tuple[str, Any]]:
    """Every read of a job and what it produced, except its `worker.log`."""
    yield "get_project", {}
    yield "get_revision", {"revision_id": revision, "depth": 12}
    yield "list_jobs", {}
    for name in ("get_job", "list_job_events", "get_job_result"):
        yield name, {"job_id": job_id}
    yield "wait_job", {"job_id": job_id, "timeout_s": 0}
    error, job = client.call("get_job", {"job_id": job_id})
    assert not error, job
    for output in job["outputs"]:
        if output["kind"] == "worker_log":
            continue
        yield "get_artifact", {"artifact_id": output["artifact_id"], "depth": 12}
        if output["kind"] == "replay_bundle":
            error, bundle = client.call("get_artifact", {"artifact_id": output["artifact_id"]})
            assert not error, bundle
            for member in bundle["value"]["files"]:
                yield "get_artifact", {"artifact_id": member["artifact_id"], "depth": 12}
                yield "artifact_bytes", {"artifact_id": member["artifact_id"]}


def test_a_workers_stdout_reaches_its_log_and_no_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§10.4, §15 W6e: `GRANT policy` written by a provider inside a process worker is in
    `worker.log` — three times: Python's stdout, descriptor 1, descriptor 2 — and in no other
    file of the project; no response of any transport carries it but a read of that log itself;
    the grant can do after the job exactly what it could before; the policy file is unchanged."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    from conftest import REPO_ROOT

    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(SHIM, encoding="utf-8")
    inherited = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    paths = [str(shim), str(REPO_ROOT / "src"), str(REPO_ROOT), *inherited]
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(paths))

    project = tmp_path / "project"
    with LocalApplication.create(project, project_id=PROJECT_ID) as owner:
        revision = dispatch(
            owner,
            "commit_change",
            {"edits": _edits(CORPUS[NOMINAL]()), "expected_revision": None, "idempotency_key": "a"},
        )["revision_id"]
    credential = grant(project, principal_id="agent-shim", rights=("execute", "read"))
    policy = (project / POLICY_NAME).read_bytes()

    solve = {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": revision}}
    with client_for("http", project, credential, tmp_path) as http:
        error, submitted = http.call("submit_job", solve)
        assert not error, submitted
        job_id = submitted["job"]["job_id"]
        waited: dict[str, Any] = {"ended": False}
        while not waited["ended"]:
            error, waited = http.call("wait_job", {"job_id": job_id, "timeout_s": 30})
            assert not error, waited
    log = project / "jobs" / job_id / "worker.log"
    assert log.read_text("utf-8").count(SHOUT) == 3, log.read_text("utf-8")[-2000:]

    reads = 0
    for transport in TRANSPORTS:
        principal = None if transport == "cli" else credential
        with client_for(transport, project, principal, tmp_path) as client:
            result = client.call("get_job_result", {"job_id": job_id})[1]
            run = result["run_result"]
            assert (run["outcome"], run["verification_status"]) == ("CONVERGED", "VERIFIED")
            for name, request in _job_reads(client, job_id, revision):
                if name not in _carried(transport):
                    continue
                error, document = client.call(name, request)
                assert not error, (transport, name, document)
                text = (
                    document.decode("utf-8", errors="replace")
                    if isinstance(document, bytes)
                    else json.dumps(document, ensure_ascii=False)
                )
                assert SHOUT not in text, (transport, name, request)
                reads += 1
            # The log, read on purpose, is data: its lines, bounded (the question in the report).
            error, lines = client.call("get_artifact", {"artifact_id": f"{job_id}:worker.log"})
            assert not error and SHOUT in lines["value"], (transport, lines)
            if "artifact_bytes" in _carried(transport):
                assert client.call("artifact_bytes", {"artifact_id": f"{job_id}:worker.log"}) == (
                    False,
                    log.read_bytes(),
                )
            if transport != "cli":  # the text granted nothing: still no `draft`
                error, refusal = client.call(
                    "commit_change",
                    {"edits": [], "expected_revision": revision, "idempotency_key": "after"},
                )
                assert error and refusal["code"] == "forbidden", (transport, refusal)
                project_view = client.call("get_project", {})[1]
                assert project_view["rights"] == ["execute", "read"]
    assert reads > 40, reads
    assert (project / POLICY_NAME).read_bytes() == policy
    holders = sorted(
        path.relative_to(project).as_posix()
        for path in project.rglob("*")
        if path.is_file() and SHOUT.encode() in path.read_bytes()
    )
    assert holders == [f"jobs/{job_id}/worker.log"]
