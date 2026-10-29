"""The verifier's γ–φ form for the K02/T05 units' lifted splits (S11 units design §4.8; ADR 0051;
WO-D3).

Since I1b `verify.table.revision_checks` sends `wilson-ig-v2` revisions here (`GAMMA_PHI_UNITS`).
It is the first pass's `DECLARED_MIXTURE` form (`verify.forms`,
`verify.table.revision_checks`) with one addition, so that the five γ–φ-faced units of WO-D1 are
verified rather than blocked:

- **Identity with the first pass.** Every stream and unit `DECLARED_MIXTURE` handles gets the
  checks it gets there, built by the same functions: declared streams (`n·h(T, P, phase)` and
  `phase_admissibility.stream.<S>`), the routing models, the column (whose staged splits are
  not `SPLIT_RULES` descriptors and are left to its own rows), the material balances,
  specifications and bounds (S11.A73).
- **What it adds**, for each `SPLIT_RULES` descriptor (an instance of a model with a registry
  split), SYN-001's check ids (`verify.table._split_checks`) with these substitutions:
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
from openflowsheet.models.syn001.equilibrium_form import composition_dependent
from openflowsheet.models.syn001.saturation_band import (
    BandError,
    degeneracy_distance,
    is_temperature_degenerate,
)
from openflowsheet.orchestrator.splits import SPLIT_RULES
from openflowsheet.thermo import FlashRequest, Phase, PropertyProvider, StreamState
from openflowsheet.thermo.stability import StabilityReport
from openflowsheet.verify import CheckResult, dormant, evaluated, forms, unsupported
from openflowsheet.verify.checks import (
    KIND_REFERENCE,
    VerifierError,
    bounds_checks,
    qualification,
    stream_of,
)
from openflowsheet.verify.column import _SHARED_STABILITY, _STABLE
from openflowsheet.verify.table import (
    MODEL_CHECKS,
    REACTING_MODELS,
    REACTION_DATUM_NOTE,
    SPLIT_ENTHALPY_NOTE,
    Degeneracy,
    ModelChecks,
    Unit,
    _envelope_energy,
    _envelope_material,
)

if TYPE_CHECKING:
    from openflowsheet.orchestrator.region import LiftedSplit

__all__ = [
    "BAND_NOTE",
    "GAMMA_PHI_UNITS",
    "degeneracy",
    "registry_splits",
    "revision_checks",
    "split_checks",
]

#: The form's name: `verify.forms.form_of("wilson-ig-v2")`, which `verify.table.revision_checks`
#: dispatches here (I1b).
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
    provider: PropertyProvider,
    flows: tuple[float, ...],
    temperature: float,
    pressure: float,
    phase: Phase,
    context: EvaluationContext,
) -> tuple[bool, float, float] | str:
    """`(stable, tm, ε)`: the provider's verdict on `phase`, the other phase model's trial `tm`
    and the report's resolution; or the reason it decided nothing (`verify.column`'s rule)."""
    other: Phase = "VAPOR" if phase == "LIQUID" else "LIQUID"
    judge = getattr(provider, "stability", None)
    if judge is None:
        return "stability_unavailable"
    report: StabilityReport = judge(
        StreamState(n=flows, temperature=temperature, pressure=pressure), phase, context
    )
    distance = report.tm.get(other)
    if report.label not in (_STABLE, "UNSTABLE") or distance is None:
        return f"stability_{report.label.lower()}: {report.reason}"
    return report.label == _STABLE, distance, report.epsilon


def _admissibility(
    split: LiftedSplit,
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    note: str,
) -> CheckResult:
    """§4.8's admissibility under SYN-001's id for the split's branch."""
    name = f"{split.unit}.{split.stream}"
    vapor, liquid = _flows(state, split.vapor), _flows(state, split.liquid)
    temperature, pressure = state[split.temperature], state[split.pressure]
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
        verdict = _stability(provider, flows, temperature, pressure, phase, context)
        if isinstance(verdict, str):
            return unsupported(
                id=identifier, category="phase_admissibility", subject=split.stream, reason=verdict
            )
        verdicts.append(verdict)
    stable = all(verdict[0] for verdict in verdicts)
    # A two-phase branch also needs both totals at or above −τ_flow (§4.8).
    stable = stable and min(total_vapor, total_liquid) >= -tolerances["molar_flow"]
    least = min(verdicts, key=lambda verdict: verdict[1]) if verdicts else (True, 0.0, 0.0)
    return replace(
        evaluated(
            id=identifier,
            category="phase_admissibility",
            subject=split.stream,
            value=least[1],
            tolerance=least[2],
            independence_qualification=note + _SHARED_STABILITY,
        ),
        result="pass" if stable else "fail",
    )


