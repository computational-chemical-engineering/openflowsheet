"""The day-one sizing families (E01 design §4.4.0–§4.4.7), registered against the model ids of
the model registry (`MODEL_ID` of each unit module; verified by WO-A2).

Every formula is the note's, written with the algebra's `exp`/`log`/`sqrt` and `**`; every input
is a θ with its provenance (§4.2.3); every choice is a regime entry made on floats (§4.3.2).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any, NamedTuple

from openflowsheet.assessment.linearization import Refusal
from openflowsheet.assessment.program import (
    FunctionalBuilder,
    Limitation,
    OutputDef,
    Symbols,
    Theta,
)
from openflowsheet.assessment.regimes import (
    AdmissibilityRow,
    Regime,
    RegimeEntry,
    select_argmax,
    select_service,
)
from openflowsheet.assessment.sizing.core import (
    GRAVITY,
    ItemFamily,
    SizedItem,
    SizingContext,
    SizingInput,
    SizingPlan,
    StreamFlow,
    argmax_rows,
    nominal,
    register_family,
    size_output,
    sub_item,
)
from openflowsheet.assessment.views import UnitRef
from openflowsheet.compile.spec import Algebra, Expr
from openflowsheet.models import duty_id, pressure_id, temperature_id
from openflowsheet.models.syn001 import cascade_spec
from openflowsheet.models.syn001.pump import work_id
from openflowsheet.models.thermal.state import liquid_id, vapor_id
from openflowsheet.thermo import FlashRequest, StreamState

__all__ = ["PRICE_PER_SI", "underwood"]

#: §4.5.6: exact SI factors of an energy price's `per` (only these compare utilities, rule 2).
PRICE_PER_SI: Mapping[str, float] = {
    "J": 1.0,
    "kJ": 1e3,
    "MJ": 1e6,
    "GJ": 1e9,
    "kWh": 3.6e6,
    "MWh": 3.6e9,
}

_THIRD = 1.0 / 3.0


def underwood(dt1: Expr, dt2: Expr) -> Expr:
    """`ΔT_lm = ((ΔT₁^{1/3} + ΔT₂^{1/3})/2)³` (§4.4.1), written with `**(1.0/3.0)`."""
    return ((dt1**_THIRD + dt2**_THIRD) / 2.0) ** 3


def _empty() -> SizingPlan:
    return SizingPlan()


def _refused(code: str, target: str, detail: str = "") -> SizingPlan:
    return SizingPlan(refusals=(Refusal(code, target, detail),))


# -- duties --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Duty:
    """A unit's duty: a host variable (`<U>.Q`, a column's `<U>.stage.<j>.Q`) or a pinned input
    (`<U>.Q_spec`), and its value at the state."""

    name: str
    pinned: bool
    value: float

    def build(self, s: Symbols, a: Algebra) -> Expr:
        return s.pin(self.name) if self.pinned else s.x(self.name)


def _duty(sctx: SizingContext, unit_id: str, variable: str | None = None) -> _Duty | None:
    name = variable or duty_id(unit_id)
    if name in sctx.variables:
        return _Duty(name, False, sctx.x(name))
    spec = f"{unit_id}.Q_spec"
    if variable is None and spec in sctx.parameters:
        return _Duty(spec, True, float(sctx.parameters[spec]))
    return None


def _duty_item_needed(sctx: SizingContext, unit_id: str, duty: _Duty | None) -> bool:
    """§4.4.0: a flash's or reactor's duty item exists unless the duty is a pin (`<U>.Q_spec`)
    equal to 0.0 — whether or not the unit also carries the duty as a variable tied to it."""
    pin = sctx.parameters.get(f"{unit_id}.Q_spec")
    return duty is not None and not (pin is not None and float(pin) == 0.0)


# -- phase signatures (for LMTD_ACROSS_PHASE_CHANGE, information only) ---------------------------


def _signature(sctx: SizingContext, stream: str) -> str | None:
    if vapor_id(stream) in sctx.variables:
        vapour, liquid = sctx.x(vapor_id(stream)), sctx.x(liquid_id(stream))
        return "VAPOR" if liquid == 0.0 else "LIQUID" if vapour == 0.0 else "VAPOR_LIQUID"
    total = sctx.total(stream)
    if total == 0.0:
        return None
    from openflowsheet.models import flow_id  # noqa: PLC0415

    view = sctx.ctx.view
    state = StreamState(
        n=tuple(sctx.x(flow_id(stream, c)) for c in view.components),
        temperature=sctx.x(temperature_id(stream)),
        pressure=sctx.x(pressure_id(stream)),
    )
    result = view.provider.flash(FlashRequest(state=state), view.context)
    return result.phase_signature if result.status == "ok" else None


# -- §4.4.1 exchanger.utility --------------------------------------------------------------------


def _utility_temperatures(
    utility: Mapping[str, Any],
) -> tuple[float, float] | None:
    if "T_supply" not in utility:
        return None
    supply = float(utility["T_supply"])
    return supply, float(utility.get("T_return", supply))


def _differences(service: str, t_us: Any, t_ur: Any, t_pi: Any, t_po: Any) -> tuple[Any, Any]:
    """§4.4.1's counter-current ΔT₁, ΔT₂ (floats or expressions alike)."""
    if service == "heating":
        return t_us - t_po, t_ur - t_pi
    return t_pi - t_ur, t_po - t_us


def _price_per_joule(utility: Mapping[str, Any]) -> float | None:
    price = utility.get("price", {})
    factor = PRICE_PER_SI.get(price.get("per", ""))
    return None if factor is None else float(price["value"]) / factor


