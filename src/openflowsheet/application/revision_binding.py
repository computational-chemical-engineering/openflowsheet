"""Binding a `ProcessRevision` to a revision-built flowsheet. T05 design note §1.3, §1.4.

`application.binding` binds the registered SYN-001 revisions to `Syn001Flowsheet` by topology and
stays as it is. This module builds the flowsheet *from* the revision: every instance's unit is
constructed by the builder registered for its model id (`MODEL_BUILDERS`, `model_builders`),
from the instance's parameters and pins read by §1.3's rules, with no default (D5). Each builder
returns the unit and its `configuration` — the part of the revision that selects expressions
without changing ids, which the flowsheet's label digests (register R-047).

**A pin is consumed when its builder reads it.** The builder is handed the instance view with a
pin mapping that records every value read; a pin nobody read is a specification the flowsheet
would silently ignore, and is refused `specification_unconsumed(<spec id>)` (R5). Membership
tests (`in`) do not count as a read.

Every refusal is an `Unbound` with R-022's kind and a stable code, never an exception: a revision
the rules cannot read may be perfectly fine, and says so as `unsupported`.

**What a builder reads is declared, once, in its `ModelSignature`** (T07 design note §4.2
`list_models`, §15 W5c): the model's ports, its required and zero-only parameters, the pins it
always reads and the one-of specification choices. The builders take those lists from
`MODEL_SIGNATURES` rather than from literals, so what `list_models` reports is what binding reads;
the signature constructs nothing.

The signatures, the pin readers and the `Builder` and `Configuration` types live in
`model_signatures`, the builder catalogue in `model_builders` (S17 R3); this module holds the
binder (`bind_revision_flowsheet`), the basis and provider selection, and the refusals, and
re-exports both modules' public names, so `revision_binding.<name>` imports keep working.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import partial
from typing import TYPE_CHECKING, Any, Final, overload

from openflowsheet.adapters import variants
from openflowsheet.application.binding_common import Unbound, _column_owners
from openflowsheet.application.model_builders import MODEL_BUILDERS as MODEL_BUILDERS
from openflowsheet.application.model_builders import SurrogateResolver as SurrogateResolver
from openflowsheet.application.model_builders import _c1_reactor_surrogate as _c1_reactor_surrogate
from openflowsheet.application.model_builders import _c1_reactor_surrogate_of
from openflowsheet.application.model_builders import resolve_surrogate as resolve_surrogate
from openflowsheet.application.model_signatures import (
    _ADIABATIC_MIXER,
    _C1_ADIABATIC_MIXER,
    _C1_FEED_SOURCE,
    _C1_PRODUCT_SINK,
    _C1_STREAM_SPLITTER,
    _C1_TP_FLASH,
    _C1_TP_HEATER,
    _COOLPROP,
    _FEED_SOURCE,
    _IAPWS95,
    _LIQUID_PUMP,
    _PH_FLASH,
    _PRODUCT_SINK,
    _STREAM_SPLITTER,
    _THERMAL_FLASH,
    _THERMAL_HEATER,
    _THERMAL_MIXER,
    _THERMAL_VALVE,
    _TP_FLASH,
    _TP_HEATER,
    _VALVE,
    _WILSON,
    _named_first,
)
from openflowsheet.application.model_signatures import _COLUMN as _COLUMN
from openflowsheet.application.model_signatures import LIST_MODELS_LINE as LIST_MODELS_LINE
from openflowsheet.application.model_signatures import MODEL_BASES as MODEL_BASES
from openflowsheet.application.model_signatures import MODEL_SIGNATURES as MODEL_SIGNATURES
from openflowsheet.application.model_signatures import ROUTING_MODELS as ROUTING_MODELS
from openflowsheet.application.model_signatures import S11_BASES as S11_BASES
from openflowsheet.application.model_signatures import TARGET_PATH_HEADING as TARGET_PATH_HEADING
from openflowsheet.application.model_signatures import Builder as Builder
from openflowsheet.application.model_signatures import Configuration as Configuration
from openflowsheet.application.model_signatures import Encoding as Encoding
from openflowsheet.application.model_signatures import ModelSignature as ModelSignature
from openflowsheet.application.model_signatures import PinColumn as PinColumn
from openflowsheet.application.model_signatures import PinQuantity as PinQuantity
from openflowsheet.application.model_signatures import SpecificationChoice as SpecificationChoice
from openflowsheet.application.model_signatures import _columns as _columns
from openflowsheet.application.model_signatures import instance_contract as instance_contract
from openflowsheet.application.model_signatures import pin_encodings as pin_encodings
from openflowsheet.application.model_signatures import render_encoding as render_encoding
from openflowsheet.application.model_signatures import target_path_table as target_path_table
from openflowsheet.canonical import document_sha256, first_noncanonical
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.process import Connection, ProcessGraph
from openflowsheet.graph.trace import Declaration
from openflowsheet.models import SpecificationError, UnitModel, flow_id, pressure_id, temperature_id
from openflowsheet.models.revision_flowsheet import (
    SYN001_BASIS,
    ComponentBasis,
    InputMapping,
    InstanceView,
    RevisionError,
    RevisionFlowsheet,
    configuration_sha256,
    parse_revision,
    pin_specifications,
    selectable_bases,
)
from openflowsheet.models.syn001 import PROVIDER_ID as SYN001_PROVIDER_ID
from openflowsheet.models.thermal import machines as thermal_machines
from openflowsheet.orchestrator.splits import split_owners, staged_units
from openflowsheet.studies.surrogate import reactor as c1_surrogate
from openflowsheet.thermo import PropertyProvider
from openflowsheet.thermo.pr_c1 import PROVIDER_ID as C1_PROVIDER_ID

if TYPE_CHECKING:
    from openflowsheet.orchestrator.budget import PropertyMeter

__all__ = [
    "MODEL_BASES",
    "MODEL_BUILDERS",
    "MODEL_SIGNATURES",
    "SELECTABLE_BASES",
    "Builder",
    "SurrogateResolver",
    "Encoding",
    "ModelSignature",
    "PinColumn",
    "RevisionBinding",
    "SpecificationChoice",
    "basis_provider",
    "bind_revision_flowsheet",
    "instance_contract",
    "provider_for",
    "pin_encodings",
    "render_encoding",
    "resolve_surrogate",
    "specification_rows",
    "target_path_table",
]

#: The context a revision-built flowsheet's units are constructed with (§1.4).
_CONTEXT = EvaluationContext(
    model_version="revision-structural", constants_sha256="0" * 64, phase_signature=None
)


@dataclass(frozen=True)
class RevisionBinding:
    """A revision-built flowsheet with what the structural layer and the verifier need."""

    flowsheet: RevisionFlowsheet
    #: `flowsheet.spec()`, computed once.
    spec: ProblemSpec
    graph: ProcessGraph
    #: Row id -> the instance that authored it, from each unit's own contribution (T01 A15).
    row_units: Mapping[str, str]
    #: ADR 0002's `document_sha256` of the revision this binding was built from.
    revision_sha256: str
    #: How the revision's inputs were read (T06 spec §8.5): `parse_revision`'s record, which is
    #: also what `verify_revision` reads. Empty for every registered revision.
    input_mapping: InputMapping = field(default_factory=InputMapping)
    #: Instance id -> {pinned column -> the specification that pins it}: what each builder was
    #: handed and consumed, recorded where the units are built (M06 design note §4.1, R3). The
    #: first specification in document order names a column two equal specifications pin, as
    #: `specification_unconsumed` and `specification_conflict` name it. Read only by
    #: `specification_rows`, for `inspect_structure`'s index; never by the structural analysis.
    specification_pins: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    #: Instance id -> the SurrogateManifest its `model.artifact_ref` resolved to, hash- and
    #: checker-verified by the binder (M04 spec §8.2): what the certificate's
    #: `SURROGATE-DOMAIN:<unit>` check and `surrogate_model` limitation read (spec §8.6). Empty
    #: when the revision binds no surrogate.
    surrogate_manifests: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


def specification_rows(binding: RevisionBinding, declaration: Declaration) -> dict[str, str]:
    """Row id -> the revision specification the row realises, on `revision_eo` (M06 design note
    §4.1): a specification row (`TracedRow.is_specification_row`) whose one column is a pin its
    authoring instance consumed. Joined on the row's traced incidence and the binder's own
    routing record, never on id text (R-019). For `inspect_structure`'s index only: the route's
    analysis is given no specification ids on `revision_eo`, and its report does not change."""
    attributed: dict[str, str] = {}
    for row_id in declaration.row_ids:
        row = declaration.rows[row_id]
        if row.unit is None or row.coefficients is None or not row.is_specification_row:
            continue
        (column,) = row.coefficients
        specification = binding.specification_pins.get(row.unit, {}).get(column)
        if specification is not None:
            attributed[row_id] = specification
    return attributed


# -- encodings: how a revision pins what a builder reads (T07 ruling round 6, B2) ----------------


def _first_encodings(
    view: InstanceView, signature: ModelSignature, components: Sequence[str]
) -> str:
    """Each of `signature`'s pins with its first encoding, then each choice's options."""
    parts = [_named_first(view, signature, pin, components) for pin in signature.pins]
    parts += [
        f"one of {choice.name} ("
        + "; ".join(_named_first(view, signature, option, components) for option in choice.options)
        + ")"
        for choice in signature.choices
    ]
    return "; ".join(parts) if parts else "no pinned column"


def _unconsumed_hint(view: InstanceView, column: str, components: Sequence[str]) -> str | None:
    """`specification_unconsumed(<id>)`'s hint: what the instance's model reads instead; `None`
    for a model with no signature."""
    signature = MODEL_SIGNATURES.get(view.model_id)
    if signature is None:
        return None
    return (
        f"{view.unit_id} ({signature.model_id}) does not read column {column}; it reads "
        f"{_first_encodings(view, signature, components)}"
    )


def _instance_targets(signature: ModelSignature) -> str:
    """What an instance of `signature`'s model takes as a target path: the distinct instance-form
    encodings of its pins and options, then `parameters.<name>` for its required and zero-only
    parameters (a `specification_unsupported` hint on an instance target)."""
    paths: dict[str, str] = {}
    for pin in (*signature.pins, *(o for c in signature.choices for o in c.options)):
        for encoding in pin_encodings(signature, pin):
            if encoding.object_type == "instance":
                paths.setdefault(
                    encoding.path, f"{encoding.path} ({encoding.kind}, {encoding.si_unit})"
                )
    names = [*paths.values(), *(f"parameters.{p}" for p in (*signature.required, *signature.zero))]
    if not names:
        return "takes no target path"
    return "takes path " + (
        names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"
    )


# -- a C1 reactor's surrogate manifest (M04 spec §8.2; the builders are in `model_builders`) -------


def _resolve_surrogate(
    instance: InstanceView, surrogates: SurrogateResolver | None
) -> Mapping[str, Any] | None:
    """M04 spec §8.2: the instance's SurrogateManifest, or `None` (`resolve_surrogate`)."""
    return resolve_surrogate(instance.model_version, instance.model_artifact_ref, surrogates)


