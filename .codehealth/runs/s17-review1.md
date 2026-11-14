# S17 review 1 (reviewer agent, 2026-11-13): 8df70461..5d46d5fb, revision_run.py, 12 steps

Verdict: 10 accept (4 with a note), 2 reject (readability; no behaviour difference found in any step).

- 4193249e accept: warm-start record along ADR 0070's inner/outer start; order and in-place mutation unchanged.
- 80e96cc3 accept: pure move.
- d1185ee1 accept.
- c9f3c531 accept-with-note: helper returns a tuple and also appends to the caller's list via `found +=` (out-parameter through list.__iadd__); a6b4ec14 returns the list instead.
- b29aea3c REJECT: dict branch of a three-branch recursive walker moved into `_constants_for_shape_mapping`, creating mutual recursion while the list branch stays inline. Fix: keep `_digests_for_shape` predicate, put the dict loop back.
- b8eda4c9 accept.
- 5851135c accept-with-note: redundant `region_plan = ...; return region_plan`.
- 2f03a3a5 accept-with-note: docstring omits two None cases (non-legacy route, non-RegionResult detail).
- 70064af5 accept-with-note: docstring says "when `run_id` names none"; the lookup uses `manifest.run_id`.
- 4749d62d accept.
- a6b4ec14 accept.
- 5d46d5fb REJECT: `_classified_report` bundles two unrelated post-steps (classification and `_replayed_from_record`) under a name covering the first only. Fix: inline, or extract only the classification.

Playbook material:
- Rule: extract along a concept the spec/ADR names, and move its citation comment with it.
- Rule: extract a whole early-return branch, stage calls included, as one unit.
- Rule: a helper that finds differences returns them; caller does `found += helper(...)`; no appending through a list parameter.
- When not: do not lift one branch out of a structural recursion (mutual recursion for a score drop).
- When not: a helper whose parameters feed disjoint statements, or whose name covers only part of its body.
- Rule: a docstring names the input actually read and every case that returns None.
- Note: place a helper directly after its caller.
- Note: what remains in reproduce_bundle is the `at("compare"); return Reproduction(_inspected(...))` ladder (1304-1357); more tail extractions lower the score without helping; a recipe for the ladder itself is worth more.
