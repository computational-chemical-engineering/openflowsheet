"""V17's agent harness: one headless Claude Code session per (task, repetition) (T07 W7a).

Normative text: design note `docs/design/T07-jobs-and-bindings.md` §14.1 (what an agent run is),
§14.2 (what is recorded per run) and §17 D-Q7; `docs/derivations/T07-v17-tasks-spec.md` §4
(principals, fixtures, the final answer), §5 (the prompts: body plus registered footer), §8 (the
agent configuration) and §16 (O9, U1–U3); the W0.7 flag table in `docs/t07-measurements.md`. The
W7a canaries that pinned `AGENT` are recorded under `runs/canary/` and in the measurements log.

One run (`run`):

1. seeds the task's fixture project (`fixtures.build`, which grants `cap-agent-v17` and writes its
   token) under a work directory **outside the repository**: `<work>/<campaign>/<task>-<rep>/`
   holds `project/`, `secret/token` (mode 0600 in a 0700 directory), `mcp.json`, and `cwd/`, the
   empty directory the session runs in. The token is never under `cwd/`, never in the run record,
   and never on a command line: `mcp.json` names the file through `OPENFLOWSHEET_TOKEN_FILE`,
   and the session has no file or shell tool with which to read it (`--tools ""`);
2. launches `claude` (`command`) with a whitelisted environment (`session_environment`): no
   `ANTHROPIC_API_KEY`, no `CLAUDE_*` variable of an enclosing session, so the existing login is
   what authenticates and nothing of the operator's session leaks in; `--setting-sources ""`
   keeps the operator's settings and CLAUDE.md out (canary ii, `AGENT`);
3. streams the transcript to `transcript.jsonl` line by line, counting turns (`TurnCounter`), and
   enforces the wall cap (and, only where `--max-turns` is not passed, the turn cap) by killing the
   session's process group (`run_session`);
4. records §14.2's items in `benchmarks/t07/v17/runs/<campaign>/<task>-<rep>/` (`run.json`,
   `prompt.txt`, `transcript.jsonl`, `result.json`, `mcp.json`, `stderr.txt`), exports the store
   (`export.write`) and scores it (`scorer.score` → `scores.json`).

A campaign's registration (Amendment R6.7, R6.9) chooses the reference
(`scorer.CAMPAIGN_REFERENCES`: `v17-c2` reads `t07_reference_c2.json`), the prompt
(`campaign_prompt`, FX-12 against that registration) and the configuration (`REGISTERED_CONFIGS`:
`v17-c2` runs `AGENT_C2`); `run.json` records the campaign and the reference's SHA-256 (CAMP-01).
A new `v17-c2` starts only when the preconditions P1–P8 hold (`preflight.require`).

`run.json` is written twice: first, before anything is launched, with `infrastructure_failure`
set to `harness_incomplete`, so a run the harness never finishes is recorded as an
infrastructure failure and not silently re-run; last, with the session's outcome.

The campaign (`campaign`) takes the registered order (`scorer.run_order`: repetition-major, T01…T10
within each repetition), never re-runs a run whose directory exists, counts infrastructure failures
as failures (the scorer does, from `run.json`), stops at a run whose `init` message shows it
outside the registered configuration (`session_checks`), and writes `campaign.json`
(`scorer.aggregate`). It is W7d's; W7a builds it and does not run it.

Operator identity (spec §8 "Operator identity (R6)", Amendment R6.6). Claude Code 2.1.283 puts the
login's e-mail address into every session's context: its user context gains a `userEmail` section
from `oauthAccount.emailAddress` of the global config (`$CLAUDE_CONFIG_DIR/.claude.json`, else
`~/.claude.json`) whenever the session authenticates through the claude.ai login. No flag removes
it (`--setting-sources`, `--safe-mode` and `--system-prompt` do not touch the user context;
`--bare` refuses the login). A configuration with `operator_isolation` therefore gives the session
an empty `CLAUDE_CONFIG_DIR` of its own under the work directory, which holds no account, and
authenticates it with `CLAUDE_CODE_OAUTH_TOKEN` read at run time from a token file (`Operator`).
The harness reads the address at run time too, only to count it (`identifier_hits`) in the
run's files; it is written to no file (RUN-ID-SCAN). The identity canaries (`identity_canary`,
CAN-ii-e and its control) run in the evidence artifacts directory, which git ignores, and commit
only their verdict and counts.

Infrastructure failures (scorer A1/A9) are the causes the scorer cannot see in the files: the wall
cap, the budget guard, a service error (an `is_error` result that is not the turn cap), a session
that exits without a `result` message, and the harness's own turn cap (a fallback outside the
registered configuration). Reaching `--max-turns` is the agent's outcome, not
an infrastructure failure: its `result` message (`error_max_turns`) and final text are scored as
they are.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import IO, Any, Final

from benchmarks.t07.v17 import export, fixtures, scorer
from openflowsheet.canonical import canonical_json

REFERENCE: Final[dict[str, Any]] = scorer.load_reference()
REGISTERED: Final[Mapping[str, Any]] = REFERENCE["agent_configuration"]
REPO_ROOT: Final[Path] = scorer.REPO_ROOT
RUNS_ROOT: Final[Path] = Path(__file__).resolve().parent / "runs"
CANARY_CAMPAIGN: Final[str] = "canary"
SERVER_NAME: Final[str] = str(REGISTERED["mcp_server_name"])
ALLOWED_TOOLS: Final[str] = str(REGISTERED["allowed_tools"])
AGENT_PRINCIPAL: Final[str] = REFERENCE["constants"]["agent"]["principal_id"]
#: §14.1: the MCP server the session starts, the application's own `serve-mcp`.
SERVE_MCP_MODULE: Final[str] = "openflowsheet.application.cli"
TOKEN_FILE_VARIABLE: Final[str] = "OPENFLOWSHEET_TOKEN_FILE"
#: O9: `total_cost_usd` on the subscription login is Claude Code's estimate, not a bill.
COST_BASIS: Final[str] = "subscription_estimate"
#: The aliases `--model` also accepts (W0.7); a run record must carry a pinned id (spec §17).
MODEL_ALIASES: Final[frozenset[str]] = frozenset({"fable", "opus", "sonnet", "haiku", "default"})
#: The environment the session inherits; everything else (an API key, the enclosing session's
#: `CLAUDE_*` variables, its effort and model settings) is dropped.
ENVIRONMENT_KEEP: Final[tuple[str, ...]] = (
    "HOME",
    "USER",
    "LOGNAME",
    "PATH",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
)
#: Seconds between SIGTERM and SIGKILL when the harness stops a session.
KILL_GRACE_S: Final[float] = 10.0
INCOMPLETE: Final[str] = "harness_incomplete"
PROMPT_FILE: Final[str] = "prompt.txt"
MCP_FILE: Final[str] = "mcp.json"
STDERR_FILE: Final[str] = "stderr.txt"
CAMPAIGN_FILE: Final[str] = "campaign.json"
#: §8 R6: the variables that isolate the session from the operator's account.
CONFIG_DIR_VARIABLE: Final[str] = "CLAUDE_CONFIG_DIR"
OAUTH_TOKEN_VARIABLE: Final[str] = "CLAUDE_CODE_OAUTH_TOKEN"
#: The global config file whose `oauthAccount.emailAddress` Claude Code puts into the context.
GLOBAL_CONFIG_FILE: Final[str] = ".claude.json"
#: R6.6: the files RUN-ID-SCAN and CAN-ii-e search for the operator address.
SCANNED_FILES: Final[tuple[str, ...]] = (
    scorer.TRANSCRIPT_FILE,
    scorer.RESULT_FILE,
    STDERR_FILE,
    scorer.STORE_EXPORT_FILE,
)
#: Seconds a token must stay valid beyond the wall cap when the token file records its expiry.
TOKEN_MARGIN_S: Final[float] = 300.0


class HarnessError(RuntimeError):
    """The harness refuses a configuration or a directory; nothing was launched."""


# =============================================================================================
# The agent configuration (spec §8)
# =============================================================================================


@dataclass(frozen=True)
class AgentConfig:
    """Spec §8's registered values, and the flags W0.7 and the W7a canaries settled.

    `max_turns_flag` says whether `--max-turns` is passed (canary iv); when it is not, the harness
    stops the session itself once the stream shows more than `max_turns` turns. `isolation` holds
    the flags that keep the operator's CLAUDE.md, memory and settings out of the session (D-Q7,
    canary ii). `operator_isolation` (§8 R6) gives the session its own empty Claude Code config
    directory and a token, so that the login's account, and with it the e-mail address, is not
    in its context (module docstring).
    """

    model: str
    effort: str
    max_turns: int
    max_turns_flag: bool
    wall_cap_s: float
    max_budget_usd: float
    isolation: tuple[str, ...]
    claude: str = "claude"
    operator_isolation: bool = False

    def check(self) -> None:
        """Spec §17 "watch for": a model alias instead of a pinned id."""
        if self.model in MODEL_ALIASES or not self.model.startswith("claude-"):
            raise HarnessError(f"--model {self.model!r} is not a pinned model id")
        if not self.effort:
            raise HarnessError("the effort is not pinned")

    def as_document(self) -> dict[str, Any]:
        document = asdict(self)
        document["isolation"] = list(self.isolation)
        return document


#: The registered configuration: spec §8 with the values W7a read (Claude Code 2.1.283).
#:
#: - `model`: the `model` of every canary's `init` message for `--model claude-sonnet-5`, the
#:   Sonnet 5 id of this version's compiled model catalog (Frank: one pinned Sonnet id).
#: - `effort`: 2.1.283's default for that model, `default_effort: "high"` in the compiled catalog
#:   (and the catalog lookup's own fallback). The session's effective default can also come from
#:   the organisation or a served flag, which is why it is passed explicitly (spec U3).
#: - `max_turns_flag`: canary (iv) — the parser accepts `--max-turns` (it is not in `--help`) and
#:   a session with `--max-turns 2` ended `error_max_turns` after two assistant turns.
#: - `isolation`: canary (ii). `--setting-sources ""` drops user, project and local settings, and
#:   with them the user CLAUDE.md (the loader reads it only when `userSettings` is a source): the
#:   session answered NONE, while the same text without it quoted `~/.claude/CLAUDE.md`.
#:   `--safe-mode` (spec §8's first choice) also drops the `--mcp-config` server: canary c1's
#:   `init` listed no MCP server and no tool, so it is not usable (W0.7 E4).
AGENT: Final[AgentConfig] = AgentConfig(
    model="claude-sonnet-5",
    effort="high",
    max_turns=int(REGISTERED["max_turns"]),
    max_turns_flag=True,
    wall_cap_s=float(REGISTERED["wall_cap_s"]),
    max_budget_usd=float(REGISTERED["max_budget_usd"]),
    isolation=("--setting-sources", ""),
)
#: `v17-c2`'s configuration (Amendment R6.7 (4)): `v17-c1`'s pins, plus operator identity
#: isolation (§8 R6, CAN-ii-e).
AGENT_C2: Final[AgentConfig] = replace(AGENT, operator_isolation=True)
#: The init message's `apiKeySource` on the existing login: no separately billed key (Frank).
LOGIN_KEY_SOURCE: Final[str] = "none"


@dataclass(frozen=True)
class Operator:
    """What operator identity isolation needs at run time (§8 R6): the login's e-mail address,
    which RUN-ID-SCAN counts, and the file the OAuth token of an isolated session is read from,
    afresh before each session (a campaign outlives a login's access token). The address and the
    token are never written to a file or shown by `repr`."""

    address: str = field(repr=False)
    token_file: Path | None = None

    def oauth_token(self, config: AgentConfig) -> str:
        """The token, valid for `config`'s whole wall cap (`read_oauth_token`)."""
        if self.token_file is None:
            raise HarnessError("operator_identity_isolation: unsupported(no operator token)")
        return read_oauth_token(self.token_file, config.wall_cap_s + TOKEN_MARGIN_S)


def operator_address(environment: Mapping[str, str] | None = None) -> str:
    """The login's address, where Claude Code reads it: `oauthAccount.emailAddress` of the
    operator's global config (`$CLAUDE_CONFIG_DIR/.claude.json`, else `~/.claude.json`)."""
    environment = os.environ if environment is None else environment
    base = environment.get(CONFIG_DIR_VARIABLE) or environment.get("HOME") or str(Path.home())
    try:
        config = json.loads((Path(base) / GLOBAL_CONFIG_FILE).read_text(encoding="utf-8"))
        address = config["oauthAccount"]["emailAddress"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HarnessError(
            f"operator_identity_isolation: unsupported(the login's address is unreadable: "
            f"{type(error).__name__})"
        ) from None
    if not isinstance(address, str) or "@" not in address:
        raise HarnessError("operator_identity_isolation: unsupported(no login address)")
    return address


def read_oauth_token(path: Path, min_valid_s: float) -> str:
    """The token in `path`: a Claude Code credentials file (`claudeAiOauth.accessToken`, refused
    when `expiresAt` falls within `min_valid_s`) or a file holding only the token (as
    `claude setup-token` prints it). The file must be readable by its owner only."""
    if path.stat().st_mode & 0o077:
        raise HarnessError(f"{path} is readable by others")
    text = path.read_text(encoding="utf-8").strip()
    try:
        document = json.loads(text)
    except ValueError:
        document = None
    if isinstance(document, Mapping):
        oauth = document.get("claudeAiOauth")
        token = oauth.get("accessToken") if isinstance(oauth, Mapping) else None
        expires = oauth.get("expiresAt") if isinstance(oauth, Mapping) else None
        if not isinstance(token, str) or not token:
            raise HarnessError(f"{path} holds no claudeAiOauth.accessToken")
        if isinstance(expires, int | float) and expires / 1000.0 < time.time() + min_valid_s:
            raise HarnessError(f"the token in {path} expires within {min_valid_s:.0f} s")
        return token
    if not text or any(character.isspace() for character in text):
        raise HarnessError(f"{path} does not hold one token")
    return text


def login_operator(token_file: Path | None, config: AgentConfig) -> Operator:
    """The operator: the address from the operator's own config and, for an isolated
    configuration, a token file whose token is valid now for the whole wall cap."""
    operator = Operator(address=operator_address(), token_file=token_file)
    if config.operator_isolation:
        operator.oauth_token(config)
    return operator


def identifier_hits(run_dir: Path, address: str) -> dict[str, int]:
    """RUN-ID-SCAN: occurrences of `address`, case-insensitively, in each of the run's
    `SCANNED_FILES` (0 for an absent file). Only counts leave this function."""
    pattern = re.compile(re.escape(address.encode("utf-8")), re.IGNORECASE)
    return {
        name: len(pattern.findall((run_dir / name).read_bytes()))
        if (run_dir / name).is_file()
        else 0
        for name in SCANNED_FILES
    }


def _number_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(value)


def command(config: AgentConfig, prompt: str, mcp_json: Path) -> list[str]:
    """§14.1's command line. The prompt is the only positional argument and follows `-p`
    directly: every later option either takes one value or is variadic and followed by
    another option, so no option can swallow it."""
    argv = [
        config.claude,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--mcp-config",
        str(mcp_json),
        "--strict-mcp-config",
        "--tools",
        "",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--permission-prompts",
        "none",
        "--model",
        config.model,
        "--effort",
        config.effort,
        "--max-budget-usd",
        _number_text(config.max_budget_usd),
        "--no-session-persistence",
        *config.isolation,
    ]
    if config.max_turns_flag:
        argv += ["--max-turns", str(config.max_turns)]
    return argv


def mcp_config(project: Path, token_file: Path) -> dict[str, Any]:
    """§14.1's `mcp.json`: this checkout's `serve-mcp` over the fixture project, run by this
    interpreter with this checkout's `src` first on `PYTHONPATH`; the token by file name."""
    return {
        "mcpServers": {
            SERVER_NAME: {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-m", SERVE_MCP_MODULE, "serve-mcp", "--project", str(project)],
                "env": {
                    "PYTHONPATH": str(REPO_ROOT / "src"),
                    TOKEN_FILE_VARIABLE: str(token_file),
                },
            }
        }
    }


def session_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """The whitelisted environment of the session (`ENVIRONMENT_KEEP`)."""
    source = os.environ if source is None else source
    return {key: source[key] for key in ENVIRONMENT_KEEP if key in source}


# =============================================================================================
# The work directory: outside the repository, the token outside the session's cwd
# =============================================================================================


@dataclass(frozen=True)
class WorkPaths:
    root: Path
    project: Path
    token_file: Path
    mcp_json: Path
    cwd: Path
    #: §8 R6: the isolated session's own Claude Code config directory (empty when it starts).
    config_dir: Path


def work_paths(work: Path, campaign: str, name: str) -> WorkPaths:
    root = work.resolve() / campaign / name
    return WorkPaths(
        root=root,
        project=root / "project",
        token_file=root / "secret" / "token",
        mcp_json=root / MCP_FILE,
        cwd=root / "cwd",
        config_dir=root / "claude-config",
    )


def check_outside_repository(path: Path) -> None:
    """§14.1: the session's directory is outside the repository, and no ancestor holds a
    `CLAUDE.md` or a `.git` that Claude Code's discovery could find by walking up."""
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise HarnessError(f"{resolved} is inside the repository {REPO_ROOT}")
    for directory in (resolved, *resolved.parents):
        for marker in ("CLAUDE.md", ".git"):
            if (directory / marker).exists():
                raise HarnessError(f"{directory / marker} is visible from {resolved}")


def prepare(paths: WorkPaths) -> None:
    """Create the empty session directory; the fixture writes the project and the token."""
    if paths.root.exists():
        raise HarnessError(f"{paths.root} exists; a run is never repeated in place")
    check_outside_repository(paths.root)
    paths.cwd.mkdir(parents=True)
    paths.token_file.parent.mkdir(mode=0o700, parents=True)


def check_token_placement(paths: WorkPaths) -> None:
    """The token is readable by its owner only and lies outside the session's directory."""
    token = paths.token_file.resolve()
    cwd = paths.cwd.resolve()
    if token == cwd or cwd in token.parents:
        raise HarnessError("the token file is inside the session's working directory")
    if token.stat().st_mode & 0o077 or token.parent.stat().st_mode & 0o077:
        raise HarnessError("the token file or its directory is readable by others")
    if any(cwd.iterdir()):
        raise HarnessError(f"the session's working directory {cwd} is not empty")


# =============================================================================================
# One session: stream, count turns, enforce the caps
# =============================================================================================


class TurnCounter:
    """Turns in a stream-json transcript: the distinct `message.id`s of `assistant` lines.

    Claude Code may split one assistant message over several lines with one id (scorer A2); a
    line without an id counts as its own turn."""

    def __init__(self) -> None:
        self._ids: set[str] = set()
        self._anonymous = 0
        self.init: dict[str, Any] | None = None
        self.result_line: bytes | None = None

    @property
    def turns(self) -> int:
        return len(self._ids) + self._anonymous

    def feed(self, line: bytes) -> None:
        try:
            entry = json.loads(line)
        except ValueError:
            return
        if not isinstance(entry, dict):
            return
        kind = entry.get("type")
        if kind == "assistant":
            message = entry.get("message")
            identifier = message.get("id") if isinstance(message, dict) else None
            if isinstance(identifier, str):
                self._ids.add(identifier)
            else:
                self._anonymous += 1
        elif kind == "system" and entry.get("subtype") == "init" and self.init is None:
            self.init = entry
        elif kind == "result":
            self.result_line = line.rstrip(b"\n")


def count_turns(lines: Sequence[bytes]) -> int:
    counter = TurnCounter()
    for line in lines:
        counter.feed(line)
    return counter.turns


@dataclass(frozen=True)
class SessionOutcome:
    returncode: int | None
    wall_s: float
    stopped: str | None
    turns: int
    init: dict[str, Any] | None
    result: dict[str, Any] | None
    result_line: bytes | None


def _stop(process: subprocess.Popen[bytes], grace_s: float) -> None:
    """SIGTERM the session's process group (claude and the MCP server it started), then
    SIGKILL after `grace_s`."""
    for sig, wait in ((signal.SIGTERM, grace_s), (signal.SIGKILL, None)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        if wait is None:
            break
        try:
            process.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def run_session(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    transcript: Path,
    stderr: Path,
    wall_cap_s: float,
    turn_cap: int | None,
    kill_grace_s: float = KILL_GRACE_S,
) -> SessionOutcome:
    """Run `argv` in its own process group, copying stdout line by line to `transcript`.

    The wall cap stops the session after `wall_cap_s`; `turn_cap` (None when `--max-turns` is
    passed, as registered) stops it once the stream shows more turns than that. A session the
    turn cap stops has no `result` message, which the scorer reads as an infrastructure failure
    (A9): the harness's own turn cap is a fallback for a Claude Code without `--max-turns`."""
    counter = TurnCounter()
    stopped: list[str] = []
    started = time.monotonic()
    with transcript.open("wb") as sink, stderr.open("wb") as errors:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=errors,
            start_new_session=True,
        )
        stdout: IO[bytes] | None = process.stdout
        assert stdout is not None

        def pump() -> None:
            for line in stdout:
                sink.write(line)
                sink.flush()
                counter.feed(line)
                if turn_cap is not None and counter.turns > turn_cap and not stopped:
                    stopped.append("turn_cap")
                    threading.Thread(
                        target=_stop, args=(process, kill_grace_s), daemon=True
                    ).start()

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        try:
            process.wait(timeout=wall_cap_s)
        except subprocess.TimeoutExpired:
            if not stopped:
                stopped.append("wall_cap")
            _stop(process, kill_grace_s)
            process.wait()
        reader.join(timeout=60.0)
    result: dict[str, Any] | None = None
    if counter.result_line is not None:
        loaded = json.loads(counter.result_line)
        result = loaded if isinstance(loaded, dict) else None
    return SessionOutcome(
        returncode=process.returncode,
        wall_s=time.monotonic() - started,
        stopped=stopped[0] if stopped else None,
        turns=counter.turns,
        init=counter.init,
        result=result,
        result_line=counter.result_line,
    )


def infrastructure_failure(outcome: SessionOutcome) -> dict[str, str] | None:
    """Scorer A1/A9: the causes only the harness sees. `--max-turns` is the agent's outcome."""
    if outcome.stopped == "wall_cap":
        return {"reason": "wall_cap"}
    if outcome.stopped == "turn_cap":
        return {"reason": "harness_turn_cap"}
    result = outcome.result
    if result is None:
        return {"reason": f"no_result_message (exit {outcome.returncode})"}
    subtype = str(result.get("subtype"))
    if "budget" in subtype:
        return {"reason": "budget_guard"}
    if subtype == "error_max_turns":
        return None
    if subtype != "success" or result.get("is_error") is True:
        return {"reason": f"service_error ({subtype})"}
    return None


# =============================================================================================
# Provenance: versions, commit, digests
# =============================================================================================


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tool_descriptions_sha256() -> str:
    """§14.2: SHA-256 of the canonical JSON of the MCP binding's tool list (name, description,
    inputSchema), as `list_tools` serves it."""
    from openflowsheet.application.bindings import mcp

    tools = [tool.model_dump(mode="json", exclude_none=True) for tool in mcp.tools()]
    return hashlib.sha256(canonical_json(tools)).hexdigest()


def claude_version(claude: str) -> str:
    completed = subprocess.run(
        [claude, "--version"], capture_output=True, text=True, check=True, timeout=60
    )
    return completed.stdout.strip()


def git_state() -> dict[str, Any]:
    """The commit, and whether anything outside `runs/` differs from it."""

    def git(*arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), *arguments],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    runs = RUNS_ROOT.relative_to(REPO_ROOT).as_posix()
    try:
        dirty = git("status", "--porcelain", "--", ".", f":(exclude){runs}")
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(dirty)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _utc_now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


#: The `init` members a run records: what the session was given (model, tools, server, key
#: source) and what customisation Claude Code still loaded (D-Q7).
INIT_MEMBERS: Final[tuple[str, ...]] = (
    "model",
    "claude_code_version",
    "apiKeySource",
    "permissionMode",
    "tools",
    "mcp_servers",
    "plugins",
    "skills",
    "agents",
    "output_style",
    "memory_paths",
)


def init_summary(init: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if init is None:
        return None
    return {key: init[key] for key in INIT_MEMBERS if key in init}


def auto_memory_files(init: Mapping[str, Any] | None) -> list[str] | None:
    """D-Q7: the files in the session's auto-memory directory (Claude Code creates it empty
    for a new working directory; the agent has no tool that could write to it)."""
    paths = init.get("memory_paths") if init is not None else None
    directory = paths.get("auto") if isinstance(paths, Mapping) else None
    if not isinstance(directory, str):
        return None
    root = Path(directory)
    if not root.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def session_checks(config: AgentConfig, init: Mapping[str, Any] | None) -> list[str]:
    """What the `init` message must show for a run to be in the registered configuration: the
    pinned model, the existing login (no API key), the `procsim` server connected, and tools
    from it only. A campaign stops at the first run that fails one (the run itself is kept)."""
    if init is None:
        return ["no init message"]
    problems: list[str] = []
    if init.get("model") != config.model:
        problems.append(f"model {init.get('model')!r} is not {config.model!r}")
    if init.get("apiKeySource") != LOGIN_KEY_SOURCE:
        problems.append(f"apiKeySource {init.get('apiKeySource')!r} is not the existing login")
    servers = init.get("mcp_servers")
    connected = [
        server
        for server in (servers if isinstance(servers, list) else [])
        if isinstance(server, Mapping)
        and server.get("name") == SERVER_NAME
        and server.get("status") == "connected"
    ]
    if not connected:
        problems.append(f"the {SERVER_NAME} server is not connected")
    tools = init.get("tools")
    prefix = f"mcp__{SERVER_NAME}__"
    if not isinstance(tools, list) or not tools:
        problems.append("the session was given no tool")
    else:
        outside = [tool for tool in tools if not str(tool).startswith(prefix)]
        if outside:
            problems.append(f"tools outside {prefix}*: {outside}")
    return problems


def _write_json(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# =============================================================================================
# A run
# =============================================================================================


@dataclass(frozen=True)
class Session:
    """What `launch` returns: the session's outcome and the run record's session members."""

    outcome: SessionOutcome
    record: dict[str, Any]


def launch(
    config: AgentConfig,
    prompt: str,
    paths: WorkPaths,
    run_dir: Path,
    *,
    environment: Mapping[str, str] | None = None,
    oauth_token: str | None = None,
) -> Session:
    """Write `mcp.json`, run the session in `paths.cwd`, and record the transcript, the result
    message, the prompt and the configuration in `run_dir`. Under `operator_isolation` the
    session gets its own empty config directory and `oauth_token` (§8 R6)."""
    check_token_placement(paths)
    check_outside_repository(paths.cwd)
    env = session_environment(environment)
    if config.operator_isolation:
        if oauth_token is None:
            raise HarnessError("operator_identity_isolation: unsupported(no operator token)")
        paths.config_dir.mkdir(mode=0o700)
        env[CONFIG_DIR_VARIABLE] = str(paths.config_dir)
        env[OAUTH_TOKEN_VARIABLE] = oauth_token
    mcp_document = mcp_config(paths.project, paths.token_file)
    _write_json(paths.mcp_json, mcp_document)
    _write_json(run_dir / MCP_FILE, mcp_document)
    (run_dir / PROMPT_FILE).write_text(prompt, encoding="utf-8")
    argv = command(config, prompt, paths.mcp_json)
    started_at = _utc_now()
    outcome = run_session(
        argv,
        cwd=paths.cwd,
        env=env,
        transcript=run_dir / scorer.TRANSCRIPT_FILE,
        stderr=run_dir / STDERR_FILE,
        wall_cap_s=config.wall_cap_s,
        turn_cap=None if config.max_turns_flag else config.max_turns,
    )
    if outcome.result_line is not None:
        (run_dir / scorer.RESULT_FILE).write_bytes(outcome.result_line + b"\n")
    record = {
        "agent_configuration": config.as_document(),
        "model": config.model,
        "command": [*argv[:2], f"<{PROMPT_FILE}>", *argv[3:]],
        "environment_keys": sorted(env),
        "session": {
            "started_at": started_at,
            "ended_at": _utc_now(),
            "wall_s": round(outcome.wall_s, 3),
            "returncode": outcome.returncode,
            "stopped": outcome.stopped,
            "turns_counted": outcome.turns,
            "init": init_summary(outcome.init),
            "auto_memory_files": auto_memory_files(outcome.init),
            "checks": session_checks(config, outcome.init),
        },
        "sha256": {
            "task_text": sha256_text(prompt),
            "tool_descriptions": tool_descriptions_sha256(),
            "transcript": hashlib.sha256(
                (run_dir / scorer.TRANSCRIPT_FILE).read_bytes()
            ).hexdigest(),
        },
    }
    return Session(outcome=outcome, record=record)


def run(
    task_id: str,
    repetition: int,
    campaign: str,
    *,
    work: Path,
    config: AgentConfig = AGENT,
    runs_root: Path = RUNS_ROOT,
    environment: Mapping[str, str] | None = None,
    operator: Operator | None = None,
) -> Path:
    """One (task, repetition): fixture, session, record, export, score. Returns the run
    directory `runs_root/<campaign>/<task>-<rep>`.

    The campaign chooses the registration (`scorer.CAMPAIGN_REFERENCES`: the prompt, and the
    reference whose SHA-256 `run.json` records, CAMP-01) and, for a registered campaign, the
    only configuration it may run with (`REGISTERED_CONFIGS`). Under `operator_isolation` the
    run's files are scanned for the operator address after the export (RUN-ID-SCAN)."""
    config.check()
    reference = scorer.load_reference(scorer.reference_path(campaign))
    if task_id not in reference["tasks"]:
        raise HarnessError(f"unknown task {task_id!r}")
    check_registered_config(campaign, config)
    oauth_token = _session_token(config, operator)
    task_prompt = campaign_prompt(reference, task_id)
    name = f"{task_id}-{repetition}"
    run_dir = runs_root / campaign / name
    paths = work_paths(work, campaign, name)
    if run_dir.exists():
        raise HarnessError(f"{run_dir} exists; a run is never repeated")
    prepare(paths)
    run_dir.mkdir(parents=True)
    version = claude_version(config.claude)
    base: dict[str, Any] = {
        "task_id": task_id,
        "repetition": repetition,
        "campaign": campaign,
        "reference_sha256": scorer.reference_file_sha256(campaign),
        "session_principal": AGENT_PRINCIPAL,
        "cost_basis": COST_BASIS,
        "claude_code_version": version,
        "git": git_state(),
    }
    _write_json(
        run_dir / scorer.RUN_FILE, {**base, "infrastructure_failure": {"reason": INCOMPLETE}}
    )
    fixture = fixtures.build(task_id, paths.project, paths.token_file)
    session = launch(
        config, task_prompt, paths, run_dir, environment=environment, oauth_token=oauth_token
    )
    record = {
        **base,
        **session.record,
        "fixture_digest": fixture.digest,
        "session_start": fixture.session_start,
        "infrastructure_failure": infrastructure_failure(session.outcome),
    }
    _write_json(run_dir / scorer.RUN_FILE, record)
    export.write(fixture.project, fixture.session_start, run_dir)
    if config.operator_isolation:
        assert operator is not None
        hits = identifier_hits(run_dir, operator.address)
        record["operator_identifier_hits"] = sum(hits.values())
        record["operator_identifier_hits_by_file"] = hits
        _write_json(run_dir / scorer.RUN_FILE, record)
    (run_dir / scorer.SCORES_FILE).write_bytes(scorer.dump(scorer.score(run_dir)))
    return run_dir


def _session_token(config: AgentConfig, operator: Operator | None) -> str | None:
    """The isolated session's token, read before anything of the run is created, so that a
    missing or expiring token refuses the run instead of recording a failure."""
    if not config.operator_isolation:
        return None
    if operator is None:
        raise HarnessError("operator_identity_isolation: unsupported(no operator token)")
    return operator.oauth_token(config)


#: Amendment R6.7 (4): the configuration each registered campaign runs with (`claude` aside).
REGISTERED_CONFIGS: Final[Mapping[str, AgentConfig]] = {"v17-c1": AGENT, "v17-c2": AGENT_C2}


def check_registered_config(campaign: str, config: AgentConfig) -> None:
    """A registered campaign runs only in its registered configuration."""
    registered = REGISTERED_CONFIGS.get(campaign)
    if registered is not None and replace(config, claude=registered.claude) != registered:
        raise HarnessError(f"{campaign} runs only with its registered configuration")


def campaign_prompt(reference: Mapping[str, Any], task_id: str) -> str:
    """§4.4's prompt under `reference`, as `fixtures.prompt` builds it under `v17-c1`'s; FX-12
    against the campaign being seeded: it must hash as that registration says (Amendment
    R6.11, `fixtures.py`)."""
    task = reference["tasks"][task_id]
    footer = (
        str(reference["footer_template"])
        .replace("<TASK_ID>", task_id)
        .replace("<ANSWER_MEMBERS>", task["answer_members"])
    )
    text = str(task["body"]) + "\n\n" + footer
    if sha256_text(text) != task["prompt_sha256"]:
        raise HarnessError(f"FX-12: {task_id}'s prompt does not hash as registered")
    return text


# =============================================================================================
# The campaign (W7d; not run in W7a)
# =============================================================================================

RunFunction = Callable[..., Path]


def recorded_checks(run_dir: Path) -> list[str]:
    """`session_checks` as `run.json` recorded them (none for a run without a session)."""
    path = run_dir / scorer.RUN_FILE
    if not path.is_file():
        return []
    session = json.loads(path.read_text(encoding="utf-8")).get("session")
    checks = session.get("checks") if isinstance(session, Mapping) else None
    return [str(problem) for problem in checks] if isinstance(checks, list) else []


def campaign(
    name: str,
    *,
    work: Path,
    config: AgentConfig = AGENT,
    runs_root: Path = RUNS_ROOT,
    resume: bool = False,
    run_one: RunFunction = run,
    operator: Operator | None = None,
    preflight: Callable[[], None] | None = None,
) -> Path:
    """Spec §7.6: every (task, repetition) once, in the registered order; a run whose
    directory exists — finished, failed, or abandoned by the harness — is never run again.
    A new campaign refuses an existing directory; `resume` continues one after an interruption
    without touching what it holds. Writes `campaign.json`, the scorer's aggregation.

    `v17-c2` starts only when P1–P8 hold (Amendment R6.8): a new `v17-c2` runs `preflight`
    (default `benchmarks.t07.v17.preflight.require`) before anything is created."""
    config.check()
    if name == CANARY_CAMPAIGN:
        raise HarnessError("the canary directory is not a campaign")
    check_registered_config(name, config)
    reference = scorer.load_reference(scorer.reference_path(name))
    campaign_dir = runs_root / name
    if campaign_dir.exists() and not resume:
        raise HarnessError(f"{campaign_dir} exists; a campaign is never re-run (resume continues)")
    if not resume and git_state()["dirty"] is not False:
        raise HarnessError("the checkout is not a clean commit; a campaign runs on a commit")
    if not resume and "preconditions" in reference.get("registration", {}):
        if preflight is None:
            from benchmarks.t07.v17 import preflight as preconditions

            preflight = preconditions.require
        preflight()
    campaign_dir.mkdir(parents=True, exist_ok=True)
    for task_id, repetition in scorer.run_order(reference):
        if (campaign_dir / f"{task_id}-{repetition}").exists():
            continue
        run_dir = run_one(
            task_id,
            repetition,
            name,
            work=work,
            config=config,
            runs_root=runs_root,
            operator=operator,
        )
        problems = recorded_checks(run_dir)
        if problems:
            raise HarnessError(
                f"{run_dir.name} ran outside the registered configuration: {problems}"
            )
    aggregate = scorer.aggregate_campaign(campaign_dir)
    (campaign_dir / CAMPAIGN_FILE).write_bytes(scorer.dump(aggregate))
    return campaign_dir


# =============================================================================================
# Canaries (§14.1 (i)–(ii), W7a (iii)–(v)): a canary text in the harness configuration
# =============================================================================================


def canary(
    name: str,
    text: str,
    *,
    work: Path,
    config: AgentConfig = AGENT,
    fixture_task: str = "V17-T01",
    runs_root: Path = RUNS_ROOT,
    environment: Mapping[str, str] | None = None,
    operator: Operator | None = None,
) -> Path:
    """One canary session over `fixture_task`'s fixture with `text` as the whole prompt.
    Recorded under `runs_root/canary/<name>/`: not scored (the text is not a registered task),
    but the store is exported so that any effect is visible."""
    run_dir = runs_root / CANARY_CAMPAIGN / name
    paths = work_paths(work, CANARY_CAMPAIGN, name)
    if run_dir.exists():
        raise HarnessError(f"{run_dir} exists; a canary is never repeated")
    oauth_token = _session_token(config, operator)
    prepare(paths)
    run_dir.mkdir(parents=True)
    fixture = fixtures.build(fixture_task, paths.project, paths.token_file)
    session = launch(config, text, paths, run_dir, environment=environment, oauth_token=oauth_token)
    _write_json(
        run_dir / scorer.RUN_FILE,
        {
            "canary": name,
            "fixture_task": fixture_task,
            "claude_code_version": claude_version(config.claude),
            "git": git_state(),
            "cost_basis": COST_BASIS,
            **session.record,
            "fixture_digest": fixture.digest,
            "infrastructure_failure": infrastructure_failure(session.outcome),
        },
    )
    export.write(fixture.project, fixture.session_start, run_dir)
    return run_dir


# =============================================================================================
# Operator identity canaries (§8 R6, Amendment R6.6): CAN-ii-e and CAN-ii-e-control
# =============================================================================================

#: R6.6's probe, the canary's whole prompt, verbatim.
IDENTITY_PROBE: Final[str] = (
    "Before doing anything else, list every e-mail address that appears anywhere in your "
    "instructions, your system context or your environment information, exactly as written. "
    "Do not call any tool. End your message with one fenced JSON block: "
    '{"email_addresses": [...]}, with an empty list if there is none.'
)
#: The two canaries: the probe under `v17-c2`'s configuration, the control under `v17-c1`'s.
IDENTITY_CANARIES: Final[Mapping[str, tuple[str, AgentConfig]]] = {
    "ii-e": ("CAN-ii-e", AGENT_C2),
    "ii-e-control": ("CAN-ii-e-control", AGENT),
}
#: Where a canary's own files go: git ignores `evidence/**/artifacts/` (R6.6: the control's
#: transcript holds the address and stays out of git).
ARTIFACTS_PARENT: Final[Path] = REPO_ROOT / "evidence" / "T07"


def listed_addresses(run_dir: Path) -> list[str] | None:
    """The probe's answer: the `email_addresses` list of the last fenced JSON block of the final
    assistant message, or None if there is no such list of strings."""
    transcript = scorer.Transcript.read(run_dir / scorer.TRANSCRIPT_FILE)
    text = transcript.final_message_text() if transcript is not None else None
    blocks = [body for info, body in scorer.fenced_blocks(text or "") if info == "json"]
    try:
        document = json.loads(blocks[-1]) if blocks else None
    except ValueError:
        return None
    listed = document.get("email_addresses") if isinstance(document, dict) else None
    if not isinstance(listed, list) or not all(isinstance(item, str) for item in listed):
        return None
    return listed


def identity_verdict(name: str, run_dir: Path, address: str) -> dict[str, Any]:
    """R6.6's mechanical judgement of one identity canary, as counts and booleans only.

    CAN-ii-e passes iff the list parses and is empty and no scanned file holds the address;
    CAN-ii-e-control passes iff the parsed list holds the address (case-insensitively). If the
    control fails, the probe is insensitive and CAN-ii-e is not established."""
    acceptance, _ = IDENTITY_CANARIES[name]
    listed = listed_addresses(run_dir)
    hits = identifier_hits(run_dir, address)
    wanted = address.casefold()
    in_list = listed is not None and any(item.strip().casefold() == wanted for item in listed)
    if name == "ii-e":
        passed = listed == [] and sum(hits.values()) == 0
    else:
        passed = in_list
    return {
        "acceptance": acceptance,
        "passed": passed,
        "parsed": listed is not None,
        "listed_count": len(listed) if listed is not None else None,
        "operator_address_listed": in_list,
        "operator_identifier_hits": sum(hits.values()),
        "operator_identifier_hits_by_file": hits,
    }


def identity_canary(
    name: str,
    *,
    work: Path,
    operator: Operator,
    artifacts: Path,
    claude: str | None = None,
    runs_root: Path = RUNS_ROOT,
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Run one identity canary over the T01 fixture into `artifacts/canary/<name>/` (outside
    git), judge it, and write only the verdict and counts to `runs_root/canary/<name>/run.json`.
    Returns that file."""
    if name not in IDENTITY_CANARIES:
        raise HarnessError(f"unknown identity canary {name!r}")
    _, config = IDENTITY_CANARIES[name]
    if claude is not None:
        config = replace(config, claude=claude)
    record_dir = runs_root / CANARY_CAMPAIGN / name
    if record_dir.exists():
        raise HarnessError(f"{record_dir} exists; a canary is never repeated")
    run_dir = canary(
        name,
        IDENTITY_PROBE,
        work=work,
        config=config,
        runs_root=artifacts,
        environment=environment,
        operator=operator,
    )
    recorded = json.loads((run_dir / scorer.RUN_FILE).read_text(encoding="utf-8"))
    init = recorded.get("session", {}).get("init") or {}
    files = sorted(path for path in run_dir.iterdir() if path.is_file())
    summary = {
        "canary": name,
        **identity_verdict(name, run_dir, operator.address),
        "probe_sha256": sha256_text(IDENTITY_PROBE),
        "fixture_task": recorded["fixture_task"],
        "agent_configuration": recorded["agent_configuration"],
        "environment_keys": recorded["environment_keys"],
        "claude_code_version": recorded["claude_code_version"],
        "git": recorded["git"],
        "model": init.get("model"),
        "apiKeySource": init.get("apiKeySource"),
        "session_checks": recorded["session"]["checks"],
        "infrastructure_failure": recorded["infrastructure_failure"],
        "cost_basis": COST_BASIS,
        "total_cost_usd": _recorded_cost(run_dir),
        "artifacts": {
            "directory": _shown(run_dir),
            "sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        },
    }
    record_dir.mkdir(parents=True)
    _write_json(record_dir / scorer.RUN_FILE, summary)
    return record_dir / scorer.RUN_FILE


def _recorded_cost(run_dir: Path) -> Any:
    path = run_dir / scorer.RESULT_FILE
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("total_cost_usd")


def _shown(path: Path) -> str:
    """A path relative to the repository when it lies inside it (no user name recorded)."""
    resolved = path.resolve()
    if REPO_ROOT not in resolved.parents:
        return "<outside>"
    return resolved.relative_to(REPO_ROOT).as_posix()


# =============================================================================================
# CLI
# =============================================================================================


def _configured(arguments: argparse.Namespace) -> AgentConfig:
    """The campaign's registered configuration (`REGISTERED_CONFIGS`), else `AGENT`."""
    campaign_name = getattr(arguments, "campaign", None) or getattr(arguments, "name", None)
    config = REGISTERED_CONFIGS.get(campaign_name, AGENT) if campaign_name else AGENT
    if getattr(arguments, "claude", None):
        config = replace(config, claude=arguments.claude)
    return config


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else None)
    parser.add_argument("--claude", default=None, help="the claude binary (default: claude)")
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("command", help="print a task's command line and mcp.json; run nothing")
    show.add_argument("--task", required=True, choices=tuple(REFERENCE["tasks"]))
    show.add_argument("--work", required=True, type=Path)
    one = sub.add_parser("run", help="one (task, repetition)")
    one.add_argument("--task", required=True, choices=tuple(REFERENCE["tasks"]))
    one.add_argument("--rep", required=True, type=int)
    one.add_argument("--campaign", required=True)
    one.add_argument("--work", required=True, type=Path)
    many = sub.add_parser("campaign", help="the thirty runs in the registered order (W7d)")
    many.add_argument("--name", required=True)
    many.add_argument("--work", required=True, type=Path)
    many.add_argument("--resume", action="store_true")
    for with_token in (one, many):
        with_token.add_argument(
            "--oauth-token-file",
            type=Path,
            default=None,
            help="an isolated configuration's token (§8 R6): a credentials file or a setup-token",
        )
    sub.add_parser("preflight", help="P1–P8 for v17-c2 (Amendment R6.8); exit 1 unless all hold")
    probe = sub.add_parser("canary", help="one canary session (W7a)")
    probe.add_argument("--name", required=True)
    probe.add_argument("--text-file", required=True, type=Path, help="the canary text (UTF-8)")
    probe.add_argument("--work", required=True, type=Path)
    probe.add_argument("--max-turns", type=int, default=None, help="override, canary iv only")
    probe.add_argument(
        "--no-isolation",
        action="store_true",
        help="drop the isolation flags: canary ii's positive control only",
    )
    identity = sub.add_parser(
        "canary-identity", help="CAN-ii-e or its control (§8 R6); files under the artifacts"
    )
    identity.add_argument("--name", required=True, choices=tuple(IDENTITY_CANARIES))
    identity.add_argument("--work", required=True, type=Path)
    identity.add_argument(
        "--oauth-token-file",
        type=Path,
        default=None,
        help="the isolated session's token (a credentials file or a setup-token); ii-e only",
    )
    arguments = parser.parse_args(argv)
    if arguments.command == "canary-identity":
        _, identity_config = IDENTITY_CANARIES[arguments.name]
        if identity_config.operator_isolation and arguments.oauth_token_file is None:
            parser.error("ii-e needs --oauth-token-file")
        operator = login_operator(arguments.oauth_token_file, identity_config)
        commit = git_state()["commit"] or "uncommitted"
        print(
            identity_canary(
                arguments.name,
                work=arguments.work,
                operator=operator,
                artifacts=ARTIFACTS_PARENT / commit / "artifacts",
                claude=arguments.claude,
            )
        )
        return 0
    if arguments.command == "preflight":
        from benchmarks.t07.v17 import preflight

        report = preflight.run_all()
        print(json.dumps(report, indent=1, sort_keys=True))
        return 0 if all(item["passed"] for item in report.values()) else 1
    config = _configured(arguments)
    session_operator: Operator | None = None
    if arguments.command in ("run", "campaign") and config.operator_isolation:
        if arguments.oauth_token_file is None:
            parser.error("this campaign isolates the operator's account: --oauth-token-file")
        session_operator = login_operator(arguments.oauth_token_file, config)
    if arguments.command == "command":
        paths = work_paths(arguments.work, "<campaign>", f"{arguments.task}-<rep>")
        argv_shown = command(config, f"<{PROMPT_FILE}>", paths.mcp_json)
        print(json.dumps(argv_shown))
        print(json.dumps(mcp_config(paths.project, paths.token_file), indent=1))
        return 0
    if arguments.command == "run":
        print(
            run(
                arguments.task,
                arguments.rep,
                arguments.campaign,
                work=arguments.work,
                config=config,
                operator=session_operator,
            )
        )
        return 0
    if arguments.command == "campaign":
        print(
            campaign(
                arguments.name,
                work=arguments.work,
                config=config,
                resume=arguments.resume,
                operator=session_operator,
            )
        )
        return 0
    if arguments.max_turns is not None:
        config = replace(config, max_turns=arguments.max_turns)
    if arguments.no_isolation:
        config = replace(config, isolation=())
    text = arguments.text_file.read_text(encoding="utf-8").strip()
    print(canary(arguments.name, text, work=arguments.work, config=config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
