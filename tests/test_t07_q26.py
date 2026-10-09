"""T07 W6e: R-088 Q26 — no T07 operation accepts a matrix or a state from outside (§13).

Design note §13, Q26's row. Two halves:

**(i) The static schema scan.** Every request schema reachable from `OPERATIONS` is walked, every
`$ref` resolved against the published schemas, and every member classified by what its schema
*declares*: a numeric array (an array whose items admit a number), a numeric map (an object whose
additional or pattern properties admit a number), or a numeric scalar. §13 allows exactly
`check_tolerances` (kind → number), `budgets`, `max_property_calls`, `depth` and `limit`; any
numeric array or map elsewhere fails. The scan is shown to catch what it must (a numeric array,
a map from variable ids to numbers, one hidden behind a `$ref` or a combinator) on synthetic
schemas. Two inventories are pinned beside it, so a new member of either kind is seen:

- the numeric *scalars*, which are not arrays or maps and so not what Q26 forbids — §13's list
  names `depth` and `limit`, and the scan also finds `after_sequence` (an event cursor) and
  `timeout_s` (how long `wait_job` waits);
- the *untyped* members, which declare nothing and so admit anything: an edit's `value`
  (`commit_change`, `preview_change`). It is revision content — the model — validated as a
  revision when the change is applied; no operation reads it as a solver state.

One array admits integers and is not in §13's list: an edit's `path`, an address into the
revision whose items are a member name or an array index (`string | integer >= 0`). It is pinned
by operation and by item schema, not allowed by name.

**M02 (R-235, design note M02 §14 B2).** The `experiment` job's inlet is a model input — the
definition of the experiment, which its record is identified by — not a solver state: one numeric
array is allowed by full path and only there, `submit_job`'s `body/inlet/n`, and the scalar
inventory gains `body/inlet/T`, `body/inlet/P` and `body/n_tubes`. That no path leads from the
`experiment` body to a solver start, a warm start or a coupling iterate is the companion test,
`tests/test_m02_experiment_body_isolation.py`.

**(ii) The forged bundle through every transport that reaches reproduce.** A bundle of a run that
did not converge (`SYN-001-A02-352-vapor-guess-410`, `HOMOTOPY_STALLED`), forged to carry the
`VERIFIED` certificate of a run that did (`SYN-001-A02-360`), with a consistent index and
recomputed manifest hashes (W3a's `_rewrite`, which W3a's own Q26 test uses at the run layer).
`reproduce(rerun=true)` must give `MISMATCH` and `rerun=false` `inspected_archived_results` /
`NOT_RUN` — never `MATCH`:

- **Python** and the **CLI** carry `reproduce`, which imports the bundle from a path;
- **HTTP** and **MCP** carry no import, only a `reproduce` job of a bundle the project already
  holds: the forged bundle, imported once in-process, is reproduced over each by `submit_job`.

The day `solve_resume` lands, (ii) must gain a W14 path case (§13).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_transport_support import SERVED, CliClient, Client, HttpClient, McpClient, PythonInline
from test_t07_w3a_revision_runs import _rewrite

from openflowsheet.application.authz import grant
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import SCHEMA_BASE, published_schemas
from openflowsheet.run.bundle import read_artifact, read_manifest

# ============================================================================ (i) the scan

#: §13: the members allowed to be, or contain, numbers.
ALLOWED = frozenset({"check_tolerances", "budgets", "max_property_calls", "depth", "limit"})
#: R-235: model inputs allowed by full path (operation, path, kind), nowhere else.
ALLOWED_BY_PATH = frozenset({("submit_job", "body/inlet/n", "array")})
NUMERIC = frozenset({"number", "integer"})


@dataclass(frozen=True)
class Finding:
    operation: str
    path: tuple[str, ...]  # member names; `*` for an array item or a map value
    kind: str  # "array", "map", "scalar", "untyped"

    @property
    def allowed(self) -> bool:
        return bool(ALLOWED.intersection(self.path))


def _resolve(reference: str, base: str | None, documents: Mapping[str, Any]) -> tuple[Any, str]:
    address, _, fragment = reference.partition("#")
    document_id = address or base
    assert document_id is not None and document_id in documents, reference
    target: Any = documents[document_id]
    for token in fragment.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        target = target[int(token)] if isinstance(target, list) else target[token]
    return target, document_id


def _admits_number(schema: Any, base: str | None, documents: Mapping[str, Any]) -> bool | None:
    """Whether `schema` declares that it admits a number: `True`, `False`, or `None` for a schema
    that declares nothing (`{}`, `true`) and so admits anything."""
    if schema is True or schema == {}:
        return None
    if not isinstance(schema, Mapping):
        return False
    if "$ref" in schema:
        target, base = _resolve(schema["$ref"], base, documents)
        rest = {k: v for k, v in schema.items() if k != "$ref"}
        found = _admits_number(target, base, documents)
        return found if not rest else (found or bool(_admits_number(rest, base, documents)))
    declared = schema.get("type")
    types = {declared} if isinstance(declared, str) else set(declared or ())
    if types & NUMERIC:
        return True
    values = [schema["const"]] if "const" in schema else list(schema.get("enum", []))
    if any(isinstance(v, int | float) and not isinstance(v, bool) for v in values):
        return True
    branches = [b for k in ("oneOf", "anyOf", "allOf") for b in schema.get(k, [])]
    if any(_admits_number(branch, base, documents) for branch in branches):
        return True
    if types or branches or set(schema) & {"properties", "items", "enum", "const", "pattern"}:
        return False
    return None


def scan(
    operation: str, schema: Any, documents: Mapping[str, Any] | None = None
) -> Iterator[Finding]:
    """Every member of `schema` that is or contains numbers, or declares nothing."""
    documents = published_schemas() if documents is None else documents
    yield from _walk(operation, schema, (), None, documents, ())


def _walk(
    operation: str,
    schema: Any,
    path: tuple[str, ...],
    base: str | None,
    documents: Mapping[str, Any],
    active: tuple[str, ...],
) -> Iterator[Finding]:
    if not isinstance(schema, Mapping):
        return
    if "$ref" in schema:
        target, target_base = _resolve(schema["$ref"], base, documents)
        address = f"{target_base}#{schema['$ref'].partition('#')[2]}"
        if address not in active:
            yield from _walk(operation, target, path, target_base, documents, (*active, address))
    for keyword in ("oneOf", "anyOf", "allOf"):
        for branch in schema.get(keyword, []):
            yield from _walk(operation, branch, path, base, documents, active)
    for name, member in schema.get("properties", {}).items():
        admits = _admits_number(member, base, documents)
        if admits is None:
            yield Finding(operation, (*path, name), "untyped")
        elif admits:
            yield Finding(operation, (*path, name), "scalar")
        yield from _walk(operation, member, (*path, name), base, documents, active)
    for keyword, kind in (("items", "array"), ("additionalProperties", "map")):
        inner = schema.get(keyword)
        if isinstance(inner, Mapping | bool) and inner is not False:
            if _admits_number(inner, base, documents):
                yield Finding(operation, path, kind)
            yield from _walk(operation, inner, (*path, "*"), base, documents, active)
    for inner in schema.get("patternProperties", {}).values():
        if _admits_number(inner, base, documents):
            yield Finding(operation, path, "map")
        yield from _walk(operation, inner, (*path, "*"), base, documents, active)


def _findings() -> list[Finding]:
    return sorted(
        {f for row in OPERATIONS.values() for f in scan(row.name, row.request_schema)},
        key=lambda f: (f.operation, f.path, f.kind),
    )


def test_t07_q26_no_external_state_the_scan_catches_what_it_must() -> None:
    """The scan is not vacuous: a numeric array, a map from variable ids to numbers, each found
    directly, behind a `$ref`, inside an array of objects and behind a combinator."""
    documents = {
        "urn:x": {
            "$defs": {
                "state": {"type": "object", "additionalProperties": {"type": "number"}},
                "vector": {"type": "array", "items": {"type": ["number", "null"]}},
            }
        }
    }
    schema = {
        "type": "object",
        "properties": {
            "x0": {"type": "array", "items": {"type": "number"}},
            "initial": {"$ref": "urn:x#/$defs/state"},
            "guesses": {"type": "array", "items": {"$ref": "urn:x#/$defs/vector"}},
            "seed": {"oneOf": [{"type": "string"}, {"$ref": "urn:x#/$defs/vector"}]},
            "by_id": {"type": "object", "patternProperties": {"^v": {"type": "integer"}}},
            "note": {"type": "string"},
        },
    }
    found = {(f.path, f.kind) for f in scan("synthetic", schema, documents)}
    assert found >= {
        (("x0",), "array"),
        (("initial",), "map"),
        (("guesses", "*"), "array"),
        (("seed",), "array"),
        (("by_id",), "map"),
    }, found
    assert not any(path == ("note",) for path, _ in found)


def test_t07_q26_no_external_state() -> None:
    """(i) No request member reachable from `OPERATIONS` is, or contains, a numeric array or a map
    to numbers, outside §13's allowed members; the scalar and untyped inventories are pinned."""
    findings = _findings()
    containers_found = [f for f in findings if f.kind in ("array", "map") and not f.allowed]
    # An edit's `path` is an address into the revision — member names and array indices — not
    # values: its items are a string or an integer >= 0. Pinned, and its shape held, so that no
    # number of any other kind can arrive through it.
    addresses = {f for f in containers_found if f.path == ("edits", "*", "path")}
    assert {(f.operation, f.kind) for f in addresses} == {
        ("commit_change", "array"),
        ("preview_change", "array"),
    }
    change_set = published_schemas()[SCHEMA_BASE + "change-set.schema.json"]
    path_schema = change_set["$defs"]["edit"]["properties"]["path"]["items"]
    assert path_schema == {"anyOf": [{"type": "string"}, {"type": "integer", "minimum": 0}]}
    model_inputs = {
        f for f in containers_found if (f.operation, "/".join(f.path), f.kind) in ALLOWED_BY_PATH
    }
    assert {(f.operation, "/".join(f.path), f.kind) for f in model_inputs} == ALLOWED_BY_PATH
    forbidden = [f for f in containers_found if f not in addresses | model_inputs]
    assert forbidden == [], forbidden
    containers = {(f.operation, "/".join(f.path), f.kind) for f in findings if f.allowed}
    # `check_tolerances` (kind -> number) is the one numeric map; it is found, and allowed.
    assert ("submit_job", "body/check_tolerances", "map") in containers
    scalars = {(f.operation, "/".join(f.path)) for f in findings if f.kind == "scalar"}
    names = {path.split("/")[-1] for _, path in scalars}
    assert names == {
        "wall_time_s",  # under `budgets`
        "max_property_calls",
        "depth",
        "limit",
        "after_sequence",
        "timeout_s",
        "T",  # R-235: the `experiment` inlet's, and its tube count
        "P",
        "n_tubes",
        "max_cold_experiments",  # M04: a `surrogate_study`'s budget, a count, not a state
    }, scalars
    assert {path for _, path in scalars if path.endswith("wall_time_s")} == {"budgets/wall_time_s"}
    assert {(o, path) for o, path in scalars if path.split("/")[-1] in ("T", "P", "n_tubes")} == {
        ("submit_job", "body/inlet/T"),
        ("submit_job", "body/inlet/P"),
        ("submit_job", "body/n_tubes"),
    }
    assert {(o, path) for o, path in scalars if path.endswith("max_cold_experiments")} == {
        ("submit_job", "body/budget/max_cold_experiments")
    }
    untyped = {(f.operation, "/".join(f.path)) for f in findings if f.kind == "untyped"}
    assert untyped == {
        ("commit_change", "edits/*/value"),
        ("preview_change", "edits/*/value"),
    }, untyped


