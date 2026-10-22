# C7 — build decisions (post-0.2.0 dev version, R-460)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`

- Tag source: `git rev-list -n1 v0.2.0` in this worktree gives `5c82b4cc40dd4fefd3dbce45352910006e5dee13` (the local
  tag; equals `5c82b4c` in `docs/V02_STATE.md` and `TAG_0_2_0` in `tests/test_m07a_harvest.py`).
- Negative control (step 1): with `"0.2.0"` in `RELEASED` and the version still `0.2.0`,
  `tests/test_v02_main_version.py` gives 1 failed, 2 passed — AM-40 fails: `tree_differences(5c82b4c, HEAD)` has 11
  D2.4 paths (`benchmarks/m06/openidaes450/split.json`, `benchmarks/t08/support_envelope.yaml`, 9 under
  `src/openflowsheet/`).
- DECISION: the version label on `main` after 0.2.0 → `0.3.0.dev0` (v0.3 is in progress; PEP 440 sorts it after
  0.2.0). Alternative: `0.2.1.dev0`. Reversible by: reverting the version commit and re-taking W27's coverage. The
  label is Frank's to change (R-460, rulings Q3).
- DECISION: the working envelope after 0.2.0 → `v0.2-envelope-dev` / `release: 0.2.0.dev0`, unchanged from R-193.
  It is the registered form: R-460 / MR-3, the envelope's own header, `t08_support_matrix.py:61-65` ("the first D2.4
  change after the tag returns it to `v0.2-envelope-dev`"), `WORKING_ENVELOPE` in `tests/test_v02_main_version.py`,
  and M07a.A10 (`tests/test_m07a_v0_2_gate.py:1030`), whose edit R-475 pins to exactly two pairs under A31 (b), so a
  new id would need a ruling. R-460 also rejects a dev label equal to the package version. Alternative:
  `v0.3-envelope-dev` / `0.3.0.dev0`. Reversible by: the ruling below, then editing the envelope, `ENVELOPE_ID`,
  `WORKING_ENVELOPE` and A10's pairs together.
- QUESTION: is v0.3's working envelope a new id (`v0.3-envelope-dev`, `release: 0.3.0.dev0`, an R-193 analogue for
  v0.3) or does R-193's `v0.2-envelope-dev` / `0.2.0.dev0` stay the working form until v0.3's cut? The latter is
  what the code and tests now require. A new id touches R-193's scope, `WORKING_ENVELOPE`, and A10's frozen edit (R-475,
  A31 (b)). Default applied: keep `v0.2-envelope-dev`.
