# S09 build decisions

Build-lane choices made while executing `docs/derivations/S09-spec.md` §12. Each is an isolated, revertible commit.
Scientific questions are not decided here.

## WO-S09-1 (environment)

- MEASURED: the spec's lock command resolves `biosteam==2.54.0` to 63 distributions; every version of §2.1 matches
  (thermosteam 0.54.2, thermo 0.6.1, chemicals 1.5.2, flexsolve 0.5.10, numba 0.68.0, numpy 2.5.4, scipy 1.18.1,
  CoolProp 8.0.0). The `aarch64-manylinux_2_28` resolution gives the same 63 pins.
- MEASURED: five distributions are sdists (biosteam, thermosteam, flexsolve, colorpalette, numpoly), not two as the spec
  says. Four are pure Python. **numpoly 1.3.9 has no wheel and compiles Cython/C code** (build-system requires
  setuptools, wheel, Cython, numpy); the spec calls them pure-Python wheels. With the default isolated build the install
  works, but its build tools are not hash-checked.
- DECISION: take the spec's fallback route, extended to numpoly's needs → pin `setuptools`, `wheel`, `cython` in the lock
  (added unpinned to the `.in`, so they resolve to the latest: setuptools 84.2.1, wheel 0.48.0, cython 3.3.0), hash-install
  those and numpy first, then the whole lock with `--no-build-isolation`. Alternative: leave isolated builds (unhashed
  build tools). Reversible by: dropping the three lines from the `.in`, recompiling the lock, and the two-phase install in
  `build_biosteam`.
- DECISION: the pip-freeze fingerprint now includes cython and wheel (they are in the environment). It does not cover the
  compiled bytes of numpoly's extension, which depend on the host gcc. Alternative: add a hash of numpoly's `.so` files
  to the fingerprint. Reversible by: editing `fingerprint()`. Open for the design lane: whether the spec wants that.
- DECISION: `--no-cache-dir` on both installs, so nothing comes from a local pip cache. Alternative: the pip cache as
  for IDAES. Reversible by: removing the flag.
- DECISION: the build-tool subset is cut from the lock at build time by awk, not kept as a second file. Alternative: a
  committed `biosteam-build-tools.lock`. Reversible by: swapping the awk step for `-r` that file.
- DECISION: `uv` 0.12.12 was already installed (`~/.local/bin/uv`); nothing installed.
- DECISION: `.venv-biosteam` is covered by the existing `.venv-*/` pattern of `.gitignore` (`git check-ignore` confirms).
- MEASURED: two consecutive builds, 38 s and 36 s, give the same pip-freeze SHA-256
  `0edea300bbf188030642265ca811425c270d5508bf119fa86431572c06c69a95`; `pip check` passes; the environment imports
  biosteam 2.54.0 (no column was run). Size 874 MB.
- DECISION: A04's file part is `tests/test_s09_environment.py`: lock pins every distribution by hash and holds §2.1's
  versions, `.in` matches the lock header, §9 carries one fingerprint twice and the licence and aarch64 statements, the
  script builds with `--require-hashes`. The record-fingerprint half of A04 waits for WO-S09-2's records. Alternative:
  rebuilding in the test (rejected: the gate never builds external tools). Reversible by: deleting the file.

## WO-S09-2 (blind qualification)

Fresh build-lane agent, brief `docs/briefs/S09-wo2-qualification.md`. Files opened: the spec, `s09_cases.json`,
`s03_cases.json`, `s09_design/`, the S03 harnesses (structure only), BioSTEAM's source, and the lines of
`t06_fixtures.py` named below. Nothing under `s09_spike/`, `benchmarks/s03/references/results/`, `benchmarks/s09/`,
`s03_reference.json` or S03's `comparison.json` was opened.

- DECISION: `t06_fixtures.py` is not on the brief's read list, but spec §4.2 and §2.3 step 2 require importing its
  SYN-001 constants (A03 exempts it by SHA-256). Only its top-level names, the seven constants, `component_balance`,
  `pip_freeze_sha256` and `finite` were read (SHA-256 matches the pin). Alternative: stop and ask. Reversible by: n/a.