# -- the binder: target paths, bases, admissibility, `bind_revision_flowsheet` ---------------------

#: Model id -> what an instance of it takes as a target path, for `parse_revision`'s
#: `specification_unsupported` hint on an instance target (ruling round 6, B2).
_INSTANCE_TARGETS: Final[Mapping[str, str]] = {
    model_id: _instance_targets(signature) for model_id, signature in MODEL_SIGNATURES.items()
}


#: The model performing the same function on the other basis, both ways (R-288's hint): the six
#: C1 units are their SYN-001 namesakes (design note §8; W27's R-283). The C1 reactors have none.
_NAMESAKES: Final[tuple[tuple[str, str], ...]] = tuple(
    (syn001_unit.model_id, c1_unit.model_id)
    for syn001_unit, c1_unit in (
        (_FEED_SOURCE, _C1_FEED_SOURCE),
        (_ADIABATIC_MIXER, _C1_ADIABATIC_MIXER),
        (_TP_HEATER, _C1_TP_HEATER),
        (_TP_FLASH, _C1_TP_FLASH),
        (_STREAM_SPLITTER, _C1_STREAM_SPLITTER),
        (_PRODUCT_SINK, _C1_PRODUCT_SINK),
    )
)
_SAME_FUNCTION: Final[Mapping[str, str]] = {
    **dict(_NAMESAKES),
    **{c1_id: syn001_id for syn001_id, c1_id in _NAMESAKES},
}


