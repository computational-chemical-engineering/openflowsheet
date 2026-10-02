"""Generate T07's round-trip fixtures from real solves and real jobs. Register R-015.

**`solution-state`** (design note ruling round 2, W3e item 1): the `solution-state.json` a
`revision_eo` solve of the SYN-001 revision (`benchmarks/syn001/cases/SYN-001-nominal.yaml`, under
the route's registered policy `T06-revision-v2` and the registered check policy) writes into its
bundle — read back from the bundle, so it is the bytes the code emits, not a document written by
hand. Its values are a converged state's floats, which ADR 0007 measured one to three ulps apart
between the two CI architectures, so "regenerates identically" is `run.compare.differences` empty
(the state digest shape-checked only, the values within ADR 0007 D2's policy) together with exact
`variable_ids` (`tests/test_t07_w3e_solution_state.py`).

**`job` and `job-event`** (design note §15 W4a; ADR 0008 A1 acceptance (a)): three jobs of one
in-process project, run by `LocalApplication` under the inline executor, read back from its store —

- `job-000001`, a solve **cancelled while queued** (0 outputs): submitted from another thread
  while this one holds the compute lock, then cancelled;
- `job-000002`, a **converged solve** of the SYN-001 revision (3 outputs of 3 kinds: the
  certificate, the run manifest, the bundle);
- `job-000003`, a **`reproduce` with `rerun = false`** of job-000002's bundle (1 output, the
  replay report);

and one `job-event` of each producer kind from those streams (`ended` twice: completed and
cancelled). Timestamps, and every output's `sha256` and `size_bytes` (the run manifest carries the
environment and the clock, the certificate floats), differ from one generation to the next, so
"regenerates identically" is equality with those members masked (`stable`); everything else —
ids, kinds, names, stages, endings, request hashes, the project-policy hash — is exact
(`tests/test_t07_adr0008_jobs.py`). `--write` is for when that fails.

**`application-results`** (ruling round 4, W5a-Q2; ADR 0019 Amendment 1): one valid fixture per
`$def`, each the response `dispatch` returns — bounded, as every transport carries it — in one
in-process project holding the SYN-001 revision, a child of it (one specification value changed,
one member removed) and one converged solve: `submit_job`, `list_jobs`, `list_job_events`,
`wait_job`, `get_project`, `list_models`, `list_revisions` (and its first item,
`revision_summary`), `get_revision` at depth 1 and `diff_revisions`. One invalid fixture per
`$def` is that response with its first required member removed, `{expect_error, document}`; and
`model_registry_view` has a second, its first pin without the `specifications` ADR 0019
Amendment 2 requires.
"Regenerates identically" is `stable` equality, as for the jobs
(`tests/test_t07_w5e_application_results.py`).

Usage:
    PYTHONPATH=src:. .venv/bin/python scripts/t07_schema_fixtures.py [--write]
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import yaml  # noqa: E402
from t07_jobs_support import cancel_while_queued, commit, lifecycle_violations  # noqa: E402

from openflowsheet.application.local import LocalApplication  # noqa: E402
from openflowsheet.application.operations import dispatch  # noqa: E402
from openflowsheet.application.policies import resolve_policy  # noqa: E402
from openflowsheet.application.revision_run import (  # noqa: E402
    Route,
    run_revision_session,
    select_route,
)
from openflowsheet.application.types import JobRequest, ReproduceBody, SolveBody  # noqa: E402
from openflowsheet.run.bundle import read_artifact  # noqa: E402
from openflowsheet.run.manifest import THREAD_VARIABLES  # noqa: E402
from openflowsheet.run.solution_state import NAME  # noqa: E402
from openflowsheet.verify.certificate import CheckPolicy  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"
REVISION = ROOT / "benchmarks" / "syn001" / "cases" / "SYN-001-nominal.yaml"
FIXTURE = "solution_state/valid/syn001_nominal_revision_eo.json"
#: The job fixtures, by the outputs each holds (ADR 0008 A1 (a)).
JOB_FIXTURES = {
    0: "job/valid/solve_cancelled_while_queued.json",
    1: "job/valid/reproduce_without_rerun.json",
    3: "job/valid/solve_converged.json",
}
#: The job-event fixtures, one per producer kind (two for `ended`).
EVENT_FIXTURES = (
    "job_event/valid/accepted.json",
    "job_event/valid/started.json",
    "job_event/valid/progress.json",
    "job_event/valid/output.json",
    "job_event/valid/cancel_requested.json",
    "job_event/valid/ended_completed.json",
    "job_event/valid/ended_cancelled.json",
)
TIMESTAMPS = frozenset({"created_at", "started_at", "ended_at", "recorded_at"})
RESULTS_SCHEMA = "application-results.schema.json"
#: Each `application-results` `$def`'s valid fixture: what the response shows.
RESULTS_VALID = {
    "submit_result": "solve_accepted_and_run_inline",
    "job_page": "one_converged_solve",
    "job_event_page": "first_three_events",
    "job_wait": "ended_converged_solve",
    "project_summary": "two_revisions_one_job",
    "model_registry_view": "registered_models",
    "revision_summary": "syn001_nominal",
    "revision_page": "two_revisions",
    "projection": "syn001_nominal_depth_1",
    "semantic_diff": "one_value_changed_one_member_removed",
}


def _pin_threads() -> None:
    for variable in THREAD_VARIABLES:
        os.environ.setdefault(variable, "1")


def solution_state_documents() -> dict[str, Any]:
    """The solution-state fixture's document, from a live `run_revision_session` (threads pinned
    as CI pins them)."""
    _pin_threads()
    document = yaml.safe_load(REVISION.read_text(encoding="utf-8"))
    route = select_route(document)
    if not isinstance(route, Route) or route.solve_path != "revision_eo":
        raise SystemExit(f"SYN-001-nominal does not route to revision_eo: {route}")
    policy = resolve_policy("default", route.solve_path)
    assert policy is not None
    with tempfile.TemporaryDirectory() as scratch:
        directory = Path(scratch)
        manifest = run_revision_session(
            route,
            document,
            directory,
            run_id="t07-fixture",
            policy=policy,
            check_policy=CheckPolicy(),
            policy_requested="default",
        )
        if NAME not in manifest.artifacts or manifest.verification_status != "VERIFIED":
            raise SystemExit(f"no verified solution state: {manifest.verification_status}")
        return {FIXTURE: read_artifact(directory, NAME)}


def job_documents() -> dict[str, Any]:
    """The job and job-event fixtures, from three real jobs of one project (module docstring)."""
    _pin_threads()
    document = yaml.safe_load(REVISION.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as scratch:
        application = LocalApplication.create(Path(scratch) / "project", project_id="t07-fixtures")
        try:
            revision_id = commit(application, document, "syn001-nominal")
            _, cancelled = cancel_while_queued(
                application,
                JobRequest("solve", "fixture-cancelled-while-queued", SolveBody(revision_id)),
            )
            solved = application.submit_job(
                JobRequest("solve", "fixture-solve", SolveBody(revision_id))
            ).job
            reproduced = application.submit_job(
                JobRequest(
                    "reproduce",
                    "fixture-reproduce",
                    ReproduceBody(f"{solved.job_id}:bundle", rerun=False),
                )
            ).job
            violations = lifecycle_violations(application)
            if violations:
                raise SystemExit(f"the fixture jobs break the lifecycle: {violations}")
            jobs = {
                job.job_id: application.store.job_snapshot(job.job_id)
                for job in (cancelled, solved, reproduced)
            }
        finally:
            application.close()
    documents: dict[str, Any] = {}
    for job, _ in jobs.values():
        documents[JOB_FIXTURES[len(job.outputs)]] = job.as_document()
    solve_events = [event.as_document() for event in jobs[solved.job_id][1]]
    cancel_events = [event.as_document() for event in jobs[cancelled.job_id][1]]
    first = {
        kind: next(e for e in solve_events if e["kind"] == kind)
        for kind in ("accepted", "started", "progress", "output", "ended")
    }
    for name, event in zip(
        EVENT_FIXTURES,
        (
            first["accepted"],
            first["started"],
            first["progress"],
            first["output"],
            next(e for e in cancel_events if e["kind"] == "cancel_requested"),
            first["ended"],
            cancel_events[-1],
        ),
        strict=True,
    ):
        documents[name] = event
    return documents


def application_results_documents() -> dict[str, Any]:
    """The `application-results` fixtures, from real responses (module docstring)."""
    _pin_threads()
    document = yaml.safe_load(REVISION.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as scratch:
        application = LocalApplication.create(Path(scratch) / "project", project_id="t07-results")
        try:
            parent = commit(application, document, "syn001-nominal")
            # The child: the first specification's value changed and its notes removed.
            edited = copy.deepcopy(document)
            edited["specifications"][0]["value"] = 1.5
            del edited["specifications"][0]["notes"]
            child = commit(application, edited, "syn001-edited")

            def call(name: str, request: dict[str, Any]) -> Any:
                return dispatch(application, name, request)

            submitted = call(
                "submit_job",
                {
                    "operation": "solve",
                    "idempotency_key": "fixture-results-solve",
                    "body": {"revision_id": parent},
                },
            )
            job_id = submitted["job"]["job_id"]
            revisions = call("list_revisions", {})
            responses = {
                "submit_result": submitted,
                "job_page": call("list_jobs", {}),
                "job_event_page": call("list_job_events", {"job_id": job_id, "limit": 3}),
                "job_wait": call("wait_job", {"job_id": job_id, "timeout_s": 0}),
                "project_summary": call("get_project", {}),
                "model_registry_view": call("list_models", {}),
                "revision_summary": revisions["items"][0],
                "revision_page": revisions,
                "projection": call("get_revision", {"revision_id": parent, "depth": 1}),
                "semantic_diff": call(
                    "diff_revisions", {"from_revision": parent, "to_revision": child}
                ),
            }
            violations = lifecycle_violations(application)
            if violations:
                raise SystemExit(f"the fixture job breaks the lifecycle: {violations}")
        finally:
            application.close()
    schema = json.loads((ROOT / "schemas" / RESULTS_SCHEMA).read_text(encoding="utf-8"))
    documents: dict[str, Any] = {}
    for name, response in responses.items():
        documents[f"application_results/{name}/valid/{RESULTS_VALID[name]}.json"] = response
        member = schema["$defs"][name]["required"][0]
        documents[f"application_results/{name}/invalid/missing_{member}.json"] = {
            "expect_error": f"'{member}' is a required property",
            "document": {key: value for key, value in response.items() if key != member},
        }
    # ADR 0019 Amendment 2 (ruling round 6, B2 item 4): the first pin of the response without
    # the member the amendment requires.
    registry = copy.deepcopy(responses["model_registry_view"])
    (pinned,) = [model for model in registry["models"] if model["pins"]][:1]
    del pinned["pins"][0]["specifications"]
    documents["application_results/model_registry_view/invalid/pin_missing_specifications.json"] = {
        "expect_error": "'specifications' is a required property",
        "document": registry,
    }
    return documents


def documents() -> dict[str, Any]:
    return {**solution_state_documents(), **job_documents(), **application_results_documents()}


def stable(document: Any) -> Any:
    """`document` with the members that differ between generations masked: timestamps, and the
    `sha256` and `size_bytes` of every artifact reference."""
    if isinstance(document, dict):
        reference = {"kind", "artifact_id", "sha256", "size_bytes", "name"} == set(document)
        return {
            key: "<volatile>"
            if key in TIMESTAMPS or (reference and key in ("sha256", "size_bytes"))
            else stable(value)
            for key, value in document.items()
        }
    if isinstance(document, list):
        return [stable(item) for item in document]
    return document


def serialize(document: Any) -> str:
    return json.dumps(document, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    status = 0
    for name, document in documents().items():
        path = FIXTURE_DIR / name
        same = False
        if path.is_file():
            committed = json.loads(path.read_text(encoding="utf-8"))
            same = (
                committed == document if name == FIXTURE else stable(committed) == stable(document)
            )
        if same:
            print(f"same {name}")
        elif arguments.write:
            # Only a missing or differing fixture is (re)written: a passed one is never
            # regenerated.
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialize(document), encoding="utf-8")
            print(f"wrote {name}")
        else:
            print(f"{'differs' if path.is_file() else 'missing'} {name}")
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
