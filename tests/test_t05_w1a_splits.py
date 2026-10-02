"""T05 W1.a: the lifted-split registry and the revision-side residence-time mapping.

Design note `docs/design/T05-generalization.md` §3, §5, §7 (W1.a). The registry is proved equal
to SYN-001's hand-named descriptors — by value and by the `repr` digest protocol P (v) pins — and
the structural agreement of §3.3 is checked on the legacy declaration, with a negative control per
check so that each is shown able to fail. The T05 descriptors are checked field by field from
literal wirings: they need only ids, so no T05 model class is read.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

import pytest

from openflowsheet.application.binding import structural_inputs
from openflowsheet.compiled import EvaluationContext
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.models import Wiring
from openflowsheet.models.syn001 import COMPONENTS
from openflowsheet.models.syn001.flowsheet import WIRING, Syn001Flowsheet
from openflowsheet.orchestrator.execution import declaration_identity
from openflowsheet.orchestrator.mass import residence_time, syn001_residence_time
from openflowsheet.orchestrator.region import LiftedSplit, syn001_lifted_splits
from openflowsheet.orchestrator.splits import SPLIT_RULES, check_agreement, lifted_splits
from openflowsheet.thermo.syn001 import Syn001Provider

#: W0.1's value (`docs/t05-measurements.md`), protocol P item (v).
SPLITS_REPR_SHA256 = "fc36484e7a89f0e844a0f2e1148ef89052bdd97aaa7a63538685bc505a11e17a"


@pytest.fixture(scope="module")
def legacy() -> dict[str, Any]:
    flowsheet = Syn001Flowsheet(
        provider=Syn001Provider(),
        context=EvaluationContext(
            model_version="t05-w1a", constants_sha256="0" * 64, phase_signature=None
        ),
    )
    spec, _, row_units = structural_inputs(flowsheet)
    model_version, constants = declaration_identity(spec)
    declaration = trace_declaration(
        spec, model_version=model_version, constants_sha256=constants, row_units=row_units
    )
    instances = [(u.unit_id, u.model_id, WIRING[u.unit_id]) for u in flowsheet.units()]
    return {
        "spec": spec,
        "row_units": row_units,
        "declaration": declaration,
        "instances": instances,
    }


def test_registry_holds_one_rule_per_lifting_model() -> None:
    assert {model: (rule.style, rule.equilibrium) for model, rule in SPLIT_RULES.items()} == {
        "syn001.tp_heater": ("outlet", "HEAT-equilibrium"),
        "syn001.tp_flash": ("products", "FLASH-equilibrium"),
        "syn001.valve": ("outlet", "VLV-equilibrium"),
        "syn001.conversion_reactor": ("outlet", "RX-equilibrium"),
        "syn001.ph_flash": ("products", "PHF-equilibrium"),
    }


def test_registry_reproduces_the_syn001_descriptors(legacy: dict[str, Any]) -> None:
    general = lifted_splits(legacy["instances"], COMPONENTS)
    assert general == syn001_lifted_splits(COMPONENTS)
    assert hashlib.sha256(repr(general).encode()).hexdigest() == SPLITS_REPR_SHA256
    # The legacy function itself has not moved (protocol P item v).
    assert (
        hashlib.sha256(repr(syn001_lifted_splits(("A", "B", "C"))).encode()).hexdigest()
        == SPLITS_REPR_SHA256
    )


def test_descriptors_follow_the_order_given(legacy: dict[str, Any]) -> None:
    order = [split.unit for split in lifted_splits(legacy["instances"][::-1], COMPONENTS)]
    assert order == ["U-FLASH", "U-HEAT"]


def test_structural_agreement_holds_on_syn001(legacy: dict[str, Any]) -> None:
    splits = lifted_splits(legacy["instances"], COMPONENTS)
    check_agreement(
        legacy["instances"], splits, legacy["spec"], legacy["row_units"], legacy["declaration"]
    )


def _explicit_agreement(legacy: dict[str, Any], splits: tuple[LiftedSplit, ...]) -> None:
    """§3.3 (a)–(e) written out against the declaration, independently of `check_agreement`."""
    spec, row_units, declaration = legacy["spec"], legacy["row_units"], legacy["declaration"]
    squared = [row for row in spec.equation_ids if spec.row_kinds[row] == "molar_flow_squared"]
    # (a)
    assert {split.unit for split in splits} == {row_units[row] for row in squared}
    for split in splits:
        # (b)
        assert split.equilibrium_rows == tuple(r for r in squared if row_units[r] == split.unit)
        # (c)
        for name in (
            *split.feed,
            split.temperature,
            split.pressure,
            *split.vapor,
            *split.liquid,
            split.vapor_total,
            split.liquid_total,
        ):
            assert name in spec.variable_ids
        # (d)
        assert set(declaration.rows[split.vapor_definition].columns) == {
            *split.vapor,
            split.vapor_total,
        }
        assert set(declaration.rows[split.liquid_definition].columns) == {
            *split.liquid,
            split.liquid_total,
        }
        # (e)
        for row, vapor, liquid in zip(
            split.equilibrium_rows, split.vapor, split.liquid, strict=True
        ):
            assert {vapor, liquid, split.vapor_total, split.liquid_total} <= set(
                declaration.rows[row].columns
            )


def test_structural_agreement_a_to_e_written_out(legacy: dict[str, Any]) -> None:
    _explicit_agreement(legacy, lifted_splits(legacy["instances"], COMPONENTS))


def test_agreement_refuses_an_unregistered_lifting_unit(legacy: dict[str, Any]) -> None:
    """(a): a unit with equilibrium rows whose model has no rule."""
    instances = [
        (unit, "test.lifter" if unit == "U-HEAT" else model, wiring)
        for unit, model, wiring in legacy["instances"]
    ]
    splits = lifted_splits(instances, COMPONENTS)
    with pytest.raises(ValueError, match=r"^lifted_split_unregistered\(test\.lifter\)$"):
        check_agreement(
            instances, splits, legacy["spec"], legacy["row_units"], legacy["declaration"]
        )


def test_agreement_refuses_a_rule_without_rows(legacy: dict[str, Any]) -> None:
    """(a): a descriptor for a unit that authors no equilibrium row."""
    splits = lifted_splits(legacy["instances"], COMPONENTS)
    stray = replace(splits[0], unit="U-SPLIT")
    with pytest.raises(ValueError, match=r"^lifted_split_without_rows\(U-SPLIT\)$"):
        check_agreement(
            legacy["instances"],
            (*splits, stray),
            legacy["spec"],
            legacy["row_units"],
            legacy["declaration"],
        )


@pytest.mark.parametrize(
    ("corrupt", "code"),
    [
        (
            lambda s: replace(s, equilibrium_rows=s.equilibrium_rows[::-1]),
            "lifted_split_rows_disagree",
        ),
        (lambda s: replace(s, vapor_total="S3.Vx"), "lifted_split_variables_absent"),
        (
            lambda s: replace(s, vapor_definition=s.liquid_definition),
            "lifted_split_definition_disagrees",
        ),
        (
            lambda s: replace(s, vapor=(s.vapor[1], s.vapor[0], s.vapor[2])),
            "lifted_split_equilibrium_disagrees",
        ),
    ],
    ids=["b-order", "c-absent", "d-definition", "e-equilibrium"],
)
def test_agreement_refuses_a_descriptor_that_disagrees(
    legacy: dict[str, Any], corrupt: Any, code: str
) -> None:
    """(b)–(e): each check fails on a descriptor corrupted in exactly its own way."""
    heater, flash = lifted_splits(legacy["instances"], COMPONENTS)
    with pytest.raises(ValueError, match=rf"^{code}\(U-HEAT"):
        check_agreement(
            legacy["instances"],
            (corrupt(heater), flash),
            legacy["spec"],
            legacy["row_units"],
            legacy["declaration"],
        )


def test_residence_time_over_the_syn001_wiring_is_the_legacy_mapping() -> None:
    assert residence_time(WIRING, COMPONENTS) == syn001_residence_time(COMPONENTS)


# -- the T05 descriptors, from literal wirings -------------------------------------------------


def _one(unit: str, model: str, wiring: Wiring) -> LiftedSplit:
    (split,) = lifted_splits([(unit, model, wiring)], COMPONENTS)
    return split


def test_valve_descriptor_is_outlet_style() -> None:
    split = _one("U-VLV", "syn001.valve", Wiring({"inlet": ("S3",), "outlet": ("S4",)}))
    assert split == LiftedSplit(
        unit="U-VLV",
        stream="S4",
        feed=("S4.n.A", "S4.n.B", "S4.n.C"),
        temperature="S4.T",
        pressure="S4.P",
        vapor=("S4.vap.A", "S4.vap.B", "S4.vap.C"),
        liquid=("S4.liq.A", "S4.liq.B", "S4.liq.C"),
        vapor_total="S4.V",
        liquid_total="S4.L",
        equilibrium_rows=(
            "U-VLV:VLV-equilibrium:A",
            "U-VLV:VLV-equilibrium:B",
            "U-VLV:VLV-equilibrium:C",
        ),
        vapor_definition="U-VLV:Vdef",
        liquid_definition="U-VLV:Ldef",
    )


def test_reactor_descriptor_is_outlet_style() -> None:
    split = _one("U-RX", "syn001.conversion_reactor", Wiring({"inlet": ("S2",), "outlet": ("S3",)}))
    assert split == LiftedSplit(
        unit="U-RX",
        stream="S3",
        feed=("S3.n.A", "S3.n.B", "S3.n.C"),
        temperature="S3.T",
        pressure="S3.P",
        vapor=("S3.vap.A", "S3.vap.B", "S3.vap.C"),
        liquid=("S3.liq.A", "S3.liq.B", "S3.liq.C"),
        vapor_total="S3.V",
        liquid_total="S3.L",
        equilibrium_rows=(
            "U-RX:RX-equilibrium:A",
            "U-RX:RX-equilibrium:B",
            "U-RX:RX-equilibrium:C",
        ),
        vapor_definition="U-RX:Vdef",
        liquid_definition="U-RX:Ldef",
    )


def test_ph_flash_descriptor_is_products_style() -> None:
    split = _one(
        "U-PHF",
        "syn001.ph_flash",
        Wiring({"inlet": ("S4",), "vapor": ("S5",), "liquid": ("S6",)}),
    )
    assert split == LiftedSplit(
        unit="U-PHF",
        stream="S4",
        feed=("S4.n.A", "S4.n.B", "S4.n.C"),
        temperature="S5.T",
        pressure="S5.P",
        vapor=("S5.n.A", "S5.n.B", "S5.n.C"),
        liquid=("S6.n.A", "S6.n.B", "S6.n.C"),
        vapor_total="S5.N",
        liquid_total="S6.N",
        equilibrium_rows=(
            "U-PHF:PHF-equilibrium:A",
            "U-PHF:PHF-equilibrium:B",
            "U-PHF:PHF-equilibrium:C",
        ),
        vapor_definition="U-PHF:Ndef:vapor",
        liquid_definition="U-PHF:Ndef:liquid",
    )


def test_models_without_a_rule_contribute_no_descriptor() -> None:
    instances = [
        ("U-P", "syn001.liquid_pump", Wiring({"inlet": ("S1",), "outlet": ("S2",)})),
        ("U-M", "syn001.adiabatic_mixer", Wiring({"inlet": ("S2", "S9"), "outlet": ("S3",)})),
    ]
    assert lifted_splits(instances, COMPONENTS) == ()
