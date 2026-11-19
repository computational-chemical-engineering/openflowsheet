# S19 W5 WO-0: the probe re-runs x0 to x12 (W5-T2)

Ruling `docs/briefs/S19-W5-ruling.md`, section 3.1 (method) and 6.1 W5-T2 (the check). The re-measurement is the
reference, not section 3.2.

## Provenance

- Probe runs: the WO-0 engineer, 2026-11-18 between 18:59 and 19:43, on detached scratch worktrees of 8d31b89e
  outside the repository (removed afterwards). Each of x1 to x12 had one comment line appended to one file
  (`# W5 identity experiment: a comment-only edit (never committed).`); x0 had no edit. The appendix A probe ran
  with `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1` and the main checkout's `.venv`:
  `PYTHONPATH=src python scripts/corpus_identity.py --check --log <x>.f0.log`, then
  `PYTHONPATH=src python scripts/registry_builtin.py --check`, then the MCP digest tier and the F1 trio.
- Verdicts: fix round 1 (review R-W5-WO0), 2026-11-18, `scripts/w5_identity.py` at the fix 5 commit of
  `wp/S19-w5`, against those F0 logs:
  `python scripts/w5_identity.py predict --base 8d31b89e --files <file> --against-log <x>.f0.log`.
  x0 ran on a detached worktree of 8d31b89e without `--files`, so E is `git diff 8d31b89e..HEAD`, empty there.
- Every probe: MCP digest `40 passed`. F1 trio: x0 `93 passed`, x1 to x12 `4 failed, 89 passed` (the four tests
  section 3.2 names).

## Result

| tree | edited file | F0 summary line (unpinned `--check`) | registry `--check` | predict verdict |
| --- | --- | --- | --- | --- |
| x0 | `none` | `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35` | clean, `registry_sha256 f251447d06a6...` | PASS, none (exit 0) |
| x1 | `thermo/pr_lib.py` | `F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `12534b86ad25...` | PASS, M9 1 (exit 0) |
| x2 | `assessment/cost/sets.py` | `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35` | FAIL on `builtin-sha256.txt` only, `d1908a39bce8...` | PASS, none (exit 0) |
| x3 | `thermo/syn001.py` | `F0 FAIL: M1 50/50, M2 FAIL 52/61, M3 FAIL 52/61, M4 61/61, M5 61/61, M6 FAIL 77/85, M7 FAIL 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `a88593c4f984...` | predict FAIL: E refused (2 problem(s)) (exit 1) |
| x4 | `models/syn001/flash.py` | `F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `3fce7a1e553f...` | PASS, M9 1 (exit 0) |
| x5 | `thermo/pr_c1.py` | `F0 FAIL: M1 50/50, M2 FAIL 1/61, M3 FAIL 1/61, M4 61/61, M5 61/61, M6 FAIL 2/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `fc01e31ce696...` | PASS, M2 1, M3 1, M6 2, M9 1 (exit 0) |
| x6 | `thermo/iapws95.py` | `F0 FAIL: M1 50/50, M2 FAIL 3/61, M3 FAIL 3/61, M4 61/61, M5 61/61, M6 FAIL 2/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `be1abaf2d1f7...` | PASS, M2 3, M3 3, M6 2, M9 1 (exit 0) |
| x7 | `thermo/wilson_ig.py` | `F0 FAIL: M1 50/50, M2 FAIL 5/61, M3 FAIL 5/61, M4 61/61, M5 61/61, M6 FAIL 2/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `e8bbae113bad...` | PASS, M2 5, M3 5, M6 2, M9 1 (exit 0) |
| x8 | `thermo/coolprop_heos.py` | `F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 FAIL 2/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `1d256b312c0b...` | PASS, M6 2, M9 1 (exit 0) |
| x9 | `models/c1/flash.py` | `F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `bd94e76ee6e9...` | PASS, M9 1 (exit 0) |
| x10 | `models/thermal/heater.py` | `F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `78facf48ba43...` | PASS, M9 1 (exit 0) |
| x11 | `thermo/wilson_ig_v2.py` | `F0 FAIL: M1 50/50, M2 FAIL 5/61, M3 FAIL 5/61, M4 61/61, M5 61/61, M6 FAIL 2/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `3f1a464826d2...` | PASS, M2 5, M3 5, M6 2, M9 1 (exit 0) |
| x12 | `thermo/_coolprop_heos_fluids.py` | `F0 FAIL: M1 50/50, M2 61/61, M3 61/61, M4 61/61, M5 61/61, M6 FAIL 2/85, M7 52/52, M8 105/105, M9 FAIL 1/35` | FAIL on `builtin-sha256.txt` only, `190a1478d767...` | PASS, M6 2, M9 1 (exit 0) |

- Every verdict compares the predicted (measure, key) pairs with the log's moved keys as sets per measure, both
  ways, and the predicted summary line with the log's first line: 0 differences in each of the 12 PASS rows.
- x3 is refused by R1 since fix 3 (`REFUSED src/openflowsheet/thermo/syn001.py: tier 4 (excluded), refused by R1`
  and `REFUSED M7: 52 key(s) predicted to move, refused by R1`). Its reach, compared at function level
  (`w5.predict` against `w5.log_moved` of `x3.f0.log`): 0 differences, summary line equal, `M2 52, M3 52, M6 77,
  M7 52, M9 1`.
- Registry: every edited tree moved only `builtin-sha256.txt`; no table pointer moved, and the tool predicts no
  table pointer for any of x1 to x12 (`tables.sha256` unchanged), with `builtin-sha256.txt` moving in each.
- The per-measure counts equal section 3.2's rows.
