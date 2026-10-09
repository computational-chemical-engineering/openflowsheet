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
