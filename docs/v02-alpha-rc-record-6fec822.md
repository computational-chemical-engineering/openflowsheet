# V02 alpha — the release-candidate record at `C_α`

*Superseded by R-370 (spec Amendment 3 §19.1): `C_α¹` = `6fec822`'s frozen envelope states a platform the reactor is not measured on; the re-cut candidate `C_α²` = `cc73219`'s record is `docs/v02-alpha-rc-record.md`.*

*`C_α` here is the re-cut candidate `C_α¹` (spec Amendment 2 §18.4, R-349). The record of the superseded first
candidate `C_α⁰` = `e0e198e` is kept at `docs/v02-alpha-rc-record-e0e198e.md`.*

V02 alpha release spec §8.2–§8.3 (WO-10; Amendment 2 §18.5 action 5), in `docs/t08-rc-record.md`'s form. This record **reports**; it judges no
gate. Each Result cell states what the step's record or CI job says, in the closed vocabulary
`scripts/v0_2_gate.py` reads through `v0_1_gate.py`'s grammar (Ruling 3: `PASS` / `success`; `FAIL` / `failure` /
`skipped` / not measured); the verdicts are the design lane's (`verdict`, §6.3). Every record the per-step table
cites is committed under `evidence/M07a/6fec82232e1c47308a5e1d67338058f352992800/rc/` at the same relative path
(a record over 1 MB gzip-compressed beside it), and `rc/records.json` lists all 61 with sha256, size and how each is
kept (59 as is; the two ensemble run files gzip-compressed). `tests/test_m07a_rc_records.py` checks that the hashes
below resolve to them. The scripts that ran the local steps are committed beside them, under
`evidence/M07a/6fec82232e1c47308a5e1d67338058f352992800/tools/` (byte-identical to what ran; the Python ones with a
`.txt` suffix so that the linters of `check.sh` do not read them).

## The candidate and the runs

