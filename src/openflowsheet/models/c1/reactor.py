"""`c1.reactor` and `c1.reactor_standin` in a flowsheet solve: the embedded unit (M02 design note
§4.1; ADR 0034 D1, D9; M02 WO-9).

**Extent-fixed.** The unit is compiled with rows that take the N2 conversion X̂ and the temperature
rise ΔT̂ as pinned parameters, `<U>.coupling.X` and `<U>.coupling.dT`, carried in
`constants_sha256` with the stoichiometry `<U>.nu.<i>`:

- `C1RX-mole.<i>`: `n_in,i + ν_i ξ − n_out,i` (`reaction_balance_row`);
- `C1RX-extent`: `ξ − X̂ n_N2,in / 1` (`extent_row`, key N2, ν_N2 = −1);
- `C1RX-temperature`: `T_out − T_in − ΔT̂ = 0`, written `T_in − T_out + ΔT̂` by `offset_row` (build
  log D45: the builder's `outlet − inlet + offset`, with ΔT̂ the rise);
- `C1RX-pressure`: `P_in − P_out` (`balance_row`);
- `C1RX-duty`: `Q + Ḣ_in − Ḣ_out` over `pr-c1-v1`'s vapour enthalpy-flow blocks (§14.2 B17), on
  PR-C1-ref-v1, a formation datum, so no ξ Δh_r term (ADR 0011 D2).

**The unit never calls the external model.** These rows are analytic; the coupled route (ADR 0034
D2) iterates X̂ and ΔT̂ against the experiment, re-compiling the inner problem per iteration. The
extent is the column `extent_id(U)` (`<U>.xi`), the name the traversal, the verifier's reaction
envelope and its material rule already read (build log D45).

One class serves both model ids: `c1.reactor` (variant-backed, `experiment_provider`) and the
synthetic `c1.reactor_standin` (in process, `explicit_reduced`). The bound variant's document
supplies the manifest's domain and limitations; the stand-in's first limitation and its
description say SYNTHETIC (M01.A49).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.compile.spec import EquationSpec, QuantityKind
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Accumulation,
    Contribution,
    DeclaredEquation,
    DerivativeDeclaration,
    Holdup,
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
    reactor_standin,
)
from openflowsheet.models.c1.blocks import (
    VapourEnthalpyFlow,
    block_feeding,
    exactly_dormant,
    hdot_block_id,
)
from openflowsheet.models.c1.units import (
    PACKAGE,
    c1_components,
    c1_provider,
    enthalpy_flow,
    vapour_refusal,
)
from openflowsheet.models.rows import (
    balance_row,
    energy_row,
    extent_row,
    offset_row,
    reaction_balance_row,
)
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.thermo import PropertyProvider, StreamState
from openflowsheet.thermo.conventions import (
    REACTION_CONSISTENT_CONVENTIONS,
    reference_convention_not_reaction_consistent,
)

#: The variant-backed reactor (ADR 0034 D9).
REACTOR_MODEL_ID: Final = "c1.reactor"
#: The synthetic stand-in, M01's model id (ADR 0034 D9).
STANDIN_MODEL_ID: Final = reactor_standin.MODEL_ID
MODEL_IDS: Final = (REACTOR_MODEL_ID, STANDIN_MODEL_ID)
#: The key reactant of `C1RX-extent`: X̂ is a conversion of N2.
KEY_COMPONENT: Final = "N2"

#: The C1 reactor's ports, as M01 declared them (spec §8.2): vapour inlet and outlet, a duty.
PORTS: Final[tuple[Port, ...]] = reactor_standin.PORTS

_SOURCE: Final = (
    "docs/design/M02-pymrm-adapter.md §4.1; "
    "docs/adr/0034-external-models-in-a-flowsheet-solve.md D1"
)

#: Design note §4.1: the stand-in's five row families with its accumulation declarations, stated
#: at pinned coupling parameters.
EQUATIONS: Final[tuple[DeclaredEquation, ...]] = (
    DeclaredEquation(
        equation_id="C1RX-mole",
        statement="n_in,i + nu_i xi - n_out,i = 0 for every component i, nu = (-3, -1, 2, 0, 0)",
        dependencies=("inlet.state.n", "outlet.state.n", "extent.xi"),
        conditional_class="unconditional",
        accumulation=Accumulation(
            kind="holdup_balance",
            holdup=Holdup(
                symbol="N_i", quantity="component moles held in the reactor", dimension=MOLE
            ),
        ),
        dimension=MOLAR_FLOW,
        source=_SOURCE,
    ),
    DeclaredEquation(
        equation_id="C1RX-extent",
        statement=(
            "xi - X n_N2,in / 1 = 0, X the pinned coupling parameter U.coupling.X (the N2 "
            "conversion the coupled route iterates against the external model)"
        ),
        dependencies=("inlet.state.n", "extent.xi", "parameters.coupling.X"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=MOLAR_FLOW,
        source=_SOURCE,
    ),
    DeclaredEquation(
        equation_id="C1RX-temperature",
        statement=(
            "T_out - T_in - dT = 0, dT the pinned coupling parameter U.coupling.dT (K); the row "
            "is written T_in - T_out + dT"
        ),
        dependencies=("inlet.state.T", "outlet.state.T", "parameters.coupling.dT"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=TEMPERATURE,
        source=_SOURCE,
    ),
    DeclaredEquation(
        equation_id="C1RX-pressure",
        statement=(
            "P_in - P_out = 0: the zero-pressure-drop convention, admissible iff |dP|/P_in <= "
            "1e-3 (ADR 0027 D2)"
        ),
        dependencies=("inlet.state.P", "outlet.state.P"),
        conditional_class="unconditional",
        accumulation=Accumulation(kind="algebraic"),
        dimension=PRESSURE,
        source=_SOURCE,
    ),
    DeclaredEquation(
        equation_id="C1RX-duty",
        statement=(
            "Q + Hdot_V(in) - Hdot_V(out) = 0, Q positive into the unit; Hdot_V = Sum(n) h of the "
            "pr-c1-v1 vapour on PR-C1-ref-v1, a formation datum, so no xi dh_r term (ADR 0011 "
            "D2); 0 with the ideal-gas flow derivatives at an exactly dormant stream (design "
            "note §14.2 B17)"
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
        source=_SOURCE,
    ),
)

_RESIDUALS: Final = DerivativeDeclaration(
    output="residuals",
    with_respect_to=("free_variables",),
    method="analytic",
    regime="all",
    notes="the embedded rows at pinned coupling parameters (ADR 0034); exact for those rows",
)
_EXTERNAL_MAP: Final = DerivativeDeclaration(
    output="outlet.state",
    with_respect_to=("inlet.state",),
    method="unavailable",
    regime="all",
    notes="the external map; no sensitivity through this unit (ADR 0034 D4)",
)


def _artifact_hash() -> str:
    """The module source's SHA-256. Not cached (build log D37 (f): T07 G20 counts caches)."""
    return file_sha256(Path(__file__))


