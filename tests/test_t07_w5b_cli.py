"""T07 W5b: the CLI binding (design note §11.5) — `api`, and the existing commands unchanged.

**`api` adds nothing** (§11.6 (3), the CLI half of G14's conformance). Two projects are seeded
alike through `LocalApplication`; every operation the table carries on the `cli` transport then
runs once on the first through `main(["api", ...])` and once on the second through `dispatch`,
and the two responses must be equal once the clock readings are removed (ids agree because
ordinals are deterministic from a fresh store). Each reachable `ApiError` exits its §5.8 code,
and a refusal the CLI makes itself (an unparsable request, an operation it does not carry) is
the same typed, audited refusal `dispatch` makes.

**The existing commands are unchanged byte for byte** (§11.5). `existing_commands` runs
`validate`, `solve`, `inspect`, `replay`, and `project init|grant|revoke` — their success and
refusal paths — in-process through `main(argv)`, and compares stdout, stderr and the exit code
with `tests/fixtures/t07/cli-existing-commands.json`, which was captured from the CLI *before*
W5b touched it (commit `9b541df`). Only what cannot repeat between two runs of the same command
is masked, by `normalized`: the run's temporary directory, the validation report's clock
reading, a grant's random token, and the host description a bundle records (`=== environment`,
the replay report's `*_environment`), with the host's floating-point solution bound. Everything
else is compared exactly. There is no `gate` command in the CLI (the plan's v0.0 gate is
`scripts/v0_0_gate.py`), so none is pinned.

Regenerate the pins only for a deliberate output change, and say so in the commit:
`PYTHONPATH=src:. python tests/test_t07_w5b_cli.py --write-pins`.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from t07_corpus import CORPUS
from t07_jobs_support import lifecycle_violations
from t08_d1_substitution import d1_str05_reversed_message
from t08_rename_substitution import record_process_runtime, renamed_back_cli_text
from t08_v2_substitution import CLI_STRUCTURAL_SUBSTITUTION, record_v1, v2_reversed_cli_text

from openflowsheet.application.cli import API_EXIT_CODES, TOKEN_FILE_VARIABLE, main
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS, dispatch
from openflowsheet.application.types import (
    Change,
    Edit,
    JobRequest,
    SolveBody,
    schema_errors,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.run.bundle import ARTIFACT_DIR

PINS = REPO_ROOT / "tests" / "fixtures" / "t07" / "cli-existing-commands.json"
#: SHA-256 of the pins as T07 captured them. T08 D1's STR-05 extension (Frank, 2026-09-29) moved
#: them by its substitution only, T08 review 2's U05 refusal (Ruling 1) by one entry only, and
#: ADR 0025 D1.2's recording switch (Frank, 2026-10-02, R-148) by the structural hash `solve` and
#: `inspect` print only: all three reversed, the file is these bytes again.
PINS_T07_SHA256 = "86aae0c13e5125a2e26f3441af70878519fdbcac41b3432b5efb64efd1596a6c"
#: The one pinned command U05 moved: `validate --task optimization` was the `simulation` report
#: with its task and status renamed, and is now the typed `unsupported` refusal.
U05_ARGV = ["validate", "<CASE>", "--task", "optimization"]
CASE = REPO_ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"


# ================================================================ the existing commands, pinned


def existing_commands(root: Path) -> list[list[str]]:
    """Every existing command's success and refusal path, in an order that builds what the next
    one reads (`root` is empty; `broken.yaml` is written into it)."""
    project = str(root / "project")
    bundle = str(root / "bundle")
    broken = root / "broken.yaml"
    document = yaml.safe_load(CASE.read_text(encoding="utf-8"))
    document["connections"] = document["connections"][:1]
    broken.write_text(yaml.safe_dump(document), encoding="utf-8")
    return [
        ["validate", str(CASE)],
        ["validate", str(CASE), "--json"],
        ["validate", str(CASE), "--task", "optimization"],
        ["validate", str(broken)],
        ["validate", str(broken), "--json"],
        ["solve", "SYN-001-invented", "--out", str(root / "nowhere")],
        ["solve", "SYN-001-nominal", "--out", bundle],
        ["inspect", bundle],
        ["replay", bundle],
        ["replay", bundle, "--json"],
        ["replay", bundle, "--rerun"],
        ["project", "init", project, "--project-id", "p-cli"],
        ["project", "init", project, "--project-id", "p-cli"],
        ["project", "grant", "--project", project, "--principal", "agent-1"]
        + ["--capability-id", "cap-1"],
        ["project", "grant", "--project", project, "--principal", "agent-2"]
        + ["--rights", "read,bogus"],
        ["project", "revoke", "--project", project, "--capability", "cap-1"],
        ["project", "revoke", "--project", project, "--capability", "cap-1"],
    ]


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    """`main(argv)` in-process: its exit code, stdout and stderr (a `SystemExit` is a code)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exited:
            code = exited.code if isinstance(exited.code, int) else 1
    return code, out.getvalue(), err.getvalue()


