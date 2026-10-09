"""ExternalFunction holders: the one place a TRF run reaches a black box (M05 design note §6.3;
ADR 0038 D5; R-262).

There is one `EFHolder` per black box — per property block and per external link — and every
`ExternalFunction` of that box calls through it. What the holder guarantees is what the probe found
TRF does not (design note §4):

- **Identity under clone.** TRF works on `model.clone()`, which deep-copies whatever a callback is
  bound to, so a ledger kept on a bound method's owner sees none of TRF's calls (probe P2′: 0 of
  23). `__deepcopy__` returns the holder itself, and the callables handed to Pyomo are closures,
  which `deepcopy` treats atomically; both together keep one holder, one memo and one ledger.
- **Exact-key memo.** Values and Jacobians are memoized on the exact binary64 inputs (canonical
  bytes, signed zeros normalized as ADR 0001 D1.5 requires of every state key), never quantized.
- **Never a non-finite value.** TRF accepts a NaN silently and reports optimal (probe P7), so a
  non-finite output — or input — is a refusal, never a return value.
- **Typed refusals.** A property block's `DomainError`, a truth's non-`ok` status, a non-finite
  value and an exhausted budget each raise `TruthRefused`. TRF has no evaluation-failure path (probe
  P6): the exception ends the run and the runner maps it to `TRF_TRUTH_REFUSED(<status>:<reason>)`.
  A refused key is remembered, so asking again re-raises without a second evaluation, and every
  refusal is kept on the holder: Pyomo 6.10.1's `EFReplacement.exitNode` swallows *any* exception
  raised by the start-value evaluation (a bare `except:` that sets the holder variable to 0), so
  the runner must find a refusal there even when TRF did not see it.
- **Budget.** Before every cold value request the holder admits it against every cap it was given
  for the run; a refused admission raises `TruthRefused("budget", "budget_exhausted")` and is not a
  request. A cap is therefore never exceeded.
- **Ledger.** Every request — a value or a Jacobian, cold or a memo hit — appends one
  `HolderRequest`. The TRF iteration it belongs to is read from the run's `RunState`, which the log
  handler advances (`trf_state.TrfLogHandler`); the first value request at a key in a run is given
  its purpose from TRF 6.10.1's fixed call order (design note §8.3).

This module imports neither Pyomo nor any truth: it is exercised in the default gate.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any, Final, Literal, Protocol

from openflowsheet.canonical import encode_doubles
from openflowsheet.compile.spec import DomainError, PropertyBlock

HolderKind = Literal["property_block", "truth"]
CallKind = Literal["value", "jacobian"]
Served = Literal["cold", "store_hit", "memo_hit"]

#: Design note §8.1's purposes of a first value request at a key (TRF 6.10.1's call order, §8.3).
TRF_START_VALUE: Final = "trf_start_value"
TRF_PMP_VALUE: Final = "trf_pmp_value"
TRF_TRIAL_VALUE: Final = "trf_trial_value"
#: The finite-difference policy's points (`truths.py`, M05-fd-v2): a gradient TRF asked for, the
#: affine basis's gradient at w₀ (§6.6), and the once-per-study gradient-quality check (§6.5).
TRF_FD_POINT: Final = "trf_fd_point"
BASIS_FD_POINT: Final = "basis_fd_point"
FDCHECK_POINT: Final = "fdcheck_point"

#: `describe()["kind"]` of a truth whose evaluations are M02 experiments: the one kind of box that
#: counts against a parent budget (§16.4). Surrogates and in-process test truths never do.
PARENT_EXPERIMENT: Final = "parent_experiment"

#: Orders refusals across holders, so the runner can name the first one of a run.
_REFUSAL_ORDER = itertools.count()
#: Admission against shared caps is one decision across every holder of a run and of a study.
_BUDGET_LOCK = threading.Lock()


class TruthRefused(Exception):  # noqa: N818 - the design note's name (§6.3; ADR 0038 D5)
    """A black box refused a request (ADR 0038 D5). `status` is the class of refusal — a truth's
    experiment status, `property_domain_error`, `non_finite_output`, `non_finite_input` or
    `budget` — and `reason` names what refused or why; `detail` is free text for the record.
    `meta` is the refusing truth's (§16.4), so a refused experiment is still accounted for."""

    def __init__(
        self, status: str, reason: str, detail: str = "", meta: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(f"{status}:{reason}" + (f" ({detail})" if detail else ""))
        self.status = status
        self.reason = reason
        self.detail = detail
        self.meta: Mapping[str, Any] = {} if meta is None else dict(meta)
        self.order = next(_REFUSAL_ORDER)

    @property
    def code(self) -> str:
        """`<status>:<reason>`, the argument of `TRF_TRUTH_REFUSED(...)`."""
        return f"{self.status}:{self.reason}"


class ColdBudget:
    """A cap on cold value requests, shared by every holder it is given to (design note §6.3).

    A run's cap and a study's cap are two `ColdBudget`s; a holder admits a cold request only when
    every one of its caps has room, and then charges all of them."""

    def __init__(self, name: str, cap: int) -> None:
        if cap < 0:
            raise ValueError(f"budget {name!r}: a cap is a count, got {cap}")
        self.name = name
        self.cap = cap
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.used >= self.cap


def _admit(budgets: Sequence[ColdBudget]) -> ColdBudget | None:
    """Charge every budget, or none: the first exhausted one, if any, is returned uncharged."""
    with _BUDGET_LOCK:
        for budget in budgets:
            if budget.exhausted:
                return budget
        for budget in budgets:
            budget.used += 1
        return None


class RunState:
    """What a holder needs to know about the TRF run it is serving.

    `last_logged_iteration` is `None` until TRF logs iteration 0, and is advanced by the log
    handler as each `****** Iteration k ******` record arrives. TRF 6.10.1 evaluates nothing
    between a record's lines, so a request made after the record of iteration k belongs to
    iteration k + 1 (design note §8.3)."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.last_logged_iteration: int | None = None

    @property
    def current_iteration(self) -> int:
        """The iteration a request made now belongs to: 0 (the start and the PMP) until iteration
        0 is logged, then one past the last logged."""
        last = self.last_logged_iteration
        return 0 if last is None else last + 1


@dataclass(frozen=True)
class HolderRequest:
    """One request a holder served (design note §6.3, §8.1).

    `served` is `cold` for an evaluation of the box, `store_hit` for a truth that answered from its
    experiment store, `memo_hit` for an answer from this holder's memo. A request whose evaluation
    refused carries the refusal's code as `status`; an admission the budget refused is not a
    request and is not here (it is in `EFHolder.refusals`)."""

    seq: int
    run_id: str | None
    call: CallKind
    inputs_sha256: str
    served: Served
    trf_iteration: int | None
    purpose: str | None
    status: str
    wall_s: float
    #: §16.4's `meta` of the value served (a truth's; `None`, 0, `False` for a property block and
    #: for a Jacobian): the experiment's key, the executions this request caused (0 unless it was
    #: served `cold` by an experiment), and whether the point is extrapolated.
    experiment_key: str | None = None
    executions: int = 0
    extrapolated: bool = False

    def as_document(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "run_id": self.run_id,
            "call": self.call,
            "inputs_sha256": self.inputs_sha256,
            "served": self.served,
            "trf_iteration": self.trf_iteration,
            "purpose": self.purpose,
            "status": self.status,
            "wall_s": self.wall_s,
            "experiment_key": self.experiment_key,
            "executions": self.executions,
            "extrapolated": self.extrapolated,
        }


@dataclass(frozen=True)
class BoxValues:
    """A box's outputs at one input, whether a truth served them from its store, and the truth's
    `meta` (§16.4; empty for a property block)."""

    values: tuple[float, ...]
    store_hit: bool = False
    meta: Mapping[str, Any] = field(default_factory=dict)


class BlackBox(Protocol):
    """What a holder evaluates: `n_out` outputs of `n_in` inputs, and their dense Jacobian.

    Either method raises `TruthRefused` to refuse; any other exception is a defect in the box and
    propagates unchanged."""

    @property
    def n_in(self) -> int: ...

    @property
    def n_out(self) -> int: ...

    def values(self, inputs: tuple[float, ...]) -> BoxValues: ...

    def jacobian(self, inputs: tuple[float, ...]) -> tuple[tuple[float, ...], ...]: ...


class PropertyBlockBox:
    """A `PropertyBlock` as a black box: values, and its declared-sparse Jacobian made dense.

    A `DomainError` is the block refusing a state outside its stated domain; it becomes
    `TruthRefused("property_domain_error", <block_id>)` with the block's message as detail."""

    def __init__(self, block: PropertyBlock) -> None:
        self.block = block
        self.n_in = len(block.input_ids)
        self.n_out = len(block.output_ids)

    def values(self, inputs: tuple[float, ...]) -> BoxValues:
        try:
            produced = self.block.values(inputs)
        except DomainError as error:
            raise TruthRefused("property_domain_error", self.block.block_id, str(error)) from error
        if len(produced) != self.n_out:
            raise ValueError(
                f"block {self.block.block_id!r} declares {self.n_out} outputs but returned "
                f"{len(produced)}"
            )
        return BoxValues(tuple(float(value) for value in produced))

    def jacobian(self, inputs: tuple[float, ...]) -> tuple[tuple[float, ...], ...]:
        try:
            triples = self.block.jacobian(inputs)
        except DomainError as error:
            raise TruthRefused("property_domain_error", self.block.block_id, str(error)) from error
        dense = [[0.0] * self.n_in for _ in range(self.n_out)]
        for row, column, value in triples:
            dense[row][column] = float(value)
        return tuple(tuple(row) for row in dense)


class TruthModel(Protocol):
    """Design note §6.4: an expensive model of the seven inlet coordinates with two outputs, the
    coupling coordinates (X, ΔT). `evaluate` returns them with §16.4's `meta`
    `{status, cache_hit, experiment_key, executions, extrapolated}`, whose `status` is `ok` for a
    usable result; `gradient` is the 2 × 7 Jacobian. A truth whose `describe()["gradient"]` is
    `finite_difference` has no gradient of its own: its `finite_difference` policy is applied by
    the holder, which requests every point. The adapters live in `truths.py`."""

    def describe(self) -> Mapping[str, Any]: ...

    def evaluate(self, inlet: Sequence[float]) -> tuple[float, float, Mapping[str, Any]]: ...

    def gradient(self, inlet: Sequence[float]) -> Sequence[Sequence[float]]: ...


class TruthBox:
    """A `TruthModel` as a two-output black box. A status other than `ok` is a refusal with that
    status and the truth's `code` as its reason when it gives one (`out_of_domain`,
    `error:external_timed_out`, …), carrying the truth's `meta`.

    `parent` says whether its evaluations are parent experiments, the only ones a parent budget
    counts (§16.4). `finite_difference` is the truth's FD policy when its gradient is
    `finite_difference`, else `None`; the holder then forms the Jacobian from value requests."""

    n_in: Final = 7
    n_out: Final = 2

    def __init__(self, truth: TruthModel) -> None:
        self.truth = truth
        self.identity = dict(truth.describe())
        self.parent = self.identity.get("kind") == PARENT_EXPERIMENT
        self.finite_difference: Any = None
        if self.identity.get("gradient") == "finite_difference":
            self.finite_difference = truth.finite_difference  # type: ignore[attr-defined]
            if self.finite_difference is None:
                raise ValueError(f"truth {self.identity.get('id')!r}: no finite-difference policy")

    def values(self, inputs: tuple[float, ...]) -> BoxValues:
        conversion, rise, meta = self.truth.evaluate(inputs)
        status = str(meta.get("status", "ok"))
        if status != "ok":
            reason = str(meta.get("code") or self.identity.get("id", "truth"))
            raise TruthRefused(status, reason, str(dict(meta)), meta)
        return BoxValues(
            (float(conversion), float(rise)), bool(meta.get("cache_hit", False)), dict(meta)
        )

    def jacobian(self, inputs: tuple[float, ...]) -> tuple[tuple[float, ...], ...]:
        if self.finite_difference is not None:
            raise TypeError(
                f"truth {self.identity.get('id')!r}: its Jacobian is the holder's finite "
                "difference (EFHolder.request_jacobian)"
            )
        matrix = self.truth.gradient(inputs)
        return tuple(tuple(float(value) for value in row) for row in matrix)


def _settle(future: Future[Any]) -> Any:
    """A finished future's result, or the exception it raised (returned, not raised)."""
    error = future.exception()
    return error if error is not None else future.result()


def _call(function: Callable[..., Any], *args: Any) -> Any:
    try:
        return function(*args)
    except Exception as error:  # noqa: BLE001 - returned to the batch, which re-raises it in order
        return error


class _InFlight:
    """A cold evaluation in progress, which a second request at the same key waits for."""

    def __init__(self) -> None:
        self.done = threading.Event()


class EFHolder:
    """One black box behind every `ExternalFunction` of its outputs (design note §6.3).

    `scales[k]` is output k's power-of-two scale s_k: the callbacks return `values[k] / s_k` and
    row k of the Jacobian divided by s_k, and the projection multiplies by s_k again, so the
    scaling is exact in binary64."""

    def __init__(
        self, name: str, box: BlackBox, scales: Sequence[float], *, kind: HolderKind
    ) -> None:
        if len(scales) != box.n_out:
            raise ValueError(f"holder {name!r}: {len(scales)} scales for {box.n_out} outputs")
        self.name = name
        self.box = box
        self.kind = kind
        self.scales = tuple(float(scale) for scale in scales)
        self.n_in = box.n_in
        self.n_out = box.n_out
        self._lock = threading.Lock()
        self._values: dict[bytes, BoxValues | TruthRefused | _InFlight] = {}
        self._jacobians: dict[bytes, tuple[tuple[float, ...], ...] | TruthRefused] = {}
        self._ledger: list[HolderRequest] = []
        self._refusals: list[TruthRefused] = []
        self._run: RunState | None = None
        self._budgets: tuple[ColdBudget, ...] = ()
        self._run_value_keys: set[bytes] = set()

    # -- identity under TRF's clone (probe P2′) -------------------------------------------------

    def __deepcopy__(self, memo: dict[int, Any]) -> EFHolder:
        return self

    def __copy__(self) -> EFHolder:
        return self

    # -- the run --------------------------------------------------------------------------------

    def begin_run(self, run: RunState, budgets: Sequence[ColdBudget] = ()) -> None:
        """Serve one TRF run: attribute requests to it and admit cold ones against `budgets`.

        A truth that is not a parent experiment never counts against a parent budget (§16.4):
        budgets given to its holder are a configuration error."""
        if budgets and not self._charges_budgets:
            raise ValueError(
                f"holder {self.name!r}: truth {self.truth_identity.get('id')!r} is not a parent "
                "experiment and never counts against a parent budget (design note §16.4)"
            )
        with self._lock:
            if self._run is not None:
                raise RuntimeError(f"holder {self.name!r} already serves run {self._run.run_id!r}")
            self._run = run
            self._budgets = tuple(budgets)
            self._run_value_keys = set()

    def end_run(self) -> None:
        with self._lock:
            self._run = None
            self._budgets = ()
            self._run_value_keys = set()

    # -- what Pyomo calls -----------------------------------------------------------------------

    def value_callback(self, output: int) -> Callable[..., float]:
        """The `function=` of output `output`'s `ExternalFunction`: `values[k] / s_k`."""
        scale = self.scales[output]

        def value(*args: float) -> float:
            return self.request_values(args)[output] / scale

        value.__qualname__ = f"{self.name}[{output}].value"
        return value

    def gradient_callback(self, output: int) -> Callable[[Sequence[float], Any], list[float]]:
        """The `gradient=` of output `output`'s `ExternalFunction`: Jacobian row k over s_k, as
        the list Pyomo appends the function-id column to."""
        scale = self.scales[output]

        def gradient(args: Sequence[float], fixed: Any) -> list[float]:
            return [entry / scale for entry in self.request_jacobian(args)[output]]

        gradient.__qualname__ = f"{self.name}[{output}].gradient"
        return gradient

    # -- requests -------------------------------------------------------------------------------

    def request_values(
        self, args: Sequence[float], *, purpose: str | None = None
    ) -> tuple[float, ...]:
        """The box's outputs at the first `n_in` of `args`, from the memo or one evaluation.

        `purpose` labels the request whether it is served cold or from the memo (the
        finite-difference points: `trf_fd_point`, `basis_fd_point`, `fdcheck_point`); without
        one, the first request at a key in a run gets its purpose from TRF's call order, served
        cold or not, and a repeated one gets none (design note §8.3)."""
        outcome, entry = self._values_request(args, purpose)
        with self._lock:
            self._ledger.append(replace(entry, seq=len(self._ledger)))
        return self._unwrap(outcome)

    def request_batch(
        self, points: Sequence[Sequence[float]], *, purpose: str, workers: int
    ) -> tuple[tuple[float, ...], ...]:
        """`request_values` at every point, on up to `workers` threads (§6.5), with the ledger
        entries appended in point order whatever the completion order, so the ledger is the same
        serial or concurrent. Every point is requested before any refusal is raised; the first
        refusal in point order is then raised (any other exception likewise)."""
        if workers > 1 and len(points) > 1:
            with ThreadPoolExecutor(max_workers=min(workers, len(points))) as pool:
                futures = [pool.submit(self._values_request, point, purpose) for point in points]
            settled = [_settle(future) for future in futures]
        else:
            settled = [_call(self._values_request, point, purpose) for point in points]
        with self._lock:
            for result in settled:
                if not isinstance(result, BaseException):
                    self._ledger.append(replace(result[1], seq=len(self._ledger)))
        values = []
        for result in settled:
            if isinstance(result, BaseException):
                raise result
            values.append(self._unwrap(result[0]))
        return tuple(values)

    def request_jacobian(
        self, args: Sequence[float], *, purpose: str | None = None
    ) -> tuple[tuple[float, ...], ...]:
        """The box's dense Jacobian at the first `n_in` of `args`, from the memo or one call.

        A box with a `finite_difference` policy (a parent truth, §6.5) has it formed here: the
        base value (memo, normally), then its seven points through `request_batch`, labelled
        `purpose` (`trf_fd_point` by default; `basis_fd_point` for the affine basis, §6.6)."""
        inputs, key = self._key(args)
        start = time.perf_counter()
        with self._lock:
            held = self._jacobians.get(key)
            if held is not None:
                self._append("jacobian", key, "memo_hit", None, held, start)
                return self._unwrap_jacobian(held)
        outcome: tuple[tuple[float, ...], ...] | TruthRefused
        try:
            policy = getattr(self.box, "finite_difference", None)
            if policy is not None:
                base = self.request_values(inputs)
                points = policy.points(inputs)
                values = self.request_batch(
                    points, purpose=purpose or TRF_FD_POINT, workers=policy.workers
                )
                matrix = policy.quotients(inputs, base, points, values)
            else:
                matrix = self.box.jacobian(inputs)
            if len(matrix) != self.n_out or any(len(row) != self.n_in for row in matrix):
                raise ValueError(
                    f"holder {self.name!r}: the box returned a Jacobian that is not "
                    f"{self.n_out} x {self.n_in}"
                )
            if all(math.isfinite(entry) for row in matrix for entry in row):
                outcome = tuple(tuple(float(entry) for entry in row) for row in matrix)
            else:
                outcome = TruthRefused("non_finite_output", self.name, "jacobian")
        except TruthRefused as refusal:
            outcome = refusal
        with self._lock:
            self._jacobians.setdefault(key, outcome)
            if isinstance(outcome, TruthRefused) and outcome not in self._refusals:
                self._refusals.append(outcome)
            self._append("jacobian", key, "cold", None, outcome, start)
        return self._unwrap_jacobian(outcome)

    def _values_request(
        self, args: Sequence[float], purpose: str | None
    ) -> tuple[BoxValues | TruthRefused, HolderRequest]:
        """One value request, and its ledger entry (unnumbered: the caller appends it)."""
        inputs, key = self._key(args)
        start = time.perf_counter()
        while True:
            with self._lock:
                held = self._values.get(key)
                first_in_run = key not in self._run_value_keys
                if held is None:
                    budgets = self._budgets if self._charges_budgets else ()
                    chosen = purpose
                    if chosen is None and first_in_run:
                        chosen = self._call_order_purpose(self._run)
                    self._run_value_keys.add(key)
                    self._values[key] = flight = _InFlight()
                    break
                if not isinstance(held, _InFlight):
                    chosen = purpose
                    if chosen is None and first_in_run:
                        chosen = self._call_order_purpose(self._run)
                    self._run_value_keys.add(key)
                    return held, self._entry("value", key, "memo_hit", chosen, held, start)
                pending = held
            pending.done.wait()

        exhausted = _admit(budgets)
        if exhausted is not None:
            refusal = TruthRefused(
                "budget", "budget_exhausted", f"{exhausted.name}: cap {exhausted.cap} reached"
            )
            with self._lock:
                del self._values[key]
                if first_in_run:
                    self._run_value_keys.discard(key)
                self._refusals.append(refusal)
            flight.done.set()
            raise refusal

        outcome: BoxValues | TruthRefused
        try:
            outcome = self.box.values(inputs)
            if not all(math.isfinite(value) for value in outcome.values):
                outcome = TruthRefused(
                    "non_finite_output", self.name, "values", getattr(outcome, "meta", None)
                )
        except TruthRefused as refusal:
            outcome = refusal

        with self._lock:
            self._values[key] = outcome
            if isinstance(outcome, TruthRefused):
                self._refusals.append(outcome)
            served: Served = (
                "store_hit" if isinstance(outcome, BoxValues) and outcome.store_hit else "cold"
            )
            entry = self._entry("value", key, served, chosen, outcome, start)
        flight.done.set()
        return outcome, entry

    @property
    def _charges_budgets(self) -> bool:
        """Whether cold requests are admitted against budgets: every box but a truth that is not a
        parent experiment (a property block's budget is the WO-3 mechanism's test, G7)."""
        return not isinstance(self.box, TruthBox) or self.box.parent

    @property
    def truth_identity(self) -> Mapping[str, Any]:
        """The ledger's `truth: {kind, id}` (§8.1): a truth's `describe()`, or the block's."""
        if isinstance(self.box, TruthBox):
            return dict(self.box.identity)
        block = getattr(self.box, "block", None)
        return {"kind": "property_block", "id": getattr(block, "block_id", self.name)}

    # -- what the runner and the record read ----------------------------------------------------

    @property
    def ledger(self) -> tuple[HolderRequest, ...]:
        with self._lock:
            return tuple(self._ledger)

    @property
    def refusals(self) -> tuple[TruthRefused, ...]:
        with self._lock:
            return tuple(self._refusals)

    def summary(self, run_id: str | None = None) -> dict[str, int]:
        """Counts by call and service, over one run or every request (property blocks are
        recorded in aggregate, design note §8.1)."""
        entries = [entry for entry in self.ledger if run_id is None or entry.run_id == run_id]
        counts = {
            f"{call}_{served}": 0
            for call in ("value", "jacobian")
            for served in ("cold", "store_hit", "memo_hit")
        }
        for entry in entries:
            counts[f"{entry.call}_{entry.served}"] += 1
        counts["requests"] = len(entries)
        counts["refused"] = sum(1 for entry in entries if entry.status != "ok")
        return counts

    # -- internals ------------------------------------------------------------------------------

    def _key(self, args: Sequence[float]) -> tuple[tuple[float, ...], bytes]:
        if len(args) < self.n_in:
            raise ValueError(f"holder {self.name!r} takes {self.n_in} inputs, got {len(args)}")
        inputs = tuple(float(value) for value in args[: self.n_in])
        if not all(math.isfinite(value) for value in inputs):
            refusal = TruthRefused("non_finite_input", self.name, repr(inputs))
            with self._lock:
                self._refusals.append(refusal)
            raise refusal
        return inputs, encode_doubles(inputs)

    def _call_order_purpose(self, run: RunState | None) -> str | None:
        """Design note §8.3: before iteration 0 is logged the first key of a run is the start
        value (`EFReplacement`) and any later one the PMP point; after it, a trial point."""
        if run is None:
            return None
        if run.last_logged_iteration is None:
            return TRF_START_VALUE if not self._run_value_keys else TRF_PMP_VALUE
        return TRF_TRIAL_VALUE

    def _entry(
        self,
        call: CallKind,
        key: bytes,
        served: Served,
        purpose: str | None,
        outcome: object,
        start: float,
    ) -> HolderRequest:
        """A ledger entry, unnumbered (`seq` −1 until it is appended)."""
        run = self._run
        meta: Mapping[str, Any] = getattr(outcome, "meta", None) or {}
        return HolderRequest(
            seq=-1,
            run_id=run.run_id if run is not None else None,
            call=call,
            inputs_sha256=hashlib.sha256(key).hexdigest(),
            served=served,
            trf_iteration=run.current_iteration if run is not None else None,
            purpose=purpose,
            status=outcome.code if isinstance(outcome, TruthRefused) else "ok",
            wall_s=time.perf_counter() - start,
            experiment_key=meta.get("experiment_key"),
            executions=0 if served == "memo_hit" else int(meta.get("executions", 0)),
            extrapolated=bool(meta.get("extrapolated", False)),
        )

    def _append(
        self,
        call: CallKind,
        key: bytes,
        served: Served,
        purpose: str | None,
        outcome: object,
        start: float,
    ) -> None:
        entry = self._entry(call, key, served, purpose, outcome, start)
        self._ledger.append(replace(entry, seq=len(self._ledger)))

    @staticmethod
    def _unwrap(outcome: BoxValues | TruthRefused) -> tuple[float, ...]:
        if isinstance(outcome, TruthRefused):
            raise outcome
        return outcome.values

    @staticmethod
    def _unwrap_jacobian(
        outcome: tuple[tuple[float, ...], ...] | TruthRefused,
    ) -> tuple[tuple[float, ...], ...]:
        if isinstance(outcome, TruthRefused):
            raise outcome
        return outcome
