"""E01 WO-A3: cost forms, the SSLW set, quotes and the cost basis (design note §4.5–§4.6, §9.2).

Assertions A16–A19, A44 (forms) and A45. Expectations are hand calculations written from the
pinned IDAES-PSE 2.13.0 source (`idaes/models/costing/SSLW.py`, sha256 `362b0a22…1184`), with the
coefficients typed here from that file and the line cited, never read back from the set file or
from the code under test. A14/A15 (WO-B4's independent transcription and the IDAES evaluation) run
in I1.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from importlib.resources import files
from typing import Any

import casadi as ca
import pytest

from openflowsheet.assessment.cost.forms import (
    ATM_PA,
    FORMS,
    KAPPA_A,
    KAPPA_Q,
    KAPPA_W,
    PSI_PA,
    OutOfRange,
    Selection,
    log_polynomial,
    motor_efficiency,
    power_law,
    rows,
    select,
)
from openflowsheet.assessment.cost.index import (
    IndexSeries,
    SourceBasis,
    TargetBasis,
    escalate,
    load_rates,
    load_series,
)
from openflowsheet.assessment.cost.quotes import Quote, size_mismatch
from openflowsheet.assessment.cost.sets import (
    CostSetError,
    NoCorrelation,
    entry_for,
    load_set,
    parse_set,
    resolve,
)
from openflowsheet.assessment.program import Limitation, Refusal
from openflowsheet.compile.reference import FloatAlgebra

F = FloatAlgebra()


class CasadiAlgebra:
    def exp(self, v: Any) -> Any:
        return ca.exp(v)

    def log(self, v: Any) -> Any:
        return ca.log(v)

    def sqrt(self, v: Any) -> Any:
        return ca.sqrt(v)


def shipped_document() -> dict[str, Any]:
    path = files("openflowsheet").joinpath("_data", "assessment", "cost", "sslw-idaes-v1.json")
    return json.loads(path.read_text(encoding="utf-8"))


SSLW = load_set("sslw-idaes-v1")


def entry(entry_id: str, **options: str) -> Any:
    resolved = resolve(SSLW, entry_id, options)
    assert not isinstance(resolved, NoCorrelation), resolved
    return resolved


def psig_to_pa(p: float) -> float:
    return ATM_PA + p * PSI_PA


# -- unit factors (§9.2.4) -----------------------------------------------------------------------


def test_the_unit_factors_are_the_notes_binary64_constants() -> None:
    assert KAPPA_A == 10.763910416709722
    assert KAPPA_Q == 15850.323141488905
    assert KAPPA_W == 0.0013410220895950279
    assert PSI_PA == 6894.757293168361 and ATM_PA == 101325.0


# -- the set file and its loader (A45) -----------------------------------------------------------


def test_the_shipped_set_loads_with_the_notes_entries_in_order(capsys: Any) -> None:
    assert [e.entry_id for e in SSLW.entries] == [
        "exchanger.shell_tube",
        "vessel.vertical",
        "vessel.horizontal",
        "column.trays",
        "pump",
        "motor.electric",
        "compressor",
        "turbine",
    ]
    doc = shipped_document()
    source = doc["source"]["transcribed_from"]
    assert source["version"] == "2.13.0"
    assert source["wheel_sha256"].startswith("2b67301a") and source["wheel_sha256"].endswith("85f9")
    assert source["file_sha256"].startswith("362b0a22") and source["file_sha256"].endswith("1184")
    notice = doc["source"]["notice"].splitlines()
    assert len(notice) == 12 and "All rights reserved." in notice[9]
    text = doc["source"]["licence_text"]
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == doc["source"]["licence_text_sha256"]
    assert doc["source"]["licence_text_sha256"].startswith("4fdde00b")
    kinds = []
    for item in doc["entries"]:
        found = list(dict(item.get("ranges", {})).items())
        for option in item.get("options", {}).values():
            for body in option.get("choices", {}).values():
                found += list(dict(body.get("ranges", {})).items())  # one row per choice
        for name, r in found:
            kinds.append((item["entry_id"], name, r["source"]["kind"], r["source"].get("verified")))
    print("\n".join(f"{e} {n}: {k} verified={v}" for e, n, k, v in kinds))
    # §10.4.3: the five ranges QA1 found matching are verified (QA1.patch); the five ruling B adds
    # wait for a person's approval (A48, C7).
    primary = sorted((e, n, v) for e, n, k, v in kinds if k == "primary")
    assert primary == sorted(
        [
            ("exchanger.shell_tube", "area_ft2", True),
            ("vessel.vertical", "weight_lb", False),
            ("pump", "size_factor", True),
            ("pump", "flow_gpm", True),
            ("pump", "power_hp", True),
            ("motor.electric", "motor_power_hp", True),
            ("compressor", "consumed_power_hp", False),
            ("compressor", "consumed_power_hp", False),
            ("compressor", "consumed_power_hp", False),
            ("turbine", "power_hp", False),
        ]
    ), primary
    assert {k for _, _, k, _ in kinds} == {"pinned", "primary"}
    assert "primary" in capsys.readouterr().out


def _refused(doc: dict[str, Any], fragment: str) -> None:
    with pytest.raises(CostSetError) as raised:
        parse_set(doc)
    assert any(fragment in reason for reason in raised.value.reasons), raised.value.reasons


def test_a45_the_loader_refuses_a_missing_source_line() -> None:
    doc = shipped_document()
    del doc["entries"][0]["options"]["hx_type"]["choices"]["Utube"]["alpha2"]["source_line"]
    _refused(doc, "hx_type.choices.Utube.alpha2: missing source_line")
    doc = shipped_document()
    del doc["entries"][3]["coefficients"]["count_b"]["source_line"]
    _refused(doc, "count_b: missing source_line")
    doc = shipped_document()
    del doc["entries"][4]["options"]["pump_type"]["default_source_line"]
    _refused(doc, "default without default_source_line")


def test_a45_the_loader_refuses_a_primary_source_without_verified() -> None:
    doc = shipped_document()
    del doc["entries"][0]["ranges"]["area_ft2"]["source"]["verified"]
    _refused(doc, "primary source without verified")
    doc = shipped_document()
    del doc["entries"][0]["ranges"]["pressure_psig"]["source"]
    _refused(doc, "range without source")


def test_a45_the_loader_refuses_a_floor_on_a_decreasing_form() -> None:
    doc = shipped_document()
    doc["entries"][0]["coefficients"]["pressure_a"][1]["value"] = -0.5
    _refused(doc, "the floor undercuts")


def test_a45_the_loader_refuses_an_unknown_option_choice() -> None:
    doc = shipped_document()
    doc["entries"][0]["options"]["tube_length"]["default"] = "TenFoot"
    _refused(doc, "default 'TenFoot' is not one of its choices")


def test_a45_the_loader_refuses_non_contiguous_pieces() -> None:
    doc = shipped_document()
    doc["entries"][1]["ranges"]["platform_length_ft"]["pieces"][1]["min"] = 41.0
    _refused(doc, "pieces are not contiguous")


def test_the_loader_refuses_an_unknown_form_and_a_narrow_size_range() -> None:
    doc = shipped_document()
    doc["entries"][7]["form"] = "sslw-fan-v1"
    _refused(doc, "unknown form 'sslw-fan-v1'")
    doc = shipped_document()
    doc["entries"][0]["ranges"]["area_ft2"]["max"] = 299.0
    _refused(doc, "max 299.0 < 2·min 150.0")


def test_options_outside_their_choices_are_no_correlation() -> None:
    assert isinstance(resolve(SSLW, "exchanger.shell_tube", {"hx_type": "Spiral"}), NoCorrelation)
    # SSLW.py:1420-1441: reciprocating pumps take only these four materials, the others not two.
    refused = resolve(SSLW, "pump", {"pump_type": "Reciprocating", "material": "CastIron"})
    assert isinstance(refused, NoCorrelation) and "CastIron" in refused.detail
    assert isinstance(resolve(SSLW, "pump", {"material": "CarbonSteel"}), NoCorrelation)
    assert isinstance(
        resolve(SSLW, "pump", {"pump_type": "ExternalGear", "pump_type_factor": "2.1"}),
        NoCorrelation,
    )
    assert isinstance(resolve(SSLW, "compressor", {"drive_type": "SteamTurbine"}), NoCorrelation)
    assert isinstance(resolve(SSLW, "turbine", {"material": "x"}), NoCorrelation)


def test_defaults_are_idaes_argument_defaults_and_are_reported() -> None:
    hx = entry("exchanger.shell_tube", material="CarbonSteelCarbonSteel")
    assert hx.options == {
        "hx_type": "Utube",
        "material": "CarbonSteelCarbonSteel",
        "tube_length": "TwelveFoot",
    }
    assert hx.defaulted == ("hx_type", "tube_length")
    pump = entry("pump")
    assert pump.options["pump_type_factor"] == "1.4" and pump.n("F_T") == 2.00  # SSLW.py:1558
    gear = entry("pump", pump_type="ExternalGear")
    assert "pump_type_factor" not in gear.options and gear.n("type_factor_other") == 1.0
    vessel = entry("vessel.vertical")
    assert vessel.continuous["shell_thickness_in"] == 1.25  # SSLW.py:513


def test_the_family_lookup_puts_vertical_first() -> None:
    assert entry_for(SSLW, "drum").entry_id == "vessel.vertical"
    assert entry_for(SSLW, "drum", "horizontal").entry_id == "vessel.horizontal"
    assert entry_for(SSLW, "column.shell").entry_id == "vessel.vertical"
    assert entry_for(SSLW, "machine.drive").entry_id == "motor.electric"
    assert entry_for(SSLW, "exchanger.process").entry_id == "exchanger.shell_tube"
    assert entry_for(SSLW, "unknown.family") is None


# -- I. exchanger (A17, A18, A44) ----------------------------------------------------------------


def hand_exchanger_cp1(area_ft2: float, p_psig: float) -> float:
    """U-tube, stainless/stainless, 12 ft (IDAES defaults, SSLW.py:329-331), per unit."""
    z = 1.1 * area_ft2  # SSLW.py:393
    c_b = math.exp(11.3852 - 0.9186 * math.log(z) + 0.09790 * math.log(z) ** 2)  # :403, :415-425
    f_m = 2.70 + (area_ft2 / 100) ** 0.07  # :446, :460
    u = p_psig / 100
    f_p = 0.9803 + 0.0180 * u + 0.0017 * u**2  # :494-496
    return f_p * f_m * 1.12 * c_b  # :384, :501-507


def test_a17_above_s_max_splits_into_parallel_units_bitwise() -> None:
    hx = entry("exchanger.shell_tube")
    form = FORMS[hx.form]
    area = 2.5 * 12000.0 / KAPPA_A
    x = {"area": area, "design_pressure": psig_to_pa(500.0)}
    sel = select(form, hx, x)
    assert isinstance(sel, Selection) and sel.size == "units:3" and sel.n == 3
    p = (x["design_pressure"] - ATM_PA) / PSI_PA
    assert form.cost(hx, x, sel, F) == 3 * hand_exchanger_cp1((area / 3) * KAPPA_A, p)
    assert [(r.row_id, r.sense, r.bound) for r in rows(form, hx, sel)][:2] == [
        ("area_ft2.lo", 1, 3 * 150.0),
        ("area_ft2.hi", -1, 3 * 12000.0),
    ]


def test_a18_below_s_min_is_the_floor_with_an_empty_derivative_row() -> None:
    hx = entry("exchanger.shell_tube")
    form = FORMS[hx.form]
    x = {"area": 0.5 * 150.0 / KAPPA_A, "design_pressure": psig_to_pa(50.0)}
    sel = select(form, hx, x)
    assert isinstance(sel, Selection) and sel.size == "floor" and sel.pieces["pressure_psig"] == 0
    assert form.cost(hx, x, sel, F) == hand_exchanger_cp1(150.0, 100.0)
    s, pr = ca.SX.sym("S"), ca.SX.sym("P")
    cost = form.cost(hx, {"area": s, "design_pressure": pr}, sel, CasadiAlgebra())
    assert ca.jacobian(ca.SX(cost), ca.vertcat(s, pr)).nnz() == 0


def test_a44_exchanger_pressure_floor_refusal_and_carbon_steel() -> None:
    hx = entry("exchanger.shell_tube")
    form = FORMS[hx.form]
    # F_P at p ≤ 100 psig is 1.0 bitwise with a structurally empty ∂/∂P row.
    for p in (100.0, 50.0, -14.0):
        sel = select(form, hx, {"area": 50.0, "design_pressure": psig_to_pa(p)})
        assert isinstance(sel, Selection)
        assert form.pressure_factor(hx, 100.0) == 1.0
        assert sel.pieces["pressure_psig"] == (1 if p == 100.0 else 0)
    floor = Selection("units:1", 1, {"pressure_psig": 0})
    s, pr = ca.SX.sym("S"), ca.SX.sym("P")
    cost = form.cost(hx, {"area": s, "design_pressure": pr}, floor, CasadiAlgebra())
    assert ca.jacobian(ca.SX(cost), pr).nnz() == 0 and ca.jacobian(ca.SX(cost), s).nnz() == 1
    over = select(form, hx, {"area": 50.0, "design_pressure": psig_to_pa(2000.0 * (1 + 1e-9))})
    assert isinstance(over, OutOfRange) and over.target == "pressure"
    extrapolated = select(
        form,
        hx,
        {"area": 50.0, "design_pressure": psig_to_pa(2500.0)},
        allow_extrapolation=True,
    )
    assert isinstance(extrapolated, Selection) and "pressure_psig" in extrapolated.extrapolated
    cs = entry("exchanger.shell_tube", material="CarbonSteelCarbonSteel")
    x = {"area": 50.0, "design_pressure": psig_to_pa(300.0)}
    sel = select(form, cs, x)
    assert isinstance(sel, Selection)
    a = 50.0 * KAPPA_A
    z = 1.1 * a
    c_b = math.exp(11.3852 - 0.9186 * math.log(z) + 0.09790 * math.log(z) ** 2)
    u = ((x["design_pressure"] - ATM_PA) / PSI_PA) / 100
    f_p = 0.9803 + 0.0180 * u + 0.0017 * u**2
    assert form.cost(cs, x, sel, F) == f_p * 1.0 * 1.12 * c_b  # F_M == 1.0 (SSLW.py:455-456)


# -- II. vessel (A44) ----------------------------------------------------------------------------


def test_a44_the_vessel_hand_case() -> None:
    v = entry("vessel.vertical")
    form = FORMS[v.form]
    x = {"diameter": 1.0, "length": 3.0, "thickness": 0.03175}
    weight = form.weight(v, x)
    assert weight == pytest.approx(6777.48970680199, rel=1e-13)
    sel = select(form, v, x)
    assert isinstance(sel, Selection)
    assert sel.size == "units:1" and sel.pieces == {
        "platform_length_ft": 0,
        "platform_diameter_ft": 1,
    }
    lw = math.log(weight)
    c_v = math.exp(7.0132 + 0.18255 * lw + 0.02297 * lw**2)  # SSLW.py:676, :687-695
    assert c_v == pytest.approx(33222.512431689356, rel=1e-12)
    c_pl = 361.8 * (1.0 / 0.3048) ** 0.73960 * 12.0**0.70684  # :758-760, L floored at 12 ft
    assert c_pl == pytest.approx(5045.446066094272, rel=1e-12)
    assert form.cost(v, x, sel, F) == pytest.approx(38267.95849778363, rel=1e-12)
    assert form.cost(v, x, sel, F) == 1.0 * c_v + c_pl


def test_vessel_platform_pieces_floors_and_orientation() -> None:
    v = entry("vessel.vertical")
    form = FORMS[v.form]
    tall = {"diameter": 2.0, "length": 60 * 0.3048, "thickness": 0.03175}
    sel = select(form, v, tall)
    assert isinstance(sel, Selection) and sel.pieces["platform_length_ft"] == 2
    d_ft, l_ft = 2.0 / 0.3048, 60 * 0.3048 / 0.3048
    w = form.weight(v, tall)
    lw = math.log(w)
    c_v = math.exp(7.0132 + 0.18255 * lw + 0.02297 * lw**2)
    assert form.cost(v, tall, sel, F) == pytest.approx(
        c_v + 300.9 * d_ft**0.63316 * l_ft**0.80161, rel=1e-14
    )  # :765-767, with 300.9 for IDAES's 309.9 (S3 p. 575 Eq. 22.58; §10.10.5.1, R-897)
    assert ("platform_diameter_ft.hi", -1, 24.0) in [
        (r.row_id, r.sense, r.bound) for r in rows(form, v, sel)
    ]
    wide = {"diameter": 23 * 0.3048, "length": 20 * 0.3048, "thickness": 0.03175}
    out = select(form, v, wide)  # piece 1 admits D ≤ 21 ft only
    assert isinstance(out, OutOfRange) and out.target == "platforms.D"
    bare = entry("vessel.vertical", platforms_ladders="false")
    sel = select(form, bare, wide)
    assert isinstance(sel, Selection) and sel.pieces == {}
    h = entry("vessel.horizontal")
    x = {"diameter": 1.5, "length": 6.0, "thickness": 0.03175}
    sel = select(form, h, x)
    assert isinstance(sel, Selection)
    w = form.weight(h, x)
    lw = math.log(w)
    expected = math.exp(8.9552 + -0.2330 * lw + 0.04333 * lw**2) + 2005 * (1.5 / 0.3048) ** 0.20294
    assert form.cost(h, x, sel, F) == pytest.approx(expected, rel=1e-14)  # :674, :749
    small = select(form, h, {"diameter": 0.2, "length": 0.5, "thickness": 0.003})
    assert isinstance(small, Selection) and small.size == "floor"
    huge = {"diameter": 6.0, "length": 40.0, "thickness": 0.1}  # ≈ 1.5e6 lb
    assert isinstance(select(form, h, huge), OutOfRange)
    assert select(form, h, huge, allow_extrapolation=True).extrapolated  # type: ignore[union-attr]


# -- III. trays (A44) ----------------------------------------------------------------------------


def test_a44_the_tray_count_factor() -> None:
    t = entry("column.trays")
    form = FORMS[t.form]
    assert form.count_factor(t, 10) == pytest.approx(1.4997082643358985, rel=1e-15)
    assert form.count_factor(t, 19) == pytest.approx(1.0409949546984238, rel=1e-15)
    assert form.count_factor(t, 20) == form.count_factor(t, 21) == 1.0
    x = {"diameter": 1.2, "n_act": 25}
    sel = select(form, t, x)
    assert isinstance(sel, Selection)
    d = 1.2 / 0.3048
    expected = 25.0 * 1.0 * 1 * (1 + 0 * d) * (468.00 * math.exp(0.1739 * d))  # :817, :856-868
    assert form.cost(t, x, sel, F) == pytest.approx(expected, rel=1e-15)
    valve = entry("column.trays", tray_type="Valve", tray_material="Monel")
    expected = 25.0 * 1.0 * 1.18 * (2.306 + 0.1120 * d) * (468.00 * math.exp(0.1739 * d))
    assert form.cost(valve, x, sel, F) == pytest.approx(expected, rel=1e-15)
    floor = select(form, t, {"diameter": 0.3, "n_act": 25})
    assert isinstance(floor, Selection) and floor.size == "floor"
    assert form.cost(t, {"diameter": 0.3, "n_act": 25}, floor, F) == pytest.approx(
        25.0 * 1.0 * 1 * 1 * 468.00 * math.exp(0.1739 * 2.0), rel=1e-15
    )


# -- IV–VII. machines; the pump and motor basis at CE 500 (A44, R-896) ----------------------------


def test_a44_the_ce394_ratio_and_the_pump_forms() -> None:
    # §10.10.4 (R-896): the 3rd ed. states every pump and motor correlation at CE 500 (pp. 561-563),
    # so the entry's basis is amended from IDAES's CE 394 label to 500 and no factor applies.
    pump = entry("pump")
    assert pump.ratio == 1.0 and pump.amended["index_basis.value"]["effective_value"] == 500.0
    form = FORMS[pump.form]
    x = {"vol_flow": 0.01, "head": 50.0, "power": 8.0e3}
    sel = select(form, pump, x)
    assert isinstance(sel, Selection) and sel.size == "units:1"
    s = (0.01 * KAPPA_Q) * (50.0 / 0.3048) ** 0.5  # SSLW.py:1502-1524
    c_b = math.exp(9.7171 - 0.6019 * math.log(s) + 0.0519 * math.log(s) ** 2)  # :1585-1590
    assert form.cost(pump, x, sel, F) == pytest.approx(2.00 * 2.00 * c_b, rel=1e-15)
    gear = entry("pump", pump_type="ExternalGear", material="CastIron")
    sel = select(form, gear, x)
    assert isinstance(sel, Selection)
    q = 0.01 * KAPPA_Q
    c_b = math.exp(7.6964 + 0.1986 * math.log(q) + 0.0291 * math.log(q) ** 2)  # :1591-1596
    assert form.cost(gear, x, sel, F) == pytest.approx(1 * 1.00 * c_b, rel=1e-15)
    recip = entry("pump", pump_type="Reciprocating", material="NiAlBronze")
    sel = select(form, recip, x)
    assert isinstance(sel, Selection)
    w = 8.0e3 / 745.6998715822702
    c_b = math.exp(7.8103 + 0.26986 * math.log(w) + 0.06718 * math.log(w) ** 2)  # :1597-1602
    assert form.cost(recip, x, sel, F) == pytest.approx(1.15 * c_b, rel=1e-15)


def test_a44_motor_efficiency_and_the_motor_form() -> None:
    motor = entry("motor.electric")
    assert motor_efficiency(motor, 1.0, F) == 0.8
    assert motor_efficiency(motor, 10.0, F) == pytest.approx(0.8638030099054395, rel=1e-15)
    form = FORMS[motor.form]
    x = {"power": 20.0e3}
    sel = select(form, motor, x, units=2)
    assert isinstance(sel, Selection) and sel.size == "units:2" and sel.n == 2
    w = (20.0e3 / 2) / 745.6998715822702
    eta = 0.80 + 0.0319 * math.log(w) - 0.00182 * math.log(w) ** 2  # SSLW.py:1637-1641
    lam = math.log(w / eta)
    c_b = math.exp(
        5.8259 + 0.13141 * lam + 0.053255 * lam**2 + 0.028628 * lam**3 - 0.0035549 * lam**4
    )  # :1652-1661
    assert form.cost(motor, x, sel, F) == pytest.approx(2 * 1 * c_b, rel=1e-14)  # CE 500 (R-896)
    for power in (1.0e17, 1.0e-4):  # η_m ≤ 0 outside ln W ∈ (−13.96, 31.5)
        guard = select(form, motor, {"power": power})
        assert isinstance(guard, OutOfRange) and guard.target == "eta"
    tiny = select(form, motor, {"power": 100.0})
    assert isinstance(tiny, Selection) and tiny.size == "floor"
    assert form.cost(motor, {"power": 100.0}, tiny, F) == pytest.approx(math.exp(5.8259), rel=1e-15)


def _eta_m(w_hp: float) -> float:
    """Eq. 22.18 (S3 p. 562; SSLW.py:1636-1641), restated."""
    lw = math.log(w_hp)
    return 0.80 + 0.0319 * lw - 0.00182 * lw * lw


def _brake_for(p_c: float) -> float:
    """The per-unit brake power (hp) whose consumed power w/η_m(w) is `p_c`, by Newton on floats."""
    w = 0.9 * p_c
    for _ in range(60):
        lw = math.log(w)
        eta = 0.80 + 0.0319 * lw - 0.00182 * lw * lw
        slope = (eta - (0.0319 - 2 * 0.00182 * lw)) / eta**2
        step = (w / eta - p_c) / slope
        w -= step
        if abs(step) <= 1e-17 * w:
            break
    return w


def test_compressor_and_turbine_forms() -> None:
    comp = entry("compressor")
    assert comp.includes_drive
    assert comp.drive is not None and comp.drive.entry_id == "motor.electric"
    form = FORMS[comp.form]
    x = {"power": 2.0e6}
    sel = select(form, comp, x)
    assert isinstance(sel, Selection) and sel.size == "units:1"
    w = 2.0e6 / 745.6998715822702
    assert form.cost(comp, x, sel, F) == pytest.approx(
        1 * 2.5 * math.exp(7.58 + 0.8 * math.log(w / _eta_m(w))), rel=1e-15
    )  # SSLW.py:1136, :1146, :1156, :1164-1178; consumed power (§10.4.4)
    screw = entry("compressor", compressor_type="Screw", material="CarbonSteel")
    big = {"power": 1.2e6}  # 1609 hp brake: three screw units of 578 hp consumed
    sel = select(form, screw, big)
    assert isinstance(sel, Selection) and sel.size == "units:3"
    w = (1.2e6 / 3) / 745.6998715822702
    assert form.cost(screw, big, sel, F) == pytest.approx(
        3 * math.exp(8.1238 + 0.7243 * math.log(w / _eta_m(w))), rel=1e-15
    )
    turbine = entry("turbine")
    form = FORMS[turbine.form]
    sel = select(form, turbine, {"power": 5.0e5})
    assert isinstance(sel, Selection) and sel.size == "units:1"
    assert [(r.row_id, r.bound) for r in rows(form, turbine, sel)] == [
        ("power_hp.lo", 20.0),
        ("power_hp.hi", 5000.0),
    ]
    assert form.cost(turbine, {"power": 5.0e5}, sel, F) == pytest.approx(
        530 * (5.0e5 / 745.6998715822702) ** 0.81, rel=1e-15
    )  # :1376-1385
    # §10.4.5: a floor below 20 hp, parallel expanders above 5,000 hp.
    small = {"power": 10.0 / KAPPA_W}
    sel = select(form, turbine, small)
    assert isinstance(sel, Selection) and sel.size == "floor"
    assert form.cost(turbine, small, sel, F) == pytest.approx(530 * 20.0**0.81, rel=1e-15)
    large = {"power": 12000.0 / KAPPA_W}
    sel = select(form, turbine, large)
    assert isinstance(sel, Selection) and sel.size == "units:3" and sel.n == 3
    assert form.cost(turbine, large, sel, F) == pytest.approx(3 * 530 * 4000.0**0.81, rel=1e-14)


def test_a50_the_compressor_regimes_at_their_boundaries() -> None:
    """§10.5 A50: per-unit P_C at S_min·(1 ± 1e-9), S_max·(1 − 1e-12) and, at N = 2,
    S_max·(1 + 1e-9) select floor / units:1, units:1 and units:3; C_P by hand to A14's 1e-10."""
    alpha = {"Centrifugal": (7.58, 0.8), "Reciprocating": (7.9661, 0.8), "Screw": (8.1238, 0.7243)}
    bounds = {
        "Centrifugal": (200.0, 30000.0),
        "Reciprocating": (100.0, 20000.0),
        "Screw": (10.0, 750.0),
    }
    for kind, (s_min, s_max) in bounds.items():
        e = entry("compressor", compressor_type=kind, material="CarbonSteel")
        form = FORMS[e.form]
        a1, a2 = alpha[kind]
        for per_unit, units, want in (
            (s_min * (1 - 1e-9), 1, "floor"),
            (s_min * (1 + 1e-9), 1, "units:1"),
            (s_max * (1 - 1e-12), 1, "units:1"),
            (s_max * (1 + 1e-9), 2, "units:3"),
        ):
            x = {"power": units * _brake_for(per_unit) / KAPPA_W}
            sel = select(form, e, x)
            assert isinstance(sel, Selection) and sel.size == want, (kind, per_unit, sel)
            if want == "floor":
                hand = math.exp(a1 + a2 * math.log(s_min))
            else:
                n = sel.n
                w = (x["power"] / n) * KAPPA_W
                hand = n * math.exp(a1 + a2 * math.log(w / _eta_m(w)))
            assert form.cost(e, x, sel, F) == pytest.approx(hand, rel=1e-10), (kind, want)
            q = form.quantities(e, x, F, sel.n)["consumed_power_hp"]
            for r in rows(form, e, sel):  # the held regime's rows hold at S(N) (§10.4.4)
                assert r.sense * (q - r.bound) >= 0.0, (kind, want, r)


