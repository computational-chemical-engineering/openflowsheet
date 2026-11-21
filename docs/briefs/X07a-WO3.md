# X07a-WO3: replay platforms and floating-point differences on the new legs (ruling section 6)

Build lane, `opus-engineer`. Worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/x07a`, branch `wp/X07a`,
head 8b9e8f86. Work only there. Do not spawn sub-agents yourself. Budget about 150k tokens of context: at the cap,
commit what is complete, rewrite the Position section of `docs/X07a_DECISIONS.md`, and end.

Authorization, push rules and the scientific-conduct limits are those of `docs/briefs/X07a-WO1.md` (read its "Scope",
"Stop and report instead of choosing" and "Acceptance"); they bind unchanged. Never push, merge into or rebase
`main`; never tag. You may push `wp/X07a` to run CI.

## The spec

`docs/X07a-platform-ruling.md` (the design-lane ruling, commit 8b9e8f86) is the spec: section 4 (R1, R2 with rules
P1 to P5), section 5.1 (ADR 0007 Amendment 3, status proposed), and **section 6 (changes C1 to C6, acceptance A1 to
A12, stop conditions)**. Implement section 6 as written. Section 8's defaults apply to Q-4, Q-6, Q-7 and Q-8 (the
orchestrator takes Q-8's default: X07a builds no part of ADR 0067 D7); Q-5 (registering macOS or Windows) is Frank's
and its default holds: not in 0.5, so `REGISTERED_PLATFORMS` stays unchanged.

ADR 0007 Amendment 3 is proposed, not accepted: build C1 on this branch, record in the manifest and in
`docs/X07a_DECISIONS.md` that X07a's merge into `main` waits on Frank accepting it (a Decision Desk card is being
filed). Do not edit the ADR's status.

Also read `docs/X07a_DECISIONS.md` (D-1 to D-19, the platform-limit table, Position). Run 44652504290 (head a24a0bf3)
is A10's Linux baseline. The windows-latest leg of that run may have finished since: read it first.

## After section 6, if budget remains

Continue WO2's classification of the remaining Windows failures outside the Q-2/Q-3 class (largest cluster
`test_m02_experiments.py`, the child ending `environment_unavailable`; then X02 external, V17 reference, M05 host keys):
portability bug (fix, Linux bitwise unchanged) or platform limit (a row with its run id). Same rules as WO2.

## Report (200 to 300 words)

Commits; A1 to A12 each with its command and one-line result; run ids with per-leg verdicts; what is left failing and
why; any stop condition hit. Detail goes into `docs/X07a_DECISIONS.md`, not the report.
