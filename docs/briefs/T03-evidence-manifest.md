# Brief — `scripts/t03_evidence_manifest.py` (T03 acceptance item A26)

**To:** `opus-engineer` (build lane), worktree isolation
**From:** the session, 2026-09-24
**Branch to start from:** `wp/T03` (HEAD `43eb7ad` or later)

## The question

Write the script that generates `evidence/T03/<commit>/manifest.json` with one `checks[]` entry per
registered assertion `T03.A00` … `T03.A26`, each **measured by running the code in-process** and
compared with the independent expectation in `benchmarks/t03/reference_values.yaml` (the
specification's 40-digit twin) — never transcribed from prose.

## Rules (read `CLAUDE.md` first)

Work in your own worktree on a branch `wp/T03-manifest`; touch only `scripts/t03_evidence_manifest.py`;
commit, do not push or merge. Gate `PATH=.venv/bin:$PATH ./scripts/check.sh` stays green (if the
worktree has no `.venv`, use the main checkout's with `PYTHONPATH=<worktree>/src:<worktree>`). A failed
check stays failed; never set `review`; no angle-bracket values. Commit messages end with
`Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01QMQnXcFna3j5D6Ai9Ja9AE`.

## The pattern

`scripts/t02_evidence_manifest.py` is the template (same CLI `<gate-stdout> --commit <sha> [--out]
[--identities DIR] [--ci-run URL]`, same `check()` helper, same top-level fields, same status rule,
non-zero exit on any `fail`). Its author (you, on T02) imported case builders from `tests/` so the
manifest and the gate run the same fixtures — do the same.

## Where each assertion is

Authority: `docs/derivations/T03-phase-controller-spec.md` §11 (the catalogue — read it in full) and
`benchmarks/t03/reference_values.yaml`. The tests already implement each assertion; the manifest
records the measured values beside the expected ones.

| Assertions | Test file / source |
| --- | --- |
| A00 | `docs/derivations/scripts/t03_reference.py --check` (107 checks), the YAML's SHA-256 against the spec header, `--emit` twice identical, no `process_runtime`/`benchmarks` import (AST) |
| A01 | `tests/test_k03_schemas.py` (the literal refused/required), `SolvePolicy().as_document()["phase_contract"]` |
| A02–A05, A13–A18, A23 | `tests/test_t03_contract.py` (helpers `observe`, `synthetic`, `assert_refused`) |
| A06–A12, A24 | `tests/test_t03_phase.py` (helpers `run_case`, `assert_attempt`, `assert_final`) |
| A19–A22 | `tests/test_t03_roots.py` (helper `rec_05_run`) |
| A23 cross-platform | `scripts/t03_identity.py` inside the K05 identity document (key `"t03"`); with `--identities DIR` compare the two CI artifacts' `identity.json` key by key exactly as `.github/workflows/ci.yml`'s identity job does; without it, that half is `unsupported` |
| A25 | the gate stdout (all pass; K03, T02, K04, K05 files included) |
| A26 | this manifest: ids exactly `T03.A00`…`T03.A26`; `requirements: ["D09", "D11", "A01", "V15"]`; `limitations` restate spec §13 |

## Record, don't fix — known deviations for the review

1. The cycling `solve_closed` message changed with §4.10's grammar although §10 lists only OFF-B's
   `attempt_opened` message (tests `test_k03_attempts.py` updated).
2. `branch_provenance.decision` for an attempt whose proposed restart the gate refused is `restart`
   (the reference's convention), not `terminal`; spec §8.1's table is ambiguous there.
3. `delta_scaled_inf` is a float in the fingerprint; the spec says "no float is added"; it was
   registered as an ADR 0007 D1 exact field (K04 generator).
4. A removed row's parameter no remaining row reads is now dropped from the declaration (found by
   A20); the A02-360 revisions share one `constants_sha256`.
5. W9: a value-less `role: free` specification carries `bounds` (the schema requires value or
   bounds); the declaration is assembled with the flowsheet's declared default, then that orphan
   parameter is dropped.
6. PHS-05 is an expected failure handed to T04 (spec F1).

## Verify

Gate green; the script at your HEAD (no `--identities`) exits 0 with every check `pass` except the
A23 CI half `unsupported` (and A26 if you follow T02's `--ci-run` rule); the output validates against
the evidence-manifest schema and `tests/test_evidence_manifests.py`'s rules.

## Report

Worktree path, branch, commit, per-check summary with any non-pass and its reason, and anything that
looked wrong in the code (a finding, not a fix).
