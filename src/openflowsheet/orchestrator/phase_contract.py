"""The phase-attempt contract, decided in one place. ADR 0005; T03 specification §4–§5.

Both controllers — the tear path's `solve_with_attempts` and the lifted EO path's region solve —
close every attempt through `decide`, and both record candidates through one `WallObserver`. What
differs between the paths is only *what* the controller can say about an attempt's end: who
reports a trial's regime, and the two lifted-only closure conversions. That is the `PathOps`
protocol; the precedence, the restart selection, the restart gate and the message grammar are here
and nowhere else (T03 §4.8: "Neither path keeps its own cycle or budget check").
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final, Literal, Protocol

import numpy as np
import numpy.typing as npt

from openflowsheet.canonical import document_sha256
from openflowsheet.numerics.newton import NewtonResult
from openflowsheet.orchestrator.trace import AttemptSignature, SolveOutcome, SolvePolicy

__all__ = [
    "Candidate",
    "Conversion",
    "Decision",
    "OpeningSource",
    "OpeningState",
    "PathOps",
    "CONTRACT_V2",
    "WallObserver",
    "adjacent",
    "check_opening",
    "decide",
    "format_signature",
    "jacobian_pattern",
    "restart_message",
]

#: ADR 0012 D4's second rule set (T05b spec §6–§7). Its PH-type kernel, unprojected start,
#: records (§6.2–§6.5) and `ZERO_FLOW` regime (§7.1–§7.5) are the region's (`region.py`); the
#: tear path has no lifted split, so its rules there are v1's. `ZERO_FLOW`'s place in the lattice
#: is `adjacent`'s, here.
CONTRACT_V2: Final = "T05b-phase-contract-v2"


#: T03 §4.4: the regime lattice `LIQUID — TWO_PHASE — VAPOR`.
_RANK: Final[Mapping[str, int]] = {"LIQUID": 0, "TWO_PHASE": 1, "VAPOR": 2}

#: T05b spec §7.3 (ADR 0012 D4 (c)): `ZERO_FLOW` is adjacent to each of the three. Only
#: `T05b-phase-contract-v2` puts it in a signature, so v1's lattice is unchanged.
_ZERO_FLOW: Final = "ZERO_FLOW"


def _step(a: str, b: str) -> int:
    """Lattice distance between two regimes: `_RANK`'s, or one step to or from `ZERO_FLOW`."""
    if a == b:
        return 0
    if _ZERO_FLOW in (a, b):
        return 1
    return abs(_RANK[a] - _RANK[b])


OpeningSource = Literal[
    "initializer",
    "phase_rejected_trial",
    "pinned_iterate",
    "closure_projection",
    "merge_best_iterate",
    # ADR 0010 D7.5 (T04 §5.3): recovery edge 3's first attempt, opened at the failed solve's
    # item-0 opening state.
    "eo_recovery_start",
]

#: The six opening checks of T03 §5.1, in the order a refusal names the first that fails.
OPENING_CHECKS: Final[tuple[str, ...]] = (
    "identity",
    "step",
    "scale_segment",
    "coverage",
    "active_set",
    "bounds",
)


def _is_item(unit: str) -> bool:
    """T05b spec §7.8 (i): a dormancy-form item's key is `<U>.<port>`; a unit id never contains
    `.` (the revision reader's R1, since K02's ids use it as a separator)."""
    return "." in unit


def _split(signature: AttemptSignature) -> tuple[AttemptSignature, frozenset[str]]:
    """A signature's unit entries, and the keys of its items (always `ZERO_FLOW`)."""
    units = tuple(entry for entry in signature if not _is_item(entry[0]))
    return units, frozenset(unit for unit, _ in signature if _is_item(unit))


