"""Pure-fluid property blocks for the `thermal.*` rows (S11 units design §4.3).

Every block is a `PropertyBlock` with analytic or implicit (implicit-function-theorem) first
derivatives. Each evaluates the provider at unit flow, since every property it reads is intensive
for a pure fluid; this is exact and never meets `dormant_state`.

**Trial states** (§4.1). A provider refusal that means "outside this regime's domain" —
`phase_not_stable`, `near_critical`, `no_saturation`, `out_of_domain` — is a `DomainError`, which
the compiled boundary reports as `invalid_trial_state`; any other refusal is a `RuntimeError` (a
defect). A trial outside the declared regime's region is outside that regime's domain
(blueprint §7.7).

**Block ids** satisfy the backend token rule of `tp_state._BLOCK_TOKEN`; an unusable stream or
unit id is refused, never sanitized.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, NoReturn

from openflowsheet.compile.spec import DomainError
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError
from openflowsheet.models.syn001.tp_state import _BLOCK_TOKEN
from openflowsheet.models.thermal import ADDITIVE_VAPOUR
from openflowsheet.models.thermal.kernel import (
    DOMAIN_CODES,
    Failure,
    Jet,
    Sat,
    _refusal,
    _solve,
    isentropic_temperature,
    phase_properties,
    saturation,
)
from openflowsheet.thermo import Phase, PropertyProvider, PropertyRequest, StreamState

__all__ = [
    "IsentropicEnthalpyBlock",
    "IsentropicState",
    "PhaseFlowBlock",
    "SaturatedFlowBlock",
    "isentropic_block_id",
    "isentropic_state",
    "phase_block_id",
    "saturated_block_id",
]

Variant = Literal[
    "pure-single/single", "pure-sat/single", "pure-single/sat", "pure-sat/sat", "additive-vapour"
]
#: The C = 1 variants: `pure-<inlet>/<isentropic state>`, each side single-phase or saturated.
PURE_VARIANTS: Final[tuple[str, ...]] = (
    "pure-single/single",
    "pure-sat/single",
    "pure-single/sat",
    "pure-sat/sat",
)
VARIANTS: Final[tuple[str, ...]] = (*PURE_VARIANTS, "additive-vapour")


def _token(name: str) -> str:
    if not _BLOCK_TOKEN.match(name):
        raise SpecificationError(
            f"id {name!r} cannot name a property block. The backend accepts a letter followed by "
            "letters, digits and non-consecutive underscores; sanitizing it here could quietly "
            "map two ids onto one block"
        )
    return name


def phase_block_id(stream: str, phase: Phase) -> str:
    """`PF_<S>_<phase>`: one block per (stream, phase); every reader names the same block."""
    return f"PF_{_token(stream)}_{phase.lower()}"


def saturated_block_id(stream: str) -> str:
    """`PFsat_<S>`: the saturated stream's block; producer and readers name the same one."""
    return f"PFsat_{_token(stream)}"


def isentropic_block_id(unit: str) -> str:
    """`PFs_<U>`: the machine's isentropic-enthalpy block."""
    return f"PFs_{_token(unit)}"


def _raise(failure: Failure, block_id: str) -> NoReturn:
    """A kernel or provider refusal as the exception the compiled boundary understands."""
    if failure.code in DOMAIN_CODES or failure.status == "out_of_domain":
        raise DomainError(f"{block_id}: {failure.message}")
    raise RuntimeError(f"{block_id}: provider returned {failure.status}: {failure.message}")


def _pure(provider: PropertyProvider, component: str) -> None:
    components = provider.describe().components
    if components != (component,):
        raise SpecificationError(
            f"a pure-fluid block needs a one-component provider for {component!r}, got {components}"
        )


