"""The command line: `validate`, `solve`, `inspect`, `replay`, `project`, `api`, `serve-http`,
`serve-mcp`. K06, gates G02 and G06; T07 §10.3, §11.5.

Blueprint D15: local Python and CLI share one contract and neither requires a network round
trip. So this module is thin on purpose — it parses arguments, calls the application layer,
and prints. Anything it computed for itself would be behaviour a Python caller could not get.

**G06 is "the end-to-end example is inspectable without unrelated code".** That is what
`inspect` is for: point it at a bundle and it prints what the run was, what was checked, what
was found and what was not claimed — without the reader importing anything, reading a test, or
knowing which of eleven modules to start from.

**T07 (design note §11.5): `api` is the CLI binding of the contract.**
`openflowsheet api <operation> --project DIR (--json '<request>' | --json-file F)
[--raw-out FILE]` opens the project as `LOCAL_OWNER` (§10.2), sends the request document through
`operations.dispatch` — the one path every binding takes — and prints the response as canonical
JSON. Exit 0 is a domain result, whatever its status; an `ApiError` is printed the same way and
exits `API_EXIT_CODES[code]`, 2–16 in §5.8's order. Exit 1 means no call was made: the request
file could not be read or the project could not be opened (the message is on stderr).

`api` runs jobs on the inline executor only. §11.5 names `--executor inline|process`, but a
one-shot command closes its project when it returns, and closing a process executor ends every
job it still runs `cancelled(server_shutdown)` (§9.3) — so the process executor belongs to the
servers, which live as long as their jobs (build-lane decision W5b-Q1, `docs/T07_DECISIONS.md`).

**The servers** (§11.2, §10.2). `serve-http` opens the project with the process executor and
serves it with `bindings.http.serve` until interrupted (with `--ui`, `bindings.web.serve`, which
adds the diagnostic web shell at `/ui/`, M06); `serve-mcp` is `serving.serve_mcp`, over stdio.
Both need the `server` extra; without it, or when the project cannot be opened, or (`--ui`) when
the shell's packaged files are missing, they refuse to start with exit 1 and the reason on stderr.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, get_args

from openflowsheet.application.types import ApiErrorCode
from openflowsheet.application.validation import validate

if TYPE_CHECKING:
    from openflowsheet.application.local import LocalApplication

#: §11.5: an `ApiError`'s exit code, 2–16 in §5.8's table order (`ApiErrorCode`'s order). 0 is a
#: domain result; 1 is a call that was never made. argparse's own usage error is also 2.
API_EXIT_CODES: Final[Mapping[str, int]] = {
    code: 2 + index for index, code in enumerate(get_args(ApiErrorCode))
}
#: §10.2: where `serve-mcp` finds its token file when `--token-file` is not given.
TOKEN_FILE_VARIABLE: Final[str] = "OPENFLOWSHEET_TOKEN_FILE"


def _load(path: Path) -> Any:
    import yaml

    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text) if path.suffix in (".yaml", ".yml") else json.loads(text)


def command_validate(arguments: argparse.Namespace) -> int:
    """Blueprint §4.3: a status is computed from a revision and a task, never set.

    A task v0.1 does not validate for (`optimization`, U05) is refused before any analysis: the
    typed error document is printed as `api` prints one, and the command exits its §5.8 code.
    """
    from openflowsheet.application.contract import ApplicationError

    try:
        report = validate(_load(Path(arguments.revision)), arguments.task)
    except ApplicationError as refused:
        _print_document(refused.error.as_document())
        return API_EXIT_CODES[refused.code]
    if arguments.json:
        print(json.dumps(report.as_document(), indent=1, sort_keys=True))
        return 0 if report.status != "INVALID" else 1

    print(f"revision  {report.revision_id}")
    print(f"task      {report.task}")
    print(f"status    {report.status}")
    marks = {"PASS": "ok  ", "FAIL": "FAIL", "WARN": "warn", "NOT_RUN": "  - "}
    for check in report.checks:
        print(f"  [{marks[check.result]}] {check.id}: {check.message}")
        if check.implicated_objects:
            print(f"           implicated: {', '.join(check.implicated_objects)}")
    if report.structural_counts is None:
        print(f"\nstructural counts: not computed — {report.structural_counts_absent_reason}")
    else:
        counts = report.structural_counts
        print(
            f"\nstructural counts: {counts['equations']} equations, "
            f"{counts['free_variables']} free variables, {counts['matched']} matched, "
            f"{counts['unmatched']} unmatched"
        )
    return 0 if report.status != "INVALID" else 1


def command_solve(arguments: argparse.Namespace) -> int:
    """Solve a registered SYN-001 case, verify it, and write a replay bundle."""
    from openflowsheet.application.revision_run import registered_case, registered_flowsheet
    from openflowsheet.run.session import run_session

    case = registered_case(arguments.case)
    if case is None:
        print(f"no registered case {arguments.case!r}", file=sys.stderr)
        return 2

    directory = Path(arguments.out)
    manifest = run_session(registered_flowsheet(case), directory, run_id=arguments.case)

    print(f"case              {arguments.case}")
    print(f"outcome           {manifest.outcome}")
    print(f"verification      {manifest.verification_status}")
    print(f"structural sha256 {manifest.structural_sha256}")
    print(f"bundle            {directory}")
    return 0 if manifest.verification_status == "VERIFIED" else 1


def command_inspect(arguments: argparse.Namespace) -> int:
    """G06: what a run was, what was checked, what was found, what was **not** claimed."""
    from openflowsheet.run.bundle import read_artifact, read_manifest, verify_bundle

    directory = Path(arguments.bundle)
    manifest, _ = read_manifest(directory)
    integrity = verify_bundle(directory)

    print("=== run")
    print(f"  id                {manifest.run_id}")
    print(f"  model             {manifest.model_version}")
    print(f"  outcome           {manifest.outcome}")
    print(f"  verification      {manifest.verification_status}")
    print(f"  structural sha256 {manifest.structural_sha256}")
    print(f"  integrity         {'ok' if integrity.ok else 'FAILED ' + str(integrity)}")

    print("\n=== environment (provenance; recorded, not part of the identity)")
    for key, value in sorted(manifest.environment.as_document().items()):
        print(f"  {key:<22}{value}")

    if "solution-certificate.json" in manifest.artifacts:
        certificate = read_artifact(directory, "solution-certificate.json")
        checks = certificate["checks"]
        by_result: dict[str, int] = {}
        for check in checks:
            by_result[check["result"]] = by_result.get(check["result"], 0) + 1
        print(f"\n=== certificate  {certificate['verification_status']}")
        print(f"  checks            {len(checks)} ({by_result})")
        print(f"  regularity        {certificate['regularity']['status']}")
        print(f"  solution bound    {certificate['solution_error_bound_scaled']}")
        failing = [check["id"] for check in checks if check["result"] == "fail"]
        if failing:
            print(f"  FAILING           {failing}")
        print("\n=== what this certificate does not claim")
        for statement in certificate["statements"]:
            print(f"  - {statement}")
        if certificate["limitations"]:
            print("\n=== limitations")
            for limitation in certificate["limitations"]:
                print(f"  - {limitation}")

    if "failure-bundle.json" in manifest.artifacts:
        bundle = read_artifact(directory, "failure-bundle.json")
        print(f"\n=== failure  {bundle['outcome']}")
        print(f"  taxonomy          {bundle['taxonomy']}")
        print(f"  implicated        {bundle['implicated_sources']}")
        for action in bundle["suggested_actions"]:
            print(f"  suggested         {action['action']} (requires permission)")

    events = read_artifact(directory, "solve-events.json")
    print(f"\n=== trace  {len(events)} events")
    for event in events:
        outcome = f" -> {event['outcome']}" if event.get("outcome") else ""
        print(f"  {event['sequence']:>3}  {event['kind']:<16} attempt {event['attempt']}{outcome}")
    return 0 if integrity.ok else 1


def command_replay(arguments: argparse.Namespace) -> int:
    """ADR 0007 D4: the mode is decided from the environment before anything runs.

    `--rerun` is the application's `reproduce_bundle` (T08 review 2, Ruling 11, reversing T07
    D-Q6 for the CLI): a bundle with `revision.json` reruns its recorded route, a K05 bundle
    reruns only when its `run_id` is a registered case, and anything else is not rerun —
    `NOT_RUN`, with the reason (`rerun_unsupported(no_revision_document)` for an unknown run id).
    There is no fallback to SYN-001-nominal: a verdict about another problem's rerun is a wrong
    result. Exit 0 iff the verdict is `MATCH`, or `NOT_RUN` when `--rerun` was not given.
    """
    from openflowsheet.run.replay import replay

    directory = Path(arguments.bundle)
    if arguments.rerun:
        import tempfile

        from openflowsheet.application.revision_run import reproduce_bundle

        with tempfile.TemporaryDirectory() as scratch:
            report = reproduce_bundle(
                directory, rerun=True, rerun_directory=Path(scratch) / "rerun", run_id="replay"
            ).report
    else:
        report = replay(directory, None)
    if arguments.json:
        print(json.dumps(report.as_document(), indent=1, sort_keys=True))
    else:
        print(f"mode      {report.mode}")
        print(f"verdict   {report.verdict}")
        print(f"integrity {'ok' if report.integrity.ok else report.integrity.as_document()}")
        print(f"bitwise   {report.bitwise_floats}")
        for reason in report.reasons:
            print(f"  reason  {reason}")
        for difference in report.differences[:20]:
            print(f"  differs {difference}")
    return (
        0
        if report.verdict == "MATCH" or (report.verdict == "NOT_RUN" and not arguments.rerun)
        else 1
    )


def command_project_init(arguments: argparse.Namespace) -> int:
    """T07 §10.3: a new project directory — store, empty policy, owner and job folders."""
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.store import StoreError

    try:
        application = LocalApplication.create(arguments.directory, project_id=arguments.project_id)
    except StoreError as error:
        print(str(error), file=sys.stderr)
        return 2
    with application:
        print(f"project   {application.project_id}")
        print(f"directory {arguments.directory}")
    return 0


def command_project_grant(arguments: argparse.Namespace) -> int:
    """T07 §10.3: add a grant; print its token once — only the token's SHA-256 is stored."""
    from openflowsheet.application.authz import grant
    from openflowsheet.application.store import StoreError
    from openflowsheet.application.types import Limits

    try:
        capability, token = grant(
            Path(arguments.project),
            principal_id=arguments.principal,
            rights=[right.strip() for right in arguments.rights.split(",") if right.strip()],
            limits=Limits(
                default_wall_time_s=arguments.default_wall_time_s,
                max_wall_time_s=arguments.max_wall_time_s,
                max_active_jobs=arguments.max_active_jobs,
            ),
            expires_at=arguments.expires_at,
            note=arguments.note,
            capability_id=arguments.capability_id,
        )
    except (ValueError, StoreError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"capability {capability.capability_id}")
    print(f"principal  {capability.principal_id}")
    print(f"rights     {','.join(capability.rights)}")
    print(f"token      {token}")
    print("(the token is shown once; the project stores only its SHA-256)")
    return 0


