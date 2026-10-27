"""S11 WO-D1: the γ–φ faces of the five K02/T05 `syn001.*` units (S11.A67, S11.A68).

`docs/derivations/S11-units-design.md` §4.5 (ADR 0051). The shared `tp_state` helpers and the five
unit modules gain a branch on `composition_dependent(provider)`: a `wilson-ig-v1` provider gets
`GammaPhiLnKBlock` (fed by the liquid flows) and mixture enthalpy blocks, and the SYN-001 path is
unchanged. Here:

- **A67** the five modules' SYN-001 manifests equal the base's with
  `implementation_artifact.artifact_hash` removed (the module file's SHA-256, which D1's edits
  move); the rest of A67 is the identity gate and the unchanged K02/T05/T05b tests;
- **A68** on the real and the verification records, each unit's rows are the SYN-001 rows (ids,
  kinds, order, variables) read through γ–φ blocks, the K-block is fed by the liquid flows, a
  recording provider sees no `lnK` and no `h_<c>` request, and every row vanishes within its
  registered kind tolerance at the state the unit's own evaluator returns: the rows and the
  evaluator describe the same function.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from conftest import REPO_ROOT

from openflowsheet.canonical import document_sha256
from openflowsheet.compile.reference import row_values
from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Contribution,
    SpecificationError,
    UnitModel,
    Wiring,
    assemble,
    duty_id,
    flow_id,
    pressure_id,
    temperature_id,
)
from openflowsheet.models.syn001.blocks import EnthalpyFlowBlock, LnKBlock
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.flash import TPFlash, total_flow_id
from openflowsheet.models.syn001.gamma_phi_blocks import (
    GammaPhiLnKBlock,
    MixtureEnthalpyFlowBlock,
)
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.models.syn001.mixer import AdiabaticMixer
from openflowsheet.models.syn001.ph_flash import PHFlash
from openflowsheet.models.syn001.sink import ProductSink
from openflowsheet.models.syn001.tp_state import (
    equilibrium_block,
    liquid_flow_id,
    liquid_total_id,
    tp_state,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.models.syn001.valve import Valve
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider
from openflowsheet.verify.checks import KIND_TOLERANCE

CONTEXT = EvaluationContext(model_version="S11-WO-D1@" + "0" * 64, constants_sha256="0" * 64)
SYN001 = Syn001Provider()
RECORDS = {
    "real": REPO_ROOT / "benchmarks" / "s10" / "records.yaml",
    "verification": REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml",
}
#: The feed of every case: liquid at 330 K and 101 325 Pa on both record files (measured: the TP
#: state at 350 K is two-phase, with vapour fractions 0.876 (real) and 0.973 (verification)).
FEED_N = (0.4, 0.3, 0.3)
P_ATM = 101_325.0


# -- S11.A67: SYN-001's manifests ------------------------------------------------------------------

#: `document_sha256` of each manifest with `implementation_artifact.artifact_hash` removed,
#: measured at the base `01f95c92` (before D1) on the constructions below.
BASE_MANIFESTS = {
    "syn001.tp_heater": "7ed543dd9c058904a27b166000dffd1e6db494153be3578f9927644e492d6065",
    "syn001.tp_flash": "e19c5fae8a1cf40489db376510856da18e1f27d6dea8bb330a5d079e036f4919",
    "syn001.ph_flash": "4fa150bfe683d90d1abafd1f300158c8e32a1f9097a77bae0cf94835fcdbce40",
    "syn001.valve": "027b43e12fe9e5bdac909e02e536e0d7350fa00d7fd4e39cf5bdd2e981c56f00",
    "syn001.adiabatic_mixer": "318f428f269e05d6e6c4078e74dd0fd9ac02ba1a3599eee263bfa974c2600878",
}


def _without_artifact_hash(manifest: Mapping[str, Any]) -> dict[str, Any]:
    document = copy.deepcopy(dict(manifest))
    del document["implementation_artifact"]["artifact_hash"]
    return document


def test_a67_the_syn001_manifests_are_the_bases() -> None:
    units: tuple[Any, ...] = (
        TPHeater(unit_id="U-H", provider=SYN001, outlet_temperature=350.0, context=CONTEXT),
        TPFlash(unit_id="U-F", provider=SYN001, temperature=360.0, pressure=1e5, context=CONTEXT),
        PHFlash(unit_id="U-P", provider=SYN001, duty=0.0, context=CONTEXT),
        Valve(unit_id="U-V", provider=SYN001, outlet_pressure=5e4, context=CONTEXT),
        AdiabaticMixer(unit_id="U-M", provider=SYN001, context=CONTEXT),
    )
    assert {unit.model_id for unit in units} == set(BASE_MANIFESTS)
    for unit in units:
        assert (
            document_sha256(_without_artifact_hash(unit.manifest()))
            == (BASE_MANIFESTS[unit.model_id])
        ), unit.model_id


# -- the recording provider ------------------------------------------------------------------------


class Recording:
    """Forwards to a provider and records every property name, flash and other call it sees."""

    def __init__(self, inner: WilsonIdealGasProvider) -> None:
        self.inner = inner
        self.properties: list[str] = []
        self.calls: list[str] = []

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        self.calls.append("evaluate_phase")
        self.properties.extend(request.properties)
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        self.calls.append(f"flash:{request.specification}")
        return self.inner.flash(request, context)

    def __getattr__(self, name: str) -> Any:
        self.calls.append(name)
        return getattr(self.inner, name)


def _faces(provider: PropertyProvider) -> dict[str, Any]:
    """The three fields D2's binding passes off SYN-001 (S11 units design §4.5)."""
    described = provider.describe()
    return {
        "property_provider": described.provider_id,
        "reference_convention": described.reference_convention,
        "domain": {"T": described.domain["T"], "P": described.domain["P"]},
        "components": described.components,
    }


