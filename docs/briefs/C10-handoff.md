# C10 handoff — specifier stopped at the context cap (2026-10-22)

**Done:** read the brief, CLAUDE.md, `thermo/__init__.py`, `pr_c1.py` header, ADR 0043/0026 D4/0001 D5/0012 D1–D3, L01-spec §3/§5 pattern,
R-565. Eleven `DECISION:` lines in `docs/C10_DECISIONS.md` (id S05, sources, generator layout, coefficients, `IAPWS95-ref-v1`,
domain, phase rule, properties, flash, root bracket, rights). C10-Q1/Q2 appended to `docs/FRANK_QUESTIONS.md`.
**Not written:** ADR 0045, `docs/derivations/S05-IAPWS95-spec.md`, generators and their JSON, register R-585…R-594.

**Measured facts (do not re-measure):**
- iapws.org: proxy CONNECT 403. The release tables cannot be read, so use two-implementation agreement.
- CoolProp 8.0.0 is at `/home/user/venv-l01-sources/bin/python` (MIT). `CP.get_fluid_param_string('Water','JSON')`: sha256
  `a10a0da6…0dec4586`. EOS keys: `alpha0` (Lead a1/a2, LogTau 3.00632, 5 Planck–Einstein) and `alphar` (Power, Gaussian,
  NonAnalytic); `gas_constant` 8.314371357587; `molar_mass` 0.018015268; reducing T 647.096 K, p 22064000 Pa, ρ 17873.72799560906 mol/m³.
- `iapws` 1.5.5 is in the scratch venv `/tmp/claude-0/-home-user-openflowsheet/2d2da80b-dab5-573b-9a3f-ceefc20b228b/scratchpad/venv-iapws`
  (GPL-3; `IAPWS95` "revised release of 2016"). It has the same n°1 and n°2 as CoolProp and R 8.314371357587, and carries no verification tables.

**Next agent (specifier, fresh, ~120k):**
1. Write `s05_crosscheck.py` (scratch venv with both packages; `--check`). It transcribes the coefficients to
   `s05_iapws95_coefficients.json`, asserts they equal iapws's exactly, and evaluates the states with both implementations.
2. Write `s05_reference.py` (mpmath 50 digits; `--check`). It covers the R6-95 Table-6 points (500 K, 838.025 kg/m³; 647 K, 358 kg/m³)
   for φ°/φʳ and the derivatives, about 8 single-phase (T,P) states across both branches and the supercritical region, and saturation at
   275, 450, 625 and 647.0 K. It emits the 9-digit roundings for the pending Table 6–8 check, and refuses to emit if the cross-check
   disagrees or any self-claim in the decisions fails.
3. Write the spec (§ order as L01-spec), with assertions S05.A01…: coefficients bitwise; φ derivatives; p, h, s, cp, lnφ, v and Z by
   state; the T/P/n derivatives by central differences, with the measured floor; Maxwell (equal p and g); the Psat
   Clausius–Clapeyron slope; every typed refusal with a control; the ε_σ band; and `tp_flash_degenerate`.
   Add two work orders of about 120k each, the manifest check list and the non-claims (no IF97, no transport, no binding, no W27).
4. Write ADR 0045 (pattern ADR 0043) and the register R-585…R-594 (format as R-569). Copy the DECISION lines into the spec.
