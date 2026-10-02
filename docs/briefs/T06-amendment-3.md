# Brief — T06 amendment round 3 (small items before scoring)

**To:** `specifier` (design lane). **From:** build lane, 2026-09-26. **Branch:** `wp/T06`.
**Deliverable:** dated amendments to `docs/derivations/T06-corpus-spec.md` (and the register only if
a choice could be undone later); twin re-emitted only if a registered value changes (`--check`, new
SHA); a ruling list in §2 here. No code; do not commit. Evidence: `docs/T06_DECISIONS.md` (the W6,
W12, W15 entries) and `docs/t06-measurements.md` ("2026-09-26 — M7 and W6"). **Item 1 must be ruled
before the scoring run** (the committed starts `641de215…` can still be regenerated; nothing is scored).

1. **Step 5 on a perturbed start (W6 Q1).** The start re-splits each unit's lifted outlet by a TP flash
   of the perturbed stream. Identical to the closure's split on STR-01, NET-11; different on THM-08 and
   THM-09, whose valve closes exactly at saturation — with `S2.T` perturbed their split starts
   single-phase (THM-08: 11 liquid / 9 vapour). Rule: keep, or seed from the unit's closure split
   (ADR 0012 D5's rule for traversal starts), and whether the starts file must be regenerated.
2. **Acyclic count (W6 Q2):** the plans give 10 acyclic cases (THM-09 the tenth), not "nine"; A84 states
   it as a finding — amend the text.
3. **Draw key (W6 Q3):** the key uses the fixture id, as the KATs spell it — ratify.
4. **F-BUDGET (W6 Q4):** includes `ATTEMPTS_EXHAUSTED` (K04's budget/cancellation taxonomy) — ratify.
5. **W12 Q1:** the twin's `registered_si_value` for five parameter pairs differs from the case files
   (C1 efficiency 0.751 vs 0.75; C2 conversion.A 0.51 vs 0.5; split.C 0.051 vs 0.05; C3 split_fraction
   0.61 vs 0.6; C2 drop 2500 Pa vs 0) — the generator hard-codes them; rule (fix the twin, or the
   assertion's wording).
6. **W12 Q2:** C2 with any nonzero `U-RX.pressure_drop` is refused by `plan_revision` (T01
   `SPECIFICATION_CONFLICT`) — a recycle loop with a pressure drop and no pressure-raising unit
   over-determines its pressures; A71's trace/certificate comparison cannot run on C2 — choose another
   carrier or amend A71.
7. **W12 Q3:** mutating a Quantity's unit in a test rewrites its bounds in the same unit — ratify.
8. **W12 STR-06:** its DIM-01 message now ends "not judged for a component outside the set:
   SPEC-feed-n-B" (A72 (a)), contradicting the W12 row's "every registered report unchanged" — amend.
9. **A81 (a):** the K03 OFF-B fixture re-baseline changed 22 events' `property_calls` and
   `requested_evaluations` (both forgiven counters), not one value — the build lane committed it
   (R-015); amend A81's text.

## 2. Rulings (the design lane fills this in)

Ruled 2026-09-26 by the design lane (`specifier`); spec `docs/derivations/T06-corpus-spec.md`
Amendment 3 (every changed passage carries **(A3)**); register R-067 amended. Measured on this host
at `4560c30`…`93472b6` (W13 merged meanwhile; all re-run at `93472b6`), scratch probes, no ensemble
start solved. The twin is
unchanged (`--check` 340/340, emission byte-identical, `3058c360…`).

1. **Keep.** Step 5 at a perturbed start is the provider's TP flash of the perturbed outlet stream
   for every heater-style split, PH-type included; ADR 0012 D5's closure seed is the traversal
   start's rule only (§6.2 (A3)). D5 exists because a temperature-degenerate outlet's `(n, T, P)`
   does not fix its split; every published perturbed outlet lies ≥ 0.339 K outside its band
   (THM-08 start 05; `τ_T = 1e-6 K`), where the TP flash is the only equilibrium split. The closure
   carried over breaks the split rows and puts pure B two-phase off `T_sat`; re-run, it overwrites
   the perturbed `S2.T`/`S2.n`. Uniform: STR-01's and NET-11's bracket-route valves open
   single-phase in 9/20 and 10/20 starts under the same rule. Decided on the definition, not on an
   outcome (no THM-08/THM-09 start solved). New A85 (premise, rule recomputed, zero-perturbation
   17 equal + THM-08/09's four columns, regime census). **No regeneration on this account** —
   but see item 10.
2. **Amended:** ten acyclic cases (§6.2, §7.4, §15, A84); the report's count check is against 10.
3. **Ratified:** `<case id>` in the key is the registered fixture id (§6.3); fixture ids are unique
   (`corpus.fixtures_unique`); A21's test adds "no `|` in a fixture or coordinate id".
4. **Ratified:** `F-BUDGET` = K04 `TAXONOMY`'s `budget/cancellation outcomes` (`BUDGET_EXHAUSTED`,
   `ATTEMPTS_EXHAUSTED`) (§7.2).
5. **Fix the assertion's wording, not the twin:** A70 compares each pair with its SI twin (the case
   with that input at `registered_si_value`, in SI); exactly five pairs differ from their case by
   design (75.1 % is the pair the binary reading breaks); each of the five SI twins moves
   `constants_sha256` (measured).
6. **Another carrier:** A71 splits into (a) the binding half on C2 (unchanged), (b) C2's refusal
   registered (`analyse` `SPECIFICATION_CONFLICT` at 1 Pa, 2500 Pa and 2.5 kPa; `plan_revision`'s
   `ValueError` identical in both spellings), (c) the solve half on **NET-06's `U-PHF.pressure_drop`**
   — measured `CONVERGED`/`VERIFIED` in both spellings, 3 Jacobians, traces and certificates
   byte-identical, `S3.P = S4.P = S5.P = 97 500.0 Pa`. Q18 opened (T07: typed result for a
   non-closed plan).
7. **Ratified:** an in-test unit mutation writes the whole Quantity (value, bounds, nominal) in the
   new unit, round-tripping bit for bit (A2 table's preamble).
8. **Amended:** W12's inertness — reports unchanged except exactly three `DIM-01` messages
   (STA-03 ×2, STR-06) (§17 W12).
9. **Amended:** A81 (a) — one file, `property_calls` and `requested_evaluations` in 22 of 27
   events (+1 in 6, +2 in 16; 44 values), nothing else (A81, §17 W15, A2.5).
10. **New, from W13 (landed during this round): re-emit the starts file once.** It records
    `provider.implementation_sha256`, which ADR 0017 moved (`75c9d5ba…` → `67e47281…`); ADR 0017
    D6's "the starts file records no provider identity" is wrong (finding 17; erratum recommended,
    not written). Regenerated under the new provider at `d0797f6`, twice (default and single BLAS
    threads): the only differing JSON path is `/provider/implementation_sha256`; new sha256
    **`3a7bd49c66493744753d1eac554101317c931e0ef51d9154d6f7cab3124fef82`** (1 109 603 bytes).
    Every start stands. §6.5 (A3), A25, chunk W16. *Alternative:* keep `641de215…` and make
    `check`/A25 compare modulo the provider block — rejected as a permanent special case in the
    check; reversible by reverting W16's one commit.

**Build-lane checklist (spec §17 (A3)).** W16: `generate --force` → `3a7bd49c…` exactly, registry
`ensemble.starts_sha256`, A25 with the live provider block, the JSON-path proof in
`docs/t06-measurements.md`. W6 (A3): A85 test; `ACYCLIC_TEXT_COUNT` 10 and A84's test; A21's `|`
check; do not touch `generator.py`. W12 (A3): A70 docstrings and the five `constants_sha256`
checks; A71 (b) and (c). Then the scoring run.
