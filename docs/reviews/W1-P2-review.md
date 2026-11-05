# W1 P2 review: ADR 0062 (F2 material model), ADR 0063 (F4 property methods), ADR 0064 (F5 phase equilibrium)

Reviewer (design lane), 2026-11-05. Brief `docs/roadmap/brief-reviewer-W1-P2.md`. Reviewed the three ADRs at `147d6e96`
against `brief-architect-W1-P2.md`, ADR 0060, ADR 0061 (with the P1 review applied), `foundation-rulings.md` Q2, Q4, Q5,
§14 and §15, and the note §2.2. I built and ran nothing. I checked the factual premises against the code and data:
`thermo/pr_c1.py:166–195, 280, 308–320, 506–520, 711–761`; the constructors of the other legacy providers;
`thermo/__init__.py:58–80`; `thermo/cache.py:116–121, 193–203`; `adapters/experiments/request.py:41–44`;
`run/identity.py:59–160`; `run/solution_state.py`; `verify/certificate.py:326, 354`; the v1 schemas
(`process-revision`, `specification`, `solve-policy`, `units.json`); ADR 0060 D1 (id rule, line 85) and its namespace
rule (272–274). I counted with grep: 44 benchmark revision files carry `phase_capability` on connections.

**Verdict.** The identity architecture holds. No existing dataclass gains a field that `asdict` sees (I confirmed
`request.py:43`). The id grammar is injective over the stated alphabets. The narrowed `data_sha256` is a sound cache
identity. Every §14/§15 row's obligation is present (checklist at the end). Four defects must be fixed before
acceptance:
- the non-TP flash at a fixed phase set has no solution at π = C + 1, which is FB-04's wet-steam case;
- the dispatch rule sends FB-04 to the T05b code, which refuses it;
- the lowering proof is vacuous as worded, and the v2 grammar cannot carry two v1 connection fields the corpus uses;
- a delegating composition can evaluate packaged data while its identity names other records.

**ADR 0062: accept after the listed fixes. ADR 0063: accept after the listed fixes. ADR 0064: accept after the listed
fixes.** I give D1's replacement text below, so 0064 needs no second architect pass. One threshold in it, and S6, need a
design-lane decision; I give the defaults.

## Findings, ranked

### Must fix

**M1. ADR 0064 D1 and ADR 0063 D7: PH, PS and β specifications have no solution at a fixed phase set when π = C + 1.**
D1 solves every non-TP spec by "outer safeguarded Newton (bracketed) on T … over the TP solve". ADR 0063 D7 solves a
procedural PH point by "Newton on T at the frozen phase set". *Scenario:* FB-04's turbine outlet and its isentropic
reference are wet steam (C = 1, π = 2). At fixed P, a two-phase TP equilibrium of pure water exists only at T_sat(P).
Over the unrestricted TP flash, Ḣ(T) jumps from ṁĥ_L to ṁĥ_V at T_sat. The bracket collapses onto T_sat and the residual
never vanishes. At the frozen set {L, V}, no T ≠ T_sat has a solution, so the Newton on T is undefined. Legacy IAPWS-95
also refuses the metastable phase once |ln(P/P_sat)| > 1e-6 (`iapws95.py:781`), which is about 3e-5 K off saturation, so
iterates cannot even be evaluated. E-F5-6 cannot pass. Near π = C + 1 for C ≥ 2 (narrow-boiling, or VLLE at fixed P)
the same route is singular or badly conditioned. *Fix:* replace D1's fixed-set and non-TP text (edit 0064-1), and point
0063 D7 at it (edit 0063-2).