# -- the five cases --------------------------------------------------------------------------------


def _feed(
    unit_id: str, stream_n: Sequence[float], t: float, p: float, faces: Mapping[str, Any]
) -> FeedSource:
    return FeedSource(unit_id=unit_id, flows=tuple(stream_n), temperature=t, pressure=p, **faces)


def _stream_values(stream: str, state: StreamState, components: Sequence[str]) -> dict[str, float]:
    values = {flow_id(stream, c): n for c, n in zip(components, state.n, strict=True)}
    values[temperature_id(stream)] = state.temperature
    values[pressure_id(stream)] = state.pressure
    return values


def _lifted_values(
    stream: str, vapor: StreamState, liquid: StreamState, components: Sequence[str]
) -> dict[str, float]:
    values: dict[str, float] = {}
    for c, v, liq in zip(components, vapor.n, liquid.n, strict=True):
        values[vapor_flow_id(stream, c)] = v
        values[liquid_flow_id(stream, c)] = liq
    values[vapor_total_id(stream)] = sum(vapor.n)
    values[liquid_total_id(stream)] = sum(liquid.n)
    return values


def _split(provider: PropertyProvider, state: StreamState) -> tuple[StreamState, StreamState]:
    answer = tp_state(provider, state, CONTEXT)
    assert answer.status == "ok" and answer.vapor is not None and answer.liquid is not None
    return answer.vapor, answer.liquid


class Case:
    """One flowsheet around the unit under test, and the state its evaluators put it at."""

    def __init__(
        self,
        unit: Any,
        units: Sequence[UnitModel],
        wiring: Mapping[str, Wiring],
        streams: Sequence[str],
        values: Mapping[str, float],
    ) -> None:
        self.unit = unit
        self.units = tuple(units)
        self.wiring = dict(wiring)
        self.streams = tuple(streams)
        self.values = dict(values)

    def spec(self, components: Sequence[str]) -> ProblemSpec:
        return assemble(
            label="S11-WO-D1",
            units=self.units,
            wiring=self.wiring,
            streams=self.streams,
            components=components,
        )


