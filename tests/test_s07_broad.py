"""S07 tier B: `coolprop-heos-v1` for the 114 broad-list fluids (WO-S07-2b; spec §16.10, A34, A35).

Tier B is **self-consistent only, not validated** (spec §16.5.1): the expectations are the
generator's 50-digit evaluations of each fluid's closed form with CoolProp's own coefficients
(`s07_reference.json`, spec §16.6), plus the provider's consistency with itself (A10, A11, A17,
A22). Nothing here checks a tier-B fluid's coefficients against their source, and no check
compares an EOS with experiment (spec §15, §16.17).

The column applied is §16.10's tier-B one; the tolerances are §16.11's. The checks are the tier-A
ones (`test_s07_coolprop.py`), applied at the states ref registers for tier B. No fluid is
skipped and none has its own tolerance: a fluid the generic provider cannot serve fails here and
is removed by amendment (spec §16.13 Q-A1-5).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable

import pytest
from s07_coolprop_support import require_coolprop
from test_s07_coolprop import (
    ABSENT_SCRIPT,
    FD_TOL,
    FLUIDS,
    LOW_ORDER,
    REF,
    ROOT,
    THIRD_ORDER,
    Provider,
    Result,
    a01_problems,
    a03_problems,
    a05_problems,
    a28_problems,
    a34_problems,
    band_t,
    check_a02,
    ev,
    fd_ratios,
    flash,
    probe_problems,
    psat,
    refusal_problem,
    run_script,
    saturated_phases,
    six,
    tp,
)

from openflowsheet.thermo import PropertyResult
from openflowsheet.thermo import _coolprop_heos_fluids as table
from openflowsheet.thermo import coolprop_heos as cph

TIER_B = [row["id"] for row in table.FLUIDS if row["tier"] == "B"]
PROVIDERS = {cid: Provider(cid) for cid in TIER_B}
#: Spec §16.6: the registered states of a tier-B fluid.
PHI_KEYS = {"phi_gas", "phi_liq", "phi_dilute"}
TP_KEYS = {"V_sup", "V_sub", "L_sub", "S_dense", "L_corner", "V_corner"}
#: Spec §16.10 A10/A11: the provider's own saturation at these three temperatures.
SAT_TEMPERATURES = ("T_lo", "T_mid", "T_sigma_max")
PUBLISHED_CHECKS = ROOT / "benchmarks" / "s07" / "published_checks.yaml"


@pytest.fixture
def coolprop() -> None:
    require_coolprop()


needs_coolprop = pytest.mark.usefixtures("coolprop")


def sat_temperature(cid: str, key: str) -> float:
    constants = FLUIDS[cid]["constants"]
    if key == "T_mid":
        return float(FLUIDS[cid]["saturation"]["sat_mid"]["T"])
    return float(constants[key])


# -- the list, A01, A02, A25, A28, A34, A35 --------------------------------------------------------


def test_tier_b_is_the_114_others() -> None:
    """Spec §16.1, §16.3: 123 admitted, tier A the nine S04 fluids, tier B the other 114."""
    assert len(table.FLUIDS) == 123
    assert len(TIER_B) == 114
    assert all(FLUIDS[cid]["tier"] == "B" for cid in TIER_B)
    assert all(FLUIDS[cid]["verification"] == "self-consistent" for cid in TIER_B)


@pytest.mark.parametrize("cid", TIER_B)
def test_a01_constants_are_refs_bitwise(cid: str) -> None:
    assert a01_problems(PROVIDERS[cid], cid) == []


@pytest.mark.parametrize("cid", TIER_B)
def test_a02_describe(cid: str) -> None:
    check_a02(PROVIDERS[cid], cid)


def test_a02_a28_describe_answers_without_coolprop_with_the_same_identity() -> None:
    states = [[cid, *tp(cid, "V_sup")[:2]] for cid in TIER_B]
    absent = run_script(ABSENT_SCRIPT, states)
    assert sorted(absent) == sorted(TIER_B)
    for cid in TIER_B:
        assert absent[cid]["describe"] == repr(PROVIDERS[cid].describe()), cid


@needs_coolprop
def test_a28_identity_recipe() -> None:
    assert a28_problems(cph, TIER_B) == []


@pytest.mark.parametrize("cid", TIER_B)
def test_a34_tier_and_bound_are_reported(cid: str) -> None:
    assert a34_problems(PROVIDERS[cid], cid) == []
    assert "self-consistent" in PROVIDERS[cid].describe().uncertainty  # spec §16.5.1


def qualifies(rows: list[dict[str, object]]) -> bool:
    """Spec §16.5.2 A35: at least 3 rows at 2 or more distinct densities (C16 passed by ref)."""
    return len(rows) >= 3 and len({row["rho"] for row in rows}) >= 2


def test_a35_published_checks() -> None:
    checks = REF["published_checks"]
    assert checks["sha256"] == hashlib.sha256(PUBLISHED_CHECKS.read_bytes()).hexdigest()
    reporting = []
    for cid in TIER_B:
        rows = checks["rows"].get(cid, [])
        reports = FLUIDS[cid]["verification"] == "published-check"
        assert reports == qualifies(rows), cid
        described = PROVIDERS[cid].describe().uncertainty
        assert described.startswith("verification: published-check") == reports, cid
        reporting += [cid] if reports else []
    if not any(checks["rows"].values()):
        assert reporting == []  # zero rows (S07, Q-A1-3): no fluid reports `published-check`


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a25_determinism_and_identity(cid: str) -> None:
    """As tier A, at tier B's registered states (it has no NC state; the NC midpoint stays)."""
    provider, fluid = PROVIDERS[cid], PROVIDERS[cid]._fluid
    t, p, phase = tp(cid, "L_sub")
    band = FLUIDS[cid]["band"]["probes"]["0.5"]["P"]
    calls: list[Callable[[], Result]] = [
        lambda: ev(provider, t, p, phase),
        lambda: ev(provider, band_t(cid), band, "LIQUID"),
        lambda: psat(provider, band_t(cid)),
        lambda: ev(provider, t, FLUIDS[cid]["tsat"]["tsat_mid"]["P"], "VAPOR", ("Tsat",)),
        lambda: ev(provider, sum(fluid.nc_t) / 2, sum(fluid.nc_p) / 2, "VAPOR"),
        lambda: ev(provider, t, p, phase, ("g",)),
        lambda: ev(provider, fluid.t_lo * (1 - 1e-6), p, phase),
        lambda: flash(provider, t, p),
        lambda: flash(provider, t, p, spec="PH"),
        lambda: flash(provider, band_t(cid), band),
    ]
    for call in calls:
        first, second = call(), call()
        assert repr(first) == repr(second)
        assert first.provider_id == "coolprop-heos-v1"
        assert first.reference_convention == "COOLPROP-DEF-ref-v1"
        assert first.achieved_accuracy == "exact-double"
        if isinstance(first, PropertyResult):
            assert all(math.isfinite(value) for value in first.values.values())


