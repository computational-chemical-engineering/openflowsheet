# ADR 0046 — CoolProp as an optional pure-fluid Helmholtz evaluator: a library-only provider `coolprop-heos-v1` (package S07)

**Status:** **Proposed, 2026-10-23** (design lane, `specifier`; R-618…R-622). It becomes Accepted when all of these
hold:
- `evidence/S07/<commit>/manifest.json` is `tested`, with spec §13's check list complete, on both CI architectures;
- the `reviewer` has passed `thermo/coolprop_heos.py` and the generator `s07_reference.py`;
- spec §11 Q-1 (aarch64 identity) is answered with its number, and this status line says which outcome holds;
- Frank has answered Q-S07-1 (whether the cryogenic liquids may wait), or its default has stood unchallenged through
  the package's review;
- spec §10 F-1 is written into ADR 0001 D5 and `interfaces-frozen.md` §3 by the design lane.

**Author:** design lane (`specifier`), package S07. **Normative text:** `docs/derivations/S07-spec.md`.
**Generator:** `docs/derivations/scripts/s07_reference.py` (WO-S07-1; the plan is spec §8).
**Builds on:** ADR 0001 D1–D5; ADR 0026 (provider pattern: typed refusals, implementation and data hashes);
ADR 0045 (`iapws95-v1`, whose algorithms S07 generalizes and whose reference values judge S07's water); ADR 0007 and
ADR 0025 (cross-platform comparison); R-568/R-569 (library-only providers); T08.A32 (no third-party data in the
artifacts); Frank's queueing of S07 (2026-10-23) and his S05 Q-8 answer ("library only for now; binding planned later
together with S07").
**Supersedes, for this provider only:** ADR 0045's rejected alternative "CoolProp … as a runtime dependency" (see
Alternatives). ADR 0045 is not edited.

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
- **D8 — Cross-architecture rule** (spec §11 Q-1). Bit-identity on aarch64 is the target, measured by spec A31 in CI.
  If it does not hold, the pre-registered bound is 1e-12 relative (1e-10 near critical), and the manifest records the
  measured worst. That is 4 decades inside every reference tolerance. Beyond 1e-12 the build lane stops, and the bound
  is not loosened.
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
- `pyproject.toml` (extra), `requirements.lock` (one pin), and the G19 licence inventory (spec F-3).
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
