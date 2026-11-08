"""ST WO-1: the stream table core (`application.stream_table`) against note §11's gates G1–G10,
G14 and G16 at core level, and foundation rulings Amendment 5's assertions Q1.A14, Q1.A15, Q2.A13
and Q4.A13–A15 (`docs/design/ST-stream-table.md`, `docs/roadmap/foundation-rulings.md` §17).

Expectations come from outside the module under test: the S05 reference (`s05_reference.json`,
mpmath, independent of production code) for G3; the provider's own values, called directly by the
test, for G2 and the closed forms of Q4.A15; and the verifier's helpers for G7, G8 and G16, which
are comparators of the same code base (Amendment 5, "not established"). Set `ST_RECORD=<path>` to
append the recorded numbers (G1, G2, G7, G8, G14, G16 (e)) as JSON lines.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import st_support as support
from st_support import (
    Members,
    Recording,
    build,
    families,
    members,
    stream,
    substream,
    unit,
    with_rows,
    with_state,
)

from openflowsheet.application import stream_table
from openflowsheet.canonical import canonical_json, document_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.messages import audit
from openflowsheet.messages.catalogue import CATALOGUE
from openflowsheet.models import flow_id, pressure_id, temperature_id
from openflowsheet.thermo import PropertyRequest, PropertyResult, StreamState
from openflowsheet.thermo.iapws95 import Iapws95Provider
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.verify import checks, forms, thermal
from openflowsheet.verify import pr_c1 as verify_pr_c1

EPS = sys.float_info.epsilon
ROOT = support.ROOT
TH_C1 = "s11-th/TH-C1"
#: G3's state (note §11): S4 at 932203.564 Pa, V = L = 0.5 mol/s.
G3_PRESSURE = 932203.564
#: O6: G3's expectations, molar, from the committed S05 reference; M of water (S05).
S05_450 = json.loads(
    (ROOT / "docs" / "derivations" / "scripts" / "s05_reference.json").read_text(encoding="utf-8")
)["saturation"]["450"]
M_WATER = 0.018015268
#: Q1.A15 (d): above IAPWS-95's critical pressure.
SUPERCRITICAL_PRESSURE = 2.5e7
SYN_COMPONENTS = ("A", "B", "C")
#: Q4.A15's probe pressure (= P_r) and amounts.
PROBE_PRESSURE = 1e5
PROBE_FLOWS = (1.0, 1.0, 1.0)


def _record(gate: str, **values: Any) -> None:
    target = os.environ.get("ST_RECORD")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"gate": gate, **values}, sort_keys=True) + "\n")


def _context(source: Members) -> EvaluationContext:
    return EvaluationContext(
        model_version=source.certificate["model_version"],
        constants_sha256=source.certificate["constants_sha256"],
        phase_signature=None,
    )


def _phase(entry: Mapping[str, Any], family: str) -> dict[str, Any]:
    (found,) = [phase for phase in entry["phases"] if phase["id"]["family"] == family]
    return dict(found)


def _iapws(context: EvaluationContext, temperature: float, pressure: float, phase: str) -> Any:
    return Iapws95Provider().evaluate_phase(
        PropertyRequest(StreamState((1.0,), temperature, pressure), phase, ("h",)),  # type: ignore[arg-type]
        context,
    )


def _saturation(context: EvaluationContext, pressure: float) -> tuple[float, float]:
    """`(h_L, h_V)` at `(T_sat(P), P)`, evaluated by the test directly (G2)."""
    provider = Iapws95Provider()
    t_lo = float(provider.describe().domain["T"][0])
    t_sat = provider.evaluate_phase(
        PropertyRequest(StreamState((1.0,), t_lo, pressure), "LIQUID", ("Tsat",)), context
    ).values["Tsat"]
    return (
        _iapws(context, t_sat, pressure, "LIQUID").values["h"],
        _iapws(context, t_sat, pressure, "VAPOR").values["h"],
    )


# -- the probe stream of Q1.A14 (b) and Q4.A15 ----------------------------------------------------


@cache
def _probe() -> tuple[str, str]:
    """Q1.A14 (b)'s stream: the first undeclared (R3) stream of a SYN-001 corpus revision, in
    corpus order, whose certificate carries no degeneracy `independent_split` row for it (such a
    row flags the stream whatever its state, which Q4.A15 (b) and (c) must control; D1-4)."""
    for run, document in support.documents().items():
        if document["basis"]["provider_id"] != "syn001":
            continue
        for entry in document["streams"]:
            (sub,) = entry["substreams"]
            degenerate = any(
                quote["reason"] in stream_table.DEGENERATE_REASONS for quote in entry["checks"]
            )
            if sub["phase_source"] == "flash" and not degenerate:
                return run, entry["id"]
    raise AssertionError("no SYN-001 corpus revision has an undeclared stream")


def _probe_members(
    flows: tuple[float, ...], temperature: float, pressure: float | None = None
) -> tuple[Members, str]:
    run, name = _probe()
    source = members(run)
    updates = {flow_id(name, c): n for c, n in zip(SYN_COMPONENTS, flows, strict=True)}
    updates[temperature_id(name)] = temperature
    if pressure is not None:
        updates[pressure_id(name)] = pressure
    return with_state(source, updates), name


def _sums(temperature: float) -> tuple[tuple[float, ...], float, float]:
    """`(K, Σ z K, Σ z/K)` at the probe's `(n, T, P)`, as syn001's flash forms them."""
    provider = Syn001Provider()
    context = EvaluationContext(model_version="st-probe", constants_sha256="st-probe")
    constants = checks.k_values(provider, temperature, PROBE_PRESSURE, context)
    total = sum(PROBE_FLOWS)
    z = tuple(value / total for value in PROBE_FLOWS)
    sum_zk = sum(z[i] * constants[i] for i in range(3))
    sum_z_over_k = sum(z[i] / constants[i] for i in range(3))
    return constants, sum_zk, sum_z_over_k


def _bisect(side: str, low: float, high: float) -> float:
    """A temperature whose `Σ z K − 1` (bubble) or `Σ z/K − 1` (dew) lies in `[low, high]`, found
    by bisection in double on the provider's own sums (Q4.A15)."""

    def excess(temperature: float) -> float:
        _, sum_zk, sum_z_over_k = _sums(temperature)
        return (sum_zk if side == "bubble" else sum_z_over_k) - 1.0

    # Σ z K rises with T (bubble), Σ z/K falls (dew).
    lo, hi = (330.0, 360.0) if side == "bubble" else (360.0, 390.0)
    rising = side == "bubble"
    for _ in range(200):
        middle = 0.5 * (lo + hi)
        value = excess(middle)
        if low <= value <= high:
            return middle
        if (value < low) == rising:
            lo = middle
        else:
            hi = middle
    raise AssertionError(f"no {side} temperature with excess in [{low}, {high}]")


# -- G1: Rankine energy (TH-C1) -------------------------------------------------------------------


