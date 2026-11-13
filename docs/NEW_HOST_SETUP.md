# New-host setup: moving development from TRS2 to SMM-TR09

Frank decided on 2026-11-10 that development moves to SMM-TR09 after the v0.4.0 release, because TRS2
hard-resets under load. Target: Linux, clone of `https://github.com/computational-chemical-engineering/openflowsheet.git`
into `/home/eajfpeters/Code/OpenFlowsheet`. Every fact cites `file:line` of this repo. Where the repo is
silent the text says "not documented; ask". Size figures marked (TRS2) were measured with `du -sh` on 2026-11-10.

## 1. Clone and the base dev environment

```sh
git clone https://github.com/computational-chemical-engineering/openflowsheet.git /home/eajfpeters/Code/OpenFlowsheet
cd /home/eajfpeters/Code/OpenFlowsheet
python3.13 --version                      # the project needs >= 3.13 (pyproject.toml:14); the lock is from 3.13.5 (requirements.lock:2)
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.lock     # CI's route (.github/workflows/ci.yml:103-104)
.venv/bin/python -m pip install -e .                      # ci.yml:113
.venv/bin/python -m pip install -e '.[dev,server]'        # what `make venv` does (Makefile:7-10); dev = pytest, mypy, ruff, stubs
```

- `PYTHONPATH=src` is the habit for scripts run without the editable install; `pyproject.toml:195` sets
  `pythonpath = ["."]` for pytest. With `pip install -e .` it is not required.
