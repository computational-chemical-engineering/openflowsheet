# F0 review: the corpus identity gate, with the D9, D15 and D16 rulings

Reviewer (design lane), 2026-11-05. Brief `docs/briefs/F0-review.md`. Reviewed `wp/F0` at `032105e2` (code as of
`ab97a46e`) against roadmap §3 F0 and §2.4.4 (S1). I ran `corpus_identity.py --check` in the worktree at `032105e2`
on ref-x86-64. It exited 0 and printed `F0 PASS: M1 50/50, M2 52/52, M3 52/52, M4 52/52, M5 52/52, M6 52/52, M7
52/52, M8 105/105, M9 8/8`. The F0 test file result is in the closing line of this note.

**Verdict.** The gate is built soundly. It compares every measure with the committed registry. A missing or extra key
fails, and so does a measure that is not implemented. M7 and M8 cannot turn into a silent pass: a renamed, skipped or
deselected node, or a driver that crashes, fails M8 by name. The four exit mutations hold. There are two exceptions.
First, M6 is judged on platforms where its values cannot match (finding 1). Second, the corpus covers only one of
the seven frozen provider bases (finding 2). F0 is **not** ready for `tested` yet; the conditions are at the end.

## Findings, ranked

1. **Must fix: M6 is judged off the reference platform, but its keys hash exact iterate states.**
   `scripts/corpus_identity.py:476-485` exempts only M4 and M7 off the reference platform. M6 (`:245`) digests
   `ExactPropertyCache._property_key`/`_flash_key`, which hash `_state_document(request.state)`
   (`thermo/cache.py:193-211`): the float state of every Newton iterate. D5's own premise is that CI runners disagree
   with the reference in the last bits. *Scenario:* `scripts/check.sh` on the aarch64 leg (and possibly the hosted
   x86-64 one) runs `tests/test_f0_corpus_identity.py::test_the_gate_passes`. Every key after the first in the 15
   tear-path runs differs, so M6 fails 15/52 and CI goes red. No CI run of `wp/F0` exists (the branch has not been
   pushed). *Fix (needs a decision; I would take the first):* build M6 from a committed request sample (D8's
   alternative). Record the requests and their contexts once, then recompute the keys without solving. That makes M6
   portable, and it can carry one request per registered provider, which also closes the provider-coverage half of
   finding 2 for M6. Fallback: treat M6 like M4 (`NOT JUDGED` off the reference platform). Either way, the summary
   should count runs that have keys: 37 of the 52 register `n_keys: 0`, so "M6 52/52" overstates coverage.
2. **Should fix (needs a decision): the M2–M7 corpus exercises one provider basis.** Every registered
   `model_version` carries `syn001-4e4c37cc8054-…` (`benchmarks/f0/corpus.json` M2), and so do the M7 bundles.
   `pr_c1`, `pr_lib`, `wilson_ig(_v2)`, `iapws95`, `coolprop_heos` and the `c1.*`, `thermal.*` and Wilson-column
   families are never run. *Scenario:* an F3/F4 edit to shared code that those providers import (`thermo/__init__.py`,
   `compiled.py`, `revision_binding.py`) moves PR, Wilson or IAPWS numerics. M9 stays green (the bytes of the eight
   files are unchanged), and nothing else is run, so F0 passes. *Fix:* add one registered revision per basis to
   `run_corpus()`, solved through the existing g8 `solve()` path: `benchmarks/s11/gp/GP-*.json`,
   `benchmarks/s11/thermal/TH-*.json`, plus a registered case each for pr-c1, IAPWS and CoolProp. A1 allows this,
   because the cases are registered. I would do it in F0, before `tested`, because F0 exists to guard F2–F5, and those
   packages touch exactly these bases.
3. **Should fix: M9's scan can narrow silently.** At `corpus_identity.py:389-406`, a hash scope that reads its own
   bytes by any idiom other than `__file__`/`here` plus `.read_bytes` contributes no file and raises nothing. The
   docstring at `:376-377` says the opposite. Today the eight registered paths pin the set, so a rewritten site fails
   as "registered, not measured". Under ruling D9 below, however, the scan must read `file_sha256(Path(__file__))` and
   `path=Path(__file__)` (`models/thermal/*.py` → `thermal/common.py:397`). *Fix:* raise when any scope resolves to no
   file.
4. **Should fix: `.gitattributes` misses hashed text kinds.** The file lists `*.py … *.md` only. The 19 `*.txt`
   files under `benchmarks/t06/ensemble/runs/` are pinned by its `SHA256SUMS`. There are also 113 `*.jsonl` files, 18
   `*.log` files, and the `SHA256SUMS` files themselves. On X07a's Windows leg with autocrlf, these check out as CRLF,
   and the SHA tests fail. The roadmap requires "every data file whose bytes enter an identity" to be marked.
   `git ls-files --eol` shows 0 CRLF files in the index, so adding `*.txt *.jsonl *.log SHA256SUMS` is a no-op under
   renormalize.
5. **Should fix: the thread variables are set at import and leak into the whole session.** `corpus_identity.py:36-37`
   writes `OPENBLAS/OMP/MKL_NUM_THREADS=1` into `os.environ` when pytest *collects* the F0 test module. For the rest
   of the full gate, every subprocess that any test spawns then runs single-threaded. The in-process numpy is already
   loaded, so the setting does not even serve F0 inside pytest. It might explain part of the V17 wall-time gap (450 s
   in the gate, 344 s alone); I did not test that. *Fix:* set the variables in `main()`, since the script imports
   numpy lazily anyway.
