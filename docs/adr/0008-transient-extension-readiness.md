# ADR 0008 — Transient-extension readiness: time at the evaluation boundary, state-hash coverage, and per-row accumulation declarations

**Status:** Accepted (directed by Frank Peters, 2026-09-16; decision register R-001). The migration in "Consequences" is applied by the Opus session on branch `adr/0008-transient-readiness`; the ADR is in force once `PATH=.venv/bin:$PATH ./scripts/check.sh` passes with the tests listed under "Acceptance evidence". Amended by Amendment 1 (accepted 2026-09-26).  
**Date:** 2026-09-16  
**Author:** Fable 5.1 (Fable owns every ADR, all derivations including the PTC mapping, and every change to the P01 interface freeze, plan §1.3)  
**Affected requirements:** D07 (PTC: equation-to-state mapping, mass matrix, sign convention — the part a unit model must declare about itself), D10 (exact property cache — confirmed unchanged and explicitly closed against a time coordinate), A01 (context lifetime), A03 (the PTC step is formed outside the evaluation boundary), D20 and blueprint §8.3 (the state hash is an evaluation identity, not a run fingerprint), blueprint §3.2 (pinned inputs), §4.1 (ModelManifest), §4.4 (schema migration), §6.4, §7.5.  
**Affected packages:** K01 (compiled-problem assembly and schema promotion), K02 (first unit models), K03 (contexts per attempt), T04 (PTC family), T05 (new unit models), and every later package that introduces a unit model or a compiled-problem schema. ADR 0002 (canonical hash encoding) and ADR 0007 (replay identity) inherit D2 as a constraint.  
**Blueprint authority:** §2.2 (dynamics deferred — binding and untouched by this ADR), §3.2 ("Parameter and specification values are pinned inputs"), §4.1 (ModelManifest content), §6.4 (exact cache key), §7.5 and D07 ("The model supplies the equation-to-variable mapping, M, sign conventions … No generic diagonal-magnitude recipe is trusted by default").

## Context

Frank intends, at a later release, to simulate transient behaviour and switching feeds. Blueprint §2.2 defers dynamics and that deferral stands. The question put to this ADR (brief `docs/briefs/ADR-0008-transient-readiness.md`) is which provisions must be fixed *now*, while `src/` is 561 lines and no unit model exists, so that a later transient capability is an additive extension rather than a refactor of every unit model and of the residual/Jacobian boundary. Three candidate provisions were named: P-1, a time coordinate in `EvaluationContext`; P-2, what `state_sha256` covers; P-3, an accumulation declaration per conservation row in every unit model.

Two facts about the repository shape the rulings. First, most of the semi-explicit DAE skeleton is already a v0.1 obligation through PTC: blueprint §7.5 writes `M(x̂) dx̂/dτ = −F̂(x̂)` with zero rows for algebraic equations, requires the model to supply the equation-to-variable mapping, `M` and the sign convention, and forms the linearly implicit step `(M_k/Δτ + Ĵ_k) Δx̂ = −F̂_k` from `Ĵ_k` — the Jacobian this boundary already returns. The plan (`docs/implementation-plan.md:255`) has committed the first PTC family to the *physical holdup* qualification route (a): a flash with liquid and vapour holdup, mass and energy accumulation, explicit residual sign and mass mapping. So the accumulation structure of the SYN-001 units is needed in v0.1 regardless of any transient plan; the only question is who owns each unit's share of it. Second, the six declared SYN-001 manifests already disagree on the sign of their balance rows: `FLASH-mole`, `MIX-mole`, `MIX-energy`, `HEAT-duty` and `FLASH-duty` are written inflow-minus-outflow, `HEAT-mole` is written outflow-minus-inflow. That is exactly the sign/mapping hazard the plan warns about ("Do not use −F as artificial dynamics without checking the sign/mapping"), and it is cheapest to remove before a single residual is implemented.

The residual/Jacobian identity rule (`docs/interfaces-frozen.md` §1; CLAUDE.md "Scientific conduct") is enforced through matching `state_sha256`, `model_version` and phase signature. Today `state_sha256` is the P02-local hash of the state doubles in variable order (`docs/derivations/P02-composition-spec.md` §10.4, recomputed independently by `benchmarks/p02/judge.py:_state_sha256`). No document says what the hash *covers* as opposed to how it is *encoded*; the encoding is ADR 0002's, the coverage is fixed here.

## Where the blueprint §2.2 line is

§2.2 forbids *building a DAE compiler* in the first release and says that *reserving metadata for future dynamics does not by itself justify one*. This ADR reserves metadata and freezes two coverage rules. It builds no integrator, no event detection, no index reduction, no holdup state variable, no mass matrix, no time-varying schema field and no trajectory certificate, and it changes no release gate. The metadata it reserves (D3) is not reserved *for* dynamics: it is the manifest-level half of the D07 obligation that T04 must discharge for steady-state PTC in v0.1. The two coverage rules (D1, D2) close ambiguities that exist today in the steady-state boundary. The line is: **a unit model states what its rows conserve; the solver layer, not the model, decides whether anything is ever integrated.** Nothing in this ADR crosses it.

## Decision

### D1. Time is not a coordinate of the evaluation boundary (P-1: adopt-modified — the field is rejected, the concern is closed another way)

1. **No time at the boundary.** `residual(x, context)`, `jacobian(x, context)` and `reconstruct(x, context)` are functions of the dense free-variable vector `x` and of the *pinned inputs* identified by `context`. Neither physical time `t`, pseudo-time `τ`, a time step `h` or `Δτ`, nor any history vector (`x_{n−1}`, an estimate of `ẋ`) is ever an argument of these methods, a coordinate of `x`, or a field of `EvaluationContext`. The field `time: float | None` proposed in the brief is **rejected**.
2. **Why.** A residual `F` is a state function of `(x, p)` where `p` is the vector of pinned inputs. Time enters a transient problem in exactly two places, and neither is inside `F`: (i) through the *accumulation term* `M dx/dt`, which an integrator forms from `x` at two or more stage points and a step — outside the boundary, using the `M` that models declare (D3) and the `J` the boundary already returns; (ii) through *time-varying boundary specifications* `p(t)`, which the orchestrator evaluates at the stage time to a value and pins. The compiled problem sees `p`, never `t`. Thermodynamic properties are state functions and never depend on `t`; a `t` field in the context would therefore have to be *excluded* from the exact-property key by a rule nobody would test, which is the silent-inconsistency risk the brief names. Putting `t` into `x` would put a column into the Jacobian that no equation differentiates. Putting it into the context conflates two lifetimes: a context pins what is constant across an attempt; a pinned value at a stage time *is* constant across the nonlinear solve at that stage, and the blueprint already has the right name for such a thing — a pinned input (§3.2).
3. **Pinned inputs and their identity.** Parameter and specification values — including the value at the current stage time of a time-varying specification — are pinned inputs. They are identified at the boundary by the pair (`model_version`, `constants_sha256`): two evaluations whose non-state inputs differ in any way have distinct pairs. The P02 convention (spec §10.4: `constants_sha256` over the thirteen SYN-001 physical constants, specification values fixed by the form named in `model_version`) satisfies this rule and stands as recorded. K01's obligation under this rule is D4.1.
4. **`workspace` is inert.** `EvaluationContext.workspace` carries run-local mutable work buffers (scratch arrays, caches that are *exact* by construction, counters). Nothing the evaluated function depends on may be carried in it: not time, not a parameter value, not a specification value, not a phase decision. Two contexts that differ only in `workspace` evaluate the same function at the same `x`. This is normative now; its executable test arrives with the first compiled problem (D4.2), because nothing evaluates a residual in the gate today.
5. **Exact-property cache key: unchanged.** The key is blueprint §6.4's list verbatim (provider implementation and data hashes, ordered components, reference convention, state-definition ID, exact canonical numerical inputs, phase/branch policy, requested properties, derivative order, accuracy policy). This ADR adds nothing to it and forbids adding a time coordinate to it. If a provider ever needs `t` in its key, it is not a property provider and is not admitted through `PropertyProvider`.
6. **What P-1 neutralizes, and how it is tested now.** The lock-in was that a later session, finding no `time` field, would thread it through `workspace` or add it to the context unilaterally. After this ADR the field set of `EvaluationContext` and the parameter lists of the three Protocol methods are frozen by an executable test (C7, assertions A1–A3), so either move fails the gate and points at this ADR; and `docs/interfaces-frozen.md` §1 states the rule in the frozen text (C1).

### D2. `state_sha256` covers exactly `x` (P-2: adopt)

1. **Coverage.** `state_sha256` is a hash over exactly the dense vector `x` as passed to `residual`/`jacobian`/`reconstruct`, in `CompiledProblemMetadata.variable_ids` order, after signed-zero normalization (ADR 0001 D1.5). Every coordinate of `x` participates at full double precision; the order participates; nothing else participates. Encoding of the doubles is ADR 0002's (until ADR 0002 closes, the P02-local `%.17g` comma-joined UTF-8 text of spec §10.4 is the encoding in use); this ADR fixes coverage, not encoding, and no test may pin a digest value.
2. **Excluded by construction.** Context fields (echoed separately in the result), pinned inputs (identified by `constants_sha256`/`model_version`), the phase signature (echoed separately), reconstructed or derived quantities (phase split, enthalpy flows), and any integrator internal (`t`, `τ`, `h`, `x_{n−1}`, `ẋ`) — none of which exists at the boundary (D1).
3. **Consequence for a later transient extension.** If holdup states are ever introduced, they are free variables: elements of `x` with `variable_ids`, columns of the Jacobian. They are then covered by `state_sha256` automatically, with no change to this rule, to the result types or to the judge. A design that kept holdup outside `x` would violate D2 and ADR 0001 D2.5 (two descriptions of one function) and requires a new ADR.
4. **Pairing identity.** A `JacobianResult` is paired with an `EvaluationResult` — "describes the same function at the same state" — exactly when the four echoed fields `model_version`, `constants_sha256`, `state_sha256` and `phase_signature` are equal and both were produced under the same context (which pins the accuracy policy). No other field participates in pairing. `accuracy` is not added to `JacobianResult`: the context pins it and widening the result type would serve no transient purpose.
5. **Relation to ADR 0007.** `state_sha256` is an evaluation-boundary identity. Run fingerprints, replay identity and certificate hashes are ADR 0007's; they may *include* state hashes but may not redefine what `state_sha256` covers. Blueprint §8.3's exclusions (timestamps, job IDs, telemetry) never applied to `state_sha256` and still do not.
6. **Quantization.** Because every coordinate participates at full precision, a hash that is invariant under a one-ulp change of any coordinate is a quantized hash and is forbidden (blueprint §6.4: "Quantizing state coordinates … is forbidden in exact evaluation"). Assertion H1 in C7 is the executable form of this sentence.

