# M04 review (design lane, one `reviewer` pass) — `wp/M04` @ `3f99eee`

Date 2026-10-15. Subject: `git diff 37ae0adc..3f99eee -- src`, `tests/test_m04_*`, evidence manifest at `a9566a6`
(status `tested`, 57/58, A33 `not_applicable`), build log E10–E34. Authority: `docs/derivations/M04-spec.md` §3–§8,
§11, §18–§19; ADR 0036 (Am. 1, 2); ADR 0037. Rulings that change the spec are in its §20 (Amendment 3) and in
register entries R-360…R-369.

**Verdict: fix first.** Two must-fix items, each small. The conformal arithmetic is sound. q̂ is the k-th order
statistic with failed draws at +∞ inside n, and k = 114 of 118 tolerates n − k = 4. h_min is an exact integer tail.
The verdict function follows §7.3's order. The study maps every non-`ok` calibration or test draw to a null score.
E32's launcher change is sound. The two must-fix items are in the promotion trust boundary, not in the arithmetic.

## Must fix

**MF1. A surrogate that failed promotion enters a revision unchecked when its instance is added or renamed.**
`application/replacement.py:240-253`: `replacements()` takes only `set(old) & set(new)`. A surrogate-backed instance
that is new in the revision is never compared. This covers a renamed instance, an added one, and the first revision.
The binder accepts any manifest that its checker accepts (`revision_binding.py:1390-1412`), and a NOT_PROMOTABLE
manifest is internally consistent, so the checker accepts it.

