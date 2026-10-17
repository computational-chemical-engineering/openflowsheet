# The released 0.2.0a1 alpha on `main` — design-lane rulings (R-456 – R-460)

**Authority and scope.** Design lane (`specifier`), 2026-10-17, one pass on
`docs/briefs/V02-alpha-main-rulings-brief.md` at `wp/V02-alpha-main` @ `6a760c1`. These rulings decide
what the checks that fail after the alpha's merge into `main` verify from now on, and what the version and
the envelope on `main` are between releases. They are consistent with ADR 0028 (D4), the alpha release spec
(`docs/derivations/V02-alpha-release-spec.md` §5.3, MR-3), R-193, R-217, R-234, R-295, R-435 and ADR 0036 D8.
They amend no ADR, no frozen interface and no released record. The build lane applies §3 in the order of §4.
Register entries: R-456 (items 1 and 5), R-457 (items 2–4), R-458 (item 6), R-459 (item 7), R-460 (item 8).
Amended once, 2026-10-17, by R-458 A1 (§2 R-458, §3 E5a and E6, §5 O5, §7), on the evidence of E6's stop at
`3969e57`.

**Already decided, not reopened.** 0.2.0a1 was released from `423ae9c`. Nothing in its record is rewritten:
the CHANGELOG section `## v0.2.0a1`, the ledger at `C_α²`, the verdicts, and the M07a manifest and its RC
records. No tolerance, band or classification moves.

## 1. Measured facts, with corrections to the brief

All facts were measured on `6a760c1`. Its `src/` and `schemas/` are identical to the merge `06fb0f2`.

| # | Fact | How it was measured |
| --- | --- | --- |
| F1 | Item 1: the only ledger difference in W23–W27 from `C_α²` is W24's `evidence`. It is `[]` at `C_α²` and `[evidence/M03/fd16834…/manifest.json]` now (`078d579`, M03 WO-10). The ledger at the tag `423ae9c` equals `C_α²`'s for W23–W27. The claimed rows V11–W22 are identical between the tag and HEAD. | `yaml` comparison of the three `docs/requirements.yaml` versions |
| F2 | Items 2–4: **the moved surface is M04's, not M03's or M05's.** The served list at `C_α²` digests to `383b4e2c…` (D_2). On `main` it digests to `455d01eb2f420032b27358798e6b331a0120aa1857f02ce3cb7851647849e125`. The only difference is M04's `surrogate_study` job kind (ADR 0037 D6, ADR 0019 Amendment 5): a fourth value in the `operation` enum, a body branch and a result branch, across `submit_job`, `get_job`, `get_job_result`, `list_jobs`, `wait_job` and `cancel_job`. The tools are still 17 and no description changed. `tests/m04_schema_support.py`'s `without_m04` (R-295's strip) applied to `main`'s list gives exactly D_2, and the rest of the alpha's chain then holds. `strip_m02` applied directly to `main`'s list gives `1142d707…` ≠ D_1. | `m07a_rc.served_tools()` run on both trees (the `C_α²` tree from `git archive`), followed by a leaf diff |
| F3 | Item 5: on `main`, `scripts/v0_2_gate.py --rc cc73219… --candidate 423ae9c… --markdown` exits 0. Its 2248-byte table is contained verbatim in the released `## v0.2.0a1` section. The working tree's `CHANGELOG.md` is byte-identical to the tag's. | the script was run on `6a760c1` |
| F4 | Item 6: the in-process backend's environment fingerprint is `{kind, boundary_sha256, module, module_sha256, openflowsheet_version}` (`adapters/experiments/backends.py:166–176`). The fingerprint is part of every experiment key (ADR 0036 D8). In `adapters/` the version is used only there, so the external (REAL) backend's handshake does not carry it. | code reading |
| F5 | Item 6: **`scripts/m05_retake_diff.py` does not prove a digest-only re-take.** It compares coupling digests by shape and the ledger, store and environment sidecars bytewise, and it checks no old→new digest map. S77's proof was a leaf walk outside the repository (build log S77). | code reading |
| F6 | Item 7: R-365's own text says "a new L-row", with no number. The number L43 was assigned by the build lane (M04 build log E37) and is cited in the committed M05 manifests (`cfecb15`, `56fb2fa`, as "M04 L43"). The harvest rows of `989b16f` map M04/M05 to `L49`. | grep |
| F7 | Item 8: `main` still carries the **pinned** alpha envelope (`v0.2-alpha-envelope-1`, `release: 0.2.0a1`), now with L49, a row the alpha did not ship. The alpha spec's "MR-3, after the tag" requires the first D2.4 change after the tag to return the envelope to R-193's working form (`v0.2-envelope-dev`, `0.2.0.dev0`). The merge did not do this. | `benchmarks/t08/support_envelope.yaml:24–25`; spec §5 (MR-3 paragraph) |
| F8 | Item 8: `release.yml` accepts only `X.Y.Z` or `X.Y.Z{a\|b\|rc}N`, so a `.devN` head can never be dispatched. `gate_set_of` covers no `.dev` version, so the gate answers NO. The only T08 test on the working-tree version is `pyproject` == `__version__`. The version-carrying set is B-WO10-4's: `pyproject.toml`, `__init__.py`, the two `project_summary` fixtures and `tests/test_m06_w27_coverage.py:544`, plus W27's `coverage.json` (re-taken) and the G10 records. PEP 440: `0.2.0a2.dev0` > `0.2.0a1` > `0.2.0.dev0`. | `release.yml:69–80`; `packaging.version` |
| F9 | The D2.4 tree check (`v0_1_gate.tree_differences`) finds 137 paths where HEAD differs from `423ae9c`, and also from `C_α²`. | the script was run on `6a760c1` |