6. **Note: an empty measure passes.** `compare()` reports a measure with an empty registered set and an empty
   measurement as PASS "0/0" (`:486-499`). Only the pytest test pins the counts (`test_f0…:55-56`, and M3–M6 not
   directly). *Fix:* fail when `n == 0`.
7. **Note: the exit-2 test has no unmutated control** (`tests/test_f0_corpus_identity.py:152-168`; exit 3 has one).
   Off the reference platform its M4 FAIL assertion is vacuous: `judged()` forces a reference comparison against
   hashes that differ anyway. *Fix:* first assert that the unmutated run's M2, M3 and M4 PASS, and judge M4 only on
   the reference platform.
8. **Note: exit 3 tests F0's own sensitivity, not the full pipeline.** It flips F0's reader (`gate.artifacts`), not
   the verifier. That meets the roadmap's wording ("a test-only mutation"). It does not show that a changed verifier
   reaches M5 through the certificate and the manifest.
9. **Note: `--record` writes the host's class as `reference_platform`** (`:519`) without checking that it is
   `ref-x86-64`. A re-record on another host silently moves where M4 is judged.
10. **Note: D15's count is 36, not 37.** Each guarded literal occurs in exactly 36 `artifacts/solve-policy.json`
    files and nowhere else under `tests/fixtures` or `benchmarks`.

## Rulings

**D15 → option (1′), registration-scoped. Read that way, it is a scope correction; option (1), by structure, would be a
relaxation.** The three guards protect *registered input* documents. Their docstrings say "registered case, fixture
or reference document" and "the policies that select it are built in code and named by id and hash". The 36 files
are archived *outputs* of a policy that code built (`resolve_policy(DEFAULT_POLICY_ID, …)`) at v0.3.0. They are the
record that a replay needs. Exempting by structure would let any future directory that holds a `run-manifest.json`
carry the values unchecked, and that would be a relaxation. **Build lane:**
- In one isolated commit, add a shared test helper that reads an `archived_outputs` map (path → SHA-256) from
  `benchmarks/f0/corpus.json`. `--record` writes the map from the M7 index.
- Each of the three guards skips a file only when both its path and its SHA-256 match an entry.
- A test pins the exemption at 36 files per guard. It also checks that every exempt file is an
  `artifacts/solve-policy.json` of a bundle that `index.json` names.
- Every other file in the bundles stays scanned.
- Options (2) and (3) are rejected. (2) hides the files by location; (3) is D3's rejected alternative.

**D16 → an additive ADR, written as `docs/adr/0059-evidence-work-package-ids.md` (Proposed).** The pattern becomes
`^(?:[PKTMSR][0-9]{2}[a-z]?|F[0-9]|X[0-9]{2}[a-z]?|TX|MSG|ST|OPT|RRC|PrISMa)$`. I checked it against every old-pattern
id (16 200); all still match. It refuses `L01`, `C9`, `E01`, `W1` and `FB-04`. The ADR reverses the rejected
alternative of R-565 and R-878 and says what changed: ADR 0057 fixes more than forty ids. It keeps R-565's
objections, so the L and C letters stay out and the ledger and model-manifest patterns are untouched. **Build lane:**
- Apply the ADR in one commit.
- Add a register entry.
- Record the ADR's acceptance evidence, then mark it Accepted.
- Commit `evidence/F0/<commit>/manifest.json`.

**D9 → include the legacy unit-model modules in M9.** The default rests on a false premise: `artifact_hash` enters
none of M1–M8.
- M2's `model_version` and `constants_sha256` are functions of the spec alone (`orchestrator/execution.py:172-187`).
- M3 is the float-free R0 projection (`run/identity.py:59`).
- No bundle or registered document carries `artifact_hash`.

As a result, an edit to `models/c1/flash.py` is caught only if it moves a state hash of an exercised case on the
reference platform, and the c1 and thermal families are not exercised at all (finding 2). §2.4.4 places S1 under the
legacy-family freeze and says "a legacy bug fix … is not allowed under F0 PASS".

**How M9 enumerates them.** M9 adds every file whose SHA-256 equals some legacy manifest's
`implementation_artifact.artifact_hash`, taking each model id in `MODEL_BUILDERS` (`revision_binding.py:1642`) and
obtaining its manifest as `tests/test_k02_unit_models.py` does. A model id whose manifest cannot be produced, or whose
hash matches no file under `src/`, raises. If producing every manifest proves impractical, extend the AST scan to the
two idioms in use (see finding 3). In that case, add a test that the set's size equals the number of distinct manifest
`module` values. The files are registered by path, alongside the eight provider files. Excluded:
`studies/surrogate/reactor.py` and `adapters/*` self-hashes, because they are not legacy unit families. The wider
reading of "imported into" (all transitive imports) is not adopted, because it would freeze the core; finding 2 is
the right guard there.

## May F0 be marked `tested`?

Not on the rulings alone. It may be marked `tested` when all of the following hold:
1. D15 (1′), the D16 ADR and the D9 inclusion are applied, each as its own commit. The M9 registry diff must be
   insertions only.
2. Finding 1 is fixed, and CI is green on both architectures for `wp/F0`.
3. Findings 3–5 ride in the same batch.
4. The full gate is green, with the V17 budget test re-run on a quiet host.

Finding 2 is Frank's call. If it is deferred, record it as a declared limit, and make it an entry condition for the
first of F2, F3 or F4 to merge.

**Not examined:** the bundle contents (out of scope), `run_revision_session`'s internals, the `_Recorder` beyond its
outcome ranking, and ruff and mypy.

**F0 test file run** (worktree, `032105e2`, ref-x86-64): `14 passed in 87.01s`.