- DECISION: `s03_cases.json` is read at `docs/derivations/scripts/` (spec §2.3, A03's input files); the brief's
  `benchmarks/s03/` location does not exist.
- DECISION: S03 §6's allowances (T 1e-5 K, flow 3.1e-7 mol/s, duty 1e-2 W, relative 1e-6) and S03's rule 2c and §17.4
  thresholds are taken from `s03_qualify_dwsim.py`'s constants (S03-spec.md is not on the read list). They enter only
  the rerun movement and the path spread. Alternative: read S03 §6. Reversible by: editing `ALLOWANCE`.
- DECISION: rule 1's fingerprint is computed by the harness (`fx.pip_freeze_sha256`, the build script's algorithm)
  against §9's SHA-256 written into the harness: `fx.fingerprint` has no BioSTEAM branch and `t06_fixtures.py` is
  pinned; `docs/reference-environments.md` is not an A03 input file. Reversible by: editing
  `EXPECTED_PIP_FREEZE_SHA256`.
- DECISION: the accuracy rerun is run for every rung that passes rules 2, 2c and 2d's specification residual, not only
  the eventual selection, because "first rung passing rules 2-2d" includes the rerun. Alternative: rerun only the
  first such rung. Reversible by: one condition in `attempt`.
- DECISION: path dependence (§6.4) evaluates the tolerance at the earlier rung's tool value (§5.3 order), maximum over
  all pairs. Alternative: the selected rung's value. Reversible by: `path_dependence`.
- DECISION: the L2(c) inspection (§2.4) is read from a model built at x = 1 under R1's settings, not solved.
- DECISION: an exception in pass 1 does not stop the path: P3 and P4 still run and are recorded (A07: every run shows
  both passes); B1 fails. Alternative: stop after pass 1. Reversible by: `solve`.
- DECISION: a ratio with a zero denominator (an empty stream) is NaN, so the check that reads it fails as non-finite.
  The first development run crashed the harness on R3's empty-stream states (`ZeroDivisionError`, RC2 family): a
  harness defect, corrected before any recorded run.
