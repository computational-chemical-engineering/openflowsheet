"""`c1.feed_source` — the fresh-feed boundary of a C1 flowsheet (design note §8, M02 WO-8.2).

`syn001.feed_source`'s rows under a C1 identity. The SYN-001 class is not reused: its manifest and
its row origins carry SYN-001 constants (its model id, its domain, its provider and convention),
so a thin C1 class writes the same three rows — "variable minus pinned specification", all
algebraic (ADR 0008 D1.3) — with the C1 family names.

Like SYN-001's, it holds no property provider and reports no phase signature for a flowing feed:
the phase of what it emits is the downstream units' and the verifier's question. A dormant feed is
`ZERO_FLOW` by arithmetic alone (ADR 0001 D3.1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from openflowsheet.models.c1 import (
    COMPONENTS,
    MOLAR_FLOW,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    TEMPERATURE,
)
from openflowsheet.models.c1.units import DESIGN_NOTE, P_RANGE, PACKAGE, T_RANGE, c1_components
from openflowsheet.models.rows import specification_row
from openflowsheet.thermo import StreamState

MODEL_ID: Final = "c1.feed_source"

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    ),
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="C1FEED-n",
        statement="n_out,i - n_spec,i = 0 for every component i",
        dependencies=("specifications.SPEC-feed-n-*",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1FEED-T",
        statement="T_out - T_spec = 0",
        dependencies=("specifications.SPEC-feed-T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1FEED-P",
        statement="P_out - P_spec = 0",
        dependencies=("specifications.SPEC-feed-P",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DESIGN_NOTE,
    ),
)


def _artifact_hash() -> str:
    """The module source's SHA-256. Not cached: T07 G20 lists every per-process cache, and this
    one would only save a file read per manifest (build log D37 (f))."""
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class FeedSource:
    """One C1 fresh-feed boundary instance."""

    unit_id: str
    #: Specified component molar flows, mol/s, in `components` order.
    flows: tuple[float, ...]
    temperature: float
    pressure: float
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        c1_components(self.unit_id, self.components)
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

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="C1 fresh-feed boundary",
            description="Boundary that emits a fully specified C1 material stream.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="outlet.state",
                    with_respect_to=("specifications",),
                    method="unavailable",
                    regime="all",
                    notes=(
                        "A sensitivity with respect to a specification is a derivative with "
                        "respect to a pinned input; the compiled boundary differentiates only "
                        "with respect to free variables (blueprint §5.2)."
                    ),
                ),
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes="The three row families are affine in the free variables.",
                ),
            ),
            initialization=Initialization(
                strategy="none", notes="A fully specified boundary needs no guess."
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "zero_flow"),
                limitations=(
                    "Boundary only: it imposes the specified state and models no equipment.",
                    "Holds no property provider and reports no phase signature for a flowing "
                    "feed: the phase of what it emits is judged downstream (the units' causal "
                    "evaluates, design note §14.2 B16) and by the certificate.",
                    f"Streams are {PROVIDER_ID} streams under {REFERENCE_CONVENTION}; mixing "
                    "them with SYN-001 streams is REFERENCE_MISMATCH (ADR 0001 D5.2).",
                ),
                temperature_k=T_RANGE,
                pressure_pa=P_RANGE,
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="thread_safe",
            evaluation_cost_class="cheap",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            package=PACKAGE,
        )

    def flow_parameter(self, component: str) -> str:
        return f"{self.unit_id}.n_spec.{component}"

    @property
    def temperature_parameter(self) -> str:
        return f"{self.unit_id}.T_spec"

    @property
    def pressure_parameter(self) -> str:
        return f"{self.unit_id}.P_spec"

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, specified for "
                f"{self.components}"
            )
        outlet = wiring.one("outlet")
        equations: list[EquationSpec] = []
        parameter_ids: list[str] = []
        parameters: dict[str, float] = {}
        for component, value in zip(self.components, self.flows, strict=True):
            parameter = self.flow_parameter(component)
            parameter_ids.append(parameter)
            parameters[parameter] = normalize_zero(float(value))
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "C1FEED-n", component),
                    build=specification_row(flow_id(outlet, component), parameter),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "C1FEED-n"),
                )
            )
        for equation_id, variable, parameter, value in (
            ("C1FEED-T", temperature_id(outlet), self.temperature_parameter, self.temperature),
            ("C1FEED-P", pressure_id(outlet), self.pressure_parameter, self.pressure),
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
            row_id(self.unit_id, "C1FEED-n", name): "molar_flow" for name in self.components
        }
        kinds[row_id(self.unit_id, "C1FEED-T")] = "temperature"
        kinds[row_id(self.unit_id, "C1FEED-P")] = "pressure"
        return Contribution(
            equations=tuple(equations),
            parameter_ids=tuple(parameter_ids),
            parameters=parameters,
            row_kinds=kinds,
        )

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        """Emit the specified stream; a boundary has nothing to compute and nothing to fail on."""
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
