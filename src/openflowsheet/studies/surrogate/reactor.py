"""`c1.reactor_surrogate`: M02's embedded C1 reactor with (X̂, ΔT̂) replaced by the frozen quadratic
of the scaled inlet (M04 spec §3.2, §8.1; ADR 0037 D1, D2; register R-240, R-241).

**The rows.** M02's extent-fixed rows (`models.c1.reactor`, design note §4.1) with the two pinned
coupling parameters replaced by the surrogate's prediction at the unit's own inlet:

- `C1RX-mole.<i>`: `n_in,i + ν_i ξ − n_out,i` (M02's, unchanged);
- `C1RX-extent`: `R_ξ = ξ − X̃(z(s)) n_N2,in` (kind `molar_flow`);
- `C1RX-temperature`: `R_T = (T_out − T_in) − ΔT̃(z(s))` (kind `temperature`), oriented as spec
  §3.3 states it, so that `∂R_T/∂T_out = +1` (M04.A12);
- `C1RX-pressure`, `C1RX-duty`: M02's, unchanged.

X̃ and ΔT̃ are one property block of the inlet stream, `<U>_surrogate`, whose values and Jacobian are
`quadratic.QuadraticSurrogate.predict` and `quadratic.inlet_sensitivity` (spec §3.3, closed form):
residual and Jacobian describe the same function wherever the input map is defined. Where it is not
(`n_N2 = 0` or `n_tot = 0` with a flow) the block raises `DomainError`
`surrogate_input_undefined(<U>)`, an invalid trial (spec §3.7). At an exactly dormant inlet the
surrogate is not evaluated: the block answers (X̃, ΔT̃) = (0, 0) with every derivative 0, so the rows
give ξ = 0 and T_out = T_in exactly (spec §3.7) — a convention on Newton's direction from a dormant
iterate, as B17's is, that moves no converged value (build log, WO-7).

**Identity.** The coefficients and N_tubes are compile-time constants of the instance: the block
holds them, and the binder reports the manifest's SHA-256 and N_tubes as the instance's
configuration, so they enter the flowsheet label and hence `model_version` (ADR 0002 D2.7). They are
deliberately not pinned inputs (`parameter_ids`): no row reads them symbolically, so a parametric
derivative with respect to them would be a silent zero (M03 D1/D2).

**Refusals** (spec §3.6) happen where a native unit's hard domain is judged: the causal evaluation
here (`out_of_domain`: `surrogate_input_undefined(<U>)`,
`surrogate_outside_hard_domain(<U>:<bound>)`, `surrogate_output_inadmissible(<U>:<X|dT>)`) and the
certificate's `SURROGATE-DOMAIN:<U>` check
(`verify.surrogate`). The rows themselves stay defined (polynomials), so Newton may pass through an
inadmissible iterate.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from openflowsheet.canonical import file_sha256
from openflowsheet.compile.spec import (
    DomainError,
    EquationSpec,
    Expr,
    PropertyBlock,
    QuantityKind,
    RowBuilder,
)
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
from openflowsheet.models.c1 import (
    COMPONENTS,
    MOLAR_FLOW,
    NU,
    PROVIDER_ID,
    REFERENCE_CONVENTION,
    TEMPERATURE,
)
from openflowsheet.models.c1 import reactor as embedded
from openflowsheet.models.c1.blocks import (
    VapourEnthalpyFlow,
    block_feeding,
    exactly_dormant,
    hdot_block_id,
)
from openflowsheet.models.c1.units import (
    c1_components,
    c1_provider,
    enthalpy_flow,
    vapour_refusal,
)
from openflowsheet.models.rows import balance_row, energy_row, reaction_balance_row
from openflowsheet.models.syn001.conversion_reactor import extent_id
from openflowsheet.studies.surrogate.plan import coordinates, scaled
from openflowsheet.studies.surrogate.quadratic import (
    QuadraticSurrogate,
    causal_outlet,
    inlet_sensitivity,
)
from openflowsheet.studies.surrogate.study import MODEL_ID
from openflowsheet.thermo import PropertyProvider, StreamState
from openflowsheet.thermo.conventions import (
    REACTION_CONSISTENT_CONVENTIONS,
    reference_convention_not_reaction_consistent,
)

__all__ = [
    "EQUATIONS",
    "HARD_BOUNDS",
    "MODEL_ID",
    "PORTS",
    "C1ReactorSurrogate",
    "SurrogateBlock",
    "hard_domain_bounds",
    "surrogate_of",
]

#: The surrogate's ports are M02's embedded unit's (spec §8.1).
PORTS: Final[tuple[Port, ...]] = embedded.PORTS
#: The key reactant of `C1RX-extent`: X̃ is a conversion of N2.
KEY_COMPONENT: Final = embedded.KEY_COMPONENT
#: The hard-domain bounds in the order the refusal names them (spec §3.6): the tokens of
#: `surrogate_outside_hard_domain(<U>:<bound>)`.
HARD_BOUNDS: Final[tuple[str, ...]] = ("T", "P", "H2_N2", "inerts", "F_tube")

_SOURCE: Final = (
    "docs/derivations/M04-spec.md §3.2, §8.1; "
    "docs/adr/0037-m04-surrogate-unit-promotion-and-rollback.md D1"
)
_BLOCK_TOKEN: Final = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*$")
_N2: Final = COMPONENTS.index(KEY_COMPONENT)
_INPUTS: Final = len(COMPONENTS) + 2


def _replaced(equation: DeclaredEquation) -> DeclaredEquation:
    """M02's declaration, or the surrogate's for the two rows it replaces (spec §3.2)."""
    if equation.equation_id == "C1RX-extent":
        return DeclaredEquation(
            equation_id="C1RX-extent",
            statement=(
                "xi - X(z(inlet)) n_N2,in = 0, X the frozen full quadratic of the scaled inlet "
                "(M04 spec §3.1-§3.4), its coefficients the instance's SurrogateManifest's"
            ),
            dependencies=("inlet.state", "extent.xi"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=MOLAR_FLOW,
            source=_SOURCE,
        )
    if equation.equation_id == "C1RX-temperature":
        return DeclaredEquation(
            equation_id="C1RX-temperature",
            statement=(
                "(T_out - T_in) - dT(z(inlet)) = 0, dT the frozen full quadratic of the scaled "
                "inlet (K); xi = 0 and T_out = T_in exactly at a dormant inlet (M04 spec §3.7)"
            ),
            dependencies=("inlet.state", "outlet.state.T"),
            conditional_class="unconditional",
            accumulation=Accumulation(kind="algebraic"),
            dimension=TEMPERATURE,
            source=_SOURCE,
        )
    return equation


#: M02's five row families with the two coupling rows replaced (spec §3.2); the accumulation
#: declarations are M02's (spec §8.1).
EQUATIONS: Final[tuple[DeclaredEquation, ...]] = tuple(_replaced(e) for e in embedded.EQUATIONS)

_RESIDUALS: Final = DerivativeDeclaration(
    output="residuals",
    with_respect_to=("free_variables",),
    method="analytic",
    regime="all",
    notes="closed form: the quadratic's gradient composed with the input map (M04 spec §3.3)",
)
_SURROGATE_MAP: Final = DerivativeDeclaration(
    output="outlet.state",
    with_respect_to=("inlet.state",),
    method="analytic",
    regime="all",
    notes=(
        "derivative of the surrogate; agreement with the parent is the gradient metric of its "
        "manifest"
    ),
)


def _artifact_hash() -> str:
    """The module source's SHA-256. Not cached (T07 G20 counts caches)."""
    return file_sha256(Path(__file__))


