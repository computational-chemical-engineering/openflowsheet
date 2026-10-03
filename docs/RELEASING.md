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
| `gate` | yes | The version is `pyproject.toml`'s and of the form `X.Y.Z`; a tag `vX.Y.Z`, if it exists, is on this commit; `CHANGELOG.md` has a `## vX.Y.Z` section (the release notes); the gate of the version's minor line, `scripts/v<major>_<minor>_gate.py --rc <rc>`, exits 0 **and** prints `vX.Y.Z tag may be proposed: YES`. Uploads `release-record` (`gate.txt`, `notes.md`). |
| `tag` | no | Tags the gated commit `vX.Y.Z` (annotated, by `github-actions[bot]`) and pushes the tag with the workflow's `GITHUB_TOKEN`. An existing tag on the same commit is accepted; on another commit, refused. |
| `build` | yes | The sdist and the wheel from the gated commit, built twice and inspected (`scripts/t08_dist.py`, T08.A43). Uploads `dist` and `build-record`. |
| `pypi` | no | Waits for approval in the GitHub environment `pypi`, then uploads `dist` to PyPI by trusted publishing (no token). |
| `github-release` | no | Creates the GitHub release `vX.Y.Z` with the `CHANGELOG.md` section as its notes and the sdist and wheel attached. |

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
   section in `CHANGELOG.md`. Check the gate locally:

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

## What the workflow refuses

| Refusal | Enforced by |
| --- | --- |
| Running outside `computational-chemical-engineering/openflowsheet` | every job's `if: github.repository == '…'` |
| Tagging, uploading or publishing on a dry run | `tag`, `pypi`, `github-release`: `if: … && !inputs.dry_run` |
| An upload without approval | `pypi` runs in the environment `pypi` (required reviewer Frank) |
| A version not of the form `X.Y.Z`, or not `pyproject.toml`'s | `gate`, first step |
| A tag `vX.Y.Z` on another commit | `gate` (before anything is built) and `tag` |
| A release without its `CHANGELOG.md` section | `scripts/changelog_section.py` in `gate` |
| A gate that is not YES for this version | `gate`: the minor line's gate script must exist, exit 0 **and** print `vX.Y.Z tag may be proposed: YES` |
| Files under the D2.4 paths that differ from `C`'s beyond the version | the gate's tree check (by git where `C` is present, else by `release/rc-trees/<C>.json`) |
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
