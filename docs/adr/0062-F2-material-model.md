# ADR 0062 — F2: material model, connection definitions, phase and variable ids, `ProcessRevision` v2

**Status:** **Proposed, 2026-11-05.** Design wave W1, pass P2 (ADR 0057, R-928). Takes effect when Accepted after the W1
reviewer pass over ADRs 0062–0064; built in 0.5 on `wp/F2`. The core (D13) freezes at the end of W1 (R-929).
**Author:** design lane (`architect`). **Brief:** `docs/roadmap/brief-architect-W1-P2.md`.
**Refines:** `target-architecture.md` §2.1, §3 F2, §8. Departures are marked **[departure]** with their reason.
**Adopts verbatim** (foundation rulings; this ADR is their authority once Accepted): Q1.R1–R5, Q1.A5, A8; Q3.R1–R5, R7,
Q3.A1–A3, A6 (Amendment 2, A1-a); Q4.R1 and Q4.R8's rendering, Q4.A5 (Amendment 2, S5: the family vocabulary and
qualifiers on every family are core); Q6.R1–R5, Q6.A1–A5; Q7.R1–R5, Q7.A1, A2, A4, A5; Q8.R1–R6, Q8.A1, A2, A4, A6.
**Amends** (each additive; v1 documents, `nTP-v1` and every legacy digest unchanged):
- ADR 0001 D1.3 (kinds, D1), D2 and D3 for v2 documents (§10 items 1–2: D3.1's "T and P remain labels" reads "the
  thermal coordinate and P").
- `interfaces-frozen.md` §1 (D2: new types, two widened annotations) and §2 (schemas: `ProcessRevision` v2,
  `Specification` v2, `connection-definition`, `solution-state-v2`); ADR 0002 D7 (new versions, no instance migrated).
- ADR 0019 D1 as **Amendment 9**: revision operations accept `schema_version: 2` (D12); no new operation.
- ADR 0060 D1/D4: payload schemas of the kinds it assigns to ADR-F2 (D3, D9, D10); the static `flash` space table (D2).

---

## Context

Today: `StreamState(n, T, P)` (`thermo/__init__.py:105`), ids `<S>.n.<C>`, `<S>.T`, `<S>.P`, one `ComponentBasis`, five
phase Literals, every connection pinned to `nTP-v1`. P1 gives the registry (ADR 0060: kinds, descriptors, tokens,
`implementation_sha256`) and records by SHA with a derived data lock (ADR 0061). The 35 identity-bearing legacy modules
(F0 M9: 8 thermo providers, 27 unit modules) are never edited; `thermo/__init__.py`, `thermo/cache.py`,
`run/solution_state.py` are not among them.

**The fact that shapes D2.** `adapters/experiments/request.py:43` hashes `dataclasses.asdict(PropertyCapabilities)` into
`provider_identity_sha256`. Adding a field to an existing frozen dataclass, even with a default, therefore moves a
legacy identity. No existing dataclass gains a field in this ADR.

## Decisions

### D1. Quantity kinds (ADR 0001 D1.3; `schemas/units.json`)

Added kinds (dimension order L, M, T, Θ, N, I, J):

| Kind | SI unit | Dimension | Use |
| --- | --- | --- | --- |
| `specific_enthalpy` | `J/kg` | (2,0,−2,0,0,0,0) | `ĥ`; h of a `kg`-basis component (Q7.A4) |
| `specific_entropy` | `J/(kg K)` | (2,0,−2,−1,0,0,0) | `ŝ`; s of a `kg` component |
| `specific_volume` | `m3/kg` | (3,−1,0,0,0,0,0) | `v̂` (Q4.R3 FLUID key); TV specifications |
| `specific_heat_capacity` | `J/(kg K)` | (2,0,−2,−1,0,0,0) | `cp` of a `kg` component (ADR 0063 D1) |
| `molar_entropy` | `J/(mol K)` | (2,1,−2,−1,−1,0,0) | s°, s per mol (ADR 0061 risk 6) |
| `segment_molar_flow` | `mol/s` | (0,0,−1,0,1,0,0) | `segment_mol` amounts (Q7.R3) |
| `segment_molar_mass` | `kg/mol` | (0,1,0,0,−1,0,0) | M per segment type (Q7.R2) |
| `segment_molar_enthalpy` | `J/mol` | (2,1,−2,0,−1,0,0) | h, Δf h° per segment-mol (ADR 0061 risk 4) |
| `segment_molar_entropy` | `J/(mol K)` | (2,1,−2,−1,−1,0,0) | s, s° per segment-mol |
| `segment_molar_heat_capacity` | `J/(mol K)` | (2,1,−2,−1,−1,0,0) | `cp` per segment-mol (ADR 0063 D1) |
| `segment_molar_volume` | `m3/mol` | (3,0,0,0,−1,0,0) | `v` per segment-mol (ADR 0063 D1) |
| `enthalpy_flow` | `W` | (2,1,−3,0,0,0,0) | `Ḣ`; distinct from `heat_rate` and `power` |
| `mass_fraction` | `1` | 0 | w[c], the composition common to every basis (Q7.R3) |
| `number_flow` | `1/s` | (0,0,−1,0,0,0,0) | particle numbers, counts per class |

`power` exists (work, W). Kinds sharing a dimension are distinct (ADR 0001 D1.3's rule); nothing sums across kinds except
`ṁ` through M and a method's declared composition map (Q7.R3). **Unit spelling, one answer for F2 and MSG:** the
`si_unit` strings follow `units.json`'s existing form — ASCII, a space for a product, one `/`, parentheses around a
compound denominator, digit exponents (`J/(mol K)`, `J/(kg K)`, `m3/kg`). MSG renders the stored string; no `·`, `*`,
`^` or Unicode superscript is a registered spelling. `kg` and `segment_mol` records are admitted from F2-WO1 on (ADR
0061 risk 4 closes; `amount_basis_unsupported` stops firing for them).

### D2. Provider-level types (`openflowsheet/material/`, re-exported from `openflowsheet.thermo`)

```python
@dataclass(frozen=True, slots=True)
class EvaluationState:                       # one substream, the provider level
    n: tuple[float, ...]                     # parent amount per component of the provider's `components`, own basis
    temperature: float                       # K
    pressure: float                          # Pa
    attributes: tuple[tuple[str, tuple[float, ...]], ...] = ()   # (attribute key, values), sorted by key bytes
    @classmethod
    def from_stream_state(cls, s: StreamState) -> "EvaluationState": return cls(s.n, s.temperature, s.pressure)
    def to_stream_state(self) -> StreamState    # refuses (ValueError) if attributes is non-empty
```

`from_stream_state` copies the three references (no arithmetic), so the round trip is bitwise by construction; the
exit test proves it over the corpus. A partition attribute's parent (Q6.R2) is computed by the material model as the
fixed-order sum over classes (ascending class index) before `n` is formed; providers never see classes unless they
declare the attribute read (ADR-F4). Attribute key: `<kind id>` (substream scope) or `<kind id>[<component>]`.

`PhaseId(family: str, qualifier: str | None, ordinal: int)`, `PhaseSet = tuple[PhaseId, ...]` in canonical order (D6).
Widened annotations only (no runtime change; legacy providers never receive the new types, ADR-F4's adapters convert):
`PropertyRequest.state: StreamState | EvaluationState`; `PropertyRequest.phase: Phase | PhaseId`. **[departure]** from
the note §8: `PropertyCapabilities`, `FlashResult` and `FlashRequest` are **not** widened (the fact above). v2
capability fields live in ADR-F4's new `MethodDescription`; N-phase results in ADR-F5's `EquilibriumResult`; providers
are asked TP flashes and phase evaluations only, and every other specification is solved by ADR-F5's service. The static
`flash` token space (ADR 0060 D4) is `TP, PH, PS, TV, PBETA, TBETA`; only `TP` is a provider capability.
`thermo/cache.py` keys an `EvaluationState` by n, T, P **and** `attributes`, and a `PhaseId` by its rendering (D6); a
`StreamState` key is byte-unchanged (M6).

### D3. Connection definitions (F1 kind `connection_definition`; `schemas/connection-definition.schema.json`)

Two levels. A **template** is a registered descriptor; an **instance** is a canonical document in the revision whose
SHA is the connection's definition identity.

| Template (built-in, core) | Instance parameters | Variables per connection |
| --- | --- | --- |
| `nTP-v1` (exists, ADR 0060 D6) | none: one `mixed` substream over the revision's components, `true` basis; substream id `mixed` | legacy ids, unchanged |
| `mat-v1` | `thermal_coordinate`, `substreams` | D7 |
| `heat-v1` | none | `~Q`, kind `heat_rate` |
| `work-v1` | none | `~W`, kind `power` |
| `signal-v1` | `quantity_kind` (a registered kind) | `~s`, that kind |

A `mat-v1` instance (closed objects):

```
{ template: "mat-v1", thermal_coordinate: "h_mass" | "T",
  substreams: [ { id: <uid>, kind: "mixed" | "solid" | "nonconventional",
                  components: [<component id>…],          # a subsequence of component_set order, ≥ 1
                  conserved_basis: {preset: "true"}
                                 | {preset: "apparent" | null, species: [<component id>…],
                                    groups: [{id: <uid>, content: {<species id>: <int>}}…], fast_reactions: <reaction-set id> | null},
                  grids: [{id: <uid>, quantity_kind, edges: [float…]}],   # strictly increasing, ≥ 2 edges
                  attributes: [{kind: <attribute_kind id>, version, components: [<id>…] | null, grid: <grid id> | null}] } ] }
```

Rules (validation, typed): at most one `mixed` substream; substream ids unique, in the id alphabet; a component in at
most one substream except dissolved-plus-solid-substream (Q8.R2), a component confined to a phase model not in a
`solid` substream (`solid_role_conflict`); `nonconventional` holds only `kg`-basis components; a group basis has
integer content, A of full row rank (`species_basis_redundant`, Q3.R7), and is checked against `fast_reactions` by
Q3.R1 (i)–(iii) in exact rational arithmetic (`material/basis.py`, `fractions.Fraction`); M_g per Q3.R7 is computed
at validation and recorded in the layout. **[departure]** grids are declared inside their substream (Q6.R4: "declared
once per substream in the definition"), not in a revision-level `grids` list as the note sketches; a grid enters the SHA
by value. `phase_order_keys` stay revision-level (D11).

**Identity.** `definition_sha256 = document_sha256({"template": [id, version, descriptor_sha256], "body": instance})`
with the instance normalised (key order canonical, component lists as given, groups by id, attributes by (kind,
components)). The revision-local id is not in the preimage, so equal definitions in two revisions share a SHA.
`nTP-v1`'s SHA is that of `{"template": ["nTP-v1", "1.0.0", <descriptor_sha256>], "body": {}}`.

Every order below is the normalised instance's, so equal `definition_sha256` means equal layout; (kind, components) is
unique within a substream (`attribute_redundant`).

**Carried indices** of a substream, in this order: for each component in definition order, its parent amount, or, if a
partition attribute targets it, its classes (ascending) instead (Q6.R2); for a group basis the groups replace the
species. Non-partition attributes follow, in attribute order, component order, class order. After the last substream
(instance order), the stream fields once per connection: `h` (or `T`), then `P`. For `nTP-v1` this is today's order
(flows, T, P).

### D4. Dormancy, labels, attributes

Adopted rules (Q1.R4, Q6.R3, Q8.R6) as executable predicates in `material/state.py`: a substream is dormant iff every
carried amount `== 0.0` (signed zeros normalised first, ADR 0001 D1.5); a stream iff all its substreams are. Dormant ⇒
`Ḣ`, `ṁ`, attributes exactly `+0.0`; derived intensives `None` with reason `zero_flow`; `ĥ` is a label (never a property
input; the zero-flow row forms are ADR-F6's). A non-zero attribute on a dormant parent is an invalid state
(`attribute_on_zero_parent(<S>, <kind>)`). `ṁ = Σ M n` in carried-index order with M_g for groups (Q3.R7) and M = 1 for
a `kg`-basis component, one rounding per term, no fma. Admissibility inequalities (Q6.R5) are attribute-kind payload,
checked with τ_mono = 1e-12.

### D5. Attribute, derived-quantity, kinetics and section kinds (payload schemas; F1 kinds)

- `attribute_kind` (core): `{scope: component | substream, partition: bool, classed: bool, quantity_kind,
  parent_kind: <kind> | null, inequalities: [{lhs: [[coef, term]…], rhs: [[coef, term]…], allowance: "tau_mono"}]}`;
  F1 refuses a kind whose index set holds a definitional identity (`attribute_redundant`). Built-ins: none in 0.5; the
  three probes are test-only registrations (`probe.moments`, `probe.classes`, `probe.partition`).
- `derived_quantity` (core except `expression`): `{inputs: [{role, endpoint_kind}], auxiliary_points: [{name, spec:
  [[name, kind], [name, kind]], candidates: "method" | [rendering…]}], output: {vocabulary_item | "builtin"},
  quantity_kind, degeneracy: <registered condition id> | null, expression}`. `expression` is **preview**: in 0.5–0.6
  only `"builtin"` is admitted (T, β, `s_mass`, `h_molar`, x[c], w[c], ρ, bubble and dew T and P, implemented by
  ADR-F4/F5).
- `kinetics_kind` (core envelope; rate expression **preview**): `{writes: "source_terms", indices: "any_carried"}`.
- `revision_section` (core mechanism): `{schema: <JSON Schema $id>, reason: string}`; a section body validates against
  it; sections enter `content_hash`.

### D6. Phase ids (Q4.R1, R8; core grammar)

Families are F1 `phase_family` descriptors; the built-ins are `VAPOR`, `LIQUID`, `FLUID`, `SOLID` (core). Family id
`^[A-Z][A-Z0-9_]*$`. `phase_family` descriptors are built-in only. An extension spelling (ADR 0060's `<namespace>.`
prefix cannot match this pattern) needs an amendment of this ADR. Qualifier grammar, rendered inside `( )`:

```
qual := cid | cid "," form | "model=" mid        # cid: component id; form: ^[A-Za-z0-9][A-Za-z0-9_-]*$; mid: F1 id
render(f, q, k) = f ( "(" q ")" if q ) ( "." k if k ≥ 2 )
```

`,` and `=` are outside the component alphabet, so a component, a component form and a model id never render alike even
when a component id equals a model id (Q4.A5). Parse (test-only): family = longest `[A-Z0-9_]*` prefix; a `(` opens the
qualifier, closed by the first `)` (neither parenthesis is in any alphabet); a final `.k` needs k ≥ 2 without leading
zero, so `LIQUID.1` does not parse. Examples: `VAPOR`, `LIQUID.2`, `FLUID(water)`, `LIQUID(water).2`,
`SOLID(CaCO3,calcite)`, `SOLID(model=langmuir-co2)`. **Phase-set rendering** (signatures): canonical order — family by
(registration order VAPOR, LIQUID, FLUID, SOLID), qualifier (none first, then UTF-8 bytes), ordinal — joined by `+`
(outside both alphabets). A point of a `split` method with candidates {VAPOR, LIQUID} renders `LIQUID`, `VAPOR`,
`TWO_PHASE` as today; `ZERO_FLOW` stays a stream property (Q4.R7). Ordering *within* a family (Q4.R3) is ADR-F5's.

### D7. Variable ids (S6; core)

The note's grammar, made exact: `vid := owner ("@" sub)? ("#" point ("#" phase)?)? "~" field ("[" index "]")*`, `owner
:= uid ("/" uid)*`, `point := uid`. **Field table** (closed, core; additions by ADR amendment): connection fields `n`
(carried amount; indices `[component]` or `[component][class]` or `[group]`), `a` (non-partition attribute;
`[kind][component]?[class]?`), `h`, `T`, `P`, `Q`, `W`, `s`; state-point fields `n`, `T`, `h`, `P`, `beta`, `v` (ADR-F5,
F6). Fields of unit-owned variables are added by ADR-F6 before the W1 freeze. Class indices are 1-based decimals.
Production code renders only (`material/vid.py`); ids stay opaque (R-019). `tests/f2/vid_parse.py` is the left inverse
that proves injectivity. Every v2 id contains `~`; `nTP-v1` connections keep today's ids exactly; `ProblemSpec` still
refuses duplicates (`compile/spec.py:174`).

### D8. Material layout and `solution-state-v2`

`MaterialLayout` (built at validation, immutable): per connection `{connection, definition, definition_sha256, slots:
[{substream, field, index: [..], quantity_kind, variable_index}]}` in D3's order, plus per substream M (or M_g) and the
dormancy partition. `layout.state(x, connection) -> MaterialState` reads by index, never by parsing an id.
`solution-state-v2` = v1's fields (`state_sha256`, `variable_ids`, `variables`) plus `material_layout` (the slots
without `variable_index`, which `variable_ids` order gives) and `state_points: [{point, signature}]` (renderings).
v2-compiled runs write v2. Legacy runs and lowered runs (D12) write `solution-state-v1` unchanged. Every artifact of a
lowered run is byte-identical to the v1 run of its lowered document, except the run manifest's revision reference (the
v2 `revision_id` and `content_hash`). `material_layout` and signatures are R0; floats stay out of R0 as today.

**Fingerprint [departure].** A v2 revision in the v1-expressible subset (D12) is lowered to a v1 document and compiled
by the untouched v1 path; its compiled problem, and so its `model_version`, is the v1 one, and that is correct because
the problem is identical. The definition SHAs join the numerical-model fingerprint only where a v2 compiler builds the
problem (ADR-F6): the note's "for v2 runs only" is narrowed to "for v2-compiled runs". In a v2-compiled run the
definition SHAs are recorded in `solution-state-v2`. They enter R0 through `run/identity.py`'s `r0_projection`, which is
extended for `solution-state-v2` documents only (`material_layout`, `state_points`).

### D9. Energy and signal connections; endpoints (note §2.1 items 9–10, adopted)

Value = energy flow from `from` to `to`; an inlet energy port reads energy into the unit (ADR 0001 D4.1), an outlet
port energy out; an unconnected energy port leaves the duty a unit variable. A signal carries one SI value of its
`quantity_kind`; both endpoints must have that kind (`signal_kind_mismatch(<connection>)`). Endpoints: `{instance,
port}` (any kind); `{probe: <target>}` (signal source only; target as D10); `{instance, parameter}` (signal sink only,
the manifest must declare it `manipulable`, else `parameter_not_manipulable`; bound by a signal and a time input:
`parameter_binding_conflict`); `{specification: <id>}` (signal sink only, ADR 0065 D10: that specification's row reads
the signal's `~s` in place of its pinned value; bound also by a time input: `parameter_binding_conflict`). Energy and
signal connections, probes and parameter sinks are validated and laid out in
0.5 and refused at binding with `construct_unavailable(<construct>, F6)` until ADR-F6's units read them.

### D10. `Specification` v2 (`schemas/specification-v2.schema.json`)

v1's fields, with `target` either v1's `{object_type, object_id, path}` (the only form for instances and `nTP-v1`
connections) or one of: `{variable: <vid>}`; `{derived: <derived_quantity id>, version, stream: <connection id>,
component?: id, phase?: <rendering>}`; `{energy: <connection id>}`; `{signal: <connection id>}`. `kind` must equal the
target's quantity kind. A derived target before ADR-F4/F5 builds it is refused `construct_unavailable(derived:<id>,
F4)`; `specification_degenerate(<spec>)` is ADR-F4's opening check. A `{derived: X, stream: S}` target on an `h_mass`
connection compiles by the F6 sheet's C3 (`docs/derivations/F6-std-seed.md`: the X-form row ṁ_S ĥ_S − Ḣ^XP(n_S,
X_spec, P_S) = 0 through an XP point at S's amounts).

### D11. `ProcessRevision` v2 (`schemas/process-revision-v2.schema.json`)

| Field | Content | Freeze |
| --- | --- | --- |
| `schema_version` | const 2 | core |
| `revision_id`, `parent_revision`, `content_hash`, `title`, `description`, `provenance` | as v1 | core |
| `convention` | `ELEMENTAL-ref-v1` or a native convention id from `interfaces-frozen.md` §3 (ADR-F4 extends) | core |
| `component_set` | `{components: [{id, record}], parameter_sets: [sha]}`, `record` a record SHA (ADR 0061) | core |
| `materials` | `{thermal_coordinate, definitions: [{id, …D3 instance}], phase_order_keys?: [component id…]}` | core |
| `reaction_sets` | `[{id, reactions: [{id, stoichiometry: {<component>: [p, q]}, scope: [<substream id>…]}], kinetics?: {kind, version, …}}]` | core; kinetics body preview |
| `property_methods` | `{default: MethodSet, overrides: [{instance, side?, method_set}]}` (ADR-F4) | preview |
| `instances` | `[{id, model, semantic_role, parameters, references?, template?, policy}]` | core; `template` preview |
| `connections` | `[{id, kind, from, to, definition, quantity_kind?, phase_assertion?, initialization_hint?, phase_capability?, notes?}]` | core; `phase_assertion` preview |
| `specifications` | `[Specification v2]` | core |
| `sections` | `{<namespace>: {schema, body}}` | core mechanism |

Rules: ids in `^[A-Za-z0-9][A-Za-z0-9_.:-]*$` (the v1 pattern; assumption A6 holds by schema). Stoichiometry: `[p, q]`
integers, q > 0, gcd 1, p ≠ 0 (a zero coefficient is omitted; canonical); every stoichiometric component lies in a scope
substream. `semantic_role` is a registered id (the v1 enum plus `utility`, `controller`, `shaft`, `relief_device`;
ADR-F6 owns the vocabulary). A material connection's `definition` names a `materials.definitions` id or `nTP-v1`; an
energy one `heat-v1` or `work-v1`; a signal one `signal-v1` with `quantity_kind`. `phase_capability` (v1's enum) only on
`nTP-v1` connections; it and `notes` enter `content_hash` as in v1. No `component_mapping`, no `record_source`.
`content_hash` = v1's rule (`CONTENT_HASH_EXCLUDED` unchanged in name and members), applied to the v2 document.
**Thermal coordinate** (note item 11): every material definition has the revision's coordinate
(`thermal_coordinate_mismatch(<definition>)`); `h_mass` admits `std.*` units only
(`unit_coordinate_unsupported(<instance>, h_mass)`); `T` admits `nTP-v1`, legacy and `std.*` units. **Port
compatibility** (note item 12): one definition per connection, accepted by both endpoints
(`definition_incompatible(<connection>, <instance>.<port>)`); generic transport units take one definition on all
material ports unless the manifest declares subset fill (identical grids and bases, missing parts exact `+0.0`) or a
declared map. Grids differ: `attribute_grid_mismatch`. **In 0.5** `property_methods.default` admits one legacy provider
id and no overrides (v1's selection in v2).

### D12. Reading, lowering and operations (ADR 0019 Amendment 9)

`parse_revision` dispatches on `schema_version`: 1 → the untouched v1 reader; 2 → `revision_v2.parse` (ADR 0002 D7.5:
never read as the other). **Lowering** (`revision_v2/lower.py`): a v2 document is *v1-expressible* iff its convention is
the legacy provider's native one, every material connection is `nTP-v1`, it has no energy or signal connection, reaction
set, section, probe or parameter endpoint, and every component record carries `legacy.{profile, file}` from one file
whose component list equals `component_set` in order (ADR 0061 D12). It lowers to the v1 document with `record_source` =
that file and `component_mapping` the identity; anything else is refused `construct_unavailable(<construct>,
<foundation>)`. Lowering is a field map. A connection with `definition: nTP-v1` becomes `state_definition: nTP-v1`,
`component_mapping: revision_component_set`. `phase_capability`, `initialization_hint` and `notes` are copied.
Specifications in v1's target form are copied. `convention`, `materials` and `property_methods` are dropped, after
checking that `property_methods.default` is the provider ADR 0050 D1 assigns to `record_source` (else
`construct_unavailable(property_methods, F4)`). **Raising** (`revision_v2/raise_v1.py`, test and tooling only) inverts
the map, with `convention` = that provider's native convention. Amendment 9: `commit_change`, `preview_change`,
`diff_revisions`, `validate_revision`, `check_admission` (ADR 0060 D11's revision form) and run submission accept v2
documents; `ChangeSet` paths address v2 fields unchanged; results gain no field. `check_admission` adds F2's checks
(thermal coordinate, port compatibility, solid roles, grids, basis validity, signal kinds) to
`AdmissionReport.notices`/refusals.

### D13. Core at the end of W1, and preview

**Core (frozen):** D1's kinds and spelling rule; D2's types and annotations; the template set, `mat-v1`'s grammar,
normalisation and SHA, carried-index order (D3); D4's predicates; D5's payload envelopes; D6's grammar, family
vocabulary and set rendering; D7's grammar and field table; D8's layout and `solution-state-v2`; D9's endpoint kinds and
codes; D10; D11's core fields and rules; D12's dispatch and lowering criterion. **Preview (to the end of 0.6, R-929):**
`property_methods`, `phase_assertion`, `template`, kinetics bodies, the derived-quantity `expression`, the content of any
section namespace.

## Alternatives rejected

- *Fields added to `PropertyCapabilities`/`FlashResult` with defaults* (the note's §8 rows): moves
  `provider_identity_sha256` for every legacy provider (`asdict`), and needs every serializer audited forever.
- *Definitions only as registered descriptors* (no instances): every new component list would be an extension.
- *Definitions only inline* (no templates): `nTP-v1` and `heat-v1` would have no shared identity across revisions.
- *Qualifier spelled `SOLID.NaCl`* (Q8's informal text): collides with ordinals and `.` in component ids (Q4.A5).
- *A revision-level grid library*: a grid is a property of the substream it classifies (Q6.R4); one place to look.
- *Joining `nTP-v1`'s SHA to the fingerprint of lowered runs*: distinguishes identical compiled problems.
- *A v2 binder for legacy units in 0.5*: duplicates the v1 binder; lowering reuses it bitwise.

## Migration proof

F0 PASS on every work order (M1–M9; no frozen module edited; no existing dataclass gains a field). v1 documents are read
by the untouched v1 reader. `StreamState ↔ EvaluationState` bitwise over every corpus stream (E-F2-1). Raising then
lowering every corpus revision returns its v1 document with the same `content_hash`, and each raised v2 document, run
through Amendment 9, reproduces the corpus run's `r0_sha256`, `state_sha256` and `solution-state.json` bytes (E-F2-3).
M6's recorded cache-key digests unchanged.

## Exit tests (F0 PASS implied on each)

- **E-F2-1** Q1.A8: over every stream of every corpus run, `EvaluationState.from_stream_state(s).to_stream_state()`
  equals `s` bitwise (each float by `struct.pack('<d')`), and `n` is the same tuple object contents.
- **E-F2-2** Round trips: fixtures with all three connection kinds, all three endpoint kinds, a `mat-v1` with `mixed`
  and `solid` substreams, a group basis, a classed attribute on a grid, a reaction set and a section: parse → canonical
  → parse is a fixed point; `content_hash` stable under key reordering; changing any core field moves it.
- **E-F2-3** Lowering: every corpus v1 revision raises and lowers to the same bytes' `content_hash`; each raised v2
  document, submitted as a run through Amendment 9, gives `r0_sha256` and `state_sha256` equal to the corpus run's, and
  a `solution-state.json` byte-identical to it. A v2 document with any non-expressible construct is refused with the
  catalogued `construct_unavailable` naming it.
- **E-F2-4** Q1.A5 and Q6.A1–A5 on the probe flowsheets (test-only numeric probes: mixer ≤ 8 inlets, splitter, heater in
  `(n, ĥ, P)`, division-free rows solved for the outlet; no property call): relative conservation ≤ 1e-14 per carried
  amount and attribute; dormant streams exact `+0.0`, `ĥ` bitwise its label; the 5e-324 stream flowing. O-9: report
  the worst moment deficit; amend τ_mono if the margin is below 10×.
- **E-F2-5** Ids **[gen]**: 10⁴ random structures with adversarial user ids (`a.2`, `n`, `LIQUID`, `x:y`, digits,
  `model`, a component id equal to a model id), qualifiers on every family (Q4.A5): render then parse returns the
  structure; no v2 id equals any legacy-form id of any structure; no two structures render alike.
- **E-F2-6** Layout: for every probe and fixture state, `layout.state(x, c)` equals the state built independently from
  the definition; the code path contains no id parsing (a test asserts `vid_parse` is not importable from `src/`).
- **E-F2-7** Q3.A1–A3, A6 **[gen]** in exact arithmetic (all five A6 cases and the former-rule control), M_g per case.
- **E-F2-8** Q7.A1, A2, A4, A5; Q8.A1, A2 (definition-level part: no SOLID candidate generated for a solid-substream
  component), A4 (T selection rule with a stub model), A6.
- **E-F2-9** Typed refusals: one fixture per code in the table below; each refused with exactly that code and params.
- **E-F2-10** `solution-state-v2` round-trip and schema; legacy runs still write `solution-state-v1` bytes identical to
  the corpus (M4 covers it).

## New catalogue codes (ADR 0058 C3)

`solid_role_conflict`, `species_basis_redundant`, `species_basis_incompatible`, `species_basis_not_monotone`,
`group_amount_negative`, `molar_mass_inconsistent`, `feed_not_electroneutral`, `attribute_redundant`,
`attribute_grid_mismatch`, `attribute_on_zero_parent`, `amount_basis_mismatch`, `thermal_coordinate_mismatch`,
`unit_coordinate_unsupported`, `definition_incompatible`, `signal_kind_mismatch`, `parameter_not_manipulable`,
`parameter_binding_conflict`, `state_degenerate_in_definition`, `construct_unavailable`, `quantity_kind_mismatch`.

## Work orders (`wp/F2`; after F1-WO2 and F3-WO1 are on `main`; at most two engineers at a time)

| # | WO | Content and files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **F2-WO1** Kinds and types | `schemas/units.json` (D1); `src/openflowsheet/material/{__init__,state,phase_id}.py`; annotations in `thermo/__init__.py`; `thermo/cache.py` (D2 keys); ADR 0061 `kg`/`segment_mol` gate lifted | E-F2-1; phase-id part of E-F2-5; Q2.A10 (b) and E-F3-13 `kg` branches updated | no | Opus (state), Sonnet (`phase_id.py` from D6) |
| 2 | **F2-WO2** Definitions and bases | `schemas/connection-definition.schema.json`; `material/{definitions,basis}.py`; payload schemas for `attribute_kind`, `derived_quantity`, `kinetics_kind`, `phase_family`, `revision_section`; built-in templates and families in `registry/builtin/` via `scripts/registry_builtin.py` | E-F2-7; template SHAs pinned | no | Opus |
| 3 | **F2-WO3** Ids and layout | `material/{vid,layout}.py`; `tests/f2/vid_parse.py` | E-F2-5, E-F2-6 | no | Opus |
| 4 | **F2-WO4** Revision v2 | `schemas/{process-revision-v2,specification-v2}.schema.json`; `src/openflowsheet/revision_v2/{parse,validate,canonical}.py`; fixtures under `tests/fixtures/schemas/v2/` | E-F2-2, E-F2-8, E-F2-9 | no | Opus (validate), Sonnet (fixtures) |
| 5 | **F2-WO5** Probes | `tests/f2/probes.py`, test-only attribute kinds | E-F2-4 | no | Opus |
| 6 | **F2-WO6** Lowering, state, operations | `revision_v2/{lower,raise_v1}.py`; `run/solution_state.py` (v2 writer beside v1); `run/identity.py` (`r0_projection` for v2 only); dispatch in the application layer; ADR 0019 Amendment 9 pointer; `interfaces-frozen.md` | E-F2-3, E-F2-10 | no | Opus |
| 7 | Close-out | evidence manifest, catalogue entries, full gate, CI both legs | all E-F2 | no | Sonnet |

**Unblocks.** WO1: F4's adapters (types), X11 rest (`kg`, `segment_mol` records). WO2+WO3: F4's `MaterialModel` and
F5's signatures. WO4+WO6: v2 documents in 0.5 on legacy providers; F6's binder. X09, X08, X17, PrISMa wait on F4–F6.

## Risks and open questions (each with a default)

1. **E-F2-3 depends on every corpus record carrying `legacy.file`** (fact: F3-WO3's index). *Default:* the lowering
   criterion as written; a corpus revision that cannot raise is listed and excluded from E-F2-3 only with a reviewer
   ruling, never silently.
2. **Kinds for attribute moments of real polymers and PSDs** (X19, X20) are not chosen (`number_flow` is the probes'
   only). *Needs:* fact (their design passes). *Default:* each package adds its kinds by an additive amendment (R2).
3. **The `,` and `model=` qualifier spellings** are a taste call inside Q4.R1's constraint. *Needs:* Frank's preference
   only if he dislikes them. *Default:* as D6; changing them after W1 is a grammar change.
4. **Lowered runs keep v1 fingerprints** (D8). *Resolved:* accepted by the W1 P2 review (ruling 2), conditional on M3,
   which is applied (D8, D12, E-F2-3).

## Edits `target-architecture.md` needs (the orchestrator applies them)

1. §2.1.1: templates and instances (D3); grids inside substreams; `conserved_basis` grammar of D3.
2. §2.1.6: qualifier grammar `cid | cid,form | model=mid` and the `+` set rendering (D6).
3. §2.1.7: the closed field table of D7.
4. §2.1.8: "For v2 runs only" → "for v2-compiled runs (ADR 0062 D8)"; lowered runs keep v1 fingerprints.
5. §2.1.14: `component_set.components[].record`; signal `quantity_kind` on the connection; lowering in 0.5 (D12).
6. §8: `PropertyCapabilities`, `FlashResult`, `FlashRequest` rows → "unchanged; new `MethodDescription` (ADR-F4) and
   `EquilibriumResult` (ADR-F5)"; kinds row adds `specific_volume`, `molar_entropy`, `segment_molar_enthalpy`,
   `segment_molar_entropy`, `enthalpy_flow`, `mass_fraction`, `number_flow`, `specific_heat_capacity`,
   `segment_molar_heat_capacity`, `segment_molar_volume`.
7. §3 F2 exit: "Also Q3.A1–A3" → "Also Q3.A1–A3, A6" (Amendment 2) and add the lowering identity (E-F2-3).

## Review applied (W1 P2 review, `docs/reviews/W1-P2-review.md`, 2026-11-05)

Status stays Proposed.

| Finding | Edit |
| --- | --- |
| M3 (0062-1) | D8: lowered runs write v1 artifacts byte-identical but for the revision reference; R0 via `r0_projection` (v2 only). |
| M3 (0062-2) | D11: `phase_capability?` and `notes?` on connections; rule: `nTP-v1` only, in `content_hash` as in v1. |
| M3 (0062-3) | D12: lowering as a field map, `property_methods.default` checked against ADR 0050 D1; raising inverts it. |
| M3 (0062-4) | E-F2-3 runs each raised v2 document; migration proof restated; F2-WO6 lists `run/identity.py`; risk 4 resolved. |
| S1 | D2: `thermo/cache.py` keys `attributes` and `PhaseId` renderings; `StreamState` keys unchanged; listed in F2-WO1. |
| S2 (0062-5) | D3: layout order from the normalised instance; stream fields once per connection; `nTP-v1` substream id `mixed`. |
| S3 (0062-6) | D6: `phase_family` built-in only; "then extension families by id" deleted. |
| S4 (0062-7) | D6: Q4.R7's wording restored verbatim. |
| S5 (0062-8) | D10: v1's target form kept; D7: unit-owned fields added by ADR-F6 before the W1 freeze. |
| S10 (0063-5) | D1: `specific_heat_capacity`, `segment_molar_heat_capacity`, `segment_molar_volume` added; edit list item 6. |
| N6, N7 (0062-9) | D4: M = 1 for `kg`; F2-WO1 acceptance; E-F2-5 "of any structure"; D7 `point := uid`. |
| Ruling 2 | D6's Q4.R7 narrowing removed (S4); D2, D3 and D8 departures accepted unchanged. |

Not applied: none of the edits for this ADR.

## W1 P3 review applied (`docs/reviews/W1-P3-review.md`, 2026-11-06)

Status stays Proposed. Cross-ADR edits from the W1 P3 review's consolidated list (the F6 sheet, M3).

| Finding | Edit |
| --- | --- |
| M3 | D9: endpoint `{specification: <id>}` (signal sink only), by ADR 0065 D10. |
| B-7 | D10: a `{derived: X, stream: S}` target on an `h_mass` connection compiles by the F6 sheet's C3. |

Not applied: none of the edits for this ADR.
