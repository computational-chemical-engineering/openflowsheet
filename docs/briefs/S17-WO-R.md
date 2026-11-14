# S17 restructure work order: module splits (D18)

You are an engineer on OpenFlowsheet's S17 code-health campaign. Do not spawn sub-agents yourself.
Your splits: given in the launch message (one commit per split, in the order given).

## Read first

1. `docs/S17_RULES.md` (standing rules; binding) and `docs/S17_DECISIONS.md` D18, D20 and the last entries.
2. The design note `/home/eajfpeters/Code/OpenFlowsheet/.git/codehealth/design/S17-architecture.md` section 3:
   "Mechanics common to R1 to R4" and your split's paragraph; section 5 (verification gates, numbers fixed).
3. Your split's approved plan, committed at `.codehealth/restructure/split-<id>.toml` in the worktree. Its comment
   block (moved names per file, re-exports, lazy imports that move, retargets, risks, the plan review's changes)
   overrides the design note where they differ. Never edit a plan or the config: they are the orchestrator's.
4. The tool doc `/home/eajfpeters/Code/cce-code-health/plugins/cce-code-health/skills/refactor-loop/SKILL.md`,
   "Restructure".

## Setup

- Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/s17`, branch `wp/S17`. Work only there.
- Tool: `/home/eajfpeters/Code/OpenFlowsheet/.venv-codehealth/bin/codehealth` (0.1.1.dev46+ga34015853, D20).
- The plans and the new modules' layer entries are already in HEAD (the orchestrator's config commit), so every base
  holds them.
- Gate one split (D14: commit provisionally, then gate; on failure `git reset --hard <last accepted>`), in the
  background, waiting for its notice:
  `.claude/skills/s17-refactor/gate.sh --restructure <last accepted sha> .codehealth/restructure/split-<id>.toml <label>`
  (restructure mode, no gain check; the tests tier runs the full suite, 10 to 20 min). Log it with
  `codehealth log --gate-json <json> --campaign s17 --target <old file>::<first moved name> --recipe split
  --model <your model> --result accepted-neutral --reason "<plan id>: <what moved>"`.
- R5 has no plan: refactor mode, `gate.sh --no-gain <last accepted sha> r5`, log `--recipe move-private
  --result accepted-neutral`.
- Commit `restructure(application/<old>): <what>` with trailers `Codehealth-Class: restructure`,
  `Codehealth-Recipe: split`, `Codehealth-Debt: X -> X` (file debt of the old file before, total of old plus new
  after), then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Checks before each gate (report each)

- Moved-definition identity: for each moved name, `ast.dump` of its top-level statement at base (old file) equals
  that at head (new file). Script it.
- `git diff --stat` lists only the plan's files and the named importers.
- `codehealth arch` matches the plan's expected numbers for this point in the order (R1 8/33, R2 6/14, R3 4/10,
  R4 3/8, R5 2/6: violations / cycle edges). A difference: stop and report before gating.
- ruff check, ruff format --check, mypy on the touched files; the plan's extra checks (R1: `mkdocs build --strict`
  as CI runs it; R3: tests/test_s11_thermal_binding.py and tests/test_s11_column_unit.py each in isolation).

## Behaviour

Bitwise. Definitions move verbatim in their original order with the `#:` comments above them; no `__all__` in a new
file; never touch an old `__all__` or remove an import it lists. Every old import path stays valid as a re-export
(`from ... import (Name as Name, ...)`). Lazy imports move with their function unchanged. No new public name beyond
the plan's `new_public`.

## Stop

When your splits are done, or on a STOP condition in the plan, or after about 150k tokens of context, or after two
failed gates on one split. Leave the tree clean at the last accepted commit. No push.

## Report (about 20 lines)

Per split: commit, gate result, arch numbers, identity check, diff stat summary, anything for the orchestrator.