class PhaseFlowBlock:
    """`(n, T, P) -> H = n h^phase(T, P)`, W; pure fluid only.

    Jacobian `[h, n dh/dT, n dh/dP]`. **Dormant rule** (n == 0.0 exactly): the value and the T and
    P entries are 0.0; the n entry is h^phase at the first point the provider answers — (T, P),
    then (T_sat(P), P) on the phase's own root — else `DomainError`. A convention that fixes
    Newton's direction off dormancy, never a converged value (S10-C's gamma-phi precedent).
    """

    def __init__(
        self,
        provider: PropertyProvider,
        component: str,
        phase: Phase,
        context: EvaluationContext,
        *,
        block_id: str,
    ) -> None:
        _pure(provider, component)
        self._provider = provider
        self._phase: Phase = phase
        self._context = context
        self._block_id = block_id

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return ("n", "T", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return ("H",)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0), (0, 1), (0, 2))

    def _h(self, temperature: float, pressure: float) -> Jet | Failure:
        jets = phase_properties(
            self._provider, self._context, temperature, pressure, self._phase, ("h",)
        )
        return jets if isinstance(jets, Failure) else jets["h"]

    def _answered(self, temperature: float, pressure: float) -> Jet:
        jet = self._h(temperature, pressure)
        if isinstance(jet, Failure):
            _raise(jet, self._block_id)
        return jet

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        total, temperature, pressure = (float(value) for value in inputs)
        if total == 0.0:
            return [0.0]
        return [total * self._answered(temperature, pressure)[0]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        total, temperature, pressure = (float(value) for value in inputs)
        if total == 0.0:
            return [(0, 0, self._dormant_slope(temperature, pressure)), (0, 1, 0.0), (0, 2, 0.0)]
        h, d_t, d_p = self._answered(temperature, pressure)
        return [(0, 0, h), (0, 1, total * d_t), (0, 2, total * d_p)]

    def _dormant_slope(self, temperature: float, pressure: float) -> float:
        first = self._h(temperature, pressure)
        if not isinstance(first, Failure):
            return first[0]
        if first.code not in DOMAIN_CODES and first.status != "out_of_domain":
            _raise(first, self._block_id)
        sat = saturation(self._provider, pressure, self._context)
        if isinstance(sat, Failure):
            raise DomainError(
                f"{self._block_id}: dormant, and h^{self._phase} is answered neither at "
                f"({temperature!r} K, {pressure!r} Pa) nor on the saturation line "
                f"({first.message}; {sat.message})"
            )
        return sat.value(self._phase, "h")


class SaturatedFlowBlock:
    """`(V, L, P) -> (Tsat, H)`: T_sat(P) and H = V h^V_sat(P) + L h^L_sat(P), W.

    Valid at any P in the saturation range, whatever the iterate's T. dTsat/dP is the provider's;
    dH/dP = V dh^V_s/dP + L dh^L_s/dP along the line, dh_s/dP = (dh/dT) dT_sat/dP + dh/dP.
    """

    def __init__(
        self,
        provider: PropertyProvider,
        component: str,
        context: EvaluationContext,
        *,
        block_id: str,
    ) -> None:
        _pure(provider, component)
        self._provider = provider
        self._context = context
        self._block_id = block_id

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return ("V", "L", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return ("Tsat", "H")

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 2), (1, 0), (1, 1), (1, 2))

    def _saturation(self, pressure: float) -> Sat:
        sat = saturation(self._provider, pressure, self._context)
        if isinstance(sat, Failure):
            _raise(sat, self._block_id)
        return sat

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        vapour, liquid, pressure = (float(value) for value in inputs)
        sat = self._saturation(pressure)
        return [
            sat.temperature,
            vapour * sat.value("VAPOR", "h") + liquid * sat.value("LIQUID", "h"),
        ]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        vapour, liquid, pressure = (float(value) for value in inputs)
        sat = self._saturation(pressure)
        return [
            (0, 2, sat.dtsat_dp),
            (1, 0, sat.value("VAPOR", "h")),
            (1, 1, sat.value("LIQUID", "h")),
            (1, 2, vapour * sat.along("VAPOR", "h") + liquid * sat.along("LIQUID", "h")),
        ]


# -- the isentropic state -------------------------------------------------------------------------


