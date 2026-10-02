"""Property blocks: the bridge from a `PropertyProvider` to a residual expression.

A row builder works on symbols, a provider works on numbers. `PropertyBlock` is the seam, and it
has one hard obligation: **declare the Jacobian sparsity**. Without the declaration a backend
propagates the dependency structure of an opaque call — every output on every input — and the
block's structural zeros come back as stored zeros. P02 measured that as 66 stored entries where
60 were expected.

**What these blocks do not claim.** The pattern is built from what the provider *declares* in
`PropertyCapabilities.derivative_order`, not from what is identically zero. SYN-001's vapour
enthalpy has no pressure dependence at all, and the provider still declares `P: 1` and returns
`0.0` for it — which is the right thing for the provider to do (a zero derivative and an absent
one are different answers) and leaves this block no way to tell the two apart. So a vapour
enthalpy block declares a pressure column and stores exact zeros in it. That is an efficiency
cost, not a correctness one, and it is stated rather than papered over by hard-coding SYN-001's
enthalpy formula here — a model that knows its provider's algebra is a model that stops being
replaceable (blueprint §5.3).
"""

from __future__ import annotations

from collections.abc import Sequence

from openflowsheet.compile.spec import DomainError
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    Phase,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)

#: `lnK` and `h` are state functions of (T, P) in an ideal package, but `PropertyRequest` always
#: carries a full `StreamState`, and a dormant one would (correctly) be refused a composition-
#: dependent property. A block evaluating `lnK` therefore passes a unit flow of every component:
#: a flowing, composition-neutral state that cannot be mistaken for a physical stream.
_PROBE_FLOW = 1.0


def _unwrap(result: PropertyResult, block_id: str) -> PropertyResult:
    """Turn a non-`ok` provider answer into the exception the compiled boundary understands."""
    if result.status == "ok":
        return result
    if result.status == "out_of_domain":
        raise DomainError(f"{block_id}: {result.message}")
    raise RuntimeError(f"{block_id}: provider returned {result.status}: {result.message}")


class LnKBlock:
    """`(T, P) -> (lnK_i)`. Dense: every K-value depends on both coordinates."""

    def __init__(
        self,
        provider: PropertyProvider,
        components: tuple[str, ...],
        context: EvaluationContext,
        *,
        block_id: str = "lnK",
    ) -> None:
        self._provider = provider
        self._components = components
        self._context = context
        self._block_id = block_id

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return ("T", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return tuple(f"lnK_{name}" for name in self._components)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((row, column) for row in range(len(self._components)) for column in range(2))

    def _request(self, inputs: Sequence[float], derivatives: tuple[str, ...]) -> PropertyResult:
        temperature, pressure = float(inputs[0]), float(inputs[1])
        state = StreamState(
            n=(_PROBE_FLOW,) * len(self._components),
            temperature=temperature,
            pressure=pressure,
        )
        return _unwrap(
            self._provider.evaluate_phase(
                PropertyRequest(
                    state=state,
                    phase="LIQUID",
                    properties=("lnK",),
                    derivatives=derivatives,
                ),
                self._context,
            ),
            self._block_id,
        )

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        result = self._request(inputs, ())
        return [result.values[f"lnK_{name}"] for name in self._components]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        result = self._request(inputs, ("T", "P"))
        triples: list[tuple[int, int, float]] = []
        for row, name in enumerate(self._components):
            entry = result.derivatives[f"lnK_{name}"]
            triples.append((row, 0, entry["T"]))
            triples.append((row, 1, entry["P"]))
        return triples


class EnthalpyFlowBlock:
    """`(n_i, T, P) -> (H_i)` with `H_i = n_i h_i^phase(T, P)`, one output per component, in W.

    Enthalpy *flow* rather than molar enthalpy, so an energy row is a plain sum of block outputs
    and does not multiply a symbol by a block output — that keeps the row's own Jacobian trivial
    and puts the chain rule where the declared sparsity can describe it.

    Sparsity is `3n` of `n(n + 2)`: `dH_i/dn_i` only (the package mixes ideally, so one
    component's enthalpy does not depend on another's flow), plus the two state columns.
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

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def input_ids(self) -> tuple[str, ...]:
        return (*(f"n_{name}" for name in self._components), "T", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return tuple(f"H_{name}" for name in self._components)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        count = len(self._components)
        pattern: list[tuple[int, int]] = []
        for row in range(count):
            pattern.append((row, row))
            pattern.append((row, count))
            pattern.append((row, count + 1))
        return tuple(pattern)

    def _split(self, inputs: Sequence[float]) -> tuple[StreamState, int]:
        count = len(self._components)
        flows = tuple(float(value) for value in inputs[:count])
        state = StreamState(
            n=flows, temperature=float(inputs[count]), pressure=float(inputs[count + 1])
        )
        return state, count

    def _request(self, state: StreamState, derivatives: tuple[str, ...]) -> PropertyResult:
        return _unwrap(
            self._provider.evaluate_phase(
                PropertyRequest(
                    state=state,
                    phase=self._phase,
                    properties=("h",),
                    derivatives=derivatives,
                ),
                self._context,
            ),
            self._block_id,
        )

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        state, _ = self._split(inputs)
        if state.is_dormant:
            # ADR 0001 D3.1: a dormant stream's enthalpy flow is exactly zero and no property is
            # evaluated for it. Returning zeros here is the rule, not a shortcut.
            return [0.0] * len(self._components)
        result = self._request(state, ())
        return [
            flow * result.values[f"h_{name}"]
            for name, flow in zip(self._components, state.n, strict=True)
        ]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        state, count = self._split(inputs)
        if state.is_dormant:
            # dH_i/dn_i = h_i still, even at zero flow: the row is linear in the flow. The state
            # columns vanish because every flow multiplying them is zero. Evaluating h at a
            # dormant state is what D3.1 forbids, so the flow derivative is reported from a probe
            # at the same (T, P) with unit flows -- h does not depend on composition here, and
            # the provider declares that in `PropertyCapabilities.properties`.
            probe = StreamState(
                n=(_PROBE_FLOW,) * count,
                temperature=state.temperature,
                pressure=state.pressure,
            )
            result = self._request(probe, ())
            triples: list[tuple[int, int, float]] = []
            for row, name in enumerate(self._components):
                triples.append((row, row, result.values[f"h_{name}"]))
                triples.append((row, count, 0.0))
                triples.append((row, count + 1, 0.0))
            return triples

        result = self._request(state, ("T", "P"))
        triples = []
        for row, (name, flow) in enumerate(zip(self._components, state.n, strict=True)):
            entry = result.derivatives[f"h_{name}"]
            triples.append((row, row, result.values[f"h_{name}"]))
            triples.append((row, count, flow * entry["T"]))
            triples.append((row, count + 1, flow * entry["P"]))
        return triples
