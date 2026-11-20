# X07a build decisions (WO1: Windows and macOS CI legs, platform layer)

Brief: `docs/briefs/X07a-WO1.md`. Branch `wp/X07a`, base `main` c4a91a75. Build lane. Each entry:
`DECISION: <question> -> <choice>. Alternative: <x>. Reversible by: <how>.`

## Decisions

- D-1. DECISION: where the platform calls live -> one module `src/openflowsheet/_platform.py`,
  standard library only, in `repo-layers` directly below `openflowsheet._files` (which now calls
  it). Alternative: a package `openflowsheet.platform`. Reversible by: moving the module; it has
  four callers.
- D-2. DECISION: Windows file lock -> `msvcrt.locking(LK_NBLCK)` on byte 0 after `lseek(0)`; the
  refusal (`PermissionError`, EACCES) is re-raised as `BlockingIOError(EWOULDBLOCK)` so both
  callers' existing handling works unchanged. Alternative: `LockFileEx` through ctypes.
  Reversible by: replacing the Windows branch of `lock_exclusive`/`release_lock`.
- D-3. DECISION: removing a held lock file -> `release_lock_file`: POSIX unlinks first, then
  unlocks and closes (the order `release_owner` and `recover` had); Windows unlocks and closes
  first (an open file cannot be removed there) and ignores the `PermissionError` of a prober that
  holds it open. `recover`'s try/finally became `_close_probe(handle, path, remove=ended)`; the
  POSIX call sequence is the same on success and on failure. Alternative: open lock files with
  delete sharing (not available through `os.open`). Reversible by: the one helper.
- D-4. DECISION: Windows process tree -> the worker puts itself first thing in a new Job Object
  with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and holds its only, non-inherited handle; the
  executor's `Process.kill()` (TerminateProcess) closes it and the system ends every process in
  the job. `kill_process_tree` returns False on Windows. Consequence on Windows only: processes a
  worker leaves running are also ended when the worker exits normally. Alternative:
  `CREATE_NEW_PROCESS_GROUP` + CTRL_BREAK (not a forced kill; misses grandchildren). Reversible
  by: the Windows branch of `isolate_process_tree`.
- D-5. DECISION: atomic replace on Windows -> `os.replace` retried on `PermissionError` 50 times
  20 ms apart, then raised; no directory `fsync` (ADR 0061 N12: "fsync ... on POSIX"). ADR 0061's
  verify-and-drop rule is for content-addressed objects (F3, not on `main`) and is not taken.
  Alternative: no retry. Reversible by: `replace_file`.
- D-6. DECISION: the type check on the Windows leg -> POSIX-only names behind `sys.platform`
  if/else branches (mypy evaluates them per platform; `mypy --platform win32` 15 errors -> 0):
  `_load_average` in the two G11 coverage scripts, the V17 harness `_stop`, the BLAS and OpenMP
  probes' `LOADED_LIBRARY_MODE`, the launcher's refusal through `is_windows()` (the test now
  patches `sys.platform` itself). Alternative: `# type: ignore[..., unused-ignore]`. Reversible
  by: commit 05886465.
- D-7. DECISION: CI layout -> the same `check` job and steps with `runner` widened to four values
  (job names stay `check (<runner>)`, which `scripts/release_rc.py` reads); `shell: bash`
  everywhere; `core.autocrlf false` before the Windows checkout. Linux artifact names unchanged
  (`junit-x86_64`, `junit-aarch64`); the new legs upload `junit-<os>-<arch>`. RP §6.2's step 1
  still reads the two Linux legs only: widening the release procedure to four legs is not this
  work order's. Alternative: a separate `check-platforms` job. Reversible by: commit 4fb8a63d.
- D-8. DECISION: `identity` (G05) with a failed leg -> runs unless cancelled (not on a
  `release_rc` dispatch) and compares the legs that emitted their identity (at least two), so a
  red new leg does not suppress the Linux comparison. Alternative: unchanged (`needs: check`
  skips it when any leg fails). Reversible by: the job's `if`.
- D-9. DECISION: CoolProp on the new legs -> not installed; its lock, its licence gate and the
  S07 steps are Linux-only and `OPENFLOWSHEET_REQUIRE_COOLPROP` is unset there, so its tests skip
  with their reason. The extra's wheels are audited (S07 record, `WHEEL_SHA256`) for the two
  Linux wheels only; adding the Windows and macOS wheel hashes needs that audit. Alternative:
  add the two hashes (downloaded: win_amd64 f1f78a2e..., macosx_11_0_arm64 46de36f5...).
  Reversible by: the `runner.os == 'Linux'` conditions.

