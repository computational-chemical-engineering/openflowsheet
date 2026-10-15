# V02 alpha gate (M07a) build-lane decisions log

Open choices the build lane made while executing `docs/derivations/V02-alpha-release-spec.md` §15, for the design-lane
read of WO-5 and WO-8 (spec §15, "Design-lane steps"). Each names the commit that carries it and the alternative.

## WO-5 (step 8, the surface chain; commit `b44f684`)

B-WO5-1 **D_2, c_2's registered digest.** §15 makes WO-5 depend on "link c_2 registered" at M02's merge; no register
entry or committed constant pins it (R-234 says "M02's digest is registered at the merge commit"; the M02 manifest at
`ba90619` records `383b4e2c…` as evidence, "not a pin"). Chosen: `scripts/m07a_rc.py` `LINKS[1].digest` =
`383b4e2c004810663a3e3f80c591730bc95894e35736619eacac0f51e51b5403`, measured on this branch's merge of `main`
(`46176a7`, `harness.tool_descriptions_sha256()`), equal to the manifest's `served_sha256`; the test holds it equal to
that manifest value and the manifest's `without_m02_sha256` equal to D_1. Alternative: a register entry (design lane)
naming D_2, which the constant would then cite. Needs: the design lane to register it (or name another value).

B-WO5-2 **Where step 8 lives.** A new `scripts/m07a_rc.py` with one subcommand, `surface` (record
`rc-alpha-surface.json`, step `surface-alpha`, `t08-rc-v1` format via `t08_rc.finish`). CI's `rc_alpha` runs every
other step through `t08_rc.py` unchanged. Alternative: an `m07a_rc.py` that re-exports all of `t08_rc`'s subcommands.

