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

## WO-3 — (b), S01 cascades get S02 §8 item 6 (2026-10-26, commits `a6fa18a7`, `6ea95a4a`)

- §5.2 as written: `TWO_PHASE_SATURATION_TOLERANCE` and the body of `column_solve._saturation_pairs` moved to
  `cascade_solve` (`saturation_pairs(unit, components, provider, state, regimes)`); `column_solve` imports both and keeps
  `_saturation_pairs(spec, …)` as a one-line delegation; `cascade_solve.acceptance_failures` gains the clause under
  `SATURATION_PREFIX = "§8 saturation: "` (both exported); `solve_cascade` unchanged. S01 spec §18 (Amendment 2, verbatim)
  and its header line. Tests: `tests/test_s08b_saturation.py` (B1, B2, B3, and the constants moved, not copied).
- DECISION WO3-1: `test_s08_item6.py::test_a_band_answer_other_than_inside_is_a_failure` stubbed
  `column_solve_module.band_temperature`; the moved body looks `band_temperature` up in `cascade_solve`, so the stub no
  longer reached it (3 parametrized failures: finite errors where `inf` was asserted) → the stub is retargeted to
  `cascade_solve_module` (two lines; every asserted value unchanged). Alternative: route the lookup through
  `column_solve` (a signature §5.2 does not give). Reversible by: reverting that hunk of `a6fa18a7`. §7 B3 says S08's
  item-6 tests "pass untouched"; this one-line touch is for the design lane to accept.
- B1, first form, failed in one shard (`test_s01_cascade_wo3` before it): the cached `solved("C2")` root and a fresh
  `solve_cascade(C2)` differ in their last bits (stage-1 bubble error 2.0096e-06 vs 7.3633e-09 K; both accepted). A
  solve depends on which caches earlier tests warmed (why G1 deals both trees alike). B1 now spies on
  `cascade_solve.saturation_pairs` and compares the six strings with the raising solve's own values (`6ea95a4a`).
- **B2 measured:** largest saturation error over C1–C5 = **1.6091221937131195e-06 K** (fresh process; ≤ 1e-5 K; per
  case in the manifest). Order-dependent at the 1e-6 K level: in the shard above, C2's cached root gives 2.0096e-06 K.
- Acceptance on `f6011de2` (WO-3 + the records commit; before the B1 fix): 25 S01/S02/S03/S06/S08/S08b modules, 950
  passed, 1 failed (B1's first form; after the fix its shard passes, 150, and the module, 5);

      S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/20     (10 min 47 s)
      S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL
      S10C-IDENTITY PASS n=858 changed=[]

  `b_only=0/20`: the decisions of the branch-only `test_s08b_saturation.py` (informational, §9). WO-2's line had 0/0.

## WO-4 — evidence and records, without the full gate and the review (2026-10-26)

- `scripts/s08b_evidence_manifest.py` after S08's generator. DECISION WO4-1 (§10 Q5): `requirements: [D09]`; X31 is a gate
  id the frozen schema's `^[DA][0-9]{2}$` does not admit (S08's precedent, W5-7), named in a limitation; `depends_on` is
  not a manifest field. Alternative: empty `requirements`. Reversible by: `REQUIREMENTS`.
