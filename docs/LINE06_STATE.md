# LINE06 state: the 0.6 line (F2, F8, X06, then the 0.6.0 release)

Rewritten in place. History: `docs/LINE06_DECISIONS.md` (append-only, grep it). Rules: `docs/LINE06_RULES.md`.
Procedure: `.claude/skills/line06/SKILL.md`. Host SMM-TR09 (`ref-x86-64`); orchestrator session OpenFlowsheet-TR09.

## Objective

0.6.0 released with F2 (ADR 0062), F8 WO1 to WO3 and WO5 (ADR 0067) and X06 (ADR 0078), per R-1070 and ADR 0057
Amendment 3. Line acceptance: a v2 revision with store-pinned records solves on the legacy route on all three OSes;
the ADR acceptances of card `ofs-line06-adr-clause`; X06's exits.

## Position (2026-11-27, 16:05)

- All three packages built, reviewed and fixed; nothing merged into `main` yet. `main` local, last pushed `4c7d3d6a`.
- **F2** (ADR 0062 **Accepted**): CI at origin `4b820b97` FAILED (run 46003226499): Windows 6 tests (":" in an E-F2-3
  scratch path) and `identity` (no jsonschema in the job). Fix F2-CI1 on local wp/F2 `80cdcfb3` (after `2757eb37`);
  full gate on it running (detached worktree `.claude/worktrees/f2-gate`, PID in `~/.cache/line06/f2-ci1/gate.pid`,
  summary `~/.cache/line06/f2-ci1/gate-80cdcfb3.summary`).
- **F8** (ADR 0067 + ADR 0019 Amendment 12 **Accepted**): local wp/F8 = `4daff37f` (contains wp/F2 4b820b97, review
  fix round F8-FR, manifest `evidence/F8/18676313.../manifest.json` tested). Card `ofs-f8-accept-adr0067` VERIFIED,
  `executed`; full gate PASS 21895 passed; origin wp/F8 = `14409696`, CI running. Merges after F2.
- **X06** (ADR 0078 Accepted): origin wp/X06 = `a514896c` (X06-CI1 fixes; full gate PASS 21303 passed). CI running.
- `release/lines/0.6.json` DRAFT (LINE06-L0); release campaign not started.

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

## Next action (2026-11-27 14:20, written for a self-reset; NO agent of this session is running)

Background jobs (they survive the reset; their notices arrive in the new context):
1. **F2 gate at 80cdcfb3** (F2-CI1). On `GATE PASS`: push
   `git -c credential.helper= -c credential.helper='!gh auth git-credential' push origin 80cdcfb3:refs/heads/wp/F2`
   (orchestrator's push; ADR 0062 card already executed), CI waiter (log `~/.cache/line06/ci/f2-80cdcfb3.log`),
   `git worktree remove .claude/worktrees/f2-gate`. On all legs green: F2 merge card (A: "Merge wp/F2 at 80cdcfb3
   into main with a merge commit, run F0 on main, push main." B: "Do not merge F2 yet."). On FAIL: no push, fix.
2. **X06 CI waiter**: same script for `wp/X06 a514896c0dca95a436626f8ce67eb477855b6f18`, log
   `~/.cache/line06/ci/x06-a514896c.log`. On green: X06 merge card via hub. Mention on the card for design-lane
   notice: DECISION X06-CI1-1 (new addendum `benchmarks/x06/numerical_policy_external.yaml` classifies
   `expected_sha256`/`actual_sha256` exact; R-1032 precedent).
3. **F8 CI waiter**: same script for `wp/F8 14409696d814565ae037f16ceed948ebba1e7577`, log
   `~/.cache/line06/ci/f8-14409696.log`. Expect the same two F2 failures (it holds wp/F2 4b820b97); judge only F8-specific reds. F8 waits for F2's merge. On failure:
   fix order as for F2.

**Merge order into main:** whichever of F2 / X06 is green first merges first (merge card each). The second
re-decomposes its surface chain onto the first's digest (R-1072/R-1073: X06's c_12 `D_12` vs F2's c_11 `D_11`
`8eee5313`): that is an opus-engineer work order on the second branch, then its gate, push, CI, merge card. F8 merges
after F2 (wp/F8 must first merge the final wp/F2 and main). After each merge: F0 on main
(`scripts/corpus_identity.py --check`), push main, delete the worktree.

**Rules learnt today** (LINE06_DECISIONS 2026-11-27): the full local gate (`scripts/gate.sh`, ~1.5 h, run in a
detached worktree) passes before any package push; the codehealth diff is informational, not a push gate. Branch
pushes for CI are the orchestrator's (a card only when the user's card bundles it). Code health to file with
`code_health`: S2 (AttributeError on `reproduce` of a named bundle), `render_error` without a code prefix (X06
review ruling 9), F2 `application/validation.py` large_file (nloc 1003).

**After the three merges:** L3 (line clause on CI), then REL060 (rel050 skill order; `docs/briefs/LINE06-line-0.6.md`).

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
