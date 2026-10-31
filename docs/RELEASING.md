# Releasing OpenFlowsheet

OpenFlowsheet is developed and released in one repository,
`computational-chemical-engineering/openflowsheet` (public): branches, pull requests, CI, tags and
releases all live there (Frank's decision, 2026-10-03; R-150). Its history starts at v0.1.0
(`5a35019`); the development history before it is archived, read-only, in the private
`openflowsheet-dev` — see `docs/HISTORY.md`.

A release is one GitHub workflow, `.github/workflows/release.yml`, dispatched by hand. It is a
**dry run by default**. The one-time setup and the approval of the PyPI upload are Frank's;
everything else is automated and refuses to run unless the release gate says YES.

| Job | Runs on a dry run | What it does |
| --- | --- | --- |
| `gate` | yes | The version is `pyproject.toml`'s and of the form `X.Y.Z`, or a pre-release `X.Y.Z{a\|b\|rc}N` (N ≥ 1; see [Pre-releases](#pre-releases)); a tag `vX.Y.Z`, if it exists, is on this commit; `CHANGELOG.md` has a `## vX.Y.Z` section (the release notes); the gate of the version's minor line, `scripts/v<major>_<minor>_gate.py --rc <rc>`, exits 0 **and** prints `vX.Y.Z tag may be proposed: YES`. Uploads `release-record` (`gate.txt`, `notes.md`). |
| `tag` | no | Tags the gated commit `vX.Y.Z` (annotated, by `github-actions[bot]`) and pushes the tag with the workflow's `GITHUB_TOKEN`. An existing tag on the same commit is accepted; on another commit, refused. |
| `build` | yes | The sdist and the wheel from the gated commit, built twice and inspected (`scripts/t08_dist.py`, T08.A43). Uploads `dist` and `build-record`. |
| `pypi` | no | Waits for approval in the GitHub environment `pypi`, then uploads `dist` to PyPI by trusted publishing (no token). |
| `github-release` | no | Creates the GitHub release `vX.Y.Z` with the `CHANGELOG.md` section as its notes and the sdist and wheel attached; a version with an `a`, `b` or `rc` segment is marked a pre-release (`--prerelease`). |

Every job runs only in `computational-chemical-engineering/openflowsheet` (a fork skips them all).
The gate judges the release candidate `C` given as `rc` (default
`67c66d98587f23bd7dfe8da28a8facccc92da21e`, the v0.1 candidate): the released files under the
ADR 0021 D2.4 paths must equal `C`'s but for the version. `C` is a commit of the archived history,
so in this repository the gate reads `C`'s files from `release/rc-trees/<C>.json`, their recorded
sha256 (R-151).

## One-time setup

### 1. The `pypi` environment (the approval gate)

1. `openflowsheet` → **Settings** → **Environments** → **New environment**, name `pypi` →
   **Configure environment**.
2. **Required reviewers**: tick, add Frank → **Save protection rules**.
3. **Deployment branches and tags**: **Selected branches and tags** → **Add deployment branch or
   tag rule** → **Branch**, `main`; add a second rule → **Tag**, `v*`. The workflow is dispatched
   from `main`, so its `pypi` job deploys from `main`; the tag rule admits a run dispatched from a
   release tag.

No secret is needed: the upload uses the job's OIDC token, and the tag is pushed with the
workflow's own `GITHUB_TOKEN`.

### 2. Actions

**Settings** → **Actions** → **General**: allow GitHub Actions. If the organization allows only
selected actions, allow `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`,
`actions/download-artifact` and `pypa/gh-action-pypi-publish`. If a ruleset protects tags `v*`,
let GitHub Actions bypass it (the `tag` job creates the tag).

### 3. PyPI trusted publisher (done)

Frank has registered the pending publisher on pypi.org: PyPI project `openflowsheet`, owner
`computational-chemical-engineering`, repository `openflowsheet`, workflow `release.yml`, and **no
environment** — PyPI then accepts an upload from any job of that workflow, and the approval gate
is the GitHub environment `pypi` alone. To tighten it, edit the publisher on PyPI and set its
environment to `pypi` (it must equal the `environment.name` of the `pypi` job).

### 4. The pre-push guard (every clone that also holds the archive)

A clone that holds both the archived history and the public line — the old development checkout,
or any clone that has fetched `openflowsheet-dev` — can publish the private history with one
`git push`. In every such clone, once:

```sh
scripts/install-hooks.sh          # writes $(git rev-parse --git-path hooks)/pre-push
```

The hook (a copy of `scripts/pre_push_guard.py`; the hooks directory is shared by all worktrees
of the clone) refuses a push to any URL naming `computational-chemical-engineering/openflowsheet…`
other than the archive `openflowsheet-dev` unless every commit it could send descends from v0.1.0
(`5a35019`); a merge that brings in an archived commit is refused although its tip descends. It
fails closed: without `5a35019` in the clone nothing is shown to descend, and the push is refused.
A different existing `pre-push` hook is kept unless `--force` is given. A fresh clone of the public
repository holds no archived commit and needs no guard, but the hook does no harm there.

### 5. The archive

The private `openflowsheet-dev` stays as the read-only archive of the pre-0.1.0 history (its
commit ids are cited in `evidence/`). **Settings** → **General** → **Archive this repository**
makes it read-only on GitHub; that is Frank's call.

## Per release

1. **Prepare** on a branch and merge to `main` by pull request: the version in `pyproject.toml`,
   `src/openflowsheet/__init__.py` and the version-carrying test fixtures
   (`tests/fixtures/schemas/application_results/project_summary/*/*.json`), and a `## vX.Y.Z`
   section in `CHANGELOG.md`. The same cut commit updates `README.md`'s status to name the release
   (it is the PyPI project page; every link in it absolute; `tests/test_readme_current.py`). Check
   the gate locally:

   ```sh
   PYTHONPATH=src .venv/bin/python scripts/v0_1_gate.py --rc 67c66d98587f23bd7dfe8da28a8facccc92da21e
   ```

   It must end with `vX.Y.Z tag may be proposed: YES`.
2. **Dry run.** `openflowsheet` → **Actions** → **release** → **Run workflow**. Use workflow from
   `main`; `version` `X.Y.Z`; `rc` as given (the v0.1 candidate); **dry_run ticked** → **Run
   workflow**. `gate` and `build` run; `tag`, `pypi` and `github-release` are skipped.
3. **Inspect** the run's artifacts: `release-record` (`gate.txt`, the gate's report ending
   `vX.Y.Z tag may be proposed: YES`; `notes.md`, the release notes), `dist` (the sdist and the
   wheel) and `build-record` (`t08-a43-dist.json`, every check passed).