def test_a50_the_loader_refuses_a_compressor_without_a_motor_and_a_narrow_consumed_range() -> None:
    doc = shipped_document()
    doc["entries"] = [e for e in doc["entries"] if e["entry_id"] != "motor.electric"]
    _refused(doc, "needs the set's machine.drive entry of form sslw-motor-v1")
    doc = shipped_document()
    choices = doc["entries"][6]["options"]["compressor_type"]["choices"]
    choices["Screw"]["ranges"]["consumed_power_hp"]["max"] = 29.0
    _refused(doc, "consumed-power range max 29.0 < 3·min 10.0")


def test_a51_the_loader_refuses_a_malformed_amendment() -> None:
    def amended(doc: dict[str, Any]) -> dict[str, Any]:
        node = doc["entries"][0]["options"]["hx_type"]["choices"]["fixed_head"]["alpha2"]
        return node["amended"]  # type: ignore[no-any-return]

    for change, fragment in (
        (lambda a: a.pop("ruling"), "amended: missing ruling"),
        (lambda a: a.pop("citation"), "amended: missing citation"),
        (lambda a: a.pop("replaces"), "amended: neither replaces nor index_basis"),
        (lambda a: a.update(replaces=0.9228), "amended: replaces 0.9228 equals value"),
        (lambda a: a.update(scale="log"), "amended: scale and index_basis go together"),
        (lambda a: a.update(index_basis=567.0), "amended: scale and index_basis go together"),
        (lambda a: a.update(index_basis=567.0, scale="cubic"), "scale 'cubic' is not one of"),
    ):
        doc = shipped_document()
        change(amended(doc))
        _refused(doc, fragment)
    # §10.10.5.2: the sixth refusal; a basis has no basis of its own.
    for entry_id in ("pump", "motor.electric"):
        doc = shipped_document()
        body = next(e for e in doc["entries"] if e["entry_id"] == entry_id)
        body["index_basis"]["value"]["amended"].update(index_basis=394.0, scale="log")
        _refused(doc, "index_basis.value.amended: a basis carries no index_basis or scale")


