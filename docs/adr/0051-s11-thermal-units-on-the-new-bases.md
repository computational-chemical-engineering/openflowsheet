# ADR 0051 — Thermal units on the new bases: declared-regime pure-fluid streams with a carried split under `nTP-v1`, the `thermal.*` family, γ–φ faces for the K02/T05 units, and `wilson-ig-v2` (package S11, second pass)

**Status:** **Accepted, 2026-10-30**, marked by the build lane (V03 spec §6, R-876; the check is recorded in `docs/V03_DECISIONS.md` for S13's manifest). Proposed 2026-10-27 (design lane, `architect`; register R-813…R-821). It becomes **Accepted** when:
- S11's evidence manifest is `tested`, with gates G1–G13 passing (`docs/derivations/S11-design.md` §6 and
  `docs/derivations/S11-units-design.md` §6);
- the single `reviewer` pass has passed tracks C and D against the units design note.

**Implemented, tested (2026-10-28, WO-I2):** `evidence/S11/01e72ca464dcb68c489e235d3d5446d450e109e1/manifest.json` is `status: tested`, 123 of 126
checks: S11.A42–A86 and G9–G13 pass, with G1–G7. G8 (the full gate, CI on both architectures and the
cross-architecture comparisons) and the single `reviewer` pass are outstanding, so the status stays **Proposed**.

**Date:** 2026-10-27
**Author:** design lane (`architect`), brief `docs/briefs/S11-units-design.md`.
**Normative text:** `docs/derivations/S11-units-design.md`.
**Decided by Frank (2026-10-27):** first pass §7 Q2 (pure-fluid thermal units) and Q3 (γ–φ faces for the K02/T05
units) — "Include in S11" for both. His directive is "as few limitations as possible". This supersedes the first
pass's defaults (S11b, S11c).

**Amends:**
- **ADR 0001 D2.5.** The split of a two-phase stream is reconstructable from (n, T, P), *except* for a saturated
  pure-fluid stream. Its split is carried (D2 below).
- **ADR 0050:**
  - D1: the Wilson record source selects `wilson-ig-v2` (from WO-D5);
  - D3: the admission rows of D6 below;
  - D5: the verifier forms of D8 below;
  - D9: W27 v3 gains the `wilson-ig-v2` provider row and seven model functions, and S4 is generated at I1b.

**Extends:** ADR 0012 D7. A saturated pure-fluid stream is temperature-degenerate by construction, and its carried
split is what the verifier judges.

**Leaves unchanged:**
- ADR 0047 and the `wilson-ig-v1` module bytes;
- every provider module under `thermo/` that existed before S11;
- every schema, `Protocol`, quantity kind, check category and tolerance;
- `StreamState`.

**Affected requirements:** D08 (provider conformance in consumers), T08.A20 (the providers axis), W27-R63, R01
(cases), and the unit-model envelope.
**Affected packages:** S11 (tracks C and D, I1b); S05, S07 and S10 providers are consumed byte-unchanged; S10-C's γ–φ
blocks and kernels are reused.

## Context

The first pass made `iapws95-v1`, `coolprop-heos-v1` and `wilson-ig-v1` selectable, but admitted only routing models
on them, plus the column on Wilson. Thermal units were deferred, for two reasons:
- the TP flash of a pure fluid is degenerate on the saturation line, so `nTP-v1` cannot say how much vapour a
  saturated pure stream carries;
- the K02/T05 units' EO faces read SYN-001's `lnK` and `h_<c>`.

Both Helmholtz providers answer a phase only on its stable side, or within ε_σ = 1e-6 in ln(P/P_sat). `wilson-ig-v1`
declares no entropy, and its liquid has no volume.

## Decisions

**D1. Declared regimes for pure-fluid streams.** On a pure-fluid basis a connection's `phase_capability` is the
stream's regime:
- `liquid`: single-phase liquid;
- `vapor`: single-phase vapour, or supercritical by the provider's label;
- `vapor_liquid`: saturated, with T = T_sat(P) and 0 ≤ β ≤ 1 inclusive.

A closure that lands in another regime is refused `phase_regime_mismatch(<S>)`, naming the declaration to use. There
is no regime discovery for pure fluids in S11.

**D2. A saturated pure-fluid stream is `nTP-v1` plus a carried split.**
- In the EO, its producer authors the columns `<S>.sat.V` and `<S>.sat.L` and the rows T − T_sat(P) = 0 and
  V + L − n = 0. Its enthalpy flow is V·h^V_sat(P) + L·h^L_sat(P), evaluated at (T_sat(P), P) only.
- In the causal traversal it travels as `SaturatedStreamState`: a `StreamState` subclass in the models layer,
  carrying `vapor_fraction`, which is never passed to a provider.
- The producer's `UnitEvaluation.owned` seeds the EO start.

**D3. Closures land on the saturation line by construction.** A saturated outlet's vapour flow is fixed by:
- the unit's energy row (PH);
- an isentropic-enthalpy block through the work row (PS);
- a vapour-fraction row; or
- a fixed-β row (drum products).

