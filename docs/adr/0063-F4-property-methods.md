# ADR 0063 — F4: property methods, composition, convention and the thermo face

**Status:** **Proposed, 2026-11-05.** W1 pass P2 (ADR 0057, R-928); Accepted after the W1 P2 reviewer pass; built in 0.6
on `wp/F4`. Method slots stay `preview` to the end of 0.6 (R-929). **Author:** design lane (`architect`). **Refines:**
`target-architecture.md` §2.3, §3 F4. **Adopts verbatim:** Q2.R1–R9 and Q2.A1–A9, A11 (Amendments 2 and 3); cites Q3.R5
and adopts Q3.A5; Q1.A1, A2, A6. **Amends:** ADR 0001 D5.2 for v2 (recorded shifts replace "no implicit shift";
`ELEMENTAL-ref-v1` joins D5's list and `interfaces-frozen.md` §3); ADR 0050 D5 for v2; ADR 0011 D2 by a new decision
naming the datum (v2 reaction consistency per component, Q2.R4); ADR 0061 D10's last paragraph (D2 below); `SolvePolicy`
schema (`scales["specific_enthalpy"]` and a new optional `energy_check` object, D6). Builds on ADR 0060 (D3 self-hash,
D4 `vocab` space) and ADR 0062 (`EvaluationState`, layout, ids).

## Decisions

### D1. Vocabulary registry (`openflowsheet/methods/vocabulary.py`, version `vocab-v1`, static `vocab` space)

Item = `{name, index: none | component | component_pair | species | phase, kind_by_basis: {mol, segment_mol, kg},
phase_specific, reference_dependent, derivatives: {T, P, n} max order}`. `vocab-v1` items: `h`, `s`, `g` (reference-
dependent), `v`, `Z`, `cp`, `lnphi[c]`, `Psat`, `Tsat`, `h_ig`, `s_ig` (the anchor states, Q2.R9 (b)). Kinds per basis
follow Q7.A4 (table below). X17 adds transport items by an additive version. **Legacy adapters**
(`methods/legacy_adapters/<provider>.py`, new modules) map legacy names (`h`, `s`, `v`, `Z`, `cp`, `lnphi_<c>`, `Psat`,
`Tsat`) to items and convert `EvaluationState → StreamState` (ADR 0062 D2); SYN-001's `lnK` is not mapped (F4 composes
no SYN-001 method).

| Item | `mol` | `segment_mol` | `kg` |
| --- | --- | --- | --- |
| `h`, `g`, `h_ig` | `molar_enthalpy` | `segment_molar_enthalpy` | `specific_enthalpy` |
| `s`, `s_ig` | `molar_entropy` | `segment_molar_entropy` | `specific_entropy` |
| `cp` | `molar_heat_capacity` | `segment_molar_heat_capacity` | `specific_heat_capacity` |
| `v` | `molar_volume` | `segment_molar_volume` | `specific_volume` |

`segment_molar_heat_capacity`, `segment_molar_volume` and `specific_heat_capacity` are added to ADR 0062 D1's table
(additive, R2).

### D2. Composition, identity and data

`compose(method: Descriptor, lock: DataLock, substream: str, sources: [Descriptor]) -> ComposedProvider` (pure; fresh
objects each call). A `ComposedProvider` implements the frozen protocol (`describe()` returns a `PropertyCapabilities`
with `state_definition = "evaluation-state-v1"`, `phases = ()` and `flashes = ("TP",)` (the phase models are in
`describe_method()`), `properties` = the legacy names of the vocabulary items provided, `components` = the substream's,
`reference_convention` = the flowsheet convention) plus `describe_method() -> MethodDescription` (new type:
`fluid_model: split | single`, `phase_models` with supports (Q4.R8), `vocabulary_version`, `attributes_read`,
`convention`, `shifts`, `bridges`, `native_convention`, `boundary_records`).

**Methods in 0.6** (F1 `property_method`, v2 payload `{family, required_fields, phase_models, vocabulary,
derivative_orders, attributes_read, convention_capability, domain_rules}`): delegating `composed.pr-c1-v1`,
`composed.wilson-ig-v2`, `composed.iapws95-v1`, `composed.coolprop-heos-v1` (all `split`, Q4.R6), and the re-implemented
`cubic.pr-v1` (`single`). A delegating composition is admitted only when its delegate reads exactly the lock's data:
- `composed.pr-c1-v1` and `composed.wilson-ig-v2`: the substream's records (and parameter set) are one legacy file's
  indexed records in file order, so that `records.legacy_views.legacy_path_for` returns the delegate's packaged path
  (ADR 0061 D12).
