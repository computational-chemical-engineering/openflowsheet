---
name: rel050
description: Resume or run OpenFlowsheet's 0.5.0 release campaign (REL050) - read order, routing by role, how a work order is written and judged, the RP order from line file to dispatch, what waits for Frank. Use after a context reset or when asked to continue the 0.5 release.
---

# REL050: the 0.5.0 release, orchestrator procedure

Position, numbers and rules live in files on branch `wp/REL050` (worktree
`/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/rel050`). A fresh session reads, in order:

1. `docs/REL050_STATE.md`: position, next actions, gate table, open decisions.
2. `docs/REL050_RULES.md`: Frank's words, stops, lanes, freeze, git rules. Every brief names it.
3. `docs/REL050_DECISIONS.md`: append-only; `grep` it.
4. RP `docs/derivations/release-procedure.md` by section only (`grep -n '^#'`): §3 line file, §5 K3/C, §6 RC job,
   §7 version and pin, §8 acceptances, §9.2 order after C, §12 stops, §13 lanes. `docs/RELEASING.md` "Per release"
   and "Pre-releases" for the dispatch. The 0.4 precedent: `docs/REL040_HANDOFF.md`, `docs/REL040-rc-record.md`.
5. Briefs: `<git-common-dir>/codehealth/briefs/REL050-*.md` (and `X07a-*`, `X01-*` for the package merges).

## Roles

- `specifier`: the line file's design-lane fields (claim set, `rc_items`, phrases), once (RP §13 (1)).
- `verdict`: one pass over all claimed gates after the lapse report (RP §9.2 step 3).
- `reviewer`: X01 part A; and only if release machinery (`scripts/release_*.py`, RP) changes.
- `opus-engineer`: RC jobs, re-takes, K3, manifests (numerics-adjacent). `sonnet-implementer`: mechanical docs,
  CHANGELOG, RELEASING block, manifest moves with an exact spec.
- The orchestrator (this session) writes briefs as files, reads one result per wake, merges, logs, keeps the state
  file. At most 2 agents at a time; never resume a large-context agent; fresh agent per follow-up.

## The order

Package merges (X07a, X01 part A) -> line file (specifier, then RP.L01-L11) -> wp/REL050 into main -> K3 (RP §7.1)
-> J (re-takes incl. m05 REAL) -> C -> RC steps 1-17 -> RP §9.2 steps 1-7 -> merge C into main -> dry run -> Frank's
dispatch and PyPI approval -> post-tag working form (RP §7.4).

## Waits for Frank (Decision Desk via hub; DECISION-REQUEST, "the user" not first names, action text per option)

Every merge into main; message 1 (lapsed acceptances, claim-set change) and message 2 (new failing clause), batched
(RP §8.5); the tag, dispatch and PyPI approval. Act on a card only after `decision_desk_verify.py` prints VERIFIED.

## Milestones and self-reset

At a milestone (a package merged, K3, C, H3) or above ~100k context, with no agent of this session running: rewrite
`docs/REL050_STATE.md`, commit on wp/REL050, then run
`python3 ~/.claude/tools/self_reset.py "Resume REL050: read .claude/worktrees/rel050/.claude/skills/rel050/SKILL.md and follow it."`
and end the turn. While S19 is also open, the S19 state file names its own next action; resume it too.
