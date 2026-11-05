# ADR 0065 — F6: unit-model framework v2 (`UnitModel` v2, `ModelManifest` v2, `std.*`, expressions, legacy retirement)

**Status:** **Proposed, 2026-11-05.** Design wave W1, pass P3 (ADR 0057, R-928). Takes effect when Accepted after the W1
P3 reviewer pass over ADRs 0065–0067; built in 0.6 on `wp/F6`. The core (D19) freezes at the end of W1; the template,
method-set and phase-assertion slots and the expression *uses* stay `preview` to the end of 0.6 (R-929).
**Author:** design lane (`architect`). **Brief:** `docs/roadmap/brief-architect-W1-P3.md`.
**Refines:** `target-architecture.md` §2.4, §3 F6, §8 (`ModelManifest`, `UnitModel` rows). Departures are marked
**[departure]** with their reason. **Note edits:** `docs/roadmap/W1-P3-note-edits.md`.
**Adopts verbatim** (foundation rulings; this ADR is their authority once Accepted): Q1.R4's zero-flow form and label
value for unit rows (F2 adopted the predicates), Q1.R6 and Q1.A9; Q5.R7's no-read rule and Q5.A8; Q1.R8's zero-holdup
*form grammar* (its mechanics are ADR 0066's); finding A2-b (decided in D9).
**Amends** (each additive; every v1 document, legacy digest and identity-bearing module unchanged):
- ADR 0060: D1 (payloads of `unit_model` v2, `semantic_role`, `equipment_class`, discrete coordinates `zero_flow_form`,
  `phase_routing`, `controller_regime`); D12 (per-side `requires` and admission, D5).
- ADR 0062 D7 (unit-owned variable fields and the v2 parameter-id fields, D4); D8 (the v2-compiled fingerprint, D3);
  D9 (energy and signal constructs are read; `construct_unavailable(<construct>, F6)` retires, D10).
- ADR 0002 D2.7: `compiled-problem-structure-v2` for v2-compiled problems only (D3); migration report: no instance
  migrated, no stored digest changes.
- ADR 0012 D4(c)/D12: generalised to v2 units as the `zero_flow_form` discrete coordinate (D7); v1 untouched.
- ADR 0050 D3: a new family is written against `MaterialModel` only (D16); legacy families keep D3.
- ADR 0054: `semantic_role` becomes a registered vocabulary (D15); the v1 schema enum is unchanged.
- ADR 0019 D1 as **Amendment 10**: `check_admission` gains a per-side form; `list_capabilities` returns v2 unit port and
  parameter schemas from the manifest (D5, D2). No new operation.

---

## Context

Today a unit is `UnitModel` (`models/__init__.py:369`: `ports`, `declared_equations`, `manifest`, `contribute(wiring,
components)`, `evaluate`); rows are `EquationSpec`s built against an `Algebra` (`compile/spec.py:112`), properties come
from `PropertyBlock`s the unit builds from its own provider, and `MODEL_BUILDERS`/`MODEL_BASES`/`MODEL_SIGNATURES`
(`application/revision_binding.py:1579–1674`) are identity tables. Each family encodes its provider's physics (ADR 0050
D3). `model_version` = `<label>@sha256(structure document v1)`, whose five members are the variable, equation and
parameter ids and the row accumulation (`canonical.py:444–496`); ADR 0002 D2.7 planned a `-v2` document with a
`sources` member for when problems are assembled from manifests. P1/P2 give the registry (ADR 0060), records by SHA
(ADR 0061), `mat-v1` definitions, vids, `ProcessRevision` v2 and lowering (ADR 0062), `MaterialModel.state_point`
(ADR 0063 D7) and the generalised phase contract with discrete coordinates (ADR 0064 D3). A v2 document in the
v1-expressible subset is *lowered* and runs the untouched v1 path; every other v2 document needs this ADR's compiler.

## Decisions

### D1. The `UnitModel` v2 protocol and its types (`src/openflowsheet/units_v2/`)

```python
class UnitModelV2(Protocol):
    model_id: str; version: str                      # = the unit_model descriptor's (id, version)
    def declare(self, binding: UnitBinding) -> UnitDeclaration: ...          # pure; no state, no property call
    def contribute(self, decl: UnitDeclaration, wiring: WiringV2,
                   material: MaterialModel, mode: Literal["steady", "dynamic"]) -> ContributionV2: ...
    # optional, present iff the manifest declares them:
    def evaluate(self, decl, inlets: Mapping[str, Sequence[MaterialState]], material) -> UnitEvaluationV2: ...
    def reseed(self, decl, port: str, opening: OpeningView) -> ReseedValue: ...   # D8, kind `unit_code` only
    def initialize(self, decl, inlets, material) -> Mapping[str, float]: ...       # guesses for owned variables
```

- `UnitBinding` (frozen): instance path (D13), validated parameter values, per port the ordered connection ids and
  their `definition_sha256`, per side the method set (ADR 0063 D5; default one method set), mode.
- `WiringV2` maps each port to its connections' `MaterialLayout` slots (ADR 0062 D8) or energy/signal variable ids; it
  never exposes an id to be parsed.
- `ContributionV2` (frozen): `rows: tuple[RowSpecV2]` (`EquationSpec` plus `kind`, `dimension` and the build-time raw-read
  set, D6), `owned_variables: tuple[(vid, quantity_kind, role)]`, `parameters: tuple[(pid, value)]` in declaration
  order, `state_points: tuple[StatePointRequest]`, `forms: tuple[ZeroFlowFormInstance]`, `blocks` (opaque, D14 only);
  in dynamic mode also `differential_pairs`, `discrete_states`, `event_functionals`, `zero_holdup_forms`, `transfers`
  (types defined by ADR 0066; F6 refuses dynamic mode, D18).