def surrogate_of(manifest: Mapping[str, Any]) -> QuadraticSurrogate:
    """The frozen predictor of a SurrogateManifest (`predictor.coefficients`, basis order)."""
    coefficients = manifest["predictor"]["coefficients"]
    return QuadraticSurrogate(
        coefficients_x=tuple(float(b) for b in coefficients["X"]),
        coefficients_dt=tuple(float(b) for b in coefficients["dT_K"]),
    )


def _within(value: float, bounds: Sequence[float]) -> bool:
    return float(bounds[0]) <= value <= float(bounds[1])


def hard_domain_bounds(
    inlet: StreamState, hard: Mapping[str, Any], n_tubes: float
) -> tuple[str, ...]:
    """The bounds of the parent's hard domain (`domain.hard`, a verbatim copy of the variant's
    `boundary.hard_domain`) a flowing inlet violates, as `HARD_BOUNDS` tokens. The predicates are
    the parent's own (`models.c1.boundary.hard_domain_violations`): inclusive bounds, H2/N2
    division-free (no N2 is outside every ratio bound), inerts `n_Ar + n_CH4 ≤ max · n_tot`,
    per-tube flow `n_tot / N_tubes` when the parent bounds it."""
    n = inlet.n
    total = inlet.total_flow
    violated = []
    if not _within(inlet.temperature, hard["T_K"]):
        violated.append("T")
    if not _within(inlet.pressure, hard["P_Pa"]):
        violated.append("P")
    low, high = (float(b) for b in hard["H2_N2"])
    if not (n[1] > 0.0 and low * n[1] <= n[0] <= high * n[1]):
        violated.append("H2_N2")
    if not (n[3] + n[4]) <= float(hard["inert_max"]) * total:
        violated.append("inerts")
    flow = hard.get("tube_flow_mol_s")
    if flow is not None and not _within(total / n_tubes, flow):
        violated.append("F_tube")
    return tuple(violated)


