# RRC handoff (build lane; branch `wp/RRC`, worktree `.claude/worktrees/rrc`)

Design: `docs/design/RRC-revision-region-continuation.md` (§7 work orders, §8 gates); ADR 0072 (Proposed).
Review: `docs/reviews/RRC-review.md` (main, ed522d7c). Decisions: `docs/RRC_DECISIONS.md` (D-1…D-38). Rewritten in place.

## Done
- **WO-1…WO-5** (see `RRC_DECISIONS.md`); **WO-6** guide page `c6d3b9c6` (D-28).
- **WO-7 (review fix round)**, one commit each: M2 `3d225107` (D-29), S1 `fb77a26a` (D-30), S2 `b2c3cccd` (D-31),
  N1 `91f326c4` (D-32), S3 `d7db8b8a` (D-33), E3c `32f8099c` (D-34), `interfaces-frozen.md` `fcc352d8` (D-35),
  CHANGELOG `48ff72a0` (D-36), design note D-5/D-6/D-10 `de0e54b9` (D-37), L-COL-9 harvest note `f50f6b5c` (D-38).
  M1 was done on main by the orchestrator.

## Gates (2026-11-08, x86-64, after WO-7)
- F0 PASS: M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35.
- Edge-3 test files: WO-7 edits none; vs main only `test_t06_f4_literals.py` (D-4, WO-1).
- `tests/test_rrc_*.py` 71 passed. Touched/literal/doc/envelope/changelog/registry/edge-3 files: 187 passed.
  `test_t08_w2_recovery_edges.py` 26 passed (cited-node run included; it failed before E3c, D-34).
- ruff check + format clean; mypy (as `scripts/check.sh`) clean, 307 files; `t08_support_matrix.py --check` 0;
  `mkdocs build --strict` clean; `doc_pages.py --check` up to date. Full gate NOT run (orchestrator, after OPT).

## Next (not done; for the orchestrator)
- **Renumbering at ADR 0072's acceptance (S4):** R-RRC-1…6 → register numbers in the register and ADR 0072, AND in
  `tests/test_t08_b50_surface_content.py` `V02_ADDITIONS["solve_policies"] = {"RRC-revision-v1": "R-RRC-6"}`.
  ADR 0072 status line likewise at acceptance.
- ADR 0072 D5's bullet "`opening_state_sha256` equal to the source root's" is S1-consistent only read as "over the
  free columns"; align it with design §5.8 (amended) at acceptance — not edited here (ADR is design-lane text).
- Merge order (review item 6): OPT first; then rebase, rerun `test_rrc_*`, OPT's `final_system` tests, F0; one full gate.
- For `tested`: CI green x86-64 + aarch64; G8 on N1 **and C3** on both legs; G7 on aarch64; evidence manifest
  `evidence/RRC/<commit>/manifest.json` with the commands actually run. Never `reviewed` by the build lane.
- Merge also needs Frank's yes on FQ1 and ADR 0072 accepted. FQ3 re-asked on main (N2).
- `results-ref-x86-64.json` (measured at 40fba287) lacks the harness's new key `g2f_opening_equals_source_over_free_columns`;
  a future re-take adds it (D-30). Nothing registered moved.

## Review notes left as notes (no action ordered)
- R5 `ValueError` on a corrupt bundle's rerun; homotopy defect-guard omission; A3 dotted reason path freezes at release;
  G6 counters would differ by `spent'` where a refused opening spent property calls.
