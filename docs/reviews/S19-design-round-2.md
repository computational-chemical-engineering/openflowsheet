# S19 design round 2: rulings on items (i) to (v)

Design lane (Opus), 2026-11-20, brief `docs/briefs/S19-design-round-2.md`, worktree tip 0667f95f. Numbers: a
`codehealth scan` of the worktree (336 files, debt 2314.5, health 8.89) and scratch probes that call the pinned tool's
own functions (cce-code-health 34a30bf: `analyze`, `file_report`, `literal_drops`, `duplicated_lines`) on edited
copies. They are predictions, not gate results. Nothing committed, nothing gated.

## (v) studies/nlp/verification.py to health >= 7.0

**Ruling: merge the twin returns as a pure refactor (B with no behaviour change), then one extraction in
`_assessment`. This replaces R-W3-G3-5 (b), whose premise no longer holds.**

- Health 6.1 is a penalty of 3.9. Complex x3 = 1.5 (verify_candidate cognitive 36, `_constraint_feasibility` 18,
  `_functional` 16). Long x2 = 0.6 (verify_candidate 147, `_kkt` 71). Bumpy x2 = 1.0 (verify_candidate,
  `_assessment`). many_args x4 = 0.8. Reaching 7.0 needs a penalty of 3.0 or less. The brief left out
  `_constraint_feasibility` (debt 3.0) and `_functional` (1.0).
- Rule 15 is stale. Playbook rule 15 dates from S17. Since cce-code-health 6529f47 (S19_DECISIONS :1184, pinned
  2026-11-16, two days before R-W3-G3-5) the `literals` check lets a literal's count drop when every scope that reached
  it still reaches it. I ran `literal_drops` on the merged file: no problems, no new literals. The allowed drops are
  'not_evaluated' x2 and 'reason' x2, both still reached from verify_candidate through the helper. I rule both drops
  allowed.
- No observable output changes. Apart from the reason text, which stays at each call site, the two stop records
  match field for field. `certificate` and `state` are the fields `point.certificate` and `point.state` of a frozen
  dataclass, so a helper that reads them from `point` builds the same record. This is not a change to verifier
  behaviour, and no ADR is needed.
- Path (A), without the merge, does strictly worse. The twins carry 13.5 of the 33.7 debt and the third bump, and any
  extracted phase that contains a twin needs a sentinel return that the caller tests again. The phases are:
  - P1: re-solve and V1, with a stop;
  - P2: V2 and V4;
  - P3: assessment and V7, with a stop;
  - P4: evaluation point and phase rows, with a stop;
  - P5: V3, and V4 with phase rows;
  - P6: V5, V6 and the record.

  Only one parameter object is cohesive: V4's fixed inputs (record, declared, held, signature, zero). They are built
  once in P2 and read only by the two `_regimes` calls. An object over (values, names, checks, point, basis) would
  mix V1's result with the check accumulator. It is not admitted, and it is not needed.
- Path (C) alone reaches 7.1 by fixing two of: `_constraint_feasibility` complex, `_functional` complex, `_assessment`
  bumpy. It takes the same number of steps but cuts about a third of the debt (about 4 against 15.5) and leaves the
  duplicated records in place. Rejected.

### Work order WO-V (opus-engineer, lane G3, from the wp/S19 tip after the queued lanes merge; S19_RULES, S19-W3-common)

Refactor mode, inside verification.py; apply the S1 arithmetic rule (it is the verifier, though not on the S1 list).
0. **Pinning tests first** (build lane, own commit before the chain base: a step may not touch tests). Pin the full
   record of three stops of `verify_candidate` (`as_document()` plus `simulation_state`, `sensitivity`,
   `assessment_values`, `basis`, and `point` is the re-solve's): (a) `assessment_not_evaluable: <reason>` (a refusing
   program, or monkeypatch `verification._assessment` to return a string); (b) `phase_rows_not_evaluable: <reason>`
   (natural, or monkeypatch `verification._phase_terms`); (c) the V1 stop, `no_simulation` (no state) and
   `resolve_not_certified` (revision host, not admitted). No test, script, benchmark or other src file contains these
   texts today (grep). Falsifier: one reason prefix changed in a scratch copy fails the test (quote it); patch_noop 0.
