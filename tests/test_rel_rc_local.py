"""RP §6.1, §6.4–§6.6, §6.9: the standing RC job's local steps (ADR 0055 WO-R6).

`scripts/release_rc_local.py` ports 0.3.0's RC runner and record writers; these tests judge the
record writers on fixtures, each rule with a passing case and a failing control, RP's two changes
(step 12's single `r375.audit` given step 12's own runs file, §6.4; step 14's n ≥ 1 in place of
0.3.0's 190, §6.5), the runner's plan through a recording executor, its refusals, `rc/records.json`
and the promoted G11 collector, which writes what 0.2.0's `g11collect.py.txt` wrote.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m07_rc_keep  # noqa: E402
import release_rc  # noqa: E402
import release_rc_local as local  # noqa: E402

S13_TOOLS = REPO_ROOT / "evidence/S13/a3e508e35fc5451fe56fa7b70941621992d35b50/tools"
HEAD = subprocess.run(
    ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
).stdout.strip()


def _inputs(
    out: Path, codes: Mapping[str, int], logs: Mapping[str, str] | None = None, **extra: str
) -> local.Inputs:
    directory = out / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    for label, text in (logs or {}).items():
        (directory / f"{label}.log").write_text(text, encoding="utf-8")
    return local.Inputs(out, dict(codes), directory, HEAD, **extra)


def _results(checks: list[dict[str, Any]]) -> dict[str, str]:
    return {check["id"]: check["result"] for check in checks}


def _junit(path: Path, cases: list[tuple[str, str, str | None]], failures: int = 0) -> None:
    body = "".join(
        f'<testcase classname="{c}" name="{n}">' + (f"<{t}/>" if t else "") + "</testcase>"
        for c, n, t in cases
    )
    skipped = sum(1 for *_, t in cases if t == "skipped")
    path.write_text(
        f'<testsuites><testsuite tests="{len(cases)}" failures="{failures}" errors="0" '
        f'skipped="{skipped}">{body}</testsuite></testsuites>',
        encoding="utf-8",
    )


# -- step 11 --------------------------------------------------------------------------------------


def _step11(tmp_path: Path, edit: str | None, codes: Mapping[str, int]) -> dict[str, str]:
    committed = json.loads((REPO_ROOT / "benchmarks/m01/idaes-conformance.json").read_text("utf-8"))
    if edit == "inputs":
        committed["inputs"]["components_yaml_sha256"] = "0" * 64
    elif edit == "numbers":
        committed["inputs"]["records"]["H2"]["molar_mass"] *= 1 + 1e-15
    (tmp_path / "idaes-conformance.json").write_text(json.dumps(committed), encoding="utf-8")
    (tmp_path / "external-crosscheck-check.stdout.txt").write_text("PASS\n", encoding="utf-8")
    return _results(local.step11_checks(_inputs(tmp_path, codes)))


def test_step11_idaes_may_differ_only_in_its_inputs_hashes(tmp_path: Path) -> None:
    ran = {"step11-xcheck": 0, "step11-idaes": 0}
    assert set(_step11(tmp_path, "inputs", ran).values()) == {"pass"}
    assert _step11(tmp_path, None, ran)["a40.idaes_numbers_identical"] == "pass"
    assert _step11(tmp_path, "numbers", ran)["a40.idaes_numbers_identical"] == "fail"
    failed = _step11(tmp_path, None, {"step11-xcheck": 1, "step11-idaes": 2})
    assert failed == {
        "a40.crosscheck_exit": "fail",
        "a40.idaes_exit": "fail",
        "a40.idaes_numbers_identical": "fail",
    }


# -- step 12 --------------------------------------------------------------------------------------

STEP12_CODES = {
    "reactor-build": 0,
    "reactor-verify": 0,
    "step12-g10": 0,
    "step12-g11": 0,
    "step12-g12": 0,
    "step12-g12-edges": 0,
    "step12-m02-tests": 0,
}


def _step12(
    tmp_path: Path,
    codes: Mapping[str, int] = STEP12_CODES,
    lock: str | None = None,
    judge_ok: bool = True,
    threads: str = "OMP/OPENBLAS/MKL_NUM_THREADS=1",
    failures: int = 0,
) -> dict[str, str]:
    real = local.sha256(REPO_ROOT / "src/openflowsheet/adapters/pymrm/reactor-env.lock")
    (tmp_path / "env-manifest.json").write_text(json.dumps({"lock_sha256": lock or real}), "utf-8")
    environment = {
        "threads": threads,
        "python": "3",
        "platform": "x",
        "packages": {"a": "1"},
        "cpu_model": "c",
    }
    (tmp_path / "g10-adapter-halves-v3.json").write_text(json.dumps({"environment": environment}))
    _junit(tmp_path / "m02-tests.junit.xml", [("t", "a", None)], failures)

    def judge() -> tuple[dict[str, Any], bool]:
        if judge_ok is None:
            raise KeyError("summary")
        return {}, judge_ok

    judges = dict.fromkeys(("g10", "g11", "g12"), judge)
    return _results(local.step12_checks(_inputs(tmp_path, codes), judges))


def test_step12_a41_checks_and_their_controls(tmp_path: Path) -> None:
    assert set(_step12(tmp_path).values()) == {"pass"}
    assert _step12(tmp_path, lock="0" * 64)["a41.environment_from_c_alpha_lock"] == "fail"
    assert (
        _step12(tmp_path, {**STEP12_CODES, "reactor-verify": 1})[
            "a41.environment_from_c_alpha_lock"
        ]
        == "fail"
    )
    assert {_step12(tmp_path, judge_ok=False)[f"a41.g1{k}"] for k in "012"} == {"fail"}
    assert _step12(tmp_path, judge_ok=None)["a41.g11"] == "fail"  # type: ignore[arg-type]
    assert _step12(tmp_path, {**STEP12_CODES, "step12-g12-edges": 1})["a41.g12"] == "fail"
    assert _step12(tmp_path, threads="4")["a41.one_thread_environment_recorded"] == "fail"
    assert _step12(tmp_path, failures=1)["a41.m02_tests_with_reactor"] == "fail"


AUDIT_LINE = (
    "G11 experiments audit: 2 runs, 210 boundary points, 210 results, 210 attempts, 0 without a "
    "result, 32 direct points (no records); 6 items + schema: 0 problems; context (job_id): 7 "
    "findings: PASS"
)


def test_step12_experiments_holds_exactly_r375_audit_given_step12s_own_runs_file(
    tmp_path: Path,
) -> None:
    """§6.4 item 4: one check, its line exactly, j recorded; the audit reads step 12's runs file."""
    seen: list[list[str]] = []

    def audit(code: int, line: str) -> local.Audit:
        def run(argv: list[str]) -> tuple[int, str]:
            seen.append(argv)
            return code, f"progress\n{line}\n"

        return run

    i = _inputs(tmp_path / "step12", {})
    (check,) = local.step12_experiments_checks(i, audit(0, AUDIT_LINE))
    assert (check["id"], check["result"], check["job_id_findings"]) == ("r375.audit", "pass", 7)
    runs = seen[0][seen[0].index("--runs") + 1]
    assert runs == str(tmp_path / "step12" / "g11-coverage-v3.runs.json")
    assert seen[0][-2:] == [
        str(tmp_path / f"step12/experiments/g11-experiments-run{k}.json") for k in (1, 2)
    ]
    for code, line in (
        (1, AUDIT_LINE),
        (0, AUDIT_LINE.replace("210 results", "209 results")),
        (0, AUDIT_LINE.replace("PASS", "FAIL")),
    ):
        (control,) = local.step12_experiments_checks(i, audit(code, line))
        assert control["result"] == "fail"


