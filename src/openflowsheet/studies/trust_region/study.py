"""The C1 study's formulation `c1-trf-study-v1` (M05 design note §7.1; ADR 0039 D1, D2; R-267).

WO-5 builds the formulation and its projection; the loop, the parent checks and the records are
WO-6's. Everything here is **generated** from the bound revision, the bound variant's boundary
block and the admissibility definitions, never authored per case:

- **Case.** A revision binding of the C1 loop `C1-LOOP-M02-v1` (M02 design note §8.1), at the
  coupled route's inner problem: the embedded reactor pinned at w₀ (`with_coupling`, M02's
  accessor), its coupling parameters promoted to the link variables (X̂, ΔT̂) (ADR 0038 D3).
- **Decision.** The outlet-temperature specification of the `c1.tp_heater` that feeds the
  reactor (its `T_spec`, a pinned input, ADR 0031 D1), in a registered box: [643.15, 733.15] K for
  the REAL study (the kinetics' inlet data span, R-169), [653.15, 693.15] K for TR-E2 and the loops.
  The purge fraction stays the revision's (0.02).
- **Objective `c1-obj-nh3-liquid-v1`.** Maximize the NH₃ molar flow of the `c1.tp_flash`'s liquid
  outlet, mol/s, scale 1.
- **Constraints**, from the variant's `boundary.hard_domain` and M04 spec §3.2's A(s):
  T_in and P_in as bounds on the reactor-inlet variables; 1 ≤ H₂/N₂ ≤ 4 as lo·n_N₂ − n_H₂ ≤ 0 and
  n_H₂ − hi·n_N₂ ≤ 0; inerts as n_Ar + n_CH₄ − inert_max·Σn ≤ 0; for a variant with a per-tube
  flow bound, lo ≤ Σn/N_tubes ≤ hi; X̂ ≤ r/3 as 3 X̂ n_N₂ − n_H₂ ≤ 0. X̂ ∈ [0, 0.95] and
  ΔT̂ ∈ [−50, 250] K are the link variables' bounds, the provider's domain bounds every stream T
  and P, and molar flows are non-negative (the projection's own bounds, §6.1). Expression
  constraints carry the margin 1e-6 relative (`InequalitySpec.tightened`: none on a zero bound).
- **Stated limits, never constraints:** `extrapolated`, `synthetic`, `fd_gradient`,
  `surrogate_outside_reference_domain` (recorded by WO-6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from openflowsheet.adapters.variants import Variant, hard_domain
from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.compile.spec import Expr
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.models.c1.flash import TPFlash
from openflowsheet.models.c1.heater import TPHeater
from openflowsheet.models.c1.reactor import C1Reactor
from openflowsheet.studies.trust_region.holders import TruthModel
from openflowsheet.studies.trust_region.projection import (
    DecisionSpec,
    ExternalLinkSpec,
    InequalitySpec,
    ObjectiveSpec,
    Projection,
    project,
)
from openflowsheet.thermo.pr_c1 import COMPONENTS

__all__ = [
    "MARGIN_REL",
    "OBJECTIVE_ID",
    "REAL_BOX",
    "STUDY_ID",
    "TR_E2_BOX",
    "C1Formulation",
    "c1_formulation",
    "project_c1",
]

STUDY_ID: Final = "c1-trf-study-v1"
OBJECTIVE_ID: Final = "c1-obj-nh3-liquid-v1"
#: ADR 0039 D1: the REAL decision box (the kinetics' inlet data span, R-169), K.
REAL_BOX: Final = (643.15, 733.15)
#: ADR 0039 D2: TR-E2's and the loops' decision box, K.
TR_E2_BOX: Final = (653.15, 693.15)
#: §7.1: the relative margin on expression constraints.
MARGIN_REL: Final = 1e-6
#: §7.1: the objective's scale, mol/s.
OBJECTIVE_SCALE: Final = 1.0
_PROVIDER_KINDS: Final = {"T": "temperature", "P": "pressure"}


@dataclass(frozen=True)
class C1Formulation:
    """The projection's inputs for one C1 study, and where each came from."""

    reactor: str
    heater: str
    inlet_stream: str
    liquid_stream: str
    decisions: tuple[DecisionSpec, ...]
    external_links: tuple[ExternalLinkSpec, ...]
    inequalities: tuple[InequalitySpec, ...]
    objective: ObjectiveSpec
    #: The provider's declared domain by variable kind (§6.1 step 1).
    domain: Mapping[str, tuple[float, float]]
    #: The truth's hard domain on the reactor inlet's T and P (§7.1).
    variable_bounds: Mapping[str, tuple[float, float]]


def _only(found: Sequence[Any], what: str) -> Any:
    if len(found) != 1:
        raise ValueError(f"a C1 study needs exactly one {what}; the revision has {len(found)}")
    return found[0]


def _linear(terms: Sequence[tuple[float, str]]) -> Any:
    """A `RowBuilder` Σ c·v over variable ids."""

    def build(v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any) -> Expr:
        total: Any = 0.0
        for coefficient, name in terms:
            total = total + coefficient * v[name]
        return total

    return build


