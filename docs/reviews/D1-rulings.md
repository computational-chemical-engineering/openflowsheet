# D1 — batched design-lane ruling round after S01, S02, C4 and C7 (2026-10-22)

**Author:** design lane (`specifier`). **Branch:** `wp/D1` from `wp/C7` `9b09ed2`. **Brief:**
`docs/briefs/D1-ruling-round.md`. **Register:** R-560 to R-565. **ADR:** none (no frozen interface, schema, ADR
decision or registered identity changes; §4).

## 0. Authority and scope

This document rules on the brief's six questions. Each ruling binds the build lane through the work orders in §2, and
through the dated spec amendments listed in §3, which are made in the same commit. It changes no production code and
no test. Where a ruling interprets an older register entry, the entry stays in force and the new entry says what it
adds.

## 1. Rulings

### Q1 — T05b §6.6 against later packages' v2 policies (R-560)

**Facts.** T05b spec §6.6 says that every registered policy stays v1 and that the T05b cases run `T05b-v2`. B06
(`tests/test_t05b_literal.py:103-149`) admits the `phase_contract=` keyword only in two named sources:
`application/policies.py` (`T05B_V2`) and `models/syn001/cascade_solve.py:107` (`S01_DEFAULT_V1`, from S01 WO-5).
S02 added no third source: S02 spec §0 reuses `s01-default-v1`. The text of §6.6 was already narrower than the
repository before S01. `T06-revision-v1`, `T06-revision-v2`, `T08-warm-v1` and `T08-ptc-v1` are v2, because they are
`dataclasses.replace` derivations of `T05B_V2` (`policies.py:1-25`, ADRs 0015, 0018, 0023, 0024). The same holds for
S01's `s01-isothermal-presolve-v1`. `scripts/t05b_evidence_manifest.py:1652` still exempts only the first source. Run
at HEAD, it would report `cascade_solve.py:107` as an offender.

**Ruling.** §6.6 becomes a registered-list rule, and the amendment is written below §6.6 in this commit:

- The policies registered before T05b stay v1.
- A **v2 root** is a policy that spells the keyword. It exists only if it is a row of §6.6's register table, and each
  root is constructed exactly once, in its listed source, under its listed id.
- A `replace` derivation that leaves `phase_contract` alone inherits v2 and needs no row. It must be registered under
  its own id by its own ADR or spec.
- A new root takes four things in one commit: the registering spec or ADR, a register entry, a table row, and the
  same row in B06's `V2_SOURCES`.

`s01-default-v1` stays in `cascade_solve.py`.