B-WO5-3 **G16-b loop restated.** `t08_rc.step_surface`'s G16-b loop is copied into `m07a_rc.g16b` (check id
`a37.g16b_clean`), because factoring it out would edit the 0.1 step, which §15 forbids. Alternative: refactor
`t08_rc.py` (rejected by the spec's "unchanged").

B-WO5-4 **Item 3 by substitution.** `v17-c2`'s two texts are substituted into the stripped, dumped tool list rather than
re-served through `mcp.description`; equivalent because each served description is its file byte for byte (asserted by
`served_texts_are_the_files` and by `test_m02s_surface_move_decomposes_onto_the_base`).

B-WO5-5 **R-133's file hashes.** Item 4's "whose files equal R-133's" has no registered number. Chosen: the two
reviewed hashes in `REVIEW.json` at `PUBLIC_ROOT` (v0.1.0), restated in `R133_FILE_SHA256` and tested against
`git show PUBLIC_ROOT:…/REVIEW.json`.

B-WO5-6 **Control readings.** (i) the added member also fails item 1 (the served digest is not D_2); "fails at link
m" is read as the first failing row being link m's. (ii) "one member too many" is `get_project`'s `head` removed after
`without_m02`. (iii) one byte of `list_jobs.md`, judged on `description_problems` (texts passed in, not written to
disk). (iv) s_1 replaced by the identity.

B-WO5-7 **CI gating.** `rc_alpha` joins `rc` in the `if` of `dist`, `bundle-set`, `rc-steps`, `rc-ensemble`
(`clean-install` and `bundle-replay` follow by `needs`); in `rc-steps` the 0.1 surface step is now `if: always() &&
inputs.rc` and the alpha's `if: always() && inputs.rc_alpha`. The `rc` path's behaviour is unchanged.

## WO-8 (the harvest of T08's manifest; commit `e808406`)

The E/S/P/B classification is a design-lane read (spec §15, as T08.A21's was). The draft, item by item, in
`benchmarks/t08/support_envelope.yaml` (T08 manifest `67c66d98…`):

B-WO8-1 **Restated rows.** `limitations[12..57]` are T08's restatements "Lxx: …" of envelope rows; each is E to its own
row (46 items). Alternative: P (they duplicate the envelope).

B-WO8-2 **V14 (b).** `limitations[2]`, `checks[42]` (T08.A70) and `checks[67]` (T08.B23) are E to L01 (precedent:
T04 `limitations[11]`). Alternative: also carry B8 (PTC-R1 qualification) as a second pointer.

B-WO8-3 **E with a judgement.** `[5]` (A45 under policy v2, pivot paths not compared) E L07; `[11]` (bitwise,
portability) E L07, L15; `[7]` (V19 feasibility) E L42, since the shipped `pr-c1-v1` row now carries the user-facing
remainder (vapour-only light gases, no mixture VLE validation, k_ij = 0). Alternative for `[7]`: S to M01's
`check:M01.A38`–`A40` (K_NH₃ pinned by R-152, property values chosen by M01).

B-WO8-4 **P.** `[0]` evidence class (precedent T07, M06 P; T06 chose E L18), `[1]` verdicts outside the schema,
`[3]` test provenance, `[4]` §A4.6 attestation, `[6]` B50 amended by Frank, `[8]` library-only (no envelope row or
backlog id names it), `[9]` A34's scope at T08's RC (MR-11 widens A34 for the alpha but not to replays), `[10]` RC
record storage. Questions: should `[8]` become an envelope row, and `[9]` a backlog id?

B-WO8-5 **The v0.1 size quote.** `test_a21_every_item_is_classified_once_and_resolves` filtered manifests by first
letter P/K/T, which now admits T08; it is scoped to exclude `evidence/T08/`, matching its comment ("18 manifests of
P00–T07"). Alternative: move the quote to `t08_reference.py`'s `HARVEST_PACKAGES`.

B-WO8-6 **Size and the matrix now.** `HARVEST_SIZE = (23, 316, 29)` is the tree's size today; WO-10 re-reads it at
`C_α` and M07a's manifest quotes it. `docs/support-matrix.md` is re-emitted now because T08.A23 requires it to match
the harvest; WO-10 re-emits it again after the `C_α` pin of `envelope_id` and `release` (not done here).

## After the design-lane read (F1, F2, F4; R-320, R-321) and WO-10

B-F1-1 **How the A50 test finds `C_α`** (`a5b37a3`). The commits named as `C_α` are the `## v0.2.0a1` heading's (once
its marker is gone) and the directory name of every `evidence/M07a/<sha>/manifest.json`; for each, `git ls-tree -r
<sha> -- evidence/M07a/` must be empty. With none named, no M07a manifest may exist. Reason: the heading keeps its
marker until the verdicts (it is pasted with the gate table), while M07a's manifest is written right after `C_α`.
Alternative: the heading alone (the test would be red from the manifest commit to the verdicts).

B-F2-1 **M07a is never a review-table row, in both modes** (`5882a2c`). R-320 says (g) reads `C_α`'s tree once the
heading names it; until then it reads the working tree, which from WO-10's manifest commit holds M07a's manifest.
`NOT_A_ROW = ("M07a",)` applies in both modes (at `C_α` it excludes nothing). The third column is derived from
`review`: `pending`, or `signed <first ISO date> (R-017)`. Alternative: exclude only in working-tree mode.

B-WO10-1 **M07a.A10's fixture (b) at the cut** (cut commit). `test_a10_the_envelope_must_be_pinned_to_the_alpha` used
the real working envelope as "today's file" (dev id). At `C_α` the file is pinned, so the test undoes the pin on the
real file's text (two line replacements) and asserts the dev id before using it. Alternative: `git show` of a pre-cut
commit (fails on a shallow CI checkout).

B-WO10-2 **`t08_support_matrix.ENVELOPE_ID` follows the pin** (cut commit). The script holds the file's id
(`v0.2-envelope-dev`, R-193), so MR-3's "T08.A20–A24 at `C_α`" needs it set to `v0.2-alpha-envelope-1` in the cut;
the first D2.4 change after the tag returns both. Alternative: accept either id (weakens A20–A24).

B-WO10-3 **W27's `coverage.json` re-taken at the cut build** (cut commit). `test_committed_coverage_json_is_g14_…`
compares the live registry snapshot with the committed one except `git_commit`; the version bump changes
`package_version`. Re-taken with `python -m benchmarks.m06.w27.coverage` (precedent `fc54944`, the M02 join), and
`docs/m06-w27-coverage.md` regenerated (`report --check` OK). Rows and summary unchanged; `registration_sha256` also
moves (`14ff19d9…` → `ba627342…`), because registration Amendment 3 (`b3216dc`) landed after the last re-take; G14
PASS. `dry_illustration.json` not re-emitted (precedent). Alternative: drop `package_version` from the comparison.

B-WO10-4 **Version-carrying files at the cut.** `pyproject.toml`, `src/openflowsheet/__init__.py`, the two
`project_summary` fixtures (as the 0.1.1 bump `752864f`), and `tests/test_m06_w27_coverage.py`'s live
`package_version` assertion. `tests/fixtures/schemas/experiment_coupling/*` (`openflowsheet_version: 0.1.1`, a
recorded run's provenance) and `tests/web/frame.test.mjs` (a stub server's `0.2.0.dev0`) are not version carriers.

B-WO10-5 **Gating in a snapshot worktree.** Each gate runs `scripts/gate.sh` in a detached scratch worktree at
`HEAD` + the named paths' working content (`git commit-tree` on a temporary index), and the commit is made from
exactly the gated tree (`git read-tree <tree>`), so the next change can be prepared while a 23–32 min gate runs.

B-WO10-6 **Step 12's certificates for step 10 (F7).** `benchmarks/m02/g12_real_loop.py` solves in a
`TemporaryDirectory` and keeps only `certificate_sha256`; no step-12 certificate file survives, and `benchmarks/` is
frozen at `C_α`. Chosen: run the script unchanged through a wrapper outside the tree
(`<scratch>/rca-e0e198e/g12keep.py`) that replaces only the module's `tempfile.TemporaryDirectory` with a kept
directory (`…/rc/step12/g12-bundles`, `g12-edges-bundles`), so `t08_rc.py certificates` can audit the bundles'
`solution-certificate.json`. G10 and G11 emit no certificates. Alternative: an `m07a_rc.py` subcommand reimplementing
the solve (duplicates frozen code). **Question for the design lane:** is this wrapper an acceptable "step 12's output"
for MR-11, or should step 10 audit only the hashes the record carries?

B-WO10-7 **Step 11's IDAES environment, second build.** The first `build-reference-envs.sh idaes` failed `pip check`
because the session's `PYTHONPATH` (the RC worktree's `src`) leaked into the build (openflowsheet 0.2.0a1 seen with
missing deps). Rebuilt in the same throwaway worktree at `C_α` with `env -u PYTHONPATH` and a system `PATH`; no input of
the check changed. Both attempts' logs are kept (`step11-idaes-env.log`, `step11-idaes-env-first-attempt.build.log`).

B-WO10-8 **Steps 11 and 12 get `t08-rc-v1` records from outside the tree.** M01's and M02's scripts write records
without `commit` or `tree_clean`, and M07a.A43 needs both on every record of steps 1–12. Chosen: a script run from
outside the tree against the RC worktree at `C_α` (`evidence/M07a/<C_α>/tools/m07a_rc_external.py.txt`, committed with
the records) judges each step by the rules the M01 and M02 manifests already use — M01's `_idaes` comparison (only
`inputs.*_sha256` may differ) and `scripts/m02_evidence_manifest.py`'s `g10`, `g11`, `g12`, imported, not restated —
and writes `step11/rc-step11.json` and `step12/rc-step12.json` through `t08_rc.finish`. Alternative: an `m07a_rc.py`
subcommand (a change to the tree after `C_α`; `scripts/` is outside D2.4, but the RC job would then not be `C_α`'s
code). Reversible by: deleting the two records and their rows.

