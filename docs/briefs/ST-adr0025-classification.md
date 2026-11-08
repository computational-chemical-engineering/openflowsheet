# Specifier brief: ADR 0025 D2.3 classification of ST's `data_sha256` and `implementation_sha256`

Status: brief, 2026-11-08. Small design-lane ruling. **Do not spawn sub-agents yourself.** Reading only, no test runs.

## The question

ST's `stream-table.schema.json` (on `wp/ST`, worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/st`, head
`3ba9edc3`) carries two `sha256` names in its `basis` (copied from each provider's `describe()`,
`src/openflowsheet/application/stream_table.py:944-945`) that T08's numerical policy has not classified; ADR 0025 D2.3
(`docs/adr/0025-cross-platform-replay-comparison.md`) refuses to default a new name, so
`tests/test_t08_adr0025.py`'s two A1 tests are red. **Exact or float digest, each?**

## Facts (from `docs/ST_DECISIONS.md` 8b-2, ~line 317 — read it)

- `implementation_sha256`: SHA-256 of the provider module's source bytes (`syn001.py:401`, `pr_lib.py:856`,
  `wilson_ig_v2.py:117`). Bytes.
- `data_sha256`: provider-dependent. SYN-001: `hash_named_doubles` over registered constants `R, T_REF, P_REF, C_P,
  T_BOIL_*, L_VAP_*, V_MOLAR_*` (`src/openflowsheet/.../syn001.py:406-422`) — a digest of float literals, not of solved
  state. pr_lib/pr_c1/wilson/iapws95: the data file's bytes. CoolProp: canonical JSON of version, fluid, fluid-file
  digest.
- Precedent: `benchmarks/t08/numerical_policy_v2.yaml` classes `constants_sha256` (registered constant doubles) exact;
  `level_constants_sha256` is float only because its vector holds a solved p⁰ (ADR 0010, ADR 0007 D1 row 3).
  Per-package addenda: `scripts/t08_numerical_policy.py` `ADDENDA` (M04 `2a4370aa`, M05 `c6c229e8`, E01 `b474ef71`,
  OPT `d5533e09`).
- Engineer's proposed default (not applied): both `exact_sha256` in a new `benchmarks/st/numerical_policy_external.yaml`
  (`ST-numerical-policy-external-v1`, schemas `[stream-table.schema.json]`), `st` added to `ADDENDA` after `e01`,
  `tests/test_m05_study_record.py`'s ADDENDA pin amended.

The question to settle: is a hash of registered float literals platform-stable by construction (same bits on every
platform, as `constants_sha256`), so "exact" is right, and does anything in how `hash_named_doubles` serialises them
break that?

## Deliverable

A numbered ruling appended to the "Design-lane confirmations (2026-11-08)" section of `docs/reviews/ST-review.md` on
`wp/ST` (one paragraph per name: class, reason, precedent), and, if you accept the proposed addendum, write
`benchmarks/st/numerical_policy_external.yaml` yourself in the existing addenda's format (it is a policy document);
leave the `ADDENDA` code line and the test pin to the build lane (name them exactly). Commit on `wp/ST` (named paths,
message `ST: ADR 0025 D2.3 ruling on data_sha256 / implementation_sha256`, trailers `Co-Authored-By: Claude Opus 5.5
<noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`), push. Report
≤ 10 lines. Never read `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.
