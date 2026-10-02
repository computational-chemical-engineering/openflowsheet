"""SYN-001: the synthetic three-component ideal fixture (implementation plan §3, P01).

A, B and C are artificial pseudo-components with no chemical identity and no elemental formula.
Nothing in this package is an experimental or real-chemistry claim (`docs/derivations/SYN-001.md`).

Contents: `oracle` (the independent scalar reference), `reference_values.yaml` (Fable-authored
20-digit values, independent of the oracle), `components.yaml` (the three ComponentRecords) and
`cases/` (one ProcessRevision document per registered flowsheet case).
"""