def split_checks(
    split: LiftedSplit,
    components: Sequence[str],
    state: Mapping[str, float],
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    note: str,
    distance: float | None = None,
) -> list[CheckResult]:
    """§4.8 on one registry split under SYN-001's ids (`verify.table._split_checks`): a flowing
    degenerate split (`distance` its `δ`) has `.saturation` and its independent split
    `not_applicable`; any other has its admissibility and the fresh flash's comparison."""
    name = f"{split.unit}.{split.stream}"
    subject = split.stream
    if distance is not None:
        return [
            evaluated(
                id=f"phase_admissibility.{name}.saturation",
                category="phase_admissibility",
                subject=subject,
                value=distance,
                tolerance=tolerances["temperature"],
                reference=KIND_REFERENCE["temperature"],
                independence_qualification=note + BAND_NOTE,
            ),
            dormant(
                id=f"independent_split.{name}",
                category="independent_split",
                subject=subject,
                reason="temperature_degenerate",
            ),
        ]
    vapor, liquid = _flows(state, split.vapor), _flows(state, split.liquid)
    checks: list[CheckResult] = []
    if sum(vapor) + sum(liquid) == 0.0:
        checks.append(
            dormant(
                id=f"phase_admissibility.{name}", category="phase_admissibility", subject=subject
            )
        )
    else:
        checks.append(_admissibility(split, state, provider, context, tolerances, note))
    if all(flow == 0.0 for flow in _flows(state, split.feed)):
        checks.append(
            dormant(id=f"independent_split.{name}", category="independent_split", subject=subject)
        )
        return checks
    fresh_vapor, fresh_liquid = _fresh_split(provider, split, state, context)
    checks.append(
        evaluated(
            id=f"independent_split.{name}.total",
            category="independent_split",
            subject=subject,
            value=state[split.vapor_total] - sum(fresh_vapor.n),
            tolerance=tolerances["molar_flow"],
            reference=KIND_REFERENCE["molar_flow"],
            independence_qualification=note,
        )
    )
    for index, component in enumerate(components):
        by_vapor = vapor[index] - fresh_vapor.n[index]
        by_liquid = liquid[index] - fresh_liquid.n[index]
        checks.append(
            evaluated(
                id=f"independent_split.{name}.{component}",
                category="independent_split",
                subject=subject,
                value=by_vapor if abs(by_vapor) >= abs(by_liquid) else by_liquid,
                tolerance=tolerances["molar_flow"],
                reference=KIND_REFERENCE["molar_flow"],
                independence_qualification=note,
            )
        )
    return checks


def revision_checks(
    view: RevisionView,
    splits: Sequence[LiftedSplit],
    state: Mapping[str, float],
    *,
    provider: PropertyProvider,
    context: EvaluationContext,
    tolerances: Mapping[str, float],
    judged_at: Mapping[str, float] | None = None,
    owners: Mapping[str, str] | None = None,
) -> list[CheckResult]:
    """`verify.table.revision_checks`'s `DECLARED_MIXTURE` branch, argument for argument, with
    §4.8's registry splits: their lifted streams' enthalpies in the one map every energy check
    reads, and their `split_checks` before the declared streams' admissibility.

    `owners` is accepted for the same signature; the staged splits it resolves are not registry
    splits, and the column's rows are its own `ModelChecks` (as in the first pass)."""
    del owners
    if not composition_dependent(provider):
        raise VerifierError(
            f"gamma_phi_units needs a composition-dependent provider, not "
            f"{provider.describe().provider_id}"
        )
    at = state if judged_at is None else judged_at
    note = qualification(provider)
    reacting = any(i.model_id in REACTING_MODELS for i in view.instances)
    reaction_note = note + REACTION_DATUM_NOTE.format(
        convention=provider.describe().reference_convention
    )
    components = view.components
    declared = forms.declared_phases(view)
    degenerate = degeneracy(view, splits, at, provider, context)

    energy: list[CheckResult] = []
    enthalpy: dict[str, float] = {}
    for stream in view.streams:
        carried = stream_of(at, stream, components)
        if stream in degenerate.enthalpy:
            enthalpy[stream] = degenerate.enthalpy[stream]
        elif carried.is_dormant:
            enthalpy[stream] = 0.0
            energy.append(
                dormant(
                    id=f"energy_balance.enthalpy.{stream}",
                    category="energy_balance",
                    subject=stream,
                )
            )
        else:
            phase = declared[stream]
            # An unlifted stream's value is never judged: every check reading it is blocked.
            enthalpy[stream] = (
                0.0 if phase is None else forms.enthalpy_flow(provider, carried, phase, context)
            )

    units: list[tuple[Unit, ModelChecks | None]] = [
        (
            Unit(
                view=instance,
                state=at,
                enthalpy=enthalpy,
                tolerances=tolerances,
                energy_note=reaction_note if instance.model_id in REACTING_MODELS else note,
                provider=provider,
                context=context,
                notes=degenerate.notes,
                unlifted=degenerate.unlifted,
                components=tuple(components),
            ),
            MODEL_CHECKS.get(instance.model_id),
        )
        for instance in view.instances
    ]

    material: list[CheckResult] = []
    specification: list[CheckResult] = []
    own_admissibility: list[CheckResult] = []
    bounds: list[CheckResult] = bounds_checks(
        provider, state, streams=view.streams, components=components
    )
    for judged, entry in units:
        certified = judged if at is state else replace(judged, state=state)
        if entry is None:
            material.append(
                unsupported(
                    id=f"material_balance.{certified.id}.all",
                    category="material_balance",
                    subject=certified.id,
                    reason=f"model_unsupported({certified.view.model_id})",
                )
            )
            continue
        material += entry.material(certified, components)
        energy += entry.energy(judged, components)
        specification += entry.specification(certified, components)
        bounds += entry.bounds(certified, components)
        own_admissibility += entry.admissibility(judged, components)
    material += _envelope_material(view, state, tolerances)
    energy.append(
        _envelope_energy(
            view, at, enthalpy, tolerances, reaction_note if reacting else note, degenerate
        )
    )

    admissibility: list[CheckResult] = []
    for split in registry_splits(view, splits):
        admissibility += split_checks(
            split,
            components,
            at,
            provider,
            context,
            tolerances,
            note,
            degenerate.splits.get(split.unit),
        )
    admissibility += forms.stream_admissibility(view, declared, at, provider, context, note)
    admissibility += own_admissibility
    return [*material, *energy, *specification, *bounds, *admissibility]
