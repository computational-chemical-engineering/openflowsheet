# LINE06 X06-WO3: further solve policies (ADR 0078 D4)

Build lane, `opus-engineer`. **Do not spawn sub-agents yourself.** Rules: `docs/LINE06_RULES.md` (read it first,
including the surface-suite rule: `tests/test_t07_*.py`, `tests/test_t08_w2_*.py`, `tests/test_m07a_surface_chain.py`).
Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x06`, branch `wp/X06` (head `7ca42a0e`: WO1, WO2
done, ADR 0078 Accepted). Another engineer may work on F2 in `.claude/worktrees/f2`; leave it alone. Budget about
150k context: at the cap, commit what is complete, write where you stopped in `docs/X06_DECISIONS.md`, and end.

## The task

Build X06-WO3 as ADR 0078 states it (`docs/adr/0078-X06-application-capabilities.md`, **Accepted**; do not edit it):
D4 (lines ~162-205: project-registered, immutable, `user.`-named solve-policy documents stored as job-less artifact
rows; every free member validated against the solver's registries at registration; Q5: registration needs the
`draft` right; Q6: the seven benchmark-registered policies stay `unsupported`) and work-order row 3 (line ~392):
`orchestrator/policy_validation.py`; `application/{solve_policy_registry,solve_policy_service}.py`; `admission.py`,
`validation_service.py`, `jobs/runner.py` (D4.6); `inspection_service.py` (`get_project`); `contract.py`
(`SolvePolicies`), `operations.py`, `authz`, `local.py`, descriptions, `application-results` `$defs`; layers;
catalogue; the served-digest re-pin (`X06_SERVED_SHA256`, `without_x06`, chain link c_12's `D_12`); the new operations
as conformance steps on all six clients (ADR D6).

## Facts established

- WO1 (MCP over HTTP) and WO2 (branches) logs: `docs/X06_DECISIONS.md`. Current pins: `X06_SERVED_SHA256` =
  `7e8393a5…` (decomposes onto F3's `f7ec3c94…`); chain link c_12 (R-1073) in `scripts/m07a_rc.py`.
- F0 on wp/X06 must stay: M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42. The verifier never reads
  the solve policy, and bundles replay without the project (D4's safety argument): a test must show both.
- ADR Q7 is measured here: E-X06-12 decides whether any path dispatches on a policy's name rather than its content;
  on a difference, stop and report to the design lane.
- `tests/test_t08_w2_description_reviews.py::test_every_description_is_reviewed_by_both_lanes` is red by design until
  the reviews are recorded (five texts from WO2; yours add to them). Do not mark any review; list your new or changed
  description files in the report.

## Acceptance (report each)

1. E-X06-11 to E-X06-15 and E-X06-22 (ADR "Exit tests"): test names and counts; Q7's answer with its evidence.
2. The surface suites, `tests/test_x06_*.py`, MSG and doc-page tests: counts; 0 failed except the description-review
   gate (name the texts it lists). Run after your last commit.
3. ruff check, ruff format --check, `mypy src` clean.
4. F0 PASS with the counts above, at your last commit.

## How

Commit named paths on wp/X06, messages `X06-WO3: ...`; DECISIONs in `docs/X06_DECISIONS.md`. Long runs through
`/home/eajfpeters/Code/OpenFlowsheet/.claude/skills/line06/run.sh <name> <command>`. No push, no merge.

## Stops (report rather than choose)

A path that dispatches on a policy's name (Q7); a change to a record, run identity, the store schema or a request
hash; a registered policy's behaviour changes; the ADR contradicts the code; a test passes only by relaxing a check.

## Report (200-300 words)

Per acceptance item: pass/fail and the number; DECISIONs (one line each); commits; the description files touched;
anything for WO4.
