"""M05 WO-9: gate G11 judged on the committed REAL record (design note §13 G11, §12 WO-9 as amended
by §20.7, §7.5 `M05-budget-v1`, §17.2; build log S65-S69).

`benchmarks/m05/records/trust-region-study-real.json` was written by `scripts/m05_wo9_real.py` at
`OMP_NUM_THREADS=1` in the `nlp` environment with the pinned reactor environment (`pymrm` tier);
G10's REAL part is that script's `--replay` (the replay from the record, F-20; the numbers are in
the build log). The criteria are §13's G11 row, never loosened here; the optimality outcome is
reported, not gated (W25), so no test asserts the study status or the decision.

Default gate: reads the committed files; nothing runs. S6R-20 (R-1008): `--retake-into`'s three
refusals, each before the run starts. S6R-28 (WO-7 (b)): a re-take keeps the store's non-empty child
logs, on a synthetic store that a stubbed run leaves.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
import m05_replay as replay  # noqa: E402

RECORDS = REPO_ROOT / "benchmarks" / "m05" / "records"
STEM = RECORDS / "trust-region-study-real"
#: §7.5's REAL row of `M05-budget-v1`.
STUDY_COLD, STUDY_WALL_S, RUN_COLD, RUN_ITERATIONS = 400, 4 * 3600.0, 250, 30
#: The measured count (build log S69): of the reactor link's 61 requests, 12 were served by an
#: experiment outside the kinetics' data domain (10 of its 32 cold experiments).
EXTRAPOLATED, TRUTH_REQUESTS = 12, 61
#: R-433 (§21.4): the `extrapolated` limitation as M05's manifest and W24 text state it — the
#: ledger count, and the data-edge flip at C1's loop state. WO-10b copies it verbatim.
EXTRAPOLATED_LIMITATION = (
    "extrapolated: 12 of 61 reactor requests, reported, not a distance from the data. At C1's "
    "loop state the reactor-inlet H2/N2 sits on the kinetics' data edge, so the per-evaluation "
    "flag is decided at solver resolution: it flips between solves 3.5e-5 K apart (cand-C1's P1 "
    "solve extrapolated, its minus poll at 653.15 K not)."
)
#: A typed TRF outcome (§6.7, R-401): a name, with a reason in parentheses for the refused,
#: errored and unverified outcomes.
TYPED_OUTCOME = re.compile(r"TRF_[A-Z_]+(\([^()]+\))?")
#: §7.4's candidate statuses.
CANDIDATE_STATUSES = frozenset(
    {
        "PARENT_CHECK_FAILED",
        "REGIME_CHANGED",
        "PARENT_CONSTRAINT_VIOLATED",
        "PROJECTION_DISAGREES",
        "NOT_STATIONARY_AT_DELTA",
        "PARENT_LOCAL_EVIDENCE",
        "NOT_CHECKED",
    }
)
STUDY_STATUSES = re.compile(
    r"DECISION_STABLE|ITERATION_LIMIT|BUDGET_EXHAUSTED|FAILED\(.+\)|UNSUPPORTED\(.+\)"
)


def _read(suffix: str) -> Any:
    return json.loads(STEM.with_suffix(suffix).read_text(encoding="utf-8"))


def record() -> dict[str, Any]:
    document: dict[str, Any] = _read(".json")
    return document


def test_the_record_is_reals_and_anchored() -> None:
    """The REAL configuration (§7.5, R-313) and M07's FD-3 anchor (S65): the run commit, a clean
    tree, the spent wall time; the sidecars' digests are the record's."""
    document = record()
    spec = document["spec"]
    assert spec["case"] == "REAL"
    assert spec["truth"]["id"] == "pymrm-6089593-g2-nz800-s123-v3"
    assert spec["truth"]["synthetic"] is False
    assert spec["truth"]["gradient"] == "finite_difference"
    assert spec["decisions"] == [{"id": "preheater.T_spec", "lower": 653.15, "upper": 693.15}]
    assert spec["budgets"]["configuration"] == "REAL"
    assert spec["configs"]["basis"] == "M05-basis-v2"
    assert document["stage_a"] == {"executed": False, "reason": "surrogate_not_promoted"}
    provenance = document["provenance"]
    assert re.fullmatch(r"[0-9a-f]{40}", provenance["run_commit"])
    assert provenance["tree_clean"] is True
    assert 0.0 < provenance["wall_s"]
    artifacts = document["artifacts"]
    for suffix, name in ((".ledger.json", "ledger"), (".experiments.json", "experiment_store")):
        digest = hashlib.sha256(STEM.with_suffix(suffix).read_bytes()).hexdigest()
        assert digest == artifacts[name]


def test_g11_the_fd_check_is_recorded() -> None:
    """G11: `fd_check` with its class, τ̂, ν̂ and selected η (§17.2)."""
    check = record()["fd_check"]
    assert check["policy"] == "M05-fd-v2"
    assert check["class"] in ("clean", "truncation_dominated", "noise_dominated")
    assert check["result"] in ("pass", "fd_unstable")
    (selected,) = [c for c in check["candidates"] if c["eta"] == check["selected_eta"]]
    assert selected["class"] == check["class"]
    assert all(math.isfinite(selected[key]) for key in ("truncation", "noise", "g_inf"))
    assert check["selected_eta"] in (2.0**-14, 2.0**-12, 2.0**-10)


def test_g11_stage_c_steps_and_ends_typed_within_the_budget() -> None:
    """G11: stage C makes at least one accepted iteration (an f- or θ-type step) and ends with a
    typed outcome within `M05-budget-v1`."""
    document = record()
    runs = [run for run in document["runs"] if run["stage"] == "C"]
    assert runs
    accepted = sum(
        1 for run in runs for item in run["iterations"] if item["type"] in ("f", "theta")
    )
    assert accepted >= 1
    for run in runs:
        assert TYPED_OUTCOME.fullmatch(run["outcome"]), run["outcome"]
        assert run["cold"] <= RUN_COLD
        assert max(item["k"] for item in run["iterations"]) <= RUN_ITERATIONS
    assert STUDY_STATUSES.fullmatch(document["status"])
    budgets = document["accounting"]["budgets"]
    assert (budgets["study_cold"], budgets["study_wall_s"]) == (STUDY_COLD, STUDY_WALL_S)
    assert budgets["cold_used"] <= STUDY_COLD


def test_g11_g7_holds_on_the_run() -> None:
    """G11 asks G7 on the run: the store bijection; every holder's cold + store + memo requests
    equal its requests; no non-finite output served; cold requests within the caps."""
    document = record()
    ledger = _read(".ledger.json")
    couplings = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in STEM.with_suffix(".coupling").glob("*.json")
    }
    store = _read(".store.json")
    assert store
    assert replay.store_bijection_violations(store, ledger, couplings) == []
    assert replay.persisted_violations(document, STEM.with_suffix(".coupling")) == []
    for run in document["runs"]:
        for summary in run["ledger"]["summary"].values():
            served = sum(
                summary[f"{call}_{how}"]
                for call in ("value", "jacobian")
                for how in ("cold", "store_hit", "memo_hit")
            )
            assert served == summary["requests"]
    refused = [e for b in ledger for e in b["requests"] if e["status"] != "ok"]
    summaries = [s for run in document["runs"] for s in run["ledger"]["summary"].values()]
    assert len(refused) == sum(s["refused"] for s in summaries)  # each refusal is the run's


def test_g11_every_candidate_has_a_status() -> None:
    """G11: every candidate has one of §7.4's statuses (the first failing check, or none)."""
    for candidate in record()["candidates"]:
        assert candidate["status"] in CANDIDATE_STATUSES, candidate["candidate_id"]


