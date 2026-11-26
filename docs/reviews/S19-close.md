# S19 close note: repo-wide code health

**Closed:** 2026-11-21. **Merged into main:** ceb38cec (Decision Desk card `ofs-s19-merge-main`, choice A, verified
and executed; F0 PASS on main). S19 is part of 0.5.0. **End gate:** G-END PASSED at 043879a4
(`docs/reviews/S19-G-END-verdict.md`, verdict commit 15e1e147). Written by the build-lane orchestrator; it records
outcomes and open items and settles no design question.

## Outcome against the baseline

Scope `src/openflowsheet/*`, baseline CB = d90b498f (main after S17), tool pin `34a30bf` (cross-checked with
`d542005`, the pin at registration).

| measure | CB d90b498f (trial scan, 2026-11-14 pin) | G-END 043879a4 | G-END threshold |
| --- | --- | --- | --- |
| debt | 6370.9 | 1878.4 | <= 1900 |
| health (NLOC-weighted) | 7.3 | 9.06 | >= 9.0 |
| brain functions | 44 | 0 | 0 |
| lowest file health (files below 7.0) | 1.0 (42 files) | 7.0, `models/syn001/column.py` (0 files) | >= 7.0 |
| import cycles at depth 4 | 10 (79 cycle edges) | 0 | 0 |
| layer and forbid violations | 14 | 0 | 0 |
| file smells | 59 | 48 (47 duplication, 1 `large_file`) | not bounded |

Behaviour: F0 PASS 9/9 at the tip, M7's 52 values identical to CB, MCP digest by E1 to E5. User-visible identity
changes are those of ADR 0077 (verdict T4; CHANGELOG `## Unreleased`).

## Findings on the criterion (verdict C1 to C4): disposition

These are questions about how a future end gate is written. They do not reopen G-END. Each is a design-lane item for
the next code-health campaign's gate registration; none is settled here.

| # | finding | disposition |
| --- | --- | --- |
| C1 | E2 does not class a merge of main that must regenerate a digest of both sides | open, design lane: add the verdict's ruling on 68abf467 (generator-forced, recomputed, `--check` clean) as E2 text |
| C2 | the G-END row names no instrument version; the tool was re-pinned after the thresholds were set | open, design lane: future gate rows record the tool pin. S19_RULES "Settled" now names `34a30bf` (T6 fixed in this commit) |
| C3 | the scan clauses do not bound file smells (the region.py duplication of 2aaa5d3f was caught only by CI's ratchet) | open, design lane: whether an end gate carries "no new file smell against CB" |
| C4 | "full suite" is not defined against the nlp marker or the gates' budget deselections | open, design lane: name the collection in the gate row (G-END's run: default collection minus the two wall-time budget tests, T5) |

## Limitations carried into the release report

Verdict T1 to T7 travel unchanged into the S19 manifest and the 0.5.0 release report: T1 the E2 ruling on 68abf467;
T2 WO-N4's W5-S3/S4 evidence is the verdict's rerun; T3 43dccc21 and b1d2ae6a as post-K generator-only commits; T4
ADR 0077's user-visible identity changes; T5 the local full suite's collection and the nlp-marked suite outside
G-END; T6 the tool pin (fixed in S19_RULES); T7 48 file smells.

## Open after S19

The build-lane and design-lane items listed in `docs/S19_STATE.md` ("Open build-lane items", "Open for the design
lane", "Open after S19 (F1)") stay open; none blocks 0.5.0. The trailing item behind 0.5 (232 pre-S19 broken
references in living docs, card `ofs-s19-w4-docs-scope` A) stays trailing. S18 waits for Frank.

## Housekeeping

- Gate runner: stopped when no campaign needs the S19 gate queue (`kill $(cat <queue>/runner.pid)`).
- The docs-only log commits on `wp/S19` after 9fb4d5df (this note among them) go into main with the next REL050
  merge or after the v0.5.0 tag; the D2.4 freeze covers only `src/`, `schemas/` and `benchmarks/`.
- Worktrees s19-g1o8 and s19-g3 hold branches that are not ancestors of `wp/S19`; keep until Frank rules on them.
