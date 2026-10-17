# Verdict brief: `0.2.0a1` at C_α² — V11–V20, W21, W22 (spec §6.3, Amendment 3 §19.8 action 9)

**Task.** One `verdict` agent judges V11–V20, W21 and W22 at **C_α² = `cc73219a77f6a54579c8acb151ed6fae228c8a4c`**
(branch `wp/V02-alpha-rc2`). C_α¹ (`6fec822`) is superseded by Amendment 3 (R-370: the frozen envelope claimed aarch64 for
the reactor). Worktree `/home/frankp/Codes/OpenFlowsheet/.claude/worktrees/alpha-gate`, branch `wp/V02-alpha-gate`.

**Build on the C_α¹ verdict** `docs/reviews/V02-alpha-verdicts-6fec822.md` (8 PASS; V14 FAIL (b); BLOCKED V13 (e),
V17 (a), W21 (c) on Frank's pending ADR 0028 answers; findings A1–A10). Re-check each gate at C_α², and judge fresh what
changed: C_α² = C_α¹ + §19.1 item 2 (a)–(e) (11 files: envelope L15/platforms axis corrected, L44–L48, U15, M02
limitations[1,2,3,6] P→E, support matrix, gate re-judgement rule + M07a.A14, `-rs` in check.sh, CHANGELOG skeleton +
phrase test, spec/register/generator/YAML of Amendment 3). Apply Amendment 3 (§19: R-370…R-379, incl. A61 naming V13 (e),
R-371's date rule — `Judged` is today; Frank's answers must be dated after it; A2's re-judgement line comes later).
Verdicts that differ from v0.1's (`docs/reviews/T08-verdicts.md`, `67c66d9`) or from C_α¹'s say why.

**Output.** `docs/reviews/V02-alpha-verdicts.md` in the same form as the C_α¹ document (§6.3: header with C_α² 40 hex
and today's date; one `Verdict` table, twelve rows V11…V20, W21, W22; one section per gate judging every clause, its
evidence at C_α², what it does not establish). Never set `reviewed`; never move a tolerance, band or classification rule.
List, for Frank, exactly which of his ADR 0028 answers each BLOCKED/FAIL row waits on.

**Manifest.** `evidence/M07a/cc73219…/manifest.json` is `tested` (R-373): 38 pass, 0 fail, 6 unsupported (A52 per §19.4,
A60–A64 — outputs of this verdict and of action 10).

**Rules.** Read narrowly (grep -n / sed -n); stay under ~150k context. Commit the verdict doc (named path, trailer
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` / `Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv`),
push. Run `scripts/v0_2_gate.py --rc cc73219a77f6a54579c8acb151ed6fae228c8a4c` once to confirm it parses the document and
refuses only for expected reasons. Report ≤ 300 words.

---
## RC record at C_α² (`docs/v02-alpha-rc-record.md`)
## The candidate and the runs

- **`C` = `cc73219a77f6a54579c8acb151ed6fae228c8a4c`** (`C_α²`, "V02 alpha Am3 action 5: cut C_α² — Amendment 3
  action 4, the `## v0.2.0a1` skeleton per §19.5; phrases from the YAML (R-374)"): `C_α¹` = `6fec822` + 6505315,
  162e13b, e892790, 967a622, 7af0ee3 cherry-picked with `-x` (branch `wp/V02-alpha-rc2`, §19.7, B-AM3-6). Its diff
  from `C_α¹` is §19.1 item 2's (a)–(e), 11 files. Package `openflowsheet` `0.2.0a1`. Its tree record is
  `release/rc-trees/cc73219a77f6a54579c8acb151ed6fae228c8a4c.json` (M07a.A44).
- **CI dispatch run 38813135468** (`workflow_dispatch`, `rc_alpha=true`, `rc_distribution=true`, head `C_α`):
  conclusion **success**. **CI push run 38813136015** at `C_α`: conclusion **success**.
- **Local steps** on `ref-x86-64` (AMD Ryzen Threadripper PRO 5965WX, Linux 6.12.111+deb13-amd64, Python 3.13.5),
  run 2026-10-15 23:52 to 2026-10-16 00:44 from a detached worktree at `C_α` (`.claude/worktrees/rc-cc73219`, clean
  throughout: `git status --porcelain` empty at the start, after the venv and at the end) in a fresh venv of
  `requirements.lock` with the worktree installed editable (`--no-deps`), so every child imported `C_α`'s `src/`;
  threads pinned (`OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`). Every local step (2, 6–12) ran in one
  session from one script, `tools/run_local.sh` (`C_α¹`'s, its comments and candidate retargeted), with every
  environment built afresh and logs under `~/.cache/of-rca-cc73219/`; its one-line-per-command summary is
  `tools/run_local.summary.txt` (24 commands, every exit 0). `tools/fetch_ci.sh` downloaded the dispatch run's
  artifacts and job logs; `tools/collect.sh` copied the cited records here.
- **Step 12** ran in the reactor environment built from `C_α`'s `src/openflowsheet/adapters/pymrm/reactor-env.lock`
  (`python -m openflowsheet.adapters.pymrm.env build`, then `verify`: verified) under an external root outside every
  repository; the G12 runs through `tools/g12keep.py.txt`, which keeps the script's scratch directories so that step 10
  can audit their certificates (spec §18.2, R-348; `tools/g12keep.py.txt` sha256
  `f4b136f211de2ea3a50c179362d08cbffae4e8ae0d3b5ea055fdc39c4facfc30`, byte-identical to `C_α¹`'s). The five kept
  `solution-certificate.json` files are committed under `rc/step12/certificates/<kept bundle path>/` (the bundle's own
  `artifacts/` segment left out, B-AM2-9). The host may have been shared with other sessions' work; G11v3's timings are
  recorded under whatever load there was.
- **Steps 11 and 12's records** `step11/rc-step11.json` and `step12/rc-step12.json` are written by
  `tools/m07a_rc_external.py.txt` through `t08_rc.finish` from M01's and M02's own records and the commands' exit codes,
  judged by the M01 and M02 manifests' own rules (B-WO10-8).
- **Step 1's skip lines** (R-376): each CI architecture's `SKIPPED` summary lines are committed at
  `evidence/M07a/cc73219a77f6a54579c8acb151ed6fae228c8a4c/step1-skips/ci-x86-64.txt` (62 lines, 100 skips) and
  `…/step1-skips/ci-aarch64.txt` (64 lines, 98 skips), outside `rc/`; they are not RC records.

### Jobs of run 38813135468

| Job | Conclusion | Step |
| --- | --- | --- |
| `check (ubuntu-latest)` | success — `check.sh: PASSED`; pytest 8533 passed, 100 skipped | 1 |
| `check (ubuntu-24.04-arm)` | success — `check.sh: PASSED`; pytest 8505 passed, 98 skipped | 1 |
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

All twelve artifacts downloaded (`gh run download 38813135468`); the job logs of the RC jobs saved under
`…/artifacts/rc/ci/job-logs/` (the `check` and `identity` logs cited below).

## Per step

Paths are relative to `evidence/M07a/cc73219a77f6a54579c8acb151ed6fae228c8a4c/artifacts/rc/` (and, committed, to
`…/rc/`).

| Step | Assertion | Where | Result (as the record says) | Record | sha256 |
| --- | --- | --- | --- | --- | --- |
| 1 | T08.A41 (M07a.A30) | CI x86-64 | success (`check.sh: PASSED`; ruff check, ruff format, mypy, pytest exit 0; 8533 passed, 100 skipped, 2 deselected) | `ci/job-logs/check-ubuntu-latest.log` | `307983f5a94fcb0135f7d84ac81c535f0a863dc568d5f07b4ba844856d4cb376` |
| 1 | T08.A41 (M07a.A30) | CI aarch64 | success (`check.sh: PASSED`; 8505 passed, 98 skipped, 2 deselected) | `ci/job-logs/check-ubuntu-24.04-arm.log` | `7c1a12b1e2ff1335a2f0fa80a235be921eb336ffa4d96f03ffa230f6d5923b6b` |
| 2 | T08.A42 (M07a.A31) | local `ref-x86-64` | PASS (3/3): minus-t07 `24af004a…`, t07 key `887a2e62…` as registered (R-149); unchanged under the trial version `0.1.0`; whole document `174977cc…`, structural `ed6d11f3…`, T02 floats `9a8a5baf…` | `identity/rc-identity.json` | `ea6f62a17e98c5406b9b873cc1d987ff15e39b980d52198c256c1adee8fd4bb8` |
| 2 | T08.A42 (M07a.A31) | CI `ci-x86-64` (`rc-steps`) | PASS (3/3); the same four digests | `ci/rc-steps-ubuntu-latest/identity/rc-identity.json` | `32d3beeae858d3e21e40397f612c346333df1b66f417bc15f90ea84199bae575` |
| 2 | T08.A42 (M07a.A31) | CI `ci-aarch64` (`rc-steps`) | PASS (3/3); the same four digests | `ci/rc-steps-ubuntu-24.04-arm/identity/rc-identity.json` | `1598a78e7d2d3f72cc2804dde6ca99369b320d7be6d8c64f9701ddaceebe6303` |
| 2 | T08.A42 (cross-arch, G05) | CI `identity` | success ("G05: R0 structural identity equal across 2 platforms") | `ci/job-logs/identity.log` | `0eb539d5968a7d8cf596144649335859b36dfbd96a625d91f9d0d2689e730ec3` |
| 3 | T08.A43 (+A31 checks; M07a.A32) | CI `dist` | PASS (8/8); `a43.version` `0.2.0a1` from `__version__`, `pyproject`, the sdist and the wheel METADATA; wheel bytes equal across the two builds, sdist archive bytes differ with no differing member | `ci/rc-dist/t08-a43-dist.json` | `06bb630af6038038697fe31fda314477ea308bb11f17880894ea5b8999c24cef` |
| 4 | T08.A44 (M07a.A33) | CI x86-64 clean env | PASS (10/10); wheel `0.2.0a1`; CasADi = A30 digest `4be1571e…` and P03 per-file (2376 files); smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-latest/install-ubuntu-latest.json` | `b64bea94644b7b0152b0e9fd30263f3dafb6c2d889d4ad0a3eeda53e0e31a5d5` |
| 4 | T08.A44 (M07a.A33) | CI aarch64 clean env | PASS (9/9); wheel `0.2.0a1`; CasADi = A30 digest `7a243303…`; smoke solve CONVERGED / VERIFIED, 136 checks | `ci/rc-install-ubuntu-24.04-arm/install-ubuntu-24.04-arm.json` | `ace470c3564de5519bbb948f82b4e11bd79b2ed91328232270b89ba043fc3bf9` |
| 4 | T08.A19 (b, c) | CI x86-64, `--state installed` | PASS (4/4); lock sha256 empty beneath a stray lock; replay `inspected_archived_results` | `ci/rc-install-ubuntu-latest/lock-installed-ubuntu-latest.json` | `1f1ce4e0c5e91095535c6a7dc78287020ea14f5c9f8f2bb3179c668a9f98d7c6` |
| 4 | T08.A19 (a, c) | CI x86-64, `--state checkout` | PASS (4/4); lock `ead4edf1…` | `ci/rc-install-ubuntu-latest/lock-checkout-ubuntu-latest.json` | `e90eedda300d653bfc9fb7755609d7c3940449150e9e1d0b8b44f16af8c139ef` |
| 4 | T08.A19 (b, c) | CI aarch64, `--state installed` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-installed-ubuntu-24.04-arm.json` | `89b7584b25c2a344f63e2ba4c5f3a531874352c30bab4c852019404f112d06b0` |
| 4 | T08.A19 (a, c) | CI aarch64, `--state checkout` | PASS (4/4) | `ci/rc-install-ubuntu-24.04-arm/lock-checkout-ubuntu-24.04-arm.json` | `9501b738968b526d969c97e53672883b602fac2b49d040985c911ab639680477` |
| 5 | T08.A45 write (M07a.A34) | CI x86-64 `bundle-set` | success (job conclusion; the index carries no check list): `n_b` 52 (k05 5, g8 47), every entry exit 0; 49 CONVERGED / VERIFIED, 3 g8 runs with other registered outcomes (O3) | `ci/rc-bundles/index.json` | `76166f953b38c9cb07063ccd5b7cb16f583fad17aee8df70127d0d9abd3517d7` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI fresh x86-64 | PASS (8/8): same commit; `N_b` 52 = enumeration; every bundle `MATCH`, modes `exact_replay` 52; every bundle records `T08-numerical-policy-v2` (52); controls C1 and C2 `MISMATCH`, C3 `MATCH`, each as expected; sets k05 5, g8 47; near-threshold none | `ci/rc-replay-ubuntu-latest/replay-ubuntu-latest.json` | `ea0683342dd400e731c3bcde165fabef8318bdd4511e1c8c4dca5f4bc093fefe` |
| 5 | T08.A45 replay, A14 C1–C3 (M07a.A34) | CI aarch64 | PASS (8/8): every bundle `MATCH`, modes `compatible_reproduction` 52; policy `T08-numerical-policy-v2` (52); C1, C2 `MISMATCH` and C3 `MATCH` as expected; sets k05 5, g8 47 | `ci/rc-replay-ubuntu-24.04-arm/replay-ubuntu-24.04-arm.json` | `cbfcd1d786f373a27ac83229407830ef36d65b6973664f805cdf07c64c4ffbce` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | local `ref-x86-64` | PASS (7/7): N = 440, S = 434, F-BUDGET 3, F-FALSE-SUCCESS-CAUGHT 3, no F-CRASH or F-OTHER-ROOT; gate S ≥ 418; none verified outside S3 (worst success ratio 0.0968); A33 0; T06 A34 same-class replay 28 of 28 MATCH; registered runs untouched; one-sided 95 % CP lower bound on S 0.973264 (in the report) | `ensemble/rc-ensemble-ref-x86-64.json` | `ff4a33b9c6fae93e363e74ad1a22e11d954d293dbc57de45562fb2fb3cb10566` |
| 6 | (run file, report, replay) | local | — | `ensemble/rc-ref-x86-64.json`, `ensemble/rc-ref-x86-64.report.txt`, `ensemble/rc-ref-x86-64.replay.txt` | `505e56e86ed2114164400dad658b18020ecb092cd1a2dd1a2869f5155b8719b4`, `b11474cce3e8e6639da72c2b1368bffeebf9e126a2aba232477a172cb02a1604`, `075636e72cb7e2c460f33eaaffaaa50b3854620eb663a5fac6b7337f5a12d5d9` |
| 6 | T08.A46, A47 (S3) (M07a.A35) | CI `ci-aarch64` | PASS (7/7): N = 440, S = 434, F-BUDGET 4, F-FALSE-SUCCESS-CAUGHT 2, no F-CRASH or F-OTHER-ROOT; none verified outside S3 (worst 0.0968); A33 0; replay 28 of 28 MATCH; CP bound in the report | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ensemble-ci-aarch64.json` | `b5df933df002919dd088b2ef9bf6f7bd6ad0a24ac398b1d7025ec49fe6ff2315` |
| 6 | (run file, report, replay) | CI `ci-aarch64` | — | `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.json`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.report.txt`, `ci/rc-ensemble-ubuntu-24.04-arm/rc-ci-aarch64.replay.txt` | `6136320cb42579184c568eba276ae9493649b2ac91dbbbf7018228f683b6dde0`, `c3d8ab9b75d9ff4a68e926ab18ab242907a3fd05c60d50e1a6ba2ba285186211`, `58df70412a8179996811586bf5225f256820145e259dd822376b60314189b9cf` |
| 7 | T08.A47, A48 (M07a.A36) | local `ref-x86-64` | PASS (12/12): A47 T06.A02–A08, A16, A19, A20; A48 T06.A47, A50; 165 nodes passed, none failed, missing or skipped | `corpus-ref-x86-64.json` | `12f54e036cdf394602d5c76f901dfe82607f5237938505d4b370334a1192ef94` |
| 7 | T08.A47, A48 (M07a.A36) | CI x86-64 | PASS (12/12) | `ci/rc-steps-ubuntu-latest/corpus-ubuntu-latest.json` | `bb7a7cbae28f13bb1b396f422326ed1b8b6cd7721619ae47aebe760437442bca` |
| 7 | T08.A47, A48 (M07a.A36) | CI aarch64 | PASS (12/12) | `ci/rc-steps-ubuntu-24.04-arm/corpus-ubuntu-24.04-arm.json` | `a247bd05ae68e562c8d10f8bbc7a50b4ba1a87bec66684a854e7f43068cefbbd` |
| 8 | §5.3 chain + G16-b (M07a.A37) | local `ref-x86-64` | PASS (7/7): served `383b4e2c…` = `D_2`; strip c_2 → `6c4375b4…` = `D_1`; strip c_1 → `171dd768…` = `D_0` (R-133); with `v17-c2`'s texts `6d13e13d…` (R-137); the 17 tools and their description files; G16-b 40 of 40 clean; records attributable | `surface/rc-alpha-surface.json` | `9fd188b7f3cf78adb6c71a2a8f14634942d170bdeeb061a4335295756abbdd7d` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI x86-64 | PASS (7/7); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-latest/surface/rc-alpha-surface.json` | `8f9d9525ac42210ca81a72a6fe8352121def16ec2037ea660b2c46a69a47aeb2` |
| 8 | §5.3 chain + G16-b (M07a.A37) | CI aarch64 | PASS (7/7); the same digests; 40 of 40 clean | `ci/rc-steps-ubuntu-24.04-arm/surface/rc-alpha-surface.json` | `59eb9cebbe34fef37fc81c4c66d040114fd3d698d8227b6043fac6814883c072` |
| 9 | T08.A30 (M07a.A38) | local `ref-x86-64` | PASS ("A30 PASS"): 381 objects in 8 compiled distributions, required closure 150, no undispositioned finding in the closure, METIS not reached (O2) | `a30/a30-inventory-x86_64.json`; summary `a30/t08-a30-x86_64.json` | `a1c0ee461c6554b26def044fb39f7d9c2125733abd687c92e0ecf249528070ac`, `dbd09452c64e3b795b83aad1f3f41f8a64133f80e9a24ed55e221d318896f79e` |
| 9 | T08.A30 (M07a.A38) | CI x86-64 | PASS ("A30 PASS", exit 0): 381 objects, closure 150 | `ci/rc-steps-ubuntu-latest/a30/a30-inventory-x86_64.json`; summary `ci/rc-steps-ubuntu-latest/a30/t08-a30-x86_64.json` | `ba0192107a5aaf3980b84be604bb25ea26e84580268f223a941b92f075aada50`, `dab1651191b07ec1749c88b2369cac4ad5c64b941e2f61528ea0e76d3e796310` |
| 9 | T08.A30 (M07a.A38) | CI aarch64 | PASS ("A30 PASS", exit 0): 308 objects, closure 147 | `ci/rc-steps-ubuntu-24.04-arm/a30/a30-inventory-aarch64.json`; summary `ci/rc-steps-ubuntu-24.04-arm/a30/t08-a30-aarch64.json` | `5fbfe91ea1f7ebb0b8f75b72639d62be66950df6dea4a2697a2f0c88e8d6e1ed`, `b1aa32d66a0c9469d976575d8167c721f6734b5109d252a0f3d828a1c49186d6` |
| 10 | T08.A34 over steps 2, 6, 8 and 12 (MR-11; M07a.A39) | local `ref-x86-64` | PASS (2/2): 77 certificates audited (72 of steps 2, 6, 8 and step 12's five coupled-route certificates), 0 violations | `certificates-ref-x86-64.json` | `a092953b06caa76d8ebf5f74f6a6e3600d765bee63ec180a94995137bab5bbdd` |
| 10 | (step 12's five kept certificates, R-348; the bundle's `document_sha256` `faa8e4da…8974` = the G12 record's `certificate_sha256`) | local | — | `step12/certificates/g12-bundles/m02-g12-0/bundle/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/live/solution-certificate.json`, `step12/certificates/g12-bundles/m02-g12-0/replay/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-0/bundle/solution-certificate.json`, `step12/certificates/g12-edges-bundles/m02-g12v3-2-1/bundle/solution-certificate.json` | `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `faa8e4daa92b582e7392b3ff8f58daca7f2d48e8e6faaf4945a616791fdf8974`, `cc36ff13913c5687d221e6a63de9702a62ec17b717d122bc6e1fca67ea3abc31`, `960079a01f580ab91060f04fd99456ec8e8eff7cdfafec84bd0672e4bb272bb3` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-latest/certificates-ubuntu-latest.json` | `c4a7dce7d354971405f615d3f8e7bf3fc4d59b77e144ea13f44489bf2c52a131` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 `rc-steps` | PASS (2/2): 72 audited, 0 violations | `ci/rc-steps-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `cf12e0b526a0958fad0fb7616fc3a1e685b27a64c017d0e53214ddbd66cfdf8b` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-latest/certificates-ubuntu-latest.json` | `528b08c218a648ce4e9a3cd26cf47a2c8459122fd0aef03a60e74feaf85f9982` |
| 10 | T08.A34 (M07a.A39) | CI aarch64 clean install (step 4) | PASS (2/2): 1 audited, 0 violations | `ci/rc-install-ubuntu-24.04-arm/certificates-ubuntu-24.04-arm.json` | `7596007e8ca8f2519c83ad87df5002c2ab7c0d599224c355f9d3a3e8d3e16bc2` |
| 10 | T08.A34 (M07a.A39) | CI x86-64 bundle set (step 5) | PASS (2/2): 49 audited (of 52 bundles; the 3 unconverged G8 runs carry none), 0 violations | `ci/rc-bundle-set-certificates/rc-certificates.json` | `46cbb5fc1b4e231b7aab533a30c98d92c9da714ee1a7c96f3b24cd7fc6f0959d` |
| 11 | M07a.A40 | local `ref-x86-64`, pinned environments | PASS (3/3): `external_crosscheck.py --check` exit 0 ("external-crosscheck.json matches"); IDAES re-run exit 0; its numbers equal the committed record's, the one differing member `inputs.reference_values_yaml_sha256` | `step11/rc-step11.json` | `b29395527642bbd42c5e2a39a98f384144ee4141167fa2853ad5662d69a6bb67` |
| 11 | (cross-check output, venv, IDAES record, venv) | local | — | `step11/external-crosscheck-check.stdout.txt`, `step11/venv-xcheck.freeze.txt`, `step11/idaes-conformance.json`, `step11/venv-idaes.freeze.txt` | `2f92bf5c59207de7c1f4f59e58c59087f73908eea14c14943edeb4499ae88bdc`, `94dfb7fb94245f4aaa8e23724e52f3642db91eb579f6ba904c65eaf0092d1539`, `7e1d41dd0da62c1685c2ea422e7891bb216c2e01bebb2e7ece7de22d4360adb4`, `dfeec96faebeb6bedab5eb1c069df7344282d0002fe92fb191f2c55c73af82c6` |
| 12 | M07a.A41 (M02 G10 (a)–(i), G11 (a)–(d), G12) | local `ref-x86-64`, reactor environment from `C_α`'s lock, one thread | PASS (6/6): environment built and verified (lock `032a050c…`); G10v3 met — A42 1.56 × 10⁻⁸, A45 3.84 × 10⁻⁸, A46 5.06 × 10⁻⁵, A47 (a) bitwise, (b) 1.43 × 10⁻⁸; G11v3 met, box V5, the two runs of 121 points equal; G12 CONVERGED / VERIFIED in 4 accepted iterates, ρ 0.292, floor ratios 65.3 (ξ) and 13.3 (T), `reproduce` MATCH, live rerun bitwise; edges converged and verified; M02 tests with the reactor 562 passed | `step12/rc-step12.json` | `cc50d97d5866b3cb576478d1ca3888c4f8d085dbd0c944811e80b150d0f072a0` |
| 12 | (G10, G11, G11 runs, G12, G12 edges, M02 tests, environment, host) | local | — | `step12/g10-adapter-halves-v3.json`, `step12/g11-coverage-v3.json`, `step12/g11-coverage-v3.runs.json`, `step12/g12-real-loop-v3.json`, `step12/g12-real-loop-v3-edges.json`, `step12/m02-tests.junit.xml`, `step12/env-manifest.json`, `step12/host.txt` | `cc5b81f62b85672ef6d5403480adfe0e30e915f64da612282a4474fd4e746030`, `5eb42c9356cd4ed2662955901185d34aa265f9a8a90fcbc6b9ec19c98f2cd4fe`, `a5154500632920895750ab6824f4a0b41a4c2613ca733575b2bdbabd5ccfd052`, `33a8fea91298f0a902d22f732ea418bf86bfc5569b3881f1ae58277729ab533c`, `e4ac5a4bf6b3c75e3eada6bfdb8d9c98ca624a908d5bd70d19b22da8e737c4c7`, `3952f8f002b2aad9e357903e7965b44a9e41ce2fb5e5c7e2ed13e396417aef8a`, `f9c20cd9d686d4626fb08ca09a8d94d31f8caffa3da849b87e7a629b53cd28a6`, `e01b2e605996d24ee6c93f132ac0eb3cec2f3d220d8062a2aae5f199326c3daf` |


**M07a.A43 (provenance).** Every `t08-rc-v1` record above (local and CI, the bundle index, both replay records and
the step-11 and step-12 records included) carries `commit` = `cc73219a…`, `tree_clean = true` and
`environment_lock_sha256 = ead4edf1…b9c4`; `t08-a43-dist.json` carries the same at top level. Every one of these 29
records carries a `machine_class`, each a registered class (`ref-x86-64`, `ci-x86-64`, `ci-aarch64`) that agrees with
the record's `architecture` (`machine`) and `github_actions` where it carries them. The A30 records carry
`lock_sha256` and the host, but no `commit` or `tree_clean` (format `t08-a30-inventory-v1`); M01's and M02's records
(steps 11, 12) carry neither, and are cited through the step's `t08-rc-v1` record. Stated, not judged.

## Step 13

`scripts/v0_2_gate.py --rc C_α` (M07a.A12) needs `docs/reviews/V02-alpha-verdicts.md`, the `verdict` agent's
document at `C_α²` (§19.1 item 4), which does not exist yet (`C_α¹`'s is kept at
`docs/reviews/V02-alpha-verdicts-6fec822.md` and is not an input). It has not been run; it is pending, not failed.

## Failures

None. Every record of steps 1–12 reports `PASS` or `success`.

## Observations (not failures, not judged)

- **O1** The `check` skip counts differ between the platforms (100 / 98 skipped); the skip lines are in
  `step1-skips/` (R-376).
- **O2** The local x86-64 A30 summary differs from the committed `docs/t08-a30/t08-a30-x86_64.json` in the
  `files_digest` of all eight compiled distributions, the host's `platform` and `record_sha256`, as at `C_α¹`; the CI
  aarch64 summary differs from `docs/t08-a30/t08-a30-aarch64.json` in the eight `files_digest`, the host's `python`
  and `record_sha256`. Object counts and closures are unchanged (381 / 150; 308 / 147). A30's verdict does not read
  these fields.
- **O3** The bundle index's three G8 entries that are not CONVERGED / VERIFIED have the outcomes their revisions
  register (2 initialization, 1 homotopy stall), each with exit 0, as at `C_α¹` (named here, outside the
  per-step table, because the gate script reads any `FAIL` substring in a Result cell as a failure).
- **O4** Step 6's class counts equal `C_α¹`'s and `67c66d9`'s on `ref-x86-64` (434; F-BUDGET 3,
  F-FALSE-SUCCESS-CAUGHT 3) and on `ci-aarch64` (434; 4, 2).
- **O5** The step-11 and step-12 records' provenance carries the thread pins (`OMP/OPENBLAS/MKL_NUM_THREADS=1`),
  as `C_α¹`'s records do; `C_α¹`'s record's O5 (no pins), carried over from `C_α⁰`'s, does not describe them.
- **O6** Against `C_α¹`'s records (the 61 cited paths), every check value of steps 2–12 is equal, apart from paths,
  timestamps, hashes and these: the dist record's two sdist sizes, the install smoke run's printed bundle path (both
  architectures), and step 12's experiment and call keys (G10 runs 3–5, the G12 and edge calls; they hash the code
  identity). Thirteen cited files are byte-identical to `C_α¹`'s: the four CI A30 records, step 11's four files and
  step 12's five kept certificates. The G12 bundle certificate's `document_sha256` stays `faa8e4da…fdf8974`, equal to
