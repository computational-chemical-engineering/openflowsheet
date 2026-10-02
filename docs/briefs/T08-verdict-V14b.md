# Brief — verdict: V14 (b) on PTC-R1 (T08.B20–B23, B28; B21)

**To:** `verdict` (design lane). **From:** build lane, 2026-09-29. **Branch:** `wp/T08` at `b11d7b3` (`C_res`).
**Deliverable:** `docs/reviews/T08-verdict-V14b.md`: for each of B20, B21, B22, B23, B28 — MET / NOT MET /
INSUFFICIENT EVIDENCE / BLOCKED with reasoning, then V14 (b1) on PTC-R1 overall, and what the verdict does
not establish. Do not commit; write no code. Budget: the user is near a weekly usage limit — judge on the
registered criterion and the committed numbers; do not re-run the comparison.

## Criteria (registered; do not re-read after the result)

`docs/derivations/T08-build-first-spec.md`: §A4.3 (classes, radius 2e-3), **§A4.4 (the criterion)**, §A4.6
(git order), §C.1 rows B20–B23 as replaced by **§Am1.C** (B21 with the C-trace clause; B28 new), and
**Amendment 2** (§Am2: P-budget wording; B21's clauses "no run ends `BUDGET_EXHAUSTED` on property calls; every
run opens exactly one attempt; either is `BLOCKED`, never `FAIL`"; the P-trace erratum: B21's 1e-10 governs).
Registered platforms: `ref-x86-64` and `ci-aarch64` (each must pass; Frank's Q-A2). `ci-x86-64` is an extra,
reported. Criterion excerpt (§A4.4):

> `S_a = {g : class_a(g) ∈ {LOW, HIGH}}`. V14 (b1) holds on PTC-R1 iff, on each registered platform: route (a)
> holds (§A3; B11–B15 pass); `S_ptc ⊄ S_newton`; the saddle clause holds: `class_ptc(g) ≠ MID` for all 441
> starts, with the mechanism B14 passing.

## Evidence

- Git order: `C_reg` `9f5f29d` → `C_A1` `30243f9` → `C_case` `c337fa1` → `C_res` `b11d7b3`. `case.json`
  (sha256 `cfa994fe…` as recorded in the results) recomputes (`python -m benchmarks.t08.ptc_r1.compare
  --check-case`). Test `tests/test_t08_ptc_r1_case.py` checks the ancestry and that no results file exists before
  `C_case`. Allowed pre-result activity is recorded in `docs/T08_DECISIONS.md` and `docs/reviews/T08-review.md`
  (the reviewer's one LOW-root probe per arm after `C_case`, not a registered start). A first local
  `ref-x86-64` invocation at `8d311b9` ran but wrote nothing (missing output dir) and was re-run unchanged
  (commit message of `b11d7b3`).
- Results (committed): `benchmarks/t08/ptc_r1/results-{ref-x86-64,ci-aarch64,ci-x86-64}.{json,md}`. ci-* from CI
  run 36590634080 at `4e92e0d`; ref from a local run at `8d311b9` (tree clean). The `.md` summaries give, on all
  three classes identically:

| arm | LOW | MID | HIGH | FAIL | accepted steps | property calls |
| --- | --- | --- | --- | --- | --- | --- |
| newton | 113 | 161 | 166 | 1 | 2706 | 18046 |
| ptc | 182 | 149 | 109 | 1 | 4520 | 35162 |

  B21 facts (each class): runs 882, crashes 0, converged_unclassified 0, converged_not_verified 0,
  runs_without_c_final 0, c_final max deviation ≤ 1.07e-16 mol/s, runs_with_c_blockers 0, unattributed bound
  blocks 0, budget_exhausted `{ptc_steps: 1}`, runs_without_exactly_one_attempt 0, max attempts 1, max property
  calls per run 1402. "Starts PTC reaches and Newton does not: 84; PTC MID starts: 149."
- Route (a): B11–B15 pass (`tests/test_t08_kinetic_cstr.py`, check.sh green at `3054942`, 6496 passed); B28 is the
  generator's (`t08_build_first_reference.py --check`, 570/570).

Verify the table's numbers from the JSON yourself (they are the harness's); confirm the per-start class maps
agree across platforms, and read the one FAIL per arm and the `ptc_steps` budget end.

## Out of scope

V14 (a)/(c), V13, the release gates other than V14 (b), and any redesign. If the result suggests a follow-up (e.g.
whether PTC's MID reports are a property of the method or of the harness), state it as what the verdict does not
establish; do not propose a new criterion.
