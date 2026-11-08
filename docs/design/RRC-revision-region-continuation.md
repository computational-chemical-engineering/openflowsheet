# RRC — Revision-region continuation: recovery edge 3 for a revision-built region, continued from its nearest verified ancestor

**Package:** RRC (release 0.4; roadmap `docs/roadmap/roadmap.md:42`; ADR 0057:33). **Lane:** design (`architect`), 2026-11-08.
**Brief:** `docs/briefs/RRC-architect.md`. **Origin:** Frank's Q30 (`docs/FRANK_QUESTIONS.md:238-239`), R-827, S11 §10.8.
**ADR:** `docs/adr/0072-RRC-revision-region-continuation.md` (Proposed). It amends ADR 0010 D1, D2, D3 and D7, ADR 0015 D1
and ADR 0024, all additively. It reverses nothing, and it supersedes R-827's "no revision region has one" only under the new
policy value.
**Status:** design. Nothing here was measured for this note. The code anchors are on `main` at `ec7e90b7`. Where a choice
turns on a number not yet known, §9 names the measurement and the default to use until it exists.

---

## 0. The decision in six lines, and the frozen-interface flag

1. **Revision continuation** is edge 3's continuation for a revision-built region: `H(x, λ) = F(x; p(λ))` with
   `p(λ) = p* + (1 − λ)(p_src − p*)`. This is ADR 0010 D2's map unchanged. Only the source of `p⁰` and of the opening differ:
   both come from the **nearest ancestor revision with a `VERIFIED` solve**, not from the failed opening.
2. The continued pinned inputs are exactly those whose values differ between that ancestor's declaration and the target's.
   The λ = 0 level is therefore **the ancestor's certified problem, bit for bit**: its `(model_version, constants_sha256)`
   equals the ancestor certificate's, and the opening is that certificate's root, in that certificate's final signature.
3. It runs only if every difference between the two revision documents is a **value change of a registered operating
   specification** (§5.4). A structural edit, a model-constant edit or a first solve has no continuation.
4. It is selected by a **new value**, `globalization.eo_recovery = "homotopy_or_revision_continuation_or_sequential_restart"`,
   offered as the application policy **`RRC-revision-v1`**. That policy is `T06-revision-v2` with only that value changed.
   The action order is: specification continuation, then revision continuation, then the ADR 0015 restart. There is still
   one recovery solve per step.
5. When its preconditions fail, the reason is recorded and the edge **falls through to the restart**, unchanged. No
   registered policy carries the new value, so no registered record moves.
6. **L21 is narrowed.** **L-COL-9 is narrowed only if G5 finds a failing-first column case.** L20 and L24 are unchanged:
   the continuation is natural-parameter, it never changes the active set, and it follows no folds.

**Frozen-interface flag (needs Frank's approval before merge, as ADR 0015's did):** this design makes three additive enum
widenings.
- `solve-policy.schema.json`: `globalization.eo_recovery` gains the new value.
- `attempt-context.schema.json`: `continuation.type` changes from a `const` to `["specification_continuation", "revision_continuation"]`.
- `solution-certificate.schema.json`: `branch_provenance[].continuation.type` changes the same way.

Every existing document validates unchanged. No request schema, response schema or `ApiError` code changes. Nor does
`eo_recovery_unsupported` change: refusals of this action are recorded in the trace and in `solve-path.json`, which has
no schema.

---

## 1. Problem and scope

A revision plan is one `solve_eo` region over every row-authoring unit (`orchestrator/revision.py:354-425`). It starts from
`traversal-G0-v1`, which is two sequential passes from dormant tears. When its Newton solve ends in an edge-3 trigger
(ADR 0010 D3 as amended by ADR 0044 D1), `continuation_parameter` returns `None`, because a revision region has no
*promoted* specification row (`revision.py:400-405`, S11.A24′). The edge then records
`unsupported(no_continuation_parameter)`. Under `homotopy_or_sequential_restart`, the default on `revision_eo`, the
edge runs the 8-pass restart instead (`executor.py:871-1046`, ADR 0015).

**In scope:**
- a continuation for revision regions, with its source, selection, preconditions, action order, records, replay and cost;
- the policy value and the offered policy;
- the support-matrix consequences;
- the work orders and gates.

**Out of scope:**
- pseudo-arclength and fold following (§4 row (h) shows it is not the only sound form);
- a continuation for the *first* solve of a revision, and for any revision without a verified ancestor;
- continuation as an *initializer*. This covers a traversal that itself fails (`INITIALIZATION_FAILED`), which is not an
  edge-3 trigger;
- an explicit, request-named source (the ADR 0070 X02 form);
- the trigger set (ADR 0010 D3 / ADR 0044 D1, unchanged);
- the count (still 1);
- sweeps and studies (R-183 stands: they never name this policy);
- OPT, X02, X12;
- the `revision_coupled` and `legacy_eo` routes. On these the new value is accepted, but no source is supplied, so the edge
  behaves as `homotopy_or_sequential_restart` plus one recorded refusal event.

---

## 2. The facts this design rests on

1. **Where the residual lives at a revision start.** The traversal solves every unit at its target specifications, given
   the unit's inlets. Every specification row `±v − p` (`graph/trace.py:315`) is therefore satisfied at `x⁰`, and so is
   every unit's model row. The residual at `x⁰` sits only on the torn closure. On NET-02, *measured* in T06-F4 §2, only
   the splitter's recycle rows are non-zero. So the A02 construction, `p⁰ = x⁰[v]` on a row `v − p`, gives `p⁰ = p*`
   on every revision specification row. That is an empty path. **No re-binding of pinned inputs makes the traversal start
   a root.** The only pinned input that touches the closure residual is a splitter's fraction. Making `x⁰` a root needs
   an offset on the torn connection, which is the rejected tear-connection homotopy.
2. **A physical easy endpoint therefore has to be a known root.** For a revision there is one: a `VERIFIED` solve of an
   ancestor revision with the same declaration structure. ADR 0024 already selects such states and records them
   replayably (`application/store.py:1083`, `latest_verified_solution`). The orchestrator never reads the store.
