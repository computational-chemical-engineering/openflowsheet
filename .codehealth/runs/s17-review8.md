# S17 review 8 (reviewer, 2026-11-14): validation.py steps e3a36046..02ce7453 (5 steps, WO7)
Verdict: 5 accepted (3 accept, 2 with a note), 0 rejects. No behaviour difference by reading.
- a450f6d8 note: validate's local `schema` (validation.py:227) holds a Check or a report (rule 13): name it for the
  stage's outcome.
- 02ce7453 notes: (a) :1076-1081 bare `conversions`/`refusals` beside `parameter_conversions`: rename
  `specification_conversions`/`specification_refusals`; (b) the commit's import argument is wrong though the
  conclusion holds: every call reaching `_dimensions` reaches `_analysed`, whose first statement imports binding
  (validation.py:613), which loads HINT_LIMIT's and bound_text's modules; only an ImportError's surfacing point
  differs, still escaping validate with no partial report; (c) `_with_hint` (:1193) -> `_code_with_hint`; (d) A74
  (tests/test_t06_w12_units_v2.py:1047) pins specification-before-parameter order for conversions only; mixed
  refusals' order rests on reading.
- validate at 2.5 reads as named stages; stop.
Playbook candidates: rule 10 (lazy import moved later: justify by an earlier statement in the same call path loading
the module, or no import-time effects; "loaded by some entry module" does not count); rule 5 depth-first (a helper's
own helpers follow it; a shared helper follows the last sibling that calls it); phase results named per phase; accepted
form `T | Report` stage helper with isinstance dispatch, local named for the outcome; a lifted closure renamed when its
name relied on the enclosing function; rule 16 commit names the pinning test and which list.
