"""The C1 reactor boundary: `nTP-v1` streams in and out of the group's per-tube reactor (spec §8).

ADR 0027 decides the contract; this module is its process side, shared by the synthetic stand-in
(`reactor_standin.py`, M01) and the out-of-process adapter to the pinned reactor (M02). The
reactor itself is an `ExternalEvaluation`: given one tube's inlet it returns that tube's raw outlet,
its outlet temperature and its Ergun pressure drop. Everything else happens here:

1. **Mapping and per-tube scaling** (§8.3). The unit is `N_tubes` identical tubes; one tube sees
   F_ret_in = n_tot/N_tubes at y_ret_in = n/n_tot, T_in, and an outlet pressure p_ret_out = P_in;
   its coolant is pure N2 at sweep_ratio × F_ret_in, T_in and 1 bar. The outlet is N_tubes times
   the tube's. The map is homogeneous of degree 1 in (n, N_tubes) jointly.
2. **The zero-pressure-drop convention** (§8.8, ADR 0027 D2). P_out = P_in, admissible iff
   |ΔP|/P_in ≤ ε_P = 1e-3; otherwise `pressure_drop_exceeds_convention`.
3. **The extent projection** (§8.9, D3). ξ = Σ_{H2,N2,NH3} ν_i (n_raw,i − n_in,i)/14 and
   n_out = n_in + ν ξ, so the outlet conserves every element exactly and the inerts keep their
   inlet flows bitwise; the defect n_raw − n_out is reported, and refused `element_balance_defect`
   when max |defect|/n_tot,in > 1e-6.
4. **The process-side duty** (§8.10, D4). Q = Ḣ_out − Ḣ_in, both from `pr-c1-v1` (vapour,
   `PR-C1-ref-v1`); nothing of the reactor's own thermodynamics crosses (§8.11).
5. **The envelope and the known invalid requests** (§8.12): a status, a reason code, and on `ok`
   every field of §8.12 — the reactor-specific diagnostics are `None` where the evaluation has
   none (the stand-in).

**The order of the request checks** is normative (§8.12, Amendments 1 and 2): the component set
first (a permuted order cannot even be read), then nTP-v1's state space (finite, non-negative
flows; finite, positive T and P; `out_of_domain`, review F3), then a dormant inlet (`ZERO_FLOW`,
before any composition is formed), then the inlet's phase by the provider's flash
(`liquid_at_reactor_inlet`; a refusal of the flash passes through), then the NH3 trace, then the
adapter's hard domain; then the evaluation
(`NotAccepted` → `reactor_not_accepted(<stage>)`); after it, the pressure convention, the element
defect and the two enthalpy flows (`stream_enthalpy_refused`). The inlet's phase must precede the
hard domain: no liquid exists inside it (its lowest T_in, 573.15 K, lies above NH3's T_c,EOS =
405.55 K; claim BD-06), so a liquid inlet always has a second defect, and in any other order
`liquid_at_reactor_inlet` could never be returned (F7's state, M01.A30 and A51). The kinetics' data
domain flags, never refuses (ADR 0027 D9).

**M02 adds two things and changes no M01 path** (design note §3.1, §5.1). The hard domain is a
`HardDomain` value that defaults to M01's constants; a variant may add a per-tube flow bound
(ADR 0034 D10, Q-F5), checked last inside the hard-domain check. And the evaluation may answer
`ExecutionFailure` — it did not run to an answer (a timeout, a crash, an environment failure) —
which the evaluation step maps to `error`, `external_<kind>` (ADR 0033 D10).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS, NU
from openflowsheet.thermo import (
    FlashRequest,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)

#: ε_P of the zero-pressure-drop convention (spec §8.8, ADR 0027 D2).
EPS_PRESSURE: Final = 1e-3
#: The element-defect refusal threshold, max |defect| / n_tot,in (spec §8.9, ADR 0027 D3).
DEFECT_LIMIT: Final = 1e-6
#: y_NH3,in below this is refused `nh3_below_trace` (spec §8.12; the group's TRACE_NH3).
NH3_TRACE: Final = 1e-9
#: The coolant channel's outlet pressure, Pa (the group's `case_setup.calculate_flows`).
PERMEATE_OUTLET_PRESSURE: Final = 1.0e5
#: Σ_{H2,N2,NH3} ν_i² = 9 + 1 + 4: the least-squares extent's denominator (spec §8.9).
_REACTIVE: Final[tuple[int, ...]] = (0, 1, 2)
_NU_SQUARED: Final = float(sum(NU[i] * NU[i] for i in _REACTIVE))

#: The adapter's hard domain (spec §8.12, ADR 0027 D9): outside it the request is `out_of_domain`.
HARD_TEMPERATURE_K: Final = (573.15, 773.15)
HARD_PRESSURE_PA: Final = (5.0e6, 1.5e7)
HARD_H2_N2: Final = (1.0, 4.0)
HARD_INERT_FRACTION: Final = 0.2
#: The kinetics' data domain (spec §8.12): inside the hard domain but outside it, `ok` and
#: `extrapolated` with the violated bounds.
DATA_TEMPERATURE_K: Final = (643.15, 733.15)
DATA_PRESSURE_PA: Final = (5.0e6, 1.0e7)
DATA_H2_N2: Final = (1.5, 3.0)


@dataclass(frozen=True)
class HardDomain:
    """The adapter's hard domain (spec §8.12, ADR 0027 D9); outside it a request is `out_of_domain`.

    The defaults are M01's constants. `tube_flow` bounds the per-tube flow F_ret_in = n_tot,in /
    N_tubes, mol/s (ADR 0034 D10, Q-F5): a variant field, `None` (unbounded) for the stand-in.
    """

    temperature_k: tuple[float, float] = HARD_TEMPERATURE_K
    pressure_pa: tuple[float, float] = HARD_PRESSURE_PA
    h2_n2: tuple[float, float] = HARD_H2_N2
    inert_fraction: float = HARD_INERT_FRACTION
    tube_flow: tuple[float, float] | None = None


#: M01's hard domain: no per-tube flow bound.
DEFAULT_HARD_DOMAIN: Final = HardDomain()

#: The grammar of `NotAccepted.stage` (spec §8.12, Amendment 1); the registered stages are S1, S2,
#: S3, certificate, backflow and nonpositive_flow, and M02 may register more (it registers
#: model_exception, R-251).
_STAGE: Final = re.compile(r"[A-Za-z0-9_]+")

ReactorStatus = Literal["ok", "unsupported", "out_of_domain", "not_converged", "error"]
DomainStatus = Literal["within_data_domain", "extrapolated"]

#: The fields every `ok` reactor result carries (spec §8.12), in `as_document` order.
ENVELOPE_FIELDS: Final[tuple[str, ...]] = (
    "status",
    "code",
    "message",
    "outlet",
    "xi",
    "Q",
    "defect",
    "defect_rel",
    "pressure_drop_relative",
    "Q_coolant",
    "inlet_face_heat_loss",
    "discretization_estimate",
    "domain_status",
    "extrapolated_bounds",
    "identity",
)
#: The identity's fields (spec §8.12); the stand-in's reactor-specific ones are `None`.
IDENTITY_FIELDS: Final[tuple[str, ...]] = (
    "model_id",
    "synthetic",
    "reactor_commit",
    "pymrm_version",
    "overlay_sha256",
    "configuration_sha256",
    "profile",
)


# -- 1. mapping and per-tube scaling (§8.3) -------------------------------------------------------


@dataclass(frozen=True)
class TubeInlet:
    """What one tube of the group's reactor is given (spec §8.3), SI units."""

    #: F_ret_in = n_tot,in / N_tubes, mol/s, and y_ret_in = n_in / n_tot,in in COMPONENTS order
    #: (the reactor's own species order is the same).
    flow: float
    composition: tuple[float, ...]
    temperature: float
    #: p_ret_out = P_in: the zero-pressure-drop convention runs the tube at the process pressure.
    outlet_pressure: float
    #: The coolant (the group's convention): pure N2 at sweep_ratio × F_ret_in, T_in, 1 bar.
    coolant_flow: float
    coolant_composition: tuple[float, ...]
    coolant_temperature: float
    coolant_outlet_pressure: float