**M2. ADR 0064 D3 and D4: the dispatch rule routes FB-04 to code that refuses it, and E-F5-6 depends on F6.** Dispatch
sends "a solve whose every phase-selecting point is a two-candidate point of a split legacy or delegating method" to "the
existing T05b controller code unchanged". `composed.iapws95-v1` is delegating, `split`, with two candidates (Q4.R6). So
FB-04 is dispatched to T05b. The note's §2.2 says of T05b today: "FB-04 is refused whichever regime is declared". D4's
opening flash is never reached. Separately, E-F5-6 needs `std.turbine` and the `h_mass` coordinate, which only `std.*`
units admit (ADR 0062 D11). Those are F6, and the note's graph has F5 → F6, so F5's exit cannot hold E-F5-6. *Fix:*
edits 0064-2 and 0064-3.

**M3. ADR 0062 D8, D11, D12 and E-F2-3: the lowering proof proves nothing, and two v1 fields cannot be raised.** Two
defects:
- *The proof.* E-F2-3 says the corpus "raises and lowers to the same bytes' content_hash; the lowered runs' r0_sha256
  and state_sha256 equal the corpus values". If the lowered v1 document is what runs, the run *is* the corpus run, so
  nothing about the v2 route is tested. If the v2 document runs, D8 says "v2 runs write v2 … Either way the definition
  SHAs are recorded in `solution-state-v2` and enter R0 there", so its R0 differs. `r0_projection` today carries only
  `solution_state.variable_ids` (`run/identity.py`), and WO6 does not list `run/identity.py`.
- *The grammar.* v1 connections carry `phase_capability` and `notes`. Neither is in `CONTENT_HASH_EXCLUDED`, and 44
  benchmark revision files use `phase_capability`. D11's closed v2 connection object has neither. Raising those
  revisions loses identity-bearing content, so E-F2-3 fails on them.

Also unstated: how a v1 Specification target (`{object_type, object_id, path}`, `schemas/specification.schema.json`)
raises (see S5). And `property_methods.default` must agree with the provider that ADR 0050 D1 assigns to `record_source`.
*Fix:* edits 0062-1 to 0062-4.

**M4. ADR 0063 D2: a delegating composition can evaluate packaged data while its identity names other records.**
"A delegating composition builds the legacy provider from records through ADR 0061's legacy views and calls it
unchanged." Each legacy provider gets its data a different way:

| Provider | How it obtains its data |
| --- | --- |
| `PrC1Provider()` | No arguments. Process-global `@cache` reads of the packaged `m01` file (`pr_c1.py:177–195, 279–280`). |
| `Iapws95Provider` | No arguments. |
| `CoolPropHeosProvider(component_id)` | Built for one fluid. |
| Wilson v2 | Takes `records_path`. |

`legacy_views` builds `C1Records`, but no provider constructor accepts one. *Scenario:* a v2 revision binds N2 to a
user record with a corrected T_c. The lock, `L_m` and the cache key all carry the user's SHA. The composition evaluates
the packaged T_c. The verifier recomposes the same way and agrees. The result is wrong, its identity claims the user's
data, and no test fails. A CoolProp substream of two fluids has no build rule at all. *Fix:* edit 0063-1.

### Should fix

**S1. `thermo/cache.py` after ADR 0062 D2's widening.** `ExactPropertyCache` keys a state as `(*state.n, T, P)`
(`cache.py:116–121`) and puts `request.phase` raw into `document_sha256` (`:193–203`). Wrapping a composed provider would
make two `EvaluationState`s that differ only in attributes share one key, which returns a wrong value silently. A
`PhaseId` would not canonicalise. *Fix:* in D2, add "`thermo/cache.py` keys an `EvaluationState` by n, T, P **and**
`attributes`, and a `PhaseId` by its rendering (D6); a `StreamState` key is byte-unchanged (M6)". List the module in
F2-WO1.

**S2. ADR 0062 D3: the layout is not a function of the SHA preimage.** The SHA normalises groups by id and attributes by
(kind, components). The carried indices follow "definition order" and "attribute order". So two instances with one
`definition_sha256` can lay out differently. Also unstated: whether `h`/`P` follow each substream or come once per
connection, and the id of `nTP-v1`'s implicit substream, which a `MethodSet` (ADR 0063 D5) must key on. *Fix:* edit
0062-5.

