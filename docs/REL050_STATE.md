# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-22)

- **main = 1fe40db3** (card ofs-rel050-merge-main A, VERIFIED, executed; F0 PASS on main; pushed): ceb38cec (S19) +
  X07a + X01 + REL050 bfdd3f2d + fix 1fe40db3. wp/REL050 = 411fe0a3 (main merged in; docs-only ahead).
- **K3 running:** opus-engineer on `<briefs>/REL050-K3.md` in worktree rel050 (REL040 manifest harvest,
  HARVEST_EXCLUDED ("evidence/REL050/",), K3 0.5.0 / v0.5-envelope-1, P1/P3/P4/P6). K3 lives on wp/REL050 (0.4
  precedent). P6 already holds (SMM-TR09 ref-x86-64).
- From K3 until the dispatch main takes no D2.4 change (freeze; hub told at K3).
- GitHub API: poll every 300 s (memory `gh-api-rate-limit`).

## Next actions

1. K3 result: check the report (P1 gaps, (b) failures = RP §12 stop), push wp/REL050, tell hub the freeze is on.
2. J (RP §7.1 bullet 3): clean worktree at K3, re-takes on TR09: five G10 records (digest-only proof), M05 REAL
   (`m05_wo9_real.py --retake-into`, nlp env, OMP_NUM_THREADS=1; it fails replay since the TRS2 -> TR09 move, so the
   re-take is required), M01 IDAES conformance; then the journey record (RP §4.5) -> C. Brief pattern
   `docs/briefs/REL040-j.md`.
3. RC steps 1-17 at C (`docs/briefs/REL040-rc.md` pattern), RP §9.2 (lapse report and message 1: Q-F1, Q-F2 and the
   predicted lapses V17 carry, V14 (b), M02 N1; verdict; ledger; H1, H2, step 18 YES, H3), merge C (card), dry run,
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
