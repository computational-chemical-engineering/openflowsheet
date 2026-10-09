"""Pre-warm a surrogate study's experiment cache with concurrent `experiment` jobs (M04 spec §18
A1.6; ADR 0037 Amendment 1 D8; R-294).

`surrogate_study` is sequential. Many cold experiments are run concurrently only here: the plan's
requests that the cache misses are submitted as M02 `experiment` jobs under the process executor
at `executor.max_workers` (16 on the 24-core host; R-250 caps it at the physical cores), and the
study then runs with every record cached (cold 0). No bit changes, by construction: each record
is a deterministic function of its exact key (M01.A43, R-250), and the study reads records in plan
order whatever order they were written in. Concurrency is telemetry — it is recorded only in the
report this script writes, which the package evidence manifest carries, and never in a
SurrogateManifest or a ModelEvidence.

In order:

1. **The study's own refusals, before anything is submitted.** The plan is the registered one for
   the parent and passes its guard (`plan_invalid`, `plan_not_registered`, ...); an `it<i>`,
   i ≥ 2, is permitted by the project's earlier manifests (`iteration_not_permitted`); and the
   cache misses, counted exactly as the study counts them, do not exceed the approved budget of
   cold experiments — else INSUFFICIENT_EVIDENCE (`budget_below_plan`) with `cache_misses`, and
   nothing is submitted.
2. **The misses as `experiment` jobs**, in plan order, under the process executor at
   `max_workers` (the project policy's `executor` settings, restored afterwards).
3. **Transient outcomes are retried** (a `timed_out` under load, an executor failure): every
   request still without a deterministic result after a round is submitted again under a new
   idempotency key, up to `retries` further rounds. Whatever remains is listed as incomplete: the
   study will report the plan incomplete until a later pre-warm or study completes it. A retry
   never changes a bit — a result is a function of its key.
4. Optionally (`--study`), **the study** itself with `max_cold_experiments = 0`, which refuses if
   anything is still missing and otherwise runs fully cached.

The report (`--report`) records the parent, the plan, `max_workers`, the command, the misses
before, each round's submissions, every retry and what remains incomplete, and the wall time.

Usage (WO-11, the real reactor; never in the default gate):
    PYTHONPATH=src .venv/bin/python scripts/m04_prewarm.py --project <dir> \\
        --variant pymrm-6089593-g2-nz800-s123-v2 --plan it1 --budget <approved> \\
        --max-workers 16 --retries 2 --report <evidence>/prewarm.json --study
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from openflowsheet.adapters import variants  # noqa: E402
from openflowsheet.adapters.experiments.runner import ExperimentRunner  # noqa: E402
from openflowsheet.adapters.experiments.store import ExperimentStore  # noqa: E402
from openflowsheet.application.admission import stored_surrogate_manifests  # noqa: E402
from openflowsheet.application.authz import read_policy  # noqa: E402
from openflowsheet.application.jobs.executor import ProcessExecutor  # noqa: E402
from openflowsheet.application.jobs.model import TERMINAL_STATUSES  # noqa: E402
from openflowsheet.application.local import LocalApplication  # noqa: E402
from openflowsheet.application.operations import dispatch  # noqa: E402
from openflowsheet.application.store import (  # noqa: E402
    POLICY_NAME,
    atomic_write_bytes,
    policy_file_bytes,
)
from openflowsheet.application.types import ExecutorSettings  # noqa: E402
from openflowsheet.compiled import EvaluationContext  # noqa: E402
from openflowsheet.models.c1 import COMPONENTS  # noqa: E402
from openflowsheet.studies.surrogate.iterations import predecessors  # noqa: E402
from openflowsheet.studies.surrogate.plan import PLAN_N_TUBES  # noqa: E402
from openflowsheet.studies.surrogate.study import prepare  # noqa: E402
from openflowsheet.thermo import StreamState  # noqa: E402
from openflowsheet.thermo.pr_c1 import PrC1Provider  # noqa: E402

SCRIPT: Final = "scripts/m04_prewarm.py"
#: How often the store is read while jobs run (seconds); a wake-up costs one query.
POLL_S: Final = 0.2


def physical_cores() -> int:
    """The host's physical cores (R-250's cap on `max_workers`): distinct core sibling sets on
    Linux, else the logical count."""
    topology = Path("/sys/devices/system/cpu")
    siblings = {
        path.read_text(encoding="utf-8").strip()
        for path in topology.glob("cpu[0-9]*/topology/core_cpus_list")
    }
    return len(siblings) or (os.cpu_count() or 1)


@dataclass
class Report:
    """What the pre-warm did: the package evidence manifest's record of it (A1.6)."""

    parent: dict[str, str]
    plan_id: str
    max_workers: int
    command: list[str]
    requests: int
    cache_misses_before: int
    budget: int
    refused: dict[str, Any] | None = None
    rounds: list[dict[str, Any]] = field(default_factory=list)
    retries: list[dict[str, Any]] = field(default_factory=list)
    incomplete: list[dict[str, str]] = field(default_factory=list)
    wall_time_s: float = 0.0
    study: dict[str, Any] | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "script": SCRIPT,
            "command": self.command,
            "parent": self.parent,
            "plan_id": self.plan_id,
            "executor": {"kind": "process", "max_workers": self.max_workers},
            "requests": self.requests,
            "cache_misses_before": self.cache_misses_before,
            "budget": {"max_cold_experiments": self.budget},
            "refused": self.refused,
            "rounds": self.rounds,
            "retries": self.retries,
            "incomplete": self.incomplete,
            "wall_time_s": self.wall_time_s,
            "study": self.study,
        }