**S3. ADR 0062 D6: an extension cannot register a phase family.** The family id must match `^[A-Z][A-Z0-9_]*$`.
ADR 0060 requires every entry-point id to start with `<namespace>.`, and the namespace is `^[a-z][a-z0-9_]*$`. The two
rules are disjoint. A dotted family would also break D6's ordinal parse. This is a core-grammar item of the freeze.
*Fix:* edit 0062-6.

**S4. ADR 0062 D6 narrows Q4.R7.** Q4.R7 renders `TWO_PHASE` for "a point of a `split` method with candidates {VAPOR,
LIQUID}". D6 says "two-candidate legacy points". A v2 γ–φ method (E-F5-4's Margules system) would then render
`VAPOR+LIQUID` against the ruling. The rulings are adopted verbatim. *Fix:* edit 0062-7.

**S5. ADR 0062 D7 and D10: v1's target form is dropped, and unit variables cannot be named.** D10 "widens" the target
"to one of" four forms that exclude v1's `{object_type, object_id, path}`. D7's closed field table has no field for a
unit-owned variable. The duty of an unconnected energy port "remains a unit variable" (D9) and so cannot be targeted.
*Fix:* edit 0062-8.

**S6. ADR 0063 D4: the entropy shift is undefined for most records (needs a decision).** Q2.R1 anchors s = s°_c. Q2.R4
gives a datum only when the record has *no* formation data. ADR 0061 risk 6 states that no legacy record has s°. So
`cubic.pr-v1` on the `m01` records (Δf h° present, s° absent) has no rule for the S shift, and PS specifications on it
are undefined. PR-C1 has no entropy at all (`pr_c1.py:761`). *Default I would take:* the S shift applies only to methods
providing `s`. A component without s° takes s = 0 in its anchor phase (Q2.R4's datum applied to s alone), with the
notice `entropy_datum(<c>)`. A reaction or equilibrium that reads its `s` or `g` is refused
`component_not_reaction_consistent(<c>)`. Route this to the specifier as a Q2 amendment; F4-WO3 proceeds on the default
(edit 0063-3).

**S7. ADR 0064 D1 and D2: the algorithm has gaps the build lane cannot fill.**
- *Slot removal.* "Drop a slot whose amount is ≤ 0" is unreachable when the unknowns are ln n.
- *Trivial collapse.* Two slots of one model can converge to one composition (FLUID, `LIQUID.2`), and nothing handles
  it.
- *`max_phases`.* "candidate count" is unbounded for an interchangeable family.
- *β = 0 specifications.* PBETA/TBETA at β = 0 need the incipient-phase form, because ln 0 is undefined.
- *Wilson K.* The K estimate needs T_c, P_c and ω. E-F5-4's Margules/synthetic-Antoine system has none.
- *Untested specifications.* No exit test covers TV, PBETA or TBETA.

*Fix:* edits 0064-1 and 0064-4.

**S8. ADR 0064 E-F5-2: the bitwise-float claim depends on seeds.** The generalised controller opens with D1's flash.
T05b uses the provider's TP flash and its admissibility decision (Q5.R5). Same signatures from different seeds give
converged floats that agree only to tolerance, so E-F5-2 would fail for a reason unrelated to the lattice. *Fix:* edit
0064-5. It is also Q5.R5's text: at two-candidate legacy points the legacy decision stays.

**S9. ADR 0063 D6: the scale constants are in the wrong place, and the text contradicts itself.**
`SolvePolicy.scales` holds "the registered physical nominals by quantity kind" (`solve-policy.schema.json:62–69`).
`enthalpy_capacity_ref` and `delta_T_ref` are not kinds. D6 also gives both a default and "required for v2-compiled
runs": if code fills a default, two code versions share one `policy_sha256`. *Fix:* edit 0063-4.

**S10. ADR 0063 D1 and ADR 0062 D1: kinds are missing for the vocabulary per basis, and F4-WO1 is marked for Sonnet.**
`kind_by_basis` for `cp` (kg, segment_mol), `v` (segment_mol) and `g` has no registered kind. `units.json` has
`molar_heat_capacity` but nothing for the per-kg or per-segment forms. A Sonnet work order must not choose these. *Fix:*
edit 0063-5.

**S11. ADR 0063 D2: no fill rule for the frozen `PropertyCapabilities`.** `phases: tuple[Phase, …]` with `Phase =
Literal["LIQUID", "VAPOR"]` (`thermo/__init__.py:58`) cannot state FLUID for `cubic.pr-v1`. `asdict` of this object is
an identity input (`request.py:43`). *Fix:* edit 0063-6.

**S12. ADR 0063 D3 and D5: the `MethodSet` grammar has no `sources` or `assign`, though D3 relies on both.** And
`source_conflict` (E-F4-6) cannot occur when 0.6 ships only the thermo method. *Fix:* edit 0063-7.

### Notes

- **N1. PR-C1's ideal-gas part is separable (fact).** `pr_c1.h_ig` (`pr_c1.py:315`) is what its h sums with the
  departure (`:520`). Risk 1 and D4's conditional stop are therefore resolved. On the `m01` records Δ_{PR-C1,c} is
  exactly 0.0, because h_ig(T_REF) = Δf h° by construction and `T_REF = 298.15` is T°'s double. So E-F4-3's first
  clause is exact for PR-C1, and only its vapour-root mutation has bite. That is still the A3-a control the ruling
  asks for. Edit 0063-8.
- **N2.** E-F4-5 must shift a non-reacting component. Otherwise Σ_r|ξ_r Δr h_r| moves legitimately and the test fails
  for the right reason. Edit 0063-9.
- **N3.** The ĥ step bound c_ref × ΔT_max crosses water's latent heat (≈ 2.26e6 J/kg) in ≥ 2.26e6/(2e3·ΔT_max) steps. A
  FB-04 iteration count can be expected; this is performance, not correctness.
- **N4.** ADR 0064 D7 adds a field to a frozen dataclass, which ADR 0062 rejects for `PropertyCapabilities`. I accept it
  because the certificate serialises through `as_document` (`verify/certificate.py:354`), and I found no
  `asdict`/`astuple` path. F5-WO4 should add an AST test that none appears.
- **N5.** ADR 0060 D3's import closure of a composed method will include `thermo/__init__.py` and `material/*`. An edit
  there moves every v2 method's `implementation_sha256`. This is by design, and D2 should say so.
- **N6.** For a `kg`-basis component, M = 1 in D4's ṁ sum (state it). F2-WO1's lifting of `amount_basis_unsupported`
  flips the `kg` branches of Q2.A10 (b) and E-F3-13, so add both to F2-WO1's acceptance. Q2.A11 (d) becomes runnable
  at F4.
- **N7.** E-F2-5: "no v2 id equals any legacy-form id **of any structure**" (it is true, since every v2 id has `~`).
  State the alphabet of `point` (the uid pattern). The CoolProp anchor calls a private `_jet` on a state that the
  adapter must build as the guard does (`coolprop_heos.py:475`); Amendment 3 covers this, so say so in the WO.

## Rulings

**Ruling 1: ADR 0063 D2's narrowing of ADR 0061 D10. Accepted.** It is sound as a cache identity. A composed provider's
values depend on these inputs, and each is in `L_m`, in `d`, or elsewhere in the key:

| What the values depend on | Where it enters the key |
| --- | --- |
| The substream's records: parameters, formation entries, bridge data, the anchor | `L_m` |
| Matched parameter sets | `L_m` |
| Method, version and options | `L_m` |
| Delegate data no record carries | `d` |
| Convention | separately in D7's key |

Nothing else in the full lock reaches the values. The δ of Q2.R8 and the `phase_order_keys` affect reports and labels,
not values. Soundness requires M4's admission rule: without it, `L_m` names records the delegate does not read.
Conditions:

(a) **Define `L_m` as a document.** In D2, after "this method's entry and options", add: "`L_m` is an
`openflowsheet-data-lock-v1` document holding the substream's `components` entries in revision order, every parameter
set with at least one key matched to them (ascending), this substream's `methods` entry and this method's
`method_options`."

(b) **ADR 0061 edits** (the orchestrator applies them):
- D10, replace "`data_lock_sha256` is every composed provider's `data_sha256` (F4), and so enters the exact cache keys
  and `describe()`;" with "each composed provider's `data_sha256` is its narrowed lock (ADR 0063 D2: `document_sha256`
  of this lock restricted to the provider's substream, with the delegated legacy provider's own `data_sha256` or
  `null`), and so enters the exact cache keys and `describe()`; `data_lock_sha256` of the whole lock is recorded per
  run;".
