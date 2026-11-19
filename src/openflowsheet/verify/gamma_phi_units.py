"""The verifier's γ–φ form for the K02/T05 units' lifted splits (S11 units design §4.8; ADR 0051;
WO-D3).

Since I1b `verify.table.revision_checks` runs this form for `wilson-ig-v2` revisions
(`GAMMA_PHI_UNITS`); this module supplies the form's guard (`require_composition_dependent`), its
routing (`degeneracy`) and its admissibility rows (`admissibility_checks`). It is the first pass's
`DECLARED_MIXTURE` form (`verify.forms`, `verify.table.revision_checks`) with one addition, so
that the five γ–φ-faced units of WO-D1 are verified rather than blocked:

- **Identity with the first pass.** Every stream and unit `DECLARED_MIXTURE` handles gets the
  checks it gets there, built by the same functions: declared streams (`n·h(T, P, phase)` and
  `phase_admissibility.stream.<S>`), the routing models, the column (whose staged splits are
  not `SPLIT_RULES` descriptors and are left to its own rows), the material balances,
  specifications and bounds (S11.A73).
- **What it adds**, for each `SPLIT_RULES` descriptor (an instance of a model with a registry
  split), SYN-001's check ids (`verify.split_checks._split_checks`) with these substitutions:
  - *degeneracy*: temperature-degenerate iff the bubble and dew temperatures of the split's feed
    at P lie within τ_T of T, by `models.syn001.saturation_band.degeneracy_distance` (which
    dispatches on the equilibrium form); the check carries `BAND_NOTE`, A3's shared-implementation
    note for this criterion;
  - *independent split*: the fresh provider's TP flash of `(n_feed, T, P)` against the state's
    split: `independent_split.<U>.<S>.total` is the vapour total's difference (SYN-001's) and
    `independent_split.<U>.<S>.<c>` is whichever of `Δv_c`, `Δl_c` is larger in magnitude, so
    that it passes iff `max(|Δv_c|, |Δl_c|) ≤ τ_flow`. A degenerate split's is `not_applicable`
    (`temperature_degenerate`, ADR 0012 D7);
  - *admissibility*: `provider.stability` of each flowing phase of the split, which must report
    `STABLE_WITHIN_TESTED_SCOPE`, as `.bubble` (liquid only), `.dew` (vapour only) or `.closure`
    (both; also `V, L ≥ −τ_flow`); the value is the other phase model's trial `tm` (the least, on
    `.closure`), the tolerance the report's resolution, the verdict the provider's;
  - *enthalpy* of a heater-style (lifted) split's stream: `Σ` over phases of the phase total ×
    mixture `h(T, P, phase composition)` from the fresh flash, or from the stored split when
    degenerate (with `table.SPLIT_ENTHALPY_NOTE`). A flash-style split's products are declared
    streams, read as the first pass reads them.

A lifted stream that no `SPLIT_RULES` descriptor owns stays unlifted: every check reading it is
blocked, as in the first pass. ADR 0013 D3's unresolved route has no γ–φ counterpart in §4.8 and is
not taken here. The fresh provider is composition-dependent; anything else is refused.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Final

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import RevisionView
from openflowsheet.models.syn001.band_types import BandError
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.models.syn001.saturation_band import (
    degeneracy_distance,
    is_temperature_degenerate,
)
from openflowsheet.orchestrator.splits import SPLIT_RULES
from openflowsheet.thermo import FlashRequest, Phase, PropertyProvider, StreamState
from openflowsheet.thermo.stability import StabilityReport
from openflowsheet.verify import CheckResult, dormant, evaluated, forms, unsupported
from openflowsheet.verify.checks import (
    VerifierError,
    stream_of,
)
from openflowsheet.verify.column import _SHARED_STABILITY, _STABLE
from openflowsheet.verify.split_checks import Degeneracy
from openflowsheet.verify.table_kit import (
    SPLIT_ENTHALPY_NOTE,
    Judging,
    degenerate_split_rows,
    independent_split_rows,
)

if TYPE_CHECKING:
    from openflowsheet.models.lifted import LiftedSplit

__all__ = [
    "BAND_NOTE",
    "GAMMA_PHI_UNITS",
    "admissibility_checks",
    "degeneracy",
    "registry_splits",
    "require_composition_dependent",
    "split_checks",
]

#: The form's name: `verify.forms.form_of("wilson-ig-v2")`, which `verify.table.revision_checks`
#: runs with this module's pieces (I1b).
GAMMA_PHI_UNITS: Final = forms.GAMMA_PHI_UNITS
#: A09, as A3's `verify.forms._SHARED` for the admissibility criterion: the band is the units' own.
BAND_NOTE: Final = (
    "; the band is models.syn001.saturation_band.degeneracy_distance, the implementation the "
    "units use (not an independent check)"
)


def registry_splits(view: RevisionView, splits: Sequence[LiftedSplit]) -> tuple[LiftedSplit, ...]:
    """The descriptors of `splits` that an instance of a `SPLIT_RULES` model owns, in order (a
    staged split's key is no instance, so the column's are left out)."""
    models = {instance.unit_id: instance.model_id for instance in view.instances}
    return tuple(split for split in splits if models.get(split.unit) in SPLIT_RULES)


def _flows(state: Mapping[str, float], columns: Sequence[str]) -> tuple[float, ...]:
    return tuple(state[column] for column in columns)


def _distance(
    provider: PropertyProvider,
    split: LiftedSplit,
    state: Mapping[str, float],
    context: EvaluationContext,
) -> float:
    """`δ` of the split's feed at the split's `(T, P)`; a band refusal is the verifier's error."""
    try:
        return degeneracy_distance(
            provider,
            _flows(state, split.feed),
            state[split.temperature],
            state[split.pressure],
            context,
        )
    except BandError as error:
        raise VerifierError(
            f"the verifier's own band of {split.unit}.{split.stream} returned {error.status}: "
            f"{error.message}"
        ) from error


