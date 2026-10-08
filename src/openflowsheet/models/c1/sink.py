"""`c1.product_sink` — the product boundary of a C1 flowsheet (design note §8, M02 WO-8.2).

No equation and no variable, as `syn001.product_sink`; the SYN-001 class is not reused because its
manifest carries SYN-001 constants (model id, domain, provider, convention). It accepts a vapour or
a liquid (the loop's NH3 product is the flash's liquid, its purge a vapour) and reports only whether
the stream reaching it is dormant, which is arithmetic (ADR 0001 D3.1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Contribution,
    DeclaredEquation,
    DerivativeDeclaration,
    Initialization,
    Port,
    SpecificationError,
    UnitEvaluation,
    Validity,
    Wiring,
    manifest_document,
)
from openflowsheet.models.c1 import COMPONENTS, PROVIDER_ID, REFERENCE_CONVENTION
from openflowsheet.models.c1.units import P_RANGE, PACKAGE, T_RANGE, c1_components
from openflowsheet.thermo import StreamState

MODEL_ID: Final = "c1.product_sink"

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity=1,
        component_mapping="revision_component_set",
        state_definition="nTP-v1",
        phase_capabilities=("liquid", "vapor"),
    ),
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = ()


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class ProductSink:
    """One C1 product boundary instance."""

    unit_id: str
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        c1_components(self.unit_id, self.components)

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
            title="C1 product sink",
            description="Boundary that accepts a C1 product stream and imposes no equation.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="none",
                    with_respect_to=("inlet.state",),
                    method="unavailable",
                    regime="all",
                    notes="The sink has no output; recorded explicitly rather than left empty.",
                ),
            ),
            initialization=Initialization(strategy="none", notes="Nothing to initialize."),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "zero_flow"),
                limitations=(
                    "Contributes no equation and no variable. The empty equation list is a "
                    "positive assertion, not a placeholder.",
                    "Accepts a vapour, a liquid, or a dormant inlet; the phase of what it "
                    "receives is its producer's declaration, judged by the certificate.",
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
        """Nothing, checked: the inlet must still be wired to exactly one stream."""
        wiring.one("inlet")
        return Contribution()

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        del context
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a product sink takes exactly one inlet stream, got {inlets!r}"
            )
        return UnitEvaluation(
            status="ok",
            outlets={},
            duty=None,
            phase_signature="ZERO_FLOW" if connected[0].is_dormant else None,
            reference_convention=REFERENCE_CONVENTION,
            message="the sink imposes no equation and computes no outlet",
        )
