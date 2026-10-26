# S08b build decisions and gate log (build lane)

Design: `docs/derivations/S08b-design.md` (R-790 to R-794). Branch `wp/S08b`. Append-only.

## WO-0 — merge and baseline (2026-10-26)

- `git merge --no-ff origin/main` (main `a13203b8`, S10-C merged at `8654aabc`) → merge commit `0387b2e7`.
  One conflict, `docs/decision-register.md` (both sides appended): main's R-760…R-786 kept as merged, S08b's R-790…R-794
  appended after them; the unused-range comment corrected to R-787…R-789 (S10-C used R-782…R-786, which the design note's
  header still calls unused — no id collides; the note is not edited).
- **Merge base `B = a13203b8`** (`git merge-base HEAD origin/main` after the merge; the merge commit's `src/`, `tests/` and
  `scripts/` equal `a13203b8`'s, S08b having added only docs and the design probes). G1's `MERGE_BASE`.
- `python docs/derivations/scripts/s08b_design/column_records.py OUT` at `0387b2e7` (12.6 s):

      S08B-RECORDS n=52 moved=[] stage_a_moved=[]

  and exactly §6.1's eleven differences, byte-identical to `measured.txt`'s section (diffed): `S02.M1`, `S02.V-M2.distillate_rate+boilup_ratio`
  (`S02.stage.7:VAPOR->TWO_PHASE`), `S02.P1` `/reentry/stage_a/recovered_from/message` (`S02.stage.2:LIQUID->TWO_PHASE`),
  `S03.PC-L`, `S03.PC-LI`, `S03.PC-P`, `S03.RC1`, `S03.RC1-BR`, `S03.RC1-RR`, `S03.RC1-z`, `S03.RC7`
  (`S03.stage.7:VAPOR->TWO_PHASE`), each at `/recovered_from/message`. Q3 (§10): S10-C added no twelfth difference. Premise holds.
