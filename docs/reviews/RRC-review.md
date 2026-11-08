# RRC review (design lane, `reviewer`) — `wp/RRC` at c6d3b9c6 against `docs/design/RRC-revision-region-continuation.md` and ADR 0072

**Verdict: sound in mechanism; no code must-fix. Two documentation must-fixes before merge (M1, M2), four should-fix
items, two items that need a decision.** The edge is a real, recorded, replayable edge 3. Its λ = 0 level is the
ancestor's certified problem, held by A2 and R8. Its opening is held to T03 §5.1 against the ancestor's reported
signature. Every refusal is typed, recorded once, and falls through to the unchanged restart. The rerun does no lookup
and no binding. Under the four existing policies every hunk is inert by construction (item 4). D-11 is sound, and
complete for the 29 registered families. One finding is not about code: the candidate table shows
`T06-revision-v2` converging on every case `RRC-revision-v1` rescues, in fewer iterations. Under FQ3's default this
policy can also fail where `T06-revision-v2` converges. The user documentation must say so (M2).

Read: design note in full; ADR 0072 branch diff; `docs/RRC_DECISIONS.md` D-1–D-28; `docs/FRANK_QUESTIONS.md` RRC
section; diffs of `executor.py`, `region.py`, `homotopy.py`, `trace.py`, `policies.py`, `runner.py`, `revision_run.py`,
`store.py`, `run/identity.py`, the three schemas, support matrix rows L21/L-COL-9; `orchestrator/revision_continuation.py`
and `application/revision_continuation.py` in full; `transactions.element_diff`/`_item_paths`; the binder's
`_PARAMETER_KINDS`, `read_parameter`, `required_kind`; `column_unit.end_entries`/`_end_specification`; the heater's
`outlet_vapor_fraction`; `tests/test_rrc_edge3.py` G2/G4/G6 and `test_rrc_application.py` A3; `benchmarks/rrc/cases.yaml`,
`results-ref-x86-64.md`; `docs-site/guide/revision-continuation.md`; `wp/OPT`'s executor/region diff. Ran (project
venv, `OMP_NUM_THREADS=1`, load ≈ 31): one import-level probe, quoted under D-11 and N1. No test, no gate (full gate
running). Every measured number below is the engineers'.

## Must fix before merge

- **M1 — FQ1's wording is not what Frank is approving.** `docs/FRANK_QUESTIONS.md:449` says the three frozen schemas
  "gain optional members". They gain no member: they widen enums (design §0). Frank's yes on a frozen interface must be
  given to accurate text. Replace with: *"FQ1: three frozen schemas each accept one more value. The solver setting
  `globalization.eo_recovery` gains the new recovery value. `continuation.type`, in the attempt context and in the
  certificate's branch provenance, changes from the single value `specification_continuation` to a choice of it or
  `revision_continuation`. No member is added, and every existing document validates unchanged."*
- **M2 — declare that the policy is not a superset of `T06-revision-v2`.** All five qualifying candidates (N1–N3, C3,
  C4) converge under `T06-revision-v2` by the restart, in 5 iterations against 10–12 (N) and 8 against 22–29 (C). No
  registered case is rescued by RRC that the restart does not rescue. Under FQ3 (one recovery per step), a continuation
  that opens its attempt and then stops (`HOMOTOPY_STALLED` at a phase wall, or any other non-converged end) ends the
  step, and the restart that `T06-revision-v2` would run is never tried. The guide says the first fact in passing and
  never says the second. Add to the guide's *Declared limitations*, and as one sentence in L21's row and in E3c's note:
  *"Not a superset of `T06-revision-v2`. On every measured case where this policy's continuation converged,
  `T06-revision-v2`'s sequential restart converged as well, in fewer iterations. A continuation that stops part-way ends
  the step, and the restart is not tried (one recovery per step). This policy can therefore fail where
  `T06-revision-v2` converges. No registered case is rescued by it that `T06-revision-v2` does not rescue."*

## Should fix

- **S1 — G2(f) and §5.8 state an equality that holds only when no column is pinned (brief item 3).** The recovery
  item's `opening_state_sha256` is `state_sha256(x0, free)` (`region.py:2254`). `free` is `region.variable_ids` minus the
  signature's pinned columns, so on a source whose final signature pins any column (a single-phase split, a dormant
  form) the hash cannot equal `full_state_sha256`. A correct implementation would then fail G2(f). §5.8's "the
  certificate's link to the source root" would also be false. Amend now; do not wait for a pinned-column case to be
  registered. **G2(f):** *"The recovery item's `opening_state_sha256` equals `state_sha256` of the source root over the
  recovery attempt 0's free columns, in the region's order. The opening's pinned columns are exactly `+0.0` in that root,
  which §5.7's check establishes. When the source signature pins no column, this is the source's `full_state_sha256`."*
  **§5.8 bullet:** *"`opening_state_sha256` is the source root's hash over attempt 0's free columns. It equals the source
  certificate's `full_state_sha256` exactly when the source's final signature pins no column. The link that holds in
  every case is the `solve-path.json` member (`source_identity`, `candidate`)."* Make the same change at the four
  assertion sites: `tests/test_rrc_edge3.py:246` and `:475`, `tests/test_rrc_candidates.py:236`, and
  `benchmarks/rrc/run_candidates.py:550`. Hash `source.state` over the homotopy context's free columns
  (`tuple(context.column_scales)`, built in `free` order). Keep `== full_state_sha256` as the special case.
