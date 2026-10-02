# T08 — the release-candidate record at `C`

Release spec §8.2 (as amended by R3), brief `docs/briefs/T08-rc-run.md`. This record **reports**; it judges no
gate. PASS / FAIL / not-measured below is what each record itself says; the verdicts are the design lane's
(`verdict`, T08 Phase 5). Records are git-ignored under
`evidence/T08/814e1513b05f6c304c91a221adf58f587e96b7c0/artifacts/rc/` (local) and `…/rc/ci/` (CI artifacts and
job logs); only their sha256 are committed here.

**Superseded RC `d2ff647`: F1.** The RC at `d2ff6471c701…` (CI 36904782855) is recorded in `8ddd3d8` (this file's
previous version). Its `bundle-set` job could not upload the bundle set (`T05b:DZ-3` — a `:` in a G8 bundle
directory), so step 5's replay never ran. Fixed by `dbcbc89` (percent-encoded bundle directories); the RC below is
the next `C`.

## The candidate and the runs

- **`C` = `814e1513b05f6c304c91a221adf58f587e96b7c0`** ("T08: log RC F1 and the fix"); it differs from `d2ff647`
  by `dbcbc89` (`scripts/t08_rc.py`, `tests/test_t08_w4_rc.py`) and docs-only commits. The session reports
  `scripts/check.sh` green at `C` locally: 6719 passed, 3 skipped (not re-run for this record).
