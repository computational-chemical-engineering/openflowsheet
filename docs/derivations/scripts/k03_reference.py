"""Fable's closed-form reference generator for the K03 solver specification.

Everything here follows from the plan §3.1 definitions and the SYN-001 derivation (§3, §5.1)
alone, evaluated with mpmath at 40 significant digits. It imports nothing from
``process_runtime`` or ``benchmarks``: the numbers it emits are the *expectations* the K03 tests
judge the solver against, so they must not come from the solver.

What it produces (``docs/derivations/K03-solver-spec.md`` §11 and §12):

* the closed-form tear residual ``R(t) = r l(F + t) - t`` and its exact Jacobian ``dR/dt`` at every
  registered tear state, where ``l(n)`` is the liquid of the isothermal-isobaric flash of ``n``
  (derivation §5.1; the derivative is the implicit derivative of the Rachford-Rice root);
* the domain classification of every registered state: the v0.0 mixer's subcooled-liquid test on
  the recycle, the flash regime, and the heater-outlet regime at 350 K;
* the one-step Newton prediction from the off-ray starts, so that "not converged after one
  iteration" is a closed-form fact and not a solver observation;
* the closed forms of the synthetic seeds (NUM-02, NUM-05, BND-01, BND-02, NUM-06);
* the structural facts the pressure-row elimination must reproduce, registered from the K02
  assembly order.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/k03_reference.py --check
    python docs/derivations/scripts/k03_reference.py --emit benchmarks/k03/reference_values.yaml

``--check`` re-derives every identity the specification claims about its own numbers and refuses
to emit when one stops holding (K03-solver-spec §12.2).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Any

import yaml
from mpmath import mp, mpf

mp.dps = 40

R_GAS = mpf("8.31446261815324")
T_REF = mpf(300)
P_REF = mpf(100000)
CP = mpf(100)
T_BOIL = (mpf(320), mpf(360), mpf(400))
L_VAP = (mpf(25000), mpf(30000), mpf(35000))
V_LIQ = (mpf("0.0001"),) * 3
NAMES = ("A", "B", "C")
FRESH = (mpf(1), mpf(1), mpf(1))
T_HEATER = mpf(350)
Vec = tuple[Any, ...]

#: The flow-scale of the tear (derivation §9) and the registered component-balance tolerance
#: (ADR 0001 D6): |R_i| <= 1e-9 + 1e-8 * 3 mol/s.
TEAR_SCALE = mpf(3)
TEAR_TOLERANCE = mpf("1e-9") + mpf("1e-8") * TEAR_SCALE


def k_value(i: int, t: Any, p: Any) -> Any:
    expo = L_VAP[i] / R_GAS * (1 / T_BOIL[i] - 1 / t) + V_LIQ[i] * (p - P_REF) / (R_GAS * t)
    return P_REF / p * mp.exp(expo)


def k_vec(t: Any, p: Any) -> Vec:
    return tuple(k_value(i, t, p) for i in range(3))


def flash(n: Sequence[Any], t: Any, p: Any) -> tuple[str, Any, Vec, Vec, Any, Any]:
    """TP flash of component flows n. Returns (regime, beta, liquid, K, sum zK, sum z/K).

    Regime by the derivation §5.1 order: liquid test, then vapor test, else two-phase.
    """
    k = k_vec(t, p)
    total = sum(n)
    if total == 0:
        raise ValueError("a dormant feed has no flash regime")
    z = [ni / total for ni in n]
    szk = sum(z[i] * k[i] for i in range(3))
    szok = sum(z[i] / k[i] for i in range(3) if z[i] > 0)
    if szk <= 1:
        return "LIQUID", mpf(0), tuple(n), k, szk, szok
    if szok <= 1:
        return "VAPOR", mpf(1), (mpf(0),) * 3, k, szk, szok

    def rr(beta: Any) -> Any:
        return sum(z[i] * (k[i] - 1) / (1 + beta * (k[i] - 1)) for i in range(3) if z[i] > 0)

    # Bisection brackets the unique root in (0, 1) (derivation §5.1); a secant polish from the
    # bisected point finishes to the working precision (bisection alone stops near 1e-31).
    beta = mp.findroot(rr, (mpf(0), mpf(1)), solver="bisect", tol=mpf(10) ** -30)
    beta = mp.findroot(rr, beta)
    liquid = tuple(n[i] * (1 - beta) / (1 + beta * (k[i] - 1)) for i in range(3))
    return "TWO_PHASE", beta, liquid, k, szk, szok


def tear_residual(t: Sequence[Any], r: Any, t_flash: Any, p: Any) -> Vec:
    n = tuple(FRESH[i] + t[i] for i in range(3))
    _, _, liquid, _, _, _ = flash(n, t_flash, p)
    return tuple(r * liquid[i] - t[i] for i in range(3))


def tear_jacobian(t: Sequence[Any], r: Any, t_flash: Any, p: Any) -> tuple[str, Any]:
    """Exact dR/dt: the implicit derivative of the Rachford-Rice liquid map.

    Two-phase: l_i = n_i (1 - beta)/D_i with D_i = 1 + beta (K_i - 1) and beta the RR root, so
        dl_i/dn_j = delta_ij (1 - beta)/D_i - n_i K_i / D_i^2 * dbeta/dn_j,
        dbeta/dn_j = [(K_j - 1)/D_j] / S,  S = sum_k n_k (K_k - 1)^2 / D_k^2.
    Liquid: l = n, so dR/dt = (r - 1) I. Vapor: l = 0, so dR/dt = -I.
    """
    n = tuple(FRESH[i] + t[i] for i in range(3))
    regime, beta, _, k, _, _ = flash(n, t_flash, p)
    jac = mp.matrix(3, 3)
    if regime == "LIQUID":
        for i in range(3):
            jac[i, i] = r - 1
        return regime, jac
    if regime == "VAPOR":
        for i in range(3):
            jac[i, i] = mpf(-1)
        return regime, jac
    d = [1 + beta * (k[i] - 1) for i in range(3)]
    s = sum(n[i] * (k[i] - 1) ** 2 / d[i] ** 2 for i in range(3))
    for i in range(3):
        for j in range(3):
            dbeta = ((k[j] - 1) / d[j]) / s
            dl = (1 if i == j else 0) * (1 - beta) / d[i] - n[i] * k[i] / d[i] ** 2 * dbeta
            jac[i, j] = r * dl - (1 if i == j else 0)
    return regime, jac


def tear_jacobian_numeric(t: Sequence[Any], r: Any, t_flash: Any, p: Any) -> Any:
    """Central differences of the closed-form residual at 40 digits: a check on the algebra."""
    jac = mp.matrix(3, 3)
    h = mpf(10) ** -15
    for j in range(3):
        for sign in (1, -1):
            tt = list(t)
            tt[j] += sign * h
            res = tear_residual(tt, r, t_flash, p)
            for i in range(3):
                jac[i, j] += sign * res[i] / (2 * h)
    return jac


def mixer_margin(t: Sequence[Any], t_flash: Any, p: Any) -> Any:
    """1 - sum_i z_i K_i(T_f, P) of the recycle: > 0 subcooled liquid (v0.0 mixer accepts)."""
    total = sum(t)
    if total == 0:
        return mpf(1)  # dormant: accepted trivially (ADR 0001 D3.4)
    k = k_vec(t_flash, p)
    return 1 - sum(t[i] * k[i] for i in range(3)) / total


def reference_recycle(r: Any, t_flash: Any, p: Any) -> Vec:
    """t* = r L x, L = F_tot (1 - beta)/(1 - r): one flash of the fresh feed (derivation §5.1)."""
    regime, beta, liquid, _, _, _ = flash(FRESH, t_flash, p)
    return tuple(r * liquid[i] / (1 - r) for i in range(3))


def s(x: Any, digits: int = 20) -> str:
    """20 significant digits; a magnitude below 1e-30 is an exact zero of the closed forms.

    At 40 working digits a quantity that vanishes identically (R at t*, the mixer margin on the
    ray) comes out as rounding noise near 1e-40 whose bytes depend on the order of arithmetic.
    Printing it as 0 keeps the emitted file a function of the mathematics, not of the code path.
    """
    if abs(x) < mpf(10) ** -30:
        return "0.0"
    return str(mp.nstr(x, digits))


def vec(v: Sequence[Any]) -> list[str]:
    return [s(x) for x in v]


def mat(m: Any) -> list[list[str]]:
    return [[s(m[i, j]) for j in range(3)] for i in range(3)]


# ------------------------------------------------------------------ registered states
VARIANTS = {
    "SYN-001-nominal": (mpf("0.5"), mpf(360)),
    "SYN-001-once-through": (mpf(0), mpf(360)),
    "SYN-001-high-recycle": (mpf("0.95"), mpf(360)),
    "SYN-001-all-liquid-310K": (mpf("0.5"), mpf(310)),
    "SYN-001-all-vapor-420K": (mpf("0.5"), mpf(420)),
}
OFF_A = (mpf("0.1"), mpf("0.8"), mpf("1.2"))
OFF_B = (mpf("0.05"), mpf("0.1"), mpf("4.0"))
FD_DELTA = mpf("1e-5")  # FD oracle step: h = FD_DELTA * TEAR_SCALE per component

#: Structural facts of the K02 assembly order (`Syn001Flowsheet.spec()`), registered here so
#: the implementation's structural analysis is judged against a stated expectation. They are
#: NOT computed by this script (it has no access to the model); a change in K02's assembly
#: order or in a pressure-row statement must be re-derived by hand and re-registered.
PRESSURE_ELIMINATION = {
    "rule": "graph-cycle rule of K03-solver-spec §5.2, rows visited in assembled order",
    "eliminated_rows": [
        {
            "row_id": "U-FLASH:FLASH-P:inlet",
            "equals": [
                ["U-FEED:FEED-P", 1],
                ["U-MIX:MIX-pressure:0", -1],
                ["U-HEAT:HEAT-pressure", 1],
            ],
            "constant_mismatch_Pa_when_feed_and_flash_pressures_equal": "0",
        },
        {
            "row_id": "U-SPLIT:SPLIT-P:recycle",
            "equals": [
                ["U-FEED:FEED-P", 1],
                ["U-MIX:MIX-pressure:0", -1],
                ["U-MIX:MIX-pressure:1", 1],
                ["U-FLASH:FLASH-P:liquid", -1],
            ],
            "constant_mismatch_Pa_when_feed_and_flash_pressures_equal": "0",
        },
    ],
    "inconsistent_state": {
        "feed_pressure_Pa": "100000",
        "flash_pressure_Pa": "150000",
        "constant_mismatch_Pa": "-50000",
        "pressure_tolerance_Pa": "0.01",
        "expected_outcome": "SPECIFICATION_CONFLICT",
    },
    "retained_inner_rows": 44,
    "inner_variables": 44,
}


def state_record(label: str, t: Vec, r: Any, t_flash: Any, p: Any, why: str) -> dict[str, Any]:
    n = tuple(FRESH[i] + t[i] for i in range(3))
    regime, beta, liquid, k, szk, szok = flash(n, t_flash, p)
    heat_regime, beta_h, _, _, szk_h, szok_h = flash(n, T_HEATER, p)
    res = tear_residual(t, r, t_flash, p)
    jreg, jac = tear_jacobian(t, r, t_flash, p)
    margin = mixer_margin(t, t_flash, p)
    rec: dict[str, Any] = {
        "label": label,
        "why_registered": why,
        "t_mol_per_s": vec(t),
        "mixer_margin_1_minus_sum_zK_at_T_flash": s(margin),
        "mixer_accepts": bool(margin >= 0),
        "flash_regime": regime,
        "flash_sum_zK": s(szk),
        "flash_sum_z_over_K": s(szok),
        "flash_beta": s(beta),
        "heater_outlet_regime_at_350K": heat_regime,
        "heater_outlet_sum_zK_at_350K": s(szk_h),
        "R_mol_per_s": vec(res),
        "R_inf_mol_per_s": s(max(abs(x) for x in res)),
        "merit_scaled": s(sum((x / TEAR_SCALE) ** 2 for x in res) / 2),
        "dR_dt": mat(jac),
        "dR_dt_regime": jreg,
    }
    if margin >= 0 and regime == "TWO_PHASE":
        # One exact Newton step and the residual it leaves: closed-form "not affine off the ray".
        rhs = mp.matrix([-x for x in res])
        step = mp.lu_solve(jac, rhs)
        t1 = tuple(t[i] + step[i] for i in range(3))
        res1 = tear_residual(t1, r, t_flash, p)
        rec["newton_step_full"] = vec(step)
        rec["newton_step_target_t1"] = vec(t1)
        rec["t1_mixer_margin"] = s(mixer_margin(t1, t_flash, p))
        rec["t1_flash_regime"] = flash(tuple(FRESH[i] + t1[i] for i in range(3)), t_flash, p)[0]
        rec["R_at_t1_inf_mol_per_s"] = s(max(abs(x) for x in res1))
        rec["converged_after_one_step"] = bool(max(abs(x) for x in res1) <= TEAR_TOLERANCE)
    if regime == "LIQUID" and r < 1:
        fixed = tuple(r * FRESH[i] / (1 - r) for i in range(3))
        rec["liquid_regime_newton_target_rF_over_1_minus_r"] = vec(fixed)
        rec["liquid_regime_target_mixer_margin"] = s(mixer_margin(fixed, t_flash, p))
        rec["liquid_regime_target_mixer_accepts"] = bool(mixer_margin(fixed, t_flash, p) >= 0)
    return rec


def fd_stencil_checks(t: Vec, r: Any, t_flash: Any, p: Any) -> list[str]:
    """Every point of the central stencil at t must be a valid, in-domain tear."""
    h = FD_DELTA * TEAR_SCALE
    passed = []
    for j in range(3):
        for sign in (1, -1):
            tt = list(t)
            tt[j] += sign * h
            assert tt[j] >= 0, f"stencil point {j} {sign:+d} leaves the bound t >= 0"
            assert mixer_margin(tt, t_flash, p) > 0, (
                f"stencil point {j} {sign:+d} leaves the domain"
            )
            assert flash(tuple(FRESH[i] + tt[i] for i in range(3)), t_flash, p)[0] == "TWO_PHASE"
            passed.append(f"stencil {NAMES[j]}{sign:+d}: t={vec(tt)} in domain, two-phase")
    return passed


def build() -> dict[str, Any]:
    checks: list[str] = []
    states: dict[str, Any] = {}

    for case_id, (r, t_flash) in VARIANTS.items():
        p = P_REF
        tstar = reference_recycle(r, t_flash, p)
        entry: dict[str, Any] = {"r": s(r, 3), "T_flash_K": s(t_flash, 5), "P_Pa": "100000"}
        # --- the reference recycle t* and the identities at it
        rs = state_record(
            "t_star", tstar, r, t_flash, p, "the registered solution; R must vanish here"
        )
        res = tear_residual(tstar, r, t_flash, p)
        assert max(abs(x) for x in res) < mpf(10) ** -35, case_id
        checks.append(f"{case_id}: R(t*) = 0 to 1e-35")
        _, jstar = tear_jacobian(tstar, r, t_flash, p)
        if r > 0 and rs["flash_regime"] == "TWO_PHASE":
            for i in range(3):
                lhs = sum(jstar[i, j] * tstar[j] for j in range(3))
                assert abs(lhs - (-(1 - r) * tstar[i])) < mpf(10) ** -35, case_id
            checks.append(f"{case_id}: dR/dt(t*) t* = -(1-r) t* to 1e-35 (affine-ray relation)")
            rs["eigenvector_t_star_eigenvalue"] = s(-(1 - r))
        entry["t_star"] = rs
        # --- initializer candidates (spec §8)
        v1 = tuple(r * f for f in FRESH)
        g0 = tuple((1 - r) * x for x in tstar)  # G(0) = (1-r) t* (K02 affine-ray relation)
        entry["retired_guess_rF"] = (
            state_record(
                "retired P01 guess r*F (SYN-001-inadmissible-guess at the nominal variant)",
                v1,
                r,
                t_flash,
                p,
                "retired as an initializer (register R-014); registered at the nominal variant as "
                "the user guess of the adversarial case SYN-001-inadmissible-guess, which exists "
                "to exercise the §7.4 rejection path; recorded at the other variants for the "
                "domain classification only",
            )
            if sum(v1) > 0
            else {
                "label": "retired P01 guess r*F",
                "t_mol_per_s": vec(v1),
                "mixer_accepts": True,
                "why_registered": "dormant recycle at r = 0: accepted trivially; coincides with t*",
            }
        )
        entry["init_v2_G0"] = (
            state_record(
                "SYN-001-tear-init-v2",
                g0,
                r,
                t_flash,
                p,
                "the registered initializer (derivation §9): one traversal from the dormant "
                "recycle, r x liquid of the flash of F; equals (1-r) t*",
            )
            if sum(g0) > 0
            else {
                "label": "SYN-001-tear-init-v2 (the registered initializer)",
                "t_mol_per_s": vec(g0),
                "mixer_accepts": True,
                "why_registered": "G(0) is dormant here and coincides with t*",
            }
        )
        # executable: G(0) = (1-r) t* is the K02-measured affine relation, re-derived here
        n0 = FRESH
        _, _, liq0, _, _, _ = flash(n0, t_flash, p)
        for i in range(3):
            assert abs(r * liq0[i] - g0[i]) < mpf(10) ** -35
        checks.append(f"{case_id}: G(0) = r * liquid(flash(F)) = (1-r) t* to 1e-35")
        # --- off-ray starts (only meaningful where the mixer domain admits them)
        if t_flash == 360:
            entry["off_a"] = state_record(
                "OFF-A",
                OFF_A,
                r,
                t_flash,
                p,
                "in-domain, off the ray, all components nonzero, flash two-phase at the start: the "
                "genuinely nonlinear tear Newton with no phase change",
            )
            entry["off_b"] = state_record(
                "OFF-B",
                OFF_B,
                r,
                t_flash,
                p,
                "in-domain, off the ray, flash all-liquid at the start while the solution is "
                "two-phase: the phase-change restart",
            )
            # distinctness: off-ray means not proportional to t*
            for lab, off in (("OFF-A", OFF_A), ("OFF-B", OFF_B)):
                if r > 0:
                    cross = max(
                        abs(off[i] * tstar[j] - off[j] * tstar[i])
                        for i in range(3)
                        for j in range(3)
                    )
                    assert cross > mpf("0.05"), lab
                    checks.append(
                        f"{case_id}: {lab} is off the ray (max cross product {s(cross, 6)} > 0.05)"
                    )
            assert entry["off_a"]["flash_regime"] == "TWO_PHASE" and entry["off_a"]["mixer_accepts"]
            assert entry["off_b"]["flash_regime"] == "LIQUID" and entry["off_b"]["mixer_accepts"]
            checks.append(f"{case_id}: OFF-A two-phase, in-domain; OFF-B liquid-regime, in-domain")
            if r > 0:
                assert not entry["off_b"]["liquid_regime_target_mixer_accepts"]
                checks.append(
                    f"{case_id}: liquid-regime Newton target rF/(1-r) refused by the mixer"
                )
                assert not entry["off_a"]["converged_after_one_step"]
                left = entry["off_a"]["R_at_t1_inf_mol_per_s"][:10]
                checks.append(
                    f"{case_id}: one Newton step from OFF-A leaves |R| = {left} > tolerance"
                )
            else:
                assert entry["off_a"]["converged_after_one_step"]
                assert all(mpf(v) == 0 for v in entry["off_a"]["newton_step_target_t1"])
                checks.append(f"{case_id}: one Newton step from OFF-A lands exactly on t* = 0")
            # closed-form vs numeric derivative at OFF-A (the algebra check)
            _, jc = tear_jacobian(OFF_A, r, t_flash, p)
            jn = tear_jacobian_numeric(OFF_A, r, t_flash, p)
            err = max(abs(jc[i, j] - jn[i, j]) for i in range(3) for j in range(3))
            assert err < mpf(10) ** -25, err
            checks.append(
                f"{case_id}: closed-form dR/dt equals 40-digit central differences at OFF-A "
                f"to {s(err, 3)}"
            )
            # every entry of the two-phase Jacobian at OFF-A is a real number and the matrix has
            # no two equal rows (a permuted index changes it)
            rows = [tuple(jc[i, j] for j in range(3)) for i in range(3)]
            assert len({tuple(s(x, 12) for x in row) for row in rows}) == 3
            checks.append(f"{case_id}: the three rows of dR/dt at OFF-A are pairwise distinct")
            entry["fd_oracle_stencil_checks_at_off_a"] = fd_stencil_checks(OFF_A, r, t_flash, p)
        else:
            # single-phase variants: R is globally affine; the Jacobian is constant
            reg, jac = tear_jacobian(v1 if sum(v1) > 0 else tstar, r, t_flash, p)
            expected = (r - 1) if t_flash == 310 else mpf(-1)
            for i in range(3):
                for j in range(3):
                    assert jac[i, j] == (expected if i == j else 0)
            checks.append(
                f"{case_id}: dR/dt is exactly {s(expected, 4)} I ({reg} on the whole domain)"
            )
            entry["global_affine_note"] = (
                "the flash is single-phase for every composition at this T_f (pure A at 310 K has "
                "K_A < 1; pure C at 420 K has K_C > 1), so R is affine on the whole domain and "
                "Newton converges in one step from any admissible start"
            )
        states[case_id] = entry

    # --- a Jacobian-only state where no K_i equals 1, so no entry of dR/dt vanishes by accident
    # (at 360 K, K_B = 1 exactly makes dbeta/dn_B = 0 and hence (A,B) = (C,B) = 0 in every
    # two-phase Jacobian above). Nothing is solved here; the Schur complement is judged.
    r365, t365 = mpf("0.5"), mpf(365)
    rec365 = state_record(
        "JAC-365K-OFF-A",
        OFF_A,
        r365,
        t365,
        P_REF,
        "Jacobian-only: flash two-phase at 365 K with every K_i != 1, so all nine entries of "
        "dR/dt are nonzero and an accidental zero cannot hide a dropped term",
    )
    assert rec365["mixer_accepts"] and rec365["flash_regime"] == "TWO_PHASE"
    _, j365 = tear_jacobian(OFF_A, r365, t365, P_REF)
    smallest = min(abs(j365[i, j]) for i in range(3) for j in range(3))
    assert smallest > mpf("1e-3"), smallest
    checks.append(
        f"JAC-365K-OFF-A: in-domain, two-phase, smallest |dR/dt entry| = {s(smallest, 6)} > 1e-3"
    )
    k365 = k_vec(t365, P_REF)
    assert min(abs(k - 1) for k in k365) > mpf("0.05")
    checks.append(f"365 K: every |K_i - 1| > 0.05 (K = {vec(k365)})")
    rec365["fd_oracle_stencil_checks"] = fd_stencil_checks(OFF_A, r365, t365, P_REF)
    states["JAC-365K"] = {
        "r": "0.5",
        "T_flash_K": "365",
        "P_Pa": "100000",
        "off_a": rec365,
        "note": "not a registered solve; the tear Jacobian is asserted here only",
    }

    # --- the mixer domain at 420 K admits no flowing recycle at all
    k420 = k_vec(mpf(420), P_REF)
    assert min(k420) > 1
    checks.append(
        f"420 K: every K_i > 1 (min {s(min(k420), 6)}), so no flowing recycle is a subcooled "
        "liquid: t* = 0 is the only admissible tear"
    )

    # --- synthetic seeds
    seeds = {
        "NUM-02-linear-recycle": {
            "residual": "R(t) = f + r t - t, f = (1, 1, 1)",
            "jacobian": "(r - 1) I",
            "solution": {"r=0.5": vec((mpf(2),) * 3), "r=0.95": vec((mpf(20),) * 3)},
            "start": vec(FRESH),
            "one_step_exact": True,
            "r=1": {
                "jacobian": "0 (exactly singular)",
                "expected_outcome": "LINEAR_SOLVE_FAILED",
                "residual_at_start": vec(FRESH),
            },
        },
        "NUM-01-known-root": {
            "residual": "R(x) = x - 2",
            "start": "2",
            "expected": "CONVERGED at iteration 0; no Jacobian, no factorization",
        },
        "NUM-05-small-step-stagnation": {
            "residual": "R(x) = x^2 + c, c = 0.01",
            "start": "1",
            "minimum_of_abs_R": "0.01",
            "expected_outcome": "STAGNATION",
            "final_abs_R_interval": ["0.01", "0.0101"],
            "note": "R has no real root; the merit function has a strict positive minimum at x = 0",
        },
        "BND-01-exact-bound-landing": {
            "residual": "R(x) = ln(1 + x) - 1/2, bound x >= 0",
            "start": "4",
            "root": s(mp.e ** mpf("0.5") - 1),
            "first_newton_direction": s(-(mp.log(5) - mpf("0.5")) * 5),
            "alpha_max_first_step": s(4 / (5 * (mp.log(5) - mpf("0.5")))),
            "first_accepted_iterate": "0 exactly (bit-exact +0.0)",
            "note": "the full step from 4 crosses the bound; the line search lands exactly on it",
        },
        "BND-02-bound-blocked": {
            "residual": "R(x) = x + 1, bound x >= 0",
            "start": "0",
            "expected_outcome": "BOUND_BLOCKED",
        },
        "NUM-06-invalid-trial-wall": {
            "residual": "R(x) = x - 5, provider-like domain x <= 3",
            "start": "3",
            "expected_outcome": "LINE_SEARCH_FAILED",
            "rejections": "21 trials, alpha = 1, 1/2, ..., 2^-20, every one invalid_trial_state",
            "final_abs_R": "2",
        },
    }
    assert abs(mp.log(1 + (mp.e ** mpf("0.5") - 1)) - mpf("0.5")) < mpf(10) ** -38
    checks.append("BND-01: ln(1 + (e^0.5 - 1)) = 1/2 to 1e-38")

    return {
        "generated_by": (
            "Fable 5.1, mpmath 1.3.0 at 40 significant digits, from plan §3.1 definitions and "
            "derivation §5.1 only"
        ),
        "specification": "docs/derivations/K03-solver-spec.md",
        "independence": (
            "closed-form expectations; no solver, oracle or process_runtime code was used. "
            "The pressure_elimination block is a registered structural fact, not a computation."
        ),
        "tear_scale_mol_per_s": s(TEAR_SCALE, 3),
        "tear_tolerance_mol_per_s": s(TEAR_TOLERANCE, 5),
        "fd_oracle": {
            "stencil": "central two-point per component",
            "delta_relative_to_scale": s(FD_DELTA, 3),
            "h_mol_per_s": s(FD_DELTA * TEAR_SCALE, 3),
            "registered_state": "OFF-A of every 360 K variant",
            "floors_measured_2026_09_21": {
                "note": (
                    "max |FD - closed| at OFF-A, nominal, through the K02 traversal; error is "
                    "quadratic in delta down to 1e-5, roundoff appears at 1e-6"
                ),
                "delta=1e-2": "3.0e-5",
                "delta=1e-3": "3.0e-7",
                "delta=1e-4": "3.0e-9",
                "delta=1e-5": "3.3e-11",
                "delta=1e-6": "6.9e-11",
                "delta=1e-7": "3.7e-10",
            },
            "tolerance": "1e-9 absolute on every entry (30x above the measured floor at 1e-5)",
        },
        "K_at_P_r": {f"{int(t)}K": vec(k_vec(mpf(t), P_REF)) for t in (310, 350, 360, 365, 420)},
        "states": states,
        "synthetic_seeds": seeds,
        "pressure_elimination": PRESSURE_ELIMINATION,
        "floors_measured_2026_09_21": {
            "note": (
                "measured by Fable on the K02 flowsheet through the CasADi backend and SciPy "
                "SuperLU; regression floors, not closed forms"
            ),
            "schur_vs_closed_form_max_abs": "5.3e-15",
            "inner_consistency_scaled_max": "2.0e-15",
            "linear_residual_normalized_max": "1.3e-16",
            "u_diagonal_min_over_max_min": "7.1e-3",
            "kappa2_scaled_inner_block_range": "28 to 1440",
            "kappa2_unscaled_inner_block_range": "6.7e9 to 1.1e11",
        },
        "checks_passed": checks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="re-derive every identity and print the key numbers"
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not (args.check or args.emit):
        parser.error("choose --check and/or --emit PATH")
    ref = build()
    if args.check:
        for line in ref["checks_passed"]:
            print("check passed:", line)
        nom = ref["states"]["SYN-001-nominal"]
        print("nominal dR/dt at t*:", nom["t_star"]["dR_dt"])
        print("nominal dR/dt at OFF-A:", nom["off_a"]["dR_dt"])
        print("nominal OFF-A one step leaves |R| =", nom["off_a"]["R_at_t1_inf_mol_per_s"])
        target = nom["off_b"]["liquid_regime_newton_target_rF_over_1_minus_r"]
        margin = nom["off_b"]["liquid_regime_target_mixer_margin"]
        print("nominal OFF-B liquid-regime target:", target, "mixer margin", margin)
    if args.emit:
        with open(args.emit, "w", encoding="utf-8") as handle:
            yaml.safe_dump(ref, handle, sort_keys=False, width=110, allow_unicode=True)
        print("wrote", args.emit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
