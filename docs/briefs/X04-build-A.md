# Engineer brief: X04 engineer A — WO-1 display core, WO-2 ambient, WO-3 messages and get_job_result

Status: brief, 2026-11-09. Build lane. **Do not spawn sub-agents yourself.**

## Where

New branch `wp/X04` from `origin/main` (at or after `ced0082f`), worktree
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04` (`git worktree add -b wp/X04 .claude/worktrees/x04
origin/main`). Worktrees have no `.venv`: run `/home/frankp/Codes/OpenFlowsheet/.venv/bin/python` with
`PYTHONPATH=src` (CLI pin writer `PYTHONPATH=src:.`), confirm `openflowsheet.__file__` is the worktree's copy. Serial
tests (no xdist), `OMP_NUM_THREADS=1`.

## Spec (authority; implement it, decide nothing it settles)

- `docs/adr/0075-X04-units-at-the-boundary.md` (Proposed; decisions D1–D11; build proceeds on Proposed, Frank's accept
  is needed before merge; FQ1–FQ4 on their defaults).
- `docs/derivations/X04-test-specification.md`: sections U (WO-1), P (WO-2), M (WO-3) and T for `get_job_result`; the
  work-order list at ~line 305. Exact expected values come from `docs/derivations/scripts/x04_reference.json`
  (generator `x04_reference.py --check`). Write the tests the spec names (`tests/test_x04_display_core.py`,
  `tests/test_x04_ambient.py`, `tests/test_x04_messages.py`) asserting those exact values.
- Check OQ1 first (`grep -rn "Amendment 17" docs/adr`): if ADR 0019 Amendment 17 is taken, use the next free number
  and log it.

## Rules

- D1/D10/D11: nothing stored or hashed changes. Prove it: F0 `scripts/corpus_identity.py --check` PASS unchanged; the
  surface chain (`tests/test_m07a_surface_chain.py`) — an additive OPERATIONS change moves the served digest, so take a
  new link only as the spec says (if the spec is silent on the chain link, stop and report); global-state cache count
  test. Every new message code: a complete catalogue entry per ADR 0075 D9 (`scripts/msg_catalogue.py check` PASS, G2 0).
- A spec ambiguity that changes a number, an identity or a frozen interface: stop and report. Any other open choice:
  make it as an isolated commit and log it in a new `docs/X04_DECISIONS.md` (D-1, D-2, …).
- Small commits naming X04 and the WO. Cap ~150k context: commit what is complete, write `docs/X04_HANDOFF.md` (≤ 40
  lines: state, gates with numbers, next), end.

## Tests to run (targeted; no full gate)

New `tests/test_x04_*.py`; `tests/test_t06_w1a_units.py tests/test_t06_w12_units_v2.py tests/test_schemas_p01.py`;
`tests/test_msg_*.py tests/test_t07_w5b_cli.py tests/test_t07_w5e_application_results.py tests/test_t07_conformance.py
tests/test_m07a_surface_chain.py tests/test_t07_global_state.py`; anything a touched module's tests cover. 0 failures.
F0 PASS; `ruff check`, `ruff format --check`. Push `wp/X04`. No manifest, no merge.

Trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; named paths only. TRS2 shared: `uptime` first; targeted
tests only. Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
`~/.cache/seider4/`.

## Report (≤ 20 lines)

Commits per WO; assertions covered (A-numbers) and their status; F0 line; chain/catalogue numbers; test counts;
decisions logged; anything stopped on.