def tube_inlet(inlet: StreamState, n_tubes: float, sweep_ratio: float = 1.0) -> TubeInlet:
    """One tube's inlet for a flowing process inlet (n_tot > 0) split over `n_tubes` tubes."""
    total = inlet.total_flow
    flow = total / n_tubes
    return TubeInlet(
        flow=flow,
        composition=tuple(value / total for value in inlet.n),
        temperature=inlet.temperature,
        outlet_pressure=inlet.pressure,
        coolant_flow=sweep_ratio * flow,
        coolant_composition=(0.0, 1.0, 0.0, 0.0, 0.0),
        coolant_temperature=inlet.temperature,
        coolant_outlet_pressure=PERMEATE_OUTLET_PRESSURE,
    )


@dataclass(frozen=True)
class TubeOutlet:
    """What one tube returns: the raw outlet before projection, and its diagnostics."""

    #: The retentate's axial face flows at z = L, mol/s per tube, COMPONENTS order.
    flows: tuple[float, ...]
    #: The last retentate cell's temperature, K.
    temperature: float
    #: The tube's Ergun pressure drop, Pa (inlet minus outlet pressure).
    pressure_drop: float
    #: The coolant's heat uptake and the inlet-face heat loss, W per tube (§8.10); `None` where the
    #: evaluation has none.
    coolant_heat: float | None = None
    inlet_face_heat_loss: float | None = None


