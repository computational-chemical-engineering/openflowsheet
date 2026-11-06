# F6-std-seed — the `std.*` equation sheet on the `h_mass` coordinate (SQ-F6-2)

Status: design-lane specification (`specifier`), 2026-11-05. Brief: `docs/roadmap/brief-specifier-W1-P3-questions.md`
(deliverable B). Answers ADR 0065's SQ-F6-2 (D16, risk 1). Once ADR 0065 adopts it, the ADR is the authority and this
sheet its derivation. Expectations: `docs/derivations/scripts/f6_std_seed_reference.py`, which writes
`f6_std_seed_reference.json` and refuses to emit when one of its 107 claims about this sheet's states fails;
`--check` byte-compares (`python3 -I docs/derivations/scripts/f6_std_seed_reference.py --check`).

## 0. Authority, scope and limits

- **Scope.** For each `std.*` unit of ADR 0065 D16 (feed, sink, mixer, splitter, heater, valve, flash, pump with
  `work_model: isentropic | incompressible`, compressor, turbine, steady `std.pid`): the `h_mass` row set, division-free
  (Q1.R2), with the T-form rows it restates; its zero-flow forms (Q1.R4, Q5.R7; ADR 0012 D4 (c)/D12 as generalised by
  ADR 0065 D7); its reactivation kind (Q1.R6, ADR 0065 D8) and `t_seed`; and closed-form checks a test can assert.
- **Sources of the restated rows.** SYN-001 §4 and T05 §5–§9 (`syn001.*`), S11 units design §4.4 and ADR 0051
  (`thermal.*`), ADR 0012 D12 (dormancy forms), ADR 0065 D6–D11, foundation rulings Q1.R1–R6, Q5.R7, Q4.R9, Q5.R9.
- **Consistency.** Nothing here touches `nTP-v1`, a v1 document, a legacy unit or a registered fixture. The T-form
  variants F6-WO5 builds first keep the legacy rows; this sheet is the `h_mass` variant. Where it needs an ADR to say
  more, §7 lists the edit; it edits no ADR.

## 1. Notation

