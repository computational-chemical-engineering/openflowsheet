"""`syn001.product_sink` — the product boundary.

It contributes no equation and no variable. The manifest's empty equation list is "a positive
assertion that the model contributes no equation to the system", so this module's job is to make
that assertion executable rather than to find something for a sink to do.

The one thing it does report is whether the stream reaching it is dormant, which is arithmetic
(ADR 0001 D3.1) and needs no thermodynamics. That makes "accepts a dormant inlet" — true of the
vapour product in the 310 K variant and of the purge in the 420 K variant — something a test can
check instead of something the manifest merely claims.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from types import MappingProxyType
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
from openflowsheet.models.syn001 import (
    COMPONENTS,
    P_MAX,
    P_MIN,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    T_MAX,
    T_MIN,
)
from openflowsheet.thermo import StreamState

MODEL_ID: Final = "syn001.product_sink"
#: SYN-001's state domain, the default `domain` (S11 design §4.5).
DOMAIN: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {"T": (T_MIN, T_MAX), "P": (P_MIN, P_MAX)}
)

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
)

EQUATIONS: Final[tuple[DeclaredEquation, ...]] = ()


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


@dataclass(frozen=True)
class ProductSink:
    """One product boundary instance."""

    unit_id: str
    components: tuple[str, ...] = COMPONENTS
    #: S11 design §4.5 (ADR 0050 D3): the bound provider's identity, convention and domain, which
    #: `manifest()` reports; SYN-001's constants by default. The unit evaluates no property.
    property_provider: str = PROVIDER_ID
    reference_convention: str = REFERENCE_CONVENTION
    domain: Mapping[str, tuple[float, float]] = field(default=DOMAIN, hash=False)

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
            title="SYN-001 product sink",
            description="Boundary that accepts a product stream and imposes no equation.",
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="none",
                    with_respect_to=("inlet.state",),
                    method="unavailable",
                    regime="all",
                    notes=(
                        "The sink has no output. The entry records that fact explicitly rather "
                        "than leaving the derivative declaration empty, which would be "
                        "indistinguishable from an omission."
                    ),
                ),
            ),
            initialization=Initialization(strategy="none", notes="Nothing to initialize."),
            validity=Validity(
                components=self.components,
                phases=("liquid", "vapor", "vapor_liquid", "zero_flow"),
                limitations=(
                    "Contributes no equation and no variable. The empty equation list is a "
                    "positive assertion, not a placeholder.",
                    "Accepts a dormant inlet: the vapor product is dormant in the 310 K variant "
                    "and the purge is dormant in the 420 K variant.",
                ),
                temperature_k=self.domain["T"],
                pressure_pa=self.domain["P"],
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="native_equation",
            thread_safety="thread_safe",
            evaluation_cost_class="cheap",
            property_provider=self.property_provider,
            reference_convention=self.reference_convention,
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
            reference_convention=self.reference_convention,
            message="the sink imposes no equation and computes no outlet",
        )
