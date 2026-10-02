"""T05 W9: the six T05 manifests, their accumulation table, their contributions, and the typed-
failure catalogue (spec §5–§10, §13.2, §13.3; A01, A02, A03, A16).

The per-model modules test each model's cases; this module holds what only makes sense across
the six. Every expectation here is the specification's own text — the port tables, the equation
tables, §13.2's accumulation table, the quoted balance statements and §13.3's code list — written
out as literals, so a manifest that drifts from the document fails here rather than agreeing with
itself. Where a per-model module already pins one model's piece of this (the reactor's statements,
the separator's and the exchanger's rows), this module does not repeat it per model; it states
the whole table once.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any

import numpy as np
import pytest
from conftest import REPO_ROOT, load_yaml
from t05_support import CONTEXT, PROVIDER, REF, first_line, stream
from t05_trial_states import TrialUnit, assemble_trial
from t05b_support import REF as T05B_REF
from t05b_support import Jump
from test_schemas_p01 import schema_errors
from test_t05_exchanger import exchanger
from test_t05_exchanger import inlets as exchanger_inlets
from test_t05_ph_flash import unit_for as ph_flash_for
from test_t05_ph_kernel import enthalpy
from test_t05_pump import unit_for as pump_for
from test_t05_reactor import unit_for as reactor_for
from test_t05_separator import separator
from test_t05_valve import unit_for as valve_for

from openflowsheet.compile.casadi_backend import CasadiCompiledProblem, compile_problem
from openflowsheet.compiled import CompiledProblemMetadata, EvaluationContext
from openflowsheet.models import SpecificationError, UnitModel, Wiring, origin
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.ph_flash import PHFlash
from openflowsheet.models.syn001.ph_kernel import closure_failure, ph_state
from openflowsheet.thermo import StreamState
from openflowsheet.units import DIMENSION_ORDER

TIME_INDEX = DIMENSION_ORDER.index("time")
MOLES = [0, 0, 0, 0, 1, 0, 0]
ENERGY = [2, 1, -2, 0, 0, 0, 0]

PhaseTuple = tuple[str, ...]
ALL_PHASES: PhaseTuple = ("liquid", "vapor", "vapor_liquid")
SINGLE: PhaseTuple = ("liquid", "vapor")


@dataclass(frozen=True)
class Model:
    """One T05 model as spec §5–§10 declare it, and how this module builds an instance of it."""

    model_id: str
    #: The registered case whose inputs build the nominal instance (as the per-model modules do).
    nominal: str
    build: Callable[[Mapping[str, Any]], UnitModel]
    inlets: Callable[[Mapping[str, Any]], Mapping[str, list[StreamState]]]
    wiring: Mapping[str, tuple[str, ...]]
    #: Streams the unit computes: `(n, T, P)` of each is an unknown of its contribution.
    outlet_streams: tuple[str, ...]
    #: The port table: (name, kind, direction, multiplicity, phase capabilities).
    ports: tuple[tuple[str, str, str, int, PhaseTuple], ...]
    #: The equation table at the nominal configuration: id -> (rows, row kind, conditional class).
    equations: Mapping[str, tuple[int, str, str]]
    #: Lifting rows (origin `<model>#lifting`), all `molar_flow` and `algebraic`.
    lifting: int
    #: Owned variables and their kinds.
    owned: Mapping[str, str]
    pinned: tuple[str, ...]
    #: The configuration axes the tables allow, each with its values (A01: every one validates).
    configurations: Mapping[str, tuple[Any, ...]]

    def unit(self, **changes: Any) -> UnitModel:
        return self.build({**REF["unit_cases"][self.nominal]["inputs"], **changes})


def _material_inlet(
    name: str, phases: PhaseTuple = ALL_PHASES
) -> tuple[str, str, str, int, PhaseTuple]:
    return (name, "material", "inlet", 1, phases)


def _material_outlet(name: str, phases: PhaseTuple) -> tuple[str, str, str, int, PhaseTuple]:
    return (name, "material", "outlet", 1, phases)


def _energy_inlet(name: str) -> tuple[str, str, str, int, PhaseTuple]:
    return (name, "energy", "inlet", 1, ())


def _split(stream_id: str) -> dict[str, str]:
    names = [f"{stream_id}.{part}.{c}" for part in ("vap", "liq") for c in COMPONENTS]
    return {name: "molar_flow" for name in (*names, f"{stream_id}.V", f"{stream_id}.L")}


def _single(inputs: Mapping[str, Any]) -> dict[str, list[StreamState]]:
    return {"inlet": [stream(inputs["inlet"])]}


LIFTABLE = ("LIQUID", "VAPOR", None)

MODELS: dict[str, Model] = {
    model.model_id: model
    for model in (
        Model(
            model_id="syn001.ph_flash",
            nominal="PHF-1",
            build=ph_flash_for,
            inlets=_single,
            wiring={"inlet": ("S1",), "vapor": ("S2",), "liquid": ("S3",)},
            outlet_streams=("S2", "S3"),
            ports=(
                _material_inlet("inlet"),
                _material_outlet("vapor", ("vapor",)),
                _material_outlet("liquid", ("liquid",)),
                _energy_inlet("duty"),
            ),
            equations={
                "PHF-mole": (3, "molar_flow", "unconditional"),
                "PHF-equilibrium": (3, "molar_flow_squared", "phase_conditional"),
                "PHF-T": (1, "temperature", "unconditional"),
                "PHF-pressure": (2, "pressure", "unconditional"),
                "PHF-duty": (1, "heat_rate", "unconditional"),
                "PHF-Q": (1, "heat_rate", "unconditional"),
            },
            lifting=2,
            owned={"U-PHF.Q": "heat_rate", "S2.N": "molar_flow", "S3.N": "molar_flow"},
            pinned=("U-PHF.Q_spec", "U-PHF.pressure_drop"),
            configurations={"inlet_phase": LIFTABLE},
        ),
        Model(
            model_id="syn001.conversion_reactor",
            nominal="RX-1",
            build=reactor_for,
            inlets=_single,
            wiring={"inlet": ("S1",), "outlet": ("S2",)},
            outlet_streams=("S2",),
            ports=(
                _material_inlet("inlet"),
                _material_outlet("outlet", ALL_PHASES),
                _energy_inlet("duty"),
            ),
            equations={
                "RX-mole": (3, "molar_flow", "unconditional"),
                "RX-conversion": (1, "molar_flow", "unconditional"),
                "RX-pressure": (1, "pressure", "unconditional"),
                "RX-equilibrium": (3, "molar_flow_squared", "phase_conditional"),
                "RX-duty": (1, "heat_rate", "unconditional"),
                "RX-spec": (1, "temperature", "unconditional"),
            },
            lifting=5,
            owned={"U-RX.Q": "heat_rate", "U-RX.xi": "molar_flow", **_split("S2")},
            pinned=(
                "U-RX.nu.A",
                "U-RX.nu.B",
                "U-RX.nu.C",
                "U-RX.conversion",
                "U-RX.pressure_drop",
                "U-RX.T_spec",
            ),
            configurations={
                # Spec §6.2: the key must be a reactant; for nu = (-2, -1, 3) that is A or B.
                "key": ("A", "B"),
                "energy_specification": ("outlet_temperature", "duty"),
                "inlet_phase": LIFTABLE,
            },
        ),
        Model(
            model_id="syn001.component_separator",
            nominal="SEP-1",
            build=separator,
            inlets=_single,
            wiring={"inlet": ("S1",), "top": ("S2",), "bottom": ("S3",)},
            outlet_streams=("S2", "S3"),
            ports=(
                _material_inlet("inlet"),
                _material_outlet("top", SINGLE),
                _material_outlet("bottom", SINGLE),
                _energy_inlet("duty"),
            ),
            equations={
                "SEP-mole": (3, "molar_flow", "unconditional"),
                "SEP-split": (3, "molar_flow", "unconditional"),
                "SEP-T": (2, "temperature", "unconditional"),
                "SEP-P": (2, "pressure", "unconditional"),
                "SEP-duty": (1, "heat_rate", "unconditional"),
            },
            lifting=0,
            owned={"U-SEP.Q": "heat_rate"},
            pinned=("U-SEP.split.A", "U-SEP.split.B", "U-SEP.split.C"),
            configurations={
                "top_phase": ("LIQUID", "VAPOR"),
                "bottom_phase": ("LIQUID", "VAPOR"),
                "inlet_phase": LIFTABLE,
            },
        ),
        Model(
            model_id="syn001.valve",
            nominal="VLV-1",
            build=valve_for,
            inlets=_single,
            wiring={"inlet": ("S1",), "outlet": ("S2",)},
            outlet_streams=("S2",),
            ports=(_material_inlet("inlet"), _material_outlet("outlet", ALL_PHASES)),
            equations={
                "VLV-mole": (3, "molar_flow", "unconditional"),
                "VLV-P": (1, "pressure", "unconditional"),
                "VLV-energy": (1, "heat_rate", "unconditional"),
                "VLV-equilibrium": (3, "molar_flow_squared", "phase_conditional"),
            },
            lifting=5,
            owned=_split("S2"),
            pinned=("U-VLV.P_spec",),
            configurations={"inlet_phase": LIFTABLE},
        ),
        Model(
            model_id="syn001.liquid_pump",
            nominal="PUMP-1",
            build=pump_for,
            inlets=_single,
            wiring={"inlet": ("S1",), "outlet": ("S2",)},
            outlet_streams=("S2",),
            ports=(
                _material_inlet("inlet", ("liquid",)),
                _material_outlet("outlet", ("liquid",)),
                _energy_inlet("work"),
            ),
            equations={
                "PUMP-mole": (3, "molar_flow", "unconditional"),
                "PUMP-P": (1, "pressure", "unconditional"),
                "PUMP-work": (1, "heat_rate", "unconditional"),
                "PUMP-energy": (1, "heat_rate", "unconditional"),
            },
            lifting=0,
            # R-043: the shaft work's scaling kind is `heat_rate` (its manifest Quantity `power`).
            owned={"U-PUMP.W": "heat_rate"},
            pinned=("U-PUMP.P_spec", "U-PUMP.efficiency"),
            configurations={},
        ),
        Model(
            model_id="syn001.heat_exchanger",
            nominal="HX-1",
            build=exchanger,
            inlets=exchanger_inlets,
            wiring={
                "hot_inlet": ("S1",),
                "hot_outlet": ("S2",),
                "cold_inlet": ("S3",),
                "cold_outlet": ("S4",),
            },
            outlet_streams=("S2", "S4"),
            ports=(
                _material_inlet("hot_inlet", SINGLE),
                _material_outlet("hot_outlet", SINGLE),
                _material_inlet("cold_inlet", SINGLE),
                _material_outlet("cold_outlet", SINGLE),
            ),
            equations={
                "HX-mole-hot": (3, "molar_flow", "unconditional"),
                "HX-mole-cold": (3, "molar_flow", "unconditional"),
                "HX-pressure": (2, "pressure", "unconditional"),
                "HX-energy-hot": (1, "heat_rate", "unconditional"),
                "HX-energy-cold": (1, "heat_rate", "unconditional"),
                "HX-spec": (1, "temperature", "unconditional"),
            },
            lifting=0,
            owned={"U-HX.Q": "heat_rate"},
            pinned=("U-HX.T_spec",),
            configurations={
                "specification": ("cold_outlet_temperature", "hot_outlet_temperature", "duty"),
                "hot_phase": ("LIQUID", "VAPOR"),
                "cold_phase": ("LIQUID", "VAPOR"),
            },
        ),
    )
}
MODEL_IDS = sorted(MODELS)

#: The specification row and its pinned input by energy mode or specification (spec §6.2, §10.1).
SPECIFICATION_ROWS: dict[tuple[str, str, str], tuple[str, str, str]] = {
    ("syn001.conversion_reactor", "energy_specification", "outlet_temperature"): (
        "RX-spec",
        "temperature",
        "U-RX.T_spec",
    ),
    ("syn001.conversion_reactor", "energy_specification", "duty"): (
        "RX-spec",
        "heat_rate",
        "U-RX.Q_spec",
    ),
    ("syn001.heat_exchanger", "specification", "cold_outlet_temperature"): (
        "HX-spec",
        "temperature",
        "U-HX.T_spec",
    ),
    ("syn001.heat_exchanger", "specification", "hot_outlet_temperature"): (
        "HX-spec",
        "temperature",
        "U-HX.T_spec",
    ),
    ("syn001.heat_exchanger", "specification", "duty"): ("HX-spec", "heat_rate", "U-HX.Q_spec"),
}


def configurations(model: Model) -> list[dict[str, Any]]:
    """Every combination of the model's configuration axes (the nominal alone for the pump)."""
    combinations: list[dict[str, Any]] = [{}]
    for axis, values in model.configurations.items():
        combinations = [{**done, axis: value} for done in combinations for value in values]
    return combinations


