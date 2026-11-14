# S17 review 10 (f0297f13..37d854d7), reviewer agent, 2026-11-14

012d947f | accept | two loops are the two orders the docstring names, moved verbatim; element_diff still only when no top-level member offends; _offending_path after its caller (rule 5).
58a22104 | accept-with-note | ladder restructured whole in rung order; reads, at("compare") and reasons in order; moved unpack/initialisations pure. Note: _recorded_route (revision_run.py:1390) returns four values, name covers only the route (when-not "name describes part"): rename e.g. _rerun_inputs. Caller's `found` (revision_run.py:1314) not named for the outcome (a450f6d8 form), sits beside coupling_found.
420b299e | accept-with-note | five families lifted; _refuse_error (NoReturn) at the same point; dispatch matches fall-through; active_job_count and solve snapshot keep order. Note 1 (rule 13): caller local `admitted` (local.py:962) reuses the experiment branch's name for admit_experiment's tuple (local.py:1009): rename to `outcome` or `budgets`. Note 2: _optimize_admission docstring "the study's budgets" (local.py:1042) collides with the surrogate-study family: "the optimization's budgets".
37d854d7 | accept-with-note | two-rung check whole in the _check_request idiom; three self._surrogates() calls in order; docstring meets rule 4. Note (rule 1): ADR 0035 D2-D3 comment stays in caller (local.py:2106) saying "any failed facet rejects it with the report"; that rejection now in _check_promotion (local.py:2129) whose docstring cites neither ADR 0035 nor A3.1: add the citation to the helper docstring, cut that clause from the caller comment.

_prepare at 6.6: right to leave. revision_id = "" (local.py:2052) is never read before being reassigned; keeping dead code to pass the literal gate is gaming the other way. List it for a commit that declares the literal drop (rule 15 treatment).

Behaviour: no difference found. _valid_coupling_record returns None for "not coupled" where old code branched on the route; differs only if read_artifact returned JSON null passing coupling_record_problem, which the schema check / record["iterations"] refuses first. Surrogate-study lambda still closes over `store` == self._store.
Not examined: tests pinning order (moot, nothing reordered); whether the literal gate counts docstrings; the splits after 37d854d7.

Playbook candidates:
1. Accepted form (420b299e): per-family admission helpers return T | Error, caller issues the single refusal, when only an isinstance check and a return sit between, and the refusal function is NoReturn.
2. Rule 8 / a450f6d8: a stage helper returning a tuple is named for the whole tuple (3+ values: consider NamedTuple); the caller's local named for the outcome, never a name a lifted branch uses (rule 13).
3. Rule 15 when-not: a whole restructure that leaves an initializer dead: do not keep it to pass the literal gate; leave the ladder, list for a declared-literal-drop commit (37d854d7, _prepare).
4. Rule 1 extension: a cited check moved into a helper with preparation left in the caller: the helper docstring carries the citation; caller comment sentences now describing the helper are dropped.
5. Rule 10 extension: a helper's None ("not applicable") replacing a branch on another value: the commit shows the read value cannot itself be None.