- A material connection S carries `(n_S, ĥ_S, P_S)` (Q1.R1). ṁ_S = Σ_c M_c n_S,c, summed in component order, no fma.
  **Ḣ_S ≡ ṁ_S·ĥ_S is an expression inside a row, never a column.** Ports: I (inlet), O (outlet), k (k-th inlet of a
  `many` port in the revision's `connections` order; k = 1 is the first).
- Q (W) and W (W) are the energy-port variables, positive into the unit (ADR 0001 D4.1).
- State points (note §2.3.9, ADR 0063 D7): PH(n, ĥ, P), TP(n, T, P), XP(n, X, P) for X ∈ {T, β, ŝ, v}, and PS(n, Ṡ, P)
  with an extensive entropy specification (C8). Ḣ^pt = Σ_p Ḣ_p over the point's phase slots in canonical order, each
  read with ADR 0065 D6's `amount_weighted` accessor (exactly `+0.0` at an inactive slot); V̇^pt and Ṡ^pt likewise.
- Row ids are suggested spellings `<U>:<row>`; the kinds are those of the T-form row restated (`heat_rate` for energy
  rows, `specific_enthalpy` for ĥ rows and labels).
- "Label of U" = ĥ of U's first material inlet connection; `+0.0` for a unit without one (Q1.R4).

## 2. The sheet method (closed forms for every check)

A **test-only** composed method, `test.syn001-elemental` (suggested id): SYN-001 §1's potentials verbatim, `split`
(VAPOR ideal gas, LIQUID ideal solution with constant v), records A, B, C (M = 0.1 kg/mol, no formation data, anchor
`ig` by Q2.R9), composed on `ELEMENTAL-ref-v1`. It exists because ADR 0063 composes no SYN-001 method (finding A4-a of
the rulings) and every other seeded method lacks closed forms. Q2.R4's datum puts h = 0 and s = 0 at the ideal gas at
(T°, P°), T° the double nearest 298.15 K, P° = 1e5 Pa = P_r. Since SYN-001's vapour is its ideal gas, the shifts are
Δ_c = −(c_p (T° − T_r) + L_c) and Δˢ_c = −(c_p ln(T°/T_r) + L_c/T_b,c), and in exact arithmetic (per mole; per kg divide
by M, so ĉ_p = 1000 J/(kg K), L̂ = (2.5e5, 3e5, 3.5e5) J/kg, v̂ = 1e-3 m³/kg):

    h_c^V = c_p (T − T°)                          s_c^V = c_p ln(T/T°) − R ln(P/P°) − R ln y_c
    h_c^L = c_p (T − T°) − L_c + v (P − P_r)      s_c^L = c_p ln(T/T°) − L_c/T_b,c − R ln x_c
    K_c   = (P_r/P) exp[(L_c/R)(1/T_b,c − 1/T) + v (P − P_r)/(R T)]           (SYN-001 §3, unchanged)

Consequences the checks use: liquids mix and throttle with c_p constant, so a liquid's T is linear in ĥ at fixed
composition; ideal-gas h is P-independent; the liquid's s is P-independent, so an isentropic liquid compression is
isothermal (T05 §9.3); pure B boils at exactly 360 K at P_r (K_B(360 K, P_r) = 1). Domain: 280–440 K, 5e4–2e5 Pa;
outside it the method refuses typed. The entropy datum makes every s here carry `entropy_datum` (Q2.R10); every check
below uses s only at fixed amounts, which Q2.R10 (b) admits.

## 3. Rules common to every unit

- **C1 Coordinate-free rows stay.** Every mole, split, pressure and specification-on-a-variable row of the T-form unit
  is used verbatim; only rows containing T or Ḣ change.
- **C2 Thermal rows.** A T-form row with Ḣ_S = Ḣ(n_S, T_S, P_S) becomes the same row with ṁ_S ĥ_S (Q1.R2). When every
  term of a balance carries the same ṁ (mole rows make ṁ_O = ṁ_I bitwise: same amounts, same summation), the row is
  written as the copy ĥ_O − ĥ_I = 0 instead: the same solution where flowing, exact (bitwise) and regular at dormancy,
  where it gives Q1.R4's label without a form. Valve and splitter use it.
- **C3 Specifications on derived intensives.** A Specification v2 target `{derived: X, stream: S}` with X ∈ {T, β, ŝ, v}
  on an `h_mass` connection compiles to the **X-form row** ṁ_S ĥ_S − Ḣ^XP(n_S, X_spec, P_S) = 0 through an XP point at
  S's amounts: division-free, explicit, and refused typed (`specification_degenerate(<spec>)`) where (X, P) does not fix
  the state (T of a pure fluid at T_sat). If S is a routed outlet (ADR 0065 D9) of a unit with a state point, the target
  means that point's X and the row is written on the point's inputs (std.flash: the drum, applicable while the drum
  flows even when S's phase is inactive). Other derived targets read S's PH point (`raw`).
- **C4 Dormant points.** A state point whose input amounts are all exactly `+0.0` is not evaluated; every output is the
  label `+0.0` with derivative `+0.0`, null in reports (`zero_flow`). `amount_weighted` reads of it are `+0.0`; a `raw`
  read must be swapped by a form, else the opening is refused `inactive_phase_read(<row>, <point>)` (ADR 0065 D6's
  rule). Point-level outputs (T, P) of a point that is not dormant are readable at any slot.
- **C5 One label per dormant ĥ.** When a connection's ĥ (or a unit-owned ĥ, std.flash's ĥ_D) loses rank at dormancy,
  exactly one row leaves for its label row ĥ − ĥ_label = 0 (ĥ_label: the label of U): the specification row reading
  the corresponding dormant point if there is one (C3), reported `not_applicable(zero_flow)` and not tested; else the
  unit's declared swap row, which must hold at closure (ADR 0012 D4 (c)'s test, `zero_flow_conflict(<row>)`). Without a
  derived specification the unit's form acts; with one, the unit's energy row stays and fixes the duty or work.
