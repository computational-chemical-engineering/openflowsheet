# T08 — the release-candidate record at `C`

Release spec §8.2 (as amended by R3), brief `docs/briefs/T08-rc-run.md`. This record **reports**; it judges no
gate. Each Result cell states what the step's record or CI job says, in the closed vocabulary `scripts/v0_1_gate.py`
reads (`PASS` / `success`; `FAIL` / `failure` / `skipped` / not measured); the verdicts are the design lane's
(`verdict`, T08 Phase 5). Records are git-ignored under
`evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/artifacts/rc/` (local) and `…/rc/ci/` (CI artifacts and
job logs); only their sha256 are committed here.

*Added 2026-10-02 (T08 close, release spec Amendment R7 1, verdict finding G6):* every record of 1 MB or less
that the per-step table cites is now also committed, byte-identical, under
`evidence/T08/67c66d98587f23bd7dfe8da28a8facccc92da21e/rc/` at the same relative path, and `rc/records.json` lists
all 44 cited records with sha256, size and whether committed (42 committed; the two ensemble run files
`ensemble/rc-ref-x86-64.json` and `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, 2.4 MB each, stay
hash-referenced under `artifacts/`). `tests/test_t08_rc_records.py` checks that the hashes below resolve to them.

**Superseded candidates.**

- `d2ff647` — F1: the CI `bundle-set` job could not upload the bundle set (a `:` in the G8 bundle directory
  `T05b:DZ-3`), so step 5's replay never ran. Record in `8ddd3d8`; fixed by `dbcbc89`.
- `814e151` — F2: step 5's aarch64 replay, 21 of 52 bundles `MISMATCH` under `K04-numerical-policy-v1`. Record in
  `660d815` (frozen copy `tests/fixtures/t08/rc-record-814e151.md`); followed by ADR 0025's
  `T08-numerical-policy-v2`.
- `89c3d77` — F3: `check.sh` on both CI architectures stopped at `ruff check` (I001: the spike
  `spikes/t03/w0_screen_measurement.py` still imported `process_runtime`; a stale local ruff cache hid it), and
  `identity` was skipped. Record in `1b4c2fb`; fixed by `b8276a8` (with the A30 summaries regenerated after the
  rename).
- `78e92b7` — F4: the CI `identity` job (G05's cross-architecture comparison) exited at import — `run/compare.py`
  imports `canonical`, which imports `numpy`, absent in that job — and, behind it, called `differences(...)`
  without the keyword-only `policy_id` that ADR 0025 W2 made required. Every other job and local step was as
  stated there. Record in `d7bfaeb`; fixed by `b7cd346` (the job installs `numpy` and passes
  `policy_id="K04-numerical-policy-v1"`, ADR 0025 W5).

## The candidate and the runs

- **`C` = `67c66d98587f23bd7dfe8da28a8facccc92da21e`** ("T08: log RC F4"). Package `openflowsheet` `0.1.0rc1`.
  Changes since `78e92b7`: the CI `identity` job (`b7cd346`, F4's fix) and documentation (`d7bfaeb`, `67c66d9`).
  The session reports `scripts/check.sh` green at `C` locally with a cleared `.ruff_cache`: 6817 passed,
  3 skipped (not re-run for this record).
- **Local steps** on `ref-x86-64` (host `Linux-6.12.86+deb13-amd64`, Python 3.13.5, `.venv` with the editable
  `openflowsheet-0.1.0rc1`), threads pinned (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`), run
  2026-10-02 from a detached worktree at `C` (`.claude/worktrees/rc-67c66d9`, clean) with
  `PYTHONPATH=<worktree>/src:<worktree>`. `t08_rc.py ensemble` sets its child's `PYTHONPATH` to the worktree root
  only, so that child imported `openflowsheet` through the editable install, i.e. from the main checkout's `src/`;
  the main checkout was at `C` with a clean tree throughout, so the bytes imported are `C`'s. Every local
  `t08-rc-v1` record carries `commit` = `67c66d98…`, `tree_clean = true`,
  `environment_lock_sha256 = ead4edf1…b9c4`.
- **CI dispatch run 37008077757** (`workflow_dispatch`, `rc=true`, `rc_distribution=true`, head `67c66d98587f…`):
  conclusion **success**.
- **CI push run 37008077056** at `C`: conclusion **success**.

