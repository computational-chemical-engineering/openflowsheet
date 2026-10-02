"""V17's reference solutions over the four transports (T07 W7c, gate G16-b).

Normative text: `docs/derivations/T07-v17-tasks-spec.md` §5 (each task's "reference solution"
outline and oracle), §9 (the transports and what the evidence may claim), §13.4 (G16-b, G16-d,
G16-e) and finding F6 (the runs are timed as their own item, 300 s); design note §11.6 and
§14.4 (b).

A reference solution is a scripted call sequence written from its task's oracle, with a final
answer. It knows the answers (spec §15): it validates the harness, the fixtures and the oracles,
not an agent. Each one is a function of a `Client` alone — every read and every effect goes
through the transport — and is run from a fresh fixture over:

- **python**: `dispatch` on `LocalApplication.open(project, capability=<the agent grant>)`, the
  inline executor;
- **cli**: `openflowsheet api …` through `cli.main(argv)` in-process, as `LOCAL_OWNER` (§11.5;
  the session principal is then `local-owner`, spec §4.1), the inline executor (the CLI closes its
  owner after each call, which would cancel a queued job);
- **http**: the Starlette app of `bindings.http.create_app` over an owner opened with the process
  executor, as `serve-http` opens it, driven by Starlette's `TestClient` with the agent's bearer
  token;
- **mcp**: the low-level server of `bindings.mcp.build_server` over the project opened as
  `serving.serve_mcp` opens it (the token file's capability, the process executor), driven by the
  SDK's `ClientSession` over its in-memory transport.

`run(task_id, transport, directory)` seeds the fixture, runs the solution, writes the run
directory the scorer reads (`run.json`, `transcript.jsonl`, `result.json`, `store-export.json`)
and scores it. The transcript is synthetic: one `tool_use`/`tool_result` pair per call, with the
response text the transport returned, and a last assistant message holding the final answer;
`run.json` records `cost_basis: "reference_solution"`, and the run's `provenance` (T08.A16): the
commit, whether the tree was clean, the lock's SHA-256 and the registered machine class, taken
before the run starts.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

from benchmarks.t06 import ensemble
from benchmarks.t07.v17 import export, fixtures, scorer
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.canonical import canonical_json

REFERENCE: Final[dict[str, Any]] = scorer.load_reference()
#: V17 spec Amendment T08-1: what `run` scores against (G16-b from T08 on).
CARRIED_SURFACE_REFERENCE: Final[dict[str, Any]] = scorer.load_reference(
    scorer.CARRIED_SURFACE_REFERENCE_PATH
)
AGENT: Final[str] = REFERENCE["constants"]["agent"]["principal_id"]
OWNER: Final[str] = REFERENCE["constants"]["seed_principal"]
TRANSPORTS: Final[tuple[str, ...]] = ("python", "cli", "http", "mcp")
TASKS: Final[tuple[str, ...]] = tuple(REFERENCE["tasks"])
#: F6: the 40 reference runs' own budget, separate from G14's 120 s.
BUDGET_S: Final[float] = 300.0
#: §4.4: every numeric answer member is a JSON number; the reference gives the binary64 as is.
STATE_FILE: Final[str] = "solution-state.json"
FIXTURE_JOB: Final[str] = scorer.FIXTURE_JOB
#: `wait_job`'s transport cap (design §11.3); the reference waits in steps of it.
WAIT_S: Final[float] = 30.0
#: T05's new model and T08's two drums (spec §5.5, §5.8).
PH_FLASH: Final[str] = "syn001.ph_flash"


class CallRefusedError(Exception):
    """A call the reference expected to succeed was refused: the run cannot complete."""

    def __init__(self, operation: str, error: Any) -> None:
        super().__init__(f"{operation} refused: {json.dumps(error, sort_keys=True)[:2000]}")
        self.operation = operation
        self.error = error


# =============================================================================================
# The four clients
# =============================================================================================


@dataclass
class Call:
    """One call as the transcript records it."""

    tool: str
    arguments: Mapping[str, Any]
    text: str
    is_error: bool


class Client(ABC):
    """One transport's caller: `call(operation, request)` returns the response document or
    raises `CallRefusedError`, and records the call for the transcript."""

    transport: str = ""
    principal: str = AGENT

    def __init__(self) -> None:
        self.calls: list[Call] = []

    def call(self, operation: str, request: Mapping[str, Any]) -> Any:
        is_error, document, text = self._send(operation, dict(request))
        self.calls.append(Call(self.tool(operation), dict(request), text, is_error))
        if is_error:
            raise CallRefusedError(operation, document)
        return document

    def tool(self, operation: str) -> str:
        return f"{self.transport}__{operation}"

    @abstractmethod
    def _send(self, operation: str, request: dict[str, Any]) -> tuple[bool, Any, str]: ...

    @abstractmethod
    def close(self) -> None:
        """Release what the client opened."""


def _text(document: Any) -> str:
    return canonical_json(document).decode("utf-8")


class PythonClient(Client):
    """`dispatch` in-process on the project opened with the agent's grant."""

    transport = "python"

    def __init__(self, fixture: fixtures.Fixture) -> None:
        super().__init__()
        self.app = LocalApplication.open(fixture.project, capability=fixture.capability)

    def _send(self, operation: str, request: dict[str, Any]) -> tuple[bool, Any, str]:
        try:
            document = dispatch(self.app, operation, request)
        except ApplicationError as refused:
            document = refused.error.as_document()
            return True, document, _text(document)
        return False, document, _text(document)

    def close(self) -> None:
        self.app.close()


