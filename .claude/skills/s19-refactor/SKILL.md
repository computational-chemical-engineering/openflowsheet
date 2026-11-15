---
name: s19-refactor
description: Resume or run OpenFlowsheet's S19 repo-wide code-health campaign (orchestrator procedure, gate queue, lanes, reviews, merges, self-reset). Use when continuing S19 after a reset, briefing an S19 engineer or reviewer, or merging an S19 phase.
---

# S19 code-health campaign: orchestrator procedure

Position, numbers and rules live in files, not here. A fresh session reads, in order:

1. `docs/S19_STATE.md` (in worktree `.claude/worktrees/s19`, branch `wp/S19`): position, `MB`, open items, next
   actions, the gate table with G-END numbers.
2. `docs/S19_RULES.md`: standing rules every worker gets (Frank's words verbatim, retarget and source-reading rules).
3. `docs/S19_DECISIONS.md`: append-only log; `grep` it, never read it whole.
4. Briefs and plans: `<git-common-dir>/codehealth/briefs/` (`S19-W3-common.md` binds every engineer,
   `S19-R-W3-common.md` every reviewer, `S19-W3-targets.md` the targets); `docs/briefs/S19-G1-plan.md` (G1 recipe
   `closures-to-class`, RC1 to RC7); `.codehealth/playbook.md` (rules for new code).
5. Running work: `python3 .claude/skills/s19-refactor/gate_queue.py status`, `git worktree list`, the lane branches
   `wp/S19-g*`; drafted but ungated work in `<git-common-dir>/codehealth/drafts/`.

## Roles (repository lanes; agents in `.claude/agents/`)

- Engineer (`opus-engineer`, Opus): one lane run per brief file; delivers a chain of committed steps, enqueues it on
  the gate queue and ENDS. It never waits on a gate in context.
- Reviewer (`reviewer`, Opus; `model: fable` only for hard rulings: identity, initialization order, solver/verifier
  independence, a new recipe): one review per lane result before merge; S1 every chain, S2 every 4 steps, others every 8.
- Architect (`architect`, Fable) for a design that a recipe does not cover (as the G1 plan).
- The orchestrator (this session) briefs, reads one result per wake, merges, logs. It does not edit lane code
  except review-fix docstrings, and it never redoes an agent's work to verify it.

## The loop

1. Lanes: at most 2 engineer runs at a time until the weekly budget reset (Thu 19 Nov 13:00), then as many as the
   gate queue serves. A run takes one function or file to its end state as one chain (playbook recipes), not one
   step per gate.
2. Gate queue (Frank, 2026-11-15): the runner (`gate_queue.py run`, detached) gates each enqueued chain with
   `gate.sh` (two slots, 8 xdist workers, TMPDIR outside the repo, f6 deselected) and logs it with `codehealth log`.
   The orchestrator runs `gate_queue.py wait --since N` in the background: one wake per result.
3. On a result: PASS -> reviewer per cadence -> review fixes (docstrings by the orchestrator, gated no-gain;
   code by a fresh engineer) -> merge the lane into `wp/S19` (merge commit, `git merge -F <file>`) -> log in
   S19_DECISIONS. FAIL -> read the failed checks; an environment failure (ENOSPC, TMPDIR, a timeout far from the
   change) is re-enqueued unchanged with `--rerun-of`; a real failure goes to a fresh engineer to bisect the chain.
4. The test map: `MB` in S19_STATE is the map base; selection is cumulative from it. Move `MB` to the `wp/S19` tip
   at each milestone (`scripts/test_impact.py build --base <sha> --workers 8` with `TMPDIR` outside the repo, in a
   detached worktree; G-MAP: failures a subset of the known set), then lanes fast-forward to it.

## Milestones and self-reset (Frank, 2026-11-15)

At each milestone (a lane merged and the next runs briefed, or context above about 100k), with no background agent
of this session running (the gate runner is detached and survives): rewrite `docs/S19_STATE.md` (position, next
action, open items), commit, then run
`<git-common-dir>/codehealth/tools/self_reset.sh %29 "Resume S19: invoke the s19-refactor skill."` (this session: tmux pane `%29`, session `OpenFlowsheet:0.0`)
and end the turn. The new context starts from this file.

## Merging a phase into main

Evidence manifest `tested`, f6 alone on `wp/S19` (`pytest tests/test_t07_v17_reference.py -k f6`, no gate running),
CI green on both legs, a Decision Desk card signed by Frank and verified with `decision_desk_verify.py` (CLAUDE.md
"Decision Desk sign-offs"), merge commit, F0 on `main`, push, write `executed` on the card.

## Waits for Frank

Scope or priority changes (the G-END split into blocking and trailing parts; S18's file list), any merge into
`main`, and spending beyond the weekly budget.