def exchanger_utility(
    sctx: SizingContext,
    item_id: str,
    unit_id: str,
    duty: _Duty,
    t_in: str,
    t_out: str,
    *,
    forced_service: str | None = None,
    streams: tuple[str, str] | None = None,
    design_pressure: str | float | None = None,
    extra_limitations: Sequence[Limitation] = (),
) -> SizingPlan:
    """An `exchanger.utility` item (§4.4.1): area `|Q|/(U F_T ΔT_lm)` against one utility.

    `t_in`/`t_out` are the host ids of the process inlet and outlet temperatures; `streams` the
    process streams, when there are any, for the phase-change limitation. Rule 1 (the service) is
    `_service_rule`'s, the `U` input and its refusal `_u_input`'s. `_candidates` refuses
    NO_ADMISSIBLE_UTILITY for an undeclared named utility; `_cheapest_admissible` returns `None`,
    which this function turns into the same refusal."""
    doc = sctx.item(item_id)
    regime = sctx.ctx.regime
    declared = forced_service or doc.get("service")
    service, service_default, signed, service_entry = _service_rule(regime, item_id, duty, declared)

    # Rule 2: the utility.
    t_pi, t_po = sctx.x(t_in), sctx.x(t_out)
    named = doc.get("utility", "auto")
    candidates = _candidates(sctx, item_id, service, named)
    if isinstance(candidates, SizingPlan):
        return candidates

    utility_entry_id = f"{item_id}.utility"
    held = regime.choice(utility_entry_id)
    if held is not None:
        chosen = sctx.utility(held)
        if chosen is None:
            return _refused("NO_ADMISSIBLE_UTILITY", item_id, f"held utility {held!r} is unknown")
    elif named != "auto":
        chosen = candidates[0]
    else:
        cheapest = _cheapest_admissible(doc, candidates, service, t_pi, t_po)
        if cheapest is None:
            return _refused("NO_ADMISSIBLE_UTILITY", item_id, f"service {service}")
        chosen = cheapest
    utility_id = chosen["utility_id"]
    temperatures = _utility_temperatures(chosen)
    if temperatures is None:
        return _refused("SIZING_INPUT_MISSING", f"{item_id}.T_supply", utility_id)
    dt_min = _dt_min(doc, chosen)
    if dt_min is None:
        return _refused("SIZING_INPUT_MISSING", f"{item_id}.dT_min", utility_id)

    # Inputs (U is required, R-856).
    u_pair = _u_input(sctx, doc, item_id, service)
    if isinstance(u_pair, SizingPlan):
        return u_pair
    u_theta, u_input = u_pair
    f_theta, f_input = sctx.input(item_id, "F_T", "1", default_key="F_T")
    t_us, t_ur = temperatures
    supply = Theta(f"asm:item.{item_id}.T_supply", t_us, "K", f"utilities.{utility_id}.T_supply")
    back = Theta(f"asm:item.{item_id}.T_return", t_ur, "K", f"utilities.{utility_id}.T_return")
    dt_source = f"items.{item_id}.dT_min" if "dT_min" in doc else f"utilities.{utility_id}.dT_min"
    minimum = Theta(f"asm:item.{item_id}.dT_min", dt_min, "K", dt_source)
    ids = (supply.theta_id, back.theta_id, minimum.theta_id)

    def deltas(s: Symbols, a: Algebra) -> tuple[Expr, Expr]:
        return _differences(service, s.theta(ids[0]), s.theta(ids[1]), s.x(t_in), s.x(t_out))

    def area(s: Symbols, a: Algebra) -> Expr:
        dt1, dt2 = deltas(s, a)
        lmtd = underwood(dt1, dt2)
        return signed(s, a) / (s.theta(u_theta.theta_id) * s.theta(f_theta.theta_id) * lmtd)

    def approach(index: int) -> FunctionalBuilder:
        return lambda s, a: deltas(s, a)[index] - s.theta(ids[2])

    dt1_f, dt2_f = _differences(service, t_us, t_ur, t_pi, t_po)
    utility_entry = RegimeEntry(
        utility_entry_id,
        "utility",
        utility_id,
        "§4.3.2 rule 2" + (" (declared)" if named != "auto" else " (cheapest admissible)"),
        (
            AdmissibilityRow("dT1", approach(0), nominal(dt1_f)),
            AdmissibilityRow("dT2", approach(1), nominal(dt2_f)),
        ),
    )
    limitations = list(extra_limitations)
    phase_change = _phase_change(sctx, item_id, streams, dt1_f, dt2_f)
    if phase_change is not None:
        limitations.append(phase_change)

    def magnitude(s: Symbols, a: Algebra) -> Expr:
        return signed(s, a)

    item = SizedItem(
        item_id=item_id,
        unit_id=unit_id,
        family="exchanger.utility",
        size={"area": size_output(item_id, "area")},
        inputs=(
            u_input,
            f_input,
            SizingInput("T_supply", t_us, "K", False, supply.theta_id),
            SizingInput("T_return", t_ur, "K", "T_return" not in chosen, back.theta_id),
            SizingInput("dT_min", dt_min, "K", False, minimum.theta_id),
            SizingInput("Q", duty.value, "W", False),
            *service_default,
        ),
        design_pressure=design_pressure,
        options=_options(doc),
        utility=utility_id,
        duty=magnitude,
    )
    return SizingPlan(
        items=(item,),
        outputs=(OutputDef(size_output(item_id, "area"), "m2", area),),
        theta=(u_theta, f_theta, supply, back, minimum),
        regime_entries=(service_entry, utility_entry),
        limitations=tuple(limitations),
    )


class _ServiceRule(NamedTuple):
    """§4.3.2 rule 1 for an `exchanger.utility` item: the service, the `service_at_zero_duty`
    input when the rule took that default (else empty), the duty signed for the service, and the
    regime entry."""

    service: str
    default: tuple[SizingInput, ...]
    signed: FunctionalBuilder
    entry: RegimeEntry


