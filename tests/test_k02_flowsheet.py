"""K02: the six units composed into the SYN-001 flowsheet.

This is the composition evidence the individual unit tests cannot give. A unit can be right at
its own boundary and still be wired wrongly, mix up a stream, or disagree with its neighbour
about a pressure. Three independent checks catch that:

1. **The tear residual at the oracle's fixed point.** Blueprint §7.2 defines the recycle map's
   residual as `R(t) = G(t) - t`. At Fable's 20-digit converged recycle, one sequential pass
   through feed, mixer, heater, flash and splitter must return that same recycle to the
   registered component tolerance. Nothing here solves for it — the damped Newton is K03's.
2. **The overall balances**, which no single unit can satisfy on its own: fresh feed equals
   vapour product plus purge, and `Q_h + Q_f` equals the external products' enthalpy minus the
   fresh feed's (derivation §6). Blueprint A09 label: the energy identity shares SYN-001's
   thermodynamics with the units it checks, so it verifies bookkeeping, not enthalpy data.
3. **Recycle invariance**, the metamorphic check plan §3.2 registers: because the flash recycles
   its own saturated liquid at the same T and P, V, x and y are the same for every r and only L
   scales as `1/(1 - r)`. A unit that leaked recycle composition into the product would break it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compile.reference import row_values, state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import flow_id, origin, pressure_id, row_id, temperature_id
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.flowsheet import (
    FLASH_UNIT,
    HEATER_UNIT,
    STREAMS,
    Syn001Flowsheet,
)
from openflowsheet.models.syn001.mixer import BEHAVIOURAL_EQUATIONS
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.syn001 import Syn001Provider

CONTEXT = EvaluationContext(
    model_version="K02-unit-evaluator@" + "0" * 64, constants_sha256="0" * 64
)

#: ADR 0001 D6, registered for SYN-001 only. The energy tolerance is 1.01e-3 W: 1e-8 x 1e5 is
#: 1e-3, not 1e-4.
FLOW_TOLERANCE = 1e-9 + 1e-8 * 3.0
ENERGY_TOLERANCE = 1e-5 + 1e-8 * 1e5
TEMPERATURE_TOLERANCE = 1e-6
PRESSURE_TOLERANCE = 1e-2
COMPOSITION_TOLERANCE = 1e-10

CASE_IDS = [
    "SYN-001-nominal",
    "SYN-001-once-through",
    "SYN-001-high-recycle",
    "SYN-001-all-liquid-310K",
    "SYN-001-all-vapor-420K",
]


def variants(reference_values: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {entry["case_id"]: entry for entry in reference_values["variants"]}


def flowsheet_for(case: Mapping[str, Any]) -> Syn001Flowsheet:
    return Syn001Flowsheet(
        provider=Syn001Provider(),
        context=CONTEXT,
        split_fraction=float(case["r"]),
        flash_temperature=float(case["T_flash_K"]),
        heater_temperature=float(case["T_heater_K"]),
        pressure=float(case["P_Pa"]),
    )


def reference_recycle(case: Mapping[str, Any]) -> StreamState:
    return StreamState(
        n=tuple(float(value) for value in case["recycle_mol_per_s"]),
        temperature=float(case["T_flash_K"]),
        pressure=float(case["P_Pa"]),
    )


# ----------------------------------------------------------------- the tear at its fixed point


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_tear_residual_vanishes_at_the_reference_recycle(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """`R(t*) = G(t*) - t* = 0` at Fable's 20-digit converged recycle, for every variant.

    The strongest composition evidence K02 can produce without a solver: it is zero only if every
    unit is right *and* they are wired to the right streams in the right order.
    """
    case = variants(reference_values)[case_id]
    flowsheet = flowsheet_for(case)
    traversal = flowsheet.traverse(reference_recycle(case))
    assert traversal.status == "ok", traversal.message
    assert traversal.recycle_residual is not None
    for component, residual in zip(COMPONENTS, traversal.recycle_residual, strict=True):
        assert abs(residual) < FLOW_TOLERANCE, f"{case_id} {component}: R = {residual}"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_registered_stream_reaches_its_registered_phase(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """Derivation §7's table, stream by stream, including the three exactly dormant ones."""
    case = variants(reference_values)[case_id]
    traversal = flowsheet_for(case).traverse(reference_recycle(case))
    assert traversal.status == "ok", traversal.message
    assert traversal.phase_signatures["S2"] == case["mixer_outlet_state"]
    assert traversal.phase_signatures["S3"] == case["heater_outlet_state"]
    assert traversal.phase_signatures["S4"] == case["vapor_product_phase_signature"]
    assert traversal.phase_signatures["S6"] == case["recycle_phase_signature"]
    assert traversal.phase_signatures["S7"] == case["purge_phase_signature"]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_traversed_streams_match_the_reference(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    case = variants(reference_values)[case_id]
    traversal = flowsheet_for(case).traverse(reference_recycle(case))
    assert traversal.status == "ok", traversal.message

    for index, value in enumerate(case["vapor_product_mol_per_s"]):
        assert traversal.streams["S4"].n[index] == pytest.approx(float(value), abs=FLOW_TOLERANCE)
    for index, value in enumerate(case["purge_mol_per_s"]):
        assert traversal.streams["S7"].n[index] == pytest.approx(float(value), abs=FLOW_TOLERANCE)
    assert traversal.streams["S2"].temperature == pytest.approx(float(case["T_mix_K"]), abs=1e-6)
    assert traversal.duties[HEATER_UNIT] == pytest.approx(
        float(case["Q_heater_W"]), abs=ENERGY_TOLERANCE
    )
    assert traversal.duties[FLASH_UNIT] == pytest.approx(
        float(case["Q_flash_W"]), abs=ENERGY_TOLERANCE
    )


# ------------------------------------------------------------------------- overall balances


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_fresh_feed_equals_vapor_product_plus_purge(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """Plan §3.2's overall component balance. No single unit can satisfy it."""
    case = variants(reference_values)[case_id]
    flowsheet = flowsheet_for(case)
    traversal = flowsheet.traverse(reference_recycle(case))
    assert traversal.status == "ok", traversal.message
    for index in range(len(COMPONENTS)):
        out = traversal.streams["S4"].n[index] + traversal.streams["S7"].n[index]
        assert out == pytest.approx(flowsheet.feed_flows[index], abs=FLOW_TOLERANCE)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_total_duty_equals_products_minus_fresh_feed(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """Derivation §6, for every r: the internal recycle enthalpy cancels.

    Blueprint A09: this shares SYN-001's thermodynamics with the units it checks. It verifies
    bookkeeping, not enthalpy data, and is labelled as such.
    """
    case = variants(reference_values)[case_id]
    traversal = flowsheet_for(case).traverse(reference_recycle(case))
    total = traversal.duties[HEATER_UNIT] + traversal.duties[FLASH_UNIT]
    assert total == pytest.approx(float(case["Q_total_W"]), abs=ENERGY_TOLERANCE)
    assert total == pytest.approx(float(case["H_products_minus_H_fresh_W"]), abs=ENERGY_TOLERANCE)


def test_recycle_invariance_across_r(reference_values: Mapping[str, Any]) -> None:
    """Plan §3.2's registered metamorphic check, derived in §5.1.

    V, x and y are identical for every r and only L scales as 1/(1 - r). Checked across the three
    registered ratios at once, so a unit that leaked recycle composition into the product would
    break it even if each variant passed its own reference comparison.
    """
    cases = variants(reference_values)
    observed = {}
    for case_id in ("SYN-001-once-through", "SYN-001-nominal", "SYN-001-high-recycle"):
        case = cases[case_id]
        traversal = flowsheet_for(case).traverse(reference_recycle(case))
        assert traversal.status == "ok", traversal.message
        vapor, liquid = traversal.streams["S4"], traversal.streams["S5"]
        observed[float(case["r"])] = (
            sum(vapor.n),
            sum(liquid.n),
            tuple(value / sum(vapor.n) for value in vapor.n),
            tuple(value / sum(liquid.n) for value in liquid.n),
        )

    base_v, base_l, base_y, base_x = observed[0.0]
    for recycle_fraction, (total_v, total_l, y, x) in observed.items():
        assert total_v == pytest.approx(base_v, abs=FLOW_TOLERANCE), recycle_fraction
        assert total_l == pytest.approx(
            base_l / (1.0 - recycle_fraction), abs=FLOW_TOLERANCE / (1.0 - recycle_fraction)
        ), recycle_fraction
        for index in range(len(COMPONENTS)):
            assert y[index] == pytest.approx(base_y[index], abs=COMPOSITION_TOLERANCE)
            assert x[index] == pytest.approx(base_x[index], abs=COMPOSITION_TOLERANCE)


def test_the_retired_guess_is_refused_by_the_mixer(
    reference_values: Mapping[str, Any],
) -> None:
    """The measured fact behind registered case `SYN-001-inadmissible-guess`.

    P01 registered `recycle_i = r F_i` as the tear initializer and plan §3.2 fixes that stream at
    the flash temperature. At r = 0.5 that is an **equimolar stream at 360 K**, above its
    347.44 K bubble point (`sum_zK_fresh` = 1.3837 in the reference's own values), so the v0.0
    mixer refuses it — a damped Newton started there fails on its *first* residual evaluation.

    K02 found that and reported it rather than loosening the mixer. Fable retired the guess
    (decision register **R-014**, Frank's call) and registered the refusal as its own case, so
    the guess survives here only as the thing that must be refused: blueprint §7.4 requires every
    initializer candidate to be *checked*, and this is the candidate that fails the check.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    flowsheet = flowsheet_for(case)
    retired = flowsheet.retired_guess()
    assert retired.n == (0.5, 0.5, 0.5)
    assert retired.temperature == 360.0

    traversal = flowsheet.traverse(retired)
    assert traversal.status == "unsupported"
    assert "T05" in traversal.message
    assert traversal.message.startswith("U-MIX:")
    assert traversal.recycle_residual is None


def test_the_registered_initializer_is_admissible_at_every_variant(
    reference_values: Mapping[str, Any],
) -> None:
    """`SYN-001-tear-init-v2`: `t0 = G(0)`, one pass from a dormant recycle, `= (1 - r) t*`.

    Derivation §9's registered values, and the property that made it the registered choice: it
    traverses at every variant, where the retired guess does not at three of five.
    """
    for case_id in CASE_IDS:
        case = variants(reference_values)[case_id]
        flowsheet = flowsheet_for(case)
        guess = flowsheet.initial_recycle()
        star = reference_recycle(case)
        recycle_fraction = float(case["r"])
        for index in range(len(COMPONENTS)):
            assert guess.n[index] == pytest.approx(
                (1.0 - recycle_fraction) * star.n[index], abs=FLOW_TOLERANCE
            ), case_id
        assert flowsheet.traverse(guess).status == "ok", case_id


def test_a_scaled_tear_leaves_a_residual_the_fixed_point_test_would_not(
    reference_values: Mapping[str, Any],
) -> None:
    """Anti-vacuity for the fixed-point test: an off-solution tear must give a large residual.

    Scaling the converged recycle keeps its composition, so the mixer still accepts it, and the
    traversal completes. If the residual were small here too, the fixed-point test above would be
    satisfied by an implementation that ignored its input.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    flowsheet = flowsheet_for(case)
    star = reference_recycle(case)
    halved = StreamState(
        n=tuple(0.5 * value for value in star.n),
        temperature=star.temperature,
        pressure=star.pressure,
    )
    traversal = flowsheet.traverse(halved)
    assert traversal.status == "ok", traversal.message
    assert traversal.recycle_residual is not None
    assert max(abs(value) for value in traversal.recycle_residual) > 0.07


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_tear_map_is_exactly_affine_along_the_ray_through_its_fixed_point(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """`R(s t*) = (1 - r)(1 - s) t*`, derived and then measured at eight scale factors.

    **The derivation.** `t*` is `r L* x`, where `x` is the flash *liquid* composition — a
    saturated liquid at the flash state. Adding material of exactly that composition to a
    two-phase mixture at the same temperature and pressure adds nothing that can vaporize: the
    vapour phase is untouched, `x` and `y` are unchanged, and the liquid grows by exactly the
    amount added. So `V(s) = V*`, `x(s) = x`, and `L(s) = L(0) + s r L*`. At the fixed point
    `L* = L(0) + r L*`, hence `L(0) = (1 - r) L*` and `L(s) = L* [(1 - r) + s r]`. Then

        G(s t*) = r L(s) x = [(1 - r) + s r] t*,   R(s t*) = G - s t* = (1 - r)(1 - s) t*.

    **Why it is worth a test.** It exercises the whole flowsheet at eight *non-solution* states
    per variant against a closed-form expectation, where the fixed-point test gives one state and
    the answer zero. A unit that quietly renormalized a composition, or a splitter that mixed up
    its two outlets, would satisfy the fixed point and fail this.

    It is also the same physics as the mixer's saturated-recycle finding, seen from the other
    side: the relation holds *because* the recycle is exactly at its bubble point.
    """
    case = variants(reference_values)[case_id]
    recycle_fraction = float(case["r"])
    flowsheet = flowsheet_for(case)
    star = reference_recycle(case)
    scale = max(abs(value) for value in star.n)

    for factor in (0.0, 0.2, 0.45, 0.9, 1.0, 1.3, 2.5, 4.0):
        guess = StreamState(
            n=tuple(factor * value for value in star.n),
            temperature=star.temperature,
            pressure=star.pressure,
        )
        traversal = flowsheet.traverse(guess)
        assert traversal.status == "ok", f"s={factor}: {traversal.message}"
        assert traversal.recycle_residual is not None
        for index, residual in enumerate(traversal.recycle_residual):
            expected = (1.0 - recycle_fraction) * (1.0 - factor) * star.n[index]
            assert residual == pytest.approx(expected, abs=1e-12 * max(scale, 1.0)), (
                f"{case_id} s={factor} {COMPONENTS[index]}"
            )


def test_a_zero_recycle_traverses_and_is_its_own_fixed_point(
    reference_values: Mapping[str, Any],
) -> None:
    """r = 0: the recycle is exactly dormant and stays exactly dormant. ADR 0001 D3.5."""
    case = variants(reference_values)["SYN-001-once-through"]
    flowsheet = flowsheet_for(case)
    assert flowsheet.initial_recycle().n == (0.0, 0.0, 0.0)
    assert flowsheet.retired_guess().n == (0.0, 0.0, 0.0), "at r = 0 the two coincide"
    traversal = flowsheet.traverse(flowsheet.initial_recycle())
    assert traversal.status == "ok", traversal.message
    assert traversal.recycle_residual == (0.0, 0.0, 0.0)
    assert traversal.computed_recycle is not None
    assert traversal.computed_recycle.is_dormant


# --------------------------------------------------------------------- the assembled system


def test_the_assembled_flowsheet_compiles_and_has_the_declared_shape(
    reference_values: Mapping[str, Any],
) -> None:
    """Seven streams of five variables, nine heater-owned, three flash-owned; forty-nine rows.

    The counts are written out rather than derived from the objects under test, so an added or
    dropped row is visible here.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    spec = flowsheet_for(case).spec()
    spec.validate()
    assert len(STREAMS) == 7
    assert len(spec.variable_ids) == 7 * 5 + 9 + 3 == 47
    # feed 5, mixer 6, heater 14, flash 14, splitter 10, two sinks 0.
    assert len(spec.equations) == 5 + 6 + 14 + 14 + 10 == 49
    compile_problem(spec)


def test_the_declared_rows_over_determine_the_pressure_network_by_two(
    reference_values: Mapping[str, Any],
) -> None:
    """Measured and recorded, not repaired. This is a finding handed to K03, not a bug in K02.

    Seven pressure variables carry nine declared pressure rows: the feed specifies one, the mixer
    equates both inlets to its outlet, the heater propagates through a declared zero drop, the
    flash specifies both outlets *and its own inlet*, and the splitter copies to both outlets. In
    a loop whose declared pressure drops are all zero, two of those nine are linearly dependent.

    Every one of them is in a manifest. K03's structural analysis is what reports rank; dropping
    a row here would hide it from the analysis that is supposed to find it (blueprint §7.2).
    """
    spec = flowsheet_for(variants(reference_values)["SYN-001-nominal"]).spec()
    pressure_variables = [name for name in spec.variable_ids if name.endswith(".P")]
    pressure_rows = [
        equation.equation_id
        for equation in spec.equations
        if equation.equation_id.split(":")[1] in ("FEED-P", "MIX-pressure", "HEAT-pressure")
        or equation.equation_id.split(":")[1] in ("FLASH-P", "SPLIT-P")
    ]
    assert len(pressure_variables) == 7
    assert len(pressure_rows) == 9
    assert len(spec.equations) - len(spec.variable_ids) == 2


def test_every_assembled_row_traces_to_a_manifest_or_to_a_declared_lifting_row(
    reference_values: Mapping[str, Any],
) -> None:
    """ADR 0008 D4.4: a row the assembly authors itself must be declared `algebraic` explicitly."""
    flowsheet = flowsheet_for(variants(reference_values)["SYN-001-nominal"])
    spec = flowsheet.spec()
    declared: set[str] = set()
    behavioural: set[str] = set()
    for unit in flowsheet.units():
        for equation in unit.declared_equations():
            target = behavioural if equation.equation_id in BEHAVIOURAL_EQUATIONS else declared
            target.add(origin(unit.model_id, equation.equation_id))
    lifting = {origin(unit.model_id, "lifting") for unit in flowsheet.units()}

    produced = {equation.origin for equation in spec.equations}
    assert produced <= declared | lifting
    assert declared - produced == set(), "a declared equation authored no row"
    assert behavioural & produced == set(), "a behavioural statement authored a row"
    for equation in spec.equations:
        if equation.origin in lifting:
            assert equation.accumulation == "algebraic", equation.equation_id


def test_the_accumulation_multiset_matches_the_manifests(
    reference_values: Mapping[str, Any],
) -> None:
    """ADR 0008 D4.4's rule, read as it is written: every row's kind comes from its declaration.

    The assembled system has more rows than the manifests have declarations, because a family
    like `HEAT-mole` expands per component and because the assembly authors its own lifting rows.
    What must hold is that no row's kind was invented: each one equals the kind of the
    declaration it names, and a self-authored row is `algebraic`.
    """
    flowsheet = flowsheet_for(variants(reference_values)["SYN-001-nominal"])
    kinds = {
        origin(unit.model_id, equation.equation_id): equation.accumulation.kind
        for unit in flowsheet.units()
        for equation in unit.declared_equations()
    }
    for equation in flowsheet.spec().equations:
        expected = kinds.get(equation.origin, "algebraic")
        assert equation.accumulation == expected, equation.equation_id

    # And the four holdup rows of ADR 0008 D3.5 are present, expanded per component where the
    # declaration says "for every component i".
    holdup = [
        equation.equation_id
        for equation in flowsheet.spec().equations
        if equation.accumulation == "holdup_balance"
    ]
    zero_holdup = [
        equation.equation_id
        for equation in flowsheet.spec().equations
        if equation.accumulation == "zero_holdup_balance"
    ]
    assert len(holdup) == 3 + 1 + 3 + 1, "HEAT-mole x3, HEAT-duty, FLASH-mole x3, FLASH-duty"
    assert len(zero_holdup) == 3 + 1, "MIX-mole x3, MIX-energy"


#: Which registered tolerance bounds a row, by the unit the row is in. Bounding every row by the
#: energy tolerance -- the loosest of the set -- would let a 1e-4 mol/s component-balance error
#: pass, which is four orders past what ADR 0001 D6 registers for a flow.
def tolerance_for(equation_id: str) -> tuple[float, str]:
    family = equation_id.split(":")[1]
    if family in ("HEAT-duty", "FLASH-duty", "MIX-energy"):
        return ENERGY_TOLERANCE, "energy"
    if family in ("FEED-T", "HEAT-T", "FLASH-T", "SPLIT-T"):
        return TEMPERATURE_TOLERANCE, "temperature"
    if family in ("FEED-P", "HEAT-pressure", "FLASH-P", "SPLIT-P", "MIX-pressure"):
        return PRESSURE_TOLERANCE, "pressure"
    if family in ("HEAT-equilibrium", "FLASH-equilibrium"):
        # (mol/s)^2, so the registered flow tolerance scales with the throughput it multiplies.
        return FLOW_TOLERANCE * 40.0, "equilibrium, (mol/s)^2"
    return FLOW_TOLERANCE, "component flow"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_assembled_rows_vanish_at_the_reference_solution(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """Every row of the whole flowsheet, at Fable's 20-digit answer, at every variant.

    The strongest single statement K02 makes about its rows: the residual vector of the
    assembled system is zero at an independently computed solution. A wrong sign, a missing
    term or a mis-wired stream shows up here.

    Parametrised over all five variants, and each row bounded by the tolerance registered for
    *its* unit rather than by the loosest of the set. Both of those were wrong in the first
    version and the Fable review of K02 measured the consequence: with only the nominal variant,
    the heater outlet is single-phase, `S3.V` is zero, and `v_i L - K_i l_i V` is identically
    zero for any K at all -- so dropping the K-value from the row entirely passed 1003 of 1003
    tests. Three of the five variants have a two-phase heater outlet, and they are what give
    that row a state where it can fail.
    """
    case = variants(reference_values)[case_id]
    spec = flowsheet_for(case).spec()
    rows = row_values(spec, reference_state(case, spec))
    for equation_id, value in rows.items():
        tolerance, kind = tolerance_for(equation_id)
        assert abs(value) < tolerance, f"{equation_id} = {value} ({kind}, bound {tolerance})"


def test_the_heater_equilibrium_row_has_the_sign_its_statement_declares(
    reference_values: Mapping[str, Any],
) -> None:
    """`v_i L - K_i l_i V` on the *heater's* lifted split, at a genuinely two-phase outlet.

    The vanishing tests above cannot see a flipped sign or a dropped K-value that leaves the row
    zero at the solution. This perturbs the lifted vapour flow either side of equilibrium and
    requires the residual to follow.
    """
    case = variants(reference_values)["SYN-001-once-through"]
    assert float(case["heater_outlet_vapor_fraction"]) > 0.0, "this variant must be two-phase"
    spec = flowsheet_for(case).spec()
    base = reference_state(case, spec)
    row = row_id("U-HEAT", "HEAT-equilibrium", "A")

    assert abs(row_values(spec, base)[row]) < FLOW_TOLERANCE * 40.0

    more_vapor = dict(base)
    more_vapor[vapor_flow_id("S3", "A")] = base[vapor_flow_id("S3", "A")] * 1.5
    assert row_values(spec, more_vapor)[row] > 0.0

    less_vapor = dict(base)
    less_vapor[vapor_flow_id("S3", "A")] = base[vapor_flow_id("S3", "A")] * 0.5
    assert row_values(spec, less_vapor)[row] < 0.0


def test_the_heater_equilibrium_row_actually_uses_the_k_value(
    reference_values: Mapping[str, Any],
) -> None:
    """The row must be sensitive to K, which at a single-phase outlet it is not.

    K_B(360 K, P_r) = 1 exactly, so at the flash state the B row reduces to `v_B L - l_B V`.
    Evaluating the heater's B row at a two-phase outlet held at 360 K and comparing against that
    closed form pins the K-value's presence and its exponentiation, neither of which any
    reference-state test can see.
    """
    case = variants(reference_values)["SYN-001-once-through"]
    spec = flowsheet_for(case).spec()
    state = reference_state(case, spec)
    # Move the heater outlet to the flash state, where K_B is exactly 1.
    state[temperature_id("S3")] = 360.0
    row = row_values(spec, state)[row_id("U-HEAT", "HEAT-equilibrium", "B")]
    expected = (
        state[vapor_flow_id("S3", "B")] * state[liquid_total_id("S3")]
        - state[liquid_flow_id("S3", "B")] * state[vapor_total_id("S3")]
    )
    assert row == pytest.approx(expected, rel=1e-12, abs=1e-15)
    # And it is not trivially zero, which would make the comparison vacuous.
    assert abs(expected) > 1e-3


def composition(entry: Any, total: float) -> list[float]:
    """Component flows from a reference composition, or exact zeros where it is `undefined`.

    The reference writes a sentence rather than a vector where a phase has vanished — `undefined
    (zero vapor flow)`, `undefined (zero liquid flow)` — because ADR 0001 D3.1 makes a dormant
    stream's composition undefined and not zero. Any string is that sentinel; the component
    flows are exactly zero either way.
    """
    if isinstance(entry, str):
        assert entry.startswith("undefined"), entry
        return [0.0] * len(COMPONENTS)
    return [float(value) * total for value in entry]


def reference_state(case: Mapping[str, Any], spec: Any) -> dict[str, float]:
    """The registered nominal answer, laid out over the assembled variable vector."""
    from openflowsheet.models import duty_id
    from openflowsheet.models.syn001.flash import total_flow_id

    pressure = float(case["P_Pa"])
    recycle = [float(value) for value in case["recycle_mol_per_s"]]
    mixed = [float(value) for value in case["mixed_feed_mol_per_s"]]
    vapor_total = float(case["V_mol_per_s"])
    liquid_total = float(case["L_mol_per_s"])
    # A vanished phase has no composition: the reference writes `undefined` rather than zeros,
    # because ADR 0001 D3.1 says a dormant stream's composition is undefined and not zero. The
    # component flows are exactly zero either way, which is what the state needs.
    vapor = composition(case["y"], vapor_total)
    liquid = composition(case["x"], liquid_total)
    purge = [float(value) for value in case["purge_mol_per_s"]]

    state = {name: 0.0 for name in spec.variable_ids}
    per_stream = {
        "S1": ([1.0, 1.0, 1.0], 300.0),
        "S2": (mixed, float(case["T_mix_K"])),
        "S3": (mixed, float(case["T_heater_K"])),
        "S4": (vapor, float(case["T_flash_K"])),
        "S5": (liquid, float(case["T_flash_K"])),
        "S6": (recycle, float(case["T_flash_K"])),
        "S7": (purge, float(case["T_flash_K"])),
    }
    for stream, (flows, temperature) in per_stream.items():
        state[temperature_id(stream)] = temperature
        state[pressure_id(stream)] = pressure
        for index, component in enumerate(COMPONENTS):
            state[flow_id(stream, component)] = flows[index]

    # The heater outlet's lifted split, from the reference's own beta_h, x_h and y_h. Three of
    # the five variants are two-phase here; using an all-liquid split everywhere would leave
    # `HEAT-equilibrium` at 0 = 0 whatever K it used, which is exactly the hole the Fable review
    # of K02 measured (dropping K from the row passed the whole suite).
    beta_h = float(case["heater_outlet_vapor_fraction"])
    total_mixed = mixed[0] + mixed[1] + mixed[2]
    vapor_h = beta_h * total_mixed
    liquid_h = (1.0 - beta_h) * total_mixed
    x_h = [float(value) for value in case["heater_outlet_x"]]
    y_h = composition(case["heater_outlet_y"], 1.0)
    for index, component in enumerate(COMPONENTS):
        state[vapor_flow_id("S3", component)] = y_h[index] * vapor_h
        state[liquid_flow_id("S3", component)] = x_h[index] * liquid_h
    state[vapor_total_id("S3")] = vapor_h
    state[liquid_total_id("S3")] = liquid_h
    state[total_flow_id("S4")] = vapor[0] + vapor[1] + vapor[2]
    state[total_flow_id("S5")] = liquid[0] + liquid[1] + liquid[2]
    state[duty_id(HEATER_UNIT)] = float(case["Q_heater_W"])
    state[duty_id(FLASH_UNIT)] = float(case["Q_flash_W"])
    return state


def test_the_compiled_flowsheet_agrees_with_the_float_route(
    reference_values: Mapping[str, Any],
) -> None:
    """Forty-seven variables, forty-nine rows, eight property blocks, through the real backend."""
    case = variants(reference_values)["SYN-001-nominal"]
    spec = flowsheet_for(case).spec()
    problem = compile_problem(spec)
    metadata = problem.metadata
    context = EvaluationContext(
        model_version=metadata.model_version, constants_sha256=metadata.constants_sha256
    )
    state = reference_state(case, spec)
    result = problem.residual(np.array(state_vector(spec, state)), context)
    assert result.status == "ok", result.message
    assert result.values is not None
    expected = row_values(spec, state)
    for equation_id, got in zip(result.equation_ids, result.values, strict=True):
        assert got == pytest.approx(expected[equation_id], rel=1e-12, abs=1e-9), equation_id


def test_the_compiled_flowsheet_reports_every_row_accumulation(
    reference_values: Mapping[str, Any],
) -> None:
    """ADR 0008 D4.4: every equation id in the metadata has an accumulation entry."""
    spec = flowsheet_for(variants(reference_values)["SYN-001-nominal"]).spec()
    metadata = compile_problem(spec).metadata
    assert set(metadata.row_accumulation) == set(metadata.equation_ids)
    assert "absent" not in set(metadata.row_accumulation.values()), (
        "every row here comes from a manifest or from a lifting row the unit authored, and "
        "ADR 0008 D4.4 reserves `absent` for a row from an opaque evaluator"
    )


def test_the_variable_order_is_the_one_identity_depends_on() -> None:
    """ADR 0008 D2 hashes `x` in `variable_ids` order and ADR 0002 D2 folds the order into
    `model_version`, so a permutation is a different problem wearing the same name.

    Written out rather than derived from `STREAMS`, which is the thing that would be permuted.
    """
    flowsheet = Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT)
    names = flowsheet.spec().variable_ids
    assert names[:5] == ("S1.n.A", "S1.n.B", "S1.n.C", "S1.T", "S1.P")
    assert names[30:35] == ("S7.n.A", "S7.n.B", "S7.n.C", "S7.T", "S7.P")
    # Then the unit-owned variables, in unit order: the heater's, then the flash's.
    assert names[35] == "U-HEAT.Q"
    assert names[-3:] == ("U-FLASH.Q", "S4.N", "S5.N")


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_both_boundary_sinks_accept_their_stream_including_the_dormant_ones(
    case_id: str, reference_values: Mapping[str, Any]
) -> None:
    """A sink imposes no equation, so the traversal recording that it accepted is its only trace.

    Worth having: the vapour product is exactly dormant in the 310 K variant and the purge is
    exactly dormant in the 420 K variant, and ADR 0001 D3.4 makes both valid results rather than
    failures.
    """
    case = variants(reference_values)[case_id]
    traversal = flowsheet_for(case).traverse(reference_recycle(case))
    assert traversal.status == "ok", traversal.message
    assert traversal.accepted_by == ("U-PROD", "U-PURGE")
    if case_id == "SYN-001-all-liquid-310K":
        assert traversal.streams["S4"].is_dormant
    if case_id == "SYN-001-all-vapor-420K":
        assert traversal.streams["S7"].is_dormant


# ------------------------------------------------------------------------------- identity


class RelabelledProvider:
    """The same arithmetic, declared under a different data hash.

    Stands in for "the same equations over a different property package" — different constants,
    or the same constants under changed code. Nothing it computes differs, which is the point:
    identity must separate them anyway, or a cached or replayed result from one could be served
    for the other.
    """

    def __init__(self, data_sha256: str, provider_id: str = "syn001") -> None:
        self.inner = Syn001Provider()
        self._data = data_sha256
        self._provider_id = provider_id

    def describe(self) -> Any:
        from dataclasses import replace

        return replace(self.inner.describe(), data_sha256=self._data, provider_id=self._provider_id)

    def evaluate_phase(self, request: Any, context: EvaluationContext) -> Any:
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: Any, context: EvaluationContext) -> Any:
        return self.inner.flash(request, context)


def test_a_different_property_package_is_a_different_model_version() -> None:
    """Closes the K02 half of ADR 0008 D4.1's gap: the SYN-001 constants were hashed by nothing.

    They cannot reach `constants_sha256`, which hashes the pinned inputs and those are floats, so
    they reach identity through the label. Two flowsheets with identical equations and identical
    specifications, over providers declaring different data, must not share an identity.
    """
    base = Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT)
    altered = Syn001Flowsheet(provider=RelabelledProvider("b" * 64), context=CONTEXT)

    assert base.label != altered.label
    first = compile_problem(base.spec()).metadata
    second = compile_problem(altered.spec()).metadata
    assert first.model_version != second.model_version
    # The *structure* is identical — same rows, same variables, same order — so only the label
    # half differs. That is the distinction ADR 0002 D2 draws and it is worth pinning.
    assert first.model_version.split("@")[1] == second.model_version.split("@")[1]


def test_the_same_structure_at_a_different_recycle_ratio_differs_only_in_its_constants() -> None:
    """ADR 0008 D4.1's test, on this flowsheet: same structure, different pinned inputs.

    D4.1 in its own words: two instances compiled from the same structure with different
    specification values **share `model_version`** and differ in `constants_sha256`. The first
    version of the label carried `r`, the flash temperature and the heater temperature, which
    broke that and defeated re-binding without recompilation; the Fable review of K02 caught it.
    """
    nominal = Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT, split_fraction=0.5)
    high = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=CONTEXT,
        split_fraction=0.95,
        flash_temperature=420.0,
        heater_temperature=345.0,
    )
    first = compile_problem(nominal.spec()).metadata
    second = compile_problem(high.spec()).metadata
    assert first.model_version == second.model_version
    assert first.constants_sha256 != second.constants_sha256


def test_an_unremarkable_parameterization_does_not_overflow_the_label() -> None:
    """`r = 0.123`, `T_f = 360.25` overflowed the 64-character cap while the label carried them."""
    awkward = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=CONTEXT,
        split_fraction=0.123456789,
        flash_temperature=360.25,
        heater_temperature=347.4411819814402,
    )
    assert len(awkward.label) <= 64
    compile_problem(awkward.spec())


def test_a_label_that_will_not_fit_the_model_version_pattern_is_refused_here() -> None:
    """With the length in the message, rather than as a refusal from two layers down."""
    from openflowsheet.models import SpecificationError

    verbose = Syn001Flowsheet(
        provider=RelabelledProvider("c" * 64, provider_id="a-provider-with-a-very-long-name"),
        context=CONTEXT,
    )
    with pytest.raises(SpecificationError, match="does not fit"):
        _ = verbose.label


def test_the_lifted_equilibrium_admits_a_trivial_root_that_k03_must_reject(
    reference_values: Mapping[str, Any],
) -> None:
    """A registered hazard, demonstrated rather than described.

    `v_i L - K_i l_i V` is satisfied identically when every `v_i` is zero, whatever the feed and
    whatever the K-values: the classical trivial solution of the flash equations. It is an
    *exact* root of the lifted block, not a near-root.

    Here, at the once-through variant whose heater outlet is genuinely two-phase (β_h = 0.101),
    forcing the all-liquid split leaves **thirteen of the heater's fourteen rows at exactly
    zero**. The fourteenth is the duty row, and a solver free to choose `Q` closes that too — at
    a duty 8237.85 W below the true one, with every residual satisfied.

    No residual can exclude this, because the trivial split satisfies it. Excluding it belongs to
    initialization on the physical branch and to a final phase-admissibility check on the
    converged answer, both of which are K03's (blueprint §6.3, §7.1). This test exists so that
    the case is registered and K03 does not have to rediscover it from a wrong duty.
    """
    from openflowsheet.models import duty_id

    case = variants(reference_values)["SYN-001-once-through"]
    assert float(case["heater_outlet_vapor_fraction"]) > 0.0
    spec = flowsheet_for(case).spec()
    state = reference_state(case, spec)

    mixed = [float(value) for value in case["mixed_feed_mol_per_s"]]
    for index, component in enumerate(COMPONENTS):
        state[vapor_flow_id("S3", component)] = 0.0
        state[liquid_flow_id("S3", component)] = mixed[index]
    state[vapor_total_id("S3")] = 0.0
    state[liquid_total_id("S3")] = sum(mixed)

    rows = row_values(spec, state)
    heater_rows = {name: value for name, value in rows.items() if name.startswith("U-HEAT:")}
    assert len(heater_rows) == 14
    nonzero = {name: value for name, value in heater_rows.items() if value != 0.0}
    assert set(nonzero) == {row_id("U-HEAT", "HEAT-duty")}, nonzero

    # And the duty row closes at a duty that is wrong by a large, measured amount.
    offset = nonzero[row_id("U-HEAT", "HEAT-duty")]
    assert offset == pytest.approx(8237.850393069453, abs=ENERGY_TOLERANCE)
    closed = dict(state)
    closed[duty_id("U-HEAT")] = state[duty_id("U-HEAT")] - offset
    closed_rows = row_values(spec, closed)
    assert all(value == 0.0 for name, value in closed_rows.items() if name.startswith("U-HEAT:")), (
        "the trivial split is an exact root of every heater row once the duty is free"
    )
    assert abs(closed[duty_id("U-HEAT")] - float(case["Q_heater_W"])) > 8000.0


def test_a_recycle_guess_at_the_wrong_state_is_refused(
    reference_values: Mapping[str, Any],
) -> None:
    """The tear is three component flows because T and P are known (plan §3.2).

    A guess that disagrees with the flash specification is not a tear iterate, and accepting it
    would let a caller silently solve a different problem.
    """
    case = variants(reference_values)["SYN-001-nominal"]
    flowsheet = flowsheet_for(case)
    star = reference_recycle(case)

    for wrong in (
        StreamState(n=star.n, temperature=355.0, pressure=star.pressure),
        StreamState(n=star.n, temperature=star.temperature, pressure=90_000.0),
    ):
        traversal = flowsheet.traverse(wrong)
        assert traversal.status == "error"
        assert "flash specification" in traversal.message
        assert traversal.recycle_residual is None


def test_the_assembled_spec_carries_the_flowsheet_label_itself() -> None:
    """The label survives assembly, checked against the flowsheet rather than against another spec.

    Every other identity test here compares two `model_version`s to each other, which passes
    happily when both are equally wrong. A loop variable shadowing `assemble`'s `label`
    parameter once renamed every assembled problem to `row@<digest>` and the whole gate stayed
    green; a byte-comparison snapshot caught it and this test is the durable form.
    """
    flowsheet = Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT)
    spec = flowsheet.spec()
    assert spec.label == flowsheet.label
    assert spec.label.startswith("SYN001-fs1-syn001-")
    metadata = compile_problem(spec).metadata
    assert metadata.model_version.startswith(flowsheet.label + "@")


def test_every_variable_and_row_declares_a_quantity_kind() -> None:
    """K03's scales come from declared kinds, so a missing one must be visible here, not there.

    Counts are K03's specification §4.2, written out: 31 flow columns, 7 temperature, 7
    pressure, 2 heat rate; 25 flow rows (21 component balances plus 4 total definitions), 6
    temperature, 9 pressure, 3 energy, 6 equilibrium rows in (mol/s)².
    """
    from collections import Counter

    spec = Syn001Flowsheet(provider=Syn001Provider(), context=CONTEXT).spec()
    assert [name for name in spec.variable_ids if name not in spec.variable_kinds] == []
    assert [name for name in spec.equation_ids if name not in spec.row_kinds] == []
    assert Counter(spec.variable_kinds.values()) == Counter(
        {"molar_flow": 31, "temperature": 7, "pressure": 7, "heat_rate": 2}
    )
    assert Counter(spec.row_kinds.values()) == Counter(
        {
            "molar_flow": 25,
            "temperature": 6,
            "pressure": 9,
            "heat_rate": 3,
            "molar_flow_squared": 6,
        }
    )