B-WO10-9 **M07a's manifest `requirements`** = T08's four (`D04`, `A10`, `D17`, `D20`): the alpha re-runs T08's
acceptance at `C_α`. Alternative: add M02's `D10` (W21). Reversible by: the generator's `REQUIREMENTS`.

B-WO10-10 **M07a.A43's machine class (question for the design lane).** `scripts/t08_rc.py`, which steps 1–10 run
unchanged (§8.2), writes no `machine_class` into its steps 3, 4 and 10 records (dist, install, lock, certificates:
13 records); they carry `architecture` and `github_actions`. T08.A16 judged only `commit`, `tree_clean` and the lock
(campaign records). Chosen: the generator judges A43 strictly (all four fields), so A43 is `fail` with the 13
records listed; `tests/test_m07a_rc_records.py` pins that set so a change is seen. **Question:** does A43's
"machine class" mean T08.A16's campaign-record scope, or (architecture, CI) for the fresh-runner steps — or must
those steps re-run with the class recorded? Reversible by: the generator's `_m_provenance`.

B-WO10-11 **Second-session re-runs.** The first session's scratch (`/tmp`, a tmpfs) was lost with its venv, reactor
environment, logs and the step-12 wrapper, while step 12 was still running. This session rebuilt the RC venv
(`requirements.lock` as CI installs it, then `pip install --no-deps -e` the RC worktree), the reactor environment
from `C_α`'s lock (verified), the cross-check venv (the script's five pins) and the IDAES environment (a throwaway
worktree at `C_α`, `env -u PYTHONPATH`), all under `~/.cache/of-rca-e0e198e/` (outside every repository), and re-ran
steps 11, 12 and local step 10 in full (`tools/run_local.sh`). The first session's step-11/12 outputs are kept
apart under `artifacts/first-session/`, not cited. Steps 2, 6–9 (local) and the CI run were not re-run: their
records survived in the RC worktree's ignored `artifacts/rc/`.

