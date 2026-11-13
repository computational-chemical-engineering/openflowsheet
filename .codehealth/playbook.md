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
5. Put a private helper after its caller; several helpers of one caller follow it in the order of first call.
   (S17 review 3)
6. A helper transforms its input purely; the caller owns the edits to its side tables. (review 2: e81fd1a2, 81203d61)
7. A refusal ladder or check-and-return block is extracted whole and returns `T | Unbound` (or `Unbound | None` for a
   clause helper, citing its clause id and listed in the caller's docstring). (review 2: ee653caa, 0fd8079b; review
   3: 0843250a, 26b58c96)
8. A name covers every effect of the body and never uses a term the code's own comment sets apart (a declared
   default is not a start). (review 2: 81203d61, 0fd8079b; fixed in 9d0498fd)
9. A helper whose output is keyed by id states in its docstring which entry wins when keys collide. (review 2: d41c8028)
10. Moving a statement across an early return, or a lazy import into a helper, changes when it runs: keep the order,
    or state in the commit message that the statement is pure. (review 2: ee653caa; review 3: 5fe1f040)
11. loop-body-extract keeps the loop's guard in the caller, so the loop still reads as one sentence. (review 3: 5fe1f040)

## Refactor recipes

Seed recipes apply. Additions from S17:

| id | when not (added) | evidence |
| --- | --- | --- |
| extract-phase | the phase is one branch of a structural recursion (a walker over dict, list and leaf): lifting one branch creates mutual recursion for a score drop | review-reject b29aea3c (S17 review 1) |
| extract-phase | the helper's parameters feed disjoint statements, or its name describes only part of its body | review-reject 5d46d5fb (S17 review 1) |
| extract-phase | the remainder is a ladder of similar check-and-return rungs: peeling the tail off rung by rung lowers the score without making the ladder readable; restructure the ladder as a whole or leave it | review 1 note on `reproduce_bundle` |
| extract-phase | the remainder only threads the same locals through successive phases, or a step drops the score by less than about 2 points: stop there | S17 review 3 (cfe9099c, 1.3 points) |
| parameter-object | the fields would be created in different phases, so the object is built late for one consumer or is mutable and partly filled: it hides which phase reads what | S17 review 3 (binding.py's binder) |

Work order 1 (revision_run.py, pin 7628e737): 16 attempts, 13 gated accepts, 3 gate-fails (literals twice, tests
once: the dirty-tree test, D14), 2 review-rejects. extract-phase 12 accepts, decompose-conditional 1 (rejected).

Work order 2 (binding.py, pin 5646ad1a): 13 attempts, 13 accepted (extract-phase 12, loop-body-extract 1), 0
gate-fails; reviews 2 and 3: 0 rejects, notes applied in 9d0498fd (names and docstrings, gated `--no-gain`).
binding.py 134.2 -> 43.6.
