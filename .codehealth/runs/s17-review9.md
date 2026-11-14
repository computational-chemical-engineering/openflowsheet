# S17 review 9 (reviewer, 2026-11-14): steps f3cef5cc..4a8bcecf (4 steps, WO8a)
Verdict: 4 accepted (2 accept, 2 with a note), 0 rejects. No behaviour difference.
- c95f4cc4 notes: `_validity` docstring (replacement.py:568) omits the `_unavailable` early return (:570);
  `_hard_domain_narrowing` (:593) returns a list: `_hard_domain_narrowings` (rule 8). Order pinned by test_g9a1.
- 2b2d079f: lazy generator `_subschemas` correct (reads/exceptions keep order; never materialise). Note: `_error_refs`
  docstring (operations.py:689) omits the deliberate ValueError for an unpublished `$ref` (:697).
- 4a8bcecf note: "RFC 6901" (operations.py:712-719) overclaims: anchors resolve to the whole document, `int(token)`
  accepts -1 and 01, no percent-decoding, a scalar raises TypeError. Twins: projection.py:144 `pointer_tokens`, :157
  `resolve` (strict) and bindings/mcp.py:139 `_resolve` (whole prologue). No merge in S17 (behaviour differs). Fix:
  docstring "a lax subset ... strict form projection.resolve".
- Skipping `assemble` right: mutually recursive closures over fetch/depth/limit/sha256; only a reader class helps.
Playbook candidates: accepted forms (lazy child generator for walkers; sibling builders sharing a parameter list);
rule 15 ext (grep the shared layer for a standard's implementation before naming a helper after it); rule 4 ext
(caller docstring names non-None early returns and deliberate exceptions); when-not (mutually recursive closures over
shared captures: class or leave); commit exception lists complete or "same exceptions".
