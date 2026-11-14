"""The old import path of the solve record, `openflowsheet.numerics.solve_record`.

The record (K03 specification §12) moved to the numerics layer, which produces it (ADR 0076 I-1).
This module only re-exports its public names, so importers outside `numerics` keep this path
until ADR 0076 retargets them.
"""

from __future__ import annotations

from openflowsheet.numerics.solve_record import (
    INTERRUPT_CHECK as INTERRUPT_CHECK,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_ADMISSIBILITY_EPSILON as REGISTERED_ADMISSIBILITY_EPSILON,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_ARMIJO_C as REGISTERED_ARMIJO_C,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_ETA_INNER as REGISTERED_ETA_INNER,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_MAX_ATTEMPTS as REGISTERED_MAX_ATTEMPTS,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_MAX_ITERATIONS as REGISTERED_MAX_ITERATIONS,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_MAX_PROPERTY_CALLS as REGISTERED_MAX_PROPERTY_CALLS,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_PHASE_WALL_PATIENCE as REGISTERED_PHASE_WALL_PATIENCE,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_STAGNATION_RATIO as REGISTERED_STAGNATION_RATIO,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_STAGNATION_WINDOW as REGISTERED_STAGNATION_WINDOW,
)
from openflowsheet.numerics.solve_record import (
    REGISTERED_STEP_HALVINGS_MAX as REGISTERED_STEP_HALVINGS_MAX,
)
from openflowsheet.numerics.solve_record import (
    AttemptSignature as AttemptSignature,
)
from openflowsheet.numerics.solve_record import (
    Checkpoint as Checkpoint,
)
from openflowsheet.numerics.solve_record import (
    Counters as Counters,
)
from openflowsheet.numerics.solve_record import (
    EliminatedRowRecord as EliminatedRowRecord,
)
from openflowsheet.numerics.solve_record import (
    EoRecoveryUnsupported as EoRecoveryUnsupported,
)
from openflowsheet.numerics.solve_record import (
    EventKind as EventKind,
)
from openflowsheet.numerics.solve_record import (
    GlobalizationPolicy as GlobalizationPolicy,
)
from openflowsheet.numerics.solve_record import (
    HomotopyPolicy as HomotopyPolicy,
)
from openflowsheet.numerics.solve_record import (
    LinearRecord as LinearRecord,
)
from openflowsheet.numerics.solve_record import (
    PhaseContract as PhaseContract,
)
from openflowsheet.numerics.solve_record import (
    PtcPolicy as PtcPolicy,
)
from openflowsheet.numerics.solve_record import (
    RecycleMethod as RecycleMethod,
)
from openflowsheet.numerics.solve_record import (
    RecyclePolicy as RecyclePolicy,
)
from openflowsheet.numerics.solve_record import (
    RejectionReason as RejectionReason,
)
from openflowsheet.numerics.solve_record import (
    SolveEvent as SolveEvent,
)
from openflowsheet.numerics.solve_record import (
    SolveOutcome as SolveOutcome,
)
from openflowsheet.numerics.solve_record import (
    SolvePlan as SolvePlan,
)
from openflowsheet.numerics.solve_record import (
    SolvePolicy as SolvePolicy,
)
from openflowsheet.numerics.solve_record import (
    Trace as Trace,
)
from openflowsheet.numerics.solve_record import (
    fraction_string as fraction_string,
)
