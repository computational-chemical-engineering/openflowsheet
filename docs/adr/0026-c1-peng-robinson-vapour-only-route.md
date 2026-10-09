# ADR 0026 — The C1 property route: Peng–Robinson with the light gases vapour-only, its root and phase rules, the equilibrium-vapour flash, and the formation datum `PR-C1-ref-v1`

**Status:** **Accepted**, 2026-10-08 — on M01 `tested` (`evidence/M01/3c80392…/manifest.json`) and the design-lane review `docs/reviews/M01-review.md` with its Closure (`9098f14`: all findings closed, Amendment 2 ratified). Proposed 2026-10-08; amended before acceptance by Amendment 1 and by M01 spec Amendment 2 (review findings, §20).
Accepted when M01's evidence manifest is `tested` with the work orders of
`docs/derivations/M01-spec.md` §14 WO-1 to WO-4 and a `reviewer` pass on the provider.
**Date:** 2026-10-08
**Author:** design lane (`specifier`), M01.
**Normative text:** `docs/derivations/M01-spec.md` §3 (records), §4 (closed forms), §5 (root and phase rules, the flash),
§6 (the datum), §7 (phase contract), §9.1–§9.5 and §9.8 (assertions M01.A01–A24, A33–A40), §11 (W22). Machine-readable expectations:
`benchmarks/m01/reference_values.yaml` from `docs/derivations/scripts/m01_reference.py` (`--check`).
**Amends:** ADR 0011 D2 (the registered reaction-consistent set gains `PR-C1-ref-v1`; nothing else in D2 changes).
**Affected requirements:** W22 (one validated needed nonideal property route); D08 (real provider conformance);
D04 (data rights of parameter records).
**Affected packages:** M01 (implements it), M02 (its units consume it), M04–M07 (inherit the datum and the limits).
**Companions:** ADR 0001 D2–D5 (state `nTP-v1`, zero flow, reference conventions), ADR 0005 / 0012 (phase contract
v2), ADR 0006 (rights), ADR 0022 revision 1 and R-143 (the method: PR, H₂, N₂, Ar, CH₄ vapour-only — not reopened).

## Context

R-143 fixed the method (Peng–Robinson; H₂, N₂, Ar and CH₄ in the vapour only; the liquid is NH₃ alone) and left to
M01 the root selection, the phase split, the reference state, k_ij and the parameter sources. In T08, IDAES's full PR
VLE ended on the trivial solution and its complementarity flash failed to initialize at the reactor inlet; a
feed-based stability test misclassifies an NH₃ feed carrying a trace of light gas whose own single root is
liquid-like (spec §5.5, state F5). The frozen `PropertyProvider` protocol (interfaces-frozen §1) is not changed.

## Decision

**D1. Equation of state.** Peng–Robinson 1976 for every component and both phases: Ω_a = 0.45724, Ω_b = 0.07780 (as
rounded in PR 1976 and in IDAES 2.13), κ = 0.37464 + 1.54226 ω − 0.26992 ω² for every component (all |ω| < 0.49),
van der Waals one-fluid mixing with a_ij = √(a_i a_j)(1 − k_ij), R = 8.314 462 618 153 24 J mol⁻¹ K⁻¹. With the
rounded Ω's, NH₃'s EOS critical temperature is T_c,EOS = T_c ((1+κ)/(r+κ))², r = √(θ_c Ω_b/Ω_a), θ_c = A_c/B_c of the
exact PR critical point: 405.550 580 K against the record's 405.56 K (spec §4.3).

**D2. Root and phase rules** (spec §5). Pure NH₃ (no light gas flowing): above T_c,EOS one root, labelled vapour; below,
three real roots give liquid = smallest, vapour = largest; a single root is liquid iff v < v_c,EOS = (Z_c/B_c) b. The
stable pure phase is the existing root of lower ln φ (ties: liquid). A phase carrying any light gas is vapour by the
convention and takes the **largest** real root, refused as `vapour_root_metastable` when three roots exist and the
smallest has the lower G^dep. A liquid carrying any light gas is refused (`light_gas_in_liquid`). The **flash** solves
for the equilibrium vapour composition, not for the split: with w the light-gas proportions, y* is the smallest root
on (0, 1) of h(y) = ln y + ln φ_NH₃^V(T, P; y, w) − ln φ_NH₃^L,pure(T, P), bracketed by a fixed sample sequence and
bisected; the feed is two-phase iff n_NH₃ > n_light y*/(1 − y*). No liquid forms at T ≥ T_c,EOS or where pure NH₃'s
stable phase is vapour (P ≤ P_sat,EOS). Every refusal is a typed result with a registered reason code. More than one
admissible root is treated as three (Amendment 1): the cubic at Z = B is −2B², so two distinct admissible roots form a
double root.