def adjacent(frozen: AttemptSignature, other: AttemptSignature) -> bool:
    """T03 §4.4: every unit equal or one step apart on the lattice, at least one different; the
    lattice with T05b spec §7.3's `ZERO_FLOW` adjacent to every regime.

    T05b spec §7.8 (i): a dormancy-form item `(<U>.<port>, ZERO_FLOW)` is in a signature only
    while its form runs, and its absence (the declared form) and its presence are one step apart.
    The unit entries are judged by T03 §4.4's rule exactly as before; without items (every v1
    signature, every tear signature) nothing else is read."""
    units, items = _split(frozen)
    other_units, other_items = _split(other)
    if [unit for unit, _ in units] != [unit for unit, _ in other_units]:
        return False
    steps = [_step(a, b) for (_, a), (_, b) in zip(units, other_units, strict=True)]
    steps += [1] * len(items ^ other_items)
    return all(step <= 1 for step in steps) and any(step == 1 for step in steps)


def format_signature(signature: AttemptSignature) -> str:
    """`unit:regime,unit:regime` — the grammar of `active_set_cycling(...)` (T03 §4.10)."""
    return ",".join(f"{unit}:{regime}" for unit, regime in signature)


def _changes(
    frozen: AttemptSignature,
    other: AttemptSignature,
    declared: Mapping[str, str] = MappingProxyType({}),
) -> str:
    """`unit:<from>-><to>` for each unit entry that differs, in signature order (T03 §4.10,
    unchanged); then, T05b spec §7.8 (i), each dormancy-form item in one signature only, in
    `declared`'s order (declaration order), its absent side named by its outlet's declared phase:
    `U-PUMP.outlet:LIQUID->ZERO_FLOW`."""
    units, items = _split(frozen)
    other_units, other_items = _split(other)
    changes = [
        f"{unit}:{a}->{b}" for (unit, a), (_, b) in zip(units, other_units, strict=True) if a != b
    ]
    toggled = items ^ other_items
    order = [*(item for item in declared if item in toggled), *sorted(toggled - set(declared))]
    for item in order:
        absent = declared.get(item)
        if absent is None:
            raise ValueError(f"defect: {item} is an item with no declared phase")
        a, b = (_ZERO_FLOW, absent) if item in items else (absent, _ZERO_FLOW)
        changes.append(f"{item}:{a}->{b}")
    return ", ".join(changes)


def jacobian_pattern(
    entries: Sequence[tuple[str, str]], rows: Sequence[str], columns: Sequence[str]
) -> dict[str, Any]:
    """T03 §5.2 / ADR 0005 D5: `{rows, columns, nnz, sha256}` of the structural pattern
    restricted by id to an attempt's rows and columns. `sha256` is ADR 0002's hash of
    `{"rows": [ids], "columns": [ids], "entries": [[i, j], …]}`, positions sorted by `j`
    then `i`."""
    row_at = {name: index for index, name in enumerate(rows)}
    column_at = {name: index for index, name in enumerate(columns)}
    positions = sorted(
        (
            (row_at[row], column_at[column])
            for row, column in entries
            if row in row_at and column in column_at
        ),
        key=lambda entry: (entry[1], entry[0]),
    )
    document = {
        "rows": list(rows),
        "columns": list(columns),
        "entries": [[i, j] for i, j in positions],
    }
    return {
        "rows": len(rows),
        "columns": len(columns),
        "nnz": len(positions),
        "sha256": document_sha256(document),
    }


@dataclass(frozen=True)
class Candidate:
    """A phase-rejected trial of the most recent line search that had one (T03 §4.1)."""

    iteration: int
    halving: int
    alpha: float
    x: npt.NDArray[np.float64]
    signature: AttemptSignature


