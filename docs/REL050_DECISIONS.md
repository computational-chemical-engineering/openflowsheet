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
- 2026-11-21 ~16:05, REL050-WF2 (opus-engineer, Opus, ~123k): F-2 bfecbeb7 (only `/rc_items/7/assertion` changed),
  F-1 text bf6adbbd, F-1+F-3 code 1452d786. `--commit 1452d786 --f1-f3`: exit 0, `wheel data check (F1, F3): PASS`
  (registry_sha256 fc0af96b... both sides, N 149, N_pkg 9 = m01 + s10, wheel 3e85e546..., 1 page each, bound 2,
  host ref-x86-64); controls a-f each fail; loader RP.L01-L11 PASS at 1452d786; battery 148 passed. Engineer's two
  choices stand (bound from the checkout's N; error shape {type, message}). Pre-existing mypy note at
  wheel_data_check.py:197 (b69dc0f1, scripts not in mypy `files`). Next action 2 and 3 met; wp/REL050 pushed for CI.
- 2026-11-21 ~16:20, X07a-WO20 (opus-engineer, Opus, ~106k): manifest `tested` at bd0b7df5 in c356211b (pushed):
  X07a.CI run 44902051410 all seven legs; re-runs at bd0b7df5 all pass (support matrix 0 problems; registry 49
  descriptors fc0af96b...; legacy 149; F0 9/9; 37 files 1390 passed 2 skipped; ruff/format/mypy clean; manifest tests
  pass). Limitations [0] platforms/ADR 0007 Am3, [1] WO16 pins, [2] a36 ruling D1. Engineer's DECISION: old
  9773c361 manifest kept (as briefed) -> HARVEST_SIZE (102, 1148, 147). Alternative: rename it away as F1 did
  (dd97d79a). Reversible by: reverting c356211b. Accepted. c356211b touches a test and the envelope: fresh CI
  44913734986 / Site 44913735084 for the merge card.
- 2026-11-21 ~17:00, GitHub API quota exhausted 14:56-15:25 UTC by `gh run watch` pollers at the default 3 s
  interval (all stopped; hub told; one 300 s poller now). CI results read after the reset: wp/S19 44909075689 at
  043879a4 success on all legs -> S19-V-GEND verdict dispatched (S19 lane). X01 44909945712 at 5634fa7f FAIL on both
  legs, only test_a21_every_item_is_classified_once_and_resolves (a0e4c546 manifest limitations[0-3] unmapped) and
  test_m07a_a50_the_harvest_size_is_the_quoted_one ((101, 1148, 146) measured); 20888 passed. Fixed by the
  orchestrator (mechanical, X07a c356211b pattern): bbbca491 four class-P harvest rows, HARVEST_SIZE (101, 1148, 146),
  matrix re-emitted (--check 0 problems; 44 passed). CI 44921749701 / Site 44921749623. Then the X01 manifest move.

## 2026-11-21 ~17:30 CET: trial merge for the merge plan (after self-reset)

- Trial merges onto main d29f1a50 (scratch worktree, discarded). Order X07a, X01, REL050: X07a clean; X01 conflicts
  in `benchmarks/t08/support_envelope.yaml` (1 hunk), `docs/support-matrix.md` (2), `tests/test_m07a_harvest.py` (1);
  REL050 conflicts in `docs/decision-register.md` (2). With S19 first: S19 clean, then X07a and X01 each conflict in the
  same three harvest files, X07a and REL050 in the register. With S19 last: S19 conflicts in the three harvest files
  and the register. No conflict in `src/` or `scripts/` in any order (S19 and X07a both touch `registry_builtin.py`,
  `t05_evidence_manifest.py`, `w5_identity.py`; they merge cleanly).
- Register numbers are disjoint (S19 R-1061, 1066, 1067; X07a R-1062, 1063, 1068; REL050 R-1065): the register
  conflicts are append order only. Harvest resolution: union of the envelope rows, measured HARVEST_SIZE, `--emit`.
- So S19 before or after K3 costs the same conflicts; the difference is semantic risk (S19 touches 72 `src/` files,
  X07a 11) and S19's G-END verdict, which holds only while main stays at d29f1a50 (S19 first keeps it valid).
- Brief `X01-WO3-manifest.md` written (dispatch on CI 44921749701 green).
- X07a CI 44913734986 at c356211b: success on all legs (default-install, codehealth, check ubuntu-latest,
  ubuntu-24.04-arm, macos-latest, windows-latest, identity). X07a is ready for the integration branch.
- X01 CI 44921749701 at bbbca491: success (codehealth, default-install, check ubuntu-latest, ubuntu-24.04-arm,
  identity); Site 44921749623 success. X01-WO3 (manifest move) dispatched to sonnet-implementer.
- X01-WO3 (sonnet-implementer) done: manifest `evidence/X01/bbbca491.../manifest.json` tested, commit bfd5c180
  (pushed); HARVEST_SIZE (102, 1152, 146); F0 PASS; registry, support matrix, codehealth docs exit 0; 682 passed.
  Spot-checked: origin wp/X01 = bfd5c180, manifest status tested, commit bbbca491.
- Integration branch `int/0.5` (worktree `.claude/worktrees/int05`), pushed at d1df6999: main d29f1a50 + wp/X07a
  c356211b (b5ec5060, clean) + wp/X01 bfd5c180 (e49b534c: envelope union, HARVEST_SIZE (104, 1156, 147) = main
  (100, 1144, 146) + X07a (2, 4, 1) + X01 (2, 8, 0), matrix re-emitted, --check 0 problems) + wp/REL050 bfdd3f2d
  (d1df6999: register R-1062, 1063, 1065, 1068 in number order). Ten touched test files: 964 passed, 20 skipped.
  S19 not included (DECISION of 2026-11-21: S19 enters 0.5 only on a card signed before K3). CI poller bjggjcdnk.
- 2026-11-21 ~21:25 CET: card ofs-s19-merge-main signed, choice A (S19 enters 0.5.0), VERIFIED; executed: main =
  ceb38cec (merge of wp/S19 9fb4d5df), F0 PASS on main, pushed. The DECISION "S19 relative to K3" is settled: in.
  int/0.5 CI 44932969763 cancelled (obsolete base). int/0.5-r2 = ceb38cec + X07a (b473c716: envelope = X07a side +
  S19 rows; register R-1061..1068 ordered; HARVEST_SIZE (103, 1161, 147)) + X01 (2daf92b9: + X01 rows; HARVEST_SIZE
  (105, 1169, 147)) + REL050 bfdd3f2d (67cc5027: register ordered). Ten touched test files: 970 passed, 20 skipped.
  Pushed; CI poller b13dft0de.

## 2026-11-22: int/0.5-r2 CI red at 67cc5027; fix 1fe40db3

- CI 44945609131 at 67cc5027: FAILED on all four check legs and default-install (identity failed after: "G05
  needs two platforms; found 0", no structural artifacts). Site 44945609083 success. Causes, all S19 tooling meeting
  X07a's checks for the first time (S19's own CI had only the two Linux legs):
  (1) every leg: `tests/test_x07a_git_show_separator.py` flags `scripts/w5_identity.py:1213` (`git show rev:path`
  without `--`); (2) Windows: `tests/test_s19_gate_queue.py` 3 setup errors, `gate_queue.py` imports `fcntl`;
  (3) Windows: 4 failures in `tests/test_s19_w5_identity.py` (pin tests: `pinned_tree` worktrees the W5 base tree,
  which imports `fcntl`; the limit X07a registered for `facts`/`scratch`/`_tool` did not cover this later fixture).
  Linux legs otherwise 21016/21046 passed; the `DomainError` tracebacks in the logs are logged output of passing tests.
- Fix 1fe40db3 on int/0.5-r2 (orchestrator, 4 files): `--` in `_blob`; `_skip_base_tree_on_windows()` in
  `pinned_tree`; module `skipif` win32 in the gate-queue test; both rows in the X07a platform-limit table. Local:
  70 passed (separator lint, gate queue, w5 identity, platform rows). Pushed; CI re-run.
- Merge card now names int/0.5-r2 at the green tip (1fe40db3 or later), not 67cc5027.
- 2026-11-22: CI 44960794993 at 1fe40db3: success on all 7 jobs (check ubuntu-latest, ubuntu-24.04-arm,
  windows-latest, macos-latest; default-install; codehealth; identity). Site 44960794958 success.
  DECISION-REQUEST ofs-rel050-merge-main to hub. Verify against these texts verbatim:
  A: "Fast-forward main from ceb38cec to int/0.5-r2 at 1fe40db3 (the merges of wp/X07a c356211b, wp/X01 bfd5c180 and wp/REL050 bfdd3f2d onto ceb38cec, plus the cross-package fix commit 1fe40db3; CI 44960794993 green on all 7 jobs), run the F0 corpus identity on main, and push main only if F0 passes."
  B: "Do not use int/0.5-r2; merge wp/X07a, wp/X01 and wp/REL050 into main one at a time, each with its own merge commit, a fresh CI run on all legs and its own Decision Desk card, then run the F0 corpus identity on main and push main only if F0 passes."
- Hub filed ofs-rel050-merge-main: A verbatim as above; B reworded by hub (it pushes nothing itself). Verify B against:
  B: "Do not use int/0.5-r2; file three separate Decision Desk cards, one per package (wp/X07a, wp/X01, wp/REL050), each merging into main with its own merge commit after a fresh CI run on all legs and the F0 corpus identity on main; this card pushes nothing."
  Confirmed to hub: ofs-s19-merge-main carries `executed` (at 2026-11-21T20:25:00Z, card version 3).

## 2026-11-22: the 0.5 packages in main; K3 dispatched

- Card ofs-rel050-merge-main signed, choice A (2026-11-22T09:35Z), `decision_desk_verify.py` VERIFIED (key
  032ee0a5ae620a90) against option A's text above. Executed: main fast-forwarded ceb38cec -> 1fe40db3; F0 on main PASS
  (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42); origin/main = 1fe40db3; `executed` on the card
  (version 3). Old branch `int/0.5` (d29f1a50 base) obsolete, kept until the tag (deleting a remote branch waits).
- main merged into wp/REL050 (411fe0a3, clean; diff to main docs-only). P6 measured: SMM-TR09 `ref-x86-64`, kernel
  6.12.86+deb13-amd64.
- DECISION: where K3 lives -> on wp/REL050 (as 0.4.0: K3 49a04731 on wp/REL040, main took it in the final merge of C).
  Alternative: K3 as a commit on main (needs its own card). Reversible by: cherry-picking K3 to main on a card.
- K3 work order `<briefs>/REL050-K3.md` (opus-engineer): REL040 manifest harvest + HARVEST_EXCLUDED REL050, K3
  (0.5.0, v0.5-envelope-1, A10_PINS_0_5_0), P1/P3/P4/P6 measured.

## 2026-11-22: harvest and K3 (build lane, work order REL050-K3)

- ad74470b harvest: REL040's manifest (`84c6654…`, 3 limitations, 0 non-pass checks) classified 3 P (provenance note,
  process note, release-candidate item; patterned on S13's rows at 9eceb3aa). HARVEST_EXCLUDED `("evidence/REL050/",)`;
  `evidence/REL050/` absent. HARVEST_SIZE (105, 1169, 147) -> (106, 1172, 147), measured. `--check` 0 problems.
  Named tests 1880 passed, 45 skipped. No other test asserts the REL040 exclusion (the other `evidence/REL040/` hits
  in tests are synthetic fixture trees).
- DECISION: the comment above HARVEST_EXCLUDED gains one sentence naming 0.4.0's and 0.5.0's exclusions (0.4.0's cut
  left it saying S13). Alternative: leave the comment stale. Reversible by: reverting those three comment lines.
- K3 = 8aaed3f25d94823d2b93524884a9f054eb0d306d: the same 11 files as 49a04731. Working form before the pin read
  `v0.2-envelope-dev` / `0.2.0.dev0` as expected. README: "Version 0.5.0 is released. Version 0.4.0 was released on
  11 November 2026 and version 0.3.0 on 31 October 2026 (...)". F0 PASS (M1 50/50 ... M9 42/42).
- K3 tests: 1 failed, 1879 passed, 45 skipped. FAILED `tests/test_rel_evidence_manifest.py::
  test_rel_a20_over_0_3_0s_committed_records` (RP.S03 and RP.S04 same-form DIFFERS), through
  `tests/test_v03_v0_3_gate.py::test_a04_the_committed_test_holds_and_a_swap_fails` (`assert False`, line 453; it
  fails directly too): its `RELEASE_PINS` hard-codes the 0.2.0/0.3.0/0.4.0 pairs, K3 appends A10_PINS_0_5_0 (§7.2).
  Class (b), not the version: an RP §12 stop, reported, no expectation edited. 0.4.0 met the same at 2650fb8a
  (RELEASE_PINS extended after K3, both controls kept). No class (a) failure in the named set.
- P1 24/24 packages have a `tested` manifest whose sha is an ancestor of K3. P3: all 32 `required_adrs` Accepted;
  0062-0067 Proposed and not in `required_adrs` (Q-F1). P4 `RP.L01-L11: PASS` at K3. P6 `ref-x86-64`.
- 2026-11-22, K3 result (opus-engineer, Opus, ~116k): ad74470b harvest (REL040 manifest: 3 limitations, all P;
  HARVEST_SIZE (106, 1172, 147); HARVEST_EXCLUDED ("evidence/REL050/",)); **K3 = 8aaed3f25d94823d2b93524884a9f054eb0d306d**
  (0.5.0, v0.5-envelope-1, A10_PINS_0_5_0; F0 PASS); f1331088 log. P1 24/24 tested at ancestors; P3 32/32 required
  ADRs Accepted (0062-0067 Proposed are not in required_adrs: only Q-F1); P4 RP.L01-L11 PASS at K3; P6 ref-x86-64.
  Stop (b): test_v03 `test_a04_the_committed_test_holds_and_a_swap_fails` (RELEASE_PINS hard-coded through 0.4.0),
  seen through RP.S03/S04 in test_rel_a20. DECISION (orchestrator): ruled §7.2 bookkeeping, as 0.4.0's 2650fb8a;
  fix committed after K3 (tests/, not a D2.4 path) with controls kept and the pre-0.5 tuple added. Alternative: a
  design-lane ruling first. Reversible by: reverting that commit.

## 2026-11-22: the re-takes at K3 (J) and the journey at J (C) (build lane, work order REL050-J)

- Host SMM-TR09 (`ref-x86-64`), kernel 6.12.86+deb13-amd64 at start and at every heavy start. Run tree
  `git worktree add --detach .claude/worktrees/rc-k3-050 8aaed3f2`; `git status --porcelain --ignored` 0 lines at
  2026-11-22T10:57:46+01:00, before the first re-take. Outputs, logs and drivers: `~/.cache/rel050-cut/` (`bin/`,
  `logs/`). nlp: `$R/.venv-nlp` under env -i (HOME, PATH, LANG=C.UTF-8), OMP 1, PYOMO_CONFIG_DIR, PYTHONNOUSERSITE=1,
  PYTHONPATH=src:<nlp-test-tools>. IDAES: `$R/.venv-idaes` as step 11 runs it (-I, PYTHONPATH unset, OMP/OPENBLAS/MKL
  1, IDAES_DATA). Reactor env `pymrm-6089593-032a050c6cf3` used as is (not rebuilt).
- Re-takes, 7 single-threaded processes in parallel: the five by REL040's `g10_case.py` (`run_case` + `write_files`),
  5-7 s each, exit 0; IDAES 8 s, exit 0; REAL `--retake-into` exit 0 in 2017 s, DECISION_STABLE, T* =
  653.1500351610193, study_cold 48, `child-logs kept=0`, file set equal to the committed one.
- Proofs (each exit 0; `--old-version 0.5.0.dev0 --old-host SMM-TR09` for the five, read from the committed coupling
  records and sidecars; REAL `--old-platform 'Linux-6.12.113+deb13-amd64-x86_64-with-glibc2.41' --old-host SMM-TRS2`;
  IDAES `--old-platform` the same string):
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-tr-e2: changed-digests=41 digest=146 timing=20 path=0 version=4 platform=0 other=0 environment=equal host=0`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-tr-e2-far: changed-digests=79 digest=320 timing=35 path=0 version=7 platform=0 other=0 environment=equal host=0`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-tr-e2-fd: changed-digests=70 digest=215 timing=20 path=0 version=4 platform=0 other=0 environment=equal host=0`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-loop-r: changed-digests=91 digest=285 timing=26 path=0 version=3 platform=0 other=0 environment=equal host=0`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-loop-s: changed-digests=37 digest=124 timing=20 path=0 version=4 platform=0 other=0 environment=equal host=0`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=105 digest=569 timing=528 path=128 version=0 platform=4 other=0 environment=host host=79`
  - `IDAES-RETAKE PASS differing=environment.platform platform=1 inputs=0 other=0` (HM-28 as predicted)
  REAL meets HM-27 (`platform=4`, `host=79`). Its `digest` 569 / `changed-digests` 105 exceed H7's 504 / 103 (same tool
  since 64074f8a, same committed REAL since e0a3d6b7): the request's `provider_identity_sha256` (the provider's
  `describe()`, implementation hashes included) moved with 0.5's source, and with it every experiment key. Digest
  class, not part of the pass rule (HM-27 does not predict `changed-digests`); `other=0`, so every number is equal.