- **S2 — pin D-11's partition.** Add a test that `CONTINUABLE_PARAMETERS` and the seven denied families are disjoint and
  that together they are exactly `_PARAMETER_KINDS`'s keys. The probe confirms this holds today (29 = 22 + 7). A
  family added later is then forced into an explicit register decision. Default deny already makes such an omission
  safe; the test pins §5.4's register rule.
- **S3 — guide wording** (`docs-site/guide/revision-continuation.md`).
  - "after a failed first attempt, the solve looks for…": the lookup is eager. It happens at job start on every
    `RRC-revision-v1` solve on `revision_eo`, and costs one ancestor binding and one diff even when edge 3 never fires
    (§4(l), §5.10). Only its use waits for the failure.
  - "a third recovery is tried between the existing two" contradicts "one recovery solve per step". Write "a third
    action".
  - "available on revision solves only": write `revision_eo`. On the coupled and legacy routes the value records
    `absent(not_supplied)` and runs the restart (design §1).
- **S4 — WO-6 renumbering must reach the test.** `tests/test_t08_b50_surface_content.py` pins `V02_ADDITIONS
  ["solve_policies"] = {"RRC-revision-v1": "R-RRC-6"}`. Renumber it together with the register and ADR 0072's drafts
  (D-16). Also: L-COL-9 now cites `test_s11_column_solve.py::test_a_revision_region_has_no_edge_3_continuation`, whose
  name contradicts the narrowed text (it asserts there is no *specification* continuation). Cite it with that gloss, or
  rename it in WO-6.

## Needs a decision

- **N1 — specifications whose target is `parameters.<key>` are never continuable.** S11 §10.5 lets a `role: fixed`
  specification pin an instance parameter (`column_unit.end_entries`; `required_kind` strips `parameters.`). A3's
  specification rule accepts only `_PATH_KINDS`. The probe confirms that `parameters.condenser_reflux_ratio` 2.0 → 4.0
  as a specification gives `not_continuable(specifications:X:value)`. Written as an instance parameter, the same edit is
  continuable. The gap fails safe (conservative), but FQ4's plain words promise reflux and boil-up. **I would extend
  §5.4:** *"…and the item's `target.path` is in `CONTINUABLE_SPECIFICATION_PATHS`, or is `parameters.<key>` whose
  family (its text before the first `.`) is in `CONTINUABLE_PARAMETERS`."* That is one expression, with a test each
  way (`parameters.condenser_reflux_ratio` continuable, `parameters.feed_stage.S-IN1` refused). Alternative: declare the
  limitation in the guide.
- **N2 — re-pose FQ3 with M2's evidence.** FQ3's default was set before any candidate ran. The two alternatives are both
  rejected in §4: restart first (i), which would make the continuation run almost never, and count 2 (j), which is a
  ladder. **I would keep one recovery per step for 0.4 (opt-in, with M2 declared).** I would also record that a
  registered case where the restart fails and the continuation converges is the evidence any rescue claim, and any
  revisit of FQ2 (default on), needs first.

## Rulings

