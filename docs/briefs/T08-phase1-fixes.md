# Brief — T08 Phase 1: release-blocking record fixes (D1–D3, typed ends, record fields, substitution proof)

**To:** `opus-engineer` (build lane). **From:** the session, 2026-09-29. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-release-spec.md` §6.1–§6.2 (classification, identity
re-registration), §9 (assertions T08.A10–A16), §15 Phase 1 (items W1.0, W1.2–W1.5, W1.7, W1.8). The defects
D1–D3 are described in `docs/T08_DECISIONS.md` (entry "peer-reported record defects").

## Scope

| Item | What | Assertion |
| --- | --- | --- |
| W1.0 | a test running `docs/derivations/scripts/t08_reference.py --check` and `t08_build_first_reference.py --check` | T08.A00/A01 |
| W1.2 | D1: `validation.py:385` STR-03 names the binder's `U-HEAT` instead of the revision's instance id; report instance ids in structural messages and `implicated` | T08.A10 |
| W1.3 | D3: failure bundles report `property_calls` 0 where the trace says 202. **Isolate the cause first** (hypothesis: the executor meter at `orchestrator/executor.py:883` is not in the region counters) on the three states the spec names, then fix | T08.A12 |
| W1.4 | D2: `verify/failure.py:188` `bundle_for` reads `getattr(result, "plan")`, absent on the region view → empty `replay_identity`; revision certificates' `policy_id`/`plan_id` empty. Carry plan/policy/revision ids through the region result view into bundles and certificates | T08.A11 |
| W1.5 | typed-ends sweep: the unmapped `rank.py` error class, R4-O2, R4-O1 (see `docs/T07_STATE.md` and spec §6.1) | T08.A14 |
| W1.7 | campaign/run records: commit, `tree_clean`, the lock hash, machine class | T08.A16 |
| W1.8 | the identity **substitution proof** after W1.3/W1.4 | T08.A13 |

Out of this increment: W1.1 (ledger; the session does it), W1.6 (A89 needs aarch64 CI repetitions — later),
anything in Phase 2+, and anything on the PTC-R1 case or warm starts.

## Identity (F4, approved by Frank 2026-09-29)

The `t07` key (`11bcb148…`) may move **only by substitution**: with the fix's new values replaced by the old
ones (empty strings; the wrong counter), the identity document must reproduce the registered one byte for
byte, and the old/new diff must consist only of the fields the fix names (spec §6.2, T08.A13; ADR 0017 D3 is
the precedent — find how it was proved). Every other key stays byte-equal: K05 minus-`t07` `9a7b4e6d…`, T02
floats `9a8a5baf…`, structural `915c97e8…`, keys `t02`…`t06`. Measure with the `measure_identity` protocol in
`scripts/t07_evidence_manifest.py`. **Any other moved byte: stop and report.** Record the new `t07` value.

## Known state of the branch

`check.sh` is currently **red on exactly 5 tests**, all caused by W4 offering `T08-warm-v1` (pending a
design-lane ruling): `tests/test_t07_v17_reference.py::test_g16b_reference_run[V17-T10-{python,cli,http,mcp}]`
and the `project_summary/valid/two_revisions_one_job.json` fixture test. Do not fix those; everything else
must be green, and you report any new failure.

## Forbidden — stop and report instead

No change to schemas, MCP tools or descriptions (T08.A49); no edit to specs, ADRs, YAMLs or
`requirements.lock`; no relaxed check or removed case. If a fix needs a scientific decision (the verifier,
certificates, residuals) that the spec does not make, stop and report with file:line.

## Working rules

Work in this checkout on `wp/T08`; nobody else edits it. One coherent commit per item, messages starting
`T08 W1.n:` and ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only. Never set
`reviewed`. `.venv/bin/python`; the path has a space — quote it. Budget: the user is near a weekly usage limit —
read only what you need, targeted tests while developing, the full `check.sh` once at the end.

## Report

Commits per item; D3's isolated cause with evidence; each assertion A00/A01, A10–A14, A16 pass/fail with
numbers; the substitution proof (old and new `t07`, the field list of the diff); `check.sh` counts; decisions
you isolated; questions you stopped on.
