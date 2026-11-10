# S6dbg — diagnosis of S-6's two runner failures (build lane)

Brief: `docs/briefs/REL040-s6-debug.md`. Branch `wp/S6dbg` from `origin/main` 694d82f5. nlp env: the `m05`
worktree's `.venv-nlp` and `.reference-downloads/m03-ipopt` (as S-6).

## F-A — NLP-1 inventory workload, `TypeError` at `start["final_decisions"]`

- Reproduction: `.venv-nlp/bin/python -I scripts/m03_ipopt_inventory.py --env <m05>/.venv-nlp --check` → exit 1,
  the S-6 traceback.
- First bad commit: **f2f4ef5e** (OPT WO-4, "V2/V4/V5 on the revision host; solve_start options", D-25), merged by
  937223ad. Bisect by `--check` on archives: 937223ad^1 PASS, 937223ad FAIL, f2f4ef5e^ PASS, f2f4ef5e FAIL.
- Root cause: the workload wraps `greybox._typed_options` (to add Ipopt's `output_file`, G4) with a zero-argument
  lambda. f2f4ef5e made `solve_start` call `_typed_options(options)` (OPT design §4.3, a request's `max_iter` /
  `max_wall_time`). The lambda raised `TypeError` inside each start; `solve_start` classified every start
  `SOLVER_FAILED` with `final_decisions = None` before Ipopt ran, and the script then subscripted `None`. The optimiser
  itself is correct: unpatched, NLP-1 is `KKT_POINT_VERIFIED` from all three starts.
- Class **(a)**: a consumer of a changed internal signature. Fix 3e25b294: the wrapper forwards `*args, **kwargs`, and
  a start without decisions stops the workload naming its classification. `--check` reproduces
  `benchmarks/m03/ipopt-inventory-x86_64.json` unchanged (G1..G6 PASS); no record or number changes. New nlp test
  `test_the_inventory_workload_print_patch_takes_solve_start_overrides` executes the wrapper's own lines against
  greybox (fails on the old line, passes on the new).

## F-B — `m05_g10_real_replay`, `ReplayDivergedError` at S0's 673.15 K inlet

- Reproduction (9 s): `OMP_NUM_THREADS=1 PYOMO_CONFIG_DIR=<venv>/share/pyomo PYTHONNOUSERSITE=1
  PYTHONPATH=src:<cache>/nlp-test-tools <venv>/bin/python scripts/m05_wo9_real.py --replay` → exit 1.
- Not code: **no first bad commit.** v0.3.0's tree (git archive) diverges identically today. Same result with
  `alpha-main`'s `.venv-nlp`; the two nlp venvs have identical `pip list`.
- Root cause: **the host kernel.** The live request differs from the recorded one in one member only,
  `environment_fingerprint_sha256` (live 5710568d…, recorded dfce4150…). The reactor child's fingerprint (M02 design
  §2.4, `adapters/pymrm/child.py:409`) contains `platform.platform()` = `Linux-6.12.113+deb13-amd64-…`. Replacing
  `6.12.113` by `6.12.111` in the live fingerprint gives exactly the recorded SHA (dfce4150…). The REAL record was
  re-taken 2026-10-16 (cdefb1ab) in boot −1 (2026-10-16 08:58 → 2026-11-06), on 6.12.111; v0.3.0's RC ran in the
  same boot. 6.12.113 was installed 2026-10-17 and has run since the reboot of 2026-11-06 13:58. Every experiment key
  of the run therefore changed, and the record-only backend refuses the first one.
- Class **(c)**: the cure changes a registered record or the key's identity. Stopped; question for the design lane.

### Question for the design lane (F-B)

The REAL record's replay (G10, `m05_g10_real_replay`) is bound to the kernel release the record was taken on, by
design of M02 §2.4 (`platform` in the fingerprint, the fingerprint SHA in the experiment key). Options:

1. Re-take the REAL record on the current kernel (as M05 WO-10a did at cdacc32; ≤ 4 h, ≤ 400 cold experiments, local)
   and note in the release procedure that a kernel upgrade invalidates the REAL replay until a re-take.
2. ADR: the key-relevant fingerprint excludes the kernel release (or `platform`) — changes every experiment key and
   so every M02/M04/M05 record's store; large.
3. Replay serves a request whose key differs only in the fingerprint — weakens G10; not recommended.

Engineer's default if asked to choose: **1**, with the procedure note; 2 only if kernel churn recurs. Not acted on.

## Gates

| Gate | Result |
|---|---|
| `m03_ipopt_inventory.py --check` (NLP-1, m05 env) | PASS, G1..G6, record unchanged |
| `--workload trsp-exe --check` | PASS, G1..G6 |
| `pytest -m nlp` on S-6's 18 modules (`nlp-modules.txt`), m05 env | 212 passed (S-6: 211; +1 new test) |
| new test on the pre-fix script | FAILS (as intended) |
| F0 `scripts/corpus_identity.py --check` | PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35 |
| ruff check / format on touched files | clean |

Note: `pytest -m nlp` over the whole `tests/` tree in the nlp env stops at collection (exit 2): four modules
(`test_opt_phase_rows`, `test_s10_dwsim`, `test_s10_idaes`, `test_s10_records`) import `mpmath`, which `.venv-nlp`
lacks. S-6 runs the selected module list, so the rehearsal is unaffected; not changed here.

## Where this stopped

F-A fixed and tested. F-B diagnosed, not fixed (class c); awaiting the design lane's choice above. No merge.