def command_project_revoke(arguments: argparse.Namespace) -> int:
    """T07 §10.3: remove a grant; servers see it on their next call."""
    from openflowsheet.application.authz import revoke
    from openflowsheet.application.store import StoreError

    try:
        capability = revoke(Path(arguments.project), arguments.capability)
    except (ValueError, StoreError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"revoked    {capability.capability_id} (principal {capability.principal_id})")
    return 0


def _print_document(document: Any) -> None:
    from openflowsheet.canonical import canonical_json

    sys.stdout.write(canonical_json(document).decode("utf-8") + "\n")


def _request_text(arguments: argparse.Namespace) -> str:
    if arguments.json is not None:
        return str(arguments.json)
    if arguments.json_file == "-":
        return sys.stdin.read()
    return Path(arguments.json_file).read_text(encoding="utf-8")


def command_api(arguments: argparse.Namespace) -> int:
    """§11.5: one operation of `OPERATIONS` through `dispatch`, as `LOCAL_OWNER`."""
    from openflowsheet.application.authz import PolicyRefusedError
    from openflowsheet.application.contract import ApplicationError
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.operations import OPERATIONS, dispatch
    from openflowsheet.application.store import StoreError

    name = arguments.operation
    operation = OPERATIONS.get(name)
    if (
        arguments.raw_out is not None
        and operation is not None
        and operation.response_schema is not None
    ):
        print(f"--raw-out is for an operation whose response is bytes, not {name}", file=sys.stderr)
        return 2
    try:
        text = _request_text(arguments)
    except (OSError, UnicodeDecodeError) as error:
        print(f"cannot read the request: {error}", file=sys.stderr)
        return 1
    try:
        application = LocalApplication.open(arguments.project)
    except (StoreError, PolicyRefusedError) as error:
        print(str(error), file=sys.stderr)
        return 1
    with application:
        try:
            response = dispatch(application, name, _request(application, name, text))
        except ApplicationError as refused:
            _print_document(refused.error.as_document())
            return API_EXIT_CODES[refused.code]
    if isinstance(response, bytes):
        if arguments.raw_out is None:
            sys.stdout.buffer.write(response)
        else:
            Path(arguments.raw_out).write_bytes(response)
        return 0
    _print_document(response)
    return 0


