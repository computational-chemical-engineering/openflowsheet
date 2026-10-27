# S11 brief, second pass: the thermal units on the new bases (design lane, `architect`)

Branch `wp/S11`, worktree `.claude/worktrees/s11`, head `3cbd3bd3` (design `0b704b6d` + WO-0 identity gate). Read first:
`docs/derivations/S11-design.md` (your first pass: §0, §4.1–§4.6, §4.4's admission and gap tables, §5, §7), ADR 0050, and
the recon digest `docs/briefs/S11-binding-recon.md` §3 (provider APIs and gaps).

## 1. The question

**Frank, 2026-10-27, answering the first pass's Q2 and Q3: "Include in S11" for both.** Design, as an addendum to S11, the
thermal units on the new bases so they ship in the same batch:
- **Pure fluids (`iapws95-v1`, `coolprop-heos-v1`), was S11b:** heater/cooler, pump, compressor, turbine (isentropic, with
  `s`), valve, mixer — and therefore two-phase pure-fluid streams under `nTP-v1` (the TP flash is degenerate in the
  saturation band): what a two-phase pure-fluid stream state is, how a PH/PS closure lands on the saturation line, quality.
  The first pass says this needs an ADR: write it (ADR 0051).
- **Wilson (`wilson-ig-v1`), was S11c:** γ–φ EO faces for the K02/T05 units — heater, flash (TP and PH), valve, mixer — and
  whatever of pump/compressor/turbine is reachable. The first pass's gap table says Wilson lacks `s` (isentropic units, PS
  closures; "closing it needs a provider version 2") and `v`/`Z` (pump work). Decide: a provider version 2 (new provider id,
  since `implementation_sha256` hashes the module bytes and existing modules must not change), or refuse those units typed
  with the reason. Frank's directive: as few limitations as possible.

What must come back: the unit models (new ids or generalised existing ones), their EO faces per basis (residual rows,
derivatives, which property ids each needs), the admission-matrix rows that change from "refused" to "yes", the two-phase
pure-fluid state and its closures, any provider additions (as new modules), verifier forms for them, envelope/W27 rows,
numbered assertions with independent expectations (e.g. IAPWS-95 steam-table values, CoolProp's own PH/PS results, energy
balances closing), the identity statement (nothing registered moves), and work orders.

## 2. Constraints

- **Do not change track A or B's work orders** (§5 of the first pass): they start building now on `wp/S11-a` / `wp/S11-b`.
  The new units build on A1's registry and A2/A3's routing and verifier forms. Your work orders are **track C (pure-fluid
  units) and track D (Wilson units)**, on files disjoint from A's and B's and from each other, starting after A3 is merged
  into `wp/S11` (state which WO of yours can start earlier). If something in A/B's design must change for C/D, say exactly
  what, as a minimal amendment.
- No change to an existing `thermo/` provider module, to any registered numerical result, or to the frozen schemas without
  this ADR saying so. The identity gate is `scripts/s11_identity.py` (`S11-IDENTITY PASS n=54497 changed=[]` at `acffd034`).
- Batch, then test once (Frank): per-commit touched tests + identity gate; one `reviewer` pass, one full gate, one CI for all of
  S11 at the end. At most two engineers at a time.
- ADR 0051. Register from **R-813** (R-800…R-812 are the first pass). Record Frank's answers to Q2/Q3 as superseding the
  first pass's defaults, and amend §0 item 10, §4.4 and §7 of `S11-design.md` with a dated amendment section rather than
  rewriting them.

## 3. Out of scope

NRTL/UNIQUAC/LLE; Helmholtz mixtures; S07b cryogenic liquids; the methanol+ethanol refit; `pr-lib-v1`; reactors; side
draws/pump-arounds; GUI.

## 4. Deliverable

`docs/derivations/S11-units-design.md` (decisions, rejected alternatives, the two-phase pure-fluid state, each unit's EO face,
admission rows, assertions, tracks C and D work orders with file ownership, risks with defaults); ADR
`docs/adr/0051-…md` (Proposed); register entries from R-813; the dated amendment section in `S11-design.md`; a docs-only
commit on `wp/S11` including this brief. Do not push. Report in at most 20 lines.
