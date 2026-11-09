"""X04 WO-2: the project's ambient pressure (ADR 0075 D6).

Assertions A9–A13 of `docs/derivations/X04-test-specification.md` §5 P, and A33's round trips of
`project-policy` with `ambient_pressure` and `project_summary` (X04 decision D-1: in this module,
not in F0's M8 fixture directories). A14 needs the displayed stream table (WO-4) and lives with it.
Expected values come from `docs/derivations/scripts/x04_reference.json` (`ambient_declarations`).
"""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT
from t07_transport_support import (
    CliClient,
    Client,
    HttpClient,
    McpClient,
    PythonInline,
    ThreadStream,
)

from openflowsheet.application.authz import (
    ambient_pressure_pa,
    grant,
    read_policy,
    set_ambient_pressure,
)
from openflowsheet.application.cli import main
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import DATABASE_NAME, POLICY_NAME, StoreError
from openflowsheet.application.types import Change, ProjectPolicy, schema_errors
from openflowsheet.canonical import document_sha256

REFERENCE: dict[str, Any] = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "x04_reference.json").read_text("utf-8")
)
DECLARATIONS = REFERENCE["ambient_declarations"]
ACCEPTED = [case for case in DECLARATIONS if not case["expected"].startswith("refused:")]
REFUSED = [case for case in DECLARATIONS if case["expected"].startswith("refused:")]
RANKINE = REPO_ROOT / "examples" / "rankine-cycle.changeset.json"
pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exited:
            code = exited.code if isinstance(exited.code, int) else 1
    return code, out.getvalue(), err.getvalue()


def _project(root: Path, name: str = "project", project_id: str = "x04-ambient") -> Path:
    directory = root / name
    with LocalApplication.create(directory, project_id=project_id):
        pass
    return directory


def _audit(project: Path, operation: str) -> list[tuple[str, str]]:
    connection = sqlite3.connect(project / DATABASE_NAME)
    try:
        rows = connection.execute(
            "SELECT outcome, effect FROM audit WHERE operation = ? ORDER BY seq", (operation,)
        ).fetchall()
    finally:
        connection.close()
    return [(str(outcome), str(effect)) for outcome, effect in rows]


def _summary_ambient(project: Path) -> Any:
    with LocalApplication.open(project) as app:
        document = app.get_project().as_document()
    assert schema_errors("application-results.schema.json#/$defs/project_summary", document) == []
    return document["ambient_pressure"]


# -- A9. Declare, read, clear --------------------------------------------------------------------


@pytest.mark.parametrize("case", ACCEPTED, ids=lambda case: case["id"])
def test_a9_declare_read_clear(case: dict[str, Any], tmp_path: Path) -> None:
    project = _project(tmp_path)
    argv = ["project", "ambient", "--project", str(project)]
    code, out, err = run_cli([*argv, "--pressure", case["value"], "--unit", case["unit"]])
    assert (code, err) == (0, ""), err
    pascal = float(case["expected"])
    assert out == f"ambient pressure {case['expected']} Pa\n"
    written = json.loads((project / POLICY_NAME).read_text(encoding="utf-8"))
    assert repr(written["ambient_pressure"]) == case["expected"]
    assert read_policy(project / POLICY_NAME).ambient_pressure == pascal
    assert _audit(project, "project_ambient") == [("allowed", f"ambient:{case['expected']}")]
    assert _summary_ambient(project) == {"value": pascal, "unit": "Pa"}
    declared_bytes = (project / POLICY_NAME).read_bytes()

    code, out, err = run_cli([*argv, "--clear"])
    assert (code, out, err) == (0, "ambient pressure cleared\n", "")
    assert "ambient_pressure" not in json.loads((project / POLICY_NAME).read_text("utf-8"))
    assert _summary_ambient(project) is None
    assert [row[1] for row in _audit(project, "project_ambient")] == [
        f"ambient:{case['expected']}",
        "ambient:cleared",
    ]

    # The library call gives the same file bytes.
    other = _project(tmp_path, "library")
    assert set_ambient_pressure(other, pascal) == pascal
    assert (other / POLICY_NAME).read_bytes() == declared_bytes
    assert ambient_pressure_pa(float(case["value"]), case["unit"]) == pascal


def test_a9_the_command_needs_one_of_its_two_forms(tmp_path: Path) -> None:
    project = _project(tmp_path)
    before = (project / POLICY_NAME).read_bytes()
    base = ["project", "ambient", "--project", str(project)]
    for extra in ([], ["--pressure", "1"], ["--unit", "bar"], ["--clear", "--unit", "bar"]):
        code, out, _err = run_cli([*base, *extra])
        assert (code, out) == (2, ""), extra
    assert (project / POLICY_NAME).read_bytes() == before
    assert _audit(project, "project_ambient") == []


# -- A10. Declaration refusals --------------------------------------------------------------------


