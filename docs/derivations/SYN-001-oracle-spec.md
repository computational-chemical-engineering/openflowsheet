# SYN-001 oracle specification

**Package:** P01. Specification by Fable 5.1; implementation and tests by Opus 5 against this specification; verification of K-values, r = 0.5 oracle values, and every variant's phase state by Fable (plan §8.1 day 2).  
**Derivation:** `docs/derivations/SYN-001.md`. **Reference values:** `benchmarks/syn001/reference_values.yaml` (Fable-authored, independent of the implementation).  
**Location:** `benchmarks/syn001/oracle.py`, importable as `benchmarks.syn001.oracle`. It must not import anything from `process_runtime` (plan §3.2: "Implement the oracle separately from the production flash/recycle solver"). Pure Python plus `math`; NumPy optional. No mutable global state.

## 1. Public interface

```python
from dataclasses import dataclass
from typing import Literal, Sequence

PhaseState = Literal["LIQUID", "VAPOR", "TWO_PHASE", "ZERO_FLOW"]

@dataclass(frozen=True)
class Syn001Constants:
    R: float = 8.31446261815324
    T_r: float = 300.0
    P_r: float = 100_000.0
    c_p: tuple[float, float, float] = (100.0, 100.0, 100.0)
    T_b: tuple[float, float, float] = (320.0, 360.0, 400.0)
    L: tuple[float, float, float] = (25_000.0, 30_000.0, 35_000.0)
    v: tuple[float, float, float] = (1e-4, 1e-4, 1e-4)
    M: tuple[float, float, float] = (0.100, 0.100, 0.100)
    T_min: float = 280.0; T_max: float = 440.0
    P_min: float = 50_000.0; P_max: float = 200_000.0

class DomainError(ValueError): ...      # T or P outside the declared domain; message names the offending value

def k_values(T: float, P: float, c: Syn001Constants = ...) -> tuple[float, float, float]
def h_liquid(T: float, P: float, c=...) -> tuple[float, float, float]   # J/mol per component
def h_vapor(T: float, P: float, c=...) -> tuple[float, float, float]
def g_liquid(T: float, P: float, c=...) -> tuple[float, float, float]
def g_vapor(T: float, P: float, c=...) -> tuple[float, float, float]
def stream_enthalpy_flow(n: Sequence[float], T: float, P: float, phase: Literal["LIQUID","VAPOR"], c=...) -> float  # W; exactly 0.0 for zero n

@dataclass(frozen=True)
class TPFlashResult:
    state: PhaseState
    beta: float                      # vapor fraction V/F_tot; 0.0 for LIQUID, 1.0 for VAPOR; nan for ZERO_FLOW
    V: float; L: float               # mol/s
    vapor: tuple[float, float, float]   # component flows, mol/s (exact zeros when absent)
    liquid: tuple[float, float, float]
    x: tuple[float, float, float] | None   # None when L == 0 (composition undefined, ADR 0001 D3)
    y: tuple[float, float, float] | None   # None when V == 0
    K: tuple[float, float, float]
    sum_zK: float; sum_z_over_K: float     # nan for ZERO_FLOW
    rr_residual: float                     # RR(beta) at the returned beta; 0.0 for single-phase/zero-flow
    iterations: int

def tp_flash(n: Sequence[float], T: float, P: float, c=...) -> TPFlashResult

@dataclass(frozen=True)
class RecycleOracleResult:
    case_id: str
    r: float; T_flash: float; T_heater: float; P: float
    flash: TPFlashResult                  # single flash of the FRESH feed at (T_flash, P): the r-invariant core
    q: float | None                       # V/L; None when L == 0
    recycle: tuple[float, float, float]; purge: tuple[float, float, float]; vapor_product: tuple[float, float, float]
    recycle_state: PhaseState; purge_state: PhaseState; vapor_product_state: PhaseState
    mixed_feed: tuple[float, float, float]
    T_mix: float                          # analytic adiabatic-mixer temperature (derivation §4.1)
    mixer_outlet_state: PhaseState        # phase state of the mixed feed at (T_mix, P); must be LIQUID for the v0.0 mixer domain
    sum_zK_at_T_mix: float
    heater_outlet: TPFlashResult          # TP flash of the mixed feed at (T_heater, P)
    Q_heater: float; Q_flash: float       # W, positive into the unit
    H_fresh: float; H_recycle: float; H_mixed: float; H_heater_out: float; H_flash_out: float; H_products: float  # W
    balance_residual: tuple[float, float, float]   # F_i - vapor_product_i - purge_i
    energy_residual: float                 # Q_heater + Q_flash - (H_products - H_fresh)

def recycle_oracle(F: Sequence[float], r: float, T_flash: float, *, T_heater: float = 350.0, P: float = 100_000.0,
                   T_feed: float = 300.0, case_id: str = "", c=...) -> RecycleOracleResult

def linear_recycle(f: Sequence[float], r: float) -> tuple[float, ...]   # t = f/(1-r); ValueError if r >= 1
```