class SurrogateBlock:
    """`<U>_surrogate`: (X̃, ΔT̃) of the inlet stream's `(n, T, P)`, densely declared (spec §3.3).

    Values `QuadraticSurrogate.predict(z(s))`; Jacobian `inlet_sensitivity`'s chain rule. Exactly
    dormant: (0, 0) with every derivative 0 (the surrogate not evaluated, spec §3.7). Input map
    undefined: `DomainError` (`surrogate_input_undefined(<U>)`).
    """

    def __init__(
        self, unit_id: str, surrogate: QuadraticSurrogate, n_tubes: float, *, block_id: str
    ) -> None:
        self._unit_id = unit_id
        self._surrogate = surrogate
        self._n_tubes = n_tubes
        self._block_id = block_id

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return (*(f"n_{c}" for c in COMPONENTS), "T", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return ("X", "dT")

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((row, column) for row in range(2) for column in range(_INPUTS))

    @staticmethod
    def _state(inputs: Sequence[float]) -> StreamState:
        return StreamState(
            n=tuple(float(value) for value in inputs[: len(COMPONENTS)]),
            temperature=float(inputs[len(COMPONENTS)]),
            pressure=float(inputs[len(COMPONENTS) + 1]),
        )

    def _undefined(self) -> DomainError:
        return DomainError(f"{self._block_id}: surrogate_input_undefined({self._unit_id})")

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        state = self._state(inputs)
        if exactly_dormant(state.n):
            return [0.0, 0.0]
        u = coordinates(state, self._n_tubes)
        if u is None:
            raise self._undefined()
        x, dt = self._surrogate.predict(scaled(u))
        return [x, dt]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        state = self._state(inputs)
        if exactly_dormant(state.n):
            return [(row, column, 0.0) for row, column in self.jacobian_pattern()]
        sensitivity = inlet_sensitivity(self._surrogate, state, self._n_tubes)
        if sensitivity is None:
            raise self._undefined()
        return [
            *((0, column, value) for column, value in enumerate(sensitivity.dx_ds)),
            *((1, column, value) for column, value in enumerate(sensitivity.ddt_ds)),
        ]


def _extent_row(extent: str, conversion: str, key_flow: str) -> RowBuilder:
    """`ξ − X̃ n_N2,in`, the arithmetic of `quadratic.extent_rows` (spec §3.2)."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Any,
    ) -> Expr:
        return variables[extent] - blocks[conversion] * variables[key_flow]

    return build


def _rise_row(inlet: str, outlet: str, rise: str) -> RowBuilder:
    """`(T_out − T_in) − ΔT̃`, oriented as spec §3.3 states it (`∂R_T/∂T_out = +1`)."""

    def build(
        variables: Mapping[str, Expr],
        blocks: Mapping[str, Expr],
        parameters: Mapping[str, float],
        algebra: Any,
    ) -> Expr:
        return (variables[outlet] - variables[inlet]) - blocks[rise]

    return build


@dataclass(frozen=True)
class C1ReactorSurrogate:
    """One surrogate-backed C1 reactor in a flowsheet solve (spec §8.1)."""

    unit_id: str
    provider: PropertyProvider
    context: EvaluationContext
    #: The instance's SurrogateManifest, resolved by the binder by its SHA-256 and checked.
    surrogate_manifest: Mapping[str, Any] = field(repr=False)
    #: `model.artifact_ref`: the manifest's SHA-256 (spec §8.2).
    manifest_sha256: str
    #: N_tubes: the surrogate's per-tube flow is `n_tot / N_tubes` (spec §3.1).
    n_tubes: float
    components: tuple[str, ...] = COMPONENTS

    def __post_init__(self) -> None:
        if self.surrogate_manifest["model_id"] != MODEL_ID:
            raise ValueError(
                f"{self.unit_id}: manifest {self.surrogate_manifest['surrogate_id']!r} is "
                f"{self.surrogate_manifest['model_id']!r}'s, not {MODEL_ID!r}'s"
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
        if not _BLOCK_TOKEN.match(self.unit_id):
            raise SpecificationError(
                f"instance id {self.unit_id!r} cannot name a property block. The backend accepts "
                "a letter followed by letters, digits and non-consecutive underscores"
            )

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def surrogate_id(self) -> str:
        return str(self.surrogate_manifest["surrogate_id"])

    @property
    def synthetic(self) -> bool:
        return bool(self.surrogate_manifest["synthetic"])

    @property
    def surrogate(self) -> QuadraticSurrogate:
        return surrogate_of(self.surrogate_manifest)

    @property
    def hard_domain(self) -> Mapping[str, Any]:
        """The parent's hard domain, as the manifest copies it (spec §3.6)."""
        hard: Mapping[str, Any] = self.surrogate_manifest["domain"]["hard"]
        return hard

    @property
    def extent(self) -> str:
        return extent_id(self.unit_id)

    @property
    def block_id(self) -> str:
        return f"{self.unit_id}_surrogate"

    def stoichiometry_parameter(self, component: str) -> str:
        return f"{self.unit_id}.nu.{component}"

    def ports(self) -> tuple[Port, ...]:
        return PORTS

    def declared_equations(self) -> tuple[DeclaredEquation, ...]:
        return EQUATIONS

    def manifest(self) -> Mapping[str, Any]:
        hard = self.hard_domain
        label = "SYNTHETIC " if self.synthetic else ""
        return manifest_document(
            model_id=MODEL_ID,
            title=f"C1 reactor, {label.lower()}surrogate {self.surrogate_id}",
            description=(
                f"{label}surrogate of the C1 ammonia reactor in a flowsheet solve: M02's embedded "
                "rows with the N2 conversion and the temperature rise given by a frozen full "
                "quadratic of the scaled inlet, pinned by its SurrogateManifest's SHA-256 "
                f"{self.manifest_sha256}; it never calls the parent "
                f"{self.surrogate_manifest['parent']['variant_id']}."
            ),
            ports=PORTS,
            equations=EQUATIONS,
            derivatives=(_RESIDUALS, _SURROGATE_MAP),
            initialization=Initialization(
                strategy="local_initializer",
                notes=(
                    "At the frozen quadratic of the scaled inlet: xi = X n_N2,in, n_out = n_in + "
                    "nu xi, T_out = T_in + dT, P_out = P_in, Q = Hdot_out - Hdot_in; refused "
                    "outside the parent's hard domain or the admissible output set."
                ),
            ),
            validity=Validity(
                components=self.components,
                phases=("vapor", "zero_flow"),
                limitations=tuple(str(q) for q in self.surrogate_manifest["qualifications"]),
                temperature_k=(float(hard["T_K"][0]), float(hard["T_K"][1])),
                pressure_pa=(float(hard["P_Pa"][0]), float(hard["P_Pa"][1])),
            ),
            module=__name__,
            artifact_hash=_artifact_hash(),
            execution_class="explicit_reduced",
            thread_safety="not_thread_safe",
            evaluation_cost_class="cheap",
            property_provider=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
            package="M04",
        )

    def contribute(self, wiring: Wiring, components: Sequence[str]) -> Contribution:
        if tuple(components) != self.components:
            raise SpecificationError(
                f"{self.unit_id}: wired into components {tuple(components)}, built for "
                f"{self.components}"
            )
        inlet, outlet = wiring.one("inlet"), wiring.one("outlet")
        extent, duty = self.extent, duty_id(self.unit_id)
        enthalpies = [
            VapourEnthalpyFlow(self.provider, self.context, block_id=hdot_block_id(stream, "VAPOR"))
            for stream in (inlet, outlet)
        ]
        inlet_key, outlet_key = (f"{block.block_id}.{block.output_ids[0]}" for block in enthalpies)
        surrogate = SurrogateBlock(
            self.unit_id, self.surrogate, float(self.n_tubes), block_id=self.block_id
        )

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
                origin=origin(MODEL_ID, "C1RX-mole"),
            )
            for component in self.components
        ]
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-extent"),
                build=_extent_row(extent, f"{self.block_id}.X", flow_id(inlet, KEY_COMPONENT)),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "C1RX-extent"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-temperature"),
                build=_rise_row(
                    temperature_id(inlet), temperature_id(outlet), f"{self.block_id}.dT"
                ),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "C1RX-temperature"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-pressure"),
                build=balance_row((pressure_id(inlet),), (pressure_id(outlet),)),
                accumulation="algebraic",
                origin=origin(MODEL_ID, "C1RX-pressure"),
            )
        )
        equations.append(
            EquationSpec(
                equation_id=row_id(self.unit_id, "C1RX-duty"),
                build=energy_row((inlet_key,), (outlet_key,), source=duty),
                accumulation="holdup_balance",
                origin=origin(MODEL_ID, "C1RX-duty"),
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
        blocks: tuple[PropertyBlock, ...] = (*enthalpies, surrogate)
        return Contribution(
            variable_ids=(extent, duty),
            equations=tuple(equations),
            blocks=blocks,
            block_inputs={
                **{
                    block.block_id: block_feeding(stream)
                    for block, stream in zip(enthalpies, (inlet, outlet), strict=True)
                },
                surrogate.block_id: block_feeding(inlet),
            },
            parameter_ids=tuple(parameters),
            parameters=parameters,
            variable_kinds={extent: "molar_flow", duty: "heat_rate"},
            row_kinds=kinds,
        )

    def _refused(self, reasons: Sequence[str]) -> UnitEvaluation:
        return UnitEvaluation(
            status="out_of_domain",
            message="; ".join(reasons),
            reference_convention=REFERENCE_CONVENTION,
        )

    def evaluate(
        self, inlets: Mapping[str, Sequence[StreamState]], context: EvaluationContext
    ) -> UnitEvaluation:
        """The rows solved forward at the surrogate (`quadratic.causal_outlet`): `ξ = X̃ n_N2,in`,
        `n_out = n_in + ν ξ` (inerts bitwise), `T_out = T_in + ΔT̃`, `P_out = P_in`,
        `Q = Ḣ_out − Ḣ_in`. A dormant inlet gives a dormant outlet at `T_in`, `ξ = 0` and `Q = 0`
        exactly (spec §3.7). Refused `out_of_domain` (spec §3.6, §3.7), in this order: no defined
        input (`surrogate_input_undefined(<U>)`); outside the parent's hard domain
        (`surrogate_outside_hard_domain(<U>:<bound>)` per bound); a prediction outside A(s)
        (`surrogate_output_inadmissible(<U>:<X|dT>)` per output). A flowing inlet or outlet that is
        not VAPOR is refused as M02's embedded unit refuses it (§14.2 B16)."""
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
        if exactly_dormant(feed.n):
            return UnitEvaluation(
                status="ok",
                outlets={
                    "outlet": StreamState(
                        n=(0.0,) * len(self.components),
                        temperature=feed.temperature,
                        pressure=feed.pressure,
                    )
                },
                duty=0.0,
                extent=0.0,
                phase_signature="ZERO_FLOW",
                reference_convention=REFERENCE_CONVENTION,
            )
        found = causal_outlet(self.surrogate, feed, float(self.n_tubes))
        if found.status == "input_undefined":
            return self._refused([f"surrogate_input_undefined({self.unit_id})"])
        bounds = hard_domain_bounds(feed, self.hard_domain, float(self.n_tubes))
        if bounds:
            return self._refused(
                [f"surrogate_outside_hard_domain({self.unit_id}:{bound})" for bound in bounds]
            )
        if found.inadmissible:
            return self._refused(
                [
                    f"surrogate_output_inadmissible({self.unit_id}:{output})"
                    for output in found.inadmissible
                ]
            )
        assert found.n_out is not None and found.outlet_temperature is not None
        assert found.xi is not None
        outlet = StreamState(
            n=found.n_out, temperature=found.outlet_temperature, pressure=feed.pressure
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
            extent=found.xi,
            phase_signature="VAPOR",
            provider_id=PROVIDER_ID,
            reference_convention=REFERENCE_CONVENTION,
        )