def test_g1_rankine_energy_closes_within_the_quoted_rows() -> None:
    document = support.document(TH_C1)
    ratios = {}
    for name in ("P", "B", "T", "C"):
        entry = unit(document, name)
        (row,) = entry["checks"]
        assert abs(entry["closure"]) <= row["tolerance"], (name, entry["closure"])
        ratios[name] = abs(entry["closure"]) / row["tolerance"]
    overall = document["energy"]["overall"]
    (envelope,) = overall["checks"]
    h1 = substream(document, "S1")["H_flow"]
    h5 = substream(document, "S5")["H_flow"]
    q_b, q_c = unit(document, "B")["Q"], unit(document, "C")["Q"]
    w_p, w_t = unit(document, "P")["W"], unit(document, "T")["W"]
    gap = (h5 - h1) - (q_b + q_c + w_p + w_t)
    assert abs(gap) <= envelope["tolerance"]
    assert w_p > 0.0 and w_t < 0.0 and q_b > 0.0 and q_c < 0.0
    _record(
        "G1",
        closure_over_tolerance=ratios,
        max_ratio=max(ratios.values()),
        envelope_gap=gap,
        envelope_tolerance=envelope["tolerance"],
        H_S5_minus_H_S1=h5 - h1,
        duties=q_b + q_c + w_p + w_t,
    )


# -- G2: the lever rule (S4, R1) and S5 -----------------------------------------------------------


def test_g2_s4_vapour_fraction_is_the_lever_rule() -> None:
    source, document = members(TH_C1), support.document(TH_C1)
    context = _context(source)
    s4 = substream(document, "S4")
    assert s4["phase_source"] == "carried_split"  # O5: TH-C1's S4 is wet.
    pressure = stream(document, "S4")["P"]
    h_l, h_v = _saturation(context, pressure)
    n4 = s4["n_total"]
    h4 = (substream(document, "S3")["H_flow"] + unit(document, "T")["W"]) / n4
    lever = (h4 - h_l) / (h_v - h_l)
    (turbine,) = unit(document, "T")["checks"]
    bound = 10.0 * turbine["tolerance"] / (n4 * (h_v - h_l)) + 1e-12
    vf_molar, vf_mass = s4["vapor_fraction_molar"], s4["vapor_fraction_mass"]
    assert abs(vf_molar - lever) <= bound
    assert abs(vf_mass - vf_molar) <= 8.0 * EPS * vf_molar
    assert 1e-3 < vf_molar < 1.0 - 1e-3  # Q4.A13 (c)
    _record("G2", lever=lever, vf_molar=vf_molar, difference=vf_molar - lever, bound=bound)


def test_g2_s5_saturated_liquid() -> None:
    source, document = members(TH_C1), support.document(TH_C1)
    variables = source.variables
    s5 = substream(document, "S5")
    assert s5["phase_source"] == "carried_split"
    v5, l5 = variables["S5.sat.V"], variables["S5.sat.L"]
    n5 = s5["n_total"]
    assert s5["vapor_fraction_molar"] == v5 / (0.0 + v5 + l5)
    h_l, h_v = _saturation(_context(source), stream(document, "S5")["P"])
    bound = (abs(v5) * (h_v - h_l) + abs(v5 + l5 - n5) * abs(h_l)) / n5 + 8.0 * EPS * abs(h_l)
    assert abs(s5["h"] - h_l) <= bound
    _record("G2-S5", v5_over_n5=abs(v5) / n5, h_gap=s5["h"] - h_l, bound=bound)


# -- G3: IAPWS-95 at 450 K (Q1.A15 (a), (b)) ------------------------------------------------------


def _g3_members(pressure: float) -> Members:
    return with_state(
        members(TH_C1),
        {"S4.P": pressure, "S4.sat.V": 0.5, "S4.sat.L": 0.5, "S4.n.H2O": 1.0},
    )


def test_g3_saturation_at_450_k_against_the_s05_reference() -> None:
    source = _g3_members(G3_PRESSURE)
    document = build(source)
    assert document["components"] == [{"id": "H2O", "molar_mass": M_WATER}]
    reported_t = stream(document, "S4")["T"]
    assert reported_t == source.variables["S4.T"]  # Q1.A15 (b), bitwise
    assert abs(reported_t - 450.0) > 100.0  # Q1.A15 (a) [pre]
    s4 = substream(document, "S4")
    assert families(s4) == ["VAPOR", "LIQUID"]
    expected = {
        ("LIQUID", "h_mass"): float(S05_450["h_l"]) / M_WATER,
        ("VAPOR", "h_mass"): float(S05_450["h_v"]) / M_WATER,
        ("LIQUID", "s_mass"): float(S05_450["s_l"]) / M_WATER,
        ("VAPOR", "s_mass"): float(S05_450["s_v"]) / M_WATER,
        ("LIQUID", "rho"): float(S05_450["rho_l"]),
        ("VAPOR", "rho"): float(S05_450["rho_v"]),
    }
    errors = {}
    for (family, member), value in expected.items():
        reported = _phase(s4, family)[member]
        errors[f"{family}.{member}"] = (reported - value) / value
        assert abs(reported - value) <= 1e-7 * abs(value), (family, member, reported, value)
    assert s4["vapor_fraction_molar"] == 0.5
    _record("G3", relative_errors=errors)


def test_q1_a15_d_a_refused_tsat_nulls_the_properties_only() -> None:
    document = build(_g3_members(SUPERCRITICAL_PRESSURE))
    s4 = substream(document, "S4")
    reason = s4["absent"]["H_flow"]
    assert reason["code"] == "property_evaluation_failed"  # [pre]: Tsat refused (O-21)
    assert reason["params"]["stream"] == "S4"
    assert reason["params"]["phase"] == "LIQUID" and reason["params"]["property"] == "Tsat"
    assert reason["params"]["status"] != "ok"
    for member in ("h", "h_mass", "s", "s_mass", "rho", "H_flow", "S_flow", "V_flow"):
        assert s4[member] is None and s4["absent"][member] == reason, member
    for phase in s4["phases"]:
        for member in ("h", "h_mass", "s", "s_mass", "v", "rho", "H_flow", "S_flow", "V_flow"):
            assert phase[member] is None and phase["absent"][member] == reason, member
        assert phase["phase_fraction_molar"] == 0.5
        assert phase["phase_fraction_mass"] == 0.5
    assert s4["vapor_fraction_molar"] == 0.5 and s4["vapor_fraction_mass"] == 0.5
    for member in ("n", "m", "x", "w"):
        assert s4[member] is not None
    assert stream(document, "S4")["T"] is not None


# -- Q1.A15 (c): the carried splits' calls, and G7's R1 half --------------------------------------


def _segments(document: Mapping[str, Any], calls: list[Any], per_phase: int) -> dict[str, list]:
    """The recorded calls of each stream: streams are evaluated in document order, and each
    makes `[Tsat or flash] + per_phase` calls per listed phase (none when dormant, only the first
    when the flash or `Tsat` is refused)."""
    segments: dict[str, list[Any]] = {}
    index = 0
    for entry in document["streams"]:
        (sub,) = entry["substreams"]
        source = sub["phase_source"]
        refused = sub["absent"].get("H_flow", {}).get("code") in {
            "flash_failed",
            "property_evaluation_failed",
        } and source in {"flash", "carried_split"}
        if source == "zero_flow":
            count = 0
        elif source == "declared":
            count = per_phase * len(sub["phases"])
        elif refused:
            count = 1
        else:
            count = 1 + per_phase * len(sub["phases"])
        segments[entry["id"]] = calls[index : index + count]
        index += count
    assert index == len(calls)
    return segments


