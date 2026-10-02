"""Structural graph and analysis layer.

Owns process and equation graphs, incidence structure, Dulmage-Mendelsohn decomposition,
strongly connected components and block triangular form, tear-candidate selection, block-size
metrics, and deterministic tie-breaking (blueprint §3 layer table, §7.2). Structural results
are diagnostic: structural matching establishes neither numerical rank nor nonlinear
feasibility (blueprint D05). It must not own numerical rank verdicts or globalization policy.

This layer is introduced by package T01, implemented against
`docs/derivations/T01-structural-spec.md` and judged against
`benchmarks/t01/reference_values.yaml`.

The declaration trace (`trace`), maximum and canonical matching with the coarse
Dulmage-Mendelsohn partition (`matching`), the affine-copy certificate (`certificates`),
unit-local degrees of freedom (`dof`), strongly connected components and the block-triangular
form (`blocks`), process loops and the tear rule (`tear`), the report and its six statements
(`report`), and the finding rule (`analysis`).

**Nothing here is recognised by name.** No unit id, stream id or row id appears in this package,
and no unit model is imported: the authoring instance of a row and the state columns of a stream
are *given* by the caller, never parsed from an id. Assertion A15 relabels every id by a
bijection and requires the image of the registered answer, which is how a name-parsing shortcut
was found and removed.

**Nothing in this layer evaluates anything.** There is no state at which it runs. The incidence
comes from the row builders traced under a set-valued algebra with the parameters opaque, not
from a compiled Jacobian — because a compiled pattern moves with a parameter value (at `r = 0`
CasADi folds `0.0 * S5.n_i` away and three entries vanish) and a conclusion that moves is not a
structural conclusion. Assertion A03 makes evaluating impossible while the analysis runs.
"""
