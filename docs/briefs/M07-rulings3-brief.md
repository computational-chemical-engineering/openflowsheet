# M07 ruling round after WO-3 — design lane (`specifier`), one pass

Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/m07`, branch `wp/M07` @ `271f70d` (pushed; CI 39089921525
green on both runners). Spec `docs/derivations/M07-spec.md` (§7 gate sets, §8 RC steps, §13 WOs, A30–A38 at l.368–376,
§18 Am. 1, §19 Am. 2). Build log `docs/design/M07-build-decisions.md` J38–J43 (read those entries; they hold the evidence).
Alpha-on-main rulings `docs/design/V02-alpha-main-rulings.md` (R-456…460, O1–O5).

## Rule on
1. **J40 / M07.A31 vs A30.** A31: "the alpha entry and its tests unchanged (its `clause` = the alpha's `CLAUSE`) — alpha
   tests pass unmodified". A30: the registry covers 29 versions, none twice, via `gate_set_of`. Five alpha test cases assume
   the alpha is the only gate set, or that 0.2.0 / b1 / rc1 are uncovered, so they cannot pass unmodified once
   `v0.2-gate-v1` exists. The engineer kept the alpha's text / `--json` / `--markdown` output byte-identical after every
   commit and isolated the five test edits in `039cbd8`. Accept (and restate A31 as "alpha output byte-identical; tests
   edited only where they asserted the registry's size"), or require something else.
2. **Confirm or reverse** the engineer's revertible choices J39 (re-judgement grammar and ADR name taken from the gate set,
   `0d5dbfb`), J41 (O3: the `V17 carry` row must name every register in `m07a_rc.LINKS` = R-192, R-234, R-295, `d4680b7`),
   J42 (carry checks' CLI options, `9479f97`), J43 (`tests/test_m07_ledger.py`: four checks skip on a `.devN` version; a
   separate test fails a 0.2.0 tree without the verdict document, `8a4c4e0`). A skip on `.devN` — is that a weakening, or
   correct scoping per R-460?
3. **Registration vs spec:** the registration names M07.A53 for RC step 17; the spec's table names M07.A62. Which is right;
   fix the other (generator + regenerate if the registration is wrong).
4. **ADR 0042's table headers** are not the ones the gate reads. Say which side changes (WO-6 builds the ADR tables).
5. **Journey carry:** the J′ = `974c395` journey no longer carries to HEAD (main changed 3 `src` files and 36 M05 record
   files, the latter by R-458's digest-only re-take). Confirm the plan: RC step 15 re-runs the journey at C (~1 h local,
   free). Note: R-458 orders another digest-only G10 re-take at the 0.2.0 cut, so carrying is unlikely anyway.

## Deliverable
Rulings as a dated amendment section in the spec (§20 Am. 3) with register entries (next free numbers above R-460 unused
on `origin/main` and here), restated assertion text where changed. Commit, push `wp/M07`. Docs and generator only.
Report ≤ 200 words. Keep context under ~100k; read narrowly.