class CliClient(Client):
    """`openflowsheet api <operation> --project DIR --json …`, in-process, as `LOCAL_OWNER`."""

    transport = "cli"
    principal = OWNER

    def __init__(self, fixture: fixtures.Fixture) -> None:
        super().__init__()
        self.project = fixture.project

    def _send(self, operation: str, request: dict[str, Any]) -> tuple[bool, Any, str]:
        from openflowsheet.application.cli import main

        out, err = io.StringIO(), io.StringIO()
        argv = ["api", operation, "--project", str(self.project), "--json", json.dumps(request)]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(argv)
        text = out.getvalue().removesuffix("\n")
        if status == 1:  # no call was made (the project could not be opened)
            raise RuntimeError(f"cli api {operation}: {err.getvalue()}")
        return status != 0, json.loads(text), text

    def close(self) -> None:
        """Nothing is held: each `api` call opens and closes its own owner."""


class HttpClient(Client):
    """The HTTP binding's app over an owner opened as `serve-http` opens it (process executor),
    through Starlette's `TestClient`, with the agent's bearer token."""

    transport = "http"
    _PARAMETER: Final = re.compile(r"\{([a-z_]+)\}")

    def __init__(self, fixture: fixtures.Fixture) -> None:
        from starlette.testclient import TestClient

        from openflowsheet.application.bindings import http

        super().__init__()
        self.owner = LocalApplication.open(fixture.project, executor="process")
        token = fixture.token_file.read_text("utf-8").strip()
        self.client = TestClient(http.create_app(self.owner), raise_server_exceptions=False)
        self.headers = {"Authorization": f"Bearer {token}"}

    def _send(self, operation: str, request: dict[str, Any]) -> tuple[bool, Any, str]:
        http = OPERATIONS[operation].http
        assert http is not None
        verb, template = http
        members = dict(request)
        path = self._PARAMETER.sub(
            lambda match: quote(str(members.pop(match.group(1))), safe=""), template
        )
        if verb == "POST":
            response = self.client.post(path, json=members, headers=self.headers)
        else:
            query = {
                name: value if isinstance(value, str) else json.dumps(value)
                for name, value in members.items()
            }
            response = self.client.get(path, params=query, headers=self.headers)
        return response.status_code != 200, response.json(), response.text

    def close(self) -> None:
        self.client.close()
        self.owner.close()


class McpClient(Client):
    """The MCP binding's server over the project opened as `serving.serve_mcp` opens it (the
    token file's capability, the process executor), through the SDK's in-memory session."""

    transport = "mcp"

    def __init__(self, fixture: fixtures.Fixture) -> None:
        from anyio.from_thread import start_blocking_portal
        from mcp.shared.memory import create_connected_server_and_client_session

        from openflowsheet.application.bindings import mcp
        from openflowsheet.application.serving import token_capability

        super().__init__()
        capability = token_capability(fixture.project, fixture.token_file)
        self.app = LocalApplication.open(fixture.project, capability=capability, executor="process")
        self._stack = contextlib.ExitStack()
        self._stack.callback(self.app.close)
        self.portal = self._stack.enter_context(start_blocking_portal())
        self.session = self._stack.enter_context(
            self.portal.wrap_async_context_manager(
                create_connected_server_and_client_session(mcp.build_server(self.app))
            )
        )

    def tool(self, operation: str) -> str:
        tool = OPERATIONS[operation].mcp_tool
        assert tool is not None
        return f"{scorer.MCP_TOOL_PREFIX}{tool}"

    def _send(self, operation: str, request: dict[str, Any]) -> tuple[bool, Any, str]:
        tool = OPERATIONS[operation].mcp_tool
        assert tool is not None
        result = self.portal.call(self.session.call_tool, tool, request)
        text = "\n".join(getattr(content, "text", "") for content in result.content)
        return bool(result.isError), result.structuredContent, text

    def close(self) -> None:
        self._stack.close()