4. **Release.** Run the workflow again with the same inputs and **dry_run unticked**. `gate`
   repeats, `tag` pushes `vX.Y.Z`, `build` rebuilds, and `pypi` waits: **Review deployments** →
   tick `pypi` → **Approve and deploy**. After the upload `github-release` creates the release.
5. **Verify.** In a fresh environment `pip install openflowsheet==X.Y.Z`, and look at the release
   page and https://pypi.org/project/openflowsheet/.

**0.3.0** (V03 spec §4–§5, ADR 0053, R-872–R-877). `scripts/v0_3_gate.py` holds the 0.3 line's one gate set,
`v0.3-gate-v1`, on `v0_2_gate.py`'s engine. It covers `0.3.0`, `0.3.0bN` and `0.3.0rcN`, claims V11–V20, W21–W26 and
X31, prints W27 as not claimed, and reads ADR 0053's two tables, `docs/reviews/V03-verdicts.md`, `docs/v03-rc-record.md`
(steps 1–17), S13's manifest at C, the twenty packages' manifests at ancestors of C, and the 25 required ADRs, every
input at C (`git show`). The steps follow `0.2.0a1`'s ([Pre-releases](#pre-releases)) with these values:

1. The cut commit K3 on `main` declares `0.3.0` in `pyproject.toml`, `src/openflowsheet/__init__.py`, the two
   `project_summary` fixtures and `tests/test_m06_w27_coverage.py`, and pins the envelope (`envelope_id:
   v0.3-envelope-1`, `release: 0.3.0`). From K3 until the dispatch `main` takes no change to a D2.4 path.
