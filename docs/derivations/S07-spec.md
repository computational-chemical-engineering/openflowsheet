# S07 — CoolProp as an optional pure-fluid Helmholtz evaluator: contract, domain, identity and test specification

**Package:** S07 (brief `docs/briefs/S07-coolprop-design.md`; branch `wp/S07`). **Lane:** design (`specifier`) for
this document; build for WO-S07-1…3 (§12). **ADR:** 0046 (Proposed). **Register:** R-618…R-622.
**Precedent followed:** S05 (`docs/derivations/S05-IAPWS95-spec.md`, ADR 0045). Where this document says "as S05
§x", the S05 text applies with the substitutions stated here, and nothing else from S05 is implied.
**Generator (to be written by WO-S07-1, plan in §8):** `docs/derivations/scripts/s07_reference.py`, run in an
environment holding the `coolprop` extra and mpmath 1.3.0, `--check`; it writes `s07_reference.json`.
**Measurements behind this document:** `docs/derivations/scripts/s07_measurements/m1…m4` (§14), run 2026-10-23 on
the workstation (x86-64, Python 3.13.5) in a scratch venv with `CoolProp==8.0.0 mpmath==1.3.0`.

## 0. Read this first

- CoolProp supplies **only** the Helmholtz energy partials α°, αʳ in (δ, τ) up to total order 3, at a (T, ρ) the
  provider chooses. Every property, every density root, every saturation state, every phase decision and every
  refusal is the provider's own (blueprint §6.1, D08, D10). CoolProp's flash routines and property getters (`p()`,
  `hmolar()`, `PropsSI`, …) are never called by the provider. This is assertion A27, an allowlist over the module's
  AST, not a promise.
- Every expected number is a key of `s07_reference.json`, computed by a 50-digit mpmath evaluation of the closed
  forms of §2 over each fluid's coefficients as parsed from the pinned CoolProp's fluid JSON. CoolProp's own
  numerical evaluation never supplies an expectation (rule 1); it is what A03/A04 test.
- The water fluid is additionally judged against S05's `s05_reference.json` (A23), whose coefficients were checked
  digit by digit against the printed IAPWS release (S05 §15.1). That is the one check here that does not share
  CoolProp's data.
- The project does not redistribute CoolProp or its data: CoolProp is an optional extra, and no committed file holds a
  coefficient (A29). `s07_reference.json` holds property values at registered states, the fluids' identity hashes and
  derived constants only.
- Silence never reads as success. A missing, mismatched or mutated CoolProp is a typed refusal on every call (§5.2),
  and `describe()` still answers with the pinned identity.

## 1. Authority, scope and what this establishes

Authority: ADR 0046 (Proposed), under plan §1.3. Consistent with ADR 0001 D1–D5, ADR 0026's provider pattern,
R-568/R-569 (library-only providers), T08.A32 (no third-party data in the artifacts) and `interfaces-frozen.md` §1:
no Protocol, result type or field changes. The provider uses `PropertyRequest`, `PropertyResult`, `FlashRequest`,
`FlashResult` and `PropertyCapabilities` as they stand, and its domain is a box per fluid, which
`PropertyCapabilities.domain` can state.

This document establishes:
1. the fluids, their CoolProp names and the term types the generator must evaluate (§2);
2. the provider contract: one instance per fluid, properties, derivatives, flash (§3);
3. how CoolProp is called, and the identity, pin and guard rules (§4, §5);
4. the per-fluid domain, constants and phase rule (§6);
5. the registered states by rule, and why each is there (§7);
6. the generator plan and its executable self-claims (§8);
7. thirty-two numbered assertions with expectations and tolerances (§9);
8. findings, open questions, work orders and the manifest check list (§10–§13).

## 2. Fluids and the closed form

### 2.1 The fluid list (decided; R-620)

The nine components of the S04 library records (`benchmarks/l01/components.yaml`, `pr_lib.COMPONENTS`), by the same
component ids:

| id | CoolProp name | EOS (CoolProp `BibTeX_EOS`) | R, J/(mol·K) | M, kg/mol | T_t, K | JSON T_max, K | JSON p_max, Pa | α° types | αʳ types |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H2O | Water | Wagner-JPCRD-2002 | 8.314371357587 | 0.018015268 | 273.16 | 2000 | 1.0e9 | L, LT, PE | P, G, NA |
| CO2 | CarbonDioxide | Span-JPCRD-1996 | 8.31451 | 0.0440098 | 216.592 | 2000 | 8.0e8 | L, LT, PE, O | P, G, NA |
| N2 | Nitrogen | Span-JPCRD-2000 | 8.31451 | 0.02801348 | 63.151 | 2000 | 2.2e9 | L, LT, PET, Pw | P, G |
| O2 | Oxygen | Schmidt-FPE-1985 | 8.31434 | 0.0319988 | 54.361 | 2000 | 8.0e7 | L, LT, PE, O | P |
| Ar | Argon | Tegeler-JPCRD-1999 | 8.31451 | 0.039948 | 83.806 | 2000 | 1.0e9 | L, LT, O | P, G |
| CH4 | Methane | Setzmann-JPCRD-1991 | 8.31451 | 0.0160428 | 90.6941 | 625 | 1.0e9 | L, LT, PET, O | P, G |
| C2H6 | Ethane | Buecker-JPCRD-2006 | 8.314472 | 0.03006904 | 90.368 | 675 | 9.0e8 | L, LT, PE, O | P, G |
| C3H8 | n-Propane | Lemmon-JCED-2009 | 8.314472 | 0.04409562 | 85.525 | 650 | 1.0e9 | L, LT, PE | P, G |
| H2 | Hydrogen | Leachman-JPCRD-2009 | 8.314472 | 0.00201588 | 13.957 | 1000 | 2.0e9 | L, LT, PET | P, G |

Measured with CoolProp 8.0.0 (m1). Every fluid has exactly one EOS. Each fluid uses its own R and M everywhere; no
CODATA value enters (as S05 D1).

**Why these nine.** (a) They are the components the L01 re-take admits (L01 spec §6.3: H2O 139, CO2 38, O2 16,
C2H6 4, C3H8 4 reasons removed; N2, H2, Ar, CH4 from C1), so the ids, CAS numbers and records already exist.
(b) The S04 cross-check (A24) is available for every one. (c) They need only six α° and three αʳ term types (§2.2),
so one generator covers all nine. No development case changes class because of S07 alone: the provider is
library-only (§3.4), and the remaining component reasons after L01 (CO 6, C4H10 4, CH3OH 4, BTEX 2, ions and solids)
occur in mixtures. Adding a CoolProp pure fluid later is a generator run and a table row (§11 Q-5).

