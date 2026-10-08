"""M02 WO-4, gate G4 (design note §3.2-§3.4, §5; ADR 0033 D4-D7, D11): experiment records, the
exact cache, retry, bypass, and one execution per key — on the stand-in (in process) and the
synthetic child (out of process, `tests/support/synthetic_child.py`).

- (a) The same request twice: one execution, one cache hit; `result.json` byte-identical; the
  hit is a row of the consuming job whose parent is the producing row.
- (b) T_in + 1 ulp is another key and executes again; (c) (2n, 2 N_tubes) is another key.
- (d) `crashed`, retried once, `crashed`: two attempts, no result; the same request executes
  again (a transient outcome is never cached).
- (e) A perturbation with defect_rel 2 × 10⁻⁶ → `not_converged`, `element_balance_defect`, no
  outlet values, deterministic: the repeat is a hit.
- (f) y_NH3 = 10⁻¹⁰ → a result whose attempt is `not_executed`, `nh3_below_trace`.
- (g) A reported ΔP of 20 000 Pa at 10⁷ Pa → `pressure_drop_exceeds_convention`, retained.
- (h) Bypass: `repeat_bitwise_equal: true`; the `nondeterministic` child: one determinism finding,
  the result's envelope unchanged.
- (i) Two processes on one key: exactly one `completed` attempt in all, the other a hit (the job
  level, `max_workers = 2`, is WO-6's).

Besides: no retry after `timed_out`; `environment_changed` ends the attempt; a failed handshake
is an `environment_*` attempt keyed on the unmeasured fingerprint; a cancel during the evaluation
leaves a `cancelled` attempt and propagates; every record validates; the in-process envelope is
`ReactorStandin.evaluate`'s, and the child's outlet equals it bitwise; a variant whose boundary
block is not the implemented one is refused.
"""

from __future__ import annotations

import json
import math
import multiprocessing
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.adapters import variants
from openflowsheet.adapters.experiments.runner import ExperimentOutcome, ExperimentRunner
from openflowsheet.adapters.experiments.store import ExperimentStore
from openflowsheet.application.jobs.interrupt import JobInterrupted, interruptible
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.store import ProjectStore
from openflowsheet.application.types import schema_errors
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.models.c1.reactor_standin import ReactorStandin
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from m02_schema_fixtures import (  # noqa: E402
    N_TUBES,
    nominal_inlet,
    synthetic_backend,
    synthetic_variant,
)

CONTEXT = EvaluationContext(model_version="m02-experiments", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
STANDIN = variants.registered_variant("standin-x025-v1")
SCHEMA = "experiment.schema.json#/$defs/"


@dataclass
class Project:
    root: Path
    store: ProjectStore

    def runner(self, job_id: str | None = None) -> ExperimentRunner:
        return ExperimentRunner(
            ExperimentStore(self.root, self.store),
            PROVIDER,
            CONTEXT,
            job_id=job_id,
            backend_for=synthetic_backend(self.root / "env"),
        )

    def records(self) -> ExperimentStore:
        return ExperimentStore(self.root, self.store)

    def rows(self, key: str) -> list[tuple[Any, ...]]:
        with self.store.reading() as connection:
            return list(
                connection.execute(
                    "SELECT artifact_id, job_id, kind, parent_artifact_id FROM artifacts"
                    " WHERE name = ? ORDER BY rowid",
                    (key,),
                )
            )


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Project]:
    with LocalApplication.create(tmp_path / "p") as application:
        assert application.store.directory is not None
        yield Project(application.store.directory, application.store)


def _variant(name: str, **evaluation: Any) -> variants.Variant:
    document = json.loads(json.dumps(STANDIN.document))
    document["variant_id"] = f"test-standin-{name}"
    document["evaluation"].update(evaluation)
    return variants.variant_from_document(document)


def _run(runner: ExperimentRunner, variant: variants.Variant, **kwargs: Any) -> ExperimentOutcome:
    inlet = kwargs.pop("inlet", nominal_inlet())
    n_tubes = kwargs.pop("n_tubes", N_TUBES)
    return runner.run(variant, inlet, COMPONENTS, n_tubes, **kwargs)


def _valid(outcome: ExperimentOutcome) -> None:
    assert schema_errors(SCHEMA + "request", outcome.request) == []
    if outcome.result is not None:
        assert schema_errors(SCHEMA + "result", outcome.result) == []
    for attempt in outcome.attempts:
        assert schema_errors(SCHEMA + "attempt", attempt) == [], attempt


