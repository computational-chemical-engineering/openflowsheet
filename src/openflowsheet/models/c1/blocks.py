"""Property blocks over `pr-c1-v1`: the C1 units' bridge from the provider to a residual row.

Four block kinds (design note §14.2 B11, B17; register R-254, R-258), each a function of one
stream's `(n, T, P)` with one output and a dense declared pattern over its seven inputs (the
provider declares every one of them, `PropertyCapabilities.derivative_order`; SYN-001's blocks take
their pattern from the same declaration, `models.syn001.blocks`):

| Kind | Output | Phase |
| --- | --- | --- |
| `VapourEnthalpyFlow` | `Ḣ = Σn · h` (W) | VAPOR |
| `VapourLnPhiNH3` | `ln φ_NH3` of the vapour | VAPOR |
| `LiquidEnthalpyFlow` | `Ḣ = Σn · h` (W) | LIQUID (pure NH3) |
| `LiquidLnPhiNH3` | `ln φ_NH3` of the pure liquid | LIQUID (pure NH3) |

**A flowing stream** is the provider's: `Ḣ = Σn · h`, `∂Ḣ/∂n_j = h + Σn · ∂h/∂n_j`, `∂Ḣ/∂T = Σn ·
∂h/∂T` and the same for P; ln φ and its derivatives as the provider returns them. A provider refusal
(`unsupported`, `out_of_domain`) is an invalid trial (`DomainError`): a liquid carrying light gas
(`light_gas_in_liquid`) or with no liquid root, a metastable vapour root (B17).

**Exact dormancy** (every flow `+0.0` or `−0.0`) is where `Ḣ_V = Σ n_j h^ig_j(T) + n_tot h^dep` is
not differentiable: the departure is positively homogeneous of degree one and nonlinear in n. No
Jacobian there is *the* derivative, and the registered convention (B17, R-258) is:

- a vapour enthalpy flow is `0.0`, with `∂/∂n_j = h^ig_j(T)` (M01 §4.5's closed form,
  `pr_c1.h_ig`, read directly because the provider exposes no per-component property) and
  `∂/∂T = ∂/∂P = 0.0`, exact because `Ḣ(0, T, P) ≡ 0`: the ideal-gas limit;
- a vapour ln φ is `0.0` with every derivative `0.0`: the ideal gas;
- a liquid is pure NH3, composition-free, so ADR 0001 D3.1 does not forbid evaluating it: the
  provider is called at the probe `(0, 0, 1, 0, 0)` at `(T, P)` in LIQUID and, if it answers
  `no_liquid_root`, in VAPOR (the pure fluid's only root). The enthalpy flow is `0.0` with
  `∂Ḣ/∂n_j = h(probe)` for every j and `∂/∂T = ∂/∂P = 0.0`; ln φ is the probe's, with its T and P
  derivatives and `0.0` for every n. The fallback is never taken for a flowing liquid.

The convention moves no converged value: it acts on Newton's direction from an exactly dormant
iterate and on a regularity matrix's dormant columns. A finite-difference witness differs from it
at exactly dormant columns by design; tests exclude those columns and assert the convention there.

**Block ids** are the note's `<S>:Hdot:V`, `<S>:Hdot:L`, `<S>:lnphi_NH3:V` and `<S>:lnphi_NH3:L`
with `:` written `_` (`hdot_block_id`, `lnphi_block_id`): CasADi names a callback after its block
and admits letters, digits and single underscores only (`models.syn001.tp_state._token`). Named
after the stream, so two units that read one stream share one block (`models.assemble`
deduplicates by id).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from openflowsheet.compile.spec import DomainError
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError, flow_id, pressure_id, temperature_id
from openflowsheet.thermo import (
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.pr_c1 import COMPONENTS, PROVIDER_ID, h_ig

__all__ = [
    "LiquidEnthalpyFlow",
    "LiquidLnPhiNH3",
    "PROBE",
    "VapourEnthalpyFlow",
    "VapourLnPhiNH3",
    "block_feeding",
    "exactly_dormant",
    "hdot_block_id",
    "lnphi_block_id",
]

#: B17's liquid probe: one mol/s of NH3 and nothing else, the composition of every liquid
#: `pr-c1-v1` admits (R-143).
PROBE: Final[tuple[float, ...]] = (0.0, 0.0, 1.0, 0.0, 0.0)

#: The inputs in the order `input_ids` names them: the five flows, then T, then P.
_FLOWS: Final[tuple[str, ...]] = tuple(f"n_{c}" for c in COMPONENTS)
_INPUTS: Final[tuple[str, ...]] = (*_FLOWS, "T", "P")
_TEMPERATURE: Final = len(COMPONENTS)
_PRESSURE: Final = len(COMPONENTS) + 1
_SUFFIX: Final[dict[Phase, str]] = {"VAPOR": "V", "LIQUID": "L"}


def hdot_block_id(stream: str, phase: Phase) -> str:
    """`<S>:Hdot:<V|L>` (B12), as a CasADi-legal token."""
    return f"{stream}_Hdot_{_SUFFIX[phase]}"


def lnphi_block_id(stream: str, phase: Phase) -> str:
    """`<S>:lnphi_NH3:<V|L>` (B11), as a CasADi-legal token."""
    return f"{stream}_lnphi_NH3_{_SUFFIX[phase]}"


def block_feeding(stream: str) -> tuple[str, ...]:
    """The variables feeding a block of `stream`, in `input_ids` order."""
    return (
        *(flow_id(stream, c) for c in COMPONENTS),
        temperature_id(stream),
        pressure_id(stream),
    )


def exactly_dormant(n: Sequence[float]) -> bool:
    """B17's exact dormancy: every flow `+0.0` or `−0.0` (ADR 0001 D3.1; no threshold)."""
    return all(value == 0.0 for value in n)