### 2.2 Term types (the generator's closed forms)

τ = T_red/T, δ = ρ/ρ_red, with T_red and ρ_red (mol/m³) from the fluid JSON `EOS[0].STATES.reducing`. Sums run
over the term's arrays. Abbreviations as in §2.1.

| | type | contribution |
| --- | --- | --- |
| L | `IdealGasHelmholtzLead` | ln δ + a1 + a2 τ |
| O | `IdealGasHelmholtzEnthalpyEntropyOffset` | a1 + a2 τ |
| LT | `IdealGasHelmholtzLogTau` | a ln τ |
| PE | `IdealGasHelmholtzPlanckEinstein` | Σ n ln(1 − exp(−t τ)) |
| PET | `IdealGasHelmholtzPlanckEinsteinFunctionT` | Σ n ln(1 − exp(−(v/T_crit) τ)), `Tcrit` from the term |
| Pw | `IdealGasHelmholtzPower` | Σ n τ^t |
| P | `ResidualHelmholtzPower` | Σ n δ^d τ^t · (exp(−δ^l) if l > 0, else 1) |
| G | `ResidualHelmholtzGaussian` | Σ n δ^d τ^t exp(−η(δ − ε)² − β(τ − γ)²) |
| NA | `ResidualHelmholtzNonAnalytic` | Σ n Δ^b δ ψ, θ = (1 − τ) + A[(δ − 1)²]^{1/(2β)}, Δ = θ² + B[(δ − 1)²]^a, ψ = exp(−C(δ − 1)² − D(τ − 1)²) |

**Measured (m4):** a 30-digit mpmath evaluation of these forms, differentiated numerically, reproduces all twenty
CoolProp 8.0.0 partials (10 of α°, 10 of αʳ, total order ≤ 3) for all nine fluids at five (T/T_red, δ) points
{(1.5, 0.3), (0.8, 2.4), (0.95, 0.02), (2.5, 1.1), (1.1, 1.6)}, with max |Δ|/max(|ref|, 1) = 1.5e-15 for α° and
8.0e-14 for αʳ (worst: N2 `d3alphar_dDelta3` at (0.95, 0.02)). So the forms above are CoolProp's, and its
partials sit at the double-precision floor. The NA term at δ = 1 follows S05 §3.2's zero-jet rule (A03 state
`delta_one`, water and CO2 only). A term type outside the table is a generator refusal (claim C1), never a skip.

### 2.3 Properties

Every property is S05 §3.1's closed form in the jet, with that fluid's R and M, molar SI, and `lnphi_<id>` named by
the component id. (T, P) derivatives follow S05 §3.3, the identities I1–I9 S05 §3.4, saturation S05 §3.5. The
n-derivatives are exactly 0.0.

## 3. The provider contract

### 3.1 Module, class and instances

- Module `src/openflowsheet/thermo/coolprop_heos.py`; `PROVIDER_ID = "coolprop-heos-v1"`;
  `REFERENCE_CONVENTION = "COOLPROP-DEF-ref-v1"` (§3.5).
- `CoolPropHeosProvider(component_id)` for `component_id` in §2.1's ids; any other id raises `ValueError` at
  construction (a programming error, not a request outcome). One instance serves one fluid: components `(id,)`,
  state definition `nTP-v1`, `len(state.n) == 1`. Mixtures are out of scope (blueprint §6.1).
- The module imports CoolProp lazily, inside the guard (§5.2). `import openflowsheet.thermo.coolprop_heos` must
  succeed without CoolProp, because T08's provider scan imports every `thermo` module.
- `iapws95.py` is not modified: its `implementation_sha256` is a hash of its bytes. The S07 module re-implements the
  S05 algorithms generically over a fluid-constants record (ADR 0046 D6). A later package may factor both onto one
  core under a bit-identity gate for `iapws95-v1`.

### 3.2 What it offers

| | |
| --- | --- |
| properties | `h`, `s`, `v`, `Z`, `cp`, `lnphi_<id>`, `Psat`, `Tsat` |
| phases | `LIQUID`, `VAPOR` |
| derivatives | first order in `T`, `P`, `n_<id>`; the `n_<id>` ones are exactly 0.0 |
| flashes | `TP` only, with S05 §4.5's flash rules |
| `derivative_order` | `{T: 1, P: 1, n_<id>: 1}` |
| `domain` | `{"T": (T_lo, T_hi), "P": (P_lo, P_hi)}` of §6.1 |
| `thread_safety` | `not_thread_safe` (one CoolProp `AbstractState` per instance, §4) |
| `achieved_accuracy` | `exact-double` |
| `uncertainty` | names the EOS reference of §2.1 and says the EOS's own uncertainty is not re-validated |
| `data_provenance` | `CoolProp 8.0.0 (MIT), fluid <name>, not redistributed; <BibTeX_EOS>` |

The jet needs total order 3 (cp's T and P derivatives), and CoolProp provides it (m2: none of the twenty getters is
missing).

### 3.3 The module-level jet

`helmholtz_jet(component_id, temperature, density) -> tuple[PhiJet, PhiJet]` returns (α°, αʳ) with the ten
partials each, in S05 §3.2's order (φ, φ_δ, φ_δδ, φ_τ, φ_ττ, φ_δτ, φ_δδδ, φ_δδτ, φ_δττ, φ_τττ), at (T, ρ) in K and
mol/m³. It reuses `iapws95.PhiJet` (import only). It is part of the tested surface (A03, A04, A24) and carries the
guard of §5.2: on a guard failure it raises `CoolPropUnavailable` carrying the refusal code.

### 3.4 Library-only (decided; R-621)

`coolprop-heos-v1` is in no `SELECTABLE_BASES` entry. It is registered in `LIBRARY_ONLY_PROVIDERS` as `"S07"`, and
R-568/R-569 apply unchanged: a U02 note names it as library-only. The records-less selectable basis that S05 and
S07 both need (a basis key without a records file, unit models, W27 v2 mapping, support-matrix row, envelope) is a
follow-on package, named in §12.4. It is not designed here, because it changes the selection layer, which is shared
with `pr-c1-v1` and `pr-lib-v1`, and S07's first delivery stays small.