class _SelectableBases(Sequence[ComponentBasis]):
    """`selectable_bases()` read per access: the C1 basis reads the records on first use, never at
    import (R-219), and this holds no state (T07 G20)."""

    @overload
    def __getitem__(self, index: int) -> ComponentBasis: ...
    @overload
    def __getitem__(self, index: slice) -> Sequence[ComponentBasis]: ...
    def __getitem__(self, index: int | slice) -> ComponentBasis | Sequence[ComponentBasis]:
        return selectable_bases()[index]

    def __len__(self) -> int:
        return len(selectable_bases())

    def __iter__(self) -> Iterator[ComponentBasis]:
        # One tuple per iteration, not one per index (S11 design §4.2).
        return iter(selectable_bases())


#: Every `ComponentBasis` the binder selects a revision's provider for (`component_basis`), in a
#: fixed order, SYN-001's first (W27-R63; R-288). `basis_provider(b)` describes `b`'s provider id
#: and components.
SELECTABLE_BASES: Final[Sequence[ComponentBasis]] = _SelectableBases()


def _basis_refusal(model_id: str, basis: ComponentBasis) -> Unbound:
    """R-288: `model_id` does not bind on `basis`. The hint names the bases it binds on and, when
    there is one, the model of the same function on `basis`.

    S11.A13 (restated, R-841): on every basis the hint names every basis the model binds on
    ("bases" when there is more than one), and appends `_UNADMITTED`'s reason where it has one.
    A syn001/c1 hint is the base's byte for byte for a model whose bases S11 does not change."""
    bases = MODEL_BASES[model_id]
    own = ", ".join(sorted(bases))
    noun = "bases" if len(bases) > 1 else "basis"
    hint = f"{model_id} binds on the {own} {noun} only, not on this revision's {basis.provider_id}"
    other = _SAME_FUNCTION.get(model_id)
    if other is not None and basis.provider_id in MODEL_BASES[other]:
        hint += f"; on {basis.provider_id} the same function is {other}"
    reason = _unadmitted(model_id, basis.provider_id)
    if reason is not None:
        hint += f"; {reason}"
    return Unbound("unsupported", f"model_unsupported({model_id})", hint=hint)