def heater_flash_case(provider: PropertyProvider, model: str) -> Case:
    """GP-C1's shape: a liquid feed → `tp_heater` (lifted outlet) → `tp_flash` at the same T."""
    faces = _faces(provider)
    components = faces["components"]
    feed = StreamState(n=FEED_N, temperature=330.0, pressure=P_ATM)
    heater = TPHeater(
        unit_id="U-H", provider=provider, outlet_temperature=350.0, context=CONTEXT, **faces
    )
    flash = TPFlash(
        unit_id="U-F",
        provider=provider,
        temperature=350.0,
        pressure=P_ATM,
        context=CONTEXT,
        **faces,
    )
    heated = heater.evaluate({"inlet": (feed,)}, CONTEXT)
    assert heated.status == "ok", heated.message
    assert heated.phase_signature == "TWO_PHASE"
    outlet = heated.outlets["outlet"]
    flashed = flash.evaluate({"inlet": (outlet,)}, CONTEXT)
    assert flashed.status == "ok", flashed.message
    assert heated.duty is not None and flashed.duty is not None
    vapor, liquid = flashed.outlets["vapor"], flashed.outlets["liquid"]
    values = {
        **_stream_values("S1", feed, components),
        **_stream_values("S2", outlet, components),
        **_lifted_values("S2", *_split(provider, outlet), components),
        **_stream_values("S3", vapor, components),
        **_stream_values("S4", liquid, components),
        total_flow_id("S3"): sum(vapor.n),
        total_flow_id("S4"): sum(liquid.n),
        duty_id("U-H"): heated.duty,
        duty_id("U-F"): flashed.duty,
    }
    return Case(
        heater if model == "syn001.tp_heater" else flash,
        (
            _feed("U-FEED", FEED_N, 330.0, P_ATM, faces),
            heater,
            flash,
            ProductSink(unit_id="U-V", **faces),
            ProductSink(unit_id="U-L", **faces),
        ),
        {
            "U-FEED": Wiring({"outlet": ("S1",)}),
            "U-H": Wiring({"inlet": ("S1",), "outlet": ("S2",)}),
            "U-F": Wiring({"inlet": ("S2",), "vapor": ("S3",), "liquid": ("S4",)}),
            "U-V": Wiring({"inlet": ("S3",)}),
            "U-L": Wiring({"inlet": ("S4",)}),
        },
        ("S1", "S2", "S3", "S4"),
        values,
    )


def valve_case(provider: PropertyProvider) -> Case:
    """A liquid at 360 K and 180 kPa throttled to 101 325 Pa (lifted outlet)."""
    faces = _faces(provider)
    components = faces["components"]
    feed = StreamState(n=FEED_N, temperature=360.0, pressure=180_000.0)
    valve = Valve(unit_id="U-V", provider=provider, outlet_pressure=P_ATM, context=CONTEXT, **faces)
    answer, closure = valve.evaluate_with_closure({"inlet": (feed,)}, CONTEXT)
    assert answer.status == "ok", answer.message
    assert closure is not None and closure.split is not None
    assert closure.split.vapor is not None and closure.split.liquid is not None
    outlet = answer.outlets["outlet"]
    values = {
        **_stream_values("S1", feed, components),
        **_stream_values("S2", outlet, components),
        **_lifted_values("S2", closure.split.vapor, closure.split.liquid, components),
    }
    return Case(
        valve,
        (
            _feed("U-FEED", FEED_N, 360.0, 180_000.0, faces),
            valve,
            ProductSink(unit_id="U-K", **faces),
        ),
        {
            "U-FEED": Wiring({"outlet": ("S1",)}),
            "U-V": Wiring({"inlet": ("S1",), "outlet": ("S2",)}),
            "U-K": Wiring({"inlet": ("S2",)}),
        },
        ("S1", "S2"),
        values,
    )


def ph_flash_case(provider: PropertyProvider) -> Case:
    """A liquid feed at 330 K given the duty that heats it to two phases at 350 K."""
    faces = _faces(provider)
    components = faces["components"]
    feed = StreamState(n=FEED_N, temperature=330.0, pressure=P_ATM)
    hot = tp_state(provider, feed, CONTEXT, temperature=350.0)
    cold = tp_state(provider, feed, CONTEXT)
    assert hot.enthalpy_flow is not None and cold.enthalpy_flow is not None
    duty = hot.enthalpy_flow - cold.enthalpy_flow
    unit = PHFlash(unit_id="U-P", provider=provider, duty=duty, context=CONTEXT, **faces)
    answer, closure = unit.evaluate_with_closure({"inlet": (feed,)}, CONTEXT)
    assert answer.status == "ok", answer.message
    assert answer.phase_signature == "TWO_PHASE"
    vapor, liquid = answer.outlets["vapor"], answer.outlets["liquid"]
    values = {
        **_stream_values("S1", feed, components),
        **_stream_values("S2", vapor, components),
        **_stream_values("S3", liquid, components),
        total_flow_id("S2"): sum(vapor.n),
        total_flow_id("S3"): sum(liquid.n),
        duty_id("U-P"): duty,
    }
    return Case(
        unit,
        (
            _feed("U-FEED", FEED_N, 330.0, P_ATM, faces),
            unit,
            ProductSink(unit_id="U-V", **faces),
            ProductSink(unit_id="U-L", **faces),
        ),
        {
            "U-FEED": Wiring({"outlet": ("S1",)}),
            "U-P": Wiring({"inlet": ("S1",), "vapor": ("S2",), "liquid": ("S3",)}),
            "U-V": Wiring({"inlet": ("S2",)}),
            "U-L": Wiring({"inlet": ("S3",)}),
        },
        ("S1", "S2", "S3"),
        values,
    )