# -- steps 13–15 ----------------------------------------------------------------------------------


def test_step13_generator_claims_and_tests(tmp_path: Path) -> None:
    _junit(tmp_path / "m04-tests.junit.xml", [("t", "a", None)])
    codes = {"step13-generator": 0, "step13-fixtures": 0, "step13-tests": 0}
    good = {"step13-generator": "12 claims passed\n"}
    assert set(_results(local.step13_checks(_inputs(tmp_path, codes, good))).values()) == {"pass"}
    bad = {"step13-generator": "12 claims passed\nrecord differs\n"}
    assert (
        _results(local.step13_checks(_inputs(tmp_path, codes, bad)))["a60.w23.generator_check"]
        == "fail"
    )


def _collect(*ids: str) -> str:
    return "".join(f"{node}\n" for node in ids) + f"\n{len(ids)} tests collected\n"


def test_step14_nlp_selection_is_rps_n_at_least_one_not_0_3_0s_190() -> None:
    nodes = ("tests/test_a.py::x", "tests/test_b.py::y", "tests/test_b.py::z")
    passed, value = local.nlp_selection(_collect(*nodes), _collect(*nodes), 0, ["tests/test_a.py"])
    assert passed and value["selected_count"] == 3 and value["equal"]
    assert not local.nlp_selection(_collect(*nodes), _collect(*nodes[:2]), 0, ["m"])[0]
    assert not local.nlp_selection(_collect(), _collect(), 0, ["m"])[0]
    assert not local.nlp_selection(_collect(*nodes), _collect(*nodes), 2, ["m"])[0]
    assert not local.nlp_selection(_collect(*nodes), _collect(*nodes), 0, [])[0]