@dataclass(frozen=True)
class NotAccepted:
    """The evaluation reached no state its acceptance admits (spec §8.7), at `stage`.

    `stage` matches `[A-Za-z0-9_]+` (§8.12, Amendment 1), so the code
    `reactor_not_accepted(<stage>)` it becomes is parseable; anything else is a `ValueError`.
    """

    stage: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage, str) or _STAGE.fullmatch(self.stage) is None:
            raise ValueError(f"NotAccepted.stage must match [A-Za-z0-9_]+, got {self.stage!r}")


#: Why an evaluation did not run to an answer (ADR 0033 D5, D10): the transient execution
#: statuses of design note §3.3 that reach the boundary (`cancelled` propagates as an interrupt).
EXECUTION_FAILURE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "timed_out",
        "crashed",
        "protocol_error",
        "spawn_failed",
        "environment_unavailable",
        "environment_mismatch",
        "environment_changed",
    }
)


@dataclass(frozen=True)
class ExecutionFailure:
    """The evaluation did not run to an answer (ADR 0033 D10): it timed out, crashed, broke the
    protocol, could not be spawned, or found its environment absent, mismatched or changed.

    A fact about the execution, not about the inlet: the boundary maps it to `error`,
    `external_<kind>`, with no outlet values, and the experiment runner never caches it. `kind` is
    one of `EXECUTION_FAILURE_KINDS`; anything else is a `ValueError`.
    """

    kind: str
    message: str

    def __post_init__(self) -> None:
        if self.kind not in EXECUTION_FAILURE_KINDS:
            raise ValueError(
                f"ExecutionFailure.kind must be one of {sorted(EXECUTION_FAILURE_KINDS)}, "
                f"got {self.kind!r}"
            )


class ExternalEvaluation(Protocol):
    """The reactor behind the boundary: one tube's inlet in, that tube's raw outlet out.

    A `NotAccepted` answer becomes `not_converged`, `reactor_not_accepted(<stage>)`, with no outlet
    values; an `ExecutionFailure` becomes `error`, `external_<kind>` (ADR 0033 D10). The stand-in
    is closed-form and never fails; M02's adapter runs the pinned reactor out of process.
    """

    def __call__(self, tube: TubeInlet) -> TubeOutlet | NotAccepted | ExecutionFailure: ...


# -- 3. the extent projection (§8.9) -------------------------------------------------------------


@dataclass(frozen=True)
class Projection:
    xi: float
    outlet: tuple[float, ...]
    defect: tuple[float, ...]
    defect_rel: float


def project(n_in: Sequence[float], n_raw: Sequence[float]) -> Projection:
    """The least-squares extent and the element-conserving outlet (spec §8.9, ADR 0027 D3).

    ξ = Σ_{i∈{H2,N2,NH3}} ν_i (n_raw,i − n_in,i) / Σ ν_i²; n_out = n_in + ν ξ (the inerts' ν is 0,
    so their outlet is their inlet bitwise); defect = n_raw − n_out; defect_rel = max |defect_i| /
    n_tot,in. `n_in` must be flowing.
    """
    xi = sum(NU[i] * (n_raw[i] - n_in[i]) for i in _REACTIVE) / _NU_SQUARED
    outlet = tuple(n_in[i] + NU[i] * xi for i in range(len(COMPONENTS)))
    defect = tuple(n_raw[i] - outlet[i] for i in range(len(COMPONENTS)))
    return Projection(
        xi=xi,
        outlet=outlet,
        defect=defect,
        defect_rel=max(abs(value) for value in defect) / sum(n_in),
    )


