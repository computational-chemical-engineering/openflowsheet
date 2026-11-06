# RP handoff (ADR 0055 WO-R1…R6, build lane)

Branch `wp/RP`, worktree `.claude/worktrees/rp`. Choices C-1…C-22, questions Q-B1…B5, Q-C1…C6 and every measured
number: `docs/RP_DECISIONS.md`.

## Done

- WO-R4 (`ci.yml`, REL.A17), WO-R6 (`release_rc.py` steps 1, 8, 17, items; WO-R6b `local`, `record`, `ci`,
  `records`), WO-R6c `scripts/release_evidence_manifest.py` (`3e7ccf00`): RP.S01–S22 read from RP §11.1, one
  `ITEM.<id>` check per `rc_items` entry, `--rel-a20` (REL.A20, §11.2). Tests `tests/test_rel_evidence_manifest.py`
  (14): the catalogue, S02/S05 controls, a passing record and controls for S10, S13, S15, S17, S20, S21, REL.A20 over
  0.3.0's records with 0.3.0's two CI views (`tests/fixtures/rel/s13-ci/`, byte-equal to what S13 read).
- REL.A20: 12 of 13 same-form equal S13's `pass`; RP.S18 differs by construction (Q-C5) → `REL.A20: FAIL`.
- Package manifest `evidence/S15/3e7ccf00…/manifest.json` (C-22: the schema refuses `RP`), status `implemented`
  (REL.A20 fail; the gate red only in the browser module), harvested (class P), `HARVEST_SIZE` (69, 945, 122).
- Full gate at `3e7ccf00`: 29 failed + 1 error, all `tests/test_m06_browser_smoke.py` (browser went away under
  load); the module alone: 31 passed.

## Not done (next, in order)

1. The one `reviewer` pass over WO-R2…R6: Q-B1…B5, Q-C1…C6. Q-C5 (REL.A20 unmeetable as written) and Q-C6
   (`REL040`/`RP` vs the frozen `work_package` pattern) need a design-lane ruling (an RP amendment / a schema ADR).
2. After the ruling: re-run `--rel-a20`, re-run the full gate on a quiet host (green browser module), re-take the
   manifest (`tested` only if both hold). Do not merge before; CI green on both legs before a merge.

## How to run

- REL.A20: `release_evidence_manifest.py --line 0.3 --commit a3e508e3 --k3 295a2e65… --ci-json
  tests/fixtures/rel/s13-ci/ci-run-41108983463.json --ci-json …41108983672.json --manifest-adr 0053 --manifest-adr
  0054 --evidence evidence/S13 --out SCRATCH/m.json --rel-a20 evidence/S13/a3e508e3…/manifest.json` (38 s).
- A release: `release_evidence_manifest.py --line 0.4 --commit C --k3 K3 --ci-run PUSH --ci-run DISPATCH
  [--manifest-adr N]` at a commit whose D2.4 trees equal C's.
