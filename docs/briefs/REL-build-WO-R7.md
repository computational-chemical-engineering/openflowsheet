# Build brief: ADR 0055 WO-R7 — RP review fixes, gate re-run, manifest re-take (0.4)

Status: brief, 2026-11-06. Review `docs/reviews/RP-review.md` (`d1b4a593`, on main) is binding. Branch `wp/RP`,
worktree `.claude/worktrees/rp`, head `05e3e069`. Log `docs/RP_DECISIONS.md` (append C-23…), handoff
`docs/RP_HANDOFF.md`. First `git fetch origin && git merge origin/main` into `wp/RP` (brings the review and this brief).

## Scope, in order

1. **Amendments A-1…A-8** (review "§17 amendment block"): paste into RP `docs/derivations/release-procedure.md` §17
   verbatim, and edit the sections each amends where the block says so; one register line per amendment in
   `docs/decision-register.md` (next free R-number on the merged tree; check main's register at the merge).
2. **M-3:** paste the restated acceptance condition and the F-1…F-8 notes into `docs/adr/0055-standing-release-procedure.md`
   as the review gives them. Do not change ADR 0055's status (Frank accepts it; that is not yours).
3. **M-2 / A-1:** RP.S18 moves to the changed-form list with the sub-check that its failures all come from changed-form
   checks; REL.A20 must then PASS over 0.3.0's records, with a control that fails when a same-form check fails.
4. **M-1:** one standing-mode NO fixture per decision item on the 0.4 line for `_build_standing`, added to RP.S06's
   selection. Prove it bites: the review's mutation (blanking the RC-record, manifest, envelope, ADR and LINKS checks)
   must now fail tests; record the counts.
5. **Should-fix now:** S-1 (fingerprint reproduced at `Accepted at`, A-2), S-2 (line file unchanged between C and the
   tag), S-3 (exactly one push run and one `release_rc` dispatch at C), S-4 (C pushed as a branch head), S-5 (step 12's
   inputs registered, loud failure if unreadable, A-5), S-7 (record whether CI artifacts were downloaded), and C-12's
   check that the nlp worktree is at C and clean. Each with a test and a control. **S-6** (rehearsing steps 6, 11, 12,
   14–16 and the nlp item at a main commit) is not in this work order — it is a pre-K3 task.
6. Not in scope: the schema ADR admitting `REL[0-9]{3,}` (design lane, before K3); ADR 0055's acceptance.
7. Full gate once in the background (`PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH
   ./scripts/gate.sh`, ~2.5 h on this loaded host, logs under
   `/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/rp-gate-r7/`).
   It must be green: if only `tests/test_m06_browser_smoke.py` fails under load again, re-run the full gate (not the
   module alone) once more; no skip, no new baseline, never a budget change. Report every run.
8. Re-take the manifest `evidence/S15/<commit>/manifest.json` (C-22 stands; status `tested` only if REL.A01–A10,
   A17–A20 support it; each never-run step named; never `reviewed`), harvest tests, push `wp/RP`, wait for the push CI
   and record both legs. Do not merge. No CI dispatch.

## Rules

RP as amended is binding. Where the review leaves a choice, decide, isolate, log; where it is silent on something that
changes what passes, stop and report. Never loosen a check. Do not edit legacy release scripts or their tests, or
`evidence/S13/`. Run the tests you touch, `tests/test_rel_*.py`, `tests/test_release_workflows.py`, ruff, ruff format,
mypy, `scripts/corpus_identity.py --check` (PASS). Commit on `wp/RP` only, named paths, messages `RP WO-R7: …`. No
subagents. Never read, stat or touch `~/.config/procsim/`; do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
`~/.cache/seider4/`; nothing under other worktrees. Context cap ~150k: commit, rewrite `docs/RP_HANDOFF.md` (≤ 40 lines),
stop — before the gate rather than mid-gate. Report ≤ 25 lines.
