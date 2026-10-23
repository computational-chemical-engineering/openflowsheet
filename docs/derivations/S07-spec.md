# S07 — CoolProp as an optional pure-fluid Helmholtz evaluator: contract, domain, identity and test specification

**Package:** S07 (brief `docs/briefs/S07-coolprop-design.md`; branch `wp/S07`). **Lane:** design (`specifier`) for
this document; build for WO-S07-1a…4 (§16.14). **ADR:** 0046 (Proposed, with its Amendment 1 note). **Register:**
R-618…R-622; Amendment 1: R-623.
**Precedent followed:** S05 (`docs/derivations/S05-IAPWS95-spec.md`, ADR 0045). Where this document says "as S05
§x", the S05 text applies with the substitutions stated here, and nothing else from S05 is implied.
**Generator (to be written by WO-S07-1, plan in §8):** `docs/derivations/scripts/s07_reference.py`, run in an
environment holding the `coolprop` extra and mpmath 1.3.0, `--check`; it writes `s07_reference.json`.
**Measurements behind this document:** `docs/derivations/scripts/s07_measurements/m1…m4` (§14), run 2026-10-23 on
the workstation (x86-64, Python 3.13.5) in a scratch venv with `CoolProp==8.0.0 mpmath==1.3.0`; Amendment 1 adds m6–m8
(§16.16).

**Amendment 1 (2026-10-23, §16)** widens the fluid list from the nine S04 fluids to 123 CoolProp fluids, selected by
rule, at Frank's direction ("Broad list now"). Where §16 and an earlier section differ, §16 governs. The markers
"(amended, §16.x)" flag the places it changes, and §16.0 lists four errata in §1–§15.

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
7. thirty-two numbered assertions with expectations and tolerances (§9; thirty-five with §16.10);
8. findings, open questions, work orders and the manifest check list (§10–§13).

## 2. Fluids and the closed form

### 2.1 The fluid list (decided; R-620; amended, §16.1–§16.3: 123 fluids in two tiers, these nine are tier A)

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
partials sit at the double-precision floor (amended, §16.2: seven more term types, measured over 123 fluids). The NA term at δ = 1 follows S05 §3.2's zero-jet rule (A03 state
`delta_one`, water and CO2 only). A term type outside the table is a generator refusal (claim C1), never a skip.

### 2.3 Properties

Every property is S05 §3.1's closed form in the jet, with that fluid's R and M, molar SI, and `lnphi_<id>` named by
the component id. (T, P) derivatives follow S05 §3.3, the identities I1–I9 S05 §3.4, saturation S05 §3.5. The
n-derivatives are exactly 0.0.

## 3. The provider contract

### 3.1 Module, class and instances

- Module `src/openflowsheet/thermo/coolprop_heos.py`; `PROVIDER_ID = "coolprop-heos-v1"`;
  `REFERENCE_CONVENTION = "COOLPROP-DEF-ref-v1"` (§3.5).