def test_step14_record_reads_the_nlp_check_lines(tmp_path: Path) -> None:
    (tmp_path / "nlp-modules.txt").write_text("tests/test_a.py\n", encoding="utf-8")
    _junit(tmp_path / "m03-m05-tests.junit.xml", [("t", "a", None)])
    check = "--- pytest -m nlp: exit 0\n--- inventory --check: exit 0\n"
    logs = {
        "step14-nlp-check": check + "--- inventory --check (trsp-exe): exit 0\n",
        "step14-nlp-collect-selected": _collect("tests/test_a.py::x"),
        "step14-nlp-collect-all": _collect("tests/test_a.py::x") + "ERROR mpmath\n",
        "step14-m05-real-replay": "REPLAY PASS REAL differences=0\n",
    }
    codes = {
        "step14-nlp-check": 0,
        "step14-tests": 0,
        "step14-m05-real-replay": 0,
        "step14-m03-reference": 0,
        "step14-nlp-collect-selected": 0,
        "step14-nlp-collect-all": 2,
    }
    assert set(_results(local.step14_checks(_inputs(tmp_path, codes, logs))).values()) == {"pass"}
    logs["step14-nlp-check"] = check
    assert (
        _results(local.step14_checks(_inputs(tmp_path, codes, logs)))[
            "a60.w24.nlp_tier_and_inventory"
        ]
        == "fail"
    )


def test_step15_carry_line_and_the_journey_commands(tmp_path: Path) -> None:
    codes = {"step15-carry": 0, "step15-check": 0, "step15-replay": 0}
    logs = {"step15-carry": "RC step 15: journey 2d945b5d carried\n"}
    i = _inputs(tmp_path, codes, logs, line="0.4", journey="2d945b5d" + "0" * 32)
    checks = local.step15_checks(i)
    assert _results(checks) == dict.fromkeys(
        ("a21.carry_journey", "a21.check", "a21.replay"), "pass"
    )
    assert "release_gate.py --line 0.4" in checks[0]["command"]
    logs["step15-carry"] = "RC step 15: journey 2d945b5d not carried: src changed\n"
    assert (
        _results(local.step15_checks(_inputs(tmp_path, codes, logs)))["a21.carry_journey"] == "fail"
    )


# -- A-11 item 4 (R-1008; S6R-17, S6R-18): the platform fields of steps 14 and 15 ------------------

P0 = "Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41"
P1 = "Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41"


def _s0(directory: Path, host: str) -> None:
    path = directory / local.REAL_S0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"frozen": {"reactor": {"fingerprint": {"platform": host}}}}), encoding="utf-8"
    )


