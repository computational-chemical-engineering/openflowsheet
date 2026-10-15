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
