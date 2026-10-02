"""T07 W7a: V17's agent harness, offline (no `claude` binary is run).

Design note §14.1–§14.2, spec §8. A fake `claude` (a Python script written per test) stands in for
the session; the recorded canary transcripts under `benchmarks/t07/v17/runs/canary/` stand in
for a real stream.

- **Command construction**: the registered flags, the prompt as the only positional argument, no
  variadic option followed by a value it could swallow, a model alias refused.
- **Token placement**: the token file is 0600 in a 0700 directory, outside the session's
  directory, named only through `mcp.json`'s environment, and in no recorded file.
- **Run-directory layout**: one run writes §14.2's files and a `run.json` with scorer A1's
  members; `scores.json` is the scorer's output for that directory.
- **Wall cap**: a session that outlives the cap is killed and recorded as an infrastructure
  failure; the harness's own turn cap stops a session that streams too many turns.
- **Turn counting**: on canary (iv)'s recorded stream, and on a message split over two lines.
- **A campaign never re-runs**: the registered order, an existing run directory skipped, a second
  campaign of one name refused, a run outside the configuration stopping the campaign.
"""

from __future__ import annotations

import json
import stat
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from benchmarks.t07.v17 import harness, scorer

CANARIES = harness.RUNS_ROOT / harness.CANARY_CAMPAIGN
VARIADIC = ("--mcp-config", "--tools", "--allowedTools")

FINAL = {"task_id": "V17-T01", "status": "failed", "claims": [], "answer": {}}
INIT = {
    "type": "system",
    "subtype": "init",
    "model": harness.AGENT.model,
    "apiKeySource": "none",
    "claude_code_version": "0.0.0",
    "mcp_servers": [{"name": "procsim", "status": "connected"}],
    "tools": ["mcp__procsim__get_project"],
    "memory_paths": {},
}