## 2. Rulings

### R-456: items 1 and 5. The alpha's ledger and changelog tests judge the record that 0.2.0a1 released

M07a.A64 (`tests/test_m07a_ledger.py`) and M07a.A52 (`tests/test_m07a_changelog.py`) are checks of a past
release. As in R-217, they keep verifying that release's committed record, and they read it from the tag
commit `423ae9c`, not from the working tree. Each has a universal half that stays on the working tree:

- **For A64,** `tests/test_requirements_ledger.py::test_every_cited_evidence_manifest_exists_and_says_what_is_claimed`
  already covers all 27 gates. It passes now, with 0 missing.
- **For A52,** the working tree's `## v0.2.0a1` section must stay byte-identical to the released one.
- **Clause (c)** runs `main`'s gate script on the alpha's own candidate. This makes M07 §7.2's requirement
  that "the alpha entry's behaviour is byte-identical" executable while WO-3 changes the script.

### R-457: items 2–4. `main`'s surface chain gains link c_3 (R-295); the alpha's two-link record stays verified

The alpha spec §5.3 already settles this: "a new MCP-visible change … is a new link c_{m+1}. It needs a register
entry, a strip function, a registered digest, and Frank's carry extended to name it." On `main` the chain
gets **c_3**:

- register entry: R-295 (the decomposition), with R-457 (its place in the chain);
- strip function: `without_m04`;
- registered digest: D_3 = `455d01eb2f420032b27358798e6b331a0120aa1857f02ce3cb7851647849e125`.

The chain is checked live on `main` (items 1–4 of §5.3, with controls i–iv). The alpha's committed step-8
record at `C_α²` is checked as a record: two links, passed.

Frank's carry is **not** a test condition on `main`. It is the gate's `frank_items` check at a release.
**What the 0.2.0 gate must do (WO-3/WO-8; M07 §15 N5):**

- RC step 8 at C runs the chain with every link registered by then.
- The 0.2.0 `V17 carry` answer must name every link: R-192, R-234, R-295, and any later one.
- WO-3 makes that executable (§5, O3).