# =================================================================== (ii) the forged bundle

STALLED = "SYN-001-A02-352-vapor-guess-410"
CONVERGED = "SYN-001-A02-360"


@dataclass
class Forged:
    project: Path
    bundle: Path
    imported: str  # the forged bundle, imported into the project
    grant: tuple[Any, str]


def _solved(owner: LocalApplication, name: str, key: str) -> Path:
    """Commit corpus revision `name` over the head and solve it inline: its bundle's directory."""
    with owner.store.reading() as connection:
        head = owner.store.head(connection)
    edits = [{"operation": "set", "path": [k], "value": v} for k, v in CORPUS[name]().items()]
    committed = dispatch(
        owner,
        "commit_change",
        {"edits": edits, "expected_revision": head, "idempotency_key": f"c-{key}"},
    )
    request = {
        "operation": "solve",
        "idempotency_key": f"s-{key}",
        "body": {"revision_id": committed["revision_id"]},
    }
    job = dispatch(owner, "submit_job", request)["job"]
    assert job["status"] == "completed", job
    return owner.files_root / "jobs" / job["job_id"] / "bundle"


@pytest.fixture(scope="module")
def forged(tmp_path_factory: pytest.TempPathFactory) -> Forged:
    root = tmp_path_factory.mktemp("q26")
    project = root / "project"
    with LocalApplication.create(project, project_id="t07-q26") as owner:
        stalled = _solved(owner, STALLED, "stalled")
        converged = _solved(owner, CONVERGED, "converged")
        assert read_manifest(stalled)[0].outcome == "HOMOTOPY_STALLED"
        certificate = read_artifact(converged, "solution-certificate.json")
        assert certificate["verification_status"] == "VERIFIED"
        bundle = _rewrite(
            stalled,
            root / "forged",
            failure_bundle=None,
            solution_certificate=copy.deepcopy(certificate),
            manifest={"outcome": "CONVERGED", "verification_status": "VERIFIED"},
        )
        assert read_manifest(bundle)[0].verification_status == "VERIFIED"
        # The import HTTP and MCP cannot make: once, in-process (inspection only).
        report = dispatch(
            owner, "reproduce", {"bundle_path": str(bundle), "policy": {"rerun": False}}
        )
        assert report["verdict"] == "NOT_RUN"
    credential = grant(
        project, principal_id="agent-q26", rights=("execute", "read"), capability_id="cap-q26"
    )
    return Forged(project, bundle, "import-000001:bundle", credential)


