---
name: s17-refactor
description: Resume or run OpenFlowsheet's S17 code-health refactor campaign on src/openflowsheet/application/ (orchestrator procedure, routing, work orders, gates, closing). Use when continuing S17, briefing an S17 engineer or reviewer, or closing the campaign.
---

# S17 refactor campaign: orchestrator procedure

Position and numbers live in files, not here. Read, in order:

1. `docs/S17_STATE.md`: position, campaign base `CB`, next actions, gate table.
2. `docs/S17_RULES.md`: the standing rules every worker gets.
3. `docs/code-health.md`: the tool, the config, the campaign rules.
4. The tool's loop: `~/Code/cce-code-health/plugins/cce-code-health/skills/refactor-loop/SKILL.md` and
   `playbook-seed.md` next to it; then `.codehealth/playbook.md` if it exists.
5. Tail of the run log: `tail -n 20 "$(git rev-parse --git-common-dir)/codehealth/runs/s17.jsonl"`.
6. `docs/S17_DECISIONS.md` only for the entry a change touches (grep it).

## Routing (repository lanes)

| role | agent | for |
| --- | --- | --- |
| orchestrator | the session | state file, decisions, work orders, judging gates, merges, pushes, reports to Frank |
| engineer | `opus-engineer` | refactor steps: a work order of 3 to 6 targets, about 150k context, then ends |
| mechanical | `sonnet-implementer` | manifest, docs, playbook consolidation from the run log by script |
| reviewer | `reviewer` | every 5 accepted steps: the diffs only, against gaming (refactor-loop "Review against gaming") |

At most 2 agents at a time; only one engineer on `wp/S17` at a time (steps are sequential). Never resume a
large-context agent; start a fresh one with the run log as its memory. After an agent reports, check `git status`
in the worktree and ListAgents before the next one.

## A work order

A file `$(git rev-parse --git-common-dir)/codehealth/briefs/S17-WO<n>.md`, outside the tree (D12: a file added
after the campaign base makes every selection fall back to the full suite); copied to `docs/briefs/` at campaign end.
It names:

- `docs/S17_RULES.md` and the tool's refactor-loop skill (which it follows step by step);
- the gate base of each step: the last accepted commit, or a docs commit of the orchestrator after it (`HEAD`
  before the step's provisional commit); gate.sh passes `CB` as `--ref-base`;
- the targets: file and function, with debt from `codehealth scan --json`; targets that failed three times are out;
- the gate command: `.claude/skills/s17-refactor/gate.sh <last accepted> <label>` (background, wait for it), after a
  provisional commit of the step (D14), and `codehealth log` after it (`docs/S17_RULES.md`);
- the stop condition: targets done, or about 150k context, or three consecutive failures; commit what is accepted;
- the report: about 20 lines, accepted and failed steps with debt before and after and the failing tier.
- "Do not spawn sub-agents yourself."

## Judging a step (the orchestrator spot-checks, does not redo)

Accepted only if the run log line has `result: accepted`, the gate JSON says pass, and `codehealth diff --base <the
step's base> --head <its commit>` shows lower debt. Spot-check one step per work order by rereading its gate JSON.
A miss stays a miss in the log.

## Every 5 accepted steps

Brief a fresh `reviewer` with the commit range only (`git log`, `git show`), the review question from the
refactor-loop skill, and a 20-line verdict per step. Revert rejected steps with `git revert` (no history rewrite),
gate the revert with `gate.sh --revert <sha>`, log `review-reject` with `--reason`, and add a "when not" to the
playbook. Review notes that need only renames or docstrings: one follow-up commit gated with `gate.sh --no-gain`.

## Every ~10 attempts

`sonnet-implementer` computes per-recipe statistics from the run log with a script and updates
`.codehealth/playbook.md` in a separate docs commit (refactor-loop "Playbook consolidation").

## Closing the campaign

1. Stop rule met (state file "Budget", or G-END reached).
2. Copy the run log to `.codehealth/runs/s17.jsonl` and the briefs to `docs/briefs/` (docs commit); playbook commit.
   No file is added to the tree before this point (D12).
3. Scan at the final commit; fill G-END in the state file; write the S17 manifest (`sonnet-implementer`,
   status `tested` only after CI); T08 harvest rows for its limitations.
4. Push `wp/S17`; CI green on both legs (G-END-CI); merge into `main` (merge commit); F0 on `main`; push.
5. Report to Frank in about 20 lines: debt and health before and after per file, accepted and attempted, gate
   failures by tier, top recipes, agents used, anything for his decision (module splits).

## Waits for Frank

Module splits; anything touching public names or behaviour; the silent queued job finding (S16 B-9); the rename of
the repository's agents (after S17 merges).
