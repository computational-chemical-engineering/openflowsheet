# Reviewer brief: ST — stream table and energy summary (0.4), the single review pass

Status: brief, 2026-11-08. Design `docs/design/ST-stream-table.md` (Amendment 5), ADR `docs/adr/0068-stream-table.md`
(Proposed; ADR 0019 Amendment 13), rulings `docs/roadmap/foundation-rulings.md` §17 Amendment 5 — all on main. Branch
`wp/ST`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`, head `6f55fc19` = main `00a508bd` + `wp/MSG`
`35403f42` merged (MSG is reviewed, waits only for Frank's `explain.md` read) + WO-1…6. Log `docs/ST_DECISIONS.md`
(D1-…D6-, E1), handoff `docs/ST_HANDOFF.md`. No manifest yet; CI run 42472248770 on `6f55fc19` in progress. A full
gate is running on another branch: **do not run one**. Do not spawn sub-agents yourself.

## The question

Does `wp/ST` implement the design so that the stream table is a read-only, computed-on-request view of a finished
run's bundle that changes no released number, hash, bundle byte, cache key or replay, reports every value it cannot
give as absent with a reason (never estimated), and closes its quoted checks honestly — and what are the rulings on
the batched D-items?

## Measured (engineers' numbers)

- Core (WO-1/2): G1 max |closure|/tol 1.34e-7, envelope gap 1.4e-10 W; G2 vf − lever 0.0 (bound 2.3e-7); G3 max rel
  error 3.8e-10 vs IAPWS-95 Table 8 at 450 K (from `s05_reference.json`); G7 41 bitwise (+193 SYN-001, 0 mismatches);
  G8 max passing ratio 1.8e-4, **G8 FAILS on g8/T05b:SC-1 (2016 W), strict xfail (E1)**; G10 44 served, 8 refused;
  G14 TH-C1 0.023 s; G16 syn001 32 R3, 2 flagged, 0 disagreeing.
- WO-3…6: G5 (codes vs MSG's real catalogue) PASS; G11 four transports + conformance on 5 clients PASS; G12 served MCP
  `eaff4585…` → `6705fb05…`, without the new tool = MSG's D_4 exactly (new chain link c_5), no existing R4-G3
  snapshot moved, `API_EXIT_CODES` unchanged; G13 F0 PASS M1–M9 and no diff under
  `verify/thermo/models/run/orchestrator` or `compiled.py`; G15 PASS; A48 PASS; catalogue 373 entries, 0 G4
  violations; targeted battery 569 passed, 1 xfailed (G8). Known red: description reviews (`explain` human;
  `get_stream_table.md` design lane + human).

## Rule on each

1. **E1** (most important): G8 on temperature-degenerate lifted splits (T05b:SC-1, 2016 W) — is the failure a
   defect in ST's energy summary, in the gate's statement, or a real property of that case to be declared? Note the
   engineer's finding that design D4's premise ("the split list is not derivable from `revision.json`") is false.
2. D1-1 (Python `sum` vs "from 0.0"), D1-3 (legacy-route unit ids, revertible commit 1d3c954c), D1-6/D1-7 (schema
   amendments to design §5), D1-10…D1-14 as you see fit.
3. D3-6 (no-bundle `not_found` text "Nothing named '<job>' exists"), D3-7 (c_5 names "ADR 0068" until a register id
   exists; MSG's R-942/R-943 collide with RP's — MSG renumbers at its merge), D4-1 (`energy form:<model>` vs design
   §6.4's `energy_form:<model>` because MSG's jargon lint rejects the latter), D5-2 (CLI resolves every elision; a
   nested array > 20 items is cut without the `truncated` flag).
4. The design lane's review of `src/openflowsheet/application/bindings/descriptions/get_stream_table.md` (the text an
   agent reads): approve or give exact wording edits. Record your approval in `REVIEW.json` only if that is the
   design lane's established act there (check how MSG's reviewer recorded `explain`); never record the human review.
5. The merge of `wp/MSG` into `wp/ST` (D3-1…D3-5): anything that will break when MSG lands on main and renumbers.

## Deliverable

`docs/reviews/ST-review.md`: verdict, must-fix, should-fix, one ruling per item, wording edits, what the review did not
establish. Commit on **main** (docs-only, named path, message `docs: ST review`, trailers `Co-Authored-By: Claude
Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`). Do
not edit `wp/ST` except the design-lane `REVIEW.json` act in item 4, if that is the established act. Never set
`reviewed`. Report ≤ 30 lines.

## Machine-load rule

TRS2: `uptime` first; targeted tests only, one at a time, `OMP_NUM_THREADS=1`; no full gate.

## Out of scope

MSG's own content (reviewed), OPT, RRC, X02, X04; the web shell (deferred, O3); style.
