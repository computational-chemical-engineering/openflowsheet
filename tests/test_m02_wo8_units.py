"""M02 WO-8.2: the six C1 units, their manifests, their binding, and their causal evaluates
(design note §8, §14.2 B12, B16, B17; register R-230, R-254, R-256).

Expectations: the provider's own TP flash and enthalpies (M01.A05–A22 verified them against 50-digit
closed forms) for the evaluates; T01's structural analysis for squareness; B16's refusal text.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from m02_c1_support import connection, feed_specifications, instance, revision, specification
from test_schemas_p01 import schema_errors

from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BASES,
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.canonical import file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.analysis import analyse
from openflowsheet.models.c1 import TAU_DEW, feed, flash, heater, mixer, sink, splitter
from openflowsheet.models.c1.phase import classify
from openflowsheet.models.c1.reactor import MODEL_IDS, PORTS
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.thermo.pr_c1 import COMPONENTS, PrC1Provider

FLASH: Mapping[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")[
    "closed_form"
]["flash_states"]
CONTEXT = EvaluationContext(model_version="m02-wo8-units", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
MODULES = {
    feed.MODEL_ID: feed,
    sink.MODEL_ID: sink,
    splitter.MODEL_ID: splitter,
    mixer.MODEL_ID: mixer,
    heater.MODEL_ID: heater,
    flash.MODEL_ID: flash,
}
#: F1's composition, as a reactor-outlet-like vapour.
Z = (0.6, 0.2, 0.165, 0.015, 0.02)
P = 1.0e7


# -- registry and manifests -----------------------------------------------------------------------


def test_the_six_c1_units_bind_through_the_shared_registry() -> None:
    """R-280's join: the C1 builders are in `MODEL_BUILDERS` and `MODEL_SIGNATURES`, which
    `list_models` serves, on the C1 basis only (R-288); the interim registry is gone."""
    from openflowsheet.application import revision_binding  # noqa: PLC0415

    c1 = {model for model in MODEL_BUILDERS if model.startswith("c1.")}
    assert c1 == {model for model in MODEL_SIGNATURES if model.startswith("c1.")}
    assert c1 == set(MODULES) | set(MODEL_IDS)
    assert all(MODEL_BASES[model] == {"pr-c1-v1"} for model in c1)
    for model_id in c1:
        signature = MODEL_SIGNATURES[model_id]
        assert signature.ports == (MODULES[model_id].PORTS if model_id in MODULES else PORTS)
    for name in ("C1_MODEL_BUILDERS", "C1_MODEL_SIGNATURES", "_builder"):
        assert not hasattr(revision_binding, name), name


def _units() -> dict[str, Any]:
    context = CONTEXT
    return {
        feed.MODEL_ID: feed.FeedSource("U", Z, 300.0, P),
        sink.MODEL_ID: sink.ProductSink("U"),
        splitter.MODEL_ID: splitter.StreamSplitter("U", 0.98),
        mixer.MODEL_ID: mixer.AdiabaticMixer("U", PROVIDER, context),
        heater.MODEL_ID: heater.TPHeater("U", PROVIDER, 673.15, context),
        flash.MODEL_ID: flash.TPFlash("U", PROVIDER, 253.15, P, context),
    }


@pytest.mark.parametrize("model_id", list(MODULES))
def test_each_manifest_is_valid_tested_and_carries_no_syn001_constant(model_id: str) -> None:
    """The reuse check (design note §8): SYN-001's classes are not reused, because their manifests
    and row origins carry SYN-001 constants. The C1 classes carry none."""
    unit = _units()[model_id]
    document = dict(unit.manifest())
    assert schema_errors("model_manifest", document) == []
    assert document["id"] == model_id and document["status"] == "tested"
    assert document["introduced_by_package"] == "M02"
    artifact = document["implementation_artifact"]
    assert artifact["module"] == MODULES[model_id].__name__
    assert artifact["artifact_hash"] == file_sha256(Path(MODULES[model_id].__file__))
    requirements = document["execution_requirements"]
    assert requirements["property_provider"] == "pr-c1-v1"
    assert requirements["reference_convention"] == "PR-C1-ref-v1"
    domain = document["validity"]["domain"]
    assert domain["temperature_K"] == {"min": 200.0, "max": 1000.0}
    assert domain["pressure_Pa"] == {"min": 1.0e4, "max": 3.0e7}
    assert domain["components"] == list(COMPONENTS)
    text = json.dumps(document)
    assert "syn001" not in text and "SYN-001-ref" not in text


def _wiring(model_id: str) -> dict[str, tuple[str, ...]]:
    return {
        feed.MODEL_ID: {"outlet": ("S1",)},
        sink.MODEL_ID: {"inlet": ("S1",)},
        splitter.MODEL_ID: {"inlet": ("S1",), "recycle": ("S2",), "purge": ("S3",)},
        mixer.MODEL_ID: {"inlet": ("S1", "S2"), "outlet": ("S3",)},
        heater.MODEL_ID: {"inlet": ("S1",), "outlet": ("S2",)},
        flash.MODEL_ID: {"inlet": ("S1",), "vapor": ("S2",), "liquid": ("S3",)},
    }[model_id]


@pytest.mark.parametrize("model_id", list(MODULES))
def test_every_row_comes_from_a_declared_equation_with_a_kind(model_id: str) -> None:
    from openflowsheet.models import Wiring, origin

    unit = _units()[model_id]
    contribution = unit.contribute(Wiring(_wiring(model_id)), COMPONENTS)
    declared = {origin(model_id, equation.equation_id) for equation in unit.declared_equations()}
    origins = {equation.origin for equation in contribution.equations}
    assert origins <= declared | {origin(model_id, "lifting")}
    assert origins >= declared
    for equation in contribution.equations:
        assert equation.origin.startswith(f"{model_id}#")
        assert equation.equation_id in contribution.row_kinds


def test_the_flash_authors_b12s_rows() -> None:
    from openflowsheet.models import Wiring

    contribution = _units()[flash.MODEL_ID].contribute(Wiring(_wiring(flash.MODEL_ID)), COMPONENTS)
    kinds = dict(contribution.row_kinds)
    family = [row for row in (e.equation_id for e in contribution.equations) if "C1FL-equ" in row]
    assert family == [f"U:C1FL-equilibrium:{c}" for c in COMPONENTS]
    assert kinds["U:C1FL-equilibrium:NH3"] == "molar_flow_squared"
    for c in ("H2", "N2", "Ar", "CH4"):
        assert kinds[f"U:C1FL-equilibrium:{c}"] == "molar_flow"
    assert [e.equation_id for e in contribution.equations if "C1FL-mole" in e.equation_id] == [
        f"U:C1FL-mole:{c}" for c in COMPONENTS
    ]
    assert {e.equation_id for e in contribution.equations} >= {
        "U:Ndef:vapor",
        "U:Ndef:liquid",
        "U:C1FL-T:vapor",
        "U:C1FL-T:liquid",
        "U:C1FL-P:vapor",
        "U:C1FL-P:liquid",
        "U:C1FL-P:inlet",
        "U:C1FL-duty",
    }
    assert contribution.variable_ids == ("U.Q", "S2.N", "S3.N")
    assert {block.block_id for block in contribution.blocks} == {
        "S1_Hdot_V",
        "S2_Hdot_V",
        "S3_Hdot_L",
        "S2_lnphi_NH3_V",
        "S3_lnphi_NH3_L",
    }


def test_the_units_refuse_another_basis() -> None:
    from openflowsheet.models import SpecificationError
    from openflowsheet.thermo.syn001 import Syn001Provider

    with pytest.raises(SpecificationError, match="pr-c1-v1"):
        heater.TPHeater("U", Syn001Provider(), 673.15, CONTEXT)
    with pytest.raises(SpecificationError, match="C1 unit is built over"):
        sink.ProductSink("U", ("A", "B", "C"))


# -- binding: each unit square in a minimal flowsheet ---------------------------------------------


def _flash_specifications(vapor: str, liquid: str, t: float, p: float) -> list[dict[str, Any]]:
    return [
        specification(f"SPEC-{vapor}-T", "connection", vapor, "state.T", t, "temperature"),
        specification(f"SPEC-{vapor}-P", "connection", vapor, "state.P", p, "pressure"),
        specification(f"SPEC-{liquid}-T", "connection", liquid, "state.T", t, "temperature"),
        specification(f"SPEC-{liquid}-P", "connection", liquid, "state.P", p, "pressure"),
    ]


def minimal(model_id: str) -> dict[str, Any]:
    """`model_id` in the smallest flowsheet that closes it: feeds in, sinks out."""
    feeds = feed_specifications("S1", Z, 673.15, P)
    if model_id == feed.MODEL_ID or model_id == sink.MODEL_ID:
        return revision(
            [instance("F", "c1.feed_source"), instance("K", "c1.product_sink")],
            [connection("S1", ("F", "outlet"), ("K", "inlet"))],
            feeds,
        )
    if model_id == heater.MODEL_ID:
        return revision(
            [
                instance("F", "c1.feed_source"),
                instance("U", model_id),
                instance("K", "c1.product_sink"),
            ],
            [
                connection("S1", ("F", "outlet"), ("U", "inlet")),
                connection("S2", ("U", "outlet"), ("K", "inlet")),
            ],
            [
                *feeds,
                specification("SPEC-S2-T", "connection", "S2", "state.T", 300.0, "temperature"),
            ],
        )
    if model_id == mixer.MODEL_ID:
        return revision(
            [
                instance("F", "c1.feed_source"),
                instance("G", "c1.feed_source"),
                instance("U", model_id),
                instance("K", "c1.product_sink"),
            ],
            [
                connection("S1", ("F", "outlet"), ("U", "inlet")),
                connection("S2", ("G", "outlet"), ("U", "inlet")),
                connection("S3", ("U", "outlet"), ("K", "inlet")),
            ],
            [*feeds, *feed_specifications("S2", (0.75, 0.25, 0.0, 0.0, 0.0), 300.0, P)],
        )
    if model_id == splitter.MODEL_ID:
        return revision(
            [
                instance("F", "c1.feed_source"),
                instance("U", model_id, {"split_fraction": _fraction(0.98)}),
                instance("K", "c1.product_sink"),
                instance("L", "c1.product_sink"),
            ],
            [
                connection("S1", ("F", "outlet"), ("U", "inlet")),
                connection("S2", ("U", "recycle"), ("K", "inlet")),
                connection("S3", ("U", "purge"), ("L", "inlet")),
            ],
            feeds,
        )
    assert model_id == flash.MODEL_ID
    return revision(
        [
            instance("F", "c1.feed_source"),
            instance("U", model_id),
            instance("K", "c1.product_sink"),
            instance("L", "c1.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("U", "inlet")),
            connection("S2", ("U", "vapor"), ("K", "inlet")),
            connection("S3", ("U", "liquid"), ("L", "inlet"), "liquid"),
        ],
        [*feed_specifications("S1", Z, 268.15, P), *_flash_specifications("S2", "S3", 268.15, P)],
    )


def _fraction(value: float) -> dict[str, Any]:
    return {
        "value": value,
        "unit": "1",
        "dimension": [0, 0, 0, 0, 0, 0, 0],
        "kind": "dimensionless",
        "meaning": "test",
        "role": "fixed",
    }


def _bind(document: Mapping[str, Any]) -> RevisionBinding:
    bound = bind_revision_flowsheet(document)
    assert not isinstance(bound, Unbound), bound
    return bound


@pytest.mark.parametrize("model_id", list(MODULES))
def test_each_unit_is_square_in_a_minimal_flowsheet(model_id: str) -> None:
    """T01's structural analysis of the bound declaration: STRUCTURALLY_CLOSED. (The flash's
    `C1FL-P:inlet` and the mixer's second pressure row restate a pressure the feed fixes, as
    SYN-001's do; the analysis certifies them.)"""
    binding = _bind(minimal(model_id))
    model_version, constants = declaration_identity(binding.spec)
    report = analyse(
        binding.spec,
        binding.graph,
        model_version=model_version,
        constants_sha256=constants,
        specification_ids={},
        row_units=binding.row_units,
    )
    assert report.finding == "STRUCTURALLY_CLOSED", (report.finding, report.implicated_objects)