def _per_phase(provider: Any) -> int:
    declared = provider.describe().properties
    return 1 + ("s" in declared) + ("v" in declared)


def test_q1_a15_c_every_carried_split_is_evaluated_at_tsat() -> None:
    seen = 0
    for run, directory in support.corpus().items():
        if run not in support.documents():
            continue
        source = support.read_members(directory)
        provider = Recording(support.fresh_provider(source))
        document = build(source, provider)
        if not any(
            sub["phase_source"] == "carried_split" for _, sub in support.substreams(document)
        ):
            continue
        t_lo = float(provider.describe().domain["T"][0])
        segments = _segments(document, provider.calls, _per_phase(provider))
        for name, sub in support.substreams(document):
            if sub["phase_source"] != "carried_split":
                continue
            seen += 1
            pressure = stream(document, name)["P"]
            (method, request, result), *rest = segments[name]
            assert method == "evaluate_phase" and request.properties == ("Tsat",)
            assert request.phase == "LIQUID"
            assert request.state == StreamState((1.0,), t_lo, pressure)
            t_sat = result.values["Tsat"]
            assert [r.phase for _, r, _ in rest] == [
                family for family in families(sub) for _ in range(_per_phase(provider))
            ]
            for method, request, _ in rest:
                assert method == "evaluate_phase" and len(request.properties) == 1
                assert request.state == StreamState((1.0,), t_sat, pressure)
            expected = thermal.saturated_enthalpy(
                Iapws95Provider(), source.variables, name, _context(source), ("H2O",)
            )
            assert sub["H_flow"] == expected, (run, name)
    assert seen > 0
    _record("Q1.A15c", carried_splits=seen)


# -- Q1.A14 and G4: dormancy ----------------------------------------------------------------------


def _assert_dormant(entry: Mapping[str, Any], stored_pressure: float) -> None:
    name = entry["id"]
    zero_flow = {"code": "zero_flow", "params": {"stream": name}}
    assert entry["T"] is None and entry["absent"]["T"] == zero_flow
    assert entry["P"] == stored_pressure
    (sub,) = entry["substreams"]
    for value in (*sub["n"], *sub["m"]):
        assert value == 0.0 and math.copysign(1.0, value) == 1.0
    for member in ("n_total", "m_total", "H_flow", "S_flow", "V_flow"):
        assert sub[member] == 0.0 and math.copysign(1.0, sub[member]) == 1.0, member
    for member in ("x", "w", "h", "h_mass", "s", "s_mass", "rho"):
        assert sub[member] is None and sub["absent"][member] == zero_flow, member
    for member in ("vapor_fraction_molar", "vapor_fraction_mass"):
        assert sub[member] is None and sub["absent"][member] == zero_flow, member
    assert sub["phases"] == [] and sub["flash_near_phase_boundary"] is False
    assert sub["phase_source"] == "zero_flow"


def test_q1_a14_a_every_dormant_corpus_stream() -> None:
    dormant = 0
    for run, document in support.documents().items():
        variables = members(run).variables
        for entry in document["streams"]:
            if entry["dormant"]:
                dormant += 1
                _assert_dormant(entry, variables[pressure_id(entry["id"])])
    assert dormant >= 1  # [pre] (O-21)
    _record("Q1.A14a", dormant_streams=dormant)


@pytest.mark.parametrize("temperature", [1234.5, 300.0], ids=["b1-outside", "b2-inside"])
def test_q1_a14_b_dormant_probe_makes_no_provider_call(temperature: float) -> None:
    source, name = _probe_members((+0.0, -0.0, +0.0), temperature)
    provider = Recording(support.fresh_provider(source))
    document = build(source, provider)
    entry = stream(document, name)
    _assert_dormant(entry, source.variables[pressure_id(name)])
    codes = {reason["code"] for reason in entry["absent"].values()}
    codes |= {reason["code"] for reason in entry["substreams"][0]["absent"].values()}
    assert codes == {"zero_flow"}
    for _, request, _ in provider.calls:
        assert not request.state.is_dormant


def test_g4_mass_fractions_equal_mole_fractions_on_syn001() -> None:
    worst = 0.0
    for document in support.documents().values():
        if document["basis"]["provider_id"] != "syn001":
            continue
        for _, sub in support.substreams(document):
            for entry in (sub, *sub["phases"]):
                if entry["x"] is None:
                    continue
                for x, w in zip(entry["x"], entry["w"], strict=True):
                    assert abs(w - x) <= 8.0 * EPS * x
                    if x > 0.0:
                        worst = max(worst, abs(w - x) / (EPS * x))
    _record("G4", max_w_minus_x_over_eps_x=worst)


# -- Q4.A13: the vapour fraction ------------------------------------------------------------------


def test_q4_a13_a_vapour_fraction_definition_bitwise() -> None:
    for document in support.documents().values():
        for _, sub in support.substreams(document):
            if not sub["phases"] or sub["vapor_fraction_molar"] is None:
                continue
            n_listed = m_listed = n_vapour = m_vapour = 0.0
            for phase in sub["phases"]:
                n_listed += phase["n_total"]
                m_listed += phase["m_total"]
            for phase in sub["phases"]:
                if phase["id"]["family"] == "VAPOR":
                    n_vapour += phase["n_total"]
                    m_vapour += phase["m_total"]
            assert sub["vapor_fraction_molar"] == n_vapour / n_listed
            assert sub["vapor_fraction_mass"] == m_vapour / m_listed
            for phase in sub["phases"]:
                assert phase["phase_fraction_molar"] == phase["n_total"] / n_listed
                assert phase["phase_fraction_mass"] == phase["m_total"] / m_listed
            if "VAPOR" in families(sub):
                vapour = _phase(sub, "VAPOR")["phase_fraction_molar"]
                assert sub["vapor_fraction_molar"] == vapour
            else:
                assert sub["vapor_fraction_molar"] == 0.0


@pytest.mark.parametrize(
    ("temperature", "family", "fraction"), [(340.0, "LIQUID", 0.0), (385.0, "VAPOR", 1.0)]
)
def test_q4_a13_b_single_phase_fractions_are_exact(
    temperature: float, family: str, fraction: float
) -> None:
    _, sum_zk, sum_z_over_k = _sums(temperature)
    assert (sum_zk < 1.0) if family == "LIQUID" else (sum_z_over_k < 1.0)  # [pre]
    source, name = _probe_members(PROBE_FLOWS, temperature, PROBE_PRESSURE)
    sub = substream(build(source), name)
    assert families(sub) == [family]
    assert sub["vapor_fraction_molar"] == fraction and sub["vapor_fraction_mass"] == fraction
    assert sub["flash_near_phase_boundary"] is False  # Q4.A15 (d)


def test_q4_a13_b_declared_streams_are_zero_or_one() -> None:
    for document in support.documents().values():
        for _, sub in support.substreams(document):
            if sub["phase_source"] != "declared":
                continue
            expected = 1.0 if families(sub) == ["VAPOR"] else 0.0
            assert families(sub) in (["VAPOR"], ["LIQUID"])
            assert sub["vapor_fraction_molar"] == expected
            assert sub["vapor_fraction_mass"] == expected