1. **Step 1, consolidate-duplicate.** `_not_evaluated(checks, which, reason)` replaces the three loops (`names[1:]`,
   `("V3", "V5", "V6")` twice); `_stopped(values, names, checks, point, basis)` builds the twins' record, reading
   `certificate`/`state` from `point` (a `state is not None` narrowing that cannot fail there); the reason f-strings
   stay at their call sites. Predicted: verify_candidate 33.7 -> 20.2 (cognitive 28, NLOC 112, bumps 2), file debt
   49.8 -> 36.3, health 6.6.
2. **Step 2, extract-concept.** `_assessment`'s two CSR scatter loops (`d_dx` by output, `d_dp` by output and
   decision index) move verbatim, in order, into one or two private helpers; `float(...)` and
   `np.zeros(len(decision_ids))` unchanged. Predicted: `_assessment` 3.0 -> 1.0 (bumps 3 -> 1), file debt 34.3,
   **health 7.1**.
3. **Optional, G-END debt only** (keep each only if it drops >= 2 points): (3a) the V1 stop's record as
   `_unresolved(values, names, checks, point)` (no basis, as today); (3b) a frozen `_RegimeInputs` (record, declared,
   held, signature, zero) built where `record` is built today (after V2; `host.regimes(point)` before
   `host.held_system(point)`), used by both V4 calls, and the phase-row V4 block moved verbatim into
   `_phase_regimes(inputs, phase, active, state, rows)` returning (held_units, check); probe 1+3a+3b: verify_candidate
   20.2 -> 10.5; (3c) for margin, `_constraint_feasibility` cognitive 18 -> <= 15, slack arithmetic verbatim (7.6).

**Invariants:** bitwise (every record field, check order, exceptions, host call order and count); no new public
name; helpers <= 5 parameters; `_regimes`, `_not_closure_test`, `_phase_terms` signatures unchanged (tests import them).
**Acceptance:** gate PASS per step; file health >= 7.0 at the chain head on the gate's scan; nlp-marked suite as at
base (g19, g20 only); step-0 tests run explicitly at every step (the test map predates them); patch_noop 0; one
`reviewer` read of the chain before merge, ruling on the listed literal drops. Stop and report if a predicted debt is
missed by more than 0.5.
**Record (orchestrator):** log this as replacing R-W3-G3-5 (b); amend playbook rule 15 in its own `.codehealth`
commit (since 6529f47, merging twins into one helper that every former site calls passes `literals`; deleting one
copy still fails). Twins parked under rule 15 (runner.py R5 block; transactions.py `_check_array_index`/`_apply_at`)
can be merged the same way.

## (i) W5-S1 text

**Ruling: the tool's rule stands. Amend the text for the record (docs only, orchestrator).**

W5-S1 in `docs/briefs/S19-W5-ruling.md` section 6.2 (:385) is the definition that ADR 0077 points to. `w5_gate.py`
`scope_problems` admits two kinds of path that the text does not mention. While the text and the implementation
differ, a later reader of W5's evidence finds accepted steps that break W5-S1 as written.

Append a dated line under the bullet instead of rewriting it:

> "Amended 2026-11-20 (S19 design round 2, item i), as `scope_problems` implements: also admitted, when absent at B,
> (a) a new `.py` module in the directory of an admitted tier 1 file (a tier 1 split, ruling R4) and (b) a restructure
> or interface plan file that matches the plan globs `config.toml` passes; a plan file present at B is not admitted by
> the glob."

Note: (a) is wider than R4, because it admits any new module in that directory, not only one split from the admitted
file. W5 is complete, so no tool change is needed now. If a W5-style batch runs again, narrow (a). Not examined: which
paths W5 actually admitted under (a) and (b). The close records list them.

## (ii) `revision_binding.MODEL_BUILDERS`

**Ruling: keep it (the default).**
- Strike it from I-19's exception list with a dated ADR 0076 addendum (like I-21), not by editing I-19's text.
- Put the protocol in the docstring of `reading_for`. That function is in `benchmarks/m06/w27/snapshot.py:285`, not in
  src. Make it a docs-only commit outside the step gate. No evidence hashes that file.

Reasons:
- I-19's stated reason, "the legacy table's factory", is gone, because WO-N4 moved the factory to `model_builders`.
- What remains is W27's binder protocol, and it both reads and writes the module attribute:
  - snapshot.py reads `binding.MODEL_BUILDERS` (:153, :235) alongside `MODEL_BASES`, `SELECTABLE_BASES`,
    `basis_provider` and `LIST_MODELS`.
  - `restrict_to_v2_models` (:88-102) assigns `binding.MODEL_BUILDERS` and `binding.MODEL_BASES` on the installed
    binder. The v1/v2 restriction only reaches the binder because `_built_instances` reads `MODEL_BUILDERS` as its own module
    global (revision_binding.py:706).
