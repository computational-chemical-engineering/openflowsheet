"""Studies over a compiled problem's pinned inputs: sensitivities, sweeps, estimation (M03).

Specification `docs/derivations/M03-studies-spec.md`; ADR 0031. A study parameter is a pinned
input already listed in `CompiledProblemMetadata.parameter_ids` (D1); its derivative comes from the
parametric twin in `compile/casadi_backend.py` (D2), and a sensitivity is issued only at a qualified
regular root (D3), from one factorization (D4). Nothing here computes a derivative by differencing:
finite differences are a test oracle (R-010) and live in the test support only.
"""
