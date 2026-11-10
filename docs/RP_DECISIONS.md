# RP build decisions (ADR 0055 WO-R2, WO-R3, WO-R4, WO-R6)

Build lane, branch `wp/RP`. Brief: `docs/briefs/REL-build-WO-R2-R3.md`. Normative text: RP
(`docs/derivations/release-procedure.md`). Each choice below is isolated in `scripts/release_gate.py` and named
where it lives. Questions for the design lane are batched for the one `reviewer` pass over WO-R2…R6 (ADR 0055 §6).

## Choices (build lane, 2026-11-06)

- **B-1 Mode.** Dated mode iff neither acceptances table has a `Scope` column (REL.A03's wording); then
  `release_gate` calls the engine's `main`/`build` unchanged. Standing mode otherwise (`standing_acceptances`).
- **B-2 Where things are read.** The line file, its chain and the schema are read in the candidate's tree (as the
  engine reads every input, and RP §8.2 E1). RP.L05/RP.L08 are checked in `C`'s tree by git (RP §3.4). A line with
  `gates` or `rc_items` whose `C` is not a commit of the repository is refused, exit 2.
- **B-3 Scope of the checks.** RP.L01/L02 on every file of the chain; RP.L03/L04 on every link of the chain;
  RP.L06–L10 on the judged line; RP.L10 for either role (0.3's acceptances are ADR 0053, which passes).
- **B-4 New versus standing row.** A row is *new* (RP §8.4) iff its `Accepted at` is `C` ("carries the fingerprint
  and commit at the C it answers"). A new failure-clause row keeps the engine's `Judged` and Table T7 bounds (its
  own date is passed to `judge_gate`); a standing one has none (`datetime.date.max`, D3.4). A new decision row is
  dated on or after the lapse report's first-line date, which must name this `C`.
- **B-5 Table T7's upper bound** (an answer a re-judged gate waits on counts only up to the re-judgement) is kept
  for decision items in standing mode, as the engine's item 11 has it.
- **B-6 Report naming.** In standing mode `GateSet.adr` is the acceptances path (`StandingGateSet`), so reports say
  `release/acceptances.md` where the engine says `ADR 0053`. The engine's section suffixes (D2, D2.3, D3, D4) are
  its own text and stay.
- **B-7 Composition.** The engine's `build` takes no policy argument and is not edited, so standing mode composes
  its parts (`verdict_document`, `judge_gate`, `rc_record_problems`, `manifest_problems`, `envelope_problems`,
  `adr_problems`, `links_problems`) in `build`'s order and keys (`_build_standing`). Dated mode and the
  not-covered report call `engine.build` itself.
- **B-8 Report lines** (RP §8.5): `standing acceptance <item>: accepted <date> at <commit>, scope unchanged` for
  each row used; `acceptance <item>: lapsed (<terms>)`, `… unsupported (<reason>)`, `acceptance <clause>: not
  used`. They precede the YES/NO line, and are the JSON key `acceptances`.
- **B-9 Naming a lapse.** The differing terms are found by re-evaluating the scope at `Accepted at`: a `paths:`
  term by the paths whose records differ, an `extract:` term by itself; if `Accepted at` does not reproduce the
  recorded fingerprint, the report says only that. E1/E4 at a commit other than `C` read the newest line file of
  the chain present there, else the chain's root from the candidate (RP §8.2's seed rule, generalised). Only the
  wording depends on this; standing or lapsed is decided at `C` alone.
- **B-10 `--lapses`** prints the report to stdout (the build lane commits it as
  `evidence/<pkg>/<C>/acceptance-lapses.txt`); a row line is `<item>: stands | lapsed (…) | unsupported (…)`; the
  date is UTC; exit 0. It is refused (exit 2) on a dated line.
- **B-11 Malformed standing table** (Scope not one backtick span, an unknown term or extractor, a Fingerprint or
  Accepted-at of the wrong shape, not exactly one table of each kind, a missing column): exit 2, as a malformed
  verdict document is.
- **B-12 Extractors.** E3 is the engine's `link_registers` (an empty `LINKS` is unsupported). E4 needs exactly one
  item-1 chain entry per step-8 record; listed files not ending `.json` are not read.
- **B-13 Item 13** does not exist while D2 is deferred (RP.S06): the hook is the term `gate_row:<g>`, always
  `unsupported (gate_row needs the evidence fingerprint, ADR 0055 D2, deferred)`.
- **B-14 `release.yml`.** The role is read with `python -c json`; a malformed line file fails the step (bash `-e`).
  Refusal `no release gate for the <M>.<m> line`; the other refusals name the command run.
- **B-15 Engine-only commands** (`--write-tree-record`, `--carry-journey`, `--carry-w27`) run the engine with the
  line's gate set after the loader, without RP.L05/L08 (they judge nothing). Every line admits post-releases.

## Questions for the design lane (defaults applied)

- **Q-B1 (B-4).** RP does not say how the gate tells a new row from a standing one. Default: `Accepted at` = `C`.
- **Q-B2 (B-5).** RP §8.4 states only the lower bound for a decision item. Default: the engine's T7 upper bound too.
- **Q-B3 (B-6).** Standing-mode reasons read e.g. `FAIL clause not accepted in release/acceptances.md D3`, `(…
  release/acceptances.md D4)`. A wording ruling would need either this text or an engine edit (frozen).
- **Q-B4.** A row is checked only at `C` (RP §8.3 (b)); its fingerprint is never verified at `Accepted at`, so a
  hand-edited row with an old `Accepted at` and `C`'s fingerprint escapes §8.4's date bound. Default: as RP says.
- **Q-B5 (B-2).** A `C` known only from `release/rc-trees/` cannot pass RP.L05/L08. Default: refused, exit 2.

## Measured (2026-11-06, at `76d6ef68` + this branch)

- The seven seeded fingerprints and all eleven term hashes of `release/acceptances.md` recompute at `a3e508e3`
  exactly. At HEAD: V14 (b) is lapsed only by `src/openflowsheet/__init__.py`; V17 carry is unsupported (no
  REL040 records yet); the other five stand.
- `release_gate.py --line 0.4 --rc HEAD`: exit 2, `RP.L08: WHEEL-DATA script scripts/wheel_data_check.py: not at
  C`, alone (RP §3.4 predicts it until WO-R6).