### 3.5 Reference convention `COOLPROP-DEF-ref-v1`

- The datum of each fluid is its α° exactly as the pinned fluid JSON gives it, `EnthalpyEntropyOffset` terms
  included (CoolProp's "DEF" state). It differs per fluid: CO2 carries an IIR offset, O2, Ar, CH4 and C2H6 carry
  offsets, Water, N2, C3H8 and H2 carry none (m1).
- It is not a formation datum, and it is not in ADR 0011 D2's reaction-consistent set. Streams of this convention
  never mix with another convention's (ADR 0001 D5.2).
- For water, the numbers coincide with `IAPWS95-ref-v1` (A23 asserts h and s), but the names differ, and D5.2 still
  forbids mixing.
- The convention is bound to the pinned data: a different fluid JSON is a different datum, which the pin rule
  (§5.1) already makes a different provider version.
- The line in ADR 0001 D5 and `interfaces-frozen.md` §3 is finding F-1 (§10). This document does not write it.

## 4. How CoolProp is called

- One `CoolProp.AbstractState("HEOS", <name>)` per provider instance, created by the guard (§5.2) and reused for
  every evaluation. `specify_phase(iphase_gas)` is called once, before the first update.
- An evaluation is `update(DmolarT_INPUTS, ρ, T)` followed by the twenty partial getters. Nothing else.
- **Why impose a phase.** Measured (m2), water at four states (400 K in the dome at δ = 1.458, vapour, liquid,
  900 K): the twenty partials are bit-identical with no imposed phase, with `iphase_gas` and with `iphase_liquid`.
  Without an imposed phase CoolProp runs its own phase determination (a saturation solve), whose cost and failure
  modes are not the provider's. With `iphase_supercritical` at T < T_c it raises. In the dome, CoolProp's own `p()`
  with no imposed phase returns the saturation pressure, 245769.35 Pa, while the EOS pressure from the jet is
  6.739e15 Pa. The provider's density iterations may visit such states, so `p()` is never used.
- **The jet at (T, ρ) is the EOS at (T, ρ).** At the in-dome state, CoolProp's αʳ partials agree with
  `iapws95.phi_jet` to 2.4e-15 (m2 with the project venv).
- **Determinism.** The same (T, ρ) after intervening updates gives bit-identical partials (m2). Importing CoolProp
  leaves subnormals intact: no flush-to-zero is switched on (m3).
- **Cost.** 9.9 µs per update plus twenty getters (m3, N2, workstation). An S05-style density solve takes about ten
  evaluations.
- **Exceptions.** Any exception raised by CoolProp during an evaluation becomes the refusal
  `coolprop_evaluation_failed:` (status `error`, §6.5). A22's grid asserts that it never occurs inside the domain.

## 5. Identity, pin and guard

### 5.1 The pin and the identity rule (decided; R-619)

- **One version.** `CoolProp==8.0.0`, gitrevision `ae81610e7d23efc57f9d051c8e70a4d66e87537f` (m1). The module
  carries `PINNED_COOLPROP_VERSION`, `PINNED_COOLPROP_GITREVISION` and, per fluid, `FLUID_DATA_SHA256[id]`.
- **The fluid data hash.** `fluid_data_sha256(name)` = SHA-256 of the UTF-8 bytes of
  `json.dumps(json.loads(CP.get_fluid_param_string(name, "JSON")), sort_keys=True, separators=(",", ":"),
  ensure_ascii=True)`. Re-serializing makes the hash independent of CoolProp's whitespace and key order and of the
  platform's number printing (Python's float repr is the shortest round-trip form on every platform).
- **`data_sha256`** = SHA-256 of the canonical JSON (same `dumps` arguments) of
  `{"coolprop_version": "8.0.0", "fluid": <name>, "fluid_data_sha256": FLUID_DATA_SHA256[id]}`.
- **`implementation_sha256`** = SHA-256 of the canonical JSON of
  `{"module_sha256": <SHA-256 of coolprop_heos.py's bytes>, "coolprop_version": "8.0.0",
  "coolprop_gitrevision": "ae81610e…"}`.
- **Both are architecture-independent by construction.** The CoolProp binary differs per architecture
  (wheel SHA-256 prefixes: x86-64 `8ca1aefd1873b14f3e7e`, aarch64 `113fc0e97f2b64617141`, both
  `coolprop-8.0.0-cp312-abi3-manylinux2014_*`), so the binary's hash is recorded in the manifest and the licence
  inventory, never in the identity. A cache key or a replay comparison across architectures therefore sees one
  identity. Whether the values are identical across architectures is §9 A31.
- **Both are computed from constants.** `describe()` needs no CoolProp: the identity is what the provider will
  evaluate under, and the guard ensures that the installed CoolProp matches it before any value is produced.
- **Moving the pin** takes a register entry and a spec amendment. The generator is re-run. If any
  `FLUID_DATA_SHA256` changes, or any registered value moves outside its §9 tolerance, the provider id becomes
  `coolprop-heos-v2`; otherwise the id stays and only `implementation_sha256` moves. Running on any other installed
  version is a refusal, never a warning.

### 5.2 The guard

Run once per instance, at the first evaluation (not at construction, so constructing never fails). It sets one
outcome, which is cached for the instance's lifetime:

| order | check | refusal code (status `unsupported`) |
| --- | --- | --- |
| G1 | `import CoolProp` succeeds | `coolprop_unavailable` |
| G2 | `CoolProp.__version__ == "8.0.0"` and the gitrevision equals the pin | `coolprop_version_mismatch` |
| G3 | `fluid_data_sha256(name) == FLUID_DATA_SHA256[id]` | `coolprop_data_mismatch` |
| G4 | a fresh `AbstractState` gives α°, α°_τ, αʳ, αʳ_δ at the fluid's canary point (§6.1) within 1e-12·max(\|ref\|, 1) of the module's pinned canary values | `coolprop_state_mutated` |

**Why G4 exists.** Measured (m3): `CoolProp.set_reference_state("Water", "NBP")` leaves the fluid JSON, and so G3's
hash, unchanged, but it changes α° in every `AbstractState` created afterwards. Setting it back to `"DEF"` restores
the bits. The CoolProp library is process-global mutable state, so another caller can shift the datum silently. The
provider never mutates CoolProp's global state (A27 lists the forbidden calls). An offset shifts α° by O(1), so a
1e-12 tolerance catches it and admits cross-architecture last-bit differences (A31). The `AbstractState` created by
G4 is the one the instance keeps; later global mutations do not reach an existing instance (WO-S07-2 measures this,
A26(c)).