- `composed.coolprop-heos-v1`: one `s07` record, the provider built with its legacy id.
- `composed.iapws95-v1`: one record with water's InChIKey, of which the method reads only identity and `formation`.

Otherwise the composition is refused `records_not_delegable(<method>, <substream>)`. The adapter maps the substream's
components onto the delegate's component vector by id. The composition then calls the legacy provider unchanged.

**`implementation_sha256`** is ADR 0060 D3's formula; nothing new. A delegating method's `implementation.modules` lists
its adapter and composition modules **and the delegated legacy modules** (`openflowsheet/thermo/pr_c1.py`, …; ADR 0060
D6's implementation sets), and D3's import-closure check enforces it, so an edit to a delegated module moves the method.
The import closure of every composed method includes `thermo/__init__.py` and `material/*`, so an edit there moves every
v2 method's `implementation_sha256`; this is by design.

**`data_sha256` [narrows ADR 0061 D10, as its risk 8 allowed]:** a composed provider's `data_sha256 =
document_sha256({"method_lock": L_m, "delegate_data_sha256": d})`, where `L_m` is the lock restricted to the substream's
components, the parameter sets matched to them (ADR 0061 D5), and this method's entry and options. `L_m` is an
`openflowsheet-data-lock-v1` document holding the substream's `components` entries in revision order, every parameter
set with at least one key matched to them (ascending), this substream's `methods` entry and this method's
`method_options`; `d` is the delegated legacy provider's own `describe().data_sha256` (covers inputs no record carries:
IAPWS-95's coefficient file, CoolProp's fluid table), else `null`. An unrelated method joining a flowsheet then moves no
cache key. The full `data_lock_sha256` is still recorded per run (ADR-F8). ADR 0061 D10 carries this rule (W1 P2 review
ruling 1).

### D3. Source stack

Each (item, phase) a method set needs routes to exactly one source: the thermo method first, then `property_source`
descriptors in the method set's `sources` list. Two sources providing one (item, phase) without an explicit
`assign: {<item>: <source>}` is refused `source_conflict(<item>, <a>, <b>)`. 0.6 ships the thermo method only;
add-on payloads (X17, X15 `capeopen`) are preview.

### D4. Convention, anchors, bridges (Q2.R1–R9 adopted)

At composition on `ELEMENTAL-ref-v1`, for each component c, anchor a = the record's `anchor_phase` (never a method's
choice; adding a method never re-anchors):
1. `a = null` → `anchor_undetermined(<c>)`, refused on `ELEMENTAL-ref-v1`.
2. Native anchor value h^m_c(a; T°, P°), s^m_c, at T° = the double nearest 298.15, P° = 1e5 Pa, pure c (`n = e_c`,
   others `+0.0`), through the method's guard and domain (Q2.R9 (c)):
   - `ig`: the method's ideal-gas state, never its vapour root unless the vapour model is an ideal gas (Q2.R9 (b)).
     IAPWS-95 and CoolProp: φ° alone via the kernels' `phi_jet` (`iapws95.py:424–428`) and `_jet`
     (`coolprop_heos.py:509–545`), with Q2.R9's two formulas. Wilson-ig-v2: its VAPOR (ideal gas). PR-C1 (A3-a):
     `pr_c1.h_ig` (`src/openflowsheet/thermo/pr_c1.py:315`), which its h sums with the departure (`pr_c1.py:520`); on
     the `m01` records Δ_{PR-C1,c} is exactly 0.0. `cubic.pr-v1`: its ideal-gas c_p integral, separate by construction.
   - `l`, `s:<form>`: the method's pure phase; `aq`: infinite dilution (no 0.6 method; refused).
3. If the method cannot evaluate a: bridge (Q2.R8) through `transitions` or the difference of two formation entries,
   recorded `anchor_bridged(<m>, <c>, <a>-><φ>)`; else `anchor_unavailable(<m>, <c>, <a>)`.
4. Δ_{m,c} = Δf h°_c (+ bridge) − h^m_c; s likewise; Q2.R4's datum (0, s° or 0) when no formation data.
5. For a method providing `s`, Δˢ_{m,c} = s°_c − s^m_c(a; T°, P°). A record without s° in its anchor phase takes s = 0
   there, with notice `entropy_datum(<c>)`, and any reaction or equilibrium reading `s` or `g` of c is refused
   `component_not_reaction_consistent(<c>)` (default pending a specifier ruling, risk 5). A method without `s` (PR-C1,
   `pr_c1.py:761`) gets no S shift and provides no `s`, `s_ig` or `g`.

Shifts are constants in `describe_method().shifts`. **Application:** at the extensive level in fixed component order,
`Ḣ = n_tot·h_native; for c in order: Ḣ = Ḣ + n_c·Δ_{m,c}` (no fma), likewise S; T and P derivatives are the native
ones untouched; ∂/∂n_c adds Δ_{m,c}. On a native convention (Q2.R5) no shift is applied and only methods with that
native convention for every component are admitted (`convention_mismatch(<m>, <convention>)`). Water: the binder
takes whichever record the revision names (`s05`: datum, non-reacting; `s10`: formation data, reacting; ADR 0061 risk
3 closes with no merged record).

### D5. Method sets, sides, boundaries

`MethodSet = {<substream id>: {method, version, options, sources?: [<property_source id>…], assign?: {<item>:
<source>}}}`; revision `property_methods` (preview). A unit evaluates each side (manifest-declared port group, ADR-F6;
default one side) with one method set. PH over several substreams: one scalar T solve on `Σ_s Ḣ_s(T) − ṁĥ = 0` (Q8.R5).
A **method boundary** (two endpoint sides, different method sets) is admitted iff (i) every component is anchored or
bridged in the consumer, (ii) Q3.R5's integer C solves C A = A′Π and the consumer evaluates `b′ = C b` in fixed order
(`material/basis.py`, ADR 0062), (iii) each dropped species is reported (`solid_candidate_dropped`, `species_dropped`).
Refusals: `anchor_unavailable`, `species_basis_incompatible`, `convention_mismatch`. The boundary report carries `T_B(ĥ)
− T_A(ĥ)` as a non-R0 float; no boundary energy term.

### D6. Scales (S7)

`ĥ` scale = c_ref·s_T; step bounds on `ĥ` = c_ref × the T step bounds; energy check 1e-5 W + 1e-8 E with E = Σ|Q| +
Σ|W| + Σ_S ṁ_S c_ref ΔT_ref + Σ_r |ξ_r Δr h_r|. Constants live in the policy:
`SolvePolicy.scales["specific_enthalpy"]` (a kind nominal, = c_ref·s_T) and a new optional object
`SolvePolicy.energy_check: {capacity_ref, delta_T_ref}`, with registered values c_ref = 2.0e3 J/(kg K) and ΔT_ref =
100 K. Both are required by schema in a v2-compiled run's policy, and code supplies no default, so the values are
always in `policy_sha256`; both are absent from every v1 policy (whose `policy_sha256` therefore does not move). The ĥ
step bound reads c_ref from `energy_check`. No scale, bound or tolerance reads `|ĥ|`, `|Ḣ|` or a shift.

### D7. `MaterialModel` and the thermo face (`openflowsheet/material/model.py`)

`state_point(point_id, inputs, spec, methods, phases, outputs, formulation)` as note §2.3.9; `spec` pairs carry their
quantity kinds. At compile time the model groups points by composed method and builds **one CasADi callback per method**
whose input is the stacked inputs of its N points and whose Jacobian sparsity is block-diagonal (one block per point).
Procedural points solve inside the callback (ADR 0064 D1's fixed-set augmented system, with derivatives by the
implicit-function theorem on its converged Jacobian: `dT/dĥ = ṁ/∂Ḣ_T` at a one-phase point, 0 at π = C + 1); outputs at
inactive phases are ADR-F5's labels. Exact cache per point, keyed on (composed identity: method id, version,
`implementation_sha256`, `data_sha256`, convention; the point's spec and canonical inputs; phase set). Delegating
methods loop over points calling the legacy provider; `cubic.pr-v1` evaluates all N points in vectorised NumPy
(closed-form cubic roots, analytic derivatives in T, P, n).

### D8. Verifier

A v2 run is recomposed from its data lock (fresh `compose`, no shared cache); every state point is re-evaluated.

## Alternatives rejected

- *`data_sha256` = the whole lock* (ADR 0061 default): every method's cache identity moves when any method joins.
- *Shift on molar h inside the provider*: ties the shift to a basis; the extensive form serves `kg` and groups alike.
- *Anchoring `ig` at the vapour root at low P* for PR-C1: an approximation with a domain risk; A3-a asks for the exact ideal-gas part.
- *A merged water record*: identity of a record nobody wrote; the two real records already cover both uses.
- *Scale constants in code*: they change R0; the policy is where R0 constants live.

## Migration proof (M2)

F0 PASS; (i) delegating compositions reproduce bitwise on M6's request sets every native-layer value and derivative and
every `describe()` field except shifts and identity hashes; (ii) Q2.A1; (iii) `cubic.pr-v1` against `pr-c1-v1` in the
K04 R2 comparison with a registered difference record, the harness mapping VAPOR/LIQUID to FLUID with `character`
(Amendment 2), never claimed bitwise. Legacy runs keep legacy providers.

## Exit tests

- **E-F4-1** M2 (i)–(iii). **E-F4-2** Q2.A1–A9, A11 (A11 (b) `unsupported` without the coolprop extra; O-12, O-13).
- **E-F4-3 (A3-a)** On `composed.pr-c1-v1` and `cubic.pr-v1`, N2 and CH4 (M01 records): `h_shifted(ig; T°)` = Δf h°
  within 2 ulp, and the VAPOR at (T°, P°) differs from it by the method's departure, |Δ| ≥ 1 J/mol (non-vanishing
  control); mutation: anchoring at the vapour root makes the first difference non-zero beyond 2 ulp.
- **E-F4-4** Q1.A1, A2 (IAPWS-95 through the thermo face; O-1 measured: report the achieved PH residual), Q1.A6.
- **E-F4-5** S7: Δf h° of one non-reacting component + 1e6 J/mol leaves every scale, step bound and verdict unchanged.
- **E-F4-6** Typed refusals: `anchor_unavailable`, `anchor_undetermined`, `species_basis_incompatible`,
  `convention_mismatch`, `source_conflict` (triggered with a test-only source registration), `records_not_delegable` (an
  edited `m01` N2 record); Q3.A5.
- **E-F4-7** Batching (same machine, `cubic.pr-v1`, N = 300 PH points, values plus Jacobian): batched per-point ≤ 0.1 ×
  unbatched; delegating methods ≤ 1.05 ×. Median of 5 runs, log in the evidence manifest.
- **E-F4-8** Verifier recomposition: a run's certificate with fresh composition equals the solver-side values bitwise.

## New catalogue codes

`anchor_unavailable`, `anchor_bridged`, `anchor_defaulted` (notice, ADR 0061), `anchor_undetermined`,
`component_not_reaction_consistent`, `convention_mismatch`, `source_conflict`, `solid_candidate_dropped`,
`species_dropped`, `specification_degenerate`, `ideal_gas_state_unavailable` (cause), `records_not_delegable`,
`entropy_datum` (notice).

## Work orders (`wp/F4`; after F2-WO3 and F3-WO3/WO4)

| # | WO | Files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **F4-WO1** Vocabulary, adapters | `methods/vocabulary.py`, `methods/legacy_adapters/*.py` | adapter round trips; `vocab` validator in F1 | no | Sonnet |
| 2 | **F4-WO2** Compose, delegating methods, identity | `methods/{compose,description,lock_view}.py`; four v2 descriptors | E-F4-1 (i), E-F4-8 | no | Opus |
| 3 | **F4-WO3** Convention | `methods/convention.py` (anchors, bridges, shifts); the CoolProp anchor calls the private `_jet` on a state the adapter builds as the guard does (`coolprop_heos.py:475`; Amendment 3 covers this) | E-F4-2, E-F4-3 | no | Opus; reviewer-adjacent |
| 4 | **F4-WO4** MaterialModel, scales, boundaries | `material/{model,scales,boundary}.py`; `solve-policy` schema (`scales["specific_enthalpy"]`, `energy_check`) | E-F4-4, -5, -6 | no | Opus |
| 5 | **F4-WO5** `cubic.pr-v1` and batching | `methods/cubic_pr.py`; `scripts/bench_batching.py` | E-F4-1 (iii), E-F4-7 | no | Opus |
| 6 | Close-out | manifest, catalogue, gate, CI | all E-F4 | no | Sonnet |

**Unblocks:** F5 (WO4), X17 (WO1–2), X11 rest (WO2), PrISMa's equilibrium part (with F5).

## Risks (each with a default)

1. **PR-C1's ideal-gas part may not be separable** (fact, WO3). *Resolved by fact* (W1 P2 review N1): it is separable,
   `pr_c1.h_ig` (`src/openflowsheet/thermo/pr_c1.py:315`), summed with the departure at `pr_c1.py:520`; D4 uses it.
2. **Q2.A1's 4-ulp bound with many components** may fail where Σ|n_cΔ_c| ≫ |Ḣ| (fact). Default: fixed-order sum; a
   failure amends the bound per rulings rule 6, never the order.
3. **c_ref, ΔT_ref** (note R19; fact: F4/F6 measurements). Default: the registered values 2.0e3 J/(kg K), 100 K in
   `SolvePolicy.energy_check` (D6).
4. **CasADi callback overhead at N = 300** may hide the batching gain (fact, WO5). Default: one callback per method;
      if E-F4-7 fails, an architect question before WO6.
5. **Entropy shift for a record without s°** (W1 P2 review S6; ADR 0061 risk 6: no legacy record has s°). *Needs:* a
   specifier ruling as a Q2 amendment, batched with P3's specifier needs (orchestrator decision 2026-11-05,
   `docs/roadmap/decisions.md`). *Default:* D4 step 5 (s = 0 in the anchor phase, `entropy_datum(<c>)`, reactions and
   equilibria reading `s` or `g` of c refused); F4-WO3 proceeds on it.

## Edits `target-architecture.md` needs

§2.3.2–3: narrowed `data_sha256` (D2), `describe_method()`; §2.3.6: Amendment 2–3 anchor text and D4's PR-C1 rule;
§2.3.7: constants in `SolvePolicy.scales["specific_enthalpy"]` and `SolvePolicy.energy_check`; §2.3.8: Amendment 2's
(ii)–(iii) wording; §8: `PropertyCapabilities` row → `MethodDescription`; §3 F4 exit: "Q2.A1–A8" → "Q2.A1–A9, A11", add
Q3.A5 and E-F4-3.

## Review applied (W1 P2 review, `docs/reviews/W1-P2-review.md`, 2026-11-05)

Status stays Proposed. The S6 default and its referral follow `docs/roadmap/decisions.md` (2026-11-05).

| Finding | Edit |
| --- | --- |
| M4 (0063-1) | D2: delegation admitted only when the delegate reads exactly the lock's data; `records_not_delegable` (catalogue, E-F4-6). |
| M1 (0063-2) | D7: procedural points use ADR 0064 D1's fixed-set augmented system; dT/dĥ = 0 at π = C + 1. |
| S6 (0063-3) | D4 step 5: S shift only for methods providing `s`; s = 0 datum, `entropy_datum`; referral to the specifier as risk 5. |
| S9 (0063-4) | D6: `scales["specific_enthalpy"]` and `energy_check {capacity_ref, delta_T_ref}`, no code default; header, F4-WO4, risk 3. |
| S10 (0063-5) | D1: kind table per (item, basis); three kinds added to ADR 0062 D1. |
| S11 (0063-6) | D2: fill rule for `PropertyCapabilities` (`phases = ()`, `flashes = ("TP",)`, properties, components, convention). |
| S12 (0063-7) | D5: `MethodSet` gains `sources?` and `assign?`; E-F4-6 triggers `source_conflict` by a test-only source. |
| N1 (0063-8) | D4: PR-C1 anchors through `pr_c1.h_ig` (`src/openflowsheet/thermo/pr_c1.py:315`); risk 1 resolved by fact. |
| N2 (0063-9) | E-F4-5: a non-reacting component. |
| N5 | D2: the import closure includes `thermo/__init__.py` and `material/*`; an edit there moves every v2 method, by design. |
| N7 | F4-WO3: the CoolProp anchor's `_jet` state built as the guard does (`coolprop_heos.py:475`), covered by Amendment 3. |
| Ruling 1 | D2: `L_m` defined as an `openflowsheet-data-lock-v1` document; the ADR 0061 edit sentence dropped (applied there). |
| Ruling 2 | D6 placement fixed (S9 above); D2 narrowing accepted unchanged. |

Not applied: N3 (ĥ step count across water's latent heat) is a performance note with no edit. The cause
`ideal_gas_state_unavailable` stays in the catalogue although N1 removes its only use in D4; the review gives no edit.
