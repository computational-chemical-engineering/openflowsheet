# S07 generator review (WO-S07-1b, before WO-S07-2a)

**Reviewer:** design lane (`reviewer`), 2026-10-23. **Reviewed:** `a04c8924` on `wp/S07`:
`docs/derivations/scripts/s07_reference.py`, `s07_reference.json` (1 115 539 B), `_coolprop_heos_fluids.py`,
`docs/S07_DECISIONS.md` B-3…B-14 and Q-B1…Q-B3. **Against:** spec §2.2, §6, §7, §8, §12.1, §16, §17; ADR 0046.
**Rulings:** spec §18 (Amendment 2), register R-625.

## Verdict

**WO-S07-2a may start.** No finding is a must-fix. The expectations are independent of CoolProp's evaluation, as
rule 1 requires. Every committed jet reproduces CoolProp at the floor. The tier labels reach the records. Compaction
is lossless. Finding 1 is a generator change, made at the next regeneration, before S07's manifest. No stored
value moves.

## What was checked, and how

- **Independence (read).** Every stored number comes from the closed forms (`Eos.a0`, `Eos.ar`) by `mp.diff`, the
  generator's own density roots and Maxwell solve, or central differences at 110 digits (`Fluid.cdiff`). CoolProp
  supplies the fluid JSON, seeds, `melting_line`, `Ttriple`/`p_triple` (domain constants, as §6.1 and §16.4 allow)
  and C11's admission values. None of these is stored as an expectation. The §16.2 cp° integrals were re-derived for
  t = 0, t = −1 and general t, and they match `a0`.
- **The committed jets against CoolProp 8.0.0 (re-run here,** `scratchpad/rv/jetcheck.py`). At every stored φ state
  of all 123 fluids, |Δ|/max(|ref|, 1):
  - tier A: orders ≤ 2 at 1.1e-14, order 3 at 8.0e-14 (N2, φ_dilute);
  - `delta_one` (H2O, CO2), third order included: 1.6e-13 (CO2, αʳ_δδδ);
  - tier B: orders ≤ 2 at 9.0e-13 (R22, αʳ_ττ, φ_liq), order 3 at 6.9e-13 (MM).

  This reproduces m4 and m7 from the committed file. A03 and A04 have margins of ≥ 11× (tier B) and ≥ 63×
  (`delta_one`).
- **§16.3 against the output.** All 123 rows match (name, bound, T_lo, T_hi, P_hi). The table module lists the fluids
  in §16.3's order. There are 13 exclusions, and every `dropped` list is empty.
- **Compaction.** `encode()` refuses unless `json.loads(text) == doc` holds, with exact float equality. The
  structure is complete:
  - tier A: 8 TP states with `dT`/`dP`, 3 saturation rows with phase values, `tsat_mid` with slope, band values,
    `s04_ig`, and `delta_one` for H2O and CO2;
  - tier B: 6 TP states, `sat_mid`, `tsat_mid`, and band sets only;
  - 29–30 probes per fluid.
- **Tier labels.** Verification strings: `independent:S05` once, `independent:S04-ig` 8 times, `self-consistent`
  114 times. The E-limitation sentence is on exactly the 96 E fluids. The same strings are in the table module.
- **Probes.** `Fluid.expect` follows §6.5's precedence for rows 1–3 and 5–9. Every control is answered.

## Findings (most severe first)

1. **Should fix (generator). C12 checks less than its text says.** `s07_reference.py:1464-1516` compares φ partials,
   TP values and Psat only. It skips S05's TP derivatives, the saturated phases' values, dPsat/dT, and Tsat with
   dTsat/dP. These are the generator's generic `cdiff`, `sat` and `tsat_solve` paths, and no external check covers
   them at generation time.
   - **Measured here** (`rv/c12x.py`, `rv/c12z.py`):
     - all agree with S05;
     - derivatives ≤ 1.7e-12 relative. The worst is dcp/dT at L_ambient, which is −5.85e-3, near liquid water's
       cp minimum; scaled by cp/T it is 3.9e-14;
     - Tsat 5.8e-15, saturated-phase values ≤ 4.8e-14;
     - s_l(T_t) = 6.5e-14 J/(mol K) (the datum), so it must be judged absolutely: the difference is 5e-15·R.
   - **Fix:** §18.3's C12, then regenerate. Only water's `agreement` and the claim counts change.
2. **Should fix (spec; fixed here, §18.4).** A33(a) says `admitted()` equals ref `fluids` "in order". ref sorts its
   keys (§8), so it carries no order, and the test could not be written as stated.
3. **Note, a risk for WO-S07-2a (Q-A1-5 reaches tier A).** At C3H8's `sat_lo` (94.7 K), Z_L = 3.8e-10. C2H6's
   is 1.8e-6. Water at T_t, the regime S05 validated, has 4.9e-6. A Psat taken from the liquid-branch pressure
   carries about ε/Z_L ≈ 3e-7 relative error. Take Psat from the vapour branch, or from a Maxwell form that does not
   cancel. If A08 or A10 fails there, stop for the design lane.
4. **Note. C16 is a tripwire, not an implementation** (`:1585-1591`). Any row refuses, and
   `verification()`'s `published-check` branch is unreachable. WO-S07-4 must implement C16 and the quantities its
   rows need (w and c_v, which the generator does not compute).
5. **Note. Some claim entries are vacuous.**
   - `claim("C17", True, …)` (`:1702`) is the entry that gets counted. The real size check (`:1713`) runs after the
     counts are taken.
   - C1's "EOS[0] is the EOS parsed" holds by construction. The evidence that HEOS evaluates `EOS[0]` is C11, A03
     and the jet check above.
   - Fix at the next regeneration: count the real C17 check, and reword C1.
6. **Note. The saturation-branch claim (ρ' > ρ_c > ρ'') is not made everywhere.** It covers `sat_lo`/`sat_mid`/`sat_hi`
   and C8's 23 temperatures (`:986`, `:1441`), but not T_c(1 − 5e-4) (`:1002`, the NC states) and not
   `tsat_solve`.
   - A trivial solution would raise on the singular Jacobian, and C11 would catch a wrong NC pressure, so nothing
     fails silently.
   - Move the claim into `Fluid.sat()`.
7. **Note (spec wording; fixed here, §18.5).** §16.4's "exact decimal value of the double (`Decimal(repr(x))`)"
   contradicts itself, because `repr` is the shortest round-trip decimal. The generator follows the parenthetical,
   and the wording now matches it.

## Not examined

- The build's `--jobs` byte-identity, its timing, and its C11/C12/C18 numbers were accepted, not re-run.
- C8's grid internals were read only.
- The table module's formatting, `published_checks.yaml` beyond `rows: []`, and A29 packaging were not examined.
