"""`syn001.stream_splitter` — one inlet into a recycle and a purge at fixed fraction r.

Linear in the component flows, which is why every zero passes through exactly (ADR 0001 D3.4) and
why `r = 0` gives an exactly dormant recycle rather than something small.

**The purge is `(1 - r) n_in`, not `n_in - n_rec`.** The second form would close the component
balance to the last bit at every r, and it is tempting for exactly that reason. It is not what
`SPLIT-purge` declares, and a residual and an evaluator that describe different functions is the
defect this project cares most about. So both use `(1 - r)`, and the two outlets then sum to the
inlet only to rounding. The registered r-variants happen to be exact — at r = 0, 0.5 and 0.95 the
complement and the products are all representable — but that is luck, not a property: at r = 0.3
and n_in,i = 3 mol/s the sum is 2.9999999999999996, short by 4.4e-16 mol/s. Against a registered
component-balance tolerance of 1e-9 + 1e-8 x 3 mol/s that is nothing; it is stated here rather
than hidden by a reformulation that would make the evaluator disagree with the row.
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
from openflowsheet.models.rows import balance_row, scaled_row
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

MODEL_ID: Final = "syn001.stream_splitter"

PORTS: Final[tuple[Port, ...]] = tuple(
    Port(
        name=name,
        kind="material",
        direction=direction,  # type: ignore[arg-type]
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid",),
    )
    for name, direction in (("inlet", "inlet"), ("recycle", "outlet"), ("purge", "outlet"))
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="SPLIT-recycle",
        statement="n_rec,i - r n_in,i = 0 for every component i",
        dependencies=("inlet.state.n", "parameters.split_fraction"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="SPLIT-purge",
        statement="n_pur,i - (1 - r) n_in,i = 0 for every component i",
        dependencies=("inlet.state.n", "parameters.split_fraction"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="SPLIT-T",
        statement="T_rec - T_in = 0 and T_pur - T_in = 0",
        dependencies=("inlet.state.T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DERIVATION,
    ),
    DeclaredEquation(
        equation_id="SPLIT-P",
        statement="P_rec - P_in = 0 and P_pur - P_in = 0",
        dependencies=("inlet.state.P",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=DERIVATION,
    ),
)

_SENSITIVITY_NOTE: Final = (
    "The relation is linear and its derivative is r, but K02 exposes no sensitivity interface: "
    "it offers residual rows and a causal evaluator that returns values. Declaring `analytic` "
    "would name a capability no caller can reach, so this stays `unavailable` (blueprint §5.2)."
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class StreamSplitter:
    """One splitter instance at a fixed split fraction."""

    unit_id: str
    split_fraction: float
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        fraction = self.split_fraction
        if fraction != fraction or fraction in (float("inf"), float("-inf")):
            raise SpecificationError(f"{self.unit_id}: split fraction {fraction} is not finite")
        if fraction == 1.0:
            raise SpecificationError(
                f"{self.unit_id}: r = 1 sends the whole liquid to recycle and leaves the SYN-001 "
                "loop without a steady state (derivation §5). It is rejected, not clipped"
            )
        if not 0.0 <= fraction < 1.0:
            raise SpecificationError(
                f"{self.unit_id}: split fraction {fraction} is outside [0, 1); one of the two "
                "outlets would carry negative flow"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def fraction_parameter(self) -> str:
        return f"{self.unit_id}.split_fraction"

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="SYN-001 stream splitter",
            description="Splits one stream into a recycle and a purge at fixed fraction r.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="recycle.state.n",
                    with_respect_to=("inlet.state.n", "parameters.split_fraction"),
                    method="unavailable",
                    regime="all",
                    notes=_SENSITIVITY_NOTE,
                ),
                DerivativeDeclaration(
                    output="purge.state.n",
                    with_respect_to=("inlet.state.n", "parameters.split_fraction"),
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
                        "All eight rows are affine in the free variables; CasADi differentiates "
                        "them exactly through the K01 adapter (ADR 0003 D5.1)."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="upstream_propagation",
                notes="Both outlets follow linearly from the inlet; no independent guess.",
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "zero_flow"),
                limitations=(
                    "Linear in the component flows, so both outlets are exact at r = 0 and at a "
                    "dormant inlet (ADR 0001 D3.4).",
                    "r = 1 leaves the SYN-001 loop without a steady state and is rejected rather "
                    "than clipped (derivation §5).",
                    "Composition is identical in both outlets by construction; the splitter "
                    "separates nothing.",
                    "The purge is (1 - r) n_in, matching SPLIT-purge, so the two outlets sum to "
                    "the inlet only to rounding: exact at the registered r = 0, 0.5 and 0.95, but "
                    "short by 4.4e-16 mol/s at r = 0.3 and n_in,i = 3. The evaluator is not "
                    "reformulated as n_in - n_rec to hide that, because the row is not.",
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

    # -- rows --------------------------------------------------------------------------------

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlet = wiring.one("inlet")
        recycle = wiring.one("recycle")
        purge = wiring.one("purge")
        fraction = self.fraction_parameter

        equations: list[EquationSpec] = []
        for component in self.components:
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "SPLIT-recycle", component),
                    build=scaled_row(
                        flow_id(recycle, component),
                        flow_id(inlet, component),
                        fraction,
                        complement=False,
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "SPLIT-recycle"),
                )
            )
            equations.append(
                EquationSpec(
                    equation_id=row_id(self.unit_id, "SPLIT-purge", component),
                    build=scaled_row(
                        flow_id(purge, component),
                        flow_id(inlet, component),
                        fraction,
                        complement=True,
                    ),
                    accumulation="algebraic",
                    origin=origin(MODEL_ID, "SPLIT-purge"),
                )
            )

        for equation_id, coordinate in (("SPLIT-T", temperature_id), ("SPLIT-P", pressure_id)):
            for port, stream in (("recycle", recycle), ("purge", purge)):
                equations.append(
                    EquationSpec(
                        equation_id=row_id(self.unit_id, equation_id, port),
                        build=balance_row((coordinate(stream),), (coordinate(inlet),)),
                        accumulation="algebraic",
                        origin=origin(MODEL_ID, equation_id),
                    )
                )

        kinds: dict[str, QuantityKind] = {}
        for component in self.components:
            kinds[row_id(self.unit_id, "SPLIT-recycle", component)] = "molar_flow"
            kinds[row_id(self.unit_id, "SPLIT-purge", component)] = "molar_flow"
        for port in ("recycle", "purge"):
            kinds[row_id(self.unit_id, "SPLIT-T", port)] = "temperature"
            kinds[row_id(self.unit_id, "SPLIT-P", port)] = "pressure"

        return Contribution(
            equations=tuple(equations),
            parameter_ids=(fraction,),
            parameters={fraction: float(self.split_fraction)},
            row_kinds=kinds,
        )

    # -- evaluator ---------------------------------------------------------------------------

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        del context
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a splitter takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        fraction = float(self.split_fraction)
        complement = 1.0 - fraction
        recycle = StreamState(
            n=tuple(normalize_zero(fraction * value) for value in feed.n),
            temperature=feed.temperature,
            pressure=feed.pressure,
        )
        purge = StreamState(
            n=tuple(normalize_zero(complement * value) for value in feed.n),
            temperature=feed.temperature,
            pressure=feed.pressure,
        )
        return UnitEvaluation(
            status="ok",
            outlets={"recycle": recycle, "purge": purge},
            duty=None,
            phase_signature="ZERO_FLOW" if feed.is_dormant else None,
            reference_convention=REFERENCE_CONVENTION,
            message=(
                "phase signature not reported: a splitter changes no intensive state and holds "
                "no property provider"
                if not feed.is_dormant
                else ""
            ),
        )
