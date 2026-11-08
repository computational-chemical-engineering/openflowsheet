# RRC — build decisions (revision-region continuation, ADR 0072)

Append-only. One entry per open choice the build lane made, each in its own revertible commit:
`DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.` Design: `docs/design/RRC-revision-region-continuation.md`.

## WO-1 (2026-11-08)

- **D-1.** DECISION: When does `RRC-revision-v1` enter `APPLICATION_POLICIES` (the offered set)? → Not in WO-1; the
  policy is defined (`application/policies.py` `RRC_REVISION_V1`) but offered only once WO-3/WO-4 make its value
  executable. Reasons: (a) today's executor (`orchestrator/executor.py` `_eo_recovery`, the tuple at :892) treats any
  value other than `homotopy` / `homotopy_or_sequential_restart` as "no edge", so an offered `RRC-revision-v1` would
  silently run no recovery at all — a placeholder path (CLAUDE.md). (b) Offering it moves served content the design's
  §5.11 does not list: `get_project.solve_policies` gains an entry, so M07a's MR-7 clause
  (`tests/test_t08_b50_surface_content.py`, `V02_ADDITIONS["solve_policies"]`) needs a register entry naming
  `RRC-revision-v1`, and `tests/test_t07_w3a_revision_runs.py`, `test_t07_w5a_inspection.py` and
  `test_t07_b3_policies.py` pin the offered set. Those edits belong with the register numbering. Alternative: add it to
  `APPLICATION_POLICIES` now and edit the four tests. Reversible by: adding the one mapping entry plus those test edits
  (WO-4). Recorded for ADR 0072 C1 (a served-content move, not a digest move).
- **D-2.** DECISION: Where is a malformed `revision_continuation` (`variable_ids != ()` or `len(start_values) !=
  len(parameter_ids)`) refused? → `Continuation.__post_init__`, `ValueError`, for that type only; a
  `specification_continuation` is constructed exactly as before. Alternative: refuse inside `level_values`. Reversible
  by: moving the check.
- **D-3.** Observation, resolved by measurement (no choice made): `float(Fraction(-0.0))` is `+0.0`, so a start
  value of `-0.0` comes back as `+0.0` at λ = 0. That is the same constant: `canonical.encode_doubles` normalizes
  signed zeros, so `D` (which compares under that encoding, `continued_parameters`) and R8's level identity
  treat the two as one value (`tests/test_rrc_checks.py::test_d_compares_under_the_constants_encoding`).
- **D-4.** Not a choice, recorded for the reviewer: `tests/test_t06_f4_literals.py::test_wo1_the_literals_are_the_schema_enums`
  pinned `eo_recovery`'s enum as exactly ADR 0015's three values. The widening makes it four; the test now holds the
  Literal equal to the schema enum (its invariant, unchanged) and pins the four values in order. No other assertion
  of the file is touched, and the four edge-3 test files are not edited.

## WO-1 measurement: identity-bearing bytes (ADR 0072 C1, design §9 O2)

Measured before and after WO-1 on `wp/RRC` (`e45628fd` → WO-1):

| Bytes | Before | After |
| --- | --- | --- |
| `schemas/solve-policy.schema.json` sha256 | `e9866863…` | `f3b9f871…` (moved: the enum value and its description) |
| `schemas/attempt-context.schema.json` sha256 | `2eb2ad36…` | `78bbbc4c…` (moved: `const` → `enum`) |
| `schemas/solution-certificate.schema.json` sha256 | `dbff7aca…` | `c3571cee…` (moved: `const` → `enum`) |
| `schemas/registry.json` sha256 (a file list, no digests) | `5ffdcb29…` | unchanged |
| served MCP tool-list digest (`harness.tool_descriptions_sha256`, R-192 chain) | `455d01eb…` | unchanged |
| `policy_sha256` of `T04-W12`, `T06-revision-v2`, `T08-ptc-v1`, `T08-warm-v1` | `1f7d1172…`, `c03d7205…`, `aa0f1257…`, `32f484a1…` | unchanged |
| `benchmarks/t08/numerical_policy_v2.yaml` (`t08_numerical_policy.py --check`) | `6b449911…` | unchanged |

The old schema hashes appear only in archived per-commit RC dist lists (`evidence/*/rc/ci/rc-dist/t08-a43-dist.json`,
`release/rc-trees/*.json`), which describe those past commits and do not move. The next RC tree records the new hashes.