def test_a51_effective_values_are_the_notes_expressions_bitwise() -> None:
    """§10.10.5.1: no amendment carries an index basis, so v_e is `value`, bitwise."""
    fixed = entry("exchanger.shell_tube", hx_type="fixed_head")
    assert fixed.n("alpha2") == 0.9228
    assert sorted(fixed.amended) == ["options.hx_type.choices.fixed_head.alpha2"]
    vertical = entry("vessel.vertical")
    assert vertical.numbers["platforms"][1]["a"] == 300.9
    assert sorted(vertical.amended) == ["coefficients.platforms[1].a"]
    for entry_id in ("pump", "motor.electric"):
        e = entry(entry_id)
        assert sorted(e.amended) == ["index_basis.value"], entry_id
        assert e.amended["index_basis.value"]["effective_value"] == 500.0, entry_id
        assert e.ratio == 1.0, entry_id
    horizontal = entry("vessel.horizontal")
    assert horizontal.numbers["platforms_horizontal"] == {"a": 2005, "b_D": 0.20294}
    assert horizontal.amended == {}
    tower = entry("vessel.vertical", weight_limit="2")
    assert (tower.n("alpha1"), tower.n("alpha2"), tower.n("alpha3")) == (7.2756, 0.18255, 0.02297)
    assert sorted(tower.amended) == ["coefficients.platforms[1].a"]