def _statuses(outcome: ExperimentOutcome) -> list[str]:
    return [attempt["execution"]["status"] for attempt in outcome.attempts]


# -- the in-process path is M01's stand-in -------------------------------------------------------


def test_the_standin_result_is_m01s_envelope_and_the_childs_outlet_is_bitwise_equal(
    project: Project,
) -> None:
    runner = project.runner("job-000001")
    inside = _run(runner, STANDIN)
    _valid(inside)
    expected = ReactorStandin("x", PROVIDER, CONTEXT, n_tubes=N_TUBES).evaluate(nominal_inlet())
    assert inside.result is not None and inside.result["envelope"] == expected.as_document()
    assert inside.result["provider_calls"] == 3  # the inlet flash and the two enthalpy flows
    assert inside.result["accuracy"] == dict(STANDIN.accuracy)
    assert inside.result["provenance"]["reactor"] is None
    outside = _run(runner, synthetic_variant("ok", ["ok"]))
    _valid(outside)
    assert outside.result is not None
    for name in ("outlet", "xi", "Q", "defect", "defect_rel"):
        assert outside.result["envelope"][name] == inside.result["envelope"][name], name
    assert outside.result["envelope"]["identity"]["synthetic"] is True
    assert outside.attempts[0]["execution"]["kind"] == "out_of_process"


# -- (a)-(c): the exact cache and its key ---------------------------------------------------------


def test_g4a_the_same_request_twice_is_one_execution_and_one_hit(project: Project) -> None:
    first = _run(project.runner("job-000001"), STANDIN)
    path = project.records().result_path(first.key)
    before = path.read_bytes()
    second = _run(project.runner("job-000002"), STANDIN)
    assert (first.cache_hit, second.cache_hit) == (False, True)
    assert second.key == first.key and second.attempts == ()
    assert second.result == first.result and path.read_bytes() == before
    assert len(project.records().attempts(first.key)) == 1
    rows = project.rows(first.key)
    producing = [row for row in rows if row[2] == "experiment_result" and row[3] is None]
    (hit,) = [row for row in rows if row[3] is not None]
    assert len(producing) == 1 and producing[0][1] == "job-000001"
    assert hit[1:] == ("job-000002", "experiment_result", producing[0][0])
    kinds = sorted(row[2] for row in rows if row[1] == "job-000001")
    assert kinds == ["experiment_attempt", "experiment_request", "experiment_result"]


def test_g4b_one_ulp_in_t_in_is_another_experiment(project: Project) -> None:
    runner = project.runner()
    first = _run(runner, STANDIN)
    inlet = nominal_inlet()
    nudged = StreamState(
        n=inlet.n, temperature=math.nextafter(inlet.temperature, math.inf), pressure=inlet.pressure
    )
    second = _run(runner, STANDIN, inlet=nudged)
    assert second.key != first.key and not second.cache_hit
    assert len(project.records().attempts(second.key)) == 1


def test_g4c_twice_the_flow_over_twice_the_tubes_is_another_experiment(project: Project) -> None:
    runner = project.runner()
    first = _run(runner, STANDIN)
    inlet = nominal_inlet()
    doubled = StreamState(
        n=tuple(2.0 * value for value in inlet.n),
        temperature=inlet.temperature,
        pressure=inlet.pressure,
    )
    second = _run(runner, STANDIN, inlet=doubled, n_tubes=2.0 * N_TUBES)
    assert second.key != first.key and not second.cache_hit
    # The tube saw the same inlet: the documented cost of a process-level identity (§3.2).
    assert (
        second.attempts[0]["execution"]["tube_inlet"]
        == first.attempts[0]["execution"]["tube_inlet"]
    )


# -- (d): retry, and a transient outcome is never cached ------------------------------------------


def test_g4d_a_crash_is_retried_once_and_never_cached(project: Project) -> None:
    variant = synthetic_variant("abort", ["abort"])
    first = _run(project.runner(), variant)
    _valid(first)
    assert first.transient and _statuses(first) == ["crashed", "crashed"]
    assert [a["execution"]["signal"] for a in first.attempts] == [6, 6]
    assert (first.envelope["status"], first.envelope["code"]) == ("error", "external_crashed")
    assert first.envelope["outlet"] is None
    assert project.records().result(first.key) is None
    third = _run(project.runner(), variant)
    assert third.key == first.key and not third.cache_hit
    assert [a["attempt"] for a in third.attempts] == [3, 4]


