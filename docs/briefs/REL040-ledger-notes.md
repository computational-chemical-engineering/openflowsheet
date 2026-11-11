# Engineer brief: 0.4.0 — the ledger from the verdicts, and the `## v0.4.0` release notes (RP §9.2 step 3, RP.S17)

Status: brief, 2026-11-10. Build lane. **Do not spawn sub-agents yourself.** Work on `wp/REL040` in
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/rel040`. No D2.4 path (`src/ schemas/ benchmarks/
requirements*.lock pyproject.toml MANIFEST.in README.md LICENSE NOTICE`), no tag or release, no merge into `main`. Do
not push; the orchestrator pushes. A `specifier` works in the same worktree at the same time, on
`docs/derivations/release-procedure.md` and `docs/decision-register.md` only. Do not touch those two files. Stage only
named paths.

## Facts

- C = `84c665477b512548f38a6335f51648732b1fe5bb`, line `0.4`, package `REL040`.
- The verdict document is `docs/reviews/REL040-verdicts.md` (3e6f0d80). Verdicts:
  - 13 PASS;
  - V13 BLOCKED on (e) and V17 BLOCKED on (a), both waiting on Frank's `V17 carry` row;
  - V14 FAIL on (b), waiting on Frank's new row;
  - X31 FAIL on (c), with a standing row.
- RP.S17 (`docs/derivations/release-procedure.md` l.947–949): "The ledger's verdicts are written from the verdict
  document." The 0.3.0 pattern is commit `2b7fc98e`: `docs/requirements.yaml` plus `tests/test_v03_ledger.py`. Read that
  diff (`git show 2b7fc98e`), then see what `release_gate.py` reads from the ledger (`grep -n requirements.yaml
  scripts/release_gate.py scripts/v0_2_gate.py`).
- `release_gate.py --line 0.4 --rc <C>` currently ends `NO (12 reasons)`. One of them is "the ledger not yet written
  from the verdict".

## Do

1. **The ledger.**
   - Write the 0.4.0 verdicts into `docs/requirements.yaml` exactly as the gate reads them, as 0.3.0 did.
   - Add `tests/test_rel040_ledger.py` on 0.3.0's pattern. If the line's gate set already has a generic ledger check,
     extend that instead and say so.
   - BLOCKED rows are written as BLOCKED. They change only when Frank answers and the verdict agent re-judges.
   - Run the test, then `release_gate.py --line 0.4 --rc 84c665477b512548f38a6335f51648732b1fe5bb` and report how its
     reasons change. Expect the ledger reason to go.
   - Commit: `REL040: the ledger from the verdicts at C (RP §9.2 step 3, RP.S17)`.
2. **The notes**: `CHANGELOG.md` `## v0.4.0`, at C, in the form of 0.3.0's `## v0.3.0` section (l.65 onward).
   - Gather what changed since 0.3.0: the merged packages in `docs/progress.md` and `git log --first-parent
     a3e508e3..84c66547 --oneline`. Summarize them in plain words.
   - Include the claimed gates and their verdicts, with BLOCKED/FAIL stated, and the travelling limitations by id.
   - **F-2 (required, W21's PASS rests on it):** carry envelope row L46 or alpha §6.1 (f4)'s four reactor statements
     verbatim, as 0.3.0's notes did. Find them with `grep -n "L46" -A12 benchmarks/t08/support_envelope.yaml` and in
     0.3.0's section.
   - **F-5:** name L-X04-1..3 by text under V11, because the verdict grammar cannot carry those ids.
   - **F-4:** one sentence saying 0.4.0 adds an explicit warm-start source (ADR 0070, `solve_body.warm_start`), which
     L-WS-2's text predates.
   - Leave the standing acceptances' list as a placeholder line, `<!-- acceptances: filled after Frank's answers -->`.
     Do not invent Frank's words.
   - Do not touch `## Unreleased` except to move items that belong in 0.4.0.
   - Commit: `REL040: CHANGELOG ## v0.4.0 (notes; verdict F-2, F-4, F-5)`.
3. Check `git diff --name-only 84c66547 HEAD` holds no D2.4 path, and that `ruff check` and `ruff format --check` pass
   on the files you touched.

Trailers: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Use `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with
`PYTHONPATH=src` and `OMP_NUM_THREADS=1`. Cap ~150k context. Never read or touch `~/.config/procsim/`,
`/home/frankp/s10-papers/`, `~/.cache/seider3/` or `~/.cache/seider4/`.

## Report (at most 15 lines)

The commit shas, the test count, `release_gate.py`'s reasons before and after, and any stop.