def test_a51_fit_two_increases_with_weight() -> None:
    """§10.10.6: fit "2" increases with W for W >= 1 lb, since alpha2, alpha3 > 0; its range is the
    3rd ed.'s tower range (p. 575, Eq. 22.57)."""
    tower = entry("vessel.vertical", weight_limit="2")
    assert (tower.ranges["weight_lb"].min, tower.ranges["weight_lb"].max) == (9000.0, 2500000.0)
    assert tower.n("alpha2") > 0.0 and tower.n("alpha3") > 0.0

    def c_v(w: float) -> float:
        lw = math.log(w)
        return math.exp(tower.n("alpha1") + tower.n("alpha2") * lw + tower.n("alpha3") * lw * lw)

    grid = [10.0 ** (k / 4) for k in range(0, 29)]  # 1 lb to 1e7 lb
    assert all(c_v(a) < c_v(b) for a, b in zip(grid, grid[1:], strict=False))


def test_every_form_has_one_function_on_both_algebras() -> None:
    cases = {
        "exchanger.shell_tube": {"area": 80.0, "design_pressure": psig_to_pa(400.0)},
        "vessel.vertical": {"diameter": 1.8, "length": 15.0, "thickness": 0.03175},
        "vessel.horizontal": {"diameter": 1.5, "length": 6.0, "thickness": 0.03175},
        "column.trays": {"diameter": 1.4},
        "pump": {"vol_flow": 0.02, "head": 80.0, "power": 2.0e4},
        "motor.electric": {"power": 2.0e4},
        "compressor": {"power": 1.0e6},
        "turbine": {"power": 4.0e5},
    }
    for entry_id, x in cases.items():
        e = entry(entry_id)
        form = FORMS[e.form]
        full = {**x, "n_act": 30} if entry_id == "column.trays" else x
        sel = select(form, e, full)
        assert isinstance(sel, Selection), (entry_id, sel)
        reference = form.cost(e, full, sel, F)
        symbols = {k: ca.SX.sym(k) for k in x}
        expr = form.cost(e, {**full, **symbols}, sel, CasadiAlgebra())
        fn = ca.Function("f", list(symbols.values()), [expr])
        twin = float(fn(*[x[k] for k in symbols]))
        assert twin == pytest.approx(reference, rel=1e-14), entry_id