class WallObserver:
    """K03 §9.3's observer, one class for both paths: the wall iterations, and the candidates.

    The Newton and Anderson cores tell it every rejected trial with its real iteration and step
    length (it never infers them). A trial's *halving index* is its position in its iteration's
    line search, counting every rejection — an `invalid_trial` halves the step like any other.
    """

    def __init__(self, policy: SolvePolicy) -> None:
        self._policy = policy
        self.iterations_with_wall: list[int] = []
        self.candidates: list[Candidate] = []
        self._candidates_iteration = -1
        self._rejections: dict[int, int] = {}

    def rejected(
        self,
        iteration: int,
        alpha: float,
        x: npt.NDArray[np.float64],
        reason: str,
        signature: AttemptSignature | None,
    ) -> None:
        halving = self._rejections.get(iteration, 0)
        self._rejections[iteration] = halving + 1
        if reason != "phase_update_required" or signature is None:
            return
        if iteration != self._candidates_iteration:
            self._candidates_iteration = iteration
            self.candidates = []
        if not self.iterations_with_wall or self.iterations_with_wall[-1] != iteration:
            self.iterations_with_wall.append(iteration)
        self.candidates.append(
            Candidate(iteration, halving, alpha, np.array(x, dtype=np.float64), signature)
        )

    def should_close(self, iteration: int) -> SolveOutcome | None:
        """`phase_wall_patience` consecutive iterations at the wall means it is not an overshoot."""
        patience = self._policy.phase_wall_patience
        recent = self.iterations_with_wall[-patience:]
        if len(recent) == patience and recent == list(range(recent[0], recent[0] + patience)):
            return "PHASE_UPDATE_REQUIRED"
        return None

    def stalled_at_the_wall(self, outcome: SolveOutcome, closing_iteration: int) -> bool:
        """The other K03 §9.3 trigger: a stall with the last wall inside the window. `PTC_STALLED`
        is the PTC core's stall (ADR 0010 D6), counted in pseudo-steps."""
        if outcome not in _STALL_OUTCOMES:
            return False
        if not self.iterations_with_wall:
            return False
        return closing_iteration - self.iterations_with_wall[-1] < self._policy.stagnation_window

    def choose(self, frozen: AttemptSignature) -> Candidate | None:
        """T03 §4.5: the first candidate whose signature is adjacent, else the first."""
        if not self.candidates:
            return None
        for candidate in self.candidates:
            if adjacent(frozen, candidate.signature):
                return candidate
        return self.candidates[0]


@dataclass(frozen=True)
class OpeningState:
    """What an attempt would open from, in the terms the six checks of T03 §5.1 read."""

    values: Mapping[str, float]
    model_version: str
    constants_sha256: str
    step_index: int | None = None
    scale_segment: int = 0
    #: The regime the source reported for the state (tear: the candidate's signature).
    reported: AttemptSignature | None = None


@dataclass(frozen=True)
class OpeningRequirement:
    """What the attempt about to open requires of its opening state."""

    signature: AttemptSignature
    model_version: str
    constants_sha256: str
    free: Sequence[str]
    pinned: Sequence[str] = ()
    lower_bounds: Mapping[str, float] = field(default_factory=dict)
    step_index: int | None = None
    scale_segment: int = 0


@dataclass(frozen=True)
class OpeningRefusal:
    """The first failing opening check (T03 §5.1). `detail` is R0 — the check and the variable or
    field it failed on, never a measured number (§4.10 as amended, review S4); `observed` is the
    number, for the non-R0 records."""

    check: str
    subject: str
    observed: float | None = None

    @property
    def detail(self) -> str:
        return f"{self.check}, {self.subject}"


def check_opening(state: OpeningState, requirement: OpeningRequirement) -> OpeningRefusal | None:
    """T03 §5.1: `None` when all six checks hold; otherwise the first that fails."""
    if state.model_version != requirement.model_version:
        return OpeningRefusal("identity", "model_version")
    if state.constants_sha256 != requirement.constants_sha256:
        return OpeningRefusal("identity", "constants_sha256")
    if state.step_index != requirement.step_index:
        return OpeningRefusal("step", "step_index")
    if state.scale_segment != requirement.scale_segment:
        return OpeningRefusal("scale_segment", "scale_segment")
    for name in requirement.free:
        value = state.values.get(name)
        if value is None or not math.isfinite(value):
            return OpeningRefusal("coverage", name)
    if state.reported is not None and state.reported != requirement.signature:
        return OpeningRefusal("active_set", "reported_signature")
    for name in requirement.pinned:
        value = state.values.get(name)
        if value is None or value != 0.0 or math.copysign(1.0, value) < 0.0:
            return OpeningRefusal("active_set", name, value)
    free = set(requirement.free)
    for name, bound in requirement.lower_bounds.items():
        if name in free and state.values[name] < bound:
            return OpeningRefusal("bounds", name, state.values[name])
    return None