## 6. Domain, constants and phase rule

### 6.1 Per-fluid constants (rules; the generator emits the values, the module mirrors them bitwise, A01)

| constant | rule |
| --- | --- |
| T_c, p_c, ρ_c | the EOS's own critical point: (∂p/∂ρ)_T = (∂²p/∂ρ²)_T = 0, solved at 50 digits, seeded by CoolProp's `T_critical()` and `rhomolar_critical()`, rounded to the nearest double. Not the reducing values: O2's T_red = 154.581 K, while CoolProp reports T_c = 154.599 K (m1) |
| T_hi | min(JSON T_max, 1273.15 K): 1273.15 for H2O, CO2, N2, O2, Ar; 625, 675, 650, 1000 for CH4, C2H6, C3H8, H2 |
| P_lo | 1.0e2 Pa |
| P_hi | min(JSON p_max, 1.0e8 Pa): 8.0e7 for O2, 1.0e8 otherwise |
| T_lo | H2O: T_t = 273.16 K (S05 §4.1: ice III starts at 209.9 MPa > P_hi). Others: ⌈10·T_m(P_hi)⌉/10 K, where T_m is the melting temperature at P_hi. So no state of the box lies above the melting line (§6.2) |
| T_σ,max | T_c·(1 − 2e-4), the highest temperature at which `Psat` is answered |
| near-critical box | T ∈ (T_σ,max, T_c·(1 + 2e-3)), P ∈ [p_c·(1 − 4e-3), p_c·(1 + 8e-3)] |
| ρ_max | ⌈1.10·ρ_L(T_lo, P_hi)⌉ to 3 significant digits, mol/m³: the top of every LIQUID bracket |
| ε_σ | 1e-6 in ln P, as S05 |
| canary | (T, ρ) = (1.5·T_red, 0.3·ρ_red), with the four G4 values from the generator |

**T_m(P_hi), measured with CoolProp 8.0.0's `melting_line(iT, iP, P_hi)` (m5):** CO2 236.03, N2 82.80, O2 63.03
(at 80 MPa), Ar 106.96, CH4 114.28, C2H6 105.39, C3H8 94.67, H2 31.39 K. So T_lo = 236.1, 82.9, 63.1, 107.0, 114.3,
105.4, 94.7, 31.4 K. (Water's 264.21 K at 100 MPa lies on the ice Ih branch below T_t, which is consistent with S05's
argument.) The generator recomputes these (C9).

### 6.2 Why the cryogenic liquid is cut, and what that costs (decided for the first delivery; R-620; Q-S07-1)

Above the melting line the stable phase is solid, and the EOS's LIQUID answer there is an extrapolation.
CoolProp's own `PropsSI` refuses those states ("we don't support T below Tmelt(p)", N2, Ar, CH4, C2H6, C3H8, H2 at
(1.1·T_t, 100 MPa); m5). Raising T_lo to T_m(P_hi) keeps the domain a box, which `PropertyCapabilities.domain`
can state exactly, and needs no melting-line code at run time. **Cost:** saturated and subcooled liquid below T_lo is
out of domain: liquid N2 at 77 K, liquid Ar at 87 K, LNG at 112 K, liquid H2 at 20 K (H2's answered saturation range
is only [31.4 K, T_σ,max]). Liquid O2 at 90 K stays inside (T_lo = 63.1 K). Process gas and vapour of all nine, liquid H2O, CO2, C2H6 and C3H8 at their usual
conditions, and supercritical states are inside. Cryogenic liquids need a run-time melting guard, and the domain
would then no longer be a box. That is follow-on S07b (§12.4).

### 6.3 Phase rule, brackets, saturation and refusals

As S05 §4.2, §4.4, §3.5 and §4.5, with these substitutions:

- 647.0 K → T_σ,max; the box (647.0, 648.0) K × [22.0, 22.2] MPa → §6.1's box; T_c, p_c → §6.1's; 273.16 K → T_lo;
  1250 kg/m³ → ρ_max; the domain → §6.1's box; "H2O" → the instance's id.
- Supercritical states (T ≥ T_c) are labelled VAPOR, as S05 (Frank's C10-Q2 answer "always vapour" applies to
  this provider too; no new question).
- `Psat` is answered for T ∈ [T_lo, T_σ,max]; `Tsat` for P ∈ [max(p_σ(T_lo), P_lo), p_σ(T_σ,max)], both bounds
  computed by the provider.
