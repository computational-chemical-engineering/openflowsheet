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
  `-rs`), so a leg's failures are read by grep. Output only. Reversible by: the env line.
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

## Design-lane questions (left failing, not chosen)

- Q-1 (G19 on Windows, run 44615939688): `t07_licence_inventory.py` FAILED, 30 distributions:
  `pywin32 312: PSF (compiled) not-allowed`. pywin32 is `mcp==1.30.0`'s Windows-only requirement;
  it is not in `requirements.lock` (frozen on Linux), so on Windows it is also unpinned. Needed: a
  licence ruling on pywin32 (PSF-2.0 family, compiled) and a decision on a per-platform lock entry.
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

Rows found by the CI legs are added below with their run id.

## Position (handoff, context cap reached 2026-11-19)

Commits on `wp/X07a`: e897af52 layer, 05886465 win32 type check, 4fb8a63d CI, 8ff95818 UTF-8 /
G19 / m05 literal, a5f53590 Windows collection, d2fb0252 envelope axis, then docs and manifest.

Local (Linux x86-64): the 104 test files importing the changed modules (grep for
`application.store`, `experiments.store`, `jobs.executor`, `jobs.worker`, `_files`, `surrogate.blas`,
`g11_coverage`, `v17.harness`, `external.launcher`, excluding nlp) plus `tests/test_x07a_platform.py`:
4409 passed, 26 skipped, 3 xfailed at 4fb8a63d; later changes' tests run separately (all pass).
F0 PASS (reference platform); arch 0 cycles 0 violations; touched-file health unchanged, new
`_platform.py` 9.5; `codehealth diff` debt 55.30 -> 58.30 (the new module; informational).

CI: run 44615939688 (4fb8a63d): ubuntu-latest 1 failed (A20, fixed d2fb0252), ubuntu-arm unknown,
windows G19 + UTF-8 (fixed 8ff95818), macOS m05 literal (fixed) and F0 M7 (Q-2).
Run 44617827438 (8ff95818): windows 2 collection errors (fixed a5f53590). Run 44618922484
(a5f53590) and run 44629325836 (d2fb0252) were in progress at the cap.

Next: read run 44629325836. Expected: ubuntu legs green; windows red on G19 (Q-1) and F0 M7
(Q-2) plus any pytest failures not yet seen (first full Windows suite); macOS red on F0 M7 (Q-2).
Classify each new Windows/macOS test failure as portability bug (fix) or platform limit (row
above, with run id). Manifest `evidence/X07a/d2fb0252.../manifest.json` stays `implemented`.
