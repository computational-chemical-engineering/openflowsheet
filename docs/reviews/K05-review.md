# K05 review — runs, replay identity and gate G05, against ADR 0007 and blueprint §8.3

**Reviewer:** Fable 5.1 (`fable-reviewer`), 2026-09-22. Plan §1.3: Fable reviews every Opus package
touching replay identity.
**Brief:** `docs/briefs/K05-replay-review.md`.
**Reviewed at:** `main` = `90b765f`, code as of `350676a` (the evidence commit); the gate
`PATH=.venv/bin:$PATH ./scripts/check.sh` run here: **1285 passed, exit 0**.
**Environment here:** x86-64 Linux 6.12.86, Python 3.13.5, scipy-openblas 0.3.28, thread variables
**unset** (they are pinned to 1 only in CI).
**Measured:** every finding below marked *measured* was produced by a probe script against the
live code on this machine, from a real `solve_and_bundle` of SYN-001 nominal. Nothing in `src/` or
`tests/` was changed.

---

## 1. Verdict

**The design is right and the implementation has four holes that let a changed environment, or an
edited archive, reach `exact_replay` / `MATCH`. Not yet `reviewed`.** The mode-before-rerun ordering
(D4) is correctly built and is the load-bearing idea; the correction CI forced (§3 of the brief) was
the right correction; the artifact index is built from bytes written; a tampered artifact is not
re-run. All of that is sound.

What plausible-and-passing hides is that the same correction that took `environment` and
`artifacts` out of the *identity* hash also took them out of the only *integrity* check the manifest
has, so the two fields that decide the mode are now the two fields an editor can change without
detection. Beside that: an absent lock hash compares equal to itself; a verdict-word change without
a near-threshold flag is filtered out of the verdict unconditionally; the production comparator does
not implement the numerical policy the manifest names; and a platform Frank did not choose is
registered. Each is a small change. Together they are the difference between "a changed dependency
cannot produce a silent pass" being a sentence and being a fact.

The verification has one structural weakness: the clean-replay test, the `exact_match.json`
fixture and the `K05.clean_replay` evidence all supply the archive *re-read from disk* as the
rerun, so they measure `differences(x, x) == []`. I re-solved for real and the answer is good
(bitwise identical on this machine, all three artifact hashes equal) — but the evidence does not
say so, and should.

Must-fix M1–M6, then re-run the evidence script and the CI pair, and I expect this to be
`reviewed` without a second pass. Two points are for Frank (§8).

---

## 2. Must-fix findings

### M1 — The manifest's integrity check no longer covers the fields that decide the mode

`src/process_runtime/run/bundle.py:152` checks the manifest against itself only through
`structural_sha256`, and `manifest.py:63` (`NON_STRUCTURAL`) now excludes `environment` and
`artifacts` from that hash. So an edit to either is invisible to `verify_bundle`.

*Measured.* Two inputs, both against a freshly written nominal bundle:

- Edit `environment.lock_sha256` in `run-manifest.json` to `"0"*64` and rewrite canonically →
  `verify_bundle(...).ok == True`; `replay(..., current=<environment with that lock>)` →
  **`exact_replay` / `MATCH`**. This is the direct answer to brief §1.2: a changed environment
  reaches a passing verdict by editing the recorded environment to match it, and nothing notices.
- Edit `solve-events.json` (a message), recompute its SHA-256, write it into `artifacts[...]` →
  `verify_bundle(...).ok == True`; replay with the edited document as the rerun →
  **`exact_replay` / `MATCH`**. The test `test_an_edited_manifest_disagrees_with_its_own_hash`
  passes only because it edits `policy_id`, which is structural.

