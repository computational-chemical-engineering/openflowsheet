"""`syn001.feed_source` — the fresh-feed boundary.

Emits a fully specified material stream. Three rows, all algebraic, all of the form
"variable minus pinned specification" (ADR 0008 D1.3: a specification value is a pinned input).

The manifest's own limitation is worth restating because it shapes the code: "SYN-001 declares the
feed liquid at 300 K and P_r; the manifest does not verify that claim, the flash kernel does." So
this unit holds no property provider and reports a phase signature of `None` for a flowing feed —
not `LIQUID`, which would be the claim it was told not to make. A dormant feed is different: that
is `ZERO_FLOW` by arithmetic alone (ADR 0001 D3.1) and needs no thermodynamics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256, normalize_zero
from openflowsheet.compile.spec import EquationSpec, QuantityKind
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
    flow_id,
    manifest_document,
    origin,
    pressure_id,
    row_id,
    temperature_id,
)
from openflowsheet.models.rows import specification_row
from openflowsheet.models.syn001 import (
    COMPONENTS,
    DERIVATION,
    MOLAR_FLOW,
    P_MAX,
    P_MIN,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    T_MAX,
    T_MIN,
    TEMPERATURE,
)
from openflowsheet.thermo import StreamState

MODEL_ID: Final = "syn001.feed_source"

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    ),
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="FEED-n",
        statement="n_out,i - n_spec,i = 0 for every component i",
        dependencies=("specifications.SPEC-feed-n-*",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="FEED-T",
        statement="T_out - T_spec = 0",
        dependencies=("specifications.SPEC-feed-T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="FEED-P",
        statement="P_out - P_spec = 0",
        dependencies=("specifications.SPEC-feed-P",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DERIVATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "K02 implements the model and K01 supplies the residual derivative route, but a sensitivity "
    "of the outlet state with respect to a *specification* is a derivative with respect to a "
    "pinned input, and the compiled boundary differentiates only with respect to free variables. "
    "Still unavailable, and reported as absent rather than as zeros (blueprint §5.2)."
)

_RESIDUAL_NOTE: Final = (
    "The three rows are affine in the free variables and in the pinned specifications; CasADi "
    "differentiates them exactly through the K01 adapter (ADR 0003 D5.1)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class FeedSource:
    """One fresh-feed boundary instance."""

    unit_id: str
    #: Specified component molar flows, mol/s, in `components` order.
    flows: tuple[float, ...]
    temperature: float
    pressure: float
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if len(self.flows) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: {len(self.flows)} specified flows for "
                f"{len(self.components)} components"
            )
        negative = [
            name for name, value in zip(self.components, self.flows, strict=True) if value < 0.0
        ]
        if negative:
            raise SpecificationError(
                f"{self.unit_id}: negative specified feed flow for {negative}. A boundary that "
                "emits a negative component flow is a malformed problem, not a state the model "
                "has an answer at"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 fresh-feed boundary",
            description="Boundary that emits a fully specified material stream.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="outlet.state",
                    with_respect_to=("specifications",),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes=_RESIDUAL_NOTE,
                ),
            ),
            initialization=Initialization(
                strategy="none",
                notes="A fully specified boundary needs no guess.",
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid",),
                limitations=(
                    "Boundary only: it imposes the specified state and models no equipment.",
                    "SYN-001 declares the feed liquid at 300 K and P_r; the manifest does not "
                    "verify that claim, the flash kernel does.",
                    "Reports no phase signature for a flowing feed, because it holds no property "
                    "provider and would otherwise be asserting the claim above.",
                ),
                temperature_k=(T_MIN, T_MAX),
                pressure_pa=(P_MIN, P_MAX),
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="thread_safe",
            evaluation_cost_class="cheap",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )

    # -- parameters --------------------------------------------------------------------------

    def flow_parameter(self, component: str) -> str:
        return f"{self.unit_id}.n_spec.{component}"

    @property
    def temperature_parameter(self) -> str:
        return f"{self.unit_id}.T_spec"

    @property
    def pressure_parameter(self) -> str:
        return f"{self.unit_id}.P_spec"

    # -- rows --------------------------------------------------------------------------------

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into a flowsheet with components {tuple(components)} but "
                f"specified for {self.components}"
            )
        outlet = wiring.one("outlet")

        equations: list[EquationSpec] = []
        parameter_ids: list[str] = []
        parameters: dict[str, float] = {}

        for component, value in zip(self.components, self.flows, strict=True):
            variable = flow_id(outlet, component)
            parameter = self.flow_parameter(component)
            parameter_ids.append(parameter)
            parameters[parameter] = normalize_zero(float(value))
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "FEED-n", component),
                    build=specification_row(variable, parameter),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "FEED-n"),
                )
            )

        for equation_id, variable, parameter, value in (
            ("FEED-T", temperature_id(outlet), self.temperature_parameter, self.temperature),
            ("FEED-P", pressure_id(outlet), self.pressure_parameter, self.pressure),
        ):
            parameter_ids.append(parameter)
            parameters[parameter] = float(value)
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, equation_id),
                    build=specification_row(variable, parameter),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, equation_id),
                )
            )

        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "FEED-n", name): "molar_flow" for name in self.components
        }
        kinds[row_id(self.unit_id, "FEED-T")] = "temperature"
        kinds[row_id(self.unit_id, "FEED-P")] = "pressure"

        return Contribution(
            equations=tuple(equations),
            parameter_ids=tuple(parameter_ids),
            parameters=parameters,
            row_kinds=kinds,
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        """Emit the specified stream. A boundary has nothing to compute and nothing to fail on."""
        del context
        if inlets:
            raise SpecificationError(
                f"{self.unit_id}: a feed source has no inlet port, got {sorted(inlets)}"
            )
        state = StreamState(
            n=tuple(normalize_zero(float(value)) for value in self.flows),
            temperature=float(self.temperature),
            pressure=float(self.pressure),
        )
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": state},
            duty=None,
            phase_signature="ZERO_FLOW" if state.is_dormant else None,
            reference_convention=REFERENCE_CONVENTION,
            message=(
                ""
                if state.is_dormant
                else "phase signature not reported: this boundary holds no property provider"
            ),
        )