- `UnitEvaluationV2`: outlets as `MaterialState`, energy and work per port, `status`; on any status but `ok` nothing
  else (no partial answer), as v1's `UnitEvaluation`.

v1's `UnitModel`, `Contribution` and `EquationSpec` are untouched; `RowSpecV2` is a new type that the v2 compiler lowers
to `EquationSpec` (`accumulation` widened only through ADR 0066's `state_rate`).

### D2. `ModelManifest` v2 = the `unit_model` v2 payload (`schemas/model-manifest-v2.schema.json`, closed objects)

`manifest_format: "openflowsheet-unit-manifest-v2"`. Identity, title, status and `requires` are the F1 descriptor's
(ADR 0060 D2); the manifest is its `payload`, so `descriptor_sha256` covers it. Name alphabet for ports, sides,
parameters, points, rows, forms and internal variables: `^[a-z][a-z0-9_]*$`.

| Field | Content | Freeze |
| --- | --- | --- |
| `modes` | non-empty subset of `steady`, `dynamic`; `variant_of: <unit id> \| null` (a dynamic variant names its steady model, ADR 0008 X4′) | core |
| `ports` | `[{name, kind: material\|energy\|signal, direction, multiplicity: int ≥ 1 \| "many", side?: <side>, accepts?: [template id…] (material: `mat-v1`, `nTP-v1`), subset_fill: bool, quantity_kind?: (signal)}]` | core; declared maps `preview` |
| `sides` | `[{id, ports: [name…], requires: CNF}]`; every material port in exactly one side; omitted = one side `main` over all material ports | core |
| `parameters` | `[{name, quantity_kind, structural: bool, domain: {min?, max?, values?, integer: bool}, manipulable: bool}]`; every parameter is required in the instance (no defaults, R-924 explicitness); a structural parameter may change the row set and enters the declaration (D3); a manipulable one may be bound by a signal (D10) and is never structural | core |
| `internal_variables` | `[{name, field: x\|xi\|N\|A\|U\|K\|r, quantity_kind, index?: "carried"\|"reaction"\|"holdup_kind"}]` (D4) | core |
| `state_points` | `[{id, side, amounts: {port} \| {rows}, spec: [[quantity, kind], [quantity, kind]] (quantities from {T, P, h, s, v, beta}, kind molar or specific), candidates: "method", outputs: [vocabulary item…], formulation: "procedural"}]` | core; `candidates` assertion `preview` |
| `rows` | `[{id, index?: "carried"\|"port"\|"reaction", accumulation: ADR 0008 D3 object (+ `state_rate`, ADR 0066), quantity_kind, dimension, statement}]` | core |
| `zero_flow_forms` | D7 | core |
| `zero_holdup_forms` | D7 (grammar only; built with TX) | core grammar |
| `reactivation` | `{<outlet port>: D8 object}`; `t_seed: {parameter: <name>} \| {specification} \| "first_flowing_inlet"` | core |
| `phase_routing` | `[{point, light_to_heavy: [outlet port…], solids: <port> \| null}]` (D9) | core |
| `heat_ports`, `heat_curve` | D11 | core |
| `derivatives` | v1's `DerivativeDeclaration` list | core |
| `initialization` | v1's object | core |
| `execution` | `{class: native\|opaque_block\|external_process\|cosimulation\|cape_open, derivative_method: analytic\|ad\|finite_difference\|unavailable, thread_safety, cost_class}` (D14) | core envelope |
| `stateful` | bool; `true` iff state lives outside `x` (required `true` for `cosimulation`, `false` for `native`) | core |
| `causal_evaluation` | bool: whether `evaluate` exists (traversal and initializers use it) | core |
| `semantic_roles` | non-empty list of `semantic_role` ids, first the default (D15) | core |
| `equipment` | `[{item, class: <equipment_class id>, sizing: [{name, quantity_kind, from: {parameter}\|{variable}\|{derived}}]}]` | `preview` |
| `coverage` | `{parameters: {…}, specifications: [Specification v2…], feed: "basis"}`: the generated case of D16; required for `status` ≥ `implemented` | core |
| `validity` | v1's object, `phases` as phase-set renderings (ADR 0062 D6) | core |

Validation (typed, at registration; a built-in failing any is a build failure): every row index set resolvable; every
`holdup_balance` row's `holdup.kind` a registered holdup kind (ADR 0066 D3); every point's `side` declared; every
`reactivation` key an outlet material port; every `phase_routing` port an outlet of the point's side; at most one
`variant_of` chain level.

### D3. The unit declaration and the v2-compiled fingerprint

`declare(binding)` returns a canonical document (`schemas/unit-declaration.schema.json`): `{declaration_format:
"openflowsheet-unit-declaration-v1", instance, model: [id, version, descriptor_sha256, self_sha256], mode, ports: [{port,
connections: [ids], definition_sha256}], sides: [{side, method_set_sha256}], structural_parameters: {…}, state_points:
[{id, spec, candidates rendering, side}], rows: [row ids], owned_variables: [vids], parameters: [pids], forms: [form
ids], routing: [{point, ports}]}`. Numeric parameter values are **not** in it (they are pinned inputs, in
`constants_sha256`). `declaration_sha256 = document_sha256(declaration)`.

**Structure document v2** (`src/openflowsheet/compile/structure_v2.py`, a new module; `canonical.py` is not edited):
v1's five members with `structure_schema: "compiled-problem-structure-v2"`, plus `sources`: a list of `[role, id,
sha256]` sorted by (role, id) in UTF-8 bytes, with roles `compiler` (id `openflowsheet.units_v2`, sha = ADR 0060 D3's
self-hash over the declared compiler module set, with D3's import-closure completeness check), `data_lock` (id `""`,
the run's `data_lock_sha256`, ADR 0061 D10), `definition` (each connection-definition id, its `definition_sha256`),
`expression` (each expression document id, its SHA, D12), `template` (each flattened instance path, the template
revision's `content_hash`, D13) and `unit` (each instance path, its `declaration_sha256`); plus `differential_map`
when ADR 0066 makes the problem dynamic. `model_version = <label>@sha256(structure document v2)`.

Who uses which: v1 documents and lowered v2 documents compile through the v1 path with structure v1 (ADR 0062 D8; F0
M2 unchanged). Every problem the v2 compiler builds uses v2. **[departure]** ADR 0002 D2.7 sketched "the content
hashes of the contributing manifests *and of the revision*". The revision hash is left out: it carries every pinned
numeric value, which ADR 0002 keeps in `constants_sha256`; with it, `model_version` would move on every parameter edit
and every structure-compatibility rule keyed on `model_version` (warm starts, sparsity reuse) would break. The
declarations carry everything structural the revision contributes.

### D4. Unit-owned variable and parameter ids (ADR 0062 D7 field table, appended; core)

Owner = the instance path (`uid ("/" uid)*`, D13). Control volumes and state points share one per-unit id namespace
declared in the manifest (the `#point` slot of the grammar names either). Fields (closed; additions by amendment):

