# ADR 0068 — Stream table and energy summary: `get_stream_table`, `stream-table-v1`

**Status:** **Proposed, 2026-11-06.** It takes effect on `main` when ST's manifest is `tested` and the reviewer pass is
done. Until then ST is built on `wp/ST`. Register entries are added on acceptance.
**Author:** design lane (`architect`), ST design pass. **Brief:** `docs/briefs/ST-architect.md`.
**Design note:** `docs/design/ST-stream-table.md` holds the normative detail; the § numbers below refer to it.
**Amends:**
- ADR 0019 D1, as **ADR 0019 Amendment 13**: `Inspection` gains `get_stream_table`. On acceptance, a pointer paragraph
  is added to ADR 0019 in the form of Amendment 4. Amendment 12 is ADR 0067. The Amendment 5 gap the recon found
  (cited by ADR 0037, absent from ADR 0019) is not filled here.
- `docs/interfaces-frozen.md`: one operation, one schema added (`stream-table.schema.json`), and the served MCP tool
  list widened by one tool.

**Does not amend:**
- ADR 0019 D5: the `ApiError` shape and its closed 15-code enum are unchanged.
- `API_EXIT_CODES`.
- Any run, bundle, manifest, certificate, replay or cache schema or writer.
- ADR 0013: no verifier rule changes.
- ADR 0001 D3/D4/D5: dormancy, sign and reference conventions are used as they stand.
- Q2.R7: v1 conventions are unchanged.

**Builds on:** ADR 0056 Amendment 1 (ST; FB-06, FB-02); ADR 0057 rules C1, C3, C4 and C5; target-architecture §2.6
(S11, "Constraints on the 0.4 packages"); foundation rulings Q1.R4, Q4.R1, Q4.R7; ADR 0058 (the catalogue, member-detail
`not_found`, and `explain` as the transport pattern); R-924. Adopts verbatim foundation rulings Amendment 5: Q1.R11,
Q1.R12, Q2.R11, Q4.R10, Q4.R11, Q4.R12 and Q1.A14, Q1.A15, Q2.A13, Q4.A13–A15.

## Context

A tutorial user needed internal API (`Iapws95Provider`, `EvaluationContext`, `PropertyRequest`, the phase by hand) to
compute H(S5) − H(S1) on a Rankine cycle, and could not find a stream's vapour fraction (FB-06, FB-02).
- No operation returns per-stream derived values. `get_artifact` on `<bundle>/solution-state.json` gives raw variables
  only.
- Only the verifier computes enthalpy flows, inside its checks, with verdict-specific phase snaps.
- Rule C5 requires projections that are derived after the solve from the verified state, given per phase and per
  substream, and never part of certificate identity.
- F0 (M1–M9) must not move.

## Decision

**D1. Computed on read, not stored** (note §3 D1). `Inspection.get_stream_table(job_id, *, pointer="", depth=12,
cursor=None, limit=50) -> Projection` reads `revision.json`, `solution-state.json`, `solution-certificate.json` and
`run-manifest.json` from the job's bundle and computes a `stream-table-v1` document.
- Nothing is written to a bundle, manifest, certificate, store or cache.
- The `Projection` has `subject_id = "stream-table:<job_id>"` and `sha256` = the document's canonical SHA-256.
- 0.3.0 jobs and bundles are served by the same path.

