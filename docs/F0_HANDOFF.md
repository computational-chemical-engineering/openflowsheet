# F0 handoff (2026-11-05, second engineer)

Branch `wp/F0`, worktree `.claude/worktrees/f0`. Brief `docs/briefs/F0-build.md`; choices `docs/F0_DECISIONS.md`.

## Done
- `.gitattributes` (87936afa); gate, registry, tests (5fa16527).
- M7 fixtures: 52 bundles written at tag v0.3.0 → `tests/fixtures/f0/v0.3.0-bundles/` (833e8093); tag worktree removed.
- M7, M8 implemented, registry re-recorded (M7/M8 insertions only), strict xfail dropped (141e824f).
- M9 scan follows composed identities into imported modules (22379998); set unchanged, 8 files.
- `--check` at ab97a46e: `F0 PASS: M1 50/50, M2 52/52, M3 52/52, M4 52/52, M5 52/52, M6 52/52, M7 52/52,
  M8 105/105, M9 8/8`. F0 tests: 14 passed (~90 s).
- Full gate at ab97a46e: FAIL, 4 failed (F0_DECISIONS.md, last entries).

## Open (blocking `status: tested`)
- D15: the committed v0.3.0 bundles trip three literal guards over `tests/fixtures`/`benchmarks`. Needs a ruling;
  default proposed: exempt archived replay bundles by structure in the three guards.
- D16: the evidence schema's `work_package` pattern refuses `F0`. Needs an id or a schema ADR. Draft manifest (status
  `implemented`) is outside the repo; regenerate it at the merge head once D15/D16 are settled.
- V17 budget test `test_f6_the_forty_runs_fit_their_budget`: 450.1 s (gate) and 344.0 s (alone) at load ~50; re-run on
  a quiet host. Budget untouched.

## Next
1. Apply the D15 ruling (isolated commit), run the three guard tests and `tests/test_f0_corpus_identity.py`.
2. Apply D16, write `evidence/<id>/<commit>/manifest.json` (form `evidence/S13/`), run `tests/test_evidence_manifests.py`.
3. `scripts/gate.sh` once on a quieter host; `status: tested` only if all four exit items pass.
4. Design-lane read of F0 (D9/D13/D14/D15 batched).
