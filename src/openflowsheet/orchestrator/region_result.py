"""The region solve's records (T03 §8, T04 §5.3, OPT design §4.2.1).

`RegionAttempt` (one attempt: its signature, outcome and iterations, why it closed, what Newton
ended on, its PTC record), `AttemptSystem` (the converged attempt's square system),
`RegionResult` (what `solve_region` returns) and `RecoveryStart` (recovery edge 3's start).

Split from `orchestrator.region` (S19 RS), which re-exports all four. This module reaches no other
module of the region solver.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from openflowsheet.models.lifted import Regime
from openflowsheet.numerics.ptc import PtcRecord
from openflowsheet.orchestrator.attempts import AttemptContext
from openflowsheet.orchestrator.homotopy import Continuation, HomotopyRecord
from openflowsheet.orchestrator.trace import AttemptSignature, Checkpoint, Counters, SolveOutcome


@dataclass(frozen=True)
class RegionAttempt:
    signature: AttemptSignature
    outcome: SolveOutcome
    iterations: int
    #: Why the attempt closed into the next one, in §9's registered grammar, or "".
    reason: str = ""
    #: What Newton itself ended on, before §6.3 converted it (A31: `STAGNATION` read as a
    #: disagreement with the kernel), and the iterate it ended at, before any pin or projection.
    solver_outcome: SolveOutcome | None = None
    end_state: Mapping[str, float] = field(default_factory=dict)
    #: The numbers behind `reason` or the terminal message — an admissibility value, the offending
    #: value of a refused opening — kept here because the strings are R0 (review S4).
    observations: Mapping[str, float] = field(default_factory=dict)
    #: T04 §7.8: a PTC attempt's pseudo-steps, rejections, SER state and polish. In memory only.
    ptc: PtcRecord | None = None


@dataclass(frozen=True)
class AttemptSystem:
    """OPT design §4.2.1: the converged attempt's square system — exactly the arguments it passed
    to `_region_problem` (`rows`, `free`, `labels`) and the values it held (every column of the
    problem that is not free, at the value the attempt held it at), under its `signature`. In
    memory only, never serialised (like `RegionResult.opening`)."""

    rows: tuple[str, ...]
    free: tuple[str, ...]
    held: Mapping[str, float]
    labels: tuple[tuple[str, str, str], ...]
    signature: AttemptSignature


@dataclass(frozen=True)
class RegionResult:
    outcome: SolveOutcome
    state: Mapping[str, float]
    attempts: tuple[RegionAttempt, ...]
    #: Streams whose supplied split disagreed with the kernel and was overwritten (§6.2).
    projections: tuple[str, ...] = ()
    counters: Counters = field(default_factory=Counters)
    message: str = ""
    #: K03 §12.5's checkpoint of the last attempt that accepted a step or converged:
    #: `candidate_root` only when the solve converged, `partial` otherwise (A30).
    checkpoint: Checkpoint | None = None
    #: One context per attempt, with the active phase set it solved under (ADR 0009 D4).
    contexts: tuple[AttemptContext, ...] = ()
    #: ADR 0005 D7 (T03 §8.1): one item per attempt — the attempt history and its start.
    branch_provenance: tuple[Mapping[str, Any], ...] = ()
    #: ADR 0005 D7 (T03 §8.2): issued on a `CONVERGED`, admissible solve, `None` otherwise.
    root_fingerprint: Mapping[str, Any] | None = None
    #: Attempt 0's opening: the full state (after §6.2's projection and the attempt's pins) and
    #: the regimes it opened under — what recovery edge 3 starts from (T04 §5.3). In memory only.
    opening: tuple[Mapping[str, float], Mapping[str, Regime]] | None = None
    #: On `BUDGET_EXHAUSTED`: which budget — the core's (`newton_iterations`, `homotopy_steps`) or
    #: `property_calls` — because edge 3's trigger set tells them apart (T04 §5.1).
    budget: str | None = None
    #: T04 §4.7: the homotopy's record, when attempt 0 ran the homotopy core.
    homotopy: HomotopyRecord | None = None
    #: OPT design §4.2.1: the converged attempt's system, set iff the region returns `CONVERGED`.
    #: In memory only, never serialised.
    final_system: AttemptSystem | None = None

    @property
    def iterations(self) -> int:
        return sum(attempt.iterations for attempt in self.attempts)

    @property
    def signatures(self) -> tuple[AttemptSignature, ...]:
        return tuple(attempt.signature for attempt in self.attempts)


@dataclass(frozen=True)
class RecoveryStart:
    """Recovery edge 3's start (T04 §5.3): the failed solve's item-0 opening state and signature,
    the region's continuation parameter, and item 0's initializer source. The recovery region
    solve's attempt 0 runs the homotopy core from here, with a fresh contract state."""

    state: Mapping[str, float]
    regimes: Mapping[str, Regime]
    continuation: Continuation
    initializer_source: str | None
    #: RRC design note §5.7 (ADR 0072): the signature the source reported for `state` — a
    #: revision continuation's ancestor certificate's final signature. `None` is T04's recovery
    #: from the failed solve's own opening, which is not checked. With a value, attempt 0's
    #: opening is held to T03 §5.1's checks (`check_opening`) against it before the homotopy.
    reported_signature: AttemptSignature | None = None
