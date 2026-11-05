# F0 handoff (2026-11-05, third engineer)

Branch `wp/F0`, worktree `.claude/worktrees/f0`. Brief `docs/briefs/F0-build.md`; spec `docs/reviews/F0-review.md`;
choices `docs/F0_DECISIONS.md` (D17–D21 this round).

## Done (all review items)
- ADR 0059 D1 (13eac60b), Accepted after the manifest; D15 (1′) registered exemption, 36 per guard (acb90e9b);
  finding 3 (f5a878c9); D9 legacy unit modules by AST fallback, M9 8 → 35 (3853cc97); finding 1, committed M6
  request sample (fd92b41e); finding 2, +9 basis runs, TH-C2 stopped (8a733733); finding 4 (a783a219);
  finding 5 (205717b6, completed in ef1bf51a); notes 6, 7, 9 (ef1bf51a).
- `--check` at ef1bf51a: `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52,
  M8 105/105, M9 35/35`. F0 tests: 26 passed.
- Full gate at ef1bf51a: GATE PASS, 14866 passed, 3206 skipped (3:07:00), V17 budget test passed inside it.
- Manifest `evidence/F0/ef1bf51a…/manifest.json`, status `tested` (d0af0259); branch pushed for CI.
- CI run 42077157573 failed 3 tests (unharvested manifest, HARVEST_SIZE, M6 count off-platform); fixed in
  eba4bcb4 (gate GATE PASS 14872 passed, 2:25:04), re-take manifest `evidence/F0/eba4bcb4…` (D22, D23), harvested.

## Open
- CI on both architectures for `wp/F0` (review condition 2's CI half).
- D20: TH-C2 (CoolProp) needs the coolprop extra on the reference host; then add it to `BASIS_CASES`, re-record.
- Design-lane read of D17–D21; Frank's call on finding 2's scope (Wilson-column flowsheets not run).
