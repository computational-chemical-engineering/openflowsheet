# S19 standing rules (every worker reads this; a brief names it instead of repeating it)

## The user's constraints (verbatim where quoted)

- Frank, 2026-11-14: "My purpose now is to refactor the code such that code health becomes excellent and we can
  safely move on with the development to the future. This is the goal. Do what it takes."
- Frank, 2026-11-13: outward interfaces may be renamed and restructured, "better to do the design well now"; by ADR
  0076 (design lane), no shims left at the end. Until a step is an ADR 0076 step, old import paths stay as
  re-exports and no public name is removed or renamed.
- Behaviour is bitwise identical: every numeric result, message, order of side effects and exception. F0
  (`scripts/corpus_identity.py --check`), the MCP digest and the tests decide; a reading reviewer covers the rest.
- Repository rules in `CLAUDE.md` bind, except the agent count (Frank, 2026-11-14: more agents allowed for S19):
  about 150k context per engineer, never resume a large-context agent, stage named paths, merge commits only, never
  set `reviewed` yourself. No em dashes in any text.

## Settled

- Tool: cce-code-health `d542005` in `.venv-codehealth` (`requirements-codehealth.txt`). Config
  `.codehealth/config.toml`: scope `src/openflowsheet/*`; layer rules `application-layers` and `repo-layers`; forbid
  rules; frozen paths (including F0's 35 M9 modules from `scripts/codehealth_frozen.py`: never edited before W5).
- Design: `docs/briefs/S19-architecture.md` (phases, table 4.1 with the expected `codehealth arch` numbers per
  step, splits, sensitivity tiers and the arithmetic rule of section 5). ADR 0076 (proposed) covers interface steps.
- S17's mechanics and playbook apply: `docs/S17_RULES.md` "Git" and "Evidence standard", `.codehealth/playbook.md`
  (rules for new code, restructure rules, when-not rows), `docs/briefs/S17-architecture.md` section 3 (split
  mechanics). Read them; where this file differs, this file wins.

## Rejected (do not reopen)

- Editing `.codehealth/*` (except a restructure plan file, see Git), tests, benchmarks, schemas or requirements in a
  step. `codehealth: allow` suppressions.
- Lowering debt by fragmenting logic, moving complexity into a helper of equal complexity, bundling unrelated
  parameters, or hiding branches in data structures.
- In tier S1 files (design note section 5): any change in the order of floating-point operations: no reassociation,
  no hoisted sums, no `sum()` versus loop swaps, no NumPy for Python arithmetic.

## Ownership

- The orchestrator (the session) owns `wp/S19`, the state file, the decisions log, the config, merges and pushes.
- An engineer works only in its own worktree and branch (`wp/S19-<lane>`), makes steps and commits accepted ones, and
  writes restructure plans for its own steps; no push, no merge, no config, no docs except its report.
- A reviewer reads diffs only and writes nothing.

## Git

- One accepted step, one commit: `refactor(<package>/<file>): <what>` or `restructure(<package>): <what>` with the
  trailers `Codehealth-Class`, `Codehealth-Recipe`, `Codehealth-Debt` (refactor) as in S17, plus the
  session's Co-Authored-By line.
- A restructure step: first a plan commit (`.codehealth/restructure/<name>.toml`, S17 format, the expected arch
  numbers from table 4.1 re-derived at its base), then the step commit, gated with
  `.claude/skills/s19-refactor/gate.sh --restructure <plan commit> .codehealth/restructure/<name>.toml <label>`.
  A mismatch of the expected numbers stops the lane: report, do not adjust the plan to fit.
- Commit, then gate (S17 D14); on a failed gate `git reset --hard <last accepted>`. Never bare `git stash`.
- Patch safety (ADR 0076 review): after every move or split, `python3 .claude/skills/s19-refactor/patch_noop.py .`
  must report 0 flagged patches (a test patching `module.name` where `module` neither defines nor uses `name` is a
  silent no-op the gate cannot see; 0 of 243 at d90b498f). A flag stops the step; the orchestrator retargets the
  test outside the gate. Quote its summary line in the step's commit message.

- Retarget before the plan (S19_DECISIONS, 2026-11-14): when a move needs tests, scripts or test data to follow
  it (patch targets, file paths, allowlist entries), the retarget is its own commit placed BEFORE the plan commit:
  retarget, plan, step; gate against the plan commit. A retarget commit changes only where a patch or path points
  (a name patched in a module that keeps a call site and in one that gains one is patched in both); never an
  assertion, an expected value or a test case. An engineer writes one only when its brief or the orchestrator
  authorises that step's retarget, and a `reviewer` reads it before the lane is merged.

## Running jobs

- Gate: `.claude/skills/s19-refactor/gate.sh` (same modes as S17's: step, `--no-gain`, `--revert`,
  `--restructure`, `--self-test`). One summary line; logs and JSON under
  `$(git rev-parse --git-common-dir)/codehealth/runs/s19-gates/`; stop with `kill -INT "$(cat <tag>.pid)"`.
- Run it in the background and wait for the completion notice; read logs only on failure (`grep`, `tail`).
- Until the map is built after W2, every gate runs the full suite (about 15 min, longer when two lanes gate at once).

## Evidence standard

- Every attempt is logged with `codehealth log --gate-json <json> --campaign s19 --target <path::qualname or plan
  name> --recipe <id> --model <name>` after the gate; never by hand. Numbers come from tool output.
