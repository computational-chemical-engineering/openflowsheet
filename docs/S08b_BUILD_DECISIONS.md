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

## WO-1 — the identity gate (2026-10-26)

- `scripts/s08b_identity.py` (G1, `MERGE_BASE = "a13203b8"`, `--no-change`), its recorder plugin
  `scripts/s08b_identity_recorder.py` (copied by the gate into a directory of its own so the base tree, which lacks it,
  imports nothing else from the branch), `tests/test_s08b_identity.py` (20 verdict tests: the registered outcome passes;
  `--no-change` passes on equal trees and fails on the registered move; FAIL on a twelfth moved text, a wrong list, an
  unmoved registered text, a moved reason, digest, `stage_a` digest, a lost `stage_a`, 51 configurations, a moved
  candidate α (structural hash), a non-`.stage.` list, an item entry in the list, another text move, a failed shard,
  nothing shared).
- Control on the unmodified branch (`0387b2e7` code + WO-1 files), 9 min 44 s, 16 shards per tree:

      S08B-IDENTITY PASS a=52 a_texts=0 b_keys=6075 b_moved=0 b_only=0/0

  Base shards 13249 passed / 3137 skipped / 192 deselected (= S10-C's gate count), branch 13269 (+20, this file's tests,
  in the extra shard). 64 of the 6075 base decisions carry an empty `phase_wall(stall|patience, )` list (37 tests).
- DECISION: what does family B require of the shards? → every shard of both trees must exit 0 (a failed or crashed
  shard is `FAIL`), as `s10c_identity.py` requires of its pytest run. Alternative: compare whatever was recorded.
  Reversible by: dropping the exit check in `_verdict_b`.
- DECISION: family B's record layout → a SHA-256 over the structural fields (kind, outcome, signature, source,
  fallbacks, trial with `alpha.hex()`, opening SHA-256) plus `message` and `cause` verbatim; a structural difference is
  reported by key only. Alternative: every field verbatim (larger files, same verdict). Reversible by: the recorder.
- DECISION: `b_moved` counts decisions (keys) whose message or cause moved, not fields. Alternative: count fields.
  Reversible by: `_verdict_b`. The PASS line also carries `b_only=<base>/<branch>` (§9: keys in one tree, informational).
- First control attempt FAILed on the gate's own bug (the branch-only extra shard was also launched in the base tree,
  where its file does not exist: pytest exit 4); fixed before the PASS above.

## WO-2 — (a), signature items by declaration (2026-10-26, commit `564bf772`)

- §5.1 as written: `_is_item` deleted; `_split(signature, items)`; `adjacent(…, *, items)` and
  `WallObserver.choose(…, *, items)` keyword-only and required; `_proposal` passes `frozenset(declared)` to both
  `choose` calls; `_changes` takes its items from `declared` (the no-declared-phase raise deleted, unreachable);
  `region._units_and_items_disjoint`, called from `_LiftedOps.__init__`. Tests: `tests/test_s08b_contract.py` (A1–A4,
  A7, and `items` keyword-only/required), A5 guard edits (`items=` added, every asserted value unchanged), A6 pins in
  `test_s02_column_wo3.py::test_a12_p1_measured_branch_is_held` and `test_s08_reentry.py::test_a06_…`.
- DECISION: `AbstractSet` spelled `from collections.abc import Set as AbstractSet` (no prior use in the repo).
  Alternative: `typing.AbstractSet` (deprecated alias). Reversible by: the import line.
- Acceptance: `ruff check .` and `ruff format --check .` clean; `mypy` (250 files) clean; touched tests
  (`test_s08b_contract`, `test_s08b_identity`, `test_t05b_dormancy`, `test_t05b_zero_flow`, `test_s02_column_wo3`,
  `test_s08_reentry`, plus `test_t03_contract`, `test_t04_ptc_region`, `test_k03_attempts`) 322 passed.
- G1 on `564bf772` (10 min 9 s):

      S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/0

  61 of the 64 base decisions with an empty list moved (all `stall`); the other 3 are
  `test_k03_attempts.py::test_the_attempt_budget_is_a_typed_outcome` on the tear path, unchanged in both trees (as §5.1
  says of the tear path). A first run on the uncommitted tree FAILed one branch shard on
  `test_m07_journey.py::test_a21_…` (its carry-identity check reads `git status`: a dirty working tree, not S08b);
  re-run after the commit, PASS above.
- Older gates on the same content, at their own registered merge bases (no `MERGE_BASE` change needed: each compares
  against a fixed pre-package base and pins fields S08b does not move; neither digest includes a region message):

      S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL
      S10C-IDENTITY PASS n=858 changed=[]

- Not done here: WO-3 (§5.2), WO-4 (full gate, manifest, records, review).