## WO-10 status (2026-10-15, second session)

`C_α` = `e0e198e4632224612671db5b07445639d272d6da`; tree record `259af65`. RC worktree `.claude/worktrees/rc-e0e198e`
(clean, detached at `C_α`); its git-ignored `evidence/M07a/<C_α>/artifacts/rc/` holds every record; environments,
logs and scripts under `~/.cache/of-rca-e0e198e/` (the scripts and the summary are also committed under
`evidence/M07a/<C_α>/tools/`).

- Steps 1–10 on CI: dispatch run **38667458248** (`rc_alpha`, `rc_distribution`) success, every RC job success; push
  run **38667452347** success. Artifacts and RC job logs downloaded.
- Local `ref-x86-64`: step 2 PASS, 6 PASS, 7 PASS, 8 PASS, 9 PASS (first session); step 11 PASS (3/3: cross-check
  exit 0; IDAES re-run identical except `inputs.reference_values_yaml_sha256`); step 12 PASS (6/6: G10v3, G11v3 (V5),
  G12 CONVERGED / VERIFIED, `reproduce` MATCH, live rerun bitwise, edges, 562 M02 tests with the reactor).
- **Step 10 local FAIL (F1, spec Q5):** 77 certificates audited, 5 violations, all step 12's coupled-route
  certificates, `a09.qualified_check_ids` — 25 qualified ids where the rule expects 21; the extra four are
  `EXT-COUPLING:reactor:T`, `EXT-COUPLING:reactor:xi`, `derivative_witness.on_pattern`, `.off_pattern`. Q5's default:
  V18 (b) `FAIL` at `C_α`, escalated; the rule is not narrowed. **Question for the design lane:** is the A34 rule's
  "exactly the prefixed checks" right for coupled-route certificates (the extra qualifications look legitimate:
  external coupling and derivative witnesses), or is the certificate wrong to qualify them?
- Records: `docs/v02-alpha-rc-record.md`, `evidence/M07a/<C_α>/rc/` (56 records, `records.json`),
  `tests/test_m07a_rc_records.py`, `scripts/m07a_evidence_manifest.py`; the manifest is generated after these commit.
- Step 13 not run: it needs `docs/reviews/V02-alpha-verdicts.md` (pending, not failed).

## Amendment 2 build-lane actions (spec §18.5 items 1–2; R-345, R-347)