def _request(application: LocalApplication, name: str, text: str) -> Any:
    """The request document `text` holds, parsed as `canonical.load_document` parses (duplicate
    keys refused). An operation the CLI does not carry is refused as `dispatch` refuses an
    unknown one; a request that does not parse is refused `invalid_request` at the root. Both
    are audited (§10.7). A non-canonical *value* is `dispatch`'s to refuse (§12.5)."""
    import yaml

    from openflowsheet.application.contract import ApplicationError
    from openflowsheet.application.operations import OPERATIONS, dispatch, project_error
    from openflowsheet.application.types import ApiError
    from openflowsheet.canonical import load_document

    operation = OPERATIONS.get(name)
    if operation is None:
        dispatch(application, name, {})  # refuses an unknown operation, audited, whatever the body
    assert operation is not None
    if "cli" not in operation.transports:
        application.audit_refusal(name, "invalid_request")
        carried = sorted(row.name for row in OPERATIONS.values() if "cli" in row.transports)
        raise ApplicationError(
            project_error(
                ApiError(
                    code="invalid_request",
                    message="no such operation on the command line",
                    retryable=False,
                    detail={"operation": name, "operations": carried},
                )
            )
        )
    try:
        return load_document(text, source="the request")
    except (ValueError, yaml.YAMLError) as error:
        print(f"the request does not parse: {error}", file=sys.stderr)
        application.audit_refusal(name, "invalid_request")
        raise ApplicationError(
            project_error(
                ApiError(
                    code="invalid_request",
                    message="the request is not one JSON document, or it repeats a key",
                    retryable=False,
                    detail={"pointer": ""},
                )
            )
        ) from None


