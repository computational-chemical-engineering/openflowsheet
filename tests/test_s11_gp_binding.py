"""S11 WO-D2: the five γ–φ-faced K02/T05 builders bind on Wilson's basis.

`docs/derivations/S11-units-design.md` §4.5 (ADR 0051), "Binding (WO-D2)": `_adiabatic_mixer`,
`_tp_heater`, `_tp_flash`, `_ph_flash` and `_valve` pass `property_provider`,
`reference_convention` and `domain` from the bound provider's `describe()` on a basis other than
SYN-001's, and nothing on SYN-001's, so the SYN-001 construction is identical.

`MODEL_BASES` admits these models on SYN-001's basis only until the integration WO (I1b) adds
Wilson's row; here it is monkeypatched to admit `wilson-ig-v1` (v1 until D5 selects v2), and one
test pins the unpatched refusal so that the patch is seen to be what lets them bind.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest
from m02_c1_support import connection, quantity, revision, specification

from openflowsheet.application import revision_binding
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BASES,
    RevisionBinding,
    basis_provider,
    bind_revision_flowsheet,
)
from openflowsheet.models.revision_flowsheet import (
    SYN001_BASIS,
    SYN001_RECORDS,
    WILSON_BASIS,
    WILSON_RECORDS,
    component_basis,
)
from openflowsheet.models.syn001 import PROVIDER_ID as SYN001_PROVIDER_ID
from openflowsheet.models.syn001 import REFERENCE_CONVENTION as SYN001_CONVENTION

MIXER, HEATER, TP_FLASH, PH_FLASH, VALVE = (
    "syn001.adiabatic_mixer",
    "syn001.tp_heater",
    "syn001.tp_flash",
    "syn001.ph_flash",
    "syn001.valve",
)
FIVE = (MIXER, HEATER, TP_FLASH, PH_FLASH, VALVE)
WILSON_V1 = "wilson-ig-v1"
ROLES = {"syn001.feed_source": "feed", "syn001.product_sink": "product_sink"}

Document = dict[str, Any]


def _instance(unit: str, model: str, parameters: Mapping[str, Any] | None = None) -> Document:
    return {
        "id": unit,
        "model": {"id": model, "version": "0.0.0-declared", "artifact_ref": None},
        "semantic_role": ROLES.get(model, "other"),
        "parameters": dict(parameters or {}),
        "policy": {"fidelity": "test", "validity": "test"},
    }


def _zero_drop() -> dict[str, Any]:
    return {"pressure_drop": quantity(0.0, "Pa", "pressure", [-1, 1, -2, 0, 0, 0, 0])}


def _feed_pins(
    stream: str,
    components: Sequence[str],
    flows: Sequence[float],
    temperature: float,
    pressure: float,
) -> list[Document]:
    return [
        *(
            specification(
                f"SPEC-{stream}-n-{c}",
                "connection",
                stream,
                "state.n",
                v,
                "molar_flow",
                component=c,
            )
            for c, v in zip(components, flows, strict=True)
        ),
        specification(
            f"SPEC-{stream}-T", "connection", stream, "state.T", temperature, "temperature"
        ),
        specification(f"SPEC-{stream}-P", "connection", stream, "state.P", pressure, "pressure"),
    ]


def unit_revision(
    model: str,
    record_source: str,
    components: Sequence[str],
    flows: Sequence[float],
    *,
    temperature: float = 330.0,
    pressure: float = 101_325.0,
    outlet_temperature: float = 360.0,
    outlet_pressure: float = 50_000.0,
) -> Document:
    """feed(s) → one `model` instance `U` → one sink per outlet, on `record_source`.

    Every feed is liquid at (`temperature`, `pressure`) with `flows`; the mixer has two feeds.
    The heater's outlet and the valve's are lifted (`vapor_liquid`); the flashes' products are
    `vapor` and `liquid`. Pins: the heater's outlet T, the TP flash's T and P (both products), the
    valve's outlet P and the PH flash's duty."""
    feeds = ("S1", "S2") if model == MIXER else ("S1",)
    ports = {MIXER: ("inlet",) * 2}.get(model, ("inlet",))
    outlets: tuple[tuple[str, str, str], ...] = {
        MIXER: (("outlet", "S3", "liquid"),),
        HEATER: (("outlet", "S3", "vapor_liquid"),),
        VALVE: (("outlet", "S3", "vapor_liquid"),),
        TP_FLASH: (("vapor", "S3", "vapor"), ("liquid", "S4", "liquid")),
        PH_FLASH: (("vapor", "S3", "vapor"), ("liquid", "S4", "liquid")),
    }[model]
    parameters = _zero_drop() if model in (HEATER, TP_FLASH, PH_FLASH) else {}
    instances = [_instance("U", model, parameters)]
    connections: list[Document] = []
    pins: list[Document] = []
    for k, (stream, port) in enumerate(zip(feeds, ports, strict=True)):
        instances.append(_instance(f"F{k}", "syn001.feed_source"))
        connections.append(connection(stream, (f"F{k}", "outlet"), ("U", port), "liquid"))
        pins += _feed_pins(stream, components, flows, temperature, pressure)
    for k, (port, stream, phase) in enumerate(outlets):
        instances.append(_instance(f"K{k}", "syn001.product_sink"))
        connections.append(connection(stream, ("U", port), (f"K{k}", "inlet"), phase))
    if model == HEATER:
        pins.append(
            specification(
                "SPEC-U-T", "connection", "S3", "state.T", outlet_temperature, "temperature"
            )
        )
    if model == TP_FLASH:
        for stream in ("S3", "S4"):
            pins.append(
                specification(
                    f"SPEC-{stream}-T",
                    "connection",
                    stream,
                    "state.T",
                    outlet_temperature,
                    "temperature",
                )
            )
            pins.append(
                specification(
                    f"SPEC-{stream}-P", "connection", stream, "state.P", pressure, "pressure"
                )
            )
    if model == VALVE:
        pins.append(
            specification("SPEC-U-P", "connection", "S3", "state.P", outlet_pressure, "pressure")
        )
    if model == PH_FLASH:
        pins.append(specification("SPEC-U-Q", "instance", "U", "duty.Q", 1.0e3, "heat_rate"))
    return revision(
        instances,
        connections,
        pins,
        components=components,
        record_source=record_source,
        revision_id=f"S11-GP-BINDING-{model.split('.')[1]}",
    )


def wilson_revision(model: str, **kwargs: float) -> Document:
    return unit_revision(
        model, WILSON_RECORDS, WILSON_BASIS.components, (0.25, 0.25, 0.5), **kwargs
    )


def syn001_revision(model: str, **kwargs: float) -> Document:
    return unit_revision(model, SYN001_RECORDS, SYN001_BASIS.components, (0.5, 0.3, 0.2), **kwargs)


@pytest.fixture
def wilson_admitted(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`MODEL_BASES` with Wilson's row for the five, as I1b will add it (v1 until D5)."""
    for model in FIVE:
        monkeypatch.setitem(
            revision_binding.MODEL_BASES, model, frozenset({*MODEL_BASES[model], WILSON_V1})
        )
    yield


