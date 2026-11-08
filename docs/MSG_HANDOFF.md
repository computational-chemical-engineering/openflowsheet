# MSG handoff (after WO-12) — 2026-11-06

Branch `wp/MSG`, worktree `.claude/worktrees/msg`. Spec `docs/design/MSG-messages.md`; review
`docs/reviews/MSG-review.md` (binding); brief `docs/briefs/MSG-build-WO11-12.md`; choices `docs/MSG_DECISIONS.md`
(D11-*, D12-1…D12-5). Not merged.

## Done in WO-12

- M1: §4.2.6's normative list complete (51 entries from their producers, + 4 ending reasons `not_ready` reaches);
  `tests/test_msg_coverage.py::test_the_normative_list_is_complete` pins 68 codes complete and lint-clean.
- S4: CHECKPOINT_INCOMPATIBLE → `bug` (D12-2). S5: DIM-01 `review` dropped; `members_total` on a cut list (D12-3).
- M3: `msg_identity_gate.py --parts` defaults to `bd`; F0 covers (a), (c) (D12-4).
- M6: register R-943 (c_4, D_4 = `eaff4585…` on the merge tree; `without_msg` → D_3 `455d01eb…`) (D12-5).
- M4: `evidence/MSG/9c76b939…/manifest.json`, status `implemented` (see below).

## Gates at `9c76b939`

- Full gate (load 73–77): ruff, format, mypy, node clean; pytest 31 failed, 15062 passed, 1 error. Failures: the
  description-review test (`explain: human pending`, Frank) and load-induced ones (m06 browser smoke 29+1, kill-chain
  g3f 3.65 s > 3.0) that pass alone (32 passed).
- MSG-G0 PASS: b 0/562 (108 bundles), d 0 hits in 442 stores; F0 PASS (M1 50/50 … M9 35/35).
- MSG-G1/G2/G3 0 misses, 0 defects; G9, G10 pass. Perf: cold load 111–120 ms, render median 0.07–0.08 ms.

## Open

- **Frank:** record his review of `explain.md` (`REVIEW.json`); then the gate is green and the manifest may go to
  `tested` (no code change expected).
- **Design lane:** one prose check of the WO-12 `why`/`action` texts (review M1; fresh agent, tight brief); D12-2's
  kind override; the package's `reviewed` status.
- CI on the push: record both legs in the manifest (a check `MSG.CI`) if not already done.