def _lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fake_claude(directory: Path, mode: str) -> Path:
    """A stand-in `claude`: `--version` prints a version; otherwise it writes what it saw (argv,
    cwd listing, environment keys) to `seen.json` beside itself and streams per `mode`."""
    final = "Done.\n\n```json\n" + json.dumps(FINAL) + "\n```"
    result = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 1,
        "total_cost_usd": 0.01,
        "duration_ms": 5,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    script = directory / f"claude-{mode}"
    script.write_text(
        f"""#!/usr/bin/env python3
import json, os, sys, time
if sys.argv[1:] == ["--version"]:
    print("0.0.0 (Fake Claude)")
    sys.exit(0)
seen = {{"argv": sys.argv, "cwd": sorted(os.listdir(".")), "env": sorted(os.environ)}}
with open({str(directory / "seen.json")!r}, "w") as handle:
    json.dump(seen, handle)
def emit(entry):
    print(json.dumps(entry), flush=True)
emit({INIT!r})
mode = {mode!r}
if mode == "answer":
    content = [{{"type": "text", "text": {final!r}}}]
    emit({{"type": "assistant", "message": {{"id": "msg_1", "content": content}}}})
    emit({result!r})
elif mode == "sleep":
    time.sleep(120)
elif mode == "turns":
    for k in range(1000):
        emit({{"type": "assistant", "message": {{"id": f"msg_{{k}}", "content": []}}}})
        time.sleep(0.02)
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


# =============================================================================================
# Command construction
# =============================================================================================


def test_command_is_the_registered_configuration(tmp_path: Path) -> None:
    argv = harness.command(harness.AGENT, "the task", tmp_path / "mcp.json")
    assert argv[:3] == ["claude", "-p", "the task"]
    assert argv.count("the task") == 1

    def value(flag: str) -> str:
        return argv[argv.index(flag) + 1]

    assert value("--output-format") == "stream-json" and "--verbose" in argv
    assert value("--mcp-config") == str(tmp_path / "mcp.json") and "--strict-mcp-config" in argv
    assert value("--tools") == "" and value("--allowedTools") == "mcp__procsim__*"
    assert value("--permission-prompts") == "none"
    assert value("--model") == "claude-sonnet-5" and value("--effort") == "high"
    assert value("--max-budget-usd") == "5" and value("--max-turns") == "60"
    assert value("--setting-sources") == ""
    assert "--no-session-persistence" in argv
    # Canary c1: --safe-mode drops the --mcp-config server; nothing may bypass permissions.
    for absent in ("--safe-mode", "--bare", "--dangerously-skip-permissions", "--fallback-model"):
        assert absent not in argv
    for flag in VARIADIC:
        following = argv[argv.index(flag) + 2 :]
        assert not following or following[0].startswith("--"), flag


def test_turn_flag_is_omitted_when_the_harness_counts() -> None:
    config = replace(harness.AGENT, max_turns_flag=False)
    assert "--max-turns" not in harness.command(config, "x", Path("m.json"))


@pytest.mark.parametrize("model", ["sonnet", "opus", "default", "gpt-5"])
def test_a_model_alias_is_refused(model: str) -> None:
    with pytest.raises(harness.HarnessError):
        replace(harness.AGENT, model=model).check()
    harness.AGENT.check()


def test_the_session_environment_is_whitelisted() -> None:
    source = {
        "HOME": "/h",
        "PATH": "/p",
        "ANTHROPIC_API_KEY": "k",
        "CLAUDECODE": "1",
        "CLAUDE_EFFORT": "max",
        "CLAUDE_CODE_SESSION_ID": "s",
        "PYTHONPATH": "/x",
    }
    assert harness.session_environment(source) == {"HOME": "/h", "PATH": "/p"}


def test_mcp_json_names_the_token_by_file_and_runs_this_checkout(tmp_path: Path) -> None:
    document = harness.mcp_config(tmp_path / "project", tmp_path / "secret" / "token")
    server = document["mcpServers"]["procsim"]
    assert server["command"] == sys.executable
    assert server["args"] == [
        "-m",
        "openflowsheet.application.cli",
        "serve-mcp",
        "--project",
        str(tmp_path / "project"),
    ]
    assert server["env"] == {
        "PYTHONPATH": str(harness.REPO_ROOT / "src"),
        "OPENFLOWSHEET_TOKEN_FILE": str(tmp_path / "secret" / "token"),
    }


def test_the_session_directory_is_outside_the_repository(tmp_path: Path) -> None:
    with pytest.raises(harness.HarnessError):
        harness.check_outside_repository(harness.REPO_ROOT / "benchmarks")
    (tmp_path / "CLAUDE.md").write_text("x")
    with pytest.raises(harness.HarnessError):
        harness.check_outside_repository(tmp_path / "work" / "cwd")


# =============================================================================================
# A run: layout, token placement, what the session saw
# =============================================================================================


@pytest.fixture
def one_run(tmp_path: Path) -> tuple[Path, harness.WorkPaths, dict[str, Any]]:
    # A run records the MCP binding's tool-description digest (§14.2), so it needs the `server`
    # extra; the default-install CI job has none (W6d).
    pytest.importorskip("mcp")
    config = replace(harness.AGENT, claude=str(fake_claude(tmp_path, "answer")))
    environment = {"HOME": "/nonexistent", "PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": "k"}
    run_dir = harness.run(
        "V17-T01",
        1,
        "test",
        work=tmp_path / "work",
        config=config,
        runs_root=tmp_path / "runs",
        environment=environment,
    )
    seen = json.loads((tmp_path / "seen.json").read_text())
    return run_dir, harness.work_paths(tmp_path / "work", "test", "V17-T01-1"), seen


def test_run_directory_layout(one_run: tuple[Path, harness.WorkPaths, dict[str, Any]]) -> None:
    run_dir, paths, _ = one_run
    assert run_dir.name == "V17-T01-1" and run_dir.parent.name == "test"
    assert sorted(p.name for p in run_dir.iterdir()) == sorted(
        [
            "run.json",
            "prompt.txt",
            "mcp.json",
            "transcript.jsonl",
            "stderr.txt",
            "result.json",
            "store-export.json",
            "scores.json",
        ]
    )
    record = json.loads((run_dir / "run.json").read_text())
    # Scorer A1's members.
    assert record["task_id"] == "V17-T01" and record["repetition"] == 1
    assert record["session_principal"] == "agent-v17"
    assert record["infrastructure_failure"] is None
    assert record["cost_basis"] == "subscription_estimate"
    # §14.2's provenance.
    assert record["model"] == "claude-sonnet-5"
    assert record["claude_code_version"] == "0.0.0 (Fake Claude)"
    assert set(record["git"]) == {"commit", "dirty"}
    assert record["sha256"]["task_text"] == harness.sha256_text(
        (run_dir / "prompt.txt").read_text()
    )
    assert record["sha256"]["tool_descriptions"] == harness.tool_descriptions_sha256()
    assert len(record["fixture_digest"]) == 64
    assert record["session"]["checks"] == [] and record["session"]["turns_counted"] == 1
    assert record["command"][2] == "<prompt.txt>"
    assert record["agent_configuration"]["max_turns"] == 60
    assert json.loads((run_dir / "result.json").read_text())["subtype"] == "success"
    assert (run_dir / "scores.json").read_bytes() == scorer.dump(scorer.score(run_dir))
    assert json.loads((run_dir / "mcp.json").read_text()) == json.loads(paths.mcp_json.read_text())


def test_token_placement(one_run: tuple[Path, harness.WorkPaths, dict[str, Any]]) -> None:
    run_dir, paths, seen = one_run
    token = paths.token_file.read_text().strip()
    assert stat.S_IMODE(paths.token_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(paths.token_file.parent.stat().st_mode) == 0o700
    assert paths.cwd not in paths.token_file.parents
    server = json.loads(paths.mcp_json.read_text())["mcpServers"]["procsim"]
    assert server["env"]["OPENFLOWSHEET_TOKEN_FILE"] == str(paths.token_file)
    for path in run_dir.iterdir():
        assert token not in path.read_text(errors="replace"), path.name
    assert token not in " ".join(seen["argv"])
    # The session started in the empty directory with the whitelisted environment.
    assert seen["cwd"] == []
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert not any(key.startswith("CLAUDE") for key in seen["env"])


def test_a_run_is_never_repeated(
    one_run: tuple[Path, harness.WorkPaths, dict[str, Any]], tmp_path: Path
) -> None:
    run_dir, _, _ = one_run
    with pytest.raises(harness.HarnessError):
        harness.run("V17-T01", 1, "test", work=tmp_path / "work2", runs_root=run_dir.parents[1])


# =============================================================================================
# The caps
# =============================================================================================


def _session(tmp_path: Path, mode: str, *, wall_cap_s: float, turn_cap: int | None) -> Any:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    return harness.run_session(
        [str(fake_claude(tmp_path, mode)), "-p", "x"],
        cwd=cwd,
        env={"PATH": "/usr/bin:/bin"},
        transcript=tmp_path / "transcript.jsonl",
        stderr=tmp_path / "stderr.txt",
        wall_cap_s=wall_cap_s,
        turn_cap=turn_cap,
        kill_grace_s=1.0,
    )


def test_the_wall_cap_kills_the_session(tmp_path: Path) -> None:
    outcome = _session(tmp_path, "sleep", wall_cap_s=1.0, turn_cap=None)
    assert outcome.stopped == "wall_cap" and outcome.returncode != 0
    assert outcome.wall_s < 10.0 and outcome.init is not None and outcome.result is None
    assert harness.infrastructure_failure(outcome) == {"reason": "wall_cap"}
    assert _lines(tmp_path / "transcript.jsonl")[0]["subtype"] == "init"


def test_the_harness_turn_cap_stops_the_session(tmp_path: Path) -> None:
    outcome = _session(tmp_path, "turns", wall_cap_s=60.0, turn_cap=3)
    assert outcome.stopped == "turn_cap" and outcome.turns >= 4
    assert outcome.wall_s < 30.0
    assert harness.infrastructure_failure(outcome) == {"reason": "harness_turn_cap"}


def _outcome(result: dict[str, Any] | None, **fields: Any) -> harness.SessionOutcome:
    base: dict[str, Any] = {
        "returncode": 0,
        "wall_s": 1.0,
        "stopped": None,
        "turns": 1,
        "init": None,
        "result": result,
        "result_line": None,
    }
    return harness.SessionOutcome(**{**base, **fields})


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"subtype": "success", "is_error": False}, None),
        ({"subtype": "error_max_turns", "is_error": True}, None),
        ({"subtype": "error_max_budget_usd", "is_error": True}, {"reason": "budget_guard"}),
        ({"subtype": "error_during_execution", "is_error": True}, "service_error"),
        ({"subtype": "success", "is_error": True}, "service_error"),
        (None, "no_result_message"),
    ],
)
def test_infrastructure_failure(result: dict[str, Any] | None, expected: Any) -> None:
    found = harness.infrastructure_failure(_outcome(result, returncode=1))
    if isinstance(expected, str):
        assert found is not None and found["reason"].startswith(expected)
    else:
        assert found == expected


# =============================================================================================
# Turn counting and the session checks on the recorded canaries
# =============================================================================================


def test_turns_on_the_recorded_max_turns_canary() -> None:
    """Canary (iv): `--max-turns 2` stopped after two assistant turns; Claude Code's
    `num_turns` counts the refused third."""
    lines = (CANARIES / "c5-max-turns" / "transcript.jsonl").read_bytes().splitlines()
    assert harness.count_turns(lines) == 2
    result = json.loads((CANARIES / "c5-max-turns" / "result.json").read_text())
    assert result["subtype"] == "error_max_turns" and result["num_turns"] == 3
    uses = scorer.Transcript.read(CANARIES / "c5-max-turns" / "transcript.jsonl")
    assert uses is not None and len(uses.tool_uses()) == 2


def test_a_message_split_over_lines_is_one_turn() -> None:
    lines = [
        json.dumps({"type": "assistant", "message": {"id": "a", "content": []}}).encode(),
        json.dumps({"type": "assistant", "message": {"id": "a", "content": []}}).encode(),
        json.dumps({"type": "system", "subtype": "thinking_tokens"}).encode(),
        json.dumps({"type": "assistant", "message": {"id": "b", "content": []}}).encode(),
        b"not json",
    ]
    assert harness.count_turns(lines) == 2


def _init(name: str) -> dict[str, Any]:
    return next(
        entry
        for entry in _lines(CANARIES / name / "transcript.jsonl")
        if entry.get("type") == "system" and entry.get("subtype") == "init"
    )


def test_session_checks_on_the_canaries() -> None:
    assert harness.session_checks(harness.AGENT, _init("c4-confinement")) == []
    assert harness.session_checks(harness.AGENT, _init("c2-isolation")) == []
    # c1 ran with --safe-mode: no server, no tool.
    problems = harness.session_checks(harness.AGENT, _init("c1-confinement"))
    assert any("not connected" in p for p in problems)
    assert any("no tool" in p for p in problems)
    alias = replace(harness.AGENT, model="claude-other")
    assert harness.session_checks(alias, _init("c4-confinement"))
    keyed = {**_init("c4-confinement"), "apiKeySource": "ANTHROPIC_API_KEY"}
    assert harness.session_checks(harness.AGENT, keyed)
    extra = {**_init("c4-confinement"), "tools": ["Bash", "mcp__procsim__get_job"]}
    assert harness.session_checks(harness.AGENT, extra)


# =============================================================================================
# The campaign
# =============================================================================================


class StubRuns:
    """A `run_one` that records the calls and writes a minimal, scorable run directory."""

    def __init__(self, fail_at: tuple[str, int] | None = None) -> None:
        self.calls: list[tuple[str, int]] = []
        self.fail_at = fail_at

    def __call__(
        self, task_id: str, repetition: int, campaign: str, *, runs_root: Path, **_: Any
    ) -> Path:
        self.calls.append((task_id, repetition))
        run_dir = runs_root / campaign / f"{task_id}-{repetition}"
        run_dir.mkdir(parents=True)
        checks = ["model 'x'"] if (task_id, repetition) == self.fail_at else []
        record = {
            "task_id": task_id,
            "repetition": repetition,
            "infrastructure_failure": {"reason": "stub"},
            "session": {"checks": checks},
        }
        (run_dir / "run.json").write_text(json.dumps(record))
        return run_dir


@pytest.fixture
def clean_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harness, "git_state", lambda: {"commit": "0" * 40, "dirty": False})


@pytest.mark.usefixtures("clean_git")
def test_a_campaign_runs_the_registered_order_once(tmp_path: Path) -> None:
    order = scorer.run_order(harness.REFERENCE)
    assert len(order) == 30 and order[:2] == [("V17-T01", 1), ("V17-T02", 1)]
    runs_root = tmp_path / "runs"
    (runs_root / "c" / "V17-T03-1").mkdir(parents=True)  # a run the harness abandoned
    stub = StubRuns()
    campaign_dir = harness.campaign(
        "c", work=tmp_path / "work", runs_root=runs_root, resume=True, run_one=stub
    )
    assert stub.calls == [slot for slot in order if slot != ("V17-T03", 1)]
    aggregate = json.loads((campaign_dir / "campaign.json").read_text())
    assert aggregate["pooled_completion"]["runs"] == 30
    assert aggregate["pooled_completion"]["complete"] == 0
    # Resuming a finished campaign runs nothing; a new campaign of that name is refused.
    again = StubRuns()
    harness.campaign("c", work=tmp_path / "w", runs_root=runs_root, resume=True, run_one=again)
    assert again.calls == []
    with pytest.raises(harness.HarnessError):
        harness.campaign("c", work=tmp_path / "w", runs_root=runs_root, run_one=StubRuns())


@pytest.mark.usefixtures("clean_git")
def test_a_run_outside_the_configuration_stops_the_campaign(tmp_path: Path) -> None:
    stub = StubRuns(fail_at=("V17-T02", 1))
    with pytest.raises(harness.HarnessError, match="V17-T02-1"):
        harness.campaign("c", work=tmp_path / "w", runs_root=tmp_path / "runs", run_one=stub)
    assert stub.calls == [("V17-T01", 1), ("V17-T02", 1)]


def test_a_campaign_needs_a_clean_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harness, "git_state", lambda: {"commit": None, "dirty": None})
    with pytest.raises(harness.HarnessError):
        harness.campaign("c", work=tmp_path / "w", runs_root=tmp_path / "runs", run_one=StubRuns())
    with pytest.raises(harness.HarnessError):
        harness.campaign("canary", work=tmp_path / "w", runs_root=tmp_path / "runs")