Requirements on `r`: 0 ≤ r < 1; r ≥ 1 raises `ValueError` (the overall balance has no steady state). Requirements on `F`: finite, all F_i ≥ 0; negative raises `ValueError`; all-zero is a valid `ZERO_FLOW` case.

## 2. Algorithms (normative)

1. `k_values`: the closed form of derivation §3, evaluated exactly as written (`P_r/P * exp((L_i/R)*(1/T_b_i − 1/T) + v_i*(P − P_r)/(R*T))`). Domain check first; raise `DomainError` outside [T_min, T_max] × [P_min, P_max]. No caching.
2. `tp_flash` (derivation §5.1):
   - F_tot = Σ n_i. If F_tot == 0 exactly: return `ZERO_FLOW` with all flows 0.0, `x = y = None`, `beta = nan`, `iterations = 0`. Never divide by F_tot before this test.
   - z_i = n_i/F_tot. Active set A = {i : n_i > 0}. Compute Σ_A z_i K_i and Σ_A z_i/K_i.
   - If Σ zK ≤ 1: `LIQUID`, beta = 0.0, liquid = n, vapor = (0,0,0), x = z, y = None.
   - Else if Σ z/K ≤ 1: `VAPOR`, beta = 1.0, vapor = n, liquid = (0,0,0), y = z, x = None.
   - Else `TWO_PHASE`: solve RR(β) = Σ_A z_i (K_i − 1)/(1 + β(K_i − 1)) = 0 on the bracket (max(0, 1/(1 − K_max,A)), min(1, 1/(1 − K_min,A))) with K_max,A/K_min,A over the active set only. Use bisection to a bracket width ≤ 4 ulp, or safeguarded Newton (bisection fallback whenever the Newton step leaves the bracket) to |RR| ≤ 1e-15 and bracket width ≤ 1e-15; record `iterations`. Then x_i = z_i/(1 + β(K_i − 1)), y_i = K_i x_i for i ∈ A and exactly 0.0 otherwise; V = β F_tot, L = F_tot − V; vapor_i = V y_i, liquid_i = L x_i.
   - Never evaluate `log` of a composition. Never renormalize x or y; report them as computed (Σ x = Σ y = 1 to rounding is a test, not an enforced projection).
3. `recycle_oracle` (derivation §5–§7):
   - `flash = tp_flash(F, T_flash, P)`, the single TP flash of the fresh feed. By recycle invariance (derivation §5.1) this flash gives the *external* split directly: vapor_product = flash.vapor (V and y), and purge = flash.liquid, because purge_i = (1 − r) L x_i with L = F_tot (1 − β)/(1 − r) equals (1 − β) F_tot x_i. Then recycle_i = r/(1 − r) · purge_i and L = purge_tot + recycle_tot; q = V/L when L > 0 else None. States: a stream with total flow exactly 0.0 is `ZERO_FLOW`; otherwise recycle and purge are `LIQUID`, vapor product `VAPOR`.
   - mixed_feed = F + recycle. T_mix = (F_tot·T_feed + recycle_tot·T_flash)/(F_tot + recycle_tot) (valid because both streams are liquid with equal c_p at the same P; assert this precondition: T_flash within domain and flash liquid exists or recycle is zero). If recycle is `ZERO_FLOW`, T_mix = T_feed.
   - mixer_outlet_state = `tp_flash(mixed_feed, T_mix, P).state`; sum_zK_at_T_mix from that call.
   - heater_outlet = `tp_flash(mixed_feed, T_heater, P)`.
   - Enthalpies with `stream_enthalpy_flow`: H_fresh = liquid at T_feed; H_recycle = liquid at T_flash (0.0 if zero flow); H_mixed = H_fresh + H_recycle (adiabatic mixer, by definition); H_heater_out = vapor part at T_heater + liquid part at T_heater from `heater_outlet`; H_flash_out = vapor product at T_flash + (recycle + purge) liquid at T_flash; H_products = vapor product + purge. Q_heater = H_heater_out − H_mixed; Q_flash = H_flash_out − H_heater_out.
   - balance_residual and energy_residual as declared. These are computed, never asserted, inside the oracle; tests assert them.