def test_s6r17_the_real_replay_carries_both_platforms_and_is_judged_on_its_log_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    committed = local.ROOT / "benchmarks/m05/records" / local.REAL_S0
    leaf = json.loads(committed.read_bytes())["frozen"]["reactor"]["fingerprint"]["platform"]
    (real,) = [c for c in local.step14_checks(_inputs(tmp_path, {})) if "real_replay" in c["id"]]
    assert real["host_platform"] == local.platform.platform()
    assert real["record_platform"] == leaf
    root = tmp_path / "c"
    _s0(root / "benchmarks/m05/records", P0)
    for log, code, result in (
        ("REPLAY PASS REAL differences=0\n", 0, "pass"),
        ("REPLAY FAIL REAL differences=48\n", 1, "fail"),
    ):
        for host in (P0, P1):
            monkeypatch.setattr(local.platform, "platform", lambda host=host: host)
            i = _inputs(tmp_path, {"step14-m05-real-replay": code}, {"step14-m05-real-replay": log})
            (real,) = [c for c in local.step14_checks(i, root) if "real_replay" in c["id"]]
            assert real["id"] == "a60.w24.m05_g10_real_replay"
            assert (real["result"], real["host_platform"], real["record_platform"]) == (
                result,
                host,
                P0,
            )


def _replay(tmp_path: Path, root: Path, journey: str) -> dict[str, Any]:
    codes = {"step15-carry": 0, "step15-check": 0, "step15-replay": 0}
    i = _inputs(tmp_path, codes, {}, line="0.4", journey=journey)
    (replay,) = [c for c in local.step15_checks(i, root) if c["id"] == "a21.replay"]
    assert replay["result"] == "pass"
    return replay


def test_s6r18_the_journey_replay_reads_the_platform_of_the_m05_record_r3_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local.platform, "platform", lambda: P1)
    root, journey = tmp_path / "c", "a" * 40
    _s0(root / "benchmarks/m05/records", P0)
    carried = _replay(tmp_path, root, journey)
    assert (carried["host_platform"], carried["record_platform"]) == (P1, P0)
    _s0(root / "benchmarks/m07/journey" / journey / "m05", P1)
    rerun = _replay(tmp_path, root, journey)
    assert (rerun["host_platform"], rerun["record_platform"]) == (P1, P1)
    (root / "benchmarks/m07/journey" / journey / "m05" / local.REAL_S0).unlink()
    missing = _replay(tmp_path, root, journey)
    assert missing["record_platform"] is None
    assert "FileNotFoundError" in missing["record_platform_reason"]
    (check,) = [
        c for c in local.step15_checks(_inputs(tmp_path, {}), root) if c["id"] == "a21.check"
    ]
    assert "host_platform" not in check


# -- step 16 --------------------------------------------------------------------------------------


def _g15(tmp_path: Path, edit: str | None = None) -> bool:
    cases: list[tuple[str, str, str | None]] = [(c, n, None) for c, n in local.G15_NODES]
    cases.append(("tests.test_m06_other", "test_x", None))
    if edit == "skipped":
        cases[-1] = ("tests.test_m06_other", "test_x", "skipped")
    elif edit == "missing":
        cases.pop(0)
    elif edit == "failed":
        cases[3] = (*cases[3][:2], "failure")
    elif edit == "twice":
        cases.append(cases[0])
    _junit(tmp_path / "m06.xml", cases)
    return local.g15_registered_states(tmp_path / "m06.xml")[0]


def test_step16_c_the_25_registered_states_and_controls(tmp_path: Path) -> None:
    assert len(local.G15_NODES) == 25
    assert _g15(tmp_path)
    for edit in ("skipped", "missing", "failed", "twice"):
        assert not _g15(tmp_path, edit), edit
    assert not local.g15_registered_states(tmp_path / "absent.xml")[0]


def test_step16_d_the_refusal_is_the_expected_outcome() -> None:
    log = "Traceback (most recent call last):\n  ...\n" + local.W27_V1_REFUSAL + "\n\n"
    assert local.w27_v1_refusal(1, log, False)[0]
    assert not local.w27_v1_refusal(0, log, False)[0]
    assert not local.w27_v1_refusal(2, log, False)[0]
    assert not local.w27_v1_refusal(1, log, True)[0]
    assert not local.w27_v1_refusal(1, log + "more\n", False)[0]


