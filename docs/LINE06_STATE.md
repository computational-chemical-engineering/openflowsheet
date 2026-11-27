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

## Next action (2026-11-27, written for a self-reset; NO agent of this session is running)

Judged PASS since the morning (details: `docs/LINE06_DECISIONS.md`): F2-R1, F2-WO6b, WO6c, WO7 (+WO7-4), the F2 review
(`docs/reviews/F2-review.md`) and F2-WO8; F8-WO1 (+WO1b, R-1076 c_13), F8-WO2, F8-WO3. Heads: wp/F2 `a64f93fb`
(manifest `evidence/F2/fb75c409.../manifest.json`, `tested`), wp/F8 `25e5ed36`, wp/X06 `1b9561a3` (pushed).

**Running (2026-11-27):** the Opus review of F8-WO5 (`opus-engineer`, brief `docs/briefs/LINE06-F8-WO5-review.md`, wp/F8
from `dcf4b89f`, logs `~/.cache/line06/f8-wo5r/`). F8-WO5 judged PASS at `dcf4b89f` (errata E-D7 folded, DECISION
F8-WO5-0, `369150d3`). If the session died: check `git -C .claude/worktrees/f8 log`/status and judge on that brief.
Then F8 close-out, the F8 `reviewer` pass with the ruling batch.

**Was next (F8):** write `docs/briefs/LINE06-F8-WO5.md` (ADR 0067 D7 per-platform reference records, `run/platform_refs.py`,
invariant test; E-F8-8; Sonnet `sonnet-implementer`, then an Opus `opus-engineer` review of its diff, per the WO table).
Read D7 (`docs/adr/0067-F8-identity-replay-evidence.md` line ~152), risk 5 (reuse ADR 0025's layout if it exists; X07a
`tests/test_x07a_*`), `docs/F8_DECISIONS.md`. Then F8 close-out (ADR 0019 Amendment 12 pointer paragraph, evidence
manifest `tested`), then the F8 `reviewer` pass with the ruling batch WO1-1 and WO3-1 to WO3-10 (WO3-1: D5 step 7's
served stack has no consumer until v2-compiled runs), fix round, ADR 0067 acceptance card.
Before F8's merge: merge wp/F2's final head into wp/F8; re-decompose c_13 onto F2's D_11 `8eee5313…`; re-pin the
catalogue digest (wp/F2 `3af0a794`, wp/F8 `4ca46ea4`: a conflict to resolve); the v03 reds go away with F2's fixes.

**F2:** WO1-WO8 done; ADR 0062 D2/D11/D12 edited. Cards OPEN on the Decision Desk (filed by hub, it rings):
`ofs-f2-accept-adr0062` (A action: "Mark ADR 0062 Accepted as corrected before acceptance at wp/F2 a64f93fb (D12 per
F2-R1, D2 PropertyRequest not widened, D11 h_mass revision-wide, E-F2-9 state_degenerate_in_definition and Q6.A2
registration half deferred to F5/F6), then push wp/F2 for CI.") and `ofs-f2-check-admission-human` (A action: "Record
the user's human review as reviewed for check_admission.md at SHA-256
f111234f5e1ec6027056cf638d40f3776570fade25207919f32ddd49affb0eea (wp/F2 a64f93fb), in REVIEW.json."). On a ring:
ArtifactData `get` collection `decisions` and `list` collection `keys` (desk
https://claude.ai/artifact/AYGJBJRbCziMn7pSELMELA, same `out_dir` D in the scratchpad), then
`python3 ~/.claude/tools/decision_desk_verify.py D <id> --action "<A text>"`; on VERIFIED: set ADR 0062 Status
Accepted (date, card id); record the review in REVIEW.json (human entry: status reviewed, reviewed_by "the user,
Decision Desk ofs-f2-check-admission-human", reviewed_at the date; keep `ensure_ascii` JSON, indent 2); run
`tests/test_t08_w2_description_reviews.py`; write `executed` (update with `if_version`); push wp/F2 with
`git -c credential.helper= -c credential.helper='!gh auth git-credential' push -u origin wp/F2`; CI waiter
`~/.cache/line06/ci/wait_runs.sh wp/F2 <sha>` in the background; on green on all legs a merge card via hub.

**X06:** card `ofs-x06-descriptions-human` VERIFIED A and executed; review recorded (wp/X06 `1b9561a3`), pushed.
CI running (ci 45962988409, Site 45962988390; background waiter, log `~/.cache/line06/ci/x06-1b9561a3.log`; if the
session died, rerun `~/.cache/line06/ci/wait_runs.sh wp/X06 1b9561a3f104d90bbae2a86faef07800b0f0ef76`). On green on
all legs: X06 merge card (DECISION-REQUEST to hub; action text per option; the user, not first names). After the
merge: F0 on main, push main, delete the worktree; the second of F2/X06 to merge decomposes onto the first's digest.

At F2's merge: the register-block conflict (WO3-1) and the surface-chain order with X06 (R-1072/R-1073: the second
to merge decomposes onto the first's digest). Code health to file with `code_health`: S2 (AttributeError escapes
`reproduce` on a named bundle), `render_error` without a code prefix (X06 review ruling 9).
Process rules: every brief gives the engineer its own log dir `~/.cache/line06/<wo>/`; wait on log lines, not
`kill -0`; an agent "waiting on its own background work" after its report may hold a stale watcher: check the
worktree for its processes (`/proc/<pid>/cwd`), then TaskStop it.

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