_ENVIRONMENT_JSON = re.compile(r'("(?:current|recorded)_environment": )\{\n.*?\n \}', re.S)
_ENVIRONMENT_TEXT = re.compile(r"(=== environment[^\n]*\n)((?:  [^\n]*\n)*)")


def _mask_environment_lines(match: re.Match[str]) -> str:
    lines = match.group(2).splitlines(keepends=True)
    return match.group(1) + "".join(re.sub(r"^(  \S+ +).*", r"\1<HOST>", line) for line in lines)


def normalized(text: str, root: Path) -> str:
    """`text` with what cannot repeat between two runs masked (module docstring)."""
    text = text.replace(str(CASE), "<CASE>").replace(str(root), "<ROOT>")
    text = re.sub(r'"timestamp": "[^"]*"', '"timestamp": "<TIMESTAMP>"', text)
    text = re.sub(r"prt_[A-Za-z0-9_-]{43}", "<TOKEN>", text)
    text = _ENVIRONMENT_JSON.sub(r"\1<HOST>", text)
    text = _ENVIRONMENT_TEXT.sub(_mask_environment_lines, text)
    return re.sub(r"(?m)^(  solution bound +).*$", r"\1<HOST>", text)


def capture_existing(root: Path) -> list[dict[str, Any]]:
    """Run `existing_commands` in `root` (created empty) and return the normalized record."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    record = []
    for argv in existing_commands(root):
        code, out, err = run_cli(argv)
        record.append(
            {
                "argv": [normalized(argument, root) for argument in argv],
                "exit": code,
                "stdout": normalized(out, root),
                "stderr": normalized(err, root),
            }
        )
    return record


@pytest.fixture
def single_threaded(monkeypatch: pytest.MonkeyPatch) -> None:
    from openflowsheet.run.manifest import THREAD_VARIABLES

    for variable in THREAD_VARIABLES:
        monkeypatch.setenv(variable, "1")


def u05_reversed(pins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`pins` with U05's entry as T07 captured it: the `validate <CASE>` entry with its task and
    status renamed. Every other entry is returned as it is."""
    (simulation,) = (entry for entry in pins if entry["argv"] == ["validate", "<CASE>"])
    stdout = (
        simulation["stdout"]
        .replace("task      simulation", "task      optimization", 1)
        .replace("status    READY_FOR_SIMULATION", "status    READY_FOR_OPTIMIZATION", 1)
    )
    return [
        {**simulation, "argv": U05_ARGV, "stdout": stdout} if entry["argv"] == U05_ARGV else entry
        for entry in pins
    ]


@pytest.mark.usefixtures("single_threaded")
def test_the_pins_moved_by_d1s_str05_substitution_u05_and_v2_recording_only() -> None:
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    (u05,) = (entry for entry in pins if entry["argv"] == U05_ARGV)
    assert u05["exit"] == API_EXIT_CODES["unsupported"]
    assert json.loads(u05["stdout"])["message"] == "task_unsupported(optimization)"
    restored = json.dumps(u05_reversed(pins), indent=1, ensure_ascii=False) + "\n"
    reversed_pins = v2_reversed_cli_text(d1_str05_reversed_message(renamed_back_cli_text(restored)))
    assert hashlib.sha256(reversed_pins.encode("utf-8")).hexdigest() == PINS_T07_SHA256