def test_record_writes_t08_rc_v1_with_0_3_0s_path_step_and_ids(tmp_path: Path) -> None:
    rc, logs = tmp_path / "rc", tmp_path / "logs"
    (rc / "step13").mkdir(parents=True)
    logs.mkdir()
    _junit(rc / "step13" / "m04-tests.junit.xml", [("t", "a", None)])
    (logs / "step13-generator.log").write_text("claims passed\n", encoding="utf-8")
    summary = tmp_path / "summary.txt"
    summary.write_text(
        "".join(f"step13-{s} exit 0 :: cmd\n" for s in ("generator", "fixtures", "tests")), "utf-8"
    )
    assert local.write_record("step13", rc, HEAD, summary, logs) == 0
    record = json.loads((rc / "step13" / "rc-step13.json").read_text(encoding="utf-8"))
    assert (record["format"], record["step"], record["passed"]) == (
        "t08-rc-v1",
        "w23-m04-records",
        True,
    )
    assert [c["id"] for c in record["checks"]] == [
        "a60.w23.generator_check",
        "a60.w23.schema_fixtures",
        "a60.w23.tests",
    ]
    assert record["provenance"]["commit"] == HEAD and "machine_class" in record["provenance"]
    summary.write_text(summary.read_text("utf-8") + "step13-tests exit 1 :: cmd\n", "utf-8")
    assert local.write_record("step13", rc, HEAD, summary, logs) == 1


# -- rc/records.json and the kept certificates ----------------------------------------------------


def test_records_json_size_rule_and_refusals(tmp_path: Path) -> None:
    source, target = tmp_path / "artifacts" / "rc", tmp_path / "rc"
    (source / "step12").mkdir(parents=True)
    (source / "step12" / "small.json").write_bytes(b"{}")
    big = b"x" * (local.SIZE_LIMIT + 1)
    (source / "step12" / "big.json").write_bytes(big)
    cited = ["step12/small.json", "step12/big.json"]
    index = local.collect_records(source, target, cited, HEAD, "docs/R-rc-record.md", "REL040")
    assert index["format"] == "m07a-rc-records-v1" and index["commit"] == HEAD
    small, large = index["files"]
    assert (small["committed"], large["committed"]) == (True, False)
    assert (target / "step12" / "small.json").read_bytes() == b"{}"
    assert gzip.decompress((target / "step12" / "big.json.gz").read_bytes()) == big
    assert large["sha256"] == local.hashlib.sha256(big).hexdigest() and large["bytes"] == len(big)
    assert json.loads((target / "records.json").read_text("utf-8")) == index
    with pytest.raises(ValueError, match="cited twice"):
        local.collect_records(source, target, [*cited, cited[0]], HEAD, "r", "P")
    with pytest.raises(ValueError, match="not under"):
        local.collect_records(source, target, ["step12/absent.json"], HEAD, "r", "P")


def test_kept_g12_certificates_lose_the_artifacts_segment(tmp_path: Path) -> None:
    kept = tmp_path / "g12-bundles/m02-g12-0/bundle/artifacts/solution-certificate.json"
    kept.parent.mkdir(parents=True)
    kept.write_text("{}", encoding="utf-8")
    assert local.keep_certificates(tmp_path) == [
        "certificates/g12-bundles/m02-g12-0/bundle/solution-certificate.json"
    ]


# -- the runner -----------------------------------------------------------------------------------


def _plan(tmp_path: Path, steps: tuple[int, ...], **extra: Any) -> local.Plan:
    return local.Plan(
        line="0.4", commit=HEAD, rc=tmp_path / "rc", work=tmp_path / "w", steps=steps, **extra
    )