**D2. One `OPERATIONS` row** (note §6.1), placed immediately after `get_artifact`:
- right `read` (covering every principal's job);
- all four transports;
- HTTP `GET /v1/jobs/{job_id}/stream-table`;
- MCP tool `get_stream_table`, with a reviewed description;
- response `application-results.schema.json#/$defs/projection` (unchanged).

The default `depth` is `MAX_DEPTH` (12), because the document is 10 deep and depth 4 would elide every substream. This
is the only view operation whose default is not 4. Refusals use existing codes: `not_found` (including MSG's
member detail), `not_ready`, `unsupported` (`basis_unavailable(<id>)`) and `internal_error` (an inconsistent bundle).

**D3. The phase rule `st-phase-rule-v1`** (note §4.2), per stream, first match wins:
- **R0** dormant (`StreamState.is_dormant`): no phases; extensive values `+0.0`; T and intensives null with `zero_flow`
  (Q1.R4); no provider call; `n` and `m` are `+0.0` (Q1.R11).
- **R1** carried saturated split (`<S>.sat.V`, `<S>.sat.L` present): VAPOR (V) and LIQUID (L) at `(T_sat(P), P)`. The
  stream's `T` is the stored T; a refused `Tsat` nulls the properties only (Q1.R12).
- **R1′** carried lifted split (from the ST review, 2026-11-08): the stream of a heater-style lifted split (the list
  `verify_revision` derives from the revision) whose certificate has an `independent_split` row `not_applicable` for
  `temperature_degenerate` or `fresh_flash_unresolved`: VAPOR and LIQUID from the stored split at the split's (T, P),
  Ḣ summed from 0.0 as the verifier's `_phase_enthalpy` sums it; `phase_source: "carried_lifted_split"`, not flagged.
  A flagged stream with no such split that would reach R3 gets no number: `flash_failed(status=temperature_degenerate)`.
- **R2** declared producer-port phase: that phase at (T, P).
- **R3** otherwise: a fresh TP flash of the stream's own (n, T, P), with **no** ε_adm or τ_dew snap. Each substream
  reports `flash_near_phase_boundary` (Q4.R12 (b) (i); (ii) is decided by R1′ since the ST review).

A phase is listed iff its amount is `!= 0.0`, of either sign and never clamped, in the order VAPOR, LIQUID, with the
decision's ids (Q4.R11). Its id is Q4.R1's triple `{family, qualifier, ordinal}`; no rendered string is a key.

**D4. Provider calls and arithmetic** (note §4.3). ST uses a fresh provider (`provider_for(basis)`) and the verifier's
context (`model_version` and `constants_sha256` from the certificate).
- h is requested alone, exactly as the verifier requests it. The mixture `h` and SYN-001's per-component `h_<c>` are
  both accepted for h only.
- s and v are requested each alone, and only if declared.
- Ḣ is summed in the verifier's order, so ST's Ḣ equals the verifier helpers' bitwise wherever the two decide the same
  phases (exit test E7). The per-component form is summed as the verifier's helper of that form sums it: built-in
  `sum` as `checks.enthalpy_flow`, a 0.0-loop as `_phase_enthalpy` for R1′ (D1-1, from the ST review, 2026-11-08).
- ST imports from `verify` only `table.{FEED_MODELS, PRODUCT_MODELS, EXTERNAL_DUTY_MODELS, STAGED_DUTY_MODELS,
  WORK_MODELS}` and `column.duty`; for R1′, `orchestrator.splits.lifted_splits`, the verifier's own split list.

**D5. Quantities, SI only** (note §4.3, §5).
- Per substream (v1: one, id `mixed`) and per phase: `n`, `m`, `x`, `w`, `n_total`, `m_total`, `H_flow`, `S_flow`,
  `V_flow`, `h`, `h_mass`, `s`, `s_mass`, `rho` (phases also `v`, `phase_fraction_molar`, `phase_fraction_mass`).
- Per substream: `vapor_fraction_molar` and `vapor_fraction_mass` over the vapour group (v1: VAPOR), with the listed
  phases' sums as denominators, which `phase_fraction_molar` and `phase_fraction_mass` share (Q4.R10); and
  `flash_near_phase_boundary` (Q4.R12).
- Each substream carries `convention`, the provider's reference convention, which applies to every h and s in it.
- Density is `m / (n·v)`, and only from a provider's `v`.
- Every quotient is an IEEE division; a non-finite result is null with `value_not_finite` (Q4.R11 (c)).
- *From the ST review, 2026-11-08 (D1-6, D1-7; note §5):* a unit's port carries an `absent` map; a phase's `x` and `w`
  are given or null whole, and its `phase_fraction_molar` and `phase_fraction_mass` are nullable, so an underflowed
  phase mass is `value_not_finite` (Q4.A14 (d)).

**D6. Energy summary** (note §4.5).
- Per unit (feeds and sinks excluded): `ports` with Ḣ, `H_in`, `H_out`, `Q` and `W` (positive into the unit) and
  `closure = (Q + W) − (H_out − H_in)`. The closure is given only for units the certificate holds an `energy_balance`
  row for.
- Overall: the verifier's envelope definition, in its arithmetic order.
- Beside each, the certificate's rows are quoted (`index`, `id`, `result`, `scope`, `value`, `tolerance`, `reason`,
  `near_threshold`), together with the certificate's `judged_at`. ST never re-judges.

