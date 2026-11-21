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
- 2026-11-21 ~15:30, REL050-WF (opus-engineer, Opus, ~134k): 1dee789c `--f1-f3` + `tests/test_rel_wheel_f1_f3.py`,
  71a7328e Q-B3 phrase test; 140 passed 1 xfailed; controls a-d fail their checks; other commit -> exit 2. At HEAD
  the item exits 1: WF-1..WF-3 PASS (registry_sha256 fc0af96b... both sides, N 149, wheel 55349000...), WF-4 FAIL:
  wheel 9 legacy records vs checkout 149. Checked: ADR 0061 D8 (lines 274-280) says only m01/s10 component files are
  package data, so 9 is the specified behaviour; D-5's WF-4 contradicts D8. Not a packaging fault; nothing relaxed
  (strict xfail). DECISION: the WF-4 ruling is folded into Q-D1's scoped reviewer pass (one design pass, RP §13 (3);
  CLAUDE.md batching) -> `<briefs>/REL050-R-machinery.md`. Alternative: a second specifier pass. Reversible by: a
  specifier pass if the reviewer declines to rule.
- 2026-11-21 ~15:50, REL050-R (reviewer, Opus, ~153k; c1c61a68, `docs/reviews/REL050-R-machinery.md`): merge after
  F-1..F-3. Ruling 1: WF-4 restated (each side's (id, sha) pairs equal the index records over that side's files:
  checkout N 149, installed package-data N_pkg 9 via `t08_dist.expected_package_files`; controls e, f added); the
  `WHEEL-F1-F3` `assertion` string in the line file changes (F-2; `rc_items` already in `changed`, before K3).
  Ruling 2: controls on a scratch copy sufficient. F-3: bound the page loop. Rest of scope sound (281 passed).
  -> REL050-WF2 (opus-engineer; `<briefs>/REL050-WF2-fixes.md`).
- 2026-11-21, X07a CI 44902051410 at bd0b7df5: all legs success (Linux x2, macOS, Windows, codehealth, identity)
  -> X07a-WO20 manifest move (opus-engineer; `<briefs>/X07a-WO20-manifest.md`).