- If that read were retargeted to `model_builders.MODEL_BUILDERS`, the restriction would silently stop applying.

What the docstring should say:
- the attributes the readings probe and read;
- that `restrict_to_v2_models` replaces two of them;
- that the binder must read both tables through its own module globals.

Do not add the name to `__all__`. That would be a public API change for no gain, and `MODEL_BASES`, which is in the
same position, is not there either. Removing any protocol attribute is a new W27 reading, not a re-export cleanup.

## (iii) cascade_solve.py duplication with column_compile / column_acceptance / column_solve

**Ruling: do it in S19 as one interface step after the current lanes merge, limited to the column_compile twins.**

Facts:
- The 87 lines are seven runs, not one block (tool's `duplicated_lines`, window 8):
  - column_compile 33: `lifted_splits` stage body 15, `zero_flow_forms` stage body 8, `compile_*` Region head 10;
  - column_acceptance 35: residual drop/swap, single-phase admissibility, the `h_in` enthalpy sum;
  - column_solve 19: the entry of `recover`.
- The smell is `dup_fraction` > 0.10 at 671 NLOC, so the file must shed at least 20 lines. Removing it brings health
  from 8.4 to 9.4. Debt does not change.
- None of the four files is in W5's R (`w5_identity.py sets --check` at HEAD) or on the frozen list. column_compile
  already imports cascade_solve, so the step adds no new import edge.
- Hidden binding: `zero_flow_forms` is a textual twin but calls a different `regime_form` in each module
  (`cascade.regime_form` returns a `RegimeForm`, `column.regime_form` a `ColumnRegimeForm`). The Region twin binds
  each module's own `lifted_splits`. Sharing whole functions would therefore be wrong.

### Work order WO-C (opus-engineer, tier S1, mode interface with a plan declaring the literal moves)

1. Add public per-stage builders to cascade_solve.py: `stage_split(unit, components, stage) -> LiftedSplit` (today's
   body, verbatim) and `zero_flow_form(unit, stage, form) -> ZeroFlowForm`.
2. Both modules' `lifted_splits` and `zero_flow_forms` keep their names, signatures and stage iteration
   (`range(1, stage_count + 1)` in cascade_solve, `equilibrium_stages()` in column_compile), and each keeps its own
   `regime_form` call at the call site. Frozen column_unit.py imports them from column_compile unchanged.
3. Leave `stage_unit` duplicated: it is under the window, and column_acceptance imports column_compile's copy.

**Prediction before the plan.** Run `duplicated_lines` over the scope and target cascade_solve's `dup_fraction` at
0.095 or below; the probe gives 64/671. Add the Region head only if that target is missed, and only where it is
verbatim.

**Invariants.**
- Equal `LiftedSplit` and `ZeroFlowForm` values in the same order. These bodies do no float arithmetic.
- F0 PASS. MCP digest unchanged. Full suite green.
- patch_noop reports 0. Run the source-reading test grep for both files.
- arch 0/0.
- One S1 `reviewer` read.

**Out of S19.** The column_acceptance twins (float arithmetic on S1 paths, with different spec and regime bindings)
and the `recover` twin. Merging twin physics is a development change that needs its own design pass.

## (iv) Batch P post-K commit 43dccc21

**Ruling: acceptable as recorded. Do not re-close K. Flag it at the S19 -> main review (the default).**

Reasons:
- The K close record is write-once by design. Deleting and re-closing it to take in a derived change would make a
  gated record mutable, which is worse than a documented post-K commit.
- 43dccc21 touches only four fixtures, written by a committed generator (`t07_schema_fixtures.py --write`, `--check`
  clean). Every changed value follows from K's registry re-emit: module paths, `descriptor_sha256`, two
  `self_sha256`, `registry_sha256`. The one exception is the masked `distribution_version`, an older staleness that
  the mask hid.
- K2 PASS at 43dccc21. Job 561 merge-checked K and 43dccc21 together before the merge. I did not re-check its PASS.

Conditions:
- The W5 evidence manifest names 43dccc21 as a post-K, generator-only commit, together with its generator check.
- The close-procedure fix already in the state file stands: run every committed generator's `--check` after the
  registry re-emit and before `close`.

Not examined: (iii)'s column_acceptance and column_solve twins in detail; the W5 close records; `_kkt`/`_regimes`
beyond their metrics.