**No new Frank question now, and no paid run.** The move happened before the W27 candidate C_W exists (M07 §9
cuts C_W after M04/M05 are merged), so "surface changes after the paid W27 run, stop and ask" (N7) is not
triggered. N5 is already on 0.2.0's list; its wording gains the third change.

### R-458: item 6. Re-take the five G10 records; the fingerprint and the comparison are unchanged

`openflowsheet_version` is the experiment store's cross-release guard against serving another release's
result as an exact hit (ADR 0036 D8: the fingerprint is part of the key). The other two members of the
fingerprint are the model's own files, so none of its members is "unrelated". Changing what the fingerprint
covers would be an ADR-level change to cache-key semantics, made for test convenience. It is rejected.
Comparing G10 modulo a digest relabelling is also rejected: it would let a change to key derivation pass
unseen.

The ruling has four parts:

- **What:** every change on `main` to a fingerprinted input is followed by a digest-only re-take of the five
  records. The inputs are `__version__`, `models/c1/boundary.py` and a variant's evaluation module.
- **Proof:** the re-take is proved by a committed tool (E5), not by a walk outside the repository.
- **When:** now, once, **after** R-460's version change (one re-take, not two). Then again in the commit that
  cuts the 0.2.0 candidate, so that RC step 14 replays 0 differences at C.
- **Records:** M05's committed manifests are not rewritten. Their record sha256s describe the records they
  were taken at, as S77.

**Amendment A1 (2026-10-17, after E6 stopped at `3969e57`).** The proof as first written could never pass
the re-take it orders. The coupling record stores the in-process fingerprint in clear, so a version change
moves one non-digest leaf per coupling record: `frozen.reactor.fingerprint.openflowsheet_version`, `0.1.1` →
`0.2.0a2.dev0`. Measured at `2345b54`: 4/7/4/3/4 such leaves (one per coupling record, 22 in all), nothing
else non-digest, environment files byte-equal, map a function and injective. That is a defect in this note,
amended here, not bent in the tool.

Rule (a) admits that one leaf, as a class `version`, on three terms (E5a):

- **exact path,** not a pattern;
- **pinned values:** the committed side is `--old-version`, the re-take side is the running
  `openflowsheet.__version__`;
- **bound to its digest:** on both sides, `frozen.<u>.fingerprint_sha256` is `document_sha256` of
  `frozen.<u>.fingerprint`. That is how `backends.py:166–176` makes it, and the request's
  `environment_fingerprint_sha256` carries it into the experiment key. The clear leaf therefore cannot move
  unless the key's fingerprint digest moves with it, and that digest is then held to (b) and (c).
  Measured: the binding holds for all 22 coupling records on both sides of S77's pair (`56fb2fa^`,
  `56fb2fa`) and in the committed records at `3969e57`.

*Rejected:* the engineer's form, `*.fingerprint.openflowsheet_version` with pinned values but no binding.
The pattern would admit a leaf under any future frozen unit or nesting without a ruling. Without the
binding, a re-take whose clear version moved while `fingerprint_sha256` did not would pass, because an
unchanged digest is a valid map entry. That is a key derivation that dropped the version: the change R-458
exists to catch. *Also rejected:* ignoring the leaf like a timing (it would admit a record taken at a third
version); treating it as a digest (it is not one); taking the clear fingerprint out of `external-coupling-v1`
(a record-format change for test convenience, which also costs the record its auditability).

### R-459: item 7. L49 confirmed; R-365 keeps its text and gains an amendment line

The alpha's L43 (R-321) is released and cited by the released notes, so it keeps the id. M04's row is
**L49**, the next free id; `989b16f` already applied the change. R-365 never named a number (F6), so its
decision text stands. An amendment line records that its L-row is L49. The committed M05 manifests that
say "L43" are evidence and are not rewritten. Their harvest rows carry the mapping to L49. AM-30 makes the
mapping executable.

### R-460: item 8. Between releases `main` carries a `.dev0` version after the last release; the envelope returns to its working form