- The saturation seed: the provider's own choice of ancillary, recorded with its source in the module docstring.
  CoolProp's `SUPERANCILLARY` or ancillary data may serve as a seed only if read from the guard-checked JSON. A
  seed affects the iteration count, never the converged value (the convergence rule is S05 §3.5's 4ε).

### 6.4 Why these constants (each is a generator claim, §8)

- **The box contains the critical point and the end of the saturation curve.** p_σ(T_σ,max) > p_c(1 − 4e-3) for
  every fluid (C6). Near T_c, d ln p_σ / d ln T ≈ 6–8, so p_σ(T_σ,max)/p_c ≈ 1 − 7·2e-4 ≈ 0.9986. That is a margin
  of about 2.6e-3 in ln P over the box's lower edge. The EOS critical point lies inside the box (C6).
- **The metastable roots exist at the edge.** At T_σ,max both band-edge roots (P = p_σe^{±ε_σ}) exist on their
  branches (C7).
- **The brackets hold.** (∂p/∂ρ)_T > 0 on the VAPOR and LIQUID brackets at 23 subcritical temperatures from T_lo to
  T_σ,max, and on (0, ρ_max] at 8 temperatures from T_c(1 + 2e-3) to T_hi. p(ρ_max, T) > P_hi at all 31. 41 points
  per bracket, as S05 §4.4 (C8).
- **No melting inside the box.** T_m(P_hi) ≤ T_lo, and T_m(P) increases on 20 pressures spaced logarithmically
  from max(p_t, P_lo) to P_hi, by CoolProp's `melting_line(iT, iP, ·)`. So no (T ≥ T_lo, P ≤ P_hi) lies above the
  melting line (C9; not for H2O, §6.1).

### 6.5 Refusal table (complete; precedence top to bottom; message `<code>: <detail>`)

| # | code | status | when |
| --- | --- | --- | --- |
| 1 | `undeclared_derivative_input` | unsupported | a derivative input outside {T, P, n_<id>} |
| 2 | `unknown_property` | unsupported | a property outside §3.2's eight |
| 3 | `state_length` | error | `len(state.n) != 1` |
| 4 | `coolprop_unavailable`, `coolprop_version_mismatch`, `coolprop_data_mismatch`, `coolprop_state_mutated` | unsupported | §5.2 G1–G4 |
| 5 | `out_of_domain` | out_of_domain | outside §6.1's box |
| 6 | `dormant_state` | unsupported | n_tot == 0 |
| 7 | `no_saturation` | unsupported | `Psat` at T > T_σ,max, or `Tsat` outside its interval (§6.3) |
| 8 | `near_critical` | unsupported | inside the box, when any phase property is asked |
| 9 | `phase_not_stable` | unsupported | S05 §4.2 steps 2–4 |
| 10 | `density_not_converged`, `saturation_not_converged` | not_converged | S05 §4.4, §3.5 |
| 11 | `coolprop_evaluation_failed` | error | CoolProp raised during an evaluation (§4) |

`flash` checks S05 §4.5's order, with the guard (row 4) after `state_length`. Every result, refusals included,
carries `provider_id` `coolprop-heos-v1` and `reference_convention` `COOLPROP-DEF-ref-v1`.

## 7. Registered states (by rule; the generator emits the concrete values)

Per fluid f. T_mid = (T_lo + T_σ,max)/2. Every state's reason is in the last column. A state that a rule would put
outside f's box is dropped and recorded in the JSON's `dropped` list (C10 asserts the list is exactly the expected one).

| key | where | phase | why it is there |
| --- | --- | --- | --- |
| `phi_gas` | (1.5·T_red, 0.3·ρ_red) | jet only | dense supercritical gas; every term type is active |
| `phi_liq` | (0.8·T_red, 2.4·ρ_red) | jet only | liquid-like δ: Gaussian and high-d terms dominate |
| `phi_dilute` | (0.95·T_red, 0.02·ρ_red) | jet only | the measured worst for d3αʳ/dδ³ (m4) |
| `delta_one` | (0.9·T_red, ρ_red) | jet only | H2O, CO2 only: the NA zero-jet case (S05 §3.2) |
| `V_sup` | (1.5·T_c, 0.1·p_c) | VAPOR | ordinary process gas |
| `V_sub` | (T_mid, 0.5·p_σ(T_mid)) | VAPOR | subcritical vapour, stable branch |
| `L_sub` | (T_mid, 2·p_σ(T_mid)) | LIQUID | compressed liquid, stable branch |
| `S_dense` | (1.2·T_c, 3·p_c) | VAPOR | dense supercritical, liquid-like density: the T ≥ T_c label |
| `L_corner` | (T_lo, P_hi) | LIQUID | the melting-edge corner; the densest admitted state |
| `V_corner` | (T_hi, P_lo) | VAPOR | the near-ideal corner: lnφ ≈ 0, Z ≈ 1, but not exactly |
| `NC_V` | (T_c(1 − 5e-4), 0.995·p_σ(T)) | VAPOR | ill-conditioned density solve next to the box (bounds ×100) |
| `NC_L` | (T_c(1 − 5e-4), 1.005·p_σ(T)) | LIQUID | as `NC_V` on the other branch |
| `sat_lo`, `sat_mid`, `sat_hi` | T ∈ {T_lo, T_mid, T_σ,max} | both | `Psat`, slope, Δh; `sat_lo` has f's smallest vapour density; `sat_hi` is the edge |
| `tsat_mid` | P = p_σ(T_mid) rounded to 6 significant digits | both | `Tsat` and its slope |
| band probes | T_mid, P = p_σ·e^{s}, s ∈ {−2ε_σ, −0.5ε_σ, +0.5ε_σ, +2ε_σ} | per S05 §5.4 | the band answers both phases inside, one outside |
| refusal probes | §9 A14–A16, A18, A21, by rule from §6.1's constants (each with an answered control 1e-9 relative inside) | | each code is reachable |

`V_corner` is a vanishing-quantity state: lnφ and Z − 1 are small there, but not zero. A17's FD scale s_f keeps the
assertion non-vacuous, and A05 asserts the values themselves.

## 8. Generator plan (`s07_reference.py`; WO-S07-1) and its self-claims

**Inputs.** For each fluid, from the installed CoolProp 8.0.0 only: the fluid JSON (parsed, never written out),
`T_critical()`/`rhomolar_critical()` (seeds), `melting_line(iT, iP, ·)` (T_lo and C9), and `PropsSI` at the registered TP states (admission, C11). `s05_reference.json` for C12.

**Computation.** mpmath 1.3.0 at 50 digits. Closed forms of §2.2. Partials by mpmath's numerical differentiation of
α° and αʳ alone (S05 D6's independence: values and derivatives reach the reference by different routes). Critical
point, saturation (Maxwell), density roots and band roots solved to 40 digits, then rounded to double.

**Output.** `s07_reference.json`: `schema` `s07-reference-v1`, `coolprop_version`, `coolprop_gitrevision`, per fluid
`fluid_data_sha256`, `constants` (§6.1), `canary`, `phi_states`, `tp_states` (values and T/P derivatives),
`saturation`, `tsat`, `band`, `probes`, `dropped`, `s04_ig` (cp^ig at 300 and 600 K), `agreement` (C11's measured
worsts), and `claims` (count and names). Floats as `repr`; keys sorted; `--check` regenerates and byte-compares.

**Self-claims (the generator refuses to emit if any fails):**

| | claim |
| --- | --- |
| C1 | every fluid has one EOS, and every term type is in §2.2's table |
| C2 | the installed CoolProp is 8.0.0 at the pinned gitrevision; every `fluid_data_sha256` is stable across two reads in one process |
| C3 | no output key holds a coefficient array; the output's key set equals the schema's whitelist (feeds A29) |
| C4 | at each `phi_*` state, the 50-digit partials agree with a 30-digit recomputation to 1e-25 (the differentiation is converged) |
| C5 | the critical point satisfies \|p_ρ\|·ρ_c/p_c < 1e-20 and \|p_ρρ\|·ρ_c²/p_c < 1e-20, and T_c is within 1e-3 relative of CoolProp's `T_critical()` |
| C6 | §6.4 first item, for every fluid |
| C7 | §6.4 second item |
| C8 | §6.4 third item |
| C9 | §6.4 fourth item |
| C10 | every rule-state lies inside its fluid's box and outside the near-critical box, or is in `dropped`; the expected `dropped` list is literal in the generator; all registered TP states of a fluid are pairwise distinct |
| C11 | admission: CoolProp's `PropsSI` agrees with the generator at every TP state outside NC within 1e-7 relative (h and s within 1e-7·R·T and 1e-7·R absolute), NC within 1e-5. The measured worsts go in `agreement`. This checks the generator against an independent solve; it never supplies a number |
| C12 | water: the generator's own values at S05's registered states with T ≤ 646.9 K equal `s05_reference.json`'s within 1e-12 relative (same formulation, two generators) |
| C13 | identities I1–I9 hold on the generator's numbers at every TP and saturation state to 1e-30 relative |
| C14 | the refusal-probe table covers every code of §6.5 except row 4 and row 11, each with a control |

## 9. Assertions

Test files: `tests/test_s07_coolprop.py` (WO-S07-2) and `tests/test_s07_registration.py` (WO-S07-3). "ref" is
`s07_reference.json`. Parametrized over the nine fluids unless stated. NC bounds ×100, as S05 §6.2.

| id | assertion | expectation | tolerance |
| --- | --- | --- | --- |
| A01 | The module's per-fluid constants (§6.1, canary included), `FLUID_DATA_SHA256`, R, M, T_red, ρ_red equal ref bitwise | ref `constants`, `canary` | exact |
| A02 | `describe()` per fluid: id, convention, `nTP-v1`, components, phases, the eight properties, `("TP",)`, `derivative_order`, `domain` = the box, `thread_safety` `not_thread_safe`; with CoolProp absent it still answers, with the same identity | §3.2 | exact |
| A03 | `helmholtz_jet` at `phi_gas`, `phi_liq`, `phi_dilute`, orders ≤ 2, α° and αʳ; `delta_one` for H2O and CO2 | ref `phi_states` | \|Δ\| ≤ 1e-12·max(\|ref\|, 1) |
| A04 | The third partials at the same states | ref | \|Δ\| ≤ 1e-11·max(\|ref\|, 1) |
| A05 | `evaluate_phase` at the TP states: h, s, v, Z, cp, lnphi | ref `tp_states` | as S05 A05 |
| A06 | Their T and P derivatives | ref | 1e-8 relative; NC ×100 |
| A07 | Every `n_<id>` derivative is present and 0.0; control: the T derivatives at the same state are non-zero | 0.0 | exact |
| A08 | `Psat` at `sat_*` and dPsat/dT; dPsat/dP is 0.0 | ref | as S05 A08 |
| A09 | `Tsat` at `tsat_mid` and dTsat/dP; dTsat/dT is 0.0 | ref | as S05 A09 |
| A10 | Maxwell on the provider's own Psat, and h_V − h_L | ref | as S05 A10, with "647.0 K" read as T_σ,max |
| A11 | Clausius–Clapeyron on the provider's own answers | itself | as S05 A11 |
| A12 | The datum, H2O only: S05 A12 at T_t; control at 450 K | ref | as S05 A12 |
| A13 | Band probes: answered sets, values, refused phase `phase_not_stable:` | ref `band` | as A05 |
| A14 | `near_critical:` probes for both phases and the flash, with controls | §6.5 | exact codes |
| A15 | The T ≥ T_c label and the (T_σ,max, T_c) strip, with controls | §6.5 | exact codes |
| A16 | The four box-edge probes → `out_of_domain:` for `evaluate_phase`, `Psat`, `Tsat`, `flash`; controls at the exact bounds `ok` | §6.1 | exact codes |
| A17 | Central differences of the provider's own values against its derivatives at the TP states and band probes | itself | S05 §6.3: h = 1e-6·x, FD_TOL = 1e-10 in value units |
| A18 | `no_saturation:` probes, with controls | §6.5 | exact codes |
| A19 | A saturation-only request skips the phase check; with `h` added it does not | §6.3 | exact codes |
| A20 | Flash: as S05 A20 | §6.5 | exact |
| A21 | Contract refusals 1, 2, 3, 6 of §6.5, with controls; constructing with an id outside §2.1 raises `ValueError` | §6.5 | exact |
| A22 | Robustness grid per fluid: 24 temperatures spaced evenly from T_lo to T_hi (ends included) × P ∈ {1e2, 1e3, …, P_hi} ∪ {P_hi}. Every non-refused phase is `ok`; `not_converged` and `coolprop_evaluation_failed` never occur; every answer has (∂v/∂P)_T < 0 and cp > 0 | none | exact |
| A23 | **Water against S05.** `coolprop-heos-v1` (H2O) at every S05 registered TP, saturation and band state with T ≤ 646.9 K, against `s05_reference.json` | S05 ref | S05 A05/A06/A08/A10 bounds |
| A24 | **Against S04's ideal-gas parts.** cp^ig = R(1 − τ²α°_ττ) from `helmholtz_jet` at ρ = 1 mol/m³ (α°_ττ does not depend on ρ) against `pr_lib.cp_ig` at 300 and 600 K; control: the same comparison per kilogram fails by > 10× | `pr_lib` | 2 % relative (L01.A12, R-528) |
| A25 | Determinism: two calls bitwise equal; provider id and convention on every result; `achieved_accuracy` `exact-double` | itself | bitwise |
| A26 | Guard: (a) CoolProp made unimportable (`sys.modules["CoolProp"] = None` in a subprocess) → every property, `Psat` and flash request refuses `coolprop_unavailable:`, and `helmholtz_jet` raises; (b) a monkeypatched version string → `coolprop_version_mismatch:`; a monkeypatched fluid JSON → `coolprop_data_mismatch:`; (c) in a subprocess, `set_reference_state(<name>, "NBP")` before the first evaluation → `coolprop_state_mutated:`, and after the first evaluation → values unchanged (bitwise) | §5.2 | exact codes |
| A27 | "Helmholtz evaluator only": the module's AST uses only these CoolProp names: `AbstractState`, `specify_phase`, `iphase_gas`, `update`, `DmolarT_INPUTS`, the twenty partial getters, `get_fluid_param_string`, `get_global_param_string`, `__version__`; and none of `set_reference_state`, `set_config_*`, `add_fluids_as_JSON`, `PropsSI`, `p`, `hmolar`, … appear | file | exact |
| A28 | Identity: `implementation_sha256` and `data_sha256` follow §5.1 exactly; equal with and without CoolProp installed | §5.1 | exact |
| A29 | No redistribution: (a) no `PACKAGED` path covers `s07_reference.json` or `docs/derivations/scripts/`; a built wheel and sdist hold no CoolProp file and no fluid JSON; (b) the default wheel's `Requires-Dist` names CoolProp only under the `coolprop` extra; (c) ref's key set equals C3's whitelist | files | exact |
| A30 | Library-only: absent from `SELECTABLE_BASES`; in `LIBRARY_ONLY_PROVIDERS` as `"S07"` and in `scanned_providers`; U02's note names `coolprop-heos-v1` | R-568, R-569 | exact |
| A31 | **Cross-architecture.** `benchmarks/s07/platform_digest.json` holds, per fluid, the `float.hex` of every A03–A13 answer as produced on x86-64 (a regression fixture, not validation). On each CI architecture the test recomputes the answers and compares them. Outcome (a): bitwise equal on aarch64 → A31 passes as "bit-identical". Outcome (b) is §11 Q-1's pre-registered rule | itself | (a) bitwise; (b) per Q-1 |
| A32 | Mutation battery, each mutation failing the named assertion: (m1) permute two jet slots (φ_δτ ↔ φ_ττ) → A03 and A05 (cp); (m2) use T_red in place of T_c in the phase rule → A15 for O2; (m3) CODATA R for N2 → A05; (m4) ε_σ = 0 → A13; (m5) omit the `n_<id>` derivative → A07; (m6) call `update` without `specify_phase` → A27; (m7) skip G4 → A26(c); (m8) hash the raw JSON string instead of the canonical one → A28 | named | each fails |

### 9.1 Tolerances: floor and margin

- **The jet (A03/A04).** CoolProp's partials against 30-digit mpmath: worst 8.0e-14 over 9 fluids × 5 states ×
  20 partials (m4). A03's 1e-12 sits 12× above it. A04's 1e-11 sits 125× above it. The coefficients are
  CoolProp's, so the provider-side errors worth catching are a permuted or mis-signed slot (O(1)) and a wrong
  reducing constant or fluid name (a different τ or δ: O2's T_c in place of T_red moves τ by 1.2e-4, and the
  partials by ≥ 1e-5 relative). The bounds sit ≥ 7 decades below the first and ≥ 6 below the second.
- **The properties (A05–A11, A13).** The provider's density root is converged to 4ε (S05 §4.4). Its value floor is
  the jet floor (1e-13) times κ ≤ 100 away from NC, so ≤ 1e-11, which leaves S05's bounds (1e-8 relative or
  1e-8·R·T absolute) 3 decades of margin. The smallest error worth catching is a wrong R (CODATA vs 8.31451:
  2.9e-6 relative in v at fixed (T, P)), which is 2.5 decades above the bound. NC ×100: S05's measured NC
  conditioning (4.3e-8 in CoolProp's own solve) applies.
- **A23 (water against S05).** Two implementations of one formulation. Measured: CoolProp's water jets against
  `iapws95.phi_jet` agree to 4.2e-16 (α°) and 6.6e-13 (αʳ, worst φ_δδτ at τ = 1.001, δ = 1.3; m3 with the project
  venv), so S05's bounds hold with ≥ 3 decades of margin outside NC.
- **A17.** Exactly S05 §6.3: the same algorithm, the same floor. If WO-S07-2 measures its floor above 1e-11 for
  some fluid, the design lane re-sets the tolerance (amendment), never the harness.
- **A24.** The S04 records' cp^ig is a correlation of the same reference EOS ideal parts, and L01.A12 already bounds
  it at 2 % (R-528). The control matters more than the bound: a J/kg-for-J/mol error is a factor 1/M ≥ 22.7.
- **A31(b).** See §11 Q-1.

## 10. Findings (for other documents; not written here)

- **F-1.** ADR 0001 D5 and `interfaces-frozen.md` §3 gain the convention line `COOLPROP-DEF-ref-v1` (§3.5), written
  by the design lane on ADR 0046's acceptance, as ADR 0045 did for `IAPWS95-ref-v1`. No Protocol, schema, quantity
  kind or check category changes.
- **F-2.** ADR 0045's "Alternatives rejected" rejects CoolProp as a runtime dependency (binary wheel per platform,
  no control over refusals or exactness). ADR 0046 supersedes that rejection for the S07 provider only, because
  both objections are answered: the dependency is optional, and refusals and exactness stay the project's (§4, §5).
  ADR 0045 is not edited. The register records the supersession (R-618).
- **F-3.** The G19 licence inventory (`scripts/t07_licence_inventory.py`) covers the `server` extra's closure. It
  must also cover the `coolprop` extra's (CoolProp, MIT, compiled; numpy is already covered). That is WO-S07-1.
- **F-4.** `docs/requirements.yaml` D08 gains S07 as a package when S07's manifest is `tested` (R-614 pattern).

## 11. Open questions (each with a recommended default)

- **Q-1 (needs a fact): are CoolProp's outputs bit-identical on aarch64?** Not measurable on the workstation (no
  aarch64 binfmt; podman present but cannot run arm images). The project's own pure-Python evaluations were
  bit-identical across the CI pair (ADR 0007 measurement 2). CoolProp is compiled C++, and aarch64 compilers contract
  multiply-adds into FMA by default, so last-bit differences are plausible. **Measurement that settles it:**
  WO-S07-3's CI run of A31 on `ubuntu-24.04-arm`. **Pre-registered default if it is not bitwise:** A31 compares
  with |Δ| ≤ 1e-12·max(|x|, s_f) (NC: 1e-10), where s_f is A17's scale. The argument: last-bit differences in the
  jet (≤ a few ulp, 1e-15) are amplified by κ ≤ 100 in the density root, to ≤ 1e-13. 1e-12 leaves a 10× margin,
  and it is 4 decades inside A05's 1e-8, so no reference assertion can change verdict between architectures. The
  manifest records the measured worst per quantity, and ADR 0046's status line states "cross-architecture agreement
  ≤ <measured>, not bit-identity". If the measured worst exceeds 1e-12, nothing is loosened: the build lane stops
  and the design lane amends.