CONFIGURED = [
    pytest.param(model_id, changes, id=f"{model_id}-{'-'.join(map(str, changes.values()))}")
    for model_id in MODEL_IDS
    for changes in configurations(MODELS[model_id])
]


def expected_specification(model: Model, changes: Mapping[str, Any]) -> tuple[str, str, str]:
    """`(equation, row kind, pinned id)` of the configured specification row, if the model has
    one that the configuration selects; `("", "", "")` otherwise."""
    for (model_id, axis, value), selected in SPECIFICATION_ROWS.items():
        nominal = REF["unit_cases"][model.nominal]["inputs"].get(axis)
        if model_id == model.model_id and changes.get(axis, nominal) == value:
            return selected
    return ("", "", "")


# ----------------------------------------------------------------------------------- A01


@pytest.mark.parametrize(("model_id", "changes"), CONFIGURED)
def test_a01_every_configuration_has_a_valid_manifest_with_the_declared_contract(
    model_id: str, changes: Mapping[str, Any]
) -> None:
    """A01: schema, identity, the port table, the equation set, derivatives, provider, status."""
    model = MODELS[model_id]
    document = dict(model.unit(**changes).manifest())

    assert schema_errors("model_manifest", document) == []
    assert document["id"] == model_id
    assert document["introduced_by_package"] == "T05"
    assert document["implementation_artifact"]["planned_package"] == "T05"
    assert document["status"] not in {"reviewed", "released"}
    requirements = document["execution_requirements"]
    assert requirements["property_provider"] == "syn001"
    assert requirements["reference_convention"] == "SYN-001-ref-v1"

    ports = tuple(
        (
            port["name"],
            port["kind"],
            port["direction"],
            port["multiplicity"],
            tuple(port["phase_capabilities"]),
        )
        for port in document["ports"]
    )
    assert ports == model.ports

    equations = {entry["id"]: entry for entry in document["mathematics"]["equations"]}
    assert list(equations) == list(model.equations)
    for equation_id, (_, _, conditional_class) in model.equations.items():
        assert equations[equation_id]["conditional_class"] == conditional_class, equation_id

    derivatives = {entry["output"]: entry for entry in document["derivatives"]}
    residuals = derivatives.pop("residuals")
    assert (residuals["method"], residuals["regime"]) == ("ad", "all")
    outlets = {port[0] for port in model.ports if port[2] == "outlet"}
    assert {f"{port}.state" for port in outlets} <= set(derivatives)
    # Every sensitivity of a result to the inlets or the specifications is `unavailable` (§4.5):
    # declared absent, never reported as zeros.
    assert {output: entry["method"] for output, entry in derivatives.items()} == dict.fromkeys(
        derivatives, "unavailable"
    )


