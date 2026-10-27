"""S11 WO-I1: `syn001.column` registered in the binder and the verifier (design note §5's I1 row,
§10.6, §10.12; rulings item 9).

S11.A39 (the registries agree, 23 members, the column's bases), A91 (a dotted id beside a column is
the reader's refusal), A93 (the sixteen `_PARAMETER_KINDS` entries of R-825), and the column's
`MODEL_CHECKS` entry, which is `s11_column_support.column_checks()`.
"""

from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any

import pytest
from s11_column_support import column_checks, column_revision, quantity
from test_s02_column_wo1 import SPECS

from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BASES,
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.models.revision_flowsheet import WILSON_BASIS, parse_revision, required_kind
from openflowsheet.verify.table import MODEL_CHECKS

COLUMN = "syn001.column"
M1 = SPECS["M1"]

#: S11 design §10.6 (R-825): the sixteen names and their kinds; §10.5's twelve end names.
R825 = {
    "stage_count": "dimensionless",
    "stage_pressure": "pressure",
    "feed_stage": "dimensionless",
    "stage_duty": "heat_rate",
    "condenser_reflux_ratio": "dimensionless",
    "condenser_distillate_rate": "molar_flow",
    "condenser_duty": "heat_rate",
    "condenser_purity": "dimensionless",
    "condenser_recovery": "dimensionless",
    "condenser_temperature": "temperature",
    "reboiler_boilup_ratio": "dimensionless",
    "reboiler_bottoms_rate": "molar_flow",
    "reboiler_duty": "heat_rate",
    "reboiler_purity": "dimensionless",
    "reboiler_recovery": "dimensionless",
    "reboiler_temperature": "temperature",
}
#: A spelling of each name as an instance parameter (an attribute where the name takes one).
SPELLED = {
    "stage_pressure": "stage_pressure.1",
    "feed_stage": "feed_stage.S-FEED",
    "stage_duty": "stage_duty.2",
    "condenser_purity": "condenser_purity.A",
    "condenser_recovery": "condenser_recovery.A",
    "condenser_temperature": "condenser_temperature.1",
    "reboiler_purity": "reboiler_purity.C",
    "reboiler_recovery": "reboiler_recovery.C",
    "reboiler_temperature": "reboiler_temperature.10",
}


def _column_instance(document: dict[str, Any], unit: str = "UCOL") -> dict[str, Any]:
    instance: dict[str, Any] = next(i for i in document["instances"] if i["id"] == unit)
    return instance


# -- S11.A39 ---------------------------------------------------------------------------------------


def test_a39_the_registries_agree_and_the_column_binds_on_syn001_and_wilson() -> None:
    assert set(MODEL_BASES) == set(MODEL_BUILDERS) == set(MODEL_SIGNATURES)
    assert len(MODEL_BUILDERS) == 23
    # §9: the provider id the Wilson registry row holds (v1 until D5).
    assert MODEL_BASES[COLUMN] == frozenset({"syn001", WILSON_BASIS.provider_id})
    assert WILSON_BASIS.provider_id == "wilson-ig-v1"


def test_the_column_binds_without_a_monkeypatched_registry() -> None:
    binding = bind_revision_flowsheet(column_revision(M1))
    assert isinstance(binding, RevisionBinding), binding


def test_the_column_checks_are_the_verifier_rows_b4_built() -> None:
    assert MODEL_CHECKS[COLUMN] == column_checks()


# -- S11.A91 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("stage", [1, 5, 10])
def test_a91_an_instance_named_after_a_column_stage_is_refused_before_binding(stage: int) -> None:
    """S11.A91 (restated, R-838): `C1.stage.<j>` beside column `C1` is the reader's
    `id_unsupported(C1.stage.<j>)`, before binding."""
    document = column_revision(M1, unit="C1")
    sink = copy.deepcopy(
        next(i for i in document["instances"] if i["model"]["id"] == "syn001.product_sink")
    )
    sink["id"] = f"C1.stage.{stage}"
    document["instances"].append(sink)
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound), refused
    assert (refused.kind, refused.detail) == ("unsupported", f"id_unsupported(C1.stage.{stage})")


# -- S11.A93 ---------------------------------------------------------------------------------------


def test_a93_the_sixteen_names_have_their_kinds() -> None:
    for name, kind in R825.items():
        assert required_kind(f"parameters.{SPELLED.get(name, name)}") == kind, name


@pytest.mark.parametrize("name", sorted(R825))
def test_a93_a_wrong_declared_kind_is_refused(name: str) -> None:
    """Each of the sixteen names, declared in another kind, is
    `parameter_kind_unsupported(<U>.<name>)`."""
    spelled = SPELLED.get(name, name)
    wrong = "temperature" if R825[name] != "temperature" else "pressure"
    document = column_revision(M1)
    _column_instance(document)["parameters"][spelled] = quantity(1.0, wrong)
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound), refused
    assert refused.detail == f"parameter_kind_unsupported(UCOL.{spelled})"


def test_a93_a_stage_pressure_in_bar_reads_as_unit_conversion_v2s_pa_value() -> None:
    document = column_revision(M1)
    value = 1.2345678901
    _column_instance(document)["parameters"]["stage_pressure.1"] = {
        **quantity(value, "pressure"),
        "unit": "bar",
    }
    view = parse_revision(document)
    (instance,) = (i for i in view.instances if i.unit_id == "UCOL")
    expected = float(Fraction(repr(value)) * 100000)
    assert instance.parameters["stage_pressure.1"].hex() == expected.hex()
