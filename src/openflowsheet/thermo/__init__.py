"""Thermodynamics and property-provider layer: what a provider declares, is asked, and answers.

Owns the capability-based property contract, phase-state formulations, property adapters, the
exact-input cache used on residual/derivative/verification paths, the separate warm-start hint
cache, and the provider conformance kit (blueprint §3 layer table, §6). Exact caches key on
exact canonical inputs and never quantize state coordinates; approximate lookup may only
suggest initial guesses. It must not own solver orchestration or phase-set ownership during a
nonlinear attempt, which belongs to the orchestrator (blueprint §6.3 [A01]).

The contract below is introduced by package K02; the caches and the SYN-001 provider follow in
the same package.

`docs/interfaces-frozen.md` §1 freezes the Protocol and the *names* of its result types; their field
sets are fixed here, by K02, at first use, and are covered by the freeze from that moment. So this
module is a one-shot window in the same way `CompiledProblemMetadata`'s was, and it is written
against what the blueprint already specifies rather than against what seems convenient now.

**What a provider declares** is blueprint §6.1, taken as a checklist: supported components, phases
and state variables; the reference convention; the properties and flashes it offers; derivative
order with respect to *named* inputs; its domain; uncertainty and data provenance; thread safety;
and its numerical limitations. D08 adds the rule that a unit requires the capabilities it uses, not
a universal tier — so `PropertyCapabilities` is a description to be *queried*, never a grade to be
met.

**Three things this module refuses to let a provider do quietly**, each because the alternative is a
plausible wrong number rather than an error:

1. **Answer outside its declared domain.** `PropertyStatus` has no value meaning "extrapolated".
   A request outside the domain is `out_of_domain`, and the caller decides.
2. **Report an accuracy it did not achieve.** A result carries `achieved_accuracy`, and blueprint
   §6.4 forbids a cache entry from satisfying a tighter request than the one it was computed for.
   The field exists so that rule can be enforced rather than assumed.
3. **Return derivatives it does not have.** `derivative_order` is declared per named input, and a
   result that carries no derivative says so. A zero derivative and an absent one are different
   answers, and ADR 0003 D5.4's reasoning applies here for the same reason.

**Zero flow is a first-class answer, not an edge case.** ADR 0001 D3: a stream with `n_tot == 0`
exactly, after signed-zero normalization, is dormant. Its composition is undefined, no property
requiring composition is evaluated, and its phase signature is `ZERO_FLOW`. That is a valid result
and the types below make it expressible without dividing by a total flow anywhere.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from openflowsheet.compiled import EvaluationContext, PhaseSignature

#: What a provider was asked for and whether it could answer. There is deliberately no value
#: meaning "answered by extrapolating beyond the declared domain": blueprint §6.1 makes the domain
#: part of the public contract, so leaving it is reported, never absorbed.
PropertyStatus = Literal["ok", "out_of_domain", "unsupported", "not_converged", "error"]

#: A phase a property may be evaluated in. `ZERO_FLOW` is not a phase and never appears here; it is
#: a property of a *stream*, and appears in `PhaseSignature`.
Phase = Literal["LIQUID", "VAPOR"]


@dataclass(frozen=True)
class PropertyCapabilities:
    """What a provider supports, declared so a unit can require only what it uses (D08).

    Every field is required. A default would let a provider that declares nothing read as
    supporting something, which is the same failure `Capabilities` avoids on the compiled boundary.
    """

    #: Stable identity of the implementation and of its data, separately. Blueprint §6.4 puts both
    #: in the exact cache key: the same code with different parameters is a different provider for
    #: caching purposes, and so is the same data under changed code.
    provider_id: str
    implementation_sha256: str
    data_sha256: str
    #: `SYN-001-ref-v1` for the synthetic package (ADR 0001 D5.1). Enthalpy flows are comparable
    #: only between streams sharing provider implementation, data and reference convention
    #: (D5.2), which is why this is declared rather than assumed.
    reference_convention: str
    #: The state definition the provider speaks, `nTP-v1` (ADR 0001 D2.1).
    state_definition: str
    #: Ordered component ids. The order is part of the identity: a permutation is a different
    #: request, and blueprint §6.4 puts the ordered components in the cache key for that reason.
    components: tuple[str, ...]
    phases: tuple[Phase, ...]
    #: Property ids the provider can evaluate, e.g. `h`, `g`, `lnK`.
    properties: tuple[str, ...]
    #: Flash specifications it supports, e.g. `TP`. v0.0 is TP only; PH is T05 (plan §3.2).
    flashes: tuple[str, ...]
    #: Highest exact derivative order per named input, e.g. `{"T": 1, "P": 1}`. An input absent
    #: here has no declared derivative, which is not the same as a derivative of zero.
    derivative_order: Mapping[str, int]
    #: Inclusive bounds per state variable, e.g. `{"T": (280.0, 440.0)}`. Leaving them is
    #: `out_of_domain`, never an extrapolation.
    domain: Mapping[str, tuple[float, float]]
    #: How uncertain the numbers are and where they came from. Blueprint §6.1 requires both; for a
    #: synthetic package the honest answer names it as synthetic rather than leaving it empty.
    uncertainty: str
    data_provenance: str
    thread_safety: Literal["thread_safe", "not_thread_safe"]
    #: What the provider cannot do, in words a caller can act on.
    numerical_limitations: tuple[str, ...]


@dataclass(frozen=True)
class StreamState:
    """A material stream in the `nTP-v1` state definition (ADR 0001 D2.1).

    `n` is component molar flows in `components` order, mol/s; `T` is absolute temperature in K;
    `P` is pressure in Pa. Nothing derived is stored: total flow, mole fractions, mass flow and
    enthalpy flow are computed, and mole fractions only where the total flow is positive
    (D2.2, D3.2).
    """

    n: tuple[float, ...]
    temperature: float
    pressure: float

    @property
    def total_flow(self) -> float:
        return sum(self.n)

    @property
    def is_dormant(self) -> bool:
        """Exact IEEE zero after signed-zero normalization (ADR 0001 D3.1).

        Exact, not "small": a stream with 1e-30 mol/s of everything has a defined composition and a
        dormant one does not, and a tolerance here would silently move the boundary between them.
        """
        return self.total_flow == 0.0


@dataclass(frozen=True)
class PropertyRequest:
    """Evaluate named properties of one phase at one state.

    The phase is given, not inferred: `evaluate_phase` answers "what is `h` of the liquid at this
    state", and deciding *which* phases exist is `flash`'s job. Keeping them apart is what stops a
    caller receiving a single-phase property for a two-phase state without being told.
    """

    state: StreamState
    phase: Phase
    properties: tuple[str, ...]
    #: Inputs to differentiate with respect to, by name. Empty asks for values only. Asking for an
    #: input the provider did not declare is `unsupported`, not a silently omitted derivative.
    derivatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class PropertyResult:
    """Values, derivatives and the accuracy actually achieved.

    `values` and `derivatives` are keyed by name rather than positional, for the same reason the
    compiled boundary's Jacobian carries row and column ids: a positional result is a permutation
    waiting to happen, and here the permutation would be silent.
    """

    status: PropertyStatus
    phase_signature: PhaseSignature | None
    values: Mapping[str, float]
    #: `{property_id: {input_id: d(property)/d(input)}}`. A property absent from this mapping has
    #: no derivative in this result; it does not have a derivative of zero.
    derivatives: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    #: What accuracy this result actually has. Blueprint §6.4: a cache entry records its achieved
    #: accuracy and cannot satisfy a tighter request without evidence, which needs this recorded.
    achieved_accuracy: str = "exact-double"
    #: Identity of what produced it, for the cache key and for replay.
    provider_id: str = ""
    reference_convention: str = ""
    message: str = ""


@dataclass(frozen=True)
class FlashRequest:
    """Determine the phase split at a state. v0.0 supports `TP` only (plan §3.2)."""

    state: StreamState
    specification: str = "TP"
    derivatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlashResult:
    """The phase split, its outlet streams, and what was actually solved.

    A dormant feed gives two dormant outlets, exactly zero duty and `ZERO_FLOW` — a valid result,
    not a failure (ADR 0001 D3.4). A flash that did not converge says `not_converged` and carries
    what it reached; it never reports an unconverged split as `ok`.
    """

    status: PropertyStatus
    phase_signature: PhaseSignature | None
    #: Vapour fraction on a molar basis, or `None` where it is undefined — a dormant feed, or a
    #: status other than `ok`. Zero and "undefined" are different answers.
    vapor_fraction: float | None
    vapor: StreamState | None
    liquid: StreamState | None
    #: K-values by component id, where the flash computed them.
    k_values: Mapping[str, float] = field(default_factory=dict)
    #: Iterations actually taken, which blueprint §6.4 requires be reported separately rather than
    #: folded into a total cost.
    iterations: int = 0
    achieved_accuracy: str = "exact-double"
    provider_id: str = ""
    reference_convention: str = ""
    message: str = ""


@runtime_checkable
class PropertyProvider(Protocol):
    """Frozen in `docs/interfaces-frozen.md` §1; changes require a Fable-authored ADR.

    The method names and their arity are exactly as frozen. There is no mutable global provider
    (plan §2.1): a provider is an object a unit is given, so two revisions using different
    providers cannot contaminate one another.
    """

    def describe(self) -> PropertyCapabilities: ...

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult: ...

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult: ...
