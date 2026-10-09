"""The experiment runner: request → key → lock → cache? → evaluate → records (M02 design note
§3.2-§3.4, §5; ADR 0033 D4-D7, D11).

`ExperimentRunner.run` evaluates one process inlet of one variant through M01's `Boundary` and
keeps every fact it produces:

1. **Environment and key.** The backend's environment fingerprint is measured once per runner
   (the handshake, one per job) and its SHA-256 enters the request; the key is the request's own
   hash (§3.2). The handshake's outcome — success or failure, after its own retries — is kept for
   the runner's life: a job never handshakes twice (R-236).
2. **Lock, then cache.** The key's `flock` is held for the rest of the call and the cache is read
   after it is taken, so two jobs on one key execute it once: the second is a cache hit.
3. **Deterministic or transient (§3.3).** An evaluation that completed — any boundary status,
   refusals and `not_converged` included — or a boundary refusal before the evaluation
   (`not_executed`) is **deterministic**: one write-once `result`, served by the cache from then
   on. A timeout, a crash, a protocol, spawn or environment failure, or a cancellation is
   **transient**: attempts only, never cached, never with outlet values.
4. **Retry (§5.2).** Once more after `crashed`, `protocol_error` or `spawn_failed` (the variant's
   `max_retries`), as a new attempt inside the same lock; never after `timed_out`,
   `environment_*` or a cancellation. The handshake and the evaluation have **separate** budgets,
   each `max_retries` (R-236): the handshake is the job's, the evaluation the experiment's.
5. **Bypass (§5.3)** executes although a result exists, records the new attempt as a repeat of
   the producing one with whether its outlet is bitwise equal, and never overwrites the result;
   a deterministic repeat that differs appends a determinism finding.
6. **Cancellation.** An interrupt raised by the cooperative check (inside the launcher's poll or
   the lock's wait) leaves a `cancelled` attempt, written on the way out, and propagates.

Every attempt is written before its result is used. Property calls the boundary makes are counted
into the result (`provider_calls`) and are never a solve's budget (R-233): the caller passes an
unmetered provider.
"""

from __future__ import annotations

import dataclasses
import os
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from openflowsheet.adapters.experiments.backends import (
    Backend,
    Environment,
    Execution,
    InProcessBackend,
    OutOfProcessBackend,
    tube_document,
)
from openflowsheet.adapters.experiments.request import build_request
from openflowsheet.adapters.experiments.store import ExperimentStore
from openflowsheet.adapters.external.launcher import LaunchProgress
from openflowsheet.adapters.variants import Variant, hard_domain
from openflowsheet.canonical import document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1.boundary import (
    DATA_H2_N2,
    DATA_PRESSURE_PA,
    DATA_TEMPERATURE_K,
    DEFECT_LIMIT,
    EPS_PRESSURE,
    Boundary,
    ReactorResult,
    TubeInlet,
    refused,
)
from openflowsheet.orchestrator.trace import INTERRUPT_CHECK
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)

__all__ = ["DETERMINISTIC", "RETRYABLE", "ExperimentOutcome", "ExperimentRunner"]

ATTEMPT_VERSION: Final = "experiment-attempt-v1"
RESULT_VERSION: Final = "experiment-result-v1"
#: §3.3: the execution statuses whose outcome is a fact about the request.
DETERMINISTIC: Final = frozenset({"completed", "not_executed"})
#: §5.2: the transient statuses retried once.
RETRYABLE: Final = frozenset({"crashed", "protocol_error", "spawn_failed"})
CacheMode = Literal["use", "bypass"]


@dataclass(frozen=True)
class ExperimentOutcome:
    """What one `run` produced or found: the request, the deterministic result (stored or served;
    `None` when transient), the attempts this call wrote, and the boundary's envelope."""

    request: Mapping[str, Any]
    result: Mapping[str, Any] | None
    envelope: Mapping[str, Any]
    cache_hit: bool
    attempts: tuple[Mapping[str, Any], ...] = field(default=())

    @property
    def key(self) -> str:
        return str(self.request["experiment_key"])

    @property
    def transient(self) -> bool:
        return self.result is None


class _Counting:
    """The provider, with the experiment's own calls counted (R-233)."""

    def __init__(self, provider: PropertyProvider) -> None:
        self.provider = provider
        self.calls = 0

    def describe(self) -> PropertyCapabilities:
        return self.provider.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.calls += 1
        return self.provider.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self.calls += 1
        return self.provider.flash(request, context)