# -- generic forms -------------------------------------------------------------------------------


def test_generic_forms() -> None:
    s = 120.0
    a = [3.4974, 0.4485, 0.1074]
    l10 = math.log10(s)
    expected = 10 ** (a[0] + a[1] * l10 + a[2] * l10**2)
    assert log_polynomial(s, a, "10", 1.0, F) == pytest.approx(expected, rel=1e-14)
    le = math.log(s * 2.0)
    assert log_polynomial(s, a, "e", 2.0, F) == math.exp(a[0] + a[1] * le + a[2] * le**2)
    assert power_law(s, 1.0e5, 100.0, 0.6, F) == pytest.approx(1.0e5 * 1.2**0.6, rel=1e-15)


# -- A19 quotes ----------------------------------------------------------------------------------


def test_a19_quotes() -> None:
    e = 1.2345678901234567
    flat = Quote(cost=1.2e6, currency="EUR", year=2021, kind="purchased", source="vendor")
    assert flat.cost_expr(e, None, F) == 1.2e6 * e
    scaled = Quote(
        cost=1.2e6,
        currency="EUR",
        year=2021,
        kind="purchased",
        source="vendor",
        size_quantity="area",
        size_value=120.0,
        exponent=0.6,
    )
    assert scaled.cost_expr(e, 150.0, F) == pytest.approx(
        1.2e6 * e * (150.0 / 120.0) ** 0.6, rel=1e-15
    )
    sized = Quote(1.2e6, "EUR", 2021, "purchased", "vendor", "area", 120.0)
    assert size_mismatch(sized, "E1", 131.0) is None
    found = size_mismatch(sized, "E1", 133.0)
    assert isinstance(found, Limitation) and found.code == "QUOTE_SIZE_MISMATCH"
    assert size_mismatch(scaled, "E1", 300.0) is None


