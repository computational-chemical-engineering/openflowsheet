"""T07 ruling round 6, B1 (R6-W2): the reason reaches the agent — gate G-R6-4, the V17 replays.

Design note `docs/design/T07-jobs-and-bindings.md`, "Ruling round 6", B1 item 4 and the gate table.
In-process, on the V17-T02 task's fixture project as `benchmarks/t07/v17/fixtures.build` seeds it,
through the contract (`LocalApplication`, inline executor), with the `v17-c1` agents' own
documents (`t07_v17_c1_documents`: the T02-2 and T02-3 documents are replayed schema-conformant;
as committed they fail `SCHEMA-01`, ruling round 5 S3, before any structural stage).

- **T02-2 `rev-000002`**: `DRAFT`, STR-01…05 `NOT_RUN` naming `specification_missing(S4.P)` and
  `path: state.P`; `submit_job` refused `revision_not_ready` and no job runs; `inspect_structure`
  gives `not_run_reason` and a non-null `hint`.
- **T02-3 `rev-000003`**: `DRAFT`, `port_phase_unsupported(U-HEAT.outlet)`, the hint naming the
  accepted phase.
- **T02-1 `rev-000002`**: unchanged, `CONVERGED`/`VERIFIED` on `revision_eo`.
- **T02-2 with its `S4.T` pin replaced by the hint's instance form** (U-FLASH `outlet.T` 358 K,
  `outlet.P` 100000 Pa): READY → `revision_eo` → `CONVERGED`/`VERIFIED`, the recycle flows within
  T02 §6.4's allowance (3.1e-7 mol/s) of T02-1's.
- **An A02 legacy solve forced into `RunUnsupportedError`**: `detail.solve_path == "legacy_eo"`
  and `detail.route_reason` equal to the `route_reason` of a completed run's `solve-path.json`.
"""

from __future__ import annotations

import copy
import math
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS
from t07_jobs_support import commit
from t07_v17_c1_documents import c1_document, schema_conformant

import openflowsheet.application.jobs.runner as runner_module
from benchmarks.t07.v17 import fixtures
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.revision_run import NoRoute, RunUnsupportedError, select_route
from openflowsheet.application.types import Change, JobRequest
from openflowsheet.canonical import load_document

STRUCTURAL = ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
#: T02 §6.4: the registered EO-versus-tear agreement for flows, ten times the residual tolerance.
FLOW_ALLOWANCE = 3.1e-7
Document = dict[str, Any]


@pytest.fixture(scope="module")
def t02(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LocalApplication]:
    root = tmp_path_factory.mktemp("g-r6-4")
    fixtures.build("V17-T02", root / "project", root / "secret" / "token")
    with LocalApplication.open(root / "project") as application:
        yield application


def _commit(application: LocalApplication, document: Document) -> str:
    """The agent's document committed on the fixture's head, as the agent committed it."""
    with application.store.reading() as connection:
        head = application.store.head(connection)
        current = application.store.get_revision(connection, head) if head else None
    document = copy.deepcopy(document)
    document["parent_revision"] = head
    result = application.commit_change(
        Change(
            edits=fixtures.edits_to(None if current is None else current.document, document),
            new_revision_id=f"{document['revision_id']}-{time.monotonic_ns()}",
        ),
        head,
        f"g-r6-4-{time.monotonic_ns()}",
    )
    assert result.status == "committed", result
    assert result.revision_id is not None
    return result.revision_id


def _solve(application: LocalApplication, revision_id: str) -> Any:
    submitted = application.submit_job(
        JobRequest.from_document(
            {
                "operation": "solve",
                "idempotency_key": f"g-r6-4-{time.monotonic_ns()}",
                "body": {"revision_id": revision_id, "policy_id": "default"},
            }
        )
    )
    return application.wait_job(submitted.job.job_id, timeout_s=math.inf).job


def _state(application: LocalApplication, job: Any) -> dict[str, Any]:
    (bundle,) = [ref for ref in job.outputs if ref.kind == "replay_bundle"]
    member = f"{bundle.artifact_id}/solution-state.json"
    variables: dict[str, Any] = load_document(
        application.artifact_bytes(member).decode("utf-8"), source=member
    )["variables"]
    return variables


def _jobs(application: LocalApplication) -> int:
    return len(application.list_jobs(limit=200).items)


def test_t02_2_is_draft_names_the_missing_pin_and_is_not_solved(
    t02: LocalApplication,
) -> None:
    revision = _commit(t02, schema_conformant(c1_document("T02-2", "rev-000002")))
    report = t02.validate(revision, "simulation")
    assert report.status == "DRAFT"
    checks = {check.id: check for check in report.checks}
    for check_id in STRUCTURAL:
        assert checks[check_id].result == "NOT_RUN"
        assert "specification_missing(S4.P)" in checks[check_id].message
        assert "path: state.P" in checks[check_id].message
    before = _jobs(t02)
    with pytest.raises(ApplicationError) as refused:
        t02.submit_job(
            JobRequest.from_document(
                {
                    "operation": "solve",
                    "idempotency_key": "g-r6-4-t02-2",
                    "body": {"revision_id": revision, "policy_id": "default"},
                }
            )
        )
    assert refused.value.code == "revision_not_ready"
    assert _jobs(t02) == before
    structure = t02.inspect_structure(revision).value
    # ADR 0019 Amendment 3 (A3.1) adds three members, by addition only (M06 WO-1).
    assert set(structure) == {
        "not_run_reason",
        "hint",
        "validation_structural_report",
        "rows",
        "columns",
    }
    assert "specification_missing(S4.P)" in structure["not_run_reason"]
    assert structure["hint"] is not None and "path: outlet.P" in structure["hint"]


