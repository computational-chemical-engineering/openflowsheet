# S17 standing rules (every worker reads this; a brief names it instead of repeating it)

## The user's constraints (verbatim where quoted)

- Frank, 2026-11-12: "When I come back I hope to see a very much more healthy code." The campaign runs unattended.
- Refactor only, bitwise: a step changes structure, never behaviour; every result stays bitwise identical
  (`docs/code-health.md`, "Campaign rules" 1 to 6, binding).
- Repository rules in `CLAUDE.md` bind: at most 2 agents at a time; about 150k context per engineer; never resume a
  large-context agent; stage named paths; no squash; never set `reviewed` on your own package.
- No em dashes in any text.

## Settled

- Tool: cce-code-health at `7628e737` in `.venv-codehealth` (D10). Config `.codehealth/config.toml` (D1 to D11).
- The `tests` tier is S16's selection in `.venv-testmap` with the map of the campaign base (`OFS_MAP_BASE`, D11).
- Scope: `src/openflowsheet/application/*.py`. Frozen and forbidden paths: as the config says; the gate enforces them.

## Rejected (do not reopen)

- Editing `.codehealth/*`, tests, benchmarks or requirements inside a step.
- `codehealth: allow` suppressions.
- New public names, new modules, changed signatures or messages (a split is proposed to Frank, never done).
- Lowering debt by fragmenting logic, by moving complexity into a helper of the same complexity, by bundling unrelated
  parameters, or by hiding branches in data structures (the reviewer rejects these).

## Ownership

- The orchestrator (the session) owns `wp/S17`, the state file, the decisions log, merges and pushes.
- An engineer makes steps and commits accepted ones on `wp/S17` in `.claude/worktrees/s17`, and nothing else: no
  push, no merge, no config, no docs except its own report.
- A reviewer reads diffs only and writes nothing to the branch.

## Git

- One accepted step, one commit: `refactor(application/<file>): <what>` with trailers `Codehealth-Class: refactor`,
  `Codehealth-Recipe: <id>`, `Codehealth-Debt: <before> -> <after>`, plus the session's Co-Authored-By line.
- A failed step: `git checkout -- <files>`; never commit it. Never `git stash` bare (shared stash stack).
- Docs and config changes are separate commits by the orchestrator, outside steps.

## Running jobs

- Gate: `.claude/skills/s17-refactor/gate.sh <last accepted sha> <label>`. One summary line; full log and JSON under
  `$(git rev-parse --git-common-dir)/codehealth/runs/s17-gates/`; the PID in `<tag>.pid`; stop with `kill -INT PID`
  (the gate then kills its tier's process group).
- Run the gate in the background and wait for its completion notice; read the log only on failure (`grep`, `tail`).
- A gate takes minutes when the selection is small and about 20 minutes on a full-suite fallback.

## Evidence standard

- Every accepted step: gate exit 0, debt lower (from `codehealth diff`), one line in
  `$(git rev-parse --git-common-dir)/codehealth/runs/s17.jsonl` in the skill's format.
- Every attempt is logged, failures included, with the failing tier.
- Numbers come from tool output, never from memory.