@pytest.mark.usefixtures("single_threaded")
def test_r148_with_v1_recorded_the_commands_print_the_v1_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-148's substitution proof: the structural hash is the only text the recording switch
    moved, in `solve` and `inspect` only; with the switch undone every command prints the pins
    with that hash reversed, byte for byte. R-149's rename is undone first."""
    pinned = json.loads(renamed_back_cli_text(PINS.read_text(encoding="utf-8")))
    new, _ = CLI_STRUCTURAL_SUBSTITUTION
    moved = [" ".join(entry["argv"][:2]) for entry in pinned if new in json.dumps(entry)]
    assert moved == ["solve SYN-001-nominal", "inspect <ROOT>/bundle"], moved
    reversed_pins = json.loads(v2_reversed_cli_text(json.dumps(pinned)))
    record_process_runtime(monkeypatch)
    record_v1(monkeypatch)
    record = capture_existing(tmp_path / "run")
    assert [entry["argv"] for entry in record] == [entry["argv"] for entry in reversed_pins]
    for now, then in zip(record, reversed_pins, strict=True):
        assert now == then, " ".join(then["argv"][:2])


def test_the_existing_commands_are_unchanged_byte_for_byte(tmp_path: Path) -> None:
    pinned = json.loads(PINS.read_text(encoding="utf-8"))
    record = capture_existing(tmp_path / "run")
    assert [entry["argv"] for entry in record] == [entry["argv"] for entry in pinned]
    for now, then in zip(record, pinned, strict=True):
        assert now == then, " ".join(then["argv"][:2])


# ======================================================================= api: adds nothing


NOMINAL = "SYN-001-nominal"
#: §11.6: the members a twin project cannot repeat (clock readings), removed before comparing.
CLOCK_MEMBERS = frozenset(
    {"recorded_at", "created_at", "started_at", "ended_at", "elapsed_seconds", "timestamp"}
)
#: The artifacts whose bytes hold clock readings (`run-manifest.json` records `started_at` and
#: `elapsed_seconds`, and the bundle holds the manifest): their digests and sizes are removed.
CLOCKED_ARTIFACTS = frozenset({"run_manifest", "replay_bundle"})
CLOCKED_DIGESTS = frozenset({"manifest_sha256"})


def seed(directory: Path) -> tuple[str, str]:
    """A project with the nominal revision and one solved job, through `LocalApplication`; the
    revision id and the job id."""
    application = LocalApplication.create(directory, project_id="w5b-cli")
    with application:
        edits = tuple(Edit("set", (key,), value) for key, value in CORPUS[NOMINAL]().items())
        committed = application.commit_change(Change(edits=edits), None, "seed")
        assert committed.revision_id is not None
        submitted = application.submit_job(
            JobRequest(
                operation="solve",
                idempotency_key="seed-solve",
                body=SolveBody(revision_id=committed.revision_id),
            )
        )
        assert submitted.job.status == "completed"
        return committed.revision_id, submitted.job.job_id


def scenario(revision_id: str, job_id: str, bundle: Path) -> list[tuple[str, dict[str, Any]]]:
    """One request per operation, in an order where each finds what it reads."""
    state = f"{job_id}:bundle/solution-state.json"
    return [
        ("validate", {"revision_id": revision_id, "task": "simulation"}),
        (
            "preview_change",
            {
                "edits": [{"operation": "set", "path": ["title"], "value": "x"}],
                "expected_revision": revision_id,
            },
        ),
        (
            "commit_change",
            {
                "edits": [{"operation": "set", "path": ["title"], "value": "y"}],
                "expected_revision": revision_id,
                "idempotency_key": "second",
            },
        ),
        ("solve", {"revision_id": revision_id, "policy_id": "default"}),
        ("reproduce", {"bundle_path": str(bundle), "policy": {"rerun": False}}),
        (
            "submit_job",
            {
                "operation": "solve",
                "idempotency_key": "seed-solve",
                "body": {"revision_id": revision_id},
            },
        ),
        ("get_job", {"job_id": job_id}),
        ("list_jobs", {"limit": 1}),
        ("list_job_events", {"job_id": job_id, "after_sequence": 0, "limit": 3}),
        ("wait_job", {"job_id": job_id, "timeout_s": 0}),
        ("cancel_job", {"job_id": job_id}),
        ("get_job_result", {"job_id": job_id}),
        ("get_project", {}),
        ("list_models", {}),
        ("list_revisions", {"limit": 1}),
        ("get_revision", {"revision_id": revision_id, "pointer": "/connections", "limit": 2}),
        ("diff_revisions", {"from_revision": revision_id, "to_revision": revision_id}),
        ("inspect_structure", {"revision_id": revision_id, "depth": 2}),
        ("get_artifact", {"artifact_id": state, "pointer": "/variable_ids", "limit": 5}),
        ("artifact_bytes", {"artifact_id": state}),
    ]


