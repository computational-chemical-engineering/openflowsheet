# M04 review brief (one `reviewer` pass, with the batched build-lane rulings)

**Subject.** `wp/M04` @ `3f99eee` (worktree `.claude/worktrees/m04`). Evidence manifest
`evidence/M04/a9566a6b3805938e8d4d386cc1820a551530f771/manifest.json`, status `tested` (57/58 pass, A33
`not_applicable`). Authority: `docs/derivations/M04-spec.md` (1390 lines; §3 surrogate, §6 split-conformal, §7
promotion, §8 flowsheet/rollback, §11 assertions, §15 W23 table, §18 Amendment 1, §19 Amendment 2),
ADR 0036 (Am. 1, Am. 2) and ADR 0037. Build log: `docs/design/M04-build-decisions.md` E1–E34. src diff vs the base:
`git diff 37ae0adc..3f99eee -- src` (26 files, +4202/−110); tests under `tests/test_m04_*`.

**What was run.** Full gate before every commit; last 8653 passed, 31 skipped. Real iteration 1 (WO-11, E30,
`benchmarks/m04/wo11-b2-it1-v3/`): b2-it1 on reactor v3, 632 cold runs, verdict NOT_PROMOTABLE (`band_not_finite`):
26/632 deterministic `reactor_not_accepted(certificate)` refusals (calibration 5/118 > n−k = 4 → q̂ = ∞; test 18/300,
training 3/144, gradient 0/70), spread over T 654.6–693.1 K. Finite: cal scores ≤ 0.316, test ≤ 0.292 (282/300 within
width), max |e_X| 7.3e-4, |e_ΔT| 0.32 K, gradient e 0.036 vs 0.25. A31/A32 (manifest `d65bb022…`, cold 0 / 632 hits)/A41
(8/8 bitwise) hold. E32 (relative path → fingerprint) fixed in `adapters/external/launcher.py` (`attempt_dir.resolve()`),
proved: absolute fingerprint unchanged `dfce4150…`, relative re-run reproduces `d65bb022…`. Frank's N6 default: M04 is
`tested` whatever the real verdict; M05 uses the parent model when the surrogate is not promotable.

**Review the implementation against the spec** — conformal arithmetic (§6, q̂ with failures counted against n−k),
promotion/rollback, record identity and replay, E32's launcher change (touches M02's external launcher: any other
caller affected?), and whether the tests verify anything.

**Rule on these (batched; each as a short ruling with the action it implies):**
1. **Unruled build choices** E10, E12, E14, E24–E34 (E15/E16/E22/E23 were ruled in Amendment 2): confirm or reverse.
2. **E33.** With default multi-threaded BLAS the re-submitted study's manifest is `908cbe2f…` instead of `d65bb022…`
   (reproducible; fit differs ≤ ~1e-12 relative; `promotion` block identical). WO-11 ran single-threaded. Options: pin
   BLAS threads inside the study, or record the thread setting in the manifest / A32's conditions. Which, and does A32's
   claim need restating?
3. **The 4.1 % certificate-refusal rate inside box v2.** Does it call for an amendment (box, plan, how refusals count
   against calibration), or is NOT_PROMOTABLE the honest end of iteration 1 with iterations 2–3 (`b2-it2/3`) unrun?
   Never move a band or tolerance on the measured outcome alone.
4. **E34:** the real verdict classified as harvest class P rather than an envelope row (E).
5. **Q-A2.1** stays open (no A33 record): say what would close it.

**Rules.** No production-code edits. Write `docs/reviews/M04-review.md` (must-fix / should-fix / note with file:line,
then the rulings). Rulings that change the spec go in a short §20 Amendment 3 of the spec plus register entries
**R-360…R-369**. Commit on `wp/M04`, named paths, push. Report ≤ 300 words: merge verdict (merge / fix first),
must-fix list, one line per ruling.
