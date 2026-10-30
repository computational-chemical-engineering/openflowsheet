# V03 RC decisions (WO-5, brief `docs/briefs/V03-WO5-K3.md`)

Build-lane choices made while executing WO-5, one line each, with what reverts them.

- DECISION: K3 also sets `scripts/t08_support_matrix.ENVELOPE_ID` and re-emits `docs/support-matrix.md` (both outside
  D2.4) → yes, as 0.2.0's A = `0fcf1ad` did; without them `t08_support_matrix.py --check` fails on the envelope id.
  Alternative: leave them for a later commit. Reversible by: revert of K3 `295a2e65`.
- DECISION: the `assessment_report` fixtures that carry `0.3.0.dev0` are left as they are → they are not in §5.1's
  set (nor in 0.2.0's), and no test reads them as the package version. Alternative: bump them too.

## Stop at K3 (§10.1, F-4) — resolved by R-902

The first K3 (`ad4c23db`, discarded, never pushed) failed
`tests/test_m06_w27_coverage.py::test_committed_coverage_json_is_g14_and_this_builds_classification`: it compared
every snapshot field but `git_commit`, so `package_version` `0.3.0` != the committed `0.3.0.dev0`, and the v1 re-take
refuses (`registry_snapshot: unsupported(provider 'iapws95-v1': no registered records and phases, W27-R63)`).
Orchestrator ruling: `package_version` is build provenance and is excluded beside `git_commit` (R-902, rejected:
base-version comparison). Fix commit `91d1cc54` on 4a664416 (W27 tests at 0.3.0.dev0: 56 passed, 2 skipped), then K3.

## Step 2: the G10 re-take (`2d945b5d`)

From a clean detached worktree at K3 (`.claude/worktrees/rc-k3-295a2e6`), E6/K's recipe (alpha-main's `.venv-nlp`,
OMP 1, `PYTHONNOUSERSITE=1`, `PYTHONPATH=src:<nlp-test-tools>`): `--digest-only --old-version 0.3.0.dev0` PASS for all
five, changed digests / version leaves 41/4, 79/7, 70/4, 91/3, 37/4, `other=0`, `environment=equal`; AM-23 5 passed.

- FINDING: `benchmarks/m05/records/**` is a D2.4 path (`v0_1_gate.TREES` holds `benchmarks`), so the brief's "one
  commit (outside D2.4)" is not literally true; the commit changes nothing outside `benchmarks/m05/records/` (36 files).
  0.2.0 put the records inside K (`2c508b5` = A + records); here they follow K3 by the orchestrator's order.
- DECISION: the journey runs at `2d945b5d` (K3 + the G10 records), not at K3 itself → `carry.journey_files` holds
  `benchmarks/m05/**`, so a journey recorded at K3 cannot carry to C (`git diff --name-only K3 2d945b5d -- <carry
  paths>`: 36 files; `v0_2_gate.journey_carry` would answer `JOURNEY_RERUN`). This is 0.2.0's K exactly (A + the G10
  records). Alternative: run at K3 and re-run at C. Reversible by: re-running at K3 (one hour of compute); the carry
  argument at C is then `--carry-journey 2d945b5d`.

## Step 3: the journey (`93886ac3`)

Clean detached worktree at `2d945b5d`, m05's `.venv-nlp`, OMP 1, `PYTHONNOUSERSITE=1`, `PYTHONPATH=src`,
`--m05-record benchmarks/m05/records/trust-region-study-real.json`, artifacts in `~/.cache/v03rc-journey/artifacts`;
budgets unchanged. Exit 0, 3304 s. Decision `refined`, T* = 653.1500351610193 K, BOUND_LOWER, J = 0.4524965242483627;
R0 INDIFFERENT, R1 DECIDED 653.15 K (cold 36, 1554 s), R2 SURROGATE_NOT_PROMOTABLE, R3 DECISION_STABLE.
- R3: M05's REAL record is **not** carried (`carry_identity_differs` from anchor `cdacc32`); M05's study re-ran at
  `2d945b5d` (cold 48, 1455 s; T* 653.1500351610193).
- Against 0.2.0's K record (`2c508b5`): 69 leaves differ, all walls, coupling/run digests, `commit` and R3's
  `m05_record` {path, sha256}; every other number bitwise equal (K's comparison with J′ had 70: it also held
  `registration_sha256`, unchanged here). No stop: nothing differs for a reason other than the code changes.
