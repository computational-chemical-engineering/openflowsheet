"""`c1.stream_splitter` — one C1 stream into a recycle and a purge at a fixed fraction r (design
note §8, §8.1; M02 WO-8.2).

`syn001.stream_splitter`'s rows under a C1 identity: `n_rec,i − r n_in,i`, `n_pur,i − (1 − r)
n_in,i`, and the recycle's and the purge's T and P copied from the inlet. The SYN-001 class is not
reused: its manifest and its row origins carry SYN-001 constants. Linear in the flows, so a dormant
inlet gives dormant outlets exactly (ADR 0001 D3.4). The purge is `(1 − r) n_in`, as the row is, so
the outlets sum to the inlet only to rounding (SYN-001's splitter states the same).

It holds no provider: it changes no intensive state, so its outlets are in its inlet's phase.
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
from openflowsheet.models.rows import balance_row, scaled_row
from openflowsheet.thermo import StreamState

MODEL_ID: Final = "c1.stream_splitter"

PORTS: Final[tuple[Port, ...]] = tuple(
    Port(
        name=name,
        kind="material",
        direction=direction,  # type: ignore[arg-type]
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    )
    for name, direction in (("inlet", "inlet"), ("recycle", "outlet"), ("purge", "outlet"))
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="C1SPLIT-recycle",
        statement="n_rec,i - r n_in,i = 0 for every component i",
        dependencies=("inlet.state.n", "parameters.split_fraction"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1SPLIT-purge",
        statement="n_pur,i - (1 - r) n_in,i = 0 for every component i",
        dependencies=("inlet.state.n", "parameters.split_fraction"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1SPLIT-T",
        statement="T_rec - T_in = 0 and T_pur - T_in = 0",
        dependencies=("inlet.state.T",),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=DESIGN_NOTE,
    ),
    DeclaredEquation(
        equation_id="C1SPLIT-P",
        statement="P_rec - P_in = 0 and P_pur - P_in = 0",
        dependencies=("inlet.state.P",),
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
class StreamSplitter:
    """One C1 splitter instance; `split_fraction` is r, the recycle's share."""

    unit_id: str
    split_fraction: float
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        c1_components(self.unit_id, self.components)
        fraction = self.split_fraction
        if fraction != fraction or fraction in (float("inf"), float("-inf")):
            raise SpecificationError(f"{self.unit_id}: split fraction {fraction} is not finite")
        if fraction == 1.0:
            raise SpecificationError(
                f"{self.unit_id}: r = 1 recycles everything and purges nothing, so a loop's "
                "inerts have no exit and the loop no steady state. It is rejected, not clipped"
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

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="C1 stream splitter",
            description="Splits one C1 stream into a recycle and a purge at a fixed fraction r.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="residuals",
                    with_respect_to=("free_variables",),
                    method="ad",
                    regime="all",
                    notes="Every row is affine in the free variables.",
                ),
            ),
            initialization=Initialization(
                strategy="upstream_propagation",
                notes="Both outlets follow linearly from the inlet; no independent guess.",
            ),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "zero_flow"),
                limitations=(
                    "Linear in the component flows, so both outlets are exact at r = 0 and at a "
                    "dormant inlet (ADR 0001 D3.4).",
                    "r = 1 leaves a loop's inerts without an exit and is rejected, not clipped.",
                    "Separates nothing: both outlets have the inlet's composition, temperature "
                    "and pressure, and so its phase; it holds no property provider.",
                    "The purge is (1 - r) n_in, as its row is, so the two outlets sum to the "
                    "inlet only to rounding.",
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

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlet, recycle, purge = wiring.one("inlet"), wiring.one("recycle"), wiring.one("purge")
        fraction = self.fraction_parameter
        equations: list[EquationSpec] = []
        for component in self.components:
            for equation_id, outlet, complement in (
                ("C1SPLIT-recycle", recycle, False),
                ("C1SPLIT-purge", purge, True),
            ):
                equations.append(
                    EquationSpec(
                        equation_id=row_id(self.unit_id, equation_id, component),
                        build=scaled_row(
                            flow_id(outlet, component),
                            flow_id(inlet, component),
                            fraction,
                            complement=complement,
                        ),
                        accumulation="algebraic",
                        origin=origin(MODEL_ID, equation_id),
                    )
                )
        for equation_id, coordinate in (("C1SPLIT-T", temperature_id), ("C1SPLIT-P", pressure_id)):
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
            kinds[row_id(self.unit_id, "C1SPLIT-recycle", component)] = "molar_flow"
            kinds[row_id(self.unit_id, "C1SPLIT-purge", component)] = "molar_flow"
        for port in ("recycle", "purge"):
            kinds[row_id(self.unit_id, "C1SPLIT-T", port)] = "temperature"
            kinds[row_id(self.unit_id, "C1SPLIT-P", port)] = "pressure"
        return Contribution(
            equations=tuple(equations),
            parameter_ids=(fraction,),
            parameters={fraction: float(self.split_fraction)},
            row_kinds=kinds,
        )

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
                ""
                if feed.is_dormant
                else "phase signature not reported: a splitter changes no intensive state and "
                "holds no property provider"
            ),
        )
