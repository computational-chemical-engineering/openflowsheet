# ADR 0046 — CoolProp as an optional pure-fluid Helmholtz evaluator: a library-only provider `coolprop-heos-v1` (package S07)

**Status:** **Proposed, 2026-10-23** (design lane, `specifier`; R-618…R-622; Amendment 1: R-623; Erratum 1: R-624). It becomes
Accepted when all of these hold:
- `evidence/S07/<commit>/manifest.json` is `tested`, with spec §13's check list complete, on both CI architectures;
- the `reviewer` has passed `thermo/coolprop_heos.py` and the generator `s07_reference.py`;
- spec §11 Q-1 (aarch64 identity) is answered with its number, and this status line says which outcome holds;
- Frank has answered Q-S07-1 (whether the cryogenic liquids may wait), or its default has stood unchallenged through
  the package's review;
- spec §10 F-1 is written into ADR 0001 D5 and `interfaces-frozen.md` §3 by the design lane;
- Amendment 1's acceptance evidence (below) is in the same manifest.

*Met 2026-10-23:* Frank answered Q-S07-1, "Yes, they wait". He also chose the broad fluid list, which Amendment 1
below records.

**Author:** design lane (`specifier`), package S07. **Normative text:** `docs/derivations/S07-spec.md`.
**Generator:** `docs/derivations/scripts/s07_reference.py` (WO-S07-1; the plan is spec §8).
**Builds on:** ADR 0001 D1–D5; ADR 0026 (provider pattern: typed refusals, implementation and data hashes);
ADR 0045 (`iapws95-v1`, whose algorithms S07 generalizes and whose reference values judge S07's water); ADR 0007 and
ADR 0025 (cross-platform comparison); R-568/R-569 (library-only providers); T08.A32 (no third-party data in the
artifacts); Frank's queueing of S07 (2026-10-23) and his S05 Q-8 answer ("library only for now; binding planned later
together with S07").
**Supersedes, for this provider only:** ADR 0045's rejected alternative "CoolProp … as a runtime dependency" (see
Alternatives). ADR 0045 is not edited.

## Amendment 1 (2026-10-23; R-623) — the broad fluid list

**Trigger.** Frank, 2026-10-23: asked whether S07 starts with the nine S04 fluids or includes many more CoolProp fluids
now, he chose **"Broad list now"**. On Q-S07-1 he answered "Yes, they wait", so the cryogenic liquids stay with S07b
and the melting-line lower bound stays. **Normative text:** spec §16. Where this note and the decisions below differ,
this note governs.

**What changes.**
- **D5 — fluids by rule, in two tiers** (spec §16.1, §16.3). A CoolProp 8.0.0 fluid is admitted iff it is not
  pseudo-pure, every term type of `EOS[0]` has a closed form that reproduces CoolProp (measured), its box holds a
  saturation range and the near-critical box, and the generator's claims hold for it. That admits **123** of the 136
  fluids.
  - **Tier A** is the nine, unchanged.
  - **Tier B** is the other 114. Their ids are the CoolProp names with parentheses replaced; the CAS number is a
    constant.
  - **Thirteen are excluded,** each with its reason, which the provider reports: six pseudo-pure mixtures, two fluids
    with an Aly–Lee ideal-gas term whose CoolProp integration constants are not reproduced, Helium and ParaHydrogen
    (no saturation range above the melting bound), and MD2M, R236EA and R161 (the critical region lies outside the EOS
    range).
- **D6 — a third lower-bound kind** (spec §16.4). Fluids with a melting line keep it (M), or use the triple point when
  the line lies below it (T: H2O, HeavyWater). The 96 fluids without one (E) get
  P_hi = min(p_max, max(5 MPa, ⌈1.1·p_c⌉₂)) and T_lo = ⌈10·T_t·(1 + 1e-8 Pa⁻¹·P_hi)⌉/10. The 1e-8 Pa⁻¹ bounds the
  relative melting slope. It sits 1.6× above the steepest slope measured among CoolProp's melting lines with
  T_t ≥ 20 K (Neon) and 2.6× above the steepest non-quantum one, and generator claim C18 keeps the margin executable.
  The provider states the bound's empirical basis in `numerical_limitations`.
- **D3 — identity** (spec §16.9). The per-fluid constants move to a generated data module,
  `_coolprop_heos_fluids.py`, and `implementation_sha256` adds its hash. A pin under which the admitted list changes
  is a new provider id.