4. `linear_recycle`: t_i = f_i/(1 − r).

## 3. Registered fixture inputs

`benchmarks/registry.yaml` (created in P01, extended later) registers the family `SYN-001` with the five variants of derivation §7 plus the two outcome-type cases:

| case_id | r | T_flash | expected | class |
| --- | --- | --- | --- | --- |
| SYN-001-nominal | 0.5 | 360 | oracle values | nominal, recycle (counts once with the other r-variants) |
| SYN-001-once-through | 0 | 360 | oracle values; heater outlet TWO_PHASE; recycle ZERO_FLOW | phase appearance |
| SYN-001-high-recycle | 0.95 | 360 | oracle values; Q_heater < 0 | throughput scaling; registered PTC basin comparison (T04) |
| SYN-001-all-liquid-310K | 0.5 | 310 | flash LIQUID; vapor product ZERO_FLOW; heater outlet TWO_PHASE | single-phase endpoint |
| SYN-001-all-vapor-420K | 0.5 | 420 | flash VAPOR; liquid/purge/recycle ZERO_FLOW; heater outlet TWO_PHASE | single-phase endpoint |
| SYN-001-conflicting-heater-spec | 0.5 | 360 | validation rejects: T_out and Q both fixed | invalid specification (outside success denominator) |
| SYN-001-capped-budget | 0.5 | 360 | typed BUDGET_EXHAUSTED, no certificate | budget failure (outside success denominator) |
| NUM-02-linear-recycle | 0.5 and 0.95 | — | t = (2,2,2), (20,20,20) | analytic recycle |

Each entry carries: fresh feed, T_feed, T_heater, P, the tolerances of derivation §9, the scales, the registered initializer, `oracle: benchmarks.syn001.oracle.recycle_oracle`, `reference: benchmarks/syn001/reference_values.yaml`, `independence: "algebraic reference for the synthetic model; not an experimental validation or a simulator benchmark"`, and `budgets: {property_calls: 10000, newton_iterations: 50 per attempt, attempts: 5}` as preregistered defaults (blueprint §13.4; refined in K03).

## 4. Required tests (`tests/test_syn001_oracle.py`, plus `tests/test_syn001_reference_values.py`)

Tolerances below are for comparing the double-precision oracle with the 20-digit reference strings (parsed as float): relative 1e-13 or absolute 1e-14, whichever is looser, unless stated.

A. **Thermodynamic identities** (numerical, on a grid of at least 5 T × 3 P points spanning the domain, all components):
   1. h = g − T ∂g/∂T with a fourth-order central finite-difference stencil on g (step 0.1 K, tolerance 1e-7 J/mol) for both phases. *Amended 2026-09-07 (Fable):* the originally specified pair (second-order central difference, step 1e-3 K, tolerance 1e-6 J/mol) was a specification error, since with |g| ≈ 2.5e4 J/mol the roundoff of the difference quotient times T is itself ≈ 1e-6 J/mol; Opus measured a worst error of 1.4e-6 J/mol and no second-order step meets 1e-6 J/mol on this domain. The fourth-order stencil at 0.1 K keeps both truncation and roundoff below 2e-9 J/mol and the identity holds with about a 50-fold margin; the exact identity is separately verified at 40 digits in `docs/derivations/scripts/syn001_reference.py --check`.
   2. K_i = exp[(g_i^L − g_i^V)/(RT)] agrees with `k_values` to 1e-13 relative.
   3. K_i(T_b,i, P_r) = 1 to 1e-14; h_i^V − h_i^L = L_i at P_r to 1e-9 J/mol.
   4. `k_values` at every `K_values` entry of `reference_values.yaml`.
   5. `DomainError` at T = 279.999 K, 440.001 K, P = 49 999 Pa, 200 001 Pa; no error at the four corners.
