"""The builder catalogue: one `Builder` per model id (`MODEL_BUILDERS`, T05 design note §1.3).

Each builder constructs an instance's unit from its parameters and the pins its `ModelSignature`
declares (`model_signatures`, imported at top), and returns the unit with its configuration;
`resolve_surrogate` reads a C1 reactor's surrogate manifest through a `SurrogateResolver`. The
plugin modules `column_binding` and `thermal_binding` are imported lazily, inside the builders that
call them. `revision_binding` binds with this catalogue and re-exports its public names.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Any, Final

from openflowsheet.adapters import variants
from openflowsheet.application.model_signatures import (
    _ADIABATIC_MIXER,
    _C1_ADIABATIC_MIXER,
    _C1_FEED_SOURCE,
    _C1_PRODUCT_SINK,
    _C1_REACTOR,
    _C1_REACTOR_STANDIN,
    _C1_REACTOR_SURROGATE,
    _C1_STREAM_SPLITTER,
    _C1_TP_FLASH,
    _C1_TP_HEATER,
    _COLUMN,
    _COMPONENT_SEPARATOR,
    _CONVERSION_REACTOR,
    _FEED_SOURCE,
    _HEAT_EXCHANGER,
    _KINETIC_CSTR,
    _LIQUID_PUMP,
    _ONE_PHASE,
    _PH_FLASH,
    _PRODUCT_SINK,
    _STREAM_SPLITTER,
    _THERMAL_SIGNATURES,
    _TP_FLASH,
    _TP_HEATER,
    _VALVE,
    Builder,
    Configuration,
    ModelSignature,
    PinColumn,
    _column,
    _columns,
    _expand,
    _missing_choice_hint,
    _missing_pin_hint,
    _phase_hint,
    _pin,
    _pinned,
    _require_phase,
    _stream,
    instance_contract,
)
from openflowsheet.canonical import document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import UnitModel
from openflowsheet.models.c1 import feed as c1_feed
from openflowsheet.models.c1 import flash as c1_flash
from openflowsheet.models.c1 import heater as c1_heater
from openflowsheet.models.c1 import mixer as c1_mixer
from openflowsheet.models.c1 import reactor as c1_reactor
from openflowsheet.models.c1 import sink as c1_sink
from openflowsheet.models.c1 import splitter as c1_splitter
from openflowsheet.models.revision_flowsheet import InstanceView, RevisionError
from openflowsheet.models.syn001 import PROVIDER_ID as SYN001_PROVIDER_ID
from openflowsheet.models.syn001.component_separator import ComponentSeparator
from openflowsheet.models.syn001.conversion_reactor import ConversionReactor
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.flash import TPFlash
from openflowsheet.models.syn001.heat_exchanger import HeatExchanger
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.models.syn001.kinetic_cstr import KineticCSTR
from openflowsheet.models.syn001.mixer import AdiabaticMixer
from openflowsheet.models.syn001.ph_flash import PHFlash
from openflowsheet.models.syn001.pump import LiquidPump
from openflowsheet.models.syn001.sink import ProductSink
from openflowsheet.models.syn001.splitter import StreamSplitter
from openflowsheet.models.syn001.valve import Valve
from openflowsheet.studies.surrogate import reactor as c1_surrogate
from openflowsheet.studies.surrogate.manifest import check_manifest
from openflowsheet.thermo import Phase, PropertyProvider

#: M04 spec §8.2 (ADR 0037 D2): a SurrogateManifest by its SHA-256, or `None` when the project
#: holds none. Injected by the application from the project's artifact store (R-237's pattern);
#: the binder never reads a store.
SurrogateResolver = Callable[[str], Mapping[str, Any] | None]


# -- builder helpers ---------------------------------------------------------------------------


def _names(
    signature: ModelSignature, template: str, view: InstanceView, components: Sequence[str]
) -> tuple[str, ...]:
    """The names one of `signature`'s required templates expands to on this instance."""
    if template not in signature.required:
        raise ValueError(f"{signature.model_id} does not require {template!r}")
    return _expand(template, view, components)