def _fresh_split(
    provider: PropertyProvider,
    split: LiftedSplit,
    state: Mapping[str, float],
    context: EvaluationContext,
) -> tuple[StreamState, StreamState]:
    """The fresh provider's TP flash of the split's feed at its `(T, P)`: `(vapour, liquid)`."""
    carried = StreamState(
        n=_flows(state, split.feed),
        temperature=state[split.temperature],
        pressure=state[split.pressure],
    )
    flashed = provider.flash(FlashRequest(state=carried), context)
    if flashed.status != "ok" or flashed.vapor is None or flashed.liquid is None:
        raise VerifierError(
            f"the verifier's own split of {split.unit}.{split.stream} returned {flashed.status}"
        )
    return flashed.vapor, flashed.liquid


def _phase_flow(
    provider: PropertyProvider,
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    phase: Phase,
    context: EvaluationContext,
) -> float:
    """The phase total × mixture `h(T, P, phase composition)`; 0.0 for an empty phase."""
    stream = StreamState(n=flows, temperature=temperature, pressure=pressure)
    return forms.enthalpy_flow(provider, stream, phase, context)


def degeneracy(
    view: RevisionView,
    splits: Sequence[LiftedSplit],
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
) -> Degeneracy:
    """The registry splits' degeneracy and the lifted streams' enthalpies (§4.8), and the
    unlifted streams of the first pass that no registry split owns.

    `splits` maps each flowing degenerate split to its `δ`; `enthalpy` holds each flowing
    heater-style split's stream (fresh flash, or the stored split with its note when degenerate).
    """
    components = view.components
    declared = forms.declared_phases(view)
    distances: dict[str, float] = {}
    enthalpy: dict[str, float] = {}
    notes: dict[str, str] = {}
    for split in registry_splits(view, splits):
        if all(flow == 0.0 for flow in _flows(state, split.feed)):
            continue
        distance = _distance(provider, split, state, context)
        degenerate = is_temperature_degenerate(distance)
        if degenerate:
            distances[split.unit] = distance
        if SPLIT_RULES[_model(view, split.unit)].style != "outlet":
            continue
        stream = split.stream
        if stream_of(state, stream, components).is_dormant:
            continue
        temperature, pressure = state[split.temperature], state[split.pressure]
        if degenerate:
            vapor, liquid = _flows(state, split.vapor), _flows(state, split.liquid)
            notes[stream] = SPLIT_ENTHALPY_NOTE.format(stream=stream)
        else:
            fresh_vapor, fresh_liquid = _fresh_split(provider, split, state, context)
            vapor, liquid = tuple(fresh_vapor.n), tuple(fresh_liquid.n)
        enthalpy[stream] = _phase_flow(
            provider, vapor, temperature, pressure, "VAPOR", context
        ) + _phase_flow(provider, liquid, temperature, pressure, "LIQUID", context)
    unlifted = frozenset(
        stream
        for stream, phase in declared.items()
        if phase is None
        and stream not in enthalpy
        and not stream_of(state, stream, components).is_dormant
    )
    return Degeneracy(splits=distances, enthalpy=enthalpy, notes=notes, unlifted=unlifted)


def _model(view: RevisionView, unit: str) -> str:
    (model,) = (instance.model_id for instance in view.instances if instance.unit_id == unit)
    return model


def _stability(
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    phase: Phase,
    judging: Judging,
) -> tuple[bool, float, float] | str:
    """`(stable, tm, ε)`: the provider's verdict on `phase`, the other phase model's trial `tm`
    and the report's resolution; or the reason it decided nothing (`verify.column`'s rule)."""
    other: Phase = "VAPOR" if phase == "LIQUID" else "LIQUID"
    judge = getattr(judging.provider, "stability", None)
    if judge is None:
        return "stability_unavailable"
    report: StabilityReport = judge(
        StreamState(n=flows, temperature=temperature, pressure=pressure), phase, judging.context
    )
    distance = report.tm.get(other)
    if report.label not in (_STABLE, "UNSTABLE") or distance is None:
        return f"stability_{report.label.lower()}: {report.reason}"
    return report.label == _STABLE, distance, report.epsilon