def _loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def command_serve_http(arguments: argparse.Namespace) -> int:
    """§11.2: `serve-http --project DIR [--host 127.0.0.1] [--port 8765] [--allow-remote]
    [--ui]`. `--ui` (M06, ADR 0030 D3) also serves the diagnostic web shell at `/ui/`
    (`bindings.web`); without it nothing differs, and `bindings.web` is not even imported."""
    if not _loopback(arguments.host) and not arguments.allow_remote:
        print(
            f"--host {arguments.host} is not loopback: pass --allow-remote (there is no TLS in "
            "v0.1)",
            file=sys.stderr,
        )
        return 2
    from openflowsheet.application.authz import PolicyRefusedError
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.store import StoreError

    try:
        from openflowsheet.application.bindings import http as binding
    except ImportError:
        print(
            "serve-http: refused to start: the HTTP server needs the `server` extra: "
            "pip install 'openflowsheet[server]'",
            file=sys.stderr,
        )
        return 1
    serve = binding.serve
    if arguments.ui:
        from openflowsheet.application.bindings import web

        try:
            web.static_directory()
        except web.WebShellMissingError as error:
            print(f"serve-http: refused to start: {error}", file=sys.stderr)
            return 1
        serve = web.serve
    try:
        application = LocalApplication.open(arguments.project, executor="process")
    except (StoreError, PolicyRefusedError) as error:
        print(f"serve-http: refused to start: {error}", file=sys.stderr)
        return 1
    with application:
        serve(
            application,
            host=arguments.host,
            port=arguments.port,
            allow_remote=arguments.allow_remote,
        )
    return 0