def c1_formulation(
    binding: RevisionBinding,
    variant: Variant,
    truth: TruthModel,
    box: tuple[float, float],
) -> C1Formulation:
    """`c1-trf-study-v1`'s formulation on `binding` (the C1 loop at the coupled route's inner
    problem) for the reactor bound to `variant` and evaluated by `truth`, with the decision box
    `box` (module docstring). Raises `ValueError` for a revision that is not C1-shaped."""
    flowsheet = binding.flowsheet
    reactor: C1Reactor = _only(
        [unit for unit in flowsheet.instances if isinstance(unit, C1Reactor)], "C1 reactor"
    )
    inlet = _only(flowsheet.wiring[reactor.unit_id].streams["inlet"], "reactor inlet")
    producer = binding.graph.producer_of(inlet)
    heater = _only(
        [
            unit
            for unit in flowsheet.instances
            if unit.unit_id == producer and isinstance(unit, TPHeater)
        ],
        "c1.tp_heater feeding the reactor",
    )
    flash: TPFlash = _only(
        [unit for unit in flowsheet.instances if isinstance(unit, TPFlash)], "c1.tp_flash"
    )
    liquid = _only(flowsheet.wiring[flash.unit_id].streams["liquid"], "flash liquid outlet")

    flows = [flow_id(inlet, name) for name in COMPONENTS]
    h2, n2, _, ar, ch4 = flows
    inlet_ids = (*flows, temperature_id(inlet), pressure_id(inlet))
    domain_block = hard_domain(variant)
    ratio_low, ratio_high = domain_block.h2_n2

    def inequality(
        name: str, build: Any, bound: float, source: str, sense: str = "<="
    ) -> InequalitySpec:
        return InequalitySpec(name, build, bound, source, MARGIN_REL, sense)  # type: ignore[arg-type]

    inequalities = [
        inequality(
            "hard_domain.h2_n2.lower",
            _linear([(ratio_low, n2), (-1.0, h2)]),
            0.0,
            "variant.boundary.hard_domain.H2_N2",
        ),
        inequality(
            "hard_domain.h2_n2.upper",
            _linear([(1.0, h2), (-ratio_high, n2)]),
            0.0,
            "variant.boundary.hard_domain.H2_N2",
        ),
        inequality(
            "hard_domain.inert_max",
            _linear(
                [(1.0, ar), (1.0, ch4)] + [(-domain_block.inert_fraction, name) for name in flows]
            ),
            0.0,
            "variant.boundary.hard_domain.inert_max",
        ),
    ]
    if domain_block.tube_flow is not None:
        per_tube = _linear([(1.0 / reactor.n_tubes, name) for name in flows])
        low, high = domain_block.tube_flow
        source = "variant.boundary.hard_domain.tube_flow_mol_s"
        inequalities.append(inequality("hard_domain.tube_flow.lower", per_tube, low, source, ">="))
        inequalities.append(inequality("hard_domain.tube_flow.upper", per_tube, high, source))
    conversion = reactor.conversion_parameter

    def h2_limit(
        v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
    ) -> Expr:
        return 3.0 * p[conversion] * v[n2] - v[h2]

    inequalities.append(inequality("admissibility.h2_limit", h2_limit, 0.0, "M04 spec §3.2 A(s)"))

    def objective(
        v: Mapping[str, Expr], b: Mapping[str, Expr], p: Mapping[str, Any], a: Any
    ) -> Expr:
        return v[flow_id(liquid, "NH3")]

    provider = flowsheet.provider.describe().domain
    return C1Formulation(
        reactor=reactor.unit_id,
        heater=heater.unit_id,
        inlet_stream=inlet,
        liquid_stream=liquid,
        decisions=(DecisionSpec(heater.temperature_parameter, box[0], box[1]),),
        external_links=(
            ExternalLinkSpec(reactor.unit_id, conversion, reactor.rise_parameter, inlet_ids, truth),
        ),
        inequalities=tuple(inequalities),
        objective=ObjectiveSpec(OBJECTIVE_ID, "maximize", objective, OBJECTIVE_SCALE),
        domain={
            _PROVIDER_KINDS[key]: (float(value[0]), float(value[1]))
            for key, value in provider.items()
        },
        variable_bounds={
            temperature_id(inlet): domain_block.temperature_k,
            pressure_id(inlet): domain_block.pressure_pa,
        },
    )


def project_c1(
    binding: RevisionBinding, x0: Mapping[str, float], formulation: C1Formulation
) -> Projection:
    """The C1 formulation projected at the state `x0` of `binding`'s inner problem (§6.1): the
    omitted rows are the certified alias elimination's (R-274), and the shape check is required
    (R-278: C1 is forward by construction)."""
    return project(
        binding.spec,
        x0,
        decisions=formulation.decisions,
        objective=formulation.objective,
        domain=formulation.domain,
        external_links=formulation.external_links,
        inequalities=formulation.inequalities,
        variable_bounds=formulation.variable_bounds,
    )
