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
5. Put a private helper directly after its caller.

## Refactor recipes

Seed recipes apply. Additions from S17:

| id | when not (added) | evidence |
| --- | --- | --- |
| extract-phase | the phase is one branch of a structural recursion (a walker over dict, list and leaf): lifting one branch creates mutual recursion for a score drop | review-reject b29aea3c (S17 review 1) |
| extract-phase | the helper's parameters feed disjoint statements, or its name describes only part of its body | review-reject 5d46d5fb (S17 review 1) |
| extract-phase | the remainder is a ladder of similar check-and-return rungs: peeling the tail off rung by rung lowers the score without making the ladder readable; restructure the ladder as a whole or leave it | review 1 note on `reproduce_bundle` |

Work order 1 (revision_run.py, pin 7628e737): 16 attempts, 13 gated accepts, 3 gate-fails (literals twice, tests
once: the dirty-tree test, D14), 2 review-rejects. extract-phase 12 accepts, decompose-conditional 1 (rejected).