- DECISION WO4-2 (G3's flash comparison): `measured.txt` was taken on main `53228775`, before S10-C. The scan on the merge
  base `a13203b8` (13249 passed, 0 failed) reproduces every S01 row of `measured.txt` but not its flash-type rows: S10-C's
  tests add 46 kernel-agreeing splits to the `[0.001, 2)` bucket (n 2386 → 2432, tests 483 → 489, LIQUID 147 → 191,
  TWO_PHASE 2233 → 2235); the near-trivial buckets are unchanged. So "identical to measured.txt" cannot hold on any tree
  after S10-C → the flash-type rows are judged against the same scan of the merge base, the near-trivial buckets also
  against `measured.txt`. Alternative: a design-lane re-registration of `measured.txt` on `a13203b8`. Reversible by:
  `scan_check` (`7d095488`).
- DECISION WO4-3 (G3's dealing): the run at `7d095488` failed G3 on that finding alone — 3 splits fewer on the branch,
  `test_t05b_openings.py::test_b31a_no_case_raises[CH-UP|CH-DZ12|CH-3]`, which record their splits when run alone on the
  branch: `run_suite.py` deals each tree's own file list, the three new `test_s08b_*` files shift later files to other
  shards, and the probe sees only uncached solves. → the generator runs the probe over `s08b_identity.shards` (G1's
  dealing; for the base tree exactly `run_suite.py`'s). Alternative: `--files-from` in the design's `run_suite.py`.
  Reversible by: `g3_scans` (`6207d4c2`).
- Records: R-731's "Watch for" answered; the design note's header erratum (R-782…R-786 were S10-C's); `docs/progress.md`,
  `docs/CLOUD_WORK.md`, `docs/FRANK_QUESTIONS.md`.
- **Manifest** `evidence/S08b/acbd12664b80d06fc51cf0b68640d25d6962b4a2/manifest.json` (30 min 35 s): `status: tested`,
  18 of 20 checks pass; `S08b.gate` and `S08b.ci` `unsupported` (they run before merge). A1–A7, B1–B3 by citation (1200
  nodes passed: S08b 31, S01 138, S02 187, S03 310, S06 179, S08 106, and WO-2's contract tests); B2 per case C1
  1.609e-06, C2 1.001e-08, C3 8.43e-11, C4 2.56e-09, C5 5.75e-11 K. Gate lines at `acbd1266`:

      S08B-IDENTITY PASS a=52 a_texts=11 b_keys=6075 b_moved=61 b_only=0/20
      S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL
      S10C-IDENTITY PASS n=858 changed=[]

- **G3 at `acbd1266`** (the final code commit), against `measured.txt`: branch `passed=13280 failed=0 skipped=3137` (the
  base's 13249 + S08b's 31), base `a13203b8` `passed=13249 failed=0 skipped=3137`; M1 `records 0; tests 0` (`_is_item`
  is gone); every S01 row of `measured.txt` reproduced byte for byte, one new row
  (`S01 tests/test_s08b_saturation.py: n=31 max_sat_error=1.61e-06 K min_LV=0.0135`), largest S01 error 2.43e-06 K
  (≤ 2.5e-6); flash-type rows equal the merge base's (n=2432, tests=489, `[0.001, 2)` n=2422) and the three near-trivial
  buckets equal `measured.txt`'s (4, 2, 4 splits; max 0.0666, 0.000949, 30.70 K). The suite counts' equality with G2's
  is G2's (not run here).
- The first `tested` run at `6207d4c2` (same numbers) was not committed: its G1 check's `expected` carried an
  angle-bracket placeholder, which `test_evidence_manifests.py` refuses; fixed in `acbd1266` and re-run.
- Not done here: the full gate (G2), CI on both architectures, the `reviewer` pass; the T08 harvest follows in its own
  commit.
- T08 harvest (`cb25186d`): 8 limitations and 2 checks appended (E → L19, L19, U04+L20; the rest P); `HARVEST_SIZE`
  (58, 824, 99) → (59, 832, 101); `t08_support_matrix.py --check` 0 problems; harvest, envelope and manifest tests 412
  passed. Next (orchestrator): `scripts/gate.sh`, CI on both architectures, the `reviewer` pass, merge.

## T07 pin on ci-x86-64 (orchestrator, 2026-10-26)

- MEASURED: CI 40359016227 at `d34f8b57`: `check (ubuntu-latest)` failed one test, `test_t07_interrupt.py::
  test_interrupt_at_record_k[THM-09-4]`: `assert 136 == 94` on ci-x86-64 (aarch64 and default-install passed; local gate PASS
  13286/3137). S10-C's CI 40315691647 had 94 on ci-x86-64. S08b changes no numerics (S08/S10C identity PASS). ci-x86-64
  runners' CPU varies (EPYC 7763 / 9V74, R-782 note §8 Q-C); the length follows the CPU, not the class.
- DECISION T07-1: THM-09 start 4's length pin on ci-x86-64 → removed (treated as an unregistered class: the > 89 check and
  every record-k interrupt still run); ref-x86-64 94 and ci-aarch64 136 stay; the failure message now names the CPU model.
  Alternative: pin per (class, CPU model) — needs a measured length per runner CPU, which no run has recorded. Reversible by:
  reverting this commit. For the design-lane ruling round (with S10-C's G2 and unregistered-class decisions).

## Correction (2026-10-26, from the S08b review F1)

The WO-3 entry's fact "a cascade root's last bits depend on which caches earlier tests warmed" is wrong. The cascade solve is
deterministic (repeats bit-identical in one process, at base and head). The cause is a pre-existing test-isolation bug: the
session memo `solved("C2")` (`tests/test_s01_cascade_wo2.py:62-71`) is first filled by
`test_s01_cascade_wo3.py::test_a17_forced_edge_3_from_the_presolve_root` while `_forced_edge_3` patches `eo_recovery_due` to
`True`, so in a process where wo3 runs without wo2 first, the memo holds C2's forced edge-3 root (2.0096e-06 K) instead of A06's
root (7.36e-09 K). B1's spy form stays (a sound wiring test). Follow-up on main: B1's docstring text (review F1), the memo
filled before the patches in `_forced_edge_3`, and the `_proposal`-level `items` test (review F2).