def api(project: Path, name: str, request: Any, *extra: str) -> tuple[int, str, str]:
    return run_cli(["api", name, "--project", str(project), "--json", json.dumps(request), *extra])


def clockless(document: Any) -> Any:
    """`document` without its clock readings and the digests of the bytes that hold them."""
    if isinstance(document, dict):
        removed = CLOCK_MEMBERS | CLOCKED_DIGESTS
        if document.get("kind") in CLOCKED_ARTIFACTS:
            removed |= {"sha256", "size_bytes"}
        return {k: clockless(v) for k, v in document.items() if k not in removed}
    if isinstance(document, list):
        return [clockless(item) for item in document]
    return document


@pytest.mark.usefixtures("single_threaded")
def test_every_cli_operation_through_api_equals_dispatch(tmp_path: Path) -> None:
    """G14, the CLI half: the same scenario on twin projects, one through `api`, one through
    `dispatch` — equal responses, every operation the `cli` transport carries."""
    by_cli, by_dispatch = tmp_path / "cli", tmp_path / "dispatch"
    seeds = {seed(by_cli), seed(by_dispatch)}
    assert len(seeds) == 1, seeds
    revision_id, job_id = seeds.pop()
    bundle = tmp_path / "outside"
    shutil.copytree(by_cli / "jobs" / job_id / "bundle", bundle)
    requests = scenario(revision_id, job_id, bundle)
    carried = sorted(name for name, row in OPERATIONS.items() if "cli" in row.transports)
    assert sorted(name for name, _ in requests) == carried

    printed: dict[str, Any] = {}
    for name, request in requests:
        if OPERATIONS[name].response_schema is None:
            raw = tmp_path / f"{name}.bin"
            code, out, err = api(by_cli, name, request, "--raw-out", str(raw))
            assert (code, out, err) == (0, "", ""), name
            printed[name] = raw.read_bytes()
            continue
        code, out, err = api(by_cli, name, request)
        assert (code, err) == (0, ""), (name, out, err)
        assert out.endswith("\n") and out.count("\n") == 1, name
        printed[name] = json.loads(out)
        # The printed text is the response's canonical JSON (§11.5).
        assert out[:-1].encode("utf-8") == canonical_json(printed[name]), name

    with LocalApplication.open(by_dispatch) as application:
        for name, request in requests:
            expected = dispatch(application, name, request)
            if isinstance(expected, bytes):
                assert printed[name] == expected
            else:
                assert clockless(printed[name]) == clockless(expected), name


#: §5.8's codes in its table order, transcribed.
SECTION_5_8 = (
    "invalid_request",
    "document_not_canonical",
    "unauthenticated",
    "forbidden",
    "not_found",
    "idempotency_key_reused",
    "not_ready",
    "revision_not_ready",
    "revision_unsupported",
    "verification_weakening_refused",
    "budget_exceeds_ceiling",
    "limit_exceeded",
    "unsupported",
    "internal_error",
    # ADR 0035 D3 (M02): appended, so every earlier code keeps its exit code.
    "model_replacement_incompatible",
)


def test_the_exit_codes_are_2_to_16_in_section_5_8_order() -> None:
    assert dict(API_EXIT_CODES) == {code: 2 + index for index, code in enumerate(SECTION_5_8)}


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "project"
    LocalApplication.create(directory, project_id="w5b-refusals").close()
    yield directory
    with LocalApplication.open(directory) as application:
        assert lifecycle_violations(application) == {}


def refused(project: Path, name: str, request: Any, code: str, *extra: str) -> dict[str, Any]:
    """`api` refuses with `code`: the ApiError, printed as canonical JSON, and its exit code."""
    exit_code, out, _ = run_cli(
        ["api", name, "--project", str(project), "--json", request, *extra]
        if isinstance(request, str)
        else ["api", name, "--project", str(project), "--json", json.dumps(request), *extra]
    )
    document: dict[str, Any] = json.loads(out)
    assert out[:-1].encode("utf-8") == canonical_json(document)
    assert schema_errors("api-error.schema.json", document) == []
    assert (document["code"], exit_code) == (code, API_EXIT_CODES[code]), document
    return document


