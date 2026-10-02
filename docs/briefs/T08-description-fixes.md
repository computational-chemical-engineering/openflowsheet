# Brief — T08: apply the description review; E7 test; S6 scan; audited `_prepare` refusal

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-01. **Branch:** `wp/T08`.
**Binding:** `docs/reviews/T08-description-review.md` (N1, N2 exact texts; Rulings 1–3). Frank, 2026-10-01: **keep
V17's carry** with the surface change recorded (no new campaign); his human review of the two changed files lapses
and he re-reviews them.

## Items (one commit each; messages `T08 D-…:`)

1. **N1, N2.** Replace `validate.md`'s first paragraph and `commit_change.md`'s one sentence with exactly the review's
   texts (check the review's stated character counts: 1190 and 1500 ≤ G15's cap).
   Update `REVIEW.json`:
   - every file's `sha256`/`characters` equal to the served text;
   - the **design-lane** review of all 17 → `reviewed`, `reviewed_by: "reviewer (design lane), docs/reviews/T08-description-review.md"`,
     `reviewed_at: "2026-10-01"` (the 15 approved at their hashes; the 2 at the new texts, which the review wrote);
   - the **human** review of `validate` and `commit_change` → back to `pending` (`reviewed_by`/`reviewed_at` null),
     because the text Frank reviewed changed; the other 15 keep Frank's 2026-09-29 record.
   T08.A18 therefore stays red on exactly the two human reviews — honest, until Frank re-reviews.
2. **The surface digest.** T08.A49/B50 pin the descriptions digest `6d13e13d…` (v17-c2's surface). Register the new
   digest beside the old: a test shows the new digest's file set differs from c2's in exactly `validate.md` and
   `commit_change.md`, and that restoring those two files reproduces `6d13e13d…`. Do not change the c1/c2 campaign
   references or `t08_reference.py`'s `v17_c2_tool_descriptions_sha256` (historical). Add a register entry
   (**R-133**, format of R-129…R-132) recording Frank's 2026-10-01 decision: V17 carried across the U05 behaviour
   change and the two description fixes; no campaign ran on optimization (cite the review); rejected: a new campaign.
   Grep for other pins of the descriptions digest or of these two files (G15, G16-b, MCP tool listing fixtures) and
   move each by this change only.
3. **Ruling 1 — E7's test** in `tests/test_t08_w2_edge_identity.py`, exactly as specified (B31's start via
   `test_b31i`'s own helper, `T06-revision-v2` only, patched vs unpatched, the listed assertions), and E7's
   inventory evidence → `identity_compared`. If B31's start does not go through the full revision solve, the stop
   condition stands: set E7's evidence `null` (A33 red on E7) and report.
4. **Ruling 3 — S6:** both clauses in the scan, two mutation cases; run it and confirm zero false positives.
5. **Audited `_prepare` refusal** (`application/local.py:1310`): `commit_change`/`preview_change` with
   `task == "optimization"` refuse at the top of `_prepare` with the same audited `unsupported` /
   `task_unsupported(optimization)` as `validate`. Test it.

## Rules

No schema, other description, spec, ADR or reference-YAML change. Identity: `measure_identity` gives whole K05
`7f32b143…`, `t07` `422aa7a5…` (descriptions are not in the identity document — confirm). Work in this checkout;
nobody else edits it. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only. `.venv/bin/python`;
quote the path. Budget: the user is near a weekly usage limit — targeted tests, full `check.sh` once at the end
(expected red: only T08.A18 on the two human reviews).

## Report

Commits; the new descriptions digest; every pin that moved; E7 outcome; S6 false-positive count; `check.sh` counts
and exactly what is red.
