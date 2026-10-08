"""`c1.reactor_standin` — a synthetic stand-in for the C1 reactor, for the in-repo gate (§8.13).

**Synthetic, and says so everywhere a reader will look.** It has the C1 reactor's ports, rows,
refusals and result envelope (spec §8.2-§8.12, ADR 0027 D8), with the group's reactor replaced by
closed forms: per tube, ξ_s = X n_N2,in with X = 0.25 (a per-pass N2 conversion) and T_out = T_in.
It exercises every path of the boundary (`boundary.py`) without PyMRM and certifies nothing about
the real reactor or the chemistry: its manifest's title, description and limitations say
"synthetic", and every result's identity carries `synthetic: true` (the frozen ModelManifest schema
has no `synthetic` field). It is never `validated`.

**Two test-only parameters** reach paths the closed forms never take: `perturbation`, d mol/s per
tube added to the raw outlet (the extent projection and the element-defect refusal), and
`pressure_drop`, a reported Ergun drop in Pa (the zero-pressure-drop convention).

**Constructed only over a reaction-consistent provider** (ADR 0011 D2 as amended by ADR 0026 D4):
the duty is the total-enthalpy balance Q = Ḣ_out − Ḣ_in, right only on a formation datum; any other
reference convention is refused `reference_convention_not_reaction_consistent(<convention>)`.

Not registered in `MODEL_BUILDERS`: binding the C1 reactor into a revision, with its rows in a
compiled problem, is M02's (spec §8.14); this module's rows are the declaration M02 implements.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import document_sha256, file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Accumulation,
    DeclaredEquation,
    DerivativeDeclaration,
    Holdup,
    Initialization,
    Port,
    SpecificationError,
    Validity,
    manifest_document,
)
from openflowsheet.models.c1 import (
    COMPONENTS,
    ENERGY,
    MOLAR_FLOW,
    MOLE,
    NU,
    POWER,
    PRESSURE,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    TEMPERATURE,
)
from openflowsheet.models.c1.boundary import (
    Boundary,
    ReactorResult,
    TubeInlet,
    TubeOutlet,
    require_positive,
)
from openflowsheet.thermo import PropertyProvider, StreamState
from openflowsheet.thermo.conventions import (
    REACTION_CONSISTENT_CONVENTIONS,
    reference_convention_not_reaction_consistent,
)

MODEL_ID: Final = "c1.reactor_standin"
SPECIFICATION: Final = "docs/derivations/M01-spec.md §8.2, §8.13"
#: X, the stand-in's per-pass N2 conversion (spec §8.13).
CONVERSION: Final = 0.25

PORTS: Final[tuple[Port, ...]] = (
    Port(
        name="inlet",
        kind="material",
        direction="inlet",
        multiplicity=1,
        component_mapping=COMPONENTS,
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
    ),
    Port(
        name="outlet",
        kind="material",
        direction="outlet",
        multiplicity=1,
        component_mapping=COMPONENTS,
        state_definition="nTP-v1",
        phase_capabilities=("vapor",),
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

#: Spec §8.2's nine rows (five component rows, extent, temperature, pressure, duty): DOF 0 given
#: the inlet and the configuration.
EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="C1RX-mole",
        statement="n_out,i - n_in,i - nu_i xi = 0 for every component i, nu = (-3, -1, 2, 0, 0)",
        dependencies=("inlet.state.n", "outlet.state.n", "extent.xi"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i", quantity="component moles held in the reactor", dimension=MOLE
            ),
        ),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="C1RX-extent",
        statement=(
            "xi - Xi(n_in, T_in, P_in) = 0: the external evaluation's extent projected onto the "
            "reaction (spec §8.9); the stand-in's raw extent is X n_N2,in, X = 0.25"
        ),
        dependencies=("inlet.state", "extent.xi"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="C1RX-temperature",
        statement="T_out - Theta(n_in, T_in, P_in) = 0; the stand-in's Theta is T_in",
        dependencies=("inlet.state", "outlet.state.T"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="C1RX-pressure",
        statement=(
            "P_out - P_in = 0: the zero-pressure-drop convention, admissible iff |dP|/P_in <= 1e-3 "
            "(ADR 0027 D2)"
        ),
        dependencies=("inlet.state.P", "outlet.state.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=SPECIFICATION,
    ),
    DeclaredEquation(
        equation_id="C1RX-duty",
        statement=(
            "Q - (Hdot_out - Hdot_in) = 0, Q positive into the unit; both enthalpy flows by "
            "pr-c1-v1 on PR-C1-ref-v1, a formation datum, so no xi dh_r term (ADR 0011 D2)"
        ),
        dependencies=("inlet.state", "outlet.state", "duty.Q"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="U", quantity="internal energy of the reactor contents", dimension=ENERGY
            ),
        ),
        dimension=POWER,
        source=SPECIFICATION,
    ),
)

LIMITATIONS: Final[tuple[str, ...]] = (
    "SYNTHETIC: the reactor is replaced by closed forms (xi = 0.25 n_N2,in per pass, T_out = "
    "T_in); its numbers certify the boundary code, never the reactor or the chemistry (spec §8.13, "
    "§17).",
    "The zero-pressure-drop convention: P_out = P_in, refused above |dP|/P_in = 1e-3 (ADR 0027 "
    "D2).",
    "The outlet is the least-squares extent projection of the raw outlet, refused above an "
    "element defect of 1e-6 of the inlet flow (ADR 0027 D3).",
    "A vapour inlet only: a liquid at the inlet, a component set other than (H2, N2, NH3, Ar, "
    "CH4), y_NH3 below 1e-9 and an inlet outside 573.15-773.15 K, 5-15 MPa, H2/N2 in [1, 4], "
    "inerts <= 20 % are refused; outside the kinetics' data domain the result is flagged "
    "extrapolated (ADR 0027 D9).",
)


@cache
def _artifact_hash() -> str:
    return file_sha256(Path(__file__))


def _standin_evaluation(
    conversion: float, perturbation: tuple[float, ...] | None, pressure_drop: float
) -> Any:
    """The stand-in's external evaluation: closed forms on one tube's inlet."""

    def evaluate(tube: TubeInlet) -> TubeOutlet:
        feed = tuple(tube.flow * y for y in tube.composition)
        xi = conversion * feed[1]
        flows = tuple(feed[i] + NU[i] * xi for i in range(len(COMPONENTS)))
        if perturbation is not None:
            flows = tuple(value + d for value, d in zip(flows, perturbation, strict=True))
        return TubeOutlet(flows=flows, temperature=tube.temperature, pressure_drop=pressure_drop)

    return evaluate


@dataclass(frozen=True)
class ReactorStandin:
    """One stand-in reactor: N_tubes identical synthetic tubes over `pr-c1-v1`."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    #: A positive real (spec §8.2); the map is homogeneous of degree 1 in (n, N_tubes).
    n_tubes: float = 1.0
    #: Test-only: d, mol/s per tube, added to the raw outlet (spec §8.13).
    perturbation: tuple[float, ...] | None = None
    #: Test-only: the tube's reported Ergun pressure drop, Pa (spec §8.13).
    pressure_drop: float = 0.0

    def __post_init__(self) -> None:
        require_positive(self.n_tubes, f"{self.unit_id}: n_tubes")
        if self.perturbation is not None and len(self.perturbation) != len(COMPONENTS):
            raise ValueError(f"{self.unit_id}: a perturbation has {len(COMPONENTS)} entries")
        described = self.provider.describe()
        convention = described.reference_convention
        if convention not in REACTION_CONSISTENT_CONVENTIONS:
            raise SpecificationError(
                f"{reference_convention_not_reaction_consistent(convention)}\n"
                f"{self.unit_id}: the provider's reference convention {convention!r} is not in "
                f"the registered reaction-consistent set {sorted(REACTION_CONSISTENT_CONVENTIONS)}"
                "; a total-enthalpy balance over it would not carry an enthalpy of reaction"
            )
        if tuple(described.components) != COMPONENTS:
            raise SpecificationError(
                "component_set_mismatch\n"
                f"{self.unit_id}: the provider's components {list(described.components)} are not "
                f"the C1 set {list(COMPONENTS)}"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    def configuration(self) -> Mapping[str, Any]:
        """The configuration that is part of the unit's identity (spec §8.2)."""
        return {
            "model_id": MODEL_ID,
            "conversion_N2": CONVERSION,
            "n_tubes": self.n_tubes,
            "perturbation_mol_s": None if self.perturbation is None else list(self.perturbation),
            "pressure_drop_Pa": self.pressure_drop,
        }

    def identity(self) -> Mapping[str, Any]:
        """§8.12's identity: the reactor-specific members are `None`, `synthetic` is true."""
        return {
            "model_id": MODEL_ID,
            "synthetic": True,
            "reactor_commit": None,
            "pymrm_version": None,
            "overlay_sha256": None,
            "configuration_sha256": document_sha256(self.configuration()),
            "profile": None,
        }

    def evaluate(self, inlet: StreamState, components: Sequence[str] = COMPONENTS) -> ReactorResult:
        boundary = Boundary(provider=self.provider, n_tubes=self.n_tubes, identity=self.identity())
        evaluation = _standin_evaluation(CONVERSION, self.perturbation, self.pressure_drop)
        return boundary.evaluate(inlet, components, evaluation, self.context)

    # -- declaration -------------------------------------------------------------------------

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        return manifest_document(
            model_id=MODEL_ID,
            title="C1 reactor, synthetic stand-in",
            description=(
                "SYNTHETIC stand-in for the C1 ammonia reactor: the C1 reactor's ports, rows, "
                "refusals and result envelope with the group's reactor replaced by closed forms "
                "(xi = 0.25 n_N2,in per tube, T_out = T_in). It exercises the boundary of ADR "
                "0027 in the in-repo gate and certifies nothing about the real reactor."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(
                DerivativeDeclaration(
                    output="outlet.state",
                    with_respect_to=("inlet.state",),
                    method="unavailable",
                    regime="all",
                    notes=(
                        "The boundary returns values only; the C1 reactor's embedding in a "
                        "compiled problem, and with it any sensitivity, is M02's (spec §8.14)."
                    ),
                ),
            ),
            initialization=Initialization(
                strategy="local_initializer",
                notes="The closed forms evaluated at the inlet: the stand-in has no iteration.",
            ),
            validity=Validity(
                components=COMPONENTS,
                phases=("vapor", "zero_flow"),
                limitations=LIMITATIONS,
                temperature_k=(573.15, 773.15),
                pressure_pa=(5.0e6, 1.5e7),
            ),
            module="openflowsheet.models.c1.reactor_standin",
            artifact_hash=_artifact_hash(),
            execution_class="explicit_reduced",
            thread_safety="thread_safe",
            evaluation_cost_class="cheap",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            status="tested",
            package="M01",
        )