- Risk 8: replace the text after its title with "*Resolved* by ADR 0063 D2 (narrowed per substream and method; W1 P2
  review ruling 1)."

(c) Drop ADR 0063 D2's own edit sentence ("Edit for ADR 0061 D10: …"), which (b) supersedes.

**Ruling 2: the departures.**

| Departure | Ruling |
| --- | --- |
| 0062 D2: `PropertyCapabilities`, `FlashResult` and `FlashRequest` not widened | **Accepted.** The fact is confirmed (`request.py:43`). |
| 0062 D3: grids declared inside substreams | **Accepted.** This is Q6.R4's own wording. |
| 0062 D8: definition SHAs in the fingerprint only for v2-compiled runs | **Accepted**, conditional on M3. A lowered run is a v1 run in every artifact. |
| 0062 D6: Q4.R7 narrowed to "legacy points" | **Rejected.** Use Q4.R7's wording (S4). |
| 0063 D2: `data_sha256` narrowed | **Accepted** (ruling 1). |
| 0063 D6: constants in `SolvePolicy.scales` | **Fix required** (S9). |
| 0064 D3: dispatch to the T05b code | **Accepted for v1-path runs only** (M2). |
| 0064 D7: new optional certificate field | **Accepted** (N4). |

## Exact edits

**ADR 0062**