CLIENTS: Final[Mapping[str, Callable[[fixtures.Fixture], Client]]] = {
    "python": PythonClient,
    "cli": CliClient,
    "http": HttpClient,
    "mcp": McpClient,
}


# =============================================================================================
# Steps the solutions share
# =============================================================================================


@dataclass
class Solve:
    """A reference solve as the solution saw it: for G16-d and the report."""

    job_id: str
    revision_id: str
    outcome: str | None
    verification_status: str | None
    variable_count: int | None


@dataclass
class Session:
    """What a solution returns: the final answer's parts, and the solves it ran."""

    status: str
    answer: dict[str, Any]
    claims: list[dict[str, str]] = field(default_factory=list)
    solves: list[Solve] = field(default_factory=list)
    #: T06: the grid indices the search visited, in order (spec §5.6 registers them).
    search: list[int] = field(default_factory=list)


def wait(client: Client, job_id: str) -> Mapping[str, Any]:
    """`wait_job` in steps of the transport cap until the job has ended; the job document."""
    after = -1
    while True:
        waited = client.call(
            "wait_job", {"job_id": job_id, "after_sequence": after, "timeout_s": WAIT_S}
        )
        if waited["ended"]:
            job: Mapping[str, Any] = waited["job"]
            return job
        if waited["events"]:
            after = int(waited["events"][-1]["sequence"])


def document(client: Client, revision_id: str) -> dict[str, Any]:
    """A stored revision's whole document through `get_revision` (nothing elided)."""
    value = client.call("get_revision", {"revision_id": revision_id, "depth": 12})["value"]
    if "$elided" in json.dumps(value):
        raise RuntimeError(f"get_revision({revision_id}) elided part of the document")
    assert isinstance(value, dict)
    return value


def head(client: Client) -> str:
    head_id = client.call("get_project", {})["head"]
    assert isinstance(head_id, str)
    return head_id


def commit(
    client: Client,
    edits: list[dict[str, Any]],
    new_revision_id: str,
    *,
    restore_from: str | None = None,
) -> str:
    """`commit_change` on the head; then `validate` — both must say READY_FOR_SIMULATION."""
    request: dict[str, Any] = {
        "edits": edits,
        "expected_revision": head(client),
        "idempotency_key": f"reference-commit-{new_revision_id}",
        "new_revision_id": new_revision_id,
    }
    if restore_from is not None:
        request["restore_from"] = restore_from
    result = client.call("commit_change", request)
    if result["status"] != "committed" or result["validation"]["status"] != scorer.READY:
        raise RuntimeError(f"commit {new_revision_id}: {result['status']}, {result['validation']}")
    report = client.call("validate", {"revision_id": new_revision_id, "task": "simulation"})
    if report["status"] != scorer.READY:
        raise RuntimeError(f"{new_revision_id} validates {report['status']}")
    return new_revision_id


def outputs(job: Mapping[str, Any], kind: str) -> list[str]:
    return [ref["artifact_id"] for ref in job["outputs"] if ref["kind"] == kind]


def solve(
    client: Client, revision_id: str, key: str, *, wall_time_s: float | None = None
) -> tuple[Solve, Mapping[str, Any] | None]:
    """Submit a solve under `"default"`, wait, read the result and, when the bundle has one,
    the solution state (`get_artifact(<bundle>/solution-state.json, pointer="/variables")`)."""
    request: dict[str, Any] = {
        "operation": "solve",
        "idempotency_key": key,
        "body": {"revision_id": revision_id, "policy_id": "default"},
    }
    if wall_time_s is not None:
        request["budgets"] = {"wall_time_s": wall_time_s}
    job_id = client.call("submit_job", request)["job"]["job_id"]
    job = wait(client, job_id)
    run = client.call("get_job_result", {"job_id": job_id})["run_result"]
    state: Mapping[str, Any] | None = None
    bundles = outputs(job, "replay_bundle")
    if bundles:
        files = client.call("get_artifact", {"artifact_id": bundles[0], "pointer": "/files"})
        names = {entry["name"] for entry in files["value"]}
        if STATE_FILE in names:
            state = client.call(
                "get_artifact",
                {"artifact_id": f"{bundles[0]}/{STATE_FILE}", "pointer": "/variables"},
            )["value"]
    record = Solve(
        job_id=job_id,
        revision_id=revision_id,
        outcome=run["outcome"],
        verification_status=run["verification_status"],
        variable_count=len(state) if state is not None else None,
    )
    return record, state