@dataclass(frozen=True)
class Conversion:
    """A proposed restart: the new signature, the opening state, where it came from, and why."""

    signature: AttemptSignature
    opening: Any
    source: OpeningSource
    cause: str
    trial: Candidate | None = None
    #: Measured numbers behind the cause (an admissibility value), for non-R0 records only.
    observations: Mapping[str, float] = field(default_factory=dict)
    #: T05b spec §6.5 (ADR 0012 D10 F2): `(unit, kernel)` for each PH-type split of the opening
    #: that F2's fallback answered — `ph-band` (the PH closure's band route) or `tp` (the TP
    #: flash) — in signature order. Empty under v1, and when every PH closure answered by its
    #: primary route.
    fallbacks: tuple[tuple[str, str], ...] = ()


def restart_message(conversion: Conversion) -> str:
    """`phase_update(<cause>)`; with F2's fallbacks (T05b spec §6.5, no float in the grammar),
    `phase_update(<cause>; fallback(<unit>, <kernel>)[, …])`."""
    if not conversion.fallbacks:
        return f"phase_update({conversion.cause})"
    items = ", ".join(f"fallback({unit}, {kernel})" for unit, kernel in conversion.fallbacks)
    return f"phase_update({conversion.cause}; {items})"


class PathOps(Protocol):
    """What only a path can say about an attempt's end. T03 §4.6–§4.7 on the lifted path."""

    lifted: bool

    def converged(self, result: NewtonResult) -> Conversion | None:
        """§4.7(a): `None` when the converged state is admissible."""
        ...

    def blocked(self, result: NewtonResult) -> Conversion | None:
        """§4.6: a disappearance, when the core ended `BOUND_BLOCKED` on a watched variable."""
        ...

    def kernel_disagrees(self, result: NewtonResult) -> Conversion | None:
        """§4.7(b): the kernel's regime at the end state, when it differs."""
        ...

    def at_candidate(self, candidate: Candidate, cause: str) -> Conversion:
        """§4.5: the opening state at a chosen phase-rejected trial."""
        ...

    def opening_check(self, conversion: Conversion) -> OpeningRefusal | None:
        """§5.1: `None`, or the first failing check."""
        ...


DecisionKind = Literal["converged", "restart", "terminal"]


@dataclass(frozen=True)
class Decision:
    """The controller's verdict on one attempt (T03 §4.8). `message` goes on the next
    `attempt_opened` for a restart, on `solve_closed` for a terminal outcome."""

    kind: DecisionKind
    outcome: SolveOutcome
    message: str
    cause: str = ""
    conversion: Conversion | None = None
    #: The numbers behind the decision (§4.10 as amended): never in `message` or `cause`.
    observations: Mapping[str, float] = field(default_factory=dict)