@pytest.mark.parametrize("model_id", list(MODULES))
def test_each_minimal_flowsheet_traverses(model_id: str) -> None:
    traversed = _bind(minimal(model_id)).flowsheet.traverse({})
    assert traversed.status == "ok", (traversed.failed_unit, traversed.code)


def test_a_c1_model_in_a_syn001_revision_is_refused() -> None:
    """A `c1.*` model binds only on the C1 basis: in a SYN-001 revision the binder refuses it
    `model_unsupported` from `MODEL_BASES`, its hint naming the SYN-001 model of the same function
    (R-288; before the join the builder refused it, build log D37 (d))."""
    flows = [
        specification(
            f"SPEC-S1-n-{c}", "connection", "S1", "state.n", 1.0, "molar_flow", component=c
        )
        for c in ("A", "B", "C")
    ]
    document = revision(
        [instance("F", "c1.feed_source"), instance("K", "c1.product_sink")],
        [connection("S1", ("F", "outlet"), ("K", "inlet"))],
        [
            *flows,
            specification("SPEC-S1-T", "connection", "S1", "state.T", 300.0, "temperature"),
            specification("SPEC-S1-P", "connection", "S1", "state.P", 1.0e5, "pressure"),
        ],
        components=("A", "B", "C"),
        record_source="benchmarks/syn001/components.yaml",
    )
    assert bind_revision_flowsheet(document) == Unbound(
        "unsupported",
        "model_unsupported(c1.feed_source)",
        hint=(
            "c1.feed_source binds on the pr-c1-v1 basis only, not on this revision's syn001; "
            "on syn001 the same function is syn001.feed_source"
        ),
    )


