# M07 review brief: the journey (WO-1, WO-2, WO-2b, WO-4) — design-lane `reviewer`, one pass

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m07`, branch `wp/M07` @ `d8ae8c1` (pushed). Write
`docs/reviews/M07-review.md`; rulings that change the spec go in `docs/derivations/M07-spec.md` as a dated amendment
section with register entries in `docs/decision-register.md` (next free numbers above R-451 that are unused here, on
`origin/main` and on `origin/wp/V02-alpha-gate`). Commit, push `wp/M07`. Never set `reviewed` in a manifest yourself.

## What to review
Spec §13 says: "A design-lane review of WO-1/WO-4 (journey numbers and labels) is one `reviewer` pass before the RC."
- Design authority: `docs/derivations/M07-spec.md` (sections on the rungs R0–R3, labels, A1.6 conditions l.650–690,
  §13 WO table, §18 Amendment 1 = rulings R-420…427, which overrides earlier text); ADR 0041 (journey, W25).
- Code: `scripts/m07_journey.py` (+ helpers it imports), `tests/test_m07_journey.py`, `tests/test_m07_journey_record.py`;
  `git log --oneline ee48ed9..d8ae8c1 -- scripts tests src` for the range (main merges inside it are not M07's).
- Build log: `docs/design/M07-build-decisions.md` J1–J30; handoff `docs/briefs/M07-wo4-handoff.md` (23 lines).
- Committed record: `benchmarks/m07/journey/1623633db5afd6a55e2807f848ad4cf6a84e71b3/` (`journey.json`, `journey.md`,
  `m05/`).

## Measured (session-verified reports)
- Journey at J=`1623633`, exit 0, ~55 min, `check` accepts. R0 INDIFFERENT at 673.15 K (stand-in; 9 solves VERIFIED,
  J 0.46705958492513017). R1 (PyMRM v3 grid) DECIDED at 653.15 K, BOUND_LOWER; nine points verified; J 0.45250 → 0.44531;
  indifference set [653.15]. R2 SURROGATE_NOT_PROMOTABLE (M04 verdict). R3: carry fails (src changed since M05's run
  commit) → M05 study re-run at J: DECISION_STABLE, T* = 653.1500351610193, J* = 0.4524965242483627, bitwise equal to M05's
  REAL record; T* re-solve reproduces J* bitwise (91 constraints). TC-1 HOLDS; P01 FE_CHANGED, P13 FE_UNCHANGED; decision
  `refined`, INTERIOR. Cold runs 36 + 48 + 4 = 88 of 460.
- The `8f85aa2` run gave bitwise equal numbers (only commit, tree_clean, walls, coupling digests, M05 re-run path differ).
- `replay`: bitwise in 13.4 s; refuses (exit 2) under `OMP_NUM_THREADS=2`.
- Gates: 9435 passed, 31 skipped at `c1f104f` and `d8ae8c1`; nlp tier 186/1; `-m pymrm` A24 replay test 1 passed.

## Open questions to rule on (engineer's defaults kept, no code changed for them)
1. **Label disagreement:** T* is 3.5e-5 K above the lower bound 653.15 K, so the at-bound test (tolerance 2e-5 K) reads
   INTERIOR, while R1's grid reads BOUND_LOWER. Default: report both as the rules give them. Is that consistent with the
   spec's label semantics, or should one label be derived from the other / the tolerance be scaled as M05's G9 (1e-6 scaled)?
2. **J22:** new limitation code `R3:carry_identity_differs`; condition 5 holds for a re-run record only once committed.
3. **J25:** `env.verify` lists `variant_id` as a difference despite R-259 (provenance only); `nlp-test-tools` on PYTHONPATH
   breaks the reactor check.
4. **J27:** replay takes walls, coupling digests, experiment counts once mapped to store hits, and R3's carry from the
   record rather than re-deriving them. Does that meet "replay reproduces every number"?
5. J24 (process): WO-4 part 1 gated only its tip; WO-4b gated each commit (J30). Note only.

## Not to spend time on
Packaging, CI, WO-3/WO-5…8 (not built), the 0.2.0a1 alpha (separate branch), M05's internals (reviewed in M05 §21).

## Deliverable
Review document with: verdict (merge-ready / fix first), must-fix items with `file:line`, rulings 1–4, anything a test
does not actually verify. ≤ 300-word report to the session.
