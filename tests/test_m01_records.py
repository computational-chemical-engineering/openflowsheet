"""M01.A01, A03 (records half): the five C1 component records and their loader (M01 spec §3, WO-1).

The expectations are the committed `benchmarks/m01/components.yaml` itself, read here with
`yaml.safe_load` independently of `openflowsheet.thermo.pr_c1`'s parser: the loader must hand the
provider exactly the parsed floats (bitwise), in the registered order, from the packaged bytes.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from test_schemas_p01 import validator_for

from openflowsheet.resources import PACKAGED, packaged
from openflowsheet.thermo.pr_c1 import (
    COMPONENTS,
    RECORDS_PATH,
    REFERENCE_CONVENTION,
    load_records,
    parse_records,
)
from openflowsheet.units import check_quantity

RECORDS = REPO_ROOT / "benchmarks" / "m01" / "components.yaml"
DOCUMENT: dict[str, Any] = yaml.safe_load(RECORDS.read_text(encoding="utf-8"))
BY_ID = {record["id"]: record for record in DOCUMENT["components"]}


def test_a01_five_records_in_the_registered_order() -> None:
    assert [record["id"] for record in DOCUMENT["components"]] == ["H2", "N2", "NH3", "Ar", "CH4"]
    assert COMPONENTS == ("H2", "N2", "NH3", "Ar", "CH4")
    assert DOCUMENT["reference_convention"] == REFERENCE_CONVENTION == "PR-C1-ref-v1"


@pytest.mark.parametrize("component", COMPONENTS)
def test_a01_each_record_validates_and_is_real_and_verified(component: str) -> None:
    record = BY_ID[component]
    validator = validator_for("component_record")
    assert [error.message for error in validator.iter_errors(record)] == []
    for name, quantity in [
        ("molecular_weight", record["molecular_weight"]),
        *record["parameters"].items(),
    ]:
        assert check_quantity(quantity) == (), name
    assert record["synthetic"] is False
    assert record["elemental_verification"] == "VERIFIED"


def test_the_records_are_package_data_read_from_the_single_repository_copy() -> None:
    assert RECORDS_PATH in PACKAGED
    data = packaged(RECORDS_PATH).read_bytes()
    assert data == RECORDS.read_bytes()
    assert load_records().sha256 == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("index", range(5))
def test_a03_the_loader_hands_over_the_parsed_floats_bitwise(index: int) -> None:
    loaded = load_records().components[index]
    record = DOCUMENT["components"][index]
    parameters = record["parameters"]

    def same(left: float, right: Any) -> bool:
        return isinstance(right, float) and left.hex() == right.hex()

    assert loaded.id == record["id"] == COMPONENTS[index]
    assert same(loaded.molar_mass, record["molecular_weight"]["value"])
    assert same(loaded.critical_temperature, parameters["critical_temperature"]["value"])
    assert same(loaded.critical_pressure, parameters["critical_pressure"]["value"])
    assert same(loaded.acentric_factor, parameters["acentric_factor"]["value"])
    assert same(loaded.formation_enthalpy, parameters["standard_formation_enthalpy"]["value"])
    for k in range(5):
        assert same(loaded.cp_coefficients[k], parameters[f"ideal_gas_cp_b{k}"]["value"]), k
    assert loaded.cp_temperature_range == (200.0, 1000.0)
    assert dict(loaded.elemental_composition) == record["elemental_composition"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda text: text.replace(
                "reference_convention: PR-C1-ref-v1", "reference_convention: X"
            ),
            "reference_convention",
        ),
        (lambda text: text.replace("  - id: N2\n", "  - id: N2x\n"), "component order"),
        (lambda text: text.replace("unit: Pa\n", "unit: bar\n", 1), "unit"),
    ],
)
def test_a_record_file_off_the_registration_is_refused(mutation: Any, message: str) -> None:
    text = RECORDS.read_text(encoding="utf-8")
    changed = mutation(text)
    assert changed != text
    with pytest.raises(ValueError, match=message):
        parse_records(changed.encode("utf-8"))
