# T08 review 2 — the harvest (W2.2), the recovery-edge inventory (W2.4), rulings on the envelope

**Reviewer:** design lane (`reviewer`), 2026-10-01. **Branch:** `wp/T08` at `2f47b29`. **Brief:**
`docs/briefs/T08-review-2.md`. **Built against:** release spec §5.2–§5.7, §6.3, §8.1, §9; `docs/T08_DECISIONS.md`
(entries "Phase 2a" and "W2.4 landed"); CLAUDE.md rule 5 (no placeholder success paths).

**What I ran.** `pytest tests/test_t08_w2_recovery_edges.py -k "not cited_nodes"`: 17 passed, 5 failed (A33 on
E1, E5, E10, E11, E12, as reported). `scripts/t08_support_matrix.py --check`: 0 problems. I read the manifest
text of all 123 P, 41 S and 2 B items and of all 90 E items, truncated to 300 characters each. Probes were
code reads only. I did not run the cited-nodes subprocess test or the full suite.

## Verdict

**Not ready. There are three must-fix (M) findings.** The harvest is honest and mostly well filed. No P item
hides a correctness claim. Four items are misfiled, and one compound E item omits a user-facing part. The
inventory's mechanism is sound and its mutation tests are real. But the code scan misses a reachable,
default-on fallback, the solve-side `legacy_eo` route. Two code paths are rule-5 defects that must be fixed
before the RC: U05 (Q1) and the CLI `replay --rerun` fallback (Q11). All are cheap to fix. The rulings below
are written so that the build lane can transcribe them.

## A. Findings

### Must fix

- **M1. The inventory misses the solve-side route fallback.** `application/revision_run.py:202–206`,
  `select_route`, works like this: when the revision binder refuses, the document goes to `legacy_eo` (a
  different binder, so a different `model_version`), and the refusal is recorded as the route's reason. That
  makes it a recovery edge in §5.6's sense: one formulation is insufficient, so another runs on the same
  document. It is reached under the default policy by every revision the revision binder refuses with
  `specification_role_unsupported` (T07 S-G). E11 inventories only `validate()`'s twin. The scan (§A.2 of
  the test) reads no `Route(...)` producer, so the "bijection holds" claim is false for this edge. Its guard
  already exists (`legacy_admission`, C0–C5, `tests/test_t07_r7_admission.py`). Fix: Ruling 5 (E11).
- **M2. U05: `validate(task="optimization")` returns `READY_FOR_OPTIMIZATION`.**
  (`application/validation.py:293`; reached through `local.py:369–385`.) Blueprint §(validation states)
  defines that status as "requires a valid optimization formulation". v0.1 checks none and has no optimizer,
  so the status is a placeholder success. Fix: Ruling 1.
- **M3. CLI `replay --rerun` compares the bundle with another problem.** `application/cli.py:183–186`
  reruns `registered_case(run_id) or SYN-001-nominal`. This is worse than the brief states. The CLI never
  reads `revision.json`, so **every revision-built bundle** (job ids are not registered cases) is compared
  with nominal's rerun. The result is a structural `MISMATCH` (`run/replay.py:242`) for a correct bundle,
  and exit 1. The application's `reproduce_bundle` (`revision_run.py:666–740`) already does this correctly.
  Fix: Ruling 11.

### Should fix

- **S1. W2.2: T06 `limitations[12]` (compound, E → L04, L03) omits Q27.** Q27 says there is no concurrent
  verification within one process. `verify/regularity.py:84–90` saves, seeds and restores numpy's *global*
  generator around `onenormest`. Two `verify` calls in threads of one process can therefore interleave.
  The estimate, `rcond₁` and the bound then move, and a regularity verdict near `TAU_ILL` can flip. Jobs run
  in spawn processes (`jobs/executor.py:19`) and are unaffected. A Python-API user is affected. Fix: new
  row L37, added to the item's pointers (§C).
- **S2. W2.2: K02 `limitations[6]` (P, "no sensitivity capability … (unlisted)") is user-facing.** Blueprint
  §(studies) promises sensitivities, sweeps and estimation. v0.1 offers none, and the matrix says nothing.
  Fix: reclassify it E → U05, amended to name the studies (Ruling 1).
- **S3. W2.2: open defects that were handed on are filed P.** These are T03 `limitations[16]`, T05
  `limitations[12]` and T05b `limitations[14]`, plus T05b `limitations[13]`'s N-W5/N-W6. None is user-facing
  (each is unreachable or harmless in v0.1). But P means "stays in its manifest", and that drops an open
  defect from every list. Fix: new backlog id B10 (§C, Ruling 4's rule "a handed-on defect is never P").
- **S4. W2.2: T07 `limitations[2]` S → `doc:…/REVIEW.json` is a vacuous pointer, and T07
  `limitations[3]` hides an open RC obligation as P.** REVIEW.json existed, with `pending`, when the
  limitation was written. A21 checks only that the file exists, so it would pass with the review undone.
  Fix: Ruling 13 (a test asserting the statuses), with both items S → that test.
- **S5. W2.2: L22 is too broad.** It joins an evidence-scope statement with a performance non-claim. These
  are two different user questions. Fix: split L22 into L22 and L36 (Ruling 4).
- **S6. W2.4: the event-producer scan fails open.** `_Scan.visit_Call` adds an `event:` label only for a
  *constant* argument equal to an event kind. A producer that passes the kind through a local
  (`kind = "restart"; trace.record(kind=kind)`) or through a module constant is silently invisible. The test
  docstring's "a producer the scan cannot read fails the bijection" holds only for `_KernelAnswer` and
  `_refused`. No producer is missed today: the forwarding helpers `executor.py:191` and `:378` take `kind`
  as a parameter, and their call sites pass constants. Fix: a `kind=` argument (or `_initializer_event`'s
  third argument) that is neither a string constant nor a parameter of the enclosing function yields
  `<unreadable at …>`. If modules outside `orchestrator/`, `numerics/` and `verify/` produce false positives
  (admission, store, runner, certificates use unrelated `kind`s), restrict this rule to modules that import
  `process_runtime.orchestrator.trace`. Add one mutation case to `test_a33_the_scan_finds_a_new_producer`.
- **S7. W2.4: E1/E2 `enabled: default` is false for every supported interface.** See Ruling 8.
- **S8. W2.4: E4's `guard` injects `model_version` only.** `constants_sha256` is guarded but never injected.
  Fix: Ruling 6.
- **S9. W2.4: E7's certificate evidence certifies the wrong producer.** CH-UP-DP's `tp` is the
  leaving-`ZERO_FLOW` flash, not the failure branch (`region.py:639–643`). Fix: Ruling 7.

### Notes

- N1. T01 `limitations[7]` (P) says structural results are generic, not numerical rank. It is user-facing
  for `inspect_structure` readers → E → new L38.
- N2. T05b `limitations[15]` (E → L07; `onenormest` seeded from the global RNG) is closed by
  `ONENORMEST_SEED` (T06 §8.1, R-069) → S → the test that pins `ONENORMEST_SEED`. Find it with
  `grep -rn ONENORMEST_SEED tests/`.
- N3. T03 `limitations[6]` (S → b41) has an E part, "continuation history across runs does not exist" →
  class E → [L10], under Ruling 4's compound rule.
- N4. T05b `limitations[13]` carries Q9 (an E part; L02) and N-W5/N-W6 (B parts) → class E → [L02, B10].
  For this, Ruling 4 lets an E item also carry B pointers.
- N5. K03 `limitations[0]`, the "confirm each of the four" query: parts (2) and (4) are closed by the cited
  checks. Part (1) is moot, because K04 factorizes its own Jacobian (K04 `limitations[6]`). Part (3), K03's
  own assertions without tests, is process. S stands. Put this in the note.
- N6. E2's refusal values (`merge_into_eo: unsupported`, `merge_unsupported`, executor.py:185–186) are
  outside the bijection, while E3's `eo_recovery_unsupported` values are inside it. Either add a
  `merge_unsupported:` family or record the asymmetry in the header. Not blocking.
- N7. The inventory header claims that the `fallbacks` entries "carry exactly these values". That is a
  comment, not a test. Not blocking.
- N8. A21 requires a harvest S pointer to a test node to be *collected* only. A skipped closing test would
  pass A21 (check.sh catches a failing one). Not blocking.
- N9. P03 `checks[17]`: P is acceptable until T08.A30 passes. It then becomes S → `check:T08.A30`.

## B. Rulings

Every "exact text" below is an amendment. Head the amendment block in the spec with
`*(amended 2026-10-01, T08 review 2)*`.

**1. U05 — a rule-5 defect, fixed in code.** *Rejected alternative:* amend U05 to accept a structure-only
`READY_FOR_OPTIMIZATION`. That contradicts the blueprint's definition, and it is a ready status that no
operation can consume. *Code:* in `LocalApplication.validate`, immediately after the `task not in TASKS`
check, `task == "optimization"` → `self._refuse("unsupported", "task_unsupported(optimization)",
operation="validate", pointer="/task")`. `validation.validate(..., task="optimization")` raises the same
refusal and builds no report. The enum value stays in the frozen schema, unused. Earlier tests that assert
`READY_FOR_OPTIMIZATION` are changed and listed in the manifest as moved. *New node:*
`tests/test_t08_w2_unsupported.py::test_u05_validate_for_optimization_is_unsupported`; it asserts the error
through `LocalApplication.validate`, with no report built. *Spec §5.3, row U05, replaced:*
> | U05 | `validate(task="optimization")`; any study — optimization, parametric sensitivities, sweeps, parameter estimation | `validate` with `task: optimization` ends with ADR 0019's error `unsupported`, detail `task_unsupported(optimization)`, before any analysis; no v0.1 path returns `READY_FOR_OPTIMIZATION` (the value stays in the frozen enum, unused); the other studies have no operation among the twenty of `OPERATIONS`; no optimality claim anywhere |

The envelope YAML gets the same U05 row, with the new node and `doc:docs/blueprint-v3.1.md` as evidence.
Delete the YAML header's U05 build-lane note.

**2. §5.2 Components — amend the spec to match the code.** *Rejected alternative:* widen
`canonical_components` to accept subsets. That is a binder and identity change in the RC run-up, and a
zero flow already expresses it. *Spec §5.2, the Components row, replaced:*
> | Components | exactly the three pseudo-components {A, B, C}, declared in any of the six orders and mapped onto the provider's order at binding (T06 A59–A61, R-076); a proper subset, an extra, an unknown or a repeated component is refused `components_unsupported` (U01) — a mixture without one of them is declared with all three and that component's flows exactly zero (ADR 0001 D3); `synthetic: true`; no real identity | provider component set; `canonical_components` |

Change U01's capability cell to: "real components, or a component set that is not exactly a permutation of
{A, B, C}". Add the zero-flow sentence to the envelope's `components.statement`, and delete the
header's components note.

**3. L10 — confirmed with one correction.** The seed text is stale. The restated text is right, but it
omits the tear path. *Spec §5.5 and the YAML, L10 replaced:*
> | L10 | The initializer chain is partial (blueprint §7.4, K03 §10.1): GUESS-role specifications are not bound by the revision binder (such revisions run on `legacy_eo`), the SYN-001 tear path has its registered initializer only, and the one fallback between initializer sources is `T08-warm-v1`'s compatible warm start → traversal (opt-in; L-WS-1, L-WS-2) | T03 spec §13; K03 §10.1; T07 S-G; ADR 0024 |

**4. Harvest rules — accepted, tightened. L22 is split, and new rows are added.** *Rejected alternative:*
one pointer per item, and S → test/check only. The first forces artificial splits of manifest text that is
hashed whole. The second would refuse LICENSE and ADR 0002, which really are closed by a document. *Spec §5.7,
the sentence from "classified exactly once" up to "The check fails", replaced:*
> classified exactly once: **E** (user-facing; points to one or more L-rows of §5.5 or U-rows of §5.3), **S** (superseded or closed; points to the closing test node or passing manifest check, or to a document only when the closing fact is that document's existence and it did not exist when the item was written — a status inside a document that already existed is closed by a test asserting it), **P** (provenance or process note needing no closure; stays in its manifest), **B** (an open defect or follow-up not closed in v0.1; points to a backlog id of §6.3). A compound item takes the first applicable class in the order E, B, S, P; its pointers name a row for every user-facing part, and an E item may also carry the backlog ids of its B parts. A defect handed on is never P: it is S when closed, E when a user can reach it, else B.

A21's code then accepts B ids among an E item's pointers. Rows L18–L35 are accepted. **L22 replaced, and
L36–L39 added** (spec §5.5 and the YAML):
> | L22 | Scope of the solver evidence: tear selection is greedy (minimality not claimed); behaviour finer than the registered basin margins and trajectories below a residual of 1e-6 are not established; several stated rules are exercised only by synthetic fixtures | T02 spec §12; T03 spec §13 |
> | L36 | No performance claim at size: costs are within-platform measurements on registered cases of at most tens of variables; compiles per plan run and the regularity screen's cost at size are not measured | T02 spec §12; T03 spec §13; T06 spec §15 |
> | L37 | `verify` is not safe to run concurrently in threads of one process: the regularity screen seeds and restores numpy's global generator around `onenormest` (T06 §8.1, R-069), so concurrent calls can move the estimate, `rcond₁`, the bound and a regularity verdict near its threshold; jobs run in separate processes and are unaffected | T06 spec §16 (Q27) |
> | L38 | Structural analysis is generic: validation's STR checks and `inspect_structure` report structural rank and the DM/BTF partition only; numerical rank, conditioning and feasibility are judged by the certificate's regularity screen at a converged state (blueprint D05) | T01 spec |
> | L39 | The structural-zero release (recovery edge E5) leaves no trace record: a trace does not show that it ran | `docs/recovery-edges.yaml` E5 |

**5. Unchanged-physics evidence for E1, E5, E10, E11, E12 — one test per row. No bare structural argument.**
*Rejected alternative:* accept the structural argument as prose. A33 requires evidence; prose does not fail
when the code changes, and a test that pins the argument does. Put the new tests in
`tests/test_t08_w2_edge_identity.py`, each exactly as follows:
- **E1** `test_e1_an_anderson_restart_reevaluates_the_same_map`. Take the case of
  `test_a14_rec_05_with_the_tail_stagnates_under_substitution` and wrap its map in a recorder. Run
  `solve_recycle` as that test does. Assert that at least one `restart` event fired. Assert that every map
  evaluation before and after the first restart is a call of the same map object, with parameter values
  equal (`==`) to those at the first call. Kind `identity_compared`.
- **E5** `test_e5_the_release_reevaluates_the_same_problem`. Take the problem of
  `test_b35a_the_calls_start_is_the_default_opening_and_releases`. Spy on (wrap; do not alter)
  `process_runtime.numerics.newton._released`. Assert that the spy returned a non-empty set at least once.
  Assert that every residual and Jacobian evaluation in the call was made on the same `Problem` object,
  with pinned values equal to those at the first evaluation. Kind `identity_compared`.
- **E10** `test_e10_a_refused_projection_certifies_the_same_declaration`. Run `verify_revision` on
  SYN-001-nominal's revision-route solve twice: unpatched, and with
  `process_runtime.verify.projection.factorize` patched to raise. Assert that the patched certificate
  records `judged_at == "final_state"` and refusal `linear_solve_failed`, and the unpatched one records
  `"projection"`. Assert that both certificates' `model_version`, `constants_sha256`, revision hash and
  check-policy hash are equal to each other and to the bound declaration's. Kind `identity_compared`.
- **E11** (see M1): retitle the row "revision-binder refusal → `legacy_eo` (validate's fallback and the
  solve route)". Add the label `route_fallback:legacy_eo`, which the scan reads as follows: for every call
  whose callee is `Route` and that has a third positional argument or a `reason=` keyword other than the
  constant `None`, add `route_fallback:<the first argument's strings>`. Add `route_fallback` to
  `test_the_scan_reads_every_label_source`'s prefixes. Add the failure test
  `tests/test_t07_r7_admission.py::test_g_r7_1_routes_over_the_corpus`. Set `unchanged_physics: {kind:
  guard, tests: [test_c0_a_refusal_outside_round_6s_class_is_returned_as_it_is,
  test_c1_a_free_specification_that_reaches_no_coordinate, test_c3_a_free_coordinate_the_legacy_binding_does_not_free,
  test_c4_a_target_the_legacy_binding_does_not_promote, test_c5_every_other_count_is_refused,
  test_every_admitted_corpus_route_plans_with_one_pair_on_legacy_eo]}` (all in `test_t07_r7_admission.py`),
  with the note: "held to the problem, not to `model_version`, which differs by construction".
- **E12** `test_e12_a_ptc_solve_keeps_the_declaration`. Take the lowest-index PTC-R1 start that W5's
  committed C_res records list `CONVERGED` under `T08-ptc-v1`, and solve it under `T08-ptc-v1`. Assert that
  the plan's and the root fingerprint's `model_version` and `constants_sha256` equal the bound
  declaration's. Kind `identity_compared`.

**6. Kinds of evidence — all three count, each under a condition.** *Rejected alternative:* only
`identity_compared`. The certificate's guard (`verify/certificate.py:402–440`) refuses a final solve whose
`model_version` or `constants_sha256` differs from the bound declaration, or whose revision differs. Its
checks then evaluate the original rows. So a VERIFIED outcome is a root of the unchanged problem, which is
the property the principle protects. *Spec §5.6, the sentence "Each row: … `enabled` ∈ {default,
policy-only, absent}." replaced:*
> Each row: trigger, precondition, maximum count, the injected failure and its test node, the evidence that `model_version`, `constants_sha256` and the specifications are unchanged, and `enabled` ∈ {default, policy-only, library-only, absent} (`library-only`: no application-offered policy and no `MODEL_BUILDERS` unit reaches the edge, pinned by a test that fails when one does; such a row meets every clause an enabled row meets). Evidence is one of: **(i) `identity_compared`** — a test compares the edge's instance with the failed or target one in `model_version`, `constants_sha256` and specifications (T04 §5.4), or, for an edge acting inside one call on a caller-owned problem, shows every evaluation before and after the edge made on the same problem object with equal pinned values; **(ii) `verified_certificate`** — a test in which the edge demonstrably fires (its label or provenance asserted) ends `VERIFIED` by `verify_revision`/`verify_bound` against the bound revision; it shows the reported state is a root of the unchanged problem, not that every intermediate instance was unchanged; **(iii) `guard`** — the edge's path passes an identity guard before the new instance is used, and a test injects a change of each field the row claims (`model_version` and `constants_sha256`; specification values enter through `constants_sha256`) and sees it refused. A cross-binder fallback is held to the problem, not to `model_version`: its guard is `legacy_admission`'s C0–C5 (T07 ruling round 7).

E3b, E6 and E8 meet (ii) as cited. **E4:** add the parameter `identity-constants_sha256` to
`tests/test_t03_contract.py::test_a16_an_incompatible_opening_is_refused_and_opens_nothing`. It injects a
changed `constants_sha256` at a restart opening, and `check_opening`'s identity check refuses it. Cite
the new parameter in E4. *§9, the T08.A33 row's criterion replaced:* "the bijection holds; every `default`,
`policy-only` or `library-only` row has a direct injected-failure test that passes at `C` and unchanged-physics
evidence of a kind §5.6 admits; every `library-only` row's unreachability test passes".

**7. E7 — not enough. Add the injected failure on a real revision.** *Rejected alternative:* KS-3 alone. A
kernel-level test shows the branch, not that the solve around it keeps the problem. The new test is
`test_e7_a_ph_closure_without_an_answer_keeps_the_declaration`. Patch
`process_runtime.orchestrator.region._ph_closure` to return `None`, and solve CH-UP-DP (the revision of
`tests/test_t05b_openings.py`) under its route's default policy. Assert three things: at least one recorded
`fallback(<unit>, tp)` on a PH-type split; an outcome in `SolveOutcome` (no exception); and the plan's
`model_version` and `constants_sha256` (and the root fingerprint's, if `CONVERGED`) equal to the unpatched
run's. If no `fallback(…, tp)` is recorded, the case does not reach the branch: stop and report. Do not
substitute another case. Cite the test in E7 as `identity_compared`, keeping KS-3 as the failure test.

**8. E1/E2 — `library-only`.** *Rejected alternatives:* `default` is false, because every `MODEL_BUILDERS`
unit declares exact derivatives, so `auto` never resolves to `anderson`. `policy-only` claims a selectable
policy, and none of the four offered policies is one. The new test is
`test_e1_e2_no_offered_policy_or_unit_reaches_a_recycle_iteration`. It asserts two things: every
`MODEL_BUILDERS` unit declares exact derivatives (the predicate `build_execution_plan` resolves `auto`
with), and no policy in `APPLICATION_POLICIES` has a `recycle.method` that `build_execution_plan`
resolves to a recycle iteration. Cite it in E1 and E2 under a new field `reachability_tests`, which
`check_form` requires for `library-only`. Add `library-only` to `ENABLED`. The support matrix renders
these rows as "not offered in v0.1 (library API only)". E1 still needs its identity test (Ruling 5).

**9. E5 without a label — acceptable for v0.1. Record it as L39, and backlog the label.** *Rejected
alternative:* add the label now. That is a trace/identity change in the RC run-up, and the substitution
procedure of §6.2 would be needed for no user gain. *Spec §6.3, appended:*
> B10 handed-on follow-ups, unreachable or harmless in v0.1: a `CONVERGED` result without `x_final` yields a schema-refused certificate (T03 review §8; refuse the input, or a nullable `regularity` by ADR); K02 `TPFlash.evaluate` does not apply R-007 to a declared inlet phase (T05 §20 F7); `CheckPolicy.sha256` covers the tolerance table only, not §7's thresholds and the required-check list (K04-F9 F4; a K04 revision, an identity change); T05b re-review N-W5 (augment's recursion) and N-W6 (the release acts only at `α_max = 0`). B11 a trace record for the structural-zero release, recovery edge E5 (an identity change if the record enters R0).

**10. E9 — no consequence for v0.1.** *Rejected alternative:* split the producer. The shared event's
messages already distinguish its meanings, and a split is a trace change. Add to E9's `notes`: "Under the
shared producer only `warm_start_rejected(<check>)` is this edge (a next source runs); E3b's P4 rejection
and the terminal rejections (`missing_initial_guess`, a failed traversal) start no next source and are not
edges." The tear-path gap is L10's.

**11. CLI `replay --rerun` — a rule-5 defect, fixed before the RC. This reverses T07 D-Q6 for the CLI.**
*Rejected alternative:* register a limitation. A verdict about a different problem is a wrong typed result,
and here it hits every revision-built bundle. *Code:* `command_replay` with `--rerun` calls
`reproduce_bundle(directory, rerun=True, rerun_directory=<a temporary directory>, run_id="replay")`.
It prints that report's fields as today and drops the nominal fallback. Exit 0 iff the verdict is `MATCH`,
or `NOT_RUN` when `--rerun` was not given. An unknown non-revision run id ends `NOT_RUN` with the reason
`rerun_unsupported(no_revision_document)`, and exit 1. *New assertion, spec §9:*
> | T08.A17 | CLI `replay --rerun` on (a) a revision-built bundle, (b) a K05 bundle whose `run_id` is no registered case | (a) reruns the recorded route, `MATCH`, exit 0; (b) `NOT_RUN`, reason `rerun_unsupported(no_revision_document)`, nothing rerun, exit 1 | exact | test |