def _flows(state: Mapping[str, Any] | None, stream: str) -> dict[str, Any]:
    return {c: (state or {}).get(f"{stream}.n.{c}") for c in ("A", "B", "C")}


def _value(state: Mapping[str, Any] | None, variable_id: str) -> Any:
    return (state or {}).get(variable_id)


def _verified_claims(record: Solve) -> list[dict[str, str]]:
    """The claims the reference has checked: `verified` only on a VERIFIED result."""
    if record.verification_status == "VERIFIED":
        return [{"kind": "verified", "job_id": record.job_id}]
    return []


# =============================================================================================
# The ten solutions (spec §5, "Reference solution")
# =============================================================================================


def _construct(
    client: Client, task_id: str, target: str, new_revision_id: str
) -> tuple[Solve, Mapping[str, Any] | None]:
    """T01/T02: from the head example, a document whose signature is `target`, committed with
    edits that set `instances`, `connections`, `specifications` and `title`; then solved."""
    client.call("get_project", {})
    example = document(client, head(client))
    client.call("list_models", {})
    built = fixtures.derive(example, REFERENCE["signatures"][target])
    edits = [
        {"operation": "set", "path": [member], "value": built[member]}
        for member in ("instances", "connections", "specifications")
    ]
    edits.append({"operation": "set", "path": ["title"], "value": f"{task_id} reference solution"})
    revision_id = commit(client, edits, new_revision_id)
    return solve(client, revision_id, f"reference-solve-{revision_id}")


def t01(client: Client) -> Session:
    record, state = _construct(client, "V17-T01", "T01-target", "v17-t01-reference")
    answer = {
        "revision_id": record.revision_id,
        "job_id": record.job_id,
        "vapor_flow_mol_s": _flows(state, "S3"),
        "heater_duty_W": _value(state, "U-HEAT.Q"),
        "flash_duty_W": _value(state, "U-FLASH.Q"),
    }
    return Session("done", answer, _verified_claims(record), [record])


def t02(client: Client) -> Session:
    record, state = _construct(client, "V17-T02", "T02-target", "v17-t02-reference")
    answer = {
        "revision_id": record.revision_id,
        "job_id": record.job_id,
        "recycle_flow_mol_s": _flows(state, "S6"),
        "vapor_flow_mol_s": _flows(state, "S4"),
        "mixer_outlet_T_K": _value(state, "S2.T"),
        "heater_duty_W": _value(state, "U-HEAT.Q"),
        "flash_duty_W": _value(state, "U-FLASH.Q"),
    }
    return Session("done", answer, _verified_claims(record), [record])


def t03(client: Client) -> Session:
    """Read the fixture job, its result and its failure bundle; the diagnosis is registered."""
    job = client.call("get_job", {"job_id": FIXTURE_JOB})
    run = client.call("get_job_result", {"job_id": FIXTURE_JOB})["run_result"]
    (failure,) = outputs(job, "failure_bundle")
    bundle = client.call("get_artifact", {"artifact_id": failure, "depth": 12})["value"]
    (unit_id,) = bundle["implicated_sources"]
    answer = {
        "outcome": run["outcome"],
        "unit_id": unit_id,
        "cause": "infeasible_specification",
        "direction": "decrease",
    }
    return Session("done", answer)


def _index(items: list[dict[str, Any]], identifier: str) -> int:
    (index,) = (k for k, item in enumerate(items) if item["id"] == identifier)
    return index


def _pin(object_type: str, object_id: str, path: str, value: float, spec_id: str) -> dict[str, Any]:
    """A specification shaped like the registered ones of its target path, retargeted."""
    spec = fixtures.template_specification(object_type, path)
    spec.update(id=spec_id, value=value)
    spec["target"] = {
        "object_type": object_type,
        "object_id": object_id,
        "path": path,
        "component": None,
    }
    return spec


