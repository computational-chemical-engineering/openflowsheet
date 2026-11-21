# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-21 ~21:30 CET)

- **main = ceb38cec**: S19 merged (card ofs-s19-merge-main, choice A, VERIFIED, executed; F0 PASS on main). S19 is
  in 0.5.0. Before it main was d29f1a50.
- Package heads, all `tested`, CI green: wp/X07a c356211b (manifest at bd0b7df5; CI 44913734986 all 7 legs);
  wp/X01 bfd5c180 (manifest at bbbca491, X01-WO3; CI 44921749701 + Site 44921749623 at bbbca491); wp/REL050
  bfdd3f2d + log commits (CI 44913179654 at cac945ac).
- **Integration branch `int/0.5-r2`** (worktree `.claude/worktrees/int05`) = 1fe40db3 = 67cc5027 (ceb38cec + X07a
  + X01 + REL050 bfdd3f2d; bookkeeping conflicts only) + one fix commit: S19 tooling under X07a's checks (CI
  44945609131 red at 67cc5027: git-show separator lint, two Windows `fcntl` limits; REL050_DECISIONS 2026-11-22).
  HARVEST_SIZE (105, 1169, 147). Pushed; **CI re-running at 1fe40db3** (poll 300 s). The old `int/0.5` (d29f1a50
  base) is obsolete: delete the branch after the merge.
- GitHub API: poll every 300 s, never `gh run watch` at its default interval (memory `gh-api-rate-limit`).

## Next actions

1. int/0.5-r2 CI green -> DECISION-REQUEST to hub, card ofs-rel050-merge-main: A (recommended) "merge wp/X07a,
   wp/X01 and wp/REL050 into main as the merges recorded on int/0.5-r2 (fast-forward main to int/0.5-r2 1fe40db3:
   its three merge commits are the conflict-resolved merges, then one cross-package fix commit), run F0 on main, push main only if F0 passes"; B
   separate cards and CIs per branch. Refer to "the user"; action text per option. Red -> read the failing job.
2. After the VERIFIED card: execute, `executed` on the card, log. Then K3 (RP §7.1; P1-P6 incl. the loader at K3),
   J (re-takes incl. m05 REAL on TR09), C, RC steps 1-17, RP §9.2 (lapse report and message 1: Q-F1, Q-F2 and the
   predicted lapses V17 carry, V14 (b), M02 N1; verdict; ledger; H1, H2, step 18 YES, H3), merge C, dry run,
   Frank's dispatch.

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
- S19 relative to K3: settled, S19 is in 0.5.0 (card ofs-s19-merge-main A, executed; main ceb38cec).
- X01 Q-1..Q-3: their defaults in `docs/X01_DECISIONS.md`.
