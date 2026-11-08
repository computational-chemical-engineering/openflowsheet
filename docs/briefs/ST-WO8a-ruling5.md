# Build brief: ST WO-8a — merge main, the design-lane ruling 5 (R1′ trigger), register clean-up

Status: brief, 2026-11-08. **Do not spawn sub-agents yourself.** Branch `wp/ST`, worktree
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`, head `e1a05916` (design-lane confirmations). Log
`docs/ST_DECISIONS.md`, handoff `docs/ST_HANDOFF.md`. WO-8b (the web-shell display, Frank's O3) follows in a separate
brief — not yours. Merge rule: CI green on both architectures; no local full gate.

## Do, in order (one commit each, messages `ST WO-8a: …`; log each in `docs/ST_DECISIONS.md`)

1. **`git merge main`** (no squash). Main now has MSG (merged `ed874b17`, link c_4, register R-975/R-976), X05a, WIT
   (X10a), S15a. Conflicts the way earlier merges did (`HARVEST_SIZE` recomputed, `support_envelope.yaml` combined,
   `t08_support_matrix.py --emit` then `--check`, generated files regenerated, register entries from both sides).
   `docs/reviews/ST-review.md` is add/add: take `wp/ST`'s version (main's text + the appended design-lane section).
   **Drop ST's duplicate copies of MSG's register entries** (ST carried R-942/R-943 from wp/MSG; main has them as
   R-975/R-976 and RP's own R-942…R-949 must stay untouched): `grep -rn "R-94[23]"` before and after.
   **Surface chain:** keep ST's own link as the branch has it, re-measured over main's chain if a digest moved (log
   old → new); its final number (after X02 and OPT merge) is set at WO-7, not now.
2. **Ruling 5** exactly as `docs/reviews/ST-review.md` "Design-lane confirmations (2026-11-08)" states it (read it in
   full; ADR 0068 D3 amendment and design note §4.2/§4.4 amended in `e1a05916`): in `stream_table._inputs` and
   `_decide`, R1′ fires only on the split's own row `independent_split.<U>.<S>`; the no-number branch fires on the
   verifier's own reason `temperature_degenerate_unlifted(<S>)`; a flash drum's inlet then takes R2/R3. Tests
   **DC-1…DC-6** as the ruling specifies them (including DC-5 for M1-2's mixture-`h` branch). The ruling says no served
   document moves: prove it — the 44 served 0.3.0 documents byte-identical to before (S4's check), G7/G8/G8u unchanged.
   If anything moves, stop and report.
3. **Docs pointer:** `docs/roadmap/foundation-rulings.md` ~666–676 (Q4.R12 (b)(ii)): one dated sentence pointing to
   ADR 0068's D3 amendment (2026-11-08). Nothing else in that file.
4. Targeted tests (one run at a time, `OMP_NUM_THREADS=1`): `tests/test_st*` (or as the handoff names them), the
   surface/R4-G3/description tests, `tests/test_m07a_harvest.py tests/test_t08*.py tests/test_evidence_manifests.py`;
   `scripts/corpus_identity.py --check` PASS; `ruff check`, `ruff format --check`, `mypy` clean.
   **Import path:** worktrees have no `.venv`; the main checkout's `.venv` has an editable install of **main's** `src`.
   Run with `PYTHONPATH=src` and confirm `python -c "import openflowsheet; print(openflowsheet.__file__)"` shows the
   worktree's copy (or make a worktree venv). Say which in the report.
5. Push `wp/ST`. No manifest, no merge into main.

## Rules

No relaxed checks, no edited gates, no wall-time budget changes; never set `reviewed`; no human review recorded by
you. Named paths only (never `git add -A`); trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. TRS2 shared: `uptime` first, targeted tests
only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`;
nothing in other worktrees. Context cap ~150k: commit, update `docs/ST_HANDOFF.md` (≤ 40 lines), stop.

## Report (≤ 20 lines)

Commits and head; conflicts resolved; R-942/943 clean-up; ruling 5 change (files, functions); DC-1…6 results; served
documents byte-identical (count); test counts and how `src` was resolved; F0 line.