def command_serve_mcp(arguments: argparse.Namespace) -> int:
    """§10.2: `serve-mcp --project DIR --token-file FILE` (or `OPENFLOWSHEET_TOKEN_FILE`);
    there is no anonymous server."""
    if arguments.token_file is None and not os.environ.get(TOKEN_FILE_VARIABLE):
        print(
            f"serve-mcp needs --token-file or {TOKEN_FILE_VARIABLE}; there is no anonymous server",
            file=sys.stderr,
        )
        return 2
    from openflowsheet.application.serving import serve_mcp

    return serve_mcp(arguments.project, arguments.token_file)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openflowsheet",
        description=(
            "The v0.0 local contract: validate a revision, solve a registered case, inspect "
            "a run, replay a bundle. Every command is a thin wrapper over the same "
            "application layer a Python caller uses (blueprint D15)."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate_command = commands.add_parser("validate", help="validate a revision for a task")
    validate_command.add_argument("revision", help="a ProcessRevision YAML or JSON file")
    validate_command.add_argument(
        "--task", choices=("simulation", "optimization"), default="simulation"
    )
    validate_command.add_argument("--json", action="store_true")
    validate_command.set_defaults(handler=command_validate)

    solve_command = commands.add_parser("solve", help="solve a registered SYN-001 case")
    solve_command.add_argument("case", help="a registered case id, e.g. SYN-001-nominal")
    solve_command.add_argument("--out", required=True, help="where to write the replay bundle")
    solve_command.set_defaults(handler=command_solve)

    inspect_command = commands.add_parser("inspect", help="inspect a replay bundle")
    inspect_command.add_argument("bundle")
    inspect_command.set_defaults(handler=command_inspect)

    replay_command = commands.add_parser("replay", help="replay a bundle and report")
    replay_command.add_argument("bundle")
    replay_command.add_argument(
        "--rerun", action="store_true", help="solve again and compare, rather than inspect"
    )
    replay_command.add_argument("--json", action="store_true")
    replay_command.set_defaults(handler=command_replay)

    project_command = commands.add_parser(
        "project", help="create a project and administer its capability grants"
    )
    project_commands = project_command.add_subparsers(dest="project_command", required=True)
    init_command = project_commands.add_parser("init", help="create a project directory")
    init_command.add_argument("directory")
    init_command.add_argument("--project-id", default=None)
    init_command.set_defaults(handler=command_project_init)

    grant_command = project_commands.add_parser(
        "grant", help="grant rights to a principal and print its token once"
    )
    grant_command.add_argument("--project", required=True, help="the project directory")
    grant_command.add_argument("--principal", required=True)
    grant_command.add_argument(
        "--rights", default="read,draft,execute", help="comma-separated, of the six rights"
    )
    grant_command.add_argument("--default-wall-time-s", type=float, default=300.0)
    grant_command.add_argument("--max-wall-time-s", type=float, default=1800.0)
    grant_command.add_argument("--max-active-jobs", type=int, default=4)
    grant_command.add_argument("--expires-at", default=None, help="YYYY-MM-DDTHH:MM:SS.ffffffZ")
    grant_command.add_argument("--note", default="", help="a label; never read for authority")
    grant_command.add_argument("--capability-id", default=None)
    grant_command.set_defaults(handler=command_project_grant)

    revoke_command = project_commands.add_parser("revoke", help="remove a grant")
    revoke_command.add_argument("--project", required=True, help="the project directory")
    revoke_command.add_argument("--capability", required=True)
    revoke_command.set_defaults(handler=command_project_revoke)

    api_command = commands.add_parser(
        "api",
        help="run one contract operation as the local owner and print its response",
        description=(
            "Send one request document through the operations table, as the in-process "
            "local owner, and print the response as canonical JSON. Exit 0 is a domain "
            f"result; 2-16 is an ApiError, in the order {', '.join(API_EXIT_CODES)}; 1 "
            "means no call was made."
        ),
    )
    api_command.add_argument("operation", help="an operation of the table, e.g. get_project")
    api_command.add_argument("--project", required=True, help="the project directory")
    request_source = api_command.add_mutually_exclusive_group(required=True)
    request_source.add_argument("--json", default=None, help="the request document")
    request_source.add_argument(
        "--json-file", default=None, help="a file holding the request document ('-': stdin)"
    )
    api_command.add_argument(
        "--raw-out", default=None, help="artifact_bytes: write the bytes here, not to stdout"
    )
    api_command.set_defaults(handler=command_api)

    http_command = commands.add_parser("serve-http", help="serve the project over HTTP (§11.2)")
    http_command.add_argument("--project", required=True, help="the project directory")
    http_command.add_argument("--host", default="127.0.0.1")
    http_command.add_argument("--port", type=int, default=8765)
    http_command.add_argument(
        "--allow-remote", action="store_true", help="needed for a non-loopback --host"
    )
    http_command.add_argument(
        "--ui",
        action="store_true",
        help="also serve the diagnostic web shell at /ui/ — static files only; every data "
        "request needs a bearer token",
    )
    http_command.set_defaults(handler=command_serve_http)

    mcp_command = commands.add_parser("serve-mcp", help="serve the project over MCP stdio (§10.2)")
    mcp_command.add_argument("--project", required=True, help="the project directory")
    mcp_command.add_argument(
        "--token-file", default=None, help=f"the capability's token (else ${TOKEN_FILE_VARIABLE})"
    )
    mcp_command.set_defaults(handler=command_serve_mcp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    handler = arguments.handler
    return int(handler(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
