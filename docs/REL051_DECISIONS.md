# REL051 decisions log (append-only; grep it)

## 2026-11-23: the 0.5.1 release starts

- The user (REL050 chat): 0.5.1 now, with X32 and the README, little agent work; "Yes, go; chat answers replace the
  cards". Scan of unmerged origin/wp/* at origin/main 63b00504: only X32 is a ready fix (S10C-diag, S10C-diag2,
  M06-wo17 are old diagnostics). Test merge of X32 onto main: 5 bookkeeping conflicts, cli.py merges clean.
- wp/REL051 created at 63b00504 (worktree `.claude/worktrees/rel051`). Plan in `docs/REL051_STATE.md`.

## 2026-11-23: steps 1 to 3

- Step 1 (68982da7): origin/wp/X32 (7cf27880) merged. Five bookkeeping conflicts resolved by script: CHANGELOG (X32's
  Fixed under Unreleased), envelope (X32 harvest row appended), register (R-1064 between R-1063 and R-1065), support
  matrix `--emit` then `--check` 0 problems (1320 items, 70 manifests), HARVEST_SIZE (107, 1173, 147) measured.
  The step-1 test set: 852 passed, 24 skipped (323 s).
- Step 2 (87e28c64): README Status for 0.5.0 (lead, table row "Released in 0.5.0" with 0.4.0 and 0.5.0 additions,
  claims line, quickstart tag v0.5.0); K3' moves the three strings to 0.5.1 and adds X32's line.
  `release_row_problems` + 8 controls in tests/test_readme_current.py; the old README fails it. RELEASING step 1 names
  the whole section. 33 passed.
- Step 3: RP.L11 (`scripts/release_gate.py:350`) refuses `evidence_package` REL051 on line 0.5 (id of `<line>.0`).
  RP §12 stop reported to the user in chat; the user first chose "Keep REL050". Withdrawn the same turn: RP.S22
  (`release_evidence_manifest._m_harvest`) needs C's tree empty under `evidence/<evidence_package>/`, and
  `evidence/REL050/0a800e69.../` holds 0.5.0's records. Reported to the user, who chose "Option 1": RP amendment A-14
  (RP.L11 takes the id of `<line>.Z` for the largest Z `covers` admits; `release_gate.line_release`), with the single
  verdict agent judging it (no reviewer). R-1069. Line file: covers `0\.5\.[01](?:(?:b|rc)[1-9][0-9]*)?`,
  evidence_package REL051, verdicts REL051, RC record REL051, packages + X32. Loader OK, `tree_problems` []. New test
  `test_l11_a_patch_release_takes_its_own_id` (pass + 3 controls). Release, ledger, readme, workflow tests: 337 passed.
  The user's message (2026-11-23) that this session did not show the earlier 0.5.1 go-ahead: answered, it was in the
  REL050 chat before the /clear, recorded in this state file. `tests/test_rel050_ledger.py` now reads the line file
  at v0.5.0 (63b00504). Note for K3': `RELEASED` in tests/test_v02_main_version.py lacks 0.5.0 (63b00504); add it at
  K3' when the version leaves 0.5.0.

## 2026-11-23: K3'

- 2b74e60d: REL050's manifest harvested (3 limitations, P), HARVEST_EXCLUDED ("evidence/REL051/",), HARVEST_SIZE
  (108, 1176, 147) measured; matrix --check 0 problems; 1449 passed, 43 skipped.