def test_a_timeout_is_not_retried(project: Project) -> None:
    variant = synthetic_variant("slow", ["sleep(60)"], timeout_s=1.0)
    outcome = _run(project.runner(), variant)
    _valid(outcome)
    assert _statuses(outcome) == ["timed_out"]
    assert outcome.envelope["code"] == "external_timed_out" and outcome.transient


def test_a_changed_fingerprint_ends_the_attempt_environment_changed(project: Project) -> None:
    outcome = _run(project.runner(), synthetic_variant("alt", ["fingerprint(alt)"]))
    _valid(outcome)
    assert _statuses(outcome) == ["environment_changed"]
    assert outcome.envelope["code"] == "external_environment_changed" and outcome.transient
    assert "python" in outcome.attempts[0]["execution"]["message"]


def test_a_failed_handshake_is_an_attempt_keyed_on_the_unmeasured_fingerprint(
    project: Project,
) -> None:
    variant = synthetic_variant("ok", ["ok"])
    runner = ExperimentRunner(project.records(), PROVIDER, CONTEXT)  # the pinned environment
    outcome = _run(runner, variant)
    _valid(outcome)
    assert _statuses(outcome) == ["environment_unavailable"]
    assert "pymrm.env build" in outcome.attempts[0]["execution"]["message"]
    from openflowsheet.adapters.experiments.backends import unmeasured_fingerprint
    from openflowsheet.canonical import document_sha256

    unmeasured = document_sha256(unmeasured_fingerprint(variant, "environment_unavailable"))
    assert outcome.request["environment_fingerprint_sha256"] == unmeasured


def test_a_cancel_during_the_evaluation_leaves_a_cancelled_attempt(project: Project) -> None:
    variant = synthetic_variant("sleepy", ["sleep(60)"])
    runner = project.runner()
    cancel = threading.Event()
    threading.Timer(1.5, cancel.set).start()
    with interruptible(cancel, None), pytest.raises(JobInterrupted):
        _run(runner, variant)
    request = runner.records.read(next(runner.records.base.glob("*/*/request.json")))
    assert request is not None
    (attempt,) = runner.records.attempts(request["experiment_key"])
    assert schema_errors(SCHEMA + "attempt", attempt) == []
    assert attempt["execution"]["status"] == "cancelled"
    assert attempt["execution"]["signal"] == 15 and attempt["execution"]["tube_outlet"] is None
    assert runner.records.result(request["experiment_key"]) is None


# -- (e)-(g): deterministic refusals are results --------------------------------------------------


def test_g4e_an_element_defect_is_a_deterministic_refusal(project: Project) -> None:
    inlet = nominal_inlet()
    delta = 2.0e-6 * inlet.total_flow / N_TUBES  # on Ar, which the projection never moves
    variant = _variant("defect", perturbation_mol_s=[0.0, 0.0, 0.0, delta, 0.0])
    first = _run(project.runner(), variant)
    _valid(first)
    assert first.result is not None
    envelope = first.result["envelope"]
    assert (envelope["status"], envelope["code"]) == ("not_converged", "element_balance_defect")
    assert all(envelope[name] is None for name in ("outlet", "xi", "Q", "defect", "defect_rel"))
    repeat = _run(project.runner(), variant)
    assert repeat.cache_hit and repeat.result == first.result


def test_g4f_a_trace_inlet_is_refused_before_the_evaluation(project: Project) -> None:
    inlet = nominal_inlet()
    n = list(inlet.n)
    n[2] = 1.0e-10 * inlet.total_flow
    trace = StreamState(n=tuple(n), temperature=inlet.temperature, pressure=inlet.pressure)
    outcome = _run(project.runner(), STANDIN, inlet=trace)
    _valid(outcome)
    assert outcome.result is not None and outcome.result["envelope"]["code"] == "nh3_below_trace"
    (attempt,) = outcome.attempts
    assert attempt["execution"]["status"] == "not_executed"
    assert attempt["execution"]["tube_inlet"] is None


def test_g4g_a_pressure_drop_above_the_convention_is_retained(project: Project) -> None:
    outcome = _run(project.runner(), _variant("dp", pressure_drop_Pa=20000.0))
    _valid(outcome)
    assert outcome.result is not None
    assert outcome.result["envelope"]["code"] == "pressure_drop_exceeds_convention"
    assert outcome.attempts[0]["execution"]["status"] == "completed"


# -- (h): bypass, the determinism monitor ---------------------------------------------------------