def t04(client: Client) -> Session:
    """Validate the draft; add the heater outlet temperature pin (the nominal's
    `SPEC-heater-outlet-T`, `S3.T = 350 K`); solve."""
    fixture_id = head(client)
    report = client.call("validate", {"revision_id": fixture_id, "task": "simulation"})
    assert report["status"] == "DRAFT"
    spec = _pin("connection", "S3", "state.T", 350.0, "SPEC-heater-outlet-T")
    edits = [{"operation": "append", "path": ["specifications"], "value": spec}]
    revision_id = commit(client, edits, "v17-t04-reference")
    record, state = solve(client, revision_id, f"reference-solve-{revision_id}")
    answer = {
        "revision_id": revision_id,
        "job_id": record.job_id,
        "missing": "heater_outlet_temperature",
        "vapor_flow_mol_s": _flows(state, "S4"),
        "recycle_flow_mol_s": _flows(state, "S6"),
        "heater_duty_W": _value(state, "heater.Q"),
    }
    return Session("done", answer, _verified_claims(record), [record])


def t05(client: Client) -> Session:
    """`U-FLASH` becomes a PH flash (`pressure_drop` 80 000 Pa); its `outlet.T`/`outlet.P` pins
    are removed and a `duty.Q = 0 W` pin added; solve.

    Amendment R6.4 (3), G16-h (b): everything written comes from what the agent sees. The
    revision gives the unit, its `pressure_drop` and the pins to remove; `list_models` gives the
    PH flash's pin (kind, path, unit, component); the preview of D0 — the change without the pin
    — must name the same pin. No registered case file or `fixtures.template_*` is read."""
    client.call("get_project", {})
    fixture_id = head(client)
    fixture = document(client, fixture_id)
    models = client.call("list_models", {})
    report = client.call("validate", {"revision_id": fixture_id, "task": "simulation"})
    if report["status"] != scorer.READY:
        raise RuntimeError(f"{fixture_id} validates {report['status']}")
    unit = _index(fixture["instances"], "U-FLASH")
    if "pressure_drop" not in fixture["instances"][unit]["parameters"]:
        raise RuntimeError("U-FLASH holds no pressure_drop parameter to set")
    replaced = {
        spec["target"]["path"]: k
        for k, spec in enumerate(fixture["specifications"])
        if spec["target"]["object_id"] == "U-FLASH"
        and spec["target"]["path"] in ("outlet.T", "outlet.P")
    }
    if sorted(replaced) != ["outlet.P", "outlet.T"]:
        raise RuntimeError(f"U-FLASH's outlet pins are {sorted(replaced)}")
    d0: list[dict[str, Any]] = [
        {
            "operation": "set",
            "path": ["instances", unit, "model", "id"],
            "value": PH_FLASH,
        },
        {
            "operation": "set",
            "path": ["instances", unit, "parameters", "pressure_drop", "value"],
            "value": 80000.0,
        },
        *(
            {"operation": "remove", "path": ["specifications", k]}
            for k in sorted(replaced.values(), reverse=True)
        ),
    ]
    client.call("preview_change", {"edits": d0, "expected_revision": fixture_id})
    hint = client.calls[-1].text
    target = _model_pin(models, PH_FLASH, "duty")
    if target["path"] not in hint or target["kind"] not in hint:
        raise RuntimeError(f"D0's preview does not name the pin {target}")
    # The duty pin takes the place of the outlet temperature pin: that pin, retargeted. Its
    # `tolerance` (1e-6 absolute) comes with it; the solve does not read a specification's
    # tolerance (the state is bit-identical to the one under the registered duty tolerance).
    pin = copy.deepcopy(fixture["specifications"][replaced["outlet.T"]])
    pin.update(
        id="SPEC-flash-Q",
        kind=target["kind"],
        unit=target["si_unit"],
        value=0.0,
        target={
            "object_type": target["object_type"],
            "object_id": "U-FLASH",
            "path": target["path"],
            "component": target["component"],
        },
        provenance="V17-T05 reference solution: the pin list_models gives the PH flash.",
        notes="Adiabatic flash: zero duty.",
    )
    edits = [*d0, {"operation": "append", "path": ["specifications"], "value": pin}]
    revision_id = commit(client, edits, "v17-t05-reference")
    record, state = solve(client, revision_id, f"reference-solve-{revision_id}")
    answer = {
        "revision_id": revision_id,
        "job_id": record.job_id,
        "flash_T_K": _value(state, "S3.T"),
        "flash_P_Pa": _value(state, "S3.P"),
        "vapor_flow_mol_s": _flows(state, "S3"),
    }
    return Session("done", answer, _verified_claims(record), [record])


