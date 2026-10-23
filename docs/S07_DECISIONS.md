# S07 build decisions

Build-lane choices the specification left to the engineer. Each is isolated and revertible.

## WO-S07-1a (spec §17.6)

- **B-1 (step 6): the CoolProp helper is a module beside `conftest.py`, `tests/s07_coolprop_support.py`
  (`require_coolprop()`),** following `tests/m06_browser_support.py`, not a `conftest.py` function.
  Rejected: `conftest.py`, which every test imports and which already carries unrelated helpers.
  Reversible by moving the function and its two constants.
- **B-2 (A43): the CI flag is set in the `Run checks` step's `env:` map,** not in the run script, so
  the YAML assertion reads it literally (§17.5 A43 allows step or job).

## WO-S07-1b (spec §8, §16.7; the generator)

Run: `docs/derivations/scripts/s07_reference.py` in a scratch venv (Python 3.13.5, `CoolProp==8.0.0` from
`requirements-coolprop.lock` with `--no-deps --require-hashes`, `mpmath==1.3.0`, `numpy==2.2.4`, `PyYAML==6.0.2`).

**Q-A1-4, measured (first full run, 2026-10-23): all 123 admitted fluids pass C1–C19.** No fluid fails a claim, so
no removal by amendment is needed. The 13 exclusions come out exactly as §16.1's literal list (S1 6, S2 2, S3 2,
S4 3). `dropped` is empty for every fluid, so `EXPECTED_DROPPED` is empty. T_lo, T_hi, P_hi and the bound kind
equal §16.3's table (m8's forecast) for all 123. Worst C11 agreement (CoolProp's own flash against the generator):
TP 9.5e-9 (n-Perfluorohexane, Z; bound 1e-7), NC 3.8e-7 (H2O, cp; bound 1e-5). C12 (water against S05): worst
5.8e-14 (bound 1e-12). C18: the largest relative melting slope of the M fluids with T_t >= 20 K is
6.224e-9 /Pa (Neon), so kappa = 1e-8 /Pa is 1.61x it. Output 1 115 539 bytes (C17 cap 1.5e6); the fluid table
module is 168 909 bytes. Run time at `--jobs 48`: 80–87 s wall, about 1490 s CPU (all 136 names); 312 521 claims.
`--jobs 1`: 1495 s wall, and both outputs are byte-identical to the `--jobs 48` ones (§16.7). `--check`: passes
(87 s), both files byte-identical.

Build choices (each isolated in the generator; revertible by editing the named function):

- **B-3: coefficients enter as the exact doubles CoolProp parses** (`_c`, S05's `d()`), not as the JSON's decimal
  strings at 50 digits. Exponents that are integral become Python ints (exact integer powers).
- **B-4: α°'s mixed partials are stored as exactly 0.0.** Every admitted α° type is a function of τ alone except
  the Lead term's ln δ, so α° is separable (C1 checks the types). As S05's generator did.
- **B-5: `delta_one` uses S05 §3.2's zero-jet rule in the generator** (`Eos.ar(..., zero_jet=True)`), claimed valid
  when every non-analytic term has 1/β > 3 and 2a > 3 (H2O and CO2: β = 0.3, a = 3.5). Numerical differentiation
  across |δ−1|^{10/3} at δ = 1 is not exact (S05 skipped order 3 there; it would also fail C4). With the rule, all
  20 partials are stored at `delta_one`, third order included. See Q-B2.
- **B-6: derived constants are the nearest double of the exact product** of the already-rounded double input and
  the decimal factor: T_σ,max = rnd(T_c × 0.9998), the near-critical box, 1.5·T_c, 0.1·p_c, 1.5·T_red, ….
  T_mid = rnd((T_lo + T_σ,max)/2). Ceilings (T_lo, P_hi's ⌈·⌉₂, ρ_max) use `Decimal(repr(x))`, as §16.4 says.
- **B-7: C11's lnphi** comes from a fresh `AbstractState("HEOS")` PT flash and `fugacity_coefficient(0)`, because
  `PropsSI` has no fugacity-coefficient output (it raises "Output string is invalid"). h, s, ρ, Z and cp come from
  `PropsSI`. lnphi is compared in absolute terms (1e-7; S05's lnphi admission was absolute too), h and s within
  1e-7·R·T and 1e-7·R, v, Z and cp relative. See Q-B3.
- **B-8: the density-root convergence claim is in density units**, |p − P|/(ρ·∂p/∂ρ) < 10^(8−dps). At T_lo a
  liquid's Z is about 1e-12 (1-Butene: p_σ(92.2 K) = 4.5e-6 Pa), so p/P − 1 carries about 12 digits of
  cancellation while ρ itself is converged to the working precision. For the same reason C8's saturation and
  band-edge roots are solved at 50 digits; the 41-point dp/dρ grids are evaluated at 20 digits, as S05's were.
- **B-9: seeds** come from CoolProp's own QT and PQ flashes and from `PropsSI` densities at the registered TP
  states. They affect iteration counts only; every converged root is claimed on its branch.
- **B-10: JSON layout.** Per fluid under `fluids[<id>]`: jets `{"T", "rho", "jet": [20]}` (α° then αʳ, `PhiJet`
  order); TP states `{"phase", "values": [T, P, h, s, v, Z, cp, lnphi]}`, plus `"dT"`, `"dP"` lists in the order
  h, s, v, Z, cp, lnphi for tier A; `saturation` rows `{T, Psat, dh_vap}`, plus `dPsat_dT` and the two phases'
  value lists for tier A; `tsat.tsat_mid` `{P, Tsat}`, plus `dTsat_dP` for tier A; `band` `{T, eps_sigma, probes}`
  with each probe's `answered`/`refused` phases (tier A adds each answered phase's value list); `probes` as
  `[assertion, code, probe, control]` with a request written `[kind, T, P, phase(, field, value)]`, `[flash, T,
  P]`, `[Psat, T]` or `[Tsat, P]`. Sorted keys; a list of scalars stays on one line. Rejected: `indent=1` with one
  float per line, which gave 1.85 MB and failed C17 (no state was removed; only whitespace changed).
- **B-11: the C3 whitelist** is exactly §8's and §16.7's keys: top level `schema`, `coolprop_version`,
  `coolprop_gitrevision`, `fluids`, `excluded`, `published_checks`, `claims`. Water's C12 worsts go into its
  `agreement` under `s05/<quantity>`; C18's measured slope goes into its claim statement. `claims` holds the total
  count and, per claim id, its count and statement; C19's count is 0 in the file because `--check` judges it after
  the file exists.
- **B-12: the refusal probes, by rule from §6.1's constants** (`Fluid.probes`; expected codes computed by the
  generator's own §6.5 precedence, `Fluid.expect`). A16: the four box edges at 1e-9 relative outside, for
  `evaluate_phase` and `flash`, with controls at the exact bounds; `Psat` below T_lo and above T_hi, `Tsat` below
  P_lo and above P_hi, with answered controls. A14: the middle of the near-critical box at p_c for both phases and
  the flash (control: T at the box's open upper T edge); the strip's LIQUID side at the box's lower P edge. A15:
  `S_dense` LIQUID; the strip below and above the box (1e-9 outside); (T_σ,max, p_c) VAPOR; band ±2ε_σ. A18:
  `Psat` above T_σ,max and at T_hi; `Tsat` above p_σ(T_σ,max), and below p_σ(T_lo) when that is >= P_lo. A21:
  rows 1, 2, 3, 6 at `V_sup`. 29–30 probes per fluid, 3629 in all. C14 also claims each probe reaches the code
  its family exists for.
- **B-13: C12 compares** S05's φ partials, its TP values (h, s, v, Z, cp, lnphi) and Psat at every S05 state with
  T <= 646.9 K, plain relative 1e-12.
- **B-14 (§12.1 item 5): `--check` stays a manifest command, not a CI test**, as §16.7 says and S05 did.

Questions for the design lane (batched for the WO-S07-1b review; none blocks WO-S07-2a's start beyond that review):

- **Q-B1: C14 and §6.5 row 10.** C14 says the probes cover every code "except row 4 and row 11", which includes
  row 10 (`density_not_converged`, `saturation_not_converged`). No state inside the domain should reach it (A22
  asserts it never occurs), and outside the domain `out_of_domain` takes precedence, so no rule probe can expect
  it. The generator covers rows 1–3 and 5–9 and states that in C14. Proposed: C14 reads "except rows 4, 10 and 11".
- **Q-B2: A04 at `delta_one`.** The generator stores third-order partials at `delta_one` (B-5). S05 registered
  only orders <= 2 there. If CoolProp's third-order non-analytic partials at δ = 1 do not follow the zero-jet rule,
  A04 at `delta_one` would fail for a reason outside the provider. Proposed: WO-S07-2a measures it; if it fails,
  A04 excludes `delta_one` (as S05) by ruling, never by tolerance.
- **Q-B3: C11's lnphi source** (B-7): an `AbstractState` PT flash rather than `PropsSI`, which has no such output.
  Proposed: accept; the flash is the same solver `PropsSI` calls.

**Ruled (design lane, 2026-10-23; spec §18, R-625; review `docs/reviews/S07-generator-review.md`).**
- Q-B1: yes. C14 excludes rows 4, 10 and 11. A21 reaches rows 10 and 11 by injection on N2 (§18.1).
- Q-B2: A04 keeps `delta_one`. Measured at 1.6e-13 (§18.6).
- Q-B3: accepted (§18.2).
- Generator follow-ups for the next regeneration: C12 widened (§18.3; review finding 1); count the real C17
  check and reword C1 (finding 5); move the ρ' > ρ_c > ρ'' claim into `Fluid.sat()` (finding 6).

## Generator follow-ups (review findings 1, 5, 6; spec §18.3)

- **B-15: C12 widened per §18.3** (`Fluid.c12`): the φ partials (1e-12 relative, unchanged), the TP values and
  their T and P derivatives, Psat, dPsat/dT, both saturated phases' values, Tsat and dTsat/dP (Tsat solved by the
  generator's own `tsat_solve`, seeded by CoolProp). Supersedes B-13. Measured, water: derivatives worst
  1.69e-12 (dcp/dT at L_ambient, as the review's 1.7e-12), dTsat/dP 1.0e-14, Tsat 5.8e-15, saturated-phase values
  <= 5.0e-14.
  - **DECISION (§18.3's value bound read as S05's "relative or absolute" form):** h, s and lnphi pass when
    |Δ| <= 1e-12·max(|x|, scale), scale R·T, R and 1. Read literally ("s within 1e-12·R"), the bound is *tighter*
    than relative wherever |s| > R and fails at S05's V_corner (|Δs|/R = 1.1e-12, relative 4.6e-14), a state the
    old plain-relative C12 passed. §18.3 gives the absolute forms "because s_l(T_t) is 6.5e-14", i.e. for
    vanishing values only, and §9.1 states S05's bounds as "relative or absolute". Rejected: the literal absolute
    bound (fails a state for no numerical reason); plain relative (meaningless at s_l(T_t)). Reversible by editing
    `check()` in `Fluid.c12`. For the design lane to confirm at the S07 review.
- **B-16: C17 counts the real check.** The placeholder `claim("C17", True, …)` is gone. The written C17 count is
  the one size claim made on the encoded payload that carries it; after the claim the ledger is compared with the
  written count and the generator refuses on a mismatch.
- **B-17: ρ' > ρ_c > ρ'' is claimed in `Fluid.sat()`** (every memoized saturation state: `sat_*`, the NC
  temperature, C8's grid) and at the end of `tsat_solve`; the loop over `sat_lo/mid/hi` is removed as redundant.
  C1's statement is reworded to what it checks ("the fluid JSON carries an EOS, and every term type of EOS[0], the
  one generated, is in §2.2 or §16.2").
- **Regeneration (2026-10-23, after B-15–B-17):** `--jobs 48` 90 s wall, 1450 s CPU; all claims pass; output
  1 116 476 bytes (C17 cap 1.5e6); 315 273 claims (was 312 521: C12 55 → 185, C13 16 830 → 19 452). `--check`
  (`--jobs 48`): both files byte-identical. `_coolprop_heos_fluids.py` is unchanged. The reference JSON changed
  only in: `claims/count`, `claims/names/C1/statement`, `claims/names/C12/{count,statement}`,
  `claims/names/C13/count`, and `fluids/H2O/agreement` (26 `s05/*` members added; `s05/lnphi` 5.6e-14 → 4.15e-14
  by B-15's form). No stored value, constant, state or probe moved.

## WO-S07-2a (the provider, tier A; spec §12.2, §16.8–§16.10, §18)

Commits `b39a117c` (provider, tests, T07/T08 registrations) and `b36724a6` (B-18, isolated). Status: implemented,
tested (CoolProp scratch venv, `OPENFLOWSHEET_REQUIRE_COOLPROP=1`): `tests/test_s07_coolprop.py` +
`tests/test_s07_packaging.py` 417 passed in 13.4 s. Project venv (no CoolProp): T07, T08, S05 envelope, L01 retake,
S07 tests 443 passed, 265 skipped, 6 failed = T08's C3 harvest check only (below). ruff clean, mypy clean.

- **Measured per fluid** (worst over ref's states; A05 as |Δ|/bound; A17 the FD ratio):

  | fluid | A03 | A04 (`delta_one`) | A05/bound | A08 Psat | A17 floor |
  | --- | --- | --- | --- | --- | --- |
  | H2O | 2.5e-15 | 6.2e-14 (2.2e-14) | 1.2e-5 | 3.0e-14 | 3.3e-12 |
  | CO2 | 1.1e-14 | 1.6e-13 (1.6e-13) | 2.6e-6 | 2.5e-14 | 2.8e-12 |
  | N2 | 1.5e-15 | 8.0e-14 | 3.7e-6 | 2.9e-15 | 2.1e-12 |
  | O2 | 1.2e-15 | 8.9e-15 | 4.2e-6 | 1.6e-14 | 3.0e-12 |
  | Ar | 1.3e-15 | 3.3e-15 | 1.3e-6 | 1.7e-14 | 2.2e-12 |
  | CH4 | 7.5e-16 | 9.4e-15 | 2.2e-6 | 3.6e-15 | 3.1e-12 |
  | C2H6 | 2.7e-15 | 3.4e-14 | 1.3e-6 | 6.7e-15 | 3.2e-12 |
  | C3H8 | 7.8e-16 | 1.6e-14 | 1.3e-5 | 2.7e-14 | 3.2e-12 |
  | H2 | 4.5e-15 | 3.7e-14 | 1.2e-6 | 1.2e-14 | 1.5e-12 |

  Stop lines not reached: A04 at `delta_one` ≤ 1.6e-13 (< 1e-12, §18.6); A17 floor ≤ 3.3e-12 (< 1e-11, §9.1).
  **The review's known risk (§18.7) did not materialize:** C3H8 `sat_lo` (Z_L = 3.8e-10) Psat agrees with ref to
  2.7e-14 (A08 bound 2e-9), from the vapour branch.
- **B-15 flag: none.** A05, A13 and A23 use S05's test form literally (h within 1e-8·R·T, s within 1e-8·R, lnphi
  within 1e-8, all absolute; v, Z, cp relative). No S07 assertion uses the "relative or absolute" reading.
- **Q-3 settled (A26(c)): yes, G4 runs once.** For all nine fluids, a reference-state change after an instance's
  first evaluation leaves its values bitwise unchanged, and a change before it refuses `coolprop_state_mutated:`.
  No §5.2 amendment.
- **F-5 settled: no scan change.** `scripts/t08_support_matrix.py::_scanned_providers` counts a module only if it has
  a string `PROVIDER_ID`; `_coolprop_heos_fluids.py` has none, imports without error, and is not counted. T08's A20
  literal now lists `coolprop-heos-v1` and nothing else new.
- **B-18 — DECISION (A10/A11 below P_lo; `b36724a6`, isolated): for the design lane.** C2H6 and C3H8 have
  Psat(T_lo) = 32.5 Pa and 4.93e-3 Pa < P_lo = 100 Pa, so `evaluate_phase` refuses (T_lo, Psat) `out_of_domain`
  (§6.5 row 5) and S05's A10/A11 path cannot run at `sat_lo` (4 failing cases in `b39a117c`). The test now reads both
  phases from the provider's own saturation state through the property path `evaluate_phase` uses (`_saturation`,
  `_at` at the root pressure) where Psat < P_lo, and the public path elsewhere. Measured there: C3H8
  |lnphi_L − lnphi_V| 1.2e-13, h_V − h_L vs ref 2.9e-15, CC 2.6e-14; C2H6 6.0e-15, 4.4e-16, 6.2e-15.
  Rejected: dropping the state (forbidden); lowering P_lo (a domain change). Alternatives for the ruling: confirm;
  or amend §7/A10 to define the check at Psat < P_lo. Reversible by `git revert b36724a6`.
- **B-19 — DECISION (saturation seed):** CoolProp's `ANCILLARIES` (`pS`, `rhoL`, `rhoV`) from the guard-checked
  JSON, CoolProp's `SaturationAncillaryFunction` forms, with θ = 1 − T/T_c (the EOS critical point) instead of the
  ancillary's T_r, so θ > 0 on all of (T_lo, T_c) (O2: T_r = 154.581 K < T_c = 154.599 K; the strip probes at
  T_c(1 − 1e-4) need it). Seeds only (§6.3). Other ancillary kinds (none in tier A) refuse
  `saturation_not_converged` with the kind named; WO-S07-2b measures tier B. Reversible in `_Ancillary.__call__`.
- **B-20 — DECISION (A26(c)'s perturbation):** `set_reference_state(name, "NBP")` does not move α° for CH4 (4.97e-14)
  and H2 (3.9e-11), whose DEF datum is NBP, so the literal probe cannot exercise G4 there. The test uses the first of
  NBP, ASHRAE, IIR that moves a fresh state's α° by > 1e-3 (NBP: H2O, N2, O2, Ar, C3H8; ASHRAE: CO2, C2H6), else the
  explicit `set_reference_state(name, 300 K, 100 mol/m³, 1000 J/mol, 10 J/(mol K))` (CH4, H2). Reversible in
  `MUTATED_SCRIPT.perturb`.
- **B-21 — DECISION (T08 registration now, as S05's WO-1 did):** the module's `PROVIDER_ID` enters T08's scan, so
  `scanned_providers` and `LIBRARY_ONLY_PROVIDERS` (`"coolprop-heos-v1": "S07"`) are updated here; otherwise T08 A20
  fails. T08's C3 harvest check (`test_c3_*`, 6 cases) fails until WO-S07-3's manifest carries a U02 item naming
  `coolprop-heos-v1` (R-568/R-569). T07: the module's one `@cache` allowlisted (32 → 33).
- **Build notes.** `helmholtz_jet` keeps one guarded instance per id in a module dict (the jet needs a live
  `AbstractState`). A guard step that raises reports under its own code (G2, G3, G4). A21 row 11 is injected by an
  `AbstractState` proxy whose `update` raises (the Cython class cannot be monkeypatched); rows 10 by
  `MAX_ITERATIONS = 0` on a cold instance, as S05's `_starved`. A27 is an AST check (allowed names on the names bound
  to CoolProp objects, the forbidden list anywhere, `specify_phase(iphase_gas)` before the first update, `update`
  only in `_jet`). A32 m1, m2, m5–m8 are source edits loaded as a private module (m7 in A26(c)'s subprocess); m3, m4,
  m9–m11 replace the instance's fluid record. A24 also checks cp^ig against ref `s04_ig` at 1e-12 (not numbered).

## WO-S07-2b (tier B; spec §16.10, §16.11, §16.13 Q-A1-5)

Commit `6cd2ad08`. Status: **implemented, not tested**: 49 of 2626 cases fail, all from one cause (Q-B4); stopped
for a design ruling. Tier B is **self-consistent only, not validated** (spec §16.5.1): its expectations are 50-digit
closed forms of CoolProp's own coefficients, and its other checks are the provider's consistency with itself. The
provider says so (`verification: self-consistent; …; the EOS's own uncertainty is not re-validated`, A34).

- **Runs** (x86-64; CoolProp scratch venv, `OPENFLOWSHEET_REQUIRE_COOLPROP=1`): `tests/test_s07_broad.py` 2626 cases,
  2577 passed, 49 failed, **10.9 s** wall (the tier-B run time of §16.14). `test_s07_coolprop.py` +
  `test_s07_packaging.py` 303 passed (417 before, less A34's 114 tier-B cases, now in the broad file). Project venv
  (no CoolProp): both S07 test files 377 passed, 2542 skipped. ruff clean; the new file is mypy-strict clean.
- **Worsts over the 114** (`wo2b_worsts.py`; A09 over the 108 that answer): A03 8.96e-13 (R22; bound 1e-11, m7's
  floor 1.05e-12), A04 6.89e-13 (MM; 1e-11), A05 1.25e-3 of its bound (R22 `L_corner` h, |Δh| = 1.25e-11·R·T; the
  §16.11 stop line 1e-9 is not reached), A08 1.1e-12 (R22), A09 1.6e-14, A10 |Δlnphi| 2.0e-11 (R22 at T_lo),
  A11 4.7e-11 (R22 at T_σ,max) and ≤ 1.1e-13 at T_lo, T_mid. Medians: A03 2.8e-15, A04 2.6e-14, A05 2.2e-6 of the
  bound, A17 2.9e-14.
- **A17 floor above §16.11's 1e-11 for two fluids (F-6, for the design lane).** R22 5.63e-11 (`L_corner`, liquid at
  (T_lo, P_hi): h in P, s in T) and PropyleneGlycol 1.07e-11 (`S_dense`, cp in T); every other fluid ≤ 8.7e-12
  (R1130_E). Both pass the test's 1e-10 (S05 §6.3). R22 is also the A03 floor fluid: cancellation in CoolProp's
  double-precision sums at liquid density (§16.11). §16.11 says the design lane re-sets the tolerance by amendment.
- **Q-A1-5, low-pressure side: served.** Every tier-B fluid's saturation converges at T_lo and T_mid. Lowest
  Psat(T_lo): MD3M 2.65e-6 Pa (T/T_c = 0.32), 1-Butene 4.5e-6 Pa (Z_L = 4.1e-13, the smallest); at most 23
  Newton iterations (PropyleneGlycol at T_lo; 50 allowed). A10 and A11 at T_lo pass for all 114.
- **Q-A1-5, near-critical side: not served — Q-B4 below.**
- **B-22 — DECISION (A10/A11 at Psat < P_lo for tier B): B-18's path applies.** 59 of the 114 have
  Psat(T_lo) < P_lo = 100 Pa; the shared helper `saturated_phases` reads both phases from the provider's own
  saturation state there, as B-18 does for C2H6 and C3H8. Alternative: none that runs the check (dropping is
  forbidden). Reversible with B-18 (`git revert b36724a6`), which then restores the public path for both tiers.
- **B-23 — DECISION (A25 for tier B):** the tier-A call list less `tp(cid, "NC_V")` (tier B registers no NC state,
  §16.6); the NC-box midpoint call stays. Reversible in `test_a25_determinism_and_identity`.
- **B-24 (placement).** A34's tier-B cases sit in `test_s07_broad.py` (§16.10); A33 stays whole in
  `test_s07_coolprop.py`, since it is one assertion over the full list, and it already covers all 123 and the 13
  excluded. ref's tier-B `A21`-tagged probes are not exercised: §16.10 does not apply A19–A21 to tier B.

### Q-B4 (for the design lane): the saturation solve fails near T_c for 10 tier-B fluids

- **What fails.** All 49 failures are `saturation_not_converged`. Six fluids fail at T_σ,max = T_c(1 − 2e-4) and
  above it in θ = 1 − T/T_c: Cyclopentane (from θ = 2e-3), R1234ze_Z (1e-3), R134a (5e-4), MDM, MM, R14 (2e-4). That
  fails A09 (the Tsat bounds need p_σ(T_σ,max)), A10 and A11 at T_σ,max, and probes or controls of A14, A15, A16 and
  A18: 42 cases. Ethanol, Neon and R114 fail at the A14/A15 strip controls at θ = 1e-4 (6 cases), and Fluorine at
  A22's grid point 144.409 K, θ = 3.8e-5 (1 case). Everything else passes for these 10.
- **Why.** S05's two-variable Newton in (δ', δ''), seeded by CoolProp's ancillaries (B-19), leaves ρ' > ρ_c > ρ''
  in its first steps: near T_c the seed error is comparable to ρ' − ρ''. R134a at T_σ,max: seed ρ' 5272 vs 5500,
  ρ'' 4594 vs 4520 mol/m³ (QT flash), width 980; the first step lands at (4278, 4523). The provider needs the
  saturation at every T < T_c it answers: `Psat` on [T_lo, T_σ,max], and the density bracket in the strip
  (T_σ,max, T_c) outside the NC box (`_evaluate`, `saturation = self._saturation(t)`), although the strip's label
  does not use it (`_rule`).
- **How wide** (`wo2b_near_critical.py`, θ ∈ {3e-2 … 1e-6}, T ≥ T_lo): 58 of 123 fluids fail at some θ ≥ 1e-6,
  **including tier A's O2 (θ ≤ 1e-5) and H2 (θ = 1e-6)**. The registered states reach θ < 2e-4 only at the strip
  controls (θ = 1e-4), so this is also a latent tier-A gap in the strip.
- **Not a remedy: bracket-preserving step halving** (diagnostic in the script, not in the provider). It never acts
  where the provider converges (the same root bitwise at every such point), but it does not rescue the failures:
  the iteration stalls, or the seed itself is outside ρ' > ρ_c > ρ''.
- **The options.** (a) Q-A1-5's default: exclude the 10 by amendment. It loses R134a, Ethanol, Neon, Cyclopentane,
  MM, MDM, R14, R114, Fluorine and R1234ze(Z), and leaves the strip gap for 48 others, O2 and H2 among them.
  (b) A generic change to the provider's near-critical solve, for both tiers: for example, seeds by continuation
  from a converged root at larger θ, or the strip bracketed by ρ_c instead of the saturated densities. That is new
  numerics; tier A must be proved bit-identical wherever it converges now. **Recommendation:** (b), because the gap
  is not tier-B-specific. Not implemented here: the brief forbids special cases and inventing numerics.
- **Blocks:** tier B's `tested`. A01–A08, A13, A17, A22 (except Fluorine), A25, A28 and A34–A35 pass for all 114.

### Per-fluid record (A05 as |Δ|/bound; A17 the S05 §6.3 FD ratio; θ the highest failing value of the scan)

| fluid | A03 | A04 | A05/bound | A08 | A17 floor | Psat(T_lo), Pa | max sat. iter. | highest failing θ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-Butene | 1.2e-15 | 1.9e-14 | 8.1e-06 | 1.2e-15 | 2.5e-14 | 4.5e-06 | 6 | 3e-06 |
| Acetone | 1.3e-15 | 1.7e-14 | 1.4e-06 | 1.6e-15 | 1.3e-14 | 8.1e+00 | 6 | none ≥ 1e-6 |
| Ammonia | 1.6e-14 | 5.1e-13 | 8.0e-07 | 6.7e-16 | 1.9e-14 | 3.6e+04 | 7 | 3e-06 |
| Benzene | 2.1e-15 | 9.3e-14 | 1.8e-06 | 5.6e-16 | 3.5e-14 | 1.0e+04 | 5 | none ≥ 1e-6 |
| CarbonMonoxide | 6.4e-16 | 9.9e-15 | 7.3e-07 | 4.4e-16 | 2.8e-14 | 1.9e+05 | 6 | none ≥ 1e-6 |
| CarbonylSulfide | 6.7e-16 | 1.6e-14 | 7.1e-07 | 1.0e-15 | 2.8e-14 | 2.4e+02 | 5 | 1e-06 |
| Chlorine | 1.8e-15 | 3.2e-15 | 5.1e-07 | 2.3e-15 | 1.9e-14 | 4.8e+03 | 6 | 1e-06 |
| CycloHexane | 2.9e-15 | 1.1e-13 | 8.1e-07 | 1.1e-15 | 8.6e-14 | 4.6e+04 | 5 | 1e-06 |
| CycloPropane | 5.2e-15 | 1.1e-14 | 8.5e-07 | 4.4e-16 | 6.6e-15 | 5.8e+05 | 11 | 1e-06 |
| Cyclopentane | 2.6e-15 | 7.8e-14 | 5.3e-06 | 3.0e-15 | 4.1e-14 | 2.7e+01 | 5 | 0.002 |
| D4 | 9.7e-15 | 4.3e-13 | 3.6e-06 | 2.7e-15 | 6.0e-14 | 2.2e+02 | 6 | 1e-05 |
| D5 | 4.0e-15 | 2.8e-13 | 2.2e-05 | 1.9e-14 | 6.6e-14 | 1.4e-02 | 5 | none ≥ 1e-6 |
| Deuterium | 7.3e-15 | 9.5e-14 | 7.1e-06 | 3.1e-15 | 3.9e-14 | 1.4e+06 | 8 | 5e-05 |
| Dichloroethane | 7.6e-15 | 4.2e-14 | 1.9e-06 | 1.6e-15 | 2.7e-14 | 6.8e+02 | 6 | 2e-05 |
| DiethylEther | 8.9e-16 | 1.8e-14 | 3.6e-07 | 3.3e-16 | 1.8e-14 | 3.9e+04 | 11 | 2e-05 |
| DimethylCarbonate | 1.8e-15 | 8.8e-14 | 2.1e-06 | 2.4e-15 | 1.9e-14 | 5.3e+03 | 6 | 1e-06 |
| DimethylEther | 1.3e-15 | 4.8e-14 | 3.3e-06 | 6.7e-16 | 2.2e-14 | 8.8e+00 | 7 | none ≥ 1e-6 |
| Ethanol | 2.9e-15 | 1.7e-13 | 5.1e-05 | 1.5e-14 | 1.9e-13 | 9.6e-03 | 9 | 0.0001 |
| EthylBenzene | 4.6e-15 | 9.9e-14 | 7.1e-06 | 2.7e-15 | 1.7e-14 | 2.0e-02 | 8 | none ≥ 1e-6 |
| Ethylene | 6.1e-16 | 1.1e-14 | 1.2e-06 | 6.7e-16 | 2.0e-13 | 3.3e+03 | 7 | 1e-06 |
| EthyleneOxide | 1.2e-14 | 5.4e-13 | 1.5e-06 | 6.7e-16 | 5.2e-14 | 4.7e+01 | 7 | 1e-06 |
| Fluorine | 8.1e-15 | 1.8e-14 | 2.0e-05 | 2.2e-15 | 2.9e-13 | 4.4e+02 | 7 | 5e-05 |
| HFE143m | 3.6e-15 | 1.4e-14 | 1.5e-06 | 2.9e-15 | 1.6e-14 | 1.1e+05 | 9 | none ≥ 1e-6 |
| HeavyWater | 3.9e-14 | 1.0e-13 | 3.8e-06 | 8.9e-16 | 1.0e-13 | 6.6e+02 | 7 | 1e-06 |
| HydrogenChloride | 6.8e-15 | 1.8e-13 | 9.5e-07 | 2.2e-16 | 3.2e-14 | 4.2e+04 | 9 | none ≥ 1e-6 |
| HydrogenSulfide | 5.3e-16 | 1.6e-14 | 6.4e-07 | 4.4e-16 | 2.6e-14 | 7.2e+04 | 6 | none ≥ 1e-6 |
| IsoButane | 1.5e-15 | 1.4e-14 | 1.4e-06 | 3.2e-15 | 5.3e-14 | 3.5e-01 | 5 | none ≥ 1e-6 |
| IsoButene | 8.3e-16 | 1.9e-14 | 2.5e-06 | 1.6e-15 | 2.1e-14 | 2.3e+00 | 7 | none ≥ 1e-6 |
| Isohexane | 8.3e-16 | 2.8e-14 | 1.2e-05 | 1.8e-15 | 4.1e-14 | 5.4e-05 | 6 | none ≥ 1e-6 |
| Isopentane | 6.7e-16 | 2.6e-14 | 6.0e-06 | 2.8e-15 | 9.8e-15 | 2.9e-03 | 6 | none ≥ 1e-6 |
| Krypton | 8.0e-16 | 1.2e-14 | 5.3e-07 | 1.2e-15 | 7.9e-15 | 4.8e+05 | 7 | none ≥ 1e-6 |
| MD3M | 1.1e-14 | 4.7e-13 | 3.2e-05 | 2.9e-15 | 8.6e-14 | 2.7e-06 | 6 | none ≥ 1e-6 |
| MD4M | 1.6e-14 | 6.0e-13 | 4.8e-06 | 9.8e-15 | 5.6e-14 | 7.6e-06 | 7 | 1e-06 |
| MDM | 7.4e-15 | 7.4e-14 | 5.8e-06 | 2.0e-15 | 5.8e-14 | 6.6e-03 | 6 | 0.0002 |
| MM | 1.6e-14 | 6.9e-13 | 5.8e-06 | 4.0e-15 | 4.2e-14 | 1.0e+01 | 5 | 0.0002 |
| Methanol | 1.1e-14 | 1.2e-14 | 2.0e-04 | 3.4e-14 | 3.1e-12 | 1.6e+00 | 9 | 1e-06 |
| MethylLinoleate | 4.7e-14 | 1.3e-14 | 3.8e-05 | 5.6e-16 | 2.6e-13 | 1.8e-05 | 7 | 1e-05 |
| MethylLinolenate | 3.6e-15 | 1.3e-14 | 2.1e-06 | 3.3e-16 | 2.1e-14 | 5.6e-06 | 7 | 3e-06 |
| MethylOleate | 6.0e-15 | 1.8e-14 | 4.1e-06 | 1.3e-15 | 2.9e-14 | 5.2e-06 | 8 | 3e-06 |
| MethylPalmitate | 4.8e-15 | 1.4e-14 | 3.4e-06 | 4.8e-15 | 1.3e-14 | 9.5e-02 | 6 | 3e-06 |
| MethylStearate | 1.2e-14 | 1.4e-14 | 6.8e-06 | 1.0e-15 | 4.7e-15 | 3.8e-02 | 7 | 1e-05 |
| Neon | 2.8e-15 | 6.0e-14 | 1.2e-06 | 1.1e-15 | 3.6e-14 | 9.3e+05 | 10 | 0.0001 |
| Neopentane | 1.1e-15 | 2.4e-14 | 3.7e-07 | 4.4e-16 | 1.7e-14 | 6.1e+04 | 6 | none ≥ 1e-6 |
| NitrousOxide | 1.0e-15 | 1.3e-14 | 3.8e-07 | 1.6e-15 | 1.9e-14 | 2.0e+05 | 6 | none ≥ 1e-6 |
| Novec649 | 9.5e-16 | 1.9e-14 | 4.3e-06 | 2.2e-16 | 4.7e-14 | 9.9e-01 | 6 | none ≥ 1e-6 |
| OrthoDeuterium | 7.3e-15 | 9.5e-14 | 7.1e-06 | 1.3e-15 | 3.9e-14 | 1.4e+06 | 9 | 3e-06 |
| OrthoHydrogen | 3.4e-15 | 4.4e-14 | 2.1e-06 | 4.4e-15 | 2.0e-14 | 1.0e+06 | 8 | 1e-06 |
| ParaDeuterium | 7.3e-15 | 9.5e-14 | 7.1e-06 | 3.6e-15 | 5.5e-14 | 1.4e+06 | 6 | none ≥ 1e-6 |
| Propylene | 6.4e-15 | 2.1e-13 | 1.0e-06 | 2.2e-16 | 3.2e-14 | 1.6e-02 | 9 | none ≥ 1e-6 |
| PropyleneGlycol | 1.1e-14 | 3.7e-13 | 7.1e-06 | 3.6e-15 | 1.1e-11 | 4.8e-03 | 23 | none ≥ 1e-6 |
| Propyne | 1.6e-14 | 2.7e-14 | 2.1e-06 | 4.0e-15 | 3.5e-14 | 4.6e+05 | 9 | 2e-05 |
| R11 | 1.6e-15 | 1.0e-14 | 5.6e-06 | 1.1e-16 | 6.4e-14 | 2.0e+01 | 10 | none ≥ 1e-6 |
| R1123 | 5.2e-15 | 3.0e-13 | 9.5e-07 | 2.2e-16 | 1.5e-14 | 7.1e+04 | 9 | none ≥ 1e-6 |
| R113 | 4.8e-16 | 9.4e-15 | 9.5e-07 | 6.7e-16 | 2.9e-14 | 4.0e+03 | 6 | none ≥ 1e-6 |
| R1130_E | 7.2e-16 | 1.0e-13 | 9.5e-06 | 2.7e-15 | 8.7e-12 | 1.7e+03 | 7 | 3e-06 |
| R1132_E | 8.4e-15 | 2.6e-13 | 7.7e-07 | 1.8e-15 | 2.1e-14 | 4.2e+05 | 9 | 1e-05 |
| R114 | 3.6e-15 | 1.0e-14 | 4.3e-06 | 8.9e-16 | 5.0e-14 | 1.5e+05 | 11 | 0.0001 |
| R115 | 1.3e-15 | 7.0e-15 | 3.1e-06 | 1.9e-15 | 1.4e-14 | 4.6e+03 | 7 | none ≥ 1e-6 |
| R116 | 6.1e-16 | 2.3e-14 | 7.1e-07 | 1.3e-15 | 6.2e-15 | 4.7e+04 | 8 | none ≥ 1e-6 |
| R12 | 5.6e-16 | 2.3e-14 | 1.6e-06 | 3.3e-15 | 1.1e-14 | 8.9e-01 | 7 | none ≥ 1e-6 |
| R1224YDZ | 2.6e-15 | 8.8e-14 | 5.3e-06 | 4.0e-15 | 3.1e-14 | 8.7e+00 | 9 | none ≥ 1e-6 |
| R123 | 4.4e-14 | 3.6e-13 | 8.4e-04 | 4.5e-14 | 4.9e-12 | 1.4e+01 | 7 | 1e-05 |
| R1233zd_E | 4.3e-15 | 1.9e-13 | 2.7e-06 | 2.2e-15 | 2.9e-14 | 2.7e+01 | 6 | none ≥ 1e-6 |
| R1234yf | 2.0e-15 | 2.3e-14 | 4.4e-06 | 4.0e-15 | 1.3e-13 | 1.5e+00 | 8 | none ≥ 1e-6 |
| R1234ze_E | 3.9e-15 | 8.2e-14 | 7.8e-07 | 2.7e-15 | 1.1e-14 | 5.6e+02 | 6 | 1e-06 |
| R1234ze_Z | 2.2e-15 | 5.8e-14 | 1.4e-06 | 2.2e-16 | 2.5e-13 | 1.2e+05 | 5 | 0.001 |
| R124 | 6.6e-16 | 1.2e-14 | 5.3e-06 | 1.8e-15 | 3.1e-14 | 1.2e-01 | 9 | none ≥ 1e-6 |
| R1243zf | 1.2e-15 | 7.1e-14 | 7.1e-07 | 2.4e-15 | 1.9e-14 | 1.4e+00 | 6 | none ≥ 1e-6 |
| R125 | 5.7e-15 | 2.8e-14 | 1.4e-06 | 2.2e-16 | 2.8e-14 | 6.2e+03 | 6 | none ≥ 1e-6 |
| R13 | 4.2e-15 | 2.3e-15 | 3.6e-06 | 2.3e-15 | 5.0e-13 | 3.9e+00 | 12 | 5e-05 |
| R1336mzz_E | 7.3e-15 | 1.1e-13 | 1.6e-06 | 1.3e-15 | 3.4e-14 | 1.6e+03 | 7 | none ≥ 1e-6 |
| R1336mzz_Z | 3.1e-15 | 1.7e-14 | 2.4e-06 | 2.7e-15 | 2.4e-14 | 5.5e+01 | 6 | none ≥ 1e-6 |
| R134a | 1.8e-15 | 2.6e-14 | 3.2e-06 | 1.1e-15 | 2.5e-14 | 9.6e+02 | 7 | 0.0005 |
| R13I1 | 5.6e-16 | 2.8e-14 | 3.7e-06 | 3.6e-15 | 1.2e-13 | 1.5e+00 | 6 | none ≥ 1e-6 |
| R14 | 1.9e-15 | 7.0e-15 | 1.7e-06 | 1.0e-15 | 1.8e-14 | 2.1e+04 | 6 | 0.0002 |
| R141b | 1.2e-15 | 9.3e-15 | 1.4e-06 | 2.0e-15 | 1.6e-13 | 2.0e+01 | 6 | none ≥ 1e-6 |
| R142b | 1.4e-15 | 9.5e-15 | 6.8e-07 | 1.1e-16 | 2.0e-14 | 1.2e+01 | 7 | 1e-06 |
| R143a | 2.9e-15 | 1.5e-14 | 1.1e-06 | 2.6e-15 | 1.9e-14 | 2.4e+03 | 6 | none ≥ 1e-6 |
| R152A | 2.3e-14 | 9.5e-14 | 2.9e-05 | 2.6e-14 | 6.7e-12 | 1.7e+02 | 10 | 5e-05 |
| R21 | 6.5e-14 | 6.3e-14 | 1.2e-05 | 2.3e-14 | 1.4e-13 | 2.3e+03 | 11 | 1e-05 |
| R218 | 1.2e-15 | 5.0e-15 | 3.5e-06 | 1.3e-15 | 1.4e-14 | 6.8e+00 | 6 | none ≥ 1e-6 |
| R22 | 9.0e-13 | 3.8e-13 | 1.3e-03 | 1.1e-12 | 5.6e-11 | 1.6e+00 | 5 | 1e-05 |
| R227EA | 3.4e-15 | 6.0e-15 | 9.4e-06 | 3.6e-15 | 7.3e-14 | 2.3e+01 | 5 | none ≥ 1e-6 |
| R23 | 1.5e-15 | 1.3e-14 | 2.5e-06 | 5.6e-16 | 1.1e-13 | 1.7e+02 | 6 | 1e-05 |
| R236FA | 4.3e-15 | 2.2e-13 | 8.2e-07 | 8.9e-16 | 1.4e-14 | 4.3e+02 | 5 | 3e-06 |
| R245ca | 1.8e-15 | 1.6e-14 | 5.5e-06 | 0.0e+00 | 5.2e-14 | 3.3e+02 | 6 | none ≥ 1e-6 |
| R245fa | 3.2e-15 | 8.0e-14 | 2.8e-06 | 1.3e-15 | 6.9e-14 | 4.3e+01 | 10 | none ≥ 1e-6 |
| R32 | 1.5e-15 | 8.1e-14 | 4.4e-07 | 1.3e-15 | 3.3e-14 | 1.7e+02 | 7 | 1e-06 |
| R365MFC | 3.9e-15 | 1.4e-14 | 7.6e-06 | 9.7e-15 | 4.5e-14 | 5.4e+03 | 8 | none ≥ 1e-6 |
| R40 | 5.7e-16 | 2.5e-14 | 4.4e-07 | 4.4e-16 | 2.2e-14 | 9.5e+04 | 12 | 1e-05 |
| R41 | 1.0e-15 | 2.1e-14 | 6.8e-07 | 2.2e-15 | 1.7e-14 | 1.0e+03 | 6 | none ≥ 1e-6 |
| RC318 | 3.7e-15 | 1.1e-14 | 2.5e-06 | 6.7e-16 | 2.3e-14 | 3.7e+04 | 7 | 1e-05 |
| SulfurDioxide | 1.4e-15 | 2.1e-14 | 6.1e-07 | 2.0e-15 | 2.4e-14 | 6.5e+03 | 6 | none ≥ 1e-6 |
| SulfurHexafluoride | 1.3e-14 | 2.2e-14 | 1.9e-06 | 6.4e-15 | 6.5e-14 | 3.6e+05 | 6 | 1e-06 |
| Tetrahydrofuran | 2.0e-15 | 5.0e-14 | 4.6e-06 | 8.9e-16 | 1.6e-14 | 7.4e-01 | 6 | none ≥ 1e-6 |
| Toluene | 1.0e-15 | 3.3e-14 | 9.4e-07 | 1.1e-15 | 1.1e-14 | 1.7e-01 | 7 | none ≥ 1e-6 |
| VinylChloride | 5.0e-15 | 2.2e-13 | 1.4e-05 | 2.9e-15 | 3.6e-12 | 2.4e-01 | 8 | 1e-06 |
| Xenon | 6.7e-16 | 1.2e-14 | 5.5e-07 | 1.3e-15 | 2.0e-14 | 1.5e+05 | 7 | 3e-06 |
| cis-2-Butene | 1.3e-15 | 1.9e-14 | 2.2e-06 | 5.3e-15 | 2.6e-14 | 9.8e-01 | 7 | 1e-05 |
| m-Xylene | 2.3e-15 | 7.5e-14 | 1.8e-06 | 3.6e-15 | 1.5e-14 | 1.0e+01 | 8 | none ≥ 1e-6 |
| n-Butane | 1.3e-15 | 1.1e-14 | 2.4e-05 | 8.7e-15 | 6.1e-13 | 9.7e-01 | 7 | none ≥ 1e-6 |
| n-Decane | 1.0e-15 | 5.3e-14 | 1.2e-06 | 2.9e-15 | 1.0e-14 | 5.2e+00 | 7 | 3e-06 |
| n-Dodecane | 1.0e-15 | 1.4e-14 | 1.9e-06 | 5.8e-15 | 4.7e-15 | 2.5e+00 | 7 | none ≥ 1e-6 |
| n-Hexane | 1.1e-14 | 4.1e-13 | 1.1e-06 | 1.8e-15 | 2.6e-14 | 4.1e+00 | 6 | none ≥ 1e-6 |
| n-Nonane | 1.2e-15 | 3.4e-14 | 6.8e-07 | 8.9e-16 | 1.4e-14 | 1.7e+00 | 5 | 1e-06 |
| n-Octane | 2.5e-15 | 1.9e-14 | 2.7e-06 | 2.2e-16 | 4.1e-14 | 7.2e+00 | 7 | none ≥ 1e-6 |
| n-Pentane | 1.6e-14 | 6.7e-13 | 1.8e-06 | 1.0e-15 | 4.6e-14 | 8.2e-01 | 9 | none ≥ 1e-6 |
| n-Perfluorobutane | 2.8e-15 | 1.3e-13 | 1.4e-06 | 0.0e+00 | 1.2e-14 | 4.0e+00 | 9 | none ≥ 1e-6 |
| n-Perfluorohexane | 1.3e-14 | 6.4e-13 | 1.5e-06 | 4.6e-15 | 1.9e-14 | 1.4e+01 | 7 | none ≥ 1e-6 |
| n-Perfluoropentane | 6.7e-15 | 1.8e-13 | 2.8e-06 | 2.8e-15 | 1.2e-14 | 4.5e-01 | 6 | none ≥ 1e-6 |
| n-Undecane | 1.8e-15 | 3.3e-15 | 4.1e-06 | 3.0e-15 | 8.1e-15 | 1.8e+00 | 6 | 3e-06 |
| o-Xylene | 4.2e-15 | 1.1e-13 | 3.6e-06 | 1.3e-15 | 4.1e-14 | 6.6e+01 | 7 | 1e-06 |
| p-Xylene | 2.5e-15 | 4.1e-15 | 9.1e-07 | 1.9e-15 | 1.2e-14 | 1.4e+03 | 6 | none ≥ 1e-6 |
| trans-2-Butene | 6.7e-16 | 2.0e-14 | 1.6e-06 | 2.9e-15 | 1.0e-14 | 1.9e+02 | 7 | none ≥ 1e-6 |

## WO-S07-NC2 / NC3 (design note `docs/design/S07-near-critical-saturation.md`, Q-B4)

Status: **implemented; WO-S07-2b's tier B now passes; two gates of the note fail (G3, G8) and wait for a ruling.**
CoolProp scratch venv, x86-64, `OPENFLOWSHEET_REQUIRE_COOLPROP=1`. Identity was proved by recording every
`evaluate_phase`/`flash` answer and every saturation result over the test suites (repr, round-trip exact) before and
after each commit (scratch `recplug.py`/`cmp.py`).

- **`16387740` refactor (inert).** `_maxwell_newton` extracted. S07 record over broad + coolprop + packaging
  (35803 distinct calls) byte-identical; same 49 Q-B4 failures.
- **`e14b7cc5` D1 + D2.** `nc_scan.py` (G1/G2/G3/G8; 123 fluids, 19759 T, 12 s): 0 unsolved, fallback at 343 points,
  max polish 8 iterations, 0 G2 violations (no plain root moved, fallback never entered where the plain Newton
  converges). Outer loop = bisection as specified (the prototype's Newton was not used). Forced fallback where the
  plain Newton converges: refused at 4884 points, all θ ≥ 2.15e-3 (step 1/4/5 checks, M4's region); agreement
  where both converge (14532 pairs): densities 5.1e-12 (θ ≥ 1e-2, bound 1e-11), **1.10e-8 (θ < 1e-2, bound 1e-8;
  R22 at θ = 5e-5)**, **p_σ 6.5e-12 (bound 1e-12; 29 pairs R22 for θ ≤ 2.2e-3, 3 pairs R21)**. Jets inside the
  fallback: **max 414 (Cyclopentane; G8 bound 400)**, next 394 (R1234ze_Z), 388 (R134a); the whole solve with the
  failed Newton, 422. Cost split (Cyclopentane, forced, θ = 3.2e-2: 425 jets): 104 spinodal + ~57 k/K evaluations,
  255 in 50 inner root solves (24 halvings), 9 polish.
- **`c76bc19b` D3** (+ the module/`_density` docstrings). S07 record vs the pre-NC2 baseline: 35718 identical,
  85 former refusals answered, 0 answered values changed. **`tests/test_s07_broad.py` 2626 passed**;
  coolprop + packaging 303 passed.
- **`232711c3` tests** (`tests/test_s07_near_critical.py`, N1-N3, N5 at the note's grids/bounds): 490 of 492
  pass; N3 fails for R22 (both halves; numbers above). Left failing; not relaxed.
- **`8cab0e15` S05 (D5).** S05 record (38010 calls) byte-identical before/after (sha256 `2bd5e0edc2f1dd00…` both);
  S05 tests 380 passed, 1 skipped; `s05_reference.py --check` 2848 claims, json byte-identical; N6 fails before the
  commit, passes after; `iapws95._saturation` converges at all 7478 points (G7(d)).
- **Generators:** `s07_reference.py --check` all claims, json and fluid table byte-identical (112 s).
- **Touched suites:** S05 + S07 (7 files) 3801 passed, 1 skipped, 2 failed (R22 N3); project venv 766 passed,
  3038 skipped. ruff, format, mypy (project config, 244 files) clean.

- **DECISION (Q3, session 2026-10-23):** the S05 strip fix goes on `wp/S07` as its own commit (`8cab0e15`).
  Alternative: a separate S05 package. Reversible by reverting that commit.
- **DECISION (Q5, session 2026-10-23):** S05 gets no fallback (D1/D2); G7(d) measured it unneeded. Alternative: port D1.
  Reversible: additive.
- **B-25 — DECISION (θ_min endpoint):** T_c(1 − 5e-5) computes θ < 5e-5 by one rounding for every fluid, so the
  fallback is (correctly) not tried there (16 G1 "failures" in the first scan, all this). The scan and N1 move such a
  grid T down by `nextafter` until θ ≥ θ_min. Alternative: drop the endpoint. Reversible in `nc_scan.py`/`at_theta`.
- **B-26 — DECISION (step 5's inner starts, unspecified):** ρ_V(P_a) from min(P_a/RT, ρ_vb), ρ_L(P_b) from ρ_lb, as
  step 6's first time. Reversible in `_maxwell_fallback`.
- **B-27 — DECISION (step 6's stop test):** tested after each halving (so a final P_m and its roots always exist);
  F = NaN → `None`; 64 halvings without reaching 2^−26 → `None`. Reversible in `_maxwell_fallback`.
- **B-28 — DECISION (G7(c)'s continuity):** read as G5's (T_c(1 − 1e-12) vs T_c): 9.6e-12 (LIQUID 25 MPa), 1.2e-11
  (VAPOR 20 MPa). Literally against 647.096 K the probes give 8.9e-6, 1.5e-6, 1.5e-7 (LIQUID) and 1.1e-5, 1.8e-6,
  1.8e-7 (VAPOR): linear in ΔT (the physical (∂ln v/∂T)_P ≈ 1.5e-2/K), so 1e-8 cannot hold there.
- **B-29 (placement):** N1-N3, N5, N6 in the new `tests/test_s07_near_critical.py`; `test_s07_broad.py` keeps 2626.
- **B-30 — DECISION:** a CoolProp exception inside the fallback propagates as `coolprop_evaluation_failed` (as every
  other `_jet` failure), not `None`. Reversible: catch in `_maxwell_fallback`.

### For the design lane (one ruling round)

**Ruled 2026-10-23 (R-626; spec §19; review `docs/reviews/S07-review.md`):** G3 and G8 bounds re-set (§19.2, §19.3); θ_min kept (remedy 7e-5 pre-registered); B-15, B-18–B-30 confirmed; F-6 accepted (A17 stop line 1e-10, h-scan rule); S05 A33: default = carry in S07's manifest (needs a decision). Remaining build items: §19.8.

1. **G3 fails for R22 (and R21 on p_σ):** the Maxwell floor of R22 is higher (R22 is F-6's cancellation fluid); the
   p_σ difference follows from Δρ'' times (∂ln p/∂ln ρ)_T at the vapour. Options: bounds by amendment, or accept.
2. **G8 fails by 3.5 %:** 414 jets (Cyclopentane) vs 400. Options: re-set the bound, or Q4's safeguarded Newton.
3. **The new S05 manifest (WO-NC3) is not generated:** `s05_evidence_manifest.py`'s A33 is the identity of WO-S05-5's
   packaging range (`92779215..C_m`, an exact file list); on `wp/S07` no base makes it pass, so the manifest would be
   `implemented`. Needs a ruling on how A33 is carried (e.g. by hash from `01cdeed4`'s manifest).

## Review fixes (R-626, spec §19.8) and WO-S07-NC4

CoolProp scratch venv, x86-64, `OPENFLOWSHEET_REQUIRE_COOLPROP=1`. No provider file changed; no answered value changed.

- **`e27d493a` A47 and the scan take §19.2/§19.3.** N3 bounds: densities 1e-11 (θ ≥ 1e-2) / 3e-8; p_σ 1e-12 / 1e-10.
  The two R22 N3 tests now pass (246 N3 cases). `nc_scan.py`: PASS, 19759 points, 0 G1/G2 failures, fallback at
  343, max polish 8, max fallback jets 414 (tripwire 500), near ρ 1.10e-8, far ρ 5.09e-12, near p_σ 6.54e-12, far
  p_σ 6.79e-13 (14532 pairs).
- **`b79375b3` C-strip (§19.4).** Holds for all 123 fluids at T_σ,max and T_c(1 − θ), θ ∈ {1e-4, 5e-5, 1e-6}
  (984 claims). JSON: only the claim ledger changes; every value and the fluid table byte-identical. Generator
  wall 112 s → 306 s (CPU 1401 → 4658 s; the k grid at 50 digits is most of it).
  - **B-31 — DECISION (claim id):** C-strip is ledger id `C20` (statement starts "C-strip (§19.4)"), because the
    ledger orders ids numerically. Alternative: a non-numeric id with a changed sort. Reversible: rename.
  - **B-32 — DECISION (the generator's QT-free saturation, §19.5 "a seed of its own choice"):** spinodals by
    stepping out of ρ_c (k(ρ_c) < 0 claimed) in steps doubling from ρ_c·θ^½/64, then bisection; pressure bisection
    on g' − g'' between the spinodal pressures to 1e-6 of that range; then the existing Newton, run at dps + 20
    with the 50-digit tolerance (its conditioning ~θ^(−3/2); at dps 50 it did not meet 1e-44 at θ = 1e-6 for
    CO2, R22, Neon, Ammonia, H2). Checked against the QT-seeded root at T_σ,max: < 1e-40 for all 123.
    `saturation()` gained an optional `tol`, default unchanged. Alternative: QT seeds (excluded by §19.5).
  - **B-33 — DECISION (grid spelling):** (0, ρ_max] is ρ_max·i/401, i = 1…401; [ρ'', ρ'] is ρ'' + (ρ' − ρ'')·i/400,
    i = 0…400; the bisection stops at 1e-25 relative. C-strip uses the QT-free solve at all four T. Reversible in `c20`.
- **`45cdcb19` A49 branch check; identity scripts.** All 123 × 7 × 4 strip states on their branch. `recplug.py`
  and `cmp.py` committed under `docs/derivations/scripts/s07_measurements/`. Digests (sha256 of the records):
  - **S07 (G2):** pre-change (`2cd05bca`) and after the refactor `16387740`
    `405a6a65ce234f44b6f902db9c775f394a7959369005266f9c5a5a392f83324f` (35803 keys); after D3 `c76bc19b`
    `2d95732312c94945c91527854c97f9f7c1f4056bf7b3068a69d7ad944779ceb3` (35890 keys: 35718 identical, 85 former
    refusals answered, 0 answers changed). Re-run with the committed scripts at `45cdcb19`: `2d957323…` reproduced.
  - **S05 (G7(b)):** `2bd5e0edc2f1dd001b89d51a313c4fd728481086a2f75493bacd151fccfd7b8e` before and after
    `8cab0e15` (38010 lines, 22782 keys); reproduced at `45cdcb19`.
- **`def4a3ec` A48 references (§19.5).** 30 references in `fluids[*].nc_saturation` (I8 claimed to 1e-30 each).
  `NC_FALLBACK_T`, registered from `nc_scan.py` (which now records every fallback T), at θ: Cyclopentane 4.46e-3,
  R1234ze_Z 1.21e-3, R134a 8.89e-4, MDM 2.11e-4, MM 2.11e-4, R14 2.00e-4, R114 1.59e-4, Neon 1.38e-4, Ethanol
  1.19e-4, R13 8.89e-5, Deuterium 7.14e-5, Fluorine 6.29e-5, R152A 5.30e-5. A48 passes 30/30: θ ≥ 1e-4 (25) worst
  ρ 1.45e-10, p_σ 1.33e-13; θ < 1e-4 (5) worst ρ 4.06e-9, p_σ 2.42e-12 (all R22).
  - **B-34 — DECISION (layout):** a per-fluid key `nc_saturation` (`{label: {T, rho_l, rho_v, Psat}}`, labels
    `theta_2e-4`, `theta_1e-4`, `theta_5e-5`, `fallback`; empty for the other fluids), added to C3's whitelist.
    Alternative: entries in `saturation` (whose tests parametrize over fixed keys). Reversible: move the key.
- **F-6 h-scan record (§19.6)**, the two fluids above 1e-11, measured by the reviewer (`docs/reviews/S07-review.md`):
  R22 `L_corner` h in P 2.1e-11…6.6e-11 and s in T 2.9e-11…7.5e-11 over h/x = 1e-8…1e-4 (independent of h: value
  noise); PropyleneGlycol `S_dense` cp in T 2.1e-13 → 1.3e-5 (∝ h³: truncation). Both accepted.
- **Gates.** `s07_reference.py --check`: all claims, json and fluid table byte-identical on re-run (329 s). S05 + S07
  (7 files): 3833 passed, 1 skipped; project venv 766 passed, 3068 skipped. ruff and format clean.
- **DECISION:** S05 A33 evidence carried in S07's manifest (reviewer default; session, 2026-10-23).

## Handoff: next

The review fixes (§19.8) and WO-S07-NC4 are done (above); A45–A50 and C-strip pass on x86-64. Next: WO-S07-3
(registration manifest with the U02 item, the S05 section carrying `8cab0e15`'s A33 evidence, A29–A31, platform
digest, the G2/G7(b) digests above), then G9 (full gate, CI on both architectures; §19.1's θ_min remedy if A45
fails on aarch64).