- **`C` = `6fec82232e1c47308a5e1d67338058f352992800`** (`C_α¹`, "V02 alpha Am2 action 4: cut C_α¹ — R-347, t08_dist's record names the machine class
  (B-AM2-3)"): `e0e198e` + ab80ca5, 04e65be, 00acbe9, f0cfda8 cherry-picked (branch `wp/V02-alpha-rc1`, B-AM2-6).
  Package `openflowsheet` `0.2.0a1`. Its tree record is `release/rc-trees/6fec82232e1c47308a5e1d67338058f352992800.json` (`a39a1dd`, M07a.A44).
- **CI dispatch run 38772065394** (`workflow_dispatch`, `rc_alpha=true`, `rc_distribution=true`, head `C_α`):
  conclusion **success**. **CI push run 38772054427** at `C_α`: conclusion **success**.
- **Local steps** on `ref-x86-64` (AMD Ryzen Threadripper PRO 5965WX, Linux 6.12.111+deb13-amd64, Python 3.13.5),
  run 2026-10-15 from a detached worktree at `C_α` (`.claude/worktrees/rc-6fec822`, clean throughout: `git status
  --porcelain` empty at the start, after the venv and at the end) in a venv of `requirements.lock` with the worktree
  installed editable (`--no-deps`), so every child imported `C_α`'s `src/`; threads pinned
  (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`). Every local step (2, 6–12) ran in one session from one
  script, `tools/run_local.sh` (step 6 beside the others), with environments and logs under
  `~/.cache/of-rca-6fec822/`; its one-line-per-command summary is `tools/run_local.summary.txt` (every command exit
  0). `tools/collect.sh` copied the cited records here.
- **Step 12** ran in the reactor environment built from `C_α`'s `src/openflowsheet/adapters/pymrm/reactor-env.lock`
  (`python -m openflowsheet.adapters.pymrm.env build`, then `verify`: verified) under an external root outside every
  repository; the G12 runs through `tools/g12keep.py.txt`, which keeps the script's scratch directories so that step 10
  can audit their certificates (spec §18.2, R-348; `tools/g12keep.py.txt` sha256
  `f4b136f211de2ea3a50c179362d08cbffae4e8ae0d3b5ea055fdc39c4facfc30`, byte-identical to `C_α⁰`'s). The five kept
  `solution-certificate.json` files are committed under `rc/step12/certificates/<kept bundle path>/` (the bundle's own
  `artifacts/` segment left out, B-AM2-9). The host was shared with other work (other sessions' gates and runs);
  G11v3's timings are recorded under that load.
- **Steps 11 and 12's records** `step11/rc-step11.json` and `step12/rc-step12.json` are written by
  `tools/m07a_rc_external.py.txt` through `t08_rc.finish` from M01's and M02's own records and the commands' exit codes,
  judged by the M01 and M02 manifests' own rules (B-WO10-8).

### Jobs of run 38772065394

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — `check.sh: PASSED`; pytest 8507 passed, 100 skipped | 1 |
| `check (ubuntu-24.04-arm)` | success — `check.sh: PASSED`; pytest 8479 passed, 98 skipped | 1 |
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

All twelve artifacts downloaded (`gh run download 38772065394`); the job logs of the RC jobs saved under
`…/artifacts/rc/ci/job-logs/` (the `check` and `identity` logs cited below).

## Per step

Paths are relative to `evidence/M07a/6fec82232e1c47308a5e1d67338058f352992800/artifacts/rc/` (and, committed, to
`…/rc/`).

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
| 1 | T08.A41 (M07a.A30) | CI x86-64 | success (`check.sh: PASSED`; ruff check, ruff format, mypy, pytest exit 0; 8507 passed, 100 skipped, 2 deselected) | `ci/job-logs/check-ubuntu-latest.log` | `12444b90e10c5d8d5aa9018d2b3f24e8d2c36c72c3855e9cb6aa85a0888fd17b` |
| 1 | T08.A41 (M07a.A30) | CI aarch64 | success (`check.sh: PASSED`; 8479 passed, 98 skipped, 2 deselected) | `ci/job-logs/check-ubuntu-24.04-arm.log` | `bed930ace3dd90880f287b9f7cfe5705e3fdd1a014d494a1e6c8b0f50ea21ed6` |
| 2 | T08.A42 (M07a.A31) | local `ref-x86-64` | PASS (3/3): minus-t07 `24af004a…`, t07 key `887a2e62…` as registered (R-149); unchanged under the trial version `0.1.0`; whole document `174977cc…`, structural `ed6d11f3…`, T02 floats `9a8a5baf…` | `identity/rc-identity.json` | `4fad54488323390ed6196f1b442989a47dcddf3b3ee42cf298f0a5bf03269599` |
| 2 | T08.A42 (M07a.A31) | CI `ci-x86-64` (`rc-steps`) | PASS (3/3); the same four digests | `ci/rc-steps-ubuntu-latest/identity/rc-identity.json` | `4e8e6a79a3ea988ed550de317a48c6e305982a55cd9c4333f1918b8df8c50231` |
| 2 | T08.A42 (M07a.A31) | CI `ci-aarch64` (`rc-steps`) | PASS (3/3); the same four digests | `ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json` | `77f2042d362f6eda8627e178f5d86d73a525280642f3588248160bbee6f8af44` |
| 2 | T08.A42 (cross-arch, G05) | CI `identity` | success ("G05: R0 structural identity equal across 2 platforms") | `ci/job-logs/identity.log` | `ba1e3ce197ab5d28aba88a41007b052aeb1f3e9e959b6cabe645b1c65a42f7cc` |
| 3 | T08.A43 (+A31 checks; M07a.A32) | CI `dist` | PASS (8/8); `a43.version` `0.2.0a1` from `__version__`, `pyproject`, the sdist and the wheel METADATA; wheel bytes equal across the two builds, sdist archive bytes differ with no differing member | `ci/rc-dist/t08-a43-dist.json` | `36a296527cb9306bd5c4a9e55afd2fe5bff42557d503166c4b5a78fdd818a9b8` |
| 4 | T08.A44 (M07a.A33) | CI x86-64 clean env | PASS (10/10); wheel `0.2.0a1`; CasADi = A30 digest `4be1571e…` and P03 per-file (2376 files); smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-latest/install-ubuntu-latest.json` | `1eed06c3cfe2b73a9ca6b4f6bae90587a9e8d87aeccc6881a2110bee16b4b0be` |
| 4 | T08.A44 (M07a.A33) | CI aarch64 clean env | PASS (9/9); wheel `0.2.0a1`; CasADi = A30 digest `7a243303…`; smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json` | `403c0634304ee6b43a8bfb29da46abb3f9f1b5a461df4a153a9268a9cd10dc64` |
| 4 | T08.A19 (b, c) | CI x86-64, `--state installed` | PASS (4/4); lock sha256 empty beneath a stray lock; replay `inspected_archived_results` | `ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json` | `3d9be989669390b933cdd07adaf6c1e5b07be37a9237761ca85ae7661a8a485c` |
| 4 | T08.A19 (a, c) | CI x86-64, `--state checkout` | PASS (4/4); lock `ead4edf1…` | `ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json` | `9db65ec6d32364a515e5cecbd6185a9f16053b57485198f8906db19dd5ab45f3` |
| 4 | T08.A19 (b, c) | CI aarch64, `--state installed` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json` | `22f9126237df736ccbdf5a737d0566d2d1c8eac5ec262ecab896d16738fa6c6b` |
| 4 | T08.A19 (a, c) | CI aarch64, `--state checkout` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json` | `c1b2a935ff5532dee0cbad687b1d741ffb22d9cd4a2ca7aa306ea5a21647654d` |
| 5 | T08.A45 write (M07a.A34) | CI x86-64 `bundle-set` | success (job conclusion; the index carries no check list): `n_b` 52 (k05 5, g8 47), every entry exit 0; 49 CONVERGED / VERIFIED, 3 g8 runs with other registered outcomes (O3) | `ci/rc-bundles/index.json` | `e8af24206ff7fd80595f1df8c5e04413ef322e9344fdc29f853b41d00a2504ca` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI fresh x86-64 | PASS (8/8): same commit; `N_b` 52 = enumeration; every bundle `MATCH`, modes `exact_replay` 52; every bundle records `T08-numerical-policy-v2` (52); controls C1 and C2 `MISMATCH`, C3 `MATCH`, each as expected; sets k05 5, g8 47; near-threshold none | `ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json` | `250ea36983189859565f917340c2f642e7297be7eeffb3991089781d123a59c0` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI aarch64 | PASS (8/8): every bundle `MATCH`, modes `compatible_reproduction` 52; policy `T08-numerical-policy-v2` (52); C1, C2 `MISMATCH` and C3 `MATCH` as expected; sets k05 5, g8 47 | `ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json` | `b7b2872b3f92a63c325a7d5376469e8549eed340f615c10ae742cb4b264d5ff5` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | local `ref-x86-64` | PASS (7/7): N = 440, S = 434, F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3, no F-CRASH or F-OTHER-ROOT; gate S ≥ 418; none verified outside S3 (worst success ratio 0.0968); A33 0; T06 A34 same-class replay 28 of 28 MATCH; registered runs untouched; one-sided 95 % CP lower bound on S 0.973264 (in the report) | `ensemble/rc-ensemble-ref-x86-64.json` | `8390f57ad7ab9fd472928880f7013f3a604891d92867b45b2e316d1687343e53` |
| 6 | (run file, report, replay) | local | — | `ensemble/rc-ref-x86-64.json`, `ensemble/rc-ref-x86-64.report.txt`, `ensemble/rc-ref-x86-64.replay.txt` | `868077361ba5ae87f8a5ed3fbe783163e8009977c7c619c01eddcc34500ce716`, `d33027d3f89529711bec8bdd3100a8ec05da03673492da1766e88f52ec0509d0`, `feac65ffec3360cabebb77fa9bef040b1ed16ed9cd1b36f6e9839db51186bad2` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | CI `ci-aarch64` | PASS (7/7): N = 440, S = 434, F-BUDGET 4, F-FALSE-SUCCESS-CAUGHT 2, no F-CRASH or F-OTHER-ROOT; none verified outside S3 (worst 0.0968); A33 0; replay 28 of 28 MATCH; CP bound in the report | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json` | `ed68c0b9370b7dd8fe0659591bc68574aba2277e43aa8a55ffe99aa70f54b1e8` |
| 6 | (run file, report, replay) | CI `ci-aarch64` | — | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.report.txt`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.replay.txt` | `e0c1008ccff5f343ba4dae3f9cb561b6fda9427ae00051a0c8ba9de2648eb14d`, `b59665ada614c0029702e5924b3e1fce8d2922a634eebb093c0419f4945c9261`, `1a7b927c26d6a1e40628c063f364de9a46225b6420eb8f787cc462e98d9e7348` |
| 7 | T08.A47, A48 (M07a.A36) | local `ref-x86-64` | PASS (12/12): A47 T06.A02–A08, A16, A19, A20; A48 T06.A47, A50; 165 nodes passed, none failed, missing or skipped | `corpus-ref-x86-64.json` | `b711b25b58d0f9af0fcdfcd074473b27eb02ed1678b289891230492084c8bd77` |
| 7 | T08.A47, A48 (M07a.A36) | CI x86-64 | PASS (12/12) | `ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json` | `2c10067cc303baeab40621242e1ea2a573dcc42b3e3b976ca2eb433444fe80b9` |
| 7 | T08.A47, A48 (M07a.A36) | CI aarch64 | PASS (12/12) | `ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json` | `ffa966b5f6602309375d439b2dca4cd31b9f6735a9f406b7b4a4cdaf3bbd5437` |
| 8 | §5.3 chain + G16-b (M07a.A37) | local `ref-x86-64` | PASS (7/7): served `383b4e2c…` = `D_2`; strip c_2 → `6c4375b4…` = `D_1`; strip c_1 → `171dd768…` = `D_0` (R-133); with `v17-c2`'s texts `6d13e13d…` (R-137); the 17 tools and their description files; G16-b 40 of 40 clean; records attributable | `surface/rc-alpha-surface.json` | `db1f7a1388069adb067c22d9ebb2904575aab1b13ffd3de7d22140bd89e78f3e` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI x86-64 | PASS (7/7); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-latest/surface/rc-alpha-surface.json` | `b880c4c27c7dbad766175409e109a957190131a52c64ea352e69036cfc34f7ac` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI aarch64 | PASS (7/7); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-24.04-arm/surface/rc-alpha-surface.json` | `f5ec57ebe9ecc7ff93a14c278e0b887f3c13eebd2e87a54190f02edcabcd2991` |
| 9 | T08.A30 (M07a.A38) | local `ref-x86-64` | PASS ("A30 PASS"): 381 objects in 8 compiled distributions, required closure 150, no undispositioned finding in the closure, METIS not reached (O2) | `a30/a30-inventory-x86_64.json`; summary `a30/t08-a30-x86_64.json` | `733dba5ba4cfd0646bc9264a749dd1798c89705881b0281985368e933808ff38`, `b9ff3ddabc0843a901768eec982369adabc8c922fb4e025aa622183e7c38b337` |
| 9 | T08.A30 (M07a.A38) | CI x86-64 | PASS ("A30 PASS", exit 0): 381 objects, closure 150 | `ci/rc-steps-ubuntu-latest/a30/a30-inventory-x86_64.json`; summary `ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json` | `ba0192107a5aaf3980b84be604bb25ea26e84580268f223a941b92f075aada50`, `dab1651191b07ec1749c88b2369cac4ad5c64b941e2f61528ea0e76d3e796310` |
| 9 | T08.A30 (M07a.A38) | CI aarch64 | PASS ("A30 PASS", exit 0): 308 objects, closure 147 | `ci/rc-steps-ubuntu-24.04-arm/a30/a30-inventory-aarch64.json`; summary `ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json` | `5fbfe91ea1f7ebb0b8f75b72639d62be66950df6dea4a2697a2f0c88e8d6e1ed`, `b1aa32d66a0c9469d976575d8167c721f6734b5109d252a0f3d828a1c49186d6` |
| 10 | T08.A34 over steps 2, 6, 8 and 12 (MR-11; M07a.A39) | local `ref-x86-64` | PASS (2/2): 77 certificates audited (72 of steps 2, 6, 8 and step 12's five coupled-route certificates), 0 violations | `certificates-ref-x86-64.json` | `564588ce3ec0f005a728f31522b8188d55abb75ec747019f0c84197e0d625ca9` |
| 10 | (step 12's five kept certificates, R-348; the bundle's `document_sha256` `faa8e4da…8974` = the G12 record's `certificate_sha256`) | local | — | `step12/certificates/g12-bundles/m02-g12-0/bundle/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/live/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/replay/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-0/bundle/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-1/bundle/solution-certificate.json` | `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `cc36ff13913c5687d221e6a63de9702a62ec17b717d122bc6e1fca67ea3abc31`, `960079a01f580ab91060f04fd99456ec8e8eff7cdfafec84bd0672e4bb272bb3` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json` | `ffd23e6f4ea1183e1bebb82a2e6690de8fb175e7bc7672fcb795559032728c3e` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `d6cabbf8d128e9a23bcc94ecb186edbc3ff9ec85b19106309fdd64fc13df15dd` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json` | `cb1ca32e3a5dd67fb18d9e416a9d96a95676410b7106cd77da248eaf1271b940` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `a9789e1d1bc3f7e0e21f4f1b4621666e3cc28ada55e50515ab929e0e26802230` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 bundle set (step 5) | PASS (2/2): 49 audited (of 52 bundles; the 3 unconverged G8 runs carry none), 0 violations | `ci/rc-bundle-set-certificates/rc-certificates.json` | `177a02d228305d0e16eed541b6c039c297ab15a02fbdc91f830368165f0d95ba` |
| 11 | M07a.A40 | local `ref-x86-64`, pinned environments | PASS (3/3): `external_crosscheck.py --check` exit 0 ("external-crosscheck.json matches"); IDAES re-run exit 0; its numbers equal the committed record's, the one differing member `inputs.reference_values_yaml_sha256` | `step11/rc-step11.json` | `7c40028002bf799bceeffe22a25a4cd395792c4b07a208f662b7f296a3806e43` |
| 11 | (cross-check output, venv, IDAES record, venv) | local | — | `step11/external-crosscheck-check.stdout.txt`, `step11/venv-xcheck.freeze.txt`, `step11/idaes-conformance.json`, `step11/venv-idaes.freeze.txt` | `2f92bf5c59207de7c1f4f59e58c59087f73908eea14c14943edeb4499ae88bdc`, `94dfb7fb94245f4aaa8e23724e52f3642db91eb579f6ba904c65eaf0092d1539`, `7e1d41dd0da62c1685c2ea422e7891bb216c2e01bebb2e7ece7de22d4360adb4`, `dfeec96faebeb6bedab5eb1c069df7344282d0002fe92fb191f2c55c73af82c6` |
| 12 | M07a.A41 (M02 G10 (a)–(i), G11 (a)–(d), G12) | local `ref-x86-64`, reactor environment from `C_α`'s lock, one thread | PASS (6/6): environment built and verified (lock `032a050c…`); G10v3 met — A42 1.56 × 10⁻⁸, A45 3.84 × 10⁻⁸, A46 5.06 × 10⁻⁵, A47 (a) bitwise, (b) 1.43 × 10⁻⁸; G11v3 met, box V5, the two runs of 121 points equal; G12 CONVERGED / VERIFIED in 4 accepted iterates, ρ 0.292, floor ratios 65.3 (ξ) and 13.3 (T), `reproduce` MATCH, live rerun bitwise; edges converged and verified; M02 tests with the reactor 562 passed | `step12/rc-step12.json` | `4868a2d6ab9791763f2efa7e7f0631741d9d4c817547d48cd96deefb69495119` |
| 12 | (G10, G11, G11 runs, G12, G12 edges, M02 tests, environment, host) | local | — | `step12/g10-adapter-halves-v3.json`, `step12/g11-coverage-v3.json`, `step12/g11-coverage-v3.runs.json`, `step12/g12-real-loop-v3.json`, `step12/g12-real-loop-v3-edges.json`, `step12/m02-tests.junit.xml`, `step12/env-manifest.json`, `step12/host.txt` | `477fdc0b779b468262938fe56df999e2666c76ae2b7308ac0bb87187ad42f9a1`, `3c50d1636d9fa85b5818310e360a3848a72588f371ee07cbb6c2d8a2008c9f92`, `ba60c06613c676992a4931cb456fa83b1fd4601b3b19f87ca3bc0de368da1efd`, `2d40da37b563faf676ff28c84c0fd65e13f5bd35607afe6be1d155854b05d3f1`, `52707917fbebcb917723da563d122eb57a6590b362a0da360722f514b40ac480`, `29cfb6d607361f6109d62c2e988fc86ed86508d30ea4e8adae08e6108f810eaa`, `ae29698d590ba3fc258a6730af7e74454ee4bd1b7a754d48b85cf73a07fdc280`, `48d65e6b31e68bc8927adf40527d6fc367b4f046ec205c4d3783ede7d7a1ad4f` |

**M07a.A43 (provenance).** Every `t08-rc-v1` record above (local and CI, the bundle index, both replay records and
the step-11 and step-12 records included) carries `commit` = `6fec8223…`, `tree_clean = true` and
`environment_lock_sha256 = ead4edf1…b9c4`; `t08-a43-dist.json` carries the same at top level. Every one of these 29
records carries a `machine_class` (R-347: now also the 13 records of `install-check`, `lock-check`, `certificates`
and `t08_dist.py`, which `C_α⁰`'s lacked), each a registered class (`ref-x86-64`, `ci-x86-64`, `ci-aarch64`) that
agrees with the record's `architecture` (`machine`) and `github_actions` where it carries them. The A30 records carry
`lock_sha256` and the host, but no `commit` or `tree_clean` (format `t08-a30-inventory-v1`); M01's and M02's records
(steps 11, 12) carry neither, and are cited through the step's `t08-rc-v1` record. Stated, not judged.

## Step 13

`scripts/v0_2_gate.py --rc C_α` (M07a.A12) needs `docs/reviews/V02-alpha-verdicts.md`, which does not exist yet
(the `verdict` agent at `C_α`, §6.3). It has not been run; it is pending, not failed.

## Failures

None. Every record of steps 1–12 reports `PASS` or `success`. `C_α⁰`'s F1 (step 10's local audit, 5
violations in step 12's coupled-route certificates) does not recur: R-345 removed the four entries that are not
[A09] text, and the same audit at `C_α¹` finds 0 violations in 77 certificates.

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
- **O6** Against `C_α⁰`'s records, every check value of steps 2–12 is equal, apart from paths, timestamps,
  hashes and these: the dist record's member sizes and the `coupled_run.py`/`checks.py` members (R-345's two
  files), the install smoke run's printed bundle path, and step 12's experiment and call keys (they hash the code
  identity). Step 12's numbers (G10v3, G11v3, G12 ρ, floor ratios, iterate counts) are equal. The G12 bundle
  certificate's `document_sha256` moves from `d61a86fb…19faa4` to `faa8e4da…fdf8974` and the edges' to
  `cc36ff13…` and `960079a0…`: R-345 changes those certificates' qualification entries, as Am2.5 (iii) measured.
- **O7** The local A30 summary's eight `files_digest` values differ from `C_α⁰`'s local summary too (as O2 states
  against the committed file); object counts and closures are equal (381 / 150).
