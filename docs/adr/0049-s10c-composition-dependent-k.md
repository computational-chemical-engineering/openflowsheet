# ADR 0049 — Composition-dependent K in the PH kernel and the column: equilibrium forms, the constant-β point, a band-first PH route, and the column's admission of `wilson-ig-v1` (package S10-C)

**Status:** **Accepted, 2026-10-30**, marked by the build lane (V03 spec §6, R-876; the check is recorded in `docs/V03_DECISIONS.md` for S13's manifest). Proposed 2026-10-26 (design lane, `architect`; register R-760…R-769). It became **Accepted** when:
- S10-C's evidence manifest is `tested`, with gates G1–G9 of the design note passing;
- the `reviewer` has passed WO-1…WO-4 against the design note and the S10-C specification.

*Met 2026-10-30 (V03 WO-4):* `evidence/S10c/2aedd250…/manifest.json` (and the earlier `8f38f963…`) is `tested`: `S10C.G1`, `S10C.G1-flowsheets`, `S10C.G2`, `S10C.G-R3` and `S10C.G-R7` pass, G3 is held by S10C.A60/A61 against its registered references (the review's must-fix F1), and G9's wall times are recorded in WO-4; the merge `8654aabc` records the gate PASS (13249/3137) and CI 40315691647. `docs/reviews/S10C-review.md` passed WO-1…WO-4 with that one must-fix, which the manifest carries. G3–G8 are the S10-C specification's assertions S10C.A01–A61 (spec §6), all `pass` in `2aedd250…`.

**Date:** 2026-10-26
**Author:** design lane (`architect`), brief `docs/briefs/S10C-flash-and-column.md`.
**Normative text:** `docs/derivations/S10C-design.md`; the registered states, tolerances and derivations are the
`specifier`'s `docs/derivations/S10C-spec.md` (WO-S) with `benchmarks/s10c/reference_values.yaml`.
**Amends:**
- ADR 0011 D1, for composition-dependent forms only: the PH kernel's provider class and the monotonicity argument its
  bracket relies on;
- ADR 0012 D1–D2, for composition-dependent forms only: the band primitive `T(β)` and the order of the PH routes;
- S03 spec §9 S11, for the column only: identity is checked against an allow-list of equilibrium forms.

No frozen `Protocol`, schema, quantity kind, check category or tolerance changes. SYN-001 and every provider outside
the allow-list are bit-identical.

**Affected requirements:** D08 (provider conformance in consumers), R01 (cases), U02 (library-only limitations),
blueprint §6.2–§6.3.
**Affected packages:** S10-C implements it. S10 (`wilson-ig-v1`, ADR 0047) and S08 (ADR 0048) are consumed unchanged.
**Companions:** ADR 0001 D2–D5; ADR 0005, 0011, 0012 (PH closure, band, phase contract); ADR 0047 (the provider, D10);
ADR 0048 (Stage B).

## Context

SYN-001's K depends on `(T, P)` only. Every K consumer — `LnKBlock` (inputs `T, P`, a composition-neutral probe),
`cascade._k_values`, `saturation_band.band_temperature`, the PH kernel's routes and closure rows — encodes that.
`wilson-ig-v1` (γ–φ, Wilson liquid, ideal-gas vapour) has `K_i = γ_i(x) P_i^sat(T)/P`. S11 refuses it in the column by
identity because a composition-independent K would be answered silently wrong. S10's TP flash also has a measured noise
floor near an azeotrope (S10 spec §14 E-2) that a PH flash searching the two-phase sliver must not inherit.

## Decision

**D1. Equilibrium forms.** A unit-layer function resolves a provider by `(provider_id, reference_convention)` to
`syn001-lnK-TP` (SYN-001) or `gamma-phi-ig-v1` (`wilson-ig-v1` under `WILSON-IG-ref-v1` or `S10-VER-ref-v1`), else
`None`. The column admits exactly these two; for the second it also checks the declared capabilities and that the
vapour `ln φ` is exactly zero at one probe. Every other provider keeps S11's cause, with the message naming the new
scope. The S01 cascade keeps S11 unchanged. Procedural kernels treat `None` exactly as SYN-001, so their behaviour for
non-admitted providers does not move.

**D2. K at a liquid composition; mixture enthalpy flows.** For `gamma-phi-ig-v1`, `ln K_i = ln φ_i^L(T, P, x)` from the
provider's `lnphi_<c>`; `Ḣ = n_tot h`. The provider is not adapted to offer `lnK` or `h_<c>`: their absence is a
tripwire that makes any unmigrated call site fail loudly.

**D3. The constant-β point** generalises ADR 0012 D1's `T(β)`: for flowing `n`, `P`, `β`, find `(T, x)` with
`x_i = z_i/(1 + β(K_i(T, P, x) − 1))` and `Σ z_i(K_i − 1)/(1 + β(K_i − 1)) = 0`, by composition successive substitution
with an exact, bracketed temperature solve per step (`DELTA_BETA = 1e-13`, cap 1000). `β = 0` is the bubble point in one
step; `β = 1` is the dew point (`tm* = 0`). β is never solved from K, so the iteration has no E-2 floor.

**D4. Band-first PH route** for a composition-dependent form: band ends first, then exactly one of a liquid bracket, a
vapour bracket or the existing β-bisection band route, accepted on the closure's own rows with K at the answer's liquid
composition. The provider's TP flash is not called inside the band. The monotonicity ADR 0011 D1 relies on is replaced,
for this class, by the theorem that `Ḣ_TP(T)` is strictly increasing for a γ–φ-IG provider with positive latent heats
and heat capacities (frozen heat capacity plus a non-negative latent term, by the strict convexity of the two-phase
Gibbs energy, S10 spec §4.1), with `T_b` and `T_d` unique. SYN-001's routes and order are unchanged.

**D5. E-2** is remedied in the PH flash by D3–D4. The provider's TP flash is unchanged.

**D6. The column's K-block** has inputs `(l_1…l_C, T_j, P_j)` (the condenser's: `v_2`) and the provider's projected
composition derivatives as its `∂ ln K/∂l` block. A dormant liquid is evaluated at the composition-neutral probe; every
row reading the block multiplies it by a flow of the same input, so the convention moves no residual or Jacobian
entry. Enthalpy blocks are single-output mixture blocks. The bubble-point and S08 core sweeps evaluate K at a
composition relaxed by `ω = 1/2`.

**D7. Scope.** Library level only (Frank's Q-F2 default). For the new form the column admits `reflux_ratio`,
`boilup_ratio`, `distillate_rate`, `bottoms_rate` and `duty` specifications; `purity`, `recovery` and `temperature` are
refused, typed. No unit other than the column is admitted.

## Alternatives considered

- **A capability rule for admission** (declares `∂/∂n`). `pr-c1-v1` and `pr-lib-v1` declare it and are φ–φ; a γ–φ
  K-block would ignore `ln φ^V(y)`. Rejected.
- **An adapter offering `lnK`/`h_<c>`.** Makes every unmigrated call site silently wrong. Rejected.
- **A generic φ–φ K-block with vapour inputs.** Needs incipient-vapour variables in the bubble row and the band; no
  admitted provider needs it. Deferred to the first φ–φ liquid provider.
- **Today's PH order with the TP flash.** Fails inside E-2 slivers before the band route can run; not cheaper. Rejected.
- **A conditioning-tied stop in the TP flash.** A heuristic floor whose error accepts unconverged splits, `ok` answers
  with ≈ 1e-6 relative β error, and a new provider identity. Rejected.
- **Undamped lagged K in the sweeps.** Measured: C-EW oscillates. **A Raoult-to-Wilson homotopy.** A block parameter and
  a new continuation path where damping suffices. Both rejected.

## Consequences

- **C1.** No frozen interface changes. `BandTemperature` gains a defaulted field; new modules
  `models/syn001/{equilibrium_form,gamma_phi,gamma_phi_blocks}.py`; dispatch branches at the top of existing functions;
  one branch in `orchestrator/region.py` (`_admissible`).
- **C2.** SYN-001, pr-c1-v1 and every non-admitted provider: bit-identical (gate G1). `thermo/` untouched (S10's
  results and identities do not move).
- **C3.** S03 A04's message assertion is amended; its cause assertion stands.
- **C4.** Limitations: binaries only for the band's uniqueness proof (T5); absolute equilibrium tolerance limits the
  band route to streams below ≈ 1000 mol/s; Stage B for the new form is tested at the opening level only.

## Migration impact

None for stored documents. `LIBRARY_ONLY_PROVIDERS["wilson-ig-v1"]` stays; U02 rows that state the column's refusal of
the provider are restated as library-level support.

## Acceptance evidence

Gates G1–G10 of `docs/derivations/S10C-design.md` §6, the mutations M1–M5, and the `reviewer` pass.