- (Amended, §16.8: any id of §16.3; excluded fluids are reported.) `CoolPropHeosProvider(component_id)` for `component_id` in §2.1's ids; any other id raises `ValueError` at
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
- **`implementation_sha256`** (amended, §16.9: adds the fluid-table module's hash) = SHA-256 of the canonical JSON of
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

### 6.1 Per-fluid constants (rules; the generator emits the values, the module mirrors them bitwise, A01; T_lo and P_hi amended, §16.4)

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
argument.) The generator recomputes these (C9). (Amended, §16.0 E1: N2's T_lo is 82.8 K.)

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
  melting line (C9; not for H2O, §6.1). (Amended, §16.0 E2 and §16.4: the grid starts at max(p_t, P_lo, p_m,min).)

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

## 7. Registered states (by rule; the generator emits the concrete values; tier A — tier B is §16.6)

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

## 8. Generator plan (`s07_reference.py`; WO-S07-1b) and its self-claims (amended, §16.7)

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

## 9. Assertions (applicability by tier and A33–A35: §16.10)

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

### 9.1 Tolerances: floor and margin (tier B: §16.11)

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
- **Q-4 (closed by Frank, 2026-10-23: "Yes, they wait"): may the cryogenic liquids wait?** That is §6.2's cut. Asked as Q-S07-1 in
  `docs/FRANK_QUESTIONS.md`. **Default:** yes, they wait for S07b.
- **Q-5 (closed by Frank, 2026-10-23: "Broad list now"; §16): more CoolProp fluids.** **Default:** none until a case needs a
  pure-fluid stream of a component outside the nine. Each addition is a generator run, a §2.1 row and a register
  entry.

## 12. Work orders (superseded by §16.14; each ≤ ~100k context; the lead lane is build for all three, and the design lane reviews WO-S07-1's generator before WO-S07-2 starts)

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

## 13. Manifest check list (`evidence/S07/<commit>/manifest.json`; extended, §16.15)

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

## 15. What this document does not establish (extended, §16.17)

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

## 16. Amendment 1 — the broad fluid list (2026-10-23; R-623)

### 16.0 Authority, trigger and precedence

- **Trigger.** Frank, 2026-10-23 (`docs/FRANK_QUESTIONS.md`, S07). Asked whether S07 starts with the nine S04 fluids
  and adds more later, he chose **"Broad list now"**. On Q-S07-1 he answered **"Yes, they wait"**: the cryogenic
  liquids stay with S07b, and the melting-line lower bound stays. §11 Q-4 and Q-5 are closed by these answers.
- **Authority.** ADR 0046 (Proposed) with its Amendment 1 note, and R-623. Consistent with `interfaces-frozen.md` §1
  (no Protocol, result type or field changes) and with the component-record id pattern
  `^[A-Za-z0-9][A-Za-z0-9_.:-]*$` (`schemas/component-record.schema.json`).
- **Precedence.** Where this section and §1–§15 differ, this section governs. Everything it does not name stands,
  including every tier-A expectation and tolerance.
- **It establishes:** the selection rule and the resulting 123 fluids (§16.1, §16.3); seven added term types (§16.2);
  the lower bound for fluids without a melting line (§16.4); verification by tier, and what each tier is and is not
  (§16.5); tier-B registered states (§16.6); the generator, provider and identity amendments (§16.7–§16.9);
  applicability by tier, three new assertions and the amended tolerances (§16.10, §16.11); rights (§16.12); open
  questions (§16.13); re-sized work orders (§16.14).
- **Errata found while measuring.** They are corrected here, not worked around downstream.
  - **E1.** §6.1 states N2's T_lo as 82.9 K. N2's T_m(100 MPa) is 82.7993 K, so the rule gives
    ⌈827.993⌉/10 = **82.8 K**. The rule was right and the stated value was mis-rounded. The generator's value governs
    (A01).
  - **E2.** C9's grid (§6.4) must start at max(p_t, P_lo, p_m,min), where p_m,min = `melting_line(iP_min, ·, ·)`.
    Started at p_t, CoolProp raises at the first grid point for N2, H2O, Ar and CH4, because their EOS triple pressures
    lie below their melting lines' own lower limits: N2 12519.78 < 12523 Pa, H2O 611.6548 < 611.657 Pa,
    CH4 11696.06 < 11700 Pa, Ar 68892.48 < 69688.0 Pa (m8). As written, C9 would have refused for four of the nine.
  - **E3.** §2.1 gives O2's `BibTeX_EOS` as `Schmidt-FPE-1985`. The full string is
    `Schmidt-FPE-1985,Stewart-JPCRD-1991`, and `data_provenance` carries the full string.
  - **E4.** "Every fluid has exactly one EOS" (§2.1, C1) holds for the nine but not for the broad set: 21 admitted
    fluids list more than one EOS. HEOS evaluates `EOS[0]`, and the generator parses `EOS[0]` alone. m7 shows that
    CoolProp's partials equal `EOS[0]`'s closed forms at the floor for all 21.

### 16.1 The selection rule (decided; R-623)

The rule is applied to CoolProp 8.0.0's `FluidsList` (136 names; m6). A fluid is admitted iff S1–S5 all hold. The
generator computes the admitted list by these rules and compares it with its literal list (C15). A mismatch is a
refusal.

| rule | statement | excluded by it |
| --- | --- | --- |
| S1 | `EOS[0].pseudo_pure` is false | 6: Air, R404A, R407C, R410A, R507A, SES36 |
| S2 | every term type of `EOS[0]` (α° and αʳ) has a closed form in §2.2 or §16.2 | 2: n-Heptane, D6 (`IdealGasHelmholtzCP0AlyLee`, §16.2) |
| S3 | §16.4's rule gives T_lo < 0.99·T_c (a saturation range of at least 1 % of T_c) | 2: Helium (T_lo = 14.3 K, T_c = 5.195 K), ParaHydrogen (T_lo = 34.2 K, T_c = 32.94 K) |
| S4 | the near-critical box lies inside the domain box: T_hi > T_c(1 + 2e-3) and P_hi > p_c(1 + 8e-3) | 3: MD2M (T_hi = 600 K < 600.6 K), R236EA (T_hi = 412 K < T_c = 412.41 K), R161 (P_hi = 5.0 MPa < p_c = 5.01 MPa) |
| S5 | the generator's claims C1–C19 hold for the fluid | none forecast: m8 checks C6, C8, C9, C10 and whether `PropsSI` answers at every C11 state, in double precision, for all 123 |

**Result: 123 fluids.** Tier A is the nine S04 fluids. Tier B is the other 114. Thirteen are excluded. Each excluded
fluid and its reason are emitted (ref `excluded`) and reported by the provider (§16.8), so none goes missing silently.

**Why each rule.**
- S1: a pseudo-pure EOS describes a mixture as if it were pure. Its "saturation" has no dew–bubble split, so S05's
  phase rule would make a false claim about it.
- S2: the expectation must come from a closed form. A term type whose form does not reproduce CoolProp cannot supply
  an expectation (rule 1).
- S3 and S4: §6.3's phase rule and claims C6–C7 presume a saturation curve that ends at a critical point inside the
  box. A fluid whose box lacks one would need a different phase rule.
- S5: the generator never emits a fluid whose claims fail. If one fails in WO-S07-1b, the build lane stops, and the
  design lane removes the fluid by amendment with the measured reason. There is no silent skip.
- Helium and ParaHydrogen wait for S07b with the other cryogenic liquids.

### 16.2 Added term types (closed forms; measured)

Seven term types beyond §2.2, all evaluated on `EOS[0]` with τ = T_red/T and δ = ρ/ρ_red as in §2.2:

| | type | contribution | admitted users |
| --- | --- | --- | --- |
| PEG | `IdealGasHelmholtzPlanckEinsteinGeneralized` | Σ n ln(c + d·exp(t τ)) | 1 (Fluorine) |
| CP | `IdealGasHelmholtzCP0PolyT` | Σ_k A(c_k, t_k), with the term's own `Tc` and `T0` | 21 |
| CC | `IdealGasHelmholtzCP0Constant` | A(`cp_over_R`, 0), with the term's own `Tc` and `T0` | 4 |
| E | `ResidualHelmholtzExponential` | Σ n δ^d τ^t exp(−g δ^l), taken literally (g = 0 gives 1) | 10 |
| DE | `ResidualHelmholtzDoubleExponential` | Σ n δ^d τ^t exp(−gd δ^ld − gt τ^lt) | 1 (Methanol) |
| L5 | `ResidualHelmholtzLemmon2005` | Σ n δ^d τ^t · (exp(−δ^l) if l > 0, else 1) · (exp(−τ^m) if m > 0, else 1) | 1 (R125) |
| GB | `ResidualHelmholtzGaoB` | Σ n δ^d τ^t exp(η(δ − ε)² + 1/(β(τ − γ)² + b)), η as stored (negative) | 1 (Ammonia) |

For a cp°/R term c·T^t, A(c, t) = (1/T)∫_{T0}^{T} c T'^t dT' − ∫_{T0}^{T} c T'^(t−1) dT', with T = Tc/τ and
τ0 = Tc/T0. In closed form:
- t = 0: c(1 − τ/τ0 + ln(τ/τ0));
- t = −1: c[(τ/Tc) ln(τ0/τ) + (τ − τ0)/Tc];
- otherwise: −c Tc^t τ^(−t)/(t(t + 1)) − c T0^(t+1) τ/(Tc(t + 1)) + c T0^t/t.

**Measured (m7).** 30-digit closed forms, differentiated numerically, reproduce CoolProp's twenty partials at §2.2's
five points for all 123 admitted fluids, in |Δ|/max(|ref|, 1):
- α°: ≤ 4.6e-14;
- αʳ, total order ≤ 2: ≤ 1.05e-12 (R22, αʳ_ττ at (0.8, 2.4)); the next worst is 6.6e-14, and the median 2.3e-15;
- αʳ, order 3: ≤ 6.9e-13 (MM, αʳ_δδδ at (0.95, 0.02)); median 2.9e-14.

The worst over each added type's users: PEG 2.1e-15 (α°), CP 4.6e-14 (α°), CC 2.5e-15 (α°), E 1.0e-13 (αʳ),
DE 1.5e-14, L5 4.6e-14, GB 5.0e-13.

**Not admitted: `IdealGasHelmholtzCP0AlyLee`.** The cp° integral of the Aly–Lee form
c0 + c1(u/sinh u)² + c3(v/cosh v)², with u = c2/T and v = c4/T, reproduces CoolProp's α°_ττ to ≤ 3.3e-14. But α° and
α°_τ differ by a + bτ: b = 6.832331 for n-Heptane and 9.861130 for D6 (m7 diagnostic, recorded in §16.16). So
CoolProp's integration constants for this type are not those of the cp° integral from T0. This document will not
encode a reverse-engineered constant as an expectation (§16.13 Q-A1-2).

### 16.3 Ids, tiers and the fluid table

- **Component ids.** Tier A keeps the S04 ids (§2.1). A tier-B id is the CoolProp name with `(` replaced by `_` and
  `)` deleted. Seven names change, for example `R1234ze(E)` → `R1234ze_E`. Every id matches the component-record
  pattern, the ids are unique, and so are the CAS numbers (C15; m8 asserts all three). Property names are
  `lnphi_<id>` and derivative inputs `n_<id>`.
- **CAS.** Each fluid's CAS number (JSON `INFO.CAS`, a fact, not a coefficient) is a constant (A01). The binding
  follow-on (§12.4) maps component records to provider fluids by CAS, not by name.
- **Tier** is a property of the fluid. It is emitted in ref `fluids` and reported by `describe()` (A34).
  **A** = the nine, judged by every §9 assertion as written. **B** = the 114 others, judged by §16.10's subset.
- **Bound kind** (§16.4's T_lo rule): **M** = melting line at P_hi; **T** = triple point exactly, because the melting
  line lies below T_t (H2O, HeavyWater); **E** = triple-point estimate, because the pinned data have no melting line.

The table below was measured by m8 with CoolProp 8.0.0. The generator recomputes every value, and its claims govern
(C15, A01). T_lo, T_hi and P_hi follow §16.4.

| # | id | CoolProp name | EOS (`BibTeX_EOS`) | T_lo bound | T_lo, K | T_hi, K | P_hi, Pa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | H2O | Water | Wagner-JPCRD-2002 | T | 273.16 | 1273.15 | 1e+08 |
| 2 | CO2 | CarbonDioxide | Span-JPCRD-1996 | M | 236.1 | 1273.15 | 1e+08 |
| 3 | N2 | Nitrogen | Span-JPCRD-2000 | M | 82.8 | 1273.15 | 1e+08 |
| 4 | O2 | Oxygen | Schmidt-FPE-1985,Stewart-JPCRD-1991 | M | 63.1 | 1273.15 | 8e+07 |
| 5 | Ar | Argon | Tegeler-JPCRD-1999 | M | 107 | 1273.15 | 1e+08 |
| 6 | CH4 | Methane | Setzmann-JPCRD-1991 | M | 114.3 | 625 | 1e+08 |
| 7 | C2H6 | Ethane | Buecker-JPCRD-2006 | M | 105.4 | 675 | 1e+08 |
| 8 | C3H8 | n-Propane | Lemmon-JCED-2009 | M | 94.7 | 650 | 1e+08 |
| 9 | H2 | Hydrogen | Leachman-JPCRD-2009 | M | 31.4 | 1000 | 1e+08 |
| 10 | 1-Butene | 1-Butene | Lemmon-FPE-2005 | E | 92.2 | 525 | 5e+06 |
| 11 | Acetone | Acetone | Lemmon-JCED-2006 | E | 187.8 | 550 | 5.2e+06 |
| 12 | Ammonia | Ammonia | Gao-JPCRD-2020 | E | 221 | 725 | 1.3e+07 |
| 13 | Benzene | Benzene | Thol-HTHP-2012 | E | 293.8 | 725 | 5.4e+06 |
| 14 | CarbonMonoxide | CarbonMonoxide | Lemmon-JCED-2006 | M | 87.7 | 500 | 1e+08 |
| 15 | CarbonylSulfide | CarbonylSulfide | Lemmon-JCED-2006 | E | 143.9 | 650 | 7.1e+06 |
| 16 | Chlorine | Chlorine | Thol-AICHE-2021 | E | 186.9 | 525 | 8.5e+06 |
| 17 | cis-2-Butene | cis-2-Butene | Lemmon-FPE-2005 | E | 141.1 | 525 | 5e+06 |
| 18 | CycloHexane | CycloHexane | Zhou-JPCRD-2014 | M | 329.4 | 700 | 1e+08 |
| 19 | Cyclopentane | Cyclopentane | Gedanitz-JCED-2015 | E | 188.9 | 550 | 5.1e+06 |
| 20 | CycloPropane | CycloPropane | Polt-CT-1992 | E | 290 | 473 | 6.2e+06 |
| 21 | D4 | D4 | Thol-THESIS-2015 | E | 304.8 | 1200 | 5e+06 |
| 22 | D5 | D5 | Thol-FPE-2019-siloxanes | E | 237.3 | 630 | 5e+06 |
| 23 | Deuterium | Deuterium | Richardson-JPCRD-2013 | M | 36.8 | 600 | 1e+08 |
| 24 | Dichloroethane | Dichloroethane | Thol-THESIS-2015 | E | 251.3 | 1000 | 5.8e+06 |
| 25 | DiethylEther | DiethylEther | Thol-IJT-2014 | E | 283.5 | 548 | 5e+06 |
| 26 | DimethylCarbonate | DimethylCarbonate | Zhou-JPCRD-2011 | E | 292.1 | 600 | 5.4e+06 |
| 27 | DimethylEther | DimethylEther | Wu-JPCRD-2011 | E | 139.5 | 525 | 5.9e+06 |
| 28 | Ethanol | Ethanol | Schroeder-JPCRD-2014 | M | 171.3 | 650 | 1e+08 |
| 29 | EthylBenzene | EthylBenzene | Zhou-JPCRD-2012 | E | 187.2 | 700 | 5e+06 |
| 30 | Ethylene | Ethylene | Smukala-JPCRD-2000 | M | 127.2 | 450 | 1e+08 |
| 31 | EthyleneOxide | EthyleneOxide | Thol-CES-2015,Thol-CES-2015-CORR,Thol-THESIS-2015 | E | 173.7 | 1000 | 8.1e+06 |
| 32 | Fluorine | Fluorine | deReuck-BOOK-1990 | M | 55.5 | 300 | 2e+07 |
| 33 | HeavyWater | HeavyWater | Herrig-JPCRD-2019 | T | 276.969 | 825 | 1e+08 |
| 34 | HFE143m | HFE143m | Akasaka-IJR-2012 | E | 252 | 420 | 5e+06 |
| 35 | HydrogenChloride | HydrogenChloride | Thol-JCED-2018-HCl | E | 173.8 | 670 | 9.2e+06 |
| 36 | HydrogenSulfide | HydrogenSulfide | Lemmon-JCED-2006 | E | 206.3 | 760 | 9.9e+06 |
| 37 | IsoButane | IsoButane | Buecker-JPCRD-2006B | M | 125.4 | 575 | 3.5e+07 |
| 38 | IsoButene | IsoButene | Lemmon-FPE-2005 | E | 139.1 | 550 | 5e+06 |
| 39 | Isohexane | Isohexane | Lemmon-JCED-2006 | E | 125.6 | 550 | 5e+06 |
| 40 | Isopentane | Isopentane | Lemmon-JCED-2006 | M | 124.4 | 500 | 1e+08 |
| 41 | Krypton | Krypton | Lemmon-JCED-2006 | M | 143.9 | 750 | 1e+08 |
| 42 | m-Xylene | m-Xylene | Zhou-JPCRD-2012 | E | 236.6 | 700 | 5e+06 |
| 43 | MD3M | MD3M | Thol-FPE-2019-siloxanes | E | 201.6 | 673 | 5e+06 |
| 44 | MD4M | MD4M | Thol-FPE-2019-siloxanes | E | 224.9 | 655 | 5e+06 |
| 45 | MDM | MDM | Thol-JCED-2017-siloxanes | E | 196.6 | 575 | 5e+06 |
| 46 | Methanol | Methanol | deReuck-BOOK-1993 | M | 189.8 | 620 | 1e+08 |
| 47 | MethylLinoleate | MethylLinoleate | Huber-EF-2009 | E | 273 | 1000 | 5e+06 |
| 48 | MethylLinolenate | MethylLinolenate | Huber-EF-2009 | E | 273 | 1000 | 5e+06 |
| 49 | MethylOleate | MethylOleate | Huber-EF-2009 | E | 266.2 | 1000 | 5e+06 |
| 50 | MethylPalmitate | MethylPalmitate | Huber-EF-2009 | E | 317.9 | 1000 | 5e+06 |
| 51 | MethylStearate | MethylStearate | Huber-EF-2009 | E | 327.5 | 1000 | 5e+06 |
| 52 | MM | MM | Thol-FPE-2016-MM,Thol-THESIS-2015 | E | 215.2 | 673 | 5e+06 |
| 53 | n-Butane | n-Butane | Buecker-JPCRD-2006B | M | 136.9 | 575 | 1.2e+07 |
| 54 | n-Decane | n-Decane | Lemmon-JCED-2006 | E | 255.7 | 675 | 5e+06 |
| 55 | n-Dodecane | n-Dodecane | Lemmon-EF-2004 | E | 276.8 | 700 | 5e+06 |
| 56 | n-Hexane | n-Hexane | Thol-FPE-2019-alkanes-hexane | E | 186.8 | 600 | 5e+06 |
| 57 | n-Nonane | n-Nonane | Lemmon-JCED-2006 | E | 230.7 | 600 | 5e+06 |
| 58 | n-Octane | n-Octane | Beckmueller-IJT-2019-octane | E | 227.2 | 730 | 5e+06 |
| 59 | n-Pentane | n-Pentane | Thol-FPE-2019-alkanes-pentane | M | 156.3 | 650 | 1e+08 |
| 60 | n-Perfluorobutane | n-Perfluorobutane | Gao-2022-CxFy | E | 151.2 | 450 | 5e+06 |
| 61 | n-Perfluorohexane | n-Perfluorohexane | Gao-2022-CxFy | E | 196.5 | 450 | 5e+06 |
| 62 | n-Perfluoropentane | n-Perfluoropentane | Gao-2022-CxFy | E | 155.7 | 500 | 5e+06 |
| 63 | n-Undecane | n-Undecane | Aleksandrov-TE-2011 | E | 260 | 700 | 5e+06 |
| 64 | Neon | Neon | Thol-JPCRD-2019-Neon | M | 37.1 | 725 | 1e+08 |
| 65 | Neopentane | Neopentane | Lemmon-JCED-2006 | E | 269.5 | 550 | 5e+06 |
| 66 | NitrousOxide | NitrousOxide | Lemmon-JCED-2006 | E | 197 | 525 | 8e+06 |
| 67 | Novec649 | Novec649 | McLinden-JCED-2015-Novec649 | E | 173.3 | 500 | 5e+06 |
| 68 | o-Xylene | o-Xylene | Zhou-JPCRD-2012 | E | 260.4 | 700 | 5e+06 |
| 69 | OrthoDeuterium | OrthoDeuterium | Richardson-JPCRD-2013 | M | 36.8 | 600 | 1e+08 |
| 70 | OrthoHydrogen | OrthoHydrogen | Leachman-JPCRD-2009 | M | 31.4 | 1000 | 1e+08 |
| 71 | p-Xylene | p-Xylene | Zhou-JPCRD-2012 | E | 300.8 | 700 | 5e+06 |
| 72 | ParaDeuterium | ParaDeuterium | Richardson-JPCRD-2013 | M | 36.8 | 600 | 1e+08 |
| 73 | Propylene | Propylene | Lemmon-PROPYLENE-2013 | M | 96.9 | 575 | 1e+08 |
| 74 | PropyleneGlycol | PropyleneGlycol | Eisenbach-JPCRD-2021 | E | 230.3 | 680 | 8.1e+06 |
| 75 | Propyne | Propyne | Polt-CT-1992 | E | 290.2 | 474 | 6.3e+06 |
| 76 | R11 | R11 | Jacobsen-FPE-1992 | E | 170.9 | 625 | 5e+06 |
| 77 | R1123 | R1123 | Akasaka-IJR-2020-R1123 | E | 205.2 | 480 | 5.1e+06 |
| 78 | R113 | R113 | Marx-BOOK-1992 | E | 248.8 | 525 | 5e+06 |
| 79 | R1130_E | R1130(E) | Huber-IJT-2025-R1130E | E | 236.3 | 525 | 5.8e+06 |
| 80 | R1132_E | R1132(E) | Akasaka-IJT-2024-R1132E | E | 253.7 | 400 | 5.7e+06 |
| 81 | R114 | R114 | Platzer-BOOK-1990 | E | 286.9 | 507 | 5e+06 |
| 82 | R115 | R115 | Lemmon-JCED-2016-365227 | E | 182.3 | 550 | 5e+06 |
| 83 | R116 | R116 | Lemmon-JCED-2006 | E | 181.8 | 425 | 5e+06 |
| 84 | R12 | R12 | Marx-BOOK-1992 | E | 122 | 525 | 5e+06 |
| 85 | R1224YDZ | R1224YDZ | Akasaka-IJT-2023-R1224ydZ | E | 165.7 | 473.15 | 5e+06 |
| 86 | R123 | R123 | Younglove-JPCRD-1994 | E | 174.3 | 600 | 5e+06 |
| 87 | R1233zd_E | R1233zd(E) | Akasaka-JPCRD-2022-R1233zdE | E | 174.1 | 450 | 5e+06 |
| 88 | R1234yf | R1234yf | Lemmon-IJT-2022 | E | 127.7 | 410 | 5e+06 |
| 89 | R1234ze_E | R1234ze(E) | Thol-IJT-2016-R1234zeE | E | 177.1 | 420 | 5e+06 |
| 90 | R1234ze_Z | R1234ze(Z) | Akasaka-JCED-2019 | E | 286.7 | 440 | 5e+06 |
| 91 | R124 | R124 | deVries-ICR-1995 | E | 126 | 470 | 5e+06 |
| 92 | R1243zf | R1243zf | Akasaka-IJT-2025-R1243zf | E | 128.5 | 430 | 5e+06 |
| 93 | R125 | R125 | Lemmon-JPCRD-2005 | E | 181.2 | 500 | 5e+06 |
| 94 | R13 | R13 | Platzer-BOOK-1990 | E | 103.1 | 450 | 5e+06 |
| 95 | R1336mzz_E | R1336mzz(E) | Akasaka-IJT-2023 | E | 210.2 | 410 | 5e+06 |
| 96 | R1336mzz_Z | R1336mzz(Z) | McLinden-JCED-2020-R1336mzzZ | E | 191.8 | 500 | 5e+06 |
| 97 | R134a | R134a | TillnerRoth-JPCRD-1994 | E | 178.4 | 455 | 5e+06 |
| 98 | R13I1 | R13I1 | Lemmon-JCED-2016-365227 | E | 126 | 420 | 5e+06 |
| 99 | R14 | R14 | Platzer-BOOK-1990 | E | 126 | 623 | 5e+06 |
| 100 | R141b | R141b | Lemmon-JCED-2006 | E | 178.2 | 500 | 5e+06 |
| 101 | R142b | R142b | Lemmon-JCED-2006 | E | 149.9 | 470 | 5e+06 |
| 102 | R143a | R143a | LemmonJacobsen-JPCRD-2000 | E | 169.5 | 650 | 5e+06 |
| 103 | R152A | R152A | Outcalt-JPCRD-1996-R152A | E | 162.3 | 500 | 5e+06 |
| 104 | R21 | R21 | Platzer-BOOK-1990 | E | 211.8 | 473 | 5.9e+06 |
| 105 | R218 | R218 | Lemmon-JCED-2006 | E | 131.8 | 440 | 5e+06 |
| 106 | R22 | R22 | Kamei-IJT-1995 | E | 122.1 | 550 | 5.5e+06 |
| 107 | R227EA | R227EA | Lemmon-JCED-2016-365227 | E | 153.7 | 475 | 5e+06 |
| 108 | R23 | R23 | Penoncello-JPCRD-2003 | E | 124.4 | 475 | 5.4e+06 |
| 109 | R236FA | R236FA | Pan-FPE-2012 | E | 188.6 | 400 | 5e+06 |
| 110 | R245ca | R245ca | Zhou-IJT-2016-R245ca | E | 205.8 | 450 | 5e+06 |
| 111 | R245fa | R245fa | Akasaka-JPCRD-2015-R245fa | E | 179.7 | 440 | 5e+06 |
| 112 | R32 | R32 | TillnerRoth-JPCRD-1997 | E | 145.1 | 435 | 6.4e+06 |
| 113 | R365MFC | R365MFC | Lemmon-JCED-2016-365227 | E | 251 | 500 | 5e+06 |
| 114 | R40 | R40 | Thol-IJT-2014 | E | 247.8 | 730 | 7.7e+06 |
| 115 | R41 | R41 | Lemmon-JCED-2006 | E | 138.3 | 425 | 6.5e+06 |
| 116 | RC318 | RC318 | Platzer-BOOK-1990 | E | 245.1 | 623 | 5e+06 |
| 117 | SulfurDioxide | SulfurDioxide | Gao-JCED-2016 | E | 214.9 | 525 | 8.7e+06 |
| 118 | SulfurHexafluoride | SulfurHexafluoride | Guder-JPCRD-2009 | E | 234.8 | 625 | 5e+06 |
| 119 | Tetrahydrofuran | Tetrahydrofuran | Fiedler-IJT-2023-THF | E | 174.5 | 600 | 5.9e+06 |
| 120 | Toluene | Toluene | Lemmon-JCED-2006 | E | 186.9 | 700 | 5e+06 |
| 121 | trans-2-Butene | trans-2-Butene | Lemmon-FPE-2005 | E | 176 | 525 | 5e+06 |
| 122 | VinylChloride | VinylChloride | Thol-IJT-2022-VinylChloride | E | 126.8 | 430 | 6.2e+06 |
| 123 | Xenon | Xenon | Lemmon-JCED-2006 | E | 171.9 | 750 | 6.5e+06 |

Counts: 123 fluids; bound M 25, T 2, E 96. The 21 that list more than one EOS (E4) are Ammonia, D4, D5,
HydrogenChloride, MD3M, MD4M, MDM, MM, Methanol, Neon, R11, R123, R1234yf, R1234ze(E), R1234ze(Z), R152A, R245fa,
SulfurDioxide, n-Hexane, n-Octane and n-Pentane.

### 16.4 The lower bound (amends §6.1's T_lo and P_hi rows; R-623)

T_hi, P_lo, T_σ,max, the near-critical box, ρ_max, ε_σ and the canary keep §6.1's rules for every fluid. T_lo and
P_hi follow the fluid's bound kind:

| bound | applies when | P_hi | T_lo |
| --- | --- | --- | --- |
| M | the pinned data have a melting line, and T_m rises on C9's grid | min(JSON p_max, 1.0e8 Pa) | ⌈10·T_m(P_hi)⌉/10 K |
| T | the pinned data have a melting line, and T_m ≤ T_t and non-increasing on C9's grid (an ice-Ih-like branch) | min(JSON p_max, 1.0e8 Pa) | T_t, CoolProp's `Ttriple()`, exactly |
| E | the pinned data have no melting line | min(JSON p_max, max(5.0e6 Pa, ⌈1.1·p_c⌉₂)) | ⌈10·T_t·(1 + κ·P_hi)⌉/10 K, with κ = 1.0e-8 Pa⁻¹ |

- ⌈x⌉₂ rounds up to two significant digits. Every ceiling is taken on the exact decimal value of the double
  (`Decimal(repr(x))`), with no fudge term. p_c is §6.1's EOS critical pressure, solved at 50 digits.
- **C9, amended (E2).** For M and T fluids, the grid of 20 logarithmically spaced pressures runs from
  max(p_t, P_lo, p_m,min) to P_hi, and p_m,max ≥ P_hi. M requires T_m to increase strictly on the grid. T requires
  T_m ≤ T_t and non-increasing on it. A fluid that fits neither is a refusal (S5).
- **The T fluids.** T_m(100 MPa) is 264.21 K for H2O and 268.49 K for HeavyWater, both below T_t (m6). Water's T_lo
  was already S05 §4.1's T_t.

**Why κ = 1e-8 Pa⁻¹ (0.01 MPa⁻¹).**
- κ bounds the relative melting slope (T_m(P)/T_t − 1)/(P − p_t) of a fluid whose melting line is not in the data.
- Measured over the 25 M fluids, on C9's grid (from m8's data): the largest for T_t ≥ 20 K is Neon's, 0.00622 MPa⁻¹.
  The largest among non-quantum fluids is IsoButane's, 0.00382, followed by N2's, 0.00349.
- So κ sits 1.6× above Neon and 2.6× above every non-quantum fluid. Only the hydrogen isotopes (T_t < 20 K) exceed
  it, and all of them have melting lines.
- Simon-type melting curves are concave in T(P), so the slope near p_t bounds the rise at P_hi.
- Claim C18 makes this executable: κ ≥ 1.5 × the largest such slope over the M fluids with T_t ≥ 20 K, or the
  generator refuses.

**Why the pressure floor is 5 MPa and 1.1·p_c.**
- With κ fixed, T_lo/T_t = 1 + κ·P_hi. That is 2.0 at 100 MPa, which would be useless, and 1.05 at 5 MPa.
- 5 MPa covers the condensing pressures of refrigerant and ORC cycles and most pure-fluid process streams of these
  fluids.
- The 1.1·p_c floor keeps the critical point and the near-critical box inside the box (S4), which §6.3's phase rule
  needs. For ammonia it gives P_hi = 13 MPa and T_lo = 221.0 K, still below the 239.8 K normal boiling point.
- Of the 96 E fluids, 67 have P_hi = 5 MPa and the others up to 13 MPa. T_lo/T_t lies in [1.05, 1.13].

**What it costs (E fluids).** Liquid within 5–13 % of T_t above the triple point is out of domain, and so is every
state above P_hi. For example, liquid p-xylene at 298 K (T_lo = 300.8 K), liquid D4 at 298 K (304.8 K) and compressed
liquid R134a above 5 MPa are refused. Liquid benzene at 298 K (T_lo = 293.8 K), toluene from 186.9 K, ammonia from
221.0 K, and every vapour and supercritical state up to P_hi are inside.

**What it does not establish.** κ is an empirical bound taken from CoolProp's melting lines of other fluids. It is
not a property of the E fluids. A fluid whose relative melting slope exceeds 0.01 MPa⁻¹ would have a thin solid sliver
near (T_lo, P_hi) inside its box, answered as LIQUID. The provider says so: each E fluid carries the
`numerical_limitations` sentence of §16.8 (A34).

### 16.5 Verification by tier (decided; R-623)

What each check is:

| | check | what it verifies | kind |
| --- | --- | --- | --- |
| V1 | A03, A04: CoolProp's jet against 50-digit closed forms of the same coefficients | CoolProp evaluates the functional form with the coefficients it ships, and the provider calls it at the right (T, ρ) with the right reducing constants | implementation verification; shares CoolProp's data |
| V2 | A05, A08, A09: provider answers against 50-digit solves of those closed forms | the provider's density roots, saturation and property formulas | implementation verification |
| V3 | C11: CoolProp's own `PropsSI` against the generator | the generator, against an independent solver | admission of the generator; shares the data |
| V4 | A10, A11, A17, A22, C13's identities | the thermodynamic consistency of the provider's own answers | self-consistency |
| V5 | A23: water against S05, whose coefficients were checked digit by digit against the printed IAPWS release | CoolProp's water data and the provider, against an independent transcription and implementation | independent cross-check (H2O) |
| V6 | A24: cp^ig against the S04 records, 2 % | the ideal-gas part, against an independent correlation | independent but weak (the nine) |
| V7 | C16, A35: closed forms against published EOS check values (§16.5.2) | CoolProp's coefficients are the paper's | data verification against the source |

None of V1–V7 is empirical validation. No check here compares an EOS with experiment (§15).

#### 16.5.1 What each tier gets

- **Tier A:** V1–V6, by every §9 assertion as written. Verification string `independent:S05` for H2O and
  `independent:S04-ig` for the other eight.
- **Tier B:** V1–V4, at §16.6's registered states, with §16.10's applicability. Verification string
  `self-consistent`. It means: CoolProp evaluates its coefficients correctly, and the provider's answers are correct
  for those coefficients and consistent with each other. Nothing in S07 checks a tier-B fluid's coefficients against
  their source. A tier-B fluid reports `published-check` only through §16.5.2.

#### 16.5.2 Published check values (a mechanism; none required in S07)

- **Measured: CoolProp's fluid file provides none.** The union of the top-level keys over all 136 fluid JSONs is
  {ANCILLARIES, EOS, INFO, STATES, TRANSPORT} (m6). `STATES` holds anchors that CoolProp computed itself
  (`hs_anchor`, `sat_min_*`). They are not published values, they are not independent, and they are not used.
- **Papers.** Many EOS papers print a table of values for checking computer programs: typically p, c_v and w,
  sometimes α partials, at stated (T, ρ), to 9–10 significant digits. Transcribing them needs access to each paper
  and a checked transcription. S07 requires none (§16.13 Q-A1-3).
- **The mechanism**, so that each later addition is a data row: `benchmarks/s07/published_checks.yaml`, committed
  from WO-S07-1b on with `rows: []`. A row is `{fluid: <id>, source: <citation>, table: <table id in the source>,
  T: <K>, rho: <mol/m³>, quantity: <p | cv | cp | w | alphar | …>, value: <as printed>, digits: <significant digits
  printed>}`. A density printed per kilogram is converted with the fluid's M, and the row says so.
- **C16.** For every row, the 50-digit closed form agrees with `value` within one unit in its last printed digit.
  Every row names a source. The file's SHA-256 is in ref.
- **A35.** A tier-B fluid reports `published-check` iff it has at least 3 rows, at least 2 distinct densities among
  them, and all of them pass C16. Three rows, because one passing value can be an accident at a state where the
  wrong term happens to be small. With zero rows, A35 asserts that no fluid reports `published-check`.
- **Why one unit in the last printed digit.** The printed value is the paper's EOS rounded to its printed digits
  (≤ 0.5 unit). The closed form evaluates the same coefficients at 50 digits. The second half-unit covers the paper's
  own double-precision evaluation. A coefficient that differs from the paper's moves a value by its relative
  difference times its term's share, so this check resolves coefficient differences down to roughly the printed
  precision of the values, not below.

### 16.6 Tier-B registered states (by rule; the generator emits the values)

Per tier-B fluid, 11 registered states with stored values:

| key | where | stored | assertions |
| --- | --- | --- | --- |
| `phi_gas`, `phi_liq`, `phi_dilute` | as §7 | the 20 partials, α° then αʳ, each in `PhiJet` order | A03, A04 |
| `V_sup` | (min(1.5·T_c, T_hi), 0.1·p_c) | h, s, v, Z, cp, lnphi | A05, A07, A17 |
| `V_sub`, `L_sub` | as §7 | as above | A05, A17 |
| `S_dense` | (min(1.2·T_c, T_hi), min(3·p_c, P_hi)) | as above | A05, A15's label, A17 |
| `L_corner`, `V_corner` | as §7 | as above | A05, A17 |
| `sat_mid` | T_mid | Psat, h_V − h_L | A08, A10 |
| `tsat_mid` | P = p_σ(T_mid), rounded to 6 significant digits | Tsat | A09 |

The generator also emits, as states and expected codes without values: §7's band probes (the answered sets and the
refused phase), the refusal probes with their controls (C14), and the A10/A11 temperatures {T_lo, T_mid, T_σ,max}.

