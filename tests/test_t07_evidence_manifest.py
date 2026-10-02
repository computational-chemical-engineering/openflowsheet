"""T07 W8b, W8c: the evidence manifest generator (`scripts/t07_evidence_manifest.py`).

The generator's expensive inputs (the tests it runs, the identity protocol, Appendix J's timings,
CI) are replaced here by stated ones; everything it reads from the repository (the review and its
fix commits in git, the tool descriptions, the cited records, the canary exports) is read for
real. Asserted: the output validates against `schemas/evidence-manifest.schema.json` and holds no
angle-bracketed text; G17 is never `pass` without the verdict file, and follows it when present;
`reviewed` is never set, and the review fields stay `pending`; a failed or pending check keeps the
status at `implemented`.

W8c (V17 spec Amendment R6): G17 is judged on `v17-c2` alone, from the verdict rows citing its
`campaign.json`, never from `v17-c1`'s; V17 reads its own rows the same way; `v17-c1` is a reported
check that passes while its record stands as failed (19/30) and is a component of nothing; a
campaign whose files leave its `SHA256SUMS` fails; G16-c and R5b-O3 cover both campaigns. The
verdict file here is always a stated one: nothing depends on `docs/reviews/T07-verdicts.md`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import REPO_ROOT


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t07_evidence_manifest", REPO_ROOT / "scripts" / "t07_evidence_manifest.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their annotations through it
    spec.loader.exec_module(module)
    return module


generator = _load()
HEAD = generator._git("rev-parse", "HEAD").strip()


class AllPass(generator.TestRun):  # type: ignore[misc, name-defined]
    """Every selector names 40 passed nodes of 0.01 s; every module ran one."""

    def select(self, selector: str) -> dict[str, tuple[str, float]]:
        return {f"{selector}[{index}]": ("passed", 0.01) for index in range(40)}


def _tests(**failed: str) -> Any:
    nodes = {f"{module}::test_stated": ("passed", 0.01) for module in generator.test_modules()}
    run = AllPass(nodes, 0)
    if failed:

        class Failing(AllPass):
            def select(self, selector: str) -> dict[str, tuple[str, float]]:
                found = super().select(selector)
                if selector in failed.values():
                    return {name: ("failed", 0.01) for name in found}
                return found

        run = Failing(nodes, 0)
    return run


IDENTITY = {
    **generator.IDENTITY_EXPECTED,
    "k05_whole": generator.IDENTITY_RECORDED_PREFIX["k05_whole"] + "0" * 56,
    "key_t07": generator.IDENTITY_RECORDED_PREFIX["key_t07"] + "0" * 56,
    "k05_bytes": 1,
}
G18 = {
    "method": "stated",
    "grace_s": 0.5,
    "omp_num_threads": "1",
    "job_statuses": ["completed"],
    "g18_job_overhead_s": {"n": 20, "median": 0.5, "min": 0.4, "max": 0.51},
    "submit_to_ended_s": {"n": 20, "median": 0.62, "min": 0.52, "max": 0.63},
    "solve_elapsed_s": {"n": 20, "median": 0.12, "min": 0.12, "max": 0.13},
    "application_solve_round_trip_s": {"n": 5, "median": 0.64, "min": 0.54, "max": 0.64},
    "g5_cooperative_cancel_to_ended_s": {"values": [0.11] * 5},
    "g5_forced_cancel_to_ended_s": {"values": [0.61] * 5},
    "g5_cooperative_endings": [["cancelled", "cancel_requested", "cooperative"]] * 5,
    "g5_forced_endings": [["cancelled", "cancel_requested", "forced"]] * 5,
}
CI = [
    {
        "databaseId": 1,
        "workflowName": "ci",
        "event": "push",
        "headSha": HEAD,
        "conclusion": "success",
        "jobs": [{"name": name, "conclusion": "success"} for name in generator.CI_JOBS],
    }
]
GATE = {"passed": True, "pytest_counts": {"passed": 1}, "stdout_sha256": "0" * 64}
AGGREGATE = {
    "schema": "t07-v17-campaign-v1",
    "pooled_completion": {"complete": 27, "runs": 30, "threshold": 24, "met": True},
    "gates": {"unauthorized_effects": {"established": True, "total": 0}},
    "g17_mechanical": {"completion_met": True, "zero_gates_met": True},
    "tasks_with_zero": [],
    "infrastructure_failures": [],
    "harness_defects": 0,
    "cost": {"pooled": {}},
}
#: `v17-c1` as recorded: 19 of 30, every zero gate met.
AGGREGATE_C1 = {
    **AGGREGATE,
    "pooled_completion": {"complete": 19, "runs": 30, "threshold": 24, "met": False},
    "g17_mechanical": {"completion_met": False, "zero_gates_met": True},
}


@pytest.fixture(scope="module")
def review() -> dict[str, Any]:
    return generator.review_findings()  # type: ignore[no-any-return]


def _sha(campaign: Path) -> str:
    return hashlib.sha256((campaign / "campaign.json").read_bytes()).hexdigest()


def _campaign(
    tmp_path: Path,
    aggregate: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    name: str = "v17-c2",
) -> Path:
    """A campaign directory holding only its aggregate, listed in its `SHA256SUMS` (for `v17-c1`
    with the redaction's files beside it), which the re-aggregation reproduces."""
    campaign = tmp_path / name
    campaign.mkdir()
    data = json.dumps(aggregate, sort_keys=True).encode()
    (campaign / "campaign.json").write_bytes(data)
    listing = f"{hashlib.sha256(data).hexdigest()}  ./campaign.json\n"
    (tmp_path / f"{name}.SHA256SUMS").write_text(listing, "utf-8")
    if name == "v17-c1":
        (tmp_path / f"{name}.REDACTED.SHA256SUMS").write_text(listing, "utf-8")
        (tmp_path / f"{name}.SCORES-v1.SHA256SUMS").write_text(listing, "utf-8")
        (tmp_path / f"{name}.REDACTION.md").write_text("# redaction note\n", "utf-8")
    previous = generator.aggregate_campaign
    monkeypatch.setattr(
        generator, "aggregate_campaign", lambda c: data if c == campaign else previous(c)
    )
    return campaign


def _verdict(
    tmp_path: Path,
    cell: str,
    campaign: Path | None,
    cite: bool = True,
    rows: tuple[str, ...] = (),
) -> Path:
    """A stated verdict file: one G17 row on `campaign` (its digest in the row when `cite`),
    then `rows` as written."""
    digest = f" `{_sha(campaign)}`" if campaign and cite else ""
    path = tmp_path / "T07-verdicts.md"
    path.write_text(
        "# T07 verdicts\n\n"
        + "| # | Criterion | Verdict |\n| --- | --- | --- |\n"
        + f"| 1 | G17: the agent campaign `v17-c2`{digest} | {cell} |\n"
        + "".join(f"{row}\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _inputs(tmp_path: Path, **overrides: Any) -> Any:
    fields: dict[str, Any] = {
        "commit": HEAD,
        "tests": _tests(),
        "gate": GATE,
        "identity": IDENTITY,
        "g18": G18,
        "ci": CI,
        "campaign": tmp_path / "absent-campaign",
        "verdicts": tmp_path / "absent-verdicts.md",
        "campaign_c1": tmp_path / "absent-campaign-c1",
    }
    fields.update(overrides)
    return generator.Inputs(**fields)


def _manifest(inputs: Any, review: dict[str, Any]) -> dict[str, Any]:
    return generator.plain(generator.build(inputs, review=review))  # type: ignore[no-any-return]


def _check(manifest: dict[str, Any], identifier: str) -> dict[str, Any]:
    (entry,) = [e for e in manifest["checks"] if e["id"] == f"T07.{identifier}"]
    found: dict[str, Any] = entry
    return found


def test_the_manifest_validates_and_holds_no_angle_bracketed_text(
    tmp_path: Path, review: dict[str, Any]
) -> None:
    manifest = _manifest(_inputs(tmp_path), review)
    assert generator.problems(manifest) == []
    ids = [entry["id"] for entry in manifest["checks"]]
    assert len(ids) == len(set(ids))
    assert manifest["requirements"] == ["D15"]
    for gate in [f"G{n}" for n in range(1, 21)] + ["PLAN", "V17", "D15(a)", "D15(b)", "CI"]:
        assert f"T07.{gate}" in ids
    assert "T07.G17-c1" in ids


def test_every_cited_record_is_in_its_file(tmp_path: Path, review: dict[str, Any]) -> None:
    manifest = _manifest(_inputs(tmp_path), review)
    cited = [r for e in manifest["checks"] for r in e.get("value", {}).get("records", [])]
    assert cited and all(row["found"] for row in cited), [r for r in cited if not r["found"]]


def test_the_review_has_a_check_per_m_and_s_finding_each_with_a_fix(
    tmp_path: Path, review: dict[str, Any]
) -> None:
    assert (review["must"], review["should"], review["notes"]) == (2, 11, 12)
    manifest = _manifest(_inputs(tmp_path), review)
    for finding in review["findings"]:
        entry = _check(manifest, f"REVIEW.{finding.id}")
        assert entry["value"]["fix_commits"], finding.id


def test_g17_is_pending_without_the_campaign(tmp_path: Path, review: dict[str, Any]) -> None:
    manifest = _manifest(_inputs(tmp_path), review)
    g17 = _check(manifest, "G17")
    assert (g17["result"], g17["value"]["measured"]["state"]) == ("unsupported", "pending")
    assert _check(manifest, "PLAN")["result"] != "pass"
    assert _check(manifest, "V17")["result"] != "pass"
    assert manifest["status"] == "implemented"


def test_g17_is_never_pass_without_the_verdict_file(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _campaign(tmp_path, AGGREGATE, monkeypatch)
    manifest = _manifest(_inputs(tmp_path, campaign=campaign), review)
    g17 = _check(manifest, "G17")
    assert g17["result"] == "unsupported"
    assert g17["value"]["measured"]["state"] == "pending"
    assert g17["value"]["measured"]["g17_mechanical"]["completion_met"] is True
    assert manifest["status"] == "implemented"


@pytest.mark.parametrize(
    ("cell", "cite", "mechanical", "expected"),
    [
        ("**MET.** 27 of 30.", True, {"completion_met": True, "zero_gates_met": True}, "pass"),
        ("**NOT MET.** 19 of 30.", True, {"completion_met": True, "zero_gates_met": True}, "fail"),
        ("**MET.**", False, {"completion_met": True, "zero_gates_met": True}, "fail"),
        ("**MET.**", True, {"completion_met": False, "zero_gates_met": True}, "fail"),
        ("**MET.**", True, {"completion_met": True, "zero_gates_met": None}, "fail"),
        ("**INSUFFICIENT EVIDENCE.**", True, {"completion_met": True}, "unsupported"),
    ],
)
def test_g17_follows_the_verdict_and_the_arithmetic(
    tmp_path: Path,
    review: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    cell: str,
    cite: bool,
    mechanical: dict[str, Any],
    expected: str,
) -> None:
    campaign = _campaign(tmp_path, {**AGGREGATE, "g17_mechanical": mechanical}, monkeypatch)
    verdicts = _verdict(tmp_path, cell, campaign, cite)
    manifest = _manifest(_inputs(tmp_path, campaign=campaign, verdicts=verdicts), review)
    assert _check(manifest, "G17")["result"] == expected
    assert generator.problems(manifest) == []


def test_reviewed_is_never_set_even_when_every_check_passes(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _campaign(tmp_path, AGGREGATE, monkeypatch)
    c1 = _campaign(tmp_path, AGGREGATE_C1, monkeypatch, "v17-c1")
    v17 = f"| 2 | V17 on `v17-c2` `{_sha(campaign)}` | **MET.** |"
    verdicts = _verdict(tmp_path, "**MET.**", campaign, rows=(v17,))
    inputs = _inputs(tmp_path, campaign=campaign, campaign_c1=c1, verdicts=verdicts)
    manifest = _manifest(inputs, review)
    failing = [e["id"] for e in manifest["checks"] if e["result"] != "pass"]
    assert failing == []
    assert manifest["status"] == "tested"
    assert manifest["review"] == {"numerical": "pending", "process_model": "pending"}
    assert generator.status(manifest["checks"], True) == "tested"
    assert generator.status([{"result": "pass"}], True) not in {"reviewed", "released"}


@pytest.mark.parametrize("missing", ["ci", "identity", "g18"])
def test_a_missing_measurement_is_not_a_pass(
    tmp_path: Path, review: dict[str, Any], missing: str
) -> None:
    value: Any = [] if missing == "ci" else None
    manifest = _manifest(_inputs(tmp_path, **{missing: value}), review)
    assert manifest["status"] == "implemented"
    assert generator.problems(manifest) == []
    if missing == "ci":
        assert _check(manifest, "CI")["result"] == "unsupported"
        assert _check(manifest, "G19")["result"] == "unsupported"


def test_a_failed_test_fails_its_check_and_keeps_the_status(
    tmp_path: Path, review: dict[str, Any]
) -> None:
    tests = _tests(failed="tests/test_t07_w4d_duplicate_jobs.py")
    manifest = _manifest(_inputs(tmp_path, tests=tests), review)
    assert _check(manifest, "G4")["result"] == "fail"
    assert _check(manifest, "PLAN")["result"] == "fail"
    assert manifest["status"] == "implemented"


def test_a_moved_identity_digest_fails_g1(tmp_path: Path, review: dict[str, Any]) -> None:
    identity = {**IDENTITY, "t02_floats": "f" * 64}
    manifest = _manifest(_inputs(tmp_path, identity=identity), review)
    assert _check(manifest, "G1")["result"] == "fail"


def test_the_gate_log_is_read_as_written(tmp_path: Path) -> None:
    log = tmp_path / "gate.txt"
    log.write_text("6100 passed, 2 skipped in 400.1s\n=== check.sh: PASSED ===\n", "utf-8")
    assert generator.gate_log(log)["passed"] is True
    assert generator.gate_log(log)["pytest_counts"] == {"passed": 6100, "skipped": 2}
    log.write_text("1 failed, 6100 passed in 400.1s\n=== check.sh: FAILED ===\n", "utf-8")
    assert generator.gate_log(log)["passed"] is False


def test_junit_nodes_and_selectors(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<?xml version="1.0"?><testsuites><testsuite>'
        '<testcase classname="tests.test_t07_x" name="test_a[1]" time="1.5"/>'
        '<testcase classname="tests.test_t07_x" name="test_ab" time="0.5">'
        '<failure message="x"/></testcase>'
        '<testcase classname="tests.test_t07_x" name="test_c" time="0.1">'
        '<skipped type="pytest.skip" message="x"/></testcase>'
        "</testsuite></testsuites>",
        "utf-8",
    )
    run = generator.parse_junit(junit, 1)
    assert run.nodes == {
        "tests/test_t07_x.py::test_a[1]": ("passed", 1.5),
        "tests/test_t07_x.py::test_ab": ("failed", 0.5),
        "tests/test_t07_x.py::test_c": ("skipped", 0.1),
    }
    assert set(run.select("tests/test_t07_x.py::test_a")) == {"tests/test_t07_x.py::test_a[1]"}
    assert len(run.select("tests/test_t07_x.py::test_a*")) == 2
    assert len(run.select("tests/test_t07_x.py")) == 3
    assert run.select("tests/test_t07_y.py") == {}


# ----------------------------------------------------------------------------- W8c: two campaigns


def _both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, c1: dict[str, Any] | None = None
) -> tuple[Path, Path]:
    return (
        _campaign(tmp_path, AGGREGATE, monkeypatch),
        _campaign(tmp_path, c1 or AGGREGATE_C1, monkeypatch, "v17-c1"),
    )


def test_g17_is_judged_on_the_c2_rows_and_c1_is_reported_alongside(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, c1 = _both(tmp_path, monkeypatch)
    c1_row = f"| 3 | G17 on `v17-c1` `{_sha(c1)}` (reported) | **NOT MET.** 19 of 30. |"
    verdicts = _verdict(tmp_path, "**MET.** 25 of 30.", campaign, rows=(c1_row,))
    inputs = _inputs(tmp_path, campaign=campaign, campaign_c1=c1, verdicts=verdicts)
    manifest = _manifest(inputs, review)
    g17 = _check(manifest, "G17")
    assert g17["result"] == "pass"
    assert g17["value"]["measured"]["verdict"]["rows"] == 1
    reported = _check(manifest, "G17-c1")
    assert reported["result"] == "pass"
    measured = reported["value"]["measured"]
    assert measured["reads"] == generator.C1_RECORDED
    assert measured["gate_result"].startswith("NOT MET, 19/30")
    assert measured["verdict"]["citing_states"] == ["NOT MET"]
    for entry in manifest["checks"]:
        assert "G17-c1" not in (entry["value"].get("components") or {}), entry["id"]
    assert generator.problems(manifest) == []


def test_a_met_row_judging_c2_that_cites_c1_beside_it_does_not_re_judge_c1(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed verdict's shape (R6: "any claim cites both campaigns"): one G17 row, MET,
    citing c2 (judged) and c1 (reported). It passes G17 and leaves `v17-c1`'s record standing."""
    campaign, c1 = _both(tmp_path, monkeypatch)
    verdicts = _verdict(
        tmp_path,
        f"**MET.** 25 of 30 on `v17-c2`; `v17-c1` `{_sha(c1)}` failed (reported).",
        campaign,
    )
    inputs = _inputs(tmp_path, campaign=campaign, campaign_c1=c1, verdicts=verdicts)
    manifest = _manifest(inputs, review)
    assert _check(manifest, "G17")["result"] == "pass"
    reported = _check(manifest, "G17-c1")
    assert reported["result"] == "pass"
    assert reported["value"]["measured"]["verdict"]["rows_judging_campaign"] == 0


def test_a_c1_row_never_decides_g17(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no row citing `v17-c2`, a row citing `v17-c1` is not read for G17."""
    campaign, c1 = _both(tmp_path, monkeypatch)
    c1_row = f"| 3 | G17 on `v17-c1` `{_sha(c1)}` | **MET.** |"
    verdicts = _verdict(tmp_path, "unread", campaign, cite=False, rows=(c1_row,))
    manifest = _manifest(
        _inputs(tmp_path, campaign=campaign, campaign_c1=c1, verdicts=verdicts), review
    )
    assert _check(manifest, "G17")["result"] == "unsupported"
    # ... and `v17-c1` judged MET contradicts its record.
    assert _check(manifest, "G17-c1")["result"] == "fail"


def test_c1_is_pending_without_its_record_and_fails_when_its_record_changes(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _manifest(_inputs(tmp_path), review)
    reported = _check(manifest, "G17-c1")
    assert (reported["result"], reported["value"]["state"]) == ("unsupported", "pending")
    changed = {**AGGREGATE_C1, "pooled_completion": {"complete": 24, "runs": 30}}
    campaign, c1 = _both(tmp_path, monkeypatch, changed)
    manifest = _manifest(_inputs(tmp_path, campaign=campaign, campaign_c1=c1), review)
    assert _check(manifest, "G17-c1")["result"] == "fail"


def test_c1_needs_its_redaction_note(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, c1 = _both(tmp_path, monkeypatch)
    (tmp_path / "v17-c1.REDACTION.md").unlink()
    manifest = _manifest(_inputs(tmp_path, campaign=campaign, campaign_c1=c1), review)
    reported = _check(manifest, "G17-c1")
    assert reported["result"] == "fail"
    assert reported["value"]["measured"]["records"]["redaction_note"]["absent"] is True


def test_a_file_outside_the_campaigns_sums_fails_g17(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign, c1 = _both(tmp_path, monkeypatch)
    (campaign / "added.txt").write_text("x", "utf-8")
    verdicts = _verdict(tmp_path, "**MET.**", campaign)
    manifest = _manifest(
        _inputs(tmp_path, campaign=campaign, campaign_c1=c1, verdicts=verdicts), review
    )
    g17 = _check(manifest, "G17")
    assert g17["result"] == "fail"
    assert g17["value"]["measured"]["sha256sums"]["unlisted"] == ["added.txt"]


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("| 2 | V17 `{sha}` | **MET.** |", "pass"),
        ("| 2 | V17 `{sha}` | **NOT MET.** |", "fail"),
        ("| 2 | V17-T05-1 `{sha}` | **NOT MET.** |", "unsupported"),
        (None, "unsupported"),
    ],
)
def test_v17_reads_its_own_rows(
    tmp_path: Path,
    review: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    row: str | None,
    expected: str,
) -> None:
    campaign, c1 = _both(tmp_path, monkeypatch)
    rows = (row.format(sha=_sha(campaign)),) if row else ()
    verdicts = _verdict(tmp_path, "**MET.**", campaign, rows=rows)
    manifest = _manifest(
        _inputs(tmp_path, campaign=campaign, campaign_c1=c1, verdicts=verdicts), review
    )
    assert _check(manifest, "G17")["result"] == "pass"
    assert _check(manifest, "V17")["result"] == expected


def test_g16c_and_the_exports_cover_both_campaigns(
    tmp_path: Path, review: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    campaign = _campaign(tmp_path, AGGREGATE, monkeypatch)
    manifest = _manifest(_inputs(tmp_path, campaign=campaign), review)
    for identifier in ("G16-c", "R5b-O3"):
        entry = _check(manifest, identifier)
        assert (entry["result"], entry["value"]["measured"]["state"]) == ("unsupported", "pending")
        assert "v17-c1" in entry["value"]["measured"]["reason"]
    c1 = _campaign(tmp_path, AGGREGATE_C1, monkeypatch, "v17-c1")
    manifest = _manifest(_inputs(tmp_path, campaign=campaign, campaign_c1=c1), review)
    for identifier in ("G16-c", "R5b-O3"):
        entry = _check(manifest, identifier)
        assert entry["result"] == "pass"
        assert {"v17-c2", "v17-c1"} <= set(entry["value"]["measured"])


def test_the_committed_campaigns_match_their_sums_and_c1_reads_as_recorded() -> None:
    """On the committed records (no re-scoring): every file of both campaigns equals its sums,
    and `v17-c1`'s aggregate still reads 19/30 with every zero gate met."""
    for campaign in (generator.CAMPAIGN, generator.CAMPAIGN_C1):
        sums = generator.campaign_sums(campaign)
        assert sums["ok"], sums
    assert generator._sums_file(generator.CAMPAIGN_C1).name == "v17-c1.REDACTED.SHA256SUMS"
    c1 = json.loads((generator.CAMPAIGN_C1 / "campaign.json").read_bytes())
    reads = {
        "complete": c1["pooled_completion"]["complete"],
        "runs": c1["pooled_completion"]["runs"],
        "completion_met": c1["g17_mechanical"]["completion_met"],
        "zero_gates_met": c1["g17_mechanical"]["zero_gates_met"],
    }
    assert reads == generator.C1_RECORDED
    assert generator.C1_FAILURE_ANALYSIS.is_file()