1. **D-11: accepted; sound and complete for the registered families.**
   - The binder itself types a key by its text before the first `.` (`read_parameter`, `required_kind`). The column
     parses its end specifications by the same split (`<end>_<kind>[.<attribute>]`).
   - A suffix that carries structure (`.<component>`, `.<stage>`, `.<inlet>`) can change only by renaming the key.
     `_item_paths` reports a renamed key as a length-2 added/removed path, which fails `len(path) >= 3`. The rename
     also moves `parameter_ids` and so `model_version` (R5).
   - `bounds`, `nominal` and `kind` edits are refused (`path[-1]`). The integer-read parameters (`stage_count`,
     `feed_stage`, via `_integer`) are denied.
   - The allowlisted families I checked (the heater's `outlet_vapor_fraction`, the column end specifications) enter as
     row constants. Linear interpolation keeps a box-bounded value inside its bounds.
   - I found no user-editable parameter that would be continued while changing structure, stoichiometry or a model
     constant.
   - The gaps are conservative only: N1, and notes or bounds edits are refused.
2. **The other decisions.**
   - **D-5** accepted. Amend §5.5's pseudo-code tail to "`recovered_provenance(…, first_initializer_source=
     REVISION_CONTINUATION_SOURCE)`, the restart's pattern". §5.8 governs.
   - **D-6** accepted. Amend §5.7: the message is `revision_continuation_rejected(opening:<check>:<subject>)`, with
     `<subject>` mandatory and never a float.
   - **D-7** accepted.
   - **D-8** accepted. Verified by reading: `_external_opening` builds the warm start's `OpeningState`/
     `OpeningRequirement` exactly as before, and `reported` defaults to `None`.
   - **D-10** accepted. Say in §5.8 and E3c: `absent`/`rejected` with no `initializer_rejected` event means the
     application refused the source and edge 3 never fired.
   - **D-12–D-15** accepted.
   - **D-16** accepted, with S4.
3. **Opening hash: G2(f) must be amended (S1).** Amend now. The text is wrong in general, not merely untested.
4. **Inertness: no non-edge-3 path and no run under the four existing policies changes behaviour.**
   - Every behavioural hunk is guarded:
     - the new value in `_eo_recovery`;
     - `reported_signature is not None` in `region.py`;
     - `type == "revision_continuation"` in `level_values` and `__post_init__`;
     - `continues_revisions(policy)` in the runner and in `run_revision_session`;
     - the member's presence in `r0_projection`.
   - `as_context()` serialises no new field. Nothing `asdict`s a `Continuation`. `test_an_inert_value_ignores_a_supplied_source`
     pins the event-for-event equality.
   - Bytes that move: the three schema files; `get_project.solve_policies` (one entry); the support envelope and
     matrix; the four tests that pin the offered set. All are listed in D-1/D-16 and ADR 0072 C1.
   - G1 still rests on F0 and the batteries. The full gate is required (item 6).
5. **Candidate procedure: meets the pre-registration intent.**
   - `cba5e8e2` (05:24) precedes the runner (`b0c7d1ec`, 05:30) and every result.
   - `git diff dbe59313 cba5e8e2` is YAML key quoting only, 12 lines (D-26).
   - D-27's diff is two comment lines.
   - The table is §8.1's: 3 + 5 + 2 candidates, in order, with the selection rules and F2's fallback.
   - D-17 is stricter than the design (both legs `taken`, equal root digests). D-18–D-23 accepted.
   - D-24 accepted: the "If G5 passes" text, since C3 qualifies. C3 is a splitter edit inside a column region; column
     end-parameter continuation itself is mechanism evidence only (F1, forced edge). State that in L-COL-9's evidence
     note.
   - D-25 accepted: §5.2 deferred to the `T08-warm-v1` precedent, which has no `registry.yaml` entry.
6. **For `tested`, and the merge order.**
   - For `tested`:
     - CI green on x86-64 and aarch64;
     - G8 (equal `artifact_r0_sha256` and R0 projection) on N1 **and C3**, on both legs; it is now measured only on
       x86-64's NET-02 store pair;
     - G7 on aarch64 in its registered mode;
     - `evidence/RRC/<commit>/manifest.json` with the commands actually run;
     - one full `scripts/gate.sh` on the final, rebased head.
   - For the merge, additionally: Frank's yes on FQ1 (after M1), ADR 0072 accepted, and the rest of WO-6 (E3c,
     `interfaces-frozen.md`, CHANGELOG, renumbering with S4). Never `reviewed` by the build lane.
   - Order versus `wp/OPT`: no correctness constraint. OPT touches `_region`'s `BUDGET_EXHAUSTED` replace and adds
     `final_system`. RRC does not touch `_region`, and `replace(recovered, …)` carries `final_system` exactly as the
     homotopy branch does.
   - **I would merge OPT first** if both are unblocked. RRC then rebases, reruns `test_rrc_*`, OPT's
     `final_system` tests and F0, and spends its single full gate on that head.

## Notes

- R5's `ValueError` (candidate ids ≠ target ids) is reachable on a rerun of a hand-edited or corrupt bundle. That
  rerun crashes instead of reporting a replay difference. It could map to a typed rerun error.
- `_revision_continuation` omits the homotopy branch's defect guard on an empty `failed.branch_provenance`. This is
  harmless while `eo_recovery_due` implies an opened attempt.
- A3's reason path joins keys with `.`, and keys contain `.` (`parameters.feed_stage.S-IN1.value`), so the string
  cannot be parsed back. It is the design's form, and the member carries both documents. Keep it, but it freezes at
  release.
- G6's equality "except `policy_id`" is measured on NET-02, where a refused opening spent no property calls. §5.5
  restarts with the refused solve's `spent'`. Where that is non-zero, G6's counters would differ by exactly it.
- `CONTINUABLE_MEMBERS` adds `title` and `description`, which `CONTENT_HASH_EXCLUDED` already holds (harmless).

## Not established by this review

- No test or gate was run by the reviewer. aarch64 behaviour (G7, G8, O3) is unmeasured.
- Not read:
  - `run_candidates.py` beyond its G2(f) line;
  - `test_rrc_checks.py`, `test_rrc_continuation.py`, and most of `test_rrc_candidates.py` and of the G7 tests;
  - the homotopy core's behaviour on a revision continuation beyond the diff;
  - whether every other builder consumes its allowlisted families only as row constants;
  - whether the coupled and legacy routes accept `RRC-revision-v1`.
- The replay member is complete for a rerun on another machine: target binding plus member, with no store, certificate
  or source binding needed. R8 ties `source_parameters` to the recorded `constants_sha256`, but the bundle does not
  carry the ancestor's certificate, so `source_identity` is recorded, not re-certified (as for ADR 0024's member).
- Numerical verification only. The regression references are self-generated, with independent checks. No empirical
  validation and no human sign-off is claimed.
