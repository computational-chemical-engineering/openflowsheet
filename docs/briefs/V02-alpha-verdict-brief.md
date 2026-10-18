# Verdict brief: `0.2.0a1` at C_α¹ — V11–V20, W21, W22 (spec §6.3)

**Task.** One `verdict` agent judges V11–V20, W21 and W22 together at the release candidate
**C_α¹ = `6fec82232e1c47308a5e1d67338058f352992800`** (branch `wp/V02-alpha-rc1`; C_α⁰ = `e0e198e` superseded by
Amendment 2, R-349 — its record is `docs/v02-alpha-rc-record-e0e198e.md`). It does not judge W23–W27. Worktree
`/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/alpha-gate`, branch `wp/V02-alpha-gate`.

**Output.** `docs/reviews/V02-alpha-verdicts.md` in T08 Amendment R3 §R3.3's form (see `docs/reviews/T08-verdicts.md`
for a worked example), with §6.3's three differences (pasted below): header line with C_α¹ (40 hex) and today's date;
exactly one `Verdict` table `Gate | Verdict | Failing clauses | Travelling limitations | Basis`, twelve rows V11…V20,
W21, W22; clauses `Gnn (x)`. One section per gate judging every clause met / not met / blocked, its evidence at C_α¹,
and what it does not establish (W21/W22: at least §6.1–§6.2's lists). A verdict differing from v0.1's at `67c66d9`
(`docs/reviews/T08-verdicts.md`) says why. Never set `reviewed`; never move a tolerance, band or classification rule.
Amendment 2 (spec §18) applies: F1 was a certificate defect fixed at C_α¹; V18's failure at C_α⁰ was clause (c).

**State of the manifest.** `evidence/M07a/6fec822…/manifest.json` is `implemented`: 37 pass, 0 fail, 6 unsupported —
A52 (two changelog tests pending until the gate table is pasted from `v0_2_gate.py --markdown`, after the verdicts,
by design: build log B-WO8) and A60–A64 (await the verdicts and WO-11). Judge whether that satisfies §6.3's precondition
in substance; if you find it does not, say so and stop.

**Build-lane choices to note (rule only if they affect a verdict):** B-AM2-6 C_α¹ on its own remote branch; B-AM2-9
certificate paths omit the ignored `artifacts/` segment; B-AM2-10 bundle/live/replay certificates byte-identical, RC-record
hash tests compare multisets (commit 6146aa3). Detail: `docs/design/V02-alpha-build-decisions.md`.

**Rules.** Read narrowly (grep -n / sed -n); stay under ~150k context. Commit `docs/reviews/V02-alpha-verdicts.md` with
named paths, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`; push. Report ≤ 300 words: the twelve verdicts
one line each, failing clauses, what is not established.

---
## A. RC record at C_α¹ (`docs/v02-alpha-rc-record.md`)
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


## B. M01 and M02 manifests (checks and limitations)

### `evidence/M01/3c803920f63f3d2e2fe7300090198f2e5670fbf7/manifest.json` — status `tested`, commit `3c803920f63f3d2e2fe7300090198f2e5670fbf7`

- M01.A01 [pass] M01 spec §9, M01.A01: `components.yaml` holds five records, ids in the order H2, N2, NH3, Ar, CH4; each validates against `component-record.schema.json` and `check_quantity`; `synthetic: false`; `elemental_verification:  — value: {"tests": {"selector": "tests/test_m01_*.py::test_a01_*", "passed": 7, "failed": 0, "skipped": 0}}
- M01.A02 [pass] M01 spec §9, M01.A02: `external-crosscheck.json` has `retrieval_all_equal: true` and every `retrieval.*.equal` true (form test in the gate; the script's `--check` is evidence in the manifest). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a02_*", "passed": 1, "failed": 0, "skipped": 0}, "crosscheck": {"exit_code": 0, "output": "external-crosscheck.json matches", "record_sha256": "72a273
- M01.A03 [pass] M01 spec §9, M01.A03: The provider's parameters equal the records' values bitwise (as parsed floats); `data_sha256` is the SHA-256 of `components.yaml`'s bytes; `implementation_sha256` the SHA-256 of the provider module' — value: {"tests": {"selector": "tests/test_m01_*.py::test_a03_*", "passed": 7, "failed": 0, "skipped": 0}}
- M01.A04 [pass] M01 spec §9, M01.A04: `describe()`: `provider_id` `pr-c1-v1`, `reference_convention` `PR-C1-ref-v1`, `state_definition` `nTP-v1`, components (H2, N2, NH3, Ar, CH4), phases (LIQUID, VAPOR), properties ⊇ {h, Z, v, lnphi_H2 — value: {"tests": {"selector": "tests/test_m01_*.py::test_a04_*", "passed": 1, "failed": 0, "skipped": 0}}
- M01.A05 [pass] M01 spec §9, M01.A05: Per component: κ, a_c, b rel 10⁻¹⁴; NH₃'s T_c,EOS rel 10⁻¹³ (`closed_form.components`, `nh3_eos_critical`). Simple products; the floor is a few ulp. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a05_*", "passed": 6, "failed": 0, "skipped": 0}, "measured": {"kappa_a_c_b": {"value": 2.220446049250313e-16, "tolerance": 1e-14, "sense": "<=", "with
- M01.A06 [pass] M01 spec §9, M01.A06: c_p^ig(298.15 K), c_p^ig(700 K), h^ig(268.15 K), h^ig(700 K) per component rel 10⁻¹²; h^ig(298.15 K) = Δ_fH° within 10⁻⁹ J/mol. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a06_*", "passed": 5, "failed": 0, "skipped": 0}, "measured": {"cp_h_ig": {"value": 9.115589140092656e-16, "tolerance": 1e-12, "sense": "<=", "within":
- M01.A07 [pass] M01 spec §9, M01.A07: Phase states V1, V2, V3, V4, V5, L1, L2: Z, h, every reported ln φ rel 10⁻¹²; v rel 10⁻¹². — value: {"tests": {"selector": "tests/test_m01_*.py::test_a07_*", "passed": 7, "failed": 0, "skipped": 0}, "measured": {"Z_h_v_lnphi": {"value": 6.059019004649999e-16, "tolerance": 1e-12, "sense": "<=", "with
- M01.A08 [pass] M01 spec §9, M01.A08: Roots and labels: L2 and V3 (one state, three roots) have distinct Z equal to the reference's smallest and largest; L1 is a single liquid-like root (v ＜ v_c,EOS); V4 is the single supercritical root — value: {"tests": {"selector": "tests/test_m01_*.py::test_a08_*", "passed": 9, "failed": 0, "skipped": 0}}
- M01.A09 [pass] M01 spec §9, M01.A09: V1's five ln φ are nonzero and differ pairwise by at least 10⁻⁶, and V2's likewise; every |h^dep| at V1–V5, L1, L2 exceeds 1 J/mol (a dropped departure term fails A07). *Why 10⁻⁶ (Amendment 1):* it  — value: {"tests": {"selector": "tests/test_m01_*.py::test_a09_*", "passed": 9, "failed": 0, "skipped": 0}, "measured": {"min_pairwise_lnphi_gap": {"value": 0.0004347423147853281, "tolerance": 1e-06, "sense": 
- M01.A10 [pass] M01 spec §9, M01.A10: At V1, V2 (VAPOR) and L1 (LIQUID), for every property X ∈ {Z, v, h, ln φ_*} and input x ∈ {T, P, n_j}: |s·(∂X/∂x)_impl − s·(∂X/∂x)_ref| ≤ 10⁻⁹·max(|X|, 1, |s·(∂X/∂x)_ref|), s = T, P or n_tot,in resp — value: {"tests": {"selector": "tests/test_m01_*.py::test_a10_*", "passed": 3, "failed": 0, "skipped": 0}, "measured": {"scaled_derivative_error": {"value": 5.271357053122545e-16, "tolerance": 1e-09, "sense":
- M01.A11 [pass] M01 spec §9, M01.A11: L1's n-derivatives are exactly 0.0 (pure-liquid properties are composition-free); V1's and V2's are all nonzero (DER-NZ: each ＞ 10⁻¹² in magnitude), so A10 is not met by zeros. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a11_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"L1_n_derivatives_exactly_zero": true, "min_vapour_n_derivative": {"value": 2.3891818462
- M01.A12 [pass] M01 spec §9, M01.A12: Identities of the implementation itself, independent of the reference, at V1 and V2 (as amended by Amendment 1). Homogeneity of X ∈ {Z, v, h}: |Σ_j n_j ∂X/∂n_j| ≤ 10⁻¹²·Σ_j |n_j ∂X/∂n_j|. The ln φ b — value: {"tests": {"selector": "tests/test_m01_*.py::test_a12_*", "passed": 2, "failed": 0, "skipped": 0}, "measured": {"homogeneity_Z_v_h": {"value": 6.109990213179649e-16, "tolerance": 1e-12, "sense": "<=",
- M01.A13 [pass] M01 spec §9, M01.A13: A derivative request for an undeclared input returns `unsupported` with `undeclared_derivative_input`. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a13_*", "passed": 3, "failed": 0, "skipped": 0}}
- M01.A14 [pass] M01 spec §9, M01.A14: U1 → `unsupported`, message matches `^light_gas_in_liquid:`; U2 → `^no_liquid_root:`; U3 → `^no_vapour_root:`; U4 → `^vapour_root_metastable:`; U5, U6 → status `out_of_domain`, `^out_of_domain:`. A  — value: {"tests": {"selector": "tests/test_m01_*.py::test_a14_*", "passed": 9, "failed": 0, "skipped": 0}}
- M01.A15 [pass] M01 spec §9, M01.A15: F1, F5, F11, F13: `ok`, TWO_PHASE; y* (= `k_values["NH3"]`, the only key) rel 10⁻¹¹; `vapor_fraction` |Δ| ≤ 10⁻¹²; vapour NH₃ and liquid NH₃ flows rel 10⁻¹¹; the liquid's light-gas flows are +0.0 ex — value: {"tests": {"selector": "tests/test_m01_*.py::test_a15_*", "passed": 4, "failed": 0, "skipped": 0}, "measured": {"y_star_rel": {"value": 3.552713678800501e-15, "tolerance": 1e-11, "sense": "<=", "withi
- M01.A16 [pass] M01 spec §9, M01.A16: At the implementation's own TWO_PHASE results (A15 states), its own `evaluate_phase` gives |ln y* + ln φ_NH₃^V − ln φ_NH₃^L| ≤ 10⁻¹² (the equilibrium row closes on the provider's own evaluations). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a16_*", "passed": 4, "failed": 0, "skipped": 0}, "measured": {"equilibrium_residual": {"value": 8.881784197001252e-16, "tolerance": 1e-12, "sense": "<
- M01.A17 [pass] M01 spec §9, M01.A17: Single-phase routes: F2 VAPOR, F3 VAPOR, F6 VAPOR, F8 VAPOR, F9 VAPOR, F10 VAPOR (vapor_fraction 1.0, liquid dormant), F7 LIQUID (vapor_fraction 0.0, vapour dormant); the present phase equals the fe — value: {"tests": {"selector": "tests/test_m01_*.py::test_a17_*", "passed": 7, "failed": 0, "skipped": 0}}
- M01.A18 [pass] M01 spec §9, M01.A18: F4 is VAPOR, or TWO_PHASE with liquid NH₃ ≤ 10⁻¹² × the feed's NH₃. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a18_*", "passed": 1, "failed": 0, "skipped": 0}}
- M01.A19 [pass] M01 spec §9, M01.A19: F12 is VAPOR (the rules' answer at the near-critical state; registered behaviour, not a physical claim). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a19_*", "passed": 1, "failed": 0, "skipped": 0}}
- M01.A20 [pass] M01 spec §9, M01.A20: F14: `ok`, `ZERO_FLOW`, `vapor_fraction` None, both outlets all +0.0, `k_values` empty. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a20_*", "passed": 1, "failed": 0, "skipped": 0}}
- M01.A21 [pass] M01 spec §9, M01.A21: Feed independence: F1 with its NH₃ doubled gives y* bitwise equal to F1's. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a21_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"y_star_bitwise_equal": true}}
- M01.A22 [pass] M01 spec §9, M01.A22: Material closure: for every TWO_PHASE result, vapour + liquid = feed componentwise within 1 ulp of the feed's component flow. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a22_*", "passed": 4, "failed": 0, "skipped": 0}, "measured": {"closure_in_ulp_of_feed": {"value": 1.0, "tolerance": 1.0, "sense": "<=", "within": true
- M01.A23 [pass] M01 spec §9, M01.A23: Σ ν_i h_i^ig at 298.15 K = −91 116 J/mol within 10⁻⁹ J/mol; at 673.15 K rel 10⁻¹² (−104 003.12297042357). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a23_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"dh_r_298_15_abs_J_mol": {"value": 0.0, "tolerance": 1e-09, "sense": "<=", "within": tru
- M01.A24 [pass] M01 spec §9, M01.A24: The registry of reaction-consistent conventions equals {`SYN-001-ref-v1`, `PR-C1-ref-v1`}; SYN-001's constant is unchanged and a subset; a C1 reacting unit over `pr-c1-v1` constructs; over an unregi — value: {"tests": {"selector": "tests/test_m01_*.py::test_a24_*", "passed": 2, "failed": 0, "skipped": 0}}
- M01.A25 [pass] M01 spec §9, M01.A25: Stand-in at V1's inlet: ξ = 0.05875 rel 10⁻¹⁴; n_out as §8.13 rel 10⁻¹⁴; T_out = T_in, P_out = P_in bitwise; Q = −6205.800878966381 W rel 10⁻¹⁰ (Ḣ_in, Ḣ_out rel 10⁻¹¹; the difference amplifies by 1. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a25_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"xi_rel": {"value": 2.220446049250313e-16, "tolerance": 1e-14, "sense": "<=", "within": 
- M01.A26 [pass] M01 spec §9, M01.A26: Projection with the registered d (as amended by Amendment 1): - ξ and the projected outlet: rel 10⁻¹² (measured 2.2 × 10⁻¹⁶); - the inerts' projected flows equal their inlet flows bitwise, and the C — value: {"tests": {"selector": "tests/test_m01_*.py::test_a26_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"xi_and_projected_outlet_rel": {"value": 2.220446049250313e-16, "tolerance": 1e-12, "sen
- M01.A27 [pass] M01 spec §9, M01.A27: Pressure convention: reported ΔP 5000 Pa at P_in 10⁷ → `ok`; 20 000 Pa → `unsupported`, `pressure_drop_exceeds_convention`. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a27_*", "passed": 2, "failed": 0, "skipped": 0}}
- M01.A28 [pass] M01 spec §9, M01.A28: Zero-flow inlet → `ZERO_FLOW` result per §8.12; Q is +0.0 exactly. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a28_*", "passed": 1, "failed": 0, "skipped": 0}}
- M01.A29 [pass] M01 spec §9, M01.A29: Per-tube scaling: the stand-in's result for (k n_in, k N_tubes), k ∈ {2, 7}, equals k × the result for (n_in, N_tubes) rel 10⁻¹⁵ (n_out, ξ, Q). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a29_*", "passed": 2, "failed": 0, "skipped": 0}, "measured": {"scaled_result_rel": {"value": 0.0, "tolerance": 1e-15, "sense": "<=", "within": true, "
- M01.A30 [pass] M01 spec §9, M01.A30: Each refusal of §8.12 testable by the stand-in returns its status and code (inlet liquid: F7's state as inlet; component mismatch: a permuted order; trace: y_NH₃ = 10⁻¹⁰; hard domain: T_in = 550 K;  — value: {"tests": {"selector": "tests/test_m01_*.py::test_a30_*", "passed": 6, "failed": 0, "skipped": 0}}
- M01.A31 [pass] M01 spec §9, M01.A31: Data-domain flag: T_in = 623.15 K (inside the hard domain) → `ok`, `domain_status: extrapolated` listing `T_in`; T_in = 673.15 K → `within_data_domain`. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a31_*", "passed": 2, "failed": 0, "skipped": 0}}
- M01.A32 [pass] M01 spec §9, M01.A32: The envelope of an `ok` result has every field of §8.12 (stand-in: the reactor-specific diagnostics are present and `null`). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a32_*", "passed": 1, "failed": 0, "skipped": 0}}
- M01.A33 [pass] M01 spec §9, M01.A33: Existing identities unchanged: the gate passes with no edit to any registered value under `benchmarks/syn001/`, `benchmarks/t05/`, `benchmarks/t05b/`, `benchmarks/t06/`, `benchmarks/t08/`, the K05 i — value: {"frozen_paths_diff": {"base": "c1da14c14625e596978c691c8ba72f0a132bbc51", "commit": "3c803920f63f3d2e2fe7300090198f2e5670fbf7", "paths": ["benchmarks/syn001", "benchmarks/t05", "benchmarks/t05b", "be
- M01.A34 [pass] M01 spec §9, M01.A34: `m01_reference.py --check` exits 0 (88 claims hold, files byte-identical; 82 before Amendment 1 added PR-07, PH-GAP, BD-04, BD-05, BD-06, DX-01). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a34_*", "passed": 1, "failed": 0, "skipped": 0}, "generator": {"exit_code": 0, "claims": 88, "last_line": "88 claims hold; reference_values.yaml match
- M01.A35 [pass] M01 spec §9, M01.A35: No runtime import of `chemicals`, `thermo`, `CoolProp`, `cantera` or `mpmath` from `openflowsheet`; `pyproject.toml`'s runtime dependencies unchanged. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a35_*", "passed": 2, "failed": 0, "skipped": 0}}
- M01.A36 [pass] M01 spec §9, M01.A36: Exact caching: two `evaluate_phase` requests differing by one ulp in T produce different cache keys and both evaluate (the existing cache rule; the provider supplies non-empty identity hashes). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a36_*", "passed": 1, "failed": 0, "skipped": 0}}
- M01.A37 [pass] M01 spec §9, M01.A37: IDAES conformance (build lane, IDAES 2.13 env, M01's records, k_ij = 0, vapour-only convention): at V1, V2 and L1, ln φ |Δ| ≤ 10⁻⁹ and Z rel 10⁻⁹; at F1 and F11, β |Δ| ≤ 10⁻⁸ and y* rel 10⁻⁸; record — value: {"tests": {"selector": "tests/test_m01_*.py::test_a37_*", "passed": 5, "failed": 0, "skipped": 0}, "measured": {"Z_rel": {"value": 4.2465542963513587e-16, "tolerance": 1e-09, "sense": "<=", "within": 
- M01.A38 [pass] M01 spec §9, M01.A38: W22, pure NH₃ saturation: |P_sat,PR/P_sat,ref − 1| ≤ 0.02 at 240, 260, 268.15, 280, 300, 320 K against CoolProp 8.0.0's ammonia (Gao et al. 2020). Measured maximum 0.0127 (240 K); 0.0072 at 268.15 K — value: {"measured": {"max_abs_P_sat_rel_dev": {"value": 0.012675, "tolerance": 0.02, "sense": "<=", "within": true, "margin": 1.58}, "by_temperature_K": {"240": 0.012675, "260": 0.008599, "268.15": 0.007171,
- M01.A39 [pass] M01 spec §9, M01.A39: W22, liquid NH₃ fugacity at the separator states: |ln φ^L_PR − ln φ^L_ref| ≤ 0.05 at (268.15 K, 10⁷ Pa) and (250 K, 2.5 × 10⁷ Pa). Measured 0.0254 and 0.0401. — value: {"measured": {"max_abs_dlnphi": {"value": 0.040096, "tolerance": 0.05, "sense": "<=", "within": true, "margin": 1.25}, "by_state": {"NH3-LIQUID-268.15-1e7": 0.025394, "NH3-LIQUID-250-2.5e7": 0.040096}
- M01.A40 [pass] M01 spec §9, M01.A40: W22, vapour fugacity of each pure light gas at (268.15 K, 10⁷ Pa) and (673.15 K, 10⁷ Pa), and of NH₃ vapour at (673.15 K, 10⁷ Pa): |Δ ln φ| ≤ 0.05. Measured maximum 0.0424 (CH₄, 268.15 K). — value: {"measured": {"max_abs_dlnphi": {"value": 0.042371, "tolerance": 0.05, "sense": "<=", "within": true, "margin": 1.18}, "by_state": {"H2-VAPOR-268.15-1e7": 0.032804, "H2-VAPOR-673.15-1e7": 0.006775, "N
- M01.A41 [pass] M01 spec §9, M01.A41: The start strategy is accepted (§8.7) at the design grid num_z = 800 for T_in ∈ {653.15, 673.15, 693.15} K, and the group's cold start at the true inlet is rejected for `dt_init` ∈ {10⁻⁶, 10⁻³, 10⁻¹ — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_a41_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"accepted_at_num_z_800": {"673.15": true, "653.15": true, "693.15": true}, "cold_sta
- M01.A42 [pass] M01 spec §9, M01.A42: Path independence at the design grid: S2 with `dt_init` 10⁻⁶ and 10⁻¹ give outlets (n_out, T_out) within 10⁻⁶ relative (§10.3; measured 1.6 × 10⁻⁸). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_a42_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"max_rel_diff": {"value": 1.559285305616933e-08, "tolerance": 1e-06, "sense": "<=", 
- M01.A43 [pass] M01 spec §9, M01.A43: Repeatability: two repeats at the design grid are bitwise identical (one machine, one environment). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_a43_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"runs": 2, "two_runs": true, "bitwise_identical": true}}
- M01.A44 [pass] M01 spec §9, M01.A44: The backflow override is inert: replacing it by `[0, 0, 0, 1, 0]` leaves the outlet bitwise unchanged, and u_ret ＞ 0 on every face. — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_a44_*", "passed": 10, "failed": 0, "skipped": 0}, "measured": {"bitwise_identical": true, "min_u_ret_min": 0.0013803491565340664, "u_ret_positive_
- M01.A45 [pass] M01 spec §9, M01.A45: Raw element defects |Δ(H, N, C, Ar)|/inlet ≤ 10⁻⁷ at every accepted grid (measured at 800: 2.66 × 10⁻⁸ at the nominal T_in 673.15 K, 1.72 × 10⁻⁸ at 653.15 K and 2.98 × 10⁻⁸ at 693.15 K; ≤ 9.2 × 10⁻¹ — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_a45_*", "passed": 7, "failed": 0, "skipped": 0}, "measured": {"max_element_defect_rel_accepted": {"value": 2.9798974020496724e-08, "tolerance": 1e
- M01.A46 [pass] M01 spec §9, M01.A46: |ΔP|/P_in ≤ 10⁻³ at every registered point (measured 4.90–5.06 × 10⁻⁵). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_a46_*", "passed": 9, "failed": 0, "skipped": 0}, "measured": {"max_abs_dP_over_P": {"value": 5.059274805523455e-05, "tolerance": 0.001, "sense": "
- M01.A47 [not_applicable] M01 spec §9, M01.A47: M02's adapter reproduces the probe's design-grid nominal outlet (as amended by Amendment 1). The outlet means the evaluation's raw `TubeOutlet`, at N_tubes = 1, before projection: five flows and T_o — value: {"measured": {"to_reproduce": {"outlet_n_mol_s": [0.004206722750696396, 0.0014141525193808178, 0.0007451757058514184, 0.00010720442233839437, 0.00014293922978452547], "T_out_K": 757.3353119014521}, "r
- M01.A48 [pass] M01 spec §9, M01.A48: The refinement record holds the grid sequence of §10.1 with its order estimate and the design grid's discretization estimate; every reactor result reports that estimate (§8.12). — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_a48_*", "passed": 1, "failed": 0, "skipped": 0}, "measured": {"grid_num_z": [100, 200, 400, 800, 1600, 3200], "grid_registered": true, "accepted_e
- M01.A49 [pass] M01 spec §9, M01.A49: The stand-in is labelled as §8.13 states. Its manifest validates against `model-manifest.schema.json`. Its `title` contains `synthetic` (case-insensitive), its `description` begins `SYNTHETIC`, and  — value: {"tests": {"selector": "tests/test_m01_*.py::test_a49_*", "passed": 5, "failed": 0, "skipped": 0}}
- M01.A50 [pass] M01 spec §9, M01.A50: Provider request checks (§5.3, §5.4 step 0): — value: {"tests": {"selector": "tests/test_m01_*.py::test_a50_*", "passed": 10, "failed": 0, "skipped": 0}}
- M01.A51 [pass] M01 spec §9, M01.A51: Boundary paths beyond A30 (§8.12): - (i) an evaluation that returns `NotAccepted("S3")` → `not_converged`, code `reactor_not_accepted(S3)`; every code of this kind matches `^reactor_not_accepted\([A — value: {"tests": {"selector": "tests/test_m01_*.py::test_a51_*", "passed": 27, "failed": 0, "skipped": 0}}
- M01.A52 [pass] M01 spec §9, M01.A52: The probe record, as committed, holds §8.15's record halves: - `version` 2; `reactor_commit` the pin of §8.1; `environment.packages.pymrm` `2.5.0`; - A41: `pinned` and both `neighbouring_inlet_tempe — value: {"tests": {"selector": "tests/test_m01_*.py::test_a52_*", "passed": 33, "failed": 0, "skipped": 0}, "measured": {"mapping_F_ulp": {"value": 1.0, "tolerance": 2.0, "sense": "<=", "within": true, "margi
- M01.gate [pass] M01 spec §13: `./scripts/check.sh` green at C, with M01.A01, A03-A36 and A49-A52 among its tests. — value: "check.sh PASSED; pytest: 7135 passed, 31 skipped"

Limitations:
- W21 and W22 are v0.2 requirement ids the manifest schema's `requirements` pattern ([DA]nn) cannot carry; this evidence bears on both, and their verdicts are the `verdict` lane's, not this manifest's.
- The reactor is not run here: A41-A46 and A48 are checked as the probe record's halves (spec §8.15, M01.A52) on the record last written at 74b43096e7ff43220189649597c0a4070136d847, whose bytes A34 pins. reactor_probe.py was not re-run for this manifest. The adapter halves of A41-A48, including all of A47, are M02's (R-200).
- The stand-in c1.reactor_standin is synthetic: A25-A32 and A49-A51 certify the boundary code, never the reactor (spec §8.13, R-199).
- W22 is validated for pure-component behaviour only (A38-A40, spec §11); there is no mixture VLE validation, and k_ij = 0.
- The probe record's numbers come from one machine and one environment. Two record values sit within 10x of their bounds by the spec's own registration: A45's worst accepted element defect, 2.98e-8 at the design grid's 693.15 K neighbour (2.66e-8 at the nominal inlet), against 1e-7, with the refusal threshold 1e-6 33.6x above it; and A52's mapping of the recorded n (1 ulp against 2). Both are consta
- Human numerical and process-modeling review remain `pending`; `reviewed` is never self-set.

### `evidence/M02/ba90619c62329165a21731fdff01ebc9c7203287/manifest.json` — status `tested`, commit `ba90619c62329165a21731fdff01ebc9c7203287`

- M02.G1 [pass] M02 design note §10, G1 (Schemas), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_schemas.py::*"], "passed": 23, "failed": 0, "skipped": 0}, "mcp_tool_list": {"served_sha256": "383b4e2c004810663a3e3f80c591730bc95894e35736619eacac0f51e51b5403
- M02.G2 [pass] M02 design note §10, G2 (Inertness), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_join.py::*", "tests/test_m02_wo7_binding.py::*", "tests/test_m02_wo8_registries.py::*", "tests/test_m02_wo8_verifier.py::test_g2i_*"], "passed": 40, "failed": 
- M02.G3 [pass] M02 design note §10, G3 (Kill chain), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_kill_chain.py::*"], "passed": 13, "failed": 0, "skipped": 0}}
- M02.G4 [pass] M02 design note §10, G4 (Records and cache), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_experiments.py::*", "tests/test_m02_experiment_job.py::test_g4i_*"], "passed": 28, "failed": 0, "skipped": 0}}
- M02.G5 [pass] M02 design note §10, G5 (Experiment job), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_experiment_job.py::*", "tests/test_m02_experiment_body_isolation.py::*"], "passed": 21, "failed": 0, "skipped": 0}}
- M02.G6 [pass] M02 design note §10, G6 (Frozen identity), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_variants.py::*", "tests/test_m02_wo7_binding.py::test_g6a_*", "tests/test_m02_wo10_coupled.py::test_g6c_*"], "passed": 37, "failed": 0, "skipped": 0}}
- M02.G7 [pass] M02 design note §10, G7 (PR units), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_wo8_g7.py::*", "tests/test_m02_wo8_blocks.py::*", "tests/test_m02_wo8_region.py::*", "tests/test_m02_wo8_units.py::*", "tests/test_m02_wo8_verifier.py::*", "te
- M02.G8 [pass] M02 design note §10, G8 (Coupled route with the stand-in), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_wo9_reactor.py::*", "tests/test_m02_wo10_driver.py::*", "tests/test_m02_wo10_coupled.py::*", "tests/test_m02_wo14.py::*"], "passed": 68, "failed": 0, "skipped"
- M02.G9 [pass] M02 design note §10, G9 (Promotion), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_wo11_promotion.py::*"], "passed": 17, "failed": 0, "skipped": 0}}
- M02.G10 [pass] M02 design note §10, G10 (Adapter halves of M01.A41–A48), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_g10_record.py::*", "tests/test_m02_pymrm_child.py::*", "tests/test_m02_pymrm_env.py::*"], "passed": 99, "failed": 0, "skipped": 0}, "measured": {"record": {"pa
- M02.G11 [pass] M02 design note §10, G11 (Coverage and timing), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_wo12b_v3.py::*", "tests/test_m02_experiments.py::test_g11v3_*"], "passed": 43, "failed": 0, "skipped": 0}, "measured": {"record": {"path": "benchmarks/m02/g11-
- M02.G12 [pass] M02 design note §10, G12 (Real loop), as amended by §14.2–§14.7. — value: {"tests": {"selectors": ["tests/test_m02_wo14.py::test_rp1_*"], "passed": 1, "failed": 0, "skipped": 0}, "measured": {"record": {"path": "benchmarks/m02/g12-real-loop-v3.json", "sha256": "47dc9f089b71

Limitations:
- W21 ('PyMRM boundary/accuracy/execution and provenance') and W22 are v0.2 requirement ids the manifest schema's `requirements` pattern ([DA]nn) cannot carry. This evidence bears on W21 (design note §10.4 lists which gates bear on which part); its verdict is the `verdict` lane's, not this manifest's.
- The real-reactor evidence (G10–G12) is opt-in: it needs the separately built, pinned reactor environment (design note §2.4), runs on Linux only (macOS best effort, Windows refused before spawn; ADR 0033 D2) and is R3. Its records were measured on one machine (the records name the CPU model and the environment fingerprint) and are read here, not re-run (only the two `pymrm` environment tests, A47 (
- `external-subprocess-v1` is not a sandbox: no filesystem confinement, network isolation, memory or CPU quota, or syscall filtering; trust rests on provenance (ADR 0033 D2; design note §12 N1, accepted for v0.2 local use as the default pending Frank).
- v3's inert floor y_inert >= 0.035 sits just above a measured S1 failure (0.03 at 653.15 K, 11 MPa, H2/N2 2.5; build log D105). G11 samples only the corners and the centre of the hard domain; the real loop's smallest request is 1.116 x the floor (D115). An in-domain S1 failure ends in a refusal and then an honest COUPLING_NOT_CONVERGED, never a false success (M02 review F10).
- G8 (c)'s sequential-substitution oracle is independent of the EO machinery in flowsheet structure, not in thermodynamics: it shares `thermo.pr_c1` with the code under test, which M01's evidence covers (M02 review F10).
- Self-generated outputs are regression fixtures, not validation: the G10/G11 records are judged against M01's bounds and the probe record; G8 (f) against the design lane's table through an independent replica; G12 by its certificate, with its record a regression fixture. This is numerical verification, not empirical validation of the reactor model.
- Cross-platform reproduction of a coupled run rests on the per-float rules of R-317 (the coupling record) and build log D130 (a failure bundle's compact copy, a session decision not yet ruled by the design lane), tested by perturbing the last bits on one machine (RP-2, RP-2b, D130), not by a run on a second architecture.

## C. Spec §5 and §6 (`docs/derivations/V02-alpha-release-spec.md`)

## 5. V11–V20 at `C_α`

### 5.1 Criteria carried unchanged

| Gate | Criterion | Evidence at `C_α` (RC step, §8.2) | Moved record (§5.2) |
| --- | --- | --- | --- |
| V11 | T08 §4.1 | step 1 (K06, T01, T06, T07 nodes; T08.A10; T08.A35) | MR-10 |
| V12 | T08 §4.2 | step 1 (T05, T05b, build-first B10–B19) | — |
| V13 | T08 §4.3 and T08.A71 | step 1 (T01, T02, K03, B40–B49) | MR-7 (B50) |
| V14 | T08 §4.4 and T08.A70 | step 1 (T04, T02, B20–B25 nodes; T08.A33) | MR-8 (D3 per release) |
| V15 | T08 §4.5 | step 1; the certificate schema's `NOT_ASSESSED` uniqueness claims | — |
| V16 | T08 §4.6 | step 7 (T08.A48) | — |
| V17 | T08 §4.7 | step 8 | MR-1, MR-2, MR-6 |
| V18 | T08 §4.8 | step 1 (T08.A31–A33); step 9 (T08.A30); step 10 (T08.A34) | MR-11, MR-12 |
| V19 | T08 §4.9 | the dossier, ADR 0022 and `benchmarks/t08/v19/` at `C_α` | — |
| V20 | T08 §4.10 | step 1 (T08.A10); step 6 (T08.A46); step 7 (T08.A47) | — |

**Unchanged assertions.** T08.A10–A19, A20–A24 (under R-193's working-envelope rule), A30–A35, A40–A48, A60–A65 and
A70–A71 are carried as T08 states them, each as amended there. T08.A32 is carried as M01 spec §3.5 amends it for real
component records. Each is re-run at `C_α` by the step named above. T08.A40 requires `requirements.lock` to hash to
`ead4edf1…`. It is unchanged on `main`, `wp/M02` and `wp/M03` today (generator claim L1). A lock edit before `C_α`
fails A40, and it is not a moved record.

**V12's denominator** is §14.3's unit list (T08 §4.2). The C1 models M02 adds (`c1.*`) are W21's and W22's evidence, not
V12's. They enter the envelope's `unit_models` axis (T08.A20) without changing V12's list.

### 5.2 The moved records and their counterparts

| MR | Record (v0.1) | Why it moved | Counterpart at `C_α` | Checked by |
| --- | --- | --- | --- | --- |
| MR-1 | T08.A49's descriptions digest `171dd768…` (R-133, R-137) | R-192 (ADR 0019 A3.2: `diff_revisions`'s `outputSchema` gains `elements`) → `6c4375b4…`; R-234 (M02's additive schema members) → M02's served digest | the **surface chain** of §5.3: the digest served at `C_α` decomposes, one registered link at a time, to `171dd768…` and then to `v17-c2`'s `6d13e13d…`; the 17 description texts are byte-identical to R-133's | M07a.A37 |
| MR-2 | T08 §4.7's carry of V17 from `c7bbc98` | the surface differs from R-133's, so V17 is `BLOCKED` pending Frank (T08 §4.7, F5) | Frank's `V17 carry` row in ADR 0028, naming every link of the chain | M07a.A05; the V17 verdict |
| MR-3 | the envelope `v0.1-envelope-1`, release `0.1.0` (as released at `v0.1.1`) | R-193: the file is v0.2's working envelope `v0.2-envelope-dev`, release `0.2.0.dev0` | at `C_α`, `envelope_id: v0.2-alpha-envelope-1` and `release: 0.2.0a1`, equal to the version being cut (R-193's watch-for); T08.A20–A24 at `C_α`; the harvest covers every manifest at `C_α`, **T08's included** (R8 4, milestone 0 F3) | M07a.A10, A50 |
| MR-4 | the v0.1.0 notes' limitation list, checked against v0.1's envelope as released (R-216; R-217's amendment and merge note) | v0.2's rows (L42, L-WEB-1…4, and later ones) are not v0.1.0's | the `## v0.2.0a1` section names exactly the alpha envelope's `limitations` ids, in order, L42 and L-WEB-1…4 among them | M07a.A52 |
| MR-5 | the v0.1.0 review table and the 18-manifest harvest size (R-217) | scoped to P, K and T | the `## v0.2.0a1` review table has one row per package with a manifest at the candidate, with that manifest's `status` (the manifest at the latest committer time when there are several); the harvest's size at `C_α` (manifests, limitations, non-pass checks) is quoted in M07a's manifest and held equal by a test | M07a.A50, A52 |
| MR-6 | T08.A49 (step 8: digest, schemas, G16-b) | MR-1; `scripts/t08_rc.py`'s A49 constant is a 0.1 record and is not edited (R-192, M02 B1) | M07a.A37 replaces step 8: the chain (which also carries A49's request/response-schema clause, as T08 read it, through the last link), and G16-b 40/40 against `t07_reference_t08.json`, unchanged. The 0.1 row `a49.descriptions_digest_r133` is not a row of the alpha's RC record. Its endpoint `171dd768…` is asserted inside the chain, so nothing it fixed is released. | M07a.A37 |
| MR-7 | T08.B50 (R-134, R-144): digest `171dd768…`, the schemas of `c7bbc98`, and the content differences exactly `syn001.kinetic_cstr`, `T08-ptc-v1`, `T08-warm-v1` | the digest and the schemas as MR-1; the content moves when M02 adds `c1.*` models to `list_models` (FD-α4) | digest and schemas by the chain, under the same carry (MR-2). Content: the differences from `c7bbc98`, excluding `server.package_version`, are exactly B50's named entries plus the v0.2 additions named by register entries (each `list_models` id and `solve_policies` id). Frank's F5 ruling of 2026-09-29 ("content-only additions keep V17's carry") covers them. An unnamed addition fails. | M07a.A51 |
| MR-8 | ADR 0021 D3's acceptance of V14 (b) (2026-09-29) | D3 is per release | ADR 0028's D3 table: V14 (b) with Frank's acceptance dated on or after the alpha's `Judged` date | M07a.A04 |
| MR-9 | the v0.1.0 notes' gate table, tested against the **live** ledger and `T08-verdicts.md` | the alpha writes V and W verdicts into the same ledger rows (FD-α5) | the test reads the ledger and `T08-verdicts.md` as v0.1.0 released them (`PUBLIC_ROOT`, R-216's pattern); `## v0.2.0a1`'s table is `v0_2_gate.py --markdown`'s | M07a.A53, A52 |
| MR-10 | V11 (e): T08.A35, a real **v0.0.0**-emitted bundle | v0.1.0 was released and schemas changed after it under ADRs (ADR 0019 Amendment 3; ADR 0033–0035), so by T08 §4.1's own reasoning the clause now also applies to a v0.1.x-emitted instance | T08.A35 unchanged, **and** M07a.A42: the `SYN-001-nominal` bundle written by the CLI at tag `v0.1.1` gets a typed report from `C_α`'s `replay`, `inspect` renders it, and no exception is unhandled | M07a.A42 |
| MR-11 | T08.A34 over "every certificate the RC job emits" (steps 4–7) | the RC job now also emits coupled-route certificates (step 12) | the same rule over steps 4–7 **and** 12; step 12's output is the kept directories of §18.2, bound to the step-12 record by hash *(amended 2026-10-15, Amendment 2 B-WO10-6)* | M07a.A39 |
| MR-12 | T08.A30's scope: the default install and the `server` extra | M03 may declare an `nlp` extra (Q6) | the default install and `server` (unchanged); and every extra that `C_α` declares and `v0.1.1` did not, through its own [A10] audit and Frank's recorded licence decision (M03's: `docs/m03-ipopt-audit.md` and M03 N1). Otherwise V18 (a) is `FAIL`. | M07a.A38 |

**MR-3, after the tag.** The first commit on `main` after the tag that changes a D2.4 path returns the envelope to
R-193's working form (`v0.2-envelope-dev`, `0.2.0.dev0`). The tag `v0.2.0a1` keeps the pinned file. After `C_α`, M07a's
own manifest is excluded from the harvest (`HARVEST_EXCLUDED = ("evidence/M07a/",)`), exactly as T08's was: it is
written after `C_α`, and it is the next harvest's.

### 5.3 The surface chain (MR-1, MR-6)

**Notation.**
- `T(C)` is the MCP tool list served at `C`.
- `d(·)` is its digest, by `benchmarks/t07/v17/harness.py`'s `tool_descriptions_sha256` rule: SHA-256 of the canonical
  JSON of every tool's `model_dump(exclude_none=True)`, covering names, descriptions, `inputSchema` and `outputSchema`.

**The links.** The surface changes registered since R-133, in the order they were introduced, are links `c_1 … c_m`.
Today m = 2:

| Link | Register | What it adds | Digest after it |
| --- | --- | --- | --- |
| c_1 | R-192 | `elements`: required member of `diff_revisions`'s `outputSchema` (ADR 0019 A3.2) | `6c4375b478d71c12b1211c17fafe7e58e9dfc0a05e11def2106799a6917631c9` |
| c_2 | R-234 | M02's enum values, branches, members and `$defs` (M02 note §14 B1) | registered at M02's merge into `main` |

Each link k has a registered strip function `s_k` that removes exactly what `c_k` added, and a registered digest `D_k`
after it. `D_0` = `171dd768efcfb24f65d79d83a4f157dcfd1436935bf5106a247b84f3040e4d14` (R-133).

**The chain holds at `C_α` iff all five hold:**
1. `d(T(C_α)) = D_m`.
2. `d(s_k(s_{k+1}(… s_m(T(C_α))))) = D_{k−1}` for k = m … 1, each strip applied to the **previous strip's output**. Two
   separate strips of the served list do not satisfy this. Today's `_without_a3_2`, applied to `T(C)` directly, stops
   giving `D_0` once M02 is merged.
3. With every link stripped, serving `v17-c2`'s `validate.md` and `commit_change.md` in place of the served two gives
   `6d13e13d660521c1a39dc245d5237c974a4273b0c3eeadb02d44538ba2669a4d` (R-137).
4. The MCP tools at `C_α` are exactly the 17 of `V17_C2_FILE_SHA256`. Each description file's SHA-256 equals that table's
   value, except `validate` and `commit_change`, whose files equal R-133's. T08.A18 is therefore not reopened.
5. **Negative controls** (test states):
   - (i) a member added to another tool's `outputSchema` → the chain fails at link m, naming it;
   - (ii) `s_m` made to strip one member too many → it fails at m;
   - (iii) one byte of a non-N1/N2 description changed → item 4 fails;
   - (iv) `elements` left in place → it fails at link 1.

**A new MCP-visible change before `C_α`** (a schema edit by M03 or M04) is a new link c_{m+1}. It needs a register
entry, a strip function, a registered digest, and Frank's carry extended to name it. Without all four the chain fails
and V17 is `BLOCKED`.

### 5.4 Clause labels for V12, V16 and V17

T08 §4 letters the clauses of V11, V13–V15 and V18–V20. For a FAIL or BLOCKED row at `C_α`, the alpha's verdict
document also uses the labels below. They are labels only; no criterion changes.

- **V12 (a)**: every model of §14.3's list has, at `C`, the definition of done of T08 §4.2's rule.
- **V16 (a)**: at least 30 distinct cases. **V16 (b)**: eight shared-model comparisons. **V16 (c)**: at least two by
  both tools where feasible. **V16 (d)**: the registered ensemble. T08 §4.6's rule is "T06 verdict 1 stands and
  T08.A48 passes".
- **V17 (a)**: the agent surface at `C` is one to which Frank has carried `v17-c2`'s evidence, and M07a.A37's chain
  holds. **V17 (b)**: G16-b's ten scripted reference solutions are clean on 40 of 40 runs over Python, CLI, HTTP and
  MCP at `C`.

---

## 6. W21 and W22

Both are judged by the `verdict` agent at `C_α`, from the inputs of §6.3. A clause is `met` only when every listed
item holds at `C_α`. The gate is `PASS` iff every clause is met.

### 6.1 W21 — "PyMRM adapter with port mapping, accuracy contract, out-of-process execution policy, timeout, provenance, and parent-model validation" (blueprint §14.4 bullet 1)

The ids are M01 spec §9 (`M01.Ann`) and M02 note §10 (`Gn`). "Step" refers to §8.2.

**W21 (a) — Port mapping.** The reactor's ports, degrees of freedom and unit mapping (M01 §8.2–8.3; ADR 0027) are
implemented and checked.
- M01.A25–A32 and A49–A51 at step 1. These run on the stand-in path.
- M01.A52's record half: mapping 1 ulp, against a bound of 2.
- G4 (e)–(g), G8 (a)–(e) and G9 (b) at step 1.
- G10 (h) at step 12: the full boundary at N_tubes = 1 is within 10⁻⁶ of the record.

**W21 (b) — Accuracy contract.** The real variant declares its precision floor, ε_eval = 10⁻⁶ relative, and the
design grid's discretization estimate (M02 D7). Every `ok` result carries both: G10 (i) at step 12.

The variant's own figures hold at step 12:

| Item | Bound | Recorded |
| --- | --- | --- |
| G10 (b), path independence | ≤ 10⁻⁶ | 1.56 × 10⁻⁸ |
| G10 (e), element defect | ≤ 10⁻⁷ | 2.98 × 10⁻⁸ (M01.A45 record half) |
| G10 (f), \|ΔP\|/P_in | ≤ 10⁻³ | 4.90–5.06 × 10⁻⁵ |
| G12, the real loop's floor ratios | ≥ 10 | — |

M01 §10's grid study (M01.A48's record half) holds.

**W21 (c) — Out-of-process execution policy.** The profile is `external-subprocess-v1` (ADR 0033 D1–D2).
- G3 (a)–(h) at step 1, on Linux.
- G4 (a)–(i) and G5 at step 1.
- The support matrix states the profile, "not a sandbox", Linux as the registered platform, and Windows refused.
- M02 N1 accepted by Frank in ADR 0028's decisions table. This is a precondition, not a default, because the alpha
  publishes the profile.

**W21 (d) — Timeout.**
- G3 (b) at step 1: `timed_out` is recorded within 3.5 s of spawn under `timeout_s = 1`, and there is no retry.
- The per-attempt timeout in force at `C_α` is the one M02 §5.2 registers.
- G11 (d)'s `startup_s` and `solve_s`, measured at step 12, are recorded beside it.

No new ratio is introduced. A timeout that the measured attempt exceeds makes G12 fail, and that fails W21.

**W21 (e) — Provenance.**
- G6 (a)–(c) at step 1.
- Every experiment result record that step 12 writes carries blueprint §9.1's six items, in the fields of
  `experiment.schema.json` (ADR 0033): the boundary mapping; the version (the variant id and SHA-256, and the reactor
  commit); the discretization settings (num_z and the estimate); the convergence evidence (stage and certificate); the
  conserved fluxes (element defects); and the cost (wall time).
- G10 (g) at step 12: M01.A47 (a) bitwise, or the finding naming both CPU models with (h) deciding (R-200).
- G12's `reproduce` returns `MATCH` from the record.
- The reactor commit in the real variant equals ADR 0022's pin, `6089593464fc9bc2c0a0cb58e30ad5433ece6332`.
- The reactor and its data are used by reference under the dossier's rights table (T08.A64; ADR 0006 mode A). The
  wheel carries the reactor environment's lock and no code of the group's.

**W21 (f) — Parent-model validation**, read as decided in ADR 0028 D7. The PyMRM reactor is the parent model of v0.2's
surrogates (blueprint §9.1–9.2). Its validation evidence is carried by the adapter and stated, not re-made. The clause
is met iff all four hold:
- **(f1)** The parent model run through the adapter reproduces the parent model run standalone: G10 (g) bitwise or,
  failing that, (h) within 10⁻⁶ (M01.A47), at step 12.
- **(f2)** The parent model's own regression reference at the pin is reproduced: T08.A61 (the group's suite at
  `6089593`: 69 passed, 0 failed, 3 skips counted *not reproduced*), at the pin the variant names.
- **(f3)** The parent model's numerical error is evidenced and carried with every result: M01 §10 (A48's record half,
  the discretization estimate DX-01, path independence) and G10 (i).
- **(f4)** Its empirical validation is cited, not re-judged. The verdict and the notes say four things:
  - the group's published comparison with experimental data (Gargiulo et al. 2025 §3.1, of Rossetti et al. 2006's rate
    law; dossier H2, R-143) is the group's evidence;
  - this project has compared no reactor result with data;
  - the numbers are the group's model at the pin, a regression;
  - their discretization bias is 1.0–1.4 % in NH₃ (M02 §13).

*The stronger reading, rejected as the default (F-α4).* "Parent-model validation" would mean that this project
compares reactor results with experimental data. That is validation of the reactor's physics. Blueprint §9.1 keeps
high-fidelity model discrepancy as separate evidence, and M07's "truth checks" own it. The 4TU dataset's use also
awaits Frank's rights statement (T08 R3 8 (b)). Under that reading W21 (f) would be `BLOCKED` on the statement.

**W21 does not establish:**
- that the reactor is right: every real-reactor number is the group's model at the pin, a regression, with F-R2, F-R3
  and its discretization bias;
- bitwise reproduction across machines, or any run on aarch64, which is not measured (Q1);
- a sandbox, Windows support, or concurrency across hosts or on network filesystems;
- sensitivities through the reactor, or optimization;
- the convergence of coupled loops in general;
- that the stand-in certifies anything about the reactor (R-199).

### 6.2 W22 — "One additional validated nonideal property route sufficient for the selected chemistry" (blueprint §14.4 bullet 2; R-160; M01 spec §11)

**W22 (a) — Numerical verification.**
- M01.A05–A22 pass at step 1. Their expectations come from closed forms (`m01_reference.py`), independent of the
  implementation.
- M01.A34 (`m01_reference.py --check`) passes at step 1.

**W22 (b) — Conformance with an independent implementation of the same method.**
- M01.A37 at step 1: `pr-c1-v1` at `C_α` against the committed IDAES 2.13 record.
- Step 11: re-running `idaes_conformance.py` in the IDAES environment gives numbers identical to
  `benchmarks/m01/idaes-conformance.json`. Only `inputs.*_sha256` members may differ, and each that does is listed
  (M01's manifest records `inputs.reference_values_yaml_sha256` and gives the reason).

**W22 (c) — Empirical validation of the pure-component behaviour that drives the loop**, against the reference
equations of state. The bands are validation bands (R-160), the design lane's fitness statement. They are not
numerical tolerances.

| Assertion | Quantity | Measured | Band | Band ÷ measured |
| --- | --- | --- | --- | --- |
| M01.A38 | max \|P_sat,PR/P_sat,ref − 1\|, 240–320 K | 0.012675 | 0.02 | 1.58 |
| M01.A39 | max \|Δ ln φ^L\|, NH₃ at the separator states | 0.040096 | 0.05 | 1.25 |
| M01.A40 | max \|Δ ln φ^V\|, light gases and NH₃ vapour | 0.042371 | 0.05 | 1.18 |

The table is generator claims M1–M3. Step 11 re-derives these values at `C_α` with
`external_crosscheck.py --check` (exit 0).

The provider at `C_α` equals the closed form within A05–A22's tolerances, 10⁻⁹–10⁻¹⁴ (W22 (a); M01 §9.8), and the
closed form is what the bands compare. So the route validated is the provider that `C_α` ships.

The verdict quotes the three ratios. It does not turn them into a confidence statement.

**W22 (d) — Sufficient for the selected chemistry.** The C1 loop binds every property evaluation to `pr-c1-v1` and
solves to `VERIFIED`:
- G7 (a)–(e) and G8 (a)–(c) at step 1;
- G12 at step 12.

The gaps the route leaves are stated:
- the LIQUID regime and pure-NH₃ flashes are deferred and refused typed (M02 N5);
- dissolved light gases are not represented (R-143);
- k_ij = 0, with its effect stated (R-157);
- there is no mixture VLE validation (R-160);
- PR's saturated-liquid volume is 11–30 % high and its enthalpy of vaporization 2–5 % high (M01 §11). No loop decision
  in v0.2 uses either.

**W22 does not establish:**
- mixture VLE;
- the effect of k_ij beyond R-157's statement;
- the near-critical region;
- liquid-density fitness;
- any claim outside the five C1 components and the domain M01 registers.

### 6.3 The verdict procedure

**Who and when.** One `verdict` agent, after the RC record is complete (§8.3) and M07a's manifest is `tested`. It
judges V11–V20, W21 and W22 together, at `C_α`. It does not judge W23–W27.

**Its brief must paste:**
- the RC record's step table, with every record's path and SHA-256;
- the M01 manifest (`evidence/M01/3c80392…`) and the M02 manifest (at M02's `tested` commit), their checks and
  limitations;
- §5 and §6 of this specification;
- T08 §4;
- ADR 0028's tables as they stand.

**Output.** `docs/reviews/V02-alpha-verdicts.md`, in T08 Amendment R3 §R3.3's form, with three differences:
- The header line is `**Release candidate:** \`<C_α, 40 hex>\`   **Judged:** <YYYY-MM-DD>   **By:** design lane (\`verdict\`)`.
- There is exactly one table with a `Verdict` header: `Gate | Verdict | Failing clauses | Travelling limitations |
  Basis`, with twelve rows, `V11` … `V20`, `W21`, `W22`, in that order.
- Clauses are written `Gnn (x)` with §4's, §5.4's and §6's labels. Limitation ids come from the alpha envelope.

Below the table there is one section per gate. Each section judges every clause met, not met or blocked, gives its
evidence at `C_α`, and states what the verdict does not establish. For W21 and W22 that is at least the lists of
§6.1–§6.2.

**Rules.**
- A V or W verdict that differs from v0.1's at `67c66d9` says why in its section.
- The verdict never sets `reviewed`.
- It never moves a tolerance, a band or a classification rule.

---

## D. T08 §3.3 and §4 (`docs/derivations/T08-release-spec.md`)
### 3.3 Rules of judgement

- **Vocabulary.** The ledger takes `PASS`, `FAIL`, `BLOCKED` (`schemas/requirements-ledger.schema.json`); the brief's MET / NOT MET are `PASS` / `FAIL`. `BLOCKED` is used **only** when the missing input is outside both lanes' authority (Frank's decision, a rights statement, external access). Evidence the lanes were to produce and did not is `FAIL`, never `BLOCKED`. A gate whose clauses are all met with registered limitations is `PASS`, and its limitations travel by envelope id (§5) into the verdict, the gate report and the release notes.
- **Clause-wise.** A gate is `PASS` iff every clause is met. A `FAIL` names the clause. A gate is never reworded to pass, and no clause leaves the denominator (plan §1.1).
- **At the RC commit.** A verdict judges the RC commit. Package manifests are evidence about their own commits; they count for the RC through the RC job (§8.2), which re-runs every registered assertion (the full gate on both architectures) and the campaigns named in §4. A campaign result that no longer holds at the RC is `FAIL` at the RC and the earlier record stands as history (R-087's precedent).
- **No new tolerance.** A verdict may not change a tolerance, a mapping, a setting or a classification rule. T08 adds none.
- **Numerical verification, empirical validation, optimality evidence** stay distinct in every verdict and in the release notes. Nothing in v0.1 is empirically validated: SYN-001 is synthetic.

---

## 4. Gate criteria

### 4.0 Summary

| Gate | Clauses (blueprint §14.3 / §13.4) | Existing evidence | Expectation | T08 adds | Frank |
| --- | --- | --- | --- | --- | --- |
| **V11** | semantic diff; immutable drafts; task-specific validation; units and component/reference checks; real migration if applicable | K06, T01, T06 (A43, A55–A57, A67–A74), T07 (`diff_revisions`, `preview_change`) | likely PASS | the migration probe (T08.A35); D1 (T08.A10) | — |
| **V12** | the §14.3 unit list; per-model definition of done | T05, T05b | likely PASS | ledger evidence list (T08.A02) | — |
| **V13** | DM/SCC/BTF with block statistics; safeguarded recycle and coupled EO; scales before iteration; model initialization; **warm starts** | T01, T02, K03; T03 spec: warm starts across runs absent in v0.1 | **FAIL on the warm-start clause** | nothing unless F2 says build | **F2** |
| **V14** | typed homotopy; **one PTC family qualified by §7.5** with tested SER; three bounded recovery edges | T04 (PTC experimental, §8.3), T02, ADR 0015 | **FAIL on the qualified-PTC clause** | nothing unless F1 says build | **F1** |
| **V15** | phase disappearance/reappearance with frozen attempts; cross-unit spec promotion without nested SM; multiple roots with honest branch reporting | T02, T03, T06 (ADV-05, THM-09 census) | likely PASS | re-run at RC (T08.A41) | — |
| **V16** | ≥ 30 distinct cases; eight shared comparisons; ≥ 2 by both tools where feasible; registered ensemble | T06 verdict 1: 8/8 by both, 16/16 AGREE | PASS (carried) | our side at RC (T08.A48) | — |
| **V17** | local/HTTP/MCP; ten tasks; ≥ 80 %; zero unauthorized actions and false verification | T07 verdict: 25/30 on `v17-c2` | PASS (carried) | surface identity and scripted transports at RC (T08.A49) | F5 only if the surface changed |
| **V18** | dependency/data provenance incl. the binary inventory; final target-Jacobian regularity; qualified energy checks; no enabled recovery edge without a direct failure test | P03, K04, T06 (A32, A33, A37–A46), T02/T04 edges | needs T08 work | T08.A30–A34 | — |
| **V19** | real chemistry selected and specified for v0.2 with data and comparison feasibility established | OpenIDAES-450 audit; the group's ammonia model (found locally) | needs T08 work + Frank | T08.A60–A65, the dossier | **F3** |
| **V20** | nominal fixtures pass; invalid structural cases rejected for the right reason; no false `VERIFIED` in the adversarial suite; ≥ 95 % over the registered ensemble | T06 verdicts 2 and 3a (run 2: S = 434/440 on both classes) | likely PASS | ensemble at RC (T08.A46); T08.A47; D1 (T08.A10) | — |

### 4.1 V11 — semantic diff, drafts, task validation, units/references, migration

*Clauses* (blueprint §14.3 bullet 1): (a) semantic diff; (b) immutable drafts; (c) task-specific validation; (d) units and component/reference checks; (e) a real migration fixture if applicable.
*Evidence to judge:* (a) T07's `diff_revisions` / `semantic_diff` `$def` and its tests; (b)–(c) K06's content-addressed revisions, draft vs ready, optimistic conflict, idempotent commit, and T01's structural validation (STR-01…06; R-022's DRAFT/INVALID rule); (d) T06 A43, A55–A57, A67–A74 (DIM-01, COMP-03, ADR 0016), THM-05 (`reference_convention_not_reaction_consistent`); K06's `unsupported` structural-over-specification check is superseded by T01 A09 (the verdict cites the superseding test). (e) **Applicable**: v0.0.0 was tagged (`9a4391f`) and every schema that changed afterwards did so under an ADR that states its migration impact (ADR 0009, 0005, 0010, 0012, 0015, 0018: an old policy is refused, never reinterpreted). The clause is met iff the RC does what those ADRs say on a *real* v0.0.0-emitted instance: T08.A35.
*T08 adds:* T08.A35; T08.A10 (D1 is also a validation-message defect, judged under V20).
*Verdict rule:* PASS iff (a)–(d) each have a passing test node at the RC and T08.A35 passes.

### 4.2 V12 — required unit library with per-model definition of done

*Clauses* (bullet 2): network units, heater/cooler, TP/PH flash, component separator, conversion reactor, simple valve and liquid pump, one two-stream exchanger; each with its definition of done (plan T05 row: contract, limiting/failure tests, balance and derivative evidence, at least one coupled case per family).
*Evidence:* T05 A00–A30 and T05b B00–B36/X00–X26; `MODEL_BUILDERS` lists twelve models (feed, sink, adiabatic mixer, TP heater, TP flash, splitter, PH flash, valve, liquid pump, conversion reactor, component separator, heat exchanger). A cooler is the TP heater with negative duty (ADR 0001 sign convention).
*T08 adds:* `docs/requirements.yaml` V12 `evidence` lists T05 and T05b (it is `[]` today; T08.A02).
*Verdict rule:* PASS iff every listed model has, at the RC, a passing contract test, a limiting/failure test, a balance test, a derivative test, and appears in at least one registered coupled case. A model whose DoD item is `unsupported` in a manifest is a limitation of that model, listed in the envelope, not a pass.

### 4.3 V13 — structure, recycle and EO, scaling, initialization, warm starts

*Clauses* (bullet 3): (a) DM/SCC/BTF diagnostics with block statistics and canonical tie-breaks; (b) a safeguarded recycle solve and a coupled EO block, with EO/tear agreement; (c) physical scales before iteration, fixed within an attempt (D06); (d) model initialization — the local model initializers and upstream propagation of §7.4, every candidate checked, rejections recorded; (e) **compatible warm starts** (§7.4's second source: a prior run's state offered as an initial candidate for a compatible problem, checked like every other candidate).
*Reading of (e), decided here.* §14.3's "model initialization and warm starts" sits in the solver-kernel bullet and names §7.4's sources. K02's **warm-start cache** (§6.4, D10: property-level hints that are never an exact answer) is a different mechanism and does **not** satisfy (e). The plan's V13 text ("scaling and initialization") omits "warm starts" and "block statistics"; the blueprint clause counts (§1; FD1).
*Evidence:* (a) T01; (b) T02 (A13–A15, A32, A34); (c) K03, T02; (d) K03 §10.1 and its `unsupported` `K03.initializer_chain`, T02/T05 traversal initializers, T06 F4's sequential restart; the verdict must find, for each §7.4 source, either a passing test or a recorded absence (an absent source silently skipped fails (d)). (e) T03 spec §5.1 (the opening checks are ready for "a compatible warm start, K03 §10.1 source 2, absent in v0.1") and §13 ("none exists in v0.1"); K03 §10.1 ("recorded absent").
*Expectation:* (a)–(d) met; (e) judged at the RC on T08 build-first B40–B51 (R-124); F2 answered *build* *(amended 2026-09-29, T08 build-first §E.1)*. T08.A71.
*Options (F2):* (i) tag v0.1 with V13 FAIL on (e), warm starts owned by M03 (sweeps are where they pay); (ii) build them in T08: an `architect` design note (explicit source — a named prior bundle's `solution-state.json` — or automatic from the store; how the source enters the RunManifest and replay identity; whether the frozen `Application.solve` needs a sibling operation, which is an ADR 0019 amendment), then one build increment and a `reviewer` pass: about one week, and it touches replay identity; (iii) hold the tag. *Recommended default:* (i).

### 4.4 V14 — homotopy, qualified PTC/SER, three bounded recovery edges

*Clauses* (bullet 4): (a) one typed homotopy; (b) **one PTC family qualified by §7.5 with tested SER control**; (c) three tested recovery edges with budgets, rollback and unchanged target semantics.
*Criterion for (b), fixed here.* A family is qualified for V14 iff **all** hold: (b1) T04 §8.1's criterion, **unchanged**: route (a) holds and, on the registered comparison, the set of starts from which PTC reaches the registered root is not contained in damped Newton's, under the same contract, tolerances and budgets; (b2) the comparison case — its starts, criterion and budgets — was committed before any PTC result on it existed (git order is the evidence); (b3) the family is selectable, by a registered policy, on a flowsheet inside the v0.1 envelope (§5): a family no supported flowsheet can select is not a v0.1 capability; (b4) SER tested (T04 A19–A22).
*Why not re-read.* Blueprint §7.5 lists route (a) — a physical derivation — as acceptable, and T04 §8.2 shows route (a) holds. But T04 registered, before running the comparison, that the family qualifies only if it also improves a tested basin (blueprint §15's risk row: "improves no tested basin → keep it experimental"), and the plan says "if no useful qualified family passes, retain PTC as experimental and record the v0.1 gate as incomplete". Reading route (a) alone as sufficient now, after the comparison came out 18/18 for both methods, is a criterion changed after the result. Rejected (R-118).
*Evidence:* (a) T04 A02–A12; (b) T04 §8.3: 18/18 both, PTC 1.9–8.8× costlier → (b1) fails; (b) PTC-R1: T08 build-first spec Part A *(amended 2026-09-29, T08 build-first §E.2)*; (c) T04 §5.5's table (edges 1–2 from T02, edge 3 here), plus ADR 0015's sequential restart.
*Expectation:* (b) judged at the RC on T08 build-first B20–B25 against §A4's resolution of T04 §8.4 (R-123); outcome not known; F1 answered *build*; (a) and (c) met *(amended 2026-09-29, T08 build-first §E.2)*. T08.A70.
*What qualification would cost (F1).* T04 §8.4 preregistered **PTC-R1** (Uppal–Ray–Poore exothermic CSTR, `Da = 0.072`, `B = 8`, `β = 0.3`, `Le = 1`, 21 × 21 starts) with its owner "the first package that registers a reactor with holdup". Run as a bare two-variable residual through T04's generic core it would take about a day, but it fails (b3): no supported flowsheet can select it. Meeting (b3) needs a kinetic CSTR with holdup as a unit model, its mass-mapping derivation (route a), the preregistered comparison, and review: about one to two weeks, outcome not known in advance. A NET-07-based qualification would need a new preregistration (T04 did not register one) and mappings for the exchanger and PH flash: similar cost.
*Options (F1):* (i) tag v0.1 with V14 FAIL on (b), PTC experimental and selectable by explicit policy only, PTC-R1's owner assigned at v0.2 planning (FD6); (ii) build the CSTR-with-holdup route in T08; (iii) hold the tag. *Recommended default:* (i) — the homotopy and all three edges are delivered, and T04 showed that on the registered flowsheets PTC cannot help by structure.

### 4.5 V15 — frozen phases, EO cross-unit specification, multiple roots

*Clauses* (bullet 5): (a) phase disappearance/reappearance under frozen attempts with restart tests (A01); (b) cross-unit specification promotion to EO without nested SM loops (A02; plan T02 A02 test: capability error if a region unit lacks EO derivatives); (c) a multiple-root example with honest branch reporting (D11: no uniqueness or dynamic-stability overclaim).
*Evidence:* (a) T03 (A00–A26); (b) T02; (c) T03's root fingerprint and branch provenance, T06 ADV-05 (A15) and THM-09's branch census (A31); T06 spec §15's "no uniqueness claim".
*Verdict rule:* PASS iff each clause has passing test nodes at the RC (T08.A41) and no certificate or report states uniqueness or dynamic stability.

### 4.6 V16 — corpus, comparisons, ensemble

*Clauses* (bullet 6 and plan §5.1): ≥ 30 distinct correctness/diagnostic cases; eight shared-model comparisons across DWSIM and IDAES; ≥ 2 by both where feasible; the registered §13.4 ensemble.
*Evidence:* T06 verdict 1 (8 of 8 by ≥ 1 tool, 8 of 8 by both, 16/16 AGREE, positive controls DISAGREE); T06 A01 (49 cases, distinctness by mechanism as registered); the ensemble registration (22 × 20).
*T08 adds:* T08.A48 (our side re-solved at the RC equals its committed records; the tool side is not re-run — tool versions and inputs are unchanged, and T06 A48's fingerprints stand). The IDAES near-sharp-ε disclosure travels (envelope limitation L16).
*Verdict rule:* PASS iff T06 verdict 1 stands and T08.A48 passes.

### 4.7 V17 — the agent binding

*Evidence:* T07 verdict (G17 and V17 MET on `v17-c2`, pinned configuration, MCP-only agent evidence). Its §8 limitations travel verbatim (envelope L12).
*T08 adds:* T08.A49: the agent-facing surface at the RC — the served tool descriptions' digest equals R-133's carried surface `171dd768…` (which differs from `v17-c2`'s `6d13e13d…` in exactly `validate.md` and `commit_change.md`), and the operations table's request/response schemas equal `v17-c2`'s — and G16-b's ten scripted reference solutions pass 40/40 over Python, CLI, HTTP and MCP at the RC.
*Verdict rule:* PASS (carried from `c7bbc98`, across R-133's recorded change) iff T08.A49 passes. If the surface differs from R-133's carried surface, V17 is `BLOCKED` pending a new decision of Frank's (F5; a new campaign is billed subscription time). *(amended 2026-10-01, Amendment R3 2)*

### 4.8 V18 — distribution/data gates, rank evidence, energy checks, recovery edges

*Clauses* (bullet 8, [A08/A09/A10]): (a) dependency and data provenance gates including the binary inventory; (b) final target-Jacobian regularity diagnostics; (c) qualified energy checks; (d) no enabled recovery edge without a direct failure test.
*Evidence and T08 work:* (a) P03's audit and ADR 0006; T07's server-extra licence inventory (G19); **T08.A30–A32** — ADR 0006 D5.4's refresh is due because the aarch64 wheel was never audited (ADR 0006 "does not establish") and the default install's other compiled distributions (numpy, scipy and their vendored libraries; the server extra's compiled wheels) have never been inventoried at object level. (b)–(c) K04, T06 A32, A33, A37–A46, re-run at the RC, and **T08.A34** over every certificate the RC job emits. (d) **T08.A33**, the recovery-edge inventory (§5.6).
*Verdict rule:* PASS iff T08.A30–A34 pass. An object in a required closure whose licence is restrictive, GPL-family other than the LGPL Frank allowed (ADR 0006 Q1), or unresolved, and which no ADR dispositions, is FAIL — and goes to Frank as a blueprint §15 reading, as ADR 0006 Q1 did.

### 4.9 V19 — the real-chemistry dossier

*Clause* (bullet 9): "real-chemistry reference journey selected and specified for v0.2 with data and comparison feasibility established"; plan §4.4: "a scored dossier: available validated reactor/kinetics, property coverage, data rights, independent simulator case, computational cost, and a continuous design decision affected by reactor fidelity. Prefer a model Frank's group can actually provide."
*Verdict rule:* PASS iff (i) Frank's selection recorded in ADR 0022 *(amended 2026-10-02, Amendment R7 2)*; (ii) the dossier for the selection has every item of §7.1 (T08.A60); (iii) H1–H6 are all `met` for the selection (§7.2) — `needs_frank` resolved by Frank's statements, `needs_fact` by measurement; (iv) T08.A61–A63 pass; (v) the rights table has no unknown (T08.A64). `BLOCKED` while the selection or a rights statement is outstanding; `FAIL` if the selected chemistry fails a hard criterion after measurement.

### 4.10 V20 — nominal robustness, invalid structure, adversarial suite

*Clauses* (§13.4): (a) all fixed nominal correctness fixtures pass; (b) every injected invalid structural case is rejected for the right reason, **naming the revision's own objects** (§7.7: "return actionable unmatched objects"); (c) no false `VERIFIED` in the adversarial suite; (d) ≥ 95 % verified success over the registered ensemble (20+ cases × 20 starts), with per-case rates and uncertainty.
*Evidence:* T06 verdicts 2 and 3a (run 2; run 1's FAIL stands); T06 A04–A08, A16, A19, A20.
*T08 adds:* **T08.A46** — the registered gate re-run at the RC on `ref-x86-64` and `ci-aarch64` with the registered starts and the unchanged classifier; **T08.A47** — the adversarial and invalid-structure suite at the RC; **T08.A10** — D1.
*Verdict rule:* PASS iff T08.A10, A46 and A47 pass. The one-sided 95 % Clopper–Pearson lower bound is reported, never gated (Frank, T06 Q7). At the gate's threshold S = 418 of 440 it is **0.92937011597863969609**; at run 2's S = 434 it was 0.97326390295610562038 (generator-checked). Both assume independent starts, which clustered starts are not (plan §6.2).

---


## E. ADR 0028's tables (`docs/adr/0028-v0.2-pre-release-policy.md`)
### D5. Where the evidence lives

| Item | Path |
| --- | --- |
| Evidence package | `M07a` (manifest-schema pattern `[PKTMSR][0-9]{2}[a-z]?`; T05b's precedent for a package with no ledger row) |
| Manifest | `evidence/M07a/<C_α>/manifest.json` |
| RC records | `evidence/M07a/<C_α>/rc/` and `artifacts/` (T08 Amendments R7 1 and R8 1) |
| RC record | `docs/v02-alpha-rc-record.md` |
| Verdicts | `docs/reviews/V02-alpha-verdicts.md`: twelve rows, V11…V20, W21, W22 |
| C's file record | `release/rc-trees/<C_α>.json` (R-151's format, written at the RC) |
-
`accepted, YYYY-MM-DD`, dated on or after the alpha verdict's `Judged` date (spec Amendment 1, Table T6).

| Item | Question | Default | Frank's answer |
| --- | --- | --- | --- |
| N3 | What `0.2.0a1` claims (spec §3, F-α0) | `v0.2-alpha-gate-v1`: V11–V20 re-judged at `C_α` by T08 §4 unchanged, plus W21 and W22; nothing of W23–W27. Alternatives: (i) also W26; (ii) W21 and W22 only; (iii) no pre-release before M05 or 0.2.0 | pending |
| V17 carry | Carry `v17-c2`'s agent evidence (V17, and T08.B50's surface) across R-192 (`elements` in `diff_revisions`'s output schema) and R-234 (M02's additive schema members), with the decomposition chain of spec §5.3 recorded (F-α2) | carry, as R-133 did; alternative: a new V17 campaign (about USD 10, one hour) | pending |
| M02 N1 | Publish `external-subprocess-v1` in `0.2.0a1`: the group's pinned code runs with the user's privileges, unconfined, on Linux (F-α3) | accept, stated as "not a sandbox" in the support matrix and the notes | pending |
-
starts with `accepted` and holds a date on or after the alpha verdict's `Judged` date.

| Clause | Evidence | Frank's acceptance | Owner after 0.2.0a1 |
| --- | --- | --- | --- |
| V14 (b) | the alpha verdict at `C_α` (`docs/reviews/V02-alpha-verdicts.md`); T08's PTC-R1 records (`docs/reviews/T08-verdict-V14b.md`) | pending | a later package that preregisters a new family or new SER settings before any result (R-118) |