- **D7 — verification by tier** (spec §16.5).
  - Tier B is verified by 50-digit closed forms of CoolProp's own coefficients, and by consistency identities on the
    provider's answers. That is implementation verification and self-consistency, not validation, and `describe()`
    says so (`verification: self-consistent`).
  - Measured: CoolProp's fluid files hold no published check values.
  - Published values transcribed from the EOS papers are a mechanism (a data file and claim C16). S07 requires none.
  - Water (against S05) and the nine (against S04's ideal-gas parts) keep their independent cross-checks.
- **D8 — tier B's cross-architecture stop line** is 1e-10 (spec §16.11), because tier B's jet floor reaches 1.05e-12
  (R22). Tier A keeps 1e-12. *Superseded by spec §20 (R-627): see D8.*
- **Rights.** The Rights argument below does not depend on the fluid and covers all 123 (spec §16.12).

**Alternatives rejected (Amendment 1).**
- *Exclude every fluid without a melting line.* That leaves 27 fluids, and it contradicts Frank's choice. It would
  drop ammonia, the aromatics, the refrigerants and the heavier alkanes.
- *T_lo = T_t for those fluids.* That gives silent LIQUID answers in the solid region, which R-620 rejected.
- *The full registered-state set for every fluid.* That means a reference file of several MB, and the same generic
  code judged 114 times. Tier B registers 11 states per fluid instead (spec §16.6).
- *Admit the Aly–Lee fluids with a fitted constant.* That would copy the expectation from the thing tested.
- *Admit the pseudo-pure mixtures.* That applies a pure-fluid phase rule to a mixture.

**Errata in the first spec** (spec §16.0): N2's T_lo is 82.8 K; C9's melting grid starts at the melting line's own
lower pressure limit; O2's EOS citation key is the full string; C1's "one EOS per fluid" becomes "`EOS[0]`".

**Acceptance evidence added.** Spec A33–A35 and §16.10's tier-B column pass on both architectures. Generator claims
C15–C19 pass. The manifest carries spec §16.15's items.

**Does not establish.** That any tier-B fluid's coefficients are the source paper's. That the E boxes are free of
solid states for every fluid. That every claim holds at 50 digits for all 123 before WO-S07-1b's run (spec §16.13
Q-A1-4).

## Erratum 1 (2026-10-23; R-624; spec §17)

D2: CoolProp is hash-pinned in `requirements-coolprop.lock`, installed after `requirements.lock` with `--no-deps`.
`requirements.lock` and its registered hash `ead4edf1…` are unchanged. G19 judges the extra's increment (CoolProp,
MIT). numpy belongs to the base install, audited by T08.A30 and dispositioned by R-135.

This note supersedes D2's "It enters `requirements.lock` … (MIT, compiled, numpy already covered)", the Interfaces
line's "`requirements.lock` (one pin)", and R-618's "locked in `requirements.lock`" (the register carries the
amended-by line). Written by the design lane at the S07 generator review (spec §17.7 F-6; R-625).

## Use case

Water has its own provider (S05). The other components the L01 re-take admits (CO2, O2, C2H6, C3H8, and C1's N2, H2,
Ar, CH4) have only `pr-lib-v1`, a Peng–Robinson vapour model. Each of them has a reference equation of state in
CoolProp, a mature MIT library. Transcribing and verifying nine such EOS ourselves, as S05 did for one, would take
nine S05s. Calling CoolProp for the Helmholtz energy alone gets reference-EOS accuracy for all nine. Phase logic,
refusals, caching and identity stay the project's. This ADR fixes how that call is made, pinned and judged. It
makes no flowsheet binding.

## Decision

- **D1 — CoolProp is a Helmholtz evaluator only.** The provider calls `AbstractState("HEOS", name)`,
  `specify_phase(iphase_gas)`, `update(DmolarT_INPUTS, ρ, T)` and the twenty partial getters of α° and αʳ up to total
  order 3, and nothing else that evaluates. Every property, density root, saturation state, phase label and refusal is
  computed by the provider from the jet, by S05's closed forms and algorithms. CoolProp's flash routines and property
  getters are never called. An AST allowlist enforces this (spec A27). Spec §4 has the measurements behind the
  imposed phase: identical jets with and without it, and CoolProp's own `p()` in the dome returning the saturation
  pressure rather than the EOS value.
- **D2 — An optional, pinned dependency.** `CoolProp==8.0.0` (gitrevision `ae81610e…`) is the `coolprop` extra. It is
  not a default requirement of the wheel. It enters `requirements.lock` the way the `server` extra's closure does, so
  CI installs it on both architectures. The G19 licence inventory covers it (MIT, compiled, numpy already covered).
  *(Superseded by Erratum 1, above: `requirements-coolprop.lock`, and G19 judges the increment.)*
  Any other installed version is a typed refusal on every call (`coolprop_version_mismatch:`). Moving the pin takes a
  register entry and a spec amendment.
