# Build brief: MSG review fixes — WO-11 (sidecar WO-5a, rule 2, entry fixes) and WO-12 (catalogue completion, evidence)

Status: brief, 2026-11-06. Review `docs/reviews/MSG-review.md` (`2aee6dd3`, on main) is binding: its must-fix M1–M7,
its rulings Q1–Q9 and its should-fix items. Branch `wp/MSG`, worktree `.claude/worktrees/msg`, head `8d955cd7`. Log
`docs/MSG_DECISIONS.md` (append D11-*, D12-*), handoff `docs/MSG_HANDOFF.md`. First `git merge origin/main` into
`wp/MSG` (it brings the review and this brief).

DECISION (orchestrator): M7 / WO-5a lands **before** the merge (the reviewer's preference). Alternative: merge with the
numbers as strict xfails and WO-5a after. Reversible by: reverting WO-5a's commits.
DECISION (orchestrator): M1 — complete every entry the note §4.2.6 requires (no declared-stub limitation). Alternative:
ship stubs as a declared limitation (Frank's call if he wants it). Reversible by: Frank's late answer.

## WO-11 (first engineer)

- **WO-5a per Q1:** the diagnostic sidecar at `revision_flowsheet.py:1029-1034` (outside F0 M9), driven by
  `detail_pattern`s over the failing unit's message line 2 (exact floats). Delivers C02 and C11 numbers, C09 bounds and
  C01's `landed`; C01's value/saturation/pressure numbers stay strict xfails, re-reasoned to "deferred to F6 v2 models
  (Q1 (c))". Amend note §4.6 only as the review says. Never edit the M9-frozen thermal modules.
- **`legacy._typed`:** refuse non-finite floats (`nan`, `inf`) before WO-5a's patterns use it; test with a control.
- **Q2:** §4.4 rule 2 — first FAIL check, else first NOT_RUN check on a DRAFT report, never WARN; add the failing
  check's `implicated_objects` as elements. Lift the C06–C08, C10 xfails this resolves; inner codes reached become
  complete in the same change.
- **M2:** `pressure_rise` generic title plus a valve variant (emitters `thermal/valve.py:248`, `syn001/valve.py:396`).
- **Q6:** `explain.md` wording edits ("project data" → "data"; "with its numbers" → "with its own ids and, where known,
  numbers"); record the design-lane review in `REVIEW.json` as the review states. Frank's review stays open — do not
  record it.
- **Q7 D4-1 overruled:** the three stubs (`not_a_directory`, `not_a_project`, …) become complete.
- **Should-fix:** `out_of_domain` (conditional water range and kind), `unsupported` (action with a reason), stub kinds
  of `worker_lost`, `owner_lost`, `store_error` — each as the review says.

## WO-12 (second engineer, after WO-11's commits)

- **M1:** complete every remaining entry of note §4.2.6 (api_error, outcomes, statuses, job statuses,
  `isentropic_state_single_phase`, `pressure_fall`, FB-01's three); a test pinning the required-complete list.
- **M3:** MSG-G0 per Q3 — F0 replaces (a) and (c); MSG-G0 runs (b) and (d) and reports PASS; no re-take of (c).
- **M6:** register entry for c_4 in R-457's form, D_4 measured on the merge tree (`docs/decision-register.md`,
  committed on `wp/MSG`).
- **M4 + evidence:** records for MSG-G1/G2/G3/G9/G10 and the performance gate in the manifest; full gate once; F0
  check; push; aarch64 CI green recorded. Manifest `tested` only if supported (the explain.md test fails until Frank's
  review is recorded — state that; never `reviewed`).

## Rules (both)

Gate numbers, F0 and the 0.3 surface must not move except where the review rules. Never loosen a check, never change a
wall-time budget (host load ~50–80: re-run alone, report both timings). Run the tests you touch, ruff, ruff format,
mypy; `scripts/corpus_identity.py --check` PASS. Venv: `PYTHONPATH=$PWD/src
PATH=/home/frankp/Codes/OpenFlowsheet/.venv/bin:$PATH`. Long runs in the background, logs under
`/tmp/claude-1003/-home-frankp-Codes-OpenFlowsheet/fd59d98d-797a-4da8-93d6-9c61c6d4bdc7/scratchpad/msg-wo11/` (or
`msg-wo12/`). Commit on `wp/MSG` only, named paths, messages `MSG WO-11: …` / `MSG WO-12: …`. Push `wp/MSG`; do not
merge. Where the review leaves a choice, decide, isolate, log; where it is silent on something that changes numerics,
identity or a frozen interface, stop and report. No subagents. Never read, stat or touch `~/.config/procsim/`; do not
read `/home/frankp/s10-papers/`, `~/.cache/seider3/`, `~/.cache/seider4/`; nothing under other worktrees. Context cap
~150k: commit, rewrite `docs/MSG_HANDOFF.md` (≤ 40 lines), stop. Report ≤ 25 lines.