def _unwrap(result: PropertyResult, block_id: str) -> PropertyResult:
    """A refusal is an invalid trial (B17); an `error` (a malformed request) is a defect."""
    if result.status == "ok":
        return result
    if result.status in ("out_of_domain", "unsupported"):
        raise DomainError(f"{block_id}: {result.status}: {result.message}")
    raise RuntimeError(f"{block_id}: provider returned {result.status}: {result.message}")


class _Block:
    """One output over `(n_H2, n_N2, n_NH3, n_Ar, n_CH4, T, P)`, densely declared."""

    _phase: Phase
    _output: str

    def __init__(
        self,
        provider: PropertyProvider,
        context: EvaluationContext,
        *,
        block_id: str,
    ) -> None:
        identity = provider.describe().provider_id
        if identity != PROVIDER_ID:
            raise SpecificationError(
                f"{block_id}: a {type(self).__name__} block evaluates {PROVIDER_ID}, not "
                f"{identity!r} (design note §14.2 B17)"
            )
        self._provider = provider
        self._context = context
        self._block_id = block_id

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return _INPUTS

    @property
    def output_ids(self) -> tuple[str, ...]:
        return (self._output,)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((0, column) for column in range(len(_INPUTS)))

    @staticmethod
    def _state(inputs: Sequence[float]) -> StreamState:
        return StreamState(
            n=tuple(float(value) for value in inputs[:_TEMPERATURE]),
            temperature=float(inputs[_TEMPERATURE]),
            pressure=float(inputs[_PRESSURE]),
        )

    def _request(
        self,
        state: StreamState,
        phase: Phase,
        properties: tuple[str, ...],
        derivatives: tuple[str, ...],
    ) -> PropertyResult:
        return self._provider.evaluate_phase(
            PropertyRequest(
                state=state, phase=phase, properties=properties, derivatives=derivatives
            ),
            self._context,
        )

    def _flowing(self, state: StreamState, derivatives: tuple[str, ...]) -> PropertyResult:
        return _unwrap(
            self._request(state, self._phase, (self._output,), derivatives), self._block_id
        )

    def _probe(self, state: StreamState, derivatives: tuple[str, ...]) -> PropertyResult:
        """B17's liquid probe at the dormant stream's `(T, P)`: LIQUID, else — on
        `no_liquid_root` — VAPOR, the pure fluid's only root."""
        probe = StreamState(n=PROBE, temperature=state.temperature, pressure=state.pressure)
        result = self._request(probe, "LIQUID", (self._output,), derivatives)
        if result.status == "unsupported" and result.message.startswith("no_liquid_root"):
            result = self._request(probe, "VAPOR", (self._output,), derivatives)
        return _unwrap(result, self._block_id)