def _unit(binding: RevisionBinding) -> Any:
    (unit,) = (u for u in binding.flowsheet.units() if u.unit_id == "U")
    return unit


@pytest.mark.parametrize("model", FIVE)
def test_unpatched_the_five_are_refused_on_wilson(model: str) -> None:
    """Until I1b, R-288 refuses the five on Wilson's basis; the fixture is what admits them."""
    refused = bind_revision_flowsheet(wilson_revision(model))
    assert isinstance(refused, Unbound), refused
    assert (refused.kind, refused.detail) == ("unsupported", f"model_unsupported({model})")


@pytest.mark.usefixtures("wilson_admitted")
@pytest.mark.parametrize("model", FIVE)
def test_on_wilson_the_unit_carries_the_bound_providers_fields(model: str) -> None:
    document = wilson_revision(model)
    bound = bind_revision_flowsheet(document)
    assert isinstance(bound, RevisionBinding), bound
    described = basis_provider(component_basis(document)).describe()
    assert described.provider_id == WILSON_V1
    unit = _unit(bound)
    assert unit.provider.describe().provider_id == WILSON_V1
    assert unit.components == WILSON_BASIS.components
    assert (unit.property_provider, unit.reference_convention) == (
        described.provider_id,
        described.reference_convention,
    )
    assert dict(unit.domain) == {
        "T": tuple(described.domain["T"]),
        "P": tuple(described.domain["P"]),
    }
    manifest = unit.manifest()
    requirements, domain = manifest["execution_requirements"], manifest["validity"]["domain"]
    assert requirements["property_provider"] == WILSON_V1
    assert requirements["reference_convention"] == described.reference_convention
    assert (domain["temperature_K"]["min"], domain["temperature_K"]["max"]) == tuple(
        described.domain["T"]
    )
    assert (domain["pressure_Pa"]["min"], domain["pressure_Pa"]["max"]) == tuple(
        described.domain["P"]
    )
    assert list(domain["components"]) == list(WILSON_BASIS.components)


@pytest.mark.usefixtures("wilson_admitted")
@pytest.mark.parametrize("model", FIVE)
def test_on_syn001_the_builders_pass_nothing(model: str) -> None:
    bound = bind_revision_flowsheet(syn001_revision(model))
    assert isinstance(bound, RevisionBinding), bound
    unit = _unit(bound)
    assert (unit.property_provider, unit.reference_convention, dict(unit.domain)) == (
        SYN001_PROVIDER_ID,
        SYN001_CONVENTION,
        {"T": (280.0, 440.0), "P": (50000.0, 200000.0)},
    )


# -- the constructors' range checks read the bound domain (§4.5) ---------------------------------
# Wilson's domain is T ∈ [300, 400] K, P ∈ [3e4, 2e5] Pa; SYN-001's is [280, 440] K, [5e4, 2e5] Pa.


@pytest.mark.usefixtures("wilson_admitted")
def test_a_valve_outlet_inside_wilsons_pressure_domain_only_binds_on_wilson() -> None:
    assert isinstance(
        bind_revision_flowsheet(wilson_revision(VALVE, outlet_pressure=40_000.0)), RevisionBinding
    )
    refused = bind_revision_flowsheet(syn001_revision(VALVE, outlet_pressure=40_000.0))
    assert isinstance(refused, Unbound), refused
    assert (refused.kind, refused.detail, refused.implicated) == (
        "inadmissible",
        "value_outside_model_domain: pressure_outside_domain(outlet_pressure)",
        ("U",),
    )


@pytest.mark.usefixtures("wilson_admitted")
@pytest.mark.parametrize("model", (HEATER, TP_FLASH))
def test_an_outlet_temperature_outside_wilsons_domain_is_refused_on_wilson(model: str) -> None:
    assert isinstance(
        bind_revision_flowsheet(syn001_revision(model, outlet_temperature=290.0)), RevisionBinding
    )
    refused = bind_revision_flowsheet(wilson_revision(model, outlet_temperature=290.0))
    assert isinstance(refused, Unbound), refused
    assert (refused.kind, refused.implicated) == ("inadmissible", ("U",))
    assert refused.detail.startswith("value_outside_model_domain: U: ")
    assert refused.detail.endswith(
        "temperature 290.0 K is outside the declared domain [300.0, 400.0] K"
    )
