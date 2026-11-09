# Build brief: ST CI red at `8ce17244` (run 42517844608) — three failures

Status: brief, 2026-11-08. **Do not spawn sub-agents yourself.** Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`,
branch `wp/ST`. Worktrees have no `.venv`: run tests as
`PYTHONPATH=src /home/frankp/Codes/OpenFlowsheet/.venv/bin/python -m pytest …` and first confirm
`openflowsheet.__file__` points into the worktree (main's editable install otherwise shadows it — the likely reason
these were not caught locally).

## Failures (both CI legs; default-install has 1 and 2 only)

1. `tests/test_m02_schemas.py:267` `test_g1c_without_m02s_additions_every_response_is_its_pre_m02_snapshot` —
   `KeyError: 'get_stream_table'`.
2. `tests/test_m04_study_job.py:287` `test_a42_m04s_responses_decompose_onto_m02s_snapshots` — same KeyError.
   Both loop over `OPERATIONS` against pre-ST snapshots; MSG's new `explain` row is skipped via
   `tests/msg_schema_support.py` `MSG_OPERATIONS`. ST's `get_stream_table` row postdates these snapshots in the same
   way. Fix in the established pattern (an ST-owned set, e.g. in an ST schema-support module or alongside ST's
   existing surface helpers, with a comment citing ST's ADR 0068). Check `tests/test_t07_w5e_application_results.py`
   and any other test iterating `OPERATIONS` against a snapshot for the same gap. Do **not** relax an assertion: the
   skip must name exactly ST's new operation(s); every other row stays checked. If ST already re-records snapshot
   digests elsewhere (surface chain), keep consistent with that.
3. `tests/test_st_core.py:373` `test_q1_a15_c_every_carried_split_is_evaluated_at_tsat` (CoolProp/IAPWS leg) —
   `KeyError: 'S3.n.H2O'` in `src/openflowsheet/verify/checks.py:130` `stream_of`, called from
   `verify/thermal.py:140` `saturated_enthalpy(Iapws95Provider(), source.variables, name, …, ("H2O",))`. The test passes a
   stream name whose variables are not in `source.variables` (or are keyed differently after main was merged in).
   Diagnose: is it a test bug (wrong `source`/document for that stream, or a stream whose id scheme changed on main) or
   a product bug in ST's stream-table code? If it is a test bug, fix the test; if it is product code, fix it and say
   exactly what changed. If the fix would change numerics, identity or a frozen interface, stop and report instead.

## Done when

The three tests pass with the worktree's `src`; also run `tests/test_st_*.py`, `tests/test_m02_schemas.py`,
`tests/test_m04_study_job.py`, `tests/test_t07_w5e_application_results.py`, `tests/test_msg_*.py`; `ruff check` +
`ruff format --check` on touched files. Log the fix as the next entry in `docs/ST_DECISIONS.md`. One or two commits,
named paths, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; push `wp/ST`. No merge, no manifest.

TRS2 shared (load ~29 of ~36): `uptime` first; targeted tests only, `-n 4` at most. Never read or touch
`~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

Report ≤ 15 lines: commits, cause of each failure, tests run with counts.
