# Build brief: X02 — catalogue entries for X02's three new message codes (CI red on `test_msg_coverage`)

Status: brief, 2026-11-08. **Do not spawn sub-agents yourself.** Branch `wp/X02`, worktree
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x02`, head `51ef7460`. Import path: run with
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` and `PYTHONPATH=src` (confirm `openflowsheet.__file__` is the
worktree's).

## The failure

CI `42512488771` on `51ef7460`: one failure on all three legs (15207 passed),
`tests/test_msg_coverage.py::test_g2_every_scanned_code_has_an_entry_or_a_reason` — MSG (merged into X02 at
`f36b4a56`) requires every scanned code to have a catalogue entry or an allow-reason; X02's three codes have neither:
`coupling_warm_start` (`application/coupled_run.py:1102`), `warm_start_source_missing` (`application/admission.py:206`),
`warm_start_unit_unknown` (`application/admission.py:219`).

## Do

1. Read how MSG catalogues codes (`src/openflowsheet/messages/catalogue/`, `scripts/msg_catalogue.py`, MSG's design
   note / `docs/MSG_DECISIONS.md` on main for the entry format, families and the `review` flag), and how a package
   merged after MSG added entries for its own codes if one did. For each of the three codes decide by MSG's rules
   whether it is a catalogue entry (a user-facing refusal/diagnostic) or an allow-listed scan hit (with a reason). Write
   entries in the catalogue's voice from what the code actually does at those lines and ADR 0070's text (no new claims).
   New prose entries carry `review: true` (awaiting design-lane review) if that is how MSG marks unreviewed text —
   never mark text reviewed yourself.
2. Regenerate whatever MSG's generators derive from the catalogue (catalogue digest, doc pages `doc_pages.py`,
   `message_entry` fixtures) the way MSG's own commits did; log old → new digests in `docs/X02_DECISIONS.md` (D-39).
3. Tests: `tests/test_msg_*`, `tests/test_x02*`, `tests/test_m07a_surface_chain.py`, doc-page and description tests;
   `scripts/msg_catalogue.py check`; `scripts/corpus_identity.py --check`; `ruff check`, `ruff format --check`, `mypy`.
   If a catalogue change moves X02's c_5 digest D_5 `f51b69bf…` or MSG's D_4, stop and report.
4. One commit `X02: catalogue entries for coupling_warm_start, warm_start_source_missing, warm_start_unit_unknown
   (MSG G2)`, named paths, trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
   https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/X02`. No manifest, no merge.

TRS2 shared: `uptime` first; targeted tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`,
`~/.cache/seider3/`, `~/.cache/seider4/`; nothing in other worktrees.

## Report (≤ 12 lines)

Entry vs allow per code and why; digests old → new; test counts; F0 line; commit.
