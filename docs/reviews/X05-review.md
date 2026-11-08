# X05 review — replay from the wheel (ADR 0069, amends ADR 0007 D4/D6), WO-1…WO-3 on `wp/X05`

**By:** design lane (`reviewer`), 2026-11-07. **Brief:** `docs/briefs/X05-reviewer.md` (`81a19017`). **Reviewed:**
`git diff 004d7faa...wp/X05` at head `82030102`: `src/openflowsheet/run/{lock,manifest,replay}.py`, `resources.py`,
the `_data/requirements.lock` link, `pyproject.toml`, `scripts/t08_rc.py` (`lock-check`, `f0-replay`), CI
`clean-install`, `tests/test_x05_{lock,replay_from_the_wheel}.py` and the touched T08/M01 tests, against ADR 0069
(Proposed), `docs/X05_DECISIONS.md` (Q-N1, D-1…D-8) and `evidence/X05/42c84f1d…/manifest.json`. This review sets no
manifest status, and `reviewed` is not claimed anywhere.

## Verdict

**The implementation is sound: no path records `lock_sha256` without the D2 check, and none reads a lock from outside
the package.** Cold numerics, the environment document's eight keys and ADR 0007 D4's table are unchanged. **It is
not yet mergeable as accepted**, for two procedural reasons (M1, M2), not code defects. One should-fix (S1) is a
one-line change in `run/lock.py`.