def mixer_case(provider: PropertyProvider) -> Case:
    """Two liquids at 320 K and 340 K, 101 325 Pa."""
    faces = _faces(provider)
    components = faces["components"]
    first = StreamState(n=(0.6, 0.2, 0.2), temperature=320.0, pressure=P_ATM)
    second = StreamState(n=(0.1, 0.4, 0.5), temperature=340.0, pressure=P_ATM)
    mixer = AdiabaticMixer(unit_id="U-M", provider=provider, context=CONTEXT, **faces)
    answer = mixer.evaluate({"inlet": (first, second)}, CONTEXT)
    assert answer.status == "ok", answer.message
    assert answer.phase_signature == "LIQUID"
    assert answer.iterations > 0
    outlet = answer.outlets["outlet"]
    assert 320.0 < outlet.temperature < 340.0
    values = {
        **_stream_values("S1", first, components),
        **_stream_values("S2", second, components),
        **_stream_values("S3", outlet, components),
    }
    return Case(
        mixer,
        (
            _feed("U-F1", first.n, 320.0, P_ATM, faces),
            _feed("U-F2", second.n, 340.0, P_ATM, faces),
            mixer,
            ProductSink(unit_id="U-K", **faces),
        ),
        {
            "U-F1": Wiring({"outlet": ("S1",)}),
            "U-F2": Wiring({"outlet": ("S2",)}),
            "U-M": Wiring({"inlet": ("S1", "S2"), "outlet": ("S3",)}),
            "U-K": Wiring({"inlet": ("S3",)}),
        },
        ("S1", "S2", "S3"),
        values,
    )


MODELS = (
    "syn001.tp_heater",
    "syn001.tp_flash",
    "syn001.ph_flash",
    "syn001.valve",
    "syn001.adiabatic_mixer",
)


def build(model: str, provider: PropertyProvider) -> Case:
    if model in ("syn001.tp_heater", "syn001.tp_flash"):
        return heater_flash_case(provider, model)
    if model == "syn001.valve":
        return valve_case(provider)
    if model == "syn001.ph_flash":
        return ph_flash_case(provider)
    return mixer_case(provider)


def _rebuilt_on_syn001(unit: Any) -> Any:
    """The same unit on the SYN-001 provider (components kept): the SYN-001 path's rows."""
    return type(unit)(
        **{
            name: getattr(unit, name)
            for name in unit.__dataclass_fields__
            if name not in ("provider", "property_provider", "reference_convention", "domain")
        },
        provider=SYN001,
    )


