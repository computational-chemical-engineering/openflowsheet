"""Application service layer.

Owns transactions and optimistic revision control, draft versus ready validation, idempotent
commits, jobs and their lifecycle events, artifact storage references, and authorization
(blueprint §3 layer table, §11). Local Python and CLI use share this one contract with any
later HTTP/MCP binding, so no mandatory network round trip exists for local scientific use
(blueprint D15). It must not contain client-specific scientific behavior.

No functionality yet; introduced by package K06.
"""
