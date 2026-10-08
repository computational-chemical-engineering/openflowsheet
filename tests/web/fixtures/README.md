# Web shell fixtures (M06)

Regression fixtures for the Node tests of the diagnostic web shell (`tests/web/*.test.mjs`).
Every byte here is a server answer, written by a script and never edited by hand. They are
regression fixtures, not validation: a correctness claim rests on an independent expectation
(the design note's G7 numbers below, and the analytic checks of the model tests), not on these
files agreeing with themselves.

| File | Written by | Held to the server by |
| --- | --- | --- |
| `expander.json` | `scripts/m06_web_expander_fixture.py --write` (M06 WO-6) | `tests/test_m06_wo6_expander_fixture.py` (`--check`: byte-equal to today's `projection.project`) |
| `w26/exchanges.json` | `scripts/m06_web_fixtures.py --write` (M06 WO-7) | `tests/test_m06_fixtures_valid.py` (every record schema-valid; the project is §8's) |
| `w26/raw/<job>/<member>` | the same run | the same test (bytes = the SHA-256 and size the bundle listing registers; record schema of the kind) |

## `w26/` — the W26 fixture project

`scripts/m06_web_fixtures.py` builds the project of design note §8 (`docs/design/M06-web-shell.md`)
through the contract with the inline executor, then asks, through `operations.dispatch` as the
right caller, every request the screens of §6 make: projected documents reassembled view by view
as `api.readWhole` asks for them, and the raw bytes of every bundle member. Timestamps and elapsed
times are not normalised; a rewrite therefore differs, and the files are written once and
committed. `tests/web/fixture-transport.mjs` answers `api.js` from them: it decodes each URL and
body back to the operation and its members and fails a test that asks for a record the fixtures
do not hold.

Grants: `agent-a` (read, draft, execute), `viewer-b` (read), `supervisor-c` (read, policy).

| Id | What | Outcome recorded |
| --- | --- | --- |
| `rev-000001` | `SYN-001-T06-NET02` | READY_FOR_SIMULATION |
| `job-000001` | rev-000001, policy `default` (→ `T06-revision-v2`) | CONVERGED, VERIFIED |
| `rev-000002` | NET-02 with `U-SPLIT` `split_fraction` 0.95 → 0.90 | READY_FOR_SIMULATION |
| `job-000002` | rev-000002, `default` | CONVERGED, VERIFIED |
| `rev-000003` | `SYN-001-conflicting-heater-spec` | INVALID |
| `rev-000004` | `SYN-001-A02-352-vapor-guess-410` | READY_FOR_SIMULATION |
| `job-000003` | rev-000004, `default` (→ `T04-W12`) | HOMOTOPY_STALLED, no verification status |
| `rev-000005` | NET-02, title `<img src=x onerror=alert(1)>` U+202E `evil`, description likewise | READY_FOR_SIMULATION |
| audit | `viewer-b`: `submit_job` and `list_audit` (all principals) | both `forbidden`, audited |

`exchanges.json`: `revisions`, `jobs` (the ids above), `numeric_query_members` (the query members
the HTTP binding reads as numbers, per GET operation), `shared` (115 records: answers that do not
depend on the caller, asked as `agent-a` — 53 `inspect_structure` views, 32 `artifact_bytes`,
5 each of `get_revision` and `validate`, 4 `diff_revisions`, 3 each of `get_artifact`, `get_job`,
`get_job_result` and `list_job_events`, 2 `list_jobs`, 1 each of `list_models` and
`list_revisions`) and `principals` (12 records: `get_project` and `list_audit` per principal, the
build's three `submit_job` answers, and `viewer-b`'s two refusals). A record is
`{status, body}`, or `{status, raw}` naming a file under `raw/`. 550 009 bytes.

### The G7 numbers, as measured in these files

Read off the raw records with a JSON reader (`python -c` over `raw/`), before any shell code ran;
the WO-8 model tests compute the same numbers in the shell's own code and assert them.

| G7 row | Measured |
| --- | --- |
| NET-02 run (`job-000001`): trace events | 27 (`solve-events.json`) |
| attempts | 2 (`attempt_opened`/`attempt_closed` at attempt 0 and 1; no homotopy correctors) |
| attempt 0 | BOUND_BLOCKED; deltas property 54 (55 − 1), residual 2, jacobian 2, factorizations 2 |
| attempt 1 | CONVERGED; deltas 135 (338 − 203) / 7 / 4 / 4 |
| totals (final event) | 338 / 9 / 6 / 6 |
| certificate | VERIFIED, 144 checks, 3 limitations, all `near_threshold` (`residual.U-MIX:MIX-energy`, `residual.U-HEAT:HEAT-duty`, `residual.U-PHF:PHF-equilibrium:A`) |
| `U-HEAT.Q` | 31487.641739605908 (short: `31487.6`) |
| A02-352 run (`job-000003`) | HOMOTOPY_STALLED; failure bundle `replay_identity.policy_id` `T04-W12`; `observations.counters.property_calls` 2104; inferred cause `phase_boundary_on_path(U-HEAT)`, kind `hypothesis` |
| NET-02 layout | computed by `js/model/layout.js` (WO-8); not a property of these files |

### Raw records

| File | Kind | Bytes | SHA-256 (first 12) |
| --- | --- | --- | --- |
| `w26/raw/job-000001/check-policy.json` | check_policy | 172 | `21c44e105a1b` |
| `w26/raw/job-000001/execution-plan.json` | execution_plan | 5530 | `84b88f9e87fa` |
| `w26/raw/job-000001/revision.json` | revision_document | 8012 | `b684aab6db85` |
| `w26/raw/job-000001/run-manifest.json` | run_manifest | 2330 | `d9b9bf4d15a9` |
| `w26/raw/job-000001/solution-certificate.json` | solution_certificate | 56582 | `3ceae8227f6c` |
| `w26/raw/job-000001/solution-state.json` | solution_state | 1664 | `d9cbaeda9eeb` |
| `w26/raw/job-000001/solve-events.json` | solve_trace | 13205 | `a17e716f4640` |
| `w26/raw/job-000001/solve-path.json` | solve_path | 77 | `3be5f79526fc` |
| `w26/raw/job-000001/solve-plan.json` | solve_plan | 4621 | `dda62af8ea37` |
| `w26/raw/job-000001/solve-policy.json` | solve_policy | 1726 | `c03d7205fb44` |
| `w26/raw/job-000001/structural-report.json` | structural_report | 12701 | `a8c7eff73e85` |
| `w26/raw/job-000002/check-policy.json` | check_policy | 172 | `21c44e105a1b` |
| `w26/raw/job-000002/execution-plan.json` | execution_plan | 5530 | `325f3024f5be` |
| `w26/raw/job-000002/revision.json` | revision_document | 8019 | `420a662ec22a` |
| `w26/raw/job-000002/run-manifest.json` | run_manifest | 2330 | `4f4aa356adf8` |
| `w26/raw/job-000002/solution-certificate.json` | solution_certificate | 55943 | `ad0523d7b30e` |
| `w26/raw/job-000002/solution-state.json` | solution_state | 1648 | `bc286e7d7c71` |
| `w26/raw/job-000002/solve-events.json` | solve_trace | 11704 | `171bdec6828c` |
| `w26/raw/job-000002/solve-path.json` | solve_path | 77 | `3be5f79526fc` |
| `w26/raw/job-000002/solve-plan.json` | solve_plan | 4621 | `f4cc9111eaaa` |
| `w26/raw/job-000002/solve-policy.json` | solve_policy | 1726 | `c03d7205fb44` |
| `w26/raw/job-000002/structural-report.json` | structural_report | 12701 | `e4416ae62167` |
| `w26/raw/job-000003/check-policy.json` | check_policy | 172 | `21c44e105a1b` |
| `w26/raw/job-000003/execution-plan.json` | execution_plan | 5510 | `3239e2f46bda` |
| `w26/raw/job-000003/failure-bundle.json` | failure_bundle | 2458 | `94f822d0495c` |
| `w26/raw/job-000003/revision.json` | revision_document | 11236 | `c42e455950ab` |
| `w26/raw/job-000003/run-manifest.json` | run_manifest | 2204 | `b21fc4bc4150` |
| `w26/raw/job-000003/solve-events.json` | solve_trace | 136278 | `42ec5b9d1e5f` |
| `w26/raw/job-000003/solve-path.json` | solve_path | 139 | `119a8d48e8e3` |
| `w26/raw/job-000003/solve-plan.json` | solve_plan | 4540 | `f481836bc203` |
| `w26/raw/job-000003/solve-policy.json` | solve_policy | 1687 | `1f7d11723fa2` |
| `w26/raw/job-000003/structural-report.json` | structural_report | 13334 | `40668c64efe1` |

Three kinds have no published record schema (`check_policy`, `solve_path`, `structural_report`);
the validity test holds them to being JSON objects and fails on any further kind without one.