2. C is K3 plus commits outside the D2.4 paths: K3's journey record, the RC records, `release/rc-trees/<C>.json`,
   `evidence/S13/<C>/manifest.json`, the verdicts, the ledger and the `## v0.3.0` section of `CHANGELOG.md`. C is
   merged into `main` with a merge commit, never squashed.
3. The RC job runs at C: steps 1–17 (step 17b is CI's `rc-coolprop` job, the CoolProp tests with
   `requirements-coolprop.lock` installed; step 12 keeps G11's experiment results and audits them, as every release
   from 0.3.0 does, R-375 and R-909), then

   ```sh
   PYTHONPATH=src .venv/bin/python scripts/v0_3_gate.py --rc <C>
   ```

   must end with `v0.3.0 tag may be proposed: YES`.
4. **Dispatch** as in steps 2–5 above, with `version` `0.3.0` and **`rc` = C**.
5. After the tag, the first D2.4 change sets `0.4.0.dev0`, returns the envelope to its working form and re-takes the
   five in-process G10 records (R-875, R-458).

## Pre-releases

V02 alpha release spec §9 (ADR 0028 D4–D6). A pre-release has a canonical PEP 440 version,
`X.Y.ZaN`, `X.Y.ZbN` or `X.Y.ZrcN` with N ≥ 1 (`0.2.0a1`, never `0.2.0a0`, `0.2.0a01`,
`0.2.0-a1` or `0.2.0alpha1`), so that setuptools writes it unchanged into the metadata and the file
names. `release.yml` and `scripts/changelog_section.py` accept exactly those forms (the spec's
Tables T2 and T3); the gate is still resolved by major and minor version, and the GitHub release is
created marked **pre-release**, which `pip` installs only with `--pre` or the exact version.

**The gate.** `scripts/v0_2_gate.py` holds a registry of gate sets. Its only one today,
`v0.2-alpha-gate-v1`, covers `0.2.0aN` and nothing else: it claims V11–V20 (re-judged at the
alpha's own release candidate `C_α`), W21 and W22, prints W23–W27 as not claimed, and reads every
input at the tag candidate (`git show`), not from the working tree. It also requires Frank's three
answers and his D3 acceptances in ADR 0028's two tables (never ADR 0021's), each starting
`accepted, YYYY-MM-DD` with the date right after the word and on or after the verdict's `Judged`
date, so that an answer given for one pre-release is not read for the next (spec Tables T4 and T6,
Amendment 1); the RC record
`docs/v02-alpha-rc-record.md` with steps 1–12 passed, M07a's manifest at `C_α`, M01's and M02's
`tested` manifests at ancestors of `C_α`, the envelope pinned to `v0.2-alpha-envelope-1` with
`release` equal to the version, and the required ADRs Accepted. Every other `0.2` version is
refused as not covered until M07 registers the 0.2.0 gate set.

**Preparation of `0.2.0a1`** (spec §9.2):

1. `C_α` declares the version itself: `0.2.0a1` in `pyproject.toml`, `src/openflowsheet/__init__.py`
   and the version-carrying test fixtures, and the envelope pinned (MR-3). There is no bump at the
   tag: the gate requires `C_α`'s version to equal the candidate's (ADR 0028 D4).
2. **The freeze.** From `C_α` until the dispatch, `main` takes no change to a D2.4 path (`src/`,
   `schemas/`, `benchmarks/`, `requirements.lock`, `pyproject.toml`, `MANIFEST.in`, `README.md`,
   `LICENSE`, `NOTICE`); work continues on branches. The alternative (spec Q7) is that Frank pushes
   `v0.2.0a1` on the candidate and dispatches from the tag.
3. The RC job runs at `C_α`; its records, the RC record, the M07a manifest, the verdicts, the
   ledger and the `## v0.2.0a1` section of `CHANGELOG.md` are committed after `C_α`, outside the
   D2.4 paths; `release/rc-trees/<C_α>.json` is written with
   `scripts/v0_2_gate.py --rc <C_α> --write-tree-record`. `C_α` is merged into `main` with a merge
   commit, never squashed, so that it stays reachable.
