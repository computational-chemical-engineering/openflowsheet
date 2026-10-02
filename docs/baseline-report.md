# P00 baseline inspection report

**Work package:** P00 — inspect repository, baseline tests and instructions; record blueprint
hash; bootstrap package and progress/requirements ledger (implementation plan §4.1).
**Lead model:** Opus 5. **Reviewer:** Fable 5.1 (not yet performed).
**Branch:** `wp/P00`.
**Date of inspection:** 6 September 2026.

This report records the repository exactly as found, before any P00 change, and the environment
the bootstrap was built and checked in. Every command below was actually run; its output is
reproduced or summarized faithfully.

## 1. Repository state at start

Inspected in an isolated git worktree of the repository. The worktree branch was renamed to
`wp/P00` before any file was created (`git branch -m wp/P00`).

```
$ git status
On branch worktree-agent-a3364ad8d313a48fd
nothing to commit, working tree clean

$ git log --oneline -5
292f8fe Baseline: blueprint v3.1, implementation plan v1.1, working rules

$ git branch --show-current
worktree-agent-a3364ad8d313a48fd     # renamed to wp/P00
```

The repository contained exactly one commit and eight tracked files. Full inventory with exact
byte sizes (`find . -path ./.git -prune -o -type f -printf "%s %p\n"`):

| Bytes | Path |
| ---: | --- |
| 5277 | `CLAUDE.md` |
| 287 | `.gitignore` |
| 88151 | `docs/blueprint-v3.1.md` |
| 53353 | `docs/implementation-plan.md` |
| 56064 | `docs/design-history/blueprint-v1.md` |
| 107166 | `docs/design-history/blueprint-v2.md` |
| 73918 | `docs/design-history/blueprint-v3.md` |
| 43525 | `docs/design-history/implementation-plan-v1.0.md` |

There was no `src/`, no `tests/`, no `schemas/`, no `benchmarks/`, no `examples/`, no
`evidence/`, no `docs/adr/`, no `docs/progress.md`, no `docs/requirements.yaml`, no
`pyproject.toml`, no packaging metadata, and no CI configuration.

The pre-existing `.gitignore` (287 bytes) already ignored `.venv/`, the usual Python build and
cache directories, and — significantly — `evidence/**/artifacts/`, `*.h5`, and `*.npz`. It was
left unmodified; the evidence layout documented in `evidence/README.md` was written to match it
rather than the reverse.

## 2. Baseline tests

**None.** There was no test directory, no test file, no test runner configuration, and no CI
workflow in the starting repository. There was therefore no baseline test result to preserve or
compare against, and nothing to regenerate. The four test modules added by P00
(`tests/test_document_hashes.py`, `tests/test_package_imports.py`,
`tests/test_requirements_ledger.py`, `tests/test_evidence_manifests.py`) are the first tests in
this repository.

## 3. Document hashes

```
$ sha256sum docs/blueprint-v3.1.md docs/implementation-plan.md CLAUDE.md
66f574b07e86a89962236f4a48850e733f3c03379a3a55caf78ef30f7915e8aa  docs/blueprint-v3.1.md
86b652dadde6be9223105ee00ffa1afe121870278ffd60ae769427785bf4ca23  docs/implementation-plan.md
6c54f965234476176c9fe25a76d2d60f6b3db9c72af5f318c7784ee6cf4381d4  CLAUDE.md
```

| Document | SHA-256 | Status |
| --- | --- | --- |
| `docs/blueprint-v3.1.md` | `66f574b07e86a89962236f4a48850e733f3c03379a3a55caf78ef30f7915e8aa` | **Matches** the `**Baseline SHA-256:**` value recorded in the `docs/implementation-plan.md` header |
| `docs/implementation-plan.md` | `86b652dadde6be9223105ee00ffa1afe121870278ffd60ae769427785bf4ca23` | Recorded here and in `docs/requirements.yaml`; the plan does not record its own hash |
| `CLAUDE.md` | `6c54f965234476176c9fe25a76d2d60f6b3db9c72af5f318c7784ee6cf4381d4` | Recorded here only |

The blueprint hash agrees with the plan header, so the architectural authority is the document
the execution plan was written against. `docs/requirements.yaml` records the blueprint and plan
hashes, and `tests/test_document_hashes.py` and `tests/test_requirements_ledger.py` re-check
both the file hash and the plan-header value on every run, so a silent edit to either
authoritative document breaks the build.

Plan version parsed from the same header: **1.1**.

## 4. Environment

| Item | Value |
| --- | --- |
| OS | Debian GNU/Linux 13 (trixie), kernel `6.12.86+deb13-amd64`, `x86_64` |
| Python | 3.13.5 (`main`, Jun 13 2026, 14:18:01) `[GCC 14.2.0]` at `/usr/bin/python3` |
| git | 2.47.3 |
| make | GNU make, `/usr/bin/make` |

System-wide Python packages present before P00
(`python3 -c "import importlib.metadata ..."`):

