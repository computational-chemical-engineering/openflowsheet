# Build brief: ST WO-3…WO-6 on top of wp/MSG — 0.4

Status: brief, 2026-11-08. Spec: `docs/design/ST-stream-table.md` (Amendment 5) and `docs/adr/0068-stream-table.md`
(Proposed; merge waits for Frank). Branch `wp/ST`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`,
head `dff3e439`. Start by reading `docs/ST_HANDOFF.md` and `docs/ST_DECISIONS.md` on that branch; WO-1/2 are done.
**Do not spawn sub-agents yourself.**

## Why now, and the base

All other 0.4 packages are built and wait for Frank. `wp/MSG` (`35403f42`) is reviewed and complete; it waits only for
Frank's human review of `explain.md` (a description text, not the registry or catalogue machinery). DECISION
(`docs/roadmap/decisions.md` 2026-11-08): ST WO-3…6 build on `wp/MSG` merged into `wp/ST`, instead of waiting for MSG
to reach main. First step: `git merge main` then `git merge wp/MSG` into `wp/ST` (no squash; resolve conflicts, log
them as D3-…). When MSG lands on main, `wp/ST` merges main again; MSG's merge-time renumbering (R-942/R-943 → new ids,
its c_4 surface link) is MSG's job — do not renumber anything of MSG's here.

## Scope (design §10 rows 3–6, as the handoff's "Next" lists them)

- **WO-3** operation: `LocalApplication.get_stream_table` mapping `StreamTableError` to `ApplicationError`
  (`not_found` via MSG's member-detail helper, `unsupported` with the hint, `internal_error`); the `OPERATIONS` row
  after `get_artifact`; the `schemas/registry.json` entry for `stream-table.schema.json` (fixes the 4 A48 failures in
  `tests/test_t08_w4_package_data.py`); gates G11–G13. Surface digests / surface chain links that move because of the
  new operation: follow the existing pattern (link after MSG's c_4; record the old and new digest in ST_DECISIONS).
- **WO-4** catalogue: the seven ST codes in MSG's catalogue (`messages/catalogue/*.yaml`), complete entries (what,
  where, why, what to do) — no stubs; G5's "every code is a catalogue key" against the real catalogue; G15.
- **WO-5** CLI `openflowsheet streams` (text, JSON, CSV), HTTP and MCP per the design; any new MCP description file
  needs the two recorded reviews (design lane + human) — add it to `REVIEW.json` with both pending; never mark either.
- **WO-6** docs (`mkdocs.yml`, user docs page) per the design.
- WO-7 (manifest, full gate, reviewer) is **not** in this brief.

## Rules

- Identity "no", proven: `scripts/corpus_identity.py --check` PASS at the end. No released number, hash, bundle byte,
  cache key or replay may move. Never adjust a gate. No relaxed checks.
- The design and Amendment 5 are binding; a scientific ambiguity they do not settle → stop and report. Build choices:
  decide, isolate in one commit, log in `docs/ST_DECISIONS.md`; design-lane questions batched for ST's reviewer pass.
- Run the tests you touch (targeted, `OMP_NUM_THREADS=1`), `ruff check`, `ruff format --check`, `mypy` on what you
  add. No full gate. TRS2 is shared: `uptime` first, one test run at a time.
- Commit on `wp/ST` only, named paths (never `git add -A`), messages `ST WO-<n>: …`, ending with the session's
  Co-Authored-By / Claude-Session lines. Push `wp/ST` at the end (not main). Do not merge into main.
- Context cap ~150k tokens: commit what is complete, rewrite `docs/ST_HANDOFF.md` (≤ 40 lines), stop.
- Never read, stat or touch `~/.config/procsim/`; do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
  `~/.cache/seider4/`; nothing under other worktrees.

## Report (≤ 25 lines)

Commits; G5, G11–G13, G15 pass/fail; the A48 tests; surface digests old → new; F0 line; choices logged; design-lane
questions; where you stopped if not done.