def _service_rule(regime: Regime, item_id: str, duty: _Duty, declared: str | None) -> _ServiceRule:
    """§4.3.2 rule 1: the service `regime` holds for `<item>.service`, else `select_service` on the
    duty's value and the `declared` service; the duty as heating (`Q`) or cooling (`-Q`); the
    entry with its `duty` admissibility row."""
    service_entry_id = f"{item_id}.service"
    service = regime.choice(service_entry_id) or select_service(duty.value, declared)
    # Rule 1 at Q == 0.0 with nothing declared or held takes `service_at_zero_duty` (A41).
    service_default = (
        (SizingInput("service", service, "", True, default_key="service_at_zero_duty"),)
        if duty.value == 0.0 and declared is None and regime.choice(service_entry_id) is None
        else ()
    )
    duty_build = duty.build
    if service == "heating":
        signed: FunctionalBuilder = duty_build
    else:

        def signed(s: Symbols, a: Algebra) -> Expr:
            return -duty_build(s, a)

    service_entry = RegimeEntry(
        service_entry_id,
        "service",
        service,
        "§4.3.2 rule 1",
        (AdmissibilityRow("duty", signed, nominal(duty.value)),),
    )
    return _ServiceRule(service, service_default, signed, service_entry)


def _candidates(
    sctx: SizingContext, item_id: str, service: str, named: Any
) -> list[Mapping[str, Any]] | SizingPlan:
    """§4.3.2 rule 2's candidates: the utility the item names (`named`, unless `auto`), else every
    utility of the service's kind. A `NO_ADMISSIBLE_UTILITY` refusal when the named utility is not
    declared."""
    candidates = [u for u in sctx.utilities if u.get("kind") == service]
    if named != "auto":
        candidates = [u for u in sctx.utilities if u["utility_id"] == named]
        if not candidates:
            return _refused("NO_ADMISSIBLE_UTILITY", item_id, f"utility {named!r} is not declared")
    return candidates


def _cheapest_admissible(
    doc: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    service: str,
    t_pi: float,
    t_po: float,
) -> Mapping[str, Any] | None:
    """§4.3.2 rule 2 without a held or declared utility: the cheapest candidate whose ΔT₁ and ΔT₂
    both reach the item's `dT_min`, else the candidate's, at the process temperatures `t_pi`,
    `t_po`, ties to the earlier candidate. A candidate without temperatures, `dT_min` or a
    comparable price is skipped; `None` when no candidate is admissible."""
    admissible: list[tuple[float, int, Mapping[str, Any]]] = []
    for order, utility in enumerate(candidates):
        temperatures, dt_min = _utility_temperatures(utility), _dt_min(doc, utility)
        price = _price_per_joule(utility)
        if temperatures is None or dt_min is None or price is None:
            continue
        dt1, dt2 = _differences(service, *temperatures, t_pi, t_po)
        if dt1 - dt_min >= 0.0 and dt2 - dt_min >= 0.0:
            admissible.append((price, order, utility))
    if not admissible:
        return None
    return min(admissible, key=lambda entry: (entry[0], entry[1]))[2]


def _dt_min(doc: Mapping[str, Any], utility: Mapping[str, Any]) -> float | None:
    """The item's `dT_min`, else the utility's; `None` when neither declares one."""
    if "dT_min" in doc:
        return float(doc["dT_min"])
    return float(utility["dT_min"]) if "dT_min" in utility else None


def _u_input(
    sctx: SizingContext, doc: Mapping[str, Any], item_id: str, service: str
) -> tuple[Theta, SizingInput] | SizingPlan:
    """The item's required `U` (R-856) as `(θ, input)`, the shape `SizingContext.input` returns:
    the item's own (`doc`), else `defaults.U_by_service.<service>`; a
    `SIZING_INPUT_MISSING(<item>.U)` refusal with neither."""
    if "U" in doc:
        u_value, u_source, u_default = float(doc["U"]), f"items.{item_id}.U", False
    elif service in sctx.defaults.get("U_by_service", {}):
        u_value = float(sctx.defaults["U_by_service"][service])
        u_source, u_default = f"defaults.U_by_service.{service}", False
    else:
        return _refused("SIZING_INPUT_MISSING", f"{item_id}.U", f"service {service}")
    u_theta = Theta(f"asm:item.{item_id}.U", u_value, "W/(m2*K)", u_source)
    return u_theta, SizingInput("U", u_value, "W/(m2*K)", u_default, u_theta.theta_id)


def _phase_change(
    sctx: SizingContext,
    item_id: str,
    streams: tuple[str, str] | None,
    dt1_f: float,
    dt2_f: float,
) -> Limitation | None:
    """§4.4.1's `LMTD_ACROSS_PHASE_CHANGE` (information only): the process streams' phase
    signatures at inlet and outlet, when both are known and differ; with ΔT₁ and ΔT₂ both positive
    the detail also carries their ratio `r` and Underwood's relative error against the exact LMTD.
    `None` without process `streams`, or when either signature is unknown or they agree."""
    if streams is None:
        return None
    before, after = (_signature(sctx, stream) for stream in streams)
    if before is not None and after is not None and before != after:
        detail: dict[str, Any] = {"inlet": before, "outlet": after}
        if dt1_f > 0.0 and dt2_f > 0.0:
            ratio = max(dt1_f, dt2_f) / min(dt1_f, dt2_f)
            exact = dt1_f if dt1_f == dt2_f else (dt1_f - dt2_f) / math.log(dt1_f / dt2_f)
            detail |= {
                "r": ratio,
                "underwood_over_lmtd_minus_1": underwood(dt1_f, dt2_f) / exact - 1.0,
            }
        return Limitation("LMTD_ACROSS_PHASE_CHANGE", item_id, detail)
    return None