- DECISION: thread counts fixed to 1 (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`) in
  `s09_qualify.sh`; six case processes at a time (`JOBS`). Alternative: library defaults, sequential. Reversible by:
  the two lines in the script.
- DECISION: `s09_qualify.sh` takes OUT and REPEAT as arguments: A03 forbids the path `benchmarks/s09/` in the scanned
  set. The second run is written outside the repository and is not committed; the repeat block carries both runs'
  record hashes.
- DECISION: A17 compares each record of run 2 with run 1 after removing every `wall_time*` key (the only wall-clock
  fields), byte for byte on the canonical JSON.
- DECISION: recorded but used by no rule: the tool's `_mean_residual` and, for R3, fsolve's `nfev`, `ier`, `mesg`
  (§6.1: the tool's report is not used).
- DECISION: A03's "qualification commit" is the last commit touching `qualification/biosteam.json`; the assembler also
  records `harness.head` and whether the scripts were clean there. Both are scanned with `git show`.
- DECISION: the tool-free tests are `tests/test_s09_qualification.py` (A03 self-scan, A06, A07, A08). A06-A08 skip,
  with that reason, until the records are committed. Reversible by: deleting the file.
- MEASURED (STOP, rule 6): §4.3's `thermo_classes` item registers `PCF = MockPoyntingCorrectionFactors`
  (`s09_reference.py:523`, spec §4.3 row 7). thermosteam 0.54.2's class is spelled `MockPoyintingCorrectionFactors`
  (`thermosteam/equilibrium/poyinting_correction_factors.py:51`); no class of the registered spelling exists. The exact
  check therefore fires rule 2c `property_mapping(thermo_classes)` on every case. The recorded run is not made until the
  design lane rules (proposed: an erratum to the registered string; no other change).
- MEASURED: `s09_cases.json -> pairs` holds 19 pairs (17 S03 cases, PC-P, PC-LB); spec §3 and §12 say 20.
- MEASURED: B2 reads `iter`, which R3 (`simultaneous correction`, fsolve) never increments (`stage.py:3014-3061`):
  B2 is vacuous on R3. B3/B4 still guard it; fsolve's `nfev` is recorded.
- MEASURED: with two specifications the stored B after pass 1 is not exactly the constructor's (RC1: 0.49999999999999833
  for Reflux 2, 1.4999999999999816 for Boilup 1.5); P3 re-stores it and the read-back after pass 2 is exact.
- MEASURED (development runs, disclosed; outputs in the scratchpad, not committed): dev0 = RC1 as registered (every rung
  fails rule 2c `property_readback`, only `thermo_classes`). dev1 = all 19 pairs with the PCF string replaced in memory
  by the tool's spelling (a scratch wrapper; the harness unchanged). Results: every case available at §2.5's expected
  level (RC1/RC2/RC3 families, PC-P, PC-LB at L1; RC4 family, RC5, RC6, RC7 at L2(c)), every Q-X4/Q-X5/Q-X8
  realization as §2.5 states. Selected R1, except R2 for the RC3 and RC4 families (R1 fails B3 there). R3 fails rule 2
  on every case (B4, or B1 with the negative-temperature extrapolation). Floors over the 51 passing rungs: B3 3.3e-11
  mol/s (rerun 3.9e-10), B4 2.1e-11 (1.9e-10), adiabatic duty 1.2e-6 W (6.7e-6), B5 energy 1.8e-11 W; rerun movement
  ≤ 0.038 tolerance; path spread ≤ 1.2e-3 tolerance; outer |g|/ytol ≤ 4.4e-3. No floor is near a threshold
  (Q-S09-5). Thin margin (§6.6, ratio > 0.1): RC6 0.263 and RC7 0.197, both the rerun movement at L2(c), where the
  rerun's ytol equals rule 2d's threshold (C4 allows up to 0.05 tolerance there, i.e. ratio 0.5).
- MEASURED (development, disclosed): dev2 and dev3 = the same in-memory wrapper after the zero-division fix, two full
  runs, assembled with the harness's `--assemble`: 19/19 available, repeat identical for every record (A17's mechanics
  work), fingerprint matches §9. A06, A07, A08 and the pair-coverage test pass on dev2's records (with the wrapper's PCF
  string acknowledged), and catch five in-memory mutations (rung order, re-specification route, a start value, the
  solver's `maxiter`, the selected rung).
- STOPPED HERE (WO-S09-2): the harness, the shell and the tool-free tests are committed; the recorded run waits for the
  PCF ruling. After an erratum to `s09_reference.py` and `s09_cases.json`, the recorded run is
  `spikes/references/s09_qualify.sh benchmarks/s09/references <dir outside the repo> <log>` (about 10 min), then commit
  `benchmarks/s09/references/{qualification/biosteam.json,results/biosteam-*.json}` as the qualification commit.

## WO-S09-2b (second attempt, after Amendment 1)

Fresh build-lane agent, brief `docs/briefs/S09-wo2-qualification.md`. Files opened: the brief, the spec (§18 and the
harness's sections), `s09_cases.json` (SHA-256 `760ab27f…a813c`, as §18 registers), this file, the harness and its tests,
`biosteam/units/stage.py:3040-3050`. Nothing on the brief's forbidden list was opened.

- DECISION (§18.6 item 2): per pass the harness records `fsolve = {ran, nfev, ier, mesg}`; `ran` is
  `info_after is not ABSENT and info_after is not info_before` on `_simultaneous_correction_info`. B2's counter is
  `b2_count(rung, pass)`: fsolve's `nfev` on R3 (None, hence a B2 failure, when it did not run), `iter` elsewhere; the
  rung name is the rung's index in `s09_cases.json → rungs`. The outer-loop evaluations record both passes' B2 counters
  (`pass1_count`, `pass2_count`, `B2_counter`) in place of `pass1_iter`/`pass2_iter`. Checked tool-free on a stand-in
  column: ran/nfev for (fsolve, fsolve), (fsolve, none), (none, none). Reversible by: reverting the harness commit.
- DECISION (§18.6 item 3): the rerun calls `evaluate(…, tol=1e-9, x=run["x"])` directly at L2(c) (one evaluation, no
  loop, `outer = None`) and at L1 (`x = None`); `one_solve`/`outer_loop` lose their `ytol_factor` argument. The record
  carries `form`, which at L2(c) quotes `floor_rerun["L2(c)"]`, so an unamended `s09_cases.json` fails loudly.
- DECISION (§18.6 item 4): the margin rows are the nine of `margin.rows`, in that order (`MARGIN_ROWS`); total-condenser
  vapour only on total-condenser cases, path spread only when two or more rungs pass. The specification row is now the
  largest per-specification `measure / θ_k` (before: largest measure over largest threshold, which mixes kinds when the
  two ends differ). `max_check` becomes `max_row`; the record carries `thin_level` and `effect` from `s09_cases.json`.
- DECISION: tool-free tests gain A08's new item (rerun: `outer is None`, `x` equal to the final evaluation's and
  `returned_x`, tolerance and applied tolerances 1e-9) and, in A07, the `fsolve` block's shape and B2's counter per
  rung. The 10x-ytol rerun-loop check is gone with the loop.
