"""Benchmark registry and its cases (implementation plan §1.2, §3; blueprint §13).

A package only so that `benchmarks.syn001.oracle` is importable from the tests and nameable in
`benchmarks/registry.yaml` as a dotted callable path. Nothing here is production code: the
oracle is an independent algebraic reference and is never called from `openflowsheet`
(implementation plan §3.2; `docs/derivations/SYN-001-oracle-spec.md` §5).
"""