# ----------------------------------------------------------------------------------- A02

#: Spec §13.2, the accumulation table (normative; extends ADR 0008 D3.5 to T05's manifests).
REGISTERED_KINDS: dict[tuple[str, str], str] = {
    ("syn001.ph_flash", "PHF-mole"): "holdup_balance",
    ("syn001.ph_flash", "PHF-duty"): "holdup_balance",
    ("syn001.ph_flash", "PHF-equilibrium"): "algebraic",
    ("syn001.ph_flash", "PHF-T"): "algebraic",
    ("syn001.ph_flash", "PHF-pressure"): "algebraic",
    ("syn001.ph_flash", "PHF-Q"): "algebraic",
    ("syn001.conversion_reactor", "RX-mole"): "holdup_balance",
    ("syn001.conversion_reactor", "RX-duty"): "holdup_balance",
    ("syn001.conversion_reactor", "RX-conversion"): "algebraic",
    ("syn001.conversion_reactor", "RX-pressure"): "algebraic",
    ("syn001.conversion_reactor", "RX-equilibrium"): "algebraic",
    ("syn001.conversion_reactor", "RX-spec"): "algebraic",
    ("syn001.component_separator", "SEP-mole"): "zero_holdup_balance",
    ("syn001.component_separator", "SEP-duty"): "zero_holdup_balance",
    ("syn001.component_separator", "SEP-split"): "algebraic",
    ("syn001.component_separator", "SEP-T"): "algebraic",
    ("syn001.component_separator", "SEP-P"): "algebraic",
    ("syn001.valve", "VLV-mole"): "zero_holdup_balance",
    ("syn001.valve", "VLV-energy"): "zero_holdup_balance",
    ("syn001.valve", "VLV-P"): "algebraic",
    ("syn001.valve", "VLV-equilibrium"): "algebraic",
    ("syn001.liquid_pump", "PUMP-mole"): "zero_holdup_balance",
    ("syn001.liquid_pump", "PUMP-energy"): "zero_holdup_balance",
    ("syn001.liquid_pump", "PUMP-P"): "algebraic",
    ("syn001.liquid_pump", "PUMP-work"): "algebraic",
    ("syn001.heat_exchanger", "HX-mole-hot"): "holdup_balance",
    ("syn001.heat_exchanger", "HX-mole-cold"): "holdup_balance",
    ("syn001.heat_exchanger", "HX-energy-hot"): "holdup_balance",
    ("syn001.heat_exchanger", "HX-energy-cold"): "holdup_balance",
    ("syn001.heat_exchanger", "HX-pressure"): "algebraic",
    ("syn001.heat_exchanger", "HX-spec"): "algebraic",
}