@dataclass(frozen=True)
class IsentropicState:
    """A pure fluid's isentropic state at P_O (§4.3), intensive, with what its derivatives need.

    `inlet` is s* and its T_I, P_I derivatives (the T_I entry is 0.0 for a saturated inlet, whose
    s* = s^{phi_I}_sat(P_I) moves only along the line). A single-phase isentropic state carries
    T_s and its `entropy` and `enthalpy` jets at (T_s, P_O); a saturated one carries `beta` and
    the saturation `sat` at P_O, with T_s = T_sat(P_O).
    """

    temperature: float
    inlet: Jet
    entropy: Jet | None = None
    enthalpy: Jet | None = None
    beta: float | None = None
    sat: Sat | None = None

    @property
    def h(self) -> float:
        """The intensive h_s, J/mol."""
        if self.sat is None:
            assert self.enthalpy is not None
            return self.enthalpy[0]
        assert self.beta is not None
        liquid, vapour = self.sat.value("LIQUID", "h"), self.sat.value("VAPOR", "h")
        return liquid + self.beta * (vapour - liquid)


def isentropic_state(
    provider: PropertyProvider,
    context: EvaluationContext,
    variant: Variant,
    inlet_phase: Phase,
    isentropic_phase: Phase,
    inlet_temperature: float | None,
    inlet_pressure: float,
    outlet_pressure: float,
) -> IsentropicState | Failure:
    """The pure variants' isentropic state (§4.3), or a typed refusal.

    s* is s^{phi_I}(T_I, P_I), or s^{phi_I}_sat(P_I) for a saturated inlet. A single-phase
    isentropic state solves s^{phi_s}(T_s, P_O) = s* from the inlet temperature (T_sat(P_I) for a
    saturated inlet); a saturated one is beta_s = (s* - s^L_sat)/(s^V_sat - s^L_sat) at P_O. No
    root on phi_s's side, or beta_s outside [0, 1], is `isentropic_state_two_phase`: the
    isentropic state lies past the declared one (S11C_DECISIONS C3-2).
    """
    if variant not in PURE_VARIANTS:
        raise ValueError(f"{variant!r} is not a pure-fluid isentropic variant")
    inlet_side, outlet_side = variant.removeprefix("pure-").split("/")
    if inlet_side == "sat":
        at_inlet = saturation(provider, inlet_pressure, context)
        if isinstance(at_inlet, Failure):
            return at_inlet
        inlet: Jet = (
            at_inlet.value(inlet_phase, "s"),
            0.0,
            at_inlet.along(inlet_phase, "s"),
        )
        start = at_inlet.temperature
    else:
        if inlet_temperature is None:
            raise ValueError(f"{variant} needs the inlet temperature")
        jets = phase_properties(
            provider, context, inlet_temperature, inlet_pressure, inlet_phase, ("s",)
        )
        if isinstance(jets, Failure):
            return jets
        inlet, start = jets["s"], inlet_temperature

    if outlet_side == "single":
        solved = isentropic_temperature(
            provider, context, inlet[0], outlet_pressure, isentropic_phase, start
        )
        if isinstance(solved, Failure):
            return solved
        temperature = solved[0]
        found: dict[str, Jet] = {}
        for name in ("s", "h"):
            answered = phase_properties(
                provider, context, temperature, outlet_pressure, isentropic_phase, (name,)
            )
            if isinstance(answered, Failure):
                return answered
            found[name] = answered[name]
        return IsentropicState(temperature, inlet, entropy=found["s"], enthalpy=found["h"])

    sat = saturation(provider, outlet_pressure, context)
    if isinstance(sat, Failure):
        return sat
    liquid, vapour = sat.value("LIQUID", "s"), sat.value("VAPOR", "s")
    beta = (inlet[0] - liquid) / (vapour - liquid)
    if not 0.0 <= beta <= 1.0:
        return Failure(
            "unsupported",
            "isentropic_state_two_phase",
            f"s* = {inlet[0]!r} gives beta_s = {beta!r} at {outlet_pressure!r} Pa: the isentropic "
            "state is single-phase, not the declared saturated one",
        )
    return IsentropicState(sat.temperature, inlet, beta=beta, sat=sat)