def test_g11_the_limitations_include_extrapolated_with_its_count_and_fd_gradient() -> None:
    """G11: `extrapolated` and `fd_gradient` are stated. §7.1 counts `extrapolated` per
    evaluation: the count is the truth holder's ledger requests whose experiment left the
    kinetics' data domain (build log S69); the record states the limitation, the ledger artifact
    (its sha256 `artifacts.ledger`) carries the count."""
    document = record()
    assert {"extrapolated", "fd_gradient"} <= set(document["limitations"])
    ledger = _read(".ledger.json")
    truth = [e for b in ledger if b["holder"].startswith("link:") for e in b["requests"]]
    extrapolated = [e for e in truth if e["extrapolated"]]
    assert (len(extrapolated), len(truth)) == (EXTRAPOLATED, TRUTH_REQUESTS)
    assert all("extrapolated" in c["limitations"] for c in document["candidates"])


def test_r433_the_extrapolated_wording_is_the_ledger_count_and_the_recorded_flip() -> None:
    """R-433 (§21.4): the wording's count is the ledger's (the test above ties `EXTRAPOLATED` and
    `TRUTH_REQUESTS` to the ledger artifact), and the flip it states is the record's: cand-C1's P1
    solve carries `extrapolated`, its minus poll 3.5e-5 K below at exactly 653.15 K does not."""
    count = f"{EXTRAPOLATED} of {TRUTH_REQUESTS} reactor requests, reported, not a distance"
    assert EXTRAPOLATED_LIMITATION.startswith(f"extrapolated: {count} from the data.")
    document = record()
    (candidate,) = [c for c in document["candidates"] if c["candidate_id"] == "cand-C1"]
    solves = {solve["check_id"]: solve for solve in candidate["solves"]}
    p1 = solves["cand-C1-P1"]
    minus = solves["cand-C1-poll-preheater.T_spec-minus"]
    assert (p1["limitations"], minus["limitations"]) == (["extrapolated"], [])
    (t_p1,) = p1["decisions"].values()
    assert minus["decisions"] == {"preheater.T_spec": 653.15}
    assert f"{t_p1 - 653.15:.1e}" == "3.5e-05" and "3.5e-5 K apart" in EXTRAPOLATED_LIMITATION