- **The clamps** (`min(…, T_hi)`, `min(…, P_hi)`) are written for all fluids. They are inactive for the nine, so
  tier A's §7 states do not change: m8 finds no clamp firing for any of the nine, and C10 asserts that tier A's
  states equal §7's unclamped rule. Over tier B the clamps fire 88 times for `V_sup`, 50 times for `S_dense`'s T and
  86 times for its P (m8).
- **Why these states.** The jets are where each fluid's own coefficients enter, which is the fluid-specific risk. The
  six TP states test the per-fluid constants (R, M, reducing values, brackets, ρ_max) at a vapour, a liquid, a dense
  supercritical state and the two corners. `sat_mid` and `tsat_mid` exercise the saturation solver.
- **Not registered for tier B:** NC states, band values, T and P derivative values, `sat_lo` and `sat_hi` values,
  `s04_ig`. They test generic code that tier A already judges against independent values (A06, A13, NC). A tier-B
  derivative is judged by A04, which checks the third partials where a fluid-specific derivative error would start,
  and by A17, the central differences of the provider's own values.
- **`dropped`.** m8 forecasts it empty for tier B. The literal expected list is fixed at WO-S07-1b's first run, and
  the design lane reviews it: each entry needs its rule's reason.
- **Layout and size.** Jets are stored as a 20-float list (α° then αʳ, `PhiJet` order) and TP states as
  `[T, P, h, s, v, Z, cp, lnphi]`, for both tiers. That is about 150 floats per tier-B fluid. The estimate is about
  0.4 MB for tier B and 0.6–0.9 MB for the whole file. C17 caps the file at 1.5e6 bytes. Past the cap the generator
  refuses, and the design lane amends (fewer tier-B states). The harness is never bent to fit.