| Field | Index | Meaning | Kind |
| --- | --- | --- | --- |
| `Q` | `[<energy port>]` | heat through that port when unconnected (connected: the connection's `~Q`) | `heat_rate` |
| `W` | `[<energy port>]` | work through that port when unconnected | `power` |
| `x` | `[<name>]` | an algebraic internal variable | declared |
| `xi` | `[<reaction id>]` | an extent rate | `molar_flow` (or `segment_molar_flow`) |
| `N`, `A` | carried index as connection `n` / `a` | material holdup of a control volume (`<U>#<cv>~N[...]`) | the amount / attribute kind |
| `U` | — | energy holdup of a material control volume | `energy` |
| `K` | `[<holdup kind id>]` | non-material holdup (`<U>#<cv>~K[wall_energy]`, Q1.R9) | the kind's |
| `r` | `[<name>]` | a `state_rate` state (ADR 0066) | declared |

Parameter ids of v2-compiled problems use the same grammar with fields `p[<name>]` (unit parameter) and `z[<name>]`
(discrete state held as a pinned input, ADR 0066 D4). Index rendering: decimal for integers, the name otherwise.
`tests/f2/vid_parse.py` extends its injectivity proof to these fields (E-F2-5's generator).

### D5. Sides and per-side admission (ADR 0060 D12, additive)

A side is a manifest-declared group of material ports evaluated with one method set (ADR 0063 D5). Admission for a
unit with sides `S1…Sk`: `admit_sides(unit, {side: (method, definition)})` runs ADR 0060 D5 steps 0–3 once per side,
with the unit-level `requires` conjoined to that side's `requires`, and refuses with the first failing side in
manifest order,
`capability_missing(<unit>, <method>, <clause>)` plus `params.side`. A unit without `sides` has one side whose
`requires` is empty, so its verdict is exactly D5's (E-F6-3 proves it over the full matrix). `check_admission`
(Amendment 10) accepts `{unit, sides: {<side>: {method, definition}}}` beside ADR 0060 D11's forms. In 0.6 a revision's
`property_methods.overrides[].side` stays `preview` (ADR 0062 D11): every side of an instance takes the default method
set unless an override is given.

### D6. State points, raw reads and the no-read rule (Q5.R7, adopted)

A row builder reads a state point through a handle with two accessors per phase slot: `amount_weighted(output)`
returns `n_p · o_p` (both block outputs; at an inactive slot both are `+0.0` with derivative `+0.0`, so any label value
leaves the row and its Jacobian unchanged), and `raw(output)` returns `o_p`. While each row is built, the handle records
every `raw` access as `(point, slot, output)`; the record is the row's **raw-read set** (deterministic, part of the
declaration's row metadata, not of the structure document). At every opening, for each active row and each raw read of
a slot that is inactive in the opening signature: if an active zero-flow form (D7) swaps that row, nothing happens;
otherwise the opening is refused `inactive_phase_read(<row>, <phase>)`. Amounts and phase fractions are always readable
(they are amounts). Q5.A8's seam (labels set to 1.0) is the test of this design.

### D7. Zero-flow forms (Q1.R4 for unit rows) and zero-holdup forms

A form: `{id, trigger: {port: <material port>} | {phase_inactive: {point, slot}}, swap: [row id…], labels: [{row:
<new row id>, field: "h" | "T", label: "first_inlet" | "zero"}]}`. It is **selected exactly when its trigger is
exactly dormant** (every carried amount of every connection on the port `== 0.0` after signed-zero normalisation,
ADR 0062 D4; or the slot inactive). Then the swapped rows leave and the label rows `<field>_out − <field>_label = 0`
enter, with `<field>_label` the `h` (on `mat-v1`) or `T` (on `nTP-v1`) of the unit's first material inlet in the
revision's `connections` order, or `+0.0` for `"zero"` (a unit with no inlet). A label row is never compiled into the
declaration and never moves `model_version` (ADR 0012 D4(c)'s rule). **Carrying it:** F6 registers the F1
`discrete_coordinate` `zero_flow_form` (values `absent`, `present` per (instance, form); adjacency absent ↔ present);
the F5 contract (ADR 0064 D3) treats it as one more coordinate: screen = dormancy agreement per trial, closure =
agreement both ways and ADR 0012 D4(c)'s swapped-row test (`zero_flow_conflict(<row>)`). **Coverage is generated**
(a CI check, E-F6-9; the registry runs no numerics): for every dormancy pattern of a unit's material ports (all 2^k
patterns, k ≤ 6; larger k sampled with a fixed seed), the unit's Jacobian block with the selected forms must be
structurally regular (DM matching) and numerically regular at the generator's probe state; a failure names
`zero_flow_form_missing(<unit>, <row>)` and fails CI. `zero_holdup_forms` use the same object with `trigger: {holdup: <control volume>}`; F6 validates their grammar,
ADR 0066 gives their mechanics and TX builds the units that use them.

### D8. Reactivation (Q1.R6, adopted)

Per outlet material port, the manifest declares how its `h` is re-seeded at an opening where it flows again after a
label wrote it: `{kind: "copy_inlet", inlet: <port>}` (bitwise the inlet's `h`: splitter, valve), `{kind: "feed_spec"}`
(`Ḣ(T_spec, P, n)/ṁ` from the feed's own point), `{kind: "phase_outlet", point}` (its routed phase's `h` from the
opening flash, D9), `{kind: "unit_code"}` (the unit's `reseed`). A port without an entry falls to Q1.R6 (2): `Ḣ(T_seed,
P, n)/ṁ` from a TP point under the side's method, `T_seed` per `t_seed`. The opening runs passes in plan order until a
pass seeds nothing; a stream left unseeded fails the opening `reactivation_seed_unavailable(<connection>)`. An
instrumented counter in `MaterialModel.state_point` counts evaluations with a label input; it must stay 0 (Q1.A9).

### D9. Port routing of phases (A2-b; decided here)

A unit whose outlets take phases of a state point declares `phase_routing`: outlet ports from light to heavy, and
optionally a `solids` port. At every **opening** the routing is fixed for the attempt: (i) at a point of a `split`
method (families VAPOR/LIQUID, legacy and delegating methods), VAPOR to the first port and the LIQUID slots to the
following ports in mass-density order, ascending (with two candidates this is today's routing exactly; equivalence
step 1 depends on it); (ii) at a point of a `single` method (FLUID), active fluid phases by **mass density**, ascending,
to ports in order. In both, phases beyond the last port go to the last port; SOLID phases to `solids`, else to the last port. (iii) *Exactly one active FLUID
phase*: density order says nothing, so the phase goes to the first port iff its `character` (ADR 0064, O-11's rule) is
vapour-like, else to the last; **specifier question SQ-F6-1**, default as stated. The assignment is the F1 discrete
coordinate `phase_routing` (value: port → phase-set rendering; adjacency: one transposition of density-adjacent phases,
or a change of the single phase's port). Closure checks the order at the converged state; a different order closes
the attempt `routing_order_changed(<unit>)` and the controller opens the adjacent assignment (cycle rule as ADR 0005).
A relative density gap ≤ τ_ρ attaches `near_threshold` (Q4.R5's pattern; τ_ρ = 1e-6, SQ-F6-1).

### D10. Energy and signal constructs; manipulable parameters; steady controllers

ADR 0062 D9's constructs compile in v2: an energy connection's `~Q`/`~W` is the variable both endpoint units read with
ADR 0001 D4.1's sign (inlet port: into the unit). A probe `{probe: target}` adds the signal variable `~s` and the
algebraic row `s − target = 0` (target as a Specification v2 target, a derived quantity through its state point). A
parameter sink makes the parameter `p[name]` a column equal to the signal's `~s` (one variable; the unit's rows read
the signal symbol in place of the pinned value), refused if the parameter is not `manipulable`.

**Steady controller `std.pid`** (ports `pv` signal inlet, `out` signal outlet; parameters `sp`, `out_min`, `out_max`,
`action: direct | reverse` (structural), gains (unused in steady mode)). With integral action it contributes one owned
variable (the `out` connection's `~s`) and one row chosen by the F1 discrete coordinate `controller_regime` ∈
{`tracking`, `saturated_low`, `saturated_high`}: tracking `e = sp − pv = 0` (the row ADR 0066's `state_rate` integral
row reduces to at `ṙ = 0`, so steady and dynamic agree bitwise); saturated `out − out_min = 0` or `out − out_max = 0`.
Adjacency: tracking ↔ each saturated value. Closure: tracking requires `out_min ≤ out ≤ out_max`; `saturated_low`
requires `σ·e ≤ 0` and `saturated_high` `σ·e ≥ 0`, with σ = +1 for `reverse`, −1 for `direct` (an integrator that would
drive the output further past its limit); a failed condition closes the attempt and opens the adjacent regime
(**SQ-F6-3**, default as stated). Ratio, lead–lag, selector and split range are TX's seed (**[departure]**: note
§2.4.11 lists them with `std.pid`; F6's exit needs only the PI loop, and their dynamic semantics are TX's).

### D11. Heat intervals, heat curves and `heat_direction`

`heat_ports: [{port, side, from: "inlet" | <point>, to: "outlet" | <point>}]`: the temperature interval of the process
side exchanging heat through that energy port is [min, max] of the derived T at `from` and `to`. The verifier check
`heat_direction` (judged, outside the residual): for a heat connection from A to B, `max T_A ≥ min T_B − τ_hd`; τ_hd is
the existing exchanger temperature-cross check's tolerance (`verify/table.py:965`) (**SQ-F6-4**). `heat_curve: {port,
side, points: int ≥ 2}`: a post-solve projection (rule C5; never in identity) of (T, cumulative Q) at `points` PH points
evenly spaced in `h` between `from` and `to` at the side's outlet P, computed through `MaterialModel`; X14 reads it.

### D12. Expression documents (`schemas/expression.schema.json`; `src/openflowsheet/expressions/`)

```
document := {expression_format: "openflowsheet-expression-v1", quantity_kind, body: expr}
expr := {c: <finite float>}                                   # constant, ADR 0002 canonical float
      | {v: <field>[index]}  | {p: <parameter name>}           # unit-local variable / parameter
      | {q: <vocabulary item>, at: <point>, phase?: <rendering>, weighted?: true}   # state-point output (D6 accessor)
      | {op: "add"|"mul", args: [expr, expr, …]}               # n-ary, evaluated left to right as written
      | {op: "sub"|"div"|"pow", args: [expr, expr]} | {op: "neg"|"exp"|"log"|"sqrt", args: [expr]}
      | {regime: <discrete coordinate id>, cases: {<value>: expr}}   # piecewise only through declared regimes (E01 D3)
```

No reordering, folding or simplification in canonical form: the document's SHA (`document_sha256`) pins the
floating-point evaluation order. Validation infers each node's quantity kind and dimension (ADR 0001 D1.2 exponent
vectors; `exp`/`log` arguments dimensionless; `add`/`sub` operands equal) and refuses `expression_dimension_mismatch`.
The compiler maps the AST onto the same `Algebra` that `EquationSpec.build` receives; a domain violation at evaluation
raises `DomainError` (an invalid trial, as today). The verifier re-evaluates every expression with its own evaluator
(`expressions/evaluate.py`, plain Python floats, no import of the compiler). Expression documents enter `content_hash`
where the revision holds them and the structure-v2 `sources`. **Uses** (declarative user units as `unit_model`
descriptors whose rows are expressions, controller laws, the `expression` kinetics kind, TX events and inputs, recipe
conditions, report quantities) are `preview` to the end of 0.6; Python units stay admitted under the `install` right.

### D13. Templates and flattening (`preview` to the end of 0.6)

An instance may carry `template: {revision: <content_hash>, ports: {<exposed>: "<inner instance>.<port>"},
parameters: {<exposed>: "<inner instance>.<parameter>"}}` (ADR 0062 D11's `template` slot). At bind time the template
revision (from the project store; absent: `template_unavailable(<hash>)`) is flattened: each inner instance and
connection id becomes `<outer id>/<inner id>`, recursively (depth ≤ 8, a repeated hash on the path refuses
`template_cycle(<hash>)`); exposed ports are replaced by the inner endpoints; inner specifications are kept with
prefixed targets; exposed parameters override the inner values. Ids therefore depend only on instance ids, never on
array order. The flattened revision is derived, never stored; each flattened instance's template hash enters `sources`.

### D14. Execution classes: external, co-simulated and CAPE-OPEN seams

`native` units contribute rows. `opaque_block` units (ADR 0033/0034's in-process external models) contribute one
`PropertyBlock`-shaped unit block with a declared Jacobian pattern and `derivative_method`; `finite_difference` and
`unavailable` carry ADR 0034's limitations. `external_process` keeps ADR 0034 D6 (R3). `cosimulation` (R-923) requires
`stateful: true` and `modes: [dynamic]`; it is refused `mode_unsupported(steady)` in steady runs and
`construct_unavailable(cosimulation, TX)` until TX. `cape_open` is refused `construct_unavailable(cape_open, X15)` until
X15, and its descriptor declares `platforms: ["windows-x86_64"]`. No class but `native` is admitted by D16's matrix.

### D15. Semantic roles and equipment classes

`semantic_role` (F1 kind; payload `{description}`; built-in only, core): the v1 enum's fourteen values (ADR 0054) plus
`utility`, `controller`, `shaft`, `relief_device` (ADR 0062 D11). An instance's role must be in its unit's
`semantic_roles` or be `other` (`semantic_role_mismatch(<instance>)`); roles stay descriptive (ADR 0054 D2): no solver
or verifier code reads them. `equipment_class` (F1 kind, `preview`, shared with X12, X16, X23): payload `{parent: <id> |
null, sizing_quantities: [{name, quantity_kind}]}`; F6 seeds one class per `std.*` unit (`vessel.drum`, `exchanger.duty`,
`valve.control`, `pump.centrifugal`, `compressor.centrifugal`, `turbine.expander`, `mixer.junction`, `splitter.tee`)
and leaves the taxonomy's growth to X12. Identity follows use (note §2.4.10).

### D16. The `std.*` seed, its equations, and the coverage matrix

**Seed** (`src/openflowsheet/std/`): `std.feed`, `std.sink`, `std.mixer`, `std.splitter`, `std.heater`, `std.valve`,
`std.flash` (inlet multiplicity `many`; fixed-P with duty, the TP and PH modes of the legacy flashes being
specifications), `std.pump` (structural parameter `work_model: isentropic | incompressible`, matching `thermal.pump` and
`syn001.liquid_pump`), `std.compressor`, `std.turbine` (isentropic reference = a PS state point at `(n, s_in, P_out)`
with candidates = the method's, no declared phase, ADR 0064 D4), and `std.pid` (D10). Every module imports only
`openflowsheet.units_v2`, `openflowsheet.material`, `openflowsheet.expressions` and the standard library (E-F6-1).
**Equations source.** Design-approved now: the T-form rows of the legacy units they replace (SYN-001 units design
§4, ADR 0051's thermal rows, ADR 0012 D12's forms) and Q1.R1–R6 for the `h_mass` coordinate. Not yet approved: the
`h_mass` row set of each unit with its zero-flow forms, reactivation kinds and `t_seed`, which a specifier equation
sheet `docs/derivations/F6-std-seed.md` must give (**SQ-F6-2**). F6-WO5 builds the T-form variants first; the `h_mass`
forms wait for the sheet.

**Coverage matrix** (`scripts/coverage_matrix.py --check`, one summary line, log in a file). Axes: every registered
v2 `unit_model` with `execution.class: native` × every `property_method` × the definition templates the unit accepts
(`nTP-v1` and a generated `mat-v1` with one `mixed` substream and the revision's coordinate). The verdict of each triple
comes from D5. *Admitted:* the generator builds feed(s) → unit → sink(s) from the method's entry in
`benchmarks/f6/coverage-bases.yaml` (component set, feed T, P, z inside the method's domain) and the manifest's
`coverage` block; the case must reach `VERIFIED`. *Refused:* the refusal must be typed with a catalogued code. CI fails
on an admitted triple without a bases entry or not `VERIFIED`, and on an untyped refusal; so a new method or unit enters
automatically and fails until it is covered. Legacy units are outside the generated cases (their admission set is ADR
0060 E-F1-1's; their corpus is F0's).

### D17. Legacy freeze, v1 adapter, equivalence and retirement (R-929)

**Byte freeze** as the note (S1; F0 M9). **v1 adapter** (`units_v2/adapter_v1.py`): wraps a legacy unit for a
v2-compiled revision that mixes it with v2 units: `declare` from its v1 manifest and signature (one side, `nTP-v1`
ports, no state points, its ADR 0012 D12 forms as D7 forms), `contribute` delegating to v1 `contribute` with today's ids
(ADR 0062 D7 keeps them on `nTP-v1`). **[departure]** Admitted only for legacy units with no phase-selecting point (no
lifted split, no T05b regime; the generated table `legacy_adaptable.json` reads T05b's signature-unit registry); others
are refused `legacy_unit_not_adaptable(<model>)` with the remedy "use the `std.*` counterpart or keep the revision
v1-expressible". Reason: carrying T05b's kernel-driven split regimes into the generalised controller is a second phase
contract inside the first; nothing in the corpus needs it.

**Equivalence** (M2), exactly the note's relation and Π (§2.4 migration proof), in two steps: step 1, `std.*` on a `T`
flowsheet (`nTP-v1`, native convention, the legacy provider through its delegating composed method) against the legacy
units on every corpus case whose units the seed covers, on the `syn001`, Wilson, IAPWS-95 and CoolProp bases; step 2,
`std.*` on `T` against `std.*` on `h_mass` with `ELEMENTAL-ref-v1` at every non-degenerate corpus state. The legacy →
`std.*` correspondence for the harness is a committed table `benchmarks/f6/equivalence-map.yaml` (model id → std unit,
parameter map, specification map); it is not a user tool (U4). A case with a unit outside the seed is reported
`equivalence_pending(<family>)`.

**Retirement.** `scripts/f6_parity.py --check` writes `benchmarks/f6/parity.json`: per legacy family, parity iff every
unit of the family has a map entry and passes step 1 on all its corpus cases and its matrix triples. A family at parity
is closed: in a **v2** revision the binder refuses its units `legacy_family_closed(<family>, <std model>)`; v1 revisions
are unaffected forever. Expected in 0.6: `thermal` reaches parity; `syn001` and `c1` do not (column, cascade, reactors,
exchanger, separator are outside the seed).

### D18. Modes

F6 builds steady variants. `mode: dynamic` is refused `mode_unsupported(dynamic)` until TX; dynamic variants are
separate manifests (`variant_of`) sharing kernels with the steady ones (ADR 0008 X4′).

### D19. Core at the end of W1, and preview

**Core (frozen):** D1's protocol and type field sets; D2's fields marked core; D3's declaration document and structure
v2 (members, roles, ordering); D4's fields; D5's per-side admission; D6's accessors and the opening rule; D7's form
grammar, selection rule, label values and the `zero_flow_form` coordinate; D8's kinds; D9's routing rule and
coordinate; D10's endpoint semantics, `std.pid`'s steady rows and `controller_regime`; D11's interval rule; D12's
document format and node set (additions by amendment); D14's class envelope; D15's role vocabulary; D16's matrix rule;
D17's freeze, adapter limit and retirement rule. **Preview (to the end of 0.6, R-929):** templates (D13), per-side
method overrides, phase assertions in `candidates`, declared port maps, expression *uses*, `equipment` and
`equipment_class`, sizing and costing hooks.

## Alternatives rejected

- *Extending v1 `UnitModel`/`Contribution` with optional fields.* `Contribution` instances feed identity-bearing v1
  paths; any default-valued field risks a changed `asdict` digest (the ADR 0062 `PropertyCapabilities` lesson), and the
  v1 contract has no state points, sides or forms to hang them on.
- *Inferring raw reads from the CasADi graph.* The graph cannot tell `n_p·o_p` from `o_p` once multiplied by other
  terms, so the no-read rule would be heuristic; the accessor record is exact and costs nothing at evaluation.
- *Zero-flow forms as a per-call switch inside the residual.* A switch makes the function depend on a threshold of `x`
  without a recorded decision; ADR 0012 D12 chose attempt-level coordinates for the same reason.
- *Routing by `character` for every FLUID point.* It would give O-11's identification rule numerical consequence where
  density already decides (two or more phases) and would split two liquids by an identification parameter that does not
  separate them.
- *A family per provider; refactoring legacy families in place; a built-in two-phase assumption; code-only user
  models* — the note's rejections, unchanged.

## Migration proof

F0 PASS on every work order (no frozen module edited; `canonical.py`, `models/__init__.py` and `compile/spec.py`
untouched; v1 and lowered runs keep structure v1, so M2 cannot move). Equivalence steps 1 and 2 (E-F6-5, E-F6-6) are
the numerical proof that `std.*` describes the same processes. The ADR 0002 D7 migration report: no instance migrated;
structure v2 applies only to problems no released artifact contains.

## Exit tests (F0 PASS implied on each)

- **E-F6-1** Architecture: an AST scan finds no import of `openflowsheet.thermo.<provider>`, `openflowsheet.models` or
  `application.revision_binding` from `openflowsheet.std` or `openflowsheet.units_v2` (except `adapter_v1.py`).
- **E-F6-2** Every `std.*` manifest validates; one invalid fixture per D2 validation rule, each refused with its code.
- **E-F6-3** Per-side admission: over the full `admission_matrix`, every single-side verdict equals ADR 0060 D5's
  bitwise (same list); a two-side probe is admitted per side and refused naming the failing side.
- **E-F6-4** Coverage matrix complete; mutation controls: deleting one bases entry, or making one refusal untyped,
  fails the check.
- **E-F6-5** Equivalence step 1 on every covered corpus case (CoolProp leg on a machine with the extra); the
  `equivalence_pending` list is printed and committed.
- **E-F6-6** Equivalence step 2 at every non-degenerate corpus state.
- **E-F6-7** Q1.A9 (a)–(c) with the mutation control.
- **E-F6-8** Q5.A8 with the mutation control.
- **E-F6-9** Zero-flow coverage **[gen]**: every `std.*` unit, every dormancy pattern of its material ports: forms
  selected exactly; the block regular after the swap; dormant `h` bitwise its Q1.R4 label; label-input counter 0.
- **E-F6-10** Routing: (a) split points route bitwise as legacy (inside E-F6-5); (b) a `single`-method decanter probe
  with a heavy-oil/water density inversion between two specifications routes by density, the inversion restarting by
  adjacency with `routing_order_changed`; (c) a single FLUID phase follows D9 (iii); (d) a gap below τ_ρ flags
  `near_threshold`.
- **E-F6-11** Templates: a two-level template flattens to stable ids (permuting inner arrays or re-flattening changes no
  id; renaming the outer instance changes only prefixes); a cycle is refused `template_cycle`.
- **E-F6-12** Expressions: round trip and SHA stability under key order; dimension refusals; a compiled expression row
  equals the hand-written row bitwise in value and Jacobian at 100 generated states; the verifier's evaluator agrees
  within 1e-14 relative; `log` of a negative is an invalid trial.
- **E-F6-13** `mode_unsupported(dynamic)`; `cosimulation` and `cape_open` refused typed.
- **E-F6-14** Steady PI: a heater duty driven by `std.pid` on the outlet T solves as a design specification (`VERIFIED`,
  outlet T = sp within the certificate tolerance); with sp out of reach the attempt sequence is tracking →
  `saturated_high`, `out = out_max`, `VERIFIED`, the regime sequence recorded.
- **E-F6-15** Scaling (N9): `std` flash-stage column template, 10 components, stages {10, 20, 40, 70, 100}, median of 3:
  log–log slope ≤ 1.3 for compile time and for time per Newton iteration; the 1e4-variable rate-based probe (50 stages,
  10 components, 3 points per stage) records absolute times (R1).
- **E-F6-16** The FB-04 turbine on `std.turbine`, `composed.iapws95-v1`, `mat-v1` `h_mass`, `ELEMENTAL-ref-v1`, wet
  outlet, no declared phase: `VERIFIED`; outlet β and `h` within the registered tolerance of E-F5-6's reference.
- **E-F6-17** Structure v2: `model_version` moves on a change of a declaration, definition SHA, expression, data lock or
  compiler self-hash, and not on a numeric parameter value (which moves `constants_sha256`).
- **E-F6-18** Constructs: a condenser–reboiler probe joined by `heat-v1` closes energy within τ_E; `heat_direction`
  passes on it and fails on a reversed fixture; a probe and a parameter sink compile; no `construct_unavailable(…, F6)`
  remains for them.
- **E-F6-19** R19 measurement: over every `VERIFIED` `h_mass` run of E-F6-4 and E-F6-6, the log gives min, median and
  max of ĉ_p,eff = 1/(dT/dh) at flowing one-phase points and each run's energy-check margin.
- **E-F6-20** Retirement: with `parity.json` forced closed for a test family, a v2 revision using it is refused
  `legacy_family_closed`; the same unit in a v1 revision runs unchanged.
- **E-F6-21** v1 adapter: `syn001.feed_source` (syn001 basis) feeding `std.heater` runs; adapted rows equal the v1 rows
  bitwise at the same `x`; a legacy flash in a mixed revision is refused `legacy_unit_not_adaptable`.

## New catalogue codes (ADR 0058 C3)

`mode_unsupported`, `inactive_phase_read`, `reactivation_seed_unavailable`, `zero_flow_form_missing`,
`routing_order_changed` (notice), `semantic_role_mismatch`, `legacy_family_closed`, `legacy_unit_not_adaptable`,
`template_unavailable`, `template_cycle`, `template_port_unknown`, `expression_invalid`,
`expression_dimension_mismatch`, `controller_saturated` (notice), `equivalence_pending` (notice); check id
`heat_direction`.

## Work orders (`wp/F6`, 0.6; WO1–WO3 may start once F1-WO2 and F2-WO3 are on `main`; WO4 on needs F4-WO4 and F5's contract)

| # | WO | Content and files | Acceptance | Identity | Lane |
| --- | --- | --- | --- | --- | --- |
| 1 | **F6-WO1** Types, manifest, ids | `units_v2/{__init__,types,manifest}.py`; `schemas/{model-manifest-v2,unit-declaration}.schema.json`; vid fields in `material/vid.py`, `tests/f2/vid_parse.py`; F1 payload schemas for `unit_model` v2, `semantic_role` (+ built-ins), `equipment_class` | E-F6-2 (schema part), E-F2-5 extended | no | Opus (types); Sonnet (schema fixtures) |
| 2 | **F6-WO2** Sides and matrix skeleton | `units_v2/admission.py`; `scripts/coverage_matrix.py` (verdict table only); Amendment 10 request form | E-F6-3 | no | Opus |
| 3 | **F6-WO3** Expressions | `expressions/{grammar,canonical,compile,evaluate}.py`; `schemas/expression.schema.json` | E-F6-12 | no | Opus |
| 4 | **F6-WO4** v2 compiler and phase machinery | `units_v2/{binding,compile,forms,routing,reactivation}.py`; `compile/structure_v2.py`; registration of `zero_flow_form`, `phase_routing`, `controller_regime`; test-only probe units | E-F6-17, E-F6-8, E-F6-9 (probes), E-F6-10 (b–d) | no | Opus |
| 5 | **F6-WO5** `std.*` seed | `std/*.py`; `benchmarks/f6/coverage-bases.yaml`; matrix cases; `h_mass` forms after SQ-F6-2 | E-F6-4, -7, -9, -13, -16 | no | Opus |
| 6 | **F6-WO6** Equivalence, retirement, adapter | `benchmarks/f6/equivalence-map.yaml`; `scripts/{f6_equivalence,f6_parity}.py`; `units_v2/adapter_v1.py`, `legacy_adaptable.json` generator | E-F6-5, -6, -20, -21 | no | Opus |
| 7 | **F6-WO7** Constructs and controller | energy/signal compile path; `std/pid.py`; heat intervals, curves, `heat_direction` in the verifier | E-F6-14, -18 | no | Opus |
| 8 | **F6-WO8** Templates and scale | `units_v2/templates.py`; `scripts/f6_scaling.py` | E-F6-11, -15 | no | Opus |
| 9 | **F6-WO9** Close-out | E-F6-1 test; catalogue entries; R19 log; evidence manifest; full gate; CI both legs | E-F6-1, -19, all | no | Sonnet |

**Unblocks.** WO1–WO4: X10 gaps, X08, X09, X13, X19 (`std.*` work on the framework). WO5–WO6: X10 gaps' matrix, the
`thermal` retirement. WO7: TX controllers (dynamic `std.pid`), X12 utilities (energy connections), X14 (heat curves and
intervals). WO8: X22 (templates, rate stages), X24 superstructure blocks. D14's seams: X15 (CAPE-OPEN), TX
(co-simulation). F7 needs WO1–WO4 (manifest rows, structure v2, `differential_map` slot).

## Risks and open questions (each with a default)

1. **SQ-F6-2 delays the `h_mass` seed** (fact: specifier round timing). *Default:* WO5 builds T-form units first; E-F6-6
   and E-F6-16 wait for the sheet; F6 does not exit without them.
2. **R1 scale** (fact: E-F6-15). *Default:* keep D02; a slope > 1.3 or unusable absolute time is an architect question
   recorded as an ADR on the expression layer (note R1).
3. **The adapter limit** (preference: Frank). Mixed revisions with legacy flashes or columns are refused. *Default:* as
   D17; lifting it is a later ADR if a user needs it before `syn001` reaches parity.
4. **Compiler self-hash in `model_version`** (preference). Every compiler edit re-registers the v2 corpus, as legacy
   module edits would. *Default:* keep it; an inert refactor is still proved by `state_sha256` and certificates.
5. **c_ref, ΔT_ref** (fact: E-F6-19). *Default:* keep 2.0e3 J/(kg K) and 100 K; propose an ADR-F4 amendment if the median
   ĉ_p,eff lies outside [c_ref/10, 10 c_ref] or any run's energy-check margin is below 10×.
6. **Coverage bases for CoolProp's 118 fluids** (fact). *Default:* one bases entry per method id (a representative fluid
   set), not per fluid; per-fluid coverage stays with ADR 0063's tests.

## Specifier questions (batched for the round after P3; defaults let work proceed)

- **SQ-F6-1** (A2-b residue) Routing of exactly one active FLUID phase, and τ_ρ. *Default:* D9 (iii) by `character`
  (O-11's rule, which then gains a numerical consequence: Frank should know when answering O-11); τ_ρ = 1e-6 relative.
- **SQ-F6-2** The `std.*` equation sheet: per unit, the `h_mass` row set (division-free, Q1.R2), its zero-flow forms,
  reactivation kinds and `t_seed`. *Default:* the mechanical restatement `Ḣ_S = ṁ_S h_S` of the approved T-form rows;
  a form for every row whose `h` coefficient is the `ṁ` of a port that can be dormant; Q1.R6's three examples as kinds.
- **SQ-F6-3** Steady saturation closure (D10): the sign condition and the adjacency. *Default:* as D10.
- **SQ-F6-4** `heat_direction`'s tolerance τ_hd and whether an equal-temperature contact passes. *Default:* the
  exchanger temperature-cross check's tolerance; equality passes.