- **Probe** (scratch test on WO-9's world; nothing committed): one `commit_change` with four `set` edits. It renames
  `reactor` to `reactor_b`, binds A18's rough surrogate (NOT_PROMOTABLE, `width_limit_exceeded`, q̂ = 1.61), and
  rewires S3/S4.
- **Result:** `committed`. The solve job ran and ended in an initializer failure, for model reasons.
- **Why it matters.** A solvable case would certify with a `surrogate_model` limitation. That limitation states a
  band and coverage numbers and no verdict (`verify/surrogate.py:84-104`).
- **What it contradicts.** ADR 0037 rejected a separate promote operation *because* "commit_change could still swap
  the model unchecked". §8.4 says a failed promotion is rejected.
- **Correction:** R-360 / §A3.1. Every surrogate-backed instance that has no checked replacement must have a manifest
  whose re-derived verdict is PROMOTABLE. Otherwise the change is rejected with `model_replacement_incompatible`,
  reason `surrogate_not_promoted(<instance>)`. New assertion A48.

**MF2. The checker does not tie the failure lists to the null scores, so a hand-edited manifest can be promoted.**
`studies/surrogate/manifest.py:541-686` re-derives q̂, H and the verdict from `calibration.scores` and
`evaluation.scores`. It never checks that `scores[i]` is null exactly when i is in `splits.<s>.failed ∪ incomplete`.

- **Probe** (scratch script on the committed WO-11 manifest): replace the 5 + 18 null scores by 0.1 and recompute
  q̂, H, L, the promotion block and the bound consistently. The derived verdict is PROMOTABLE (q̂ = 0.117,
  H = 282 ≥ 279), and `check_manifest` returns `[]`. The `failed` lists still name the 23 refused draws.
- **What it contradicts.** ADR 0037: "the facet re-derives it from the stored scores, so a hand-edited manifest
  cannot be promoted". It also contradicts §5.3's rule that a failed draw is never covered.
- **The same gap elsewhere.** A gradient centre's `status`/`errors` is not tied to `splits.gradient.failed`.
  `fit.training_ok` is not tied to the training count minus its failed and incomplete draws.
- **Correction:** R-361 / §A3.2. Three checker rules, plus three A24 mutations.

## Should fix

**SF1. The manifest (the surrogate's identity) depends on the BLAS thread count (E33).**
`quadratic.py:186-193` (`svd`, `qr`, `q.T @ y`). The docstring at `quadratic.py:8-9` reads as if the score were
BLAS-independent, but that holds only given the coefficients. Ruled in R-362 / §A3.3: pin the fit to one thread, and
restate A32. Do this in the same round as MF1–MF2: it is inert against `d65bb022…`.

**SF2. With no predictor, the record states two false reasons.**
`study.py:277-295` and `318-331`. An unidentifiable fit makes every calibration and test score null, so the record
says `band_not_finite` (q̂ = +∞, as if failures exceeded n − k). The centres are `not_evaluated`, so it says
`gradient_check_incomplete` ("a failed stencil experiment"). The verdict is right (IE), but both lists misstate
causes, and the checker agrees because `derived_verdict` repeats the mapping. **Needs a decision**, ruled in
R-363 / §A3.4: with no predictor, the score-, band- and gradient-dependent reasons are not evaluated. V01–V16 are
unchanged.

## Notes

- **N1.** `quadratic.fit_quadratic(..., scaling=SCALING)` (`quadratic.py:171`) gives a production signature a box v1
  default. A forgotten argument would silently fit in v1's z. E27 says every production call passes it. Make the
  parameter required, and let the tests pass `SCALING` explicitly (R-369).
- **N2.** `admission.surrogate_resolver` (`admission.py:371-382`) re-reads and re-hashes every stored manifest on
  each `resolve`. That is O(#manifests) file reads per bind and per replacement side. It is fine today; cache by
  `(relpath, sha256)` if the count grows.
- **N3.** WO-11's record keeps only the code `reactor_not_accepted(certificate)` per refusal. Which certificate check
  refused, and by what margin, is in the cached results, not in the record. R-364 hands that diagnosis to the
  parent's owner.
- **N4.** E32 is sound.
  - `launch` has three callers: `backends.py:323` (handshake), `backends.py:387` (experiment), and
    `jobs/worker.py:193`, a test hook whose job directory is absolute.
  - Logs record constant relative paths (`launcher.py:281-285`), so no record carries the resolved path.
  - At absolute, symlink-free paths, `resolve()` is the identity. At relative or symlinked paths the old keys were
    per-handshake, never hit, so nothing reachable is lost.
- **N5.** `ExperimentRunner.request` (`runner.py`, M04 diff) handshakes before a budget refusal. That launches a
  child but writes no experiment, so §5.4 holds. Failed handshake attempts are still written by the first `run`.

**Not examined:** the replacement facets other than `surrogate_evidence`/`derivatives`; the sampler and generator
(`plan.py`, `m04_reference.py`); the schemas beyond E26; `reactor.py`'s residual/Jacobian (A-tests cover it); the jobs
lifecycle; `scripts/m04_evidence_manifest.py`'s parsing.

## Rulings (batched)

| Item | Ruling | Action |
| --- | --- | --- |
| E10 | confirmed | none |
| E12 | confirmed (R-295's pattern) | none |
| E14 | confirmed, with wording | The `unit_models` statement adds: "no promotable surrogate of the real C1 reactor exists in v0.2 (L-row of R-365)" |
| E24 | confirmed: an erratum. A registered lower bound rounds down, so G5's it1 bound is 0.2084 | §A3.6 |
| E25 | confirmed | none |
| E26 | confirmed: an erratum to §A2.3's "no schema change" | §A3.6 |
| E27 | confirmed | N1: make `scaling` required in production signatures |
| E28 | confirmed (ADR 0036 D1′) | none |
| E29 | confirmed. `data[*].keys_sha256` are key digests, which are in E by R-325 | Name them in A47's evidence E, keeping the equality-to-manifest check (§A3.6) |
| E30 | confirmed | none |
| E32 | confirmed (N4) | none |
| E33 | **pin, not record** (R-362). The manifest is identity (`model.artifact_ref`). Recording an environment value in it would make identity depend on the host, and F4 says unknown is never exact | Fit under one BLAS thread. A49. A32 restated: bitwise at one platform, whatever the thread setting |
| 4.1 % refusals | **no amendment** (R-364). §5.3 registered the +∞ rule and its cost before the run. The refusals lie in the interior, so a box chosen to avoid them would be selected on the outcome. b2-it2/3 are not merely unrun: §5.5 rule 2 and A1.2's guard refuse them after `band_not_finite`. NOT_PROMOTABLE is iteration 1's honest end | A finding to the parent's owner: diagnose the 26 keys from cache. A new parent variant means a new study under a new amendment |
| E34 | **reversed in part** (R-365). The real verdict is user-facing, so it is E, not P | limitations[0] → E, with a new L-row. limitations[1] and the A33 check → B. limitations[2] → B, then S when R-362 lands. limitations[3] stays P |
| Q-A2.1 | stays open (R-366) | It closes only with A33's record on a PROMOTABLE real surrogate. That record must show no `surrogate_outside_reference_domain` limitation, with the H₂/N₂ coordinate's margin to box v2's face stated in binary64 |