@pytest.mark.parametrize("case", REFUSED, ids=lambda case: case["id"])
def test_a10_declaration_refusals(case: dict[str, Any], tmp_path: Path) -> None:
    project = _project(tmp_path)
    before = (project / POLICY_NAME).read_bytes()
    part = case["expected"].removeprefix("refused:")
    code, out, err = run_cli(
        [
            "project",
            "ambient",
            "--project",
            str(project),
            "--pressure",
            case["value"],
            "--unit",
            case["unit"],
        ]
    )
    assert (code, out) == (2, "")
    assert f"Details: ambient_pressure_invalid({part})" in err
    assert (project / POLICY_NAME).read_bytes() == before
    assert _audit(project, "project_ambient") == []

    with pytest.raises(StoreError) as caught:
        ambient_pressure_pa(float(case["value"]), case["unit"])
    assert caught.value.args[0] == f"ambient_pressure_invalid({part})"
    assert caught.value.code == "ambient_pressure_invalid"


@pytest.mark.parametrize("pascal", [0.0, -0.0, -1e5, float("nan"), float("inf"), -float("inf")])
def test_a10_the_library_call_refuses_the_same(pascal: float, tmp_path: Path) -> None:
    project = _project(tmp_path)
    before = (project / POLICY_NAME).read_bytes()
    with pytest.raises(StoreError) as caught:
        set_ambient_pressure(project, pascal)
    assert caught.value.args[0] == "ambient_pressure_invalid(value)"
    assert (project / POLICY_NAME).read_bytes() == before
    assert _audit(project, "project_ambient") == []


def test_a10_an_unparsable_value_is_refused_as_a_value(tmp_path: Path) -> None:
    project = _project(tmp_path)
    code, _out, err = run_cli(
        ["project", "ambient", "--project", str(project), "--pressure", "one", "--unit", "bar"]
    )
    assert code == 2
    assert "Details: ambient_pressure_invalid(value)" in err


# -- A11. Policy bytes ----------------------------------------------------------------------------

#: The members of `project-policy-v1` before X04: an undeclared ambient adds none.
PRE_X04_MEMBERS = {"schema_version", "project_id", "capabilities", "executor"}


def test_a11_an_undeclaring_project_keeps_its_policy_bytes(tmp_path: Path) -> None:
    project = _project(tmp_path, project_id="x04-bytes")
    data = (project / POLICY_NAME).read_bytes()
    document = json.loads(data)
    assert set(document) == PRE_X04_MEMBERS
    pre_x04 = {
        "schema_version": "project-policy-v1",
        "project_id": "x04-bytes",
        "capabilities": [],
        "executor": {"max_workers": 1, "grace_s": 10},
    }
    assert data == (json.dumps(pre_x04, indent=1, sort_keys=True) + "\n").encode("utf-8")
    policy = read_policy(project / POLICY_NAME)
    assert policy.ambient_pressure is None
    assert policy.policy_sha256 == document_sha256(pre_x04)


def test_a11_declaring_then_clearing_restores_the_bytes(tmp_path: Path) -> None:
    project = _project(tmp_path)
    grant(project, principal_id="agent-1", capability_id="cap-1")
    before = (project / POLICY_NAME).read_bytes()
    set_ambient_pressure(project, 101325.0)
    assert (project / POLICY_NAME).read_bytes() != before
    set_ambient_pressure(project, None)
    assert (project / POLICY_NAME).read_bytes() == before


def test_a11_grants_and_revocations_write_no_ambient(tmp_path: Path) -> None:
    # The repository commits no `project-policy.json` file; the policies the operator commands
    # write are the existing ones, and none gains a member.
    from openflowsheet.application.authz import revoke
    from openflowsheet.application.store import policy_file_bytes

    project = _project(tmp_path)
    grant(project, principal_id="agent-1", capability_id="cap-1")
    grant(project, principal_id="agent-2", capability_id="cap-2")
    revoke(project, "cap-1")
    data = (project / POLICY_NAME).read_bytes()
    assert set(json.loads(data)) == PRE_X04_MEMBERS
    assert policy_file_bytes(read_policy(project / POLICY_NAME)) == data


# -- A33 (WO-2's part): round trips --------------------------------------------------------------


@pytest.mark.parametrize("ambient", [None, 101325.0, 101324.66370467292, 95000.0])
def test_a33_project_policy_round_trips_with_ambient(ambient: float | None) -> None:
    policy = ProjectPolicy(project_id="p", capabilities=(), ambient_pressure=ambient)
    document = policy.as_document()
    assert schema_errors("project-policy.schema.json", document) == []
    assert ("ambient_pressure" in document) == (ambient is not None)
    rebuilt = ProjectPolicy.from_document(json.loads(json.dumps(document)))
    assert rebuilt == policy and rebuilt.as_document() == document


@pytest.mark.parametrize("bad", [0, 0.0, -1.0, "101325", None, True])
def test_a33_the_policy_schema_refuses_a_bad_ambient(bad: Any) -> None:
    document = ProjectPolicy(project_id="p", capabilities=()).as_document()
    document["ambient_pressure"] = bad
    assert schema_errors("project-policy.schema.json", document) != []


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_a33_the_policy_type_refuses_a_bad_ambient(bad: float) -> None:
    with pytest.raises(ValueError):
        ProjectPolicy(project_id="p", capabilities=(), ambient_pressure=bad)