- `check` ACCEPT; `replay` at `93886ac3` (clean worktree): bitwise, 19 s; `OMP_NUM_THREADS=2` exit 2.
  `tests/test_m07_journey_record.py`: 56 passed. `v0_2_gate.journey_carry(2d945b5d, 93886ac3)`: carried; from K3 it
  would not carry (36 files of `benchmarks/m05/**`).

## Handoff

- Branch `wp/V03-rc` (not pushed): fix `91d1cc54`, K3 `295a2e65` (on `main`), log, G10 re-take `2d945b5d`, journey
  record `93886ac3` (J = `2d945b5d`), this log.
- WO-5 steps 1–3 done. At C the RC job carries the journey with `--carry-journey 2d945b5d --rc C` (not K3).
- Not done: C itself (WO-6's RC job). Scratch: `~/.cache/v03rc-tmp`, `~/.cache/v03rc-journey`, `~/.cache/v03rc-tools`.

# WO-6 (brief `docs/briefs/V03-WO6-RC.md`, on `main` at `4e8c3ba0`)

- First check (before C): `v0_3_gate.py`'s tree rule is `v0_2_gate.main` → `v0_1_gate.tree_differences(rc=C,
  candidate)`: it compares the **candidate with C** under `TREES`, never K3 with C; `m07a`/`m07_evidence_manifest`
  call it as `(C, HEAD)`. No rule or test diffs K3..C, so `2d945b5d`'s and `93886ac3`'s `benchmarks/m05/records` and
  `benchmarks/m07/journey/2d945b5d…` are not refused. Their C-tree bytes enter `release/rc-trees/<C>.json`.
- DECISION: how does the RC dispatch run both the alpha's step 8 (`m07a_rc.py surface`, §3.3) and `rc-coolprop`
  (17b)? `rc-coolprop` ran only under `inputs.rc`, whose `rc-steps` runs T08.A49's surface (`served ==
  R133_DESCRIPTIONS_SHA256`, D_0), red at D_3; with both inputs the two surface steps share `$OUT/surface`. → the
  job's `if` becomes `inputs.rc || inputs.rc_alpha`; the dispatch is `rc_alpha=true` (which includes the
  distribution). A15's test reads `inputs.rc` as a substring and still holds. Alternative: a new `rc_v03` input on
  seven jobs. Reversible by: reverting the ci.yml commit.
- DECISION: where is step 17c's producer (F-V3) and the `mr12_extras_v03` call? → `scripts/v03_rc.py` (committed in
  C, linted, `tests/test_v03_rc.py`) writes the `t08-rc-v1` records of step 15 and 17a–17e; `step17c` records one
  check per `MR12_AUDITS_V03` entry (id = its `check` command, result = its exit status) and then calls
  `m07a_evidence_manifest.mr12_extras_v03_at(C, record)` (the measure's git reading, factored out of
  `_m_mr12_extras_v03`, behaviour unchanged) as a third check `a22.17c.mr12_extras_v03` (pass, `["coolprop",
  "lca"]`). The S13 manifest calls `MEASURES["mr12_extras_v03"]` again over the committed record. Steps 11–14 and
  16 use 0.2.0's `m07_rc_external.py` as 0.2.0 kept it (a tool beside the records). Alternative: everything as
  out-of-tree tools. Reversible by: reverting the producer commit.
- DECISION: V03.A19 (c) names "S10's P1 state", which no S10 record defines (S10's real reference states are
  RE1–RE3; P1–P3 are S10C's column premises) → (c) compares, bitwise (`float.hex`), `evaluate_phase` (both phases,
  every property and derivative; the liquid's `lnphi` carries γ) and `flash` (K) at RE1, RE2, RE3 and A12's state,
  a superset of any one state. Alternative: one state of the design lane's naming. Reversible by: editing
  `v03_rc.A19_STATES`. **Question for the design lane** (batched): which state "P1" meant.
- Step 15's carry argument is `2d945b5d` (WO-5's decision above), not the spec's K3; A21's wording follows it.

## The local run at C = `4fa15efa` (2026-10-30, `~/.cache/of-rc-v03-4fa15ef`, worktree `rc-v03-4fa15ef`)

63 commands; all exit 0 except three steps (and the records that read them):
- **Step 17b FAIL** — `tests/test_s11_w27_v3.py::test_a40_a84_the_build_snapshot_is_s4_and_classifies_the_225_rows`
  (1 failed, 4173 passed): `scripts/s11_w27_s4.py` compares the S4 snapshot in every member but `git_commit`, so at
  0.3.0 `package_version` differs from the committed `0.3.0.dev0` (`S4 DIFFERS: 1 problem(s)`). Not CoolProp-gated:
  it fails in the default suite too, so CI's `check` at C is red on both architectures. K3 had no full gate (R-902's
  fix covered `test_m06_w27_coverage.py` only).
- DECISION: apply R-902 to the S4 check (`package_version` excluded beside `git_commit`; the control test also sets
  it) → outside D2.4, a new C. It narrows a check, so the orchestrator confirms it as R-902's reach before the RC
  re-runs. Alternative: a register entry of its own. Reversible by: reverting that commit.
- **Step 14 FAIL (tooling)** — `m03_nlp_check.sh` with no test paths collects all of `tests/`; three
  `tests/test_s10_*.py` modules (newer than 0.2.0) import `mpmath` at module level, absent from the audited nlp
  environment → collection errors, `pytest -m nlp: exit 2`. Both inventory `--check`s exit 0. Fix in the runner only
  (not in C): pass the modules that hold `mark.nlp`, as E01's manifest does (run N); measured at C: `-m nlp`
  collects the same 190 nodes from those 13 modules as from `tests/` (`--collect-only` lists identical).
- **Step 16 FAIL — stop (design lane)** — `python -m benchmarks.m06.w27.dryrun` (M06 G15's dry run, part of W26's
  G1–G15) refuses: `SnapshotUnsupportedError: registry_snapshot: unsupported(provider 'iapws95-v1': no registered
  records and phases, W27-R63)`, the v1 snapshot refusal spec §2.1 records for W27's coverage. `tests/test_m06_*.py`
  passed and `node --test` passed. A fix touches `benchmarks/` (D2.4) or changes what step 16 runs: not chosen here.
- CI at `4fa15efa` (push 41092667441, dispatch 41092667216; orchestrator's reading): `rc-steps` (both), `dist`,
  `bundle-set`, `rc-ensemble` success; every default-suite job fails exactly the S4 test above; `rc-coolprop` aarch64
  also has one skip, `tests/test_s07_registration.py:242: A31a holds on x86_64 only; this machine is aarch64 (A31b)`.
- DECISION (orchestrator ruling, batched for the verdict): 17b's CI check allows exactly that registered platform
  skip, matched by its reason text, on aarch64 only; x86-64 stays 0 skipped; any other skip fails (`ci.yml`, 17b
  step; tried on five synthetic logs: arm+A31b pass, x86+A31b fail, arm+other fail, arm+both fail, none pass).
  Reversible by: reverting that commit.

## WO-6 handoff (the new C is the commit that adds this section)

- **Branch** `wp/V03-rc`. Old C `4fa15efa` is superseded, never to be judged. The new C is this commit, = `4fa15efa` +
  `fe61ae9d` (R-902 in `scripts/s11_w27_s4.py`, with a control) + `49a9dfc5` (17b's aarch64 A31b skip in `ci.yml`) +
  this log. No D2.4 path changed after WO-5 (`git diff --name-only 28a2be21 <C> -- src schemas benchmarks
  requirements*.lock pyproject.toml MANIFEST.in README.md LICENSE NOTICE` is empty). Dispatch: `gh workflow run ci.yml
  --ref wp/V03-rc -f rc_alpha=true` (only that input).
- **Full gate at `fe61ae9d`** (clean worktree `.claude/worktrees/gate-v03-fe61ae9`, main `.venv` tools): GATE PASS,
  14757 passed, 3206 skipped, 197 deselected (2710 s). `49a9dfc5` changes only `ci.yml` (A15 test 2 passed).
- **Runner** (out of tree, as 0.2.0's): `~/.cache/of-rc-v03-4fa15ef/tools/` — `run_local.sh` (steps 2, 6–17),
  `run_step14.sh` (now passes the 13 `mark.nlp` modules), `m07_rc_external.py` (0.2.0's, output path S13),
  `g12keep.py`, `collect_records.py` (args: artifacts/rc, evidence/S13/<C>/rc, cited.txt, C, docs/v03-rc-record.md).
  Re-run from a fresh `W` and a clean detached worktree at the new C: copy `tools/`, set the worktree path, then
  `bash $W/tools/run_local.sh <wt>` (about 1 h 40 min).
- **What ran at old C (local, 63 commands)**: all exit 0 except steps 14, 16 and 17b (above). Records at old C passed:
  2, 6–13, 15 (carry from `2d945b5d`: carried; check, replay exit 0), 17a, 17c (`["coolprop", "lca"]`, measure
  `pass`), 17d (A24, A25 lca; A33–A36 nlp), 17e (A17, A19 (a)–(d) incl. the superset (c)); step 8 surface PASS.
  **None carries**: the RC record must cite records whose `commit` is C, so every step re-runs at the new C. The old
  run is diagnostic only (`~/.cache/of-rc-v03-4fa15ef/`, worktree `.claude/worktrees/rc-v03-4fa15ef`).
- **Expected at the new C**: steps 14 and 17b pass (the fixes above); **step 16 still FAILs** on G15's W27 dry run
  (`registry_snapshot: unsupported(… iapws95-v1 …, W27-R63)`). That is a design-lane stop (W26's G15 vs §2.1's v1
  snapshot refusal). Record it as FAIL; do not change the step.
- **Not done**: steps 2–17 at the new C; `collect_records.py` + `cited.txt`; `docs/v03-rc-record.md` (in
  `v02-rc-record.md`'s form; step cells must be digits, so 17a–17e are rows with step `17`); `release/rc-trees/<C>.json`
  (`v0_3_gate.py --rc C --write-tree-record`); the S13 manifest generator (none exists; S13a's pattern: A25–A27
  `unsupported` until WO-7/8, the 17c part calls `MEASURES["mr12_extras_v03"]` with `evidence=evidence/S13`); CI ids.
- **Open for the design lane (batched)**: step 16's G15 dry run (stop); R-902's reach to the S4 check; A19 (c)'s "P1
  state" (superset accepted for now); the 17b A31b skip (orchestrator ruling).

## WO-6 at C = `a3e508e3`: the S13 generator and the tree record

- Tree record `release/rc-trees/a3e508e3….json` written by `v0_3_gate.py --rc C --write-tree-record` (`d963c64b`);
  the four test modules that read tree records: 287 passed.
- `scripts/s13_evidence_manifest.py` in `m07_evidence_manifest.py`'s pattern: one check per §7 assertion (catalogue
  read from the spec; a missing rule stops it), D-gated ones by S13a's selections run here (A12 (c) by
  `s11_identity.py` with its own `TMPDIR`), R-gated ones from `rc/records.json`'s committed records, CI runs at C,
  and the gate's own readers (`rc_record_problems`, `adr_problems`, `verdict_document`); 17c also through M07a's
  `MEASURES["mr12_extras_v03"]` with `evidence/S13` (F-V3).
- DECISION: what `S11.G8`, `S12.G8`, `S12.G10` are at C (A27 names them, the spec does not define them at C) →
  S11.G8 = full gate log + `check` and `rc-coolprop` on both architectures + step 17b's record; S12.G8 = full gate log +
  `check` on both; S12.G10 = step 17a's record (E01 §9.6 G10 is A48 = 17a). Alternative: the CI jobs only.
  Reversible by: editing `GATES` in the generator.
- DECISION: "one check per ADR in S13's manifest" (§6) → `ADR.<n>` checks transcribed from WO-4's table: `met` rows
  pass iff the status line is Accepted; 0050–0052 take V03.A24's result (their condition); 0043 passes iff Proposed and
  not required; 0053/0054 are `unsupported` (pending) until Accepted at WO-8. Alternative: a committed JSON. Reversible
  by: editing `adr_checks`.
- DECISION: before WO-7/WO-8, V03.A25 (when the verdict document does not exist yet) and V03.A27 (while step 18 has
  not run) are `unsupported` with `state: pending`, not `fail` (S13a's pattern; the handoff's "A25–A27 unsupported
  until WO-7/8"). `unsupported` is not a pass, so the status stays `implemented`. Reversible by: two `if`s.
- **Amendment 2 (`8e0cb1a1`, R-903…R-908) in the runner and the generator.** C stays `a3e508e3`. Out of tree
  (`~/.cache/of-rc-v03-a3e508e/tools/`, edited while the run was at step 12, before step 14 started; `run_local.sh`
  untouched): `run_step14.sh` writes `step14/nlp-modules.txt` (the `grep -l 'mark.nlp'` list) and adds
  `step14-nlp-collect-selected` / `step14-nlp-collect-all` (`--collect-only -q -m nlp`, modules vs `tests/`);
  `m07_rc_external.py` step 14 adds `a60.w24.nlp_selection` (A33), step 16 is `W26 (V03 spec §3.5, V03.A32)` with
  `a60.w26.g15_registered_states` (the 25 nodes, `skipped_total`) and `a60.w26.w27_v1_refusal` (exit 1, the exact
  W27-R63 last line, no `<C7>/summary.json`) in place of `w27_dry_run`. Generator: A32 (step 16's record, exactly the
  four checks), A33 (step 14's record, modules carried, 190 equal sets).
- **Controls (§4 of the ruling), on `4fa15efa`'s inputs** (its step-16 junit and dry-run log, `nlp-files.txt` /
  `nlp-all.txt`): unmodified, (c), (d) and `nlp_selection` pass (190 = 190, equal). (c) fails with a `<skipped>` child
  on `test_harness_states[W27-S04]`, and with `test_candidate_states[W27-S11]` deleted (reported `missing`); (d) fails
  on the `unsupported(route enumeration) for openflowsheet 0.3.0` last line, and on exit 0; `nlp_selection` fails with
  one id removed from either list, and on two empty lists.

## The RC run at C = `a3e508e3` (2026-10-30, `~/.cache/of-rc-v03-a3e508e`, worktree `rc-v03-a3e508e`)

- Fresh `W`, clean detached worktree, the handoff's runner plus: a private `--basetemp` per pytest under
  `~/.cache/v03rc-tmp/rc-a3e508e/` (inert), and Amendment 2's step-14/16 changes (above). 65 commands, 3994 s; every
  exit 0 except `step14-nlp-collect-all` 2 and `step16-dryrun` 1 (both registered by Amendment 2). Tree clean at start,
  after venv, after archive, at end; nlp worktree: 50 ignored `__pycache__` entries at the end, as at `4fa15efa`.
- Every record passes at C: steps 2, 6–16 and 17a–17e (`passed`, all checks `pass`, `commit` = C, `tree_clean`); step 16
  4/4 (662 passed, 0 skipped; node 92/92; G15 25 of 25; the exact W27-R63 refusal, exit 1, no `summary.json`); step 14
  5/5 (190 = 190, equal sets, 13 modules); step 15 "the journey at 2d945b5d carried", ACCEPT, bitwise; 17b 4174 passed,
  0 skipped; ensemble S = 437 (F-FALSE-SUCCESS-CAUGHT 3).
- CI at C: dispatch 41108983463 (`rc_alpha=true`) success, push 41108983672 success, Site 41108983605 success.
  THM-09/4 rows copied (`0b112d13`). Records, tools, step-1 skips and `docs/v03-rc-record.md` committed (`0caf09a0`);
  `rc_record_problems` reads the record with no problem.
- S13 generator at C (`--gate-log gate-fe61ae9.log --ci-run 41108983463 --ci-run 41108983672`): 47 checks, 40 pass,
  1 fail (V03.A12), 6 unsupported (A08 R part, A25, A26, A27, ADR.0053, ADR.0054: pending WO-7/WO-8). Manifest not
  committed (removed: an untracked manifest makes `test_m07a_a50_the_harvest_size…` and `test_t08_w2_support_envelope
  ::test_a21…` fail — committing S13's manifest needs the harvest/envelope update S13a's commit made).
- **STOP — V03.A12 (c) fails at C.** `scripts/s11_identity.py` (base `8c34ecb0`): `S11-IDENTITY FAIL n=54494`, 47
  family-C digests differ, all binder calls of `tests/test_m04_wo{7,8,19,20}_*.py` (surrogate manifests); identical key
  set on a second run with a fresh `TMPDIR`. Cause: the only `src/` change since S13a's passing run (`0ce3748a`) is K3's
  `__version__` `0.3.0.dev0` → `0.3.0`, and `adapters/experiments/backends.py:174` writes `openflowsheet_version` into
  each experiment manifest, so the bound documents' SHA-256 change. Not a numerics change; the same class as R-902
  (version as build provenance). A fix changes a check (s11_identity's comparison or its base) or how A12 (c) is judged
  at C — design lane. Options: (a) R-902's reach to `s11_identity.py` (exclude `openflowsheet_version` from the
  document digest, with a control); (b) judge A12 (c) at C by S13a's pass at `0ce3748a` plus "src diff = version only";
  (c) a base at K3. Default I would take: (a). Nothing else depends on it.

## WO-7b at C = `a3e508e3`: the verdict's build-lane fixes (F1 = V03.A34, F3, F6, F8)

- F1 step 1 (`3b05511d`): step 12's own `step12/g11-coverage-v3.runs.json` (`cdb7d999…fd0a`) committed before the
  re-run. Then `tools/run_g11keep.sh` (out of tree, copied to `evidence/S13/<C>/tools/`): `step12-g11`'s exact
  arguments through 0.2.0's `g11keep.py`, OMP/OPENBLAS/MKL = 1, `OPENFLOWSHEET_EXTERNAL_ROOT` as step 12: exit 0,
  1758 s (step 12: 1755 s); RC worktree clean before and after; keep dir 105 MB (ignored). `g11collect.py`: 2 runs,
  121 points, 105 boundary with one experiment each, 16 direct. `g11keep.py.txt` and `g11collect.py.txt` are
  byte-identical to `evidence/M07/ce993651…/tools/` (`cmp`), so no diff to record (§4 item 2).
- V03.A34 (Amendment 3, R-909) record `step12/experiments/rc-step12-experiments.json` (`c8e9be63…`), written by
  `tools/g11record.py.txt`: (a) exit 0; (b) 242 point-runs, 6 members incl. `attempts`, 0 differences
  (`tools/g11equal.py.txt`); (c) the audit given step 12's own runs file: exit 0, the registered line, j = 420. Also:
  S12.2/S12.3 (0.2.0's `s12_check.py.txt` against `6fec822`'s record) hold; the collected records are runs 1, 2 bound
  to the re-run's runs file, per-run (label, path) multisets equal step 12's own (210 boundary, 32 direct).
  Controls of `g11equal.py` on 0.2.0's committed records: passes unmodified; fails with one `stage` changed, one
  `attempts` changed, two labels swapped, a member added on one side only, run 1 given twice, one record path changed.
- DECISION: TMPDIR for the re-run → private `~/.cache/v03rc-tmp/wo7b/tmp` (brief rule; inert: G11's stores go to the
  keep dir, step 12 used the default). Alternative: the default. Reversible by: deleting one `export` in
  `run_g11keep.sh` and re-running.
- DECISION: A34's record is written by a new tool `g11record.py` (t08_rc's `check`/`finish`, rc-step12.json's
  provenance) rather than a step in `m07_rc_external.py` → the RC runner stays as it ran. Alternative: a step-12b in
  `m07_rc_external.py`. Reversible by: moving the function.
- RC record: step 12's data row cites the runs file; a new step-12 row (V03.A34) cites the six files; `records.json`
  110 entries (two gzip); `rc_record_problems` → `[]`. F6: step 8's local cell now reads "served D_3 (c_3, R-295)
  `455d01eb…`; strip c_3 → `383b4e2c…`" (`3970c35a`). F3: one bullet in `## v0.3.0` "What it is not" (`41b99a9b`).
  F8: ADRs 0050–0052 Accepted (`fa8d4f0e`; rows in `docs/V03_DECISIONS.md`).