## WO-3 (2026-11-08)

Built on `main` (OPT's executor edits not pulled, per the work order; the merger resolves `RegionResult.final_system`).

- **D-5.** Not a free choice; the design's two sentences disagree and §5.8 decides. §5.5 says the action's tail is
  "exactly the homotopy branch's tail: `recovered_provenance(failed.bp, recovered.bp)`", but §5.8 names the recovery
  item's `initializer_source` `revision_continuation_source`, and `recovered_provenance` without
  `first_initializer_source` requires item 0's source (`traversal-G0-v1`) and raises a defect otherwise. →
  `recovered_provenance(..., first_initializer_source=REVISION_CONTINUATION_SOURCE)`, the restart's pattern.
  Alternative: none that keeps §5.8. Reversible by: dropping the keyword (then §5.8 must change).
- **D-6.** DECISION: The region refusal's message and the recorded reason → `revision_continuation_rejected(opening:
  <check>:<subject>)` in the region result; the executor records `opening(<check>:<subject>)`, e.g.
  `opening(active_set:S3.vap.A)` — G6(i)'s form. `<subject>` is `OpeningRefusal.subject` (a column or field id, R0);
  the observed float is never in the string. Alternative: §5.7's optional `[:<detail>]` omitted (`opening(active_set)`),
  which loses the column G6(i) names. Reversible by: one f-string in `region.py` and the `removeprefix` in
  `executor._revision_continuation`.
- **D-7.** DECISION: Does a passed §5.7 opening check emit `initializer_accepted` (as a passed warm-start check does)? →
  No. §5.8 lists the action's events as today's `homotopy_step` events only, and the recovery item's provenance already
  names the source; a new event would be a trace-kind use the design did not list. Alternative: emit
  `initializer_accepted(revision_continuation_source)`. Reversible by: one `run.record` in `region.py`'s new block.
- **D-8.** Structure only, isolated in `88b31d23`: the warm start's inline opening check became `_external_opening`
  (the same requirement, plus an optional `reported`), so the two external starts share one construction.
  `tests/test_t08_w4_warm_starts.py` 19 passed at that commit; F0 below. Reversible by: reverting `88b31d23` and
  inlining the check in the new block.
- **D-9.** Threading (no choice beyond §5.5's "the way `warm_start` is threaded"): the source reaches `_eo_recovery` from
  all three call sites — the revision region, the warm-started region (`_warm_start`), and SYN-001's region, where R3
  records `absent(not_revision_built)` and the restart's P3 then refuses (`test_r3_a_syn001_region_is_not_revision_built`).

## WO-4 (2026-11-08)

- **D-10.** DECISION: The member's `status` when edge 3 never consulted the source → an assembled candidate is
  `not_reached` (reason `null`); an application refusal (`absent(no_verified_ancestor)`, an A1–A3 `rejected`) is
  recorded as that refusal even though no event was emitted. §5.8 defines `not_reached` as "the source was assembled but
  edge 3 never consulted it", so a source that was never assembled keeps the lookup's or assembly's own verdict, and a
  rerun passes it back unchanged. Alternative: `not_reached` for every supplied source not consulted, the refusal
  dropped. Reversible by: the `elif` in `ContinuationSource.member`.
- **D-11.** DECISION (a reading of §5.4, for the reviewer): an instance parameter's `<name>` is the key's family before
  the first `.` — `stage_pressure.3`, `feed_stage.S-IN1`, `damkohler.B`, `nu.A` — as the binder reads a key's kind
  (`models/revision_flowsheet.py:825`, `name.split(".")[0]`). Stage pressures and duties are always indexed keys, so
  reading the key itself would make them never continuable, against §5.4's list and FQ4's plain words; the denied
  families (`feed_stage`, `nu`, `damkohler`, …) stay denied. Alternative: the whole key. Reversible by: one
  expression in `_offending_path`.
- **D-12.** DECISION: A3's order and spelling (§5.3 says "the first offending element in `element_diff` order") →
  top-level members first, in code-point order, as `not_continuable(<member>)`; then `element_diff`'s elements
  (`instances`, `connections`, `specifications`, by id), an added or removed item as `not_continuable(<member>:<id>)`,
  an unpairable member as `not_continuable(<member>)`, a changed item's first offending path (code-point order) as
  `not_continuable(<member>:<id>:<dotted path>)`. Alternative: elements before top-level members. Reversible by: the
  loop order in `not_continuable`.
- **D-13.** DECISION: A1's order and content → the certificate first: missing, unreadable, or without
  `model_version`/`constants_sha256`/`root_fingerprint.full_state_sha256`/a final `branch_provenance` signature is
  `integrity(certificate)`; then the state document must be intact (`warm_start.intact`: schema, ids, its own
  `state_sha256`) and its `state_sha256` the root's, else `integrity(state_sha256)`. A2's binder refusal is
  `source_binding(<Unbound.detail>)` (the `RevisionError` code), its identity mismatch `source_identity(model_version)`
  before `source_identity(constants_sha256)`. Alternative: state before certificate. Reversible by: `_integrity`.
- **D-14.** DECISION: The R0 projection's branch (§5.8's classes) → `record`, `selection`, `status`, `reason`,
  `continued`, `source_identity` without `full_state_sha256`, `source_signature`, `source_content_hash` (the source
  document's `content_hash` only; the body is provenance), `source_parameters` (canonical strings),
  `candidate_variable_ids` (sorted, the warm-start pattern). Provenance ids, the document body and both float digests
  are out. Alternative: carry `full_state_sha256` as a shape flag. Reversible by: the block in `run/identity.py`.
- **D-15.** DECISION: `run_revision_session` called under the new value on `revision_eo` without a source (a direct
  caller, not the job runner) writes the member as `absent(not_supplied)`, the executor's R4 reason, so the member is
  written whenever the policy names the value (§5.8). Alternative: no member without a source. Reversible by: the
  default in `run_revision_session`.
- **D-16.** D-1 executed: `RRC-revision-v1` is offered (`APPLICATION_POLICIES`). The MR-7 clause needs a register entry
  naming it, and register numbers are assigned at ADR 0072's acceptance (WO-6; OPT holds up to R-960 on its branch), so
  the entry is in the register under the draft id **R-RRC-6** (also added to ADR 0072's drafts) and
  `V02_ADDITIONS["solve_policies"] = {"RRC-revision-v1": "R-RRC-6"}`; WO-6 renumbers both. B50's get_project clause
  strips RRC's addition exactly once, as it strips M02's and S11's models. The offer also moves
  `benchmarks/t08/support_envelope.yaml`'s `solve_policies` members (T08.A20 holds the axis equal to
  `APPLICATION_POLICIES`) and so `docs/support-matrix.md` (regenerated; `t08_support_matrix.py --check` 0 problems).
  Alternative: a numbered entry now (collision risk across branches). Reversible by: reverting the offer commit.

### Served content moved by the offer (D-1/D-16), measured old → new

| Served | Before | After |
| --- | --- | --- |
| `get_project.solve_policies` (sha256 of its canonical JSON, fresh project) | `74e41d71862762ec…` | `94c6ae7c0948d464…` (one entry added) |
| `RRC-revision-v1` `policy_sha256` (new entry) | — | `ff2ff84f8172fca9cbfa86334f82f43eed1c0917d0c5c673ce6f1f73de915f19` |
| served MCP tool-list digest (`harness.tool_descriptions_sha256`) | `455d01eb…` | unchanged |
| `policy_sha256` of the four policies offered before | `1f7d1172…`, `c03d7205…`, `aa0f1257…`, `32f484a1…` | unchanged |
| `docs/support-matrix.md` (rendering of the envelope) | four policies | five (regenerated) |

### WO-4 gate runs (2026-11-08, at `3968b720`)

- G1 battery 626 passed (list in `RRC_HANDOFF.md`); F0 PASS (M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105,
  M9 35/35); edge-3 test files unchanged; `t08_support_matrix.py --check` 0 problems.
- G6 (a, c, d, e, k) and G7 (four bundles `MATCH`, 0 differences, no lookup) in `tests/test_rrc_application.py`.
- G8 measured twice in fresh processes (NET-02 store pair): `artifact_r0_sha256` `aa47dabf12e4000a…` both runs.
- Opening hash (WO-3's open point): no WO-4 case pins a column; NET-02's recovery item opens at `full_state_sha256`.

## WO-5 (2026-11-08)

Commits: `cba5e8e2` (5a: `benchmarks/rrc/cases.yaml`, pushed before any run), `b0c7d1ec` (runner), `96a7129d` (first
results), `40fba287` (runner self-contained), `b91b0ddb` (registration, results re-taken, gate tests), `395c5f56`
(L21, L-COL-9).

- **D-17.** DECISION: Where each policy runs → the target under the control, `T06-revision-v2` and `RRC-revision-v1`
  **in-process** (WO-3's candidate construction), and `RRC-revision-v1` **again in the store** (the application's own
  `find_source`/A1–A3). The control cannot run in the store (not offered, by §8.1). Selection requires both the
  in-process record and the store member to be `taken`; on every non-forced candidate the two roots' digests are equal
  (measured). Alternative: the store leg only for RRC. Reversible by: dropping `store_leg` in `run_case`.
- **D-18.** DECISION: The control keeps `policy_id = "RRC-revision-v1"`, only `eo_recovery` replaced by `"none"` (§8.1's
  words). Alternative: a distinct id. No record of the control is stored. Reversible by: `CONTROL` in the harness.
- **D-19.** DECISION: The column flowsheets bind through the production registration (`MODEL_BUILDERS` has
  `syn001.column` since I1), not the tests' `column_registered` patch (which installs the same `build_column`). Every
  column run is `VERIFIED` under it. Alternative: the patch. Reversible by: wrapping `run_case` in the patch.
- **D-20.** Reading, for the reviewer: "ends in an edge-3 trigger outcome" (Family C's control) is
  `recovery.eo_recovery_due(outcome, budget, attempts=solver_outcomes(attempts))` on the failed region result, the
  executor's own predicate.
- **D-21.** DECISION: Family F has no store leg: the forcing patch is in-process. F1, F2 are reported under all three
  policies with the forcing on for each. F2's 295 K source was `VERIFIED`; the 298 K fallback was not used.
- **D-22.** G10's `levels_compiled` counts every compile inside the action, the λ = 1 recompile of `_region` included:
  4 on a path without rejection = λ = 1 plus §5.10's three λ < 1 levels (0, 1/4, 3/4); C4 (2 rejections) compiled 5.
- **D-23.** DECISION: The harness lives in `benchmarks/rrc/run_candidates.py` and is self-contained (mypy runs strict
  over `benchmarks/`; no benchmark module imports a test module). It copies T06's `ALLOWANCE`, the twin-root reader and
  S02's flow tolerance; `test_the_harness_reads_the_registered_references_as_the_tests_do` holds each equal to the
  tests' own. A29's feed is read from the revision's pinning specifications (`SPEC-S-IN1-n-<c>`), held equal to
  `column_case_spec("M1-recycle")`'s. Alternative: a test-side harness. Reversible by: moving the module.
- **D-24.** DECISION: L21 and L-COL-9 are rewritten in WO-5 (the WO-5 brief), not WO-6, with §6's texts (L-COL-9: the
  "If G5 passes" branch). L-COL-9's pinned test stays as evidence, unedited: it asserts the column region has no
  *specification* continuation parameter, still true. The harvest note "carried verbatim" became "narrowed by RRC G5".
  Reversible by: reverting `395c5f56`.
- **D-25.** DECISION: `benchmarks/registry.yaml` is not edited. The pairs are registered where the WO-5 row puts them
  (`benchmarks/rrc/reference_values.yaml`, evidence class regression, the independent checks named and measured);
  benchmark registration is design-lane-led (CLAUDE.md). Open: whether a registry entry is wanted.
- **D-26.** Recorded: the first local 5a commit (`dbe59313`) had a YAML syntax error (unquoted `[` in keys). It was
  amended to `cba5e8e2` (keys quoted, one list item quoted; no content change) before any run and before the push.

### WO-5 measured (x86-64; `benchmarks/rrc/results-ref-x86-64.md`)

- G9: 10 candidates × 3 policies, all reported; three fresh runs (b0c7d1ec ×2, 40fba287): outcomes, iterations,
  λ-trials, checks and state digests equal.
- Selected: **N1** (G4) and **C3** (G5). Also qualifying, not registered: N2, N3, C4 (C4: 2 rejected trials, λ = 1/2
  visited). C1, C2, C5 converge first under every policy (store member `not_reached`).
- G4 (N1): control `BOUND_BLOCKED` (1 it); RRC `CONVERGED`/`VERIFIED`/`taken`, 12 it, λ 1/4, 3/4, 1, 0 rejected;
  closed-form worst ratio 0.0109 (S3.liq.C; ≤ 1); restart root 1.96e-9 scaled (≤ 1e-8).
- G5 (C3, M1-recycle split 0.2 → 0.9): control `BOUND_BLOCKED` (4 it, in the trigger set); RRC
  `CONVERGED`/`VERIFIED`/`taken`, 22 it, 0 rejected; A29 closure 2.73e-10 (≤ 1); restart root 7.8e-15 scaled.
  **L-COL-9 narrowed.**
- F1: item-0 root 4.4e-13 scaled, `D` = both column end parameters. F2: 2.0e-14 scaled.
- G2 (a)–(f): N1 (`test_rrc_edge3`), C3 (`test_rrc_candidates`). (f) holds on every taken run (7 of 7): every source
  signature in the table is all `TWO_PHASE`, so no column is pinned; WO-4's forward risk did not bite. O5: no opening
  refusal anywhere.
- G7 on the C3 bundle: `MATCH`, 0 differences. G10: recovery 0.12–0.63 s, compile ≤ 0.051 s per level (O4's 10 s far
  off), property calls 208–2070.
- **D-27.** Recorded (a G1 finding, fixed): `test_t06_f4_literals.py::test_wo1_no_committed_document_names_the_new_policy_value`
  failed on `benchmarks/rrc/cases.yaml`, whose two policy comments spelled the `eo_recovery` literals (spelled in code
  only). The two comments were reworded (`git diff cba5e8e2 -- benchmarks/rrc/cases.yaml`: two comment lines, no key,
  rule or value); `reference_values.yaml`'s `cases_sha256` follows. The edge-3 test file is not edited.
- WO-5 battery (rrc ×5, t04_homotopy, t04_edge3, t06_f4 ×7, t06_w4_registry, t07_b3_policies, s11_column_solve):
  333 passed, 1 failed (D-27); after the fix the failing file and the G9 tests: 22 passed. Support-envelope and
  surface-content tests: 48 passed. F0 PASS (M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35).

## WO-6 docs (2026-11-08)

- **D-28.** DECISION: WO-6 (this commit) is the user-guide text only: new page `docs-site/guide/revision-continuation.md`
  (nav entry in `mkdocs.yml`, one-line pointers in `guide/limitations.md` and `guide/concepts.md`). It quotes L21 and
  L-COL-9 as the support matrix now reads them, and the N1/C3 numbers from `benchmarks/rrc/results-ref-x86-64.md`.
  Not done, by the WO-6 brief (D-16: no renumbering; no binding-description edits): R-RRC-1…6 renumbering, E3c in
  `recovery-edges.yaml`, `interfaces-frozen.md`, CHANGELOG, ADR 0072 status line. Reversible by: reverting the commit.
- Checks: `mkdocs build --strict` clean; `scripts/doc_pages.py --check` up to date; `test_doc_pages.py`,
  `test_t06_f4_literals.py` 21 passed. The page does not spell the `eo_recovery` literal.

## WO-7 review fix round (2026-11-08; review `docs/reviews/RRC-review.md` on main, ed522d7c)

- **D-29 (M2).** Applied: the guide's *Declared limitations* carries the review's five sentences ("Not a superset of
  `T06-revision-v2`…") verbatim; L21's row in `benchmarks/t08/support_envelope.yaml` gains them as one sentence (and
  the guide's quoted L21 follows); `docs/support-matrix.md` re-emitted (`t08_support_matrix.py --check` 0 problems).
  E3c's note carries the same sentence in its own commit (D-34). Checks: `test_t08_w2_support_envelope.py`,
  `test_t08_w2_unsupported.py`, `test_doc_pages.py`, `test_t06_f4_literals.py`: 77 passed.
- **D-30 (S1).** Applied the review's amendment text to G2 (f) (§8.2's table) and the §5.8 certificate bullet in the
  design note copy on this branch, each marked *(Amended by the review, S1.)*. The assertion sites hash the source
  root over the recovery attempt 0's free columns (`tuple(context.column_scales)` of the attempt-0 homotopy context):
  `tests/test_rrc_edge3.py` (`opening_hash`, used by G2 and `_same_root`), `tests/test_rrc_candidates.py` (G2 on C3,
  importing `opening_hash`), and the harness, which now records `g2f_opening_equals_source_over_free_columns` beside
  the kept special case `g2f_opening_equals_source_full_state`; the G9 test asserts both (the registered signatures
  pin no column). `opening_hash` asserts `== full_state_sha256` when the free columns are the whole state.
  Nothing registered moves: `results-ref-x86-64.json`, `reference_values.yaml` and `cases.yaml` are unedited (the
  committed table, measured at 40fba287, lacks the new key; a re-take would add it). Check: `test_rrc_edge3.py` +
  `test_rrc_candidates.py` 24 passed.
- **D-31 (S2).** `tests/test_rrc_application.py::test_the_parameter_families_are_partitioned_into_continuable_and_denied`
  pins D-11's partition: `CONTINUABLE_PARAMETERS` (22) and the test's `DENIED_PARAMETERS` (7: `stage_count`,
  `feed_stage`, `nu`, `damkohler`, `T_ref`, `T_scale`, `coolant_cp`) are disjoint and together exactly the binder's
  `_PARAMETER_KINDS` keys (29). The denied set lives in the test, not in code (default deny needs no list).
  Alternative: a `DENIED_PARAMETERS` constant in `application/revision_continuation.py`. Reversible by: moving it.
- **D-32 (N1, the orchestrator's decision: do it).** §5.4 extended with the review's text: a `changed` specification
  whose `target.path` is `parameters.<key>` is continuable iff the key's family (text before the first `.`) is in
  `CONTINUABLE_PARAMETERS` — one expression in `_offending_path`, the instance rule's family test (D-11), and D-11's
  family reading is written into §5.4. Tests, one each way
  (`test_a3_a_specification_pinning_a_parameter_is_judged_by_its_family`): the column's
  `parameters.condenser_reflux_ratio` moved to a `role: fixed` specification, 2.0 → 4.0, is continuable;
  `parameters.feed_stage.S-IN1` the same way, value − 1, is `not_continuable(specifications:SPEC-S02-pinned:value)`.
  The positive half fails without the code change (checked). A3 only; no registered pair has such a specification,
  so no measured case moves. `test_rrc_application.py` 25 passed.
- **D-33 (S3).** The guide's three wording fixes: the ancestor lookup is eager (at job start on every
  `RRC-revision-v1` solve on `revision_eo`, one ancestor binding and one diff even when edge 3 never fires; only its
  use waits for the failure); "a third action" (not "a third recovery"); "the `revision_eo` route only", with the
  coupled and legacy routes recording `absent(not_supplied)` and running the restart. Also, following D-32, the
  "When it applies" list says an operating parameter counts whether written as an instance parameter or pinned by a
  fixed specification on `parameters.<name>`. `mkdocs build --strict` clean; `doc_pages.py --check` up to date.
- **D-34 (WO-6 rest: E3c).** `docs/recovery-edges.yaml` gains row E3c after E3b, in E3b's fields (design §6): trigger as
  E3a; preconditions R3–R9b in §5.5's order with their reasons; `max_count` shared with E3a/E3b; `enabled: policy-only`
  (the inventory's word for §6's "opt-in": offered by explicit id, never the default); label
  `eo_recovery:<the new value>`; failure tests G4, G5, G6; `unchanged_physics: identity_compared` by the two G2 tests
  (N1, C3). The note carries M2's sentence, the shared producers (E3a, E9), D-10's reading and O6. Without the row,
  `test_t08_w2_recovery_edges.py::test_a33_the_bijection_holds` failed on this branch (the new value was emitted by the
  code, in no row) — a full-gate failure that the WO-5 battery did not include. The test's `ROW_IDS` gains `E3c`
  (spec §5.6's seed plus E3c; T08 spec §5.6's seed table is not edited). `test_t08_w2_recovery_edges.py` 26 passed,
  the cited-node run included.
- **D-35 (WO-6 rest: freeze list).** `docs/interfaces-frozen.md` §2 gains the ADR 0072 paragraph in M1's accurate
  words (three schemas each accept one more value; no member added), with C1's measured bytes and the
  `get_project.solve_policies` entry.
- **D-36 (WO-6 rest: CHANGELOG).** `## Unreleased` gains `### RRC — revision-region continuation (ADR 0072,
  Proposed)`, after X05's entry: the policy, M2's non-superset statement, the records, E3c/L21/L-COL-9, the schemas.