def _reports_by_path(client: Client, bundle: Path) -> dict[bool, dict[str, Any]]:
    reports = {}
    for rerun in (True, False):
        error, report = client.call(
            "reproduce", {"bundle_path": str(bundle), "policy": {"rerun": rerun}}
        )
        assert not error, report
        reports[rerun] = report
    return reports


def _reports_by_job(client: Client, imported: str, tag: str) -> dict[bool, dict[str, Any]]:
    reports = {}
    for rerun in (True, False):
        request = {
            "operation": "reproduce",
            "idempotency_key": f"q26-{tag}-{rerun}",
            "body": {"bundle_artifact_id": imported, "rerun": rerun},
        }
        error, submitted = client.call("submit_job", request)
        assert not error, submitted
        job_id = submitted["job"]["job_id"]
        waited: dict[str, Any] = {"ended": False}
        while not waited["ended"]:
            error, waited = client.call("wait_job", {"job_id": job_id, "timeout_s": 30})
            assert not error, waited
        error, result = client.call("get_job_result", {"job_id": job_id})
        assert not error and result["replay_report"] is not None, result
        reports[rerun] = result["replay_report"]
    return reports


@pytest.mark.parametrize("transport", ["python", "cli", "http", "mcp"])
def test_t07_q26_no_external_state_a_forged_bundle_never_matches(
    forged: Forged, transport: str, tmp_path: Path
) -> None:
    """(ii) Over each transport that reaches reproduce: a rerun re-solves from the revision and
    the policy and reports `MISMATCH`; an inspection reports `NOT_RUN`; never `MATCH`."""
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    import sys

    from t07_transport_support import ThreadStream

    capability, token = forged.grant
    client: Client
    with pytest.MonkeyPatch.context() as patch:
        if transport == "cli":
            out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
            patch.setattr(sys, "stdout", out)
            patch.setattr(sys, "stderr", err)
            client = CliClient(forged.project, tmp_path / "raw.bin", out, err)
        elif transport == "python":
            client = PythonInline(forged.project)  # `dispatch`, which carries `reproduce`
        elif transport == "http":
            client = HttpClient(forged.project, token)
        else:
            client = McpClient(forged.project, capability)
        try:
            if "reproduce" in client.carries:
                reports = _reports_by_path(client, forged.bundle)
            else:
                assert "reproduce" not in SERVED[transport]
                reports = _reports_by_job(client, forged.imported, transport)
        finally:
            client.close()
    rerun, inspected = reports[True], reports[False]
    assert rerun["verdict"] == "MISMATCH", json.dumps(rerun)[:2000]
    assert rerun["mode"] != "inspected_archived_results"
    assert (inspected["mode"], inspected["verdict"]) == ("inspected_archived_results", "NOT_RUN")