def _inlet_phase(view: InstanceView) -> Phase | None:
    _stream(view, "inlet")
    return view.phases["inlet"]


# -- the six K02 builders (§1.3's table) --------------------------------------------------------


def _routing_fields(provider: PropertyProvider) -> dict[str, Any]:
    """S11 design §4.5: a routing model's manifest fields from the bound provider on a basis
    other than SYN-001's; nothing on SYN-001's, whose defaults are its constants (so its
    manifests do not change). The five γ–φ-faced units (mixer, heater, TP flash, PH flash,
    valve) take the same fields (S11 units design §4.5, WO-D2)."""
    described = provider.describe()
    if described.provider_id == SYN001_PROVIDER_ID:
        return {}
    return {
        "property_provider": described.provider_id,
        "reference_convention": described.reference_convention,
        "domain": {"T": tuple(described.domain["T"]), "P": tuple(described.domain["P"])},
    }


def _feed_source(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _FEED_SOURCE
    instance_contract(view, signature, components)
    pin = signature.pin("flows")
    flows = _columns(view, pin, components)
    unit = FeedSource(
        unit_id=view.unit_id,
        flows=tuple(
            _pin(view, column, partial(_missing_pin_hint, view, signature, pin, components, c))
            for c, column in zip(components, flows, strict=True)
        ),
        temperature=_pinned(view, signature, "temperature"),
        pressure=_pinned(view, signature, "pressure"),
        components=components,
        **_routing_fields(provider),
    )
    return unit, {}


def _adiabatic_mixer(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    instance_contract(view, _ADIABATIC_MIXER, components)
    unit = AdiabaticMixer(
        unit_id=view.unit_id,
        provider=provider,
        context=context,
        components=components,
        **_routing_fields(provider),
    )
    return unit, {}


def _tp_heater(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _TP_HEATER
    instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    unit = TPHeater(
        unit_id=view.unit_id,
        provider=provider,
        outlet_temperature=_pinned(view, signature, "outlet_temperature"),
        context=context,
        inlet_phase=inlet_phase,
        pressure_drop=0.0,
        components=components,
        **_routing_fields(provider),
    )
    return unit, {"inlet_phase": inlet_phase}


def _tp_flash(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _TP_FLASH
    instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    # Both outlets wired before either is read.
    _stream(view, "vapor")
    _stream(view, "liquid")
    temperature = _pinned(view, signature, "temperature")
    pressure = _pinned(view, signature, "pressure")
    if _pinned(view, signature, "liquid_temperature") != temperature:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.T)")
    if _pinned(view, signature, "liquid_pressure") != pressure:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.P)")
    unit = TPFlash(
        unit_id=view.unit_id,
        provider=provider,
        temperature=temperature,
        pressure=pressure,
        context=context,
        inlet_phase=inlet_phase,
        components=components,
        **_routing_fields(provider),
    )
    return unit, {"inlet_phase": inlet_phase}


def _stream_splitter(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    parameters = instance_contract(view, _STREAM_SPLITTER, components)
    unit = StreamSplitter(
        unit_id=view.unit_id,
        split_fraction=parameters["split_fraction"],
        components=components,
        **_routing_fields(provider),
    )
    return unit, {}


def _product_sink(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    instance_contract(view, _PRODUCT_SINK, components)
    unit = ProductSink(unit_id=view.unit_id, components=components, **_routing_fields(provider))
    return unit, {}


# -- the six T05 builders (§1.3's table, W11) ----------------------------------------------------


def _declared_phase(view: InstanceView, port: str) -> Phase:
    """A port whose rule is `liquid` or `vapor`: wired, and not lifted."""
    _stream(view, port)
    phase = view.phases[port]
    if phase is None:
        raise RevisionError(
            "unsupported",
            f"port_phase_unsupported({view.unit_id}.{port})",
            _phase_hint(view, port, _ONE_PHASE),
        )
    return phase


def _one_specification(
    view: InstanceView, signature: ModelSignature, name: str
) -> tuple[PinColumn, str]:
    """Exactly one of the choice's options is pinned; returns it and its column, unread.

    Options are keyed by column, a later option taking an earlier one's column.
    """
    choice = signature.choice(name)
    candidates = {_column(view, option): option for option in choice.options}
    pinned = [column for column in candidates if column in view.pins]
    if not pinned:
        raise RevisionError(
            "incomplete",
            f"specification_missing({view.unit_id}.{choice.name})",
            _missing_choice_hint(view, signature, choice),
        )
    if len(pinned) > 1:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.{choice.name})")
    return candidates[pinned[0]], pinned[0]


def _ph_flash(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _PH_FLASH
    parameters = instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    unit = PHFlash(
        unit_id=view.unit_id,
        provider=provider,
        duty=_pinned(view, signature, "duty"),
        context=context,
        pressure_drop=parameters["pressure_drop"],
        inlet_phase=inlet_phase,
        components=components,
        **_routing_fields(provider),
    )
    return unit, {"inlet_phase": inlet_phase}


def _valve(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _VALVE
    instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    unit = Valve(
        unit_id=view.unit_id,
        provider=provider,
        outlet_pressure=_pinned(view, signature, "outlet_pressure"),
        context=context,
        inlet_phase=inlet_phase,
        components=components,
        **_routing_fields(provider),
    )
    return unit, {"inlet_phase": inlet_phase}


def _liquid_pump(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _LIQUID_PUMP
    parameters = instance_contract(view, signature, components)
    unit = LiquidPump(
        unit_id=view.unit_id,
        provider=provider,
        outlet_pressure=_pinned(view, signature, "outlet_pressure"),
        efficiency=parameters["efficiency"],
        context=context,
        components=components,
    )
    return unit, {}


def _conversion_reactor(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """`conversion.<k>` names the key `k`: the one reaction has exactly one."""
    signature = _CONVERSION_REACTOR
    stoichiometry = _names(signature, "nu.{component}", view, components)
    conversions = _names(signature, "conversion.{key}", view, components)
    parameters = instance_contract(view, signature, components)
    (conversion,) = conversions
    inlet_phase = _inlet_phase(view)
    option, column = _one_specification(view, signature, "energy_specification")
    energy_specification = option.name
    key_component = conversion.removeprefix("conversion.")
    unit = ConversionReactor(
        unit_id=view.unit_id,
        provider=provider,
        stoichiometry=tuple(parameters[name] for name in stoichiometry),
        key_component=key_component,
        conversion=parameters[conversion],
        energy_specification=energy_specification,
        value=_pin(view, column),
        context=context,
        pressure_drop=parameters["pressure_drop"],
        inlet_phase=inlet_phase,
        components=components,
    )
    return unit, {
        "inlet_phase": inlet_phase,
        "key_component": key_component,
        "energy_specification": energy_specification,
    }


def _kinetic_cstr(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """`damkohler.<k>` names the key `k`; the outlet is declared `vapor` or `liquid`."""
    signature = _KINETIC_CSTR
    stoichiometry = _names(signature, "nu.{component}", view, components)
    rates = _names(signature, "damkohler.{key}", view, components)
    parameters = instance_contract(view, signature, components)
    (rate,) = rates
    inlet_phase = _inlet_phase(view)
    phase = _declared_phase(view, "outlet")
    key_component = rate.removeprefix("damkohler.")
    unit = KineticCSTR(
        unit_id=view.unit_id,
        provider=provider,
        stoichiometry=tuple(parameters[name] for name in stoichiometry),
        key_component=key_component,
        damkohler=parameters[rate],
        reference_temperature=parameters["T_ref"],
        temperature_scale=parameters["T_scale"],
        coolant_flow=parameters["coolant_flow"],
        coolant_cp=parameters["coolant_cp"],
        coolant_temperature=parameters["T_coolant"],
        phase=phase,
        context=context,
        pressure_drop=parameters["pressure_drop"],
        inlet_phase=inlet_phase,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase, "key_component": key_component, "phase": phase}


def _syn001_column(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """`column_binding.build_column` (§4.7.1–§4.7.2), imported at the call, so the plugin module
    loads only when a column is built. (The import was lazy to break a cycle while the signatures
    lived in `revision_binding`; `column_binding` now imports `model_signatures`, not this
    module.)"""
    from openflowsheet.application.column_binding import build_column  # noqa: PLC0415

    return build_column(view, provider, context, components)


def _component_separator(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _COMPONENT_SEPARATOR
    split = _names(signature, "split.{component}", view, components)
    parameters = instance_contract(view, signature, components)
    inlet_phase = _inlet_phase(view)
    top_phase = _declared_phase(view, "top")
    bottom_phase = _declared_phase(view, "bottom")
    unit = ComponentSeparator(
        unit_id=view.unit_id,
        provider=provider,
        split=tuple(parameters[name] for name in split),
        context=context,
        inlet_phase=inlet_phase,
        top_phase=top_phase,
        bottom_phase=bottom_phase,
        components=components,
    )
    return unit, {"inlet_phase": inlet_phase, "top_phase": top_phase, "bottom_phase": bottom_phase}


def _heat_exchanger(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    """Each side keeps its declared phase: its outlet's rule is its inlet's."""
    signature = _HEAT_EXCHANGER
    instance_contract(view, signature, components)
    phases: dict[str, Phase] = {}
    for side in ("hot", "cold"):
        phases[side] = _declared_phase(view, f"{side}_inlet")
        _stream(view, f"{side}_outlet")
        _require_phase(view, f"{side}_outlet", phases[side])
    option, column = _one_specification(view, signature, "specification")
    unit = HeatExchanger(
        unit_id=view.unit_id,
        provider=provider,
        specification=option.name,
        value=_pin(view, column),
        context=context,
        hot_phase=phases["hot"],
        cold_phase=phases["cold"],
        components=components,
    )
    return unit, {
        "specification": option.name,
        "hot_phase": phases["hot"],
        "cold_phase": phases["cold"],
    }


# -- the six M02 C1 builders (design note §8, §14.2; WO-8.2) ------------------------------------
#
# The C1 units are their own classes (`models.c1`): SYN-001's carry SYN-001 constants in their
# manifests and row origins. Their signatures read what SYN-001's read, port for port, so the
# verifier's rules (`verify.table`) read the same pins. They bind only on the C1 basis, which
# `MODEL_BASES` states and the binder enforces (R-288); the builders do not check it.


def _c1_feed_source(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _C1_FEED_SOURCE
    instance_contract(view, signature, components)
    pin = signature.pin("flows")
    flows = _columns(view, pin, components)
    unit = c1_feed.FeedSource(
        unit_id=view.unit_id,
        flows=tuple(
            _pin(view, column, partial(_missing_pin_hint, view, signature, pin, components, c))
            for c, column in zip(components, flows, strict=True)
        ),
        temperature=_pinned(view, signature, "temperature"),
        pressure=_pinned(view, signature, "pressure"),
        components=components,
    )
    return unit, {}


def _c1_adiabatic_mixer(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    instance_contract(view, _C1_ADIABATIC_MIXER, components)
    unit = c1_mixer.AdiabaticMixer(
        unit_id=view.unit_id, provider=provider, context=context, components=components
    )
    return unit, {}


def _c1_tp_heater(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _C1_TP_HEATER
    instance_contract(view, signature, components)
    unit = c1_heater.TPHeater(
        unit_id=view.unit_id,
        provider=provider,
        outlet_temperature=_pinned(view, signature, "outlet_temperature"),
        context=context,
        components=components,
    )
    return unit, {}


def _c1_tp_flash(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _C1_TP_FLASH
    instance_contract(view, signature, components)
    _stream(view, "inlet")
    _stream(view, "vapor")
    _stream(view, "liquid")
    temperature = _pinned(view, signature, "temperature")
    pressure = _pinned(view, signature, "pressure")
    if _pinned(view, signature, "liquid_temperature") != temperature:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.T)")
    if _pinned(view, signature, "liquid_pressure") != pressure:
        raise RevisionError("conflict", f"specification_conflict({view.unit_id}.P)")
    unit = c1_flash.TPFlash(
        unit_id=view.unit_id,
        provider=provider,
        temperature=temperature,
        pressure=pressure,
        context=context,
        components=components,
    )
    return unit, {}


def _c1_stream_splitter(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    parameters = instance_contract(view, _C1_STREAM_SPLITTER, components)
    unit = c1_splitter.StreamSplitter(
        unit_id=view.unit_id,
        split_fraction=parameters["split_fraction"],
        components=components,
    )
    return unit, {}


def _c1_product_sink(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    instance_contract(view, _C1_PRODUCT_SINK, components)
    return c1_sink.ProductSink(unit_id=view.unit_id, components=components), {}


def _c1_reactor(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    signature = _C1_REACTOR if view.model_id == _C1_REACTOR.model_id else _C1_REACTOR_STANDIN
    parameters = instance_contract(view, signature, components)
    variant = variants.resolve(view.model_id, view.model_version, view.model_artifact_ref)
    if variant is None:  # the binder resolved every variant-backed instance before building
        raise RevisionError("unsupported", f"model_variant_mismatch({view.unit_id})")
    initial = variant.coupling["initial"]
    unit = c1_reactor.C1Reactor(
        unit_id=view.unit_id,
        model=view.model_id,
        provider=provider,
        context=context,
        variant=variant.document,
        n_tubes=parameters["n_tubes"],
        conversion=float(initial["X"]),
        temperature_rise=float(initial["dT_K"]),
        components=components,
    )
    # `n_tubes` selects no expression (no row reads it), so the configuration digest gets
    # nothing; the unit carries it for the experiment request.
    return unit, {}


def _c1_reactor_surrogate_of(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
    manifest: Mapping[str, Any],
) -> tuple[UnitModel, Configuration]:
    parameters = instance_contract(view, _C1_REACTOR_SURROGATE, components)
    assert view.model_artifact_ref is not None  # `_resolve_surrogate` resolved it
    unit = c1_surrogate.C1ReactorSurrogate(
        unit_id=view.unit_id,
        provider=provider,
        context=context,
        surrogate_manifest=manifest,
        manifest_sha256=view.model_artifact_ref,
        n_tubes=parameters["n_tubes"],
        components=components,
    )
    # The manifest (its coefficients) and N_tubes select the block's expression without changing
    # an id: the configuration digest, hence the label and `model_version`, carries both (ADR
    # 0002 D2.7). Neither is a pinned input: no row reads them symbolically (build log, WO-7).
    return unit, {
        "surrogate_manifest_sha256": view.model_artifact_ref,
        "n_tubes": repr(float(parameters["n_tubes"])),
    }


def _c1_reactor_surrogate(
    view: InstanceView,
    provider: PropertyProvider,
    context: EvaluationContext,
    components: tuple[str, ...],
) -> tuple[UnitModel, Configuration]:
    raise RevisionError("unsupported", f"surrogate_manifest_mismatch({view.unit_id})")


def resolve_surrogate(
    version: str | None, reference: str | None, surrogates: SurrogateResolver | None
) -> Mapping[str, Any] | None:
    """M04 spec §8.2: the SurrogateManifest a `c1.reactor_surrogate` reference names, or `None` —
    no resolver, an unknown hash, a document whose canonical SHA-256 is not `reference`
    (`model.artifact_ref`), a `version` (`model.version`) that is not its `surrogate_id`, or a
    manifest its checker refuses (M04.A24). The binder's resolution and the replacement check's
    (spec §8.3, `resolvable`)."""
    if surrogates is None or reference is None:
        return None
    manifest = surrogates(reference)
    if manifest is None:
        return None
    try:
        if document_sha256(manifest) != reference:
            return None
    except (TypeError, ValueError):
        return None
    if check_manifest(manifest):
        return None
    if manifest["surrogate_id"] != version:
        return None
    return manifest


# -- the `thermal.*` family (S11 units design §4.4, §5.4 I1b) -----------------------------------


def _thermal_builder(model_id: str) -> Builder:
    """`thermal_binding.BUILDERS[model_id]`, imported at the call, so the plugin module loads only
    when a `thermal.*` unit is built (`thermal_binding` imports `model_signatures`, not this
    one)."""

    def build(
        view: InstanceView,
        provider: PropertyProvider,
        context: EvaluationContext,
        components: tuple[str, ...],
    ) -> tuple[UnitModel, Configuration]:
        from openflowsheet.application.thermal_binding import BUILDERS  # noqa: PLC0415

        return BUILDERS[model_id](view, provider, context, components)

    return build


#: Model id -> builder: the six K02 models, the six T05 ones (§1.3's table), T08's kinetic CSTR
#: (build-first §A1), S11's column (§4.7), M02's six C1 units and two C1 reactor ids (R-280), and
#: M04's surrogate of the C1 reactor (R-301): its registered builder refuses; the binder hands a
#: resolved manifest to `_c1_reactor_surrogate_of` instead.
MODEL_BUILDERS: Final[Mapping[str, Builder]] = {
    _FEED_SOURCE.model_id: _feed_source,
    _ADIABATIC_MIXER.model_id: _adiabatic_mixer,
    _TP_HEATER.model_id: _tp_heater,
    _TP_FLASH.model_id: _tp_flash,
    _STREAM_SPLITTER.model_id: _stream_splitter,
    _PRODUCT_SINK.model_id: _product_sink,
    _PH_FLASH.model_id: _ph_flash,
    _VALVE.model_id: _valve,
    _LIQUID_PUMP.model_id: _liquid_pump,
    _CONVERSION_REACTOR.model_id: _conversion_reactor,
    _COMPONENT_SEPARATOR.model_id: _component_separator,
    _HEAT_EXCHANGER.model_id: _heat_exchanger,
    _KINETIC_CSTR.model_id: _kinetic_cstr,
    _COLUMN.model_id: _syn001_column,
    _C1_FEED_SOURCE.model_id: _c1_feed_source,
    _C1_ADIABATIC_MIXER.model_id: _c1_adiabatic_mixer,
    _C1_TP_HEATER.model_id: _c1_tp_heater,
    _C1_TP_FLASH.model_id: _c1_tp_flash,
    _C1_STREAM_SPLITTER.model_id: _c1_stream_splitter,
    _C1_PRODUCT_SINK.model_id: _c1_product_sink,
    _C1_REACTOR.model_id: _c1_reactor,
    # R-310: `models/c1/reactor_standin.py`'s sentence "Not registered in `MODEL_BUILDERS`" is a
    # recorded erratum (the module's bytes are the stand-in variant's pinned artifact).
    _C1_REACTOR_STANDIN.model_id: _c1_reactor,
    _C1_REACTOR_SURROGATE.model_id: _c1_reactor_surrogate,
    # S11 units design §5.4 (I1b): the seven `thermal.*` builders (`thermal_binding`).
    **{s.model_id: _thermal_builder(s.model_id) for s in _THERMAL_SIGNATURES},
}