# -- A16 the cost basis --------------------------------------------------------------------------


SERIES = {s: load_series(s) for s in ("bls-ppi-wpu11-annual-v1", "eurostat-ppi-c28-ea-annual-v1")}
RATES = load_rates()
DEFAULT_SERIES = {"USD": "bls-ppi-wpu11-annual-v1", "EUR": "eurostat-ppi-c28-ea-annual-v1"}


def target(currency: str, year: int, lf: float = 1.0) -> TargetBasis:
    return TargetBasis(currency, year, DEFAULT_SERIES, lf)


def factor(source: SourceBasis, to: TargetBasis, series: Any = None) -> float:
    found = escalate(source, to, series or SERIES, RATES)
    assert not isinstance(found, Refusal), found
    return found.factor


def test_a16_the_same_basis_is_exactly_one_and_round_trips_within_2_ulp() -> None:
    for currency in ("USD", "EUR"):
        for year in (2006, 2015, 2021, 2024):
            assert factor(SourceBasis(currency, year), target(currency, year)) == 1.0
    ulp = math.ulp(1.0)
    there = factor(SourceBasis("USD", 2010), target("USD", 2024))
    back = factor(SourceBasis("USD", 2024), target("USD", 2010))
    assert abs(there * back - 1.0) <= 2 * ulp
    there = factor(SourceBasis("EUR", 2023), target("USD", 2023))
    back = factor(SourceBasis("USD", 2023), target("EUR", 2023))
    assert abs(there * back - 1.0) <= 2 * ulp


