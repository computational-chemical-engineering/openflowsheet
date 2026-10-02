# Brief — T08: review 2 fixes, part B (transcribe the rulings into the spec, envelope, harvest and register)

**To:** `sonnet-implementer` (build lane). **From:** the session, 2026-10-01. **Branch:** `wp/T08`.
**Binding:** `docs/reviews/T08-review-2.md` — Rulings 1–4, 6, 9, 11–13 (§B: each gives the exact amended text),
§C (harvest edits, notes as written), §D item 4. You transcribe; you decide nothing. If a ruling's text is not
exact enough to transcribe, stop and report the ruling number and what is missing.

## What to do (one commit per numbered item; messages `T08 R2-B…:`)

1. **Spec amendment.** Append to `docs/derivations/T08-release-spec.md` a section "Amendment R2 (2026-10-01,
   transcribed by the build lane from `docs/reviews/T08-review-2.md`, design-lane rulings)" containing each ruling's
   amended text, marked with its ruling number, and mark the amended places in the body with
   "*(amended 2026-10-01, review 2 Ruling n)*" as the repo does for earlier amendments. Ruling 2 changes §5.2's
   components line (≈ :186). Do not rewrite history: amendment text plus markers only.
2. **Envelope and harvest.** In `benchmarks/t08/support_envelope.yaml`: rows L22 (split per Ruling 4) and L36–L39,
   U05 (Ruling 1's wording), backlog ids B10 and B11, and every harvest edit of §C, exactly as written. Then run
   `.venv/bin/python scripts/t08_support_matrix.py --emit` (check its `--help` for the exact form) to regenerate
   `docs/support-matrix.md`, and `--check` must report 0 problems.
3. **Register.** Add to `docs/decision-register.md`, in the format of R-126…R-128 (read R-128's section), the entries
   the rulings call for — at least: the reversal of T07 D-Q6 (Ruling 11, CLI `--rerun`), U05 as a refusal (Ruling 1),
   the evidence kinds (Ruling 6), the description review blocking the RC (Ruling 13). Number them from **R-129**.
   Update the "next free" index paragraph if it lists R numbers.

## Rules

Edit only `docs/derivations/T08-release-spec.md`, `benchmarks/t08/support_envelope.yaml`, `docs/support-matrix.md`
and `docs/decision-register.md`. No code, tests, schemas, ADRs or generators. Note: three registered literal guards
forbid certain literals in YAML under `benchmarks/` (the refined `eo_core` value, the edge-3 restart value,
`T05b-phase-contract-v2`) — if a transcribed text contains one, stop and report rather than re-spelling it.
Verification: `scripts/t08_support_matrix.py --check` 0 problems;
`PATH=.venv/bin:$PATH python -m pytest -q tests/test_t08_w2_support_envelope.py tests/test_t08_w2_unsupported.py
tests/test_t08_reference_generators.py tests/test_t05b_literal.py tests/test_t06_f4_literals.py tests/test_t06_w18_literal.py`
pass (report anything else red). Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only.

## Report

Commits; for each ruling, where its text went; the `--check` and pytest results; anything you stopped on.