| Package | Version |
| --- | --- |
| numpy | 2.2.4 |
| scipy | 1.15.3 |
| pytest | 8.3.5 |
| mypy | 1.15.0 |
| PyYAML | 6.0.2 |
| jsonschema | 4.19.2 |
| setuptools | 78.1.1 |
| pip | 25.1.1 |

Absent system-wide: `ruff`, `uv`, `pip-tools`. `python3 -m venv` works and PyPI is reachable.

Consequences for the bootstrap, all consistent with implementation plan §2 ("Pin exact working
versions in the implementation environment; do not select a package version solely because it
is newest"):

- The build backend is **setuptools** (already present at 78.1.1); no new build-time dependency
  was introduced.
- Runtime dependencies are pinned to the exact versions already validated on this machine:
  `numpy==2.2.4`, `scipy==1.15.3`, `pyyaml==6.0.2`, `jsonschema==4.19.2`.
- The `dev` extra pins `pytest==8.3.5`, `mypy==1.15.0`, `ruff==0.12.11` (the first ruff ever
  installed for this project; nothing pre-existing constrained the choice),
  `types-PyYAML==6.0.12.20260906`, `types-jsonschema==4.26.0.20260518` — each pinned to the
  version actually installed and checked here.
- CasADi, Pyomo, PyNumero/ASL and cyipopt are **not** dependencies. The backend is undecided
  until the P02 spike and the P03 ADR; adding either candidate now would prejudge that decision.

## 5. Environment reproduction

```
$ python3 -m venv .venv
$ .venv/bin/python -m pip install --upgrade pip        # pip 25.1.1 -> 26.2.1
$ .venv/bin/python -m pip install -e '.[dev]'
Successfully installed attrs-26.1.0 iniconfig-2.3.0 jsonschema-4.19.2
jsonschema-specifications-2025.9.1 mypy-1.15.0 mypy_extensions-1.1.0 numpy-2.2.4
packaging-26.3 pluggy-1.6.0 process-runtime-0.0.0.dev0 pytest-8.3.5 pyyaml-6.0.2
referencing-0.37.0 rpds-py-2026.6.3 ruff-0.12.11 scipy-1.15.3
types-jsonschema-4.26.0.20260518 types-PyYAML-6.0.12.20260906 typing_extensions-4.16.0
$ make lock            # .venv/bin/python -m pip freeze --exclude-editable > requirements.lock
```

`.venv/` is gitignored by the pre-existing `.gitignore`. `requirements.lock` is committed and
carries a header giving the Python version and the generation command; it is the environment
that `.github/workflows/ci.yml` installs and that every evidence manifest hashes as
`inputs.environment_lock_hash`.

## 6. Verification run

```
$ make check      # PATH=.venv/bin:$PATH ./scripts/check.sh
=== ruff check: ruff check . ===
All checks passed!
--- ruff check: exit 0
=== ruff format: ruff format --check . ===
15 files already formatted
--- ruff format: exit 0
=== mypy: mypy src ===
Success: no issues found in 10 source files
--- mypy: exit 0
=== pytest: pytest -q ===
...ssssss.........................                                       [100%]
28 passed, 6 skipped in 0.14s
--- pytest: exit 0
=== check.sh: PASSED ===
```

The six skips are the parametrized evidence-manifest checks at the moment they were first run:
no manifest existed yet, so the parameter set was empty. They become real cases as soon as
`evidence/P00/<commit>/manifest.json` is committed, and the suite was re-run after that commit;
the P00 evidence manifest records both runs with their exit codes.

## 7. Statement on user work

**No user work was overwritten.** Every pre-existing file — `CLAUDE.md`, `.gitignore`,
`docs/blueprint-v3.1.md`, `docs/implementation-plan.md`, and the four files under
`docs/design-history/` — is byte-identical to its state at commit `292f8fe`. P00 added new files
only; it modified and deleted none. This can be checked directly:

```
$ git diff --stat 292f8fe -- CLAUDE.md .gitignore docs/blueprint-v3.1.md \
      docs/implementation-plan.md docs/design-history/
```

The pre-existing `.gitignore` conventions were adopted rather than replaced, and the work was
done in an isolated worktree on `wp/P00`, so no other branch was touched.

## 8. What P00 deliberately did not do

- **No LICENSE file.** `pyproject.toml` declares `license = "Apache-2.0"` as the intent recorded
  in blueprint §15, but blueprint §15 also states that adoption requires that the project has
  the rights to distribute its contributions, and that the license text is authoritative rather
  than any design summary. Adding the text is Frank's call; the item is carried in
  `docs/progress.md` under "Notes for Frank".
- **No scientific semantics.** Units, state and zero-flow conventions, SYN-001, and the oracle
  are P01 and Fable-led. The nine subpackages contain a docstring and nothing else.
- **No `benchmarks/registry.yaml`, no ADRs, no `docs/support-matrix.md`.** These belong to P01
  and later packages; creating them empty now would be a placeholder.
- **No backend dependency and no `studies`, `adapters`, client, or web packages.** Plan §2:
  empty future service packages are unnecessary.
- **No CI run.** The workflow file is committed but has not executed; the P00 evidence manifest
  records this as a limitation, and the checks reported above are single-platform and local.
