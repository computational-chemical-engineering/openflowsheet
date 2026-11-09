# Engineer brief: ST WO-7 — re-base on main, chain link c_7, ADR 0068 Accepted, register ids, push for CI

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.** Start only when the orchestrator says
`wp/MSGp` has merged into main (main then holds MSG, X02, OPT, RRC and the MSG catalogue ruling).

## Where

Branch `wp/ST`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`, CI-green head `eb1e0936` (39 commits
ahead of main at the time of writing). Read first: `docs/ST_HANDOFF.md` (its last paragraph lists what WO-7 must do at
the merge), `docs/ST_DECISIONS.md` (append your entries there), `docs/roadmap/decisions.md` entries mentioning ST.
Worktrees have no `.venv`: run `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with `PYTHONPATH=src` (CLI pin
writer `PYTHONPATH=src:.`), confirm `openflowsheet.__file__` is the worktree's copy. Serial tests, `OMP_NUM_THREADS=1`.

## Settled (do not reopen)

- Frank, 2026-11-08 (decision board): ADR 0068 **accepted**; `get_stream_table` and `explain` descriptions approved
  (human reviews are already in `REVIEW.json` on `wp/ST` — Frank's own script; never edit a human review entry);
  O3 = include the stream table in the web shell (done, WO-8b).
- ADR 0068 D3 amendment (ruling 5, implemented in WO-8a, DC-1…DC-6): stands on its default; the board item is open
  only for Frank's glance. Keep the dated amendment text as is.
- ADR 0025 D2.3 for `data_sha256` / `implementation_sha256`: ruled and applied (`be89d011`, `8ce17244`).
- Register block for ST: **R-1000…R-1009** (decisions.md, "register number blocks"). Main owns R-975/976 (MSG),
  R-950…955 (X02), R-960…969 + R-988 (OPT), R-970, R-980–987, R-990…996 (RRC). ST's own entries on the branch must be
  renumbered into R-1000… if they use any other id; references to main's ids are taken as main has them.
- Surface chain: main's served links are c_4 MSG, c_5 X02 (D_5 `f51b69bf…`), c_6 OPT (D_6
  `3fdc797ad64485abf63fb491ebd56aa43dc510e62e9e218b0dd7a8fcc2e38a85`); RRC added none. ST becomes **c_7** on top of D_6.

## Do

1. `git merge origin/main` (merge commit; no rebase). Expected conflict areas (handoff + log): register ids; the
   surface-chain fixture/test (G12, c_5/c_6 order → ST's link moves to c_7); `api_errors.yaml` (S2's one hunk); the
   catalogue YAML / `scan-allow.yaml` (keep both sides' entries); `ADDENDA` order (OPT's `opt` before ST's `st`, merge
   order); `HARVEST_SIZE`; the global-state cache count (main 39, plus whatever ST adds); `support_envelope.yaml`;
   T08.A20 envelope count (ST's `get_stream_table` on top of main's list). Hand-written sources: keep both sides; if a
   conflict is a real semantic clash (two different values for the same registered thing), stop and report.
2. Regenerate the generated files from their generators (never hand-edit): surface-chain link c_7 (the generator the
   chain test names), `scripts/t07_schema_fixtures.py --write`, `scripts/doc_pages.py`, `scripts/msg_catalogue.py
   sync-limitations`, `scripts/t08_support_matrix.py --emit`, CLI pins `--write-pins`, MCP digests as ST's handoff
   names them. Then each `--check`.
3. MSG catalogue G2: every user-visible code ST adds has a complete entry or an allow-list reason;
   `scripts/msg_catalogue.py check` PASS. A code without either: stop and report (wording is design-lane).
4. ADR 0068 status line → `Accepted (Frank Peters, 2026-11-08)`, D3 amendment kept; decision-register / ADR index
   entries in the repository's form, under R-1000….
5. Measure and record in `docs/ST_DECISIONS.md` (§ WO-7): c_7 digest and `without_st` = D_6; served documents moved
   (expected: none beyond ST's own surface); G7, G8, G8u unchanged from WO-8b (numbers in `docs/ST_HANDOFF.md`);
   cache count; A20 count; catalogue digest. Any movement in a number the handoff pins: stop and report.
6. Tests: every `tests/test_st_*.py`, `tests/test_m07a_surface_chain.py`, `tests/test_t07_global_state.py`,
   `tests/test_msg_*.py`, `tests/test_t07_w5b_cli.py`, `tests/test_t07_w5e_application_results.py`,
   `tests/test_t08*.py`, `tests/test_m07a_harvest.py`, `tests/test_evidence_manifests.py`, the description-review test,
   `tests/test_t07_conformance.py`; the web-shell node tests as WO-8b ran them. 0 failures. F0
   `scripts/corpus_identity.py --check` PASS; `ruff check`, `ruff format --check`.
7. Update `docs/ST_HANDOFF.md` in place (state, gates, next = CI then manifest). Commit named paths (one merge commit
   plus one or two follow-ups, messages naming ST and WO-7), push `wp/ST`, report the head sha. **No manifest yet** —
   the orchestrator watches CI and then briefs the manifest.

Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Cap ~150k context: if reached, commit what is complete,
write where you stopped in `docs/ST_HANDOFF.md`, end. TRS2 shared: `uptime` first; targeted tests only. Never read or
touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## Report (≤ 20 lines)

Conflicts and resolutions; c_7 digest; numbers of step 5 vs the handoff; test counts; F0 line; head sha; anything
stopped on.
