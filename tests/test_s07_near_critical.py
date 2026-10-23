"""S07 near-critical saturation and the (T_σ,max, T_c) strip: the gates of design note
`docs/design/S07-near-critical-saturation.md` (§6), as assertions N1-N3, N5 and N6 (S07 Amendment 3
numbers them; G4 and G6 belong to the generator, WO-S07-NC4).

- N1 (G1): the saturation exists at T_σ,max and at θ = 1 − T/T_c ∈ {2e-4, 1e-4, 5e-5} for all 123.
- N2 (G2): where the Newton from the ancillary seeds converges, the answer is bitwise that Newton's
  and the fallback is never entered.
- N3 (G3): where both converge, the fallback forced from the same T agrees with the plain root
  within the Maxwell root's double-precision floor.
- N5 (G5): every strip state outside the box is answered, mechanically stable, and continuous
  across T_c.
- N6 (G7(c), (d)): S05 adopts the strip rule (D5), and its own saturation needs no fallback.

The dense coverage scan (G1 over 40 points per decade, G8's cost) is
`docs/derivations/scripts/s07_measurements/nc_scan.py`, a measurement with a one-line summary.
"""

from __future__ import annotations

import math

import pytest
from s07_coolprop_support import require_coolprop
from test_s07_coolprop import CONTEXT, ev

from openflowsheet.thermo import Phase, PropertyRequest, StreamState
from openflowsheet.thermo import _coolprop_heos_fluids as table
from openflowsheet.thermo import coolprop_heos as cph
from openflowsheet.thermo import iapws95 as w

ALL = [row["id"] for row in table.FLUIDS]
PROVIDERS = {cid: cph.CoolPropHeosProvider(cid) for cid in ALL}
#: N1-N3's θ grid (design note §6 G1: the tier-B points; N3 adds θ = 1e-2 for its far bound).
N1_THETAS = (2e-4, 1e-4, 5e-5)
N3_THETAS = (1e-2, *N1_THETAS)
#: N5's strip θ grid (design note §6 G5).
N5_THETAS = (1.9999e-4, 1e-4, 5e-5, 1e-5, 1e-6, 1e-8, 1e-12)
#: N3's bounds (spec §19.2, A47; G3 re-set by R-626), relative: densities 1e-11 for θ ≥ 1e-2 and
#: 3e-8 for θ_min ≤ θ < 1e-2 (two accepted roots differ by up to about 2√ε at the floor); p_σ
#: 1e-12 and 1e-10 (it follows ρ'' through (k''/Z'')·|Δρ''|/ρ'').
N3_FAR, N3_NEAR = 1e-11, 3e-8
N3_PRESSURE_FAR, N3_PRESSURE_NEAR = 1e-12, 1e-10
#: N5's continuity bound at T_c (design note §6 G5).
CONTINUITY = 1e-8


@pytest.fixture
def coolprop() -> None:
    require_coolprop()


needs_coolprop = pytest.mark.usefixtures("coolprop")


def provider(cid: str) -> cph.CoolPropHeosProvider:
    instance = PROVIDERS[cid]
    assert instance._guard() is None
    return instance


def at_theta(fluid: cph._Fluid, theta: float) -> float:
    """T_c(1 − θ), moved down to the nearest double whose computed θ is not below it (T_c(1 − 5e-5)
    computes θ < 5e-5 by one rounding for every fluid, outside the fallback's domain)."""
    t = fluid.t_c * (1.0 - theta)
    while 1.0 - t / fluid.t_c < theta:
        t = math.nextafter(t, 0.0)
    return t


def temperatures(fluid: cph._Fluid) -> list[float]:
    return [fluid.t_sigma_max, *(at_theta(fluid, theta) for theta in N1_THETAS)]


def plain(instance: cph.CoolPropHeosProvider, t: float) -> cph._Saturation | None:
    """The Newton from the ancillary seeds alone."""
    fluid, seeds = instance._fluid, instance._seeds
    assert seeds is not None
    rho_l, rho_v = seeds.rho_l(t, fluid.t_c), seeds.rho_v(t, fluid.t_c)
    if not (cph._usable(rho_l) and cph._usable(rho_v)):
        return None
    return instance._maxwell_newton(t, rho_l / fluid.rho_red, rho_v / fluid.rho_red)


