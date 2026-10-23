# L01 specification — component-library gaps on the OpenIDAES-450 development half (Water first)

**Status:** Proposed, 2026-10-22; **amended** 2026-10-22 by the `reviewer` (§12: A12 bound and scope, `vapour_unstable`, T08.A32, packaging). **Amended** again 2026-10-22 by the `specifier` (§13, S04 ruling: A22's W27 clause and the library-only provider; R-566, R-567, R-569). **Author:** design lane (`specifier`), package L01, branch `wp/L01`.
**Decision record:** ADR 0043 (Proposed); register R-520…R-527; `docs/L01_DECISIONS.md`.
**Package id S04 (D1, R-565).** Manifest check ids are `S04.<label>` for this spec's `L01.<label>`.
**Generator:** `docs/derivations/scripts/l01_projection.py` (`--emit`, `--check`) → `l01_projection.json` beside it.
Every number in §3 and §6 is that record's, and the generator refuses to emit when a claim of §7 stops being true.

## 0. Read this first

1. **Water can enter the library through an existing method, but only as a vapour.** The existing non-synthetic method
   is Peng–Robinson 1976 (ADR 0026). Its only liquid regime is pure NH₃, so liquid water would need a new method
   (IAPWS-95, or a PR liquid-mixture regime). Of the 150 development cases that hold water, 3 declare a vapour-only PR
   package (`ngfc_atr` and the two `official_idaes_smr_*` cases), and all 3 are unit-blocked. The other 147 need
   another method (§3).
2. **On the development half, adding these components makes no case a `CANDIDATE`.** The projection (§6.3) moves 3
   cases from `COMPONENT_UNAVAILABLE` to `PROPERTY_ROUTE_UNAVAILABLE`: the IAPWS-95 pump variants, which now say what
   is really missing. It also removes 220 component reasons. Classes go from UNIT 184 / NOT_STEADY 32 / COMPONENT 9
   to UNIT 184 / NOT_STEADY 32 / COMPONENT 6 / ROUTE 3 / CANDIDATE 0.
3. **Identity:** nothing committed moves. The components go into a new record file and a new provider id,
   `pr-lib-v1`. The C1 files and modules stay byte-identical (§4.4, L01.A22).
4. **W27 as registered cannot judge the resulting build.** A second `cubic_pr` route is refused for two reasons: the
   provider is not registered (W27-R24 (a)) and two routes share a method (W27-R24 (d)). Separately, CO is refused
   because the archive spelling `Co` (cobalt) casefolds to the record's `CO` (W27-R24 (c)). These are findings F-1
   and F-2 (§8). L01 does not amend W27; the re-take's refusal is a registered result (L01.A24).

## 1. Authority, scope and what this establishes

Authority: Frank's L01 scope (2026-10-22) and the brief `docs/briefs/L01-specification.md`. This document must agree
with ADR 0026 (the PR method), ADR 0001 D5 and ADR 0011 D2 (reference conventions, `interfaces-frozen.md` M01
paragraph), W27 registration §5.5, §5.6 and §21 (`docs/derivations/M06-W27-registration.md`) and the C2 split
(SPLIT-R08…R11). Only the **development half** is used: the 225 ids of `split.json#/development/case_ids`. Every
all-case file is filtered to those ids before anything is counted, and no held-out row is read.

This document establishes the following:
- the disposition of each component in development-blocking order (§3);
- the library route: its records, sources, provider rules and refusals (§4);
- the identity consequences (§4.4);
- 26 numbered assertions (§5);
- the development-only re-take procedure and report format, with the projected result (§6);
- the generator's self-claims (§7), the findings (§8), the non-claims (§9), the open questions (§10) and the work
  orders (§11).

## 2. Inputs

The record's `inputs` member pins these by SHA-256: `split.json`, `case_facts.json`, `coverage.json` (the `snapshot`
member and the development rows only), `registration.json`, and `benchmarks/m01/components.yaml` (the molar-mass
anchors). The classifier is W27's own, `coverage.check_snapshot` and `coverage.classify_case`, run on development cases
only. W27's files are read and never written.

## 3. Dispositions, in development-blocking order

**Rule R-A (admission).** A component enters `pr-lib-v1` iff all of the following hold:
- it is a W27-R15 `chemical`;
- it is unavailable at the 0.2.0 snapshot;
- at least one development case lists it whose non-reaction packages are **all** `cubic_pr`, every one of them
  declaring phases within {vapor}.

Every other component is recorded as `needs new method: <the methods its development cases declare>` and stopped.
Why this rule: W27-R16 is method-blind, so a record admitted where no case's method can use it would remove component
reasons that no route can serve. That inflates availability without representing anything.

**Rule R-B (stopped by the registration).** A component that R-A admits, but whose record W27-R24 refuses, is recorded
as `stopped` with the refusal text.

The order is by number of development cases holding the CAS RN (ties by CAS). The full list of 27 chemicals is
`dispositions` in the record. This table shows the head of it, plus the cases that are blocked only by components.

| # | Component (CAS) | Dev cases | Disposition |
| --- | --- | --- | --- |
| 1 | water `7732-18-5` (H2O, water, steam, water_vapor) | 150 | **admit, vapour.** 3 cases vapour-PR-only. Not served: iapws95, watertap_aqueous, conservation_only, biochemical, aqueous_apparent_species, ideal_gas, ideal_liquid, ideal_vle, activity_coefficient, hydrometallurgy_solids, specialty_fluid, pseudo_property, unidentified (needs new method: **iapws95** first) |
| 2 | CO2 `124-38-9` | 38 | **admit, vapour** (3 vapour-PR cases) |
| 3 | NaCl `7647-14-5` | 29 | needs new method: watertap_aqueous, conservation_only. Stopped |
| 4 | O2 `7782-44-7` | 18 | **admit, vapour** (1: `ngfc_atr`) |
| 5 | benzene `71-43-2` | 15 | needs new method: ideal_vle (also iapws95, conservation_only). Stopped |
| 6 | toluene `108-88-3` | 14 | as benzene. Stopped |
| 7 | MEA `141-43-5` | 6 | needs new method: aqueous_apparent_species. Stopped |
| 8 | CO `630-08-0` | 6 | R-A admits it (3 cases). **Stopped by R-B**: W27-R24 (c), `Co`→`CO` (F-2) |
| 9 | methanol `67-56-1` | 6 | needs new method: activity_coefficient (NRTL), ideal_vle, ideal_gas. Stopped |
| 10 | sulfuric acid `7664-93-9` | 6 | needs new method: ideal_liquid (an electrolyte model in fact). Stopped |
| 11 | propane `74-98-6` | 5 | **admit, vapour** (1: `ngfc_atr`) |
| 12 | ethane `74-84-0` | 4 | **admit, vapour** (1: `ngfc_atr`) |
| — | ethylene glycol `107-21-1`, ethylene oxide `75-21-8` | 4, 3 | needs new method: ideal_liquid. Stopped |

**Not admitted, with the reason:**
- `C4H10` is `unidentified` (an ambiguous isomer, W27-R15). It is never available.
- Ions are never available (W27-R16).
- NH₃ is not copied into the library. No vapour-PR development case lists it, and copying it would bring the pure-liquid
  regime with it.