**D7. Absence.** Every object has an `absent` map, quantity → `{code, params}`; a value is null iff it has an entry.
There are seven new catalogue codes (below). No value is invented.

**D8. CLI.** `openflowsheet streams (--project DIR --job JOB_ID | BUNDLE_DIR) [--format text|json|csv] [--output
PATH]` (note §6.3). Project mode pages the operation; directory mode applies the same core function to a bundle on
disk, as `inspect` and `replay` do. JSON output is the document; CSV has one row per (stream, substream,
phase-or-total).

**Frozen-list changes.**
- New operation: `get_stream_table`. No new result-type name: the response is `Projection`.
- Schema added: `stream-table.schema.json` (format id `stream-table-v1`), listed in `schemas/registry.json`. Header,
  stream, substream, phase, unit and overall objects are open; phase id, absent entry and check quote are closed; growth
  is additive only (C5), and a breaking change is `stream-table-v2`. The substream object carries
  `flash_near_phase_boundary: boolean` from v1 on, and a stream's `checks` also quote its `independent_split` rows
  (Q4.R12).
- The served MCP tool list moves by one tool. With it removed, it equals `main`'s digest at ST's branch point; the new
  digest is recorded in ST's manifest and in `tests/test_t08_w2_surface_digest.py`.
- One new R4-G3 response snapshot. Every existing snapshot and every existing schema is byte-identical.

## Alternatives rejected

- **A run artifact written at solve time.** It edits the run path and adds a manifest member to every bundle (M3/M7 and
  replay risk). It costs provider calls on every solve, couples report failures to runs, cannot serve 0.3.0 bundles,
  and freezes values at the solve version's provider.
- **Both an artifact and an operation.** Two sources of truth, with no good answer to which is authoritative.
- **Reusing or refactoring the verifier's Ḣ helpers.** They return only scalars, embed verdict snaps, and differ per
  basis form; refactoring them edits `verify/` (an M5 numerics risk).
- **The carried lifted split for every lifted outlet.** *Amended from the ST review, 2026-11-08:* the first reason
  given here was false (`verify_revision` derives the list from the revision), and the second holds only where the
  `independent_split` check ran. Where it did not, R1′ reads the carried split. Everywhere else reading it would move
  the resolved-split streams off the verifier's arithmetic and lose their E7 bitwise status, and buy nothing, because
  the flash and the split agree there within the quoted check.
