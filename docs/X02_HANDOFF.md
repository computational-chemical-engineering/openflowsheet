# X02 handoff (build lane) — WO-5 stopped at registration (escalated)

Branch `wp/X02` (worktree `.claude/worktrees/x02`). Design: `docs/design/X02-warm-starts.md` (binding), ADR 0070
(Proposed). Choices: `docs/X02_DECISIONS.md` D-1…D-29. Run tests with `PYTHONPATH=src ../../../.venv/bin/python -m
pytest` from the worktree (the shared venv imports the main checkout otherwise; `MYPYPATH=src` for mypy).

## Done

- WO-1…WO-4 (see the decisions log and earlier commits).
- **WO-5, built:** `src/openflowsheet/adapters/pymrm/child_warm.py` (sha `1f11b4b1…`; loads `child.py` by path,
  pinned to v3's runner hash), `benchmarks/x02/variant-s123w-provisional.json`, `tests/test_x02_wo5_warm_child.py`
  (31, no environment), campaign script `benchmarks/x02/g5_warm_reactor.py` (`inlets`, `part-a-v3`, `loops`,
  `variant --registered|--loop`).
- **G5 measured** (`evidence/X02/69c4a24d…/`, index with artifact tree hashes; stores under `artifacts/`):
  - (a) cold = v3 recorded `tube_outlet` bitwise at 8/8 inlets (D-22: second sequence `cand-C1-P1`, since the
    note's g12 and S0 sequences are the same four keys);
  - (b) warm accepted, `used` 8/8, no fallback; rel max **1.92e-7**;
  - (c) warm **21 % slower** overall (round 2 ran at 6/8 warm vs 4/8 cold; longer certificates);
  - (e) v3 real loop restart: VERIFIED, 1 outer iteration, w₀ bitwise, 1 call, no `start` member.
- G0 after WO-5: F0 PASS M1–M9 (50/61/61/61/61/85/52/105/35); v1–v3 variant files unchanged; G0 key test (163,
  0 differences) and the G0-listed + touched tests: 310 passed.

## Blocked (design lane, D-29)

1. G5b 1.92e-7 lies in the note's "pass with a manifest note" band, but registering it against
   `precision_floor_rel` 1e-6 violates I3 ("at least one decade below"). Raise the floor, register anyway, or not
   register?
2. G5c contradicts §3.1's premise (warm 10–15 % faster): Q1 (build the warm variant) may need re-deciding.

## Next (only after a ruling)

- If registered: `python benchmarks/x02/g5_warm_reactor.py variant --registered <rel>`, add the printed sha to
  `adapters/variants/registry.json`, `variant --loop` (writes `c1-loop-real-s123w.json`), then
  `loops --store … --work … --value 675.15 --out …` (G5d; neighbour SPEC-S3-T +2 K), ~15 reactor calls.
- WO-6 as planned (MSG tokens, register entries, progress, manifest, reviewer, full gate).