# -- the result envelope (§8.12) ------------------------------------------------------------------


@dataclass(frozen=True)
class ReactorResult:
    """A reactor answer: `status`, a reason `code`, and on `ok` every field of spec §8.12.

    A refusal carries no outlet values: `outlet`, `xi`, `Q` and every diagnostic are `None`.
    """

    status: ReactorStatus
    code: str
    message: str = ""
    outlet: StreamState | None = None
    xi: float | None = None
    #: W, positive into the unit (ADR 0001 D4.1): Ḣ_out − Ḣ_in by `pr-c1-v1`.
    Q: float | None = None  # noqa: N815 - the duty's registered symbol
    defect: tuple[float, ...] | None = None
    defect_rel: float | None = None
    #: |ΔP| / P_in of the tube's Ergun drop: the convention's inconsistency (§8.8).
    pressure_drop_relative: float | None = None
    Q_coolant: float | None = None  # noqa: N815 - the registered symbol
    inlet_face_heat_loss: float | None = None
    #: The registered discretization estimate of the configured grid (spec §10), as a mapping.
    discretization_estimate: Mapping[str, Any] | None = None
    domain_status: DomainStatus | None = None
    extrapolated_bounds: tuple[str, ...] | None = None
    identity: Mapping[str, Any] = field(default_factory=dict)

    def as_document(self) -> dict[str, Any]:
        outlet = None
        if self.outlet is not None:
            outlet = {
                "n": list(self.outlet.n),
                "T": self.outlet.temperature,
                "P": self.outlet.pressure,
            }
        document: dict[str, Any] = {name: getattr(self, name) for name in ENVELOPE_FIELDS}
        document["outlet"] = outlet
        for name in ("defect", "extrapolated_bounds"):
            if document[name] is not None:
                document[name] = list(document[name])
        document["identity"] = dict(self.identity)
        return document


def refused(status: ReactorStatus, code: str, message: str) -> ReactorResult:
    """A typed refusal (spec §8.12): status, code and message, no outlet values."""
    return ReactorResult(status=status, code=code, message=f"{code}: {message}")


# -- the checks (§8.12) ---------------------------------------------------------------------------


def _within(value: float, bounds: tuple[float, float]) -> bool:
    return bounds[0] <= value <= bounds[1]


def _h2_n2_within(n: Sequence[float], bounds: tuple[float, float]) -> bool:
    """H2/N2 in `bounds`, division-free; no N2 is outside every ratio bound."""
    return n[1] > 0.0 and bounds[0] * n[1] <= n[0] <= bounds[1] * n[1]


def state_space_violation(inlet: StreamState) -> str | None:
    """Why the inlet lies outside nTP-v1's state space (ADR 0001 D2), or `None`.

    Every flow finite and non-negative (−0.0 is zero), T and P finite and positive. Checked before
    the dormant test (spec §8.12 step 2, Amendment 2, review F3): a dormant inlet's T and P are free
    labels, but only within the state space, and a sum of zero is not a dormant inlet when a flow
    is negative.
    """
    bad = [c for c, value in zip(COMPONENTS, inlet.n, strict=True) if not 0.0 <= value < math.inf]
    if bad:
        return f"component flows {bad} are not finite and non-negative (ADR 0001 D2)"
    t, p = inlet.temperature, inlet.pressure
    if not (0.0 < t < math.inf and 0.0 < p < math.inf):
        return f"T = {t!r} K, P = {p!r} Pa: not finite and positive (ADR 0001 D2)"
    return None