def test_the_escalation_formula_and_its_refusals() -> None:
    bls = SERIES["bls-ppi-wpu11-annual-v1"].values
    eur_2023 = RATES.usd_per_unit("EUR", 2023)
    found = escalate(SourceBasis("USD", 2010), target("EUR", 2023, 1.1), SERIES, RATES)
    assert not isinstance(found, Refusal)
    assert found.factor == (bls[2023] / bls[2010]) * (1.0 / eur_2023) * 1.1
    jpy = escalate(SourceBasis("USD", 2020), target("JPY", 2020), SERIES, RATES)
    assert not isinstance(jpy, Refusal) and jpy.exchange == 1.0 / (
        1.0 / RATES.rates["JPY"][1][2020]
    )
    gone = escalate(SourceBasis("GBP", 2020), target("USD", 2020), SERIES, RATES)
    assert isinstance(gone, Refusal) and gone.code == "ESCALATION_SERIES_MISSING"
    early = escalate(SourceBasis("EUR", 1990), target("EUR", 2020), SERIES, RATES)
    assert isinstance(early, Refusal) and early.code == "INDEX_YEAR_UNAVAILABLE"
    late = escalate(SourceBasis("USD", 2020), target("EUR", 2030), SERIES, RATES)
    assert isinstance(late, Refusal) and late.code == "INDEX_YEAR_UNAVAILABLE"
    odd = TargetBasis("SEK", 2020, {"USD": "bls-ppi-wpu11-annual-v1"})
    none = escalate(SourceBasis("USD", 2020), odd, SERIES, RATES)
    assert isinstance(none, Refusal) and none.code == "EXCHANGE_RATE_UNAVAILABLE"


