# S07 — near-critical saturation and the (T_σ,max, T_c) strip (design note, Q-B4)

Design lane, 2026-10-23. Brief: `docs/briefs/S07-near-critical-saturation.md`. Branch `wp/S07`. No production code.
Prototype and measurements: scratch only (`proto/fallback.py`, `scan1.py`, `strip.py`; numbers below). This note
stands alone.

## 1. Problem and scope

`CoolPropHeosProvider._solve_saturation` (`src/openflowsheet/thermo/coolprop_heos.py:587`) is S05 §3.5's Newton in
(δ', δ'') on F1 = J' − J'' and F2 = K' − K'' (J = δ(1 + δαʳ_δ) = p/(ρ_red R T), K = αʳ + δαʳ_δ + ln δ), seeded by
CoolProp's JSON ancillaries with the EOS T_c in θ (B-19). It returns `None` when an iterate leaves ρ' > ρ_c > ρ'' > 0
or after `MAX_ITERATIONS` = 50. Near T_c it fails, and the provider uses the saturation in two places that fail with it:

1. **T ≤ T_σ,max = T_c(1 − 2e-4):** the phase rule, `Psat`, and the `Tsat` bounds (p_σ(T_σ,max)) and iterates.
2. **The strip (T_σ,max, T_c) outside the near-critical box:** the label does not use the saturation (`_rule`), but
   `_evaluate` (`:899-903`) fetches it for the density bracket and refuses `saturation_not_converged` if it is `None`.

**In scope:** a generic fix of both, for all 123 fluids; whether S05 (`iapws95.py`) needs it; θ_min; identity plan;
work orders; gates. **Out of scope:** mixtures, cryogenic liquids (S07b), binding, F-6 (A17 floor) and B-15 (bounds
reading): this design does not touch them, and their rulings stay with the spec amendment round.

## 2. Measured facts that decide the design

All with CoolProp 8.0.0, x86-64, the provider's own `_jet`; θ = 1 − T/T_c.

- **M1 — where the plain Newton fails.** At θ ≥ 2e-4: Cyclopentane (from 2e-3), R1234ze_Z (1e-3), R134a (5e-4), MDM, MM,
  R14 (2e-4). Count of the 123 failing at θ = 1e-4, 5e-5, 2e-5, 1e-5, 1e-6: 9, 12, 15, 27, 57. Never at θ ≥ 5e-3.
- **M2 — seeds can be unusable.** MM's `rhoL` seed is 1336 mol/m³ < ρ_c = 1653 at θ = 1e-5, 795 at 1e-6, and
  **negative** at 1e-7 (−25.9) and 1e-8 (−1139). A negative seed makes `_jet` raise `coolprop_evaluation_failed`, so
  today such a state refuses `error`, not `saturation_not_converged`.
- **M3 — the Maxwell root has a double-precision floor.** The same 2-D Newton from two different seeds (ancillary vs
  the fallback of §4.2) converges to roots differing by at most 1.5e-12 (θ = 3e-2), 9.4e-12 (2e-3), 4.2e-10 (2e-4),
  1.2e-9 (1e-4), 1.3e-9 (5e-5), 3.0e-9 (2e-5) relative. The largest accepted final step (R-595's floor clause) is
  4.6e-10 at 2e-4, 1.1e-9 at 1e-4, 3.5e-9 at 5e-5, 1.4e-8 at 2e-5 — √ε = 1.49e-8 is reached at θ ≈ 2e-5. Below,
  the polish fails: 1 fluid at 3e-6, 8 at 1e-6, 67 at 3e-7. This is the expected ε·θ^(−3/2) scaling (loop height
  ∝ θ^(3/2), ∂p/∂ρ ∝ θ). Consequence: spec §6.3's "a seed affects the iteration count, never the converged value"
  holds only to this floor.
- **M4 — multiparameter EOS have extra loops away from T_c.** (∂p/∂ρ)_T at ρ_c is *positive* (ρ_c lies in an inner
  stable wiggle) at θ = 3e-2 for 29 fluids (H2O, CO2, N2, Ar, CH4, C2H6, C3H8 among them), at 1e-2 for 9, at 5e-3 for
  2 (Ammonia, o-Xylene), and for none at θ ≤ 2e-3. A ρ_c-anchored, single-loop argument is valid only near T_c.
- **M5 — prototype fallback (§4.2, outer loop Newton instead of bisection).** Wherever the plain Newton fails at
  θ ≥ 1e-5, the fallback plus the unchanged 2-D Newton as polish converges: 0 failures in 123 fluids × 15 θ;
  ≤ 7 polish iterations at θ ≥ 2e-5; 118–163 jets for the seed stage; whole scan 6 s.
- **M6 — the strip without saturation.** The T ≥ T_c bracket (0, ρ_max] started at min(P/RT, ρ_max), at 2952 strip
  states (123 fluids × θ ∈ {1.9999e-4, 1e-4, 5e-5, 1e-5, 1e-6, 1e-8} × {LIQUID at p_c(1+8e-3)(1+1e-12) and P_hi,
  VAPOR at p_c(1−4e-3)(1−1e-12) and P_lo}): all converge, (∂p/∂ρ)_T > 0 at the root, |p/P − 1| ≤ 1e-9. Against the
  saturation-bracketed answer where that exists: 894 differ, by ≤ 2.2e-12 relative, all LIQUID (different start);
  VAPOR is bitwise equal (same start, min(P/RT, ρ'') = P/RT).
- **M7 — S05 has the strip defect (merged code).** `iapws95._saturation` converges at θ ∈ {1.5e-4 … 1e-5} (≤ 7
  iterations) and 3e-6 (16), fails at ≤ 1e-6. Public answers: at 647.0954, 647.0959 and 647.09599 K, LIQUID at 25 MPa
  and VAPOR at 20 MPa (outside the box [22.0, 22.2] MPa) all refuse `saturation_not_converged`, while 647.09 K and
  647.096 K answer. Changing S05's strip bracket unconditionally would move the registered `NC_liquid` (647.05 K,
  22.3 MPa) by 20 ulp (2.6e-15); `NC_vapour` would not move.

## 3. Constraints and invariants

- CoolProp only as a Helmholtz evaluator at (T, ρ) (ADR 0046); no flash on the exact path. Pure Python.
- Residual and Jacobian describe the same function; the saturation cache keys on the exact double T (unchanged).
- **Identity:** every state either provider answers today keeps its answer bitwise (S05's registered records,
  `s05_reference.json`, the S05 manifest, S07's tier-A tests, A25). New code may run only on paths that today return
  `None` or a refusal.
- No per-fluid tolerances, constants or fits; no fluid dropped; an unanswerable state is a typed refusal.
- The acceptance test of a saturation state is one rule for every path: the 2-D Newton's R-595 convergence with
  ρ' > ρ_c > ρ'' > 0 throughout (`_converged`, `STEP_TOLERANCE` = 4ε, `FLOOR_ONSET` = 2^−26).

## 4. The decision

### 4.1 Summary

- **D1 — fallback, not replacement.** `_solve_saturation(T)` runs today's Newton first, byte-for-byte. Only if it
  returns `None` and θ ≥ θ_min does a **spinodal-bracketed one-dimensional solve in pressure** compute new seeds, from
  which the **same** 2-D Newton loop (the polish) runs. A fallback result is accepted by the same rule as a plain one,
  plus an outer-branch check (§4.2 step 7).
- **D2 — seed positivity guard.** If a seed density is not finite and positive, the plain Newton is skipped (it would
  raise in `_jet`, M2), and D1's fallback is tried. Inert: no such state answers today.
- **D3 — the strip uses the saturation if there is one, else the T ≥ T_c bracket.** In (T_σ,max, T_c), when
  `self._saturation(t)` is `None`, `_density` is called with `saturation=None` — the existing supercritical bracket
  (0, ρ_max] from min(P/RT, ρ_max) — instead of refusing. Inert: that branch replaces a refusal only.
- **D4 — θ_min = 5e-5** (new module constant `THETA_FALLBACK_MIN: Final = 5e-5`, with θ = 1 − T/T_c computed as
  `1.0 - temperature / fluid.t_c`).
- **D5 — S05 adopts D3 only**, in its own commit. It does not need D1/D2 (its IAPWS ancillaries converge on its whole
  saturation range, M7; gate G7 proves it on a dense grid).

### 4.2 The fallback (D1), exactly

Inputs: T with θ ≥ θ_min, the fluid's ρ_c, ρ_max, ρ_red, R, the ancillary seeds. Notation: `k(ρ)` = 1 + 2δαʳ_δ +
δ²αʳ_δδ = (∂p/∂ρ)_T/(RT) (from `_jet`), `p(ρ)` from `_pressure`, `K(ρ)` = αʳ + δαʳ_δ + ln δ. Every loop has a fixed
bound; any failure returns `None` (→ the existing `saturation_not_converged` refusal).

1. **Anchor.** Require k(ρ_c) < 0. (Near T_c this is k_T·(T − T_c) < 0 because §6.1's ρ_c is the EOS's own critical
   density; M4 shows it fails only at θ ≥ 5e-3, where the plain Newton has never failed.)
2. **Vapour point.** ρ_a = min(seed ρ'', ρ_c/2) if the seed is finite and positive, else ρ_c/2; halve ρ_a while
   k(ρ_a) ≤ 0, at most 64 times.
3. **Spinodals by bisection on the sign of k**, exactly 52 halvings each, keeping the end with k > 0:
   ρ_vb from [ρ_a, ρ_c] (keep the low end's side), ρ_lb from [ρ_c, ρ_max] (keep the high end's side). Requires
   k(ρ_max) > 0 (spec C8 already claims it). 52 halvings make the interval ≤ ε·ρ_c, so P_b below is p_sV to rounding.
4. **Pressure bracket.** P_a = p(ρ_lb), P_b = p(ρ_vb); require 0 < P_a < P_b.
5. **End signs.** F(P) = K(ρ_L(P)) − K(ρ_V(P)), where ρ_V(P) = `_bracketed_density(T, P, 0.0, ρ_vb, start)` and
   ρ_L(P) = `_bracketed_density(T, P, ρ_lb, ρ_max, start)`. At P_b use ρ_V = ρ_vb; at P_a use ρ_L = ρ_lb. Require
   F(P_a) > 0 > F(P_b). (Under single-loop k this is the equal-area theorem: F(P_b) = ∫(1/ρ_L − 1/ρ_mid) dJ < 0 over
   the unstable branch, and symmetrically F(P_a) > 0. The test makes the bracket valid whatever the EOS does.)
6. **Bisection on P**: P_m = ½(P_a + P_b); evaluate F(P_m) with the inner roots warm-started from the previous inner
   roots (first time: ρ_V from min(P_m/RT, ρ_vb), ρ_L from ρ_lb); F > 0 → P_a = P_m, F < 0 → P_b = P_m, F = 0 → stop.
   Stop when P_b − P_a ≤ 2^−26·P_b; at most 64 halvings. Any inner `None` → `None`. Seeds: the inner roots at the
   final P_m.
7. **Polish and acceptance.** Run the existing 2-D Newton loop from (δ_L, δ_V) = (ρ_L, ρ_V)/ρ_red, with the same
   bracket test, `_converged` and `MAX_ITERATIONS`; p_σ from the vapour as now. Additionally require ρ' ≥ ρ_lb and
   ρ'' ≤ ρ_vb at the result (both phases on the outer, mechanically stable branches).

Refactor needed: the 2-D Newton loop becomes a private method `_maxwell_newton(temperature, dl, dv)` called by both
paths with no change to its arithmetic (same operation order — identity depends on it). `_Saturation` gains no field;
the iteration count recorded is the polish's count (diagnostics may log `fallback=True` in a debug path only).

**Termination.** Every loop is bounded: 64 + 2·52 + 64 outer × 2 inner × 50 + 50. **Success** is guaranteed when, at T,
k has exactly one zero in (0, ρ_c) and one in (ρ_c, ρ_max) and k(ρ_c) < 0: then both branches are monotone, F is
strictly decreasing in P (dF/dP = (1/ρ_L − 1/ρ_V)/(RT) < 0), the bracket of step 5 holds, bisection reaches 2^−26 in
≤ 64 halvings, and the polish starts within ~√ε·Z/k of the root, inside Newton's quadratic basin. The single-loop
condition is not provable for an arbitrary EOS; it is a generator claim (C-strip, §5.3) at the temperatures that
matter, and the run-time checks of steps 1, 4, 5 and 7 turn any violation into a typed refusal, never a wrong root.

### 4.3 Why θ_min = 5e-5

- Needed: the saturation must exist for θ ≥ 2e-4 (T_σ,max), plus the `Tsat` Newton's overshoot above T_σ,max, which is
  quadratic in the ancillary seed's T error (≪ 1e-6 relative). With D3 the strip never needs it.
- Possible: the polish converges reliably only while the floor (M3) is well below √ε: at 5e-5 the worst accepted step
  was 3.5e-9 ≈ √ε/4; at 2e-5 it was 1.4e-8 ≈ √ε. So 5e-5 leaves a 4× margin to T_σ,max and a 4× margin to the floor.
- Not a registered value: the tier-A strip controls are at θ = 1e-4 and Fluorine's A22 point at 3.8e-5, so no
  registered state sits on the threshold.
- **No public refusal arises from θ_min:** `Psat` above T_σ,max is already `no_saturation`; strip phase requests are
  answered by D3. Below θ_min the plain Newton still runs (identity), and if it fails the strip uses D3.

### 4.4 Rejected alternatives

- **(a) Exclude the 10 fluids.** Loses R134a, Ethanol, Neon, Cyclopentane, MM, MDM, R14, R114, Fluorine, R1234ze(Z),
  and leaves the strip gap in 48 others, tier-A O2 and H2, and S05 (M7). The generic fix is ~100 lines and measured to
  work (M5, M6). Rejected.
- **Replace the 2-D Newton by the 1-D solve everywhere.** Moves every saturation by up to the floor (4e-10 at
  T_σ,max, M3), so every registered saturation-derived value changes; the ρ_c anchor is invalid at θ ≥ 5e-3 (M4).
  Rejected.
- **Bracket-preserving step halving.** Measured (WO-S07-2b): rescues none. Rejected.
- **Continuation in θ from a converged root.** Needs a converged root at larger θ (recursion through the cache, cost
  unbounded), and has no convergence argument: a continuation seed can also leave the bracket. Rejected.
- **Critical-scaling seeds ρ' − ρ'' ∝ θ^β fitted per fluid.** New per-fluid data with an unstated validity range;
  multiparameter EOS are classical (β = ½) only very close to T_c. Rejected.
- **Symmetric/antisymmetric variables with the trivial root divided out.** A new Newton map (moves every root to the
  floor) whose divided differences cancel O(Δρ) terms; no termination gain. Rejected.
- **Strip always without saturation (cleaner single rule).** Changes 894 answered S07 strip states by ≤ 2.2e-12 and
  S05's registered `NC_liquid` by 20 ulp (M6, M7); the identity rule prefers D3. Rejected.
- **Safeguarded Newton instead of bisection in steps 3 and 6.** The prototype shows ≤ 4 outer Newton iterations
  (≈ 3× fewer jets), but bisection needs no slope, no shrink rule and no proof; the path is rare and cached (≈ 350
  jets ≈ 7 ms per new T, only where the plain Newton failed). Deferred to a measured need (Q4).

## 5. The design in detail

### 5.1 S07 provider (`coolprop_heos.py`)

- `_solve_saturation(T)`: `seeds is None` → `None` (as now). Compute seed densities. If both finite and positive,
  `result = self._maxwell_newton(T, dl, dv)`; if not `None`, return it (the plain path, untouched arithmetic). Else, if
  `1.0 - T / fluid.t_c >= THETA_FALLBACK_MIN`, return `self._maxwell_fallback(T)` (§4.2); else `None`.
- `_evaluate`, strip branch (`:899-903`): replace the refusal by "saturation stays `None`"; `_density(t, p, phase,
  None)` then takes the `T ≥ T_c` branch. The `T ≤ T_σ,max` paths (`_rule` → `None` → refusal) are unchanged.
- Docstrings: module docstring's seed paragraph gets the fallback and θ_min; `_density`'s docstring states the strip
  bracket rule.
- The flash path (`:996`) calls only `_rule`, which needs no saturation in the strip; it gets D1 through `_rule` for
  T ≤ T_σ,max and needs no D3 change. The `Psat` branch (`:915`) is unreachable in the strip (refused `no_saturation`
  at `:869`). The saturation call sites are `:650` (Tsat), `:666` (bounds), `:761` (rule), `:903` (strip), `:915`.

### 5.2 S05 provider (`iapws95.py`), own commit

- `_evaluate` (`:908-912`): the same replacement as §5.1 — a `None` saturation in the strip falls through to
  `_density(..., None)`. Its flash (`:989`) calls only `_rule`, so needs nothing. Nothing else in S05 changes; `s05_reference.json` and
  `s05_reference.py` are not touched.

### 5.3 Spec and generator

- **S07 Amendment 3** (specifier, docs-only): (i) §6.3: the saturation solve is §4.2's two-stage rule with θ_min; the
  seed sentence becomes "a seed affects the iteration count, and the converged value only within the double-precision
  floor of the Maxwell root (M3)"; (ii) the strip bracket rule D3; (iii) new generator claim **C-strip**: for every
  fluid at T ∈ {T_σ,max, T_c(1−1e-4), T_c(1−1e-6)}, k changes sign exactly twice on (0, ρ_max] (401-point grid,
  sign changes refined by bisection at 50 digits), and the spinodal pressures satisfy p_sL > p_c(1 − 4e-3) and
  p_sV < p_c(1 + 8e-3) — so the D3 root is unique for every strip state outside the box; (iv) near-critical Maxwell
  references: 50-digit (ρ', ρ'', p_σ) at θ ∈ {2e-4, 1e-4} for H2O, O2, H2, R134a, Cyclopentane, MM, R14 (the generator
  solves Maxwell at 50 digits by Newton from the provider-independent QT-free seed of its choice); (v) assertions N1–N6
  of §6 numbered by the amendment (next free ids after A44).
- **S05 erratum paragraph** (same specifier pass): S05 §4.4's strip uses the supercritical bracket when the saturation
  does not converge; registered values unchanged.

## 6. Verification gates (falsifiable, with numbers)

- **G1 — coverage (N1).** 123 fluids × T ∈ {T_lo, T_σ,max} ∪ {T_c(1 − θ): θ log-spaced 40 per decade from
  min(0.5, 1 − T_lo/T_c) to θ_min}: `_solve_saturation` is non-`None` at every point. Report fallback count and max
  polish iterations (expect ≤ 10; measured ≤ 7). Test file: tier-B broad tests at θ ∈ {2e-4, 1e-4, 5e-5}; the dense
  scan is a committed measurement script with a one-line summary.
- **G2 — identity, S07 (N2).** At every G1 point where the plain Newton converges, the result is bitwise the plain one
  and the fallback is not entered (instrumented counter = 0 there). All S07 tests that passed before pass unchanged;
  the 49 Q-B4 failures pass.
- **G3 — two-seed agreement (N3).** At G1 points where both converge (fallback forced in the test), |Δρ'|/ρ' and
  |Δρ''|/ρ'' ≤ 1e-11 for θ ≥ 1e-2 and ≤ 1e-8 for θ ≥ θ_min; |Δp_σ|/p_σ ≤ 1e-12. (Measured maxima: 1.5e-12, 1.3e-9.)
- **G4 — independent expectation (N4).** §5.3(iv)'s 50-digit roots: ρ', ρ'' within 1e-8 relative, p_σ within 1e-11.
- **G5 — strip (N5).** 123 fluids × θ ∈ {1.9999e-4, 1e-4, 5e-5, 1e-5, 1e-6, 1e-8, 1e-12} × the four M6 states: every
  answer `ok`, (∂v/∂P)_T < 0, cp > 0; continuity at T_c: at P_hi (LIQUID) and P_lo (VAPOR),
  |v(T_c(1 − 1e-12)) − v(T_c)| ≤ 1e-8·v(T_c). No `saturation_not_converged` anywhere in the strip.
- **G6 — C-strip** holds for all 123 (generator `--check`).
- **G7 — S05 (N6).** (a) All S05 tests pass and `s05_reference.py --check` passes with `s05_reference.json` unchanged;
  (b) a scratch digest of `float.hex` of every S05 registered TP, saturation, band and Tsat answer, and the outcome of
  every A14–A21 probe, is identical before and after (numbers into the S07 decisions log); (c) new probes at 647.0954,
  647.0959, 647.09599 K, LIQUID 25 MPa and VAPOR 20 MPa, answer `ok` and satisfy G5's continuity bound against
  647.096 K; (d) `iapws95._saturation` converges at every T = 273.16 + 0.05·i K up to 647.0 K and at 647.0 K
  (justifies D5).
- **G8 — cost.** The plain path gains no `_jet` call (D2 is arithmetic). Fallback ≤ 400 jets per T (count in G1).
- **G9 — merge gates.** Full `scripts/gate.sh` once before merge; CI green on both architectures. A31's platform digest,
  if generated after this change, needs no special handling (D1–D3 are inert at A03–A13's states).

## 7. Work orders (dependency order; each ≤ ~100k context)

1. **WO-S07-NC1 (design lane, `specifier`, docs-only, ~40k).** S07 Amendment 3 and the S05 erratum per §5.3, with N1–N6
   texts from §6. Acceptance: the amendment cites this note; no other section changes. May run in parallel with 2.
2. **WO-S07-NC2 (build, `opus-engineer`, ~80k).** §5.1 in `coolprop_heos.py` (refactor `_maxwell_newton` first, as its
   own commit, proved inert: the 2626 tier-B + tier-A cases give the same pass/fail and the 2577 passing answers
   bitwise; then D2 + D1; then D3), tests for N1–N3, N5. Acceptance: G1, G2, G3, G5, G8; one decisions-log entry per
   commit.
3. **WO-S07-NC3 (build, `opus-engineer`, ~40k), after 2.** §5.2 in `iapws95.py` as a single commit naming S05; N6 test;
   G7 digest script in scratch, numbers in the log; a new S05 evidence manifest for the commit. Acceptance: G7.
4. **WO-S07-NC4 (build, `opus-engineer`, ~60k), after 1.** Generator: C-strip and the 50-digit near-critical roots in
   `s07_reference.py`; regenerate `s07_reference.json`; N4 test. Acceptance: G4, G6, generator `--check`.
5. **Review** (`reviewer`, one pass over 2–4 against this note), then WO-S07-3's manifest work; G9.

## 8. Risks and open questions (each with a default)

- **Q1 (fact): single-loop between grid points.** The fallback is proved under single-loop k; C-strip and G1's dense
  grid sample it. *Default:* accept the sampled evidence; a violation would surface as a typed refusal, never a wrong
  root (steps 1, 4, 5, 7).
- **Q2 (fact): the floor on aarch64.** θ_min's margins were measured on x86-64. *Default:* same constant; CI runs the
  tier-B cases at θ ∈ {2e-4, 1e-4, 5e-5} on both architectures, which falsifies it if the floor differs.
- **Q3 (user preference): S05 fix on `wp/S07` or a separate package.** *Default:* on `wp/S07` as its own commit with
  its own S05 evidence manifest and the same reviewer pass (it is inert by construction and small). Reversible by
  reverting that commit.
- **Q4 (fact): fallback cost.** ≈ 7 ms per new T on a rare, cached path. *Default:* bisection; switch steps 3 and 6 to
  a safeguarded Newton only if a benchmark shows the fallback on a hot path.
- **Q5 (user preference): should S05 also get D1/D2?** *Default:* no — not needed by G7(d), and any S05 change costs an
  evidence cycle.
- **Q6 (fact): θ in the strip below θ_min with a plain-converged saturation.** The strip answer's last bits there come
  from the saturation bracket, elsewhere from D3 (≤ 2.2e-12 apart, M6). *Default:* accept; both are the same unique root
  within its conditioning, and the rule is deterministic in T.
- **Q7: F-6 and B-15.** Not touched by this design. *Default:* leave them to the Amendment-3 specifier pass as separate
  items.
