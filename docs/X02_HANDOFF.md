# X02 handoff (build lane) — WO-6 stopped at G5d (iii) (escalated, D-32)

Branch `wp/X02` (worktree `.claude/worktrees/x02`). Design: `docs/design/X02-warm-starts.md` (amended A-1…A-9),
ADR 0070 (Proposed, amended per the review), review `docs/reviews/X02-review.md` (binding). Choices: D-1…D-32 in
`docs/X02_DECISIONS.md`. Tests: `PYTHONPATH=src ../../../.venv/bin/python -m pytest` from the worktree; `MYPYPATH=src`.
Never squash: the evidence pins `69c4a24d`, `005d206f`, `dcb499ee`.

## WO-6 done

- M-1: A-1…A-9 in the note; ADR 0070 D2, D4, D7, D8, Consequences bullet 2, Migration (S-4), draft D (`dc2b1081`).
- Ruling 1: `child_warm.py`, its tests, the provisional variant and `g5_warm_reactor.py` removed; `CHILD_SCRIPTS =
  ("child.py",)`; T07 allowlist justification and D-21 name one entry, count 36 (`09401fcc`).
- M-2: `docs/recovery-edges.yaml` E9 `enabled: default`, precondition, trigger, max_count (`fc1391cb`).
- S-1 (bare check names in records, wrapped trace messages, new test) and S-3 (G3f pinned to `MISMATCH` +
  `external_request(0, reactor)`) (`bda43556`). Targeted run: X02 WO-1…4 + G0, T07 global state, T08 recovery edges,
  edge identity, warm starts: **111 passed**. mypy clean on touched files.
- Register: R-950 stays c_4 (`wp/MSG` not merged at WO-6; MSG renumbers per ruling 4) (`81ae7809`).
- S-2: `benchmarks/x02/g5d_v3_loops.py` (D-30), record `evidence/X02/dcb499ee…/g5d-v3.json` + `index.json` (D-31).

## Blocked (design lane, D-32)

G5d on v3, neighbour SPEC-S3-T 673.15 → 675.15 K: (i) VERIFIED 4 outer; (ii) VERIFIED 1 outer, w₀ bitwise, 1 call;
(iii) cold VERIFIED 4, warm VERIFIED **4** — "warm takes fewer outer iterations" fails (§7 G5 (d): escalate). Bound
holds (Δû 3.76e-4 ≤ 1.64e-3), edit moves û 83.7 bounds. Warm starts ~2× closer but converges at the same k.
Proposed default: record as measured; qualify ADR 0070 Consequences bullet 1; no iteration-count gate.

## Next (after the ruling)

1. ADR 0070 Acceptance evidence ("G5 (d) ran on v3 per S-2" + the ruling) and Consequences bullet 1.
2. `docs/progress.md`; full gate once (only when `pgrep -af 'scripts/gate.sh|scripts/check.sh'` is empty;
   `PYTHONPATH=$PWD/src PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH ./scripts/gate.sh`, background);
   F0 `scripts/corpus_identity.py --check`.
3. Manifest: the frozen pattern `^[PKTMSR][0-9]{2}[a-z]?$` refuses `X02` → file as `S16` (R-878 rule, RP's C-22; S16
   unused on main, MSG and X05 at WO-6), harvest per RP's `f6f838dd` (support_envelope, support-matrix,
   `HARVEST_SIZE` in `tests/test_m07a_harvest.py`), status `tested` only if supported; push; record CI run id.