- **Local steps** on `ref-x86-64` (host `Linux-6.12.86+deb13-amd64`, Python 3.13.5, `.venv`), threads pinned
  (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`), run 2026-10-01 evening from a detached worktree at
  `C` (`.claude/worktrees/rc-814e151`, clean) with `PYTHONPATH=<worktree>/src:<worktree>`; the branch head moved
  to `e4ed6e9` (docs only) during the run. `t08_rc.py ensemble` sets its child's `PYTHONPATH` to the worktree root
  only, so that child imported `process_runtime` through the editable install, i.e. from the main checkout's
  `src/`; `git diff --quiet C HEAD -- src scripts benchmarks` was empty and the main tree clean, before and after,
  so the bytes imported are `C`'s. Every local `t08-rc-v1` record carries `commit = C`, `tree_clean = true`,
  `environment_lock_sha256 = ead4edf1…b9c4`.
- **CI dispatch run 36909737249** (`workflow_dispatch`, `rc=true`, `rc_distribution=true`, head `814e1513b05f…`):
  conclusion **failure** (one job: `bundle-replay (ubuntu-24.04-arm)`, F2 below).
- **CI push run 36909737415** at `C`: conclusion **success**.

### Jobs of run 36909737249

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — 6711 passed, 11 skipped (1308 s) | 1 |
| `check (ubuntu-24.04-arm)` | success — 6714 passed, 8 skipped (1011 s) | 1 |
| `default-install` | success | — |
| `identity` | success — "G05: R0 structural identity equal across 2 platforms" | 2 |
| `dist` | success — "T08.A43: PASS" | 3 |
| `clean-install (ubuntu-latest)` | success | 4, 10 |
| `clean-install (ubuntu-24.04-arm)` | success | 4, 10 |
| `bundle-set` | success — "bundles-write: 52 bundles (k05 5, g8 47); ok"; certificates PASS; upload ok | 5, 10 |
| `bundle-replay (ubuntu-latest)` | success — "bundles-replay: PASS" | 5 |
| `bundle-replay (ubuntu-24.04-arm)` | **failure** — "bundles-replay: FAIL" | 5 |
| `rc-ensemble` (ubuntu-24.04-arm) | success | 6 |
| `rc-steps (ubuntu-latest)` | success | 2, 7–10 |
| `rc-steps (ubuntu-24.04-arm)` | success | 2, 7–10 |
| `a89-repeats`, `a30-inventory`, `ensemble`, `ptc-r1`, `ensemble-compare` | skipped (not RC inputs) | — |

All twelve artifacts downloaded (`gh run download 36909737249`): `structural-identity-{ubuntu-latest,
ubuntu-24.04-arm}`, `rc-dist`, `rc-install-{…}`, `rc-bundles`, `rc-bundle-set-certificates`, `rc-replay-{…}`,
`rc-ensemble-ubuntu-24.04-arm`, `rc-steps-{…}`. Job logs saved under `…/rc/ci/job-logs/`.

## Per step

Paths are relative to `evidence/T08/<C>/artifacts/rc/`.

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
| 1 | T08.A41 | CI x86-64, aarch64 | success / success (6711 p, 11 s; 6714 p, 8 s) | `ci/job-logs/check-ubuntu-latest.log`, `ci/job-logs/check-ubuntu-24.04-arm.log` | — (job logs; conclusion from the API) |
| 2 | T08.A42 | local `ref-x86-64` | PASS (3/3: `minus_t07_registered`, `t07_key_substituted`, `unchanged_under_trial_version`) | `identity/rc-identity.json` | `3d7a554cbc36cc13e320fc3892bb21bce1202500518fa07ac042363221a53b18` |
| 2 | T08.A42 | CI `ci-x86-64` | PASS (3/3) | `ci/rc-steps-ubuntu-latest/identity/rc-identity.json` | `354fee5cc8152d1ea5f55b82c3fe7fce9d14094629b196c3515c3161c01a602f` |
| 2 | T08.A42 | CI `ci-aarch64` | PASS (3/3) | `ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json` | `2dc857c5b330be647bbd4718e44b3d6b09e27732db8290da100641080be88863` |
| 2 | T08.A42 (cross-arch) | CI `identity` | equal across 2 platforms; `identity.json` byte-equal on both and locally (`identity/as-built/identity.json`) | `ci/structural-identity-*/identity.json` | `7f32b1431226d11fd7b5b89f467525ca72648d6d7596df82d5d64b27d1ddf7e5` (all three) |
| 3 | T08.A43 (+A31 checks) | CI `dist` | PASS (8/8); version `0.1.0rc1`; wheel bytes equal across the two builds, sdist archive bytes differ with no differing member (`two_builds` pass as recorded) | `ci/rc-dist/t08-a43-dist.json` | `1e5a92d71f21e472d07c5b7c2070bee5953a6f82cef3f628fd17703a41a76dc6` |
| 4 | T08.A44 | CI x86-64 clean env | PASS (10/10; CasADi = A30 digest `4be15715…`, = P03 per-file, 2376 files; smoke solve CONVERGED/VERIFIED, 136 checks) | `ci/rc-install-ubuntu-latest/install-ubuntu-latest.json` | `b8118697d701e238a390c3a40be6d977382152f60a0d7c4b92cad0a06eedd074` |
| 4 | T08.A44 | CI aarch64 clean env | PASS (9/9; CasADi = A30 digest `7a243303…`; smoke solve CONVERGED/VERIFIED, 136 checks) | `ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json` | `6d93096e5943beb9c0b174e6ec972e6c3f6ec9bd76d780e1b4a274f2376bb9ad` |
| 4 | T08.A19 (b, c) | CI x86-64, `--state installed` | PASS (4/4; lock sha256 empty beneath a stray lock; replay `inspected_archived_results` / `NOT_RUN`) | `ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json` | `2936c6f4309910a43c74e791dae39105e8a2e302ba8680a5bd01fd68b596d76b` |
| 4 | T08.A19 (a, c) | CI x86-64, `--state checkout` | PASS (4/4; lock `ead4edf1…`; replay `NOT_RUN`) | `ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json` | `fb969474f607f25d2ba19d4b56af8cbfd85082bd05bbee2ca17601aefeded4ec` |
| 4 | T08.A19 (b, c) | CI aarch64, `--state installed` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json` | `f3e1ca5324b8834c712ff7bf40201dba912ec713aab24ed40e60824226f80f66` |
| 4 | T08.A19 (a, c) | CI aarch64, `--state checkout` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json` | `357eaf3482645c2951c5d091503317c6c796fc3a22566662b073782410eb83c6` |
| 5 | T08.A45 (write) | CI x86-64 `bundle-set` | 52 bundles (k05 5, g8 47), every entry exit 0; G8 directories percent-encoded (`T05b%3ADZ-3`, …) | `ci/rc-bundles/index.json` | `45efd3cfaaf0fba7132a5b48bb9806ea9c54cbc67cd4bda16832e379943ac05e` |
| 5 | T08.A45 (replay) | CI fresh x86-64 | PASS (4/4): same commit; `N_b` 52 = enumeration; every bundle `MATCH`, modes `exact_replay` 52; sets k05 5, g8 47; near-threshold none | `ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json` | `cb5684737d4f9be51c38a8f4433c9ef654314dba46761ab0183b5498739fbeb0` |
| 5 | T08.A45 (replay) | CI aarch64 | **FAIL** (3/4): `a45.every_bundle_matches` fail — 31 `MATCH`, 21 `MISMATCH`, modes `compatible_reproduction` 52, near-threshold none (F2) | `ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json` | `d716f857e4e6603ddff0aec80d820711bc52c2ba61773ecbc50622457bd571bb` |
| 6 | T08.A46, A47 (S3) | local `ref-x86-64` | PASS (7/7). N = 440, S = 434 (S^first 370, S^rescued 64), F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3; gate S ≥ 418; no verified outside S3 (worst success ratio 0.0968); A33 failures 0; T06 A34 same-class replay 28/28 MATCH; registered runs untouched | `ensemble/rc-ensemble-ref-x86-64.json` | `40ac803502d1847cdb2d1a8dffc2d112f282ba51f165b75c197910af273b9682` |
| 6 | (run file, report, replay) | local | — | `ensemble/rc-ref-x86-64.json`, `.report.txt`, `.replay.txt` | `7b6c81c7d8fc07e443f8259e94e5227b7dd4f78f92dc5dcb84dc80abf5d5eaa3`, `f355ea0bbff6491355d5c67968eab440223b3864d49960ba3dd9122f2ee0fbb6`, `d201e748946aae3079c8b0d3749ece54ebb90b180678ac2445972cc5815fe231` |
| 6 | T08.A46, A47 (S3) | CI `ci-aarch64` | PASS (7/7). N = 440, S = 434 (S^first 367, S^rescued 67), F-BUDGET 4, F-FALSE-SUCCESS-CAUGHT 2; no verified outside S3 (worst 0.0968); A33 failures 0; replay 28/28 MATCH | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json` | `f3d2b6da77ccd03df4a4e5eac64474f59fd7e561916779f285baa9ee770cc4aa` |
| 6 | (run file, report, replay) | CI `ci-aarch64` | — | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, `.report.txt`, `.replay.txt` | `76fb9304b67660ca5f64627d2fc58236773e8497b7fd94fe2a93027a095ca356`, `dca765ea81917bcaeefaffdbbaad4f5deb390e9d1a24b3c29386bb3be9a64144`, `45070aebfed1ea4cb781d52d854e50293671dcb3a1c3e5ae4c0e4c8d21fdd6af` |
| 7 | T08.A47, A48 | local `ref-x86-64` | PASS (12/12: A47 T06.A02–A08, A16, A19, A20; A48 T06.A47, A50; 165 nodes passed, none failed/missing/skipped) | `corpus-ref-x86-64.json` | `2c623ae1bd1a17ad0c3abde054f54aedea2d4915d288a694b5e5d81b88f7b5fd` |
| 7 | T08.A47, A48 | CI x86-64 | PASS (12/12) | `ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json` | `0f484aa709dbea7f09e30d13f5b1340288aa8f1ca584a8f482bcddb18e7ad231` |
| 7 | T08.A47, A48 | CI aarch64 | PASS (12/12) | `ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json` | `d32d99b47f8f1c45c699442fd6ae63889482e9fd984b9ffdf0fed333ca288576` |
| 8 | T08.A49 (+A16 G16-b) | local `ref-x86-64` | PASS (4/4): served digest `171dd768…` = R-133's; served with `v17-c2`'s texts `6d13e13d…` = `v17-c2`'s; `equals_v17_c2_as_written: false` (the literal reading, recorded); G16-b 40/40 clean; records attributable | `surface/rc-surface.json` | `7ae1aeb5c08bd0175495f1649748bf309bc6cee010f8bd10406f069b71341437` |
| 8 | T08.A49 | CI x86-64 | PASS (4/4, same digests, 40/40) | `ci/rc-steps-ubuntu-latest/surface/rc-surface.json` | `a9b513b4eac16f61419c5f279fe878e68e1493fe66bae161d011cde2501154bd` |
| 8 | T08.A49 | CI aarch64 | PASS (4/4, same digests, 40/40) | `ci/rc-steps-ubuntu-24.04-arm/surface/rc-surface.json` | `49714585ca2cb38b74ca8381dd0dc4b19a55dcf97581ecf63f431b796525df3e` |
| 9 | T08.A30 | local `ref-x86-64` | "A30 PASS" (exit 0): 381 objects in 8 compiled distributions, required closure 150, no undispositioned finding in the closure, METIS not reached. Summary **byte-identical** to the committed `docs/t08-a30/t08-a30-x86_64.json` | `a30/a30-inventory-x86_64.json`; summary `a30/t08-a30-x86_64.json` | `af29d5fd1f88d997b95e85c09456b63b56b177398bf946e0848accce80c7a97c`; `2485b3e38d31650192e08b36b4bca8e38c5d188830cc871eaf83c20a9fa74ff0` |
| 9 | T08.A30 | CI x86-64 | "A30 PASS" (exit 0): 381 objects, closure 150 (observation O2) | `ci/rc-steps-ubuntu-latest/a30/a30-inventory-x86_64.json`; summary | `8848f3940c7949212be0e1da4b79610290b9a8dd895febcf32b42fdfbb8d90c7`; `5e5484955e0feb72af0d26c2c418cf592a3e342d941be2487a5cf1444aa362fa` |
| 9 | T08.A30 | CI aarch64 | "A30 PASS" (exit 0): 308 objects, closure 147. Record sha256 = the one the committed `docs/t08-a30/t08-a30-aarch64.json` names | `ci/rc-steps-ubuntu-24.04-arm/a30/a30-inventory-aarch64.json`; summary | `7c27517e0aa344a1a545da09381a69faa12253c8feeaa6fb063abd1ed6fb1943`; `9fa340ecd5720b7e50126bf46629012c75dc6390d3d66af1f9f7ff40e4c520e9` |
| 10 | T08.A34 | local, over steps 2, 6, 7, 8's outputs | PASS: 72 certificates audited, 0 violations | `certificates-ref-x86-64.json` | `7dceb387c8e4c70bb88d5bc593e05b1e6580a992bc09b3323d7b0b0bbd165652` |
| 10 | T08.A34 | CI x86-64 `rc-steps` | PASS: 72 audited, 0 violations | `ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json` | `3f872f8c9909d640fb17deb990ab48ec3eb3e1d15dd2a6f8e3fe0651a76809ad` |
| 10 | T08.A34 | CI aarch64 `rc-steps` | PASS: 72 audited, 0 violations | `ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `18061a4ed13945585f385bc127e3be1b797eeb8ee12eea42642a00d9ccd47f1c` |
| 10 | T08.A34 | CI x86-64 clean install (step 4) | PASS: 1 audited, 0 violations | `ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json` | `4c62b250466017cb21a55e338a3224b4f64a7b1a59bb2607d6297d9dda829880` |
| 10 | T08.A34 | CI aarch64 clean install (step 4) | PASS: 1 audited, 0 violations | `ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `ce5ce088efb8b36e30894c976573384f62e7a2a218f9304d4e894615a4b423f8` |
| 10 | T08.A34 | CI x86-64 bundle set (step 5) | PASS: 49 audited (of 52 bundles written), 0 violations | `ci/rc-bundle-set-certificates/rc-certificates.json` | `51e2e15744c2237b6f005c8e9964d3b060eddc5b9b509a9bae742174ba69ff95` |
| 10 | T08.A34 | step 6 ensemble (both classes) | inside the ensemble records: `a34.ensemble_certificates` pass, A33 failures 0 | (the step-6 records above) | — |
| 11 | T08.A50 | local, `--rc C`, candidate `HEAD` of the worktree (= `C`) | exit 1: "v0.1.0 tag may be proposed: NO (21 reasons)"; every gate V11–V20 "no verdict"; tree check (D2.4) "equal to C" | `v0_1_gate.log`; `--json` output `v0_1_gate_json.log` | `f41f8e8578aa4d9e9ee4b7ff1b0a3db02d9c74ac30174a5f9052d0eb9aa53d61`; `4040caa94454b948e3f3a1a64128fa8228ef96875b2308a841fcb305aebf44dd` |

**T08.A16 (provenance).** Every `t08-rc-v1` record above (local and CI, the bundle index and both replay records
included) carries `commit = C` and `tree_clean = true`, with `environment_lock_sha256 = ead4edf1…b9c4`;
`t08-a43-dist.json` carries `commit = C`, `tree_clean = true` and the same lock hash at top level. The A30 records
carry `lock_sha256 = ead4edf1…` and the host, but no `commit` or `tree_clean` field (format
`t08-a30-inventory-v1`); stated, not judged. (The A30 records of this RC are byte-identical to those of the
superseded RC, local and CI.)

## Failures

**F2 — step 5, aarch64 replay: 21 of 52 bundles `MISMATCH`.** Verbatim (`ci/job-logs/bundle-replay-ubuntu-24.04-arm.log`):

```
PASS a45.same_commit
PASS a45.n_b_equals_the_enumeration
FAIL a45.every_bundle_matches
PASS a45.every_set_enumerated
bundles-replay: FAIL (/home/runner/work/_temp/rc-replay/replay-ubuntu-24.04-arm.json)
##[error]Process completed with exit code 1.
```

Every aarch64 replay ran in mode `compatible_reproduction` (reason: "platform identity differs: recorded
('x86_64', 'Linux', '3.13.15', 'scipy-openblas'), current ('aarch64', 'Linux', '3.13.15', 'scipy-openblas')"),
`integrity_ok` true, no near-threshold flag. The failing bundles and their differences, verbatim from the record
(floats compared under "the interim 1e-09 relative / 0 absolute"):

| Bundle | Differences (recorded value against archived value) |
| --- | --- |
| `k05/SYN-001-high-recycle` | `solve-events.json[4].linear.u_diag_min_abs`: 0.04477807556912964 against 0.0731916085271539 |
| `g8/SYN-001-T06-NET02` | `certificate_id` 'cert-1cd3ed009947' against 'cert-1cf23ff02335'; `limitations[0..2].value`: -0.00044157064985483885 / -0.00044157060619909316, 0.0004971807647962123 / 0.0004971807211404666, 1.1384663878288848e-08 / 1.1384653220147811e-08 |
| `g8/SYN-001-T06-NET03` | `certificate_id`; `U-FL2.Q` -3.9700052307840726e-11 against 1.1073945456610047e-11; `solve-events[9].linear.u_diag_min_abs` 0.12785732202141917 against 0.13970043213598085 |
| `g8/SYN-001-T06-NET09` | `certificate_id` only |
| `g8/SYN-001-T06-NET10` | `certificate_id`; `U-FL2.Q` 2.6653784440034204e-11 against 2.236276251310271e-12 |
| `g8/SYN-001-T06-NET11` | `certificate_id` only |
| `g8/SYN-001-T06-STA03-degC` | `certificate_id` only |
| `g8/SYN-001-T06-STA03-kgs` | `certificate_id` only |
| `g8/SYN-001-A02-340-two-phase-guess` | `certificate_id` only |
| `g8/SYN-001-A02-352-vapor-guess-410` | four `solve-events` messages differing in the last digits of a rejected temperature (e.g. 'H_S3_vapor: … temperature 52.11447523132472 K outside [280.0, 440.0] K' against '… 52.114475231324604 K …'); six `solve-events[…].level_constants_sha256` |
| `g8/SYN-001-A02-355-dew-guess-377` | `certificate_id` only |
| `g8/SYN-001-A02-355-dew-guess` | `certificate_id` only |
| `g8/SYN-001-A02-355-liquid-guess` | `certificate_id` only |
| `g8/SYN-001-A02-355` | `certificate_id` only |
| `g8/SYN-001-A02-360-liquid-guess` | `certificate_id`; `limitations[0..2].value` (-5.7412500531484056e-08 / -5.7412500975573266e-08, 3.598530673443179e-08 / 3.598530651238718e-08, 4.8401172958456584e-08 / 4.840117284743428e-08); `U-FLASH.Q` 1.6328084717631697e-16 against -4.530826668708299e-15 |
| `g8/SYN-001-A02-360-vapor-guess` | `certificate_id`; `U-FLASH.Q` 3.75905281057578e-18 against 8.271806125530277e-19; four `solve-events` messages (rejected temperatures, last digits) |
| `g8/SYN-001-A02-360` | `certificate_id`; `U-FLASH.Q` -1.1311235625986564e-16 against 3.899697337511436e-17 |
| `g8/SYN-001-A02-365` | `certificate_id` only |
| `g8/SYN-001-all-liquid-310K` | `certificate_id` only |
| `g8/SYN-001-high-recycle` | `certificate_id`; one `solve-events` message ('… 576.9372132792676 K …' against '… 576.9372132792677 K …') |
| `g8/SYN-001-nominal` | `certificate_id` only |

What the record shows, without judging it: the differences are cross-architecture floating-point differences —
last-digit changes, quantities at round-off scale (heat duties of 1e-11 to 1e-18 compared with a zero absolute
floor), a pivot diagnostic, and identifiers/hashes derived from them (`certificate_id`, `level_constants_sha256`,
messages embedding a float). The same 52 bundles replay `exact_replay` / `MATCH` on the fresh x86-64 runner. The
`k05` `SYN-001-nominal` bundle `MATCH`es on aarch64; the `g8` bundle of the same case does not (`certificate_id`).
Whether these fields belong under `compatible_reproduction` across architectures under `K04-numerical-policy-v1`
is a policy question for the design lane, not a local defect this record can name; not fixed here (brief: a fix
means a new `C`).

The `bundles-write` step again prints `DomainError … temperature … K outside [280.0, 440.0] K` tracebacks during
the solves (24 occurrences in the job log, sha256 `fae2f564…`); the step reported `ok`. Recorded, not interpreted.

No other job, step or check failed.

## Observations (not failures, not judged)

- **O1** `v0_1_gate.py` reports `docs/reviews/T08-verdicts.md does not exist (T08.A03)` and no ledger verdict for
  any of V11–V20, as expected before the verdict phase; it lists V14 (b) as "FAIL, accepted by Frank 2026-09-29
  (ADR 0021 D3)".
- **O2** The CI x86-64 A30 summary differs from the committed `docs/t08-a30/t08-a30-x86_64.json` (made on
  `ref-x86-64`) in `host` (Python 3.13.15 vs 3.13.5; kernel/glibc), `record_sha256`, and `files_digest` of eight
  distributions: `cffi`, `numpy` (compiled) and `httpx`, `idna`, `jsonschema`, `mcp`, `python-dotenv`, `uvicorn`.
  CasADi's digest is equal (`a44.casadi_files_equal_a30` pass on x86-64 against the committed summary). The local
  `ref-x86-64` summary is byte-identical to the committed one.
- **O3** The installed wheel's version is `0.1.0rc1` (`a43.version`, `a44.wheel_version`); the identity step's
  trial version is `0.1.0`.
- **O4** The `check` skip counts differ between platforms and from the local run (11 / 8 / 3 skipped).
- **O5** The step-6 results are identical in their counts to the superseded RC's on both classes (ref-x86-64
  370 + 64, ci-aarch64 367 + 67).
