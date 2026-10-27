"""Volumetric-flow property blocks for sizing (E01 design §4.4.3).

`V̇` is the one sizing input the host's rows do not carry. Two blocks provide it, each with the
provider's own derivatives, declared sparse:

- `VolumetricFlowBlock` — a single-phase stream, `(n_1…n_C, T, P) -> V̇ = N·v^φ(T, P, n)` with
  `N = Σ n_c` (a left fold in component order), from `provider.evaluate_phase(…, ("v",))`.
  `∂V̇/∂n_c = v + N ∂v/∂n_c`, `∂V̇/∂T = N ∂v/∂T`, `∂V̇/∂P = N ∂v/∂P`. A pure fluid's `v` is intensive,
  so `∂v/∂n = 0` exactly and only `T`, `P` derivatives are requested (the thermal blocks' rule).
- `SaturatedVolumetricFlowBlock` — a saturated pure-fluid stream (S11, ADR 0051 D2), `(V, L, P) ->
  V̇ = V v^V_sat(P) + L v^L_sat(P)`, on the saturation routine of `models/thermal/kernel.py`
  (`saturation` for `T_sat(P)` and `dT_sat/dP`; `phase_properties` for `v` of each phase at
  `(T_sat, P)`), `dv_sat/dP = (∂v/∂T) dT_sat/dP + ∂v/∂P` along the line.

A provider that does not answer `v` for the phase is a refusal at planning time
(`SIZING_INPUT_UNAVAILABLE(<item>.v)` / `(<item>.v_sat)`, §4.4.3), checked by `volume_available`;
a refusal at an evaluation state is `DomainError`, which the program surfaces as
`TwinEvaluationError` (§4.2.3). A dormant stream has no block (its `V̇` is the constant 0.0).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from openflowsheet.compile.spec import DomainError
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.thermal.kernel import DOMAIN_CODES, Failure, phase_properties, saturation
from openflowsheet.thermo import Phase, PropertyProvider, PropertyRequest, StreamState

__all__ = [
    "VOLUME_OUTPUT",
    "SaturatedVolumetricFlowBlock",
    "VolumetricFlowBlock",
    "saturated_volume_available",
    "volume_available",
    "volumetric_block_id",
]

#: The one output of both blocks, m³/s.
VOLUME_OUTPUT: Final = "Vdot"


def volumetric_block_id(index: int) -> str:
    """`ASMVF_<k>`: the k-th volumetric block of a program, in construction order (§4.2.4).

    Stream and unit ids may contain characters a backend token refuses (`U-FLASH`), so the id is
    an ordinal, not a sanitised name that could map two streams onto one block."""
    if index < 1:
        raise ValueError(f"block ordinal {index!r} must be ≥ 1")
    return f"ASMVF_{index}"


def _raise(block_id: str, status: str, message: str) -> None:
    code = message.splitlines()[0] if message else status
    if code in DOMAIN_CODES or status == "out_of_domain":
        raise DomainError(f"{block_id}: {message}")
    raise DomainError(f"{block_id}: the provider returned {status}: {message}")


class VolumetricFlowBlock:
    """`(n_1…n_C, T, P) -> V̇ = N·v^φ(T, P, n)`, m³/s, for one phase of a single-phase stream."""

    def __init__(
        self,
        provider: PropertyProvider,
        context: EvaluationContext,
        phase: Phase,
        *,
        block_id: str,
    ) -> None:
        self._provider = provider
        self._context = context
        self._phase: Phase = phase
        self._block_id = block_id
        self._components = tuple(provider.describe().components)
        self._pure = len(self._components) == 1
        self._derivatives = (
            ("T", "P") if self._pure else ("T", "P", *(f"n_{c}" for c in self._components))
        )

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def input_ids(self) -> tuple[str, ...]:
        return (*(f"n_{c}" for c in self._components), "T", "P")

    @property
    def output_ids(self) -> tuple[str, ...]:
        return (VOLUME_OUTPUT,)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return tuple((0, j) for j in range(len(self._components) + 2))

    def molar_volume(self, inputs: Sequence[float]) -> tuple[float, dict[str, float]]:
        """`v` and the provider's derivatives `{T, P[, n_<c>]}` at the inputs (N > 0)."""
        count = len(self._components)
        flows = tuple(float(value) for value in inputs[:count])
        temperature, pressure = float(inputs[count]), float(inputs[count + 1])
        result = self._provider.evaluate_phase(
            PropertyRequest(
                state=StreamState(n=flows, temperature=temperature, pressure=pressure),
                phase=self._phase,
                properties=("v",),
                derivatives=self._derivatives,
            ),
            self._context,
        )
        if result.status != "ok":
            _raise(self._block_id, result.status, result.message)
        derivatives = result.derivatives.get("v", {})
        missing = [name for name in self._derivatives if name not in derivatives]
        if missing:
            raise DomainError(f"{self._block_id}: the provider gives no ∂v/∂{missing}")
        return float(result.values["v"]), {k: float(derivatives[k]) for k in self._derivatives}

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        total = sum(float(value) for value in inputs[: len(self._components)])
        if total == 0.0:
            raise DomainError(f"{self._block_id}: a dormant stream has no volumetric block")
        v, _ = self.molar_volume(inputs)
        return [total * v]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        count = len(self._components)
        total = sum(float(value) for value in inputs[:count])
        if total == 0.0:
            raise DomainError(f"{self._block_id}: a dormant stream has no volumetric block")
        v, d = self.molar_volume(inputs)
        entries = [
            (0, j, v if self._pure else v + total * d[f"n_{c}"])
            for j, c in enumerate(self._components)
        ]
        entries.append((0, count, total * d["T"]))
        entries.append((0, count + 1, total * d["P"]))
        return entries


