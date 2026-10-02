"""Process IR layer.

Owns the semantic description of a process: components, model instances, connections,
specifications, scenarios, and the semantic identities that make a revision addressable
(blueprint §3 layer table, §4). It owns canonical serialization and identity, draft and
task-scoped validation inputs, and schema migrations. It must not own backend objects,
live solver state, or GUI layout, and it never reaches into numerical runtime structures.

No functionality yet; introduced by package P01.
"""
