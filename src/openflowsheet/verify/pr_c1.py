"""The verifier's `pr-c1-v1` forms of K04 §4.4 and §4.7 (M02 design note §14.2 B15; ADR 0013
Amendment 3; register R-257).

`pr-c1-v1` has no K-values, a mixture `h` rather than per-component `h_<c>`, a liquid that is pure
NH3 and a half-open saturation band (M01 §7 rule 4). SYN-001's table functions read all four, so the
revision table (`verify.table`) dispatches on the revision's basis and, for `pr-c1-v1`, runs the
forms here. SYN-001's functions are not edited: their arithmetic is protected by leaving it alone.

- **Fresh-flash enthalpy** (K04 §4.4, ADR 0013 D2): a dormant stream is `0.0`; otherwise the
  stream's own `(n, T, P)` is flashed, and a TWO_PHASE answer whose liquid NH3 is at most
  τ_dew of the stream is read as VAPOR at the stream's own state (D2's analogue, M01 §7 rule 6);
  each non-dormant outlet contributes `Σn · h` in its phase, vapour then liquid, from `0.0`.
- **No degeneracy and no unresolved routing** (ADR 0012 D7, ADR 0013 D3): a stream carrying light
  gas has a half-open band, so it is never degenerate, and with `w = ∞` D3's floor is 0. A pure-NH3
  stream within τ_T of T_sat(P) is read in its fresh flash's phase — conservative: a wrong reading
  fails an energy check and never passes one. A stated limitation.
- **A split** (K04 §4.7): VAPOR branch `.dew`, one-sided against τ_dew; TWO_PHASE `.closure`, the
  first-order distance in kelvin of the vapour from its own NH3 dew temperature at fixed `(v, P)`,
  against τ_T; LIQUID branch `.bubble` `unsupported`; the independent split by K04's formula.
- **Declared ports**: a declared vapour port by the τ_dew test on a fresh flash of the stream; a
  declared liquid port `unsupported`.

No tolerance, kind, category or required check is new: τ_dew is R-230's (`models.c1.TAU_DEW`, the
one name this module reads from the models), τ_T and τ_flow are K04's, so `check_policy_sha256` does
not move. The band rule here is the verifier's own copy of the solver's (`models.c1.phase.classify`,
R-016); a test compares the two as data (gate G7 (k)).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import TAU_DEW
from openflowsheet.models.revision_flowsheet import RevisionView
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)
from openflowsheet.verify import (
    NEAR_THRESHOLD_MARGIN,
    CheckResult,
    dormant,
    evaluated,
    unsupported,
)
from openflowsheet.verify.checks import KIND_REFERENCE, VerifierError, stream_of

if TYPE_CHECKING:
    from openflowsheet.orchestrator.region import LiftedSplit

__all__ = [
    "PROVIDER_ID",
    "VAPOUR_ONLY",
    "band",
    "declared_port_checks",
    "enthalpy_flow",
    "liquid_fraction",
    "split_checks",
]

#: The provider whose forms these are.
PROVIDER_ID: Final = "pr-c1-v1"
#: The condensable component, and the vapour-only ones: the verifier's own reading of R-143.
CONDENSABLE: Final = "NH3"
VAPOUR_ONLY: Final[tuple[str, ...]] = ("H2", "N2", "Ar", "CH4")
#: B15 item 7: the qualification each `pr-c1-v1` admissibility check appends.
DEW_FORM: Final = "dew band, liquid NH3 fraction of a fresh TP flash"
CLOSURE_FORM: Final = "first-order distance in K from the vapour's NH3 dew point"


def _form(note: str, form: str) -> str:
    return f"{note}; pr-c1-v1 form (M01 §7; design note §14.2 B15): {form}"


def _nh3(stream: StreamState, components: Sequence[str]) -> float:
    return stream.n[components.index(CONDENSABLE)]


def _flash(
    provider: PropertyProvider, context: EvaluationContext, stream: StreamState
) -> FlashResult:
    return provider.flash(FlashRequest(state=stream), context)


def liquid_fraction(result: FlashResult, stream: StreamState, components: Sequence[str]) -> float:
    """`l_NH3 / n_tot` of an `ok` flash of a flowing `stream`: `0.0` for a VAPOR answer, the
    liquid's NH3 over the stream's total otherwise (all of it for a LIQUID answer)."""
    assert result.liquid is not None
    return _nh3(result.liquid, components) / stream.total_flow


def band(
    provider: PropertyProvider,
    context: EvaluationContext,
    n: Sequence[float],
    temperature: float,
    pressure: float,
    components: Sequence[str],
) -> tuple[str | None, float]:
    """The verifier's copy of M01 §7 rule 3 with τ_dew: a fresh TP flash, TWO_PHASE with
    `l_NH3 / n_tot ≤ τ_dew` read as VAPOR. Returns `(regime, value)` as the solver's `classify`
    does — `0.0` for ZERO_FLOW and VAPOR, `n_light / n_tot` for LIQUID, `l_NH3 / n_tot` for
    TWO_PHASE — and `(None, nan)` on a refusal."""
    stream = StreamState(n=tuple(n), temperature=temperature, pressure=pressure)
    result = _flash(provider, context, stream)
    if result.status != "ok" or result.phase_signature is None:
        return None, math.nan
    if result.phase_signature in ("ZERO_FLOW", "VAPOR"):
        return result.phase_signature, 0.0
    if result.phase_signature == "LIQUID":
        light = sum(stream.n[components.index(c)] for c in VAPOUR_ONLY)
        return "LIQUID", light / stream.total_flow
    value = liquid_fraction(result, stream, components)
    return ("VAPOR" if value <= TAU_DEW else "TWO_PHASE"), value


def _phase_property(
    provider: PropertyProvider,
    context: EvaluationContext,
    stream: StreamState,
    phase: Phase,
    name: str,
    derivatives: tuple[str, ...] = (),
) -> tuple[float, float | None, str]:
    """One property of `stream` in `phase`: `(value, ∂/∂T or None, "")`, or `(nan, None,
    status)` when the provider refuses."""
    result = provider.evaluate_phase(
        PropertyRequest(state=stream, phase=phase, properties=(name,), derivatives=derivatives),
        context,
    )
    if result.status != "ok":
        return math.nan, None, str(result.status)
    by_t = result.derivatives[name]["T"] if derivatives else None
    return result.values[name], by_t, ""


def enthalpy_flow(
    provider: PropertyProvider,
    stream: StreamState,
    context: EvaluationContext,
    components: Sequence[str],
) -> float:
    """`Ḣ` of `stream` from a fresh flash of its own `(n, T, P)` (K04 §4.4; B15 item 2)."""
    if stream.is_dormant:
        return 0.0
    result = _flash(provider, context, stream)
    if result.status != "ok":
        raise VerifierError(f"the verifier's own flash returned {result.status}: {result.message}")
    outlets: tuple[tuple[Phase, StreamState | None], ...] = (
        ("VAPOR", result.vapor),
        ("LIQUID", result.liquid),
    )
    if (
        result.phase_signature == "TWO_PHASE"
        and liquid_fraction(result, stream, components) <= TAU_DEW
    ):
        outlets = (("VAPOR", stream),)
    total = 0.0
    for phase, outlet in outlets:
        if outlet is None or outlet.is_dormant:
            continue
        h, _, refused = _phase_property(provider, context, outlet, phase, "h")
        if refused:
            raise VerifierError(f"the verifier's own enthalpy returned {refused}")
        total += sum(outlet.n) * h
    return total


def _dew(*, id: str, subject: str, value: float, note: str) -> CheckResult:
    """B15's one-sided τ_dew test: pass iff `value ≤ τ_dew`, reference 1.0, near threshold iff
    `τ/10 < value ≤ 10 τ` (ADR 0007 D2.4)."""
    return CheckResult(
        id=id,
        category="phase_admissibility",
        subject=subject,
        result="pass" if value <= TAU_DEW else "fail",
        value=value,
        tolerance=TAU_DEW,
        reference=1.0,
        near_threshold=TAU_DEW / NEAR_THRESHOLD_MARGIN < value <= TAU_DEW * NEAR_THRESHOLD_MARGIN,
        independence_qualification=_form(note, DEW_FORM),
    )


def _fresh_dew(
    provider: PropertyProvider,
    context: EvaluationContext,
    stream: StreamState,
    components: Sequence[str],
    *,
    id: str,
    subject: str,
    note: str,
) -> CheckResult:
    """The τ_dew test on a fresh flash of `stream`; a refusal is `unsupported` (`dew_<status>`),
    never a pass."""
    result = _flash(provider, context, stream)
    if result.status != "ok" or result.liquid is None:
        return unsupported(
            id=id, category="phase_admissibility", subject=subject, reason=f"dew_{result.status}"
        )
    return _dew(
        id=id, subject=subject, value=liquid_fraction(result, stream, components), note=note
    )


def _closure(
    *,
    id: str,
    subject: str,
    provider: PropertyProvider,
    context: EvaluationContext,
    vapor: StreamState,
    liquid: StreamState,
    components: Sequence[str],
    tolerance: float,
    note: str,
) -> CheckResult:
    """B15 item 4's TWO_PHASE closure: `|g / g_T|` in kelvin, `g = ln(v_NH3 / Σv) + ln φ^V_NH3(v,
    T, P) − ln φ^L_NH3(T, P)` on the state's own phases, `g_T` its T-derivative."""
    if not (sum(vapor.n) > 0.0 and sum(liquid.n) > 0.0):
        return unsupported(
            id=id,
            category="phase_admissibility",
            subject=subject,
            reason="closure_nonpositive_phase",
        )
    lv, lv_t, refused = _phase_property(
        provider, context, vapor, "VAPOR", "lnphi_NH3", derivatives=("T",)
    )
    if not refused:
        ll, ll_t, refused = _phase_property(
            provider, context, liquid, "LIQUID", "lnphi_NH3", derivatives=("T",)
        )
    if refused:
        return unsupported(
            id=id, category="phase_admissibility", subject=subject, reason=f"closure_{refused}"
        )
    assert lv_t is not None and ll_t is not None
    slope = lv_t - ll_t
    if slope == 0.0:
        return unsupported(
            id=id, category="phase_admissibility", subject=subject, reason="closure_degenerate"
        )
    fraction = _nh3(vapor, components) / sum(vapor.n)
    g = (math.log(fraction) if fraction > 0.0 else -math.inf) + lv - ll
    return evaluated(
        id=id,
        category="phase_admissibility",
        subject=subject,
        value=abs(g / slope),
        tolerance=tolerance,
        reference=KIND_REFERENCE["temperature"],
        independence_qualification=_form(note, CLOSURE_FORM),
    )


def split_checks(
    split: LiftedSplit,
    components: Sequence[str],
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    note: str,
) -> list[CheckResult]:
    """K04 §4.7 on one `pr-c1-v1` split (B15 item 4): the branch's admissibility, then the
    independent split by SYN-001's formula (written again here; `table._split_checks` is not
    edited)."""
    name = f"{split.unit}.{split.stream}"
    subject = split.stream
    checks: list[CheckResult] = []
    vapor = tuple(state[column] for column in split.vapor)
    liquid = tuple(state[column] for column in split.liquid)
    temperature = state[split.temperature]
    pressure = state[split.pressure]
    total_vapor, total_liquid = sum(vapor), sum(liquid)
    carried = StreamState(
        n=tuple(state[column] for column in split.feed),
        temperature=temperature,
        pressure=pressure,
    )

    if total_vapor + total_liquid == 0.0:
        checks.append(
            dormant(
                id=f"phase_admissibility.{name}", category="phase_admissibility", subject=subject
            )
        )
    elif total_vapor == 0.0:
        checks.append(
            unsupported(
                id=f"phase_admissibility.{name}.bubble",
                category="phase_admissibility",
                subject=subject,
                reason="pr_liquid_regime_unsupported",
            )
        )
    elif total_liquid == 0.0:
        if carried.is_dormant:
            # A vapour split of a dormant feed has nothing to flash; the material balance judges
            # the inconsistency, and this check says it does not apply rather than passing.
            checks.append(
                dormant(
                    id=f"phase_admissibility.{name}.dew",
                    category="phase_admissibility",
                    subject=subject,
                )
            )
        else:
            checks.append(
                _fresh_dew(
                    provider,
                    context,
                    carried,
                    components,
                    id=f"phase_admissibility.{name}.dew",
                    subject=subject,
                    note=note,
                )
            )
    else:
        checks.append(
            _closure(
                id=f"phase_admissibility.{name}.closure",
                subject=subject,
                provider=provider,
                context=context,
                vapor=StreamState(n=vapor, temperature=temperature, pressure=pressure),
                liquid=StreamState(n=liquid, temperature=temperature, pressure=pressure),
                components=components,
                tolerance=tolerances["temperature"],
                note=note,
            )
        )

    if carried.is_dormant:
        checks.append(
            dormant(id=f"independent_split.{name}", category="independent_split", subject=subject)
        )
        return checks
    flashed = _flash(provider, context, carried)
    if flashed.status != "ok" or flashed.vapor is None:
        raise VerifierError(f"the verifier's own split of {name} returned {flashed.status}")
    checks.append(
        evaluated(
            id=f"independent_split.{name}.total",
            category="independent_split",
            subject=subject,
            value=state[split.vapor_total] - sum(flashed.vapor.n),
            tolerance=tolerances["molar_flow"],
            reference=KIND_REFERENCE["molar_flow"],
            independence_qualification=note,
        )
    )
    for index, component in enumerate(components):
        checks.append(
            evaluated(
                id=f"independent_split.{name}.{component}",
                category="independent_split",
                subject=subject,
                value=vapor[index] - flashed.vapor.n[index],
                tolerance=tolerances["molar_flow"],
                reference=KIND_REFERENCE["molar_flow"],
                independence_qualification=note,
            )
        )
    return checks


def declared_port_checks(
    view: RevisionView,
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    note: str,
    declared_ports: Mapping[str, tuple[tuple[str, bool], ...]],
) -> list[CheckResult]:
    """B15 item 5, with `table._declared_port_checks`' iteration and ids: by model id, the ports
    whose declared phase is judged (`declared_ports`, the table's entries). A declared vapour by
    the τ_dew test on a fresh flash of the stream's own `(n, T, P)`; a declared liquid
    `unsupported` (`pr_declared_liquid_unsupported`); a dormant stream `not_applicable`."""
    checks: list[CheckResult] = []
    for instance in view.instances:
        ports = declared_ports.get(instance.model_id)
        if ports is None:
            continue
        for port, several in ports:
            phase = instance.phases.get(port)
            if phase is None:
                continue
            for stream in instance.ports.get(port, ()):
                identifier = (
                    f"phase_admissibility.{instance.unit_id}.{port}.{stream}"
                    if several
                    else f"phase_admissibility.{instance.unit_id}.{port}"
                )
                carried = stream_of(state, stream, components=view.components)
                if carried.is_dormant:
                    checks.append(
                        dormant(id=identifier, category="phase_admissibility", subject=stream)
                    )
                elif phase == "LIQUID":
                    checks.append(
                        unsupported(
                            id=identifier,
                            category="phase_admissibility",
                            subject=stream,
                            reason="pr_declared_liquid_unsupported",
                        )
                    )
                else:
                    checks.append(
                        _fresh_dew(
                            provider,
                            context,
                            carried,
                            view.components,
                            id=identifier,
                            subject=stream,
                            note=note,
                        )
                    )
    return checks
