# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-22, C proposed)

- main = 1fe40db3 (the 0.5 packages; card ofs-rel050-merge-main executed). **Freeze on main** (D2.4 paths) since K3;
  hub told and records it.
- wp/REL050: **K3 = 8aaed3f25d94823d2b93524884a9f054eb0d306d** (0.5.0, v0.5-envelope-1), a6d1bea8 RELEASE_PINS
  fix (tests/), **J = 3caa928cc82083e49184b4ee099bc9dbcb8b542b**, **C = 0a800e69f200e52dae7e5f3d2d56810bc8f10e27**
  (journey record), log 04dc7cd6. P1, P3, P4, P6 hold at K3 (REL050_DECISIONS). CI at 3da2c4e2 green (7 jobs).
- **C pushed as branch `rc/0a800e6`**; its push CI run (RC step 1) is being watched (poll 300 s; if the notice is
  lost: `gh run list --branch rc/0a800e6 --workflow ci`). wp/REL050 pushed at 04dc7cd6.
- Run artifacts of J: `~/.cache/rel050-cut/` (logs, drivers, journey-attempt1).

## Next actions

1. Push CI at C green on both Linux legs (step 1 needs `check` on ubuntu-latest and ubuntu-24.04-arm, junit
   artifacts). Red: read the failing job.
2. RC work order: brief `<briefs>/REL050-RC.md` from `docs/briefs/REL040-rc.md` (0.4.0 part 3) and RP §6 (steps
   1-17 at C, record `docs/REL050-rc-record.md`, records outside D2.4 paths after C). Host TR09; envs as in
   `<briefs>/REL050-J.md`. Step 15 note: the journey runs with `PYTHONPATH=src` (J's DECISION). opus-engineer.
3. RP §9.2 after the RC record: lapse report (`release_gate.py --line 0.5 --rc <C> --lapses`) and message 1 to the
   user via hub (Q-F1, Q-F2, predicted lapses V17 carry, V14 (b), M02 N1; frank_items in the line file); verdict
   (one `verdict` pass); ledger; H1, H2, step 18 YES, H3; merge C into main (card); dry run; dispatch.

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