- DECISION: envelope id -> `v0.5-envelope-2` (content differs from 0.5.0's `-1`). Alternative: keep `-1` with release
  0.5.1. Reversible by: the line file's envelope_id, the envelope header and `ENVELOPE_ID`.
- **K3' = 8f7ce045** (full sha in `git rev-parse 8f7ce045`): 0.5.1 in the version files, README, envelope
  v0.5-envelope-2/0.5.1, A10_PINS_0_5_1, RELEASE_PINS, RELEASED + 0.5.0. K3 brief test set: 1982 passed, 45 skipped,
  no failure (the G10 records' version tests are not in that set; J' re-takes them). F0 PASS (M1 50/50, M2 61/61,
  M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42).
- Preconditions at K3' (`~/.cache/rel051-cut/bin/preconditions.py`): P1 all 25 packages have a tested manifest at an
  ancestor (X32 2725fa7d); P3 all required ADRs Accepted; P4 RP.L01-L11 PASS; P6 `ref-x86-64`.

## 2026-11-23: J' and C'

- Re-takes from clean `rc-k3-051` at K3' 8f7ce045 (0 lines, 14:31:20; kernel 6.12.86+deb13-amd64; load 1.4): five G10
  5-7 s, IDAES 7 s, REAL 2022 s (DECISION_STABLE, T* 653.1500351610193, run_cold 32), all exit 0, file sets equal.
  Proofs (`--old-version 0.5.0 --old-host SMM-TR09`; REAL/IDAES `--old-platform Linux-6.12.86+deb13-amd64-x86_64-with-glibc2.41`):
  five G10 PASS with counts equal to 0.5.0's (platform=0 other=0 environment=equal host=0); REAL PASS changed-digests=5
  digest=9 timing=528 path=0 version=0 platform=0 other=0 environment=equal host=0; IDAES PASS differing= (byte-identical,
  not changed).
- **J' = 6cf18bb16682426947bba9d6ecc29e5f8e8dda41** (42 files). At J': `-m nlp test_m05_g10_replay` 5 passed; REAL
  `--replay` REPLAY PASS differences=0 (7 s); retake and journey-record tests 176 passed, 5 deselected.
- Journey from clean `rc-j-051` at J' (0 lines, 15:06:02), PYTHONPATH=src (0.5.0's DECISION): exit 0, 4567 s, refined,
  R3 DECISION_STABLE, T* 653.1500351610193.
- **C' (proposed) = ee934680d94879032b34ae8649baa31ff5a210c8**, the record under `benchmarks/m07/journey/6cf18bb1.../`
  (12 files). Against 0.5.0's record (3caa928c): 71 of 10794 leaves differ, all allowed classes: wall_s (R0/R1 grid
  9+9, budgets R0/R1/R3, accounting R0/R1/R3/journey/t_star_resolve, R3 t_star_resolve), digests (coupling_sha256 R0/R1
  grid and artifacts 9 each, R3 candidate coupling_record_sha256, parent_checks R3/journey run_sha256), `commit`, R3's
  `m05_record` (path, sha256, offered.sha256, offered.anchor). Every number bitwise equal.