- **0062-1 (M3), D8.**
  - Replace "v2 runs write v2; legacy runs write `solution-state-v1` unchanged." with "v2-compiled runs write v2. Legacy
    runs and lowered runs (D12) write `solution-state-v1` unchanged. Every artifact of a lowered run is byte-identical
    to the v1 run of its lowered document, except the run manifest's revision reference (the v2 `revision_id` and
    `content_hash`)."
  - Replace "Either way the definition SHAs are recorded in `solution-state-v2` and enter R0 there." with "In a
    v2-compiled run the definition SHAs are recorded in `solution-state-v2`. They enter R0 through `run/identity.py`'s
    `r0_projection`, which is extended for `solution-state-v2` documents only (`material_layout`, `state_points`)."
- **0062-2 (M3), D11 `connections` row.** Make it `[{id, kind, from, to, definition, quantity_kind?, phase_assertion?,
  initialization_hint?, phase_capability?, notes?}]`, and add to Rules: "`phase_capability` (v1's enum) only on `nTP-v1`
  connections; it and `notes` enter `content_hash` as in v1."
- **0062-3 (M3), D12.** After "with `record_source` = that file and `component_mapping` the identity", add: "Lowering is
  a field map. A connection with `definition: nTP-v1` becomes `state_definition: nTP-v1`, `component_mapping:
  revision_component_set`. `phase_capability`, `initialization_hint` and `notes` are copied. Specifications in v1's
  target form are copied. `convention`, `materials` and `property_methods` are dropped, after checking that
  `property_methods.default` is the provider ADR 0050 D1 assigns to `record_source` (else `construct_unavailable(
  property_methods, F4)`). Raising inverts the map, with `convention` = that provider's native convention."
