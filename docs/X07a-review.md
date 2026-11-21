# X07a review (design lane, `reviewer`): Windows and macOS CI legs, at db051d9c

Scope: `git diff c4a91a75..db051d9c`, the ruling `docs/X07a-platform-ruling.md`, ADR 0007 Amendment 3 (D-27),
`docs/X07a_DECISIONS.md` (WO5 to WO8 whole), the Windows log of CI 44736771069 (da4c03b0). CI 44764813337 was not read.
Nothing was built or run for this review.

**Verdict: not ready for the merge card.** The replay and platform layer is sound. Two of the four Windows rows the
handoff calls floating point are defects of another class (R-1, R-2), and four bounded build-lane items are owed (R-3
to R-6). None of the design questions blocks the merge (R-7 to R-9).

## Findings

**R-1 (must fix; defect, not an R2 row): `test_m04_quadratic.py::test_a49` fails because the BLAS pin does nothing off
Linux.** `studies/surrogate/blas.py:40,52-61` finds the loaded OpenBLAS only through `/proc/self/maps`. On Windows
`controlled()` is empty, so `single_blas_thread` is a no-op. NumPy's and SciPy's `scipy_openblas` DLLs still honour
`OPENBLAS_NUM_THREADS`, so `pinned_1 != pinned_8` (log line 2057; coefficient 2: `0x1.fd590a544e981p-10` against
`...987p-10`). The run-to-run intermittency in the WO6 Position ("in 44699040945 only") is a49's vacuous-skip branch:
when OpenBLAS does not split the work at that size on a given runner, the inert pin goes unnoticed.
- In scope: M04 spec A3.3 (`docs/derivations/M04-spec.md:1414-1420`, R-362) is a per-platform rule ("whatever the
  process's setting"; A32: "bitwise on one platform"). R2 governs comparisons across platforms, and a49 compares two
  runs on one host. `blas.py:15-17` ("a platform without `/proc` ... A1.3's platform classes govern") misreads A3.3,
  because A1.3 governs comparisons across platforms, not across thread settings on one platform.
- Measure on the Windows leg: `len(blas.controlled())` inside the a49 child (expected 0), and `pinned_n ==
  unpinned_n` for n = 1 and 8 (expected true).
- Fix (build lane on Opus, with a design-lane review because it touches determinism): enumerate the loaded modules
  on win32 (`K32EnumProcessModules` and `GetModuleFileNameW` through ctypes) and on darwin (`_dyld_image_count` and
  `_dyld_get_image_name`). Keep the symbol probe. Add no dependency, since `requirements.lock` is frozen. Correct the
  `blas.py` docstring and `_platform.py:57-60` ("no caller reaches it there"). `greybox.py`'s OpenMP probe uses the
  same `/proc` pattern: check it. Acceptance: a49 passes on Windows with `controlled()` non-empty (logged), and Linux
  stays unchanged (`d65bb022...`).
- **Needs a decision.** The alternative is a P4 limit row stating that A3.3 is unmet on Windows and macOS. That
  narrows a registered rule. I would fix it.

**R-2 (must fix; P4 path, not floating point): `test_m04_reference_values.py::test_a34`.**
`docs/derivations/scripts/m04_reference.py:1771-1773` writes `str(V3_VARIANT)`, `str(LOOP_RECORD)` and
`str(LOOP_EDGES)` as the keys of `amendment2.sources`. On Windows these keys contain backslashes, so the bytes of
`reference_values.json` differ while all 11943 claims pass (log 2214). The handoff's "the generator renders no paths"
is not so. D-29 applies: fix with `.as_posix()`. Linux bytes are unchanged, and the generator is not hash-pinned
(no SHA of it in the repository).
- A second failure is hidden behind the first. `test_m04_reference_values.py:40` expects `benchmarks/m04/...`, but
  the generator prints `{path}` natively (`benchmarks\m04\plan-it1.json` in the log). Use the native regex of
  6e7934ec (m03 a42).
- If `reference_values.json` still differs after the fix, print a unified diff on the leg before calling any float
  a platform difference.

**R-3 (should fix before the merge): TH-C1 companion (b) on Windows is a P3c row.** The Windows set is exactly the
macOS set (log 1184-1215: `certificate_id`, `energy.overall.closure`, `energy.units[0].closure`). Register
`("AMD64", "Windows")` under X07a-L5 in `tests/conftest.py:50`, with the P3a numbers (closure 6.18e-10, run
44736771069). Extend row L5 to both platforms. Build lane.

**R-4 (should fix before the merge): `test_opt_cost_lca.py::test_the_hand_model_reproduces_p1` is a P2 row with a P3
companion.**
- What the test compares: the host's fresh TH-C1 solve (`benchmarks/opt/cost_lca.py:273-298`), carried through
  `sizes`, against `P_SIZES`, which was recorded on Linux (`benchmarks/e01/cost_hand/cost_hand.py:764`; its
  `state_sha256` `a23b2407...` is the same state whose digest is TH-C1's `certificate_id`).
- The bound is 1e-13 (`tests/test_opt_cost_lca.py:92`), four decades below the policy's 1e-9. It is a
  rounding-level claim about Linux's bits. The root is the same as in R-3.
- Form: `bitwise_baseline(row="X07a-L11")` on the node. Add a companion on every leg: the same `p1_check` at
  T08-numerical-policy-v2's 1e-9 relative (ADR 0007 D2.1). Windows' 1.75e-12 passes it. Never widen 1e-13.
- This extends P2's list ("a bound below the policy, on floats recorded on another platform"). It is recorded here as
  the reviewer's reading. Build lane.

**R-5 (Q-13): option A, with one condition.** On win32, the expected `RP.S03 fail; S13 pass: DIFFERS` holds only
while `test_m07a_v0_2_gate.py::test_a07...` is a key of `conftest.FROZEN_WINDOWS_LIMITS`. Derive the expectation from
that key, and give it a row id that `test_x07a_platform_rows.py` checks, so that lifting the limit fails the test.
S13a's rule (`scripts/s13_evidence_manifest.py:323-326`, none skipped) stays as it is. Option B is rejected: it loses
REL.A20's other 11 checks on Windows. Build lane.

**R-6 (should fix before the merge; D-24's companion is owed).** A85b's products style (`tests/test_t06_w6_a85.py:168-172`,
and w30's equivalent) is Python `sum` over committed floats in a fixed order. That is platform-independent, and P2
requires such a step to run on every platform. Split it into an unmarked node. Build lane.

**R-7 (Q-10): both paths are departures; fix them after the merge.** Row L5 stands for 0.5.
- `certificate_id` is a digest of the state's floats (ADR 0008 D2.1). `run/compare.py:383` already compares a
  digest-derived id for shape, but only when the document carries `target_state_sha256` (`_digest_derived_id`), and
  the stream-table document does not.
- The near-zero closures have "no registered floor" (`compare.py:945`). Adding one is D2.3's ordinary change "with
  its threshold's provenance" (ADR 0007, line 244). The specifier names the threshold (the energy-balance check's
  tolerance).
- Both changes alter `run.compare` on every platform and need a mutation case each: design lane (`specifier`).

**R-8 (Q-4): the row stands for 0.5.**
- The margin and `inverse_one_norm_estimate` both move by 2.28e-9 relative. That is consistent with the inverse norm
  scaling as 1/margin near the phase boundary: one ill-conditioned state, seen three times.
- `inverse_one_norm_estimate` is an estimator diagnostic (P3b's "pivot-path diagnostic" kind).
  `solution_error_bound_scaled` is that estimate times a residual below its tolerance, which D2.2 (m03 rule 2) says
  is not a measurement. Both are departures, and their floors should be propagated (the precedent of m03 rule 4).
- The margin still needs the ruling's measurement (|operand| / |margin| at outcome 8, split 1). The default (no floor)
  holds until then.
- Design lane: one isolated comparator commit after the merge, with mutation cases.

**R-9 (Q-11): accept P2 as provisional.** The outcome counts are images of floats at decision boundaries, compared by
`==` against counts recorded on Linux. Before the row is lifted, measure on macOS which two regions move and their
decisive margins. If both margins lie at policy-noise distance from the boundary, P2 holds; otherwise it is a defect.
The robustness question (which outcome a region near the boundary should take) belongs to T05b's backlog, not to
X07a.

**R-10 (D-20): accept, and correct the ruling.** The ruling says "exactly one" reason (`docs/X07a-platform-ruling.md:139`,
`:181`). The code emits the `running on` reason followed by `no rerun was supplied`. The judged answer is exact: a
third reason, a missing note or a lock reason each fail (the mutation cases in `tests/test_f0_corpus_identity.py`).
Add a one-line erratum to R1.4 and P1c so that the governing text matches the judged answer. Design lane, docs only.

**R-11 (the build decisions).**
- D-21 and D-22: accept. P3c requires the measured set, so registering all five paths is right.
- D-28: accept. It protects the carry identity, and each row names what lifts it.
- D-29: accept. It was applied where a failure showed it was needed; R-2 is the one live miss. Latent cases:
  - `run/bundle.py:136` builds the set of present artifacts with native paths, so a nested artifact name would read
    as unexpected on Windows. No nested name exists in the corpus or in `src` (note).
  - The evidence-manifest scripts run on Linux only.
- D-30: accept. The order is measured, pinned by `test_ci_installs_the_windows_lock_on_the_windows_leg_only`, and the
  closure test asserts pywin32's version on Windows. `requirements.lock` is unchanged in the diff. Note:
  `requirements-windows.lock` is outside `lock_sha256` (R-140), so a same-host exact replay across a pywin32 change
  goes unseen. That is inert for numerics.
- D-31: accept. Note: `_lf_licence_files` (`tests/test_t07_server_extra.py:197`) runs only on win32. Add a Linux
  assertion that it reproduces the recorded rows, so the Windows branch cannot drift from the script's hashing.

**R-12 (Q1, the package diff): sound.**
- `decide_mode` (`run/replay.py:111-112`, `_alike_and_pinned`) is R1.2 exactly. The lock rungs come first, and every
  outcome between registered platforms is unchanged (A2: 82 880 of 82 944 pairs identical; the 64 others are equal
  unregistered pairs).
- F0 M7 judges R1.4 exactly, with mutation cases.
- The P1c, P2 and P3c helpers are correct.
- No relaxed check, removed case or narrowed denominator was found. Every rewritten assertion keeps its Linux
  expectation, and the CI-matrix guard is stricter, with a case showing it is not vacuous. No released record was
  edited; the two frozen test files were restored (ebe513d9, da4c03b0).
- Note on R1.5: the tests replace two fields of the host's environment (`test_k05_replay.py:177,593,798,819`). That
  meets the rule's purpose, not its letter.
- Note on the Windows store lock (`_platform.py:85-90`, `msvcrt.locking`): the system releases a dead process's lock
  with a delay, so `recover` may skip a just-dead owner once. This affects liveness only.

## Merge preconditions, in order

1. WO9 (build lane, Opus): R-1 (or Frank's decision on the row), R-2, R-3, R-4, R-5 (option A) and R-6, each as an
   isolated commit. Run the touched tests locally, and F0 must PASS.
2. CI at the WO9 head: all four legs green (Windows: 0 failed), and the identity and codehealth jobs green. That run
   also confirms WO8's two fixes.
3. Move the manifest to that head with status `tested`. Its limitations name the open rows (L1 to L11), Q-4, Q-10
   and Q-11 as post-merge design-lane items, and the outcome of R-1.
4. The R-10 erratum is committed. The build lane does not set `reviewed`.
5. Only then the merge card. Amendment 3 is already accepted (D-27). After the merge, run
   `scripts/corpus_identity.py --check` on `main`.

Not examined: the Job Object path under a nested job (read only), the 37 `NEEDS_EXTERNAL_CHILD` nodes one by one, the
docs-site and support-envelope wording, any macOS log, and CI 44764813337.

## WO9 review (design lane, `reviewer`, at 335c09bf)

Scope: `git diff 2f067059..335c09bf` (4f964722 to 90d53af2) and the WO9 entry of `docs/X07a_DECISIONS.md`. Run on
Linux x86-64 (repo venv): the eight touched test files, 207 passed, none skipped (a49 passed, not skipped; a34 found
the generator byte-identical to the committed files). CI 44770741082 was not read.

**Verdict: R-1 is correct, and unchanged in effect on Linux. R-2 to R-6 match their findings. Ready for the merge card
once W-1 is in and CI is green on all four legs; W-2 and W-3 are decisions that may be taken at the card.**

1. **W-1 (should fix before the card; build lane, test only).** `tests/test_m04_quadratic.py:458` asserts that the pin
   controls *some* OpenBLAS, not *every* one. The fit uses both: NumPy's (`np.linalg.svd`, `qr`,
   `quadratic.py:190,194`) and SciPy's (`solve_triangular`, line 32). `blas._library` (`blas.py:61-62,71`) silently
   drops a library that fails to open or exports no symbol pair. If it drops one of the two on a leg, the condition
   still holds. On a runner where that library does not split the work at this size, the bitwise asserts miss it too,
   which is R-1's vacuity again. Fix: the child also reports `[os.path.basename(p) for p in blas._loaded_openblas()]`,
   and the test asserts it equals `controlled`. Keep the existing non-empty condition.
2. **W-2 (needs a decision; I would take (a)).** On an Accelerate leg the pin rightly controls nothing. But
   `_a49_child` varies only `OMP_NUM_THREADS` and `OPENBLAS_NUM_THREADS` (line 425), which Accelerate ignores, so the
   skip at line 469 is certain, A3.3 is never exercised there, and the skip text blames the CPU count. (a) Set
   `VECLIB_MAXIMUM_THREADS` with the other two and name the BLAS in the skip reason. If the unpinned fits then differ
   at 1 and 8, pinned fails: that is a real A3.3 finding for a P4 row, not a WO9 defect. (b) Keep the skip and state in
   the manifest's limitations that A3.3 is not exercised on macOS. Either way, `blas.py:16-18` ("OpenBLAS's thread
   variables then do not reach the fit") says nothing about Accelerate's own thread count. Amend it to match the
   choice.
3. **W-3 (should fix; needs a decision; I would refuse).** The failure paths differ. On Linux, `_platform.py:262-263`
   returns `[]` when `/proc/self/maps` cannot be read, so a production fit runs unpinned with no trace (the old
   behaviour). Windows raises `WinError`, and macOS raises on a missing `_dyld_*` symbol. Let the `OSError` propagate
   (`blas` is the only caller), so that every route refuses. Only an error path changes: a job on a Linux host without
   `/proc` now fails instead of running unpinned.
4. **Linux identity (sound).** `loaded_libraries` collects the same `fields[5].strip()` set. Filtering on the basename
   of the stripped path selects the same strings, because stripping removes only trailing whitespace, which cannot
   take part in a match of "openblas". The sorted order is the same, and `_library` and `single_blas_thread` are
   untouched. So the same libraries get the same `get`/`set` calls in the same order. The WO-11 evidence for d65bb022
   stands without a re-submit.
5. **Windows and macOS routes (sound as read; unverified until the legs' logs).** `cb` and `needed` are in bytes; the
   grow-and-retry loop and the slice `needed // sizeof(HMODULE)` are right; `GetModuleFileNameW`'s size is in
   characters (32768), and a 0 return is skipped. On win32 `ctypes.CDLL` ignores `mode` (`winmode` governs), and
   `LoadLibraryExW` on a loaded module's full path returns that module's handle. `CDLL(None)` reaches `_dyld_*`
   through libSystem, and NULL names are skipped. Test (f) checks discovery on every leg against NumPy's own
   extension module, which is a real check. Note: on Linux the list also holds pseudo-entries (`[heap]`, `[vdso]`),
   which the docstring calls file names. This is harmless.
6. **R-2 to R-6 (match).** R-2: the keys are relative `Path`s, so `.as_posix()` writes Linux's bytes. The test's native
   regex follows m03 a42. `reference_values.json` is untouched, sha256 d0a23a01. R-3: `("AMD64", "Windows")` carries
   the same three paths under L5. R-4: 1e-13 is kept, and the companion is at `V2_RELATIVE_TOLERANCE`, asserted to be
   1e-9. R-5: the expectation is derived from the a07 key, and the rows test fails when the limit is lifted; the
   other same-form keys on Windows stay unverified until CI, as WO9 states. R-6: the products style moved to an
   unmarked node, with `_same` unchanged and no case removed. Nothing widened, removed or re-registered.
7. **Merge card.** CI at the WO9 head must show, on Windows, a49 passing with `blas_controlled` naming both DLLs,
   and on macOS what `openblas_builds` says. Record both junit properties in the manifest.

Not examined: any CI log, Windows or macOS execution, `greybox`'s probes beyond the top-level `import cyipopt`
(line 60), and the win32 branch of R-5 beyond reading it.