- At C' in clean `rc-c-051` (0 lines, 16:22:35): `check` ACCEPT; replay bitwise 27 s (PYTHONPATH=src) and 25 s
  (src:<nlp-test-tools>, step 15's line), tree clean after; OMP_NUM_THREADS=2 exit 2 (refused, as designed);
  `journey_carry(J', C')` carried, differs=(); `tests/test_m07_journey_record.py` 107 passed, 6 deselected.
  `git diff --name-only K3' C'`: 42 m05 records, 12 journey files, 2 docs files.
- C' pushed alone as `rc/ee93468` (RP §6.2, A-4): push run 45204749193; `release_rc` dispatch
  (`gh workflow run ci.yml --ref rc/ee93468 -f release_rc=true`) run 45204778756.
- RC local (`rc_local.sh`: steps A 2,6,7,8,9,11,13; B 12,10; C 14,15,16,17; at most 8 threads) started 16:24:35 in a
  re-created clean `rc-c-051` (0 lines; the first one held replay caches), PID 3261459, driver log
  `~/.cache/rel051-cut/logs/rc-driver.txt`. Full gate at C' in clean `gate-c-051` (0 lines), `gate_c.sh`, summary
  `~/.cache/rel051-cut/gate/summary.txt`. No commit in either tree.
- CI green: 42bafc14 (ci 45182284925, Site 45182284725); K3' push tip 36b64053 (ci 45184678563, Site 45184678643).
- Full gate at C' in clean `gate-c-051` (0 lines before and after, HEAD unchanged): **GATE PASS ee934680: 21126 passed,
  107 skipped, 223 deselected, 3 xfailed, 2 warnings in 5504.65 s** (log `~/.cache/rel051-cut/gate/`). Worktree removed.
- RC local: A (2,6,7,8,9,11,13) exit 0 15:24-15:39Z; B (12,10) exit 0 15:39-16:47Z; C (14-17) started 16:47Z.
- RC local C (14-17) exit 0 16:47-17:02Z; driver done. Runner summary (55 lines, as 0.5.0's 55): non-zero only
  `step14-nlp-collect-all exit 2` and `step16-dryrun exit 1` (step 16 (d)'s registered refusal), both as at 0.5.0;
  `step17-items` exit 0 here (system gh 2.105.0 has `--json attempt`; 0.5.0's stop does not recur): 9/9 items pass
  (E01-A48, E01-G5-lca 44 passed, E01-G6-nlp, MR12-coolprop, MR12-lca A42, WHEEL-DATA, WHEEL-F1-F3, S07-F8 and PTC-R1
  `success` both legs from dispatch 45204778756 attempt 1).
- CI at C': dispatch 45204778756 success (attempt 1); Site 45204748872 success; push 45204749193 still running.
- `ci --ci-run 45204778756` attempt 1 exit 1: `gh run download` stopped after 5 of 14 artifacts, no job logs (log
  `~/.cache/rel051-cut/logs/rc2-ci-attempt1.log`); a manual `gh run download` of the same run into an empty scratch
  directory got all 14. DECISION: a transient fetch failure, not a step result: the partial `<rc>/ci/` (only this call's
  output) removed and `ci` run once more: exit 0, 14 artifacts and 13 job logs, none empty. Alternative: stop and ask.
  Reversible by: deleting `<rc>/ci/` and fetching again.
- RC records checked against 0.5.0's committed ones before writing the RC record: every judged record's checks equal
  except commit, paths, digests, run ids, J', times; step 13's junit 961 tests vs 949 (12 more
  `tests.test_evidence_manifests` cases, the manifests added since 0.5.0's C); A30's `files_digest` of 8 pure-Python
  distributions at unchanged versions (inferred, not traced: the RC venv path moved rel050-cut -> rel051-cut), object
  counts and checks equal; dist/install `0.5.1`; G11/G12 experiment keys moved (provider identity, as at 0.5.0).
- Push run 45204749193 at C': `check (ubuntu-latest)` attempt 1 **failure**, annotation "The hosted runner lost
  communication with the server..." during "Run checks" (infrastructure, no test result); aarch64, macOS, codehealth
  success. DECISION: re-run that failed job once when the run completes (attempt 2); RP §6.2 takes the push run at its
  latest attempt and lists every attempt so that a retry is visible to the verdict; no step re-runs CI. Alternative:
  record step 1 failed and ask the user. Reversible by: nothing to undo (attempt 1 stays recorded).
- RC records committed: e8326949 (126 records, RC record 69 rows, 0 FAIL), e20cd9e9 (tree record), b6779017 (lapse
  report: V14 (b) lapsed by `src/openflowsheet/__init__.py` and `application/cli.py`; six rows stand). Push run
  45204749193 attempt 2 success on every job (identity "equal across 4 platforms", log re-fetched from attempt 2);
  step 1 PASS 4/4. RC trees removed.
- Verdict: brief `<briefs>/REL051-verdict.md`, one `verdict` agent started (the only agent of 0.5.1). The user asked
  why an agent ran ("I thought no additional agents would be used..."); told it is the one narrow verdict pass the
  state file records from the REL050 chat; asked in chat: the user chose "Let it finish".

## 2026-11-23: the verdicts at C' and the two answers

- Verdict agent (`verdict`, Opus at the highest effort, ~227k tokens, 11 min): `docs/reviews/REL051-verdicts.md`,
  commit 50871b17. 15 PASS; V14 FAIL (V14 (b): PTC at MID from 149 of 441 starts on both CI legs, as at 0.5.0); X31
  FAIL (X31 (c), pre-registered). None BLOCKED. A-14 (RP.L11) sound and falsified by its controls, but incomplete: F-7,
  RP.S02's table lists `M.m.1` as not covered (measured: `_m_version_table` fail, `['0.5.1']`). Findings F-8 (notes
  need `## v0.5.1` with the README's phrases, the two FAILs, L46, the G14 sentence), F-9 (CHANGELOG headings
  "unreleased"), F-10 (two README omissions; a fix needs a new C'; not required for 0.5.1), F-11 (the quickstart URL
  resolves after the tag). Orchestrator check of F-7: confirmed in `version_table` (the old table misclassifies
  0.5.1).
- Asked in chat; the user: V14 (b) "Accept for 0.5.1 (Recommended)"; RP.S02 "Extend A-14 (Recommended)".
- V14 (b) row renewed (commit after 50871b17): fingerprint at C' 5718167d…c509 recomputed with `release_gate.Scopes`
  (control: 82469c08… at 0a800e69 equals the committed row's); `--lapses` at HEAD: all seven rows stand.
- A-14 second part: `version_table(name, patch)` and `_m_version_table` with `line_release`; RP §11.1 and §17.7;
  register R-1069 amended. Release tests 244 passed (new: table test, `[0.5]` case, two controls).
- F-10 not acted on (would need a new C'); recorded for 0.6's README.

## 2026-11-23: ledger, notes, H1, H2, step 18 at H2 (RP §9.2 steps 3-7; this session, no agent)

- Ledger a09c4284 (RP.S17): 0.5.1 notes on V14 (the user's row 66e7b7dd), V17, X31; no verdict moves against 0.5.0's
  released ledger. `tests/test_rel051_ledger.py` (baseline v0.5.0 63b00504): 7 passed; control (V14 to PASS) 2 failed.
- Notes a186facc (RP §10): `## v0.5.1` with X32 and the README (from Unreleased), A-14, the `--markdown` table, the
  RP.S10 lines (V14 (b) 2026-11-23, X31 (c) 2026-10-30), W26's G14 sentence, L46 verbatim (F-2), the seven rows, the
  22 phrases once each (RP.S10 measure pass; a first draft quoted the W27 phrase twice, reworded). Notes tests 440
  passed, 2 skipped. F-9 (version headings say "unreleased"): the house form; DECISION: fix the released headings in
  the post-tag working-form commit on main. Alternative: now. Reversible by: one heading edit.
- H1 first run (at a186facc) exit 1: `REL051 implemented ee934680: 31 checks, 29 pass, 2 fail` (RP.S11, RP.S18):
  the RC record's step-1 row said "attempt 1, `failure` ...", which `rc_record_problems` reads as a failed step.
  8cdccd04 rewords the cell (no status word; the step passed at attempt 2) and regenerates the record from the
  committed generator. **H1 = 142daa49** at G = 8cdccd04 (clean): `REL051 tested ee934680: 31 checks, 31 pass, 0 fail,
  0 unsupported`, exit 0, manifest SHA-256 822f0c68ee4986ddf3be6a3e7bd76cb07a0420922d3d034c675191c6ce6dd026.
- H2: nothing to mark (RP.S16: 32 required ADRs, problems [], manifest_adrs []). H2 = H1.
- **Step 18 at H2** (HEAD 142daa49, clean): `release_gate.py --line 0.5 --rc ee934680...` exit 0, last line
  **`v0.5.1 tag may be proposed: YES`**; log `evidence/REL051/<C'>/artifacts/step18-H2.log` (git-ignored), SHA-256
  4ada7d22adeb6f22fca1cf71bc66676c74fa5761f17e29a7ae182ef9f4d6945f. All seven standing acceptances, scope unchanged.
- D2.4: `git diff --name-only C' HEAD` touches none of the D2.4 paths.

## 2026-11-23: merge and dispatch answers (the user, in chat)

- Merge: "Merge when green (Recommended)": "once CI at ca65ec1a is green on all check legs, fast-forward main 63b00504
  -> ca65ec1a in the main checkout, run F0 on main, and push main only if F0 passes. Then dispatch the release workflow
  as a dry run (version 0.5.1, rc ee934680, dry_run ticked)."
- Dispatch: "Session dispatches (Recommended)": "if the dry run succeeds, this session dispatches release.yml on main
  with version 0.5.1, rc ee934680d94879032b34ae8649baa31ff5a210c8 and dry_run unticked. You approve the PyPI upload in
  the GitHub 'pypi' environment when it asks. Only after the workflow has tagged v0.5.1 and published does the session
  commit main's working form 0.6.0.dev0 (RP 7.4), push main, and lift the freeze."

## 2026-11-24: the merge into main and the dry run

- CI 45277785189 at ca65ec1a (H3): success on all four check legs, identity, default-install, codehealth (attempt 1).
- On the user's chat answer: main fast-forwarded 63b00504 -> ca65ec1acaa965bf6caceda5bd9aff10daccc365 in the main
  checkout (clean; origin/main was 63b00504). F0 on a clean worktree at ca65ec1a: PASS (M1 50/50, M2-M5 61/61, M6
  85/85, M7 52/52, M8 105/105, M9 42/42). main pushed; origin/main = ca65ec1a.
- Release workflow dry run: `gh workflow run release.yml --ref main -f version=0.5.1 -f rc=ee934680... -f
  dry_run=true` -> run 45299190200.
- Dry run 45299190200: success (gate `v0.5.1 tag may be proposed: YES`, V14 and X31 FAIL rows; build success; tag,
  pypi, github-release skipped); notes.md is the `## v0.5.1` section.
- On the user's chat answer: dispatched `gh workflow run release.yml --ref main -f version=0.5.1 -f rc=ee934680... -f
  dry_run=false` (origin/main = ca65ec1a) -> run 45299519224: gate, tag, build success; tag `v0.5.1` (object
  9c950102) on ca65ec1a. `pypi` waits for the user's approval in the GitHub environment (still waiting 4 h later).
