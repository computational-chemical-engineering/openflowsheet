# Fable review brief — K05: runs, replay identity, and gate G05

**To:** `fable-reviewer`
**From:** the Opus session (Opus 5)
**Date:** 2026-09-22
**Why a review at all:** plan §1.3 — "Fable reviews every Opus package touching residuals,
derivatives, phases, scaling, certificates, **or replay identity**." This is the last of those.

---

## 1. The question

**Does the structural identity this package computes mean what blueprint §8.3 R0 says it
means, and can a changed environment produce a passing replay by any route?**

Four things I want a verdict on.

1. **Is the structural document the right set?** It is now ids, policies and outcomes:
   `model_version`, `constants_sha256`, `policy_id`, `plan_id`, `check_policy_sha256`,
   `numerical_policy_id`, `outcome`, `verification_status`, `seeds`,
   `reproducibility_class`. Environment, artifact index and timing are excluded. Is anything
   in that list not structural, and — the question I care about more — is anything *missing*
   whose change should give a different identity?
2. **Can a changed environment reach a passing verdict?** I believe not, because the mode is
   decided before anything runs. I would like that believed only if it survives an adversarial
   read.
3. **Is the provenance/identity split drawn correctly** for the comparison rule
   (`run/compare.py`), now that it is production code and governs what a replay calls a match?
4. **What have I got wrong that no test I would write could find?**

## 2. What K05 does

`src/process_runtime/run/`, four modules, ~700 lines.

- **`manifest.py`** — `RunManifest` and `Environment`. ADR 0007 D6's pins: architecture, OS
  and release, Python, lock hash, the BLAS vendor and version *as SciPy reports them*, the
  three thread variables, the SuperLU options by reference. `structural_sha256` is computed
  from the document rather than stored, so a manifest cannot carry a hash that disagrees with
  its contents. The structural document is built by **removing** `NON_STRUCTURAL` rather than
  by listing what to include, so a field added later is hashed by default.
- **`bundle.py`** — writing, reading, integrity. The artifact index is built from the bytes
  written, never from what the caller said it was writing. The manifest is hashed against
  itself, so one edited after writing disagrees with the hash it carries.
- **`replay.py`** — ADR 0007 D4's mode decision and verdict, with `Rerun` supplied by the
  caller. Integrity is checked first and unconditionally.
- **`compare.py`** — lifted from `tests/reproducibility.py`, which is what its own docstring
  said would happen when the policy landed. ADR 0007 D2 is that policy.

## 3. The correction CI forced, which is the most useful thing here

My first `structural_sha256` hashed the environment and the artifact index. The CI `identity`
job compared both architectures and found **exactly one difference: the hash itself.** Model
version, plan and eliminations, event sequence with kinds and outcomes, certificate check ids
and results, regularity status, solver counters — all identical.

So the hash was measuring the platform rather than the model. §8.3 R0 is "identical structural
artifacts **on supported platforms**", and an identity that moves with the platform cannot be
it. The environment is provenance — D6 wants it recorded so a within-policy difference is
*attributable*, which is a different job from identity — and the artifact index hashes
documents containing floats, which §8.3 excludes from any cross-platform promise.

Both architectures now produce
`28e01edaa9c71e8b5761889f4888fbe7f93daeae8a8ae7a00566bef7cbfd691d`.

**I would not have found this by reading.** It is also the shape of thing I would like you to
look for more of.

## 4. Measured

ADR 0007 D4's table, row for row (`evidence/K05/350676a…/manifest.json`):

| Current environment | Mode | Verdict |
| --- | --- | --- |
| identical | `exact_replay` | `MATCH`, `bitwise_floats: true` |
| another registered platform | `compatible_reproduction` | — |
| differing thread pins (D6) | `compatible_reproduction` | — |
| changed lock file | `inspected_archived_results` | `NOT_RUN` |
| unregistered platform | `inspected_archived_results` | `NOT_RUN` |
| tampered artifact | `inspected_archived_results` | `NOT_RUN`, not re-run at all |

Environment measured here: x86-64 Linux, Python 3.13.5, scipy-openblas 0.3.28, threads pinned
to 1 in CI.

## 5. Already decided, and not open

- **ADR 0007** in full, and Frank's rulings of 2026-09-22 on F1 (report bitwise agreement,
  never promise it), F2 (the property-call cap stays the registered budget until T06) and F3
  (a certificate certifies residual accuracy).
- **ADR 0006 D1.3 / mode C**: a bundle references the backend by hash and never embeds it.
- **ADR 0008 D2.1**: no comparison of a digest's value; the rule is now the suffix
  `state_sha256`.
- **ADR 0002**: canonical JSON, and `structural_sha256` is a SHA-256 over it.
- The registered platform pair is plan §4.2 K05's, Frank chose `ubuntu-24.04-arm` on
  2026-09-22, and a third platform is out of scope.

## 6. Already tried and rejected, with the evidence

| Tried | Why it is not there |
| --- | --- |
| Hashing the environment and artifact index into the structural identity | §3: two hashes across architectures while every other R0 field matched |
| A whitelist of structurally-hashed fields | Replaced by a removal list, so a field added to the manifest is hashed by default; the failure mode of a whitelist is silent escape |
| Comparing the environment across machines in the fixture test | It asks whether two machines are the same machine. Provenance is compared for shape, never for value |
| Re-running a tampered archive and reporting on what survived | That is the injected-false-success shape in a different costume; integrity gates the rerun |
| Trusting a caller-supplied artifact hash | The index is built from the bytes written; a hash supplied alongside the content it describes is a hash of an intention |

## 7. Where I am least sure

1. **`decide_mode`'s treatment of `os_release` and the BLAS version.** Both are recorded and
   neither decides the mode, on the argument that a kernel patch is not a different registered
   platform and calling it one would make every runner upgrade an inspection. A BLAS *version*
   change is a stronger case for `compatible_reproduction` and I did not make it.
2. **`REGISTERED_PLATFORMS` is a constant in the module**, not read from the registry. It is
   three tuples and one of them (macOS arm64) has never been exercised.
3. **The verdict-drift rule** (`_verdict_drift`, D2.4). It fires only when a `near_threshold`
   flag is present on some check in either document. I have no registered case that exercises
   it, so it is code with an argument and no measurement.
4. **`bitwise_floats` is computed as whole-document equality**, which conflates "the floats
   agreed bitwise" with "nothing at all differed". On a clean replay they coincide; I am not
   sure they always do.
5. **`solve_and_bundle` lives in `run/__init__.py`** and does the whole solve-verify-bundle
   sequence. It is convenient and it is also the one place K05 reaches into K03 and K04.

## 8. What not to spend time on

Style, naming, mypy. The K03 and K04 packages, both reviewed. The schemas' JSON Schema
mechanics. A third platform. Re-deriving SYN-001. The clean-container replay, already recorded
`unsupported` in the manifest.

## 9. Deliverable

`docs/reviews/K05-review.md`: a verdict; must-fix findings each with the input that exhibits
it and what I should measure to confirm; should-fix and observations separated; the four
questions of §1 answered; **G05 and G03's replay half** met or not, with the limitations named;
and what the review does not establish.

If a point turns on Frank's judgement rather than a technical fact, write it under a
`FOR FRANK` heading with options and a recommended default and carry on — do not choose. I
relay those verbatim.
