# LINE06-X06-R1: two design-lane rulings from X06-WO3 (architect)

Standing rules: `docs/LINE06_RULES.md` (binding). Do not spawn sub-agents yourself. Work in the worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06` (branch wp/X06, head c526de6a, clean). ADR 0078 is
**Accepted**; do not edit its decisions. Record each ruling in `docs/X06_DECISIONS.md` (append, a section
"Design-lane rulings R1") and commit that file only (named path). Write no production code and no tests.

## Question 1 (Q7, replay identity): how does the bundle integrity check judge a `user.` policy?

Facts (measured by X06-WO3, `docs/X06_DECISIONS.md` section "Q7 measured", about line 169):
- E-X06-12 passes: `user.copy` (T06-revision-v2's policy document, only `policy_id` changed) solves SYN-001-nominal
  to a byte-identical `solution-state.json`; the certificate differs only in `policy_id` and `plan_id`.
- E-X06-13 fails (`xfail(strict=True)` in `tests/test_x06_solve_policies.py`): `src/openflowsheet/run/bundle.py:202`
  `_cross_check_solve_path` resolves `solve-path.json`'s `policy_requested` **by name** via
  `orchestrator.policies.resolve_policy`; a `user.` id resolves to nothing, so the bundle is
  `tampered: [solve-path.json]` and reproduce gives `inspected_archived_results`/`NOT_RUN` (T06 bundle:
  `compatible_reproduction`/`MATCH`).
- ADR 0078 context says replay rebuilds the policy from `solve-policy.json`, never by id lookup (grep the ADR for
  "never by id"); D4 at about lines 162-205; Q7 at about line 416; the stop at line 343.
- The engineer's proposal: for a `user.` `policy_requested`, the candidate is `SolvePolicy.from_document(` the
  bundle's `solve-policy.json` `)` with `policy_id` equal to the request, then the same comparison with the
  manifest's `policy_sha256` (including the admission `max_property_calls` lowering); every non-`user.` bundle is
  judged exactly as today.

Rule on: is the proposal sound as a tamper check (what does it still detect, what does it no longer detect, given
that `solve-policy.json` is itself hashed in the bundle index and the manifest carries `policy_sha256`)? Does it
change any existing bundle's verdict or F0 (it must not)? Should the check also consult the project store when the
policy is registered there, or deliberately not (a bundle must verify on a fresh project)? State the exact rule
the engineer implements, and the tests that prove it (E-X06-13 green, a forged `user.` bundle still caught).

## Question 2 (R-088 Q26): an exception for `register_solve_policy`'s `policy/scales`?

Facts (`docs/X06_DECISIONS.md` section "R-088 Q26 measured", about line 185):
- `tests/test_t07_q26.py::test_t07_q26_no_external_state` fails: `Finding(operation='register_solve_policy',
  path=('policy', 'scales'), kind='map')`. The allowlist is `ALLOWED_BY_PATH` at `tests/test_t07_q26.py:192-200`;
  the precedent is F3's `("validate_record", "reactions/*/stoichiometry", "map")` (ADR 0061, section "F3 ruling
  round 2 applied: fix round 3"; R-1058), documented in the test's docstring at about lines 40-52.
- The engineer's claim: `scales` keys are registered quantity kinds, values are policy constants validated once at
  registration (ADR 0078 D4.3); `policy.scales` is read nowhere in `src/`; nothing from it reaches a solver state.
  Verify that claim yourself (`grep -rn "scales" src/openflowsheet`).

Rule on: grant the exception by full path, or require another shape (for example refuse `scales` in a user policy).
If granted, say where it is recorded (the form F3 used: a section in the governing ADR's record or the decisions
file, and the requirement row it cites) and whether this needs the user's acceptance as a change to an Accepted ADR
or is within ADR 0078's D4 as written.

## Output

The two rulings committed in `docs/X06_DECISIONS.md`; report in at most 250 words: per question the ruling, the
exact rule or allowlist entry for the engineer, the tests, and whether a user card is needed.
