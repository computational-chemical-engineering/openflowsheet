# V03 — the release-candidate record at `C`

V03 release specification (`docs/derivations/V03-release-spec.md`) §4 and Amendment 2 (R-903…R-908), WO-6, in
`docs/v02-rc-record.md`'s form. This record **reports**; it judges no gate. Each Result cell states what the step's
record or CI job says, in the closed vocabulary `scripts/v0_3_gate.py` reads through `v0_2_gate.py`'s
`rc_record_problems` (`PASS` / `success`; `FAIL` / `failure` / `skipped` / not measured); the verdicts are the
design lane's. Every record the per-step table cites is committed under `evidence/S13/a3e508e35fc5451fe56fa7b70941621992d35b50/rc/` at the same relative
path (a record over 1 MB gzip-compressed beside it), and `rc/records.json` lists all 110 with sha256, size and how each
is kept (five gzip-compressed: the two ensemble run files, the aarch64 S07 A31 report and the two G11 experiment records of step 12).
The scripts that ran the local steps are committed beside them, under `evidence/S13/a3e508e35fc5451fe56fa7b70941621992d35b50/tools/` (byte-identical to what
ran; the Python ones with a `.txt` suffix so that the linters of `check.sh` do not read them).

## The candidate and the runs

- **`C` = `a3e508e35fc5451fe56fa7b70941621992d35b50`** ("V03 (WO-6): decisions log — the run at 4fa15ef, its three failures, the new C and the handoff").
  Package `openflowsheet` `0.3.0`. K3 = `295a2e65` is its ancestor, and no D2.4 path changed after WO-5
  (`git diff --name-only 28a2be21 C -- src schemas benchmarks requirements*.lock pyproject.toml MANIFEST.in README.md
  LICENSE NOTICE` is empty). Its tree record is `release/rc-trees/a3e508e35fc5451fe56fa7b70941621992d35b50.json` (R-151). Amendment 2 (`8e0cb1a1`, docs
  only) landed after `C`; `C` was not re-cut and every record names `C`.
- **CI dispatch run 41108983463** (`workflow_dispatch`, `rc_alpha=true` only, head `C`, ref `wp/V03-rc`):
  conclusion **success**. **CI push run** 41108983672 at `C` (`check` on both architectures, `default-install`,
  `identity`): **success**; the `Site` push run 41108983605: **success**.
