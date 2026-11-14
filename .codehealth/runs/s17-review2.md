# S17 review 2 (reviewer, 2026-11-13): binding.py steps 76a00379..0fd8079b
Verdict: 5 accepted (1 accept, 4 accept-with-note), 0 rejects. No behaviour difference found.
Notes to act on after WO2 (names-only cleanup step, gated without --require-gain):
- 81203d61 `_without_rows` also drops orphaned parameters: rename (e.g. `_without_rows_and_orphaned_parameters`), when-not #2.
- 0fd8079b `_assembly_starts` contradicts its comment (defaults are not starts): rename `_assembly_values`; docstring: default overrides guess when a column is in both.
- e81fd1a2 caller loops `promotions` twice (720-723); one loop would do. Docstring precedence on key collision.
- ee653caa `_wiring_edges(WIRING)` moved before the refusals (pure; unmentioned in the commit message).
Playbook additions: purity of helpers, caller owns side tables; ladders whole as T | Unbound; moving a statement across an
early return must be stated as pure in the commit message, else keep order; helper name must not use a term its comment
sets apart; keyed outputs state collision precedence; a name covers every effect of the body.
Pre-existing finding (outside S17, design lane): `_promote_specifications` builds row id SPEC:<name> per specification,
not per column (binding.py:868 at 0fd8079b); a fixed specification with two promotable columns would give two
EquationSpecs with one id, `promotions` keeps the last (880). Reachability not checked. For Frank / design lane.
