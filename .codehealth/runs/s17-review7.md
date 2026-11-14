# S17 review 7 (reviewer, 2026-11-13): steps cae099ae..8d07d95b (8 steps, WO6)
Verdict: 8 accepted (4 with a note, names/docstrings only), 0 rejects. No behaviour difference.
- af6741e5 note: `_end_exited` hides that `_watch` (executor.py:531) signals cancel/wall-time stops and kills workers
  past grace (§8.2). Rename `_poll_and_end_exited`, name stops and kills in its docstring (:433); flag `unrecorded`
  (:381) -> `ending_failed` (rule 13).
- b92b807b note: `solve` (runner.py:584) has no docstring; rule 7 (list the first phase helper) missed.
- 2c6a1599 note: `_warm_start` docstring (runner.py:714) omits the None when the opted-in lineage has no verified
  solution (rule 4, callee's None).
- a9b001e0 note: runner.py:734 comment "at the site of the warm-start lookup (`_warm_start`)" misreads; the original
  meant ADR 0024 D2's "here, where the store is". "nearest verified ancestor" inaccurate for a refusal.
- `_supervise` (8.0) and `solve` (5.1) read as named phases; stopping right (state across iterations; handlers read
  `run`, `selected`). `_supervise` docstring should name all four helpers.
Playbook candidates: rule 8 incl. callee effects; rule 4 incl. callee Nones; moved "here"/"same site" comments are
rewritten to state the referent; rule 7 writes the docstring if none; accepted patterns: break-with-carry -> return
carry; closure reading only self -> method; when-not: remainder carries state across iterations or a handler reads
locals the helper would hide.