### 16.7 Generator amendments (`s07_reference.py`)

- **Inputs.** Add `FluidsList` (C15), `melting_line(iP_min, ·, ·)` and `melting_line(iP_max, ·, ·)` (C9), and
  `benchmarks/s07/published_checks.yaml` (C16).
- **The fluid loop.** Every admitted fluid runs in a worker process (`--jobs N`, default `os.cpu_count()`). The parent
  serializes the results in sorted order, so the bytes do not depend on N. WO-S07-1b checks `--jobs 1` against the
  default once, over the full run, and records the result.
- **Cost (an estimate; WO-S07-1b records the measured time).** m7 needed 0.3 s of CPU per fluid for 100 partials at
  30 digits. With the solves and C8's 31 × 82 bracket points, the budget is up to about 1 min of CPU per fluid, about
  2 h of CPU in all, and a few minutes of wall time on the workstation's 48 threads. `--check` stays a manifest
  command, not a CI test.
- **Claims amended.**
  - C1: every admitted fluid's `EOS[0]` term types are in §2.2 or §16.2, and `EOS[0]` is the EOS parsed (E4).
  - C9: as §16.4.
  - C10: adds that tier A's states equal §7's unclamped rule.
  - C11: holds at every TP state of either tier outside NC. A `PropsSI` exception fails the claim; it is not a skip.
  - C13: holds at every stored TP and saturation state of either tier.
  - C14: per fluid, both tiers.
