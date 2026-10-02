"""Numerical runtime layer.

Owns residual and Jacobian evaluation mechanics, explicit sparse linear solves through SciPy
SuperLU with recorded options and linear residuals, step computation, damping and line search,
scaling application, and local convergence measures (blueprint §3 layer table, §3.1, §7.3).
Residual and Jacobian paths must describe the same function at the same state. It must not own
permission decisions, plan construction, or any agent-generated mathematics.

Scales and the linear solve are introduced by package K03. `scaling` builds `S_x` and `S_F`
from the registered physical nominals by declared quantity kind (K03 specification §4), and
`linear` is the one SuperLU solve with the explicit options and recorded evidence of ADR 0004.
Neither owns a solve *plan*: bounded attempts, the phase controller, checkpoints and budgets
belong to the orchestrator.
"""