class _EnthalpyFlow(_Block):
    """`Ḣ = Σn · h` of one phase; the flowing chain rule is shared by both phases."""

    _output = "h"

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        state = self._state(inputs)
        if exactly_dormant(state.n):
            return [0.0]
        result = self._flowing(state, ())
        return [state.total_flow * result.values["h"]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        state = self._state(inputs)
        if exactly_dormant(state.n):
            flows = self._dormant_flow_derivatives(state)
            return [
                *((0, column, value) for column, value in enumerate(flows)),
                (0, _TEMPERATURE, 0.0),
                (0, _PRESSURE, 0.0),
            ]
        result = self._flowing(state, _INPUTS)
        h, by = result.values["h"], result.derivatives["h"]
        total = state.total_flow
        return [
            *((0, column, h + total * by[name]) for column, name in enumerate(_FLOWS)),
            (0, _TEMPERATURE, total * by["T"]),
            (0, _PRESSURE, total * by["P"]),
        ]

    def _dormant_flow_derivatives(self, state: StreamState) -> tuple[float, ...]:
        raise NotImplementedError


class VapourEnthalpyFlow(_EnthalpyFlow):
    """`<S>:Hdot:V`: a vapour stream's enthalpy flow; the ideal-gas limit at exact dormancy."""

    _phase: Phase = "VAPOR"

    def _dormant_flow_derivatives(self, state: StreamState) -> tuple[float, ...]:
        return tuple(h_ig(state.temperature, index) for index in range(len(COMPONENTS)))


class LiquidEnthalpyFlow(_EnthalpyFlow):
    """`<S>:Hdot:L`: the pure-NH3 liquid's enthalpy flow; the probe's h at exact dormancy."""

    _phase: Phase = "LIQUID"

    def _dormant_flow_derivatives(self, state: StreamState) -> tuple[float, ...]:
        h = self._probe(state, ()).values["h"]
        return (h,) * len(COMPONENTS)


class VapourLnPhiNH3(_Block):
    """`<S>:lnphi_NH3:V`: ln φ_NH3 of a vapour stream; `0.0` with zero derivatives at exact
    dormancy (the ideal gas)."""

    _phase: Phase = "VAPOR"
    _output = "lnphi_NH3"

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        state = self._state(inputs)
        if exactly_dormant(state.n):
            return [0.0]
        return [self._flowing(state, ()).values[self._output]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        state = self._state(inputs)
        if exactly_dormant(state.n):
            return [(0, column, 0.0) for column in range(len(_INPUTS))]
        by = self._flowing(state, _INPUTS).derivatives[self._output]
        return [(0, column, by[name]) for column, name in enumerate(_INPUTS)]


class LiquidLnPhiNH3(_Block):
    """`<S>:lnphi_NH3:L`: ln φ_NH3 of the pure-NH3 liquid; the probe's at exact dormancy, with
    its T and P derivatives and `0.0` for every flow."""

    _phase: Phase = "LIQUID"
    _output = "lnphi_NH3"

    def _answer(self, state: StreamState, derivatives: tuple[str, ...]) -> PropertyResult:
        if exactly_dormant(state.n):
            return self._probe(state, derivatives)
        return self._flowing(state, derivatives)

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        return [self._answer(self._state(inputs), ()).values[self._output]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        state = self._state(inputs)
        if exactly_dormant(state.n):
            by = self._probe(state, ("T", "P")).derivatives[self._output]
            return [
                *((0, column, 0.0) for column in range(len(_FLOWS))),
                (0, _TEMPERATURE, by["T"]),
                (0, _PRESSURE, by["P"]),
            ]
        by = self._flowing(state, _INPUTS).derivatives[self._output]
        return [(0, column, by[name]) for column, name in enumerate(_INPUTS)]
