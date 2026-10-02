"""Agent-native open process simulator, provisional import name ``openflowsheet``.

This distribution is the single installable package described in blueprint v3.1 §15: one
modular monorepo with logical layers rather than microservices. The subpackages ``ir``,
``units``, ``models``, ``thermo``, ``compile``, ``graph``, ``numerics``, ``orchestrator``,
and ``application`` correspond to the architectural boundaries of blueprint §3, and each one
states its own responsibility and the work package that will introduce its behavior. Later
layers (``studies``, ``adapters``, clients, and the web workbench) are deliberately absent
until their packages start, per implementation plan §2.

No functionality yet; introduced by package P00 (repository bootstrap only).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