- **D3 — Identity when the data live in a third-party package** (spec §5.1).
  - `data_sha256` hashes {pinned version, fluid name, SHA-256 of the fluid's JSON as CoolProp reports it,
    re-serialized canonically}.
  - `implementation_sha256` hashes {the module's bytes, pinned version, pinned gitrevision}.
  - Neither hashes the per-architecture binary, so one identity holds on both CI architectures. The wheels' SHA-256s
    go in the manifest and the licence inventory.
  - Both are computed from constants, so `describe()` answers without CoolProp.
  - A changed fluid hash, or a registered value moving outside tolerance under a new pin, makes the id
    `coolprop-heos-v2`.
- **D4 — A guard, because CoolProp is process-global mutable state** (spec §5.2). Before the first evaluation, each
  instance checks four things: the import, the version, the fluid hash, and a canary of α° that catches
  `set_reference_state` (measured: it changes α° without changing the JSON). Each failure is a typed `unsupported`
  refusal on every later call. The provider never mutates CoolProp's global state.
- **D5 — Nine fluids, one instance per fluid, pure only** (spec §2.1, §3.1). H2O, CO2, N2, O2, Ar, CH4, C2H6, C3H8
  and H2, by the S04 library's ids. Properties `h`, `s`, `v`, `Z`, `cp`, `lnphi_<id>`, `Psat`, `Tsat`. First
  derivatives in T, P and n (the n ones exactly 0.0). Flash `TP` only. State definition `nTP-v1`. Convention
  `COOLPROP-DEF-ref-v1`: each fluid's α° as the pinned data give it, offsets included. That is not a formation datum,
  and it is not mixed with other conventions.
- **D6 — Domain is a box per fluid, and the solid is outside it** (spec §6). T ∈ [T_lo, min(T_max, 1273.15 K)],
  P ∈ [1e2 Pa, min(p_max, 1e8 Pa)]. T_lo is the triple point for water and the melting temperature at the top
  pressure for the others, so the box contains no solid state and `PropertyCapabilities.domain` states it exactly.
  The near-critical box, the saturation edge and the liquid bracket follow fixed relative rules, each with a
  generator claim. S05's algorithms are re-implemented generically in a new module. `iapws95.py` is untouched.
- **D7 — Expectations from closed forms, judged three ways** (spec §8, §9).
  - The generator evaluates the closed forms at 50 digits from the parsed fluid JSON.
  - CoolProp's numerical output is tested against it, never used for it.
  - Water is judged a second time against S05's reference, whose coefficients match the printed IAPWS release.
  - The ideal-gas parts are compared with the S04 records (2 %, L01.A12).
- **D8 — Cross-architecture rule** (spec §11 Q-1, §20; R-622, R-627). Bit-identity on aarch64 is the target,
  measured by spec A31 in CI, and x86-64 must reproduce the digest bitwise. If aarch64 differs, A31 judges each answer
  by class (spec §20.3). Ordinary answers must agree within 1e-10 of max(|x|, s_f), for both tiers. Near-critical
  answers (state within 1 % of T_c) get a per-state allowance: the saturation pressure within 1e-10 (G3's near
  bound), every other answer within 1e-10·max(|x|, s_f) + 2e-10·P|∂q/∂P|_T, its own pressure sensitivity. Reference
  verdicts are decided by A05–A13 on both architectures, not by A31. Beyond an allowance the build lane stops, and
  nothing is loosened.
- **D9 — Library-only** (spec §3.4). The provider is not in `SELECTABLE_BASES`. It is registered under R-568, and its
  limitations go to U02 under R-569. The records-less selectable basis for S05 and S07 is a follow-on package with
  its own ADR.

## Alternatives rejected

- **CoolProp's own flash and property getters** (`PropsSI`, `update(PT_INPUTS)`). The settled brief excludes them.
  The measured reason: CoolProp's TP solve is noisy at about 1e-10, and its central differences are off by 1e-4 to
  1e-3 relative in the P derivatives (S05 §6.3). Its phase decisions and failures would not be ours either.
- **CoolProp as a default dependency.** That would put a compiled third-party binary and its data in every install,
  which ADR 0045 rejected and the brief settles against.
- **ADR 0045's rejection kept as is.** Its two objections were a binary wheel per platform and no control over
  refusals and exactness. The extra makes the first optional. D1 and D4 answer the second. The rejection stands for
  `iapws95-v1`.
- **Hashing the CoolProp binary into the identity.** The binary differs per architecture, so the identity would
  differ between the CI pair, and cross-architecture replay would compare different providers.
- **Hashing CoolProp's JSON string as returned.** Canonical re-serialization is just as exact, and it does not
  depend on CoolProp's whitespace or key order.
- **Transcribing the coefficients into the repository** (the S05 route). That would redistribute data the brief says
  we do not redistribute, and it would mean nine transcriptions to verify.
- **A run-time melting guard now.** It makes the domain non-rectangular, which `PropertyCapabilities.domain` cannot
  state, and it needs per-fluid melting equations at run time. It is deferred to S07b. The cost is that the cryogenic
  liquids wait (Q-S07-1).
- **Designing the shared records-less basis key now.** It changes the selection layer, which `pr-c1-v1` and
  `pr-lib-v1` share, and it would double S07's first delivery. It is a follow-on, together with S05's binding.
- **One provider over all nine components with one-hot compositions.** That is a mixture interface without mixture
  semantics. It invites a composition derivative that does not exist.

## Rights

- **CoolProp is MIT.** The licence file is read from the installed distribution (`coolprop-8.0.0.dist-info/licenses/
  LICENSE`; G19 records its hash). The project installs nothing and ships nothing of CoolProp: the user installs the
  extra from PyPI, and the provider reads the data at run time from that installation. That is ordinary use of an
  MIT-licensed package, and it creates no notice obligation for our artifacts.
- **The EOS coefficients** originate in the papers of spec §2.1 (RC-01's publishers) and, for some fluids, in
  REFPROP-associated work (RC-02). CoolProp distributes them under its own terms. Whether it may do so is CoolProp's
  question, not ours. We neither copy nor redistribute them: no committed file holds a coefficient (spec A29, C3).
- **`s07_reference.json`** holds property values that the project computed at registered states, the fluids' hashes
  and a few derived constants (critical point, domain bounds, canary values). These are computed facts, as in any
  test expectation, and they stay out of every `PACKAGED` path (spec A29), so T08.A32 is unaffected.
- **Flag.** If a future distribution bundles CoolProp (for example an all-in-one installer), it must carry CoolProp's
  MIT notice. That needs its own decision. Nothing here authorises it.

## Affected requirements and documents

- D08 (thermodynamic primitive) gains S07 when its manifest is `tested` (spec F-4). D10 (cache) is unchanged: the
  provider sits behind the existing exact-input cache, keyed on D3's identities.
- ADR 0001 D5 and `interfaces-frozen.md` §3: one convention line, written on acceptance (spec F-1). No Protocol,
  schema, quantity kind or result-type field changes.
- `pyproject.toml` (extra), `requirements.lock` (one pin), and the G19 licence inventory (spec F-3). *(Superseded by
  Erratum 1: `requirements-coolprop.lock`, and `requirements.lock` is unchanged.)*
- R-568's `LIBRARY_ONLY_PROVIDERS` and R-569's U02 note: one entry each.
- ADR 0045: its rejection is superseded for this provider only. The register records it (R-618). ADR 0045's text is
  unchanged.

## Migration impact

- No committed record moves. `pr-c1-v1`, `pr-lib-v1`, `iapws95-v1` and `syn001` stay byte-identical, so no existing
  hash changes. W27 coverage, the journey and the replay bundles are unchanged (library-only).
- The default install is unchanged. CI's environment gains one wheel per architecture.
- New identities: `coolprop-heos-v1`'s implementation and per-fluid data hashes.

## Acceptance evidence

- S07.A01–A32 pass at the branch head on x86-64 and aarch64. `s07_reference.py --check` is OK. The licence inventory
  is OK with both wheel hashes. All of it is recorded in `evidence/S07/<commit>/manifest.json` at `tested`.
- A `reviewer` pass over the provider and the generator.
- Q-1's outcome stated in this status line, and Q-S07-1 answered or defaulted.

## What this ADR does not establish

- The accuracy of any EOS against experiment, or of CoolProp's coefficients against the papers (water excepted,
  through S05).
- Bit-identity on aarch64 before A31 has run there.
- Any development case becoming runnable. Binding is a follow-on.
- Mixtures, transport properties, solids, cryogenic liquids below T_lo, near-critical states inside the box, and
  metastable states beyond ε_σ.
- Permission to bundle CoolProp in any distribution.
- Anything about the held-out half.