- **0062-4 (M3), E-F2-3 and WO6.**
  - In E-F2-3, replace "the lowered runs' `r0_sha256` and `state_sha256` equal the corpus values" with "each raised v2
    document, submitted as a run through Amendment 9, gives `r0_sha256` and `state_sha256` equal to the corpus run's,
    and a `solution-state.json` byte-identical to it".
  - In F2-WO6, add `run/identity.py` (`r0_projection` for v2 only).
- **0062-5 (S2), D3.**
  - Insert before "**Carried indices**": "Every order below is the normalised instance's, so equal `definition_sha256`
    means equal layout; (kind, components) is unique within a substream (`attribute_redundant`)."
  - Replace "Then the stream fields: `h` (or `T`) and `P`." with "After the last substream (instance order), the stream
    fields once per connection: `h` (or `T`), then `P`."
  - In the `nTP-v1` row, add "substream id `mixed`".
- **0062-6 (S3), D6.** After "Family id `^[A-Z][A-Z0-9_]*$`." add: "`phase_family` descriptors are built-in only. An
  extension spelling (ADR 0060's `<namespace>.` prefix cannot match this pattern) needs an amendment of this ADR."
  Delete ", then extension families by id".
- **0062-7 (S4), D6.** Replace "Two-candidate legacy points render" with "A point of a `split` method with candidates
  {VAPOR, LIQUID} renders".
- **0062-8 (S5).**
  - D10: replace "v1's fields with `target` widened to one of:" with "v1's fields, with `target` either v1's
    `{object_type, object_id, path}` (the only form for instances and `nTP-v1` connections) or one of:".
  - D7, after the field table, add: "Fields of unit-owned variables are added by ADR-F6 before the W1 freeze."
- **0062-9 (N6, N7).**
  - D4: "M = 1 for a `kg`-basis component".
  - F2-WO1 acceptance: "+ Q2.A10 (b) and E-F3-13 `kg` branches updated".
  - E-F2-5: "of the same structure" → "of any structure".
  - D7: "`point` := uid".

**ADR 0063**

- **0063-1 (M4), D2.** Replace "A delegating composition builds the legacy provider from records through ADR 0061's
  legacy views and calls it unchanged." with:

  > A delegating composition is admitted only when its delegate reads exactly the lock's data:
  > - `composed.pr-c1-v1` and `composed.wilson-ig-v2`: the substream's records (and parameter set) are one legacy file's
  >   indexed records in file order, so that `records.legacy_views.legacy_path_for` returns the delegate's packaged
  >   path (ADR 0061 D12).
  > - `composed.coolprop-heos-v1`: one `s07` record, the provider built with its legacy id.
  > - `composed.iapws95-v1`: one record with water's InChIKey, of which the method reads only identity and `formation`.
  >
  > Otherwise the composition is refused `records_not_delegable(<method>, <substream>)`. The adapter maps the
  > substream's components onto the delegate's component vector by id. The composition then calls the legacy provider
  > unchanged.

  Add `records_not_delegable` to the catalogue, and a refusal fixture (an edited `m01` N2 record) to E-F4-6.
- **0063-2 (M1), D7.** Replace "(PH: Newton on T at the frozen phase set, then the implicit-function derivatives
  `dT/dĥ = ṁ/∂Ḣ_T`, etc.)" with "(ADR 0064 D1's fixed-set augmented system, with derivatives by the implicit-function
  theorem on its converged Jacobian: `dT/dĥ = ṁ/∂Ḣ_T` at a one-phase point, 0 at π = C + 1)".
- **0063-3 (S6), D4.** Add step 5: "For a method providing `s`, Δˢ_{m,c} = s°_c − s^m_c(a; T°, P°). A record without
  s° in its anchor phase takes s = 0 there, with notice `entropy_datum(<c>)`, and any reaction or equilibrium reading
  `s` or `g` of c is refused `component_not_reaction_consistent(<c>)` (default pending a specifier ruling). A method
  without `s` (PR-C1, `pr_c1.py:761`) gets no S shift and provides no `s`, `s_ig` or `g`."
