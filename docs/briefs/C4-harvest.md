# C4 — the post-0.2.0 harvest: M07a's and M07's manifests (build lane, `opus-engineer`)

`docs/CLOUD_WORK.md:27` (C4). Branch `wp/C4` from `main` `ebc234e`. Register numbering: **R-542…R-545** (if a ruling
line is needed; design-lane questions go to `docs/C4_DECISIONS.md` as `QUESTION:`).

## The question
R-485 (M07 spec §25, `docs/derivations/M07-spec.md:2257-2328`) deferred M07a's three manifests (24 limitations,
18 non-pass checks) and M07's manifests to "the next harvest". 0.2.0 is released; this package is that harvest.

## Facts with anchors
- Exclusion: `scripts/t08_support_matrix.py:478-484` (`HARVEST_EXCLUDED = ("evidence/M07a/", "evidence/M07/")`),
  `harvest_items` :487-507. Manifests: `evidence/M07a/{e0e198e…,6fec822…,cc73219…}`, `evidence/M07/{c899c85…,ce99365…}`.
- Tests: `tests/test_m07a_harvest.py` (A50 `HARVEST_SIZE` :32 — now `(34, 413, 41)` after S01; the
  "nothing excluded at C_α / C′" test), `tests/test_t08_w2_support_envelope.py` (A21 classification; A23 matrix bytes).
  Classification rules: `scripts/t08_support_matrix.py` `check_a21`; T08 release spec §5
  (`docs/derivations/T08-release-spec.md`). S01's classification of its 36+13 items (commit series on `main`,
  `git log --oneline -- benchmarks/t08/support_envelope.yaml`) is the most recent worked example.
- The envelope id/release pin (MR-3; `tests/test_m07a_harvest.py`) and `docs/support-matrix.md` (A23).

## Exit test
`HARVEST_EXCLUDED` empty (or each remaining entry justified by a register line); every M07a/M07 item classified
E/S/P/B with pointers; `HARVEST_SIZE` and its comment updated; the tests that pinned the exclusion at C′/C_α keep
their historical assertions about those commits (do not rewrite history) and gain the post-0.2.0 state;
`docs/support-matrix.md` re-rendered; `tests/test_t08_w2_*.py tests/test_m07a_*.py tests/test_m07_*.py` pass;
ruff/format/mypy clean. If the envelope id must change for new rows, say why in a `DECISION:` line.

## Out of scope
Changing any released record, verdict or 0.2.0 artifact; re-classifying rows already in the envelope.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/C4-handoff.md`, stop. Report ≤ 150 words.