3. **Identity is a pure function of the declaration.** `model_version = label@structure_sha256(variable_ids, equation_ids,
   parameter_ids, row_accumulation)` and `constants_sha256 = H(parameters, parameter_ids)`
   (`orchestrator/execution.py:172-189`). Two revisions with equal `model_version` have the same pinned-input ids. Re-binding
   every differing id to the ancestor's value therefore reproduces the ancestor's `constants_sha256` exactly. This is
   checkable, not assumed (§5.5 R8).
4. **Revision values are pinned inputs.** A specification is a row `±v − p` with a parameter-dependent constant, because
   ADR 0008 D1.3 forbids a literal. Unit parameters are typed by name (`models/revision_flowsheet.py:252-295`,
   `_PARAMETER_KINDS`, `_PATH_KINDS`). Some of them are discrete or model constants: `stage_count`, `feed_stage`, `nu`,
   `damkohler`, `T_ref`, `T_scale`, `coolant_cp`.
5. **The ancestor's certificate carries what the opening needs.** It has `root_fingerprint.{model_version,
   constants_sha256, full_state_sha256}` and `branch_provenance[-1].signature`, the converged attempt's `[unit, regime]`
   pairs (`schemas/solution-certificate.schema.json`). `solution-state.json` carries `variable_ids`, `variables` and
   `state_sha256` only (`run/solution_state.py:42-61`).
6. **The homotopy machinery is generic in `p⁰`.**
   - `level_values` forms `p⁰` from `opening[v]` (`homotopy.py:107-125`); this is the one place that changes.
   - `_homotopy` compiles each λ < 1 level by `rebind` and checks that `model_version` is unchanged (`region.py:2636-2750`).
   - `RecoveryStart` hands `solve_region` a settled opening and its regimes (`region.py:438-447`). The recovery path skips
     §6.2 and the opening fixed point (`region.py:1951-1957`).
7. **M9 holds no `orchestrator/` or `application/` file**, *measured*: `corpus_identity.frozen_modules()` returns 35
   files and none is under those directories. `models/syn001/column_solve.py:1189` and `cascade_solve.py:642` build a
   `Continuation`. They are not edited: the new field has a default.

---

## 3. Constraints and invariants

- **ADR 0010 D2 holds level for level.**
  - Each λ < 1 level is a re-binding of pinned inputs, by id, of the *target's* declaration. It has the target's
    `model_version` and its own `constants_sha256`.
  - λ = 1 is the target compiled instance itself.
  - λ is an exact dyadic, and each level's values are formed in exact rationals and rounded once.
  - The signature is frozen for the whole path, so the active set never changes. A phase boundary on the path ends
    `HOMOTOPY_STALLED`, bracketed.
  - No λ < 1 level is target-verified.
  - The verifier judges only the λ = 1 state, against the target declaration, unchanged.
- **Additional invariant:** the λ = 0 level's `(model_version, constants_sha256)` equals the source certificate's. Its
  opening state is the certificate's root (`state_sha256` = `full_state_sha256`), in the certificate's final signature.
- **R-031's lesson holds:** never from the failed end state. **R-016 holds:** the verifier shares nothing with the source.
- **Determinism.**
  - Every decision on this edge is an id comparison, a canonical-encoding comparison of document constants, a digest
    equality or a typed outcome. None is a float threshold.
  - Selection is by revision-graph depth, then job ordinal.
- **Inertness.** Under every existing `eo_recovery` value, the code path and every record are byte-identical (F0 M1–M9).
  The four edge-3 test files are not edited.
- **Typed outcomes.** No placeholder success. A refusal is recorded with its reason, and the restart (or its own
  `unsupported`) follows.
- **Count.** One recovery *region solve* per step. A refusal before any attempt opens is a precondition failure, not a
  solve. This follows ADR 0015 P4 (decided by running the initializer) and ADR 0024 ("the caller takes the next source").

---

## 4. Decision and the alternatives rejected

**Chosen: revision continuation from the nearest verified ancestor, as edge 3's action between the specification
continuation and the restart.** This is the blueprint's own order. §7.4 ranks compatible warm starts (source 2) above
upstream propagation (source 4), and §7.7 says "try another globalization" after an EO globalization failure. The design
follows the branch from a certified root of a real neighbouring problem to the target, which ADR 0031 D5 assigned to
continuation ("following a branch is continuation's job"). It is **not** warm-start chaining (R-183): nothing starts Newton
at the target from the neighbour, and nothing runs in a sweep. Nor does it rest on speed, which is what X02 measured
(D-32: 4 = 4); it rests on rescue.

| | Rejected | Why (first principles first, then precedent) |
| --- | --- | --- |
| (a) | Specification rows on revision regions (R-827) | §2.1: every revision specification row is satisfied at the traversal start, so `p⁰ = p*` and the path is empty. It would also change every revision plan and enter `executor.py:670`. |
| (b) | Tear-connection homotopy (cut and blend) | The λ < 1 levels need extra columns and rows (a consumer-side copy of the torn stream), so the level is no re-binding of the target declaration: a new `model_version`, an endpoint mapping that is a projection, and a new identity ADR (ADR 0010 D2, ADR 0008 D1.2(ii)/D1.3; ADR 0015 alternatives). Its added coverage over the restart is first solves of recycles, which the restart already rescues (20 of 20, T06-F4 §2). |
| (c) | Split-fraction (recycle-closure) continuation from `r = 0` | Coverage: splitter-closed loops only (T06-F4 §4(a)). New reason: at `r = 0` the recycle stream is exactly zero, so the λ = 0 root sits in a `ZERO_FLOW`/dormant signature, and leaving it changes the active set, which ADR 0010 D2 forbids. The form is unable by construction, not merely narrow. |
| (d) | Global Newton homotopy `F − (1 − λ)F(x⁰)` | ADR 0010:104, unchanged: the levels are not physical, and the offset lies outside pinned-input identity. |
| (e) | Heuristic "easy" values (low purity, low recycle, a cooler heater) from the traversal start | No root is known at λ = 0, so the λ = 0 corrector from `x⁰` is the same failing Newton. The easy values would be constants tuned per unit kind on the cases they are meant to rescue (selection after the fact). |
| (f) | Continuing only the continuable differences and leaving the others at the target | The λ = 0 level is then not the ancestor's problem, so no root is known there. |
| (g) | Any `VERIFIED` state of the same `model_version` (siblings, other lineages), nearest by a parameter distance | The selection would need a float metric, which is not an R0 decision. Revision history is the registered, deterministic relation (ADR 0024 D2). |
| (h) | Pseudo-arclength | Not the only sound form: natural-parameter continuation is sound on every path without a fold, and a fold or phase boundary ends typed and bracketed (L20). Deferred by the blueprint (`:289`) and the T04 spec (`:34`). |
| (i) | Restart before continuation | Under count 1, continuation would run only where the restart's preconditions fail, which is acyclic regions, and those converge from the traversal. L-COL-9 and L21 would not be lifted in practice. |
| (j) | Continuation, then the restart (count 2) | A recovery ladder (ADR 0015 alternatives; `eo_recovery_max_count` is the literal 1). Frank question FQ3; default no. |
| (k) | Re-solving the ancestor inside the edge when no stored state exists | A nested solve with its own failures inside a recovery, and no certificate to anchor λ = 0. |
| (l) | Lazy lookup through a store callback at edge time | It saves one lookup per solve but gives a second store-reading seam. The eager lookup mirrors ADR 0024 exactly. |
| (m) | Folding into `homotopy` or `homotopy_or_sequential_restart` | It silently changes a registered value's meaning (ADR 0010 D1). |
| (n) | Making the new value the revision route's default | It moves every revision run's identity, and it makes a rescued result depend on project history by default. Frank question FQ2; default no. |

---

## 5. The design

### 5.1 The map, the levels and identity (ADR 0010 D2, a second applicability)

**The continued set.** Let `S` be the source declaration (the ancestor's spec, bound from its revision document) and `T`
the target's. `D = [pid for pid in T.parameter_ids if enc(S.parameters[pid]) != enc(T.parameters[pid])]`, in
`T.parameter_ids` order, where `enc` is the per-value float encoding `canonical.constants_sha256` hashes. Then:
- `Continuation(type="revision_continuation", parameter_ids=tuple(D), variable_ids=(), start_values=tuple(S.parameters[p] for p in D))`;
- `p_j(λ) = fl(p_j* + (1 − λ)(p_j^src − p_j*))` in `Fraction`, rounded once, for λ < 1. λ = 1 is the target instance, never
  re-bound;
- λ = 0 gives `p_src` exactly, so the λ = 0 level's `declaration_identity` equals `(S.model_version, S.constants_sha256)`.

**`homotopy.py` changes (the only numerics edit):**
- `Continuation` gains `start_values: tuple[float, ...] = ()`, and `type` widens to
  `Literal["specification_continuation", "revision_continuation"]`.
- `level_values` dispatches on `type`:
  - for `revision_continuation`, `start = Fraction(continuation.start_values[i])`, and `opening` is not read;
  - for `specification_continuation`, the code is byte-identical to today's.
- A `revision_continuation` with `variable_ids != ()` or `len(start_values) != len(parameter_ids)` is a `ValueError`.

**Controller, corrector, budgets.** These are unchanged (`HomotopyPolicy` defaults: Δλ₀ = 1/4, ×2 / ÷2, Δλ_min = 1/1024,
corrector ≤ 10 iterations, ≤ 64 λ-trials). A λ = 0 corrector failure is `HOMOTOPY_STALLED`, as in D2. No new constant.

### 5.2 The policy value and the offered policy

- `GlobalizationPolicy.eo_recovery` (`orchestrator/trace.py:633`) gains
  `"homotopy_or_revision_continuation_or_sequential_restart"`. It is R0, and never the default.
- `application/policies.py`:
  `RRC_REVISION_V1 = replace(T06_REVISION_V2, policy_id="RRC-revision-v1", globalization=replace(T06_REVISION_V2.globalization, eo_recovery=<new value>))`,
  added to `APPLICATION_POLICIES`. It is not added to `ROUTE_DEFAULT_POLICY`. It is registered in `benchmarks/registry.yaml`
  and `REGISTERED_POLICY_IDS` exactly as the T08 precedent did for `T08-warm-v1`; WO-5 follows whatever that precedent is.
- Under the new value the application supplies a source (§5.3) only on `revision_eo`.

### 5.3 Selection and assembly (application layer)

**Selection `store-nearest-verified-ancestor-v1` (run only, never on rerun).**
1. Walk `parent_revision` from the target. The target itself is excluded.
2. For each ancestor in order (parent first), call `Store.latest_verified_solution(connection, (ancestor,),
   excluding=<this job>)`. ADR 0024's predicate is unchanged: an ended solve job, a `solution_state` artifact, and a
   `VERIFIED` verdict.
3. The **first hit wins and nothing further is searched**, as in ADR 0024 (§B1).
4. If no ancestor has a hit, the result is `absent("no_verified_ancestor")`.

The lookup runs at the call site that performs ADR 0024's lookup, iff the resolved policy's `eo_recovery` is the new value
and the route is `revision_eo`.

**Assembly `assemble(source_document, state_document, certificate_fields, target_binding)` (run and rerun alike).** The
first failure decides, and the result is a refusal with `status = "rejected"`:
- **A1 integrity:** `state_sha256(variables over variable_ids)` must equal both the document's `state_sha256` and
  `certificate.root_fingerprint.full_state_sha256`. Reason: `integrity(state_sha256)`. A missing certificate artifact is
  `integrity(certificate)`.
- **A2 source identity** (run only; on rerun the verdict and `source_parameters` are taken from the record):
  - bind `source_document` with the target binding's binder configuration;
  - `declaration_identity(spec_src)` must equal the certificate's `(model_version, constants_sha256)`, else
    `source_identity(<field>)`;
  - a `RevisionError` gives `source_binding(<code>)`.
- **A3 continuable:** every difference is allowed by §5.4. Reason: `not_continuable(<member>:<id>:<dotted path>)`, naming
  the first offending element in `element_diff` order (member, id, path in code-point order).

**The result:** `RevisionContinuationCandidate(job_id, revision_id, model_version, constants_sha256, full_state_sha256,
signature, state, parameters)`. It is frozen and lives in `orchestrator/revision_continuation.py`.
- `signature` is `certificate.branch_provenance[-1].signature` as `tuple[(unit, regime)]`, in recorded order.
- `state` is the solution-state values.
- `parameters` is `spec_src.parameters` (the full vector).

A refusal is `RevisionContinuationRefusal(status: Literal["absent", "rejected"], reason: str)`.

### 5.4 Continuable differences (registered allowlist, default deny)

Diff the source document against the target document with `semantic_diff` and `element_diff`
(`application/transactions.py:237`).

- **Top level.** A changed member must be in `CONTENT_HASH_EXCLUDED ∪ {"title", "description"}`; any other member is
  `not_continuable(<member>)`.
- **`connections`.** Any element is not continuable.
- **`specifications`.** A `changed` element is allowed iff every path is one of `("value",)`, `("unit",)` or
  `("meaning",)`, and the item's `target.path` is in `CONTINUABLE_SPECIFICATION_PATHS` = {`state.n`, `state.T`, `state.P`,
  `outlet.T`, `outlet.P`, `duty.Q`}, or is `parameters.<key>` whose family (its text before the first `.`) is in
  `CONTINUABLE_PARAMETERS` (S11 §10.5 lets a `role: fixed` specification pin an instance parameter; it is judged by the
  instance rule's family test, D-11). That set is all of `_PATH_KINDS`. `added` and `removed` are not continuable.
  *(Extended by the review, N1.)*
- **Family.** An instance parameter's `<name>` below, and a `parameters.<key>` target's, is the key's family: its text
  before the first `.` (`stage_pressure.3`, `feed_stage.S-IN1`), as the binder types a key (D-11).
- **`instances`.** A `changed` element is allowed iff every path has the form `("parameters", <name>, …, <field>)`, with
  `<field>` in {`value`, `unit`, `meaning`} and `<name>` in `CONTINUABLE_PARAMETERS`:
  - `pressure_drop`, `split_fraction`, `efficiency`, `outlet_vapor_fraction`, `conversion`, `split`;
  - `coolant_flow`, `T_coolant`;
  - `stage_pressure`, `stage_duty`;
  - `condenser_reflux_ratio`, `condenser_distillate_rate`, `condenser_duty`, `condenser_purity`, `condenser_recovery`,
    `condenser_temperature`;
  - `reboiler_boilup_ratio`, `reboiler_bottoms_rate`, `reboiler_duty`, `reboiler_purity`, `reboiler_recovery`,
    `reboiler_temperature`.
- **Not continuable** (discrete, or a model constant whose interpolation is not an operating point): `stage_count`,
  `feed_stage`, `nu`, `damkohler`, `T_ref`, `T_scale`, `coolant_cp`. Also every path under `model`, `role`, `kind`,
  `dimension` or a target, and every added or removed item.
- A parameter registered later is not continuable until it is added here, by a register entry.

Both sets are R0 constants in `application/revision_continuation.py`. A3 is what separates `feed_stage` 5 → 4 (which may
leave `model_version` unchanged) from `split_fraction` 0.2 → 0.9.

### 5.5 The edge-3 dispatcher (`orchestrator/executor.py`)

`execute_plan` gains a keyword `revision_continuation: RevisionContinuationCandidate | RevisionContinuationRefusal | None = None`.
- It is read only when the policy names the new value; otherwise it is ignored and never recorded, as `warm_start` is.
- It is threaded to `_eo_recovery` the way `warm_start` is threaded.
- `StepResult` gains `revision_continuation: RevisionContinuationRecord | None = None`, and `PlanResult` exposes the first
  non-`None` one, the `warm_start` pattern (`executor.py:129-150`).

```
_eo_recovery(..., candidate):
    if eo_recovery not in {homotopy, homotopy_or_sequential_restart, NEW} or not RegionResult: return as today
    if not eo_recovery_due(...): return as today
    continuation = continuation_parameter(...)                 # unchanged
    if continuation is not None: <today's homotopy branch, byte-identical>
    if eo_recovery == homotopy_or_sequential_restart: return _sequential_restart(...)   # unchanged
    if eo_recovery == NEW: return _revision_continuation(..., candidate)
    return unsupported(no_continuation_parameter)               # unchanged