def _split_admissibility(split: LiftedSplit, judging: Judging) -> CheckResult:
    """§4.8's admissibility under SYN-001's id for the split's branch."""
    name = f"{split.unit}.{split.stream}"
    vapor, liquid = _flows(judging.state, split.vapor), _flows(judging.state, split.liquid)
    temperature, pressure = judging.state[split.temperature], judging.state[split.pressure]
    total_vapor, total_liquid = sum(vapor), sum(liquid)
    phases: tuple[tuple[Phase, tuple[float, ...]], ...]
    if total_vapor == 0.0:
        identifier, phases = f"phase_admissibility.{name}.bubble", (("LIQUID", liquid),)
    elif total_liquid == 0.0:
        identifier, phases = f"phase_admissibility.{name}.dew", (("VAPOR", vapor),)
    else:
        identifier = f"phase_admissibility.{name}.closure"
        flowing: tuple[tuple[Phase, tuple[float, ...], float], ...] = (
            ("VAPOR", vapor, total_vapor),
            ("LIQUID", liquid, total_liquid),
        )
        phases = tuple((phase, flows) for phase, flows, total in flowing if total > 0.0)
    verdicts: list[tuple[bool, float, float]] = []
    for phase, flows in phases:
        verdict = _stability(flows, temperature, pressure, phase, judging)
        if isinstance(verdict, str):
            return unsupported(
                id=identifier, category="phase_admissibility", subject=split.stream, reason=verdict
            )
        verdicts.append(verdict)
    stable = all(verdict[0] for verdict in verdicts)
    # A two-phase branch also needs both totals at or above −τ_flow (§4.8).
    stable = stable and min(total_vapor, total_liquid) >= -judging.tolerances["molar_flow"]
    least = min(verdicts, key=lambda verdict: verdict[1]) if verdicts else (True, 0.0, 0.0)
    return replace(
        evaluated(
            id=identifier,
            category="phase_admissibility",
            subject=split.stream,
            value=least[1],
            tolerance=least[2],
            independence_qualification=judging.note + _SHARED_STABILITY,
        ),
        result="pass" if stable else "fail",
    )


def split_checks(
    split: LiftedSplit, judging: Judging, distance: float | None = None
) -> list[CheckResult]:
    """§4.8 on one registry split under SYN-001's ids (`verify.split_checks._split_checks`): a
    flowing degenerate split (`distance` its `δ`) has `.saturation` and its independent split
    `not_applicable`; any other has its admissibility and the fresh flash's comparison."""
    name = f"{split.unit}.{split.stream}"
    subject = split.stream
    if distance is not None:
        return degenerate_split_rows(
            name, subject, distance, judging.tolerances, judging.note + BAND_NOTE
        )
    vapor, liquid = _flows(judging.state, split.vapor), _flows(judging.state, split.liquid)
    checks: list[CheckResult] = []
    if sum(vapor) + sum(liquid) == 0.0:
        checks.append(
            dormant(
                id=f"phase_admissibility.{name}", category="phase_admissibility", subject=subject
            )
        )
    else:
        checks.append(_split_admissibility(split, judging))
    if all(flow == 0.0 for flow in _flows(judging.state, split.feed)):
        checks.append(
            dormant(id=f"independent_split.{name}", category="independent_split", subject=subject)
        )
        return checks
    fresh_vapor, fresh_liquid = _fresh_split(
        judging.provider, split, judging.state, judging.context
    )
    total = judging.state[split.vapor_total] - sum(fresh_vapor.n)
    differences: list[float] = []
    for index in range(len(judging.components)):
        by_vapor = vapor[index] - fresh_vapor.n[index]
        by_liquid = liquid[index] - fresh_liquid.n[index]
        differences.append(by_vapor if abs(by_vapor) >= abs(by_liquid) else by_liquid)
    checks += independent_split_rows(name, subject, total, differences, judging)
    return checks


def require_composition_dependent(provider: PropertyProvider) -> None:
    """The form's guard (§4.8): the fresh provider is composition-dependent
    (`models.syn001.equilibrium_form.composition_dependent`); any other raises `VerifierError`."""
    if not composition_dependent(provider):
        raise VerifierError(
            f"gamma_phi_units needs a composition-dependent provider, not "
            f"{provider.describe().provider_id}"
        )


def admissibility_checks(
    view: RevisionView,
    splits: Sequence[LiftedSplit],
    declared: Mapping[str, Phase | None],
    degenerate: Degeneracy,
    judging: Judging,
) -> list[CheckResult]:
    """The form's admissibility rows (§4.8): each registry split's `split_checks` in `splits`
    order, routed by `degenerate`, then each stream's in its `declared` phase
    (`forms.stream_admissibility`, as in the first pass)."""
    admissibility: list[CheckResult] = []
    for split in registry_splits(view, splits):
        admissibility += split_checks(split, judging, degenerate.splits.get(split.unit))
    admissibility += forms.stream_admissibility(
        view, declared, judging.state, judging.provider, judging.context, judging.note
    )
    return admissibility
