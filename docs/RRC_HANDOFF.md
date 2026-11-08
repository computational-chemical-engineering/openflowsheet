# RRC handoff (build lane; branch `wp/RRC`, worktree `.claude/worktrees/rrc`)

Design: `docs/design/RRC-revision-region-continuation.md` (§7 work orders, §8 gates); ADR 0072 (Proposed).
Decisions: `docs/RRC_DECISIONS.md` (D-1…D-4). Rewritten in place; this is a position, not a diary.

## Done
- **WO-1** `2e3104cf` + `88de116a` (docs): `homotopy.Continuation.start_values`, `type` widened, `level_values`
  dispatch (revision branch reads no opening; specification branch unchanged); `eo_recovery` Literal +1 value;
  `RRC_REVISION_V1` defined in `application/policies.py`, **not offered** (D-1); three schema widenings (FQ1,
  awaiting Frank); `schemas/README.md` note; ADR 0072 C1 filled with the measured byte moves.
  Tests: `tests/test_rrc_continuation.py` (11).
- **WO-2** `4875cf32`: `orchestrator/revision_continuation.py` (candidate/refusal/record types, constants,
  `continued_parameters`, `revision_continuation()` R5/R6/R8/R9a, `refusal_message`). Tests: `tests/test_rrc_checks.py`
  (11, NET-02 binding; R8 iff `D` complete via monkeypatched `continued_parameters`).

## Gates measured (2026-11-08)
- G1 targeted battery (`test_rrc_continuation`, the 4 edge-3 files, `t06_w4_registry`, `t07_b3_policies`,
  `t07_w3a_revision_runs`, `t04/k03/k04/k05/p01` schema tests, `t08_w2_surface_digest`, `t08_b50_surface_content`):
  557 passed. Then `t06_f4_literals`, `t06_f4_policy`, `t07_w5a_inspection`, `test_rrc_checks`: 43 passed.
- Edge-3 test files: empty diff against `main`.
- `scripts/t08_numerical_policy.py --check`: PASS, `numerical_policy_v2.yaml` sha256 `6b449911…` unchanged.
- F0 `scripts/corpus_identity.py --check` at `4875cf32`: PASS — M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61,
  M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- Bytes moved: only the three schema files (table in `docs/RRC_DECISIONS.md`). MCP tool-list digest `455d01eb…`,
  `schemas/registry.json`, all offered `policy_sha256` unchanged.

## Next (not started)
- **WO-3** waits for OPT's executor changes on `main` (design §9 O7): rebase `wp/RRC`, then §5.5 `_revision_continuation`
  in `executor.py` and §5.7 `RecoveryStart.reported_signature` + attempt-0 check in `region.py`; `tests/test_rrc_edge3.py`.
  WO-3 uses `RevisionContinuationRecord`, `refusal_message`, `REVISION_CONTINUATION_SOURCE` from WO-2.
- **WO-4** must also offer the policy (D-1): add `"RRC-revision-v1": RRC_REVISION_V1` to `APPLICATION_POLICIES`, update
  `test_t07_w3a_revision_runs.py` / `test_t07_w5a_inspection.py` / `test_t07_b3_policies.py` pins, and name it in
  `test_t08_b50_surface_content.py` `V02_ADDITIONS["solve_policies"]` with its register entry (needs the number).

## Open for the design lane (batched)
- D-1 (offer timing) and the served `get_project.solve_policies` move it implies — not in design §5.11.
- FQ1 (Frank): the three schema widenings; merge waits for "yes".
