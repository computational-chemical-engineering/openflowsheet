# ADR 0045 — Pure water by IAPWS-95: a library-only provider `iapws95-v1` (package S05, planned v0.3)

**Status:** Proposed, 2026-10-22. It becomes Accepted when five things hold:
- WO-S05-1 and WO-S05-2's manifest is `tested`;
- the `reviewer` has passed the provider (it touches residuals, derivatives and phase logic);
- Frank has answered C10-Q1 (rights, with the release's Tables 6–8 compared, spec §10 Q-1);
- Frank has answered C10-Q2 (supercritical label);
- the finding of spec §8 F-1 has been written into ADR 0001 D5 and `interfaces-frozen.md` by the design lane.

**Author:** design lane (`specifier`), package C10 → S05.
**Normative text:** `docs/derivations/S05-IAPWS95-spec.md`.
**Generators:** `docs/derivations/scripts/s05_reference.py` (project venv, mpmath only) and `s05_crosscheck.py` (scratch venv only).
**Decisions:** `docs/C10_DECISIONS.md` (eleven lines, copied into spec §13).
**Builds on:** ADR 0001 D1–D5 (units, `nTP-v1`, zero flow, reference conventions), ADR 0026 (provider pattern: typed refusals,
implementation and data hashes), ADR 0043 and R-568/R-569 (library-only providers), and Frank's L01-Q3 answer (IAPWS-95 is a
planned v0.3 method with its own ADR, not benchmark tuning).
**Register:** R-585…R-594.

## Use case

Water is the most frequent unavailable component on the OpenIDAES-450 development half: 150 of 225 cases (ADR 0043).
`pr-lib-v1` admits it only as a Peng–Robinson vapour, and the development cases that need liquid water or steam
tables name the `iapws95` method (W27 `package_methods`). No existing method serves them. This ADR specifies the
method itself: a pure-water property provider on the existing contract, with no flowsheet binding. Binding,
selection and W27 exposure belong to later packages.

## Decision

- **D1 — Formulation.** The IAPWS-95 formulation, R6-95(2018) revision: the dimensionless Helmholtz energy
  φ(δ, τ) = φ°(δ, τ) + φʳ(δ, τ), with 8 ideal-gas coefficients and 56 residual terms (7 polynomial, 44 exponential,
  3 Gaussian, 2 non-analytic). R = 0.46151805 kJ/(kg·K) and M = 18.015268 g/mol, so the molar R is 8.314371357587 J/(mol·K).
  This is not CODATA's value, and it is used everywhere in this provider. Spec §2.
- **D2 — Coefficients and their evidence.**
  - The coefficients are transcribed from CoolProp 8.0.0's `Water` fluid string (MIT, SHA-256 recorded).
  - `s05_crosscheck.py` asserts that they equal `iapws` 1.5.5's exactly (GPL-3, executed as a comparison only).
  - They are committed as `s05_iapws95_coefficients.json`. The provider's copy is byte-identical (S05.A01).
  - Expectations come from a 50-digit mpmath generator over that file.
  - A value is admitted only where both external implementations agree with it within spec §6.2's bounds.
  - The release's printed Tables 6–8 could not be read (iapws.org refused, 2026-10-22). Comparing them is an open
    *needs a fact* item, and the generator already emits the 9-digit values to compare.
- **D3 — Provider `iapws95-v1`** (`thermo/iapws95.py`), components `("H2O",)`, state definition `nTP-v1`.
  - Properties per phase: `h`, `s`, `v`, `Z`, `cp`, `lnphi_H2O` (molar SI).
  - Saturation: `Psat`(T) and `Tsat`(P).
  - First derivatives in `T`, `P` and `n_H2O`; the `n_H2O` derivatives are exactly 0.0.
  - Flash: `TP` only.
  - It carries `implementation_sha256` and `data_sha256` (the coefficient file).
  - It is library-only: it is in no `SELECTABLE_BASES` entry, so R-568/R-569 apply unchanged.
- **D4 — Reference convention `IAPWS95-ref-v1`.**
  - The formulation's own datum: u = 0 and s = 0 for the saturated liquid at the triple point.
  - It is not a formation datum, and it is not in ADR 0011 D2's reaction-consistent set.
  - Streams of this convention never mix with others' (ADR 0001 D5.2).