#: S11 design §4.4, units design §4.7: why a model is not admitted on a basis S11 adds (or why
#: `syn001.column` or a `thermal.*` model is not admitted on a basis), appended to R-288's hint.
#: No pair between SYN-001 and C1 of a model outside the `thermal.*` family reads it.
_UNADMITTED: Final[Mapping[str, str]] = {
    # I1b (orchestrator ruling): the first pass's "S11b"/"S11c" texts restated to the admission
    # S11 ends with; the pairs are those of §4.7's "—" cells that no rewritten reason covers.
    "gamma_phi": (
        "its EO face reads lnK and h_<c>, and S11 gives γ–φ faces to the five K02/T05 units "
        "only (L-GP-1)"
    ),
    "pure_fluid": (
        "pure-fluid streams are declared-regime (ADR 0051), which only the thermal.* units take; "
        "none of them has this function"
    ),
    "c1_physics": "the c1.* units carry pr-c1-v1's own physics (ADR 0050 D3)",
    "column_vapour": "pr-c1-v1 is vapour-only (S02 §0)",
    "column_pure": "a pure fluid has no stage composition",
    # Units design §4.7 (I1b).
    "declared_regime": (
        "use thermal.{namesake} (ADR 0051: pure-fluid streams are declared-regime)"
    ),
    "lifted": "use syn001.{namesake} (lifted two-phase streams)",
    "no_volume": "wilson-ig-v2 has no liquid volume, which a pump needs (L-GP-1)",
    "no_entropy": (
        "thermal.* needs a provider with s (SYN-001: none; pr-c1-v1: vapour-only, no s)"
    ),
}
#: Units design §4.7: a `syn001.*` model's `thermal.*` namesake on a pure fluid, and a
#: `thermal.*` model's `syn001.*` namesake on Wilson.
_THERMAL_NAMESAKE: Final[Mapping[str, str]] = {
    _TP_HEATER.model_id: "heater",
    _VALVE.model_id: "valve",
    _ADIABATIC_MIXER.model_id: "mixer",
    _PH_FLASH.model_id: "flash",
    _TP_FLASH.model_id: "flash",
    _LIQUID_PUMP.model_id: "pump",
}
_LIFTED_NAMESAKE: Final[Mapping[str, str]] = {
    _THERMAL_HEATER.model_id: "tp_heater",
    _THERMAL_VALVE.model_id: "valve",
    _THERMAL_MIXER.model_id: "adiabatic_mixer",
    _THERMAL_FLASH.model_id: "ph_flash",
}
_THERMAL_PUMP: Final = thermal_machines.MACHINE_MODEL_IDS["pump"]
_COLUMN_MODEL: Final = "syn001.column"
#: The C1 routing models, refused on S11's bases with their SYN-001 namesake's hint only.
_C1_ROUTING: Final = frozenset(
    c1_id for syn001_id, c1_id in _NAMESAKES if syn001_id in ROUTING_MODELS
)