- **C6 Reactivation.** ADR 0065 D8's kinds. An owned ĥ last written by a label is re-seeded like an outlet, before any
  point that reads it. `t_seed` (Q1.R6 (2)): the T an X-form specification fixes, else the derived T of the first
  flowing non-label inlet. A quotient in a seed is computed only for a flowing ṁ.
- **C7 Stream points.** A flowing connection's derived T is its PH point under the producer's method (Q1.R3), a
  post-solve projection no row reads; the verifier evaluates it for every flowing connection (ADR 0063 D8). A refused
  stream point means the state is not a state of the method; the run cannot be `VERIFIED` (finding F6S-a, §7).
- **C8 Isentropic references.** A PS point takes the extensive specification (Ṡ, P) at its amounts, solving
  Ṡ(T, P, n) − Ṡ_spec = 0: the entropy analogue of Q1.R2, with no ŝ = Ṡ/ṁ quotient (edit B-6).

**Tolerance classes** used by every assertion below.
- **(R) Rows at the closed form.** The unit's compiled rows evaluated at the closed-form state on the sheet method:
  |r| ≤ 1e-12 × the largest |term| of the row. Floor: at most eight terms, each a few roundings of composed values
  (native + shift), ≲ 30 ε ≈ 7e-15 relative; margin ≥ 100.