### Jobs of run 37008077757

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — `check.sh: PASSED`; pytest 6809 passed, 11 skipped | 1 |
| `check (ubuntu-24.04-arm)` | success — `check.sh: PASSED`; pytest 6812 passed, 8 skipped | 1 |
| `default-install` | success | — |
| `identity` | success — "G05: R0 structural identity equal across 2 platforms" | 2 |
| `dist` | success — "T08.A43: PASS" | 3 |
| `clean-install (ubuntu-latest)` | success | 4, 10 |
| `clean-install (ubuntu-24.04-arm)` | success | 4, 10 |
| `bundle-set` | success — "bundles-write: 52 bundles (k05 5, g8 47); ok"; certificates PASS | 5, 10 |
| `bundle-replay (ubuntu-latest)` | success — "bundles-replay: PASS" | 5 |
| `bundle-replay (ubuntu-24.04-arm)` | success — "bundles-replay: PASS" | 5 |
| `rc-ensemble` (ubuntu-24.04-arm) | success | 6 |
| `rc-steps (ubuntu-latest)` | success | 2, 7–10 |
| `rc-steps (ubuntu-24.04-arm)` | success | 2, 7–10 |
| `a89-repeats`, `a30-inventory`, `ensemble`, `ptc-r1`, `ensemble-compare` | skipped (not RC inputs) | — |

All thirteen artifacts downloaded (`gh run download 37008077757`): `structural-identity-{ubuntu-latest,
ubuntu-24.04-arm}`, `rc-dist`, `rc-install-{…}`, `rc-bundles`, `rc-bundle-set-certificates`, `rc-replay-{…}`,
`rc-ensemble-ubuntu-24.04-arm`, `rc-steps-{…}`. Job logs saved under `…/rc/ci/job-logs/`.

## Per step