def _unadmitted(model_id: str, provider_id: str) -> str | None:
    """`_UNADMITTED`'s reason for `model_id` on `provider_id`, or `None` (S11 design §4.4)."""
    if model_id == _COLUMN_MODEL:
        if provider_id == C1_PROVIDER_ID:
            return _UNADMITTED["column_vapour"]
        if provider_id in (_IAPWS95, _COOLPROP):
            return _UNADMITTED["column_pure"]
        return None
    if model_id in ROUTING_MODELS or model_id in _C1_ROUTING:
        return None
    if model_id.startswith("thermal."):
        return _unadmitted_thermal(model_id, provider_id)
    if provider_id in (_IAPWS95, _COOLPROP):
        namesake = _THERMAL_NAMESAKE.get(model_id)
        if namesake is not None:
            return _UNADMITTED["declared_regime"].format(namesake=namesake)
        return _UNADMITTED["pure_fluid" if model_id.startswith("syn001.") else "c1_physics"]
    if provider_id == _WILSON:
        if model_id == _LIQUID_PUMP.model_id:
            return _UNADMITTED["no_volume"]
        return _UNADMITTED["gamma_phi" if model_id.startswith("syn001.") else "c1_physics"]
    return None


def _unadmitted_thermal(model_id: str, provider_id: str) -> str | None:
    """`_unadmitted` for a `thermal.*` model (S11 design §4.4): no entropy on SYN-001's or C1's
    basis; on Wilson's, no liquid volume for the pump and the SYN-001 namesake to use for the
    others; `None` on any other basis."""
    if provider_id in (SYN001_PROVIDER_ID, C1_PROVIDER_ID):
        return _UNADMITTED["no_entropy"]
    if provider_id == _WILSON:
        if model_id == _THERMAL_PUMP:
            return _UNADMITTED["no_volume"]
        return _UNADMITTED["lifted"].format(namesake=_LIFTED_NAMESAKE[model_id])
    return None


#: S11 design §4.4: models outside `MODEL_BASES` refused with a hint (library-only).
_LIBRARY_ONLY_HINTS: Final[Mapping[str, str]] = {
    "syn001.cascade": (
        "bind syn001.column with its top and bottom inlets connected (S02 §1: condenser none, "
        "reboiler none is S01's cascade)"
    ),
}


class _PinReader(Mapping[str, float]):
    """An instance's pins, recording which the builder read."""

    def __init__(self, pins: Mapping[str, float]) -> None:
        self._pins = dict(pins)
        self.read: set[str] = set()

    def __getitem__(self, key: str) -> float:
        value = self._pins[key]
        self.read.add(key)
        return value

    def __contains__(self, key: object) -> bool:
        return key in self._pins

    def __iter__(self) -> Iterator[str]:
        return iter(self._pins)

    def __len__(self) -> int:
        return len(self._pins)


def _first_line(error: Exception) -> str:
    return (str(error).splitlines() or [""])[0]


def _inadmissible(error: SpecificationError, instance: str | None) -> Unbound:
    """T07 ruling round 5, S3: a value the document fixes, refused by the model it names at
    construction, implicating that model's instance."""
    return Unbound(
        "inadmissible",
        f"value_outside_model_domain: {_first_line(error)}",
        () if instance is None else (instance,),
    )


def _refusing_unit(flowsheet: RevisionFlowsheet) -> str | None:
    """The first instance whose own contribution raises `SpecificationError`, or `None` when the
    refusal is the assembled flowsheet's rather than one unit's."""
    for unit in flowsheet.units():
        try:
            unit.contribute(flowsheet.wiring[unit.unit_id], flowsheet.components)
        except SpecificationError:
            return unit.unit_id
    return None


def _variant_backed_models() -> frozenset[str]:
    """The model ids a registered variant names (M02 design note §6.1): their instances must pin
    a registered variant by id and SHA-256. Read per call (≈ 2 ms, measured), not cached: no
    process-global state (T07 G20)."""
    return frozenset(variants.registered_variant(name).model_id for name in variants.registry())


