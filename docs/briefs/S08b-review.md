# S08b brief: the package's single `reviewer` pass (design lane)

Branch `wp/S08b`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/s08b`, head `d34f8b57`. Merge base with main
`B = a13203b8`. Range `B..d34f8b57` (main merged in at `0387b2e7`; S08b's own commits follow). The design is
`docs/derivations/S08b-design.md` (architect, `971bc32f`; R-790…R-794 in `docs/decision-register.md`). The build log is
`docs/S08b_BUILD_DECISIONS.md`. The package touches phase logic, hence this review.

**Do not write or commit inside that worktree** — the full gate is running there and checks `git status`. Read only. Write
your review to `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/4eb41cce-83fd-4812-8ebc-a76f78cb2117/scratchpad/S08b-review.md`;
the orchestrator commits it as `docs/reviews/S08b-review.md`. If anything changes the design note or the register, give the
exact text in the review (errata as a dated note, register entries after R-794); the orchestrator applies it.

## What was built

- (a) `orchestrator/phase_contract.py`, `orchestrator/region.py`: a dormancy item is an entry whose key is a declared item;
  the "." heuristic (`_is_item`) is deleted; `adjacent`/`choose` take `items`; the 11 `active_set_cycling` messages of S08's 52
  configurations gain their change list. WO-2 `564bf772`.
- (b) `models/syn001/cascade_solve.py`, `column_solve.py`: S01 cascades get item 6 (the two-phase saturation consistency
  S08 gave columns), the moved code, S01's clause, `SATURATION_PREFIX`; S01 §18 Amendment 2. WO-3 `a6fa18a7`, B1 fix `6ea95a4a`.
- Gates: `scripts/s08b_identity.py` (+ recorder, `tests/test_s08b_identity.py`, 20 verdict tests) `8c455729`; manifest
  generator `scripts/s08b_evidence_manifest.py`; manifest `evidence/S08b/acbd1266…/manifest.json` tested 18/20 (gate, CI
  unsupported); T08 harvest `cb25186d`.

## What was run (local x86-64)

- WO-0: `column_records.py` at B: `S08B-RECORDS n=52 moved=[] stage_a_moved=[]` and exactly §6.1's eleven differences,
  byte-identical to `measured.txt`.
- G1 control `--no-change` on the unmodified branch: `S08B-IDENTITY PASS a=52 a_texts=0 b_keys=6075 b_moved=0 b_only=0/0`.
- G1 at `acbd1266`: `S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/20`. 64 base decisions had an empty
  change list; 61 moved (all `stall`); 3 (one tear-path test, `test_k03_attempts::test_the_attempt_budget_is_a_typed_outcome`)
  unchanged in both trees. The 20 branch-only keys are from the new `test_s08b_saturation.py`.
- `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL`; `S10C-IDENTITY PASS n=858 changed=[]`.
- B2 1.609e-06 K (C1), bound 1e-5 K. G3: branch 13280 passed, base 13249; S01 rows reproduce `measured.txt`, largest error
  2.43e-06 K; M1 `records 0`.
- Running now: the full gate and CI 40359016227.

## Look hardest at

1. **(a)**: does "declared item" literally replace the heuristic with no change of any decision's structural fields (G1
   family B says none moved — is the recorder a faithful witness: does it see every `decide` call, including those inside
   caches warmed by earlier tests)? Do `adjacent`/`choose` receive the right `items` at every call site?
2. **(b)**: item 6 in cascades — is it the same predicate S08 gave columns (`TWO_PHASE_SATURATION_TOLERANCE = 1e-4`), applied
   at the right point, with no new rule in `_admissible` or flash units (§5.3)?
3. **Build decisions needing a ruling** (in the build log):
   - **WO3-1:** a stub in `tests/test_s08_item6.py` retargeted from `column_solve` to `cascade_solve` (the moved code looks
     `band_temperature` up there); asserted values unchanged, but B3 says S08's item-6 tests "pass untouched".
   - **WO4-1:** manifest `requirements: [D09]`; the frozen schema rejects X31, so X31 is in a limitation.
   - **WO4-2:** G3 cannot hold as written: `measured.txt` predates S10-C, whose tests add 46 kernel-agreeing flash splits on
     the merge base too. Flash-type rows are judged against a scan of the merge base instead; near-trivial buckets still
     against `measured.txt`.
   - **WO4-3:** both trees' G3 shards dealt as G1 deals them (`run_suite.py`'s own dealing hid 3 cached solves on the branch).
   - G1 decisions 1–5 (shards must exit 0; record = SHA-256 of structural fields + message/cause; `b_moved` counts decisions;
     recorder copied to its own directory; `collections.abc.Set`).
4. **Fact:** a cascade root's last bits depend on which caches earlier tests warmed (C2 cached 2.0e-6 K vs fresh 7.4e-9 K;
   both accepted); B1 was changed to judge the raising solve's own values. Is that a sound assertion, or does it hide
   something?

## Not in scope

S08's and S10-C's own designs (reviewed); style; re-running the full suite (the gate does it). Scratch runs are fine
outside the worktree (e.g. a detached `git worktree add` under the scratchpad, removed afterwards).

## Deliverable

The review file above: findings by severity (must-fix / should-fix / note), each with exact text where anything changes, and
a ruling on each build decision in item 3. Report in at most 20 lines.
