# Code health: tooling and refactor-campaign rules

S17 set this up for code-health campaign 1 on `src/openflowsheet/application/`. Decisions and the baseline are in
`docs/S17_DECISIONS.md`.

## The tool

[cce-code-health](https://github.com/computational-chemical-engineering/cce-code-health) provides the `codehealth`
command: per-function debt (cognitive complexity, size, nesting, bumpy road, parameters, boolean operators; profile
`python@0`), a 1..10 health value for display, hotspots (commits x debt), a debt ratchet (`diff`) and a behaviour gate
(`gate`). Its scores are an open-source proxy, not CodeScene's Code Health.

It is a development tool. It is not a package extra, never ships in the wheel and is never imported by `src/`.
`requirements-codehealth.txt` pins it by commit SHA (pip's hash mode cannot take a VCS URL) and pins its one
dependency, complexipy, by version; the file is outside the release identity (R-140: run manifests record
`requirements.lock`'s hash only). Install it in its own environment next to the project's `.venv`:

    python3.13 -m venv .venv-codehealth
    .venv-codehealth/bin/python -m pip install -r requirements-codehealth.txt
    .venv-codehealth/bin/codehealth --help

After a re-pin, add `--force-reinstall --no-deps` to the install line: before cec6dbe the tool's version string did
not change between commits, so pip kept the old build (since then it carries the commit, e.g. 0.1.1.dev14+g7628e7375). `pip freeze | grep cce` shows the installed commit.

`scan`, `diff` and `hotspots` are static: they read files through git and need no OpenFlowsheet install. `gate` runs
the tiers below, which call the project environment themselves.

    .venv-codehealth/bin/codehealth scan                          # in-scope files, worst first
    .venv-codehealth/bin/codehealth hotspots --top 20
    .venv-codehealth/bin/codehealth diff --base origin/main       # ratchet: exit 1 if debt rises
    .venv-codehealth/bin/codehealth gate --base <step base>       # behaviour gate for one step
    .venv-codehealth/bin/codehealth gate --self-test --mutate <path:line>

Every command prints one summary line and writes the full report with `--json FILE`. Exit codes: 0 pass, 1
regression, 2 tool error, 3 a passing trial run with `--config`.

## Configuration: `.codehealth/config.toml`

The format is the docstring of `cce_code_health/gate.py` at the pinned commit. `diff` and `gate` read the config from
the base commit, so a change cannot loosen its own gate, and a step may never touch `.codehealth/*`: change the config
in a separate commit, outside a campaign step.

- **Scope:** `src/openflowsheet/application/*` (fnmatch, `*` also matches `/`; only `.py` files). A step may touch only
  in-scope files.
- **Frozen** (a byte change fails): F0's 35 M9 modules, printed by `scripts/codehealth_frozen.py` from
  `benchmarks/f0/corpus.json` (run in the base tree), and `schemas/*`, `application/bindings/descriptions/*`,
  `messages/catalogue/*`, `src/openflowsheet/**/*.md`, `src/openflowsheet/**/*.yaml`, `benchmarks/f0/*`.
- **Forbidden** in a step: `tests/*`, `benchmarks/*`, `requirements*`, `pyproject.toml`, `evidence/*`, `schemas/*`.
- **Static rules:** string literals of touched files unchanged (multiset); public API unchanged (names, signatures,
  decorators, module constants, `__all__`, re-exports, class fields); debt over the touched files may not rise.
- **Determinism pins** (`[gate.env]`): `PYTHONHASHSEED=0`, `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
  `MKL_NUM_THREADS` = 1.

### Gate tiers (all `kind = "command"`, cadence `step`, run in this order)

| tier | command | behaviour |
| --- | --- | --- |
| `ruff` | `ruff check {files} && ruff format --check {files}` | no |
| `mypy` | `mypy`, unrestricted, as `scripts/check.sh` runs it | no |
| `tests` | `scripts/test_impact.py run --base {ref_base} --workers 12 -- --timeout=900` in `.venv-testmap` (S16's selection, S17 D11, D13) | yes |
| `f0` | `scripts/corpus_identity.py --check` | yes |
| `mcp_digest` | `pytest tests/test_t08_w2_surface_digest.py tests/test_m07a_surface_chain.py` | yes |

The tiers run in the tree under test, which is a worktree, so they find the project environment through the git
common directory (`<main checkout>/.venv`); set `OPENFLOWSHEET_VENV` to use another. Every Python tier sets
`PYTHONPATH=src`: the `.venv` holds an editable install of the main checkout, and without it a worktree's tests import
the main checkout's code, not the code under test. `behaviour = false` marks ruff and mypy, so a lint or type failure
never counts as the self-test detecting its mutation. The gate stops at the first failing tier unless
`keep_going = true`.

Every tier has a `timeout` (ruff 300 s, mypy 900, tests 3600, f0 1800, mcp_digest 600). A timeout fails the tier
with exit 124: a mutation or a bad step can leave a job queued and a test waiting forever (S16's recall hit this with
`owner_instance=None`). From the pinned commit 7628e73 on, the gate runs each tier in its own process group and on a
timeout sends SIGTERM to the group, then SIGKILL after 5 s, so no pytest worker survives it (S17 D10).

There is no campaign-cadence tier: CI green on both architectures is the campaign-end check (the repository runs
`scripts/gate.sh` only before a release-candidate cut).

The `tests` tier runs in the test-map venv (`.venv-testmap` next to `.venv`, docs/test-impact.md "Install";
`OPENFLOWSHEET_TESTMAP_VENV` overrides it), because only that venv has pytest-xdist and pytest-timeout. A coverage map
takes about 70 minutes to build, so a campaign builds one, at its base, and passes that commit as `--ref-base` to
every gate run (the tier reads it as `{ref_base}`):

    .venv-testmap/bin/python scripts/test_impact.py build --base <campaign base> --workers 12
    .venv-codehealth/bin/codehealth gate --mode refactor --base <last accepted> --ref-base <campaign base> --require-gain

The selection is then of every change since the campaign base, a superset of the step's own; the map stays valid
while the campaign base is an ancestor of `HEAD`. Without `--ref-base` the tier selects against the step base
`{base}` and needs a map of it (otherwise it falls back to the full suite, about 15 minutes with 12 workers).

The gate keeps its base worktree under `$(git rev-parse --git-common-dir)/codehealth/base-<sha>` and reuses it; the
self-test uses `codehealth/selftest` there and removes it. `git worktree remove --force` removes a stale base tree.

### CI

The `codehealth` job of `.github/workflows/ci.yml` installs `requirements-codehealth.txt` into a fresh environment
and runs `codehealth diff --base origin/main --head HEAD`. It is informational: `continue-on-error: true`, no tests, not
on a dispatch. Until `.codehealth/config.toml` is on `main`, `diff` uses the tool's default scope (every `.py` file).

## Campaign rules

1. **Refactor only, bitwise.** A step changes structure, never behaviour; every result stays bitwise identical. A step
   that changes a number, a message, a public name or a signature is not a refactor step.
2. **Frozen list.** F0's M9 modules and the frozen patterns above are never touched; the gate fails a step that does.
3. **F0 and the MCP digest stay unchanged at every step.** `f0` and `mcp_digest` run on every step, not only at the end.
4. **CI on both architectures before a merge.** CI green on x86-64 and aarch64 is the merge condition, as for every
   branch (CLAUDE.md); after the merge, F0 runs on `main` before the push.
5. **Selection is inner-loop only.** S16's test-impact selection (`tests` tier) speeds up a step; it never replaces
   the full suite, which CI runs on both architectures before the merge.
6. **The run log and playbook are not step content.** The campaign log lives in
   `$(git rev-parse --git-common-dir)/codehealth/runs/<campaign>.jsonl` and is copied to `.codehealth/runs/` in a
   separate docs commit at campaign end; playbook updates are separate docs commits as well.