def hard_domain_violations(
    inlet: StreamState,
    domain: HardDomain = DEFAULT_HARD_DOMAIN,
    n_tubes: float | None = None,
) -> list[str]:
    """The hard-domain bounds a flowing inlet violates (spec §8.12, ADR 0027 D9).

    With a per-tube flow bound (ADR 0034 D10) `n_tubes` is required, and F_ret_in is formed as
    `tube_inlet` forms it; that bound is checked last, so M01's messages are unchanged.
    """
    n = inlet.n
    violated = []
    if not _within(inlet.temperature, domain.temperature_k):
        violated.append(f"T_in {inlet.temperature!r} K outside {list(domain.temperature_k)}")
    if not _within(inlet.pressure, domain.pressure_pa):
        violated.append(f"P_in {inlet.pressure!r} Pa outside {list(domain.pressure_pa)}")
    if not _h2_n2_within(n, domain.h2_n2):
        violated.append(f"H2/N2 outside {list(domain.h2_n2)}")
    if not (n[3] + n[4]) <= domain.inert_fraction * inlet.total_flow:
        violated.append(f"inert fraction above {domain.inert_fraction}")
    if domain.tube_flow is not None:
        if n_tubes is None:
            raise ValueError("a per-tube flow bound needs n_tubes")
        flow = inlet.total_flow / n_tubes
        if not _within(flow, domain.tube_flow):
            violated.append(f"F_ret_in {flow!r} mol/s outside {list(domain.tube_flow)}")
    return violated


def data_domain_violations(inlet: StreamState) -> tuple[str, ...]:
    """The kinetics' data-domain bounds violated, by name (`T_in`, `P_in`, `H2/N2`).

    A dormant inlet's T and P are labels (ADR 0001 D3.1) and are flagged as such; it has no H2/N2.
    """
    violated = []
    if not _within(inlet.temperature, DATA_TEMPERATURE_K):
        violated.append("T_in")
    if not _within(inlet.pressure, DATA_PRESSURE_PA):
        violated.append("P_in")
    if not inlet.is_dormant and not _h2_n2_within(inlet.n, DATA_H2_N2):
        violated.append("H2/N2")
    return tuple(violated)


def enthalpy_flow(
    provider: PropertyProvider, state: StreamState, context: EvaluationContext
) -> tuple[float | None, str]:
    """Ḣ = n_tot h of a vapour stream by the provider (§4.5); exactly 0.0 when dormant."""
    if state.is_dormant:
        return 0.0, ""
    result = provider.evaluate_phase(
        PropertyRequest(state=state, phase="VAPOR", properties=("h",)), context
    )
    if result.status != "ok":
        return None, result.message
    return state.total_flow * result.values["h"], ""