#: Spec §13.2's holdups, with ADR 0008 D3.2's dimensions (ADR 0001 D1.2 order).
REGISTERED_HOLDUPS: dict[str, tuple[str, list[int]]] = {
    "PHF-mole": ("N_i", MOLES),
    "PHF-duty": ("U", ENERGY),
    "RX-mole": ("N_i", MOLES),
    "RX-duty": ("U", ENERGY),
    "HX-mole-hot": ("N_hot_i", MOLES),
    "HX-mole-cold": ("N_cold_i", MOLES),
    "HX-energy-hot": ("U_hot", ENERGY),
    "HX-energy-cold": ("U_cold", ENERGY),
}

#: Spec §5–§10's balance statements, quoted exactly (ADR 0008 D3.3: inflow − outflow + sources).
#: §10.1 quotes the hot side's mole statement and says "(and cold)": the cold one is that text
#: with `hot` read as `cold`.
REGISTERED_STATEMENTS: dict[str, str] = {
    "PHF-mole": "n_in,i - n_vap,i - n_liq,i = 0 for every component i",
    "PHF-duty": "Q + Hdot_in - Hdot_vap - Hdot_liq = 0, Q positive into the unit",
    "RX-mole": "n_in,i - n_out,i + nu_i xi = 0 for every component i",
    "RX-duty": (
        "Q + Hdot_in - Hdot_out = 0, Q positive into the unit; enthalpies on the provider's "
        "formation datum (ADR 0011 D2), so the heat of reaction is carried by Hdot and never "
        "added separately"
    ),
    "SEP-mole": "n_in,i - n_top,i - n_bot,i = 0 for every component i",
    "SEP-duty": "Q + Hdot_in - Hdot_top - Hdot_bot = 0, Q positive into the unit",
    "VLV-mole": "n_in,i - n_out,i = 0 for every component i",
    "VLV-energy": "Hdot_in - Hdot_out = 0 (adiabatic, no work: isenthalpic)",
    "PUMP-mole": "n_in,i - n_out,i = 0 for every component i",
    "PUMP-energy": "W + Hdot_in - Hdot_out = 0, W positive into the unit (adiabatic)",
    "HX-mole-hot": "n_hot_in,i - n_hot_out,i = 0 for every component i",
    "HX-mole-cold": "n_cold_in,i - n_cold_out,i = 0 for every component i",
    "HX-energy-hot": (
        "Hdot_hot_in - Hdot_hot_out - Q = 0, Q the heat transferred from the hot to the cold side"
    ),
    "HX-energy-cold": "Hdot_cold_in - Hdot_cold_out + Q = 0",
}

#: Spec §7–§9's reasons for `zero_holdup_balance` (ADR 0008 D3.1), quoted exactly.
REGISTERED_REASONS: dict[str, str] = {
    "syn001.component_separator": (
        "an ideal component divider: its outlets are instantaneous fractions of its inlet at the "
        "inlet's state, so its inventory is identically zero by the model's definition; a "
        "separation vessel with holdup is a different model"
    ),
    "syn001.valve": "a throttling point with no volume by the model's definition",
    "syn001.liquid_pump": "an ideal machine with no inventory by the model's definition",
}


@cache
def declared_equations() -> dict[tuple[str, str], dict[str, Any]]:
    """Every equation of the six T05 manifests, at every configuration, keyed by (model, id).

    A configuration may change an equation's content (RX-spec, HX-spec) but never its
    classification: the same key must carry the same accumulation block in every configuration.
    """
    equations: dict[tuple[str, str], dict[str, Any]] = {}
    for model_id in MODEL_IDS:
        model = MODELS[model_id]
        for changes in configurations(model):
            for equation in dict(model.unit(**changes).manifest())["mathematics"]["equations"]:
                key = (model_id, equation["id"])
                if key in equations:
                    assert equations[key]["accumulation"] == equation["accumulation"], key
                else:
                    equations[key] = equation
    return equations


def test_a02_the_accumulation_classification_is_exactly_the_spec_table() -> None:
    kinds = {
        key: equation["accumulation"]["kind"] for key, equation in declared_equations().items()
    }
    assert kinds == REGISTERED_KINDS
    counts = Counter(kinds.values())
    assert counts == Counter({"holdup_balance": 8, "zero_holdup_balance": 6, "algebraic": 17})


@pytest.mark.parametrize("equation_id", sorted(REGISTERED_HOLDUPS))
def test_a02_holdup_symbol_and_dimension_and_the_row_dimension_they_imply(
    equation_id: str,
) -> None:
    """ADR 0008 D3.2: a holdup_balance row's dimension is its holdup's, per second."""
    (equation,) = [eq for (_, eq_id), eq in declared_equations().items() if eq_id == equation_id]
    holdup = equation["accumulation"]["holdup"]
    symbol, dimension = REGISTERED_HOLDUPS[equation_id]
    assert (holdup["symbol"], holdup["dimension"]) == (symbol, dimension)
    row = list(dimension)
    row[TIME_INDEX] -= 1
    assert equation["dimension"] == row


def test_a02_every_balance_row_states_the_quoted_text() -> None:
    """ADR 0008 D3.3: the fourteen balance statements, exactly the spec's."""
    balances = {
        eq_id: equation["statement"]
        for (_, eq_id), equation in declared_equations().items()
        if equation["accumulation"]["kind"] != "algebraic"
    }
    assert balances == REGISTERED_STATEMENTS


def test_a02_every_zero_holdup_balance_states_the_quoted_reason() -> None:
    """ADR 0008 D3.1: a zero row by physics, with the spec's reason, never by omission."""
    for (model_id, equation_id), equation in declared_equations().items():
        accumulation = equation["accumulation"]
        if accumulation["kind"] == "zero_holdup_balance":
            assert accumulation["reason"] == REGISTERED_REASONS[model_id], equation_id


#: T05b spec §16 (T05 spec §5.1 as amended by T05b): the near-pure limitation (T05 §4.4) and both
#: EO limitations of §4.7 are retired from every manifest that stated them — the PH-type three,
#: and the pump's dormant-inlet statement (T05 §4.7) — so no text cites them any more.
RETIRED_LIMITATION_CITATIONS = (
    "(T05 spec §4.4, 'What ok guarantees')",
    "(T05 spec §4.7 (a))",
    "(T05 spec §4.7 (b))",
    "(T05 spec §4.7)",
)
#: What the PH-type manifests state instead, each once: the kernel's acceptance and band route
#: (T05b §5.1–§5.3), and the EO outcome under each phase-contract literal (T05b §6.6, §11).
REGISTERED_LIMITATION_CITATIONS = (
    "(T05b spec §5.1-§5.3)",
    "(T05b spec §6.6, B08-B10, B16)",
)
#: T05b §7.8 (iv) 2 and §17: the dormant-duty conflict is typed on both faces and not searched
#: past, stated by the two PH-type models with a duty.
CONFLICT_CITATION = "(T05b spec §7.8 (iv), §17)"
LITERALS = ("T05b-phase-contract-v2", "T03-phase-contract-v1")


def _limitations(model_id: str) -> list[str]:
    return list(MODELS[model_id].unit().manifest()["validity"]["limitations"])


def _stating(limitations: list[str], citation: str) -> str:
    stating = [text for text in limitations if citation in text]
    assert len(stating) == 1, citation
    return stating[0]


@pytest.mark.parametrize(
    "model_id",
    [
        "syn001.ph_flash",
        "syn001.valve",
        "syn001.conversion_reactor",
        "syn001.liquid_pump",
        "syn001.heat_exchanger",
    ],
)
def test_a01_the_retired_limitations_are_gone(model_id: str) -> None:
    for text in _limitations(model_id):
        assert not any(citation in text for citation in RETIRED_LIMITATION_CITATIONS), text
        assert "v0.1 does not" not in text, text


@pytest.mark.parametrize(
    "model_id", ["syn001.ph_flash", "syn001.valve", "syn001.conversion_reactor"]
)
def test_a01_the_ph_type_manifests_state_the_registered_limitations(model_id: str) -> None:
    limitations = _limitations(model_id)
    kernel = _stating(limitations, REGISTERED_LIMITATION_CITATIONS[0])
    assert "ph_ill_conditioned" in kernel and "tau_E" in kernel
    assert "saturation-band route" in kernel
    eo = _stating(limitations, REGISTERED_LIMITATION_CITATIONS[1])
    assert all(literal in eo for literal in LITERALS), eo
    assert "never VERIFIED" in eo and "not CONVERGED" in eo
    conflicts = [text for text in limitations if CONFLICT_CITATION in text]
    if model_id == "syn001.valve":
        assert conflicts == []
    else:
        (conflict,) = conflicts
        assert "duty_into_dormant_stream" in conflict and "SPECIFICATION_CONFLICT" in conflict


def test_a01_the_non_lifted_dormancy_statements() -> None:
    """T05b §16 (second pass): the pump's statement names the zero-flow form and both literals;
    the exchanger keeps its causal refusal and adds its EO conflict and its unjudged terminal
    differences at a dormant side (T05b §9.3, §17)."""
    (pump,) = [text for text in _limitations("syn001.liquid_pump") if "dormant inlet" in text]
    assert all(literal in pump for literal in LITERALS)
    assert "zero-flow form" in pump and "W = 0" in pump and "not CONVERGED" in pump
    exchanger = _limitations("syn001.heat_exchanger")
    conflict = _stating(exchanger, CONFLICT_CITATION)
    assert "specification_unsatisfiable_with_dormant_side" in conflict
    assert "SPECIFICATION_CONFLICT" in conflict
    terminal = _stating(exchanger, "(T05b spec §9.3, §17)")
    assert "not_applicable" in terminal


#: T05b spec §16 (Q-S9 addendum, 2026-09-25; replaced by Q-S15 (1), 2026-09-25), verbatim: the
#: one exception to "solved and certified" on the EO path, stated by `syn001.ph_flash` alone.
DEW_POINT_LIMITATION = (
    "On the EO path a flash whose solution lies exactly on its dew or bubble point with one "
    "product zero — for example a zero-duty, zero-pressure-drop flash fed a saturated vapour or "
    "liquid — is not certified. The lifted equilibrium rows are singular there. A solve that ends "
    "at that point is certified UNVERIFIED with regularity RANK_DEFICIENT. A solve that "
    "approaches it in the two-phase form can stop at a nearby state, which the verifier fails as "
    "a detected false success (T05b spec B31 (b), §17)."
)


@pytest.mark.parametrize(
    ("model_id", "stated"),
    [("syn001.ph_flash", True), ("syn001.valve", False), ("syn001.conversion_reactor", False)],
)
def test_a01_the_ph_flash_states_the_dew_point_limitation(model_id: str, stated: bool) -> None:
    limitations = _limitations(model_id)
    assert (limitations.count(DEW_POINT_LIMITATION) == 1) is stated
    assert sum("(T05b spec B31 (b), §17)" in text for text in limitations) == int(stated)


def test_a02_no_t05_manifest_joins_the_p01_fixture_directory() -> None:
    """F4: ADR 0008's M1 and M3 count every manifest under `valid/`; T05's stay out of it."""
    directory = REPO_ROOT / "tests" / "fixtures" / "schemas" / "model_manifest" / "valid"
    fixtures = {load_yaml(path)["id"] for path in sorted(directory.glob("*.yaml"))}
    assert fixtures, "the P01 fixtures M1–M5 pin are missing"
    assert fixtures.isdisjoint(MODELS)


# ----------------------------------------------------------------------------------- A03


@pytest.mark.parametrize(("model_id", "changes"), CONFIGURED)
def test_a03_the_contribution_is_the_declared_table_and_square(
    model_id: str, changes: Mapping[str, Any]
) -> None:
    """A03: rows per declared equation, their kinds and accumulation, lifting rows, owned
    variables, pinned inputs, and rows = unknowns given the inlets (the DOF tables)."""
    model = MODELS[model_id]
    unit = model.unit(**changes)
    contribution = unit.contribute(Wiring(dict(model.wiring)), COMPONENTS)

    equations = {eq_id: (count, kind) for eq_id, (count, kind, _) in model.equations.items()}
    pinned = list(model.pinned)
    selected, selected_kind, selected_pin = expected_specification(model, changes)
    if selected:
        equations[selected] = (1, selected_kind)
        pinned[-1] = selected_pin

    declared = {
        origin(model_id, equation.equation_id): equation.accumulation.kind
        for equation in unit.declared_equations()
    }
    assert set(declared) == {origin(model_id, eq_id) for eq_id in model.equations}
    lifting = origin(model_id, "lifting")

    rows = Counter(equation.origin for equation in contribution.equations)
    expected_rows = Counter({origin(model_id, eq_id): n for eq_id, (n, _) in equations.items()})
    if model.lifting:
        expected_rows[lifting] = model.lifting
    assert rows == expected_rows

    for equation in contribution.equations:
        kind = contribution.row_kinds[equation.equation_id]
        if equation.origin == lifting:
            assert (equation.accumulation, kind) == ("algebraic", "molar_flow")
        else:
            eq_id = equation.origin.split("#", 1)[1]
            assert equation.accumulation == declared[equation.origin], equation.equation_id
            assert kind == equations[eq_id][1], equation.equation_id
            assert equation.equation_id.startswith(f"{unit.unit_id}:{eq_id}")
    assert len({equation.equation_id for equation in contribution.equations}) == len(
        contribution.equations
    )

    assert dict(contribution.variable_kinds) == dict(model.owned)
    assert list(contribution.variable_ids) == list(model.owned)
    assert list(contribution.parameter_ids) == pinned

    unknowns = len(model.outlet_streams) * (len(COMPONENTS) + 2) + len(contribution.variable_ids)
    assert len(contribution.equations) == unknowns


def unit_trial(model: Model, unit: UnitModel, inlet_phase: Any = "LIQUID") -> TrialUnit:
    """The unit alone, every stream a column; a lifted inlet's split added as free columns."""
    streams = tuple(dict.fromkeys(s for wired in model.wiring.values() for s in wired))
    return TrialUnit(
        unit=unit,
        wiring=Wiring(dict(model.wiring)),
        streams=streams,
        lifted_inlets=("S1",) if inlet_phase is None else (),
    )


def _compiled(model: Model, changes: Mapping[str, Any]) -> tuple[CasadiCompiledProblem, list[str]]:
    unit = model.unit(**changes)
    inputs = {**REF["unit_cases"][model.nominal]["inputs"], **changes}
    spec = assemble_trial(
        unit_trial(model, unit, inputs.get("inlet_phase", "LIQUID")), label="T05-A03"
    )
    return compile_problem(spec), list(spec.variable_ids)


def _metadata(model: Model, changes: Mapping[str, Any]) -> CompiledProblemMetadata:
    return _compiled(model, changes)[0].metadata


#: A pinned-input value change per model: every pinned input of the nominal instance moved.
PINNED_CHANGES: dict[str, dict[str, Any]] = {
    "syn001.ph_flash": {"duty": "40000.0", "pressure_drop": "1000.0"},
    "syn001.conversion_reactor": {
        "nu": ["-1.0", "-1.0", "2.0"],
        "conversion": "0.25",
        "pressure_drop": "500.0",
        "value": "310.0",
    },
    "syn001.component_separator": {"split": ["0.2", "0.3", "0.4"]},
    "syn001.valve": {"outlet_pressure": "90000.0"},
    "syn001.liquid_pump": {"outlet_pressure": "150000.0", "efficiency": "0.5"},
    "syn001.heat_exchanger": {"value": "315.0"},
}


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_a03_a_pinned_input_change_keeps_model_version(model_id: str) -> None:
    """ADR 0008 D4.1: same structure, other specification values -> same `model_version`,
    different `constants_sha256`."""
    model = MODELS[model_id]
    nominal = _metadata(model, {})
    moved = _metadata(model, PINNED_CHANGES[model_id])
    assert moved.model_version == nominal.model_version
    assert moved.constants_sha256 != nominal.constants_sha256


#: Configuration changes that change the structure document itself: a pinned input's id (the
#: energy mode, the exchanger's duty versus temperature specification), or the columns a lifted
#: inlet brings (declared versus lifted inlet).
STRUCTURAL_CONFIGURATIONS: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
    ("syn001.conversion_reactor", {}, {"energy_specification": "duty"}),
    ("syn001.heat_exchanger", {}, {"specification": "duty"}),
    (
        "syn001.heat_exchanger",
        {"specification": "hot_outlet_temperature"},
        {"specification": "duty"},
    ),
    ("syn001.ph_flash", {}, {"inlet_phase": None}),
    ("syn001.valve", {}, {"inlet_phase": None}),
    ("syn001.conversion_reactor", {}, {"inlet_phase": None}),
    ("syn001.component_separator", {}, {"inlet_phase": None}),
]


@pytest.mark.parametrize(("model_id", "before", "after"), STRUCTURAL_CONFIGURATIONS)
def test_a03_a_configuration_that_moves_an_id_changes_model_version(
    model_id: str, before: dict[str, Any], after: dict[str, Any]
) -> None:
    model = MODELS[model_id]
    assert _metadata(model, before).model_version != _metadata(model, after).model_version


#: Configuration changes that select a different function without changing a single id: the key
#: component, a declared phase, which outlet temperature is specified.
LABEL_CONFIGURATIONS: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
    ("syn001.conversion_reactor", {}, {"key": "B"}),
    ("syn001.conversion_reactor", {}, {"inlet_phase": "VAPOR"}),
    ("syn001.ph_flash", {}, {"inlet_phase": "VAPOR"}),
    ("syn001.valve", {}, {"inlet_phase": "VAPOR"}),
    ("syn001.component_separator", {}, {"inlet_phase": "VAPOR"}),
    ("syn001.component_separator", {}, {"top_phase": "VAPOR"}),
    ("syn001.component_separator", {}, {"bottom_phase": "VAPOR"}),
    ("syn001.heat_exchanger", {}, {"specification": "hot_outlet_temperature"}),
    ("syn001.heat_exchanger", {}, {"hot_phase": "VAPOR"}),
    ("syn001.heat_exchanger", {}, {"cold_phase": "VAPOR"}),
]


def _generic_state(names: list[str]) -> np.ndarray[Any, np.dtype[np.float64]]:
    """One state inside the domain with every coordinate distinct, the same for both problems."""
    values = []
    for index, name in enumerate(names):
        if name.endswith(".T"):
            values.append(310.0 + 2.5 * index)
        elif name.endswith(".P"):
            values.append(1.0e5 + 500.0 * index)
        elif name.endswith((".Q", ".W")):
            values.append(1234.5 + index)
        else:
            values.append(0.3 + 0.07 * index)
    return np.array(values)


@pytest.mark.parametrize(("model_id", "before", "after"), LABEL_CONFIGURATIONS)
def test_a03_a_configuration_that_moves_no_id_is_a_different_function_under_one_digest(
    model_id: str, before: dict[str, Any], after: dict[str, Any]
) -> None:
    """The structure digest of ADR 0002 D2 cannot see these configurations: the rows differ at
    one state while every id — hence the digest after `@` — is equal. This equality is kept
    visible on purpose (ADR 0002 D2.6's pattern): it is why a revision-built flowsheet's label
    carries the instances' configuration (R-047), which is where A03's "a configuration change
    changes `model_version`" is discharged for these axes, not in the unit's contribution.
    """
    model = MODELS[model_id]
    first, names = _compiled(model, before)
    second, other_names = _compiled(model, after)
    assert other_names == names
    assert first.metadata.equation_ids == second.metadata.equation_ids
    assert first.metadata.model_version.split("@")[1] == second.metadata.model_version.split("@")[1]

    x = _generic_state(names)
    values = []
    for problem in (first, second):
        context = EvaluationContext(
            model_version=problem.metadata.model_version,
            constants_sha256=problem.metadata.constants_sha256,
        )
        residual = problem.residual(x, context)
        assert residual.status == "ok", residual.message
        assert residual.values is not None
        values.append(np.asarray(residual.values))
    assert not np.array_equal(values[0], values[1])


# ----------------------------------------------------------------------------------- A16

#: Spec §13.3, the complete typed-failure catalogue, as patterns over a message's first line.
CATALOGUE: dict[str, str] = {
    "pressure_outside_domain(outlet)": r"pressure_outside_domain\(outlet\)",
    "ph_outside_domain(below)": r"ph_outside_domain\(below\)",
    "ph_outside_domain(above)": r"ph_outside_domain\(above\)",
    "ph_not_converged": r"ph_not_converged",
    "ph_ill_conditioned": r"ph_ill_conditioned",
    "inadmissible_phase(<port>, LIQUID|VAPOR)": r"inadmissible_phase\([a-z_]+, (LIQUID|VAPOR)\)",
    "state_outside_domain(<port>)": r"state_outside_domain\([a-z_]+\)",
    "duty_into_dormant_stream": r"duty_into_dormant_stream",
    "reactant_exhausted(<c>)": r"reactant_exhausted\([A-C]\)",
    "pressure_rise(valve)": r"pressure_rise\(valve\)",
    "pressure_fall(pump)": r"pressure_fall\(pump\)",
    "outlet_outside_domain": r"outlet_outside_domain",
    "heat_flow_reversed": r"heat_flow_reversed",
    "temperature_cross(hot_end)": r"temperature_cross\(hot_end\)",
    "temperature_cross(cold_end)": r"temperature_cross\(cold_end\)",
    "specification_unsatisfiable_with_dormant_side": (
        r"specification_unsatisfiable_with_dormant_side"
    ),
    "negative_pressure_drop": r"negative_pressure_drop",
    "pressure_outside_domain(outlet_pressure)": r"pressure_outside_domain\(outlet_pressure\)",
    "efficiency_outside_interval": r"efficiency_outside_interval",
    "conversion_outside_unit_interval": r"conversion_outside_unit_interval",
    "key_not_reactant": r"key_not_reactant",
    "stoichiometry_not_mass_conserving": r"stoichiometry_not_mass_conserving",
    "reference_convention_not_reaction_consistent(<convention>)": (
        r"reference_convention_not_reaction_consistent\([A-Za-z0-9._-]+\)"
    ),
    "outlet_temperature_outside_domain": r"outlet_temperature_outside_domain",
    "split_fraction_outside_unit_interval(<c>)": r"split_fraction_outside_unit_interval\([A-C]\)",
    "unknown_specification(<name>)": r"unknown_specification\([a-z_]+\)",
}


