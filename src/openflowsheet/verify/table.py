"""The verifier's check table for revision-built flowsheets. T05 design note §4 (register R-046).

SYN-001 keeps its legacy check set (`checks.material_checks` and its siblings), ids and code
unchanged; a flowsheet built from a revision is judged by this table instead, keyed by model id.
The table reads **only** the state, the revision (through `parse_revision`'s view: ids, pins and
parameters — the declaration's inputs) and a fresh provider. It shares no row builder, causal
evaluator, kernel or cache with the solver (R-016): a balance here is a plain sum over stream
flows, an enthalpy a fresh flash of the stream's own `(n, T, P)` (`checks.enthalpy_flow`), and a
phase property a fresh `evaluate_phase`.

**Why a second set and not a rewrite of the first** (D4): every legacy id, order and value stays
protected by construction. The two are held together by a bitwise cross-validation on the
SYN-001-shaped revision (`tests/test_t05_w1d_verifier.py`): each legacy value equals its general
counterpart to the bit, at the root and at a non-root. That is why every formula below is written
out in the operation order §4.3 states — left to right, sums over ports, streams and instances
accumulated from `0.0` in declaration order — and must stay so. A sum over one stream's
components is `unit_checks._component_sum`, Python's `sum`, because that is what the legacy
builders call (see its docstring).

**Order** is category-major, as the legacy engine's: material, energy, specification, bounds,
then admissibility and the independent split. Within a category: instances in declaration order,
each model's items in its entry's order, components in component order; then the flowsheet rows.
A model id without an entry yields one `unsupported` check and caps the verdict at `UNVERIFIED`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from types import ModuleType
from typing import TYPE_CHECKING, Any, NamedTuple

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import RevisionView
from openflowsheet.thermo import (
    Phase,
    PropertyProvider,
)
from openflowsheet.verify import (
    CheckResult,
    dormant,
    forms,
    pr_c1,
    unsupported,
)
from openflowsheet.verify.checks import (
    COMPONENTS,
    bounds_checks,
    enthalpy_flow,
    qualification,
    stream_of,
)
from openflowsheet.verify.flowsheet_rows import (
    REACTING_MODELS,
    _envelope_energy,
    _envelope_material,
)
from openflowsheet.verify.split_checks import (
    Degeneracy,
    _declared_port_checks,
    _split_checks,
    degeneracy,
)
from openflowsheet.verify.table_kit import REACTION_DATUM_NOTE, ModelChecks, Unit
from openflowsheet.verify.unit_checks import MODEL_CHECKS

if TYPE_CHECKING:
    from openflowsheet.models.lifted import LiftedSplit

__all__ = [
    "revision_checks",
    "revision_phase_branch",
]


# -- the check set -----------------------------------------------------------------------------


def _thermal_rows() -> ModuleType:
    """`verify.thermal`, imported at the call (lazy since it imported this module; it imports
    only `verify.table_kit` now)."""
    from openflowsheet.verify import thermal  # noqa: PLC0415

    return thermal


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
    """§4.3: the table's check set at `state`, category-major, for a revision-built flowsheet.

    Everything but the residual rows, the alias certificates and the derivative witness, which
    `verify_revision` runs as SYN-001's `_run_checks` and `_issue` do. `provider` is fresh.

    A temperature-degenerate split or stream (T05b spec §9.1–§9.2, `degeneracy`) is judged by
    what the state carries: its enthalpy in the one map every energy and declared-port check
    reads, its admissibility `.saturation`, its independent split `not_applicable`.

    `judged_at` (ADR 0013 D1; K04-F9 spec §5.1) is where the fresh-flash categories are
    evaluated — the energy balances and the enthalpy map they read, the splits' admissibility and
    independent split, the declared ports, and the degeneracy routing that selects among their
    forms; material balances, specifications and bounds stay at `state`. `None` is `state`.

    `owners` (S11 design §10.11): a staged split's key → its instance (`degeneracy`); `None`
    when no instance is staged. A model's own admissibility rows (`ModelChecks.admissibility`)
    follow the declared ports on every form; the form's own rows come from
    `_mixture_admissibility`, `_pr_admissibility` or `_syn_admissibility`."""
    at = state if judged_at is None else judged_at
    note = qualification(provider)
    reacting = any(i.model_id in REACTING_MODELS for i in view.instances)
    reaction_note = note + REACTION_DATUM_NOTE.format(
        convention=provider.describe().reference_convention
    )
    components = view.components
    # S11 design §4.6 (ADR 0050 D5): the form is resolved from the basis. M02 design note §14.2
    # B15: a `pr-c1-v1` revision takes `verify.pr_c1`'s forms at the sites below, SYN-001's runs
    # SYN-001's lines, and every other basis the declared-phase mixture form (`verify.forms`).
    form = forms.form_of(view.basis.provider_id)
    if form == forms.GAMMA_PHI_UNITS:
        # Units design §4.8 (I1b): `wilson-ig-v2` revisions take the γ–φ form, which imports this
        # module.
        from openflowsheet.verify import gamma_phi_units  # noqa: PLC0415

        return gamma_phi_units.revision_checks(
            view,
            splits,
            state,
            provider=provider,
            context=context,
            tolerances=tolerances,
            judged_at=judged_at,
            owners=owners,
        )
    pr = form == forms.PR
    mixture = form == forms.DECLARED_MIXTURE
    declared = forms.declared_phases(view) if mixture else {}
    saturated = (
        _saturated_outlets(view) if mixture and forms.pure_fluid_provider(provider) else frozenset()
    )
    if mixture:
        degenerate = _mixture_degeneracy(view, at, declared, saturated)
    elif pr:
        degenerate = Degeneracy()
    else:
        degenerate = degeneracy(view, splits, at, provider, context, tolerances, owners)

    enthalpy, energy = _stream_enthalpies(
        view, at, _Routing(pr, mixture, declared, saturated, degenerate), provider, context
    )

    # Each instance is read twice when the two points differ: its energy rows at `at`, its
    # material, specification and bounds rows at `state`.
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

    judging = _Judging(at, provider, context, tolerances, note)
    if mixture:
        admissibility = _mixture_admissibility(view, declared, saturated, judging)
    elif pr:
        admissibility = _pr_admissibility(view, splits, judging)
    else:
        admissibility = _syn_admissibility(view, splits, enthalpy, degenerate, judging)
    return [*material, *energy, *specification, *bounds, *admissibility, *own_admissibility]


def _saturated_outlets(view: RevisionView) -> frozenset[str]:
    """Units design §4.8 (I1b): the streams at the outlet ports of `thermal.*` units that declare
    no phase (`vapor_liquid`). On a pure-fluid basis each is saturated (ADR 0051 D1; L-TH-2),
    read from its carried split by `verify.thermal` (`_mixture_degeneracy` handles the other
    streams without a declared phase)."""
    return frozenset(
        stream
        for instance in view.instances
        if instance.model_id.startswith("thermal.")
        for port, streams in instance.ports.items()
        if instance.directions.get(port) == "outlet" and instance.phases.get(port) is None
        for stream in streams
    )


def _mixture_degeneracy(
    view: RevisionView,
    at: Mapping[str, float],
    declared: Mapping[str, Phase | None],
    saturated: frozenset[str],
) -> Degeneracy:
    """The declared-mixture form's `Degeneracy` at `at`: no bands. Each `saturated` stream gets
    `verify.thermal`'s carried-split note; a flowing stream without a declared phase in
    `declared` that is not saturated stays unlifted (its checks blocked; S11.A17)."""
    return Degeneracy(
        notes={
            stream: _thermal_rows().CARRIED_SPLIT_NOTE.format(stream=stream) for stream in saturated
        },
        unlifted=frozenset(
            stream
            for stream, phase in declared.items()
            if phase is None
            and stream not in saturated
            and not stream_of(at, stream, view.components).is_dormant
        ),
    )


class _Routing(NamedTuple):
    """How the revision's form reads its streams' enthalpies (S11 design §4.6; M02 design note
    §14.2 B15; units design §4.8), as revision_checks routes them."""

    #: A `pr-c1-v1` basis: `verify.pr_c1`'s enthalpy flow.
    pr: bool
    #: The declared-phase mixture form (`verify.forms`).
    mixture: bool
    #: Each stream's declared phase (`forms.declared_phases`); empty outside the mixture form.
    declared: Mapping[str, Phase | None]
    #: The saturated `thermal.*` outlets (`_saturated_outlets`); empty unless the mixture form
    #: runs on a pure-fluid basis.
    saturated: frozenset[str]
    #: The streams whose enthalpy the state carries instead; only `.enthalpy` is read.
    degenerate: Degeneracy


def _stream_enthalpies(
    view: RevisionView,
    at: Mapping[str, float],
    routing: _Routing,
    provider: PropertyProvider,
    context: EvaluationContext,
) -> tuple[dict[str, float], list[CheckResult]]:
    """The one enthalpy map every energy and declared-port check reads, at `at`, and the
    `energy_balance.enthalpy.<S>` dormant rows of the dormant streams, in `view.streams` order.

    A stream in `routing.degenerate.enthalpy` takes that value; a dormant one `0.0`; otherwise the
    form's enthalpy flow: PR-C1's, the mixture form's (a saturated outlet's from its carried
    split, an unlifted stream's `0.0`, any other in its declared phase), or SYN-001's."""
    energy: list[CheckResult] = []
    enthalpy: dict[str, float] = {}
    for stream in view.streams:
        carried = stream_of(at, stream, view.components)
        if stream in routing.degenerate.enthalpy:
            enthalpy[stream] = routing.degenerate.enthalpy[stream]
        elif carried.is_dormant:
            enthalpy[stream] = 0.0
            energy.append(
                dormant(
                    id=f"energy_balance.enthalpy.{stream}",
                    category="energy_balance",
                    subject=stream,
                )
            )
        elif routing.pr:
            enthalpy[stream] = pr_c1.enthalpy_flow(provider, carried, context, view.components)
        elif routing.mixture:
            phase = routing.declared[stream]
            if stream in routing.saturated:
                enthalpy[stream] = _thermal_rows().saturated_enthalpy(
                    provider, at, stream, context, view.components
                )
            else:
                # An unlifted stream's value is never judged: every check reading it is blocked.
                enthalpy[stream] = (
                    0.0 if phase is None else forms.enthalpy_flow(provider, carried, phase, context)
                )
        else:
            enthalpy[stream] = enthalpy_flow(provider, carried, context)
    return enthalpy, energy


class _Judging(NamedTuple):
    """Where and with what revision_checks judges the fresh-flash categories (ADR 0013 D1), in
    the order the admissibility checks take them."""

    #: The point judged (`judged_at`, or `state` when it is `None`).
    at: Mapping[str, float]
    #: The fresh provider and its evaluation context.
    provider: PropertyProvider
    context: EvaluationContext
    tolerances: Mapping[str, float]
    #: The provider's qualification note (`checks.qualification`).
    note: str


def _mixture_admissibility(
    view: RevisionView,
    declared: Mapping[str, Phase | None],
    saturated: frozenset[str],
    judging: _Judging,
) -> list[CheckResult]:
    """The declared-mixture form's admissibility rows: each stream's in its `declared` phase
    (`forms.stream_admissibility`), then, when any outlet is `saturated`, `verify.thermal`'s
    saturated-stream rows."""
    at, provider, context, tolerances, note = judging
    admissibility: list[CheckResult] = []
    admissibility += forms.stream_admissibility(view, declared, at, provider, context, note)
    if saturated:
        admissibility += _thermal_rows().saturated_stream_checks(
            view, at, provider, context, tolerances, note
        )
    return admissibility


def _pr_admissibility(
    view: RevisionView, splits: Sequence[LiftedSplit], judging: _Judging
) -> list[CheckResult]:
    """The `pr-c1-v1` form's admissibility rows (M02 design note §14.2 B15): `verify.pr_c1`'s
    split checks in `splits` order, then its declared-port checks."""
    at, provider, context, tolerances, note = judging
    admissibility: list[CheckResult] = []
    for split in splits:
        admissibility += pr_c1.split_checks(
            split, view.components, at, provider, context, tolerances, note
        )
    admissibility += pr_c1.declared_port_checks(
        view,
        at,
        provider,
        context,
        note,
        {model: entry.declared_ports for model, entry in MODEL_CHECKS.items()},
    )
    return admissibility


def _syn_admissibility(
    view: RevisionView,
    splits: Sequence[LiftedSplit],
    enthalpy: Mapping[str, float],
    degenerate: Degeneracy,
    judging: _Judging,
) -> list[CheckResult]:
    """SYN-001's form's admissibility rows: each split's admissibility and independent split
    (`_split_checks`, in `splits` order, routed by `degenerate`), then the declared ports, which
    read `enthalpy`."""
    at, provider, context, tolerances, note = judging
    admissibility: list[CheckResult] = []
    for split in splits:
        admissibility += _split_checks(
            split,
            view.components,
            at,
            provider,
            context,
            tolerances,
            note,
            degenerate.splits.get(split.unit),
            unresolved=split.unit in degenerate.unresolved,
        )
    admissibility += _declared_port_checks(
        view, at, enthalpy, provider, context, tolerances, note, degenerate
    )
    return admissibility


def revision_phase_branch(
    state: Mapping[str, float],
    streams: Sequence[str],
    splits: Sequence[LiftedSplit],
    *,
    components: Sequence[str] = COMPONENTS,
) -> dict[str, Any]:
    """§4.2: every stream's regime, and each lifted split read from the state, keyed
    `<unit>:<stream>`; `components` the order a stream's flows are read in (the revision's)."""
    branch: dict[str, Any] = {
        stream: "ZERO_FLOW" if stream_of(state, stream, components).is_dormant else "FLOWING"
        for stream in streams
    }
    for split in splits:
        branch[f"{split.unit}:{split.stream}"] = {
            "vapor_total": state[split.vapor_total],
            "liquid_total": state[split.liquid_total],
            "vapor": [state[column] for column in split.vapor],
            "liquid": [state[column] for column in split.liquid],
        }
    return branch
