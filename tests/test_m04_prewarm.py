"""M04.A40 (WO-17): a concurrently pre-warmed study is bitwise the sequential one (spec §18 A1.6).

ADR 0037 Amendment 1 D8, R-294: `surrogate_study` stays sequential; many cold experiments are run
concurrently only by pre-warming the cache (`scripts/m04_prewarm.py`), and then the study runs
fully cached. No bit may change: each record is a deterministic function of its exact key, and the
study reads records in plan order whatever order they were written in. Concurrency is telemetry —
in the pre-warm's report, never in the SurrogateManifest or the ModelEvidence.

A40 asks for the smooth prefix plan's 199 requests as `experiment` jobs under the process executor
at `max_workers = 4`, and for A19's records bitwise. The synthetic parents are reachable from no
request (they are not registered; M02's rule for test variants), so A40 is checked in two halves
(a build-lane decision, reported to the design lane):

- **the script's path**, with the registered stand-in: `prewarm` submits the prefix plan's 199
  misses as `experiment` jobs under `ProcessExecutor` at `max_workers = 4`, then the study runs
  with `max_cold_experiments = 0` (cold 0, hits 199) and its manifest and evidence are bitwise the
  sequential study's (A16's), every result record too except `produced_by.job_id`, which names
  the job that wrote it;
- **A19 bitwise**, with the smooth parent: its 199 requests run by four spawned processes, each its
  own runner on the shared store; the study then gives cold 0, hits 199 and A19's manifest and
  evidence bitwise, and every result record is bitwise the sequential run's (no job ids).

The budget refusal happens before anything is submitted, with the study's own rule.
"""

from __future__ import annotations

import json
import multiprocessing
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.store import ExperimentStore
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.canonical import canonical_json
from openflowsheet.studies.surrogate import plan as sp
from openflowsheet.studies.surrogate.study import run_study

