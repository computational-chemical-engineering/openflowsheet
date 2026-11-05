# MSG handoff (after WO-3, WO-4, WO-6) — 2026-11-05

Branch `wp/MSG`, worktree `.claude/worktrees/msg`. Spec `docs/design/MSG-messages.md`; choices in
`docs/MSG_DECISIONS.md` (D0-1…D6-5). Not pushed, not merged.

## Done (commits)

- WO-3 `251b98b4`: `ApiError.explanation`, layered `ApplicationError.__str__`, `project_error`
  attaches `detail.explanation` (idempotent), nested attach at `operations.error_locations`, MCP
  error results projected, CLI stderr text + top-level `internal_error` handler + validate line,
  FB-03(b) `not_found` members. Tests `tests/test_msg_surfaces.py`.
- WO-4 `69802e70`: coded `StoreError`, `create(exist_ok=)`, `project init --exist-ok`, three new
  stubs (`not_a_directory`, `not_a_project`, `project_id_mismatch`, review: true), README, MSG-G9.
- WO-6 `d8a2be92`: `RunFailure`, `RunResult.failure`, `raise_for_outcome`, `SolveFailedError`,
  schemas (`run_failure`, `explanation`), conftest converse check, CLI failure text, MSG-G10
  (`tests/msg_schema_support.without_msg`, `SNAPSHOT_MSG`, `MSG_SERVED_SHA256`, chain link c_4).
- Follow-through `4324953f`: `tests/msg_support.machine_detail`, pins reversal, G20, W26 members.

## Next

- WO-7 (`explain`): extend `without_msg` with the `explain` tool and `$defs/message_entry`;
  re-measure and re-register `MSG_SERVED_SHA256` / `m07a_rc` c_4 digest; add `message_entry` to
  `DEFS` and fixtures in `scripts/t07_schema_fixtures.py` (pattern: `explanation`).
- WO-5 (sidecar; own engineer): `_run_failure` already passes `worker_result.run["diagnosis"]`
  to `explain_failure`; C01/C02 numbers then appear in `failure.explanation.numbers`.
- WO-10: web shell display; W26 fixtures already carry `failure` / `detail.explanation`.
- Design lane (batched): register entry with `D_4` and Frank's carry naming c_4 (D6-4); stub
  prose for the three FB-01 codes (D4-1); CLI `solve`/`inspect` render without revision context
  (D6-3); the `operation` member §4.13.3 shows is not in the machine detail (D3-4).

## Gates at the end of this run

MSG-G0 PASS (a–d) at `4324953f`; gate: only 3 wall-clock limits under load failed (details and
A/B timings at the tail of `docs/MSG_DECISIONS.md`).
