"""The transport bindings (T07 W6, design note §11): each reads `operations.OPERATIONS` and goes
through `operations.dispatch`, and adds nothing (§11.6). Importing this package imports no
transport library; each binding module imports its own (the optional `server` extra)."""
