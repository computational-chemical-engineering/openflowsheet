"""Closed-form reference generator for T03, the general phase-attempt contract (ADR 0005).

Everything here follows from definitions: the SYN-001 thermodynamics of
``docs/derivations/SYN-001.md`` (through the sibling closed-form scripts ``syn001_reference.py``,
``k03_reference.py`` and ``t02_reference.py``), the lifted equilibrium-oriented rows of the A02
region (T02-recycle-spec §6.1, §7.3), K03's Newton core as specified (K03-solver-spec §5), and the
phase-attempt contract of ``docs/derivations/T03-phase-controller-spec.md`` §4, which is *simulated
here at 40 significant digits from its own statement*. It imports nothing from
``process_runtime`` or ``benchmarks``: the numbers it emits are the expectations the T03 tests
judge the implementation against, so they must not come from it.

**Why a reduced block is exact (T03 spec §6.1).** In the A02 region the rows of the recycle loop
do not read any of the eleven heater-side variables (``S3.T``, the lifted split of S3,
``U-HEAT.Q``, ``U-FLASH.Q``): the flash is isothermal at 360 K and reads only ``S3.n``. The
region Jacobian is therefore block lower-triangular, and at the sequential pre-solve's state the
loop rows are satisfied, so every Newton direction has a loop part that vanishes and a heater part
that is the Newton direction of the eleven-row block alone. The block is simulated here; the loop
enters as the constants ``S3.n``, ``H_S2`` and the flash products' enthalpy.

Three classes of value are emitted and labelled as such in the YAML:

* ``closed_form`` -- phase boundaries, branch roots, duties, region shapes, Rachford-Rice splits
  at registered temperatures, solution-error bounds of the manufactured recycle.
* ``policy_simulation`` -- the trajectory of the registered contract on the registered cases,
  evaluated in 40-digit arithmetic. An implementation of the same contract must reproduce it; a
  different contract will not (the ablations below show which rule each assertion depends on).
* ``measured`` -- the same twin rerun in 53-bit arithmetic, used only to argue the tolerances.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/t03_reference.py --check
    python docs/derivations/scripts/t03_reference.py --emit benchmarks/t03/reference_values.yaml

``--check`` re-derives every identity the specification claims about its own numbers and refuses
to emit when one stops holding (T03 spec §12.2). ``--emit`` is byte-reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from mpmath import eye, lu_solve, matrix, mp, mpf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import syn001_reference as p01  # noqa: E402  (closed-form SYN-001 thermodynamics, mpmath)
import t02_reference as t02  # noqa: E402  (closed-form A02 sweep and the T02 recycle twin)

mp.dps = 40

# --------------------------------------------------------------------------------------------
# 1. Registered constants (K03 §5.9, T02 §5.10, T03 §4.9) -- none of them new except DELTA_ROOT
# --------------------------------------------------------------------------------------------

ARMIJO_C = mpf("1e-4")
STEP_HALVINGS_MAX = 20
STAGNATION_WINDOW = 5
STAGNATION_RATIO = mpf("0.99")
MAX_ITERATIONS = 50
MAX_ATTEMPTS = 5
PHASE_WALL_PATIENCE = 2
ADMISSIBILITY_EPSILON = mpf("1e-12")
T_DOMAIN = (mpf(280), mpf(440))  # the SYN-001 provider's temperature domain, K
DELTA_ROOT = mpf("1e-4")  # T03 §8.3: root comparison, scaled infinity norm

P_R = mpf(100000)
CP = p01.CP
L_VAP = p01.L_VAP
COMPONENTS = ("A", "B", "C")

#: ADR 0001 D6 row tolerances by kind, `a + r s` (K04 §5.2 for the equilibrium row).
TOL_FLOW = mpf("1e-9") + mpf("1e-8") * 3
TOL_EQUILIBRIUM = mpf("1e-9") * 3 + mpf("1e-8") * 9
TOL_ENERGY = mpf("1e-5") + mpf("1e-8") * mpf(10) ** 5

#: K03 §4.2 scales by kind.
SCALE_FLOW = mpf(3)
SCALE_EQUILIBRIUM = mpf(9)
SCALE_TEMPERATURE = mpf(100)
SCALE_ENERGY = mpf(10) ** 5

CF = t02.a02_closed_forms()
N3: tuple[Any, ...] = tuple(CF["S3_n_mol_per_s"])
N3_TOTAL = sum(N3)
Z3 = tuple(v / N3_TOTAL for v in N3)
H_S2 = CF["H_S2_W"]
H_OUT = CF["H_flash_products_W"]
T_BUBBLE = CF["S3_bubble_point_K"]
T_DEW = CF["S3_dew_point_K"]


def q_flash_at(temp_k: Any) -> Any:
    """The flash duty that makes `temp_k` the heater outlet temperature (T02 §7.6)."""
    return H_OUT - split_enthalpy(temp_k)


def split_enthalpy(temp_k: Any) -> Any:
    regime, split = kernel(temp_k)
    return heater_enthalpy({"T": temp_k, **split})


# --------------------------------------------------------------------------------------------
# 2. The heater-side block of the A02 region (T03 spec §6.1)
# --------------------------------------------------------------------------------------------

VARIABLES = ("T", "vA", "vB", "vC", "lA", "lB", "lC", "V", "L", "Qh", "Qf")
ROWS = ("eqA", "eqB", "eqC", "spA", "spB", "spC", "Vdef", "Ldef", "HEAT", "FLASH", "SPEC")
#: The implementation's ids for the block's variables, for the YAML and the messages.
IDS = {
    "T": "S3.T",
    "vA": "S3.vap.A",
    "vB": "S3.vap.B",
    "vC": "S3.vap.C",
    "lA": "S3.liq.A",
    "lB": "S3.liq.B",
    "lC": "S3.liq.C",
    "V": "S3.V",
    "L": "S3.L",
    "Qh": "U-HEAT.Q",
    "Qf": "U-FLASH.Q",
}
FLOW_VARIABLES = ("vA", "vB", "vC", "lA", "lB", "lC", "V", "L")
VAPOR_SIDE = ("vA", "vB", "vC", "V")
LIQUID_SIDE = ("lA", "lB", "lC", "L")
COLUMN_SCALE = {
    **{v: SCALE_FLOW for v in FLOW_VARIABLES},
    "T": SCALE_TEMPERATURE,
    "Qh": SCALE_ENERGY,
    "Qf": SCALE_ENERGY,
}
ROW_SCALE = {
    **{r: SCALE_EQUILIBRIUM for r in ("eqA", "eqB", "eqC")},
    **{r: SCALE_FLOW for r in ("spA", "spB", "spC", "Vdef", "Ldef")},
    **{r: SCALE_ENERGY for r in ("HEAT", "FLASH", "SPEC")},
}
ROW_TOLERANCE = {
    **{r: TOL_EQUILIBRIUM for r in ("eqA", "eqB", "eqC")},
    **{r: TOL_FLOW for r in ("spA", "spB", "spC", "Vdef", "Ldef")},
    **{r: TOL_ENERGY for r in ("HEAT", "FLASH", "SPEC")},
}
REGIMES = ("LIQUID", "TWO_PHASE", "VAPOR")
#: T03 §4.4: the adjacency of the phase-set lattice of a vapour-liquid unit.
ADJACENT = {
    ("LIQUID", "TWO_PHASE"),
    ("TWO_PHASE", "LIQUID"),
    ("TWO_PHASE", "VAPOR"),
    ("VAPOR", "TWO_PHASE"),
}


def k_values(temp_k: Any) -> tuple[Any, ...]:
    return tuple(p01.k_value(i, temp_k, P_R) for i in range(3))


def dk_dt(temp_k: Any) -> tuple[Any, ...]:
    """d K_i / dT at P = P_ref: K_i = exp(L_i / R (1/Tb_i - 1/T)), so K_i' = K_i L_i / (R T^2)."""
    return tuple(p01.k_value(i, temp_k, P_R) * L_VAP[i] / (p01.R_GAS * temp_k**2) for i in range(3))


def heater_enthalpy(x: dict[str, Any]) -> Any:
    """`H_S3` from the lifted split: `sum (v_i + l_i) cp (T - 300) + sum v_i L_i` at P_ref."""
    sensible = CP * (x["T"] - p01.T_REF)
    return sum(
        (x["v" + c] + x["l" + c]) * sensible + x["v" + c] * L_VAP[i]
        for i, c in enumerate(COMPONENTS)
    )


def pinned_of(regime: str) -> tuple[str, ...]:
    return {"LIQUID": VAPOR_SIDE, "VAPOR": LIQUID_SIDE, "TWO_PHASE": ()}[regime]


def dropped_of(regime: str) -> tuple[str, ...]:
    return {
        "LIQUID": ("eqA", "eqB", "eqC", "Vdef"),
        "VAPOR": ("eqA", "eqB", "eqC", "Ldef"),
        "TWO_PHASE": (),
    }[regime]