def test_t02_3_rev3_names_the_accepted_phase(t02: LocalApplication) -> None:
    revision = _commit(t02, schema_conformant(c1_document("T02-3", "rev-000003")))
    report = t02.validate(revision, "simulation")
    assert report.status == "DRAFT"
    assert "port_phase_unsupported(U-HEAT.outlet)" in (report.structural_counts_absent_reason or "")
    structure = t02.inspect_structure(revision).value
    assert structure["hint"] == (
        "Port outlet of syn001.tp_heater takes phase vapor_liquid; the connection declares liquid."
    )


def _instance_form(document: Document) -> Document:
    """T02-2's `rev-000002` with its `S4.T` pin replaced by the hint's instance form: U-FLASH
    `outlet.T` 358 K and `outlet.P` 100000 Pa."""
    repaired = schema_conformant(document)
    (vapor_t,) = [e for e in repaired["specifications"] if e["id"] == "SPEC-flash-vapor-T"]
    repaired["specifications"].remove(vapor_t)
    for path, kind, unit, value in (
        ("outlet.T", "temperature", "K", 358),
        ("outlet.P", "pressure", "Pa", 100000),
    ):
        entry = copy.deepcopy(vapor_t)
        entry.update(
            id=f"SPEC-flash-{path}",
            kind=kind,
            unit=unit,
            value=value,
            target={
                "object_type": "instance",
                "object_id": "U-FLASH",
                "path": path,
                "component": None,
            },
        )
        repaired["specifications"].append(entry)
    return repaired


def test_t02_1_and_t02_2_repaired_by_the_hint_solve_to_one_state(t02: LocalApplication) -> None:
    solved = {}
    for label, document in (
        ("T02-1", c1_document("T02-1", "rev-000002")),
        ("T02-2 repaired", _instance_form(c1_document("T02-2", "rev-000002"))),
    ):
        revision = _commit(t02, document)
        assert t02.validate(revision, "simulation").status == "READY_FOR_SIMULATION", label
        structure = t02.inspect_structure(revision).value
        assert (structure["solve_path"], structure["route_reason"]) == ("revision_eo", None)
        job = _solve(t02, revision)
        assert job.status == "completed", (label, job.error)
        result = t02.get_job_result(job.job_id).run_result
        assert result is not None
        assert (result.solve_path, result.outcome, result.verification_status) == (
            "revision_eo",
            "CONVERGED",
            "VERIFIED",
        ), label
        solved[label] = _state(t02, job)
    recycle = [f"S6.n.{component}" for component in ("A", "B", "C")]
    for variable in recycle:
        assert abs(solved["T02-2 repaired"][variable] - solved["T02-1"][variable]) <= (
            FLOW_ALLOWANCE
        ), variable


def test_a_forced_legacy_end_names_its_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with LocalApplication.create(tmp_path / "a02", project_id="g-r6-4-a02") as application:
        revision = commit(application, CORPUS["SYN-001-A02-360"]())
        completed = _solve(application, revision)
        assert completed.status == "completed"
        (bundle,) = [ref for ref in completed.outputs if ref.kind == "replay_bundle"]
        member = f"{bundle.artifact_id}/solve-path.json"
        recorded: dict[str, Any] = load_document(
            application.artifact_bytes(member).decode("utf-8"), source=member
        )
        assert recorded["solve_path"] == "legacy_eo"

        def unmapped(*arguments: Any, **keywords: Any) -> Any:
            raise RunUnsupportedError("certificate_unmapped(legacy_eo,evaluate,converge)")

        monkeypatch.setattr(runner_module, "run_revision_session", unmapped)
        failed = _solve(application, revision)
    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.code == "unsupported"
    assert failed.error.detail == {
        "reason": "certificate_unmapped(legacy_eo,evaluate,converge)",
        "solve_path": "legacy_eo",
        "route_reason": recorded["route_reason"],
    }
    assert recorded["route_reason"] == (
        "unsupported(specification_role_unsupported(GUESS-heater-outlet-T))"
    )


def test_a_job_that_finds_no_route_carries_the_revision_binders_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The job's own `revision_unsupported` (its `resolve` stage re-selects the route) adds
    `detail.hint` beside `detail.unbound` (ruling round 6, B1 item 4). Unreachable after `READY`
    on the corpus (G9 (d)), so the job's route is replaced."""
    none = select_route(schema_conformant(c1_document("T02-2", "rev-000002")))
    assert isinstance(none, NoRoute)
    with LocalApplication.create(tmp_path / "p", project_id="g-r6-4-noroute") as application:
        revision = commit(application, CORPUS["SYN-001-nominal"]())
        monkeypatch.setattr(runner_module, "select_route", lambda document: none)
        failed = _solve(application, revision)
    assert failed.status == "failed"
    assert failed.error is not None and failed.error.code == "revision_unsupported"
    assert failed.error.detail == {"unbound": none.reason, "hint": none.hint}
    assert none.hint is not None and "path: state.P" in none.hint