- **The method that would unblock the most development cases** is not PR. iapws95 appears in 8 cases as the only
  method and in 16 more beside others. watertap_aqueous accounts for 50 water cases. This answers the brief's
  question; choosing the next method is Frank's call (§10 Q-3).

## 4. The library route `pr-lib-v1`

### 4.1 Records

The records live in the new file `benchmarks/l01/components.yaml`, mirrored byte for byte in
`src/openflowsheet/_data/benchmarks/l01/components.yaml` and added to `openflowsheet.resources.PACKAGED`. The file holds
nine records in this identity order: **H2, N2, Ar, CH4, H2O, CO2, O2, C2H6, C3H8**.

**Format.** The format is C1's (`benchmarks/m01/components.yaml`, schema `schemas/component-record.schema.json`,
unchanged):
- the same parameter set: `critical_temperature`, `critical_pressure`, `acentric_factor`,
  `standard_formation_enthalpy`, `ideal_gas_cp_b0…b4`, and the `ideal_gas_cp_lower/upper_temperature` pair;
- the same units, `reference_convention: PR-C1-ref-v1`, and one `provenance` string per value.

**Copied records.** H2, N2, Ar and CH4 are copied from C1 with every value and provenance string unchanged (L01.A02).
One substance has one datum across routes.

**Sources for the new records.** They come from the same sources and retrieval tools as C1 (ADR 0026 D5, Frank's
dossier statement 1):

| Value | Source | Retrieval |
| --- | --- | --- |
| T_c, P_c, ω | the critical point and acentric factor of the reference equation of state. H2O: IAPWS-95 (Wagner & Pruß, JPCRD 31 (2002) 387). CO2: Span & Wagner, JPCRD 25 (1996) 1509. O2: Schmidt & Wagner, FPE 19 (1985) 175. C2H6: Bücker & Wagner, JPCRD 35 (2006) 205. C3H8: Lemmon, McLinden & Wagner, JCED 54 (2009) 3141 | chemicals 1.5.2, method `HEOS` |
| Δ_fH° (ideal gas, 298.15 K) | ATcT 1.112 (Ruscic & Bross). O2 is 0 by definition | chemicals 1.5.2, method `ATCT_G` |
| b_0…b_4, 200–1000 K | NASA TM-4513 (McBride, Gordon & Reno 1993) low-range NASA-7 set, b_k = a_{k+1}·1000^k exactly in decimal | Cantera 3.2.0 `data/nasa_gas.yaml` |
| molar mass, identifiers (CAS, InChI, InChIKey, Hill formula) | IUPAC atomic weights as tabulated by chemicals 1.5.2 | chemicals 1.5.2 |

**Cross-check.** Every new value is cross-checked against CoolProp 8.0.0, as C1's
`benchmarks/m01/components_crosscheck.py` does, into `benchmarks/l01/components-crosscheck.json`, which states every
deviation.

**Missing source.** If a source lacks a species (for example C2H6 or C3H8 is absent from `nasa_gas.yaml`, or from
ATcT 1.112), that component is **stopped with `needs a fact`**. No substitute source is used without a ruling (§10
Q-4).

### 4.2 The provider

The provider is the new module `src/openflowsheet/thermo/pr_lib.py`, provider id `pr-lib-v1`, `state_definition`
`nTP-v1`. It reads its components from the record file, in file order.

**Method (unchanged from ADR 0026).**
- D1: PR 1976 with Ω_a = 0.45724, Ω_b = 0.07780 and the 1976 κ(ω).
- D3: van der Waals one-fluid mixing with k_ij = 0.
- D4: reference convention `PR-C1-ref-v1`. h_i^ig(T) = Δ_fH°_i + ∫_{298.15}^{T} c_p,i^ig dT, and the departure is
  added.
- Derivatives are analytic: implicit through the cubic, with n-derivatives projected onto the simplex (as in
  `pr_c1.py`'s docstring).

**Phases.** VAPOR only, for every component. A LIQUID request is refused `phase_unsupported`. `flash` is refused
`flash_unsupported` (one phase kind, so there is nothing to split).

**Root rule (vapour).** The provider takes the **largest** admissible root and applies two typed refusals, in order:
1. `vapour_root_metastable`: three admissible roots exist and the smallest has the lower G^dep/RT = Σ y_i ln φ_i. This
   is ADR 0026 D2's guard, unchanged.
2. `vapour_root_liquid_like`: the chosen root has v < (Z_c/B_c)·b_mix, where Z_c/B_c is the constant of ADR 0026 D2
   and `pr_c1.py:213` (≈ 3.951). This is the new guard (R-523). For a pure component it is exactly ADR 0026 D2's single-root
   liquid test. It only ever refuses, so it cannot admit a state that C1's rules would refuse.

**Domain.** The box is C1's: T ∈ [200, 1000] K (the c_p range), P ∈ [10⁴, 3·10⁷] Pa, flows finite and non-negative.
Outside it the provider refuses `out_of_domain`.

**Refusals.** Every refusal is typed: status `unsupported` or `out_of_domain`, a message beginning `<code>:`, and no
values.

### 4.3 Exposure (conditional)

*(Amended 2026-10-23 by §14: WO-L01-3 is split. WO-L01-3a measures on a binding outside the wheel and exposes
nothing. WO-L01-3b exposes, and is held until Frank decides to ship.)*
The route is exposed only by **WO-L01-3**, and only after W27 can judge it (F-1, §10 Q-1). That work order adds:
- a `SELECTABLE_BASES` entry with `record_source = benchmarks/l01/components.yaml`;
- **no** models, so `MODEL_BASES` is unchanged and the route's `model_ids` is empty (units are out of scope);
- a `snapshot.PROVIDER_LINES` entry, with `vapor` for every component.

Until then the provider is reachable only by direct construction, and from tests.

### 4.4 Identity consequences

**Unchanged (L01.A22):**
- `benchmarks/m01/components.yaml` and its `_data` mirror;
- `thermo/pr_c1.py`, so `pr-c1-v1`'s `data_sha256` and `implementation_sha256` are unchanged;
- every `models/c1/*` module and `thermo/conventions.py`;
- every committed W27 file (`coverage.json`, `case_facts.json`, `registration.json`, snapshots);
- the journey record and the M02/M05 dumps.

**New identities:** `pr-lib-v1`'s `data_sha256` (the bytes of the new record file) and `implementation_sha256` (the
bytes of `pr_lib.py`).

**Moved by WO-L01-3 only:**
- `openflowsheet.resources.PACKAGED` (one added path);
- the binder's selectable bases. Every new registry snapshot's `snapshot_sha256` moves, which is expected: a new build
  is a new measurement. `list_models_sha256` does not move, because no models are added.

**Rejected alternative.** Appending the records to C1's file and module would do the following:
- lengthen every C1 n-vector;
- move `pr-c1-v1`'s two hashes;
- invalidate every committed v0.2 record that hashes them.

ADR 0043 records this.

## 5. Assertions

The tests are `tests/test_l01_records.py` (A01–A12), `tests/test_l01_provider.py` (A13–A21) and
`tests/test_l01_retake.py` (A22–A26). "Lit" values are in `l01_projection.json#/literature`, each with its citation,
and tolerances are in `#/tolerance`. Values marked † were transcribed by the specifier from the cited published
tables without access to the printed source in this session. §10 Q-5 asks for them to be verified. A failure of a †
value amends this document (rule 6), and the test is never bent.

