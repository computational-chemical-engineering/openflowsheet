# V02 alpha — the release-candidate record at `C_α`

*Superseded by R-349 (spec Amendment 2 §18.4): `C_α⁰` = `e0e198e` cannot reach a verdict; the re-cut candidate `C_α¹` = `6fec822`'s record is `docs/v02-alpha-rc-record.md`.*

V02 alpha release spec §8.2–§8.3 (WO-10), in `docs/t08-rc-record.md`'s form. This record **reports**; it judges no
gate. Each Result cell states what the step's record or CI job says, in the closed vocabulary
`scripts/v0_2_gate.py` reads through `v0_1_gate.py`'s grammar (Ruling 3: `PASS` / `success`; `FAIL` / `failure` /
`skipped` / not measured); the verdicts are the design lane's (`verdict`, §6.3). Every record the per-step table
cites is committed under `evidence/M07a/e0e198e4632224612671db5b07445639d272d6da/rc/` at the same relative path
(a record over 1 MB gzip-compressed beside it), and `rc/records.json` lists all 56 with sha256, size and how each is
kept (54 as is; the two ensemble run files gzip-compressed). `tests/test_m07a_rc_records.py` checks that the hashes
below resolve to them. The scripts that ran steps 10–12 locally are committed beside them, under
`evidence/M07a/e0e198e4632224612671db5b07445639d272d6da/tools/` (byte-identical to what ran; the Python ones with a
`.txt` suffix so that the linters of `check.sh` do not read them).

## The candidate and the runs

