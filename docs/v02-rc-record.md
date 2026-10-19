# V02 — the release-candidate record at `C`

*`C` here is the re-cut candidate `C′` (M07 spec Amendment 7 §24.6, R-484). The superseded candidate `c899c85` has
no RC record; its account is `docs/design/M07-build-decisions.md` J56–J66 and its small-text records are kept under
`evidence/M07/c899c85ab43fb114cd85c69baf12e692b75a8eab/rc/` (RC.3).*

M07 spec §8 and §24.7 action 7 (WO-8c), in the V02 alpha release spec §8.3's form (`docs/t08-rc-record.md`'s). This
record **reports**; it judges no gate. Each Result cell states what the step's record or CI job says, in the closed
vocabulary `scripts/v0_2_gate.py` reads through `v0_1_gate.py`'s grammar (Ruling 3: `PASS` / `success`; `FAIL` /
`failure` / `skipped` / not measured); the verdicts are the design lane's. Every record the per-step table cites is
committed under `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/rc/` at the same relative path (a record over
1 MB gzip-compressed beside it), and `rc/records.json` lists all 92 with sha256, size and how each is kept (the two
ensemble run files and step 17's three carry and coverage documents gzip-compressed). The scripts that ran the local
steps are committed beside them, under `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/tools/` (byte-identical
to what ran; the Python ones with a `.txt` suffix so that the linters of `check.sh` do not read them).

## The candidate and the runs

- **`C` = `ce993651ce37c1343e771b276160bd6623e43500`** (`C′`, "M07 (WO-8c, action 6, C′): build log J67-J72 —
  Amendment 7 actions 1-5 done; this commit is the re-cut C′"). Package `openflowsheet` `0.2.0`. RC.1: `c899c85` is
  its ancestor, and `git diff --name-only c899c85 C′ -- src benchmarks schemas requirements.lock pyproject.toml` is
  empty; the journey's cut commit K = `2c508b5` stays (§24.6). Its tree record is
  `release/rc-trees/ce993651ce37c1343e771b276160bd6623e43500.json` (M07a.A44).
- **CI dispatch run 39291243747** (`workflow_dispatch`, `rc_alpha=true`, `rc_distribution=true`, head `C`, ref
  `wp/M07-rc-ce99365`): conclusion **success**. **CI push runs** at `C`: 39276061202 (`wp/M07`) and 39291243653
  (`wp/M07-rc-ce99365`), both **success**.
- **Local steps** on `ref-x86-64` (AMD Ryzen Threadripper PRO 5965WX, Linux 6.12.111+deb13-amd64, Python 3.13.5),
  run 2026-10-19 19:06 to 20:40 from a detached worktree at `C` (`.claude/worktrees/rc-ce99365`, clean throughout:
  `git status --porcelain` empty at the start, after the venv, after the W27 archive's hard links and at the end) in
  a fresh venv of `requirements.lock` with the worktree installed editable (`--no-deps`); threads pinned
  (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`). Steps 2 and 6–17 ran in one session from one script,
  `tools/run_local.sh` (WO-8b's at `c899c85`, with two changes: step 12's G11 takes `--d78` from the registered
  extract and no `--previous-runs`, §24.3 action 2; step 14 is `tools/run_step14.sh`), with every environment built
  afresh and logs under `~/.cache/of-rc-ce99365/`; its one-line-per-command summary is `tools/run_local.summary.txt`
  (50 commands, every exit 0) and the durations in seconds `tools/durations.txt`. `tools/fetch_ci.sh` downloaded the
  dispatch run's artifacts and job logs; `tools/collect.sh` copied the cited records here and
  `tools/make_record.py.txt` wrote this table's hashes from `rc/records.json`.
- **Step 12** ran in the reactor environment built from `C`'s `src/openflowsheet/adapters/pymrm/reactor-env.lock`
  (`build`, then `verify`: verified) under an external root outside every repository; the G12 runs through
  `tools/g12keep.py.txt`, which keeps the script's scratch directories so that step 10 can audit their certificates
  (R-348). The five kept `solution-certificate.json` files are committed under
  `rc/step12/certificates/<kept bundle path>/`. G11 took 2988 s. The host may have been shared with other sessions'
  work; G11v3's timings are recorded under whatever load there was.
- **Step 14** ran in a second clean detached worktree at `C` (`~/.cache/of-rc-ce99365/nlp-wt`, no install into it),
  every command under `env -i` with only the variables `scripts/m03_nlp_check.sh` and M05's manifest set
  (`OMP_NUM_THREADS=1`, `PYTHONNOUSERSITE=1`, `PYOMO_CONFIG_DIR`), in m05's audited `.venv-nlp`;
  `tests/test_m03_reference.py` is not in its test list (it needs `mpmath`, the project environment's, where
  `m03_reference.py --check` runs; J60).
- **Steps 11–17's records** `stepNN/rc-stepNN.json` are written by `tools/m07_rc_external.py.txt` through
  `t08_rc.finish` from the steps' own records, logs and exit codes.
- **Step 1's skip lines** (R-376): `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/step1-skips/ci-x86-64.txt`
  (68 lines, 106 skips) and `…/step1-skips/ci-aarch64.txt` (71 lines, 105 skips), outside `rc/`; they are not RC
  records.

### Jobs of run 39291243747

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — `check.sh: PASSED`; pytest 9911 passed, 106 skipped; the browser test required | 1, 16 |
| `check (ubuntu-24.04-arm)` | success — `check.sh: PASSED`; pytest 9882 passed, 105 skipped | 1 |
| `default-install` | success | — |
| `identity` | success — "G05: R0 structural identity equal across 2 platforms" | 2 |
| `dist` | success | 3 |
| `clean-install (ubuntu-latest)` | success | 4, 10 |
| `clean-install (ubuntu-24.04-arm)` | success | 4, 10 |
| `bundle-set` | success | 5, 10 |
| `bundle-replay (ubuntu-latest)` | success | 5 |
| `bundle-replay (ubuntu-24.04-arm)` | success | 5 |
| `rc-ensemble` (ubuntu-24.04-arm) | success | 6 |
| `rc-steps (ubuntu-latest)` | success; `a30.log` ends `a30 exit status 0` (CI.1) | 2, 7–10 |
| `rc-steps (ubuntu-24.04-arm)` | success; `a30.log` ends `a30 exit status 0` (CI.1) | 2, 7–10 |
| `ensemble`, `ptc-r1`, `ensemble-compare`, `a89-repeats`, `a30-inventory` | skipped (not RC inputs) | — |

All artifacts downloaded (`gh run download 39291243747`); the RC jobs' logs saved under `…/artifacts/rc/ci/job-logs/`
(the `check` and `identity` logs cited below).

## Per step

Paths are relative to `evidence/M07/ce993651ce37c1343e771b276160bd6623e43500/artifacts/rc/` (and, committed, to
`…/rc/`).

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
| 1 | T08.A41 (M07a.A30) | CI x86-64 | success (`check.sh: PASSED`; ruff check, ruff format, mypy, pytest exit 0; 9911 passed, 106 skipped, 192 deselected); `tests/test_m07_ledger.py` 1 passed and 4 skipped, each naming `docs/reviews/V02-verdicts.md` (§23.2) | `ci/job-logs/check-ubuntu-latest.log` | `dbc50ef7a92c1aac0997eae790c1d65c32f7bab090fc488c5efe78a24267b5a9` |
| 1 | T08.A41 (M07a.A30) | CI aarch64 | success (`check.sh: PASSED`; 9882 passed, 105 skipped, 192 deselected); the ledger's four skips the same | `ci/job-logs/check-ubuntu-24.04-arm.log` | `5a34a55f08af189219d5e29f2651d60006d94260a616c6ae6050eb657f788e40` |
| 2 | T08.A42 (M07a.A31) | local `ref-x86-64` | PASS (3/3): minus-t07 `24af004a…`, t07 key `887a2e62…` as registered (R-149); unchanged under the trial version `0.1.0` | `identity/rc-identity.json` | `ab85ee1325e2ae0d78892f1974d4350db26bc826faef61bf1cf7e05bfd30abd5` |
| 2 | T08.A42 (M07a.A31) | CI `ci-x86-64` (`rc-steps`) | PASS (3/3); the same digests | `ci/rc-steps-ubuntu-latest/identity/rc-identity.json` | `4786d9f34f51851f7e151dd4ed8e2016e206cfcdaba3cb5680f02e2cf4fd51d2` |
| 2 | T08.A42 (M07a.A31) | CI `ci-aarch64` (`rc-steps`) | PASS (3/3); the same digests | `ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json` | `c2028812b716be333306df861f848979cf4ca4d9b069307e0f1697ba144a71c3` |
| 2 | T08.A42 (cross-arch, G05) | CI `identity` | success ("G05: R0 structural identity equal across 2 platforms") | `ci/job-logs/identity.log` | `1994c52acd94a314168cba9ee5193c9e877ad242034814f53808bc561be66ecc` |
| 3 | T08.A43 (+A31 checks; M07a.A32) | CI `dist` | PASS (8/8); `a43.version` `0.2.0` from `__version__`, `pyproject`, the sdist and the wheel METADATA; wheel bytes equal across the two builds, sdist archive bytes differ with no differing member | `ci/rc-dist/t08-a43-dist.json` | `73d04ead30c568ec295bb861faaa4b0d76c8d03c4c0ad2d038eacedc4277fb73` |
| 4 | T08.A44 (M07a.A33) | CI x86-64 clean env | PASS (10/10); wheel `0.2.0`; CasADi = A30 digest `4be1571e…` and P03 per-file (2376 files); smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-latest/install-ubuntu-latest.json` | `f10cc09cfff5314dcddd18a7b5fdb16b93668fa175f26ce94312a9fcd83e8857` |
| 4 | T08.A44 (M07a.A33) | CI aarch64 clean env | PASS (9/9); wheel `0.2.0`; CasADi = A30 digest `7a243303…`; smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json` | `53f4c29f2f5eff43b52a32b74d11ef792987c985063b804d794e5e827c4a0704` |
| 4 | T08.A19 (b, c) | CI x86-64, `--state installed` | PASS (4/4) | `ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json` | `d34bdeae39e10abce8d83df5cd7db5253373eb8c0a949b7cb4fc3b01771320d6` |
| 4 | T08.A19 (a, c) | CI x86-64, `--state checkout` | PASS (4/4); lock `ead4edf1…` | `ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json` | `c32273c45cde1c039436e45b6a6d38a429f82a98278be53a9522bb776aa0b22c` |
| 4 | T08.A19 (b, c) | CI aarch64, `--state installed` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json` | `307f8f8adbebf854ef1cb152f829164d0957495d31891ef914dde4ba0ae85704` |
| 4 | T08.A19 (a, c) | CI aarch64, `--state checkout` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json` | `60d6e243db95f2c1cbef94e6e2cfec73ce150333140eb1b97b5b1d4aca39c203` |
| 5 | T08.A45 write (M07a.A34) | CI x86-64 `bundle-set` | success (job conclusion; the index carries no check list): `n_b` 52 (k05 5, g8 47), every entry exit 0; 49 CONVERGED, 3 g8 runs with other registered outcomes (O3) | `ci/rc-bundles/index.json` | `0ffce33f51c2bd654469f90584f44b167615baffa67b27d1a8103fd837ae226c` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI fresh x86-64 | PASS (8/8): same commit; `N_b` 52 = enumeration; every bundle `MATCH`, modes `exact_replay` 52; policy `T08-numerical-policy-v2` (52); C1, C2 `MISMATCH` and C3 `MATCH` as expected; sets k05 5, g8 47 | `ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json` | `6bbad4006bd25ea2ee2560084fb5ea4a34f5cf996d8824f8bc3186d21b1894bc` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI aarch64 | PASS (8/8): every bundle `MATCH`, modes `compatible_reproduction` 52; policy `T08-numerical-policy-v2` (52); C1, C2 `MISMATCH` and C3 `MATCH` as expected; sets k05 5, g8 47 | `ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json` | `7d22adffa8108259543e081dfa0c4f691a809766420d87f5dc9dd2e0fff1124b` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | local `ref-x86-64` | PASS (7/7): N = 440, S = 434, F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3, no F-CRASH or F-OTHER-ROOT; gate S ≥ 418; none verified outside S3 (worst success ratio 0.0968); A33 0; T06 A34 same-class replay 28 of 28 MATCH; registered runs untouched | `ensemble/rc-ensemble-ref-x86-64.json` | `84d580c4472c32df14aa345bbfd365c2cc2695e343b2ddc861b33ca95fd50a37` |
| 6 | (run file, report, replay) | local | — | `ensemble/rc-ref-x86-64.json`, `ensemble/rc-ref-x86-64.report.txt`, `ensemble/rc-ref-x86-64.replay.txt` | `26a3108885cafa568fe893c3dc98eb09db22f90e7d3133853f5b8c93726b22f0`, `52f241cf642cd6c1fc2f957588ab0dec54486c09859b92f831a9baaa2e511884`, `a44aa173a88802666cf2aacb8afa26340f96ed30337615ab25ed63d01d00ed17` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | CI `ci-aarch64` | PASS (7/7): N = 440, S = 434, F-BUDGET 4, F-FALSE-SUCCESS-CAUGHT 2, no F-CRASH or F-OTHER-ROOT; none verified outside S3 (worst 0.0968); A33 0; replay 28 of 28 MATCH | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json` | `ef370934a911e6ab1c8f96ec697163759dbfc4bb7476d737bef2a38042fedfad` |
| 6 | (run file, report, replay) | CI `ci-aarch64` | — | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.report.txt`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.replay.txt` | `375be926627bb7a3d3871c144380a43ad88e4b3c6c0d5b0b9e3261ebb582309f`, `bbcb013b18a81d7663a560c308d8994e76941e4ed96cd26a8c5f12b57d8e6cec`, `5a110a9329a5125913b9788b16abb0e829ee545bf5401ec407eae0df5243c6b4` |
| 7 | T08.A47, A48 (M07a.A36) | local `ref-x86-64` | PASS (12/12): A47 T06.A02–A08, A16, A19, A20; A48 T06.A47, A50; 165 nodes passed, none missing or skipped | `corpus-ref-x86-64.json` | `fb08330d1298629dff51dcddc39dc9aaefc9d1c382b5798c600f96cc6b775ccc` |
| 7 | T08.A47, A48 (M07a.A36) | CI x86-64 | PASS (12/12) | `ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json` | `9400dd00ac067e2edc9754247a90671130da177d77fde2aed01581c4ca08e06a` |
| 7 | T08.A47, A48 (M07a.A36) | CI aarch64 | PASS (12/12) | `ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json` | `cd022aae5c1c77c6021d459b5ef5646696c128bf87cbbf1b87fc9f96720d92ec` |
| 8 | §5.3 chain + G16-b (M07a.A37) | local `ref-x86-64` | PASS (8/8): c_3 (R-295) `455d01eb…`; served `383b4e2c…` = `D_2`; strip c_2 → `6c4375b4…` = `D_1`; strip c_1 → `171dd768…` = `D_0`; with `v17-c2`'s texts `6d13e13d…` (R-137); the tools and their description files; G16-b 40 of 40 clean; records attributable | `surface/rc-alpha-surface.json` | `cfd0e3c937922677c7241de888dae24957626c95f5720cbbc800cf4118f8c2e8` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI x86-64 | PASS (8/8); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-latest/surface/rc-alpha-surface.json` | `59bfeb86cf39427c05efe8a540fefbf4b71139ebcd104aac14fe20afd6be3b02` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI aarch64 | PASS (8/8); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-24.04-arm/surface/rc-alpha-surface.json` | `14af9fa93cd347be73d5601d9c684b456497ecab31b70acb10c9234cdab44268` |
| 9 | T08.A30 (M07a.A38; §24.1 S9.1–S9.4) | local `ref-x86-64` | PASS ("A30 PASS"): over the default install and `server`; 266 distinct objects, required closure 150, no undispositioned object in the closure, METIS not reached (S9.1); `modules_walked` 182, `modules_imported` 179, `solve_exit` 0 (S9.3); `nlp_extra_modules` `openflowsheet.studies.nlp.greybox` → `cyipopt`, `openflowsheet.studies.trust_region.projection` → `pyomo`, `openflowsheet.studies.trust_region.trf` → `pyomo` (S9.2). These three `nlp`-extra modules are outside A30's scope by MR-12 and are covered by step 14's inventory check and R-450: `mr12_extras_v02` at `C` gives pass, new extras `["nlp"]`, audit and inventory present, step 14's `a60.w24.nlp_tier_and_inventory` pass at `C`, R-450 in the register (S9.4) | `a30/a30-inventory-x86_64.json`, `a30/t08-a30-x86_64.json`, `a30.log` | `7bfd29222588cd8b095e56db538cdacc11a0100391c8052784efc8f1ff812696`, `b1548aff5789654be3422a6da499ab5021f22432a4c4a07c54afb3183953ae7d`, `773efd494673f7d02b24c0f5cf304da1472774cc84cbfb976c09fc9a1b374727` |
| 9 | T08.A30 (M07a.A38; S9.1–S9.3, CI.1) | CI x86-64 | PASS ("A30 PASS"; `a30.log` ends `a30 exit status 0`, `rc-steps` success): 266 distinct objects, closure 150; 182 walked, 179 imported, solve exit 0; the same three `nlp_extra_modules` | `ci/rc-steps-ubuntu-latest/a30/a30-inventory-x86_64.json`, `ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json`, `ci/rc-steps-ubuntu-latest/a30.log` | `371e68ac59af50aa1700b6bf7bcdb2f4592c86ac5b0837f904bcb9d4b7582eab`, `9cc64c8291bbb3bba31dd3cfca4c037f98943ff574de917aa579143af7115625`, `a21c2ddbcc8accca44855627d765a633abee5f0e25ad539f6f46f03911ccdf32` |
| 9 | T08.A30 (M07a.A38; S9.1–S9.3, CI.1) | CI aarch64 | PASS ("A30 PASS"; `a30.log` ends `a30 exit status 0`, `rc-steps` success): 232 distinct objects, closure 147; 182 walked, 179 imported, solve exit 0; the same three `nlp_extra_modules` | `ci/rc-steps-ubuntu-24.04-arm/a30/a30-inventory-aarch64.json`, `ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json`, `ci/rc-steps-ubuntu-24.04-arm/a30.log` | `97116de3d9bbfada154dded9e2b2008e6f5c9a6b5327317a8085b88b6de92386`, `69548155caac1edcbd92186258c25f21b0415670606889ccbac6539b9968232b`, `02f33c02740cfc815e59e9ce06c95d0c721fc3cabbe066e0a62ee5968b22e585` |
| 10 | T08.A34 over steps 2, 6, 8 and 12 (MR-11; M07a.A39) | local `ref-x86-64` | PASS (2/2): 77 certificates audited (72 of steps 2, 6, 8 and step 12's five coupled-route certificates), 0 violations | `certificates-ref-x86-64.json` | `2c380fa4fbc7252138c85254e0a717dfb7de6b19e9f1f823900b576ea30ded8b` |
| 10 | (step 12's five kept certificates, R-348) | local | — | `step12/certificates/g12-bundles/m02-g12-0/bundle/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/live/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/replay/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-0/bundle/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-1/bundle/solution-certificate.json` | `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `cc36ff13913c5687d221e6a63de9702a62ec17b717d122bc6e1fca67ea3abc31`, `960079a01f580ab91060f04fd99456ec8e8eff7cdfafec84bd0672e4bb272bb3` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json` | `b5b377ef1af8f06577a3eaa81d4a03128492d75b73f308245fe43985213f699a` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `d01060828ae2886a3fee9690abe0e3ee033d7c201e22544ba28430d830cef24d` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json` | `5b99a355875413441328e32c30eff3dfb46e616c97c129029af63d8fec0733d7` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `aeb319b86c8fd88c135757cf4d2b884253928aa83afc2585ec3974ce25319582` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 bundle set (step 5) | PASS (2/2): 49 audited (of 52 bundles; the 3 unconverged G8 runs carry none), 0 violations | `ci/rc-bundle-set-certificates/rc-certificates.json` | `62eaa950253f2e8bceac057a75bf46f46124ee8f8628f6de328f917c1f4f5c82` |
| 11 | M07a.A40 | local `ref-x86-64`, pinned environments | PASS (3/3): `external_crosscheck.py --check` exit 0 ("external-crosscheck.json matches"); IDAES re-run exit 0; its numbers equal the committed record's, the one differing member `inputs.reference_values_yaml_sha256` | `step11/rc-step11.json` | `f863537df60ea841fa742ac9d14a31fd4a20c7c25444fbb6b7417e0dec6a0ea1` |
| 11 | (cross-check output, venv, IDAES record, venv) | local | — | `step11/external-crosscheck-check.stdout.txt`, `step11/venv-xcheck.freeze.txt`, `step11/idaes-conformance.json`, `step11/venv-idaes.freeze.txt` | `2f92bf5c59207de7c1f4f59e58c59087f73908eea14c14943edeb4499ae88bdc`, `94dfb7fb94245f4aaa8e23724e52f3642db91eb579f6ba904c65eaf0092d1539`, `7e1d41dd0da62c1685c2ea422e7891bb216c2e01bebb2e7ece7de22d4360adb4`, `dfeec96faebeb6bedab5eb1c069df7344282d0002fe92fb191f2c55c73af82c6` |
| 12 | M07a.A41 (M02 G10 (a)–(i), G11 (a)–(d), G12) | local `ref-x86-64`, reactor environment from `C`'s lock, one thread | PASS (6/6): environment built and verified (lock `032a050c…`); G10v3 met — A42 1.56 × 10⁻⁸, A45 3.84 × 10⁻⁸, A46 5.06 × 10⁻⁵, A47 (a) bitwise, (b) 1.43 × 10⁻⁸; G11v3 met (S12.4): G11v3-1, -2, -3, -8, -11 and -12 met, `G11v3-4_selected` `V5`, 121 points per run, 2 runs, all equal; G12 CONVERGED in 4 outer iterations, final k 3, floor ratios 13.3 (T) and 65.3 (ξ); M02 tests with the reactor 570 passed | `step12/rc-step12.json` | `f40268c61a79e2515030b5f8c003b8a3f831789b8e4083202bc962cb2008a93d` |
| 12 | §24.3 action 2 (S12.2, S12.3, S12.5) | local | PASS (S12.2 and S12.3 hold, `tools/s12_check.py.txt`): `--d78` = `docs/derivations/scripts/m07_g11_d78_extract.json`, sha256 `a118c62a50cb998733b171792347b5ff14f43e707a16b07e768ee316e5132bb0`, the registered extract of D78's values, provenance `afa7325a…` (R-480); `d78.variant` = the alpha record's; `--previous` = `bd446ab`'s `g11-coverage-v3.json` (`fa1b0254…`); `--previous-runs` omitted under D100's fallback (generator E4, S12.1): `previous.runs_file` and `previous.runs_sha256` null, `G11v3-11.stage_steps_from` `points`; every `G11v3-3` corner's `d78_stage` (16), `G11v3-5.S1_as_D78`'s keys and `d78_S1_steps` (10) and every `G11v3-8` point's `d78_stage` (8) equal `6fec822`'s step-12 record | `step12/g11-coverage-v3.json`, `step12/d78-extract.sha256`, `step12/archived-inputs.sha256` | `432bf6317046175d370596f8783edc0bde00b1985303f7d90f25d4732cfcc9b2`, `8b64838c09932541d646e0ab0e8f448ce52f96f14057ace38b311e8556fd3f2a`, `3d09a52aefe19c670a7ab3cd534cecbe4b89572c6af4347a01838cdd23f7f562` |
| 12 | (G10, G11 runs, G12, G12 edges, M02 tests, environment, host) | local | — | `step12/g10-adapter-halves-v3.json`, `step12/g11-coverage-v3.runs.json`, `step12/g12-real-loop-v3.json`, `step12/g12-real-loop-v3-edges.json`, `step12/m02-tests.junit.xml`, `step12/env-manifest.json`, `step12/host.txt` | `758ece8d82c928fa201255a6b9f64392d76904af29ef12777ae90229788e1cab`, `9c9dc2f42ba96dd69d6799021925e8102dd59118813f34b0055b451004697c09`, `2cb6449c84be2446f1b368da959abb34d106569ed4b062260733ac795aa3f404`, `4cfbc37b94e197dbf4c40f1b697f2c4f28581b358487af162541f40d40ee58a4`, `c1c4157db6c3f9a5e71597dde490e24a823e6cad006082747a793a79e0642156`, `f8686615d58738234bba500cac5fbd970c8764e37752d0a5919e45f24dfa0872`, `1577d2e733c47b2c4c15205285d5115a34502ea245141e45adfe0d25aafa9a1c` |
| 13 | W23 (M07.A60) | local, project venv | PASS (3/3): `m04_reference.py --check` exit 0 ("11943 claims passed"); `m04_schema_fixtures.py` exit 0; `tests/test_m04_*.py tests/test_evidence_manifests.py` 485 passed | `step13/rc-step13.json`, `step13/m04-tests.junit.xml`, `step13/step13-generator.log`, `step13/step13-fixtures.log` | `3d62ec407561e2805b6c777868aa9e520c656f567375cacbdd8f3d9780351004`, `9ee14bc66cf964c72afd1665ae3d99781e566ffd8656d68881adb7e3c3fda3a6`, `79ede8007aecc79c0dd022320685167fb2b25eed027b41da988cb3b956ece2d9`, `b8499736719c5672cb41e371010ec5397285afd30e282435edd8629575610812` |
| 14 | W24 (M07.A60) | local, m05's audited `nlp` environment, clean worktree at `C` | PASS (4/4): `m03_nlp_check.sh` 186 passed, 1 skipped, inventory `--check` exit 0 for both workloads (NLP-1, Ipopt executable); M03/M05 all tiers 640 passed, 2 skipped; `m05_wo9_real.py --replay` "REPLAY PASS REAL differences=0"; `m03_reference.py --check` exit 0 | `step14/rc-step14.json`, `step14/nlp.junit.xml`, `step14/step14-nlp-check.log`, `step14/m03-m05-tests.junit.xml`, `step14/step14-m05-real-replay.log`, `step14/step14-m03-reference.log` | `11c6e5d6a1eeb3c407b06fa585e8099a2a031ad274690c01de9cca3d57af9747`, `1b0ae70600fb9fa19b67e383922170754a4a646f44ea8b446ac68dad69e1b098`, `ef2cfdf2e67210fdcb92d93ae23d07a0be38654b571756bad1c623b1d7b8f357`, `a47259aad035cfa4968f12030e7d1740d5a0558655eba4d446711314ba59880d`, `a29d81b43d687481bb36dd836ee930d72cf332ce19483f87821baf220d632d96`, `63ff10839a608402bba46c0e06dba02dbc4962627dd12960a2f6fab195484e25` |
| 15 | W25 (M07.A61) | local; `check` and `replay` in the `nlp` environment | PASS (3/3): "RC step 15: the journey at 2c508b5 carried"; `check: ACCEPT`; `replay: bitwise` | `step15/rc-step15.json`, `step15/step15-carry.log`, `step15/step15-check.log`, `step15/step15-replay.log` | `85bd006c9deed2a2fd120e72f30971151101db12de7f1c9acd337426c45af746`, `0dc2047e99f4f4313640939f557c8a8662b44c774d48a4bee63645ed866f522c`, `de6d88adc7ca89239a8bde0b11e8f2543f1ed2becf7bae8b52d55c514d72a008`, `1a92b6e87cef30245145bc4da7f207f42f830417594f9226412ac6b78f59553f` |
| 16 | W26 (M07.A60) | local `ref-x86-64` | PASS (3/3): `tests/test_m06_*.py` with `OPENFLOWSHEET_REQUIRE_BROWSER=1` 661 passed; `node --test` 92 of 92; W27 dry run "A23 PASS (62 records)" | `step16/rc-step16.json`, `step16/m06-tests.junit.xml`, `step16/step16-node.log`, `step16/step16-dryrun.log` | `107b2e5194a4c95e683fe8cbadbb20975a91258772a53140f230a809fb5f38cd`, `fdb43c42a5ac992b4f43063ab917bfbebc80a501722880b36249cdd955af6a70`, `a555dfa5aeaa8e43a77f6fef843ed4232744c4dd75cdfe7bc8b290b183fcee6b`, `62bba25d82aa4fc4fb2c054e91f6c31f418ff00cbbf648c6a95cdfc989de4750` |
| 16 | W26, the browser test (M07.A60) | CI x86-64 `check (ubuntu-latest)` | success: the job runs `tests/test_m06_*.py` with `OPENFLOWSHEET_REQUIRE_BROWSER=1` (the step-1 log above) | `ci/job-logs/check-ubuntu-latest.log` | `dbc50ef7a92c1aac0997eae790c1d65c32f7bab090fc488c5efe78a24267b5a9` |
| 17 | W27 (M07.A62; §22.2 17a–17d) | local, fresh `$S` outside the repository | PASS (4/4): 17a tree `95f9fcf2c6a24084b823746959971fc5e183895a` = the judged record; 17b coverage at `C` exit 0; 17c "RC step 17: the W27 campaign carried" (`at-c.json` = `at-cw.json`, `3c0e08c7…`); 17d precheck and `aggregate` exit 0, `diff -r` empty, `campaign.json` `4812910abb2622b9192c01eae331fa2e97b3f523d78f73510b845c32f20f9e28` | `step17/rc-step17.json`, `step17/step17a-tree.log`, `step17/step17c-carry.log`, `step17/step17d-diff.log`, `step17/step17d-sha256.log` | `3dd1106c7d59b14987c0956dfee6ad5d193c0b5b30acdf3cad0bc99aeb021b4a`, `bea1164824129b54ef0f3ab5ca70d071a61430e016b1a8849cac7aab7e594ca3`, `048ad4260a94b39fc9d0ba97ecc808655b4e91943a9424ac4b00bea4199cb08a`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, `159cd995993b191a0f768fa9c4e8ba9c034ff0a68b9c87e0ff56b3614bb5dc30` |
| 17 | (carry members, coverage at `C`) | local | — | `step17/at-cw.json`, `step17/at-c.json`, `step17/coverage-at-C.json` | `3c0e08c73ade930179bea8b75b30d7adc46080d5859407c3a13e275ce05a9ee5`, `3c0e08c73ade930179bea8b75b30d7adc46080d5859407c3a13e275ce05a9ee5`, `121186c1e43b937af57701b8856ee42784501e8867020bfc05984ca163629fb6` |

**M07a.A43 (provenance).** Every `t08-rc-v1` record above (local and CI, both replay records and the records of steps
11–17 included) carries `commit` = `ce993651…`, `tree_clean = true` and `environment_lock_sha256 = ead4edf1…`;
`t08-a43-dist.json` carries the same at top level. The A30 records carry `lock_sha256` and the host, but no `commit`
or `tree_clean` (format `t08-a30-inventory-v1`); M01's and M02's records (steps 11, 12) carry neither, and are cited
through the step's `t08-rc-v1` record. Stated, not judged.

**J.1** (§24.5): at `C`, in the reactor (`nlp`) environment with `OMP_NUM_THREADS=1`,
`pytest -m pymrm tests/test_m07_journey_record.py -k a24 -rs` gives 1 passed (`2c508b5`) and 1 skipped (`974c395`:
"A24 for 974c395 is judged at its own commit; its carry to this tree does not hold (M07 §24.5, R-483)").

## Step 18

`scripts/v0_2_gate.py --rc C` (M07.A36) is run for its YES line only at a candidate where
`pytest tests/test_m07_ledger.py` gives 5 passed and 0 skipped, after the verdicts (§8, §23.2). It has not been run;
it is pending, not failed.

## Failures

None. Every record of steps 1–17 reports `PASS` or `success`.

## Observations (not failures, not judged)

- **O1** The `check` skip counts differ between the platforms (106 / 105 skipped); the skip lines are in
  `step1-skips/` (R-376). The aarch64 file is byte-identical to `c899c85`'s.
- **O2** The A30 object counts and closures (266 / 150 on x86-64, 232 / 147 on aarch64) are over the default install
  and `server` with the scoped workload (§24.1); the alpha's (381 / 150, 308 / 147) were counted at a tree without
  `studies/` modules. A30's verdict reads the closure, not these counts.
- **O3** The bundle index's three g8 entries that are not CONVERGED have the outcomes their revisions register (2
  initialization, 1 homotopy stall), each with exit 0, as at the alpha (named here, outside the per-step table,
  because the gate script reads any upper-case failure word in a Result cell as a failure).
- **O4** Step 6's class counts equal the alpha's on `ref-x86-64` (434; F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3) and on
  `ci-aarch64` (434; 4, 2).
- **O5** Step 12's G10v3 and G12 values (A42, A45, A46, A47 (b); G12's outer iterations, final k and floor ratios,
  the edges' `y_inert`) equal `cc73219`'s step-12 record exactly; the G12 check differs from it only in record paths,
  hashes and `solve_wall_s` (271.7 s here, 126.7 s there).