def _range(pair: Sequence[float]) -> str:
    return f"{float(pair[0]):g}-{float(pair[1]):g}"


def variant_limitations(model_id: str, variant: Mapping[str, Any]) -> tuple[str, ...]:
    """The manifest's limitations, from the bound variant's document (design note §4.1): the
    stand-in's SYNTHETIC label first (M01.A49, R-199); the real reactor's discretization estimate,
    `extrapolated` results, F-R2 and F-R3 (M01 spec §8.14); for both, the embedding, the domain
    and the conventions."""
    variant_id = str(variant["variant_id"])
    boundary = variant["boundary"]
    hard, data = boundary["hard_domain"], boundary["data_domain"]
    embedding = (
        "In a flowsheet solve the unit's rows take the N2 conversion X and the temperature rise "
        "dT as pinned coupling parameters and never call the external model; the coupled route "
        "iterates them against it (ADR 0034 D1, D2). No sensitivity through the external map "
        "(ADR 0034 D4)."
    )
    domain = (
        f"A vapour inlet only, on {PROVIDER_ID} under {REFERENCE_CONVENTION}; the experiment "
        f"refuses an inlet outside T {_range(hard['T_K'])} K, P {_range(hard['P_Pa'])} Pa, H2/N2 "
        f"{_range(hard['H2_N2'])}, inerts <= {float(hard['inert_max']):g}"
        + (
            ""
            if hard["tube_flow_mol_s"] is None
            else f", per-tube flow {_range(hard['tube_flow_mol_s'])} mol/s"
        )
        + f" (variant {variant_id}); outside the kinetics' data domain (T "
        f"{_range(data['T_K'])} K, P {_range(data['P_Pa'])} Pa, H2/N2 {_range(data['H2_N2'])}) "
        "its results are flagged extrapolated (ADR 0027 D9)."
    )
    conventions = (
        "The zero-pressure-drop convention, P_out = P_in, admissible iff |dP|/P_in <= "
        f"{float(boundary['eps_P']):g} (ADR 0027 D2); the outlet is the extent projection of the "
        "raw outlet (ADR 0027 D3)."
    )
    if variant["synthetic"]:
        conversion = float(variant["evaluation"]["conversion_N2"])
        return (
            f"SYNTHETIC: the external model is closed forms (xi = {conversion:g} n_N2,in per "
            "pass, T_out = T_in); it certifies nothing about the reactor or the chemistry, and "
            "is never listed as a supported reactor model (M01 spec §8.13, §17; R-199).",
            embedding,
            domain,
            conventions,
        )
    estimate = variant["accuracy"]["discretization_estimate"]
    return (
        embedding,
        f"Discretization at the design grid (num_z = {estimate['num_z']}), an estimate, not a "
        f"bound (M01 spec §10.1): xi high by {_percent(estimate['xi_high_rel'])}, NH3 out high "
        f"by {_percent(estimate['NH3_out_high_rel'])}, T_out low by "
        f"{_range(estimate['T_out_low_K'])} K.",
        domain,
        conventions,
        "F-R2: the kinetics evaluate their fugacity-coefficient correlations at the sum of the "
        "reactive partial pressures, not the total pressure (M01 spec §8.5); the group's model "
        "as pinned.",
        "F-R3: the pinned model imposes the inlet temperature as a Dirichlet condition with "
        "axial conduction, so 23-33 % of the reaction heat leaves through the inlet face; the "
        "process duty Q absorbs it (M01 spec §8.10).",
    )


