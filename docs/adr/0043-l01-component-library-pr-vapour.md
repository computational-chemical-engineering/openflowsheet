# ADR 0043 — Component-library gaps: Water first, through a separate vapour-only Peng–Robinson library route `pr-lib-v1`

**Status:** Proposed, 2026-10-22. It becomes Accepted when three things hold: WO-L01-1 and WO-L01-2's manifest is
`tested`, the `reviewer` has passed the provider, and Frank has answered Q-1 and Q-2 of the spec (§10).
**Author:** design lane (`specifier`), package L01.
**Normative text:** `docs/derivations/L01-spec.md`. The generator is `docs/derivations/scripts/l01_projection.py`.
**Builds on:** ADR 0026 (the PR method, D1–D5), ADR 0001 D5 and ADR 0011 D2 (reference conventions), and W27
registration §5.5, §5.6 and §21. Development-half evidence comes from the C2 split (R-486…R-494).
**Register:** R-520…R-527.

## Use case

The OpenIDAES-450 development half (225 cases) has no available component outside C1's five. Water is unavailable in
150 development cases, CO2 in 38 and O2 in 18. Frank asked for Water first, then the next most-blocking components,
**using existing property methods only**. A component that needs a new method is recorded as such and stopped.

## Decision

- **D1 — Admission rule R-A.** A component enters the library iff:
  - it is a W27 `chemical`;
  - it is unavailable;
  - some development case lists it whose non-reaction packages are all `cubic_pr`, each declaring phases within
    {vapor}.

  All other components are `needs new method: <methods>` and stopped (spec §3). A record whose spelling W27-R24
  refuses is stopped (R-B).
- **D2 — Admitted:** H2O, CO2, O2, C2H6, C3H8, all vapour only. **Stopped:** CO, by R-B (`Co`/`CO`, F-2), and every
  other component, with its method named. IAPWS-95 is the largest missing method behind water.
- **D3 — A separate route.**
  - The records go into the new file `benchmarks/l01/components.yaml`, which holds H2, N2, Ar and CH4 copied verbatim
    from C1, and then the five new records.
  - They are read by a new provider, `pr-lib-v1` (`thermo/pr_lib.py`).
  - C1's file, module and models stay byte-identical.
- **D4 — Method unchanged.** ADR 0026 D1, D3 and D4: PR 1976 with rounded Ω, κ 1976, k_ij = 0, and the reference
  convention `PR-C1-ref-v1`, shared by both routes. They share it because the datum is the same; no new convention is
  registered and `conventions.py` is unchanged.
- **D5 — Vapour phase rule.** The largest root, with two typed refusals:
  - ADR 0026 D2's `vapour_root_metastable`;
  - `vapour_root_liquid_like` when v < (Z_c/B_c)·b_mix. This is D2's pure-component single-root test applied with the
    mixture's b. It only ever refuses.

  Liquid requests and `flash` are refused. The domain box is C1's.

  **Amended 2026-10-22 (reviewer, R-540; spec §12.3):** a third refusal, `vapour_unstable`, follows the two above.
  It applies when a pure-component trial phase has tangent-plane distance tm_i < −10⁻¹⁰. For a pure fluid it is D2's
  guard. A VAPOR answer is certified stable against pure-component trial phases only, not against mixed liquids.
  Also amended: A12's bound is 2 % over all nine records (R-528), T08.A32 admits the library file (R-529), and
  packaging moves with WO-L01-3 after L01-Q4 (R-541).
- **D6 — Sources.** The sources are C1's: reference-EOS critical constants and ω, retrieved with chemicals 1.5.2
  `HEOS`; ATcT 1.112 Δ_fH° (`ATCT_G`); NASA TM-4513 low-range NASA-7 coefficients from Cantera 3.2.0; the cross-check
  is against CoolProp 8.0.0. A missing species stops that component; no substitute source is used.
- **D7 — Measurement.** Coverage is measured on development ids only, with W27's classifier, by a dedicated L01
  re-take that never writes W27's files or prints all-case counts. Until W27 can judge two routes of one method (F-1),
  the re-take's typed refusal is the registered result.

## Alternatives rejected

- **Appending the records to C1's file and `pr_c1.py`.** This lengthens every C1 n-vector, moves `pr-c1-v1`'s
  `data_sha256` and `implementation_sha256`, and invalidates the committed v0.2 records that hash them (the journey,
  the M02/M05 dumps, the W27 snapshots).
- **Admitting every component as a PR vapour.** W27-R16 is method-blind, so this would remove component reasons in
  cases whose method nothing serves. That inflates availability.
- **A pure-water PR liquid** (the NH₃ regime extended). A second condensable makes liquid mixtures possible, which is
  a new regime. No vapour-PR development case declares a liquid, and PR is not IAPWS-95.
- **A new reference-convention name.** It would need an `interfaces-frozen.md` change for an identical datum.
- **Working around W27-R24 (c) for CO** (dropping the formula, or renaming). This bends the harness, which rule 6
  forbids.

## Affected requirements and documents

- ADR 0026 (method, reused; not amended).
- `interfaces-frozen.md`: no change (PropertyProvider, the ComponentRecord schema and the conventions are unchanged).
- W27 registration: no change by L01. Findings F-1 and F-2 ask for a W27 Amendment 3, and F-3 corrects the brief.
- The C2 split rules SPLIT-R08…R11, which are obeyed: the generator and the re-take filter to development ids first.

## Migration impact

- No committed record moves (spec §4.4, L01.A22).
- New identities: `pr-lib-v1`'s two SHA-256 values.
- WO-L01-3 (held) adds one `PACKAGED` path, one selectable basis and one snapshot line. New snapshots then have a new
  `snapshot_sha256`, and `list_models_sha256` is unchanged.

## Acceptance evidence

- L01.A01–A23 pass at the branch head, with `l01_projection.py --check` OK. This is recorded in
  `evidence/L01/<commit>/manifest.json` at `tested`.
- L01.A24 is shown, its refusal recorded.
- L01.A25 and A26 are shown after W27 Amendment 3.
- A `reviewer` pass over `pr_lib.py` (it touches phase logic and derivatives).
- Frank's answers to spec Q-1 and Q-2.

## What this ADR does not establish

- No development case becomes runnable: the projected CANDIDATE count is 0 → 0.
- No liquid water, and no states above 1000 K.
- No accuracy of PR for steam beyond L01.A17 and A18.
- Nothing about the held-out half.
