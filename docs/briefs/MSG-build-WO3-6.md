# Build brief: MSG work orders WO-3, WO-4, WO-6 (0.4)

Status: brief, 2026-11-05. Spec: `docs/design/MSG-messages.md`; ADR 0058 **Accepted** (Frank, 2026-11-05; R-932…R-937),
effective on `main` when MSG is `tested` and reviewed. Branch `wp/MSG`, worktree `.claude/worktrees/msg`. WO-0…WO-2 are
done (`37a521f9`…`62e400c5`); read `docs/MSG_DECISIONS.md` (D0-1…D2-6) before you start.

## Scope

In order: WO-3 (`ApiError` explanations on every surface, plus FB-03(b) `not_found`), WO-4 (FB-01), WO-6
(`RunResult.failure`), from the note §6 with their files and *Accept* lists. Read §3.3, §3.4, §3.7, §3.8, §4.5, §4.7,
§4.8, §4.10, §4.13.3, §4.13.4, §5, §7 rows MSG-G0, G7, G8, G9, G10. Do not start WO-5 (the diagnostic sidecar: it is the
riskiest identity change and gets its own engineer) or WO-7 and later.

## Rules

- Start with `git merge main` (brings ADR 0058's Accepted status and register entries).
- MSG-G0 must PASS after each identity-touching WO (WO-3 is one), against the committed baseline. If it fails, stop and
  report: no released number, hash, bundle byte or replay verdict may move. Never adjust the gate to make it pass; a gate
  change needs its own commit and a reason in the decisions log, and is flagged in your report.
- MSG-G7: only the CLI golden records the note names may change; all 17 exit codes unchanged. MSG-G10: with `failure`
  and the `explain` row removed, every frozen-surface snapshot and the MCP digest equal the pre-MSG values.
- Build choices: decide, isolate, log in `docs/MSG_DECISIONS.md` (D3-…, D4-…, D6-…). A choice that changes numerics,
  identity or a frozen interface beyond ADR 0058: stop and report. Questions for the design lane are batched for MSG's
  single reviewer pass — list them, do not wait.
- No relaxed checks, no removed cases. Run the tests you touch. Run the full gate once at the end, in the background
  (`PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`), and wait for its
  notification. The host is heavily loaded by other users: if the only failures are wall-time budget tests
  (`test_f6_the_forty_runs_fit_their_budget`, `test_the_budget_of_the_scenario_runs`), re-run each alone and report
  both timings; never change a budget.
- Commit on `wp/MSG` only, named paths, messages `MSG WO-<n>: …`. Do not push or merge.
- Context cap about 150k tokens: commit what is complete, write `docs/MSG_HANDOFF.md` (≤ 40 lines), stop.
- Never touch `~/.config/procsim/`, `.claude/worktrees/f0`. Do not start subagents.

## Report (≤ 30 lines)

Commits per WO; *Accept* items pass/fail; MSG-G0, G7, G8, G9, G10 summary lines; gate result; choices logged; design-lane
questions.
