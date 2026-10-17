# Note from M05 to M07: `extrapolated` at C1's loop state (R-433)

From: M05 (wp/M05), design note `docs/design/M05-trust-region.md` §21.4, register R-433, build log S69.
For: M07 (wp/M07), R-424's `extrapolated` count. Copy this file to wp/M07 when M07 next touches R-424.

**What M05 found.** At C1's loop state the real reactor's inlet H2/N2 sits on the kinetics' data edge. The
reactor's per-evaluation `extrapolated` flag is correct, but at that state it is decided at solver resolution:
in M05's REAL record it flips between coupled solves 3.5e-5 K apart.
- `benchmarks/m05/records/trust-region-study-real.json`: cand-C1's P1 solve (`candidates[0].solves[0]`,
  T = 653.1500352 K) carries `limitations: ["extrapolated"]`; the minus poll at exactly 653.15 K and the plus poll
  carry none; S0 at 673.15 K carries none.
- Over the whole study, 12 of the reactor link's 61 truth requests (10 of its 32 cold experiments) were served by
  an experiment outside the data domain. The count is read from the ledger artifact
  (`trust-region-study-real.ledger.json`, anchored by `artifacts.ledger`); the record has no count field (R-433).

**What it means for M07.** R-424 counts the final coupling iteration per certified state. At C1's state that count
inherits the flip: a state a few 1e-5 K away can count as extrapolated or not. Report it as M05 does —
"reported, not a distance from the data" — and do not read a change in the count between nearby states as a
change in the physics.

**What it is not.** It is not a finding against the reactor, which flags correctly: a binary edge flag at an
on-edge state flips at solver resolution.
