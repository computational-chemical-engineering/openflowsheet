"""`syn001.component_separator` — an ideal component divider with a calculated duty (T05 spec §7).

Each component `i` goes to `top` in the specified fraction `s_i` and the rest to `bottom`. Both
outlets leave at the inlet's `(T, P)`, each in a **declared** phase: `top_phase` and
`bottom_phase` are configuration, not results. The duty is whatever closes the energy balance with
the outlets written in those phases — SEP-2's vapour top makes it the latent heat of what went up.

**Why declared phases, and not a lifted split.** A separator outlet may be vapour or liquid, but
the specification keeps every T05 unit to at most one lifted split (R-039), so that ADR 0005's
"one regime per phase-selecting unit" holds unchanged; the separator has two outlets and lifts
neither. The price is the one K02's heater and mixer already pay: an outlet written as a phase it
is not in describes a different function, so the evaluator applies R-007's admissibility
criterion (`tp_state.single_phase_admissible`) to each declared outlet, `top` first, and refuses
with a typed `unsupported` rather than reporting a duty for a state the rows cannot represent.

**The inlet** is either declared (`inlet_phase` LIQUID or VAPOR, admitted by the same criterion,
which K02's flash did not do — spec F7) or lifted upstream (`inlet_phase = None`), in which case
this unit reads the producer's split blocks exactly as K02's `TPFlash._inlet_enthalpy` does and
declares no block of its own that could disagree with them.

**Exact zeros.** `top_i = s_i n_in,i` and `bot_i = n_in,i - top_i`, the second as written in
`SEP-mole` rather than as `(1 - s_i) n_in,i`: at `s_i = 1` it is `x - x = 0` and at `s_i = 0` it is
`0 · x = 0`, so a split of 1 or 0 gives an exactly dormant outlet (SEP-3, SEP-4) and SEP-2's
`n_top,C` is exactly zero.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256, normalize_zero
from openflowsheet.compile.spec import EquationSpec, PropertyBlock, QuantityKind
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    DerivativeDeclaration,
    Initialization,
    Port,
    SpecificationError,
    UnitEvaluation,
    Validity,
    Wiring,
    duty_id,
    flow_id,
    manifest_document,
    origin,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.rows import balance_row, energy_row, scaled_row
from openflowsheet.models.syn001 import (
    COMPONENTS,
    MOLAR_FLOW,
    P_MAX,
    P_MIN,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    T_MAX,
    T_MIN,
    TEMPERATURE,
)
from openflowsheet.models.syn001.admission import admitted_enthalpy, provider_refusal
from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock
from openflowsheet.models.syn001.tp_state import (
    enthalpy_block_id,
    liquid_flow_id,
    single_phase_enthalpy,
    tp_state,
    vapor_flow_id,
)
from openflowsheet.thermo import Phase, PropertyProvider, StreamState

MODEL_ID: Final = "syn001.component_separator"

#: Where the equations are stated. T05's models cite their own specification, not SYN-001 §4.
SPECIFICATION: Final = "docs/derivations/T05-unit-models-spec.md §7"

_DECLARABLE: Final[tuple[Phase, ...]] = ("LIQUID", "VAPOR")

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor", "vapor_liquid"),
    ),
    Port(
        name="top",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    ),
    Port(
        name="bottom",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    ),
    Port(
        name="duty",
        kind="energy",
        direction="inlet",
        multiplicity=1,
        component_mapping=None,
        state_definition=None,
        phase_capabilities=(),
    ),
)

#: ADR 0008 D3.1's reason, verbatim from the specification.
_ZERO_HOLDUP_REASON: Final = (
    "an ideal component divider: its outlets are instantaneous fractions of its inlet at the "
    "inlet's state, so its inventory is identically zero by the model's definition; a separation "
    "vessel with holdup is a different model"
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="SEP-mole",
        statement="n_in,i - n_top,i - n_bot,i = 0 for every component i",
        dependencies=("inlet.state.n", "top.state.n", "bottom.state.n"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_ZERO_HOLDUP_REASON),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="SEP-split",
        statement="n_top,i - s_i n_in,i = 0 for every component i",
        dependencies=("inlet.state.n", "top.state.n", "parameters.split"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="SEP-T",
        statement="T_top - T_in = 0 and T_bot - T_in = 0",
        dependencies=("inlet.state.T", "top.state.T", "bottom.state.T"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="SEP-P",
        statement="P_top - P_in = 0 and P_bot - P_in = 0",
        dependencies=("inlet.state.P", "top.state.P", "bottom.state.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="SEP-duty",
        statement="Q + Hdot_in - Hdot_top - Hdot_bot = 0, Q positive into the unit",
        dependencies=("inlet.state", "top.state", "bottom.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="zero_holdup_balance", reason=_ZERO_HOLDUP_REASON),
        dimension=POWER,
        source=SPECIFICATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "The outlet flows are linear in the inlet flows, but the duty runs through the declared-phase "
    "enthalpies, and T05 exposes no sensitivity interface (spec §4.5): the unit offers residual "
    "rows and a causal evaluator that returns values. This stays `unavailable` and is reported as "
    "absent rather than as zeros (blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


def split_fraction_error(component: str) -> str:
    """The registered construction code for a split fraction outside `[0, 1]` (spec §13.3)."""
    return f"split_fraction_outside_unit_interval({component})"


def lifted_inlet_enthalpy(
    provider: PropertyProvider,
    components: tuple[str, ...],
    context: EvaluationContext,
    inlet: str,
) -> tuple[tuple[str, ...], tuple[PropertyBlock, ...], dict[str, tuple[str, ...]]]:
    """The block outputs whose sum is `Hdot_in` for an inlet whose split its producer lifted.

    The same blocks, ids and feeding variables as K02's `TPFlash._inlet_enthalpy`: this unit
    declares nothing the producer did not already name after the stream, and `assemble`
    deduplicates by block id. Returns `(keys, blocks, block_inputs)`.
    """
    blocks: list[PropertyBlock] = []
    inputs: dict[str, tuple[str, ...]] = {}
    keys: list[str] = []
    phases: tuple[tuple[Phase, Any], ...] = (("VAPOR", vapor_flow_id), ("LIQUID", liquid_flow_id))
    for phase, ids in phases:
        block = EnthalpyFlowBlock(
            provider, components, phase, context, block_id=enthalpy_block_id(inlet, phase)
        )
        blocks.append(block)
        inputs[block.block_id] = (
            *(ids(inlet, name) for name in components),
            temperature_id(inlet),
            pressure_id(inlet),
        )
        keys.extend(f"{block.block_id}.{output}" for output in block.output_ids)
    return tuple(keys), tuple(blocks), inputs


@dataclass(frozen=True)
class ComponentSeparator:
    """One separator instance: per-component split fractions to `top`, declared outlet phases."""

    unit_id: str
    provider: PropertyProvider
    #: `s_i`, the fraction of component `i` sent to `top`, in `components` order. Pinned inputs.
    split: tuple[float, ...]
    context: EvaluationContext
    #: The declared phase of the inlet; `None` means its split is lifted by its producer. No
    #: default: the spec gives none, and which enthalpy the inlet row writes is not a guess.
    inlet_phase: Phase | None
    top_phase: Phase = "LIQUID"
    bottom_phase: Phase = "LIQUID"
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if len(self.split) != len(self.components):
            raise ValueError(
                f"{self.unit_id}: {len(self.split)} split fractions for "
                f"{len(self.components)} components {self.components}"
            )
        for label, phase in (("top_phase", self.top_phase), ("bottom_phase", self.bottom_phase)):
            if phase not in _DECLARABLE:
                raise ValueError(f"{self.unit_id}: {label} must be LIQUID or VAPOR, got {phase!r}")
        if self.inlet_phase is not None and self.inlet_phase not in _DECLARABLE:
            raise ValueError(
                f"{self.unit_id}: inlet_phase must be LIQUID, VAPOR or None, got "
                f"{self.inlet_phase!r}"
            )
        for component, fraction in zip(self.components, self.split, strict=True):
            # `not 0 <= s <= 1` also refuses NaN, which compares false with everything.
            if not (math.isfinite(fraction) and 0.0 <= fraction <= 1.0):
                raise SpecificationError(
                    f"{split_fraction_error(component)}\n"
                    f"{self.unit_id}: the split fraction of {component} is {fraction}; a fraction "
                    "outside [0, 1] sends a negative flow to one outlet, and it is refused rather "
                    "than clipped"
                )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    def split_parameter(self, component: str) -> str:
        return f"{self.unit_id}.split.{component}"

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 component separator with declared outlet phases",
            description=(
                "Sends a specified fraction of each component to the top outlet and the rest to "
                "the bottom, both at the inlet's temperature and pressure in declared phases; "
                "the duty is calculated."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="top.state",
                    with_respect_to=("inlet.state", "parameters"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="bottom.state",
                    with_respect_to=("inlet.state", "parameters"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="duty.Q",
                    with_respect_to=("inlet.state", "parameters"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes=(
                        "Every row is written over flowsheet variables and declared-phase (or the "
                        "producer's lifted) enthalpy blocks, so the backend differentiates it "
                        "exactly through K01; the blocks supply their own declared-sparse "
                        "analytic derivatives. No inner solve sits inside a residual."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "The causal evaluator: the outlets are the split fractions of the inlet at "
                    "the inlet's state, the duty the enthalpy difference in the declared phases."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    "An ideal component divider: no holdup, no equilibrium between the outlets, "
                    "and both outlets at the inlet's temperature and pressure.",
                    "Each outlet is written in its declared phase (top_phase, bottom_phase) and "
                    "admitted by R-007's criterion |Hdot_TP - Hdot_phase| / (dHdot_phase/dT) <= "
                    "1e-6 K, top first; an inadmissible outlet is a typed unsupported "
                    "inadmissible_phase(top|bottom, <PHASE>), never a duty for a different "
                    "state.",
                    "A declared inlet phase is admitted by the same criterion "
                    "(inadmissible_phase(inlet, <PHASE>)); inlet_phase None reads the "
                    "producer's lifted split.",
                    "The unit authors no lifted split (R-039), and reports phase_signature null "
                    "except ZERO_FLOW for a dormant inlet.",
                    "A split fraction of 1 or 0 gives an exactly dormant outlet; a fraction "
                    "outside [0, 1] is refused at construction.",
                    "A dormant inlet gives two dormant outlets at the inlet's (T, P) and exactly "
                    "zero duty (ADR 0001 D3.4).",
                ),
                temperature_k=(T_MIN, T_MAX),
                pressure_pa=(P_MIN, P_MAX),
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="not_thread_safe",
            evaluation_cost_class="moderate",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            package="T05",
        )

    # -- rows --------------------------------------------------------------------------------

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise ValueError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlet = wiring.one("inlet")
        top = wiring.one("top")
        bottom = wiring.one("bottom")
        duty = duty_id(self.unit_id)

        blocks: list[PropertyBlock] = []
        block_inputs: dict[str, tuple[str, ...]] = {}
        if self.inlet_phase is None:
            inlet_keys, inlet_blocks, inlet_inputs = lifted_inlet_enthalpy(
                self.provider, self.components, self.context, inlet
            )
            blocks.extend(inlet_blocks)
            block_inputs.update(inlet_inputs)
        else:
            inlet_block, inlet_feeding, inlet_keys = single_phase_enthalpy(
                self.provider, self.components, self.context, inlet, self.inlet_phase
            )
            blocks.append(inlet_block)
            block_inputs[inlet_block.block_id] = inlet_feeding
        outlet_keys: list[str] = []
        for stream, phase in ((top, self.top_phase), (bottom, self.bottom_phase)):
            block, feeding, keys = single_phase_enthalpy(
                self.provider, self.components, self.context, stream, phase
            )
            blocks.append(block)
            block_inputs[block.block_id] = feeding
            outlet_keys.extend(keys)

        equations: list[EquationSpec] = []
        kinds: dict[str, QuantityKind] = {}
        for component in self.components:
            equation_id = row_id(self.unit_id, "SEP-mole", component)
            equations.append(
                EquationSpec(
                    equation_id=equation_id,
                    build=balance_row(
                        (flow_id(inlet, component),),
                        (flow_id(top, component), flow_id(bottom, component)),
                    ),
                    accumulation="zero_holdup_balance",
                    origin=origin(MODEL_ID, "SEP-mole"),
                )
            )
            kinds[equation_id] = "molar_flow"
        for component in self.components:
            equation_id = row_id(self.unit_id, "SEP-split", component)
            equations.append(
                EquationSpec(
                    equation_id=equation_id,
                    build=scaled_row(
                        flow_id(top, component),
                        flow_id(inlet, component),
                        self.split_parameter(component),
                        complement=False,
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "SEP-split"),
                )
            )
            kinds[equation_id] = "molar_flow"
        coordinates: tuple[tuple[str, Any, QuantityKind], ...] = (
            ("SEP-T", temperature_id, "temperature"),
            ("SEP-P", pressure_id, "pressure"),
        )
        for equation, coordinate, kind in coordinates:
            for port, stream in (("top", top), ("bottom", bottom)):
                equation_id = row_id(self.unit_id, equation, port)
                equations.append(
                    EquationSpec(
                        equation_id=equation_id,
                        build=balance_row((coordinate(stream),), (coordinate(inlet),)),
                        accumulation="algebraic",
                        origin=origin(MODEL_ID, equation),
                    )
                )
                kinds[equation_id] = kind
        equation_id = row_id(self.unit_id, "SEP-duty")
        equations.append(
            EquationSpec(
                equation_id=equation_id,
                build=energy_row(tuple(inlet_keys), tuple(outlet_keys), source=duty),
                accumulation="zero_holdup_balance",
                origin=origin(MODEL_ID, "SEP-duty"),
            )
        )
        kinds[equation_id] = "heat_rate"

        parameters = {
            self.split_parameter(component): float(fraction)
            for component, fraction in zip(self.components, self.split, strict=True)
        }
        return Contribution(
            variable_ids=(duty,),
            equations=tuple(equations),
            variable_kinds={duty: "heat_rate"},
            row_kinds=kinds,
            blocks=tuple(blocks),
            block_inputs=block_inputs,
            parameter_ids=tuple(parameters),
            parameters=parameters,
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise ValueError(
                f"{self.unit_id}: a separator takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise ValueError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )

        if feed.is_dormant:
            # ADR 0001 D3.4 and spec §7: both outlets dormant at the inlet's (T, P), exactly zero
            # duty, and no property is evaluated because there is nothing to evaluate.
            dormant = StreamState(
                n=tuple(0.0 for _ in self.components),
                temperature=feed.temperature,
                pressure=feed.pressure,
            )
            return UnitEvaluation(
                status="ok",
                outlets={"top": dormant, "bottom": dormant},
                duty=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
            )

        # Inlet enthalpy, spec §5.2 (3): a declared phase is admitted by R-007 and then written
        # as that phase -- the enthalpy the rows' inlet block computes; a lifted inlet is the TP
        # state its producer's split describes.
        if self.inlet_phase is None:
            inlet_state = tp_state(self.provider, feed, context)
            if inlet_state.status != "ok":
                return provider_refusal("inlet", inlet_state.status, inlet_state.message)
            assert inlet_state.enthalpy_flow is not None
            inlet_enthalpy = inlet_state.enthalpy_flow
        else:
            answer = admitted_enthalpy(
                self.provider,
                self.components,
                context,
                unit_id=self.unit_id,
                port="inlet",
                stream=feed,
                phase=self.inlet_phase,
            )
            if isinstance(answer, UnitEvaluation):
                return answer
            inlet_enthalpy = answer

        top_flows = tuple(
            normalize_zero(fraction * flow)
            for fraction, flow in zip(self.split, feed.n, strict=True)
        )
        bottom_flows = tuple(
            normalize_zero(flow - upward) for flow, upward in zip(feed.n, top_flows, strict=True)
        )
        top = StreamState(n=top_flows, temperature=feed.temperature, pressure=feed.pressure)
        bottom = StreamState(n=bottom_flows, temperature=feed.temperature, pressure=feed.pressure)

        outlet_enthalpy = 0.0
        for port, stream, phase in (
            ("top", top, self.top_phase),
            ("bottom", bottom, self.bottom_phase),
        ):
            answer = admitted_enthalpy(
                self.provider,
                self.components,
                context,
                unit_id=self.unit_id,
                port=port,
                stream=stream,
                phase=phase,
            )
            if isinstance(answer, UnitEvaluation):
                return answer
            outlet_enthalpy += answer

        return UnitEvaluation(
            status="ok",
            outlets={"top": top, "bottom": bottom},
            duty=outlet_enthalpy - inlet_enthalpy,
            # Two declared regimes are not one signature (spec §7); only ZERO_FLOW is reported.
            phase_signature=None,
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )
