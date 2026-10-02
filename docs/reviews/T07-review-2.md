# T07 review 2 — the fixes for V17 c1 defects B1–B3 (rf3a)

Design lane, `reviewer`, 2026-09-28. Read-only, at `wp/T07` HEAD `1159761`. `src/` is identical to
`14412a6`. Scope: `git diff d01a4d7 14412a6 -- src schemas docs/interfaces-frozen.md`, reviewed against
three sources: ruling round 6 in `docs/design/T07-jobs-and-bindings.md`, decision F3, and the rf3a
entries in `docs/T07_DECISIONS.md`. The first review's findings are out of scope.

The probes are in
`/tmp/claude-1003/-home-frankp-Codes-Process-Simulator/c1654ca5-cf40-4fac-b53a-1914bdd081e5/scratchpad/review2/`
(`p1`…`p11`). Each was run with `PYTHONPATH=src:.:tests`.

## Verdict

**B2 is sound as ruled. B3 is sound, with one gap (S2). B1 is implemented exactly as ruled, but the
rule does not achieve what the ruling says it does.** `legacy_answers` inspects only two things:
- the revision binder's *first* refusal code;
- the set of roles.

`specification_role_unsupported` is raised in `_read` at R5 (`models/revision_flowsheet.py:345`). That
happens before any builder runs. So on a document with a `free` specification, the revision binder
never states its pin, contract or target objections, and the legacy binder never has to show that it
uses the `free` role at all. Two consequences follow, each shown by a probe:

- **M1:** the legacy route certifies (VERIFIED) a problem that the document does not state.
- **M2:** B1's exact c1 end comes back: READY, then converges, then
  `certificate_unmapped(legacy_eo,evaluate,converge)`. Ruling item 3 says this is unreachable.

One strengthening of `legacy_answers` fixes both. It keeps G-R6-1 at 36/11/3 (probe 11).

**P3 can be attested once M1 and M2 are fixed.** The fix narrows a registered rule (R6-O1, which Frank
approved as a *narrowed* fallback, and this narrows it further), so the design lane rules it first.
After that, re-run G-R6-1, G-R6-2 and G-R6-7.

Counts: **M 2, S 2, N 4.**

## Findings

### M1 — a `free` specification hides every post-R5 objection. `legacy_eo` then certifies SYN-001's closure of the document, not the document

`application/binding.py:284-297` (`legacy_answers`). Also `revision_run.py:197`, `validation.py:423`,
and the root at `models/revision_flowsheet.py:345`.

**Scenario.** An agent writes T02-2's c1 document again (drum pressure unpinned). It also keeps a `free`
guess, the A02 pattern. The route is still `legacy_eo`. The legacy binder closes S4.P with S1.P (its
isobaric declaration) and the solve ends VERIFIED. That is the problem B1 ruled a fallback must never
substitute, and it is now certified rather than refused.

Probe `p1_routes.py`. All four documents are A02-360 with the edit named:
```
A02-360 minus SPEC-flash-P:      route=legacy_eo | validate=READY_FOR_SIMULATION | rev-binder(free->fixed)=incomplete:specification_missing(S4.P)
flash-T only on S4 (S5.T unpinned): route=legacy_eo | validate=READY_FOR_SIMULATION | rev-binder(free->fixed)=incomplete:specification_missing(S5.T)
both (T02-2's shape + free):     route=legacy_eo | validate=READY_FOR_SIMULATION | rev-binder(free->fixed)=incomplete:specification_missing(S4.P)
```

Probe `p2_solve.py` solves the first of these:
```
route legacy_eo reason unsupported(specification_role_unsupported(GUESS-heater-outlet-T))
outcome CONVERGED cert VERIFIED
S4.P 100000.0 S1.P 100000.0
```

The same gap also lets G-R6-7's own mutation classes through when they are stated as a
`parameters.<name>` specification. `_instance_contracts` parses the document with `specifications`
emptied (`binding.py:622`), so the contract never sees them. The legacy binder also drops fixed
targets it cannot map. Probes `p4_more.py` and `p5_paramspec.py`:
```
m1 via parameters.pressure_drop spec: route=legacy_eo validate=READY_FOR_SIMULATION []
m3 via parameters.efficiency spec:    route=legacy_eo validate=READY_FOR_SIMULATION []
+ unknown path state.x on S2:         route=legacy_eo validate=READY_FOR_SIMULATION []
```

**Smallest fix (design lane; it amends R2.1 as ruled).** Admit `legacy_eo` only when, in addition:

(b) the revision binder, run on the document with every `free` role read as `fixed`, either binds or
refuses only `specification_unconsumed(<id>)` of a specification that was `fixed`. That refusal is the
cross-unit target, which is what the free role exists for. Its check runs after every builder, so
reaching it means every pin was present and every contract held.

`validate()` should then report (b)'s refusal, which carries its B2 hint (for example
`specification_missing(S4.P)` and `path: state.P`). It should not report the uninformative
`specification_role_unsupported`.

A `free` specification with no value needs a placeholder start for (b); probe 11 used 358 K.

### M2 — ruling item 3's "certificate_unmapped cannot be reached through admission" is false: an inert `free` specification

The anchors are the same as M1's, plus `revision_run.py:419` (the raise).

**Scenario.** An agent adds a `role: free` "guess" on the recycle stream to a fully specified loop.
This is plausible for the T02 task, since the A02 files model a guess exactly this way. A second way
in is a `free` specification on a column that a `fixed` one also pins. In both cases the legacy binder
removes no pinned row (`Binding.freed` is empty), so the plan is `[evaluate, converge]`.

Probe `p10_inert_free.py`, on SYN-001-nominal:
```
free S6.T (not a pinned coordinate)            | route legacy_eo | validate READY_FOR_SIMULATION
   solve: RunUnsupportedError certificate_unmapped(legacy_eo,evaluate,converge)
free S3.T (heater pin), no compensating target | route legacy_eo | validate READY_FOR_SIMULATION
   solve: RunUnsupportedError certificate_unmapped(legacy_eo,evaluate,converge)
```
This is c1's T02-2 and T02-3 end, byte for byte.

**Smallest fix.** Add a second condition:

(a) the legacy binding frees a pinned coordinate. Require `len(lb.freed) >= #free specifications > 0`,
so that the plan has a `solve_eo` step. This means `legacy_answers` takes the legacy binding as well.
Both callers already hold it.

Probe `p11_candidate.py` applies (a) and (b) together:
```
corpus legacy_eo kept: 11
A02 minus flash P   | route today: legacy_eo | candidate admits: (False, True, False)
A02 + dp via spec   | route today: legacy_eo | candidate admits: (False, True, False)
A02 + state.x       | route today: legacy_eo | candidate admits: (False, True, False)
nominal + free S6.T | route today: legacy_eo | candidate admits: (False, False, False)
nominal + free S3.T | route today: legacy_eo | candidate admits: (False, False, False)
```
The tuples read (admitted, (a), (b)). All 11 corpus `legacy_eo` revisions still pass, so G-R6-1 should
stay at 36/11/3. G-R6-2 has to be re-measured.

Add the five documents above to G-R6-7 as m5–m9.

### S1 — after W6, the `unsupported` tie hides the contract's reason from the agent

`application/validation.py:440-452`, ruling round 3 Q2.

The tie rule gives the revision binder's refusal, because "the legacy one speaks only of SYN-001's
declaration". Since W6 that premise is stale: the legacy binder's `unsupported` refusal can now be the
revision binder's own contract code. Take G-R6-7's m1 (flash `pressure_drop` 50 kPa). It is correctly
not READY, but every surface names only the free role, with no hint.

Probe `p6_fixcheck2.py`:
```
m1 validate STR-01: not run: this revision cannot be analysed by T01's binding: specification_role_unsupported(GUESS-heater-outlet-T)
m1 inspect_structure: {'not_run_reason': "...specification_role_unsupported(GUESS-heater-outlet-T)", 'hint': None}
```

`detail.unbound`, which does name `parameter_value_unsupported`, appears only on
`revision_unsupported`. Admission never reaches it, because the revision is DRAFT. So B1 item 4 ("the
reason reaches the agent") fails for the W6 classes.

**Fix (needs a decision; my recommendation is to do this).** When the revision refusal is
`specification_role_unsupported` and the legacy binder refuses, report the legacy refusal. The legacy
binder is the one that reads `free`. Only an `unsupported` tie of this shape moves. The M1 and M2 fix
may subsume this, if the design lane routes these refusals through (b).

### S2 — B3: a registry *key* that is not a `policy_id` still gets the false "no registered solve policy"

The constant is `application/policies.py:78`, and its test is `tests/test_t07_b3_policies.py:38`.

The registry says "a policy is named here by a registry key; `policy_id` is the string the policy
document carries". Two registered policies share the `policy_id` `T04-HOM-01`, with different
`sha256`. The key `T04-HOM-01-edge-off` is registered, but it is refused `not_found` with B3's false
text.

Probe `p9_b3.py`:
```
T06-revision-v1 -> unsupported | solve policy 'T06-revision-v1' is registered but not offered in v0.1
T04-HOM-01 -> unsupported | solve policy 'T04-HOM-01' is registered but not offered in v0.1
T04-HOM-01-edge-off -> not_found | no registered solve policy 'T04-HOM-01-edge-off'
no-such-policy -> not_found | no registered solve policy 'no-such-policy'
```

**Fix.** Make the constant the registry's keys together with its `policy_id` values, which is 9 strings.
The equality test then checks against both.

### N1 — G-R6-5 (iii) is a logged measurement, not a test, and it no longer holds after W6

The code-token equality over the 5485 perturbed documents was measured at W3. After W6, 6 of those
documents report the producer's `port_phase_unsupported`, where before they reported the consumer's.
The kind is the same, and the change is disclosed. Nothing committed pins the post-W6 set. Suggestion:
commit its digest, the way `CORPUS_REPORTS_SHA256` is committed.

### N2 — G-R6-6's "`specifications` equals `pin_encodings`" is tautological

`local.py` calls `pin_encodings`, so this equality cannot fail. The substance is G-R6-5 (i): 25/25
triples repaired, a count I confirmed by dumping every model's pins and options.

`list_models` under-lists on purpose, as ruled. For example, the binder accepts `outlet.T` on the
reactor's option, but it is not listed. Every listed encoding binds, which is the direction that
matters.

### N3 — `inspect_structure` can name `legacy_eo` for a DRAFT revision whose solve would raise untyped

Probe `p7_freepin.py` / `p8_inspect.py`: A02-360 with `SPEC-flash-P` made `free`:
```
route legacy_eo | validate DRAFT
inspect legacy_eo ... STRUCTURAL_UNDER_SPECIFICATION
solve_route -> UnsupportedRankStructureError: 3 freed variables against 1 promoted targets
```
Admission step 2 blocks it, so this is not reachable through `submit_job`. The M2 fix (a) probably
removes the route, but I did not probe that.

### N4 — cost

`validate()` now builds the revision flowsheet on every closed legacy analysis. `inspect_structure`
with no route runs both binders up to three times (`select_route`, `validate`, `structural_refusal`).
This costs time only.

## Checked and sound

- **Hints stay out of every hash.**
  - The code tokens at every raise site are unchanged in the diff.
  - `RevisionError.__str__` is still `kind: code`.
  - `Unbound.hint` is `compare=False`, so equality and the generated `__hash__` exclude it, and it is
    bounded to 512 characters.
  - `route_reason` in `solve-path.json` and in the job's `detail` is `kind(detail)` only.
  - A hint reaches the `t07` key only through a validation message (`runs.validation`, q29's non-PASS
    messages). The ruling allows this, and the key currently has zero such entries (`11bcb148…`
    unmoved, per the log; I did not re-run it).
- **Hint plumbing.** DIM-01 bounds its message the same way. `detail.hint` on admission's and the
  runner's `revision_unsupported` comes from `NoRoute.hint`. `_typed_end` receives the re-bound route.
- **The encodings match R5.** Every pin sits on an outlet port. The instance form's `fixes` equals
  what R5's `outlet.T|P` reaches: both of the flash's outlets, or the single outlet elsewhere.
- **The schema change is purely additive and as ruled.** It touches `model_registry_view` pins and
  options only: required `specifications`, `minItems 1`, `additionalProperties: false`, the enums, the
  `object_id` pattern, and the `$ref` for `kind`. The frozen-interfaces line is present.
- **W6 is sound in direction.** The contract only adds refusals and never admits anything. One function
  now serves both binders. The 435 moved codes are all off-corpus.
- **B3 otherwise.** One check point, in `resolve_policies`, serves both admission and the runner. An
  unknown id stays `not_found`. `detail.{policy_id, offered}` is present. `src/` does not read the
  registry.
- **`legacy_answers` as written matches the ruling's pseudocode exactly.** That includes the handling of
  `decision` and a missing role, and `refusal_code`.

## Not examined

- the description texts, G15 and `REVIEW.json`;
- `scripts/t07_schema_fixtures.py`;
- the HTTP and MCP transports;
- the c1 transcript replays;
- the V17 harness and reference (rf3b);
- re-running the identity scripts or the full gate. The G-R6-1/2 numbers are taken from the committed
  tests and the log.

## Re-check at `0899f7c` (ruling round 7, rf5) — 2026-09-28

I read two things:
- ruling round 7, in the design note's last section;
- `git diff 86ab418 HEAD -- src tests scripts/t07_perturbed_refusals.py`.

`legacy_admission` implements C0–C4 as ruled:
- the per-specification C1 and C3;
- a probe loop that runs until the binder binds;
- the legacy-side check on `promoted` (C4);
- `Route.reason` unchanged.

The S1 substitution is limited to the free class and to `incomplete`/`unsupported`. I re-ran probes
p1–p11 at HEAD, and added p12. I also ran `tests/test_t07_r7_admission.py`, `test_t07_b3_policies.py`,
`test_t07_r6_routes.py` and `test_t07_r6_free_role.py`: **86 passed**. I did not re-run the full gate
or the identity scripts.

- **M1 — closed.** A02-360 without the flash pressure pin was READY → `legacy_eo` → VERIFIED. It is now
  `DRAFT`, with no route, and reports `incomplete(specification_missing(S4.P))`, whose hint names
  `path: state.P`; `legacy_route_not_admitted(specification_missing)` is its legacy part (p1, p2). The
  same holds for:
  - S5.T left unpinned, and T02-2's own shape (p1);
  - `parameters.pressure_drop` and `parameters.efficiency` stated as specifications (p5, p6);
  - an unknown path `state.x` (p4).

  The model substitutions under SYN-001's topology are refused by C2 or by W6's contract (p12):
  - the flash named `syn001.ph_flash`;
  - the heater named `syn001.valve` or `syn001.liquid_pump`.

  The round's own m11 and m12 are `DRAFT` (p12).
- **M2 — closed for this review's cases.** On nominal, the free S6.T and the free S3.T that a fixed
  specification also pins are both now `DRAFT` with no route (p10), so c1's `certificate_unmapped` end
  is no longer reachable from them. All 11 corpus `legacy_eo` revisions are still admitted (p11).
- **S1 — closed.** m1 now reports `parameter_value_unsupported(flash.pressure_drop)` in `validate()`
  and in `inspect_structure` (p6). `hint` is null, because B2's table has no parameter hint, as ruled.
- **S2 — closed.** `T04-HOM-01-edge-off` → `unsupported`, "registered but not offered"; an unknown id
  stays `not_found` (p9).
- **New, S3 (should fix; pre-existing since R2.1, not introduced by rf3a or rf5).** Admission does not
  check T02 §7.1's v0.1 rank rule, which requires exactly one freed column and one promoted target.
  The document is A02-360 with `SPEC-feed-n-A` made `free`, plus a fixed purge-flow target `S7.n.A`,
  so it has two design-specification pairs. It is `READY_FOR_SIMULATION` → `legacy_eo`. `solve_route`
  then raises `UnsupportedRankStructureError: 2 freed variables against 2 promoted targets; v0.1 pairs
  exactly one of each` (p12, from `orchestrator/execution.py:484`). The runner does not catch it, so the
  job would end in `internal_error` ("the job runner raised …", `jobs/executor.py:183`). That breaks
  READY's promise of a typed end, the same family as M2, but through a door that c2's all-fixed T02
  task is unlikely to open.

  Smallest fix: a clause C5 in `legacy_admission` that refuses `unsupported` unless
  `len(binding.freed) == len(binding.promoted) == 1`. That mirrors `execution.py:484`. Alternatively,
  map the error in `legacy_plan` to a `PlanRefusal`. Either is one commit, and on the corpus the
  measured sets are 1 and 1 for all 11 revisions. I recommend fixing it with C5 before c2. It does not
  block P3.

**P3 ("B1–B3 fixed as ruled, merged, gate green, reviewed") can be attested.** M1, M2, S1 and S2 are
closed at `0899f7c`. S3 is a pre-existing gap, recommended for a fix before c2 but not part of B1–B3
as ruled. The gate number, 6303, is the engineer's; I did not re-run the full gate.

## Re-check 2 (rf6, merge `25039c3`) — 2026-09-28

I read `git diff 564786b 25039c3 -- src tests`. `src/` at HEAD `1458fad` is the same as at `25039c3`.
I ran probe p13 against HEAD.

- **S3 is closed.** The two-pair document (A02-360 with `SPEC-feed-n-A` made free, plus a fixed
  `S7.n.A`) is now `DRAFT` with no route. It reports `specification_pairing_unsupported(2,2)`, and
  its hint names all four specifications with their coordinates. `inspect_structure` gives the same
  hint.

  C5 also covers the neighbouring shapes:
  - one free specification with no target → `(1,0)`;
  - a free flash `outlet.T`, which frees two columns → `(2,1)`.

  Both are `DRAFT` with no route. Corpus `legacy_eo` routes are still 11.

  The belt-and-braces end also works. `bind_route("legacy_eo", …)` on the two-pair document, followed
  by `solve_route`, now raises `RunUnsupportedError: plan_refused(UNSUPPORTED_RANK_STRUCTURE)`. The
  runner turns that into a typed `unsupported` end, instead of the `internal_error` defect.
- **No new M or S.** Three notes:
  - The `try` in `solve_route` also wraps `plan_revision` and `_validated_override`'s tear-stream
    errors, which would get the same code. That is typed and harmless, and unreachable with the
    registered policies.
  - The hint reads "frees 2 against 2" where "2 coordinates against 2 targets" was meant. It is
    wording only.
  - `orchestrator/rank.py` defines a second, separate `UnsupportedRankStructureError`. It is raised
    at solve and verify time by `eliminate_alias_rows`, and `solve_route` does not map it. That is
    pre-existing, unrelated to S3, and I did not probe it.

Not re-run: the gate count (6315, the engineer's), the identity scripts and the 50-report digest.
