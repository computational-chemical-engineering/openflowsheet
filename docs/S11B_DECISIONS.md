# S11 build decisions — track B

Build-lane choices the design note (`docs/derivations/S11-design.md`, ADR 0050) left to the engineer, for track B
(`wp/S11-b`: B1–B4). One line each, as `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`; each is
isolated and revertible. Measurements go in the run log below.

## Decisions

DECISION: Q7 (does the binder require every multiplicity-1 port wired?) → fact: it requires every *declared* material port wired, of any multiplicity (`bind_revision_flowsheet`, `port_unwired`), so `many` does not make `top`/`bottom` optional; `ColumnUnit.ports()` declares only the ports its instance wires (the model's `PORTS` lists all five). Alternative: an optional-port notion in the binder (track A / I1 file, frozen-adjacent). Reversible by: making `ports()` return `PORTS`.
DECISION (escalated): where the column's end specifications are read → instance parameters `condenser.<kind>[.<attr>]`, `reboiler.<kind>[.<attr>]` (a `role: fixed` specification with target `parameters.<end>.<kind>…` lands there too), one function `column_unit.end_entries`. The note's revision *pins* need a `condenser.*`/`reboiler.*` target path in `revision_flowsheet._PATH_KINDS` and the routing in `_read` (track A's file), and `PinColumn` has no non-stream quantity (`revision_binding.py`); the column's parameters are also absent from `_PARAMETER_KINDS`, so only SI-unit-of-the-declared-kind is checked. Alternative: the paths as the note says (design lane + A/I1). Reversible by: rewriting `end_entries` to read `view.pins`.
DECISION: a column instance id must be a token (S01's `_token`: its property blocks are named after it) → refused at parse as `id_unsupported(<U>)` with a hint, not left to surface as `value_outside_model_domain`. Alternative: map ids to tokens (changes every row id). Reversible by: deleting the check.
DECISION: every side feed on `feed` shares one declared phase (the revision reader's R4 is one phase per port: `port_phase_ambiguous`) → recorded in L-COL-1. Alternative: one port per feed. Reversible by: n/a (reader rule).
DECISION: inlet ports `feed`/`top`/`bottom` declared `vapor_liquid`, or a `bottoms` not `liquid`, or a distillate neither → `port_unsupported(<U>.<port>)` as §4.7.1 says (the binder's idiom for one-phase ports is `port_phase_unsupported`). Alternative: the binder's idiom. Reversible by: renaming the code in `column_unit`.
DECISION: `column_binding` imports `ModelSignature`/`Configuration` from `revision_binding`; I1 registering it inside `revision_binding` must import it lazily (or at the module end) to avoid a cycle. Alternative: move the two types. Reversible by: n/a (I1's choice).
DECISION: where the recovery definition's row builder lives (`test_k02_unit_models` forbids a builder in a unit module) → `models/rows.py` `scaled_sum_definition_row`, a new function (no existing builder changed), though rows.py is not in track B's §5 list (track A does not touch it). Alternative: a design-lane amendment of the ownership table. Reversible by: reverting the B1 fix-up commit.

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
