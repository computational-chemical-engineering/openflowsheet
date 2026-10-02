# Brief — T08: merge v2 recording with the approved identity move; G3; B50's exact test; `k_ij` row; CHANGELOG table

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-02. **Branch:** `wp/T08`.
Context: `docs/T08_DECISIONS.md` entries of 2026-10-01/02 (verdicts at `814e151`; ADR 0025 build; the held branch).

## Frank's decision (2026-10-02)

Recording `T08-numerical-policy-v2` moves the registered K05 identity keys because `RunManifest.structural_sha256`
covers `numerical_policy_id`. **Frank approved re-registering them as a substitution-only move** (precedent: D2/D3
T08.A13, STR-05 R-…):
whole `7f32b143…` → `28dd8bf7…`, minus-`t07` `9a7b4e6d…` → `29246e05…`, `t07` `422aa7a5…` → `a96f17ed…`, structural
`915c97e8…` → `e62a59a6…`; T02 floats `9a8a5baf…` unchanged. (Full hashes: measure them; the prefixes are the
engineer's report.)

## Items (one commit each, `T08 …:`)

1. **Merge** `wp/T08-a25-recording` (`056f850` W3b, `4395df4` W8; rebased on `5b86e71`) into `wp/T08`
   (`git merge --no-ff`; resolve nothing by hand without saying so).
2. **Re-register** the moved values everywhere they are pinned: `tests/test_t07_identity.py`,
   `tests/test_t08_w1_identity_substitution.py`, the constants in `scripts/t08_rc.py`, `tests/test_t07_w5b_cli.py`'s
   `solve` stdout pin (structural `af86adb8…` → `f9536122…`), and any other pin a grep finds — each with a
   **substitution test** (v1 substituted back reproduces the old registered value byte for byte), following the
   existing substitution tests' pattern. Do not touch historical records (evidence manifests, T06/T07 run files,
   `tests/fixtures/t08/v0.0.0-*`, `benchmarks/t07/v17/runs/**`, RC records).
   Add register entry **R-148** to `docs/decision-register.md` (format of R-144/R-145): Frank's approval, the old and new
   values, the cause, the substitution proof, rejected alternatives (exclude the field from structural identity — moves
   every hash and changes its meaning; don't record v2 — contradicts ADR 0025 D1.2). Next free → R-149.
3. **G3** (`docs/reviews/T08-verdicts.md` finding G3): `scripts/v0_1_gate.py` reads §8.1's conditions and the RC record
   (`docs/t08-rc-record.md` for the named `--rc`): no tag proposal unless the RC record exists for that commit and every
   §8.2 step it lists passed. Test it (a failed step blocks; a missing record blocks).
4. **B50's exact test** (build-first spec Amendment 4, R-144): a test that the `list_models` and `get_project` content
   served today differs from `c7bbc98`'s exactly by `syn001.kinetic_cstr`, `T08-ptc-v1`, `T08-warm-v1`, excluding
   `server.package_version`. Find how `c7bbc98`'s content can be reproduced (a fixture at that commit, or rebuild
   from `git show c7bbc98:…`); if it cannot be done without a judgement call, stop and report.
5. **The `k_ij` rights row** (verdict finding on V19): in `docs/v02-real-chemistry-dossier.md`'s rights table, the
   `k_ij` row needs source, licence/permission, scope, mode. W3.3 used `k_ij = 0` for every pair (no source): record
   that as "none used (k_ij = 0, a modelling choice of the T08 smoke runs); M01 must select and cite a source" with
   status `needs_fact` for M01 — not `unknown`.
6. **CHANGELOG table**: `tests/test_t08_w4_changelog.py::test_the_gate_table_is_what_the_gate_script_prints` fails since
   the verdicts landed. Make the CHANGELOG draft's table equal what `v0_1_gate.py --markdown` prints now (it shows the
   verdicts at `814e151`), as that test intends.

## Rules

`requirements.lock`, specs and ADRs untouched (except the register). The MCP surface must stay as it is (served tool
list `dbc18fe3…`, descriptions `171dd768…`). Work in this checkout; nobody else edits it. Messages end with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`; stage named paths only. Budget: the user is
near a weekly usage limit — targeted tests, then `PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh` once (threads 1);
expected fully green.

## Report

Commits; the new full identity values; every pin moved and its substitution test; G3 behaviour; B50 test result;
`check.sh` counts; questions.
