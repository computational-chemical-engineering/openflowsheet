# S04 (was L01) — two rulings before WO-D1-B (design lane, `specifier`, small pass)

Branch `wp/S04` (worktree `/home/user/ofs-s04`) = `wp/L01` + `wp/D1` (`main` + S01, S02, C4, C7, D1). Package id S04
per R-565 (D1). With `main` merged in, two tests fail; each needs a ruling, not a code guess.

1. **L01.A22 pins `coverage.json`.** `tests/test_l01_records.py:448-456` asserts `PINNED` SHA-256s, including
   `benchmarks/m06/openidaes450/coverage.json` = `b69626c7…`. C7 re-took W27's coverage at `0.3.0.dev0` (R-460;
   `docs/C7_DECISIONS.md:25-30`), so it is now `aa89cdd6…`. C2's split met the same change with Amendment 1 (R-555:
   read the pinned blob from git history and check the read fields). Rule what A22 should assert about
   `coverage.json` (its intent: L01 moves no C1/W27 identity) — e.g. drop it from `PINNED` and assert L01's commits do
   not touch it, or follow R-555's pattern — and amend L01 spec A22 accordingly.
2. **T08.A20 providers axis.** `tests/test_t08_w2_support_envelope.py:62-70` (`check_a20`): "envelope ['pr-c1-v1',
   'syn001'] != code ['pr-c1-v1', 'pr-lib-v1', 'syn001']". `pr-lib-v1` is library-only (not selectable until L01 WO-3,
   L01 spec §4.3). R-561 (D1) rules library-only *models* stay U04 until bound. Rule the providers-axis analogue:
   list `pr-lib-v1` in the envelope as an unsupported/library-only provider row (which row kind, which typed
   outcome), or exclude unexposed providers from the axis by rule — and amend T08 release spec §5 / the A20 text.

## Exit test
Dated amendments (L01 spec; T08 release spec §5 if needed), register entries **R-566…R-569**, and a short work order
for the build lane (the test/envelope changes) appended to `docs/reviews/D1-rulings.md` as "WO-D1-C". No production or
test code changes by you. Commit (`S04 (ruling):` prefix, trailers). Report ≤ 100 words.