- **D5 — Domain and phase rule** (spec §4).
  - Domain: T ∈ [273.16, 1273.15] K, P ∈ [1.0e2, 1.0e8] Pa.
  - Below 647.0 K, saturation decides the phase with a two-sided band ε_σ = 1e-6 in ln P, inside which both phases
    are answered.
  - T ≥ T_c is labelled VAPOR.
  - (647.0, 648.0) K × [22.0, 22.2] MPa is refused `near_critical`.
  - Every other outcome is a typed refusal with a fixed message prefix; silence never reads as success.
- **D6 — Derivatives are exact.** φ and all its partial derivatives up to total order 3 come from one evaluation of the
  closed form (spec §3.2), so values and derivatives describe the same function. The generator obtains its
  expectations by 50-digit numerical differentiation of φ alone. The two routes are therefore independent.
- **D7 — Flash.** `TP` only: single-phase answers outside the band. Inside the band it is refused
  `tp_flash_degenerate`, because the split of a pure fluid at fixed (T, P) is undetermined there.

## Alternatives rejected

- **IAPWS-IF97.** It is faster, but it is a fit to IAPWS-95 with region seams, and its derivatives jump across them.
  It is out of scope by the brief. It could later serve as a seed only.
- **CoolProp or `iapws` as a runtime dependency.** That would mean a binary wheel per platform (CoolProp), a GPL-3
  licence (`iapws`), and no control over refusals or exactness. They are used as comparisons only.
- **Expectations taken from CoolProp or `iapws` values.** Rule 1: an implementation is not an expectation. They admit
  the generator's numbers; they do not supply them.
- **CODATA R.** It departs from the formulation by 9e-6 relative, which shifts p and h measurably.
- **A formation-datum shift**, so that h(ideal gas, 298.15 K) = Δ_fH°. Pure water has no reaction here, and D5.2
  already forbids mixing conventions. It can be added later by a new convention name.
- **Answering metastable roots out to the spinodal** (the pr_c1 L2 precedent). The band ε_σ is enough for a
  round trip through Tsat. A wider metastable range invites labels that disagree with stability.
- **Labelling the supercritical fluid by density.** That is C10-Q2, defaulted to VAPOR. Either label flips somewhere
  on a boiler path; the density label also flips along an isotherm.

## Affected requirements and documents

- ADR 0001 D5 and `interfaces-frozen.md`: one new convention line, `IAPWS95-ref-v1`, written when this ADR is accepted.
  This is a finding (spec §8 F-1), not written by C10. No Protocol, schema, quantity kind or check category changes.
- `thermo/conventions.py`: unchanged. The convention is not reaction-consistent.
- T08.A20 / R-568: the provider is library-only, so one registration line is added under R-568's rule.
- The support matrix: U02 gains a note naming `iapws95-v1` as library-only (R-569 pattern), in WO-S05-2.
- Rights: `docs/l01-rights-check.md`'s pattern. IAPWS terms are `unresolved`, and the coefficient file is in no
  `PACKAGED` path until C10-Q1 is answered.

## Migration impact

- No committed record moves. `pr-c1-v1`, `pr-lib-v1` and `syn001` stay byte-identical, so no existing hash changes.
- New identities: `iapws95-v1`'s `implementation_sha256` and `data_sha256`.
- The W27 coverage, the journey and the replay bundles are unchanged, because the provider is library-only.

## Acceptance evidence

- S05.A01–A30 pass at the branch head, `s05_reference.py --check` is OK in the project venv, and
  `s05_crosscheck.py --check` is OK in a scratch venv. This is recorded in `evidence/S05/<commit>/manifest.json`
  at `tested`, with the check list of spec §12.
- A `reviewer` pass over `thermo/iapws95.py`.
- Frank's answers to C10-Q1 and C10-Q2.

## What this ADR does not establish

- That the coefficients equal the printed release. They equal two independent transcriptions, and the release's
  Tables 6–8 are not yet compared (spec §10 Q-1).
- Any development case becoming runnable. The provider is library-only, and binding is a later package.
- IF97, transport properties, mixtures with water, electrolytes, ice, metastable states beyond the ε_σ band, and
  near-critical states inside the refused box.
- Accuracy against experiment. IAPWS-95's own uncertainty statement is the release's, and it is not re-validated here.
- Anything about the held-out half.