**D3. k_ij = 0 for every pair**, with the stated effect: at the C1 separator (F1) k_ij = 0.1 for H₂–NH₃ moves y* by
−3.1 %, for N₂–NH₃ by −2.1 %, every other pair by less than 0.4 % (spec §4.2). No cited k_ij set for the H₂/N₂/Ar/CH₄–NH₃
pairs is used; the effect is part of W22's statement.

**D4. The reference convention `PR-C1-ref-v1`** is a formation datum: the ideal gas of component i at 298.15 K has
h_i = Δ_fH°_i(298.15 K), elements in their reference states zero; h_i^ig(T) = Δ_fH°_i + ∫_{298.15}^{T} c_p,i^ig dT;
phase enthalpies add the PR departure. Σ ν_i h_i is an enthalpy of reaction (−91 116 J per mol N₂ at 298.15 K exactly,
on the records). **ADR 0011 D2's reaction-consistent set becomes `{"SYN-001-ref-v1", "PR-C1-ref-v1"}`**; reactors on
it balance total enthalpy and never add a ξΔh_r term, exactly as D2 requires.

**D5. Parameter sources** (spec §3; Frank's statement 1 of 2026-10-02 applied): T_c, P_c, ω of each component's
reference equation of state (Leachman 2009, Span 2000, Gao 2020, Tegeler 1999, Setzmann & Wagner 1991), retrieved by
`chemicals` 1.5.2 method `HEOS`; ideal-gas c_p from the low-range NASA-7 polynomials of McBride, Gordon & Reno 1993
(NASA TM-4513, a work of the U.S. Government), retrieved from Cantera 3.2.0, stored as dimensionless b_k for
c_p/R = Σ b_k (T/1000 K)^k; Δ_fH° from ATcT 1.112 via `chemicals`. Cross-checked against CoolProp 8.0.0
(`benchmarks/m01/external-crosscheck.json`). The libraries are retrieval and test-time tools, never runtime
dependencies; the values live in `benchmarks/m01/components.yaml` with their citations.

**D6. Provider surface.** Provider id `pr-c1-v1`; `state_definition` `nTP-v1`; components `(H2, N2, NH3, Ar, CH4)`;
phases `(LIQUID, VAPOR)`; properties `h`, `Z`, `v`, `lnphi_<id>`; flashes `("TP",)`; derivatives in `T`, `P`,
`n_<id>` (order 1); domain T ∈ [200, 1000] K, P ∈ [1e4, 3e7] Pa. Refusals carry `status` `unsupported` or
`out_of_domain` and a `message` that begins with the reason code and a colon. A malformed request (a state of the
wrong length) is `error`, `state_length` (Amendment 1). A `flash` request that asks for derivatives is refused
`flash_derivatives_unsupported`, because `FlashResult` cannot carry them (Amendment 1).

## Alternatives considered

- **Exact Ω_a, Ω_b (0.457235529, 0.0777960739).** Rejected: IDAES 2.13, the independent reference (R-143), uses the
  rounded values, and the generator reproduces its separator to 4 × 10⁻¹² only with them; the exact constants would
  move every comparison by ~10⁻⁵ and gain nothing measurable.
- **Rachford–Rice-style bisection on the split from the feed (the previous specifier's tentative choice), or a TPD
  test on the feed's own root.** Rejected: an NH₃ feed with a trace of H₂ (F5) has a single liquid-like root, its TPD
  is ≈ 0⁻, and the method returns one dense "vapour" — the trivial-solution trap of T08 in another form. The y*
  formulation finds the H₂-rich vapour (y* = 0.0555) and is feed-independent (generator claim FL-INDEP).
- **Minimum-Gibbs root for the light-gas phase.** Rejected as the default: it switches roots discontinuously along the
  flash's search and disagrees with IDAES's vapour root at three-root states; the guard keeps the largest root and
  refuses the states where that root is not the stable one.
- **A literature k_ij set** (e.g. a regression on Michels 1950 or Larson & Black 1925). Rejected for v0.2: no set
  covering the C1 pairs was identified in an open, cited source, and fitting one is a validation task with data not
  yet transcribed (spec §15 Q-F2).
- **Poling et al. (5th ed.) c_p polynomials via `chemicals`.** Rejected: their redistribution in the project's own
  records is a rights question for Frank; NASA TM-4513 needs no grant and is within 0.51 % of CoolProp's ideal-gas
  c_p on 250–1000 K for NH₃ (1.1 % for CH₄ at 1000 K).
- **NASA's own Δ_fH (in the polynomials' integration constants) instead of ATcT.** Rejected: ATcT is the more accurate
  value (NH₃: −45.558 ± 0.030 kJ/mol against JANAF's −45.898); recorded as a cross-check.

## Consequences

- C1. No frozen interface, schema, quantity kind or check category changes. `docs/interfaces-frozen.md` §3 gains a note
  that ADR 0001 D5's convention list includes `PR-C1-ref-v1` and that ADR 0011 D2's set has two members (written by
  Amendment 1).
- C2. SYN-001's provider, its oracle and every registered identity (SYN-001 structural hash, the K05 identity
  document, T06's corpus values) are untouched: the provider is additive (assertion M01.A33).
- C3. The units that consume the provider (PR flash, heater/cooler, mixer, splitter on `pr-c1-v1`) are M02's; their
  phase-contract rules are specified in M01 spec §7.
- C5. T08.A32's synthetic-only rule is amended for real records (spec §3.5, R-158); its test is changed by WO-1.
- C4. Limitations stated, not fixed: no dissolved light gases (R-143); k_ij = 0; PR's saturated-liquid volume of NH₃
  is 11–30 % high (the Poynting term carries it into ln f^L: +0.025 at the separator); no mixture VLE validation.

## Migration

None: no existing record, identity or registered value moves.

## Acceptance evidence

- `docs/derivations/scripts/m01_reference.py --check` (88 claims since Amendment 1) and
  `benchmarks/m01/external_crosscheck.py --check`.
- M01.A01, A03–A24, A33–A36 and A50 pass in the gate; the IDAES conformance record (M01.A37) and the W22 comparison (M01.A38–A40) committed.
- `reviewer` pass on the provider against spec §4–§7.

## Amendment 1 (2026-10-08): the build lane's measurements, ruled

**Status:** Proposed with this ADR; design lane (`specifier`), M01 spec Amendment 1 (§19); register R-196, R-197.
No closed form, registered state, expectation value or refusal code of the draft changes.

- A1.1 (D2). More than one admissible root is treated as three: smallest = liquid, largest = vapour, and the guard
  compares the two. The cubic at Z = B is −2B² (generator claim PR-07), so two distinct admissible roots are a double
  root. The case is not registered and not asserted (spec §5.2).
- A1.2 (D6). The provider's request checks are ratified as built:
  - a negative or non-finite flow, or a non-finite T or P → `out_of_domain`;
  - an unknown property → `unsupported`, `unknown_property`;
  - a state of the wrong length → `error`, `state_length`;
  - a non-TP flash → `unsupported`, `unsupported_specification`.

  One behaviour is replaced: a `flash` that asks for derivatives is refused (`flash_derivatives_unsupported`), not
  ignored. SYN-001's provider is not changed (spec §5.3, §5.4 step 0; M01.A50).
- A1.3 (verification). M01.A09, A12 and A26 are restated on measured floors (spec §19). A12's ln φ identities are
  bounded by 10⁻¹² times the block's largest scaled entry. The generator gains PR-07, PH-GAP, BD-04, BD-05, BD-06
  and DX-01 (88 claims).
- A1.4 (C1). The note for `docs/interfaces-frozen.md` §3 is written.

## Amendment 2 (2026-10-09): M01 spec §7 rule 2's equilibrium row (M02 WO-8 rulings)

**Status:** Recorded by the design lane (`architect`), M02 (`docs/design/M02-pymrm-adapter.md` §14.2 B11–B12; R-254),
for ratification by the `specifier` (optional; the work proceeds on it).

- A2.1 (C3). The normative §7 is amended by M01 spec Amendment 3. The NH₃ equilibrium row of a PR split is written
  in R-008's pairwise form, `E = L · n_V,NH₃ · φ^V_NH₃ − V · n_L,NH₃ · φ^L_NH₃` (kind molar_flow_squared). M01's
  `n_V,NH₃ φ^V − n_V,tot φ^L` is not zero on the VAPOR branch, and above T_c,EOS it cannot be evaluated at all, yet
  the region drops equilibrium rows on single-phase branches and K04 evaluates every declared row. The light-gas
  liquid flows become zero rows in the equilibrium family, pinned at `+0.0` in TWO_PHASE.
- A2.2. On TWO_PHASE the new row is `L V (y φ^V − φ^L)`, so its root set is unchanged. No closed form, provider
  behaviour, registered state, expectation value, refusal code or M01 assertion moves.