B. **Plan sanity values:** K(360 K, P_r) = (2.8406442066, 1, 0.3105797512) to 1e-10 absolute; bubble point of the equimolar feed at P_r (found by a test-local bisection on Σ zK = 1) = 347.44118198144 to 1e-9 K; Σ zK(350 K) = 1.07031421908 to 1e-10.
C. **TP flash:** for each variant's mixed feed at (350 K, P_r) and fresh feed at (T_flash, P_r): state, beta, x, y, V, L against the reference; Σ x = 1 and Σ y = 1 to 1e-14 (when defined); RR residual ≤ 1e-14; component balance vapor + liquid = feed exactly (to 1e-15 relative); zero feed → `ZERO_FLOW` with `x is None and y is None`; feed (1, 0, 1) → x_B = y_B = 0.0 exactly and no exception; feed (0, 1, 0) at 360 K (pure B at its boiling point, K_B = 1 exactly) → Σ zK = 1 ≤ 1, so the classification order gives `LIQUID` with beta = 0.0; the test documents this boundary convention; feed (1, 1, 1) at the bubble point found by the test-local bisection → state ∈ {LIQUID, TWO_PHASE} with beta ≤ 1e-12 (rounding decides which side of the boundary; the test asserts only that no exception occurs and beta is at the boundary).
D. **Recycle oracle, r = 0.5 nominal:** q, L, V, x, y against the plan §3.2 digits (1e-10 absolute) and the 20-digit reference (1e-13 relative); recycle, purge, vapor product, mixed feed, T_mix, Q_heater, Q_flash, and all H_* against the reference; balance_residual ≤ 1e-14 mol/s; energy_residual ≤ 1e-9 W; every registered tolerance of derivation §9 satisfied with margin (assert |residual| < 0.01 × tolerance).
E. **Every registered variant:** all phase states in `reference_values.yaml` (`flash_phase_state`, `recycle_phase_signature`, `vapor_product_phase_signature`, `purge_phase_signature`, `mixer_outlet_state`, `heater_outlet_state`) match exactly; every numeric field matches the reference; Q_heater at r = 0.95 is negative; zero-flow streams are exactly `0.0` in every component (not merely small).
F. **Recycle-invariance metamorphic check:** for r ∈ {0, 0.5, 0.95, 0.99}: vapor product, x, y identical across r to 1e-13 relative; L(r)·(1 − r) constant to 1e-13 relative; Q_heater + Q_flash identical across r to 1e-9 W.
G. **Energy closure per variant:** Q_heater + Q_flash − (H_products − H_fresh) ≤ 1e-9 W; the closed form c_p (T_flash − T_feed) F_tot + V Σ y_i L_i matches to 1e-9 W.
H. **Mixer domain margin:** 1 − sum_zK_at_T_mix positive for r ∈ {0, 0.5, 0.9, 0.95, 0.99, 0.999} and matches the `domain_boundaries` table to 1e-10.
I. **Linear recycle:** values; r = 1 raises.
J. **Argument validation:** negative F_i, r < 0, r ≥ 1, nonfinite inputs raise `ValueError`; none of these are silently corrected.
K. **Independence guard:** a test asserts that `benchmarks.syn001.oracle` does not import `process_runtime` (inspect `sys.modules` after a fresh import in a subprocess, or scan the source for the string).
L. **Reference file integrity:** `reference_values.yaml` parses; every variant `case_id` appears in `benchmarks/registry.yaml`; no angle-bracket placeholders; sha256 of the file recorded in the P01 evidence manifest.

## 5. Out of scope for the oracle

No derivatives (P02 uses the closed forms of derivation §3 in its own harness), no PH flash, no non-equimolar-c_p mixer (T_mix formula asserts its precondition), no pressure drops, no property caching, no `process_runtime` types. The oracle is the reference for K02–K04 comparisons; it is not the production solver and must never be called from production code paths.
