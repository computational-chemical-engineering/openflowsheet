# V02 alpha Amendment 2: design-lane read of build actions 1–2 (§18.4 item 2, §18.5 action 3)

**Reader:** design lane (`reviewer`), 2026-10-15, on `wp/V02-alpha-gate` @ `2e778d3`.
**Diff read:** `ab80ca5..2e778d3` (04e65be R-345, 00acbe9 + f0cfda8 R-347, 46b2095 generator, f77262e/2e778d3 log),
against spec §18.1–§18.5 (R-345…R-349) and build log B-AM2-1…B-AM2-4. The Amendment 2 rulings themselves were not
re-opened. Gate and Am2.5 numbers are taken as reported in B-AM2-1; nothing was re-run except the tree simulation in (5).

## Verdict: proceed to the re-cut `C_α¹`. No must-fix.

R-345 is exactly §18.1's remedy; Am2.1–Am2.4 falsify the defect; R-347 and the generator check meet §18.3. B-AM2-3's
workflow steps are sound and inert to the artifacts, but they go beyond §18.3's text, so this ruling records them (S2).
One pre-cut check is recommended (S3), because a failure there would cost a further re-cut.

## (1) R-345: matches §18.1
- `coupled_run.py:766` writes `None`; `checks.py:930–950` no longer computes or writes the witness note. The two
  changes outside the literal scope are forced and harmless: `_check` loses its `reproducibility` parameter, which only
  the old note used (`coupled_run.py:744–751`, 2 call sites, no other callers), and `witness_skipped_columns`'s
  docstring (`checks.py:954`). `certificate.py` is unchanged. Its `independence_qualifications` (1305–1316) is the only
  consumer of the field in `src/`, so no other certificate field can move. The class is still in the `external_model`
  limitation (`coupled_run.py:812–822`), and the columns are still in `derivative_witness_partial` (`certificate.py:1239`).
