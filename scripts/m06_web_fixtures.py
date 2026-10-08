"""M06 WO-7 (design note §8 "Fixtures"): the W26 fixture project and the server's answers to it.

`build_fixture_project(path)` builds a directory project through the contract with the inline
executor: grants `agent-a` (read, draft, execute), `viewer-b` (read) and `supervisor-c` (read,
policy); as `agent-a` commits `SYN-001-T06-NET02` (rev-000001) and solves it with `default`
(job-000001); commits the same with `instances[U-SPLIT].parameters.split_fraction.value`
0.95 -> 0.90 (rev-000002) and solves it (job-000002); commits `SYN-001-conflicting-heater-spec`
(rev-000003, INVALID); commits `SYN-001-A02-352-vapor-guess-410` (rev-000004) and solves it
(job-000003, HOMOTOPY_STALLED); commits NET-02 with a title and a description carrying markup and
U+202E (rev-000005). As `viewer-b` it then asks `submit_job` and `list_audit` for all
principals; both are refused (`forbidden`) and audited. The browser smoke test (WO-11) imports
it.

`capture(project)` then asks, through `operations.dispatch` as the right caller, every request
the screens of §6 make on that project — the projected documents (revisions, structure, bundle
listings) reassembled view by view exactly as `api.readWhole` asks for them (§5.4), each view
recorded — and reads the raw bytes of every bundle member. The Node tests answer the shell's
`api.js` from these records through a fake transport (`tests/web/fixture-transport.mjs`), so
what a screen's `load` asks is held to what the server answered. Answers that depend on the
caller (`get_project`, `list_audit`, the build's own `submit_job` requests and refusals) are
recorded per principal; every other answer once, as `agent-a`. Nothing captured is an effect or
a refusal, so the project's audit rows are exactly the build's.

These are regression fixtures, not validation (CLAUDE.md): every record is a real server
response, never written by hand, and `tests/test_m06_fixtures_valid.py` holds each one to its
operation's response schema and each bundle member to its record schema. Timestamps and elapsed
times are not normalised, so a rewrite differs; it is written once (`--write`) and committed.

Usage: `python scripts/m06_web_fixtures.py --write [--out DIR]`.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

from openflowsheet.application.authz import grant
from openflowsheet.application.bindings.http import HTTP_OPERATIONS
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import CapabilityReference

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
TARGET: Final[Path] = ROOT / "tests" / "web" / "fixtures" / "w26"
GENERATOR: Final[str] = "scripts/m06_web_fixtures.py"
PROJECT_ID: Final[str] = "m06-web-fixtures"

NET02: Final[Path] = ROOT / "benchmarks" / "t06" / "cases" / "SYN-001-T06-NET02.yaml"
STR03: Final[Path] = (
    ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-conflicting-heater-spec.yaml"
)
A02_352: Final[Path] = (
    ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-A02-352-vapor-guess-410.yaml"
)
#: §8: rev-000005's title and description — markup, then U+202E (RIGHT-TO-LEFT OVERRIDE), then text.
HOSTILE_TITLE: Final[str] = "<img src=x onerror=alert(1)>‮evil"
HOSTILE_DESCRIPTION: Final[str] = "<script>alert(2)</script>‮evil description"

#: §5.4: the views `api.readWhole` asks for (`VIEW_DEPTH`, `VIEW_LIMIT` of `js/api.js`).
VIEW_DEPTH: Final[int] = 12
VIEW_LIMIT: Final[int] = 200
ELIDED: Final[str] = "$elided"
#: The page sizes the screens ask for (`PAGE` of `js/screens/common.js`, M06 WO-9).
REVISION_PAGE: Final[int] = 200
PROJECT_JOB_PAGE: Final[int] = 50
JOB_PAGE: Final[int] = 200
EVENT_PAGE: Final[int] = 500
AUDIT_PAGE: Final[int] = 200
#: Operations whose answer depends on the caller: recorded per principal.
PER_PRINCIPAL: Final[frozenset[str]] = frozenset({"get_project", "list_audit"})
PRINCIPALS: Final[tuple[str, ...]] = ("agent-a", "viewer-b", "supervisor-c")


@dataclass
class FixtureProject:
    """The built project: its directory, each principal's capability and token, and the ids."""

    path: Path
    capabilities: dict[str, CapabilityReference]
    tokens: dict[str, str]
    revisions: dict[str, str] = field(default_factory=dict)
    jobs: dict[str, str] = field(default_factory=dict)
    #: The records of the build's own requests the shell can make, per principal:
    #: `{principal: {key: record}}` (the solves' `submit_job`, `viewer-b`'s two refusals).
    effects: dict[str, dict[str, Any]] = field(default_factory=dict)

    def open(self, principal: str) -> LocalApplication:
        return LocalApplication.open(self.path, capability=self.capabilities[principal])