B-AM2-1 **R-345 as built (action 1).** `application/coupled_run.py`'s `_check` writes
`independence_qualification=None` (its `reproducibility` parameter, used only for the old note, is dropped; the class stays in
the `external_model` limitation); `verify/checks.py`'s `derivative_witness` writes no note (the `skipped`/`note` lines go,
the docstring and `witness_skipped_columns`'s say the exclusion lives in `derivative_witness_partial` only).
`certificate.py` unchanged. New `tests/test_a09_qualification_field.py`: Am2.1–Am2.3 at S1 (K05's `run_session` on
SYN-001 nominal), S2 (M02 WO-8's V1, 5 skipped columns, as D43) and S3 (`C1-LOOP-M02-v1` with `standin-x025-v1` in
process), each precondition asserted; Am2.4 (a) monkeypatches `coupled_run._check` to restore `external model, R1` at S3,
(b) wraps `checks.derivative_witness` to restore the old note at S2: Am2.1 and Am2.2 then return exactly the restored ids,
and S1 still passes. On the pre-fix code the new file fails 3 of 5 (S2, S3, and (a), because S3 also carries the witness
entries), the two M02 tests below fail, and (b) passes, as it should. M02 tests edited (§18.4 item 1 (a)):
`test_m02_wo8_verifier.py::test_the_witness_does_not_difference_exactly_zero_pr_flow_columns` (the expected note becomes
`None`, docstring), `test_m02_wo10_coupled.py::test_r3_an_out_of_process_coupled_run_is_r3_and_its_checks_say_so` (`{None}`,
and R3 asserted on the `external_model` limitation instead).