Run by the reviewer at `82030102` on `ref-x86-64` (load ≈ 21 of 48): `tests/test_x05_lock.py` **49 passed** (0.76 s);
`tests/test_x05_replay_from_the_wheel.py` **14 passed** (8.6 s; the five `lock-check` states and the eight replay cells
on the copied tree); `docs/derivations/scripts/x05_reference.py --check` **PASS** (36 cases, 8 replay cells, 25
assertions); a memo probe (S1). No full gate and no F0 `--check` were run (the brief's machine-load rule).

## Must fix (before the merge)

- **M1 — the dispatch cannot close the four unsupported checks.** Run 42391223708 (`workflow_dispatch` on `wp/X05`,
  head `82030102`) was started without `rc_distribution` (or `rc`, `rc_alpha`, `release_rc`). When read at 17:31 its
  `dist` job was **skipped**, and `clean-install` (`needs: dist`) was skipped with it. `check` (both legs) and
  `default-install` were still in progress. So whatever the run's conclusion, it evidences none of A20's sdist half,
  A21, A22 (b), A25's CI half or Q-N2. X05 rewrites `clean-install`, and that job has never run on either leg; aarch64
  has never run at all. ADR 0069 §8 names these checks as acceptance evidence by run id. **Fix:** after the main merge
  (M2), dispatch `ci.yml` at the fix-round head with `-f rc_distribution=true`, and re-take the manifest as in ruling 3.
- **M2 — merge `main` into `wp/X05` and make the RP step-4 edit, which is now due.** See ruling 5.

## Should fix

- **S1 — the memoised exception's traceback grows on every call** (`src/openflowsheet/run/lock.py:175`, D-2). `raise
  outcome` re-raises the stored instance, and each raise adds the `installed_version` and `verify_lock` frames to its
  `__traceback__`. Measured with `importlib.metadata.distribution` raising: the traceback depth after 1…5
  `verify_lock` calls was 4, 6, 8, 10, 12. Each frame keeps that call's lock bytes, text and pins alive. Scenario: a
  long-lived `serve-http`/MCP process in an F6 environment (unreadable closure metadata) leaks memory on every
  `environment()` call. **Fix:** `raise outcome.with_traceback(None)` (this keeps D-2's instance and its class). Add
  one assertion to `test_a19_the_memo_holds_the_outcome_not_only_the_version` that the depth is the same after the
  first and the third call.

## Notes (no action required)

- **N1 — a lock that verifies is the lock recorded.** If a copy of `src/openflowsheet` keeps the link (`cp -a`, not a
  registered install mode), `_data/requirements.lock` resolves to the file three levels above the copied package.
  That is R-140's location, but the file is verified before it is hashed, so D4.1's attestation still holds: each of
  the 9 is at the pins of the hashed bytes. A hash that differs from `ead4edf1…` replays inspected. This is not a false
  `exact_replay`. Wheels and the sdist carry resolved bytes.
- **N2 — Q-F1 is not reverted by one commit.** `a58ef5a5` isolates the pins and D-1. A revert would also have to restate
  `test_a25_the_closure_is_pinned_exactly_in_requires_dist` (WO-1) and A25's CI half as their inverse, as ADR §11
  Q-F1 says. The register line should not claim that one revert is enough.
- **N3 — the memo is process-wide.** Every shadow or fake-dist test runs in a subprocess today. A future in-process
  test that changes `sys.path` metadata after another test has called `environment()` would see stale versions. Keep
  such tests in subprocesses, or reset `lock._INSTALLED` with `monkeypatch`, as A19's memo test does.
- **N4 — the experiments backend's `lock_sha256`** (`adapters/experiments/backends.py:281`) is the reactor
  environment's lock, not this one. It is untouched and unaffected.

## Rulings

1. **D2 against the reference: correct.**
   - `verify_lock` matches D2.1–D2.4: the grammar, the first malformed line with `repr`, duplicate names after PEP 503
     normalisation, closure order, no short-circuit, string comparison, F6 by class name, the hash of the raw bytes.
   - All 36 states equal the JSON. The JSON is rendered by an independent implementation, `x05_reference.py`, which
     imports nothing from `openflowsheet`.
   - **Every producer of `lock_sha256` goes through `verify_lock`.** `environment()` with no argument reads only
     `files("openflowsheet")/_data/requirements.lock` (`resources.packaged`), and `_checkout_lock`/`_repository_lock`
     are deleted. `environment(lock_path=…)` verifies the named file and has no production caller.
     `run/bundle.py:101` rebuilds a recorded `Environment` with `lock_findings=()`. No other constructor exists in
     `src/`.
   - R-140's watch item holds. A13 (a verifiable stray above the package, never read) and A14 (no packaged lock: F1,
     never the stray's hash) pass on the copied tree.
   - **The link:** the wheel carries the bytes (A20 local; `test_a20` pins the link and that it is the only
     `requirements.lock` under `src/`). `t08_dist.py` resolves the `_data/` links in the sdist. The sdist's byte check
     is M1's.
2. **D-8: accepted.** `SHIPPED_DATA` admits `(src/)?openflowsheet/_data/requirements.lock` by exact path. The file is
   the project's own list of names and versions, the case M02 §2.4 admitted for `reactor-env.lock`. Nothing else is
   admitted, and the inventory still refuses any other new member.
3. **`tested`: supported as a status, not sufficient for acceptance.**
   - The manifest declares the four `unsupported` halves honestly, with local substitutes on `ref-x86-64`: the wheel
     records and A22 (a) at `7f39b199`. `src/`, `scripts/`, `.github/` and `pyproject.toml` are unchanged from there to
     `82030102`, so the substitutes stand for the head's code.
   - ADR 0069 takes effect only with §8's CI evidence (M1). **If the `rc_distribution` dispatch is green**, write a new
     `evidence/X05/<fix-head>/manifest.json`:
     - A20sdist, A21, A22b and A25ci become `pass`, each with the run id and the artifact files and SHA-256s:
       `t08-a43-dist.json`; per runner, `lock-{installed,checkout,installed-off,checkout-off,installed-nolock}-<runner>.json`,
       `f0-<runner>.json` and `unconstrained-<runner>.json`.
     - `X05.CI` names the dispatch. Q-N2 is answered from the two `f0-*.json` mode and verdict counts.
     - The limitation "the X05 brief forbids a dispatch" is dropped.
   - **If it is not green:** a failing `x05.*` check, or any F0 `MISMATCH` or inspected mode on either leg, is a
     design-lane finding (ADR §11 Q-N2's default). It is not a narrowed denominator. The merge waits.
4. **The build decisions.**
   - **D-1 accepted.** The exact list is kept and lives in the pin commit (see N2 for the scope of a revert).
   - **D-2 accepted with S1.** Storing the instance is right for exceptions with unusual constructors; the growing
     traceback is not.
   - **D-6 accepted.**
     - `f0-replay` runs `corpus_identity.m7()` in-process after the installed `openflowsheet` is bound, so the paths
       `corpus_identity` inserts at import cannot redirect the package's submodules.
     - The judgement is the registered value on the reference platform, else `MATCH` with integrity and an exact or
       compatible mode.
     - The timeout of 45 min against A22 (a)'s 9 s is ample margin.
   - **D-7 accepted.**
     - **At the merge:** ADR 0069 becomes Accepted and ADR 0007 Amendment 2 (§13) is appended verbatim.
     - **Register:** the three §12 lines take the next free numbers above X02's R-950 (R-951–R-953 if X02 lands first
       with R-950 alone), and R-140 gains "Lifted by X05 (ADR 0069), <date>; L41 narrowed (D7.3)". The register line
       for D3.2 states N2's revert scope.
   - D-3, D-4 and D-5 (not asked) are consistent with the ADR.
5. **The merge with `main`** (RP merged after `004d7faa`):
   - **(a)** `docs/derivations/release-procedure.md:422`, step 4: change "Clean install and the lock lookup (T08.A44,
     T08.A19) … Checks `a44.*`, `a19.*`" to "Clean install and the packaged lock (T08.A44; X05.A21, A22 (b), A25; T08.A19
     retired by ADR 0069 D7.2) … Checks `a44.*`, `x05.*`". The `a19.*` ids of step 17 (`wheel_data_check.py`, V03.A19)
     are a different A19 and stay.
   - **(b)** `.github/workflows/ci.yml`: keep main's `|| inputs.release_rc` on `dist`'s `if` and RP's
     `default-install` condition (C-3), together with X05's `clean-install` steps and its 45-min timeout.
   - **(c)** `benchmarks/t08/support_envelope.yaml`: main added only new rows (REL.A20, RP.gate) and none touches L41.
     Merge, regenerate `docs/support-matrix.md`, then run `t08_support_matrix.py --check`.
   - **(d)** `docs/progress.md`: remove the pending "step-4 line left to `wp/RP`" item, and update the same note in
     `X05_DECISIONS.md` D-7.
   - **(e) Line files:** `release/lines/0.3.json` and `0.4.json` carry no `a19.*` pair and no reference to the removed
     `test_t08_r3_a19_lock_lookup.py`, so no id changes there. **Needs a decision (release lane):** no 0.4 gate claims
     step 4 (no `[4, …]` pair), and no gate's tests glob reaches `tests/test_x05_*.py`. Under RP §6.1 X05's
     clean-install evidence is then not re-taken at the 0.4 cut. I would add `tests/test_x05_*.py` and `[4, "x05.*"]`
     to the 0.4 gate that carries L41/R-140, as a line-file change in the fix round.
   - **(f)** After the merge: run the touched tests, `x05_reference.py --check`, F0 `--check` and the full gate once,
     then the M1 dispatch.

## What this review did not establish

- Anything the CI halves measure (M1): the sdist bytes, the real wheel on either leg, aarch64 at all, and F0 from the
  wheel off the reference platform.
- Q-N1 for `.venv-nlp` and `.venv-lca`, which were judged from their build locks only. The live measurement is the
  next RC's.
- The full gate, F0 `--check`, `t08_support_matrix.py --check` and A22 (a): these are the engineer's numbers and were
  not re-run here.
- A24's prose (the CHANGELOG, the T08 spec notes, the support-matrix text). Only the diff summary was read, not the
  wording.
- `x05_reference.py`'s D2 implementation line by line: it was run (`--check` PASS) and its imports were checked, but
  it was not audited.
- What ADR 0069 §10 already disclaims: pre-X05 checkout bundles written off the lock, build identity under one version
  string, metadata against the imported module, Pythons other than 3.13 (`requires-python >=3.13` admits 3.14, whose
  closure is unmeasured), and the extras.
