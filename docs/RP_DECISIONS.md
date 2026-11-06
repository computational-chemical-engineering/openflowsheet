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
