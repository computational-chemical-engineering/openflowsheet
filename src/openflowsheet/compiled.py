"""The `CompiledProblem` boundary, introduced by P02 (`docs/interfaces-frozen.md` §1).

The frozen document says the Protocol objects are introduced in code by the package that first
needs each one, and that they must match it verbatim. The method names, their arity and their
return-type names are therefore exactly as frozen. The parameter *annotations* come from the
binding semantics attached to the same section: `x` is a dense NumPy vector of the ordered free
variables, and the context pins model and data versions, the phase signature, the accuracy policy
and the run-local workspace.

P02 uses these types to describe what its two harnesses expose. The executable objects live in the
backend environments under `spikes/p02/`; only the metadata is canonical and serializable, and a
missing capability is reported as absent, never replaced with zeros.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

StateVector = npt.NDArray[np.float64]

EvaluationStatus = Literal["ok", "invalid_trial_state", "unsupported", "error"]
PhaseSignature = Literal["LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW"]
CapabilityLevel = Literal["exact", "absent"]
JacobianCapability = Literal["exact_sparse_csc", "absent"]
PatternProvenance = Literal["backend-declared", "thresholded"]
#: How a row's conservation content accumulates, by equation id (ADR 0008 D3, promoted by K01 per
#: D4.4). `absent` is for a row whose accumulation genuinely cannot be known — one produced by an
#: opaque evaluator. A row the compiler itself authors, such as a tear or a specification-promotion
#: row, is *not* `absent`: K01 wrote it and must declare it `algebraic`.
RowAccumulation = Literal["algebraic", "zero_holdup_balance", "holdup_balance", "absent"]


@dataclass(frozen=True)
class EvaluationContext:
    """Pins model and data versions, phase signature, accuracy policy and workspace.

    The outer active-set controller constructs a new context after a phase restart; a
    `JacobianResult` is valid only for the same context as its residual.

    Time is not a coordinate of this boundary (ADR 0008 D1). No field here carries physical
    time, pseudo-time, a step or a state history, and none may be added without a new ADR:
    `tests/test_adr_0008_transient_readiness.py` pins this field set. A time-varying boundary
    specification reaches the compiled problem as a pinned input evaluated by the orchestrator
    and identified by (`model_version`, `constants_sha256`). `workspace` holds run-local work
    buffers only; the evaluated function never depends on its contents.
    """

    model_version: str
    constants_sha256: str
    phase_signature: PhaseSignature | None = None
    accuracy_policy: str = "exact-double"
    workspace: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Capabilities:
    """Negotiated optional capabilities. A missing exact Hessian is `absent`, never zeros.

    Every field is required. A default of `"exact_sparse_csc"` would mean a backend that declares
    nothing is treated as exact, which is a placeholder success path in the boundary type itself.
    """

    jacobian: JacobianCapability
    jvp: CapabilityLevel
    vjp: CapabilityLevel
    hessian: CapabilityLevel


@dataclass(frozen=True)
class CompiledProblemMetadata:
    """Typed, immutable, serializable metadata. Executable objects stay runtime-local.

    `parameter_ids` and `row_accumulation` were added by K01 at schema promotion, which is the
    window ADR 0008 D4.1 and D4.4 name; adding either afterwards would have been a migration
    (ADR 0008 Q2). Both are required and neither has a default, for the reason `Capabilities`
    gives: a default would let a compiler that declares nothing be read as having declared
    something.
    """

    model_version: str
    backend: str
    backend_version: str
    variable_ids: tuple[str, ...]
    equation_ids: tuple[str, ...]
    #: The order in which `constants_sha256` hashes the pinned-input vector (ADR 0008 D4.1).
    #: `model_version` identifies equation structure and backend form only, so two instances that
    #: differ solely in specification values share it and are told apart here.
    parameter_ids: tuple[str, ...]
    column_scales: Mapping[str, float]
    row_scales: Mapping[str, float]
    #: One entry per `equation_ids` member, copied from the contributing manifests (ADR 0008 D4.4).
    #: T04 reads it to place the nonzero entries of the PTC mass matrix `M`, which is why a missing
    #: or guessed entry here becomes a wrong `M` there rather than a visible error.
    row_accumulation: Mapping[str, RowAccumulation]
    capabilities: Capabilities
    constants_sha256: str


@dataclass(frozen=True)
class EvaluationResult:
    """Status, phase signature, state and model identity, accuracy and evaluation counters."""

    status: EvaluationStatus
    values: tuple[float, ...] | None
    equation_ids: tuple[str, ...]
    phase_signature: PhaseSignature | None
    model_version: str
    constants_sha256: str
    #: Hash of exactly the dense `x` as passed, in `variable_ids` order, after signed-zero
    #: normalization, and nothing else (ADR 0008 D2). Encoding is ADR 0002's.
    state_sha256: str
    counters: Mapping[str, Mapping[str, int]]
    accuracy: str = "exact-double"
    message: str = ""


@dataclass(frozen=True)
class JacobianResult:
    """A sparse Jacobian in documented CSC ordering with explicit row and column identity.

    Valid only for the same state, model version, phase regime and evaluation policy as the
    residual it accompanies.
    """

    status: EvaluationStatus
    row_ids: tuple[str, ...]
    col_ids: tuple[str, ...]
    indptr: tuple[int, ...]
    indices: tuple[int, ...]
    data: tuple[float, ...]
    phase_signature: PhaseSignature | None
    model_version: str
    constants_sha256: str
    #: Hash of exactly the dense `x` as passed, in `variable_ids` order, after signed-zero
    #: normalization, and nothing else (ADR 0008 D2). Encoding is ADR 0002's.
    state_sha256: str
    counters: Mapping[str, Mapping[str, int]]
    #: Required: a default of `"backend-declared"` would let a thresholded pattern pass as declared.
    pattern_provenance: PatternProvenance
    source_map: Sequence[Mapping[str, Any]] = ()
    format: str = "csc"
    message: str = ""

    @property
    def nnz(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class ProcessState:
    """The reconstructed process state. P02 reconstructs variables only."""

    variables: Mapping[str, float]
    phase_signature: PhaseSignature | None = None


@runtime_checkable
class CompiledProblem(Protocol):
    """Frozen in `docs/interfaces-frozen.md` §1; changes require a Fable-authored ADR."""

    metadata: CompiledProblemMetadata

    def residual(self, x: StateVector, context: EvaluationContext) -> EvaluationResult: ...

    def jacobian(self, x: StateVector, context: EvaluationContext) -> JacobianResult: ...

    def reconstruct(self, x: StateVector, context: EvaluationContext) -> ProcessState: ...