- **Exempting a flagged envelope from E8** (the ST review's option (a), 2026-11-08). It would loosen a gate around a
  wrong number: `T05b:SC-1`'s S2 was reported 2016 W low, with a vapour fraction of 0, at a temperature-degenerate
  stream whose every vapour fraction is consistent.
- **A typed full-document response, or a flattened record layout.** The first breaks ADR 0019 §4.1's bounded
  projection; the second still elides at depth 4 and loses per-substream grouping.
- **An ideal-gas density, or a per-component `s` sum, where the provider has none.** Both are inventions (R-924); a
  per-component key does not say whether it is pure-component or partial molar, and summed pure-component values drop
  the entropy of mixing (Q2.R11).

## Migration proof

No identity input changes:
- no file under `src/openflowsheet/{verify,thermo,models,run,orchestrator}/` nor `compiled.py` is modified;
- nothing is written to a bundle, manifest, certificate or cache;
- no fixture enters an `M8_FUNCTIONS` collector;
- no case enters `ROUND_TRIPS`.

Hence F0's M1–M9 are unchanged, and F0 PASS is required as proof (E13). Existing request and response schemas are
unchanged and their round-trip fixtures pass. Old stores and bundles are served by the same read path.

## Exit tests (note §11; F0 PASS implied on each)

- **E1** TH-C1 Rankine (IAPWS-95):
  - each unit's `|closure| ≤` its row's tolerance;
  - `|(H(S5) − H(S1)) − (Q_B + Q_C + W_P + W_T)| ≤` the envelope tolerance;
  - signs `W_P > 0`, `W_T < 0`, `Q_B > 0`, `Q_C < 0`.
- **E2** Lever rule at S4: `|vf_molar − (h4 − h_L)/(h_V − h_L)| ≤ 10·tol_T/(n4·Δh_vap) + 1e-12`, where
  `h4 = (H(S3) + W_T)/n4` and `h_L`, `h_V` are evaluated independently. At S5, `vf_molar = V5/(0.0 + V5 + L5)` and `|h −
  h_L(P5)| ≤ (|V5|(h_V − h_L) + |V5 + L5 − n5|·|h_L|)/n5 + 8ε|h_L|`.
- **E3** IAPWS-95 Table 8 at 450 K (h, s, ρ of both phases) to 1e-7 relative, through `build` on a set state. S4's
  stored T is kept (Q1.A15).
- **E4** Limiting cases: a dormant stream (`+0.0` extensive values, null T and intensives); single-phase vapour
  fraction exactly 0 or 1; on SYN-001, `|w − x| ≤ 8ε·x`; Q1.A14, Q4.A13 (b), (f), Q4.A14 (d).
- **E5** Absence: null ⇔ an `absent` entry, every code catalogued, no NaN or inf. Q2.A13.
- **E6** Consistency:
  - Σx and Σw within 1e-12 of 1;
  - the phase sums equal the stream's;
  - the Rachford–Rice residual is ≤ 1e-10 on SYN-001 two-phase streams. Q4.A13 (a), (d).
- **E7** Bitwise Ḣ equality with the verifier helpers for R1, for R2 on the declared-mixture and γ–φ forms, and for R3
  single-phase flashes. Q1.A15 (c); Q4.A14 (a)–(c).
- **E8** Envelope: bitwise equal to the quoted value when `judged_at == "final_state"` and every stream is
  E7-bitwise; otherwise within the tolerance.
- **E9** Determinism: identical canonical bytes and `sha256` across calls and processes.
- **E10** Every v0.3.0 fixture bundle with the four members is served and valid; the others are refused `not_found`.
- **E11** Transport parity and every refusal on every transport.
- **E12** MCP digest without the tool, R4-G3 snapshots, `API_EXIT_CODES` and existing schemas are all unchanged.
- **E13** `corpus_identity.py --check` PASS; there is no diff under the frozen directories.
- **E14** ≤ 0.5 s on TH-C1 and ≤ 2 s on the largest corpus case (recorded).
- **E15** MSG's C3 runtime audit passes.
- **E16** The report's decision near a phase boundary: Q4.A15 (note G16).

## New catalogue codes (ADR 0058 C3)

- `zero_flow(stream)` (notice; reuse it if present);
- `property_not_provided(provider, property)` (not_supported);
- `property_evaluation_failed(stream, phase, property, status)` (numerical);
- `flash_failed(stream, status)` (numerical);
- `value_not_finite(subject, quantity)` (numerical);
- `stream_enthalpy_absent(subject, streams)` (notice);
- `energy_balance_undefined(unit, model)` (not_supported).

Families and gaps are in note §6.4.

## Work orders (`wp/ST`; note §10)

- **WO-1** Core `application/stream_table.py` with its tests (Opus). It touches only new files and may start before
  MSG merges.
- **WO-2** Schema and fixtures (Sonnet).
- **WO-3** The operation on all transports, digest and snapshots (Opus).
- **WO-4** Catalogue entries (Sonnet drafts, Opus checks).
- **WO-5** CLI `streams` (Sonnet).
- **WO-6** Docs and the MCP description (Sonnet; the description is reviewed in ST's reviewer pass).
- **WO-7** Evidence, the full gate, F0, CI and the reviewer (Opus).

WO-2 onward start after `wp/MSG` merges into `main`. Files shared with MSG are listed in note §9.

## Risks and open questions (each with a default; note §12)

- **O1 (fact).** Does the registry entry move F0? *Default:* add it. If it does move F0, the schema becomes
  `application-results.schema.json#/$defs/stream_table`.
- **O2 (fact).** Is a default depth of 4 pinned by a test? *Default:* 12; if it is pinned, keep 4 and document it.
- **O3 (preference).** Web shell. *Default:* later.
- **O4 (preference).** CSV. *Default:* in.
- **O5 (fact).** Is TH-C1's S4 saturated? *Default:* yes; otherwise the next thermal case.
- **O6 (fact) — resolved 2026-11-06.** E3's expectations are read from the committed S05 reference
  `docs/derivations/scripts/s05_reference.json` `/saturation/450` (independent mpmath values registered against Table 8,
  `S05-IAPWS95-spec.md:660`). A mismatch with the provider is reported, never adjusted.
- **O7 (preference).** `from_bundle` public. *Default:* yes, as a library helper outside the contract.
- **O8 (fact).** Coupled runs. *Default:* served; an external unit's closure is `energy_balance_undefined`.

**Riskiest point:** near a phase boundary, R3's unsnapped flash can decide differently from the verifier, and providers
deliver h in two value shapes. Both are mitigated by the quoted checks, `judged_at`, and E6–E8. *Ruled by Q4.R12
(Amendment 5):* the raw flash stays; `flash_near_phase_boundary` and the quoted `independent_split` rows mark where the
verifier may have decided otherwise; E16 tests it. *Scope of Q4.R12 (a), from the ST review, 2026-11-08:* the raw
flash stays wherever the verifier could flash; where it could not, R1′ applies (D3).

## Specifier questions (defaults apply until ruled; note §13)

Ruled 2026-11-06 (foundation rulings Amendment 5): SQ-ST-1 Q4.R10, SQ-ST-2 Q1.R11, SQ-ST-3 Q4.R12, SQ-ST-4 Q1.R12,
SQ-ST-5 Q2.R11, SQ-ST-6 Q4.R11; each default adopted with the precisions of §17's table.

- **SQ-ST-1** Vapour fraction on both bases, over the VAPOR family; no "quality" member; 0 or 1 outside the dome.
- **SQ-ST-2** The T of a dormant stream is null (Q1.R4), not the stored label.
- **SQ-ST-3** R3 uses an unsnapped TP flash.
- **SQ-ST-4** R1 phases are evaluated at `(T_sat(P), P)`.
- **SQ-ST-5** Density only from `v`; per-component values are accepted for h only.
- **SQ-ST-6** Phases are listed iff their amount is `!= 0.0`.

## Amendment 5 applied (2026-11-06)

Edits 0068-1 to 0068-7 of foundation rulings §17 (Amendment 5) are applied: 0068-1 (Builds on), 0068-2 (D3), 0068-3
(D5), 0068-4 (Alternatives rejected), 0068-5 (E2–E7, E16), 0068-6 (Riskiest point, Specifier questions) and 0068-7
(Frozen-list changes).
