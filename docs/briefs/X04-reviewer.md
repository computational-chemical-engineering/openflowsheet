# Reviewer brief: X04 (units at the boundary), WO-1–WO-4

Status: brief, 2026-11-09. Design lane, the package's single `reviewer` pass (ADR 0075's acceptance names "the
`reviewer` pass over WO-1–WO-4"). **Do not spawn sub-agents yourself.** Reading and running tests only; no code edits.

## What to review

Branch `wp/X04` at `bb4b21cd`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/x04` (read there; do not
commit there). Diff: `git diff origin/main...bb4b21cd` (36 files, +4325/−114). Core: `src/openflowsheet/units/display.py`
(412 lines, new), `messages/render.py`, `application/{stream_table,stream_table_format,local,operations,types,cli,contract}.py`,
catalogue `refusals.yaml`/`notices.yaml`, the two changed descriptions `bindings/descriptions/get_job_result.md` and
`get_stream_table.md` (+ `REVIEW.json`), schemas. Tests `tests/test_x04_{display_core,ambient,messages,stream_table}.py`.

Against: `docs/adr/0075-X04-units-at-the-boundary.md` (D1–D11), `docs/derivations/X04-test-specification.md` (A1–A40,
§4 site table), generator `docs/derivations/scripts/x04_reference.py` / `.json`. Build decisions D-1…D-12 in
`docs/X04_DECISIONS.md`; state in `docs/X04_HANDOFF.md`.

## Measured (by the build lane)

A1–A36 covered except WO-5's (A37–A40): display core 498 passed (all 400 round trips; ~62k seeded displays bit for
bit), ambient 41, messages 38, stream table 29. F0 PASS (M1–M9) — nothing stored or hashed moved. MSG check 391/95, G2
0. Targeted battery 1573 passed. **Known red, deliberately deferred to X04's final work order** (orchestrator decision,
`docs/roadmap/decisions.md` 2026-11-09): surface chain 14 (X04 takes c_8, R-1010…), R4-G3 snapshot 5
(`SNAPSHOT_X04`), t08_w2 surface digest 9, description review 1 (your pass is the design-lane review of both changed
descriptions).

## Where I am least sure — look hardest here

1. D3 arithmetic in `display.py` (exact decimal, shortest round-tripping search, fallback, out-of-range) vs ADR 0075
   D3 and the generator: any path where a displayed value does not convert back to the SI value, or a gauge offset
   reaches a pressure *difference* (D4).
2. D1/D10/D11 identity: can `display_units` or the ambient pressure reach a run, a cache key, a bundle, a certificate or
   a hashed document? (D-2 excluded wall-clock fields from A13's bundle comparison; D-12 fixed A13's flakiness — check
   both are sound and not a narrowed check.)
3. D-5 (`detail.reason` = full message head for `unsupported` refusals), D-8 (bundle-directory `streams` refuses gauge),
   D-9 (out-of-range display → absent), D-10 (header unit rules), D-6 (`phase_id.ordinal` never displayed), D-7 (the
   `get_stream_table.md` rewrite to 1499 of 1500 characters — read the whole text; no fact dropped?).
4. Test strength: would the tests fail if the conversion were applied to an unkinded number, or to a hashed document?

## Deliverable

`docs/reviews/X04-review.md`: verdict; findings M (must-fix) / S (should-fix) / N (notes) with file:line and a stated
fix; a ruling on each of D-1…D-12 (keep / change, with the change); the design-lane review verdict for each of the two
description texts (approve / approve with edits — give the exact edited text, keeping ≤ 1500 characters); a numbered
fix-round work order for the build lane. Commit on **main** (docs only, named path, message `docs: X04 review`,
trailers `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; `git pull --rebase` if rejected). Report ≤ 20 lines,
including whether anything needs Frank.

TRS2 shared: `uptime` first; targeted tests only (serial, `PYTHONPATH=src` with
`/home/frankp/Codes/OpenFlowsheet/.venv/bin/python`, from the x04 worktree). Never read or touch
`~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.
