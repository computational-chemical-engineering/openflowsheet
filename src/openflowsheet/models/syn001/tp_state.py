"""The TP-state kernel the heater and the flash share (plan §4.2 K02).

Both units answer the same question — "what is this set of component flows at this temperature
and pressure, and what enthalpy does it carry?" — and differ only in what they do with the
answer. The flash publishes the two phases as separate outlet streams; the heater keeps them
inside itself and reports only the duty. Sharing the kernel is a requirement, not a convenience:
"heater and flash share one TP-state kernel (§3.2)".

**What the kernel does not do.** It does not choose a phase regime by itself and then hide the
choice — it reports what the provider's flash returned, including `ZERO_FLOW` for a dormant feed
(ADR 0001 D3.4) and a dormant outlet for `V = 0` or `L = 0`. It does not extrapolate: a state
outside the provider's declared domain comes back `out_of_domain` with the provider's message.
And it does not convert a failure into an answer: every non-`ok` status carries no enthalpy and
no streams.

**Enthalpy of a dormant phase is exactly zero, and is not asked for.** ADR 0001 D3.1 says a
dormant stream's enthalpy flow *is* exactly `0`, and that no property requiring composition is
evaluated for it. SYN-001's enthalpies happen not to require composition, so calling the provider
would be harmless here and wrong in general; the kernel skips the call.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from openflowsheet.compile.spec import EquationSpec, PropertyBlock, QuantityKind
from openflowsheet.compiled import EvaluationContext, PhaseSignature
from openflowsheet.models import (
    Contribution,
    SpecificationError,
    flow_id,
    origin,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.rows import balance_row, definition_row, equilibrium_row
from openflowsheet.models.syn001 import TEMPERATURE_TOLERANCE
from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock, LnKBlock
from openflowsheet.models.syn001.saturation_band import (
    BandError,
    degeneracy_distance,
    is_temperature_degenerate,
    outside_the_degeneracy_window,
)
from openflowsheet.thermo import (
    FlashRequest,
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyStatus,
    StreamState,
)


@dataclass(frozen=True)
class TPState:
    """A stream's phase split at a specified (T, P), and the enthalpy flow that goes with it.

    On any status other than `ok`, every value field is `None` or empty. A partial answer here
    would travel straight into a duty.
    """

    status: PropertyStatus
    phase_signature: PhaseSignature | None = None
    vapor: StreamState | None = None
    liquid: StreamState | None = None
    vapor_fraction: float | None = None
    #: Total enthalpy flow of both phases, W, in the provider's reference convention.
    enthalpy_flow: float | None = None
    k_values: Mapping[str, float] = field(default_factory=dict)
    iterations: int = 0
    provider_id: str = ""
    reference_convention: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if self.status != "ok" and (
            self.vapor is not None or self.liquid is not None or self.enthalpy_flow is not None
        ):
            raise ValueError(
                f"TPState status {self.status!r} carries a split or an enthalpy; a failed kernel "
                "reports why and nothing a duty could be computed from"
            )


def enthalpy_flow(
    provider: PropertyProvider,
    state: StreamState,
    phase: Phase,
    components: tuple[str, ...],
    context: EvaluationContext,
) -> tuple[PropertyStatus, float, str]:
    """`Sum_i n_i h_i^phase(T, P)` for one single-phase stream, W.

    A dormant stream contributes exactly `0.0` and the provider is not called (ADR 0001 D3.1).
    """
    if state.is_dormant:
        return "ok", 0.0, ""
    result = provider.evaluate_phase(
        PropertyRequest(state=state, phase=phase, properties=("h",)), context
    )
    if result.status != "ok":
        return result.status, 0.0, result.message
    total = 0.0
    for component, flow in zip(components, state.n, strict=True):
        total += flow * result.values[f"h_{component}"]
    return "ok", total, ""


def single_phase_admissible(
    provider: PropertyProvider,
    state: StreamState,
    phase: Phase,
    components: tuple[str, ...],
    context: EvaluationContext,
) -> tuple[bool, float, float, PropertyStatus, str]:
    """May this stream's enthalpy be written as if it were entirely in `phase`?

    Returns `(admissible, single_phase_enthalpy, equivalent_temperature_error, status, message)`.

    **The criterion is intensive, and that is the whole point.** The obvious test — compare the
    single-phase enthalpy against the true TP-state enthalpy and demand the gap be below the
    registered *energy* tolerance — is a bound in watts on a question about a state. It passes
    whenever the throughput is small enough, and a mixer built that way admits a 45%-vapour
    stream at 1e-8 mol/s and reports an outlet 64 K too cold with status `ok`. That was measured
    on the first version of this code, and it is exactly the plausible wrong number this
    repository exists to refuse.

    So the enthalpy gap is converted into the temperature error it would cause, by dividing by
    the slope `dH/dT` the closure already has to query, and compared against ADR 0001 D6's
    registered **temperature** tolerance. Only registered constants appear, the test scales with
    throughput because the slope does, and it bounds the thing a caller actually sees.

    At the registered states: the saturated SYN-001 recycle passes by nine orders of magnitude,
    and an equimolar feed at 347.45 K — 0.009 K above its bubble point — is refused.

    **A temperature-degenerate stream is admitted in either phase** (T05b spec §10, ADR 0012
    D8). When both its bubble and dew temperatures lie within `1e-6 K` of its temperature
    (`saturation_band.degeneracy_distance`, spec §4.4) — pure B at `T_sat`, or a trace narrower
    than the tolerance — every vapour fraction is consistent with its `(n, T, P)`, so this layer,
    which sees nothing else, cannot say which phase it was produced in; the certificate, which
    knows the assigned phase, decides (spec §9.1). The reported gap is then the degeneracy
    distance. Only the refusal path runs the test, so an admitted stream is answered exactly as
    before; a band search the provider refuses leaves the refusal standing (nothing is admitted
    on a test that did not complete). Two sign tests of `g` at `T ∓ 2 τ_T` come first
    (`saturation_band.outside_the_degeneracy_window`, T05b W6): they refuse a stream that
    certainly is not degenerate for 2 `lnK` calls instead of the bisections' ~100, and decide
    nothing otherwise, so every verdict is the band test's.
    """
    if state.is_dormant:
        # ADR 0001 D3.1: no property is evaluated and the enthalpy flow is exactly zero, so the
        # question does not arise. A dormant stream is in no phase at all. This is *not* the
        # trivial root discussed below -- that one has a flowing stream with a vanished phase.
        return True, 0.0, 0.0, "ok", ""

    single = provider.evaluate_phase(
        PropertyRequest(state=state, phase=phase, properties=("h",), derivatives=("T",)),
        context,
    )
    if single.status != "ok":
        return False, 0.0, 0.0, single.status, single.message

    enthalpy = 0.0
    slope = 0.0
    for component, flow in zip(components, state.n, strict=True):
        enthalpy += flow * single.values[f"h_{component}"]
        slope += flow * single.derivatives[f"h_{component}"]["T"]

    true_state = tp_state(provider, state, context)
    if true_state.status != "ok":
        return False, 0.0, 0.0, true_state.status, true_state.message
    assert true_state.enthalpy_flow is not None

    gap = abs(true_state.enthalpy_flow - enthalpy)
    if not slope > 0.0:
        # No slope means no way to express the gap as a temperature, so the question cannot be
        # answered rather than being answered permissively.
        return (
            gap == 0.0,
            enthalpy,
            0.0,
            "ok",
            "" if gap == 0.0 else f"d(H)/dT is {slope}, so the gap cannot be judged",
        )
    equivalent = gap / slope
    if equivalent <= TEMPERATURE_TOLERANCE:
        return True, enthalpy, equivalent, "ok", ""
    if outside_the_degeneracy_window(provider, state.n, state.temperature, state.pressure, context):
        return False, enthalpy, equivalent, "ok", ""
    try:
        distance = degeneracy_distance(
            provider, state.n, state.temperature, state.pressure, context
        )
    except BandError:
        return False, enthalpy, equivalent, "ok", ""
    if is_temperature_degenerate(distance):
        return True, enthalpy, distance, "ok", ""
    return False, enthalpy, equivalent, "ok", ""


def tp_state(
    provider: PropertyProvider,
    feed: StreamState,
    context: EvaluationContext,
    *,
    temperature: float | None = None,
    pressure: float | None = None,
) -> TPState:
    """Flash `feed`'s component flows at the specified (T, P) and total the enthalpy.

    `temperature` and `pressure` default to the feed's own, which is how a unit asks "what state
    is this stream already in?" — the heater needs that for its inlet and the flash for its feed.
    """
    capabilities = provider.describe()
    components = capabilities.components
    if len(feed.n) != len(components):
        raise ValueError(
            f"stream carries {len(feed.n)} component flows; the provider declares "
            f"{len(components)}: {components}"
        )
    target = StreamState(
        n=feed.n,
        temperature=feed.temperature if temperature is None else float(temperature),
        pressure=feed.pressure if pressure is None else float(pressure),
    )

    flashed = provider.flash(FlashRequest(state=target, specification="TP"), context)
    if flashed.status != "ok":
        return TPState(
            status=flashed.status,
            provider_id=flashed.provider_id,
            reference_convention=flashed.reference_convention,
            message=flashed.message,
        )
    if flashed.vapor is None or flashed.liquid is None:
        raise ValueError(
            "the provider reported an ok TP flash without both outlet streams; "
            "ADR 0001 D3.4 requires two, either of which may be dormant"
        )

    total = 0.0
    phases: tuple[tuple[Phase, StreamState], ...] = (
        ("VAPOR", flashed.vapor),
        ("LIQUID", flashed.liquid),
    )
    for phase, stream in phases:
        status, contribution, message = enthalpy_flow(provider, stream, phase, components, context)
        if status != "ok":
            return TPState(
                status=status,
                provider_id=flashed.provider_id,
                reference_convention=flashed.reference_convention,
                message=f"{phase.lower()} enthalpy: {message}",
            )
        total += contribution

    return TPState(
        status="ok",
        phase_signature=flashed.phase_signature,
        vapor=flashed.vapor,
        liquid=flashed.liquid,
        vapor_fraction=flashed.vapor_fraction,
        enthalpy_flow=total,
        k_values=flashed.k_values,
        iterations=flashed.iterations,
        provider_id=flashed.provider_id,
        reference_convention=flashed.reference_convention,
        message=flashed.message,
    )


# ------------------------------------------------------ the kernel's equation-oriented face
#
# The procedural kernel above answers "what is this stream". The rows below say the same thing to
# a solver, and they follow the formulation Fable fixed for P02 in
# `docs/derivations/P02-composition-spec.md` (rows `bal_i`, `Vdef`, `Ldef`, `eq_i`): the
# phase split is *lifted* into variables `v_i`, `l_i`, `V`, `L`, and equilibrium is written
# `v_i L - K_i l_i V = 0`.
#
# Two properties of that form are the reason it is used rather than a mole-fraction form. It never
# divides by a total flow, which ADR 0001 D3.2 forbids; and it is exact at a zero component and at
# a zero phase, because every term is a product of flows. The alternative — an opaque block that
# runs an inner Rachford-Rice solve and returns an implicit derivative (blueprint §5.1) — would put
# a Newton solve inside every residual evaluation and a one-sided derivative at the phase boundary.
#
# WHAT THE FORM DOES NOT DO, AND WHICH K03 INHERITS
# -------------------------------------------------
# `v_i L - K_i l_i V` is satisfied identically when every `v_i` is zero (so `V = 0`) and when every
# `l_i` is zero (so `L = 0`), whatever the feed and whatever the K-values. These are the classical
# trivial solutions of the flash equations and they are *exact* roots of the lifted block, not
# near-roots: at the once-through variant's genuinely two-phase heater outlet, forcing the
# all-liquid split leaves thirteen of the heater's fourteen rows at exactly 0.0, and the fourteenth
# is the duty row, which a solver free to choose `Q` closes at a duty 8237.85 W below the true one.
# Measured, and registered as `tests/test_k02_flowsheet.py::
# test_the_lifted_equilibrium_admits_a_trivial_root_that_k03_must_reject`.
#
# Nothing in a residual can exclude them, because they satisfy it. Excluding them is a job for the
# things blueprint §6.3 and §7.1 name: an initialization that starts on the physical branch, and a
# final phase-admissibility check on the converged answer. Both are K03's. K02's obligation is to
# state the hazard where the next reader of this formulation will meet it, rather than to leave it
# to be rediscovered from a wrong duty.
#
# `energy` in the P02 spec is written outflow minus inflow. ADR 0008 D3.3 later reversed the
# orientation of every balance row, and the manifests are written in the new one. The manifest
# statement is what these rows implement.


def vapor_flow_id(stream: str, component: str) -> str:
    """The lifted vapour component flow of a stream whose declared regime is two-phase."""
    return f"{stream}.vap.{component}"


def liquid_flow_id(stream: str, component: str) -> str:
    return f"{stream}.liq.{component}"


def vapor_total_id(stream: str) -> str:
    return f"{stream}.V"


def liquid_total_id(stream: str) -> str:
    return f"{stream}.L"


#: CasADi names a `Callback` with the block id, and it accepts only a letter followed by letters,
#: digits and non-consecutive underscores. Sanitizing silently would let two stream ids collapse
#: onto one block, so an unusable stream id is refused instead.
_BLOCK_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*$")


def _token(stream: str) -> str:
    if not _BLOCK_TOKEN.match(stream):
        raise SpecificationError(
            f"stream id {stream!r} cannot name a property block. The backend accepts a letter "
            "followed by letters, digits and non-consecutive underscores; sanitizing it here "
            "could quietly map two streams onto one block"
        )
    return stream


def enthalpy_block_id(stream: str, phase: Phase) -> str:
    """One block per (stream, phase). Two units reading the same stream name the same block."""
    return f"H_{_token(stream)}_{phase.lower()}"


def lnk_block_id(stream: str) -> str:
    return f"lnK_{_token(stream)}"


def single_phase_enthalpy(
    provider: PropertyProvider,
    components: tuple[str, ...],
    context: EvaluationContext,
    stream: str,
    phase: Phase,
) -> tuple[PropertyBlock, tuple[str, ...], tuple[str, ...]]:
    """An enthalpy block for a stream in one declared phase, and the keys a row sums.

    Returns `(block, feeding_variable_ids, output_keys)`.
    """
    block = EnthalpyFlowBlock(
        provider, components, phase, context, block_id=enthalpy_block_id(stream, phase)
    )
    feeding = (
        *(flow_id(stream, name) for name in components),
        temperature_id(stream),
        pressure_id(stream),
    )
    keys = tuple(f"{block.block_id}.{output}" for output in block.output_ids)
    return block, feeding, keys


def lift_two_phase_stream(
    *,
    unit_id: str,
    model_id: str,
    equilibrium_equation_id: str,
    stream: str,
    provider: PropertyProvider,
    components: tuple[str, ...],
    context: EvaluationContext,
) -> tuple[Contribution, tuple[str, ...]]:
    """Give a two-phase stream its lifted split, and return the enthalpy keys a duty row sums.

    Authored by the unit that *produces* the stream, once. A unit that merely reads the stream
    refers to the same variables and the same block ids, so the split is a property of the stream
    and not of whoever looked at it.

    Rows authored here: the equilibrium relation (declared by the model's manifest, passed in as
    `equilibrium_equation_id`) and five lifting rows the unit authors itself — three phase splits
    and two total definitions. ADR 0008 D4.4 requires a self-authored row to be declared
    `algebraic` explicitly, which is what they are: they define variables, they conserve nothing.
    """
    vapor_ids = tuple(vapor_flow_id(stream, name) for name in components)
    liquid_ids = tuple(liquid_flow_id(stream, name) for name in components)
    total_vapor, total_liquid = vapor_total_id(stream), liquid_total_id(stream)

    lnk = LnKBlock(provider, components, context, block_id=lnk_block_id(stream))
    vapor_block = EnthalpyFlowBlock(
        provider, components, "VAPOR", context, block_id=enthalpy_block_id(stream, "VAPOR")
    )
    liquid_block = EnthalpyFlowBlock(
        provider, components, "LIQUID", context, block_id=enthalpy_block_id(stream, "LIQUID")
    )

    equations: list[EquationSpec] = []
    for index, component in enumerate(components):
        equations.append(
            EquationSpec(
                equation_id=row_id(unit_id, equilibrium_equation_id, component),
                build=equilibrium_row(
                    vapor_ids[index],
                    liquid_ids[index],
                    total_vapor,
                    total_liquid,
                    f"{lnk.block_id}.lnK_{component}",
                ),
                accumulation="algebraic",
                origin=origin(model_id, equilibrium_equation_id),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(unit_id, "split", component),
                build=balance_row(
                    (vapor_ids[index], liquid_ids[index]), (flow_id(stream, component),)
                ),
                accumulation="algebraic",
                origin=origin(model_id, "lifting"),
            )
        )
    equations.append(
        EquationSpec(
            equation_id=row_id(unit_id, "Vdef"),
            build=definition_row(total_vapor, vapor_ids),
            accumulation="algebraic",
            origin=origin(model_id, "lifting"),
        )
    )
    equations.append(
        EquationSpec(
            equation_id=row_id(unit_id, "Ldef"),
            build=definition_row(total_liquid, liquid_ids),
            accumulation="algebraic",
            origin=origin(model_id, "lifting"),
        )
    )

    kinds: dict[str, QuantityKind] = {}
    for index, component in enumerate(components):
        kinds[row_id(unit_id, equilibrium_equation_id, component)] = "molar_flow_squared"
        kinds[row_id(unit_id, "split", component)] = "molar_flow"
        kinds[vapor_ids[index]] = "molar_flow"
        kinds[liquid_ids[index]] = "molar_flow"
    kinds[row_id(unit_id, "Vdef")] = "molar_flow"
    kinds[row_id(unit_id, "Ldef")] = "molar_flow"
    kinds[total_vapor] = "molar_flow"
    kinds[total_liquid] = "molar_flow"
    lifted_variables = (*vapor_ids, *liquid_ids, total_vapor, total_liquid)

    contribution = Contribution(
        variable_ids=lifted_variables,
        equations=tuple(equations),
        variable_kinds={name: kinds[name] for name in lifted_variables},
        row_kinds={name: kind for name, kind in kinds.items() if name not in set(lifted_variables)},
        blocks=(lnk, vapor_block, liquid_block),
        block_inputs={
            lnk.block_id: (temperature_id(stream), pressure_id(stream)),
            vapor_block.block_id: (*vapor_ids, temperature_id(stream), pressure_id(stream)),
            liquid_block.block_id: (*liquid_ids, temperature_id(stream), pressure_id(stream)),
        },
    )
    keys = tuple(
        f"{block.block_id}.{output}"
        for block in (vapor_block, liquid_block)
        for output in block.output_ids
    )
    return contribution, keys


def stream_enthalpy_terms(
    provider: PropertyProvider,
    components: tuple[str, ...],
    context: EvaluationContext,
    stream: str,
    phase: Phase | None,
) -> tuple[tuple[str, ...], tuple[PropertyBlock, ...], dict[str, tuple[str, ...]]]:
    """The block outputs whose sum is a stream's `Hdot`, as a unit reading the stream writes it.

    Returns `(keys, blocks, block_inputs)`. A declared phase is `single_phase_enthalpy`'s block.
    A lifted stream (`phase` is `None`) is read through the two blocks its *producer* already
    named after the stream, fed by the producer's split variables; the reader declares them too,
    and `assemble` deduplicates by block id, so only one of each is compiled.

    The same construction as `TPFlash._inlet_enthalpy` (K02), written here once for T05's units;
    K02's flash keeps its own copy so that its module, whose hash its manifest carries, does not
    change.
    """
    if phase is not None:
        block, feeding, keys = single_phase_enthalpy(provider, components, context, stream, phase)
        return keys, (block,), {block.block_id: feeding}

    blocks: list[PropertyBlock] = []
    inputs: dict[str, tuple[str, ...]] = {}
    all_keys: list[str] = []
    lifted: tuple[tuple[Phase, Callable[[str, str], str]], ...] = (
        ("VAPOR", vapor_flow_id),
        ("LIQUID", liquid_flow_id),
    )
    for lifted_phase, name in lifted:
        block = EnthalpyFlowBlock(
            provider,
            components,
            lifted_phase,
            context,
            block_id=enthalpy_block_id(stream, lifted_phase),
        )
        blocks.append(block)
        inputs[block.block_id] = (
            *(name(stream, component) for component in components),
            temperature_id(stream),
            pressure_id(stream),
        )
        all_keys.extend(f"{block.block_id}.{output}" for output in block.output_ids)
    return tuple(all_keys), tuple(blocks), inputs
