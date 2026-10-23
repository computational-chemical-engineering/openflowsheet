# C10 handoff — second specifier pass (2026-10-22)

**Done (on `wp/C10`):**
- ADR 0045 (Proposed).
- `docs/derivations/S05-IAPWS95-spec.md`, §0–§13: derivation, domain, phase rule, brackets, refusal table, registered
  states, S05.A01–A30 with tolerances, self-claims, findings F-1…F-3, non-claims, Q-1…Q-6, WO-S05-1/2, manifest list.
- Register R-585…R-594, and five amending DECISION lines in `docs/C10_DECISIONS.md`.

**Generators:**
- `s05_crosscheck.py` (scratch venv `…/scratchpad/venv-iapws`, which now also holds CoolProp 8.0.0 and mpmath 1.3.0;
  run with `-I`). It writes `s05_iapws95_coefficients.json` (SHA-256 `b9e93877…`) and `s05_crosscheck.json`, and
  its `--check` passes.
- `s05_reference.py` (project venv, about 5 minutes) writes `s05_reference.json`. Its claims cover admission with a
  10× margin, identities I1–I9, the datum, the box, the band, and the bracket grid at 31 temperatures.

**Measured (do not re-measure):**
- Worst agreements: φ 4e-14; TP values 4.9e-10 (CoolProp) and 2e-12 (iapws); NC states 4.3e-8 (CoolProp; hence the
  ×100 factor); iapws's Tsat is loose at 1e-8; |Z − 1| at `SC_ideal` is 6.3e-8.
- CoolProp's central-difference floor at step 1e-6 is 1e-4 to 1e-3, from solver noise. So A17 is in value units with
  FD_TOL = 1e-10 (Q-6).

**Remaining gaps:**
- Q-1: the R6-95 Tables 6–8 comparison and the rights (C10-Q1).
- Q-5: admission of the third-order φ partials.
- Q-6: the provider's own FD floor (WO-S05-1 measures it).
- F-1: the ADR 0001 D5 / `interfaces-frozen.md` line is to be written on acceptance.
- `reviewer` pass on this spec (build-lane review for coverage and packaging).

**Next:** the build lane runs WO-S05-1 (provider plus A01–A21, A23–A24), then WO-S05-2 (A22, A25–A30, manifest).
