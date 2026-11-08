# Build brief: X05a — Frank's Q-F1 = no (leave the four transitive members floating) and ADR 0069's acceptance

Status: brief, 2026-11-08. Frank accepted ADR 0069 and answered **Q-F1: no, do not pin** (decision board; record
`docs/FRANK_QUESTIONS.md` "Answers — Frank, 2026-11-08"). ADR 0069 (`docs/adr/0069-X05-replay-from-the-wheel.md`)
names this alternative itself (§11 Q-F1): "leave them floating; a plain install records `""` with the floating members
named, and A25 is restated as that inverse. Reversible by one isolated commit." The pin commit is `a58ef5a5`
(`pyproject.toml` + `tests/test_m01_provider.py`). **Do not spawn sub-agents yourself.**

## Where

New branch `wp/X05a` from main, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x05a`
(`git worktree add -b wp/X05a .claude/worktrees/x05a main`). Manifest later under `evidence/X05a/` (not by you).

## Do (one commit each, messages `X05a: …`)

1. **The reversal (isolated):** `git revert a58ef5a5` (or its exact inverse if it no longer applies cleanly) — the
   four `==` pins leave `[project].dependencies`; `tests/test_m01_provider.py`'s list returns to the five direct pins.
2. **A25 restated as its inverse** in `tests/test_x05_lock.py` (and wherever A25's static half lives): the non-extra
   `Requires-Dist` pins exactly the five direct members and leaves the four transitive members unpinned; an
   unconstrained install whose transitive members differ from the lock records `lock_sha256 = ""` and names them in
   the replay reason (the D5 path). Keep every other X05 assertion; no relaxed check. If an X05 test or the wheel
   replay (X05.A22) assumed the pins in a way the ADR does not cover, stop and report.
3. **ADR 0069 text:** status → `**Accepted, 2026-11-08** (Frank, on the decision board) with Q-F1 = no; Q-F2, Q-F3 =
   default (no).` Amend D3.2 (line ~108) and the A25 row (~341) to the floating form, quoting the replaced text in a
   dated "Amendment 1 (Frank's Q-F1, 2026-11-08)" section rather than silently rewriting it. Append ADR 0007
   Amendment 2 (§13's text verbatim) to `docs/adr/0007-*.md`.
4. **Register:** number §12's drafted entries **R-985, R-986, R-987** (block R-985…989), restating the third one for
   Q-F1 = no (decision: the transitive members float; rejected: exact pins in `Requires-Dist`; reason: Frank's Q-F1,
   users keep upgrade freedom; consequence: only an install constrained by the lock verifies). Add to **R-140**: "Lifted
   by X05 (ADR 0069), 2026-11-08; L41 narrowed (D7.3)." Format as the neighbouring entries (see R-970).
5. User-facing text that promises "a plain `pip install openflowsheet` replays exactly" (`grep -rn "plain .pip install"
   docs src README* CHANGELOG*`): correct it to "an install constrained by the shipped lock" and say how
   (`pip install -c <lock> openflowsheet` or the documented equivalent). CHANGELOG line under the 0.4 section.
6. Targeted tests (one run at a time, `OMP_NUM_THREADS=1`): `tests/test_x05_*.py tests/test_m01_provider.py`, the
   packaging/wheel tests that read `Requires-Dist` (grep), `scripts/corpus_identity.py --check` PASS; `ruff check`,
   `ruff format --check`, `mypy`.
7. Push `wp/X05a`. Do not merge; no manifest.

Named paths only; trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. TRS2 shared: `uptime` first; targeted tests only. Never read
or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 15 lines)

Commits; the restated A25; tests; F0 line; user-facing text changed; anything stopped on.
