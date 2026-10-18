"""M06 WO-16d/e/g: the W27 harness, preflight and report, offline (no `claude` binary is run).

Registration §8 (configuration), §9 (W27-A21/A22: card and prompt), §13 (W27-A23: the run record),
§18 WO-16e (P1–P8); design note §11 G15. A stand-in `claude` (`benchmarks.m06.w27.stubs`) makes
no network or model call. Tests that need a case card read the pinned archive and skip without it.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from m06_w27_support import clean_head, stub_campaign

from benchmarks.m06.w27 import harness, preflight, registration, report, sample, stubs
from benchmarks.t07.v17 import harness as v17

ARCHIVE_PRESENT = (registration.ARCHIVE_DIR / "cases").is_dir()
needs_archive = pytest.mark.skipif(
    not ARCHIVE_PRESENT, reason="pinned archive absent (scripts/m06_w27_acquire.py)"
)


# =================================================================================================
# The configuration (W27-R33): the model is a recorded parameter
# =================================================================================================


def test_agent_config_is_the_registered_one_with_the_given_model() -> None:
    config = harness.agent_config("claude-test-model-id")
    assert config.model == "claude-test-model-id"
    assert (config.effort, config.max_turns, config.max_turns_flag) == ("high", 60, True)
    assert (config.wall_cap_s, config.max_budget_usd) == (1800.0, 5.0)
    assert config.isolation == ("--setting-sources", "") and config.operator_isolation
    argv = v17.command(config, "PROMPT", Path("/x/mcp.json"))
    assert argv[argv.index("--model") + 1] == "claude-test-model-id"
    assert argv[argv.index("--effort") + 1] == "high"
    assert argv[argv.index("--max-turns") + 1] == "60"
    assert argv[argv.index("--max-budget-usd") + 1] == "5"
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--allowedTools") + 1] == "mcp__procsim__*"
    assert "--strict-mcp-config" in argv and argv[argv.index("--setting-sources") + 1] == ""


@pytest.mark.parametrize("model", ["opus", "sonnet", "default", "claude-sonnet-5", "gpt-x"])
def test_an_alias_or_v17s_model_is_refused(model: str) -> None:
    with pytest.raises(harness.HarnessError):
        harness.agent_config(model)


def test_an_unpinned_configuration_runs_without_model() -> None:
    config = harness.agent_config(None)
    config.check()
    assert "--model" not in v17.command(config, "PROMPT", Path("/x/mcp.json"))
    init = {"apiKeySource": "none", "mcp_servers": [], "tools": []}
    assert "the init message names no model" in v17.session_checks(config, init)
    assert not any("model" in p for p in v17.session_checks(config, {**init, "model": "m"}))
    with pytest.raises(harness.HarnessError):
        v17.AgentConfig(**{**v17.AGENT.as_document(), "isolation": (), "model": None}).check()


def test_an_unpinned_attempt_records_its_init_model_as_the_pin() -> None:
    def record(model: str) -> dict[str, Any]:
        session = {"init": {"model": model}, "checks": []}
        return {"model": None, "pinned": {"model": None, "effort": "high"}, "session": session}

    unpinned = record("claude-test-m1")
    harness._unpinned(unpinned)
    assert unpinned["pinned"] == {"model": "claude-test-m1", "effort": "high"}
    assert unpinned["model"] is None and unpinned["session"]["checks"] == []
    v17s = record("claude-sonnet-5")
    harness._unpinned(v17s)
    assert v17s["pinned"]["model"] is None
    assert v17s["session"]["checks"] == [
        "model 'claude-sonnet-5' is V17's, not W27's (registration §3 F1, §23.5)"
    ]


# =================================================================================================
# W27-A21, A22: the card and the prompt
# =================================================================================================


def test_a22_prompt_is_the_template_and_nothing_else() -> None:
    table = registration.load()["prompt"]
    card = '{"case_id": "c-1", "request": "braces {x} stay"}'
    digest = registration.sha256_bytes(card.encode("utf-8"))
    text = harness.prompt("c-1", card)
    begin = f"<<<OPENIDAES CASE DATA BEGIN case_id=c-1 sha256={digest}>>>"
    end = "<<<OPENIDAES CASE DATA END case_id=c-1>>>"
    assert text == table["template"].format(
        envelope_begin=begin,
        card=card,
        envelope_end=end,
        footer=table["footer"].format(case_id="c-1"),
    )
    assert f"{begin}\n{card}\n{end}" in text
    assert '{"case_id": "c-1", "status": "built"' in text  # the footer's own braces unescaped
    assert "{case_id}" not in text and "{footer}" not in text and "{{" not in text


@needs_archive
def test_a21_a22_on_a_real_case(tmp_path: Path) -> None:
    case_id = stubs.NON_CANDIDATE
    card = harness.case_card(case_id)
    registered = registration.load()["prompt"]["card"]["sha256_by_case"][case_id]
    assert registration.sha256_bytes(card.encode("utf-8")) == registered
    assert card in harness.prompt(case_id, card)
    copy = tmp_path / case_id
    shutil.copytree(registration.ARCHIVE_DIR / "cases" / case_id, copy)
    document = json.loads((copy / "case.json").read_text(encoding="utf-8"))
    document["request"] = str(document.get("request")) + " (altered)"
    (copy / "case.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(harness.HarnessError, match="W27-A21"):
        harness.case_card(case_id, tmp_path)


# =================================================================================================
# W27-A23: a stub run through the real harness
# =================================================================================================


@pytest.fixture(scope="module")
def stub_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    pytest.importorskip("mcp")
    if not ARCHIVE_PRESENT:
        pytest.skip("pinned archive absent (scripts/m06_w27_acquire.py)")
    (s01,) = [s for s in stubs.states() if s.state_id == "W27-S01"]
    return stubs.harness_run(s01, tmp_path_factory.mktemp("w27-run"))


def test_a23_run_record(stub_run: Path) -> None:
    record = json.loads((stub_run / "run.json").read_text(encoding="utf-8"))
    verdict = harness.a23(record)
    assert verdict["passed"], verdict
    assert record["model"] == stubs.STUB_MODEL and record["effort"] == "high"
    assert record["claude_code_version"].startswith(stubs.STUB_VERSION)
    assert record["registration_sha256"] == registration.sha256_file(registration.REGISTRATION_JSON)
    assert record["coverage_sha256"] == registration.sha256_file(registration.COVERAGE_JSON)
    assert record["prompt_sha256"] == v17.sha256_text(
        (stub_run / "prompt.txt").read_text(encoding="utf-8")
    )
    assert record["session"]["checks"] == []
    assert record["operator_identifier_hits"] == 0
    assert record["infrastructure_failure"] is None
    broken = {k: v for k, v in record.items() if k != "lock_sha256"}
    assert not harness.a23(broken)["passed"]


def test_a_fresh_project_and_the_export(stub_run: Path) -> None:
    export = json.loads((stub_run / "store-export.json").read_text(encoding="utf-8"))
    assert {"audit", "audit_all", "bundle_files"} <= set(export)
    owners = {row["principal_id"] for row in export["audit_all"]}
    assert owners == {"local-owner"}  # init and grant only; the stub did nothing
    assert export["audit"] == [] and export["revisions"] == [] and export["jobs"] == []
    policy = json.loads((stub_run / "mcp.json").read_text(encoding="utf-8"))
    assert "OPENFLOWSHEET_TOKEN_FILE" in policy["mcpServers"]["procsim"]["env"]
    scores = json.loads((stub_run / "scores.json").read_text(encoding="utf-8"))
    assert scores["outcome"] == "CORRECT_LIMITATION"


# =================================================================================================
# The campaign loop
# =================================================================================================


def test_campaign_runs_the_order_once_after_the_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = stub_campaign(tmp_path / "runs", clean_head(monkeypatch))
    drawn = json.loads(campaign.sample_path.read_bytes())
    calls: list[tuple[str, int]] = []
    stop_at = [2]

    class StopError(Exception):
        pass

    def run_one(case_id: str, order: int, campaign: str, **kwargs: Any) -> Path:
        run_dir = kwargs["runs_root"] / campaign / f"{order:02d}-{case_id}"
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text("{}", encoding="utf-8")
        calls.append((case_id, order))
        if order == stop_at[0]:
            raise StopError
        return run_dir

    config = harness.agent_config("claude-test-model-id")
    refused: list[str] = []

    def failing() -> dict[str, Any]:
        refused.append("preflight")
        raise preflight.PreflightError("P1")

    common: dict[str, Any] = {
        "work": tmp_path / "w",
        "config": config,
        "claude_code_version": "1",
        "coverage_path": campaign.coverage_path,
        "sample_path": campaign.sample_path,
        "runs_root": campaign.runs_root,
        "run_one": run_one,
    }
    with pytest.raises(preflight.PreflightError):
        harness.campaign("c", preflight=failing, **common)
    assert refused == ["preflight"] and calls == []
    assert not (campaign.directory / "preflight.json").exists()
    with pytest.raises(StopError):
        harness.campaign("c", preflight=lambda: {"P1": {"passed": True}}, **common)
    assert [o for _, o in calls] == [1, 2]
    assert [c for c, _ in calls] == drawn["run_order"][:2]
    stop_at[0] = 3
    with pytest.raises(StopError):
        harness.campaign("c", resume=True, preflight=dict, **common)
    assert [o for _, o in calls] == [1, 2, 3]  # 1 and 2 exist and are not re-run


# =================================================================================================
# The preflight (P1–P8)
# =================================================================================================


def _campaign(tmp_path: Path, **changes: Any) -> preflight.Campaign:
    data = registration.COVERAGE_JSON.read_bytes()
    (tmp_path / "coverage.json").write_bytes(data)
    drawn = sample.sample_document(json.loads(data), data)
    (tmp_path / "sample.json").write_bytes(registration.dump(drawn))
    base = preflight.Campaign(
        name="c",
        runs_root=tmp_path / "runs",
        coverage_path=tmp_path / "coverage.json",
        sample_path=tmp_path / "sample.json",
        model="claude-test-model-id",
        claude_code_version="9.9.9",
        approval_file=tmp_path / "decisions.md",
    )
    return replace(base, **changes)


def test_p1_reads_the_recorded_approval(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    assert not preflight.p1(campaign)["passed"]
    campaign.approval_file.write_text(
        "# log\n- **W27 Tier 1 approved** (Frank, date): 45 runs.\n", encoding="utf-8"
    )
    assert preflight.p1(campaign)["passed"]
    # Frank's approval is recorded in the repository's file (main, merged for M06 review F7).
    assert preflight.p1(replace(campaign, approval_file=preflight.APPROVAL_FILE))["passed"]


def test_p2_pins_and_checks_pass_at_registration(tmp_path: Path) -> None:
    if not ARCHIVE_PRESENT:
        pytest.skip("pinned archive absent (scripts/m06_w27_acquire.py)")
    verdict = preflight.p2(_campaign(tmp_path))
    assert verdict["sha256_as_registered"] and verdict["archive"]["sha256_matches"]
    assert verdict["generator_check_exit"] == 0 and verdict["facts_check_exit"] == 0
    assert verdict["passed"]


def test_p4(tmp_path: Path) -> None:
    campaign = _campaign(tmp_path)
    assert preflight.p4(campaign)["passed"]
    drawn = json.loads(campaign.sample_path.read_bytes())
    drawn["cases"] = drawn["cases"][1:]
    campaign.sample_path.write_bytes(registration.dump(drawn))
    assert not preflight.p4(campaign)["passed"]


def test_p6_p7_p8_on_stub_canaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    if not ARCHIVE_PRESENT:
        pytest.skip("pinned archive absent (scripts/m06_w27_acquire.py)")
    clean_head(monkeypatch)
    campaign = _campaign(tmp_path, model=stubs.STUB_MODEL, claude_code_version=stubs.STUB_VERSION)
    campaign.directory.mkdir(parents=True)
    for name in ("coverage.json", "sample.json"):
        shutil.copyfile(tmp_path / name, campaign.directory / name)
    campaign = replace(
        campaign,
        coverage_path=campaign.directory / "coverage.json",
        sample_path=campaign.directory / "sample.json",
    )
    harness.confirm("c", runs_root=campaign.runs_root)
    assert not preflight.p6(campaign)["passed"] and not preflight.p7(campaign)["passed"]
    canary = stubs.State("canary", "", "", text="Stub canary.")
    drawn = json.loads(campaign.sample_path.read_bytes())
    verdicts = harness.canaries(
        "c",
        work=tmp_path / "work",
        claude=str(stubs.write_fake_claude(tmp_path / "bin", canary)),
        runs_root=campaign.runs_root,
        operator=stubs.stub_operator(tmp_path),
        run_one=lambda *a, **k: harness.run(
            *a, **k, environment={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
        ),
    )
    assert [v["case_id"] for v in verdicts] == drawn["canaries"]
    assert all(v["passed"] for v in verdicts), verdicts
    records = [
        json.loads((campaign.directory / "canary" / v["attempt"] / "run.json").read_bytes())
        for v in verdicts
    ]
    # Attempt 01 runs on Claude Code's default and pins it; 02 and 03 pass --model (§23.5).
    assert [r["model"] for r in records] == [None, stubs.STUB_MODEL, stubs.STUB_MODEL]
    assert "--model" not in records[0]["command"] and "--model" in records[1]["command"]
    confirmation = registration.sha256_file(campaign.directory / harness.CONFIRMATION_FILE)
    assert all(r["confirmation_sha256"] == confirmation for r in records)
    assert preflight.p6(campaign)["passed"] and preflight.p7(campaign)["passed"]
    assert not preflight.p7(replace(campaign, model="claude-other"))["passed"]
    assert preflight.p8(campaign)["runs_present"] == []
    (campaign.directory / "01-x").mkdir()
    assert preflight.p8(campaign)["runs_present"] == ["01-x"]


# =================================================================================================
# The command line (WO-17), over the stand-in `claude`: no model call
# =================================================================================================


def test_spend_sums_the_recorded_costs(tmp_path: Path) -> None:
    for name, cost in (("canary/01-a", 0.25), ("01-b", 1.5), ("02-c", None)):
        run_dir = tmp_path / name
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text("{}", encoding="utf-8")
        if cost is not None:
            (run_dir / "result.json").write_text(json.dumps({"total_cost_usd": cost}), "utf-8")
    assert harness.spend(tmp_path) == {
        "cost_basis": v17.COST_BASIS,
        "runs": 3,
        "total_cost_usd": 1.75,
        "uncosted": ["02-c"],
    }


def test_campaign_stops_before_a_run_that_could_pass_the_spend_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = stub_campaign(tmp_path / "runs", clean_head(monkeypatch))
    calls: list[int] = []

    def run_one(case_id: str, order: int, campaign: str, **kwargs: Any) -> Path:
        run_dir = kwargs["runs_root"] / campaign / f"{order:02d}-{case_id}"
        run_dir.mkdir(parents=True)
        (run_dir / "run.json").write_text("{}", encoding="utf-8")
        (run_dir / "result.json").write_text('{"total_cost_usd": 4.0}', encoding="utf-8")
        calls.append(order)
        return run_dir

    config = harness.agent_config("claude-test-model-id")  # the USD 5 cap per run
    # The stub canaries record no cost: three uncosted runs at the cap, USD 15, come first.
    # Before run k: 15 + 4(k-1) recorded or capped + 5 for run k; run 4 would bound 32 > 29.
    with pytest.raises(harness.HarnessError, match="spend ceiling USD 29: recorded 12.00"):
        harness.campaign(
            "c",
            work=tmp_path / "w",
            config=config,
            claude_code_version="1",
            coverage_path=campaign.coverage_path,
            sample_path=campaign.sample_path,
            runs_root=campaign.runs_root,
            preflight=lambda: {"P1": {"passed": True}},
            run_one=run_one,
            spend_ceiling_usd=29.0,
        )
    assert calls == [1, 2, 3]
    # A run with no recorded cost counts at the cap: 12 + 5 x 4 + 5 = 37 > 36.
    (campaign.directory / "03-uncosted").mkdir()
    (campaign.directory / "03-uncosted" / "run.json").write_text("{}", encoding="utf-8")
    harness.within_spend_ceiling(campaign.directory, config, 37.0)
    with pytest.raises(harness.HarnessError, match="4 uncosted run"):
        harness.within_spend_ceiling(campaign.directory, config, 36.0)


def test_cli_refuses_a_campaign_without_its_coverage_and_sample(tmp_path: Path) -> None:
    with pytest.raises(harness.HarnessError, match="coverage and sample first"):
        harness.main(
            ["--runs-root", str(tmp_path), "preflight", "--campaign", "c"]
            + ["--model", "claude-test-model-id", "--claude-code-version", "9.9.9"]
        )


def test_cli_confirm_canaries_preflight_and_spend_on_stubs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("mcp")
    if not ARCHIVE_PRESENT:
        pytest.skip("pinned archive absent (scripts/m06_w27_acquire.py)")
    clean_head(monkeypatch)
    runs_root = tmp_path / "runs"
    (runs_root / "c").mkdir(parents=True)
    data = registration.COVERAGE_JSON.read_bytes()
    drawn = sample.sample_document(json.loads(data), data)
    (runs_root / "c" / "coverage.json").write_bytes(data)
    (runs_root / "c" / "sample.json").write_bytes(registration.dump(drawn))
    claude = stubs.write_fake_claude(tmp_path / "bin", stubs.State("canary", "", "", text="S."))
    operator = stubs.stub_operator(tmp_path)
    monkeypatch.setattr(v17, "login_operator", lambda token_file, config: operator)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    common = ["--claude", str(claude), "--runs-root", str(runs_root)]
    assert harness.main([*common, "confirm", "--campaign", "c"]) == 0
    assert capsys.readouterr().out.strip().endswith(harness.CONFIRMATION_FILE)
    assert (
        harness.main(
            [*common, "canaries", "--campaign", "c"]
            + ["--work", str(tmp_path / "work"), "--oauth-token-file", str(operator.token_file)]
        )
        == 0
    )
    verdicts = json.loads(capsys.readouterr().out)
    assert [v["case_id"] for v in verdicts] == drawn["canaries"]
    assert sorted(p.name for p in (runs_root / "c" / "canary").iterdir()) == [
        f"{k:02d}-{c}" for k, c in enumerate(drawn["canaries"], start=1)
    ]
    pins = ["--model", stubs.STUB_MODEL, "--claude-code-version", stubs.STUB_VERSION]
    # P3 fails: the committed coverage.json was not made at this commit.
    assert harness.main([*common, "preflight", "--campaign", "c", *pins]) == 1
    results = json.loads(capsys.readouterr().out)
    assert results["P6"]["passed"] and results["P7"]["passed"] and not results["P3"]["passed"]
    assert results["P5"]["passed"] and results["P8"]["passed"]
    assert not (runs_root / "c" / "preflight.json").exists()
    assert harness.main([*common, "spend", "--campaign", "c"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "cost_basis": v17.COST_BASIS,
        "runs": 3,
        "total_cost_usd": 0.0,
        "uncosted": [],
    }
    # The order so far: no preflight.json and no run yet.
    assert harness.main([*common, "order", "--campaign", "c"]) == 1
    assert "preflight.json#missing" in json.loads(capsys.readouterr().out)["problems"]


# =================================================================================================
# The generated report (Tier 0 item 4)
# =================================================================================================


def test_report_is_generated_from_coverage_json() -> None:
    assert report.main(["--check"]) == 0
    text = registration.REPORT_MD.read_text(encoding="utf-8")
    coverage = json.loads(registration.COVERAGE_JSON.read_bytes())
    assert report.sentence(coverage) in text
    assert coverage["snapshot_sha256"] in text and coverage["list_models_sha256"] in text