def test_each_reachable_api_error_exits_its_code(project: Path) -> None:
    """As the local owner, `unauthenticated` and `forbidden` cannot arise (§10.2)."""
    assert refused(project, "get_job", {}, "invalid_request")["detail"] == {"pointer": ""}
    assert refused(project, "get_job", '{"job_id": NaN}', "document_not_canonical")["detail"] == {
        "pointer": "/job_id"
    }
    refused(project, "get_job", {"job_id": "job-000099"}, "not_found")
    edits = [{"operation": "set", "path": ["title"], "value": "a"}]
    first = {"edits": edits, "expected_revision": None, "idempotency_key": "k"}
    code, _, _ = api(project, "commit_change", first)
    assert code == 0
    edits[0]["value"] = "b"
    refused(project, "commit_change", first, "idempotency_key_reused")
    refused(
        project,
        "submit_job",
        {"operation": "solve", "idempotency_key": "s", "body": {"revision_id": "r-none"}},
        "not_found",
    )


def test_the_cli_refuses_as_dispatch_does_and_audits_it(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown operation is `dispatch`'s own refusal; a request that does not parse (or
    repeats a key) is `invalid_request` at the root; an operation the table does not carry on
    the CLI is refused like an unknown one. Each is one audited refusal (§10.7)."""
    unknown = refused(project, "grant_policy", {}, "invalid_request")
    assert "grant_policy" not in unknown["detail"]["operations"]
    for text in ('{"job_id": ', '{"job_id": "job-000001", "job_id": "job-000002"}'):
        assert refused(project, "get_job", text, "invalid_request")["detail"] == {"pointer": ""}
    row = OPERATIONS["get_project"]
    monkeypatch.setitem(
        OPERATIONS, "get_project", dataclasses.replace(row, transports=("python", "http"))
    )
    off = refused(project, "get_project", {}, "invalid_request")
    assert "get_project" not in off["detail"]["operations"]
    monkeypatch.undo()
    with LocalApplication.open(project) as application:
        audit = application.store.audit_rows()
    assert [(row["operation"], row["outcome"], row["code"]) for row in audit[-4:]] == [
        ("grant_policy", "refused", "invalid_request"),
        ("get_job", "refused", "invalid_request"),
        ("get_job", "refused", "invalid_request"),
        ("get_project", "refused", "invalid_request"),
    ]


def test_a_call_that_is_never_made_exits_1(tmp_path: Path) -> None:
    code, out, err = run_cli(["api", "get_project", "--project", str(tmp_path), "--json", "{}"])
    assert (code, out) == (1, "") and "not a project" in err
    missing = str(tmp_path / "absent.json")
    code, out, err = run_cli(["api", "get_project", "--project", ".", "--json-file", missing])
    assert (code, out) == (1, "") and "cannot read the request" in err


def test_the_request_comes_from_a_file_or_stdin(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = tmp_path / "request.json"
    request.write_text('{"limit": 1}', encoding="utf-8")
    base = ["api", "list_revisions", "--project", str(project)]
    by_file = run_cli([*base, "--json-file", str(request)])
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"limit": 1}'))
    by_stdin = run_cli([*base, "--json-file", "-"])
    assert by_file == by_stdin == (0, '{"items":[],"next_cursor":null}\n', "")
    code, _, err = run_cli(["api", "get_project", "--project", str(project), "--raw-out", "x"])
    assert code == 2 and "--json" in err
    code, _, err = run_cli([*base, "--json", "{}", "--raw-out", str(tmp_path / "x")])
    assert code == 2 and "--raw-out" in err and not (tmp_path / "x").exists()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["serve-http", "--project", "p", "--host", "0.0.0.0"], "--allow-remote"),
        (["serve-http", "--project", "p", "--host", "example.org"], "--allow-remote"),
        (["serve-mcp", "--project", "p"], "no anonymous server"),
    ],
)
def test_the_servers_refuse_their_arguments_before_anything_runs(
    argv: list[str], message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-loopback host without `--allow-remote`, or no credential for `serve-mcp`, is a
    usage error (exit 2): nothing is opened, nothing is served."""
    monkeypatch.delenv(TOKEN_FILE_VARIABLE, raising=False)
    code, out, err = run_cli(argv)
    assert (code, out) == (2, "") and message in err