**Reasons.**
- `policies.py` is the application's registry, and `REGISTERED_POLICY_IDS` is held equal to
  `benchmarks/registry.yaml` (`tests/test_t07_b3_policies.py`). Moving S01's policy there would offer a policy for a
  library-only capability on the revision routes (`resolve_policy`: "a named registered policy is honoured on either
  route"). That changes the application contract and moves nothing else.
- Building it as `replace(T05B_V2, …)` would remove the keyword. That route escapes B06's scan instead of being
  registered.

**What changes.** The T05b spec §6.6 amendment and B06 row note (this commit). WO-D1-A items 1 and 2: B06 checks the
table, and the T05b manifest scan reads `V2_SOURCES`.

`DECISION: Q1 → amend T05b §6.6 to a registered table of v2 roots (T05b-v2, s01-default-v1), replace-derivations inherit and are registered by their own ADR/spec; s01-default-v1 stays in cascade_solve.py. Alternative: move it into application/policies.py (offers it on the revision routes) or build it by replace (evades B06). Reversible by: a register entry moving the row, then the same move in V2_SOURCES and the table.`

### Q2 — S01/S02 scope rows (R-561)

**Facts.** At `9b09ed2`, 30 harvest items have `U04` among their pointers: 18 from `evidence/S01/` and 12 from
`evidence/S02/`. No other package has any. Every one of these notes names its model id (`syn001.cascade` or
`syn001.column`) as library-only. `MODEL_BUILDERS` has 22 entries and holds neither id (measured with the project
venv). U04 is "a model id not in `MODEL_BUILDERS` → `model_unsupported`" (`benchmarks/t08/support_envelope.yaml:341`).
R-535 already says S02's L-rows wait for the binding package.

**Ruling.** The L-rows are written when the cascade or the column binds, not now. The package that adds
`syn001.cascade` or `syn001.column` to `MODEL_BUILDERS` writes their L-rows and reclassifies that model's U04 items in
the same commit. Until then, U04 is the true user-facing statement: an application user who names the model gets
`model_unsupported`.

A tripwire makes the deferral executable, in the pattern of T08 Ruling 6's `library-only` edge rows: a test fails as
soon as either id is bound while its U04 items stand (WO-D1-A item 3). §5.7 of the T08 release spec gains the rule
(this commit).

**Reasons.** The support matrix describes what the application offers. An L-row for a capability no user can reach
would state the limits of something the matrix calls unsupported. Either it contradicts U04, or the reader has to
know that the row is dormant.

`DECISION: Q2 → L-rows when the model binds; U04 until then, pinned by a tripwire test that fails when syn001.cascade or syn001.column enters MODEL_BUILDERS with its U04 items standing. Alternative: S01/S02 L-rows now (a dormant claim beside U04). Reversible by: adding the rows and dropping the model from the tripwire map.`

### Q3 — C4-Q1: M07a.A61 classified S (R-562)

**Facts.** The three items (`6fec822` limitations[4] and checks[39]; `cc73219` limitations[3] and checks[40];
`e0e198e` limitations[6] and checks[39]) each say "M07a.A61 is unsupported (pending)", with `state: pending`. None of
them states a limitation. A61's registered criterion (V02 alpha spec line 877) already expects "V14 (b) `FAIL`". The
closing fact is the verdict document `docs/reviews/V02-alpha-verdicts.md`, and it did not exist when any of the items
was written: `git cat-file` at `7f4f6e0`, the `cc73219` manifest's commit, reports it absent, and the other two items
say so in their own text. That is exactly §5.7's S-by-document clause. The user-facing fact, PTC experimental and
V14 (b) FAIL, is row L01, which T08's harvest already carries (`T08-verdict-V14b.md` is in L01's evidence).

**Ruling.** S stands, and C4's rows are unchanged. E → L01 would misfile the items. The compound rule (E first) applies
only to an item with a user-facing part, and these items have none. Filing them E would also make a pending state
read as a limitation.

`DECISION: C4-Q1 → S to the verdict documents (as filed). Alternative: E → L01. Reversible by: editing the three pairs of harvest rows.`

### Q4 — C7-Q1: the working envelope after 0.2.0 (R-563)

**Facts.**
- C7 kept `v0.2-envelope-dev` with `release: 0.2.0.dev0` while `main` is `0.3.0.dev0`.
- Renaming the envelope breaks `test_a10_the_envelope_must_be_pinned_to_the_alpha`
  (`tests/test_m07a_v0_2_gate.py:1030-1048`). Its edit is pinned by R-475 and by M07.A31 (b)
  (`tests/test_m07_v0_2_gate.py:327, 372-378`) to exactly the two 0.2.0 pairs.
- ADR 0042, which is Accepted, states that same "exactly the two pairs" in its migration impact.
- R-475's "Watch for" already says the 0.3.0 cut breaks A10 again and needs its own ruling.
- R-460 calls the envelope's `release` "a label … not ordered", and `release.yml` and the gate refuse every `.devN`.
  So no release and no record carries the working id.

**Ruling.** Keep `v0.2-envelope-dev` with `0.2.0.dev0` as `main`'s working form until v0.3's release-policy ADR, the
0.2.0 successor of ADR 0042. That ADR decides, in one place, the 0.3.0 pin, the working form that follows it, and A10's
pairs.

From R-193 on, the working id reads as a fixed token meaning "main's unreleased working envelope". It no longer
glosses as "v0.2 under development". `docs/RELEASING.md` says so (this commit). Renaming now would amend an accepted
ADR's acceptance evidence and the frozen alpha test. The 0.3.0 cut amends both again, so renaming now costs two edits
for a label that nothing releases.

