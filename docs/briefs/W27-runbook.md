# W27 runbook — WO-17 at C_W (M07 spec §9; registration W27-R31, R33, R58; approval `docs/V02_DECISIONS.md` P1)
Spends money: Frank's approval is USD 15–45. Order: (a) coverage, (b) draw, (c) canaries, (d) preflight + 45 runs, (e) scores.
**Setup** at the clean C_W checkout (repo root): `export PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH C=w27-m07-<C_W short sha>`;
`R=benchmarks/m06/openidaes450/runs/$C; W=/tmp/w27-work-$C` (outside the repo); `T=<0600 token file>` (`claude setup-token`
output or a credentials file; operator isolation, W27-R33); `M=<exact model id>`; `V=<Claude Code version, e.g. 2.1.302>`.
- `M`: "the most recent Claude model at campaign time, by exact id" (W27-R33; aliases and `claude-sonnet-5` are refused).
  2.1.302's compiled catalog lists e.g. `claude-opus-5-5`, `claude-fable-5-1`, `claude-mythos-5-1`: which is "most recent" is the session's call.
- Archive: a **real, ignored** directory, never a symlink (an untracked link dirties the tree: P8 fails, `tree_clean` false):
  `mkdir -p evidence/M06/W27/artifacts && cp -al <a worktree holding it>/evidence/M06/W27/artifacts/{OpenIDAES-450-demo.tar.gz,extracted} evidence/M06/W27/artifacts/`.
  (The gate is the other way round: it needs the symlink — `tests/test_m07a_harvest.py` fails on the real directory.)
- Nothing is committed between (a) and the end of (d): P3 requires `coverage.json` made at HEAD; `runs/` is outside the
  tree-clean check, everything else must be clean.

**(a) Coverage at C_W** (W27 clause (a)): `mkdir -p $R && python -m benchmarks.m06.w27.coverage --out $R/coverage.json`
— expect exit 0, `G14 PASS`, `CANDIDATE: 0` of 450 and of 82; anything else: stop, design lane.
**(b) Seeded draw:** `python -m benchmarks.m06.w27.sample $R/coverage.json --out $R/sample.json` (45 cases, 3 canaries).
It precedes the canaries because W27-R31 defines them as frame cases *not* in the sample (see the open question on M07.A50).
**(c) Canaries:** `python -m benchmarks.m06.w27.harness canaries --campaign $C --model $M --work $W --oauth-token-file $T`
— records `$R/canary/0k-<case>/`; exit 0 iff all three pass; the printed `init_model`, `init_claude_code_version` are the
pins (use them as `$M`, `$V`). A failed canary: stop and report (re-canary, Q3, is not implemented: P6 counts exactly three).
**(d) Preflight, then the runs:**
`python -m benchmarks.m06.w27.harness preflight --campaign $C --model $M --claude-code-version $V > $R/preflight.json`
(exit 0 iff P1–P8 all pass); then, in the background (45 sessions, ≤ 1800 s wall each):
`python -m benchmarks.m06.w27.harness campaign --campaign $C --model $M --claude-code-version $V --work $W --oauth-token-file $T`
— re-runs the preflight, then `$R/NN-<case>/` in `run_order` (run.json, prompt.txt, transcript.jsonl, result.json,
store-export.json, scores.json), then `$R/campaign.json`. It stops at a run outside the configuration (kept; counts), and
before any run whose `--max-budget-usd 5` cap would take the recorded spend past `--spend-ceiling-usd` (default 45).
**Stop:** kill the process; the run in flight keeps its directory (never re-run). **Resume:** the same command with `--resume`
(no preflight; runs only missing directories, in order).
**Spend:** `python -m benchmarks.m06.w27.harness spend --campaign $C` — sum of `total_cost_usd` over every `result.json`
(canaries included; Claude Code's subscription estimate, `cost_basis`); `uncosted` lists runs with no recorded cost.
**(e) Scores:** each run is scored as it ends; re-score one: `python -m benchmarks.m06.w27.scorer $R/NN-<case> --coverage $R/coverage.json`;
`campaign.json` (W27-R53…R56) is written at the end of (d); a resumed campaign writes it when the last run is done.
**Committing the records** (`$R`, never the archive): only together with the U14 rewrite — `test_u14_…` fails on any
`/runs/` path today (R-194 "rewritten with the campaign"); R58's `confirmation/` record of an empty C has no writer yet.
