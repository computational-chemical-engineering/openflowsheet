"""The column's property blocks for the γ–φ-IG form (S10-C design note §4.7, ADR 0049 D6).

SYN-001's `LnKBlock` takes `(T, P)` only and evaluates `lnK` at a composition-neutral probe,
because SYN-001's K does not depend on composition. For `gamma-phi-ig-v1`,
`ln K_i = ln φ_i^L(T, P, x)` (the provider's vapour `ln φ` is identically zero, which the column's
`admission` checks), so the K-block reads the stage's **liquid flows** as well, and its Jacobian
carries the provider's projected composition derivatives: at `n = l` they *are* `∂ ln K_i/∂l_j`.
The enthalpy block is a single-output mixture block `Ḣ = n_tot h` (the flowing formulas of
`models/c1/blocks.py`): the γ–φ-IG provider declares a mixture `h`, not `h_<c>`.

**Dormant inputs.** The float evaluator evaluates every block at every state, and a dormant state
has no composition, so neither block ever sends one to the provider (ADR 0001 D3.1):

- the K-block evaluates at the probe `n = (1, …, 1)` and stores `0.0` in every `n` column. Every
  row reading it multiplies `K_i` by a flow of the block's own input (`v_i L − K_i l_i V`,
  `Σ K_i v_{2,i} − V_2`), so at a dormant input the row's value and its entries through `ln K` are
  zero whatever the block returns. The rows' *direct* flow entries (`−K_i V` in `∂/∂l_i`) do read
  the probe's K; a regime in which the liquid is dormant (`VAPOR`) pins those columns and drops
  those rows, so the convention moves nothing that regime solves for, and on an exactly dormant
  two-phase iterate it fixes Newton's direction, not a converged value;
- the enthalpy block returns `Ḣ = 0.0` and, for `∂Ḣ/∂n_j`, `h(T, P, e_j)` of the block's phase
  from one pure-component probe per component (exact here because `Ḣ` is linear in `n`; for any
  provider it is the derivative along each axis); its `T` and `P` entries are `0.0`.

Provider refusals become the exceptions the compiled boundary understands (`blocks._unwrap`).
"""

from __future__ import annotations

from collections.abc import Sequence

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.blocks import _unwrap
from openflowsheet.thermo import (
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)

__all__ = ["GammaPhiLnKBlock", "MixtureEnthalpyFlowBlock", "probe_flows"]


def probe_flows(count: int) -> tuple[float, ...]:
    """The K-block's composition-neutral probe for a dormant liquid: a unit flow of every
    component (design note §4.7)."""
    return (1.0,) * count


def _state(inputs: Sequence[float], count: int) -> StreamState:
    return StreamState(
        n=tuple(float(value) for value in inputs[:count]),
        temperature=float(inputs[count]),
        pressure=float(inputs[count + 1]),
    )


class GammaPhiLnKBlock:
    """`(n_1…n_C, T, P) -> (lnK_i)` with `lnK_i = ln φ_i^L(T, P, n)`. Dense `C × (C + 2)`.

    The output ids are `LnKBlock`'s, so `equilibrium_row` and `bubble_row` read it unchanged.
    """

    def __init__(
        self,
        provider: PropertyProvider,
        components: tuple[str, ...],
        context: EvaluationContext,
        *,
        block_id: str,
    ) -> None:
        self._provider = provider
        self._components = components
        self._context = context
        self._block_id = block_id
        self._lnphi = tuple(f"lnphi_{name}" for name in components)
        self._flows = tuple(f"n_{name}" for name in components)

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return (*self._flows, "T", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return tuple(f"lnK_{name}" for name in self._components)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        count = len(self._components)
        return tuple((row, column) for row in range(count) for column in range(count + 2))

    def _request(self, state: StreamState, derivatives: tuple[str, ...]) -> PropertyResult:
        return _unwrap(
            self._provider.evaluate_phase(
                PropertyRequest(
                    state=state,
                    phase="LIQUID",
                    properties=self._lnphi,
                    derivatives=derivatives,
                ),
                self._context,
            ),
            self._block_id,
        )

    def _evaluated(self, inputs: Sequence[float]) -> tuple[StreamState, bool]:
        """The state the provider is asked at (the probe when the input is dormant)."""
        count = len(self._components)
        state = _state(inputs, count)
        if not state.is_dormant:
            return state, False
        probe = StreamState(
            n=probe_flows(count), temperature=state.temperature, pressure=state.pressure
        )
        return probe, True

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        state, _ = self._evaluated(inputs)
        result = self._request(state, ())
        return [result.values[name] for name in self._lnphi]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        state, dormant = self._evaluated(inputs)
        count = len(self._components)
        if dormant:
            result = self._request(state, ("T", "P"))
        else:
            result = self._request(state, (*self._flows, "T", "P"))
        triples: list[tuple[int, int, float]] = []
        for row, name in enumerate(self._lnphi):
            entry = result.derivatives[name]
            for column, wrt in enumerate(self._flows):
                triples.append((row, column, 0.0 if dormant else entry[wrt]))
            triples.append((row, count, entry["T"]))
            triples.append((row, count + 1, entry["P"]))
        return triples


class MixtureEnthalpyFlowBlock:
    """`(n_1…n_C, T, P) -> (H)` with `H = n_tot h^phase(T, P, n)`, W. Dense `1 × (C + 2)`.

    `∂H/∂n_j = h + n_tot ∂h/∂n_j`, `∂H/∂T = n_tot ∂h/∂T`, `∂H/∂P = n_tot ∂h/∂P`.
    """

    def __init__(
        self,
        provider: PropertyProvider,
        components: tuple[str, ...],
        phase: Phase,
        context: EvaluationContext,
        *,
        block_id: str,
    ) -> None:
        self._provider = provider
        self._components = components
        self._phase = phase
        self._context = context
        self._block_id = block_id
        self._flows = tuple(f"n_{name}" for name in components)

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return (*self._flows, "T", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return ("H",)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((0, column) for column in range(len(self._components) + 2))

    def _request(self, state: StreamState, derivatives: tuple[str, ...]) -> PropertyResult:
        return _unwrap(
            self._provider.evaluate_phase(
                PropertyRequest(
                    state=state, phase=self._phase, properties=("h",), derivatives=derivatives
                ),
                self._context,
            ),
            self._block_id,
        )

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        state = _state(inputs, len(self._components))
        if state.is_dormant:
            # ADR 0001 D3.1: a dormant stream's enthalpy flow is exactly zero, with no evaluation.
            return [0.0]
        return [state.total_flow * self._request(state, ()).values["h"]]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        count = len(self._components)
        state = _state(inputs, count)
        if state.is_dormant:
            pure = tuple(
                self._request(
                    StreamState(
                        n=tuple(1.0 if k == j else 0.0 for k in range(count)),
                        temperature=state.temperature,
                        pressure=state.pressure,
                    ),
                    (),
                ).values["h"]
                for j in range(count)
            )
            return [
                *((0, column, value) for column, value in enumerate(pure)),
                (0, count, 0.0),
                (0, count + 1, 0.0),
            ]
        result = self._request(state, (*self._flows, "T", "P"))
        h, by = result.values["h"], result.derivatives["h"]
        total = state.total_flow
        return [
            *((0, column, h + total * by[name]) for column, name in enumerate(self._flows)),
            (0, count, total * by["T"]),
            (0, count + 1, total * by["P"]),
        ]