# -- the causal evaluates: B16's refusals and the flash's split -----------------------------------


def _stream(n: Sequence[float], t: float, p: float = P) -> StreamState:
    return StreamState(n=tuple(n), temperature=t, pressure=p)


def _h(n: Sequence[float], t: float, phase: Any, p: float = P) -> float:
    if all(value == 0.0 for value in n):
        return 0.0
    result = PROVIDER.evaluate_phase(
        PropertyRequest(state=_stream(n, t, p), phase=phase, properties=("h",)), CONTEXT
    )
    assert result.status == "ok", result.message
    return sum(n) * result.values["h"]


#: G7 (e): y_NH3 = 0.15, the rest F1's light gases in their proportions.
Y15 = (0.85 * 0.6 / 0.835, 0.85 * 0.2 / 0.835, 0.15, 0.85 * 0.015 / 0.835, 0.85 * 0.02 / 0.835)


def test_g7e_the_heater_into_the_two_phase_region_is_refused_by_its_evaluate() -> None:
    """G7 (e): the heater to 253.15 K at 1e7 Pa with y_NH3 = 0.15 refuses
    `vapour_phase_inadmissible`, naming the outlet and its liquid NH3 fraction."""
    unit = heater.TPHeater("U", PROVIDER, 253.15, CONTEXT)
    answer = unit.evaluate({"inlet": (_stream(Y15, 673.15),)}, CONTEXT)
    regime, value, _ = classify(PROVIDER, CONTEXT, Y15, 253.15, P)
    assert regime == "TWO_PHASE" and value > TAU_DEW
    assert answer.status == "unsupported"
    assert answer.message == (
        f"vapour_phase_inadmissible: outlet: liquid NH3 fraction {value:.3g} > 1e-10"
    )
    assert not answer.outlets and answer.duty is None