def basis_provider(basis: ComponentBasis) -> PropertyProvider:
    """A fresh provider of `basis` (ADR 0034 D8, ADR 0050 D1), raising `ValueError` for a basis
    with no provider. The raising API W27's snapshot calls; the binder calls `provider_for`, which
    checks the basis' preconditions first (S11 design §4.3)."""
    if basis.provider_id == C1_PROVIDER_ID:
        from openflowsheet.thermo.pr_c1 import PrC1Provider  # noqa: PLC0415

        return PrC1Provider()
    if basis.provider_id == "iapws95-v1":
        from openflowsheet.thermo.iapws95 import Iapws95Provider  # noqa: PLC0415

        return Iapws95Provider()
    if basis.provider_id == _WILSON:
        from openflowsheet import resources  # noqa: PLC0415
        from openflowsheet.thermo import wilson_ig  # noqa: PLC0415
        from openflowsheet.thermo.wilson_ig_v2 import WilsonIdealGasProviderV2  # noqa: PLC0415

        # V03 spec §9.1 (R-880): the records the package carries; `None` is a checkout's copy.
        return WilsonIdealGasProviderV2(resources.packaged_path(wilson_ig.RECORDS_PATH))
    if basis.provider_id == "coolprop-heos-v1":
        from openflowsheet.thermo.coolprop_heos import CoolPropHeosProvider  # noqa: PLC0415

        (component,) = basis.components
        return CoolPropHeosProvider(component)
    if basis != SYN001_BASIS:
        raise ValueError(f"no provider for basis {basis.provider_id!r}")
    from openflowsheet.thermo.syn001 import Syn001Provider  # noqa: PLC0415

    return Syn001Provider()


#: S11 design §4.3: the hint of a CoolProp basis without its optional extra.
COOLPROP_UNAVAILABLE_HINT: Final = (
    "the coolprop extra is not installed (pip install openflowsheet[coolprop])"
)


def provider_for(basis: ComponentBasis) -> PropertyProvider | Unbound:
    """`basis_provider(basis)` once the basis' bind-time preconditions hold (S11 design §4.3,
    ADR 0050 D4), else the typed refusal: CoolProp's optional extra must be importable, and
    Wilson's records must load and satisfy the column theorem's premises P1–P3 in closed form
    (`thermo.wilson_premises`; closes R-781)."""
    if basis.provider_id == "coolprop-heos-v1" and importlib.util.find_spec("CoolProp") is None:
        return Unbound(
            "unsupported", "basis_unavailable(coolprop-heos-v1)", hint=COOLPROP_UNAVAILABLE_HINT
        )
    if basis.provider_id == _WILSON:
        refusal = _wilson_refusal()
        if refusal is not None:
            code, hint = refusal
            return Unbound("unsupported", code, hint=hint)
    return basis_provider(basis)


def _wilson_refusal() -> tuple[str, str] | None:
    """The code and hint that refuse the Wilson basis in this installation, or `None` (S11 design
    §4.3): `basis_unavailable` when the real records do not load, `basis_premises_unmet` naming
    the first violated premise. The verifier's `fresh_provider` raises the same codes. Since
    0.3.0 the records are package data (V03 spec §9.1, R-880), so a wheel binds the basis and
    R-811's refusal of a wheel is gone; an installation without the file is still refused."""
    from openflowsheet import resources  # noqa: PLC0415
    from openflowsheet.thermo import wilson_ig, wilson_premises  # noqa: PLC0415

    try:
        records = wilson_ig.load_records(resources.packaged_path(wilson_ig.RECORDS_PATH))
    except wilson_ig.RecordError as error:
        cause = _first_line(error).split(":", 1)[0]
        return (
            f"basis_unavailable({_WILSON})",
            f"{cause}: the records {wilson_ig.RECORDS_PATH} are neither package data nor in a "
            "source checkout (R-880)",
        )
    found = wilson_premises.violations(records)
    if found:
        return f"basis_premises_unmet({_WILSON})", found[0].hint
    return None


