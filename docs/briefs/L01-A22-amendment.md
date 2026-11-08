# Specifier brief: L01.A22's byte pin on `models/c1/flash.py` after WIT M-6 part b

Status: brief, 2026-11-08. Small design-lane ruling. **Do not spawn sub-agents yourself.**

## The question

`wp/X10b` (`03709167`) applies Frank's Q-WIT-2 = yes (2026-11-08): it corrects the outdated near-dew sentence in
`c1.tp_flash`'s manifest text, so `src/openflowsheet/models/c1/flash.py` moves `f228a4a3f0fe…5abc5c1b` →
`b1b47c287086…bf9932e6a`; F0 M9's entry was re-recorded for exactly that file (M1–M8 equal, `--check` PASS);
`model_version` and every result are unchanged. L01.A22 (a) (`docs/derivations/L01-spec.md` §13.2, as amended by
R-566; test `tests/test_l01_records.py:410-412` `test_a22_the_c1_files_are_byte_identical_to_the_l01_base`) byte-pins
the 13 `models/c1/*.py` among 18 files, so it now fails. The WIT review (`docs/reviews/WIT-review.md` ~line 105) says the
pin needs an L01 amendment, not a silent re-pin. How should L01.A22 (a) be amended?

## Options on the table (from `docs/WIT_DECISIONS.md` D-11 on `wp/X10b`)

1. Amend §13.2 (a) to pin `b1b47c28…` for `flash.py`, recorded as WIT M-6's registered move (Frank-approved).
2. Move A22's C1 pins to clause (f)'s review-time form (as R-566 did for `coverage.json`), so a later registered move
   by another package does not break L01's test.
3. Anything better you see — the invariant is "L01 moves no C1 identity"; the pin is the means.

Constraints: no relaxed check (a change must keep a test that would catch an unintended edit of those files); the F0
corpus (M9) already guards the same bytes, which bears on whether a second byte pin is needed.

## Deliverable

A numbered amendment to `docs/derivations/L01-spec.md` §13 (quote the replaced text), a register line drafted for
**R-983** (block R-980…984; R-983/984 free), and the exact test change for the build lane to make on `wp/X10b`
(file, function, assertion). Commit on **main** (docs-only, named paths, message `docs: L01.A22 amendment after WIT
M-6b`, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; `git pull --rebase` if the push is rejected). Report ≤ 15
lines, including whether this needs Frank (default expectation: no — Frank approved the flash.py move itself).

TRS2 shared: `uptime` first; no test runs beyond reading. Out of scope: everything outside L01.A22.
