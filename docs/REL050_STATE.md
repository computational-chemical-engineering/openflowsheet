# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-23, 0.5.0 released; post-tag open)

- main = 1fe40db3 (the 0.5 packages; card ofs-rel050-merge-main executed). **Freeze on main** (D2.4 paths) since K3;
  hub told and records it.
- wp/REL050: **K3 = 8aaed3f25d94823d2b93524884a9f054eb0d306d** (0.5.0, v0.5-envelope-1), a6d1bea8 RELEASE_PINS
  fix (tests/), **J = 3caa928cc82083e49184b4ee099bc9dbcb8b542b**, **C = 0a800e69f200e52dae7e5f3d2d56810bc8f10e27**
  (journey record), pushed as `rc/0a800e6`. P1, P3, P4, P6 hold at K3. CI at 3da2c4e2 green (7 jobs).
- CI at C: push run **45019680845** (step 1), `release_rc` dispatch **45019811148** (orchestrator, 2026-11-22 ~12:00Z).
- **RC work order running**: `<briefs>/REL050-RC.md`, opus-engineer, RC tree `.claude/worktrees/rc-c-050`, work
  `~/.cache/rel050-cut/rc/`; it commits records under evidence/REL050, release/rc-trees, docs only; does not push.
- **Local full gate at 71c1d04f (C + docs)** running in the rel050 worktree, PID in `~/.cache/rel050-cut/gate/pid`,
  summary `~/.cache/rel050-cut/gate/summary.txt`, log beside it. Run as `PATH=$R/.venv/bin:$PATH PYTHONPATH=src
  scripts/gate.sh <log>` (without PYTHONPATH=src the main .venv imports the main checkout's src).
- Run artifacts of J: `~/.cache/rel050-cut/` (logs, drivers, journey-attempt1).

## Next actions

1. **0.5.0 RELEASED** (tag v0.5.0 = 63b00504; PyPI; GitHub release 2026-11-23T09:31Z).
2. Open (card ofs-rel050-dispatch A, not yet `executed`): RP §7.4 working form on a branch from v0.5.0: version
   0.6.0.dev0 (RP §7.1's set), envelope `v0.2-envelope-dev`/`0.2.0.dev0`, `RELEASED` gains 0.5.0 = 63b00504, RELEASING
   "After a tag", the five G10 re-takes (R-458, `--old-host SMM-TR09`), tests reading version and envelope; CI; then
   push main and lift the freeze (tell hub); write `executed` on the card. Pattern: RP_DECISIONS `## 0.4.0 after the
   tag` (b618f2fe). **Pause until Thu 2026-11-26 13:00: no new agents**; the user decides whether the session does it
   alone before then.
3. **Thursday 2026-11-26 13:00 order (proposed; the user decides):** (a) `0.5.0.post1` README fix (R-922) or fold it into
   0.5.1; (b) 0.5.1 patch release with X32 and other ready fixes (scan wp/* for tested+reviewed unmerged); (c) the
   0.6.0.dev0 working form after the last 0.5.x; (d) RP amendment: K3 precondition P7 (ready fixes merged or named).
4. 0.6 follow-ups: V17 campaign `v17-c3` (F1/F3 tools); RP amendment for verdict F-3, F-4; the 0.6 line file
   inheriting 0.5.

## Gates (criteria fixed before the run)

| gate | pass criterion | result |
| --- | --- | --- |
| P1-P6 (RP §5.3) at K3 | every package `tested`/`reviewed` at an ancestor of K3; RP.L01-L11 hold; required ADRs Accepted or routed; host prints `ref-x86-64` | |
| RC steps 1-17 at C | no RP §12 stop; every step's result recorded, none `unsupported` | met: 69 rows, 0 FAIL (fd50e7fc) |
| verdict | every claimed gate met (verdict document), or Frank's answer row | met: 15 PASS, V14 (b) and X31 (c) FAIL with standing rows (121d7b32) |
| step 18 at H2 | exit 0, last line exactly `v0.5.0 tag may be proposed: YES` | met at ee519d46 and 77d20401 |
| CI | green on both architectures at C and at the merge into main | met: at C 45019680845/45019811148; at H3 45086710551 |
| dry run | release workflow dry run: gate YES, build, `t08-a43-dist.json` all passed | met: 45134619467 |

## Open decisions (defaults stand unless Frank says otherwise)

- Q-F1 (note §8): the 0.5 line acceptance's "ADR-F1 to ADR-F8 Accepted" (0062-0067 Proposed) -> default: the clause
  moves to 0.6, as for 0.4. Frank, message 1.
- Q-F2: Windows and macOS CI legs not judged at C (step 1 reads the Linux legs) -> default: no change. Message 1.
- Q-B1 default stands (0.4-era packages not added). Q-B2 done (WF). Q-B3 done (71a7328e). Q-D1 done (REL050-R).
- S19 relative to K3: settled, S19 is in 0.5.0 (card ofs-s19-merge-main A, executed; main ceb38cec).
- X01 Q-1..Q-3: their defaults in `docs/X01_DECISIONS.md`.