def system(regime: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """T02 §6.3.1: the free columns and retained rows of the block under a regime."""
    free = tuple(v for v in VARIABLES if v not in pinned_of(regime))
    rows = tuple(r for r in ROWS if r not in dropped_of(regime))
    return free, rows


def residual(x: dict[str, Any], q_spec: Any) -> dict[str, Any]:
    k = k_values(x["T"])
    out: dict[str, Any] = {}
    for i, c in enumerate(COMPONENTS):
        out["eq" + c] = x["v" + c] * x["L"] - k[i] * x["l" + c] * x["V"]
        out["sp" + c] = x["v" + c] + x["l" + c] - N3[i]
    out["Vdef"] = x["V"] - sum(x["v" + c] for c in COMPONENTS)
    out["Ldef"] = x["L"] - sum(x["l" + c] for c in COMPONENTS)
    h3 = heater_enthalpy(x)
    out["HEAT"] = x["Qh"] - (h3 - H_S2)
    out["FLASH"] = x["Qf"] - (H_OUT - h3)
    out["SPEC"] = x["Qf"] - q_spec
    return out


def jacobian(x: dict[str, Any], free: Sequence[str], rows: Sequence[str]) -> matrix:
    """The exact Jacobian of `residual` (closed form, not differenced)."""
    k = k_values(x["T"])
    dk = dk_dt(x["T"])
    sensible = CP * (x["T"] - p01.T_REF)
    dh: dict[str, Any] = {"T": CP * sum(x["v" + c] + x["l" + c] for c in COMPONENTS)}
    for i, c in enumerate(COMPONENTS):
        dh["v" + c] = sensible + L_VAP[i]
        dh["l" + c] = sensible
    full: dict[str, dict[str, Any]] = {r: {} for r in ROWS}
    for i, c in enumerate(COMPONENTS):
        full["eq" + c] = {
            "v" + c: x["L"],
            "L": x["v" + c],
            "l" + c: -k[i] * x["V"],
            "V": -k[i] * x["l" + c],
            "T": -dk[i] * x["l" + c] * x["V"],
        }
        full["sp" + c] = {"v" + c: mpf(1), "l" + c: mpf(1)}
    full["Vdef"] = {"V": mpf(1), **{"v" + c: mpf(-1) for c in COMPONENTS}}
    full["Ldef"] = {"L": mpf(1), **{"l" + c: mpf(-1) for c in COMPONENTS}}
    full["HEAT"] = {"Qh": mpf(1), **{v: -d for v, d in dh.items()}}
    full["FLASH"] = {"Qf": mpf(1), **dh}
    full["SPEC"] = {"Qf": mpf(1)}
    jac = matrix(len(rows), len(free))
    for i, r in enumerate(rows):
        for j, v in enumerate(free):
            jac[i, j] = full[r].get(v, mpf(0))
    return jac


def merit(values: dict[str, Any], rows: Sequence[str]) -> Any:
    return sum((values[r] / ROW_SCALE[r]) ** 2 for r in rows) / 2


def converged(values: dict[str, Any], rows: Sequence[str]) -> bool:
    return all(abs(values[r]) <= ROW_TOLERANCE[r] for r in rows)


# --------------------------------------------------------------------------------------------
# 3. The kernel, the admissibility screen and the branch found (K03 §8.2, T03 §4.3)
# --------------------------------------------------------------------------------------------


def kernel(temp_k: Any) -> tuple[str, dict[str, Any]]:
    """The provider's TP regime and split of `S3.n` at (T, P_r): derivation §5.1's order."""
    fl = p01.tp_flash(list(N3), temp_k, P_R)
    state = fl["state"]
    zero = mpf(0)
    if state == "LIQUID":
        split = {"V": zero, "L": N3_TOTAL}
        for i, c in enumerate(COMPONENTS):
            split["v" + c], split["l" + c] = zero, N3[i]
        return "LIQUID", split
    if state == "VAPOR":
        split = {"V": N3_TOTAL, "L": zero}
        for i, c in enumerate(COMPONENTS):
            split["v" + c], split["l" + c] = N3[i], zero
        return "VAPOR", split
    vapor = fl["beta"] * N3_TOTAL
    liquid = N3_TOTAL - vapor
    split = {"V": vapor, "L": liquid}
    for i, c in enumerate(COMPONENTS):
        split["v" + c] = vapor * fl["y"][i]
        split["l" + c] = liquid * fl["x"][i]
    return "TWO_PHASE", split


def admissibility_value(x: dict[str, Any], branch: str) -> Any:
    """K03 §8.2's test value on a single-phase branch: sum x K (liquid) or sum y / K (vapour)."""
    k = k_values(x["T"])
    side = "l" if branch == "LIQUID" else "v"
    total = sum(x[side + c] for c in COMPONENTS)
    frac = [x[side + c] / total for c in COMPONENTS]
    if branch == "LIQUID":
        return sum(frac[i] * k[i] for i in range(3))
    return sum(frac[i] / k[i] for i in range(3))


def branch_found(x: dict[str, Any]) -> str:
    """K03 §8.2's 'branch found': by the state's phase totals, not by the frozen regime."""
    if x["V"] == 0:
        return "LIQUID"
    if x["L"] == 0:
        return "VAPOR"
    return "TWO_PHASE"


def in_domain(x: dict[str, Any]) -> bool:
    return T_DOMAIN[0] <= x["T"] <= T_DOMAIN[1]


# --------------------------------------------------------------------------------------------
# 4. The core twin (K03 §5 exactly as the Newton core implements it) with the T03 hooks
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rules:
    """The registered contract, or one ablation of it (used only to show what each rule does)."""

    screen: str = "per_trial"  # "per_trial" (T03 §4.3) | "none" (T02 §6.3.4: closure only)
    selection: str = "largest_adjacent"  # T03 §4.5 | "largest" (K03 v0.0 §9.3)
    disappearance: str = "bound_blocked"  # T03 §4.6 | "landing" (T02 §6.3.3 as written)
    #: T03 §7: "none" (K03 §9.4, retained) | "count" (a signature may recur, bounded only by
    #: max_attempts) | "merit" (it may recur iff its opening merit is strictly below the merit at
    #: its previous opening). The last two exist here only to show they do not rescue PHS-05.
    recurrence: str = "none"


REGISTERED = Rules()
T02_RULES = Rules(screen="none", selection="largest", disappearance="landing")


@dataclass
class Trial:
    iteration: int
    halving: int
    alpha: Any
    temperature: Any
    verdict: str  # accepted | invalid_trial | phase_update_required | armijo
    reported: str | None = None  # the kernel regime of a phase-rejected trial
    screen_value: Any = None
    state: dict[str, Any] | None = None
    merit_ratio: Any = None  # trial merit / (1 - 2 c alpha) merit, for the Armijo margin


@dataclass
class CoreRun:
    outcome: str
    iterations: int
    x: dict[str, Any]
    trials: list[Trial] = field(default_factory=list)
    wall_iterations: list[int] = field(default_factory=list)
    candidates: list[Trial] = field(default_factory=list)
    landings: list[tuple[int, Any, tuple[str, ...]]] = field(default_factory=list)
    blocked: tuple[str, ...] = ()
    closed_by: str = ""  # wall | landing | "" (the core's own outcome)
    landed_variable: str = ""
    residual_history: list[dict[str, Any]] = field(default_factory=list)
    direction_history: list[dict[str, Any]] = field(default_factory=list)
    alpha_max_history: list[Any] = field(default_factory=list)
    ratio_gaps: list[Any] = field(default_factory=list)


def watched(regime: str, x: dict[str, Any]) -> dict[str, str]:
    """T03 §4.6: the lifted variables whose persistent block means a phase leaves.

    Only a TWO_PHASE unit has a phase that can leave; a phase total is watched while the stream
    flows, a phase component while the stream's own component is positive (T02 §6.3.3's premise,
    ADR 0001 D3.3's exception)."""
    if regime != "TWO_PHASE":
        return {}
    out: dict[str, str] = {}
    if N3_TOTAL > 0:
        out["V"], out["L"] = "vapor", "liquid"
    for i, c in enumerate(COMPONENTS):
        if N3[i] > 0:
            out["v" + c], out["l" + c] = "vapor", "liquid"
    return out


def core(x0: dict[str, Any], regime: str, q_spec: Any, rules: Rules) -> CoreRun:
    free, rows = system(regime)
    x = dict(x0)
    for v in pinned_of(regime):
        x[v] = mpf(0)
    values = residual(x, q_spec)
    ratios: list[Any] = []
    run = CoreRun("", 0, x)
    last_wall_line_search = -1
    for it in range(MAX_ITERATIONS + 1):
        run.residual_history.append(values)
        m = merit(values, rows)
        if converged(values, rows):
            run.outcome, run.iterations, run.x = "CONVERGED", it, x
            return run
        if it == MAX_ITERATIONS:
            run.outcome, run.iterations, run.x = "BUDGET_EXHAUSTED", it, x
            return run
        if len(ratios) >= STAGNATION_WINDOW and all(
            q > STAGNATION_RATIO for q in ratios[-STAGNATION_WINDOW:]
        ):
            run.outcome, run.iterations, run.x = "STAGNATION", it, x
            return run
        jac = jacobian(x, free, rows)
        step = lu_solve(jac, matrix([-values[r] for r in rows]))
        d = {v: step[j] for j, v in enumerate(free)}
        run.direction_history.append(d)
        # K03 §5.3: bound-aware alpha_max and exact landing (lower bound 0 on every flow column)
        ratios_to_bound = {
            v: -x[v] / d[v] for v in free if v in FLOW_VARIABLES and d[v] < 0 and x[v] + d[v] < 0
        }
        alpha_max = min([mpf(1), *ratios_to_bound.values()])
        if alpha_max <= 0:
            run.outcome, run.iterations, run.x = "BOUND_BLOCKED", it, x
            run.blocked = tuple(v for v in free if v in ratios_to_bound and x[v] <= 0)
            return run
        landing = tuple(v for v, r in ratios_to_bound.items() if r == alpha_max)
        if ratios_to_bound:
            ordered = sorted(ratios_to_bound.values())
            if len(ordered) > 1:
                run.ratio_gaps.append((ordered[1] - ordered[0]) / ordered[0])
        run.alpha_max_history.append(alpha_max)
        accepted = False
        for j in range(STEP_HALVINGS_MAX + 1):
            alpha = alpha_max / mpf(2) ** j
            y = {v: (x[v] + alpha * d[v] if v in d else x[v]) for v in x}
            if j == 0:
                for v in landing:
                    y[v] = mpf(0)
            trial = Trial(it, j, alpha, y["T"], "", state=y)
            if not in_domain(y):
                trial.verdict = "invalid_trial"
                run.trials.append(trial)
                continue
            if rules.screen == "per_trial" and regime in ("LIQUID", "VAPOR"):
                value = admissibility_value(y, regime)
                trial.screen_value = value
                if value > 1 + ADMISSIBILITY_EPSILON:
                    reported, _ = kernel(y["T"])
                    if reported != regime:
                        trial.verdict, trial.reported = "phase_update_required", reported
                        run.trials.append(trial)
                        if it != last_wall_line_search:
                            last_wall_line_search = it
                            run.candidates = []
                        run.candidates.append(trial)
                        if not run.wall_iterations or run.wall_iterations[-1] != it:
                            run.wall_iterations.append(it)
                        continue
            trial_values = residual(y, q_spec)
            trial_merit = merit(trial_values, rows)
            bound = (1 - 2 * ARMIJO_C * alpha) * m
            trial.merit_ratio = trial_merit / bound if bound > 0 else mpf(0)
            if trial_merit > bound:
                trial.verdict = "armijo"
                run.trials.append(trial)
                continue
            trial.verdict = "accepted"
            run.trials.append(trial)
            ratios.append(trial_merit / m if m > 0 else mpf(0))
            x, values, accepted = y, trial_values, True
            if j == 0 and landing:
                run.landings.append((it, alpha_max, landing))
                hit = [v for v in landing if v in watched(regime, x)]
                if rules.disappearance == "landing" and hit:
                    run.outcome, run.iterations, run.x = "PHASE_UPDATE_REQUIRED", it + 1, x
                    run.closed_by, run.landed_variable = "landing", hit[0]
                    return run
            break
        recent = run.wall_iterations[-PHASE_WALL_PATIENCE:]
        if (
            len(recent) == PHASE_WALL_PATIENCE
            and recent == list(range(recent[0], recent[0] + PHASE_WALL_PATIENCE))
            and recent[-1] == it
        ):
            run.outcome, run.iterations, run.x = "PHASE_UPDATE_REQUIRED", it + int(accepted), x
            run.closed_by = "wall"
            return run
        if not accepted:
            run.outcome, run.iterations, run.x = "LINE_SEARCH_FAILED", it, x
            return run
    raise AssertionError("unreachable: the iteration budget is checked inside the loop")


# --------------------------------------------------------------------------------------------
# 5. The controller twin (T03 §4)
# --------------------------------------------------------------------------------------------


@dataclass
class Attempt:
    regime: str
    source: str
    opening_temperature: Any
    opening_beta: Any
    opening_trial: tuple[int, int] | None
    opening_alpha: Any
    run: CoreRun
    decision: str = ""
    cause: str = ""
    #: K03 §8.2's value at the opening state of a single-phase attempt -- recorded because the
    #: opening point is *not* screened (T03 §4.3), and PHS-04 opens where it would fail.
    opening_screen: Any = None
    #: The scaled merit of the attempt's own system at its opening state (T03 §7).
    opening_merit: Any = None


@dataclass
class Solve:
    outcome: str
    attempts: list[Attempt]
    x: dict[str, Any] | None = None
    refused: str = ""


def signature_text(regime: str) -> str:
    return f"U-HEAT:{regime},U-FLASH:TWO_PHASE"


def select_restart(candidates: list[Trial], frozen: str, rules: Rules) -> Trial:
    """T03 §4.5: the largest alpha among the adjacent candidates, else the largest alpha."""
    if rules.selection == "largest_adjacent":
        for trial in candidates:
            if (frozen, trial.reported) in ADJACENT:
                return trial
    if rules.selection == "smallest":  # the rejected "nearest the wall" alternative (T03 §4.5)
        return candidates[-1]
    return candidates[0]


def initial_state(t0: Any) -> tuple[str, dict[str, Any]]:
    """§7.5 of T02: the pre-solve with S3.T pinned at the guess; the split is the kernel's."""
    regime, split = kernel(t0)
    x: dict[str, Any] = {"T": t0, **split}
    h3 = heater_enthalpy(x)
    x["Qh"], x["Qf"] = h3 - H_S2, H_OUT - h3
    return regime, x


def beta_of(x: dict[str, Any]) -> Any:
    return x["V"] / (x["V"] + x["L"])


def pin(x: dict[str, Any], remaining: str) -> dict[str, Any]:
    """T02 §6.3.3's restart point: the phase that left is exactly zero, the other takes the feed."""
    y = dict(x)
    gone, kept = ("v", "l") if remaining == "LIQUID" else ("l", "v")
    for i, c in enumerate(COMPONENTS):
        y[gone + c], y[kept + c] = mpf(0), N3[i]
    y["V" if gone == "v" else "L"] = mpf(0)
    y["L" if gone == "v" else "V"] = N3_TOTAL
    return y


def solve(
    t0: Any, q_spec: Any, rules: Rules = REGISTERED, max_attempts: int = MAX_ATTEMPTS
) -> Solve:
    regime, x = initial_state(mpf(t0))
    used: list[str] = []
    opened_merit: dict[str, Any] = {}
    attempts: list[Attempt] = []
    source, opening_trial, opening_alpha, cause = "initializer", None, None, ""
    for k in range(max_attempts):
        _, rows = system(regime)
        opening = {**x, **{v: mpf(0) for v in pinned_of(regime)}}
        merit_at_opening = merit(residual(opening, q_spec), rows)
        if regime in used and (
            rules.recurrence == "none"
            or (rules.recurrence == "merit" and not merit_at_opening < opened_merit[regime])
        ):
            return Solve(
                "ACTIVE_SET_CYCLING", attempts, refused=f"{signature_text(regime)}; {cause}"
            )
        used.append(regime)
        opened_merit[regime] = merit_at_opening
        run = core(x, regime, q_spec, rules)
        attempt = Attempt(regime, source, x["T"], beta_of(x), opening_trial, opening_alpha, run)
        attempt.opening_merit = merit_at_opening
        if regime in ("LIQUID", "VAPOR"):
            attempt.opening_screen = admissibility_value(
                {**x, **{v: mpf(0) for v in pinned_of(regime)}}, regime
            )
        attempts.append(attempt)
        end = run.x
        new: str | None = None
        opening_trial, opening_alpha = None, None
        if run.outcome == "CONVERGED":
            branch = branch_found(end)
            if (
                branch == "TWO_PHASE"
                or admissibility_value(end, branch) <= 1 + ADMISSIBILITY_EPSILON
            ):
                attempt.decision = "converged"
                return Solve("CONVERGED", attempts, x=end)
            new, split = kernel(end["T"])
            x = {**end, **split}
            value = admissibility_value(end, branch)
            cause = f"inadmissible(S3, all_{branch.lower()}, {p01.s(value)})"
            source = "closure_projection"
        elif run.closed_by == "wall" or (
            run.outcome in ("LINE_SEARCH_FAILED", "STAGNATION")
            and run.wall_iterations
            and run.iterations - run.wall_iterations[-1] < STAGNATION_WINDOW
        ):
            pick = select_restart(run.candidates, regime, rules)
            assert pick.state is not None and pick.reported is not None
            new = pick.reported
            _, split = kernel(pick.state["T"])
            x = {**pick.state, **split}
            trigger = "patience" if run.closed_by == "wall" else "stall"
            cause = f"phase_wall({trigger}, U-HEAT:{regime}->{new})"
            source, opening_trial, opening_alpha = (
                "phase_rejected_trial",
                (
                    pick.iteration,
                    pick.halving,
                ),
                pick.alpha,
            )
        elif run.closed_by == "landing" or (
            run.outcome == "BOUND_BLOCKED" and any(v in watched(regime, end) for v in run.blocked)
        ):
            variable = (
                run.landed_variable
                if run.closed_by == "landing"
                else next(v for v in run.blocked if v in watched(regime, end))
            )
            phase = "vapor" if variable in VAPOR_SIDE else "liquid"
            if regime == "TWO_PHASE":
                new = "LIQUID" if phase == "vapor" else "VAPOR"
            else:  # T02's single-phase clause (ablation only; T03 watches no single-phase unit)
                new = "VAPOR" if regime == "LIQUID" else "LIQUID"
            x = pin(end, new)
            cause = f"phase_disappeared(U-HEAT, {phase}, {IDS[variable]})"
            source = "pinned_iterate"
        elif run.outcome in (
            "STAGNATION",
            "LINE_SEARCH_FAILED",
            "BOUND_BLOCKED",
            "BUDGET_EXHAUSTED",
        ):
            verdict, split = kernel(end["T"])
            if verdict != regime:
                new = verdict
                x = {**end, **split}
                cause = f"kernel_disagrees(U-HEAT, {verdict})"
                source = "closure_projection"
        if new is None:
            attempt.decision = "terminal"
            return Solve(run.outcome, attempts, x=end)
        attempt.decision, attempt.cause = "restart", cause
        regime = new
        if k + 1 == max_attempts:
            return Solve("ATTEMPTS_EXHAUSTED", attempts, x=end)
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------------------------
# 6. Output helpers
# --------------------------------------------------------------------------------------------


def s(value: Any, digits: int = 20) -> str:
    return p01.s(value, digits)


def trial_record(trial: Trial) -> dict[str, Any]:
    record: dict[str, Any] = {
        "iteration": trial.iteration,
        "halving": trial.halving,
        "alpha": s(trial.alpha),
        "S3_T_K": s(trial.temperature),
        "verdict": trial.verdict,
    }
    if trial.reported is not None:
        record["reported_heater_regime"] = trial.reported
    if trial.screen_value is not None:
        record["screen_value"] = s(trial.screen_value)
    return record


def attempt_record(attempt: Attempt, keep_trials: bool) -> dict[str, Any]:
    run = attempt.run
    record: dict[str, Any] = {
        "signature": signature_text(attempt.regime),
        "opening_source": attempt.source,
        "opening_trial": (
            None
            if attempt.opening_trial is None
            else {"iteration": attempt.opening_trial[0], "halving": attempt.opening_trial[1]}
        ),
        "opening_alpha": None if attempt.opening_alpha is None else s(attempt.opening_alpha),
        "opening_S3_T_K": s(attempt.opening_temperature),
        "opening_beta": s(attempt.opening_beta),
        "opening_screen_value": (
            s(attempt.opening_screen) if attempt.opening_screen is not None else None
        ),
        "core_outcome": run.outcome,
        "core_iterations": run.iterations,
        "decision": attempt.decision,
        "cause": attempt.cause,
        "end_S3_T_K": s(run.x["T"]),
    }
    if run.blocked:
        record["blocked_by"] = [IDS[v] for v in run.blocked]
    if run.landings:
        record["landings"] = [
            {"iteration": it, "alpha_max": s(a), "variables": [IDS[v] for v in vs]}
            for it, a, vs in run.landings
        ]
    if keep_trials:
        record["trials"] = [trial_record(t) for t in run.trials]
    record["phase_rejections"] = sum(t.verdict == "phase_update_required" for t in run.trials)
    record["invalid_trials"] = sum(t.verdict == "invalid_trial" for t in run.trials)
    return record


def final_record(x: dict[str, Any]) -> dict[str, Any]:
    return {
        "S3_T_K": s(x["T"]),
        "U_HEAT_Q_W": s(x["Qh"]),
        "U_FLASH_Q_W": s(x["Qf"]),
        "beta": s(beta_of(x)),
        "S3_vapor_mol_per_s": [s(x["v" + c]) for c in COMPONENTS],
        "S3_liquid_mol_per_s": [s(x["l" + c]) for c in COMPONENTS],
        "branch_found": branch_found(x),
    }


# --------------------------------------------------------------------------------------------
# 7. Margins: every decision on a registered path is far from its threshold (T03 §6.5)
# --------------------------------------------------------------------------------------------


def decision_margins(result: Solve, q_spec: Any) -> dict[str, Any]:
    """The smallest distance of each discrete decision from the value that would flip it."""
    screen: list[Any] = []
    domain: list[Any] = []
    kernel_margin: list[Any] = []
    armijo: list[Any] = []
    for attempt in result.attempts:
        for trial in attempt.run.trials:
            if trial.screen_value is not None:
                screen.append(abs(trial.screen_value - 1 - ADMISSIBILITY_EPSILON))
            domain.append(
                min(abs(trial.temperature - T_DOMAIN[0]), abs(trial.temperature - T_DOMAIN[1]))
            )
            if trial.verdict == "phase_update_required":
                kernel_margin.append(
                    min(abs(trial.temperature - T_BUBBLE), abs(trial.temperature - T_DEW))
                )
            if trial.merit_ratio is not None:
                armijo.append(abs(1 - trial.merit_ratio))
    convergence: list[Any] = []
    for attempt in result.attempts:
        run = attempt.run
        if run.outcome != "CONVERGED":
            continue
        _, rows = system(attempt.regime)
        last = run.residual_history[-1]
        before = run.residual_history[-2] if len(run.residual_history) > 1 else None
        convergence.append(min(ROW_TOLERANCE[r] / max(abs(last[r]), mpf("1e-300")) for r in rows))
        if before is not None:
            convergence.append(max(abs(before[r]) / ROW_TOLERANCE[r] for r in rows))
    return {
        "screen_min_abs_sum_minus_1": min(screen) if screen else None,
        "domain_min_K": min(domain) if domain else None,
        "phase_boundary_min_K": min(kernel_margin) if kernel_margin else None,
        "armijo_min_relative": min(armijo) if armijo else None,
        "convergence_min_factor": min(convergence) if convergence else None,
    }


# --------------------------------------------------------------------------------------------
# 8. Synthetic tear seeds (T03 §6.6): one variable, regimes by band, closed form
# --------------------------------------------------------------------------------------------


def band_seed(bands: tuple[Any, Any], target: Any, x0: Any) -> dict[str, Any]:
    """F(x) = x - target in every regime; regime(x) = LIQUID below bands[0], TWO_PHASE below
    bands[1], VAPOR above. K03's line search and T03's wall rule, exactly (scale 1, no bounds)."""

    def regime_of(x: Any) -> str:
        return "LIQUID" if x < bands[0] else ("TWO_PHASE" if x < bands[1] else "VAPOR")

    attempts: list[dict[str, Any]] = []
    x = mpf(x0)
    regime = regime_of(x)
    used: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        if regime in used:
            return {"outcome": "ACTIVE_SET_CYCLING", "attempts": attempts}
        used.append(regime)
        wall: list[int] = []
        cands: list[tuple[Any, Any, str]] = []
        last = -1
        record: dict[str, Any] = {"signature": regime, "opening_x": s(x), "iterations": []}
        attempts.append(record)
        closed = ""
        for it in range(MAX_ITERATIONS + 1):
            f = x - target
            if abs(f) <= mpf("1e-12"):
                record["core_outcome"], record["core_iterations"] = "CONVERGED", it
                return {"outcome": "CONVERGED", "x": s(x), "attempts": attempts}
            d = -f
            m = f**2 / 2
            accepted = False
            line: list[dict[str, Any]] = []
            for j in range(STEP_HALVINGS_MAX + 1):
                alpha = mpf(1) / 2**j
                y = x + alpha * d
                r = regime_of(y)
                if r != regime:
                    line.append({"alpha": s(alpha), "x": s(y), "reported": r})
                    if it != last:
                        last, cands = it, []
                    cands.append((alpha, y, r))
                    if not wall or wall[-1] != it:
                        wall.append(it)
                    continue
                if (y - target) ** 2 / 2 > (1 - 2 * ARMIJO_C * alpha) * m:
                    line.append({"alpha": s(alpha), "x": s(y), "verdict": "armijo"})
                    continue
                line.append({"alpha": s(alpha), "x": s(y), "verdict": "accepted"})
                x, accepted = y, True
                break
            record["iterations"].append(line)
            if len(wall) >= 2 and wall[-2:] == [it - 1, it]:
                closed = "wall"
                record["core_outcome"], record["core_iterations"] = "PHASE_UPDATE_REQUIRED", it + 1
                break
            if not accepted:
                closed = "stall"
                record["core_outcome"], record["core_iterations"] = "LINE_SEARCH_FAILED", it
                break
        assert closed
        pick = next((c for c in cands if (regime, c[2]) in ADJACENT), cands[0])
        record["restart"] = {"alpha": s(pick[0]), "x": s(pick[1]), "signature": pick[2]}
        x, regime = pick[1], pick[2]
    return {"outcome": "ATTEMPTS_EXHAUSTED", "attempts": attempts}


# --------------------------------------------------------------------------------------------
# 9. The manufactured multiple-root case REC-05 (T02 §8) and the fingerprint tolerance
# --------------------------------------------------------------------------------------------

GAMMA_TAIL = mpf("0.1")


def rec05_map() -> Callable[[tuple[Any, ...]], tuple[Any, ...]]:
    return t02.manufactured_map(t02.REC_MAPS["REC-05"]["A"], GAMMA_TAIL)


def rec05_jacobian(t: Sequence[Any]) -> matrix:
    d = [t[i] - t02.T_STAR[i] for i in range(3)]
    jq = matrix([[0, d[2], d[1]], [d[2], 0, d[0]], [d[1], d[0], 0]])
    return t02.REC_MAPS["REC-05"]["A"] + GAMMA_TAIL * jq / t02.S3


def rec05_newton(t0: Sequence[Any]) -> tuple[str, int, tuple[Any, ...]]:
    """K03 §5 on R(t) = G(t) - t with bounds t >= 0 (the merge edge's region Newton, T02 §4.4)."""
    g = rec05_map()
    x = [mpf(v) for v in t0]

    def res(t: Sequence[Any]) -> list[Any]:
        y = g(tuple(t))
        return [y[i] - t[i] for i in range(3)]

    def phi(t: Sequence[Any]) -> Any:
        return sum((v / t02.S3) ** 2 for v in res(t)) / 2

    for it in range(MAX_ITERATIONS + 1):
        f = res(x)
        if all(abs(v) <= t02.TEAR_TOL for v in f):
            return "CONVERGED", it, tuple(x)
        d = lu_solve(rec05_jacobian(x) - eye(3), matrix([-v for v in f]))
        alpha_max = min([mpf(1), *(-x[i] / d[i] for i in range(3) if d[i] < 0 and x[i] + d[i] < 0)])
        m = phi(x)
        for j in range(STEP_HALVINGS_MAX + 1):
            alpha = alpha_max / 2**j
            y = [x[i] + alpha * d[i] for i in range(3)]
            if phi(y) <= (1 - 2 * ARMIJO_C * alpha) * m:
                x = y
                break
        else:
            return "LINE_SEARCH_FAILED", it, tuple(x)
    return "BUDGET_EXHAUSTED", MAX_ITERATIONS, tuple(x)


def inf_norm_rows(m: matrix) -> Any:
    return max(sum(abs(m[i, j]) for j in range(m.cols)) for i in range(m.rows))


# --------------------------------------------------------------------------------------------
# 10. Build
# --------------------------------------------------------------------------------------------

PHS_CASES: dict[str, dict[str, Any]] = {
    "SYN-001-A02-355-liquid-guess": {"T_heater": 355, "guess": 350, "id": "PHS-01"},
    "SYN-001-A02-360-liquid-guess": {"T_heater": 360, "guess": 350, "id": "PHS-02"},
    "SYN-001-A02-360-vapor-guess": {"T_heater": 360, "guess": 400, "id": "PHS-03"},
    "SYN-001-A02-340-two-phase-guess": {"T_heater": 340, "guess": 360, "id": "PHS-04"},
    "SYN-001-A02-355-dew-guess": {"T_heater": 355, "guess": 375, "id": "PHS-05"},
}


def build(low_precision_floor: bool = True) -> dict[str, Any]:
    checks: list[str] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        if not cond:
            raise AssertionError(f"self-check failed: {name} {detail}")
        checks.append(name)

    # ---- closed forms of the A02 family ----------------------------------------------------
    ok("bubble point of S3.n inside (351, 352) K", 351 < T_BUBBLE < 352)
    ok("dew point of S3.n inside (377, 378) K", 377 < T_DEW < 378)
    q_specs = {t: q_flash_at(mpf(t)) for t in (340, 355, 360)}
    ok(
        "Q_flash(360 K) is exactly the registered zero to 1e-25 W",
        abs(q_specs[360]) < mpf("1e-25"),
    )
    ok(
        "Q_flash(355 K) equals T02's registered sweep value to 1e-20 W",
        abs(q_specs[355] - CF["sweep"]["T_heater=355K"]["Q_flash_W"]) < mpf("1e-20"),
    )
    ok(
        "Q_flash(340 K) equals T02's registered sweep value to 1e-20 W",
        abs(q_specs[340] - CF["sweep"]["T_heater=340K"]["Q_flash_W"]) < mpf("1e-20"),
    )

    def liquid_root(q: Any) -> Any:
        return p01.T_REF + (H_OUT - q) / (CP * N3_TOTAL)

    def vapor_root(q: Any) -> Any:
        return p01.T_REF + (H_OUT - q - sum(N3[i] * L_VAP[i] for i in range(3))) / (CP * N3_TOTAL)

    branch_roots = {
        t: {"liquid_branch_T_K": liquid_root(q), "vapor_branch_T_K": vapor_root(q)}
        for t, q in q_specs.items()
    }
    ok(
        "the 355 K liquid-branch root equals T02's 389.438 K and lies inside the domain",
        abs(
            branch_roots[355]["liquid_branch_T_K"]
            - CF["branch_roots"]["Q_flash=Q(355K)"]["liquid_branch_T_K"]
        )
        < mpf("1e-25")
        and branch_roots[355]["liquid_branch_T_K"] < T_DOMAIN[1],
    )
    ok(
        "the 360 K liquid-branch root lies above the domain, the vapour-branch root below it",
        branch_roots[360]["liquid_branch_T_K"] > T_DOMAIN[1]
        and branch_roots[360]["vapor_branch_T_K"] < T_DOMAIN[0],
    )
    ok(
        "the 340 K root is on the liquid branch (below the bubble point) and inside the domain",
        abs(branch_roots[340]["liquid_branch_T_K"] - 340) < mpf("1e-25") and 340 < T_BUBBLE,
    )

    # ---- the reduction is exact: the analytic Jacobian is the derivative of the residual ------
    probe = {**kernel(mpf(365))[1], "T": mpf(365), "Qh": mpf(70000), "Qf": mpf(-5000)}
    jac = jacobian(probe, VARIABLES, ROWS)
    worst = mpf(0)
    for j, v in enumerate(VARIABLES):
        for i, r in enumerate(ROWS):
            numeric = mp.diff(lambda t, v=v, r=r: residual({**probe, v: t}, 0)[r], probe[v])
            worst = max(worst, abs(numeric - jac[i, j]) / max(1, abs(jac[i, j])))
    ok(
        "the block's closed-form Jacobian equals its 40-digit derivative to 1e-25",
        worst < mpf("1e-25"),
    )
    ok(
        "the block is square under every regime (T02 §6.3.1)",
        all(len(system(r)[0]) == len(system(r)[1]) for r in REGIMES),
    )

    # ---- the registered cases ---------------------------------------------------------------
    cases: dict[str, Any] = {}
    results: dict[str, Solve] = {}
    for case_id, spec in PHS_CASES.items():
        q = q_specs[spec["T_heater"]]
        result = solve(spec["guess"], q)
        results[case_id] = result
        cases[case_id] = {
            "id": spec["id"],
            "Q_flash_spec_W": s(q),
            "guess_S3_T_K": spec["guess"],
            "outcome": result.outcome,
            "attempts": [attempt_record(a, keep_trials=True) for a in result.attempts],
            "final": final_record(result.x) if result.x is not None else None,
            "refused": result.refused,
            "margins": {
                k: (None if v is None else s(v, 6)) for k, v in decision_margins(result, q).items()
            },
        }

    def attempts_of(case_id: str) -> list[Attempt]:
        return results[case_id].attempts

    # PHS-01 and PHS-02: the liquid-guess cases are successes under the contract
    for case_id, temp in (
        ("SYN-001-A02-355-liquid-guess", 355),
        ("SYN-001-A02-360-liquid-guess", 360),
    ):
        res = results[case_id]
        a1, a2 = attempts_of(case_id)[0], attempts_of(case_id)[-1]
        ok(
            f"{case_id}: CONVERGED in exactly 2 attempts",
            res.outcome == "CONVERGED" and len(res.attempts) == 2,
        )
        ok(
            f"{case_id}: attempt 1 is LIQUID and closes on the wall's patience at core iteration 2",
            a1.regime == "LIQUID" and a1.run.closed_by == "wall" and a1.run.iterations == 2,
        )
        ok(
            f"{case_id}: attempt 2 opens TWO_PHASE from a phase-rejected trial of iteration 1",
            a2.regime == "TWO_PHASE"
            and a2.source == "phase_rejected_trial"
            and a2.opening_trial is not None
            and a2.opening_trial[0] == 1,
        )
        ok(
            f"{case_id}: a far (VAPOR) candidate exists and is not the one chosen",
            any(t.reported == "VAPOR" for t in a1.run.candidates)
            and a1.run.candidates[0].reported == "VAPOR",
        )
        ok(
            f"{case_id}: attempt 2 lands S3.vap.C at iteration 0 and does not close on it",
            a2.run.landings
            and a2.run.landings[0][0] == 0
            and a2.run.landings[0][2] == ("vC",)
            and a2.run.closed_by == "",
        )
        ok(
            f"{case_id}: after the landing the direction on S3.vap.C points inward (> 0)",
            a2.run.direction_history[1]["vC"] > 0,
        )
        ok(
            f"{case_id}: the converged state is the {temp} K sweep row (T within 1e-6 K)",
            res.x is not None
            and abs(res.x["T"] - temp) < mpf("1e-6")
            and branch_found(res.x) == "TWO_PHASE",
        )
    ok(
        "PHS-01 attempt 2 converges at core iteration 5",
        attempts_of("SYN-001-A02-355-liquid-guess")[1].run.iterations == 5,
    )
    ok(
        "PHS-02 attempt 2 converges at core iteration 4",
        attempts_of("SYN-001-A02-360-liquid-guess")[1].run.iterations == 4,
    )
    ok(
        "PHS-02 attempt 1's full step is refused by the provider domain (442.64 K), not by phase",
        attempts_of("SYN-001-A02-360-liquid-guess")[0].run.trials[0].verdict == "invalid_trial",
    )

    res = results["SYN-001-A02-360-vapor-guess"]
    ok(
        "PHS-03: VAPOR then TWO_PHASE, CONVERGED at 360 K",
        res.outcome == "CONVERGED"
        and [a.regime for a in res.attempts] == ["VAPOR", "TWO_PHASE"]
        and res.x is not None
        and abs(res.x["T"] - 360) < mpf("1e-6"),
    )
    ok(
        "PHS-03: attempt 1 reports a far (LIQUID) candidate that is skipped",
        any(t.reported == "LIQUID" for t in res.attempts[0].run.candidates)
        and select_restart(res.attempts[0].run.candidates, "VAPOR", REGISTERED).reported
        == "TWO_PHASE",
    )

    res = results["SYN-001-A02-340-two-phase-guess"]
    a1 = res.attempts[0]
    ok(
        "PHS-04: TWO_PHASE then LIQUID, CONVERGED at 340 K on the liquid branch",
        res.outcome == "CONVERGED"
        and [a.regime for a in res.attempts] == ["TWO_PHASE", "LIQUID"]
        and res.x is not None
        and abs(res.x["T"] - 340) < mpf("1e-6")
        and branch_found(res.x) == "LIQUID",
    )
    ok(
        "PHS-04: attempt 1 lands S3.vap.C at iteration 0, then is BOUND_BLOCKED on it alone at 1",
        a1.run.landings
        and a1.run.landings[0][2] == ("vC",)
        and a1.run.outcome == "BOUND_BLOCKED"
        and a1.run.iterations == 1
        and a1.run.blocked == ("vC",),
    )
    ok(
        "PHS-04: the disappearance restart opens LIQUID where the screen would refuse a trial "
        "(the opening point is not screened)",
        admissibility_value(pin(a1.run.x, "LIQUID"), "LIQUID") > 1 + ADMISSIBILITY_EPSILON,
    )
    ok(
        "PHS-04: attempt 2 converges at core iteration 1 (the liquid block is affine)",
        res.attempts[1].run.iterations == 1,
    )

    res = results["SYN-001-A02-355-dew-guess"]
    ok(
        "PHS-05: TWO_PHASE, then LIQUID, then ACTIVE_SET_CYCLING",
        res.outcome == "ACTIVE_SET_CYCLING"
        and [a.regime for a in res.attempts] == ["TWO_PHASE", "LIQUID"],
    )
    ok(
        "PHS-05: attempt 1 is BOUND_BLOCKED on S3.vap.C alone at iteration 1",
        res.attempts[0].run.outcome == "BOUND_BLOCKED"
        and res.attempts[0].run.blocked == ("vC",)
        and res.attempts[0].run.iterations == 1,
    )
    ok(
        "PHS-05: the LIQUID attempt fails its first line search with 21 phase rejections",
        res.attempts[1].run.outcome == "LINE_SEARCH_FAILED"
        and res.attempts[1].run.iterations == 0
        and sum(t.verdict == "phase_update_required" for t in res.attempts[1].run.trials) == 21,
    )
    ok(
        "PHS-05: the pinned LIQUID opening is deep inside the two-phase band",
        T_BUBBLE + 10 < res.attempts[1].opening_temperature < T_DEW - 5,
    )

    # ---- every decision on a registered success path is far from its threshold ---------------
    for case_id in PHS_CASES:
        margin = decision_margins(results[case_id], q_specs[PHS_CASES[case_id]["T_heater"]])
        if margin["screen_min_abs_sum_minus_1"] is not None:
            ok(
                f"{case_id}: every screen decision is >= 1e-6 from 1 + eps",
                margin["screen_min_abs_sum_minus_1"] >= mpf("1e-6"),
            )
        ok(
            f"{case_id}: every trial is >= 1e-3 K from the provider domain's edges",
            margin["domain_min_K"] >= mpf("1e-3"),
        )
        if margin["phase_boundary_min_K"] is not None:
            ok(
                f"{case_id}: every phase-rejected trial is >= 1e-3 K from the bubble and dew point",
                margin["phase_boundary_min_K"] >= mpf("1e-3"),
            )
        if margin["armijo_min_relative"] is not None:
            ok(
                f"{case_id}: every Armijo decision is >= 1e-6 (relative) from its bound",
                margin["armijo_min_relative"] >= mpf("1e-6"),
            )
        if margin["convergence_min_factor"] is not None:
            ok(
                f"{case_id}: the convergence iteration is decided by a factor >= 1.5 on both sides",
                margin["convergence_min_factor"] >= mpf("1.5"),
            )
    for case_id in (
        "SYN-001-A02-355-liquid-guess",
        "SYN-001-A02-360-liquid-guess",
        "SYN-001-A02-340-two-phase-guess",
    ):
        for attempt in results[case_id].attempts:
            for gap in attempt.run.ratio_gaps:
                ok(
                    f"{case_id}: the landing variable is decided by a ratio gap >= 1e-3",
                    gap >= mpf("1e-3"),
                )

    # ---- ablations: every rule of the contract is load-bearing on a registered case ----------
    ablations: dict[str, Any] = {}
    for label, rules in (
        ("no per-trial screen (T02 §6.3.4)", Rules(screen="none")),
        ("largest alpha without adjacency (K03 v0.0 §9.3)", Rules(selection="largest")),
        ("disappearance on a landing (T02 §6.3.3 as written)", Rules(disappearance="landing")),
    ):
        entry = {}
        for case_id in ("SYN-001-A02-355-liquid-guess", "SYN-001-A02-360-liquid-guess"):
            q = q_specs[PHS_CASES[case_id]["T_heater"]]
            out = solve(PHS_CASES[case_id]["guess"], q, rules)
            entry[case_id] = {
                "outcome": out.outcome,
                "signatures": [a.regime for a in out.attempts],
            }
            ok(f"ablation '{label}' breaks {case_id}", out.outcome != "CONVERGED")
        ablations[label] = entry

    # ---- T03 §7: the two natural recurrence rules do not rescue PHS-05 -------------------------
    recurrence: dict[str, Any] = {}
    for mode, expected in (("count", "ATTEMPTS_EXHAUSTED"), ("merit", "ACTIVE_SET_CYCLING")):
        out = solve(375, q_specs[355], Rules(recurrence=mode))
        recurrence[mode] = {
            "outcome": out.outcome,
            "signatures": [a.regime for a in out.attempts],
            "opening_S3_T_K": [s(a.opening_temperature, 8) for a in out.attempts],
            "opening_merit": [s(a.opening_merit, 6) for a in out.attempts],
        }
        ok(
            f"PHS-05 with recurrence '{mode}' ends {expected}, not CONVERGED",
            out.outcome == expected,
        )
    ablations["PHS-05 under a recurrence rule (T03 §7)"] = recurrence

    # ---- the twin reproduces T02's measured failures under T02's rules ------------------------
    t02_cross: dict[str, Any] = {}
    out = solve(350, q_specs[355], T02_RULES)
    t02_cross["SYN-001-A02-355-liquid-guess"] = {
        "outcome": out.outcome,
        "attempts": [attempt_record(a, keep_trials=False) for a in out.attempts],
    }
    ok(
        "T02 rules, 355 liquid guess: attempt 1 converges in 1 iteration to the 389.438 K root",
        out.attempts[0].run.outcome == "CONVERGED"
        and out.attempts[0].run.iterations == 1
        and abs(out.attempts[0].run.x["T"] - branch_roots[355]["liquid_branch_T_K"]) < mpf("1e-20"),
    )
    ok(
        "T02 rules, 355 liquid guess: VAPOR next, then ACTIVE_SET_CYCLING (T02 A30)",
        out.outcome == "ACTIVE_SET_CYCLING"
        and [a.regime for a in out.attempts] == ["LIQUID", "VAPOR"],
    )
    out = solve(350, q_specs[360], T02_RULES)
    t02_cross["SYN-001-A02-360-liquid-guess"] = {
        "outcome": out.outcome,
        "attempts": [attempt_record(a, keep_trials=False) for a in out.attempts],
    }
    ok(
        "T02 rules, 360 liquid guess: the twin reproduces T02's measured stagnation iterations "
        "13 and 9 (T02 §7.6)",
        out.attempts[0].run.iterations == 13 and out.attempts[1].run.iterations == 9,
    )
    ok(
        "T02 rules, 360 liquid guess: LIQUID stagnates above 439.99 K, VAPOR stagnates below "
        "280.01 K, ACTIVE_SET_CYCLING (T02 A31)",
        out.outcome == "ACTIVE_SET_CYCLING"
        and [a.regime for a in out.attempts] == ["LIQUID", "VAPOR"]
        and out.attempts[0].run.outcome == "STAGNATION"
        and out.attempts[0].run.x["T"] > mpf("439.99")
        and out.attempts[1].run.outcome == "STAGNATION"
        and out.attempts[1].run.x["T"] < mpf("280.01"),
    )
    t02_cross["T02_measured_for_comparison"] = {
        "360_attempt_1": "STAGNATION at iteration 13 at 439.999 999 7 K (T02 §7.6, measured)",
        "360_attempt_2": "STAGNATION at iteration 9 at 280.000 02 K (T02 §7.6, measured)",
    }

    # ---- basin margin: neighbouring guesses behave like the registered ones --------------------
    basin: dict[str, Any] = {}
    for temp, guesses in ((355, (345, 351)), (360, (345, 351, 380, 430))):
        for guess in guesses:
            out = solve(guess, q_specs[temp])
            basin[f"T_heater={temp}K,guess={guess}K"] = {
                "outcome": out.outcome,
                "signatures": [a.regime for a in out.attempts],
            }
            ok(
                f"basin margin: Q({temp} K) from {guess} K converges to {temp} K",
                out.outcome == "CONVERGED"
                and out.x is not None
                and abs(out.x["T"] - temp) < mpf("1e-5"),
            )
    out = solve(377, q_specs[355])
    basin["T_heater=355K,guess=377K"] = {
        "outcome": out.outcome,
        "signatures": [a.regime for a in out.attempts],
    }
    ok(
        "basin margin: PHS-05's failure is not a knife edge (377 K fails the same way)",
        out.outcome == "ACTIVE_SET_CYCLING",
    )

    # ---- the A02 family scan: the registered selection against "nearest the wall" --------------
    targets = (340, 355, 358, 360, 365)
    guesses = (300, 330, 345, 350, 351, 352, 355, 360, 365, 370, 375, 377, 380, 400, 430)
    scan: dict[str, Any] = {}
    for label, rules in (
        ("largest_adjacent (registered)", REGISTERED),
        ("smallest alpha (rejected)", Rules(selection="smallest")),
    ):
        failures = []
        for temp in targets:
            q = q_flash_at(mpf(temp))
            for guess in guesses:
                out = solve(guess, q, rules)
                if not (
                    out.outcome == "CONVERGED"
                    and out.x is not None
                    and abs(out.x["T"] - temp) < mpf("1e-5")
                ):
                    failures.append(f"T_heater={temp}K,guess={guess}K: {out.outcome}")
        scan[label] = {"runs": len(targets) * len(guesses), "failures": failures}
    ok(
        "family scan: the registered contract fails exactly 355 K from 375 and 377 K (2 of 75)",
        [f.split(":")[0] for f in scan["largest_adjacent (registered)"]["failures"]]
        == ["T_heater=355K,guess=375K", "T_heater=355K,guess=377K"],
    )
    ok(
        "family scan: the nearest-the-wall selection fails 5 of 75",
        len(scan["smallest alpha (rejected)"]["failures"]) == 5,
    )

    # ---- the synthetic tear seeds ---------------------------------------------------------------
    seeds = {
        "PHS-SYN-1": band_seed((mpf(1), mpf(2)), mpf(3), mpf(0)),
        "PHS-SYN-2": band_seed((mpf(1), mpf("1.01")), mpf(3), mpf(0)),
    }
    s1, s2 = seeds["PHS-SYN-1"], seeds["PHS-SYN-2"]
    ok(
        "PHS-SYN-1: LIQUID -> TWO_PHASE -> VAPOR, CONVERGED at x = 3",
        s1["outcome"] == "CONVERGED"
        and [a["signature"] for a in s1["attempts"]] == ["LIQUID", "TWO_PHASE", "VAPOR"],
    )
    ok(
        "PHS-SYN-1: attempt 1 restarts from alpha = 1/2 (x = 1.875), not from the VAPOR trial at 1",
        s1["attempts"][0]["restart"]["x"] == s(mpf("1.875")),
    )
    ok(
        "PHS-SYN-2: no adjacent candidate exists, the largest alpha (VAPOR, x = 3) is taken",
        s2["outcome"] == "CONVERGED"
        and [a["signature"] for a in s2["attempts"]] == ["LIQUID", "VAPOR"]
        and s2["attempts"][0]["restart"]["x"] == s(mpf(3)),
    )

    # ---- region shapes per signature (closed form, T02 §7.3 counts) --------------------------
    shapes = {
        "U-HEAT:TWO_PHASE,U-FLASH:TWO_PHASE": [42, 42],
        "U-HEAT:LIQUID,U-FLASH:TWO_PHASE": [
            42 - len(dropped_of("LIQUID")),
            42 - len(pinned_of("LIQUID")),
        ],
        "U-HEAT:VAPOR,U-FLASH:TWO_PHASE": [
            42 - len(dropped_of("VAPOR")),
            42 - len(pinned_of("VAPOR")),
        ],
    }
    ok(
        "the region is 38 x 38 under a single-phase heater and 42 x 42 two-phase",
        shapes["U-HEAT:LIQUID,U-FLASH:TWO_PHASE"] == [38, 38]
        and shapes["U-HEAT:VAPOR,U-FLASH:TWO_PHASE"] == [38, 38],
    )

    # ---- REC-05: two roots, provenance and the fingerprint tolerance -------------------------
    g05 = rec05_map()
    t_star = t02.T_STAR
    s_one = tuple(mpf(v) for v in t02_s1())
    ok(
        "REC-05: S1 is a fixed point to 1e-30",
        max(abs(g05(s_one)[i] - s_one[i]) for i in range(3)) < mpf("1e-30"),
    )
    run_a = t02.accelerate(
        t02.bounded_map(g05),
        tuple(mpf("1.1") * v for v in t_star),
        scale=(t02.S3,) * 3,
        tolerance=(t02.TEAR_TOL,) * 3,
        lower_bounds=(0, 0, 0),
    )
    run_b = t02.accelerate(
        t02.bounded_map(g05),
        t_star,
        scale=(t02.S3,) * 3,
        tolerance=(t02.TEAR_TOL,) * 3,
        lower_bounds=(0, 0, 0),
    )
    run_c_sub = t02.accelerate(
        t02.bounded_map(g05),
        tuple(mpf("1.1") * v for v in t_star),
        scale=(t02.S3,) * 3,
        tolerance=(t02.TEAR_TOL,) * 3,
        lower_bounds=(0, 0, 0),
        depth=0,
    )
    best = min(
        range(len(run_c_sub.residual_inf_scaled)), key=lambda i: run_c_sub.residual_inf_scaled[i]
    )
    merge_outcome, merge_iterations, merge_x = rec05_newton(run_c_sub.trajectory_x[best])

    def dist_scaled(a: Sequence[Any], b: Sequence[Any]) -> Any:
        return max(abs(a[i] - b[i]) for i in range(3)) / t02.S3

    ok(
        "MR-A: Anderson from 1.1 t* lands within DELTA_ROOT of S1",
        run_a.outcome == "CONVERGED" and dist_scaled(run_a.x, s_one) <= DELTA_ROOT,
    )
    ok(
        "MR-B: from t* the solve converges at iteration 0 on t*",
        run_b.outcome == "CONVERGED"
        and run_b.iterations == 0
        and dist_scaled(run_b.x, t_star) == 0,
    )
    ok(
        "MR-C: substitution from 1.1 t* stagnates at 20 and the merge's Newton lands on S1",
        run_c_sub.outcome == "RECYCLE_STAGNATION"
        and run_c_sub.iterations == 20
        and merge_outcome == "CONVERGED"
        and dist_scaled(merge_x, s_one) <= DELTA_ROOT,
    )
    bounds = {}
    for name, root in (("t*", t_star), ("S1", s_one)):
        inverse = (eye(3) - rec05_jacobian(root)) ** -1
        bounds[name] = inf_norm_rows(inverse) * t02.TEAR_TOL / t02.S3
    separation = dist_scaled(s_one, t_star)
    ok(
        "DELTA_ROOT >= 10 x twice the largest first-order solution-error bound (REC-05)",
        DELTA_ROOT >= 10 * 2 * max(bounds.values()),
    )
    ok(
        "DELTA_ROOT <= 1e-2 x the scaled separation of t* and S1",
        DELTA_ROOT <= mpf("1e-2") * separation,
    )
    t02_allowance_scaled = max(
        mpf("3.1e-7") / SCALE_FLOW,
        mpf("1e-5") / SCALE_TEMPERATURE,
        mpf("0.1") / mpf(10) ** 5,
        mpf("1e-2") / SCALE_ENERGY,
    )
    ok(
        "DELTA_ROOT >= 10 x twice T02 §6.4's largest scaled state allowance (SYN-001 roots)",
        DELTA_ROOT >= 10 * 2 * t02_allowance_scaled,
    )
    # ---- T02's registered successes (guess 358 K) are unchanged by the contract --------------
    t02_successes: dict[str, Any] = {}
    #: T02's evidence manifest at b68585f (A28, A29: 3, 4, 3 iterations) -- measured on the
    #: implementation. The T02 specification's own "measured 4" for -355 was the prototype's.
    measured_t02 = {355: 3, 360: 3, 365: 4}
    for temp in (355, 360, 365):
        out = solve(358, q_flash_at(mpf(temp)))
        results[f"T02 success {temp}"] = out
        t02_successes[f"SYN-001-A02-{temp} (guess 358 K)"] = {
            "outcome": out.outcome,
            "attempts": len(out.attempts),
            "core_iterations": out.attempts[-1].run.iterations,
            "t02_measured_iterations": measured_t02[temp],
            "landings": sum(len(a.run.landings) for a in out.attempts),
        }
        ok(
            f"T02 A28/A29 under the contract: Q({temp} K) from 358 K converges in one attempt",
            out.outcome == "CONVERGED"
            and len(out.attempts) == 1
            and out.x is not None
            and abs(out.x["T"] - temp) < mpf("1e-5"),
        )
        ok(
            f"T02 A28/A29 under the contract: Q({temp} K) from 358 K lands nothing on a bound",
            t02_successes[f"SYN-001-A02-{temp} (guess 358 K)"]["landings"] == 0,
        )
        ok(
            f"the twin reproduces the implementation's measured count for Q({temp} K) from 358 K",
            out.attempts[-1].run.iterations == measured_t02[temp],
        )
    ok(
        "the three A02-360 routes (358 K, PHS-02, PHS-03) meet at one root within DELTA_ROOT",
        all(
            results[c].x is not None
            and abs(results[c].x["T"] - 360) / SCALE_TEMPERATURE <= DELTA_ROOT
            for c in (
                "SYN-001-A02-360-liquid-guess",
                "SYN-001-A02-360-vapor-guess",
                "T02 success 360",
            )
        ),
    )

    multiple_roots = {
        "REC-05 gamma=0.1": {
            "t_star": [s(v) for v in t_star],
            "S1": [s(v) for v in s_one],
            "scaled_separation": s(separation),
            "first_order_solution_error_bound_scaled": {k: s(v, 8) for k, v in bounds.items()},
            "MR-A": {
                "method": "anderson",
                "start": "1.1 t*",
                "outcome": run_a.outcome,
                "iterations": run_a.iterations,
                "lands_on": "S1",
                "final_t": [s(v) for v in run_a.x],
            },
            "MR-B": {
                "method": "anderson",
                "start": "t*",
                "outcome": run_b.outcome,
                "iterations": run_b.iterations,
                "lands_on": "t*",
            },
            "MR-C": {
                "method": "anderson depth_max = 0, then the merge edge (T02 §4.4)",
                "start": "1.1 t*",
                "loop_outcome": run_c_sub.outcome,
                "loop_iterations": run_c_sub.iterations,
                "best_iterate_index": best,
                "merge_outcome": merge_outcome,
                "merge_newton_iterations": merge_iterations,
                "lands_on": "S1",
                "final_t": [s(v) for v in merge_x],
            },
        },
        "fingerprint": {
            "policy": "T03-root-fingerprint-v1",
            "delta_scaled_inf": s(DELTA_ROOT, 3),
            "t02_state_allowance_scaled_max": s(t02_allowance_scaled, 6),
        },
    }

    # ---- measured: the same twin in 53-bit arithmetic (the floor the tolerances sit above) ----
    measured: dict[str, Any] = {
        "note": "The registered contract simulated again with mp.prec = 53 (binary64-like), "
        "compared with the 40-digit run. A floor of the algorithm, not of the implementation; "
        "labelled, never an expectation.",
    }
    if low_precision_floor:
        saved = mp.prec
        try:
            reference_runs = {
                c: results[c]
                for c in ("SYN-001-A02-355-liquid-guess", "SYN-001-A02-360-liquid-guess")
            }
            mp.prec = 53
            for case_id, reference in reference_runs.items():
                q = q_specs[PHS_CASES[case_id]["T_heater"]]
                low = solve(PHS_CASES[case_id]["guess"], +q)
                worst_t = mpf(0)
                for att_ref, att_low in zip(reference.attempts, low.attempts, strict=True):
                    for tr_ref, tr_low in zip(att_ref.run.trials, att_low.run.trials, strict=True):
                        worst_t = max(
                            worst_t,
                            abs(tr_ref.temperature - tr_low.temperature) / tr_ref.temperature,
                        )
                assert low.x is not None and reference.x is not None
                measured[case_id] = {
                    "same_outcome_attempts_and_counts": low.outcome == reference.outcome
                    and [(a.regime, a.run.iterations) for a in low.attempts]
                    == [(a.regime, a.run.iterations) for a in reference.attempts],
                    "worst_relative_trial_T_difference": s(worst_t, 3),
                    "final_T_difference_K": s(abs(low.x["T"] - reference.x["T"]), 3),
                }
        finally:
            mp.prec = saved
        for case_id in ("SYN-001-A02-355-liquid-guess", "SYN-001-A02-360-liquid-guess"):
            ok(
                f"{case_id}: 53-bit arithmetic reproduces the attempts and counts",
                bool(measured[case_id]["same_outcome_attempts_and_counts"]),
            )
            ok(
                f"{case_id}: 53-bit trial temperatures agree to 1e-12 relative (1e-9 registered)",
                mpf(measured[case_id]["worst_relative_trial_T_difference"]) < mpf("1e-12"),
            )

    document = {
        "constants": {
            "admissibility_epsilon": s(ADMISSIBILITY_EPSILON, 3),
            "phase_wall_patience": PHASE_WALL_PATIENCE,
            "stagnation_window": STAGNATION_WINDOW,
            "max_attempts": MAX_ATTEMPTS,
            "step_halvings_max": STEP_HALVINGS_MAX,
            "provider_temperature_domain_K": [280, 440],
            "delta_root_scaled_inf": s(DELTA_ROOT, 3),
        },
        "closed_form": {
            "S3_n_mol_per_s": [s(v) for v in N3],
            "S3_bubble_point_K": s(T_BUBBLE),
            "S3_dew_point_K": s(T_DEW),
            "Q_flash_spec_W": {f"T_heater={t}K": s(q) for t, q in q_specs.items()},
            "branch_roots": {
                f"T_heater={t}K": {k: s(v) for k, v in roots.items()}
                for t, roots in branch_roots.items()
            },
            "region_shapes_rows_by_columns": shapes,
        },
        "policy_simulation": {
            "cases": cases,
            "ablations": ablations,
            "t02_rules_cross_check": t02_cross,
            "basin_margin": basin,
            "family_scan": scan,
            "synthetic_tear_seeds": seeds,
        },
        "t02_successes_under_the_contract": t02_successes,
        "multiple_roots": multiple_roots,
        "measured": measured,
        "checks_passed": checks,
    }
    return document


def t02_s1() -> tuple[Any, ...]:
    """S1 of REC-05 gamma = 0.1 by Newton from T02's registered digits (a closed-form root)."""
    from mpmath import findroot

    g = rec05_map()

    def res(a: Any, b: Any, c: Any) -> list[Any]:
        y = g((a, b, c))
        return [y[0] - a, y[1] - b, y[2] - c]

    root = findroot(res, (mpf("3.8887"), mpf("2.5769"), mpf("3.1111")))
    return (root[0], root[1], root[2])


def emit(path: Path, document: dict[str, Any]) -> str:
    header = {
        "generated_by": "docs/derivations/scripts/t03_reference.py (design lane, T03): closed "
        "forms of SYN-001 through syn001_reference.py and t02_reference.py, and the T03 "
        "phase-attempt contract simulated at 40 digits from its statement in "
        "T03-phase-controller-spec.md §4",
        "specification": "docs/derivations/T03-phase-controller-spec.md",
        "independence": "no solver, graph-layer, oracle or process_runtime code was used. "
        "`closed_form` values are expectations; `policy_simulation` values are definition-level "
        "references (the same contract, derived a second time); `measured` is labelled and never "
        "an expectation.",
    }
    text = yaml.safe_dump({**header, **document}, sort_keys=False, allow_unicode=True, width=110)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="re-derive every identity and print the checks"
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit PATH")
    document = build()
    if args.check:
        for name in document["checks_passed"]:
            print(f"ok  {name}")
        print(f"{len(document['checks_passed'])} checks passed")
    if args.emit:
        digest = emit(Path(args.emit), document)
        print(f"wrote {args.emit}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