- **Q-2 (closed by measurement while writing).** O2's T_m at its P_hi = 80 MPa is 63.03 K (m5). CoolProp raises
  only above 80 MPa, outside O2's Simon range. If the generator finds `melting_line` failing on any of C9's 20
  pressures, it refuses to emit, and the design lane amends (it does not fall back silently).
- **Q-3 (needs a fact): does a G4-checked `AbstractState` keep its α° after a later `set_reference_state`?**
  WO-S07-2 measures it in A26(c). **Default:** yes, so G4 runs once. If no, G4 runs on every evaluation (cost: four
  getters, < 1 µs), and §5.2 is amended.
- **Q-4 (needs the user's preference): may the cryogenic liquids wait?** That is §6.2's cut. Asked as Q-S07-1 in
  `docs/FRANK_QUESTIONS.md`. **Default:** yes, they wait for S07b.
- **Q-5 (needs the user's preference, not asked now): more CoolProp fluids.** **Default:** none until a case needs a
  pure-fluid stream of a component outside the nine. Each addition is a generator run, a §2.1 row and a register
  entry.

## 12. Work orders (each ≤ ~100k context; the lead lane is build for all three, and the design lane reviews WO-S07-1's generator before WO-S07-2 starts)

### 12.1 WO-S07-1 (build, `opus-engineer`): dependency, inventory and generator

1. `pyproject.toml`: `coolprop = ["CoolProp==8.0.0"]` under `[project.optional-dependencies]`. Not in
   `[project].dependencies`.
2. `requirements.lock`: add `CoolProp==8.0.0`, the way the `server` extra's closure is locked (the lock is the CI
   environment, not the default install; numpy is already pinned). CI then installs CoolProp on both architectures
   with no workflow change. Verify by `pip install -r requirements.lock` in a fresh venv on x86-64.
3. F-3: the licence inventory covers the `coolprop` extra; MIT is already in `ALLOWED` (check). Record both wheel
   SHA-256s with `--wheels` (both architectures, `pip download --platform …`).
4. `docs/derivations/scripts/s07_reference.py` per §8, and `s07_reference.json`, with `--check`.
5. Tests: none of the provider's. A generator check test may assert `--check` runs in < 10 min (or it stays a
   manifest command, as S05's did; the engineer chooses and records the choice).
6. Stop and report if any claim fails. Never edit a constant rule of §6.1 to make a claim pass.

### 12.2 WO-S07-2 (build, `opus-engineer`): the provider

`thermo/coolprop_heos.py` per §3–§6, and `tests/test_s07_coolprop.py` covering A01–A28 and A32. Settle Q-3.
Measure the A17 floor per fluid and record it. Before starting, read S05 §3–§4 and `iapws95.py`'s solver functions
(`_saturation`, `_bracketed_density`, `_metastable_density`, `_rule`) as the algorithm to generalize; do not import
them.

### 12.3 WO-S07-3 (build, `sonnet-implementer`): registration, cross-architecture and manifest

1. R-568/R-569: `LIBRARY_ONLY_PROVIDERS["coolprop-heos-v1"] = "S07"`, the U02 note, the harvest re-take that follows
   (S05's WO-S05-5 pattern for `HARVEST_SIZE`).
2. A29, A30, A31 in `tests/test_s07_registration.py`; `benchmarks/s07/platform_digest.json` generated on x86-64 by a
   committed script with `--check`. Push and read the aarch64 job's A31 result. Settle Q-1: if not bitwise, apply
   the pre-registered rule, record the measured worst, and stop for the design lane only if it exceeds 1e-12.
3. `evidence/S07/<commit>/manifest.json` per §13.

### 12.4 Follow-ons (not in S07)

- **Binding package** (records-less pure-fluid bases for `iapws95-v1` and `coolprop-heos-v1`: basis key, unit-model
  admission, W27 v2 mapping, support-matrix rows, envelope). Frank's S05 Q-8 answer plans it "together with S07".
  It needs its own ADR, because it changes `SELECTABLE_BASES`' shape.
- **S07b — cryogenic liquids:** a run-time melting guard, a non-box domain stated in `numerical_limitations`.
- **Core factoring:** S05 and S07 on one Helmholtz pure-fluid core, under a bit-identity gate for `iapws95-v1`.
- **Mixtures:** out of scope until composition derivatives are measured (blueprint §6.1).

## 13. Manifest check list (`evidence/S07/<commit>/manifest.json`)

`status: tested` requires: A01–A32 pass on x86-64 and aarch64 (A31 with Q-1's outcome stated); `s07_reference.py
--check` OK, with the command and CoolProp version recorded; the licence inventory OK with both wheel SHA-256s;
the measured A17 floors; Q-1 and Q-3 answered with their numbers; `requirements: [D08]`; `review: pending` (the
human sign-off is not an agent's to claim).

## 14. Measurements behind this document (commands; scratch venv only)

```
python3 -m venv $S/cpvenv && $S/cpvenv/bin/pip install CoolProp==8.0.0 mpmath==1.3.0
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m1_fluids.py       # §2.1 table, version, gitrevision, 136 fluids
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m2_api.py m2.json  # getters present, imposed phase, dome, determinism
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m3_more.py m3.json # FTZ, set_reference_state, water jets, timing
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m4_mp.py           # §2.2 forms vs CoolProp, 9 fluids
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m5_melt.py         # T_m(P_hi), PropsSI below T_melt
pip download --no-deps CoolProp==8.0.0 --only-binary=:all: [--platform manylinux2014_aarch64 --python-version 3.12]
```

The comparisons with `iapws95.phi_jet` (§4, §9.1) ran in the project venv over m2's and m3's JSON (inline
scripts; the reorder from m2's getter order to `PhiJet`'s order is the permutation (0, 1, 3, 2, 5, 4, 6, 7, 8, 9)).
WO-S07-1's generator re-measures every load-bearing number here as a claim (C2, C4, C9, C11, C12). These
scripts are records, not gates.

## 15. What this document does not establish

- The accuracy of any EOS against experiment, or of CoolProp's coefficients against the original papers (except
  water, through S05 and the IAPWS release). A03/A04 show that CoolProp evaluates its own data correctly. They do
  not show that the data are the papers'.
- The melting lines' accuracy. They are used once, to place T_lo, and they are CoolProp's data.
- Any development case becoming runnable. The provider is library-only.
- Bit-identity on aarch64, until Q-1 is measured.
- Mixtures, transport properties, solids, cryogenic liquids below T_lo, near-critical states inside the box, and
  metastable states beyond ε_σ.
- Permission to bundle CoolProp in any distribution. The extra is installed by the user from PyPI. A bundle would
  carry CoolProp's MIT notice and is a separate decision (ADR 0046).
- Anything about the held-out half.