class OpeningNotSettledError(Exception):
    """T05b spec §7.8 (ii) 2 (ruled 2026-09-25, Q-S9; R-065): an opening whose fixed point over
    the lifted splits' `ZERO_FLOW` membership and the dormancy items still changed something at
    pass `m + 1` — reachable only through a recycle whose dormancy does not settle. A path raises
    it from an opening; `opening_not_settled` turns it into the contract's cycling refusal, so the
    refusal is still produced in this module alone (T03 A02)."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"opening_not_settled({identifier})")
        self.identifier = identifier


def opening_not_settled(error: OpeningNotSettledError) -> Decision:
    """The terminal decision for an opening that does not settle: `ACTIVE_SET_CYCLING`, message
    `opening_not_settled(<id>)` — `<id>` the first split's unit id or item key, in declaration
    order, that pass `m + 1` changed. A typed outcome, never an exception."""
    return Decision("terminal", "ACTIVE_SET_CYCLING", str(error))


#: T03 §4.8 row 4's stalls. ADR 0010 D6 (T04 §7.6) adds the PTC core's failure to advance,
#: `PTC_STALLED`, in the place `LINE_SEARCH_FAILED` holds for Newton; nothing a Newton or Anderson
#: core produces changes path.
_STALL_OUTCOMES: Final = frozenset(
    {"LINE_SEARCH_FAILED", "STAGNATION", "RECYCLE_STAGNATION", "PTC_STALLED"}
)
#: T03 §4.8 row 5 (lifted: the kernel's regime at the end state), with `PTC_STALLED` (ADR 0010 D6).
_KERNEL_OUTCOMES: Final = frozenset(
    {"STAGNATION", "LINE_SEARCH_FAILED", "BOUND_BLOCKED", "PTC_STALLED"}
)
#: Row 5's core budgets: Newton's iterations and, ADR 0010 D6, PTC's pseudo-steps. The property
#: budget is not one — there is nothing left to ask the kernel with.
_KERNEL_BUDGETS: Final = frozenset({"newton_iterations", "ptc_steps"})


def _proposal(
    result: NewtonResult,
    frozen: AttemptSignature,
    wall: WallObserver,
    ops: PathOps,
) -> Conversion | None:
    """The precedence table of T03 §4.8, rows 2–5 (row 1 is the caller's, row 6 is `None`)."""
    # T05b spec §7.8 (i): each dormancy-form item's declared phase, in declaration order, names
    # an item's absence in a cause string. Only the lifted path under v2 has items; an ops without
    # the attribute (the tear path, every v1 attempt) has none.
    declared: Mapping[str, str] = getattr(ops, "declared_phases", MappingProxyType({}))
    if result.outcome == "PHASE_UPDATE_REQUIRED":
        candidate = wall.choose(frozen)
        if candidate is not None:
            return ops.at_candidate(
                candidate,
                f"phase_wall(patience, {_changes(frozen, candidate.signature, declared)})",
            )
    if ops.lifted and result.outcome == "BOUND_BLOCKED":
        blocked = ops.blocked(result)
        if blocked is not None:
            return blocked
    if result.outcome in _STALL_OUTCOMES and wall.stalled_at_the_wall(
        result.outcome, result.iterations
    ):
        candidate = wall.choose(frozen)
        if candidate is not None:
            return ops.at_candidate(
                candidate, f"phase_wall(stall, {_changes(frozen, candidate.signature, declared)})"
            )
    if ops.lifted and (
        result.outcome in _KERNEL_OUTCOMES
        or (result.outcome == "BUDGET_EXHAUSTED" and result.budget in _KERNEL_BUDGETS)
    ):
        return ops.kernel_disagrees(result)
    return None


def decide(
    result: NewtonResult,
    *,
    attempt_index: int,
    frozen: AttemptSignature,
    wall: WallObserver,
    ops: PathOps,
    policy: SolvePolicy,
    used: Sequence[AttemptSignature],
    attempts_run: Callable[[], int] | None = None,
) -> Decision:
    """T03 §4.8: precedence, restart selection and the restart gate, for both paths."""
    if result.converged:
        conversion = ops.converged(result)
        if conversion is None:
            return Decision("converged", "CONVERGED", "")
    else:
        conversion = _proposal(result, frozen, wall, ops)
        if conversion is None:
            return Decision("terminal", result.outcome, result.message)

    # The restart gate, in this order: the budget, cycling, the opening checks.
    ran = attempt_index + 1 if attempts_run is None else attempts_run()
    if ran >= policy.max_attempts:
        return Decision(
            "terminal",
            "ATTEMPTS_EXHAUSTED",
            f"{ran} attempts without convergence, against a policy maximum of "
            f"{policy.max_attempts}",
            cause=conversion.cause,
            conversion=conversion,
            observations=conversion.observations,
        )
    if conversion.signature in used:
        return Decision(
            "terminal",
            "ACTIVE_SET_CYCLING",
            f"active_set_cycling({format_signature(conversion.signature)}; {conversion.cause})",
            cause=conversion.cause,
            conversion=conversion,
            observations=conversion.observations,
        )
    refused = ops.opening_check(conversion)
    if refused is not None:
        observed = (
            {f"{refused.check}:{refused.subject}": refused.observed}
            if refused.observed is not None
            else {}
        )
        return Decision(
            "terminal",
            "CHECKPOINT_INCOMPATIBLE",
            f"checkpoint_incompatible({refused.detail})",
            cause=conversion.cause,
            conversion=conversion,
            observations={**conversion.observations, **observed},
        )
    return Decision(
        "restart",
        "PHASE_UPDATE_REQUIRED",
        restart_message(conversion),
        cause=conversion.cause,
        conversion=conversion,
        observations=conversion.observations,
    )
