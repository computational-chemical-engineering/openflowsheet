# C2 Amendment 2 — where case_facts-v2.json is written, and how SPLIT-A09 admits it (design lane, specifier)

**Question.** Amend the C2 split registration (`docs/derivations/C2-OpenIDAES-450-split-registration.md`, F-1 section
l.206–216) so the F-1 facts file `benchmarks/m06/openidaes450/case_facts-v2.json` can be committed without breaking a
registered assertion. Decide (a) which script writes it and (b) how SPLIT-A09 admits it; then state what `split.json#/f1/status`
becomes and what generator `--check` verifies.

**Measured facts (WS1, 2026-10-22, `docs/C7_DECISIONS.md` l.64–72; parked branch `wp/WS1-f1` @ `7b5c07f`, `git show 7b5c07f`).**
- The file was written from the real archive by a `facts-v2` stage added to the **W27 generator**
  (`scripts/m06_w27_registration.py`): 450 cases, 3,725 topology units, sha256 `57d43acb…`, kind sets equal to v1's
  `topology_kinds`; v1 `facts --check` and split `--check` byte-identical.
- The full gate then failed exactly two registered assertions:
  1. SPLIT-A09 (`tests/test_c2_openidaes450_split.py:176`): v2 names every held-out case id, and is not in
     `c2_openidaes450_split.ALL_CASE_FILES` (the allowlist) nor under `gen.HELDOUT_SEGMENT`.
  2. W27 P2 (`tests/test_m06_w27_harness.py:314`): the W27 generator's SHA-256 is pinned
     (`preflight.REGISTERED_SHA256`); adding the stage changed it.
- v0.2's W27 registration stays unchanged (Frank, L01-Q1 answer). C9 (on `main`) added a W27 registration version 2
  for the NEXT release (`docs/C9_DECISIONS.md`, R-570…R-574, R-580) — read it; it may be the natural home or a constraint.

**Constraints.** Never rewrite `case_facts.json` (`coverage.json` pins it). No relaxed check: A09's purpose (no held-out id
leaks outside named places) must survive — an allowlist entry must be as narrow as the existing ones. Don't re-pin v0.2's W27
generator unless you show that is the least-change option and say what else it moves. Frank's split answers (C2-Q1/Q2,
`docs/FRANK_QUESTIONS.md` top) are settled.

**Deliverable.** Commit on branch `wp/C2-A2` (worktree `.claude/worktrees/c2-a2` from `main`): the amendment section in the
registration, register entries (next free R-numbers; grep `^## R-` in `docs/decision-register.md`), any test-spec change as
numbered assertions, and a ≤15-line work order for the build lane (which file holds the writer, which test changes, what
`--check` covers, the expected sha `57d43acb…` re-verified). Do not implement; do not merge. Docs-only: no local gate needed.
Report ≤150 words. Trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` /
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`.
