# S17 build decisions (append-only)

Package S17, code-health campaign 1 on `src/openflowsheet/application/`. Build lane. Tooling and rules:
`docs/code-health.md`.

## 2026-11-12, WO-1: tooling, baseline, gate trial

- **DECISION D1. Pin cce-code-health at `0cf99531041dce8cef69e2905b552b2d3072db70`**, not the brief's first
  `3c001f0a`: the code_health session's update (self-test counts behaviour command tiers; `behaviour = false`).
- **DECISION D2. complexipy pinned by version (`==8.3.0`) in `requirements-codehealth.txt`.** The tool requires
  `complexipy>=8`, and complexipy computes every cognitive-complexity number behind the debt scores, so a floating
  version would move the baseline. Hashes are impossible in a file with a VCS URL (pip's hash mode is all or nothing).
- **DECISION D3. Tier commands find the project environment through the git common directory**
  (`$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.venv`, override `OPENFLOWSHEET_VENV`).
  Command tiers run in the head worktree, where `.venv/bin/...` does not exist; an absolute workstation path would not
  travel. Every Python tier sets `PYTHONPATH=src`, because the `.venv`'s editable install points at the main checkout
  (measured: without it, `import openflowsheet` in a worktree resolves to `/home/.../OpenFlowsheet/src`).
- **DECISION D4. The `mypy` tier is unrestricted** (`mypy`, the `files` of `pyproject.toml`, as `scripts/check.sh`).
  Measured: 42 s cold, under 1 s warm (6 to 10 s in the gate trials); a restricted run would not check the callers of a
  changed private helper, which `public_api` does not protect.
- **DECISION D5. No campaign-cadence tier.** CLAUDE.md runs `scripts/gate.sh` only before a release-candidate cut and
  makes CI green on both architectures the merge condition; CI is the campaign-end check. A `gate.sh` tier would also
  run the whole suite inside every self-test (self-test selects cadence `campaign`).
- **DECISION D6. No machine-readable baseline committed.** The tool has no baseline file under `.codehealth/`: `diff`
  and `gate` compare against the merge-base, never a stored baseline. The numbers below regenerate with the commands
  given.
- **DECISION D7. Gate trials ran against base `db0e29e4`** (this branch's config commit), not `6d195c49`. The gate reads
  the config and runs `frozen_cmd` at the base, and `6d195c49` has neither; against it the gate fails `config`
  ("refactor mode needs a reference or command tier"), `forbid` (`.codehealth/config.toml`) and `scope`. `application/`
  is byte-identical at both commits. The trials used `--config` with `keep_going = true` added, so every tier reports
  (a trial exits 3 when it passes; these exit 1).
- Note: the brief's frozen patterns `src/openflowsheet/**/*.md` and `**/*.yaml` need a directory below
  `src/openflowsheet/`; a file directly in it is not matched. Harmless: scope admits only `.py` under `application/`.

### Baseline at `6d195c49` (codehealth 0.2.0.dev0 @ 0cf99531, profile `python@0`, complexipy 8.3.0)

    codehealth scan --top 100 --json scan.json                  # application/ (this config)
    codehealth scan --ref 6d195c49 --json scan_repo.json        # repo-wide (no config at 6d195c49: every .py)
    codehealth hotspots --top 100                               # application/; repo-wide from a worktree of 6d195c49
    codehealth diff --base 6d195c49 --head HEAD                 # DIFF PASS, 1 touched file, debt 0.00 -> 0.00

Totals (health is NLOC-weighted; debt is the gated quantity):

| scope | files | NLOC | debt | debt/kNLOC | health | fns with debt | brain fns | file smells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `src/openflowsheet/application/` | 39 | 17939 | 855.0 | 47.66 | 7.22 | 93/988 | 6 | 7 |
| `src/` | 277 | 99486 | 6924.1 | 69.60 | 7.05 | 592/4675 | 50 | 62 |
| repository (every `.py`) | 1191 | 422533 | 26489.5 | 62.69 | 7.18 | 1989/21772 | 158 | 196 |
| application/'s four CodeScene hotspots | 4 | 5260 | 342.9 | 65.19 | 4.32 | 29/259 | 4 | 3 |
| application/'s top 10 by rank | 10 | | | | 5.69 | | | |

Next to CodeScene (code_health's report): overall 7.07 (codehealth: application/ 7.22, src/ 7.05, repository 7.18);
hotspots 4.43 (codehealth: the four files below 4.32, application/'s top 10 hotspots 5.69). The two scales are not the
same metric. codehealth's five lowest-health files in `application/` are `revision_run.py` 1.80,
`revision_binding.py` 4.70, `local.py` and `binding.py` 5.00, `coupled_run.py` 5.20: CodeScene's four plus
`binding.py`, in a different order (CodeScene ranks `local.py` worst; codehealth ranks `revision_run.py` worst, far below
the rest).

| file (`application/`) | CodeScene | codehealth health | debt | NLOC | commits | rank | brain | file smells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `local.py` | 3.97 | 5.00 | 37.7 | 1739 | 33 | 1244 | 0 | large_file |
| `revision_run.py` | 4.04 | 1.80 | 136.0 | 1026 | 19 | 2584 | 2 | large_file |
| `coupled_run.py` | 4.10 | 5.20 | 83.8 | 942 | 14 | 1173 | 1 | |
| `revision_binding.py` | 4.12 | 4.70 | 85.4 | 1553 | 22 | 1879 | 1 | large_file |

All 39 files, worst debt first:

| file | NLOC | debt | health | commits | rank | brain | file smells |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| revision_run.py | 1026 | 136.0 | 1.80 | 19 | 2584 | 2 | large_file |
| binding.py | 856 | 134.2 | 5.00 | 3 | 403 | 1 | |
| revision_binding.py | 1553 | 85.4 | 4.70 | 22 | 1879 | 1 | large_file |
| coupled_run.py | 942 | 83.8 | 5.20 | 14 | 1173 | 1 | |
| validation.py | 897 | 57.9 | 6.30 | 9 | 521 | 0 | |
| jobs/model.py | 217 | 54.2 | 8.20 | 4 | 217 | 1 | |
| transactions.py | 241 | 47.0 | 8.00 | 2 | 94 | 0 | |
| local.py | 1739 | 37.7 | 5.00 | 33 | 1244 | 0 | large_file |
| jobs/executor.py | 458 | 37.0 | 8.50 | 2 | 74 | 0 | |
| stream_table_format.py | 378 | 35.0 | 7.80 | 3 | 105 | 0 | |
| cli.py | 853 | 30.6 | 8.70 | 17 | 520 | 0 | |
| jobs/runner.py | 940 | 29.7 | 8.20 | 16 | 475 | 0 | |
| operations.py | 599 | 18.0 | 8.60 | 10 | 180 | 0 | |
| replacement.py | 563 | 17.0 | 8.50 | 6 | 102 | 0 | |
| revision_continuation.py | 352 | 13.0 | 9.10 | 2 | 26 | 0 | |
| projection.py | 207 | 7.0 | 8.80 | 1 | 7 | 0 | |
| store.py | 1062 | 5.5 | 8.10 | 8 | 44 | 0 | large_file |
| admission.py | 336 | 5.0 | 9.30 | 7 | 35 | 0 | |
| capabilities.py | 258 | 5.0 | 9.50 | 4 | 20 | 0 | |
| revision_routes.py | 85 | 4.0 | 8.80 | 1 | 4 | 0 | duplication |
| stream_table.py | 869 | 4.0 | 9.30 | 9 | 36 | 0 | |
| jobs/worker.py | 169 | 3.0 | 9.60 | 2 | 6 | 0 | |
| authz.py | 293 | 2.0 | 9.80 | 6 | 12 | 0 | |
| contract.py | 179 | 2.0 | 8.60 | 9 | 18 | 0 | duplication |
| types.py | 1531 | 1.0 | 9.00 | 16 | 16 | 0 | large_file |
| 14 files with debt 0 (`__init__.py`, `bindings/{__init__,http,mcp,web}.py`, `column_binding.py`, `jobs/{__init__,interrupt}.py`, `policies.py`, `revisions.py`, `serving.py`, `structure_index.py`, `thermal_binding.py`, `trust_region_parent.py`) | 1196 | 0.0 | 10.00 | | | 0 | |

Repository hotspots (top 5 by commits x debt): `docs/derivations/scripts/m06_w27_registration.py` 4586,
`src/openflowsheet/models/syn001/column.py` 4235, `docs/derivations/scripts/s10_reference.py` 3886,
`src/openflowsheet/orchestrator/region.py` 3740, `src/openflowsheet/studies/trust_region/projection.py` 3002;
`application/revision_run.py` is sixth (2584), `application/revision_binding.py` eleventh (1879).

### Gate trial (base `db0e29e4`, trial config with `keep_going = true`)

| trial | config | frozen | forbid | scope | literals | public_api | debt | ruff | mypy | tests | f0 | mcp_digest | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| empty diff (committed config) | FAIL "nothing to gate (empty diff)" | ok | ok | ok | ok | ok | 0.0 -> 0.0 | not run | | | | | FAIL, by design |
| refactor: extract `_semantic_content` from `revisions.content_hash` | ok | ok | ok | ok | ok | ok | 0.0 -> 0.0 | ok | ok 6.2 s | FAIL exit 2 (no `scripts/test_impact.py`) | ok 40.6 s | ok 13.7 s | FAIL (tests only) |
| behaviour: `owner_instance=None` in `local.py::_context` | ok | ok | ok | ok | ok | ok | 37.7 -> 37.7 | FAIL (format) | FAIL (arg-type: `None` for `str`) | FAIL exit 2 | ok, F0 PASS: not caught | ok: not caught | FAIL |

The behaviour change is caught only by the non-behaviour tiers (ruff format, mypy). F0 and the MCP digest do not catch
it. The tests that would (measured by hand, `PYTHONPATH=src pytest` on the six test files naming `owner_instance`):
4 failed, 273 passed with the change; the three failing files pass at the base (41 passed). So the `tests` tier
catches it once S16 selects any of `test_t07_w6a_http.py`, `test_t07_adr0008_mcp.py`, `test_t07_adr0008_jobs.py`.

### Self-test (committed config at `db0e29e4`)

`codehealth gate --self-test --mutate src/openflowsheet/application/revision_run.py:1078` mutates `"0" * 64` to
`"0" * 65` in `registered_flowsheet` (the K06 CLI's model version). Result: `SELF-TEST PASS`, exit 0, "1/3 reference
tiers detected the mutation": `tests` "detected" (exit 2: the missing S16 script), `f0` missed (41.9 s),
`mcp_digest` missed (13.7 s); ruff and mypy passed and do not count (`behaviour = false`). The PASS is vacuous: the
only detecting tier fails at the unmutated HEAD as well. No test names `K06-cli@`, so this literal is not covered by
F0, the digest, or (by grep) any test. Re-run the self-test once S16 lands.

- **DECISION D8 (2026-11-12). Re-pin cce-code-health at `83614510eae16f11dd595b1fcd38c27b43703837`** (code_health's
  fix of the seven tool issues WO-1 reported: self-test runs every behaviour tier unmutated first and fails if one
  fails; `codehealth config --check`; `[gate] prefix` with `{gitdir}`; one path matcher). Until S16's
  `scripts/test_impact.py` is on this branch, the self-test fails by design ("tier tests fails without mutation").
  Alternative: keep 0cf99531, whose self-test PASS at WO-1 was vacuous. Reversible by: the pin line.
- **DECISION D9 (2026-11-12). Every gate tier gets a `timeout`** (ruff 300 s, mypy 900, tests 3600, f0 1800,
  mcp_digest 600). S16's recall hung 5 h on the mutation `owner_instance=None`: `store.start_job` fences on
  `owner_instance = ?`, which never matches NULL, so `executor._run` returns, the job stays queued and
  `_wait_until_ended` waits with `math.inf`. A step or a self-test mutation can do the same; a timeout fails the tier
  (exit 124). `tests` runs serially (`test_impact.py run` has no workers option), so its limit is the widest.
  The tool kills only the tier's shell on a timeout (reported to code_health). Alternative: no limits and a watchdog.
  Reversible by: the five `timeout` lines.
- **DECISION D10 (2026-11-12). Re-pin cce-code-health at `7628e7375cb9ce9574f5a54b8811b99c9314169e`** (code_health's
  fix of the timeout orphan issue reported with D9: a tier runs in its own session; on a timeout or interrupt the gate
  sends SIGTERM to the process group, then SIGKILL after 5 s, and kills stragglers of a tier that ended normally;
  timeout stays exit 124; 72 tool tests pass, 3 new). Installed as 0.1.1.dev14+g7628e7375; `config --check` OK.
  The tool's `frozen_cmd` has no timeout (a quick git-level check). Alternative: stay on 83614510 and rely on a
  watchdog. Reversible by: the pin line.
- **DECISION D11 (2026-11-13). The `tests` tier runs S16's selection in `.venv-testmap` with 12 workers, a 900 s
  per-test limit and the map of the campaign base** (`run --base "${OFS_MAP_BASE:-{base}}" --workers 12 --
  --timeout=900`). A map takes about 70 min (20284 tests at a9e733e4), so one map per step base is too slow; a map of
  the campaign base serves every step while that base is an ancestor of `HEAD` (docs/test-impact.md), and the
  selection, cumulative since the campaign base, is a superset of the step's own, so it stays sound and grows only
  with the campaign. `OFS_MAP_BASE` cannot live in the config: the config commit is itself the campaign base. The
  test-map venv has pytest-xdist (the main `.venv` has not) and pytest-timeout (B-9 of S16: a hung test fails, named,
  inside the tier's 3600 s). This supersedes D9's "`tests` runs serially". Alternative: per-step maps, or the main
  `.venv` serially (a fallback would take over an hour). Reversible by: the `tests` tier's `cmd` line.
- **DECISION D12 (2026-11-13). No file is added to the tree between the campaign base and the campaign end.** S16's
  `select` falls back to the full suite when any file was added since the map's base (tests list and glob trees), and
  with `OFS_MAP_BASE` every change since the campaign base counts. So `.codehealth/playbook.md` is committed as a stub
  before the campaign base, work orders live in `$(git rev-parse --git-common-dir)/codehealth/briefs/` like the run
  log, and both are copied into the tree at campaign end. Edits of existing files (state file, playbook, decisions)
  are fine: a changed non-Python file selects the tests that opened it. A step's gate base is `HEAD` just before the
  step. Alternative: rebuild the map after each addition (70 min). Reversible by: this entry and the skill text.
- **DECISION D13 (2026-11-13). Re-pin cce-code-health at `5646ad1af337ead0a2cf26578e6545de34ac4d94`** (code_health's
  answer to S17's feedback, 88 tool tests): `{ref_base}` in tier commands, so the `tests` tier reads the campaign base
  from `gate --ref-base` instead of `OFS_MAP_BASE`; `detect_exit = [1, 124]` on `tests`, `f0` and `mcp_digest` (in the
  self-test any other nonzero exit is an error, not a detection); `--require-gain` (exit 0 means accept: debt over
  the touched files strictly lower); `codehealth log` writes the run-log line from the gate JSON; exit codes,
  `debt_before`/`debt_after` and `head_tree` in the gate JSON; `end_line` and `qualname` in the scan. Installed as
  0.1.1.dev16+g5646ad1af. Work order 1 ran on 7628e737; its gate JSONs lack `head_tree`, so its two review-reject
  lines were written by script from the engineer's lines. Alternative: stay on 7628e737 with `OFS_MAP_BASE` and
  hand-written log lines. Reversible by: the pin line, the tier `cmd` and `detect_exit` lines, gate.sh.
- **DECISION D14 (2026-11-13). Commit, then gate.** `tests/test_m07_journey.py::test_a21_the_carry_identity_...` fails
  whenever `src/openflowsheet` has uncommitted changes (`carry_identical` in `scripts/m07_journey.py` needs a clean
  tree), so a step gated on an uncommitted tree always fails the `tests` tier. Work order 1's engineer found it and
  committed each step provisionally, gated it against the last accepted commit, and reset (`git reset --hard`) on a
  failure; no failed step is in history. Adopted as the rule. It also fits `codehealth log`, which requires HEAD's tree
  to equal the judged tree. Alternative: exclude the test from the tier (a weaker gate) or make the test tolerate a
  dirty tree (a test change, outside a refactor campaign). Reversible by: the "Git" section of `docs/S17_RULES.md`.
- **Review 1 (2026-11-13, reviewer agent):** 12 steps of work order 1 (8df70461..5d46d5fb): 10 accepted, 2 rejected
  for readability (b29aea3c mutual recursion; 5d46d5fb a helper bundling two unrelated post-steps); no behaviour
  difference found. Both reverted in 76a00379 (conflicts with the later step f1646388 resolved to the pre-step code;
  `_constants_for_shape` byte-identical to before b29aea3c); behaviour tiers on 76a00379: selection 113 files 3490
  passed, F0 PASS, MCP digest 40 passed; ruff, mypy clean. Full verdict: `<git-common-dir>/codehealth/runs/s17-review1.md`.