- **0063-4 (S9), D6.** Replace "optional `SolvePolicy.scales` keys `enthalpy_capacity_ref` (default 2.0e3 J/(kg K))
  and `delta_T_ref` (100 K), required for v2-compiled runs" with "`SolvePolicy.scales["specific_enthalpy"]` (a kind
  nominal, = c_ref·s_T) and a new optional object `SolvePolicy.energy_check: {capacity_ref, delta_T_ref}`, with
  registered values c_ref = 2.0e3 J/(kg K) and ΔT_ref = 100 K. Both are required by schema in a v2-compiled run's
  policy, and code supplies no default, so the values are always in `policy_sha256`". The ĥ step bound reads c_ref
  from `energy_check`.
- **0063-5 (S10), D1.** Add a kind row per (item, basis): `cp` → `molar_heat_capacity` / `segment_molar_heat_capacity` /
  `specific_heat_capacity`; `v` → `molar_volume` / `segment_molar_volume` / `specific_volume`; `g` → the `h` kinds. Add
  the three new kinds to ADR 0062 D1's table (additive, R2).
- **0063-6 (S11), D2.** After "`state_definition = "evaluation-state-v1"`", add: "`phases = ()` and `flashes = ("TP",)`
  (the phase models are in `describe_method()`), `properties` = the legacy names of the vocabulary items provided,
  `components` = the substream's, `reference_convention` = the flowsheet convention".
- **0063-7 (S12), D5.** Make `MethodSet = {<substream id>: {method, version, options, sources?: [<property_source
  id>…], assign?: {<item>: <source>}}}`. In E-F4-6, trigger `source_conflict` with a test-only source registration.
- **0063-8 (N1), D4.** Replace the PR-C1 clause from "the legacy module's ideal-gas function" to "native convention kept
  (Q2.R5)." with "`pr_c1.h_ig` (`pr_c1.py:315`), which its h sums with the departure (`pr_c1.py:520`); on the `m01`
  records Δ_{PR-C1,c} is exactly 0.0". Change risk 1 to "Resolved by fact (W1 P2 review N1)".
- **0063-9 (N2), E-F4-5.** "Δf h° of one component" → "Δf h° of one non-reacting component".

**ADR 0064**

- **0064-1 (M1, S7), D1.** Replace from "Non-TP specs: outer safeguarded Newton" to the end of D1 with:

  > **Equilibrium at a fixed set, every spec.**
  > - *Unknowns:* ln n_{p,i} for each active slot p and each component i of its support with z_i > 0, plus the spec's
  >   free variable: T for PH, PS and PBETA; P for TV and TBETA; none for TP.
  > - *Residuals:* ln f_{p,i} − ln f_{1,i} = 0 for p ≥ 2; the component balances; the spec scaled per ADR 0063 D6
  >   (Ḣ − ṁĥ, Ṡ − ṁŝ, V − ṁv̂, n_{p,tot} − β n_tot).
  > - *Iteration:* successive substitution (≤ 5 steps, TP only), then Newton. The line search is Gibbs descent for TP and
  >   the residual norm otherwise.
  > - *π = C + 1:* the system stays regular (the free variable is fixed by equilibrium, the spec fixes the amounts). For
  >   C = 1 it reduces to T = Tsat(P) (vocabulary `Tsat`), or P = Psat(T), and the lever rule. Both phases are then
  >   evaluated at saturation, inside the legacy guard.
  > - *β = 0:* the incipient phase takes the form of unknowns ln W_i, residuals ln W_i + ln φ_i(W) − d_i = 0, and
  >   Σ W_i = 1.
  > - *Removal and collapse:* a slot whose amount falls below τ_β·n_tot is dropped and the set re-solved; τ_β = 1e-12
  >   by default, fixed with O-2's measurement (**needs a decision**). Two slots of one model within τ_comp in
  >   composition (and, under FLUID, in ln v̂) are merged and recorded.
  > - *Slot limits:* at most C active slots for TP and C + 1 otherwise, C counting components with z_i > 0.
  >
  > **Unrestricted flash, non-TP specs:** a bracketed search on the free variable over the unrestricted TP flash
  > discovers the set. When the bracket collapses onto a set change across which the spec residual changes sign, the
  > set is the union of both sides, and the fixed-set solve above finishes the point. Derivatives to the outer problem
  > come from the implicit-function theorem on the converged augmented Jacobian. The ln-fugacity residual target is
  > ≤ 1e-10 (O-2).

  In D2, add: "Wilson K uses the records' T_c, P_c and ω; a method declaring composition-free K or `Psat` uses K =
  Psat/P instead; with neither, the two Wilson generators are skipped and recorded."
