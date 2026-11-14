"""Orchestrator layer.

Owns solve-plan construction, bounded attempts and the active-phase controller, continuation
and pseudo-transient policy, checkpoints, budgets and recovery edges, solution verification and
certificates, failure bundles, and run provenance and replay identity (blueprint §3 layer
table, §7, §8). The phase set belongs to the local nonlinear attempt and is frozen within it
[A01]. It must not contain a hidden language model inside the trusted solve path, and it must
not import backend objects.

The recorded metadata of a solve — `SolvePolicy`, `SolveEvent`, `Checkpoint` and the
append-only `Trace` — is introduced by package K03 and lives in `numerics.solve_record`, because
it is what Newton, PTC and Anderson produce (ADR 0076 I-1); `trace` re-exports it at its old
path. The plan, the bounded attempts and the active-phase controller follow in this package.
"""