*Register entry (take the next free R number):* "CLI `replay --rerun` follows `reproduce_bundle`; the fallback
to SYN-001-nominal is removed. Rejected: keeping it (T07 design note §12.3, §17 D-Q6), because it compares an
unknown or revision-built run with another problem's rerun. Decided by design lane, T08 review 2, 2026-10-01."

**12. Inventory location — `docs/recovery-edges.yaml` stands. No ADR.** *Rejected alternative:*
`benchmarks/t08/` plus a guard exemption. That would weaken three registered literal guards to move a file
that is not a case, fixture or reference. *Spec §5.6, appended to the first paragraph:* "The inventory is
`docs/recovery-edges.yaml`: it spells policy literals that the T05b/T06 literal guards forbid in registered
cases, fixtures and references, which it is not."

**13. T07 L3 — the design-lane text review blocks the RC. It is not a limitation.** It is done by the
design-lane `reviewer`, in one short pass of its own over the 17 texts at their recorded hashes. It records
`reviewed` or `changes_requested` per operation in REVIEW.json. A changed text voids Frank's human review of
that text, and he re-reviews it. *Rejected alternative:* a limitation row. T07 §11.3 made both reviews
conditions, and an unreviewed agent-facing text is a process gap, not a user-facing property. *New
assertion, spec §9:*
> | T08.A18 | `src/process_runtime/application/bindings/descriptions/REVIEW.json` | for each of the 17 operations both reviews (`design-lane`, `human`) are `reviewed`, with `reviewed_by` and `reviewed_at` set, at the recorded hash, which equals the served text's | exact | test |

The node is `tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes`.
It stays red until the review is recorded (no xfail). Harvest T07 `limitations[2]` and `[3]` are S → that
node. *§8.1 item 2 replaced:* "**RC blockers closed.** D1–D3, the typed-ends sweep, A89, the record fields
(§6.1) — T08.A10–A16; review 2's rule-5 defects — U05 (T08.A22's U05 node) and the CLI rerun (T08.A17); the
design-lane review of the MCP tool descriptions (T08.A18)."

## C. Harvest edits (YAML `harvest`; notes as written)

| Item | Now | Becomes |
| --- | --- | --- |
| K02 `limitations[6]` | P | E → [U05] |
| T01 `limitations[7]` | P | E → [L38] |
| T03 `limitations[6]` | S → b41 | E → [L10] |
| T03 `limitations[16]` | P | B → [B10] |
| T05 `limitations[12]` | P | B → [B10] |
| T05b `limitations[13]` | P | E → [L02, B10] |
| T05b `limitations[14]` | P | B → [B10] |
| T05b `limitations[15]` | E → [L07] | S → the `ONENORMEST_SEED` test node (N2) |
| T06 `limitations[12]` | E → [L04, L03] | E → [L04, L03, L37] |
| T06 `limitations[18]` | E → [L19] | E → [L19, L36] |
| T02 `limitations[10]`, `[16]`; T03 `limitations[7]` | E → [L22] | E → [L36] |
| T04 `limitations[9]`; T05b `limitations[7]` | E → [L18, L22] | E → [L18, L36] |
| T07 `limitations[2]`, `[3]` | S → doc / P | S → T08.A18's node |
| K03 `limitations[0]` | S | unchanged; note per N5 |