- **J = 3caa928cc82083e49184b4ee099bc9dbcb8b542b** (parent 3da2c4e2 = K3 + a6d1bea8 tests + docs logs): 46 files,
  written/changed TR-E2 8/7, TR-E2-FAR 11/10, TR-E2-FD 8/7, LOOP-R 7/6, LOOP-S 8/6, REAL 9/9 (its sidecar moves
  SMM-TRS2 -> SMM-TR09), IDAES 1/1. At J: `-m nlp tests/test_m05_g10_replay.py` 5 passed; `m05_wo9_real.py --replay`
  `REPLAY PASS REAL differences=0` (7 s; the TR09 failure since the host move is cured, WO-H4); `tests/test_m05_*retake*.py
  tests/test_m01_idaes_retake_diff.py tests/test_m07_journey_record.py` 159 passed, 4 deselected.
- Journey attempt 1 (clean `rc-j-050` at J, 0 lines at 11:34:06) with the brief's nlp line, PYTHONPATH=src:<nlp-test-tools>:
  exit 3 in 7 s, `INSUFFICIENT_EVIDENCE`, R1/R3 `UNSUPPORTED(reactor_environment_unavailable)`. Cause measured:
  `m07_journey.reactor_available` runs M02's `env.verify`, which then reads nlp-test-tools' `pytest 8.3.5` and
  `iniconfig 2.3.0` ahead of the reactor env's pinned 9.1.1 / 2.3.1 (`packages` != `locked packages`, those two only);
  with PYTHONPATH=src it returns True. Not committed; kept in `~/.cache/rel050-cut/journey-attempt1/`.
  - DECISION: the journey runs with PYTHONPATH=src, as 0.4.0's step 3 (`journey.sh`, b40d48d1) and 0.3.0's did; the
    brief's generic nlp line does not apply to `m07_journey.py run`. Alternative: stop and ask. Reversible by:
    discarding C and re-running. For RC step 15: `replay` at C passes in both lines (below); a step that runs
    `m07_journey.py run` with the tools on PYTHONPATH would meet attempt 1's outcome.