class IsentropicEnthalpyBlock:
    """`PFs_<U>`: the machine's isentropic enthalpy flow `Hs` (§4.3), one of five variants.

    Pure variants (C = 1; `isentropic_state` gives the state):
    - `pure-single/single`, inputs (n, T_I, P_I, P_O): Hs = n h^{phi_s}(T_s, P_O). Derivatives by
      the implicit function theorem on F = s^{phi_s}(T_s, P_O) - s*: dT_s/dx = -(dF/dx)/(dF/dT_s),
      then dHs/dx = n (dh/dT_s) dT_s/dx + n dh/dx|_{T_s}; dT_s/dn = 0 exactly for C = 1.
      Identities (A49): dHs/dT_I = n T_s c_p,I / T_I and dHs/dP_O = n v_s.
    - `pure-sat/single`, inputs (n, P_I, P_O): as above with s* = s^{phi_I}_sat(P_I), whose P_I
      derivative is taken along the line.
    - `pure-single/sat` and `pure-sat/sat`: Hs = n [h^L_sat + beta_s (h^V_sat - h^L_sat)](P_O);
      d(beta_s)/dx = (ds*/dx)/ds_vap for x in {T_I, P_I}, and at P_O
      d(beta_s)/dP_O = -(ds^L_sat/dP + beta_s d(ds_vap)/dP)/ds_vap; dHs/dn is the bracket.

    `additive-vapour` (Wilson), inputs (n_1..n_C, T_I, P_I, P_O): T_s solves
    sum_j n_j [s_j(T_s, P_O) - s_j(T_I, P_I)] = 0 by the kernel's safeguarded Newton from T_I on the
    provider's T domain, s_j and h_j the provider's VAPOR s and h at the pure composition e_j;
    Hs = sum_j n_j h_j(T_s, P_O). Admitted by identity only (`ADDITIVE_VAPOUR`), phase VAPOR.

    A state past the declared isentropic one (`isentropic_state_two_phase`) is a `DomainError` at
    a trial (§4.3); the evaluate refuses it first at a solution.

    **Dormant rule** (n == 0.0; n_tot == 0.0 for `additive-vapour`): value 0.0. For C = 1 the
    derivatives are evaluated at n = 1 and the n entry is the intensive value, the others 0.0. For
    `additive-vapour` T_s and the derivatives are evaluated at the probe n = (1, ..., 1) and the
    T and P entries are scaled by 0.0 (S10-C's convention).
    """

    def __init__(
        self,
        provider: PropertyProvider,
        component: str | tuple[str, ...],
        context: EvaluationContext,
        *,
        block_id: str,
        variant: Variant,
        inlet_phase: Phase,
        isentropic_phase: Phase,
    ) -> None:
        if variant not in VARIANTS:
            raise SpecificationError(
                f"isentropic block variant {variant!r} is not one of {VARIANTS}"
            )
        if variant == "additive-vapour":
            components = (component,) if isinstance(component, str) else tuple(component)
            _additive(provider, components, inlet_phase, isentropic_phase)
            self._components = components
        else:
            if not isinstance(component, str):
                raise SpecificationError(f"{variant} is a pure-fluid variant; got {component!r}")
            _pure(provider, component)
            self._components = (component,)
        self._provider = provider
        self._context = context
        self._block_id = block_id
        self._variant: Variant = variant
        self._inlet_phase: Phase = inlet_phase
        self._phase: Phase = isentropic_phase

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def variant(self) -> str:
        return self._variant

    @property
    def _saturated_inlet(self) -> bool:
        return self._variant.startswith("pure-sat/")

    @property
    def input_ids(self) -> tuple[str, ...]:
        if self._variant == "additive-vapour":
            return (*(f"n_{name}" for name in self._components), "T_I", "P_I", "P_O")
        if self._saturated_inlet:
            return ("n", "P_I", "P_O")
        return ("n", "T_I", "P_I", "P_O")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return ("Hs",)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((0, column) for column in range(len(self.input_ids)))

    # -- pure variants -------------------------------------------------------------------------

    def state(
        self, inlet_temperature: float | None, inlet_pressure: float, outlet_pressure: float
    ) -> IsentropicState:
        """The pure variants' isentropic state; a refusal raised as the compiled boundary wants."""
        answer = isentropic_state(
            self._provider,
            self._context,
            self._variant,
            self._inlet_phase,
            self._phase,
            inlet_temperature,
            inlet_pressure,
            outlet_pressure,
        )
        if isinstance(answer, Failure):
            if answer.code == "isentropic_state_two_phase":
                raise DomainError(f"{self._block_id}: {answer.message}")
            _raise(answer, self._block_id)
        return answer

    def _pure_inputs(self, inputs: Sequence[float]) -> tuple[float, float | None, float, float]:
        if self._saturated_inlet:
            total, p_in, p_out = (float(value) for value in inputs)
            return total, None, p_in, p_out
        total, t_in, p_in, p_out = (float(value) for value in inputs)
        return total, t_in, p_in, p_out

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        if self._variant == "additive-vapour":
            return self._additive_values(inputs)
        total, t_in, p_in, p_out = self._pure_inputs(inputs)
        if total == 0.0:
            return [0.0]
        return [total * self.state(t_in, p_in, p_out).h]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        if self._variant == "additive-vapour":
            return self._additive_jacobian(inputs)
        total, t_in, p_in, p_out = self._pure_inputs(inputs)
        state = self.state(t_in, p_in, p_out)
        inlet = state.inlet
        scale = total  # dormant: T, P entries carry the zero flow
        if state.sat is None:
            assert state.entropy is not None and state.enthalpy is not None
            h, h_t, h_p = state.enthalpy
            _, s_t, s_p = state.entropy
            dts_dtin = inlet[1] / s_t
            dts_dpin = inlet[2] / s_t
            dts_dpout = -s_p / s_t
            d_tin = scale * h_t * dts_dtin
            d_pin = scale * h_t * dts_dpin
            d_pout = scale * (h_t * dts_dpout + h_p)
        else:
            assert state.beta is not None
            sat, beta = state.sat, state.beta
            h_l, h_v = sat.value("LIQUID", "h"), sat.value("VAPOR", "h")
            ds_vap = sat.value("VAPOR", "s") - sat.value("LIQUID", "s")
            dh_vap = h_v - h_l
            h = h_l + beta * dh_vap
            s_l_p, s_v_p = sat.along("LIQUID", "s"), sat.along("VAPOR", "s")
            h_l_p, h_v_p = sat.along("LIQUID", "h"), sat.along("VAPOR", "h")
            dbeta_dpout = -(s_l_p + beta * (s_v_p - s_l_p)) / ds_vap
            d_tin = scale * dh_vap * (inlet[1] / ds_vap)
            d_pin = scale * dh_vap * (inlet[2] / ds_vap)
            d_pout = scale * (h_l_p + beta * (h_v_p - h_l_p) + dh_vap * dbeta_dpout)
        if self._saturated_inlet:
            return [(0, 0, h), (0, 1, d_pin), (0, 2, d_pout)]
        return [(0, 0, h), (0, 1, d_tin), (0, 2, d_pin), (0, 3, d_pout)]

    # -- additive-vapour -----------------------------------------------------------------------

    def _component_jets(self, index: int, temperature: float, pressure: float) -> dict[str, Jet]:
        """s_j and h_j, the provider's VAPOR s and h at e_j, with their T and P derivatives."""
        flows = tuple(1.0 if k == index else 0.0 for k in range(len(self._components)))
        result = self._provider.evaluate_phase(
            PropertyRequest(
                state=StreamState(n=flows, temperature=temperature, pressure=pressure),
                phase="VAPOR",
                properties=("s", "h"),
                derivatives=("T", "P"),
            ),
            self._context,
        )
        if result.status != "ok":
            _raise(_refusal(result.status, result.message), self._block_id)
        return {
            name: (
                result.values[name],
                result.derivatives[name]["T"],
                result.derivatives[name]["P"],
            )
            for name in ("s", "h")
        }

    def _additive_state(
        self, flows: tuple[float, ...], t_in: float, p_in: float, p_out: float
    ) -> tuple[float, list[dict[str, Jet]], list[dict[str, Jet]]]:
        """`(T_s, jets at (T_I, P_I), jets at (T_s, P_O))` per component."""
        count = len(self._components)
        at_inlet = [self._component_jets(j, t_in, p_in) for j in range(count)]
        target = sum(n_j * jets["s"][0] for n_j, jets in zip(flows, at_inlet, strict=True))

        def evaluate(temperature: float) -> tuple[float, float]:
            at = [self._component_jets(j, temperature, p_out) for j in range(count)]
            entropy = sum(n_j * jets["s"][0] for n_j, jets in zip(flows, at, strict=True))
            slope = sum(n_j * jets["s"][1] for n_j, jets in zip(flows, at, strict=True))
            return entropy - target, slope

        t_low, t_high = (float(value) for value in self._provider.describe().domain["T"])
        solved = _solve(
            evaluate,
            t_low,
            t_high,
            start=t_in,
            what=f"additive-vapour isentropic state at {p_out!r} Pa",
        )
        if isinstance(solved, Failure):
            _raise(solved, self._block_id)
        temperature = solved[0]
        at_outlet = [self._component_jets(j, temperature, p_out) for j in range(count)]
        return temperature, at_inlet, at_outlet

    def _additive_inputs(
        self, inputs: Sequence[float]
    ) -> tuple[tuple[float, ...], float, float, float]:
        count = len(self._components)
        flows = tuple(float(value) for value in inputs[:count])
        t_in, p_in, p_out = (float(value) for value in inputs[count:])
        return flows, t_in, p_in, p_out

    def _additive_values(self, inputs: Sequence[float]) -> Sequence[float]:
        flows, t_in, p_in, p_out = self._additive_inputs(inputs)
        if sum(flows) == 0.0:
            return [0.0]
        _, _, at_outlet = self._additive_state(flows, t_in, p_in, p_out)
        return [sum(n_j * jets["h"][0] for n_j, jets in zip(flows, at_outlet, strict=True))]

    def _additive_jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        flows, t_in, p_in, p_out = self._additive_inputs(inputs)
        count = len(flows)
        dormant = sum(flows) == 0.0
        if dormant:
            flows = (1.0,) * count
        _, at_inlet, at_outlet = self._additive_state(flows, t_in, p_in, p_out)
        pairs = list(zip(flows, at_inlet, at_outlet, strict=True))
        slope = sum(n_j * out["s"][1] for n_j, _, out in pairs)
        h_t = sum(n_j * out["h"][1] for n_j, _, out in pairs)
        h_p = sum(n_j * out["h"][2] for n_j, _, out in pairs)
        dts_dtin = sum(n_j * inn["s"][1] for n_j, inn, _ in pairs) / slope
        dts_dpin = sum(n_j * inn["s"][2] for n_j, inn, _ in pairs) / slope
        dts_dpout = -sum(n_j * out["s"][2] for n_j, _, out in pairs) / slope
        scale = 0.0 if dormant else 1.0
        entries = [
            (0, j, out["h"][0] - h_t * (out["s"][0] - inn["s"][0]) / slope)
            for j, (_, inn, out) in enumerate(pairs)
        ]
        entries += [
            (0, count, scale * h_t * dts_dtin),
            (0, count + 1, scale * h_t * dts_dpin),
            (0, count + 2, scale * (h_t * dts_dpout + h_p)),
        ]
        return entries


def _additive(
    provider: PropertyProvider,
    components: tuple[str, ...],
    inlet_phase: Phase,
    isentropic_phase: Phase,
) -> None:
    """The additive premise is admitted by identity only (§4.3), for a vapour on both sides."""
    described = provider.describe()
    identity = (described.provider_id, described.reference_convention)
    if identity not in ADDITIVE_VAPOUR:
        raise SpecificationError(
            f"the additive-vapour isentropic block is admitted only on {sorted(ADDITIVE_VAPOUR)}; "
            f"got {identity}"
        )
    if tuple(described.components) != components:
        raise SpecificationError(
            f"the additive-vapour block is built for {components}, the provider has "
            f"{tuple(described.components)}"
        )
    if (inlet_phase, isentropic_phase) != ("VAPOR", "VAPOR"):
        raise SpecificationError(
            f"the additive-vapour block is a vapour on both sides, got {inlet_phase}, "
            f"{isentropic_phase}"
        )