The docstrings at `bundle.py:8-12` and `bundle.py:81-83` ("a manifest edited after the fact is
caught") are therefore true for ten fields and false for the seven that matter most.

**Correction.** Two hashes, two jobs. Keep `structural_sha256` as the R0 identity. Add
`manifest_sha256 = sha256(canonical_json(_base_document()))` over *everything* (all fields, both
hashes excluded), written by `write_bundle` and checked by `verify_bundle`. State its bound
honestly in the docstring: a self-hash catches an edit that did not recompute it, which is every
accidental edit and every careless one; it is not a signature and does not claim to be. (A
signature is a later package's — T08 — and needs a key.)

**What to measure.** The two inputs above must give `verify_bundle(...).ok == False` with
`run-manifest.json` in `tampered`, and `replay` must return `NOT_RUN`. Keep the `policy_id` test;
add both of these beside it.

### M2 — A verdict-word change is never a mismatch, flag or no flag

`replay.py:177` removes every entry matching `_is_verdict_only` from the list that decides the
verdict, and `_is_verdict_only` (`replay.py:209-211`) is a substring test on
`".verification_status:"` with no reference to whether a near-threshold flag exists. D4 says the
opposite: a verdict change *with* a flag is reported as `MATCH` plus
`verdict_changed_near_threshold`; a verdict change *without* one is an R0 difference and
`MISMATCH`.

*Measured.* Rerun = the archived certificate with only `verification_status` set to `"FAILED"`;
no check in either document has `near_threshold` (SYN-001 nominal has none, K04 A33). Result:
**`verdict = MATCH`**, `verdict_changed_near_threshold = ()`, and the difference is listed in
`differences` but not counted. A reader who trusts the verdict word gets a `MATCH` on a run whose
certificate says the opposite of the archive's.

In practice a changed verdict arrives with a changed check `result` and that *is* counted — but
the rule as written makes the verdict word itself worthless as an R0 field, and it is the one
field a reader looks at first.

**Correction.** Suppress a `verification_status` entry from `real` only when `_verdict_drift`
listed that artifact; otherwise it counts. Make the match path-exact
(`f"{name}<root>.verification_status:"`), not a substring at any depth. Then extend
`_verdict_drift` to D2.4's other two conditionally-R0 words — a per-check `result` where *that
check* is flagged, and `regularity.status` where any of its inputs is flagged — which is the
half of D2.4 the brief's §7.3 says is unexercised. Today a flagged check whose `result` flips is
`MISMATCH` (*measured*), which D2.4 says to report rather than fail on.

**What to measure.** The input above → `MISMATCH`. The same input with `near_threshold: true` on
one check in both documents → `MATCH` with the drift listed. A flagged check with `result`
flipped and everything else identical → `MATCH` with the drift listed; the same with the flag
absent → `MISMATCH`.

### M3 — An absent lock hash is "the same dependencies"

`manifest.py:147` records `lock_sha256 = ""` when `requirements.lock` is not found, and
`Environment.same_dependencies` (`manifest.py:112`) compares the strings, so `"" == ""`.
`_repository_lock` (`manifest.py:153`) walks the parents of `manifest.py` looking for the file —
which finds it under an editable install or a venv inside the repository, and finds nothing for
a package installed anywhere else.

*Measured.* `environment(lock_path="/nonexistent")` on both sides → `decide_mode` returns
**`exact_replay`**. So two non-editable installs with different SciPy versions, same
architecture, same Python, would call each other the same environment and compare under
`exact_replay`. The reason string even has a `'(none)'` branch for display, which shows the case
was seen and the comparison not.

Related and weaker: the lock hash is the hash of a *file in a source tree*, not of the installed
environment; `pip install --upgrade scipy` into the venv changes nothing it sees. The BLAS
identity, which *is* read from the installed SciPy, is not consulted (S3).

**Correction.** `same_dependencies` is `False` when either side is empty, with the reason "no
lock file recorded" / "no lock file found", and `decide_mode` returns
`inspected_archived_results`. Separately, derive the dependency identity from what is installed
(`importlib.metadata` versions of every distribution named in the lock, hashed canonically) and
record it beside the file hash; the file hash stays for attribution.

**What to measure.** Empty on either side → `inspected_archived_results` and a named reason.
Both present and equal → unchanged behaviour.

### M4 — `compare.py` does not implement the policy the manifest names

The manifest records `numerical_policy_id: K04-numerical-policy-v1`; ADR 0007 D2.6 says that
policy *is* `benchmarks/k04/reference_values.yaml` `numerical_policy` and that the comparison
code reads it from there. `compare.py` reads nothing from it: `RELATIVE_TOLERANCE` and
`REGISTERED_FLOOR` are inline (`compare.py:111,123`), still labelled "Interim, pending ADR
0007", and the two tables disagree in both directions:

| Path | YAML (the policy) | `compare.py` (what replay applies) |
| --- | --- | --- |
| `rcond_1` | 1e-14 | **1e-8** — six decades looser; two ill-conditioned certificates at 1e-9 and 1e-12 "agree" |
| `step_inf_scaled` | 1.03e-8 | absent → `ABSOLUTE_FLOOR` 1e-24 |
| `constant_mismatch` | 1e-2 | absent → 1e-24 |
| `u_diag_min_abs` | 1e-10 × `u_diag_max_abs` | absent |
| `merit` | 5.33889e-17 | 5.4e-17 (rounded looser) |
| `witness_max_diff` | **absent from the YAML** | 1e-7 |

And `ABSOLUTE_FLOOR = 1e-24` (`compare.py:143`), which D2.3 withdrew in as many words, is live
at `compare.py:261` as the fallback for any float the table does not name. K04 A32
(`tests/test_k04_schemas.py:190`) classifies schema floats against `compare.py`'s
`REGISTERED_FLOOR`, not against the YAML, so the drift between them is invisible to the test
that exists to catch it.

The `rcond_1` row is the one with a consequence: for a *lower* threshold the D2.2 argument
inverts — below `τ_ill` the value is the measurement (how singular), not the absence of one —
which is why the ADR floors it at the estimate's noise (`n ε`) and not at `τ_ill`. The code's
floor makes every pair of `ILL_CONDITIONED` certificates agree on `rcond_1` whatever it says.

**Correction.** `compare.py` loads the YAML table at import (the policy id, the relative
tolerance, the floors, with the two rule-valued rows — `u_diag_min_abs`, `check.value` — handled
by the existing `SELF_FLOORED` mechanism generalized to "floor from a sibling"); delete
`ABSOLUTE_FLOOR`, and make an unregistered float a *difference* ("`<path>`: unclassified float,
ADR 0007 D2.3"), never a tolerance. A32 checks the YAML's key set against the schemas. Add
`witness_max_diff` to the YAML with its provenance (K04 §4.8) in the same change — D2.3's rule.
`solve_and_bundle` reads `numerical_policy_id` from the same table rather than a literal.

**What to measure.** A32 passes against the YAML; a certificate with `rcond_1` 1e-9 against
1e-12 is `MISMATCH`; the nominal cross-architecture comparison is still `MATCH` (nothing at a
registered state sits within six decades of any of these floors).

### M5 — macOS arm64 is registered, and the recorded platform is never checked

`replay.py:40-42` registers `("arm64", "Darwin")`. Plan §4.2 K05 says *one of* {Linux aarch64,
macOS arm64}; Frank chose Linux aarch64 on 2026-09-22; ADR 0007 D3.3 says a certificate "does not
carry a promise about a platform outside the registered pair"; and the evidence manifest's own
limitation admits macOS arm64 "has never been exercised". `compatible_reproduction` is the R2
report — "supported differing environments" — and issuing it on a platform nobody has measured
is a false claim of support.

*Measured.* Recorded x86-64 Linux, current arm64/Darwin → **`compatible_reproduction`**. The
manifest's limitation text says "a bundle recorded there would be an inspection today"; it would
not — recorded s390x Linux, current x86-64 Linux → **`compatible_reproduction`** too, because
`decide_mode` (`replay.py:85`) checks only the *current* platform against the registry.

**Correction.** Remove `("arm64", "Darwin")`. Check both `(recorded.architecture,
recorded.os_name)` and the current pair; either outside the set → `inspected_archived_results`
with a reason naming which side. Then pin the constant to the CI matrix: a test that reads
`ci.yml` and asserts the registered set equals the set of runners' `(machine, system)` pairs,
so a registration without a measurement cannot recur silently (this closes brief §7.2).

### M6 — The clean-replay evidence measures the archive against itself

`scripts/k05_evidence_manifest.py:40-41`, `scripts/k05_schema_fixtures.py:44-46` and
`tests/test_k05_replay.py:218-226` all build the rerun as
`{name: read_artifact(directory, name)}` — the archived bytes, parsed. The evidence check
`K05.clean_replay` then records `bitwise_floats: true` and `differences: []` as a measurement.
It is `differences(x, x) == []`, and would report the same on a solver that returned a
different answer every call.

*Measured, and this is the number the evidence should carry.* A second `solve_and_bundle` of the
same flowsheet in the same process, compared against the first bundle: `exact_replay` / `MATCH`,
`bitwise_floats: true`, zero differences, and the three artifact SHA-256s **equal**
(`solution-certificate.json` `925d251738…`, `solve-events.json` `483faa68d8…`,
`solve-plan.json` `92f411bb1f…`). So on this machine, in one process, the solve is bit-repeatable
— which is exactly the observation D3.2 says to record and never promise, and nothing in the
package currently observes it.

**Correction.** The evidence script, the fixture generator and the clean-replay test re-solve
(a second `solve_and_bundle` into a second directory, its artifacts as the `Rerun`). Keep one
`differences(x, x)` case if you like, named as the tautology it is. Regenerate
`exact_match.json` and the evidence manifest from the re-solve.

---

## 3. Should-fix

### S1 — `structural_sha256` does not see the plan's structure, the event sequence or the solver counters — **needs a decision (Opus), recommendation below**

`plan_id` is a name (`orchestrator/tear.py:445`: label + policy id), `policy_id` is a name, and
the artifacts are excluded. So the hash covers ids, policy *names*, `check_policy_sha256`, the
outcome word and the verdict word. Two runs with different event sequences, different attempt
trees or different solver counters — all R0 by D1 — share an identity if their outcome words
agree. Brief §1.1 asked what is missing; this is the answer.

*Measured.* `SolvePolicy` with the same `policy_id` and `max_iterations_per_attempt + 1` → same
`structural_sha256`, same `plan_id`. The `SolvePolicy` has `as_document()` and no hash;
`CheckPolicy` has both.

Two readings of what the field means: (a) *the manifest's identity* — what ran, under which
policies, with what outcome — which is what it is today and should then be documented as such;
(b) *the run's R0 identity* — (a) plus a digest of the R0 projection of the artifacts, which is
precisely the document `scripts/k05_structural_identity.py` already builds. I recommend **(b)**:
it makes G05 a one-hash comparison with the identity document as its diagnosable preimage, it
is what a reader of the name will assume, and nothing is released so the field's meaning is
still free. Either way, add `policy_sha256 = sha256(canonical_json(SolvePolicy.as_document()))`
to the manifest as a structural field, mirroring `check_policy_sha256` — D1 says every
`SolvePolicy` value is R0, and today none is in the identity.

If (b): `Rerun` should also carry the rerun's manifest, so replay compares `structural_sha256`
first and reports it as the headline R0 result before descending into the artifacts.

### S2 — The structural hash and the G05 document are R0 only under D2.4's condition, and neither says so

`verification_status` and `outcome` are in the structural document; per-check `result` words
are in the G05 identity document. D1 makes these R0 **conditionally** — only when no quantity
they depend on is near threshold. At a near-threshold case the two registered platforms can
legitimately produce different `structural_sha256` values and a G05 `identity` failure that is
not a defect, with nothing in either document to say why. SYN-001 nominal has no flags (A33), so
this is invisible today and will surface the day a registered case lands in the band.

**Correction.** The identity document carries each check's `near_threshold` flag (a boolean, no
float) so a cross-platform `result` difference is diagnosable as D2.4 or as a defect; the CI
comparison treats a `result`/`verification_status` difference on a flagged check as a reported
drift, not a failure; and the manifest docstring states the condition on `structural_sha256`. If
S1(b) is adopted the same condition attaches to the artifact projection.

### S3 — The BLAS identity is recorded and ignored by the mode decision (brief §7.1)

`Environment.identity()` (`manifest.py:191`) is architecture, OS name, Python version. ADR 0007
D3.3 lists "BLAS vendor" as part of the platform identity K05 records; it is not in the tuple.
And the *version* is the one thing the lock hash cannot see when a wheel is rebuilt or the venv
is upgraded under an unchanged lock (M3). The measured non-portability enters at the
factorization, i.e. in the code the BLAS build feeds.

**Correction.** `blas["name"]` joins `identity()` (per D3.3, not a new decision). A differing
`blas["version"]` with everything else equal → `compatible_reproduction` at best, reason named.
This is my call as the ADR's author, answering the brief's doubt: yes, make the version decide;
the argument that "every runner upgrade becomes an inspection" applies to `os_release`, not to
the library the arithmetic went through, and the mode it produces is `compatible_reproduction`,
not an inspection.

### S4 — Extra rerun artifacts are ignored

`replay.py:164` iterates the *archive's* index; an artifact the rerun produced and the archive
lacks is never seen. *Measured:* a rerun carrying an additional `failure-bundle.json` beside the
certificate → `MATCH`, no difference. A rerun that produced both a certificate and a failure
bundle would be exactly the "never both" case `solve_and_bundle`'s docstring forbids.

**Correction.** After the loop, every name in `rerun.artifacts - manifest.artifacts` is a
difference: "the rerun produced an artifact the archive does not have".

### S5 — `compare.py` classifies by key name at any depth

`VOLATILE_FIELDS` and `PROVENANCE_SUBTREES` (`compare.py:175,180`) apply wherever the key
appears. Any future artifact with a key called `artifacts`, `environment`, `run_id` or
`hostname` at any depth is silently compared for shape only — the same silent-escape shape the
`state_sha256` suffix rule was adopted to avoid, in the other direction. The failure bundle
(blueprint §8.2: "replay identity", "evidence") is the likely first collision.

**Correction.** Anchor these to the root of the run-manifest and replay-report documents
(`<root>.environment`, `<root>.artifacts`, …) rather than to a bare key. Keep the suffix rule
for float digests, which was a deliberate choice with a stated reason.

### S6 — `solve_and_bundle` (brief §7.5)

Four things, all in `run/__init__.py`:

- `model_version` and `constants_sha256` are `""` when the solve failed before a plan existed
  (`__init__.py:67-70`). A failure bundle "includes … replay identity" (§8.2); two different
  models that both failed at planning would share `structural_sha256`. Both values are available
  from the compiled problem's metadata independently of the plan; read them from there.
- `CheckPolicy()` is constructed inside and not injectable; a run under a relaxation policy
  cannot be bundled through this entry point. Take `check_policy` as a keyword.
- `numerical_policy_id` is a literal (M4).
- `reproducibility_class` is the dataclass default `"R1"` on every manifest, never derived.
  Today no run uses an external provider so it is true; the field should be computed (R3 when
  any provider is external) or required from the caller, not defaulted to a claim.

And the placement: this is the application layer's job (K06) reaching into K03 and K04 from a
package `__init__`. Move it to `run/session.py` or leave it and mark it as K06's to replace;
either is fine, an `__init__` with `object`-typed parameters and four `type: ignore`s is not.

### S7 — Thread pins: unset on both sides is `exact_replay` — **FOR FRANK, see §8 F4**

`environment()` records `os.environ.get(name)`, so an unpinned machine records `None` for all
three, and `same_threads` compares `None == None`. *Measured here:* all three `None`, and the
committed fixture `syn001_nominal.json` has the same. Two unpinned machines with different core
counts therefore replay as `exact_replay`, while the effective OpenBLAS thread count — the
quantity D6 cares about — is unknown on both. D6 says "as set", so the code matches the ADR; the
ADR's gap is mine. The choice of default has a product-facing consequence and is held for Frank.

### S8 — Verification quality beyond M6

- `test_a_clean_replay_of_the_same_run_matches` and `test_a_rerun_that_actually_differs…` both
  pass with a comparator that ignored floats entirely; add one case where a float moved beyond
  D2 (`merit` × 2) → `MISMATCH`, and one where it moved within D2 (last-bit perturbation of
  `u_diag_min_abs`) → `MATCH` with `bitwise_floats: false`. Those two are the policy.
- `read_manifest` (`bundle.py:91-118`) is an explicit key list — a whitelist in disguise, which
  is what the removal-list design of `NON_STRUCTURAL` was chosen to avoid. A field added to
  `RunManifest` and `_base_document` but not here reads back as its default and every bundle
  carrying it fails integrity: loud, so tolerable, but a round-trip test
  (`as_document → read_manifest → as_document` equal) makes it a test failure instead of a
  field-day for whoever adds the next field.
- `test_the_ci_workflow_pins_threads_and_compares_two_platforms` asserts an `arm` runner exists;
  it should assert the registered-platform constant equals the matrix (M5).

---

## 4. Observations (no action required unless noted)

- **`bitwise_floats` (brief §7.4).** `fresh == archived` is Python equality; with canonical JSON
  normalizing signed zero (`canonical.py:247`) and refusing NaN, it coincides with canonical-byte
  equality in every case a bundle can contain. It *is* whole-document equality, so it is `False`
  on any structural difference — but then the verdict is `MISMATCH` and the flag is moot. Define
  it as `canonical_json(fresh) == canonical_json(archived)` per artifact, report per artifact, and
  the name is exact. No behaviour change on the registered case.
- **`hostname` is never populated** (`solve_and_bundle` does not set it; *measured* `''`). It
  is in `NON_STRUCTURAL`, tested for exclusion, and always empty. Populate it
  (`platform.node()`) or drop it; an always-empty provenance field is a field nobody will notice
  is empty.
- **`current=` in `replay()`** is a caller-supplied environment recorded as `current_environment`
  indistinguishably from a measured one. A one-word `environment_source: measured | supplied` on
  the report makes a test seam visible in the artifact it produces.
- **The G05 document is a subset of D1's R0 set.** Missing: event `trial_status`,
  `rejection_reason`, `message`, `alpha` (a power of two — R0 by D1, excluded by the no-floats
  rule); `eliminated_rows[].sign`; scales and bounds (registry floats, "declared, not
  thresholded" — R0 by D1, excluded by the same rule); certificate `transformations` and
  `check_policy_sha256`. An exact-comparison allowlist like A32's `EXACT_FLOATS` would admit the
  declared floats. Worth doing with S1(b); not a gap in what was claimed.
- **`differences()` floor threading.** The `floor` parameter is discarded at every dict level
  (`compare.py:239` rebinds it) and not propagated through lists (`compare.py:252`), so a float
  list under a self-floored key — the escalation's singular values, whose ADR floor is
  `n ε σ_max` — falls to the last-path-segment lookup, which for `values[3]` matches nothing.
  Reaches only the escalation path; fix with M4.
- **`python_version` at patch level** decides `compatible_reproduction` while `os_release` does
  not. Inconsistent, in the conservative direction; leave it.
- **`verify_bundle` `unexpected`** covers `artifacts/` only; a file dropped beside the manifest
  is not reported. Harmless — nothing reads it — but "a bundle that does not describe itself"
  should include its own root.
- **Migration.** A manifest with a field an older reader does not know reads as `tampered`
  (M1's second hash makes this stricter still). That is ADR 0002 D7's territory; note it there
  when the first migration arrives.
- **Performance.** Nothing here is on a hot path; documents are kilobytes. Not examined further.
- **G05's `identity` job** is sound: field-by-field over the union of keys, fails on any
  difference, prints both hashes, requires two documents. The two-runner `check` job must pass
  on both legs first (`needs: check`), which is right.

---

## 5. The four questions of brief §1

**1. Is the structural document the right set?** Nothing in it is non-structural;
`reproducibility_class` is a claim rather than a fact (S6) but a claim about the run is
structural. What is *missing*: the `SolvePolicy`'s values (S1, measured: a changed
`max_iterations_per_attempt` under the same id is the same identity), and — depending on what
the field is meant to mean — the R0 projection of the artifacts: plan structure, event sequence,
solver counters (S1). And the set carries two conditionally-R0 words without the condition (S2).

**2. Can a changed environment reach a passing verdict?** Yes, by three routes, all measured:
edit the recorded environment in the manifest (M1 — the integrity check does not cover it);
have no lock file on either side (M3); change the installed BLAS or any package under an
unchanged lock file (M3/S3 — the file hash is a proxy and the direct measurement is not
consulted). And a fourth on an unregistered platform, which reaches `compatible_reproduction`
rather than `MATCH` (M5). The belief in the brief — "the mode is decided before anything runs" —
is correct and survives; what does not survive is that the *inputs* to that decision are
trustworthy. After M1, M3, M5 and S3, I can find no route.

**3. Is the provenance/identity split drawn correctly in `compare.py`?** In direction, yes:
identity compared for value, provenance for shape, digests for shape, counts for kind, floats
under the policy. Two defects in mechanism: the policy it applies is not the policy the manifest
names (M4), and the split is by bare key name at any depth (S5). One thing to know: `replay()`
never compares the two *manifests* — only the artifacts — so the split governs the fixture test
today and replay only if S1(b) is adopted.

**4. What is wrong that no test you would write could find?** Three things, in the order I
would want to have been told:

- *The correction in brief §3 had a second half.* Removing `environment` and `artifacts` from
  the identity hash was right; but that hash was also the manifest's integrity check, and the
  test for integrity edits a field that happened to stay structural. A test written from the
  design ("edit the manifest, expect tampered") passes; only a test written from the threat
  ("edit the field that decides the mode") fails. M1.
- *The comparator and the policy drifted apart while the test that guards them reads the
  comparator.* A32 classifies against `compare.py`'s table, so the table and the YAML can
  disagree in both directions with every test green. M4. The tell was the comment still saying
  "Interim, pending ADR 0007" on code the docstring calls normative.
- *The clean-replay evidence is a tautology and the true number was never taken.* M6. The
  re-solve is bit-repeatable here; that is worth recording precisely because D3.2 says it is
  observed, not promised — and it was neither.

---

## 6. G05 and G03's replay half

**G05, first clause — "dependency change detected."** *Met as measured, not yet as claimed.* A
changed lock-file hash yields `inspected_archived_results` / `NOT_RUN` before any rerun, at the
decision function and end to end, on this machine and in CI. The limitations: the lock hash must
be present (M3), the manifest must be unedited (M1), and a dependency that moves under an
unchanged lock file is not a "dependency change" the gate sees (M3/S3). After M1 and M3 the
clause is met without qualification; S3 widens what "dependency" covers.

**G05, second clause — "two-platform structural equality."** *Met*, by the CI `identity` job on
run 35751016849 for SYN-001 nominal: every R0 field the identity document carries is equal
across x86-64 and aarch64, and both produce `structural_sha256 = 28e01eda…`. The limitations
are named honestly in the manifest and I add two: the equality is conditional on D2.4 (no
near-threshold flag; true at every registered state, K04 A33) and undeclared as such (S2); and
the `structural_sha256` equality is the weak half of the evidence — it covers ids, policy names
and two words — while the field-by-field comparison is the strong half (S1).

**G03, replay half — "serialized manifests … replay bundle."** *Met.* Two schemas with fixtures
generated from real runs and real replays (R-015), round-tripped, compared with provenance
excluded. The schemas' mechanics were not examined (brief §8). The fixture `exact_match.json`
must be regenerated after M6.

**Plan §4.2 K05 acceptance, "clean-environment replay."** Recorded `unsupported` in the
manifest, honestly. Whether that leaves K05 `tested` is Frank's (§8 F5).

---

## 7. What this review does not establish

- **Behaviour on any platform but this one and the CI pair.** All measurements here are x86-64
  Linux; the aarch64 numbers are CI's, read from the evidence manifest and the brief.
- **The JSON Schema mechanics** of `run-manifest` and `replay-report`, per brief §8.
- **That M1's second hash is a security boundary.** It is not, and the correction says so. A
  bundle that must survive a hostile editor needs a signature and a key, which is not v0.0.
- **The D2.4 drift path on a real near-threshold case.** No registered case lands in the band;
  everything about it here is by construction and reading (M2, S2). ADR 0007 Q1 is still open.
- **Anything about K03 or K04.** Both reviewed separately; read here only where K05 reaches
  into them (`solve_and_bundle`, the certificate's flags).
- **The fresh-container replay.** Not performed by the package and not by me.
- **Human numerical and process-modelling sign-off.** Pending, and not an agent's to claim.

---

## 8. FOR FRANK

Two points turn on judgement rather than on a technical fact. I have not chosen; the package
should carry the recommended default only if you say so.

### F4 — An unset thread variable: unknown, or equal to another unset one?

Today an unpinned machine records `None` for all three thread variables, and two such machines
compare equal (S7). Every developer replay outside CI is therefore `exact_replay` while the
effective thread count on each side is unknown and may differ. D6 says "as set" and the code
follows it; the ADR did not say what an unset variable means.

- **Option A (recommended default):** an unset variable is *unknown*, and unknown is never
  `exact_replay`; the mode is `compatible_reproduction` with the reason "thread count not pinned
  on the recorded / current side". Record the effective count (from `threadpoolctl` when
  importable, else `os.cpu_count()`) beside the variables so the reason can name it. Consequence:
  a developer who wants `exact_replay` locally pins the three variables, which is one line and
  is what CI already does.
- **Option B:** keep unset-equals-unset; record the effective count for attribution only.
  Consequence: `exact_replay` is reported on an unknown environment, which is the one report
  D4 reserves for a known one.

I would take A: it costs a developer one line and it keeps `exact_replay` meaning what the ADR
says. This is adjacent to ADR 0007 Q2 (an unpinned CI job), which is still open with its default.

### F5 — Does K05 stand `tested` with "clean-environment replay" recorded `unsupported`?

Plan §4.2 K05's first acceptance item is "clean-environment replay". The manifest performs an
in-process replay and a correct refusal in a changed environment, and records the
fresh-container replay as `unsupported` rather than claiming it — the honest choice. Whether a
package with one of four acceptance items unsupported is `tested` is a scope call.

- **Option A (recommended default):** accept `tested`, and make the container replay a named
  acceptance item of K06 (which already owns "complete CLI solve/inspect/replay") or of T08
  (which owns reference environments). The mechanism K05 owns is measured; what the container
  adds is the *installation* dimension, which is precisely where M3 lives and which K06's CLI
  is the natural vehicle to exercise.
- **Option B:** hold K05 at `implemented` until a replay from a container built only from
  `requirements.lock` has been run and recorded.

I would take A, on the condition that M3 is fixed first — a container replay today would find
M3, and the package should not need the container to find it.