- **Amendment 3 in the S13 generator** (§10.5 items 2, 4): V03.A34 = `step12/experiments/rc-step12-experiments.json`
  through T08's `_record` (re-hashed against `records.json`) plus a measure requiring exactly A34's three ids, each
  `pass`; A12 (c) decided by `a12c_decide` (a pure function of §7.1's facts) after R0, with R1 in a detached worktree
  of HEAD (version line V_C → V_B, `--keep` under `artifacts/V03.A12c-aligned-keep/`, worktree removed after);
  the three limitation texts verbatim (checked against the spec text). `s11_identity.py` not edited.
  Controls (`tools/s13_controls.py.txt`, before the commit): 15 of 15 as expected — A12 (c) passes on a PASS-shaped
  R0 with everything else broken and on the lines measured at C (R0 `n=54494 … (47 digests differ)`, R1
  `n=54494 changed=[] (C branch shards [1, 3, 7, 11] exited non-zero)`, the five readers from
  `~/.cache/v03rc-a12-keep/branch/`); fails on R0 key `A:`, R0 naming a failed shard, R1 with a changed key, R1
  naming a base shard, n+1, a sixth id, four of five, a two-line numstat, V_C = V_B. A34 passes on the committed
  record, fails with one check `fail`, with a fourth check, and without its `records.json` entry.
- DECISION: when R0 passes, §7.1 says (c) passes "whatever else it is given" → the clean-tracked-files fact is
  recorded but not required in that branch (the generator refuses a dirty tree before it runs anyway).
  Alternative: require it in both branches. Reversible by: moving one line in `a12c_decide`.
