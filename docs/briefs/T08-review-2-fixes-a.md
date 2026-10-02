# Brief — T08: review 2 fixes, part A (code defects and the edge-identity tests)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-01. **Branch:** `wp/T08`.
**Binding:** `docs/reviews/T08-review-2.md` — findings M1–M3 and S-items it names, Rulings 1, 5, 6, 7, 8, 11 (with
their exact test specifications), §D items 1–3. Part B (spec/envelope/harvest transcription, §D item 4) is a
separate increment — do not do it here, except the inventory edits of §D item 3.

## Items (one commit each; messages `T08 R2-…:`)

1. **M2 / Ruling 1 — U05:** `validate(task="optimization")` (and the other studies Ruling 1 lists) refuses with
   `unsupported` / `task_unsupported(<task>)` instead of `READY_FOR_OPTIMIZATION` (`application/validation.py:293`).
   The U05 test node. Check every pinned fixture/digest that moves and prove it moves only by this change; if a
   registered identity document moves, **stop and report** (it would need Frank's approval).
2. **M3 / Ruling 11 — CLI `replay --rerun`:** route through `reproduce_bundle` (`application/cli.py:183-186`), no
   fallback to SYN-001-nominal; T08.A17's test as the ruling specifies. The register entry reversing T07 D-Q6 is
   written in part B — mention it in the commit body.
3. **Ruling 5/6/7/8 — `tests/test_t08_w2_edge_identity.py`:** the five identity tests (E1, E5, E7, E10, E12) and the
   E1/E2 reachability test exactly as specified; the T03 A16 `constants_sha256` injection parameter (E4).
4. **§D item 3 — inventory and scan (`docs/recovery-edges.yaml`, `tests/test_t08_w2_recovery_edges.py`):** E1/E2
   `library-only` + `reachability_tests`; the evidence pointers for E4, E7, E10, E11, E12 (E11 retitled); **M1**: the
   `route_fallback:` label family for `select_route` (`application/revision_run.py:202-206`) and its row; the scan
   fails closed on a non-constant event kind (S6); the E9 note. Afterwards T08.A33 should pass on every row; if a
   row still lacks evidence, it stays red — report it.
5. **T08.A18:** the test that stays red until the design-lane description review is recorded in
   `src/process_runtime/application/bindings/descriptions/REVIEW.json` (Ruling 13). It is **expected red** — this is
   honest, not a failure to fix. Do not edit REVIEW.json.

## Rules

No change to schemas, MCP tools or descriptions, specs, ADRs, YAML references, generators or `requirements.lock`.
Identity: `measure_identity` (`scripts/t07_evidence_manifest.py`) must give whole K05 `7f32b143…`, `t07`
`422aa7a5…`, minus-`t07` `9a7b4e6d…`, structural `915c97e8…`, T02 floats `9a8a5baf…` — check after items 1 and 2;
any move: stop and report. Work in this checkout; nobody else edits it. Messages end with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only; never set
`reviewed`. `.venv/bin/python`; quote the path. Budget: the user is near a weekly usage limit — targeted tests while
developing, the full `PATH=.venv/bin:$PATH ./scripts/check.sh` once at the end (expected red only on T08.A18).

## Report

Commits per item; tests added with results; A33 per row; identity values; `check.sh` counts (and exactly which
tests are red); questions you stopped on.