**Am2.5, measured at ab80ca5 + the change.** (i) G2 (ii): `scripts/m02_g2_corpus.py` — 50 revisions, 44 certificates,
file sha256 `659748576adb97300a3b1022ddf30d504a37a8c8ed4b6d6a8506b2c40c16c16d`, text sha256 `20004c0aa707…b39e7`: byte-identical
to D39/D43. (ii) K05 identity: `scripts/t08_rc.py identity` PASS — `a42.minus_t07_registered` (R-149's `24af004a…`),
`a42.t07_key_substituted`, `a42.unchanged_under_trial_version`. (iii) Every `pr-c1-v1` revision the tests register (M02's
5-revision C1 corpus and WO-8's 6 region flowsheets) solved through the application at ab80ca5 and with the change:
`solution-state.json` bytes identical in all 10 that solve, outcomes and verdicts identical; certificates changed in 9,
each carrying `derivative_witness_partial` (the loop also `external_model`), and in each the only difference is the
scoped checks' `independence_qualification` and their entries (F1/F11/F4/V1 12→10, mixer 7→5, zero 4→2, WO-8 loop
20→18, coupled loop 25→21); `C1-HEATER-M02-v1` (no skipped column) is unchanged; `C1-REACTOR-M02-v1` ends
`EVALUATION_ERROR` without the reactor environment at both commits. The run manifests and attempt records differ
in the changed and the unchanged runs alike (run-time metadata and recorded code identity, not solve numerics). Q-A2-2's answer: nothing outside the two scoped
certificate classes moves. (iv) Committed fixtures that move: none — no tracked file outside `docs/` contains either old
note (`git grep`), and `C_α⁰`'s evidence is not regenerated.

B-AM2-2 **R-347 as built in `scripts/t08_rc.py` (action 2).** `install-check`, `lock-check` and `certificates` pass
`provenance={**provenance(), "machine_class": machine_class()}` to `finish`, the pattern steps 5, 8 and 9 already use;
in `install-check` the call is in the `finish` arguments, after every check, so the checkout's harness is imported
only after the clean-install checks have run. No constant, check, judgement or `format` id changes. Tests: the
`lock-check` end-to-end test (`tests/test_t08_r3_a19_lock_lookup.py::test_the_three_states_end_to_end`) now asserts the
member on both states (no test pinned these records' key sets, so this is the extension); new
`tests/test_v02a_r347_machine_class.py` runs `certificates` in process and `install-check` as CI does (another
interpreter, outside the checkout, the package copied out of the tree) and asserts the member equals
`t08_rc.machine_class()` and, on a registered host, agrees with `architecture` and `github_actions`.

B-AM2-3 **`t08_dist.py`'s CI jobs install the lock (choice; isolated commit).** §18.3 assumed the member is "computed
by a function the same script already calls"; `t08_dist.py` is stdlib-only and runs in a bare `setup-python`
interpreter (ci.yml `dist`, release.yml `build`), where `benchmarks.t06.ensemble` (numpy, scipy, yaml, and the
package through `generator.py`) cannot be imported. Chosen: `t08_dist.machine_class()` appends the checkout's
`scripts/` and `src/` to `sys.path` and returns `t08_rc.machine_class()`; both jobs gain one step,
`python -m pip install -r requirements.lock`, before the script. The two builds run in their own venv
(`build_environment`), so the artifacts and every A43 check are unaffected. Alternatives: a stdlib re-derivation
of the class in `t08_dist.py` (rejected by §18.3: a second derivation rule can drift), or a fallback value when
the import fails (a record without a computed class). Reversible by reverting that one commit (the dist record
then has no member and A43 fails on it at `C_α¹`, as at `C_α⁰`). Not exercised end to end here: a dist build
needs the network (`pip install setuptools`); the test pins the function only.

B-AM2-4 **The M07a generator and its test (action 2, post-candidate files).** `scripts/m07a_evidence_manifest.py`'s
`_m_provenance` now also fails a class that is not a key of `ensemble.registered()["machine_classes"]`
(`unregistered_machine_class`) or that disagrees with the record's `architecture` (the dist record: `machine`) or
`github_actions` where the record carries them (`machine_class_disagrees`); two tests on constructed records cover
pass and the three failures. `tests/test_m07a_rc_records.py` still reads `C_α⁰`'s records (`RC` = `e0e198e`, kept
untouched until action 7), so `NO_MACHINE_CLASS` keeps its 13 entries, now commented as `C_α⁰`'s: it becomes empty
when `RC` moves to `C_α¹` in action 6. The class test also checks agreement on the 16 records that carry a class
(all agree). Measured at `C_α⁰` with the new generator: A43 `fail`, 29 records, 13 without a class, 0 unregistered,
0 disagreeing, 0 unattributable — the same verdict as before. These two files are not part of `C_α¹`'s tree
(§18.4 item 1); the R-345 and R-347 commits carry no post-candidate file, so action 4 can cherry-pick them.

## Amendment 2 build-lane actions 4–7 (spec §18.5; R-348, R-349) and the action-3 read's items

B-AM2-5 **Review S3 checked before the cut.** ci.yml dispatched with `rc_distribution` at the action-3 tip `eb108c4`
(run **38768575677**): `dist`, both `clean-install` jobs, `bundle-set` and both `bundle-replay` jobs success. Their
records carry the class: `t08-a43-dist.json` `machine_class` `ci-x86-64` beside `machine` `x86_64` (lock-only
interpreter, step 3); `install-*`, `lock-checkout-*`, `lock-installed-*` and `certificates-*` carry `ci-x86-64` /
`ci-aarch64` agreeing with `architecture` and `github_actions: true` (wheel-only clean venv, step 4). No fix needed.

B-AM2-6 **How `C_α¹` was cut (action 4).** A new branch `wp/V02-alpha-rc1` from `e0e198e`, carrying ab80ca5, 04e65be,
00acbe9 and f0cfda8 cherry-picked with `-x` (no conflict); the last one's subject is rewritten to name the cut, its body
kept. `C_α¹` = its tip **`6fec82232e1c47308a5e1d67338058f352992800`**. `git diff --stat e0e198e 6fec822`: 14 files, as
the read's simulation; on `src/ tests/ scripts/ .github/` the tree equals `2e778d3` except the two post-candidate files.
Gate at `C_α¹`: PASS, 8574 passed, 33 skipped (22:40). Why a branch: a dispatch needs a branch ref whose tip is `C_α¹`,
and `wp/V02-alpha-gate` already holds post-candidate commits (C_α⁰ was dispatched when that branch's tip was it). The
branch is pushed (dispatch and push CI at `C_α¹`), and merged into `wp/V02-alpha-gate` with a merge commit so that
`C_α¹` stays reachable from the RC branch (§7.4). Alternatives: one squashed cut commit (loses the per-change
provenance the read reviewed); a tag (outward, Frank's). Reversible by: deleting the branch before the merge.

B-AM2-7 **Review S2 accepted.** §18.4 (b) (R-347's member and the tests it extends) includes B-AM2-3's two workflow
steps, `python -m pip install -r requirements.lock` in ci.yml `dist` and release.yml `build`: §18.3's "a function the
same script already calls" is false for `t08_dist.py`, and the alternatives (a second derivation, a fallback value) are
the ones §18.3 rejects. The release `build` job's import of the lock's runtime dependencies is accepted as marginal
(the read, (4) S2).

B-AM2-8 **Review S1.** `tests/test_m07a_rc_records.py` builds dist-form records (`t08-a43-dist-v1`, members at top
level, `machine`, no CI flag): one agreeing (`ci-x86-64` / `x86_64`, pass), one disagreeing (`ci-aarch64` / `x86_64`,
`machine_class_disagrees`) beside one without a class. Mutation check: with `document.get("machine")` dropped from
`_m_provenance`, the disagreeing test fails.

B-AM2-9 **Step 12's committed certificates are named by their kept bundle path, without the bundle's `artifacts/`
segment** (records commit). The kept files sit at `<kept dir>/<bundle>/artifacts/solution-certificate.json`, and
`.gitignore`'s `evidence/**/artifacts/` would ignore that path under `rc/`. Chosen:
`rc/step12/certificates/<kept dir>/<bundle>/solution-certificate.json` (e.g. `g12-bundles/m02-g12-0/bundle/…`), the
bundle naming F1 already used; the copy is `tools/collect.sh`'s. Alternatives: `git add -f` under an ignored path
(fragile), or an ignore exception. Reversible by: renaming the five files and `STEP12_BUNDLE`.

B-AM2-10 **The RC-record hash tests compare multisets** (isolated commit `6146aa3`). At `C_α¹` the `m02-g12-0` bundle,
live and replay certificates are byte-identical (the live rerun and the replay reproduce the bundle bitwise), so
three listed records share one sha256 and `len(cited) == len(set(cited))` cannot hold. The test now requires the
cited and listed hashes to be equal as multisets with unique paths, and the row test checks every path of a cited
hash. Nothing listed can go uncited. Alternatives: commit one copy (A39's count of 3 + `len(edges)` would then fail),
or leave the copies out of `records.json` (unbound files under `rc/`). Reversible by: reverting `6146aa3` together with
three of the five certificate rows.

B-AM2-11 **Actions 5–7 as run.** Steps 1–10 on CI: dispatch **38772065394** (`rc_alpha`, `rc_distribution`) success, every
RC job success (check: 8507 passed / 100 skipped x86-64, 8479 / 98 aarch64); push **38772054427** success. Local
`ref-x86-64`, one script (`evidence/M07a/<C_α¹>/tools/run_local.sh`, scratch `~/.cache/of-rca-6fec822/`, RC worktree
`.claude/worktrees/rc-6fec822`, clean at start, after the venv and at the end): steps 2, 6, 7, 8, 9, 11, 12 PASS;
step 10 local PASS, 77 certificates, 0 violations (F1 gone). Against `C_α⁰` every check value is equal except paths,
timestamps, hashes and the code-identity keys; the G12 bundle certificate's `document_sha256` is `faa8e4da…fdf8974`
(was `d61a86fb…`) and equals the record's `certificate_sha256` (Q-A2-3: yes). Generator at `C_α¹`: A39 pass (5 of 5,
0 violations, bound), A43 pass (29 records, 0 without class, 0 unregistered, 0 disagreeing). Manifest
`evidence/M07a/<C_α¹>/manifest.json`: **`implemented`**, 37 pass, 0 fail, 6 unsupported — A52 (two changelog tests
skip as pending: the gate table comes from `--markdown` after the verdicts) and A60–A64 (verdicts, ledger). Step 13
not run (needs `docs/reviews/V02-alpha-verdicts.md`). `C_α⁰`'s evidence is kept as it was (records, manifest
`implemented`, tree record); its RC record moved to `docs/v02-alpha-rc-record-e0e198e.md` with one R-349 line.

B-AM2-12 **`docs/progress.md` and `docs/V02_STATE.md` are left to the orchestrator** (§18.5 action 7 names them). Both
are maintained on `main` by the session's `v0.2 state:` commits; this branch's copies are stale, and editing them here
would conflict at merge. The numbers they need are in B-AM2-11.

## Amendment 3 build-lane actions 1–4 and action 7's status rule (spec §19.8; R-370…R-377)

Commits on `wp/V02-alpha-gate`: action 1 `162e13b`, action 2 `e892790`, then action 3, action 4, and the two
generator commits (hashes in `git log`). Facts the amendment asked for:
- **Q-A3-2: yes.** Every L44–L48 and U15 pointer resolves as written (`--check`: 0 problems); none was replaced.
- **Q-A3-3: found.** `tests/test_m02_wo8_g7.py::test_g7e_a_pure_nh3_feed_is_refused_by_the_flash` pins the typed
  refusal (`unsupported`, `pure_nh3_flash_unsupported`; the solve ends `INITIALIZATION_FAILED`). U15 cites it.
- **Q-A3-4: no.** `-rs` adds `SKIPPED [n] …` lines before pytest's final count line. The readers of step 1's logs
  look for `=== check.sh: PASSED ===` (`t08_evidence_manifest.py`) and for `^N passed|failed` and
  `^(FAILED|ERROR) ` (`gate.sh`). None matches a `SKIPPED` line.

B-AM3-1 **The `## v0.2.0a1` Known-limitations list was regenerated in action 1's commit, not action 4's.** M07a.A52 (e)
(`test_e_the_limitation_ids_are_the_envelopes_in_order`) fails once the envelope gains L44–L48, so action 1's
acceptance (`gate.sh` green) needs it. §19.5 item 6 is therefore met by `162e13b`. Alternative: hold action 1 until
action 4. Reversible by: moving that hunk between commits at the cherry-pick.

B-AM3-2 **The four reclassified M02 harvest notes gain the suffix ` (R-370, class E)`.** Notes are free text, are not
rendered and are not hashed. The suffix marks which rows the design lane re-read. Alternative: leave the notes as they
were. Reversible by: a sed over four lines.

B-AM3-3 **The re-judgement's refusal wording, and a `rejudged` key in the JSON report.** When there is a
re-judgement, the date refusals name `Judged date J, re-judged R (gates)`. With no re-judgement, the existing T6
messages are byte-identical, and the A04/A05 tests that pin them are unchanged. Two new refusals:
`Frank's answer to I: accepted D, after the re-judgement of G that read it (…; §19.2 Table T7)` and
`G (x): accepted D, before the re-judgement of G that judged it (…; D2.3; §19.2 Table T7)`. `--markdown` is unchanged,
because A52 (c) compares it. The gates a re-judgement may list live in `GateSet.rejudge_waits`, which the registry
test holds to the YAML's `rejudge_depends`. The line is found anywhere in the document (A14 (d)). The `## Re-judgement`
section is not checked, because T8 is the rule. Reversible by: reverting `e892790`.

B-AM3-4 **`scripts/m02_evidence_manifest.py --harvest` now writes R-370's classes** (`HARVEST_E`). Without this, a
re-run would silently write P back over R-370. Its output for M02's manifest is byte-identical to the committed block
(checked). This commit is on `wp/V02-alpha-gate` only. It is not in §19.1 item 2's list, so `C_α²` does not
cherry-pick it. Alternative: leave the generator stale. Reversible by: reverting its commit.

B-AM3-5 **Action 7's status rule, now (self-contained).** In `scripts/m07a_evidence_manifest.py`:
- `STATUS_IDS` is A00–A51 and A53;
- A14 is catalogued, with the selector `test_m07a_v0_2_gate.py::test_a14_*`;
- A52 is measured `unsupported` / `pending`, with §19.4's reason.

A52 no longer runs the changelog module through the generator; that module still runs in `check.sh`. Checked on
synthetic entries: all pass gives `tested`; A52 and A60–A64 unsupported gives `tested`; A14 or A53 failing gives
`implemented`. Writing A52 and A64 with `judged_at` at the candidate (§19.4, "after step 5") is left for action 10.
The generator is not in `C_α²`'s tree.
