# X02 handoff (build lane) — WO-7 done; awaiting Frank's ADR 0070 acceptance and the merge

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
- Register: R-950 stayed c_4 at WO-6 (`81ae7809`); at the merge prep it became c_5 after MSG's c_4 (D-36).
- S-2: `benchmarks/x02/g5d_v3_loops.py` (D-30), record `evidence/X02/dcb499ee…/g5d-v3.json` + `index.json` (D-31).

## WO-7 done (close-out)

- D-32 carried out: note §7 G5 (d)(iii) A-10; ADR 0070 Consequences bullet 1 and Acceptance evidence (review text +
  D-32); status stays Proposed (`2ab11b66`, `18633e9f`). D-33 (manifest id `X02`, ADR 0059 D1), D-34 (G5b `fail`).
- Full gate at `2ab11b66`: PASS, 15138 passed. F0 PASS (M1–M9). Targeted X02 + G0 files: 258 passed. CI at
  `2ab11b66`: run 42398109849 success on both architectures.
- Manifest `evidence/X02/2ab11b66…/manifest.json`, `tested`, 18 checks (G5b, G5d_iii_iterations `fail` with
  `accepted_fail`; G5c `not_applicable`); harvested (10 P items), `HARVEST_SIZE` (71, 958, 125).

## Merge prep done (brief `docs/briefs/X02-merge-prep.md`)

- D-35 merge of `main` (MSG), D-36 surface link c_5 (D_5 `f51b69bf…`), D-37 cache count 38, D-38 ADR 0070 Accepted,
  R-951…R-955.

## Next

CI green on both architectures at the pushed head; the orchestrator re-takes the manifest and merges `wp/X02` (never
squash: evidence pins `69c4a24d`, `005d206f`, `dcb499ee`, `2ab11b66`). No `reviewed` is claimed.