**What changes.** Only the RELEASING sentence. The recommended default for the v0.3 ADR is in §5.

`DECISION: C7-Q1 → keep v0.2-envelope-dev / 0.2.0.dev0 until v0.3's release-policy ADR (one ruling for the 0.3.0 pin, the successor working form and A10's pairs). Alternative: v0.3-envelope-dev / 0.3.0.dev0 now (+2 A10 pairs, amends ADR 0042's migration impact and A31 (b)). Reversible by: that ADR, or an ADR now amending ADR 0042's migration clause with the four-pair A10 edit.`

### Q5 — C7-Q2: the 0.2.0 ledger tests (R-564)

**Facts.**
- At `0.3.0.dev0`, `at_c` skips all four judging tests in `tests/test_m07_ledger.py` (S-UNCOV).
- O1 (`docs/design/V02-alpha-main-rulings.md:365-367`), M07 spec §23.2 ("After the tag R-456's re-scoping applies")
  and the module's own docstring already decide that after 0.2.0 the ledger is read at the tag commit. It is not done.
- `docs/requirements.yaml` and `docs/reviews/V02-verdicts.md` are byte-identical between `5c82b4c` (tag `v0.2.0`,
  version `0.2.0`) and HEAD.
- CI checks out with `fetch-depth: 0`.
- While the tests skip, 0.2.0's release record has no executable check. R-456 rejected exactly that.

**Ruling.** Do it now, as R-456 did for the alpha. M07 spec Amendment 9 (§26, this commit) gives the exact form, and
WO-D1-A item 4 implements it. Expected result: `tests/test_m07_ledger.py` gives 5 passed and 0 skipped at HEAD.

`DECISION: C7-Q2 → scope the 0.2.0 ledger tests to the tag commit now (O1's post-release clause); at_c and its predicate test are retired. Alternative: leave the skips to a later package. Reversible by: reverting WO-D1-A item 4.`

### Q6 — Evidence-manifest ids for C-items and L01 (R-565)

**Facts.**
- Three frozen schemas share the package namespace. `evidence-manifest.schema.json:23` uses
  `^[PKTMSR][0-9]{2}[a-z]?$`. `requirements-ledger.schema.json:89` and `model-manifest.schema.json:31, 212` use
  `^[PKTMSR][0-9]{2}$`.
- C1 to C7 are `docs/CLOUD_WORK.md` queue items, not plan packages. Frank's queue rule there reads "a tested manifest
  where the package has one". C5 and C6 took plan ids (S01, S02) and carry manifests. C1 to C4 and C7 merged or are
  merging on the gate and CI.
- L01 (component-library gaps, new scope 2026-10-22, ADR 0043 on `wp/L01`) adds a provider (`pr-lib-v1`) and tested
  numerics. Its manifest draft is `docs/briefs/L01-WOR-manifest-draft.json` on `wp/L01`, with 6 checks and
  4 limitations.
- `L01` also collides with the envelope's limitation row `L01` (PTC experimental), which bare harvest pointers name.
  This ruling's own Q3 shows the ambiguity.

**Ruling.**

1. CLOUD_WORK C-items, and design-lane ruling rounds such as D1, carry no evidence manifest. They merge on the read
   full gate and green CI on both architectures. The merge commit message records both: gate result with commit, and
   the CI run id. Their tests and generator `--check` modes are their acceptance evidence. A C-item that is or becomes
   a plan package takes that package's id and its manifest, as C5 and C6 did.
2. L01 is renumbered **S04**: the next free id in the v0.3 line, with no dependency on S03. Its dependency is C2's
   split. The package id S04 is used in the manifest (`work_package`, the path `evidence/S04/<commit>/`), in the
   manifest's check ids (`S04.<label>` for the spec's `L01.<label>`, a one-to-one prefix map stated once in the L01
   spec header), in envelope `check:` pointers, and for the branch of further work (`wp/S04`, created at `wp/L01`'s
   tip).
3. File names, module names, the spec's own labels, generators and registered hashes keep `L01`. Moving them would move
   registered bytes for a label.
