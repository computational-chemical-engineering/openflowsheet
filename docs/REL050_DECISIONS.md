# REL050 decisions and build log (append-only; grep, never read whole)

- 2026-11-20, R-1065 (Frank): the smaller 0.5 (X07a, F1, F3, X01 plugin docs). Commits 84a08a84, cc6e685e.
- 2026-11-21 ~14:45: Frank asked "Will you take care of the release?"; the OpenFlowsheet-TR09 session takes it.
  Campaign files: REL050_STATE.md, REL050_RULES.md, this log, `.claude/skills/rel050/SKILL.md`; briefs in
  `<git-common-dir>/codehealth/briefs/REL050-*.md`.
- DECISION: S19 relative to K3 -> S19 merges into main only if its card is signed before K3, else after the tag.
  Alternative: hold K3 for S19. Reversible by: Frank's answer in message 1.
- 2026-11-21 ~15:00, X01 review (reviewer, Opus, ~122k; `<briefs>/X01-R-WO1A.md`): merge after fixes; blocker F3-stale
  guide; X01-WO2 (sonnet-implementer, ~71k) applied all, 1bd587ed + 5634fa7f, CI 44909945712 / Site 44909945705.
  Q-1..Q-3 defaults stand (none for Frank).
- 2026-11-21 ~15:25, REL050-L1 (specifier, ~283k; `<briefs>/REL050-L1-line-file.md`): line file draft bc6e6fe9, claim
  set unchanged, new rc_item WHEEL-F1-F3, Q-F1 and Q-F2 for message 1 (defaults stand), Q-D1 a scoped reviewer pass.
- 2026-11-21 ~15:00 (clock), main d29f1a50 merged into wp/REL050 (c4f7c650): note §7 loader check RP.L01-L11 PASS at
  HEAD; ADRs 0007, 0057, 0060, 0061, 0076, 0077 Accepted on the branch. Next action 1 met.
- 2026-11-21, REL050-WF dispatched (opus-engineer; `<briefs>/REL050-WF-wheel-f1-f3.md`): D-5 `--f1-f3` (WF-1..WF-5,
  controls a-d) and Q-B3's phrase test (default taken). Q-B1 default stands (0.4-era packages not added).
