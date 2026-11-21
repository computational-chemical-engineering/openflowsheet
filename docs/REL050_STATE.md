# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-21 ~18:20 CET)

- main = d29f1a50. **wp/REL050** = cac945ac + log commits (pushed at cac945ac; **CI 44913179654 green** on both
  Linux legs, default-install, codehealth, identity). Holds: main merged in (c4f7c650; loader RP.L01-L11 PASS, the
  six new required ADRs Accepted); line file `release/lines/0.5.json`; WHEEL-F1-F3 `--f1-f3` (1dee789c, fixed by
  REL050-WF2 bfecbeb7/bf6adbbd/1452d786: `--commit 1452d786 --f1-f3` exit 0 PASS, N 149, N_pkg 9); Q-B3 phrase test
  (71a7328e); scoped reviewer pass REL050-R done (c1c61a68, merge after F-1..F-3, all applied). Next actions 1-3 met.
- **X07a**: manifest `tested` at bd0b7df5 in c356211b (pushed; X07a-WO20). Old 9773c361 manifest kept, HARVEST_SIZE
  (102, 1148, 147). **CI 44913734986 at c356211b running** (poller b060poyxl).
- **X01**: CI 44909945712 at 5634fa7f failed only on harvest bookkeeping (A21 unmapped a0e4c546 limitations;
  HARVEST_SIZE). Fixed by the orchestrator bbbca491 (pushed): 4 class-P rows, HARVEST_SIZE (101, 1148, 146).
  **CI 44921749701 / Site 44921749623 at bbbca491 running** (poller b7xas16w4). Then the X01 manifest moves to
  `tested` at bbbca491 (the existing tested manifest is at a0e4c546; sonnet brief, pattern X07a c356211b), push,
  fresh CI.
- S19 (not a 0.5 item): G-END PASSED, manifest tested (f814928a), CI 44923603617 running. See S19_STATE.
- GitHub API: quota shared by all sessions; poll with `gh run view --json status` every 300 s, never `gh run watch`
  at its default interval (14:56-15:25 UTC outage, memory `gh-api-rate-limit`).

## Background waits running (notices arrive in the next context)

- b060poyxl: polls X07a 44913734986 (the REL050 and S19 runs it also watched are done). Green -> step 2 below.
- b7xas16w4: polls X01 44921749701, then prints Site 44921749623. Green -> X01 manifest move.
- b0yo0or3j: polls wp/S19 44923603617 (S19's).

## Next actions

1. On each green: log in REL050_DECISIONS. X01: brief the manifest move (sonnet-implementer; X07a-WO20's brief
   `<briefs>/X07a-WO20-manifest.md` as template, no re-runs beyond its check list), push, CI.
2. **Merge plan (DECISION for this step):** every branch changes `HARVEST_SIZE` and appends to
   `benchmarks/t08/support_envelope.yaml`, so each merge into main conflicts with the next and needs main merged back
   plus a ~2 h CI. Proposal: one integration branch `int/0.5` = main + wp/X07a + wp/X01 + wp/REL050 (resolve the
   harvest conflicts by re-measuring HARVEST_SIZE and re-emitting the matrix), one CI; then ONE Decision Desk card via
   hub (DECISION-REQUEST, "the user", action text per option): A merge the three into main in that order with the
   integration CI as evidence (recommended), B separate cards and CIs. S19's own card separately: A merge before K3
   (enters 0.5), B after the tag; note the conflict cost either way.
3. After the merge(s): K3 (RP §7.1; note §7's loader command at K3, P1-P6), J (re-takes incl. m05 REAL on TR09), C,
   RC steps 1-17, RP §9.2 (lapse report and message 1: Q-F1, Q-F2 and the predicted lapses V17 carry, V14 (b),
   M02 N1; verdict; ledger; H1, H2, step 18 YES, H3), merge C, dry run, Frank's dispatch.

## Gates (criteria fixed before the run)

| gate | pass criterion | result |
| --- | --- | --- |
| P1-P6 (RP §5.3) at K3 | every package `tested`/`reviewed` at an ancestor of K3; RP.L01-L11 hold; required ADRs Accepted or routed; host prints `ref-x86-64` | |
| RC steps 1-17 at C | no RP §12 stop; every step's result recorded, none `unsupported` | |
| verdict | every claimed gate met (verdict document), or Frank's answer row | |
| step 18 at H2 | exit 0, last line exactly `v0.5.0 tag may be proposed: YES` | |
| CI | green on both architectures at C and at the merge into main | |
| dry run | release workflow dry run: gate YES, build, `t08-a43-dist.json` all passed | |

## Open decisions (defaults stand unless Frank says otherwise)

- Q-F1 (note §8): the 0.5 line acceptance's "ADR-F1 to ADR-F8 Accepted" (0062-0067 Proposed) -> default: the clause
  moves to 0.6, as for 0.4. Frank, message 1.
- Q-F2: Windows and macOS CI legs not judged at C (step 1 reads the Linux legs) -> default: no change. Message 1.
- Q-B1 default stands (0.4-era packages not added). Q-B2 done (WF). Q-B3 done (71a7328e). Q-D1 done (REL050-R).
- S19's merge into main relative to K3: only if its card is signed before K3; otherwise after the tag (D2.4 freeze).
- X01 Q-1..Q-3: their defaults in `docs/X01_DECISIONS.md`.
