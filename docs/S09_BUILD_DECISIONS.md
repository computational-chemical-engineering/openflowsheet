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
- MEASURED (recorded run, harness `fd38124d`, clean at head; records committed in `95643b4c` before any classifier
  work, A16): `spikes/references/s09_qualify.sh benchmarks/s09/references <scratch>/repeat_run2 <scratch>/qualify.log`
  → `19/19 available; repeat identical True; fingerprint matches True` (A17: every record of run 2 equals run 1 byte
  for byte without `wall_time*`). No record carries a `harness_error`. No development run was made in this attempt;
  the harness's changed paths were checked tool-free only.
- MEASURED: levels and selected rungs: L1/R1 for RC1, RC2, RC1-RR, RC1-BR, RC1-z, RC2-RR, RC2-B, RC2-z, PC-P, PC-LB;
  L1/R2 for RC3, RC3-Q, RC3-z; L2(c)/R2 for RC4, RC4-D, RC4-z; L2(c)/R1 for RC5, RC6, RC7. Outer evaluations 7 to 9.
  R3 fails rule 2 on all 19 (B4 alone on 9; B1+B2+B3[+B4+B5] on 10, B2 there from the raised pass). R1 fails on the
  RC3 and RC4 families (B3; at L2(c) the first evaluation, B3+B5).
- MEASURED: margin (§18.4(c)): largest row ratio over the 19 selected records 0.0117 (RC6, path spread); every other
  ≤ 2.3e-3. No thin margin (none above 0.1).