4. Check the gate locally on `main`:

   ```sh
   PYTHONPATH=src .venv/bin/python scripts/v0_2_gate.py --rc <C_α>
   ```

   It must end with `v0.2.0a1 tag may be proposed: YES`.
5. **Dispatch** as in [Per release](#per-release) steps 2–5, with `version` `0.2.0a1` and **`rc` =
   `C_α`**. The `rc` input's default is the v0.1 candidate `67c66d9`; a dispatch that forgets to
   change it is refused, because that candidate's version `0.1.0rc1` is not the candidate's.

**After a tag** (R-460). The first change to a D2.4 path after a tag moves the version to a `.dev0`
that sorts after the tagged version, and returns the envelope to its working form
(`v0.2-envelope-dev`, `release: 0.2.0.dev0`, R-193). After `0.2.0a1`, `main` carries
`0.2.0a2.dev0`; `0.2.0.dev0` would sort before the release it follows. After `0.2.0`, `main` carries
`0.3.0.dev0` (C7), with the envelope again in its working form; after `0.3.0`, `0.4.0.dev0` (V03 WO-9). The working form's id and label are a fixed token for `main`'s
unreleased working envelope, not "v0.2 under development"; the token stays across releases (V03 spec §5.3, R-563):
each release adds only its own two pin pairs. The version is set in
`pyproject.toml`, `src/openflowsheet/__init__.py`, the two `project_summary` fixtures and
`tests/test_m06_w27_coverage.py`. At 0.2.0 W27's `coverage.json` was re-taken at that build; from
0.3.0 it is not, because W27's version-1 snapshot refuses the S11 build (`registry_snapshot: unsupported(provider
'iapws95-v1' …)`), 0.3.0 claims no W27, and the one default-gate test that compares it with the live build treats
`package_version`, like `git_commit`, as build provenance outside the comparison (R-902; R-566 dropped the byte
pin; V03 spec §2.1, §5.1, F-4). A version
string that names a release identifies that release's D2.4 tree and nothing else
(`tests/test_v02_main_version.py`). `release.yml` refuses a `.devN` version and the gate answers NO
for it, so a head between releases cannot be dispatched. The version is part of the in-process
experiment fingerprint, so the five in-process G10 records are re-taken after it changes and the
re-take is proved with `scripts/m05_retake_diff.py --digest-only` (R-458).

## Post-releases

R-922 (V03-post1). A post-release `X.Y.Z.postN` (N ≥ 1, canonical) republishes a released `X.Y.Z`
with a corrected PyPI page and nothing else — `0.3.0.post1` is the first. It is admitted iff, against
`X.Y.Z`'s candidate C, the D2.4 files differ only in `README.md`; in `pyproject.toml` only
`[project]` `version`, `urls` and `readme`; and in `src/openflowsheet/__init__.py` only the version
string; files outside D2.4 (the version-carrying test fixtures, `CHANGELOG.md`, `docs/`, `scripts/`,
`tests/`, `.github/`) are free. A tag `vX.Y.Z` must be on an ancestor of the candidate.

`X.Y.Z`'s gate verdict carries unchanged: the line's gate script (`scripts/v0_3_gate.py` for 0.3)
gates `X.Y.Z.postN` as `X.Y.Z`, with the same gate set, the same C, the same verdicts and the
envelope still at `X.Y.Z` (`v0.3-envelope-1`, `release: 0.3.0`); its report adds the line
`post-release (R-922): of X.Y.Z, released (tag vX.Y.Z)` and ends `vX.Y.Z.postN tag may be proposed:
YES`. Nothing is re-judged and no RC job runs. The steps:

1. On a branch, set `X.Y.Z.postN` where the cut set `X.Y.Z` (`pyproject.toml`,
   `src/openflowsheet/__init__.py`, the `project_summary` fixtures, the W27 coverage test), change
   the README or the project links, and write a `## vX.Y.Z.postN` section in `CHANGELOG.md` that says
   what changed and that no code did. Merge to `main`.