- **`C` = `e0e198e4632224612671db5b07445639d272d6da`** (`C_α`, "V02 alpha WO-10: cut C_α — version 0.2.0a1;
  envelope pinned v0.2-alpha-envelope-1 / 0.2.0a1 (MR-3)"). Package `openflowsheet` `0.2.0a1`. Its tree record is
  `release/rc-trees/e0e198e4632224612671db5b07445639d272d6da.json` (`259af65`, M07a.A44).
- **CI dispatch run 38667458248** (`workflow_dispatch`, `rc_alpha=true`, `rc_distribution=true`, head `C_α`):
  conclusion **success**. **CI push run 38667452347** at `C_α`: conclusion **success**.
- **Local steps** on `ref-x86-64` (AMD Ryzen Threadripper PRO 5965WX, Linux 6.12.111+deb13-amd64, Python 3.13.5),
  run 2026-10-15 from a detached worktree at `C_α` (`.claude/worktrees/rc-e0e198e`, clean throughout) in a venv of
  `requirements.lock` with the worktree installed editable (`--no-deps`), so every child imported `C_α`'s `src/`;
  threads pinned (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`). Steps 2 and 6–9 ran in the first
  session; that session's scratch (venv, logs) was lost before steps 10–12 finished, so a second session rebuilt the
  environments and re-ran steps 10, 11 and 12 in full (build decision B-WO10-11; `tools/run_local.sh`,
  `tools/run_local_g12.sh`, their one-line-per-command summary `tools/run_local.summary.txt`). The step-2 and 6–9
  records are the first session's, unchanged.
- **Step 12** ran in the reactor environment built from `C_α`'s `src/openflowsheet/adapters/pymrm/reactor-env.lock`
  (`python -m openflowsheet.adapters.pymrm.env build`, then `verify`: verified) under an external root outside every
  repository; the G12 runs through `tools/g12keep.py.txt`, which keeps the script's scratch directories so that step 10
  can audit their certificates (B-WO10-6). The host was shared with other work during step 12 (load average 86–90 on
  48 threads, `tools/host-load.txt`); G11v3's timings are recorded under that load.
- **Steps 11 and 12's records** `step11/rc-step11.json` and `step12/rc-step12.json` are written by
  `tools/m07a_rc_external.py.txt` through `t08_rc.finish` from M01's and M02's own records and the commands' exit codes,
  judged by the M01 and M02 manifests' own rules (B-WO10-8).

### Jobs of run 38667458248

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — `check.sh: PASSED`; pytest 8498 passed, 100 skipped | 1 |
| `check (ubuntu-24.04-arm)` | success — `check.sh: PASSED`; pytest 8470 passed, 98 skipped | 1 |
| `default-install` | success | — |
| `identity` | success — "G05: R0 structural identity equal across 2 platforms" | 2 |
| `dist` | success | 3 |
| `clean-install (ubuntu-latest)` | success | 4, 10 |
| `clean-install (ubuntu-24.04-arm)` | success | 4, 10 |
| `bundle-set` | success | 5, 10 |
| `bundle-replay (ubuntu-latest)` | success | 5 |
| `bundle-replay (ubuntu-24.04-arm)` | success | 5 |
| `rc-ensemble` (ubuntu-24.04-arm) | success | 6 |
| `rc-steps (ubuntu-latest)` | success | 2, 7–10 |
| `rc-steps (ubuntu-24.04-arm)` | success | 2, 7–10 |
| `ensemble`, `ptc-r1`, `ensemble-compare`, `a89-repeats`, `a30-inventory` | skipped (not RC inputs) | — |

All twelve artifacts downloaded (`gh run download 38667458248`); the job logs of the RC jobs saved under
`…/artifacts/rc/ci/job-logs/` (the `check` and `identity` logs cited below).

## Per step

Paths are relative to `evidence/M07a/e0e198e4632224612671db5b07445639d272d6da/artifacts/rc/` (and, committed, to
`…/rc/`).

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
| 1 | T08.A41 (M07a.A30) | CI x86-64 | success (`check.sh: PASSED`; ruff check, ruff format, mypy, pytest exit 0; 8498 passed, 100 skipped, 2 deselected) | `ci/job-logs/check-ubuntu-latest.log` | `aa3a6e00214ad71d2504af017af235eded24e2999b568341f6a35e381cb16796` |
| 1 | T08.A41 (M07a.A30) | CI aarch64 | success (`check.sh: PASSED`; 8470 passed, 98 skipped, 2 deselected) | `ci/job-logs/check-ubuntu-24.04-arm.log` | `2ddbb92603d2493a86d34960071929cef41e61e1ee39a78605dccefb83cebe15` |
| 2 | T08.A42 (M07a.A31) | local `ref-x86-64` | PASS (3/3): minus-t07 `24af004a…`, t07 key `887a2e62…` as registered (R-149); unchanged under the trial version `0.1.0`; whole document `174977cc…`, structural `ed6d11f3…`, T02 floats `9a8a5baf…` | `identity/rc-identity.json` | `4b62ab9e7db1a9fd44ba81115a73a7254cd3f7b5e2494c408503ac784aa9a770` |
| 2 | T08.A42 (M07a.A31) | CI `ci-x86-64` (`rc-steps`) | PASS (3/3); the same four digests | `ci/rc-steps-ubuntu-latest/identity/rc-identity.json` | `8641ca244ce31bb5540dca7cea254395f25ab51c82580a91379b6d1a09084d5e` |
| 2 | T08.A42 (M07a.A31) | CI `ci-aarch64` (`rc-steps`) | PASS (3/3); the same four digests | `ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json` | `8df5a75003cb80bb6657deda1c37f03b753cb70165310f69c59aca9675f5ee35` |
| 2 | T08.A42 (cross-arch, G05) | CI `identity` | success ("G05: R0 structural identity equal across 2 platforms") | `ci/job-logs/identity.log` | `bd7bfcd22bf9257555e56a154dfb4dbc5a7228fd1e21412cb8b11ea96750a61d` |
| 3 | T08.A43 (+A31 checks; M07a.A32) | CI `dist` | PASS (8/8); `a43.version` `0.2.0a1` from `__version__`, `pyproject`, the sdist and the wheel METADATA; wheel bytes equal across the two builds, sdist archive bytes differ with no differing member | `ci/rc-dist/t08-a43-dist.json` | `f670f9cc251c2a3411725d0c0aa78089865553f7a1e2ef64642c077beedfad23` |
| 4 | T08.A44 (M07a.A33) | CI x86-64 clean env | PASS (10/10); wheel `0.2.0a1`; CasADi = A30 digest `4be1571e…` and P03 per-file (2376 files); smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-latest/install-ubuntu-latest.json` | `2e5766a10946817dc58534d17271047922bfe847475ea7d8bfd0208a86bd2e23` |
| 4 | T08.A44 (M07a.A33) | CI aarch64 clean env | PASS (9/9); wheel `0.2.0a1`; CasADi = A30 digest `7a243303…`; smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json` | `4098a5e622c8debce3f59aff55815a7dfedf1fab513f3d6821483931b5cca034` |
| 4 | T08.A19 (b, c) | CI x86-64, `--state installed` | PASS (4/4); lock sha256 empty beneath a stray lock; replay `inspected_archived_results` | `ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json` | `d9b1507b0a02ab6d0730f5e3213c90c9abb9020586574b0902b556d99a283f53` |
| 4 | T08.A19 (a, c) | CI x86-64, `--state checkout` | PASS (4/4); lock `ead4edf1…` | `ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json` | `638fd028b234fa0cd5ad5a94c621d5113f79719940ae6b56b6d0063903de6f7d` |
| 4 | T08.A19 (b, c) | CI aarch64, `--state installed` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json` | `3a3581dc7dea8984047c32a0c36b8abef6a522fa609aba9fb1ea3206d5dfa495` |
| 4 | T08.A19 (a, c) | CI aarch64, `--state checkout` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json` | `4a7805bb6bf1153d0610526b3574bfdc0aba625caaacdb97d06903e23bc6b21e` |
| 5 | T08.A45 write (M07a.A34) | CI x86-64 `bundle-set` | success (job conclusion; the index carries no check list): `n_b` 52 (k05 5, g8 47), every entry exit 0; 49 CONVERGED / VERIFIED, 3 g8 runs with other registered outcomes (O3) | `ci/rc-bundles/index.json` | `92ee9a8e608e7306f355508e77fbd26d7c1f21ebadc6a731cbb6a4f7c46e6637` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI fresh x86-64 | PASS (8/8): same commit; `N_b` 52 = enumeration; every bundle `MATCH`, modes `exact_replay` 52; every bundle records `T08-numerical-policy-v2` (52); controls C1 and C2 `MISMATCH`, C3 `MATCH`, each as expected; sets k05 5, g8 47; near-threshold none | `ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json` | `139c1ae0c6a7b48903447d17160cb1516ffa1de60b8d0a6cfb7e74287f0d7c06` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI aarch64 | PASS (8/8): every bundle `MATCH`, modes `compatible_reproduction` 52; policy `T08-numerical-policy-v2` (52); C1, C2 `MISMATCH` and C3 `MATCH` as expected; sets k05 5, g8 47 | `ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json` | `d96bef971334d6bbdcbb5882f76a29eb7a91836070e7ff239ab6f3ca0434ccad` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | local `ref-x86-64` | PASS (7/7): N = 440, S = 434, F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3, no F-CRASH or F-OTHER-ROOT; gate S ≥ 418; none verified outside S3 (worst success ratio 0.0968); A33 0; T06 A34 same-class replay 28 of 28 MATCH; registered runs untouched; one-sided 95 % CP lower bound on S 0.973264 (in the report) | `ensemble/rc-ensemble-ref-x86-64.json` | `4deeaf6d0664857a1901b3fc5af2da89f192edf830d2fe25973057918bef63fe` |
| 6 | (run file, report, replay) | local | — | `ensemble/rc-ref-x86-64.json`, `ensemble/rc-ref-x86-64.report.txt`, `ensemble/rc-ref-x86-64.replay.txt` | `23040f4b80faeec6a4fa8f408b949135afff9d18a1026f3d266d216c0e4e3494`, `b35b327689a152bb4667782612a0eadaba0dd1af6183cc773d760fbc13038c43`, `26928c67d982988404fc4e4599d60a597f439e5b8b623d063afa34540ec3b2a8` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | CI `ci-aarch64` | PASS (7/7): N = 440, S = 434, F-BUDGET 4, F-FALSE-SUCCESS-CAUGHT 2, no F-CRASH or F-OTHER-ROOT; none verified outside S3 (worst 0.0968); A33 0; replay 28 of 28 MATCH; CP bound in the report | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json` | `5e2edb9d3ee862a3e761647a0b1f65b2af31e0cdcc731b3821fb178881ea9ec6` |
| 6 | (run file, report, replay) | CI `ci-aarch64` | — | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.report.txt`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.replay.txt` | `9ea8b86e0dae607af7706206d53b0a9deae4db1525c55cb5a7181df7efd2d74b`, `92cb4ce721aae11b700361b6ed50f7debe64beaafc48677485ae04d80833b137`, `b12d0fc4827ee99d38bbdcc56f753c117f28397e8286e955771f5e841aead483` |
| 7 | T08.A47, A48 (M07a.A36) | local `ref-x86-64` | PASS (12/12): A47 T06.A02–A08, A16, A19, A20; A48 T06.A47, A50; 165 nodes passed, none failed, missing or skipped | `corpus-ref-x86-64.json` | `42d944bda6cab6be48c082dbafb7eb077cb346aab643c4d2b1c33bc26da0c254` |
| 7 | T08.A47, A48 (M07a.A36) | CI x86-64 | PASS (12/12) | `ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json` | `b88facae19c373964e5da15228dd56e93f39e3f1953fd886aef0328bb507ad1f` |
| 7 | T08.A47, A48 (M07a.A36) | CI aarch64 | PASS (12/12) | `ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json` | `4de3dbddf0cf248b01302ab8598384f1aa09bbc33bed84adfa2b336fafe7cd96` |
| 8 | §5.3 chain + G16-b (M07a.A37) | local `ref-x86-64` | PASS (7/7): served `383b4e2c…` = `D_2`; strip c_2 → `6c4375b4…` = `D_1`; strip c_1 → `171dd768…` = `D_0` (R-133); with `v17-c2`'s texts `6d13e13d…` (R-137); the 17 tools and their description files; G16-b 40 of 40 clean; records attributable | `surface/rc-alpha-surface.json` | `9cd5d9697c8d5674569815acae5abc004c5dbc396b885ba7c2bb95cc3ab522b2` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI x86-64 | PASS (7/7); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-latest/surface/rc-alpha-surface.json` | `d6d8ebf8519bd18c7df67d606d758c76d602351dfaf79ec04ad4744fca5499aa` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI aarch64 | PASS (7/7); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-24.04-arm/surface/rc-alpha-surface.json` | `18f7adcb184b17c7343728e55ca23a19526849092402c0c8461ecec6504b6db9` |
| 9 | T08.A30 (M07a.A38) | local `ref-x86-64` | PASS ("A30 PASS"): 381 objects in 8 compiled distributions, required closure 150, no undispositioned finding in the closure, METIS not reached (O2) | `a30/a30-inventory-x86_64.json`; summary `a30/t08-a30-x86_64.json` | `76044103b995c139d7e8d024b17f46be8a382ed5b3cf38c66fb67867dca9bcdd`, `973da24d384a462659c99cd362c2aec9a69f4a717f936d61fdf9033f9165139c` |
| 9 | T08.A30 (M07a.A38) | CI x86-64 | PASS ("A30 PASS", exit 0): 381 objects, closure 150 | `ci/rc-steps-ubuntu-latest/a30/a30-inventory-x86_64.json`; summary `ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json` | `ba0192107a5aaf3980b84be604bb25ea26e84580268f223a941b92f075aada50`, `dab1651191b07ec1749c88b2369cac4ad5c64b941e2f61528ea0e76d3e796310` |
| 9 | T08.A30 (M07a.A38) | CI aarch64 | PASS ("A30 PASS", exit 0): 308 objects, closure 147 | `ci/rc-steps-ubuntu-24.04-arm/a30/a30-inventory-aarch64.json`; summary `ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json` | `5fbfe91ea1f7ebb0b8f75b72639d62be66950df6dea4a2697a2f0c88e8d6e1ed`, `b1aa32d66a0c9469d976575d8167c721f6734b5109d252a0f3d828a1c49186d6` |
| 10 | T08.A34 over steps 2, 6, 8 and 12 (MR-11; M07a.A39) | local `ref-x86-64` | FAIL (1/2): 77 certificates audited, 5 violations, all five step 12's coupled-route certificates (`a09.qualified_check_ids`, F1); the other 72 clean | `certificates-ref-x86-64.json` | `d4968328ab8b7d6c94f201dd83b9e418f183e0809f66a1bdba8c444154bcb810` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json` | `ca530e1857108592d157197ede382217096641bb8088a690ec120412da1d006b` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `78cc5267fbc93cc44219ef6f44841013cd2690c57609d9a8419b5325cd814d73` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json` | `2820a5d457e1f5746078b9778e4f34aa0e8355ea19404bb49f0db1ece5ab0830` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `70c0977b6aa18cf5fec043797c79c03e9a6b05a2636bdcb63793a3d7489e6737` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 bundle set (step 5) | PASS (2/2): 49 audited (of 52 bundles; the 3 unconverged G8 runs carry none), 0 violations | `ci/rc-bundle-set-certificates/rc-certificates.json` | `f8dda49a451b3bb159cf620f37c87405dff23602eaa03d8682b8ae0cf0748e61` |
| 11 | M07a.A40 | local `ref-x86-64`, pinned environments | PASS (3/3): `external_crosscheck.py --check` exit 0 ("external-crosscheck.json matches"); IDAES re-run exit 0; its numbers equal the committed record's, the one differing member `inputs.reference_values_yaml_sha256` | `step11/rc-step11.json` | `371957058ec96fcb31f80022b2d8ac7ff5e6da677f4ec9be12e6aed966e973dd` |
| 11 | (cross-check output, venv, IDAES record, venv) | local | — | `step11/external-crosscheck-check.stdout.txt`, `step11/venv-xcheck.freeze.txt`, `step11/idaes-conformance.json`, `step11/venv-idaes.freeze.txt` | `2f92bf5c59207de7c1f4f59e58c59087f73908eea14c14943edeb4499ae88bdc`, `94dfb7fb94245f4aaa8e23724e52f3642db91eb579f6ba904c65eaf0092d1539`, `7e1d41dd0da62c1685c2ea422e7891bb216c2e01bebb2e7ece7de22d4360adb4`, `dfeec96faebeb6bedab5eb1c069df7344282d0002fe92fb191f2c55c73af82c6` |
| 12 | M07a.A41 (M02 G10 (a)–(i), G11 (a)–(d), G12) | local `ref-x86-64`, reactor environment from `C_α`'s lock, one thread | PASS (6/6): environment built and verified (lock `032a050c…`); G10v3 met — A42 1.56 × 10⁻⁸, A45 3.84 × 10⁻⁸, A46 5.06 × 10⁻⁵, A47 (a) bitwise, (b) 1.43 × 10⁻⁸; G11v3 met, box V5, the two runs of 121 points equal; G12 CONVERGED / VERIFIED in 4 accepted iterates, ρ 0.292, floor ratios 65.3 (ξ) and 13.3 (T), `reproduce` MATCH, live rerun bitwise; edges converged and verified; M02 tests with the reactor 562 passed | `step12/rc-step12.json` | `9797561eb8a2b50584990721cde516cf3a452fa1a4111f042db01eb00dee6f68` |
| 12 | (G10, G11, G11 runs, G12, G12 edges, M02 tests, environment, host) | local | — | `step12/g10-adapter-halves-v3.json`, `step12/g11-coverage-v3.json`, `step12/g11-coverage-v3.runs.json`, `step12/g12-real-loop-v3.json`, `step12/g12-real-loop-v3-edges.json`, `step12/m02-tests.junit.xml`, `step12/env-manifest.json`, `step12/host.txt` | `81964cafe945e23637deb5706e704d29412ff52f91504549c6d8ba159c598a4d`, `586fc599ea6611dfe7c28921cba4e8cf8ab2828a9a0afe74490d566d71434cb3`, `3beb52bbdf88a93f75b9e404dade9589abde751c3cffb9d44ef103deaa751a17`, `56010f74736f9bbca8d042e4f4d55a9ec5841a51f4747a0feb798c0d72264425`, `f68cc88a42813c56c07459050ed618473e3d4278e12573bf33dcb95c2dc38249`, `8f43cc07e32601d0eda55fc96d3e230e0a591cacbaeda703120cb8bc1c6bc377`, `531206d1e25a4104c95ea25b9a5b57e504b429c10c153c55a21975133c20826c`, `d8c98f43c7211f745cb1423dd8439657498c0af1be6a39192b1709e4c2c4203f` |

**M07a.A43 (provenance).** Every `t08-rc-v1` record above (local and CI, the bundle index, both replay records and
the step-11 and step-12 records included) carries `commit` = `e0e198e4…`, `tree_clean = true` and
`environment_lock_sha256 = ead4edf1…b9c4`; `t08-a43-dist.json` carries the same at top level. A machine class is
carried by the identity, bundle-index, replay, ensemble, corpus, surface, step-11 and step-12 records; the 13
records of `t08_rc.py`'s `dist`, `install-check`, `lock-check` and `certificates` steps carry `architecture` and
`github_actions` but no `machine_class` (B-WO10-10, a question for the design lane). The A30 records carry
`lock_sha256` and the host, but no `commit` or `tree_clean` (format `t08-a30-inventory-v1`); M01's and M02's records
(steps 11, 12) carry neither, and are cited through the step's `t08-rc-v1` record. Stated, not judged.

## Step 13

`scripts/v0_2_gate.py --rc C_α` (M07a.A12) needs `docs/reviews/V02-alpha-verdicts.md`, which does not exist yet
(the `verdict` agent at `C_α`, §6.3). It has not been run; it is pending, not failed.

## Failures

- **F1 (step 10, MR-11; spec Q5).** T08.A34's audit over step 12's output finds 5 violations, all
  `a09.qualified_check_ids`: each of step 12's five coupled-route certificates (`g12-bundles/m02-g12-0/{bundle,
  live,replay}`, `g12-edges-bundles/m02-g12v3-2-{0,1}/bundle`) qualifies 25 check ids where the rule expects the 21
  checks with T06 A33's prefixes (`energy_balance.`, `phase_admissibility.`, `independent_split.`) whose result is
  `pass` or `fail`; the extra four are `EXT-COUPLING:reactor:T`, `EXT-COUPLING:reactor:xi`,
  `derivative_witness.on_pattern` and `derivative_witness.off_pattern`. None is missing. The other 72 certificates
  (steps 2, 6, 8) are clean, as are steps 4 and 5's on CI. Spec Q5's default applies: V18 (b) is `FAIL` at `C_α`
  unless the design lane rules otherwise; the rule is not narrowed here.

## Observations (not failures, not judged)

- **O1** The `check` skip counts differ between the platforms (100 / 98 skipped).
- **O2** The local x86-64 A30 summary differs from the committed `docs/t08-a30/t08-a30-x86_64.json` in the
  `files_digest` of all eight compiled distributions, the host's `platform` (a newer kernel) and `record_sha256`
  (at `67c66d9` the two were byte-identical); the CI aarch64 summary differs from `docs/t08-a30/t08-a30-aarch64.json`
  in the eight `files_digest`, the host's `python` and `record_sha256`. Object counts and closures are unchanged
  (381 / 150; 308 / 147). A30's verdict does not read these fields.
- **O3** The bundle index's three G8 entries that are not CONVERGED / VERIFIED have the outcomes their revisions
  register (2 initialization, 1 homotopy stall), each with exit 0, as at `67c66d9` (named here, outside the
  per-step table, because the gate script reads any `FAIL` substring in a Result cell as a failure).
- **O4** Step 6's class counts equal `67c66d9`'s on `ref-x86-64` (434; F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3) and on
  `ci-aarch64` (434; 4, 2).
- **O5** The step-12 record's own provenance shows no thread pins: the judging script ran without them; the
  measurements it judges ran pinned (G10's environment block: `OMP/OPENBLAS/MKL_NUM_THREADS=1`).