sys.path.insert(0, str(REPO_ROOT / "tests" / "support"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m04_prewarm  # noqa: E402
import m04_prewarm_support as support  # noqa: E402
import m04_synthetic_parents as parents  # noqa: E402

STANDIN = variants.registered_variant("standin-x025-v1")
WORKERS = 4


def _result_bytes(root: Path, keys: list[str]) -> dict[str, bytes]:
    store = ExperimentStore(root)
    return {key: store.result_path(key).read_bytes() for key in keys}


def _without_job(record: bytes) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(record)
    document["produced_by"] = {**document["produced_by"], "job_id": "MASKED"}
    return document


def test_a40_the_smooth_prefix_prewarmed_by_four_processes_is_a19_bitwise(tmp_path: Path) -> None:
    variant = parents.synthetic_variant(parents.SMOOTH_ID)
    sequential = run_study(support.runner(tmp_path / "sequential"), variant, "it1-prefix", 1000)
    assert sequential.verdict == "PROMOTABLE" and sequential.cold_experiments == 199  # A19

    plan = sp.registered_plan("it1-prefix", synthetic_parent=True)
    requests = [(*state.n, state.temperature, state.pressure) for _, state in plan.requests()]
    root = tmp_path / "concurrent"
    chunks = [(str(root), parents.SMOOTH_ID, requests[w::WORKERS]) for w in range(WORKERS)]
    with multiprocessing.get_context("spawn").Pool(WORKERS) as pool:
        written = pool.starmap(support.run_chunk, chunks)
    assert sum(len(keys) for keys in written) == 199

    cached = run_study(support.runner(root), variant, "it1-prefix", 0)
    assert (cached.cold_experiments, cached.cache_hits, cached.cache_misses) == (0, 199, 0)
    assert cached.manifest is not None and sequential.manifest is not None
    assert canonical_json(cached.manifest) == canonical_json(sequential.manifest)
    assert canonical_json(cached.evidence) == canonical_json(sequential.evidence)
    keys = [key for split in sp.SPLITS for key in sequential.manifest["splits"][split]["keys"]]
    assert sorted(keys) == sorted(key for chunk in written for key in chunk)
    assert _result_bytes(root, keys) == _result_bytes(tmp_path / "sequential", keys)


def _study(app: LocalApplication, key: str, budget: int) -> dict[str, Any]:
    body = {
        "parent": {
            "model_id": STANDIN.model_id,
            "variant_id": STANDIN.variant_id,
            "variant_sha256": STANDIN.sha256,
        },
        "plan_id": "it1-prefix",
        "budget": {"max_cold_experiments": budget},
    }
    request = {"operation": "surrogate_study", "idempotency_key": key, "body": body}
    job = dispatch(app, "submit_job", request)["job"]
    study: dict[str, Any] = dispatch(app, "get_job_result", {"job_id": job["job_id"]})[
        "surrogate_study"
    ]
    return study


def test_a40_the_prewarm_script_under_the_process_executor_changes_no_bit(tmp_path: Path) -> None:
    sequential_dir = tmp_path / "sequential"
    app = LocalApplication.create(sequential_dir)
    try:
        sequential = _study(app, "sequential", 1000)
        manifest_row = app.store.artifacts_of_kind("surrogate_manifest")[0]
        manifest = json.loads((app.files_root / manifest_row.relpath).read_bytes())
        sequential_root = app.files_root
    finally:
        app.close()
    # The stand-in's scores are roundoff (its verdict is not asserted, spec §9.2): every decision
    # is near threshold, so bitwise equality here is the most fragile comparison there is.
    assert sequential["cold_experiments"] == 199

    directory = tmp_path / "prewarmed"
    LocalApplication.create(directory).close()
    report = m04_prewarm.prewarm(
        directory, STANDIN, "it1-prefix", max_workers=WORKERS, budget=199, study=True, repeats=2
    )
    document = report.as_document()
    assert document["refused"] is None
    assert document["executor"] == {"kind": "process", "max_workers": WORKERS}
    assert (document["requests"], document["cache_misses_before"]) == (199, 199)
    assert document["rounds"] == [{"round": 0, "submitted": 199, "without_result": 0}]
    assert (document["retries"], document["incomplete"]) == ([], [])
    # A41's mechanics (opt-in on the real reactor): serial bypass repeats reproduce the
    # concurrently written records bitwise.
    assert [(r["label"], r["repeat_of"], r["repeat_bitwise_equal"]) for r in report.repeats] == [
        ("test[0]", 1, True),
        ("test[1]", 1, True),
    ]
    assert report.study is not None
    cached = report.study["answer"]
    assert (cached["cold_experiments"], cached["cache_hits"], cached["cache_misses"]) == (0, 199, 0)
    # The manifest and the evidence are bitwise the sequential study's.
    assert (cached["manifest_sha256"], cached["evidence_sha256"]) == (
        sequential["manifest_sha256"],
        sequential["evidence_sha256"],
    )
    assert (cached["verdict"], cached["insufficient"], cached["not_promotable"]) == (
        sequential["verdict"],
        sequential["insufficient"],
        sequential["not_promotable"],
    )
    # The policy's executor settings are restored; concurrency is in the report only.
    app = LocalApplication.open(directory)
    try:
        assert app.store.policy_path is not None
        policy = json.loads(app.store.policy_path.read_bytes())
        assert policy["executor"]["max_workers"] == 1
        jobs = [app.store.get_job(job_id) for job_id in app.store.job_ids()]
        operations = [job.operation for job in jobs if job is not None]
        assert (operations.count("experiment"), operations.count("surrogate_study")) == (201, 1)
        assert {job.status for job in jobs if job is not None} == {"completed"}
        prewarmed_root = app.files_root
    finally:
        app.close()
    assert b"max_workers" not in canonical_json(manifest)
    keys = [key for split in sp.SPLITS for key in manifest["splits"][split]["keys"]]
    before, after = _result_bytes(sequential_root, keys), _result_bytes(prewarmed_root, keys)
    assert {k: _without_job(v) for k, v in after.items()} == {
        k: _without_job(v) for k, v in before.items()
    }


def test_a40_the_prewarm_refuses_a_budget_below_the_misses_before_submitting(
    tmp_path: Path,
) -> None:
    LocalApplication.create(tmp_path / "project").close()
    report = m04_prewarm.prewarm(
        tmp_path / "project", STANDIN, "it1-prefix", max_workers=WORKERS, budget=198
    )
    assert report.refused == {
        "verdict": "INSUFFICIENT_EVIDENCE",
        "insufficient": ["budget_below_plan"],
        "cache_misses": 199,
    }
    assert report.rounds == [] and report.study is None
    app = LocalApplication.open(tmp_path / "project")
    try:
        assert dispatch(app, "list_jobs", {})["items"] == []
        assert list(app.files_root.glob("experiments/*/*/*.json")) == []
    finally:
        app.close()


def test_a40_the_prewarm_refuses_what_the_study_would(tmp_path: Path) -> None:
    LocalApplication.create(tmp_path / "project").close()
    with pytest.raises(sp.PlanRefusedError) as refused:
        m04_prewarm.prewarm(tmp_path / "project", STANDIN, "it2", max_workers=WORKERS, budget=2000)
    assert refused.value.code == "iteration_not_permitted"
    with pytest.raises(ValueError, match="physical cores"):
        m04_prewarm.prewarm(
            tmp_path / "project", STANDIN, "it1-prefix", max_workers=10_000, budget=199
        )
