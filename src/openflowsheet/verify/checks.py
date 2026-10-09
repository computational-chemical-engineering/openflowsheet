"""The check set, §4.1–§4.7. Each check says in its docstring what it does *not* share.

Blueprint §8.1 asks for "independent balance evaluators", and [A09] says what independence
cannot mean when the energy check uses the same property package: it is bookkeeping, not
thermodynamic validation, and the shared provider hashes go on the result.

The strongest checks here are the cheapest. §4.3 is plain summation over stream flows with no
compiled problem and no provider in it at all; §4.4 re-flashes every stream from its own
`(n, T, P)` instead of believing the lifted split. Between them they catch the trivial root
that satisfies all 49 assembled rows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

import numpy as np

from openflowsheet.compile.reference import state_vector
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models import duty_id, flow_id, pressure_id, temperature_id
from openflowsheet.models.syn001 import (
    ENERGY_TOLERANCE,
    FLOW_TOLERANCE,
    TEMPERATURE_TOLERANCE,
)
from openflowsheet.models.syn001.flash import total_flow_id
from openflowsheet.models.syn001.flowsheet import (
    FLASH_UNIT,
    HEATER_UNIT,
    STREAMS,
    Syn001Flowsheet,
)
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.thermo import FlashRequest, PropertyProvider, StreamState
from openflowsheet.verify import (
    NEAR_THRESHOLD_MARGIN,
    CheckResult,
    dormant,
    evaluated,
    unsupported,
)

if TYPE_CHECKING:
    from openflowsheet.verify.zero_flow import ZeroFlowSplit

#: §5.1, from ADR 0001 D6. Pressure and the lifted equilibrium row are the two the K03 work
#: left implicit; §5.2 derives the equilibrium row's from the flow rule at the flow scale.
PRESSURE_TOLERANCE: Final = 1e-2
#: §5.2: `a = 1e-9 x 3`, `r s = 1e-8 x 9`. Dividing the row by the flow scale gives a flow.
EQUILIBRIUM_TOLERANCE: Final = 1e-9 * 3.0 + 1e-8 * 9.0
#: §4.7, as K03 §8.2 argues it.
ADMISSIBILITY_EPSILON: Final = 1e-12

#: §5.1's mapping from a declared quantity kind to its registered tolerance.
KIND_TOLERANCE: Final[Mapping[str, float]] = {
    "molar_flow": FLOW_TOLERANCE,
    "molar_flow_squared": EQUILIBRIUM_TOLERANCE,
    "heat_rate": ENERGY_TOLERANCE,
    "temperature": TEMPERATURE_TOLERANCE,
    "pressure": PRESSURE_TOLERANCE,
}

#: §5.1's `s_i`, the registered reference. Read from the registry, never from an iterate.
KIND_REFERENCE: Final[Mapping[str, float]] = {
    "molar_flow": 3.0,
    "molar_flow_squared": 9.0,
    "heat_rate": 1e5,
    "temperature": 100.0,
    "pressure": 1e5,
}

COMPONENTS: Final = ("A", "B", "C")


def routing_tolerances(tolerances: Mapping[str, float] | None) -> dict[str, float]:
    """ADR 0013 Amendment 2: the tolerance a *routing* decision reads, per kind,
    ρ_k = max(τ_k(policy), τ_k(registered)); a kind the policy omits takes its registered value,
    and `None` is the registered table.

    A route selects which checks exist, or at which state they are judged (the projection's
    guards 1 and 5, D3's unresolved-split test); the policy's own τ is only ever the right-hand
    side of a check's `|value| ≤ τ`. So a policy that only tightens is routed as the registered
    one — it can turn a pass into a fail, never remove a check — and a loosened one as itself.
    At the registered policy each ρ_k is the registered float itself."""
    supplied = tolerances or {}
    return {
        kind: max(supplied.get(kind, registered), registered)
        for kind, registered in KIND_TOLERANCE.items()
    }


class VerifierError(RuntimeError):
    """The verifier could not run a check for a reason that is not a verdict."""


def qualification(provider: PropertyProvider) -> str:
    """[A09]: the shared provider, named, on every check that depends on it.

    "Shares the provider" means the correlations and the reference data are common with the
    solver, so the check is process bookkeeping and not thermodynamic validation. Recording the
    hashes is what stops the certificate from reading as the second thing.
    """
    capabilities = provider.describe()
    return (
        f"shares the property provider with the solver: provider_id={capabilities.provider_id}, "
        f"implementation_sha256={capabilities.implementation_sha256}, "
        f"data_sha256={capabilities.data_sha256}, "
        f"reference_convention={capabilities.reference_convention}; this is a consistency "
        "check of process bookkeeping, not a validation of the enthalpy correlations"
    )


def stream_of(
    state: Mapping[str, float], stream: str, components: Sequence[str] = COMPONENTS
) -> StreamState:
    """`stream`'s `(n, T, P)` read from `state`, its flows in `components` order — SYN-001's by
    default, a revision's view's on the revision path (M02 design note §14.2 B15 item 1)."""
    return StreamState(
        n=tuple(state[flow_id(stream, component)] for component in components),
        temperature=state[temperature_id(stream)],
        pressure=state[pressure_id(stream)],
    )


# ---------------------------------------------------------------------- 4.1 the original rows


def residual_checks(
    compiled: CompiledProblem,
    spec: ProblemSpec,
    state: Mapping[str, float],
    context: EvaluationContext,
    kinds: Mapping[str, str],
    tolerances: Mapping[str, float],
) -> tuple[list[CheckResult], str]:
    """§4.1: all 49 rows at `x_final`, fresh context, fresh provider, no cache.

    Independent of the solver and of nothing else — it *is* K01's compiled function, evaluated
    at a state the solver produced. That is why it is the weakest check in the set and why §4.3
    and §4.4 exist: the trivial root satisfies every row here.
    """
    result = compiled.residual(np.array(state_vector(spec, state)), context)
    if result.status != "ok" or result.values is None:
        raise VerifierError(f"the residual at the final state returned {result.status}")

    checks: list[CheckResult] = []
    for row_id, value in zip(result.equation_ids, result.values, strict=True):
        kind = kinds.get(row_id)
        if kind is None:
            raise VerifierError(f"row {row_id!r} declares no quantity kind; it cannot be judged")
        checks.append(
            evaluated(
                id=f"residual.{row_id}",
                category="residual",
                subject=row_id,
                value=float(value),
                tolerance=tolerances.get(kind, KIND_TOLERANCE[kind]),
                reference=KIND_REFERENCE[kind],
            )
        )
    return checks, result.state_sha256


# ------------------------------------------------------------------- 4.2 the alias certificates


def alias_checks(
    eliminated: Sequence[object],
    row_values: Mapping[str, float],
    unsupported_reason: str = "",
) -> list[CheckResult]:
    """§4.2: the eliminated rows are *satisfied*, and their certificates still hold.

    Two claims, not one. K03 §7.3's rule is that an eliminated row is not a discarded row, so
    the row's own value must vanish; and the certificate that justified removing it — the
    signed combination of retained rows plus a constant — must still be an identity here.

    With `unsupported_reason` (T06 spec §8.2; ADR 0014 D5) the certificates could not be
    witnessed — the second state K03 §7.2 needs could not be built inside the provider's domain,
    or not evaluated — and both claims of every eliminated row are `unsupported` with that
    reason: the elimination is then the procedure's structural answer only, never a pass.
    """
    checks: list[CheckResult] = []
    for row in eliminated:
        row_id: str = row.row_id  # type: ignore[attr-defined]
        if unsupported_reason:
            checks += [
                unsupported(
                    id=f"alias_certificate.{claim}.{row_id}",
                    category="alias_certificate",
                    subject=row_id,
                    reason=unsupported_reason,
                )
                for claim in ("identity", "satisfied")
            ]
            continue
        mismatch: float = row.constant_mismatch  # type: ignore[attr-defined]
        combination = sum(
            sign * row_values[name]
            for name, sign in row.equals  # type: ignore[attr-defined]
        )
        checks.append(
            evaluated(
                id=f"alias_certificate.identity.{row_id}",
                category="alias_certificate",
                subject=row_id,
                value=row_values[row_id] - combination - mismatch,
                tolerance=PRESSURE_TOLERANCE,
                reference=KIND_REFERENCE["pressure"],
            )
        )
        checks.append(
            evaluated(
                id=f"alias_certificate.satisfied.{row_id}",
                category="alias_certificate",
                subject=row_id,
                value=row_values[row_id] - mismatch,
                tolerance=PRESSURE_TOLERANCE,
                reference=KIND_REFERENCE["pressure"],
            )
        )
    return checks


# ------------------------------------------------------------------- 4.3 the material balances


def material_checks(
    state: Mapping[str, float],
    split_fraction: float,
    tolerances: Mapping[str, float] | None = None,
) -> list[CheckResult]:
    """§4.3: plain sums over the stream flows. No compiled problem, no provider, no unit model.

    This is what blueprint §8.1 means by "independent balance evaluators". The compiled
    `MIX-mole` rows compute the same sums, but through K01's expression graph and K02's row
    builders; a permuted component index, a dropped stream or a sign error in either shows here
    and not there. The **envelope** row — fresh feed equals vapour product plus purge — is not a
    compiled row at all, so nothing but this check ever evaluates it.
    """

    limit = (tolerances or KIND_TOLERANCE)["molar_flow"]

    def n(stream: str, component: str) -> float:
        return state[flow_id(stream, component)]

    checks: list[CheckResult] = []

    def record(name: str, subject: str, value: float) -> None:
        checks.append(
            evaluated(
                id=f"material_balance.{name}",
                category="material_balance",
                subject=subject,
                value=value,
                tolerance=limit,
                reference=KIND_REFERENCE["molar_flow"],
            )
        )

    for component in COMPONENTS:
        record(
            f"mixer.{component}",
            "U-MIX",
            n("S1", component) + n("S6", component) - n("S2", component),
        )
        record(f"heater.{component}", HEATER_UNIT, n("S2", component) - n("S3", component))
        record(
            f"flash.{component}",
            FLASH_UNIT,
            n("S3", component) - n("S4", component) - n("S5", component),
        )
        record(
            f"splitter.{component}",
            "U-SPLIT",
            n("S5", component) - n("S6", component) - n("S7", component),
        )
        record(
            f"ratio.{component}",
            "U-SPLIT",
            n("S6", component) - split_fraction * n("S5", component),
        )
        record(
            f"envelope.{component}",
            "flowsheet",
            n("S1", component) - n("S4", component) - n("S7", component),
        )
        record(
            f"lifted_split.{component}",
            "S3",
            n("S3", component)
            - state[vapor_flow_id("S3", component)]
            - state[liquid_flow_id("S3", component)],
        )

    record(
        "total.S3.V",
        "S3",
        state[vapor_total_id("S3")] - sum(state[vapor_flow_id("S3", c)] for c in COMPONENTS),
    )
    record(
        "total.S3.L",
        "S3",
        state[liquid_total_id("S3")] - sum(state[liquid_flow_id("S3", c)] for c in COMPONENTS),
    )
    for stream in ("S4", "S5"):
        record(
            f"total.{stream}.N",
            stream,
            state[total_flow_id(stream)] - sum(n(stream, c) for c in COMPONENTS),
        )
    return checks


# --------------------------------------------------------------------- 4.4 the energy balances


def enthalpy_flow(
    provider: PropertyProvider, stream: StreamState, context: EvaluationContext
) -> float:
    """`Ḣ` from a **fresh flash of the stream's own `(n, T, P)`** — never from a lifted split.

    This is the whole point of §4.4. At the trivial-root state the compiled `HEAT-duty` and
    `FLASH-duty` rows are exactly satisfied with both duties wrong by 8237.85 W, because those
    rows read the split that is in `x`. A flash of S3 at its own state returns the real one.

    A dormant stream is exactly zero and is not flashed (ADR 0001 D3.1): zero flow carries zero
    enthalpy whatever the labels on its `T` and `P` say.

    **The phase decision at K03 §8.2's `ε_adm`** (ADR 0013 D2; K04-F9 spec §5.2). A stream the
    provider's flash splits is read as a liquid when §4.7's bubble test admits it as one
    (`Σ x_i K_i ≤ 1 + ε_adm`), else as a vapour when the dew test does (`Σ y_i / K_i ≤ 1 + ε_adm`):
    the verifier's own enthalpy says what its admissibility check says. A saturated product
    within `ε_adm` of its boundary — every product and copy of one at the verifier's projection —
    then has no kink, while a stream past it (INJ-F10's liquid, 0.384 past its bubble point) is
    still flashed and the energy checks see the split. Where the provider reads the stream
    single-phase the value is unchanged, bit for bit; the phase enthalpy is the same
    `evaluate_phase` call and the same sum. The independent split's flash of a split's feed
    (§4.7) does not use this function: a feed inside its band is two-phase by definition.
    """
    if stream.is_dormant:
        return 0.0
    result = provider.flash(FlashRequest(state=stream), context)
    if result.status != "ok":
        raise VerifierError(f"the verifier's own flash returned {result.status}: {result.message}")

    outlets: tuple[tuple[str, StreamState | None], ...] = (
        ("VAPOR", result.vapor),
        ("LIQUID", result.liquid),
    )
    if result.phase_signature == "TWO_PHASE":
        admissible = _admissible_phase(provider, stream, context)
        if admissible is not None:
            outlets = ((admissible, stream),)

    total = 0.0
    for phase, outlet in outlets:
        if outlet is None or outlet.is_dormant:
            continue
        from openflowsheet.thermo import PropertyRequest

        properties = provider.evaluate_phase(
            PropertyRequest(state=outlet, phase=phase, properties=("h",)),  # type: ignore[arg-type]
            context,
        )
        if properties.status != "ok":
            raise VerifierError(f"the verifier's own enthalpy returned {properties.status}")
        total += sum(
            flow * properties.values[f"h_{component}"]
            for component, flow in zip(COMPONENTS, outlet.n, strict=True)
        )
    return total


def energy_checks(
    provider: PropertyProvider,
    state: Mapping[str, float],
    context: EvaluationContext,
    tolerances: Mapping[str, float] | None = None,
) -> list[CheckResult]:
    """§4.4, with [A09] recorded on every row and the envelope's blind spot registered."""
    note = qualification(provider)
    limit = (tolerances or KIND_TOLERANCE)["heat_rate"]
    streams = {name: stream_of(state, name) for name in STREAMS}
    flows: dict[str, float] = {}
    checks: list[CheckResult] = []

    for name, stream in streams.items():
        if stream.is_dormant:
            flows[name] = 0.0
            checks.append(
                dormant(
                    id=f"energy_balance.enthalpy.{name}", category="energy_balance", subject=name
                )
            )
        else:
            flows[name] = enthalpy_flow(provider, stream, context)

    heater_duty = state[duty_id(HEATER_UNIT)]
    flash_duty = state[duty_id(FLASH_UNIT)]

    def record(name: str, subject: str, value: float) -> None:
        checks.append(
            evaluated(
                id=f"energy_balance.{name}",
                category="energy_balance",
                subject=subject,
                value=value,
                tolerance=limit,
                reference=KIND_REFERENCE["heat_rate"],
                independence_qualification=note,
            )
        )

    record("mixer", "U-MIX", flows["S1"] + flows["S6"] - flows["S2"])
    record("heater", HEATER_UNIT, flows["S2"] + heater_duty - flows["S3"])
    record("flash", FLASH_UNIT, flows["S3"] + flash_duty - flows["S4"] - flows["S5"])
    record("splitter", "U-SPLIT", flows["S5"] - flows["S6"] - flows["S7"])
    # §4.4 and §9.2: the envelope *passes* at the trivial root, because the two duty errors
    # cancel and `Q_h + Q_f` is invariant. Registered as a documented blind spot, and never the
    # only energy check.
    record(
        "envelope",
        "flowsheet",
        heater_duty + flash_duty - (flows["S4"] + flows["S7"] - flows["S1"]),
    )
    return checks


# ------------------------------------------------------- 4.5 / 4.6 specifications and domain


#: K04 §4.5's list, in its order: the columns a SYN-001 revision fixes by specification. The nominal
#: checks read their values from the flowsheet; `declared_specification_checks` from the revision.
SPECIFICATION_COLUMNS: Final[tuple[str, ...]] = (
    temperature_id("S1"),
    pressure_id("S1"),
    *(flow_id("S1", component) for component in COMPONENTS),
    temperature_id("S3"),
    temperature_id("S4"),
    temperature_id("S5"),
)


def declared_specification_checks(
    state: Mapping[str, float],
    *,
    values: Mapping[str, float],
    kinds: Mapping[str, str],
    freed: Mapping[str, str],
    promoted: Sequence[str],
    tolerances: Mapping[str, float] | None = None,
) -> list[CheckResult]:
    """§4.5 on a bound declaration (T04 §4.8 item 3): K04's list, with the binding's two edits.

    A column the binding frees keeps its check id and is `not_applicable` with reason
    `freed(<revision specification id>)` — its value is the solve's, and judging it against the
    guess was the defect. A column a promoted row pins gains `specification.<column>` against the
    revision's value. `values` are the revision's, by column; the flowsheet is never read."""
    limits = tolerances or KIND_TOLERANCE
    checks: list[CheckResult] = []
    for column in (*SPECIFICATION_COLUMNS, *promoted):
        if column in freed:
            checks.append(
                dormant(
                    id=f"specification.{column}",
                    category="specification",
                    subject=column,
                    reason=f"freed({freed[column]})",
                )
            )
            continue
        kind = kinds[column]
        checks.append(
            evaluated(
                id=f"specification.{column}",
                category="specification",
                subject=column,
                value=state[column] - values[column],
                tolerance=limits[kind],
                reference=KIND_REFERENCE[kind],
            )
        )
    return checks


def specification_checks(
    flowsheet: Syn001Flowsheet,
    state: Mapping[str, float],
    tolerances: Mapping[str, float] | None = None,
) -> list[CheckResult]:
    """§4.5: the revision's fixed values, read from the revision and not from the plan."""
    checks: list[CheckResult] = []

    limits = tolerances or KIND_TOLERANCE

    def record(name: str, kind: str, value: float) -> None:
        checks.append(
            evaluated(
                id=f"specification.{name}",
                category="specification",
                subject=name,
                value=value,
                tolerance=limits[kind],
                reference=KIND_REFERENCE[kind],
            )
        )

    record("S1.T", "temperature", state[temperature_id("S1")] - flowsheet.feed_temperature)
    record("S1.P", "pressure", state[pressure_id("S1")] - flowsheet.pressure)
    for index, component in enumerate(COMPONENTS):
        record(
            f"S1.n.{component}",
            "molar_flow",
            state[flow_id("S1", component)] - flowsheet.feed_flows[index],
        )
    record("S3.T", "temperature", state[temperature_id("S3")] - flowsheet.heater_temperature)
    for stream in ("S4", "S5"):
        record(
            f"{stream}.T",
            "temperature",
            state[temperature_id(stream)] - flowsheet.flash_temperature,
        )
    return checks


def is_flow_column(name: str) -> bool:
    """A column §4.6 requires nonnegative: a stream's or a split's molar flow, or a total."""
    return ".n." in name or name.endswith((".V", ".L", ".N")) or ".vap." in name or ".liq." in name


def label_checks(
    zero_flow: Sequence[ZeroFlowSplit],
    state: Mapping[str, float],
    tolerances: Mapping[str, float],
) -> list[CheckResult]:
    """T05b spec §9.3: each zero-flow label row `T_out − T_label` as a residual check, in the
    splits' order, after the compiled rows."""
    checks: list[CheckResult] = []
    for split in zero_flow:
        if split.label is not None:
            label, outlet, source = split.label
            checks.append(
                evaluated(
                    id=f"residual.{label}",
                    category="residual",
                    subject=label,
                    value=state[outlet] - state[source],
                    tolerance=tolerances.get("temperature", KIND_TOLERANCE["temperature"]),
                    reference=KIND_REFERENCE["temperature"],
                )
            )
    return checks


def bounds_checks(
    provider: PropertyProvider,
    state: Mapping[str, float],
    streams: Sequence[str] = STREAMS,
    *,
    components: Sequence[str] = COMPONENTS,
) -> list[CheckResult]:
    """§4.6: nonnegative flows exactly, and a flowing stream inside the declared domain.

    A dormant stream's `T` and `P` are labels, not a state (ADR 0001 D3.1), so they are not
    checked; the check is recorded `not_applicable` rather than skipped. `streams` is the
    flowsheet's allocation order: SYN-001's by default, a revision's for `verify_revision`, and
    `components` the order its flows are read in (M02 design note §14.2 B15 item 1).
    """
    domain = provider.describe().domain
    low_t, high_t = domain["T"]
    low_p, high_p = domain["P"]
    checks: list[CheckResult] = []

    for name, value in sorted(state.items()):
        if is_flow_column(name):
            # Signed-zero normalization first (ADR 0001 D1.5): `-0.0` is `+0.0` and is not
            # a negative flow.
            normalized = value + 0.0
            checks.append(
                CheckResult(
                    id=f"bounds_and_domain.nonnegative.{name}",
                    category="bounds_and_domain",
                    subject=name,
                    result="pass" if normalized >= 0.0 else "fail",
                    value=normalized,
                    tolerance=0.0,
                )
            )

    for stream in streams:
        carried = stream_of(state, stream, components)
        if carried.is_dormant:
            checks.append(
                dormant(
                    id=f"bounds_and_domain.domain.{stream}",
                    category="bounds_and_domain",
                    subject=stream,
                )
            )
            continue
        inside = low_t <= carried.temperature <= high_t and low_p <= carried.pressure <= high_p
        checks.append(
            CheckResult(
                id=f"bounds_and_domain.domain.{stream}",
                category="bounds_and_domain",
                subject=stream,
                result="pass" if inside else "fail",
                value=carried.temperature,
                tolerance=high_t,
                reference=low_t,
            )
        )
    return checks


# ---------------------------------------------------- 4.7 admissibility and the independent split


def k_values(
    provider: PropertyProvider,
    temperature: float,
    pressure: float,
    context: EvaluationContext,
) -> tuple[float, ...]:
    """`K_i(T, P)` from the provider, for the admissibility sums of K03 §8.2."""
    import math

    from openflowsheet.thermo import PropertyRequest

    reference = StreamState(n=(1.0, 1.0, 1.0), temperature=temperature, pressure=pressure)
    result = provider.evaluate_phase(
        PropertyRequest(state=reference, phase="LIQUID", properties=("lnK",)), context
    )
    if result.status != "ok":
        raise VerifierError(f"the verifier's own K-values returned {result.status}")
    return tuple(math.exp(result.values[f"lnK_{component}"]) for component in COMPONENTS)


def _one_sided(*, id: str, subject: str, value: float, note: str) -> CheckResult:
    """K03 §8.2's single-phase test, which is **one-sided** and must not be made two-sided.

    A declared liquid is admissible when `sum x_i K_i <= 1 + eps`. A liquid well below its
    bubble point has `sum x K = 0.96`, and a symmetric `|value - 1| <= eps` would reject it —
    the check would then fail at four of the five registered variants and pass only where the
    state happens to sit on the boundary, which is the opposite of what it is for. The value
    recorded is `sum - 1` so a reader sees the margin and its sign.
    """
    return CheckResult(
        id=id,
        category="phase_admissibility",
        subject=subject,
        result="pass" if value <= 1.0 + ADMISSIBILITY_EPSILON else "fail",
        value=value - 1.0,
        tolerance=ADMISSIBILITY_EPSILON,
        reference=1.0,
        near_threshold=abs(value - 1.0) <= ADMISSIBILITY_EPSILON * NEAR_THRESHOLD_MARGIN,
        independence_qualification=note,
    )


def _fractions(flows: Sequence[float]) -> tuple[float, ...]:
    total = sum(flows)
    return tuple(flow / total for flow in flows)


def _admissible_phase(
    provider: PropertyProvider, stream: StreamState, context: EvaluationContext
) -> str | None:
    """ADR 0013 D2: `"LIQUID"` when a flowing `stream` passes §4.7's bubble test at its own
    `(T, P)`, else `"VAPOR"` when it passes the dew test, else `None` — the tests and the
    arithmetic of `admissibility_checks`, `≤ 1 + ε_adm` each."""
    constants = k_values(provider, stream.temperature, stream.pressure, context)
    fractions = _fractions(stream.n)
    if sum(x * k for x, k in zip(fractions, constants, strict=True)) <= 1.0 + ADMISSIBILITY_EPSILON:
        return "LIQUID"
    if sum(y / k for y, k in zip(fractions, constants, strict=True)) <= 1.0 + ADMISSIBILITY_EPSILON:
        return "VAPOR"
    return None


def closure_check(
    *,
    id: str,
    subject: str,
    provider: PropertyProvider,
    vapor: Sequence[float],
    liquid: Sequence[float],
    temperature: float,
    pressure: float,
    context: EvaluationContext,
    tolerance: float,
    note: str,
) -> CheckResult:
    """§4.7's two-phase closure as T06 spec §8.8 (A4) corrects it: `max(|T − T_b(l, P)|,
    |T − T_d(v, P)|)` in kelvin against the temperature tolerance, from the verifier's own band
    (`verify.saturation`; R-016's independence). K03 §8.2 meant the Rachford–Rice closure — the
    liquid at its bubble point and the vapour at its dew point, both `T` — and K04 wrote it as
    `Σ(v/V) − Σ(l/L)`, which is `1 − 1` for every `V, L > 0`.

    A `SaturationError` is `unsupported` (`closure_<status>`), never a raise; so is a phase whose
    total is not positive (`closure_nonpositive_phase`), which has no bubble or dew point and
    whose flows the nonnegativity checks already judge."""
    from openflowsheet.verify.saturation import SaturationError, saturation_closure

    if not (sum(vapor) > 0.0 and sum(liquid) > 0.0):
        return unsupported(
            id=id,
            category="phase_admissibility",
            subject=subject,
            reason="closure_nonpositive_phase",
        )
    try:
        value = saturation_closure(provider, vapor, liquid, temperature, pressure, context)
    except SaturationError as error:
        return unsupported(
            id=id,
            category="phase_admissibility",
            subject=subject,
            reason=f"closure_{error.status}",
        )
    return evaluated(
        id=id,
        category="phase_admissibility",
        subject=subject,
        value=value,
        tolerance=tolerance,
        reference=KIND_REFERENCE["temperature"],
        independence_qualification=note,
    )


def admissibility_checks(
    provider: PropertyProvider,
    state: Mapping[str, float],
    context: EvaluationContext,
) -> list[CheckResult]:
    """§4.7: K03 §8.2's table, executed by the verifier at the state it is judging.

    K03 specified this and never ran it — the Fable review of K03 recorded that as finding S3 —
    and it could not have run it usefully on the tear path anyway, because the branch it guards
    is in the sink block the attempt signature deliberately does not freeze (review Q3). So it
    lands here, where the state is finished and there is something to check.

    The registered case is the trivial root: S3 forced all-liquid at the once-through variant
    has `sum x_i K_i(350 K) = 1.07 > 1`, which says a liquid at that composition and temperature
    would boil. A branch that cannot exist is the one thing a residual cannot report.
    """
    note = qualification(provider)
    checks: list[CheckResult] = []

    vapor = tuple(state[vapor_flow_id("S3", component)] for component in COMPONENTS)
    liquid = tuple(state[liquid_flow_id("S3", component)] for component in COMPONENTS)
    temperature = state[temperature_id("S3")]
    pressure = state[pressure_id("S3")]
    total_vapor, total_liquid = sum(vapor), sum(liquid)

    if total_vapor + total_liquid == 0.0:
        checks.append(
            dormant(id="phase_admissibility.S3", category="phase_admissibility", subject="S3")
        )
    else:
        constants = k_values(provider, temperature, pressure, context)
        if total_vapor == 0.0:
            checks.append(
                _one_sided(
                    id="phase_admissibility.S3.bubble",
                    subject="S3",
                    value=sum(x * k for x, k in zip(_fractions(liquid), constants, strict=True)),
                    note=note,
                )
            )
        elif total_liquid == 0.0:
            checks.append(
                _one_sided(
                    id="phase_admissibility.S3.dew",
                    subject="S3",
                    value=sum(y / k for y, k in zip(_fractions(vapor), constants, strict=True)),
                    note=note,
                )
            )
        else:
            checks.append(
                closure_check(
                    id="phase_admissibility.S3.closure",
                    subject="S3",
                    provider=provider,
                    vapor=vapor,
                    liquid=liquid,
                    temperature=temperature,
                    pressure=pressure,
                    context=context,
                    tolerance=TEMPERATURE_TOLERANCE,
                    note=note,
                )
            )

    # The independent split: flash S3 from its own (n, T, P) and compare, rather than believing
    # the lifted variables. At the trivial root this differs by 0.304 mol/s, ten million times
    # the tolerance.
    carried = stream_of(state, "S3")
    if carried.is_dormant:
        checks.append(
            dormant(id="independent_split.S3", category="independent_split", subject="S3")
        )
        return checks

    flashed = provider.flash(FlashRequest(state=carried), context)
    if flashed.status != "ok" or flashed.vapor is None:
        raise VerifierError(f"the verifier's own split returned {flashed.status}")
    checks.append(
        evaluated(
            id="independent_split.S3.total",
            category="independent_split",
            subject="S3",
            value=state[vapor_total_id("S3")] - sum(flashed.vapor.n),
            tolerance=FLOW_TOLERANCE,
            reference=KIND_REFERENCE["molar_flow"],
            independence_qualification=note,
        )
    )
    for index, component in enumerate(COMPONENTS):
        checks.append(
            evaluated(
                id=f"independent_split.S3.{component}",
                category="independent_split",
                subject="S3",
                value=vapor[index] - flashed.vapor.n[index],
                tolerance=FLOW_TOLERANCE,
                reference=KIND_REFERENCE["molar_flow"],
                independence_qualification=note,
            )
        )
    return checks


# ---------------------------------------------------------------- 4.8 the derivative witness

#: §4.8. The measured minimum: quadratic in delta down to 1e-5 (2.8e-10 worst) and
#: roundoff-dominated from 1e-6 (2.8e-9). Registered because it is the measured minimum, not
#: because it is a round number.
FD_RELATIVE_STEP: Final = 1e-5
#: §4.8: 350x above the worst floor and 1600x below the smallest nonzero scaled entry
#: (1.6e-4 measured), so a dropped term or a K at the wrong temperature is caught and roundoff
#: is not.
DERIVATIVE_TOLERANCE: Final = 1e-7


def derivative_witness(
    tear: object, state: Mapping[str, float], *, unstenciled: frozenset[str] = frozenset()
) -> list[CheckResult]:
    """§4.8: central differences of the **compiled 49-row function** against its AD Jacobian.

    Of the compiled function, not of the traversal: plan §4.2 demotes a finite-difference tear
    Jacobian to a test oracle, and K03 measured why it cannot be used at `t*` at all — the
    stencil leaves the mixer's domain on two of three columns there, because `t*` is the
    saturated boundary. The compiled function has no such domain edge in the lifted variables.

    Off-pattern entries are compared too. A structural zero that is not exactly zero is a
    declared pattern that lies, and it is silent in every residual.

    A stencil point is a state the verifier constructs, so one the compiled function cannot
    evaluate — a pressure within one step of the provider's domain edge — makes both witness
    checks `unsupported`, naming the column and the status, and never raises (T06 spec §8.2;
    ADR 0014 D5).

    `unstenciled` (M02 design note §14.2 B17 *Consequence*; build log D40) names columns the
    witness does not difference: a `pr-c1-v1` revision's flow columns that are exactly `0.0` at
    `state`, where every stencil point leaves the provider's domain (a negative flow, or light gas
    in the pure-NH3 liquid) and the AD entries are B17's registered dormancy convention, at which
    no derivative exists. Empty for every other revision, which runs the stencil as before.
    """
    from openflowsheet.compile.reference import state_vector

    spec = tear.spec  # type: ignore[attr-defined]
    compiled = tear.compiled  # type: ignore[attr-defined]
    context = tear.context  # type: ignore[attr-defined]
    scaling = tear.scaling  # type: ignore[attr-defined]

    base = np.array(state_vector(spec, state))
    jacobian = compiled.jacobian(base, context)
    if jacobian.status != "ok":
        raise VerifierError(f"the witness could not read the Jacobian: {jacobian.status}")

    exact: dict[tuple[int, int], float] = {}
    for column in range(len(jacobian.col_ids)):
        for offset in range(jacobian.indptr[column], jacobian.indptr[column + 1]):
            exact[(int(jacobian.indices[offset]), column)] = float(jacobian.data[offset])

    worst_on, worst_off = 0.0, 0.0
    for column, name in enumerate(jacobian.col_ids):
        if name in unstenciled:
            continue
        step = FD_RELATIVE_STEP * scaling.column[name]
        forward, backward = base.copy(), base.copy()
        forward[column] += step
        backward[column] -= step
        high = compiled.residual(forward, context)
        low = compiled.residual(backward, context)
        if high.status != "ok" or low.status != "ok" or high.values is None or low.values is None:
            status = high.status if high.status != "ok" else low.status
            reason = f"witness_stencil_{status}({name})"
            return [
                unsupported(
                    id=f"derivative_witness.{which}",
                    category="derivative_witness",
                    subject="target_jacobian",
                    reason=reason,
                )
                for which in ("on_pattern", "off_pattern")
            ]
        for row, row_id in enumerate(jacobian.row_ids):
            difference = (high.values[row] - low.values[row]) / (2.0 * step)
            scaled = difference * scaling.column[name] / scaling.row[row_id]
            entry = exact.get((row, column))
            if entry is None:
                worst_off = max(worst_off, abs(scaled))
            else:
                scaled_exact = entry * scaling.column[name] / scaling.row[row_id]
                worst_on = max(worst_on, abs(scaled_exact - scaled))

    return [
        evaluated(
            id="derivative_witness.on_pattern",
            category="derivative_witness",
            subject="target_jacobian",
            value=worst_on,
            tolerance=DERIVATIVE_TOLERANCE,
            reference=1.0,
        ),
        evaluated(
            id="derivative_witness.off_pattern",
            category="derivative_witness",
            subject="target_jacobian",
            value=worst_off,
            tolerance=DERIVATIVE_TOLERANCE,
            reference=1.0,
        ),
    ]