_revision_continuation(step, region, flowsheet, spec, policy, run, spent, state, following, candidate):
    R3  not isinstance(flowsheet, RevisionFlowsheet)       -> refusal absent("not_revision_built")
    R4  candidate is None                                  -> refusal absent("not_supplied")
        candidate is a RevisionContinuationRefusal         -> that refusal
    R5..R9a  found = revision_continuation(candidate, spec, region)     # pure, §5.6
        a refusal                                          -> that refusal
    R9b recovered, spent', state', _ = _region(region, dict(candidate.state), flowsheet, spec, policy, run,
              spent, following, None,
              RecoveryStart(state=candidate.state,
                            regimes={u: r for (u, r) in candidate.signature if u in region.signature_units},
                            continuation=found,
                            initializer_source=REVISION_CONTINUATION_SOURCE,
                            reported_signature=candidate.signature))
        if recovered.outcome == "INITIALIZATION_FAILED" and not recovered.attempts:
            spent = spent'; keep the pre-call `state`; refusal rejected("opening(<check>:<subject>)")
            # <check>:<subject> read from the result's `revision_continuation_rejected(opening:<check>:<subject>)` (§5.7)
        else:
            <the homotopy branch's tail, with the restart's provenance pattern>:
            recovered_provenance(failed.bp, recovered.bp, first_initializer_source=REVISION_CONTINUATION_SOURCE),
            # (Amended by the review, D-5: §5.8 names the recovery item's source, so the keyword is required.)
            checkpoint rule, replace(step, outcome, iterations, message, detail, eo_recovery="taken",
            recovered_from=failed, revision_continuation=Record(status="taken", reason=None, D, start_values))
            return
    on refusal: _reject_initializer(run, spent, f"revision_continuation_{status}: {reason}")   # one event
                step = replace(step, revision_continuation=Record(status, reason))
                return _sequential_restart(step, region, flowsheet, spec, policy, run, spent, state, following)
