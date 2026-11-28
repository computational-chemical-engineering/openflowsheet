# LINE06 state: the 0.6 line (F2, F8, X06, then the 0.6.0 release)

Rewritten in place. History: `docs/LINE06_DECISIONS.md` (append-only, grep it). Rules: `docs/LINE06_RULES.md`.
Procedure: `.claude/skills/line06/SKILL.md`. Host SMM-TR09 (`ref-x86-64`); orchestrator session OpenFlowsheet-TR09.

## Objective

0.6.0 released with F2 (ADR 0062), F8 WO1 to WO3 and WO5 (ADR 0067) and X06 (ADR 0078), per R-1070 and ADR 0057
Amendment 3. Line acceptance: a v2 revision with store-pinned records solves on the legacy route on all three OSes;
the ADR acceptances of card `ofs-line06-adr-clause`; X06's exits.

## Position (2026-11-28, ~07:45)

- **F2** merged (`f1fdda2b`). **X06** merged (`9532829b`). main pushed at `9532829b`; local main ahead (docs only).
- **F8** (ADR 0067 + ADR 0019 Amendment 12 Accepted): gate PASS at b7f99d18; wp/F8 `d3846b8d` pushed; **CI 46098069377
  green** (four check legs, default-install, identity, Site). codehealth (informational): NEW import cycle
  run.replay <-> run.replay_v2, debt 19.30 -> 54.60. Card **`ofs-f8-merge` open** (A: merge now, cycle fix reaches main
  via REL060's gate+CI; B: fix on wp/F8 first, gate, CI, new card; C: no). Verbatim texts: LINE06_DECISIONS 06:12 entry.
- **F8-CYC PASS** (cycle fix): local branch `wp/F8-cycle` (worktree `.claude/worktrees/f8cyc`) `d04439c6` =
  d3846b8d + `befa9e60` (leaf `run/replay_rules.py`) + `d04439c6` (one comparison loop). 0 cycles; debt -> 48.00.
- **REL060 started early**: worktree `.claude/worktrees/rel060`, branch `wp/REL060` (local). LINE06-L1, R-TO, R-WV,
  R-REV, R-FIX all PASS; `tests/test_rel*.py` 338 passed. Build decisions `docs/REL060_DECISIONS.md`.

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

## Next action (2026-11-28 ~07:45; NO agent of this session is running)

Running: full gate on d04439c6 in detached worktree `.claude/worktrees/f8cyc-gate`, PID 1185667, summary via
`~/.cache/line06/f8cyc/gate-d04439c6.log` (one line), full log `~/.cache/line06/f8cyc/gate-d04439c6.full.log`.
When it ends: log the result in LINE06_DECISIONS; on FAIL `grep -nE 'FAILED|ERROR'` the full log, brief a fix.

1. **Card `ofs-f8-merge`** (hub rings on sign-off). Verify with the exact text of the signed option
   (`python3 ~/.claude/tools/decision_desk_verify.py D ofs-f8-merge --action "<text>"`; ArtifactData get `decisions`,
   list `keys`, same out_dir D).
   - **A VERIFIED:** merge wp/F8 at d3846b8d into main (merge commit), F0, push main (only if main's commits since the
     merge base touch no src/tests/schemas), `executed`, remove worktree f8. Then on wp/REL060: merge main, merge
     wp/F8-cycle; loader check; full gate in a detached worktree; push wp/REL060; CI; card `ofs-rel060-merge`.
   - **B VERIFIED:** `git -C .claude/worktrees/f8 merge --ff-only wp/F8-cycle` (wp/F8 -> d04439c6); with the gate on
     d04439c6 PASS push wp/F8, CI waiter, then a new merge card. Then REL060 as in A.
2. Then K3 per the rel050 skill order (`.claude/skills/rel050/SKILL.md`; `.git/codehealth/briefs/REL050-K3.md`), J,
   C, RC steps 1-17 (items WHEEL-F2, F2-THREE-OS at step 17), verdict, step 18, message 1 (no claim-set change;
   predicted lapses V17 carry, V14 (b): note §9), dry run, dispatch, PyPI (each the user's card).
3. OpenFlowsheet code-health backlog (session code_health declined them as not tool defects): F8 debt (platform_refs
   23, bundle_v2 9); F2 `application/validation.py` large_file (nloc 1003); S2 `reproduce` AttributeError on a named
   bundle; `render_error` without code prefix; REL060 review notes N-2..N-5 (`docs/reviews/REL060-machinery.md`).

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
