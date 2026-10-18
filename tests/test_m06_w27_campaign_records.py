"""M06 W27 registration §23 (Amendment 4, WO-17a): the campaign's records, its order, re-canaries
and the model pin, offline — W27-A74…A78 and the `canaries` command.

Every expectation is read from `registration.json#/campaign_records`. No `claude` binary runs: the
canary attempts and campaign runs are stubs (`stubs.canary_attempt`, `m06_w27_support.stub_runs`).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from m06_w27_support import (
    FAST_CHECKS,
    MODELS,
    NAME,
    K,
    StopRunsError,
    canary_cases,
    canary_chain,
    clean_head,
    context,
    drawn,
    head,
    stub_campaign,
    stub_runs,
)

from benchmarks.m06.w27 import harness, preflight, registration, stubs

RECORDS = registration.load()["campaign_records"]


def test_the_harness_names_the_registered_records() -> None:
    assert harness.CONFIRMATION_FILE == RECORDS["confirmation"]["file"]
    assert harness.PREFLIGHT_FILE == RECORDS["preflight"]["file"]
    assert harness.CANARY_DIR == RECORDS["canary_dir"]
    assert harness.RUNS_ROOT == registration.ROOT / RECORDS["runs_root"]


# =================================================================================================
# W27-A74: `confirm` and P5
# =================================================================================================


def test_a74_confirm_and_p5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commit = clean_head(monkeypatch)
    # (a) The committed Tier 0 coverage and its re-draw: the empty path.
    directory = drawn(tmp_path / "a")
    path = harness.confirm(NAME, runs_root=tmp_path / "a")
    assert path == directory / RECORDS["confirmation"]["file"]
    record = json.loads(path.read_bytes())
    assert sorted(record) == sorted(RECORDS["confirmation"]["members"])
    assert record["schema"] == RECORDS["confirmation"]["schema"]
    assert (record["campaign"], record["commit"], record["tree_clean"]) == (NAME, commit, True)
    assert record["candidates"] == [] and record["empty"] is True
    assert record["coverage_sha256"] == registration.sha256_file(directory / "coverage.json")
    assert record["sample_sha256"] == registration.sha256_file(directory / "sample.json")
    campaign = context(directory)
    assert preflight.p5(campaign)["passed"]
    # (b) One frame case set to CANDIDATE with no reasons, re-drawn: refused, nothing written.
    coverage = json.loads(registration.COVERAGE_JSON.read_bytes())
    row = next(r for r in coverage["rows"] if r["class"] != "ARTIFACT_INCOMPLETE")
    row["class"], row["reasons"] = "CANDIDATE", []
    refused = drawn(tmp_path / "b", coverage)
    argv = ["--runs-root", str(tmp_path / "b"), "confirm", "--campaign", NAME]
    assert harness.main(argv) == 2
    assert not (refused / "confirmation").exists()
    verdict = preflight.p5(context(refused))
    assert not verdict["passed"] and verdict["reason"] == "non_empty_candidates"
    assert verdict["candidates"] == [row["case_id"]]
    # (c) A broken link: the last hex digit of `sample_sha256` changed.
    original = path.read_bytes()
    digest = record["sample_sha256"]
    broken = {**record, "sample_sha256": digest[:-1] + ("0" if digest[-1] != "0" else "1")}
    path.write_bytes(registration.dump(broken))
    assert preflight.p5(campaign)["failed"] == ["sample_sha256"]
    # (d) A lying flag.
    path.write_bytes(registration.dump({**record, "empty": False}))
    assert preflight.p5(campaign)["failed"] == ["empty"]
    path.write_bytes(original)
    assert preflight.p5(campaign)["passed"]


def test_confirm_refuses_a_dirty_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    drawn(tmp_path)
    monkeypatch.setattr(harness, "git_state", lambda r: {"commit": head(), "tree_clean": False})
    with pytest.raises(harness.HarnessError, match="not clean"):
        harness.confirm(NAME, runs_root=tmp_path)
    assert not (tmp_path / NAME / "confirmation").exists()


# =================================================================================================
# W27-A76, A77: P6 and P7 on the registered states
# =================================================================================================


def _states_campaign(tmp_path: Path, state: dict[str, Any]) -> preflight.Campaign:
    """`state`'s attempts as stub canary attempts: A, B, C the canaries in order, X the first
    frame case by canary rank that is neither sampled nor a canary; HEAD is HEAD, K is K."""
    directory = drawn(tmp_path / state["id"])
    canaries = canary_cases(directory)
    coverage = json.loads((directory / "coverage.json").read_bytes())
    chosen = set(json.loads((directory / "sample.json").read_bytes())["cases"])
    remaining = sorted(
        (
            r["case_id"]
            for r in coverage["rows"]
            if r["class"] != "ARTIFACT_INCOMPLETE" and r["case_id"] not in chosen
        ),
        key=lambda c: registration.hash_rank("canary", c),
    )
    assert remaining[:3] == canaries
    cases = {"A": canaries[0], "B": canaries[1], "C": canaries[2], "X": remaining[3]}
    commits = {"HEAD": head(), "K": K}
    for attempt in state["attempts"]:
        stubs.canary_attempt(
            directory,
            attempt["n"],
            cases[attempt["case"]],
            commit=commits[attempt["commit"]],
            passed=attempt["passed"],
            model=MODELS.get(attempt["model"], attempt["model"]),
            init_model=MODELS.get(attempt["init_model"], attempt["init_model"]),
        )
    pin = state.get("pin")
    return context(directory, model=MODELS.get(pin, pin) if pin else MODELS["M1"])


@pytest.mark.parametrize("state", RECORDS["p6_states"], ids=lambda s: s["id"])
def test_a76_p6_states(tmp_path: Path, state: dict[str, Any]) -> None:
    verdict = preflight.p6(_states_campaign(tmp_path, state))
    assert verdict["passed"] is state["expected_pass"], verdict


def test_a76_states_cover_both_verdicts() -> None:
    states = RECORDS["p6_states"]
    assert len(states) == 11
    passing = sorted(s["id"] for s in states if s["expected_pass"])
    assert passing == ["P6-S1", "P6-S2", "P6-S4", "P6-S6"]


@pytest.mark.parametrize("state", RECORDS["p7_states"], ids=lambda s: s["id"])
def test_a77_p7_states(tmp_path: Path, state: dict[str, Any]) -> None:
    campaign = _states_campaign(tmp_path, state)
    assert preflight.p6(campaign)["passed"]  # GC-A4-6: every P7 state passes P6
    verdict = preflight.p7(campaign)
    assert verdict["passed"] is state["expected_pass"], verdict


def test_a77_states_cover_both_verdicts() -> None:
    states = RECORDS["p7_states"]
    assert len(states) == 6
    assert sorted(s["id"] for s in states if s["expected_pass"]) == ["P7-T1", "P7-T5"]


# =================================================================================================
# The `canaries` command (W27-R68, registration §23.4, §23.5)
# =================================================================================================


def _attempts(plan: list[bool], default: str = MODELS["M1"]) -> Any:
    """A `run_one` making stub attempts: each passes as `plan` says; the `init` model is the
    requested one, or `default` (Claude Code's default) without `--model`."""
    requested: list[str | None] = []

    def run_one(case_id: str, order: int, campaign: str, **keywords: Any) -> Path:
        model = keywords["config"].model
        requested.append(model)
        directory = keywords["runs_root"] / campaign.removesuffix(f"/{harness.CANARY_DIR}")
        return stubs.canary_attempt(
            directory,
            order,
            case_id,
            commit=head(),
            passed=plan.pop(0),
            model=model,
            init_model=default if model is None else model,
            chain=keywords["chain"],
        )

    run_one.requested = requested  # type: ignore[attr-defined]
    return run_one


def _confirmed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    clean_head(monkeypatch)
    directory = drawn(tmp_path)
    harness.confirm(NAME, runs_root=tmp_path)
    return directory


def test_canaries_number_stop_at_a_failure_and_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _confirmed(tmp_path, monkeypatch)
    cases = canary_cases(directory)
    run_one = _attempts([False, True, True, True])
    first = harness.canaries(NAME, work=tmp_path / "w", runs_root=tmp_path, run_one=run_one)
    assert [(v["attempt"], v["passed"]) for v in first] == [(f"01-{cases[0]}", False)]
    again = harness.canaries(NAME, work=tmp_path / "w", runs_root=tmp_path, run_one=run_one)
    assert [v["attempt"] for v in again] == [
        f"02-{cases[0]}",
        f"03-{cases[1]}",
        f"04-{cases[2]}",
    ]
    assert run_one.requested == [None, MODELS["M1"], MODELS["M1"], MODELS["M1"]]
    record = json.loads((directory / "canary" / f"02-{cases[0]}" / "run.json").read_bytes())
    given = RECORDS["run_json_added"]["canary"]  # run() itself adds coverage_sha256
    assert {k: record[k] for k in given} == {k: canary_chain(directory)[k] for k in given}
    # Every case has passed at HEAD: nothing is attempted again (no re-roll).
    assert harness.canaries(NAME, work=tmp_path / "w", runs_root=tmp_path, run_one=run_one) == []
    campaign = context(directory)
    assert preflight.p6(campaign)["passed"] and preflight.p7(campaign)["passed"]
    assert preflight.p6(campaign)["counted"] == {
        cases[0]: f"02-{cases[0]}",
        cases[1]: f"03-{cases[1]}",
        cases[2]: f"04-{cases[2]}",
    }


def test_canaries_refuse_a_seventh_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = _confirmed(tmp_path, monkeypatch)
    run_one = _attempts([False] * 6)
    for _ in range(6):
        verdicts = harness.canaries(NAME, work=tmp_path / "w", runs_root=tmp_path, run_one=run_one)
        assert len(verdicts) == 1 and not verdicts[0]["passed"]
    assert RECORDS["canary_attempts_max"] == 6
    with pytest.raises(
        harness.RefusalError, match=r"re-canary allowance exhausted \(registration §17 Q3\): Frank"
    ):
        harness.canaries(NAME, work=tmp_path / "w", runs_root=tmp_path, run_one=run_one)
    assert len(list((directory / "canary").iterdir())) == 6
    assert len(run_one.requested) == 6


@pytest.mark.parametrize(("default", "match"), [("claude-sonnet-5", "Frank"), ("opus", "A4-Q1")])
def test_canaries_refuse_v17s_model_or_an_alias_as_the_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, default: str, match: str
) -> None:
    _confirmed(tmp_path, monkeypatch)
    run_one = _attempts([True, True], default=default)
    with pytest.raises(harness.RefusalError, match=match):
        harness.canaries(NAME, work=tmp_path / "w", runs_root=tmp_path, run_one=run_one)
    assert run_one.requested == [None]  # attempt 01 ran; attempt 02 was never launched


