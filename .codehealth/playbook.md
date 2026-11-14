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
4. A docstring names the input actually read and every case that returns None, including a None a callee passes
   through; a caller's docstring also names its other early returns and the exceptions it raises on purpose.
   (70064af5, 2f03a3a5; review 7: 2c6a1599, fixed in 18562395; review 9: c95f4cc4, 2b2d079f, fixed in 70f99f8c)
5. Put a private helper after its caller; several helpers of one caller follow it in the order of first call. A
   helper extracted later but called earlier goes in its call-order place, not at the end. The order is depth-first:
   a helper's own helpers follow it before the caller's next helper, and a helper shared by sibling helpers follows
   the last sibling that calls it. (S17 review 3; review 5: 1fe361e5, fixed in 140ce084; review 8: 02ce7453, fixed
   in ac9d221c)
6. A helper transforms its input purely; the caller owns the edits to its side tables. (review 2: e81fd1a2, 81203d61)
7. A refusal ladder or check-and-return block is extracted whole and returns `T | Unbound` (or `Unbound | None` for a
   clause helper, citing its clause id and listed in the caller's docstring). (review 2: ee653caa, 0fd8079b; review
   3: 0843250a, 26b58c96) The step that extracts a caller's first clause or phase helper also lists it in the
   caller's docstring, writing that docstring if the caller has none (review 7: b92b807b). `_<clause>_refusal` names a check returning `Unbound | None`; a function that always builds an
   Unbound takes another suffix. (review 5: 140ce084; `_basis_refusal` predates the rule and is imported by
   tests/test_s11_routing.py)
8. A name covers every effect of the body, including effects of the methods it calls, and never uses a term the
   code's own comment sets apart (a declared default is not a start). A helper whose bool means "the caller goes on"
   is named for the state it guarantees, not for the caller's next action. (review 2: 81203d61, 0fd8079b; fixed in
   9d0498fd; review 6: cae099ae `_ensure_member`, fixed in 7cf38820; review 7: af6741e5 `_poll_and_end_exited`,
   fixed in 18562395)
9. A helper whose output is keyed by id states in its docstring which entry wins when keys collide. (review 2: d41c8028)
10. Moving a statement across an early return, or a lazy import into a helper, changes when it runs: keep the order,
    or state in the commit message that the statement is pure. A store moved later: the commit names every statement
    it now follows and the catch sites in between. Values hoisted above a rule table: the commit says why they cannot
    raise (field reads, a property the constructor already evaluated), not only that they are pure. A moved comment
    that points ("here", "the same site") is rewritten to state its referent. (review 2: ee653caa; review 3: 5fe1f040;
    review 4: 4a8a1129; review 6: b5451805; review 7: a9b001e0) A lazy import moved later is justified by an earlier
    statement in the same call path that already loads the module, or by a module body without import-time effects;
    "loaded by some entry module" does not count, and "an import only binds names" holds only for a module already
    loaded. A commit that says "the same exceptions" either lists every type the moved code can raise or lists none.
    (review 8: 02ce7453, corrected in ac9d221c; review 9: 4a8bcecf)
11. loop-body-extract keeps the loop's guard in the caller, so the loop still reads as one sentence. (review 3: 5fe1f040)
12. A helper's parameter and return types are no weaker than the values they carry: `Any` where mypy inferred a type
    is a regression (import the type under `TYPE_CHECKING`). Widening to what the callee needs is fine unless the
    caller's stronger type carries an invariant the helper's output depends on (metering, canonical form). (review
    4: 839117ac, a3f998be, fixed in 6a025d12; review 5: db8de9f3, fixed in 140ce084)
13. A parameter or local is named for what it holds; never reuse a caller's local name for a different object, and
    name a module helper apart from a closure it serves. When phase helpers replace one loop's accumulators, each
    phase's result is named for its phase (never one bare and one qualified). A closure lifted to module scope is
    renamed when its name relied on the enclosing function. (review 4: a3f998be, 4a8a1129, fixed in 6a025d12;
    review 8: a450f6d8, 02ce7453, fixed in ac9d221c)