# -- S11.A68 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("records", sorted(RECORDS))
@pytest.mark.parametrize("model", MODELS)
def test_a68_the_unit_reads_its_rows_through_gamma_phi_blocks(model: str, records: str) -> None:
    provider = Recording(WilsonIdealGasProvider(RECORDS[records]))
    case = build(model, provider)
    unit = case.unit
    assert unit.model_id == model
    components = unit.components
    wiring = case.wiring[unit.unit_id]
    ours: Contribution = unit.contribute(wiring, components)
    theirs: Contribution = _rebuilt_on_syn001(unit).contribute(wiring, components)

    # The SYN-001 rows, ids, kinds, order and variables; only the blocks differ.
    assert [row.equation_id for row in ours.equations] == [
        row.equation_id for row in theirs.equations
    ]
    assert [row.origin for row in ours.equations] == [row.origin for row in theirs.equations]
    assert ours.variable_ids == theirs.variable_ids
    assert dict(ours.variable_kinds) == dict(theirs.variable_kinds)
    assert dict(ours.row_kinds) == dict(theirs.row_kinds)
    assert [block.block_id for block in ours.blocks] == [block.block_id for block in theirs.blocks]

    for block in ours.blocks:
        assert not isinstance(block, LnKBlock | EnthalpyFlowBlock), block.block_id
        assert isinstance(block, GammaPhiLnKBlock | MixtureEnthalpyFlowBlock), block.block_id
        inputs = ours.block_inputs[block.block_id]
        assert len(inputs) == len(components) + 2
        if isinstance(block, GammaPhiLnKBlock):
            # Fed by the liquid flows of the stream whose equilibrium it closes, then T, P.
            # A flash's K-block is named after its vapour product and reads its liquid product;
            # a lifted stream's reads the stream's own lifted liquid.
            stream = block.block_id.removeprefix("lnK_")
            if "liquid" in wiring.streams:
                expected = tuple(flow_id(wiring.one("liquid"), c) for c in components)
            else:
                expected = tuple(liquid_flow_id(stream, c) for c in components)
            assert tuple(inputs[: len(components)]) == expected, block.block_id
            assert tuple(inputs[-2:]) == (temperature_id(stream), pressure_id(stream))
    k_blocks = [block for block in ours.blocks if isinstance(block, GammaPhiLnKBlock)]
    assert len(k_blocks) == (0 if model == "syn001.adiabatic_mixer" else 1)

    # The flowsheet's rows and variables are those of the SYN-001 flowsheet of the same shape,
    # pressure rows that restate a feed's pressure (FLASH-P inlet, MIX-pressure) included.
    spec = case.spec(components)
    syn = Case(
        None,
        tuple(_rebuilt_on_syn001(u) if hasattr(u, "provider") else u for u in case.units),
        case.wiring,
        case.streams,
        case.values,
    ).spec(components)
    assert len(spec.equation_ids) == len(syn.equation_ids)
    assert spec.equation_ids == syn.equation_ids
    assert spec.variable_ids == syn.variable_ids
    assert dict(spec.row_kinds) == dict(syn.row_kinds)

    # The rows vanish at the evaluator's state, within each row's registered kind tolerance.
    rows = row_values(spec, case.values)
    kinds = spec.row_kinds
    worst = {
        equation_id: value
        for equation_id, value in rows.items()
        if not abs(value) <= KIND_TOLERANCE[kinds[equation_id]]
    }
    assert worst == {}

    # Every property the provider was asked for is declared; nothing asked `lnK` or `h_<c>`.
    described = provider.describe()
    requested = set(provider.properties)
    assert "lnK" not in requested
    assert not any(name.startswith("h_") for name in requested), requested
    assert requested <= set(described.properties), requested - set(described.properties)
    assert "h" in requested
    if model != "syn001.adiabatic_mixer":
        assert any(name.startswith("lnphi_") for name in requested)


@pytest.mark.parametrize("records", sorted(RECORDS))
def test_a68_the_manifest_names_the_bound_provider(records: str) -> None:
    provider = WilsonIdealGasProvider(RECORDS[records])
    described = provider.describe()
    case = heater_flash_case(provider, "syn001.tp_heater")
    for unit in case.units[1:3]:
        manifest = unit.manifest()
        requirements = manifest["execution_requirements"]
        assert requirements["property_provider"] == described.provider_id
        assert requirements["reference_convention"] == described.reference_convention
        domain = manifest["validity"]["domain"]
        assert tuple(domain["components"]) == described.components
        assert (domain["temperature_K"]["min"], domain["temperature_K"]["max"]) == (
            described.domain["T"]
        )
        assert (domain["pressure_Pa"]["min"], domain["pressure_Pa"]["max"]) == (
            described.domain["P"]
        )


def test_the_equilibrium_block_dispatches_on_the_form() -> None:
    wilson = WilsonIdealGasProvider(RECORDS["verification"])
    components = wilson.describe().components
    liquid = tuple(f"S.liq.{c}" for c in components)
    block, inputs = equilibrium_block(
        wilson,
        components,
        CONTEXT,
        block_id="lnK_S",
        temperature="S.T",
        pressure="S.P",
        liquid=liquid,
    )
    assert isinstance(block, GammaPhiLnKBlock)
    assert inputs == (*liquid, "S.T", "S.P")
    block, inputs = equilibrium_block(
        SYN001,
        ("A", "B", "C"),
        CONTEXT,
        block_id="lnK_S",
        temperature="S.T",
        pressure="S.P",
        liquid=("S.liq.A", "S.liq.B", "S.liq.C"),
    )
    assert isinstance(block, LnKBlock)
    assert inputs == ("S.T", "S.P")


@pytest.mark.parametrize("records", sorted(RECORDS))
def test_the_range_checks_read_the_bound_domain(records: str) -> None:
    """A heater at 410 K: outside SYN-001's domain, and refused or admitted by the bound one."""
    provider = WilsonIdealGasProvider(RECORDS[records])
    faces = _faces(provider)
    t_max = faces["domain"]["T"][1]
    TPHeater(unit_id="U-H", provider=provider, outlet_temperature=t_max, context=CONTEXT, **faces)
    with pytest.raises(SpecificationError, match="outside the declared domain"):
        TPHeater(
            unit_id="U-H",
            provider=provider,
            outlet_temperature=t_max + 1.0,
            context=CONTEXT,
            **faces,
        )