- D-10. DECISION: text encoding on Windows -> `PYTHONUTF8=1` on the Windows leg (run
  44615939688: F0 and pytest collection stopped on `UnicodeDecodeError: 'charmap'` reading
  `benchmarks/t04/reference_values.yaml` through `tests/test_t04_edge3.py`'s `read_text()`). `src`
  already names `utf-8` at every text read (the one exception reads `/proc/cpuinfo`), so only tests
  and scripts need it. Alternative: `encoding="utf-8"` at every test and script read. Reversible
  by: the line in the Windows step.
- D-11. DECISION: a failed G19 hid the Windows leg's tests -> `Run checks` runs unless
  cancelled; the leg stays red on G19. Alternative: `continue-on-error` on G19 (relaxes the gate;
  rejected). Reversible by: the step's `if`.
- D-12. DECISION: `tests/test_m05_retake_digest_only.py` refused to import on macOS: its guard
  (§11.0, no literal is a real host value) found the made-up `NEW_HOST["cpu_count"] = 3` equal to
  the macos-latest runner's CPU count -> the made-up value is 7 (5 and 96 are taken). The guard is
  unchanged. Reversible by: the literal.

- D-13. DECISION (WO2): every Linux leg of run 44629506428 failed on T08.A21 and M07a.A50: the
  manifest added at 37049c8a was not harvested -> T08 harvest rows (class P) for it and
  `HARVEST_SIZE` (100, 1139, 147), as every package that adds a manifest does (commit 8b1c7671).
  A later manifest needs the same rows. Alternative: none (the gate is the rule).
- D-14. DECISION (WO2): the Windows "G19 hang" -> not a hang in G19: G19 fails in seconds (Q-1) and
  `Run checks` then runs pytest, which took 175 min on Windows in run 44618922484 (17068 tests,
  Linux about 115 min). The `check` job gets `timeout-minutes: 300` so a real hang ends bounded.
  Alternative: no bound (default 360 min). Reversible by: the line. `gh run cancel` of the two
  long runs was refused by the session's permission classifier; they end on their own.
- D-15. DECISION (WO2): the CI pytest summary names failures -> `PYTEST_ADDOPTS: -rsfE` (was
  `-rs`), so a leg's failures are read by grep. Output only. Run 44652504290 showed it inert:
  `check.sh`'s own `-rs` comes later on the command line and wins, so `check.sh` now passes
  `-rsfE` itself. Reversible by: the env line and the `check.sh` flag.
- D-16. DECISION (WO2): `bash` in tests on Windows resolved to the WSL launcher (CreateProcess
  searches System32 before PATH; 33 failures in `test_release_workflows.py`, stderr "wsl.exe
  --install <Distro>") -> `conftest.BASH`: `shutil.which("bash")` on win32, the bare name
  elsewhere (Linux argv unchanged). Portability bug in the tests, fixed.
- D-17. DECISION (WO2): a corpus name with ":" (`T05b:DZ-3`) as a directory name (WinError 123,
  13 failures in `test_t07_w3a_revision_runs.py`) -> the test's directory replaces ":" by "_".
  Portability bug in the test, fixed.
- D-18. DECISION (WO2): `os.kill(pid, signal.SIGKILL)` on a `multiprocessing.Process` -> its
  `.kill()` (the same SIGKILL on POSIX, TerminateProcess on Windows) in `test_t07_store.py` and the
  server kill of `test_t07_w4c_process_executor.py`; tests that judge the POSIX exit code
  `-SIGKILL` are a platform limit (row below).

- D-19. DECISION (WO2): the codehealth job's "Debt ratchet against origin/main (informational)"
  fails on `debt over touched files rose 55.30 -> 58.30`, all of it the new
  `src/openflowsheet/_platform.py` (0.0 -> 3.0; health 9.5). The job is `continue-on-error: true`
  by design (S17, ci.yml `codehealth`): expected for a branch that adds a module, not fixed.

- D-20. DECISION (WO3): the reasons of an inspected replay off the registered set -> judged as the
  code emits them: the `running on <machine>/<system>, which is not a registered platform` reason
  followed by `no rerun was supplied`, the note `run.replay.replay` appends when it re-runs nothing
  and `revision_replay._inspected` keeps (F0 M7 `M7_NOT_RERUN`; `conftest.NOT_RERUN_NOTE` for P1c).
  The ruling (R1.4, P1c, A5) says "exactly one reason"; measured under a simulated Darwin identity,
  every bundle M7 replays and every OPT-A2 member reports both. A lock reason, an unknown policy, a
  foreign or a third reason, or a missing note still fail. Alternative: drop the note in
  `_inspected` when the environment decided the mode (changes what replay reports on Linux too, so
  not the build lane's). Reversible by: the two constants and the A5 cases.
- D-21. DECISION (WO3): the P1c helper `assert_inspected_off_registered(report, row=...)` takes a
  `ReplayReport` or its document (the CLI's `--json`, the G11 subprocess) and groups the reasons by
  member: an optimization record's report prefixes each with `<member>: ` (`starts/0/start: ...`),
  and each member must carry the `running on` reason, then at most the note of D-20. Alternative:
  one helper per report shape. Reversible by: the helper.
- D-22. DECISION (WO3): the M03 platform-difference row (X07a-L3) registers the five paths the macOS
  leg measured, not F-5's one: WO2's log excerpt showed only the margin; run 44652504290's full
  message names five (table below). Registering them is P3c's interim; classifying them is Q-4.
- A2 (WO3, measured 2026-11-20): over the A1 grid, `decide_mode` at `bd7548e4` against C1: 288
  environments, 82 944 ordered pairs, 82 880 identical in mode and reasons, 64 differ (every one a
  pair of equal environments on arm64/Darwin or AMD64/Windows, inspected -> `exact_replay`), 0 with
  both sides registered. Modes after C1: 128 exact, 4 544 compatible, 78 272 inspected. Script:
  a scratch copy of `git show bd7548e4:src/openflowsheet/run/replay.py` against the branch module.
- ADR 0007 Amendment 3 is **proposed**, not accepted: C1 (commit b27c69a1, revertible alone) builds
  against it. X07a's merge into `main` waits on Frank accepting it (a Decision Desk card).

## Design-lane questions (left failing, not chosen)

- Q-1 (G19 on Windows, run 44615939688): `t07_licence_inventory.py` FAILED, 30 distributions:
  `pywin32 312: PSF (compiled) not-allowed`. pywin32 is `mcp==1.30.0`'s Windows-only requirement;
  it is not in `requirements.lock` (frozen on Linux), so on Windows it is also unpinned. Needed: a
  licence ruling on pywin32 (PSF-2.0 family, compiled) and a decision on a per-platform lock entry.
  **Closed (WO5)** for the licence: Frank, ofs-x07a-pywin32-licence A (R-1063); G19's `ALLOWED_FOR`
  admits `("pywin32", "PSF")` only. The lock half is Q-12.
- Q-12 (WO5, the lock half of R-1063; stop condition of the WO5 brief, lock edit not committed). The
  lock that installs the server extra on Windows is `requirements.lock` (ci.yml "Install locked
  dependencies", `pip install -r requirements.lock` on all four legs). Measured on this workstation
  with `pywin32==312 ; sys_platform == "win32"` inserted after `python-multipart` (then reverted):
  the lock's SHA-256 moves `ead4edf1...b9c4` -> `0f02fc83...6f2e`; `verify_lock` on Linux returns
  `("", ("the lock openflowsheet/_data/requirements.lock is malformed at line 36: ...",))` (F2: D2.2's
  `NAME==VERSION` fullmatch admits no marker), so `lock_sha256` is `""` on every platform; F0 FAIL
  `M7 FAIL 52/52` (every bundle `NOT_RUN`, "this side's lock did not verify"), M1 to M6, M8, M9 equal;
  the lock's pinned digest fails 46 tests in 6 files (test_x05_lock 41, test_s07_packaging 2,
  test_t08_w1_records 2, test_t08_w4_rc 1, plus test_t07_server_extra through S07 A41's subprocess);
  `scripts/t08_rc.py` `LOCK_SHA256` and the A30 records pin it too. Any edit of the file, even one D2.2
  accepts, moves the digest. Options: (a) a Windows-only increment lock (`requirements-windows.lock`,
  `pywin32==312` with its wheel hashes, `pip install --no-deps --require-hashes` on the Windows leg,
  the `requirements-coolprop.lock` pattern of R-624), `requirements.lock` unchanged; (b) an ADR 0069
  amendment admitting markers in D2.2 and a re-registration of the lock digest; (c) no pin: pywin32
  stays resolved from `mcp`'s `pywin32>=310; sys_platform == 'win32'` (312 today). Default proposed:
  (a), the action's "the lock" read as a Windows lock; not built, since the card names "the lock".
  **Closed (WO6)**: Frank, ofs-x07a-pywin32-lock A (R-1063 amended): `requirements-windows.lock`,
  `pywin32==312 --hash=sha256:c53e878d...aaf9` (cp313 win_amd64, `pip download`, PyPI agrees),
  `--no-deps --require-hashes` on the Windows leg; `requirements.lock` byte-unchanged.
- Q-2 (F0 M7 on macOS, run 44615939688): `F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 NOT JUDGED,
  M5 61/61, M6 70/70, M7 FAIL 52/52, M8 105/105, M9 35/35`. M2, M3, M5 are equal: no floating-point
  difference. M7: every one of the 52 v0.3.0 bundles is `{'verdict': 'NOT_RUN', 'integrity_ok':
  True}` against the registered `MATCH` (first: `k05/SYN-001-nominal`), because `decide_mode` gives
  `inspected_archived_results` for a Linux-written bundle on macOS (`run/replay.py:239`), which is
  the replay policy, not a defect. F0 judges `verdict` on every platform (`M7_PORTABLE`). Needed: a
  ruling on M7's expected verdict per machine class (ADR 0067 D7, R9: per-platform reference
  records).

- Q-2 extended (WO2, runs 44618922484 and 44629506428): the same rule fails tests, not only F0.
  `run/replay.py:53` `REGISTERED_PLATFORMS` holds `(x86_64, Linux)` and `(aarch64, Linux)` only, so
  `decide_mode` gives `inspected_archived_results`/`NOT_RUN` for every rerun on Windows and macOS,
  a same-host rerun included. macOS: about 90 of 144 failures (47 `test_g8_rerun_matches_on_the_same_host`,
  `test_a16_a17_the_replay_matrix`, `test_g16*`, `test_t07_q26_*`, ...); Windows: 54 of the rest.
  Registering a platform for replay is the same ruling as Q-2.
- Q-4 (WO3, ruling section 8, extended by D-22): are M03's `splits[].margin`,
  `regularity.inverse_one_norm_estimate` and `regularity.solution_error_bound_scaled` compared
  with the class and floor the policy gives them (ruling P3b)? The numbers are row X07a-L3's.
  `solution_error_bound_scaled` moves by a factor 3.07 (relative 2.07) while its operands move by
  about 2.3e-9 relative: it is an error bound scaled by a residual at noise level, compared with
  its D2.2 floor 1e-8 against values of 1.8e-8 and 5.5e-8. The ruling's default (no floor for the
  margin) does not cover the two regularity paths, which F-5 did not show. Not chosen (stop
  condition "a P3b classification that the policy's text does not settle"); the row stands.
- Q-10 (WO3, row X07a-L5): TH-C1's companion (b) on macOS differs in `certificate_id` (a digest,
  compared for value: P3b names this as a comparator departure) and `energy.overall.closure` (a
  near-zero closure with no floor). Fixing the comparison changes `run.compare` on every platform:
  not chosen; the row stands.
- Q-11 (WO4, row X07a-L10): `test_b34a_the_outcome_counts` on macOS moves two regions from
  `BOUND_BLOCKED` to `SPECIFICATION_CONFLICT`. Is a regression count of discrete solver outcomes a
  bitwise expectation (P2, the default taken: the outcome is a function of the run's floats at a
  decision boundary), or is a platform-dependent outcome class a robustness question for T05b's
  outcome rules (which outcome a region near the boundary should take)? Not chosen beyond the
  provisional row; which two regions move was not identified (no macOS host).
- Q-3 (WO2, macOS run 44629506428): floating-point differences against Linux-recorded fixtures,
  for example `test_every_registered_call_is_bitwise_the_baseline[kernel_targets]`
  (`_same(1.9163045025588417, 1.9163045025588423)`), `test_the_fixtures_are_what_real_runs_emit_today`
  (`qualification.outcomes[8].splits[1].margin: 1.3370443359361772e-05 against 1.33704433897...`),
  `test_th_c1_golden[csv,json,text]`. Per-platform reference records are a design-lane ruling
  (ADR 0067 D7, R9); left failing.

## Platform limits (deliverable 4)

| Test or module | Platform | Reason | Lifted by |
| --- | --- | --- | --- |
| `tests/test_m02_kill_chain.py` (module `skipif`, pre-existing) | macOS, Windows | G3 is registered on Linux (ADR 0033 D2: macOS best effort, Windows refused before spawn) | X07b |
| `adapters/external/launcher.py` `launch` | Windows | `external_execution_unsupported_platform` (ADR 0033 D2), typed result | X07b |
| CoolProp tests (`tests/s07_coolprop_support.py` skip) | macOS, Windows | extra not installed: wheels audited for Linux only (D-9) | S07-style wheel audit (X07b) |
| `tests/test_m06_browser_smoke.py` (module skip, as when no browser is found) | Windows | the driver passes `--remote-debugging-pipe` fds 3/4 by `dup2` (POSIX); run 44617827438 | a Windows pipe driver (X07b or M06 follow-up) |
| `spikes/p02/common/timing.py` `measure_memory` | Windows | POSIX `resource` (now imported in the function; the module imports everywhere) | not needed by any test |
| `nlp`, `pymrm` marked tests (deselected by `-m` on every leg, pre-existing) | all | opt-in environments | X07b |
| `tests/test_s19_w5_identity.py` (`facts`, `scratch`, `_tool`), `tests/test_s19_w5_gate.py` (`sets`) | Windows | the W5 base tree is imported to measure facts and imports `fcntl` (it predates `_platform`); run 44618922484, 45 errors + 19 failures | a W5 base at or after X07a's merge (S19) |
| `tests/test_t07_w4c_process_executor.py` 2 tests, `tests/test_t07_w4e_error_mapping.py` 1 test (`NEEDS_SIGKILL`) | Windows | the lost worker is made by SIGKILL and judged by its POSIX exit code; run 44618922484 | X07b (Windows kill-chain semantics) |
| `tests/test_t07_v17_c2.py` (`_posix_only` in `_operator`, `identity_claude`, one test) | Windows | V17 harness: token secrecy is checked on POSIX mode bits (Windows reports 0o666), stand-in `claude` is a shebang script; run 44618922484 | not planned (V17 runs on the Linux workstation, R-116) |
| `tests/test_t07_w7a_harness.py` (`fake_claude`) | Windows | the stand-in `claude` is a shebang script run with a POSIX PATH; run 44618922484 | not planned (as above) |
| `tests/test_p03_a30_workload.py::test_s9_5_control_a_registered_module_failing_on_pyomo_is_recorded` | macOS, Windows | the A30 workload (`scripts/p03_binary_inventory.py` `_WORKLOAD`) reads `/proc/self/maps`; the binary inventory is a Linux measurement (the `a30-inventory` job); s9_5a to d fail before the read and run everywhere; run 44670029066 | not planned (a binary inventory per platform would be X07b's) |
| `tests/test_m02_experiments.py` (18 tests), `tests/test_x02_wo4_external.py` (10), `tests/test_m02_wo10_coupled.py` (8), marked `conftest.NEEDS_EXTERNAL_CHILD` | Windows | the experiment child is spawned by `external-subprocess-v1`, which refuses Windows before spawn (ADR 0033 D2, the `launch` row above): every attempt ends `environment_unavailable` (37 nodes); the refusal is `test_m02_kill_chain::test_refusals_before_any_spawn`'s (on Linux, `sys.platform` patched); run 44670029066 | X07b |
| `tests/test_t07_w5b_cli.py::test_the_existing_commands_are_unchanged_byte_for_byte`, `::test_r148_with_v1_recorded_the_commands_print_the_v1_pins`, `tests/test_t08_rename_substitution.py::test_with_the_pre_rename_self_hashes_the_cli_prints_the_pre_rename_pins` | Windows | the pinned transcripts of every CLI command were recorded on Linux and carry POSIX paths after `<ROOT>`; the CLI prints the host's native paths (`<ROOT>\broken.yaml`), which is correct there; run 44670029066 | per-platform transcripts (not planned) |
| `tests/test_m07_journey.py::test_a00_the_generator_check_passes`, `::test_a15_r2_is_not_promotable_with_m04s_reasons_and_no_evaluation`, `tests/test_m07_journey_record.py::test_a21_r3_is_the_r3_document_of_its_m05_record` (4) | Windows | `scripts/m07_journey.py` `_relative` writes `str(path)` (backslashes); the file is a member of the M07 carry `journey_files` (`benchmarks/m07/registration.json`), so the one-word fix (`as_posix()`) is held back (D-28); run 44670029066 | the next M07 journey re-take, which may edit its carry members |
| `tests/test_m02_pymrm_child.py::test_a_sigint_ends_the_child_by_the_signal_not_sigabrt` | Windows | `send_signal(SIGINT)` to a child and a negative return code are POSIX (`ValueError: Unsupported signal: 2`); run 44670029066 | not planned |
| `tests/test_t07_w7a_harness.py::test_token_placement` | macOS | V17 harness (as the Windows rows): the stand-in session's cwd, empty on Linux, lists `nonexistent` on macOS (the session's `HOME` is `/nonexistent`; the stand-in runs as `/usr/bin/env python3` with `PATH=/usr/bin:/bin`, the system shim). Cause not diagnosed (no macOS host); the other `one_run` tests pass there; run 44670029066 | not planned (V17 runs on the Linux workstation, R-116) |
| `tests/test_s03_references.py::test_a10_the_comparison_recomputes_identically_from_the_committed_files` | Windows | `scripts/s03_reference_comparison.py` keys `inputs_sha256` by `str(path.relative_to(ROOT))` (2 keys with backslashes); S09 A02 (`test_s09_references.py::test_a02_s03_is_untouched_since_its_merge`) holds the file byte-identical to `390e0af5`, so the `as_posix()` fix is held back (as D-28); run 44670029066 | an S03 re-take that may edit its classifier |
| `tests/test_c9_w27_v2.py::test_generator_check` | Windows | `w27_registration_v2.py` records `document` and `generator` as native paths; version 3's `BASE_PINS` pin the generator's bytes (`0963c445...5708`), so the fix is held back; version 3's own generator is fixed (s11 a32); run 44670029066 | a W27 version 4 re-pinning version 2 |
| `tests/test_s16_test_impact.py::test_runtime_open_record_walks_library_frames_and_drops_imports` | Windows | the test-map runtime (`scripts/test_impact_runtime.py:98`) matches an opened path by the POSIX prefix `root + "/"`; the map is built only in the Linux test-map venv (`docs/test-impact.md`), an inner-loop aid, never a gate; run 44670029066 | not planned |
| `tests/test_t08_w4_v0_1_gate.py::test_the_recorded_tree_gives_git_s_answer` (skipped by `conftest.FROZEN_WINDOWS_LIMITS`, the file cannot carry a marker) | Windows | its `chmod(0o755)` is no mode change where git has no executable bit; WO5's `update-index --chmod=+x` fix (2bb2c157) broke M07a.A13 (`test_a13_the_v0_1_gate_and_its_test_are_byte_identical_to_the_base`, registered `4caa7d86...6de55`, `benchmarks/m07a/reference_values.yaml:114`) and is reverted (WO6) | a v0.1 gate re-registration (not planned) |
| `tests/test_m07a_v0_2_gate.py::test_a07_t08_a50_s_and_r_151_s_states_give_v0_1_s_answers` (skipped by `conftest.FROZEN_WINDOWS_LIMITS`, the file cannot carry a marker) | Windows | its `chmod(0o755)` is no mode change where git has no executable bit; the `update-index --chmod=+x` fix (672fe9f0) broke M07.A31(b) (`tests/test_m07_v0_2_gate.py::test_a31_b_the_alpha_s_tests_are_the_tagged_ones_but_the_four_edited`, the top-level AST against the 0.2 alpha tag, CI 44722847356) and is reverted (WO7) | a 0.2 alpha tests re-registration (not planned) |

Rows found by the CI legs are added below with their run id.

### Replay and floating-point rows (WO3, ruling P1 to P5)

Ids are carried by the code (`bitwise_baseline(row=...)`, `assert_inspected_off_registered(...,
row=...)`, `conftest.PLATFORM_DIFFERENCES`); `tests/test_x07a_platform_rows.py` asserts the two sets
of ids are equal.

| Row | Test node(s) | Platform | Class | Numbers (P3a) | Run | Lifted by |
| --- | --- | --- | --- | --- | --- | --- |
| X07a-L1 | `tests/test_t05b_kernel_inert.py::test_the_baseline_is_what_the_generator_emits_today`, `::test_every_registered_call_is_bitwise_the_baseline` (all groups) | macOS, Windows | bitwise (P2) | `kernel_targets` 1.9163045025588417 against 1.9163045025588423: 3 ulp, 3.5e-16 relative (F-5) | 44629506428, 44652504290 | never by registration: a baseline recorded or measured bit-identical on the platform (`BITWISE_BASELINE_PLATFORMS`) |
| X07a-L2 | `tests/test_st_cli.py::test_th_c1_golden[csv,json,text]`, `::test_output_writes_the_file_and_prints_nothing` (the CSV golden's bytes) | macOS, Windows | bitwise (P2); companions on every leg: (a) `test_th_c1_the_goldens_are_the_formatters_image_of_the_json_golden`, (b) `test_th_c1_a_fresh_solve_is_the_json_golden_under_the_policy` | (b) measures it | 44629506428, 44652504290 | as X07a-L1 |
| X07a-L3 | `tests/test_m03_schemas.py::test_the_fixtures_are_what_real_runs_emit_today`, fixture `study/sensitivity_result/valid/b1_forward_phase_boundary.json` | macOS | policy-bounded (P3c) | macOS against Linux, bound max(1e-9 rel, floor): `qualification.outcomes[8].splits[1].margin` and `qualification.splits[1].margin` 1.3370443359361772e-05 against 1.3370443389781883e-05, 3.04e-14, bound 1.34e-14 (no floor), ratio 2.28; `qualification.regularity.inverse_one_norm_estimate` 563097.6782451527 against 563097.6769593855, 1.29e-3, bound 5.63e-4 (its D2.2 floor, absolute 0.0), ratio 2.28; `qualification.regularity.solution_error_bound_scaled` 5.5097787861064925e-08 against 1.7963045774504667e-08, 3.71e-8, bound 1e-8 (its D2.2 floor), ratio 3.71; `refusals[0].message` float 0 of its text, the margin's numbers (ADR 0025 D6) | 44652504290 | Q-4 (classification, P3b) or the platform's registration with an ADR 0067 D7 record |
| X07a-L5 | `tests/test_st_cli.py::test_th_c1_a_fresh_solve_is_the_json_golden_under_the_policy` (X07a-L2's companion (b)) | macOS, Windows (WO9, review R-3: the same three paths) | policy-bounded (P3c) | `<root>.certificate_id` 'cert-47d7a759d62a' (macOS), 'cert-eb29b5b86be8' (Windows) against 'cert-a23b2407ff55' (a digest compared for value); `<root>.energy.overall.closure` (macOS -1.10958353...e-10, Windows 6.184563972...e-10) and `<root>.energy.units[0].closure` (WO4: the third path, in the set pytest printed, not in its truncated message), near-zero closures, relative 1e-9 with no registered floor (ADR 0007 D2.3) | 44670029066 (macOS), 44736771069 (Windows) | Q-10 (P3b classification) or registration with a D7 record |
| X07a-L4 | `tests/test_opt_replay.py::test_g13_the_committed_record_replays_to_match_without_ipopt`, `::test_g11_replay_imports_neither_pyomo_nor_cyipopt`, `::test_g13_reproduce_imports_and_replays_an_optimization_record`, `::test_g13_the_cli_replays_an_optimization_record` | macOS, Windows | replay-committed (P1c): OPT-A2 was written on x86-64 Linux | - | 44652504290 | the platform's registration (ruling E-3) |
| X07a-L6 | `tests/test_m01_provider.py::test_f2_the_counterexample_has_one_root_and_no_liquid` (both states) | macOS (measured), Windows (skipped by the marker) | bitwise (P2): the F2 states are ulp-level counterexamples found on Linux, beside the discriminant's zero; the root count is the image of that platform's bits. Companion on every leg: `test_f2_every_returned_root_is_a_root_across_the_spinodal_crossing` (±60 ulp of the committed `float.hex` A and B) | `real_roots(400.0, 10025791.149338447, pure)` gives more than one root on macOS (`too many values to unpack (expected 1)`); the state at ...482 passes | 44670029066 | as X07a-L1 |
| X07a-L7 | `tests/test_m02_schemas.py::test_g1a_the_fixtures_are_what_the_code_emits_today` | macOS (measured), Windows (skipped by the marker) | bitwise (P2): `stable(fixture) == stable(document)`, `==` on floats of Linux-recorded fixtures | first differing fixture `experiment_coupling/valid/standin_loop.json`, last digits only, for example 0.6984587611993993 against 0.6984587611994003, `coolant_flow` 0.006397747615876461 against 0.006397747615876485 | 44670029066 | as X07a-L1 |
| X07a-L8 | `tests/test_m02_wo10_coupled.py::test_rp2b_the_seam_reaches_the_reactor_rate` (split from `test_rp2b_a_w_dependent_rerun_one_ulp_off_matches_not_bitwise`, which keeps `MATCH`, not bitwise, `w` moved and the served reason on every leg) | macOS (measured), Windows (skipped by the marker) | bitwise (P2): the witness that a 1-2 ulp seam at k = 1 reaches `r_xi` was measured on Linux's iterates (`OneUlpOnTheFirstClip`: "two at this point") | on macOS every iterate's `r_xi` is bit-equal to the record's (`assert any(...)` False) while `bitwise_floats` is False | 44670029066 | as X07a-L1 |
| X07a-L9 | `tests/test_t06_w6_a85.py::test_a85b_every_published_split_column_is_the_rule_applied_to_its_stream`, `tests/test_t06_w30_holdout.py::test_a85b_every_holdout_split_column_is_the_rule_applied_to_its_stream` (all cases) | macOS (measured), Windows (skipped by the marker) | bitwise (P2): `_same` is "bit for bit" against the published split columns; heater style only since WO9. Companions on every leg (review R-6): `test_a85b_every_published_products_split_total_is_the_sum_of_its_flows`, `test_a85b_every_holdout_products_split_total_is_the_sum_of_its_flows` (the products style, Python `sum` over committed floats in a fixed order) | w30 NET-02 start 21 `S3.vap.A` 0.9812393267462561 against 0.981239326746256; w30 NET-03 start 25 `S9.vap.A` 0.30926437883431707 against 0.30926437883431684; w6 NET-03 start 3 `S4.vap.A` | 44670029066 | as X07a-L1 |
| X07a-L10 | `tests/test_t05b_candidate_answers.py::test_b34a_the_outcome_counts` | macOS (measured), Windows (skipped by the marker) | bitwise (P2), provisional (Q-11): a regression count, recorded on Linux, of discrete outcomes that are a function of the sweep's floats, compared by `==` | macOS: `BOUND_BLOCKED` 2 -> 0, `SPECIFICATION_CONFLICT` 6 -> 8 (CONVERGED 82, ACTIVE_SET_CYCLING 10, STAGNATION 4 equal) | 44670029066 | as X07a-L1, or Q-11 |
| X07a-L11 | `tests/test_opt_cost_lca.py::test_the_hand_model_reproduces_p1` | Windows (measured), macOS (skipped by the marker) | bitwise (P2; review R-4: a bound below the policy on floats recorded on another platform): the host's fresh TH-C1 solve, carried through `sizes`, against `P_SIZES` recorded on Linux (`cost_hand.py:764`, the state of TH-C1's `certificate_id`), bound 1e-13. Companion on every leg: `test_the_hand_model_reproduces_p1_under_the_policy` (the same `p1_check` at 1e-9 relative, ADR 0007 D2.1) | Windows: `sizes_worst_relative` 1.7483368258677137e-12, `opex_total_relative` 2.07e-16 | 44736771069 | as X07a-L1 |
| X07a-L12 | `tests/test_rel_evidence_manifest.py::test_rel_a20_over_0_3_0s_committed_records` (RP.S03's same-form line) | Windows (while `test_m07a_v0_2_gate.py::test_a07_t08_a50_s_and_r_151_s_states_give_v0_1_s_answers` is a key of `FROZEN_WINDOWS_LIMITS`) | registered consequence of a frozen Windows limit (review R-5, Q-13 option A): RP.S03's D selection runs `test_m07a_v0_2_gate.py`, whose a07 skips there, and S13a's rule (none skipped) makes it `fail`. Expected exactly `RP.S03 same form: fail; S13 V03.A03 pass: DIFFERS`, RP.S03 in RP.S18's `not_pass` and outside the changed form, `REL.A20: FAIL`; with RP.S03 set aside the other 11 same-form keys, RP.S18's A-1 sub-check and the controls are judged as on Linux (`conftest.FROZEN_WINDOWS_CONSEQUENCES`) | `RP.S03 same form: fail; S13 V03.A03 pass: DIFFERS` | 44736771069 | the a07 limit's lifting (the rows test fails while the row outlives its key) |

## WO4 decisions (2026-11-20)

- D-23. DECISION (WO4): the `codehealth` job of 44670029066 failed on this branch's code (`diff`
  debt 62.60 -> 67.60: `_platform.replace_file` nesting 4, `decide_mode` boolops 4) -> fixed
  (b39ada81): the exact rung is the predicate `_alike_and_pinned`, `replace_file` has no nested
  raise; a new test pins the Windows retry contract and passes on the old and the new code. Local
  `codehealth diff` PASS 62.60 -> 62.60. Alternative: a suppression. Reversible by: the commit.
- D-24. DECISION (WO4): P2 rows mark the whole node, every parameter (L6, L9), as P2 says; the rp2b
  witness is split into its own node so that `MATCH`, not bitwise, stays judged on every leg (L8).
  The A85b products-style columns (sums of committed floats) are a P2 companion not yet split out.
  Alternative: per-parameter marks. Reversible by: the markers.
- D-25. DECISION (WO4): `t08_rc.py install-check` on a machine without an A30 summary records
  `a44.casadi_files_equal_a30` failed with `expected: null` and writes the record (was a
  `KeyError`): a portability bug, not a limit; Linux records unchanged. Reversible by: ff7a1437.
- D-26. DECISION (WO4): the manifest moves to 9773c361 (run 44670029066, the last run complete on
  four legs at WO4), `limitations[0]` rewritten (Amendment 3 proposed, the two unregistered
  platforms), harvest rows re-hashed (54fb9423..., 4264fe29...); `HARVEST_SIZE` unchanged (same
  items). A6: the new test `test_a6_this_hosts_lock_is_verified_and_its_platform_is_the_reported_one`
  logs `MSG X07a-A6: lock_sha256 <sha> on <machine>/<system>` per leg; F0 M7 PASS on macOS and
  Windows in 44670029066 already implies a verified lock there (Q-6 yes on both).
- D-27. Frank accepted ADR 0007 Amendment 3 (Decision Desk ofs-x07a-adr0007-am3, option A, 2026-11-20,
  `VERIFIED`; R-1062): copied into `docs/adr/0007-reproducibility-certificate-policy.md` unchanged; no further
  replay platform in 0.5. The manifest's `limitations[0]` and its harvest row (sha256 bbf06597...) say accepted.
  Frank allowed pywin32 (ofs-x07a-pywin32-licence, option A, `VERIFIED`; R-1063): Q-1 is answered, its build is a
  separate work order.

## WO5 decisions (2026-11-20)

- D-28. DECISION (WO5): a portability fix in a file that is a member of an M07 carry
  (`benchmarks/m07/registration.json` `journey_files`, `r3_files`: `scripts/m07_journey.py`,
  `scripts/m05_wo8_runs.py`, `scripts/m05_wo9_real.py`) is not made: editing a carry member ends the
  carry of the committed journey records from their anchor. The M05 retake test is fixed on the test
  side only (its sidecars written with LF); `m05_wo8_runs` still writes text sidecars with the
  platform's newline (a Windows re-take would write CRLF; none is planned). Alternative: fix both
  scripts and let the next journey re-take re-derive R3. Reversible by: the fix, one line each.
- D-29. DECISION (WO5): a path written into a record or compared as a set key is POSIX
  (`as_posix()`), in tests and in `scripts/release_rc.py` (`records`, `output`); a generator's text
  file is written with `newline="\n"` (`scripts/registry_builtin.py`). Linux bytes unchanged.
  Alternative: rows. Reversible by: the commits.

## WO6 decisions (2026-11-20)

- D-30. DECISION (WO6): the Windows leg installs `requirements-windows.lock` **before**
  `requirements.lock`, not after it as the WO6 brief says (the card names no order). Measured
  (pip 25.1.1, scratch venv): with `six==1.16.0` installed, `pip install --no-deps
  --require-hashes -r` a lock giving it an all-zero hash prints "Requirement already satisfied"
  and exits 0. After the main lock, which resolves `mcp`'s `pywin32>=310` to 312 unpinned, the
  Windows lock's hash would never be checked while 312 is the newest release; installed first,
  the hash is checked and the main lock keeps 312. Alternative: after, as briefed (or after with
  `--force-reinstall`). Reversible by: reverting the D-30 commit (moves the step back).
  Confirmed in run 44703554833 (head b04d7764): "Successfully installed pywin32-312", then the
  main lock "Requirement already satisfied: pywin32>=310"; G19 step green on windows-latest.
- D-31. DECISION (WO6): on Windows `test_the_installed_closure_is_the_recorded_one` compares
  licence files with CRLF read as LF. Measured (run 44703554833, then the wheels from `pip
  download --platform win_amd64 --python-version 3.13`): pydantic-core 2.46.5 and rpds-py
  2026.6.3 ship `licenses/LICENSE` with CRLF (`fbe7f615...`, `8bcb72c8...`); LF-normalised they
  are the record's `2afdd30d...` and `314e4e91...`; cffi and cryptography are byte-equal. The
  normalising helper reproduces all 29 recorded rows on Linux. The G19 record and the script are
  unchanged. Alternative: a Windows licence record, or CRLF normalisation in the script's hash.
  Reversible by: reverting the D-31 commit.

## Windows classification (run 44670029066, head 9773c361: 116 failed, 179 errors)

Fixed: 179 errors WinError 123 (`T05b:DZ-3.rerun`, W3a's rerun directory, a99c510f). F0 PASS on
Windows (M7 52/52 by R1.4). Marked off-platform by WO3/WO4 rows (L1, L2, L6 to L10): g1a, A85b,
B34a, TH-C1 golden. Clusters left, by class (WO2's rules; none yet fixed or rowed):

- path separators in recorded strings: `test_s05_envelope` a26, `test_x05_lock` a20,
  `test_t06_w30_holdout` a99a, `test_t06_w29_runs` (2), `test_rel_ci_release_rc`,
  `test_pre_push_guard`, `test_msg_corpus` C04/C05, `test_m07_journey` a00, `test_s11_w27_v3` a32,
  `test_t08_w4_v0_1_gate`, and probably the "a fixture exists that nothing regenerates" family
  (`test_k03/k04/k05/t04_schemas`, `test_t07_w5e`, `test_t08_rename_substitution`, `test_t07_w5b_cli`);
  `test_c9_w27_v2` committed-relative (`path is on mount 'D:'`): portability bugs, to fix.
- CRLF written by a generator or compared as text: `test_f1_discovery`, `test_s03/s09_references`,
  `test_m07_journey_record` a21 (4), `test_t06_w31_runs` (6), `test_m02_pymrm_child` (2),
  `test_t07_evidence_manifest`, `test_c2_openidaes450_split`: portability bugs (newline="\n").
- WinError 32: `test_s16_test_impact` (3); signal 2: `test_m02_pymrm_child` SIGINT,
  `test_t07_conformance` serve: WO2's classes (likely limits: no SIGINT delivery to a child on
  Windows).
- experiment child `environment_unavailable`: `test_m02_experiments` (19), `test_m02_wo10_coupled`
  (8), `test_x02_wo4_external` (10): one root cause, not diagnosed.
- M05 host keys: `test_m05_retake_digest_only` (10); V17 reference: `test_t07_s3_validation`;
  Q-1: `test_t07_server_extra` (pywin32); P3 sets on Windows (not macOS's): TH-C1 companion (b),
  `test_m03_schemas`; others unread: `test_opt_cost_lca` hand model, `test_m03_reference` a42,
  `test_m04_reference_values` a34, `test_m06_wo4_serving`, `test_m07a_v0_2_gate` a07,
  `test_t08_w1_ledger`, `test_t07_interrupt` no_broad_except, `test_s16` runtime_open_record,
  `test_p03` s9_5 and `test_v02a_r347` (both fixed or rowed by WO4 for every non-Linux leg).

### Windows clusters after WO5 (from run 44670029066's 116 failed; 44683830734's Windows leg was still running)

Fixed (portability, Linux bytes unchanged, F0 PASS 9/9): M05 retake (10, test LF), path keys and
link targets in tests (k03, k04, k05, t04, t06 w29 (2), w30 a99a, t07 w5e, t08 rename schema, x05
a20, s05 a26, v0_1 gate chmod), t06 w31 (6, `t06_ensemble` starts_file), release_rc a items,
f1 discovery (registry_builtin LF), pymrm child (2 CRLF stderr, 1 venv path): about 35 nodes.
Rowed (Windows limits): the experiment child (37, ADR 0033 D2), w5b/t08-rename CLI transcripts (3),
M07 record paths (6, D-28), pymrm SIGINT (1). Left, unread or not fixed: `test_s16_test_impact`
(4, WinError 32), `test_t07_conformance` serve (signal 2), `test_c9_w27_v2` (2: committed-relative
across mounts, generator check), `test_s11_w27_v3` a32 generator check, `test_msg_corpus` C04/C05
(`<tmp>\plant` ids), `test_pre_push_guard` (native hook path), `test_s03/s09_references`
(recompute), `test_t07_evidence_manifest` (V17 files differ), `test_c2_openidaes450_split`,
`test_t07_server_extra` (the Windows closure has pywin32, the record does not: a Windows record or
a scoped comparison, with Q-12), `test_s07_packaging` (its A41 subprocess of the same),
`test_t07_s3_validation`, `test_opt_cost_lca`, `test_m03_reference` a42, `test_m04_reference_values`
a34, `test_m06_wo4_serving`, `test_m07a_v0_2_gate` a07, `test_t08_w1_ledger`, `test_t07_interrupt`,
`test_v02a_r347`, and the P3 sets on Windows (`test_st_cli` TH-C1 (b), `test_m03_schemas`).

## Position (handoff, WO6, 2026-11-20)

Part 1 (card ofs-x07a-pywin32-lock A, R-1063 amended, Q-12 closed): 071815c7 `requirements-windows.lock`
(sha256 `71f30fa7...4bff`; `pywin32==312`, cp313 win_amd64 wheel `c53e878d...aaf9`, PyPI agrees); b04d7764
installs it before the main lock (D-30). `requirements.lock` unchanged, `ead4edf1...b9c4`. Run 44703554833:
the Windows lock step installed pywin32 312 by hash and G19 passed on windows-latest;
`test_the_installed_closure_is_the_recorded_one` then failed only on two CRLF licence files (D-31, ad9be51c).

Part 2 commits (each X07a): msg_corpus, pre_push_guard, w27 v3 generator, c9 a22 drive, c2 a25c, t07
campaign_sums, t07 interrupt and s3_7, test_impact and s16 sqlite close, s09 generator, m03 a42, m07a a07
mode, v0_0_gate, serve-http and m06 serve check (Ctrl+Break), t08_rc console, t06 w28, m05 retake cache dir;
limits rowed: S03 a10, c9 v2 generator check, S16 B-18, the v0_1 gate chmod case (conftest
`FROZEN_WINDOWS_LIMITS`). ebe513d9 restores `tests/test_t08_w4_v0_1_gate.py` to its registered bytes:
WO5's 2bb2c157 had broken M07a.A13 (red on all four legs of 44699040945: a13, rel a20, t08 generators).

Windows counts: 44699040945 (58bdd149) 39 failed, 0 errors; 44703554833 (b04d7764) 38 failed, 0 errors;
the linux and macOS legs of both: the same 3 (A13 family), fixed by ebe513d9. Local: touched tests pass;
F0 PASS 9/9; `codehealth arch --depth 4` 0 cycles, 0 violations.

Left on Windows after the last push (expected, unverified until its run ends): floating point, design lane
(P3 sets): `test_st_cli` TH-C1 json (b) and `test_output_writes_the_file_and_prints_nothing` (a CSV digit),
`test_opt_cost_lca` hand model (sizes 1.75e-12 against 1e-13), `test_m04_reference_values` a34 (reference
JSON differs; the generator renders no paths; not diagnosed), `test_m04_quadratic` a49 (in 44699040945 only),
`test_m03_schemas` fixtures. To confirm: Ctrl+Break serve (t07 conformance, m06 serving) and the m05 retake
fix. Next: read the Windows leg of the run for the final head (`gh api .../jobs/<id>/logs` to a file, grep
`Z (FAILED|ERROR) tests/`). Open for the reviewer: D-20, D-22, D-28 to D-31, Q-4, Q-10, Q-11, D-24's companion.
Push from this worktree: `git -c credential.helper='!gh auth git-credential' push origin wp/X07a`.

## WO8 (2026-11-20, CI 44736771069 at da4c03b0: Windows 7 failed, 4 of them P3 rows for the design lane)

- `test_smoke_serve_http_on_a_loopback_port` (exit 3 after a clean shutdown): uvicorn 0.54 restores the
  handlers it found and re-raises the captured signal. SIGINT's handler raises `KeyboardInterrupt`, which
  `uvicorn.run` swallows (POSIX exit 0); SIGBREAK's is the C runtime default, exit 3. 43520d8e: `http.run`
  handles SIGBREAK with `signal.default_int_handler` for uvicorn's span (Windows, main thread; inert
  elsewhere); `web.serve` (m06) goes through the same `run`. The m06 serve check ignores the exit code, so
  it was green already. POSIX analogue measured: SIGTERM re-raised gives -15 bare, 0 wrapped.
- `test_the_installed_hook_guards_git_push` (push exit 0): the hook ran (python3 resolved; the archive push
  went through it), but git hands it the remote as given, `C:\...\computational-chemical-engineering\
  openflowsheet.git`, and `REPOSITORY` matches `/` only, so `guarded()` was False. 13e0e6a6: `guarded()`
  reads `\` as `/`; two cases added (a Windows public path, guarded; the archive's, not). A real guard bug,
  not a test artefact.
- `test_rel_a20_over_0_3_0s_committed_records` (`RP.S03 same form: fail`): not floating point. RP.S03's D
  selection runs `tests/test_m07a_v0_2_gate.py`; on Windows its a07 is skipped by `FROZEN_WINDOWS_LIMITS`
  (da4c03b0, log line 1876 of the run), and S13a's rule (`s13_evidence_manifest._pytest_part`: exit 0, one
  passed, **none skipped**) makes the selection `fail`, so it differs from S13's Linux `pass`. Every repair
  is out of bounds (STOPPED, Q-13 below).
- Q-13 (open, design lane): REL.A20 on Windows while the a07 limit stands. (A) a P3c-style registered
  difference: on win32 the test expects RP.S03 exactly `fail; S13 V03.A03 pass: DIFFERS` and every other
  same-form key `equal` (an assertion edit; keeps the other 11 checks and RP.S18's sub-check judged on
  Windows; fails when a07's limit lifts). (B) row the whole node in `FROZEN_WINDOWS_LIMITS` (loses REL.A20 on
  Windows). Rejected: S13a's rule admitting a registered skip (a relaxed check); the a07 index-staging fix
  (M07.A31(b) holds the file). Engineer's preference: A.
- Left: Q-13; the four P3 rows (TH-C1 json (b), `test_opt_cost_lca`, m04 a34, m04 a49).