def test_q4_a13_d_the_two_bases() -> None:
    first_unequal: float | None = None
    worst = 0.0
    for document in support.documents().values():
        masses = {c["id"]: c["molar_mass"] for c in document["components"]}
        for _, sub in support.substreams(document):
            vf_molar, vf_mass = sub["vapor_fraction_molar"], sub["vapor_fraction_mass"]
            if vf_molar is None:
                continue
            if len(set(masses.values())) == 1:
                size = len(sub["components"])
                assert abs(vf_mass - vf_molar) <= 4.0 * (size + 1) * EPS * vf_molar
                if vf_molar > 0.0:
                    worst = max(worst, abs(vf_mass - vf_molar) / (EPS * vf_molar))
            elif first_unequal is None and len(sub["phases"]) >= 2:
                first_unequal = abs(vf_mass - vf_molar)
    assert first_unequal is not None and first_unequal > 1e-3  # [pre] (O-21)
    _record("Q4.A13d", max_vf_gap_over_eps_vf=worst, first_unequal_gap=first_unequal)


def test_q4_a13_e_no_member_is_called_quality() -> None:
    pattern = re.compile("quality", re.IGNORECASE)

    def keys(node: Any) -> Iterator[str]:
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from keys(value)
        elif isinstance(node, list):
            for value in node:
                yield from keys(value)

    for document in support.documents().values():
        assert not any(pattern.search(key) for key in keys(document))


def test_q4_a13_f_a_refused_flash_nulls_the_phase_quantities() -> None:
    source, name = _probe_members(PROBE_FLOWS, 450.0)
    entry = stream(build(source), name)
    (sub,) = entry["substreams"]
    reason = {"code": "flash_failed", "params": {"stream": name, "status": "out_of_domain"}}
    assert sub["phases"] == []
    for member in ("vapor_fraction_molar", "vapor_fraction_mass", "H_flow", "h", "h_mass"):
        assert sub[member] is None and sub["absent"][member] == reason, member
    assert sub["n"] == [1.0, 1.0, 1.0] and sub["x"] is not None
    assert entry["T"] == 450.0 and entry["P"] is not None


# -- Q4.A14: listing ------------------------------------------------------------------------------


def _s5(vapor: float, liquid: float | None = None) -> tuple[Members, dict[str, Any]]:
    source = members(TH_C1)
    n5 = source.variables["S5.n.H2O"]
    edited = with_state(source, {"S5.sat.V": vapor, "S5.sat.L": n5 if liquid is None else liquid})
    return edited, substream(build(edited), "S5")


def _saturated(source: Members, name: str) -> float:
    return thermal.saturated_enthalpy(
        Iapws95Provider(), source.variables, name, _context(source), ("H2O",)
    )


@pytest.mark.parametrize("vapor", [+0.0, -0.0], ids=["plus-zero", "minus-zero"])
def test_q4_a14_a_a_zero_vapour_is_not_listed(vapor: float) -> None:
    source, sub = _s5(vapor)
    assert families(sub) == ["LIQUID"]
    assert sub["vapor_fraction_molar"] == 0.0 and sub["vapor_fraction_mass"] == 0.0
    assert sub["H_flow"] == _saturated(source, "S5")


def test_q4_a14_b_a_trace_vapour_is_listed() -> None:
    source, sub = _s5(1e-300)
    assert families(sub) == ["VAPOR", "LIQUID"]
    assert _phase(sub, "VAPOR")["n_total"] == 1e-300
    assert sub["vapor_fraction_molar"] > 0.0
    assert sub["H_flow"] == _saturated(source, "S5")


def test_q4_a14_c_a_negative_vapour_is_listed_unclamped() -> None:
    n5 = members(TH_C1).variables["S5.n.H2O"]
    vapor = -1e-12 * n5
    liquid = n5 - vapor
    source, sub = _s5(vapor, liquid)
    assert families(sub) == ["VAPOR", "LIQUID"]
    phase = _phase(sub, "VAPOR")
    assert phase["n_total"] == vapor < 0.0 and phase["phase_fraction_molar"] < 0.0
    assert sub["vapor_fraction_molar"] == vapor / (0.0 + vapor + liquid) < 0.0
    assert sub["H_flow"] == _saturated(source, "S5")
    total = 0.0
    for listed in sub["phases"]:
        total += listed["H_flow"]
    assert sub["H_flow"] == total


def test_q4_a14_d_a_subnormal_stream_flows_and_its_mass_underflows() -> None:
    source, name = _probe_members((5e-324, 0.0, 0.0), 350.0, PROBE_PRESSURE)
    entry = stream(build(source), name)
    (sub,) = entry["substreams"]
    assert entry["dormant"] is False and entry["T"] == 350.0
    assert families(sub) == ["VAPOR"]  # [pre]: the flash answers VAPOR
    phase = _phase(sub, "VAPOR")
    assert phase["n_total"] == 5e-324
    assert sub["h"] == 30000.0 and phase["h"] == 30000.0
    assert sub["x"] == [1.0, 0.0, 0.0] and sub["vapor_fraction_molar"] == 1.0
    assert sub["m_total"] == 0.0 and math.copysign(1.0, sub["m_total"]) == 1.0
    for owner, member in (
        (sub, "h_mass"),
        (sub, "w"),
        (sub, "vapor_fraction_mass"),
        (phase, "phase_fraction_mass"),
    ):
        assert owner[member] is None and owner["absent"][member]["code"] == "value_not_finite"


def _flash_signature(source: Members, name: str) -> str | None:
    from openflowsheet.thermo import FlashRequest

    variables = source.variables
    components = support.fresh_provider(source).describe().components
    st = StreamState(
        tuple(variables[flow_id(name, c)] for c in components),
        variables[temperature_id(name)],
        variables[pressure_id(name)],
    )
    return (
        support.fresh_provider(source)
        .flash(FlashRequest(state=st), _context(source))
        .phase_signature
    )


def test_q4_a14_e_every_single_phase_flash_lists_one_phase() -> None:
    for run, document in support.documents().items():
        source = members(run)
        for name, sub in support.substreams(document):
            if sub["phase_source"] != "flash":
                continue
            if _flash_signature(source, name) in ("LIQUID", "VAPOR"):
                assert len(sub["phases"]) == 1, (run, name)


# -- Q2.A13: property forms -----------------------------------------------------------------------


def test_q2_a13_a_syn001_substreams() -> None:
    for run, document in support.documents().items():
        if document["basis"]["provider_id"] != "syn001":
            continue
        not_s = {"code": "property_not_provided", "params": {"provider": "syn001", "property": "s"}}
        not_v = {"code": "property_not_provided", "params": {"provider": "syn001", "property": "v"}}
        for _, sub in support.substreams(document):
            if not sub["phases"]:
                continue
            for entry in (sub, *sub["phases"]):
                for member in ("H_flow", "h", "h_mass"):
                    assert entry[member] is not None, (run, member)
                for member in ("s", "s_mass", "S_flow"):
                    assert entry["absent"][member] == not_s
                for member in ("V_flow", "rho", *(("v",) if entry is not sub else ())):
                    assert entry["absent"][member] == not_v