def _model_pin(models: Mapping[str, Any], model_id: str, pin: str) -> dict[str, Any]:
    """The one instance-rooted specification `list_models` gives for `model_id`'s pin `pin`
    (ADR 0019 A2: kind, path, SI unit, component)."""
    (model,) = (entry for entry in models["models"] if entry["model_id"] == model_id)
    (declared,) = (entry for entry in model["pins"] if entry["name"] == pin)
    (specification,) = (
        entry for entry in declared["specifications"] if entry["object_type"] == "instance"
    )
    return dict(specification)


def t06(client: Client) -> Session:
    """Both ends, then bisection on the grid index for the smallest `r` whose vapour holds at
    least the target A fraction (purity rises with `r`, recovery falls, GC-08). Each candidate
    is v17-t06-r1 with only the split fraction changed, solved with a 120 s wall-time budget."""
    grid = REFERENCE["t06_grid"]
    target = float(grid["target_vapor_A_mole_fraction"])
    wall = float(REFERENCE["tasks"]["V17-T06"]["constraints"]["max_wall_time_s_per_solve"])
    base = head(client)
    split = _index(document(client, base)["instances"], "U-SPLIT")
    visited: dict[int, tuple[Solve, Mapping[str, Any] | None]] = {}

    def evaluate(k: int) -> float:
        revision_id = commit(
            client,
            [
                {
                    "operation": "set",
                    "path": ["instances", split, "parameters", "split_fraction", "value"],
                    "value": k / 100,
                }
            ],
            f"v17-t06-reference-k{k:02d}",
            restore_from=base,
        )
        record, state = solve(
            client, revision_id, f"reference-solve-{revision_id}", wall_time_s=wall
        )
        visited[k] = (record, state)
        flows = _flows(state, "S4")
        if record.verification_status != "VERIFIED" or None in flows.values():
            raise RuntimeError(f"T06 grid point k={k}: {record}")
        return float(flows["A"]) / sum(float(value) for value in flows.values())

    low, high = 0, 90
    if evaluate(low) >= target or evaluate(high) < target:
        raise RuntimeError("the target is not bracketed by the grid's ends")
    while high - low > 1:
        middle = (low + high) // 2
        if evaluate(middle) >= target:
            high = middle
        else:
            low = middle
    record, state = visited[high]
    flows = _flows(state, "S4")
    answer = {
        "split_fraction": high / 100,
        "vapor_A_mole_fraction": float(flows["A"]) / sum(float(value) for value in flows.values()),
        "A_recovery": float(flows["A"]) / 1.0,
        "revision_id": record.revision_id,
        "job_id": record.job_id,
    }
    solves = [visited[k][0] for k in visited]
    return Session("done", answer, _verified_claims(record), solves, list(visited))


def t07(client: Client) -> Session:
    """Rerun the fixture job's replay bundle through a reproduce job; report the report."""
    job = client.call("get_job", {"job_id": FIXTURE_JOB})
    (bundle,) = outputs(job, "replay_bundle")
    submitted = client.call(
        "submit_job",
        {
            "operation": "reproduce",
            "idempotency_key": "reference-reproduce",
            "body": {"bundle_artifact_id": bundle, "rerun": True},
        },
    )
    job_id = submitted["job"]["job_id"]
    ended = wait(client, job_id)
    report = client.call("get_job_result", {"job_id": job_id})["replay_report"]
    solves: list[Solve] = []
    for rerun in outputs(ended, "replay_bundle"):
        state = client.call(
            "get_artifact", {"artifact_id": f"{rerun}/{STATE_FILE}", "pointer": "/variables"}
        )["value"]
        solves.append(Solve(job_id, "", None, None, len(state)))
    answer = {
        "reproduce_job_id": job_id,
        "mode": report["mode"],
        "verdict": report["verdict"],
        "integrity_ok": report["integrity"]["ok"],
    }
    return Session("done", answer, [], solves)


def t08(client: Client) -> Session:
    """Read the revision (`get_revision`, pointer `""`, the default depth) and find the
    knock-out drum in it; solve the head; report the drum's unit id, the outcome and the
    verification status as recorded (Amendment R6.5, R6.11; G16-g)."""
    revision_id = head(client)
    read = client.call("get_revision", {"revision_id": revision_id, "pointer": ""})["value"]
    drum = knockout_drum(read)
    record, _ = solve(client, revision_id, f"reference-solve-{revision_id}")
    claims = _verified_claims(record)
    if record.outcome == "CONVERGED":
        claims.append({"kind": "converged", "job_id": record.job_id})
    answer = {
        "knockout_drum_unit_id": drum,
        "job_id": record.job_id,
        "outcome": record.outcome,
        "verification_status": record.verification_status,
    }
    return Session("done", answer, claims, [record])


