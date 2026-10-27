# S11 build decisions — track B

Build-lane choices the design note (`docs/derivations/S11-design.md`, ADR 0050) left to the engineer, for track B
(`wp/S11-b`: B1–B4). One line each, as `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`; each is
isolated and revertible. Measurements go in the run log below.

## Decisions

## WO-B1 inventory: structural and inlet-dependent items (§4.7.2)

Structural (checked at bind from `ColumnStructure`, B2; `validate` keeps its order and messages):
S02 §5 R1 (`stage_count`), R3's stage-pressure half (`P_j*` in the provider's `P` box), R4 (side-feed
stage in 1..N, one per stage), R6 (declared single phase: the parser's `port_unsupported`), S1 (kinds),
S2 (presence and kind of each end specification), S3 (distillate and bottoms rates together), S4 (a
direct kind's sign and finiteness), S6 (top/bottom inlet against the ends: by construction, the ends
are read from the wiring), S7 (no side feed at a slot stage), S8 (N holds the ends), S9 (pressure
monotone), S10-C D8 (γ–φ kinds: `specification_unsupported(<U>.<end>.<kind>)`), S06 §5 I1 (attribute),
I2 (value, finite and 0 < x < 1).
Inlet-dependent (left to `validate` at evaluate): R2 (inlet flows), R3's inlet `T`/`P` half, R5
(inlet admissibility), S5 (rate ≥ feed), S10 (no feed: zero total flow), I3 (absent component), I4
(temperature band: §4.7.2 lists it here), I5 (rank of the split rows, whose coefficients are the
`F_c`), I6 (product split), R7 (energy precheck).

## Run log
