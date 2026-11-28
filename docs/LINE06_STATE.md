# LINE06 state: the 0.6 line (F2, F8, X06, then the 0.6.0 release)

Rewritten in place. History: `docs/LINE06_DECISIONS.md` (append-only, grep it). Rules: `docs/LINE06_RULES.md`.
Procedure: `.claude/skills/line06/SKILL.md`. Host SMM-TR09 (`ref-x86-64`); orchestrator session OpenFlowsheet-TR09.

## Objective

0.6.0 released with F2 (ADR 0062), F8 WO1 to WO3 and WO5 (ADR 0067) and X06 (ADR 0078), per R-1070 and ADR 0057
Amendment 3. Line acceptance: a v2 revision with store-pinned records solves on the legacy route on all three OSes;
the ADR acceptances of card `ofs-line06-adr-clause`; X06's exits.

## Position (2026-11-28, ~05:45)

- **F2** merged (`f1fdda2b`). **X06** merged (`9532829b`). main pushed at `9532829b`; local main ahead (docs only).
- **F8** (ADR 0067 + ADR 0019 Amendment 12 Accepted): full gate PASS; wp/F8 `d3846b8d` pushed, CI 46098069377
  running (Site success; `codehealth` failed, informational as at F2; four check legs and default-install running).
- **REL060 started early** (decision 03:45): worktree `.claude/worktrees/rel060`, branch `wp/REL060` (local, not
  pushed). LINE06-L1 PASS (0.6.json final, note `docs/briefs/REL060-line-0.6.md`, no claim-set change). R-TO
  (`release_rc.py junit-cases`, item F2-THREE-OS = L3) and R-WV (`wheel_data_check.py --f2`, item WHEEL-F2) PASS;
  R-REV (RP 13(3) reviewer, `docs/reviews/REL060-machinery.md`) -> R-FIX PASS (F-1, F-2, F-3 pinned =56/=1, N-1).
  `tests/test_rel*.py` 338 passed; real `--f2` re-run after F-1: PASS (log `~/.cache/line06/rel060/wv-*.log`).
  Build decisions `docs/REL060_DECISIONS.md`. Q-L1, Q-B2, Q-D1, Q-D2 defaults stand.

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

## Next action (2026-11-28 ~05:45; NO agent of this session is running)

Background: CI waiter `~/.cache/line06/ci/wait_runs.sh wp/F8 d3846b8dbbc58d01c5c5706c999d3834925f0fa7` (PID 896329)
-> `~/.cache/line06/ci/f8-d3846b8d.log` (rerun it if gone). Its notice (and a second watcher's that cats that log) may
arrive in this context.

1. **F8 CI ends.** Four check legs + default-install + identity `success` (codehealth informational; record what it
   flagged: `gh run view 46098069377 --log-failed | grep`): DECISION-REQUEST `ofs-f8-merge` to hub (as
   ofs-x06-merge; ADR 0019 Amendment 12 already Accepted, so no amendment option). On VERIFIED: merge wp/F8 into main
   (merge commit), F0 (`scripts/corpus_identity.py --check`), push main, delete worktree f8. On red: `--log-failed`,
   fix on wp/F8 (opus-engineer brief), gate, push.
2. **After the F8 merge:** merge main into wp/REL060; loader check (0067 then passes); push wp/REL060 for CI (release
   scripts and tests changed); on green, merge card `ofs-rel060-merge` (wp/REL060 into main). Then K3 per the rel050
   skill order (`.claude/skills/rel050/SKILL.md`; `.git/codehealth/briefs/REL050-K3.md` is 0.5's K3 brief), J, C, RC
   steps 1-17 (items WHEEL-F2 and F2-THREE-OS run at step 17), verdict, step 18, message 1 (no claim-set change;
   predicted lapses V17 carry, V14 (b): note §9), dry run, dispatch, PyPI (each the user's card).
3. Code health to file with `code_health` (from 2026-11-27): S2, `render_error` without code prefix, F2
   `application/validation.py` large_file; plus R-REV notes N-2..N-5 (`docs/reviews/REL060-machinery.md`).

**Rules learnt** (LINE06_DECISIONS 2026-11-27): the full local gate (`scripts/gate.sh`, ~1.5 h, detached worktree)
passes before any package push; the codehealth diff is informational. Branch pushes for CI are the orchestrator's.

## Decisions settled (Decision Desk, 2026-11-26, each choice A, VERIFIED, `executed` written)

- `ofs-line06-rest`: new 0.7 "multiphase core and generic units"; dynamics 0.8, design toolkit 0.9,
  batch/relief/synthesis/electrolytes 0.10; 1.0 unchanged. Applied in `roadmap.md`, ADR 0057 Amendment 3, R-1070.
- `ofs-line06-adr-clause`: the 0.6 line acceptance requires ADR 0062, 0067 and 0078 Accepted; 0063 to 0065 to 0.7,
  0066 to 0.8. Applied likewise.
- `ofs-line06-x06-scope`: X06's architect pass designs ADR 0056 row 8 in full, in its order. In the D1 brief.

- `ofs-x06-accept-adr0078` (A, VERIFIED, executed): ADR 0078 accepted as written at dcbab9b7 with Q1-Q3, Q5, Q6 defaults.
- `ofs-x06-mcp-clients` (A, VERIFIED, executed): static bearer only in 0.6; OAuth later.
- `ofs-x06-descriptions-human` (A, VERIFIED, executed 2026-11-27): the 11 texts human-reviewed (wp/X06 1b9561a3).

## Open decisions (later, not yet requested)

ADR 0062 acceptance (before F2m), ADR 0067 (before F8m); each merge; the release cards.

## Estimate (extrapolated, not measured)

About 16 work orders plus 1 architect, 3 reviewer, 1 specifier and 1 verdict pass: 1.5 to 2.5 weeks of wall clock,
about 8 to 12M tokens. Baseline: F1 (7 WOs, 14 h) and F3 (6 WOs, 2.5 days) from ADR to merge.

## Anchors

ADR 0062 work orders `docs/adr/0062-F2-material-model.md` (section "Work orders"), exits ("Exit tests"); ADR 0067
the same sections; ADR 0056 row 8 (X06's scope); `release/lines/0.6.json`; `docs/briefs/LINE06-line-0.6.md`;
`scripts/release_gate.py` `load_line`, `line_problems`, `line_release`.
