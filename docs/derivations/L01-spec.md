# L01 specification — component-library gaps on the OpenIDAES-450 development half (Water first)

**Status:** Proposed, 2026-10-22. **Author:** design lane (`specifier`), package L01, branch `wp/L01`.
**Decision record:** ADR 0043 (Proposed); register R-520…R-527; `docs/L01_DECISIONS.md`.
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
- **L01.A24** — Before W27 can judge two `cubic_pr` routes, the re-take (§6) on a build that exposes `pr-lib-v1`
  behaves as follows:
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
- **WO-L01-3 — Exposure and re-take** (held until Q-1 is resolved):
  - the binder basis and the snapshot line (§4.3);
  - `benchmarks/l01/retake.py` (§6.2) and `tests/test_l01_retake.py` for A23–A26.
  - Before W27-A3 only A24 is runnable, and its refusal is the registered result.
