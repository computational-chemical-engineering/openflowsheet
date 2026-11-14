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
from typing import TYPE_CHECKING, Any

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.revision_flowsheet import RevisionView
from openflowsheet.thermo import (
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
from openflowsheet.verify.flowsheet_rows import EXTERNAL_DUTY_MODELS as EXTERNAL_DUTY_MODELS
from openflowsheet.verify.flowsheet_rows import FEED_MODELS as FEED_MODELS
from openflowsheet.verify.flowsheet_rows import KINETIC_CSTR as KINETIC_CSTR
from openflowsheet.verify.flowsheet_rows import PRODUCT_MODELS as PRODUCT_MODELS
from openflowsheet.verify.flowsheet_rows import REACTING_MODELS as REACTING_MODELS
from openflowsheet.verify.flowsheet_rows import STAGED_DUTY_MODELS as STAGED_DUTY_MODELS
from openflowsheet.verify.flowsheet_rows import WORK_MODELS as WORK_MODELS
from openflowsheet.verify.flowsheet_rows import _envelope_energy, _envelope_material
from openflowsheet.verify.split_checks import Degeneracy as Degeneracy
from openflowsheet.verify.split_checks import _declared_port_checks, _split_checks
from openflowsheet.verify.split_checks import _phase_enthalpy as _phase_enthalpy
from openflowsheet.verify.split_checks import degeneracy as degeneracy
from openflowsheet.verify.table_kit import DECLARED_ENTHALPY_NOTE as DECLARED_ENTHALPY_NOTE
from openflowsheet.verify.table_kit import REACTION_DATUM_NOTE as REACTION_DATUM_NOTE
from openflowsheet.verify.table_kit import SPLIT_ENTHALPY_NOTE as SPLIT_ENTHALPY_NOTE
from openflowsheet.verify.table_kit import UNRESOLVED_ENTHALPY_NOTE as UNRESOLVED_ENTHALPY_NOTE
from openflowsheet.verify.table_kit import ModelChecks as ModelChecks
from openflowsheet.verify.table_kit import Rule as Rule
from openflowsheet.verify.table_kit import Unit as Unit
from openflowsheet.verify.table_kit import blocked_check as blocked_check
from openflowsheet.verify.table_kit import stream_notes as stream_notes
from openflowsheet.verify.unit_checks import MODEL_CHECKS as MODEL_CHECKS
from openflowsheet.verify.unit_checks import _c1_flash_material as _c1_flash_material
from openflowsheet.verify.unit_checks import _c1_reactor_material as _c1_reactor_material
from openflowsheet.verify.unit_checks import _feed_specification as _feed_specification
from openflowsheet.verify.unit_checks import _flash_energy as _flash_energy
from openflowsheet.verify.unit_checks import _flash_specification as _flash_specification
from openflowsheet.verify.unit_checks import _heater_energy as _heater_energy
from openflowsheet.verify.unit_checks import _heater_specification as _heater_specification
from openflowsheet.verify.unit_checks import _mixer_energy as _mixer_energy
from openflowsheet.verify.unit_checks import _mixer_material as _mixer_material
from openflowsheet.verify.unit_checks import _pump_material as _pump_material
from openflowsheet.verify.unit_checks import _reactor_energy as _reactor_energy
from openflowsheet.verify.unit_checks import _splitter_energy as _splitter_energy
from openflowsheet.verify.unit_checks import _splitter_material as _splitter_material
from openflowsheet.verify.unit_checks import _splitter_specification as _splitter_specification

if TYPE_CHECKING:
    from openflowsheet.orchestrator.region import LiftedSplit

__all__ = [
    "DECLARED_ENTHALPY_NOTE",
    "MODEL_CHECKS",
    "REACTION_DATUM_NOTE",
    "SPLIT_ENTHALPY_NOTE",
    "UNRESOLVED_ENTHALPY_NOTE",
    "Degeneracy",
    "ModelChecks",
    "Unit",
    "degeneracy",
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
    follow the declared ports on every form."""
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
    # Units design §4.8 (I1b): on a pure-fluid basis a `vapor_liquid` outlet of a `thermal.*` unit
    # is saturated (ADR 0051 D1; L-TH-2), read from its carried split by `verify.thermal`; any other
    # stream without a declared phase stays unlifted (S11.A17).
    saturated = (
        frozenset(
            stream
            for instance in view.instances
            if instance.model_id.startswith("thermal.")
            for port, streams in instance.ports.items()
            if instance.directions.get(port) == "outlet" and instance.phases.get(port) is None
            for stream in streams
        )
        if mixture and forms.pure_fluid_provider(provider)
        else frozenset()
    )
    if mixture:
        # No bands; a flowing stream without a declared phase is unlifted (its checks blocked).
        degenerate = Degeneracy(
            notes={
                stream: _thermal_rows().CARRIED_SPLIT_NOTE.format(stream=stream)
                for stream in saturated
            },
            unlifted=frozenset(
                stream
                for stream, phase in declared.items()
                if phase is None
                and stream not in saturated
                and not stream_of(at, stream, components).is_dormant
            ),
        )
    else:
        degenerate = (
            Degeneracy()
            if pr
            else degeneracy(view, splits, at, provider, context, tolerances, owners)
        )

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
        elif pr:
            enthalpy[stream] = pr_c1.enthalpy_flow(provider, carried, context, components)
        elif mixture:
            phase = declared[stream]
            if stream in saturated:
                enthalpy[stream] = _thermal_rows().saturated_enthalpy(
                    provider, at, stream, context, components
                )
            else:
                # An unlifted stream's value is never judged: every check reading it is blocked.
                enthalpy[stream] = (
                    0.0 if phase is None else forms.enthalpy_flow(provider, carried, phase, context)
                )
        else:
            enthalpy[stream] = enthalpy_flow(provider, carried, context)

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

    admissibility: list[CheckResult] = []
    if mixture:
        admissibility += forms.stream_admissibility(view, declared, at, provider, context, note)
        if saturated:
            admissibility += _thermal_rows().saturated_stream_checks(
                view, at, provider, context, tolerances, note
            )
        admissibility += own_admissibility
        return [*material, *energy, *specification, *bounds, *admissibility]
    if pr:
        for split in splits:
            admissibility += pr_c1.split_checks(
                split, components, at, provider, context, tolerances, note
            )
        admissibility += pr_c1.declared_port_checks(
            view,
            at,
            provider,
            context,
            note,
            {model: entry.declared_ports for model, entry in MODEL_CHECKS.items()},
        )
        admissibility += own_admissibility
        return [*material, *energy, *specification, *bounds, *admissibility]
    for split in splits:
        admissibility += _split_checks(
            split,
            components,
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
    admissibility += own_admissibility
    return [*material, *energy, *specification, *bounds, *admissibility]


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
