# S17 review 3 (reviewer, 2026-11-13): binding.py steps 0fd8079b..cfe9099c (8 steps)
Verdict: 8 accepted (5 accept, 3 accept-with-note), 0 rejects. No behaviour difference found.
Notes: 3f2bb3bb rename `_starts` -> `_guesses` (sits next to `_assembly_starts`); 5fe1f040 lazy `si_unit` import moved
into `_read_as_fixed` (runs only when a free entry exists; not observable unless the import fails; unmentioned in the
commit); cfe9099c `_process_graph` docstring should say column_owners is left empty and added after assembly (R-019).
Binder reads as named phases; the unnamed remainder threads spec/pinned/row_units/specification_ids across phases.
Parameter object: stop here (would bundle unrelated parameters; locals created in different phases).
Playbook: lazy-import moves are stated in the commit; loop-body-extract keeps the guard in the caller; clause helpers
return `Unbound | None`, cite their clause and appear in the caller's docstring list; helpers follow the caller in
order of first call; when-not for extract-phase: the remainder only threads the same locals, or a step drops less than
about 2 points. Not for S17: free targets computed in four places (:739, :824, :830, :1090), a dataflow refactor.
