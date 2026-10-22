# C4 — build decisions (post-0.2.0 harvest)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

## Harvest of M07a's three manifests and M07's (R-485's next harvest)

Measured: the four manifests hold 46 items (M07a 24 limitations + 18 non-pass checks; M07 `ce99365` 4 + 0;
`evidence/M07/c899c85…` holds no manifest). Classified 38 S, 8 P, 0 E, 0 B. `HARVEST_SIZE` (36, 440, 44) →
(40, 468, 62); 530 harvest rows. Negative control: with the old exclusion, `check_a21` reports the 46 rows dangling.

- DECISION: envelope id for the new rows → keep `v0.2-envelope-1` / `release: 0.2.0`. The rows add no axis,
  `unsupported` or `limitations` row (no E item needs a new one), as S01's and S02's harvest rows did; the return to
  the working form is paired with main's version by R-460 / AM-41 (`tests/test_v02_main_version.py`) and the gate
  pins the id, so changing the id alone would break that pairing. Alternative: `v0.2-envelope-dev` / `0.2.0.dev0`
  here. Reversible by: the commit that moves main's version off 0.2.0 (see QUESTION C4-Q2).
- DECISION: "Evidence class" lines (M07 `limitations[0]`, each M07a `limitations[0]`) and "step 13 / step 18 not run
  by the generator" lines → P, as T08's `limitations[0]`, M06's `limitations[6]` and S01/S02's gate notes are.
  Alternative: E → L18. Reversible by: editing the rows' class and pointer.
- DECISION: M07a.A60–A63 pending (checks and their limitation lines) → S to `doc:docs/reviews/V02-alpha-verdicts.md`
  (`C_α²`); `6fec822`'s also to `V02-alpha-verdicts-6fec822.md` (superseded with its candidate, R-370); `e0e198e`'s
  note R-346/R-349 (no verdict there). No manifest records them `pass`, so no `check:` pointer exists. Alternative:
  P (the verdict lane's). Reversible by: editing the rows.
- DECISION: M07a.A39, A43 (fail at `e0e198e`; R-345/R-346, R-347), A52 (unsupported before step 5) and A64 (pending)
  → S to `check:M07a.<id>`, which passes at `cc73219` (and A39/A43 at `6fec822`). Reversible by: editing the rows.
- DECISION: M07 `limitations[1]` (verdicts not judged here) → S to `check:M07.A40`–`A42` (pass in the same manifest)
  and `doc:docs/reviews/V02-verdicts.md`; `limitations[3]` (R-485's deferral) → S to the A21 test and the new
  `test_c4_the_post_0_2_0_harvest_reads_m07a_and_m07`. The statement stays true of the 0.2.0 envelope as released,
  which is not changed. Alternative: P. Reversible by: editing the rows.
- DECISION: history kept in `test_m07a_a50_nothing_is_excluded_from_the_harvest_at_c_alpha` → the live-constant
  assertion becomes two historical ones read with `git show`: `("evidence/M07a/",)` at C′ (M07 spec §25.1) and
  `("evidence/M07a/", "evidence/M07/")` at the v0.2.0 tag `5c82b4c`; the `C_α` and C′ `ls-tree` checks are unchanged.
  The post-0.2.0 state is a new test. Alternative: keep the constant tuple. Reversible by: reverting the test edit.
- QUESTION C4-Q1: M07a.A61 (V11–V20) pending → S to the alpha verdicts, whose V14 is FAIL on (b). Default: S, because
  the FAIL is already user-facing as L01 (and T08-verdict-V14b.md) and the item itself is a pending state.
  Alternative: E → L01.
- QUESTION C4-Q2 (found, outside C4): main carries version `0.2.0` and `v0.2-envelope-1` after D2.4 changes since the
  tag (S01's `src` at `7dcdf2a`; S02's and C4's `benchmarks/` rows). R-460 / AM-40–42 say the first D2.4 change after
  a tag moves the version to a `.dev0` and the envelope to `v0.2-envelope-dev`; `RELEASED` in
  `tests/test_v02_main_version.py` lists only `0.2.0a1`, so nothing catches it. Default: the package that next moves
  main's version (with `RELEASED` gaining `0.2.0`) does both; C4 does not.
- NOTE: `docs/support-matrix.md`'s harvest sentence says "of the 29 manifests" but counts packages (40 manifests are
  harvested); pre-existing `_render_harvest` wording, not changed here.
