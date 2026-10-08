# M01 specification — the C1 property route and the PyMRM reactor boundary

**Status:** design lane (`specifier`), 2026-10-08. **Draft for review**, **amended twice** (Amendment 1, 2026-10-08,
§19: rulings on the build lane's measurements at `13bcef7`; Amendment 2, 2026-10-08, §20: the closure of the design-lane
review's findings, `docs/reviews/M01-review.md`); the build lane implements against it, a
`reviewer` reviews the implementation, a `verdict` judges W22 and M01's part of W21 from the evidence.
**Package:** M01 (plan v1.2 §4.4: *pin the selected PyMRM reactor and one required nonideal property route; derive
process boundary mappings. Acceptance: model/source/data rights, numerical refinement evidence,
ports/DOF/reference-state compatibility, known invalid requests*). Gates fed: **W22**, **W21** (M01's part).
**Brief:** `docs/briefs/M01-specification.md` (authoritative for scope). Supersedes `docs/derivations/M01-spec-WIP.md`
(the previous specifier's halt note; its measured leads are re-measured here, §18).
**Decisions:** ADR 0026 (the property route), ADR 0027 (the reactor boundary); register R-154 to R-169; Amendment 1:
R-195 to R-200.
**Machine-readable values:**

| File | Produced by | Class |
| --- | --- | --- |
| `benchmarks/m01/components.yaml` | authored from retrieved values (§3) | the records |
| `benchmarks/m01/reference_values.yaml` | `docs/derivations/scripts/m01_reference.py --emit` (`--check`) | closed forms (expectations), generator claims, 53-bit floors |
| `benchmarks/m01/reactor-overlay.json` | the same generator | reactor configuration rows (§8.6) |
| `benchmarks/m01/external-crosscheck.json` | `benchmarks/m01/external_crosscheck.py --emit` (`--check`), separate venv | measured: retrieval equality, CoolProp cross-checks, W22 comparisons |
| `benchmarks/m01/reactor-probe.json` | `benchmarks/m01/reactor_probe.py`, separate venv, pinned reactor | measured: the group's model (regression for M02, never an expectation for this repository's code) |

## 1. Authority and scope

This document is the authority for: the five C1 component records and their sources; the Peng–Robinson closed forms,
root selection and phase logic of provider `pr-c1-v1`; the reference convention `PR-C1-ref-v1`; the boundary
between OpenFlowsheet's `nTP-v1` streams and the group's reactor `ammonia_synthesis_reactor` @ `6089593`; the
numbered assertions `M01.Axx` the implementation and the evidence manifest are judged by; and the build lane's work
orders. It is bound by ADR 0001 (state, zero flow, signs, reference conventions), ADR 0005/0012 (phase contract v2),
ADR 0008 (no time at the evaluation boundary), ADR 0011 (formation datum; reactors balance total enthalpy), ADR 0013
(the verifier's fresh flash), ADR 0019/0020 (application contract, frozen), ADR 0022 and R-143 (C1, PR with the light
gases vapour-only, the pin), R-152 (K_NH₃ = the code's 7000 cal/mol), R-153 (order). It changes no frozen interface
or schema (§2.2 of the plan): every addition is a new provider, new records, new modules. With no schema change, the
deferred schema `$id` move (R-149) does not ride on M01.

Out of scope (brief §10): M02's execution adapter mechanics beyond the contract of §8, M03–M05, the web shell, full PR
VLE with dissolved gases, columns, DWSIM, re-selecting the chemistry, production code.

## 2. What M01 establishes (summary)

| # | Item | Where | Decision |
| --- | --- | --- | --- |
| 1 | Records: T_c, P_c, ω (reference EOS via `chemicals` HEOS), c_p (NASA TM-4513 via Cantera), Δ_fH (ATcT 1.112), all cited, no rights grant needed | §3 | ADR 0026 D5, R-158 |
| 2 | PR with Ω_a = 0.45724, Ω_b = 0.07780, κ(1976), k_ij = 0 (effect stated) | §4 | ADR 0026 D1, D3; R-154, R-157 |
| 3 | Root rules: pure NH₃ by T_c,EOS and v_c,EOS; light-gas phase = largest root with a metastability guard | §5.2–5.3 | ADR 0026 D2, D6; R-154, R-159 |
| 4 | The flash solves for the equilibrium vapour composition y*(T, P, w); feed-independent; avoids the trivial solution | §5.4 | ADR 0026 D2; R-155 |
| 5 | `PR-C1-ref-v1`: ideal gas at 298.15 K = Δ_fH°; added to ADR 0011 D2's reaction-consistent set | §6 | ADR 0026 D4; R-156 |
| 6 | Phase-contract v2 rules for the PR units (built in M02) | §7 | ADR 0026 C3 |
| 7 | Reactor boundary: ports/DOF, per-tube scaling, zero-ΔP convention (ε_P = 10⁻³), least-squares extent projection, process-side duty, refusal codes | §8 | ADR 0027 D1–D4; R-161–R-163, R-167 |
| 8 | Five-species reactor configuration: overlay rows, a subclass for one three-species constant | §8.5–8.6 | ADR 0027 D5; R-164 |
| 9 | Start strategy (trace-NH₃ continuation) and M01's solver profile (the group's tolerance leaves 0.5 % iteration error) | §8.7 | ADR 0027 D6; R-165 |
| 10 | Refinement evidence and the grids | §10 | ADR 0027 D7; R-166 |
| 11 | W22: what "validated" means and the evidence | §11 | R-160 |
| 12 | The M01/M02 split and a synthetic stand-in reactor for the in-repo gate | §8.13–8.14 | ADR 0027 D8; R-168 |
| 13 | Out-of-data-domain inlets are flagged, not refused | §8.12 | ADR 0027 D9; R-169 |
| 14 | Amendment 1: A09, A12 and A26 re-stated on measured floors; request checks and boundary paths ratified (flash derivatives refused); the boundary's check order normative; where "synthetic" is written | §19 | ADR 0026, 0027 Amendment 1; R-195–R-200 |
| 15 | Amendment 2: the review's findings F1–F5 closed (root convergence, the boundary's state-space check, Q-N4's reversal path, the flash's measured miss region, the harvest class) | §20 | R-197 (correction note); `docs/reviews/M01-review.md` |

## 3. Component records (`benchmarks/m01/components.yaml`)

### 3.1 Values and primary sources

Order (the identity order of every n-vector): **H2, N2, NH3, Ar, CH4**. Every record validates against
`schemas/component-record.schema.json` and `openflowsheet.units.check_quantity` (checked when written).

| id | M (kg/mol) | T_c (K) | P_c (Pa) | ω | Δ_fH°(298.15 K) (J/mol) | EOS source of T_c, P_c, ω |
| --- | --- | --- | --- | --- | --- | --- |
| H2 | 0.00201588 | 33.145 | 1 296 400 | −0.219 | 0 | Leachman et al., JPCRD 38 (2009) 721 (normal H₂) |
| N2 | 0.0280134 | 126.192 | 3 395 800 | 0.0372 | 0 | Span et al., JPCRD 29 (2000) 1361 |
| NH3 | 0.01703052 | 405.56 | 11 363 400 | 0.256 | −45 558 (±30) | Gao, Wu, Bell, Lemmon, JPCRD (2020) (CoolProp key Gao-JPCRD-2020) |
| Ar | 0.039948 | 150.687 | 4 863 000 | −0.00219 | 0 | Tegeler et al., JPCRD 28 (1999) 779 |
| CH4 | 0.01604246 | 190.564 | 4 599 200 | 0.01142 | −74 534 (±57) | Setzmann & Wagner, JPCRD 20 (1991) 1061 |

- T_c, P_c, ω: the reference equation of state's values as tabulated by `chemicals` 1.5.2 method `HEOS` (Frank's
  "first retrieval source"), the primary reference being the EOS paper.
- Δ_fH°: Active Thermochemical Tables 1.112 (Ruscic & Bross, ATcT.anl.gov) via `chemicals` method `ATCT_G`; elements
  in their reference states are zero by definition.
- c_p^ig: McBride, Gordon & Reno, NASA TM-4513 (1993), low-range NASA-7 coefficients (200–1000 K), species notes
  TPIS78 (H₂, N₂), TPIS89 (NH₃), L 6/88 (Ar), L 8/88 (CH₄), retrieved from Cantera 3.2.0 `data/nasa_gas.yaml`.
  Stored as dimensionless `ideal_gas_cp_b0..b4` with **c_p^ig/R = Σ_{k=0}^{4} b_k (T / 1000 K)^k**,
  b_k = a_{k+1}·1000^k exactly in decimal (the registered kinds have no K⁻ᵏ; the scaling is exact).
- M from IUPAC/CIAAW standard atomic weights (`chemicals.elements.molecular_weight`); identifiers (CAS, InChI,
  InChIKey, formula) from `chemicals`.
- **No value comes from the group's reactor property database** (Frank, 2026-10-02).

### 3.2 Constants used with the records

R = 8.314 462 618 153 24 J mol⁻¹ K⁻¹ (exact SI) everywhere, including the NASA polynomials (NASA's fits used 8.31451;
the difference is 6 × 10⁻⁶ relative and is not corrected). T_ref = 298.15 K.

### 3.3 Cross-check (measured, `external-crosscheck.json`)

- Retrieval: every recorded T_c, P_c, ω, Δ_fH equals `chemicals`' value exactly; every b_k equals Cantera's a_{k+1}·1000^k
  to 10⁻¹⁵; identifiers and M equal (`retrieval_all_equal: true`).