def test_the_servers_refuse_to_start_on_a_directory_that_is_no_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The servers are wired (W6e): each opens the project, and refuses to start — exit 1, the
    reason on stderr, nothing on stdout — when it cannot. There is no stub result any more."""
    pytest.importorskip("mcp")
    token = tmp_path / "token"
    token.write_text("prt_" + "A" * 43, encoding="utf-8")
    monkeypatch.delenv(TOKEN_FILE_VARIABLE, raising=False)
    code, out, err = run_cli(["serve-http", "--project", str(tmp_path), "--port", "0"])
    assert (code, out) == (1, "") and "serve-http: refused to start" in err
    code, out, err = run_cli(["serve-mcp", "--project", str(tmp_path), "--token-file", str(token)])
    assert (code, out) == (1, "") and "serve-mcp: refused to start" in err
    monkeypatch.setenv(TOKEN_FILE_VARIABLE, str(token))
    code, out, err = run_cli(["serve-mcp", "--project", str(tmp_path)])
    assert (code, out) == (1, "") and "serve-mcp: refused to start" in err


def test_serve_http_serves_an_owner_opened_with_the_process_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`serve-http` hands `bindings.http.serve` the project opened with the process executor
    (§9.1: a server's jobs each run in their own worker) and its arguments as given, and closes
    the owner once serving returns. (The conformance suite serves a real one over loopback.)"""
    pytest.importorskip("starlette")
    from openflowsheet.application.bindings import http
    from openflowsheet.application.jobs.executor import ProcessExecutor

    directory = tmp_path / "project"
    LocalApplication.create(directory, project_id="w6e-serve").close()
    seen: list[dict[str, Any]] = []

    def serve(owner: Any, **options: Any) -> None:
        assert isinstance(owner.executor, ProcessExecutor)
        assert owner.project_id == "w6e-serve"
        seen.append(options)

    monkeypatch.setattr(http, "serve", serve)
    argv = ["serve-http", "--project", str(directory), "--host", "::1", "--port", "9000"]
    assert run_cli(argv) == (0, "", "")
    assert seen == [{"host": "::1", "port": 9000, "allow_remote": False}]


def test_api_runs_jobs_inline_only(project: Path) -> None:
    """W5b-Q1: a one-shot `api` closes its project on return, and closing a process executor
    ends its jobs `cancelled(server_shutdown)`; so `api` has no `--executor` (the servers run
    the process executor)."""
    code, out, err = run_cli(
        ["api", "get_project", "--project", str(project), "--json", "{}", "--executor", "process"]
    )
    assert (code, out) == (2, "") and "--executor" in err


def test_the_console_script_writes_raw_bytes_to_stdout(tmp_path: Path) -> None:
    """One subprocess smoke test (§11.6 (3)): the module as the console script runs it, and the
    raw export's bytes, unaltered, on stdout."""
    directory = tmp_path / "project"
    _, job_id = seed(directory)
    artifact_id = f"{job_id}:bundle/solution-state.json"
    completed = subprocess.run(
        [sys.executable, "-m", "openflowsheet.application.cli", "api", "artifact_bytes"]
        + ["--project", str(directory), "--json", json.dumps({"artifact_id": artifact_id})],
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    assert completed.returncode == 0, completed.stderr
    with LocalApplication.open(directory) as application:
        assert completed.stdout == application.artifact_bytes(artifact_id)
    stored = directory / "jobs" / job_id / "bundle" / ARTIFACT_DIR / "solution-state.json"
    assert completed.stdout == stored.read_bytes()


if __name__ == "__main__" and sys.argv[1:] == ["--write-pins"]:
    import tempfile

    from openflowsheet.run.manifest import THREAD_VARIABLES

    for variable in THREAD_VARIABLES:
        os.environ[variable] = "1"
    with tempfile.TemporaryDirectory() as scratch:
        pins = capture_existing(Path(scratch) / "run")
    PINS.parent.mkdir(parents=True, exist_ok=True)
    PINS.write_text(json.dumps(pins, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(pins)} pins to {PINS.relative_to(REPO_ROOT)}")
