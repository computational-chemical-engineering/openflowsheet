"""Cost estimation and life-cycle assessment as differentiable assessment functionals (E01).

E01 design `docs/derivations/E01-design.md`; ADR 0052 (Proposed); register R-850…R-862. An
assessment is an explicit post-solve functional `y = G(x, d; θ, ρ)` of a verified state, compiled
by the existing compiler as a functional `ProblemSpec` and never part of a `CompiledProblem`: an
attached assessment moves no registered result, certificate or replay identity (§4.14).

Layer introduced by package E01.
"""