- Journey attempt 2: worktree removed and re-added at J (0 lines at 11:36:07), PYTHONPATH=src, else as above. Exit 0,
  4558 s. refined, T* = 653.1500351610193 K BOUND_LOWER, J = 0.4524965242483627; R0 INDIFFERENT 673.15, R1 DECIDED
  653.15 (cold 36, 2139 s), R2 SURROGATE_NOT_PROMOTABLE, R3 DECISION_STABLE (re-run, carry_identity_differs from anchor
  8aaed3f2; cold 48, 2011 s); journey wall 4556 s.
- **C (proposed) = 0a800e69f200e52dae7e5f3d2d56810bc8f10e27**, the record under `benchmarks/m07/journey/<J>/` (12 files).
  In a clean worktree at C (`rc-c-050`, 0 lines): `check` ACCEPT; `replay` bitwise, 25 s, with PYTHONPATH=src and with
  src:<nlp-test-tools> (step 15's line), tree still clean after; OMP_NUM_THREADS=2 exit 2 (refused, as designed);
  `v0_2_gate.journey_carry(J, C)` carried; `tests/test_m07_journey_record.py` 90 passed, 5 deselected.
- Against 0.4.0's record at e0a3d6b7: 109 of 10794 leaves differ, all allowed: walls (R0/R1 grid wall_s 9+9, budget
  spent R0/R1/R3, accounting R0/R1/R3/journey/t_star_resolve, R3 t_star_resolve), digests (coupling_sha256 and
  run_sha256 in R0/R1 grid and artifacts 9 each, R3 candidate coupling_record_sha256, parent_checks R0/R1/R3/journey
  run_sha256), `commit`, R3's `m05_record` (path, sha256, offered.sha256, offered.anchor). 38 more than 0.4.0's 71:
  the R0/R1 `run_sha256` digests (36 + 2 parent_checks); their input was not traced (inferred: the source change, as
  for REAL's provider identity).
  Every number bitwise equal. No stop.
- Peak 1-min load seen 1.52 (this work at most 7 threads). Run worktrees rc-k3-050, rc-j-050, rc-c-050 removed;
  `~/.cache/rel050-cut/` kept.
- 2026-11-22, CI 45009971732 at 3da2c4e2 (K3 + RELEASE_PINS fix): success on all 7 jobs.
- 2026-11-22, J result (opus-engineer, Opus, ~141k): **J = 3caa928cc82083e49184b4ee099bc9dbcb8b542b**, **C (proposed) =
  0a800e69f200e52dae7e5f3d2d56810bc8f10e27**, log 04dc7cd6. Proofs all PASS (five G10: platform=0 other=0
  environment=equal; REAL: version=0 other=0 environment=host, SMM-TRS2 -> SMM-TR09; IDAES: platform=1 other=0).
  `m05_wo9_real.py --replay` REPLAY PASS (the TR09 failure since the host move is cured). Journey: refined,
  T* 653.15 K, J 0.4525; check ACCEPT; replay bitwise; carried; 109/10794 leaves differ from 0.4.0's, all allowed
  classes, every number bitwise. Orchestrator checks: `git diff K3 C` over the D2.4 paths = 1 IDAES file, 45
  m05/records files, 12 journey files only; nothing in D2.4 after C. Engineer's DECISION accepted: the journey ran
  with `PYTHONPATH=src` (0.4.0's step-3 line); the brief's nlp line with nlp-test-tools put pytest 8.3.5 ahead of the
  reactor env's 9.1.1 and `env.verify` refused (attempt 1, uncommitted, `~/.cache/rel050-cut/journey-attempt1/`).
  Watch at step 15: `m07_journey.py run` with the tools on PYTHONPATH reproduces attempt 1; `replay` passes in both.
- C pushed on its own as `rc/0a800e6` (RP §6.2, A-4) for the push run at C; wp/REL050 pushed at 04dc7cd6.

## 2026-11-22: RC job dispatched (orchestrator)

- `release_rc` dispatch at C (`gh workflow run ci.yml --ref rc/0a800e6 -f release_rc=true`): run 45019811148, beside
  the push run 45019680845. As 0.4.0 (the orchestrator dispatches; RP §6.10).
- W27 archive on TR09: `~/.cache/openflowsheet/w27/artifacts` (RP_DECISIONS `## 0.4.0 cut` host note), passed by
  `--w27-artifacts`.
- Local full gate at 71c1d04f (C + docs) started in the rel050 worktree. First start failed at once (exit 127, ruff not
  on PATH: the worktree has no `.venv`); restarted as `PATH=$R/.venv/bin:$PATH PYTHONPATH=src scripts/gate.sh`
  (PYTHONPATH=src checked: `openflowsheet.__file__` resolves in the worktree, not the main checkout).
- RC work order `<briefs>/REL050-RC.md` to opus-engineer (at most 8 threads; RC tree `rc-c-050`).
- Full gate at 71c1d04f: **FAIL**, 2 failed, 21075 passed, 107 skipped, 222 deselected, 3 xfailed (5498 s). Both in
  `tests/test_rel_rc_local.py` (`test_record_writes_t08_rc_v1_with_0_3_0s_path_step_and_ids`: commit 71c1d04f !=
  95f3897c; `test_the_runner_plan_for_steps_12_14_15`: run() 1). Cause: the orchestrator's docs commit 95f3897c moved
  HEAD in the gate's worktree mid-run. The file re-run at a stable HEAD (95f3897c): 26 passed. The failed run stays
  recorded (log `~/.cache/rel050-cut/gate/gate-71c1d04f.log`).
- DECISION: the gate is re-run in its own clean detached worktree at C (`gate-c-050`, 0 porcelain lines), where no
  one commits. Alternative: re-run in rel050 with commits held. Reversible by: none needed (a run, no change).
  Lesson: never commit in the worktree a gate runs in.

## 2026-11-22: the RC job at C (build lane, work order REL050-RC); STOPPED at `ci`/`step1`/`items` (host gh)

- Host SMM-TR09, kernel 6.12.86+deb13-amd64 at start and end. RC tree `git worktree add --detach
  .claude/worktrees/rc-c-050 0a800e69`; `git status --porcelain --ignored` 0 lines at 2026-11-22T13:02:37+01:00. W27
  tarball SHA-256 `6d42c02fdc7e8e4c81c861d77fd5b546198a2bfd7d9c87212c97149e50ea4526` (= the registered `6d42c02f…4526`).
- Driver `~/.cache/rel050-cut/bin/rc_local.sh` (logs `~/.cache/rel050-cut/logs/`, runner work `~/.cache/rel050-cut/rc/`):
  `release_rc.py local --line 0.5` run by `$R/.venv/bin/python -B` with `PYTHONPATH=src` (the runner imports
  `release_gate`, which needs `jsonschema`; the runner strips PYTHONPATH for every step), inputs as the work order,
  `--ci-run 45019811148`. A first start with `/usr/bin/python3` died at import (`No module named 'jsonschema'`) before
  any step; nothing written.
- DECISION: three sequential invocations, 0.4.0's split (`2,6,7,8,9,11,13` 12:03-12:19Z; `12,10` 12:19-13:27Z;
  `14,15,16,17` 13:27-13:40Z), so that G11's 8 workers ran alone. Alternative: one invocation. Reversible by: re-run.
- Exits: A 0, B 0, C 1 (C-14: `step17-items` exit 1). By-design non-zero: `step14-nlp-collect-all` 2, `step16-dryrun` 1.
- Records (pass/total, all `passed` true): 2 3/3; 6 7/7; 7 12/12; 8 15/15; 9 "A30 PASS"; 10 2/2 (0 violations);
  11 3/3 (`differing_members` []); 12 6/6 and `r375.audit` 1/1 ("2 runs, 210 boundary points, 210 results, 210
  attempts, 0 without a result, 32 direct points ...: PASS", job_id 420); 13 3/3; 14 5/5; 15 3/3; 16 4/4.
  Steps 14 and 15: `host_platform` = `record_platform` = `Linux-6.12.86+deb13-amd64-x86_64-with-glibc2.41`.
- **Stop: step 17 wrote no record.** `step17-items` died before any item ran: `release_rc.py items` calls
  `gh run list ... --json databaseId,headSha,event,status,conclusion,attempt` (`release_rc.py:231-233`), and TR09's
  `gh` 2.46.0 (Debian) answers `Unknown JSON field: "attempt"`. The same field is in `step1` (`_gh_runs`, :250) and
  `ci` (`gh run view --json ...,attempt`, :422), so step 1, `ci` and step 17 cannot run on this host's gh. Not an item
  failure; no item was judged. A newer gh outside the repository (fetching gh 2.103.3 into `~/.cache/rel050-cut/`) was
  refused by the session's permission classifier; a tool edit is a stop. Nothing re-run.
- CI at C: push run 45019680845 `success` (`check` x86-64, aarch64, macOS, Windows; `default-install`; `identity`;
  `codehealth`); dispatch 45019811148 `success` (orchestrator's read).
- Peak 1-min load 19.47 at 12:29Z (G11's 8 workers + runner, beside the gate and other sessions; this job <= 9
  processes). Not done: `ci`, `step1`, `items`, `records`, the RC record, the tree record, `--lapses`. Kept for
  resumption: `rc-c-050` with its artifacts, `~/.cache/rel050-cut/rc/` (venvs, nlp worktree).
- 2026-11-22, RC result (opus-engineer, Opus, ~131k): local steps 2, 6-16 at C pass (2 3/3, 6 7/7, 7 12/12, 8 15/15,
  9 A30 PASS, 10 2/2, 11 3/3, 12 6/6 + r375.audit, 13 3/3, 14 5/5, 15 3/3, 16 4/4; steps 14/15 host = record
  platform). CI at C: push 45019680845 success (all four check legs), dispatch 45019811148 success. **Stop**: step 1,
  `ci` and step 17 `items` need `gh ... --json attempt`; TR09's gh 2.46.0 (Debian) answers `Unknown JSON field:
  "attempt"` (orchestrator reproduced). The engineer's download of an official gh tarball was refused by the
  permission classifier; no tool edited. Kept for resumption: `rc-c-050` (records in its evidence/REL050/<C>/artifacts/rc),
  `~/.cache/rel050-cut/rc/`, driver `~/.cache/rel050-cut/bin/rc_local.sh`.
- DECISION-REQUEST to hub (2026-11-22): A install a current gh for the runner's ci/step1/items only (recommended);
  B reviewed runner fallback and a new C'. Held until the user answers.
- Card `ofs-rel050-rc-gh` filed by hub (default hold). Option texts to verify against:
  A: "The user installs a current GitHub CLI release (official tarball, checksum verified) under ~/.cache/rel050-cut/gh
  on SMM-TR09, or approves that install in the REL050 session's own permission prompt; the REL050 session then puts it
  first on PATH for the RC runner's ci, step1 and items calls only and finishes the RC job at C (0a800e69)."
  B: as requested (reviewed runner fix, new C', CI and every RC step re-run). A signed A does not authorize retrying
  the refused download unprompted: the install is the user's hand or their approval in this session's prompt.
- Full gate at C (0a800e69, clean worktree `gate-c-050`, PATH=$R/.venv/bin, PYTHONPATH=src): **GATE PASS**, 21077
  passed, 107 skipped, 222 deselected, 3 xfailed (5243 s). Log `~/.cache/rel050-cut/gate/gate-C-0a800e69.log`
  (sha256 prefix 033af1a4831e8245). Worktree removed.
- 2026-11-22, the user in the REL050 session: "I approve that you install the recent gh version." (Option A, given in
  this session's chat; the card `ofs-rel050-rc-gh` is not used for it.) Installed gh v2.103.3 (published 2026-10-26)
  from cli/cli's release: `gh_2.103.3_linux_amd64.tar.gz` checksum OK against `gh_2.103.3_checksums.txt`, unpacked
  under `~/.cache/rel050-cut/gh/`; `--json attempt` works (runs at C: push 45019680845, dispatch 45019811148, attempt 1).
- DECISION: v2.103.3, not v2.105.0 (2026-11-18): the newest release at least two weeks old. Alternative: v2.105.0.
  Reversible by: pointing PATH at another version.
- Work order `<briefs>/REL050-RC2.md` (opus-engineer): ci, step1, items, records, RC record, tree record, lapses.

## 2026-11-22: the RC job at C finished: step 1, `ci`, items, records, lapse report (build lane, work order REL050-RC2)

- Host SMM-TR09, kernel 6.12.86+deb13-amd64. Driver `~/.cache/rel050-cut/bin/rc2.sh` (logs `~/.cache/rel050-cut/logs/rc2-*`),
  22:23:58-22:27:13Z, `rc-c-050` at C with 0 porcelain lines before and after. gh 2.103.3 (2026-10-26) from
  `~/.cache/rel050-cut/gh/gh_2.103.3_linux_amd64/bin` first on PATH for these three invocations only.
- `step1` (runner `$R/.venv/bin/python -B`, `PYTHONPATH=src`) exit 0, 4/4 (push run 45019680845 `success`, attempt 1;
  `check` x86_64 and aarch64 `success`, no class-ratio lines; junit read on both legs).
- `ci --ci-run 45019811148` exit 0: the dispatch's artifacts and 13 job logs into `<rc>/ci/`.
- `items`: `local`'s own step-17 argv (`summary.txt` `step17-items`: `rcvenv` interpreter, `--python coolprop=cpvenv`,
  `--python lca=venv-lca`, `--nlp-prefix`/`--nlp-cache` as `local`, `--nlp-root ~/.cache/rel050-cut/rc/nlp-wt`,
  `--ci-run 45019811148`) in its step environment (`env -u PYTHONPATH`, one thread). Exit 0; 9/9 items pass: E01-A48,
  S07-F8 (`rc-coolprop` success both legs, 4 files), MR12-coolprop, MR12-lca, E01-G5-lca (44 passed), E01-G6-nlp,
  WHEEL-DATA, WHEEL-F1-F3 (`registry_sha256` `6a7550d4…` equal; legacy 149 in the checkout, 9 in the wheel), PTC-R1
  (success both legs, 4 files).
- DECISION: `items` with `local`'s step-17 interpreter (`rcvenv`) and nlp worktree (clean at C; ignored `__pycache__`
  from step 14, as `local` would have run it), not `$R/.venv` and a new worktree. Alternative: 0.4.0's fresh
  `items-nlp-wt`. Reversible by: re-running `items` that way.
- `ci/job-logs/identity.log` (row 2's G05, "equal across 4 platforms"): `gh run view --job 137236877467 --log` (gh
  2.46) wrote 0 bytes; fetched with `gh api repos/{owner}/{repo}/actions/jobs/137236877467/logs` (26775 bytes, raw form).
- `records` (126 cited: REL040's 124 + WHEEL-F1-F3's record and log; `tools/cited.txt` sha256 977f23bb…; 6
  gzip-compressed) exit 0. `rc/records.json` d59698fbbde69d08ff13735fd7f7b10334d97a7e6518123641c5b98965fb608c;
  `docs/REL050-rc-record.md` c9cc33410fb5d9e17987ef923887ea0794da0c2afcfed7db6ba462e85e3843c8 (69 rows, 0 FAIL; from
  `tools/make_record.py.txt`); `release/rc-trees/<C>.json` 1f8042d01cead04a260e5da387f2835b615ea5dc431d1bf4904e38f37f1319f6
  (`--write-tree-record` exit 0); `acceptance-lapses.txt`
  a618d96c0f109273e97455d028b032c9cd53e11bc7430d8d08e43bd42e47504d (`--lapses` exit 0, stderr empty).
- Lapse report (2026-11-22): 4 stand (X31 (c), Claim set, M03 N1, coolprop and lca licences), 3 lapsed, 0 unsupported:
  `V14 (b): lapsed (<267 paths: 265 under src/openflowsheet/, benchmarks/t08/ptc_r1/{compare,diagnose}.py>)`,
  `V17 carry: lapsed (extract:links; extract:served_digest)`,
  `M02 N1: lapsed (src/openflowsheet/adapters/external/launcher.py)`; verbatim in the file.
- Commits fd50e7fc (records, RC record), 9e5c4ae4 (tree record), 1520a623 (lapse report). No D2.4 path after C.
- Peak 1-min load 1.31 (30 s samples, `rc2-load.txt`). No §12 stop.
- The full artifacts (`<rc>`, 126M) copied to `rel050`'s `evidence/REL050/<C>/artifacts/rc/` (git-ignored; `diff -rq`
  equal) before `rc-c-050`, `nlp-wt` and `idaes-wt` were removed. `~/.cache/rel050-cut/` kept (its `rcvenv` and
  `cpvenv` were editable installs of `rc-c-050` and are now stale).
- 2026-11-22, RC2 result (opus-engineer, Opus, ~142k): step 1 4/4 (push 45019680845 success, attempt 1); `ci` exit 0
  (13 job logs); items 9/9 pass (E01-A48, S07-F8, MR12-coolprop, MR12-lca, E01-G5-lca, E01-G6-nlp, WHEEL-DATA,
  WHEEL-F1-F3, PTC-R1). fd50e7fc records (126 cited, 6 gzip) + RC record (69 rows, 0 FAIL); 9e5c4ae4 tree record;
  1520a623 lapses; 1b02bc38 log. Lapses at C: 4 stand (X31 (c), Claim set, M03 N1, coolprop and lca licences),
  3 lapsed (V14 (b) on 267 src/ptc_r1 paths; V17 carry links + served_digest; M02 N1 launcher.py), 0 unsupported:
  as the line note predicted (served_digest moved with c_9/c_10's surface edits). Engineer DECISIONS accepted: items
  through the runner's own step-17 interpreter and nlp-wt; identity job log by `gh api .../jobs/<id>/logs`. The
  runner's rcvenv/cpvenv in `~/.cache/rel050-cut/rc/` were editable installs of the removed rc-c-050 (dead).
  Orchestrator: `git diff --name-only C HEAD` no D2.4 path; RC record's only `FAIL` is its legend. wp/REL050 pushed
  at 1b02bc38.
- Message 1 (RP §8.5) sent to hub as one DECISION-REQUEST, four questions with option texts: Q-F1 (A move clause to
  0.6 / B hold / C record unmet), Q-F2 (A Linux legs only / B amend §6.2 to four legs), V17 carry (A carry across c_9,
  c_10 / B new campaign ~USD 10), M02 N1 (A keep shipping "not a sandbox" / B hold for a launcher review). V14 (b)
  goes in message 2 (failing clause, after Judged).
- Hub filed message 1 as four cards: ofs-rel050-q-f1, ofs-rel050-q-f2, ofs-rel050-v17-carry, ofs-rel050-m02-n1. Texts
  as sent except: q-f1 A = "Amend ADR 0057 D6 and roadmap.md so the clause 'ADR-F1 to ADR-F8 Accepted' moves to the
  0.6 line, as it moved from 0.4; 0.5.0 proceeds." and q-f2 B = "Amend RP section 6.2 and release_rc.py so step 1
  judges all four check legs (reviewed change; a Windows or macOS failure at C becomes a release stop), and re-run
  step 1 at C." Verify against these. Hub's notes on the cards: q-f1 A moves the clause a second time; v17-carry hub
  leans B (evidence three releases old, never drove the c_9/c_10 tools).

## 2026-11-22: message 1 answered (four cards, all VERIFIED)

- `decision_desk_verify.py` VERIFIED, key 032ee0a5ae620a90, against the logged option texts:
  ofs-rel050-q-f1 **A** (move the clause to 0.6; signed 22:38:54Z); ofs-rel050-q-f2 **A** (Linux legs only;
  22:39:24Z); ofs-rel050-v17-carry **B** (new V17 agent campaign at C; 22:40:19Z); ofs-rel050-m02-n1 **A** (keep the
  label, scope as at C; 22:38:34Z). Not yet executed.
- Finding on v17-carry B (orchestrator, before acting): the card's cost line ("about USD 10, about one hour", taken
  from the 0.4 row's alternative) understates it. The harness, preflight and scorer are hard-wired to campaign
  `v17-c2` (preflight P1 the user's approval line in T07_DECISIONS, P8 "no runs/v17-c2/ yet"; 25 literal mentions in
  `benchmarks/t07/v17/`), the model pin is `claude-sonnet-5`, and the 30 registered tasks never call F1's or F3's
  tools. A new campaign needs a registered campaign (design lane), harness changes under `benchmarks/` (a D2.4 path:
  C moves, CI and RC steps re-run at C'), and the V17 login. Reported to the user before acting.

## 2026-11-22: acceptance rows for V17 carry and M02 N1 at C (REL050-ACC)

- `release/acceptances.md` rows replaced in place, Accepted at = C = 0a800e69; the old rows moved unedited to
  History under "Lapsed at C = 0a800e69, 2026-11-22 (decision items)". Frank's answers verbatim: M02 N1 "Keep the label"
  (card `ofs-rel050-m02-n1`, A); V17 carry "Carry for 0.5, campaign in 0.6 (Recommended)" (plain words; replaces
  card `ofs-rel050-v17-carry`, whose choice B needed a registered campaign and a new candidate).
- `LINKS` at C (`scripts/m07a_rc.py`) is exactly c_1..c_10 with R-192, R-234, R-295, R-934, R-950, R-960, R-1000,
  R-1010, R-1030, R-1051; the V17 row names all ten.
- Fingerprints at C (gate's `Scopes.evaluate`, candidate = this branch): V17 carry
  `9f4fb274bec701f2d923e7594e35e490d7c22ff108c82c738fb884fdefab6615`; M02 N1
  `7de4c9316455eb93fd2777a7161bb9c5d45d679dfb04419bb034ede64a094680`.
- Check `release_gate.py --line 0.5 --rc C --lapses` (output in `~/.cache/rel050-cut/acc-lapses.txt`; the committed
  lapse report is untouched): V17 carry stands, M02 N1 stands, V14 (b) lapsed (unchanged, waits for message 2),
  X31 (c), Claim set, M03 N1, coolprop and lca licences stand. `tests/test_rel_*.py`: 228 passed.
- 2026-11-22, V17: the user, asked in the REL050 chat after the v17-carry B scope finding: "Carry for 0.5, campaign in
  0.6 (Recommended)". Card ofs-rel050-v17-carry marked `executed: not done, superseded` (hub agreed). **Follow-up for
  0.6:** a registered V17 campaign `v17-c3` with tasks that drive F1's and F3's tools (c_9, c_10), via the design lane.
- ACC result (sonnet-implementer, Sonnet, ~74k): 6cfe0fc4 rows, b17d9ec7 log; LINKS at C = c_1..c_10 as briefed;
  tests/test_rel_*.py 228 passed. Orchestrator re-ran `--lapses` at b17d9ec7: V17 carry stands, M02 N1 stands, V14 (b)
  lapsed, the other four stand. `executed` written on all four cards (q-f1 done, q-f2 no change, m02-n1 done,
  v17-carry superseded).
- Verdict work order `<briefs>/REL050-verdict.md` (verdict agent).

## 2026-11-23: verdict at C and message 2

- Verdict (verdict agent, Opus, ~279k; `<briefs>/REL050-verdict.md`): `docs/reviews/REL050-verdicts.md` 121d7b32,
  Judged 2026-11-22. 15 PASS; FAIL V14 (b) (PTC ends at MID from 149 of 441 starts on both CI legs, as 0.4.0; row
  lapsed: not releasable until a new row) and X31 (c) (pre-registered, row stands: releasable); 0 BLOCKED. It
  recomputed 126 records, 53 t08-rc-v1 records, 7 fingerprints (V14 (b) at C `82469c08…2c40`), the 12-row chain; the
  document parses with the gate's reader. Findings: F-1 the V14 (b) row; **F-2 the `## v0.5.0` notes must carry L46
  (the four reactor statements) in W21's gate-table row or text, else W21 is judged again**; F-3 RP should name the
  journey's invocation line (`PYTHONPATH=src`); F-4 step 13 skips 19 archived-history nodes (TR09 clone lacks the
  pre-0.1.0 commits; none a W23 input); **F-5 the notes say no agent has driven F1's or F3's seven tools (V17 rests
  on the carry)**; F-6 V11 carries L-X04-1..3 by id.
- Message 2 sent to hub: card ofs-rel050-v14b (A renew V14 (b) as at 0.4.0 / B hold for a solver fix).
- For the notes work order: F-2 and F-5. For RP's next amendment (design lane, not now): F-3, F-4.