def _percent(pair: Sequence[float]) -> str:
    return f"{100.0 * float(pair[0]):.1f}-{100.0 * float(pair[1]):.1f} %"


@dataclass(frozen=True)
class C1Reactor:
    """One C1 reactor in a flowsheet solve, at pinned coupling parameters (design note §4.1)."""

    unit_id: str
    #: `c1.reactor` or `c1.reactor_standin`.
    model: str
    provider: PropertyProvider
    context: EvaluationContext
    #: The bound variant's document (registered, hash-checked by the binder).
    variant: Mapping[str, Any] = field(repr=False)
    #: N_tubes: not a parameter of the inner problem (no row reads it); carried in the unit's
    #: configuration for the experiment request (design note §4.1).
    n_tubes: float
    #: X̂, the pinned N2 conversion (`<U>.coupling.X`).
    conversion: float
    #: ΔT̂, the pinned temperature rise in K (`<U>.coupling.dT`).
    temperature_rise: float
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if self.model not in MODEL_IDS:
            raise ValueError(f"{self.unit_id}: {self.model!r} is not a C1 reactor model id")
        if self.variant["model_id"] != self.model:
            raise ValueError(
                f"{self.unit_id}: variant {self.variant['variant_id']!r} is "
                f"{self.variant['model_id']!r}'s, not {self.model!r}'s"
            )
        c1_components(self.unit_id, self.components)
        c1_provider(self.unit_id, self.provider)
        convention = self.provider.describe().reference_convention
        if convention not in REACTION_CONSISTENT_CONVENTIONS:
            raise SpecificationError(
                f"{reference_convention_not_reaction_consistent(convention)}\n"
                f"{self.unit_id}: the provider's reference convention {convention!r} is not in "
                f"the registered reaction-consistent set {sorted(REACTION_CONSISTENT_CONVENTIONS)}"
            )
        if not self.n_tubes > 0.0:
            raise SpecificationError(f"{self.unit_id}: n_tubes {self.n_tubes!r} is not positive")

    @property
    def model_id(self) -> str:
        return self.model

    @property
    def extent(self) -> str:
        return extent_id(self.unit_id)

    def stoichiometry_parameter(self, component: str) -> str:
        return f"{self.unit_id}.nu.{component}"

    @property
    def conversion_parameter(self) -> str:
        return f"{self.unit_id}.coupling.X"

    @property
    def rise_parameter(self) -> str:
        return f"{self.unit_id}.coupling.dT"

    @property
    def synthetic(self) -> bool:
        return bool(self.variant["synthetic"])

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        hard = self.variant["boundary"]["hard_domain"]
        if self.synthetic:
            title = "C1 reactor, synthetic stand-in, embedded"
            description = (
                "SYNTHETIC stand-in for the C1 ammonia reactor in a flowsheet solve: the "
                "embedded rows at a pinned N2 conversion and temperature rise, coupled to closed "
                "forms in place of the group's reactor. It certifies nothing about the reactor."
            )
        else:
            title = "C1 ammonia reactor, embedded"
            description = (
                "The C1 ammonia reactor in a flowsheet solve: the embedded rows at a pinned N2 "
                "conversion and temperature rise, coupled to the pinned external reactor model "
                f"(variant {self.variant['variant_id']})."
            )
        return manifest_document(
            model_id=self.model,
            title=title,
            description=description,
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(_RESIDUALS, _EXTERNAL_MAP),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "At the pinned coupling parameters: xi = X n_N2,in, n_out = n_in + nu xi, "
                    "T_out = T_in + dT, P_out = P_in, Q = Hdot_out - Hdot_in; the external model "
                    "is not called."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("vapor", "zero_flow"),
                limitations=variant_limitations(self.model, self.variant),
                temperature_k=(float(hard["T_K"][0]), float(hard["T_K"][1])),
                pressure_pa=(float(hard["P_Pa"][0]), float(hard["P_Pa"][1])),
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="explicit_reduced" if self.synthetic else "experiment_provider",
            thread_safety="not_thread_safe",
            evaluation_cost_class="cheap" if self.synthetic else "expensive",
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
        inlet, outlet = wiring.one("inlet"), wiring.one("outlet")
        extent, duty = self.extent, duty_id(self.unit_id)
        blocks = [
            VapourEnthalpyFlow(self.provider, self.context, block_id=hdot_block_id(stream, "VAPOR"))
            for stream in (inlet, outlet)
        ]
        inlet_key, outlet_key = (f"{block.block_id}.{block.output_ids[0]}" for block in blocks)

        equations: list[EquationSpec] = [
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-mole", component),
                build=reaction_balance_row(
                    flow_id(inlet, component),
                    self.stoichiometry_parameter(component),
                    extent,
                    flow_id(outlet, component),
                ),
                accumulation="holdup_balance",
                origin=origin(self.model, "C1RX-mole"),
            )
            for component in self.components
        ]
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-extent"),
                build=extent_row(
                    extent,
                    self.conversion_parameter,
                    flow_id(inlet, KEY_COMPONENT),
                    self.stoichiometry_parameter(KEY_COMPONENT),
                ),
                accumulation="algebraic",
                origin=origin(self.model, "C1RX-extent"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-temperature"),
                # `outlet − inlet + offset` read with the inlet as its first term: T_in − T_out +
                # ΔT̂, so T_out = T_in + ΔT̂ (build log D45).
                build=offset_row(
                    temperature_id(inlet), temperature_id(outlet), self.rise_parameter
                ),
                accumulation="algebraic",
                origin=origin(self.model, "C1RX-temperature"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-pressure"),
                build=balance_row((pressure_id(inlet),), (pressure_id(outlet),)),
                accumulation="algebraic",
                origin=origin(self.model, "C1RX-pressure"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-duty"),
                build=energy_row((inlet_key,), (outlet_key,), source=duty),
                accumulation="holdup_balance",
                origin=origin(self.model, "C1RX-duty"),
            )
        )
        kinds: dict[str, QuantityKind] = {
            row_id(self.unit_id, "C1RX-mole", component): "molar_flow"
            for component in self.components
        }
        kinds[row_id(self.unit_id, "C1RX-extent")] = "molar_flow"
        kinds[row_id(self.unit_id, "C1RX-temperature")] = "temperature"
        kinds[row_id(self.unit_id, "C1RX-pressure")] = "pressure"
        kinds[row_id(self.unit_id, "C1RX-duty")] = "heat_rate"
        parameters = {
            self.stoichiometry_parameter(component): float(nu)
            for component, nu in zip(self.components, NU, strict=True)
        }
        parameters[self.conversion_parameter] = float(self.conversion)
        parameters[self.rise_parameter] = float(self.temperature_rise)
        return Contribution(
            variable_ids=(extent, duty),
            equations=tuple(equations),
            blocks=tuple(blocks),
            block_inputs={
                block.block_id: block_feeding(stream)
                for block, stream in zip(blocks, (inlet, outlet), strict=True)
            },
            parameter_ids=tuple(parameters),
            parameters=parameters,
            variable_kinds={extent: "molar_flow", duty: "heat_rate"},
            row_kinds=kinds,
        )

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        """The rows solved forward at the pinned coupling parameters, in the rows' arithmetic
        order: `ξ = X̂ n_N2,in / (−ν_N2)`, `n_out,i = n_in,i + ν_i ξ`, `T_out = T_in + ΔT̂`,
        `P_out = P_in`, `Q = Ḣ_out − Ḣ_in`. A dormant inlet gives a dormant outlet labelled
        `T_in + ΔT̂`, `ξ = 0` and `Q = 0` exactly. A flowing inlet or outlet that is not VAPOR by
        M01 §7 rule 3 is refused `vapour_phase_inadmissible` (§14.2 B16)."""
        connected = tuple(inlets.get("inlet", ()))
        if len(connected) != 1 or set(inlets) - {"inlet"}:
            raise SpecificationError(
                f"{self.unit_id}: a reactor takes exactly one inlet stream, got {inlets!r}"
            )
        feed = connected[0]
        if len(feed.n) != len(self.components):
            raise SpecificationError(
                f"{self.unit_id}: inlet carries {len(feed.n)} components, expected "
                f"{len(self.components)}"
            )
        temperature = feed.temperature + float(self.temperature_rise)
        if exactly_dormant(feed.n):
            return UnitEvaluation(
                status="ok",
                outlets={
                    "outlet": StreamState(
                        n=(0.0,) * len(self.components),
                        temperature=temperature,
                        pressure=feed.pressure,
                    )
                },
                duty=0.0,
                extent=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
            )
        key = self.components.index(KEY_COMPONENT)
        xi = float(self.conversion) * feed.n[key] / (-float(NU[key]))
        outlet = StreamState(
            n=tuple(flow + float(nu) * xi for flow, nu in zip(feed.n, NU, strict=True)),
            temperature=temperature,
            pressure=feed.pressure,
        )
        for where, stream in (("inlet", feed), ("outlet", outlet)):
            refused = vapour_refusal(self.provider, context, where, stream)
            if refused is not None:
                return refused
        h_in, failure = enthalpy_flow(self.provider, context, feed, "VAPOR")
        if failure is not None:
            return failure
        h_out, failure = enthalpy_flow(self.provider, context, outlet, "VAPOR")
        if failure is not None:
            return failure
        return UnitEvaluation(
            status="ok",
            outlets={"outlet": outlet},
            duty=h_out - h_in,
            extent=xi,
            phase_signature="VAPOR",
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )
