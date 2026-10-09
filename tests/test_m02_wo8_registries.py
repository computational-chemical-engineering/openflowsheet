"""M02 WO-8.3: the registries' full key sets and their `c1.` entries (design note §14.2 B13;
register R-255).

B13 restricts the four tests that pin a registry literally to their `syn001.` keys, their literals
unchanged: `test_t05_w1a_splits::test_registry_holds_one_rule_per_lifting_model`,
`test_t05b_zero_flow::test_the_registry_names_each_models_zero_flow_ids`,
`test_t05b_dormancy::test_b23_the_registry_is_the_registered_one` and
`test_t05_table_independence::test_the_verifiers_dormant_outlets_are_the_solvers_as_data`. This
file pins each registry's full key set and its `c1.` entries exactly, so together the two pin
everything the originals pinned, plus the additions: no check is narrowed.
"""

from __future__ import annotations

from openflowsheet.orchestrator.splits import DORMANCY_RULES, SPLIT_RULES, DormancyRule, SplitRule
from openflowsheet.verify.table import (
    EXTERNAL_DUTY_MODELS,
    FEED_MODELS,
    MODEL_CHECKS,
    PRODUCT_MODELS,
    _c1_flash_material,
    _feed_specification,
    _flash_energy,
    _flash_specification,
    _heater_energy,
    _heater_specification,
    _mixer_energy,
    _mixer_material,
    _pump_material,
    _splitter_energy,
    _splitter_material,
    _splitter_specification,
)
from openflowsheet.verify.zero_flow import DORMANT_OUTLETS, PRODUCT_MOLE_ROWS, DormantOutlet

SYN001_SPLIT_MODELS = {
    "syn001.tp_heater",
    "syn001.tp_flash",
    "syn001.valve",
    "syn001.conversion_reactor",
    "syn001.ph_flash",
}
SYN001_DORMANCY_KEYS = {
    ("syn001.liquid_pump", None),
    ("syn001.adiabatic_mixer", None),
    ("syn001.heat_exchanger", "duty"),
    ("syn001.heat_exchanger", "hot_outlet_temperature"),
    ("syn001.heat_exchanger", "cold_outlet_temperature"),
}


def test_the_split_registry_is_syn001s_five_and_the_c1_flash() -> None:
    assert set(SPLIT_RULES) == SYN001_SPLIT_MODELS | {"c1.tp_flash"}
    assert SPLIT_RULES["c1.tp_flash"] == SplitRule(
        "products",
        "C1FL-equilibrium",
        "TP",
        "C1FL-mole",
        None,
        vapour_only=("H2", "N2", "Ar", "CH4"),
    )


def test_no_syn001_rule_declares_a_vapour_only_component() -> None:
    """B13: SYN-001's rules have an empty `vapour_only`, so they run today's statements."""
    assert all(SPLIT_RULES[model].vapour_only == () for model in SYN001_SPLIT_MODELS)


def test_the_dormancy_registry_is_syn001s_and_the_c1_mixers_vapour_outlet() -> None:
    assert set(DORMANCY_RULES) == SYN001_DORMANCY_KEYS | {("c1.adiabatic_mixer", None)}
    assert DORMANCY_RULES[("c1.adiabatic_mixer", None)] == (
        DormancyRule("outlet", "inlet", "C1MIX-energy", None, "VAPOR"),
    )


# -- the verifier's registries (WO-8.4; B13, B15 item 6) -------------------------------------------

C1_MODELS = {
    "c1.feed_source",
    "c1.product_sink",
    "c1.stream_splitter",
    "c1.adiabatic_mixer",
    "c1.tp_heater",
    "c1.tp_flash",
}


def test_the_verifiers_dormant_outlets_and_product_mole_rows_add_the_c1_entries() -> None:
    assert set(DORMANT_OUTLETS) == {
        "syn001.liquid_pump",
        "syn001.adiabatic_mixer",
        "syn001.heat_exchanger",
        "c1.adiabatic_mixer",
    }
    assert DORMANT_OUTLETS["c1.adiabatic_mixer"] == (
        DormantOutlet("outlet", "inlet", "C1MIX-energy", None),
    )
    assert dict(PRODUCT_MOLE_ROWS) == {
        "syn001.tp_flash": "FLASH-mole",
        "syn001.ph_flash": "PHF-mole",
        "c1.tp_flash": "C1FL-mole",
    }


def test_the_verifiers_c1_dormant_outlet_is_the_solvers_as_data() -> None:
    """`test_t05_table_independence`'s comparison, for the `c1.` keys it is restricted from."""
    (solver,) = DORMANCY_RULES[("c1.adiabatic_mixer", None)]
    (verifier,) = DORMANT_OUTLETS["c1.adiabatic_mixer"]
    assert (verifier.outlet, verifier.trigger, verifier.swapped, verifier.side) == (
        solver.outlet,
        solver.trigger,
        solver.swapped,
        solver.side,
    )
    assert verifier.unless is None


def test_model_checks_hold_the_c1_entries_from_syn001s_rule_functions() -> None:
    assert C1_MODELS <= set(MODEL_CHECKS)
    rules = {
        model: (
            entry.material,
            entry.energy,
            entry.specification,
            entry.declared_ports,
        )
        for model, entry in MODEL_CHECKS.items()
        if model.startswith("c1.")
    }
    nothing = MODEL_CHECKS["c1.product_sink"].material
    assert rules == {
        "c1.feed_source": (nothing, nothing, _feed_specification, ()),
        "c1.product_sink": (nothing, nothing, nothing, ()),
        "c1.stream_splitter": (
            _splitter_material,
            _splitter_energy,
            _splitter_specification,
            (),
        ),
        "c1.adiabatic_mixer": (
            _mixer_material,
            _mixer_energy,
            nothing,
            (("inlet", True), ("outlet", False)),
        ),
        "c1.tp_heater": (
            _pump_material,
            _heater_energy,
            _heater_specification,
            (("inlet", False), ("outlet", False)),
        ),
        "c1.tp_flash": (
            _c1_flash_material,
            _flash_energy,
            _flash_specification,
            (("inlet", False),),
        ),
    }


def test_the_envelope_sets_gain_the_c1_ids() -> None:
    assert FEED_MODELS == {"syn001.feed_source", "c1.feed_source"}
    assert PRODUCT_MODELS == {"syn001.product_sink", "c1.product_sink"}
    assert EXTERNAL_DUTY_MODELS[-2:] == ("c1.tp_heater", "c1.tp_flash")
    assert [m for m in EXTERNAL_DUTY_MODELS if m.startswith("c1.")] == [
        "c1.tp_heater",
        "c1.tp_flash",
    ]
