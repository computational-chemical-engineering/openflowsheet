"""Compilation layer.

Owns lowering of the IR to a ``CompiledProblem``: ordered free variables and residual
equations, unit resolution, alias and fixed-variable elimination, source maps back to original
equations, declared sparsity, structural fingerprints, and negotiated optional capabilities
(blueprint §3 layer table, §3.2). Backend and callback lowering live here so that the
orchestrator imports no backend objects. It must not introduce new physical assumptions
without a recorded transformation.

No functionality yet; introduced by package K01.
"""