def _bits(value: Any) -> Any:
    """A document with every number as its exact binary64 hex form: equality is bitwise (signed
    zero included). A record read back from disk spells an integral float as an integer (ADR 0002
    canonical JSON), so integers are read as the binary64 they denote."""
    if isinstance(value, float | int) and not isinstance(value, bool):
        return float(value).hex()
    if isinstance(value, Mapping):
        return {key: _bits(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_bits(item) for item in value]
    return value


def _differing(first: Mapping[str, Any], second: Mapping[str, Any]) -> list[str]:
    """The execution members in which two deterministic attempts differ in any bit."""
    names = ("tube_outlet", "stage")
    return [name for name in names if _bits(first.get(name)) != _bits(second.get(name))]


def supported(variant: Variant, capabilities: PropertyCapabilities) -> None:
    """Refuse (`ValueError`) a variant whose boundary block is not the boundary this build
    implements: M01's convention, ε_P, projection, defect limit and data domain, on the provider
    the caller supplies."""
    block = variant.boundary
    implemented = {
        "provider": capabilities.provider_id,
        "reference_convention": capabilities.reference_convention,
        "pressure_convention": "zero_drop",
        "eps_P": EPS_PRESSURE,
        "projection": "lsq_extent_v1",
        "defect_limit": DEFECT_LIMIT,
        "duty": "process_side",
        "per_tube_scaling": True,
    }
    for name, value in implemented.items():
        if block[name] != value:
            raise ValueError(
                f"{variant.variant_id}: boundary.{name} = {block[name]!r}; this build "
                f"evaluates {value!r}"
            )
    data = block["data_domain"]
    declared = (tuple(data["T_K"]), tuple(data["P_Pa"]), tuple(data["H2_N2"]))
    if declared != (DATA_TEMPERATURE_K, DATA_PRESSURE_PA, DATA_H2_N2):
        raise ValueError(f"{variant.variant_id}: boundary.data_domain is not M01's")


def _frozen(failure: Execution) -> Execution:
    """The job's failed handshake as a later experiment of the job records it: the same status
    and logs, said to be the job's outcome, not a new execution (R-236)."""
    message = f"the job's handshake failed and is not repeated (R-236): {failure.message}"
    return dataclasses.replace(failure, message=message, timing={"wall_s": 0.0})


class ExperimentRunner:
    """Runs experiments into one project's records, for one job (or none)."""

    def __init__(
        self,
        records: ExperimentStore,
        provider: PropertyProvider,
        context: EvaluationContext,
        *,
        job_id: str | None = None,
        backend_for: Callable[[Variant], Backend] | None = None,
        check: Callable[[], None] | None = None,
    ) -> None:
        self.records = records
        self.provider = provider
        self.context = context
        self.job_id = job_id
        self._backend_for = backend_for
        self._check = check
        self._backends: dict[str, Backend] = {}
        #: Per variant: the handshake's outcome and the failed handshakes before it (R-236).
        self._handshakes: dict[str, tuple[Environment, tuple[Execution, ...]]] = {}
        #: The variants whose failed handshakes are already written as attempts (by the first
        #: `run`, whichever call handshook).
        self._recorded: set[str] = set()

    def backend(self, variant: Variant) -> Backend:
        """One backend per variant for the runner's life: its handshake is the job's (§6.1)."""
        if variant.sha256 not in self._backends:
            if self._backend_for is not None:
                backend = self._backend_for(variant)
            elif variant.kind == "in_process":
                backend = InProcessBackend(variant)
            else:
                backend = OutOfProcessBackend(variant)
            self._backends[variant.sha256] = backend
        return self._backends[variant.sha256]

    def check(self) -> Callable[[], None] | None:
        return self._check if self._check is not None else INTERRUPT_CHECK.get()

    def request(
        self,
        variant: Variant,
        inlet: StreamState,
        components: Sequence[str],
        n_tubes: float,
    ) -> dict[str, Any]:
        """The keyed request `run` would evaluate for this inlet, with no experiment record
        written: a caller can count a plan's cache misses before running any of it (M04 spec
        §5.4). The job's handshake runs here if it has not run yet, once per runner (R-236);
        its failed attempts, if any, are written by the first `run`, as without this call."""
        capabilities = self.provider.describe()
        supported(variant, capabilities)
        backend = self.backend(variant)
        environment, _, _ = self._environment(
            variant, backend, int(variant.execution["max_retries"])
        )
        return build_request(variant, capabilities, n_tubes, components, inlet, environment.sha256)

    def run(
        self,
        variant: Variant,
        inlet: StreamState,
        components: Sequence[str],
        n_tubes: float,
        *,
        cache: CacheMode = "use",
    ) -> ExperimentOutcome:
        capabilities = self.provider.describe()
        supported(variant, capabilities)
        backend = self.backend(variant)
        check = self.check()
        retries = int(variant.execution["max_retries"])
        environment, failed, _ = self._environment(variant, backend, retries)
        first = variant.sha256 not in self._recorded
        self._recorded.add(variant.sha256)
        request = build_request(
            variant, capabilities, n_tubes, components, inlet, environment.sha256
        )
        key = request["experiment_key"]
        with self.records.locked(key, check):
            existing = self.records.result(key)
            written: list[Mapping[str, Any]] = []
            self.records.write_request(request, self.job_id)  # once; byte-equal if present
            # Every execution is an attempt (§3.3): a handshake that failed is one, under the key
            # its fingerprint (measured after a retry, or not at all) gave the request. A later
            # experiment of the same job is not handshaken again (R-236); when the job's handshake
            # failed, its attempt records that frozen failure, which it did not execute.
            if first:
                for failure in failed:
                    written.append(self._failed_handshake(key, failure, existing))
            elif environment.failure is not None:
                written.append(self._failed_handshake(key, _frozen(environment.failure), existing))
            if environment.failure is not None:
                failure = environment.failure
                envelope = refused("error", f"external_{failure.status}", failure.message)
                return ExperimentOutcome(
                    request, None, envelope.as_document(), False, tuple(written)
                )
            if existing is not None and cache == "use":
                self.records.record_hit(key, self.job_id)
                return ExperimentOutcome(
                    request, existing, existing["envelope"], True, tuple(written)
                )
            while True:
                attempt, envelope, calls = self._attempt(
                    variant, backend, request, inlet, components, n_tubes, check, existing
                )
                written.append(attempt)
                status = attempt["execution"]["status"]
                if status in DETERMINISTIC:
                    break
                if status not in RETRYABLE or retries <= 0:
                    return ExperimentOutcome(
                        request, None, envelope.as_document(), False, tuple(written)
                    )
                retries -= 1
            if existing is not None:  # a bypassed repeat: never overwritten
                findings = _differing(self._producing(existing), attempt["execution"])
                if findings:
                    finding = {"attempt": attempt["attempt"], "differing_fields": findings}
                    self.records.append_finding(key, finding, self.job_id)
                result = self.records.result(key)
                assert result is not None
                return ExperimentOutcome(request, result, result["envelope"], False, tuple(written))
            result = self._result(variant, environment, request, attempt, envelope, calls)
            self.records.write_result(result, self.job_id)
            return ExperimentOutcome(request, result, result["envelope"], False, tuple(written))

    # -- one attempt ---------------------------------------------------------------------------

    def _environment(
        self, variant: Variant, backend: Backend, retries: int
    ) -> tuple[Environment, tuple[Execution, ...], bool]:
        """The backend's environment and the failed handshakes before it, and whether this call
        handshook. The handshake is retried after a transient failure within its own budget
        (`retries`, R-236) — before any key exists, so a fingerprint measured on a retry is the one
        the key carries. Its outcome, success or failure, is kept for the runner's life (one job):
        a later call returns it without handshaking again."""
        if variant.sha256 in self._handshakes:
            environment, failed = self._handshakes[variant.sha256]
            return environment, failed, False
        folder = self.records.base / "handshakes" / variant.sha256[:16]
        found: list[Execution] = []
        while True:
            # Named, not created: only a handshake that runs creates it (a frozen or an
            # in-process environment needs none).
            directory = folder / f"{self.job_id or 'nojob'}-{os.getpid()}-{uuid.uuid4().hex[:12]}"
            environment = backend.environment(directory)
            if environment.failure is not None:
                found.append(environment.failure)
            if (
                environment.failure is None
                or environment.failure.status not in RETRYABLE
                or len(found) > retries
            ):
                self._handshakes[variant.sha256] = (environment, tuple(found))
                return environment, tuple(found), True

    def _failed_handshake(
        self, key: str, failure: Execution, existing: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        number = self.records.next_attempt(key)
        repeat_of = None if existing is None else int(existing["produced_by"]["attempt"])
        attempt = self._document(key, number, failure, None, 0.0, repeat_of, None)
        self.records.write_attempt(attempt, self.job_id)
        return attempt

    def _producing(self, result: Mapping[str, Any]) -> Mapping[str, Any]:
        produced = result["produced_by"]["attempt"]
        attempt = self.records.read(self.records.attempt_path(result["experiment_key"], produced))
        assert attempt is not None
        execution: Mapping[str, Any] = attempt["execution"]
        return execution

    def _attempt(
        self,
        variant: Variant,
        backend: Backend,
        request: Mapping[str, Any],
        inlet: StreamState,
        components: Sequence[str],
        n_tubes: float,
        check: Callable[[], None] | None,
        existing: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any], ReactorResult, int]:
        """One evaluation attempt, its record written before it is returned (§3.3)."""
        key = request["experiment_key"]
        number = self.records.next_attempt(key)
        directory = self.records.attempt_directory(key, number)
        repeat_of = None if existing is None else int(existing["produced_by"]["attempt"])
        provider = _Counting(self.provider)
        boundary = Boundary(
            provider=provider,
            n_tubes=n_tubes,
            identity=backend.identity(n_tubes),
            sweep_ratio=variant.sweep_ratio,
            discretization_estimate=variant.accuracy["discretization_estimate"],
            hard_domain=hard_domain(variant),
        )
        progress = LaunchProgress()
        seen: list[tuple[TubeInlet, Execution]] = []

        def evaluation(tube: TubeInlet) -> Any:
            execution = backend.evaluate(tube, directory, progress, check)
            seen.append((tube, execution))
            return execution.answer

        started = time.perf_counter()
        interrupted = True
        try:
            envelope = boundary.evaluate(inlet, components, evaluation, self.context)
            interrupted = False
        except Exception:
            interrupted = False
            raise
        finally:
            if interrupted:  # an interrupt (a BaseException) is on its way out: record it first
                cancelled = Execution(
                    kind=backend.kind,
                    status="cancelled",
                    answer=None,
                    message="cancelled: the job was interrupted during the evaluation",
                    exit_code=progress.exit_code,
                    signal=progress.signal,
                    logs=progress.logs,
                    timing={"wall_s": progress.wall_s},
                )
                tube = seen[0][0] if seen else None
                attempt = self._document(
                    key, number, cancelled, tube, time.perf_counter() - started, repeat_of, None
                )
                self.records.write_attempt(attempt, self.job_id)
        wall = time.perf_counter() - started
        if not seen:
            execution = Execution(kind=backend.kind, status="not_executed", answer=None)
            tube = None
        else:
            tube, execution = seen[0]
        equal: bool | None = None
        if existing is not None and execution.status in DETERMINISTIC:
            equal = not _differing(self._producing(existing), self._execution(execution, tube))
        attempt = self._document(key, number, execution, tube, wall, repeat_of, equal)
        self.records.write_attempt(attempt, self.job_id)
        return attempt, envelope, provider.calls

    def _execution(self, execution: Execution, tube: TubeInlet | None) -> dict[str, Any]:
        directory_logs = execution.logs
        return {
            "kind": execution.kind,
            "status": execution.status,
            "exit_code": execution.exit_code,
            "signal": execution.signal,
            "message": execution.message[:4096],
            "tube_inlet": None if tube is None else tube_document(tube),
            "tube_outlet": None if execution.tube_outlet is None else dict(execution.tube_outlet),
            "stage": execution.stage,
            "diagnostics": None if execution.diagnostics is None else dict(execution.diagnostics),
            "fingerprint": None if execution.fingerprint is None else dict(execution.fingerprint),
            "logs": None if directory_logs is None else dict(directory_logs),
        }

    def _document(
        self,
        key: str,
        number: int,
        execution: Execution,
        tube: TubeInlet | None,
        wall_s: float,
        repeat_of: int | None,
        equal: bool | None,
    ) -> dict[str, Any]:
        body = self._execution(execution, tube)
        if body["logs"] is not None:
            directory = execution.directory or self.records.attempt_directory(key, number)
            body["logs"]["relpaths"] = {
                name: self.records.relpath(directory / path)
                for name, path in body["logs"]["relpaths"].items()
            }
        timing = dict(execution.timing)
        body["timing"] = {
            "wall_s": timing.get("wall_s") if timing.get("wall_s") is not None else wall_s,
            "startup_s": timing.get("startup_s"),
            "solve_s": timing.get("solve_s"),
        }
        return {
            "schema_version": ATTEMPT_VERSION,
            "experiment_key": key,
            "attempt": number,
            "job_id": self.job_id,
            "execution": body,
            "repeat_of": repeat_of,
            "repeat_bitwise_equal": equal,
        }

    def _result(
        self,
        variant: Variant,
        environment: Environment,
        request: Mapping[str, Any],
        attempt: Mapping[str, Any],
        envelope: ReactorResult,
        calls: int,
    ) -> dict[str, Any]:
        reactor = variant.evaluation.get("reactor")
        return {
            "schema_version": RESULT_VERSION,
            "experiment_key": request["experiment_key"],
            "request_sha256": document_sha256(request),
            "outcome_class": "deterministic",
            "envelope": envelope.as_document(),
            "accuracy": dict(variant.accuracy),
            "produced_by": {"job_id": self.job_id, "attempt": attempt["attempt"]},
            "provenance": {
                "variant_id": variant.variant_id,
                "variant_sha256": variant.sha256,
                "reactor": None if reactor is None else dict(reactor),
                "fingerprint_sha256": environment.sha256,
            },
            "provider_calls": calls,
            "determinism_findings": [],
        }