@dataclass(frozen=True)
class Boundary:
    """The process side of one C1 reactor configuration (spec §8.2-§8.12).

    `identity` is the result identity of §8.12 (reactor commit, pymrm version, overlay SHA-256,
    configuration hash, profile, and whether the evaluation is synthetic); `discretization_estimate`
    the registered estimate for the configured grid, `None` where there is none.
    """

    provider: PropertyProvider
    n_tubes: float
    identity: Mapping[str, Any]
    sweep_ratio: float = 1.0
    discretization_estimate: Mapping[str, Any] | None = None
    #: M01's constants unless a variant says otherwise (ADR 0034 D10).
    hard_domain: HardDomain = DEFAULT_HARD_DOMAIN

    def __post_init__(self) -> None:
        # M01 review (passed to M02): the per-tube scaling divides by `n_tubes` (§8.3), so a
        # zero, negative or non-finite count is a configuration defect, refused at construction
        # rather than surfacing as a NaN or a sign flip inside an evaluation.
        if not 0.0 < self.n_tubes < math.inf:
            raise ValueError(f"n_tubes {self.n_tubes!r} is not finite and positive")

    def evaluate(
        self,
        inlet: StreamState,
        components: Sequence[str],
        evaluation: ExternalEvaluation,
        context: EvaluationContext,
    ) -> ReactorResult:
        """The reactor's answer for one process inlet, every path of spec §8.12."""
        if tuple(components) != COMPONENTS or len(inlet.n) != len(COMPONENTS):
            return refused(
                "unsupported",
                "component_set_mismatch",
                f"the inlet declares {list(components)}; the C1 reactor takes {list(COMPONENTS)}",
            )
        outside = state_space_violation(inlet)
        if outside is not None:
            return refused("out_of_domain", "out_of_domain", outside)
        if inlet.is_dormant:
            # §8.12: outlet +0.0, Q = +0.0, T_out = T_in, P_out = P_in, ξ = 0 (ADR 0001 D3).
            return self._ok(
                code="ZERO_FLOW",
                outlet=StreamState(
                    n=(0.0,) * len(COMPONENTS),
                    temperature=inlet.temperature,
                    pressure=inlet.pressure,
                ),
                xi=0.0,
                duty=0.0,
                defect=(0.0,) * len(COMPONENTS),
                defect_rel=0.0,
                pressure_drop_relative=0.0,
                tube=None,
                inlet=inlet,
            )
        flashed = self.provider.flash(FlashRequest(state=inlet), context)
        if flashed.status != "ok":
            return ReactorResult(
                status=flashed.status,
                code=flashed.message.split(":", 1)[0],
                message=flashed.message,
            )
        if flashed.phase_signature != "VAPOR":
            return refused(
                "unsupported",
                "liquid_at_reactor_inlet",
                f"the inlet flashes {flashed.phase_signature} by the provider's TP flash",
            )
        if not inlet.n[2] >= NH3_TRACE * inlet.total_flow:
            return refused(
                "unsupported",
                "nh3_below_trace",
                f"y_NH3,in below {NH3_TRACE}: the rate carries a negative power of a_NH3",
            )
        violated = hard_domain_violations(inlet, self.hard_domain, self.n_tubes)
        if violated:
            return refused("out_of_domain", "out_of_domain", "; ".join(violated))

        tube = evaluation(tube_inlet(inlet, self.n_tubes, self.sweep_ratio))
        if isinstance(tube, ExecutionFailure):
            return refused("error", f"external_{tube.kind}", tube.message)
        if isinstance(tube, NotAccepted):
            return refused(
                "not_converged",
                f"reactor_not_accepted({tube.stage})",
                "the evaluation reached no accepted state (spec §8.7)",
            )
        drop = abs(tube.pressure_drop) / inlet.pressure
        if drop > EPS_PRESSURE:
            return refused(
                "unsupported",
                "pressure_drop_exceeds_convention",
                f"|dP|/P_in = {drop!r} above eps_P = {EPS_PRESSURE}",
            )
        raw = tuple(self.n_tubes * value for value in tube.flows)
        projection = project(inlet.n, raw)
        if projection.defect_rel > DEFECT_LIMIT:
            return refused(
                "not_converged",
                "element_balance_defect",
                f"defect_rel = {projection.defect_rel!r} above {DEFECT_LIMIT}",
            )
        outlet = StreamState(
            n=projection.outlet, temperature=tube.temperature, pressure=inlet.pressure
        )
        h_in, why_in = enthalpy_flow(self.provider, inlet, context)
        h_out, why_out = enthalpy_flow(self.provider, outlet, context)
        if h_in is None or h_out is None:
            return refused(
                "error", "stream_enthalpy_refused", f"the provider refused: {why_in or why_out}"
            )
        return self._ok(
            code="ok",
            outlet=outlet,
            xi=projection.xi,
            duty=h_out - h_in,
            defect=projection.defect,
            defect_rel=projection.defect_rel,
            pressure_drop_relative=drop,
            tube=tube,
            inlet=inlet,
        )

    def _ok(
        self,
        *,
        code: str,
        outlet: StreamState,
        xi: float,
        duty: float,
        defect: tuple[float, ...],
        defect_rel: float,
        pressure_drop_relative: float,
        tube: TubeOutlet | None,
        inlet: StreamState,
    ) -> ReactorResult:
        def scaled(value: float | None) -> float | None:
            return None if value is None else self.n_tubes * value

        violated = data_domain_violations(inlet)
        return ReactorResult(
            status="ok",
            code=code,
            outlet=outlet,
            xi=xi,
            Q=duty,
            defect=defect,
            defect_rel=defect_rel,
            pressure_drop_relative=pressure_drop_relative,
            Q_coolant=None if tube is None else scaled(tube.coolant_heat),
            inlet_face_heat_loss=None if tube is None else scaled(tube.inlet_face_heat_loss),
            discretization_estimate=self.discretization_estimate,
            domain_status="extrapolated" if violated else "within_data_domain",
            extrapolated_bounds=violated,
            identity=dict(self.identity),
        )


def require_positive(value: float, name: str) -> None:
    """A configuration number that must be a positive finite real (N_tubes, the sweep ratio)."""
    if not (math.isfinite(value) and value > 0.0):
        raise ValueError(f"{name} = {value!r} must be a positive finite real (spec §8.2)")