def test_an_index_basis_uses_a_users_cepci_or_maps_to_2006() -> None:
    sslw = SourceBasis("USD", index=("CEPCI", 500.0), year_equivalent=2006, set_id="sslw-idaes-v1")
    mapped = escalate(sslw, target("USD", 2024), SERIES, RATES)
    assert not isinstance(mapped, Refusal)
    bls = SERIES["bls-ppi-wpu11-annual-v1"].values
    assert mapped.factor == bls[2024] / bls[2006]
    assert [lim.code for lim in mapped.limitations] == ["INDEX_BASIS_MAPPED"]
    cepci = IndexSeries("user-cepci", "CEPCI", {2024: 800.0})
    user = escalate(
        sslw,
        TargetBasis("USD", 2024, {"USD": "user-cepci"}),
        {**SERIES, "user-cepci": cepci},
        RATES,
    )
    assert not isinstance(user, Refusal) and user.factor == 800.0 / 500.0 and not user.limitations


def test_the_series_files_carry_their_provenance_and_match_the_publishers() -> None:
    for series in SERIES.values():
        doc = series.document
        for key in ("publisher", "title", "url", "retrieved", "sha256", "licence", "licence_text"):
            assert doc[key], key
        assert len(doc["sha256"]) == 64
    bls = SERIES["bls-ppi-wpu11-annual-v1"].values
    assert bls[2024] == 179.313 and bls[2025] == 186.2  # BLS API v1, period M13
    eu = SERIES["eurostat-ppi-c28-ea-annual-v1"].values
    assert eu[2021] == 100.0  # the base year of unit I21
    # G.5A release of January 5, 2026.
    assert RATES.usd_per_unit("EUR", 2025) == 1.1306
    assert RATES.usd_per_unit("GBP", 2024) == 1.2781
    assert RATES.rates["JPY"][1][2025] == 149.5686
    assert RATES.rates["CHF"][1][2023] == 0.8984
    assert RATES.rates["CNY"][1][2022] == 6.7290


def test_no_shipped_set_number_is_lost_on_parsing() -> None:
    """Every `{value, source_line}` parses to the float of its printed decimal."""
    doc = shipped_document()
    seen = 0

    def walk(node: Any) -> None:
        nonlocal seen
        if isinstance(node, dict):
            if "source_line" in node and "value" in node:
                seen += 1
                assert isinstance(node["value"], int | float)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(copy.deepcopy(doc))
    assert seen > 150


def test_item_options_and_shell_thickness_are_schema_fields() -> None:
    """An item names the set's options as strings (the set file's names and choices) and the vessel
    shell thickness in m (θ `t_shell`, §9.2.4 II); a non-string option fails validation."""
    from openflowsheet.assessment.spec import AssessmentDocumentError, load_assessment

    base = {
        "schema_version": "assessment-v1",
        "assessment_id": "x",
        "basis": {"currency": "USD", "year": 2024},
    }
    item = {"options": {"weight_limit": "2", "platforms_ladders": "false"}, "shell_thickness": 0.02}
    spec = load_assessment({**base, "items": {"D-1.drum": item}})
    assert spec.document["items"]["D-1.drum"] == item
    for bad in ({"options": {"weight_limit": 2}}, {"shell_thickness": 0.0}, {"options": {"x": ""}}):
        with pytest.raises(AssessmentDocumentError):
            load_assessment({**base, "items": {"D-1.drum": bad}})