def catalogued(line: str) -> list[str]:
    return [code for code, pattern in CATALOGUE.items() if re.fullmatch(pattern, line)]


@cache
def registered_first_lines() -> dict[str, str]:
    """The first message line of every registered failure and construction case, by case id."""
    lines: dict[str, str] = {}
    for case_id, case in REF["unit_cases"].items():
        if case["expected"]["status"] == "ok":
            continue
        model = MODELS[case["model"]]
        inputs = case["inputs"]
        result = model.build(inputs).evaluate(model.inlets(inputs), CONTEXT)
        assert result.status == case["expected"]["status"], case_id
        lines[case_id] = first_line(result.message)
    for case_id, case in REF["specification_errors"].items():
        model = MODELS[case["model"]]
        with pytest.raises(SpecificationError) as refused:
            model.unit(**case["change_from_nominal"])
        lines[case_id] = first_line(str(refused.value))
    return lines


def constructed_first_lines() -> dict[str, str]:
    """The four §13.3 codes no registered case reaches, each from one change to a registered
    case (not registered values; they close the catalogue, they do not validate a number)."""
    lines: dict[str, str] = {}
    phf = MODELS["syn001.ph_flash"]

    # A port state the provider refuses: PHF-1's inlet at 450 K, above the domain.
    inputs = REF["unit_cases"]["PHF-1"]["inputs"]
    hot = {**inputs["inlet"], "T_K": "450.0"}
    result = phf.build(inputs).evaluate({"inlet": [stream(hot)]}, CONTEXT)
    lines["PHF-1 at 450 K"] = first_line(result.message)

    # HX-3's duty raised to 1 MW: neither outlet temperature stays in the domain (§10.2 (4)).
    exchanged = {**REF["unit_cases"]["HX-3"]["inputs"], "value": "1000000.0"}
    result = exchanger(exchanged).evaluate(exchanger_inlets(exchanged), CONTEXT)
    lines["HX-3 at 1 MW"] = first_line(result.message)

    # `ph_ill_conditioned`, the refusal at the end of the kernel's fallback chain. Until T05b it
    # was constructed from PHF-6's feed with 1e-12 of an absent component (T05 A29's near-pure
    # class); T05b's band route answers that feed (ADR 0012 D2, spec §16), and the chain's
    # refusal is reached only when the provider breaks the class's continuity. So PHF-1's unit on
    # the JUMP double of T05b §12.2 (every vapour enthalpy +1 000 J/mol above 360 K), with the
    # duty that puts the target in the middle of the resulting jump: both routes close on the
    # jump, |f| ≈ 680 W (B03).
    registered = REF["unit_cases"]["PHF-1"]["inputs"]
    jump = T05B_REF["kernel_doubles"]["JUMP"]["inputs"]
    feed = stream(registered["inlet"])
    assert feed.n == tuple(float(value) for value in jump["n_mol_per_s"])
    duty = float(jump["H_target_W"]) - enthalpy(feed, registered["inlet_phase"])
    unit = PHFlash(
        unit_id="U-PHF",
        provider=Jump(PROVIDER),
        duty=duty,
        context=CONTEXT,
        pressure_drop=float(registered["pressure_drop"]),
        inlet_phase=registered["inlet_phase"],
    )
    result = unit.evaluate({"inlet": [feed]}, CONTEXT)
    lines["PHF-1 on the JUMP double"] = first_line(result.message)

    # No unit exposes the kernel's evaluation budget; the budget refusal is checked through
    # `closure_failure`, the one path every PH-type unit turns a kernel answer into its own.
    nominal = REF["unit_cases"]["PHF-1"]["inputs"]
    inlet = stream(nominal["inlet"])
    target = enthalpy(inlet, "LIQUID") + float(nominal["duty"])
    answer = ph_state(PROVIDER, inlet.n, inlet.pressure, target, CONTEXT, max_evaluations=10)
    lines["PHF-1 with a 10-evaluation budget"] = first_line(closure_failure(answer).message)
    return lines


def test_a16_every_registered_failure_starts_with_its_code_and_a_catalogued_one() -> None:
    """No registered failure or construction case yields a first line outside §13.3, and each
    yields its registered code byte for byte."""
    for case_id, line in registered_first_lines().items():
        registered = (
            REF["unit_cases"][case_id]["expected"]["code"]
            if case_id in REF["unit_cases"]
            else REF["specification_errors"][case_id]["code"]
        )
        assert line == registered, case_id
        assert len(catalogued(line)) == 1, f"{case_id}: {line!r} is not one §13.3 code"


def test_a16_every_catalogued_code_is_produced() -> None:
    """Every §13.3 code is some case's first line: 22 by registered cases, the other four by the
    constructed ones, each of which must land on exactly the code it was built for."""
    constructed = constructed_first_lines()
    assert {name: catalogued(line) for name, line in constructed.items()} == {
        "PHF-1 at 450 K": ["state_outside_domain(<port>)"],
        "HX-3 at 1 MW": ["outlet_outside_domain"],
        "PHF-1 on the JUMP double": ["ph_ill_conditioned"],
        "PHF-1 with a 10-evaluation budget": ["ph_not_converged"],
    }
    by_registered = {
        code for line in registered_first_lines().values() for code in catalogued(line)
    }
    assert len(by_registered) == 22
    produced = by_registered | {code for line in constructed.values() for code in catalogued(line)}
    assert produced == set(CATALOGUE)