def test_canaries_need_the_confirmation_and_take_no_model(tmp_path: Path) -> None:
    drawn(tmp_path)
    with pytest.raises(harness.HarnessError, match="confirmation first"):
        harness.canaries(NAME, work=tmp_path / "w", runs_root=tmp_path, run_one=_attempts([]))
    with pytest.raises(SystemExit):
        harness.main(
            ["--runs-root", str(tmp_path), "canaries", "--campaign", NAME, "--model", "x"]
            + ["--work", str(tmp_path / "w"), "--oauth-token-file", str(tmp_path / "t")]
        )


# =================================================================================================
# W27-A75: `preflight.json` and P8; W27-A78: `order_check`
# =================================================================================================


def test_a75_a78_preflight_record_p8_and_the_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit = clean_head(monkeypatch)
    campaign = stub_campaign(tmp_path / "runs", commit)
    directory = campaign.directory
    record_path = directory / RECORDS["preflight"]["file"]

    def start(run_one: Any) -> None:
        harness.campaign(
            NAME,
            work=tmp_path / "w",
            config=harness.agent_config(MODELS["M1"]),
            claude_code_version=stubs.STUB_VERSION,
            coverage_path=campaign.coverage_path,
            sample_path=campaign.sample_path,
            runs_root=campaign.runs_root,
            preflight=lambda: preflight.require(campaign, FAST_CHECKS),
            run_one=run_one,
        )

    # `canary/`, `confirmation/` are expected: P8 passes; the standalone preflight writes nothing.
    assert preflight.p8(campaign)["passed"]
    assert all(v["passed"] for v in preflight.run_all(campaign, FAST_CHECKS).values())
    assert not record_path.exists()
    # A stray run directory fails P8: no preflight.json, no run directory.
    (directory / "01-x").mkdir()
    assert preflight.p8(campaign)["runs_present"] == ["01-x"]
    with pytest.raises(preflight.PreflightError, match="P8"):
        start(stub_runs(commit, stop_after=1))
    assert not record_path.exists()
    assert sorted(p.name for p in directory.iterdir() if p.name[:2].isdigit()) == ["01-x"]
    (directory / "01-x").rmdir()
    # preflight.json alone fails P8.
    record_path.write_text("{}", encoding="utf-8")
    assert preflight.p8(campaign)["runs_present"] == ["preflight.json"]
    record_path.unlink()
    # The stub campaign: preflight.json, then the runs, each naming its digest.
    with pytest.raises(StopRunsError):
        start(stub_runs(commit, stop_after=3))
    record = json.loads(record_path.read_bytes())
    assert sorted(record) == sorted(RECORDS["preflight"]["members"])
    assert record["schema"] == RECORDS["preflight"]["schema"] and record["passed"] is True
    assert (record["campaign"], record["commit"], record["model"]) == (NAME, commit, MODELS["M1"])
    assert sorted(record["checks"]) == [f"P{k}" for k in range(1, 9)]
    assert [sorted(c) for c in record["canaries"]] == [
        sorted(RECORDS["preflight"]["canaries_item"])
    ] * 3
    runs = sorted(p for p in directory.iterdir() if p.is_dir() and p.name[:2].isdigit())
    assert len(runs) == 3
    digest = registration.sha256_file(record_path)
    assert all(
        json.loads((r / "run.json").read_bytes())["preflight_sha256"] == digest for r in runs
    )
    assert not preflight.p8(campaign)["passed"]
    # A resumed campaign reuses preflight.json.
    with pytest.raises(StopRunsError):
        harness.campaign(
            NAME,
            work=tmp_path / "w",
            config=harness.agent_config(MODELS["M1"]),
            claude_code_version=stubs.STUB_VERSION,
            coverage_path=campaign.coverage_path,
            sample_path=campaign.sample_path,
            runs_root=campaign.runs_root,
            resume=True,
            preflight=lambda: pytest.fail("no preflight on --resume"),
            run_one=stub_runs(commit, stop_after=1),
        )
    assert registration.sha256_file(record_path) == digest
    runs = sorted(p for p in directory.iterdir() if p.is_dir() and p.name[:2].isdigit())

    # W27-A78: every link and the commit rule, one at a time.
    assert harness.order_check(directory) == {"passed": True, "commit": commit, "problems": []}
    original = record_path.read_bytes()
    record_path.write_bytes(original[:-1] + b" ")  # one byte
    assert harness.order_check(directory)["problems"] == [
        f"{r.name}/run.json#preflight_sha256" for r in runs
    ]
    record_path.write_bytes(original)
    canary = directory / "canary" / f"02-{canary_cases(directory)[1]}" / "run.json"
    saved = canary.read_bytes()
    document = json.loads(saved)
    document["sample_sha256"] = "0" * 64
    canary.write_text(json.dumps(document), encoding="utf-8")
    problems = harness.order_check(directory)["problems"]
    assert f"canary/{canary.parent.name}/run.json#sample_sha256" in problems
    assert set(problems) <= {
        f"canary/{canary.parent.name}/run.json#sample_sha256",
        "preflight.json#canaries",
    }
    canary.write_bytes(saved)
    run_json = runs[1] / "run.json"
    document = json.loads(run_json.read_bytes())
    run_json.write_text(json.dumps({**document, "commit": K}), encoding="utf-8")
    assert harness.order_check(directory)["problems"] == [f"{runs[1].name}/run.json#commit"]


def test_a_campaign_without_a_pin_or_preflight_record_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commit = clean_head(monkeypatch)
    campaign = stub_campaign(tmp_path / "runs", commit)
    common: dict[str, Any] = {
        "work": tmp_path / "w",
        "claude_code_version": stubs.STUB_VERSION,
        "coverage_path": campaign.coverage_path,
        "sample_path": campaign.sample_path,
        "runs_root": campaign.runs_root,
        "run_one": stub_runs(commit, stop_after=1),
    }
    with pytest.raises(harness.HarnessError, match="--model"):
        harness.campaign(NAME, config=harness.agent_config(None), preflight=dict, **common)
    with pytest.raises(harness.HarnessError, match="never passed"):
        harness.campaign(
            NAME, config=harness.agent_config(MODELS["M1"]), preflight=dict, resume=True, **common
        )
    shutil.rmtree(campaign.directory / "canary")
    with pytest.raises(harness.HarnessError, match="no counted canary attempt"):
        harness.campaign(
            NAME,
            config=harness.agent_config(MODELS["M1"]),
            preflight=lambda: {"P1": {"passed": True}},
            **common,
        )
    assert not (campaign.directory / "preflight.json").exists()