2. Check: `PYTHONPATH=src .venv/bin/python scripts/v0_3_gate.py --rc <C>` ends with
   `vX.Y.Z.postN tag may be proposed: YES`.
3. Dispatch as in steps 2–5 of [Per release](#per-release), with `version` `X.Y.Z.postN` and `rc` = C.
   `release.yml` refuses a post-release whose `vX.Y.Z` tag does not exist, and does not mark the
   GitHub release a pre-release.

## What the workflow refuses

| Refusal | Enforced by |
| --- | --- |
| Running outside `computational-chemical-engineering/openflowsheet` | every job's `if: github.repository == '…'` |
| Tagging, uploading or publishing on a dry run | `tag`, `pypi`, `github-release`: `if: … && !inputs.dry_run` |
| An upload without approval | `pypi` runs in the environment `pypi` (required reviewer Frank) |
| A version not of the form `X.Y.Z`, `X.Y.Z{a\|b\|rc}N` or `X.Y.Z.postN` (N ≥ 1), or not `pyproject.toml`'s | `gate`, first step |
| A post-release `X.Y.Z.postN` without a tag `vX.Y.Z` | `gate`, first step, and the gate script (R-922) |
| A tag `vX.Y.Z` on another commit | `gate` (before anything is built) and `tag` |
| A release without its `CHANGELOG.md` section | `scripts/changelog_section.py` in `gate` |
| A gate that is not YES for this version | `gate`: the minor line's gate script must exist, exit 0 **and** print `vX.Y.Z tag may be proposed: YES` |
| Files under the D2.4 paths that differ from `C`'s beyond the version (for a post-release, beyond R-922's allowance) | the gate's tree check (by git where `C` is present, else by `release/rc-trees/<C>.json`) |
| Artifacts that fail T08.A43's inspection | `build` (`scripts/t08_dist.py`), before `pypi` |
| A build after a failed or cancelled `tag` | `build`'s `if` |

## Rolling back

- **Before approving `pypi`**: reject the deployment or cancel the run. On a real run the tag is
  already pushed; delete it if the release is abandoned (the tag's page → **Delete**, or
  `git push origin :refs/tags/vX.Y.Z` from a clone with write access). Re-running the workflow on
  the same commit accepts an existing tag on that commit.
- **After the PyPI upload**: PyPI never accepts the same file name twice, so a version cannot be
  replaced. **Yank** it: pypi.org → `openflowsheet` → **Manage** → **Releases** → `X.Y.Z` →
  **Options** → **Yank** (with a reason), then release `X.Y.Z+1`. Mark the GitHub release as such
  or delete it; leave the tag, which names what PyPI shipped.

## Notes

- **The gate is per minor line.** `scripts/v0_1_gate.py` covers `0.1.z` and refuses any other
  version; a `0.2.x` release needs a `scripts/v0_2_gate.py` and its own release candidate.
  `scripts/v0_2_gate.py` covers only the versions of its registered gate sets (today `0.2.0aN`);
  M07 adds the set for `0.2.0`.
- **A tag pushed with `GITHUB_TOKEN` starts no other workflow.** Nothing here is tag-triggered;
  `ci.yml` runs on branch pushes and pull requests.
- **v0.1.0** is on GitHub (tag `v0.1.0`, the root commit) but was not published to PyPI; `0.1.1`
  is the first release through this workflow. Whether v0.1.0 itself should reach PyPI is Frank's
  call.
- **Tests that read the archived history** skip in this repository with the reason "pre-0.1.0
  development history is archived in openflowsheet-dev (R-150)", and run unchanged where that
  history is present (`tests/conftest.py`, `require_archived_history`).
- A local rehearsal of the `gate` job, in a clone with the project environment:

  ```sh
  VERSION=X.Y.Z; RC=67c66d98587f23bd7dfe8da28a8facccc92da21e
  python scripts/changelog_section.py "v$VERSION" > /tmp/notes.md
  python scripts/v0_1_gate.py --rc "$RC" | tee /tmp/gate.txt
  grep -qxF "v$VERSION tag may be proposed: YES" /tmp/gate.txt && echo gate YES
  python scripts/t08_dist.py --out /tmp/dist --commit HEAD
  ```