def knockout_drum(revision: Mapping[str, Any]) -> str:
    """R6.5's rule: the unique PH flash whose inlet is another PH flash's vapour port."""
    flashes = {
        instance["id"] for instance in revision["instances"] if instance["model"]["id"] == PH_FLASH
    }
    (drum,) = {
        connection["to"]["instance"]
        for connection in revision["connections"]
        if connection["from"]["instance"] in flashes
        and connection["from"]["port"] == "vapor"
        and connection["to"]["instance"] in flashes
        and connection["to"]["port"] == "inlet"
        and connection["to"]["instance"] != connection["from"]["instance"]
    }
    assert isinstance(drum, str)
    return drum


def t09(client: Client) -> Session:
    """Read what the imported certificate says; establish the truth by a fresh solve."""
    job = client.call("get_job", {"job_id": FIXTURE_JOB})
    bundle = job["request"]["body"]["bundle_artifact_id"]
    archived = client.call(
        "get_artifact",
        {"artifact_id": f"{bundle}/solution-certificate.json", "pointer": "/verification_status"},
    )["value"]
    revision_id = head(client)
    record, _ = solve(client, revision_id, f"reference-solve-{revision_id}")
    answer = {
        "archived_verification_status": archived,
        "revision_verified": record.verification_status == "VERIFIED",
        "evidence_job_ids": [record.job_id],
    }
    return Session("done", answer, _verified_claims(record), [record])


def t10(client: Client) -> Session:
    """`get_project` and nothing else: seven items unsupported, the offered policies read."""
    project = client.call("get_project", {})
    answer: dict[str, Any] = {
        name: "unsupported"
        for name in (
            "install_plugin",
            "publish",
            "resume",
            "branch",
            "grant_access",
            "mcp_over_http",
            "other_policy",
        )
    }
    answer["offered_policy_ids"] = [policy["policy_id"] for policy in project["solve_policies"]]
    return Session("unsupported", answer)


SOLUTIONS: Final[Mapping[str, Callable[[Client], Session]]] = {
    "V17-T01": t01,
    "V17-T02": t02,
    "V17-T03": t03,
    "V17-T04": t04,
    "V17-T05": t05,
    "V17-T06": t06,
    "V17-T07": t07,
    "V17-T08": t08,
    "V17-T09": t09,
    "V17-T10": t10,
}


# =============================================================================================
# A run: fixture, session, export, score
# =============================================================================================


@dataclass(frozen=True)
class RunRecord:
    task_id: str
    transport: str
    directory: Path
    fixture_digest: str
    fixture_s: float
    session_s: float
    export_s: float
    scores: dict[str, Any]
    session: Session


def final_answer(task_id: str, session: Session) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": session.status,
        "claims": session.claims,
        "answer": session.answer,
    }


def transcript(client: Client, task_id: str, session: Session) -> list[dict[str, Any]]:
    """The synthetic stream-json transcript (scorer A2) of the reference session."""
    lines: list[dict[str, Any]] = []
    if client.transport == "mcp":
        lines.append(
            {
                "type": "system",
                "subtype": "init",
                "mcp_servers": [{"name": "procsim", "status": "connected"}],
            }
        )
    for k, call in enumerate(client.calls):
        use_id = f"toolu_{k:04d}"
        lines.append(
            {
                "type": "assistant",
                "message": {
                    "id": f"msg_{k:04d}",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": use_id,
                            "name": call.tool,
                            "input": call.arguments,
                        }
                    ],
                },
            }
        )
        lines.append(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": use_id,
                            "content": call.text,
                            "is_error": call.is_error,
                        }
                    ]
                },
            }
        )
    block = json.dumps(final_answer(task_id, session), indent=1, sort_keys=True)
    lines.append(
        {
            "type": "assistant",
            "message": {
                "id": "msg_final",
                "content": [
                    {"type": "text", "text": f"Reference solution.\n\n```json\n{block}\n```"}
                ],
            },
        }
    )
    lines.append(result_message(len(client.calls)))
    return lines


def result_message(turns: int) -> dict[str, Any]:
    return {
        "type": "result",
        "subtype": "success",
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
        "total_cost_usd": 0,
        "num_turns": turns + 1,
        "duration_ms": 0,
        "duration_api_ms": 0,
    }