# -- A03, A04: the jet (spec §16.11: tier B's A03 bound is 1e-11) ----------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a03_jet_orders_up_to_two(cid: str) -> None:
    assert set(FLUIDS[cid]["phi_states"]) == PHI_KEYS
    assert a03_problems(cph, cid, LOW_ORDER, 1e-11) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a04_third_partials(cid: str) -> None:
    assert a03_problems(cph, cid, THIRD_ORDER, 1e-11) == []


# -- A05, A07: the six TP states -------------------------------------------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a05_values(cid: str) -> None:
    """S05 A05's bounds at §16.6's six states; the phase label is ref's (A15's at `S_dense`)."""
    assert set(FLUIDS[cid]["tp_states"]) == TP_KEYS
    assert a05_problems(PROVIDERS[cid], cid) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a07_n_derivatives_are_exactly_zero(cid: str) -> None:
    result = ev(PROVIDERS[cid], *tp(cid, "V_sup"))
    assert result.status == "ok", result.message
    for x in six(cid):
        assert result.derivatives[x][f"n_{cid}"] == 0.0, x
        assert result.derivatives[x]["T"] != 0.0, x  # control


# -- A08-A11: saturation ---------------------------------------------------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a08_psat(cid: str) -> None:
    """Psat at `sat_mid`; dPsat/dP is 0.0; dPsat/dT is judged by A11 (spec §16.10)."""
    entry = FLUIDS[cid]["saturation"]["sat_mid"]
    result = psat(PROVIDERS[cid], entry["T"])
    assert result.status == "ok", result.message
    assert abs(result.values["Psat"] / entry["Psat"] - 1.0) <= 2e-9
    assert result.derivatives["Psat"]["P"] == 0.0
    assert result.derivatives["Psat"][f"n_{cid}"] == 0.0


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a09_tsat(cid: str) -> None:
    """Tsat at `tsat_mid`; dTsat/dT is 0.0 (spec §16.10)."""
    entry = FLUIDS[cid]["tsat"]["tsat_mid"]
    result = ev(PROVIDERS[cid], band_t(cid), entry["P"], "VAPOR", ("Tsat",))
    assert result.status == "ok", result.message
    assert abs(result.values["Tsat"] / entry["Tsat"] - 1.0) <= 1e-9
    assert result.derivatives["Tsat"]["T"] == 0.0
    assert result.derivatives["Tsat"][f"n_{cid}"] == 0.0


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
@pytest.mark.parametrize("key", SAT_TEMPERATURES)
def test_a10_maxwell_on_the_providers_own_psat(cid: str, key: str) -> None:
    _, liquid, vapour = saturated_phases(PROVIDERS[cid], sat_temperature(cid, key))
    lnphi = f"lnphi_{cid}"
    assert abs(liquid[lnphi] - vapour[lnphi]) <= 1e-8
    if key == "T_mid":
        expected = FLUIDS[cid]["saturation"]["sat_mid"]["dh_vap"]
        assert abs((vapour["h"] - liquid["h"]) / expected - 1.0) <= 1e-9


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
@pytest.mark.parametrize("key", SAT_TEMPERATURES)
def test_a11_clausius_clapeyron_on_the_providers_answers(cid: str, key: str) -> None:
    sat, liquid, vapour = saturated_phases(PROVIDERS[cid], sat_temperature(cid, key))
    ratio = (vapour["s"] - liquid["s"]) / (vapour["v"] - liquid["v"])
    bound = 1e-6 if key == "T_sigma_max" else 1e-8
    assert abs(sat.derivatives["Psat"]["T"] / ratio - 1.0) <= bound