def experiment_body(variant: variants.Variant, state: StreamState) -> dict[str, Any]:
    """The `experiment` job body of one plan request (one tube, the plan's inlet exactly)."""
    return {
        "model": {
            "id": variant.model_id,
            "version": variant.variant_id,
            "artifact_ref": variant.sha256,
        },
        "inlet": {
            "components": list(COMPONENTS),
            "n": list(state.n),
            "T": state.temperature,
            "P": state.pressure,
        },
        "n_tubes": PLAN_N_TUBES,
        "cache": "use",
    }


def _set_executor(directory: Path, settings: ExecutorSettings) -> ExecutorSettings:
    """Write the project policy's `executor` settings (an operator's edit of the file); the
    settings in force before."""
    path = directory / POLICY_NAME
    policy = read_policy(path)
    atomic_write_bytes(path, policy_file_bytes(replace(policy, executor=settings)))
    return policy.executor


def _wait(application: LocalApplication, job_ids: Sequence[str]) -> None:
    pending = set(job_ids)
    while pending:
        pending = {
            job_id
            for job_id in pending
            if (job := application.store.get_job(job_id)) is None
            or job.status not in TERMINAL_STATUSES
        }
        if pending:
            time.sleep(POLL_S)


def prewarm(
    directory: Path,
    variant: variants.Variant,
    plan_id: str,
    *,
    max_workers: int,
    budget: int,
    retries: int = 2,
    study: bool = False,
    command: Sequence[str] = (),
) -> Report:
    """Pre-warm `plan_id`'s experiments for `variant` in the project at `directory` (module
    docstring). `ValueError` for a `max_workers` above the physical cores or a plan the study
    would refuse; a budget refusal is a report with `refused` set and nothing submitted."""
    if not 1 <= max_workers <= physical_cores():
        raise ValueError(f"max_workers = {max_workers}: 1 to {physical_cores()} physical cores")
    if budget < 0 or retries < 0:
        raise ValueError("budget and retries are counts >= 0")
    started = time.monotonic()
    plan = prepare(variant, plan_id)  # PlanRefusedError (a ValueError) before anything runs
    application = LocalApplication.open(directory)
    try:
        if plan.iteration > 1:
            predecessors(
                variant,
                plan_id,
                stored_surrogate_manifests(application.store, application.files_root),
            )
        # The study's count: the same runner identity as the job's (ADR 0033), read-only.
        runner = ExperimentRunner(
            ExperimentStore(application.files_root),
            PrC1Provider(),
            EvaluationContext(model_version=variant.variant_id, constants_sha256=variant.sha256),
        )
        labelled = plan.requests()
        keys = [
            str(runner.request(variant, state, COMPONENTS, PLAN_N_TUBES)["experiment_key"])
            for _, state in labelled
        ]
        records = runner.records
        missing = [
            (label, state, key)
            for (label, state), key in zip(labelled, keys, strict=True)
            if records.result(key) is None
        ]
    finally:
        application.close()
    report = Report(
        parent={"variant_id": variant.variant_id, "variant_sha256": variant.sha256},
        plan_id=plan_id,
        max_workers=max_workers,
        command=list(command),
        requests=len(labelled),
        cache_misses_before=len(missing),
        budget=budget,
    )
    if len(missing) > budget:  # spec §5.4's refusal, the study's own rule
        report.refused = {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "insufficient": ["budget_below_plan"],
            "cache_misses": len(missing),
        }
        report.wall_time_s = time.monotonic() - started
        return report

    token = uuid.uuid4().hex[:12]
    previous = _set_executor(directory, ExecutorSettings(max_workers=max_workers))
    try:
        application = LocalApplication.open(directory, executor=ProcessExecutor())
        try:
            for round_number in range(retries + 1):
                if not missing:
                    break
                submitted = []
                for label, state, key in missing:
                    request = {
                        "operation": "experiment",
                        "idempotency_key": f"m04-prewarm-{plan_id}-{token}-r{round_number}-"
                        f"{len(submitted)}",
                        "body": experiment_body(variant, state),
                    }
                    job = dispatch(application, "submit_job", request)["job"]
                    submitted.append((label, key, job["job_id"]))
                    if round_number > 0:
                        report.retries.append(
                            {
                                "round": round_number,
                                "label": label,
                                "key": key,
                                "job_id": job["job_id"],
                            }
                        )
                _wait(application, [job_id for _, _, job_id in submitted])
                still = [(label, key) for label, key, _ in submitted if records.result(key) is None]
                report.rounds.append(
                    {
                        "round": round_number,
                        "submitted": len(submitted),
                        "without_result": len(still),
                    }
                )
                by_key = {key: (label, state) for label, state, key in missing}
                missing = [(by_key[key][0], by_key[key][1], key) for _, key in still]
        finally:
            application.close()
    finally:
        _set_executor(directory, previous)
    report.incomplete = [{"label": label, "key": key} for label, _, key in missing]

    if study:
        application = LocalApplication.open(directory)
        try:
            request = {
                "operation": "surrogate_study",
                "idempotency_key": f"m04-prewarm-{plan_id}-{token}-study",
                "body": {
                    "parent": {
                        "model_id": variant.model_id,
                        "variant_id": variant.variant_id,
                        "variant_sha256": variant.sha256,
                    },
                    "plan_id": plan_id,
                    "budget": {"max_cold_experiments": 0},
                },
            }
            job = dispatch(application, "submit_job", request)["job"]
            answer = dispatch(application, "get_job_result", {"job_id": job["job_id"]})
            report.study = {"job_id": job["job_id"], "answer": answer["surrogate_study"]}
        finally:
            application.close()
    report.wall_time_s = time.monotonic() - started
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--variant", required=True, help="a registered variant id")
    parser.add_argument("--plan", required=True, help="it1, it1-prefix (synthetic only), it2, it3")
    parser.add_argument("--budget", type=int, required=True, help="approved cold experiments")
    parser.add_argument("--max-workers", type=int, default=16)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--study", action="store_true", help="then run the study, budget 0")
    arguments = parser.parse_args(argv)
    variant = variants.registered_variant(arguments.variant)
    report = prewarm(
        arguments.project,
        variant,
        arguments.plan,
        max_workers=arguments.max_workers,
        budget=arguments.budget,
        retries=arguments.retries,
        study=arguments.study,
        command=[SCRIPT, *(argv if argv is not None else sys.argv[1:])],
    )
    document = report.as_document()
    text = json.dumps(document, indent=2) + "\n"
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(text, encoding="utf-8")
    print(text, end="")
    if report.refused is not None or report.incomplete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