def test_g7e_the_traversal_stops_at_that_heater_with_its_refusal() -> None:
    """G7 (e), the traversal's outcome recorded: the pass ends `unsupported` at the heater, its
    code the evaluate's first line, as it ends at SYN-001's mixer."""
    document = minimal(heater.MODEL_ID)
    for entry in document["specifications"]:
        if entry["id"] == "SPEC-S2-T":
            entry["value"] = 253.15
        if entry["target"].get("component") is not None:
            entry["value"] = Y15[COMPONENTS.index(entry["target"]["component"])]
    traversed = _bind(document).flowsheet.traverse({})
    assert (traversed.status, traversed.failed_unit) == ("unsupported", "U")
    assert traversed.code.startswith("vapour_phase_inadmissible: outlet: liquid NH3 fraction")


def test_the_heater_refuses_a_two_phase_inlet_and_reads_a_pure_nh3_liquid_as_liquid() -> None:
    unit = heater.TPHeater("U", PROVIDER, 673.15, CONTEXT)
    answer = unit.evaluate({"inlet": (_stream(Y15, 253.15),)}, CONTEXT)
    assert answer.status == "unsupported"
    assert answer.message.startswith("vapour_phase_inadmissible: inlet: liquid NH3 fraction ")
    liquid = unit.evaluate({"inlet": (_stream((0.0, 0.0, 1.0, 0.0, 0.0), 268.15),)}, CONTEXT)
    assert (liquid.status, liquid.message) == (
        "unsupported",
        "vapour_phase_inadmissible: inlet: LIQUID",
    )