**D4. Producers.** Only `thermal.*` units produce saturated pure-fluid streams. `syn001.feed_source` and
`syn001.stream_splitter` refuse to produce one; `syn001.product_sink` may read one. A drum's products are declared
`vapor_liquid`.

**D5. Trial states.** A pure-fluid block turns the provider refusals `phase_not_stable`, `near_critical`,
`no_saturation` and `out_of_domain` into `invalid_trial_state`. Any other refusal is a defect.

**D6. The `thermal.*` family** (`heater`, `valve`, `mixer`, `flash`, `pump`, `compressor`, `turbine`) is
basis-generic over the declared stream forms and lives in new modules. Admission:

| | `iapws95-v1` | `coolprop-heos-v1` | `wilson-ig-v2` |
| --- | --- | --- | --- |
| `thermal.heater`, `valve`, `mixer`, `flash`, `pump` | yes | yes | — |
| `thermal.compressor`, `thermal.turbine` | yes | yes | yes, single-phase vapour |
| `syn001.tp_heater`, `tp_flash`, `ph_flash`, `valve`, `adiabatic_mixer` | — | — | yes |

The machines carry no entropy rows and no internal columns. Their isentropic enthalpy comes from a block that solves
the PS relation inside itself (single-phase), or in closed form (saturated). On Wilson the block relies on an
additive-entropy premise, admitted by identity.

**D7. γ–φ faces.** `models/syn001/tp_state.py`'s shared EO helpers dispatch on the equilibrium form to S10-C's
γ–φ blocks. The five unit modules take their manifest's provider fields from the bound provider. SYN-001's code path
is textually unchanged, and the units' SYN-001 manifests differ only in `artifact_hash`.

**D8. `wilson-ig-v2`** (`thermo/wilson_ig_v2.py`) is a new provider id over the same records.
- It forwards every v1 answer bit for bit.
- It adds `s` in closed form from S10's potential, with the datum s_i^ig(298.15 K, 101 325 Pa) = 0.
- It refuses n-derivatives of `s` at a zero mole fraction.
- It is the provider the Wilson record source selects (WO-D5, gated bitwise).
- `v` and `Z` are not added, because the method's liquid has no volume. The pump stays refused on Wilson.

**D9. The verifier.**
- Saturated pure streams are judged on their carried split: `.saturation` and `.fraction` checks, and
  `independent_split` `not_applicable(temperature_degenerate)`.
- Machines are judged by the verifier's own PS bisection.
- Wilson lifted splits are judged by a fresh TP flash and the provider's `stability()`, with degeneracy routing. For
  everything the first pass's declared-phase form already handles, this form gives identical checks.

**D10. Zero flow.** Single-phase thermal outlets whose temperature is set by the energy row get `DORMANCY_RULES`
entries (ADR 0012 D12). Saturated outlets are regular at dormancy.

## Alternatives considered

- **Lifted splits with discovered regimes for pure fluids.** One compiled function serves every regime, so every
  phase block is evaluated at every iterate. A Helmholtz provider refuses a phase beyond ε_σ, and two-phase Newton
  steps leave the saturation line at second order. Fixing this needs per-regime block forms in the region (T05b-scale
  work) or a synthetic metastable extension. Deferred; Frank may ask for it.
- **The K-form row for C = 1.** It degenerates to V·L·(1 − K).
- **A `vapor_fraction` field on `StreamState`, or a new (n, H, P) state definition.** The first changes a frozen
  provider request type; the second re-plumbs the stack.
- **Reading wet inlets by (n, T, P).** Every wet-stream reader would start with its latent heat misplaced.
- **Generalizing the `syn001.*` units to pure fluids, or per-basis namesake families.** The first conflicts with
  their lifted-split form; the second is N×M duplication.
- **A T_s column with an entropy row.** No row kind exists for it, and T_s would have no dormancy label.
- **New `wilson.*` ids, or subclasses per basis.** Registries keyed by model id would be duplicated, and so would
  each `contribute`.
- **Refusing the Wilson machines; entropy computed in the unit layer; a v2 with a Poynting volume; a second Wilson
  basis.** Respectively: against Frank's directive; a provider bypass; a different method; two record sources for
  one file.

## Consequences

- **C1.** Pure-fluid flowsheets enter S11: steam cycles, refrigeration cycles, throttling, separator drums, and
  compressors on any of 123 CoolProp fluids or IAPWS-95 water. Each stream's regime is declared.
- **C2.** On Wilson, heaters, TP and PH flashes, valves and mixers enter flowsheets with lifted two-phase streams, and
  vapour compressors and turbines with them.
- **C3.** `LIBRARY_ONLY_PROVIDERS` regains `"wilson-ig-v1": "S10"`. The envelope gains seven members and the rows
  L-TH-1…7 and L-GP-1…3.
- **C4.** W27 v3 gains seven model functions (heater, valve, mixer, flash, pump, compressor, expander) and the v2
  provider row; S4 is generated at I1b.

## Acceptance evidence

- Gates G9–G13 of `docs/derivations/S11-units-design.md` §6, beside G1–G8 of the first pass.
- `evidence/S11/<commit>/manifest.json` at `tested`.
- One `reviewer` pass covering tracks C and D.