- Smoke test: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_readme_current.py` (a fast file; any
  small targeted test works). Not a documented smoke command; ask if a canonical one is wanted.
- `.venv/` and `.venv-*/` are git-ignored (`.gitignore:5,8`); so are `.reference-downloads/` (`:10`),
  `evidence/**/artifacts/` (`:20`) and `.cache/` (`:34`).
- Node >= 22 is needed by the gate (`scripts/check.sh:36-40`); CI uses Node 22 (`ci.yml:129`).
  Without it set `OPENFLOWSHEET_SKIP_WEB_TESTS=1` (`check.sh:31-34`). A headless Chromium is only needed for the
  `browser` marker (`pyproject.toml:205`); `OPENFLOWSHEET_REQUIRE_BROWSER=1` makes its absence a failure (`ci.yml:145`).
  How to install Node or Chromium on TR09: not documented; ask.
- No sudo is assumed in the repo's builds (`docs/reference-environments.md:26`); TR09's privileges: not documented; ask.

## 2. Extra environments

All are git-ignored and rebuildable from committed locks. "Needs" says which tests or RC steps use them.

| Env | Purpose | Build | Lock | Size | Needs |
| --- | --- | --- | --- | --- | --- |
| CoolProp extra (in a venv) | optional CoolProp provider (`pyproject.toml:61`) | after the base install: `.venv/bin/python -m pip install --no-deps --require-hashes -r requirements-coolprop.lock` (`requirements-coolprop.lock:3`, `ci.yml:109-110`) | `requirements-coolprop.lock` | small, not stated | the CoolProp tests (skipped without it, `docs/V03_DECISIONS.md:243`); RC step 17 builds its own `cpvenv` (`release_rc_local.py:1411-1416`) |
| docs tools | mkdocs site | `pip install --no-deps --require-hashes -r requirements-docs.txt` (`requirements-docs.txt:5`) | `requirements-docs.txt` | not stated (TRS2 `~/.cache/doc-venv` 887M) | doc-site build only |
| `.venv-testmap` | test-impact selection (S16), an inner-loop aid; never a merge gate | the base install by CI's route, then `--no-deps --require-hashes -r requirements-coolprop.lock`, `--no-deps -e .`, `--no-deps --require-hashes -r requirements-testmap.lock` (`docs/test-impact.md`, "Install") | `requirements-testmap.lock` | venv as the main one plus about 10 MB; a map is 25 MB in `~/.cache/openflowsheet/testmap/<sha>/` (a9e733e4, `docs/S16_DECISIONS.md`) | `scripts/test_impact.py build`, `select`, `run` |
| `.venv-nlp` | the audited Ipopt/cyipopt/PyNumero env for the `nlp` extra | `scripts/build-m03-ipopt-env.sh [prefix] [cache]`, defaults `.venv-nlp` and `.reference-downloads/m03-ipopt` (`build-m03-ipopt-env.sh:27-28`); check with `.venv/bin/python scripts/m03_ipopt_inventory.py --env .venv-nlp --check` (`reference-environments.md:297-298`) | `benchmarks/m03/nlp-conda-explicit.txt`, `nlp-pip.lock`, `nlp-build-conda-explicit.txt` | 841M (TRS2, m05 worktree); about 25 s per build with a warm package cache (`reference-environments.md:318`) | `pytest -m nlp` (`scripts/m03_nlp_check.sh`); `scripts/m05_wo9_real.py` (REAL M05 record); RC steps 14, 15 and the `nlp` items (`release_rc_local.py:902,1265,1366`) |
| `.venv-idaes` | IDAES 2.13.0 reference tool + binary extensions 3.4.2 | `scripts/build-reference-envs.sh idaes [log]` (`reference-environments.md:33`) | `spikes/references/idaes-requirements.lock` (`--require-hashes`) | 693 MB with extensions (`reference-environments.md:46`); TRS2 `~/.cache/idaes-2.13` 616M is a separate scratch env | M01 IDAES conformance record (RC step 11, `release_rc_local.py:1064-1087`); the RC builds its own `idaes-wt/.venv-idaes` if absent |
| `.venv-dwsim` | DWSIM via pythonnet + .NET 8.0.31 | `scripts/build-reference-envs.sh dwsim [log]` | `spikes/references/dwsim-requirements.lock` | 866 MB (`reference-environments.md:48`) | DWSIM reference spikes; not in the RC steps read |
| `.venv-biosteam` | S09 third column reference | `scripts/build-reference-envs.sh biosteam [log]` (`reference-environments.md:333`) | `spikes/references/biosteam-requirements.lock` | about 874 MB (`:333`); needs `gcc` for numpoly (`:338`) | S09 column reference runs |
| reactor (PyMRM) env | pinned reactor env for M02 v3 (`pymrm` marker) | `python -m openflowsheet.adapters.pymrm.env build --variant <v> --root <external root>` then `verify` (`release_rc_local.py:951-969`); root defaults to `$OPENFLOWSHEET_EXTERNAL_ROOT` or `$XDG_CACHE_HOME/openflowsheet/external` (`pymrm/env.py:7-8`). `<v>` = `pymrm-6089593-g2-nz800-s123-v1` (`release_rc_local.py:49`) | `src/openflowsheet/adapters/pymrm/reactor-env.lock` | 797M (TRS2 `~/.cache/openflowsheet/external/pymrm-6089593-032a050c6cf3`) | RC step 12 (G10 to G12), `-m pymrm` tests |
| LCA env | optional Brightway adapter (`pyproject.toml:75`) | `scripts/build-lca-env.sh <dir> <python>` (`release_rc_local.py:1417-1424`) | `benchmarks/e01/brightway/lca-pip.lock` | not stated | RC step 17 items |
| XCHECK venv | M01 external crosscheck | RC builds `venv-xcheck` from `XCHECK_PINS` (`release_rc_local.py:1057`) | pins in the script | not stated | RC step 11 |
| `.venv-casadi`, `.venv-pyomo` | P02 backend spikes (historic) | `docs/backend-environments.md:15-25` | inline pins | 490 MB, 291 MB (`backend-environments.md:62-63`) | not needed for development; rebuild only if asked |

The RC runner (`scripts/release_rc.py local ...`, usage at `release_rc.py:43-48`) builds several of these itself
under its `--work` directory; only the nlp prefix/cache, the journey and the W27 archive are supplied.

## 3. Tests and gates

- Targeted: `.venv/bin/python -m pytest -q tests/test_<name>.py`. `-m nlp` and `-m pymrm` tests are deselected
  by the default gate (`scripts/m03_nlp_check.sh:4-5`).
- Full gate: `scripts/gate.sh [logfile]`; it runs `scripts/check.sh` (ruff, ruff format, mypy, pytest, node tests;
  `check.sh:25-52`) and prints one summary line (`gate.sh:1-18`). About 1 h serial (task statement; the repo's own
  figures: 29 and 30 min per full-suite mode, `docs/C7_DECISIONS.md:54`). Run one at a time. It needs the venv
  first on PATH: `PATH=$PWD/.venv/bin:$PATH scripts/gate.sh` (`Makefile:24`). Per `CLAUDE.md` the local full gate
  is for release-candidate cuts only; CI on both architectures is the merge condition.
- F0: `.venv/bin/python scripts/corpus_identity.py --check` on `main` after a merge, before the push (`CLAUDE.md:64`).
- nlp: `scripts/m03_nlp_check.sh [--no-inventory] [prefix] [cache] [-- pytest args]` (`m03_nlp_check.sh:19`) sets
  `PYTHONNOUSERSITE=1`, `PYOMO_CONFIG_DIR=<env>/share/pyomo`, `OMP_NUM_THREADS=1` and puts pytest on the path from
  `benchmarks/m03/nlp-test.lock`. `pytest -m nlp` over the whole `tests/` tree in the nlp env stops at collection
  (`docs/S6DBG_DECISIONS.md:62`); pass module paths.
- REAL M05 record: `OMP_NUM_THREADS=1 PYOMO_CONFIG_DIR=.venv-nlp/share/pyomo PYTHONNOUSERSITE=1 PYTHONPATH=src:.reference-downloads/m03-ipopt/nlp-test-tools .venv-nlp/bin/python scripts/m05_wo9_real.py [--replay | --retake-into <dir>]` (`m05_wo9_real.py:62-64`).
- Without the W27 archive the gate still passes; about 60 W27 tests skip (`docs/CLOUD_WORK.md:16-17`).

## 4. Local-only state on TRS2 (not in git)

Sizes from `du -sh` on TRS2, 2026-11-10. Paths are under `/home/frankp/Codes/OpenFlowsheet` unless `~`.

| Item | Size | Copy or rebuild | Reason |
| --- | --- | --- | --- |
| `.claude/worktrees/m05/.venv-nlp` | 841M | **copy** if Frank wants the exact audited env of the last RC; else rebuild | It is "audited" and RC steps 14/15 and the REAL record use it. The build is hash-locked and reproducible across prefixes (`reference-environments.md:314-318`), so a rebuild is legitimate, but then the M03 inventory `--check` must pass. conda envs hold absolute prefixes, so a copy to another path is fragile: rebuild is the safer default. Decision: ask Frank. |
| `.claude/worktrees/alpha-main/.venv-nlp` | symlink (4.0K) | do not copy | It points to the m05 one above. |
| `.claude/worktrees/m05/.reference-downloads` | 1.9G | **rebuild** (re-created by the build script, hash-pinned) | Holds micromamba, the package cache, build env, logs and `m03-ipopt/nlp-test-tools` (needed on `PYTHONPATH` by `m05_wo9_real.py`). The main checkout has none. Rebuilding needs network and "PyPI reachable" (`backend-environments.md:13`). |
| `.reference-downloads` (main checkout) | does not exist | n/a | The IDAES/DWSIM builds write the .deb and .NET tarball here (241M in `.claude/worktrees/s03`, `reference-environments.md:51`); re-downloaded, SHA-pinned. |
| W27 archive: `.claude/worktrees/m06-w27h/evidence/M06/W27/artifacts` | 645M (tarball `OpenIDAES-450-demo.tar.gz` 220 802 919 bytes + `extracted/`, `github/`, ...) | **copy** | Needed by RC step 16 via `--w27-artifacts DIR` (`release_rc_local.py:1045-1052`, R-947). The tarball is a release asset pinned by size and SHA-256 `6d42c02f...4526` (`docs/V02_DECISIONS.md:74`); its download URL: not documented; ask. Copy the directory, then verify the SHA. |
| `~/.cache/openflowsheet/external/pymrm-6089593-032a050c6cf3` | 797M | **rebuild** with the reactor env command (section 2) | Built from `reactor-env.lock`; step 12 builds and verifies it. Rebuild needs network. |
| `~/.cache/idaes-2.13` | 616M | rebuild, or skip | A scratch IDAES env named in `docs/E01B_DECISIONS.md:626`; the RC builds its own. |
| `~/.cache/doc-venv` | 887M | rebuild if docs work is needed | Named in `docs/V03_DECISIONS.md:243`; docs tools lock `requirements-docs.txt`. |
| `~/.cache/of-rc-v03-a3e508e` (and other `of-rc-*`) | 5.0G | **do not copy** | Old RC work directories (`docs/v03-rc-record.md:31`); the evidence that matters is committed. |
| `~/.cache/e01-i1-tmp` | 740M | do not copy | Scratch (`docs/E01B_DECISIONS.md:460`). |
| `~/.claude` (global CLAUDE.md, agents, memory) | not measured | copy or recreate per Frank | `CLAUDE.md` "Cloud sessions" lists it as absent in a fresh clone; how Frank syncs it: not documented; ask. |

Excluded; ask Frank: `~/.config/procsim/`, `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`.

## 5. Credentials and accounts (the user does these personally)

- `gh auth login` on TR09 (the repo's CI polling and `gh` use). Not stored in the repo.
- Git identity: `git config --global user.name` and `user.email`. Value: not documented; ask Frank.
- PyPI trusted publisher: already registered server-side (project `openflowsheet`, workflow `release.yml`, no
  environment; `docs/RELEASING.md:50-56`). Nothing to do on TR09; the release runs in GitHub Actions with the
  `pypi` environment approval. No secret is needed (`RELEASING.md:40-41`).
- Pre-push guard: only for a clone that also holds `openflowsheet-dev` history (`RELEASING.md:58-62`). A fresh clone of
  the public repository needs none and the hook does no harm: `scripts/install-hooks.sh`. TRS2's checkout has an
  `archive` remote (`openflowsheet-dev`); do not add it on TR09 unless needed, and if added run the hook first.
- The archive `openflowsheet-dev` stays a read-only private repository (`RELEASING.md:73-76`).
- V17 login token: never copied by an agent (R-116, `CLAUDE.md` "Cloud sessions"). Frank provisions it; where it
  lives: not documented; ask. Only RC/W27/V17 campaigns need it.

## 6. Platform note: the first cut on TR09 needs re-takes

The records and judgements bound to the RC host move from TRS2 to TR09 by `docs/reviews/HOSTMOVE-ruling.md`
(R-1020, RP amendment A-13): its sections 3 to 7 say what moves and how, and its work orders WO-H1 to WO-H5 carry
it out. In short: the five in-process G10 records were re-baselined on TR09 after the tag (WO-H2); M05's REAL
record and M01's IDAES record are re-taken at the first TR09 K3 (WO-H4); TR09 joins T06's `ref-x86-64` only by
WO-H5's proof (RP (P6)). The proofs take the A-13 form: `scripts/m05_retake_diff.py --digest-only --old-version
<v> --old-host SMM-TRS2` for the five, and `--old-platform <p> --old-host SMM-TRS2` for REAL. A kernel upgrade
between J and the RC steps 11, 14, 15 still means a new J and a new C (`RELEASING.md`, the R-1008 paragraph).
Do not carry TRS2's records across as if they matched TR09.

## 7. Machine-load rule

Check `uptime` before heavy runs; run one full gate at a time. TRS2's rule was at most about 36 busy cores of 48
(`docs/V02_STATE.md:131`). TR09's core count and the equivalent cap: not documented; ask. The RC runner pins
`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` to 1 (`release_rc_local.py:46`). Also:
`CLAUDE.md` "Agent budget" (at most 2 agents at a time, fresh agents not resumed, gates by risk).