# -- A13-A16, A18: the band's answered sets and the refusal probes (codes only) --------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a13_band_answered_sets(cid: str) -> None:
    provider, t = PROVIDERS[cid], band_t(cid)
    problems = []
    for key, probe in FLUIDS[cid]["band"]["probes"].items():
        assert sorted([*probe["answered"], *probe["refused"]]) == ["LIQUID", "VAPOR"], key
        for phase in ("LIQUID", "VAPOR"):
            result = ev(provider, t, float(probe["P"]), phase, derivatives=())
            if phase in probe["refused"]:
                problem = refusal_problem(result, "unsupported", "phase_not_stable")
                problems += [f"band {key} {phase}: {problem}"] if problem else []
            elif result.status != "ok" or result.phase_signature != phase:
                problems.append(f"band {key} {phase}: {result.status} {result.message}")
    assert problems == []
    assert probe_problems(provider, cid, ("A13",)) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
@pytest.mark.parametrize("tag", ["A14", "A15", "A16", "A18"])
def test_refusal_probes(cid: str, tag: str) -> None:
    assert probe_problems(PROVIDERS[cid], cid, (tag,)) == []


# -- A17: value/derivative consistency at the six TP states (S05 §6.3) -----------------------------


def a17_worst(cid: str) -> dict[str, float]:
    worst = {}
    for name in FLUIDS[cid]["tp_states"]:
        t, p, phase = tp(cid, name)
        for wrt in ("T", "P"):
            ratios = fd_ratios(PROVIDERS[cid], cid, t, p, phase, wrt, "tp")
            worst[f"{name}-{wrt}"] = max(ratios.values())
    return worst


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a17_finite_differences(cid: str) -> None:
    worst = a17_worst(cid)
    assert max(worst.values()) <= FD_TOL, {k: v for k, v in worst.items() if v > FD_TOL}


# -- A22: the robustness grid (12 temperatures for tier B) -----------------------------------------


def a22_problems(provider: Provider) -> tuple[list[str], int, int]:
    fluid = provider._fluid
    temperatures = [fluid.t_lo + (fluid.t_hi - fluid.t_lo) * i / 11 for i in range(12)]
    temperatures[-1] = fluid.t_hi
    pressures = [10.0**k for k in range(2, 9) if 10.0**k <= fluid.p_hi]
    pressures += [fluid.p_hi] if fluid.p_hi not in pressures else []
    problems, answered = [], 0
    for t in temperatures:
        if t <= fluid.t_sigma_max:
            sat = psat(provider, t)
            problems += [f"Psat at {t}: {sat.message}"] if sat.status != "ok" else []
        for p in pressures:
            for phase in ("LIQUID", "VAPOR"):
                result = ev(provider, t, p, phase)
                if result.status != "ok":
                    code = result.message.split(":")[0]
                    if code not in ("phase_not_stable", "near_critical"):
                        problems.append(f"{phase} at {t}, {p}: {result.message}")
                    continue
                answered += 1
                if not result.derivatives["v"]["P"] < 0.0 or not result.values["cp"] > 0.0:
                    problems.append(f"{phase} at {t}, {p}: dv/dP or cp has the wrong sign")
    return problems, answered, len(temperatures) * len(pressures)


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_B)
def test_a22_robustness_grid(cid: str) -> None:
    problems, answered, states = a22_problems(PROVIDERS[cid])
    assert problems == []
    assert answered >= states  # every (T, P) answers some phase
