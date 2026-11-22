# REL050 state: the 0.5.0 release

Rewritten in place; history in `docs/REL050_DECISIONS.md` (append-only, grep it). Rules: `docs/REL050_RULES.md`.
Procedure: `.claude/skills/rel050/SKILL.md` (on this branch; worktree `.claude/worktrees/rel050`).

## Objective

Frank, 2026-11-21: "Will you take care of the release?" (answered yes). Scope fixed by R-1065 (ADR 0057 Amendment 1,
Frank 2026-11-20, "Let's go for the smaller 0.5 release"): **0.5 = X07a, F1, F3, X01's plugin docs**; F2, F8, X06
and X01's selectability lead 0.6. Procedure: RP (`docs/derivations/release-procedure.md`), ADR 0055; dispatch steps
in `docs/RELEASING.md`. Last release v0.4.0 (2026-11-11); main is `0.5.0.dev0`.

## Position (2026-11-22, message 1 answered; verdict)

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

1. **Verdict running** (`<briefs>/REL050-verdict.md`; document `docs/reviews/REL050-verdicts.md`). Judge its report:
   every claimed gate PASS, or failing clauses listed. Then message 2 via hub (V14 (b), any new failing clause).
2. Ledger; H1 (release manifest `tested` at a clean G, `release_evidence_manifest.py --line 0.5 --commit C --k3 K3
   --ci-run 45019680845 --ci-run 45019811148`, pattern RP_DECISIONS `## 0.4.0 cut` H1), H2, step 18 YES at H2, H3;
   CHANGELOG and RELEASING block; card to merge C (via wp/REL050) into main; dry run; the user's dispatch and PyPI.
- Message 1 done: Q-F1 A (03c428f6), Q-F2 A, M02 N1 A and V17 carry (the user's chat answer) rows 6cfe0fc4; lapses
  at HEAD: only V14 (b) lapsed. v17-c3 campaign is a 0.6 follow-up.

## Gates (criteria fixed before the run)

| gate | pass criterion | result |
| --- | --- | --- |
| P1-P6 (RP §5.3) at K3 | every package `tested`/`reviewed` at an ancestor of K3; RP.L01-L11 hold; required ADRs Accepted or routed; host prints `ref-x86-64` | |
| RC steps 1-17 at C | no RP §12 stop; every step's result recorded, none `unsupported` | met: 69 rows, 0 FAIL (fd50e7fc) |
| verdict | every claimed gate met (verdict document), or Frank's answer row | |
| step 18 at H2 | exit 0, last line exactly `v0.5.0 tag may be proposed: YES` | |
| CI | green on both architectures at C and at the merge into main | at C: met (45019680845, 45019811148) |
| dry run | release workflow dry run: gate YES, build, `t08-a43-dist.json` all passed | |

## Open decisions (defaults stand unless Frank says otherwise)

- Q-F1 (note §8): the 0.5 line acceptance's "ADR-F1 to ADR-F8 Accepted" (0062-0067 Proposed) -> default: the clause
  moves to 0.6, as for 0.4. Frank, message 1.
- Q-F2: Windows and macOS CI legs not judged at C (step 1 reads the Linux legs) -> default: no change. Message 1.
- Q-B1 default stands (0.4-era packages not added). Q-B2 done (WF). Q-B3 done (71a7328e). Q-D1 done (REL050-R).
- S19 relative to K3: settled, S19 is in 0.5.0 (card ofs-s19-merge-main A, executed; main ceb38cec).
- X01 Q-1..Q-3: their defaults in `docs/X01_DECISIONS.md`.