- MEASURED: tool-free tests `tests/test_s09_qualification.py` and `tests/test_s09_environment.py`: 13 passed (A03 at
  head and at the qualification commit, A04 file part, A06, A07, A08 with §18.4(b)'s item, pair coverage). `ruff check
  .` and `ruff format --check .` clean.
- STOPPED HERE (WO-S09-2 done): next is WO-S09-3 (classifier, comparison), which recomputes B2 per rung and the margin
  rows from the raw fields (§18.6).

## WO-S09-3 (classifier, gate test, evidence)

Build-lane agent, after the qualification commit `95643b4c` (A16). Files opened: the spec (§2–§18), this file,
`s09_cases.json`, S03's classifier and its gate test and manifest generator, the BioSTEAM records and the harness's
record-writing code (to read the field layout), S03's `comparison.json`, `s03_reference.json`. Commits: classifier and
`comparison.json` `94a9d0c0`; gate test `11a83b08`; manifest generator `6ce5b624`.

- DECISION: A03 and A06–A08 stay in `tests/test_s09_qualification.py` (WO-S09-2's tool-free tests); they are not
  duplicated in `tests/test_s09_references.py`, and the manifest judges them from those nodes. A04's record half
  (every record's fingerprint, rule 1) and A17 (repeat run, re-hashed from the committed records) are added to
  `test_s09_references.py`, as §13 requires a test for each of A01–A18. Alternative: copies in both files.
  Reversible by: moving the tests.
- DECISION: B4's `K_c` is recomputed from SYN-001's closed form at T06's pinned constants (50-digit decimal) at the
  stage's recorded T and P; the harness's per-stage `K` (inside its check block) is not read. §4.3's readback ties the
  tool's `Psat` to the closed form within 1e-14 relative. Measured: largest B4 difference to the harness's value
  1.2e-15 (threshold 1e-8). Alternative: read the recorded `K`. Reversible by: `psat_ratio`.
- DECISION: B5's energy closure sums every stage's computed duty (§5.6: "the duty of every stage"), as the harness
  does and as §6.6's floor (1.4e-11 W) implies. Alternative: the condenser and reboiler duties only (S03's DWSIM form),
  which would repeat rule 2c's intermediate-duty check. No verdict depends on it (intermediate duties ≤ 2.6e-8 W).
  Reversible by: one sum in `rule2`.
- DECISION: rule 2c's order is S03's (stage count, map, inlet stages, pressures, intermediate = adiabatic duty), then
  the total-condenser vapour (where S03 has its zero-liquid-distillate check), the specification read-back, the
  property readback, then S03's 1e-4 specification check. Only the label of a record failing several checks depends
  on it. Reversible by: reordering `rule2c`.
- DECISION: the read-back's expected stored values are recomputed in binary64 from the registered value with §5.6's
  expressions (`1/RR`; total condenser `B = 0` and side draw `1/(1+RR)`; `B/F` with F the exact decimal sum of the
  registered inlet flows; `3.6 Q`), at L2(c) `1/x` or `x` with x the outer loop's `returned_x`, and the run's `x` must
  equal it. The harness's `expected_stored` is not read. All 19 selected runs and their reruns pass exactly.
- DECISION: a total condenser's reflux is the binary64 subtraction of stage 0's liquid and the side draw's flow. A
  decimal subtraction of their shortest reprs gave a value one ulp away on RC2 (0.6749999999999566 against the tool's
  0.6749999999999567); it was replaced before the comparison was committed.
- DECISION: rule 2d also requires the rerun's applied tolerances to equal `floor_rerun`'s (1e-9, 1e-9), label
  `rerun_settings(...)`; rerun failures are labelled `rerun_not_run`, `rerun_rule2(...)`, `rerun_rule2c(...)`,
  `rerun_movement(...)`. Alternative: leave the settings to A08. Reversible by: `rerun_check`.
- DECISION: the margin rows "rerun movement" and "path spread" are computed in the twin's tolerance, as the
  classifier's rule 2d is (§6.4); the harness's are in the tool's. Measured: relative differences ≤ 2.1e-4 (rerun)
  and ≤ 5e-5 (path). Reversible by: `margin`.
- DECISION: A10's "+0.01 Pa" mutation (S03 A12's) is applied to a product's pressure: a stage pressure enters B4's `K`,
  so rule 2 (B4) fires before rule 2c. A10's rerun mutation and A11's path mutation move one component (C) from the
  bottom to the top product, so that rules 2 and 2c and every specification stay unchanged. A10's per-kind test (S03
  §17.9) shifts the registered value against BioSTEAM's view of a record carrying the kind: 9 of the 10 kinds (no
  BioSTEAM record carries a total condenser's distillate rate).
- DECISION: a record that is not available classifies by rule 0 with the record's own reason (S03's pattern). None
  occurs. Each row carries `selection` (the recorded rung and the one recomputed from the raw fields); A18's test
  requires them equal (they are for all 19).
- DECISION: §8.1's row 5 and row 6 outcomes use `pre_registered`'s wording (tools sorted: "three references
  (BioSTEAM, DWSIM, IDAES)", "one reference (BioSTEAM), absent: DWSIM, IDAES"); the absent tools' reasons are quoted
  in `absent_reasons`. IDAES's and DWSIM's classes are read from S03's `x31` block, never recomputed.
- DECISION: rule 1 reads the fingerprint from `docs/reference-environments.md` §9 (exactly one distinct value
  required) and the versions from `s09_cases.json → environment`.
- MEASURED (`comparison.json` at `94a9d0c0`): 17 compared pairs `AGREE` (largest worst ratio 0.0202 tolerance,
  RC6 `bottom[A]`; RC3 family 0.0017–0.0035; all others ≤ 1.1e-5). Controls: PC-LB `DISAGREE` (243.3 tolerances,
  `Q_reboiler`; tool-model distance to PC-LI's 3.6e-7 tolerance), PC-P `DISAGREE` (175.9, `T[1]`); no control
  `AGREE`, BioSTEAM's pairs count. (PC-L, PC-LI) `not_applicable`. Three-tool X31: RC1, RC2 row 5 (three
  references), RC3 row 5 (BioSTEAM, IDAES), RC4 row 6 (BioSTEAM); clause **met where available, 3 of 4** (row 5 in
  3), equal to the pre-registered outcome; inverse kinds RC5, RC6 row 5 (three), RC7 row 5 (two). Reduction to S03's
  two tools reproduces S03's rows and "not met". Thin margin: none (largest 0.0117, RC6 path spread).
- MEASURED: the classifier's recomputation against the harness's summaries (not used, compared once in the
  scratchpad): selection, quantities (exact), path-dependence rung sets and one-phase sets identical for all 19;
  B3 ≤ 9e-17 mol/s, B5 component ≤ 6e-17 mol/s, B5 energy ≤ 4.4e-12 W, final |g| ≤ 1e-16 apart.
- MEASURED: `tests/test_s09_references.py` 125 passed (314 s, most of it the live solve of our side and the three
  generators); `tests/test_s03_references.py`, `test_s03_ours.py`, `test_s09_qualification.py`,
  `test_s09_environment.py` 308 passed; `s09_reference_comparison.py --check` and `s03_reference_comparison.py
  --check` recompute identically; S03's files unchanged since `390e0af5` (A02); `ruff check .`, `ruff format --check .`
  clean.

## WO-S09-5a (merge of main; review should-fix F1)

Build-lane agent, after the package review (`docs/reviews/S09-review.md`) and Amendment 2 (spec §19, R-751, R-752).

- Merge of `main` (S08 at `d96c17ae`, state to `ffcb387f`): two append/append conflicts, resolved as a pure union by
  script (base + main's block + S09's block, every line of both sides kept). `docs/decision-register.md`: 14272 + 239
  (R-728–R-736) + 345 (R-740–R-752) = 14856 lines; `docs/FRANK_QUESTIONS.md`: 176 + 7 + 2 = 185. MEASURED after the
  merge: ledger, T08, M07a and S09 tests 970 passed, 12 skipped, 2 failed (T08 A21, M07a A50). Both fail identically
  at `cca49af5` before the merge (A50: (54, 759, 91) vs (53, 735, 88) there, (55, 771, 93) vs (54, 747, 90) after):
  S09's manifest is not harvested yet, which a later work order does.
- F1 fixed as §19.3 states: the classifier's B3 keeps a NaN (`Decimal("NaN") if r.is_nan() or b3.is_nan() else
  max(b3, abs(r))`, B4's form). §19.5's A09 mutation added
  (`test_a09_b3_keeps_a_nan_in_the_first_flow_it_reads`: RC1's selected run, stage 0, first inlet, A = NaN → rule 2,
  reason `B3(nan mol/s)`). MEASURED: the test fails before the fix (label `AGREE`, the review's probe (a)) and passes
  after; `s09_reference_comparison.py --check` recomputes `comparison.json` identically and `SHA256SUMS` matches
  (A13: every committed B3 is finite, so no committed byte moves).
- `s09_evidence_manifest.py`'s `amendments()` reads §18.5 and §19.5; an id amended twice (A09) carries both,
  §18.5's text first. The manifest's `case_id` names both sections. The manifest is not regenerated here.
- MEASURED (after the fix): `tests/test_s09_*.py` and `tests/test_s03_references.py` 354 passed (396 s);
  `s09_reference.py --check` PASS, 181 claims, `s09_cases.json` byte-identical (`760ab27f…a813c`);
  `s09_reference_comparison.py --check` identical; `ruff check .` and `ruff format --check .` clean (890 files).

## WO-S09-5b (ledger, manifest, harvest)

- DECISION (harvest classes of both S09 manifests, build-lane draft for design-lane review, W5-9's and B-84/B-86/B-91's way;
  S03's classes for the same kinds of item): the superseded `6ce5b624` manifest stays (the verdict document and the state
  file name it), so the harvest classifies it too (as S03's `959131dc` and S10's earlier manifests are). Both share
  limitations[0]-[22] by text. [0], [1] -> E to L18; [2] -> E to U04, L19; [9] (x86-64 only, aarch64 installability) -> E to
  L15; [10] (no sensitivity, no phase-transition robustness, nonideal none) -> E to U04, U05, L20, U02; [3]-[8] (readings of
  NOT_COMPARABLE, ladder, path independence, probes, the clause, partial independence), [11]-[16] (§18.7), [17]-[22]
  (records, thin margin, gate and CI, review) and the old manifest's [23], checks A19, gate, ci -> P. Alternatives: [9] -> P;
  [8] -> E to L18. Reversible by: editing those entries before merge, then `t08_support_matrix.py --emit`.
- MEASURED: manifest `evidence/S09/4d4df0875557cb53bcb0c267ad3a82de38c7d694/manifest.json` (generated at ledger commit
  `4d4df087`, clean tree): `tested`, 26 of 28 checks pass (gate and CI unsupported). Ledger: S09 `tested`; X31 and D19 cite it.
- MEASURED: `HARVEST_SIZE` (54, 747, 90) -> (56, 794, 95) (two manifests, 47 limitations, 5 non-pass checks added). The
  envelope diff is 335 lines appended, 0 deleted; the old file a byte prefix of the new (HG(b), R-617). `--check`: 0 problems.
  Tests: `test_s09_*`, `test_s03_references`, ledger, `test_t08_*`, `test_m07a*`: 1139 passed, 2 skipped; ruff clean.
