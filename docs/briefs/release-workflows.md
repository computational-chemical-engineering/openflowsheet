# Brief — automate releases: a private release workflow and a public publish workflow

**To:** `opus-engineer` (build lane). **From:** the session, 2026-10-03. **Branch:** a new branch `release-automation`
from `main` (`2a96726`); the session merges it.
**Decision (Frank, 2026-10-03):** releases are made by GitHub workflows. One-time setup and the approval click stay
with Frank; everything else is automated and refuses to run unless the release gate says YES.

## The setup this targets (Frank does it once; document it, don't do it)

- The current private repository is renamed `computational-chemical-engineering/openflowsheet-dev` (private, full
  history, the authority). A new **public** repository `computational-chemical-engineering/openflowsheet` receives one
  squashed commit per release (no development history — Frank's decision, R-… "squash at release"; the pre-public audit
  found the pre-redaction V17 transcripts in history).
- The private repo holds a secret `PUBLIC_REPO_DEPLOY_KEY` (the private half of a deploy key with write access on the
  public repo).
- PyPI has a **pending trusted publisher** for project `openflowsheet`: owner `computational-chemical-engineering`,
  repository `openflowsheet`, workflow `publish.yml`, environment `pypi`.
- GitHub environments with Frank as required reviewer: `release` (private repo), `pypi` (public repo).

## Deliverables

1. **`scripts/release_snapshot.py`** (testable logic the workflow calls):
   - `check`: run `scripts/v0_1_gate.py --rc <C>` at the target commit and require exit 0 and the line
     `v0.1.0 tag may be proposed: YES` (generalize the version in the expected line if the script prints it); require
     `pyproject.toml`'s version == the requested version; refuse otherwise with a clear message.
   - `build`: given the tagged commit and a path to a clone of the public repo (possibly empty), produce one commit on
     the public `main` whose tree is exactly the tagged tree minus an exclusion list (`release/public-exclude.txt`,
     gitignore-style; initially only `.github/workflows/release.yml` — the private-only workflow — plus anything Frank
     lists later), whose parent is the previous public release commit (none for the first), with a fixed author
     ("OpenFlowsheet release <e.a.j.f.peters@tue.nl>"), commit date = the tagged commit's date (reproducible), message
     `OpenFlowsheet vX.Y.Z` + one line naming the development commit id; and an annotated tag `vX.Y.Z` on it. No
     history from the private repo may enter the public one (verify: the public commit's ancestry contains only earlier
     release snapshots).
   - Tests (`tests/test_release_snapshot.py`) with temporary git repos: first release (orphan), second release (parent =
     first, tree replaced exactly, deletions propagate), exclusion list honoured, refusal when the gate says NO or the
     version mismatches, no private commit reachable from the public ref, reproducible (same inputs → same commit id).
2. **`.github/workflows/release.yml`** (private repo; `workflow_dispatch` only; inputs `version`, `rc_commit`, `ref`
   (default `main`), `dry_run` (default **true**); `environment: release`; runs only if
   `github.repository == 'computational-chemical-engineering/openflowsheet-dev'`): checkout with full history; install
   from `requirements.lock` as needed; `release_snapshot.py check`; create the annotated tag `vX.Y.Z` in the private repo;
   clone the public repo over SSH with the deploy key; `release_snapshot.py build`; if not `dry_run`, push the private
   tag and the public `main` + tag; always upload the snapshot's file list and the would-be commit id as an artifact.
3. **`.github/workflows/publish.yml`** (lives in the tree, so it reaches the public repo through the snapshot; triggered
   by `push` of tags `v*`; runs only if `github.repository == 'computational-chemical-engineering/openflowsheet'`):
   job `build` — check the tag equals the package version, build sdist + wheel (reuse `scripts/t08_dist.py` if it works
   standalone in the snapshot, else `python -m build` with the lock's build backend pin), upload as artifact; job
   `pypi` — `environment: pypi`, `permissions: id-token: write`, `pypa/gh-action-pypi-publish` **pinned by commit SHA**;
   job `github-release` — create the GitHub release with the CHANGELOG section for that version as notes
   (`scripts/changelog_section.py vX.Y.Z`, tested). Pin every third-party action by commit SHA.
4. **`docs/RELEASING.md`**: the one-time setup (the four bullets above, as click-by-click steps including how to make the
   deploy key with `ssh-keygen`), and the per-release procedure (dispatch with `dry_run: true`, inspect the artifact,
   dispatch with `dry_run: false`, approve in the `release` environment, then approve in `pypi`), plus how to roll back
   (yank on PyPI; delete a public tag) and what the workflows refuse.
5. Lint the workflows (`actionlint` if installable into a scratch location without touching the project venv; otherwise
   YAML-parse them in a test and check the required keys/guards).

## Rules

Do not touch the release-checked trees (ADR 0021 D2.4: `src/`, `schemas/`, `benchmarks/`, `requirements.lock`,
`pyproject.toml`, `MANIFEST.in`, `README.md`, `LICENSE`, `NOTICE`) — the gate must stay YES for `C` = `67c66d9`; confirm
with `scripts/v0_1_gate.py --rc 67c66d98587f23bd7dfe8da28a8facccc92da21e` at your final commit. Nothing is pushed,
tagged or published by you; no network writes. Commit on `release-automation` (messages ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`); stage named paths only. Run
`rm -rf .ruff_cache && PATH="$PWD/.venv/bin:$PATH" ./scripts/check.sh` once at the end and quote its final line.

## Report

Commits; how each refusal is enforced; the dry-run you could perform locally (the snapshot built from `a3bc534` into a
scratch "public" repo: commit id, file count, excluded paths); the gate's output at your final commit; `check.sh`'s
final line; anything Frank must know before the setup.
