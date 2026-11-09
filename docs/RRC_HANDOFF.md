# RRC handoff (build lane; branch `wp/RRC`, worktree `.claude/worktrees/rrc`)

Design: `docs/design/RRC-revision-region-continuation.md` (§7 work orders, §8 gates); ADR 0072 **Accepted 2026-11-08**
(Frank), register R-990…R-995. Review: `docs/reviews/RRC-review.md`. Decisions: `docs/RRC_DECISIONS.md` (D-1…D-45).
Rewritten in place.

## Done
- **WO-1…WO-7** (see `RRC_DECISIONS.md`; WO-7 = review fix round, D-29…D-38).
- **Merge prep** (brief `docs/briefs/RRC-merge-prep.md`), one commit each: merge of `main` at `c1ced8a7` `ec858608`
  (D-39); no chain link, cache count 39 (D-40); ADR 0072 accepted, R-990…R-995, D5 wording `f7225336` (D-41); MSG
  catalogue G2 `d43e7af8` (D-42); ADR 0025 D2.3 no addendum (D-43); G8 test `ffc09015` (D-44); T08 B27 fix
  `62c4d980` (D-45).

## Gates (2026-11-09, x86-64, merge-prep head)
- Served MCP digest = main's D_6 `3fdc797a…` exactly: RRC is not a chain link; ST takes c_7.
- `test_rrc_*` (incl. G8), `test_opt*` (default env), recovery edges, surface chain/digest, global state (39),
  descriptions, R4-G3 files, `test_msg_*`: 685 passed, 21 deselected, 3 xfailed.
- `test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py`: 1119 passed, 2 skipped, 1 failed → fixed
  (D-45), file re-run 15 passed. ruff, format, mypy (328 files) clean. `msg_catalogue.py check` PASS (379 entries).
  F0 PASS (M1 50/50, M2–M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35). Full local gate not run (Frank's rule).
- G7 on both CI legs (default suite, no skip); G8 now `tests/test_rrc_g8_determinism.py` (N1, C3; R0 pinned at the
  x86-64 value, so aarch64 checks the cross-architecture half).

## Next (not done; for the orchestrator)
- CI green on x86-64 and aarch64 on the pushed head (watch `test_rrc_g8_determinism` on aarch64: a different R0 there
  is a G8 failure, not a pin to move).
- Evidence manifest `evidence/RRC/<commit>/manifest.json` (`tested`) with the commands actually run; never `reviewed`
  by the build lane. Then merge into `main`, F0 on `main`.
- `results-ref-x86-64.json` (measured at 40fba287) lacks the harness's key
  `g2f_opening_equals_source_over_free_columns`; a future re-take adds it (D-30). Nothing registered moved.

## Review notes left as notes (no action ordered)
- R5 `ValueError` on a corrupt bundle's rerun; homotopy defect-guard omission; A3 dotted reason path freezes at release;
  G6 counters would differ by `spent'` where a refused opening spent property calls.