def bind_revision_flowsheet(
    document: Mapping[str, Any], *, surrogates: SurrogateResolver | None = None
) -> RevisionBinding | Unbound:
    """Build and bind a revision's flowsheet, or say which of R-022's kinds prevented it (§1.4).

    `surrogates` resolves a `c1.reactor_surrogate` instance's manifest by its SHA-256 (M04 spec
    §8.2); without one, such an instance is refused `surrogate_manifest_mismatch(<instance>)`.

    Phases, in order, each returning its first refusal: `_model_refusal` (M02 §6.1 variants,
    then R-288 bases), `_surrogate_manifests`, `_built_instances` (on the metered provider),
    `_split_key_refusal` (R-822), `_port_refusal` per instance, then the unconsumed-pin check."""
    from openflowsheet.orchestrator.budget import PropertyMeter

    # R-088 Q29 (T07 design note §12.5): a non-canonical number is refused typed at entry,
    # whether or not a reader reads its field; in a field nothing reads, a digest would
    # otherwise raise untyped.
    pointer = first_noncanonical(document)
    if pointer is not None:
        return Unbound("unsupported", f"document_not_canonical({pointer})")

    try:
        view = parse_revision(document, _INSTANCE_TARGETS)
        sources = pin_specifications(document)
    except RevisionError as error:
        return Unbound(error.kind, error.code, hint=error.hint)

    unbindable = _model_refusal(view.instances, view.basis)
    if unbindable is not None:
        return unbindable
    manifests = _surrogate_manifests(view.instances, surrogates)
    if isinstance(manifests, Unbound):
        return manifests

    # Metered from construction: the declaration's property blocks capture the provider here,
    # and a plan run counts their calls (T02; `PropertyMeter`). The provider is the one the
    # revision's `record_source` selects (ADR 0034 D8): `pr-c1-v1` for the C1 records, SYN-001
    # for every other value, exactly as before.
    bound_provider = provider_for(view.basis)
    if isinstance(bound_provider, Unbound):
        return bound_provider
    provider = PropertyMeter(bound_provider)
    built = _built_instances(view.instances, provider, view.components, manifests)
    if isinstance(built, Unbound):
        return built

    # S11 design §10.2 step 9 (R-822): no instance id is a lifted-split key a staged unit supplies.
    # The reader's id rule refuses the dotted spelling first (R-838); this is the binder's guard,
    # a set intersection of the supplied keys with the ids, not parsing.
    shadowed = _split_key_refusal(view.instances, [unit for _, unit, _, _ in built])
    if shadowed is not None:
        return shadowed

    for instance, unit, _, _ in built:
        miswired = _port_refusal(instance, unit)
        if miswired is not None:
            return miswired

    for instance, _, _, reader in built:
        unread = [column for column in instance.pins if column not in reader.read]
        if unread:
            return Unbound(
                "unsupported",
                f"specification_unconsumed({sources[unread[0]][0]})",
                hint=_unconsumed_hint(instance, unread[0], view.components),
            )

    flowsheet = RevisionFlowsheet(
        provider=provider,
        context=_CONTEXT,
        components=view.components,
        instances=tuple(unit for _, unit, _, _ in built),
        wiring={instance.unit_id: instance.wiring for instance in view.instances},
        streams=view.streams,
        configuration_sha256=configuration_sha256(
            view, {instance.unit_id: configuration for instance, _, configuration, _ in built}
        ),
    )
    try:
        spec = flowsheet.spec()
        row_units = {
            equation.equation_id: unit.unit_id
            for unit in flowsheet.units()
            for equation in unit.contribute(
                flowsheet.wiring[unit.unit_id], flowsheet.components
            ).equations
        }
    except SpecificationError as error:
        return _inadmissible(error, _refusing_unit(flowsheet))

    units = tuple(instance.unit_id for instance in view.instances)
    producers = {stream: producer for stream, producer, _ in view.edges}
    graph = ProcessGraph(
        units=units,
        connections=tuple(
            Connection(
                stream_id=stream,
                producer=producer,
                consumer=consumer,
                state_columns=(
                    *(flow_id(stream, c) for c in view.components),
                    temperature_id(stream),
                    pressure_id(stream),
                ),
            )
            for stream, producer, consumer in sorted(set(view.edges))
        ),
        instance_ids={unit: unit for unit in units},
        column_owners=_column_owners(spec.variable_ids, producers, units),
    )
    return RevisionBinding(
        flowsheet=flowsheet,
        spec=spec,
        graph=graph,
        row_units=row_units,
        revision_sha256=document_sha256(document),
        input_mapping=view.input_mapping,
        specification_pins={
            instance.unit_id: {column: sources[column][0] for column in instance.pins}
            for instance in view.instances
        },
        surrogate_manifests=manifests,
    )


def _model_refusal(instances: Sequence[InstanceView], basis: ComponentBasis) -> Unbound | None:
    """`bind_revision_flowsheet`'s model checks: `None` when every instance's model is pinned to
    a variant the registry resolves (if variant-backed) and binds on `basis`, else the first
    refusal; every instance's variant is checked before any instance's basis."""
    for instance in instances:
        # M02 design note §6.1 (ADR 0035 D1): a variant-backed model is pinned by variant id
        # and SHA-256, resolved against the registry; a native model's `version` is unread.
        if instance.model_id in _variant_backed_models() and (
            variants.resolve(instance.model_id, instance.model_version, instance.model_artifact_ref)
            is None
        ):
            return Unbound("unsupported", f"model_variant_mismatch({instance.unit_id})")
    for instance in instances:
        # R-288: a model binds on the bases `MODEL_BASES` lists for it, and nowhere else.
        if instance.model_id not in MODEL_BASES:
            return Unbound(
                "unsupported",
                f"model_unsupported({instance.model_id})",
                hint=_LIBRARY_ONLY_HINTS.get(instance.model_id),
            )
        if basis.provider_id not in MODEL_BASES[instance.model_id]:
            return _basis_refusal(instance.model_id, basis)
    return None