def _options(doc: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("material", "subtype", "orientation", "tray_type", "allow_extrapolation", "F_BM")
    return {key: doc[key] for key in keys if key in doc}


class _Heater:
    name = "exchanger.utility"

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        duty = _duty(sctx, unit.unit_id)
        if duty is None:
            return _refused("SIZING_INPUT_UNAVAILABLE", f"{unit.unit_id}.Q", "no duty variable")
        inlet, outlet = unit.ports["inlet"][0], unit.ports["outlet"][0]
        return exchanger_utility(
            sctx,
            unit.unit_id,
            unit.unit_id,
            duty,
            temperature_id(inlet),
            temperature_id(outlet),
            streams=(inlet, outlet),
            design_pressure=pressure_id(inlet),
        )


# -- §4.4.2 exchanger.process --------------------------------------------------------------------


class _ProcessExchanger:
    name = "exchanger.process"

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        item_id = unit.unit_id
        doc = sctx.item(item_id)
        for key in ("U", "dT_min"):
            if key not in doc:
                return _refused("SIZING_INPUT_MISSING", f"{item_id}.{key}", "required per item")
        duty = _duty(sctx, unit.unit_id)
        if duty is None or duty.pinned:
            # The transferred duty is the unit's own variable (`<U>.Q`, sink of the hot side).
            return _refused("SIZING_INPUT_UNAVAILABLE", f"{item_id}.Q", "no duty variable")
        hot_in, hot_out = unit.ports["hot_inlet"][0], unit.ports["hot_outlet"][0]
        cold_in, cold_out = unit.ports["cold_inlet"][0], unit.ports["cold_outlet"][0]
        u_theta = Theta(f"asm:item.{item_id}.U", float(doc["U"]), "W/(m2*K)", f"items.{item_id}.U")
        minimum = Theta(
            f"asm:item.{item_id}.dT_min", float(doc["dT_min"]), "K", f"items.{item_id}.dT_min"
        )
        f_theta, f_input = sctx.input(item_id, "F_T", "1", default_key="F_T")
        t = tuple(temperature_id(s) for s in (hot_in, cold_out, hot_out, cold_in))

        def deltas(s: Symbols, a: Algebra) -> tuple[Expr, Expr]:
            return s.x(t[0]) - s.x(t[1]), s.x(t[2]) - s.x(t[3])

        def area(s: Symbols, a: Algebra) -> Expr:
            dt1, dt2 = deltas(s, a)
            ua = s.theta(u_theta.theta_id) * s.theta(f_theta.theta_id) * underwood(dt1, dt2)
            return duty.build(s, a) / ua

        def approach(index: int) -> FunctionalBuilder:
            return lambda s, a: deltas(s, a)[index] - s.theta(minimum.theta_id)

        dt1_f = sctx.x(t[0]) - sctx.x(t[1])
        dt2_f = sctx.x(t[2]) - sctx.x(t[3])
        entry = RegimeEntry(
            f"{item_id}.approach",
            "utility",
            "counter-current",
            "§4.4.2 (a single choice)",
            (
                AdmissibilityRow("dT1", approach(0), nominal(dt1_f)),
                AdmissibilityRow("dT2", approach(1), nominal(dt2_f)),
            ),
        )
        item = SizedItem(
            item_id=item_id,
            unit_id=unit.unit_id,
            family="exchanger.process",
            size={"area": size_output(item_id, "area")},
            inputs=(
                SizingInput("U", float(doc["U"]), "W/(m2*K)", False, u_theta.theta_id),
                f_input,
                SizingInput("dT_min", float(doc["dT_min"]), "K", False, minimum.theta_id),
                SizingInput("Q", duty.value, "W", False),
            ),
            design_pressure=max(
                (pressure_id(hot_in), pressure_id(cold_in)), key=lambda name: sctx.x(name)
            ),
            options=_options(doc),
        )
        return SizingPlan(
            items=(item,),
            outputs=(OutputDef(size_output(item_id, "area"), "m2", area),),
            theta=(u_theta, minimum, f_theta),
            regime_entries=(entry,),
        )


# -- §4.4.4 drum ---------------------------------------------------------------------------------


def drum(sctx: SizingContext, unit: UnitRef, item_id: str) -> SizingPlan:
    """A vertical (default) or horizontal flash drum (§4.4.4). A dormant liquid product reads
    ρ_L from the item's `dormant_liquid_density` (§9.3), else the V member is refused."""
    doc = sctx.item(item_id)
    inlet = unit.ports["inlet"][0]
    vapour_stream, liquid_stream = unit.ports["vapor"][0], unit.ports["liquid"][0]
    liquid, liquid_entry = sctx.flow(item_id, liquid_stream, "LIQUID")
    vapour, vapour_entry = sctx.flow(item_id, vapour_stream, "VAPOR")
    if isinstance(liquid, Refusal):
        return SizingPlan(refusals=(liquid,), regime_entries=(liquid_entry, vapour_entry))
    if isinstance(vapour, Refusal):
        return SizingPlan(refusals=(vapour,), regime_entries=(liquid_entry, vapour_entry))
    inputs = [
        sctx.input(
            item_id, "tau", "s", item_key="residence_time_s", default_key="drum_residence_time"
        ),
        sctx.input(
            item_id, "fill", "1", item_key="fill_fraction", default_key="drum_fill_fraction"
        ),
        sctx.input(item_id, "LD", "1", default_key="drum_LD"),
        sctx.input(item_id, "K_SB", "m/s", default_key="drum_K_SB"),
    ]
    tau, fill, ld, k_sb = (theta.theta_id for theta, _ in inputs)
    refusals: list[Refusal] = []
    rho_dormant: str | None = None
    if "dormant_liquid_density" in doc:
        declared = sctx.input(item_id, "dormant_liquid_density", "kg/m3")
        rho_dormant = declared[0].theta_id
        used = liquid.dormant and not vapour.dormant
        inputs.append((declared[0], replace(declared[1], used=used)))

    def volume(s: Symbols, a: Algebra) -> Expr:
        return s.theta(tau) * liquid.vdot(s, a) / s.theta(fill)

    def d2_liquid(s: Symbols, a: Algebra) -> Expr:
        return (4.0 * s.out(size_output(item_id, "volume")) / (math.pi * s.theta(ld))) ** (
            2.0 / 3.0
        )

    def d2_vapour(s: Symbols, a: Algebra) -> Expr:
        rho_v = vapour.density(s, a)
        if liquid.dormant:
            assert rho_dormant is not None
            rho_l = s.theta(rho_dormant)
        else:
            rho_l = liquid.density(s, a)
        u_v = s.theta(k_sb) * a.sqrt((rho_l - rho_v) / rho_v)
        return 4.0 * vapour.vdot(s, a) / (math.pi * u_v)

    members: list[tuple[str, FunctionalBuilder]] = [("L", d2_liquid)]
    if not vapour.dormant:
        if liquid.dormant and rho_dormant is None:
            # §4.4.4, §9.3 (ii): ρ_L is undefined for a dormant liquid product unless declared.
            refusals.append(
                Refusal("SIZING_INPUT_UNAVAILABLE", f"{item_id}.rho_L", "dormant liquid")
            )
        else:
            members.append(("V", d2_vapour))
    outputs = [OutputDef(size_output(item_id, "volume"), "m3", volume)]
    volume_theta, volume_records = sctx.volume_inputs(item_id, (liquid, vapour))
    theta = [theta for theta, _ in inputs] + list(volume_theta)
    controlling, rule_6 = _drum_controlling(sctx, item_id, members, outputs, theta)
    d2 = dict(members)[controlling]

    def diameter(s: Symbols, a: Algebra) -> Expr:
        return a.sqrt(d2(s, a))

    def height(s: Symbols, a: Algebra) -> Expr:
        return s.theta(ld) * s.out(size_output(item_id, "diameter"))

    outputs += [
        OutputDef(size_output(item_id, "diameter"), "m", diameter),
        OutputDef(size_output(item_id, "height"), "m", height),
    ]
    orientation = doc.get("orientation") or sctx.defaults.get("drum_orientation") or "vertical"
    defaulted_orientation = "orientation" not in doc and "drum_orientation" not in sctx.defaults
    item = SizedItem(
        item_id=item_id,
        unit_id=unit.unit_id,
        family="drum",
        size={q: size_output(item_id, q) for q in ("volume", "diameter", "height")},
        inputs=(
            *(record for _, record in inputs),
            *volume_records,
            SizingInput(
                "orientation",
                orientation,
                "",
                defaulted_orientation,
                default_key="drum_orientation" if defaulted_orientation else None,
            ),
        ),
        design_pressure=pressure_id(inlet),
        options={**_options(doc), "orientation": orientation},
    )
    return SizingPlan(
        items=(item,),
        outputs=tuple(outputs),
        theta=tuple(theta),
        regime_entries=(liquid_entry, vapour_entry, *rule_6),
        refusals=tuple(refusals),
    )


def _drum_controlling(
    sctx: SizingContext,
    item_id: str,
    members: Sequence[tuple[str, FunctionalBuilder]],
    outputs: Sequence[OutputDef],
    theta: Sequence[Theta],
) -> tuple[str, tuple[RegimeEntry, ...]]:
    """The drum's controlling diameter member by §4.3.2 rule 6, with its regime entries: `L` and
    none when `L` is the only member; else the held `controlling` choice, or the member with the
    largest diameter at the state (`select_argmax` over the members' diameters, evaluated with
    `outputs` and `theta`), and its `argmax` entry."""
    if len(members) == 1:
        return "L", ()
    probe = [OutputDef(f"size.{item_id}.{name}.diameter", "m", build) for name, build in members]
    floats = sctx.values([*outputs, *probe], theta)
    values = {name: floats[f"size.{item_id}.{name}.diameter"] for name, _ in members}
    held = sctx.ctx.regime.choice(f"{item_id}.controlling")
    names = [name for name, _ in members]
    controlling = held or names[select_argmax([values[name] for name in names])]
    rows = argmax_rows(members, controlling, values)
    return controlling, (
        RegimeEntry(f"{item_id}.controlling", "argmax", controlling, "§4.3.2 rule 6", rows),
    )


class _Flash:
    name = "drum"

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        plan = drum(sctx, unit, sub_item(unit.unit_id, "drum"))
        duty = _duty(sctx, unit.unit_id)
        if not _duty_item_needed(sctx, unit.unit_id, duty):
            return plan
        assert duty is not None
        inlet, vapour = unit.ports["inlet"][0], unit.ports["vapor"][0]
        return plan.merged(
            exchanger_utility(
                sctx,
                sub_item(unit.unit_id, "duty"),
                unit.unit_id,
                duty,
                temperature_id(inlet),
                temperature_id(vapour),
                streams=(inlet, vapour),
                design_pressure=pressure_id(inlet),
            )
        )


# -- §4.4.5 machines -----------------------------------------------------------------------------


class _Machine:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.name = f"machine.{kind}"

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        item_id = unit.unit_id
        work = work_id(unit.unit_id)
        if work not in sctx.variables:
            return _refused("SIZING_INPUT_UNAVAILABLE", f"{item_id}.W", "no work variable")
        doc = sctx.item(item_id)
        inlet, outlet = unit.ports["inlet"][0], unit.ports["outlet"][0]
        sign = -1.0 if self.kind == "turbine" else 1.0
        outputs = [OutputDef(size_output(item_id, "power"), "W", lambda s, a: sign * s.x(work))]
        size = {"power": size_output(item_id, "power")}
        refusals: list[Refusal] = []
        entries: list[RegimeEntry] = []
        theta: list[Theta] = []
        volume_records: tuple[SizingInput, ...] = ()
        if self.kind == "pump":
            flow, entry = sctx.flow(item_id, inlet, "LIQUID")
            entries.append(entry)
            if isinstance(flow, Refusal):
                refusals.append(flow)
                volume_theta, volume_records = sctx.volume_inputs(item_id, ())
            else:
                outputs += _pump_extras(item_id, flow, pressure_id(inlet), pressure_id(outlet))
                size |= {q: size_output(item_id, q) for q in ("vol_flow", "head")}
                volume_theta, volume_records = sctx.volume_inputs(item_id, (flow,))
            theta.extend(volume_theta)
        limitations: list[Limitation] = []
        items: list[SizedItem] = []
        if self.kind == "turbine":
            eta, record = sctx.input(
                item_id,
                "eta_gen",
                "1",
                item_key="generator_efficiency",
                default_key="generator_efficiency",
            )
            theta.append(eta)
            limitations.append(Limitation("GENERATOR_NOT_COSTED", item_id))
            generation: FunctionalBuilder = lambda s, a: -s.x(work) * s.theta(eta.theta_id)  # noqa: E731
            items.append(
                SizedItem(
                    item_id,
                    unit.unit_id,
                    "machine.turbine",
                    size,
                    (record,),
                    pressure_id(inlet),
                    _options(doc),
                    electricity="generation",
                    power=generation,
                )
            )
        else:
            family: ItemFamily = "machine.pump" if self.kind == "pump" else "machine.compressor"
            items.append(
                SizedItem(
                    item_id,
                    unit.unit_id,
                    family,
                    size,
                    volume_records,
                    pressure_id(outlet),
                    _options(doc),
                )
            )
            drive_id = sub_item(unit.unit_id, "drive")
            eta, record = sctx.input(
                drive_id,
                "eta_drive",
                "1",
                item_key="drive_efficiency",
                default_key="drive_efficiency",
            )
            theta.append(eta)

            def consumed(s: Symbols, a: Algebra) -> Expr:
                return s.x(work) / s.theta(eta.theta_id)

            outputs.append(OutputDef(size_output(drive_id, "power"), "W", consumed))
            items.append(
                SizedItem(
                    drive_id,
                    unit.unit_id,
                    "machine.drive",
                    {"power": size_output(drive_id, "power")},
                    (record,),
                    None,
                    _options(sctx.item(drive_id)),
                    electricity="consumption",
                    power=consumed,
                )
            )
        return SizingPlan(
            items=tuple(items),
            outputs=tuple(outputs),
            theta=tuple(theta),
            regime_entries=tuple(entries),
            refusals=tuple(refusals),
            limitations=tuple(limitations),
        )


def _pump_extras(item_id: str, flow: StreamFlow, p_in: str, p_out: str) -> list[OutputDef]:
    """`vol_flow = V̇_in`, `head = (P_out − P_in)·v_in/(M̄_in g) = ΔP·V̇_in/(ṁ_in g)` (§4.4.5)."""

    def head(s: Symbols, a: Algebra) -> Expr:
        lift = s.x(p_out) - s.x(p_in)
        return lift * s.out(size_output(item_id, "vol_flow")) / (flow.mass(s, a) * GRAVITY)

    return [
        OutputDef(size_output(item_id, "vol_flow"), "m3/s", flow.vdot),
        OutputDef(size_output(item_id, "head"), "m", head),
    ]


# -- §4.4.6 column -------------------------------------------------------------------------------


def actual_trays(trays: int, efficiency: float) -> int:
    """`N_act = ⌈N_tr / E_o⌉`, structural, with `E_o` read as the decimal it is written as (so
    `7 / 0.7` gives 10, not the 11 binary64 division gives)."""
    return math.ceil(Fraction(trays) / Fraction(repr(float(efficiency))))


class _Column:
    name = "column"

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        structure = unit.structure.structure
        u, n = unit.unit_id, int(structure.stage_count)
        design = max(float(p) for p in structure.pressures)
        plan = self._shell(sctx, unit).merged(
            SizingPlan(limitations=(Limitation("COLUMN_AUXILIARIES_NOT_COSTED", u),))
        )
        if structure.condenser != "none":
            duty = _duty(sctx, u, cascade_spec.stage_duty_id(u, 1))
            if duty is None:
                plan = plan.merged(_refused("SIZING_INPUT_UNAVAILABLE", f"{u}.condenser.Q"))
            else:
                plan = plan.merged(
                    exchanger_utility(
                        sctx,
                        sub_item(u, "condenser"),
                        u,
                        duty,
                        cascade_spec.stage_temperature_id(u, 2),
                        cascade_spec.stage_temperature_id(u, 1),
                        forced_service="cooling",
                        design_pressure=design,
                    )
                )
        if structure.reboiler != "none":
            duty = _duty(sctx, u, cascade_spec.stage_duty_id(u, n))
            if duty is None:
                plan = plan.merged(_refused("SIZING_INPUT_UNAVAILABLE", f"{u}.reboiler.Q"))
            else:
                plan = plan.merged(
                    exchanger_utility(
                        sctx,
                        sub_item(u, "reboiler"),
                        u,
                        duty,
                        cascade_spec.stage_temperature_id(u, n - 1),
                        cascade_spec.stage_temperature_id(u, n),
                        forced_service="heating",
                        design_pressure=design,
                    )
                )
        return plan

    def _shell(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        """The shell and trays (§4.4.6); a refusal here leaves the condenser and reboiler. The
        inputs are `_shell_inputs`'s, the stage walk and its refusals `_shell_stages`'s."""
        structure = unit.structure.structure
        u, n = unit.unit_id, int(structure.stage_count)
        condenser, reboiler = structure.condenser != "none", structure.reboiler != "none"
        first, last = (2 if condenser else 1), (n - 1 if reboiler else n)
        shell, trays_id = sub_item(u, "shell"), sub_item(u, "trays")
        inputs = _shell_inputs(sctx, shell)
        c_sb, f_flood, phi, s_tray, h_top, h_bottom, e_o = (t.theta_id for t, _ in inputs)
        n_tr = last - first + 1
        n_act = actual_trays(n_tr, inputs[6][0].value)  # E_o, structural
        stages = _shell_stages(sctx, u, shell, range(first, last + 1), (c_sb, f_flood, phi))
        if isinstance(stages, SizingPlan):
            return stages
        flows, entries, members = stages
        volume_theta, volume_records = sctx.volume_inputs(shell, flows)
        theta = [t for t, _ in inputs] + list(volume_theta)
        probe = [OutputDef(f"size.{shell}.s{name}.diameter", "m", b) for name, b in members]
        floats = sctx.values(probe, theta)
        values = {name: floats[f"size.{shell}.s{name}.diameter"] for name, _ in members}
        names = [name for name, _ in members]
        held = sctx.ctx.regime.choice(f"{shell}.controlling")
        controlling = held or names[select_argmax([values[name] for name in names])]
        if len(members) > 1:
            entries.append(
                RegimeEntry(
                    f"{shell}.controlling",
                    "argmax",
                    controlling,
                    "§4.3.2 rule 6",
                    argmax_rows(members, controlling, values),
                )
            )
        d2 = dict(members)[controlling]

        def diameter(s: Symbols, a: Algebra) -> Expr:
            return a.sqrt(d2(s, a))

        def height(s: Symbols, a: Algebra) -> Expr:
            return (n_act - 1) * s.theta(s_tray) + s.theta(h_top) + s.theta(h_bottom)

        design = max(float(p) for p in structure.pressures)
        doc = sctx.item(shell)
        outputs = [
            OutputDef(size_output(shell, "diameter"), "m", diameter),
            OutputDef(size_output(shell, "height"), "m", height),
            OutputDef(
                size_output(trays_id, "diameter"),
                "m",
                lambda s, a: s.out(size_output(shell, "diameter")),
            ),
        ]
        items = [
            SizedItem(
                shell,
                u,
                "column.shell",
                {q: size_output(shell, q) for q in ("diameter", "height")},
                (*(r for _, r in inputs), *volume_records),
                design,
                {**_options(doc), "orientation": "vertical"},
            ),
            SizedItem(
                trays_id,
                u,
                "column.trays",
                {"diameter": size_output(trays_id, "diameter")},
                (SizingInput("N_act", n_act, "1", False),),
                design,
                {**_options(sctx.item(trays_id)), "N_act": n_act},
            ),
        ]
        return SizingPlan(
            items=tuple(items),
            outputs=tuple(outputs),
            theta=tuple(theta),
            regime_entries=tuple(entries),
        )


def _shell_inputs(sctx: SizingContext, shell: str) -> list[tuple[Theta, SizingInput]]:
    """The shell's §4.4.6 inputs as `(θ, input)` pairs, in the order `C_SB`, `f_flood`,
    `phi_active`, `s_tray`, `H_top`, `H_bottom`, `E_o` (structural): each from the item, else the
    document's defaults, else the built-in default (`SizingContext.input`)."""
    return [
        sctx.input(shell, "C_SB", "m/s", default_key="column_C_SB"),
        sctx.input(
            shell,
            "f_flood",
            "1",
            item_key="flooding_fraction",
            default_key="column_flooding_fraction",
        ),
        sctx.input(
            shell,
            "phi_active",
            "1",
            item_key="active_area_fraction",
            default_key="column_active_area_fraction",
        ),
        sctx.input(
            shell, "s_tray", "m", item_key="tray_spacing", default_key="column_tray_spacing"
        ),
        sctx.input(shell, "H_top", "m", default_key="column_H_top"),
        sctx.input(shell, "H_bottom", "m", default_key="column_H_bottom"),
        sctx.input(
            shell,
            "E_o",
            "1",
            item_key="overall_efficiency",
            default_key="column_overall_efficiency",
            structural=True,
        ),
    ]


class _ShellStages(NamedTuple):
    """The shell's stage walk (§4.4.6): the live stages' vapour and liquid flows, every stage's
    dormant entries in stage order, and each live stage's `(j, D_j²)` member."""

    flows: list[StreamFlow]
    entries: list[RegimeEntry]
    members: list[tuple[str, FunctionalBuilder]]


def _shell_stages(
    sctx: SizingContext,
    u: str,
    shell: str,
    stages: range,
    d2_theta: tuple[str, str, str],
) -> _ShellStages | SizingPlan:
    """The shell's trays `stages` of column `u`, each with its vapour flow and, unless the vapour
    is dormant, its liquid flow and `_stage_d2` (`d2_theta`: the θ ids of `C_SB`, `f_flood`,
    `phi_active`). A refusal plan, with the entries so far, at the first stage whose vapour or
    liquid flow is refused or whose liquid is dormant; `SIZING_INPUT_UNAVAILABLE(<shell>.V)` when
    every stage's vapour is dormant."""
    c_sb, f_flood, phi = d2_theta
    flows: list[StreamFlow] = []
    components = sctx.ctx.view.components
    entries: list[RegimeEntry] = []
    members: list[tuple[str, FunctionalBuilder]] = []
    for j in stages:
        vap_ids = (
            tuple(cascade_spec.vapor_id(u, j, c) for c in components),
            cascade_spec.stage_temperature_id(u, j),
            cascade_spec.stage_pressure_id(u, j),
        )
        liq_ids = (
            tuple(cascade_spec.liquid_id(u, j, c) for c in components),
            vap_ids[1],
            vap_ids[2],
        )
        vapour, v_entry = sctx.flow(shell, f"stage.{j}.V", "VAPOR", state_ids=vap_ids)
        entries.append(v_entry)
        if isinstance(vapour, Refusal):
            return SizingPlan(refusals=(vapour,), regime_entries=tuple(entries))
        if vapour.dormant:
            continue
        liquid, l_entry = sctx.flow(
            shell, f"stage.{j}.L", "LIQUID", target="v_L", state_ids=liq_ids
        )
        entries.append(l_entry)
        if isinstance(liquid, Refusal):
            return SizingPlan(refusals=(liquid,), regime_entries=tuple(entries))
        if liquid.dormant:
            return SizingPlan(
                refusals=(Refusal("SIZING_INPUT_UNAVAILABLE", f"{shell}.rho_L", f"stage {j}"),),
                regime_entries=tuple(entries),
            )
        flows += (vapour, liquid)
        members.append((str(j), _stage_d2(vapour, liquid, c_sb, f_flood, phi)))
    if not members:
        return _refused("SIZING_INPUT_UNAVAILABLE", f"{shell}.V", "every tray's vapour is dormant")
    return _ShellStages(flows, entries, members)


def _stage_d2(
    vapour: StreamFlow, liquid: StreamFlow, c_sb: str, f_flood: str, phi: str
) -> FunctionalBuilder:
    """`D_j² = 4 V̇_j/(π f_flood φ_active u_f,j)`, `u_f,j = C_SB sqrt((ρ_L − ρ_V)/ρ_V)` (§4.4.6)."""

    def build(s: Symbols, a: Algebra) -> Expr:
        rho_l, rho_v = liquid.density(s, a), vapour.density(s, a)
        u_f = s.theta(c_sb) * a.sqrt((rho_l - rho_v) / rho_v)
        return 4.0 * vapour.vdot(s, a) / (math.pi * s.theta(f_flood) * s.theta(phi) * u_f)

    return build


# -- §4.4.7 reactor.vessel -----------------------------------------------------------------------


class _Reactor:
    """`<U>.vessel` with `V = τ_R·V̇_out` (§4.4.0, §4.4.7) and the duty item.

    `kinetic` (`syn001.kinetic_cstr`, §9.3 (i)): the outlet's phase is the unit's declared one,
    and the report carries the informational `implied_rate_constant = Da/τ_R` (s⁻¹). Otherwise
    (the conversion reactor) the phase is the provider's TP-flash label at the planning state."""

    name = "reactor.vessel"

    def __init__(self, *, kinetic: bool) -> None:
        self.kinetic = kinetic

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        u = unit.unit_id
        vessel = sub_item(u, "vessel")
        inlet, outlet = unit.ports["inlet"][0], unit.ports["outlet"][0]
        doc = sctx.item(vessel)
        plan = _empty()
        if "residence_time_s" not in doc:
            plan = _refused("SIZING_INPUT_MISSING", f"{vessel}.residence_time_s", "required")
        else:
            phase = unit.structure.phase if self.kinetic else _signature(sctx, outlet)
            if phase not in ("LIQUID", "VAPOR"):
                plan = _refused(
                    "SIZING_INPUT_UNAVAILABLE",
                    f"{vessel}.v",
                    f"outlet phase signature {phase!r} is not single-phase",
                )
            else:
                plan = self._vessel(sctx, unit, vessel, outlet, phase, pressure_id(inlet))
        duty = _duty(sctx, u)
        if _duty_item_needed(sctx, u, duty):
            assert duty is not None
            plan = plan.merged(
                exchanger_utility(
                    sctx,
                    sub_item(u, "duty"),
                    u,
                    duty,
                    temperature_id(outlet),
                    temperature_id(outlet),
                    design_pressure=pressure_id(inlet),
                    extra_limitations=(Limitation("JACKET_AS_EXCHANGER", sub_item(u, "duty")),),
                )
            )
        return plan

    def _vessel(
        self, sctx: SizingContext, unit: UnitRef, vessel: str, outlet: str, phase: Any, design: str
    ) -> SizingPlan:
        flow, entry = sctx.flow(vessel, outlet, phase)
        if isinstance(flow, Refusal):
            return SizingPlan(refusals=(flow,), regime_entries=(entry,))
        tau, tau_input = sctx.input(vessel, "tau_R", "s", item_key="residence_time_s")
        ld, ld_input = sctx.input(vessel, "LD", "1", default_key="reactor_LD")
        volume_theta, volume_records = sctx.volume_inputs(vessel, (flow,))
        informational: tuple[SizingInput, ...] = ()
        if self.kinetic:
            damkohler = unit.parameters[unit.structure.damkohler_parameter]
            informational = (
                SizingInput("implied_rate_constant", damkohler / tau.value, "1/s", False),
            )

        def volume(s: Symbols, a: Algebra) -> Expr:
            return s.theta(tau.theta_id) * flow.vdot(s, a)

        def diameter(s: Symbols, a: Algebra) -> Expr:
            return (
                4.0 * s.out(size_output(vessel, "volume")) / (math.pi * s.theta(ld.theta_id))
            ) ** _THIRD

        def height(s: Symbols, a: Algebra) -> Expr:
            return s.theta(ld.theta_id) * s.out(size_output(vessel, "diameter"))

        item = SizedItem(
            vessel,
            unit.unit_id,
            "reactor.vessel",
            {q: size_output(vessel, q) for q in ("volume", "diameter", "height")},
            (tau_input, ld_input, *volume_records, *informational),
            design,
            {**_options(sctx.item(vessel)), "orientation": "vertical"},
        )
        return SizingPlan(
            items=(item,),
            outputs=(
                OutputDef(size_output(vessel, "volume"), "m3", volume),
                OutputDef(size_output(vessel, "diameter"), "m", diameter),
                OutputDef(size_output(vessel, "height"), "m", height),
            ),
            theta=(tau, ld, *volume_theta),
            regime_entries=(entry,),
        )


# -- none / unsupported --------------------------------------------------------------------------


class _NoEquipment:
    name = "none"

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        return SizingPlan(no_equipment=(unit.unit_id,))


class _Unsupported:
    name = "unsupported"

    def plan(self, sctx: SizingContext, unit: UnitRef) -> SizingPlan:
        doc = sctx.item(unit.unit_id)
        if "quote" in doc or "exclude" in doc:
            return _empty()
        return _refused("NO_SIZING_MODEL", unit.unit_id, unit.model_id)


#: §4.4.0's table, with the registry's ids (WO-A2 facts: `syn001.liquid_pump`, `c1.tp_heater`,
#: `c1.tp_flash`, `c1.reactor`/`c1.reactor_standin`; the mixers, splitters, feeds and sinks).
_TABLE: tuple[tuple[tuple[str, ...], Any], ...] = (
    (("thermal.heater", "syn001.tp_heater", "c1.tp_heater"), _Heater()),
    (("syn001.heat_exchanger",), _ProcessExchanger()),
    (("thermal.flash", "syn001.tp_flash", "syn001.ph_flash", "c1.tp_flash"), _Flash()),
    (("thermal.pump", "syn001.liquid_pump"), _Machine("pump")),
    (("thermal.compressor",), _Machine("compressor")),
    (("thermal.turbine",), _Machine("turbine")),
    (("syn001.column",), _Column()),
    (("syn001.kinetic_cstr",), _Reactor(kinetic=True)),
    (("syn001.conversion_reactor",), _Reactor(kinetic=False)),
    (
        (
            "thermal.valve",
            "thermal.mixer",
            "syn001.valve",
            "syn001.adiabatic_mixer",
            "syn001.stream_splitter",
            "syn001.feed_source",
            "syn001.product_sink",
            "c1.adiabatic_mixer",
            "c1.stream_splitter",
            "c1.feed_source",
            "c1.product_sink",
        ),
        _NoEquipment(),
    ),
    (("syn001.component_separator", "c1.reactor", "c1.reactor_standin"), _Unsupported()),
)

for _ids, _family in _TABLE:
    for _model_id in _ids:
        register_family(_model_id, _family)
