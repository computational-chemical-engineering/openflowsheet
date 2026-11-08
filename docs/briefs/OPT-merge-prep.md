# Build brief: OPT — merge preparation after Frank's acceptance of ADR 0071 (0.4)

Status: brief, 2026-11-08. Start **after X02 is merged into main** (merge order MSG → X02 → **OPT** → RRC → ST). Frank
accepted ADR 0071 and ADR 0019 Amendment 16 and confirmed every OPT default (Q1 request only, Q2 standard route only,
Q3 later package, Q4 replay re-checks, Q5 32 starts/500 it/120 s, Q6 no auto-commit, Q7 verify with the
phase-boundary flag, Q8 no ARM audit, Q9 not in 0.4; record `docs/FRANK_QUESTIONS.md` "Answers — Frank, 2026-11-08").
His human reviews of `validate.md`/`submit_job.md` are committed on the branch (`9869773e`, by Frank). **Do not spawn
sub-agents yourself.**

Branch `wp/OPT`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/opt`, head `9869773e`; manifest
`evidence/OPT/a46ea80f…/` (to be re-taken by the orchestrator after CI, not by you); log `docs/OPT_DECISIONS.md`;
handoff `docs/OPT_HANDOFF.md`; review `docs/reviews/OPT-review.md`. Merge rule: CI green on both architectures, no
local full gate. Import path: worktrees have no `.venv`; run with `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`
and `PYTHONPATH=src`, and confirm `openflowsheet.__file__` is the worktree's copy.

## Do, in order (one commit each, messages `OPT: …`; log each in `docs/OPT_DECISIONS.md` as D-86, D-87, …)

1. `git merge main` (no squash). Main now has WIT (ADR 0073, K04 §4.8.x derivative witness), MSG (c_4), X02 (c_5,
   R-950…R-955), X05a, X10b, S15a. Conflicts as earlier merges (`HARVEST_SIZE` recomputed, `support_envelope.yaml`
   combined, `t08_support_matrix.py --emit` then `--check`, generated files regenerated, register entries from both
   sides; `run_revision`/bindings keep every side's parameters).
2. **Surface chain:** OPT's link becomes **c_6**, appended after X02's c_5: strip OPT's members over main's chain,
   measure D_6, update `m07a_rc.LINKS`, the chain test and every text naming OPT's link (R-960, ADR 0071, OPT docs).
   Stripping OPT must give main's D_5 exactly; if not (the packages interact), stop and report — never re-record D_4/D_5.
   R4-G3 response-schema snapshots: re-take over main's as X02 did (X02 D-35/D-36 show the pattern).
3. **Global-state cache count:** OPT moved it against an older main; recompute against main as merged
   (`tests/test_t07_global_state.py::test_g20_every_hit_is_allowlisted_and_every_entry_is_hit`; main has 38 after X02).
4. **M-4 after WIT (D-42 / D-82 (a)):** WIT's fixed witness was expected to make OPT's D-42 GP-C3 held single-phase
   splits on γ–φ verify (`docs/roadmap/decisions.md` 2026-11-07 WIT entry: "intended moves only for today's failures
   (… OPT D-42 GP-C3 held splits verify)"). On the merged tree re-run the D-42 case(s) and OPT's tests that pin
   `START_NOT_CERTIFIED` for it. If they now verify: update D-42's tests to the new outcome only where the WIT ruling
   predicts it, and correct `docs-site/guide/optimisation.md` § Declared limitations (a) and `docs/OPT_HANDOFF.md`'s
   limitation list to what is now true (log old → new). If they do not verify, keep (a) and record the measured reason.
   Either way, the result goes in the handoff for the manifest re-take. Anything else that moved: stop and report.
5. **ADR 0071 → Accepted:** status `**Accepted, 2026-11-08** (Frank, on the decision board) with ADR 0019 Amendment
   16; Q1–Q9 defaults.` keeping "Proposed <date>" after it; ADR 0019 Am. 16 likewise (and the pointer paragraph /
   `docs/interfaces-frozen.md` entry if ADR 0071 asks for them on acceptance, as X02 did for ADR 0070). Register:
   R-960 loses "provisional"; ADR 0071's drafted entries take **R-961…** in order (block R-960…969; more than nine →
   stop), format as R-951/R-985.
6. Targeted tests (one run at a time, `OMP_NUM_THREADS=1`): `tests/test_opt*`, the surface chain / R4-G3 / surface
   digest / description tests, the global-state cache test, `tests/test_m07a_harvest.py tests/test_t08*.py
   tests/test_evidence_manifests.py`, the WIT tests (`tests/test_wit_*.py`); `scripts/corpus_identity.py --check`
   PASS; `ruff check`, `ruff format --check`, `mypy` clean (whole repo).
7. Push `wp/OPT`. Do not merge into main and do not write the manifest.

## Rules

No relaxed checks, no edited gates, no wall-time budget changes; never set `reviewed`; record no human review. Named
paths only (never `git add -A`); trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. TRS2 shared: `uptime` first, targeted tests
only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`;
nothing in other worktrees. Context cap ~150k: commit, update `docs/OPT_HANDOFF.md` (≤ 40 lines), stop.

## Report (≤ 20 lines)

Commits and head; conflicts; D_6; cache count old → new; M-4 outcome (verify or not, with numbers); register numbers;
test counts and `src` resolution; F0 line.