14. A commit message describes the moved unit in the terms the docstring uses. (review 5: b92b0490)
15. A lifted check with a verbatim twin elsewhere in the module (same messages): name the twin in the commit. Merging
    the two drops string literals, which the bitwise gate refuses, so the merge waits for a behaviour-level change.
    (review 6: cae099ae, transactions.py `_check_array_index` and `_apply_at`; WO6: runner.py `solve` and `optimize`
    share the R5 `verification_weakening_refused` block) Before naming a helper after a standard (RFC 6901, JSON
    Schema), grep the shared layer for an implementation; name it as the twin, the differences that block the merge,
    and the subset the helper implements. (review 9: 4a8bcecf, `_pointer_target` vs `projection.resolve`)
16. An order claim on collected findings is only as good as a test that pins the ordered list; set comparisons do not
    pin order. Say which in the commit, and which list the test pins. (review 6: b5451805, tests compare rule sets;
    review 8: 02ce7453, A74 pins conversions only)

Accepted forms (S17): a rule table restructured whole, one `_check_<subject>` per rule in rule order, 3-line rules
included for uniformity (b5451805); a loop whose `break` set a carry variable becomes `return carry` when the loop is
the whole helper, the caller keeping the lock and the requeue (65fdadb0); a closure that reads only `self` becomes a
method after its caller, one that reads the caller's locals stays (8d07d95b); a stage helper returns `T | Report`
with the caller dispatching by `isinstance` when the PASS value shares its constructor with a refusal rung, the
caller's local named for the outcome (a450f6d8); a structural walker lifts its child enumeration into a lazy
generator with the recursion left in the walker, only if the walk never mutates the node, and the generator is never
materialised to a list (2b2d079f); sibling builders for spec-named record kinds may share one parameter list, never
merged into one builder with a kind flag (0b1537e6).

## Refactor recipes

Seed recipes apply. Additions from S17:

| id | when not (added) | evidence |
| --- | --- | --- |
| extract-phase | the phase is one branch of a structural recursion (a walker over dict, list and leaf): lifting one branch creates mutual recursion for a score drop | review-reject b29aea3c (S17 review 1) |
| extract-phase | the helper's parameters feed disjoint statements, or its name describes only part of its body | review-reject 5d46d5fb (S17 review 1) |
| extract-phase | the remainder is a ladder of similar check-and-return rungs: peeling the tail off rung by rung lowers the score without making the ladder readable; restructure the ladder as a whole or leave it | review 1 note on `reproduce_bundle` |
| extract-phase | the remainder only threads the same locals through successive phases, or a step drops the score by less than about 2 points: stop there | S17 review 3 (cfe9099c, 1.3 points) |
| extract-phase | the remainder carries state across loop iterations (a failure counter, a `continue`), or an exception handler reads locals the helper would assign: stop there | S17 review 7 (`_supervise` at 8.0, `solve` at 5.1) |
| extract-phase | mutually recursive closures over shared captured values: lift them all into a small class, or leave them | S17 review 9 (`stream_table_format.assemble`, skipped) |
| extract-phase | a closure reads and writes one side table in at most 8 lines: extracting the read alone gains score, not clarity. A larger closure becomes a thin adapter that owns the `nonlocal` and side-table writes, with the pure work in a module helper named apart | S17 review 4 (483fd1a3, 5.0 points; 4a8a1129) |
| extract-phase | a dispatch whose branches are the families of one design table: lift every family or none; lifting only the most nested one earns nesting credit and splits rungs the families share | S17 review 5 (e0c43abe) |
| parameter-object | the fields would be created in different phases, so the object is built late for one consumer or is mutable and partly filled: it hides which phase reads what | S17 review 3 (binding.py's binder) |

Work order 1 (revision_run.py, pin 7628e737): 16 attempts, 13 gated accepts, 3 gate-fails (literals twice, tests
once: the dirty-tree test, D14), 2 review-rejects. extract-phase 12 accepts, decompose-conditional 1 (rejected).

Work order 2 (binding.py, pin 5646ad1a): 13 attempts, 13 accepted (extract-phase 12, loop-body-extract 1), 0
gate-fails; reviews 2 and 3: 0 rejects, notes applied in 9d0498fd (names and docstrings, gated `--no-gain`).
binding.py 134.2 -> 43.6.