4. The S04 manifest is harvested like any other: classified E/S/P/B under §5.7, with `HARVEST_SIZE` updated. It is not
   excluded.

**Reasons.**
- Widening the frozen schemas needs an ADR across three schemas.
- Adding `L` would make `L01` mean both a package and a support row.
- Adding `C` needs single-digit ids, which is a fourth pattern.

The id is a label and reversible, so this is not Frank's. His rule on C-items is restated in
`docs/FRANK_QUESTIONS.md` as no-answer-needed.

`DECISION: Q6 → C-items and ruling rounds carry no manifest (gate + CI recorded in the merge message); L01 is renumbered S04 for its manifest, check ids and branch, with files and labels unchanged. Alternative: an ADR widening the three schemas' package pattern. Reversible by: such an ADR, then moving evidence/S04/ to the widened id.`

## 2. Work orders (build lane)

**WO-D1-A** (`sonnet-implementer`, on `wp/D1`; one isolated commit per item; run only the touched tests). Every
assertion below is an exact comparison of strings, sets or counts. No tolerance applies, so no floor needs quoting.

1. **D1-A01 (Q1).** In `tests/test_t05b_literal.py`, add `test_b06_the_v2_register_is_the_specs`.
   - It parses the rows between `<!-- B06-V2-REGISTER -->` and `<!-- /B06-V2-REGISTER -->` in
     `docs/derivations/T05b-limitations-spec.md`. For each row whose first cell is back-ticked, it takes the first
     two back-ticked cells as (policy id, repository-relative source).
   - It asserts that the set equals `{(id, source.relative_to(REPO_ROOT).as_posix()) for source, _, _, id in V2_SOURCES}`.
   - Negative control, in the test: the same parse of the text with the `s01-default-v1` row removed gives a different
     set.
   - Update B06's docstring and comments to cite "§6.6 as amended (D1, R-560)".
2. **D1-A02 (Q1).** In `scripts/t05b_evidence_manifest.py::_p1_scan_policies`:
   - Build `exempt` from the test file plus every source in `literal_fixtures.V2_SOURCES`.
   - The B06 description text says "outside the registered exemptions (spec §6.6 as amended, R-560)".
   - Record in the build log that, measured, `_p1_scan_policies()["offenders"] == []` at the item's commit. It was
     `["src/openflowsheet/models/syn001/cascade_solve.py:107"]` before.
3. **D1-A03 (Q2).** In `tests/test_t08_w2_support_envelope.py`, add `LIBRARY_ONLY = {"syn001.cascade": "S01",
   "syn001.column": "S02"}` and a helper `library_only_problems(builders, harvest) -> list[str]` that reports:
   - (a) each id in `builders`;
   - (b) each harvest item from `evidence/<pkg>/` (pkg a value of the map) with `U04` in `to` whose `note` lacks
     `` `<id>` `` and `library-only`;
   - (c) each such package with no U04 item (no vacuous pass).

   Each message names the id and says "bound: add its L-rows and reclassify its U04 items (D1, R-561)". Three
   assertions:
   - The helper returns `[]` on `revision_binding.MODEL_BUILDERS` and the envelope's harvest.
   - It returns exactly one problem naming `syn001.cascade` with `{**MODEL_BUILDERS, "syn001.cascade": object()}`.
   - It returns exactly one problem when one S01 U04 item's note has its id removed (a deep copy).
4. **D1-A04 (Q5).** Implement M07 spec §26, then run `pytest tests/test_m07_ledger.py`. Expected: 5 passed,
   0 skipped. Run the §26 negative control once without committing it and record its outcome.

**WO-D1-B** (the L01 lane's engineer, on `wp/S04`, created from `wp/L01`'s tip):

1. Move the draft to `evidence/S04/ce9b8d5…/manifest.json`, or re-take it at a later code commit. Set
   `work_package: "S04"` and check ids `S04.*`; `T08.A32` stays as it is. Write the one-line alias in the L01 spec
   header: "Package id S04 (D1, R-565). Manifest check ids are `S04.<label>` for this spec's `L01.<label>`."
