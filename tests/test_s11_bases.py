"""S11 WO-A1: the basis registry, `SELECTABLE_BASES` and the bind-time preconditions.

`docs/derivations/S11-design.md` §4.1–§4.3 (ADR 0050 D1, D2, D4; register R-800, R-801, R-803),
assertions S11.A01–A10. The registry selects a basis by `component_set.record_source`; every
unregistered value still selects SYN-001.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from m02_c1_corpus import C1_CORPUS
from t07_corpus import CORPUS
from test_schemas_p01 import schema_errors

from openflowsheet.application import revision_binding
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    SELECTABLE_BASES,
    basis_provider,
    provider_for,
)
from openflowsheet.application.validation import validate
from openflowsheet.canonical import document_sha256
from openflowsheet.models.revision_flowsheet import (
    COOLPROP_RECORDS,
    IAPWS95_BASIS,
    IAPWS95_RECORDS,
    SYN001_BASIS,
    SYN001_RECORDS,
    WILSON_BASIS,
    WILSON_RECORDS,
    RevisionError,
    component_basis,
    selectable_bases,
)
from openflowsheet.thermo import _coolprop_heos_fluids as table
from openflowsheet.thermo import iapws95, pr_c1, wilson_ig, wilson_premises

COOLPROP_AVAILABLE = importlib.util.find_spec("CoolProp") is not None
FLUID_IDS = tuple(str(row["id"]) for row in table.FLUIDS)


def _document(record_source: Any, components: Any = ("A", "B", "C")) -> dict[str, Any]:
    component_set: dict[str, Any] = {"components": list(components)}
    if record_source is not None:
        component_set["record_source"] = record_source
    return {"component_set": component_set}


def _records(relative: str) -> list[dict[str, Any]]:
    return list(load_yaml(REPO_ROOT / relative)["components"])


# -- S11.A01: 127 entries, in the fixed order --------------------------------------------------


def test_a01_the_selectable_bases_are_the_127_in_order() -> None:
    bases = tuple(SELECTABLE_BASES)
    assert len(SELECTABLE_BASES) == 127 == len(bases)
    assert bases == selectable_bases()
    assert bases[0] == SYN001_BASIS
    assert bases[1] == component_basis(_document(pr_c1.RECORDS_PATH, pr_c1.COMPONENTS))
    assert bases[2] == IAPWS95_BASIS and bases[3] == WILSON_BASIS
    assert [b.provider_id for b in bases[4:]] == ["coolprop-heos-v1"] * 123
    assert [b.components for b in bases[4:]] == [(c,) for c in FLUID_IDS]
    assert [b.record_source for b in bases] == [
        SYN001_RECORDS,
        pr_c1.RECORDS_PATH,
        IAPWS95_RECORDS,
        WILSON_RECORDS,
        *[COOLPROP_RECORDS] * 123,
    ]
    assert SELECTABLE_BASES[5] == bases[5] and list(SELECTABLE_BASES[2:4]) == list(bases[2:4])


def test_a01_record_source_is_keyword_required() -> None:
    with pytest.raises(TypeError):
        type(SYN001_BASIS)("syn001", ("A", "B", "C"), {}, "x")  # type: ignore[misc]


def test_a01_the_registry_paths_are_the_providers() -> None:
    assert WILSON_RECORDS == wilson_ig.RECORDS_PATH
    assert pr_c1.RECORDS_PATH != SYN001_RECORDS
    assert WILSON_BASIS.components == wilson_ig.load_records().components


# -- S11.A02: each entry's provider describes it ------------------------------------------------


@pytest.mark.parametrize("index", range(127))
def test_a02_each_basis_provider_describes_its_basis(index: int) -> None:
    basis = selectable_bases()[index]
    described = basis_provider(basis).describe()
    assert (described.provider_id, tuple(described.components)) == (
        basis.provider_id,
        basis.components,
    )


def test_a02_basis_provider_refuses_an_unknown_basis() -> None:
    other = dataclasses.replace(SYN001_BASIS, provider_id="pr-lib-v1")
    with pytest.raises(ValueError, match="no provider for basis 'pr-lib-v1'"):
        basis_provider(other)


# -- S11.A03: selection --------------------------------------------------------------------------


def test_a03_each_registered_record_source_selects_its_basis() -> None:
    assert component_basis(_document(IAPWS95_RECORDS, ["H2O"])) is IAPWS95_BASIS
    assert component_basis(_document(WILSON_RECORDS, WILSON_BASIS.components)) is WILSON_BASIS
    assert component_basis(_document(pr_c1.RECORDS_PATH)).provider_id == "pr-c1-v1"
    assert component_basis(_document(SYN001_RECORDS)) is SYN001_BASIS


@pytest.mark.parametrize("component", FLUID_IDS)
def test_a03_each_coolprop_fluid_selects_its_basis(component: str) -> None:
    basis = component_basis(_document(COOLPROP_RECORDS, [component]))
    assert basis.provider_id == "coolprop-heos-v1" and basis.components == (component,)
    assert basis == selectable_bases()[4 + FLUID_IDS.index(component)]


@pytest.mark.parametrize("record_source", [None, "benchmarks/s10/verification-records.yaml", ""])
def test_a03_an_unregistered_record_source_selects_syn001(record_source: Any) -> None:
    assert component_basis(_document(record_source)) is SYN001_BASIS
    assert component_basis({}) is SYN001_BASIS


# -- S11.A04: CoolProp's one-fluid rule ---------------------------------------------------------


@pytest.mark.parametrize(
    ("components", "hint"),
    [
        (
            ["CO2", "N2"],
            "coolprop-heos-v1 serves exactly one admitted fluid per revision; got [CO2, N2]",
        ),
        (
            ["Unobtainium"],
            "coolprop-heos-v1 serves exactly one admitted fluid per revision; got [Unobtainium]",
        ),
        ([], "coolprop-heos-v1 serves exactly one admitted fluid per revision; got []"),
    ],
)
def test_a04_coolprop_refuses_other_than_one_admitted_fluid(
    components: list[str], hint: str
) -> None:
    with pytest.raises(RevisionError) as raised:
        component_basis(_document(COOLPROP_RECORDS, components))
    assert (raised.value.kind, raised.value.code, raised.value.hint) == (
        "unsupported",
        "components_unsupported",
        hint,
    )


@pytest.mark.parametrize("name", sorted(table.EXCLUDED))
def test_a04_each_excluded_fluid_is_refused_with_its_reason(name: str) -> None:
    assert len(table.EXCLUDED) == 13
    with pytest.raises(RevisionError) as raised:
        component_basis(_document(COOLPROP_RECORDS, [name]))
    assert raised.value.code == "components_unsupported"
    reason = table.EXCLUDED[name]
    assert raised.value.hint == f"{name!r} is excluded from coolprop-heos-v1: {name}: {reason}"


# -- S11.A05: molar masses -------------------------------------------------------------------------


def test_a05_the_molar_masses_are_the_sources() -> None:
    assert dict(IAPWS95_BASIS.molecular_weights) == {"H2O": iapws95.M} == {"H2O": 0.018015268}
    wilson = {r["id"]: r["molecular_weight"]["value"] for r in _records(WILSON_RECORDS)}
    assert dict(WILSON_BASIS.molecular_weights) == wilson
    assert tuple(wilson) == WILSON_BASIS.components
    for basis, row in zip(selectable_bases()[4:], table.FLUIDS, strict=True):
        assert dict(basis.molecular_weights) == {row["id"]: row["M"]}


# -- S11.A06: the two record files -----------------------------------------------------------------


def test_a06_the_coolprop_records_are_the_generators() -> None:
    script = REPO_ROOT / "docs" / "derivations" / "scripts" / "s11_coolprop_records.py"
    done = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.startswith("OK:")


@pytest.mark.parametrize("relative", [IAPWS95_RECORDS, COOLPROP_RECORDS])
def test_a06_the_record_files_validate(relative: str) -> None:
    document = load_yaml(REPO_ROOT / relative)
    assert document["record_schema"] == "schemas/component-record.schema.json"
    for record in document["components"]:
        assert schema_errors("component_record", record) == [], record["id"]


def test_a06_the_records_carry_the_registry_values() -> None:
    (water,) = _records(IAPWS95_RECORDS)
    assert water["identifiers"] == {"cas": "7732-18-5", "formula": "H2O"}
    assert load_yaml(REPO_ROOT / IAPWS95_RECORDS)["reference_convention"] == "IAPWS95-ref-v1"
    rows = _records(COOLPROP_RECORDS)
    assert [r["id"] for r in rows] == list(FLUID_IDS)
    for record, row in zip(rows, table.FLUIDS, strict=True):
        assert record["molecular_weight"]["value"] == row["M"]
        assert record["identifiers"]["cas"] == row["cas"] and record["name"] == row["name"]
    assert load_yaml(REPO_ROOT / COOLPROP_RECORDS)["reference_convention"] == (
        "COOLPROP-DEF-ref-v1"
    )


# -- S11.A07 / A08: P1–P3 in closed form -----------------------------------------------------------

_POSITIVITY = load_yaml(REPO_ROOT / "benchmarks" / "s10c" / "reference_values.yaml")["positivity"]
_KEYS = {"P1": "dlnpsat_dT", "P2": "cp_liquid", "P3": "cp_ig"}


def _three(value: float) -> float:
    return float(f"{value:.3g}")


@pytest.mark.parametrize(
    ("which", "path"),
    [("real", None), ("verification", "benchmarks/s10/verification-records.yaml")],
)
def test_a07_the_premises_hold_with_the_registered_minima(which: str, path: str | None) -> None:
    records = wilson_ig.load_records(None if path is None else REPO_ROOT / path)
    assert wilson_premises.violations(records) == ()
    found = wilson_premises.minima(records)
    assert len(found) == 3 * len(records.components)
    lo, hi = records.temperature_domain
    for minimum in found:
        expected = _POSITIVITY[which][minimum.component][_KEYS[minimum.premise]]
        assert _three(minimum.value) == expected, minimum
        assert minimum.holds
        assert lo <= minimum.temperature <= hi
        if minimum.where == "endpoint":
            assert minimum.temperature in (lo, hi), minimum


def test_a07_an_interior_minimum_is_a_root_of_the_cubic() -> None:
    # A constructed record whose c_p^ig has an interior minimum at θ = 0.35 (P3's cubic root).
    records = wilson_ig.load_records()
    cp = list(records.cp)
    cp[0] = (2.0, -0.7, 1.0, 0.0, 0.0)  # b0 − 0.7θ + θ²: minimum at θ = 0.35
    shaped = dataclasses.replace(records, cp=tuple(cp))
    p3 = next(m for m in wilson_premises.minima(shaped) if m.premise == "P3")
    assert p3.where == "root"
    assert p3.temperature == pytest.approx(350.0, rel=1e-12)
    assert p3.value == pytest.approx(wilson_premises.R * (2.0 - 0.1225), rel=1e-12)


def test_a08_a_widened_domain_breaks_p2_for_water() -> None:
    records = dataclasses.replace(wilson_ig.load_records(), temperature_domain=(300.0, 800.0))
    first = wilson_premises.violations(records)[0]
    assert (first.premise, first.component) == ("P2", "H2O")
    assert 750.0 <= first.temperature <= 800.0


def test_a08_the_binder_refuses_unmet_premises(monkeypatch: pytest.MonkeyPatch) -> None:
    widened = dataclasses.replace(wilson_ig.load_records(), temperature_domain=(300.0, 800.0))
    monkeypatch.setattr(wilson_ig, "load_records", lambda path=None: widened)
    refused = provider_for(WILSON_BASIS)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "basis_premises_unmet(wilson-ig-v2)")
    assert refused.hint is not None and refused.hint.startswith("P2: H2O min ")
    temperature = float(refused.hint.split("at T = ")[1].removesuffix(" K"))
    assert 750.0 <= temperature <= 800.0


# -- S11.A09: availability -------------------------------------------------------------------------


def test_a09_coolprop_without_its_extra_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    real = importlib.util.find_spec
    monkeypatch.setattr(
        revision_binding.importlib.util,
        "find_spec",
        lambda name, *a: None if name == "CoolProp" else real(name, *a),
    )
    refused = provider_for(component_basis(_document(COOLPROP_RECORDS, ["CO2"])))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "basis_unavailable(coolprop-heos-v1)")
    assert refused.hint == (
        "the coolprop extra is not installed (pip install openflowsheet[coolprop])"
    )


def test_a09_wilson_without_its_records_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    load = wilson_ig.load_records
    monkeypatch.setattr(wilson_ig, "_checkout_records", lambda: tmp_path / "absent.yaml")
    with pytest.raises(wilson_ig.RecordError):
        load()
    refused = provider_for(WILSON_BASIS)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "basis_unavailable(wilson-ig-v2)")
    assert refused.hint is not None
    assert refused.hint.startswith("records_missing: ") and "R-706" in refused.hint
    assert "Q-F3" in refused.hint


def test_a09_the_other_bases_have_their_providers() -> None:
    for basis in (SYN001_BASIS, IAPWS95_BASIS, WILSON_BASIS, selectable_bases()[1]):
        provider = provider_for(basis)
        assert not isinstance(provider, Unbound)
        assert provider.describe().provider_id == basis.provider_id
    co2 = provider_for(component_basis(_document(COOLPROP_RECORDS, ["CO2"])))
    assert isinstance(co2, Unbound) != COOLPROP_AVAILABLE


# -- S11.A10: validation ---------------------------------------------------------------------------

#: SHA-256 over the T07 and C1 corpora's validation reports (56 revisions, `now` fixed), each as
#: its name then `document_sha256(report.as_document())`, measured at the base `8c34ecb0`.
BASE_VALIDATION_DIGEST = "e6c92d9059db0e814c26020782ebbd8818abc5931ccfa4dd44135f969c2f37ab"


def test_a10_a_coolprop_revision_with_two_components_fails_comp02() -> None:
    document = next(iter(CORPUS.values()))()
    document["component_set"] = {"record_source": COOLPROP_RECORDS, "components": ["CO2", "N2"]}
    checks = {c.id: c for c in validate(document, now=lambda: "2026-10-26T00:00:00Z").checks}
    assert checks["COMP-02"].result == "FAIL"
    assert checks["COMP-02"].message == (
        f"{COOLPROP_RECORDS}: components_unsupported (coolprop-heos-v1 serves exactly one "
        "admitted fluid per revision; got [CO2, N2])"
    )


def test_a10_the_corpus_validation_reports_are_the_bases() -> None:
    documents = {**{n: b() for n, b in CORPUS.items()}, **{n: b() for n, b in C1_CORPUS.items()}}
    assert len(documents) == 56
    digest = hashlib.sha256()
    for name in sorted(documents):
        report = validate(documents[name], now=lambda: "2026-10-26T00:00:00Z").as_document()
        digest.update(name.encode())
        digest.update(document_sha256(report).encode())
    assert digest.hexdigest() == BASE_VALIDATION_DIGEST


# -- S11.A83: the envelope after I1b (units design §4.10) -----------------------------------------


def test_a83_the_envelope_holds_the_thermal_models_and_their_limitations() -> None:
    envelope = load_yaml(REPO_ROOT / "benchmarks" / "t08" / "support_envelope.yaml")
    axes = {axis["id"]: axis for axis in envelope["axes"]}
    members = axes["unit_models"]["members"]
    assert len(members) == 30
    assert sorted(members) == sorted(revision_binding.MODEL_BUILDERS)
    assert axes["property_model"]["providers"] == [
        "coolprop-heos-v1",
        "iapws95-v1",
        "pr-c1-v1",
        "syn001",
        "wilson-ig-v2",
    ]
    ids = {row["id"] for row in envelope["limitations"]}
    assert {f"L-TH-{n}" for n in range(1, 9)} | {f"L-GP-{n}" for n in range(1, 4)} <= ids
    texts = {row["id"]: " ".join(row["text"].split()) for row in envelope["limitations"]}
    # L-S11-1/2 drop "routing models only" (§4.10); rulings item 10's appended sentences.
    assert all("Only the routing models" not in texts[f"L-S11-{n}"] for n in (1, 2, 3))
    # `{U}`, not `<U>`: a T08 manifest holds no angle-bracketed span (its description rule).
    assert texts["L-TH-4"].endswith("is refused `isentropic_state_two_phase({U})`.")
    assert "(measured: 4 of 11 200 grid outcomes, at 22.85 MPa)" in texts["L-TH-5"]
    assert texts["L-TH-8"].startswith("A revision declares one phase per port (R4)")
