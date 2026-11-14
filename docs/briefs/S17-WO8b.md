# S17 work order 8b: local.py, revision_run.py, revision_continuation.py

You are an engineer on OpenFlowsheet's S17 code-health campaign. Do not spawn sub-agents yourself.

## Read first (in this order)

1. `docs/S17_RULES.md` (standing rules; binding). Note D14, D15 and D20 (the `[architecture]` ratchet: a step that adds a layer violation, an import cycle edge or a forbidden import fails the gate): commit each step provisionally, then gate it; on a failed
   gate `git reset --hard <last accepted>`. Log every attempt with `codehealth log` (never by hand).
2. `.codehealth/playbook.md` (this campaign's rules 1 to 16, accepted forms and "when not" entries from reviews 1 to 9). Follow them.
3. The tool's loop: `/home/eajfpeters/Code/cce-code-health/plugins/cce-code-health/skills/refactor-loop/SKILL.md` and
   `playbook-seed.md` next to it. The repository's rules override it where they differ.
4. `docs/code-health.md`, "Campaign rules" and the tier table.

## Setup

- Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s17`, branch `wp/S17`. Work only there.
- Tool: `/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth` (0.1.1.dev46+ga34015853, D20).
- Coverage strength: `/home/eajfpeters/Code/OpenFlowsheet/.venv-testmap/bin/python scripts/test_impact.py select
  --base 3fa719737549094622ce3b124b2f8341c555f335 --lines path:a-b` (scan JSON functions now have `end_line`).
- Gate one step: `.claude/skills/s17-refactor/gate.sh <last accepted sha> <label>` in the background; wait for its
  completion notice. It runs `gate --require-gain`: exit 0 means accept. A step that cannot pass without new files or
  public names is out of scope (restructure comes later, D18): note it in your report instead. It prints the gate JSON path; pass it to
  `codehealth log --gate-json <json> --campaign s17 --target <path::qualname> --recipe <id> --model <your model>`.
- The first step's base is HEAD when you start (an orchestrator commit after the last accepted step).

## Targets (`codehealth scan` at 18562395; re-scan at your first base)

1. `src/openflowsheet/application/local.py::LocalApplication._prepare` (line 1983): debt 11.6, cognitive 23.
2. `src/openflowsheet/application/revision_run.py::reproduce_bundle` (line 1280): debt 10.5, cognitive 23. Review 1
   noted it is a ladder of check-and-return rungs: restructure the ladder whole (accepted form b5451805) or leave it.
3. `src/openflowsheet/application/revision_continuation.py::not_continuable` (line 228): debt 7.0, cognitive 22.
4. `src/openflowsheet/application/local.py::LocalApplication._admit` (line 947): debt 9.1, only if a clean step exists.

local.py's public surface (the `LocalApplication` methods without a leading underscore) is redesigned later (D19):
touch only private methods and module functions.

Several small steps per function. Re-scan after each accepted step. Gates run the full suite (about 10 to 14 min).
Do not edit the tree while a gate runs (D14). No new files, no new public names, no moved public functions; the
`[architecture]` ratchet (D20) fails any new upward import. Skip a target when the playbook's when-not rows say so
and say why in the report; a skipped target is a fine outcome.

## Lessons from reviews 1 to 9

All are in the playbook (rules 1 to 16, accepted forms, when-not rows). In short: extract along a named concept with its citation;
whole early-return branches and ladders as one unit; pure helpers, the caller owns side tables; names cover every
effect; state any statement or lazy import that moves across an early return in the commit message; stop extracting
when the remainder only threads the same locals or a step drops less than about 2 points; no parameter object over
locals created in different phases; helper types no weaker than the values they carry (no `Any` where mypy
inferred a type; `TYPE_CHECKING` imports are fine); a helper extracted later goes in call order; the first phase
helper of a caller is listed in its docstring; `_x_refusal` returns `Unbound | None` (or the module's analogue).

## Behaviour

Bitwise: same order of side effects, same exceptions and messages, same string literals (the gate counts the literal
multiset of touched files), same public names and signatures. New helpers are private (`_name`) in the same module.
Transaction and job side effects, store writes and their order, refusals and their messages are behaviour.

## Stop

When the targets are done, or after about 150k tokens of context, or after three consecutive failed attempts.
Leave the tree clean (`git status` empty) at the last accepted step. No push.

## Report (about 20 lines)

Per attempt: target, recipe, result, debt before and after, commit sha. Both files' debt before and after. Anything
that needs the orchestrator's decision.