def _case(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(path.read_text("utf-8"))
    return loaded


def key(name: str, args: Mapping[str, Any]) -> str:
    """The record key of a request: the operation and its non-null members as canonical JSON —
    what `tests/web/fixture-transport.mjs` computes from the URL and body `api.js` sends."""
    members = {k: v for k, v in args.items() if v is not None}
    return f"{name} " + json.dumps(
        members, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _record(app: LocalApplication, name: str, args: Mapping[str, Any]) -> dict[str, Any]:
    """`dispatch` of one request as the HTTP binding would answer it: `{status, body}`, or for
    the raw export `{status, bytes}` (the bytes are written to a file by `capture`)."""
    request = {k: v for k, v in args.items() if v is not None}
    try:
        result = dispatch(app, name, request)
    except ApplicationError as refused:
        return {"status": refused.error.http_status, "body": refused.error.as_document()}
    if OPERATIONS[name].response_schema is None:
        assert isinstance(result, bytes)
        return {"status": 200, "bytes": result}
    return {"status": 200, "body": json.loads(json.dumps(result))}


def _commit(app: LocalApplication, edits: list[dict[str, Any]], key_: str) -> str:
    project = dispatch(app, "get_project", {})
    result = dispatch(
        app,
        "commit_change",
        {"edits": edits, "expected_revision": project["head"], "idempotency_key": key_},
    )
    assert result["status"] == "committed", result
    revision: str = result["revision_id"]
    return revision


def _whole(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{"operation": "set", "path": [k], "value": v} for k, v in document.items()]


def _solve(project: FixtureProject, app: LocalApplication, revision: str, key_: str) -> str:
    request = {
        "operation": "solve",
        "idempotency_key": key_,
        "body": {"revision_id": revision, "policy_id": "default"},
    }
    record = _record(app, "submit_job", request)
    assert record["status"] == 200, record
    project.effects.setdefault("agent-a", {})[key("submit_job", request)] = record
    job: str = record["body"]["job"]["job_id"]
    ended = dispatch(app, "wait_job", {"job_id": job, "timeout_s": 300})
    assert ended["ended"], ended
    return job


def build_fixture_project(path: Path) -> FixtureProject:
    """§8: the W26 fixture project at `path` (a directory that does not exist yet)."""
    LocalApplication.create(path, project_id=PROJECT_ID).close()
    capabilities: dict[str, CapabilityReference] = {}
    tokens: dict[str, str] = {}
    for principal, rights in (
        ("agent-a", ("read", "draft", "execute")),
        ("viewer-b", ("read",)),
        ("supervisor-c", ("read", "policy")),
    ):
        capabilities[principal], tokens[principal] = grant(
            path, principal_id=principal, rights=rights, capability_id=f"cap-{principal}"
        )
    project = FixtureProject(path=path, capabilities=capabilities, tokens=tokens)
    net02 = _case(NET02)
    with project.open("agent-a") as agent:
        project.revisions["NET02"] = _commit(agent, _whole(net02), "fixture-commit-net02")
        project.jobs["NET02"] = _solve(
            project, agent, project.revisions["NET02"], "fixture-solve-1"
        )

        instances = copy.deepcopy(net02["instances"])
        (split,) = (instance for instance in instances if instance["id"] == "U-SPLIT")
        assert split["parameters"]["split_fraction"]["value"] == 0.95
        split["parameters"]["split_fraction"]["value"] = 0.90
        project.revisions["NET02-split-0.90"] = _commit(
            agent,
            [{"operation": "set", "path": ["instances"], "value": instances}],
            "fixture-commit-split",
        )
        project.jobs["NET02-split-0.90"] = _solve(
            project, agent, project.revisions["NET02-split-0.90"], "fixture-solve-2"
        )

        project.revisions["STR03"] = _commit(agent, _whole(_case(STR03)), "fixture-commit-str03")
        project.revisions["A02-352"] = _commit(
            agent, _whole(_case(A02_352)), "fixture-commit-a02-352"
        )
        project.jobs["A02-352"] = _solve(
            project, agent, project.revisions["A02-352"], "fixture-solve-3"
        )

        hostile = {**net02, "title": HOSTILE_TITLE, "description": HOSTILE_DESCRIPTION}
        project.revisions["hostile"] = _commit(agent, _whole(hostile), "fixture-commit-hostile")
    with project.open("viewer-b") as viewer:
        refused: dict[str, dict[str, Any]] = {
            "submit_job": {
                "operation": "solve",
                "idempotency_key": "fixture-viewer-solve",
                "body": {"revision_id": project.revisions["NET02"], "policy_id": "default"},
            },
            "list_audit": {"order": "descending", "limit": AUDIT_PAGE},
        }
        for name, request in refused.items():
            record = _record(viewer, name, request)
            assert record["status"] == 403 and record["body"]["code"] == "forbidden", record
            project.effects.setdefault("viewer-b", {})[key(name, request)] = record
    return project


# ============================================================================ the shell's reads


class Recorder:
    """The answers of one principal's requests, by `key`; the shared ones are kept once."""

    def __init__(self, project: FixtureProject) -> None:
        self.project = project
        self.shared: dict[str, Any] = {}
        self.own: dict[str, dict[str, Any]] = {principal: {} for principal in PRINCIPALS}
        self.raw: dict[str, bytes] = {}
        self._apps = {principal: project.open(principal) for principal in PRINCIPALS}

    def close(self) -> None:
        for app in self._apps.values():
            app.close()

    def ask(self, principal: str, name: str, args: Mapping[str, Any]) -> dict[str, Any]:
        """One request as `principal`: its record (recorded under its key)."""
        record = _record(self._apps[principal], name, args)
        if "bytes" in record:
            self.raw[str(args["artifact_id"])] = record.pop("bytes")
            record["raw"] = _raw_name(str(args["artifact_id"]))
        target = self.own[principal] if name in PER_PRINCIPAL else self.shared
        target[key(name, args)] = record
        return record

    def body(self, principal: str, name: str, args: Mapping[str, Any]) -> Any:
        record = self.ask(principal, name, args)
        assert record["status"] == 200, (name, args, record)
        return record["body"]

    def pages(
        self, principal: str, name: str, args: Mapping[str, Any], *, events: bool = False
    ) -> list[Any]:
        """Every page of a list: by `cursor`, or (`list_job_events`) by `after_sequence`."""
        items: list[Any] = []
        cursor_args = dict(args)
        while True:
            page = self.body(principal, name, cursor_args)
            items.extend(page["items"])
            if page["next_cursor"] is None:
                return items
            if events:
                cursor_args["after_sequence"] = int(page["next_cursor"])
            else:
                cursor_args["cursor"] = page["next_cursor"]

    def read_whole(self, principal: str, name: str, args: Mapping[str, Any]) -> Any:
        """§5.4's `readWhole`, as `js/api.js` runs it, every view recorded."""
        sha: list[str] = []

        def view(pointer: str, cursor: str | None) -> dict[str, Any]:
            document: dict[str, Any] = self.body(
                principal,
                name,
                {
                    **args,
                    "pointer": pointer,
                    "depth": VIEW_DEPTH,
                    "limit": VIEW_LIMIT,
                    "cursor": cursor,
                },
            )
            if not sha:
                sha.append(document["sha256"])
            assert document["sha256"] == sha[0], (name, args, pointer)
            return document

        def page(pointer: str) -> Any:
            first = view(pointer, None)
            if not isinstance(first["value"], list):
                return first["value"]
            items = list(first["value"])
            cursor = first["next_cursor"]
            while cursor is not None:
                following = view(pointer, cursor)
                items.extend(following["value"])
                cursor = following["next_cursor"]
            return items

        def expand(node: Any, at: str, target: bool = False) -> Any:
            if _is_marker(node, at):
                value = page(at)
                if _is_marker(value, at):
                    return value
                return expand(value, at, isinstance(value, list))
            if isinstance(node, list):
                if not target and node and _is_marker(node[-1], at, "items"):
                    return expand(page(at), at, True)
                return [expand(item, f"{at}/{index}") for index, item in enumerate(node)]
            if isinstance(node, dict):
                return {k: expand(v, f"{at}/{_escape(k)}") for k, v in node.items()}
            return node

        root = page("")
        return expand(root, "", isinstance(root, list))


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _is_marker(node: Any, at: str, kind: str | None = None) -> bool:
    """`api.js`'s `isMarker`: `{"$elided": {"pointer": at, "items"|"members": n}}`, sole key."""
    if not isinstance(node, dict) or list(node) != [ELIDED]:
        return False
    inner = node[ELIDED]
    if not isinstance(inner, dict) or len(inner) != 2 or inner.get("pointer") != at:
        return False
    counts = [name for name in inner if name != "pointer"]
    count = counts[0] if len(counts) == 1 else ""
    if count not in ("items", "members") or (kind is not None and count != kind):
        return False
    value = inner[count]
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _raw_name(artifact_id: str) -> str:
    """`raw/<job>/<member>` for `<job>:bundle/<member>`."""
    job, _, member = artifact_id.partition(":bundle/")
    assert job and member and "/" not in member, artifact_id
    return f"raw/{job}/{member}"


def capture(project: FixtureProject) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Every request §6's screens make on `project`, answered: the fixture document and the raw
    bytes by artifact id."""
    recorder = Recorder(project)
    try:
        _capture(recorder)
    finally:
        recorder.close()
    numeric = {
        name: sorted(
            member
            for member in operation.request_schema.get("properties", {})
            if _numeric_member(operation.request_schema, member)
        )
        for name, operation in OPERATIONS.items()
        if operation in HTTP_OPERATIONS
        and operation.http is not None
        and operation.http[0] == "GET"
    }
    for principal, records in project.effects.items():
        for name, record in records.items():
            recorder.own[principal].setdefault(name, record)
    document = {
        "generator": GENERATOR,
        "project_id": PROJECT_ID,
        "revisions": project.revisions,
        "jobs": project.jobs,
        "numeric_query_members": {
            name: members for name, members in sorted(numeric.items()) if members
        },
        "shared": dict(sorted(recorder.shared.items())),
        "principals": {p: dict(sorted(recorder.own[p].items())) for p in PRINCIPALS},
    }
    return document, recorder.raw


def _numeric_member(schema: Mapping[str, Any], member: str) -> bool:
    declared = schema["properties"][member].get("type")
    types = {declared} if isinstance(declared, str) else set(declared or ())
    return bool(types & {"integer", "number"})


def _capture(rec: Recorder) -> None:
    project = rec.project
    for principal in PRINCIPALS:
        rec.body(principal, "get_project", {})
    # #/ — the project screen.
    rec.pages("agent-a", "list_revisions", {"limit": REVISION_PAGE})
    rec.body("agent-a", "list_jobs", {"limit": PROJECT_JOB_PAGE})
    rec.pages("agent-a", "list_jobs", {"limit": JOB_PAGE})
    rec.body("agent-a", "list_models", {})
    # #/rev/{rid}, /validation, /row/{row}; #/compare/rev/{a}/{b}.
    parents: dict[str, str | None] = {}
    for revision in project.revisions.values():
        document = rec.read_whole("agent-a", "get_revision", {"revision_id": revision})
        parents[revision] = document.get("parent_revision")
        rec.body("agent-a", "validate", {"revision_id": revision, "task": "simulation"})
        rec.read_whole("agent-a", "inspect_structure", {"revision_id": revision})
    for revision, parent in parents.items():
        if parent is not None:
            rec.body(
                "agent-a", "diff_revisions", {"from_revision": parent, "to_revision": revision}
            )
    # #/job/{jid} and its sub-screens; #/compare/run/{j1}/{j2}.
    for job in project.jobs.values():
        rec.body("agent-a", "get_job", {"job_id": job})
        rec.pages(
            "agent-a",
            "list_job_events",
            {"job_id": job, "after_sequence": -1, "limit": EVENT_PAGE},
            events=True,
        )
        result = rec.body("agent-a", "get_job_result", {"job_id": job})
        (bundle,) = (
            output["artifact_id"]
            for output in result["run_result"]["outputs"]
            if output["kind"] == "replay_bundle"
        )
        listing = rec.read_whole("agent-a", "get_artifact", {"artifact_id": bundle})
        for member in listing["files"]:
            rec.ask("agent-a", "artifact_bytes", {"artifact_id": member["artifact_id"]})
    # #/history — each principal's own rows, and all principals' as `supervisor-c` (`viewer-b`'s
    # refused request for them is the build's, recorded with its effects). Nothing above is an
    # effect or a refusal, so these lists show exactly the build's rows.
    for principal in PRINCIPALS:
        rec.ask(
            principal,
            "list_audit",
            {"principal_id": principal, "order": "descending", "limit": AUDIT_PAGE},
        )
    rec.ask("supervisor-c", "list_audit", {"order": "descending", "limit": AUDIT_PAGE})


def _write(document: dict[str, Any], raw: Mapping[str, bytes], out: Path) -> list[tuple[str, int]]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    written: list[tuple[str, int]] = []
    text = json.dumps(document, sort_keys=True, ensure_ascii=False, indent=1) + "\n"
    (out / "exchanges.json").write_text(text, encoding="utf-8")
    written.append(("exchanges.json", len(text.encode("utf-8"))))
    for artifact_id, data in sorted(raw.items()):
        name = _raw_name(artifact_id)
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(data)
        written.append((name, len(data)))
    return written


def main(argv: list[str], build: Callable[[Path], FixtureProject] = build_fixture_project) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", required=True)
    parser.add_argument("--out", type=Path, default=TARGET)
    arguments = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="m06-web-fixtures-") as scratch:
        project = build(Path(scratch) / "project")
        document, raw = capture(project)
    for name, size in _write(document, raw, arguments.out):
        print(f"{size:>9}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
