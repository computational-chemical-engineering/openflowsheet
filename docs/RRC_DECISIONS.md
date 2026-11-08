# RRC — build decisions (revision-region continuation, ADR 0072)

Append-only. One entry per open choice the build lane made, each in its own revertible commit:
`DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.` Design: `docs/design/RRC-revision-region-continuation.md`.

## WO-1 (2026-11-08)

- **D-1.** DECISION: When does `RRC-revision-v1` enter `APPLICATION_POLICIES` (the offered set)? → Not in WO-1; the
  policy is defined (`application/policies.py` `RRC_REVISION_V1`) but offered only once WO-3/WO-4 make its value
  executable. Reasons: (a) today's executor (`orchestrator/executor.py` `_eo_recovery`, the tuple at :892) treats any
  value other than `homotopy` / `homotopy_or_sequential_restart` as "no edge", so an offered `RRC-revision-v1` would
  silently run no recovery at all — a placeholder path (CLAUDE.md). (b) Offering it moves served content the design's
  §5.11 does not list: `get_project.solve_policies` gains an entry, so M07a's MR-7 clause
  (`tests/test_t08_b50_surface_content.py`, `V02_ADDITIONS["solve_policies"]`) needs a register entry naming
  `RRC-revision-v1`, and `tests/test_t07_w3a_revision_runs.py`, `test_t07_w5a_inspection.py` and
  `test_t07_b3_policies.py` pin the offered set. Those edits belong with the register numbering. Alternative: add it to
  `APPLICATION_POLICIES` now and edit the four tests. Reversible by: adding the one mapping entry plus those test edits
  (WO-4). Recorded for ADR 0072 C1 (a served-content move, not a digest move).
- **D-2.** DECISION: Where is a malformed `revision_continuation` (`variable_ids != ()` or `len(start_values) !=
  len(parameter_ids)`) refused? → `Continuation.__post_init__`, `ValueError`, for that type only; a
  `specification_continuation` is constructed exactly as before. Alternative: refuse inside `level_values`. Reversible
  by: moving the check.
- **D-3.** Observation, resolved by measurement (no choice made): `float(Fraction(-0.0))` is `+0.0`, so a start
  value of `-0.0` comes back as `+0.0` at λ = 0. That is the same constant: `canonical.encode_doubles` normalizes
  signed zeros, so `D` (which compares under that encoding, `continued_parameters`) and R8's level identity
  treat the two as one value (`tests/test_rrc_checks.py::test_d_compares_under_the_constants_encoding`).
- **D-4.** Not a choice, recorded for the reviewer: `tests/test_t06_f4_literals.py::test_wo1_the_literals_are_the_schema_enums`
  pinned `eo_recovery`'s enum as exactly ADR 0015's three values. The widening makes it four; the test now holds the
  Literal equal to the schema enum (its invariant, unchanged) and pins the four values in order. No other assertion
  of the file is touched, and the four edge-3 test files are not edited.

## WO-1 measurement: identity-bearing bytes (ADR 0072 C1, design §9 O2)

Measured before and after WO-1 on `wp/RRC` (`e45628fd` → WO-1):

| Bytes | Before | After |
| --- | --- | --- |
| `schemas/solve-policy.schema.json` sha256 | `e9866863…` | `f3b9f871…` (moved: the enum value and its description) |
| `schemas/attempt-context.schema.json` sha256 | `2eb2ad36…` | `78bbbc4c…` (moved: `const` → `enum`) |
| `schemas/solution-certificate.schema.json` sha256 | `dbff7aca…` | `c3571cee…` (moved: `const` → `enum`) |
| `schemas/registry.json` sha256 (a file list, no digests) | `5ffdcb29…` | unchanged |
| served MCP tool-list digest (`harness.tool_descriptions_sha256`, R-192 chain) | `455d01eb…` | unchanged |
| `policy_sha256` of `T04-W12`, `T06-revision-v2`, `T08-ptc-v1`, `T08-warm-v1` | `1f7d1172…`, `c03d7205…`, `aa0f1257…`, `32f484a1…` | unchanged |
| `benchmarks/t08/numerical_policy_v2.yaml` (`t08_numerical_policy.py --check`) | `6b449911…` | unchanged |

The old schema hashes appear only in archived per-commit RC dist lists (`evidence/*/rc/ci/rc-dist/t08-a43-dist.json`,
`release/rc-trees/*.json`), which describe those past commits and do not move. The next RC tree records the new hashes.

## WO-3 (2026-11-08)

Built on `main` (OPT's executor edits not pulled, per the work order; the merger resolves `RegionResult.final_system`).

- **D-5.** Not a free choice; the design's two sentences disagree and §5.8 decides. §5.5 says the action's tail is
  "exactly the homotopy branch's tail: `recovered_provenance(failed.bp, recovered.bp)`", but §5.8 names the recovery
  item's `initializer_source` `revision_continuation_source`, and `recovered_provenance` without
  `first_initializer_source` requires item 0's source (`traversal-G0-v1`) and raises a defect otherwise. →
  `recovered_provenance(..., first_initializer_source=REVISION_CONTINUATION_SOURCE)`, the restart's pattern.
  Alternative: none that keeps §5.8. Reversible by: dropping the keyword (then §5.8 must change).
- **D-6.** DECISION: The region refusal's message and the recorded reason → `revision_continuation_rejected(opening:
  <check>:<subject>)` in the region result; the executor records `opening(<check>:<subject>)`, e.g.
  `opening(active_set:S3.vap.A)` — G6(i)'s form. `<subject>` is `OpeningRefusal.subject` (a column or field id, R0);
  the observed float is never in the string. Alternative: §5.7's optional `[:<detail>]` omitted (`opening(active_set)`),
  which loses the column G6(i) names. Reversible by: one f-string in `region.py` and the `removeprefix` in
  `executor._revision_continuation`.
- **D-7.** DECISION: Does a passed §5.7 opening check emit `initializer_accepted` (as a passed warm-start check does)? →
  No. §5.8 lists the action's events as today's `homotopy_step` events only, and the recovery item's provenance already
  names the source; a new event would be a trace-kind use the design did not list. Alternative: emit
  `initializer_accepted(revision_continuation_source)`. Reversible by: one `run.record` in `region.py`'s new block.
- **D-8.** Structure only, isolated in `88b31d23`: the warm start's inline opening check became `_external_opening`
  (the same requirement, plus an optional `reported`), so the two external starts share one construction.
  `tests/test_t08_w4_warm_starts.py` 19 passed at that commit; F0 below. Reversible by: reverting `88b31d23` and
  inlining the check in the new block.
- **D-9.** Threading (no choice beyond §5.5's "the way `warm_start` is threaded"): the source reaches `_eo_recovery` from
  all three call sites — the revision region, the warm-started region (`_warm_start`), and SYN-001's region, where R3
  records `absent(not_revision_built)` and the restart's P3 then refuses (`test_r3_a_syn001_region_is_not_revision_built`).
