# LINE06 state: the 0.6 line (F2, F8, X06, then the 0.6.0 release)

Rewritten in place. History: `docs/LINE06_DECISIONS.md` (append-only, grep it). Rules: `docs/LINE06_RULES.md`.
Procedure: `.claude/skills/line06/SKILL.md`. Host SMM-TR09 (`ref-x86-64`); orchestrator session OpenFlowsheet-TR09.

## Objective

0.6.0 released with F2 (ADR 0062), F8 WO1 to WO3 and WO5 (ADR 0067) and X06 (ADR 0078), per R-1070 and ADR 0057
Amendment 3. Line acceptance: a v2 revision with store-pinned records solves on the legacy route on all three OSes;
the ADR acceptances of card `ofs-line06-adr-clause`; X06's exits.

## Position (2026-11-26)

- `main` = the planning commit (local; last pushed head `4c7d3d6a`, 0.6.0.dev0). Cleanup done: every secondary
  worktree removed (all clean and contained in `main` or a kept branch), the S19 gate-queue daemon stopped, wp/REL050
  and wp/S19 log commits merged (docs only). No job of this campaign is running.
- Plans updated: R-1070; ADR 0057 Amendment 3; `roadmap.md` 0.6, new 0.7, 0.8 to 0.10; line notes in ADR 0062 and 0067.
- `release/lines/0.6.json` DRAFT (LINE06-L0): loads clean, `line_release` 0.6.0, release tests 406 passed. Field
  reasons and what LINE06-L1 must still design: `docs/briefs/LINE06-line-0.6.md`.
- Decision Desk: the three cards settled (below). F2-WO1 and D1 running.

## Order and gates (pass criteria fixed before the run; the orchestrator judges each, a miss is recorded as a miss)

| # | Step | Who | Pass criterion |
| --- | --- | --- | --- |
| P1 | F2 premise check: every file, function and interface ADR 0062's work orders name exists as named after S19 (ADR 0076) and F3 | orchestrator | a table in the log with 0 unresolved rows, or a STOP to the design lane |
| F2 | wp/F2, WO1 to WO6, then WO7 close-out | opus-engineer (WO1 to WO6), sonnet-implementer (WO7) | E-F2-1 to E-F2-10 pass; F0 PASS (all nine checks); tests touched pass locally; manifest `tested` |
| F2r | one `reviewer` pass on wp/F2, fix round | reviewer, then engineer | no open must-fix |
| F2m | ADR 0062 Accepted (card), CI green on every leg at the pushed head, merge, F0 on main | the user, orchestrator | card VERIFIED; CI `success` on all four OS legs; F0 PASS on main |
| D1 | X06 architect pass: ADR 0078 Proposed with work orders and exits | architect | ADR committed; ADR 0056 row 8 in full (card A); every deferral argued |
| F8 | wp/F8, WO1 to WO3 (after F2-WO4 and WO6 on wp/F2), WO5 | opus-engineer; sonnet-implementer for WO5 with an Opus review | E-F8-1 to E-F8-6, E-F8-8, E-F8-10 pass; F0 PASS; manifest `tested` |
| F8r, F8m | reviewer pass; ADR 0067 Accepted; CI; merge; F0 | as F2r, F2m | as F2r, F2m |
| X06 | wp/X06 per ADR 0078's work orders, after its acceptance | opus-engineer / sonnet-implementer | ADR 0078's exits pass; F0 PASS; manifest `tested` |
| X06r, X06m | reviewer pass; CI; merge; F0 | as F2r, F2m | as F2r, F2m |
| L3 | the line clause: the registered v2 case lowered and solved on the Linux, Windows and macOS legs | CI | `r0_sha256` and `state_sha256` equal to the v1 run's on every leg (ADR 0062 D8, E-F2-3) |
| R | REL060: LINE06-L1 (specifier), K3, J, C, RC steps 1 to 17, verdict, ledger, H1, step 18, merge, dry run, dispatch | rel050 skill's order | step 18 `v0.6.0 tag may be proposed: YES`; release run `success`; PyPI approved by the user |

Parallelism: at most two agents. F2 first; D1 runs beside F2 once the X06 scope card is answered; F8-WO1 can start
once F2-WO4 is on wp/F2 (F8 branches from wp/F2's head, merges after F2).

## Next action

Done: D1, F2-WO1 (with a recorded miss, fixed by WO2b), F2-WO2, F2-WO2b, X06-WO1 (log). Running (the cap of two):
`opus-engineer` on F2-WO3 (worktree `f2`, `docs/briefs/LINE06-F2-WO3.md`: chain link c_11 then ids and layout) and
`opus-engineer` on X06-WO2 (worktree `x06`, `docs/briefs/LINE06-X06-WO2.md`, plus chain link c_12 by message). On each
report: `git -C <worktree> status`, ListAgents, judge on the brief's acceptance (surface suites included), re-run F0 on
the branch, log. Next briefs: F2-WO4 (revision v2), X06-WO3 (solve policies). Cards open: `ofs-x06-accept-adr0078`
(verify with the pinned text in the log), `ofs-x06-mcp-clients`. After Q1: R-110 status line, roadmap resume move,
target-architecture X06 row. F2 ruling round (batched, at F2's reviewer pass): WO1-4, WO1-1, WO1-9, M = 1 for kg,
WO2-1, WO2-7. X06 reviewer: WO1-1 (unused serve functions), stateless tools/call without initialize.

## Decisions settled (Decision Desk, 2026-11-26, each choice A, VERIFIED, `executed` written)

- `ofs-line06-rest`: new 0.7 "multiphase core and generic units"; dynamics 0.8, design toolkit 0.9,
  batch/relief/synthesis/electrolytes 0.10; 1.0 unchanged. Applied in `roadmap.md`, ADR 0057 Amendment 3, R-1070.
- `ofs-line06-adr-clause`: the 0.6 line acceptance requires ADR 0062, 0067 and 0078 Accepted; 0063 to 0065 to 0.7,
  0066 to 0.8. Applied likewise.
- `ofs-line06-x06-scope`: X06's architect pass designs ADR 0056 row 8 in full, in its order. In the D1 brief.

## Open decisions (later, not yet requested)

ADR 0062 acceptance (before F2m), ADR 0067 (before F8m), ADR 0078 (after D1); each merge; the release cards.

## Estimate (extrapolated, not measured)

About 16 work orders plus 1 architect, 3 reviewer, 1 specifier and 1 verdict pass: 1.5 to 2.5 weeks of wall clock,
about 8 to 12M tokens. Baseline: F1 (7 WOs, 14 h) and F3 (6 WOs, 2.5 days) from ADR to merge.

## Anchors

ADR 0062 work orders `docs/adr/0062-F2-material-model.md` (section "Work orders"), exits ("Exit tests"); ADR 0067
the same sections; ADR 0056 row 8 (X06's scope); `release/lines/0.6.json`; `docs/briefs/LINE06-line-0.6.md`;
`scripts/release_gate.py` `load_line`, `line_problems`, `line_release`.