def test_missing_inputs_refuse_before_anything_runs(tmp_path: Path) -> None:
    inside = REPO_ROOT / "evidence/RP" / HEAD / "artifacts/rc"
    full = {"nlp_prefix": Path("/n"), "nlp_cache": Path("/c"), "journey": "j" * 40}
    plan = _plan(tmp_path, (14, 15), **full)
    plan.rc = inside
    assert local.missing_inputs(plan) == []
    refusals = [
        ({**full, "nlp_cache": None}, "--nlp-prefix and --nlp-cache (step 14, 15)"),
        ({**full, "journey": None}, "--journey (step 15)"),
    ]
    for given, refusal in refusals:
        plan = _plan(tmp_path, (14, 15), **given)
        plan.rc = inside
        assert local.missing_inputs(plan) == [refusal]
    assert local.missing_inputs(_plan(tmp_path, (2,)))[0].startswith("--rc inside the checkout")


def _run(
    tmp_path: Path, steps: tuple[int, ...], *, exit_code: int = 0, **extra: Any
) -> list[tuple[str, list[str], Path]]:
    seen: list[tuple[str, list[str], Path]] = []

    def execute(argv: list[str], log: Path, env: Mapping[str, str], cwd: Path) -> int:
        seen.append((log.stem, argv, cwd))
        log.write_text("", encoding="utf-8")
        return 0

    plan = _plan(tmp_path, steps, **extra)
    (plan.work / "rcvenv/bin").mkdir(parents=True)
    (plan.work / "rcvenv/bin/python").touch()
    if not (plan.work / "nlp-wt").exists():
        os.symlink(REPO_ROOT, plan.work / "nlp-wt")  # a checkout at HEAD = C
    with mock.patch.object(local, "_output", _clean_status(local._output)):
        assert local.Runner(plan, execute=execute).run() == exit_code
    return seen


def _clean_status(output: Any) -> Any:
    """`_output`, with `git status --porcelain` empty: the symlinked nlp worktree is this checkout,
    whose working tree a test run may change (C-12's own test uses a real repository)."""

    def found(argv: list[str], *args: Any, **kwargs: Any) -> str:
        return (
            ""
            if argv[:3] == ["git", "status", "--porcelain"] and len(argv) == 3
            else output(argv, *args, **kwargs)
        )

    return found


def test_the_runner_runs_only_the_selected_steps_in_0_3_0s_order(tmp_path: Path) -> None:
    seen = _run(tmp_path, (2, 13))
    labels = [label for label, *_ in seen]
    basetemp = next(a for a in seen[-2][1] if a.startswith("--basetemp="))
    assert Path(basetemp.removeprefix("--basetemp=")).parent.is_dir()
    assert labels == [
        "step02-identity",
        "step13-generator",
        "step13-fixtures",
        "step13-tests",
        "record-step13",
    ]


def test_the_runner_plan_for_steps_12_14_15(tmp_path: Path) -> None:
    nlp = {"nlp_prefix": Path("/n"), "nlp_cache": Path("/c"), "journey": "a" * 40}
    seen = {label: (argv, cwd) for label, argv, cwd in _run(tmp_path, (12, 14, 15), **nlp)}
    g11, _ = seen["step12-g11"]
    assert g11[1:4] == ["scripts/m07_rc_keep.py", "g11", str(tmp_path / "w/g11-keep")]
    assert "--d78" in g11 and "--previous-runs" not in g11
    assert seen["step12-g11-collect"][0][-2:] == [
        str(tmp_path / "rc/step12/g11-coverage-v3.runs.json"),
        str(tmp_path / "rc/step12/experiments"),
    ]
    assert seen["step12-g12"][0][1:3] == ["scripts/m07_rc_keep.py", "g12"]
    modules = (tmp_path / "rc/step14/nlp-modules.txt").read_text("utf-8").split()
    assert modules and all("mark.nlp" in (REPO_ROOT / m).read_text("utf-8") for m in modules)
    check, cwd = seen["step14-nlp-check"]
    assert cwd == tmp_path / "w/nlp-wt" and check[-len(modules) :] == modules
    assert seen["step14-nlp-collect-all"][0][-1] == "tests/"
    assert seen["step15-carry"][0][1:] == [
        "scripts/release_gate.py",
        "--line",
        "0.4",
        "--rc",
        HEAD,
        "--carry-journey",
        "a" * 8,
    ]
    for record in ("step12", "step12-experiments", "step14", "step15"):
        assert f"record-{record}" in seen