- **Local steps** on `ref-x86-64` (AMD Ryzen Threadripper PRO 5965WX, Linux 6.12.111+deb13-amd64, Python 3.13.5), run
  2026-10-30 19:42 to 20:48 from a detached worktree at `C` (`.claude/worktrees/rc-v03-a3e508e`, clean throughout:
  `git status --porcelain` empty at the start, after the venv, after the W27 archive's hard links and at the end) in a
  fresh venv of `requirements.lock` with the worktree installed editable (`--no-deps`); threads pinned
  (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`); each pytest with its own `--basetemp` outside the
  repository. Steps 2 and 6–17 ran in one session from one script, `tools/run_local.sh` (0.2.0's, retargeted to
  `evidence/S13`: step 15 carries the journey of J = `2d945b5d` with `scripts/v0_3_gate.py`; step 17 is V03's
  17a–17e, recorded by `C`'s `scripts/v03_rc.py`), every environment built afresh, logs under
  `~/.cache/of-rc-v03-a3e508e/`; its one-line-per-command summary is `tools/run_local.summary.txt` (65 commands; every
  exit 0 except `step14-nlp-collect-all` exit 2 and `step16-dryrun` exit 1, both as Amendment 2 registers them: A33
  does not judge the collection over `tests/`, and A32 (d) requires the dry run's exit 1) and the durations in seconds
  `tools/durations.txt`. `tools/fetch_ci.sh` downloaded the dispatch run's artifacts and job logs; `tools/collect.sh`
  copied the cited records here and `tools/make_record.py.txt` wrote this table's hashes from `rc/records.json`.
- **Step 12** ran in the reactor environment built from `C`'s `src/openflowsheet/adapters/pymrm/reactor-env.lock`
  (`build`, then `verify`) under an external root outside every repository; the G12 runs through
  `tools/g12keep.py.txt`, which keeps the scratch directories so that step 10 can audit their certificates (R-348).
  The five kept `solution-certificate.json` files are committed under `rc/step12/certificates/<kept bundle path>/`.
  G11 took 1755 s.
- **Step 14** ran in a second clean detached worktree at `C` (`~/.cache/of-rc-v03-a3e508e/nlp-wt`, no install into
  it), every command under `env -i` with only the variables `scripts/m03_nlp_check.sh` and M05's manifest set, in
  m05's audited `.venv-nlp`. `m03_nlp_check.sh` gets the 13 modules `grep -l 'mark.nlp' tests/test_*.py` lists
  (`step14/nlp-modules.txt`), and the two `--collect-only -m nlp` runs compare them with `tests/` (A33, R-907).
- **Steps 11–14 and 16's records** `stepNN/rc-stepNN.json` are written by `tools/m07_rc_external.py.txt` through
  `t08_rc.finish`; step 16's has A32's four checks (Amendment 2), step 14's A33's `a60.w24.nlp_selection`. Steps 15
  and 17a–17e's are written by `C`'s `scripts/v03_rc.py`.
- **Step 1's skip lines** (R-376): `evidence/S13/a3e508e35fc5451fe56fa7b70941621992d35b50/step1-skips/ci-x86-64.txt` (69 lines) and
  `…/step1-skips/ci-aarch64.txt` (73 lines), outside `rc/`; they are not RC records.

### Jobs of run 41108983463

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — `check.sh: PASSED`; pytest 17856 passed, 107 skipped; the browser test required | 1, 16 |
| `check (ubuntu-24.04-arm)` | success — `check.sh: PASSED`; pytest 17826 passed, 107 skipped | 1 |
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
| `rc-coolprop (ubuntu-latest)` | success — 4174 passed, 0 skipped | 17 (17b) |
| `rc-coolprop (ubuntu-24.04-arm)` | success — 4173 passed, 1 skipped (the registered A31b skip) | 17 (17b) |
| `ensemble`, `ptc-r1`, `ensemble-compare`, `a89-repeats`, `a30-inventory` | skipped (not RC inputs) | — |

All artifacts downloaded (`gh run download 41108983463`); the RC jobs' logs saved under `…/artifacts/rc/ci/job-logs/`.

## Per step

Paths are relative to `evidence/S13/a3e508e35fc5451fe56fa7b70941621992d35b50/artifacts/rc/` (and, committed, to `…/rc/`).

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
| 1 | V03.A20, A24 (alpha §8.2 step 1) | CI x86-64 `check (ubuntu-latest)` | success (`check.sh: PASSED`; ruff check, ruff format, mypy, pytest, node exit 0; 17856 passed, 107 skipped, 197 deselected; then 3496 passed, 1 skipped); S07 A31 bitwise; S11 thermal check bitwise; THM-09/4 94 | `ci/job-logs/check-ubuntu-latest.log`, `ci/s07-a31-report-x86_64/a31_report_x86_64.json` | `fc6a252e15170907c1b2231e6d6b1af2298077f5f4158af620e9de6a6fd0ab1e`, `ad7aa37890278612e088aff0a969a661fa39129efc14225838d2beeb8b1de34c` |
| 1 | V03.A20, A24 (alpha §8.2 step 1) | CI aarch64 `check (ubuntu-24.04-arm)` | success (`check.sh: PASSED`; 17826 passed, 107 skipped, 197 deselected; then 3495 passed, 2 skipped); S07 A31 within §20 (class T worst 5.658e-11 of 1e-10, class N 0.0183 of its allowance); S11 thermal classes: flash 0.0240 of its bound, relative 1.463e-03 (≤ 0.1, R-845's watch); THM-09/4 136 | `ci/job-logs/check-ubuntu-24.04-arm.log`, `ci/s07-a31-report-aarch64/a31_report_aarch64.json` | `62c1269144817b8ae47e580290b0c824ba38c62bdfb4c921b930bebe1d857cb5`, `d4dbd4db28ba5f2b7dc850d9d0d4285e990d356fe308b78bf9647f6d746869c6` |
| 2 | V03.A20 (T08.A42) | local `ref-x86-64` | PASS (3/3): minus-t07 `24af004a…`, t07 key `887a2e62…` as registered; unchanged under the trial version `0.1.0` | `identity/rc-identity.json` | `e0f005fbf9cb2f23cbbaf31a66ee46df10e812c4fecfed40c74618ed1f8b8473` |
| 2 | V03.A20 (T08.A42) | CI `ci-x86-64` (`rc-steps`) | PASS (3/3): the same digests | `ci/rc-steps-ubuntu-latest/identity/rc-identity.json` | `58698c60fc76baa7a633ec1ba0f11285ff08362cae5535717a2d140d7de3753c` |
| 2 | V03.A20 (T08.A42) | CI `ci-aarch64` (`rc-steps`) | PASS (3/3): the same digests | `ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json` | `70bbf9eae07b6d62dd46a2592f29ae0b364ad181d65ce9508ef9b9ac16bb5b17` |
| 2 | V03.A20 (T08.A42 cross-arch, G05) | CI `identity` | success ("G05: R0 structural identity equal across 2 platforms") | `ci/job-logs/identity.log` | `a870edbb870e813e3519b02a944a299d600374c3bb037fdc9e3e2986bd5789fa` |
| 3 | V03.A20 (T08.A43) | CI `dist` | PASS (8/8): `a43.version` `0.3.0`; wheel bytes equal across the two builds | `ci/rc-dist/t08-a43-dist.json` | `0db86dd0961a9962b88bbebdb39c07c006ec0008c576b80b7dca564bf2f9ac5f` |
| 4 | V03.A20 (T08.A44) | CI x86-64 clean env | PASS (10/10): wheel `0.3.0`; smoke solve CONVERGED / VERIFIED | `ci/rc-install-ubuntu-latest/install-ubuntu-latest.json` | `9d99c671b96e66d8f832adf2f8aeb7a65ff806ea8abdd3a8de0f9ab7264e2998` |
| 4 | V03.A20 (T08.A44) | CI aarch64 clean env | PASS (9/9): wheel `0.3.0`; smoke solve CONVERGED / VERIFIED | `ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json` | `451cef4fbf7d709ba825f82ad2782c897a31e030767a8c3e664f8b8fdb951150` |
| 4 | V03.A20 (T08.A19 (b, c)) | CI x86-64, `--state installed` | PASS (4/4): as registered | `ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json` | `e03c4597dfe8cb8d11a8fd7040ac89e47542687c336edb913ec9b44244daed11` |
| 4 | V03.A20 (T08.A19 (a, c)) | CI x86-64, `--state checkout` | PASS (4/4): as registered | `ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json` | `d0ff25c2a16056361a45b0bf9678b38b372e103dfe2d540ffdcb7995671beef1` |
| 4 | V03.A20 (T08.A19 (b, c)) | CI aarch64, `--state installed` | PASS (4/4): as registered | `ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json` | `65b3422578812145ca43e854faf874bf06dc362cd87e954421583f910af095ee` |
| 4 | V03.A20 (T08.A19 (a, c)) | CI aarch64, `--state checkout` | PASS (4/4): as registered | `ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json` | `8135797729229ab34a4397b8ad16555979b300b8023099383f30e8ecdb2ca43d` |
| 5 | V03.A20 (T08.A45 write) | CI x86-64 `bundle-set` | success (job conclusion; the index carries no check list): `n_b` 52, every entry exit 0 | `ci/rc-bundles/index.json` | `d653ed3d3414a7f3ee1644964447aaccaa77ae5faf0c325ac498ac09b25ea2a2` |
| 5 | V03.A20 (T08.A45 replay, A14 C1–C3) | CI fresh x86-64 | PASS (8/8): `N_b` 52; every bundle `MATCH`, modes `exact_replay` 52 | `ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json` | `d7684ac36bbfad9096210eb2d07f9c570e23d56a2d2285536a204524baa5b120` |
| 5 | V03.A20 (T08.A45 replay, A14 C1–C3) | CI aarch64 | PASS (8/8): `N_b` 52; every bundle `MATCH`, modes `compatible_reproduction` 52 | `ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json` | `cc50f546b5617596876ad26b86450a1df6d71653bc8167105389d4fbcc09cd92` |
| 6 | V03.A20 (T08.A46, A47 S3) | local `ref-x86-64` | PASS (7/7): N = 440, S = 437, F-FALSE-SUCCESS-CAUGHT 3; gate S ≥ 418; none verified outside S3 (worst success ratio 0.0968); A33 0; T06 A34 same-class replay 25 of 25 MATCH | `ensemble/rc-ensemble-ref-x86-64.json` | `4156e261a71e8b1693fba8431a6f6a96bc445e224a6045be6c8fec8a708e7813` |
| 6 | (run file, report, replay) | local | — | `ensemble/rc-ref-x86-64.json`, `ensemble/rc-ref-x86-64.report.txt`, `ensemble/rc-ref-x86-64.replay.txt` | `1c4fd25c17e7be23893cc422d83412a3fb5c7cec7c7c71181e5dbc14098010ca`, `23e7a092c63b5921c30a5201ccdfc882d05c21034ea8d9bf728b28de028ca2ca`, `b09536f86247399c0142e171ad4dd28f4d89789806d9561bf27d7c9b3bbca66f` |
| 6 | V03.A20 (T08.A46, A47 S3) | CI `ci-aarch64` (`rc-ensemble`) | PASS (7/7): N = 440, S = 437, F-FALSE-SUCCESS-CAUGHT 3; none verified outside S3 (worst 0.0968); A33 0; replay 25 of 25 MATCH | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json` | `55c36c3821bb558c9e032f29e6777ffa0a4eca32472946aba57a4b6fadce967f` |
| 6 | (run file, report, replay) | CI `ci-aarch64` | — | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.report.txt`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.replay.txt` | `7c08d9225a4defa64c3c1031caf8960f2bb8064f238b621ca80ed44c0699f719`, `dfb7e321250ac41951d2cb186137bf3daf85b5bc2bee6fef76af9b66c1b70045`, `56e6935ed5f3786c3c27e51bd0453fa6cea4131e235924333525b9995e26d550` |
| 7 | V03.A20 (T08.A47, A48) | local `ref-x86-64` | PASS (12/12): A47 T06.A02–A08, A16, A19, A20; A48 T06.A47, A50 | `corpus-ref-x86-64.json` | `235f6414fdc8b88dca63b2de7706da81d9364c91769ad2a7bd5dc625f1630e23` |
| 7 | V03.A20 (T08.A47, A48) | CI x86-64 | PASS (12/12): the same | `ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json` | `8841e956462faca7b1874471085e90f775861caa5b7c9883dffee87d26bc8aef` |
| 7 | V03.A20 (T08.A47, A48) | CI aarch64 | PASS (12/12): the same | `ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json` | `1a8e9c08cd239751320ecadd09e81aea481839c7ccffa349bb22c570db1062b7` |
| 8 | V03.A20, A23 (§3.3 chain + G16-b) | local `ref-x86-64` | PASS (8/8): served D_3 (c_3, R-295) `455d01eb…`; strip c_3 → `383b4e2c…`; strip c_2 → `6c4375b4…`; strip c_1 → `171dd768…`; with `v17-c2`'s texts `6d13e13d…`; G16-b 40 of 40 clean | `surface/rc-alpha-surface.json` | `bcdedfca0ab00ce84bf41127d66934df0633607ae3597820e6f7d41760bbea42` |
| 8 | V03.A20, A23 | CI x86-64 | PASS (8/8): the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-latest/surface/rc-alpha-surface.json` | `3afc20c5b7f237e95016fa2bf7f48006d3619078d97a0d33f0244534683f1b3e` |
| 8 | V03.A20, A23 | CI aarch64 | PASS (8/8): the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-24.04-arm/surface/rc-alpha-surface.json` | `3131ea10722a623da3779b9f8e3f5f56a9b3002ce6a3f4fc2c368bc9fafb1ba0` |
| 9 | V03.A20 (T08.A30) | local `ref-x86-64` | PASS ("A30 PASS"): 266 distinct objects, required closure 150, no undispositioned object in the closure | `a30/t08-a30-x86_64.json`, `a30/a30-inventory-x86_64.json`, `a30.log` | `4c80e4c815483d6570196da5dfd332bee4fc11a75f297b996ad74fd14982d4dc`, `5583263b3be0501417740c7e8519c2bae4cb13ee35c113f0e2625e0ac7caf5a8`, `54954f4434754789c8fbd881bf518f364c2c959a4f32af260ab1a83136a5ddfe` |
| 9 | V03.A20 (T08.A30, CI.1) | CI x86-64 | PASS ("A30 PASS"; `rc-steps` success): 266 distinct objects, closure 150 | `ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json`, `ci/rc-steps-ubuntu-latest/a30/a30-inventory-x86_64.json`, `ci/rc-steps-ubuntu-latest/a30.log` | `2b243432bbd36ae15809d15ac2edc45386b564e81454cf04b09d47b17fcd9e2c`, `25a26f942670f1cbe67e2201f57cb996f4fde9e036786abb3fcc0b97cc92bdaa`, `293a1a75a6a3eb32f1c2014bf4d95affaa7af31cbad58b36916254c908c717ff` |
| 9 | V03.A20 (T08.A30, CI.1) | CI aarch64 | PASS ("A30 PASS"; `rc-steps` success): 232 distinct objects | `ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json`, `ci/rc-steps-ubuntu-24.04-arm/a30/a30-inventory-aarch64.json`, `ci/rc-steps-ubuntu-24.04-arm/a30.log` | `ba5964629d5528fecdb5e191adcb689855e0e8568706243f90d32ede80f0644e`, `1002344bdec870eae54e5c9bcf696b98b1edfb7aa97bd8f8586255d6ffc37d04`, `772e57919f51bc53b243126a8b34a7ae86904cb02c00555db465fa3fb02a13f6` |
| 10 | V03.A20 (T08.A34 over steps 2, 6, 8 and 12) | local `ref-x86-64` | PASS (2/2): 77 certificates audited, 0 violations | `certificates-ref-x86-64.json` | `e038faf7151e4dc7fae0a0bcc9b70a63200772781efd120c2160b477ddfc26a6` |
| 10 | (step 12's five kept certificates, R-348) | local | — | `step12/certificates/g12-bundles/m02-g12-0/bundle/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/live/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/replay/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-0/bundle/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-1/bundle/solution-certificate.json` | `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `cc36ff13913c5687d221e6a63de9702a62ec17b717d122bc6e1fca67ea3abc31`, `960079a01f580ab91060f04fd99456ec8e8eff7cdfafec84bd0672e4bb272bb3` |
| 10 | V03.A20 (T08.A34) | CI x86-64 `rc-steps` | PASS (2/2): 0 violations | `ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json` | `b397038b280e2d57f76bf20e0d9da3219381b9fff3fa2819babf25ef79c0fabf` |
| 10 | V03.A20 (T08.A34) | CI aarch64 `rc-steps` | PASS (2/2): 0 violations | `ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `c208a2fc29007ebf320763d51fc1fbd539f70b02ad53af75044dcc81ffa86632` |
| 10 | V03.A20 (T08.A34) | CI x86-64 clean install (step 4) | PASS (2/2): 0 violations | `ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json` | `e5a42121585e0d5dc5c49a6dc1f4942268b2531512a5b074ee227de718145cbc` |
| 10 | V03.A20 (T08.A34) | CI aarch64 clean install (step 4) | PASS (2/2): 0 violations | `ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `59eb2b96567bd2c24174db701241666adb5a10a7cb37e3faa8407fd6f6c88318` |
| 10 | V03.A20 (T08.A34) | CI x86-64 bundle set (step 5) | PASS (2/2): 0 violations | `ci/rc-bundle-set-certificates/rc-certificates.json` | `29df5a4252c139dd9bfe929aa0b1992a204731f91feb33b55e35aab9bb9ccc3e` |
| 11 | V03.A20 (M07a.A40) | local `ref-x86-64`, pinned environments | PASS (3/3): `external_crosscheck.py --check` exit 0 ("external-crosscheck.json matches"); IDAES re-run exit 0, its numbers equal the committed record's (the one differing member `inputs.reference_values_yaml_sha256`) | `step11/rc-step11.json` | `40295b487b0f8269ef3170076eec6b167a6607d6720617d03ef0ebddc6f6a930` |
| 11 | (cross-check output, venvs, IDAES record) | local | — | `step11/external-crosscheck-check.stdout.txt`, `step11/venv-xcheck.freeze.txt`, `step11/idaes-conformance.json`, `step11/venv-idaes.freeze.txt` | `2f92bf5c59207de7c1f4f59e58c59087f73908eea14c14943edeb4499ae88bdc`, `9e6ed701b6fdf58e6488c981fabe732116380ba012dd661cbf85de0b7119db11`, `7e1d41dd0da62c1685c2ea422e7891bb216c2e01bebb2e7ece7de22d4360adb4`, `dfeec96faebeb6bedab5eb1c069df7344282d0002fe92fb191f2c55c73af82c6` |
| 12 | V03.A20 (M07a.A41: M02 G10, G11, G12) | local `ref-x86-64`, reactor environment from `C`'s lock, one thread | PASS (6/6): environment built and verified; G10v3 (A42 1.56e-08), G11v3 and G12 as M02's manifest judges them; M02 tests with the reactor 570 passed | `step12/rc-step12.json` | `ea7dd46d6578d8eb22208f7eef6a62d28f6d708fd08434fdf5ddf4e9196b61ab` |
| 12 | (G10, G11, G11's runs, G12, G12 edges, M02 tests, environment, host) | local | — | `step12/g10-adapter-halves-v3.json`, `step12/g11-coverage-v3.json`, `step12/g11-coverage-v3.runs.json`, `step12/g12-real-loop-v3.json`, `step12/g12-real-loop-v3-edges.json`, `step12/m02-tests.junit.xml`, `step12/env-manifest.json`, `step12/host.txt` | `4c62053528a19cf3da2f1448e56891be90e4e9b39621e8a58a2a4496999aaeb0`, `3dc7a82489fe91fa106fff9d17c3c529c96b4e83e4a3a08a466875daacf3ca1e`, `cdb7d9993327cd48543212c37063421fa9c82232dd05b356e1609335fce6fd0a`, `0ffef45fabb036b94de667781379a4e037e13310cef0c089a4083fbba86cab85`, `9b1450486028d41b30b9fba89b88355318ab991a652adb5478b63a427bf0b3fd`, `77dd0b9f2a3fa95bd97746b9f116a5ebe400ea5e48014c458b0ddc1b91394b93`, `9ee50c43f06aa1609e0de7839f8b3f046257be81dadcef7fe41f908a9236781d`, `e16fbc528be18e6159a07517d77f08465833a1309555a910f90badee77a36f83` |
| 12 | V03.A34 (W21 (e); R-375, R-909): G11's experiment results kept and audited | local `ref-x86-64`, reactor environment from `C`'s lock, one thread; the audit over the committed records | PASS (3/3): G11 re-run at `C` with step 12's command through `tools/g11keep.py.txt` (`tools/run_g11keep.sh`, exit 0, 1758 s; worktree clean before and after); `tools/g11collect.py.txt`: 2 runs, 121 points each, 105 boundary points each with one experiment, 16 direct points without a store; (b) the re-run's runs file equals step 12's own (`cdb7d999…`, committed before the re-run) in `stage`, `accepted`, `child_accepted`, `tube_outlet`, `path` and `attempts` at all 242 point-runs, 0 differences; (c) `scripts/m07_g11_experiments_audit.py --runs` step 12's own runs file: 210 results, 210 attempts, 0 without a result, 32 direct points, 6 items + schema 0 problems (context `job_id` 420, not judged) | `step12/experiments/rc-step12-experiments.json`, `step12/experiments/g11-experiments-run1.json`, `step12/experiments/g11-experiments-run2.json`, `step12/experiments/g11-experiments-audit.json`, `step12/experiments/g11-coverage-v3.json`, `step12/experiments/g11-coverage-v3.runs.json` | `c8e9be634eaa2fed1a7ddffb5560ccadc1c4129e2e2215a3b90869936fa278e7`, `ba6f7b1fd0524819b6fbad82f299ca1d9ae93a0e9973fc3835ad166ca8a2c13b`, `11fcb6fc8ca3525bb2da49bcb28fe852e12e561a1fd83c4035884c982b469031`, `e36eb2fc00644d1ba438053cd4460471c467c47b1298d99b6984870f72537a20`, `410b0ec2d6611288d97d9b3a0514a509d324d061b04039d044b2382b450f7ecf`, `cf7ed7415a6a4e805592743a069e5957877131fbe435c75018b0119088cacab8` |
| 13 | V03.A20 (W23) | local, project venv | PASS (3/3): `m04_reference.py --check` exit 0 ("11943 claims passed"); `m04_schema_fixtures.py` exit 0; `tests/test_m04_*.py tests/test_evidence_manifests.py` 677 passed | `step13/rc-step13.json`, `step13/m04-tests.junit.xml`, `step13/step13-generator.log`, `step13/step13-fixtures.log` | `66e42cb4c5c512d461613b753f07dd862d33c9c360ce3d78975cf958aeb5de57`, `4ef2fec9e6087eca8bba3528e2f6108ed029f991955b6af39852f212bb59da4f`, `79ede8007aecc79c0dd022320685167fb2b25eed027b41da988cb3b956ece2d9`, `b8499736719c5672cb41e371010ec5397285afd30e282435edd8629575610812` |
| 14 | V03.A20, A33 (W24) | local, m05's audited `nlp` environment, clean worktree at `C` | PASS (5/5): `m03_nlp_check.sh` over the 13 `mark.nlp` modules 190 passed, inventory `--check` exit 0 for both workloads; `-m nlp` collects the same 190 node ids over those modules as over `tests/`; M03/M05 all tiers 640 passed, 2 skipped; `m05_wo9_real.py --replay` "REPLAY PASS REAL differences=0"; `m03_reference.py --check` exit 0 | `step14/rc-step14.json`, `step14/nlp-modules.txt`, `step14/nlp.junit.xml`, `step14/step14-nlp-check.log`, `step14/step14-nlp-collect-selected.log`, `step14/step14-nlp-collect-all.log`, `step14/m03-m05-tests.junit.xml`, `step14/step14-m05-real-replay.log`, `step14/step14-m03-reference.log` | `48dc8119960cc5534c923223b5c1ad116738f513213fdea4bebba3a1307a3fdf`, `8a9e5c2018a9910f32c539e175c91f5bd041e870ce9c6eab3266416c812750d9`, `0ff194c01eb4f76cee26b74c6a3769c194cffb8b6d82a2e5b258203539759835`, `50d8b3b1db43c47bd5eb2b660e01c472b3339a99d96cf4e33b5bfa8ed322a5fc`, `9f5c9c15aded47af92f54ae2525d81875bd7abf89435d4f97ffefbfe2f2d65a5`, `d7f73402941802bb4650ea6a5e9121d389e9c59a0f26cceebbf4d63613c2b383`, `156ff438509b4bc80cb2163097643679f93af03878ea6bd6b5d9910c94ff1d39`, `a29d81b43d687481bb36dd836ee930d72cf332ce19483f87821baf220d632d96`, `63ff10839a608402bba46c0e06dba02dbc4962627dd12960a2f6fab195484e25` |
| 15 | V03.A21 (W25) | local; `check` and `replay` in the `nlp` environment | PASS (3/3): "RC step 15: the journey at 2d945b5d carried"; `check: ACCEPT`; `replay: bitwise` | `step15/rc-step15.json`, `step15/step15-carry.log`, `step15/step15-check.log`, `step15/step15-replay.log` | `091f0cc2d98b03b66beab84f77125f4c595a68a438b2a7bdab679ddaf2b322db`, `1862c97ce57ae6f7a35c2b4581a052f3151a8f5831d37c5f065b4666cf0053b7`, `de6d88adc7ca89239a8bde0b11e8f2543f1ed2becf7bae8b52d55c514d72a008`, `1a92b6e87cef30245145bc4da7f207f42f830417594f9226412ac6b78f59553f` |
| 16 | W26 (V03.A20, A32) | local `ref-x86-64` | PASS (4/4): `tests/test_m06_*.py` with `OPENFLOWSHEET_REQUIRE_BROWSER=1` 662 passed, 0 skipped; `node --test` 92 of 92; G15's 20 registered states, W27-A23, A79b and the two G14 nodes passed (25 of 25); W27 v1 dry run refuses as registered (W27-R63; G14 not judged at 0.3.0, §3.5) | `step16/rc-step16.json`, `step16/m06-tests.junit.xml`, `step16/step16-node.log`, `step16/step16-dryrun.log` | `e895654f4ace065a91c78a2d83cba5cf7ff7a199bff8c172ff207f2c4cc3ace0`, `af34d2cbebc6d6b9e58eba1f98b012c2114fe75feeeb19656a14c1412645737a`, `2981348113c591400444d2c7688a401d57c99ca7241ae7f6dbbe5df240c109ec`, `7f3a737b60e9b0bb840095c8a758d4fc9a55ec930d10b5d3af11a4c1606a6e58` |
| 16 | W26, the browser test (V03.A20) | CI x86-64 `check (ubuntu-latest)` | success: the job runs `tests/test_m06_*.py` with `OPENFLOWSHEET_REQUIRE_BROWSER=1` (the step-1 log above) | `ci/job-logs/check-ubuntu-latest.log` (step 1's record) | — (cited once, on step 1's row) |
| 17 | V03.A22 (17a, E01 G10) | local | PASS (1/1): `a48_release_check()` returns `pass`, 0 unverified primary ranges | `step17/rc-step17a.json` | `c119c9b224d3b244383e27b7687fce7ffbd83ebcb68488d2db51169b64aa147b` |
| 17 | V03.A22 (17b, S07 F-8) | local, main lock then `requirements-coolprop.lock` | PASS (1/1): every S07 and S11 module importing CoolProp: 4174 passed, 0 skipped | `step17/rc-step17b.json`, `step17/17b.junit.xml`, `step17/17b-modules.txt` | `ac3d6ce9a4695109280c0497800223832487cc09c4e6266404d75bb19fb13d77`, `c0a143af3a70bdf2126fd79f05cd97bb19cfd166a409ed8ae8535bcf23815481`, `1d2a5e3a94db7f6a93a8db848ec1625a1f41605382567761da189114b32f5a1d` |
| 17 | V03.A22 (17b, S07 F-8) | CI x86-64 `rc-coolprop` | success: 4174 passed, 0 skipped | `ci/rc-coolprop-ubuntu-latest/17b-ubuntu-latest.log`, `ci/rc-coolprop-ubuntu-latest/modules-ubuntu-latest.txt` | `a715a9063baf05af99044bbd0bd76f3f0766598391e7df2fe128311c61ac5306`, `1d2a5e3a94db7f6a93a8db848ec1625a1f41605382567761da189114b32f5a1d` |
| 17 | V03.A22 (17b, S07 F-8) | CI aarch64 `rc-coolprop` | success: 4173 passed, 1 skipped, the registered A31b skip (`tests/test_s07_registration.py:242`, aarch64 only) | `ci/rc-coolprop-ubuntu-24.04-arm/17b-ubuntu-24.04-arm.log`, `ci/rc-coolprop-ubuntu-24.04-arm/modules-ubuntu-24.04-arm.txt` | `4f5acb8345687089dae845e17896827fda423d7f7d19b313cb57d2dd02c29da4`, `1d2a5e3a94db7f6a93a8db848ec1625a1f41605382567761da189114b32f5a1d` |
| 17 | V03.A22 (17c, MR-12 v03) | local | PASS (3/3): `new_since_v0_2_0 == ["coolprop", "lca"]`, each entry's check `pass` at `C` | `step17/rc-step17c.json`, `step17/17c-coolprop-inventory.json` | `554f55f9834c8e24e62d6c4403d4a5151f3442cffddd8bd54391c62a02ea47d5`, `287938e7f6b8bb55e8eb3d30da953ab4d4890502409754846a2965348c2f60a8` |
| 17 | V03.A22 (17d, E01 G5 A24, A25; G6 A33–A36) | local, the `lca` and audited `nlp` environments | PASS (8/8): `lca` 44 passed; `nlp` 27 passed; 0 skipped | `step17/rc-step17d.json`, `step17/17d-lca.junit.xml`, `step17/17d-nlp.junit.xml` | `df619f74fe1f8bb129f2f0d8dd62c4b625ae96e74370ea8c62759beb1ad745b4`, `9895952ca4da3361ae10e5d7f06145fe36694407bbc7b752ac46184d9126fc28`, `ef005e5541fb211deb99a0d20bdb347d34f04ef8814be496841b39c18643fec1` |
| 17 | V03.A22, A17, A19 (17e) | local, fresh venv from the wheel | PASS (11/11): the wheel from `C` (T08.A43); the ship set and E01's data once each with the repository SHA-256, no repository-only file (A17); A19 (a)–(d) in a fresh venv | `step17/rc-step17e.json`, `step17/dist/t08-a43-dist.json`, `step17/a19-installed.json`, `step17/a19-checkout.json` | `338c094293864dd94ccbdb512b23e4302d62002c1bbbc073ec4d6bb31450f033`, `97d466f37ecc95f00970437901c5b49e4d7cb73751cc1c5a9108bf9fb358ed09`, `2a7dc4a48fb14a727126b56ec6b197941a78a00242250bb64e123e06e618e6f3`, `f316359925292eea80015da733a11c366d4525882cc2cf0f21134d9e16b25953` |

**Provenance.** Every `t08-rc-v1` record above (local and CI) carries `commit` = `a3e508e3…` and
`tree_clean = true`; the A30 records carry the lock and the host but no `commit` (format `t08-a30-inventory-v1`);
M01's and M02's own records (steps 11, 12) carry neither and are cited through the step's `t08-rc-v1` record. Stated,
not judged.

**V03.A24's numbers (CI at `C`).** S07 A31: x86-64 bit-identical; aarch64 within spec §20 (class T worst ratio
5.658e-11 of 1e-10, class N worst 0.0183 of its allowance, 10818 of 22946 rows differ). S11 thermal check: x86-64
bitwise; aarch64 classed, worst |delta|/bound energy 2.855e-03, entropy 2.380e-03, unit 5.920e-04, relative 1.463e-03
(≤ 0.1, R-845's watch), flash 2.403e-02 (0.024 at the S11 merge). THM-09/4's six lines (both runs) are in
`docs/t07-measurements.md` (R-796): ci-x86-64 94, ci-aarch64 136.

## Step 18

`scripts/v0_3_gate.py --rc C` (V03.A27) is run for its YES line only after the verdicts and the ledger (WO-8). It has
not been run; it is pending, not failed.

## Failures

None. Every record of steps 1–17 reports `PASS` or `success`.

## Observations (not failures, not judged)

- **O1** The `check` skip counts are 107 on both architectures; the skip lines are in `step1-skips/` (R-376).
- **O2** Step 6's class counts on `ref-x86-64` and `ci-aarch64` are 437 SUCCESS and 3 F-FALSE-SUCCESS-CAUGHT each;
  0.2.0's were 434 with 3 and 3 (ref) and 4 and 2 (aarch64). The gate (S ≥ 418) reads the counts, not their equality.
- **O3** The A30 summary counts 266 distinct objects on x86-64 (232 on aarch64) while its log line counts 381 objects
  in 8 compiled distributions, as at 0.2.0 (its O2); A30's verdict reads the closure (150), not these counts.
- **O4** The dry run's refusal (step 16, A32 (d)) and the collection over `tests/` exiting 2 (step 14, A33) are the
  two non-zero exits of the local run, each registered by Amendment 2; neither is a failed step.