- CoolProp 8.0.0: T_c, P_c within 3.3 × 10⁻⁵ (H₂) and 8 × 10⁻⁷ (others); ω minus its definition from CoolProp's
  P_sat(0.7 T_c): ≤ 3.5 × 10⁻⁴ (the records' ω are rounded).
- c_p^ig against CoolProp's reference-EOS ideal part, 250–1000 K: H₂ ≤ 0.39 %, N₂ ≤ 0.11 %, NH₃ ≤ 0.51 %, Ar 6 × 10⁻⁶,
  CH₄ ≤ 1.12 % (at 1000 K; 0.77 % at 700 K). Against JANAF (via `thermo`): NH₃ ≤ 0.81 %, CH₄ ≤ 2.5 % at 1000 K.
- Δ_fH: ATcT minus JANAF = +340 J/mol (NH₃), +339 J/mol (CH₄): ATcT is the newer network; recorded, not corrected.

### 3.4 Rights (ADR 0006)

Published numerical constants quoted with their citations, a handful per component (not an extraction of any
database); NASA TM-4513 is a work of the U.S. Government; `chemicals` (MIT) and Cantera (BSD-3-Clause) are retrieval
tools, CoolProp (MIT) a cross-check tool; none is a runtime dependency of the solver. **No rights grant is relied
on.** The Poling (5th ed.) c_p polynomials were not used because they would need one (§15 Q-N1).

### 3.5 T08.A32 amended for real records (finding of this specification's own gate run)

T08.A32 (release spec, v0.1) requires every ComponentRecord in the repository to be `synthetic: true`; its test
(`tests/test_t08_w2_inventory.py::test_a32_every_component_record_is_synthetic_with_rights`) fails as soon as
`components.yaml` is committed (measured on `wp/M01`: 1 failed, 6877 passed). The premise "no real component data"
ends with M01 by design; the assertion is **amended, not relaxed**: a record with `synthetic: true` keeps T08.A32's
rule unchanged; a record with `synthetic: false` must (i) be one of the five records of `benchmarks/m01/components.yaml`
(no other real record may appear unvetted), (ii) carry `identifiers` with `cas`, `inchi`, `inchikey`, (iii) carry
non-empty `rights.source`, `rights.redistribution` and a `provenance` on every parameter and on the molecular weight,
and (iv) be covered by M01.A02 (retrieval equality). WO-1 makes this change to the test first, citing this section and
R-158. Shipping the records in the v0.2 wheel (as package data, like SYN-001's) ends T08.A32's "no third-party data in
sdist or wheel" for v0.2; that is a release-policy question for Frank (Q-N4).

## 4. Peng–Robinson closed forms (provider `pr-c1-v1`)

### 4.1 Pure-component parameters

a_c,i = Ω_a R² T_c,i² / P_c,i, b_i = Ω_b R T_c,i / P_c,i, Ω_a = 0.45724, Ω_b = 0.07780 (decimal-exact),
√α_i(T) = 1 + κ_i (1 − √(T/T_c,i)), κ_i = 0.37464 + 1.54226 ω_i − 0.26992 ω_i²,
a_i(T) = a_c,i α_i, da_i/dT = −a_c,i κ_i √α_i / √(T T_c,i).
√α_i > 0 on the whole domain (generator claims PR-03-*; at 1000 K the smallest is N₂'s 0.2166).

### 4.2 Mixing and k_ij

a_m = Σ_i Σ_j y_i y_j a_ij, a_ij = √(a_i a_j)(1 − k_ij), S_i = Σ_j y_j a_ij, b_m = Σ y_i b_i,
da_m/dT = Σ_i Σ_j y_i y_j (1 − k_ij)(a_i' a_j + a_i a_j')/(2√(a_i a_j)).
**k_ij = 0 for every pair** (ADR 0026 D3). Stated effect (generator, F1 at 268.15 K, 10⁷ Pa; y* = 0.061547):

| Pair | k = −0.1 | k = +0.1 | k = +0.2 |
| --- | --- | --- | --- |
| H2–NH3 | +3.2 % | −3.1 % | −6.2 % |
| N2–NH3 | +2.1 % | −2.1 % | −4.1 % |
| NH3–CH4 | +0.31 % | −0.31 % | −0.63 % |
| NH3–Ar | +0.17 % | −0.17 % | −0.34 % |
| H2–N2 | −0.19 % | +0.19 % | +0.38 % |

### 4.3 The cubic, the PR critical constants, NH₃'s EOS critical point

A = a_m P/(RT)², B = b_m P/(RT); Z³ − (1 − B)Z² + (A − 3B² − 2B)Z − (AB − B² − B³) = 0; admissible roots Z > B.
Discriminant Δ = 18bcd − 4b³d + b²c² − 4c³ − 27d² of z³ + bz² + cz + d: three distinct real roots iff Δ > 0.

The exact PR critical constants (triple root): Z_c = (1 − B_c)/3, A_c = 3Z_c² + 3B_c² + 2B_c, Z_c³ = A_c B_c − B_c² − B_c³:
B_c = 0.077796073903888455972, Z_c = 0.30740130869870384801, A_c = 0.45723552892138218938, θ_c = A_c/B_c =
5.8773599486044029529, v_c/b = Z_c/B_c = 3.951373035591441433.

With the rounded Ω's, θ(T) = a(T)/(bRT) = (Ω_a/Ω_b)(T_c/T)α(T); θ = θ_c at √(T/T_c) = (1+κ)/(r+κ), r = √(θ_c Ω_b/Ω_a):
**T_c,EOS = T_c ((1+κ)/(r+κ))²**, P_c,EOS = B_c R T_c,EOS / b, **v_c,EOS = (Z_c/B_c) b**. For NH₃ (κ = 0.75176908288):
T_c,EOS = 405.5505804875952 K, P_c,EOS = 11 362 562.645500638 Pa, v_c,EOS = 9.122389971359765 × 10⁻⁵ m³/mol
(generator claims PR-04, PR-05: A = A_c and B = B_c there to 10⁻⁴⁰; T_c − T_c,EOS = 0.0094 K).

### 4.4 Fugacity coefficients

ln φ_i = (b_i/b_m)(Z − 1) − ln(Z − B) − [A/(2√2 B)] (2S_i/a_m − b_i/b_m) ln[(Z + (1+√2)B)/(Z + (1−√2)B)].
ln φ_i is defined for every component, present or not (an absent component's value is its infinite-dilution
coefficient; V5 registers ln φ_NH₃ at y_NH₃ = 0).

### 4.5 Enthalpy (reference convention `PR-C1-ref-v1`, §6)

h_i^ig(T) = Δ_fH°_i + 1000 R Σ_k b_k [τ^{k+1} − τ_0^{k+1}]/(k+1), τ = T/1000 K, τ_0 = 0.29815 (exact closed form;
h_i^ig(298.15 K) = Δ_fH°_i).
h^dep = RT(Z − 1) + [(T da_m/dT − a_m)/(2√2 b_m)] ln[(Z + (1+√2)B)/(Z + (1−√2)B)].
h(phase) = Σ y_i h_i^ig(T) + h^dep. v = ZRT/P. Enthalpy flow Ḣ = n_tot h; on a dormant stream Ḣ = 0 exactly.

### 4.6 Derivatives the provider declares

Inputs `T`, `P` and `n_<id>` for the five ids (order 1). Properties `h`, `Z`, `v`, `lnphi_<id>` are intensive, so
for the VAPOR phase Σ_j n_j ∂X/∂n_j = 0 (homogeneity), Σ_i n_i ∂ln φ_i/∂n_j = 0 (Gibbs–Duhem at fixed T, P), and
∂ln φ_i/∂n_j = ∂ln φ_j/∂n_i (symmetry); for the LIQUID phase (pure NH₃) every n-derivative is exactly 0. The method
(analytic, implicit differentiation of the root, or automatic) is the implementer's; the expectations are the
generator's 50-digit numerical derivatives of the closed forms (independent of any analytic formula), which satisfy
the three identities to 10⁻²⁵ (claims DER-HOM, DER-GD, DER-SYM) and have no vanishing entry (DER-NZ: every registered
vapour derivative exceeds 10⁻¹² in magnitude).

### 4.7 Sanity values (full set in `reference_values.yaml` → `closed_form`)

| State | T (K), P (Pa) | n (mol/s) | Phase | Z | h (J/mol) | ln φ_NH₃ |
| --- | --- | --- | --- | --- | --- | --- |
| V1 | 673.15, 10⁷ | (0.70, 0.235, 0.03, 0.015, 0.02) | VAPOR | 1.0253224507926901 | 8411.091539543166 | −0.004238504410618317 |
| V2 | 268.15, 10⁷ | IDAES separator vapour | VAPOR | 0.9943972083293808 | −5698.1067545966225 | −0.47078703743519856 |
| L1 | 268.15, 10⁷ | pure NH₃ | LIQUID | 0.13072045559137904 | −69084.57681680721 | −3.2588216442882425 |
| L2 | 350, 10⁶ | pure NH₃ | LIQUID (3 roots) | 0.013383920356505217 | −61673.45080642687 | 1.099408690192041 |
| V3 | 350, 10⁶ | pure NH₃ | VAPOR (3 roots) | 0.9461336373913496 | −44135.21458823313 | −0.052913604431839546 |
| V4 | 420, 5×10⁶ | pure NH₃ | VAPOR (supercritical) | 0.8389115472866022 | −42866.71571005264 | −0.15490680243620764 |
| V5 | 268.15, 10⁷ | (0.75, 0.25, 0, 0, 0) | VAPOR | 1.02335231137587 | −1020.8050783977252 | −0.37109065230202437 |

V1's five ln φ: H₂ 0.022860273754912258, N₂ 0.03468667929053277, NH₃ −0.004238504410618317, Ar 0.021484160476678813,
CH₄ 0.023295016069697597. Ideal-gas reaction enthalpy (per mol N₂): −91 116 J/mol at 298.15 K (exactly 2Δ_fH°_NH₃),
−104 003.12297042357 J/mol at 673.15 K.

**Independent transcription check (generator claim IDAES-01).** With T08's parameter set (read from
`benchmarks/t08/v19/c1-idaes.json`, for this check only) the generator reproduces IDAES 2.13's vapour-only separator:
β to 4.1 × 10⁻¹², y_NH₃ to 4.4 × 10⁻¹², the five vapour φ to 4.4 × 10⁻¹⁵ and the liquid φ to 3.6 × 10⁻¹⁴ relative.

## 5. Root selection and phase logic

### 5.1 The convention (R-143, not reopened)

H₂, N₂, Ar, CH₄ exist only in the vapour; the liquid is pure NH₃. A phase carrying any light gas is the vapour;
the only liquid is pure NH₃. Light gases never dissolve (the v0.2 limitation).

### 5.2 Roots

**Pure NH₃ at (T, P)** (the composition of a LIQUID request, or a VAPOR request with no light gas flowing):
1. T ≥ T_c,EOS: one real root (the cubic is monotone for θ ≤ θ_c); it is the vapour. No liquid root.
2. T < T_c,EOS, three real roots (Δ > 0): liquid = smallest, vapour = largest (the middle root is never used).
3. T < T_c,EOS, one real root: **liquid iff v = ZRT/P < v_c,EOS**, else vapour. Exact wherever NH₃'s two spinodal
   volumes straddle v_c,EOS, which the generator checks at 200, 240, 268.15, 300, 350, 400 and 405 K (claims PR-06; at 268.15 K they are
   3.7657 × 10⁻⁵ and 4.0729 × 10⁻⁴ m³/mol around v_c,EOS = 9.1224 × 10⁻⁵): a single root lies outside the spinodal
   interval, on the liquid branch iff it is left of it.
4. The stable pure phase: the existing root of lower ln φ_NH₃; ties go to the liquid; with one root, that root's phase.

**A phase carrying any light gas** (n_light = n_H₂ + n_N₂ + n_Ar + n_CH₄ > 0): the **largest** real root Z > B
(IDAES's vapour root). Guard: if Δ > 0 and the smallest root has strictly lower G^dep/RT = Σ y_i ln φ_i, the
evaluation is refused `vapour_root_metastable` (U4). The guard applies to `evaluate_phase` and to the flash's
converged vapour (§5.4 step 7); not to the flash's internal samples.

Determining Δ's sign: the implementation may use the discriminant or the count of polished real roots; at the
registered states the margin is wide (no registered state has a near-double root). A near-degenerate state is not
registered and its classification is not asserted (§17).

**Converged roots only (Amendment 2, review F2).** A polished candidate is a root only if the cubic there is zero to
within its own evaluation error, |f(Z)| ≤ 16 u Σ|terms| (u = 2⁻⁵³; Horner's error is at most ≈ 6u Σ|terms|). Near a
double root (within ≈ 10⁻¹⁴ of P, relative, of a spinodal) the trigonometric form puts two candidates at the cubic's
extremum, where Newton jumps away and is still moving after its 8 steps; the review measured such iterates returned
as roots with residuals up to 10⁻², and `evaluate_phase(LIQUID)` answering `ok` at pure NH₃, 400 K,
10 025 791.149338482 Pa, where the cubic has one real root (0.486253) and a complex pair (0.222075 ± 2.8 × 10⁻⁸ i).
Where the three-root branch keeps fewer than three distinct roots, the converged candidate of largest |f′| (the
isolated, well-conditioned root) is divided out, and the quadratic left, Z² + (c₂ + r)Z − c₀/r, is solved by the
cancellation-free formula: a negative discriminant means a complex pair, so one root. Cardano's single root is simple
and is kept as polished. Measured (the review's P2 scan re-run, 20 000 random states): no returned value changes bit
for bit; worst root error 8.6 × 10⁻¹⁶. Measured (±60 ulp of P around every spinodal crossing at 220–400 K, three
compositions, 3 267 states): worst distance of a returned root from a true one 2.0 × 10⁻⁸ (the near-double root's own
conditioning, √u), against 0.28 before; every returned value is a root to rounding.

**Two admissible roots (Amendment 1).** The cubic at Z = B equals −2B² < 0 (claim PR-07) and tends to +∞, so its roots
above B, counted with multiplicity, are odd in number: one or three. Two *distinct* admissible roots therefore occur
only at a double root (Δ = 0), or where roundoff splits a near-double root. *(Amendment 2, review F2: the two-root
returns actually measured before were not a split double root but unconverged Newton iterates, the real part of a
complex pair among them. Since Amendment 2 two distinct roots come only from the deflated quadratic with a
non-negative discriminant: roots of the cubic to rounding, a near-double pair.)* Whenever more than one admissible root is
found, the rules above apply as for three: smallest = liquid (pure NH₃), largest = vapour, and the guard compares the
smallest with the largest. This is the continuous extension of the three-root rule; no registered state reaches it
and it is not asserted.

### 5.3 `evaluate_phase` rules and refusals

| Request | Result |
| --- | --- |
| T or P outside [200, 1000] K × [10⁴, 3×10⁷] Pa | `out_of_domain`, message `out_of_domain: ...` |
| `LIQUID` with any light gas > 0 | `unsupported`, `light_gas_in_liquid: ...` |
| `LIQUID`, pure NH₃, no liquid root (T ≥ T_c,EOS, or one vapour-like root) | `unsupported`, `no_liquid_root: ...` |
| `VAPOR`, pure NH₃, no vapour-like root | `unsupported`, `no_vapour_root: ...` |
| `VAPOR` with light gas, guard fails | `unsupported`, `vapour_root_metastable: ...` |
| `LIQUID` asking for `lnphi_<light gas>` | `unsupported`, `light_gas_in_liquid: ...` |
| a derivative input not declared | `unsupported`, `undeclared_derivative_input: <id>` |
| a property not in `describe().properties` (Amendment 1) | `unsupported`, `unknown_property: ...` |
| a state whose `n` has other than five entries (Amendment 1) | `error`, `state_length: ...` (a malformed request, not a capability or domain limit) |
| T or P not finite, or a component flow negative or not finite (−0.0 is zero; Amendment 1) | `out_of_domain`, `out_of_domain: ...` (outside the declared box or nTP-v1's state space, ADR 0001 D2) |
| a dormant state (n_tot = 0) | `unsupported`, `dormant_state: composition undefined` (ADR 0001 D3.1) |
| otherwise | `ok`, values and requested derivatives |

Check order (ratified by Amendment 1 as built): undeclared derivative input, unknown property, state length, domain
(T, P, flows), dormant state, then the phase rules of the table's upper rows. Every registered refusal state has one
defect, so the order is not asserted.

A metastable pure-NH₃ liquid (L2: three roots, the vapour stable) is evaluable: `evaluate_phase` answers "what is the
liquid's h at this state", deciding which phase exists is `flash`'s job (the protocol's own split).

### 5.4 The TP flash

Given n (mol/s), T, P:

0. Request checks (Amendment 1), in this order: a `specification` other than `TP` → `unsupported`,
   `unsupported_specification: ...`; a non-empty `derivatives` → `unsupported`, `flash_derivatives_unsupported: ...`
   (`FlashResult` has no field to carry derivatives and `describe()` declares derivative orders for `evaluate_phase`
   only, so an ignored request would read as an answer; a unit takes the derivatives of its equilibrium row from
   `evaluate_phase`, §7); a state of other than five flows → `error`, `state_length: ...`. No refusal carries a split.
1. Out of domain (as §5.3, including negative or non-finite flows) → `out_of_domain`. n_tot = 0 → `ok`, `ZERO_FLOW`,
   `vapor_fraction` None, both outlets dormant (all flows +0.0, labels T and P), `k_values` empty (ADR 0001 D3.4).
2. n_light = 0 (pure NH₃): phase = VAPOR if T ≥ T_c,EOS else the stable pure phase (§5.2 item 4); `vapor_fraction`
   1.0 or 0.0; the present phase carries the feed bitwise, the absent phase is dormant; `k_values` empty.
3. n_NH₃ = 0: VAPOR (no liquid can exist).
4. T ≥ T_c,EOS, or pure NH₃'s stable phase at (T, P) is the vapour (P ≤ P_sat,EOS(T)): VAPOR. *Argument:* for a
   (diffusionally) stable vapour f_NH₃ rises with y_NH₃ up to f_NH₃^V,pure < f_NH₃^L,pure, so no composition
   condenses NH₃ (F3).
5. Otherwise let w_k = n_k/n_light (the light-gas proportions, k over H₂, N₂, Ar, CH₄), ln φ^L = ln φ_NH₃ of the pure
   liquid root at (T, P), and **h(y) = ln y + ln φ_NH₃^V(T, P; y_NH₃ = y, y_k = (1 − y) w_k) − ln φ^L** on (0, 1), with
   the vapour's largest root (no guard). h(0⁺) = −∞.
6. **Bracket:** evaluate h at the fixed sample sequence s = (1/64, 2/64, …, 63/64, 1 − 2⁻⁷, 1 − 2⁻⁸, …, 1 − 2⁻⁴⁰)
   in that order; the first sample with h(s) ≥ 0 is `hi`, the previous sample (or 0) is `lo`. No sample with h ≥ 0 →
   VAPOR (route `no_liquid`). **Bisect** on [lo, hi]: mid = (lo + hi)/2, h(mid) ≥ 0 → hi = mid, else lo = mid, until
   hi − lo ≤ 2 ulp(hi) or 200 halvings; y* = (lo + hi)/2.
7. Guard at y* (§5.2); then v_NH₃ = n_light y*/(1 − y*). If n_NH₃ ≤ v_NH₃: VAPOR (route `undersaturated`).
   Else TWO_PHASE: vapour = (n_H₂, n_N₂, v_NH₃, n_Ar, n_CH₄), liquid = (0, 0, n_NH₃ − v_NH₃, 0, 0) with exact +0.0
   light-gas entries; `vapor_fraction` = (n_light + v_NH₃)/n_tot; `k_values` = {"NH3": y*} (x_NH₃ = 1; a light gas has
   no K and is absent from the mapping — absent means "not computed", not zero); `iterations` = samples + halvings.

y* depends on (T, P, w) only, never on n_NH₃ (claim FL-INDEP): the equilibrium vapour of a pure-liquid system is
fixed by the light gases' proportions. The flash is therefore exact to the root of one scalar equation, needs no
initial guess, and cannot converge to the trivial solution (all K = 1), which in this formulation does not exist.

### 5.5 Why the feed's own root is not consulted (the trivial-solution trap, F5)

F5: n = (10⁻⁶, 0, 0.999999, 0, 0) at 268.15 K, 10⁷ Pa. The feed's mixture cubic has one liquid-like root; a TPD test
on that root gives ln(z φ_NH₃(z)) − ln φ^L ≈ ln(0.999999) < 0, declaring one dense phase. The convention's answer is
an H₂-rich vapour with y* = 0.05547685337297486 and β = 1.0587353031750334 × 10⁻⁶ (F5, TWO_PHASE); the remaining
0.9999989412646968 mol/s is liquid.

### 5.6 Registered flash states (why each is in the list)

| id | T (K), P (Pa) | feed n | Result (route) | Why |
| --- | --- | --- | --- | --- |
| F1 | 268.15, 10⁷ | (0.60, 0.20, 0.165, 0.015, 0.02) | TWO_PHASE, y* = 0.06154699974328799, β = 0.8897621934945995 | the C1 separator (IDAES composition) |
| F2 | 300, 10⁷ | (0.70, 0.235, 0.03, 0.015, 0.02) | VAPOR (`undersaturated`), y* = 0.1681719369482627 | subcritical, P > P_sat, too little NH₃ |
| F3 | 268.15, 2×10⁵ | (0.25, 0.25, 0.5, 0, 0) | VAPOR (`no_liquid`) | below P_sat,EOS(268.15 K) = 352 112.754 Pa |
| F4 | 268.15, 10⁷ | F1's light gases, NH₃ = 0.05476219349459947 | VAPOR or TWO_PHASE with l ≤ 10⁻¹² n_NH₃ | the dew point: classification at the ulp level is not asserted |
| F5 | 268.15, 10⁷ | (10⁻⁶, 0, 0.999999, 0, 0) | TWO_PHASE, y* = 0.05547685337297486 | the trivial-solution trap (§5.5) |
| F6 | 268.15, 10⁷ | (0.75, 0.25, 0, 0, 0) | VAPOR (`no_nh3`) | no NH₃ |
| F7 | 268.15, 10⁷ | pure NH₃ | LIQUID | pure compressed liquid |
| F8 | 350, 10⁶ | pure NH₃ | VAPOR | three roots, the vapour stable |
| F9 | 420, 5×10⁶ | pure NH₃ | VAPOR | above T_c,EOS |
| F10 | 673.15, 10⁷ | reactor inlet | VAPOR (`supercritical`) | decided without the search |
| F11 | 250, 2.5×10⁷ | F1's feed | TWO_PHASE, y* = 0.025522059342750248, β = 0.8568690630768132 | a second separator state: other sample bracket (index 1) |
| F12 | 400, 2×10⁷ | (0.5, 0.17, 0.3, 0.01, 0.02) | VAPOR (`no_liquid`) | 5.6 K below T_c,EOS: the near-critical adversarial case, registered for what the rules give |
| F13 | 268.15, 5×10⁵ | (0.02, 0, 0.98, 0, 0) | TWO_PHASE, y* = 0.7150720927197992 | U4's feed: the vapour at y* has three roots and passes the guard; bracket index 45 |
| F14 | 300, 10⁷ | all zero | ZERO_FLOW | dormant feed |

F1 against T08's IDAES (different parameter set, so not a conformance test): β 0.88976 vs 0.88970, y* 0.061547 vs
0.061485 — the records' parameters move the separator by 0.1 %.

## 6. The reference convention `PR-C1-ref-v1` and ADR 0011

`PR-C1-ref-v1`: each component's ideal gas at T_ref = 298.15 K has h = Δ_fH°(298.15 K) of §3; the elements in their
reference states (H₂, N₂, Ar as gases) have zero; pressure enters only through the departure. It is a **formation
datum** in ADR 0011 D2's sense: Σ_i ν_i h_i is an enthalpy of reaction at every (T, P) and phase assignment, and the
C1 reactor's energy balance is written in total-enthalpy form Q + Ḣ_in − Ḣ_out = 0 with no ξΔh_r term (§8.10).
**ADR 0011 D2's registered reaction-consistent set becomes {`SYN-001-ref-v1`, `PR-C1-ref-v1`}** (ADR 0026 D4). The
constant `REACTION_CONSISTENT_CONVENTIONS` in `models/syn001/conversion_reactor.py` is **not edited** (its source is
in SYN-001's model versions; editing it would move SYN-001's identity): the C1 units check against a registry constant
in a new module (WO-3), and a test asserts the SYN-001 constant is a subset of the registry and the registry equals the
ADR's set (M01.A24). ADR 0001 D5.2 is unchanged: streams of `pr-c1-v1` and of SYN-001 never mix (`REFERENCE_MISMATCH`).

The group's reactor uses the same kind of datum (Δ_fH + ∫c_p, ideal gas, 298.15 K) with its own values
(Δ_fH(NH₃) = −46 120 J/mol, DIPPR-107 c_p): its internal enthalpies are **not** process enthalpies and never cross the
boundary (§8.10).

## 7. Phase contract v2 for the PR units (normative for M02's units)

The units on `pr-c1-v1` (flash, heater/cooler, mixer, splitter; M02) use `T05b-phase-contract-v2` with these rules:

1. **Regimes.** A PR split's lattice is `LIQUID — TWO_PHASE — VAPOR` with `ZERO_FLOW` adjacent to each (ADR 0012 D4).
   LIQUID is admissible only when no light gas flows in the split's feed; with light gas flowing the reachable regimes
   are VAPOR and TWO_PHASE.
2. **Rows.** TWO_PHASE: material rows n_in,i − n_V,i − n_L,i = 0 for every i; the liquid's light-gas flows are not
   variables (structural zeros, ADR 0001 D3.3); **one equilibrium row, division-free and log-free (R-008's form):
   E = n_V,NH₃ · φ_NH₃^V(T, P, n_V) − n_V,tot · φ_NH₃^L(T, P) = 0** (mol/s; it is y φ^V = φ^L multiplied by n_V,tot),
   scaled by the registered flow scale. VAPOR: n_L,i = 0 rows, no equilibrium row. LIQUID: n_V,i = 0 rows.
3. **Admissibility** (ADR 0005 D3, the screen): VAPOR is admissible iff the provider's flash of the split's (n, T, P)
   is VAPOR, or TWO_PHASE with l_NH₃ within the C1 loop's registered flow tolerance (registered by M02; the dew-point
   band, F4); TWO_PHASE iff n_L,NH₃ ≥ 0 and n_V,NH₃ ≥ 0 at the
   solution; LIQUID iff the feed has no light gas and the stable pure phase is liquid.
4. **Saturation band (ADR 0012 D1).** For a feed with light gas the band in T at fixed (n, P) is half-open: no bubble
   point exists (light gases never dissolve), the dew temperature T_d solves n_NH₃ = n_light y*(T_d)/(1 − y*(T_d)).
   A stream is never temperature-degenerate in ADR 0012 D7's sense (that needs both ends within τ_T); the PH kernel's
   band route is not used. For pure NH₃ the band is the point T_sat(P) and ADR 0012's saturation route applies with
   P_sat,EOS of §4 (the PR saturation, §11).
5. **ZERO_FLOW** exactly as ADR 0012 D4 (c).
6. **The verifier (ADR 0013)** fresh-flashes each stream with `pr-c1-v1`'s `flash`; a vapour product at its own dew
   point may come back TWO_PHASE with an O(ulp) liquid (F4) and is admissible by rule 3.

M02 registers these as tests of its units; M01's provider supplies everything they read (ln φ, h, the flash). The
equilibrium row's derivatives come from `evaluate_phase`'s ln φ derivatives (§4.6); `flash` is called without
`derivatives`, which it refuses (§5.4 step 0, Amendment 1).

## 8. The reactor boundary (ADR 0027)

### 8.1 The pin

`ammonia_synthesis_reactor` `main` @ `6089593464fc9bc2c0a0cb58e30ad5433ece6332` (MIT), model `MembraneReactor1D`
(the group's `settings.MODEL_1D = "1d"`), non-isothermal, every permeance pre-factor `P0_<species>` = 0 (a packed bed
whose inner tube is a co-current coolant channel), `pymrm == 2.5.0`, run out of process (M02), never vendored. Kinetics
as implemented, K_NH₃ = exp(−8.3/R + 7000/RT) with R in cal (R-152); the reactor keeps its own kinetics, its own
fugacity-coefficient correlations and its own ideal-gas thermodynamics (ADR 0027 D4).

**Correction to the dossier §6:** at the pin the reactor's molar density is the **ideal gas**, not Peng–Robinson (the
PR branch of `gas_mixture_correlations.molar_density` is commented out); its enthalpy is Δ_fH + ∫ DIPPR-107 c_p (a
cubic spline of c_p, `species_enthalpies`). Its PR parameters are not used at the pin.

### 8.2 Ports and degrees of freedom

The C1 reactor unit (M02's wrapper; the stand-in of §8.13 has the same contract):

| Port | Kind | Direction | State | Phase |
| --- | --- | --- | --- | --- |
| `inlet` | material | inlet | `nTP-v1`, the five components | vapour (a liquid is refused, §8.12) |
| `outlet` | material | outlet | `nTP-v1` | vapour |
| `duty` | energy | inlet | Q, W, positive into the unit (ADR 0001 D4.1) | — |

Rows (n = 5 components): n_out,i − n_in,i − ν_i ξ = 0 (5, ν = (−3, −1, 2, 0, 0)); ξ − Ξ(n_in, T_in, P_in) = 0;
T_out − Θ(n_in, T_in, P_in) = 0; P_out − P_in = 0 (§8.8); Q − (Ḣ_out − Ḣ_in) = 0 with Ḣ from `pr-c1-v1` (§8.10).
Unknowns beyond the inlet: n_out (5), T_out, P_out, ξ, Q — nine rows, nine unknowns: **DOF 0** given the inlet and
the configuration. Ξ and Θ are the external evaluation (the projected extent and the outlet temperature, §8.9); how
M02 embeds them (grey box, tear, surrogate) is M02's.

Configuration (fixed; part of the unit's identity): the geometry, catalyst and coolant of the group's case
`G2 — GHSV sweep_1000` (r_max 0.03 m, r_min 0.005 m, L 1 m + 0.05 m sealing, Dcat 0.333, ε 0.4, ρ_c 590 kg/m³, one
inner tube, co-current, permeate outlet 1 bar), sweep ratio 1, **N_tubes** (a positive real, §8.3), num_z (§10), the
overlay (§8.6), the solver profile (§8.7).

### 8.3 Units mapping and per-tube scaling

- Per-tube inlet flow F_ret_in = n_tot,in / N_tubes (mol/s); composition y_ret_in = n_in/n_tot,in (the reactor's own
  species order is the same H₂, N₂, NH₃, Ar, CH₄); T_ret_in = T_in; **p_ret_out = P_in** (§8.8).
- Coolant (the group's convention, `case_setup.calculate_flows`): pure N₂, F_perm_in = sweep_ratio × F_ret_in,
  T_perm_in = T_in, p_perm_out = 10⁵ Pa.
- Outlet: n_out = N_tubes × (the retentate's axial face flows at z = L, `compute_flows()[0][-1]`), T_out = the last
  retentate cell's temperature (the upwind face value), P_out = P_in.
- The map is homogeneous of degree 1 in (n_in, N_tubes) jointly; registered at N_tubes = 1 per tube.

### 8.4 The nominal inlet

Per tube: F_ret_in = 0.007146961299302104 mol/s (the G2 geometry at GHSV 1000 h⁻¹, `calculate_flows`), y_in =
(0.70, 0.235, 0.03, 0.015, 0.02) (IDAES's reactor-inlet composition, H₂/N₂ = 2.979), T_in = 673.15 K (inside the
kinetics' data domain 643–733 K), P_in = 10⁷ Pa. G2's own 623 K lies outside the data domain and is not the nominal
point.

### 8.5 Five species in the pinned code (findings F-R1, F-R2)

- **F-R1.** `membrane_reactor_1d.py:304–308` hard-codes a three-species backflow inflow concentration
  `[0, 1 − 10⁻⁴, 10⁻⁴]`; with five species the constructor's initialization solve fails on a shape mismatch. The
  adapter subclasses the pinned class and, after `_init_derived()`, sets that attribute to the padded
  `[0, 1 − 10⁻⁴, 10⁻⁴, 0, 0]` × p/(RT). It enters only where the retentate velocity reverses at the outlet face; the
  probe asserts u_ret > 0 on every face and that replacing it by `[0, 0, 0, 1, 0]` changes nothing bitwise
  (M01.A44; Amendment 1 corrects the pointer, which read A47). The code is not patched (used by reference).
- `P0_Ar`, `P0_CH4` (and `EA_*`) are set on the config (zero); `y_perm_in` and `y_perm_init` are given with five
  entries (pure N₂).
- **F-R2.** The kinetics evaluate their fugacity-coefficient correlations at the sum of the **reactive** partial
  pressures (`ammonia_synthesis_kinetics.py:350`, p = Σ over H₂, N₂, NH₃), not the total pressure: with 3.5 % inerts
  the correlations see 0.965 P. The group's model, as pinned; stated, not changed.

### 8.6 The overlay rows (`benchmarks/m01/reactor-overlay.json`)

The pinned database holds H₂, N₂, NH₃ only. M01's overlay adds Ar and CH₄: M, T_c, P_c, ω, Δ_fH from the records;
c_p in the reactor's DIPPR-107 form — Ar exactly 5/2 R (C1 = 20 786.156 545 383 1 J/(kmol K), C2 = C4 = 0), CH₄ a
relative least-squares fit to the NASA c_p on 250–1000 K with C3 = 2000 K, C5 = 1000 K fixed (C1, C2, C4 rounded to
6 digits; max deviation 0.42 %); **transport columns copied at run time from the pinned database's N₂ row**, and binary
rows copied from its H₂/N₂ (pairs with H₂) and N₂/NH₃ (the others) entries (the group's numbers are read from the
pinned checkout, never copied into this repository). The surrogate's effect is measured (§10.4).

### 8.7 Start strategy, solver profile and acceptance

Cold starts with real NH₃ in the inlet fail (`reactor-probe.json` → `cold_start_true_inlet`, num_z = 100: `dt_init`
10⁻⁶, 10⁻³, 10⁻¹ all end after 400 steps at steady-state norms 3.59, 3.58, 3.90, rejected by the group's own
acceptance, two of them with less NH₃ at the outlet than at the inlet — lost states). The registered strategy:

- **S1** (cold): the inlet with y_NH₃ := 10⁻⁹ (the group's `TRACE_NH3`), renormalized; the group's `SOLVER_1D` and
  `DT_INIT_1D = 10⁻⁶`; must be accepted by the group's `solver_acceptance`.
- **S2** (warm): the true inlet, initial fields (c, p, T) from S1, the group's settings, `dt_init = 10⁻⁶`.
- **S3** (polish, M01's profile): on S2's reactor, Newton `rtol = 10⁻¹²`, `atol = 0.1 × target`, `dt_init = 1`,
  ≤ 400 steps, steady-state target **10⁻⁶ × (num_z/100)²** (the norm's roundoff floor grows as num_z²; §10.2).
- **Acceptance (M01):** S3 converged at its target; the group's KPI-drift certificate passes after S3; u_ret > 0 on
  every face; every axial flow > 0; |ΔP|/P_in ≤ ε_P (§8.8); the element defect ≤ 10⁻⁶ (§8.9). A failed criterion
  carries no outlet values (§8.12). *Who judges what (Amendment 1):* the evaluation (M02's adapter) judges the first
  four and reports a failure as `NotAccepted(<stage>)`, which the boundary returns as `not_converged`,
  `reactor_not_accepted(<stage>)`; the boundary judges the last two on the evaluation's output, with their own codes
  (`unsupported`, `pressure_drop_exceeds_convention`; `not_converged`, `element_balance_defect`).

Why S3: at the group's tolerance (absolute norm 10⁻³) two accepted, certified states from different starts differ by
0.45 % in outlet y_NH₃ and 0.5 K in T_out at num_z = 100 (the Newton exits on `atol = 10⁻³` at its first iterate, so
the state cannot improve); S3 makes the outlet a function of the inlet to the path-independence level of §10.3.

### 8.8 Pressure: the zero-pressure-drop convention

The process sees ΔP = 0: P_out = P_in. The reactor runs with p_ret_out = P_in, so its bed is at P_in + ΔP_Ergun(z);
the inconsistency sits at the inlet only and equals ΔP/P_in (measured 4.9 × 10⁻⁵ at the nominal point; §10). The
convention is **admissible iff |ΔP|/P_in ≤ ε_P = 10⁻³**; otherwise the request is refused
`pressure_drop_exceeds_convention` (M02's "incompatible pressure boundary rejected"). A recycle compressor is not
modelled (it would need PR entropy and an efficiency; v0.2 does not). ε_P's argument: the rate scales roughly with
P^1.5, so ε_P bounds the unrepresented pressure effect on the rate near 0.15 %, below the reactor's discretization
error at the design grid (§10) and far above the measured nominal value.

### 8.9 The outlet projection and the elemental balance

The reactor's raw outlet n_raw conserves elements only to its residual. The boundary projects onto the reaction's
manifold: **ξ = Σ_{i∈{H₂,N₂,NH₃}} ν_i (n_raw,i − n_in,i) / Σ ν_i²** (= /14), n_out = n_in + ν ξ (inerts exactly their
inlet values), defect d = n_raw − n_out, defect_rel = max_i |d_i| / n_tot,in. The projected outlet conserves H, N, C
and Ar exactly (E ν = 0, claim RX-01). Refusal `element_balance_defect` iff defect_rel > 10⁻⁶ (measured 6 × 10⁻¹⁰ to 2.7 × 10⁻⁸
under S3; the group's loose tolerance gave ~10⁻⁴ — the previous specifier's "grid-independent floor 2.2 × 10⁻⁴" was
iteration error, §18). Element matrix rows (Ar, C, H, N) over (H₂, N₂, NH₃, Ar, CH₄): (0,0,0,1,0), (0,0,0,0,1),
(2,0,3,0,4), (0,2,1,0,0).

### 8.10 Energy

Q = Ḣ_out − Ḣ_in with both enthalpy flows from `pr-c1-v1` (vapour, `PR-C1-ref-v1`) at (n_out, T_out, P_out) and
(n_in, T_in, P_in): the process-side duty (ADR 0011 D2 total-enthalpy form). Reported diagnostics, never balance
terms: the coolant's heat uptake Q_cool (the group's N₂ c_p, closed-form DIPPR-107 antiderivative), and the
**inlet-face heat loss** −(ΔḢ_ret + Q_cool) by the group's own enthalpies.

**F-R3 (measured, for Frank).** The pinned 1D model imposes the inlet temperature as a Dirichlet condition while
conducting heat axially, so heat leaves through the inlet face: at the nominal point the retentate's enthalpy falls by
12.8 W while the coolant takes up 3.1 W (num_z = 100; at the design grid 800 the inlet-face loss is 6.5 W against
3.3 W to the coolant), i.e. 23–33 % of the reaction heat (≈ 28 W) leaves upstream; the group's own `species_enthalpies` agree with the closed form to 10⁻⁹. With a Danckwerts
inlet this heat would preheat the feed instead. The process duty Q absorbs it (it is heat leaving the unit), so the
boundary stays consistent; the physics question is the group's (§15 Q-F1).

### 8.11 What crosses the boundary

In: n_in, T_in, P_in, N_tubes. Out: n_out (projected), T_out, P_out = P_in, ξ, Q (process side), and the
diagnostics of §8.12. Nothing of the reactor's internal thermodynamics (its enthalpies, densities, φ correlations)
crosses: the outlet is re-evaluated by `pr-c1-v1`.

### 8.12 The result envelope and the known invalid requests

Every reactor result carries: `status` (`ok`, `unsupported`, `out_of_domain`, `not_converged`, `error`), a reason
code, and when `ok`: the outlet state, ξ, Q, defect_rel, ΔP/P_in, Q_cool, the inlet-face heat loss, the
discretization estimate of §10 for the configured grid, `domain_status` (`within_data_domain` or `extrapolated` with
the violated bounds), and the identity (reactor commit, pymrm version, overlay SHA-256, configuration hash, profile).

| Request | Status, code | Testable by |
| --- | --- | --- |
| inlet flash (by `pr-c1-v1`) not VAPOR | `unsupported`, `liquid_at_reactor_inlet` | stand-in |
| component set or order ≠ (H2, N2, NH3, Ar, CH4) | `unsupported`, `component_set_mismatch` | stand-in |
| an inlet outside nTP-v1's state space: a flow negative or not finite, or T or P not finite or ≤ 0, dormant or not (Amendment 2, review F3) | `out_of_domain`, `out_of_domain` (ADR 0001 D2) | stand-in |
| n_tot,in = 0 (every flow +0.0 or −0.0) | `ok`, `ZERO_FLOW`: outlet +0.0, Q = +0.0, T_out = T_in, P_out = P_in, ξ = 0 | stand-in |
| y_NH₃,in < 10⁻⁹ (incl. zero NH₃) | `unsupported`, `nh3_below_trace` (the rate carries a negative power of a_NH₃, regularized in the code by A_SMALL = 10⁻⁴ bar; the group feeds 10⁻⁹) | stand-in |
| T_in ∉ [573.15, 773.15] K or P_in ∉ [5×10⁶, 1.5×10⁷] Pa or H₂/N₂ ∉ [1, 4] or y_inert > 0.2 | `out_of_domain` (the adapter's hard domain, around the group's case envelope 548–698 K; M01 measured the start strategy at 653.15–693.15 K and 10⁷ Pa only — inside the hard domain a failure is `not_converged`, never a silent result; Q-F4) | stand-in |
| |ΔP|/P_in > 10⁻³ | `unsupported`, `pressure_drop_exceeds_convention` | stand-in (reported ΔP), M02 (real) |
| the reactor's result fails §8.7's acceptance | `not_converged`, `reactor_not_accepted(<stage>)`, no outlet values | M02 (real); stand-in boundary with an evaluation returning `NotAccepted` |
| defect_rel > 10⁻⁶ | `not_converged`, `element_balance_defect` | stand-in (injected) |
| the provider's inlet flash refuses (out of its domain, a metastable vapour; Amendment 1. A negative or non-finite flow is the boundary's own step 2 since Amendment 2) | the provider's status and reason code, passed through with its message | stand-in boundary with a refusing provider |
| the provider refuses Ḣ_in or Ḣ_out (`evaluate_phase` not `ok`; Amendment 1) | `error`, `stream_enthalpy_refused`, the provider's message carried | stand-in boundary with a refusing provider |
| a liquid with dissolved light gas anywhere | not representable: refused by the provider (§5.3) | provider |
| inside the hard domain but outside the kinetics' data domain (T_in 643.15–733.15 K, P_in 5×10⁶–10⁷ Pa, H₂/N₂ ∈ [1.5, 3]) | `ok` with `domain_status: extrapolated` and the list | stand-in |

**`<stage>` (Amendment 1)** matches `[A-Za-z0-9_]+`. The registered stages: `S1`, `S2`, `S3` (that stage did not reach
its target, or the group's acceptance rejected its state), `certificate` (S3 converged; the KPI-drift certificate
failed), `backflow` (u_ret ≤ 0 on a face), `nonpositive_flow` (an axial flow ≤ 0). M02 may register further stages
(a timeout, say) in its own specification, each with a test; the boundary passes the stage through verbatim.

**Check order (normative, Amendment 1; step 2 inserted by Amendment 2).** (1) component set and order, including the
flow vector's length (`component_set_mismatch`); (2) nTP-v1's state space: every flow finite and ≥ 0 (−0.0 is zero),
T and P finite and > 0, else `out_of_domain`, `out_of_domain` (ADR 0001 D2; Amendment 2, review F3); (3) a dormant
inlet (`ZERO_FLOW`, before any composition is formed; its T and P are labels, ADR 0001 D3.1, free within the state
space); (4) the inlet's TP flash by `pr-c1-v1` (a refusal passes through; a result other than VAPOR is
`liquid_at_reactor_inlet`); (5) the NH₃ trace; (6) the hard domain; (7) the evaluation (`NotAccepted` →
`reactor_not_accepted(<stage>)`); (8) the pressure convention; (9) the element defect; (10) the two enthalpy flows
(`stream_enthalpy_refused`); (11) `ok`, with the data-domain flag. *Why step 2 precedes the dormant check (Amendment
2):* `is_dormant` tests n_tot = 0, so (0.5, −0.5, 0, 0, 0) was answered `ZERO_FLOW` with an all-zero outlet, against
the reactor's own H₂ and N₂ rows (§8.2), and an all-zero inlet with T = NaN was answered `ok` with T_out = NaN; the
provider refuses both (its domain check precedes its dormancy check, A50), and the boundary now does too. *Why this
order:* every other registered refusal
has a single defect and gives its own code under any order. A liquid inlet cannot have a single defect. No liquid
exists inside the hard domain: its lowest inlet temperature, 573.15 K, lies above NH₃'s T_c,EOS = 405.55 K (claim
BD-06), and the flash is VAPOR there for any feed (§5.4 step 4). If the hard domain came before the inlet phase,
`liquid_at_reactor_inlet` could never be returned. M01.A30's liquid inlet (F7's state, also outside the hard domain)
asserts the order. Steps 7–9 judge the evaluation's output and so follow it.

The data domain flags rather than refuses (ADR 0027 D9): the design variable of v0.2 is the reactor inlet temperature,
whose optimum may lie below 643 K (the group's draft reports 573 K for its membrane reactor), and the bed's own
temperature leaves the data domain at every registered state (T_max 760–767 K at the design grid). A refusal would hide the very question
the journey asks; the flag keeps it visible to M04/M05.

### 8.13 The synthetic stand-in reactor (in-repo gate, no PyMRM)

Model id `c1.reactor_standin` (M01-build), same ports, rows, refusals and envelope as §8.2–8.12, with the external
evaluation replaced by closed forms: **ξ_s = X n_N₂,in, X = 0.25 (per-pass N₂ conversion); T_out = T_in**; an
optional injected raw-outlet perturbation d (test-only parameter) and an optional reported ΔP (test-only parameter).
It exercises every boundary path and certifies nothing about the real reactor. Registered: inlet V1's n at 673.15 K,
10⁷ Pa → ξ = 0.05875, n_out = (0.52375, 0.17625, 0.1475, 0.015, 0.02), Q = −6205.800878966381 W (Ḣ_in =
8411.091539543166 W, Ḣ_out = 2205.290660576785 W, Q/ξ = −105 630.65325900223 J/mol); with d = (2, −1, 3, 0.1, 0) ×
10⁻⁶ mol/s: ξ = 0.05875 + 10⁻⁶/14, defect as in `reference_values.yaml` → `closed_form.boundary.projection`.

*Where "synthetic" is written (Amendment 1).* The frozen `ModelManifest` schema has no `synthetic` field
(`additionalProperties: false`), and adding one is a schema change M01 does not make. The label is therefore carried
by the fields that exist, and is checkable (M01.A49):
- the manifest's `title` names a synthetic stand-in;
- its `description` begins `SYNTHETIC`;
- its first `validity.limitations` entry begins `SYNTHETIC:`;
- every `ok` result's `identity.synthetic` is `true` (M02's adapter writes `false`). This is the machine-readable
  label, and every piece of evidence that cites a result carries it. A refusal carries no values and so nothing that
  could be cited as reactor output.

The manifest's `status` is a software status (`tested`), never a validation claim. The stand-in is not in
`MODEL_BUILDERS`, so a revision that names it is refused `model_unsupported(c1.reactor_standin)` (T08 U04). The v0.2
working envelope (`benchmarks/t08/support_envelope.yaml`) therefore does not list it at M01 (§8.14).

### 8.14 The M01/M02 boundary

M01 (this package): the provider, the records, the boundary module (mapping, projection, convention checks, envelope,
refusal codes), the stand-in, the overlay and the probe. M02: the out-of-process execution adapter (environment
creation from pins, the subclass of F-R1, the S1–S3 strategy, timeouts, caching keyed on exact inputs and the
configuration hash, failed runs retained, frozen model versions, promotion), the PR-capable unit models of §7, and the
re-measurement of §10's regression values through its adapter (M01.A41–A48 run by M02, §8.15; Amendment 1 corrects
the range, which read A45–A50. M01.A49–A52 are Amendment 1's in-gate assertions, §9.10, and are not M02's).

What M02 inherits from Amendment 1:
- The adapter is an `ExternalEvaluation` of the boundary module. It returns `NotAccepted(<stage>)` with §8.12's
  registered stages, and it leaves |ΔP| and the element defect to the boundary (§8.7).
- §8.12's check order and codes hold for the real unit unchanged.
- Its result identity has `synthetic: false` and the reactor fields filled.
- The real reactor model enters `MODEL_BUILDERS`, and with it the envelope's `unit_models` axis, with its
  limitations (§10's discretization estimate, `extrapolated` results, F-R2, F-R3).
- If M02 also binds the stand-in for in-repo loop tests, the envelope lists it as synthetic, with a limitation row
  saying it certifies nothing about the reactor. It is never listed as a supported reactor model (R-199).

### 8.15 The M02 hand-off: what is reproduced, where, and what the gate checks (Amendment 1)

Two halves of each probe assertion. The **record half** is M01's: `benchmarks/m01/reactor-probe.json` (version 2),
made once by `reactor_probe.py` in its own environment. The **adapter half** is M02's: the same quantity re-measured
through M02's `ExternalEvaluation`.

| Assertion | Record half (M01, in the gate: M01.A52) | Adapter half (M02) |
| --- | --- | --- |
| A41 | `pinned` and both neighbouring inlet temperatures: num_z 800, accepted; the three cold starts at the true inlet (num_z 100): rejected | S1–S3 accepted at num_z = 800 for T_in ∈ {653.15, 673.15, 693.15} K; the failing cold start is not re-run |
| A42 | `path_independence.max_rel_diff` ≤ 10⁻⁶ (recorded 1.56 × 10⁻⁸) | S2 with `dt_init` 10⁻⁶ and 10⁻¹ at the nominal point: outlets within 10⁻⁶ relative |
| A43 | `repeats`: 2 runs, bitwise identical | two adapter runs with the cache bypassed: bitwise identical |
| A44 | `backflow_override` bitwise identical; `u_ret_min` > 0 in every entry | the same, through M02's own F-R1 subclass |
| A45 | max \|element defect\| ≤ 10⁻⁷ in every accepted entry | every accepted adapter run |
| A46 | \|ΔP\|/P_in ≤ 10⁻³ in every entry | every accepted adapter run |
| A47 | — | (a) bitwise and (b) within 10⁻⁶, as A47 states |
| A48 | grid sequence 100–3200, accepted exactly for 100–800; the estimate recomputed by claim DX-01 | every `ok` result's `discretization_estimate` equals `reference_values.yaml` → `derived_from_measured.discretization_estimate` |

**Environment.** The adapter half runs in the probe's kind of environment: a venv built from the pins of
`reactor_probe.py`, with the pinned reactor clone exported by `git archive` and one thread. It is recorded as
evidence-manifest rows (as M01's probe row, §13), not as default-gate tests, because PyMRM is not a dependency of the
gate. Whether M02 adds a separate CI job for it is M02's decision. M02's record states its `environment` block in the
probe's format, plus the CPU model, which the probe record lacks.

**Is the probe record a gate-checked regression?** Yes, in two ways, and never as an expectation for this repository's
code.
- Its bytes are pinned by A34: `derived_from_measured.probe_sha256`. An edited record fails `--check` until the
  generator is re-emitted, which shows in review.
- M01.A52 (WO-8) checks every record half above against the record's own numbers, so the spec and the record cannot
  drift apart.

The gate never re-runs the reactor.

**Q-F4's sweep, defined.** The 16 corners of T_in × P_in × H₂/N₂ × y_inert, with values {573.15, 773.15} K ×
{5 × 10⁶, 1.5 × 10⁷} Pa × {1, 4} × {0, 0.2}, plus the centre (673.15 K, 10⁷ Pa, 2.5, 0.1). At every point:
y_NH₃ = 0.03; Ar:CH₄ = 3:4 (the nominal ratio); the nominal per-tube flow F_ret_in = 0.007146961299302104 mol/s;
num_z = 800; S1–S3 through the adapter. That is 17 solves, ≈ 2.5 min. Each corner's inlet is built so that it
satisfies `hard_domain_violations` in floating point. If the exact construction rounds outside a bound (y_inert = 0.2,
say), the value is moved inward by at most 2⁻⁴⁰ relative. An `out_of_domain` at a corner is a construction error,
not a result. For each point M02 records the status, the code
and stage, the wall time, and, when `ok`, A45's and A46's values. The sweep is a measurement, not a pass/fail gate:
every point must end `ok` or in a typed refusal, never silently. If any point inside the hard domain is not accepted,
M02 narrows the hard domain by a register entry and an ADR 0027 amendment, and registers the failing point as a
refusal test (Q-F4's default). The per-tube flow is not a dimension of the hard domain today (Q-F5).

## 9. Assertions

Expectations come from `reference_values.yaml` (`closed_form`) unless stated. "rel ε" means |impl − ref| ≤ ε·max(|ref|, 1)
for dimensionless or J/mol quantities, and |impl/ref − 1| ≤ ε for molar volumes and flows. The double-precision floor of
a straightforward transcription is measured by the generator (`measured.transcription_floor`): ≤ 4.1 × 10⁻¹⁶ for Z, h
(J/mol, relative) and every ln φ at V1, V2, L1. Each tolerance below sits ≥ 10³ above that floor and ≥ 10³ below the
smallest defect worth catching (a dropped mixing term, a permuted component or a one-digit error in a constant moves
these values by ≥ 10⁻⁶; Ω_a's fifth digit moves ln φ_NH₃ at V2 by ~10⁻⁵). Two assertions are about quantities with a
floor of their own: the ln φ derivative identities (A12) and the projection's defect (A26). Amendment 1 states those
floors there, measured on those quantities, with their margins in `reference_values.yaml` → `assertion_margins`.

### 9.1 Records and declaration

- **M01.A01** — `components.yaml` holds five records, ids in the order H2, N2, NH3, Ar, CH4; each validates against
  `component-record.schema.json` and `check_quantity`; `synthetic: false`; `elemental_verification: VERIFIED`. Exact.
- **M01.A02** — `external-crosscheck.json` has `retrieval_all_equal: true` and every `retrieval.*.equal` true (form test
  in the gate; the script's `--check` is evidence in the manifest).
- **M01.A03** — The provider's parameters equal the records' values bitwise (as parsed floats); `data_sha256` is the
  SHA-256 of `components.yaml`'s bytes; `implementation_sha256` the SHA-256 of the provider module's source. Exact.
- **M01.A04** — `describe()`: `provider_id` `pr-c1-v1`, `reference_convention` `PR-C1-ref-v1`, `state_definition`
  `nTP-v1`, components (H2, N2, NH3, Ar, CH4), phases (LIQUID, VAPOR), properties ⊇ {h, Z, v, lnphi_H2, lnphi_N2,
  lnphi_NH3, lnphi_Ar, lnphi_CH4}, flashes ("TP",), derivative_order = {T: 1, P: 1, n_H2: 1, n_N2: 1, n_NH3: 1,
  n_Ar: 1, n_CH4: 1}, domain {T: (200.0, 1000.0), P: (1e4, 3e7)}. Exact.

### 9.2 Closed-form values

- **M01.A05** — Per component: κ, a_c, b rel 10⁻¹⁴; NH₃'s T_c,EOS rel 10⁻¹³ (`closed_form.components`,
  `nh3_eos_critical`). Simple products; the floor is a few ulp.
- **M01.A06** — c_p^ig(298.15 K), c_p^ig(700 K), h^ig(268.15 K), h^ig(700 K) per component rel 10⁻¹²; h^ig(298.15 K) =
  Δ_fH° within 10⁻⁹ J/mol.
- **M01.A07** — Phase states V1, V2, V3, V4, V5, L1, L2: Z, h, every reported ln φ rel 10⁻¹²; v rel 10⁻¹².
- **M01.A08** — Roots and labels: L2 and V3 (one state, three roots) have distinct Z equal to the reference's smallest and
  largest; L1 is a single liquid-like root (v < v_c,EOS); V4 is the single supercritical root. Values as A07.
- **M01.A09** — V1's five ln φ are nonzero and differ pairwise by at least 10⁻⁶, and V2's likewise; every |h^dep| at
  V1–V5, L1, L2 exceeds 1 J/mol (a dropped departure term fails A07). *Why 10⁻⁶ (Amendment 1):* it is 10⁶ times A07's
  tolerance, so a permuted component index fails A07 by at least that factor. The reference's smallest gaps are
  4.35 × 10⁻⁴ (V1, H₂/CH₄) and 0.046 (V2, N₂/Ar) (`assertion_margins.A09_min_pairwise_lnphi_gap`; claim PH-GAP holds
  the 10⁻⁶ bound on the reference). The draft's parenthetical, "changes A07's comparison by ≥ 10⁻³", was false at V1.

### 9.3 Derivatives

- **M01.A10** — At V1, V2 (VAPOR) and L1 (LIQUID), for every property X ∈ {Z, v, h, ln φ_*} and input x ∈ {T, P,
  n_j}: |s·(∂X/∂x)_impl − s·(∂X/∂x)_ref| ≤ 10⁻⁹·max(|X|, 1, |s·(∂X/∂x)_ref|), s = T, P or n_tot,in respectively
  (`closed_form.derivatives`). Argument: an analytic or AD derivative in double has no stencil; its floor is the
  value floor times the conditioning (≲ 10⁻¹³); 10⁻⁹ leaves 10⁴. A sign error or a dropped implicit-root term is
  ≥ 10⁻³ relative.
- **M01.A11** — L1's n-derivatives are exactly 0.0 (pure-liquid properties are composition-free); V1's and V2's are all
  nonzero (DER-NZ: each > 10⁻¹² in magnitude), so A10 is not met by zeros.
- **M01.A12** — Identities of the implementation itself, independent of the reference, at V1 and V2 (as amended by
  Amendment 1). Homogeneity of X ∈ {Z, v, h}: |Σ_j n_j ∂X/∂n_j| ≤ 10⁻¹²·Σ_j |n_j ∂X/∂n_j|. The ln φ block: with the
  dimensionless J_ij = n_tot ∂ln φ_i/∂n_j, y = n/n_tot and **M = max_{i,j} |J_ij|**:
  - homogeneity |Σ_j y_j J_ij| ≤ 10⁻¹² M for every i;
  - Gibbs–Duhem |Σ_i y_i J_ij| ≤ 10⁻¹² M for every j;
  - symmetry |J_ij − J_ji| ≤ 10⁻¹² M for every i, j.

  *Floor.* A computed J_ij carries a few ulp of the terms it is built from, and those terms are the size of the
  block's largest entries, not of J_ij itself. By symmetry, column j of Gibbs–Duhem is row j of homogeneity in exact
  arithmetic, so the two identities share one floor, ≈ c·u·M (u = 2⁻⁵³). The draft divided each column by its own
  Σ_i |y_i J_ij|. At V1 that sum is 1.0 × 10⁻⁴ for N₂'s column against M = 0.078, which put the floor at ≈ 10⁻¹³
  (measured 9.97 × 10⁻¹⁴ at `13bcef7`). The draft's tolerance of 10⁻¹² sat only 10× above that, not the 10³ §9 requires.

  *Margin.* Measured at `13bcef7`:

  | Identity | Measured | Location |
  | --- | --- | --- |
  | ln φ homogeneity | ≤ 2.9 × 10⁻¹⁷ M | V1 |
  | Gibbs–Duhem | ≤ 2.5 × 10⁻¹⁶ M | V1 |
  | symmetry | ≤ 3.8 × 10⁻¹⁶ M | V1 |
  | homogeneity of Z, v, h | ≤ 6.1 × 10⁻¹⁶ of their own row scales | V1 (v) |

  10⁻¹² sits ≥ 2.6 × 10³ above the largest of these. A sign error or a dropped term in one derivative moves that
  entry by ≥ 10⁻³ of itself. Even at the smallest entry, J_N₂N₂ at V1 (2.1 × 10⁻⁵), such an error moves homogeneity
  and Gibbs–Duhem by 4.9 × 10⁻⁹, which is 6 × 10⁴ times the bound.
- **M01.A13** — A derivative request for an undeclared input returns `unsupported` with `undeclared_derivative_input`.

### 9.4 Refusals

- **M01.A14** — U1 → `unsupported`, message matches `^light_gas_in_liquid:`; U2 → `^no_liquid_root:`; U3 →
  `^no_vapour_root:`; U4 → `^vapour_root_metastable:`; U5, U6 → status `out_of_domain`, `^out_of_domain:`. A dormant
  state in `evaluate_phase` → `^dormant_state:`. No refusal carries values.

### 9.5 The flash

- **M01.A15** — F1, F5, F11, F13: `ok`, TWO_PHASE; y* (= `k_values["NH3"]`, the only key) rel 10⁻¹¹; `vapor_fraction`
  |Δ| ≤ 10⁻¹²; vapour NH₃ and liquid NH₃ flows rel 10⁻¹¹; the liquid's light-gas flows are +0.0 exactly; the vapour's
  light-gas flows equal the feed's bitwise. Argument: y* is a root of one scalar equation found by bisection to ~ulp;
  roundoff in h (≲ 10⁻¹⁵) moves y* by ≲ 10⁻¹⁵/(y* h′(y*)) ≈ 10⁻¹⁵ relative (h′ ≈ 1/y*).
- **M01.A16** — At the implementation's own TWO_PHASE results (A15 states), its own `evaluate_phase` gives
  |ln y* + ln φ_NH₃^V − ln φ_NH₃^L| ≤ 10⁻¹² (the equilibrium row closes on the provider's own evaluations).
- **M01.A17** — Single-phase routes: F2 VAPOR, F3 VAPOR, F6 VAPOR, F8 VAPOR, F9 VAPOR, F10 VAPOR (vapor_fraction 1.0,
  liquid dormant), F7 LIQUID (vapor_fraction 0.0, vapour dormant); the present phase equals the feed bitwise;
  `k_values` empty.
- **M01.A18** — F4 is VAPOR, or TWO_PHASE with liquid NH₃ ≤ 10⁻¹² × the feed's NH₃.
- **M01.A19** — F12 is VAPOR (the rules' answer at the near-critical state; registered behaviour, not a physical claim).
- **M01.A20** — F14: `ok`, `ZERO_FLOW`, `vapor_fraction` None, both outlets all +0.0, `k_values` empty.
- **M01.A21** — Feed independence: F1 with its NH₃ doubled gives y* bitwise equal to F1's.
- **M01.A22** — Material closure: for every TWO_PHASE result, vapour + liquid = feed componentwise within 1 ulp of the
  feed's component flow.

### 9.6 Datum, reaction-consistent set, the stand-in, the boundary

- **M01.A23** — Σ ν_i h_i^ig at 298.15 K = −91 116 J/mol within 10⁻⁹ J/mol; at 673.15 K rel 10⁻¹² (−104 003.12297042357).
- **M01.A24** — The registry of reaction-consistent conventions equals {`SYN-001-ref-v1`, `PR-C1-ref-v1`}; SYN-001's
  constant is unchanged and a subset; a C1 reacting unit over `pr-c1-v1` constructs; over an unregistered convention it
  raises `reference_convention_not_reaction_consistent(<convention>)`.
- **M01.A25** — Stand-in at V1's inlet: ξ = 0.05875 rel 10⁻¹⁴; n_out as §8.13 rel 10⁻¹⁴; T_out = T_in, P_out = P_in
  bitwise; Q = −6205.800878966381 W rel 10⁻¹⁰ (Ḣ_in, Ḣ_out rel 10⁻¹¹; the difference amplifies by 1.4).
- **M01.A26** — Projection with the registered d (as amended by Amendment 1):
  - ξ and the projected outlet: rel 10⁻¹² (measured 2.2 × 10⁻¹⁶);
  - the inerts' projected flows equal their inlet flows bitwise, and the CH₄ defect is exactly 0.0 (raw and inlet are
    the same double and ν_CH₄ = 0);
  - the defect vector: |d_i − d_i,ref| ≤ **10⁻¹³ × n_tot,in** for every i, and |defect_rel − defect_rel,ref| ≤ 10⁻¹³;
  - the projected outlet conserves Ar, C, H and N: |Σ_i E_ki (n_out,i − n_in,i)| ≤ **10⁻¹³ × n_tot,in** for each
    element.

  *Floor.* The defect is about 10⁻⁶ mol/s, a difference of flows near 0.5 mol/s, so its 53-bit floor is the raw
  outlet's own rounding: 5.6 × 10⁻¹⁷ × n_tot,in, which is 2.5 × 10⁻¹¹ of the defect itself (claim BD-04;
  `assertion_margins.A26_projection`). No binary64 implementation can reach the draft's relative 10⁻¹². The element
  balances have a floor of 2.8 × 10⁻¹⁷ × n_tot,in in exact sums over the double outlet. Evaluated as float sums, though,
  each may add up to γ₅·Σ_i |E_ki n_i|, ≈ 1.7 × 10⁻¹⁵ for the H row (a worst-case bound, not a measurement), which is
  above the draft's 10⁻¹⁵.

  *Margin.* 10⁻¹³ × n_tot,in sits 1.8 × 10³ above the measured floors and 57 times above that worst-case bound. It
  sits at least 10⁶ below the nearest listed wrong projection. Dropping the inert defect moves d by 10⁻⁷ × n_tot,in, a
  one-species extent moves it by ≥ 2.2 × 10⁻⁶, and a reversed sign, divisor 13 or permuted H₂/N₂ stoichiometry moves it
  by more (claim BD-05). The build measured 2.5 × 10⁻¹¹ relative (5.5 × 10⁻¹⁷ mol/s) at `f595179`.
- **M01.A27** — Pressure convention: reported ΔP 5000 Pa at P_in 10⁷ → `ok`; 20 000 Pa → `unsupported`,
  `pressure_drop_exceeds_convention`.
- **M01.A28** — Zero-flow inlet → `ZERO_FLOW` result per §8.12; Q is +0.0 exactly.
- **M01.A29** — Per-tube scaling: the stand-in's result for (k n_in, k N_tubes), k ∈ {2, 7}, equals k × the result for
  (n_in, N_tubes) rel 10⁻¹⁵ (n_out, ξ, Q).
- **M01.A30** — Each refusal of §8.12 testable by the stand-in returns its status and code (inlet liquid: F7's state as
  inlet; component mismatch: a permuted order; trace: y_NH₃ = 10⁻¹⁰; hard domain: T_in = 550 K; defect: d with
  defect_rel 2 × 10⁻⁶) and carries no outlet values.
- **M01.A31** — Data-domain flag: T_in = 623.15 K (inside the hard domain) → `ok`, `domain_status: extrapolated`
  listing `T_in`; T_in = 673.15 K → `within_data_domain`.
- **M01.A32** — The envelope of an `ok` result has every field of §8.12 (stand-in: the reactor-specific diagnostics
  are present and `null`).

### 9.7 What must not move, and the tools

- **M01.A33** — Existing identities unchanged: the gate passes with no edit to any registered value under
  `benchmarks/syn001/`, `benchmarks/t05/`, `benchmarks/t05b/`, `benchmarks/t06/`, `benchmarks/t08/`, the K05 identity
  fixtures, or `models/syn001/`; SYN-001's structural hash and the K05 identity document are reproduced bit for bit.
- **M01.A34** — `m01_reference.py --check` exits 0 (88 claims hold, files byte-identical; 82 before Amendment 1 added
  PR-07, PH-GAP, BD-04, BD-05, BD-06, DX-01).
- **M01.A35** — No runtime import of `chemicals`, `thermo`, `CoolProp`, `cantera` or `mpmath` from `openflowsheet`;
  `pyproject.toml`'s runtime dependencies unchanged.
- **M01.A36** — Exact caching: two `evaluate_phase` requests differing by one ulp in T produce different cache keys and
  both evaluate (the existing cache rule; the provider supplies non-empty identity hashes).

### 9.8 External conformance and validation (W22)

- **M01.A37** — IDAES conformance (build lane, IDAES 2.13 env, M01's records, k_ij = 0, vapour-only convention): at V1, V2
  and L1, ln φ |Δ| ≤ 10⁻⁹ and Z rel 10⁻⁹; at F1 and F11, β |Δ| ≤ 10⁻⁸ and y* rel 10⁻⁸; record
  `benchmarks/m01/idaes-conformance.json` with environment hashes. Argument: claim IDAES-01 shows agreement at 4 × 10⁻¹²
  (β) and 4 × 10⁻¹⁵ (φ) with T08's parameters; Ipopt's tolerance bounds β; 10⁻⁸ leaves a margin of ~10³.
- **M01.A38** — W22, pure NH₃ saturation: |P_sat,PR/P_sat,ref − 1| ≤ 0.02 at 240, 260, 268.15, 280, 300, 320 K against
  CoolProp 8.0.0's ammonia (Gao et al. 2020). Measured maximum 0.0127 (240 K); 0.0072 at 268.15 K.
- **M01.A39** — W22, liquid NH₃ fugacity at the separator states: |ln φ^L_PR − ln φ^L_ref| ≤ 0.05 at (268.15 K, 10⁷ Pa)
  and (250 K, 2.5 × 10⁷ Pa). Measured 0.0254 and 0.0401.
- **M01.A40** — W22, vapour fugacity of each pure light gas at (268.15 K, 10⁷ Pa) and (673.15 K, 10⁷ Pa), and of NH₃
  vapour at (673.15 K, 10⁷ Pa): |Δ ln φ| ≤ 0.05. Measured maximum 0.0424 (CH₄, 268.15 K).

The W22 bands are validation bands (§11), not numerical tolerances: they bound the model's empirical error at the
states the loop uses, and implementation bugs are caught by A05–A22 at 10⁻⁹–10⁻¹⁴.

### 9.9 The reactor (W21; measured by M01's probe, re-measured by M02's adapter)

Values from `benchmarks/m01/reactor-probe.json` (version 2). These are regression values of the group's model on one
machine (the probe's environment record); M02's adapter must reproduce them.

- **M01.A41** — The start strategy is accepted (§8.7) at the design grid num_z = 800 for T_in ∈ {653.15, 673.15, 693.15} K,
  and the group's cold start at the true inlet is rejected for `dt_init` ∈ {10⁻⁶, 10⁻³, 10⁻¹} (the failure S1–S2 exist for).
- **M01.A42** — Path independence at the design grid: S2 with `dt_init` 10⁻⁶ and 10⁻¹ give outlets (n_out, T_out) within
  10⁻⁶ relative (§10.3; measured 1.6 × 10⁻⁸).
- **M01.A43** — Repeatability: two repeats at the design grid are bitwise identical (one machine, one environment).
- **M01.A44** — The backflow override is inert: replacing it by `[0, 0, 0, 1, 0]` leaves the outlet bitwise unchanged,
  and u_ret > 0 on every face.
- **M01.A45** — Raw element defects |Δ(H, N, C, Ar)|/inlet ≤ 10⁻⁷ at every accepted grid (measured ≤ 2.7 × 10⁻⁸ at
  800, ≤ 9.2 × 10⁻¹⁰ at 100–400); the refusal threshold 10⁻⁶ of §8.9 sits 37 times above the design grid's value.
- **M01.A46** — |ΔP|/P_in ≤ 10⁻³ at every registered point (measured 4.90–5.06 × 10⁻⁵).
- **M01.A47** — M02's adapter reproduces the probe's design-grid nominal outlet (as amended by Amendment 1). The
  outlet means the evaluation's raw `TubeOutlet`, at N_tubes = 1, before projection: five flows and T_out.
  - (a) *Bitwise.* M02's `ExternalEvaluation` is called with the record's tube inputs exactly: `pinned.F_ret_in_mol_s`,
    `pinned.y_in`, T_in, p_ret_out = P_in, and §8.3's coolant. The environment block equals the record's (python, the
    four packages, the platform string, one thread). The call then returns flows and T_out equal to
    `pinned.outlet_n_mol_s` and `pinned.T_out_K` bitwise. If the environment block is equal and the bits are not,
    that is reported as a finding naming both CPU models, and (b) decides acceptance.
  - (b) *Within 10⁻⁶ relative* on each of the five flows and on T_out, in two cases: the same call in any environment
    with the same pins (reactor commit, `pymrm` 2.5.0, overlay bytes, configuration, profile), and the full boundary
    at N_tubes = 1 with the process inlet n = `pinned.inlet_n_mol_s`.

  *Why the full boundary is under (b):* the record was made from (F, y), not from n. §8.3's mapping of the recorded n
  differs from F by 1 ulp in Σn and from y by 1 ulp in four components (M01.A52). 10⁻⁶ is §10.3's path-independence
  bound, 64 times the measured iteration noise.
- **M01.A48** — The refinement record holds the grid sequence of §10.1 with its order estimate and the design grid's
  discretization estimate; every reactor result reports that estimate (§8.12).

### 9.10 Amendment 1: request checks, boundary paths, the synthetic label, the probe record (in the gate)

- **M01.A49** — The stand-in is labelled as §8.13 states. Its manifest validates against
  `model-manifest.schema.json`. Its `title` contains `synthetic` (case-insensitive), its `description` begins
  `SYNTHETIC`, and its `validity.limitations[0]` begins `SYNTHETIC:`. Every `ok` result has `identity.synthetic` exactly
  `true`. `MODEL_BUILDERS` has no key `c1.reactor_standin`, and the revision binder refuses a revision naming it
  `model_unsupported(c1.reactor_standin)`. Exact. The stand-in's status as an unsupported model is checked, not
  assumed.
- **M01.A50** — Provider request checks (§5.3, §5.4 step 0):

  | Request | Status | Message matches |
  | --- | --- | --- |
  | `evaluate_phase` at V1 with properties `("h", "s")` | `unsupported` | `^unknown_property:` |
  | either method with a state of 4 or of 6 flows | `error` | `^state_length:` |
  | either method with V1's flows and N₂ = −0.235, or NH₃ = +inf, or T = NaN | `out_of_domain` | `^out_of_domain:` |
  | `flash` with `specification="PH"` | `unsupported` | `^unsupported_specification:` |
  | `flash` of F1's state with `derivatives=("T",)` | `unsupported` | `^flash_derivatives_unsupported:` |

  No refusal carries values, derivatives or a split (`phase_signature`, `vapor_fraction`, `vapor`, `liquid` all
  `None`). Exact. Each state has exactly one defect.
- **M01.A51** — Boundary paths beyond A30 (§8.12):
  - (i) an evaluation that returns `NotAccepted("S3")` → `not_converged`, code `reactor_not_accepted(S3)`; every code
    of this kind matches `^reactor_not_accepted\([A-Za-z0-9_]+\)$`;
  - (ii) a provider whose `flash` answers as `pr-c1-v1` but whose `evaluate_phase` refuses → `error`,
    `stream_enthalpy_refused`, and the message contains the provider's message;
  - (iii) V1's inlet with N₂ = −0.235 → `out_of_domain`, code `out_of_domain`, passed through from the inlet flash;
    *(Amendment 2, review F3: that state is now refused by the boundary's own step 2, see (v); (iii) holds the
    pass-through with a provider whose `flash` refuses the nominal inlet: its status, code and message come back
    unchanged. No inlet inside the state space and the hard domain is refused by `pr-c1-v1`'s flash.)*
  - (iv) the check order: F7's state as the inlet → `liquid_at_reactor_inlet`, although it is also outside the hard
    domain (A30's case; claim BD-06).
  - (v) (Amendment 2, review F3) each inlet outside nTP-v1's state space → `out_of_domain`, code `out_of_domain`, the
    message citing ADR 0001 D2, no outlet values: n = (0.5, −0.5, 0, 0, 0); an all-zero inlet with T = NaN, with
    P = −1 Pa, with P = +∞, with T = 0 K; V1's inlet with N₂ = −0.235, with NH₃ = NaN, with H₂ = +∞. A dormant inlet at
    50 K and 1 Pa (with a −0.0 flow) is still `ZERO_FLOW` with those labels, and a permuted component set still gives
    `component_set_mismatch` first.

  No refusal carries outlet values. Exact.
- **M01.A52** — The probe record, as committed, holds §8.15's record halves:
  - `version` 2; `reactor_commit` the pin of §8.1; `environment.packages.pymrm` `2.5.0`;
  - A41: `pinned` and both `neighbouring_inlet_temperatures` at num_z 800 with `m01_accepted` true;
    `cold_start_true_inlet` with `dt_init` exactly {10⁻⁶, 10⁻³, 10⁻¹}, all `accepted` false;
  - A42: `path_independence.max_rel_diff` ≤ 10⁻⁶;
  - A43: `repeats.runs` 2 with `bitwise_identical` true;
  - A44: `backflow_override.bitwise_identical` true, and `u_ret_min` > 0 in every grid entry and both neighbours;
  - A45: max |`element_defect_rel`| ≤ 10⁻⁷ in every entry with `m01_accepted` true;
  - A46: |`dP_over_P`| ≤ 10⁻³ in every entry;
  - A48: the grid's num_z is (100, 200, 400, 800, 1600, 3200), with `m01_accepted` true exactly for the first four;
  - §10.1's design-grid row equals the record to its printed digits (n_NH₃,out 7.451757058514 × 10⁻⁴ mol/s,
    T_out 757.335312 K);
  - the boundary's `tube_inlet` of `pinned.inlet_n_mol_s` at N_tubes = 1 gives F and y within 2 ulp of
    `pinned.F_ret_in_mol_s` and `pinned.y_in` (the reason A47 (a) is stated at the evaluation).

  Exact unless stated. A regression record of the group's model, never an expectation for this repository's code.

## 10. Numerical refinement evidence (W21, M01's part)

### 10.1 Grid study

Nominal point (§8.4), per tube, the S1–S3 strategy at every grid, one thread (`reactor-probe.json`, version 2):

| num_z | accepted | wall (s) | n_NH₃,out (mol/s) | T_out (K) | inlet-face loss (W) | Q_cool (W) | element defect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 100 | yes | 5.9 | 7.789743815547e-4 | 751.845453 | 9.720 | 3.098 | 6.1e-10 |
| 200 | yes | 5.4 | 7.589297181439e-4 | 755.073854 | 7.823 | 3.227 | 5.5e-10 |
| 400 | yes | 6.7 | 7.505991621934e-4 | 756.438789 | 7.027 | 3.283 | 9.1e-10 |
| **800** | **yes** | **9.0** | **7.451757058514e-4** | **757.335312** | **6.507** | **3.320** | **2.7e-8** |
| 1600 | no (KPI drift 1.9e-3, defect 2.2e-4) | 12.7 | (7.4072e-4) | (758.0495) | — | — | — |
| 1600, +40 polish steps (Newton atol 10⁻¹²) | not accepted (defect still 2.2e-6, moving) | ~100 | 7.42024e-4 ± 2e-9 | 757.8590 | — | — | 2.2e-6 |
| 3200 | no (KPI drift 4.4e-3) | 21.5 | (7.4031e-4) | (758.1442) | — | — | — |

Differences in n_NH₃,out between successive grids: −2.0044e-5 (100→200), −8.331e-6 (200→400), −5.423e-6 (400→800),
−3.151e-6 (800→1600 polished). **Observed order** log₂ of successive ratios: 1.27, 0.62, 0.78 — sub-first-order and not
yet constant; T_out behaves alike (ratios 2.37, 1.52, 1.71). The cause is not established; the measured inlet-face
loss (F-R3), which converges slowly with the grid, is the leading candidate (the inlet's thermal boundary layer is
λ/(ρ c_p u) ≈ 4 mm, i.e. a few cells at num_z = 800).

**Registered discretization estimate at the design grid num_z = 800** (Richardson with p ∈ [0.62, 0.78], from the
400/800 and 800/1600 differences): n_NH₃,out is **high by 1.0–1.4 %** (NH₃ production, ξ, high by 1.4–1.9 %), T_out
**low by 1.2–1.7 K**. An estimate, not a bound (Q-F3). *Amendment 1:* the estimate is registered machine-readably,
recomputed from the record, in `reference_values.yaml` → `derived_from_measured.discretization_estimate`:
- p 0.619–0.783;
- NH₃ 1.02–1.38 %;
- ξ 1.44–1.94 %;
- T_out 1.24–1.67 K.

Claim DX-01 holds these printed ranges to the record. The draft printed T_out's lower end as 1.3 K; the recomputed value
is 1.24 K. The recipe: for each p and each of the two differences, the 800 error is the 400→800 difference × 2⁻ᵖ/(1 − 2⁻ᵖ),
or the 800→1600 difference × 1/(1 − 2⁻ᵖ), with 1600 the record's last fine-polish state. The range is over the four
values, relative to the extrapolated value. At the group's publication grid num_z = 100 the outlet NH₃ is
≈ 5.5 % high and T_out ≈ 7 K low.

Element defects are ≤ 2.7 × 10⁻⁸ at every accepted grid and equal across H, N, C and Ar (a common total-flow factor,
the residual's, not a reaction-stoichiometry error). ΔP/P_in = 4.90–5.01 × 10⁻⁵ at every grid.

### 10.2 Steady-state norm floor

The group's absolute steady-state norm (RMS of the raw residual, `factor_norm` = 1/√(2 num_z (n_c + 2))) has a
roundoff floor that grows with the grid: best norms over 25 polish steps 7.7 × 10⁻⁸ (num_z = 100), 1.7 × 10⁻⁷ (200),
5.9 × 10⁻⁷ (400), 2.2 × 10⁻⁶ (800). The S3 target 10⁻⁶ (num_z/100)² keeps a factor ≥ 13 above it at every grid
measured; a fixed 10⁻⁶ is unreachable above num_z = 400 (the first probe run spent 185 s at 800 against it).

### 10.3 Iteration error and path independence

At the design grid, S2 started with `dt_init` 10⁻⁶ and 10⁻¹ ends, after S3, at outlets that differ by at most
**1.6 × 10⁻⁸** relative (n_out and T_out; 3.4 × 10⁻⁹ at num_z = 400). At the group's own tolerance the same two starts
differ by 0.45 % in y_NH₃ and 0.5 K (num_z = 100). Two repeats are bitwise identical; replacing F-R1's backflow
constant by `[0, 0, 0, 1, 0]` changes nothing bitwise (u_ret ≥ 1.39 × 10⁻³ m/s on every face). **Path-independence
bound (M01.A42, A47): 10⁻⁶ relative** — 64 times the measured 1.6 × 10⁻⁸, and 4500 times below the group-tolerance
path dependence it exists to exclude.

### 10.4 Model-data sensitivity of the inert rows

Copying the transport columns and pairs from H₂ instead of N₂ moves the design-grid outlet by **0.31 %** (max over n_out
and T_out). This is model uncertainty from the surrogate (§8.6), of the same order as the discretization estimate,
and it is stated in every result's identity (the overlay's hash), not hidden in a tolerance.

Neighbouring inlet temperatures at the design grid (accepted, M01.A41): T_in 653.15 K → n_NH₃,out 7.714415577531382e-4,
T_out 753.042982 K, T_max 760.06 K; 673.15 K → 7.451757058514184e-4, 757.335312 K, 763.39 K; 693.15 K →
7.163232261279267e-4, 762.213588 K, 767.30 K. At this GHSV the outlet NH₃ falls with T_in over 653–693 K
(equilibrium-limited hot zone): the interior optimum the v0.2 decision looks for, if any, lies below 653 K, outside the
kinetics' data domain (§8.12, R-169).

Process side (`reference_values.yaml` → `derived_from_measured`, regression): ξ = 2.65383399725e-4 mol/s, projection
defect 9.4 × 10⁻⁹, **Q = −9.750509665 W** per tube by `pr-c1-v1`, against the reactor's own −(3.320 + 6.507) =
−9.827 W: the two thermodynamic data sets (NASA + PR departures against the group's DIPPR ideal gas) differ by 0.8 %
in the duty.

### 10.5 What the coupled loop needs

- **Determinism:** bitwise repeatable on one machine (A43); across environments within the path-independence bound
  (A47).
- **Noise far below the loop's tolerances:** the reactor map's iteration noise is ≤ 1.6 × 10⁻⁸ relative; a loop
  component-balance tolerance must sit above 10⁻⁷ × the reactor's throughput to be insensitive to it (M02 registers
  the C1 loop tolerances). A finite-difference sensitivity with relative input step h carries ≈ 1.6 × 10⁻⁸/h relative
  noise (≈ 2 × 10⁻⁴ at h = 10⁻⁴; M04 decides).
- **Accuracy:** the design grid's 1.0–1.4 % (NH₃) bias is a smooth function of the inputs at fixed grid, so an
  optimization at num_z = 800 is well posed for the discretized model; no finer grid is accepted by the pinned solver,
  so M07's truth check at the design point is limited to this estimate and must say so.
- **Cost:** ~9 s per cold-started solve (S1–S3) at num_z = 800 on one thread; a warm start from a neighbouring solution
  (M02's choice, ADR 0024's compatibility rules) is the expected route to cheaper loop iterations.

## 11. W22: what "validated" means for the C1 route

W22 ("one validated needed nonideal property route") is met when all of the following hold, and its verdict states
exactly what they cover:

1. **Numerical verification** of the implementation against the closed forms: M01.A05–A22 (expectations independent of
   the implementation).
2. **Conformance** with an independent implementation of the same method: M01.A37 (IDAES 2.13, the reference R-143
   names).
3. **Empirical validation of the pure-component behaviour that drives the loop**, against the reference equations of
   state (themselves fitted to experimental data): M01.A38 (NH₃ saturation pressure), M01.A39 (liquid NH₃ fugacity
   at the separator: the quantity y* is proportional to), M01.A40 (light-gas vapour fugacities). The bands (2 % in
   P_sat, 0.05 in ln φ) are the design lane's fitness statement: an error of that size moves the separator's vapour NH₃
   by at most ~5 %, the same order as the unquantified k_ij effect of §4.2 (k = 0.1 moves it 3 %), and well inside the
   difference between a kinetic and an equilibrium reactor that the v0.2 decision turns on.

W22 **cannot claim** mixture VLE validation: no open, transcribed high-pressure NH₃–H₂–N₂ dataset is in the repository.
Candidates identified (not transcribed, not read here): Larson & Black (1925), the NH₃ content of H₂/N₂ gas over liquid
NH₃ at high pressure; Michels et al. (1950, Physica 16, 831), NH₃–H₂ and NH₃–N₂ phase equilibria; Wiebe & Tremearne
(1933–34), gas solubilities in liquid NH₃ (outside the convention). Transcribing Larson & Black's gas-phase NH₃
content is the one comparison the vapour-only convention can make directly (§15 Q-F2). PR's saturated-liquid NH₃
volume is 11–30 % high (240–400 K) and its enthalpy of vaporization 2–5 % high (−7 % at 400 K): stated, not used by a
loop decision in v0.2 (no unit in the C1 journey is sensitive to liquid density; the flash's energy row uses h).

## 12. Known invalid requests (consolidated)

Provider (§5.3, §5.4): out-of-domain T or P, or a negative or non-finite flow; a liquid with light gas; a liquid where
no liquid root exists; a vapour of pure NH₃ where no vapour root exists; a metastable light-gas vapour; an undeclared
derivative; an unknown property; a state of the wrong length; a dormant state in `evaluate_phase`; a flash for another
specification, or with derivatives requested. Reactor boundary (§8.12): a non-vapour inlet; a component-set mismatch;
y_NH₃ below the trace; outside the hard domain; the provider's refusal of the inlet flash (passed through) or of an
enthalpy flow; a pressure drop above ε_P; an unaccepted reactor state; an element defect above 10⁻⁶. Each has a code,
each code an assertion (M01.A13, A14, A27, A30, A50, A51), and none returns values.

## 13. Evidence manifest catalogue (`evidence/M01/<commit>/manifest.json`)

| Check | Command | Expect |
| --- | --- | --- |
| gate | `./scripts/check.sh` | green; M01.A01, A03–A36 and A49–A52 among the tests |
| generator | `python docs/derivations/scripts/m01_reference.py --check` | exit 0 (A34) |
| records cross-check | `python -I benchmarks/m01/external_crosscheck.py --check` (its venv; pins in the script) | exit 0 (A02, A38–A40) |
| IDAES conformance | the WO-5 script in the IDAES venv (`spikes/references/idaes-requirements.lock`) | A37's record committed |
| reactor probe | `benchmarks/m01/reactor_probe.py` (its venv, pinned clone, `git archive` export) | the record of §10 (A41–A46, A48) |
| identities | the existing identity tests; `git diff --stat` on the paths of A33 | unchanged (A33) |

Status vocabulary: `implemented` (code merged), `tested` (gate and every row above pass at the commit), `reviewed`
(by the `reviewer`, never self-set), and the W22/W21 verdicts are separate (`verdict`).

## 14. Work orders (build lane, in order)

- **WO-1 Records loader.** First amend T08.A32's test as §3.5 states (the gate is red on `wp/M01` until then). Then
  load `benchmarks/m01/components.yaml` into typed C1 records (package data like SYN-001's). Gate: A01, A03, §3.5.
- **WO-2 Provider `pr-c1-v1`** (`src/openflowsheet/thermo/pr_c1.py`): §4 closed forms, §5.2–5.3 rules, derivatives of
  §4.6, `describe()` of A04. Pure Python + numpy; no new runtime dependency. Gate: A04–A14, A35, A36.
- **WO-3 Flash and the datum registry.** §5.4 flash; `thermo/conventions.py` (or equivalent) holding the
  reaction-consistent registry. Gate: A15–A24.
- **WO-4 Tests transcribing the registered states** from `reference_values.yaml` (parametrized, ids V1…F14), the
  generator `--check` in the gate, the external-crosscheck form test. Gate: A01, A02, A34.
- **WO-5 IDAES conformance run** (separate env): rebuild T08's vapour-only property block with M01's records, evaluate
  V1, V2, L1 and flash F1, F11; commit the record and its script. Gate: A37.
- **WO-6 Boundary module and stand-in** (`src/openflowsheet/models/c1/`): mapping (§8.3), projection (§8.9), pressure
  convention (§8.8), Q (§8.10), envelope and refusals (§8.12), data-domain flag, `c1.reactor_standin` (§8.13). Gate:
  A25–A32.
- **WO-7 Evidence manifest** for M01 with the catalogue of §13, `status: tested` when every row passes. A33 checked
  there.
- **WO-8 Amendment 1** (before WO-7's manifest; the rulings of §19). The design lane has already changed the generator,
  `reference_values.yaml`, and the A09, A12, A26 and A34 tests.
  1. `PrC1Provider.flash`: after the specification check and before the state-length check, a non-empty
     `request.derivatives` returns `unsupported`, `flash_derivatives_unsupported: ...` with no split. Change the
     docstring's "not offered" to "refused".
  2. Add `NotAccepted.__post_init__`: it raises `ValueError` for a stage outside `[A-Za-z0-9_]+`.
  3. Correct `models/c1/boundary.py`'s module docstring. Its sentence "each registered refusal has one defect, so the
     order decides only unregistered combinations" is false (F7's state has two). Cite §8.12's normative order and
     its reason (claim BD-06).
  4. Add the tests M01.A49, A50 and A51 (§9.10). Each state has one defect; each refusal asserts that it carries no
     values. A51 (ii) uses a provider double that delegates `describe` and `flash` to `pr-c1-v1` and refuses
     `evaluate_phase`. A49's binder half uses T08 U04's refusal path.
  5. Add the test M01.A52, a form test of `benchmarks/m01/reactor-probe.json` (§8.15), in a new module
     `tests/test_m01_reactor_probe_record.py`. It reads the record and never runs the reactor.
  6. WO-7's manifest records A49–A52, A12's and A26's amended bounds with the measured values, and A34's 88 claims.

M02 (its own brief, after M01 `tested`): the adapter that reproduces the probe (A41–A48 through the adapter), the PR
units under §7's rules, the loop.

## 15. Open questions

- **Q-F1 (needs a fact, Frank's group).** F-R3: is the inlet's Dirichlet temperature condition with axial conduction
  intended (25–33 % of the reaction heat leaves through the inlet face at the nominal point), or should the inlet be a
  Danckwerts condition? *Measurement that settles it:* the group's statement, or a 1D run with a Danckwerts inlet at a
  new pin. *Default:* use the pin as is; report the inlet-face loss in every result; M07 states it.
- **Q-F2 (needs a fact).** Mixture VLE data: transcribe Larson & Black (1925) gas-phase NH₃ contents (open access status
  to be checked) and compare y* at their states. *Default:* W22 claims pure-component validation only (§11).
- **Q-F3 (needs a fact).** The asymptotic grid-convergence order of the outlet (§10.1); *measurement:* the probe's grid
  sequence extended if the order estimate is unstable. *Default:* the design grid and its estimate of §10.
- **Q-F4 (needs a fact).** The start strategy's coverage of the hard domain (573.15–773.15 K, 5–15 MPa): M01 measured
  three inlet temperatures at 10⁷ Pa. *Measurement:* M02's adapter sweep over the hard domain's corners and centre.
  *Default:* keep the hard domain; any failure inside it is `not_converged` (typed), and M02 narrows the domain by a new
  entry if a region fails systematically. The sweep's points are defined in §8.15 (Amendment 1).
- **Q-F5 (needs a fact; Amendment 1).** The hard domain does not bound the per-tube flow (GHSV), yet the start
  strategy was measured at GHSV 1000 h⁻¹ only, and M07 chooses N_tubes. *Measurement:* M02 solves §8.15's centre point
  at 0.5 and 2 times the nominal per-tube flow. *Default:* M02 adds a per-tube-flow bound of [0.5, 2] × the nominal
  F_ret_in to the hard domain by an ADR 0027 amendment (outside it: `out_of_domain`), and widens it only on measured
  acceptance.
- **Q-N4 (needs Frank's decision — distribution).** The v0.2 wheel would ship the five C1 records (published constants
  with citations; NASA TM-4513 a U.S. Government work) as package data, ending v0.1's "no third-party data in sdist or
  wheel" (T08.A32). *Default:* ship them with their citations and rights fields; M07's release specification records
  it; if Frank declines, the provider reads the records from a user-supplied path and the wheel carries none.
- **Q-N1 (needs Frank's preference — rights).** Poling 5th ed. c_p polynomials could replace NASA TM-4513 if Frank
  wants the "properties book" source; it needs his view on redistributing book tables. *Default:* NASA (no grant needed).
- **Q-N2 (needs Frank's preference).** The F-R1/F-R2 findings and the overlay concern the group's code: Frank may prefer a
  new pin with five-species support upstream. *Default:* keep `6089593` with the subclass and the overlay.
- **Q-N5 (needs Frank's preference; Amendment 1).** Should a later schema change give `ModelManifest` a structured
  `synthetic` field (or an evidence class)? Today a synthetic model is marked in prose fields only, plus
  `identity.synthetic` in its results (§8.13). *Default:* no schema change in v0.2. Revisit only if a synthetic model is
  ever bound into `MODEL_BUILDERS`, which M02 decides (R-199).
- **Q-N3 (needs Frank's preference).** The design grid's cost/accuracy trade (§10.5). *Default:* num_z = 800 (≈ 9 s per
  solve, NH₃ 1.0–1.4 % high); 400 halves nothing that matters (6.7 s) and doubles the error.

## 16. Decisions taken in this specification

DECISION: Ω_a, Ω_b → PR 1976's rounded 0.45724 / 0.07780. Alternative: exact roots. Reversible by: a new provider
version (data hash moves; no registered identity outside M01).
DECISION: k_ij → 0 for every pair, effect stated (§4.2). Alternative: a fitted set. Reversible by: records gain k_ij rows.
DECISION: light-gas phase root → largest root with a metastability guard. Alternative: minimum-Gibbs root. Reversible by:
§5.2 and A14's U4 expectation.
DECISION: flash → equilibrium-vapour composition y* by fixed samples + bisection. Alternative: bisection on the split
from the feed (WIP). Reversible by: §5.4 (expectations unchanged at F1, F11; F5 would change).
DECISION: c_p source → NASA TM-4513 via Cantera (no rights grant). Alternative: Poling 5th ed. via `chemicals` (rights
question, Q-N1). Reversible by: replacing ten b_k per component and the data hash.
DECISION: Δ_fH → ATcT 1.112. Alternative: JANAF / NASA. Reversible by: two records.
DECISION: pressure → zero-ΔP convention, p_ret_out = P_in, ε_P = 10⁻³. Alternative: recycle compressor; inversion for
p_ret_out. Reversible by: ADR 0027 D2.
DECISION: outlet → least-squares extent projection, inerts exact, refusal above 10⁻⁶. Alternative: extent from N₂ or NH₃
alone. Reversible by: §8.9.
DECISION: duty → process side by `pr-c1-v1`; reactor keeps its kinetics, φ correlations and thermo. Alternative: PR
fugacities in the kinetics (changes the group's validated model). Reversible by: ADR 0027 D4.
DECISION: inerts in the reactor → overlay rows with N₂ transport surrogates and a CH₄ DIPPR fit. Alternative: lumping
the inerts into N₂. Reversible by: the overlay file.
DECISION: start → trace-NH₃ continuation S1–S3 with M01's polish profile. Alternative: the group's tolerance alone (0.5 %
path dependence). Reversible by: §8.7.
DECISION: data domain → flag, not refusal. Alternative: refuse outside 643–733 K. Reversible by: §8.12.
DECISION: units on `pr-c1-v1` → M02. Alternative: M01-build. Reversible by: moving WO entries.
DECISION: T08.A32 → amended for real records (§3.5), not relaxed. Alternative: keep the records out of the repository
until v0.2's release spec. Reversible by: reverting §3.5 and WO-1's test change.

Amendment 1 (§19):
DECISION: A26's defect vector and element balances → 10⁻¹³ × n_tot,in. Alternative: relative 10⁻¹² (unreachable in
binary64). Reversible by: A26 and three lines of its test (R-195).
DECISION: A12's ln φ identities → bounded by 10⁻¹² × the block's largest scaled entry. Alternative: each sum by its own
magnitude at a looser tolerance. Reversible by: A12 and its test (R-196).
DECISION: A09's permutation guard → pairwise gap ≥ 10⁻⁶ (10⁶ × A07's tolerance). Alternative: the draft's 10⁻³ at
another state. Reversible by: A09 and claim PH-GAP.
DECISION: provider request checks → ratified as built; a flash asked for derivatives → refused
`flash_derivatives_unsupported`. Alternative: ignore them as SYN-001 does. Reversible by: §5.4 step 0 (R-197).
DECISION: boundary → inlet phase checked before the hard domain; an enthalpy refusal is `error`,
`stream_enthalpy_refused`; registered `<stage>` names. Alternative: hard domain first. Reversible by: §8.12 (R-198).
DECISION: stand-in → labelled in the manifest's prose fields and `identity.synthetic`; not in the envelope at M01.
Alternative: a schema widening; listing it now. Reversible by: §8.13 (R-199).
DECISION: A47 → bitwise at the evaluation with the record's (F, y); within 10⁻⁶ through the boundary; the probe record
gate-checked (A34's hash and A52), never re-run by the gate. Alternative: bitwise through the boundary (unachievable:
the mapping is 1 ulp off). Reversible by: A47 and §8.15 (R-200).

## 17. What M01 does not establish

- **No mixture VLE validation.** The separator's y* is validated only through its pure-component ingredients (§11);
  dissolved gases are not represented (R-143).
- **Not that the reactor is right.** The reactor numbers are the group's model's outputs at the pin (regression values),
  including F-R2's φ evaluation and F-R3's inlet heat loss; nothing here compares them with experiment or with the 4TU
  dataset.
- **Not grid convergence beyond the measured sequence** (§10, Q-F3).
- **Not the stand-in's physics.** `c1.reactor_standin` is synthetic; its numbers certify the boundary code, never the
  reactor or the chemistry.
- **Not the near-critical phase behaviour.** F12 registers what the rules give; near-double-root classifications are not
  asserted; the flash's fixed samples could miss a positive excursion of h narrower than their spacing (only near T_c,EOS).
- **Not the k_ij.** k_ij = 0 is a choice with a stated effect, not a fitted or validated value.
- **Not the PR liquid density or h_vap** for any purpose beyond §11's statement.
- **Not K_NH₃ against Rossetti 2006** (R-152: a decision, not a verification).
- **Not the overlay's transport surrogates** beyond the measured sensitivity of §10.4.
- **Not reproduction across machines** of the reactor's bits (A43 is one machine; A47 states the cross-environment bound).
- **Not a structured synthetic flag in `ModelManifest`** (Amendment 1). The stand-in's manifest says SYNTHETIC in its
  prose fields; only its results carry the machine-readable `identity.synthetic` (§8.13, Q-N5). A consumer that reads
  only the manifest's structured fields cannot tell a synthetic model from another.
- **Not the order of the provider's request checks, nor its root rules at two admissible roots** (Amendment 1; §5.2,
  §5.3). Both are ratified as built. Neither is asserted, because no registered state has two defects or a
  near-double root. *(Amendment 2, review F2: what is asserted near a double root is that every returned value is a
  root of the cubic to rounding, across ±60 ulp of the review's 400 K crossing, and that the review's counterexample
  has one root and no liquid; which label a near-double pair gets is still not.)*

## 18. Corrections and the WIP note's leads, re-measured

- Dossier §6 ("the group's own reactor model already uses PR for mixture properties"): wrong at the pin — ideal-gas
  density (§8.1). The dossier is a T08 record and is not rewritten; this specification and ADR 0027 carry the correction.
- WIP 1 (mpmath PR reproduces IDAES): confirmed (claim IDAES-01; β 4.1 × 10⁻¹², previously 4.7 × 10⁻¹²).
- WIP 3 (five species; cold start fails at 5 % inerts; continuation works): five species need the F-R1 subclass in
  addition to the database rows; the registered start is S1–S3 (continuation in NH₃, not in inert fraction).
- WIP 4 (φ at the reactive-species pressure): confirmed at `ammonia_synthesis_kinetics.py:350` (F-R2).
- WIP 5 ("error at num_z = 100 ≈ +3.2 %; element-balance floor 2.2 × 10⁻⁴ grid-independent"): both measured at the
  group's loose tolerance; with S3 the element defect is ~6 × 10⁻¹⁰ and the grid study is §10.
- WIP 6 (cold start fails with real NH₃ inlet; trace works): confirmed (§8.7).
- `benchmarks/m01/reactor-probe.json` version 1 held failed solves; version 2 replaces it.

## 19. Amendment 1 (2026-10-08): rulings on the build lane's measurements

The build lane implemented WO-1 to WO-6 and measured against §9 at `f595179` / `13bcef7`. A05–A08, A10, A11, A15–A22,
A25 and A29 are worst 2.2 × 10⁻¹⁶ to 8.7 × 10⁻¹⁵, far inside their tolerances; A37 is in its record. Eight items came
back to the design lane, and a ninth came from the session's M02 recon. This amendment rules on each and changes the
text in place, marked "Amendment 1". No settled design is reopened: no closed form, registered state, expectation
value, refusal code of the draft or frozen interface changes.

| # | Item | Ruling | Reason | Where |
| --- | --- | --- | --- | --- |
| 1 | A26's defect vector at relative 10⁻¹² | Amended: 10⁻¹³ × n_tot,in for the defect vector and defect_rel. The element balances move to the same scale (10⁻¹⁵ → 10⁻¹³ × n_tot,in). The CH₄ defect is exactly 0. | The floor is the raw outlet's rounding, 2.5 × 10⁻¹¹ of the defect, so the draft's tolerance was unreachable. The element sums' worst-case float bound, 1.7 × 10⁻¹⁵, exceeded the draft's 10⁻¹⁵. | A26; BD-04, BD-05; R-195 |
| 2 | A09's "≥ 10⁻³" | Amended: gap ≥ 10⁻⁶ = 10⁶ × A07's tolerance. The build's test already asserts this. | V1's H₂/CH₄ gap is 4.35 × 10⁻⁴; a permutation still fails A07 by ≥ 4 × 10⁸. | A09; PH-GAP |
| 3 | A12 Gibbs–Duhem 1.0 × 10⁻¹³ against 10⁻¹² | Scaling changed: the ln φ identities are bounded by 10⁻¹² × M (the block's largest scaled entry). The tolerance is unchanged. | Confirmed as roundoff. The self-normalized floor at V1's N₂ column is u·M/1.0 × 10⁻⁴ ≈ 10⁻¹³, only 10× below the old bound. On M's scale the worst is 3.8 × 10⁻¹⁶. | A12; R-196 |
| 4 | No `synthetic` field in `ModelManifest` | Sufficient as built, with no schema change. §8.13 now says where the label lives, and A49 checks it. | The schema is frozen. `identity.synthetic` is the machine-readable label, and the prose prefix `SYNTHETIC:` is checkable. | §8.13, A49, Q-N5; R-199 |
| 5 | The stand-in and the v0.2 envelope | No envelope change at M01; decided at M02. | The stand-in is not bound, so T08.A20's axis is true as it stands, and U04 already refuses it (A49 checks that). If M02 binds it, it is listed as synthetic only. | §8.13, §8.14; R-199 |
| 6a | Negative or non-finite flows → `out_of_domain` | Ratified | Outside nTP-v1's state space, and the `thermo` contract answers nothing outside its domain. | §5.3, A50 |
| 6b | Unknown property → `unsupported`, `unknown_property:` | Ratified | A typed, coded refusal, as SYN-001 refuses. | §5.3, A50 |
| 6c | Wrong state length → `error`, `state_length:` | Ratified | A malformed request, not a capability or domain limit. | §5.3–5.4, A50 |
| 6d | Non-TP flash → `unsupported_specification:` | Ratified | `describe().flashes` is `("TP",)`. | §5.4, A50 |
| 6e | Flash derivatives ignored | **Replaced:** refused `unsupported`, `flash_derivatives_unsupported:` | `FlashResult` cannot carry them, so silence would read as an answer. The same provider refuses undeclared derivatives in `evaluate_phase` (A13). No caller passes them. SYN-001 is not changed (A33). | §5.4, §7, A50; R-197 |
| 6f | Enthalpy refusal at the boundary → `error`, `stream_enthalpy_refused` | Ratified | An admissible request whose answer cannot be formed; typed, carrying the provider's message, with no values. | §8.12, A51; R-198 |
| 6g | `reactor_not_accepted(<stage>)` via `NotAccepted` | Ratified. The stage grammar and the registered stages are added. | §8.12 named the code but not `<stage>`, and M02 needs both. | §8.7, §8.12, A51; R-198 |
| 6h | Two admissible roots treated as three | Ratified | f(B) = −2B² (PR-07), so two distinct admissible roots mean a double root; this is the continuous extension of the three-root rule. | §5.2; R-197 |
| 6i | Boundary check order | Ratified and made normative | No liquid exists inside the hard domain (BD-06), so checking the inlet phase first is the only order in which `liquid_at_reactor_inlet` can be returned. A30's F7 state asserts it. | §8.12, A51; R-198 |
| 7 | ADR 0026 C1's note for `interfaces-frozen.md` | Written in this amendment (§3 of that file) | One paragraph in the design lane's own document; no work order needed. | `docs/interfaces-frozen.md` §3 |
| 8 | §7 and the M02 hand-off | Made consistent | §7 states where the equilibrium row's derivatives come from. §8.14 lists what M02 inherits. Two pointers are corrected: §8.14's A45–A50 → A41–A48 and §8.5's A47 → A44. | §7, §8.5, §8.7, §8.14 |
| 9 | §8.14's A45–A50, and the M02 hand-off's completeness (coordinator) | Corrected to A41–A48; §8.15 added; A47 and §10.1 amended; A52, DX-01, Q-F5 added | See "Item 9" below. | §8.14, §8.15, A47, A52, §10.1, Q-F5 |

**Tolerances changed (old → new):**
- A26 defect vector: relative 10⁻¹² (absolute 10⁻¹⁸ on zero entries) → 10⁻¹³ × n_tot,in absolute (zero entry: exactly 0).
- A26 defect_rel: — → 10⁻¹³ (newly registered).
- A26 element balances: 10⁻¹⁵ × n_tot,in → 10⁻¹³ × n_tot,in.
- A12 ln φ homogeneity and Gibbs–Duhem: 10⁻¹² × each sum's own magnitude → 10⁻¹² × M. Symmetry: 10⁻¹² × max|·|, now stated
  as the same M.
- A09 permutation gap: "≥ 10⁻³" → ≥ 10⁻⁶.
- A47: "bitwise in the probe's environment" → bitwise at the evaluation, with the record's tube inputs, when the
  environment block is equal. 10⁻⁶ relative applies through the full boundary and in any other environment with the
  same pins. The bound is unchanged; its place is stated.

Unchanged: A26's ξ and projected outlet (relative 10⁻¹²); A12's Z, v, h homogeneity; every other tolerance.

**Generator.** `m01_reference.py` gains the claims PR-07, PH-GAP, BD-04, BD-05, BD-06 and DX-01 (82 → 88). It also
gains the YAML section `assertion_margins` and `derived_from_measured.discretization_estimate`. No `closed_form`
value moves. `--check` reproduces the files byte-for-byte.

**Item 9 (the coordinator, from the M02 recon).**
- §8.14's "A45–A50 run by M02" named assertions that did not exist. The true set is A41–A48, as §9.9 and ADR 0027
  state. It is corrected, and A49–A52 are now this amendment's in-gate assertions.
- The hand-off is completed in the new §8.15:
  - per assertion, a record half (M01, in the gate, A52) and an adapter half (M02);
  - A47 is restated at the evaluation level. A measured fact made the draft's "bitwise in the probe's environment"
    unachievable through the boundary: §8.3's mapping of the recorded n is 1 ulp off the recorded (F, y);
  - Q-F4's 17-point sweep is defined;
  - Q-F5 is new: the per-tube flow is not bounded by the hard domain;
  - the probe record is a gate-checked regression (A34's hash, plus A52), never re-run by the gate;
  - A48's estimate is now machine-readable for M02's results (DX-01), and §10.1's T_out range is corrected from
    1.3–1.7 K to 1.2–1.7 K.

## 20. Amendment 2 (2026-10-08): review findings

The design-lane review of the implementation (`docs/reviews/M01-review.md`, at `c2cf045`) found one must-fix (F1) and
four should-fixes (F2–F5), each with a prescribed fix. The build lane closed them, one commit per finding, and changed
the normative text in place, marked "Amendment 2". No closed form, registered state, expectation value, tolerance or
frozen interface changes; every registered value (A05–A11, A15–A22, A37) is bit-identical before and after (every
output of `evaluate_phase` and `flash` at the registered states compared as `float.hex`).

| Finding | Closure | Where |
| --- | --- | --- |
| F2 (should-fix): `admissible_roots` returned unconverged Newton iterates as roots within ≈ 10⁻¹⁴ of a spinodal, and `evaluate_phase(LIQUID)` answered `ok` at a state with no liquid root | A candidate is kept only if it is a root to rounding; a three-root branch left with fewer than three deflates the best-conditioned root and solves the quadratic. The review's counterexample and a ±60-ulp sweep are tests. R-197's rationale for the two-root rule is corrected (a note appended to R-197); the rule stands. | §5.2, §17; `pr_c1.py` `admissible_roots`; `tests/test_m01_provider.py::test_f2_*`; R-197 |
| F3 (should-fix): the boundary tested dormancy before the inlet's state space, so (0.5, −0.5, 0, 0, 0) and an all-zero inlet with T = NaN answered `ok` | Step 2 of §8.12's order (state space: flows finite and ≥ 0, T and P finite and > 0 → `out_of_domain`) inserted before the dormant check, in the text and in `Boundary.evaluate`. A51 (iii) is restated with a refusing-flash double, because its negative-flow state now stops at step 2; A51 (v) is new. BD-06 and A51 (iv) are unaffected: F7's state is inside the state space, so the inlet phase still precedes the hard domain. | §8.12, A51; `boundary.py` `state_space_violation`; R-198 (note) |
