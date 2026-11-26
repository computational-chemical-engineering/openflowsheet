---
name: line06
description: Resume or run OpenFlowsheet's 0.6 line campaign (LINE06) - F2, F8 WO1-WO3/WO5, X06, then the 0.6.0 release. Read order, routing by role, how a work order is written and judged, merge and release order, what waits for the user. Use after a context reset or when asked to continue 0.6, F2, F8 or X06.
---

# LINE06: the 0.6 line, orchestrator procedure

Position, numbers and rules live in files on `main` (`/home/eajfpeters/Code/OpenFlowsheet`). Read, in order:

1. `docs/LINE06_STATE.md`: position, gate table, next action, open cards, running jobs.
2. `docs/LINE06_RULES.md`: the user's words, stops, lanes, agents, git, runs. Every brief names it.
3. `docs/LINE06_DECISIONS.md` and the package files `docs/{F2,F8,X06}_DECISIONS.md`: append-only; `grep` them.
4. The package's ADR by section only (`grep -n '^#'`): 0062 (F2), 0067 (F8), 0078 (X06): Decisions, Exit tests, Work
   orders, Risks. ADR 0057 Amendment 3 and R-1070 for scope.
5. For the release: the `rel050` skill's order (`.claude/skills/rel050/SKILL.md`; read REL050/REL051 for "wp/REL050"),
   RP by section, `docs/briefs/LINE06-line-0.6.md`.

## Roles

- `opus-engineer`: the work orders marked Opus (numerics-adjacent, identity, schemas, replay).
- `sonnet-implementer`: the ones marked Sonnet (close-out, manifests, mechanical), with a complete spec.
- `architect`: X06 once (ADR 0078). `reviewer`: once per package before its merge. `specifier`: LINE06-L1 once.
  `verdict`: once at the release. `recon`: cheap location work for a brief, when the files are not known.
- The orchestrator (this session): writes each brief as a file `docs/briefs/LINE06-<WO>.md`, runs P1-style premise
  checks itself, reads one result per wake, spot-checks the one number that matters, merges, logs, keeps the state
  file. At most 2 agents; never resume a large-context agent.

## A work order

Brief file: the task in one paragraph; the ADR sections and `file:line` anchors; the facts established (numbers);
what was tried and rejected; the acceptance check (exit ids, the test command, F0); "Do not spawn sub-agents
yourself"; `docs/LINE06_RULES.md`; a 200-300 word report. The engineer works in the package worktree, commits named
paths, logs DECISIONs in the package file, does not push. Judge it on the acceptance check alone; a miss is a miss.
After it reports: `git status` in the worktree and ListAgents before the next agent on the same tree.

## Merge order per package

All WOs pass -> manifest `tested` -> reviewer pass and fix round -> ADR acceptance card (DECISION-REQUEST to hub) ->
push the branch (CI must judge it) -> CI green on all legs -> merge card -> merge into main (merge commit) -> F0 on
main -> push main -> delete the worktree.

## Waits for the user (Decision Desk via hub; "the user", action text per option)

ADR acceptances, every merge into main, the release's messages, tag, dispatch, PyPI. Act only on VERIFIED
(`python3 ~/.claude/tools/decision_desk_verify.py D <id> --action "<exact action>"`), then write `executed`.

## Milestones and self-reset

At a milestone (a WO judged, a package merged) or above ~150k context, with no agent of this session running:
rewrite `docs/LINE06_STATE.md` (and every running job's PID, log, what to do when it ends), commit on main (local),
then run `python3 ~/.claude/tools/self_reset.py "Resume LINE06: invoke the line06 skill."` and end the turn.
