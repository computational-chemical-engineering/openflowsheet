# ADR 0063 — F4: property methods, composition, convention and the thermo face

**Status:** **Proposed, 2026-11-05.** W1 pass P2 (ADR 0057, R-928); Accepted after the W1 P2 reviewer pass; built in
0.6 on `wp/F4`. Method slots stay `preview` to the end of 0.6 (R-929). **Author:** design lane (`architect`).
**Refines:** `target-architecture.md` §2.3, §3 F4. **Adopts verbatim:** Q2.R1–R9 and Q2.A1–A9, A11 (Amendments 2 and
3); cites Q3.R5 and adopts Q3.A5; Q1.A1, A2, A6. **Amends:** ADR 0001 D5.2 for v2 (recorded shifts replace "no implicit
shift"; `ELEMENTAL-ref-v1` joins D5's list and `interfaces-frozen.md` §3); ADR 0050 D5 for v2; ADR 0011 D2 by a new
decision naming the datum (v2 reaction consistency per component, Q2.R4); ADR 0061 D10's last paragraph (D2 below);
`SolvePolicy` schema (two optional `scales` keys, D6). Builds on ADR 0060 (D3 self-hash, D4 `vocab` space) and ADR 0062
(`EvaluationState`, layout, ids).

## Decisions

### D1. Vocabulary registry (`openflowsheet/methods/vocabulary.py`, version `vocab-v1`, static `vocab` space)

Item = `{name, index: none | component | component_pair | species | phase, kind_by_basis: {mol, segment_mol, kg},
phase_specific, reference_dependent, derivatives: {T, P, n} max order}`. `vocab-v1` items: `h`, `s`, `g` (reference-
dependent), `v`, `Z`, `cp`, `lnphi[c]`, `Psat`, `Tsat`, `h_ig`, `s_ig` (the anchor states, Q2.R9 (b)). Kinds per
basis follow Q7.A4 (`h`: `molar_enthalpy`, `segment_molar_enthalpy`, `specific_enthalpy`). X17 adds transport items by
an additive version. **Legacy adapters** (`methods/legacy_adapters/<provider>.py`, new modules) map legacy names
(`h`, `s`, `v`, `Z`, `cp`, `lnphi_<c>`, `Psat`, `Tsat`) to items and convert `EvaluationState → StreamState` (ADR 0062
D2); SYN-001's `lnK` is not mapped (F4 composes no SYN-001 method).

### D2. Composition, identity and data

`compose(method: Descriptor, lock: DataLock, substream: str, sources: [Descriptor]) -> ComposedProvider` (pure; fresh
objects each call). A `ComposedProvider` implements the frozen protocol (`describe()` returns a `PropertyCapabilities`
with `state_definition = "evaluation-state-v1"`) plus `describe_method() -> MethodDescription` (new type: `fluid_model:
split | single`, `phase_models` with supports (Q4.R8), `vocabulary_version`, `attributes_read`, `convention`,
`shifts`, `bridges`, `native_convention`, `boundary_records`).

**Methods in 0.6** (F1 `property_method`, v2 payload `{family, required_fields, phase_models, vocabulary,
derivative_orders, attributes_read, convention_capability, domain_rules}`): delegating `composed.pr-c1-v1`,
`composed.wilson-ig-v2`, `composed.iapws95-v1`, `composed.coolprop-heos-v1` (all `split`, Q4.R6), and the
re-implemented `cubic.pr-v1` (`single`). A delegating composition builds the legacy provider from records through ADR
0061's legacy views and calls it unchanged.

**`implementation_sha256`** is ADR 0060 D3's formula; nothing new. A delegating method's `implementation.modules` lists
its adapter and composition modules **and the delegated legacy modules** (`openflowsheet/thermo/pr_c1.py`, …; ADR 0060
D6's implementation sets), and D3's import-closure check enforces it, so an edit to a delegated module moves the method.

**`data_sha256` [narrows ADR 0061 D10, as its risk 8 allowed]:** a composed provider's
`data_sha256 = document_sha256({"method_lock": L_m, "delegate_data_sha256": d})`, where `L_m` is the lock restricted
to the substream's components, the parameter sets matched to them (ADR 0061 D5), and this method's entry and options;
`d` is the delegated legacy provider's own `describe().data_sha256` (covers inputs no record carries: IAPWS-95's
coefficient file, CoolProp's fluid table), else `null`. An unrelated method joining a flowsheet then moves no cache key.
The full `data_lock_sha256` is still recorded per run (ADR-F8). Edit for ADR 0061 D10: "`data_lock_sha256` is every
composed provider's `data_sha256`" → "each composed provider's `data_sha256` is ADR 0063 D2's narrowed lock".

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
     (`coolprop_heos.py:509–545`), with Q2.R9's two formulas. Wilson-ig-v2: its VAPOR (ideal gas). PR-C1 (A3-a): the
     legacy module's ideal-gas function that its own h sums with the departure (the WO names it by `file:line`); if the
     module has none separable, the WO stops (a premise of this ADR is false) and the default is refusal
     `anchor_unavailable(composed.pr-c1-v1, <c>, ig)` with cause `ideal_gas_state_unavailable`, native convention
     kept (Q2.R5). `cubic.pr-v1`: its ideal-gas c_p integral, separate by construction.
   - `l`, `s:<form>`: the method's pure phase; `aq`: infinite dilution (no 0.6 method; refused).
3. If the method cannot evaluate a: bridge (Q2.R8) through `transitions` or the difference of two formation entries,
   recorded `anchor_bridged(<m>, <c>, <a>-><φ>)`; else `anchor_unavailable(<m>, <c>, <a>)`.
4. Δ_{m,c} = Δf h°_c (+ bridge) − h^m_c; s likewise; Q2.R4's datum (0, s° or 0) when no formation data.

Shifts are constants in `describe_method().shifts`. **Application:** at the extensive level in fixed component order,
`Ḣ = n_tot·h_native; for c in order: Ḣ = Ḣ + n_c·Δ_{m,c}` (no fma), likewise S; T and P derivatives are the native
ones untouched; ∂/∂n_c adds Δ_{m,c}. On a native convention (Q2.R5) no shift is applied and only methods with that
native convention for every component are admitted (`convention_mismatch(<m>, <convention>)`). Water: the binder
takes whichever record the revision names (`s05`: datum, non-reacting; `s10`: formation data, reacting; ADR 0061 risk
3 closes with no merged record).

### D5. Method sets, sides, boundaries

`MethodSet = {<substream id>: {method, version, options}}`; revision `property_methods` (preview). A unit evaluates each
side (manifest-declared port group, ADR-F6; default one side) with one method set. PH over several substreams: one
scalar T solve on `Σ_s Ḣ_s(T) − ṁĥ = 0` (Q8.R5). A **method boundary** (two endpoint sides, different method sets) is
admitted iff (i) every component is anchored or bridged in the consumer, (ii) Q3.R5's integer C solves C A = A′Π and the
consumer evaluates `b′ = C b` in fixed order (`material/basis.py`, ADR 0062), (iii) each dropped species is reported
(`solid_candidate_dropped`, `species_dropped`). Refusals: `anchor_unavailable`, `species_basis_incompatible`,
`convention_mismatch`. The boundary report carries `T_B(ĥ) − T_A(ĥ)` as a non-R0 float; no boundary energy term.

### D6. Scales (S7)

`ĥ` scale = c_ref·s_T; step bounds on `ĥ` = c_ref × the T step bounds; energy check 1e-5 W + 1e-8 E with E = Σ|Q| +
Σ|W| + Σ_S ṁ_S c_ref ΔT_ref + Σ_r |ξ_r Δr h_r|. Constants live in the policy: optional `SolvePolicy.scales` keys
`enthalpy_capacity_ref` (default 2.0e3 J/(kg K)) and `delta_T_ref` (100 K), required for v2-compiled runs, absent from
every v1 policy (whose `policy_sha256` therefore does not move). No scale, bound or tolerance reads `|ĥ|`, `|Ḣ|` or a
shift.

### D7. `MaterialModel` and the thermo face (`openflowsheet/material/model.py`)

`state_point(point_id, inputs, spec, methods, phases, outputs, formulation)` as note §2.3.9; `spec` pairs carry their
quantity kinds. At compile time the model groups points by composed method and builds **one CasADi callback per
method** whose input is the stacked inputs of its N points and whose Jacobian sparsity is block-diagonal (one block per
point). Procedural points solve inside the callback (PH: Newton on T at the frozen phase set, then the implicit-function
derivatives `dT/dĥ = ṁ/∂Ḣ_T`, etc.); outputs at inactive phases are ADR-F5's labels. Exact cache per point, keyed on
(composed identity: method id, version, `implementation_sha256`, `data_sha256`, convention; the point's spec and
canonical inputs; phase set). Delegating methods loop over points calling the legacy provider; `cubic.pr-v1`
evaluates all N points in vectorised NumPy (closed-form cubic roots, analytic derivatives in T, P, n).

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
- **E-F4-5** S7: Δf h° of one component + 1e6 J/mol leaves every scale, step bound and verdict unchanged.
- **E-F4-6** Typed refusals: `anchor_unavailable`, `anchor_undetermined`, `species_basis_incompatible`,
  `convention_mismatch`, `source_conflict`; Q3.A5.
- **E-F4-7** Batching (same machine, `cubic.pr-v1`, N = 300 PH points, values plus Jacobian): batched per-point ≤ 0.1 ×
  unbatched; delegating methods ≤ 1.05 ×. Median of 5 runs, log in the evidence manifest.
- **E-F4-8** Verifier recomposition: a run's certificate with fresh composition equals the solver-side values bitwise.

## New catalogue codes

`anchor_unavailable`, `anchor_bridged`, `anchor_defaulted` (notice, ADR 0061), `anchor_undetermined`,
`component_not_reaction_consistent`, `convention_mismatch`, `source_conflict`, `solid_candidate_dropped`,
`species_dropped`, `specification_degenerate`, `ideal_gas_state_unavailable` (cause).

## Work orders (`wp/F4`; after F2-WO3 and F3-WO3/WO4)

| # | WO | Files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **F4-WO1** Vocabulary, adapters | `methods/vocabulary.py`, `methods/legacy_adapters/*.py` | adapter round trips; `vocab` validator in F1 | no | Sonnet |
| 2 | **F4-WO2** Compose, delegating methods, identity | `methods/{compose,description,lock_view}.py`; four v2 descriptors | E-F4-1 (i), E-F4-8 | no | Opus |
| 3 | **F4-WO3** Convention | `methods/convention.py` (anchors, bridges, shifts) | E-F4-2, E-F4-3 | no | Opus; reviewer-adjacent |
| 4 | **F4-WO4** MaterialModel, scales, boundaries | `material/{model,scales,boundary}.py`; `solve-policy` schema keys | E-F4-4, -5, -6 | no | Opus |
| 5 | **F4-WO5** `cubic.pr-v1` and batching | `methods/cubic_pr.py`; `scripts/bench_batching.py` | E-F4-1 (iii), E-F4-7 | no | Opus |
| 6 | Close-out | manifest, catalogue, gate, CI | all E-F4 | no | Sonnet |

**Unblocks:** F5 (WO4), X17 (WO1–2), X11 rest (WO2), PrISMa's equilibrium part (with F5).

## Risks (each with a default)

1. **PR-C1's ideal-gas part may not be separable** (fact, WO3). Default: D4's refusal; `cubic.pr-v1` carries `ig`.
2. **Q2.A1's 4-ulp bound with many components** may fail where Σ|n_cΔ_c| ≫ |Ḣ| (fact). Default: fixed-order sum; a
   failure amends the bound per rulings rule 6, never the order.
3. **c_ref, ΔT_ref** (note R19; fact: F4/F6 measurements). Default 2.0e3, 100 K.
4. **CasADi callback overhead at N = 300** may hide the batching gain (fact, WO5). Default: one callback per method;
   if E-F4-7 fails, an architect question before WO6.

## Edits `target-architecture.md` needs

§2.3.2–3: narrowed `data_sha256` (D2), `describe_method()`; §2.3.6: Amendment 2–3 anchor text and D4's PR-C1 rule;
§2.3.7: constants in `SolvePolicy.scales`; §2.3.8: Amendment 2's (ii)–(iii) wording; §8: `PropertyCapabilities` row →
`MethodDescription`; §3 F4 exit: "Q2.A1–A8" → "Q2.A1–A9, A11", add Q3.A5 and E-F4-3.