2. Classify the manifest's limitations and non-pass checks in `benchmarks/t08/support_envelope.yaml` under §5.7. Update
   `HARVEST_SIZE` and re-emit `docs/support-matrix.md`.
3. Required to pass: `tests/test_evidence_manifests.py`, the A21 and A50 harvest tests, and
   `t08_support_matrix.py --check` with 0 problems.

## 3. Spec and document amendments in this commit

- `docs/derivations/T05b-limitations-spec.md`: §6.6, the register table and the rule; the B06 row note (R-560).
- `docs/derivations/T08-release-spec.md`: §5.7, the library-only rule (R-561).
- `docs/derivations/M07-spec.md`: §26 Amendment 9 (R-564).
- `docs/RELEASING.md`: "After a tag", the working-form token (R-563).
- `docs/CLOUD_WORK.md`: the manifest rule for C-items and ruling rounds (R-565).
- `docs/FRANK_QUESTIONS.md`: the D1 section.
- `docs/decision-register.md`: R-560 to R-565.

## 4. What this does not establish

- No ADR is written. ADR 0042 is not amended. No schema, interface or registered hash moves.
- No test or production code changes here. WO-D1-A and WO-D1-B are unimplemented until their commits.
- B06, even when amended, does not find a v2 policy that is derived by `replace` in an unregistered place. Such a
  policy is a review finding, not a B06 failure (§5, D1-O1).
- Nothing here judges L01/S04's science, its harvest classes, or Frank's L01-Q1 and L01-Q4. The C2 split's Q-5 is not
  touched either.
- The S01/S02 limitations are not true or false of a bound model. They describe the library.
- A61's S classification says nothing about V14 beyond L01.

## 5. Open questions (each with a default)

- **D1-O1 (needs a fact).** Can B06 also enumerate `replace`-derived v2 policies? It would do so by importing
  `src/openflowsheet/**` and collecting module-level `SolvePolicy` objects. Measure the import cost and side effects.
  Default: no. Review catches them.
- **D1-O2 (needs the user's preference, deferred to the v0.3 release-policy ADR).** What should the working form after
  0.3.0 be? Default: a version-free id (`main-envelope-dev`) with `release` equal to `main`'s version, so the question
  stops recurring. A10's pairs are ruled together with it.
- **D1-O3 (needs a fact).** Does a full rename of L01's files and labels to S04 move registered bytes? This matters only
  if the L01 lane wants the rename. Default: alias only (R-565).

## 6. WO-D1-A build log (build lane, 2026-10-22)

- Item 1 (`bba7ebf`): `test_b06_the_v2_register_is_the_specs`; in-test negative control (row removed gives a different set).
- Item 2 (`60ec28b`): measured `_p1_scan_policies()["offenders"] == []` at the commit (was `["src/openflowsheet/models/syn001/cascade_solve.py:107"]`); sources_scanned 723; negative control, a probe `scripts/zz_probe.py` with `phase_contract=` is reported as `scripts/zz_probe.py:1` (file removed).
- Item 3: `library_only_problems` and three tests in `tests/test_t08_w2_support_envelope.py` (32 passed in the file); S01 18 and S02 12 U04 items all carry their id and `library-only`.
- Item 4: `tests/test_m07_ledger.py` gives 5 passed, 0 skipped (the `v0.2.0` tag is fetched here; the tag test skips where it is not). Negative control (constant = `ALPHA_TAG_COMMIT`, not committed): 3 failed (`test_the_claimed_verdicts_are_the_documents`, `test_every_claimed_gate_cites_m07_at_c`, `test_the_tag_commit_is_0_2_0`), 2 passed. §26.4 expected only the cites test to fail; the alpha's verdict set also differs from 0.2.0's, so the verdict-equality test fails as well. Not an issue for the check.
- Full touched run: 894 passed, 3 deselected (tests/test_t05b_*, test_t08_w2_*, test_m07_*); ruff and mypy clean.
- Not done: spec §26.3 item 1's optional import of the constant in `test_v02_main_version.py` and `test_m07a_harvest.py` (literals kept).
