# WS1 — the workstation-only items after the cloud session (build lane, opus-engineer)

No model calls, no spend. Work in a new worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/ws1` on branch
`wp/WS1` from `main` (`deee3ad` or later). No other agent runs. Read `CLAUDE.md` (gate by risk, 2026-10-22). Frank wants
minimal token use: run recipes, read logs only by `grep`/`tail`, no exploration beyond each item.

## Items, in order (each its own commit)
1. **G10 re-take at `0.3.0.dev0`** — the recipe and expected numbers are in `docs/C7_DECISIONS.md` l.31–36: in
   `.venv-nlp` (use the m05/main recipe: `OMP_NUM_THREADS=1 PYOMO_CONFIG_DIR=.venv-nlp/share/pyomo PYTHONNOUSERSITE=1
   PYTHONPATH=$PWD/src:.reference-downloads/m03-ipopt/nlp-test-tools`; find `.venv-nlp`/`.reference-downloads` in the
   main checkout or `.claude/worktrees/m05` and symlink or reference them), from a clean tree, re-run TR-E2, TR-E2-FAR,
   TR-E2-FD, LOOP-R, LOOP-S; prove with `scripts/m05_retake_diff.py --digest-only --old-version 0.2.0` (expected:
   `version=` leaves 4/7/4/3/4, changed digests 41/79/70/91/37, other=0, environment equal); AM-23 5 passed;
   `-m nlp tests/test_m05_g10_replay.py` 5 passed. The re-take must record a clean tree with its `run_commit` in history
   (precedent R-477: version-state commit first, records commit after). Different counts → STOP, log both.
2. **REAL replay at `0.3.0.dev0`** (`docs/C7_DECISIONS.md` l.37–38): `scripts/m05_wo9_real.py --replay` in the reactor
   environment (about 25 min); expect `REPLAY PASS REAL differences=0`. Record the result line in `docs/C7_DECISIONS.md`.
3. **ADR 0044 acceptance, condition (4) and Frank's added condition** (`docs/adr/0044-*.md` l.3–8;
   `docs/FRANK_QUESTIONS.md` Answers: "every other unit's results unchanged, bit-identical at the old configuration"):
   (a) scan the registered step records for `LINEAR_SOLVE_FAILED` with ≥ 2 attempts (the workstation scan the ADR
   names; S02 spec §18.3 says where) and log counts; (b) show that no registered record of any unit other than the
   S02 column changes under the new recovery path (re-run the committed regression/replay records that exist for the
   other units and compare bytes or the registered digests). Write both results into the ADR's status paragraph as
   evidence. Do NOT flip ADR 0044 to Accepted yourself unless every one of its four conditions plus Frank's is met and
   recorded; if one is not, say which.
4. **C2 F-1 facts** (`docs/derivations/C2-OpenIDAES-450-split-registration.md` l.206–216): with the archive as a REAL
   ignored directory (`cp -al` `OpenIDAES-450-demo.tar.gz` and `extracted` from
   `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts/` into the worktree's
   `evidence/M06/W27/artifacts/`), run the workstation `facts` stage to write the NEW file
   `benchmarks/m06/openidaes450/case_facts-v2.json` (schema `openidaes450-case-facts-v2`, `topology_units` per case,
   sorted by id); never rewrite `case_facts.json`. Then do what the registration says follows (`split.json#/f1/status`,
   generator `--check`). If the registration leaves the next step to the design lane, stop after writing the file and
   say so.

## Rules
Never read, stat, copy or log `~/.config/procsim/v17-token`. Records/docs commits: run the tests they touch. Before
proposing a merge: full `scripts/gate.sh` (background; summary line only; W27 symlink
`evidence/M06/W27/artifacts` → the archive dir above if the real copy is gone; remove after; never commit it), and read
the result BEFORE pushing a merge. Merge `wp/WS1` into `main` only if the full gate passes and CI is green on both
architectures; otherwise leave the branch pushed. Never run the gate during an nlp/REAL run. Named paths only. Trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` /
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Context cap ~120k: commit, ≤20-line handoff
in `docs/C7_DECISIONS.md`, stop. Update `docs/V02_STATE.md` "Next action" in place at the end (2–3 lines).
Report ≤ 150 words: per item done/blocked with the key numbers; commits; gate; CI; merge sha or why not.
