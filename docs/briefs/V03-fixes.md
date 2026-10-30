# V03 brief 3: the review fixes and merge-readiness (build lane, one engineer)

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/v03`, branch `wp/V03` (head `1125d2bc`). The review is
`docs/reviews/V03-review.md` (exact text for every change; R-900, R-901). Previous handoff: end of `docs/V03_DECISIONS.md`.

1. **Merge `main`** (E01b merged at `51cd6847`: the Seider-checked cost set, A48 at 0, S12b manifest and harvest). Register:
   per-entry merge, keep every entry of both sides (main's order, then ours-only); envelope/harvest: keep both blocks,
   recount `HARVEST_SIZE` (manifests, items, unsupported checks: add each side's increments over the merge base), re-emit
   the matrix with `scripts/t08_support_matrix.py --emit` and `--check` 0. Never drop main's content.
2. **F-V1 (must-fix):** the `lca` entry of `MR12_AUDITS_V03` (`scripts/m07a_evidence_manifest.py:437-442`) runs
   `scripts/e01_d04_inventory.py --check` and cites R-900; spec §9.3 erratum; the two test-register edits; register R-900 and
   R-901 exactly as the review gives them.
3. **F-V2:** ADR 0049's "Met" line names G4–G8 (= S10C.A01–A61 per the S10-C spec §6) — check each against the S10c manifest
   first; state any that does not hold rather than writing it.
4. **WO-3's A48 item:** now that E01b is in, set what the spec's WO-3 says for "A48 tripwire at 0 after P2" and confirm
   `a48_release_check()` gives (pass, 0).
5. **F-E1:** state as a limitation (the envelope / E01 limitations, as the review's exact text says) that every P2 capital
   row is floored, so A33–A36 no longer exercise capital derivatives through the optimiser.
6. **F-E2:** a synthetic control in the cost tests with an entry at CE 394 (ratio ≠ 1), so the index ratio path is tested
   again; exact form per the review.
7. **The review's notes** for WO-6 (step17 record `step17/rc-step17c.json`; the W5c pins in §9.4): write them where the review
   says (spec erratum / WO-6 text).
8. If `main` by your end contains `docs-site/` (the docs branch is in its merge gate now), merge `main` again and fix the site's
   Wilson "source checkout" lines and the examples' turbine/compressor `semantic_role` (`turbine`/`compressor`, ADR 0054;
   re-run `tests/test_doc_examples.py` and `mkdocs build --strict` per `docs/DOC_DECISIONS.md` O1/O2). Otherwise say so.

Checks: the tests you touch, `scripts/t08_support_matrix.py --check`, `scripts/s11_identity.py` (PASS). Not the full gate.
Rules as brief 2 (`docs/briefs/V03-WO3-WO4.md`): DECISION lines in `docs/V03_DECISIONS.md`, private temp dirs (TMPDIR only for
`s11_identity.py`; do not share a `--basetemp` across its shards), named-path staging, no push, no subagents, no personal
identifiers to external services, never touch `~/.config/procsim/v17-token`, ~150k context cap with a handoff. Report in at
most 15 lines.