def test_the_heater_evaluates_a_vapour_and_a_dormant_inlet() -> None:
    unit = heater.TPHeater("U", PROVIDER, 300.0, CONTEXT)
    answer = unit.evaluate({"inlet": (_stream(Z, 673.15),)}, CONTEXT)
    assert answer.status == "ok" and answer.phase_signature == "VAPOR"
    assert answer.outlets["outlet"] == _stream(Z, 300.0)
    assert answer.duty == _h(Z, 300.0, "VAPOR") - _h(Z, 673.15, "VAPOR")
    dormant = unit.evaluate({"inlet": (_stream((0.0,) * 5, 673.15),)}, CONTEXT)
    assert dormant.status == "ok" and dormant.phase_signature == "ZERO_FLOW"
    assert dormant.duty == 0.0 and dormant.outlets["outlet"] == _stream((0.0,) * 5, 300.0)


def test_the_mixer_closes_its_energy_balance_in_the_vapour() -> None:
    unit = mixer.AdiabaticMixer("U", PROVIDER, CONTEXT)
    hot, cold = _stream(Z, 673.15), _stream((0.75, 0.25, 0.0, 0.0, 0.0), 300.0)
    answer = unit.evaluate({"inlet": (hot, cold)}, CONTEXT)
    assert answer.status == "ok" and answer.phase_signature == "VAPOR"
    outlet = answer.outlets["outlet"]
    assert outlet.n == tuple(a + b for a, b in zip(Z, cold.n, strict=True))
    assert 300.0 < outlet.temperature < 673.15
    target = _h(Z, 673.15, "VAPOR") + _h(cold.n, 300.0, "VAPOR")
    assert abs(_h(outlet.n, outlet.temperature, "VAPOR") - target) <= 1e-9 * abs(target)


def test_the_mixer_with_equal_inlet_temperatures_widens_its_bracket() -> None:
    """Peng–Robinson mixes non-ideally: the outlet is not exactly the inlets' temperature, and the
    closure still finds it."""
    unit = mixer.AdiabaticMixer("U", PROVIDER, CONTEXT)
    a, b = (
        _stream((0.0, 0.0, 0.2, 0.0, 0.0), 350.0, 2.0e6),
        _stream((0.75, 0.25, 0, 0, 0), 350.0, 2.0e6),
    )
    answer = unit.evaluate({"inlet": (a, b)}, CONTEXT)
    assert answer.status == "ok"
    outlet = answer.outlets["outlet"]
    target = _h(a.n, 350.0, "VAPOR", 2.0e6) + _h(b.n, 350.0, "VAPOR", 2.0e6)
    assert outlet.temperature != 350.0
    got = _h(outlet.n, outlet.temperature, "VAPOR", 2.0e6)
    assert abs(got - target) <= 1e-9 * abs(target)


def test_g7e_the_mixer_outlet_forced_two_phase_is_refused() -> None:
    """A cold light-gas vapour and a warm NH3 vapour, each VAPOR, mix into a vapour past its dew
    point: the evaluate refuses the outlet (B16)."""
    unit = mixer.AdiabaticMixer("U", PROVIDER, CONTEXT)
    gas = _stream((0.75, 0.25, 0.0, 0.0, 0.0), 210.0, 2.0e6)
    ammonia = _stream((0.0, 0.0, 1.0, 0.0, 0.0), 350.0, 2.0e6)
    for stream in (gas, ammonia):
        regime, _, _ = classify(PROVIDER, CONTEXT, stream.n, stream.temperature, stream.pressure)
        assert regime == "VAPOR"
    answer = unit.evaluate({"inlet": (gas, ammonia)}, CONTEXT)
    assert answer.status == "unsupported"
    assert answer.message.startswith("vapour_phase_inadmissible: outlet: liquid NH3 fraction ")


def test_the_mixer_with_every_inlet_dormant_labels_its_outlet() -> None:
    unit = mixer.AdiabaticMixer("U", PROVIDER, CONTEXT)
    answer = unit.evaluate(
        {"inlet": (_stream((0.0,) * 5, 280.0), _stream((0.0,) * 5, 300.0))}, CONTEXT
    )
    assert answer.status == "ok" and answer.phase_signature == "ZERO_FLOW"
    assert answer.outlets["outlet"] == _stream((0.0,) * 5, 280.0)