- No tracked fixture outside `docs/` and `evidence/M07a/` holds either old note (`grep` over py/json/yaml), so
  "fixtures that move: none" holds. The M02 design note's two passages are marked superseded (`M02-pymrm-adapter.md:478,
  1480`).

## (2) Am2.1–Am2.4: they falsify the defect
- The preconditions are asserted at all three states (`test_a09_qualification_field.py:128–130, 153–155, 166–170`). S1
  also asserts that its entries are non-empty, so Am2.2 at S1 catches a fix that drops the prefixed entries.
- Am2.2 uses its own copy of A33's prefixes, symmetric difference plus the provider members, not the certificate's rule.
  Every rejected alternative of §18.1 fails at least one assertion. Filtering in `certificate.py` leaves the check-level
  note, which fails Am2.1 and Am2.3. Writing [A09] text on the EXT checks fails Am2.2 and Am2.3. Dropping all entries
  fails Am2.2 at S1.
- Both negative controls patch the live producers. `certificate.py:1205` imports `derivative_witness` at call time, and
  `coupled_run` looks up `_check` as a module global. Each control requires exactly the restored ids.
- **N1 (note)** `:215`: S3's witness assertion is conditional. That matches the spec, which gives S3 no skip
  precondition. B-AM2-1 shows S3 does skip (4a failed on the old code for that reason), so it could be pinned as a
  precondition. S2 already covers the witness defect.

## (3) R-347 and `_m_provenance`
- `t08_rc.py:430–438, 531–538, 1298–1304` pass `{**provenance(), "machine_class": machine_class()}`, evaluated after
  every check. No constant, check or `format` changes. `t08_dist.py:453` computes the class after the builds and after
  `tree_clean`, and `__pycache__/` is git-ignored. The generator (`m07a_evidence_manifest.py:346–368`) adds "registered"
  and agreement with `architecture`/`machine` and `github_actions` where present, as §18.3 requires.
- **S1 (should fix, post-candidate, does not block the cut)** `tests/test_m07a_rc_records.py` `_provenance_of` writes
  only `t08-rc-v1` records that have a `provenance` block. The dist-record path (`t08-a43-dist-v1`, top-level `machine`,
  no `provenance`, `m07a_evidence_manifest.py:354`) is exercised by no test. `C_α⁰`'s dist record has no class, so the
  first exercise would be action 6. Add a constructed dist record that agrees and one that disagrees.

## (4) B-AM2-3: the lock install in ci.yml `dist` and release.yml `build`
- **The inertness claim is sound by construction.** `build_environment` (`t08_dist.py:217–230`) is a plain
  `python -m venv`, with no system site-packages. Its pip comes from ensurepip, and it installs pinned setuptools.
  `requirements.lock` pins neither pip nor setuptools. The hooks run the venv's python with `os.environ`, which
  `pip install` does not change, and the parent's `sys.path` edits do not reach subprocesses. Every A43 check is stdlib
  arithmetic on the archives. `clean-install` is a separate job with its own venv.
- **S2 (needs a decision; I would accept)** §18.3 justified the exception by "a function the same script already
  calls", which is false for `t08_dist.py`. So the two workflow steps are outside §18.3's text but inside the purpose of
  §18.4 (b). The alternatives, a second derivation or a fallback value, are the ones §18.3 rejects. Record here that
  (b) includes the two steps. ci.yml's step is needed for step 3's record. release.yml's step is needed only to keep the
  release job working with the shared script; the release build record is not one of the step 1–12 records. Side
  effect: the release `build` job now imports the lock's third-party packages, unhashed, in the process that holds the
  artifacts before upload. This is marginal, because these are the wheel's own runtime dependencies and the `gate` job
  already runs them. Accept.
- **S3 (should fix before the cut)** Two import paths are new on CI, and the tests run them only in the dev venv, where
  `openflowsheet` is installed editable along with the dev dependencies:
  - `t08_dist.machine_class()` in a lock-only interpreter, importing `openflowsheet` from the appended `src/` (step 3);
  - `install-check` and `lock-check` calling `machine_class()` in the wheel-only clean venv (step 4). That imports the
    checkout's `benchmarks.t06.ensemble` against the installed wheel.

  A static check finds nothing missing. The imports are numpy, scipy, yaml and casadi, all in `Requires-Dist`, and
  `openflowsheet/__init__.py` makes no metadata lookup. But a failure is fail-closed: no record is written, and the fix
  would need `C_α²`, because A43 needs `commit` = C on every record. Before cutting, dispatch ci.yml's
  `rc_distribution` path (`dist` + `clean-install`) on the action-2 tip, or simulate both interpreters locally.

## (5) Applying the commits onto `e0e198e`: clean
I simulated the cut with `git merge-tree --write-tree`. ab80ca5, 04e65be, 00acbe9 and f0cfda8 each apply onto
`e0e198e` without conflict. None of their paths changed in `e0e198e..ab80ca5^`. The result differs from `e0e198e` in
exactly 14 files: 2 workflows, the spec, the register, the M02 note, `t08_dist.py`, `t08_rc.py`, `coupled_run.py`,
`checks.py`, and 5 tests. That is §18.4 (a)–(c) plus S2's workflow steps. On `src/`, `tests/`, `scripts/` and
`.github/` it equals `2e778d3` except for the two post-candidate files (generator and its test), which are absent. So
the gate at `2e778d3` ran the code `C_α¹` will carry. §8.1 must still run at `C_α¹` itself, because the test count
differs.
- **N2 (note)** At `C_α¹`, §18's header cites the brief (`b8a769a`), and §18 cites `C_α⁰`'s RC record and B-WO10-6/10.
  None of these is in that tree. R-349's own example ("this amendment's commit") leaves the brief out, so accept the
  dangling references.

## Not examined
`t08_rc.audit_certificate`; the other producers in `verify/table.py`/`pr_c1.py` (§18.7); the 33 skipped tests; the
Am2.5 runs themselves (accepted as logged); release.yml's other jobs.
