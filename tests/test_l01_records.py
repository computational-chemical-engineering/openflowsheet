"""L01.A01–A12, and A22 for the record files: the nine `pr-lib-v1` component records (L01 spec §4.1,
§5; ADR 0043 D3, D6; WO-L01-1).

The expectations are independent of the records: the C1 file (A02), the CAS check-digit rule and
W27's registered aliases (A03), the registered atomic-weight table (A04), the registered elements
(A05), the unchanged ComponentRecord schema (A06), and the literature table and tolerances of
`docs/derivations/scripts/l01_projection.json` (A07–A11; † values, spec §10 Q-5). A12 reads the
retrieval script's committed record `benchmarks/l01/components-crosscheck.json`, pinned to the
record bytes it was made from, and re-runs the script where the source packages are installed.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from test_schemas_p01 import validator_for

from openflowsheet.resources import PACKAGED, packaged
from openflowsheet.thermo import pr_c1, pr_lib
from openflowsheet.thermo.pr_lib import (
    COMPONENTS,
    RECORDS_PATH,
    REFERENCE_CONVENTION,
    RecordError,
    load_records,
    parse_records,
)
from openflowsheet.units import check_quantity

RECORDS = REPO_ROOT / "benchmarks" / "l01" / "components.yaml"
C1_RECORDS = REPO_ROOT / "benchmarks" / "m01" / "components.yaml"
CROSSCHECK = REPO_ROOT / "benchmarks" / "l01" / "components-crosscheck.json"
CROSSCHECK_SCRIPT = REPO_ROOT / "benchmarks" / "l01" / "components_crosscheck.py"
PROJECTION = json.loads(
    (REPO_ROOT / "docs" / "derivations" / "scripts" / "l01_projection.json").read_text(
        encoding="utf-8"
    )
)
DOCUMENT: dict[str, Any] = yaml.safe_load(RECORDS.read_text(encoding="utf-8"))
BY_ID = {record["id"]: record for record in DOCUMENT["components"]}
C1_BY_ID = {
    record["id"]: record
    for record in yaml.safe_load(C1_RECORDS.read_text(encoding="utf-8"))["components"]
}
REGISTRATION = json.loads(
    (REPO_ROOT / "benchmarks" / "m06" / "openidaes450" / "registration.json").read_text(
        encoding="utf-8"
    )
)
LIBRARY = PROJECTION["library"]
NEW_BY_ID = {entry["id"]: entry for entry in LIBRARY["new"]}
LIT = PROJECTION["literature"]
TOL = {name: float(value) for name, value in PROJECTION["tolerance"].items()}

#: Spec §4.1: the identity order.
NINE = ("H2", "N2", "Ar", "CH4", "H2O", "CO2", "O2", "C2H6", "C3H8")
COPIED = ("H2", "N2", "Ar", "CH4")
NEW = ("H2O", "CO2", "O2", "C2H6", "C3H8")
INORGANIC = ("H2O", "CO2", "O2")
HYDROCARBON = ("C2H6", "C3H8")
#: J/(mol K), exact in the 2019 SI (the records' header).
R = 8.31446261815324


def _value(record: dict[str, Any], name: str) -> float:
    value = record["parameters"][name]["value"]
    assert isinstance(value, float), (record["id"], name, value)
    return value


# ================================================================================ L01.A01


def test_a01_nine_records_in_the_registered_order() -> None:
    assert [record["id"] for record in DOCUMENT["components"]] == list(NINE)
    assert COMPONENTS == NINE
    assert LIBRARY["copied_from_c1"] == list(COPIED)
    assert [entry["id"] for entry in LIBRARY["new"]] == list(NEW)
    assert DOCUMENT["reference_convention"] == REFERENCE_CONVENTION == "PR-C1-ref-v1"
    assert DOCUMENT["record_schema"] == "schemas/component-record.schema.json"


def test_a01_the_records_are_not_packaged_before_wo_l01_3() -> None:
    # Spec §12.5 (R-541): until WO-L01-3, after Frank's L01-Q4, the file is not in `PACKAGED`, has
    # no `_data` copy, and `load_records` reads the source checkout's single copy.
    data = RECORDS.read_bytes()
    assert RECORDS_PATH == "benchmarks/l01/components.yaml"
    assert RECORDS_PATH not in PACKAGED
    copy = REPO_ROOT / "src" / "openflowsheet" / "_data" / RECORDS_PATH
    assert not copy.exists() and not copy.is_symlink()
    with pytest.raises(KeyError):
        packaged(RECORDS_PATH)
    checkout = pr_lib._checkout_records()
    assert checkout is not None and checkout.resolve() == RECORDS.resolve()
    assert load_records().sha256 == hashlib.sha256(data).hexdigest()


# ================================================================================ L01.A02


@pytest.mark.parametrize("component", COPIED)
def test_a02_the_copied_records_equal_c1_value_for_value(component: str) -> None:
    record, c1 = BY_ID[component], C1_BY_ID[component]
    # Every parsed value, unit, provenance and rights string (whole-record equality) ...
    assert record == c1
    # ... and every float bitwise, as the two loaders hand them over.
    for name in c1["parameters"]:
        assert _value(record, name).hex() == _value(c1, name).hex(), name
    lib = load_records().components[NINE.index(component)]
    ref = pr_c1.load_records().components[pr_c1.COMPONENTS.index(component)]
    pairs = [
        (lib.molar_mass, ref.molar_mass),
        (lib.critical_temperature, ref.critical_temperature),
        (lib.critical_pressure, ref.critical_pressure),
        (lib.acentric_factor, ref.acentric_factor),
        (lib.formation_enthalpy, ref.formation_enthalpy),
        *zip(lib.cp_coefficients, ref.cp_coefficients, strict=True),
        *zip(lib.cp_temperature_range, ref.cp_temperature_range, strict=True),
    ]
    assert [a.hex() for a, _ in pairs] == [b.hex() for _, b in pairs]
    assert (lib.id, lib.name, dict(lib.elemental_composition)) == (
        ref.id,
        ref.name,
        dict(ref.elemental_composition),
    )


# ================================================================================ L01.A03


def _cas_valid(cas: str) -> bool:
    """The CAS RN check digit: the weighted sum (weights 1, 2, ... from the right) mod 10."""
    parts = cas.split("-")
    if len(parts) != 3 or not all(p.isdigit() for p in parts) or len(parts[2]) != 1:
        return False
    body = parts[0] + parts[1]
    total = sum(int(d) * w for w, d in enumerate(reversed(body), start=1))
    return total % 10 == int(parts[2])


def test_a03_the_cas_check_is_not_vacuous() -> None:
    assert _cas_valid("7732-18-5") and _cas_valid("124-38-9")
    assert not _cas_valid("7732-18-6")
    assert not _cas_valid("124-38-8")


@pytest.mark.parametrize("component", NINE)
def test_a03_cas_check_digit_and_the_registered_w27_alias(component: str) -> None:
    cas = BY_ID[component]["identifiers"]["cas"]
    assert _cas_valid(cas), cas
    assert REGISTRATION["components"]["aliases"][component] == cas
    if component in NEW:
        assert NEW_BY_ID[component]["cas"] == cas


# ================================================================================ L01.A04


@pytest.mark.parametrize("component", NEW)
def test_a04_molar_mass_from_the_registered_atomic_weights(component: str) -> None:
    weights = {e: Decimal(a) for e, a in LIBRARY["atomic_weights_g_per_mol"].items()}
    assert weights == {
        "H": Decimal("1.00794"),
        "C": Decimal("12.0107"),
        "N": Decimal("14.0067"),
        "O": Decimal("15.9994"),
        "Ar": Decimal("39.948"),
    }
    elements = NEW_BY_ID[component]["elements"]
    expected = sum(weights[e] * n for e, n in elements.items()) / 1000
    assert expected == Decimal(NEW_BY_ID[component]["molar_mass_kg_per_mol"])
    quantity = BY_ID[component]["molecular_weight"]
    assert quantity["unit"] == "kg/mol"
    assert abs(quantity["value"] / float(expected) - 1.0) <= 1e-12


# ================================================================================ L01.A05


@pytest.mark.parametrize("component", NEW)
def test_a05_elements_are_the_registered_ones_and_verified(component: str) -> None:
    record = BY_ID[component]
    assert record["elemental_composition"] == NEW_BY_ID[component]["elements"]
    assert record["elemental_verification"] == "VERIFIED"
    assert record["identifiers"]["formula"] == NEW_BY_ID[component]["formula"]
    assert record["name"] == NEW_BY_ID[component]["name"]


# ================================================================================ L01.A06


@pytest.mark.parametrize("component", NINE)
def test_a06_each_record_validates_against_the_unchanged_schema(component: str) -> None:
    record = BY_ID[component]
    validator = validator_for("component_record")
    assert [error.message for error in validator.iter_errors(record)] == []
    for name, quantity in [
        ("molecular_weight", record["molecular_weight"]),
        *record["parameters"].items(),
    ]:
        assert check_quantity(quantity) == (), name
    assert record["synthetic"] is False


def _swap_h2o_and_co2(text: str) -> str:
    head, rest = text.split("  - id: H2O\n", 1)
    h2o, tail = rest.split("  - id: CO2\n", 1)
    co2, after = tail.split("  - id: O2\n", 1)
    return head + "  - id: CO2\n" + co2 + "  - id: H2O\n" + h2o + "  - id: O2\n" + after


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (_swap_h2o_and_co2, r"component order \[.*'CO2', 'H2O'.*\] is not the registered"),
        (
            lambda text: text.replace("unit: Pa\n", "unit: bar\n", 1),
            r"H2\.critical_pressure: unit 'bar', the record must state 'Pa'",
        ),
        (
            lambda text: text.replace(
                "reference_convention: PR-C1-ref-v1", "reference_convention: X"
            ),
            r"reference_convention 'X' is not 'PR-C1-ref-v1'",
        ),
    ],
    ids=["reordered-ids", "critical-pressure-in-bar", "reference-convention-X"],
)
def test_a06_the_loader_refuses_a_corrupted_copy(mutation: Any, message: str) -> None:
    text = RECORDS.read_text(encoding="utf-8")
    corrupted = mutation(text)
    assert corrupted != text
    with pytest.raises(RecordError, match=message):
        parse_records(corrupted.encode("utf-8"))


def test_a06_the_loader_hands_over_the_parsed_floats_bitwise() -> None:
    loaded = load_records()
    assert tuple(c.id for c in loaded.components) == NINE
    for component in loaded.components:
        record = BY_ID[component.id]
        assert component.molar_mass.hex() == record["molecular_weight"]["value"].hex()
        assert component.critical_temperature.hex() == _value(record, "critical_temperature").hex()
        assert component.critical_pressure.hex() == _value(record, "critical_pressure").hex()
        assert component.acentric_factor.hex() == _value(record, "acentric_factor").hex()
        assert (
            component.formation_enthalpy.hex()
            == _value(record, "standard_formation_enthalpy").hex()
        )
        for k in range(5):
            assert component.cp_coefficients[k].hex() == _value(record, f"ideal_gas_cp_b{k}").hex()


# =========================================================================== L01.A07–A11 (†)


@pytest.mark.parametrize("component", NEW)
def test_a07_critical_temperature(component: str) -> None:
    lit = float(LIT[component]["Tc"])
    assert abs(_value(BY_ID[component], "critical_temperature") - lit) <= TOL["Tc_K"]


@pytest.mark.parametrize("component", NEW)
def test_a08_critical_pressure(component: str) -> None:
    lit = float(LIT[component]["Pc"])
    assert abs(_value(BY_ID[component], "critical_pressure") - lit) / lit <= TOL["Pc_rel"]


@pytest.mark.parametrize("component", NEW)
def test_a09_acentric_factor(component: str) -> None:
    lit = float(LIT[component]["omega"])
    assert abs(_value(BY_ID[component], "acentric_factor") - lit) <= TOL["omega_abs"]


@pytest.mark.parametrize("component", NEW)
def test_a10_formation_enthalpy(component: str) -> None:
    value = _value(BY_ID[component], "standard_formation_enthalpy")
    if component == "O2":
        assert value == 0.0 and LIT[component]["dHf"] == "0"
        return
    assert value != 0.0
    tolerance = TOL["dHf_inorganic_J"] if component in INORGANIC else TOL["dHf_hydrocarbon_J"]
    assert abs(value - float(LIT[component]["dHf"])) <= tolerance


@pytest.mark.parametrize("component", NEW)
def test_a11_ideal_gas_heat_capacity_at_298_15_k(component: str) -> None:
    record = BY_ID[component]
    cp = R * sum(_value(record, f"ideal_gas_cp_b{k}") * 0.29815**k for k in range(5))
    lit = float(LIT[component]["cp298"])
    tolerance = TOL["cp_inorganic_rel"] if component in INORGANIC else TOL["cp_hydrocarbon_rel"]
    assert abs(cp - lit) / lit <= tolerance


# ================================================================================ L01.A12

CROSS: dict[str, Any] = json.loads(CROSSCHECK.read_text(encoding="utf-8"))
PINS = {
    "chemicals": "1.5.2",
    "thermo": "0.6.1",
    "CoolProp": "8.0.0",
    "cantera": "3.2.0",
    "PyYAML": "6.0.2",
}


@pytest.mark.parametrize("component", NINE)
def test_a12_the_cp_range_is_200_to_1000_k_exactly(component: str) -> None:
    record = BY_ID[component]
    assert _value(record, "ideal_gas_cp_lower_temperature") == 200.0
    assert _value(record, "ideal_gas_cp_upper_temperature") == 1000.0


def test_a12_the_crosscheck_record_is_of_these_bytes_and_these_pins() -> None:
    assert CROSS["records_sha256"] == hashlib.sha256(RECORDS.read_bytes()).hexdigest()
    assert CROSS["packages"] == PINS
    assert list(CROSS["retrieval"]) == list(NINE)


@pytest.mark.parametrize("component", NINE)
def test_a12_every_value_is_the_retrieval_sources_value(component: str) -> None:
    # Exact float equality for T_c, P_c, omega, Δ_fH°; b_k = a_(k+1)·1000^k exactly in decimal
    # (Cantera 3.2.0 nasa_gas.yaml); molar mass exactly in decimal; identifiers; quoted citations.
    equal = CROSS["retrieval"][component]["equal"]
    assert {k for k, ok in equal.items() if not ok} == set()
    assert len(equal) == 13
    assert component not in CROSS["retrieval_failures"]


@pytest.mark.parametrize("component", NINE)
def test_a12_ideal_gas_cp_within_two_percent_of_coolprop(component: str) -> None:
    # Spec §12.1 (R-528): 2 %, every record of the file; the floor is the NASA-fit vs reference-EOS
    # ideal-part disagreement on correct data (CH4 +0.68 % at 900 K), the closest swap 6.5 %.
    deviation = CROSS["crosscheck"][component]["cp_rel_dev_vs_coolprop_ideal_gas"]
    assert {t: abs(deviation[t]) <= 0.02 for t in ("300.0", "600.0", "900.0")} == {
        "300.0": True,
        "600.0": True,
        "900.0": True,
    }, deviation
    assert CROSS["a12_cp_within_bound"][component] is True


def _pins_present() -> bool:
    try:
        return all(importlib.metadata.version(name) == pin for name, pin in PINS.items())
    except importlib.metadata.PackageNotFoundError:
        return False


def test_a12_the_retrieval_script_reproduces_its_record_or_says_why_not() -> None:
    """`--check` where the source packages are (`OFS_L01_SOURCES_PYTHON`, or this interpreter);
    elsewhere the script must refuse to pass, saying which distributions are missing."""
    interpreter = os.environ.get("OFS_L01_SOURCES_PYTHON") or sys.executable
    run = subprocess.run(
        [interpreter, "-I", str(CROSSCHECK_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    if os.environ.get("OFS_L01_SOURCES_PYTHON") or _pins_present():
        assert (run.returncode, run.stdout.strip()) == (0, "components-crosscheck.json matches")
        return
    assert run.returncode == 3, run.stdout + run.stderr
    assert run.stdout.startswith("SKIPPED: components-crosscheck.json not recomputed")
    pytest.skip(f"retrieval re-run not possible here: {run.stdout.strip()}")


# =================================================================== L01.A22 (the record files)

#: SHA-256 at b843941 (the L01 base) of the C1 files §4.4 lists as unchanged.
PINNED = {
    "benchmarks/m01/components.yaml": (
        "6f154f7fbc3f4bef9fe3cb2048983cc19ad13c6b43f40d29fa944e9b719f05b9"
    ),
    "src/openflowsheet/thermo/pr_c1.py": (
        "a6123b07fa9ab6f91dd85543f8438d54b071105a9f6ac14be8eeab015403e6f4"
    ),
    "src/openflowsheet/thermo/conventions.py": (
        "4add4700fbb288d1e868309e43bdbb4d5ca993f431e401fdea67497638286a2e"
    ),
    "src/openflowsheet/models/c1/__init__.py": (
        "32f5599257a67a72d3a68670eec3cc9f14c265787a8ab08741cf5339ce2a35e0"
    ),
    "src/openflowsheet/models/c1/blocks.py": (
        "fac9fabfc574b15671e00e06104a5377577f99fbbaf911f724783ecccce70212"
    ),
    "src/openflowsheet/models/c1/boundary.py": (
        "ae803b456f0f4c4610535c59582f04b56643b468011ea34de6706f3ab01d5ed0"
    ),
    "src/openflowsheet/models/c1/feed.py": (
        "e822b7d225c0547ba74c7069562a0eb1e63f44c047c7374bac7fdc4f57e15e1a"
    ),
    "src/openflowsheet/models/c1/flash.py": (
        "f228a4a3f0fe5f181e42d341c676de4b802c0b5cb7502fa21baa9ffa5abc5c1b"
    ),
    "src/openflowsheet/models/c1/heater.py": (
        "9c1e3dc5aacdcb793e3e64eaf4fbda097a42f2291d2b689a97272e5b7d85b505"
    ),
    "src/openflowsheet/models/c1/mixer.py": (
        "adae2b60ba3904870054f6d78a7f2f7bb26d68ad4875fd08f55de34077a906ae"
    ),
    "src/openflowsheet/models/c1/phase.py": (
        "e2c862037a8f1b4dcb55be31bc208e3114f121f65995a76b22d4f85209639582"
    ),
    "src/openflowsheet/models/c1/reactor.py": (
        "39c39298dacdf6f453ec3a780d1ad1728d2e4b60e3d07e6d460533deb544780d"
    ),
    "src/openflowsheet/models/c1/reactor_standin.py": (
        "8ffbcf1d11dfc56599dc3de72ed380be9546596755a94e869a74b2a973d25f6e"
    ),
    "src/openflowsheet/models/c1/sink.py": (
        "5abe06a4aaf599e29f1f93410fffcb4620c8b5055dc349fe48d647fa93804e75"
    ),
    "src/openflowsheet/models/c1/splitter.py": (
        "1051b6577784a89d5c420ce93440c981c45814cb4a379ed424f9dcfc32d2ee5e"
    ),
    "src/openflowsheet/models/c1/units.py": (
        "86efa53f389205840dbc0d5c7e6354eeaf210134bdcef7ecdf25599250465696"
    ),
    "benchmarks/m06/openidaes450/case_facts.json": (
        "0ca8cffa146865971dd2a2d445b699cf484965cc052f7f37d8f6554c669e38f7"
    ),
    "benchmarks/m06/openidaes450/coverage.json": (
        "b69626c7e908218e70f8726534a00c964674b2cbda7f582c8650ed939e48e3ba"
    ),
    "benchmarks/m06/openidaes450/registration.json": (
        "ee099a60f9da6900325f54127f92e9eee926d2015f97b527843db482d6f0e52e"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a22_the_c1_files_are_byte_identical_to_the_l01_base() -> None:
    models = sorted((REPO_ROOT / "src" / "openflowsheet" / "models" / "c1").glob("*.py"))
    listed = {p for p in PINNED if p.startswith("src/openflowsheet/models/c1/")}
    assert {p.relative_to(REPO_ROOT).as_posix() for p in models} == listed
    assert {p: _sha256(REPO_ROOT / p) for p in PINNED} == PINNED
    assert (
        hashlib.sha256(packaged(pr_c1.RECORDS_PATH).read_bytes()).hexdigest()
        == PINNED["benchmarks/m01/components.yaml"]
    )


def test_a22_pr_c1_describes_the_same_identity() -> None:
    capabilities = pr_c1.PrC1Provider().describe()
    assert capabilities.data_sha256 == PINNED["benchmarks/m01/components.yaml"]
    assert capabilities.implementation_sha256 == PINNED["src/openflowsheet/thermo/pr_c1.py"]
    assert capabilities.components == ("H2", "N2", "NH3", "Ar", "CH4")


def test_a22_the_library_module_does_not_reach_into_pr_c1() -> None:
    # Spec §11 WO-L01-2: `pr_lib` must not import `pr_c1`'s private names (here: nothing of it).
    source = Path(pr_lib.__file__).read_text(encoding="utf-8")
    assert "pr_c1" not in source
