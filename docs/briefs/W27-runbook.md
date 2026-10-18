# W27 runbook — WO-17 at C_W (M07 spec §9, §21; registration W27-R31, R33, R58, §23 R64–R68; approval `docs/V02_DECISIONS.md` P1)
Spends money: Frank's approval is USD 15–45. Order (registration §23.2): (a) coverage, (b) draw, (b′) confirm, (c) canaries,
(d) preflight + 45 runs, (e) scores, (f) order check. Each record names the SHA-256 of the earlier ones (`order_check`).
**Setup** at the clean C_W checkout (repo root): `export PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH C=w27-m07-<short sha>`
(the commit of the campaign's *first* `coverage.json`; the name never changes, even if C_W moves);
`R=benchmarks/m06/openidaes450/runs/$C; W=/tmp/w27-work-$C` (outside the repo); `T=<0600 token file>` (`claude setup-token`
output or a credentials file; operator isolation, W27-R33); `V=<Claude Code version, e.g. 2.1.302>`.
- The model (registration §23.5): Claude Code's default on this login. The canaries read it themselves: the first attempt
  whose transcript's `init` names a model (the *pinning attempt*) and every attempt before it run without `--model`; every
  later attempt passes `--model <pin>`. `M` is that pin, read after (c). Nobody chooses it.
- Archive: a **real, ignored** directory, never a symlink (an untracked link dirties the tree: P8 fails, `tree_clean` false):
  `mkdir -p evidence/M06/W27/artifacts && cp -al <a worktree holding it>/evidence/M06/W27/artifacts/{OpenIDAES-450-demo.tar.gz,extracted} evidence/M06/W27/artifacts/`.
  (The gate is the other way round: it needs the symlink — `tests/test_m07a_harvest.py` fails on the real directory.)
- Nothing is committed between (a) and the end of (d): P3 requires `coverage.json` made at HEAD; `runs/` is outside the
  tree-clean check, everything else must be clean.

**(a) Coverage at C_W** (W27 clause (a)): `mkdir -p $R && python -m benchmarks.m06.w27.coverage --out $R/coverage.json`
— expect exit 0, `G14 PASS`, `CANDIDATE: 0` of 450 and of 82; anything else: stop, design lane.
**(b) Seeded draw:** `python -m benchmarks.m06.w27.sample $R/coverage.json --out $R/sample.json` (45 cases, 3 canaries).
The draw precedes the canaries: W27-R31 defines them as frame cases not in the sample (R-468).
**(b′) Confirm:** `python -m benchmarks.m06.w27.harness confirm --campaign $C` — writes `$R/confirmation/confirmation.json`
(W27-R66). Exit 2 with `confirmation: <k> sampled CANDIDATE case(s); …` and nothing written: stop, design lane.
**(c) Canaries:** `python -m benchmarks.m06.w27.harness canaries --campaign $C --work $W --oauth-token-file $T` (no `--model`)
— attempts the canary cases of `sample.json` in order at HEAD as `$R/canary/<NN>-<case>/`, NN = 01…06 numbered on across
cases, skipping a case that already passed at HEAD; exit 0 when every canary case has passed at HEAD; exit 1 at the first
failed attempt (it stops there). `M` is the pinning attempt's `init_model` and `V` its `init_claude_code_version`, as the
verdicts print them (attempt 01's, unless it had no `init` message); P7 checks both.
- **Re-canary** (W27-R68; at most 3, so 6 attempts in all, every attempt counts toward spend; none is ever deleted or
  reused): after a failed attempt, read its `run.json`/`stderr`. If it needs no code change, run the same command again.
  If it needs a harness fix: commit it (C_W becomes the new HEAD), re-make (a), (b), (b′) in place — their `rows`, `cases`,
  `run_order` and `canaries` must equal the old ones, otherwise stop, design lane; record the old digests in the build log
  (A4-Q3) — then run (c) again: canaries that passed at the old commit run again at the new one (only attempts at C_W count).
- Exit 2: `re-canary allowance exhausted (registration §17 Q3): Frank` (a seventh attempt; nothing launched), or the pin is
  `claude-sonnet-5` (Frank, §3 F1), or the pinning attempt's `init` model is an alias, not a full id (design lane, A4-Q1).
**(d) Preflight, then the runs:**
`python -m benchmarks.m06.w27.harness preflight --campaign $C --model $M --claude-code-version $V` (prints P1–P8, writes
nothing; exit 0 iff all pass); then, in the background (45 sessions, ≤ 1800 s wall each):
`python -m benchmarks.m06.w27.harness campaign --campaign $C --model $M --claude-code-version $V --work $W --oauth-token-file $T`
— re-runs P1–P8; only if all pass it writes `$R/preflight.json` (W27-R67) and then `$R/NN-<case>/` in `run_order` (run.json,
prompt.txt, transcript.jsonl, result.json, store-export.json, scores.json; each `run.json` names `preflight_sha256`), then
`$R/campaign.json`. A failing preflight writes nothing. It stops at a run outside the configuration (kept; counts), and
before any run whose `--max-budget-usd 5` cap would take the recorded spend past `--spend-ceiling-usd` (default 45).
**Stop:** kill the process; the run in flight keeps its directory (never re-run). **Resume:** the same command with `--resume`
(no preflight; reuses `preflight.json`; runs only missing directories, in order).
**Spend:** `python -m benchmarks.m06.w27.harness spend --campaign $C` — sum of `total_cost_usd` over every `result.json`
(canary attempts included; Claude Code's subscription estimate, `cost_basis`); `uncosted` lists runs with no recorded cost.
**(e) Scores:** each run is scored as it ends; re-score one: `python -m benchmarks.m06.w27.scorer $R/NN-<case> --coverage $R/coverage.json`;
`campaign.json` (W27-R53…R56) is written at the end of (d); a resumed campaign writes it when the last run is done.
**(f) Order:** `python -m benchmarks.m06.w27.harness order --campaign $C` — the digest chain and the commit rule (M07.A50,
W27-A78); exit 0 iff every link is equal and every record carries C_W with a clean tree.
**Committing the records:** `$R` only (never the archive); U14 (W27-R64, `test_u14_…`) admits campaign records only under
`benchmarks/m06/openidaes450/runs/w27-m07-<hex>/`.
**Dry run first** (no model, nothing spent; at a clean commit with the real archive directory):
`python -m benchmarks.m06.w27.dryrun --out /tmp/w27-dry-run-$(git rev-parse --short HEAD)` — exit 0 iff G14, P1–P8,
`preflight.json`, the 45 stub runs, `order_check`, G15 and A23 all pass.
