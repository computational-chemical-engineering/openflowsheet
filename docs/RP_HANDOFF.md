# RP handoff (ADR 0055 WO-R1…R7, build lane)

Branch `wp/RP`, worktree `.claude/worktrees/rp`. Choices C-1…C-29, questions and every measured number:
`docs/RP_DECISIONS.md`. The review: `docs/reviews/RP-review.md`.

## Done

- WO-R1…R7. The review's must-fix items M-1 (standing-mode fixtures, mutation 6 failed / 50 passed), M-2 (REL.A20)
  and M-3 (ADR 0055's restated acceptance) are applied; REL.A18 and A19 have tests (C-28).
- Code commit `fd28ff7b`: gate `GATE PASS` (15070 passed, 3206 skipped, 197 deselected, 3446 s); F0 PASS (M1–M9 equal);
  push CI `ci` 42320544169 (both `check` legs, `identity`, `default-install`) and `Site` 42320544186 green.
- `tests/test_rel_*.py` + `tests/test_release_workflows.py`: 230 passed. REL.A20: `REL.A20: PASS`.
- Manifest `evidence/S15/fd28ff7bc8e3e98c67857c869d6939d1d755f3ed/manifest.json`, status `tested` (never `reviewed`):
  REL.A01–A10 and A17–A20, the gate, F0, CI and its six limitations. The old `3e7ccf00…` manifest stays.
- Harvested (6 class-P items): `HARVEST_SIZE` (70, 951, 122); `t08_support_matrix.py --check` 0 problems.

## Not done (next, in order)

1. Merge `wp/RP` into `main` (orchestrator). Not merged here.
2. Before 0.4.0's K3: K-1 the schema ADR admitting `REL[0-9]{3,}` (so `evidence/REL040/` passes `t08.problems`);
   S-6 one background `release_rc.py local` with every step at a `main` commit after the merge (steps 6, 11, 12, 14–16
   and `E01-G6-nlp` have never run); K-2 Frank's acceptance of ADR 0055 on its restated condition, and F-8 (two
   messages, the second after `Judged`).
3. The review's should-fix items S-1…S-7 not recorded as closed in `RP_DECISIONS.md` stay open for 0.4.0's cut.
4. D2 (REL.A11–A16, A21, `release-audit`, WO-R5) is deferred and outside this acceptance.

## How to run

- REL.A20: `release_evidence_manifest.py --line 0.3 --commit a3e508e3 --k3 295a2e65… --ci-json
  tests/fixtures/rel/s13-ci/ci-run-41108983463.json --ci-json …41108983672.json --manifest-adr 0053 --manifest-adr
  0054 --evidence evidence/S13 --out SCRATCH/m.json --rel-a20 evidence/S13/a3e508e3…/manifest.json` (38 s).
- A release: `release_evidence_manifest.py --line 0.4 --commit C --k3 K3 --ci-run PUSH --ci-run DISPATCH
  [--manifest-adr N]` at a commit whose D2.4 trees equal C's.