```

The restart's preconditions P3 to P5, its records and its `unsupported` reasons are untouched. P5 reads
`failed.branch_provenance`, which is still the original failed solve's.

### 5.6 The pure checks (`orchestrator/revision_continuation.py`, new; no I/O)

`revision_continuation(candidate, spec, region) -> Continuation | RevisionContinuationRefusal`. The first failure decides.
- **R5:** `candidate.model_version == declaration_identity(spec)[0]`, else `rejected("model_version")`. With equal
  `model_version`, `set(candidate.parameters) == set(spec.parameter_ids)`. A violation is a defect: `ValueError`.
- **R6:** `D` (§5.1) is non-empty, else `rejected("no_changed_specification")`. With `D` empty, the ancestor is a verified
  root of the target itself, which is a warm start (ADR 0024's policy), not a path.
- **R8:** `declaration_identity(rebind(spec, level_values(cont, spec.parameters, {}, Fraction(0))))` equals
  `(candidate.model_version, candidate.constants_sha256)`, else `rejected("level_identity")`.
- **R9a:** every `u` in `region.signature_units` appears in `candidate.signature`, else
  `rejected("opening(coverage:<first missing unit in signature_units order>)")`.

### 5.7 The region-solve seam (`orchestrator/region.py`)

- `RecoveryStart` gains `reported_signature: AttemptSignature | None = None`. `None` is today's recovery, byte-identical.
- With a value:
  - attempt 0 opens at `recovery.state` with `recovery.regimes`, as today's recovery does: no §6.2 projection, no kernel
    opening, no opening fixed point. The dormancy items come from the state by `_items`, as today;
  - **before the homotopy core**, attempt 0's opening is held to `check_opening` (`phase_contract.py:292`), built exactly
    as the compatible-warm-start check builds it (`region.py:2157`), with `reported = recovery.reported_signature`.
    This checks coverage, the active-set pinned columns at exactly `+0.0`, the lower bounds on free columns, and that
    the reported signature equals the opening (regimes plus dormancy items);
  - a refusal ends the solve `INITIALIZATION_FAILED` with message `revision_continuation_rejected(opening:<check>:<subject>)`.
    `<subject>` is mandatory: the refusal's column, unit or field id (`OpeningRefusal.subject`, R0), never a float.
    *(Amended by the review, D-6.)*
    No attempt is opened, and it emits exactly the events a refused warm-start opening emits.
- The identity pair in `OpeningState` is set equal to the requirement's. Identity was established by R5 and R8. The
  requirement's `constants_sha256` is the target's, as for the warm start.
- `_homotopy` is unchanged except that `level_values` now dispatches (§5.1). `opening_state` and `x0` are the source state.
- Scales are those `solve_region` computes for this opening, as for any recovery. The ancestor's state is never re-scaled
  by the ancestor's policy.

### 5.8 Records

**Trace (existing kinds only).**
- On a refusal: one `initializer_rejected` event with message `revision_continuation_<status>: <reason>`, emitted before the
  restart's events.
- On the action: today's `homotopy_step` events, with `level_constants_sha256`, `lambda_value` and `delta_lambda`.
- The step's `region_closed` carries `eo_recovery = taken` or `unsupported`, as today. When it is `unsupported`, the reason
  is the restart's.

**Attempt context.** `core = homotopy` and `continuation = {type: "revision_continuation", parameter_ids: D}`.

**Certificate.**
- The recovery's first `branch_provenance` item has:
  - `core = homotopy` and `opening_source = eo_recovery_start`;
  - `initializer_source = "revision_continuation_source"`, a free string;
  - `opening_state_sha256`, the source root's hash over attempt 0's free columns. It equals the source certificate's
    `full_state_sha256` exactly when the source's final signature pins no column. The link that holds in every case is
    the `solve-path.json` member (`source_identity`, `candidate`). *(Amended by the review, S1.)*;
  - `continuation = {type: "revision_continuation", parameter_ids, lambda_levels, lambda_reached, rejected_trials}`.
- Verification is unchanged (R-035, `verify_revision`).

**Checkpoints.** λ < 1 is `partial`, with `continuation_lambda`, as in ADR 0010 D7.4.

**`solve-path.json` member `revision_continuation`.** It is written iff the policy names the new value on `revision_eo`,
whether or not edge 3 fired, as ADR 0024 D4 does.

| Field | Content | Class |
| --- | --- | --- |
| `record` | `"RRC-revision-continuation-v1"` | R0 |
| `selection` | `"store-nearest-verified-ancestor-v1"` | R0 |
| `status` | `absent` \| `rejected` \| `not_reached` \| `taken` | R0 |
| `reason` | the R0 string from §5.3, §5.5 or §5.6, or `null` | R0 |
| `continued` | `{parameter_ids, start_values}` when `taken`, else `null`; `start_values` are canonical float strings of document constants | R0 |
| `source_job_id`, `source_revision_id` | ids | provenance |
| `source_identity` | `{model_version, constants_sha256}` (R0) and `full_state_sha256` (digest, shape only) | as stated |
| `source_signature` | `[[unit, regime], …]` | R0 |
| `source_document` | the stored ancestor revision. Its `content_hash` is R0; the body is provenance | as stated |
| `source_parameters` | `{pid: canonical float string}` of `spec_src` | R0 |
| `candidate` | the `solution-state` document | values R1/R2; digest shape only |

`status = not_reached` means the source was assembled but edge 3 never consulted it. `status` `absent` or `rejected` with
no `initializer_rejected` event in the trace means the application refused the source (no verified ancestor, or an A1–A3
refusal) and edge 3 never fired; the refusal is recorded as that refusal (D-10). *(Amended by the review.)*
`run.identity.r0_projection` gains one
branch for this member, as ADR 0024 did for `warm_start`. A bundle without the member is unaffected.

### 5.9 Replay

`replay --rerun` takes the member (`_recorded_revision_continuation`, the `_recorded_warm_start` pattern,
`revision_run.py:981`). It does no lookup and no source binding.
- It rebuilds the candidate from `source_parameters`, `source_identity`, `source_signature` and `candidate`.
- It re-runs A1 and A3 and the pure checks R5 to R9b, and passes the result to `execute_plan`.
- A recorded `absent`, or a recorded A2 refusal, is passed as that refusal.

The rerun's member must equal the recorded member under its R0 projection; otherwise that is a replay difference. A bundle
replays alone, as ADR 0024 D5 requires.

### 5.10 Cost (blueprint §7.7)

- **At solve start:** at most depth-many indexed store queries, one JSON read for the state and one for the certificate,
  one binding of the ancestor document, and one `element_diff`. All of this is unmetered, as initializers are.
- **At the edge:**
  - R5 to R9a are hashing only;
  - the action is one region solve of at most 64 λ-trials × 10 corrector iterations;
  - λ < 1 levels are compiled once each and cached per λ. A path with no rejection compiles three levels: λ = 0, 1/4
    and 3/4;
  - property calls are metered against the plan's remaining budget, as for the homotopy today.
- **Bundle:** one more state vector and one revision document, a few tens of kB for a column flowsheet.

### 5.11 Which registered records move: none

- The new branch is reachable only when `eo_recovery` is the new value. No registered policy, fixture, bundle or test
  carries that value, so `_eo_recovery`'s other branches are byte-identical.
- `level_values` for `specification_continuation`, and every `RecoveryStart(...)` built today (no `reported_signature`),
  run today's code.
- The schema changes accept every existing document (a `const` becomes an enum containing it). So M8's outcomes stand,
  and fixtures regenerate byte-identically.
- Runs recorded `unsupported(no_continuation_parameter)` or restarted under `homotopy_or_sequential_restart` keep their
  policy, and so keep their records.
- What *does* change bytes: the three schema files, `schemas/registry.json`'s entries for them if it digests them, and
  possibly a served MCP digest. WO-1 measures and lists these in ADR 0072 C1 before Frank's approval (§9 O2).

### 5.12 Seams, file by file

| File | Change | WO |
| --- | --- | --- |
| `orchestrator/homotopy.py` | `Continuation.start_values`, `type` widened, `level_values` dispatch | 1 |
| `orchestrator/trace.py` | `eo_recovery` Literal, docstring | 1 |
| `schemas/solve-policy`, `attempt-context`, `solution-certificate` `.schema.json` | the three widenings | 1 |
| `application/policies.py` | `RRC_REVISION_V1` | 1 |
| `orchestrator/revision_continuation.py` (new) | candidate, refusal and record types; constants; `revision_continuation()` | 2 |
| `orchestrator/region.py` | `RecoveryStart.reported_signature`; the attempt-0 check | 3 |
| `orchestrator/executor.py` | keyword, `_revision_continuation`, `StepResult` and `PlanResult` fields | 3 |
| `application/revision_continuation.py` (new) | selection, `assemble`, allowlists, member document | 4 |
| `application/revision_run.py`, the job worker's lookup site, `run` identity | threading, member, R0 branch, rerun | 4 |
| `benchmarks/rrc/` (new), `tests/test_rrc_*.py` (new) | cases and gates | 2–5 |
| `docs/support-matrix.md`, `benchmarks/t08/support_envelope.yaml`, `docs/recovery-edges.yaml` (E3c), `docs/interfaces-frozen.md`, register, CHANGELOG | docs | 6 |

---

## 6. Support matrix and register consequences

- **L21** becomes: "Edge 3's continuation exists for a region with a promoted specification (specification
  continuation). Under `RRC-revision-v1`, it also exists for a revision region whose nearest verified ancestor has the same
  declaration and differs only in registered operating values (revision continuation, ADR 0072). Everywhere else edge 3 is
  the sequential restart or `unsupported(…)`. Neither continuation changes the active set." Checks: G4, G6.
- **L-COL-9.** The test-pinned clause "(no revision region has one)" is false under the new policy, and G1 keeps the
  existing L-COL-9 test unchanged and passing.
  - **If G5 passes**, the text becomes: "In a flowsheet a column region has edge-3 continuation only under
    `RRC-revision-v1`, from a verified ancestor that differs only in operating values. A first solve, a structural edit
    (stage count, feed stage, a changed end-specification choice) and the default policy have none. The unit's own
    `evaluate` keeps S02's standalone path…". Checks: G5, F1.
  - **If G5 finds no failing-first column case**, L-COL-9 keeps its text with "under the registered policies" inserted,
    and F1 is cited as mechanism evidence only. The limitation is not claimed lifted.
- **New register entries** are drafted in ADR 0072 and numbered at acceptance. R-827 gets a forward pointer; it is not
  rewritten.
- **`recovery-edges.yaml` gains E3c**, in E3b's fields: trigger as E3a; preconditions R3 to R9b in §5.5's order; `max_count`
  "1 per region step (shared with E3a/E3b)"; `enabled` opt-in; failure tests G4, G5, G6.

---

## 7. Work orders (dependency order; one commit each, naming RRC; branch `wp/RRC`; each ≤ ~150k context)

| WO | Lane, model | Content | Acceptance |
| --- | --- | --- | --- |
| **1** | build, Opus | §5.1's `homotopy.py` edit; §5.2's Literal and policy; the three schema widenings with fixture regeneration. Measure what bytes move (schema registry, served MCP digest) and write the list into ADR 0072 C1. | `tests/test_rrc_continuation.py::test_level_values_*`: λ = 0 returns `start_values` bitwise; λ = 1/2 equals `float(Fraction(p*) + Fraction(1, 2)*(Fraction(p_src) − Fraction(p*)))` bitwise; λ = 1 raises; a `specification_continuation` gives today's values on HOM-01's inputs. The four edge-3 test files pass unedited. `corpus_identity.py --check` PASS. M8 unchanged. |
| **2** | build, Opus | `orchestrator/revision_continuation.py`: types, constants (`REVISION_CONTINUATION_SOURCE`, the record id, the selection id) and `revision_continuation()` (R5, R6, R8, R9a). | Unit tests, one per reason, on hand-built candidates over NET-02's binding. One more test: R8 passes iff `D` is complete (drop one id from `D`, get `level_identity`). ruff and mypy clean. |
| **3** | build, Opus | §5.5 and §5.7 in `executor.py` and `region.py`, with the keyword threaded through `execute_plan`. Rebase on OPT's executor changes first if they have landed (§9 O7). | `tests/test_rrc_edge3.py`, with candidates built **in-process** (solve the ancestor revision under `T06-revision-v2`, take its result and certificate; no store): G2, G3 and G6(b, f–j). The fall-through equality of G6. The four edge-3 files unedited and passing. F0 PASS. |
| **4** | build, Opus | `application/revision_continuation.py` (selection, `assemble`, §5.4); threading at the warm-start lookup site; the member; the R0 branch; the rerun. | `tests/test_rrc_application.py`: G6(a, c, d, e, k); G7 on an in-store NET-02 pair; a bundle without the member gives a byte-identical R0 projection (F0 M3, M7). |
| **5** | build, Opus | **5a** (a commit *before any run*): transcribe §8.1's candidate table into `benchmarks/rrc/cases.yaml`. **5b**: run all candidates under the three policies; register the selected pairs in `benchmarks/rrc/reference_values.yaml`, labelled regression with the independent checks named; add the gate tests. | G4, G5, F1, F2, G8, G9, G10. Evidence manifest `evidence/RRC/<commit>/manifest.json` with status `tested` if they pass. |
| **6** | build, Sonnet | Docs: §6's support-matrix and envelope rows (as G5 decides), E3c, `interfaces-frozen.md`, the CHANGELOG, ADR 0072's status line (conditions met; never `reviewed`), register numbering. | Doc generators' `--check` pass; ruff on any script touched. |

Then the full `scripts/gate.sh` runs once before merge (TRS2 load rule), CI must be green on x86-64 and aarch64, and one
design-lane `reviewer` pass covers WO-1 to WO-5 against this note.

---

## 8. Verification gates

### 8.1 Pre-registered candidates (fixed now; WO-5a transcribes before running anything)

**Family N** (target: the registered NET-02 revision, unchanged except that `parent_revision` names the source).
- Sources differ from NET-02 only in the recycle splitter's `split_fraction`, in this order:
  - **N1** 0.5;
  - **N2** 0.8;
  - **N3** 0.9.
- A source is eligible iff it is `VERIFIED` under `T06-revision-v2`.
- The registered pair is the first eligible Ni whose target under `RRC-revision-v1` is `CONVERGED` with `VERIFIED`,
  `eo_recovery = taken` and member `status = taken`.

**Family C** (source: the registered `benchmarks/s11/flowsheets/M1-recycle.json`, `U-SPLIT.split_fraction = 0.2`).
- Targets differ only as listed:
  - **C1** split 0.5;
  - **C2** split 0.8;
  - **C3** split 0.9;
  - **C4** split 0.95;
  - **C5** `condenser_reflux_ratio` 4.0 and `reboiler_boilup_ratio` 3.0, split 0.2.
- The registered L-COL-9 case is the first Ci that meets both conditions:
  - under the **control** (`RRC-revision-v1` with `eo_recovery = "none"`, built in the test and not offered), it ends in
    an edge-3 trigger outcome;
  - under `RRC-revision-v1`, it ends `CONVERGED`, `VERIFIED` and `taken`.

**Forced-edge mechanism cases.** Edge 3 is forced after a `CONVERGED` item 0 by patching `eo_recovery_due` to return
`True`, as in the S01 A17 precedent. Item 0's root is then an independent expectation.
- **F1:** M1-recycle → C5's change (column end parameters).
- **F2:** registered NET-03 (a flash-liquid loop) with a source whose first feed `state.T` is 5 K lower; if that source is
  not `VERIFIED`, 2 K lower.

Every candidate's outcomes under the control, `T06-revision-v2` and `RRC-revision-v1` are reported, whatever they are
(G9).

### 8.2 Gates

| Gate | Invariant | Measured how | Criterion |
| --- | --- | --- | --- |
| **G1** inertness | Nothing registered moves | `scripts/corpus_identity.py --check`; `git diff main --` on the four edge-3 test files; `tests/test_t06_w4_registry.py`, `test_t07_b3_policies.py`; schema fixture regeneration | M1–M9 PASS; empty diff, and the files pass; every registered `policy_sha256` unchanged; fixtures byte-identical |
| **G2** level identity | ADR 0010 D2 and §3 | On the G4 run's trace and records | (a) λ = 0 level identity = the source certificate's `(model_version, constants_sha256)`. (b) Every λ < 1 level's parameter vector differs from the target's only at `D`. (c) λ = 1 identity = the failed solve's = the certificate's = NET-02's registered identity. (d) Every λ is a dyadic `p/q` string. (e) The λ = 1/2 values are bitwise as in WO-1, if λ = 1/2 is visited. (f) The recovery item's `opening_state_sha256` equals `state_sha256` of the source root over the recovery attempt 0's free columns, in the region's order. The opening's pinned columns are exactly `+0.0` in that root, which §5.7's check establishes. When the source signature pins no column, this is the source's `full_state_sha256`. *(Amended by the review, S1.)* |
| **G3** controller | Rollback, halving, stall | A stub corrector in `test_rrc_edge3.py` | One rejection at λ = 1/4: the next trial is at λ = 1/8 from the λ = 0 state, bitwise. All rejections: `HOMOTOPY_STALLED` with bracket width ≤ 2/1024 and no certificate. |
| **G4** revision rescue | A registered failing-first revision converges through the new edge | Family N's pair, under the control and under `RRC-revision-v1` | Control `BOUND_BLOCKED` (NET-02's registered edge-off outcome). RRC `CONVERGED` and `VERIFIED`. Errors against `ref.closed_form.corpus_cases.SYN-001-T06-NET02` within T06's registered NET-02 tolerances. ‖x_RRC − x_restart‖∞, scaled by the region's `Scaling`, ≤ 1e-8, where x_restart is NET-02's root under `T06-revision-v2`. |
| **G5** column rescue (L-COL-9) | As G4, for a column region | Family C's selected case | Control in the trigger set; RRC `CONVERGED` and `VERIFIED`; S11.A29's per-component closure (feed = distillate + purge) within A29's flow tolerance. If no Ci qualifies, G5 is reported **not met** and §6's fallback text applies. |
| **F1, F2** mechanism | Continuation reaches the same root as an independent start | Forced edge | `CONVERGED` and `VERIFIED`; scaled ‖x_RRC − x_item0‖∞ ≤ 1e-8; F1's `D` contains both column end parameters. |
| **G6** typed refusals | Every reason is recorded, then the restart runs unchanged | One constructed case per reason | (a) `absent:no_verified_ancestor`. (b) `absent:not_supplied`. (c) `rejected:integrity(state_sha256)`. (d) `rejected:not_continuable(instances:S02:parameters.stage_count.value)`. (e) `not_continuable(connections:…)`. (f) `model_version`. (g) `no_changed_specification`. (h) `level_identity`. (i) `opening(active_set:<column>)`: one split's recorded regime is tampered, `TWO_PHASE` → `LIQUID`, so its vapour columns are not `+0.0`. (j) `opening(coverage:<unit>)`. (k) `not_continuable(…damkohler…)` on the T08 kinetic CSTR. For each: exactly one `initializer_rejected` event with the R0 message. After that event, the step's records equal the same case's under `T06-revision-v2` except for `policy_id`. The member's `status` and `reason` are as listed. |
| **G7** replay | Replay from the bundle alone | `replay --rerun` on the G4 and G5 bundles and on a G6(a) bundle | `MATCH`, differences = 0 on x86-64; on aarch64 the platform's registered mode passes |
| **G8** determinism | R0 is reproducible | G4 twice in fresh processes; both CI legs | Equal `artifact_r0_sha256`; equal R0 projection (λ sequence, `D`, outcomes, counts) on x86-64 and aarch64 |
| **G9** honesty | No cherry-picking | The manifest's table | All 3 + 5 + 2 candidates, all three policies, every outcome, iterations and λ-trials |
| **G10** cost | Recorded, not gated | Timers in the G4, G5 and F1 runs | Wall time of the recovery, levels compiled, compile seconds per level, property calls |

A miss on G4, G5 (when a case qualifies), F1, F2, G2 or G8 is a **finding**, reported to the design lane. It is not a
tolerance to loosen. Two `VERIFIED` roots that differ by more than 1e-8 scaled mean two branches. That is reported as
such, and the gate stays failed.

---

## 9. Risks and open questions

| # | Question | Kind | Default until settled |
| --- | --- | --- | --- |
| O1 | Does any Family C candidate fail first under the control? | fact (WO-5) | §6's two branches are fixed in advance. Without a case, L-COL-9 is not claimed lifted. |
| O2 | Which identity-bearing bytes move with the three schema widenings (`schemas/registry.json`, the served MCP tool-list digest of R-192)? | fact (WO-1) | Listed in ADR 0072 C1 and carried into FQ1. If a served digest moves, the V17 re-take follows the R-192 procedure at the next release, not in RRC. |
| O3 | Is the λ sequence R0-identical on aarch64? | fact (G8) | As for T04's homotopy. If not, stop and escalate to the design lane; do not record per-architecture values. |
| O4 | Compile seconds per λ-level on the column case | fact (G10) | No threshold. Above 10 s per level, log a follow-up (re-binding inside the compiled instance); RRC is not blocked. |
| O5 | Does a stored solution state hold the signature's pinned columns at exactly `+0.0`? | fact (G4, G5) | The opening check refuses typed, then the restart runs. If a registered case trips it, escalate. A projection rule is a design decision, not the build lane's. |
| O6 | Provider drift between the ancestor's run and now | fact | No provider-identity check. The λ = 0 corrector is the check: if it fails, `HOMOTOPY_STALLED` at `λ_reached = 0`. Stated in the E3c note. |
| O7 | Concurrent OPT edits to `executor.py`/`region.py` | fact (repo state) | WO-3 rebases on `main` after OPT's executor work lands. WO-1, 2 and 4 do not wait. |
| O8 | A revision whose traversal fails (`INITIALIZATION_FAILED`) gets no continuation | preference (scope) | Out of RRC. Recorded as a clause of L21; a later "continuation as initializer source" package, if Frank wants it. |
| O9 | An explicit source (`job_id`, the X02 form) | preference | Not in RRC. |
| FQ1 | Approve the three schema widenings | Frank (frozen interfaces) | Build on `wp/RRC`; merge waits for "yes". |
| FQ2 | Default on, or by name only? | Frank (preference) | By name only (`RRC-revision-v1`) in 0.4. |
| FQ3 | Restart after a stalled continuation? | Frank (preference) | No; one recovery per step. |
| FQ4 | Which edits may be continued? | Frank (scope) | §5.4's allowlist. `damkohler` and the other model constants are excluded. |

**Frank questions, in plain words** (for `docs/FRANK_QUESTIONS.md`):

- **FQ1.** The new recovery needs three small additions to frozen record formats. The solver setting "what to do when
  Newton fails" gets one new allowed value. The field "kind of continuation" gets one new allowed value,
  `revision_continuation`, in the solver's attempt records and in the solution certificate. Nothing that exists today
  changes or stops validating. May we make them? *Default: we build it on its branch and merge only after your yes.*
- **FQ2.** Should "if the solve fails, continue from the last verified solution of an earlier revision" become the normal
  behaviour for every revision solve, or be used only when a solve asks for the policy `RRC-revision-v1`? Making it normal
  changes the recorded identity of every future revision run. It also means a rescued answer can depend on the project's
  history. *Default: only when asked for, in 0.4.*
- **FQ3.** The continuation can stop part-way, for example when a phase appears or vanishes between the old and the new
  settings. When it does, should the solver then also try the existing eight-pass restart, which would be two recovery
  attempts for one failure? *Default: no. One recovery per failure, as now. The stop is reported with how far along it
  got.*
- **FQ4.** Which edits may be continued? *Default:* operating values only:
  - feed flows, temperatures and pressures;
  - outlet temperatures and pressures, duties and pressure drops;
  - split fractions, efficiencies, vapour fractions and conversions;
  - the column's reflux, boil-up, distillate, bottoms, purity, recovery and temperature specifications, and stage pressures
    and duties;
  - coolant flow and temperature.

  Not continued: stage counts, feed stages, stoichiometry, kinetic constants (Damköhler number, reference and scale
  temperatures), coolant heat capacity, and any change of model, connection or component list.

**Least certain.**
- (1) Whether any column candidate fails first (O1).
- (2) Whether NET-02's path from `split_fraction` 0.5 stays two-phase in the heater. Its β is only 0.015 at the target, so
  a stall at a phase boundary is possible. N2 and N3 exist for that reason.
- (3) O5.