# -- S6R-20 (R-1008, `docs/reviews/REL040-s6-ruling.md` §8 WO-2): the re-take's refusals ---------


def _refused(argv: list[str], monkeypatch: pytest.MonkeyPatch, capsys: Any) -> str:
    """`m05_wo9_real.main(argv)`'s exit-2 reason; without OMP_NUM_THREADS=1 no run can start."""
    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    import m05_wo9_real  # noqa: PLC0415

    with pytest.raises(SystemExit) as raised:
        m05_wo9_real.main(argv)
    assert raised.value.code == 2
    return capsys.readouterr().err


def test_s6r20_a_retake_inside_the_repository_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    reason = _refused(["--retake-into", str(REPO_ROOT / ".cache" / "retake")], monkeypatch, capsys)
    assert "lies inside the repository" in reason


def test_s6r20_a_retake_over_an_existing_record_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    (tmp_path / "trust-region-study-real.json").write_text("{}", encoding="utf-8")
    reason = _refused(["--retake-into", str(tmp_path)], monkeypatch, capsys)
    assert "trust-region-study-real.json exists: a re-take never overwrites one" in reason


def test_s6r20_a_retake_with_replay_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    reason = _refused(["--retake-into", str(tmp_path), "--replay"], monkeypatch, capsys)
    assert "--retake-into and --replay exclude each other" in reason


# -- S6R-28 (R-1008, ruling §11.3 WO-7 (b)): a re-take keeps the non-empty child logs -------------


def _stubbed_retake(
    tmp_path: Path,
    logs: dict[str, bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    raises: Exception | None = None,
) -> tuple[Path, str]:
    """`main(["--retake-into", <dir>])` with the run stubbed: it leaves a synthetic store with one
    attempt whose `child.<name>` logs hold `logs`, and writes nothing; with `raises`, the run then
    raises it, and so does `main`. Returns (dir, stdout)."""
    monkeypatch.syspath_prepend(str(REPO_ROOT / "scripts"))
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    import m05_wo9_real  # noqa: PLC0415

    key = "ab" + "c" * 62

    def run_real(root: Path, *, archive: bytes | None = None) -> Any:
        assert archive is None
        attempt = root / "experiments" / key[:2] / key / "attempts"
        (attempt / "1").mkdir(parents=True)
        relpaths = {name: f"experiments/{key[:2]}/{key}/attempts/1/child.{name}" for name in logs}
        for name, content in logs.items():
            (root / relpaths[name]).write_bytes(content)
        document = {"execution": {"logs": {"relpaths": relpaths}}, "experiment_key": key}
        (attempt / "1.json").write_text(json.dumps(document), encoding="utf-8")
        if raises is not None:
            raise raises
        return SimpleNamespace(run=SimpleNamespace(bijection=[]))

    monkeypatch.setattr(m05_wo9_real, "run_real", run_real)
    monkeypatch.setattr(m05_wo9_real, "write", lambda real, *, stem: None)
    monkeypatch.setattr(m05_wo9_real, "summary", lambda real: "REAL (stubbed)")
    into = tmp_path / "retake"
    if raises is None:
        assert m05_wo9_real.main(["--retake-into", str(into)]) == 0
    else:
        with pytest.raises(type(raises)):
            m05_wo9_real.main(["--retake-into", str(into)])
    return into, capsys.readouterr().out


def test_s6r28_only_the_non_empty_log_is_kept_at_its_relpath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    logs = {"stderr": b"warning: a changed code path\n", "stdout": b""}
    into, out = _stubbed_retake(tmp_path, logs, monkeypatch, capsys)
    assert "child-logs kept=1" in out.splitlines()
    kept = sorted(p.relative_to(into).as_posix() for p in into.rglob("*") if p.is_file())
    key = "ab" + "c" * 62
    assert kept == [f"child-logs/experiments/ab/{key}/attempts/1/child.stderr"]
    assert (into / kept[0]).read_bytes() == logs["stderr"]


def test_s6r28_with_every_log_empty_nothing_is_kept_and_no_directory_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    into, out = _stubbed_retake(tmp_path, {"stderr": b"", "stdout": b""}, monkeypatch, capsys)
    assert "child-logs kept=0" in out.splitlines()
    assert not (into / "child-logs").exists()


def test_n5_a_run_that_raises_still_keeps_its_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    # REL040 review N-5: a crashing re-take keeps the logs that explain it. Fails at `5d0c4121`.
    logs = {"stderr": b"Traceback: the child failed\n", "stdout": b""}
    into, out = _stubbed_retake(tmp_path, logs, monkeypatch, capsys, RuntimeError("the run"))
    assert "child-logs kept=1" in out.splitlines()
    key = "ab" + "c" * 62
    kept = into / f"child-logs/experiments/ab/{key}/attempts/1/child.stderr"
    assert kept.read_bytes() == logs["stderr"]
