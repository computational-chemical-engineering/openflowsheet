# LINE06-X06-WO3b: apply the design-lane rulings R1 (opus-engineer)

Standing rules: `docs/LINE06_RULES.md` (binding). Do not spawn sub-agents yourself. Worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06` (wp/X06, head `313907cd`, clean). Another engineer works
in `.claude/worktrees/f2`; leave it alone. Commit named paths only, log DECISIONs in `docs/X06_DECISIONS.md`, do not
push. Budget about 150k context.

## The task

Implement `docs/X06_DECISIONS.md` section "Design-lane rulings R1" (line ~201 on) exactly as ruled:
1. **R1-1 (Q7):** `src/openflowsheet/run/bundle.py:202` `_cross_check_solve_path`: a `user.` request (matched whole)
   is judged only against the bundle's own `solve-policy.json` per the ruling's rule (route known; document indexed,
   intact, rebuilt by `from_document`, malformed -> tampered, never raised; `policy_id` equal to the request; hash
   equal to the manifest's `policy_sha256`; one candidate). Every other request goes through today's code unchanged.
   Fix `is_project_policy_id` to `fullmatch` (accepts `"user.x\n"` today). Tests as the ruling lists: E-X06-13 loses
   its `xfail`, the pin test `test_q7_the_bundle_check_resolves_the_requested_policy_by_name` is replaced, forgeries
   F1 to F8 each tampered, the coherent-relabel limit pinned, a genuine lowered-budget run verifies.
2. **R1-2 (Q26):** `tests/test_t07_q26.py`: admit `("register_solve_policy", "policy/scales", "map")` by full path and
   pin the 39 numeric scalars by full path as the ruling lists them; docstring paragraph like F3's, citing ADR 0078
   R1 and R-1075.
3. Append the ADR 0078 section quoted in the ruling's "Text the orchestrator applies" to
   `docs/adr/0078-X06-application-capabilities.md`, after its last section, with R-Q7 = **R-1074** and R-Q26 =
   **R-1075** (registered on main). Edit nothing else in the ADR.

## Acceptance (report each)

1. E-X06-11 to E-X06-15 and E-X06-22 in `tests/test_x06_solve_policies.py`: all pass, 0 xfailed.
2. `tests/test_t07_q26.py`: 6 passed (was 1 failed, 5 passed).
3. The ruling's bundle gate: all 63 committed bundles verify as before, 60 `ok`, digest `b42b1ec439d1683c` unchanged
   (how to compute it: the ruling's text).
4. Surface suites: `tests/test_x06_*.py`, MSG and doc-page tests, `tests/test_m07a_surface_chain.py`: 0 failed
   except `test_every_description_is_reviewed_by_both_lanes` (red by design; list any description file you touch).
5. `ruff check`, `ruff format --check`, `mypy src` clean.
6. F0: `scripts/corpus_identity.py --check` PASS with M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85,
   M7 52/52, M8 105/105, M9 42/42.

## Stops

A change to any existing bundle's verdict, a record, run identity, a request hash or F0; a test that passes only by
relaxing a check; the ruling contradicting the code.

## Report

200-300 words: per acceptance item pass/fail and the number; commits; DECISIONs (one line each); anything for WO4.
