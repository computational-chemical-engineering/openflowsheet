"""The SYN-001 binding of the sensitivity core: margins, the certificate, the host (M03 spec §3.4,
§3.5 Q1′, §4; ADR 0031 D3).

The core (`studies/sensitivity.py`) knows a compiled problem, its scales and its eliminated rows. A
SYN-001 study adds two things the core cannot know: that the root was certified by K04 for the same
state (Q1′ — a converged solve is not yet a verified one), and where the tear path's two lifted
**TP-type** phase splits sit relative to their phase boundaries (Q4): the heater outlet `U-HEAT`
(stream S3, fed by S2) and the flash `U-FLASH` (streams S4/S5, fed by S3).

**The margin** (spec §3.4). With `z_i = n_i / Σn` over the inlet's components with `n_i > 0` and
`K_i = exp(ln K_i(T, P))` from the flowsheet's own property provider at the split's specified
temperature and pressure, `s₁ = Σ z_i K_i − 1` and `s₂ = Σ z_i / K_i − 1`: `LIQUID` when `s₁ ≤ 0`
(margin `−s₁`), `VAPOR` when `s₂ ≤ 0` (margin `−s₂`), `TWO_PHASE` otherwise (`min(s₁, s₂)`), and
`ZERO_FLOW` with margin 0 when the inlet carries nothing. The margin is continuous across each
boundary, so a request within `τ_regime = 1e-4` of one is refused `PHASE_BOUNDARY` while the
Jacobian is still regular — the refusal names the boundary rather than a conditioning accident.

SYN-001's heater has no pressure drop (`U-HEAT.pressure_drop` is pinned at 0 and the flowsheet has
no field for it), so both splits are at the flowsheet's specified pressure.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from openflowsheet.compile.reference import state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.syn001.flowsheet import FLASH_UNIT, HEATER_UNIT, Syn001Flowsheet
from openflowsheet.orchestrator.tear import Syn001TearProblem
from openflowsheet.studies.sensitivity import (
    CertificateEvidence,
    Mode,
    OutputFunctional,
    Regime,
    SensitivityHost,
    SensitivityRequest,
    SensitivityResult,
    SplitRegime,
    StudyParameter,
    evaluate_sensitivity,
)
from openflowsheet.thermo import PropertyProvider, PropertyRequest, StreamState
from openflowsheet.verify.certificate import verify


def host_of(tear: Syn001TearProblem) -> SensitivityHost:
    """The tear problem's compiled 49 x 47 system, its K03 scales and its two alias rows."""
    return SensitivityHost(
        spec=tear.spec,
        compiled=tear.compiled,
        scaling=tear.scaling,
        eliminated_rows=tuple(row.row_id for row in tear.partition.elimination.eliminated),
    )


def tp_margin(
    provider: PropertyProvider,
    flows: Sequence[float],
    temperature: float,
    pressure: float,
    context: EvaluationContext,
    components: Sequence[str],
) -> tuple[Regime, float]:
    """Spec §3.4's regime and margin of a TP split of `flows` at `(temperature, pressure)`."""
    total = math.fsum(flows)
    if total == 0.0:
        return "ZERO_FLOW", 0.0
    result = provider.evaluate_phase(
        PropertyRequest(
            state=StreamState(n=tuple(flows), temperature=temperature, pressure=pressure),
            phase="LIQUID",
            properties=("lnK",),
        ),
        context,
    )
    if result.status != "ok":
        # At a converged root the provider evaluated exactly this state; failing now is a defect.
        raise ValueError(
            f"lnK at ({temperature!r} K, {pressure!r} Pa) returned {result.status}: "
            f"{result.message}"
        )
    present = [index for index, value in enumerate(flows) if value > 0.0]
    k_values = [math.exp(result.values[f"lnK_{components[index]}"]) for index in present]
    z = [flows[index] / total for index in present]
    s1 = sum(zi * ki for zi, ki in zip(z, k_values, strict=True)) - 1.0
    s2 = sum(zi / ki for zi, ki in zip(z, k_values, strict=True)) - 1.0
    if s1 <= 0.0:
        return "LIQUID", -s1
    if s2 <= 0.0:
        return "VAPOR", -s2
    return "TWO_PHASE", min(s1, s2)


def split_regimes(
    flowsheet: Syn001Flowsheet, state: Mapping[str, float]
) -> tuple[SplitRegime, ...]:
    """The tear path's two TP-type lifted splits at `state`, with their regimes and margins."""
    components = flowsheet.components
    splits = []
    for unit_id, streams, inlet, temperature in (
        (HEATER_UNIT, "S3", "S2", flowsheet.heater_temperature),
        (FLASH_UNIT, "S4/S5", "S3", flowsheet.flash_temperature),
    ):
        flows = [state[f"{inlet}.n.{component}"] for component in components]
        regime, margin = tp_margin(
            flowsheet.provider,
            flows,
            temperature,
            flowsheet.pressure,
            flowsheet.context,
            components,
        )
        splits.append(SplitRegime(unit_id, streams, "TP", regime, margin))
    return tuple(splits)


def syn001_sensitivity(
    flowsheet: Syn001Flowsheet,
    result: Any,
    *,
    parameters: Sequence[StudyParameter],
    outputs: Sequence[OutputFunctional],
    mode: Mode = "both",
    certificate: Any = None,
    state: Mapping[str, float] | None = None,
) -> SensitivityResult:
    """A sensitivity at a converged SYN-001 tear solve, under `M03-sensitivity-v1`.

    `certificate` is the K04 `SolutionCertificate` of `result`; when omitted it is issued here by
    `verify` (Q1′ is a requirement of the study level, never skipped). `state` overrides the
    solve's final state, as `verify`'s own `state=` does, for injected states. No path here
    re-solves the flowsheet: the solve and its certificate are inputs.
    """
    final_state = state if state is not None else result.final_state
    if final_state is None:
        raise ValueError("the solve carries no final state to take a sensitivity at")
    if certificate is None:
        certificate = verify(flowsheet, result, state=state)
    tear = Syn001TearProblem(flowsheet)
    request = SensitivityRequest(
        context=tear.context,
        parameters=tuple(parameters),
        outputs=tuple(outputs),
        mode=mode,
    )
    return evaluate_sensitivity(
        host_of(tear),
        np.array(state_vector(tear.spec, final_state)),
        request,
        certificate=CertificateEvidence.of(certificate),
        splits=split_regimes(flowsheet, final_state),
    )