def test_a33_project_summary_requires_a_nullable_ambient(tmp_path: Path) -> None:
    reference = "application-results.schema.json#/$defs/project_summary"
    project = _project(tmp_path)
    with LocalApplication.open(project) as app:
        document = app.get_project().as_document()
    assert document["ambient_pressure"] is None
    assert schema_errors(reference, document) == []
    for good in ({"value": 101325.0, "unit": "Pa"}, {"value": 1e-300, "unit": "Pa"}):
        assert schema_errors(reference, {**document, "ambient_pressure": good}) == []
    for bad in (
        101325.0,
        {"value": 101325.0},
        {"value": 101325.0, "unit": "bar"},
        {"value": 0.0, "unit": "Pa"},
        {"value": 1.0, "unit": "Pa", "source": "x"},
    ):
        assert schema_errors(reference, {**document, "ambient_pressure": bad}) != [], bad
    del document["ambient_pressure"]
    assert schema_errors(reference, document) != []


# -- A12. get_project on every transport ----------------------------------------------------------


@pytest.fixture
def declared(tmp_path: Path) -> Iterator[tuple[Path, dict[str, Client]]]:
    pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    project = _project(tmp_path)
    capability, token = grant(project, principal_id="agent-x04", rights=("read",))
    out, err = ThreadStream(sys.stdout), ThreadStream(sys.stderr)
    clients: dict[str, Client] = {
        "python": PythonInline(project),
        "cli": CliClient(project, tmp_path / "raw.bin", out, err),
        "http": HttpClient(project, token),
        "mcp": McpClient(project, capability),
    }
    try:
        yield project, clients
    finally:
        for client in clients.values():
            client.close()


def test_a12_get_project_carries_the_ambient_on_every_transport(
    declared: tuple[Path, dict[str, Client]], monkeypatch: pytest.MonkeyPatch
) -> None:
    project, clients = declared
    cli = clients["cli"]
    assert isinstance(cli, CliClient)
    # The CLI client's streams, set in the test body (pytest resets capture after setup).
    monkeypatch.setattr(sys, "stdout", cli.out)
    monkeypatch.setattr(sys, "stderr", cli.err)
    reference = "application-results.schema.json#/$defs/project_summary"
    for expected in (None, {"value": 95000.0, "unit": "Pa"}, None):
        set_ambient_pressure(project, None if expected is None else expected["value"])
        for name, client in clients.items():
            refused, document = client.call("get_project", {})
            assert not refused, (name, document)
            assert schema_errors(reference, document) == [], name
            assert "ambient_pressure" in document, name
            assert document["ambient_pressure"] == expected, name


# -- A13. Not in run identity ---------------------------------------------------------------------


def _solved(root: Path, name: str, ambient: float | None) -> tuple[Path, str, Any]:
    project = _project(root, name, project_id="x04-identity")
    if ambient is not None:
        set_ambient_pressure(project, ambient)
    with LocalApplication.open(project) as app:
        change, _, key = Change.from_change_set(json.loads(RANKINE.read_text(encoding="utf-8")))
        committed = app.commit_change(change, None, key)
        assert committed.revision_id is not None
        result = app.solve(committed.revision_id, "default")
        assert result.outcome == "CONVERGED"
    return project, result.job_id, result


#: The run manifest's wall-clock members, and its own hash over them: two solves of one revision
#: differ there in any one project, so they are not identity (X04 decision D-2).
WALL_CLOCK = ("started_at", "elapsed_seconds", "manifest_sha256")


def _bundle_files(project: Path, job_id: str) -> dict[str, Any]:
    bundle = project / "jobs" / job_id / "bundle"
    files: dict[str, Any] = {
        str(path.relative_to(bundle)): path.read_bytes()
        for path in sorted(bundle.rglob("*"))
        if path.is_file()
    }
    manifest = json.loads(files.pop("run-manifest.json"))
    assert all(member in manifest for member in WALL_CLOCK)
    files["run-manifest.json"] = {k: v for k, v in manifest.items() if k not in WALL_CLOCK}
    return files


def test_a13_the_ambient_is_not_in_run_identity(tmp_path: Path) -> None:
    solved = [_solved(tmp_path, f"p{i}", a) for i, a in enumerate((None, 101325.0, 95000.0))]
    files = [_bundle_files(project, job_id) for project, job_id, _ in solved]
    assert files[0], "the job wrote no bundle"
    assert files[1] == files[0]
    assert files[2] == files[0]
    # Bundle members: the solution state, the certificate and the run manifest (with its keys).
    names = set(files[0])
    assert any(name.endswith("solution-state.json") for name in names), sorted(names)
    assert any("certificate" in name for name in names), sorted(names)
    # The run result, every output's hash included — but the hashes over the whole bundle or
    # its manifest, which cover the manifest's wall-clock members (D-2).
    documents = [result.as_document() for _, _, result in solved]
    for document in documents:
        for output in document["outputs"]:
            if output["kind"] in ("replay_bundle", "run_manifest"):
                del output["sha256"]
    assert {o["kind"] for o in documents[0]["outputs"]} >= {"solution_certificate"}
    assert documents[1] == documents[0] and documents[2] == documents[0]
