# ST handoff (wp/ST, 2026-11-08) — review fix round done; WO-7 next

**State.** Branch `wp/ST` (worktree `.claude/worktrees/st`) = main `00a508bd` + `wp/MSG` `35403f42` merged + WO-1…6 +
the fix round of `docs/reviews/ST-review.md` (brief `docs/briefs/ST-fix-round.md`). Not merged to main; ADR 0068
Proposed (Frank's acceptance pending, review amendments folded in); MSG still waits for Frank. Choices and numbers:
`docs/ST_DECISIONS.md` (§ "Fix round").

**Fix-round commits.** e2079456 M1 rule R1′ · 3a7fb9c3 S1 G8u + A02-360 attribution · faadfcc7 S2 `not_found`
variant · ae224c25 S3 description edits + design-lane review recorded · 69d5453f S4 recorded route · ee0de60f
rulings D1-1, D1-6/7, D1-10…14 in note/ADR · 16b90e93 D4-1 prose capabilities.

**Gates (fix round).** G8 PASS (xfail and guard removed; max ratio 1.76e-4). SC-1 envelope 2016.0 → 0.0 W,
U-VLV 2016.0 → 0.0; SC-3 U-VLV 2016.0 → 0.0, U-PHF −2016.0 → 3.64e-12 (tol 1.01e-3). G7 41 bitwise (R1′ streams
vs `_phase_enthalpy`). G8u: all 52 corpus runs are `judged_at: projection`, so only ratios (max 2.703, A02-360,
which is the projection: ST = `checks.enthalpy_flow` bitwise at the stored state). Served MCP digest c_5
`6705fb05…` → `ebb4ca84…`; `without_st` = MSG's `eaff4585…`. `catalogue.sha256` 8fa0c03e → 81d3a6aa (S2) → 7573d7ea
(D4-1). 44 served 0.3.0 documents: only SC-1, SC-3 move (M1); none move under S4. F0 PASS (M1 50/50 … M9 35/35).
G13: no diff under verify/thermo/models/run/orchestrator/compiled.py vs 6f55fc19. Targeted battery 457 passed;
**known red:** `test_every_description_is_reviewed_by_both_lanes` (2 open: `explain`, `get_stream_table` human).

**Open for the design lane (logged, defaults applied).** DECISION M1-1 (no-split flagged stream keeps
`phase_source: flash`, flag false), M1-2 (R1′ mixture-`h` provider uses `n·h` as γ–φ `_phase_flow`), M1-3 (Q4.R12
(b)(ii) dropped as dead), S1-1 (G8u compares only `energy_balance.<U>`). Fact: a flagged undeclared products-style
feed would get `flash_failed` though the verifier flashes it; no corpus/served case.

**Not done (review Notes, out of the brief's scope).** Untyped exceptions → `internal_error`; `_quote` null reason;
R1 empty split refusal; §4.4 dormant-row sentence; paging cost measurement.

**WO-8a (2026-11-08, brief `docs/briefs/ST-WO8a-ruling5.md`, ST_DECISIONS §WO-8a).** Merged main twice (`bf357867`,
then `5f66c3f7`); register equals main's (MSG = R-975/R-976; ST's duplicate R-942/R-943 dropped). Ruling 5 in
`stream_table._inputs`/`_decide` (R1′ on the split's own row; no-number on `temperature_degenerate_unlifted(S)`);
DC-1…DC-6 in `tests/test_st_core.py`; 44 served documents byte-identical; G7/G8/G8u unchanged; F0 PASS.
**WO-8b (2026-11-08, brief `docs/briefs/ST-WO8b-webshell.md`, ST_DECISIONS 8b-1…3).** 1fdb30ad A20 envelope lists
`get_stream_table` (23; ADR 0068 accepted by Frank 2026-11-08). 4d27b52e **ADR 0025 A1 escalated, not fixed**: SYN-001's
`data_sha256` hashes registered doubles; default proposed in 8b-2 (both `exact_sha256` in an ST addendum). 3d4a9057
streams screen shows the stream table (shell 18 operations; L-WEB-1; catalogue 3ac1279a…). Battery 2246 passed, 2
failed (the two A1 tests only); browser smoke 32 passed locally; node 98 pass; F0 PASS; ruff/format/mypy clean.

**Next:** design-lane yes/no on 8b-2, then apply it (one commit), then **WO-7** — evidence manifest, CI on both
architectures. When MSG lands: merge commit only; re-measure G12 (c_5/c_6 order vs X02), take main's register ids,
S2's one-hunk conflict in `api_errors.yaml`, re-take `message_entry` fixtures; OPT's ADDENDA order (`opt` vs `st`).
