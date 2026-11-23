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