**Records**
- **L01.A01** — The file's ids are exactly the nine of §4.1, in order. `reference_convention` is `PR-C1-ref-v1`. The
  `_data` mirror is byte-identical. *Exact.*
- **L01.A02** — H2, N2, Ar, CH4: every parsed value and provenance string equals the C1 record. *Exact (bitwise
  floats).* Why: one datum per substance. A drift would make the two routes' enthalpies disagree on the same stream.
- **L01.A03** — The CAS check digit is valid for all nine records. `registration.json#/components/aliases[id]` equals
  the record's CAS for each id. *Exact.* Not vacuous: `7732-18-6` and `124-38-8` fail (generator SC-5).
- **L01.A04** — The molar mass equals Σ n_e A_e/1000, with A = {H 1.00794, C 12.0107, N 14.0067, O 15.9994,
  Ar 39.948}. Expected values in kg/mol: H2O 0.01801528, CO2 0.0440095, O2 0.0319988, C2H6 0.03006904,
  C3H8 0.04409562. *Relative 10⁻¹²*:
  - floor: the decimal-to-double conversion, 1.1·10⁻¹⁶;
  - smallest error worth catching: one wrong atomic-weight digit, ≥ 10⁻⁶;
  - SC-4 proves the table reproduces C1's five molar masses exactly.
- **L01.A05** — `elemental_composition` equals the registered elements (`#/library/new[*].elements`), and
  `elemental_verification` is `VERIFIED`. *Exact.*
- **L01.A06** — Every record validates against the unchanged ComponentRecord schema. The loader refuses three
  corrupted copies, each with a typed error naming the defect: reordered ids, a `critical_pressure` in `bar`, and
  `reference_convention: X`.
- **L01.A07** † — |T_c − Lit| ≤ 0.01 K. Lit: H2O 647.096, CO2 304.1282, O2 154.581, C2H6 305.322, C3H8 369.89.
  - Floor: 0, since the record source is the same reference-EOS constant.
  - The tolerance catches a second-decimal digit slip. The closest pair of registered T_c values is 1.19 K apart, so a
    species swap is caught too.
- **L01.A08** † — |P_c − Lit|/Lit ≤ 10⁻³. Lit (Pa): 22 064 000, 7 377 300, 5 043 000, 4 872 200, 4 251 200.
  - Floor: 0.
  - Catches unit slips (×10) and errors ≥ 0.1 %.
- **L01.A09** † — |ω − Lit| ≤ 0.003. Lit: 0.3443, 0.22394, 0.0222, 0.0995, 0.1521.
  - Floor: the quoting digits of the source.
  - Catches a decimal shift (0.03443). No two registered values are within 0.003.
- **L01.A10** † — Δ_fH°:
  - O2 is exactly 0.0, registered *because* it vanishes. A10 also asserts it is non-zero for the others.
  - |Δ − Lit| ≤ 250 J/mol for H2O (−241 826) and CO2 (−393 510). These Lit values are CODATA key values; the expected
    ATcT−CODATA gap is ≤ 40 J/mol.
  - |Δ − Lit| ≤ 600 J/mol for C2H6 (−83 800) and C3H8 (−104 700), from older calorimetry.
  - Catches the liquid-water value (−285 830), kcal/kJ slips and sign errors.
- **L01.A11** † — c_p^ig(298.15 K) = R Σ b_k 0.29815^k:
  - Lit in J/(mol K): H2O 33.59, CO2 37.129, O2 29.376 (JANAF); C2H6 52.49, C3H8 73.60 (Chao, Wilhoit & Hall 1973).
  - Tolerance: relative 0.5 % (inorganic), 1 % (hydrocarbons).
  - Floor: the NASA-7 fit residual at 298 K, ≤ 0.1 %.
  - Catches a b_k scaling slip (a factor of 10³ᵏ).
- **L01.A12** — The c_p range is [200.0, 1000.0] K exactly. Each b_k equals a_{k+1}·1000^k of the low-range set in
  Cantera 3.2.0 `nasa_gas.yaml`, exactly in decimal; this is the retrieval script's check, run where Cantera is
  installed. `components-crosscheck.json` states |c_p − c_p,CoolProp|/c_p at 300, 600 and 900 K, each ≤ 0.5 %.

**Provider.** The closed-form expectations come from a new 50-digit reference generator,
`docs/derivations/scripts/l01_reference.py` → `benchmarks/l01/reference_values.yaml`, with `--check`. It is written as
M01's `m01_reference.py` is: it reads the record file and never imports the provider. Its registered states are:
- **V1L** — T = 700 K, P = 5·10⁶ Pa, n = (H2 0.30, N2 0.04, Ar 0.01, CH4 0.18, H2O 0.30, CO2 0.10, O2 0.02,
  C2H6 0.03, C3H8 0.02) mol/s. Every flow is non-zero, so a permuted index shows.
- **V2L** — T = 500 K, P = 10⁶ Pa, n = (H2O 0.90, CO2 0.05, N2 0.05, others 0). This is steam-rich with three roots
  and a stable vapour. The zero flows test infinite-dilution ln φ.
- **P1** — pure H2O, T = 500 K, P = 10⁵ Pa.

The generator refuses to emit unless V1L and V2L are admitted and P1 is admitted.

- **L01.A13** — `describe()`:
  - provider id `pr-lib-v1`, the components in file order, phases {VAPOR}, convention `PR-C1-ref-v1`;
  - the two SHA-256 values are of `pr_lib.py`'s bytes and the record file's bytes.
  - A LIQUID request and a `flash` request are refused with their codes. *Exact.*
- **L01.A14** — The C1 cross-implementation identity. At C1V (T = 700 K, P = 2·10⁷ Pa, light gases H2 0.6, N2 0.2,
  Ar 0.05, CH4 0.15) and C1W (300 K, 10⁵ Pa, equimolar four), `pr_lib` and `pr_c1` (NH3 flow 0) agree on Z, v, h,
  ln φ of the four components, and their T, P, n derivatives. Tolerance: |Δ| ≤ 10⁻¹²·max(|X|, 1).
  - Expected floor: a few ulp, since these are two double implementations of the same closed forms.
  - WO-L01-2 measures and records the maximum. If it exceeds 10⁻¹³, the work order stops and asks for a ruling.
  - Catches any difference in Ω, κ, mixing or the reference convention.
- **L01.A15** — Values at V1L, V2L and P1: Z, v, h, ln φ_i against the reference, with M01.A09's tolerance and argument.
- **L01.A16** — Derivatives (T, P, n_j) at V1L and V2L, with M01.A10's 10⁻⁹ and argument. As M01.A11 does, A16 also
  asserts that V1L's n-derivatives are all non-zero (> 10⁻¹²), so that zeros cannot meet the check.