def _surrogate_manifests(
    instances: Sequence[InstanceView], surrogates: SurrogateResolver | None
) -> dict[str, Mapping[str, Any]] | Unbound:
    """Each `c1.reactor_surrogate` instance's manifest by instance id (ids are unique in a
    parsed revision, `id_duplicate`), resolved through `surrogates`; the first instance whose
    manifest does not resolve is refused instead."""
    manifests: dict[str, Mapping[str, Any]] = {}
    for instance in instances:
        # M04 spec §8.2 (ADR 0037 D2): a surrogate is pinned by its manifest's SHA-256, resolved
        # through the injected resolver and checked; `revision_unsupported` otherwise.
        if instance.model_id == c1_surrogate.MODEL_ID:
            manifest = _resolve_surrogate(instance, surrogates)
            if manifest is None:
                return Unbound("unsupported", f"surrogate_manifest_mismatch({instance.unit_id})")
            manifests[instance.unit_id] = manifest
    return manifests


def _built_instances(
    instances: Sequence[InstanceView],
    provider: PropertyMeter,
    components: tuple[str, ...],
    manifests: Mapping[str, Mapping[str, Any]],
) -> list[tuple[InstanceView, UnitModel, Configuration, _PinReader]] | Unbound:
    """Each instance in order with the unit and configuration its model's builder makes on
    `provider` (a surrogate's with its manifest in `manifests`) and the reader of its pins; the
    first builder's refusal instead. Raises `ValueError` when a builder builds another model or
    unit id than the instance names."""
    built: list[tuple[InstanceView, UnitModel, Configuration, _PinReader]] = []
    for instance in instances:
        reader = _PinReader(instance.pins)
        builder = MODEL_BUILDERS[instance.model_id]
        if instance.unit_id in manifests:
            builder = partial(_c1_reactor_surrogate_of, manifest=manifests[instance.unit_id])
        try:
            unit, configuration = builder(
                replace(instance, pins=reader), provider, _CONTEXT, components
            )
        except RevisionError as error:
            return Unbound(error.kind, error.code, hint=error.hint)
        except SpecificationError as error:
            # T07 ruling round 5, S3: this binder refuses `role: free`, so every value a model
            # refuses here is one the document fixes.
            return _inadmissible(error, instance.unit_id)
        if unit.model_id != instance.model_id or unit.unit_id != instance.unit_id:
            raise ValueError(
                f"builder for {instance.model_id} built {unit.model_id} {unit.unit_id!r}"
            )
        built.append((instance, unit, configuration, reader))
    return built


def _split_key_refusal(
    instances: Sequence[InstanceView], units: Sequence[UnitModel]
) -> Unbound | None:
    """S11 design §10.2 step 9 (R-822): `None` when no instance id is a lifted-split key the
    staged `units` supply, else the refusal of the first such key in `split_owners`' order."""
    ids = {instance.unit_id for instance in instances}
    owners = split_owners(staged_units(units))
    for key, owner in owners.items():
        if key in ids:
            return Unbound(
                "unsupported",
                f"id_unsupported({key})",
                hint=f"Instance id `{key}` is a lifted-split key of instance `{owner}`; "
                "rename the instance.",
            )
    return None


def _port_refusal(instance: InstanceView, unit: UnitModel) -> Unbound | None:
    """`None` when every port `instance` wires is a material port `unit.ports()` declares, with
    the declared direction and (for a port of multiplicity 1) one connection, and every declared
    material port is wired; else the first refusal, checking the wired ports in order before the
    declared ones."""
    declared = {port.name: port for port in unit.ports()}
    for port, connected in instance.ports.items():
        spec_port = declared.get(port)
        where = f"{instance.unit_id}.{port}"
        if spec_port is None or spec_port.kind != "material":
            return Unbound("unsupported", f"port_unsupported({where})")
        if spec_port.direction != instance.directions[port]:
            return Unbound("unsupported", f"port_direction_unsupported({where})")
        if spec_port.multiplicity == 1 and len(connected) != 1:
            return Unbound("unsupported", f"port_multiplicity_unsupported({where})")
    for name, spec_port in declared.items():
        if spec_port.kind == "material" and name not in instance.ports:
            return Unbound("incomplete", f"port_unwired({instance.unit_id}.{name})")
    return None