- **0064-2 (M2), D3.** Replace the **Dispatch** sentence with:

  > A run that compiles through the v1 path (a v1 document, or a v2 document lowered by ADR 0062 D12) runs the existing
  > T05b controller code unchanged under the new value. Every v2-compiled run takes the generalised controller
  > (`phase/contract.py`). At two-candidate points of a `split` legacy or delegating method, that controller keeps the
  > legacy admissibility decision and opens from the provider's own TP flash (Q5.R5).

  In the rejected alternative, read "for legacy two-candidate solves" as "for v1-path runs".
- **0064-3 (M2), E-F5-6 and F5-WO5.** Change E-F5-6 to "the FB-04 isentropic reference as a test-only PS state-point
  probe on `composed.iapws95-v1` (wet outlet, no declared phase): β and h within the registered tolerance of an
  independent IAPWS-95 evaluation". Move the full FB-04 turbine `VERIFIED` to ADR-F6's exit, and note it in the
  "Unblocks" line.
- **0064-4 (S7), exit tests.** Add **E-F5-10**: TV, PBETA(β = 0, bubble) and TBETA(β = 1, dew) on E-F5-4's Margules
  system against closed forms, plus a binary PH point at π = C + 1 (VLLE at fixed P), each within 1e-8 relative.
- **0064-5 (S8), E-F5-2.** Append: "with openings at two-candidate points taken from the provider's TP flash, as edit
  0064-2 requires".

## Rulings-adoption checklist (§14, §15)

| Rulings | Status |
| --- | --- |
| Q3.R5, Q3.A6 (F2: E-F2-7); Q3.A5 (F4: D5 (ii), E-F4-6) | present |
| Q2.R2, R4, R8, Q2.A9 (F4); Q2.R9, Q2.A11 (F4: D4, E-F4-2) | present |
| A3-a | present (E-F4-3, on two non-Helmholtz methods) |
| Q4.R1 rendering and qualifiers on every family (F2: D6, E-F2-5) | present |
| Q4.R2–R8, Q4.A1–A11, Q5.R1–R8, Q5.A1–A10 (F5) | present by adoption; Q4.R7 is S4; Q5.R5 is M2/S8 |
| F4 harness mapping VAPOR/LIQUID → FLUID (M2 (iii)) | present |
| A2-b, carried to F6 | present |
| A2-c (D6) | present: both representations, `confined_exclusive` capped at `local`, consistent with Amendment 2 |

## Not examined

- F0's corpus list. `wp/F0` is not on `main` and `scripts/corpus_identity.py` is absent, so I counted benchmark files
  with grep instead.
- Whether `units.json` bytes enter any identity. A grep found no hashing path; F0 decides.
- CasADi callback feasibility and E-F4-7's numbers.
- Q6, Q7 and Q8 assertion contents beyond their citation.
- The note's §2.1 and §2.3 in full.
- `target-architecture.md` edit lists, beyond checking that they match the decisions.