def _flash(fid: str) -> tuple[Any, Any]:
    state = FLASH[fid]
    n, t, p = tuple(state["n_mol_s"]), state["T_K"], state["P_Pa"]
    unit = flash.TPFlash("U", PROVIDER, t, p, CONTEXT)
    answer = unit.evaluate({"inlet": (_stream(n, t, p),)}, CONTEXT)
    result = PROVIDER.flash(FlashRequest(state=_stream(n, t, p)), CONTEXT)
    return answer, result


@pytest.mark.parametrize("fid", ["F1", "F11"])
def test_the_flash_evaluates_a_two_phase_feed_as_the_providers_split(fid: str) -> None:
    answer, result = _flash(fid)
    state = FLASH[fid]
    t, p = state["T_K"], state["P_Pa"]
    assert answer.status == "ok" and answer.phase_signature == "TWO_PHASE"
    assert answer.outlets["vapor"] == result.vapor and answer.outlets["liquid"] == result.liquid
    liquid = answer.outlets["liquid"].n
    assert liquid[0] == liquid[1] == liquid[3] == liquid[4] == 0.0
    n = tuple(state["n_mol_s"])
    expected = (_h(result.vapor.n, t, "VAPOR", p) + _h(result.liquid.n, t, "LIQUID", p)) - _h(
        n, t, "VAPOR", p
    )
    assert answer.duty == expected


def test_the_flash_reads_f4_as_vapour_by_the_band() -> None:
    """F4, a vapour at its own dew point: VAPOR, the feed bitwise as vapour, the liquid `+0.0`."""
    answer, _ = _flash("F4")
    n = tuple(FLASH["F4"]["n_mol_s"])
    assert answer.status == "ok" and answer.phase_signature == "VAPOR"
    assert answer.outlets["vapor"].n == n
    assert answer.outlets["liquid"].n == (0.0,) * 5
    assert all(str(value) == "0.0" for value in answer.outlets["liquid"].n)
    assert answer.duty == _h(n, 268.15, "VAPOR") - _h(n, 268.15, "VAPOR")


def test_the_flash_reads_a_band_two_phase_answer_as_vapour() -> None:
    """F4's feed with NH3 × (1 + 8.1e-10): the provider answers TWO_PHASE with l/n ≈ 0.5 τ_dew,
    the evaluate reports the feed as vapour."""
    n = list(FLASH["F4"]["n_mol_s"])
    n[2] *= 1.0 + 8.1e-10
    unit = flash.TPFlash("U", PROVIDER, 268.15, P, CONTEXT)
    result = PROVIDER.flash(FlashRequest(state=_stream(n, 268.15)), CONTEXT)
    assert result.phase_signature == "TWO_PHASE"
    answer = unit.evaluate({"inlet": (_stream(n, 268.15),)}, CONTEXT)
    assert answer.phase_signature == "VAPOR"
    assert answer.outlets["vapor"].n == tuple(n) and answer.outlets["liquid"].n == (0.0,) * 5


def test_the_flash_refuses_a_feed_without_light_gas_and_a_pressure_mismatch() -> None:
    unit = flash.TPFlash("U", PROVIDER, 268.15, P, CONTEXT)
    pure = unit.evaluate({"inlet": (_stream((0.0, 0.0, 1.0, 0.0, 0.0), 268.15),)}, CONTEXT)
    assert pure.status == "unsupported"
    assert pure.message.startswith("pure_nh3_flash_unsupported")
    mismatch = unit.evaluate({"inlet": (_stream(Z, 268.15, 2.0e7),)}, CONTEXT)
    assert mismatch.status == "error"


def test_the_flash_of_a_dormant_feed_is_zero_flow() -> None:
    unit = flash.TPFlash("U", PROVIDER, 268.15, P, CONTEXT)
    answer = unit.evaluate({"inlet": (_stream((0.0,) * 5, 300.0),)}, CONTEXT)
    assert answer.status == "ok" and answer.phase_signature == "ZERO_FLOW" and answer.duty == 0.0
    assert answer.outlets["vapor"] == answer.outlets["liquid"] == _stream((0.0,) * 5, 268.15)
