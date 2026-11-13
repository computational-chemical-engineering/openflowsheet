# OpenFlowsheet code-health playbook

Read after the tool's seed (`plugins/cce-code-health/skills/refactor-loop/playbook-seed.md` in cce-code-health).
Entries here override seed ids. Updated only in separate docs commits, from the run log and reviews (never from
memory).

## Rules for new code

1. Extract along a concept the spec or an ADR names (inner and outer start, a solve-path member, the policy documents),
   and keep its citation comment with it. (S17 review 1: 4193249e, 4749d62d, a6b4ec14)
2. Keep a whole early-return branch, with its stage or side-effect calls, as one unit. (70064af5)
3. A function that finds differences returns them; the caller collects (`found += _check(...)`). No appending through
   a list parameter. (c9f3c531 against a6b4ec14)
4. A docstring names the input actually read and every case that returns None. (70064af5, 2f03a3a5)
5. Put a private helper after its caller; several helpers of one caller follow it in the order of first call. A
   helper extracted later but called earlier goes in its call-order place, not at the end. (S17 review 3; review 5:
   1fe361e5, fixed in 140ce084)
6. A helper transforms its input purely; the caller owns the edits to its side tables. (review 2: e81fd1a2, 81203d61)
7. A refusal ladder or check-and-return block is extracted whole and returns `T | Unbound` (or `Unbound | None` for a
   clause helper, citing its clause id and listed in the caller's docstring). (review 2: ee653caa, 0fd8079b; review
   3: 0843250a, 26b58c96) The step that extracts a caller's first clause or phase helper also lists it in the
   caller's docstring. `_<clause>_refusal` names a check returning `Unbound | None`; a function that always builds an
   Unbound takes another suffix. (review 5: 140ce084; `_basis_refusal` predates the rule and is imported by
   tests/test_s11_routing.py)
8. A name covers every effect of the body and never uses a term the code's own comment sets apart (a declared
   default is not a start). (review 2: 81203d61, 0fd8079b; fixed in 9d0498fd)
9. A helper whose output is keyed by id states in its docstring which entry wins when keys collide. (review 2: d41c8028)
10. Moving a statement across an early return, or a lazy import into a helper, changes when it runs: keep the order,
    or state in the commit message that the statement is pure. A store moved later: the commit names every statement
    it now follows and the catch sites in between. (review 2: ee653caa; review 3: 5fe1f040; review 4: 4a8a1129)
11. loop-body-extract keeps the loop's guard in the caller, so the loop still reads as one sentence. (review 3: 5fe1f040)
12. A helper's parameter and return types are no weaker than the values they carry: `Any` where mypy inferred a type
    is a regression (import the type under `TYPE_CHECKING`). Widening to what the callee needs is fine unless the
    caller's stronger type carries an invariant the helper's output depends on (metering, canonical form). (review
    4: 839117ac, a3f998be, fixed in 6a025d12; review 5: db8de9f3, fixed in 140ce084)
13. A parameter is named for what it holds; never reuse a caller's local name for a different object, and name a
    module helper apart from a closure it serves. (review 4: a3f998be, 4a8a1129, fixed in 6a025d12)
14. A commit message describes the moved unit in the terms the docstring uses. (review 5: b92b0490)

## Refactor recipes

Seed recipes apply. Additions from S17:

| id | when not (added) | evidence |
| --- | --- | --- |
| extract-phase | the phase is one branch of a structural recursion (a walker over dict, list and leaf): lifting one branch creates mutual recursion for a score drop | review-reject b29aea3c (S17 review 1) |
| extract-phase | the helper's parameters feed disjoint statements, or its name describes only part of its body | review-reject 5d46d5fb (S17 review 1) |
| extract-phase | the remainder is a ladder of similar check-and-return rungs: peeling the tail off rung by rung lowers the score without making the ladder readable; restructure the ladder as a whole or leave it | review 1 note on `reproduce_bundle` |
| extract-phase | the remainder only threads the same locals through successive phases, or a step drops the score by less than about 2 points: stop there | S17 review 3 (cfe9099c, 1.3 points) |
| extract-phase | a closure reads and writes one side table in at most 8 lines: extracting the read alone gains score, not clarity. A larger closure becomes a thin adapter that owns the `nonlocal` and side-table writes, with the pure work in a module helper named apart | S17 review 4 (483fd1a3, 5.0 points; 4a8a1129) |
| extract-phase | a dispatch whose branches are the families of one design table: lift every family or none; lifting only the most nested one earns nesting credit and splits rungs the families share | S17 review 5 (e0c43abe) |
| parameter-object | the fields would be created in different phases, so the object is built late for one consumer or is mutable and partly filled: it hides which phase reads what | S17 review 3 (binding.py's binder) |

Work order 1 (revision_run.py, pin 7628e737): 16 attempts, 13 gated accepts, 3 gate-fails (literals twice, tests
once: the dirty-tree test, D14), 2 review-rejects. extract-phase 12 accepts, decompose-conditional 1 (rejected).

Work order 2 (binding.py, pin 5646ad1a): 13 attempts, 13 accepted (extract-phase 12, loop-body-extract 1), 0
gate-fails; reviews 2 and 3: 0 rejects, notes applied in 9d0498fd (names and docstrings, gated `--no-gain`).
binding.py 134.2 -> 43.6.