def test_g4h_a_bypassed_repeat_is_compared_bitwise(project: Project) -> None:
    variant = synthetic_variant("ok", ["ok"])
    first = _run(project.runner(), variant)
    before = project.records().result_path(first.key).read_bytes()
    repeat = _run(project.runner(), variant, cache="bypass")
    _valid(repeat)
    (attempt,) = repeat.attempts
    assert (attempt["repeat_of"], attempt["repeat_bitwise_equal"]) == (1, True)
    assert project.records().result_path(first.key).read_bytes() == before


def test_g4h_a_nondeterministic_repeat_is_a_finding_and_the_result_stands(
    project: Project,
) -> None:
    variant = synthetic_variant("drift", ["nondeterministic"])
    first = _run(project.runner(), variant)
    assert first.result is not None
    repeat = _run(project.runner(), variant, cache="bypass")
    (attempt,) = repeat.attempts
    assert (attempt["repeat_of"], attempt["repeat_bitwise_equal"]) == (1, False)
    assert repeat.result is not None
    assert repeat.result["determinism_findings"] == [
        {"attempt": 2, "differing_fields": ["tube_outlet"]}
    ]
    assert repeat.result["envelope"] == first.result["envelope"]
    assert schema_errors(SCHEMA + "result", repeat.result) == []


# -- (i): one execution per key -------------------------------------------------------------------


def _contend(root: str, barrier: Any, queue: Any) -> None:
    store = ProjectStore.open(Path(root))
    try:
        project = Project(Path(root), store)
        barrier.wait()
        outcome = _run(project.runner(), synthetic_variant("one-second", ["sleep(1)"]))
        queue.put((outcome.cache_hit, len(outcome.attempts)))
    finally:
        store.close()


def test_g4i_two_processes_on_one_key_execute_it_once(project: Project) -> None:
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    workers = [
        context.Process(target=_contend, args=(str(project.root), barrier, queue)) for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(60)
        assert worker.exitcode == 0
    answers = sorted(queue.get(timeout=5) for _ in workers)
    assert answers == [(False, 1), (True, 0)]
    (directory,) = project.records().base.glob("*/*/request.json")
    attempts = project.records().attempts(directory.parent.name)
    assert [attempt["execution"]["status"] for attempt in attempts] == ["completed"]


# -- the implemented boundary ---------------------------------------------------------------------


def test_a_variant_with_another_boundary_is_refused(project: Project) -> None:
    document = json.loads(json.dumps(STANDIN.document))
    document["variant_id"] = "test-standin-outlet-specified"
    document["boundary"]["pressure_convention"] = "outlet_specified"
    variant = variants.variant_from_document(document)
    with pytest.raises(ValueError, match="pressure_convention"):
        _run(project.runner(), variant)


def test_a_crashing_handshake_is_retried_as_a_handshake(project: Project) -> None:
    outcome = _run(project.runner(), synthetic_variant("bad-env", ["handshake:abort"]))
    _valid(outcome)
    assert _statuses(outcome) == ["crashed", "crashed"]
    assert all(a["execution"]["tube_inlet"] is None for a in outcome.attempts)
    handshakes = sorted((project.records().base / "handshakes").glob("*/*"))
    assert len(handshakes) == 2 and outcome.transient


def test_a_handshake_measured_on_its_retry_is_the_one_the_key_carries(project: Project) -> None:
    """A crashed handshake is retried before the key exists: the request is keyed on the
    fingerprint the retry measured, never on the unmeasured one, and the crash is attempt 1."""
    from openflowsheet.adapters.experiments.backends import unmeasured_fingerprint
    from openflowsheet.canonical import document_sha256

    variant = synthetic_variant("flaky-env", ["handshake:abort_first"])
    runner = project.runner()
    outcome = _run(runner, variant)
    _valid(outcome)
    assert _statuses(outcome) == ["crashed", "completed"]
    assert outcome.result is not None and outcome.result["produced_by"]["attempt"] == 2
    measured = runner.backend(variant).environment(project.root / "unused")
    assert measured.fingerprint is not None
    assert outcome.request["environment_fingerprint_sha256"] == measured.sha256
    unmeasured = document_sha256(unmeasured_fingerprint(variant, "crashed"))
    assert measured.sha256 != unmeasured
    logs = outcome.attempts[0]["execution"]["logs"]["relpaths"]["stderr"]
    assert logs.startswith("experiments/handshakes/") and (project.root / logs).is_file()
