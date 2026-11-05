# MSG build decisions (append-only)

Build-lane choices for package MSG that `docs/design/MSG-messages.md` leaves open (§9 and elsewhere). Each entry:
question, options, choice, reason, commit. The note's §9 names `docs/design/MSG-build-decisions.md` for this log; the
build brief (`docs/briefs/MSG-build-WO0-2.md`) names this file, and the brief governs.

## WO-0

**D0-1. What "the RC set" of MSG-G0 (b) is.** Options: (i) `tests/test_t08_w4_rc.py`'s cases literally (they write no
bundle: the file tests `scripts/t08_rc.py`'s steps); (ii) the bundle set that `t08_rc.py bundles-write` writes (K05's
registered SYN-001 runs and T07 G8's revision bundles, release spec §8.2 step 5). **Choice: (ii)**, run as a subprocess
of the current checkout. Reason: it is the RC job's bundle set, enumerated by the RC script itself. Commit: WO-0.

**D0-2. The 0.3.0 release bundles for (c).** None is in the repository or the local caches (the RC job's bundle steps
ran in CI). Per note §8 Q12's default: `msg_identity_gate.py write-v030` writes the RC set with tag `v0.3.0`'s own
code (`b8f47a04`), in a detached `git worktree` that is removed afterwards. 52 bundles (k05 + g8), kept under
`evidence/MSG/af35153…/artifacts/v030-rc/` (ignored). The baseline records each bundle's content digest, so a changed
input shows up as a (c) difference. "Each registered replay fixture" is every committed `run-manifest.json` directory
under `tests/` (the m07a and t08 SYN-001 fixtures and the three w26 web fixtures). Commit: WO-0.

**D0-3. C01–C03 before the corpus exists.** WO-9 writes the corpus; (b) needs C01–C03 now. The gate builds them
itself from `examples/rankine-cycle.changeset.json`: C01 boiler-T 973.15 K; C02 = C01 with S4 declared `vapor`; C03
reads `solution-state.json` from C01's bundle. C03 writes no bundle, so (b) records its refusal's `code` and `message`
(I1: both must stay; `detail` may gain members by WO-4). Measured at the branch point: C01
`initializer_failed(T): phase_regime_mismatch(S4)`, C02 `initializer_failed(T): isentropic_state_two_phase(T)`, C03
`not_found: no such artifact`. Commit: WO-0.

**D0-4. (d)'s SQL.** Stricter than the note's three tables: `jobs.worker_result`, `jobs.error`, `jobs.ending`,
`events.document`, `ledger.result` and the text columns of `audit`, each `CAST(col AS TEXT) LIKE '%"explanation"%'`,
over every `project.sqlite3` under the suite's `--basetemp`. `--suite` runs the default suite itself; `--stores DIR`
scans an existing base directory. A run that finds no store fails (d), so an empty scan cannot pass. Commit: WO-0.

**D0-5. The pre-MSG surface record.** The baseline's `surface` holds the served MCP tool-list digest
(`benchmarks/t07/v17/harness.tool_descriptions_sha256`), the SHA-256 of each `OPERATIONS` row's request and response
schema (canonical JSON; the "R4-G3 snapshots"), and the SHA-256 of every `schemas/*.json`. `--check` reports
`surface same|moved` but it does not decide MSG-G0 (MSG-G10 owns it). Commit: WO-0.

**D0-6. Determinism inputs.** Every measuring subprocess runs with the three thread variables at 1 (the run manifest
records them) and `PYTHONHASHSEED=0`. Commit: WO-0.