`main`'s version becomes **`0.2.0a2.dev0`**:

- It sorts after the released `0.2.0a1` and before every version the 0.2.0 gate covers (`0.2.0bN`,
  `0.2.0rcN`, `0.2.0`).
- `release.yml` refuses it, and the gate answers NO for it. Both fail closed for a non-release head.
- Records, `get_project.server.package_version` and the experiment keys made on `main` no longer claim to be
  the release.

The envelope returns to R-193's working form, `v0.2-envelope-dev` with `release: 0.2.0.dev0`, as MR-3 already
requires (F7). The envelope's `release` is a label for "v0.2 under development" and is not ordered. It
differed from the package version before (0.1.1 next to 0.2.0.dev0, R-193), and MR-3 fixes its value, so it
is not changed here.

The general rule from now on: **the first D2.4 change after a tag moves the version to a `.dev0` that sorts
after the tagged version, and returns the envelope to its working form.** A version string that names a
release identifies that release's D2.4 tree and nothing else. AM-40 makes this executable. It fails on
today's HEAD (F9), which is why this is item 8.

Rejected alternatives:

- **Keeping `0.2.0a1`.** `main` kept `0.1.1` this way during v0.2. That precedent was never ruled on, and it
  makes 137 differing paths claim the release's identity.
- **`0.2.0.dev0`.** It sorts *before* the release it follows.

## 3. Exact changes for the build lane

Every assertion below is an exact comparison of strings, bytes, digests or sets. No tolerance applies, so
there is no floor to quote. The reason each assertion cannot pass by accident is given beside it.

**E1. `tests/conftest.py`.** Add the following beside `PUBLIC_ROOT`:

```python
#: 0.2.0a1 as released: the commit tagged `v0.2.0a1` (2026-10-17; release run 39045791146), R-456.
ALPHA_TAG_COMMIT = "423ae9c54d903f9dcf0ea90fe9639222c1acbda4"
```

**E2. `tests/test_m07a_ledger.py` (R-456).** `ledger()` returns the gates of
`git show ALPHA_TAG_COMMIT:docs/requirements.yaml`. `rc()` and the verdict document stay read from the working
tree, so a rewrite of the released verdicts on `main` is caught against the released ledger. Docstring: "the
ledger as 0.2.0a1 released it (R-456)". After the change:

- **AM-01.** The claimed verdicts in the released ledger equal the verdict document's rows, as the gate's parser
  reads them (unchanged logic).
- **AM-02.** Every claimed gate in the released ledger cites `evidence/M07a/<C_α²>/manifest.json`, which exists in
  the working tree.
- **AM-03.** W21 cites an M01 and an M02 manifest, and W22 cites an M01 manifest (released ledger). Each file
  exists.
- **AM-04.** Every manifest a claimed gate cites in the released ledger exists in the working tree. Evidence is
  append-only, so a deleted release record fails this test.
- **AM-05.** W23–W27 in the released ledger equal W23–W27 at `C_α²`. This is `test_the_unclaimed_gates_are_untouched`.
  It passes (F1).
- **AM-06 (new, `test_the_tag_commit_is_0_2_0a1`).** `git merge-base --is-ancestor ALPHA_TAG_COMMIT HEAD`;
  `v0_1_gate.version_at(ALPHA_TAG_COMMIT) == "0.2.0a1"`; and, where `refs/tags/v0.2.0a1` exists, it
  resolves to `ALPHA_TAG_COMMIT`. Where the tag is absent, that one half skips and names the reason; the other
  two halves always run.

**E3. `tests/test_m07a_changelog.py` (R-456).** `section()` reads `git show ALPHA_TAG_COMMIT:CHANGELOG.md`.
Every clause (a), (b), (d)–(g) and the pending-marker test therefore judges the released section. Clause (a)'s
"first section" is a fact of the released file. On `main`, `## v0.2.0` will come first (WO-6). After the
change:

- **AM-07.** Clause (c) runs
  `v0_2_gate.py --rc <heading's C_α> --candidate ALPHA_TAG_COMMIT --markdown`, with `check=True`. Its stdout is
  contained in the released section (F3: exit 0, 2248 bytes). The test fails if WO-3 changes the alpha
  entry's output by even one byte.
- **AM-08 (new, `test_the_released_section_is_unchanged_here`).** The working tree's `## v0.2.0a1` section,
  from its heading up to the next `\n## `, equals the released section byte for byte.

**E4. `scripts/m07a_rc.py` and `tests/test_m07a_surface_chain.py` (R-457).**

In `scripts/m07a_rc.py`, add `strip_m04(tools)`, which returns
`m04_schema_support.without_m04(copy.deepcopy(tools))` (loaded as `strip_m02` loads `without_m02`). Append
`Link("c_3", "R-295", strip_m04, "455d01eb2f420032b27358798e6b331a0120aa1857f02ce3cb7851647849e125")` to
`LINKS`. Add c_3 to the docstring's list of links ("M04's `surrogate_study` job kind; registered at the alpha's
merge into `main`, R-457"), with one sentence: the released 0.2.0a1 ran the two-link chain (its committed
record), and a re-run of the alpha's step 8 uses the script at the tag.

D_3 was measured on `6a760c1`. AM-10 measures it again on every run. After E7's version change AM-10 must
still pass, because the tool list carries no version string. If it fails there, stop and report; do not
re-register D_3.

Each control first asserts that the unmodified `served` list passes the chain, so that no control can pass
merely because the chain already fails.

- **AM-10.** `chain(served)` rows are `[(1,"c_3"), (2,"c_3"), (2,"c_2"), (2,"c_1"), (3,None)]`, with
  `first_failure` None. `rows[-2]["found"] == D_0`. There are no description problems, and the served texts are
  the files.
- **AM-11.** `digest(strip_a3_2(served)) != D_0` (unchanged), **and** `digest(strip_m02(served)) != D_1`
  (F2: `1142d707…`).
- **AM-12, control (i).** Add a member `probe` to `get_project`'s `outputSchema`. Then `first_failure == "c_3 (R-295)"`
  and the first two rows' `pass` is `[False, False]`. Today this test passes for the wrong reason: the chain
  already fails at item 1.
- **AM-13, control (ii) at m.** Links `(L0, L1, Link("c_3","R-295", too_many, L2.digest))`, where `too_many`
  is `strip_m04` followed by deleting `get_project.outputSchema.properties.head`. `rows[0]` passes and
  `first_failure == "c_3 (R-295)"`.
- **AM-14, control (ii′) at an inner link.** Today's control (ii), kept, with L2 appended so that c_2 is now
  an inner link: links
  `(L0, Link("c_2","R-234", too_many_m02, L1.digest), L2)`. `rows[0]` and `rows[1]` pass, and
  `first_failure == "c_2 (R-234)"`.
- **AM-15, control (iii).** Unchanged.
- **AM-16, control (iv).** Links `(Link("c_1","R-192", identity, L0.digest), L1, L2)`. `rows[:3]` all pass,
  and `first_failure == "c_1 (R-192)"`.
- **AM-17.** The existing source checks, plus: `strip_m04(x) == without_m04(deepcopy(x))` for the served
  list, and `LINKS[2].digest` occurs in the text of the R-457 entry in `docs/decision-register.md`.
- **AM-18 (new, the released record).** `evidence/M07a/<C_α²>/rc/surface/rc-alpha-surface.json` has
  `passed` true and `first_failure` null. Its chain links are `["c_2","c_2","c_1",null]`, with
  `chain[0].found == LINKS[1].digest` (D_2) and `chain[-1].expected == V17_C2_DIGEST`. This is 0.2.0a1's step 8,
  read rather than re-run.