class _Double:
    """Q2.A13 (b), (c): SYN-001 declaring `s` and `v`, answering them per component or as a
    mixture."""

    def __init__(self, mixture: bool) -> None:
        self.inner = Syn001Provider()
        self.mixture = mixture

    def describe(self) -> Any:
        described = self.inner.describe()
        return replace(
            described,
            provider_id="syn001-double",
            properties=(*described.properties, "s", "v"),
        )

    def flash(self, request: Any, context: Any) -> Any:
        return self.inner.flash(request, context)

    def evaluate_phase(self, request: Any, context: Any) -> Any:
        if request.properties == ("s",):
            values = {"s": 150.0} if self.mixture else {"s_A": 100.0, "s_B": 200.0, "s_C": 300.0}
        elif request.properties == ("v",):
            values = {"v": 2e-3} if self.mixture else {f"v_{c}": 1e-3 for c in SYN_COMPONENTS}
        else:
            return self.inner.evaluate_phase(request, context)
        return PropertyResult(status="ok", phase_signature=None, values=values)


def _b_far() -> tuple[Members, str]:
    return _probe_members(PROBE_FLOWS, _bisect("bubble", 1e-5, 1e-4), PROBE_PRESSURE)


def test_q2_a13_b_per_component_s_and_v_are_not_summed() -> None:
    source, name = _b_far()
    reference = substream(build(source), name)
    sub = substream(build(source, _Double(mixture=False)), name)
    assert len(sub["phases"]) == 2
    for prop, members_ in (("s", ("s", "s_mass", "S_flow")), ("v", ("V_flow", "rho"))):
        reason = {
            "code": "property_not_provided",
            "params": {"provider": "syn001-double", "property": prop},
        }
        for entry in (sub, *sub["phases"]):
            for member in members_:
                assert entry[member] is None and entry["absent"][member] == reason
    for phase in sub["phases"]:
        assert phase["absent"]["v"]["params"]["property"] == "v"
    assert sub["H_flow"] == reference["H_flow"]
    assert [p["H_flow"] for p in sub["phases"]] == [p["H_flow"] for p in reference["phases"]]


def test_q2_a13_c_mixture_s_and_v_are_used_bitwise() -> None:
    source, name = _b_far()
    sub = substream(build(source, _Double(mixture=True)), name)
    s_flow = v_flow = 0.0
    for phase in sub["phases"]:
        assert phase["S_flow"] == phase["n_total"] * 150.0
        assert phase["V_flow"] == phase["n_total"] * 2e-3
        assert phase["rho"] == phase["m_total"] / phase["V_flow"]
        s_flow += phase["S_flow"]
        v_flow += phase["V_flow"]
    assert sub["S_flow"] == s_flow and sub["V_flow"] == v_flow
    assert sub["rho"] == sub["m_total"] / sub["V_flow"]


def test_q2_a13_d_wilson_vapour_has_s_and_no_density() -> None:
    reason = {
        "code": "property_not_provided",
        "params": {"provider": "wilson-ig-v2", "property": "v"},
    }
    seen = 0
    for document in support.documents().values():
        if document["basis"]["provider_id"] != "wilson-ig-v2":
            continue
        for _, sub in support.substreams(document):
            if "VAPOR" in families(sub):
                vapour = _phase(sub, "VAPOR")
                assert vapour["s"] is not None
                assert vapour["rho"] is None and vapour["absent"]["rho"] == reason
                seen += 1
    assert seen > 0  # [pre] (O-21)


# -- G5, G6: absence and consistency over every document ------------------------------------------