### D3. Every equation a model declares carries an accumulation declaration (P-3: adopt, made precise)

1. **The declaration.** Every item of `ModelManifest.mathematics.equations[]` carries a required property `accumulation` with `kind` one of exactly three values:

   | `kind` | Meaning | Also required |
   | --- | --- | --- |
   | `algebraic` | The row is not an instance of a conservation law: a specification, an equilibrium relation, a pressure equality, a definitional or dormant-inlet rule. It is a zero row of any mass matrix in any formulation. | — |
   | `zero_holdup_balance` | The row *is* a conservation balance of the unit, and its holdup is identically zero **by the model's definition** (a junction, a divider). It is a zero row of `M` because the physics says so, not because anyone chose a magnitude. A version of the unit with holdup is a *different model* with its own manifest. | `reason` (non-empty prose) and the equation's `dimension` |
   | `holdup_balance` | The row is a conservation balance whose steady-state form is the zero-accumulation limit of `d(holdup)/dt = F_row`. The manifest names the accumulated quantity: `holdup.symbol`, `holdup.quantity` (prose) and `holdup.dimension` (ADR 0001 D1.2 exponent vector). No holdup *variable* exists in `nTP-v1`; the declaration names what a holdup formulation would accumulate, and its dimension. | `holdup` object and the equation's `dimension` |

   The property has no default. A manifest without it is invalid, exactly as `Capabilities` has no default: a default of `algebraic` would make every forgotten balance row read as "no accumulation", which is the placeholder success path this provision exists to remove.
2. **Dimension consistency (executable now).** For a `holdup_balance` row, the equation's `dimension` equals `holdup.dimension` with the time exponent (index 2 of `DIMENSION_ORDER`) lowered by one. Component balance: holdup mol `(0,0,0,0,1,0,0)`, row mol/s `(0,0,−1,0,1,0,0)`. Energy balance: holdup J `(2,1,−2,0,0,0,0)`, row W `(2,1,−3,0,0,0,0)`. A mismatch is a semantic validation error (C6).
3. **Sign convention for balance rows (normative).** For every `holdup_balance` and `zero_holdup_balance` row the residual *as written in the manifest and as implemented* is

   `F_row = Σ inflow − Σ outflow + Σ sources`,

   where sources are duties and shaft work positive into the unit (ADR 0001 D4.1) and generation terms, so that the physical balance reads **`d(holdup)/dt = + F_row`**. Five of the six SYN-001 balance rows already comply; `HEAT-mole` is rewritten from `n_out,i − n_in,i = 0` to `n_in,i − n_out,i = 0` (C4). The steady-state content of the row is unchanged by the sign; its Jacobian row changes sign, which is why this must be fixed before K02 implements it. Executable test: K02's first heater residual at a trial state with `n_in,i = 1 mol/s`, `n_out,i = 0.5 mol/s` returns `F_HEAT-mole,i = +0.5 mol/s` exactly (the row is linear) — D4.3.
4. **Relation to blueprint §7.5.** The blueprint's PTC form is `M dx̂/dτ = −F̂`. With D3.3, a holdup row's `F̂_row` is `−F_row` (an exact row sign of −1), and an algebraic row's `F̂_row` is `F_row`. T04 must declare this row-sign map explicitly in its PTC mapping, as one named constant applied to residual and Jacobian together, exactly as P02 declared `OUTPUT_ROW_SIGN` (spec §4.3) — a falsifiable convention adapter, never an implicit flip. The magnitudes of `M` (holdup nominals, residence times, thermal inertia) and the equation-to-variable mapping remain T04's derivation under D07 and are **not** fixed here. What is fixed is that `M`'s *pattern* is read from the manifests: a row may receive a nonzero `M` entry only if its manifest kind is `holdup_balance`. A central recipe that assigns `M` entries to rows of any other kind, or assigns them by row magnitude without reading the manifests, violates D07 and this ADR.
5. **Registered classification of the SYN-001 manifests.** The six declared manifests are classified as follows; the table is normative and is pinned by assertion M1 (C7).

   | Model | Equation | `kind` | Holdup |
   | --- | --- | --- | --- |
   | `syn001.feed_source` | `FEED-n`, `FEED-T`, `FEED-P` | `algebraic` | — |
   | `syn001.adiabatic_mixer` | `MIX-mole` | `zero_holdup_balance` | — (junction) |
   | | `MIX-energy` | `zero_holdup_balance` | — (junction) |
   | | `MIX-pressure`, `MIX-dormant-inlet` | `algebraic` | — |
   | `syn001.tp_heater` | `HEAT-mole` | `holdup_balance` | `N_i`, mol |
   | | `HEAT-duty` | `holdup_balance` | `U`, J |
   | | `HEAT-T`, `HEAT-pressure`, `HEAT-equilibrium` | `algebraic` | — |
   | `syn001.tp_flash` | `FLASH-mole` | `holdup_balance` | `N_i`, mol |
   | | `FLASH-duty` | `holdup_balance` | `U`, J |
   | | `FLASH-equilibrium`, `FLASH-T`, `FLASH-P` | `algebraic` | — |
   | `syn001.stream_splitter` | `SPLIT-recycle`, `SPLIT-purge`, `SPLIT-T`, `SPLIT-P` | `algebraic` | — |
   | `syn001.product_sink` | (no equations) | — | — |

   Reasons, so the table is not relabelled by accident. The **mixer** is a junction: its outlet is the instantaneous sum of its inlets and it has no volume; its two balances are therefore balances with identically zero holdup. A mixing vessel is a different model. The **heater** shares the TP-state kernel with the flash and is a vessel with fluid content and thermal inertia; its component and energy balances admit holdup `N_i` (mol) and `U` (J, internal energy of the contents — the quantity an open-system energy balance accumulates; flows carry enthalpy). The **flash** is the plan's first PTC family and carries the same two holdups. The **splitter** rows `n_rec,i − r n_in,i` and `n_pur,i − (1−r) n_in,i` are split *relations*, not conservation rows (their sum is the divider's balance, which has no holdup); they are algebraic. **Feed** rows are boundary specifications; the **sink** contributes no equation (its empty list is already a positive assertion, schema description). Counts: 4 `holdup_balance`, 2 `zero_holdup_balance`, 15 `algebraic`, 21 rows — assertion M3.
