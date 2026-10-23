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

## Handoff: WO-S07-2a (the provider, tier A) — not started (engineer context cap reached after step 0)

Read: spec §3–§6 (l.123–330), §7 (l.331), §9 + §9.1 (l.391–451), §12.2 (l.506), §16.8–§16.10 (l.972–1052), §18
(l.1488–1565); S05 §3–§4 and `iapws95.py`'s `_saturation`, `_bracketed_density`, `_metastable_density`, `_rule` as
the algorithm to generalize (do not import them; `iapws95.PhiJet` import only). Template tests:
`tests/test_s05_iapws95.py`, `tests/test_s05_envelope.py` (`_starved` for §18.1's row-10 injection).
- ref layout per fluid: `constants`, `canary`, `phi_states`, `tp_states/<key>` = {phase, values [T, P, h, s, v, Z,
  cp, lnphi], dT [6], dP [6]}, `saturation/sat_{lo,mid,hi}` = {T, Psat, dPsat_dT, dh_vap, L [T, P, 6], V [T, P, 6]},
  `tsat/tsat_mid` = {P, Tsat, dTsat_dP}, `band`, `probes` (compact lists, `compact_request` in the generator),
  `s04_ig`, `verification`, `limitations`. Constants come from `_coolprop_heos_fluids.py` (A01 bitwise).
- Psat must come from the vapour branch or a non-cancelling Maxwell form (review finding 3): C3H8 `sat_lo` has
  Z_L = 3.8e-10. If A08/A10 fails there: measure, record here, STOP for a design ruling (no per-state tolerance).
- A04 at `delta_one` > 1e-12 → stop (§18.6). A17 floor > 1e-11 for any fluid → stop (§9.1). Settle Q-3 (A26(c))
  and F-5 (T08's provider scan vs the underscore table module).
- Test env: `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/venv`
  has CoolProp 8.0.0 at the pinned gitrevision plus pytest; run with `PYTHONPATH=$PWD/src:$PWD
  OPENFLOWSHEET_REQUIRE_COOLPROP=1`.