- **(P) Points at an exact input.** Given ĥ (the generator's value as a double): T within 3e-9 K, β within 1e-10.
  Floor: a PH solve to 1e-12 relative in ĥ (O-1's default) moves T by ≤ 1e-12 |ĥ|/ĉ_p,eff ≤ 3e-10 K at |ĥ| ≤ 3e5 J/kg,
  ĉ_p ≥ 1000 J/(kg K); margin 10 (O-1 measures it).
- **(S) Solves.** `VERIFIED`, and each solved ĥ within τ_E/ṁ of the closed form, each derived T within
  τ_E/(ṁ ĉ_p,eff), each duty or work within τ_E: the certificate's own bounds mapped through the closed form; at
  registered states the achieved residuals sit ≥ 7 decades below them (ADR 0007 D2.4).
- **(B) Bitwise.** Copies, labels and dormant zeros, after signed-zero normalisation.

## 4. The units

Each block: ports; the T-form rows → the `h_mass` rows; forms; reactivation; checks (case ids in the JSON).

### 4.1 `std.feed`
Ports `outlet`; parameters `n_spec` (per amount index), `P_spec`, structural `thermal_spec: T | h_mass` with `T_spec` or
`ĥ_spec`. Restates `syn001.feed_source` (n, T, P pinned).
- `FEED-n:<c>` n_c − n_spec,c = 0 and `FEED-P` P − P_spec = 0 (C1).
- `FEED-h`: T: ṁ ĥ − Ḣ^TP(n, T_spec, P) = 0 (point `feed`); h_mass: ĥ − ĥ_spec = 0 (regular at dormancy, no form).
- Form `feed-dormant`: trigger `{port: outlet}`; swap `[FEED-h]`; label `zero` (ĥ = `+0.0`).
- Reactivation `feed_spec`; `t_seed` = T_spec.
- **F6S.A1** FEED-1, (1, 1, 1) mol/s, 300 K, P_r (liquid, 47 K below its bubble point): ĥ = −298 149.999 999 999 96
  J/kg (R, S); the h_mass variant with that ĥ_spec gives the same state (B on ĥ). FEED-Z, n_spec = 0: ĥ = `+0.0` (B),
  T null (`zero_flow`), point `feed` not evaluated (instrumented count 0). Mutation: a molar ĥ (×10) or a dropped L_c
  (ĥ = +1 850 J/kg) fails (R).

### 4.2 `std.sink`
Port `inlet`; no rows, no points, no forms. Its inlet's derived T is a stream point (C7).

### 4.3 `std.mixer`
Ports `inlet` (many), `outlet`. Restates `TM-*` / `MIX-*`: mole and pressure rows verbatim (C1);
- `MIX-energy`: Σ_k ṁ_k ĥ_k − ṁ_O ĥ_O = 0, summed in connection order. A dormant inlet contributes exactly ±0.0 and
  its Jacobian entries M_c ĥ_k carry its label as a coefficient (no property input; n_k is fixed by its producer).
- Form `mixer-dormant`: trigger `{port: inlet}` (every inlet connection dormant); swap `[MIX-energy]`; label of U.
- Reactivation `unit_code`: one flowing inlet → its ĥ (copy, bitwise); several → Σ_k ṁ_k ĥ_k / Σ_k ṁ_k over flowing
  inlets in connection order.
- **F6S.A2** MIX-1: (1, 1, 1) at 300 K with (0.2, 0.3, 0.5) at 340 K, both liquid at P_r: the latent terms cancel
  component by component, so T_O = (3·300 + 1·340)/4 = 310 K, ĥ_O = −291 899.999 999 999 96 J/kg (R, S; P: T = 310 K).
  MIX-Z: the second inlet (0, 0, 0): ĥ_O within 1e-14 relative of ĥ_1 (Q1.A5), T_O = 300 K. All inlets dormant: ĥ_O
  bitwise ĥ_1 (B). Registered with distinct inlet temperatures and compositions so that a permuted inlet index or a
  mole-weighted (not mass-weighted) ĥ fails (R).

### 4.4 `std.splitter`
Ports `inlet`, `outlet` (J ≥ 2); split fractions as the T-form unit (C1).
- `SPL-h:<j>`: ĥ_Oj − ĥ_I = 0 (the T-form's "same T" restated as "same ĥ", C2; at a degenerate T only this one is
  well posed).
- No form: at inlet dormancy and at φ_j = 0 the copy already is Q1.R4's label (B).
- Reactivation `copy_inlet`.
- **F6S.A3** Every outlet ĥ bitwise the inlet's, flowing, dormant inlet, and φ_j = 0 (B); Q1.A9 (a) on reactivation
  0 → 0.3.

### 4.5 `std.heater`
Ports `inlet`, `outlet`, `duty` (energy, inlet); parameter `pressure_drop` ΔP ≥ 0. Restates `TH-*` (`thermal.heater`)
and `syn001.tp_heater`; T, duty and quality modes are specifications (ADR 0065 D16).
- `HTR-energy`: Q + ṁ_I ĥ_I − ṁ_O ĥ_O = 0. Mole and pressure (P_O − P_I + ΔP) rows verbatim.
- Specifications: duty Q − Q_spec = 0 (`{energy: …}`); outlet T or quality: the X-form row (C3) with TP or βP.
- Form `heater-dormant`: trigger `{port: inlet}`; swap `[HTR-energy]`; label of U. With an X-form specification on the
  outlet, C5 swaps that row instead and `HTR-energy` gives Q = 0. A dormant inlet with Q_spec ≠ 0 closes
  `zero_flow_conflict(HTR-energy)` (legacy `duty_into_dormant_stream`).
- Reactivation `unit_code`: X-form → Ḣ^XP(n_O, X_spec, P_O)/ṁ_O; else ĥ_I + Q/ṁ_I. `t_seed` = T_spec.
- **F6S.A4** HTR-T: FEED-1 → T_spec = 350 K: the outlet is two-phase with β = 0.101 368 723 426 727 76 (SYN-001 §3.1),
  vapour amounts (0.201 537 429 847 853 78, 0.078 098 253 651 684 78, 0.024 470 486 780 644 716) mol/s, ĥ_O =
  −220 690.498 689 768 45 J/kg, Q = 23 237.850 393 069 45 W (R, S). HTR-Q: the duty mode with Q_spec = that Q as a
  double gives T_O = 350 K and β as above (P, S). HTR-L6000 / L3000 / L0 (liquid, used by Q5.A11): T_O = 300 K +
  Q/(300 W/K) = 320, 310, 300 K. Pure B (0, 1, 0) at 300 K with T_spec = 360 K = T_sat(P_r): refused
  `specification_degenerate(<spec>)`; with quality β = 0.25 instead: ĥ_O = FLS-B25's ĥ (R). Dormant inlet: ĥ_O
  bitwise ĥ_I in both modes, Q = 0 in T mode (B). Mutation: a dropped latent term puts HTR-Q at T_O ≈ 377.5 K.

### 4.6 `std.valve`
Ports `inlet`, `outlet`; parameter `P_spec` (outlet pressure, R-040). Restates `VLV-*` / `TV-*`.
- `VLV-h`: ĥ_O − ĥ_I = 0 (C2: `VLV-energy` Ḣ_I − Ḣ_O = 0 has ṁ in both terms). Mole and `VLV-P` (P_O − P_spec) rows
  verbatim; P_spec ≤ P_I stays a one-sided verifier check (T05 §8).
- No form; reactivation `copy_inlet`.
- **F6S.A5** VLV-1: (1.2, 0.9, 0.3), 300 K, 1.8e5 Pa → P_r: T_O = 300 + v ΔP/c_p = 300.08 K (P; registered because it
  does not vanish). VLV-2: (1, 1, 1), 360 K, 1.8e5 Pa → P_r: two-phase, T_O = 348.499 864 419 208 926 K (T05's
  registered value, re-derived), β = 0.042 984 057 662 572 83 (P). VLV-3: (1, 1, 1) vapour, 420 K, 1.5e5 → 6e4 Pa:
  T_O = 420 K (P; vanishes because the ideal gas's h is P-independent, VLV-1 does not). In all three ĥ_O = ĥ_I (B).

### 4.7 `std.flash`
Ports `inlet` (many), routed outlets per `phase_routing` (ADR 0065 D9, Q4.R9; here `vapor`, `liquid`), `duty`;
parameter ΔP ≥ 0. Owned: ĥ_D (`specific_enthalpy`). Point `drum`: PH(n_D, ĥ_D, P_D) with n_D,c = Σ_k n_k,c and
P_D = P_1 − ΔP, candidates the method's, no declared phase. Restates `PHF-*` (`syn001.ph_flash`) and `TF-*`
(`thermal.flash`); `syn001.tp_flash` is its T specification.
- `FLS-energy`: Σ_k ṁ_k ĥ_k + Q − ṁ_D ĥ_D = 0, ṁ_D = Σ_c M_c n_D,c (the same sum the point uses).
- `FLS-n:<port>:<c>`: n_port,c − Σ_{p→port} n_p,c = 0 (phase amounts are always readable).
- `FLS-h:<port>`: ṁ_port ĥ_port − Σ_{p→port} Ḣ_p = 0.
- `FLS-P:<port>`: P_port − P_1 + ΔP = 0; `FLS-Pin:<k>`: P_k − P_1 = 0 for k ≥ 2 (the mixer's rule).
- PHF-equilibrium, PHF-T and the lifting rows live inside the point (ADR 0064's formulation).
- Specifications: duty Q − Q_spec = 0; T on any routed outlet means the drum's T (C3): ṁ_D ĥ_D − Ḣ^TP(n_D, T_spec, P_D)
  = 0.
- Forms: `flash-dormant`, trigger `{port: inlet}`, swap `[FLS-energy]`, label of U on ĥ_D; `flash-outlet-<port>`,
  trigger `{port: <port>}` (fixed at the opening by the routed slots' activity), swap `[FLS-h:<port>]`, label of U.
  With the drum dormant every form is selected; a T specification is then the row C5 swaps for ĥ_D's label, and
  `FLS-energy` gives Q = 0.
- Reactivation: ĥ_D `unit_code` (T specification: Ḣ^TP(n_D, T_spec, P_D)/ṁ_D; else (Σ_k ṁ_k ĥ_k + Q)/ṁ_D, one flowing
  inlet with Q = 0 a bitwise copy); outlets `phase_outlet` from the opening's drum point. `t_seed` = T_spec.
- **F6S.A6** FLS-B25 / B50 / B75: pure B (0, 1, 0) mol/s at P_r, ĥ_D = −163 149.999 999 999 97, −88 149.999 999 999 97,
  −13 149.999 999 999 977 J/kg: T = 360 K and β = 0.25, 0.5, 0.75 (P; π = C + 1, registered because T cannot decide
  it and ĥ must); a T specification on that drum is refused `specification_degenerate`. FLS-1: FEED-1 with Q_spec =
  HTR-T's Q: T = 350 K, β and vapour amounts as F6S.A4 (P, S); with T_spec = 350 K: Q = 23 237.850 393 069 45 W (S).
  Subcooled drum (FEED-1, Q = 0): `vapor` dormant with ĥ bitwise ĥ_1 (B), ĥ_liquid within 1e-14 relative of ĥ_D.
  Mutation: routing by slot ordinal instead of D9 sends the B75 vapour to `liquid`.

### 4.8 `std.pump`, `std.compressor`, `std.turbine`
Ports `inlet`, `outlet`, `work` (energy, inlet); parameters `P_spec` (outlet), η ∈ (0, 1]; pump structural
`work_model`. Points: `in` = PH(n_I, ĥ_I, P_I); `isen` = PS(n_I, Ṡ^in, P_O) (C8), candidates the method's, no declared
phase (ADR 0064 D4), for every isentropic machine. Restates `PUMP-*`, `TPU-*`, `TCO-*`, `TTU-*`.
- `MCH-energy`: W + ṁ_I ĥ_I − ṁ_O ĥ_O = 0. Mole and `MCH-P` (P_O − P_spec) rows verbatim.
- `MCH-work`, isentropic: pump and compressor η W − (Ḣ^isen − ṁ_I ĥ_I) = 0; turbine W − η (Ḣ^isen − ṁ_I ĥ_I) = 0.
- `MCH-work`, pump `incompressible`: η W − (P_O − P_I) V̇^in = 0 (V̇^in = Σ_p n_p v_p of `in`). The legacy row
  [Ḣ^L(T_I, P_O) − Ḣ^L(T_I, P_I)] equals (P_O − P_I) V̇ exactly when (∂h/∂P)_T = v, i.e. on SYN-001, the only method
  the legacy pump admits; on a method with thermal expansion the isothermal Δh is not a pump work, so the `h_mass`
  variant writes V̇ΔP, the reference tools' form (T05 §9.3). F6-WO5's T-form variant uses the same V̇ΔP row.
- Admissibility (closure, as the legacy units): under `split`, a pump inlet point with VAPOR active closes
  `inadmissible_phase(inlet, VAPOR)`, a compressor or turbine inlet with LIQUID active `inadmissible_phase(inlet,
  LIQUID)`; under `single` no character test (Q4.R9's consequences stay with routing). Bounds as T05 §9 / S11 §4.4
  (one-sided verifier checks): pump and compressor P_spec ≥ P_I and W ≥ 0, turbine P_spec ≤ P_I and W ≤ 0.
- Form `machine-dormant`: trigger `{port: inlet}`; swap `[MCH-energy]`; label of U. At dormancy `in` and `isen` are
  dormant (C4); `MCH-work` reads them only `amount_weighted`, so it gives W = 0 and the swapped row holds.
- Reactivation `unit_code`: ĥ_O = ĥ_I + W/ṁ_I with W from `MCH-work` at the opening's points; if a point is refused
  there, Q1.R6 (2) at `t_seed` = the inlet's derived T.
- **F6S.A7** PMP-1: (1.2, 0.9, 0.3), 300 K, P_r → 1.8e5 Pa, η = 0.75: W_s = 19.2 W, W = 25.6 W, T_O =
  300.026 666 666 666 67 K (R, S), **for both work models, equal within 1e-12 relative**: registered because they
  coincide on SYN-001 (its liquid entropy is P-independent).
- **F6S.A8** PMP-W (`composed.iapws95-v1`, water, 1 kg/s, 300 K, 1e5 → 1e7 Pa, η = 1; expectations from
  `s05_reference.py`'s 50-digit IAPWS-95, an independent code path): `incompressible` W = 9 934.210 037 875 670 W,
  `isentropic` W = 9 912.552 011 108 970 W with T_s = 300.200 294 923 402 K, each within 1e-9 relative (floor: a PS
  solve to 1e-12 relative in Ṡ moves h_s by ≲ 1.2e-7 J/kg, 1.2e-11 relative; margin 80). The two differ by 21.66 W, 2e6
  tolerances: a pump reading the wrong `work_model` fails. Also Q2.R10 (b) on a real record: `s05`'s H2O has no s°.
- **F6S.A9** CMP-1: (1, 1, 1) vapour, 380 K, 6e4 → 1.5e5 Pa, η = 0.8: T_s = T_I (P_O/P_I)^(R/c_p) =
  410.081 492 890 735 24 K, W = 11 280.559 834 025 717 W, T_O = 417.601 866 113 419 06 K (R, S; the generator checks
  the isentropic state's S equals the inlet's and all three states are superheated and in the domain). TRB-1: 430 K,
  1.5e5 → 6e4 Pa, η = 0.85: T_s = 398.457 386 721 271 40 K, W = −8 043.366 386 075 794 W, T_O = 403.188 778 713 080 69 K.
  Mutation: η applied on the wrong side (turbine as compressor) gives W ≈ −11 132.7 W at TRB-1.
- **F6S.A10** E-F6-16 (the FB-04 turbine, IAPWS-95, wet outlet, no declared phase) against E-F5-6's reference: outlet β
  and ĥ within E-F5-6's registered tolerance; the outlet point is π = C + 1 and is carried by ĥ alone.
- **F6S.A11** Dormant inlet, each machine: W = 0, ĥ_O bitwise ĥ_I, no point evaluated (B; counter 0).

### 4.9 `std.pid` (steady)
No material port; ADR 0065 D10's rows with Q5.R9's closure. The `pv` probe reads its stream's PH point `raw`; with that
stream dormant the opening is refused `inactive_phase_read(<probe row>, <point>)` (C4): a controller cannot measure an
undefined temperature, and a refusal says so. **F6S.A12** = Q5.A11 (on F6S.A4's HTR-L cases).

### 4.10 Coverage table (E-F6-9's generated check must reproduce it)

| Unit | Rows changed by `h_mass` | Forms (trigger → swap) | Reactivation | `t_seed` |
| --- | --- | --- | --- | --- |
| feed | `FEED-h` | outlet → `FEED-h` (label `+0.0`); none for `ĥ_spec` | `feed_spec` | T_spec |
| sink | — | — | — | — |
| mixer | `MIX-energy` | all inlets → `MIX-energy` | `unit_code` | — |
| splitter | `SPL-h:<j>` (copy) | none | `copy_inlet` | — |
| heater | `HTR-energy`; X-form spec | inlet → `HTR-energy`, or the X-form spec (C5) | `unit_code` | T_spec |
| valve | `VLV-h` (copy) | none | `copy_inlet` | — |
| flash | `FLS-energy`, `FLS-h:<port>`, `FLS-n` | inlet → `FLS-energy` (ĥ_D); outlet port → `FLS-h:<port>` | ĥ_D `unit_code`; outlets `phase_outlet` | T_spec |
| pump, compressor, turbine | `MCH-energy`, `MCH-work` | inlet → `MCH-energy` | `unit_code` | inlet T (fallback) |
| pid | — | — (dormant pv refused) | — | — |

## 5. Why these forms (argument)

1. *Rank at dormancy.* Every `h_mass` energy row has ṁ_O as the coefficient of ĥ_O. When the trigger port is dormant
   the mole rows make n_O = 0, the row's ĥ_O entry vanishes, and its remaining gradient (n entries, plus Q or W) lies
   in the span of the mole rows and of the row that fixes Q or W: the row is dependent and ĥ_O free, which is ADR 0012
   D12's situation with ĥ in place of T. Which row to swap depends on what fixes the duty: with Q fixed (duty
   specification, or a machine's work row) the energy row; with Q free (an X-form specification) the specification
   row, which then reads a dormant point (C4). C5 is the rule that makes both cases one: one label per dormant ĥ.
2. *Copies.* Where every term carries the same ṁ, the copy row has no ṁ, never loses rank, and returns the label
   bitwise; Q1.A5 and Q1.A9 (a) need bitwise. In exact arithmetic it has the solutions of the balance where flowing.
3. *X-form specifications.* A PH-derived T read raw has dT/dĥ = 0 on a π = C + 1 plateau and an inner solve in the
   residual; the X-form row evaluates an explicit TP (or βP) point and fails typed where (X, P) underdetermines the
   state, which is exactly when a T specification is meaningless. On a non-degenerate state the two have the same
   solution set; on a flash outlet the X-form row on the outlet would place a TP point on a phase boundary by
   construction, so the target moves to the drum.
4. *Entropy-flow specification.* ŝ = Ṡ/ṁ divides; the PS point given Ṡ at the same amounts solves the same state and
   needs no division at any flow, and its datum cancels (Q2.R10 (b)).

## 6. Open questions, each with a default

| # | Question | Kind | What settles it | Default |
| --- | --- | --- | --- | --- |
| F6S-Q1 | (P)'s 3e-9 K margin rests on O-1's 1e-12 relative PH tolerance | fact | F4's measured PH/PS residual on the sheet method and on IAPWS-95 | 3e-9 K; amend if the measured margin is below 10× |
| F6S-Q2 | `std.feed`'s `thermal_spec: h_mass` option (the only feed of a π = C + 1 state) | Frank's preference | — | included |
| F6S-Q3 | Pump `incompressible` = V̇ΔP/η (equal to the legacy row on SYN-001, different with thermal expansion) | Frank's preference | — | V̇ΔP; the alternative keeps the legacy isothermal Δh and admits it on SYN-001 only |
| F6S-Q4 | Character test on a `single` method's machine inlet | needs a fact | whether any seeded `single` method with a machine reaches a liquid-like compressor inlet in the coverage matrix | none (refusals by `split` families only) |

## 7. Edits the ADRs need, and findings (the orchestrator applies them)

- **B-1 (ADR 0065 D6).** Add C4: a point with all amounts `+0.0` is dormant, not evaluated, labels `+0.0` with
  derivative `+0.0`; point-level T, P of a non-dormant point are readable at any slot.
- **B-2 (ADR 0065 D7).** Labels may target a unit-owned ĥ; add C5 (one label per dormant ĥ; a specification row
  reading a dormant point is the swapped row, reported `not_applicable(zero_flow)` and untested).
- **B-3 (ADR 0065 D8).** An owned ĥ written by a label is re-seeded (`unit_code`) before any point reading it; the kinds
  per §4.10.
- **B-4 (ADR 0065 D16).** "Not yet approved: … (**SQ-F6-2**)" → "Approved: `docs/derivations/F6-std-seed.md` (rows,
  forms, reactivation, `t_seed`, C1–C8)"; `std.pump`'s `incompressible` is V̇ΔP/η in both coordinates; risk 1 resolved.
- **B-5 (ADR 0065 exits).** F6-WO5's acceptance adds F6S.A1–A11 (A10 is E-F6-16); E-F6-9 checks §4.10's table.
- **B-6 (ADR 0063 D7; note §2.3.9).** State-point specifications may carry an extensive kind (`enthalpy_flow`,
  `entropy_flow`) at the point's amounts; the isentropic reference uses (Ṡ, P).
- **B-7 (ADR 0062 D10).** A `{derived: X, stream: S}` target on an `h_mass` connection compiles by C3.
- **Finding F6S-a.** No ADR names the verifier check that fails when a flowing stream's PH point (C7) is refused; until
  one does, such a run must not be `VERIFIED`. ADR 0065 (or ADR 0063 D8).
- **Finding F6S-b** (= rulings A4-a). ADR 0065 D17's `syn001` equivalence leg needs a SYN-001 composition ADR 0063 does
  not provide.

## 8. What this sheet does not establish

- No row here has run. Every expectation is a closed form of a synthetic method (SYN-001's potentials) or S05's
  independent IAPWS-95 forms, computed by the generator; none is a measurement, and nothing validates a unit against
  plant or literature data.
- The test-only method is not a product method and does not stand in for F4's methods; the `syn001` equivalence leg
  (F6S-b) is not addressed.
- The (P) margin is an estimate (F6S-Q1). The zero-flow regularity of each form is argued (§5.1), not proved for every
  dormancy pattern and specification set; E-F6-9's generator proves it per pattern.
- It does not design column, reactor, exchanger or any unit outside ADR 0065 D16, nor the dynamic variants (TX), nor
  the routing rule (Q4.R9) or controller closure (Q5.R9), which it cites.
