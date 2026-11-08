# Build brief: X10b — WIT M-6 part b (Frank's Q-WIT-2 = yes): the flash model's near-dew sentence

Status: brief, 2026-11-08. Frank answered Q-WIT-2 **yes** (decision board; `docs/FRANK_QUESTIONS.md` "Answers —
Frank, 2026-11-08"). WIT is merged (manifest `evidence/X10a/…`); this is its follow-up. Read first:
`docs/reviews/WIT-review.md` (E-1 ruling and M-6), `docs/WIT_DECISIONS.md` and `docs/WIT_HANDOFF.md` (M-6 part a/b).
**Do not spawn sub-agents yourself.**

## Where

New branch `wp/X10b` from main, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x10b`
(`git worktree add -b wp/X10b .claude/worktrees/x10b main`).

## Do

1. One commit, as the review asks for M-6 (test case + manifest sentence together): correct the "near-dew window"
   sentence in `c1.tp_flash`'s manifest text (`src/openflowsheet/models/c1/flash.py` ~343–349) and the two G7(c)
   docstrings to the edge the fixed witness gives (measured: δ 1e-4…2.4e-4 UNVERIFIED ill-conditioned; 2.6e-4…5.7e-4
   VERIFIED with only `derivative_witness_partial`; the old witness edge was δ = 5.48e-4 — confirm the exact edge from
   the review/handoff, do not re-derive it loosely). Whatever part a already changed in the test parametrisation, leave
   it; only the text moves here unless the review says otherwise.
2. The model's artifact hash and F0's M9 entry move (the review established `model_version` and every result do not).
   Re-record exactly what moves the way the corpus tooling records an intended move (`scripts/corpus_identity.py`
   — read its help/docs for the re-record path; if the only route is hand-editing a frozen file, stop and report).
   State old → new for every hash that moved, and prove nothing else moved (`--check` M1–M8 unchanged, M9 one entry).
3. Log it in `docs/WIT_DECISIONS.md` (M-6 part b, Frank 2026-11-08). Targeted tests: `tests/test_m02_wo8_g7.py`, the
   model-manifest/artifact-hash tests (grep for the flash's hash), `tests/test_wit_*.py`, F0 `--check` PASS after the
   re-record; `ruff check`, `ruff format --check`, `mypy`.
4. Push `wp/X10b`. Do not merge; no manifest.

Named paths only; trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. TRS2 shared: `uptime` first; targeted tests only. Never read
or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Commit; the sentence before → after; hashes old → new; F0 line; tests; anything stopped on.
