"""A read-only view of a solved flowsheet's structure, for the assessment (E01 design §4.2.1).

The assessment reads a flowsheet; it never changes one (ADR 0052 D1). `view_of` adapts the two
hosts that exist — a revision flowsheet (`RevisionFlowsheet`) and SYN-001's (`Syn001Flowsheet`) —
to one protocol: the components, the property provider and evaluation context the host was bound
with, its units in declaration order with their wiring and pinned inputs, and the molar masses of
the bound component basis. Nothing here evaluates the flowsheet.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import UnitModel, Wiring
from openflowsheet.models.revision_flowsheet import (
    ComponentBasis,
    RevisionFlowsheet,
    selectable_bases,
)
from openflowsheet.models.syn001.flowsheet import WIRING as SYN001_WIRING
from openflowsheet.models.syn001.flowsheet import Syn001Flowsheet
from openflowsheet.thermo import PropertyProvider

__all__ = ["FlowsheetView", "UnitRef", "view_of"]


@dataclass(frozen=True)
class UnitRef:
    """One unit as the assessment sees it.

    `ports` maps each wired port to its stream ids (the host's wiring); `parameters` are the
    unit's pinned inputs by their ids (its `Contribution.parameters`); `structure` is the unit
    object itself, for the family that sizes it (its configuration fields, e.g. a column's stage
    count). Nothing reads `structure` to evaluate anything.
    """

    unit_id: str
    model_id: str
    ports: Mapping[str, tuple[str, ...]]
    parameters: Mapping[str, float]
    structure: Any


class FlowsheetView(Protocol):
    @property
    def components(self) -> tuple[str, ...]: ...

    @property
    def provider(self) -> PropertyProvider: ...

    @property
    def context(self) -> EvaluationContext: ...

    def units(self) -> tuple[UnitRef, ...]: ...

    def molar_masses(self) -> Mapping[str, float]: ...


@dataclass(frozen=True)
class _View:
    components: tuple[str, ...]
    provider: PropertyProvider
    context: EvaluationContext
    unit_refs: tuple[UnitRef, ...]
    masses: Mapping[str, float]

    def units(self) -> tuple[UnitRef, ...]:
        return self.unit_refs

    def molar_masses(self) -> Mapping[str, float]:
        return self.masses


def _unit_ref(unit: UnitModel, wiring: Wiring, components: tuple[str, ...]) -> UnitRef:
    contribution = unit.contribute(wiring, components)
    return UnitRef(
        unit_id=unit.unit_id,
        model_id=unit.model_id,
        ports=MappingProxyType({port: tuple(ids) for port, ids in wiring.streams.items()}),
        parameters=MappingProxyType({k: float(v) for k, v in contribution.parameters.items()}),
        structure=unit,
    )


def _basis(provider: PropertyProvider, components: tuple[str, ...]) -> ComponentBasis:
    """The bound basis: the selectable one with the provider's id over the same component set.

    A host bound on a provider no basis names is a defect of the binding, not of the assessment,
    and is refused loudly: a molar mass is never guessed.
    """
    provider_id = provider.describe().provider_id
    for basis in selectable_bases():
        if basis.provider_id == provider_id and set(basis.components) == set(components):
            return basis
    raise ValueError(
        f"no component basis of provider {provider_id!r} covers components {list(components)}; "
        "the assessment cannot state molar masses for this flowsheet"
    )


def view_of(flowsheet: RevisionFlowsheet | Syn001Flowsheet) -> FlowsheetView:
    """The assessment's view of a bound flowsheet."""
    if isinstance(flowsheet, RevisionFlowsheet):
        wiring: Mapping[str, Wiring] = flowsheet.wiring
    elif isinstance(flowsheet, Syn001Flowsheet):
        wiring = SYN001_WIRING
    else:
        raise TypeError(f"no assessment view of a {type(flowsheet).__name__}")
    components = tuple(flowsheet.components)
    basis = _basis(flowsheet.provider, components)
    refs = tuple(_unit_ref(unit, wiring[unit.unit_id], components) for unit in flowsheet.units())
    return _View(
        components=components,
        provider=flowsheet.provider,
        context=flowsheet.context,
        unit_refs=refs,
        masses=MappingProxyType({c: float(basis.molecular_weights[c]) for c in components}),
    )
