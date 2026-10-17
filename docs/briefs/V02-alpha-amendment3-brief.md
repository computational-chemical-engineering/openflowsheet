# Design-lane ruling round: V02 alpha verdict findings (Amendment 3)

One batched round. Branch `wp/V02-alpha-gate` (worktree `.claude/worktrees/alpha-gate`). C_α¹ = `6fec822`
(branch `wp/V02-alpha-rc1`). Verdicts: `docs/reviews/V02-alpha-verdicts.md` (`fffb0e4`): 8 PASS, V14 FAIL (b),
BLOCKED V13 (e), V17 (a), W21 (c) — each on one of Frank's pending ADR 0028 answers (V17 carry, M02 N1; V14 (b) D3
acceptance and N3 also pending). Findings A1–A10 at l.394–430 of the verdicts. Spec: `docs/derivations/V02-alpha-release-spec.md`
(Amendment 2 is §18 at l.1070).

Rule each finding A1–A10 (read them in the verdicts file). In particular:
- **A1** (before any tag): the alpha envelope lacks the limitation row for the unmeasured aarch64 reactor run (spec §4
  rule 4, Q1). The envelope lives under `benchmarks/`, frozen at C_α¹. Decide: re-cut C_α² with the row, or a spec
  amendment that lets the row travel outside the frozen tree (and why that is not a narrowing). A re-cut costs a full
  RC re-run (≈ 3 h, CI + local steps 11–12); prefer one re-cut that carries every fix the round requires, if any.
- **A2**: T6 wants Frank's answers dated on or after the verdict's Judged date, while BLOCKED rows need a re-judgement
  after he answers. Fix the date rule so a later answer plus re-judgement is valid.
- **A3, A4**: M07a.A61's expectation and the `tested` ordering (§9.2 steps 4–5 vs A52).
- **A5**: CHANGELOG `## v0.2.0a1` draft defects — say what the text must state (the build lane edits it).
- **A6–A10**: rule or record as findings for a later RC / 0.2.0.
Also the build-lane choices B-AM2-6, B-AM2-9, B-AM2-10 (`docs/design/V02-alpha-build-decisions.md`): confirm or reverse.

Rules: never move a tolerance, band or classification rule on the outcome. Do not re-judge verdicts (that waits for
Frank's answers). No production-code edits. Write **§19 Amendment 3** of the spec with markers, register entries
**R-370…R-379** (`docs/decision-register.md`). Commit on `wp/V02-alpha-gate`, named paths, trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`,
push. Report ≤ 300 words: one line per ruling, whether a re-cut is needed, the build-lane action list.