def test_the_runner_exits_on_its_records_not_on_expected_non_zero_commands() -> None:
    assert local.records_passed({"step16-dryrun": 1, "record-step16": 0, "step17-items": 0})
    assert local.records_passed({"record-step16": 0, "stop-nlp-wt": 0})
    assert not local.records_passed({"record-step16": 0, "stop-step12-inputs": 2})
    assert not local.records_passed({"record-step16": 1})
    assert not local.records_passed({"record-step16": 0, "step17-items": 1})
    assert not local.records_passed({})


def test_nlp_items_run_from_the_given_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-12: the runner gives the `nlp` items its clean nlp worktree; other items run from ROOT."""
    seen: dict[str, Path] = {}

    def run(argv: list[str], log: Path, environment: dict[str, str], cwd: Path = REPO_ROOT) -> int:
        seen[log.stem] = cwd
        log.write_text("", encoding="utf-8")
        return 0

    items = [
        {"id": "N", "where": "local:nlp", "assertion": "a", "command": ["bash", "x.sh"]},
        {"id": "P", "where": "local:project", "assertion": "a", "command": ["python", "y.py"]},
    ]
    monkeypatch.setattr(release_rc, "_run_to_log", run)
    monkeypatch.setattr(release_rc, "_line_items", lambda line: items)
    release_rc.items(
        "0.4", tmp_path, HEAD, {"project": "p"}, (None, None), None, {"nlp": tmp_path / "wt"}
    )
    assert seen == {"N": tmp_path / "wt", "P": REPO_ROOT}


# -- the promoted G11 keep and collect (RP §6.4 item 1) -------------------------------------------


def _keep_fixture(tmp_path: Path) -> tuple[Path, Path]:
    keep = tmp_path / "keep"
    experiment = keep / "run1/m02-g11v3-P1/records/experiments/ab/abcdef"
    (experiment / "attempts").mkdir(parents=True)
    (experiment / "request.json").write_text('{"r": 1}', encoding="utf-8")
    (experiment / "result.json").write_text('{"ok": true}', encoding="utf-8")
    for n in (10, 2):
        (experiment / "attempts" / f"{n}.json").write_text(f'{{"n": {n}}}', encoding="utf-8")
    (keep / "run1/m02-g11v3-P2").mkdir()
    runs = tmp_path / "runs.json"
    runs.write_text(
        json.dumps([[{"label": "P1", "path": "boundary"}, {"label": "P2", "path": "direct"}]]),
        "utf-8",
    )
    return keep, runs


def test_g11_collect_writes_what_0_2_0s_collector_wrote(tmp_path: Path) -> None:
    keep, runs = _keep_fixture(tmp_path)
    provenance = {"commit": HEAD}
    assert m07_rc_keep.collect(keep, runs, tmp_path / "new", provenance) == 0
    new = json.loads((tmp_path / "new/g11-experiments-run1.json").read_text("utf-8"))
    (point, direct) = new["points"]
    assert [a["n"] for a in point["experiments"][0]["attempts"]] == [2, 10]
    assert direct["experiments"] is None and new["format"] == m07_rc_keep.FORMAT
    old_out = tmp_path / "old"
    old_out.mkdir()
    done = subprocess.run(
        [sys.executable, str(S13_TOOLS / "g11collect.py.txt"), str(keep), str(runs), str(old_out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    old = json.loads((old_out / "g11-experiments-run1.json").read_text("utf-8"))
    ignored = ("description", "provenance")
    assert {k: v for k, v in old.items() if k not in ignored} == {
        k: v for k, v in new.items() if k not in ignored
    }


def test_g11_collect_refuses_kept_directories_that_are_not_the_runs_points(tmp_path: Path) -> None:
    keep, runs = _keep_fixture(tmp_path)
    (keep / "run1/m02-g11v3-P3").mkdir()
    assert m07_rc_keep.collect(keep, runs, tmp_path / "out", {}) == 1
    assert not (tmp_path / "out/g11-experiments-run1.json").exists()


def test_g11_keep_shim_names_each_points_directory_and_keeps_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(m07_rc_keep.KEEP, str(tmp_path))
    monkeypatch.setenv(m07_rc_keep.RUN, "run2")
    with m07_rc_keep._G11Kept(prefix="m02-g11v3-P7-") as name:
        assert name == str(tmp_path / "run2" / "m02-g11v3-P7")
    assert Path(name).is_dir()
    with m07_rc_keep._Runs(max_workers=1):
        assert os.environ[m07_rc_keep.RUN].startswith("run")
    assert os.environ[m07_rc_keep.RUN] == "after-runs"


# -- amendment A-5 (RP §6.4; review S-5) and C-12 (the nlp worktree at C, clean) ------------------


def test_a5_step12_s_inputs_are_registered_by_sha256(monkeypatch: pytest.MonkeyPatch) -> None:
    """The archived inputs at the full commit, each equal to its registered SHA-256 (the hashes in
    RP §6.4, read independently by `git show` here). Controls: a failed read, a changed byte."""
    found = local.step12_inputs(local._git_show)
    assert {name: hashlib.sha256(data).hexdigest() for name, data in found.items()} == {
        "g10-adapter-halves-v3": "c6a520e08433791cdea48821b981dd661a606e86bf99c740ff6bd26c86022586",
        "g11-coverage-v3": "fa1b02544f00a1ce02a203dc8cccc9d7bc5e35122a79cfe1506e355bb9729a90",
    }
    assert local.STEP12_INPUTS_AT == "bd446abab1bcc26b286ae4a287d1de131d87ceac"
    with pytest.raises(ValueError, match="could not be read"):
        local.step12_inputs(lambda at: None)
    with pytest.raises(ValueError, match="not the registered"):
        local.step12_inputs(lambda at: (local._git_show(at) or b"") + b" ")


def test_a5_unreadable_inputs_stop_step_12(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local, "_git_show", lambda at: None)
    labels = [label for label, *_ in _run(tmp_path, (12,), exit_code=1)]
    assert "step12-g10" not in labels and "step12-g11" not in labels
    summary = (tmp_path / "w" / "summary.txt").read_text("utf-8")
    assert "stop-step12-inputs exit 2 :: bd446abab1bcc26b286ae4a287d1de131d87ceac:" in summary


def test_c12_the_nlp_worktree_problem() -> None:
    assert local.nlp_tree_problem(HEAD, "", HEAD) is None
    assert local.nlp_tree_problem("d" * 40, "", HEAD) == f"HEAD {'d' * 40} is not C = {HEAD}"
    assert local.nlp_tree_problem("", "", HEAD) == f"HEAD (none) is not C = {HEAD}"
    assert local.nlp_tree_problem(HEAD, " M src/x.py\n?? y\n", HEAD) == (
        "not clean: 2 paths (M src/x.py, ?? y)"
    )


def test_c12_an_nlp_worktree_not_at_c_stops_step_14(tmp_path: Path) -> None:
    """A real repository at another commit as the nlp worktree: step 14 does not run, and the
    runner exits 1 on `stop-nlp-wt`. Control: the plan test above (a checkout at C, clean)."""
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    (other / "f").write_text("f\n", encoding="utf-8")
    git = ["git", "-C", str(other), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "add", "f"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "other"], check=True)
    (tmp_path / "w").mkdir()
    os.symlink(other, tmp_path / "w" / "nlp-wt")
    nlp = {"nlp_prefix": Path("/n"), "nlp_cache": Path("/c")}
    labels = [label for label, *_ in _run(tmp_path, (14,), exit_code=1, **nlp)]
    assert "step14-nlp-check" not in labels
    summary = (tmp_path / "w" / "summary.txt").read_text("utf-8")
    assert f"stop-nlp-wt exit 2 :: {tmp_path / 'w' / 'nlp-wt'}: HEAD " in summary