- **L01.A17** — The water normal-boiling bracket, pure H2O at P = 101 325 Pa:
  - T = 365 K → refused `vapour_root_metastable`;
  - T = 385 K → admitted.
  - Independent fact: IAPWS-95 T_b = 373.124 K.
  - Measured with the Lit constants of A07–A09 (specifier's double-precision closed form): PR places its saturation at
    374.53 K. Each state is ≥ 9.5 K from it. An error in ω of 0.1 shifts it by about 6 K.
  - Catches a wrong ω or T_c, or a missing guard.
- **L01.A18** — The liquid-like guard, and its non-vanishing counterpart:
  - pure H2O at 300 K, 5·10⁶ Pa → refused `vapour_root_liquid_like` (a single root with v/b = 1.12 < Z_c/B_c ≈ 3.951;
    water there is compressed liquid);
  - pure CO2 at 250 K, 5·10⁶ Pa → refused `vapour_root_liquid_like` (v/b = 1.52);
  - P1 admitted, with |Z − 0.9958| ≤ 0.002. 0.9958 is the IAPWS-IF97 table value at 0.1 MPa, 500 K (†). PR gives
    0.99620. The ideal-gas fallback (Z = 1) and a dropped a-term (Z ≈ 1.0006) both fall outside the band.
- **L01.A19** — The metastability guard in mixtures:
  - H2O 0.95 / N2 0.05 at 330 K, 10⁵ Pa → refused `vapour_root_metastable` (the water partial pressure is 5.5× its
    vapour pressure);
  - the same mixture at 400 K → admitted;
  - pure C3H8 at 300 K, 1.5·10⁶ Pa → refused `vapour_root_metastable` (P_sat ≈ 1.0 MPa).
- **L01.A20** — The domain: T = 199.5 K, T = 1000.5 K and P = 3.1·10⁷ Pa are each refused `out_of_domain`, with no
  values.
- **L01.A21** — The identities of M01.A12 at V1L and V2L, with the same tolerances: homogeneity, Gibbs–Duhem, and
  symmetry of n_tot ∂ln φ_i/∂n_j.

**Identity and re-take**
- **L01.A22** — The C1 files are untouched:
  - `git diff b843941..HEAD` over the files and modules §4.4 lists as unchanged is empty;
  - `pr_c1.describe()`'s two SHA-256 values equal their values at `b843941`;
  - the M01, M02, M05 and W27 pin tests pass unmodified.
- **L01.A23** — `l01_projection.py --check` exits 0, so SC-1…SC-13 hold.
- **L01.A24** *(amended by §14.4: it is now the registration-version-1 control)* — Before W27 can judge two `cubic_pr`
  routes, the re-take (§6) on a build that exposes `pr-lib-v1` behaves as follows:
  - it exits 2;
  - it prints `REFUSED:` and the W27 refusal text containing `unregistered provider ids ['pr-lib-v1']` (or, with the
    provider row added, `routes sharing a method ['cubic_pr']`; both are proven by SC-11);
  - it writes no file and prints no count.
- **L01.A25** — After F-1 is resolved, the re-take's development classes equal the projection's (§6.3), and each
  case's removed component reasons equal the projection's `transitions`. Any difference in unit reasons is listed per
  case with its W27-R62 cause (the library route has no models). If a class differs, it is a finding, not a pass.
- **L01.A26** — The re-take's output holds only development ids: the script asserts this before writing, and a test
  re-checks it. The bytes of `benchmarks/m06/openidaes450/coverage.json` are unchanged by a run.

## 6. The development-only coverage re-take

### 6.1 Why not the brief's command

`python -m benchmarks.m06.w27.coverage` has two problems for this package (F-3):
- with no `--out` it **overwrites the committed `coverage.json`** (`coverage.py:596`);
- it always prints the all-450 class counts (`:612`), which would count held-out rows.

L01 does not run it.

### 6.2 Procedure (WO-L01-3: `benchmarks/l01/retake.py`)

*(Amended by §14.3: steps 2–7 run on the measurement binding under registration version 2, and the output goes to
`evidence/S04/`.)*

1. Load the development ids. Filter `case_facts.json` to them **before** any other step.
2. Build the snapshot with `snapshot.build_snapshot()` from the installed build.
3. Run `coverage.check_snapshot(snapshot, {"cases": dev_cases})`. A `RefusalError` prints `REFUSED: <text>`, exits 2
   and writes nothing (L01.A24).
4. Run `classify_case` for each development case.
5. Compute the "before" rows the same way, from the committed `coverage.json#/snapshot`. Assert that they equal the
   committed development rows, as SC-2 does.
6. Write `evidence/L01/<commit>/retake.json` with the members `schema` (`l01-retake-v1`), `snapshot_sha256`,
   `inputs`, `before` and `after` (the §6.3 tally form), `transitions` (as in the record) and
   `unit_reason_differences`.
7. Print one line: `L01 re-take (development, 225): <after classes>; CANDIDATE <before>→<after>`.

### 6.3 Report format and the projected values

The report gives:
- a before/after class table;
- reason-kind totals;
- component reasons removed, by subject;
- the per-case transitions.

The projection below is the "hypothetical" reading: the new records are admitted vapour-only by the one `cubic_pr`
route. It is the reading W27 can judge today. Unit reasons are not projected.

| Class | before | projected |
| --- | --- | --- |
| UNIT_UNAVAILABLE | 184 | 184 |
| NOT_STEADY_STATE_SIMULATION | 32 | 32 |
| COMPONENT_UNAVAILABLE | 9 | 6 |
| PROPERTY_ROUTE_UNAVAILABLE | 0 | 3 |
| CANDIDATE | 0 | 0 |

- **Reason totals.** COMPONENT reasons go from 832 to 612. Route reasons stay at 314, and unit reasons at 621.
- **Removed, by subject:** H2O 139, CO2 38, O2 16, water 9, C2H6 4, C3H8 4, water_vapor 4, steam 3, oxygen 2,
  propane 1.
- **Class changes:** only `variant_idaes_iapws_pump_dp{200k_eff75, 600k_eff75, 800k_eff85}`, which go from COMPONENT
  to ROUTE (`no_route:iapws95`).
- **Transitions.** 157 cases record at least one change.

## 7. Generator self-claims (`l01_projection.py`; it refuses to emit if any fails)

- **SC-1** — 225 distinct development ids, each with facts and a committed row.
- **SC-2** — W27's classifier at the committed snapshot reproduces every committed development row.
- **SC-3** — The before tally is UNIT 184 / NOT_STEADY 32 / COMPONENT 9.
- **SC-4** — The atomic weights reproduce C1's five molar masses exactly, and every CAS check digit is valid.
- **SC-5** — The CAS check is not vacuous.
- **SC-6** — R-A agrees with the registered library: admitted, or stopped by R-B.
- **SC-7** — Every library id is aliased to its CAS, and the projection snapshot passes W27-R24.
- **SC-8** — No class worsens, and only COMPONENT reasons disappear.
- **SC-9** — There is no CANDIDATE, and every case served via a library component keeps a UNIT reason, so its class
  does not depend on which route's models judge it.
- **SC-10** — The projected tally is the one in §6.3.
- **SC-11** — The two-route build is refused for both W27 reasons.
- **SC-12** — The literature table covers exactly the new records.
- **SC-13** — CO's record is refused by W27-R24 (c) exactly as registered.

## 8. Findings (for other documents; not written here)

- **F-1 (W27 §21, W27-R19, W27-R24 (a)/(d), W27-R63).** A second route of an existing method cannot be judged.
  Judging it needs W27 Amendment 3, which would add three things:
  - a `provider_methods` row `pr-lib-v1 → cubic_pr`;
  - a `PROVIDER_LINES` entry;
  - a serving rule for several routes per method. Recommended: a group is served iff **some** route of its method
    serves it, and its units are judged on the serving route with the fewest unit reasons (ties by provider id).
- **F-2 (W27-R24 (c)).** The spelling check casefolds, so the record `CO` collides with the archive's `Co` (cobalt) in
  development data, and the whole snapshot is refused. The fix belongs to W27: match formulas case-sensitively, or
  register `Co` as a distinct element. CO stays stopped until then.
- **F-3 (brief).** The brief's re-take command would overwrite a committed W27 record and print held-out counts
  (§6.1).

## 9. What this does not establish

- **No coverage gain.** No development case becomes runnable, and no CANDIDATE count moves. The projection is a
  reading, not a measurement of a build.
- **No liquid water,** and no water property outside 200–1000 K. Reformer outlets above 1000 K are refused.
- **No accuracy claim for PR on water** beyond the A17/A18 bands. PR is not IAPWS-95, and nothing here validates
  steam-cycle cases.
- **Nothing about held-out cases,** and no generalisation beyond the development half (C2 R-494).
- **No k_ij.** The mixtures' phase behaviour (water-gas dew points) carries ADR 0026 D3's k_ij = 0 error, which is
  unquantified for these pairs.
- **The † values are transcriptions,** not verified against the printed sources (§10 Q-5).

## 10. Open questions (each with a recommended default)

- **Q-1** *needs the user's preference.* Who amends W27 (F-1, F-2), and when? **Default:** a separate design-lane
  package, W27-A3. L01 builds WO-1 and WO-2 now, and holds WO-3 until then.
- **Q-2** *needs the user's preference.* Build L01 at all, given there is no development gain? **Default:** yes, but
  only WO-1 and WO-2. They are cheap, they move nothing committed, and the SMR and ATR unit work will need them.
- **Q-3** *needs the user's preference.* Which new method next? **Default:** IAPWS-95, the largest dependency of water
  cases. It is not started without a scope decision.
- **Q-4** *needs a fact.* Are C2H6 and C3H8 in Cantera 3.2.0 `nasa_gas.yaml` and in ATcT 1.112 (chemicals 1.5.2)?
  The fact is settled when WO-1's retrieval runs. **Default:** if either is absent, stop that component and record
  `needs a fact`; no substitute source.
- **Q-5** *needs a fact.* Verify the † values against the printed sources (JANAF 4th ed., CODATA 1989, the
  reference-EOS papers). **Default:** the assertions stand as registered. A failure amends §5, and the test is not
  changed.
- **Q-6** *needs the user's preference.* Add the NASA-7 high range (1000–6000 K) so that reformer states can be
  evaluated? **Default:** no. It is a record-format extension and belongs in its own ADR when a unit needs it.

## 11. Work orders (`opus-engineer`, about 120k context each)

- **WO-L01-1 — Records.** Branch `wp/L01`. Needs chemicals 1.5.2, Cantera 3.2.0 and CoolProp 8.0.0; take it on the
  workstation, or in a session whose proxy allows pip.
  - Write `benchmarks/l01/components.yaml` (§4.1), its `_data` mirror and the `PACKAGED` path.
  - Write a retrieval and cross-check script, `benchmarks/l01/components_crosscheck.py` with `--check`, and its
    `components-crosscheck.json`.
  - Write `tests/test_l01_records.py` for A01–A12.
  - Stop a component (Q-4) rather than substitute a source.
  - Done when A01–A12 pass and A22 passes for the record files.
- **WO-L01-2 — Provider.**
  - Write `src/openflowsheet/thermo/pr_lib.py` (§4.2), with `pr_c1.py` untouched; it must not import `pr_c1`'s
    private names.
  - Write `docs/derivations/scripts/l01_reference.py` (50 digits, `--check`, ruff-clean) →
    `benchmarks/l01/reference_values.yaml`.
  - Write `tests/test_l01_provider.py` for A13–A21, and record A14's measured floor in the build-decisions log.
  - Done when A13–A21 and A22 pass. It then gets the design-lane `reviewer` pass (it touches phase logic and
    derivatives).
- **WO-L01-3 — Exposure and re-take** (held until Q-1 is resolved). *Superseded by §14: WO-L01-3a is the re-take,
  and WO-L01-3b is the exposure.*
  - the binder basis and the snapshot line (§4.3);
  - `benchmarks/l01/retake.py` (§6.2) and `tests/test_l01_retake.py` for A23–A26.
  - Before W27-A3 only A24 is runnable, and its refusal is the registered result.

## 12. Amendment 1 (2026-10-22, design lane `reviewer`; `docs/reviews/L01-review.md`; R-528, R-529, R-540, R-541)

This section supersedes the text it names. Every other part of the document is unchanged.

### 12.1 L01.A12's c_p cross-check: the bound is 2 % and it covers all nine records (R-528)

This replaces A12's last sentence: "`components-crosscheck.json` states |c_p − c_p,CoolProp|/c_p at 300, 600 and
900 K for **every record of the file**, each ≤ **2 %**."

Why the registered 0.5 % was wrong:
- **Floor.** The bound compares two independent evaluations of ideal-gas c_p: the NASA TM-4513 fit and the reference
  EOS's ideal part. Its floor is their disagreement on correct data. §5 derived none (A04 and A07–A11 each state one).
  The same retrieval chain measured that disagreement:
  - M01 §3.3 (R-158 "Watch for"): CH4 1.12 % at 1000 K and NH3 0.51 %, on records accepted as correct;
  - this package's JSON: CH4 −0.47 %, +0.45 % and +0.68 % at 300, 600 and 900 K. L01.A02 requires that record to be
    bitwise C1's.

  A bound below its floor fails correct data, and C3H8's +0.577 % at 600 K is within that floor.
- **Smallest error worth catching.** The cross-check is the only identity check that is independent of the retrieval
  source. A wrong species key in `nasa_gas.yaml` would pass the exact-decimal check.
  - The closest species swap, a new record against any of the nine and taken as the largest deviation of the three
    temperatures, is O2/N2 at 6.5 %.
  - A 10^{3k} scaling slip is off by orders of magnitude.
  - Digit slips are the exact-decimal check's job. A one-unit slip in a b_k's leading digit moves c_p by ≥ 1.03 %, and
    in its second digit by ≥ 0.10 %. The 0.5 % bound did not catch the second kind either.
- **Bound.** 2 % sits about 3× above the measured floor (0.68 %) and about 3× below the closest swap (6.5 %).

Scope: all nine records. With one rule per file, the copied four meet it too (max 0.68 %). Restricting A12 to the new
five was a narrowed denominator. The comparand is unchanged, and C3H8 is not stopped.

### 12.2 Quoted numbers (no assertion changes) and O2's critical point

- A18: CO2 at 250 K and 5·10⁶ Pa has v/b = **1.515** (`reference_values.yaml`: 1.51462); the quoted "1.52" is replaced.
- A19: "the water partial pressure is **5.5× the measured (IAPWS-95) vapour pressure at 330 K, 17.2 kPa, and 6.14× PR's
  own, 15 482 Pa**". As §12.3 shows, this guard is not a supersaturation guard for mixtures. The state is refused
  because it is 95 % water.
- A07 (O2): the record's T_c and P_c (154.581 K, 5.043 MPa) are the parameters that Schmidt & Wagner state and that
  chemicals' `HEOS` returns, and they are A07's comparand. They stand. CoolProp's computed critical point of that EOS
  (154.5994 K, 5.04641 MPa) is a cross-check statement. It moves PR's a_c and b by ≤ 7·10⁻⁴, far below PR's own error.

### 12.3 The vapour rule gains a third refusal, `vapour_unstable` (R-540)

The defect: ADR 0026 D2's guard compares two roots of one composition. For a mixture that is not a stability test.
Measured at `ca7213b`:
- a cooled reformer outlet (H2 0.45, N2 0.15, CH4 0.02, H2O 0.30, CO2 0.08; 313.15 K, 3 MPa) is answered `ok` VAPOR,
  with water at about 100× the fugacity of pure liquid water;
- H2O 0.6 / N2 0.4 at 330 K and 10⁵ Pa is answered `ok`.

**Rule.** This adds a third item to §4.2's root rule. After `vapour_root_metastable` and `vapour_root_liquid_like`,
the provider refuses `vapour_unstable` when some component i with 0 < y_i < 1 has tm_i < −10⁻¹⁰, where

  tm_i = ln φ_i^pure(T, P) − ln y_i − ln φ_i(T, P, y; Z_V),

- ln φ_i^pure is the smallest ln φ_i over the admissible roots of the pure-i cubic at (T, P), that is its stable root,
  because a pure phase has G^dep/RT = ln φ;
- Z_V is the chosen (largest) root.

The message is `vapour_unstable: pure-<id> trial phase tm = <tm> < 0 at <T> K, <P> Pa`. No values or derivatives are
returned.

**Derivation.**
- Michelsen's tangent-plane distance of a trial phase w, over RT, is
  tm(w) = Σ_k w_k [ln w_k + ln φ_k(w) − ln y_k − ln φ_k(y)]. If tm(w) < 0 for any w, the phase y is unstable: forming
  a phase of composition w lowers G. With w = e_i, tm(w) is tm_i.
- For y = e_i, tm_i = G^dep/RT(stable root) − G^dep/RT(Z_V). This is < 0 iff the smallest root is the stable one,
  which is exactly D2's guard, and that guard has already refused. The rule therefore extends D2 to mixtures over
  pure-component trial phases.
- It only refuses, it is closed form with no iteration, and the derivatives of an admitted state are unchanged.
- **Threshold.** The rounding error of tm_i is ≤ about 10⁻¹³ (four double terms, |ln φ| ≤ 50). 10⁻¹⁰ is 10³ above
  that. An instability with |tm| < 10⁻¹⁰ has a condensation driving force e^{10⁻¹⁰} − 1, which is immaterial.

**States.** The registered admitted states keep their status: min tm is 1.19 (V1L), 0.105 (V2L), 0.051 (A19 400 K),
0.51 (C1V) and 1.39 (C1W), and it is exactly 0 for pure P1 and A17 385 K. The generator registers three refused states
(the two above, and C3H8 0.5 / N2 0.5 at 250 K and 10⁶ Pa, tm = −0.62), each at tm ≤ −0.5. It also registers the
mixture pair of the liquid-like guard (CH4/C2H6 50/50 at 350 K: 1.5·10⁷ Pa admitted at v/b_mix = 4.13; 2·10⁷ Pa
refused at 3.16). That pair's classification flips if b_mix is replaced by the smallest or the largest b_i present.

**§9 is corrected.** The bullet "No k_ij" now reads: "No k_ij, and no full phase-stability test. A VAPOR answer is
certified stable only against pure-component trial phases (§12.3). A vapour that is unstable only towards a mixed
liquid, for example a C2H6–C3H8 condensate with no component supersaturated on its own, is not detected. Dew points
also carry ADR 0026 D3's k_ij = 0 error." ADR 0043 D5 carries the same addition.

### 12.4 T08.A32 amended for a second vetted record file (R-529)

T08.A32, as amended by M01 §3.5 (R-158), becomes the following. It is amended for real records, not relaxed.
- A `synthetic: true` record keeps the v0.1 rule unchanged.
- A `synthetic: false` record must meet all of these:
  - (i) resolve, as a symlink resolves to its single copy, to a file registered as a **vetted record file**, and
    carry one of that file's registered ids. The registry is:
    - `benchmarks/m01/components.yaml`: H2, N2, NH3, Ar, CH4, vetted by `benchmarks/m01/external-crosscheck.json`;
    - `benchmarks/l01/components.yaml`: H2, N2, Ar, CH4, H2O, CO2, O2, C2H6, C3H8, vetted by
      `benchmarks/l01/components-crosscheck.json`;
  - (ii) carry `identifiers` with `cas`, `inchi` and `inchikey`;
  - (iii) carry non-empty `rights.source` and `rights.redistribution`, and a `provenance` on every parameter and on
    the molecular weight;
  - (iv) be covered by its file's retrieval equality:
    - for M01, M01.A02 as now;
    - for L01, all 13 `retrieval[id].equal` flags, `retrieval_all_equal`, the id absent from `retrieval_failures`, and
      the JSON's `records_sha256` equal to the SHA-256 of the file's bytes. This is new and stricter: the vetting must
      be of these bytes;
  - (v) where an id appears in more than one vetted file, be the same whole record mapping in each (one datum per
    substance; L01.A02).
- The set of real (file, id) pairs equals the registry's, with each pair counted once.
- Adding a file to the registry takes a design-lane amendment that names its vetting.

**Not decided here: rights.** (iii) checks that a rights statement exists. Whether the statement is correct, and
whether any of these records ships in an sdist or wheel, is Frank's decision (M01 Q-N4, L01-Q4). T08.A32's "no
third-party data in sdist or wheel" stays as M01 §3.5 left it, a release-time question.

### 12.5 Packaging moves with WO-L01-3, after L01-Q4 (R-541)

§4.4 prevails over §4.1 and §11. The `PACKAGED` path, its `_data` link, the `pyproject.toml` package-data line, the
T08 inventory pattern and the packaged-file count are all added by WO-L01-3, and only after Frank has answered L01-Q4.
Until then the provider reads the checkout copy (`load_records`'s fallback). L01.A01's mirror clause becomes "until
WO-L01-3, `benchmarks/l01/components.yaml` is not in `PACKAGED` and has no `_data` copy". The reason is that nothing
packaged can reach the records before exposure, and L01-Q4's default is that nothing from L01 is released before the
rights review.

## 13. Amendment 2 (2026-10-22, design lane `specifier`, S04 ruling; `docs/briefs/S04-ruling.md`; R-566, R-567, R-569)

This section supersedes the text it names. Every other part of the document is unchanged. Every assertion below is an
exact comparison of strings, sets or SHA-256 values; no tolerance applies.

### 13.1 Why A22 changed (measured at `e46eb97`, `wp/S04` = `wp/L01` + `wp/D1`)

- `git diff b843941 e46eb97` over the 19 paths of `PINNED` in `tests/test_l01_records.py` changes one file,
  `benchmarks/m06/openidaes450/coverage.json`, in 3 lines: `snapshot.git_commit`, `snapshot.package_version` and the
  top-level `snapshot_sha256`. Its SHA-256 goes from `b69626c7…` to `aa89cdd6…`. The change is C7's W27 re-take
  `f85fcd7` (R-460), which reached the S04 line through the merge `0c277b0`.
- `git log --first-parent --no-merges b843941..e46eb97 -- <the 19 paths> benchmarks/m06/` is empty, so no commit on
  the L01 line touches these files.
- The re-taken file's `rows` and `summary` equal those at the base, blob `dea968a2…`, which is the blob C2 pins
  (R-555). Its snapshot routes are `syn001` and `pr-c1-v1`, and its bytes contain neither `pr-lib-v1` nor
  `benchmarks/l01/`.

A22's byte pin therefore failed for a cause that is not L01's. R-460 rewrites W27's `coverage.json` at every version
bump, so a byte pin held by a package that does not own the file fails at every bump. R-555 removed the same failure
from C2. The rule is R-567: a package byte-pins only files that no registered procedure rewrites.

### 13.2 L01.A22 as amended (R-566)

Replace L01.A22 with:

- **L01.A22** — L01 moves no C1 or W27 identity.
  - (a) The 18 files of §4.4 that no registered procedure rewrites hash to their `PINNED` SHA-256 values, which are
    unchanged. These are `benchmarks/m01/components.yaml`, `thermo/pr_c1.py`, `thermo/conventions.py`, the 13
    `models/c1/*.py`, `case_facts.json` and `registration.json`. `models/c1/` holds exactly the pinned modules, and the
    packaged C1 records hash as `benchmarks/m01/components.yaml`. `coverage.json` leaves `PINNED`.
  - (b) L01's absence from W27's committed coverage. A helper `w27_absence_problems(data: bytes) -> list[str]`
    reports:
    - `pr-lib-v1` occurring in the bytes;
    - `benchmarks/l01/` occurring in the bytes;
    - `pr-lib-v1` among `[r["provider_id"] for r in snapshot["routes"]]`;
    - `pr-c1-v1` absent from that list. This is the control: it shows that the list is populated and that it is the
      list `pr-lib-v1` would join.
    The helper returns `[]` on the committed `coverage.json`.
  - (c) L01's absence from the live build. `{b.provider_id for b in revision_binding.SELECTABLE_BASES}` contains
    `pr-c1-v1` and does not contain `pr-lib-v1`. W27's snapshot reads that table (W27-R63). The W27 pin test
    `test_committed_coverage_json_is_g14_and_this_builds_classification` holds the live snapshot equal to the
    committed one, apart from `git_commit`, so it carries (b) over to the build.
  - (d) `pr_c1.describe()`'s two SHA-256 values equal the pinned ones. This clause is unchanged.
  - (e) The M01, M02, M05 and W27 pin tests pass unmodified. This clause is unchanged.
  - (f) Review-time, not a test: `git log --first-parent --no-merges b843941..HEAD -- <(a)'s 18 files>
    benchmarks/m06/` is empty on `wp/S04`. A merge from `main` may bring a registered re-take, and that re-take is not
    L01's. The command was measured empty at `e46eb97`.
- **Negative controls, in the test:**
  - The committed document with a route `{"provider_id": "pr-lib-v1", "components": [], "model_ids": []}` appended,
    serialized with `json.dumps`, gives exactly 2 problems: the bytes and the route.
  - The document with the `pr-c1-v1` route removed gives exactly 1 problem: the control.
- **What (b) and (c) catch:**
  - a W27 re-take on a build that exposes `pr-lib-v1`, caught by (b);
  - exposure without a re-take, caught by (c) and by the W27 pin test;
  - a hand edit of the rows, caught by the W27 pin test, whose re-classification must reproduce them.
- **What they deliberately do not catch:** a re-take that moves only `git_commit`, `package_version` and
  `snapshot_sha256`. Those fields are not identity (R-460, R-555).

### 13.3 Validity and retirement

(b) and (c) hold until WO-L01-3, which runs only after W27 Amendment 3 (F-1). The commit that adds `pr-lib-v1` to
`SELECTABLE_BASES` replaces (b) and (c) with the identity statement that W27 Amendment 3 registers. The same commit
takes the steps of §13.4.

### 13.4 Addition to §4.3: until WO-L01-3, `pr-lib-v1` is a library-only provider (R-569)

`pr-lib-v1` is a library-only provider under T08 release spec §5.7, Amendment S04.
- S04's limitations about it are harvested E → `U02`, each with a note that names `` `pr-lib-v1` `` and
  `library-only`. No L-row is written for it.
- A revision cannot select it. `record_source: benchmarks/l01/components.yaml` selects SYN-001's basis, whose
  `provider_id` is `syn001`, and the library's components are then refused `RevisionError` `components_unsupported`
  (kind `unsupported`). This was measured at `e46eb97` for `[H2O, N2]` and for `[H2, N2, Ar, CH4, H2O]`.

The commit of WO-L01-3 that adds the `SELECTABLE_BASES` entry also does the following:
- adds `pr-lib-v1` to the envelope's `property_model.providers`, with an `other_basis_providers` row that carries its
  limitation L-row and a caveat;
- writes its L-rows;
- reclassifies S04's `U02` items;
- removes `pr-lib-v1` from `LIBRARY_ONLY_PROVIDERS`.

### 13.5 What this amendment does not establish

- It does not rule F-1, W27 Amendment 3, L01-Q1, L01-Q4 or the timing of WO-L01-3.
- (b) is not a check of W27's content. W27's rows and classes are held by W27's own tests and by C2's SPLIT-A18 and
  A19 (R-555), not by L01.
- C2's strict pins on `case_facts.json` and `sample.json` stand.

## 14. Amendment 3 (2026-10-23, design lane `specifier`, ruling round D2; R-615): WO-L01-3 is split into a measurement now and exposure later

### 14.1 What changed

- **W27 can now judge the route.** W27 registration version 2 (C9, `docs/derivations/W27-registration-v2.md`,
  R-570…R-574) judges a build with two `cubic_pr` routes when the classifier is called with `registration_version=2`
  (W27v2-R01, `benchmarks/m06/w27/coverage.py` `check_snapshot` and `classify_case`). §10 Q-1 and F-1 are resolved by
  it.
- **Frank keeps the records unshipped.** On 2026-10-23 (`docs/C12_DECISIONS.md`, last entry) he ruled that the nine
  `pr-lib-v1` records stay out of every release, and that shipping starts with a clean-up package.
- **The coupling.** WO-L01-3 as written (§4.3, §4.4, §12.5, §13.3, §13.4) ties the measurement to exposure: a
  `SELECTABLE_BASES` entry, the `PACKAGED` path, `_data`, `pyproject.toml`, the T08 inventory and the envelope rows.
  Exposure contradicts Frank's ruling.
- **The measurement does not need exposure.** `snapshot.build_snapshot` takes the binder as an argument (`binding`,
  `benchmarks/m06/w27/snapshot.py:222`). It reads only four things from it: `SELECTABLE_BASES`, `MODEL_BASES`,
  `MODEL_BUILDERS` and `basis_provider` (`:148–197`).

### 14.2 Ruling

WO-L01-3 is split in two.
- **WO-L01-3a, the development-half re-take on a measurement-only binding (§14.3).** It runs now, on the workstation,
  where `docs/V02_STATE.md` places the re-take.
- **WO-L01-3b, exposure.** It covers everything §4.3, §4.4 ("Moved by WO-L01-3 only"), §12.5, §13.3 and §13.4 assign
  to WO-L01-3, except the snapshot line, which 3a adds. It is held until Frank decides to ship and the clean-up package
  has landed. It then runs on the cleaned records and re-takes 3a's measurement on them (§14.5).

### 14.3 WO-L01-3a (build lane, `opus-engineer`, about 80k context; branch `wp/S04-retake`)

**Changes it may make:**
1. **The snapshot line.** In `benchmarks/m06/w27/snapshot.py`, add `PROVIDER_LINES["pr-lib-v1"]`, W27v2-R03's line:
   - the records come from `registration.ROOT / pr_lib.RECORDS_PATH`, in file order;
   - every component is `["vapor"]`.

   `benchmarks/` is outside `src`, so this is not in the wheel. A binder with no `pr-lib-v1` basis never calls it.
2. **The re-take script, `benchmarks/l01/retake.py`** (§6.2, as amended here).
   - **The measurement binding.** The script creates a `types.ModuleType("l01_measurement_binding")` with:
     - `SELECTABLE_BASES`: `tuple(revision_binding.SELECTABLE_BASES)`, followed by one `ComponentBasis` for
       `pr-lib-v1` over the nine record ids in file order, built as §4.3's entry would be;
     - `MODEL_BASES` and `MODEL_BUILDERS`: `revision_binding`'s, unchanged, so the route's `model_ids` is empty;
     - `basis_provider(b)`: `pr_lib.PrLibProvider()` for that basis, and `revision_binding.basis_provider(b)` otherwise.

     Nothing under `src/openflowsheet` constructs or imports it.
   - **§6.2 step 2** becomes `snapshot.build_snapshot(binding=<the measurement binding>)`.
   - **Steps 3–5** pass `registration_version=2` to `check_snapshot` and `classify_case`. Step 5's "before" rows come
     from the committed `coverage.json#/snapshot` under version 2. By W27v2-R10 they equal version 1's, and step 5
     asserts that they equal the committed development rows.
   - **The command line** takes `--registration-version {1,2}`, default 2. Version 1 is A24's control.
   - **Step 6** writes `evidence/S04/<commit>/retake.json`. This replaces `evidence/L01/`, under R-565's renumbering.
     Beside §6.2's members it carries:
     - `registration_version`: `2`;
     - `binding`: `"measurement-only: pr-lib-v1 added to the installed binder's SELECTABLE_BASES inside
       benchmarks/l01/retake.py; not selectable in this build (L01 §14)"`;
     - `selectable_in_build`: `false`;
     - `pr_lib_data_sha256` and `pr_lib_implementation_sha256`, from `PrLibProvider().describe()`.
   - **Step 7's printed line** gains `(measurement-only binding, W27 v2)`.
3. **`tests/test_l01_retake.py`**, for A23–A27 as amended in §14.4, and for W27v2-A23.

**What it must leave unchanged** (A27 asserts these, or an existing test already does):
- `openflowsheet.resources.PACKAGED`, the `_data` mirror, the `pyproject.toml` package-data list, the T08 inventory
  pattern and the packaged-file count;
- `revision_binding`: `SELECTABLE_BASES`, `MODEL_BASES` and `basis_provider`;
- the T08 envelope's `property_model.providers` and `LIBRARY_ONLY_PROVIDERS` (`pr-lib-v1` stays in it), S04's `U02`
  items and every L-row;
- `benchmarks/m06/openidaes450/coverage.json` and every committed W27 file (A26).

L01.A22 (b) and (c) and R-569 therefore keep holding, and §13.3's retirement does not run.

### 14.4 The assertions, as amended

- **L01.A23**: unchanged.
- **L01.A24 is amended: it is the control, not the result.** `retake.py --registration-version 1` on the measurement
  binding must:
  - exit 2;
  - print `REFUSED:` and text containing `unregistered provider ids ['pr-lib-v1']` (W27v2-A09, on the real build);
  - write no file and print no count.

  *Why it stays:* it shows that the version 1 path still refuses the two-route snapshot, so no default can reach the
  version 2 result by accident.
- **L01.A25 is the measurement.** Under version 2:
  - the development classes equal §6.3's projection;
  - each case's removed component reasons equal the projection's `transitions`;
  - any difference in unit reasons is listed per case with its W27-R62 cause.

  A class difference is a finding. It goes in the S04 build-decisions log and is escalated, and the design lane
  amends the projection. The test is never bent to fit.
- **L01.A26**: unchanged.
- **W27v2-A23** (W27 v2 §10 assigns it to WO-L01-3). On the measurement snapshot, the `pr-lib-v1` route's
  `components` equal `registration_v2.json#/snapshots/S2/routes/1/components`.
- **L01.A27 (new): the measurement does not expose.** At 3a's commit, all of the following hold:
  1. no basis in `revision_binding.SELECTABLE_BASES` has `provider_id == "pr-lib-v1"`;
  2. `snapshot.build_snapshot()`, called with no binding, has no `pr-lib-v1` route;
  3. no `openflowsheet.resources.PACKAGED` path starts with `benchmarks/l01/`;
  4. `LIBRARY_ONLY_PROVIDERS` in `tests/test_t08_w2_support_envelope.py` still maps `pr-lib-v1` to `S04`;
  5. `retake.json` has `selectable_in_build: false` and `registration_version: 2`.

  Each clause fails if 3b's exposure is done early.

### 14.5 How long the measurement is valid

- The re-take reads only two things from the records: `{id, name, formula, cas, synthetic}` and the phases
  (W27v2-R03).
- Availability is decided by CAS RN (`benchmarks/m06/w27/coverage.py:336–356`: `available = kind == "chemical" and
  cas in registry_cas`). The constants (critical properties, NASA-7) never enter.
- `retake.json` is valid only for its recorded `pr_lib_data_sha256`. Cited at any other data hash, it is stale.
  WO-L01-3b re-takes on the cleaned records.

### 14.6 Finding F-4 (for the clean-up package and Frank; not ruled here)

- **Dropping CAS RNs breaks W27's identity key.** Frank's clean-up drops the CAS RNs from the records (CAS licence).
  W27 identifies a registry chemical by CAS RN (§14.5), and W27v2-R03 reads `cas` from the records. Without CAS RNs,
  every library component is `unavailable` to W27. Before 3b can measure anything, the clean-up therefore needs a
  registered identity key other than the CAS RN, or a W27 amendment.
- **The shipped C1 records carry CAS RNs.** `benchmarks/m01/components.yaml`, packaged since 0.2.0, carries five.
  Whether C12's CAS-licence reading reaches that file is Frank's question.

Neither point is decided here.

### 14.7 Rejected alternatives

- **Wait for the clean-up package.** The measurement would then also wait on F-4. Today's records already answer what
  the re-take asks: whether the library route removes the component reasons §6.3 projects, and whether version 2
  judges a real two-route build. The constants do not enter that answer. 3a costs one script and one test, and moves
  no identity.
- **Expose with the records unpackaged (source checkout only).** Every wheel built from that commit would carry a
  selectable basis whose records are absent. A revision that selects it fails at load, which is a placeholder path.
  It would also retire L01.A22 (b) and (c) and R-569, against Frank's ruling.
- **Patch `revision_binding` in-process for the run.** The patch would be invisible in the record, and `build_snapshot`
  already takes the binder as an argument.

### 14.8 What this amendment does not establish

- **Any coverage number.** 3a measures it.
- **A validation of `pr-lib-v1`** (W27 v2 §8).
- **Any decision about shipping, F-4 or the C1 file's CAS RNs.**
- **Whether a release reports a version 2 result** (W27 v2 §9 Q-1).
