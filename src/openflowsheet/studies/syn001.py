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
from dataclasses import dataclass, replace
from typing import Any, Final

import numpy as np

from openflowsheet.compile.reference import state_vector
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import SpecificationError
from openflowsheet.models.syn001.flowsheet import FLASH_UNIT, HEATER_UNIT, Syn001Flowsheet
from openflowsheet.orchestrator.attempts import SolveResult
from openflowsheet.orchestrator.tear import Syn001TearProblem, solve_tear
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
from openflowsheet.verify.certificate import SolutionCertificate, verify

#: The `Syn001Flowsheet` field each separately settable pinned input lives in (spec §4.5). The feed
#: flows are `U-FEED.n_spec.<component>`, one entry of `feed_flows` each.
_PINNED_FIELDS: Final = {
    "U-SPLIT.split_fraction": "split_fraction",
    "U-FLASH.T_spec": "flash_temperature",
    "U-HEAT.T_spec": "heater_temperature",
    "U-FEED.T_spec": "feed_temperature",
}
#: Pinned inputs that `Syn001Flowsheet` holds in one shared field: both pressure specifications are
#: `pressure`, and the heater's pressure drop is fixed at zero. Moving one of them alone is not a
#: SYN-001 flowsheet, so they can be "set" only to the value they already have.
_SHARED_FIELDS: Final = {
    "U-FLASH.P_spec": "pressure",
    "U-FEED.P_spec": "pressure",
}


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


# -- pinned inputs and certified solves (spec §6, §7.3, §8.5 V1) ---------------------------------


def pinned_value(flowsheet: Syn001Flowsheet, parameter_id: str) -> float:
    """The current value of a SYN-001 pinned input, as the compiled problem bakes it in."""
    value = flowsheet.spec().parameters.get(parameter_id)
    if value is None:
        raise KeyError(f"{parameter_id!r} is not a pinned input of SYN-001")
    return float(value)


def with_pinned(flowsheet: Syn001Flowsheet, values: Mapping[str, float]) -> Syn001Flowsheet:
    """`flowsheet` with the given pinned inputs replaced (spec §4.5's `dataclasses.replace`).

    Raises `KeyError` for an id that is not a pinned input and `ValueError` for one SYN-001 cannot
    move alone (a pressure specification, or the heater's pressure drop) at a value other than the
    one it has: such a request is ill-formed, not a point that failed. A value the flowsheet's units
    refuse (outside a declared domain) is *not* checked here — the solve refuses it, by name.
    """
    fields: dict[str, Any] = {}
    flows = list(flowsheet.feed_flows)
    for parameter_id, value in values.items():
        if parameter_id in _PINNED_FIELDS:
            fields[_PINNED_FIELDS[parameter_id]] = float(value)
        elif parameter_id.startswith("U-FEED.n_spec."):
            component = parameter_id.removeprefix("U-FEED.n_spec.")
            if component not in flowsheet.components:
                raise KeyError(f"{parameter_id!r} is not a pinned input of SYN-001")
            flows[flowsheet.components.index(component)] = float(value)
        else:
            current = pinned_value(flowsheet, parameter_id)
            if float(value) != current:
                shared = _SHARED_FIELDS.get(parameter_id, "a fixed constant")
                raise ValueError(
                    f"{parameter_id!r} cannot be moved alone on SYN-001 (it is {shared}, shared "
                    f"or fixed); only its current value {current!r} is accepted"
                )
    if tuple(flows) != tuple(flowsheet.feed_flows):
        fields["feed_flows"] = tuple(flows)
    return replace(flowsheet, **fields)


@dataclass(frozen=True)
class CertifiedSolve:
    """A production tear solve from the registered initializer and, when it converged, its K04
    certificate. `outcome` is `CONVERGED` only when the solve converged **and** the certificate is
    `VERIFIED`; otherwise the solve's K03 outcome, `SPECIFICATION_REFUSED` (a unit refused the
    specification before any solve), or `CERTIFICATE_NOT_VERIFIED` (spec §6 item 3)."""

    outcome: str
    message: str
    result: SolveResult | None
    certificate: SolutionCertificate | None

    @property
    def verified(self) -> bool:
        return self.outcome == "CONVERGED"

    @property
    def final_state(self) -> Mapping[str, float] | None:
        return self.result.final_state if self.result is not None else None


def solve_certified(flowsheet: Syn001Flowsheet) -> CertifiedSolve:
    """Solve from the registered initializer, then certify (spec §6 items 1-3).

    A `SpecificationError` — a unit refusing its specification, such as a temperature outside the
    provider's declared domain — is a result (`SPECIFICATION_REFUSED`, its first message line),
    not an exception: the caller records it and moves on."""
    try:
        result, _ = solve_tear(flowsheet)
    except SpecificationError as error:
        return CertifiedSolve("SPECIFICATION_REFUSED", first_line(error), None, None)
    if result.outcome != "CONVERGED":
        return CertifiedSolve(result.outcome, first_line(result.message), result, None)
    certificate = verify(flowsheet, result)
    if certificate.verification_status != "VERIFIED":
        return CertifiedSolve(
            "CERTIFICATE_NOT_VERIFIED",
            f"certificate {certificate.verification_status}",
            result,
            certificate,
        )
    return CertifiedSolve("CONVERGED", first_line(result.message), result, certificate)


def output_values(
    state: Mapping[str, float], outputs: Sequence[OutputFunctional]
) -> tuple[float, ...]:
    """`y = C x` for each output functional, each a correctly rounded `math.fsum`."""
    return tuple(
        math.fsum(coefficient * state[name] for name, coefficient in output.coefficients.items())
        for output in outputs
    )


def first_line(message: object) -> str:
    """The first line of a message or an exception's text (spec §6 item 3)."""
    return (str(message).splitlines() or [""])[0]
