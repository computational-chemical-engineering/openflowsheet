# X07a-WO2: the CI legs of X07a to green, or to typed limits (roadmap 0.5)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x07a`, branch `wp/X07a`,
head 37049c8a. Work only there. Do not spawn sub-agents yourself. Budget about 150k tokens of context: at the cap,
commit what is complete, rewrite the Position section of `docs/X07a_DECISIONS.md` with where you stopped, and end.

Authorization and scope are those of `docs/briefs/X07a-WO1.md` (read its "Scope", "Deliverables", "Stop and report
instead of choosing" and "Acceptance": they bind this work order unchanged). You may push `wp/X07a` to `origin` to run
CI. Never push, merge into or rebase `main`; never tag. Read `docs/X07a_DECISIONS.md` first (D-1 to D-12, Q-1, Q-2,
the platform-limit table, Position).

## Facts (orchestrator, 2026-11-20 ~02:10 CET)

- Run 44629325836 (head d2fb0252): ubuntu-latest, ubuntu-24.04-arm and default-install green; macos-latest failed in
  steps "Run checks" and "F0 corpus identity (X07a)"; codehealth failed in "Debt ratchet against origin/main
  (informational)"; windows-latest still `in_progress` at step "The server extra and its licences (G19)" about 2.5 h
  after the push (a hang, or the step waiting on input).
- Run 44629506428 (head 37049c8a, the manifest and Position commit only): **every check leg failed**, ubuntu-latest,
  ubuntu-24.04-arm and default-install included ("Run checks", "Run the tests without the extra"); codehealth as above.
  37049c8a adds `evidence/X07a/d2fb0252.../manifest.json` and docs, so a manifest or docs check is the first suspect;
  establish it from the log, do not assume it.
- Q-1 (pywin32 licence, rights: Frank) and Q-2 (F0 M7 per-platform verdicts, ADR 0067 D7) stay failing for the design
  lane: do not choose them. Each failing step that is only Q-1 or Q-2 is reported as such.

## Work

1. Read the failing jobs' logs narrowly (`gh run view <id> --log-failed | grep -n -m 40 'FAILED\|Error\|error:'`, then
   `sed -n` around the hits). Never dump a whole log.
2. Fix the ubuntu and default-install failures of 44629506428 first: the Linux legs are the merge condition.
3. Windows: find why G19 hangs (cancel the stuck run with `gh run cancel` if it still runs). A hang must end in a
   bounded failure or a pass, never a silent wait; then read the first full Windows pytest run.
4. Classify each new Windows or macOS failure: portability bug (fix it, behaviour on Linux bitwise unchanged) or
   platform limit (a row in the table with its run id, refused typed or skipped naming the limit). No blanket module
   skip, no relaxed tolerance, no removed case.
5. Codehealth job: say whether "Debt ratchet (informational)" failing is expected for a branch that adds a module
   (WO1 measured debt 55.30 -> 58.30), or a real failure; fix it only if it is not informational by design.
6. Push, read the new run, repeat while within budget. Record each choice as a DECISION line in
   `docs/X07a_DECISIONS.md`.

## Acceptance (report each with the command and its one-line result)

As X07a-WO1 "Acceptance", plus: both ubuntu legs and default-install green on the pushed head (run id); windows-latest
and macos-latest green, or red only on Q-1 / Q-2 steps, each such step named with its first error line. Manifest:
`tested` only when all four legs are green; otherwise it stays `implemented` with the run id and the open questions.
Never `reviewed`.

## Report (200 to 300 words)

Commits, run ids with per-leg verdicts, each new platform-limit row, what is left failing and why, open design-lane
questions. Detail goes into `docs/X07a_DECISIONS.md`, not the report.
