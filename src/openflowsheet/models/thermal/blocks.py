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
from typing import Final, Literal, NoReturn

from openflowsheet.compile.spec import DomainError
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError
from openflowsheet.models.syn001.tp_state import _BLOCK_TOKEN
from openflowsheet.models.thermal.kernel import (
    DOMAIN_CODES,
    Failure,
    Jet,
    Sat,
    isentropic_temperature,
    phase_properties,
    saturation,
)
from openflowsheet.thermo import Phase, PropertyProvider

__all__ = [
    "IsentropicEnthalpyBlock",
    "PhaseFlowBlock",
    "SaturatedFlowBlock",
    "isentropic_block_id",
    "phase_block_id",
    "saturated_block_id",
]

Variant = Literal["pure-single/single"]
VARIANTS: Final[tuple[str, ...]] = ("pure-single/single",)


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


class IsentropicEnthalpyBlock:
    """`PFs_<U>`: the machine's isentropic enthalpy flow `Hs` (§4.3), one of five variants.

    `pure-single/single`: inputs (n, T_I, P_I, P_O); s* = s^{phi_I}(T_I, P_I); T_s solves
    s^{phi_s}(T_s, P_O) = s* on phi_s's side of T_sat(P_O) by the kernel's safeguarded Newton from
    T_I; Hs = n h^{phi_s}(T_s, P_O). Derivatives by the implicit function theorem on
    F = s^{phi_s}(T_s, P_O) - s^{phi_I}(T_I, P_I): dT_s/dx = -(dF/dx)/(dF/dT_s), then
    dHs/dx = n (dh/dT_s) dT_s/dx + n dh/dx|_{T_s}; dT_s/dn = 0 exactly for C = 1.
    Identities (A49): dHs/dT_I = n T_s c_p,I / T_I and dHs/dP_O = n v_s.

    **Dormant rule** (n == 0.0): value 0.0; the derivatives are evaluated at n = 1 and the n entry
    is the intensive h_s, the others 0.0.
    """

    def __init__(
        self,
        provider: PropertyProvider,
        component: str,
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
        _pure(provider, component)
        self._provider = provider
        self._context = context
        self._block_id = block_id
        self._variant = variant
        self._inlet_phase: Phase = inlet_phase
        self._phase: Phase = isentropic_phase

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def variant(self) -> str:
        return self._variant

    @property
    def input_ids(self) -> tuple[str, ...]:
        return ("n", "T_I", "P_I", "P_O")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return ("Hs",)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0), (0, 1), (0, 2), (0, 3))

    def _jets(self, name: str, temperature: float, pressure: float, phase: Phase) -> Jet:
        jets = phase_properties(
            self._provider, self._context, temperature, pressure, phase, (name,)
        )
        if isinstance(jets, Failure):
            _raise(jets, self._block_id)
        return jets[name]

    def state(
        self, inlet_temperature: float, inlet_pressure: float, outlet_pressure: float
    ) -> tuple[float, Jet, Jet, Jet]:
        """`(T_s, s^{phi_I} jet at the inlet, s^{phi_s} jet at T_s, h^{phi_s} jet at T_s)`."""
        inlet = self._jets("s", inlet_temperature, inlet_pressure, self._inlet_phase)
        solved = isentropic_temperature(
            self._provider,
            self._context,
            inlet[0],
            outlet_pressure,
            self._phase,
            inlet_temperature,
        )
        if isinstance(solved, Failure):
            if solved.code == "isentropic_state_two_phase":
                raise DomainError(f"{self._block_id}: {solved.message}")
            _raise(solved, self._block_id)
        temperature = solved[0]
        entropy = self._jets("s", temperature, outlet_pressure, self._phase)
        enthalpy = self._jets("h", temperature, outlet_pressure, self._phase)
        return temperature, inlet, entropy, enthalpy

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        total, t_in, p_in, p_out = (float(value) for value in inputs)
        if total == 0.0:
            return [0.0]
        _, _, _, enthalpy = self.state(t_in, p_in, p_out)
        return [total * enthalpy[0]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        total, t_in, p_in, p_out = (float(value) for value in inputs)
        _, inlet, entropy, enthalpy = self.state(t_in, p_in, p_out)
        h, h_t, h_p = enthalpy
        _, s_t, s_p = entropy
        dts_dtin = inlet[1] / s_t
        dts_dpin = inlet[2] / s_t
        dts_dpout = -s_p / s_t
        scale = total  # dormant: T, P entries carry the zero flow
        return [
            (0, 0, h),
            (0, 1, scale * h_t * dts_dtin),
            (0, 2, scale * h_t * dts_dpin),
            (0, 3, scale * (h_t * dts_dpout + h_p)),
        ]