@needs_coolprop
@pytest.mark.parametrize("cid", ALL)
def test_n1_n2_the_saturation_exists_and_a_plain_root_is_kept(
    cid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = provider(cid)
    entered: list[float] = []
    fallback = instance._maxwell_fallback

    def counted(t: float, seed_v: float) -> cph._Saturation | None:
        entered.append(t)
        return fallback(t, seed_v)

    monkeypatch.setattr(instance, "_maxwell_fallback", counted)
    for t in temperatures(instance._fluid):
        entered.clear()
        reference = plain(instance, t)
        solved = instance._solve_saturation(t)
        assert solved is not None, f"N1: no saturation at {t!r} K"
        assert solved.rho_l > instance._fluid.rho_c > solved.rho_v > 0.0
        if reference is not None:
            assert not entered, f"N2: the fallback ran at {t!r} K where the Newton converges"
            assert repr(solved) == repr(reference), f"N2: {solved} != {reference}"
        else:
            assert entered == [t]


def n3_pairs(cid: str) -> list[tuple[float, cph._Saturation, cph._Saturation]]:
    instance = provider(cid)
    pairs = []
    for theta in N3_THETAS:
        t = at_theta(instance._fluid, theta)
        reference = plain(instance, t)
        if reference is None:
            continue
        assert instance._seeds is not None
        forced = instance._maxwell_fallback(t, instance._seeds.rho_v(t, instance._fluid.t_c))
        if forced is not None:
            pairs.append((theta, reference, forced))
    return pairs


@needs_coolprop
@pytest.mark.parametrize("cid", ALL)
def test_n3_the_fallback_agrees_with_the_plain_root_densities(cid: str) -> None:
    for theta, reference, forced in n3_pairs(cid):
        bound = N3_FAR if theta >= 1e-2 else N3_NEAR
        assert abs(forced.rho_l - reference.rho_l) <= bound * reference.rho_l, theta
        assert abs(forced.rho_v - reference.rho_v) <= bound * reference.rho_v, theta


@needs_coolprop
@pytest.mark.parametrize("cid", ALL)
def test_n3_the_fallback_agrees_with_the_plain_root_pressure(cid: str) -> None:
    for theta, reference, forced in n3_pairs(cid):
        bound = N3_PRESSURE_FAR if theta >= 1e-2 else N3_PRESSURE_NEAR
        difference = abs(forced.pressure - reference.pressure) / reference.pressure
        assert difference <= bound, (theta, difference)


def strip_states(fluid: cph._Fluid) -> list[tuple[Phase, float]]:
    """Design note M6: just outside the box and at the domain's ends, each on its labelled side."""
    p_low, p_high = fluid.nc_p
    return [
        ("LIQUID", p_high * (1.0 + 1e-12)),
        ("LIQUID", fluid.p_hi),
        ("VAPOR", p_low * (1.0 - 1e-12)),
        ("VAPOR", fluid.p_lo),
    ]


def stable_answer(instance: cph.CoolPropHeosProvider, t: float, p: float, phase: Phase) -> float:
    result = ev(instance, t, p, phase, ("v", "cp"), ("T", "P"))
    assert result.status == "ok", f"{phase} at {t!r} K, {p!r} Pa: {result.message}"
    assert result.derivatives["v"]["P"] < 0.0
    assert result.values["cp"] > 0.0
    return result.values["v"]


@needs_coolprop
@pytest.mark.parametrize("cid", ALL)
def test_n5_the_strip_is_answered_and_continuous_at_t_c(cid: str) -> None:
    instance = provider(cid)
    fluid = instance._fluid
    for theta in N5_THETAS:
        t = fluid.t_c * (1.0 - theta)
        assert fluid.t_sigma_max < t < fluid.t_c
        for phase, p in strip_states(fluid):
            stable_answer(instance, t, p, phase)
    t_below = fluid.t_c * (1.0 - 1e-12)
    ends: tuple[tuple[Phase, float], ...] = (("LIQUID", fluid.p_hi), ("VAPOR", fluid.p_lo))
    for phase, p in ends:
        v_below = stable_answer(instance, t_below, p, phase)
        v_at = stable_answer(instance, fluid.t_c, p, "VAPOR")
        assert abs(v_below - v_at) <= CONTINUITY * v_at, (phase, v_below, v_at)


# -- N6: S05 (`iapws95.py`) ------------------------------------------------------------------------

S05 = w.Iapws95Provider()
#: Design note M7: strip temperatures at which the S05 saturation does not converge, at a liquid
#: and a vapour pressure outside the box [22.0, 22.2] MPa.
S05_STRIP_T = (647.0954, 647.0959, 647.09599)
S05_STRIP_STATES: tuple[tuple[Phase, float], ...] = (("LIQUID", 25.0e6), ("VAPOR", 20.0e6))


def s05_v(t: float, p: float, phase: Phase) -> float:
    state = StreamState(n=(1.0,), temperature=t, pressure=p)
    request = PropertyRequest(state, phase, ("v", "cp"), ("T", "P"))
    result = S05.evaluate_phase(request, CONTEXT)
    assert result.status == "ok", f"{phase} at {t!r} K, {p!r} Pa: {result.message}"
    assert result.derivatives["v"]["P"] < 0.0
    assert result.values["cp"] > 0.0
    return result.values["v"]


def test_n6_the_s05_strip_without_a_saturation_is_answered_and_continuous_at_t_c() -> None:
    for t in S05_STRIP_T:
        assert w._saturation(t) is None, t
        for phase, p in S05_STRIP_STATES:
            s05_v(t, p, phase)
    for phase, p in S05_STRIP_STATES:
        v_below = s05_v(w.T_C * (1.0 - 1e-12), p, phase)
        v_at = s05_v(w.T_C, p, "VAPOR")
        assert abs(v_below - v_at) <= CONTINUITY * v_at, (phase, v_below, v_at)


def test_n6_the_s05_saturation_converges_on_its_whole_range() -> None:
    """D5's premise: S05's Newton from the IAPWS ancillaries needs no fallback below 647.0 K."""
    grid = [273.16 + 0.05 * i for i in range(int((647.0 - 273.16) / 0.05) + 1)]
    grid = [t for t in grid if t <= w.T_SIGMA_MAX] + [w.T_SIGMA_MAX]
    failed = [t for t in grid if w._saturation(t) is None]
    assert not failed, failed[:5]