6. **Opaque models.** A manifest using `mathematics.evaluator_reference` has no equation list and therefore no per-row declaration. Such a model is *ineligible* for any holdup-based formulation: at assembly, every row it contributes is reported with accumulation `absent` (D4.4). Silence never reads as `algebraic`.
7. **Why per-model, not central (the brief's question).** `M` assigned centrally must either be a magnitude recipe (forbidden by D07) or must consult each model for its holdup structure — at which point the model has to declare it, and the only question is whether the declaration is a schema field checked at validation or a convention rediscovered from prose at T04 time. The field costs one line per equation today and its absence would cost a re-opening of every manifest, every K02 implementation and every T05 model when T04 arrives.

### D4. Obligations on later packages (normative, not testable on the current repository)

These are stated here so that no later package can claim ignorance; each names the test that discharges it. None is a change to a frozen interface beyond what C1 records.

1. **K01 — pinned-input identity.** When K01 assembles the first compiled problem from manifests and promotes the CompiledProblem schemas to `schemas/`, `constants_sha256` becomes the hash (ADR 0002 encoding) of the complete pinned-input vector of the compiled-problem *instance* — physical constants, model parameters and specification values — in the order of a new metadata field `CompiledProblemMetadata.parameter_ids: tuple[str, ...]`; `model_version` identifies equation structure and backend form only. Test: two instances compiled from the same structure with different fresh-feed values share `model_version`, differ in `constants_sha256`, and return different residuals at the same `x`. Re-binding without recompilation is permitted and recommended; recompilation is not forbidden.
2. **K01 — inert workspace.** Test: for a registered state, `residual(x, ctx)` and `residual(x, ctx')` with `ctx'` differing from `ctx` only in `workspace` (a non-empty mapping containing, deliberately, keys named `time`, `t` and `tau` with finite values) return equal `values`, equal `state_sha256` and equal `constants_sha256`; likewise for `jacobian`.
3. **K02 — balance-row sign.** For each `holdup_balance` and `zero_holdup_balance` row of each implemented model, at a registered trial state with inflow ≠ outflow, `sign(F_row) = sign(Σ inflow − Σ outflow + Σ sources)`; for the linear rows the value is exact: `HEAT-mole` with `n_in,i = 1`, `n_out,i = 0.5` gives `+0.5 mol/s`; `MIX-mole` with two inlets at `0.25` and outlet at `1.0` gives `−0.5 mol/s`.
4. **K01 — row accumulation in metadata.** When the CompiledProblem metadata schema is promoted, it carries `row_accumulation: Mapping[str, Literal["algebraic", "zero_holdup_balance", "holdup_balance", "absent"]]` keyed by equation id, copied from the contributing manifests (`absent` for rows from an opaque evaluator or from a row with no manifest, such as a tear or specification-promotion row that K01 itself generates — K01 must declare those `algebraic` explicitly, since it authored them). Test: every `equation_id` in the metadata has an entry, and the multiset of kinds equals the manifests' multiset for the SYN-001 flowsheet.
5. **T04 — pattern of `M` from the manifests.** The PTC mapping derivation reads `row_accumulation` and assigns nonzero `M` entries only to `holdup_balance` rows; it declares the row-sign map of D3.4 as one named constant; it records that a `zero_holdup_balance` row is a zero row *by physics*. Test: for the SYN-001 flowsheet, the set of rows with nonzero `M` equals the set of `holdup_balance` rows.
6. **Any later transient ADR.** Holdup states are elements of `x` (D2.3); time reaches the orchestrator, never the boundary (D1.1); the accumulation term is formed outside `residual` (D1.2). A design that needs otherwise revises this ADR first.

## Alternatives considered

- **`time: float | None = None` on `EvaluationContext` (the brief's P-1 candidate).** Rejected. It makes the residual's identity depend on a coordinate the thermodynamics never sees, forces an exclusion rule on the exact-property key, and misnames a pinned input. The `None` default would also be the kind of default that reads as a capability statement.
- **`t` as a coordinate of `x` with a trivial equation.** Rejected: a Jacobian column nothing differentiates, a hash coordinate that is not a state, and a violation of "`x` is the ordered free variables".
- **An `ẋ` (or `x_prev`, `h`) argument on `residual`.** Rejected: it would change the frozen Protocol arity for a capability that is deferred, and the linearly implicit step of §7.5 does not need it — it forms the accumulation term from `J` and `M`.
- **`state_sha256` covering `(x, phase_signature)` or `(x, constants)`.** Rejected: each of those is already echoed as its own field; folding them in would make the state hash change when the state does not, and would make "same state, different phase attempt" indistinguishable from "different state" in a trace.
- **A `parameters_sha256` field on `EvaluationContext` now.** Rejected for now: no pinned parameter vector exists before K01, an honest value today would be `None`, and the identity rule is satisfied by the existing pair. K01 discharges it inside `constants_sha256` (D4.1) without widening the context.
- **A two-valued `accumulation` (`none` / `holdup`).** Rejected: it cannot say that a junction's balance is zero *by physics* rather than by omission, so a later PTC pass could not tell a forgotten holdup from a genuine junction without reading prose.
- **Accumulation as a single per-manifest field ("this unit has holdup").** Rejected: `M` is per row; a flash has holdup on its mole and energy rows and none on its equilibrium and specification rows.
- **Declaring the mixer `holdup_balance` "to be safe".** Rejected: it would commit T04 to inventing a junction holdup (the artificial route (b) the plan did not choose), and a mixing vessel is a different model.
- **Putting the declaration in `CompiledProblemMetadata` only (central), not in `ModelManifest`.** Rejected: that is the central assignment P-3 exists to prevent, and it is not testable until K01, by which time K02's models would be written without it.
- **Defer all three with the rest of dynamics.** Rejected by Frank (R-001); the analysis here agrees for P-3 (cost rises per model) and P-2 (a coverage rule nobody wrote down is the kind that gets encoded wrong), and finds P-1 cheaper still — it needs no field at all.

## Consequences — the migration, verbatim

Opus applies the following exactly. No scientific choice is left open; where a value appears below it is the value.

### C1. `docs/interfaces-frozen.md`

In §1, the bullet list "Binding semantics attached to the signatures", **replace** the second bullet

> - `EvaluationResult` carries status, active-set (phase) signature, state/model hash, accuracy information, and evaluation counters. `JacobianResult` is valid only for the same state, model version, phase regime, and evaluation policy as its residual; `residual` and `jacobian` describe the same function at the same state.

with

> - `EvaluationResult` carries status, active-set (phase) signature, state/model hash, accuracy information, and evaluation counters. `JacobianResult` is valid only for the same state, model version, phase regime, and evaluation policy as its residual; `residual` and `jacobian` describe the same function at the same state. `state_sha256` covers exactly the dense vector `x` as passed, in `variable_ids` order, after signed-zero normalization, and nothing else; the pairing identity is equality of `model_version`, `constants_sha256`, `state_sha256` and `phase_signature` under the same context (ADR 0008 D2). Encoding of the hash is ADR 0002's.

and **replace** the third bullet

> - `EvaluationContext` pins model/data versions, phase signature, accuracy policy, and run-local workspace; the outer active-set controller constructs a new context after a phase restart.

with

> - `EvaluationContext` pins model/data versions, phase signature, accuracy policy, and run-local workspace; the outer active-set controller constructs a new context after a phase restart. Time is not a coordinate of this boundary (ADR 0008 D1): no field of `EvaluationContext` and no argument of `residual`, `jacobian` or `reconstruct` carries physical time, pseudo-time, a time step or a state history. Parameter and specification values — including the current value of a time-varying boundary specification — are pinned inputs evaluated by the orchestrator before the call and identified by the pair (`model_version`, `constants_sha256`). `workspace` carries run-local work buffers only; the evaluated function never depends on its contents.

In §2, **append** after the sentence "Canonical JSON encoding rules are ADR 0002 …":

> `ModelManifest` was migrated by ADR 0008 (a required per-equation `accumulation` declaration, D3); the migration report is ADR 0008 "Consequences" C3–C5 and the only instances, the six declared SYN-001 manifests, were migrated in the same change.

In §3, **replace**

> ADR 0001 D1–D5 (units, state definition `nTP-v1`, zero flow, signs, reference conventions) are part of this freeze.

with

> ADR 0001 D1–D5 (units, state definition `nTP-v1`, zero flow, signs, reference conventions) and ADR 0008 D1–D3 (no time at the evaluation boundary, `state_sha256` coverage, per-row accumulation declarations and the balance-row sign convention) are part of this freeze.

No signature in §1's code block changes.

### C2. `src/process_runtime/compiled.py` — docstrings only, no field or signature changes

Replace the `EvaluationContext` docstring with:

```python
    """Pins model and data versions, phase signature, accuracy policy and workspace.

    The outer active-set controller constructs a new context after a phase restart; a
    `JacobianResult` is valid only for the same context as its residual.

    Time is not a coordinate of this boundary (ADR 0008 D1). No field here carries physical
    time, pseudo-time, a step or a state history, and none may be added without a new ADR:
    `tests/test_adr_0008_transient_readiness.py` pins this field set. A time-varying boundary
    specification reaches the compiled problem as a pinned input evaluated by the orchestrator
    and identified by (`model_version`, `constants_sha256`). `workspace` holds run-local work
    buffers only; the evaluated function never depends on its contents.
    """
```

In `EvaluationResult` and `JacobianResult`, replace the line `    state_sha256: str` with

```python
    #: Hash of exactly the dense `x` as passed, in `variable_ids` order, after signed-zero
    #: normalization, and nothing else (ADR 0008 D2). Encoding is ADR 0002's.
    state_sha256: str
```

### C3. `schemas/model-manifest.schema.json`

In `properties.mathematics.properties.equations.items`:

- change `"required": ["id", "statement", "dependencies", "conditional_class"]` to `"required": ["id", "statement", "dependencies", "conditional_class", "accumulation"]`;
- add to its `properties`: `"accumulation": { "$ref": "#/$defs/accumulation" }`;
- add to the item object (sibling of `properties`):

```json
"if": {
  "properties": {
    "accumulation": {
      "properties": { "kind": { "enum": ["holdup_balance", "zero_holdup_balance"] } }
    }
  }
},
"then": { "required": ["dimension"] }
```

Add to `$defs`:

```json
"accumulation": {
  "description": "ADR 0008 D3. Every equation says what it conserves. `algebraic`: not a conservation row; a zero row of any mass matrix. `zero_holdup_balance`: a conservation balance whose holdup is identically zero by the model's definition (junction, divider) — a zero row of M by physics, with the reason stated. `holdup_balance`: a conservation balance whose steady-state form is the zero-accumulation limit of d(holdup)/dt = F_row; names the accumulated quantity and its dimension. Balance rows are written F_row = inflow − outflow + sources (D3.3). No default: a forgotten declaration is invalid, never `algebraic`.",
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind"],
      "properties": { "kind": { "const": "algebraic" } }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "reason"],
      "properties": {
        "kind": { "const": "zero_holdup_balance" },
        "reason": { "type": "string", "minLength": 1 }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "holdup"],
      "properties": {
        "kind": { "const": "holdup_balance" },
        "holdup": {
          "type": "object",
          "additionalProperties": false,
          "required": ["symbol", "quantity", "dimension"],
          "properties": {
            "symbol": { "type": "string", "minLength": 1 },
            "quantity": { "type": "string", "minLength": 1 },
            "dimension": {
              "$ref": "https://github.com/frankp/process-runtime/schemas/quantity.schema.json#/$defs/dimension"
            }
          }
        }
      }
    }
  ]
}
```

Append to the schema's top-level `description`: ` ADR 0008 D3 added the required per-equation `accumulation` declaration.`

### C4. The six valid fixtures, `tests/fixtures/schemas/model_manifest/valid/*.yaml`

Append `accumulation:` as the **last key of each equation item**, at the item's key indentation (four spaces). Exact blocks:

`feed.yaml` — `FEED-n`, `FEED-T`, `FEED-P`:
```yaml
    accumulation:
      kind: algebraic
```

`mixer.yaml` — `MIX-mole`:
```yaml
    accumulation:
      kind: zero_holdup_balance
      reason: The adiabatic mixer is a junction with no volume; its outlet is the instantaneous
        sum of its inlets, so the component holdup is identically zero by the model's definition.
        A mixing vessel with holdup is a different model with its own manifest (ADR 0008 D3.5).
```
`MIX-energy`:
```yaml
    accumulation:
      kind: zero_holdup_balance
      reason: Junction with no volume and no thermal inertia by the model's definition; the energy
        holdup is identically zero. A mixing vessel is a different model (ADR 0008 D3.5).
```
`MIX-pressure`, `MIX-dormant-inlet`:
```yaml
    accumulation:
      kind: algebraic
```

`heater.yaml` — first **replace** the `HEAT-mole` statement line

```yaml
    statement: n_out,i - n_in,i = 0 for every component i
```
with
```yaml
    statement: n_in,i - n_out,i = 0 for every component i
```
then `HEAT-mole`:
```yaml
    accumulation:
      kind: holdup_balance
      holdup:
        symbol: N_i
        quantity: component moles held in the heater
        dimension:
        - 0
        - 0
        - 0
        - 0
        - 1
        - 0
        - 0
```
`HEAT-duty`:
```yaml
    accumulation:
      kind: holdup_balance
      holdup:
        symbol: U
        quantity: internal energy of the heater contents
        dimension:
        - 2
        - 1
        - -2
        - 0
        - 0
        - 0
        - 0
```
`HEAT-T`, `HEAT-pressure`, `HEAT-equilibrium`:
```yaml
    accumulation:
      kind: algebraic
```

`flash.yaml` — `FLASH-mole`:
```yaml
    accumulation:
      kind: holdup_balance
      holdup:
        symbol: N_i
        quantity: component moles held in the flash drum, vapor plus liquid
        dimension:
        - 0
        - 0
        - 0
        - 0
        - 1
        - 0
        - 0
```
`FLASH-duty`:
```yaml
    accumulation:
      kind: holdup_balance
      holdup:
        symbol: U
        quantity: internal energy of the flash drum contents
        dimension:
        - 2
        - 1
        - -2
        - 0
        - 0
        - 0
        - 0
```
`FLASH-equilibrium`, `FLASH-T`, `FLASH-P`:
```yaml
    accumulation:
      kind: algebraic
```

`splitter.yaml` — `SPLIT-recycle`, `SPLIT-purge`, `SPLIT-T`, `SPLIT-P`:
```yaml
    accumulation:
      kind: algebraic
```

`sink.yaml` — no change (`equations: []`).

Also add one sentence to the header comment of `heater.yaml`: `# ADR 0008 D3.3: HEAT-mole is written inflow minus outflow, like every other balance row.`

### C5. New invalid fixtures under `tests/fixtures/schemas/model_manifest/invalid/`

`missing-accumulation.yaml`:
```yaml
# Invalid ModelManifest: an equation without an accumulation declaration.
#
# ADR 0008 D3.1: `accumulation` has no default. A conservation row that forgets to say what it
# conserves must fail validation, never read as `algebraic`.
expect_error: "'accumulation' is a required property"
document:
  id: syn001.bad_manifest_no_accumulation
  version: 0.0.0-declared
  status: declared
  introduced_by_package: K02
  ports:
  - name: inlet
    kind: material
    direction: inlet
    multiplicity: 1
    component_mapping: revision_component_set
    state_definition: nTP-v1
    phase_capabilities:
    - liquid
  mathematics:
    equations:
    - id: BAD-mole
      statement: n_in,i - n_out,i = 0 for every component i
      dependencies:
      - inlet.state.n
      conditional_class: unconditional
      dimension:
      - 0
      - 0
      - -1
      - 0
      - 1
      - 0
      - 0
  derivatives:
  - output: outlet.state
    with_respect_to:
    - inlet.state
    method: unavailable
  initialization:
    strategy: none
    notes: n/a
  validity:
    domain:
      temperature_K:
        min: 280.0
        max: 440.0
      pressure_Pa:
        min: 50000.0
        max: 200000.0
      components:
      - A
      - B
      - C
    limitations:
    - deliberately malformed fixture
  implementation_artifact:
    state: not_implemented
    module: null
    artifact_hash: null
  execution_requirements:
    execution_class: native_equation
    thread_safety: unknown
    evaluation_cost_class: unknown
```

`holdup-dimension-mismatch.yaml` — identical to the above except `expect_error: time exponent lowered by one`, `id: syn001.bad_manifest_holdup_dimension`, and the equation item gains
```yaml
      accumulation:
        kind: holdup_balance
        holdup:
          symbol: U
          quantity: internal energy of the contents
          dimension:
          - 2
          - 1
          - -2
          - 0
          - 0
          - 0
          - 0
```
(an energy holdup declared on a mol/s row: the JSON Schema accepts it, the semantic check of C6 must reject it).

`balance-without-dimension.yaml` — identical to `missing-accumulation.yaml` except `expect_error: "'dimension' is a required property"`, `id: syn001.bad_manifest_balance_no_dimension`, the equation item **omits** `dimension`, and gains
```yaml
      accumulation:
        kind: zero_holdup_balance
        reason: deliberately malformed fixture
```

### C6. `tests/test_schemas_p01.py` — semantic check for the dimension rule

Add to `semantic_problems` a branch for `name == "model_manifest"` calling a new function; add the function:

```python
TIME_INDEX = DIMENSION_ORDER.index("time")


def accumulation_problems(document: Any) -> list[str]:
    """ADR 0008 D3.2: a holdup_balance row's dimension is its holdup's dimension per second."""
    problems: list[str] = []
    if not isinstance(document, dict):
        return problems
    equations = (document.get("mathematics") or {}).get("equations") or []
    for index, equation in enumerate(equations):
        accumulation = equation.get("accumulation") if isinstance(equation, dict) else None
        if not isinstance(accumulation, dict) or accumulation.get("kind") != "holdup_balance":
            continue
        holdup_dimension = (accumulation.get("holdup") or {}).get("dimension")
        row_dimension = equation.get("dimension")
        if not isinstance(holdup_dimension, list) or not isinstance(row_dimension, list):
            continue  # the schema reports these
        expected = list(holdup_dimension)
        expected[TIME_INDEX] -= 1
        if row_dimension != expected:
            problems.append(
                f"$.mathematics.equations[{index}] ({equation.get('id')}): holdup_balance row "
                f"dimension {row_dimension} must equal the holdup dimension {holdup_dimension} "
                f"with the time exponent lowered by one"
            )
    return problems
```

`DIMENSION_ORDER` is already imported in that file. The `test_invalid_fixture_is_rejected_for_the_stated_reason` parametrization picks the three new fixtures up automatically; `expect_error` substrings are as given in C5.

### C7. New test module `tests/test_adr_0008_transient_readiness.py`

Module docstring names this ADR and states that every assertion below is a pin on a decision, not a numerical result. Numbered assertions; each is one test function named `test_a1_…`, `test_h1_…`, `test_m1_…` so a manifest can cite it.

**A — boundary shape** (imports from `process_runtime.compiled`; `dataclasses.fields`; `inspect.signature`).

- **A1** `tuple(f.name for f in fields(EvaluationContext)) == ("model_version", "constants_sha256", "phase_signature", "accuracy_policy", "workspace")`. Exact; a later `time`, `t`, `tau`, `dt` or any other field fails here and the message cites ADR 0008 D1.
- **A2** For each `name in ("residual", "jacobian", "reconstruct")`: `tuple(inspect.signature(getattr(CompiledProblem, name)).parameters) == ("self", "x", "context")`. Exact; an `xdot`, `t` or `h` argument fails here.
- **A3** For each of `EvaluationResult`, `JacobianResult`: `{"model_version", "constants_sha256", "state_sha256", "phase_signature"} <= {f.name for f in fields(cls)}` — the four pairing fields of D2.4 are present on both.

**H — state-hash coverage** (against `benchmarks.p02.judge._state_sha256`, the judge's independent implementation of the convention in force; import the private name deliberately, with a comment that ADR 0002/K01 must port these assertions to the canonical hash). Registered state, used by every H assertion:

```python
ORDER = ("a", "b", "c", "d", "e")
X0 = {"a": 1.5, "b": -2.25, "c": 0.0, "d": 3.0e-7, "e": 1.0e5}
```
Why these: five distinct values so a swap is detectable; `c` is registered *because* it is zero (H3 tests signed zero there; H1 tests that the one-ulp step from 0.0, which is the smallest subnormal, still registers); `d` and `e` span eleven decades so that H1 exercises a one-ulp change at `1e5` (`1.4551915228366852e-11` absolute), which a hash quantized at any fixed absolute or 1e-15-relative grid would miss. No digest value is pinned (D2.1).

- **H1** (every coordinate participates at full precision; D2.6) For each `name in ORDER`: `x = dict(X0); x[name] = math.nextafter(X0[name], math.inf)`; assert `_state_sha256(x, ORDER) != _state_sha256(X0, ORDER)`. Exact inequality, five cases.
- **H2** (order participates) `x = dict(X0); x["a"], x["b"] = X0["b"], X0["a"]`; assert hash differs from `X0`'s.
- **H3** (signed zero, ADR 0001 D1.5) `x = dict(X0); x["c"] = -0.0`; assert hash **equals** `X0`'s.
- **H4** (nothing outside `x` participates) `x = dict(X0); x["t"] = 12.5; x["tau"] = 0.75`; assert hash **equals** `X0`'s — keys not in `ORDER` do not reach the hash.
- **H5** (length participates) assert `_state_sha256(X0, ORDER[:-1]) != _state_sha256(X0, ORDER)`.
- **H6** (pure function of `(x, order)`) `tuple(inspect.signature(_state_sha256).parameters) == ("x", "order")`.

**M — manifest accumulation** (load the six valid fixtures with `conftest.load_yaml`; helper returns `{(model_id, equation_id): equation}`).

- **M1** (registered classification, D3.5) The mapping `{(model_id, eq_id): equation["accumulation"]["kind"]}` equals exactly the 21-entry table of D3.5, written out in the test as a literal dict. A relabelled, added or removed row fails here.
- **M2** (holdup identity) For each `holdup_balance` row: `holdup.symbol` and `holdup.dimension` equal the registered pair — `HEAT-mole`, `FLASH-mole`: `("N_i", [0, 0, 0, 0, 1, 0, 0])`; `HEAT-duty`, `FLASH-duty`: `("U", [2, 1, -2, 0, 0, 0, 0])` — and `equation["dimension"]` equals `holdup.dimension` with index `DIMENSION_ORDER.index("time")` lowered by one.
- **M3** (vocabulary exercised; counts) `Counter(kinds) == {"algebraic": 15, "zero_holdup_balance": 2, "holdup_balance": 4}`.
- **M4** (sign convention pinned in the text, D3.3) The `statement` of each balance row equals exactly:
  - `MIX-mole`: `sum_k n_in(k),i - n_out,i = 0 for every component i`
  - `MIX-energy`: `sum_k Hdot_in(k) - Hdot_out = 0 (adiabatic: Q = 0, W = 0)`
  - `HEAT-mole`: `n_in,i - n_out,i = 0 for every component i`
  - `HEAT-duty`: `Q - (Hdot_out - Hdot_in) = 0, Q positive into the unit`
  - `FLASH-mole`: `n_in,i - n_vap,i - n_liq,i = 0 for every component i`
  - `FLASH-duty`: `Q - (Hdot_vap + Hdot_liq - Hdot_in) = 0, Q positive into the unit`
- **M5** (`zero_holdup_balance` states its reason) each such row's `reason` contains the word `junction`.

Expected new test count: A 3 + H 6 + M 5 = 14 functions (A2 and H1 may be parametrized; counts then differ — the manifest records the actual number), plus 3 new invalid-fixture parametrizations in `test_schemas_p01.py`, plus the six valid fixtures re-running through the existing round-trip tests unchanged.

### C8. Documentation rows

`schemas/README.md`: in the P01 table row for `model-manifest.schema.json`, append to the description: `; per-equation accumulation declaration (ADR 0008, migrated 2026-09-16)`.

`tests/README.md`: add a section "Added by **ADR 0008**" with one row: `test_adr_0008_transient_readiness.py` — "Pins the evaluation-boundary field sets and method arities (no time coordinate), the coverage properties of the state hash (every coordinate at full precision, order, signed zero, nothing else), and the registered accumulation classification and balance-row statements of the six SYN-001 manifests".

`docs/decision-register.md`, entry R-001, replace the parenthetical `(P-1) how a time coordinate reaches an evaluation` with `(P-1) that time never reaches an evaluation — a time-varying specification arrives as a pinned input`. No other register change.

### C9. Effect on the P02 evidence

None. `evidence/P02/507dccfaa46fa905b651ba96de65c2ea8c9f3ca1/manifest.json` records the commands run at that commit and is immutable history; no P02 artifact reads a `ModelManifest`; the P02 result JSONs, draft schemas, judge and reference file are untouched; the field sets of `EvaluationContext`, `EvaluationResult` and `JacobianResult` are unchanged; the P02-local hash convention is confirmed, not altered, by D2. `test_p02_composition.py` continues to pass on the new commit. The recorded `stdout_sha256` of `check.sh` belongs to the P02 commit and is not a target for later commits (the test count changes).

## Acceptance evidence

- `PATH=.venv/bin:$PATH ./scripts/check.sh` green (ruff, ruff format, mypy strict, pytest) with the assertions of C7 (A1–A3, H1–H6, M1–M5) and the three C5 rejections present and passing. Baseline before this ADR: 391 tests, measured 2026-09-16 on this branch.
- The six migrated manifests pass the existing round-trip test unchanged (`test_valid_fixture_round_trips_through_json`).
- The Opus session records the actual test count and the commit in `docs/progress.md`. No evidence manifest is created for an ADR; the tests are the evidence, and their node IDs may be cited by K01/K02/T04 manifests as the D07-mapping precondition.
- Review: Opus reviews this ADR for coverage, packaging and documentation (plan §1.3); it may not alter D1–D4. Process-modeling sign-off (the heater-holdup classification in particular) is a human decision recorded separately and not claimable by an agent.

## What this ADR does not establish

- It adds **no dynamic capability**: no integrator, no step controller, no event detection, no consistent re-initialization, no index analysis, no holdup state variable, no mass matrix, no time-varying `Specification` or `ProcessRevision` field, no trajectory certificate.
- It **commits the project to no transient release**. Blueprint §2.2 stands unchanged; a transient capability requires its own ADR, its own gate and its own place in the roadmap.
- It does **not** decide the PTC equation-to-variable mapping, the magnitudes of `M`, the time-scale policy or the qualification evidence (T04, D07); it fixes only which rows *may* carry `M` entries and the sign in which balance rows are written.
- It does **not** validate anything numerically: the manifests remain `declared`; the classification of D3.5 is a modelling statement about the SYN-001 units, not a measured fact.
- It does **not** fix the hash encoding (ADR 0002), replay identity (ADR 0007), the backend (ADR 0003, P03), the scaling policy, the phase-attempt contract, or the state definition `nTP-v1`.
- It does **not** relax any gate, remove any case, or change any requirement status in `docs/requirements.yaml`.

## Additive or refactor, given these rulings

Additive. With D1, the boundary `residual(x, context) → EvaluationResult`, `jacobian(x, context) → JacobianResult` is the semi-explicit form already: a transient extension forms `M (x_{n+1} − x_n)/h + F(x_{n+1}; p(t_{n+1})) = 0` in a new orchestrator from the `J` this boundary returns and an `M` whose pattern the manifests declare (D3), evaluating `p(t)` outside and re-pinning it (D4.1). No Protocol changes, no unit model is reopened for time, and no result type widens. With D2, holdup states — should a later ADR introduce them — enter as columns of `x` and are covered by every existing identity check without a rule change. With D3, every conservation row already says what it accumulates and in which sign, so the T04 mass matrix and any later integrator read the manifests rather than re-deriving each unit; the one row whose sign disagreed is fixed before it is implemented. What remains genuinely new later — an accuracy-controlled integrator, event detection with consistent re-initialization, time-varying specification schemas, trajectory-level certificates — is new machinery beside the existing boundary, not a change to it. The residual risk is not in the boundary but in the models: a `holdup_balance` energy row whose steady-state kernel is written in terms of enthalpy flows will need the `U`–`H` relation of its holdup derived at T04, which is derivation work, not refactoring, and is exactly what route (a) of blueprint §7.5 already demands.

## Open questions with recommended defaults

| ID | Question | Label | Recommended default |
| --- | --- | --- | --- |
| Q1 | Is the SYN-001 heater a holdup unit (`N_i`, `U`) or a zero-holdup exchanger? | needs the user's preference (process-modeling) | `holdup_balance`, as registered in D3.5: it shares the flash kernel and is a vessel with contents. Reversible by editing two `accumulation` blocks in `heater.yaml` and the M1/M2/M3 literals; no other file changes. |
| Q2 | Does K01 add `row_accumulation` and `parameter_ids` to `CompiledProblemMetadata` at schema promotion, or does T04 add them when it first needs them? | needs the user's preference | K01 (D4.1, D4.4): the metadata field set freezes at promotion, so adding later is a migration; adding at promotion is free. |
| Q3 | Should `constants_sha256` be renamed (for example `pinned_inputs_sha256`) when ADR 0002 replaces the encoding, since after D4.1 it covers specification values too? | needs the user's preference | Keep the name; the frozen result types echo it and a rename is a migration for a cosmetic gain. Record the widened coverage in ADR 0002. |
| Q4 | Must `holdup_balance` rows be `conditional_class: unconditional`? | needs a fact — the first `regime_conditional` balance row (T05 valve or reactor) will show whether a switching balance is ever needed | No constraint now; PTC resets its controller on an active-set restart (blueprint §7.5), so a conditional `M` pattern is already handled. |

**Q1 answered by Frank Peters, 2026-09-16: the SYN-001 heater is a holdup unit.** The recommended default stands as registered in D3.5 (`HEAT-mole` → `N_i` mol, `HEAT-duty` → `U` J) and no file changes. Recorded by the Opus session; the classification of D3.5 was already normative and is unchanged. Q1 is closed; Q2–Q4 remain open with their defaults applied and are discharged by the named packages.

## Changing this ADR

D1–D3 are part of the P01 interface freeze from the moment C1 lands. Adding any field to `EvaluationContext`, any argument to the three Protocol methods, any coordinate to `state_sha256`'s coverage, or any value to the `accumulation.kind` vocabulary; reclassifying a row in D3.5; or changing the balance-row sign of D3.3 requires a new Fable-authored ADR stating reason, affected requirements, migration impact and acceptance evidence. D4's obligations are discharged by the named packages and their tests; a package that cannot discharge one reports it in `docs/progress.md` as a blocker, never by omission.

---

## Amendment 1 — transient readiness revisited at ~37 000 lines

**Status:** Accepted 2026-09-26 by Frank Peters, with Q-A1–Q-A5 answered by their recommended defaults (A1.5); in force from that date. W4 applied 2026-09-27, after `wp/T06` merged (`d2e17d8`): header note and the R-001 register text of A1.8. *(Before acceptance: Proposed (2026-09-26); acceptance by Frank Peters at W4 (A1.6).)*  
**Author:** design lane (`architect`). **Brief:** `docs/briefs/ADR-0008-A1-transient-readiness.md`.  
**Affected packages:** T04 (documentation of its mass mapping only), T07 (J1–J3 and J5 binding, J4 and J6 recommended), and the first transient ADR and the package that introduces the first holdup-state unit model — called **TX** below; it receives a plan ID when dynamics are scheduled.

D1–D4 above stand unchanged. This amendment adds no field, no Protocol argument, no schema keyword and no accumulation kind, and it moves no digest: **no adopted provision edits a file whose bytes enter an identity** — the twelve `models/syn001/*.py` modules (each hashes itself into `implementation_artifact.artifact_hash`, e.g. `heater.py:190`), `thermo/syn001.py` (its `implementation_sha256`, `thermo/syn001.py:393`), any schema, fixture or benchmark file.

### A1.0 Rulings

| # | Candidate | Ruling | Now | Later |
| --- | --- | --- | --- | --- |
| C1 | UV closure for holdup states | Nothing widens; convention registered in text | none | X1 on TX |
| C2 | Pressure–flow semantics | Reject — already additive | none | X2 on TX |
| C3 | U in manifests, H in the PTC mass | **Adopt**; U–H constraint A1.2 | U1, U1b, U2, U2b; `mass.py` docstring; T04 F2 declined | X3 on TX |
| C4 | Steady and dynamic forms of one unit | Separate model variant sharing kernels; no factoring needed | none | X4 on TX |
| C5 | Phase logic under time stepping | Reject — already additive | none | X5 on TX |
| C6 | Result, run, job and replay records | **Adopt as constraint on T07** (J1–J3, J5 binding; J4, J6 recommended); RunManifest/replay unchanged | pointer in `interfaces-frozen.md` | J1–J6 on T07; X6 on TX |
| C7 | Time-varying specifications | Reject — additive `oneOf` branch later | none | X7 on TX |
| C8 | Differential markers | Reject the marker; row→column map later | none | X8 on TX |
| C9 | (added) Re-binding pinned inputs without recompiling | Reject — backend-internal, equally cheap later | none | X9 on TX; Q-A4 |
| C10 | (added) Non-conservation differential rows (control) | Reject — a new kind is additive, via ADR | none | X10 on the control ADR |

### A1.1 Rulings, with reasons

**C1 — no widening; a convention.** A rigid vessel's closure — find `(T, P, split)` such that `Σ_π N_i^π = N_i`, `Σ_π V^π = V`, `Σ_π H^π − P V = U`, with phase equilibrium — is an outer problem in `(T, P)` around the provider's TP flash, the same shape ADR 0011 used for PH (outer `T` around TP). It needs per-phase `h` and a per-phase molar volume, both with `T` and `P` derivatives, and nothing else. `FlashRequest` (a `StreamState` target) and `PropertyCapabilities` (an open `properties` vocabulary; no schema enumerates property ids) need no change. **X1 (TX).** (a) Property id `v`: molar volume of the requested phase at the request's state, m³ mol⁻¹, dimension `(3,0,0,0,−1,0,0)`, derivatives declared as for `h`, and thermodynamically consistent with the provider's `h` and `lnK`: per phase `∂h/∂P|_{T,x} = v − T ∂v/∂T|_{P,x}`, and `∂lnK_i/∂P|_{T,x,y} = (v̄_i^L − v̄_i^V)/(R T)` with `v̄_i` the partial molar volumes of the same `v`. TX verifies both at the registered states to a registered tolerance; an inconsistent triple still conserves `U` but misstates the pressure response. (b) `u` is **not** a provider property: a unit forms `u^π = h^π − P v^π` itself, so U–H.3 holds by construction; a provider `u` would be a second description of one quantity. (c) The UV/UVN closure lives in the unit layer (ADR 0011 pattern); a native provider UV flash is admissible only as an accelerator that reproduces it within a registered tolerance, and it needs `FlashRequest` widened to carry `U` and `V` targets — a frozen-interface ADR, not needed for (a)–(b). (d) SYN-001 declares no `v`, and adding it to `thermo/syn001.py` would move every SYN-001 identity (T06 re-registered SYN-001 after exactly such an edit, `86ddc33` on `wp/T06`). TX therefore adds `v` in a **new provider** that returns every property SYN-001 already supplies bitwise as SYN-001 does, plus `v` — never by editing `thermo/syn001.py` (X4 (i)). SYN-001's liquid `h` and its Poynting term already use one `V_MOLAR`, so (a) is attainable for it.

**C2 — already additive.** Streams carry `(n, T, P)` as flowsheet-owned free variables (`Contribution` docstring, `models/__init__.py:298-301`); no unit owns another's pressure; a specification may already target a unit parameter (`target.path` `parameters.<name>`), so a valve opening is a specifiable pinned input; Dulmage–Mendelsohn matching (`graph/matching.py`) is structural with no causality. A flow–pressure valve is a new model with a new row matched wherever structure puts it. What does assume inlet→outlet causality is steady-state machinery a pressure-driven model need not use — the causal evaluator `UnitModel.evaluate` (an obligation for SYN-001 units only; blueprint §5.1 makes it optional in general), the ADR 0009 traversal, and the unit-local DOF attribution of `graph/dof.py` ("inlets treated as known"), a diagnostic whose identity holds by construction. None is frozen. **X2 (TX).** (a) nTP-v1 has `n_i ≥ 0` (ADR 0001 D2.3), so the first pressure-driven connection is non-reversing: a non-positive driving difference gives zero flow, the `ZERO_FLOW` regime (ADR 0001 D3), as a `regime_conditional` row; bidirectional connections need a new state definition by ADR (the `state_definition` member of ports and connections makes that an enum widening). (b) A vessel's volume is a pinned parameter of the dynamic model (C4), not a port or stream quantity.

**C3 — adopt.** The manifests and the PTC mapping state different, correct facts about different vessels (A1.2 U–H.5), and one written recommendation already invites conflating them: T04 §17 F2 suggests rewriting the manifests' `holdup.quantity` as "enthalpy content at the pinned pressure (U + PV)". **That recommendation is declined.** The manifests name the physical holdup of the physical unit (`U`, J); R-032's enthalpy content is the pseudo-transient's and stands as a PTC decision. Adopted now: tests U1/U1b (every `holdup_balance` row of the unit library declares `U…` or `N…_i`, never an enthalpy) and U2/U2b (a tripwire: only the PTC path imports `orchestrator/mass.py` directly), a docstring paragraph in `mass.py`, and a sentence closing F2 in the T04 spec (A1.6). **X3 (TX):** A1.2 in full, and one positive acceptance item that states U–H.4 directly where U2 only watches the import graph: the physical `M` is built from the X8 map alone, its stored entries are exactly `1.0`, and it carries no `MASS_POLICY` and no `mass.py` type.

**C4 — a separate model variant sharing kernels, not a mode.** The one IDAES-style comparison the brief allows: a `dynamic`/`has_holdup` configuration on the steady model, steady state being "derivatives zero". Rejected. The limit of configuration under one `model_id` is the reactor's (`conversion_reactor.py:218-242`): its two configurations swap which pinned specification one algebraic row reads (`T_spec` or `Q_spec`), which already gives two `structure_sha256` values and two `model_version`s under one `model_id` and one `artifact_hash` — so "another structure" does not by itself set a mode apart. What does: (1) ownership — a dynamic form adds owned holdup columns, closure rows and a volume parameter and, pressure-driven, changes pressure semantics (openings, not outlet pressures, are specified): a different model, not a different reading of one row; (2) the certified steady product must stay byte-identical — each model module hashes its own bytes into `artifact_hash`, so a dynamic form in `heater.py` would move the steady heater's identity at every dynamic edit; (3) sharing is already free — balance shapes are in `models/rows.py`, the TP and PH kernels in `tp_state.py` and `ph_kernel.py`, modules that enter no identity, which is why X4 (ii) gates them. No factoring of the current models is needed now. **X4 (TX).** The dynamic variant has its own `model_id`, module and manifest, and builds its balance rows with the `rows.py` builders the steady model uses. TX's acceptance, across TX's merge: (i) `git diff` over the twelve steady model modules and `thermo/syn001.py` is empty (X1 (d) keeps `v` out of it); (ii) every other existing module under `src/process_runtime/models/` and `src/process_runtime/thermo/` — the shared kernels (`rows.py`, `tp_state.py`, `ph_kernel.py`, `bisection.py`, `saturation_band.py`, the package `__init__.py` files and the rest), which enter no identity — is unchanged, or every test pinning a SYN-001 digest, certificate or replay passes unmodified; (iii) at every registered converged SYN-001 state, each dynamic variant's balance rows equal the steady model's rows **bitwise** (same builder, same stream and duty columns; holdup columns do not enter `F_row`).

**C5 — already additive.** Every identity involved is per solve: `attempt_index`, `signatures`, `branch_provenance`, `root_fingerprint` and the checkpoint are members of one `SolveResult` (`orchestrator/attempts.py:187-220`); a trace opens on `plan_built` and closes on `solve_closed` (`interfaces-frozen.md` §2); the only state that may outlive a solve is the exact-property cache, whose keys are exact inputs and therefore valid across solves (blueprint §6.4). An implicit step is a solve under a new pinned-input vector (D1.3), and "a new context after a phase restart" is exactly the discipline an event-driven integrator needs. **X5 (TX).** Within a physical time step the phase signature is frozen at the step's start; the steady controller's in-solve active-set restart must not carry a step across a phase boundary (it would cross a discontinuity unlocated and void the step's error estimate). A signature change is an event that TX locates and re-initializes; the steady machinery (phase-attempt controller, homotopy, PTC) serves only consistent initialization at `t0` and after events. The event-location algorithm is TX's.

**C6 — constrain T07 now; leave the run records alone.** `Job` does not exist yet (T07 is next), and its cardinality is cheap to choose now and costly later: turning a single result member into a list breaks every HTTP/MCP client, and adding a list beside a deprecated single member leaves every client two ways to read a result. The constraint is justified by v0.1 alone — a T06 ensemble job yields one run per start (440 starts), blueprint §455 gives jobs "progress, cancellation, checkpoint/resume semantics, and artifacts" — so it sits on the steady-state side of the §2.2 line. T07 is build-led, so only what makes a later operation additive binds; the rest of the lifecycle is T07's design. **Binding on T07 from acceptance (W4): J1, J2, J3, J5. Recommended, not binding: J4, J6.**

- **J1 — outputs are a list.** A `Job` carries its outputs as an ordered array of typed artifact references (at least: artifact kind from a closed enum, artifact id, content SHA-256), possibly empty, with no maximum. No `Job` member holds exactly one solve result, run manifest, certificate or failure bundle.
- **J2 — outputs stream.** An output event appends exactly one J1 reference, in order. Any number of output events may occur, interleaved with other events, before the event that ends the job; a consumer obtains outputs only from output events and the J1 list, never from a payload of the event that ends the job.
- **J3 — operation discriminator.** A job request names its operation in a required member with a closed enum, and the request body is selected by it (one branch per value). A later trajectory operation is an added value and branch: an additive migration with no instance changes.
- **J4 (recommended) — resume is operation-owned.** Where T07 supports resume, the checkpoint is a J1-style typed reference whose kind the operation owns; the lifecycle does not assume the solver `Checkpoint` schema.
- **J5 — kinds are closed for producers, open for consumers.** T07's schemas enumerate the artifact kinds (J1) and event kinds, and a producer emits only listed values. Every consumer T07 ships (CLI, Python/HTTP/MCP bindings) ignores an output reference or event whose kind it does not know and never rejects a response for one. Whether an event ends the job is stated in a member other than `kind` (T07 names it), so a consumer that ignores an unknown kind still sees the job end. An added kind — a trajectory artifact (X6), a simulated-time progress event — is then additive for shipped clients, not only for stored documents.
- **J6 (recommended) — lifecycle details.** Events carry a `sequence` dense from 0 and strictly increasing; progress members are operation-neutral counts (`completed`, `total`, both nullable) with solver quantities in solve events, a later operation adding its own progress kind under J5; exactly one event ends a job and nothing follows it, so resuming a cancelled or failed job is a new job. T07 may decide any of these otherwise and records why.

T07's acceptance for the binding items, in its own test module, citing "ADR 0008 A1 J1–J3, J5": (a) `Job` fixtures with 0, 1 and 3 outputs validate, the last mixing kinds; (b) the lifecycle checker accepts a stream with two output events and a progress event before the event that ends the job (T07 names the kinds), and the job's output list afterwards holds the two references in order; (c) a request with an operation outside the enum is rejected, and each enum value has exactly one request branch; (d) each shipped consumer, given a job with an output of an unknown kind and a stream containing an event of an unknown kind, ignores both without error, and recognizes an unknown-kind event that ends the job through J5's member. **RunManifest, SolutionCertificate and replay: no change.** Their single `constants_sha256`, `outcome`, `verification_status` and `target_state_sha256` are one-solve claims, correctly. **X6 (TX).** A trajectory is a new artifact kind with its own schema and certificate class, listed through J1; RunManifest and SolutionCertificate members are never reinterpreted to mean a trajectory (a VERIFIED trajectory must not read as a VERIFIED steady state).

**C7 — additive later.** A third `oneOf` branch `{"required": ["schedule"], "not": {"anyOf": [{"required": ["value"]}, {"required": ["bounds"]}]}}`, with `schedule` added to `properties` (the schema has `additionalProperties: false`) and to the `not` of both existing branches (`{"required": ["value"], "not": {"anyOf": [{"required": ["bounds"]}, {"required": ["schedule"]}]}}` and its mirror for `bounds` — without it, `{value, schedule}` matches branch 1 alone and validates), leaves every existing `Specification` valid and its canonical bytes — hence every `ProcessRevision` content hash — unchanged (an absent member is not hashed); its migration report is "no instance changes". A scheduled specification pins the same target as a valued one, so DOF analysis and `model_version` are unaffected. Reserving the member now would be a member without semantics, and its semantics (time base, interpolation, discontinuities) are integrator-coupled. **X7 (TX).** The schedule is an added branch beside `value` and `bounds`; its value at a stage time reaches the compiled problem only as a pinned input (a `constants_sha256` per stage, D1.3); a schedule discontinuity is a time event the integrator steps to.

**C8 — no marker.** The differential variables are exactly the holdup columns, and each is fixed by the row that accumulates it; a per-variable marker would be a second description of that fact (the D2.3 hazard), and today it would be empty — no holdup column exists. **X8 (TX).** An explicit map `holdup_balance row id → holdup variable id`, declared by the unit in its contribution, carried by `CompiledProblemMetadata` and entering the structure identity as a new structure-document member under ADR 0002 (as D2.7's planned `sources` will), **absent — not empty — when the problem has no holdup column**, so that no steady `model_version` moves. The map is a bijection between the dynamic units' `holdup_balance` rows and their holdup columns; each column's quantity kind has the holdup's dimension; the differential set is its image; no naming convention stands in for it. A `holdup_balance` row with no holdup column in a transient problem is refused unless the run declares that instance quasi-steady — no default (D3.1's principle).

**C9 (added) — pinned-input re-binding.** The backend bakes `spec.parameters` into the CasADi graph (`compile/casadi_backend.py:326-333`); a re-bound instance is a recompile (`homotopy.rebind` + `compile_level`, `orchestrator/region.py:2377`). That is adequate for piecewise-constant schedules and homotopy levels; a continuously varying schedule would recompile per step. Moving parameters to a symbolic input is internal to the backend behind the unchanged `residual(x, context)`, costs the same later, and done now could move Jacobian patterns and digests (Q-A4). **X9 (TX).** TX measures compile against evaluation cost before choosing; within one `model_version` the Jacobian's structural pattern must not depend on pinned-input values; a backend change meant to be inert is proved bit-identical at the SYN-001 registered states, or it is a numerics change with its own ADR.

**C10 (added) — non-conservation differential rows.** A controller's integral state, a measurement lag or an actuator obeys `ds/dt = F_row` with `s` not conserved. `holdup_balance` asserts conservation (PTC gives it a mass entry; U1 restricts its holdup to amounts and internal energy), so such a row must never be declared `holdup_balance`. **X10 (control ADR).** A new kind (for example `state_equation`, with `state.symbol`, `state.dimension`, and D3.3's orientation `ds/dt = +F_row`) is an additive `oneOf` branch that changes no existing manifest or digest; "Changing this ADR" already routes it through a new ADR. At steady state its row is the algebraic condition `F_row = 0`; PTC's V2 refuses it a mass entry, correctly, until a PTC decision says otherwise.

### A1.2 The U–H constraint for future holdup units (C3; X3)

- **U–H.1 What is held.** A physical holdup unit holds the component amounts `N_i` (mol) and the internal energy `U` (J) of the contents of its control volume — the first-law energy content of any control volume, rigid or not; the manifests' declarations, unchanged.
- **U–H.2 What rigidity decides.** With boundary work the energy row is `dU/dt = Σ Ḣ_in − Σ Ḣ_out + Q + W − P dV/dt = F_energy − P dV/dt`. A **rigid** control volume (`V` pinned, m³) drops the last term, so its dynamic row is the steady model's energy row as written (D3.3) and `U` is the column its conservative form differentiates: rigidity fixes the row's form, not what is held. The five SYN-001 holdup units are rigid (Q-A1). A rigid vessel's `H = U + PV` is not a holdup: `dH/dt = F_energy + V dP/dt`, and a pressure-driven vessel's `P` is a state.
- **U–H.3 The relation.** Contents at common `(T, P)` in phases `π` with amounts `N_i^π`; `H^π(N^π, T, P)` is the provider's enthalpy of that amount of phase `π` (the function the energy row uses for a stream's enthalpy flow, applied to amounts), `V^π = (Σ_i N_i^π) v^π(T, P, x^π)`:
  `N_i = Σ_π N_i^π`,  `V = Σ_π V^π`,  `U = Σ_π H^π − P V`,  plus the TP flash's equilibrium conditions among present phases.
  `U` inherits the provider's reference convention through `H^π` (ADR 0001 D5; ADR 0011 D2's formation datum for reacting units) and is comparable only where `H` is.
- **U–H.4 Where it lives: the conservative form.** `N_i` and `U` are columns of `x` (D2.3); the balance rows are the steady rows unchanged, with `dN_i/dt = F_mole,i` and `dU/dt = F_energy`; U–H.3 is a set of algebraic rows (or a unit-layer closure implementing them) and never an entry of `M`. The physical mass matrix is the constant 0/1 matrix `M[r, c] = 1` iff `r` is a `holdup_balance` row and `c` its holdup column (X8); it contains no thermodynamics. Reason: implicit Euler on this form gives `N_{n+1} − N_n = h F_mole(x_{n+1})` and likewise for `U`, so amount and energy are conserved step by step to the nonlinear-solve tolerance; the alternative `M(x) ẋ = F` with `M = ∂holdup/∂x` over nTP columns conserves them only to truncation error. That alternative is **rejected** for physical time.
- **U–H.5 Contrast with R-032.** The T04 pseudo-vessel holds `θ ×` outflow, and its volume `V_θ = θ Σ_π V̇^π` moves with the state at pinned `P`; with boundary work, `d(U + P V_θ)/dt = F_energy`, so it accumulates `H` (T04 §6.2). Each statement is right for its own vessel and neither transfers: a rigid vessel's contents are fixed by its volume and the contents' density, not by its outflow, and a rigid vessel does not accumulate `H`. `orchestrator/mass.py` is a PTC preconditioner and never a physical mass matrix (U2 watches its direct importers; X3's positive item states U–H.4).
- **U–H.6 Several volumes; walls.** Each rigid volume is its own control volume with its own `(N_i, U, V)` — the exchanger's hot and cold sides (`U_hot`, `U_cold`). Wall thermal inertia is not in `U` ("contents"); a model that includes it is a different model and declares what it accumulates.
- **U–H.7 Incompressible and liquid-full.** If every present phase has `∂v/∂P ≡ 0` (an incompressible liquid filling `V`), the volume row does not contain `P`, and the vessel does not determine its pressure. This is SYN-001's default liquid case: its liquid molar volume is constant (`V_MOLAR`), so every liquid-full SYN-001 vessel — the heater with liquid, the exchanger's liquid sides — is in it. Determining `P` from flow–pressure rows then gives an **index-2** DAE: `Σ_i V_MOLAR,i N_i = V` constrains differential states only, and `P` enters (through the flows) only once it is differentiated. TX must not assume index 1: its structural analysis over the X8 map detects this case, and TX either reduces the index explicitly under its own ADR or refuses the configuration; it never regularizes it silently. `v` declares its `P` derivative.
- **U–H.8 Isobaric free-volume vessel — a separate model kind, not admitted here.** A control volume whose `P` is pinned and constant in time and whose `V` moves with its contents (a liquid holdup with a free level under a vented or controlled pressure: the "flow-driven" tank or CSTR) has, from U–H.2's row, `d(U + PV)/dt = F_energy` — U–H.5's algebra with a physical volume. Its conservative energy column is `H` at that `P`, with a constant 0/1 `M` and a PH closure (ADR 0011 pattern); keeping `U` would put `P ∂V/∂x` into `M`, the form U–H.4 rejects. It is a distinct kind — `P` a parameter, never a state; `V` an output of the closure, not a parameter — and U1 refuses its `H` holdup, so it is admitted only by an ADR that amends U1 and states how U1 tells the kinds apart. Whether TX's first release admits it is Q-A5.

### A1.3 Where each provision sits relative to blueprint §2.2

| Provision | What it is | Side of the line |
| --- | --- | --- |
| U1, U1b, U2, U2b; `mass.py` docstring; T04 F2 note | Tests and text on existing v0.1 artifacts | Steady-state side: keeps v0.1's PTC pseudo-holdup apart from ADR 0008's steady-state manifest metadata. Builds nothing dynamic. |
| J1–J3, J5 (binding) and J4, J6 (recommended) on T07 | Shape of a v0.1 schema not yet written | Steady-state side: required by ensembles, experiment jobs and blueprint §455; reserves no transient member. |
| X1 (a)–(b) convention | Text only | Reserved metadata: §2.2 bars building on it, not naming it. No code, no field. |
| X1 (c)–(d), X2–X10, U–H | Constraints on TX and the control ADR | Beyond the line; they bind only when a transient ADR is written, which must revise this amendment to depart from them (D4.6). |

### A1.4 What this amendment does not establish

No dynamic capability, no integrator, no event location, no index analysis, no holdup variable, no provider property, no `Job` schema (T07 designs it within J1–J3 and J5), no transient release commitment. It does not reopen R-032, ADR 0011, D1's rejection of `EvaluationContext.time`, or any registered classification. It does not claim process-modeling sign-off: that the five SYN-001 holdup units are rigid vessels is Q-A1.

### A1.5 Open questions for Frank

| ID | Question | Needs | Recommended default |
| --- | --- | --- | --- |
| Q-A1 | Are the five SYN-001 holdup units (heater, TP flash, PH flash, conversion reactor, both exchanger sides) rigid control volumes, so that their dynamic energy rows are the steady rows (U–H.2)? | Preference (process-modeling sign-off) | Yes. No file changes. A "no" for a unit moves no steady file — it still holds `U` — but its dynamic variant is then either a moving-boundary row with `−P dV/dt` (excluded by U–H.4) or the U–H.8 kind (Q-A5), settled when TX writes that variant. |
| Q-A2 | First transient release: non-reversing pressure-driven flow in nTP-v1, or bidirectional connections? | Preference (scope) | Non-reversing (X2 (a)); bidirectional needs a state-definition ADR. Either way, a liquid-full vessel with SYN-001's incompressible liquid is index 2 under pressure-driven flow (U–H.7), and TX's ADR says how it handles or refuses it. |
| Q-A3 | Are J1–J3 and J5 binding on T07 from acceptance, with J4 and J6 recommendations? | Preference (scope) | Yes: J1–J3 and J5 are what make a later operation additive, and v0.1 ensembles and blueprint §455 need J1–J2 regardless of dynamics; J4 and J6 are T07's lifecycle design. T07 has not started. |
| Q-A4 | Does the CasADi backend's Jacobian pattern depend on pinned-input values (constant folding of a zero parameter)? | Fact | No action now. TX compiles one structure with a parameter at `0.0` and at `1.0` and compares the `jacobian_pattern` digests; if they differ, X9 applies before any per-step re-binding. |
| Q-A5 | Does TX's first release admit the isobaric free-volume vessel (U–H.8)? | Preference (scope) | No: nothing needs it now, and admitting it later is one ADR amending U1, with no hashed file moving. TX's scoping ADR should weigh it: it is index 1 and avoids U–H.7's index 2 for liquid holdups. |

**Answered by Frank Peters, 2026-09-26: all five recommended defaults** — Q-A1 yes (rigid control volumes); Q-A2 non-reversing pressure-driven flow in nTP-v1; Q-A3 yes (J1–J3 and J5 binding on T07, J4 and J6 recommended); Q-A4 no action now; Q-A5 no (the isobaric free-volume vessel is not in TX's first release).

### A1.6 Work orders (build lane, on `adr/transient-readiness-2`)

None edits a hashed file (A1 preamble). Do not edit `docs/decision-register.md` until `wp/T06` has merged.

- **W1 — tests**, appended to `tests/test_adr_0008_transient_readiness.py`, each one function named as below.
  - **U1** `test_u1_physical_holdups_are_internal_energy_and_component_moles`. Discover modules with `pkgutil.walk_packages(process_runtime.models.__path__, "process_runtime.models.")`; keep those defining a `str` `MODEL_ID` and an `EQUATIONS` that is a tuple of `DeclaredEquation` or a `Mapping` whose values are such tuples (every configuration counts); a module with a `str` `MODEL_ID` whose `EQUATIONS` has neither shape is a failure, never a skip. For each `holdup_balance` row, a helper `physical_holdup_problems(pairs)` over `(row label, Holdup)` pairs reports a problem unless: holdup dimension `ENERGY` ⇒ `re.fullmatch(r"U(_[a-z]+)?", symbol)`, `quantity.startswith("internal energy of the ")` and `"enthalpy" not in quantity.lower()`; holdup dimension `MOLE` ⇒ `re.fullmatch(r"N(_[a-z]+)?_i", symbol)` and `quantity.startswith("component moles held ")`; any other dimension ⇒ a problem. Assert no problems; that every `holdup_balance` row's `dimension` equals its holdup's dimension with the time exponent lowered by one (the one physical link a 0/1 `M` relies on); and that the discovered `(model_id, equation_id)` set of `holdup_balance` rows contains the registered twelve: `tp_heater` `HEAT-mole`, `HEAT-duty`; `tp_flash` `FLASH-mole`, `FLASH-duty`; `ph_flash` `PHF-mole`, `PHF-duty`; `conversion_reactor` `RX-mole`, `RX-duty`; `heat_exchanger` `HX-mole-hot`, `HX-mole-cold`, `HX-energy-hot`, `HX-energy-cold` (all `syn001.`-prefixed). Failure messages cite ADR 0008 A1 U–H.
  - **U1b** `test_u1b_the_holdup_rule_rejects_an_enthalpy_holdup`: the helper flags `Holdup("H", "enthalpy content at the pinned pressure (U + PV)", ENERGY)` (T04 F2's wording) and `Holdup("U", "internal energy of the contents", MOLE)`, and passes `Holdup("U_shell", "internal energy of the shell-side contents", ENERGY)`.
  - **U2** `test_u2_the_pseudo_holdup_mapping_is_imported_only_by_the_ptc_path`. Parse every `*.py` under `src/process_runtime/` except `orchestrator/mass.py` with `ast`. A module imports the mapping if it has an `Import` alias `process_runtime.orchestrator.mass`; an `ImportFrom` whose absolute module (relative levels resolved against the module's own package) is `process_runtime.orchestrator.mass`, or is `process_runtime.orchestrator` with an alias `mass`; or a string `Constant` equal to `process_runtime.orchestrator.mass`. Assert the set of such modules equals exactly `{"process_runtime.orchestrator.executor", "process_runtime.orchestrator.region"}`. The message says: a new PTC-path importer is registered here; a physical-time integrator may not import it (ADR 0008 A1 U–H.5).
  - **U2b** `test_u2b_the_import_detector_sees_every_form`: the detector, applied to source strings as module `process_runtime.orchestrator.probe`, flags `from process_runtime.orchestrator.mass import RegionMass`, `from .mass import resolve_mass`, `from . import mass`, `import process_runtime.orchestrator.mass` and `importlib.import_module("process_runtime.orchestrator.mass")`, and flags neither `from process_runtime.orchestrator.massive import x` nor `from process_runtime.models import Holdup`.
  - `tests/README.md`, section "Added by **ADR 0008**": append "Amendment 1 adds U1, U1b, U2, U2b: every physical holdup in the unit library is internal energy or component amounts, never an enthalpy, and only the PTC path imports the residence-time pseudo-holdup mapping directly."
- **W2 — `src/process_runtime/orchestrator/mass.py`, module docstring only.** Its last paragraph is exactly (revised per review F2/F7; replaces the paragraph 5a61f37 added):

  ```text
  **A pseudo-holdup, not a physical one (ADR 0008 Amendment 1, U–H.5).** The vessel above is the
  pseudo-transient's: its contents are proportional to its outflow and its volume moves with the
  state at pinned pressure, which is why it accumulates `H = U + PV`. A physical vessel's energy
  content is the manifests' `U`; the SYN-001 vessels are rigid, so `U` is also what their dynamic
  energy rows accumulate (U–H.2). Nothing here is a physical mass matrix, and a physical-time
  integrator never uses this module. `tests/test_adr_0008_transient_readiness.py` (U2) pins the
  modules that import it directly: a tripwire, not a proof.
  ```
- **W3 — pointers.** In `docs/interfaces-frozen.md` §2, replace the row `| K06/T07 | ChangeSet, Job, job events, authorization capability references |` with `| K06/T07 | ChangeSet, Job, job events, authorization capability references (Job and job events: ADR 0008 Amendment 1 J1–J3 and J5 binding from its acceptance, J4 and J6 recommended) |` (revised per review F5; applied with A1.9). In `docs/derivations/T04-globalization-spec.md` §17, append to item F2: ` *Declined by ADR 0008 Amendment 1 (C3): the manifests name the physical rigid-vessel holdup `U`; the enthalpy content is this pseudo-vessel's (U–H.5).*`
- **W4 — on Frank's approval, after `wp/T06` merges.** Set this amendment's status to Accepted with the date; append "Amended by Amendment 1 (accepted <date>)" to the header's Status line; apply the register text of A1.8 to R-001.

### A1.7 Verification gates

1. `PATH=.venv/bin:$PATH ./scripts/check.sh` green; the new count is the baseline plus the U-functions (parametrization may change the count; `docs/progress.md` records both numbers).
2. Nothing hashed or registered moves: `git diff --stat main -- src/process_runtime/models src/process_runtime/thermo src/process_runtime/compile schemas tests/fixtures benchmarks evidence` is empty; the `mass.py` diff is confined to its module docstring; every test pinning a SYN-001 digest passes unmodified.
3. Falsifiability in the gate: U1b and U2b pass, so U1 and U2 are shown able to fail.
4. Review: done (`docs/reviews/ADR-0008-A1-review.md`), disposed in A1.9. Its build-lane follow-ups (F6 and the dimension assertion in U1, W1's README wording, W2's revised paragraph) land and gates 1–3 pass again; they need no second design-lane review unless they depart from the text here. Frank accepts the amendment (W4).

### A1.8 Draft R-001 register update (the build lane applies it at W4)

In the R-001 table, change `Affected packages` to `K01, K02, K03, T04, T07 (and any package introducing a unit model; the first transient package)`, and append after "**What this does not establish.**":

> **Amendment 1 (2026-09-26; normative text: ADR 0008 "Amendment 1"; brief `docs/briefs/ADR-0008-A1-transient-readiness.md`).** Re-examined at ~37 000 lines against C1–C8 and two added candidates. **Adopted now:** the manifests' energy holdup stays the internal energy `U`, and the rigid SYN-001 vessels' dynamic energy rows are their steady rows; R-032's enthalpy content is a PTC pseudo-holdup no physical-time integrator may use (tests U1, U2); T04 finding F2's proposal to relabel the manifests "enthalpy content" is declined. **Constraint on T07 (J1–J3, J5 binding; J4, J6 recommended):** job outputs are a list of typed references, output events stream before the job ends, the operation is a closed request discriminator, and consumers ignore artifact and event kinds they do not know. **Registered for the first transient package, no code now:** holdup states in `x` in conservative form, so the physical mass matrix is a constant selection and `U = Σ_π H^π − P V` is an algebraic row; a dynamic unit is a separate model id sharing kernels, with the steady modules and kernels gated unchanged; property `v`, consistent with `h` and `lnK`, in a new provider, with `u = h − P v` formed in the unit layer; non-reversing pressure-driven flow in nTP-v1, liquid-full incompressible vessels being index 2; a phase change inside a step is an event; an explicit row→holdup-column map, absent when empty. **Excluded pending an ADR amending U1:** an isobaric free-volume vessel holding `H`. **Rejected:** a `dynamic` mode on the steady models; a `schedule` member now; a differential marker on variables; the `M(x) ẋ` form for physical time. No schema, Protocol, fixture or digest changed.

### A1.9 Disposition of the review (`docs/reviews/ADR-0008-A1-review.md`)

| Finding | Disposition | Reason | Text changed |
| --- | --- | --- | --- |
| F1 | Accepted | Frank's acceptance is the acceptance step; a review cannot put J-rules in force on T07. | Status line; A1.7 gate 4 |
| F2 | Accepted (ruling) | `U` is the energy content of any control volume; rigidity fixes only that the dynamic row is the steady row. The isobaric free-volume vessel is a separate kind holding `H`, admitted only by an ADR amending U1; excluded from TX's first release by default. | U–H.1, U–H.2, U–H.8 (new); Q-A1; Q-A5 (new); W2; A1.8 |
| F3 | Accepted | The shared kernels enter no identity; only the SYN-001 pin tests catch drift in them. | C4 reason (3); X4 (ii) |
| F4 | Accepted-modified | The migration route is dropped rather than exempted: `v` goes in a new provider, so X4 (i) stays a plain empty diff and no transient feature moves a certified identity. | X1 (d); X4 (i) |
| F5 | Accepted-modified (ruling) | Binding: J1, J2 cut to "outputs stream before the job ends, never in the ending event's payload", J3, and a new reader rule J5 (unknown kinds ignored; ending stated outside `kind`). Recommended: J4 and J6 (dense `sequence`, count-only progress, exactly one ending event with nothing after). "One terminal event ends the stream" is not kept binding, because that is what forces resume-as-new-job. | C6 (J1–J6, acceptance (b), (d)); A1.0; A1.3; A1.4; Q-A3; W3 and `interfaces-frozen.md` §2; A1.8 |
| F6 | Accepted, including the optional dimension check | A new-shape `EQUATIONS` is exactly what U1 must see; the row/holdup dimension relation is the one physical link a 0/1 `M` relies on. Build lane, in the test module. | W1 (U1) |
| F7 | Accepted | U2 is a direct-import tripwire; TX gets a positive check on the physical `M`. | C3; X3; U–H.5; W1 README sentence; W2 paragraph (verbatim, for `mass.py`) |
| F8 | Accepted | The reactor already has two `model_version`s under one `model_id`; the reasons are now ownership and byte-identity. | C4 |
| F9 | Accepted | The fragment as quoted admitted `{value, schedule}`. | C7 |
| F10 | Accepted | An emitted empty member would move every SYN-001 `model_version`. | X8 |
| F11 | Accepted | (a) `v` must agree with `h` and `lnK`; (b) a native UV flash widens a frozen interface. | X1 (a), (c) |
| F12 | Accepted | Constant `V_MOLAR` makes every liquid-full SYN-001 vessel U–H.7's case, and pressure-driven flow makes it index 2. | U–H.7; Q-A2 |
