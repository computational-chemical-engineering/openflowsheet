# Build brief: ST WO-1 (core) and WO-2 (schema, without the registry entry) — 0.4

Status: brief, 2026-11-06. Spec: `docs/design/ST-stream-table.md` (Amendment 5 applied, e91f25d1) and
`docs/adr/0068-stream-table.md` (Proposed; Frank's acceptance pending — build proceeds, merge waits). Rulings:
`docs/roadmap/foundation-rulings.md` §17 Amendment 5 (Q1.R11–R12, Q2.R11, Q4.R10–R12; assertions Q1.A14–A15, Q2.A13,
Q4.A13–A16). Branch `wp/ST`, worktree `.claude/worktrees/st` (created from main at e91f25d1).

## Scope

- **WO-1** (design §10 row 1): `src/openflowsheet/application/stream_table.py` (`build`, `from_bundle`, §4 of the note:
  phase rule `st-phase-rule-v1`, property calls and formulas, quoted checks, energy summary) and
  `tests/test_st_core.py`. Acceptance: gates G1–G10, G14, G16 at core level (§11), and **no diff** under
  `src/openflowsheet/{verify,thermo,models,run,orchestrator}/` or `compiled.py`.
  - G3/E3 read their IAPWS-95 expectations from `docs/derivations/scripts/s05_reference.json` `/saturation/450` (molar
    values; M = 0.018015268 kg/mol), never from literals (O6, resolved).
- **WO-2** (row 2) **without the registry entry**: `_data/schemas/stream-table.schema.json` (§5), `tests/test_st_schema.py`,
  valid fixtures (one per basis from WO-1's output) and the invalid fixtures the row lists. The `schemas/registry.json`
  entry waits: that file is shared with `wp/MSG`, which merges first. Note it in the handoff as pending.

Files shared with MSG (`application/{contract,local,operations,authz,cli}.py`, `schemas/registry.json`,
`messages/catalogue/*.yaml`, surface-digest and R4-G3 tests, `interfaces-frozen.md`, `mkdocs.yml`): **do not edit**.
WO-3 onward start after `wp/MSG` merges.

## Rules

- Identity "no", proven: run `scripts/corpus_identity.py --check` (F0, M1–M9) at the end; it must PASS. No released
  number, hash, bundle byte, cache key or replay may move. Never adjust a gate.
- The design and Amendment 5 are binding. A scientific ambiguity they do not settle: stop and report (do not choose).
  Build choices: decide, isolate in one commit, log in `docs/ST_DECISIONS.md` (D1-…, D2-…); questions for the
  design lane are batched for ST's single reviewer pass.
- Run the tests you touch, and `ruff check`, `ruff format --check`, `mypy` on what you add. The full gate is not needed
  for this WO pair (it runs before the merge); a work-package branch may be pushed without it.
- Commit on `wp/ST` only, named paths (never `git add -A`), messages `ST WO-<n>: …`. Push `wp/ST` to origin at the end
  (not main). Do not merge.
- Context cap about 150k tokens: commit what is complete, write `docs/ST_HANDOFF.md` (≤ 40 lines), stop.
- Never read, stat or touch `~/.config/procsim/`; do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
  `~/.cache/seider4/`; nothing under other worktrees. No subagents.

## Report (≤ 25 lines)

Commits; each gate (G1–G10, G14, G16) pass/fail with key numbers (TH-C1: H(S5) − H(S1) vs the run's duties; the lever
rule; Table 8 at 450 K relative errors); F0 summary line; choices logged; design-lane questions.
