# Reviewer brief: F2 (material model, ADR 0062), WO1 to WO7

Status: brief, 2026-11-27. Design lane, the package's single `reviewer` pass (LINE06 rules: one per package before
its merge), with the F2 ruling batch folded in. **Do not spawn sub-agents yourself.** Reading and running tests
only; no code edits. Rules: `docs/LINE06_RULES.md`.

## What to review

Branch `wp/F2` at `39244e80`, worktree `/home/eajfpeters/Code/OpenFlowsheet/.claude/worktrees/f2` (read and run
tests there; do not commit there). Diff: `git diff d00f659a...39244e80` (merge base with `main`; 145 files,
+13720/-184). Against: `docs/adr/0062-F2-material-model.md` (D1 to D13, exits E-F2-1 to E-F2-10, Q1 to Q8; D12 was
replaced before acceptance by design-lane ruling F2-R1, commit `df796cc2`). Build decisions: `docs/F2_DECISIONS.md`
(WO1-* to WO7-*; the R1 rulings at line ~458). Evidence: `evidence/F2/a3081770fa9555dcf10f30ce48995091c6c5011d/
manifest.json` (one commit before the head; WO7-4 after it). Another engineer works in `.claude/worktrees/f8`; leave
it alone. Logs only under `/home/eajfpeters/.cache/line06/f2rev/`. For tests:
`PATH=/home/eajfpeters/Code/OpenFlowsheet/.venv/bin:$PATH PYTHONPATH=src`; the `nlp` tests through
`scripts/m03_nlp_check.sh --no-inventory /home/eajfpeters/Code/OpenFlowsheet/.venv-nlp
/home/eajfpeters/Code/OpenFlowsheet/.reference-downloads/m03-ipopt -- <tests>`.

## Measured (by the build lane, judged by the orchestrator)

F0 PASS (M1 50/50, M2-M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 42/42) at every WO, last at `a3081770`. E-F2-3:
library half 59/59, run half 56/56 (`tests/test_f2_amendment9.py`, 124 + 1 nlp). WO6b battery at `ea0c1efd`: 5,859
passed, 2 failed (fixed in `b417eae3`). WO7 surface suites at `c08f90c9`: 2545 passed, 28 skipped, 3 xfailed.
Catalogue digest `2b227092…` -> `b6c8f517…` (WO7, re-pinned). No served digest moved after WO2b (`F2_SERVED_SHA256`
`9a4b4eb3…` = chain link c_11, R-1072). WO7-4 (orchestrator): `optimize_revision` lowers (D8); nlp 7 passed.
**Known red, for you (item 1):** `tests/test_v03_semantic_roles.py` a29, a31_a, a31_b (3 failed, 17 passed at the
head; they fail from `df796cc2` at the latest).

## The ruling batch (rule on each: keep / change, with the exact change)

1. **V03 A29/A31 against D12.** a29's corpus (`CORPUS_ROOTS` in the test, line ~73) now picks up the v2 fixtures
   (`tests/fixtures/schemas/v2/process_revision/valid/crystallizer.yaml` fails the v1 schema checks); a31_a ("no
   source file names the role", line ~286) finds `revision_v2/lower.py`, which D12 (F2-R1) requires to refuse a
   `semantic_role` outside v1's vocabulary; a31_b (line ~318) finds a binding outcome that the role moves. Rule what
   A29 and A31 assert after F2 (their intent: ADR 0054 (the `semantic_role` enum), the V03 spec (ADR 0053 line ~102 names it) and `docs/reviews/V03-review.md`), and give the
   exact test change, or state the code change if F2 is wrong. A narrowed corpus or check needs its reason in words.
2. **R1 open item (1)** (`docs/F2_DECISIONS.md` line ~555): does `validate` apply D11's "`h_mass` admits `std.*`
   units only" per `h_mass` definition or to every instance of an `h_mass` revision? Check the valid
   `crystallizer` fixture first. R1 open item (3) (F4's superset rule) keeps its default unless you see a defect.
3. **`check_admission.md` (WO6b-6, line ~600):** approve or edit the proposed text change (`<schema_version 1 or 2
   document>`, at most 1500 characters). It moves the served digest; the fix round registers the move.
4. **Catalogue prose (WO7-1, WO7-2):** the 18 entries WO4 added (`messages/catalogue/refusals.yaml`, `notices.yaml`)
   and the `molar_mass_inconsistent` and `attribute_grid_mismatch` param reconciliations. The prose was derived from
   the emit sites; say which entries misstate their meaning.
5. The build decisions: WO1-4 (STOP, `PropertyRequest` not widened), WO1-1 (kind lower bounds), WO1-9 (formation and
   transition kinds follow the amount basis), the `M = 1` for `kg` question (line ~84), WO2-1 (Q3.R1 (iii)), WO2-7
   (templates table), WO3-6 (layout refusals), WO4-7 (D10 strict), WO4-8 (solid roles), WO4-9
   (`state_degenerate_in_definition` not built), WO4-15 (Q8.A4's T rule), Q-WO5-a, Q-WO5-b, Q-WO5-c (lines ~377 to
   392), WO5-1 (probe scopes), WO6a-4 (`definition_sha256` exact), WO6b-7 (the run's revision reference), WO6c-2.

## Where to look hardest

D8 and E-F2-3: is every v1-path artifact of a lowered run byte-identical, and does any route (solve, job, optimize,
stream table, certificate, replay) still skip lowering? D12 after F2-R1: is every refusal reachable and tested, and
does the criterion admit exactly v1's documents? D4 and the basis code: exact arithmetic, no quantized cache key.
Test strength: would the tests fail if lowering dropped a field, or if a raised document's parameter set were wrong?

## Deliverable

`docs/reviews/F2-review.md`: verdict; findings M (must-fix) / S (should-fix) / N (notes) with file:line and a stated
fix; a ruling on each batch item; a numbered fix-round work order for the build lane (one Opus engineer). Commit on
**main** (`/home/eajfpeters/Code/OpenFlowsheet`, docs only, named path, message `LINE06: F2 review`, trailers
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session:
https://claude.ai/code/session_015Acof1nLKMy3Lsg6MpcJUZ`). Report at most 25 lines, including whether anything needs
the user (any ruling that changes ADR 0062's text before its acceptance card does: say which line goes on the card).