## D. What the build lane implements

1. **Code** (both are RC blockers): U05's refusal (Ruling 1); the CLI rerun through `reproduce_bundle`
   (Ruling 11).
2. **Tests:** six in `tests/test_t08_w2_edge_identity.py` (E1, E5, E7, E10, E12, and the E1/E2
   reachability test); the T03 A16 `constants_sha256` parameter; the U05 node; T08.A17; T08.A18 (red until
   reviewed).
3. **Inventory and scan:** E1/E2 `library-only` and `reachability_tests`; E4/E7/E10/E11/E12 evidence;
   E11 retitled; the `route_fallback:` label family; the scan made fail-closed on non-constant event kinds
   (S6); the E9 note.
4. **Envelope and spec:** the amendments of Rulings 1–4, 6, 9, 11–13; rows L22, L36–L39 and U05; backlog
   B10, B11; the harvest edits of §C; a regenerated `docs/support-matrix.md`.
5. **Then:** the design-lane `reviewer` pass over the 17 descriptions (Ruling 13), as a separate brief.

## Not examined

The Phase 2a commits other than the components axis and U05 (A20/A22/A23 mechanics, A24, the A02 ledger).
The 90 E items beyond their first 300 characters. The cited-nodes subprocess run. Whether the E3b/E6/E8 cited
tests are the only producers of their labels in the corpus. Runtime behaviour of the fixes I prescribe; for
E7, Ruling 7 says what to do if the case does not reach the branch.