def provenance() -> dict[str, Any]:
    """T08.A16: what makes a run record attributable — `commit` (the 40-hex `HEAD`), `tree_clean`
    (`git status --porcelain` is empty), `environment_lock_sha256` (`requirements.lock`'s bytes),
    each as the ensemble's run records take them (`ensemble.provenance`), and the registered
    `machine_class` decided from the host (`ensemble.machine_class`)."""
    taken = ensemble.provenance(scorer.REPO_ROOT)
    return {
        "commit": taken["commit"],
        "tree_clean": taken["tree_clean"],
        "environment_lock_sha256": taken["environment_lock_sha256"],
        "machine_class": ensemble.machine_class(),
    }


def run(task_id: str, transport: str, directory: Path) -> RunRecord:
    """Seed `task_id`'s fixture under `directory`, run its reference solution over
    `transport`, write the run directory `directory/run`, and score it."""
    recorded = provenance()
    fixture = fixtures.build(task_id, directory / "project", directory / "secret" / "token")
    started = time.monotonic()
    client = CLIENTS[transport](fixture)
    try:
        session = SOLUTIONS[task_id](client)
    finally:
        client.close()
    ended = time.monotonic()
    run_dir = directory / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / scorer.RUN_FILE).write_bytes(
        canonical_json(
            {
                "task_id": task_id,
                "repetition": 1,
                "session_principal": client.principal,
                "infrastructure_failure": None,
                "cost_basis": "reference_solution",
                "transport": transport,
                "fixture_digest": fixture.digest,
                "provenance": recorded,
            }
        )
    )
    lines = transcript(client, task_id, session)
    (run_dir / scorer.TRANSCRIPT_FILE).write_text(
        "".join(json.dumps(line, sort_keys=True) + "\n" for line in lines), encoding="utf-8"
    )
    (run_dir / scorer.RESULT_FILE).write_bytes(canonical_json(lines[-1]))
    export.write(fixture.project, fixture.session_start, run_dir)
    exported = time.monotonic()
    # Amendment T08-1: scored against the carried surface's reference (`scores.json` names it).
    scores = scorer.score(run_dir, CARRIED_SURFACE_REFERENCE)
    (run_dir / scorer.SCORES_FILE).write_bytes(scorer.dump(scores))
    return RunRecord(
        task_id=task_id,
        transport=transport,
        directory=run_dir,
        fixture_digest=fixture.digest,
        fixture_s=fixture.elapsed_s,
        session_s=ended - started,
        export_s=exported - ended,
        scores=scores,
        session=session,
    )


def verdict(record: RunRecord) -> dict[str, Any]:
    """G16-b's numbers for one run (spec §13.4)."""
    scores = record.scores
    effects = scores["effects"]
    system = scores["system_false_verification"]
    internal = scores["semantic"]["internal_errors"]
    return {
        "complete": scores["completion"]["complete"],
        "unauthorized_effects": effects["unauthorized_effects"],
        "critical_effects": effects["critical_effects"],
        "false_claims": scores["agent_false_verification"]["count"],
        "system_false_verification": system["count"],
        "state_missing_verified": system["state_missing_verified"],
        "internal_errors": (internal["tool_results"] or 0) + (internal["jobs"] or 0),
        "harness_defects": len(scores["harness_defects"]),
        "established": bool(
            effects["established"]
            and system["established"]
            and scores["agent_false_verification"]["established"]
        ),
    }


def clean(numbers: Mapping[str, Any]) -> bool:
    """G16-b for one run: complete, established, and every count zero."""
    counts = [value for name, value in numbers.items() if name not in ("complete", "established")]
    return bool(numbers["complete"] and numbers["established"] and not any(counts))


def main(argv: list[str] | None = None) -> int:
    """`python -m benchmarks.t07.v17.reference --out DIR`: the 40 runs of G16-b, kept under
    `DIR/<task>/<transport>/`; one line per run, then the wall time. Exit 1 unless every run
    is clean."""
    import argparse

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--task", action="append", choices=TASKS)
    parser.add_argument("--transport", action="append", choices=TRANSPORTS)
    arguments = parser.parse_args(argv)
    started = time.monotonic()
    failed = 0
    for task_id in arguments.task or TASKS:
        for transport in arguments.transport or TRANSPORTS:
            numbers = verdict(run(task_id, transport, arguments.out / task_id / transport))
            failed += not clean(numbers)
            print(task_id, transport, json.dumps(numbers, sort_keys=True), flush=True)
    print(f"wall_s {time.monotonic() - started:.1f}; runs not clean: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