**E5. Digest-only re-take proof (R-458), a build-lane tool.** Add `scripts/m05_retake_diff.py --digest-only
<committed-stem> <retake-stem>`. It walks every leaf of five documents: the record (without `provenance`),
the ledger, the store index, the environment file, and every coupling record, with coupling files paired by
the relabelled name. It classifies each differing leaf by the script's registered timing patterns, as a
digest (both sides match `^[0-9a-f]{64}$`), or as other. It builds the old→new map over **all** digest leaves,
equal ones included.

It exits 0 iff all of the following hold:

- (a) other = 0 (a leaf admitted by E5a's `version` class is not other; A1);
- (b) the map is a function;
- (c) the map is injective;
- (d) the environment files are byte-equal, **or** they differ only in `distributions_sha256`. In that case,
  recomputing `environment_fingerprint()`'s distribution list in the running environment, with the
  `openflowsheet==` line set to `--old-version <v>` (a required argument whenever (d)'s second branch is
  taken), reproduces the committed hash.

It prints one line per case: PASS/FAIL, the number of changed digests (distinct old values whose new value
differs), and each class count.

Acceptance:

- **AM-20.** On S77's pair (records at `56fb2fa^` against `56fb2fa`, extracted with `git archive`) it prints
  PASS for all five cases.
- **AM-21.** The changed-digest counts are recorded beside S77's `42/80/71/92/38`. A mismatch goes to the
  build log with both counting rules; it is not silently accepted (Q2).
- **AM-22.** Unit tests in `tests/test_m05_retake_digest_only.py` use synthetic JSON in `tmp_path`:
  - consistent relabelling of two digests → PASS, 2 changed;
  - one float moved by one ulp → FAIL, naming the leaf;
  - two old digests mapped to one new digest → FAIL (not injective);
  - one old digest mapped to two new digests → FAIL (not a function);
  - an environment difference outside `distributions_sha256` → FAIL.

**E5a. The `version` class and the fingerprint binding (R-458 A1).** Added to `--digest-only`, everything
else in E5 unchanged:

- **Path.** Only the coupling-record leaf at exactly `frozen.reactor.fingerprint.openflowsheet_version`.
  The same text at any other path stays other: in the record, the ledger, the store index, the environment
  file, or elsewhere in a coupling record. A new frozen unit or nesting fails closed and comes back to the
  design lane.
- **Values.** The rule is checked on every coupling pair, whether the leaf differs or not.
  - With `--old-version <v>`: the committed side equals `<v>`, and the re-take side equals the running
    `openflowsheet.__version__`. The CLI has no option for the re-take side.
  - Without `--old-version`: the two sides are equal, which is rule (a) as before.
  - A pair that lacks the leaf on either side is other.
- **Binding.** For every unit `u` in `frozen` of every coupling record, on both sides:
  `frozen.u.fingerprint_sha256 == openflowsheet.canonical.document_sha256(frozen.u.fingerprint)`. A
  mismatch is other and names the file and side. This check always runs, with or without `--old-version`.
- **One argument.** `--old-version` keeps one meaning, the committed side's version, and serves both (d) and
  this class.
- **Report.** The summary line gains `version=<n>`: the number of differing leaves admitted as `version`.

Acceptance:

- **AM-20** is unchanged: S77's pair passes without `--old-version`, with `version=0`. Its 44 coupling sides
  satisfy the binding.
- **AM-22** gains these cases (synthetic coupling records in `tmp_path`; the test may set the running
  version by monkeypatching `openflowsheet.__version__`):
  - the leaf goes `v0` → `v1`, the run is at `v1` with `--old-version v0`, and `fingerprint_sha256` is
    recomputed on both sides and moved consistently wherever it occurs → PASS, `version=1`;
  - the same, without `--old-version` → FAIL, naming the leaf;
  - `--old-version` differs from the committed side → FAIL;
  - the re-take side differs from the running version → FAIL;
  - the leaf moves but the re-take side keeps the old `fingerprint_sha256` → FAIL (binding). This case would
    PASS without the binding;
  - the same version string moves at another path (for example `frozen.reactor.openflowsheet_version`, or a
    leaf in the record) → FAIL as other.

**E6. Re-take (R-458), after E7.**

1. From a clean tree at the version-changed commit, in `.venv-nlp` with `OMP_NUM_THREADS=1`, run `run_case`
   and `write_files` into a scratch directory for TR-E2, TR-E2-FAR, TR-E2-FD, LOOP-R and LOOP-S.
2. Run `--digest-only --old-version 0.1.1` and get PASS for each case (A1). The expected counts are the ones
   measured at `2345b54`:
   - `version=` 4/7/4/3/4;
   - changed-digests 41/79/70/91/37. These are S77's counts less one, because `boundary_sha256` does not
     move here.

   A different count goes to the build log with both numbers and stops E6. It is not accepted silently.
3. Copy the files over the committed ones.
4. Acceptance:
   - **AM-23:** `OMP_NUM_THREADS=1 pytest -m nlp tests/test_m05_g10_replay.py` gives 5 passed.
   - Write an M05 build-log S-entry with the five summary lines.
   - Run `scripts/m05_wo9_real.py --replay` once and record the result (Q1).

**E7. Version and envelope (R-460).**

- Set `0.2.0a2.dev0` in B-WO10-4's set: `pyproject.toml`, `src/openflowsheet/__init__.py`, the two
  `project_summary` fixtures, and `tests/test_m06_w27_coverage.py:544`.
- Re-take W27's `coverage.json` and `docs/m06-w27-coverage.md` at that build, as `d73004a` did.
- In the envelope, set `envelope_id: v0.2-envelope-dev` and `release: 0.2.0.dev0`. Set
  `t08_support_matrix.ENVELOPE_ID = "v0.2-envelope-dev"` and update its comment ("returned at the alpha's
  merge into main, R-460").
- Re-emit `docs/support-matrix.md` and get 0 problems from `--check`.
- Add a paragraph "After a tag" to `docs/RELEASING.md` stating R-460's general rule.

New `tests/test_v02_main_version.py`, with `RELEASED = {"0.2.0a1": ALPHA_TAG_COMMIT}`:

- **AM-40.** If `__version__` is a key of `RELEASED`, then `v0_1_gate.tree_differences(RELEASED[v], HEAD) == []`.
  Negative control, always run: `tree_differences(ALPHA_TAG_COMMIT, HEAD)` is non-empty (137 at `6a760c1`, F9).
  On today's HEAD this test fails, which is the defect item 8 names.
- **AM-41.** `str(Version(__version__)) == __version__` (canonical PEP 440).
  - If the version is a dev release: the envelope is `v0.2-envelope-dev` with `0.2.0.dev0`, and `ENVELOPE_ID`
    equals that id.
  - Otherwise: the envelope's `release` equals `__version__`. This is the cut, and the gate checks the same at C.
- **AM-42.** `Version(__version__) > max(Version(v) for v in RELEASED)`, unless `__version__` is in `RELEASED`.
  This assertion is what rejects `0.2.0.dev0`.

**E8. Envelope id mapping (R-459).** In `tests/test_t08_w2_support_envelope.py`:

- **AM-30.** No harvest row whose `manifest` lies under `evidence/M04/` or `evidence/M05/` has `L43` in its
  `to` list. At least one such row has `L49`. The L43 row's text begins "The Anderson recycle".

## 4. Order, and acceptance of the whole

1. Apply E1–E4 and E8, with no version change. Gate: every failure except G10 is gone.
2. Apply E7. AM-10 must still pass, which shows D_3 is unchanged.
3. Apply E5, then E6.

The whole is accepted when:

- `scripts/gate.sh` reports 0 failed;
- the nlp tier passes, G10 included;
- CI is green on both runners;
- the commit messages name V02, and each of E5, E6 and E7 is its own commit, so that each can be reverted
  alone.

## 5. Obligations this hands to the 0.2.0 gate (M07; the M07 spec's owner folds them in)

- **O1 (WO-3).** Add `tests/test_m07_ledger.py` in the pattern of the alpha's, on the working tree at C. All 17
  gates are claimed, so there is no "untouched" test. After 0.2.0 is released, it is scoped to its tag commit,
  as R-456 does here.
- **O2 (WO-3).** AM-07 stays green. It is the executable form of M07 §7.2's "alpha entry byte-identical".
- **O3 (WO-3, WO-8).** Every MCP-visible change before C adds a link (R-457). The gate's `V17 carry` check
  must also require the row of ADR 0042 to name every `m07a_rc.LINKS[k].register`. If one is missing, the
  gate answers NO, with the reason "V17 carry does not name R-…".
- **O4 (WO-6).** `## v0.2.0` becomes the first section. AM-08 keeps the alpha's section unchanged.
- **O5 (WO-8, the cut).** The commit that sets `0.2.0` carries:
  - B-WO10-4's version set;
  - the pinned envelope (`v0.2-envelope-1`, `0.2.0`);
  - W27's coverage at C (M07 §9);
  - the G10 re-take with its digest-only proof (R-458), run with `--old-version 0.2.0a2.dev0`, the
    version of the records E6 committed (A1).

  AM-41's else-branch then holds at C.

## 6. Open questions, each with a default

- **Q1 (needs a fact).** Does REAL's replay move with the version? By code reading it does not (F4). The
  measurement that settles it is `scripts/m05_wo9_real.py --replay` at the final version (about 25 min, in the
  reactor environment). *Default:* expected 0 differences. Digest-only differences are re-taken with E5's
  proof. Any other difference: stop and escalate.
- **Q2 (needs a fact).** S77's counting rule for 42/80/71/92/38. *Default:* E5's rule (distinct changed old
  digests) is normative. A different S77 count is recorded, not reconciled by changing E5.
- **Q3 (needs Frank's preference, low stakes).** The version label on `main` between releases. *Default
  applied:* `0.2.0a2.dev0`. *Alternative:* keep `0.2.0a1`, as `main` kept `0.1.1`. That requires deleting
  AM-40/AM-42, which R-460 rejects. *Reversible by:* reverting E7's commit and repeating E6.
- **Q4 (needs Frank, at 0.2.0's ruling round; already M07 N5).** Carry `v17-c2`'s agent evidence across
  R-192, R-234 **and R-295** (M04's `surrogate_study` job kind). *Default:* carry. *Alternative:* a new V17
  campaign (about USD 10, 1 h).

## 7. What these rulings do not establish

- **No new evidence for 0.2.0a1 and no re-judgement of it.** AM-05/07/08/18 re-read its record; they do not
  re-run its RC.
- **Nothing about 0.2.0's verdicts or claim set.** O1–O5 are obligations, not results. The 0.2.0 V17 carry is
  Frank's.
- **That D_3 is the digest at M04's merge.** D_3 is measured on the merge tree only.
- **That the re-taken G10 records are numerically correct.** A re-take is a regression fixture; it proves only
  that nothing moved but digests and the pinned version leaf bound to its digest (A1). G10 is numerical
  verification, not validation (R-435).
- **That A1 covers any other non-digest move.** It admits one path. Any other difference stays other, and
  a ruling is needed for it.
- **That `.dev` heads are safe to reuse a store across.** The version guard is release-granular. Commits
  between releases share one version, as before.

## 8. Findings (recorded, not acted on here)

- **F-a.** MR-3's after-tag clause was not executed by the merge (F7). It is fixed by E7.
- **F-b.** The brief attributes the surface move to M03/M05, and names `m05_retake_diff.py` as S77's proof.
  Both are corrected by F2 and F5.
- **F-c.** The M07 spec (`wp/M07`) should cite R-456–R-460 in WO-3, WO-6 and WO-8. That edit belongs to its
  owner.
