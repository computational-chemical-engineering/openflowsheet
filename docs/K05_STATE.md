# K05 — campaign state

**Rewritten in place, never appended.** A position, not a diary.

| | |
| --- | --- |
| Objective | Immutable `RunManifest`, events, artifacts, replay, deterministic structural hashes, dependency-mismatch detection (plan §4.2 row K05) |
| Branch | `main` directly; K03/K04 shared `wp/K03` and it is merged |
| Gate | `PATH=.venv/bin:$PATH ./scripts/check.sh` — **green at 1299 tests** on both architectures |
| Lead | **Opus / Fable.** Opus designs and implements; Fable reviews, because K05 touches replay identity (plan §1.3) |
| Manifest | `evidence/K05/b0a7fe766c35f6491dfc53ecab3101199d221850/manifest.json` — `status: tested`, 7 pass / 0 fail / 1 unsupported. Fable review returned and all six must-fixes closed |
| Requirements | D20 — `implemented` in the ledger |

## Where we are now

**G05 is closed.** Both architectures produce
`structural_sha256 = 28e01edaa9c71e8b5761889f4888fbe7f93daeae8a8ae7a00566bef7cbfd691d`,
and the CI `identity` job compares the R0 documents field by field.

**G03's replay half is done.** Six artifacts of a run are serialized with generated fixtures
across K03, K04 and K05; the certificate and failure half is recorded in K04's manifest.

ADR 0007 D4's table, measured row for row:

| Current environment | Mode |
| --- | --- |
| identical | `exact_replay` |
| another registered platform | `compatible_reproduction` |
| differing thread pins | `compatible_reproduction` |
| changed lock file | `inspected_archived_results`, verdict `NOT_RUN` |
| unregistered platform | `inspected_archived_results` |

## The correction CI forced

The first `structural_sha256` hashed the environment and the artifact index. CI produced two
different values across architectures **while every other R0 field was identical** — model
version, plan, eliminations, event sequence, certificate check results, regularity status,
solver counters. The hash was the only thing that moved, so it was measuring the platform
rather than the model. Blueprint §8.3 R0 promises structural artifacts identical *on supported
platforms*; the environment is provenance (D6, for attribution) and the artifact index hashes
documents containing floats. A changed dependency is still caught, and earlier, by the mode
decision.

## What the Fable review changed

Six must-fixes, each reproduced against the live code before anything was touched. Four of them
were routes by which a changed environment or an edited archive reached `exact_replay`/`MATCH`.

| # | What was wrong | Now |
| --- | --- | --- |
| M1 | The correction above had a **second half**: `structural_sha256` was also the manifest's self-check, so removing the environment and the index removed the only thing detecting an edit to either. Measured: editing `environment.lock_sha256`, or tampering an artifact and re-indexing its hash, both verified clean | `manifest_sha256` over the whole document. Identity and integrity are two questions; documented as a self-hash, not a signature |
| M2 | The verdict suppression was unconditional, so a certificate flipping to `FAILED` with no near-threshold flag anywhere reported `MATCH` | D2.4 applies only where the drift rule fired, on that artifact, at the document root |
| M3 | An empty lock hash compared equal to itself: `exact_replay` with the dependency set unknown on both sides | Unknown is never exact |
| M4 | `compare.py` carried its own copy of the numerical policy and it had drifted — `rcond_1` at 1e-8 against the registry's 1e-14, six decades looser. K04's A32 classified against the code's table, so the drift was invisible to the test written to catch it | Loaded from `benchmarks/k04/reference_values.yaml`; the invented 1e-24 fallback is gone (D2.3) |
| M5 | Only the current platform was checked, so an archive claiming s390x replayed as `compatible_reproduction` | Both sides checked; macOS arm64 out of the registered set |
| M6 | The clean-replay evidence was a tautology: the rerun was the archive re-read, so `bitwise_floats` measured `differences(x, x)` | A second solve, which reproduces the archive bitwise |

## What the review changed, part two: the should-fixes

All eight, plus Frank's F4 ruling. The largest is S1: the identity covered what a run was
*called* — ids, policy names and two words — and not what it did. `policy_sha256` now carries
the policy's values and `artifact_r0_sha256` a digest of the R0 projection, which moved into
production (`run/identity.py`) because the manifest and the G05 comparison both need it and two
copies would be one copy and one rumour.

F4 is visible in daily use: an unpinned machine gets `compatible_reproduction`, so the tests,
the fixture generator and the evidence script all pin the three variables as CI does. The
evidence script failed two checks the first time it ran after the fix, which was the ruling
working rather than a defect.

## Next action

**K06** — transactions, the CLI, the integrated example, and the v0.0 gate (G02, G06). The
Fable review is done and all fourteen findings are closed.

## Open items

| # | Item | State |
| --- | --- | --- |
| 1 | Clean-environment replay from a fresh container | `unsupported` in the manifest. What is measured is an in-process replay and a correct refusal when the environment differs; calling that a clean-environment replay would overstate it |
| 2 | macOS arm64 | In the registered platform set, never exercised. A bundle recorded there would be an inspection today |
| 3 | The backend is referenced, never archived | ADR 0006 D1.3 and mode C. A replay depends on the wheel still being fetchable |