class SaturatedVolumetricFlowBlock:
    """`(V, L, P) -> V̇ = V v^V_sat(P) + L v^L_sat(P)`, m³/s, for a saturated pure-fluid stream."""

    def __init__(
        self, provider: PropertyProvider, context: EvaluationContext, *, block_id: str
    ) -> None:
        components = tuple(provider.describe().components)
        if len(components) != 1:
            raise ValueError(f"a saturated stream is a pure fluid; the provider has {components}")
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
        return (VOLUME_OUTPUT,)

    def jacobian_pattern(self) -> tuple[tuple[int, int], ...]:
        return ((0, 0), (0, 1), (0, 2))

    def saturated_volumes(self, pressure: float) -> tuple[tuple[float, float], tuple[float, float]]:
        """`((v^V_sat, dv^V_sat/dP), (v^L_sat, dv^L_sat/dP))` at P, along the line."""
        sat = saturation(self._provider, pressure, self._context)
        if isinstance(sat, Failure):
            _raise(self._block_id, sat.status, sat.message)
            raise AssertionError  # pragma: no cover - _raise always raises
        out: list[tuple[float, float]] = []
        for phase in ("VAPOR", "LIQUID"):
            jets = phase_properties(
                self._provider, self._context, sat.temperature, pressure, phase, ("v",)
            )
            if isinstance(jets, Failure):
                _raise(self._block_id, jets.status, jets.message)
                raise AssertionError  # pragma: no cover
            v, d_t, d_p = jets["v"]
            out.append((v, d_t * sat.dtsat_dp + d_p))
        return out[0], out[1]

    def values(self, inputs: Sequence[float]) -> Sequence[float]:
        vapour, liquid, pressure = (float(value) for value in inputs)
        (v_v, _), (v_l, _) = self.saturated_volumes(pressure)
        return [vapour * v_v + liquid * v_l]

    def jacobian(self, inputs: Sequence[float]) -> Sequence[tuple[int, int, float]]:
        vapour, liquid, pressure = (float(value) for value in inputs)
        (v_v, dv_v), (v_l, dv_l) = self.saturated_volumes(pressure)
        return [(0, 0, v_v), (0, 1, v_l), (0, 2, vapour * dv_v + liquid * dv_l)]


def volume_available(
    provider: PropertyProvider,
    context: EvaluationContext,
    phase: Phase,
    flows: Sequence[float],
    temperature: float,
    pressure: float,
) -> str | None:
    """`None` when the provider answers `v` and its derivatives for `phase` at the state, else
    the reason (a planning-time refusal, §4.4.3)."""
    described = provider.describe()
    if "v" not in described.properties:
        return f"provider {described.provider_id!r} offers no molar volume"
    if phase not in described.phases:
        return f"provider {described.provider_id!r} has no {phase} phase"
    block = VolumetricFlowBlock(provider, context, phase, block_id="ASMVF_probe")
    try:
        block.molar_volume([*flows, temperature, pressure])
    except DomainError as error:
        return str(error)
    return None


def saturated_volume_available(
    provider: PropertyProvider, context: EvaluationContext, pressure: float
) -> str | None:
    """`None` when both saturated volumes and their derivatives are answered at P, else why."""
    described = provider.describe()
    if "v" not in described.properties:
        return f"provider {described.provider_id!r} offers no molar volume"
    try:
        SaturatedVolumetricFlowBlock(provider, context, block_id="ASMVF_probe").saturated_volumes(
            pressure
        )
    except (DomainError, ValueError, KeyError) as error:
        return str(error)
    return None