Paths are relative to `evidence/T08/<C>/artifacts/rc/`.

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
| 1 | T08.A41 | CI x86-64 | success (`check.sh: PASSED`; ruff check, ruff format, mypy, pytest exit 0; 6809 passed, 11 skipped) | `ci/job-logs/check-ubuntu-latest.log` | `5d2fa56e195ac9843b6b80b03dffbdab78aac6d27d599789f6c9a25a1adcf82e` |
| 1 | T08.A41 | CI aarch64 | success (`check.sh: PASSED`; 6812 passed, 8 skipped) | `ci/job-logs/check-ubuntu-24.04-arm.log` | `abf4056c07804d7cca49842677a3d8806402371adc7b4bbcd0ad78a82dd303b9` |
| 2 | T08.A42 | local `ref-x86-64` | PASS (3/3): minus-t07 `24af004a…`, t07 key `887a2e62…` as registered; unchanged under the trial version `0.1.0`; whole document `174977cc…`, structural `ed6d11f3…`, T02 floats `9a8a5baf…` | `identity/rc-identity.json` | `3cadf7fd07915fdfb359cc8532618077855678ecf746eba91013d7f7711586f7` |
| 2 | T08.A42 | CI `ci-x86-64` (`rc-steps`) | PASS (3/3) | `ci/rc-steps-ubuntu-latest/identity/rc-identity.json` | `a20219b3b3dd5a09ce4cf523379ae65ce1fff48db749cc1a1554a6b9e75c1c34` |
| 2 | T08.A42 | CI `ci-aarch64` (`rc-steps`) | PASS (3/3) | `ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json` | `55ea702fdb689260f1f8fe4d61218e2fdff636c2e0d64a6ca6969d0d98e36a88` |
| 2 | T08.A42 (cross-arch, G05) | CI `identity` | success ("G05: R0 structural identity equal across 2 platforms"): `identity.json` equal key by key on both architectures, structural `ed6d11f3…` on each; T02 floats compared under `K04-numerical-policy-v1` with no difference reported | `ci/job-logs/identity.log` | `1768de682e4df418acf95c29285bf8798e108b168c328ba450b879b845de4591` |
| 3 | T08.A43 (+A31 checks) | CI `dist` | PASS (8/8); version `0.1.0rc1`; wheel bytes equal across the two builds, sdist archive bytes differ with no differing member (`two_builds` pass as recorded) | `ci/rc-dist/t08-a43-dist.json` | `f6e98367e6f8020ab313b32acc4e5c67d3a7e12ff82e7602bae24769374cdd96` |
| 4 | T08.A44 | CI x86-64 clean env | PASS (10/10); CasADi = A30 digest `4be15715…` and P03 per-file (2376 files); smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-latest/install-ubuntu-latest.json` | `be358002a1f0d19f73d94e2278b18d885c91c72fbd52dbc943e3052cbfb8e807` |
| 4 | T08.A44 | CI aarch64 clean env | PASS (9/9); CasADi = A30 digest `7a243303…`; smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json` | `4acaeb8315ed93ded0b550ff0230a1071e8432b043a8cf2245e8950fc9f62b2b` |
| 4 | T08.A19 (b, c) | CI x86-64, `--state installed` | PASS (4/4); lock sha256 empty beneath a stray lock; replay `inspected_archived_results` / `NOT_RUN` | `ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json` | `4c2e09895c84631f2520c7760293d879195170b3a2eb49efbab205380e4f3b42` |
| 4 | T08.A19 (a, c) | CI x86-64, `--state checkout` | PASS (4/4); lock `ead4edf1…`; replay `NOT_RUN` | `ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json` | `e78f0d57e81364f4a2c495695f154059cf998032ea2941f887ea2cb857979353` |
| 4 | T08.A19 (b, c) | CI aarch64, `--state installed` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json` | `911f542f0148d65eea30c91e9f367e34464568d18787abbc05eb9a174016641f` |
| 4 | T08.A19 (a, c) | CI aarch64, `--state checkout` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json` | `0f4eb2ec6ed8dc2b27cc73e11863b3f5c9d1cbd1ab4eedfd713179566a1bbf21` |
| 5 | T08.A45 (write) | CI x86-64 `bundle-set` | success (job conclusion; the index carries no check list): `n_b` 52 (k05 5, g8 47), every entry exit 0; 49 CONVERGED / VERIFIED, 3 g8 runs with other registered outcomes (O4) | `ci/rc-bundles/index.json` | `8339e53dd3ba4f7d05f84a53667f581acc6e61d1739499bc5af3823b1c78c7e6` |
| 5 | T08.A45 (replay), A14 C1–C3 | CI fresh x86-64 | PASS (8/8): same commit; `N_b` 52 = enumeration; every bundle `MATCH`, modes `exact_replay` 52; every bundle records `T08-numerical-policy-v2` (52); controls C1 and C2 `MISMATCH`, C3 `MATCH`, each as expected; sets k05 5, g8 47; near-threshold none | `ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json` | `79c860223e27560b10a30ee4230530c673b339b237d9230d3604f1793456676f` |
| 5 | T08.A45 (replay), A14 C1–C3 | CI aarch64 | PASS (8/8): every bundle `MATCH`, modes `compatible_reproduction` 52; policy `T08-numerical-policy-v2` (52); C1, C2 `MISMATCH` and C3 `MATCH` as expected; sets k05 5, g8 47; near-threshold none | `ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json` | `621ff3d0e15db19f302632c60710de9a651517b39b8d6382af97fccf43034166` |
| 6 | T08.A46, A47 (S3) | local `ref-x86-64` | PASS (7/7): N = 440, S = 434 (S^first 370, S^rescued 64), F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3; gate S ≥ 418; none verified outside S3 (worst success ratio 0.0968); A33 0; T06 A34 same-class replay 28 of 28 MATCH; registered runs untouched | `ensemble/rc-ensemble-ref-x86-64.json` | `424aaeed37813fa510f9886e40aaff5798957a9c2fe6c2796242a3a116ca6781` |
| 6 | (run file, report, replay) | local | — | `ensemble/rc-ref-x86-64.json`, `.report.txt`, `.replay.txt` | `be4886a0656a48cfc1bc2e8b16677661bb43875533fde43c2b61ea80b795d8f3`, `d2b0551a4fa108335f68a8fa784192cfe5c50b5eb7d3dad4407a43d6d2cbfcab`, `be43efb86f7e08d80f4695ed0aed382828303722c4ceaeafb03607b18659dd85` |
| 6 | T08.A46, A47 (S3) | CI `ci-aarch64` | PASS (7/7): N = 440, S = 434 (S^first 367, S^rescued 67), F-BUDGET 4, F-FALSE-SUCCESS-CAUGHT 2; none verified outside S3 (worst 0.0968); A33 0; replay 28 of 28 MATCH | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json` | `0d1a2d2ee15e3bd367181620c0f2af5135ac354b66758eb0f44b3410881053c3` |
| 6 | (run file, report, replay) | CI `ci-aarch64` | — | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, `.report.txt`, `.replay.txt` | `ffb453ca1b23b9a98f54d424abd5e598cf4e98122aa11e6a9d5e36fcdfdb2e5b`, `292141bdd69f6f41f8b48c4bc3329746d32eee8ff132a498eeb3d955bd0b4ece`, `ae38f39796703890567caf63a64bd47d80e922d10d96e50bcc138d81f011d7e9` |
| 7 | T08.A47, A48 | local `ref-x86-64` | PASS (12/12): A47 T06.A02–A08, A16, A19, A20; A48 T06.A47, A50; 165 nodes passed, none failed, missing or skipped | `corpus-ref-x86-64.json` | `57f78270acedd75a48bac54e61cf1b3637e8d034ff5034a6fd9bebcf6038a2c8` |
| 7 | T08.A47, A48 | CI x86-64 | PASS (12/12) | `ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json` | `0a80e23915bf9d010566bc64e1baf22d5f67c6fc00b01f73655b792cb0b657be` |
| 7 | T08.A47, A48 | CI aarch64 | PASS (12/12) | `ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json` | `c28da08cecc185c345f4636713ae1e69bb3ece704341b8eb72448d82c0b32bf7` |
| 8 | T08.A49 (+A16 G16-b) | local `ref-x86-64` | PASS (4/4): served digest `171dd768…` = R-133's; served with `v17-c2`'s texts `6d13e13d…` = `v17-c2`'s; `equals_v17_c2_as_written: false` (the literal reading, recorded); G16-b 40 of 40 clean; records attributable | `surface/rc-surface.json` | `31aefca08b5ec232428efcd10fe7ccff3391ab9e59af205be8c54fe30e17680a` |
| 8 | T08.A49 | CI x86-64 | PASS (4/4); same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-latest/surface/rc-surface.json` | `3de318443af1eb4b4409e547d19024231f1c8cd814d7d254c574920454ad10c8` |
| 8 | T08.A49 | CI aarch64 | PASS (4/4); same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-24.04-arm/surface/rc-surface.json` | `1a9abc99ba6dfbe6df5cd87640b6dbd65ad8a14c0574316f4af8960386d53b43` |
| 9 | T08.A30 | local `ref-x86-64` | PASS ("A30 PASS", exit 0): 381 objects in 8 compiled distributions, required closure 150, no undispositioned finding in the closure, METIS not reached; summary byte-identical to the committed `docs/t08-a30/t08-a30-x86_64.json` | `a30/a30-inventory-x86_64.json`; summary `a30/t08-a30-x86_64.json` | `4b0c4f856bc9f2818890cb25eb6e7316cdeae312d24d052efbe5bf60dea731a0`; `d8564c8b7ca92f3ae765cb4c03460384eb63195c4b90615d5b71bfb651fb3dce` |
| 9 | T08.A30 | CI x86-64 | PASS ("A30 PASS", exit 0): 381 objects, closure 150 (summary vs the committed one: O2) | `ci/rc-steps-ubuntu-latest/a30/a30-inventory-x86_64.json`; summary | `d2886d4b1db0d31d73c073f605bf618fbb417f901c9208a5f7fccf7d30e5416c`; `4f60e382d39508d2b8952cd6e89fa057846569d387e0a1085ec944fdbc1623bc` |
| 9 | T08.A30 | CI aarch64 | PASS ("A30 PASS", exit 0): 308 objects, closure 147; summary byte-identical to the committed `docs/t08-a30/t08-a30-aarch64.json` | `ci/rc-steps-ubuntu-24.04-arm/a30/a30-inventory-aarch64.json`; summary | `56a12dbd6de60d2db9975f05d31d7cf9b5a02e7d7aade5a110b29156a500437c`; `49529a87f7bc7233cf59b70f5e332d139dd8f7adc8fea04f50a20f0ca8714d47` |
| 10 | T08.A34 | local, over steps 2, 6, 7, 8's outputs | PASS (2/2): 72 certificates audited, 0 violations | `certificates-ref-x86-64.json` | `69f187c03d1f8aff83a32a8787bacf69deaf2a483e1c855227965fa65a94c131` |
| 10 | T08.A34 | CI x86-64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json` | `b4058996384973103eddbd3f24eb703f55cba5eb33614d24118f02307b05db84` |
| 10 | T08.A34 | CI aarch64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `b04e38584279343b87e66cae80d9de11a9a3e956fa09ec97b46e3a6865af0b13` |
| 10 | T08.A34 | CI x86-64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json` | `b900f01996a55b2eaaebc7bbd23ceb6f5c5e568c2776e500d36d9b7c511f12d5` |
| 10 | T08.A34 | CI aarch64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `897070083034d03015234be3505d307b698a558a9f7422eab6c4b3fa0099b633` |
| 10 | T08.A34 | CI x86-64 bundle set (step 5) | PASS (2/2): 49 audited (of 52 bundles; the 3 unconverged G8 runs carry none), 0 violations | `ci/rc-bundle-set-certificates/rc-certificates.json` | `7a868bc66c92b2affbf9f41ea6997c0becbc4bf41dc9c89f0c03f38e1d8b198c` |
| 10 | T08.A34 | step 6 ensemble, both classes | PASS: `a34.ensemble_certificates` pass in both step-6 records, A33 0 | (the step-6 records above) | — |
| 11 | T08.A50 | local, `--rc` `67c66d98…`, candidate `HEAD` of the worktree (= this candidate) | FAIL (exit 1, the script's own decision: "v0.1.0 tag may be proposed: NO (3 reasons)"); at the candidate it read the previous record (of `78e92b7`), as this record did not yet exist; tree check (D2.4) "equal to C" | `v0_1_gate.log`; `--json` output `v0_1_gate_json.log` | `029311a96728e42c0927b33f1560704877c80620c9eae067565a102f0c730717`; `2df69a1189e27d27f51552c2e3ccf7d8e22d23b8752d58e2d19cdb578a4b0f2c` |

**T08.A16 (provenance).** Every `t08-rc-v1` record above (local and CI, the bundle index and both replay records
included) carries `commit` = `67c66d98…` and `tree_clean = true`, with `environment_lock_sha256 = ead4edf1…b9c4`;
`t08-a43-dist.json` carries the same at top level. The A30 records carry `lock_sha256 = ead4edf1…` and the host,
but no `commit` or `tree_clean` field (format `t08-a30-inventory-v1`); stated, not judged.

## The gate script against this record

`scripts/v0_1_gate.py --rc 67c66d98…` re-run in the main checkout with this record in place (candidate
`67c66d9`, the branch head at the time; its gate lines V11–V20 are those of the step-11 run). Its tail, verbatim
(exit 1):

```
tree check (D2.4): equal to C
RC record (§8.1 item 4): steps 1–10 passed at C
v0.1.0 tag may be proposed: NO (2 reasons)
```

The script lists no reason line under its decision; the two reasons are the gate lines' own: V13 (e) FAIL not
accepted in ADR 0021 D3 ("not releasable: FAIL clause not accepted in ADR 0021 D3: ['V13 (e)'] (D2.3)"), and V19
BLOCKED ("not releasable: BLOCKED blocks the tag (D2.2)"). V14 (b) FAIL is printed as accepted by Frank
2026-09-29 (ADR 0021 D3).

## Failures

None. No job, step or check failed at this candidate. (Step 11's FAIL is the gate script's own decision, its
reasons listed above; it is the design lane's to judge.)

## Observations (not failures, not judged)

- **O1** The `check` skip counts differ between platforms and from the local run (11 / 8 / 3 skipped).
- **O2** The CI x86-64 A30 summary differs from the committed `docs/t08-a30/t08-a30-x86_64.json` (made on
  `ref-x86-64`) in `host`, `record_sha256` and the `files_digest` of host-dependent distributions, as at every
  candidate; CasADi's digest is equal on both architectures (`a44.casadi_files_equal_a30` pass). The local x86-64
  and the CI aarch64 summaries are byte-identical to the committed ones.
- **O3** The installed wheel's version is `0.1.0rc1`; the identity step's trial version is `0.1.0`.
- **O4** The bundle index's three G8 entries that are not CONVERGED / VERIFIED have outcomes
  `INITIALIZATION_FAILED` (2) and `HOMOTOPY_STALLED` (1), each with exit 0, as their revisions register them (named
  here, outside the per-step table, because the gate script reads any `FAIL` substring in a Result cell as a
  failure).
- **O5** Step 6's counts are unchanged from the superseded candidates on both classes (ref-x86-64 370 + 64,
  ci-aarch64 367 + 67).
- **O6** Apart from `commit` (and, in the step-4 smoke output, a temporary bundle path), every local and CI
  `t08-rc-v1` record at this candidate is field-for-field equal to its counterpart at `78e92b7`, with two
  exceptions: the `dist` builds (new source tree and `SOURCE_DATE_EPOCH`, so new archive hashes; the two wheels are
  still byte-equal to each other, `4072fc1c…`), and the CI x86-64 identity record's T02 floats sha256, now
  `9a8a5baf…` (equal to the local one) where at `78e92b7` it was `e8136351…`. The CI aarch64 T02 floats file is
  `edbea3ca…` as before; the `identity` job compared the two float files under `K04-numerical-policy-v1` and
  reported no difference. The local ensemble's run file, report and replay text differ bytewise from
  `78e92b7`'s (their derived record does not).
