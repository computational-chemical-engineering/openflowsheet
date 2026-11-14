# S17 review 6 (reviewer, 2026-11-13): steps 263cbf44..cae099ae (3 steps, WO5)
Verdict: 3 accepted (2 accept, 1 accept-with-note), 0 rejects. No behaviour difference.
- b5451805 accept: check_lifecycle reads as the §6.3 rule table in rule order. Hoisted views (model.py:195-198) cannot
  raise on any JobEvent (`ends_job` frozen field; `known` = `kind in EVENT_KINDS`, already evaluated in
  `__post_init__`, types.py:1173); the old body had no early return. Only a duck-typed event lacking both `sequence`
  and `ends_job` would raise AttributeError on another attribute (outside the contract). 3-line helpers for rules 9,
  11, 12 keep the table uniform (help). Order of several violations is pinned only by reading (tests compare sets:
  tests/test_t07_lifecycle.py:43, tests/test_t07_adr0008_jobs.py:154).
- a0f982e2 accept: walk then edit; moved block reads no loop variable.
- cae099ae accept-with-note. Should fix (--no-gain follow-up): `_check_array_index` (transactions.py:158-163) has an
  inline twin in `_apply_at` (187-190), and the integer-key refusal is duplicated (146 vs 181); make the helper return
  the narrowed int and call it from `_apply_at`. Rule 8: `_enter_or_create_member` (135) does not enter: rename
  `_ensure_member`; pass `following` instead of `depth`.
Playbook candidates: (1) a lifted check with a verbatim twin: route both through the helper in the same step;
(2) rule 8 ext: a helper whose bool means "the caller goes on" is named for the state it guarantees; (3) rule 10
refinement: hoisting shared values above a rule table needs the commit to say why they cannot raise; (4) ladder
when-not: b5451805 is the accepted form (restructure the whole table); (5) an order claim on collected findings needs
a test that pins the ordered list (sets do not).
