# Build brief: ST review fix round (M1, S1–S4, text amendments) — 0.4

Status: brief, 2026-11-08. The review `docs/reviews/ST-review.md` (main `fb6a81f7`) is binding: read it whole first —
Must fix (M1), Should fix (S1–S4), Rulings, the description edits, and the MSG-merge notes. Branch `wp/ST`, worktree
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`, head `6f55fc19`; log `docs/ST_DECISIONS.md`, handoff
`docs/ST_HANDOFF.md`. **Do not spawn sub-agents yourself.**

## Scope, in order (one commit per item, messages `ST fix: M1 …` etc.)

1. **M1 — rule R1′** exactly as the review states it: heater-style lifted splits whose stream has an
   `independent_split` row `not_applicable` for `temperature_degenerate` or `fresh_flash_unresolved` read their phases
   from the carried `split.vapor`/`split.liquid` (summed from 0.0 as `_phase_enthalpy` does), labelled
   `phase_source: "carried_lifted_split"`; a flagged stream without such a split gets
   `flash_failed(status="temperature_degenerate")`, never a number. Derive the split the way
   `verify/certificate.py:765-770` does — do not import a second definition if the existing one can be called; never
   read the AD Jacobian or change anything under `verify/thermo/models/run/orchestrator` or `compiled.py` (G13). G8
   stays as written: remove the strict xfail only if T05b:SC-1 now passes; quote SC-1's and SC-3's closures before
   and after. Schema/fixtures for the new `phase_source` value as the review says. Record the amendment in
   `docs/adr/0068-stream-table.md` and the design note (D4, Q4.R12 (a) scope) using the review's text, marked as
   "from the ST review, 2026-11-08".
2. **S1** — the per-unit G8 over the corpus as the review specifies, and the A02-360 2.73e-3 W question (projection vs
   raw flash): measure and record the answer in ST_DECISIONS; if it reveals another defect, stop and report.
3. **S2** — the `not_found` variant keyed on `{job_id, output: "replay_bundle"}` in MSG's catalogue entry, the
   review's wording.
4. **S3** — the three exact description edits to `get_stream_table.md`; record the design-lane approval in
   `REVIEW.json` the way MSG did it (commit `8c935831` on `wp/MSG`); human review stays pending (never mark it);
   re-record the served digest and the surface tests.
5. **S4** — route from the bundle's `solve-path.json`, not specification roles; confirm all 44 0.3.0 bundles unchanged.
6. The text amendments the Rulings section names (D1-1, D1-6/7, D1-10…14), D4-1 as plain prose.

## Rules

- No released number, hash, bundle byte, cache key or replay may move: `scripts/corpus_identity.py --check` PASS at the
  end. No relaxed checks, no edited gates, no narrowed denominators. A scientific ambiguity the review does not settle:
  stop and report.
- Targeted tests only (`tests/test_st_*.py`, the surface/R4-G3, catalogue, description and A48 tests), one run at a
  time, `OMP_NUM_THREADS=1`; `ruff check`, `ruff format --check`, `mypy` on what you touch. No full gate (one is
  running on another branch). TRS2 shared: `uptime` first.
- Commit on `wp/ST` only, named paths (never `git add -A`), trailers `Co-Authored-By: Claude Opus 5.5
  <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`. Push `wp/ST`
  at the end. Do not merge into main. Never set `reviewed`.
- Context cap ~150k tokens: commit what is complete, rewrite `docs/ST_HANDOFF.md` (≤ 40 lines), stop.
- Never read or touch `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`;
  nothing in other worktrees.

## Report (≤ 25 lines)

Commits; SC-1/SC-3 closures before → after; G8 status; S1 per-unit result and the A02-360 answer; served digest old →
new; F0 line; anything stopped on.
