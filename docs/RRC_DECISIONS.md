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