def _objects(document: Mapping[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for entry in document["streams"]:
        yield "stream", entry
        for sub in entry["substreams"]:
            yield "substream", sub
            for phase in sub["phases"]:
                yield "phase", phase
    for entry in document["energy"]["units"]:
        yield "unit", entry
        for port in entry["ports"]:
            yield "port", port
    yield "overall", document["energy"]["overall"]


#: Members that may be null by the document's structure, not as an absent quantity.
STRUCTURAL_NULLS = {"stream": {"from", "to"}}


def _floats(node: Any) -> Iterator[float]:
    if isinstance(node, float):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _floats(value)
    elif isinstance(node, list):
        for value in node:
            yield from _floats(value)


def assert_g5(document: Mapping[str, Any]) -> None:
    for kind, entry in _objects(document):
        allowed = STRUCTURAL_NULLS.get(kind, set())
        nulls = {key for key, value in entry.items() if value is None and key not in allowed}
        assert nulls == set(entry["absent"]), (kind, entry.get("id"), nulls, entry["absent"])
        for reason in entry["absent"].values():
            assert set(reason) == {"code", "params"}
            assert reason["code"] in stream_table.CODES
            assert reason["code"] in CATALOGUE  # WO-4: a key of MSG's catalogue
            for value in reason["params"].values():
                assert isinstance(value, str | int | float) or (
                    isinstance(value, list) and all(isinstance(v, str) for v in value)
                )
    assert all(math.isfinite(value) for value in _floats(document))
    canonical_json(document)


def assert_g6(document: Mapping[str, Any]) -> None:
    for _, sub in support.substreams(document):
        for entry in (sub, *sub["phases"]):
            for member in ("x", "w"):
                if entry[member] is not None:
                    assert abs(math.fsum(entry[member]) - 1.0) <= 1e-12
        if sub["H_flow"] is not None and sub["phases"]:
            total = 0.0
            for phase in sub["phases"]:
                total += phase["H_flow"]
            assert sub["H_flow"] == total
        if sub["phase_source"] == "flash" and sub["phases"]:
            for index, n in enumerate(sub["n"]):
                listed = math.fsum(phase["n"][index] for phase in sub["phases"])
                assert abs(listed - n) <= 1e-12 * sub["n_total"]
        if sub["phase_source"] == "carried_split":
            listed = math.fsum(phase["n_total"] for phase in sub["phases"])
            assert abs(listed - sub["n_total"]) <= 1e-9 * sub["n_total"]
        if sub["vapor_fraction_molar"] is not None:
            negative = math.fsum(-p["n_total"] for p in sub["phases"] if p["n_total"] < 0.0)
            slack = negative / math.fsum(p["n_total"] for p in sub["phases"])
            for fraction in (sub["vapor_fraction_molar"], sub["vapor_fraction_mass"]):
                if fraction is not None:
                    assert -slack <= fraction <= 1.0 + slack


def test_g5_absence_over_every_corpus_document() -> None:
    for run, document in support.documents().items():
        try:
            assert_g5(document)
        except AssertionError as error:
            raise AssertionError(run) from error


#: Note §6.4: each code's (family, kind), its params, and a `not_supported` one's gap capability.
SECTION_6_4: dict[str, tuple[str, str, set[str], str | None]] = {
    "zero_flow": ("notice", "notice", {"stream"}, None),
    "property_not_provided": ("refusal", "not_supported", {"provider", "property"}, "property"),
    "property_evaluation_failed": (
        "refusal",
        "numerical",
        {"stream", "phase", "property", "status"},
        None,
    ),
    "flash_failed": ("refusal", "numerical", {"stream", "status"}, None),
    "value_not_finite": ("refusal", "numerical", {"subject", "quantity"}, None),
    "stream_enthalpy_absent": ("notice", "notice", {"subject", "streams"}, None),
    "energy_balance_undefined": ("refusal", "not_supported", {"unit", "model"}, "energy form"),
}


def test_g5_every_code_is_a_complete_catalogue_entry() -> None:
    """WO-4 (note §6.4; MSG C3): the seven codes are complete entries of MSG's catalogue, of the
    family, kind and params the table gives, each with an example, `stream_enthalpy_absent`
    pointing at the four reasons a stream's enthalpy flow can be missing."""
    assert set(SECTION_6_4) == stream_table.CODES
    for code, (family, kind, params, capability) in SECTION_6_4.items():
        entry = CATALOGUE.entry(code)
        assert entry is not None, code
        assert (entry.family, entry.kind, entry.complete) == (family, kind, True), code
        assert set(entry.params) == params, code
        assert entry.document["examples"], code
        assert entry.document.get("why") and entry.document.get("action"), code
        gap = entry.gap
        if capability is None:
            assert gap is None, code
        else:
            assert gap is not None and gap["limitation"] is None, code
            assert str(gap["capability"]).startswith(f"{capability}:<"), code
    see_also = CATALOGUE.entry("stream_enthalpy_absent")
    assert see_also is not None
    assert set(see_also.see_also) >= {
        "property_not_provided",
        "property_evaluation_failed",
        "flash_failed",
        "value_not_finite",
    }


def test_g15_an_emitted_code_reaches_the_runtime_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """G15 (MSG C3): `absent` reports each code to MSG's runtime audit, which fails the session on
    a code without an entry; a code removed from the catalogue is recorded as a miss."""
    recorder = audit.Auditor()
    monkeypatch.setattr(audit, "auditor", recorder)
    stream_table.absent("zero_flow", stream="S1")
    assert recorder.misses == {}
    monkeypatch.setattr(stream_table, "CODES", stream_table.CODES | {"st_probe_code"})
    stream_table.absent("st_probe_code")
    assert recorder.misses == {"st_probe_code": "openflowsheet.application.stream_table"}


def test_g6_consistency_over_every_corpus_document() -> None:
    for run, document in support.documents().items():
        try:
            assert_g6(document)
        except AssertionError as error:
            raise AssertionError(run) from error


def _rachford_rice(source: Members, name: str, sub: Mapping[str, Any]) -> tuple[float, float]:
    variables = source.variables
    constants = checks.k_values(
        support.fresh_provider(source),
        variables[temperature_id(name)],
        variables[pressure_id(name)],
        _context(source),
    )
    beta = sub["vapor_fraction_molar"]
    residual = sum(
        z * (k - 1.0) / (1.0 + beta * (k - 1.0)) for z, k in zip(sub["x"], constants, strict=True)
    )
    y, x = _phase(sub, "VAPOR")["x"], _phase(sub, "LIQUID")["x"]
    worst = max(abs(yi - k * xi) / abs(yi) for yi, k, xi in zip(y, constants, x, strict=True))
    return residual, worst


def test_g6_rachford_rice_on_syn001_two_phase_streams() -> None:
    probes = [_b_far()]
    seen = 0
    for run, document in support.documents().items():
        if document["basis"]["provider_id"] == "syn001":
            probes += [
                (members(run), n)
                for n, s in support.substreams(document)
                if s["phase_source"] == "flash" and len(s["phases"]) == 2
            ]
    for source, name in probes:
        residual, worst = _rachford_rice(source, name, substream(build(source), name))
        assert abs(residual) <= 1e-10 and worst <= 1e-9, (name, residual, worst)
        seen += 1
    assert seen > 1


# -- G7, G8: the verifier's figures ---------------------------------------------------------------


def _syn_also(provider_id: str, sub: Mapping[str, Any], st: StreamState, context: Any) -> str:
    """Beyond G7's list, counted only: a SYN-001 stream the verifier reads by
    `checks.enthalpy_flow` without a snap (its flash agrees with the report's phases), compared
    bitwise; `=checks` or `!=checks`, else empty."""
    if provider_id != "syn001" or not sub["phases"]:
        return ""
    from openflowsheet.thermo import FlashRequest

    provider = Syn001Provider()
    result = provider.flash(FlashRequest(state=st), context)
    if result.phase_signature == "TWO_PHASE":
        if checks._admissible_phase(provider, st, context) is not None:
            return ""
        decided = ["VAPOR", "LIQUID"]
    else:
        decided = [str(result.phase_signature)]
    if decided != families(sub):
        return ""
    same = sub["H_flow"] == checks.enthalpy_flow(provider, st, context)
    return "=checks" if same else "!=checks"


@cache
def _g7(run: str) -> tuple[frozenset[str], dict[str, str]]:
    """`(bitwise, other)`: the streams whose `H_flow` G7 compared bitwise, and the rest with why
    they are not compared."""
    source, document = members(run), support.document(run)
    context = _context(source)
    variables = source.variables
    provider_id = document["basis"]["provider_id"]
    components = support.fresh_provider(source).describe().components
    bitwise: set[str] = set()
    other: dict[str, str] = {}
    for name, sub in support.substreams(document):
        st = StreamState(
            tuple(variables[flow_id(name, c)] for c in components),
            variables[temperature_id(name)],
            variables[pressure_id(name)],
        )
        provider = support.fresh_provider(source)
        source_rule = sub["phase_source"]
        expected: float | None = None
        if source_rule == "zero_flow":
            other[name] = "dormant"
            continue
        if source_rule == "carried_split":
            expected = thermal.saturated_enthalpy(provider, variables, name, context, components)
        elif source_rule == "declared" and provider_id in {
            "iapws95-v1",
            "coolprop-heos-v1",
            "wilson-ig-v2",
        }:
            expected = forms.enthalpy_flow(provider, st, families(sub)[0], context)  # type: ignore[arg-type]
        elif source_rule == "flash" and _flash_signature(source, name) in ("LIQUID", "VAPOR"):
            if provider_id == "syn001":
                expected = checks.enthalpy_flow(provider, st, context)
            elif provider_id == "pr-c1-v1":
                expected = verify_pr_c1.enthalpy_flow(provider, st, context, components)
        if expected is None:
            other[name] = f"{provider_id}:{source_rule}" + _syn_also(provider_id, sub, st, context)
            continue
        assert sub["H_flow"] == expected, (run, name, sub["H_flow"], expected)
        bitwise.add(name)
    return frozenset(bitwise), other


def test_g7_verifier_equivalence_bitwise() -> None:
    compared, counted = 0, {}
    for run in support.documents():
        bitwise, other = _g7(run)
        compared += len(bitwise)
        for reason in other.values():
            counted[reason] = counted.get(reason, 0) + 1
    assert compared > 0
    _record("G7", bitwise=compared, not_compared=counted)


#: G8's one failing run (escalated, ST_DECISIONS.md E1): `T05b:SC-1`'s product S2 is a pure
#: component at its boiling point downstream of a valve. The verifier reads its Ḣ from the stored
#: lifted split (temperature-degenerate, ADR 0012 D7); the report's raw TP flash (Q4.R12 (a))
#: lists LIQUID alone, 2016 W below it. The stream is flagged by Q4.R12 (b) (ii) as ruled, but
#: G8 bounds the envelope closure by the row's tolerance. Not loosened: reported as failing.
G8_ESCALATED = frozenset({"g8/T05b:SC-1"})


@cache
def _g8() -> tuple[dict[str, tuple[float, float]], float]:
    """`({run: (gap, tolerance)} of the runs failing G8, max passing gap/tolerance)`."""
    failures: dict[str, tuple[float, float]] = {}
    worst = 0.0
    for run, document in support.documents().items():
        overall = document["energy"]["overall"]
        if not overall["checks"]:
            continue
        (row,) = overall["checks"]
        if row["result"] in {"not_applicable", "unsupported", "blocked"} or row["value"] is None:
            continue
        envelope = {*overall["feeds"], *overall["products"]}
        if document["judged_at"] == "final_state" and envelope <= _g7(run)[0]:
            if overall["closure"] != row["value"]:
                failures[run] = (abs(overall["closure"] - row["value"]), 0.0)
            continue
        gap = abs(overall["closure"] - row["value"])
        if gap <= row["tolerance"]:
            worst = max(worst, gap / row["tolerance"])
        else:
            failures[run] = (gap, row["tolerance"])
    return failures, worst


@pytest.mark.xfail(strict=True, reason="G8 fails on g8/T05b:SC-1; escalated (ST_DECISIONS E1)")
def test_g8_envelope_agreement() -> None:
    failures, worst = _g8()
    _record("G8", max_passing_gap_over_tolerance=worst, failures=failures)
    assert not failures, failures


def test_g8_fails_only_on_the_escalated_run() -> None:
    failures, _ = _g8()
    assert set(failures) == G8_ESCALATED, failures


# -- G9: determinism ------------------------------------------------------------------------------


def _fresh_sha(directory: Path) -> str:
    code = (
        "import sys; from openflowsheet.application.stream_table import from_bundle; "
        "from openflowsheet.canonical import document_sha256; "
        "print(document_sha256(from_bundle(sys.argv[1])))"
    )
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code, str(directory)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout.strip()


def test_g9_determinism_in_process_and_across_processes() -> None:
    runs = [
        TH_C1,
        _probe()[0],
        next(
            r for r, d in support.documents().items() if d["basis"]["provider_id"] == "wilson-ig-v2"
        ),
    ]
    for run in runs:
        directory = support.corpus()[run]
        first, second = stream_table.from_bundle(directory), stream_table.from_bundle(directory)
        assert canonical_json(first) == canonical_json(second)
        expected = document_sha256(first)
        assert _fresh_sha(directory) == expected == _fresh_sha(directory)


# -- G10: 0.3.0 bundles ---------------------------------------------------------------------------


def test_g10_the_v030_bundles() -> None:
    served, refused = 0, 0
    for manifest in sorted(support.V030_BUNDLES.rglob("run-manifest.json")):
        directory = manifest.parent
        artifacts = directory / "artifacts"
        missing = [name for name in stream_table.ARTIFACTS if not (artifacts / name).is_file()]
        try:
            document = stream_table.from_bundle(directory)
        except stream_table.StreamTableError as error:
            assert error.code == "not_found" and error.detail["member"] == missing[0]
            refused += 1
            continue
        assert not missing
        assert document["judged_at"] in (None, "projection", "final_state")
        assert_g5(document)
        assert_g6(document)
        served += 1
    assert served > 0 and refused > 0
    _record("G10", served=served, refused=refused)


def test_refusals_name_the_missing_member() -> None:
    for run, error in support.refusals().items():
        assert error.code == "not_found", (run, error)
        assert error.detail["member"] in (stream_table.MANIFEST, *stream_table.ARTIFACTS)


def test_an_inconsistent_state_is_an_internal_error() -> None:
    source = members(TH_C1)
    state = json.loads(json.dumps(source.state))
    state["variables"]["S1.T"] = 400.0
    with pytest.raises(stream_table.StreamTableError) as raised:
        build(replace(source, state=state))
    assert raised.value.code == "internal_error"
    assert raised.value.detail["reasons"] == ["state_sha256_mismatch"]


@pytest.mark.skipif(support.COOLPROP, reason="the coolprop extra is installed; TH-C2 is served")
def test_an_unavailable_basis_is_refused(tmp_path: Path) -> None:
    directory = tmp_path / "bundle"
    shutil.copytree(support.corpus()[TH_C1], directory)
    revision = (ROOT / "benchmarks" / "s11" / "thermal" / "TH-C2.json").read_text(encoding="utf-8")
    (directory / "artifacts" / "revision.json").write_text(revision, encoding="utf-8")
    with pytest.raises(stream_table.StreamTableError) as raised:
        stream_table.from_bundle(directory)
    assert raised.value.code == "unsupported"
    assert raised.value.message == "basis_unavailable(coolprop-heos-v1)"
    assert raised.value.detail["hint"]


def test_every_basis_of_the_corpus_is_served() -> None:
    bases = {d["basis"]["provider_id"] for d in support.documents().values()}
    expected = {"syn001", "pr-c1-v1", "iapws95-v1", "wilson-ig-v2"}
    if support.COOLPROP:
        expected.add("coolprop-heos-v1")
    assert bases == expected


def test_c8_no_module_level_mutable_state() -> None:
    for name, value in vars(stream_table).items():
        if name.startswith("__"):
            continue
        assert not isinstance(value, dict | list | set | bytearray), name


# -- G14: performance -----------------------------------------------------------------------------


def _best_of(directory: Path, repeat: int = 3) -> float:
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        stream_table.from_bundle(directory)
        times.append(time.perf_counter() - start)
    return min(times)


def test_g14_performance() -> None:
    documents = support.documents()
    largest = max(documents, key=lambda run: len(documents[run]["streams"]))
    th_c1 = _best_of(support.corpus()[TH_C1])
    big = _best_of(support.corpus()[largest])
    _record("G14", th_c1_seconds=th_c1, largest=largest, largest_seconds=big)
    assert th_c1 <= 0.5 and big <= 2.0


# -- G16 (Q4.A15): the report's decision near a phase boundary ------------------------------------


def _minority(sub: Mapping[str, Any]) -> tuple[str, float]:
    amounts = {phase["id"]["family"]: phase["n_total"] for phase in sub["phases"]}
    total = 0.0
    for amount in amounts.values():
        total += amount
    family = min(amounts, key=lambda f: abs(amounts[f]))
    return family, abs(amounts[family]) / total


def _per_component_h(source: Members, name: str, family: str) -> dict[str, float]:
    variables = source.variables
    st = StreamState(PROBE_FLOWS, variables[temperature_id(name)], variables[pressure_id(name)])
    values = (
        Syn001Provider()
        .evaluate_phase(
            PropertyRequest(st, family, ("h",)),
            _context(source),  # type: ignore[arg-type]
        )
        .values
    )
    return {c: values[f"h_{c}"] for c in SYN_COMPONENTS}


@pytest.mark.parametrize(
    ("side", "majority"), [("bubble", "LIQUID"), ("dew", "VAPOR")], ids=["B-near", "D-near"]
)
def test_g16_a_near_the_boundary(side: str, majority: str) -> None:
    temperature = _bisect(side, 5e-13, 1e-12)
    constants, sum_zk, sum_z_over_k = _sums(temperature)
    z = 1.0 / 3.0
    if side == "bubble":
        delta = sum_zk - 1.0
        c = max(1.0, max(constants)) ** 2 / sum(z * (k - 1.0) ** 2 for k in constants)
    else:
        delta = sum_z_over_k - 1.0
        c = max(1.0, max(1.0 / k for k in constants)) ** 2 / sum(
            z * (1.0 / k - 1.0) ** 2 for k in constants
        )
    source, name = _probe_members(PROBE_FLOWS, temperature, PROBE_PRESSURE)
    assert _flash_signature(source, name) == "TWO_PHASE"  # [pre] (O-21)
    sub = substream(build(source), name)
    assert families(sub) == ["VAPOR", "LIQUID"]
    family, fraction = _minority(sub)
    assert family != majority and 0.0 < fraction <= c * delta
    assert sub["flash_near_phase_boundary"] is True
    context = _context(source)
    st = StreamState(PROBE_FLOWS, temperature, PROBE_PRESSURE)
    assert checks._admissible_phase(Syn001Provider(), st, context) == majority
    delta_h = sub["H_flow"] - checks.enthalpy_flow(Syn001Provider(), st, context)
    minority = _phase(sub, family)
    h_min = _per_component_h(source, name, family)
    h_maj = _per_component_h(source, name, majority)
    closed = math.fsum(
        n * (h_min[c] - h_maj[c]) for c, n in zip(SYN_COMPONENTS, minority["n"], strict=True)
    )
    tolerance = (
        64.0
        * EPS
        * math.fsum(
            PROBE_FLOWS[i] * abs(h_maj[c]) + minority["n"][i] * abs(h_min[c])
            for i, c in enumerate(SYN_COMPONENTS)
        )
    )
    assert abs(closed) > 10.0 * tolerance  # [pre]
    assert abs(delta_h - closed) <= tolerance
    assert (delta_h > 0.0) if side == "bubble" else (delta_h < 0.0)
    _record(
        "G16a",
        side=side,
        temperature=temperature,
        minority_fraction=fraction,
        c_delta=c * delta,
        delta_h=delta_h,
        closed_form=closed,
        achieved_over_tolerance=abs(delta_h - closed) / tolerance,
    )


@pytest.mark.parametrize("side", ["bubble", "dew"], ids=["B-far", "D-far"])
def test_g16_b_far_from_the_boundary(side: str) -> None:
    temperature = _bisect(side, 1e-5, 1e-4)
    constants, sum_zk, sum_z_over_k = _sums(temperature)
    z = 1.0 / 3.0
    if side == "bubble":
        delta = sum_zk - 1.0
        floor = delta * min(1.0, min(constants)) ** 2 / sum(z * (k - 1.0) ** 2 for k in constants)
    else:
        inverse = [1.0 / k for k in constants]
        delta = sum_z_over_k - 1.0
        floor = delta * min(1.0, min(inverse)) ** 2 / sum(z * (k - 1.0) ** 2 for k in inverse)
    source, name = _probe_members(PROBE_FLOWS, temperature, PROBE_PRESSURE)
    assert _flash_signature(source, name) == "TWO_PHASE"
    sub = substream(build(source), name)
    _, fraction = _minority(sub)
    assert fraction >= floor
    assert sub["flash_near_phase_boundary"] is False
    context = _context(source)
    st = StreamState(PROBE_FLOWS, temperature, PROBE_PRESSURE)
    assert checks._admissible_phase(Syn001Provider(), st, context) is None
    assert sub["H_flow"] == checks.enthalpy_flow(Syn001Provider(), st, context)


@pytest.mark.parametrize("reason", sorted(stream_table.DEGENERATE_REASONS))
def test_g16_c_a_degeneracy_row_flags_the_stream(reason: str) -> None:
    source, name = _b_far()
    row = {
        "category": "independent_split",
        "id": f"independent_split.st-probe.{name}",
        "independence_qualification": None,
        "near_threshold": False,
        "reason": reason,
        "reference": None,
        "result": "not_applicable",
        "scope": "not_applicable",
        "subject": name,
        "tolerance": None,
        "value": None,
    }
    flagged = build(with_rows(source, [row]))
    assert substream(flagged, name)["flash_near_phase_boundary"] is True
    quoted = stream(flagged, name)["checks"]
    assert quoted[-1]["id"] == row["id"] and quoted[-1]["reason"] == reason
    assert substream(build(source), name)["flash_near_phase_boundary"] is False


def test_g16_e_the_corpus_decisions() -> None:
    recorded: dict[str, dict[str, Any]] = {}
    for run, document in support.documents().items():
        provider_id = document["basis"]["provider_id"]
        if provider_id not in ("syn001", "pr-c1-v1"):
            continue
        source = members(run)
        context = _context(source)
        variables = source.variables
        tally = recorded.setdefault(
            provider_id, {"r3": 0, "flagged": 0, "disagreeing": 0, "max_measure": 0.0}
        )
        for name, sub in support.substreams(document):
            if sub["phase_source"] != "flash" or not sub["phases"]:
                continue
            provider = support.fresh_provider(source)
            components = provider.describe().components
            st = StreamState(
                tuple(variables[flow_id(name, c)] for c in components),
                variables[temperature_id(name)],
                variables[pressure_id(name)],
            )
            from openflowsheet.thermo import FlashRequest

            result = provider.flash(FlashRequest(state=st), context)
            decision = [result.phase_signature]
            measure = 0.0
            if result.phase_signature == "TWO_PHASE":
                decision = ["VAPOR", "LIQUID"]
                if provider_id == "syn001":
                    admissible = checks._admissible_phase(provider, st, context)
                    decision = [admissible] if admissible else decision
                    constants = checks.k_values(provider, st.temperature, st.pressure, context)
                    z = [n / st.total_flow for n in st.n]
                    bubble = max(1.0, max(constants)) ** 2 / sum(
                        zi * (k - 1.0) ** 2 for zi, k in zip(z, constants, strict=True)
                    )
                    inverse = [1.0 / k for k in constants]
                    dew = max(1.0, max(inverse)) ** 2 / sum(
                        zi * (k - 1.0) ** 2 for zi, k in zip(z, inverse, strict=True)
                    )
                    measure = max(bubble, dew) * checks.ADMISSIBILITY_EPSILON
                else:
                    fraction = verify_pr_c1.liquid_fraction(result, st, components)
                    if fraction <= verify_pr_c1.TAU_DEW:
                        decision = ["VAPOR"]
                    assert result.liquid is not None
                    x_nh3 = result.liquid.n[components.index("NH3")] / sum(result.liquid.n)
                    measure = verify_pr_c1.TAU_DEW / x_nh3
            tally["r3"] += 1
            tally["flagged"] += sub["flash_near_phase_boundary"]
            tally["max_measure"] = max(tally["max_measure"], measure)
            if decision != families(sub):
                tally["disagreeing"] += 1
                assert sub["flash_near_phase_boundary"] is True, (run, name)
    assert recorded["syn001"]["r3"] > 0
    _record("G16e", per_basis=recorded)
