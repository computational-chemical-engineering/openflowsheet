# S17 standing rules (every worker reads this; a brief names it instead of repeating it)

## The user's constraints (verbatim where quoted)

- Frank, 2026-11-12: "When I come back I hope to see a very much more healthy code." The campaign runs unattended.
- Refactor only, bitwise: a step changes structure, never behaviour; every result stays bitwise identical
  (`docs/code-health.md`, "Campaign rules" 1 to 6, binding).
- Repository rules in `CLAUDE.md` bind: at most 2 agents at a time; about 150k context per engineer; never resume a
  large-context agent; stage named paths; no squash; never set `reviewed` on your own package.
- No em dashes in any text.

## Settled

- Tool: cce-code-health at `5646ad1a` in `.venv-codehealth` (D13). Config `.codehealth/config.toml` (D1 to D13).
- The `tests` tier is S16's selection in `.venv-testmap` with the map of the campaign base (`{ref_base}`, D11, D13).
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
- Commit, then gate (D14): a step is committed provisionally and gated against the last accepted commit (a test,
  `test_m07_journey.py::test_a21...`, fails on any uncommitted change under `src/`). On a failed gate,
  `git reset --hard <last accepted>`: no failed step stays in history. Never `git stash` bare (shared stash stack).
- Rejected steps found by a review are undone by the orchestrator (`git revert`, conflicts resolved to the pre-step
  code) and gated with `gate.sh --revert <rejected sha>` (D15), then logged with `codehealth log --result
  review-reject --reason "<review N: reason>"`. A names-, docstring- or order-only follow-up from a review's notes is
  gated with `gate.sh --no-gain <last accepted sha>` (behaviour tiers, no gain check) and logged with `--result
  accepted-neutral --reason "<review N note>"` and recipe `review-note`. `codehealth log --head <step sha>` logs a
  step after a later commit (D16).
- Docs and config changes are separate commits by the orchestrator, outside steps.

## Running jobs

- Gate: `.claude/skills/s17-refactor/gate.sh <last accepted sha> <label>` (runs `gate --ref-base <CB>
  --require-gain`: exit 0 means accept, debt strictly lower). One summary line; full log and JSON under
  `$(git rev-parse --git-common-dir)/codehealth/runs/s17-gates/`; the PID in `<tag>.pid`; stop with `kill -INT PID`
  (the gate then kills its tier's process group).
- Run the gate in the background and wait for its completion notice; read the log only on failure (`grep`, `tail`).
- A gate takes minutes when the selection is small and about 20 minutes on a full-suite fallback.

## Evidence standard

- Every attempt is logged with `codehealth log --gate-json <the gate's json> --campaign s17 --target
  <path::qualname> --recipe <id> --model <name>`, run after the gate (for an accepted step, HEAD is the step's
  commit; for a failed one, before the reset). Never hand-write a log line. The tool infers accepted, gate-fail
  (with the tier) or no-gain.
- Numbers come from tool output, never from memory.