- **New claims (the generator refuses to emit if any fails):**

| | claim |
| --- | --- |
| C15 | the admitted list computed by S1–S5 equals §16.3's literal list (123, in order); the excluded list with reasons equals the literal 13; each fluid's computed bound kind equals the literal one; the ids match the component-record pattern and are unique; the CAS numbers are unique |
| C16 | §16.5.2 |
| C17 | the output file is at most 1.5e6 bytes |
| C18 | κ ≥ 1.5 × max over the M fluids with T_t ≥ 20 K of (T_m(P)/T_t − 1)/(P − p_t) on C9's grid |
| C19 | `--emit-fluid-table` reproduces the committed `_coolprop_heos_fluids.py` byte for byte (checked by `--check`) |

- **Output additions.** `fluids` (id → CoolProp name, CAS, `BibTeX_EOS`, tier, bound, verification string,
  limitation strings), `excluded` (name → reason), `published_checks` (the file's SHA-256 and the rows per fluid), and
  the tier-B blocks. C3's whitelist grows by these keys only. The schema name stays `s07-reference-v1`, since nothing
  has been emitted under it yet.

### 16.8 Provider amendments

- **The fluid table is its own module,** `src/openflowsheet/thermo/_coolprop_heos_fluids.py`. It holds data only, as
  Python literals.
  - Per fluid: id, CoolProp name, CAS, tier, bound, `BibTeX_EOS`, R, M, T_red, ρ_red, §6.1's constants, the canary,
    `FLUID_DATA_SHA256`, and the verification and limitation strings.
  - `EXCLUDED`: name → reason.
  - It is emitted by `s07_reference.py --emit-fluid-table` and committed (C19, A01). `coolprop_heos.py` holds the
    algorithms only.
  - Why a separate module: 123 fluids of constants would bury the logic, and each file stays reviewable on its own.
    The leading underscore keeps it off the provider surface. If T08's provider scan treats it otherwise, the build
    lane reports it (§16.13 F-5).
- **Construction.** `CoolPropHeosProvider(component_id)` accepts any id of §16.3. An excluded fluid's would-be id, or
  its CoolProp name, raises `ValueError` whose message contains the exclusion reason. Any other unknown id raises
  `ValueError` as before. The class methods `CoolPropHeosProvider.admitted()` and `.excluded()` return the two tables
  (A33). `helmholtz_jet` accepts every admitted id.
- **No fluid-specific code.** `coolprop_heos.py` contains no fluid name or component id as a literal. Every per-fluid
  value comes from the table (A33(c)). A fluid the generic algorithm cannot serve is excluded by amendment, never
  special-cased.
- **`describe()` strings (exact; A34).**
  - `uncertainty` = `"verification: <v>; EOS <BibTeX_EOS> as evaluated by CoolProp 8.0.0; the EOS's own uncertainty
    is not re-validated"`, where `<v>` is `independent:S05` for H2O, `independent:S04-ig` for the other tier-A
    fluids, and, for tier B, `published-check` if §16.5.2's rows qualify and `self-consistent` otherwise.
  - `numerical_limitations` gains, for E fluids only: `"lower temperature bound estimated from the triple point (no
    melting line in CoolProp 8.0.0): T_lo = T_t*(1 + 1e-8/Pa*P_hi); solid states lie inside the box if the melting
    slope exceeds 0.01/MPa*T_t"`.
  - `data_provenance` as §3.2, with the full `BibTeX_EOS` string (E3).
- **Cost.** One `AbstractState` per instance, created at the first evaluation, as before. Nothing per fluid is loaded
  from CoolProp before an instance's first evaluation.

### 16.9 Identity (amends §5.1; R-619 extended by R-623)

- `implementation_sha256` = SHA-256 of the canonical JSON of `{"module_sha256": <SHA-256 of coolprop_heos.py's
  bytes>, "fluid_table_sha256": <SHA-256 of _coolprop_heos_fluids.py's bytes>, "coolprop_version": "8.0.0",
  "coolprop_gitrevision": "ae81610e…"}`. A change to any fluid's constants changes every instance's implementation
  hash. There is one table and one identity, so a cache keyed on it can never mix table versions.
- `data_sha256` keeps its form: per instance, the version, the fluid name and that fluid's canonical JSON hash. The
  broad set adds no shared data hash, because each instance's data are its own fluid's.
- The guard (§5.2) is unchanged and runs per instance: G3 checks the instance's fluid hash and G4 its canary.
- **Moving the pin** (§5.1) now re-runs the generator over every admitted fluid. The id becomes `coolprop-heos-v2` if
  any fluid's hash changes, if any registered value moves outside its tolerance, or if the admitted list changes. A
  fluid that disappears must not do so under the old id.

### 16.10 Assertions: applicability by tier; new A33–A35

| id | tier A | tier B |
| --- | --- | --- |
| A01 | as §9, plus CAS, tier, bound and the strings | as tier A |
| A02, A25, A28 | as §9 (A28 with §16.9's recipe) | as tier A |
| A03 | as §9: \|Δ\| ≤ 1e-12·max(\|ref\|, 1) | `phi_gas`, `phi_liq`, `phi_dilute`: \|Δ\| ≤ 1e-11·max(\|ref\|, 1) |
| A04 | as §9: 1e-11 | as tier A |
| A05 | as §9 | the six TP states of §16.6, with S05 A05's bounds |
| A06 | as §9 | not applied (§16.6) |
| A07 | as §9 | at `V_sup` |
| A08 | as §9 | Psat at `sat_mid`; dPsat/dP is 0.0; dPsat/dT is judged by A11 |
| A09 | as §9 | Tsat at `tsat_mid`; dTsat/dT is 0.0 |
| A10 | as §9 | Maxwell on the provider's own Psat at {T_lo, T_mid, T_σ,max}; h_V − h_L at `sat_mid` against ref |
| A11 | as §9 | at {T_lo, T_mid, T_σ,max} |
| A12, A23 | H2O | not applied |
| A13 | as §9 | the answered sets and refused-phase codes only |
| A14–A16, A18 | as §9 | as §9 (codes, from ref's probes) |
| A17 | as §9 | at the six TP states |
| A19–A21, A24, A26 | as §9 | not applied: generic code paths, or tier-A cross-checks; every tier-B test passes the guard per instance |
| A22 | as §9, plus: `Psat` is `ok` at every grid temperature ≤ T_σ,max | 12 temperatures evenly from T_lo to T_hi, the same pressures and checks, plus the `Psat` item |
| A27, A29, A30 | global, unchanged; A29(c)'s whitelist is C3's as amended (§16.7) | — |
| A31 | as §9 | tier B's stored answers in the digest; outcome (b)'s stop line 1e-10 (§16.11) |
| A32 | as §9, plus (m9)–(m11) below | not applied |

New assertions (test file `tests/test_s07_broad.py`, except A33–A34 for tier A, which sit in
`tests/test_s07_coolprop.py`):

| id | assertion | expectation | tolerance |
| --- | --- | --- | --- |
| A33 | **The fluid list.** (a) `admitted()` equals ref `fluids` (ids, names, CAS, tier, bound, in order), and every admitted id constructs; (b) each of the 13 excluded fluids, by CoolProp name and by its would-be id, raises `ValueError` whose message contains ref's reason, and `excluded()` equals ref `excluded`; (c) the AST of `coolprop_heos.py` contains no string constant equal to an admitted or excluded CoolProp name or id (the table module is exempt) | ref | exact |
| A34 | **Tier and bound are reported.** Per fluid, `describe().uncertainty` begins with `verification: <ref's string>`; E fluids carry §16.8's sentence in `numerical_limitations`, and M and T fluids do not; control: no tier-B string begins `independent:` | ref | exact |
| A35 | **Published checks.** As §16.5.2: a tier-B fluid reports `published-check` iff its rows qualify; with zero rows no fluid does; the file hash recorded in ref equals the committed file's | ref, file | exact |

Added mutations, each failing the named assertion: (m9) the provider reads the fluid table one row off
(`R1234ze_Z`'s row for `R1234ze_E`) → A01, A05; (m10) one E fluid's T_lo is edited to T_t in the table → A01, and A16's
probe below ref's T_lo is answered; (m11) a tier-B fluid reports `independent:S04-ig` → A34.

### 16.11 Tolerances: floors and margins (amends §9.1 for tier B)

- **A03, tier B: 1e-11.** The floor is 1.05e-12 (R22, αʳ_ττ at (0.8, 2.4); m7). It comes from cancellation in
  CoolProp's double-precision sums for an EOS with large terms at liquid density; the median is 2.3e-15. The margin is
  9.5× over the worst fluid. The errors worth catching sit at least 6 decades higher: a permuted slot (O(1)) and a
  wrong reducing constant (≥ 1e-5). Tier A keeps 1e-12, against its own floor of 8.0e-15 at orders ≤ 2.
- **A04, both tiers: 1e-11.** Tier B's order-3 floor is 6.9e-13 (MM), a margin of 14×.
- **A05, A08–A10, tier B: S05's bounds.** The value floor is the jet floor times the conditioning of the density root.
  With the jet floor at ≤ 1.05e-12 and the root's conditioning κ_ρ ≤ 100 away from NC (§9.1's κ, S05), the floor is ≤ 1.1e-10, two decades below 1e-8.
  If WO-S07-2b measures a tier-B worst above 1e-9, it stops for the design lane.
- **A17, tier B.** S05 §6.3's rule. WO-S07-2b measures the floor per fluid and records the worst. Above 1e-11 the
  design lane re-sets the tolerance by amendment (§9.1's rule, unchanged).
- **A31(b), tier B: 1e-10·max(\|x\|, s_f), a pre-registered stop line** (R-622's rule with a tier-B bound).
  - A different FMA contraction perturbs CoolProp's sums by at most their own rounding, which m7 bounds at 1.05e-12 of
    max(|ref|, 1) for the worst fluid.
  - 1e-10 is that worst jet floor times the worst density-root conditioning (κ_ρ ≤ 100). The product is pessimistic:
    the worst floors occur at liquid-like states, where the root is well conditioned (κ_ρ ≪ 1), and the worst
    conditioning occurs at near-saturated vapour, where the jets are small and exact to a few ulp.
  - 1e-10 stays two decades inside A05's 1e-8. Tier B has no NC states.
  - Above 1e-10 the build lane stops, and the design lane amends. Nothing is loosened.

### 16.12 Rights (amends ADR 0046's Rights for the broad set)

- **The argument does not depend on the fluid,** so it covers all 123. CoolProp (MIT) is installed by the user from
  PyPI as the `coolprop` extra. The provider reads each fluid's data at run time from that installation. The project
  copies no coefficient and redistributes nothing of CoolProp.
- **The broad set's coefficients** come from many sources: journal papers (JPCRD, JCED, IJT, FPE, IJR, EF and others),
  two books (Platzer 1990, Marx 1992), theses (Thol 2015), and work associated with REFPROP (RC-01, RC-02). Whether
  CoolProp may distribute them is CoolProp's question. We neither copy nor redistribute them (A29, C3).
- **What the repository gains:**
  - `s07_reference.json`: computed property values at registered states, derived constants and hashes, now for 123
    fluids. It stays out of every `PACKAGED` path (A29).
  - `_coolprop_heos_fluids.py`: derived constants, R, M, the reducing constants, CAS numbers, hashes and citation keys.
    That is the kind of content §3–§6 already put into the packaged module for nine fluids.
  - `published_checks.yaml`, once rows exist: values printed in publications, with their citations. They are facts, a
    handful per fluid, and none is a coefficient.
  - None of them holds a coefficient array (C3).
- **`data_provenance`** names CoolProp's citation key for each fluid. The full citations are CoolProp's.
- **The flag stands.** Bundling CoolProp in any distribution needs its own decision.

### 16.13 Open questions and findings (Amendment 1; each question with a recommended default)

- **Q-A1-1 (needs the user's preference; not blocking): the E-bound trade.** κ = 0.01 MPa⁻¹ with
  P_hi = max(5 MPa, 1.1·p_c) costs 96 fluids 5–13 % of liquid range above T_t, and every pressure above P_hi, in
  exchange for a box that needs no melting-line data. The alternatives: (a) exclude the 96, leaving 27 fluids;
  (b) κ = 0.005 MPa⁻¹, halving the liquid-range cost with a margin of 1.3× over the non-quantum maximum and below
  Neon's slope; (c) a 10 MPa floor (T_lo = 1.10·T_t). **Default:** as specified. Reversible by a register entry and a
  generator re-run. The rule's two numbers live in the generator and the table, so no provider code changes.
- **Q-A1-2 (needs a fact): CoolProp's `IdealGasHelmholtzCP0AlyLee` constants.** **Measurement that settles it:**
  read CoolProp 8.0.0's implementation of the term (MIT source at the pinned gitrevision), derive its α° in closed
  form, and check it at m7's points. If it reproduces CoolProp at the floor, n-Heptane and D6 join by amendment.
  **Default:** excluded.
- **Q-A1-3 (needs the user's preference): transcribe published check values?** Which fluids, and whether their papers
  are accessible. **Default:** none in S07. WO-S07-4 is optional and may run after the merge, starting with the fluids
  that development cases use.
- **Q-A1-4 (needs a fact): do C5–C14 hold at 50 digits for all 123?** m8 forecasts C6 and C8–C11 in double precision.
  C5 (the critical-point solve), C7 (the band roots), C13 and C11's 1e-7 agreement are not forecast. **Measurement:**
  WO-S07-1b's first full run. **Default:** a fluid that fails any claim is removed by amendment, with the measured
  reason. The build lane continues with the others only after that amendment. No silent skip, and no per-fluid
  tolerance.
- **Q-A1-5 (needs a fact): does S05's generic algorithm serve every tier-B fluid?** The risk is saturation at very low
  reduced temperature, where p_σ(T_lo) reaches about 1e-6 Pa (1-Butene: T_lo/T_c = 0.22). **Measurement:** A22's
  `Psat` item and A10/A11 at T_lo, in WO-S07-2b. **Default:** as Q-A1-4, exclusion by amendment and no special case.
- **Q-1, extended.** WO-S07-3's aarch64 run covers tier B. Tier B's stop line is §16.11's 1e-10.
- **F-5 (for the build lane, with an acceptance test).** T08's provider scan imports every `thermo` module. WO-S07-2a
  checks that the scan imports `_coolprop_heos_fluids.py` without error and does not count it as a provider. If it
  does count it, the build lane adjusts the scan's filter and reports the change.

### 16.14 Work orders (supersede §12.1–§12.3; each ≤ ~100k context)

The lead lane is build for all of them. The design lane reviews WO-S07-1b's generator and first output, including the
`dropped` list and any claim failure (Q-A1-4), before WO-S07-2a starts.

- **WO-S07-1a (build, `sonnet-implementer`; about 40k): dependency and inventory.** §12.1 items 1–3, unchanged: the
  extra, the lock and the licence inventory with both wheel SHA-256s. Acceptance: `pip install -r requirements.lock`
  in a fresh venv imports CoolProp 8.0.0 at the pinned gitrevision; the inventory script passes with the `coolprop`
  extra; the tests it touches pass.
- **WO-S07-1b (build, `opus-engineer`; about 100k): the generator.**
  - `s07_reference.py` per §8 as amended by §16.7: the closed forms of §2.2 and §16.2, the rules of §6.1 and §16.4,
    S1–S5, claims C1–C19, the tiers, `--jobs`, `--check` and `--emit-fluid-table`.
  - Outputs: `s07_reference.json`, `_coolprop_heos_fluids.py`, and `benchmarks/s07/published_checks.yaml` with
    `rows: []`.
  - m7's forms are a starting point to read; they are records, not code to import.
  - Record the measured run time and the `--jobs 1` byte-identity check.
  - Stop and report on any claim failure (Q-A1-4). Never edit a rule to make a claim pass.
- **WO-S07-2a (build, `opus-engineer`; about 100k): the provider, tier A.** §12.2 as written, with the constants read
  from `_coolprop_heos_fluids.py`. `tests/test_s07_coolprop.py` covers A01–A28 and A32 (with m9–m11) for tier A, plus
  A33 and A34. Settle Q-3 and F-5.
- **WO-S07-2b (build, `opus-engineer`; about 80k): tier B.** `tests/test_s07_broad.py` covers §16.10's tier-B column
  over the 114 fluids, and A35. Measure and record per fluid the A17 floor and the A03 and A05 worsts, and the tier-B
  test run time on x86-64. A fluid the generic provider cannot serve (Q-A1-5) is reported, never special-cased.
- **WO-S07-3 (build, `sonnet-implementer`; about 60k).** §12.3 as written. The platform digest covers both tiers
  (tier B: its stored answers, about 0.3 MB of `float.hex`), and A31 applies its tier bounds.
- **WO-S07-4 (build; optional; does not gate S07's `tested`).** Transcribe published check values for the fluids that
  Q-A1-3 names, and regenerate. A35 then reports them.

### 16.15 Manifest additions (§13)

`status: tested` also requires:
- A33–A35 and §16.10's tier-B column pass on both architectures;
- the fluid count (123: tier A 9, tier B 114) and the excluded list with reasons, and per fluid its tier and bound;
- the generator's measured run time and the `--jobs 1` byte-identity check;
- the measured tier-B worsts (A03, A05, A17) and A31's tier-B outcome;
- the number of fluids reporting `published-check`. Zero is a valid value, and it is stated as 0.

### 16.16 Measurements behind Amendment 1 (scratch venv, as §14)

```
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m6_survey.py m6.json          # every fluid: pseudo-pure, EOS count, term types, melting line and its limits
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m7_forms_all.py m7.json       # §2.2 and §16.2 forms vs CoolProp, 130 non-pseudo-pure fluids, worsts by order
$S/cpvenv/bin/python -I docs/derivations/scripts/s07_measurements/m8_domain_forecast.py m8.json m8_table.md  # S1-S5, §16.4's bounds, forecast of C6 and C8-C11, §16.3's table
```

- Run on 2026-10-23 on the workstation (x86-64, 48 threads), with CoolProp 8.0.0 at `ae81610e…` and mpmath 1.3.0. m7
  took 5 s of wall time and 39 s of CPU in 40 processes. After `ruff format`, all three were re-run and their outputs
  were byte-identical.
- Computed inline from m7's and m8's data, not by a committed script: the Aly–Lee diagnostic (α° − closed form is
  linear in τ, and α°_ττ agrees to ≤ 3.3e-14, at τ ∈ {0.4, 0.667, 1.0, 1.25}), and the melting slopes of §16.4 on
  C9's grid.
- These are records, not gates. The generator re-measures every load-bearing number as a claim: C1 (term types), C9
  (melting lines), C11 (admission), C15 (the list) and C18 (κ).

### 16.17 What Amendment 1 does not establish

- That any tier-B fluid's coefficients are the source paper's. Only V7 would show that, and S07 transcribes no check
  values. Nor any EOS's accuracy against experiment.
- That the E boxes contain no solid state. κ is an empirical bound taken from CoolProp's melting lines of other
  fluids (§16.4).
- That claims C5, C7, C13 and C11's agreement hold at 50 digits for every admitted fluid (only partly forecast;
  Q-A1-4), or that the generic provider serves every tier-B fluid (Q-A1-5).
- That n-Heptane, D6, Helium, ParaHydrogen, MD2M, R236EA, R161 or the six pseudo-pure fluids cannot be supported. This
  document's rules exclude them, with reasons, and any of them can return by amendment.
- Anything §15 does not establish.