- REL.A03 at the checkout (`--rc a3e508e3`, text and `--json`): stdout byte-identical. HEAD is `0.4.0.dev0`, so
  both print the not-covered report; `--candidate a3e508e3` cannot be compared because that tree has no line file.
  The fixture comparison (V03.A06–A08's 17 states and the W27 malformed case) carries the substance.

## Choices (build lane, WO-R4/WO-R6, 2026-11-06)

- **C-1 `release-audit` not added.** The brief and ADR 0055's WO-R4 row list it; RP §6.10 (binding) says it is D2.3's
  and is not added while D2 is deferred. RP followed. Reversible: add the job when D2 is adopted.
- **C-2 Step 8 under `release_rc`** is a new `rc-steps` step `python scripts/release_rc.py surface`, which calls
  `m07a_rc.py surface` unchanged. The `rc_alpha` step's `if` is not widened: RP §6.10 keeps `rc`/`rc_alpha` as they
  are, and `tests/test_m07a_surface_chain.py` (legacy) pins it. Reversible: one step in `ci.yml`.
- **C-3 `default-install` skipped under `release_rc`** (same `if` as `check`): RP §6.10 "runs the RC jobs only".
- **C-4 junit** via `OPENFLOWSHEET_JUNIT_DIR` in `scripts/check.sh` (pytest `--junitxml`, node `--test-reporter=junit`
  beside `spec`), not `PYTEST_ADDOPTS`, which subprocess pytest runs in the suite would inherit and overwrite.
  Unset, `check.sh` is unchanged. Artifact `junit-<arch>`, `if-no-files-found: error`.
- **C-5 `wheel_data_check.py` copies** 17e's functions (`wheel_findings`, `a19_findings`, `exact`, `answers`,
  `probe`) rather than importing `v03_rc.py`: RP §3.3 forbids a per-release RC script as an item's owner, and the
  legacy script is not edited. A test pins that both decide identically. Check ids kept (`a17.*`, `a19.*`); 17e's
  `a22.17e.t08_a43` becomes `wheel.built` (T08.A43 itself is step 3's, RP §3.6). Work dir: `--out` or a temp dir;
  findings go to stdout, which the wrapper hashes and keeps as `step17/<id>.log`.
- **C-6 Step-17 wrapper.** `local:` items run with `PYTHONPATH=<C>/src:<C>` and one thread (0.3.0's `P` array);
  `nlp` items under `env -i` with HOME, PATH, LANG (0.3.0's 17d). "Records the command wrote itself" = files under
  `<rc>` new or changed during the item. Interpreters other than `project` are given as `--python ENV=PATH`; a
  missing one, or an unset `$NAME`, is `unsupported`. `ci:` items need `--ci-run` (a dispatch at C), else
  `unsupported`; artifacts `<job>-*` go to `step17/<id>/`.
- **C-7 Step 1's ratio lines** are the log lines of the `check` steps `S07 A31 line` and `S11 thermal reference
  line`, recorded per leg in `s1.check.<arch>`, not judged (RP.S15).
- **C-8 N-4's junit measurement** is read on the push run at the dispatch's head (the dispatch skips `check`, which
  is what writes junit).

## Questions for the design lane (defaults applied)

- **Q-C1 (C-1).** ADR 0055's WO-R4 row lists `release-audit`; RP §6.10 defers it with D2. An ADR note should align.
- **Q-C2 (C-8).** "One dispatch shows junit-x86_64/junit-aarch64 present": the dispatch cannot, since `check` is
  skipped by D4.2; default: the push run at the same commit shows them.

## Measured (WO-R4/R6, 2026-11-06)

- `scripts/wheel_data_check.py --commit b69dc0f1` (real build, fresh venv): `wheel data check: PASS`, 11/11 checks.
- RP.L01–L10 on `release/lines/0.4.json`: all pass at `bd672ff7` (`tree_problems` = []); RP.L08 control (script
  absent from the tracked set) refused.
- REL.A17 tests (`tests/test_rel_ci_release_rc.py`): 17 passed; workflow suites (`test_release_workflows`,
  `test_m07a_surface_chain`, `test_v03_rc_coolprop`, `test_s07_packaging`) unchanged and green.
- The one `release_rc` dispatch: run 42156856877 at `bd672ff7`, `success`. `check`, `identity`, `default-install`
  skipped; `rc-steps` ×2, `rc-coolprop` ×2, `rc-ensemble`, `dist`, `clean-install` ×2, `bundle-set`,
  `bundle-replay` ×2, `ptc-r1` ×2 all `success`. PTC-R1 (Q-13, N-2): `compare --run` 70 s on x86-64; job wall
  1 min 54 s (x86-64), 1 min 28 s (aarch64) — far inside 360 min, so the item stands.
- Push run 42156850745 at `bd672ff7`: `check` success on both legs (x86-64 1 h 40 min, aarch64 1 h 12 min),
  `identity` success, artifacts `junit-x86_64` and `junit-aarch64` present.
- Full gate at `bd672ff7`: `GATE PASS: 14995 passed, 3206 skipped, 197 deselected` (8527 s).

## Choices (build lane, WO-R6b, 2026-11-06)

- **C-9 The runner's layout** (`release_rc.py local`, `scripts/release_rc_local.py`). It runs from the checkout at C
  the line's `gate_set.rc_steps` that have a local leg (2, 6–17), `--steps` narrowing them. Records go under `--rc`
  = `evidence/<pkg>/<C>/artifacts/rc` (git-ignored), 0.3.0's paths and check ids; `--rc` outside the checkout is
  refused, because M02's judges (`m02_evidence_manifest.g10`–`g12`) name records relative to it. Logs, the summary
  (`<label> exit <code> :: <command>`, 0.3.0's form), the venvs, `external/`, the worktrees, the step-12 inputs and
  G11's keep directory go under `--work`.
- **C-10 G11's keep directory is `<work>/g11-keep`**, not under `<rc>/step12/`, so that step 10's certificate audit
  reads exactly the directories 0.3.0's read (0.3.0 kept G11's stores in a re-run after step 10). 0.2.0's G12 keep
  wrapper, which step 10 needs (R-348), is promoted with G11's into one tracked script `scripts/m07_rc_keep.py`
  (`g11`, `g11-collect`, `g12`); behaviour unchanged, the collected record's `description` names the script. A test
  pins that its collector writes what `g11collect.py.txt` wrote.
- **C-11 Step 12's archived inputs stay 0.2.0's and 0.3.0's**: `--previous-v3`/`--previous` are WO-12a′'s v3
  records at `bd446ab` (`STEP12_INPUTS_AT`), as RP §6.3's "registered constants at C". See Q-C3.
- **C-12 The `nlp` items run from the clean nlp worktree at C** (`items --nlp-root`, commit `88045740`), as step 14
  and 0.3.0's 17d: the RC checkout carries the project venv's editable install, which the audited environment's
  fingerprint would count. Revert the commit to run them from the repository root.
- **C-13 Missing inputs are refused up front**: a selected step 14 or 15 without `--nlp-prefix`/`--nlp-cache`, a
  step 15 without `--journey`, exit 2 before anything runs. A step-17 `nlp` item without them stays `unsupported`.
- **C-14 `local`'s exit** is 0 iff every record it wrote passed and `step17-items` exited 0. A command's own exit is
  judged in its record (step 14's collection over `tests/` and step 16's dry run exit non-zero by design).
- **C-15 `records` takes the cited list as a file** (`--cited`, one path per line, as 0.3.0's `tools/cited.txt`):
  the RC record's hashes are written from `records.json` (§6.9), so the list cannot be read from it. A path cited
  twice or absent is refused (exit 2). Step 12's kept G12 certificates are copied to `step12/certificates/` after
  step 10 (0.3.0's `collect.sh`).
- **C-16 `r375.audit`'s writer runs the audit itself** and judges its stdout's last line (0.3.0's `g11record`); the
  keep and collect exits are recorded in the check, not judged ("exactly one check", §6.4).
- **C-17 `ci`** ports `fetch_ci.sh`: the `release_rc` dispatch at C's artifacts into `<rc>/ci/`, each job that ran
  into `ci/job-logs/<job>-<leg>.log`; a run that is not a dispatch at C is refused.

## Questions for the design lane (WO-R6b, defaults applied)

- **Q-C3 (C-11).** RP §6.3 says step constants are "the registered ones at C"; step 12's archived inputs
  (`bd446ab`'s v3 records) are named only in 0.3.0's runner. Register them, or name the inputs a release uses.
- **Q-C4.** Step 16 (c) needs the pinned W27 archive in `evidence/M06/W27/artifacts/`; RP §6.6 does not say where
  the runner takes it from. Default: `--w27-artifacts DIR`, hard-linked as 0.3.0 did; absent, (c) fails.

## Measured (WO-R6b, 2026-11-06)

- Real `release_rc.py local --line 0.4 --steps 2,7,8,9,10,13` at `88045740` (1045 s, fresh `rcvenv` from the lock):
  `identity` 3/3, `corpus` 12/12, `surface-alpha` 8/8, A30 exit 0, `certificates` 2/2; every record `commit` = C,
  `tree_clean` true (the editable install leaves the tree clean), `ref-x86-64`. Step 13 failed, 85 errors: pytest's
  `--basetemp` parent did not exist; fixed in `df30b36e`. Re-run of step 13 at `df30b36e` (624 s): `rc-step13`
  3/3 pass, 696 tests, 0 failures, 0 skipped.
- `release_rc.py records` on those records: 3 collected as is; an absent cited path refused, exit 2.
- Not run here: steps 6, 11, 12 (hours; the reactor and IDAES environments), 14, 15 and the nlp item (the audited nlp
  environment lives in another worktree), 16 (the pinned W27 archive likewise), `ci` (no dispatch at this head).
- `tests/test_rel_rc_local.py` 20 passed; `tests/test_rel_*.py`, `test_release_workflows.py`,
  `test_m07a_surface_chain.py` 192 passed; F0 `corpus_identity.py --check` PASS (M1–M9 all equal).

## Choices (build lane, WO-R6c, 2026-11-06)

- **C-18 RP.S11 reads steps 1, 3–5 and the CI legs through the CI jobs**, V03.A20's form ("same form"): step 1 is the
  push run's `check` on both legs, step 2's G05 the push run's `identity`, steps 2–10's CI legs the dispatch's jobs;
  the local records of steps 2, 6–14, 16 (those in `rc_steps`); the RC record by `rc_record_problems`. Step 1's full
  record (its four checks, junit) is RP.S15's. Reversible: `STEP_JOBS`/`SPECS["S11"]` in the generator.
- **C-19 The D rules.** Test selections, each its own pytest process (S13a's rule): S01 the RP.L tests, S03 V03.A03's
  three legacy files whole + REL.A02's test, S04 V03 `a04_`, S06 V03 `a06_` + REL.A03's fixtures, S07
  `test_rel_standing_acceptances.py`, S08 V03 `a08_` + REL.A03/A05, S22 `test_m07a_harvest.py -k r911`. S02, S05,
  S22 are also measured directly from the line (T-V(M.m), the clause grammar, `HARVEST_EXCLUDED` at C). The line
  file is read in the checkout (outside D2.4); RP.L05/L08 at C.
- **C-20 Where RP names no input.** S16's manifest-conditioned ADRs are `--manifest-adr N` (R-914; none by default).
  S17's acceptances part: every row the gate needs (each `frank_items` row, each failing clause's row) stands at C.
  S10's failure lines come from the failure rows that stand. S20 requires its two checks `pass`, not "exactly two"
  (§6.5 says "holds"; 0.3.0's record has five). A line without `rc_items` makes S13 `unsupported`, never a vacuous
  pass. S22's 0.3.0 counterpart is a test, not an S13 check: its REL.A20 status is RP's stated `pass`.
- **C-21 `--rel-a20`** runs over a past release's records, so HEAD's trees may differ from C's there (only there),
  and it writes only to `--out`. Saved `gh run view` answers are read with `--ci-json`; 0.3.0's two
  (`tests/fixtures/rel/s13-ci/`) hash to the `stdout_sha256` S13's manifest recorded for them (a test pins it).

## Questions for the design lane (WO-R6c, default applied)

- **Q-C5 (REL.A20 cannot pass as written).** RP.S18 is "same form", but its rule (a) is "every other check passes",
  and over 0.3.0's records five changed-form checks fail by construction (S10: no failure lines; S13: no `rc_items`,
  `unsupported`; S15: no step-1 record; S17: ADR 0053 is not a standing table; S21: three checks). So RP.S18 is
  `fail` where S13's V03.A27 is `pass`, and REL.A20 is FAIL: 12 of 13 same-form equal. Default: RP followed
  literally, REL.A20 reported FAIL; the test pins that RP.S18's `not_pass` lies wholly in the changed-form set. A
  ruling could move RP.S18 to §11.2's changed list, or compare it over the same-form checks (an RP amendment).

## Measured (WO-R6c, 2026-11-06)

- `release_evidence_manifest.py --line 0.3 --commit a3e508e3 … --rel-a20` at `3e7ccf00` (38 s, exit 1, stdout
  `7c82ba9d…`): 22 checks, 16 pass, 5 fail, 1 unsupported. Same form: S02, S03, S04, S06, S08, S09, S11, S12, S14,
  S16, S19, S22 `pass` = S13; S18 `fail` (Q-C5). Changed form: S01, S05, S07, S20 pass (0.3.0's n = 190 meets n ≥ 1);
  S10, S15, S17, S21 fail; S13 unsupported. `REL.A20: FAIL`.
- `tests/test_rel_*.py tests/test_release_workflows.py`: 195 passed; ruff, ruff format, mypy clean; F0
  `corpus_identity.py --check` PASS (M1–M9 all equal).
- Full gate at `3e7ccf00` (8095 s): `GATE FAIL: 29 failed, 14999 passed, 3207 skipped, 197 deselected, 1 error`. All
  29 failures and the one teardown error are `tests/test_m06_browser_smoke.py`: the headless browser went away
  (`BrokenPipeError`) under host load. That module alone at the same commit: 31 passed in 43.7 s. Not a code
  failure of this branch (no web or browser file changed), but the gate is red as run; it is not re-baselined.

## Choices and questions (WO-R6c, the manifest)

- **C-22 Package RP's manifest is filed as `S15`** (`evidence/S15/3e7ccf00…/manifest.json`): the frozen schema's
  `work_package` pattern refuses `RP` (R-878's rule; E01 → S12, V03 → S13, DOC → S14). Harvested, 6 limitations and
  2 checks, class P (F0's D22); `HARVEST_SIZE` (69, 945, 122). Reversible: `git mv` to `evidence/RP/` after a schema
  ADR, and the harvest entries' paths with it.
- **Q-C6.** RP §3.1 (D1.5) names the release package `REL040`, which the same pattern refuses: at 0.4.0 the release
  manifest `evidence/REL040/<C>/manifest.json` fails `t08.problems` (schema). Either an ADR admits `REL\d{3}` (and
  `RP`), as ADR 0059 D1 admitted the roadmap ids, or RP names an S-id for each release package.

## WO-R7 (build lane, 2026-11-06): the RP review's fixes

Review `docs/reviews/RP-review.md` (binding), brief `docs/briefs/REL-build-WO-R7.md`. Amendments A-1…A-8 pasted into
RP §17.1 with their section edits, register R-942…R-949 (`7799bd72`); ADR 0055 §10 gains ruling 2's restated
acceptance and notes (M-3), status unchanged.

### Choices (each isolated in its commit)

- **C-23 A-3's chain check runs in standing mode only** (`411a6e52`). The dated path is the legacy engine unchanged
  (REL.A03 pins it byte-identical to `v0_3_gate.py`), and 0.3.0's C holds no line file, so a literal check there
  would refuse 0.3.0. The check runs for the report and for `--lapses`. Reversible: move the `chain_problems` call in
  `release_gate.main` above the `table is None` branch.
- **C-24 REL.A09's fixture names S13 as the package at `OLD`** (`03ff3ff3`). It put the 0.4 line (package REL040) at
  `OLD`, where the fixture's records are S13's, so the other decision rows, recorded at `OLD`, did not reproduce there
  and A-2 refused them. The fixture's history is now coherent; the assertion (a claim-set change lapses `Claim set`)
  is unchanged.
- **C-25 S-4 is step 1's selection plus a stated remedy, not a fifth check** (`e677ac36`). A push run exists only
  for a pushed head, so `push_run` (head = C) already fails C pushed beneath later commits; `s1.push_run` then names
  `git push origin C:refs/heads/rc/<C7>`. RP §6.2's "exactly these checks" stays four; `runs_at_c` is a record field.
- **C-26 The `release_rc` dispatch is the greatest `workflow_dispatch` run id of `ci.yml` at C** (`e677ac36`,
  `26f86b0e`). `gh run list` does not show a dispatch's inputs; at a release's C only `release_rc` is dispatched.
  `gh run view` without `--attempt` reads the latest attempt, so the manifest compares an attempt only where the given
  run states one (`t08.fetch_ci`'s fields carry none, and `t08_evidence_manifest.py` is legacy, not edited). A step 1
  record without `runs_at_c` is refused.
- **C-27 "Stops the RC" (§12) for A-5 and C-12** (`2049b4ed`): the runner writes `stop-step12-inputs` /
  `stop-nlp-wt exit 2`, runs no step 12 command, no step 14 and no step-17 nlp item, and exits 1 (`records_passed`
  judges every `stop-` line). The other steps still run, so one run shows every failure. Without a clean nlp tree at
  C the nlp items stay `unsupported`, never run from elsewhere.
- **C-28 REL.A18 and REL.A19 got tests** (`3dfa0ff0`): ruling 2's acceptance needs A17–A20 in a `tested` manifest,
  and neither had an executable check (A19's fingerprints did; its six verbatim cells did not).
- **C-29 M-1's fixtures add two to V03's twelve**: item 6 with the tree check not run, and item 11's links row
  (`links_problems`, which no standing test reached). RP.S06's selection gains `test_rel_standing_acceptances.py -k
  s06_` (`a79399bf`).

### Measured (WO-R7)

- REL.A20 (`--rel-a20` at `ae620ac4`, exit 0): 22 checks, 16 pass, 5 fail, 1 unsupported; same form
  12 of 12 equal S13; RP.S18 `not_pass` 5 (S10, S13, S15, S17, S21), all changed form, commands 29 → `REL.A20: PASS`.
  Controls in `test_rel_a20_over_0_3_0s_committed_records`: a same-form check failing; the same with S13's
  counterpart failing too (A-1's sub-check alone); zero commands — each FAIL.
- M-1 mutation (the five engine readers blanked), `tests/test_rel_standing_acceptances.py`: before 40 passed
  unmutated, 40 passed mutated; after 56 passed unmutated, 6 failed / 50 passed mutated (items 7, 8, 9, 10,
  11 (links), 12).

## REL040 prep (build lane, `wp/REL040p`, 2026-11-09)

### Choices (each isolated in its commit)

- **x05 gate entry** (`c46ef9fc`): V18, the gate that carries L41/R-140 (`docs/reviews/V03-verdicts.md`), gains
  `[4, "x05.*"]` and `tests/test_x05_*.py` — X05 review 5(e) and the logged intent of 2026-11-07. No other gate names
  step 4; `rc_steps` already holds it.
- **RP.L11** (`9743871e`): ADR 0074 O-3's default as RP amendment A-10 (§3.4, §17.3), register R-1007 (RP amendments
  are registered by precedent: A-1–A-8 R-942–R-949, A-9 R-970). `release_gate.release_package_id` encodes D2 itself.
- **The rehearsal's `--rc`**: the runner requires `--rc` inside the checkout (M02's judges read records relative to
  it), so it was `<worktree>/.cache/s6-rc` (git-ignored, not `docs/` or `evidence/`) and was moved to the scratchpad
  work directory afterwards. Step 16's dry run and `--w27-artifacts`' hard links land in the worktree's ignored
  `evidence/M06/W27/artifacts/` by the runner's design; both were removed after the run. Nothing was committed.

### S-6 rehearsal (RP review S-6, ruling 8): `release_rc.py local`, every local step of the 0.4 line

At C = `9743871e` (`main` `612e54a8` + the two commits above), clean, pushed as `wp/REL040p`; 2026-11-09 11:53–14:13
(load 26–29 of 48 cores at start). Not a candidate C; records only in the session scratchpad. Inputs:
`--nlp-prefix`/`--nlp-cache` the `m05` worktree's `.venv-nlp` and `.reference-downloads/m03-ipopt` (0.3.0's);
`--journey 2d945b5d` (0.3.0's J — no 0.4 J exists yet); `--w27-artifacts` the `m06-w27h` archive; `--ci-run
42604498076`, the `release_rc` dispatch at C (read first: `ci.yml` has no write permission, no secret and no
publish; it uploads Actions artifacts only). The dispatch concluded `success` on every job, both legs (dist,
clean-install with the `x05.*` checks, bundle-set/replay, rc-steps, rc-coolprop, rc-ensemble, ptc-r1); the push run
42604498059 `success`.

| Step | Result | First error line / note |
| --- | --- | --- |
| 2 identity | ran, 3/3 pass | |
| 6 ensemble | ran, 7/7 pass | first run of the port |
| 7 corpus | ran, 12/12 pass | |
| 8 surface | ran, 12/12 pass | |
| 9 A30 | ran, exit 0 | |
| 10 certificates | ran, 2/2 pass | audits step 12's kept certificates — first run |
| 11 W22 | **failed**, 2/3 | `a40.idaes_numbers_identical`: differing members `environment.platform`, `inputs.reference_values_yaml_sha256` against the committed IDAES record (`7dc55096…`); a record re-take question, not a runner defect |
| 12 W21 | ran, 6/6 pass; `r375.audit` pass | first run of the port; A-5's inputs read and hash-checked |
| 13 W23 | ran, 3/3 pass | |
| 14 W24 | **failed**, 3/5 | `a60.w24.nlp_tier_and_inventory`: `pytest -m nlp` 211 passed, but the NLP-1 inventory workload raised `TypeError: 'NoneType' object is not subscriptable` (`start["final_decisions"]` is None, `scripts/m03_ipopt_inventory.py` `nlp_1`); `a60.w24.m05_g10_real_replay`: `ReplayDivergedError: replay diverged: a cold execution at {... 'temperature': 673.15 ...}`. `nlp_selection` pass (the `tests/` collection's exit 2 is three `mpmath` imports, not judged, §6.5) |
| 15 W25 | **failed**, 1/3 | `a21.carry_journey` fail as expected (0.3.0's J; files differ since); `a21.check` pass; `a21.replay` `DIFFERS: replay diverged` (the same cold REAL execution as step 14) |
| 16 W26 | ran, 4/4 pass | the dry run's `SnapshotUnsupportedError` (`iapws95-v1`, W27-R63) is the expected v1 refusal (d) |
| 17 items | ran, 7/8 pass | `E01-G6-nlp` fail: the same NLP-1 inventory `TypeError` inside `m03_nlp_check.sh` (its 27 tests pass); `S07-F8`, `PTC-R1` read from the dispatch, pass |

**Runner defects found: none.** Every failure is the checked thing failing, not the port: no fix was made. Three
findings stop here for the design lane (each would change a number or a record, not the runner): (1) the NLP-1
inventory workload gets a start without `final_decisions` at C (passed at 0.3.0 in the same environment); (2) M05's
REAL replay diverges on a cold reactor execution at C (step 14 and step 15's replay), `REPLAY PASS REAL
differences=0` at 0.3.0 — the C7/V03 notes ran it in `alpha-main`'s `.venv-nlp`, this run in `m05`'s, as 0.3.0's
`run_local.sh` did, so the environment is the first thing to rule out; (3) step 11's IDAES record differs from the
committed one in two input/platform members. The 0.4 J must be recorded before step 15 can pass.

## S-6 ruling applied (build lane, `wp/REL040p`, 2026-11-09)

Ruling `docs/reviews/REL040-s6-ruling.md` (A-11, R-1008, WO-1…WO-6). Merged first: `origin/wp/S6dbg` (`fc93285f`, the
NLP-1 inventory fix `3e25b294`, F-A) and `origin/main` (`495cf29a`, docs only).

| WO | Commit | Measured |
| --- | --- | --- |
| WO-1 | `5d862052` | `--old-platform`, class `platform`, pinned fingerprint, archive walk. S6R-01…09 and S6R-10's byte copy (`changed-digests=0`) pass. S77's pair re-run: PASS, 42/80/71/92/38, classes as S78 |
| build decision | `81716c0a` | class `path` (below). S6R-10 on the committed REAL stem: `PASS changed-digests=50 digest=431 timing=0 path=128 version=0 platform=4 other=0 environment=equal` |
| WO-2 | `7a6c3a7f` | `--retake-into`; S6R-20's three refusals pass |
| WO-3 | `cb2a3a6c` | `scripts/m01_idaes_retake_diff.py`; S6R-11…15 pass (11 tests) |
| WO-4 | `4ba52083` | `host_platform`/`record_platform`; S6R-17, S6R-18 pass; S6R-19: step 11/14/15 tests unchanged, 26 passed |
| WO-5 | `4f8deeb2` | A-11 in RP (§4.5, §5.1, §6.1, §6.5, §7.1, §12, §14, §17.4), R-1008, RELEASING; `test_rel_release_gate.py` 60 passed |

**Build decision (isolated in `81716c0a`, for the design lane's review).** Every cold attempt records
`execution.logs.relpaths.{stdout,stderr}` = `experiments/<key[:2]>/<key>/attempts/<n>/child.<name>`, in the archive (96
leaves) and in the coupling records' iterations (32). WO-1 as written classifies all 128 as `other`, so S6R-10 and
S6R-22 fail by construction. Class `path` admits such a leaf, at that constant pattern only, iff every 64-hex run in
the committed text is a `<key[:2]>/<key>` directory whose key has an image under the completed map and the relabelled
text equals the re-take's. Alternative: an amendment that removes the log paths from the walk. Reversible by
reverting `81716c0a`.

**WO-6 (rehearsal at `4f8deeb2`, 2026-11-09 15:18–16:14, load 32–36 of 48).** Outputs: the session scratchpad
(`wo6/retake-real`, `wo6/retake-idaes`, proof logs) and `.cache/s6r/head11/` (git-ignored).
- **S6R-23 PASS.** IDAES re-take (pinned env built by step 11's runner, `IDAES_DATA` as there):
  `IDAES-RETAKE PASS differing=environment.platform,inputs.reference_values_yaml_sha256 platform=1 inputs=1 other=0`.
  Byte-identical to the re-run of `release_rc.py local --steps 11` at the same head, whose
  `a40.idaes_numbers_identical` fails on exactly those two members (S-6 reproduced).
- **S6R-22 FAIL — stopped here (ruling §8 WO-6; RP §12).** The REAL re-take ran to completion (exit 0, 3336 s
  wall, `DECISION_STABLE`, T* = 653.1500351610193, study_cold=48, bijection_violations=0). Proof with `--old-platform
  'Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41'`:
  `RETAKE-DIGEST-ONLY FAIL trust-region-study-real: changed-digests=104 digest=505 timing=528 path=128 version=0
  platform=4 other=0 environment=differs`, problems:
  1. `environment: differs outside distributions_sha256 (['distributions', 'distributions_sha256'])`: 17 → 18. Cause
     measured: this worktree holds a git-ignored `src/openflowsheet.egg-info`, so `PYTHONPATH=src` adds
     `openflowsheet==0.4.0.dev0` to the distributions. Without `src` on the path the nlp env gives 17 and `f775c97d…`,
     the committed digest. The rehearsal worktree was clean by `git status --porcelain`, not by `--ignored`.
  2. `map: e3b0c442… has two images [cace1071…, e3b0c442…]`: one attempt (committed key `b52fe7b3…`, T = 673.65 K,
     re-take key `f2977ba9…`) wrote to stderr (`stderr_sha256` no longer the empty digest). Its startup took 19.7 s
     against 1.7 s committed; its result is equal under the map. The stderr text is not kept. Hypothesis, not
     measured: a numba cache rebuild or warning in the shared reactor `NUMBA_CACHE_DIR` under load.
- **O-1's fact:** no REAL number moved with the kernel (`other=0` over every record, ledger, coupling, store and
  archive leaf), and no IDAES number moved (`other=0`). The proof still fails, on the two lines above.
- Not run (stopped): S6R-24 (J′, steps 11 and 14 with the re-takes), S6R-25 (step 14 negative control); S6R-21's
  file set and `provenance` were not checked as a committed step. Nothing was re-run, edited or committed to pass.

**Tests and gates.** `tests/test_rel_*.py tests/test_release_workflows.py tests/test_evidence_manifests.py` plus the
WO tests and `tests/test_m07_journey.py`: 978 passed, 1 deselected (214 s).

**Questions for the design lane.**
- Q-S6a: the class `path` (`81716c0a`): accept, or remove the log paths from the walk by amendment?
- Q-S6b: should "clean worktree at K3" in A-11 mean `git status --porcelain --ignored` empty (as step 14's nlp tree is
  recorded), or should the re-take run without `src/` on `PYTHONPATH`? Default: a fresh `git worktree add` at K3.
- Q-S6c: is a reactor child's stderr (`stderr_sha256`) part of the identity the proof requires? It is now, as a
  digest leaf. Default: yes, and the rehearsal is repeated from a fresh worktree after Q-S6b to see whether it recurs.

## S-6 WO-6 rerun from a fresh worktree (build lane, `wp/REL040p` at `00f15a01`, 2026-11-09)

Brief `docs/briefs/REL040-s6-rerun.md`; orchestrator defaults pending the design lane: Q-S6a class `path` kept,
Q-S6b clean = fresh `git worktree add` (`git status --porcelain --ignored` empty before the run, checked by the run
script), Q-S6c stderr digest stays in the identity. Same commands and nlp env as WO-6; single process; load 32–35 of
48. Outputs: session scratchpad `wo6-fresh/` (re-takes, proof logs, the RC records `rc-head/`, `rc-jprime/`). A
read-only observer copied any non-empty `child.stderr` out of the run's temporary store: none appeared.
- **S6R-22 PASS.** REAL re-take: exit 0, 3208 s wall, `DECISION_STABLE`, T* = 653.1500351610193, study_cold=48,
  bijection_violations=0. Proof: `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504
  timing=528 path=128 version=0 platform=4 other=0 environment=equal`. Against WO-6: the sidecar is equal (no
  egg-info, 17 distributions) and no attempt wrote stderr (WO-6's 104/505 counted that one attempt's stderr digest).
  S6R-21: the written file set equals the committed one (9 files).
- **S6R-23 (re-confirmed).** Step 11 at the head re-took IDAES; `m01_idaes_retake_diff.py` → `IDAES-RETAKE PASS
  differing=environment.platform,inputs.reference_values_yaml_sha256 platform=1 inputs=1 other=0`; the record is
  byte-identical to WO-6's re-take.
- **S6R-25 PASS (negative control).** Step 14 at the head: `a60.w24.m05_g10_real_replay` fails (exit 1,
  `ReplayDivergedError`), `host_platform` 6.12.113 ≠ `record_platform` 6.12.111; every other step 14 check passes.
  Step 11 at the head: `a40.idaes_numbers_identical` fails on exactly the two members above.
- **S6R-24: the ruling's expectations met, step 14 still fails on another check.** Scratch J′ = `00f15a01` + one
  commit copying both re-takes in (`ac48b042`, local, deleted after). Step 11 passed (`a40.idaes_numbers_identical`
  `differing_members` []). Step 14: `a60.w24.m05_g10_real_replay` pass, `REPLAY PASS REAL differences=0`,
  `host_platform` = `record_platform` = 6.12.113. But `a60.w24.m03_m05_all_tiers` fails: 1 failed, 665 passed —
  `tests/test_m05_retake_digest_only.py::test_s6r10_the_committed_real_stem_retaken_on_another_kernel_passes`
  asserts the committed stem's reactor platform equals the constant `P0` = 6.12.111 (line 279, from WO-1 / `81716c0a`).
  Any J that commits the re-take fails this test, at the RC's step 14 and in CI. Not changed here.

**Question for the design lane.** Q-S6d: S6R-10 pins the committed REAL stem's platform to `P0`. Default: the test
reads P0 from the committed stem's coupling records and keeps P1 a synthetic different platform, so it survives every
cut's re-take; one test-only commit before J. Alternative: J updates `P0`/`P1` alongside the re-take.

### Q-S6d (orchestrator, 2026-11-09)

`test_s6r10_the_committed_real_stem_retaken_on_another_kernel_passes` pinned the committed REAL record's platform to
the constant `P0` (6.12.111), so any J that commits the K3 re-take would fail it. Decision (the engineer's default):
the test reads the old platform from the committed record and re-takes onto a made-up platform `P_RETAKE`; the proof
(`path=128 version=0 platform=4 other=0 environment=equal`) is unchanged. Alternative: J updates P0/P1 with the
re-take. Test-only commit; the design lane confirms with Q-S6a–c.

## S-6 confirmation round applied (build lane, `wp/REL040p`, 2026-11-09)

Ruling `docs/reviews/REL040-s6-ruling.md` §11 (Q-S6a–d confirmed). Briefs `docs/briefs/REL040-s6-wo78.md` and, after a
TRS2 reset, `docs/briefs/REL040-s6-wo78-finish.md`.

| Item | Commit | Measured |
| --- | --- | --- |
| WO-8 (§11.4) | `d7258775` | S6R-12…15 under §8.0's no-host-dependence rule: platform literals made up, asserted ≠ P0 at import; S6R-14's tree-file case sets a made-up stale hash on the committed side |
| WO-7 (§11.3) | `26ad9d7f` | (a) log digests compared exactly, never in the map; (b) `--retake-into` keeps non-empty child logs. S6R-27 (1–3 discriminate against `d7258775`'s tool; 4 pins S6R-10's two lines), S6R-28 |
| A-11 item 7 (§11.2) | `0b62c12d` | verbatim into RP §7.1 and §17.4; `tests/test_rel_release_gate.py` 60 passed |

At `0b62c12d`: `tests/test_m05_retake_digest_only.py tests/test_m01_idaes_retake_diff.py` 50 passed; the default tier
(`pytest -q -rs`, serial) 16007 passed, 3206 skipped, 219 deselected, 3 xfailed, 0 failed (3775 s).

**Re-takes at `0b62c12d` (the WO-6 rerun's outputs were on the session's tmpfs and lost in the TRS2 reset; both were
re-taken, same commands).** Kept git-ignored in the rel040p worktree: `.cache/s6r/real-0b62c12d/` (REAL, proof and run
logs) and `.cache/s6r/head0b/rc/step11/` (IDAES).
- REAL: fresh `git worktree add --detach` at `0b62c12d`, `git status --porcelain --ignored` empty before the run; the
  `m05` worktree's `.venv-nlp` under `env -i` (HOME, PATH, LANG), `OMP_NUM_THREADS=1`, `PYOMO_CONFIG_DIR`,
  `PYTHONNOUSERSITE=1`, `PYTHONPATH=src:<nlp-test-tools>`; `scripts/m05_wo9_real.py --retake-into <scratch>`. Exit 0,
  wall 1915 s, `DECISION_STABLE`, T* = 653.1500351610193, study_cold=48, bijection_violations=0, `child-logs kept=0`.
  The written file set equals the committed one.
- **WO-7 live proof line** (`scripts/m05_retake_diff.py --digest-only <committed stem> <re-take> --old-platform
  'Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41'`, the committed S0 coupling record's platform), with WO-7 (a) in
  the tool: `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504 timing=528 path=128
  version=0 platform=4 other=0 environment=equal` — byte for byte the WO-6 rerun's (G1) line.
- IDAES: `release_rc.py local --line 0.4 --steps 11` at `0b62c12d`; the record is byte-identical to WO-6's
  (`76068ff5…`); `a40.idaes_numbers_identical` fails on `environment.platform`, `inputs.reference_values_yaml_sha256`
  (expected at the head); `m01_idaes_retake_diff.py` → `IDAES-RETAKE PASS
  differing=environment.platform,inputs.reference_values_yaml_sha256 platform=1 inputs=1 other=0`.

**S6R-29 (§11.4): FAIL on item 3 — stopped here for the design lane.** J′ = `0b62c12d` + one local commit copying both
re-takes in (`f056d72f` on `scratch/s6r29j`, fresh worktree; never pushed; deleted after).
1. Made as S6R-24 did; 9 files changed (8 REAL record files, the environment sidecar equal; the IDAES record).
2. PASS: the two modules 50 passed at the head and 50 passed at J′, same test ids.
3. **FAIL**: the default tier at J′ (serial, 3818 s): 3 failed, 16004 passed, 3206 skipped, 219 deselected, 3 xfailed.
   Same 19216 test ids collected at both (one id differs only by an object address in its repr,
   `test_t07_w2d_noncanonical…_RepeatedKeys object at 0x…`). The only status changes, pass → fail:
   `tests/test_m07_journey_record.py::test_a21_a_re_run_names_the_offered_m05_record_tracked_with_its_sha256`
   `[2c508b5]`, `[2d945b5]`, `[974c395]`: `assert sha256(benchmarks/m05/records/trust-region-study-real.json) ==
   offered["sha256"]` — `55c36974…` (J′) ≠ `09cf5366…` (committed, and named in those three committed M07 journey
   records `benchmarks/m07/journey/<C>/journey.json` and in M05's manifests `56fb2fac`, `cfecb15a`). Not a host test as
   such: A2.3 (R-454) binds each committed journey record to the current bytes of M05's REAL record, so any J that
   commits the REAL re-take fails these three in CI's default tier. Step 14 (`m03_m05_all_tiers`) does not run this
   module, which is why S6R-24 did not see it.
4. J′ deleted (worktree and branch).

**O-6's answer (§11.7): yes, one more module.** Beyond WO-8's module, `tests/test_m07_journey_record.py`'s A2.3 test
(3 parametrizations) depends on the committed REAL record. Not changed here (brief: no fix without the design lane).
Question for the design lane, Q-S6e: how does A2.3 read a committed journey's `offered` once J replaces the record it
names — e.g. check `tracked_unmodified` and the sha256 against the file at the journey's own commit (`git show
<C>:<path>`) rather than the working tree — and does J carry that test change before K3? Default (not applied): the
historical reading, test-only, one commit before J, under §8.0's rule.

### Q-S6e (orchestrator, 2026-11-09)

S6R-29 found `tests/test_m07_journey_record.py::test_a21_a_re_run_names_the_offered_m05_record_tracked_with_its_sha256`
(cases `2c508b5`, `2d945b5`, `974c395`) hashing the working tree's `trust-region-study-real.json` against each committed
journey's `offered.sha256`, so a J that commits the REAL re-take fails it. Decision (the engineer's default): the test
reads the offered file as tracked at the journey's own `commit` (`git show <commit>:<path>`; CI checks out full
history) and checks its sha256 and anchor from that blob. Proof: the module passes at head (56 passed) and with the
working-tree REAL record altered (56 passed). Alternative: J rewrites the three journey records. Test-only commit; the
design lane rules on it in this package's `reviewer` pass.

## REL040 review fix round (build lane, `wp/REL040p`, 2026-11-10)

Brief `docs/briefs/REL040-fix-R1.md`; authority `docs/reviews/REL040-review.md` (S-1, WO-R1; N-1, N-3, N-5).

| Item | Commit | What |
|---|---|---|
| WO-R1 | `5b8575a4` | `--digest-only`: `.inner.state_sha256`, `.inner.constants_sha256`, `.requests[<n>].inputs_sha256` compared exactly, never in the map; a difference is other, "(a value digest is compared exactly)". Tests: each moved alone → FAIL `other=1` naming the leaf (3 cases); every inner state moved one-to-one → FAIL `other=4`; relabelled stems with equal value digests pass. The 4 moved cases fail at `5d0c4121` (the tool passes them) |
| N-1 | `cfa46e70` | Q-S6e test asserts `git merge-base --is-ancestor <commit> HEAD` before `git show`; docstring notes full history. A dangling child of HEAD gives rc=1 |
| N-3 | `c95288f4` | `--old-version` beside a coupling pair whose fingerprint holds the platform is other (A-11's `environment=equal`). New test fails at `5d0c4121` |
| N-5 | `a385a417` | `m05_wo9_real.py`: `keep_child_logs` in a `finally`, so a re-take that raises keeps its logs. New test (stubbed run that raises) fails at `5d0c4121` |
| N-4 | — | Not done (brief): step 15 still chooses the M05 record by directory; equivalent for the three committed journeys |

**§2's claim, qualified (WO-R1 (d)).** The REAL digest-only proof holds the clear leaves bitwise and the log and value
digests (`execution.logs.{stdout,stderr}_sha256`, `inner.{state,constants}_sha256`, `requests[].inputs_sha256`)
exactly; every other digest (keys, request and record digests, code and input identity) is held only to a bijection,
with the clear leaves as its guard, so the proof establishes that nothing moved except the platform string at its one
bound leaf and digests of that kind.

**Lines that must not change (measured at `a385a417`).**
- Live REAL proof on `.cache/s6r/real-0b62c12d/` (`--old-platform 'Linux-6.12.111+deb13-amd64-x86_64-with-glibc2.41'`):
  `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504 timing=528 path=128 version=0
  platform=4 other=0 environment=equal`, byte for byte.
- S77's pair (`git archive 56fb2fa~1` vs `56fb2fa`, five stems, no options): PASS 42/80/71/92/38, digest/timing
  150/20, 327/35, 219/20, 288/26, 128/20 (as S78), `path=0 version=0 platform=0 other=0 environment=equal`.
- S6R-10's two lines: pinned by their tests, which pass.
- The review's S-1 demonstration (the live re-take with its 16 `inner.state_sha256` moved to distinct values): at
  `5d0c4121` `PASS changed-digests=119 … other=0` (the review's line); at `a385a417` `FAIL changed-digests=103 …
  other=16`.

**Tests (serial, `OMP_NUM_THREADS=1`).** `tests/test_m05_retake_digest_only.py tests/test_m01_idaes_retake_diff.py
tests/test_m07_journey_record.py tests/test_m05_wo9_gates.py tests/test_rel_*.py`: 326 passed, 3 deselected. F0 PASS
(M1 50/50 … M9 35/35). `ruff check`, `ruff format --check` clean. No manifest, no merge.

## 0.4.0 cut (build lane, wp/REL040, 2026-11-10)

- Part 1 commits: 44653f94 (prep manifest to S15b), 9eceb3aa (harvest S13; HARVEST_EXCLUDED REL040), K3 49a0473119a7684ddf44bdf3c59528714f49337a.
- S13 classification: limitations[0-8] class P (provenance/process/release-candidate notes), limitations[9] class E to
  L-S11-1..3 and L-E01-1 (rows it names). 0 non-pass checks. No scientific judgement needed.
- K3 also touched: t08_support_matrix.ENVELOPE_ID (as 295a2e65), the pair in tests/test_m07a_v0_2_gate.py's loop, README status
  (names 0.4.0; the table and prose below are the docs pass's).
- OPEN (stop): tests/test_rel_evidence_manifest.py::test_rel_a20_over_0_3_0s_committed_records fails from 9eceb3aa on
  ("RP.S22 same form: fail; S13 test pass: DIFFERS"): _m_harvest reads the live HARVEST_EXCLUDED, now the 0.4 tuple, for the 0.3 line.
  Not a version failure; no expectation edited.

### Part 2: the re-takes (J) and the journey at J (brief docs/briefs/REL040-j.md)

- Run tree: `git worktree add --detach .claude/worktrees/rc-k3-040 49a04731`; `git status --porcelain --ignored`
  printed 0 lines at 08:32 before the first re-take (host kernel 6.12.113). Outputs and logs: `~/.cache/rel040-cut/`.
- Re-takes, in parallel (7 single-threaded processes; load 16–19 of 48 at start): the five G10 records by E6/K's
  recipe, one process per case (`run_case` + `write_files` into `~/.cache/rel040-cut/g10`; driver
  `~/.cache/rel040-cut/bin/g10_case.py`), 4–7 s each, every record `run_commit` 49a04731, `tree_clean` true;
  REAL `scripts/m05_wo9_real.py --retake-into`, exit 0, 2110 s, DECISION_STABLE, T* = 653.1500351610193, study_cold
  48, `child-logs kept=0`, written file set equal to the committed one; IDAES in 8 s.
- DECISION: IDAES env → `~/.cache/of-rc-v03-a3e508e/idaes-wt/.venv-idaes` (0.3.0's RC step-11 env), run as step 11
  runs it (`-I`, PYTHONPATH unset, OMP/OPENBLAS/MKL 1, IDAES_DATA). Its sorted `pip freeze` sha256 dfeec96f… equals
  S-6's step-11 freeze; the record is byte-identical to S-6's (76068ff5…). Alternative: build a new env with
  `build-reference-envs.sh idaes`. Reversible by: re-taking in a new env.
- Proofs (all exit 0):
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-tr-e2-far: changed-digests=79 digest=320 timing=35 path=0 version=7 platform=0 other=0 environment=equal`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-tr-e2: changed-digests=41 digest=146 timing=20 path=0 version=4 platform=0 other=0 environment=equal`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-loop-s: changed-digests=37 digest=124 timing=20 path=0 version=4 platform=0 other=0 environment=equal`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-real: changed-digests=103 digest=504 timing=528 path=128 version=0 platform=4 other=0 environment=equal`
  - `IDAES-RETAKE PASS differing=environment.platform,inputs.reference_values_yaml_sha256 platform=1 inputs=1 other=0`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-loop-r: changed-digests=91 digest=285 timing=26 path=0 version=3 platform=0 other=0 environment=equal`
  - `RETAKE-DIGEST-ONLY PASS trust-region-study-tr-e2-fd: changed-digests=70 digest=215 timing=20 path=0 version=4 platform=0 other=0 environment=equal`
  Version leaves 4/7/4/3/4 as 0.3.0; IDAES input hashes equal the K3 files' SHA-256.
- **J = e0a3d6b78f9d245ff8ed946ae954a9682f3e24c2**: 45 files (44 under `benchmarks/m05/records/`: written/changed
  TR-E2 8/7, TR-E2-FAR 11/10, TR-E2-FD 8/7, LOOP-R 7/6, LOOP-S 8/6, REAL 9/8; the IDAES record). At J: `-m nlp
  tests/test_m05_g10_replay.py` 5 passed; `tests/test_m05_*retake*.py tests/test_m01_idaes_retake_diff.py
  tests/test_m07_journey_record.py` 112 passed, 3 deselected.
- Journey: clean detached worktree `rc-j-040` at J (`--porcelain --ignored` 0 lines), m05's `.venv-nlp`, env -i,
  OMP 1, PYOMO_CONFIG_DIR, PYTHONNOUSERSITE=1, PYTHONPATH=src, `--m05-record
  benchmarks/m05/records/trust-region-study-real.json`, budgets unchanged. Exit 0, 4670 s. refined, T* =
  653.1500351610193 K BOUND_LOWER, J = 0.4524965242483627; R0 INDIFFERENT, R1 DECIDED 653.15 (cold 36, 2252 s), R2
  SURROGATE_NOT_PROMOTABLE, R3 DECISION_STABLE (re-run, carry_identity_differs from anchor 49a04731; cold 48, 1970 s).
  - DECISION: PYOMO_CONFIG_DIR set for the journey (the brief's nlp env; 0.3.0's step 3 did not list it). No leaf
    beyond the allowed classes moved. Reversible by: re-running the journey without it.
- **C (proposed) = b40d48d10fac41f807a2e195ee6102bfdebac5e8**, the record under `benchmarks/m07/journey/<J>/` (12
  files). `check`: ACCEPT. `replay` in a clean worktree at C (`rc-c-040`, 0 lines): bitwise, 26 s;
  `OMP_NUM_THREADS=2` exit 2. `v0_2_gate.journey_carry(J, C)`: carried. `tests/test_m07_journey_record.py` at C:
  73 passed, 4 deselected.
- Against 0.3.0's record at 2d945b5d: 71 of 10794 leaves differ, all in the allowed classes — walls (R0/R1 grid
  wall_s 9+9, budget spent R0/R1/R3, accounting R0/R1/R3/journey/t_star_resolve, R3 t_star_resolve), digests
  (coupling_sha256 in R0/R1 grid and artifacts 9×4, R3 candidate coupling_record_sha256, parent_checks R3/journey
  run_sha256), `commit`, and R3's `m05_record` (path, sha256, offered.sha256, offered.anchor). Every other number
  bitwise equal; no platform string is a leaf of journey.json. No stop.
- Peak load seen: 31 (1-min, 10:27, other work); this work ≤ 7 threads.
