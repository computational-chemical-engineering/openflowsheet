# Releasing OpenFlowsheet

Releases are made by two GitHub workflows (Frank's decision, 2026-10-03). The one-time setup and
the two approval clicks are Frank's; everything else is automated and refuses to run unless the
release gate says YES.

| Repository | Visibility | Holds | Workflow |
| --- | --- | --- | --- |
| `computational-chemical-engineering/openflowsheet-dev` | private | the full development history; the authority | `.github/workflows/cut-release.yml` — dispatched by hand |
| `computational-chemical-engineering/openflowsheet` | public | one squashed commit per release, nothing else | `.github/workflows/release.yml` — started by the release tag |

**What happens.** `cut-release.yml` runs `scripts/release_snapshot.py check` (the release gate at
the development commit), tags that commit `vX.Y.Z`, and runs `scripts/release_snapshot.py build`:
one commit on the public `main` whose tree is the tagged tree minus `release/public-exclude.txt`,
whose parent is the previous release (none for the first), by `OpenFlowsheet release
<e.a.j.f.peters@tue.nl>` at the tagged commit's date, with the message `OpenFlowsheet vX.Y.Z` and the
development commit id, plus an annotated tag `vX.Y.Z` on it. No development history reaches the
public repository: only the files of the release are copied, the commit is written anew, and the
build refuses a public `main` holding anything but earlier release snapshots. The same development
commit always gives the same public commit id. The push of the public tag starts the public
`release.yml`, which checks the tag against the package version, builds the sdist and the wheel
(`scripts/t08_dist.py`: built twice and inspected), uploads them to PyPI by trusted publishing, and
creates the GitHub release with the version's `CHANGELOG.md` section as its notes.

`cut-release.yml` has two jobs. **`snapshot`** needs no secret and no approval: it checks, tags
locally, builds the snapshot from an anonymous clone of the public repository and uploads the
record. With `dry_run` (the default) that is all. Otherwise **`publish`** waits for approval in the
`release` environment, repeats the check, clones the public repository with the deploy key,
rebuilds the snapshot and refuses unless its commit id equals the one `snapshot` recorded, then
pushes the private tag and the public `main` and tag together (`git push --atomic`).

## Where things stand (2026-10-03)

`https://github.com/computational-chemical-engineering/openflowsheet` already serves one commit,
`5a35019` ("OpenFlowsheet v0.1.0 — initial public release", by Frank, the exact tree of the
development commit `a3bc534`) on `main`, with the tag `v0.1.0`. It was made by hand, so
`release/public-history.txt` lists it as the public v0.1.0 and `build` builds the next release on
it; any other foreign commit on the public `main` is refused. Consequences:

- **v0.1.0 cannot go through these workflows.** Its public tag exists, and its tree has no
  `release.yml`, so pushing that tag started nothing and v0.1.0 is not on PyPI by this route. The
  first automated release is the next version (`0.1.1` or `0.2.0`), from a development commit that
  contains this automation. Whether v0.1.0 itself should reach PyPI is Frank's call.
- The development checkout's `origin` may still name `…/openflowsheet.git`; if that URL now
  serves the public repository, **a push from that checkout publishes private history** — see the
  warning under step 1.

## One-time setup

Do these in order. Step 1 must be finished before step 2 (see the warning there).

### 1. Rename the private repository to `openflowsheet-dev`

1. On GitHub, open `computational-chemical-engineering/openflowsheet` → **Settings** → **General**.
2. Under **Repository name** enter `openflowsheet-dev` → **Rename**.
3. In **every** local clone and worktree, point `origin` at the new name:

   ```sh
   git remote set-url origin git@github.com:computational-chemical-engineering/openflowsheet-dev.git
   git remote -v   # check
   ```

> **Warning.** After the rename GitHub redirects the old name to `openflowsheet-dev` — but only
> until a repository named `openflowsheet` exists again. Once step 2 creates the public one, a
> clone still configured with the old URL pushes to the **public** repository, and Frank's own
> account has write access there: a `git push` of a development branch would publish private
> history. Update every remote (and any CI, script or bookmark that uses the URL) before step 2.

### 2. Create the empty public repository `openflowsheet`

1. GitHub → **New repository**. Owner `computational-chemical-engineering`, name `openflowsheet`,
   **Public**.
2. Leave **Add a README**, **.gitignore** and **license** all unset: the repository must be empty.
   (A first commit made by GitHub is not a release snapshot, and `build` refuses to build on it.)
3. **Create repository**.
4. **Settings** → **Actions** → **General**: allow GitHub Actions. If the organization allows only
   selected actions, allow `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`,
   `actions/download-artifact` and `pypa/gh-action-pypi-publish`.

### 3. The deploy key (write access to the public repository, held by the private one)

1. On your machine, in a scratch directory:

   ```sh
   ssh-keygen -t ed25519 -N "" -C "openflowsheet release deploy key" -f openflowsheet_deploy
   ```

   This writes `openflowsheet_deploy` (private half) and `openflowsheet_deploy.pub` (public half).
2. Public repository `openflowsheet` → **Settings** → **Deploy keys** → **Add deploy key**. Title
   `release (openflowsheet-dev cut-release.yml)`; key: the contents of `openflowsheet_deploy.pub`;
   tick **Allow write access** → **Add key**.
3. Private repository `openflowsheet-dev` → **Settings** → **Environments** → open `release`
   (create it first, step 4) → **Environment secrets** → **Add environment secret**. Name
   `PUBLIC_REPO_DEPLOY_KEY`; value: the entire contents of `openflowsheet_deploy` (from
   `-----BEGIN OPENSSH PRIVATE KEY-----` to `-----END OPENSSH PRIVATE KEY-----`) → **Add secret**.
   An environment secret is readable only by a job that passed the environment's approval; a
   repository secret (**Settings** → **Secrets and variables** → **Actions**) also works but is
   readable by any workflow in the repository.
4. Delete both files from your machine (`rm openflowsheet_deploy openflowsheet_deploy.pub`). A new
   key can always be made the same way; the old one is then deleted under **Deploy keys**.

### 4. The approval environments

1. Private repository `openflowsheet-dev` → **Settings** → **Environments** → **New environment**,
   name `release` → **Configure environment**:
   - **Required reviewers**: tick, add Frank → **Save protection rules**.
   - **Deployment branches and tags**: **Selected branches and tags** → **Add deployment branch or
     tag rule** → branch `main`. The workflow must then be dispatched from `main` (the branch whose
     `cut-release.yml` runs) for the publish job to start.
2. Public repository `openflowsheet` → **Settings** → **Environments** → **New environment**, name
   `pypi` → **Configure environment**:
   - **Required reviewers**: tick, add Frank → **Save protection rules**.
   - **Deployment branches and tags**: **Selected branches and tags** → **Add deployment branch or
     tag rule** → **Tag**, pattern `v*`.

### 5. PyPI trusted publisher (done)

Frank has registered the pending publisher on pypi.org (**Your account** → **Publishing** → **Add a
new pending publisher** → **GitHub**): PyPI project `openflowsheet`, owner
`computational-chemical-engineering`, repository `openflowsheet`, workflow `release.yml`, and **no
environment** — so PyPI accepts an upload from any job of that workflow, and the approval gate is
the GitHub environment `pypi` alone. To tighten it, edit the publisher on PyPI and set its
environment to `pypi`. The name entered on PyPI **must equal** `PYPI_ENVIRONMENT` at the top of
`.github/workflows/release.yml` (now `pypi`); if they differ, the upload is refused by PyPI.

## Per release

1. **Locally**, on the development `main`, confirm the gate:
   `PYTHONPATH=src .venv/bin/python scripts/v0_1_gate.py --rc <C>` ends with
   `v0.1.0 tag may be proposed: YES`. (`CHANGELOG.md` must have a `## vX.Y.Z` section; it becomes
   the release notes.)
2. **Dry run.** `openflowsheet-dev` → **Actions** → **cut-release** → **Run workflow**. Use workflow
   from `main`; `version` `X.Y.Z`; `rc_commit` the full id of `C`; `ref` `main` (or the commit to
   release); **dry_run ticked** → **Run workflow**.
3. **Inspect** the run's artifact `release-snapshot-vX.Y.Z`:
   - `gate.txt` — the gate's report, ending `… tag may be proposed: YES`;
   - `snapshot.json` — `public_commit` (the would-be public commit id), `parent` (the previous
     release, `null` for the first), `development_commit`, `file_count`, `excluded`;
   - `files.txt` — every path that will be public; `excluded.txt` — every path left out.
   Check that `files.txt` holds nothing that must stay private. If it does, add a pattern to
   `release/public-exclude.txt` on `main` and start again.
4. **Release.** Run the workflow again with the same inputs and **dry_run unticked**. Its `snapshot`
   job must print the same `public_commit` as the dry run (it is reproducible). The `publish` job
   then waits: **Review deployments** → tick `release` → **Approve and deploy**. It pushes the
   private tag, then the public `main` and tag.
5. **Publish.** In `openflowsheet` → **Actions**, the `release` run has started on the tag. When
   `build` has passed, the `pypi` job waits: **Review deployments** → `pypi` → **Approve and
   deploy**. After the upload, `github-release` creates the GitHub release with the notes and the
   sdist and wheel attached.
6. **Verify.** In a fresh environment `pip install openflowsheet==X.Y.Z`, and look at the release
   page and https://pypi.org/project/openflowsheet/.

Pushing to the public `main` also starts the public copy of `ci.yml` (it runs on every branch
push); that is expected and does not affect the release.

## What the workflows refuse

| Refusal | Enforced by |
| --- | --- |
| Running outside its repository | every job's `if: github.repository == '…'` (private: `openflowsheet-dev`; public: `openflowsheet`) |
| Any push or secret without approval | only `cut-release.yml`'s `publish` job pushes or reads `PUBLIC_REPO_DEPLOY_KEY`; it runs only with `dry_run` unticked and behind the `release` environment |
| A gate that is not YES | `release_snapshot.py check`: the gate script must exit 0 **and** print `vX.Y.Z tag may be proposed: YES` |
| A version `pyproject.toml` does not declare | `check` and `build` (development commit); `verify-tag` in `release.yml` (the pushed tag) |
| A version not of the form `X.Y.Z` | `check`, `build`, `verify-tag`, `changelog_section.py` |
| A modified checkout, or a commit other than the checked-out one | `check` (the gate reads the working tree) |
| A private tag `vX.Y.Z` on another commit | `check` |
| A public `main` holding anything but release snapshots | `build` (author, committer, subject, one parent, increasing versions), except the commits listed in `release/public-history.txt` |
| A version not newer than the last public release; a public tag `vX.Y.Z` that exists | `build` |
| A snapshot differing from the dry-run job's | `build --expect-commit` in the `publish` job |
| A tree whose snapshot differs from the tagged tree minus exclusions | `build` compares the written tree with the tagged tree entry by entry |
| A submodule; an exclusion pattern with `!` | `build` |
| A missing deploy key | `publish` job, before cloning |
| A release without its `CHANGELOG.md` section | `changelog_section.py`, before anything is built or uploaded |
| Artifacts that fail T08.A43's inspection | `t08_dist.py`, before the PyPI job |

## Rolling back

- **Before approving `release`**: reject the deployment or cancel the run. Nothing was pushed.
- **After the public push, before approving `pypi`**: reject the `pypi` deployment. To withdraw the
  tag, delete it from a clone with write access (`git push origin :refs/tags/vX.Y.Z`, or the tag's
  page on GitHub → **Delete**) and delete the private tag the same way. The snapshot commit stays
  on the public `main`; rewriting `main` would need a force-push. Re-running `cut-release.yml` for
  the same development commit re-creates the identical tag (and so restarts `release.yml`);
  releasing different content needs a new version.
- **After the PyPI upload**: PyPI never accepts the same file name twice, so a version cannot be
  replaced. **Yank** it: pypi.org → `openflowsheet` → **Manage** → **Releases** → `X.Y.Z` →
  **Options** → **Yank** (with a reason), then release `X.Y.Z+1`. Mark the GitHub release as such
  or delete it (the release page → **Delete**); leave the tag, which names what PyPI shipped.

## Notes

- **Hand-made public commits.** A commit put on the public `main` by hand (as v0.1.0 was) must be
  listed in `release/public-history.txt` as `<commit id> <version>` on the development `main`
  before the next release, or `build` refuses it.
- **What becomes public** is the whole tagged tree except `release/public-exclude.txt` (gitignore
  patterns, read from the tagged commit; now only `.github/workflows/cut-release.yml`). That
  includes `docs/`, `evidence/`, `scripts/` and this file. Add a pattern there before a release
  to keep a path private.
- **The gate script is per minor line**: `check` runs `scripts/v<major>_<minor>_gate.py` and
  requires the line with the version being released. `scripts/v0_1_gate.py` prints `v0.1.0`
  literally, so a `0.1.1` release needs that line to follow the version first; `0.2.x` needs a
  `scripts/v0_2_gate.py`.
- A local dry run, without GitHub:

  ```sh
  git init --bare -b main /tmp/public.git          # or: git clone --bare <public url>
  python scripts/release_snapshot.py build --version X.Y.Z --commit <commit> \
      --public /tmp/public.git --out /tmp/snapshot
  ```

  For a commit older than the exclusion list, add `--exclude-list release/public-exclude.txt`.
